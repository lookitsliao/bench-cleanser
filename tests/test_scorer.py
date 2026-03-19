"""Unit tests for the scorer module.

Tests validate the v4 binary-label + bucket-severity scorer:
- ContaminationReport building via build_report
- Binary signal detection (has_excess)
- Recommendations generation
"""

import pytest

from bench_cleanser.models import (
    AssertionVerdict,
    AssertionVerdictReport,
    ContaminationReport,
    ExcessPatchDetail,
    ExcessTestDetail,
    HunkVerdict,
    IntentStatement,
    PatchVerdict,
    PipelineConfig,
    ProblemDecomposition,
    Severity,
    TaskContaminationLabel,
    TaskLabelAssignment,
    TestModificationType,
    TestVerdict,
    TestVerdictReport,
    VagueSpecDetail,
)


def _make_intent(instance_id: str, ambiguity: float = 0.1) -> IntentStatement:
    return IntentStatement(
        instance_id=instance_id,
        core_requirement="Fix the reported bug",
        behavioral_contract="Function should work correctly",
        acceptance_criteria=["The function handles edge case X"],
        out_of_scope="Anything not described",
        ambiguity_score=ambiguity,
        raw_llm_response="test",
    )


def _make_excess_patch(
    hunks: list[tuple[PatchVerdict, float]] | None = None,
) -> ExcessPatchDetail:
    if hunks is None:
        hunks = [(PatchVerdict.REQUIRED, 0.9)]
    hunk_verdicts = [
        HunkVerdict(
            hunk_index=i,
            file_path=f"module{i}.py",
            verdict=v,
            confidence=c,
            reasoning="test",
        )
        for i, (v, c) in enumerate(hunks)
    ]
    required = sum(1 for v, _ in hunks if v == PatchVerdict.REQUIRED)
    ancillary = sum(1 for v, _ in hunks if v == PatchVerdict.ANCILLARY)
    unrelated = sum(1 for v, _ in hunks if v == PatchVerdict.UNRELATED)
    return ExcessPatchDetail(
        total_hunks=len(hunks),
        required_count=required,
        ancillary_count=ancillary,
        unrelated_count=unrelated,
        hunk_verdicts=hunk_verdicts,
    )


def _make_excess_test(
    tests: list[tuple[TestVerdict, int, int, bool]] | None = None,
) -> ExcessTestDetail:
    if tests is None:
        tests = [(TestVerdict.ALIGNED, 3, 0, False)]

    test_verdicts: list[TestVerdictReport] = []
    total_on = 0
    total_off = 0
    aligned = 0
    tangential = 0
    unrelated = 0
    has_modified = False

    for i, (verdict, on_topic, off_topic, is_mod) in enumerate(tests):
        assertions = (
            [AssertionVerdictReport(statement=f"assert_{j}", verdict=AssertionVerdict.ON_TOPIC) for j in range(on_topic)]
            + [AssertionVerdictReport(statement=f"assert_off_{j}", verdict=AssertionVerdict.OFF_TOPIC) for j in range(off_topic)]
        )
        test_verdicts.append(TestVerdictReport(
            test_id=f"test_{i}",
            test_name=f"test_{i}",
            intent_match=verdict,
            confidence=0.9,
            reasoning="test",
            is_modified=is_mod,
            assertion_verdicts=assertions,
        ))
        total_on += on_topic
        total_off += off_topic
        if verdict == TestVerdict.ALIGNED:
            aligned += 1
        elif verdict == TestVerdict.TANGENTIAL:
            tangential += 1
        else:
            unrelated += 1
        if is_mod:
            has_modified = True

    return ExcessTestDetail(
        total_tests=len(tests),
        aligned_count=aligned,
        tangential_count=tangential,
        unrelated_count=unrelated,
        total_assertions=total_on + total_off,
        on_topic_assertions=total_on,
        off_topic_assertions=total_off,
        has_modified_tests=has_modified,
        test_verdicts=test_verdicts,
    )


class TestBinarySignals:
    def test_no_unrelated_hunks_no_excess(self):
        ep = _make_excess_patch([
            (PatchVerdict.REQUIRED, 0.9),
            (PatchVerdict.ANCILLARY, 0.8),
        ])
        assert not ep.has_excess

    def test_unrelated_hunks_has_excess(self):
        ep = _make_excess_patch([
            (PatchVerdict.REQUIRED, 0.9),
            (PatchVerdict.UNRELATED, 0.8),
        ])
        assert ep.has_excess

    def test_all_on_topic_no_excess(self):
        et = _make_excess_test([
            (TestVerdict.ALIGNED, 3, 0, False),
        ])
        assert not et.has_excess

    def test_off_topic_assertions_has_excess(self):
        et = _make_excess_test([
            (TestVerdict.ALIGNED, 2, 1, False),
        ])
        assert et.has_excess

    def test_unrelated_test_has_excess(self):
        et = _make_excess_test([
            (TestVerdict.UNRELATED, 0, 0, False),
        ])
        assert et.has_excess


class TestReportSerialization:
    def test_to_dict_roundtrip(self):
        intent = _make_intent("serialize-test", ambiguity=0.5)
        ep = _make_excess_patch([
            (PatchVerdict.REQUIRED, 0.9),
            (PatchVerdict.ANCILLARY, 0.8),
        ])
        et = _make_excess_test([
            (TestVerdict.ALIGNED, 2, 1, True),
        ])
        vs = VagueSpecDetail(score=0.5, reasoning="Moderate ambiguity")

        report = ContaminationReport(
            instance_id="serialize-test",
            severity=Severity.MODERATE,
            intent=intent,
            excess_patch=ep,
            excess_test=et,
            vague_spec=vs,
            task_labels=[
                TaskLabelAssignment(
                    label=TaskContaminationLabel.EXCESS_TESTS,
                    confidence=0.9,
                    evidence=["1 OFF_TOPIC assertion"],
                    reasoning="Test assertions go beyond scope",
                ),
            ],
            recommendations=["EXCESS_TEST: 1 OFF_TOPIC assertions beyond problem scope."],
        )

        d = report.to_dict()
        assert d["instance_id"] == "serialize-test"
        assert d["severity"] in ("CLEAN", "MINOR", "MODERATE", "SEVERE")
        assert "excess_patch" in d
        assert "excess_test" in d
        assert "vague_spec" in d
        assert "task_labels" in d
        assert "recommendations" in d
        assert isinstance(d["excess_patch"]["hunks"], list)
        assert isinstance(d["excess_test"]["tests"], list)
        assert len(d["excess_test"]["tests"][0]["assertions"]) == 3
        assert d["excess_patch"]["has_excess"] is False
        assert d["excess_test"]["has_excess"] is True

        restored = ContaminationReport.from_dict(d)
        assert restored.instance_id == report.instance_id
        assert restored.severity == report.severity
        assert len(restored.task_labels) == 1
        assert restored.task_labels[0].label == TaskContaminationLabel.EXCESS_TESTS
        assert restored.excess_patch.total_hunks == 2
        assert restored.excess_test.off_topic_assertions == 1

    def test_decomposition_roundtrip(self):
        decomp = ProblemDecomposition(
            bug_description="TypeError when calling foo()",
            suggested_fix="Override __str__ on Bar class",
            legitimacy="bug",
            mentioned_files=["django/forms/models.py"],
            mentioned_functions=["modelform_factory", "__str__"],
            mentioned_classes=["ModelForm"],
            mentioned_variables=["formfield_callback"],
            mentioned_modules=["django.forms"],
        )
        intent = IntentStatement(
            instance_id="decomp-test",
            core_requirement="Fix TypeError in foo()",
            behavioral_contract="foo() should return string",
            acceptance_criteria=["foo() returns str"],
            out_of_scope="Nothing else",
            ambiguity_score=0.2,
            decomposition=decomp,
        )
        ep = _make_excess_patch()
        et = _make_excess_test()
        vs = VagueSpecDetail(score=0.2)

        report = ContaminationReport(
            instance_id="decomp-test",
            severity=Severity.CLEAN,
            intent=intent,
            excess_patch=ep,
            excess_test=et,
            vague_spec=vs,
        )

        d = report.to_dict()
        assert "decomposition" in d["intent"]
        assert d["intent"]["decomposition"]["bug_description"] == "TypeError when calling foo()"
        assert d["intent"]["decomposition"]["suggested_fix"] == "Override __str__ on Bar class"
        assert d["intent"]["decomposition"]["legitimacy"] == "bug"
        assert d["intent"]["decomposition"]["mentioned_files"] == ["django/forms/models.py"]
        assert d["intent"]["decomposition"]["mentioned_functions"] == ["modelform_factory", "__str__"]
        assert d["intent"]["decomposition"]["mentioned_classes"] == ["ModelForm"]

        restored = ContaminationReport.from_dict(d)
        assert restored.intent.decomposition is not None
        assert restored.intent.decomposition.bug_description == "TypeError when calling foo()"
        assert restored.intent.decomposition.suggested_fix == "Override __str__ on Bar class"
        assert restored.intent.decomposition.legitimacy == "bug"
        assert restored.intent.decomposition.mentioned_files == ["django/forms/models.py"]
        assert restored.intent.decomposition.mentioned_functions == ["modelform_factory", "__str__"]

    def test_no_decomposition_roundtrip(self):
        intent = _make_intent("no-decomp-test")
        ep = _make_excess_patch()
        et = _make_excess_test()
        vs = VagueSpecDetail(score=0.1)

        report = ContaminationReport(
            instance_id="no-decomp-test",
            severity=Severity.CLEAN,
            intent=intent,
            excess_patch=ep,
            excess_test=et,
            vague_spec=vs,
        )

        d = report.to_dict()
        assert "decomposition" not in d["intent"]

        restored = ContaminationReport.from_dict(d)
        assert restored.intent.decomposition is None


class TestAssertionCounts:
    def test_on_topic_off_topic_counts(self):
        et = _make_excess_test([
            (TestVerdict.ALIGNED, 3, 2, False),
        ])
        tv = et.test_verdicts[0]
        assert tv.on_topic_count == 3
        assert tv.off_topic_count == 2

    def test_zero_off_topic(self):
        et = _make_excess_test([
            (TestVerdict.ALIGNED, 5, 0, False),
        ])
        tv = et.test_verdicts[0]
        assert tv.on_topic_count == 5
        assert tv.off_topic_count == 0
