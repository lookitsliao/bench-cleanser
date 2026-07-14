"""Safety and routing invariants for the deterministic baseline."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bench_cleanser.verification import (
    ConservativeRouter,
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RiskProfile,
    RouteAction,
    RoutingPolicy,
    ValidityManifest,
)


def _manifest(
    profile: RiskProfile | None = None,
    stage: LifecycleStage = LifecycleStage.TRAINING,
) -> ValidityManifest:
    return ValidityManifest(
        instance_id="owner__repo-abc",
        candidate_id="sha256:candidate",
        lifecycle_stage=stage,
        risk_profile=profile or RiskProfile(),
        provenance={"dataset": "fixture", "base_commit": "a" * 40},
    )


def _static_pass() -> EvidenceObservation:
    return EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="syntax-and-path-checks",
        confidence=1.0,
    )


def _semantic(
    status: EvidenceStatus = EvidenceStatus.SUPPORTS_CORRECT,
    **kwargs: object,
) -> EvidenceObservation:
    return EvidenceObservation(
        kind=EvidenceKind.SEMANTIC,
        status=status,
        source="semantic-fixture",
        source_version="semantic-v1",
        confidence=0.99,
        **kwargs,
    )


def test_router_acquires_static_then_semantic() -> None:
    manifest = _manifest()
    router = ConservativeRouter()

    first = router.route(manifest)
    assert first.action == RouteAction.RUN_STATIC
    assert first.scores_calibrated is False
    assert first.calibration_id == ""
    manifest.add_evidence(_static_pass())
    assert router.route(manifest).action == RouteAction.RUN_SEMANTIC


def test_routing_policy_rejects_unversioned_trust_and_invalid_repeat_budget() -> None:
    with pytest.raises(ValueError, match="authoritative bindings"):
        RoutingPolicy(trusted_authoritative_bindings=frozenset({
            (EvidenceKind.FULL_EXECUTION, "docker", "")
        }))
    with pytest.raises(ValueError, match="cannot be smaller"):
        RoutingPolicy(
            minimum_full_execution_replicates=3,
            maximum_full_execution_attempts=2,
        )


def test_compiled_dependency_patch_routes_to_full_execution() -> None:
    manifest = _manifest(
        RiskProfile(
            language="rust",
            files_changed=4,
            lines_changed=300,
            compiled_language=True,
            native_dependencies=True,
            touches_dependency_or_build_files=True,
            touches_concurrency=True,
            oracle_strength=0.99,
        )
    )
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())

    decision = ConservativeRouter().route(manifest)

    assert decision.action == RouteAction.RUN_FULL
    assert any("high-risk" in reason for reason in decision.reasons)


def test_calibrated_low_risk_semantic_evidence_can_accept_training_case() -> None:
    manifest = _manifest(RiskProfile(oracle_strength=0.99))
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(
        _semantic(
            candidate_probability=0.999,
            calibrated_risk_upper_bound=0.01,
            calibration_id="repo-disjoint-calibration-v1",
        )
    )

    policy = RoutingPolicy(
        trusted_calibration_bindings=frozenset({
            (
                "semantic-fixture",
                "semantic-v1",
                "repo-disjoint-calibration-v1",
            )
        })
    )
    decision = ConservativeRouter(policy).route(manifest)

    assert decision.action == RouteAction.ACCEPT
    assert decision.terminal
    assert "declared calibration bound" in " ".join(decision.reasons)
    assert "held-out calibrated" not in " ".join(decision.reasons)


def test_self_asserted_calibration_is_not_trusted_and_bound_never_rejects() -> None:
    policy = RoutingPolicy(
        trusted_calibration_bindings=frozenset({
            ("semantic-fixture", "semantic-v1", "trusted-calibration")
        })
    )

    untrusted = _manifest(RiskProfile(oracle_strength=0.99))
    untrusted.add_evidence(_static_pass())
    untrusted.add_evidence(_semantic(
        candidate_probability=0.999,
        calibrated_risk_upper_bound=0.0,
        calibration_id="self-asserted",
    ))
    untrusted_decision = ConservativeRouter(policy).route(untrusted)
    assert not untrusted_decision.terminal
    assert untrusted_decision.action == RouteAction.RUN_TARGETED

    negative = _manifest(RiskProfile(oracle_strength=0.99))
    negative.add_evidence(_static_pass())
    negative.add_evidence(_semantic(
        EvidenceStatus.SUPPORTS_INCORRECT,
        candidate_probability=0.001,
        calibrated_risk_upper_bound=0.0,
        calibration_id="trusted-calibration",
    ))
    negative_decision = ConservativeRouter(policy).route(negative)
    assert not negative_decision.terminal
    assert negative_decision.action != RouteAction.REJECT


def test_evaluation_does_not_accept_semantic_evidence_by_default() -> None:
    manifest = _manifest(
        RiskProfile(oracle_strength=0.99),
        stage=LifecycleStage.EVALUATION,
    )
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(
        _semantic(
            candidate_probability=0.999,
            calibrated_risk_upper_bound=0.001,
            calibration_id="repo-disjoint-calibration-v1",
        )
    )

    policy = RoutingPolicy(
        trusted_calibration_bindings=frozenset({
            (
                "semantic-fixture",
                "semantic-v1",
                "repo-disjoint-calibration-v1",
            )
        })
    )
    assert ConservativeRouter(policy).route(manifest).action == RouteAction.RUN_FULL


def test_weak_full_execution_routes_to_oracle_hardening() -> None:
    manifest = _manifest(
        RiskProfile(
            oracle_strength=0.55,
            oracle_hardening_available=True,
        )
    )
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())
    manifest.add_evidence(
        EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.SUPPORTS_CORRECT,
            source="weak-test-suite",
            verifier_validity=0.55,
            authoritative=False,
        )
    )

    decision = ConservativeRouter().route(manifest)

    assert decision.action == RouteAction.HARDEN_ORACLE
    assert not decision.terminal


def test_semantic_runtime_conflict_hardens_even_with_passing_execution() -> None:
    manifest = _manifest(
        RiskProfile(
            oracle_strength=0.99,
            oracle_hardening_available=True,
        )
    )
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic(EvidenceStatus.SUPPORTS_INCORRECT))
    manifest.add_evidence(
        EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.SUPPORTS_CORRECT,
            source="docker-suite",
            verifier_validity=0.99,
            authoritative=True,
        )
    )

    assert ConservativeRouter().route(manifest).action == RouteAction.HARDEN_ORACLE


def test_environment_error_retries_then_abstains_instead_of_rejecting() -> None:
    manifest = _manifest(RiskProfile(oracle_strength=0.9))
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())
    manifest.add_evidence(
        EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.ERROR,
            source="docker",
            metadata={"failure_class": "environment_build"},
        )
    )

    decision = ConservativeRouter().route(manifest)

    assert decision.action == RouteAction.RUN_FULL
    assert not decision.terminal

    for attempt in range(2):
        manifest.add_evidence(EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.ERROR,
            source="docker",
            source_version=f"attempt-{attempt + 2}",
            metadata={"failure_class": "environment_build"},
        ))

    exhausted = ConservativeRouter().route(manifest)
    assert exhausted.action == RouteAction.ABSTAIN
    assert exhausted.terminal


def test_environment_error_cannot_encode_candidate_probability() -> None:
    with pytest.raises(ValueError, match="verifier failure"):
        EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.ERROR,
            source="docker",
            candidate_probability=0.0,
        )


@pytest.mark.parametrize(
    ("hardening_available", "expected_action"),
    [
        (False, RouteAction.ABSTAIN),
        (True, RouteAction.HARDEN_ORACLE),
    ],
)
def test_repeated_full_execution_disagreement_never_becomes_latest_wins(
    hardening_available: bool,
    expected_action: RouteAction,
) -> None:
    manifest = _manifest(
        RiskProfile(
            oracle_strength=0.99,
            oracle_hardening_available=hardening_available,
        )
    )
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())
    for status in (
        EvidenceStatus.SUPPORTS_CORRECT,
        EvidenceStatus.SUPPORTS_INCORRECT,
    ):
        manifest.add_evidence(EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=status,
            source="repeated-docker-suite",
            source_version="fixture-v1",
            verifier_validity=0.99,
            authoritative=True,
        ))

    decision = ConservativeRouter().route(manifest)

    assert decision.action == expected_action
    assert decision.verifier_risk == 1.0
    assert not decision.terminal if hardening_available else decision.terminal


def test_repeated_policy_trusted_full_runs_are_required_for_terminal_accept() -> None:
    manifest = _manifest(RiskProfile(oracle_strength=0.99))
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())
    policy = RoutingPolicy(
        trusted_authoritative_bindings=frozenset({
            (EvidenceKind.FULL_EXECUTION, "docker-suite", "suite-v1")
        })
    )
    router = ConservativeRouter(policy)

    for attempt in range(2):
        manifest.add_evidence(EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.SUPPORTS_CORRECT,
            source="docker-suite",
            source_version="suite-v1",
            acquisition_id=f"full-run-{attempt}",
            verifier_validity=0.99,
            authoritative=True,
        ))
        decision = router.route(manifest)
        if len([
            item
            for item in manifest.evidence
            if item.kind == EvidenceKind.FULL_EXECUTION
        ]) == 1:
            assert decision.action == RouteAction.RUN_FULL
            assert not decision.terminal

    assert decision.action == RouteAction.ACCEPT
    assert decision.terminal


def test_self_asserted_authority_is_ignored_without_runtime_policy_binding() -> None:
    manifest = _manifest(RiskProfile(oracle_strength=0.99))
    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.HUMAN_ADJUDICATION,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="human-panel",
        source_version="v1",
        acquisition_id="human-panel-case-1",
        authoritative=True,
    ))

    assert ConservativeRouter().route(manifest).action == RouteAction.RUN_STATIC

    policy = RoutingPolicy(
        trusted_authoritative_bindings=frozenset({
            (EvidenceKind.HUMAN_ADJUDICATION, "human-panel", "v1")
        })
    )
    trusted = ConservativeRouter(policy).route(manifest)
    assert trusted.action == RouteAction.ACCEPT
    assert trusted.terminal


def test_high_runtime_oracle_risk_blocks_otherwise_trusted_full_result() -> None:
    manifest = _manifest(RiskProfile(
        oracle_strength=0.99,
        observed_flake_rate=0.9,
    ))
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())
    for attempt in range(2):
        manifest.add_evidence(EvidenceObservation(
            kind=EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.SUPPORTS_CORRECT,
            source="docker-suite",
            source_version="suite-v1",
            acquisition_id=f"high-flake-run-{attempt}",
            verifier_validity=0.99,
            authoritative=True,
        ))
    policy = RoutingPolicy(
        trusted_authoritative_bindings=frozenset({
            (EvidenceKind.FULL_EXECUTION, "docker-suite", "suite-v1")
        })
    )

    decision = ConservativeRouter(policy).route(manifest)

    assert decision.verifier_risk == pytest.approx(0.9)
    assert decision.action == RouteAction.ABSTAIN
    assert decision.terminal


def test_semantic_and_static_errors_do_not_masquerade_as_runtime_oracle_risk() -> None:
    manifest = _manifest(RiskProfile(oracle_strength=0.99))
    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.ERROR,
        source="static-service",
    ))
    manifest.add_evidence(_semantic(EvidenceStatus.ERROR))

    non_runtime = ConservativeRouter().route(manifest)
    assert non_runtime.verifier_risk == pytest.approx(0.01)

    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.FULL_EXECUTION,
        status=EvidenceStatus.ERROR,
        source="docker-suite",
    ))
    runtime = ConservativeRouter().route(manifest)
    assert runtime.verifier_risk == 1.0


def test_failed_hardening_retries_and_trusted_hardening_can_resolve() -> None:
    manifest = _manifest(RiskProfile(
        oracle_strength=0.99,
        observed_flake_rate=0.9,
        oracle_hardening_available=True,
    ))
    manifest.add_evidence(_static_pass())
    manifest.add_evidence(_semantic())
    router = ConservativeRouter(RoutingPolicy(
        trusted_authoritative_bindings=frozenset({
            (EvidenceKind.ORACLE_HARDENING, "gold-sanity", "v1")
        })
    ))
    assert router.route(manifest).action == RouteAction.HARDEN_ORACLE

    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.ORACLE_HARDENING,
        status=EvidenceStatus.ERROR,
        source="gold-sanity",
        source_version="v1",
    ))
    retry = router.route(manifest)
    assert retry.action == RouteAction.HARDEN_ORACLE
    assert not retry.terminal

    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.ORACLE_HARDENING,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="gold-sanity",
        source_version="v1",
        acquisition_id="gold-sanity-run-1",
        verifier_validity=0.99,
        authoritative=True,
    ))
    resolved = router.route(manifest)
    assert resolved.action == RouteAction.ACCEPT
    assert resolved.terminal


def test_trusted_authority_requires_unique_acquisition_identity() -> None:
    manifest = _manifest(RiskProfile(oracle_strength=0.99))
    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.HUMAN_ADJUDICATION,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="human-panel",
        source_version="v1",
        authoritative=True,
    ))
    policy = RoutingPolicy(trusted_authoritative_bindings=frozenset({
        (EvidenceKind.HUMAN_ADJUDICATION, "human-panel", "v1")
    }))

    assert ConservativeRouter(policy).route(manifest).action == RouteAction.RUN_STATIC

    identified = replace(
        manifest.evidence[0],
        acquisition_id="human-panel-case-1",
    )
    manifest.evidence.clear()
    manifest.add_evidence(identified)
    with pytest.raises(ValueError, match="duplicate evidence acquisition_id"):
        manifest.add_evidence(identified)


def test_manifest_digest_is_stable_and_evidence_sensitive() -> None:
    first = _manifest()
    second = _manifest()
    assert first.canonical_digest() == second.canonical_digest()

    second.add_evidence(_static_pass())
    assert first.canonical_digest() != second.canonical_digest()
