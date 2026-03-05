"""Load SWE-bench datasets from HuggingFace and normalize to TaskRecord objects."""

from __future__ import annotations

from datasets import load_dataset

from bench_cleanser.models import TaskRecord


def _load_dataset_as_records(name: str, max_tasks: int) -> list[TaskRecord]:
    """Load a HuggingFace dataset and convert rows to TaskRecord objects."""
    ds = load_dataset(name, split="test")
    records: list[TaskRecord] = []
    for row in ds:
        if len(records) >= max_tasks:
            break
        records.append(TaskRecord.from_dict(row))
    return records


def load_swebench_verified(max_tasks: int = 500) -> list[TaskRecord]:
    """Load from the SWE-bench Verified dataset.

    Args:
        max_tasks: Maximum number of task records to return.

    Returns:
        A list of up to *max_tasks* TaskRecord objects.
    """
    return _load_dataset_as_records("princeton-nlp/SWE-bench_Verified", max_tasks)


def load_swebench_lite(max_tasks: int = 500) -> list[TaskRecord]:
    """Load from the SWE-bench Lite dataset.

    Args:
        max_tasks: Maximum number of task records to return.

    Returns:
        A list of up to *max_tasks* TaskRecord objects.
    """
    return _load_dataset_as_records("princeton-nlp/SWE-bench_Lite", max_tasks)


def load_all(max_per_dataset: int = 500) -> list[TaskRecord]:
    """Load from both SWE-bench Verified and Lite, concatenated.

    Args:
        max_per_dataset: Maximum number of records to load from each dataset.

    Returns:
        Combined list of TaskRecord objects from both datasets.
    """
    verified = load_swebench_verified(max_tasks=max_per_dataset)
    lite = load_swebench_lite(max_tasks=max_per_dataset)
    return verified + lite


def load_single_task(instance_id: str) -> TaskRecord | None:
    """Search both datasets for a specific instance_id.

    Args:
        instance_id: The unique instance identifier to look for.

    Returns:
        The matching TaskRecord, or None if not found.
    """
    for name in [
        "princeton-nlp/SWE-bench_Verified",
        "princeton-nlp/SWE-bench_Lite",
    ]:
        ds = load_dataset(name, split="test")
        for row in ds:
            if row.get("instance_id") == instance_id:
                return TaskRecord.from_dict(row)
    return None
