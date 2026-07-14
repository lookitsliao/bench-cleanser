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


def _included(instance_id: str, instance_ids: set[str] | None) -> bool:
    return instance_ids is None or instance_id in instance_ids


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _payload_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _content_text(value: Any) -> str:
    """Flatten message content without discarding structured observations."""

    if not isinstance(value, list):
        return _payload_text(value)
    parts: list[str] = []
    for block in value:
        text = _value(block, "text")
        if text is None:
            text = _value(block, "content")
        rendered = _payload_text(text)
        if rendered:
            parts.append(rendered)
    return "\n".join(parts)


def _tool_call_parts(tool_call: Any) -> tuple[str, str, str]:
    function = _value(tool_call, "function")
    if function is not None:
        name = _value(function, "name", "")
        arguments = _value(function, "arguments", "")
    else:
        name = _value(tool_call, "name", _value(tool_call, "type", ""))
        arguments = _value(tool_call, "input", _value(tool_call, "arguments", ""))
    call_id = _value(tool_call, "id", _value(tool_call, "tool_call_id", ""))
    return _payload_text(call_id), _payload_text(name), _payload_text(arguments)


def _raw_message(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        # Docent may leave Pydantic objects nested inside an otherwise plain
        # mapping. Round-tripping makes the retained provenance JSON-safe.
        return json.loads(json.dumps(message, ensure_ascii=False, default=str))
    return {
        "role": _payload_text(_value(message, "role", "")),
        "content": _content_text(_value(message, "content", _value(message, "text", ""))),
        "tool_call_id": _payload_text(_value(message, "tool_call_id", "")),
    }


def _all_transcript_messages(agent_run: Any) -> list[Any]:
    transcripts = _value(agent_run, "transcripts") or []
    messages: list[Any] = []
    if isinstance(transcripts, (list, tuple)):
        for transcript in transcripts:
            transcript_messages = _value(transcript, "messages", []) or []
            if isinstance(transcript_messages, (list, tuple)):
                messages.extend(transcript_messages)
    if messages:
        return messages

    legacy = _value(agent_run, "transcript", []) or []
    legacy_messages = _value(legacy, "messages", legacy)
    if isinstance(legacy_messages, (list, tuple)):
        return list(legacy_messages)
    return []


def _parse_docent_messages(
    messages: list[Any],
) -> tuple[list[TrajectoryAction], list[dict[str, Any]]]:
    """Normalize Anthropic/OpenAI-style messages while preserving causality."""

    actions: list[TrajectoryAction] = []
    actions_by_call_id: dict[str, TrajectoryAction] = {}
    pending_tools: list[TrajectoryAction] = []
    raw_messages: list[dict[str, Any]] = []

    def add_tool(tool_call: Any, role: str) -> None:
        call_id, tool_name, arguments = _tool_call_parts(tool_call)
        action = TrajectoryAction(
            action_type=_map_tool_to_action_type(tool_name),
            content=arguments,
            tool_name=tool_name,
            tool_call_id=call_id,
            role=role,
        )
        actions.append(action)
        pending_tools.append(action)
        if call_id:
            actions_by_call_id[call_id] = action

    def attach_observation(call_id: str, content: Any, role: str) -> None:
        observation = _content_text(content)
        target = actions_by_call_id.get(call_id) if call_id else None
        if target is None and not call_id:
            unmatched = [action for action in pending_tools if not action.observation]
            if len(unmatched) == 1:
                target = unmatched[0]
        if target is None:
            actions.append(TrajectoryAction(
                action_type=ActionType.OTHER,
                content="",
                observation=observation,
                role=role,
                tool_call_id=call_id,
            ))
            return
        if target.observation and observation:
            target.observation += "\n" + observation
        elif observation:
            target.observation = observation

    for message in messages:
        raw_messages.append(_raw_message(message))
        role = _payload_text(_value(message, "role", ""))
        content = _value(message, "content", _value(message, "text", ""))
        top_level_call_id = _payload_text(_value(message, "tool_call_id", ""))

        if isinstance(content, list):
            for block in content:
                block_type = _payload_text(_value(block, "type", ""))
                if block_type in {"text", "input_text", "output_text"}:
                    text = _content_text(_value(block, "text", _value(block, "content", "")))
                    if role == "assistant" and text:
                        actions.append(TrajectoryAction(
                            action_type=ActionType.THINK,
                            content=text,
                            role=role,
                        ))
                elif block_type in {"tool_use", "tool_call"}:
                    add_tool(block, role)
                elif block_type in {"tool_result", "tool_output"}:
                    call_id = _payload_text(
                        _value(block, "tool_use_id", _value(block, "tool_call_id", ""))
                    )
                    attach_observation(call_id, _value(block, "content", ""), role)
        else:
            if role == "assistant" and _content_text(content):
                actions.append(TrajectoryAction(
                    action_type=ActionType.THINK,
                    content=_content_text(content),
                    role=role,
                ))
            elif role == "tool" or (role == "user" and top_level_call_id):
                attach_observation(top_level_call_id, content, role)

        tool_calls = _value(message, "tool_calls", []) or []
        if isinstance(tool_calls, (list, tuple)):
            for tool_call in tool_calls:
                add_tool(tool_call, role)

    return actions, raw_messages


def _looks_like_patch(value: str) -> bool:
    return (
        "diff --git " in value
        or ("--- a/" in value and "+++ b/" in value)
        or ("*** Begin Patch" in value and "*** End Patch" in value)
    )


def _patch_from_tool_payload(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                value = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                return ""
        elif _looks_like_patch(stripped):
            return stripped
        else:
            return ""
    if isinstance(value, dict):
        for key in ("final_patch", "model_patch", "patch", "diff"):
            if key in value:
                candidate = _patch_from_tool_payload(value[key])
                if candidate:
                    return candidate
    return ""


def _explicit_patch(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("final_patch", "model_patch"):
            if key in value:
                return _explicit_patch(value[key])
    return ""


def _extract_final_patch(agent_run: Any, row: Any, actions: list[TrajectoryAction]) -> str:
    for field_name in (
        "metadata_final_patch",
        "metadata_model_patch",
        "final_patch",
        "model_patch",
    ):
        candidate = _explicit_patch(_value(row, field_name))
        if candidate:
            return candidate
    for field_name in ("final_patch", "model_patch"):
        candidate = _explicit_patch(_value(agent_run, field_name))
        if candidate:
            return candidate
    for metadata_name in ("metadata_json", "metadata"):
        metadata = _value(agent_run, metadata_name)
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = None
        candidate = _explicit_patch(metadata)
        if candidate:
            return candidate

    # A single explicit patch tool payload is usable. Multiple edit payloads
    # are not a final repository diff and must not be presented as one.
    candidates = [
        candidate
        for action in actions
        if action.action_type in {ActionType.EDIT, ActionType.WRITE}
        for candidate in [_patch_from_tool_payload(action.content)]
        if candidate
    ]
    return candidates[0] if len(candidates) == 1 else ""


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
    if filepath.is_symlink():
        logger.error("Refusing symlinked trajectory file: %s", filepath)
        return []

    records = []
    try:
        with filepath.open(encoding="utf-8") as handle:
            for line_num, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = TrajectoryRecord.from_dict(data)
                    if not _included(record.instance_id, instance_ids):
                        continue
                    records.append(record)
                except Exception as exc:
                    logger.warning(
                        "Failed to parse line %d of %s: %s", line_num, filepath, exc
                    )
    except (OSError, UnicodeError) as exc:
        logger.error("Failed to read trajectory file %s: %s", filepath, exc)
        # A decode/read failure means completeness is unknown. Do not return a
        # valid-looking prefix of the requested corpus.
        return []

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
    if dirpath.is_symlink():
        logger.error("Refusing symlinked trajectory directory: %s", dirpath)
        return []

    records = []
    for json_file in sorted(
        path for path in dirpath.iterdir() if path.suffix.lower() == ".json"
    ):
        if json_file.is_symlink():
            logger.warning("Skipping symlinked trajectory file: %s", json_file)
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            record = TrajectoryRecord.from_dict(data)
            if not _included(record.instance_id, instance_ids):
                continue
            records.append(record)
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
        try:
            data = dict(row)
            action_field = "actions" if "actions" in data else "trajectory"
            trajectory = data.get(action_field, [])
            if isinstance(trajectory, str):
                try:
                    trajectory = json.loads(trajectory)
                except json.JSONDecodeError as exc:
                    raise ValueError("trajectory is not valid JSON") from exc
            data[action_field] = trajectory
            if agent_name:
                data["agent_name"] = agent_name
            record = TrajectoryRecord.from_dict(data)
            if not _included(record.instance_id, instance_ids):
                continue
            records.append(record)
        except (TypeError, ValueError) as exc:
            iid = _value(row, "instance_id", "")
            logger.warning("Skipping malformed HuggingFace trajectory %r: %s", iid, exc)

    logger.info(
        "Loaded %d trajectories from HuggingFace %s (split=%s)",
        len(records), dataset_name, split,
    )
    return records


def load_from_docent(
    collection_id: str,
    api_key: str,
    server_url: str = "https://api.docent.transluce.org",
    frontend_url: str = "https://docent.transluce.org",
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
        server_url: Docent API server URL. The SDK appends ``/rest``
            internally — pass the bare API root, not the REST suffix.
        frontend_url: Docent frontend URL. Recent SDK versions warn
            (and will eventually error) when only one of api_url /
            frontend_url is supplied, so we pass both explicitly.
        instance_ids: Only include these instance IDs.
        model_name: Filter by model name in DQL query.
        dql_query: Custom DQL query (overrides default).
    """
    try:
        from docent import Docent
    except ImportError:
        logger.error("docent-python library required for Docent loading. pip install docent-python")
        return []

    client = Docent(
        api_key=api_key,
        api_url=server_url,
        frontend_url=frontend_url,
    )

    if dql_query is None:
        # Build default DQL query
        where_clauses = []
        if model_name:
            escaped_model_name = model_name.replace("'", "''")
            where_clauses.append(
                f"(ar.metadata_json->>'model_name' = '{escaped_model_name}')"
            )
        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        dql_query = f"""SELECT
  ar.id AS agent_run_id,
  ar.metadata_json->>'instance_id' AS metadata_instance_id,
  ar.metadata_json->>'model_name' AS metadata_model_name,
  ar.metadata_json->>'resolved' AS metadata_resolved,
  ar.metadata_json->>'turns' AS metadata_turns,
  ar.metadata_json->>'final_patch' AS metadata_final_patch,
  ar.metadata_json->>'model_patch' AS metadata_model_patch,
  ar.created_at AS created_at
FROM agent_runs ar
{where_str}
ORDER BY ar.created_at ASC"""

    logger.info("Executing DQL query on collection %s", collection_id)
    try:
        result = client.execute_dql(collection_id, dql_query)
        df = client.dql_result_to_df_experimental(result)
    except Exception as exc:
        logger.error("Docent query failed for collection %s: %s", collection_id, exc)
        return []

    logger.info("DQL returned %d agent runs", len(df))

    # Filter to target instance_ids first to avoid fetching unnecessary runs
    if instance_ids is not None:
        filtered_rows = [(idx, row) for idx, row in df.iterrows()
                         if _payload_text(
                             _value(row, "metadata_instance_id", "")
                         ).strip() in instance_ids]
    else:
        filtered_rows = list(df.iterrows())

    total_to_fetch = len(filtered_rows)
    logger.info("Fetching %d agent run transcripts from Docent", total_to_fetch)

    try:
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        use_rich = True
    except ImportError:
        use_rich = False

    records: list[TrajectoryRecord] = []

    def _fetch_and_parse(row, progress=None, task_id=None):
        run_id = _payload_text(_value(row, "agent_run_id", "")).strip()
        iid = _payload_text(_value(row, "metadata_instance_id", "")).strip()

        try:
            agent_run = client.get_agent_run(collection_id, run_id)
        except Exception as exc:
            logger.warning("Failed to fetch agent run %s: %s", run_id, exc)
            if progress is not None and task_id is not None:
                progress.update(task_id, advance=1)
            return None

        try:
            messages = _all_transcript_messages(agent_run)
            actions, raw_messages = _parse_docent_messages(messages)
            raw_turns = _value(row, "metadata_turns")
            if raw_turns in (None, ""):
                raw_turns = len([action for action in actions if action.role == "assistant"])
            record = TrajectoryRecord.from_dict({
                "instance_id": iid,
                "agent_name": _value(row, "metadata_model_name", ""),
                "actions": actions,
                "final_patch": _extract_final_patch(agent_run, row, actions),
                "resolved": _value(row, "metadata_resolved"),
                "model_name": _value(row, "metadata_model_name", ""),
                "total_tokens": 0,
                "turn_count": raw_turns,
                "raw_messages": raw_messages,
            })
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed Docent run %s: %s", run_id, exc)
            if progress is not None and task_id is not None:
                progress.update(task_id, advance=1)
            return None

        if progress is not None and task_id is not None:
            status = f"loaded:{len(records)+1} actions:{len(actions)} {record.instance_id[:40]}"
            progress.update(task_id, advance=1, status=status)

        return record

    if use_rich:
        console = Console()
        with Progress(
            SpinnerColumn(), TextColumn("[bold magenta]docent-fetch"),
            BarColumn(bar_width=40), MofNCompleteColumn(),
            TimeElapsedColumn(), TextColumn("[dim]{task.fields[status]}"),
            console=console,
        ) as progress:
            task_id = progress.add_task("Fetching", total=total_to_fetch, status="Starting...")
            for _, row in filtered_rows:
                result = _fetch_and_parse(row, progress, task_id)
                if result is not None:
                    records.append(result)
    else:
        for _, row in filtered_rows:
            result = _fetch_and_parse(row)
            if result is not None:
                records.append(result)

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
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        source,
        flags=re.IGNORECASE,
    ):
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
    if path.is_symlink():
        logger.error("Refusing symlinked trajectory source: %s", path)
        return []
    suffix = path.suffix.lower()

    if path.is_file() and suffix in (".jsonl", ".json"):
        if suffix == ".jsonl":
            return load_from_jsonl(path, instance_ids)
        # Single JSON file — treat as single-record
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            records = []
            for index, item in enumerate(items):
                try:
                    if not isinstance(item, dict):
                        raise ValueError("trajectory entry must be an object")
                    record = TrajectoryRecord.from_dict(item)
                    if not _included(record.instance_id, instance_ids):
                        continue
                    records.append(record)
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "Skipping malformed trajectory %d in %s: %s",
                        index,
                        path,
                        exc,
                    )
            return records
        except Exception as exc:
            logger.error("Failed to load %s: %s", path, exc)
            return []

    if path.is_dir():
        return load_from_json_dir(path, instance_ids)

    if path.exists():
        logger.warning("Unsupported local trajectory source: %s", path)
        return []

    if (
        suffix in {".json", ".jsonl"}
        or path.is_absolute()
        or source.startswith(("./", "../", "~"))
    ):
        logger.warning("Local trajectory source not found: %s", path)
        return []

    # Assume HuggingFace dataset name
    return load_from_huggingface(
        source, split=hf_split, instance_ids=instance_ids, agent_name=agent_name,
    )
