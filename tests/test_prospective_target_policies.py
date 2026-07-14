"""Truth-free target-policy likelihood tests for the prospective pilot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from experiments.prospective_pilot.scheduler import (
    COLLECTION_ACTION_IDS,
    POLICY_ACTION_IDS,
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    build_task_selection_decision,
    load_study_bindings,
)
from experiments.prospective_pilot.target_policies import (
    TARGET_POLICY_MANIFEST_SCHEMA_VERSION,
    TARGET_POLICY_RULES,
    TargetPolicyId,
    evaluate_all_target_policies,
    evaluate_target_policy,
    target_distribution,
)
from tests.test_prospective_scheduler import _complete_chain, _timestamp

ROOT = Path(__file__).parents[1]


@pytest.fixture
def bindings() -> SchedulerBindings:
    return load_study_bindings(ROOT)


def _trajectory(
    bindings: SchedulerBindings,
) -> tuple[tuple[TaskRoundDecision, ...], TaskSelectionDecision]:
    chain = _complete_chain(bindings, bindings.frame.task_ids[0])
    selection = build_task_selection_decision(
        chain,
        bindings=bindings,
        scheduled_at=_timestamp(len(chain) + 1),
    )
    return chain, selection


def test_behavior_target_exactly_reproduces_logged_mixture(
    bindings: SchedulerBindings,
) -> None:
    chain, selection = _trajectory(bindings)
    trace = evaluate_target_policy(
        TargetPolicyId.BEHAVIOR_MIXTURE,
        chain,
        selection,
        bindings=bindings,
    )
    assert trace.importance_weight == pytest.approx(1.0)
    assert trace.support_violation_actions == ()
    decisions = {
        item.selection_identity_sha256: item
        for round_decision in chain
        for item in round_decision.scheduled_decisions
    }
    for step in trace.steps:
        logged = decisions[step.selection_identity_sha256]
        assert tuple(
            item.action_id for item in logged.logged_policy_decision.action_catalog
        ) == COLLECTION_ACTION_IDS
        assert len(logged.logged_policy_decision.action_catalog) == 9
        assert {
            item.action_id
            for item in logged.logged_policy_decision.action_catalog
            if item.available
        }.issubset(POLICY_ACTION_IDS)
        assert len(logged.behavior_distribution) <= 7
        target = {
            item.action_id: item.probability
            for item in step.distribution.probabilities
            if item.probability > 0.0
        }
        behavior = {
            item.action_id: item.propensity
            for item in logged.behavior_distribution
        }
        assert target == behavior
        assert step.target_probability == step.behavior_probability


def test_checked_in_manifest_binds_exact_implementation_and_policy_set() -> None:
    manifest_path = (
        ROOT / "experiments/prospective_pilot/target_policy_manifest.json"
    )
    source_path = ROOT / "experiments/prospective_pilot/target_policies.py"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = source_path.read_bytes()
    assert manifest["schema_version"] == TARGET_POLICY_MANIFEST_SCHEMA_VERSION
    assert manifest["implementation"] == {
        "bytes": len(source),
        "logical_path": "experiments/prospective_pilot/target_policies.py",
        "sha256": hashlib.sha256(source).hexdigest(),
        "status": "available",
    }
    assert {
        item["id"]: (item["rule"], item["semantic_required"])
        for item in manifest["policies"]
    } == {
        policy_id.value: contract
        for policy_id, contract in TARGET_POLICY_RULES.items()
    }
    assert manifest["claim_boundary"].endswith(
        "no learned policy, calibration, causal validity, or positive performance claim"
    )


def test_all_frozen_targets_are_deterministic_and_digest_stable(
    bindings: SchedulerBindings,
) -> None:
    chain, selection = _trajectory(bindings)
    first = evaluate_all_target_policies(chain, selection, bindings=bindings)
    second = evaluate_all_target_policies(chain, selection, bindings=bindings)
    assert [item.policy_id for item in first] == list(TargetPolicyId)
    assert [item.trace_sha256 for item in first] == [
        item.trace_sha256 for item in second
    ]
    for trace in first:
        assert trace.to_dict()["trace_sha256"] == trace.trace_sha256
        if trace.support_violation_actions:
            assert trace.importance_weight is None
        else:
            assert trace.importance_weight is not None


def test_conservative_target_uses_bound_preferred_action(
    bindings: SchedulerBindings,
) -> None:
    chain, selection = _trajectory(bindings)
    trace = evaluate_target_policy(
        TargetPolicyId.CONSERVATIVE_PREFERRED,
        chain,
        selection,
        bindings=bindings,
    )
    states = {
        (round_decision.round_index, item.candidate_id): item
        for round_decision in chain
        for item in round_decision.candidates
    }
    for step in trace.steps:
        state = states[(step.round_index, step.candidate_id)]
        assert step.distribution.desired_action_id == state.preferred_action_id


def test_hash_priority_exposes_unavailable_accept_as_support_violation(
    bindings: SchedulerBindings,
) -> None:
    chain, selection = _trajectory(bindings)
    trace = evaluate_target_policy(
        TargetPolicyId.HASH_PRIORITY_NO_RUNTIME,
        chain,
        selection,
        bindings=bindings,
    )
    first_candidate_state = chain[0].candidates[0]
    accept_available = next(
        item.available
        for item in first_candidate_state.action_catalog
        if item.action_id == "accept"
    )
    if accept_available:
        assert "accept" not in trace.support_violation_actions
    else:
        assert "accept" in trace.support_violation_actions
        assert trace.importance_weight is None


def test_policy_inputs_and_trace_identity_fail_closed(
    bindings: SchedulerBindings,
) -> None:
    chain, selection = _trajectory(bindings)
    state = chain[0].candidates[0]
    with pytest.raises(ValueError, match="unknown target policy"):
        target_distribution("invented-v1", state, candidate_position=0)
    with pytest.raises(ValueError, match="candidate position"):
        target_distribution(
            TargetPolicyId.BEHAVIOR_MIXTURE,
            state,
            candidate_position=3,
        )
    trace = evaluate_target_policy(
        TargetPolicyId.BEHAVIOR_MIXTURE,
        chain,
        selection,
        bindings=bindings,
    )
    with pytest.raises(ValueError, match="digest differs"):
        replace(trace, trace_sha256="a" * 64)
