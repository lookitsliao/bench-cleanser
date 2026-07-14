"""Exact metric checks for identity-aware selective verification evaluation."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from bench_cleanser.verification.metrics import (
    VerificationOutcome,
    aggregate_metrics,
    area_under_risk_coverage,
    calibration_table,
    expected_calibration_error,
    risk_coverage_curve,
    roc_auc,
)
from bench_cleanser.verification.models import RouteAction


def _outcome(
    instance_id: str,
    probability: float,
    truth: bool,
    action: RouteAction,
    *,
    execution_count: int = 0,
    cost: float = 0.0,
) -> VerificationOutcome:
    return VerificationOutcome(
        instance_id=instance_id,
        candidate_id=f"candidate-{instance_id}",
        probability_correct=probability,
        truth_correct=truth,
        action=action,
        policy_id="router",
        policy_version="1",
        run_id="run-1",
        seed=7,
        calibration_id="calibration-1",
        corpus_id="corpus",
        corpus_revision="rev-1",
        acquisition_trajectory_digest=hashlib.sha256(
            instance_id.encode()
        ).hexdigest(),
        execution_count=execution_count,
        cost=cost,
    )


def _outcomes() -> list[VerificationOutcome]:
    return [
        _outcome("i1", 0.9, True, RouteAction.ACCEPT, cost=1.0),
        _outcome("i2", 0.8, False, RouteAction.ACCEPT, execution_count=1, cost=10.0),
        _outcome("i3", 0.2, False, RouteAction.REJECT, execution_count=1, cost=8.0),
        _outcome("i4", 0.1, True, RouteAction.REJECT, cost=2.0),
        _outcome("i5", 0.5, True, RouteAction.ABSTAIN),
    ]


def test_aggregate_metrics_keep_counts_and_denominators_explicit() -> None:
    result = aggregate_metrics(_outcomes(), calibration_bins=5)

    assert result.total == 5
    assert result.truth_correct == 3
    assert result.truth_incorrect == 2
    assert result.covered == 4
    assert result.abstained == 1
    assert result.decision_errors == 2
    assert result.false_accepts == 1
    assert result.false_rejects == 1
    assert result.coverage == pytest.approx(0.8)
    assert result.selective_error_risk == pytest.approx(0.5)
    assert result.false_accept_rate == pytest.approx(0.5)
    assert result.false_reject_rate == pytest.approx(1 / 3)
    assert result.accepted_error_rate == pytest.approx(0.5)
    assert result.rejected_error_rate == pytest.approx(0.5)
    assert result.execution_rate == pytest.approx(0.4)
    assert result.mean_executions == pytest.approx(0.4)
    assert result.mean_cost == pytest.approx(4.2)
    assert result.rate_counts()["false_accept_rate"] == {
        "numerator": 1,
        "denominator": 2,
    }


def test_undefined_rates_are_none_not_zero() -> None:
    only_correct_abstentions = [
        _outcome("a", 0.5, True, RouteAction.ABSTAIN),
        _outcome("b", 0.6, True, RouteAction.ABSTAIN),
    ]
    result = aggregate_metrics(only_correct_abstentions)

    assert result.selective_error_risk is None
    assert result.false_accept_rate is None
    assert result.accepted_error_rate is None
    assert result.rejected_error_rate is None
    assert result.roc_auc is None
    assert result.rate_counts()["selective_error_risk"]["denominator"] == 0


def test_action_conditioned_confidence_uses_the_action_actually_taken() -> None:
    accept = _outcome("accept", 0.2, False, RouteAction.ACCEPT)
    reject = _outcome("reject", 0.2, False, RouteAction.REJECT)
    abstain = _outcome("abstain", 0.99, True, RouteAction.ABSTAIN)

    assert accept.confidence == pytest.approx(0.2)
    assert reject.confidence == pytest.approx(0.8)
    assert abstain.confidence is None


def test_acquisition_trajectory_digest_is_a_strict_join_identity() -> None:
    outcome = _outcome("join", 0.8, True, RouteAction.ACCEPT)

    assert outcome.acquisition_trajectory_key == (
        *outcome.candidate_key,
        outcome.acquisition_trajectory_digest,
    )
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        replace(outcome, acquisition_trajectory_digest="sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        replace(outcome, acquisition_trajectory_digest="A" * 64)


def test_roc_auc_has_tie_handling_and_single_class_is_undefined() -> None:
    tied = [
        _outcome("a", 0.5, True, RouteAction.ACCEPT),
        _outcome("b", 0.5, False, RouteAction.REJECT),
    ]
    assert roc_auc(tied) == pytest.approx(0.5)

    one_class = [
        _outcome("a", 0.9, True, RouteAction.ACCEPT),
        _outcome("b", 0.8, True, RouteAction.ACCEPT),
    ]
    assert roc_auc(one_class) is None


def test_calibration_table_reports_empty_bins_and_reconstructs_ece() -> None:
    outcomes = [
        _outcome("a", 0.0, False, RouteAction.REJECT),
        _outcome("b", 1.0, True, RouteAction.ACCEPT),
    ]
    bins = calibration_table(outcomes, bins=4)

    assert len(bins) == 4
    assert [item.count for item in bins] == [1, 0, 0, 1]
    assert bins[1].mean_probability is None
    assert bins[1].empirical_accuracy is None
    assert expected_calibration_error(outcomes, bins=4) == pytest.approx(0.0)


def test_risk_coverage_reaches_full_coverage_and_penalizes_abstention_explicitly() -> None:
    curve = risk_coverage_curve(_outcomes())

    assert [point.retained for point in curve] == [2, 4, 5]
    assert [point.coverage for point in curve] == pytest.approx([0.4, 0.8, 1.0])
    assert curve[-1].minimum_confidence is None
    assert curve[-1].abstentions_included == 1
    assert curve[-1].decision_errors == 3
    assert curve[-1].decision_error_risk == pytest.approx(0.6)
    assert curve[-1].selective_error_risk == pytest.approx(0.5)
    assert area_under_risk_coverage(curve) == pytest.approx(0.52)


def test_auc_rejects_partial_curve_instead_of_hiding_abstained_tail() -> None:
    curve = risk_coverage_curve(_outcomes())
    with pytest.raises(ValueError, match="full coverage"):
        area_under_risk_coverage(curve[:-1])
    assert area_under_risk_coverage([]) is None


def test_outcomes_reject_non_terminal_or_untyped_actions() -> None:
    with pytest.raises(ValueError, match="terminal"):
        replace(_outcome("a", 0.5, True, RouteAction.ACCEPT), action=RouteAction.RUN_FULL)
    with pytest.raises(ValueError, match="RouteAction"):
        replace(_outcome("b", 0.5, True, RouteAction.ACCEPT), action="accept")
