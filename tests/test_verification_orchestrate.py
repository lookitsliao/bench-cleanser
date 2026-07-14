"""Fail-closed route-to-acquisition orchestration tests."""

from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

import bench_cleanser.verification.acquire as verification_acquire
import bench_cleanser.verification.orchestrate as verification_orchestrate
from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from bench_cleanser.verification.acquire import AcquisitionRequest
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RiskProfile,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)
from bench_cleanser.verification.orchestrate import (
    ORCHESTRATION_SCHEMA_VERSION,
    WORKSPACE_IDENTITY_SCHEMA_VERSION,
    RouteAcquisitionPlan,
    execute_route_acquisition,
    load_route_acquisition_plan,
    load_route_acquisition_record,
    validate_completed_route_acquisition,
)

_CANDIDATE_SHA256 = "c" * 64
_CANDIDATE_ID = f"sha256:{_CANDIDATE_SHA256}"
_BASE_COMMIT = "a" * 40
_WORKSPACE_ID = "sha256:" + "d" * 64
_ACQUISITION_ID = "acq-" + "1" * 32


def _decision(
    action: RouteAction = RouteAction.RUN_STATIC,
    *,
    terminal: bool = False,
) -> RouteDecision:
    return RouteDecision(
        action=action,
        policy_version="fixture-policy-v1",
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.6,
        estimated_relative_cost=0.1,
        reasons=("fixture route decision",),
        terminal=terminal,
    )


def _manifest(decision: RouteDecision | None = None) -> ValidityManifest:
    manifest = ValidityManifest(
        instance_id="owner__repo-candidate",
        candidate_id=_CANDIDATE_ID,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(language="python"),
        provenance={
            "dataset_revision": "fixture-v1",
            "base_commit": _BASE_COMMIT,
            "candidate_patch_sha256": _CANDIDATE_SHA256,
        },
    )
    manifest.add_decision(decision or _decision())
    return manifest


def _write_workspace_marker(
    workspace: pathlib.Path,
    *,
    candidate_id: str = _CANDIDATE_ID,
) -> tuple[pathlib.Path, str]:
    marker = workspace / ".bench-cleanser-workspace.json"
    payload = strict_json_dumps(
        {
            "schema_version": WORKSPACE_IDENTITY_SCHEMA_VERSION,
            "instance_id": "owner__repo-candidate",
            "candidate_id": candidate_id,
            "base_commit": _BASE_COMMIT,
            "workspace_id": _WORKSPACE_ID,
        },
        indent=2,
    ) + "\n"
    marker.write_text(payload, encoding="utf-8")
    return marker, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _request(
    workspace: pathlib.Path,
    *,
    kind: EvidenceKind = EvidenceKind.STATIC,
    argv: tuple[str, ...] | None = None,
) -> AcquisitionRequest:
    return AcquisitionRequest(
        kind=kind,
        source="fixture-check",
        source_version="1.0.0",
        workspace_root=str(workspace),
        working_directory=".",
        argv=argv or (sys.executable, "-c", "print('orchestrated')"),
        timeout_seconds=2.0,
        max_capture_bytes=1024,
        supports_incorrect_exit_codes=(
            () if kind == EvidenceKind.SEMANTIC else (1,)
        ),
    )


def _plan(
    tmp_path: pathlib.Path,
    manifest: ValidityManifest,
    *,
    requests: dict[RouteAction, AcquisitionRequest] | None = None,
    acquisition_id: str = _ACQUISITION_ID,
    output_name: str = "updated.json",
) -> RouteAcquisitionPlan:
    workspace = tmp_path / "workspace"
    state = tmp_path / "state"
    workspace.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    _, marker_sha256 = _write_workspace_marker(workspace)
    return RouteAcquisitionPlan(
        instance_id=manifest.instance_id,
        candidate_id=manifest.candidate_id,
        manifest_sha256=manifest.canonical_digest(),
        base_commit=_BASE_COMMIT,
        workspace_root=str(workspace),
        workspace_id=_WORKSPACE_ID,
        workspace_identity_path=".bench-cleanser-workspace.json",
        workspace_identity_sha256=marker_sha256,
        acquisition_id=acquisition_id,
        coordination_directory=str(state),
        artifact_directory=str(state / "artifacts"),
        output_path=str(state / output_name),
        requests=requests or {RouteAction.RUN_STATIC: _request(workspace)},
    )


def _rebind_artifact_observation(
    observation: EvidenceObservation,
    artifact_bytes: bytes,
) -> EvidenceObservation:
    data = observation.to_dict()
    metadata = data["metadata"]
    cost = data["cost"]
    assert isinstance(metadata, dict)
    assert isinstance(cost, dict)
    metadata["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    cost["storage_bytes"] = len(artifact_bytes)
    return EvidenceObservation.from_dict(data)


def _rewrite_raw_artifact(
    observation: EvidenceObservation,
    artifact_directory: pathlib.Path,
    mutation: Callable[[dict[str, Any]], None],
) -> EvidenceObservation:
    artifact = artifact_directory / f"{observation.acquisition_id}.json"
    raw = strict_json_loads(artifact.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    mutation(raw)
    artifact_bytes = (strict_json_dumps(raw, indent=2) + "\n").encode("utf-8")
    artifact.write_bytes(artifact_bytes)
    return _rebind_artifact_observation(observation, artifact_bytes)


def test_orchestration_persists_intent_runs_once_and_durably_updates_clone(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    decision = manifest.route_history[-1]
    workspace = tmp_path / "workspace"
    plan = _plan(
        tmp_path,
        manifest,
        requests={
            RouteAction.RUN_STATIC: _request(workspace),
            RouteAction.RUN_TARGETED: _request(
                workspace,
                kind=EvidenceKind.TARGETED_EXECUTION,
            ),
            RouteAction.RUN_FULL: _request(
                workspace,
                kind=EvidenceKind.FULL_EXECUTION,
            ),
            RouteAction.HARDEN_ORACLE: _request(
                workspace,
                kind=EvidenceKind.ORACLE_HARDENING,
            ),
        },
    )
    real_acquire = verification_orchestrate.acquire_evidence
    calls = 0
    prepared_seen: dict[str, Any] | None = None

    def counted_acquire(request, *, artifact_directory, acquisition_id=None):
        nonlocal calls, prepared_seen
        calls += 1
        prepared = json.loads(pathlib.Path(plan.output_path).read_text(encoding="utf-8"))
        prepared_seen = prepared
        assert prepared["state"] == "prepared"
        assert prepared["acquisition_id"] == plan.acquisition_id
        assert prepared["route"]["decision"]["action"] == "run_static"
        assert prepared["request"]["argv"] == list(request.argv)
        return real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", counted_acquire)
    result = execute_route_acquisition(manifest, decision, plan)

    assert calls == 1
    assert manifest.evidence == []
    assert len(manifest.route_history) == 1
    assert len(result.manifest.evidence) == 1
    assert result.manifest.route_history == manifest.route_history
    assert result.observation.acquisition_id == plan.acquisition_id
    assert result.observation.authoritative is False
    assert result.observation.kind == EvidenceKind.STATIC
    route_provenance = result.observation.metadata["route_provenance"]
    assert route_provenance["route_action"] == "run_static"
    assert route_provenance["expected_evidence_kind"] == "static"
    assert route_provenance["manifest_sha256_before_acquisition"] == (
        plan.manifest_sha256
    )
    assert route_provenance["acquisition_id"] == plan.acquisition_id
    assert route_provenance["attempt_semantics"] == "at_most_once"
    assert route_provenance["workspace_identity_scope"] == "provisioner_marker_only"
    assert route_provenance["execution_backend"] == "local_process_unsafe_non_isolated"
    assert route_provenance["detached_child_containment"] == "not_guaranteed"

    output_bytes = pathlib.Path(plan.output_path).read_bytes()
    assert hashlib.sha256(output_bytes).hexdigest() == result.output_sha256
    durable = strict_json_loads(output_bytes.decode("utf-8"))
    assert durable["state"] == "completed"
    assert durable["manifest_sha256_before"] == result.manifest_sha256_before
    assert durable["manifest_sha256_after"] == result.manifest_sha256_after
    assert durable["manifest"]["evidence"][0] == result.observation.to_dict()
    assert durable["observation"]["authoritative"] is False
    assert durable["attempt_semantics"] == "at_most_once"
    assert durable["workspace_identity_scope"] == "provisioner_marker_only"
    assert durable["orchestrator"]["sandbox"] == "not_provided"
    assert durable["orchestrator"]["execution_backend"] == (
        "local_process_unsafe_non_isolated"
    )
    assert durable["orchestrator"]["detached_child_containment"] == "not_guaranteed"
    assert prepared_seen is not None
    prepared = durable["prepared"]
    assert prepared["envelope"] == prepared_seen
    assert prepared["envelope"]["plan"] == plan.to_dict()
    assert durable["plan"] == plan.to_dict()
    assert set(durable["plan"]["requests"]) == {
        "harden_oracle",
        "run_full_execution",
        "run_static",
        "run_targeted_execution",
    }
    prepared_at = prepared["envelope"]["prepared_at"]
    parsed_prepared_at = datetime.fromisoformat(
        prepared_at.removesuffix("Z") + "+00:00"
    )
    assert parsed_prepared_at.tzinfo is not None
    assert parsed_prepared_at.utcoffset() == UTC.utcoffset(parsed_prepared_at)
    assert (
        parsed_prepared_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        == prepared_at
    )
    assert prepared_at == result.prepared_at
    assert prepared["envelope_sha256"] == hashlib.sha256(
        strict_json_dumps(prepared["envelope"]).encode("utf-8")
    ).hexdigest()
    prepared_record = strict_json_dumps(prepared["envelope"], indent=2) + "\n"
    assert prepared["record_sha256"] == hashlib.sha256(
        prepared_record.encode("utf-8")
    ).hexdigest()
    assert prepared["envelope_sha256"] == result.prepared_envelope_sha256
    assert not list(pathlib.Path(plan.output_path).parent.glob(".*updated.json.lock"))
    assert not list(pathlib.Path(plan.artifact_directory).glob(".*.lock"))
    assert len(
        list(pathlib.Path(plan.coordination_directory).glob(".decision-*.lock"))
    ) == 1


def test_completed_record_strictly_reloads_without_redispatch(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    decision = manifest.route_history[-1]
    plan = _plan(tmp_path, manifest)
    calls = 0
    real_acquire = verification_orchestrate.acquire_evidence

    def counted_acquire(request, *, artifact_directory, acquisition_id=None):
        nonlocal calls
        calls += 1
        return real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", counted_acquire)
    expected = execute_route_acquisition(manifest, decision, plan)
    assert calls == 1
    with pathlib.Path(plan.output_path).open(encoding="utf-8") as stream:
        record = load_route_acquisition_record(stream)
    restored = validate_completed_route_acquisition(
        record,
        manifest_before=manifest,
        decision=decision,
        plan=plan,
    )

    assert calls == 1
    assert restored.output_sha256 == expected.output_sha256
    assert restored.manifest.to_dict() == expected.manifest.to_dict()
    assert restored.observation == expected.observation
    assert restored.prepared_envelope_sha256 == expected.prepared_envelope_sha256


def test_completed_record_rejects_preimage_and_successor_tampering(
    tmp_path: pathlib.Path,
) -> None:
    manifest = _manifest()
    decision = manifest.route_history[-1]
    plan = _plan(tmp_path, manifest)
    execute_route_acquisition(manifest, decision, plan)
    with pathlib.Path(plan.output_path).open(encoding="utf-8") as stream:
        record = load_route_acquisition_record(stream)

    wrong_plan = json.loads(json.dumps(record))
    wrong_plan["plan"]["workspace_id"] = "sha256:" + "e" * 64
    with pytest.raises(ValueError, match="retained preimage"):
        validate_completed_route_acquisition(
            wrong_plan,
            manifest_before=manifest,
            decision=decision,
            plan=plan,
        )

    wrong_prepared = json.loads(json.dumps(record))
    wrong_prepared["prepared"]["envelope"]["prepared_at"] = (
        "2026-01-01T00:00:00Z"
    )
    with pytest.raises(ValueError, match="prepared orchestration envelope"):
        validate_completed_route_acquisition(
            wrong_prepared,
            manifest_before=manifest,
            decision=decision,
            plan=plan,
        )

    wrong_provenance = json.loads(json.dumps(record))
    wrong_provenance["observation"]["metadata"]["route_provenance"][
        "acquisition_id"
    ] = "acq-" + "2" * 32
    with pytest.raises(ValueError, match="route provenance"):
        validate_completed_route_acquisition(
            wrong_provenance,
            manifest_before=manifest,
            decision=decision,
            plan=plan,
        )

    wrong_successor = json.loads(json.dumps(record))
    wrong_successor["manifest"]["evidence"] = []
    with pytest.raises(ValueError, match="one-observation successor"):
        validate_completed_route_acquisition(
            wrong_successor,
            manifest_before=manifest,
            decision=decision,
            plan=plan,
        )


def test_completed_record_rejects_raw_artifact_and_noncanonical_record(
    tmp_path: pathlib.Path,
) -> None:
    manifest = _manifest()
    decision = manifest.route_history[-1]
    plan = _plan(tmp_path, manifest)
    execute_route_acquisition(manifest, decision, plan)
    output = pathlib.Path(plan.output_path)
    text = output.read_text(encoding="utf-8")
    with output.open(encoding="utf-8") as stream:
        record = load_route_acquisition_record(stream)

    with pytest.raises(ValueError, match="canonical durable form"):
        load_route_acquisition_record(io.StringIO(text.rstrip("\n")))

    artifact = pathlib.Path(plan.artifact_directory) / f"{plan.acquisition_id}.json"
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifact SHA-256"):
        validate_completed_route_acquisition(
            record,
            manifest_before=manifest,
            decision=decision,
            plan=plan,
        )


def test_semantic_route_executes_strict_adapter_and_appends_mapped_observation(
    tmp_path: pathlib.Path,
) -> None:
    manifest = _manifest(_decision(RouteAction.RUN_SEMANTIC))
    workspace = tmp_path / "workspace"
    payload = {
        "schema_version": "0.1.0",
        "status": "supports_correct",
        "candidate_probability": 0.88,
        "calibrated_risk_upper_bound": 0.12,
        "calibration_id": "semantic-fixture-cal-v1",
        "verifier_validity": 0.93,
        "privileged_inputs": ["issue_text"],
        "cost": {
            "input_tokens": 55,
            "output_tokens": 8,
            "usd": 0.002,
        },
    }
    request = _request(
        workspace,
        kind=EvidenceKind.SEMANTIC,
        argv=(
            sys.executable,
            "-c",
            "import sys; sys.stdout.write(sys.argv[1])",
            strict_json_dumps(payload),
        ),
    )
    plan = _plan(
        tmp_path,
        manifest,
        requests={RouteAction.RUN_SEMANTIC: request},
    )

    result = execute_route_acquisition(
        manifest,
        manifest.route_history[-1],
        plan,
    )

    observation = result.observation
    assert observation.kind == EvidenceKind.SEMANTIC
    assert observation.status == EvidenceStatus.SUPPORTS_CORRECT
    assert observation.candidate_probability == 0.88
    assert observation.calibrated_risk_upper_bound == 0.12
    assert observation.calibration_id == "semantic-fixture-cal-v1"
    assert observation.verifier_validity == 0.93
    assert observation.privileged_inputs == ("issue_text",)
    assert observation.cost.input_tokens == 55
    assert observation.cost.output_tokens == 8
    assert observation.cost.usd == 0.002
    assert observation.authoritative is False
    assert observation.metadata["route_provenance"]["route_action"] == "run_semantic"
    assert observation.metadata["route_provenance"][
        "expected_evidence_kind"
    ] == "semantic"
    assert result.manifest.evidence[-1].to_dict() == observation.to_dict()
    artifact = strict_json_loads(
        (
            pathlib.Path(plan.artifact_directory)
            / f"{plan.acquisition_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact["semantic"]["parsed"] == payload
    assert artifact["execution"]["outcome"] == "semantic_result"


def _semantic_plan_fixture(
    tmp_path: pathlib.Path,
) -> tuple[ValidityManifest, RouteAcquisitionPlan]:
    manifest = _manifest(_decision(RouteAction.RUN_SEMANTIC))
    payload = {
        "schema_version": "0.1.0",
        "status": "supports_correct",
        "candidate_probability": 0.8,
        "calibrated_risk_upper_bound": None,
        "calibration_id": "",
        "verifier_validity": 0.9,
        "privileged_inputs": [],
        "cost": {"input_tokens": None, "output_tokens": None, "usd": None},
    }
    plan = _plan(
        tmp_path,
        manifest,
        requests={
            RouteAction.RUN_SEMANTIC: _request(
                tmp_path / "workspace",
                kind=EvidenceKind.SEMANTIC,
                argv=(
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.write(sys.argv[1])",
                    strict_json_dumps(payload),
                ),
            )
        },
    )
    return manifest, plan


def test_semantic_orchestration_reparses_raw_before_manifest_insertion(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, plan = _semantic_plan_fixture(tmp_path)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        return _rewrite_raw_artifact(
            observation,
            pathlib.Path(artifact_directory),
            lambda raw: raw["semantic"]["parsed"].__setitem__(
                "candidate_probability",
                0.7,
            ),
        )

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match="parsed output does not match raw"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert manifest.evidence == []


def test_semantic_orchestration_rejects_observation_artifact_field_mismatch(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, plan = _semantic_plan_fixture(tmp_path)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        data = observation.to_dict()
        data["candidate_probability"] = 0.7
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match="candidate probability does not match"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert manifest.evidence == []


def test_semantic_orchestration_hashes_retained_bytes_independently(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, plan = _semantic_plan_fixture(tmp_path)
    real_acquire = verification_orchestrate.acquire_evidence
    forged_digest = "f" * 64

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )

        def replace_duplicate_digests(raw: dict[str, Any]) -> None:
            raw["stdout"]["sha256"] = forged_digest
            raw["semantic"]["raw_stdout"]["sha256"] = forged_digest

        rebound = _rewrite_raw_artifact(
            observation,
            pathlib.Path(artifact_directory),
            replace_duplicate_digests,
        )
        data = rebound.to_dict()
        metadata = data["metadata"]
        assert isinstance(metadata, dict)
        capture_bindings = metadata["capture_bindings"]
        assert isinstance(capture_bindings, dict)
        stdout_binding = capture_bindings["stdout"]
        assert isinstance(stdout_binding, dict)
        stdout_binding["sha256"] = forged_digest
        metadata["semantic_output_sha256"] = forged_digest
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match="digest does not match retained bytes"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert manifest.evidence == []


@pytest.mark.parametrize(
    ("action", "kind"),
    [
        (RouteAction.RUN_STATIC, EvidenceKind.STATIC),
        (RouteAction.RUN_SEMANTIC, EvidenceKind.SEMANTIC),
        (RouteAction.RUN_TARGETED, EvidenceKind.TARGETED_EXECUTION),
        (RouteAction.RUN_FULL, EvidenceKind.FULL_EXECUTION),
        (RouteAction.HARDEN_ORACLE, EvidenceKind.ORACLE_HARDENING),
    ],
)
def test_plan_has_an_explicit_exact_action_to_kind_contract(
    tmp_path: pathlib.Path,
    action: RouteAction,
    kind: EvidenceKind,
) -> None:
    manifest = _manifest(_decision(action))
    plan = _plan(
        tmp_path,
        manifest,
        requests={action: _request(tmp_path / "workspace", kind=kind)},
    )

    assert plan.requests[action].kind == kind
    assert RouteAcquisitionPlan.from_dict(plan.to_dict()).to_dict() == plan.to_dict()


def test_plan_rejects_wrong_kind_and_actions_without_local_adapter(
    tmp_path: pathlib.Path,
) -> None:
    manifest = _manifest()
    workspace = tmp_path / "workspace"
    state = tmp_path / "state"
    workspace.mkdir()
    state.mkdir()
    _, marker_sha256 = _write_workspace_marker(workspace)
    kwargs = {
        "instance_id": manifest.instance_id,
        "candidate_id": manifest.candidate_id,
        "manifest_sha256": manifest.canonical_digest(),
        "base_commit": _BASE_COMMIT,
        "workspace_root": str(workspace),
        "workspace_id": _WORKSPACE_ID,
        "workspace_identity_path": ".bench-cleanser-workspace.json",
        "workspace_identity_sha256": marker_sha256,
        "acquisition_id": _ACQUISITION_ID,
        "coordination_directory": str(state),
        "artifact_directory": str(state / "artifacts"),
        "output_path": str(state / "updated.json"),
    }

    with pytest.raises(ValueError, match="requires evidence kind 'static'"):
        RouteAcquisitionPlan(
            **kwargs,
            requests={
                RouteAction.RUN_STATIC: _request(
                    workspace,
                    kind=EvidenceKind.FULL_EXECUTION,
                )
            },
        )
    with pytest.raises(ValueError, match="requires evidence kind 'semantic'"):
        RouteAcquisitionPlan(
            **kwargs,
            requests={RouteAction.RUN_SEMANTIC: _request(workspace)},
        )
    semantic_plan = RouteAcquisitionPlan(
        **kwargs,
        requests={
            RouteAction.RUN_SEMANTIC: _request(
                workspace,
                kind=EvidenceKind.SEMANTIC,
            )
        },
    )
    assert semantic_plan.requests[RouteAction.RUN_SEMANTIC].kind == EvidenceKind.SEMANTIC


def test_selected_action_must_exist_before_any_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(
        tmp_path,
        manifest,
        requests={
            RouteAction.RUN_FULL: _request(
                tmp_path / "workspace",
                kind=EvidenceKind.FULL_EXECUTION,
            )
        },
    )
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("acquisition must not run"),
    )

    with pytest.raises(ValueError, match="no request for route action 'run_static'"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not pathlib.Path(plan.output_path).exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda plan: replace(plan, manifest_sha256="f" * 64),
            "manifest SHA-256",
        ),
        (
            lambda plan: replace(plan, candidate_id="sha256:" + "f" * 64),
            "candidate_id",
        ),
        (
            lambda plan: replace(plan, base_commit="b" * 40),
            "base_commit",
        ),
        (
            lambda plan: replace(plan, workspace_identity_sha256="f" * 64),
            "marker SHA-256",
        ),
    ],
)
def test_identity_mismatch_fails_before_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    message: str,
) -> None:
    manifest = _manifest()
    plan = mutation(_plan(tmp_path, manifest))
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("acquisition must not run"),
    )

    with pytest.raises(ValueError, match=message):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not pathlib.Path(plan.output_path).exists()


def test_every_mapped_request_must_use_the_exact_canonical_workspace(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    other = tmp_path / "other"
    other.mkdir()
    plan = _plan(
        tmp_path,
        manifest,
        requests={
            RouteAction.RUN_STATIC: _request(tmp_path / "workspace"),
            RouteAction.RUN_FULL: _request(other, kind=EvidenceKind.FULL_EXECUTION),
        },
    )
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("acquisition must not run"),
    )

    with pytest.raises(ValueError, match="exact canonical plan workspace_root"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_route_decision_must_be_exact_last_nonterminal_supported_action(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("acquisition must not run"),
    )

    with pytest.raises(ValueError, match="exact last decision"):
        execute_route_acquisition(manifest, _decision(RouteAction.RUN_FULL), plan)

    terminal_manifest = _manifest(_decision(RouteAction.ABSTAIN, terminal=True))
    terminal_plan = _plan(
        tmp_path / "terminal",
        terminal_manifest,
        output_name="terminal.json",
    )
    with pytest.raises(ValueError, match="terminal route decisions"):
        execute_route_acquisition(
            terminal_manifest,
            terminal_manifest.route_history[-1],
            terminal_plan,
        )

    semantic_root = tmp_path / "semantic"
    semantic_root.mkdir()
    semantic_manifest = _manifest(_decision(RouteAction.RUN_SEMANTIC))
    semantic_plan = _plan(semantic_root, semantic_manifest)
    with pytest.raises(ValueError, match="no request for route action 'run_semantic'"):
        execute_route_acquisition(
            semantic_manifest,
            semantic_manifest.route_history[-1],
            semantic_plan,
        )


def test_earlier_terminal_route_decision_rejects_later_nonterminal_action(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_decision(RouteAction.ABSTAIN, terminal=True))
    manifest.add_decision(_decision(RouteAction.RUN_STATIC))
    plan = _plan(tmp_path, manifest)
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("terminal history must not execute"),
    )

    with pytest.raises(ValueError, match="earlier terminal route decision"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not pathlib.Path(plan.output_path).exists()


def test_existing_manifest_acquisition_id_rejects_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    manifest.add_evidence(
        EvidenceObservation(
            kind=EvidenceKind.STATIC,
            status=EvidenceStatus.INCONCLUSIVE,
            source="existing-fixture",
            acquisition_id=_ACQUISITION_ID,
            verifier_validity=0.0,
        )
    )
    plan = _plan(tmp_path, manifest)
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("duplicate ID must not execute"),
    )

    with pytest.raises(ValueError, match="already exists in the manifest evidence ledger"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not pathlib.Path(plan.output_path).exists()


def test_marker_changed_by_command_leaves_prepared_record_without_manifest_update(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    marker = pathlib.Path(plan.workspace_root) / plan.workspace_identity_path
    real_acquire = verification_orchestrate.acquire_evidence

    def acquire_then_mutate(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        marker.write_text("{}\n", encoding="utf-8")
        return observation

    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        acquire_then_mutate,
    )
    with pytest.raises(ValueError, match="marker SHA-256"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)

    prepared = json.loads(pathlib.Path(plan.output_path).read_text(encoding="utf-8"))
    assert prepared["state"] == "prepared"
    assert manifest.evidence == []
    assert len(list(pathlib.Path(plan.artifact_directory).glob("*.json"))) == 1
    assert pathlib.Path(plan.output_path).parent.joinpath(
        f".{pathlib.Path(plan.output_path).name}.lock"
    ).exists()


def test_final_write_failure_is_not_rerun_under_a_new_identity(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_atomic_write = verification_orchestrate.atomic_write
    writes = 0

    def fail_completed_write(path, content):
        nonlocal writes
        writes += 1
        assert json.loads(content)["state"] == "completed"
        raise OSError("fixture completed-output failure")

    monkeypatch.setattr(
        verification_orchestrate,
        "atomic_write",
        fail_completed_write,
    )
    with pytest.raises(OSError, match="fixture completed-output failure"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)

    assert writes == 1
    prepared = json.loads(pathlib.Path(plan.output_path).read_text(encoding="utf-8"))
    assert prepared["state"] == "prepared"
    artifacts = list(pathlib.Path(plan.artifact_directory).glob("*.json"))
    assert len(artifacts) == 1
    first_artifact = artifacts[0]

    monkeypatch.setattr(verification_orchestrate, "atomic_write", real_atomic_write)
    with pytest.raises(ValueError, match="output already exists"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert list(pathlib.Path(plan.artifact_directory).glob("*.json")) == [
        first_artifact
    ]


def test_completed_route_step_cannot_be_replayed_at_the_same_history_index(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    first_plan = _plan(tmp_path, manifest)
    first = execute_route_acquisition(manifest, manifest.route_history[-1], first_plan)
    second_plan = _plan(
        tmp_path,
        first.manifest,
        acquisition_id="acq-" + "2" * 32,
        output_name="second.json",
    )
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("replay must not execute"),
    )

    with pytest.raises(ValueError, match="already has acquired evidence"):
        execute_route_acquisition(
            first.manifest,
            first.manifest.route_history[-1],
            second_plan,
        )
    assert not pathlib.Path(second_plan.output_path).exists()


def test_plan_loader_is_schema_strict_and_rejects_duplicate_or_unknown_actions(
    tmp_path: pathlib.Path,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    restored = load_route_acquisition_plan(
        io.StringIO(strict_json_dumps(plan.to_dict()))
    )
    assert restored.to_dict() == plan.to_dict()

    with pytest.raises(ValueError, match="unknown fields"):
        RouteAcquisitionPlan.from_dict({**plan.to_dict(), "shell": True})

    duplicate = strict_json_dumps(plan.to_dict()).replace(
        '"run_static":{',
        '"run_static":{},"run_static":{',
    )
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        load_route_acquisition_plan(io.StringIO(duplicate))

    semantic = plan.to_dict()
    semantic["requests"] = {
        "run_semantic": _request(tmp_path / "workspace").to_dict()
    }
    with pytest.raises(ValueError, match="requires evidence kind 'semantic'"):
        RouteAcquisitionPlan.from_dict(semantic)
    semantic["requests"] = {
        "run_semantic": _request(
            tmp_path / "workspace",
            kind=EvidenceKind.SEMANTIC,
        ).to_dict()
    }
    restored_semantic = RouteAcquisitionPlan.from_dict(semantic)
    assert restored_semantic.requests[RouteAction.RUN_SEMANTIC].kind == EvidenceKind.SEMANTIC


def test_preallocated_acquisition_id_must_be_safe_and_immutable(
    tmp_path: pathlib.Path,
) -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="acquisition_id must have the form"):
        _plan(tmp_path, manifest, acquisition_id="../../reused")


def test_existing_output_reservation_prevents_concurrent_duplicate_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    output = pathlib.Path(plan.output_path)
    reservation = output.parent / f".{output.name}.lock"
    reservation.write_text("held\n", encoding="utf-8")
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("reserved step must not execute"),
    )

    with pytest.raises(FileExistsError, match="already reserved"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not output.exists()
    assert not list(pathlib.Path(plan.artifact_directory).glob("*.json"))
    assert not list(
        pathlib.Path(plan.coordination_directory).glob(".decision-*.lock")
    )


def test_coordination_directory_must_be_disjoint_from_workspace(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    inside = pathlib.Path(plan.workspace_root) / "coordination"
    inside.mkdir()
    invalid = replace(
        plan,
        coordination_directory=str(inside),
        artifact_directory=str(inside / "artifacts"),
        output_path=str(inside / "updated.json"),
    )
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("invalid state path must not execute"),
    )

    with pytest.raises(ValueError, match="outside workspace_root"):
        execute_route_acquisition(manifest, manifest.route_history[-1], invalid)
    assert not (inside / "artifacts").exists()


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        ("artifact_directory", "artifact_directory must be under"),
        ("output_path", "output_path must be under"),
    ],
)
def test_artifact_and_output_paths_must_stay_under_coordination_directory(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    message: str,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    outside = tmp_path / f"outside-{field_name}"
    invalid = (
        replace(plan, artifact_directory=str(outside))
        if field_name == "artifact_directory"
        else replace(plan, output_path=str(outside))
    )
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("escaped state path must not execute"),
    )

    with pytest.raises(ValueError, match=message):
        execute_route_acquisition(manifest, manifest.route_history[-1], invalid)
    assert not outside.exists()


def test_successful_decision_claim_blocks_a_different_output_and_id(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    first_plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence
    calls = 0

    def counted_acquire(request, *, artifact_directory, acquisition_id=None):
        nonlocal calls
        calls += 1
        return real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", counted_acquire)
    execute_route_acquisition(manifest, manifest.route_history[-1], first_plan)
    second_plan = _plan(
        tmp_path,
        manifest,
        acquisition_id="acq-" + "2" * 32,
        output_name="different-output.json",
    )

    with pytest.raises(FileExistsError, match="route decision is already reserved"):
        execute_route_acquisition(manifest, manifest.route_history[-1], second_plan)
    assert calls == 1
    assert not pathlib.Path(second_plan.output_path).exists()
    assert not (
        pathlib.Path(second_plan.artifact_directory)
        / f"{second_plan.acquisition_id}.json"
    ).exists()


def test_output_appearance_during_prepared_publication_is_not_overwritten(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    output = pathlib.Path(plan.output_path)
    real_link = verification_orchestrate.os.link

    def racing_link(source, destination, *args, **kwargs):
        pathlib.Path(destination).write_text("contender-owned\n", encoding="utf-8")
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(verification_orchestrate.os, "link", racing_link)
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("publication race must not execute"),
    )

    with pytest.raises(FileExistsError, match="appeared before prepared intent"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert output.read_text(encoding="utf-8") == "contender-owned\n"
    assert not output.parent.joinpath(f".{output.name}.lock").exists()
    assert not list(
        pathlib.Path(plan.coordination_directory).glob(".decision-*.lock")
    )
    assert not list(output.parent.glob(f".{output.name}.*.tmp"))


def test_prepared_intent_write_failure_releases_prelaunch_reservations(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    output = pathlib.Path(plan.output_path)

    def fail_prepared_write(path: pathlib.Path, content: str) -> None:
        raise OSError("fixture prepared-intent failure")

    monkeypatch.setattr(verification_orchestrate, "_atomic_create", fail_prepared_write)
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("failed intent must not execute"),
    )

    with pytest.raises(OSError, match="fixture prepared-intent failure"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not output.exists()
    assert not output.parent.joinpath(f".{output.name}.lock").exists()
    assert not list(
        pathlib.Path(plan.coordination_directory).glob(".decision-*.lock")
    )


def test_prelaunch_reservation_hash_failure_releases_owned_reservations(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    output = pathlib.Path(plan.output_path)

    def fail_reservation_hash(path: pathlib.Path) -> str:
        raise OSError("fixture reservation hash failure")

    monkeypatch.setattr(
        verification_orchestrate,
        "_file_sha256",
        fail_reservation_hash,
    )
    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        lambda *args, **kwargs: pytest.fail("hash failure must not execute"),
    )

    with pytest.raises(OSError, match="fixture reservation hash failure"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert not output.exists()
    assert not output.parent.joinpath(f".{output.name}.lock").exists()
    assert not list(
        pathlib.Path(plan.coordination_directory).glob(".decision-*.lock")
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data.__setitem__("privileged_inputs", ["hidden-tests"]),
            "cannot declare privileged inputs",
        ),
        (
            lambda data: data.__setitem__("candidate_probability", 0.9),
            "unsupported scoring metadata",
        ),
        (
            lambda data: data.__setitem__("verifier_validity", 0.5),
            "verifier_validity does not match",
        ),
        (
            lambda data: data["cost"].__setitem__("cpu_seconds", 1.0),
            "unmeasured cost dimensions",
        ),
        (
            lambda data: data["metadata"].__setitem__("runner", "forged"),
            "runner identity does not match",
        ),
        (
            lambda data: data["metadata"].__setitem__("extra", True),
            "metadata envelope does not match",
        ),
        (
            lambda data: data["metadata"].__setitem__("return_code", False),
            "observation return_code is malformed",
        ),
        (
            lambda data: data["metadata"].__setitem__("stdout_truncated", 0),
            "stdout truncation contradicts observation",
        ),
        (
            lambda data: data["metadata"]["capture_bindings"][
                "stdout"
            ].__setitem__("truncated", 0),
            "stdout capture binding is malformed",
        ),
        (
            lambda data: data["metadata"].__setitem__("capture_incomplete", 0),
            "capture_incomplete is malformed",
        ),
    ],
)
def test_forged_observation_envelope_is_rejected_before_manifest_insertion(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        data = observation.to_dict()
        mutation(data)
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match=message):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
    assert manifest.evidence == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda raw: raw.__setitem__("schema_version", "forged"),
            "artifact schema_version does not match",
        ),
        (
            lambda raw: raw.__setitem__("acquisition_id", "acq-" + "f" * 32),
            "artifact acquisition_id does not match",
        ),
        (
            lambda raw: raw.__setitem__("request_sha256", "f" * 64),
            "artifact request_sha256 does not match",
        ),
        (
            lambda raw: raw.__setitem__("kind", "full_execution"),
            "artifact evidence kind does not match",
        ),
        (
            lambda raw: raw.__setitem__("source", "forged-source"),
            "artifact source identity does not match",
        ),
        (
            lambda raw: raw.__setitem__("source_version", "forged-version"),
            "artifact source identity does not match",
        ),
        (
            lambda raw: raw.__setitem__("argv", ["forged-command"]),
            "artifact argv does not match",
        ),
        (
            lambda raw: raw.__setitem__("workspace_root", "/forged-workspace"),
            "artifact workspace_root is not canonical or bound",
        ),
        (
            lambda raw: raw.__setitem__("working_directory", "forged-directory"),
            "artifact working_directory is not canonical or bound",
        ),
        (
            lambda raw: raw["runner"].__setitem__("version", "forged"),
            "artifact runner identity does not match",
        ),
        (
            lambda raw: raw["execution"].__setitem__("timeout_seconds", "2.0"),
            "artifact timeout binding does not match",
        ),
        (
            lambda raw: raw["execution"].__setitem__(
                "supports_correct_exit_codes",
                [False],
            ),
            "artifact exit-code bindings do not match",
        ),
        (
            lambda raw: raw["execution"].__setitem__("shell", True),
            "artifact isolation bindings do not match",
        ),
        (
            lambda raw: raw["execution"].__setitem__(
                "started_at",
                "not-a-timestampZ",
            ),
            "artifact started_at must be a canonical UTC timestamp",
        ),
        (
            lambda raw: raw["execution"].__setitem__("setup_error", []),
            "artifact setup_error is malformed",
        ),
        (
            lambda raw: raw["execution"].__setitem__(
                "supplied_environment_keys",
                ["LB_API_KEY"],
            ),
            "artifact supplied environment keys are malformed",
        ),
        (
            lambda raw: raw["stdout"].__setitem__("captured_bytes", 0),
            "artifact stdout capture bound is invalid",
        ),
        (
            lambda raw: raw["stdout"].__setitem__("sha256", "f" * 64),
            "artifact stdout capture contradicts observation",
        ),
        (
            lambda raw: raw["execution"].__setitem__("outcome", []),
            "artifact outcome is malformed",
        ),
        (
            lambda raw: raw["execution"].__setitem__("timed_out", True),
            "execution outcome is internally inconsistent",
        ),
    ],
)
def test_forged_raw_artifact_bindings_are_rejected_after_digest_rebinding(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        return _rewrite_raw_artifact(
            observation,
            pathlib.Path(artifact_directory),
            mutation,
        )

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match=message):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)

    prepared = strict_json_loads(
        pathlib.Path(plan.output_path).read_text(encoding="utf-8")
    )
    assert prepared["state"] == "prepared"
    assert manifest.evidence == []


def test_pre_environment_setup_failure_is_a_valid_inconclusive_acquisition(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)

    def fail_temporary_environment(*args, **kwargs):
        raise OSError("fixture temporary environment failure")

    monkeypatch.setattr(
        verification_acquire.tempfile,
        "TemporaryDirectory",
        fail_temporary_environment,
    )
    result = execute_route_acquisition(
        manifest,
        manifest.route_history[-1],
        plan,
    )

    assert result.observation.status == EvidenceStatus.INCONCLUSIVE
    assert result.observation.metadata["outcome"] == "setup_failure"
    artifact = strict_json_loads(
        (
            pathlib.Path(plan.artifact_directory)
            / f"{plan.acquisition_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact["execution"]["supplied_environment_keys"] == []


def test_capture_failure_downgrade_requires_a_recorded_failure_binding(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        rebound = _rewrite_raw_artifact(
            observation,
            pathlib.Path(artifact_directory),
            lambda raw: raw["execution"].__setitem__(
                "outcome",
                "capture_or_cleanup_failure",
            ),
        )
        data = rebound.to_dict()
        data["status"] = "inconclusive"
        data["verifier_validity"] = 0.0
        metadata = data["metadata"]
        assert isinstance(metadata, dict)
        metadata["outcome"] = "capture_or_cleanup_failure"
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match="execution outcome is internally inconsistent"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_setup_failure_cannot_contain_launched_process_state(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )

        def forge_setup_state(raw: dict[str, Any]) -> None:
            execution = raw["execution"]
            execution["outcome"] = "setup_failure"
            execution["setup_error"] = "forged setup error"
            execution["timed_out"] = True
            execution["residual_process_group"] = True
            execution["capture_incomplete"] = True
            execution["return_code"] = None

        rebound = _rewrite_raw_artifact(
            observation,
            pathlib.Path(artifact_directory),
            forge_setup_state,
        )
        data = rebound.to_dict()
        data["status"] = "inconclusive"
        data["verifier_validity"] = 0.0
        metadata = data["metadata"]
        assert isinstance(metadata, dict)
        metadata["outcome"] = "setup_failure"
        metadata["return_code"] = None
        metadata["capture_incomplete"] = True
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match="setup failure contains launched-process state"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_signaled_outcome_requires_a_negative_return_code(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def forged_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )

        def forge_missing_return_code(raw: dict[str, Any]) -> None:
            raw["execution"]["outcome"] = "signaled"
            raw["execution"]["return_code"] = None

        rebound = _rewrite_raw_artifact(
            observation,
            pathlib.Path(artifact_directory),
            forge_missing_return_code,
        )
        data = rebound.to_dict()
        data["status"] = "inconclusive"
        data["verifier_validity"] = 0.0
        metadata = data["metadata"]
        assert isinstance(metadata, dict)
        metadata["outcome"] = "signaled"
        metadata["return_code"] = None
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", forged_acquire)
    with pytest.raises(ValueError, match="non-timeout execution is missing return_code"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_raw_artifact_must_use_the_acquisition_id_bound_filename(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def renamed_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        artifact = pathlib.Path(artifact_directory) / f"{observation.acquisition_id}.json"
        renamed = artifact.with_name("forged-name.json")
        artifact.rename(renamed)
        data = observation.to_dict()
        metadata = data["metadata"]
        assert isinstance(metadata, dict)
        metadata["artifact_locator"] = renamed.as_uri()
        return EvidenceObservation.from_dict(data)

    monkeypatch.setattr(verification_orchestrate, "acquire_evidence", renamed_acquire)
    with pytest.raises(ValueError, match="path is not bound to acquisition_id"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_artifact_directory_cannot_be_rebound_after_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def rebound_directory_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        original = pathlib.Path(artifact_directory)
        moved = original.with_name("moved-artifacts")
        original.rename(moved)
        try:
            original.symlink_to(moved, target_is_directory=True)
        except OSError as exc:  # pragma: no cover - depends on Windows policy
            pytest.skip(f"symlinks unavailable: {exc}")
        return observation

    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        rebound_directory_acquire,
    )
    with pytest.raises(ValueError, match="artifact_directory changed"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_output_parent_cannot_be_rebound_after_execution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest, output_name="outputs/updated.json")
    real_acquire = verification_orchestrate.acquire_evidence

    def rebound_output_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        output_parent = pathlib.Path(plan.output_path).parent
        moved = tmp_path / "moved-output-parent"
        output_parent.rename(moved)
        try:
            output_parent.symlink_to(moved, target_is_directory=True)
        except OSError as exc:  # pragma: no cover - depends on Windows policy
            pytest.skip(f"symlinks unavailable: {exc}")
        return observation

    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        rebound_output_acquire,
    )
    with pytest.raises(ValueError, match="orchestration output changed"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)


def test_duplicate_json_key_in_raw_artifact_is_rejected_after_digest_rebinding(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    plan = _plan(tmp_path, manifest)
    real_acquire = verification_orchestrate.acquire_evidence

    def duplicate_key_acquire(request, *, artifact_directory, acquisition_id=None):
        observation = real_acquire(
            request,
            artifact_directory=artifact_directory,
            acquisition_id=acquisition_id,
        )
        artifact = pathlib.Path(artifact_directory) / f"{observation.acquisition_id}.json"
        original = artifact.read_text(encoding="utf-8")
        duplicated = original.replace(
            '  "schema_version":',
            '  "schema_version": "duplicate",\n  "schema_version":',
            1,
        )
        assert duplicated != original
        artifact_bytes = duplicated.encode("utf-8")
        artifact.write_bytes(artifact_bytes)
        return _rebind_artifact_observation(observation, artifact_bytes)

    monkeypatch.setattr(
        verification_orchestrate,
        "acquire_evidence",
        duplicate_key_acquire,
    )
    with pytest.raises(ValueError, match="duplicate JSON object key 'schema_version'"):
        execute_route_acquisition(manifest, manifest.route_history[-1], plan)
