"""Dependency-free metrics for selective verification experiments.

Every outcome is paired with authoritative truth and immutable experiment
identity.  Metrics never manufacture truth from the router's own decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isclose, isfinite

from bench_cleanser.verification.models import RouteAction


@dataclass(frozen=True)
class VerificationOutcome:
    """One prediction, disposition, cost, label, and experiment identity."""

    instance_id: str
    candidate_id: str
    probability_correct: float
    truth_correct: bool
    action: RouteAction
    policy_id: str
    policy_version: str
    run_id: str
    seed: int
    calibration_id: str
    corpus_id: str
    corpus_revision: str
    acquisition_trajectory_digest: str
    execution_count: int = 0
    cost: float = 0.0
    subgroup: str = "all"

    def __post_init__(self) -> None:
        for name in (
            "instance_id",
            "candidate_id",
            "policy_id",
            "policy_version",
            "run_id",
            "calibration_id",
            "corpus_id",
            "corpus_revision",
            "subgroup",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.probability_correct, bool) or not isinstance(
            self.probability_correct, (int, float)
        ):
            raise ValueError("probability_correct must be numeric")
        if not isfinite(self.probability_correct) or not 0.0 <= self.probability_correct <= 1.0:
            raise ValueError("probability_correct must be between 0 and 1")
        if not isinstance(self.truth_correct, bool):
            raise ValueError("truth_correct must be a boolean")
        if not isinstance(self.action, RouteAction):
            raise ValueError("action must be a RouteAction")
        if self.action not in {
            RouteAction.ACCEPT,
            RouteAction.REJECT,
            RouteAction.ABSTAIN,
        }:
            raise ValueError("outcomes require a terminal accept/reject/abstain action")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not isinstance(self.acquisition_trajectory_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}",
            self.acquisition_trajectory_digest,
        ):
            raise ValueError(
                "acquisition_trajectory_digest must be 64 lowercase hexadecimal characters"
            )
        if isinstance(self.execution_count, bool) or not isinstance(self.execution_count, int):
            raise ValueError("execution_count must be an integer")
        if isinstance(self.cost, bool) or not isinstance(self.cost, (int, float)):
            raise ValueError("cost must be numeric")
        if self.execution_count < 0 or self.cost < 0:
            raise ValueError("execution_count and cost cannot be negative")
        if not isfinite(self.cost):
            raise ValueError("cost must be finite")

    @property
    def covered(self) -> bool:
        return self.action != RouteAction.ABSTAIN

    @property
    def correct_decision(self) -> bool:
        if self.action == RouteAction.ABSTAIN:
            return False
        return (self.action == RouteAction.ACCEPT) == self.truth_correct

    @property
    def confidence(self) -> float | None:
        """Confidence in the action actually taken, not the most likely class.

        Accept confidence is ``P(correct)`` and reject confidence is
        ``P(incorrect)``.  Abstention has no terminal action whose confidence
        could be scored, so it is undefined and enters the risk--coverage
        curve only in the final explicit abstention group.
        """

        if self.action == RouteAction.ACCEPT:
            return float(self.probability_correct)
        if self.action == RouteAction.REJECT:
            return float(1.0 - self.probability_correct)
        return None

    @property
    def candidate_key(self) -> tuple[str, str, str, str]:
        return (
            self.corpus_id,
            self.corpus_revision,
            self.instance_id,
            self.candidate_id,
        )

    @property
    def acquisition_trajectory_key(self) -> tuple[str, ...]:
        """Exact trajectory join without changing candidate-level pairing."""

        return (*self.candidate_key, self.acquisition_trajectory_digest)

    @property
    def evaluation_identity(self) -> tuple[str, str, str, int, str, str, str]:
        return (
            self.policy_id,
            self.policy_version,
            self.run_id,
            self.seed,
            self.calibration_id,
            self.corpus_id,
            self.corpus_revision,
        )

    @property
    def observation_key(self) -> tuple[str, ...]:
        return tuple(str(part) for part in (*self.candidate_key, *self.evaluation_identity))


@dataclass(frozen=True)
class CalibrationBin:
    index: int
    lower_bound: float
    upper_bound: float
    count: int
    positive_count: int
    mean_probability: float | None
    empirical_accuracy: float | None
    absolute_gap: float | None
    weighted_gap: float | None


@dataclass(frozen=True)
class AggregateMetrics:
    total: int
    truth_correct: int
    truth_incorrect: int
    covered: int
    accepted: int
    rejected: int
    abstained: int
    decision_errors: int
    false_accepts: int
    false_rejects: int
    executed: int
    coverage: float
    selective_error_risk: float | None
    false_accept_rate: float | None
    false_reject_rate: float | None
    accepted_error_rate: float | None
    rejected_error_rate: float | None
    execution_rate: float
    mean_executions: float
    mean_cost: float
    brier_score: float
    brier_sum: float
    expected_calibration_error: float
    roc_auc: float | None

    def rate_counts(self) -> dict[str, dict[str, int]]:
        """Return reconstructible numerators and denominators for every rate."""

        return {
            "coverage": {"numerator": self.covered, "denominator": self.total},
            "selective_error_risk": {
                "numerator": self.decision_errors,
                "denominator": self.covered,
            },
            "false_accept_rate": {
                "numerator": self.false_accepts,
                "denominator": self.truth_incorrect,
            },
            "false_reject_rate": {
                "numerator": self.false_rejects,
                "denominator": self.truth_correct,
            },
            "accepted_error_rate": {
                "numerator": self.false_accepts,
                "denominator": self.accepted,
            },
            "rejected_error_rate": {
                "numerator": self.false_rejects,
                "denominator": self.rejected,
            },
            "execution_rate": {"numerator": self.executed, "denominator": self.total},
        }


@dataclass(frozen=True)
class RiskCoveragePoint:
    coverage: float
    retained: int
    terminal_decisions: int
    abstentions_included: int
    decision_errors: int
    terminal_decision_errors: int
    accepted: int
    false_accepts: int
    truth_incorrect: int
    executed: int
    decision_error_risk: float
    selective_error_risk: float | None
    false_accept_rate: float | None
    accepted_error_rate: float | None
    execution_rate: float
    mean_cost: float
    minimum_confidence: float | None


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator / denominator) if denominator else None


def brier_score(outcomes: list[VerificationOutcome]) -> float:
    if not outcomes:
        raise ValueError("at least one outcome is required")
    return sum(
        (item.probability_correct - float(item.truth_correct)) ** 2
        for item in outcomes
    ) / len(outcomes)


def calibration_table(
    outcomes: list[VerificationOutcome],
    *,
    bins: int = 10,
) -> list[CalibrationBin]:
    """Return all fixed-width bins, including auditable empty bins."""

    if not outcomes:
        raise ValueError("at least one outcome is required")
    if isinstance(bins, bool) or not isinstance(bins, int) or bins <= 0:
        raise ValueError("bins must be a positive integer")

    buckets: list[list[VerificationOutcome]] = [[] for _ in range(bins)]
    for item in outcomes:
        index = min(int(item.probability_correct * bins), bins - 1)
        buckets[index].append(item)

    table: list[CalibrationBin] = []
    total = len(outcomes)
    for index, bucket in enumerate(buckets):
        if bucket:
            probability = sum(item.probability_correct for item in bucket) / len(bucket)
            positives = sum(item.truth_correct for item in bucket)
            accuracy = positives / len(bucket)
            gap = abs(probability - accuracy)
            weighted_gap = len(bucket) / total * gap
        else:
            probability = None
            positives = 0
            accuracy = None
            gap = None
            weighted_gap = None
        table.append(CalibrationBin(
            index=index,
            lower_bound=index / bins,
            upper_bound=(index + 1) / bins,
            count=len(bucket),
            positive_count=positives,
            mean_probability=probability,
            empirical_accuracy=accuracy,
            absolute_gap=gap,
            weighted_gap=weighted_gap,
        ))
    return table


def expected_calibration_error(
    outcomes: list[VerificationOutcome],
    *,
    bins: int = 10,
) -> float:
    return sum(item.weighted_gap or 0.0 for item in calibration_table(outcomes, bins=bins))


def roc_auc(outcomes: list[VerificationOutcome]) -> float | None:
    """Compute ROC-AUC using pairwise ranks with correct tie handling."""

    positives = [item for item in outcomes if item.truth_correct]
    negatives = [item for item in outcomes if not item.truth_correct]
    if not positives or not negatives:
        return None

    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive.probability_correct > negative.probability_correct:
                wins += 1.0
            elif positive.probability_correct == negative.probability_correct:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def aggregate_metrics(
    outcomes: list[VerificationOutcome],
    *,
    calibration_bins: int = 10,
) -> AggregateMetrics:
    if not outcomes:
        raise ValueError("at least one outcome is required")

    covered = [item for item in outcomes if item.covered]
    accepted = [item for item in outcomes if item.action == RouteAction.ACCEPT]
    rejected = [item for item in outcomes if item.action == RouteAction.REJECT]
    false_accepts = sum(not item.truth_correct for item in accepted)
    false_rejects = sum(item.truth_correct for item in rejected)
    truth_incorrect = sum(not item.truth_correct for item in outcomes)
    truth_correct = len(outcomes) - truth_incorrect
    decision_errors = sum(not item.correct_decision for item in covered)
    executed = sum(item.execution_count > 0 for item in outcomes)
    squared_errors = sum(
        (item.probability_correct - float(item.truth_correct)) ** 2
        for item in outcomes
    )

    return AggregateMetrics(
        total=len(outcomes),
        truth_correct=truth_correct,
        truth_incorrect=truth_incorrect,
        covered=len(covered),
        accepted=len(accepted),
        rejected=len(rejected),
        abstained=len(outcomes) - len(covered),
        decision_errors=decision_errors,
        false_accepts=false_accepts,
        false_rejects=false_rejects,
        executed=executed,
        coverage=len(covered) / len(outcomes),
        selective_error_risk=_ratio(decision_errors, len(covered)),
        false_accept_rate=_ratio(false_accepts, truth_incorrect),
        false_reject_rate=_ratio(false_rejects, truth_correct),
        accepted_error_rate=_ratio(false_accepts, len(accepted)),
        rejected_error_rate=_ratio(false_rejects, len(rejected)),
        execution_rate=executed / len(outcomes),
        mean_executions=sum(item.execution_count for item in outcomes) / len(outcomes),
        mean_cost=sum(item.cost for item in outcomes) / len(outcomes),
        brier_score=squared_errors / len(outcomes),
        brier_sum=squared_errors,
        expected_calibration_error=expected_calibration_error(
            outcomes, bins=calibration_bins
        ),
        roc_auc=roc_auc(outcomes),
    )


def risk_coverage_curve(
    outcomes: list[VerificationOutcome],
) -> list[RiskCoveragePoint]:
    """Return a full-coverage conservative policy risk curve.

    Terminal decisions are ordered by confidence in the action actually taken.
    Abstentions have no action confidence, enter together after all terminal
    decisions, and count as errors in ``decision_error_risk``.  The point also
    reports terminal-only selective risk, so the abstention penalty is explicit
    rather than hidden in a changed denominator.
    """

    if not outcomes:
        raise ValueError("at least one outcome is required")
    candidates = sorted(
        outcomes,
        key=lambda item: -1.0 if item.confidence is None else item.confidence,
        reverse=True,
    )

    points: list[RiskCoveragePoint] = []
    index = 0
    while index < len(candidates):
        threshold = candidates[index].confidence
        end = index + 1
        while end < len(candidates) and candidates[end].confidence == threshold:
            end += 1
        retained = candidates[:end]
        terminal = [item for item in retained if item.covered]
        abstentions = len(retained) - len(terminal)
        accepted = [item for item in retained if item.action == RouteAction.ACCEPT]
        false_accepts = sum(not item.truth_correct for item in accepted)
        truth_incorrect = sum(not item.truth_correct for item in retained)
        terminal_errors = sum(not item.correct_decision for item in terminal)
        conservative_errors = terminal_errors + abstentions
        executed = sum(item.execution_count > 0 for item in retained)
        points.append(RiskCoveragePoint(
            coverage=len(retained) / len(outcomes),
            retained=len(retained),
            terminal_decisions=len(terminal),
            abstentions_included=abstentions,
            decision_errors=conservative_errors,
            terminal_decision_errors=terminal_errors,
            accepted=len(accepted),
            false_accepts=false_accepts,
            truth_incorrect=truth_incorrect,
            executed=executed,
            decision_error_risk=conservative_errors / len(retained),
            selective_error_risk=_ratio(terminal_errors, len(terminal)),
            false_accept_rate=_ratio(false_accepts, truth_incorrect),
            accepted_error_rate=_ratio(false_accepts, len(accepted)),
            execution_rate=executed / len(retained),
            mean_cost=sum(item.cost for item in retained) / len(retained),
            minimum_confidence=threshold,
        ))
        index = end
    return points


def area_under_risk_coverage(curve: list[RiskCoveragePoint]) -> float | None:
    """Right-continuous step integral of decision risk through full coverage.

    Lower is better.  A partial curve is rejected because silently omitting the
    abstained tail makes policies with more abstention look artificially good.
    """

    if not curve:
        return None
    area = 0.0
    prior_coverage = 0.0
    for point in curve:
        if not isfinite(point.coverage) or not 0.0 < point.coverage <= 1.0:
            raise ValueError("curve coverage must be finite and in (0, 1]")
        if point.coverage <= prior_coverage:
            raise ValueError("curve points must be ordered by increasing coverage")
        width = point.coverage - prior_coverage
        area += width * point.decision_error_risk
        prior_coverage = point.coverage
    if not isclose(prior_coverage, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("risk-coverage curve must extend to full coverage")
    return area
