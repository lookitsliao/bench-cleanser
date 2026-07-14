"""Strict manifest interchange and routing CLI tests."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

import bench_cleanser.verification.route as verification_route
from bench_cleanser.verification.models import (
    MANIFEST_SCHEMA_VERSION,
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
from bench_cleanser.verification.route import build_route_result, main
from bench_cleanser.verification.router import ConservativeRouter, RoutingPolicy


def _manifest() -> ValidityManifest:
    return ValidityManifest(
        instance_id="owner__repo-abc",
        candidate_id="sha256:candidate",
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(
            language="python",
            files_changed=2,
            lines_changed=30,
            touches_tests=True,
            semantic_disagreement=0.2,
            oracle_strength=0.9,
        ),
        provenance={
            "dataset_revision": "fixture-v1",
            "base_commit": "a" * 40,
        },
    )


def test_manifest_round_trip_preserves_evidence_history_and_digest() -> None:
    manifest = _manifest()
    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="static-fixture",
        source_version="1",
        confidence=0.9,
        privileged_inputs=("reference_patch",),
        cost=EvidenceCost(wall_seconds=0.2, input_tokens=10),
        metadata={"check": "syntax"},
    ))
    manifest.add_decision(ConservativeRouter().route(manifest))

    restored = ValidityManifest.from_dict(manifest.to_dict())

    assert restored.to_dict() == manifest.to_dict()
    assert restored.canonical_digest() == manifest.canonical_digest()


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda data: data.update(schema_version="9.0"), "unsupported manifest"),
        (
            lambda data: data["risk_profile"].update(compiled_language="false"),
            "JSON boolean",
        ),
        (lambda data: data.update(typo=True), "unknown fields"),
        (lambda data: data["provenance"].update(base_commit=123), "must be a string"),
        (
            lambda data: data["risk_profile"].update(semantic_disagreement=float("nan")),
            "must be finite",
        ),
    ],
)
def test_manifest_loader_rejects_ambiguous_or_unknown_data(mutator, message: str) -> None:
    payload = _manifest().to_dict()
    mutator(payload)

    with pytest.raises(ValueError, match=message):
        ValidityManifest.from_dict(payload)


def test_route_result_appends_auditable_decision() -> None:
    manifest = _manifest()

    result = build_route_result(manifest)

    assert result["decision"]["action"] == RouteAction.RUN_STATIC
    assert result["decision"]["scores_calibrated"] is False
    assert result["manifest"]["route_history"][-1]["action"] == "run_static"
    assert result["manifest_digest_before"] != result["manifest_digest_after"]
    assert result["policy"]["trusted_authoritative_bindings"] == []
    assert result["policy"]["minimum_full_execution_replicates"] == 2
    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION
    json.dumps(result)


def test_route_result_rejects_unchanged_or_terminal_history() -> None:
    unchanged = _manifest()
    unchanged.add_decision(ConservativeRouter().route(unchanged))
    with pytest.raises(ValueError, match="state is unchanged"):
        build_route_result(unchanged)

    terminal = _manifest()
    terminal.add_decision(RouteDecision(
        action=RouteAction.ABSTAIN,
        policy_version="fixture",
        candidate_risk=0.5,
        verifier_risk=0.5,
        expected_information_gain=0.0,
        estimated_relative_cost=0.0,
        reasons=("fixture terminal decision",),
        terminal=True,
    ))
    with pytest.raises(ValueError, match="already has a terminal"):
        build_route_result(terminal)


def test_route_cli_reads_manifest_and_writes_result(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "manifest.json"
    input_path.write_text(json.dumps(_manifest().to_dict()), encoding="utf-8")

    main([str(input_path)])

    result = json.loads(capsys.readouterr().out)
    assert result["decision"]["action"] == "run_static"
    assert result["manifest"]["lifecycle_stage"] == "rollout"


def test_route_cli_rejects_invalid_manifest(tmp_path) -> None:
    input_path = tmp_path / "manifest.json"
    input_path.write_text('{"schema_version": "0.1.0"}', encoding="utf-8")

    with pytest.raises(SystemExit, match="verification routing failed"):
        main([str(input_path)])


def test_route_cli_rejects_duplicate_json_keys(tmp_path) -> None:
    payload = json.dumps(_manifest().to_dict()).replace(
        '"instance_id": "owner__repo-abc"',
        '"instance_id": "owner__repo-abc", "instance_id": "forged"',
    )
    input_path = tmp_path / "manifest.json"
    input_path.write_text(payload, encoding="utf-8")

    with pytest.raises(SystemExit, match="duplicate JSON object key"):
        main([str(input_path)])


def test_route_cli_reports_output_write_failure_cleanly(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "manifest.json"
    input_path.write_text(json.dumps(_manifest().to_dict()), encoding="utf-8")

    def fail_write(path, content) -> None:
        raise OSError("fixture output failure")

    monkeypatch.setattr(verification_route, "atomic_write", fail_write)
    with pytest.raises(SystemExit, match="verification routing failed: fixture output failure"):
        main([str(input_path), "--output", str(tmp_path / "result.json")])


def test_route_decision_cannot_claim_missing_calibration() -> None:
    with pytest.raises(ValueError, match="require calibration_id"):
        RouteDecision(
            action=RouteAction.RUN_FULL,
            policy_version="learned-fixture",
            candidate_risk=0.2,
            verifier_risk=0.1,
            expected_information_gain=0.8,
            estimated_relative_cost=0.7,
            reasons=("fixture",),
            scores_calibrated=True,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"wall_seconds": float("nan")},
        {"cpu_seconds": float("inf")},
        {"usd": float("-inf")},
        {"input_tokens": True},
        {"storage_bytes": 1.5},
    ],
)
def test_programmatic_evidence_cost_requires_finite_strict_types(kwargs) -> None:
    with pytest.raises(ValueError):
        EvidenceCost(**kwargs)


def test_metadata_is_json_safe_defensively_copied_and_immutable() -> None:
    metadata = {"nested": [{"valid": True}]}
    observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source="fixture",
        metadata=metadata,
    )
    metadata["nested"][0]["valid"] = False

    assert observation.to_dict()["metadata"] == {"nested": [{"valid": True}]}
    json.dumps(asdict(observation), allow_nan=False)
    with pytest.raises(TypeError, match="immutable"):
        observation.metadata["new"] = True  # type: ignore[index]

    with pytest.raises(ValueError, match="non-JSON"):
        EvidenceObservation(
            kind=EvidenceKind.STATIC,
            status=EvidenceStatus.INCONCLUSIVE,
            source="fixture",
            metadata={"bad": {"set"}},
        )
    with pytest.raises(ValueError, match="keys must be strings"):
        EvidenceObservation(
            kind=EvidenceKind.STATIC,
            status=EvidenceStatus.INCONCLUSIVE,
            source="fixture",
            metadata={1: "bad"},  # type: ignore[dict-item]
        )

    cycle: dict[str, object] = {}
    cycle["cycle"] = cycle
    with pytest.raises(ValueError, match="reference cycle"):
        EvidenceObservation(
            kind=EvidenceKind.STATIC,
            status=EvidenceStatus.INCONCLUSIVE,
            source="fixture",
            metadata=cycle,
        )


def test_manifest_copies_provenance_and_revalidates_before_digest() -> None:
    provenance = {"dataset": "v1"}
    manifest = ValidityManifest(
        instance_id="i",
        candidate_id="c",
        lifecycle_stage=LifecycleStage.TRAINING,
        risk_profile=RiskProfile(),
        provenance=provenance,
    )
    provenance["dataset"] = "mutated"
    assert manifest.provenance == {"dataset": "v1"}

    manifest.provenance["invalid"] = 1  # type: ignore[assignment]
    with pytest.raises(ValueError, match="must be a string"):
        manifest.canonical_digest()


def test_programmatic_models_reject_ambiguous_types_and_nonfinite_decisions() -> None:
    with pytest.raises(ValueError, match="boolean"):
        RiskProfile(compiled_language=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        RouteDecision(
            action=RouteAction.ABSTAIN,
            policy_version="fixture",
            candidate_risk=0.5,
            verifier_risk=0.5,
            expected_information_gain=0.0,
            estimated_relative_cost=float("nan"),
            reasons=("fixture",),
            terminal=True,
        )
    with pytest.raises(ValueError, match="LifecycleStage"):
        ValidityManifest(
            instance_id="i",
            candidate_id="c",
            lifecycle_stage="training",  # type: ignore[arg-type]
            risk_profile=RiskProfile(),
            provenance={"dataset": "v1"},
        )


def test_route_result_serializes_exact_runtime_trust_policy() -> None:
    policy = RoutingPolicy(
        trusted_authoritative_bindings=frozenset({
            (EvidenceKind.FULL_EXECUTION, "docker", "v1")
        }),
        trusted_calibration_bindings=frozenset({
            ("semantic", "v2", "calibration-2026-07")
        }),
    )

    result = build_route_result(_manifest(), policy=policy)

    assert result["policy"]["trusted_authoritative_bindings"] == [
        ["full_execution", "docker", "v1"]
    ]
    assert result["policy"]["trusted_calibration_bindings"] == [
        ["semantic", "v2", "calibration-2026-07"]
    ]
