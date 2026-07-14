"""Regression tests for conservative analytic correctness boundaries."""

from __future__ import annotations

import pytest

from bench_cleanser.analysis.cross_ref import analyze_cross_references
from bench_cleanser.analysis.test_analyzer import analyze_tests
from bench_cleanser.classification.dual_taxonomy import _heuristic_labels
from bench_cleanser.code_visitor import get_post_patch_test_source
from bench_cleanser.fusion import FusionVerdict, fuse
from bench_cleanser.models import (
    AgentTrajectoryLabel,
    CallTarget,
    CodeContext,
    ContaminationReport,
    DescriptionClarity,
    HunkVerdict,
    IntentStatement,
    ParsedTask,
    PatchAnalysis,
    PatchVerdict,
    Severity,
    TaskContaminationLabel,
    TaskLabelAssignment,
    TaskRecord,
    TestAnalysis,
    TestHunk,
    TestModificationType,
    TestVerdict,
    TestVerdictReport,
)
from bench_cleanser.parsing.test_parser import (
    match_f2p_tests_to_hunks,
    parse_test_patch,
)
from bench_cleanser.schemas import (
    BatchTestVerdictItem,
    BatchTestVerdictsResponse,
)
from bench_cleanser.trajectory.analyzer import run_trajectory_analysis
from bench_cleanser.trajectory.classifier import _build_user_prompt
from bench_cleanser.trajectory.models import (
    ActionType,
    LeakagePattern,
    TrajectoryAction,
    TrajectoryAnalysis,
    TrajectoryRecord,
)


def _test_hunk(path: str, name: str) -> TestHunk:
    return TestHunk(
        file_path=path,
        test_name=name,
        full_test_id=f"{path}::{name}",
        modification_type=TestModificationType.NEW,
        added_lines=[f"+def {name}():", "+    assert True"],
        removed_lines=[],
        full_source=f"def {name}():\n    assert True",
        raw_diff="",
    )


def test_f2p_matching_uses_filename_for_duplicate_test_names():
    left = _test_hunk("tests/a/test_common.py", "test_default")
    right = _test_hunk("tests/b/test_common.py", "test_default")

    matched, unmatched = match_f2p_tests_to_hunks(
        ["tests/b/test_common.py::Suite::test_default[param]"],
        [left, right],
    )

    assert matched == [right]
    assert unmatched == []


def test_f2p_name_only_match_abstains_when_filename_is_ambiguous():
    hunks = [
        _test_hunk("tests/a.py", "test_default"),
        _test_hunk("tests/b.py", "test_default"),
    ]
    test_id = "package.tests.Case.test_default"

    matched, unmatched = match_f2p_tests_to_hunks([test_id], hunks)

    assert matched == []
    assert unmatched == [test_id]


def test_modified_test_parser_keeps_context_and_one_function_record():
    patch = """\
diff --git a/tests/test_math.py b/tests/test_math.py
--- a/tests/test_math.py
+++ b/tests/test_math.py
@@ -1,4 +1,4 @@
 def test_total():
     prepare()
-    assert total() == 1
+    assert total() == 2
     cleanup()
"""

    hunks = parse_test_patch(patch)

    assert len(hunks) == 1
    assert hunks[0].modification_type == TestModificationType.MODIFIED
    assert "def test_total():" in hunks[0].full_source
    assert "prepare()" in hunks[0].full_source
    assert "assert total() == 2" in hunks[0].full_source
    assert "cleanup()" in hunks[0].full_source
    assert "assert total() == 1" not in hunks[0].full_source


def test_modified_test_reconstruction_applies_diff_to_complete_function():
    pre = """\
def test_total():
    prepare()
    assert total() == 1
    cleanup()
"""
    raw_diff = """\
@@ -1,4 +1,4 @@ def test_total():
 def test_total():
     prepare()
-    assert total() == 1
+    assert total() == 2
     cleanup()
"""

    post = get_post_patch_test_source(
        pre,
        "test_total",
        ["+    assert total() == 2"],
        ["-    assert total() == 1"],
        raw_diff=raw_diff,
    )

    assert post == pre.replace("== 1", "== 2").rstrip("\n")


def _record(*, test_patch: str = "", before_repo_set_cmd: str = "") -> TaskRecord:
    return TaskRecord(
        instance_id="org/repo-1",
        repo="org/repo",
        base_commit="a" * 40,
        patch="",
        test_patch=test_patch,
        problem_statement="Fix the total.",
        hints_text="",
        fail_to_pass=["tests/test_math.py::test_total"],
        pass_to_pass=[],
        version="",
        before_repo_set_cmd=before_repo_set_cmd,
    )


def _intent() -> IntentStatement:
    return IntentStatement(
        instance_id="org/repo-1",
        core_requirement="Fix the total",
        behavioral_contract="total returns two",
        acceptance_criteria=["total returns two"],
        out_of_scope="",
        ambiguity_score=0.0,
    )


@pytest.mark.asyncio
async def test_unmatched_test_without_source_is_not_auto_aligned():
    record = _record()
    parsed = ParsedTask(
        record=record,
        patch_hunks=[],
        test_hunks=[],
        f2p_test_hunks=[],
        f2p_tests_with_no_hunk=list(record.fail_to_pass),
        files_in_gold_patch=[],
        files_in_test_patch=[],
    )

    analysis = await analyze_tests(parsed, _intent(), object())

    assert analysis.aligned_count == 0
    assert analysis.tangential_count == 1
    assert analysis.test_verdicts[0].intent_match == TestVerdict.TANGENTIAL
    assert "alignment is unknown" in analysis.test_verdicts[0].reasoning


@pytest.mark.asyncio
async def test_missing_assertion_verdict_remains_unscored():
    class _MissingAssertionLLM:
        async def query_structured(self, *args, **kwargs):
            return BatchTestVerdictsResponse(verdicts=[
                BatchTestVerdictItem(
                    test_index=0,
                    test_id="tests/test_math.py::test_total",
                    test_verdict="ALIGNED",
                    evidence_strength="moderate",
                    reasoning="Targets the stated behavior.",
                    is_modification_aligned=True,
                    assertion_verdicts=[],
                )
            ])

    test_hunk = _test_hunk("tests/test_math.py", "test_total")
    parsed = ParsedTask(
        record=_record(),
        patch_hunks=[],
        test_hunks=[test_hunk],
        f2p_test_hunks=[test_hunk],
        f2p_tests_with_no_hunk=[],
        files_in_gold_patch=[],
        files_in_test_patch=["tests/test_math.py"],
    )

    analysis = await analyze_tests(parsed, _intent(), _MissingAssertionLLM())

    assert analysis.total_assertions == 0
    assert analysis.on_topic_assertions == 0
    assert analysis.off_topic_assertions == 0
    assert analysis.test_verdicts[0].assertion_verdicts == []


def test_cross_ref_preserves_non_sequential_hunk_indices():
    test_hunk = _test_hunk("tests/test_math.py", "test_total")
    test_hunk.code_context = CodeContext(
        pre_patch_test_source="",
        post_patch_test_source=test_hunk.full_source,
        test_file_imports="",
        test_file_fixtures="",
        tested_functions=[],
        call_targets=[CallTarget(
            name="total",
            module="pkg.math",
            file_path="pkg/math.py",
            line_number=4,
            is_in_patch=True,
        )],
        assertions=[],
        test_file_path=test_hunk.file_path,
        repo_path="/tmp/repo",
    )
    patch_analysis = PatchAnalysis(
        total_hunks=2,
        required_count=0,
        ancillary_count=0,
        unrelated_count=2,
        hunk_verdicts=[
            HunkVerdict(
                hunk_index=17,
                file_path="pkg/math.py",
                verdict=PatchVerdict.UNRELATED,
            ),
            HunkVerdict(
                hunk_index=42,
                file_path="pkg/other.py",
                verdict=PatchVerdict.UNRELATED,
            ),
        ],
    )
    test_analysis = TestAnalysis(
        total_tests=1,
        aligned_count=1,
        tangential_count=0,
        unrelated_count=0,
        total_assertions=1,
        on_topic_assertions=1,
        off_topic_assertions=0,
        has_modified_tests=False,
        test_verdicts=[TestVerdictReport(
            test_id=test_hunk.full_test_id,
            test_name=test_hunk.test_name,
            intent_match=TestVerdict.ALIGNED,
        )],
    )

    result = analyze_cross_references(
        patch_analysis,
        test_analysis,
        [test_hunk],
    )

    assert len(result.couplings) == 1
    assert result.couplings[0].linked_hunk_indices == [17]


def test_ordinary_new_test_patch_does_not_imply_approach_lock():
    test_analysis = TestAnalysis(
        total_tests=1,
        aligned_count=1,
        tangential_count=0,
        unrelated_count=0,
        total_assertions=1,
        on_topic_assertions=1,
        off_topic_assertions=0,
        has_modified_tests=False,
    )
    candidates = _heuristic_labels(
        _intent(),
        PatchAnalysis(
            total_hunks=1,
            required_count=1,
            ancillary_count=0,
            unrelated_count=0,
        ),
        test_analysis,
        DescriptionClarity(score=0.0, reasoning=""),
        record=_record(test_patch="+def test_total():\n+    assert total() == 2"),
    )

    assert TaskContaminationLabel.APPROACH_LOCK not in {c.label for c in candidates}


def _clean_report() -> ContaminationReport:
    return ContaminationReport(
        instance_id="org/repo-1",
        severity=Severity.CLEAN,
        intent=_intent(),
        patch_analysis=PatchAnalysis(0, 0, 0, 0),
        test_analysis=TestAnalysis(0, 0, 0, 0, 0, 0, 0, False),
        description_clarity=DescriptionClarity(score=0.0, reasoning=""),
        task_labels=[TaskLabelAssignment(label=TaskContaminationLabel.CLEAN)],
    )


def test_failed_rollout_with_passed_genuine_label_cannot_be_fair_pass():
    trajectory = TrajectoryAnalysis(
        instance_id="org/repo-1",
        agent_name="agent",
        leakage_pattern=LeakagePattern.GENUINE_SOLUTION,
        trajectory_label=AgentTrajectoryLabel.AGENT_PASSED_GENUINE,
        resolved=False,
    )

    result = fuse(_clean_report(), trajectory)

    assert result.trajectory_label == AgentTrajectoryLabel.AGENT_UNKNOWN
    assert result.verdict == FusionVerdict.INCONCLUSIVE


def test_llm_trajectory_prompt_includes_tool_observation():
    trajectory = TrajectoryRecord(
        instance_id="org/repo-1",
        agent_name="agent",
        actions=[TrajectoryAction(
            action_type=ActionType.TERMINAL,
            content="pytest tests/test_math.py",
            observation="1 failed: expected 2, got 1",
        )],
        final_patch="",
        resolved=False,
    )

    prompt = _build_user_prompt(
        trajectory,
        gold_patch="",
        problem_statement="Fix total",
        f2p_test_names=[],
        heuristic_signals={},
    )

    assert "OBSERVATION: 1 failed: expected 2, got 1" in prompt


@pytest.mark.asyncio
async def test_trajectory_rehydration_searches_swebench_live(monkeypatch):
    import bench_cleanser.data_loader as data_loader
    import bench_cleanser.deep_dive as deep_dive
    import bench_cleanser.trajectory.analyzer as analyzer

    report = _clean_report()
    live_record = _record()
    calls: list[str] = []

    monkeypatch.setattr(deep_dive, "load_reports_from_dir", lambda *a, **k: [report])
    monkeypatch.setattr(
        data_loader,
        "load_swebench_pro",
        lambda max_tasks: calls.append("pro") or [],
    )
    monkeypatch.setattr(
        data_loader,
        "load_swebench_verified",
        lambda max_tasks: calls.append("verified") or [],
    )
    monkeypatch.setattr(
        data_loader,
        "load_swebench_live",
        lambda max_tasks: calls.append("live") or [live_record],
    )
    monkeypatch.setattr(analyzer, "load_trajectories", lambda *a, **k: [])

    result = await run_trajectory_analysis(
        reports_dir="unused",
        trajectory_source="unused.jsonl",
    )

    assert calls == ["pro", "verified", "live"]
    assert result == "No trajectories found for the target instances."
