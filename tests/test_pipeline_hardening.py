"""Focused security, resume-provenance, and failure-semantics tests."""

from __future__ import annotations

import json
import pathlib

import pytest

import bench_cleanser.pipeline as pipeline
from bench_cleanser.analysis.structural_diff import _find_test_source_in_repo
from bench_cleanser.cli import _pipeline_exit_code
from bench_cleanser.code_visitor import (
    extract_problem_code_context,
    get_full_test_source,
)
from bench_cleanser.models import (
    ContaminationReport,
    DescriptionClarity,
    IntentStatement,
    PatchAnalysis,
    PipelineConfig,
    Severity,
    TaskRecord,
    TestAnalysis,
)
from bench_cleanser.pipeline import (
    PipelineRunReports,
    _load_resumable_report,
    _report_payload,
    _safe_report_path,
    _write_summary,
    parse_task,
    run_pipeline,
    validate_instance_id,
)
from bench_cleanser.repo_manager import (
    RepoManager,
    resolve_confined_repo_file,
    validate_full_commit_hash,
    validate_relative_file_path,
    validate_repo_identifier,
)
from bench_cleanser.static_analysis import resolve_imports


def _record(**overrides: object) -> TaskRecord:
    values = {
        "instance_id": "owner__repo-1",
        "repo": "owner/repo",
        "base_commit": "a" * 40,
        "patch": "",
        "test_patch": "",
        "problem_statement": "Fix the bug.",
        "hints_text": "",
        "fail_to_pass": [],
        "pass_to_pass": [],
        "version": "1",
    }
    values.update(overrides)
    return TaskRecord(**values)


def _report(instance_id: str = "owner__repo-1", error: str | None = None) -> ContaminationReport:
    return ContaminationReport(
        instance_id=instance_id,
        severity=Severity.CLEAN,
        intent=IntentStatement(
            instance_id=instance_id,
            core_requirement="fix",
            behavioral_contract="works",
            acceptance_criteria=[],
            out_of_scope="",
            ambiguity_score=0.0,
        ),
        patch_analysis=PatchAnalysis(
            total_hunks=0,
            required_count=0,
            ancillary_count=0,
            unrelated_count=0,
        ),
        test_analysis=TestAnalysis(
            total_tests=0,
            aligned_count=0,
            tangential_count=0,
            unrelated_count=0,
            total_assertions=0,
            on_topic_assertions=0,
            off_topic_assertions=0,
            has_modified_tests=False,
        ),
        description_clarity=DescriptionClarity(score=0.0, reasoning="clear"),
        pipeline_error=error,
    )


@pytest.mark.parametrize(
    "repo",
    ["../victim/repo", "owner/../../victim", "https://example.test/repo", "owner"],
)
def test_repo_identifier_rejects_untrusted_shapes(repo: str) -> None:
    with pytest.raises(ValueError):
        validate_repo_identifier(repo)


def test_repo_identifier_and_full_commit_accept_expected_values() -> None:
    assert validate_repo_identifier("owner.name/repo-name_1") == "owner.name/repo-name_1"
    assert validate_full_commit_hash("A" * 40) == "a" * 40


@pytest.mark.parametrize("commit", ["abc123", "g" * 40, "a" * 39, "a" * 41, "../" + "a" * 40])
def test_full_commit_hash_is_required(commit: str) -> None:
    with pytest.raises(ValueError):
        validate_full_commit_hash(commit)


@pytest.mark.parametrize(
    "file_path",
    ["../secret", "tests/../../secret", "/etc/passwd", "C:\\secret", "a//b", "a/./b"],
)
def test_relative_file_path_rejects_escape_forms(file_path: str) -> None:
    with pytest.raises(ValueError):
        validate_relative_file_path(file_path)


def test_repo_manager_get_file_is_confined_to_checkout(tmp_path: pathlib.Path) -> None:
    manager = RepoManager(cache_dir=str(tmp_path / "cache"))
    repo_path = tmp_path / "cache" / "owner__repo" / ("a" * 12)
    repo_path.mkdir(parents=True)
    (repo_path / "safe.txt").write_text("safe", encoding="utf-8")

    assert manager.get_file(repo_path, "safe.txt") == "safe"
    with pytest.raises(ValueError):
        manager.get_file(repo_path, "../outside.txt")
    with pytest.raises(ValueError):
        manager.get_file(tmp_path, "outside.txt")

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (repo_path / "link.txt").symlink_to(outside)
    with pytest.raises(ValueError):
        manager.get_file(repo_path, "link.txt")


def test_all_source_readers_reject_checkout_symlink_escape(
    tmp_path: pathlib.Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text(
        "def test_secret():\n    return 'do-not-expose'\n",
        encoding="utf-8",
    )
    (repo_path / "escaped.py").symlink_to(outside)

    with pytest.raises(ValueError, match="escapes checkout"):
        resolve_confined_repo_file(repo_path, "escaped.py")

    assert get_full_test_source(repo_path, "escaped.py", "test_secret") == ""
    assert _find_test_source_in_repo("escaped.py::test_secret", repo_path) == ""
    assert resolve_imports("import escaped", repo_path) == {}

    context = extract_problem_code_context(
        repo_path,
        ["escaped.py"],
        ["test_secret"],
        [],
    )
    assert context.mentioned_file_contents == {}
    assert context.mentioned_entity_sources == {}


def test_repo_manager_rejects_bad_metadata_before_clone(tmp_path: pathlib.Path) -> None:
    manager = RepoManager(cache_dir=str(tmp_path / "cache"))
    with pytest.raises(ValueError):
        manager.get_repo_path("../../victim/repo", "a" * 40)
    with pytest.raises(ValueError):
        manager.get_repo_path("owner/repo", "a" * 12)
    assert list((tmp_path / "cache").iterdir()) == []


@pytest.mark.parametrize(
    "patch",
    [
        "diff --git a/good.py b/../../secret\n--- a/good.py\n+++ b/../../secret\n",
        "--- /etc/passwd\n+++ b/good.py\n",
        "--- a/good.py\n+++ C:\\secret\n",
    ],
)
def test_parse_task_rejects_unsafe_patch_paths(patch: str) -> None:
    with pytest.raises(ValueError, match="Unsafe path"):
        parse_task(_record(patch=patch))


@pytest.mark.parametrize("instance_id", ["../escape", "a/b", "/absolute", "", "a\\b"])
def test_instance_id_cannot_control_report_path(
    tmp_path: pathlib.Path,
    instance_id: str,
) -> None:
    with pytest.raises(ValueError):
        validate_instance_id(instance_id)
    with pytest.raises(ValueError):
        _safe_report_path(tmp_path, instance_id)


def test_resume_requires_complete_matching_success_report(tmp_path: pathlib.Path) -> None:
    record = _record()
    config = PipelineConfig(llm_api_key="first-key")
    path = tmp_path / "report.json"
    payload = _report_payload(_report(), record, config)
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert _load_resumable_report(path, record, config) is not None

    # Credentials are not analytical provenance and may rotate safely.
    rotated_key = PipelineConfig(llm_api_key="second-key")
    assert _load_resumable_report(path, record, rotated_key) is not None

    stale_config = PipelineConfig(llm_api_key="first-key", llm_model="different-model")
    assert _load_resumable_report(path, record, stale_config) is None
    assert _load_resumable_report(path, _record(problem_statement="changed"), config) is None

    payload["pipeline_error"] = "RuntimeError: failed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _load_resumable_report(path, record, config) is None

    payload.pop("pipeline_error")
    payload.pop("test_analysis")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _load_resumable_report(path, record, config) is None

    path.write_text("{not-json", encoding="utf-8")
    assert _load_resumable_report(path, record, config) is None


async def test_code_visitation_disabled_avoids_repo_manager(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForbiddenRepoManager:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("RepoManager must not be constructed")

    async def fake_process(*args: object, **kwargs: object) -> ContaminationReport:
        return _report()

    monkeypatch.setattr(pipeline, "RepoManager", ForbiddenRepoManager)
    monkeypatch.setattr(pipeline, "process_single_task", fake_process)
    config = PipelineConfig(
        llm_api_key="test-key",
        output_dir=str(tmp_path / "output"),
        cache_dir=str(tmp_path / "llm-cache"),
        code_visitation_enabled=False,
    )

    reports = await run_pipeline([_record()], config, resume=False)

    assert len(reports) == 1
    assert reports.new_success_count == 1
    saved = json.loads(
        (tmp_path / "output" / "reports" / "owner__repo-1.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["_provenance"]["version"] == 1


def test_exit_code_fails_when_every_new_attempt_failed() -> None:
    failed = PipelineRunReports(
        [_report(error="boom")],
        attempted_count=1,
        resumed_count=0,
        new_success_count=0,
        new_failure_count=1,
    )
    assert _pipeline_exit_code(failed) == 1

    resumed_plus_failed = PipelineRunReports(
        [_report(), _report("owner__repo-2", error="boom")],
        attempted_count=1,
        resumed_count=1,
        new_success_count=0,
        new_failure_count=1,
    )
    assert _pipeline_exit_code(resumed_plus_failed) == 1

    partial = PipelineRunReports(
        [_report(), _report("owner__repo-2", error="boom")],
        attempted_count=2,
        resumed_count=0,
        new_success_count=1,
        new_failure_count=1,
    )
    assert _pipeline_exit_code(partial) == 0


def test_summary_exposes_failure_details(tmp_path: pathlib.Path) -> None:
    _write_summary(
        [_report(), _report("owner__repo-2", error="RuntimeError: boom")],
        tmp_path,
        run_stats={
            "attempted_tasks": 2,
            "resumed_tasks": 0,
            "new_successes": 1,
            "new_failures": 1,
        },
    )
    stats = json.loads((tmp_path / "summary_stats.json").read_text(encoding="utf-8"))
    assert stats["pipeline_errors"] == 1
    assert stats["failed_tasks"] == [
        {"instance_id": "owner__repo-2", "error": "RuntimeError: boom"}
    ]
    assert stats["run"]["new_failures"] == 1
