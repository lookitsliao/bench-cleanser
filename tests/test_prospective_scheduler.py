"""Adversarial contracts for the prospective task scheduler."""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import replace
from pathlib import Path

import pytest

from bench_cleanser.verification._io import strict_json_dumps
from bench_cleanser.verification.corpus import (
    EvidenceValidity,
    EvidenceValidityAdjudication,
    PairedEvidence,
    bridge_logged_policy_observation,
)
from bench_cleanser.verification.models import (
    EvidenceCost,
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RiskProfile,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)
from bench_cleanser.verification.policy_log import (
    ActionOffer,
    BootstrapHistoryStep,
    LoggedPolicyDecision,
    RouterRouteStep,
    RouterStateView,
    validate_policy_decision_chain,
)
from experiments.prospective_pilot.review_packets import (
    EXPECTED_SOURCE_FEATURE_FREEZE,
)
from experiments.prospective_pilot.scheduler import (
    ACTION_DRAW_DOMAIN,
    ACTION_DRAW_SEED_SHA256,
    CANDIDATE_ORDER_DOMAIN,
    CANDIDATE_ORDER_SEED_SHA256,
    COLLECTION_ACTION_IDS,
    COLLECTION_ACTION_ROUTE,
    POLICY_ACTION_IDS,
    ROUTER_POLICY_CONFIG_SHA256,
    ROUTER_SOURCE_SHA256,
    SCHEDULER_GENESIS_SHA256,
    BoundRouterDecision,
    CandidateActivity,
    CandidateRoundInput,
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    TaskSelectionDisposition,
    _build_candidate_state,
    build_task_round_decision,
    build_task_selection_decision,
    derive_action_draw,
    derive_candidate_order,
    derive_task_batches,
    derive_task_order,
    load_study_bindings,
    load_task_round_decision,
    load_task_selection_decision,
    validate_complete_study_ledger,
    validate_task_round_chain,
    validate_task_trajectory,
)

ROOT = Path(__file__).resolve().parents[1]

_ACTION_KIND = {
    RouteAction.RUN_STATIC: EvidenceKind.STATIC,
    RouteAction.RUN_SEMANTIC: EvidenceKind.SEMANTIC,
    RouteAction.RUN_TARGETED: EvidenceKind.TARGETED_EXECUTION,
    RouteAction.RUN_FULL: EvidenceKind.FULL_EXECUTION,
    RouteAction.HARDEN_ORACLE: EvidenceKind.ORACLE_HARDENING,
}


@pytest.fixture(scope="module")
def bindings() -> SchedulerBindings:
    return load_study_bindings(ROOT)


def _timestamp(second: int) -> str:
    return f"2026-07-14T00:00:{second:02d}.000000Z"


def _acquisition_id(material: str) -> str:
    return "acq-" + hashlib.sha256(material.encode()).hexdigest()[:32]


def _initial_state(task_id: str, candidate_id: str) -> RouterStateView:
    bootstrap_route = RouteDecision(
        action=RouteAction.RUN_STATIC,
        policy_version="prospective-static-bootstrap-v1",
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.35,
        estimated_relative_cost=0.01,
        reasons=("deterministic static bootstrap",),
        terminal=False,
    )
    bootstrap_observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source="prospective-static-bootstrap",
        source_version="v1",
        acquisition_id=_acquisition_id(f"bootstrap:{task_id}:{candidate_id}"),
        cost=EvidenceCost(wall_seconds=1.0),
    )
    bootstrap = BootstrapHistoryStep(
        receipt_sha256=hashlib.sha256(
            f"bootstrap-receipt:{task_id}:{candidate_id}".encode()
        ).hexdigest(),
        route=RouterRouteStep.from_route_decision(bootstrap_route),
        observation=bootstrap_observation,
    )
    manifest = ValidityManifest(
        instance_id=task_id,
        candidate_id=candidate_id,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(
            language="python",
            files_changed=2,
            lines_changed=40,
            targeted_execution_available=True,
            full_execution_available=True,
        ),
        provenance={"repository": "opaque/repository"},
        evidence=[bootstrap_observation],
        route_history=[bootstrap_route],
    )
    return RouterStateView.from_manifest(
        manifest,
        bootstrap_history=(bootstrap,),
    )


def _action_spec_preimage(action_id: str) -> bytes:
    return strict_json_dumps({
        "action_id": action_id,
        "fixture_contract": "prospective-scheduler-test-v1",
    }).encode("utf-8")


def _catalog() -> tuple[ActionOffer, ...]:
    offers: list[ActionOffer] = []
    for action_id in COLLECTION_ACTION_IDS:
        route_action = COLLECTION_ACTION_ROUTE[action_id]
        terminal = route_action in {
            RouteAction.ACCEPT,
            RouteAction.REJECT,
            RouteAction.ABSTAIN,
        }
        if terminal:
            available = False
            reason = "terminal_governed"
        elif action_id == "static_bootstrap":
            available = False
            reason = "deterministic_bootstrap_completed"
        elif action_id == "hardening_curator":
            available = False
            reason = "curator_only_not_policy_available"
        elif action_id == "semantic_primary":
            available = True
            reason = "semantic_binding_available"
        else:
            available = True
            reason = "execution_binding_available"
        offers.append(ActionOffer(
            action_id=action_id,
            route_action=route_action,
            evidence_kind=None if terminal else _ACTION_KIND[route_action],
            adapter_id=(
                "adapter-oracle-hardening"
                if action_id == "hardening_curator"
                else f"adapter-{action_id}"
            ),
            adapter_version="v1",
            action_spec_sha256=hashlib.sha256(
                _action_spec_preimage(action_id)
            ).hexdigest(),
            available=available,
            availability_reason=reason,
            expected_cost=(
                EvidenceCost() if terminal else EvidenceCost(wall_seconds=1.0)
            ),
        ))
    return tuple(offers)


def _candidate(
    task_id: str,
    candidate_id: str,
    *,
    activity: CandidateActivity = CandidateActivity.ACTIVE,
    decisions: int = 0,
    acquisitions: int = 0,
    completed: tuple[str, ...] = (),
    state: RouterStateView | None = None,
    router_state_sha256: str | None = None,
    history_sha256: str | None = None,
    policy_head_sha256: str | None = None,
    catalog: tuple[ActionOffer, ...] | None = None,
) -> CandidateRoundInput:
    safe_state = state or _initial_state(task_id, candidate_id)
    bound = (
        BoundRouterDecision.from_router_state(safe_state)
        if activity == CandidateActivity.ACTIVE
        else None
    )
    return CandidateRoundInput(
        candidate_id=candidate_id,
        activity=activity,
        decision_count=decisions,
        nonterminal_acquisition_count=acquisitions,
        completed_nonterminal_action_ids=completed,
        router_state_sha256=(
            router_state_sha256 or safe_state.canonical_digest()
        ),
        history_sha256=history_sha256 or safe_state.history_sha256(),
        policy_trajectory_head_sha256=(
            policy_head_sha256
            or (
                SCHEDULER_GENESIS_SHA256
                if decisions == 0
                else hashlib.sha256(
                    f"unlinked-test-head:{candidate_id}:{decisions}".encode()
                ).hexdigest()
            )
        ),
        bound_router_decision=bound,
        action_catalog=catalog or _catalog(),
    )


def _initial_inputs(
    bindings: SchedulerBindings,
    task_id: str,
) -> tuple[CandidateRoundInput, ...]:
    return tuple(
        _candidate(task_id, candidate_id)
        for candidate_id in bindings.frame.candidate_ids_for(task_id)
    )


def _restore_prior_route(route: RouterRouteStep) -> RouteDecision:
    return RouteDecision(
        action=route.action,
        policy_version=route.policy_version,
        candidate_risk=route.candidate_risk,
        verifier_risk=route.verifier_risk,
        expected_information_gain=route.expected_information_gain,
        estimated_relative_cost=route.estimated_relative_cost,
        reasons=("restored safe route projection",),
        terminal=False,
        scores_calibrated=route.scores_calibrated,
        calibration_id=route.calibration_id,
    )


def _append_typed_result(
    old_state: RouterStateView,
    bound: BoundRouterDecision,
    *,
    chosen_action_id: str,
    acquisition_id: str,
    status: EvidenceStatus,
) -> RouterStateView:
    route_action = COLLECTION_ACTION_ROUTE[chosen_action_id]
    kind = _ACTION_KIND[route_action]
    route = RouteDecision(
        action=route_action,
        policy_version=bound.policy_version,
        candidate_risk=bound.candidate_risk,
        verifier_risk=bound.verifier_risk,
        expected_information_gain=bound.expected_information_gain,
        estimated_relative_cost=bound.estimated_relative_cost,
        reasons=("sampled prospective acquisition",),
        terminal=False,
        scores_calibrated=bound.scores_calibrated,
        calibration_id=bound.calibration_id,
    )
    observation = EvidenceObservation(
        kind=kind,
        status=status,
        source=f"prospective-{chosen_action_id}",
        source_version="v1",
        acquisition_id=acquisition_id,
        cost=EvidenceCost(wall_seconds=1.0),
    )
    manifest = ValidityManifest(
        instance_id=old_state.instance_id,
        candidate_id=old_state.candidate_id,
        lifecycle_stage=old_state.lifecycle_stage,
        risk_profile=old_state.risk_profile,
        provenance=dict(old_state.provenance),
        evidence=[
            *(item.observation for item in old_state.bootstrap_history),
            *old_state.evidence_history,
            observation,
        ],
        route_history=[
            *(
                _restore_prior_route(item.route)
                for item in old_state.bootstrap_history
            ),
            *(_restore_prior_route(item) for item in old_state.route_history),
            route,
        ],
    )
    return RouterStateView.from_manifest(
        manifest,
        bootstrap_history=old_state.bootstrap_history,
    )


def _successor_inputs(
    previous: TaskRoundDecision,
    *,
    status: EvidenceStatus = EvidenceStatus.INCONCLUSIVE,
) -> tuple[CandidateRoundInput, ...]:
    decision_by_id = {
        item.candidate_id: item for item in previous.scheduled_decisions
    }
    disposition_by_id = {
        item.candidate_id: item for item in previous.resulting_dispositions
    }
    result: list[CandidateRoundInput] = []
    for old in previous.candidates:
        disposition = disposition_by_id[old.candidate_id]
        decision = decision_by_id.get(old.candidate_id)
        if old.activity != CandidateActivity.ACTIVE:
            result.append(CandidateRoundInput(
                candidate_id=old.candidate_id,
                activity=old.activity,
                decision_count=old.decision_count,
                nonterminal_acquisition_count=old.nonterminal_acquisition_count,
                completed_nonterminal_action_ids=(
                    old.completed_nonterminal_action_ids
                ),
                router_state_sha256=old.router_state_sha256,
                history_sha256=old.history_sha256,
                policy_trajectory_head_sha256=(
                    disposition.policy_trajectory_head_sha256
                ),
                bound_router_decision=None,
                action_catalog=_catalog(),
            ))
            continue
        assert decision is not None
        route_action = COLLECTION_ACTION_ROUTE[decision.chosen_action_id]
        acquisition = route_action not in {
            RouteAction.ACCEPT,
            RouteAction.REJECT,
            RouteAction.ABSTAIN,
        }
        completed = tuple(sorted((
            *old.completed_nonterminal_action_ids,
            *((decision.chosen_action_id,) if acquisition else ()),
        )))
        if acquisition:
            assert old.bound_router_decision is not None
            assert decision.logged_policy_decision.acquisition_id is not None
            safe_state = _append_typed_result(
                old.bound_router_decision.router_state,
                old.bound_router_decision,
                chosen_action_id=decision.chosen_action_id,
                acquisition_id=decision.logged_policy_decision.acquisition_id,
                status=status,
            )
            bound = BoundRouterDecision.from_router_state(safe_state)
            router_sha = safe_state.canonical_digest()
            history_sha = safe_state.history_sha256()
        else:
            bound = None
            router_sha = old.router_state_sha256
            history_sha = old.history_sha256
        result.append(CandidateRoundInput(
            candidate_id=old.candidate_id,
            activity=disposition.activity,
            decision_count=old.decision_count + 1,
            nonterminal_acquisition_count=(
                old.nonterminal_acquisition_count + int(acquisition)
            ),
            completed_nonterminal_action_ids=completed,
            router_state_sha256=router_sha,
            history_sha256=history_sha,
            policy_trajectory_head_sha256=(
                disposition.policy_trajectory_head_sha256
            ),
            bound_router_decision=bound,
            action_catalog=_catalog(),
        ))
    return tuple(result)


def _complete_chain(
    bindings: SchedulerBindings,
    task_id: str,
    *,
    result_status: EvidenceStatus = EvidenceStatus.INCONCLUSIVE,
) -> tuple[TaskRoundDecision, ...]:
    chain: list[TaskRoundDecision] = []
    inputs = _initial_inputs(bindings, task_id)
    for round_index in range(5):
        current = build_task_round_decision(
            bindings=bindings,
            task_id=task_id,
            scheduled_at=_timestamp(round_index),
            candidates=inputs,
            prior_rounds=chain,
        )
        chain.append(current)
        if current.completes_candidate_chains:
            return tuple(chain)
        inputs = _successor_inputs(current, status=result_status)
    raise AssertionError("five-round ceiling did not terminate every candidate")


def _multi_round_chain(
    bindings: SchedulerBindings,
) -> tuple[TaskRoundDecision, ...]:
    for task_id in bindings.frame.task_ids:
        chain = _complete_chain(bindings, task_id)
        if len(chain) > 1:
            return chain
    raise AssertionError("frozen draws unexpectedly terminated all tasks in round zero")


def test_exact_frame_rng_order_and_repository_bindings(
    bindings: SchedulerBindings,
) -> None:
    assert len(COLLECTION_ACTION_IDS) == 9
    assert len(POLICY_ACTION_IDS) == 7
    assert set(COLLECTION_ACTION_IDS) - set(POLICY_ACTION_IDS) == {
        "hardening_curator",
        "static_bootstrap",
    }
    assert len(bindings.frame.task_ids) == 22
    assert sum(len(items) for _, items in bindings.frame.tasks) == 66
    assert bindings.frame.source_feature_freeze_sha256 == (
        EXPECTED_SOURCE_FEATURE_FREEZE["sha256"]
    )
    order = derive_task_order(bindings.frame.task_ids)
    assert set(order) == set(bindings.frame.task_ids)
    assert tuple(len(batch) for batch in derive_task_batches(bindings.frame.task_ids)) == (
        4,
        4,
        4,
        4,
        4,
        2,
    )

    counter = 17
    digest = hashlib.sha256(
        bytes.fromhex(ACTION_DRAW_SEED_SHA256)
        + b"\x00"
        + ACTION_DRAW_DOMAIN.encode()
        + b"\x00"
        + counter.to_bytes(8, "big")
    ).digest()
    expected_draw = (int.from_bytes(digest[:8], "big") >> 11) / float(1 << 53)
    assert derive_action_draw(counter) == expected_draw

    with pytest.raises(ValueError, match="repository file"):
        replace(bindings, collection_policy_sha256="a" * 64)


def test_round_is_exact_frame_bound_deterministic_and_strict_json(
    bindings: SchedulerBindings,
) -> None:
    task_id = bindings.frame.task_ids[0]
    candidates = _initial_inputs(bindings, task_id)
    first = build_task_round_decision(
        bindings=bindings,
        task_id=task_id,
        scheduled_at=_timestamp(0),
        candidates=candidates,
    )
    repeated = build_task_round_decision(
        bindings=bindings,
        task_id=task_id,
        scheduled_at=_timestamp(0),
        candidates=tuple(reversed(candidates)),
    )
    assert first.to_dict() == repeated.to_dict()
    assert first.candidate_order == derive_candidate_order(
        bindings.frame.candidate_ids_for(task_id)
    )
    assert first.frame_manifest_sha256 == bindings.frame.manifest_sha256
    assert first.protocol_sha256 == bindings.protocol_sha256
    assert first.router_source_sha256 == ROUTER_SOURCE_SHA256
    assert first.router_policy_config_sha256 == ROUTER_POLICY_CONFIG_SHA256
    assert all(
        item.candidate_scheduler_probability == 1.0
        for item in first.scheduled_decisions
    )
    assert first.task_trajectory_action_log_propensities == tuple(
        item.chosen_log_action_propensity for item in first.scheduled_decisions
    )
    assert first.task_trajectory_log_probability == math.fsum(
        first.task_trajectory_action_log_propensities
    )

    restored = load_task_round_decision(
        io.StringIO(strict_json_dumps(first.to_dict())),
        bindings=bindings,
    )
    assert restored == first
    unknown = first.to_dict()
    unknown["hosted_outcome"] = True
    with pytest.raises(ValueError, match="fields differ"):
        load_task_round_decision(
            io.StringIO(strict_json_dumps(unknown)),
            bindings=bindings,
        )
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        load_task_round_decision(
            io.StringIO('{"schema_version":"x","schema_version":"y"}'),
            bindings=bindings,
        )


def test_router_projection_requires_safe_preimage_and_exact_frozen_source(
    bindings: SchedulerBindings,
) -> None:
    task_id = bindings.frame.task_ids[0]
    candidate_id = bindings.frame.candidate_ids_for(task_id)[0]
    state = _initial_state(task_id, candidate_id)
    assert state.evidence_history == ()
    assert state.route_history == ()
    assert len(state.bootstrap_history) == 1
    bound = BoundRouterDecision.from_router_state(state)
    assert bound.router_state_sha256 == state.canonical_digest()
    assert bound.policy_version == "conservative-v1"

    forged = RouteDecision(
        action=RouteAction.ACCEPT,
        policy_version="evil-v99",
        candidate_risk=0.0,
        verifier_risk=0.0,
        expected_information_gain=0.0,
        estimated_relative_cost=0.0,
        reasons=("forged",),
        terminal=True,
    )
    with pytest.raises(ValueError, match="recomputation"):
        BoundRouterDecision.from_route_decision(forged, router_state=state)
    with pytest.raises(ValueError, match="source differs"):
        replace(bound, router_source_sha256="f" * 64)

    unsafe = state.to_dict()
    unsafe["hosted_outcome"] = "resolved"
    with pytest.raises(ValueError, match="unknown fields"):
        RouterStateView.from_dict(unsafe)
    label_state = _append_typed_result(
        state,
        bound,
        chosen_action_id="semantic_primary",
        acquisition_id=_acquisition_id(f"{task_id}:{candidate_id}:semantic"),
        status=EvidenceStatus.INCONCLUSIVE,
    )
    label_source = label_state.to_dict()
    label_source["evidence_history"][0]["source"] = "candidate_correct"
    with pytest.raises(ValueError, match="privileged or hosted label"):
        BoundRouterDecision.from_router_state(RouterStateView.from_dict(label_source))


def test_label_reason_repeat_spec_and_candidate_history_fail_closed(
    bindings: SchedulerBindings,
) -> None:
    task_id = bindings.frame.task_ids[0]
    candidate_id = bindings.frame.candidate_ids_for(task_id)[0]
    catalog = _catalog()
    leaked = tuple(
        replace(item, availability_reason="candidate_correct")
        if item.action_id == "semantic_primary"
        else item
        for item in catalog
    )
    with pytest.raises(ValueError, match="privileged or hosted label"):
        _candidate(task_id, candidate_id, catalog=leaked)


def test_round_zero_requires_three_distinct_candidate_bootstrap_receipts(
    bindings: SchedulerBindings,
) -> None:
    task_id = bindings.frame.task_ids[0]
    candidate_ids = bindings.frame.candidate_ids_for(task_id)
    candidate_id = candidate_ids[0]
    catalog = _catalog()
    first = _initial_state(task_id, candidate_id)
    with pytest.raises(ValueError, match="one deterministic static bootstrap"):
        _candidate(
            task_id,
            candidate_ids[0],
            state=replace(first, bootstrap_history=()),
        )

    states = [
        _initial_state(task_id, candidate_id)
        for candidate_id in candidate_ids
    ]
    duplicated_step = replace(
        states[1].bootstrap_history[0],
        receipt_sha256=states[0].bootstrap_history[0].receipt_sha256,
    )
    states[1] = replace(states[1], bootstrap_history=(duplicated_step,))
    inputs = tuple(
        _candidate(task_id, candidate_id, state=state)
        for candidate_id, state in zip(candidate_ids, states)
    )
    with pytest.raises(ValueError, match="receipt identities must be candidate-distinct"):
        build_task_round_decision(
            bindings=bindings,
            task_id=task_id,
            scheduled_at=_timestamp(0),
            candidates=inputs,
        )

    primary_spec = next(
        item.action_spec_sha256 for item in catalog if item.action_id == "full_primary"
    )
    same_repeat = tuple(
        replace(item, action_spec_sha256=primary_spec)
        if item.action_id == "full_repeat"
        else item
        for item in catalog
    )
    with pytest.raises(ValueError, match="distinct fresh-worktree action spec"):
        _candidate(task_id, candidate_id, catalog=same_repeat)

    with pytest.raises(ValueError, match="active candidate decisions"):
        _candidate(
            task_id,
            candidate_id,
            decisions=1,
            acquisitions=0,
            policy_head_sha256="1" * 64,
        )
    with pytest.raises(ValueError, match="exactly one terminal decision"):
        _candidate(
            task_id,
            candidate_id,
            activity=CandidateActivity.ABSTAINED,
            decisions=2,
            acquisitions=0,
            policy_head_sha256="1" * 64,
        )


def test_frame_candidate_substitution_and_typed_successor_rejected(
    bindings: SchedulerBindings,
) -> None:
    task_id = bindings.frame.task_ids[0]
    other_task = bindings.frame.task_ids[1]
    inputs = list(_initial_inputs(bindings, task_id))
    replacement = bindings.frame.candidate_ids_for(other_task)[0]
    inputs[0] = _candidate(task_id, replacement)
    with pytest.raises(ValueError, match="frozen task mapping"):
        build_task_round_decision(
            bindings=bindings,
            task_id=task_id,
            scheduled_at=_timestamp(0),
            candidates=inputs,
        )

    chain = _multi_round_chain(bindings)
    first = chain[0]
    valid_successors = list(_successor_inputs(first))
    active_ids = {
        item.candidate_id
        for item in first.resulting_dispositions
        if item.activity == CandidateActivity.ACTIVE
    }
    target_index = next(
        index
        for index, item in enumerate(valid_successors)
        if item.candidate_id in active_ids
    )
    target = valid_successors[target_index]
    reset_state = _initial_state(first.task_id, target.candidate_id)
    with pytest.raises(ValueError, match="randomized route/evidence"):
        valid_successors[target_index] = replace(
            target,
            router_state_sha256=reset_state.canonical_digest(),
            history_sha256=reset_state.history_sha256(),
            bound_router_decision=BoundRouterDecision.from_router_state(reset_state),
        )
        build_task_round_decision(
            bindings=bindings,
            task_id=first.task_id,
            scheduled_at=_timestamp(1),
            candidates=valid_successors,
            prior_rounds=(first,),
        )


def test_chain_uses_one_global_fsum_and_binds_policy_heads(
    bindings: SchedulerBindings,
) -> None:
    chain = _multi_round_chain(bindings)
    validate_task_round_chain(chain, bindings=bindings)
    flat_terms = tuple(
        decision.chosen_log_action_propensity
        for round_decision in chain
        for decision in round_decision.scheduled_decisions
    )
    assert chain[-1].task_trajectory_action_log_propensities == flat_terms
    assert chain[-1].task_trajectory_log_probability == math.fsum(flat_terms)
    assert chain[-1].task_trajectory_probability == math.exp(math.fsum(flat_terms))
    for previous, current in zip(chain, chain[1:]):
        expected_heads = {
            item.candidate_id: item.policy_trajectory_head_sha256
            for item in previous.resulting_dispositions
        }
        assert all(
            item.policy_trajectory_head_sha256 == expected_heads[item.candidate_id]
            for item in current.candidates
        )


def test_scheduler_policy_log_and_corpus_use_exact_join_identities(
    bindings: SchedulerBindings,
) -> None:
    chain = _multi_round_chain(bindings)
    decisions_by_candidate: dict[str, list[LoggedPolicyDecision]] = {
        candidate_id: [] for candidate_id in chain[0].candidate_order
    }
    events_by_candidate: dict[str, list[PairedEvidence]] = {
        candidate_id: [] for candidate_id in chain[0].candidate_order
    }
    adjudication = EvidenceValidityAdjudication(
        validity=EvidenceValidity.INDETERMINATE,
        source="prospective-joinability-fixture",
        protocol_version="v1",
        blinded=True,
        annotator_count=2,
        agreement=1.0,
    )

    for round_position, round_decision in enumerate(chain):
        state_by_candidate = {
            item.candidate_id: item for item in round_decision.candidates
        }
        disposition_by_candidate = {
            item.candidate_id: item
            for item in round_decision.resulting_dispositions
        }
        for scheduled in round_decision.scheduled_decisions:
            state = state_by_candidate[scheduled.candidate_id]
            logged = scheduled.logged_policy_decision
            decisions_by_candidate[scheduled.candidate_id].append(logged)
            assert state.bound_router_decision is not None
            assert logged.router_state == state.bound_router_decision.router_state
            assert logged.action_catalog == state.action_catalog
            assert logged.decision_sha256 == scheduled.selection_identity_sha256
            assert logged.trajectory_id.startswith("traj-")
            assert logged.trajectory_head_sha256 == (
                disposition_by_candidate[
                    scheduled.candidate_id
                ].policy_trajectory_head_sha256
            )

            if logged.terminal:
                assert logged.acquisition_id is None
                continue
            assert logged.acquisition_id is not None
            assert round_position + 1 < len(chain)
            successor = next(
                item
                for item in chain[round_position + 1].candidates
                if item.candidate_id == scheduled.candidate_id
            )
            assert successor.bound_router_decision is not None
            observation = (
                successor.bound_router_decision.router_state.evidence_history[-1]
            )
            assert observation.acquisition_id == logged.acquisition_id
            event = bridge_logged_policy_observation(
                event_id=f"evt-{logged.decision_id.removeprefix('dec-')}",
                policy_decision=logged,
                observation=observation,
                validity_adjudication=adjudication,
                collected_at=chain[round_position + 1].scheduled_at,
                prior_observations=events_by_candidate[scheduled.candidate_id],
            )
            assert event.decision is logged
            assert event.to_dict()["decision"] == logged.to_dict()
            events_by_candidate[scheduled.candidate_id].append(event)

    for candidate_id in chain[0].candidate_order:
        validate_policy_decision_chain(decisions_by_candidate[candidate_id])


def test_selection_requires_complete_chronological_genesis_chain(
    bindings: SchedulerBindings,
) -> None:
    chain = _multi_round_chain(bindings)
    assert chain[-1].completes_candidate_chains
    selection = build_task_selection_decision(
        chain,
        bindings=bindings,
        scheduled_at=_timestamp(10),
    )
    assert selection.disposition == TaskSelectionDisposition.ABSTAIN
    assert selection.selected_candidate_id is None
    assert selection.round_decision_sha256s == tuple(
        item.decision_sha256 for item in chain
    )
    validate_task_trajectory(chain, selection, bindings=bindings)
    restored = load_task_selection_decision(
        io.StringIO(strict_json_dumps(selection.to_dict())),
        rounds=chain,
        bindings=bindings,
    )
    assert restored == selection

    with pytest.raises(ValueError, match="start at round zero"):
        build_task_selection_decision(
            chain[1:],
            bindings=bindings,
            scheduled_at=_timestamp(10),
        )
    with pytest.raises(ValueError, match="cannot predate"):
        build_task_selection_decision(
            chain,
            bindings=bindings,
            scheduled_at="2020-01-01T00:00:00.000000Z",
        )


def test_mechanics_policy_skips_unavailable_semantic_and_exposes_paired_terminals(
    bindings: SchedulerBindings,
) -> None:
    task_id = bindings.frame.task_ids[0]
    candidate_id = bindings.frame.candidate_ids_for(task_id)[0]
    initial = _initial_state(task_id, candidate_id)
    semantic_unavailable = tuple(
        replace(
            item,
            available=False,
            availability_reason="semantic_binding_unavailable",
        )
        if item.action_id == "semantic_primary"
        else item
        for item in _catalog()
    )
    fallback = _build_candidate_state(_candidate(
        task_id,
        candidate_id,
        state=initial,
        catalog=semantic_unavailable,
    ))
    assert fallback.bound_router_decision is not None
    assert fallback.bound_router_decision.action == RouteAction.RUN_SEMANTIC
    assert fallback.preferred_action_id == "targeted_primary"

    for status, expected_action in (
        (EvidenceStatus.SUPPORTS_CORRECT, "accept"),
        (EvidenceStatus.SUPPORTS_INCORRECT, "reject"),
    ):
        state = initial
        for action_id in ("full_primary", "full_repeat"):
            bound = BoundRouterDecision.from_router_state(state)
            state = _append_typed_result(
                state,
                bound,
                chosen_action_id=action_id,
                acquisition_id=_acquisition_id(
                    f"paired:{candidate_id}:{action_id}:{status.value}"
                ),
                status=status,
            )
        candidate = _build_candidate_state(_candidate(
            task_id,
            candidate_id,
            decisions=2,
            acquisitions=2,
            completed=("full_primary", "full_repeat"),
            state=state,
        ))
        by_id = {item.action_id: item for item in candidate.action_catalog}
        assert candidate.preferred_action_id == expected_action
        assert by_id[expected_action].available is True

    error_state = initial
    for action_id, status in (
        ("full_primary", EvidenceStatus.ERROR),
        ("full_repeat", EvidenceStatus.SUPPORTS_INCORRECT),
    ):
        bound = BoundRouterDecision.from_router_state(error_state)
        error_state = _append_typed_result(
            error_state,
            bound,
            chosen_action_id=action_id,
            acquisition_id=_acquisition_id(f"error:{candidate_id}:{action_id}"),
            status=status,
        )
    error_candidate = _build_candidate_state(_candidate(
        task_id,
        candidate_id,
        decisions=2,
        acquisitions=2,
        completed=("full_primary", "full_repeat"),
        state=error_state,
    ))
    error_by_id = {
        item.action_id: item for item in error_candidate.action_catalog
    }
    assert error_by_id["reject"].available is False


def test_complete_ledger_rejects_fork_replay_and_counter_reuse(
    bindings: SchedulerBindings,
) -> None:
    all_rounds: list[TaskRoundDecision] = []
    selections: list[TaskSelectionDecision] = []
    chains: dict[str, tuple[TaskRoundDecision, ...]] = {}
    for task_id in bindings.frame.task_ids:
        chain = _complete_chain(bindings, task_id)
        chains[task_id] = chain
        all_rounds.extend(chain)
        selections.append(build_task_selection_decision(
            chain,
            bindings=bindings,
            scheduled_at=_timestamp(10),
        ))
    validate_complete_study_ledger(
        all_rounds,
        selections,
        bindings=bindings,
    )
    counters = [
        decision.action_draw_counter
        for item in all_rounds
        for decision in item.scheduled_decisions
    ]
    assert len(counters) == len(set(counters))

    fork_task = next(task for task, chain in chains.items() if len(chain) > 1)
    first = chains[fork_task][0]
    alternate = build_task_round_decision(
        bindings=bindings,
        task_id=fork_task,
        scheduled_at=_timestamp(1),
        candidates=_successor_inputs(first, status=EvidenceStatus.ERROR),
        prior_rounds=(first,),
    )
    with pytest.raises(ValueError, match="replay or task-round fork"):
        validate_complete_study_ledger(
            [*all_rounds, alternate],
            selections,
            bindings=bindings,
        )


def test_nonfinite_and_selection_chain_tampering_fail_closed(
    bindings: SchedulerBindings,
) -> None:
    chain = _multi_round_chain(bindings)
    selection = build_task_selection_decision(
        chain,
        bindings=bindings,
        scheduled_at=_timestamp(10),
    )
    tampered = selection.to_dict()
    tampered["round_decision_sha256s"] = list(
        reversed(tampered["round_decision_sha256s"])
    )
    with pytest.raises(ValueError):
        load_task_selection_decision(
            io.StringIO(strict_json_dumps(tampered)),
            rounds=chain,
            bindings=bindings,
        )

    encoded = strict_json_dumps(chain[0].to_dict())
    encoded = encoded.replace(
        f'"round_joint_probability":{chain[0].round_joint_probability}',
        '"round_joint_probability":NaN',
    )
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        load_task_round_decision(
            io.StringIO(encoded),
            bindings=bindings,
        )
