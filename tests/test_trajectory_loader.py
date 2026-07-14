"""Regression tests for strict, source-independent trajectory ingestion."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bench_cleanser.trajectory.loader as loader
from bench_cleanser.trajectory.loader import (
    _all_transcript_messages,
    _extract_final_patch,
    _parse_docent_messages,
    load_from_docent,
    load_from_huggingface,
    load_from_json_dir,
    load_from_jsonl,
    load_trajectories,
)
from bench_cleanser.trajectory.models import ActionType, TrajectoryAction, TrajectoryRecord


def _record(instance_id: str, outcome_field: str = "resolved", outcome: Any = True) -> dict:
    return {
        "instance_id": instance_id,
        outcome_field: outcome,
        "actions": [{"type": "terminal", "command": "pytest", "output": "ok"}],
        "model_patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n",
    }


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("resolved", True, True),
        ("resolved", False, False),
        ("resolved", " YES ", True),
        ("resolved", "0", False),
        ("passed_tests", 1, True),
        ("passed_tests", "no", False),
    ],
)
def test_record_normalizes_one_observed_outcome(field: str, value: Any, expected: bool) -> None:
    record = TrajectoryRecord.from_dict(_record("task-1", field, value))
    assert record.resolved is expected
    assert record.passed_tests is expected


@pytest.mark.parametrize(
    "payload",
    [
        {"instance_id": "task-1"},
        {"instance_id": "task-1", "resolved": ""},
        {"instance_id": "task-1", "resolved": None},
        {"instance_id": "task-1", "resolved": "unknown"},
        {"instance_id": "task-1", "resolved": False, "passed_tests": True},
    ],
)
def test_record_rejects_unknown_or_contradictory_outcome(payload: dict) -> None:
    with pytest.raises(ValueError):
        TrajectoryRecord.from_dict(payload)


def test_action_preserves_structured_content_observation_and_call_id() -> None:
    action = TrajectoryAction.from_dict({
        "type": "terminal",
        "content": {"cmd": "pytest"},
        "output": ["one", "two"],
        "tool_use_id": "call-1",
    })
    assert action.action_type is ActionType.TERMINAL
    assert action.content == '{"cmd": "pytest"}'
    assert action.observation == '["one", "two"]'
    assert action.tool_call_id == "call-1"


def test_jsonl_isolates_bad_rows_and_honors_empty_filter(tmp_path: Path, caplog) -> None:
    source = tmp_path / "runs.jsonl"
    source.write_text(
        "\n".join([
            json.dumps(_record("one", "resolved", "true")),
            "{not json",
            json.dumps({"instance_id": "missing-outcome"}),
            json.dumps(_record("two", "passed_tests", 0)),
        ]),
        encoding="utf-8",
    )

    records = load_from_jsonl(source)
    assert [(record.instance_id, record.resolved) for record in records] == [
        ("one", True),
        ("two", False),
    ]
    assert "line 2" in caplog.text
    assert "line 3" in caplog.text
    assert load_from_jsonl(source, instance_ids=set()) == []


def test_json_directory_is_sorted_case_insensitive_and_rejects_symlink(tmp_path: Path) -> None:
    source = tmp_path / "runs"
    source.mkdir()
    (source / "b.JSON").write_text(json.dumps(_record("b")), encoding="utf-8")
    (source / "a.json").write_text(json.dumps(_record("a")), encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(_record("outside")), encoding="utf-8")
    (source / "linked.json").symlink_to(outside)

    assert [record.instance_id for record in load_from_json_dir(source)] == ["a", "b"]


def test_single_json_array_filters_after_validation_and_keeps_valid_neighbors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "RUNS.JSON"
    source.write_text(
        json.dumps([_record("one"), 42, {"instance_id": "bad"}, _record("two")]),
        encoding="utf-8",
    )
    records = load_trajectories(str(source), instance_ids={"two"})
    assert [record.instance_id for record in records] == ["two"]


def test_local_path_failures_never_fall_through_to_huggingface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        loader,
        "load_from_huggingface",
        lambda source, **kwargs: calls.append(source) or [],
    )
    unsupported = tmp_path / "runs.txt"
    unsupported.write_text("not a trajectory", encoding="utf-8")

    assert load_trajectories(str(unsupported)) == []
    assert load_trajectories(str(tmp_path / "missing.jsonl")) == []
    assert calls == []


def test_symlinked_local_source_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text(json.dumps(_record("secret")), encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    assert load_trajectories(str(link)) == []


def test_huggingface_normalizes_aliases_and_isolates_malformed_rows(
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    rows = [
        {
            "instance_id": "actions-row",
            "actions": json.dumps([{"type": "terminal", "command": "pytest"}]),
            "final_patch": "patch-a",
            "passed_tests": "yes",
            "agent_name": "published-agent",
            "model_name": "model-a",
        },
        {
            "instance_id": "trajectory-row",
            "trajectory": [],
            "model_patch": "patch-b",
            "resolved": "false",
            "model_name_or_path": "model-b",
        },
        {"instance_id": "bad-json", "trajectory": "[", "resolved": True},
        {
            "instance_id": "contradiction",
            "trajectory": [],
            "resolved": True,
            "passed_tests": False,
        },
    ]
    module = types.ModuleType("datasets")
    module.load_dataset = lambda name, split: rows  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "datasets", module)

    records = load_from_huggingface("org/runs", agent_name="override")
    assert [record.instance_id for record in records] == ["actions-row", "trajectory-row"]
    assert [record.agent_name for record in records] == ["override", "override"]
    assert [record.model_name for record in records] == ["model-a", "model-b"]
    assert [record.resolved for record in records] == [True, False]
    assert records[0].actions[0].action_type is ActionType.TERMINAL
    assert records[0].final_patch == "patch-a"
    assert "bad-json" in caplog.text
    assert "contradiction" in caplog.text


def test_docent_parser_correlates_parallel_anthropic_results_across_transcripts() -> None:
    first = SimpleNamespace(messages=[{
        "role": "assistant",
        "content": [
            {"type": "text", "text": "inspect first"},
            {"type": "tool_use", "id": "call-a", "name": "bash", "input": {"cmd": "a"}},
            {"type": "tool_use", "id": "call-b", "name": "read_file", "input": {"path": "b"}},
        ],
    }])
    second = SimpleNamespace(messages=[{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call-b", "content": "B"},
            {"type": "tool_result", "tool_use_id": "call-a", "content": "A"},
        ],
    }])
    messages = _all_transcript_messages(SimpleNamespace(transcripts=[first, second]))
    actions, _ = _parse_docent_messages(messages)

    assert [action.action_type for action in actions] == [
        ActionType.THINK,
        ActionType.TERMINAL,
        ActionType.READ,
    ]
    assert actions[1].tool_call_id == "call-a"
    assert actions[1].observation == "A"
    assert actions[2].tool_call_id == "call-b"
    assert actions[2].observation == "B"


def test_docent_parser_handles_openai_calls_and_does_not_guess_unknown_result() -> None:
    long_output = "x" * 60_000
    messages = [
        {
            "role": "assistant",
            "content": "run both",
            "tool_calls": [
                {"id": "one", "function": {"name": "shell", "arguments": "one"}},
                {"id": "two", "function": {"name": "shell", "arguments": "two"}},
            ],
        },
        {"role": "tool", "tool_call_id": "two", "content": long_output},
        {"role": "tool", "tool_call_id": "missing", "content": "orphan"},
        {"role": "tool", "tool_call_id": "one", "content": "first"},
        {"role": "user", "content": "a new user instruction"},
    ]
    actions, _ = _parse_docent_messages(messages)

    assert actions[1].tool_call_id == "one"
    assert actions[1].observation == "first"
    assert actions[2].tool_call_id == "two"
    assert actions[2].observation == long_output
    assert actions[3].action_type is ActionType.OTHER
    assert actions[3].tool_call_id == "missing"
    assert actions[3].observation == "orphan"


def test_final_patch_requires_authoritative_or_unambiguous_patch_payload() -> None:
    patch = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b"
    edit = TrajectoryAction(
        action_type=ActionType.EDIT,
        content=json.dumps({"patch": patch}),
        tool_name="apply_patch",
    )
    write = TrajectoryAction(
        action_type=ActionType.WRITE,
        content=json.dumps({"path": "a.py", "content": "not a repository diff"}),
    )

    assert _extract_final_patch(SimpleNamespace(), {}, [edit]) == patch
    assert _extract_final_patch(SimpleNamespace(), {}, [write]) == ""
    assert _extract_final_patch(SimpleNamespace(), {}, [edit, edit]) == ""
    assert _extract_final_patch(
        SimpleNamespace(model_patch="agent patch"),
        {"metadata_final_patch": "row patch"},
        [edit],
    ) == "row patch"


class _FakeFrame:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def iterrows(self):
        return iter(enumerate(self.rows))


class _FakeDocentClient:
    def __init__(self, rows: list[dict[str, Any]], runs: dict[str, Any]):
        self.rows = rows
        self.runs = runs
        self.query = ""

    def execute_dql(self, collection_id: str, query: str) -> object:
        self.query = query
        return object()

    def dql_result_to_df_experimental(self, result: object) -> _FakeFrame:
        return _FakeFrame(self.rows)

    def get_agent_run(self, collection_id: str, run_id: str) -> Any:
        return self.runs[run_id]


def test_docent_loader_uses_all_transcripts_strict_outcomes_and_escaped_filter(
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    patch = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b"
    rows = [
        {
            "agent_run_id": "good",
            "metadata_instance_id": "task-good",
            "metadata_model_name": "agent",
            "metadata_resolved": "true",
            "metadata_turns": "2",
            "metadata_model_patch": patch,
        },
        {
            "agent_run_id": "unknown-outcome",
            "metadata_instance_id": "task-bad",
            "metadata_model_name": "agent",
            "metadata_resolved": None,
            "metadata_turns": "1",
        },
    ]
    runs = {
        "good": SimpleNamespace(transcripts=[
            SimpleNamespace(messages=[{"role": "assistant", "content": "first"}]),
            SimpleNamespace(messages=[{"role": "assistant", "content": "second"}]),
        ]),
        "unknown-outcome": SimpleNamespace(transcripts=[]),
    }
    client = _FakeDocentClient(rows, runs)
    module = types.ModuleType("docent")
    module.Docent = lambda **kwargs: client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docent", module)

    records = load_from_docent(
        "collection",
        "secret",
        model_name="agent'o",
    )
    assert [record.instance_id for record in records] == ["task-good"]
    assert [action.content for action in records[0].actions] == ["first", "second"]
    assert records[0].final_patch == patch
    assert "agent''o" in client.query
    assert "metadata_model_patch" in client.query
    assert "unknown-outcome" in caplog.text
