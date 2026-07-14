"""Strict descriptive/OPE analysis tests for the prospective pilot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from bench_cleanser.verification.models import EvidenceStatus
from experiments.prospective_pilot.analysis import (
    CandidateCorrectness,
    ProspectiveAnalysisReport,
    TaskAnalysisRecord,
    TaskValidity,
    _validate_truth_join,
    build_analysis_report,
)
from experiments.prospective_pilot.scheduler import (
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    TaskSelectionDisposition,
    build_task_selection_decision,
    load_study_bindings,
)
from experiments.prospective_pilot.target_policies import TargetPolicyId
from tests.test_prospective_scheduler import _complete_chain, _timestamp

ROOT = Path(__file__).parents[1]


@pytest.fixture
def bindings() -> SchedulerBindings:
    return load_study_bindings(ROOT)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ledger(
    bindings: SchedulerBindings,
) -> tuple[tuple[TaskRoundDecision, ...], tuple[TaskSelectionDecision, ...]]:
    rounds: list[TaskRoundDecision] = []
    selections: list[TaskSelectionDecision] = []
    for task_id in bindings.frame.task_ids:
        chain = _complete_chain(
            bindings,
            task_id,
            result_status=EvidenceStatus.SUPPORTS_CORRECT,
        )
        rounds.extend(chain)
        selections.append(build_task_selection_decision(
            chain,
            bindings=bindings,
            scheduled_at=_timestamp(len(chain) + 1),
        ))
    return tuple(rounds), tuple(selections)


def _records(
    selections: tuple[TaskSelectionDecision, ...],
) -> tuple[TaskAnalysisRecord, ...]:
    first_selected = next(
        (
            item.task_id
            for item in selections
            if item.disposition == TaskSelectionDisposition.SELECT_CANDIDATE
        ),
        None,
    )
    result: list[TaskAnalysisRecord] = []
    for index, selection in enumerate(selections):
        selected = selection.selected_candidate_id
        correctness = (
            CandidateCorrectness.INCORRECT
            if selection.task_id == first_selected
            else CandidateCorrectness.CORRECT if selected is not None else None
        )
        result.append(TaskAnalysisRecord(
            task_id=selection.task_id,
            repository_stratum=selection.task_id.partition("__")[0],
            task_selection_sha256=selection.decision_sha256,
            adjudication_record_sha256=_digest(f"adjudication:{selection.task_id}"),
            task_validity=TaskValidity.VALID,
            selected_candidate_id=selected,
            selected_candidate_correctness=correctness,
            full_execution_acquisitions=index % 3,
            environment_failure_count=int(index == 1),
            cold_worker_wall_seconds=float(index + 1),
            warm_worker_wall_seconds=float(index) / 2.0,
            cpu_seconds=float(index) / 3.0,
            storage_bytes=index * 100,
            input_tokens=index * 10,
            output_tokens=index * 2,
            usd_micros=index * 1000,
            human_minutes=index,
            deviation_codes=("environment_issue",) if index == 1 else (),
        ))
    return tuple(result)


def test_analysis_plan_binds_fixed_source_and_denies_unimplemented_estimators() -> None:
    plan_path = ROOT / "experiments/prospective_pilot/analysis_plan.json"
    source_path = ROOT / "experiments/prospective_pilot/analysis.py"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source = source_path.read_bytes()
    assert plan["available_bindings"]["analysis_implementation"] == {
        "bytes": len(source),
        "logical_path": "experiments/prospective_pilot/analysis.py",
        "sha256": hashlib.sha256(source).hexdigest(),
        "status": "available",
    }
    assert plan["implemented_estimators"]["doubly_robust"] == {
        "availability": "not_implemented_not_claimed",
        "nuisance_model": None,
        "cross_fitting": None,
    }
    assert plan["implemented_estimators"]["learned_or_calibrated_policy"] is False


def test_complete_report_releases_only_supported_adequate_ess_diagnostics(
    bindings: SchedulerBindings,
) -> None:
    rounds, selections = _ledger(bindings)
    records = _records(selections)
    report = build_analysis_report(
        rounds,
        selections,
        records,
        bindings=bindings,
    )
    payload = report.to_dict()
    assert len(payload["raw_task_cluster_rows"]) == 22
    summaries = {
        item["policy_id"]: item
        for item in payload["risk_coverage_cost_frontier"]
    }
    behavior = summaries[TargetPolicyId.BEHAVIOR_MIXTURE.value]
    assert behavior["release_status"] == "released_descriptive_ope_point_estimate"
    assert behavior["effective_sample_size"] == pytest.approx(22.0)
    assert behavior["coverage"] == pytest.approx(7 / 22)
    assert behavior["accepted_set_false_accept_risk"] == pytest.approx(1 / 7)
    assert behavior["confidence_interval"] is None
    assert all(
        item["claim_scope"]
        == "descriptive_development_analysis_only_no_h1_through_h6"
        for item in summaries.values()
    )
    assert payload["limitations"] == {
        "confidence_intervals": "not_implemented_for_ope_point_diagnostics",
        "hypothesis_tests": "none",
        "repository_generalization": "forbidden",
        "learned_or_calibrated_policy": False,
        "positive_performance_claim": False,
    }


def test_report_retains_failures_costs_deviations_and_digest_identity(
    bindings: SchedulerBindings,
) -> None:
    rounds, selections = _ledger(bindings)
    records = _records(selections)
    first = build_analysis_report(
        rounds,
        selections,
        records,
        bindings=bindings,
    )
    second = build_analysis_report(
        rounds,
        selections,
        records,
        bindings=bindings,
    )
    assert first.report_sha256 == second.report_sha256
    payload = first.to_dict()
    assert payload["deviation_log"] == [
        {
            "task_id": selections[1].task_id,
            "deviation_code": "environment_issue",
        }
    ]
    assert any(
        item["environment_failure_count"] == 1
        for item in payload["all_abstentions_and_failures"]
    )
    costs = payload["cold_and_warm_cost_decomposition"]
    assert costs["cold_worker_wall_seconds"] == sum(range(1, 23))
    assert costs["storage_bytes"] == sum(index * 100 for index in range(22))
    with pytest.raises(ValueError, match="digest differs"):
        ProspectiveAnalysisReport(first.payload, report_sha256="a" * 64)
    first.payload["claim_scope"] = "mutated"
    with pytest.raises(ValueError, match="mutated after construction"):
        first.to_dict()


def test_exact_task_and_selection_joins_fail_closed(
    bindings: SchedulerBindings,
) -> None:
    rounds, selections = _ledger(bindings)
    records = _records(selections)
    with pytest.raises(ValueError, match="exact frozen task frame"):
        build_analysis_report(
            rounds,
            selections,
            records[:-1],
            bindings=bindings,
        )
    wrong = replace(records[0], task_selection_sha256="a" * 64, record_sha256="")
    with pytest.raises(ValueError, match="selection digest differs"):
        build_analysis_report(
            rounds,
            selections,
            (wrong, *records[1:]),
            bindings=bindings,
        )


def test_repository_stratum_is_bound_to_the_frozen_task_identity(
    bindings: SchedulerBindings,
) -> None:
    _rounds, selections = _ledger(bindings)
    record = _records(selections)[0]

    with pytest.raises(ValueError, match="repository stratum differs"):
        replace(record, repository_stratum="wrong-repository", record_sha256="")


def test_conditional_truth_contract_rejects_invalid_combinations(
    bindings: SchedulerBindings,
) -> None:
    candidate_id = bindings.frame.tasks[0][1][0]
    selection = cast(
        TaskSelectionDecision,
        SimpleNamespace(
            decision_sha256="b" * 64,
            selected_candidate_id=candidate_id,
            disposition=TaskSelectionDisposition.SELECT_CANDIDATE,
        ),
    )
    with pytest.raises(ValueError, match="invalid task requires"):
        record = TaskAnalysisRecord(
            task_id=bindings.frame.task_ids[0],
            repository_stratum=bindings.frame.task_ids[0].partition("__")[0],
            task_selection_sha256="b" * 64,
            adjudication_record_sha256=_digest("invalid-combination"),
            task_validity=TaskValidity.INVALID,
            selected_candidate_id=candidate_id,
            selected_candidate_correctness=CandidateCorrectness.CORRECT,
            full_execution_acquisitions=0,
            environment_failure_count=0,
            cold_worker_wall_seconds=0,
            warm_worker_wall_seconds=0,
            cpu_seconds=0,
            storage_bytes=0,
            input_tokens=0,
            output_tokens=0,
            usd_micros=0,
            human_minutes=0,
        )
        _validate_truth_join(record, selection)
