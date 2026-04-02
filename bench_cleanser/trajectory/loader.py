"""Load agent trajectories from various sources."""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
from typing import Any

from bench_cleanser.trajectory.models import ActionType, TrajectoryAction, TrajectoryRecord

logger = logging.getLogger(__name__)


def load_from_jsonl(
    path: str | pathlib.Path,
    instance_ids: set[str] | None = None,
) -> list[TrajectoryRecord]:
    """Load trajectories from a local JSONL file.

    Each line should be a JSON object with at minimum:
    - instance_id
    - trajectory or actions (list of action dicts)
    - model_patch or final_patch
    """
    filepath = pathlib.Path(path)
    if not filepath.exists():
        logger.warning("Trajectory file not found: %s", filepath)
        return []

    records = []
    for line_num, line in enumerate(filepath.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            iid = data.get("instance_id", "")
            if instance_ids and iid not in instance_ids:
                continue
            records.append(TrajectoryRecord.from_dict(data))
        except Exception as exc:
            logger.warning("Failed to parse line %d of %s: %s", line_num, filepath, exc)

    logger.info("Loaded %d trajectories from %s", len(records), filepath)
    return records


def load_from_json_dir(
    dir_path: str | pathlib.Path,
    instance_ids: set[str] | None = None,
) -> list[TrajectoryRecord]:
    """Load trajectories from a directory of individual JSON files.

    Each JSON file should contain a single trajectory record.
    """
    dirpath = pathlib.Path(dir_path)
    if not dirpath.is_dir():
        logger.warning("Trajectory directory not found: %s", dirpath)
        return []

    records = []
    for json_file in dirpath.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            iid = data.get("instance_id", "")
            if instance_ids and iid not in instance_ids:
                continue
            records.append(TrajectoryRecord.from_dict(data))
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", json_file, exc)

    logger.info("Loaded %d trajectories from %s", len(records), dirpath)
    return records


def load_from_huggingface(
    dataset_name: str,
    split: str = "train",
    instance_ids: set[str] | None = None,
    agent_name: str = "",
) -> list[TrajectoryRecord]:
    """Load trajectories from a HuggingFace dataset.

    Many SWE-bench agent repos upload trajectory datasets. This loader
    normalizes the common fields (instance_id, trajectory, model_patch).

    Args:
        dataset_name: HuggingFace dataset identifier.
        split: Dataset split to load.
        instance_ids: Only include these instance IDs.
        agent_name: Override agent_name field (useful when dataset doesn't include it).
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("datasets library required for HuggingFace loading")
        return []

    try:
        ds = load_dataset(dataset_name, split=split)
    except Exception as exc:
        logger.error("Failed to load HuggingFace dataset %s: %s", dataset_name, exc)
        return []

    records = []
    for row in ds:
        iid = row.get("instance_id", "")
        if instance_ids and iid not in instance_ids:
            continue

        # Normalize trajectory field
        trajectory = row.get("trajectory", [])
        if isinstance(trajectory, str):
            try:
                trajectory = json.loads(trajectory)
            except json.JSONDecodeError:
                trajectory = []

        data = {
            "instance_id": iid,
            "agent_name": agent_name or row.get("model_name_or_path", ""),
            "trajectory": trajectory,
            "model_patch": row.get("model_patch", ""),
            "resolved": row.get("resolved", False),
        }
        records.append(TrajectoryRecord.from_dict(data))

    logger.info(
        "Loaded %d trajectories from HuggingFace %s (split=%s)",
        len(records), dataset_name, split,
    )
    return records


def load_from_docent(
    collection_id: str,
    api_key: str,
    server_url: str = "https://api.docent.transluce.org",
    instance_ids: set[str] | None = None,
    model_name: str | None = None,
    dql_query: str | None = None,
) -> list[TrajectoryRecord]:
    """Load agent trajectories from Docent platform.

    Uses the docent-python SDK to query agent runs via DQL and fetch
    full trajectory data for each matching run.

    Args:
        collection_id: Docent collection UUID.
        api_key: Docent API key.
        server_url: Docent API server URL.
        instance_ids: Only include these instance IDs.
        model_name: Filter by model name in DQL query.
        dql_query: Custom DQL query (overrides default).
    """
    try:
        from docent import Docent
    except ImportError:
        logger.error("docent-python library required for Docent loading. pip install docent-python")
        return []

    client = Docent(api_key=api_key, server_url=server_url)

    if dql_query is None:
        # Build default DQL query
        where_clauses = []
        if model_name:
            where_clauses.append(f"(ar.metadata_json->>'model_name' = '{model_name}')")
        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        dql_query = f"""SELECT
  ar.id AS agent_run_id,
  ar.metadata_json->>'instance_id' AS metadata_instance_id,
  ar.metadata_json->>'model_name' AS metadata_model_name,
  ar.metadata_json->>'resolved' AS metadata_resolved,
  ar.metadata_json->>'turns' AS metadata_turns,
  ar.created_at AS created_at
FROM agent_runs ar
{where_str}
ORDER BY ar.created_at ASC"""

    logger.info("Executing DQL query on collection %s", collection_id)
    result = client.execute_dql(collection_id, dql_query)
    df = client.dql_result_to_df_experimental(result)

    logger.info("DQL returned %d agent runs", len(df))

    records = []
    for _, row in df.iterrows():
        run_id = row.get("agent_run_id", "")
        iid = row.get("metadata_instance_id", "")

        if instance_ids and iid not in instance_ids:
            continue

        resolved_str = str(row.get("metadata_resolved", "false")).lower()
        resolved = resolved_str in ("true", "1", "yes")
        agent_model = row.get("metadata_model_name", "")

        try:
            agent_run = client.get_agent_run(collection_id, run_id)
        except Exception as exc:
            logger.warning("Failed to fetch agent run %s: %s", run_id, exc)
            continue

        # Parse transcript messages into TrajectoryActions
        messages = getattr(agent_run, "transcript", None) or []
        if hasattr(messages, "messages"):
            messages = messages.messages
        if not isinstance(messages, list):
            messages = []

        actions = []
        final_patch = ""
        raw_messages = []

        for msg in messages:
            if isinstance(msg, dict):
                raw_messages.append(msg)
                role = msg.get("role", "")
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle structured content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                tool_name = block.get("name", "")
                                tool_input = json.dumps(block.get("input", {}))[:50000]
                                action_type = _map_tool_to_action_type(tool_name)
                                actions.append(TrajectoryAction(
                                    action_type=action_type,
                                    content=tool_input,
                                    tool_name=tool_name,
                                    role=role,
                                ))
                            elif block.get("type") == "tool_result":
                                result_content = block.get("content", "")
                                if isinstance(result_content, list):
                                    result_content = "\n".join(
                                        b.get("text", "") for b in result_content
                                        if isinstance(b, dict) and b.get("type") == "text"
                                    )
                                if actions:
                                    actions[-1].observation = str(result_content)[:50000]
                    content = "\n".join(text_parts)

                if role == "assistant" and content:
                    actions.append(TrajectoryAction(
                        action_type=ActionType.THINK,
                        content=content,
                        role=role,
                    ))
                elif role == "tool" and content:
                    # Tool response; attach as observation to last action
                    if actions:
                        actions[-1].observation = str(content)[:50000]
                    else:
                        actions.append(TrajectoryAction(
                            action_type=ActionType.OTHER,
                            content=str(content),
                            role=role,
                        ))
            else:
                # Handle Docent message objects with attributes
                raw_messages.append({"type": str(type(msg).__name__), "str": str(msg)[:1000]})
                msg_role = getattr(msg, "role", "")
                msg_content = getattr(msg, "content", "")
                if msg_role == "assistant" and msg_content:
                    actions.append(TrajectoryAction(
                        action_type=ActionType.THINK,
                        content=str(msg_content),
                        role=msg_role,
                    ))

        # Try to extract final patch from the last edit/write action
        for action in reversed(actions):
            if action.action_type in (ActionType.EDIT, ActionType.WRITE) and action.content:
                final_patch = action.content
                break

        turns = 0
        try:
            turns = int(row.get("metadata_turns", 0))
        except (ValueError, TypeError):
            turns = len([a for a in actions if a.role == "assistant"])

        records.append(TrajectoryRecord(
            instance_id=iid,
            agent_name=agent_model,
            actions=actions,
            final_patch=final_patch,
            resolved=resolved,
            passed_tests=resolved,
            model_name=agent_model,
            total_tokens=0,
            turn_count=turns,
            raw_messages=raw_messages,
        ))

    logger.info("Loaded %d trajectories from Docent collection %s", len(records), collection_id)
    return records


def _map_tool_to_action_type(tool_name: str) -> ActionType:
    """Map Docent/Claude tool names to ActionType."""
    tool_name_lower = tool_name.lower()
    if any(t in tool_name_lower for t in ("edit", "replace", "patch")):
        return ActionType.EDIT
    if any(t in tool_name_lower for t in ("write", "create_file")):
        return ActionType.WRITE
    if any(t in tool_name_lower for t in ("read", "cat", "view")):
        return ActionType.READ
    if any(t in tool_name_lower for t in ("bash", "terminal", "execute", "run", "shell")):
        return ActionType.TERMINAL
    if any(t in tool_name_lower for t in ("search", "grep", "find", "glob")):
        return ActionType.SEARCH
    if any(t in tool_name_lower for t in ("browser", "web", "fetch")):
        return ActionType.BROWSE
    return ActionType.OTHER


def load_trajectories(
    source: str,
    instance_ids: set[str] | None = None,
    agent_name: str = "",
    hf_split: str = "train",
    api_key: str = "",
    model_filter: str = "",
) -> list[TrajectoryRecord]:
    """Auto-detect source type and load trajectories.

    Args:
        source: Path to JSONL file, JSON directory, HuggingFace dataset name,
            or Docent collection UUID.
        instance_ids: Only include these instance IDs.
        agent_name: Override agent name (for HuggingFace sources).
        hf_split: Split for HuggingFace datasets.
        api_key: API key for Docent loading (or set DOCENT_API_KEY env var).
        model_filter: Filter by model name (for Docent sources).
    """
    # Check if source looks like a Docent collection UUID
    if re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", source):
        docent_key = api_key or os.environ.get("DOCENT_API_KEY", "")
        if not docent_key:
            logger.error("Docent API key required. Pass api_key or set DOCENT_API_KEY env var.")
            return []
        return load_from_docent(
            collection_id=source,
            api_key=docent_key,
            instance_ids=instance_ids,
            model_name=model_filter or None,
        )

    path = pathlib.Path(source)

    if path.is_file() and path.suffix in (".jsonl", ".json"):
        if path.suffix == ".jsonl":
            return load_from_jsonl(path, instance_ids)
        # Single JSON file — treat as single-record
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = []
                for item in data:
                    iid = item.get("instance_id", "")
                    if instance_ids and iid not in instance_ids:
                        continue
                    records.append(TrajectoryRecord.from_dict(item))
                return records
            else:
                return [TrajectoryRecord.from_dict(data)]
        except Exception as exc:
            logger.error("Failed to load %s: %s", path, exc)
            return []

    if path.is_dir():
        return load_from_json_dir(path, instance_ids)

    # Assume HuggingFace dataset name
    return load_from_huggingface(
        source, split=hf_split, instance_ids=instance_ids, agent_name=agent_name,
    )
