"""Adversarial contract tests for write-ahead live policy decisions."""

from __future__ import annotations

import hashlib
import io
from dataclasses import replace
from math import fsum

import pytest

from bench_cleanser.verification._io import strict_json_dumps
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
    GENESIS_TRAJECTORY_HEAD_SHA256,
    POLICY_DECISION_SCHEMA_VERSION,
    ROUTER_STATE_SCHEMA_VERSION,
    ActionOffer,
    BehaviorProbability,
    BootstrapHistoryStep,
    LoggedPolicyDecision,
    RouterRouteStep,
    RouterStateView,
    canonical_action_spec_sha256,
    load_logged_policy_decision,
    preferred_uniform_behavior_distribution,
    sample_behavior_action,
    validate_policy_decision_chain,
)

_CANDIDATE_SHA256 = "c" * 64
_CANDIDATE_ID = f"sha256:{_CANDIDATE_SHA256}"
_ACTION_KIND = {
    RouteAction.RUN_STATIC: EvidenceKind.STATIC,
    RouteAction.RUN_SEMANTIC: EvidenceKind.SEMANTIC,
    RouteAction.RUN_TARGETED: EvidenceKind.TARGETED_EXECUTION,
    RouteAction.RUN_FULL: EvidenceKind.FULL_EXECUTION,
    RouteAction.HARDEN_ORACLE: EvidenceKind.ORACLE_HARDENING,
}
_TERMINAL = {RouteAction.ACCEPT, RouteAction.REJECT, RouteAction.ABSTAIN}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _route(action: RouteAction) -> RouteDecision:
    return RouteDecision(
        action=action,
        policy_version="fixture-route-v1",
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.6,
        estimated_relative_cost=0.2,
        reasons=(
            "deterministic_bootstrap"
            if action == RouteAction.RUN_STATIC
            else "fixture prior route",
        ),
    )


def _manifest(
    *,
    routes: tuple[RouteDecision, ...] = (),
    evidence: tuple[EvidenceObservation, ...] = (),
) -> ValidityManifest:
    return ValidityManifest(
        instance_id="owner__repo-1",
        candidate_id=_CANDIDATE_ID,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(
            language="python",
            files_changed=2,
            lines_changed=12,
            oracle_hardening_available=True,
        ),
        provenance={
            "dataset_revision": "fixture-v1",
            "repository": "owner/repo",
            "base_commit": "a" * 40,
            "candidate_patch_sha256": _CANDIDATE_SHA256,
            "risk_profile_version": "fixture-v1",
        },
        evidence=list(evidence),
        route_history=list(routes),
    )


def _bootstrap_state() -> tuple[RouterStateView, BootstrapHistoryStep]:
    route = _route(RouteAction.RUN_STATIC)
    observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source="fixture-bootstrap",
        source_version="v1",
        acquisition_id="acq-" + "b" * 32,
        cost=EvidenceCost(wall_seconds=1.0),
    )
    step = BootstrapHistoryStep(
        receipt_sha256=_sha("candidate-bound-bootstrap-receipt"),
        route=RouterRouteStep.from_route_decision(route),
        observation=observation,
    )
    state = RouterStateView.from_manifest(
        _manifest(routes=(route,), evidence=(observation,)),
        bootstrap_history=(step,),
    )
    return state, step


def _catalog(
    *,
    unavailable: set[RouteAction] | None = None,
) -> tuple[ActionOffer, ...]:
    unavailable = unavailable or set()
    offers = []
    for action in RouteAction:
        terminal = action in _TERMINAL
        offers.append(
            ActionOffer(
                action_id=action.value,
                route_action=action,
                evidence_kind=None if terminal else _ACTION_KIND[action],
                adapter_id="terminal-disposition" if terminal else f"adapter-{action.value}",
                adapter_version="v1",
                action_spec_sha256=canonical_action_spec_sha256(
                    {
                        "action": action.value,
                        "adapter_version": "v1",
                    }
                ),
                available=action not in unavailable,
                availability_reason=(
                    "fixture unavailable" if action in unavailable else "fixture available"
                ),
                expected_cost=(
                    EvidenceCost() if terminal else EvidenceCost(wall_seconds=1.0, usd=0.01)
                ),
            )
        )
    return tuple(sorted(offers, key=lambda item: item.action_id))


def _distribution(
    catalog: tuple[ActionOffer, ...],
) -> tuple[BehaviorProbability, ...]:
    available = [item for item in catalog if item.available]
    probability = 1.0 / len(available)
    return tuple(
        BehaviorProbability(action_id=item.action_id, propensity=probability) for item in available
    )


def _draw_for(
    distribution: tuple[BehaviorProbability, ...],
    action_id: str,
) -> float:
    lower = 0.0
    for item in distribution:
        if item.action_id == action_id:
            return lower + item.propensity / 2.0
        lower += item.propensity
    raise AssertionError(f"missing action {action_id}")


def _logged(
    state: RouterStateView,
    *,
    chosen_action_id: str = RouteAction.RUN_STATIC.value,
    prior_head: str = GENESIS_TRAJECTORY_HEAD_SHA256,
    trajectory_id: str = "trajectory-1",
    decided_at: str = "2026-07-12T01:02:03.000000Z",
    catalog: tuple[ActionOffer, ...] | None = None,
    distribution: tuple[BehaviorProbability, ...] | None = None,
) -> LoggedPolicyDecision:
    action_catalog = catalog or _catalog()
    behavior = distribution or _distribution(action_catalog)
    chosen_offer = next(item for item in action_catalog if item.action_id == chosen_action_id)
    step = len(state.evidence_history)
    return LoggedPolicyDecision(
        trajectory_id=trajectory_id,
        decision_id=f"dec-{step + 1:032x}",
        acquisition_id=(None if chosen_offer.route_action in _TERMINAL else f"acq-{step + 1:032x}"),
        decision_step=step,
        decided_at=decided_at,
        instance_id=state.instance_id,
        candidate_id=state.candidate_id,
        manifest_sha256=state.source_manifest_sha256,
        history_sha256=state.history_sha256(),
        router_state_sha256=state.canonical_digest(),
        prior_trajectory_head_sha256=prior_head,
        policy_id="fixture-policy",
        policy_version="v1",
        policy_code_config_sha256=_sha("fixture policy code and config"),
        action_catalog=action_catalog,
        behavior_distribution=behavior,
        chosen_action_id=chosen_action_id,
        chosen_propensity=next(
            item.propensity for item in behavior if item.action_id == chosen_action_id
        ),
        selection_reason_code="fixture-sampled-action",
        sampler_id="inverse-cdf",
        sampler_version="v1",
        sampler_draw=_draw_for(behavior, chosen_action_id),
        router_state=state,
    )


def test_decision_round_trips_with_stable_hashes_and_full_catalog() -> None:
    state = RouterStateView.from_manifest(_manifest())
    decision = _logged(state)

    restored = load_logged_policy_decision(io.StringIO(strict_json_dumps(decision.to_dict())))

    assert restored.to_dict() == decision.to_dict()
    assert restored.canonical_digest() == decision.decision_sha256
    assert restored.schema_version == POLICY_DECISION_SCHEMA_VERSION
    assert restored.router_state.schema_version == ROUTER_STATE_SCHEMA_VERSION
    assert {item.route_action for item in restored.action_catalog} == set(RouteAction)
    assert restored.prior_trajectory_head_sha256 == (GENESIS_TRAJECTORY_HEAD_SHA256)
    assert restored.trajectory_head_sha256 != restored.decision_sha256
    assert restored.terminal is False


def test_bootstrap_is_bound_but_does_not_advance_policy_step_or_head() -> None:
    state, step = _bootstrap_state()
    decision = _logged(
        state,
        chosen_action_id=RouteAction.RUN_SEMANTIC.value,
    )
    restored = load_logged_policy_decision(io.StringIO(strict_json_dumps(decision.to_dict())))

    assert restored.router_state.bootstrap_history == (step,)
    assert restored.router_state.evidence_history == ()
    assert restored.router_state.route_history == ()
    assert restored.decision_step == 0
    assert restored.prior_trajectory_head_sha256 == GENESIS_TRAJECTORY_HEAD_SHA256
    assert restored.acquisition_id != step.observation.acquisition_id
    assert restored.history_sha256 == state.history_sha256()


def test_bootstrap_prefix_and_safe_observation_fail_closed() -> None:
    state, step = _bootstrap_state()
    manifest = _manifest()
    with pytest.raises(ValueError, match="exact manifest prefix"):
        RouterStateView.from_manifest(manifest, bootstrap_history=(step,))

    noncanonical = replace(
        _route(RouteAction.RUN_STATIC),
        reasons=("deterministic static bootstrap",),
    )
    with pytest.raises(ValueError, match="canonical deterministic bootstrap"):
        RouterStateView.from_manifest(
            _manifest(routes=(noncanonical,), evidence=(step.observation,)),
            bootstrap_history=(step,),
        )

    with pytest.raises(ValueError, match="deterministic static"):
        replace(
            step,
            route=RouterRouteStep.from_route_decision(_route(RouteAction.RUN_SEMANTIC)),
        )
    with pytest.raises(ValueError, match="metadata must be stripped"):
        replace(
            step,
            observation=replace(
                step.observation,
                metadata={"runner": "fixture"},
            ),
        )
    duplicated = state.to_dict()
    duplicated["evidence_history"] = [duplicated["bootstrap_history"][0]["observation"]]
    with pytest.raises(ValueError, match="acquisition_id values must be unique"):
        RouterStateView.from_dict(duplicated)


def test_policy_chain_rejects_mutated_bootstrap_receipt() -> None:
    initial, step = _bootstrap_state()
    first = _logged(
        initial,
        chosen_action_id=RouteAction.RUN_SEMANTIC.value,
    )
    semantic_route = _route(RouteAction.RUN_SEMANTIC)
    semantic_observation = EvidenceObservation(
        kind=EvidenceKind.SEMANTIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source="fixture-semantic",
        source_version="v1",
        acquisition_id=first.acquisition_id or "",
        cost=EvidenceCost(wall_seconds=1.0),
    )
    successor = RouterStateView.from_manifest(
        _manifest(
            routes=(_route(RouteAction.RUN_STATIC), semantic_route),
            evidence=(step.observation, semantic_observation),
        ),
        bootstrap_history=(step,),
    )
    mutated = replace(
        successor,
        bootstrap_history=(replace(step, receipt_sha256=_sha("substituted receipt")),),
    )
    second = _logged(
        mutated,
        chosen_action_id=RouteAction.ABSTAIN.value,
        prior_head=first.trajectory_head_sha256,
        decided_at="2026-07-12T01:02:04.000000Z",
    )
    with pytest.raises(ValueError, match="immutable router baseline"):
        validate_policy_decision_chain((first, second))


def test_semantic_action_offer_can_be_selected_as_typed_acquisition() -> None:
    state = RouterStateView.from_manifest(_manifest())
    decision = _logged(
        state,
        chosen_action_id=RouteAction.RUN_SEMANTIC.value,
    )

    assert decision.terminal is False
    assert decision.acquisition_id is not None
    assert decision.chosen_offer.route_action == RouteAction.RUN_SEMANTIC
    assert decision.chosen_offer.evidence_kind == EvidenceKind.SEMANTIC
    assert decision.chosen_offer.adapter_id == "adapter-run_semantic"


def test_router_state_strips_allowlisted_operational_metadata() -> None:
    observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="fixture-static",
        source_version="v1",
        acquisition_id="acq-" + "1" * 32,
        cost=EvidenceCost(wall_seconds=1),
        metadata={
            "runner": "bench-cleanser-acquire",
            "artifact_sha256": "d" * 64,
            "route_provenance": {"route_action": "run_static"},
        },
    )
    state = RouterStateView.from_manifest(
        _manifest(routes=(_route(RouteAction.RUN_STATIC),), evidence=(observation,))
    )

    assert state.evidence_history[0].metadata == {}
    assert state.evidence_history[0].privileged_inputs == ()
    assert state.evidence_history[0].cost.wall_seconds == 1
    assert "reasons" not in state.to_dict()["route_history"][0]
    assert state.history_sha256()


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        (
            _manifest(
                routes=(_route(RouteAction.RUN_STATIC),),
                evidence=(
                    EvidenceObservation(
                        kind=EvidenceKind.STATIC,
                        status=EvidenceStatus.INCONCLUSIVE,
                        source="fixture",
                        acquisition_id="acq-" + "1" * 32,
                        privileged_inputs=("gold_patch",),
                    ),
                ),
            ),
            "privileged evidence",
        ),
        (
            _manifest(
                routes=(_route(RouteAction.RUN_STATIC),),
                evidence=(
                    EvidenceObservation(
                        kind=EvidenceKind.HUMAN_ADJUDICATION,
                        status=EvidenceStatus.SUPPORTS_CORRECT,
                        source="panel",
                        acquisition_id="acq-" + "1" * 32,
                    ),
                ),
            ),
            "human adjudication",
        ),
        (
            _manifest(
                routes=(_route(RouteAction.RUN_STATIC),),
                evidence=(
                    EvidenceObservation(
                        kind=EvidenceKind.STATIC,
                        status=EvidenceStatus.INCONCLUSIVE,
                        source="fixture",
                        acquisition_id="acq-" + "1" * 32,
                        metadata={"gold_patch": "leak"},
                    ),
                ),
            ),
            "may encode privileged data",
        ),
        (
            _manifest(
                routes=(_route(RouteAction.RUN_STATIC),),
                evidence=(
                    EvidenceObservation(
                        kind=EvidenceKind.STATIC,
                        status=EvidenceStatus.INCONCLUSIVE,
                        source="fixture",
                        acquisition_id="acq-" + "1" * 32,
                        metadata={"arbitrary_feature": True},
                    ),
                ),
            ),
            "not allowlisted",
        ),
    ],
)
def test_router_state_fails_closed_on_privileged_or_undeclared_inputs(
    manifest: ValidityManifest,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RouterStateView.from_manifest(manifest)


def test_router_state_rejects_privileged_provenance_and_bad_history_shape() -> None:
    privileged = _manifest()
    privileged.provenance["ground_truth_label"] = "correct"
    with pytest.raises(ValueError, match="privileged truth or outcome"):
        RouterStateView.from_manifest(privileged)

    evidence_without_route = _manifest(
        evidence=(
            EvidenceObservation(
                kind=EvidenceKind.STATIC,
                status=EvidenceStatus.INCONCLUSIVE,
                source="fixture",
                acquisition_id="acq-" + "1" * 32,
            ),
        )
    )
    with pytest.raises(ValueError, match="one-to-one"):
        RouterStateView.from_manifest(evidence_without_route)

    mismatch = _manifest(
        routes=(_route(RouteAction.RUN_FULL),),
        evidence=(
            EvidenceObservation(
                kind=EvidenceKind.STATIC,
                status=EvidenceStatus.INCONCLUSIVE,
                source="fixture",
                acquisition_id="acq-" + "1" * 32,
            ),
        ),
    )
    with pytest.raises(ValueError, match="action/evidence mismatch"):
        RouterStateView.from_manifest(mismatch)

    terminal = _manifest(routes=(replace(_route(RouteAction.RUN_STATIC), terminal=True),))
    with pytest.raises(ValueError, match="terminal route decision"):
        RouterStateView.from_manifest(terminal)


def test_router_state_rejects_values_that_cannot_round_trip_canonically() -> None:
    spaced_provenance = _manifest()
    spaced_provenance.provenance["repository"] = " owner/repo "
    with pytest.raises(ValueError, match="surrounding or control whitespace"):
        RouterStateView.from_manifest(spaced_provenance)

    spaced_language = _manifest()
    spaced_language.risk_profile = replace(
        spaced_language.risk_profile,
        language=" python ",
    )
    with pytest.raises(ValueError, match="surrounding or control whitespace"):
        RouterStateView.from_manifest(spaced_language)

    spaced_source = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source=" fixture-static ",
        acquisition_id="acq-" + "1" * 32,
    )
    with pytest.raises(ValueError, match="surrounding or control whitespace"):
        RouterStateView.from_manifest(
            _manifest(
                routes=(_route(RouteAction.RUN_STATIC),),
                evidence=(spaced_source,),
            )
        )


def test_action_offer_enforces_route_kind_spec_and_terminal_cost() -> None:
    offer = next(item for item in _catalog() if item.route_action == RouteAction.RUN_STATIC)
    with pytest.raises(ValueError, match="incompatible evidence_kind"):
        replace(offer, evidence_kind=EvidenceKind.FULL_EXECUTION)
    with pytest.raises(ValueError, match="64 lowercase"):
        replace(offer, action_spec_sha256="SHA256:" + "a" * 64)

    terminal = next(item for item in _catalog() if item.route_action == RouteAction.ABSTAIN)
    with pytest.raises(ValueError, match="cannot declare evidence_kind"):
        replace(terminal, evidence_kind=EvidenceKind.STATIC)
    with pytest.raises(ValueError, match="zero expected cost"):
        replace(terminal, expected_cost=EvidenceCost(wall_seconds=0.1))

    assert canonical_action_spec_sha256({"b": 2, "a": 1}) == (
        canonical_action_spec_sha256({"a": 1, "b": 2})
    )
    with pytest.raises(ValueError, match="canonical JSON"):
        canonical_action_spec_sha256({"bad": float("nan")})


def test_catalog_requires_unique_complete_actions_and_terminal_support() -> None:
    state = RouterStateView.from_manifest(_manifest())
    catalog = list(_catalog())
    catalog[1] = replace(catalog[1], action_id=catalog[0].action_id)
    with pytest.raises(ValueError, match="duplicate action_id"):
        _logged(state, catalog=tuple(catalog))

    catalog = list(_catalog())
    accept = next(item for item in catalog if item.route_action == RouteAction.ACCEPT)
    catalog.append(replace(accept, action_id="second_accept"))
    catalog = sorted(catalog, key=lambda item: item.action_id)
    with pytest.raises(ValueError, match="terminal RouteAction values"):
        _logged(state, catalog=tuple(catalog))

    missing = tuple(item for item in _catalog() if item.route_action != RouteAction.ACCEPT)
    with pytest.raises(ValueError, match="represent every RouteAction"):
        _logged(state, catalog=missing)

    unavailable_terminal = _catalog(unavailable={RouteAction.ABSTAIN})
    with pytest.raises(ValueError, match="support for abstention"):
        _logged(
            state,
            catalog=unavailable_terminal,
            distribution=_distribution(unavailable_terminal),
        )

    unavailable_profile = _manifest()
    unavailable_profile.risk_profile = replace(
        unavailable_profile.risk_profile,
        full_execution_available=False,
    )
    unavailable_state = RouterStateView.from_manifest(unavailable_profile)
    with pytest.raises(ValueError, match="contradicts the router risk profile"):
        _logged(unavailable_state)


def test_catalog_supports_multiple_concrete_offers_for_one_modality() -> None:
    state = RouterStateView.from_manifest(_manifest())
    catalog = list(_catalog())
    static = next(item for item in catalog if item.route_action == RouteAction.RUN_STATIC)
    catalog.append(
        replace(
            static,
            action_id="run_static_alternate",
            adapter_id="alternate-static-adapter",
            action_spec_sha256=_sha("alternate static intervention"),
        )
    )
    catalog_tuple = tuple(sorted(catalog, key=lambda item: item.action_id))
    decision = _logged(
        state,
        chosen_action_id="run_static_alternate",
        catalog=catalog_tuple,
        distribution=_distribution(catalog_tuple),
    )

    assert decision.chosen_offer.adapter_id == "alternate-static-adapter"
    assert sum(item.route_action == RouteAction.RUN_STATIC for item in decision.action_catalog) == 2


def test_behavior_distribution_matches_availability_normalization_and_draw() -> None:
    state = RouterStateView.from_manifest(_manifest())
    catalog = _catalog(unavailable={RouteAction.RUN_FULL})
    behavior = _distribution(catalog)
    missing = behavior[:-1]
    with pytest.raises(ValueError, match="cover exactly the available actions"):
        _logged(state, catalog=catalog, distribution=missing)

    all_catalog = _catalog()
    malformed_behavior = list(_distribution(all_catalog))
    malformed_behavior[0] = replace(
        malformed_behavior[0],
        propensity=malformed_behavior[0].propensity / 2,
    )
    with pytest.raises(ValueError, match="sum to 1"):
        _logged(
            state,
            catalog=all_catalog,
            distribution=tuple(malformed_behavior),
        )

    decision = _logged(state)
    with pytest.raises(ValueError, match="chosen_propensity does not match"):
        replace(decision, chosen_propensity=decision.chosen_propensity / 2)
    with pytest.raises(ValueError, match="canonical sampler draw"):
        replace(decision, sampler_draw=0.0)
    with pytest.raises(ValueError, match=r"finite and in \(0, 1\]"):
        BehaviorProbability(action_id="run_static", propensity=0.0)

    decision = _logged(state)
    with pytest.raises(ValueError, match="action_catalog must be ordered"):
        replace(decision, action_catalog=tuple(reversed(decision.action_catalog)))
    with pytest.raises(ValueError, match="behavior_distribution must be ordered"):
        replace(
            decision,
            behavior_distribution=tuple(reversed(decision.behavior_distribution)),
        )

    two_action_catalog = _catalog(
        unavailable=set(RouteAction)
        - {
            RouteAction.ABSTAIN,
            RouteAction.ACCEPT,
        }
    )
    tiny_support = (
        BehaviorProbability(action_id=RouteAction.ABSTAIN.value, propensity=1e-15),
        BehaviorProbability(
            action_id=RouteAction.ACCEPT.value,
            propensity=0.999999999999999,
        ),
    )
    tiny_decision = _logged(
        state,
        chosen_action_id=RouteAction.ABSTAIN.value,
        catalog=two_action_catalog,
        distribution=tiny_support,
    )
    with pytest.raises(ValueError, match="chosen_propensity does not match"):
        replace(tiny_decision, chosen_propensity=5e-13)

    with pytest.raises(ValueError, match="canonical inverse-cdf/v1 sampler"):
        replace(decision, sampler_id="another-sampler")


def test_preferred_uniform_policy_has_exact_positive_support_and_canonical_draw() -> None:
    catalog = _catalog(unavailable={RouteAction.HARDEN_ORACLE})
    behavior = preferred_uniform_behavior_distribution(
        catalog,
        preferred_action_id=RouteAction.RUN_STATIC.value,
        exploration_mass=0.5,
    )
    by_action = {item.action_id: item.propensity for item in behavior}

    assert len(behavior) == 7
    assert fsum(by_action.values()) == pytest.approx(1.0)
    assert by_action[RouteAction.RUN_STATIC.value] == pytest.approx(0.5 + 0.5 / 7)
    assert min(by_action.values()) == pytest.approx(1 / 14)
    assert RouteAction.HARDEN_ORACLE.value not in by_action

    state = RouterStateView.from_manifest(_manifest())
    decision = _logged(
        state,
        catalog=catalog,
        distribution=behavior,
        chosen_action_id=RouteAction.RUN_STATIC.value,
    )
    assert decision.behavior_distribution == behavior
    for probability in behavior:
        draw = _draw_for(behavior, probability.action_id)
        assert (
            sample_behavior_action(
                behavior,
                sampler_draw=draw,
            )
            == probability.action_id
        )


@pytest.mark.parametrize("exploration_mass", [True, 0.0, -0.1, 1.1, float("nan")])
def test_preferred_uniform_policy_rejects_invalid_or_zero_exploration(
    exploration_mass: object,
) -> None:
    with pytest.raises(ValueError, match=r"exploration_mass.*\(0, 1\]"):
        preferred_uniform_behavior_distribution(
            _catalog(),
            preferred_action_id=RouteAction.RUN_STATIC.value,
            exploration_mass=exploration_mass,  # type: ignore[arg-type]
        )


def test_preferred_uniform_policy_rejects_catalog_and_sampling_drift() -> None:
    catalog = _catalog(unavailable={RouteAction.RUN_FULL})
    with pytest.raises(ValueError, match="available action"):
        preferred_uniform_behavior_distribution(
            catalog,
            preferred_action_id=RouteAction.RUN_FULL.value,
            exploration_mass=0.5,
        )
    with pytest.raises(ValueError, match="duplicate action_id"):
        preferred_uniform_behavior_distribution(
            (*catalog, catalog[0]),
            preferred_action_id=RouteAction.RUN_STATIC.value,
            exploration_mass=0.5,
        )
    with pytest.raises(ValueError, match="ordered by action_id"):
        preferred_uniform_behavior_distribution(
            tuple(reversed(catalog)),
            preferred_action_id=RouteAction.RUN_STATIC.value,
            exploration_mass=0.5,
        )

    behavior = preferred_uniform_behavior_distribution(
        catalog,
        preferred_action_id=RouteAction.RUN_STATIC.value,
        exploration_mass=0.5,
    )
    malformed = list(behavior)
    malformed[0] = replace(
        malformed[0],
        propensity=malformed[0].propensity / 2,
    )
    with pytest.raises(ValueError, match="sum to 1"):
        sample_behavior_action(tuple(malformed), sampler_draw=0.25)
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        sample_behavior_action(behavior, sampler_draw=1.0)


def test_terminal_and_acquisition_ids_are_mutually_consistent() -> None:
    state = RouterStateView.from_manifest(_manifest())
    terminal = _logged(state, chosen_action_id=RouteAction.ABSTAIN.value)
    assert terminal.acquisition_id is None
    assert terminal.terminal is True

    with pytest.raises(ValueError, match="terminal policy decisions"):
        replace(terminal, acquisition_id="acq-" + "9" * 32)

    acquisition = _logged(state)
    with pytest.raises(ValueError, match="require acquisition_id"):
        replace(acquisition, acquisition_id=None)
    with pytest.raises(ValueError, match="decision_id must be"):
        replace(acquisition, decision_id="post-hoc-id")
    with pytest.raises(ValueError, match="canonical UTC format"):
        replace(acquisition, decided_at="2026-07-12T01:02:03Z")
    with pytest.raises(ValueError, match="canonical identifier"):
        replace(acquisition, selection_reason_code="post hoc success")


def test_reader_rejects_unknown_duplicate_noncanonical_and_tampered_fields() -> None:
    decision = _logged(RouterStateView.from_manifest(_manifest()))
    payload = decision.to_dict()
    payload["post_hoc_reward"] = 1.0
    with pytest.raises(ValueError, match="unknown fields"):
        load_logged_policy_decision(io.StringIO(strict_json_dumps(payload)))

    duplicate = strict_json_dumps(decision.to_dict()).replace(
        '"decision_step":0',
        '"decision_step":0,"decision_step":1',
    )
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        load_logged_policy_decision(io.StringIO(duplicate))

    payload = decision.to_dict()
    payload["decision_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="canonical decision content"):
        load_logged_policy_decision(io.StringIO(strict_json_dumps(payload)))

    payload = decision.to_dict()
    payload["trajectory_head_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="decision chain"):
        load_logged_policy_decision(io.StringIO(strict_json_dumps(payload)))

    nested = decision.to_dict()
    nested["router_state"]["post_hoc_label"] = True
    with pytest.raises(ValueError, match="router_state has unknown fields"):
        load_logged_policy_decision(io.StringIO(strict_json_dumps(nested)))

    object.__setattr__(decision, "trajectory_head_sha256", "a" * 64)
    with pytest.raises(ValueError, match="chain head changed"):
        decision.canonical_digest()


def test_two_step_chain_binds_prior_head_and_realized_acquisition() -> None:
    first_state = RouterStateView.from_manifest(_manifest())
    first = _logged(first_state)
    observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="fixture-static",
        source_version="v1",
        acquisition_id=first.acquisition_id or "",
        metadata={"runner": "bench-cleanser-acquire"},
    )
    second_state = RouterStateView.from_manifest(
        _manifest(
            routes=(_route(RouteAction.RUN_STATIC),),
            evidence=(observation,),
        )
    )
    second = _logged(
        second_state,
        chosen_action_id=RouteAction.ACCEPT.value,
        prior_head=first.trajectory_head_sha256,
        decided_at="2026-07-12T01:02:04.000000Z",
    )

    validate_policy_decision_chain([first, second])

    broken_head = replace(
        second,
        prior_trajectory_head_sha256="f" * 64,
        decision_sha256="",
        trajectory_head_sha256="",
    )
    with pytest.raises(ValueError, match="broken prior-head"):
        validate_policy_decision_chain([first, broken_head])

    wrong_trajectory = replace(
        second,
        trajectory_id="trajectory-2",
        decision_sha256="",
        trajectory_head_sha256="",
    )
    with pytest.raises(ValueError, match="changes trajectory_id"):
        validate_policy_decision_chain([first, wrong_trajectory])

    duplicate_decision_id = replace(
        second,
        decision_id=first.decision_id,
        decision_sha256="",
        trajectory_head_sha256="",
    )
    with pytest.raises(ValueError, match="reuses decision_id"):
        validate_policy_decision_chain([first, duplicate_decision_id])

    duplicate_acquisition_id = replace(
        second,
        chosen_action_id=RouteAction.RUN_FULL.value,
        acquisition_id=first.acquisition_id,
        chosen_propensity=next(
            item.propensity
            for item in second.behavior_distribution
            if item.action_id == RouteAction.RUN_FULL.value
        ),
        sampler_draw=_draw_for(
            second.behavior_distribution,
            RouteAction.RUN_FULL.value,
        ),
        decision_sha256="",
        trajectory_head_sha256="",
    )
    with pytest.raises(ValueError, match="reuses acquisition_id"):
        validate_policy_decision_chain([first, duplicate_acquisition_id])

    backwards = replace(
        second,
        decided_at="2026-07-12T01:02:02.000000Z",
        decision_sha256="",
        trajectory_head_sha256="",
    )
    with pytest.raises(ValueError, match="timestamps run backwards"):
        validate_policy_decision_chain([first, backwards])

    changed_manifest = _manifest(
        routes=(_route(RouteAction.RUN_STATIC),),
        evidence=(observation,),
    )
    changed_manifest.risk_profile = replace(
        changed_manifest.risk_profile,
        files_changed=99,
    )
    changed_state = RouterStateView.from_manifest(changed_manifest)
    changed_baseline = _logged(
        changed_state,
        chosen_action_id=RouteAction.ACCEPT.value,
        prior_head=first.trajectory_head_sha256,
        decided_at="2026-07-12T01:02:04.000000Z",
    )
    with pytest.raises(ValueError, match="immutable router baseline"):
        validate_policy_decision_chain([first, changed_baseline])

    changed_catalog = list(second.action_catalog)
    static_index = next(
        index
        for index, item in enumerate(changed_catalog)
        if item.route_action == RouteAction.RUN_STATIC
    )
    changed_catalog[static_index] = replace(
        changed_catalog[static_index],
        action_spec_sha256=_sha("different static intervention"),
    )
    changed_catalog_tuple = tuple(changed_catalog)
    changed_intervention = _logged(
        second_state,
        chosen_action_id=RouteAction.ACCEPT.value,
        prior_head=first.trajectory_head_sha256,
        decided_at="2026-07-12T01:02:04.000000Z",
        catalog=changed_catalog_tuple,
        distribution=_distribution(changed_catalog_tuple),
    )
    with pytest.raises(ValueError, match="changes intervention identity"):
        validate_policy_decision_chain([first, changed_intervention])


def test_terminal_decision_cannot_have_a_chain_successor() -> None:
    state = RouterStateView.from_manifest(_manifest())
    terminal = _logged(state, chosen_action_id=RouteAction.ABSTAIN.value)
    observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source="fixture",
        acquisition_id="acq-" + "8" * 32,
    )
    successor_state = RouterStateView.from_manifest(
        _manifest(
            routes=(_route(RouteAction.RUN_STATIC),),
            evidence=(observation,),
        )
    )
    successor = _logged(
        successor_state,
        prior_head=terminal.trajectory_head_sha256,
        decided_at="2026-07-12T01:02:04.000000Z",
    )

    with pytest.raises(ValueError, match="terminal policy decisions"):
        validate_policy_decision_chain([terminal, successor])
