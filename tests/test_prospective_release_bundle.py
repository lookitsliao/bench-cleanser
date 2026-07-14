"""Adversarial tests for the externally anchored structural StudyBundle."""

from __future__ import annotations

import hashlib
import inspect
import pathlib
from dataclasses import dataclass, replace
from typing import Any

import pytest

from bench_cleanser.verification._io import strict_json_dumps
from bench_cleanser.verification.models import EvidenceKind
from experiments.prospective_pilot.dispatcher import ProspectiveDispatcher
from experiments.prospective_pilot.ledger import ProspectiveLedger, ReservationRequest
from experiments.prospective_pilot.release_bundle import (
    BUNDLE_DIGEST_CONTRACT,
    STRUCTURAL_BUNDLE_SCHEMA_VERSION,
    TASK_TRAJECTORY_DIGEST_CONTRACT,
    TRAJECTORY_DIGEST_CONTRACT,
    AuditedLedgerSnapshot,
    BoundReleaseArtifact,
    ReleaseBundleError,
    build_ledger_export_trust_anchor,
    compile_prospective_release,
    load_audited_export,
    write_prospective_release_bundle,
)
from experiments.prospective_pilot.scheduler import (
    COLLECTION_ACTION_IDS,
    SchedulerBindings,
    TaskSelectionDecision,
    build_task_round_decision,
    build_task_selection_decision,
    load_study_bindings,
)
from tests.test_prospective_dispatcher import (
    _candidate_input,
    _catalog,
    _generic_spec,
    _initial_manifest,
    _make_spec,
    _timestamp,
)
from tests.test_prospective_ledger import (
    _preimages as _generic_preimages,
)
from tests.test_prospective_ledger import (
    _reservations as _generic_reservations,
)
from tests.test_prospective_ledger import (
    _round_zero as _generic_round_zero,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TYPED_INITIAL_ACTIONS = (
    "full_primary",
    "semantic_primary",
    "targeted_primary",
)


@pytest.fixture(scope="module")
def bindings() -> SchedulerBindings:
    return load_study_bindings(ROOT)


@dataclass(frozen=True)
class _TypedRoundFixture:
    ledger: ProspectiveLedger
    round_decision: Any
    specs_by_digest: dict[str, Any]


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(strict_json_dumps(value).encode("utf-8")).hexdigest()


def _typed_round_fixture(
    root: pathlib.Path,
    bindings: SchedulerBindings,
    task_id: str,
    *,
    terminal_only: bool = False,
) -> _TypedRoundFixture:
    base_catalog = _catalog()
    launch_marker = (root / "launches.txt").resolve()
    specs_by_digest: dict[str, Any] = {}
    preimages = {
        hashlib.sha256(_generic_spec(action_id)).hexdigest(): _generic_spec(action_id)
        for action_id in COLLECTION_ACTION_IDS
    }
    candidates = []
    for candidate_id in bindings.frame.candidate_ids_for(task_id):
        manifest = _initial_manifest(task_id, candidate_id)
        catalog = base_catalog
        for action_id in _TYPED_INITIAL_ACTIONS:
            offer = next(item for item in catalog if item.action_id == action_id)
            spec = _make_spec(
                root,
                action_id=action_id,
                offer=offer,
                initial=manifest,
                launch_marker=launch_marker,
                salt=f"{candidate_id[-8:]}-{action_id}",
            )
            digest = spec.canonical_digest()
            specs_by_digest[digest] = spec
            preimages[digest] = spec.canonical_preimage()
            catalog = tuple(
                replace(item, action_spec_sha256=digest) if item.action_id == action_id else item
                for item in catalog
            )
        if terminal_only:
            catalog = tuple(
                replace(
                    item,
                    available=False,
                    availability_reason=(
                        "semantic_binding_unavailable"
                        if item.action_id == "semantic_primary"
                        else "execution_binding_unavailable"
                    ),
                )
                if item.action_id
                in {
                    "semantic_primary",
                    "targeted_primary",
                    "full_primary",
                    "full_repeat",
                }
                else item
                for item in catalog
            )
        candidates.append(_candidate_input(manifest, catalog))

    round_decision = build_task_round_decision(
        bindings=bindings,
        task_id=task_id,
        scheduled_at=_timestamp(0),
        candidates=tuple(candidates),
    )
    reservations = []
    for scheduled in round_decision.scheduled_decisions:
        decision = scheduled.logged_policy_decision
        if decision.terminal:
            continue
        assert decision.acquisition_id is not None
        spec = specs_by_digest[decision.chosen_offer.action_spec_sha256]
        reservations.append(
            ReservationRequest(
                acquisition_id=decision.acquisition_id,
                resource_kind=spec.resource_kind,
                resource_key=spec.resource_key,
                details=spec.reservation_details(),
            )
        )
    used_digests = {
        offer.action_spec_sha256
        for candidate in round_decision.candidates
        for offer in candidate.action_catalog
    }
    ledger = ProspectiveLedger(root / "ledger.sqlite3", bindings=bindings)
    ledger.commit_round(
        round_decision,
        committed_at=_timestamp(1),
        action_spec_preimages={digest: preimages[digest] for digest in used_digests},
        reservations=tuple(reservations),
    )
    return _TypedRoundFixture(
        ledger=ledger,
        round_decision=round_decision,
        specs_by_digest=specs_by_digest,
    )


def _commit_selection(
    fixture: _TypedRoundFixture,
    bindings: SchedulerBindings,
) -> TaskSelectionDecision:
    selection = build_task_selection_decision(
        (fixture.round_decision,),
        bindings=bindings,
        scheduled_at=_timestamp(2),
    )
    fixture.ledger.commit_selection(selection, committed_at=_timestamp(3))
    return selection


def _snapshot(
    root: pathlib.Path,
    ledger: ProspectiveLedger,
    bindings: SchedulerBindings,
) -> AuditedLedgerSnapshot:
    export_path = root / "ledger.jsonl"
    export_path.write_text(ledger.export_jsonl(), encoding="utf-8")
    anchor_bytes, anchor_sha256 = build_ledger_export_trust_anchor(
        export_path,
        bindings=bindings,
        artifact_id="fixture-prospective-ledger",
        attestor_id="fixture-release-attestor",
    )
    anchor_path = root / "ledger.anchor.json"
    anchor_path.write_bytes(anchor_bytes)
    return load_audited_export(
        export_path,
        anchor_path,
        expected_trust_anchor_sha256=anchor_sha256,
        bindings=bindings,
    )


def test_external_anchor_rejects_a_valid_self_rehashed_replacement(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    first = _typed_round_fixture(
        tmp_path / "first",
        bindings,
        "django__django-11555",
        terminal_only=True,
    )
    _commit_selection(first, bindings)
    first_snapshot = _snapshot(tmp_path / "first", first.ledger, bindings)

    second = _typed_round_fixture(tmp_path / "second", bindings, "django__django-11299")
    second_export = tmp_path / "second" / "ledger.jsonl"
    second_export.write_text(second.ledger.export_jsonl(), encoding="utf-8")
    second_anchor, second_anchor_sha = build_ledger_export_trust_anchor(
        second_export,
        bindings=bindings,
        artifact_id="fixture-prospective-ledger",
        attestor_id="fixture-release-attestor",
    )
    second_anchor_path = tmp_path / "second" / "ledger.anchor.json"
    second_anchor_path.write_bytes(second_anchor)

    assert second_anchor_sha != first_snapshot.trust_anchor_sha256
    with pytest.raises(ReleaseBundleError, match="independently pinned digest"):
        load_audited_export(
            second_export,
            second_anchor_path,
            expected_trust_anchor_sha256=first_snapshot.trust_anchor_sha256,
            bindings=bindings,
        )


def test_terminal_at_step_zero_and_task_selection_are_in_trajectory_digest(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _typed_round_fixture(
        tmp_path,
        bindings,
        "django__django-11555",
        terminal_only=True,
    )
    assert fixture.round_decision.completes_candidate_chains is True
    selection = _commit_selection(fixture, bindings)
    snapshot = _snapshot(tmp_path, fixture.ledger, bindings)
    bundle = compile_prospective_release(snapshot)
    repeated = compile_prospective_release(snapshot)
    assert bundle.bundle_sha256 == repeated.bundle_sha256
    assert bundle.canonical_json() == repeated.canonical_json()

    payload = bundle.to_dict()
    task = next(item for item in payload["tasks"] if item["task_id"] == selection.task_id)
    candidates = [item for item in payload["candidates"] if item["task_id"] == selection.task_id]
    assert task["status"] == "abstained"
    assert task["task_selection_sha256"] == selection.decision_sha256
    assert task["task_trajectory_action_log_propensities"] == list(
        selection.final_task_action_log_propensities
    )
    assert task["task_trajectory_probability"] == selection.final_task_trajectory_probability
    assert (
        task["task_trajectory_log_probability"] == selection.final_task_trajectory_log_probability
    )
    assert len(candidates) == 3
    assert all(item["decision_count"] == 1 for item in candidates)
    assert all(item["acquisition_count"] == 0 for item in candidates)
    assert all(item["decisions"][0]["terminal"] is True for item in candidates)
    assert all(item["decisions"][0]["result"] is None for item in candidates)
    assert all(item["task_selection_sha256"] == selection.decision_sha256 for item in candidates)

    candidate = candidates[0]
    decision = candidate["decisions"][0]
    material = {
        "contract": TRAJECTORY_DIGEST_CONTRACT,
        "task_id": candidate["task_id"],
        "candidate_id": candidate["candidate_id"],
        "decision_sha256s": [decision["decision_sha256"]],
        "trajectory_head_sha256s": [decision["trajectory_head_sha256"]],
        "result_ids": [],
        "incident_ids": [],
        "nonterminal_provisioning_receipt_sha256s": [],
        "resolved_execution_provisioning": [],
        "terminal_decision_sha256": decision["decision_sha256"],
        "terminal_action": decision["route_action"],
        "task_selection_sha256": selection.decision_sha256,
        "selected_candidate_id": None,
    }
    assert candidate["candidate_trajectory_sha256"] == _sha256_json(material)
    assert (
        _sha256_json({**material, "terminal_action": "accept"})
        != (candidate["candidate_trajectory_sha256"])
    )
    assert (
        _sha256_json({**material, "task_selection_sha256": "0" * 64})
        != (candidate["candidate_trajectory_sha256"])
    )

    task_material = {
        "contract": TASK_TRAJECTORY_DIGEST_CONTRACT,
        "task_id": task["task_id"],
        "candidate_trajectory_sha256s": task["candidate_trajectory_sha256s"],
        "task_selection_sha256": selection.decision_sha256,
        "selected_candidate_id": None,
        "task_trajectory_action_log_propensities": list(
            selection.final_task_action_log_propensities
        ),
        "task_trajectory_probability": selection.final_task_trajectory_probability,
        "task_trajectory_log_probability": (selection.final_task_trajectory_log_probability),
    }
    assert task["task_trajectory_sha256"] == _sha256_json(task_material)
    assert (
        _sha256_json(
            {
                **task_material,
                "task_trajectory_log_probability": (
                    selection.final_task_trajectory_log_probability + 1.0
                ),
            }
        )
        != task["task_trajectory_sha256"]
    )

    forbidden_overrides = {
        "action",
        "cost",
        "execution_count",
        "policy_id",
        "seed",
        "subgroup",
        "truth",
    }
    assert forbidden_overrides.isdisjoint(inspect.signature(compile_prospective_release).parameters)
    assert payload["profile"] == "STRUCTURAL"
    assert STRUCTURAL_BUNDLE_SCHEMA_VERSION == "verification-gap-study-bundle-0.2.0"
    assert TRAJECTORY_DIGEST_CONTRACT == "verification-gap-candidate-trajectory-v2"
    assert TASK_TRAJECTORY_DIGEST_CONTRACT == "verification-gap-task-trajectory-v2"
    assert BUNDLE_DIGEST_CONTRACT == "verification-gap-structural-study-bundle-v2"
    assert payload["schema_version"] == STRUCTURAL_BUNDLE_SCHEMA_VERSION
    assert payload["contract"] == BUNDLE_DIGEST_CONTRACT
    assert payload["scientific_release_ready"] is False
    assert payload["profiles"]["LOGGED_POLICY_EVALUABLE"]["eligible"] is False


def test_generic_action_preimage_is_rejected_even_when_ledger_audit_accepts_it(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    round_decision = _generic_round_zero(bindings, "django__django-11555")
    assert not round_decision.completes_candidate_chains
    ledger = ProspectiveLedger(tmp_path / "ledger.sqlite3", bindings=bindings)
    ledger.commit_round(
        round_decision,
        committed_at=_timestamp(1),
        action_spec_preimages=_generic_preimages(),
        reservations=_generic_reservations(round_decision),
    )
    assert ledger.audit().complete is False
    snapshot = _snapshot(tmp_path, ledger, bindings)

    with pytest.raises(ReleaseBundleError, match="not a typed executable action spec"):
        compile_prospective_release(snapshot)


def test_partial_frame_is_explicit_and_deterministic(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _typed_round_fixture(tmp_path, bindings, "django__django-11299")
    assert not fixture.round_decision.completes_candidate_chains
    snapshot = _snapshot(tmp_path, fixture.ledger, bindings)
    bundle = compile_prospective_release(snapshot)
    payload = bundle.to_dict()

    assert payload["ledger_audit"]["complete"] is False
    assert payload["ledger_audit"]["analysis_ready"] is False
    assert payload["ledger_audit"]["pending_dispatch_count"] > 0
    assert payload["frame"]["task_status_counts"]["incomplete"] == 1
    assert payload["frame"]["task_status_counts"]["unstarted"] == 21
    started_task = next(
        item for item in payload["tasks"] if item["task_id"] == fixture.round_decision.task_id
    )
    assert started_task["task_trajectory_action_log_propensities"] == list(
        fixture.round_decision.task_trajectory_action_log_propensities
    )
    assert (
        started_task["task_trajectory_probability"]
        == fixture.round_decision.task_trajectory_probability
    )
    assert (
        started_task["task_trajectory_log_probability"]
        == fixture.round_decision.task_trajectory_log_probability
    )
    unstarted_task = next(item for item in payload["tasks"] if item["status"] == "unstarted")
    assert unstarted_task["task_trajectory_action_log_propensities"] == []
    assert unstarted_task["task_trajectory_probability"] == 1.0
    assert unstarted_task["task_trajectory_log_probability"] == 0.0
    assert (
        "behavior_ledger_does_not_cover_complete_frozen_frame" in (payload["activation_blockers"])
    )
    assert payload["protocol_artifact_audit"]["behavior_available_offer_count"] > 0
    assert payload["protocol_artifact_audit"]["reopened_protocol_result_count"] == 0
    assert any(
        item["status"] == "pending_acquisition"
        for item in payload["candidates"]
        if item["task_id"] == "django__django-11299"
    )


def test_retained_artifact_is_reopened_and_mutation_fails_closed(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _typed_round_fixture(tmp_path, bindings, "django__django-11299")
    scheduled = next(
        item
        for item in fixture.round_decision.scheduled_decisions
        if not item.logged_policy_decision.terminal
    )
    decision = scheduled.logged_policy_decision
    assert decision.acquisition_id is not None
    outcome = ProspectiveDispatcher(
        fixture.ledger,
        claimant="release-bundle-fixture-worker",
    ).dispatch_committed(
        acquisition_id=decision.acquisition_id,
        claimed_at=_timestamp(4),
        completed_at=_timestamp(5),
    )
    assert outcome.state == "completed"
    snapshot = _snapshot(tmp_path, fixture.ledger, bindings)
    payload = compile_prospective_release(snapshot).to_dict()
    assert payload["protocol_artifact_audit"]["reopened_protocol_result_count"] == 1

    candidate = next(
        item for item in payload["candidates"] if item["candidate_id"] == decision.candidate_id
    )
    result = next(item["result"] for item in candidate["decisions"] if item["result"] is not None)
    projected_decision = next(item for item in candidate["decisions"] if item["result"] is not None)
    spec = fixture.specs_by_digest[decision.chosen_offer.action_spec_sha256]
    provisioning_receipt = {
        "receipt_sha256": spec.provisioning_receipt.receipt_sha256,
        "provisioner_id": spec.provisioning_receipt.provisioner_id,
        "provisioner_version": spec.provisioning_receipt.provisioner_version,
        "architecture": spec.provisioning_receipt.architecture,
        "substrate": spec.provisioning_receipt.substrate,
        "image_digest": spec.provisioning_receipt.image_digest,
    }
    assert decision.chosen_offer.evidence_kind == EvidenceKind.FULL_EXECUTION
    assert projected_decision["provisioning_receipt"] == provisioning_receipt
    assert result["provisioning_receipt"] == provisioning_receipt
    assert candidate["execution_acquisition_count"] == 1
    assert candidate["full_execution_acquisition_count"] == 1
    assert candidate["execution_substrate_counts"] == {"local-fixture": 1}
    assert candidate["image_bound_execution_acquisition_count"] == 1
    assert "full_container_acquisition_count" not in candidate
    assert result["cost_dimension_status"]["wall_seconds"] == "measured"
    assert result["cost_dimension_status"]["storage_bytes"] == "measured"
    assert result["cost_dimension_status"]["cpu_seconds"] == "unreported_zero"

    trajectory_material = {
        "contract": TRAJECTORY_DIGEST_CONTRACT,
        "task_id": candidate["task_id"],
        "candidate_id": candidate["candidate_id"],
        "decision_sha256s": [projected_decision["decision_sha256"]],
        "trajectory_head_sha256s": [projected_decision["trajectory_head_sha256"]],
        "result_ids": [result["result_id"]],
        "incident_ids": [],
        "nonterminal_provisioning_receipt_sha256s": [provisioning_receipt["receipt_sha256"]],
        "resolved_execution_provisioning": [
            {"result_id": result["result_id"], **provisioning_receipt}
        ],
        "terminal_decision_sha256": None,
        "terminal_action": None,
        "task_selection_sha256": None,
        "selected_candidate_id": None,
    }
    assert candidate["candidate_trajectory_sha256"] == _sha256_json(trajectory_material)
    changed_provisioning = {
        **provisioning_receipt,
        "substrate": "different-substrate",
    }
    assert (
        _sha256_json(
            {
                **trajectory_material,
                "resolved_execution_provisioning": [
                    {"result_id": result["result_id"], **changed_provisioning}
                ],
            }
        )
        != candidate["candidate_trajectory_sha256"]
    )

    artifact = pathlib.Path(spec.artifact_retention.artifact_directory) / (
        f"{decision.acquisition_id}.json"
    )
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    with pytest.raises(ReleaseBundleError, match="artifact bytes differ"):
        compile_prospective_release(snapshot)


def test_bound_inputs_are_reopened_and_bundle_publication_is_immutable(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _typed_round_fixture(
        tmp_path / "study",
        bindings,
        "django__django-11555",
        terminal_only=True,
    )
    _commit_selection(fixture, bindings)
    snapshot = _snapshot(tmp_path / "study", fixture.ledger, bindings)
    registry_path = tmp_path / "candidate-registry.json"
    registry_path.write_text("{}\n", encoding="utf-8")
    registry = BoundReleaseArtifact(
        logical_name="candidate_registry",
        path=registry_path,
        expected_sha256=hashlib.sha256(registry_path.read_bytes()).hexdigest(),
    )
    bundle = compile_prospective_release(snapshot, candidate_registry=registry)
    output = tmp_path / f"verification-gap-{bundle.bundle_sha256}.json"
    write_prospective_release_bundle(bundle, output)
    assert output.read_text(encoding="utf-8") == bundle.canonical_json()
    with pytest.raises(ReleaseBundleError, match="never replaced"):
        write_prospective_release_bundle(bundle, output)
    with pytest.raises(ReleaseBundleError, match="filename must contain"):
        write_prospective_release_bundle(bundle, tmp_path / "bundle.json")

    registry_path.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(ReleaseBundleError, match="differs from its pinned digest"):
        compile_prospective_release(snapshot, candidate_registry=registry)
