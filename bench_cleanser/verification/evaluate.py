"""CLI and strict JSONL helpers for paired verification-policy evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, TextIO

from bench_cleanser import __version__
from bench_cleanser.verification._io import atomic_write, strict_json_dumps
from bench_cleanser.verification.corpus import (
    CandidateCorrectness,
    EvidenceValidity,
    TaskValidity,
    VerificationGapRecord,
    corpus_digest,
    load_corpus,
    validate_corpus,
)
from bench_cleanser.verification.metrics import (
    VerificationOutcome,
    aggregate_metrics,
    area_under_risk_coverage,
    calibration_table,
    risk_coverage_curve,
)
from bench_cleanser.verification.models import RouteAction

EVALUATION_SCHEMA_VERSION = "0.4.0"


@dataclass(frozen=True)
class EvaluationOutcome:
    """One policy disposition whose truth must be joined from corpus 0.5.0."""

    instance_id: str
    candidate_id: str
    probability_task_valid: float
    probability_correct_given_valid_task: float
    action: RouteAction
    policy_id: str
    policy_version: str
    run_id: str
    seed: int
    calibration_id: str
    corpus_id: str
    corpus_revision: str
    corpus_digest: str
    corpus_record_sha256: str
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
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a trimmed non-empty string")
        for name in (
            "probability_task_valid",
            "probability_correct_given_valid_task",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be finite and between 0 and 1")
            object.__setattr__(self, name, float(value))
        if not isinstance(self.action, RouteAction) or self.action not in {
            RouteAction.ACCEPT,
            RouteAction.REJECT,
            RouteAction.ABSTAIN,
        }:
            raise ValueError("action must be a terminal accept/reject/abstain action")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        for name in (
            "corpus_digest",
            "corpus_record_sha256",
            "acquisition_trajectory_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(
                    f"{name} must be 64 lowercase hexadecimal characters"
                )
        if (
            isinstance(self.execution_count, bool)
            or not isinstance(self.execution_count, int)
            or self.execution_count < 0
        ):
            raise ValueError("execution_count must be a non-negative integer")
        if (
            isinstance(self.cost, bool)
            or not isinstance(self.cost, (int, float))
            or not isfinite(self.cost)
            or self.cost < 0
        ):
            raise ValueError("cost must be finite and non-negative")
        object.__setattr__(self, "cost", float(self.cost))

    @property
    def candidate_key(self) -> tuple[str, str, str, str]:
        return (
            self.corpus_id,
            self.corpus_revision,
            self.instance_id,
            self.candidate_id,
        )

    @property
    def evaluation_identity(self) -> tuple[str, str, str, int, str, str, str, str]:
        return (
            self.policy_id,
            self.policy_version,
            self.run_id,
            self.seed,
            self.calibration_id,
            self.corpus_id,
            self.corpus_revision,
            self.corpus_digest,
        )

    @property
    def observation_key(self) -> tuple[str, ...]:
        return tuple(str(part) for part in (*self.candidate_key, *self.evaluation_identity))


@dataclass(frozen=True)
class JoinedOutcome:
    outcome: EvaluationOutcome
    record: VerificationGapRecord


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r} is not allowed")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _strict_outcome_json_loads(value: str) -> Any:
    return json.loads(
        value,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )


def _require_string(value: Any, field: str, line_number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"line {line_number}: {field} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"line {line_number}: {field} cannot have surrounding whitespace")
    return value


def _require_number(value: Any, field: str, line_number: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"line {line_number}: {field} must be a JSON number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"line {line_number}: {field} must be finite")
    return result


def _require_integer(value: Any, field: str, line_number: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"line {line_number}: {field} must be a JSON integer")
    return value


def _require_sha256_digest(value: Any, field: str, line_number: int) -> str:
    digest = _require_string(value, field, line_number)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(
            f"line {line_number}: {field} must be 64 lowercase hexadecimal characters"
        )
    return digest


def parse_outcome(data: dict[str, Any], *, line_number: int = 1) -> EvaluationOutcome:
    """Validate one no-coercion JSON object from a paired outcome file."""

    if not isinstance(data, dict):
        raise ValueError(f"line {line_number}: each outcome must be a JSON object")
    legacy_truth_fields = sorted(
        {"truth_correct", "probability_correct", "task_valid"}.intersection(data)
    )
    if legacy_truth_fields:
        raise ValueError(
            f"line {line_number}: legacy evaluation truth fields {legacy_truth_fields} "
            "are unsupported in evaluation schema 0.4.0; truth must come from an "
            "exact corpus 0.5.0 digest join"
        )
    allowed = {
        "instance_id",
        "candidate_id",
        "probability_task_valid",
        "probability_correct_given_valid_task",
        "action",
        "policy_id",
        "policy_version",
        "run_id",
        "seed",
        "calibration_id",
        "corpus_id",
        "corpus_revision",
        "corpus_digest",
        "corpus_record_sha256",
        "acquisition_trajectory_digest",
        "execution_count",
        "cost",
        "subgroup",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"line {line_number}: unknown fields: {unknown}")
    try:
        action = RouteAction(_require_string(data["action"], "action", line_number))
        return EvaluationOutcome(
            instance_id=_require_string(data["instance_id"], "instance_id", line_number),
            candidate_id=_require_string(data["candidate_id"], "candidate_id", line_number),
            probability_task_valid=_require_number(
                data["probability_task_valid"],
                "probability_task_valid",
                line_number,
            ),
            probability_correct_given_valid_task=_require_number(
                data["probability_correct_given_valid_task"],
                "probability_correct_given_valid_task",
                line_number,
            ),
            action=action,
            policy_id=_require_string(data["policy_id"], "policy_id", line_number),
            policy_version=_require_string(
                data["policy_version"], "policy_version", line_number
            ),
            run_id=_require_string(data["run_id"], "run_id", line_number),
            seed=_require_integer(data["seed"], "seed", line_number),
            calibration_id=_require_string(
                data["calibration_id"], "calibration_id", line_number
            ),
            corpus_id=_require_string(data["corpus_id"], "corpus_id", line_number),
            corpus_revision=_require_string(
                data["corpus_revision"], "corpus_revision", line_number
            ),
            corpus_digest=_require_sha256_digest(
                data["corpus_digest"], "corpus_digest", line_number
            ),
            corpus_record_sha256=_require_sha256_digest(
                data["corpus_record_sha256"],
                "corpus_record_sha256",
                line_number,
            ),
            acquisition_trajectory_digest=_require_sha256_digest(
                data["acquisition_trajectory_digest"],
                "acquisition_trajectory_digest",
                line_number,
            ),
            execution_count=_require_integer(
                data.get("execution_count", 0), "execution_count", line_number
            ),
            cost=_require_number(data.get("cost", 0.0), "cost", line_number),
            subgroup=_require_string(data.get("subgroup", "all"), "subgroup", line_number),
        )
    except KeyError as exc:
        raise ValueError(f"line {line_number}: missing required field {exc.args[0]!r}") from exc
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(f"line {line_number}:"):
            raise
        raise ValueError(f"line {line_number}: invalid outcome: {exc}") from exc


def load_outcomes(stream: TextIO) -> list[EvaluationOutcome]:
    """Load strict JSONL while preserving legitimate paired comparisons."""

    outcomes: list[EvaluationOutcome] = []
    seen_observations: set[tuple[str, ...]] = set()
    candidate_declarations: dict[
        tuple[str, str, str, str], tuple[str, str, str, str]
    ] = {}
    run_configuration: dict[
        tuple[str, str, str, str, str], tuple[int, str]
    ] = {}
    for line_number, raw_line in enumerate(stream, 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = _strict_outcome_json_loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
                raise ValueError(f"line {line_number}: invalid JSON: {exc}") from exc
            raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"line {line_number}: each outcome must be a JSON object")
        outcome = parse_outcome(data, line_number=line_number)

        if outcome.observation_key in seen_observations:
            raise ValueError(
                f"line {line_number}: duplicate observation identity "
                f"{outcome.observation_key!r}"
            )
        seen_observations.add(outcome.observation_key)

        declaration = (
            outcome.corpus_digest,
            outcome.corpus_record_sha256,
            outcome.acquisition_trajectory_digest,
            outcome.subgroup,
        )
        prior_declaration = candidate_declarations.setdefault(
            outcome.candidate_key,
            declaration,
        )
        if prior_declaration != declaration:
            raise ValueError(
                f"line {line_number}: paired candidate {outcome.candidate_key!r} "
                "has inconsistent corpus join, acquisition trajectory, or subgroup"
            )

        run_key = (
            outcome.corpus_id,
            outcome.corpus_revision,
            outcome.policy_id,
            outcome.policy_version,
            outcome.run_id,
        )
        prior_configuration = run_configuration.setdefault(
            run_key,
            (outcome.seed, outcome.calibration_id),
        )
        if prior_configuration != (outcome.seed, outcome.calibration_id):
            raise ValueError(
                f"line {line_number}: run {run_key!r} changes seed or calibration_id"
            )
        outcomes.append(outcome)
    if not outcomes:
        raise ValueError("outcome file contains no records")
    return outcomes


def _identity_dict(
    identity: tuple[str, str, str, int, str, str, str, str],
) -> dict[str, Any]:
    (
        policy_id,
        policy_version,
        run_id,
        seed,
        calibration_id,
        corpus_id,
        corpus_revision,
        joined_corpus_digest,
    ) = identity
    return {
        "policy_id": policy_id,
        "policy_version": policy_version,
        "run_id": run_id,
        "seed": seed,
        "calibration_id": calibration_id,
        "corpus_id": corpus_id,
        "corpus_revision": corpus_revision,
        "corpus_digest": joined_corpus_digest,
    }


def _canonical_outcome(outcome: EvaluationOutcome) -> dict[str, Any]:
    data = asdict(outcome)
    data["action"] = outcome.action.value
    return data


def _trajectory_identity_dict(outcome: EvaluationOutcome) -> dict[str, Any]:
    return {
        "corpus_id": outcome.corpus_id,
        "corpus_revision": outcome.corpus_revision,
        "corpus_digest": outcome.corpus_digest,
        "corpus_record_sha256": outcome.corpus_record_sha256,
        "instance_id": outcome.instance_id,
        "candidate_id": outcome.candidate_id,
        "policy_id": outcome.policy_id,
        "policy_version": outcome.policy_version,
        "run_id": outcome.run_id,
        "seed": outcome.seed,
        "calibration_id": outcome.calibration_id,
        "acquisition_trajectory_digest": outcome.acquisition_trajectory_digest,
    }


def _outcome_set_digest(outcomes: list[EvaluationOutcome]) -> str:
    rows = sorted(
        (_canonical_outcome(outcome) for outcome in outcomes),
        key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")),
    )
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _validate_outcome_set(outcomes: list[EvaluationOutcome]) -> None:
    """Protect direct API callers from duplicate or contradictory pooling."""

    seen: set[tuple[str, ...]] = set()
    declarations: dict[
        tuple[str, str, str, str], tuple[str, str, str, str]
    ] = {}
    runs: dict[tuple[str, str, str, str, str], tuple[int, str]] = {}
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, EvaluationOutcome):
            raise ValueError(f"outcomes[{index}] must be an EvaluationOutcome")
        if outcome.observation_key in seen:
            raise ValueError(f"duplicate observation identity {outcome.observation_key!r}")
        seen.add(outcome.observation_key)
        declaration = (
            outcome.corpus_digest,
            outcome.corpus_record_sha256,
            outcome.acquisition_trajectory_digest,
            outcome.subgroup,
        )
        prior_declaration = declarations.setdefault(
            outcome.candidate_key,
            declaration,
        )
        if prior_declaration != declaration:
            raise ValueError(
                f"paired candidate {outcome.candidate_key!r} has inconsistent corpus "
                "join, acquisition trajectory, or subgroup"
            )
        run_key = (
            outcome.corpus_id,
            outcome.corpus_revision,
            outcome.policy_id,
            outcome.policy_version,
            outcome.run_id,
        )
        prior_run = runs.setdefault(run_key, (outcome.seed, outcome.calibration_id))
        if prior_run != (outcome.seed, outcome.calibration_id):
            raise ValueError(f"run {run_key!r} changes seed or calibration_id")


def _metric_report(
    outcomes: list[VerificationOutcome],
    *,
    calibration_bins: int,
) -> dict[str, Any]:
    metrics = aggregate_metrics(outcomes, calibration_bins=calibration_bins)
    report = asdict(metrics)
    report["rate_counts"] = metrics.rate_counts()
    report["score_counts"] = {
        "brier_score": {"sum": metrics.brier_sum, "denominator": metrics.total},
        "expected_calibration_error": {
            "samples": metrics.total,
            "bins": calibration_bins,
        },
        "roc_auc": {
            "positives": metrics.truth_correct,
            "negatives": metrics.truth_incorrect,
        },
    }
    return report


def _binary_roc_auc(rows: list[tuple[float, bool]]) -> float | None:
    positives = [probability for probability, truth in rows if truth]
    negatives = [probability for probability, truth in rows if not truth]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _binary_calibration_report(
    rows: list[tuple[float, bool]],
    *,
    calibration_bins: int,
) -> dict[str, Any]:
    buckets: list[list[tuple[float, bool]]] = [
        [] for _ in range(calibration_bins)
    ]
    for probability, truth in rows:
        index = min(int(probability * calibration_bins), calibration_bins - 1)
        buckets[index].append((probability, truth))

    rendered_bins: list[dict[str, Any]] = []
    ece = 0.0
    for index, bucket in enumerate(buckets):
        if bucket:
            mean_probability = sum(item[0] for item in bucket) / len(bucket)
            positive_count = sum(item[1] for item in bucket)
            empirical_frequency = positive_count / len(bucket)
            absolute_gap = abs(mean_probability - empirical_frequency)
            weighted_gap = len(bucket) / len(rows) * absolute_gap
            ece += weighted_gap
        else:
            mean_probability = None
            positive_count = 0
            empirical_frequency = None
            absolute_gap = None
            weighted_gap = None
        rendered_bins.append({
            "index": index,
            "lower_bound": index / calibration_bins,
            "upper_bound": (index + 1) / calibration_bins,
            "count": len(bucket),
            "positive_count": positive_count,
            "mean_probability": mean_probability,
            "empirical_frequency": empirical_frequency,
            "absolute_gap": absolute_gap,
            "weighted_gap": weighted_gap,
        })

    brier_sum = sum((probability - float(truth)) ** 2 for probability, truth in rows)
    positives = sum(truth for _, truth in rows)
    return {
        "scored_count": len(rows),
        "positive_count": positives,
        "negative_count": len(rows) - positives,
        "brier_score": brier_sum / len(rows) if rows else None,
        "brier_sum": brier_sum,
        "expected_calibration_error": ece if rows else None,
        "roc_auc": _binary_roc_auc(rows),
        "calibration": {
            "method": "fixed_width_probability_bins",
            "bin_count": calibration_bins,
            "bins": rendered_bins,
        },
    }


def _join_outcomes_to_corpus(
    outcomes: list[EvaluationOutcome],
    corpus_records: list[VerificationGapRecord],
) -> list[JoinedOutcome]:
    validate_corpus(corpus_records, require_paired=True)
    exact_corpus_digest = corpus_digest(corpus_records)
    corpus_identities = {
        (outcome.corpus_id, outcome.corpus_revision) for outcome in outcomes
    }
    if len(corpus_identities) != 1:
        raise ValueError(
            "one evaluation invocation must target one corpus_id/corpus_revision"
        )
    index = {record.key: record for record in corpus_records}
    joined: list[JoinedOutcome] = []
    for outcome in outcomes:
        if outcome.corpus_digest != exact_corpus_digest:
            raise ValueError(
                f"outcome {outcome.candidate_key!r} corpus_digest does not match "
                "the supplied corpus"
            )
        key = (outcome.instance_id, outcome.candidate_id)
        record = index.get(key)
        if record is None:
            raise ValueError(
                f"outcome {outcome.candidate_key!r} has no exact corpus record"
            )
        if outcome.corpus_record_sha256 != record.canonical_digest():
            raise ValueError(
                f"outcome {outcome.candidate_key!r} corpus_record_sha256 does not "
                "match the supplied corpus record"
            )
        if (
            outcome.acquisition_trajectory_digest
            != record.acquisition_trajectory_digest()
        ):
            raise ValueError(
                f"outcome {outcome.candidate_key!r} acquisition trajectory does not "
                "match the supplied corpus record"
            )
        joined.append(JoinedOutcome(outcome=outcome, record=record))
    return joined


def _candidate_metric_outcome(item: JoinedOutcome) -> VerificationOutcome | None:
    if item.record.task_adjudication.task_validity != TaskValidity.VALID:
        return None
    correctness = item.record.candidate_adjudication.candidate_correctness
    if correctness not in {
        CandidateCorrectness.CORRECT,
        CandidateCorrectness.INCORRECT,
    }:
        return None
    outcome = item.outcome
    return VerificationOutcome(
        instance_id=outcome.instance_id,
        candidate_id=outcome.candidate_id,
        probability_correct=outcome.probability_correct_given_valid_task,
        truth_correct=correctness == CandidateCorrectness.CORRECT,
        action=outcome.action,
        policy_id=outcome.policy_id,
        policy_version=outcome.policy_version,
        run_id=outcome.run_id,
        seed=outcome.seed,
        calibration_id=outcome.calibration_id,
        corpus_id=outcome.corpus_id,
        corpus_revision=outcome.corpus_revision,
        acquisition_trajectory_digest=outcome.acquisition_trajectory_digest,
        execution_count=outcome.execution_count,
        cost=outcome.cost,
        subgroup=outcome.subgroup,
    )


def _truth_state(item: JoinedOutcome) -> str:
    validity = item.record.task_adjudication.task_validity
    if validity == TaskValidity.INVALID:
        return "invalid_task"
    if validity == TaskValidity.INDETERMINATE:
        return "indeterminate_task"
    correctness = item.record.candidate_adjudication.candidate_correctness
    if correctness == CandidateCorrectness.CORRECT:
        return "valid_correct"
    if correctness == CandidateCorrectness.INCORRECT:
        return "valid_incorrect"
    if correctness == CandidateCorrectness.INDETERMINATE:
        return "valid_candidate_indeterminate"
    raise ValueError("valid task cannot have not_applicable candidate correctness")


def _disposition_report(rows: list[JoinedOutcome]) -> dict[str, Any]:
    states: dict[str, list[EvaluationOutcome]] = {}
    for item in rows:
        states.setdefault(_truth_state(item), []).append(item.outcome)
    rendered: dict[str, Any] = {}
    quarantine_eligible = 0
    correct_quarantines = 0
    for state, outcomes in sorted(states.items()):
        actions = {
            action.value: sum(outcome.action == action for outcome in outcomes)
            for action in (RouteAction.ACCEPT, RouteAction.REJECT, RouteAction.ABSTAIN)
        }
        requires_quarantine = state in {
            "invalid_task",
            "indeterminate_task",
            "valid_candidate_indeterminate",
        }
        abstentions = actions[RouteAction.ABSTAIN.value]
        if requires_quarantine:
            quarantine_eligible += len(outcomes)
            correct_quarantines += abstentions
        rendered[state] = {
            "records": len(outcomes),
            "actions": actions,
            "execution_count": sum(
                outcome.execution_count for outcome in outcomes
            ),
            "cost": sum(outcome.cost for outcome in outcomes),
            "requires_quarantine": requires_quarantine,
            "correct_quarantine_count": abstentions if requires_quarantine else 0,
            "incorrect_non_abstain_count": (
                len(outcomes) - abstentions if requires_quarantine else 0
            ),
        }
    return {
        "by_truth_state": rendered,
        "quarantine": {
            "eligible": quarantine_eligible,
            "correct_abstentions": correct_quarantines,
            "incorrect_non_abstentions": quarantine_eligible - correct_quarantines,
            "accuracy": (
                correct_quarantines / quarantine_eligible
                if quarantine_eligible
                else None
            ),
            "rule": (
                "abstain is the only correct disposition for invalid tasks, "
                "indeterminate tasks, or indeterminate candidate truth"
            ),
        },
    }


def _raw_totals(rows: list[JoinedOutcome]) -> dict[str, Any]:
    outcomes = [item.outcome for item in rows]
    total_cost = sum(outcome.cost for outcome in outcomes)
    return {
        "records": len(outcomes),
        "actions": {
            action.value: sum(outcome.action == action for outcome in outcomes)
            for action in (RouteAction.ACCEPT, RouteAction.REJECT, RouteAction.ABSTAIN)
        },
        "records_with_execution": sum(
            outcome.execution_count > 0 for outcome in outcomes
        ),
        "execution_count": sum(outcome.execution_count for outcome in outcomes),
        "total_cost": total_cost,
        "mean_cost": total_cost / len(outcomes),
        "scope": "all joined rows before truth-conditional metric exclusions",
    }


def _task_validity_report(
    rows: list[JoinedOutcome],
    *,
    calibration_bins: int,
) -> dict[str, Any]:
    scored: list[tuple[float, bool]] = []
    validity_counts: dict[str, int] = {}
    excluded_indeterminate = 0
    for item in rows:
        validity = item.record.task_adjudication.task_validity
        validity_counts[validity.value] = validity_counts.get(validity.value, 0) + 1
        if validity == TaskValidity.INDETERMINATE:
            excluded_indeterminate += 1
        else:
            scored.append((
                item.outcome.probability_task_valid,
                validity == TaskValidity.VALID,
            ))
    return {
        "probability_field": "probability_task_valid",
        "truth_source": "joined_corpus.task_adjudication.task_validity",
        "truth_counts": dict(sorted(validity_counts.items())),
        "excluded_indeterminate": excluded_indeterminate,
        **_binary_calibration_report(scored, calibration_bins=calibration_bins),
    }


def _candidate_correctness_report(
    rows: list[JoinedOutcome],
    *,
    calibration_bins: int,
) -> dict[str, Any]:
    metric_rows = [
        outcome
        for item in rows
        if (outcome := _candidate_metric_outcome(item)) is not None
    ]
    exclusions: dict[str, int] = {}
    for item in rows:
        if _candidate_metric_outcome(item) is not None:
            continue
        state = _truth_state(item)
        exclusions[state] = exclusions.get(state, 0) + 1
    by_subgroup: dict[str, list[VerificationOutcome]] = {}
    for outcome in metric_rows:
        by_subgroup.setdefault(outcome.subgroup, []).append(outcome)
    if metric_rows:
        curve = risk_coverage_curve(metric_rows)
        summary: dict[str, Any] | None = _metric_report(
            metric_rows, calibration_bins=calibration_bins
        )
        calibration: dict[str, Any] | None = {
            "method": "fixed_width_probability_bins",
            "bin_count": calibration_bins,
            "bins": [
                asdict(item)
                for item in calibration_table(metric_rows, bins=calibration_bins)
            ],
        }
        risk_coverage: dict[str, Any] | None = {
            "abstention_treatment": (
                "valid determinate abstentions enter the final undefined-confidence group"
            ),
            "integration": "right_continuous_step_to_full_coverage",
            "area": area_under_risk_coverage(curve),
            "curve": [asdict(point) for point in curve],
        }
    else:
        summary = None
        calibration = None
        risk_coverage = None
    return {
        "probability_field": "probability_correct_given_valid_task",
        "truth_source": (
            "joined_corpus.candidate_adjudication.candidate_correctness, "
            "conditional on task_validity=valid"
        ),
        "eligible_count": len(metric_rows),
        "excluded_count": len(rows) - len(metric_rows),
        "exclusions": dict(sorted(exclusions.items())),
        "summary": summary,
        "calibration": calibration,
        "risk_coverage": risk_coverage,
        "subgroups": {
            subgroup: _metric_report(values, calibration_bins=calibration_bins)
            for subgroup, values in sorted(by_subgroup.items())
        },
    }


def _verifier_validity_report(
    corpus_records: list[VerificationGapRecord],
    *,
    calibration_bins: int,
) -> dict[str, Any]:
    modalities: dict[str, list[Any]] = {}
    for record in corpus_records:
        for event in record.observations:
            modalities.setdefault(event.observation.kind.value, []).append(event)
    rendered: dict[str, Any] = {}
    for modality, events in sorted(modalities.items()):
        scored: list[tuple[float, bool]] = []
        label_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        protocol_counts: dict[str, int] = {}
        missing_probability = 0
        indeterminate_label = 0
        inadequate_adjudication = 0
        for event in events:
            adjudication = event.validity_adjudication
            label = adjudication.validity
            label_counts[label.value] = label_counts.get(label.value, 0) + 1
            source_counts[adjudication.source] = (
                source_counts.get(adjudication.source, 0) + 1
            )
            protocol_counts[adjudication.protocol_version] = (
                protocol_counts.get(adjudication.protocol_version, 0) + 1
            )
            probability = event.observation.verifier_validity
            if label == EvidenceValidity.INDETERMINATE:
                indeterminate_label += 1
            elif not adjudication.determinate_paired_ready:
                inadequate_adjudication += 1
            elif probability is None:
                missing_probability += 1
            else:
                scored.append((probability, label == EvidenceValidity.VALID))
        rendered[modality] = {
            "event_count": len(events),
            "label_counts": dict(sorted(label_counts.items())),
            "adjudication_source_counts": dict(sorted(source_counts.items())),
            "adjudication_protocol_counts": dict(sorted(protocol_counts.items())),
            "excluded_indeterminate_label": indeterminate_label,
            "excluded_inadequate_adjudication": inadequate_adjudication,
            "excluded_missing_probability": missing_probability,
            "probability_field": "EvidenceObservation.verifier_validity",
            **_binary_calibration_report(
                scored, calibration_bins=calibration_bins
            ),
        }
    return {
        "unit": "corpus_evidence_event",
        "deduplication": "computed once per exact corpus, not once per policy outcome",
        "modalities": rendered,
    }


def _evaluation_report(
    rows: list[JoinedOutcome],
    *,
    calibration_bins: int,
) -> dict[str, Any]:
    outcomes = [item.outcome for item in rows]
    identity = outcomes[0].evaluation_identity
    if any(outcome.evaluation_identity != identity for outcome in outcomes):
        raise ValueError("evaluation report rows do not share one experiment identity")
    return {
        "identity": _identity_dict(identity),
        "input": {
            "outcome_set_sha256": _outcome_set_digest(outcomes),
            "record_count": len(outcomes),
            "acquisition_trajectory_count": len({
                outcome.acquisition_trajectory_digest for outcome in outcomes
            }),
            "acquisition_trajectory_digests": sorted({
                outcome.acquisition_trajectory_digest for outcome in outcomes
            }),
        },
        "task_validity": _task_validity_report(
            rows, calibration_bins=calibration_bins
        ),
        "raw_totals": _raw_totals(rows),
        "candidate_correctness": _candidate_correctness_report(
            rows, calibration_bins=calibration_bins
        ),
        "dispositions": _disposition_report(rows),
    }


def build_evaluation_report(
    outcomes: list[EvaluationOutcome],
    corpus_records: list[VerificationGapRecord],
    *,
    calibration_bins: int = 10,
) -> dict[str, Any]:
    """Build identity-preserving per-run evaluation and pairing diagnostics."""

    if not outcomes:
        raise ValueError("at least one outcome is required")
    if isinstance(calibration_bins, bool) or not isinstance(calibration_bins, int):
        raise ValueError("calibration_bins must be a positive integer")
    if calibration_bins <= 0:
        raise ValueError("calibration_bins must be a positive integer")
    _validate_outcome_set(outcomes)
    joined = _join_outcomes_to_corpus(outcomes, corpus_records)

    grouped: dict[
        tuple[str, str, str, int, str, str, str, str], list[JoinedOutcome]
    ] = {}
    for item in joined:
        grouped.setdefault(item.outcome.evaluation_identity, []).append(item)
    evaluations = [
        _evaluation_report(rows, calibration_bins=calibration_bins)
        for _, rows in sorted(grouped.items())
    ]

    candidate_sets = [
        {item.outcome.candidate_key for item in rows}
        for _, rows in sorted(grouped.items())
    ]
    candidate_union = set().union(*candidate_sets)
    candidate_intersection = set.intersection(*candidate_sets) if candidate_sets else set()
    fully_paired = all(candidate_set == candidate_sets[0] for candidate_set in candidate_sets)

    identities = [_identity_dict(identity) for identity in sorted(grouped)]
    exact_corpus_digest = corpus_digest(corpus_records)
    joined_record_keys = {(item.record.key) for item in joined}
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "input": {
            "outcome_set_sha256": _outcome_set_digest(outcomes),
            "record_count": len(outcomes),
            "truth_source": "exact_corpus_0.5.0_record_and_corpus_digest_join",
            "corpus_digest": exact_corpus_digest,
            "corpus_record_count": len(corpus_records),
            "joined_unique_corpus_records": len(joined_record_keys),
            "corpus_record_coverage": len(joined_record_keys) / len(corpus_records),
            "acquisition_trajectory_count": len({
                outcome.acquisition_trajectory_digest for outcome in outcomes
            }),
        },
        "identities": {
            "evaluation_units": identities,
            "policies": [
                {"policy_id": policy_id, "policy_version": policy_version}
                for policy_id, policy_version in sorted({
                    (outcome.policy_id, outcome.policy_version) for outcome in outcomes
                })
            ],
            "calibrations": sorted({outcome.calibration_id for outcome in outcomes}),
            "corpora": [
                {"corpus_id": corpus_id, "corpus_revision": corpus_revision}
                for corpus_id, corpus_revision in sorted({
                    (outcome.corpus_id, outcome.corpus_revision) for outcome in outcomes
                })
            ],
            "acquisition_trajectories": [
                _trajectory_identity_dict(outcome)
                for outcome in sorted(outcomes, key=lambda item: item.observation_key)
            ],
        },
        "pairing": {
            "evaluation_unit_count": len(evaluations),
            "unique_candidate_count": len(candidate_union),
            "candidates_shared_by_all_units": len(candidate_intersection),
            "fully_paired": fully_paired,
            "per_unit_candidate_counts": [len(candidate_set) for candidate_set in candidate_sets],
        },
        "evaluations": evaluations,
        "verifier_validity": _verifier_validity_report(
            corpus_records, calibration_bins=calibration_bins
        ),
        "known_blockers": {
            "task_aware_routing": {
                "implemented": False,
                "reason": (
                    "manifest and router-state contracts do not yet expose a task-validity "
                    "model; evaluation accepts probability_task_valid but does not make the "
                    "current router task-aware"
                ),
            },
        },
        "off_policy_evaluation": {
            "computed": False,
            "reason": (
                "acquisition_trajectory_digest is an auditable join key only; "
                "this outcome file does not establish behavior-policy propensity "
                "validity, target-policy overlap, or a causal estimand"
            ),
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench-cleanser-evaluate",
        description=(
            "Evaluate paired verification outcomes with calibration, selective "
            "risk, execution, and cost metrics"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "outcomes",
        help="Strict truth-free evaluation 0.4.0 JSONL file, or '-' for stdin",
    )
    parser.add_argument(
        "--corpus",
        required=True,
        help="Exact paired corpus 0.5.0 JSONL supplying joined truth",
    )
    parser.add_argument("--output", help="Write JSON report here instead of stdout")
    parser.add_argument(
        "--calibration-bins",
        type=int,
        default=10,
        help="Number of fixed-width ECE bins (default: 10)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.calibration_bins <= 0:
        raise SystemExit("--calibration-bins must be positive")

    try:
        with pathlib.Path(args.corpus).open(encoding="utf-8") as stream:
            corpus_records = load_corpus(stream)
        if args.outcomes == "-":
            outcomes = load_outcomes(sys.stdin)
        else:
            with pathlib.Path(args.outcomes).open(encoding="utf-8") as stream:
                outcomes = load_outcomes(stream)
        report = build_evaluation_report(
            outcomes,
            corpus_records,
            calibration_bins=args.calibration_bins,
        )
        rendered = strict_json_dumps(report, indent=2) + "\n"
        if args.output:
            atomic_write(pathlib.Path(args.output), rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, ValueError) as exc:
        raise SystemExit(f"verification evaluation failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - console entry point
    main()
