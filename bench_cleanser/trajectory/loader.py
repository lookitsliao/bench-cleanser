"""Load agent trajectories from various sources."""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

from bench_cleanser.trajectory.models import TrajectoryRecord

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


def load_trajectories(
    source: str,
    instance_ids: set[str] | None = None,
    agent_name: str = "",
    hf_split: str = "train",
) -> list[TrajectoryRecord]:
    """Auto-detect source type and load trajectories.

    Args:
        source: Path to JSONL file, JSON directory, or HuggingFace dataset name.
        instance_ids: Only include these instance IDs.
        agent_name: Override agent name (for HuggingFace sources).
        hf_split: Split for HuggingFace datasets.
    """
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
