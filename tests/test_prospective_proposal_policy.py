"""Adversarial tests for the frozen fallible-sensor proposal policy."""

from __future__ import annotations

import hashlib

import pytest

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
    RouterRouteStep,
    RouterStateView,
)
from experiments.prospective_pilot.proposal_policy import (
    ABSTAIN_ACTION_ID,
    ACCEPT_ACTION_ID,
    FULL_PRIMARY_ACTION_ID,
    FULL_REPEAT_ACTION_ID,
    REJECT_ACTION_ID,
    SEMANTIC_ACTION_ID,
    TARGETED_ACTION_ID,
    preferred_action_id,
    terminal_proposal,
)

_CANDIDATE_ID = "sha256:" + "c" * 64


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _route(action: RouteAction, *, version: str) -> RouteDecision:
    return RouteDecision(
        action=action,
        policy_version=version,
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.5,
        estimated_relative_cost=0.2,
        reasons=(
            "deterministic_bootstrap" if action == RouteAction.RUN_STATIC else "truth-free fixture",
        ),
        terminal=False,
    )


def _observation(
    kind: EvidenceKind,
    status: EvidenceStatus,
    *,
    suffix: str,
) -> EvidenceObservation:
    return EvidenceObservation(
        kind=kind,
        status=status,
        source=f"proposal-fixture-{suffix}",
        source_version="v1",
        acquisition_id="acq-" + _digest(suffix)[:32],
        cost=EvidenceCost(wall_seconds=1.0),
    )


def _state(*full_statuses: EvidenceStatus) -> RouterStateView:
    bootstrap_route = _route(RouteAction.RUN_STATIC, version="bootstrap-v1")
    bootstrap_observation = _observation(
        EvidenceKind.STATIC,
        EvidenceStatus.INCONCLUSIVE,
        suffix="bootstrap",
    )
    bootstrap = BootstrapHistoryStep(
        receipt_sha256=_digest("candidate-bound-static-receipt"),
        route=RouterRouteStep.from_route_decision(bootstrap_route),
        observation=bootstrap_observation,
    )
    randomized_routes = tuple(
        _route(RouteAction.RUN_FULL, version=f"full-{index}-v1")
        for index, _ in enumerate(full_statuses)
    )
    randomized_evidence = tuple(
        _observation(
            EvidenceKind.FULL_EXECUTION,
            status,
            suffix=f"full-{index}",
        )
        for index, status in enumerate(full_statuses)
    )
    manifest = ValidityManifest(
        instance_id="owner__repo-1",
        candidate_id=_CANDIDATE_ID,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(
            language="python",
            files_changed=2,
            lines_changed=20,
            targeted_execution_available=True,
            full_execution_available=True,
        ),
        provenance={"repository": "opaque/repository"},
        evidence=[bootstrap_observation, *randomized_evidence],
        route_history=[bootstrap_route, *randomized_routes],
    )
    return RouterStateView.from_manifest(
        manifest,
        bootstrap_history=(bootstrap,),
    )


def _catalog(*, semantic_available: bool) -> tuple[ActionOffer, ...]:
    definitions = (
        (ABSTAIN_ACTION_ID, RouteAction.ABSTAIN, None, True),
        (ACCEPT_ACTION_ID, RouteAction.ACCEPT, None, True),
        (FULL_PRIMARY_ACTION_ID, RouteAction.RUN_FULL, EvidenceKind.FULL_EXECUTION, True),
        (FULL_REPEAT_ACTION_ID, RouteAction.RUN_FULL, EvidenceKind.FULL_EXECUTION, True),
        (REJECT_ACTION_ID, RouteAction.REJECT, None, True),
        (
            SEMANTIC_ACTION_ID,
            RouteAction.RUN_SEMANTIC,
            EvidenceKind.SEMANTIC,
            semantic_available,
        ),
        (
            TARGETED_ACTION_ID,
            RouteAction.RUN_TARGETED,
            EvidenceKind.TARGETED_EXECUTION,
            True,
        ),
    )
    return tuple(
        ActionOffer(
            action_id=action_id,
            route_action=action,
            evidence_kind=kind,
            adapter_id="terminal" if kind is None else f"adapter-{action_id}",
            adapter_version="v1",
            action_spec_sha256=_digest(f"spec:{action_id}"),
            available=available,
            availability_reason="fixture_available" if available else "fixture_unavailable",
            expected_cost=EvidenceCost() if kind is None else EvidenceCost(wall_seconds=1.0),
        )
        for action_id, action, kind, available in definitions
    )


def test_unavailable_semantic_falls_through_to_targeted() -> None:
    proposal = terminal_proposal(
        _state(),
        completed_nonterminal_action_ids=(),
    )
    assert proposal.action_id is None
    assert (
        preferred_action_id(
            router_action=RouteAction.RUN_SEMANTIC,
            action_catalog=_catalog(semantic_available=False),
            proposal=proposal,
        )
        == TARGETED_ACTION_ID
    )
    assert (
        preferred_action_id(
            router_action=RouteAction.RUN_SEMANTIC,
            action_catalog=_catalog(semantic_available=True),
            proposal=proposal,
        )
        == SEMANTIC_ACTION_ID
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (EvidenceStatus.SUPPORTS_CORRECT, ACCEPT_ACTION_ID),
        (EvidenceStatus.SUPPORTS_INCORRECT, REJECT_ACTION_ID),
    ],
)
def test_two_concordant_full_executions_expose_a_fallible_terminal_proposal(
    status: EvidenceStatus,
    expected: str,
) -> None:
    state = _state(status, status)
    proposal = terminal_proposal(
        state,
        completed_nonterminal_action_ids=(
            FULL_PRIMARY_ACTION_ID,
            FULL_REPEAT_ACTION_ID,
        ),
    )
    assert proposal.action_id == expected
    assert (
        preferred_action_id(
            router_action=RouteAction.ABSTAIN,
            action_catalog=_catalog(semantic_available=False),
            proposal=proposal,
        )
        == expected
    )


@pytest.mark.parametrize(
    "statuses",
    [
        (EvidenceStatus.ERROR, EvidenceStatus.SUPPORTS_INCORRECT),
        (EvidenceStatus.UNAVAILABLE, EvidenceStatus.SUPPORTS_INCORRECT),
        (EvidenceStatus.INCONCLUSIVE, EvidenceStatus.SUPPORTS_INCORRECT),
        (EvidenceStatus.SUPPORTS_CORRECT, EvidenceStatus.SUPPORTS_INCORRECT),
    ],
)
def test_error_unavailable_inconclusive_or_disagreement_never_rejects(
    statuses: tuple[EvidenceStatus, EvidenceStatus],
) -> None:
    proposal = terminal_proposal(
        _state(*statuses),
        completed_nonterminal_action_ids=(
            FULL_PRIMARY_ACTION_ID,
            FULL_REPEAT_ACTION_ID,
        ),
    )
    assert proposal.action_id is None
    assert proposal.action_id != REJECT_ACTION_ID
