"""Strict descriptive and task-cluster OPE analysis for the prospective pilot.

Target-policy likelihoods are computed exclusively from deployable scheduler
state by :mod:`target_policies`.  Blinded adjudication enters only through the
separate post-policy ``TaskAnalysisRecord`` join below.  Estimates fail closed
on any support violation, effective sample size below ten, or an empty weighted
accepted set.  The 22-task outcome-exposed development frame supports no H1-H6,
repository-generalization, learned-policy, or calibrated-risk claim.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from math import fsum, isfinite
from typing import Any

from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from experiments.prospective_pilot.scheduler import (
    SCHEDULER_STUDY_ID,
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    TaskSelectionDisposition,
    validate_complete_study_ledger,
)
from experiments.prospective_pilot.target_policies import (
    TargetPolicyId,
    TargetPolicyTrace,
    evaluate_all_target_policies,
)

ANALYSIS_SCHEMA_VERSION = "prospective-pilot-analysis-report-0.1.0"
ANALYSIS_IMPLEMENTATION_LOGICAL_PATH = "experiments/prospective_pilot/analysis.py"
MINIMUM_EFFECTIVE_SAMPLE_SIZE = 10.0
CLAIM_SCOPE = "descriptive_development_analysis_only_no_h1_through_h6"
REPOSITORY_STRATUM_RULE = "task_id_prefix_before_double_underscore"

_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class TaskValidity(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    INDETERMINATE = "indeterminate"


class CandidateCorrectness(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(strict_json_dumps(value).encode("utf-8")).hexdigest()


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a canonical identifier")
    return value


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return value


def _candidate(value: Any, field: str) -> str:
    if not isinstance(value, str) or _CANDIDATE_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be an opaque sha256 candidate ID")
    return value


def _repository_stratum(task_id: str) -> str:
    repository, separator, instance = task_id.partition("__")
    if separator != "__" or not repository or not instance:
        raise ValueError("analysis task ID does not encode a repository stratum")
    return repository


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _nonnegative_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not isfinite(result) or result < 0.0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return result


def _enum(enum_type: type[Enum], value: Any, field: str) -> Enum:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field} must be a {enum_type.__name__}")
    return value


@dataclass(frozen=True)
class TaskAnalysisRecord:
    """Post-policy, curator-bound task outcome and measured-cost join."""

    task_id: str
    repository_stratum: str
    task_selection_sha256: str
    adjudication_record_sha256: str
    task_validity: TaskValidity
    selected_candidate_id: str | None
    selected_candidate_correctness: CandidateCorrectness | None
    full_execution_acquisitions: int
    environment_failure_count: int
    cold_worker_wall_seconds: float
    warm_worker_wall_seconds: float
    cpu_seconds: float
    storage_bytes: int
    input_tokens: int
    output_tokens: int
    usd_micros: int
    human_minutes: int
    deviation_codes: tuple[str, ...] = ()
    record_sha256: str = ""

    def _payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "repository_stratum": self.repository_stratum,
            "task_selection_sha256": self.task_selection_sha256,
            "adjudication_record_sha256": self.adjudication_record_sha256,
            "task_validity": self.task_validity.value,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_candidate_correctness": (
                self.selected_candidate_correctness.value
                if self.selected_candidate_correctness is not None
                else None
            ),
            "full_execution_acquisitions": self.full_execution_acquisitions,
            "environment_failure_count": self.environment_failure_count,
            "cold_worker_wall_seconds": self.cold_worker_wall_seconds,
            "warm_worker_wall_seconds": self.warm_worker_wall_seconds,
            "cpu_seconds": self.cpu_seconds,
            "storage_bytes": self.storage_bytes,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd_micros": self.usd_micros,
            "human_minutes": self.human_minutes,
            "deviation_codes": list(self.deviation_codes),
        }

    def __post_init__(self) -> None:
        _identifier(self.task_id, "analysis_record.task_id")
        _identifier(self.repository_stratum, "analysis_record.repository_stratum")
        if self.repository_stratum != _repository_stratum(self.task_id):
            raise ValueError(
                "analysis record repository stratum differs from its task identity"
            )
        _digest(self.task_selection_sha256, "analysis_record.task_selection_sha256")
        _digest(
            self.adjudication_record_sha256,
            "analysis_record.adjudication_record_sha256",
        )
        _enum(TaskValidity, self.task_validity, "analysis_record.task_validity")
        if self.selected_candidate_id is not None:
            _candidate(
                self.selected_candidate_id,
                "analysis_record.selected_candidate_id",
            )
        if self.selected_candidate_correctness is not None:
            _enum(
                CandidateCorrectness,
                self.selected_candidate_correctness,
                "analysis_record.selected_candidate_correctness",
            )
        for field in (
            "full_execution_acquisitions",
            "environment_failure_count",
            "storage_bytes",
            "input_tokens",
            "output_tokens",
            "usd_micros",
            "human_minutes",
        ):
            object.__setattr__(self, field, _nonnegative_int(getattr(self, field), field))
        for field in (
            "cold_worker_wall_seconds",
            "warm_worker_wall_seconds",
            "cpu_seconds",
        ):
            object.__setattr__(
                self,
                field,
                _nonnegative_number(getattr(self, field), field),
            )
        if not isinstance(self.deviation_codes, (list, tuple)):
            raise ValueError("analysis_record.deviation_codes must be a sequence")
        codes = tuple(self.deviation_codes)
        if list(codes) != sorted(codes) or len(codes) != len(set(codes)):
            raise ValueError("deviation codes must be sorted and unique")
        for code in codes:
            if not isinstance(code, str) or _CODE_RE.fullmatch(code) is None:
                raise ValueError("deviation codes must be canonical reason codes")
        object.__setattr__(self, "deviation_codes", codes)
        computed = _canonical_sha256(self._payload())
        if self.record_sha256 and _digest(
            self.record_sha256,
            "analysis_record.record_sha256",
        ) != computed:
            raise ValueError("analysis record digest differs")
        object.__setattr__(self, "record_sha256", computed)

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "record_sha256": self.record_sha256}


def _validate_truth_join(
    record: TaskAnalysisRecord,
    selection: TaskSelectionDecision,
) -> None:
    if record.task_selection_sha256 != selection.decision_sha256:
        raise ValueError("analysis record selection digest differs from ledger")
    if record.selected_candidate_id != selection.selected_candidate_id:
        raise ValueError("analysis record selected candidate differs from ledger")
    if selection.disposition == TaskSelectionDisposition.ABSTAIN:
        if record.selected_candidate_correctness is not None:
            raise ValueError("abstained task cannot carry selected-candidate truth")
        return
    if record.selected_candidate_id is None:
        raise ValueError("selected task is missing a candidate identity")
    correctness = record.selected_candidate_correctness
    if correctness is None:
        raise ValueError("selected task is missing conditional candidate truth")
    if record.task_validity == TaskValidity.INVALID:
        if correctness != CandidateCorrectness.NOT_APPLICABLE:
            raise ValueError("invalid task requires not_applicable candidate truth")
    elif record.task_validity == TaskValidity.INDETERMINATE:
        if correctness != CandidateCorrectness.INDETERMINATE:
            raise ValueError("indeterminate task requires indeterminate candidate truth")
    elif correctness == CandidateCorrectness.NOT_APPLICABLE:
        raise ValueError("valid task cannot use not_applicable candidate truth")


def _unsafe_accept(
    record: TaskAnalysisRecord,
    selection: TaskSelectionDecision,
) -> bool | None:
    if selection.disposition == TaskSelectionDisposition.ABSTAIN:
        return None
    return not (
        record.task_validity == TaskValidity.VALID
        and record.selected_candidate_correctness == CandidateCorrectness.CORRECT
    )


def _effective_sample_size(weights: Sequence[float]) -> float | None:
    total = fsum(weights)
    squared = fsum(item * item for item in weights)
    if total <= 0.0 or squared <= 0.0:
        return None
    return total * total / squared


def _weighted_mean(
    weights: Sequence[float],
    values: Sequence[float],
) -> float | None:
    denominator = fsum(weights)
    if denominator <= 0.0:
        return None
    return fsum(weight * value for weight, value in zip(weights, values, strict=True)) / denominator


def _policy_summary(
    policy_id: TargetPolicyId,
    traces: Sequence[TargetPolicyTrace],
    records: Sequence[TaskAnalysisRecord],
    selections: Sequence[TaskSelectionDecision],
) -> dict[str, Any]:
    violations = [item.task_id for item in traces if item.importance_weight is None]
    weights = [
        0.0 if item.importance_weight is None else item.importance_weight
        for item in traces
    ]
    ess = None if violations else _effective_sample_size(weights)
    if violations:
        release_status = "omitted_support_violation"
    elif ess is None or ess < MINIMUM_EFFECTIVE_SAMPLE_SIZE:
        release_status = "omitted_effective_sample_size_below_10"
    else:
        release_status = "released_descriptive_ope_point_estimate"
    accepted = [
        float(item.disposition == TaskSelectionDisposition.SELECT_CANDIDATE)
        for item in selections
    ]
    unsafe = [
        float(_unsafe_accept(record, selection) is True)
        for record, selection in zip(records, selections, strict=True)
    ]
    accepted_weights = [
        weight * indicator for weight, indicator in zip(weights, accepted, strict=True)
    ]
    accepted_denominator = fsum(accepted_weights)
    if release_status == "released_descriptive_ope_point_estimate" and accepted_denominator <= 0.0:
        release_status = "omitted_empty_weighted_accepted_set"
    released = release_status == "released_descriptive_ope_point_estimate"
    risk = (
        fsum(
            weight * accepted_indicator * unsafe_indicator
            for weight, accepted_indicator, unsafe_indicator in zip(
                weights,
                accepted,
                unsafe,
                strict=True,
            )
        )
        / accepted_denominator
        if released
        else None
    )
    total_wall = [
        item.cold_worker_wall_seconds + item.warm_worker_wall_seconds
        for item in records
    ]
    return {
        "policy_id": policy_id.value,
        "release_status": release_status,
        "support_violation_task_ids": violations,
        "support_violation_count": len(violations),
        "task_count": len(traces),
        "sum_task_weights": fsum(weights) if not violations else None,
        "effective_sample_size": ess,
        "accepted_set_false_accept_risk": risk,
        "coverage": _weighted_mean(weights, accepted) if released else None,
        "mean_full_execution_acquisitions": (
            _weighted_mean(
                weights,
                [float(item.full_execution_acquisitions) for item in records],
            )
            if released
            else None
        ),
        "mean_worker_wall_seconds": (
            _weighted_mean(weights, total_wall) if released else None
        ),
        "mean_environment_failures": (
            _weighted_mean(
                weights,
                [float(item.environment_failure_count) for item in records],
            )
            if released
            else None
        ),
        "confidence_interval": None,
        "claim_scope": CLAIM_SCOPE,
    }


@dataclass(frozen=True)
class ProspectiveAnalysisReport:
    payload: dict[str, Any]
    report_sha256: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise ValueError("analysis report payload must be a dictionary")
        canonical_payload = strict_json_loads(strict_json_dumps(self.payload))
        if not isinstance(canonical_payload, dict):
            raise ValueError("analysis report payload must remain a JSON object")
        computed = _canonical_sha256(canonical_payload)
        if self.report_sha256 and _digest(
            self.report_sha256,
            "analysis report SHA-256",
        ) != computed:
            raise ValueError("analysis report digest differs")
        object.__setattr__(self, "payload", canonical_payload)
        object.__setattr__(self, "report_sha256", computed)

    def to_dict(self) -> dict[str, Any]:
        if _canonical_sha256(self.payload) != self.report_sha256:
            raise ValueError("analysis report payload mutated after construction")
        return {**self.payload, "report_sha256": self.report_sha256}


def build_analysis_report(
    rounds: Sequence[TaskRoundDecision],
    selections: Sequence[TaskSelectionDecision],
    records: Sequence[TaskAnalysisRecord],
    *,
    bindings: SchedulerBindings,
) -> ProspectiveAnalysisReport:
    """Build the frozen descriptive/OPE report for one complete study ledger."""

    validate_complete_study_ledger(rounds, selections, bindings=bindings)
    if not isinstance(records, (list, tuple)) or any(
        not isinstance(item, TaskAnalysisRecord) for item in records
    ):
        raise ValueError("analysis records are invalid")
    record_by_task: dict[str, TaskAnalysisRecord] = {}
    for item in records:
        if item.task_id in record_by_task:
            raise ValueError("analysis records repeat a task")
        record_by_task[item.task_id] = item
    expected_tasks = tuple(bindings.frame.task_ids)
    if set(record_by_task) != set(expected_tasks):
        raise ValueError("analysis records differ from the exact frozen task frame")
    selection_by_task = {item.task_id: item for item in selections}
    round_by_task: dict[str, list[TaskRoundDecision]] = {}
    for item in rounds:
        round_by_task.setdefault(item.task_id, []).append(item)
    ordered_records = tuple(record_by_task[task_id] for task_id in expected_tasks)
    ordered_selections = tuple(selection_by_task[task_id] for task_id in expected_tasks)
    traces_by_policy: dict[TargetPolicyId, list[TargetPolicyTrace]] = {
        item: [] for item in TargetPolicyId
    }
    raw_rows: list[dict[str, Any]] = []
    for task_id, record, selection in zip(
        expected_tasks,
        ordered_records,
        ordered_selections,
        strict=True,
    ):
        _validate_truth_join(record, selection)
        chain = tuple(sorted(round_by_task[task_id], key=lambda item: item.round_index))
        traces = evaluate_all_target_policies(chain, selection, bindings=bindings)
        for trace in traces:
            traces_by_policy[trace.policy_id].append(trace)
        raw_rows.append({
            "task_id": task_id,
            "repository_stratum": record.repository_stratum,
            "record_sha256": record.record_sha256,
            "selection_sha256": selection.decision_sha256,
            "disposition": selection.disposition.value,
            "selected_candidate_id": selection.selected_candidate_id,
            "task_validity": record.task_validity.value,
            "selected_candidate_correctness": (
                record.selected_candidate_correctness.value
                if record.selected_candidate_correctness is not None
                else None
            ),
            "unsafe_accept": _unsafe_accept(record, selection),
            "full_execution_acquisitions": record.full_execution_acquisitions,
            "environment_failure_count": record.environment_failure_count,
            "cold_worker_wall_seconds": record.cold_worker_wall_seconds,
            "warm_worker_wall_seconds": record.warm_worker_wall_seconds,
            "policy_traces": {
                trace.policy_id.value: {
                    "trace_sha256": trace.trace_sha256,
                    "importance_weight": trace.importance_weight,
                    "support_violation_actions": list(
                        trace.support_violation_actions
                    ),
                }
                for trace in traces
            },
        })
    summaries = [
        _policy_summary(
            policy_id,
            traces_by_policy[policy_id],
            ordered_records,
            ordered_selections,
        )
        for policy_id in TargetPolicyId
    ]
    repository_rows: list[dict[str, Any]] = []
    for repository in sorted({item.repository_stratum for item in ordered_records}):
        members = [
            (record, selection)
            for record, selection in zip(
                ordered_records,
                ordered_selections,
                strict=True,
            )
            if record.repository_stratum == repository
        ]
        accepted = [
            (record, selection)
            for record, selection in members
            if selection.disposition == TaskSelectionDisposition.SELECT_CANDIDATE
        ]
        unsafe_count = sum(
            _unsafe_accept(record, selection) is True
            for record, selection in accepted
        )
        repository_rows.append({
            "repository_stratum": repository,
            "task_count": len(members),
            "accepted_count": len(accepted),
            "unsafe_accept_count": unsafe_count,
            "unsafe_accept_fraction": (
                unsafe_count / len(accepted) if accepted else None
            ),
            "inference_allowed": False,
        })
    deviations = [
        {"task_id": item.task_id, "deviation_code": code}
        for item in ordered_records
        for code in item.deviation_codes
    ]
    failures = [
        row
        for row in raw_rows
        if row["disposition"] == TaskSelectionDisposition.ABSTAIN.value
        or row["unsafe_accept"] is True
        or row["environment_failure_count"] > 0
    ]
    payload = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "study_id": SCHEDULER_STUDY_ID,
        "claim_scope": CLAIM_SCOPE,
        "input_identity_sha256": _canonical_sha256({
            "frame_manifest_sha256": bindings.frame.manifest_sha256,
            "protocol_sha256": bindings.protocol_sha256,
            "round_decision_sha256s": [item.decision_sha256 for item in rounds],
            "selection_sha256s": [item.decision_sha256 for item in ordered_selections],
            "analysis_record_sha256s": [item.record_sha256 for item in ordered_records],
        }),
        "frame_manifest_sha256": bindings.frame.manifest_sha256,
        "protocol_sha256": bindings.protocol_sha256,
        "raw_task_cluster_rows": raw_rows,
        "all_abstentions_and_failures": failures,
        "support_and_overlap_diagnostics": [
            {
                "policy_id": item["policy_id"],
                "release_status": item["release_status"],
                "support_violation_task_ids": item["support_violation_task_ids"],
                "support_violation_count": item["support_violation_count"],
            }
            for item in summaries
        ],
        "task_weights_and_effective_sample_size": [
            {
                "policy_id": policy_id.value,
                "task_weights": [
                    {
                        "task_id": trace.task_id,
                        "importance_weight": trace.importance_weight,
                    }
                    for trace in traces_by_policy[policy_id]
                ],
                "effective_sample_size": next(
                    item["effective_sample_size"]
                    for item in summaries
                    if item["policy_id"] == policy_id.value
                ),
            }
            for policy_id in TargetPolicyId
        ],
        "risk_coverage_cost_frontier": summaries,
        "cold_and_warm_cost_decomposition": {
            "cold_worker_wall_seconds": fsum(
                item.cold_worker_wall_seconds for item in ordered_records
            ),
            "warm_worker_wall_seconds": fsum(
                item.warm_worker_wall_seconds for item in ordered_records
            ),
            "cpu_seconds": fsum(item.cpu_seconds for item in ordered_records),
            "storage_bytes": sum(item.storage_bytes for item in ordered_records),
            "input_tokens": sum(item.input_tokens for item in ordered_records),
            "output_tokens": sum(item.output_tokens for item in ordered_records),
            "usd_micros": sum(item.usd_micros for item in ordered_records),
            "human_minutes": sum(item.human_minutes for item in ordered_records),
        },
        "descriptive_repository_strata": repository_rows,
        "deviation_log": deviations,
        "limitations": {
            "confidence_intervals": "not_implemented_for_ope_point_diagnostics",
            "hypothesis_tests": "none",
            "repository_generalization": "forbidden",
            "learned_or_calibrated_policy": False,
            "positive_performance_claim": False,
        },
    }
    return ProspectiveAnalysisReport(payload)
