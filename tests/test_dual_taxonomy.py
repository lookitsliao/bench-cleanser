"""Tests for bench_cleanser.classification.dual_taxonomy severity computation."""

from bench_cleanser.classification.dual_taxonomy import compute_task_severity
from bench_cleanser.models import Severity, TaskContaminationLabel, TaskLabelAssignment


def _label(name: str) -> TaskLabelAssignment:
    """Helper to build a TaskLabelAssignment."""
    return TaskLabelAssignment(
        label=TaskContaminationLabel(name),
        evidence=["test evidence"],
        reasoning="test reasoning",
    )


# ── CLEAN ─────────────────────────────────────────────────────────────


def test_clean_no_labels():
    assert compute_task_severity([]) == Severity.CLEAN


def test_clean_explicit():
    assert compute_task_severity([_label("clean")]) == Severity.CLEAN


# ── SEVERE ────────────────────────────────────────────────────────────


def test_severe_approach_lock():
    labels = [_label("approach_lock")]
    assert compute_task_severity(labels) == Severity.SEVERE


def test_severe_compound_overtest_overpatch():
    labels = [_label("over_test"), _label("over_patch")]
    assert compute_task_severity(labels) == Severity.SEVERE


def test_severe_over_test_alone():
    # Over_test without over_patch is rare and demands maximum attention:
    # either over_patch detection missed something, or the tests silently
    # widened expectations beyond the problem scope.  Both are SEVERE.
    labels = [_label("over_test")]
    assert compute_task_severity(labels) == Severity.SEVERE


def test_severe_approach_lock_with_others():
    labels = [_label("approach_lock"), _label("weak_coverage"), _label("over_patch")]
    assert compute_task_severity(labels) == Severity.SEVERE


# ── MODERATE ──────────────────────────────────────────────────────────


def test_moderate_over_patch_plus_hidden_context():
    labels = [_label("over_patch"), _label("hidden_context")]
    assert compute_task_severity(labels) == Severity.MODERATE


def test_moderate_over_patch_plus_unclear():
    labels = [_label("over_patch"), _label("unclear_description")]
    assert compute_task_severity(labels) == Severity.MODERATE


# ── MINOR ─────────────────────────────────────────────────────────────


def test_minor_over_patch_alone():
    labels = [_label("over_patch")]
    assert compute_task_severity(labels) == Severity.MINOR


def test_minor_unclear_description():
    labels = [_label("unclear_description")]
    assert compute_task_severity(labels) == Severity.MINOR


def test_minor_hidden_context():
    labels = [_label("hidden_context")]
    assert compute_task_severity(labels) == Severity.MINOR


def test_minor_weak_coverage():
    labels = [_label("weak_coverage")]
    assert compute_task_severity(labels) == Severity.MINOR
