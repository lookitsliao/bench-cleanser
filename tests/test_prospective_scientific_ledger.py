"""Adversarial tests for the separate prospective scientific ledger."""

from __future__ import annotations

import hashlib
import hmac
import os
import pathlib
import sqlite3
from dataclasses import replace
from typing import Any, cast

import pytest

from bench_cleanser.verification._io import strict_json_loads
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    RouteAction,
)
from bench_cleanser.verification.policy_log import RouterRouteStep
from experiments.prospective_pilot.scientific_ledger import (
    AppendReceipt,
    BootstrapReceipt,
    CuratorReceipt,
    ResourceCeilingExceeded,
    ResourceLimits,
    ResourceOutcome,
    ResourceReservation,
    ResourceSettlement,
    ResourceUsage,
    ScientificLedger,
    ScientificLedgerBindings,
    ScientificLedgerConflict,
    ScientificLedgerError,
    SignatureVerifier,
    VerifierAttestation,
    load_scientific_ledger_bindings,
    signed_envelope_bytes,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
TASK_A = "project__project-100"
TASK_B = "project__project-200"
CANDIDATE_A = f"sha256:{'a' * 64}"
CANDIDATE_B = f"sha256:{'b' * 64}"
CANDIDATE_C = f"sha256:{'c' * 64}"
CANDIDATE_D = f"sha256:{'d' * 64}"
T0 = "2026-07-14T00:00:00.000000Z"
T1 = "2026-07-14T00:01:00.000000Z"
T2 = "2026-07-14T00:02:00.000000Z"
T3 = "2026-07-14T00:03:00.000000Z"
_SECRET = b"scientific-ledger-test-verifier-secret"
_SCIENTIFIC_RECORDS_NO_UPDATE_TRIGGER_SQL = (
    "CREATE TRIGGER scientific_records_no_update "
    "BEFORE UPDATE ON scientific_records "
    "BEGIN SELECT RAISE(ABORT, 'scientific records are append-only'); END"
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class _HmacVerifier(SignatureVerifier):
    def __init__(self, *, verified_at: str = T3) -> None:
        self.verified_at = verified_at

    def verify(
        self,
        *,
        subject: bytes,
        signature: bytes,
        signature_scheme: str,
        signer_id: str,
        key_id: str,
    ) -> VerifierAttestation:
        if signature_scheme != "hmac-sha256-test":
            raise ValueError("wrong scheme")
        expected = hmac.digest(_SECRET, subject, "sha256")
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        return VerifierAttestation(
            verifier_id="fixture-verifier",
            verifier_version="v1",
            verification_artifact_sha256=hashlib.sha256(
                b"verified\0"
                + subject
                + b"\0"
                + signature
                + b"\0"
                + signer_id.encode()
                + b"\0"
                + key_id.encode()
            ).hexdigest(),
            verified_at=self.verified_at,
        )


class _UnavailableVerifier(SignatureVerifier):
    def verify(
        self,
        *,
        subject: bytes,
        signature: bytes,
        signature_scheme: str,
        signer_id: str,
        key_id: str,
    ) -> VerifierAttestation:
        raise RuntimeError("verifier unavailable")


def _bindings(
    *,
    workers: int = 2,
    maximum_usage: ResourceUsage | None = None,
    bootstrap_limit: int = 4,
    curator_limit: int = 4,
) -> ScientificLedgerBindings:
    return ScientificLedgerBindings(
        protocol_sha256=_digest("protocol"),
        frame_manifest_sha256=_digest("frame"),
        resource_ceiling_sha256=_digest("resource-ceiling"),
        task_candidates=(
            (TASK_A, (CANDIDATE_A, CANDIDATE_B)),
            (TASK_B, (CANDIDATE_C, CANDIDATE_D)),
        ),
        resource_limits=ResourceLimits(
            maximum_concurrent_workers=workers,
            maximum_usage=maximum_usage
            or ResourceUsage(
                acquisition_events=20,
                process_launches=20,
                cpu_micros=20_000_000,
                worker_wall_micros=20_000_000,
                peak_rss_bytes=1_000_000,
                storage_bytes=20_000_000,
                semantic_calls=20,
                input_tokens=20_000,
                output_tokens=20_000,
                usd_micros=20_000,
                human_minutes=200,
            ),
            maximum_deterministic_static_acquisitions=bootstrap_limit,
            maximum_curator_hardening_attempts=curator_limit,
        ),
        bootstrap_signer_ids=("fixture-static-producer",),
        curator_signer_ids=("fixture-curator",),
        reservation_signer_ids=("provisioner",),
        meter_signer_ids=("resource-meter",),
    )


def _ledger(
    tmp_path: pathlib.Path,
    *,
    bindings: ScientificLedgerBindings | None = None,
) -> ScientificLedger:
    return ScientificLedger(
        tmp_path / "scientific.sqlite3",
        bindings=bindings or _bindings(),
    )


def _bootstrap(
    *,
    task_id: str = TASK_A,
    candidate_id: str = CANDIDATE_A,
    acquisition_id: str = "bootstrap-a",
    produced_at: str = T0,
    status: EvidenceStatus = EvidenceStatus.INCONCLUSIVE,
) -> BootstrapReceipt:
    return BootstrapReceipt(
        task_id=task_id,
        candidate_id=candidate_id,
        acquisition_id=acquisition_id,
        route=RouterRouteStep(
            action=RouteAction.RUN_STATIC,
            policy_version="static-bootstrap-v1",
            candidate_risk=0.5,
            verifier_risk=0.5,
            expected_information_gain=0.1,
            estimated_relative_cost=0.01,
            scores_calibrated=False,
            calibration_id="",
        ),
        observation=EvidenceObservation(
            kind=EvidenceKind.STATIC,
            status=status,
            source="fixture-static",
            source_version="v1",
            acquisition_id=acquisition_id,
        ),
        producer_id="fixture-static-producer",
        producer_version="v1",
        artifact_sha256=_digest(f"artifact:{acquisition_id}:{status.value}"),
        produced_at=produced_at,
    )


def _curator(
    *,
    acquisition_id: str = "curator-a",
    candidate_id: str = CANDIDATE_A,
    produced_at: str = T1,
) -> CuratorReceipt:
    return CuratorReceipt(
        task_id=TASK_A,
        candidate_id=candidate_id,
        acquisition_id=acquisition_id,
        task_selection_sha256=_digest("task-selection"),
        action_spec_sha256=_digest(f"action-spec:{acquisition_id}"),
        observation=EvidenceObservation(
            kind=EvidenceKind.ORACLE_HARDENING,
            status=EvidenceStatus.SUPPORTS_CORRECT,
            source="fixture-curator",
            source_version="v1",
            acquisition_id=acquisition_id,
            authoritative=True,
            privileged_inputs=("gold_patch", "hidden_tests"),
        ),
        artifact_sha256=_digest(f"curator-artifact:{acquisition_id}"),
        curator_protocol_sha256=_digest("curator-protocol"),
        producer_id="fixture-curator",
        producer_version="v1",
        produced_at=produced_at,
    )


def _reservation(
    reservation_id: str = "reservation-a",
    *,
    resource_key: str | None = None,
    candidate_id: str | None = CANDIDATE_A,
    reserved: ResourceUsage | None = None,
    reserved_at: str = T0,
    worker_ids: tuple[str, ...] = ("worker-a",),
) -> ResourceReservation:
    return ResourceReservation(
        reservation_id=reservation_id,
        resource_key=resource_key or f"workspace:{reservation_id}",
        reservation_authority_id="provisioner",
        worker_count=len(worker_ids),
        worker_ids=worker_ids,
        task_id=TASK_A if candidate_id is not None else None,
        candidate_id=candidate_id,
        acquisition_id=f"acquisition:{reservation_id}",
        reserved=reserved
        or ResourceUsage(
            acquisition_events=1,
            process_launches=1,
            cpu_micros=2_000_000,
            worker_wall_micros=3_000_000,
            peak_rss_bytes=500_000,
            storage_bytes=1_000,
        ),
        reserved_at=reserved_at,
    )


def _settlement(
    reservation: ResourceReservation,
    reservation_receipt: AppendReceipt,
    *,
    actual: ResourceUsage | None = None,
    settled_at: str = T2,
) -> ResourceSettlement:
    return ResourceSettlement(
        reservation_id=reservation.reservation_id,
        reservation_record_sha256=reservation_receipt.record_sha256,
        meter_authority_id="resource-meter",
        actual=actual
        or ResourceUsage(
            acquisition_events=1,
            process_launches=1,
            cpu_micros=1_000_000,
            worker_wall_micros=2_000_000,
            peak_rss_bytes=400_000,
            storage_bytes=800,
        ),
        outcome=ResourceOutcome.COMPLETED,
        usage_artifact_sha256=_digest(f"usage:{reservation.reservation_id}"),
        settled_at=settled_at,
        task_id=reservation.task_id,
        candidate_id=reservation.candidate_id,
    )


def _append(
    ledger: ScientificLedger,
    subject: BootstrapReceipt | CuratorReceipt | ResourceReservation | ResourceSettlement,
    *,
    verifier: SignatureVerifier | None = None,
    signer_id: str | None = None,
) -> AppendReceipt:
    if signer_id is None:
        if isinstance(subject, (BootstrapReceipt, CuratorReceipt)):
            signer_id = subject.producer_id
        elif isinstance(subject, ResourceReservation):
            signer_id = subject.reservation_authority_id
        else:
            signer_id = subject.meter_authority_id
    signature = hmac.digest(
        _SECRET,
        signed_envelope_bytes(ledger.bindings, subject),
        "sha256",
    )
    return ledger.append_signed(
        subject,
        signature=signature,
        signature_scheme="hmac-sha256-test",
        signer_id=signer_id,
        key_id="fixture-key-v1",
        verifier=verifier or _HmacVerifier(),
    )


def test_repository_bindings_load_exact_frozen_frame_and_integer_ceiling() -> None:
    bindings = load_scientific_ledger_bindings(ROOT)

    assert bindings.task_count == 22
    assert bindings.candidate_count == 66
    assert bindings.resource_limits.maximum_concurrent_workers == 4
    assert bindings.resource_limits.maximum_usage.cpu_micros == 4_838_400_000_000
    assert bindings.resource_limits.maximum_usage.worker_wall_micros == 1_209_600_000_000
    assert bindings.resource_limits.maximum_usage.usd_micros == 500_000_000
    assert bindings.resource_limits.maximum_deterministic_static_acquisitions == 66
    assert bindings.resource_limits.maximum_curator_hardening_attempts == 132
    assert bindings.bootstrap_signer_ids == ()
    assert bindings.curator_signer_ids == ()
    assert bindings.reservation_signer_ids == ()
    assert bindings.meter_signer_ids == ()


def test_repository_bindings_cannot_accept_records_before_external_roles_exist(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path, bindings=load_scientific_ledger_bindings(ROOT))
    task_id, candidates = ledger.bindings.task_candidates[0]
    bootstrap = _bootstrap(
        task_id=task_id,
        candidate_id=candidates[0],
        acquisition_id="bootstrap-real-frame",
    )

    with pytest.raises(ScientificLedgerError, match="no frozen external authority"):
        _append(ledger, bootstrap)

    assert ledger.audit().record_count == 0


def test_signed_bootstrap_round_trips_and_exports_without_policy_join(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    bootstrap = _bootstrap()

    first = _append(ledger, bootstrap)
    repeated = _append(ledger, bootstrap, verifier=_UnavailableVerifier())
    audit = ledger.audit()
    export = ledger.export_bytes()

    assert first.inserted is True
    assert repeated == replace(first, inserted=False)
    assert audit.record_count == 1
    assert audit.bootstrap_receipt_count == 1
    assert audit.complete_bootstrap_candidate_coverage is False
    assert audit.observed_candidate_count == 1
    assert (
        audit.to_dict()["partial_frame"]["bootstrap_precedes_behavior_round_zero_proven"] is False
    )
    assert audit.to_dict()["external_checkpoint_present"] is False
    assert audit.to_dict()["signer_key_scheme_verifier_profiles_frozen"] is False
    assert audit.to_dict()["resource_reservations_joined_to_acquisitions"] is False
    assert audit.to_dict()["resource_overrun_or_deviation_records_supported"] is True
    assert audit.resource_deviation_count == 0
    assert audit.resource_deviation_dimension_count == 0
    assert audit.reservation_overrun_dimensions == ()
    assert audit.aggregate_ceiling_exceeded_dimensions == ()
    assert audit.ceiling_exceeded is False
    assert audit.halt_required is False
    assert audit.to_dict()["bootstrap_manifest_frozen_and_recomputed"] is False
    assert audit.to_dict()["externally_immutable_storage_bound"] is False
    assert audit.to_dict()["writer_reordering_detected_by_external_anchor"] is False
    assert audit.to_dict()["prefix_truncation_detected_by_external_anchor"] is False
    assert audit.to_dict()["activation_calendar_bound_and_checked"] is False
    assert b'"detached_signatures_cryptographically_reverified_during_audit":false' in export
    assert bootstrap.record_id.encode() in export
    assert os.stat(ledger.path).st_mode & 0o777 == 0o600


def test_invalid_or_postdated_signature_fails_without_mutating_ledger(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    bootstrap = _bootstrap()

    with pytest.raises(ScientificLedgerError, match="external signature verification failed"):
        ledger.append_signed(
            bootstrap,
            signature=b"not-a-valid-signature",
            signature_scheme="hmac-sha256-test",
            signer_id=bootstrap.producer_id,
            key_id="fixture-key-v1",
            verifier=_HmacVerifier(),
        )
    with pytest.raises(ScientificLedgerError, match="verification predates"):
        _append(
            ledger,
            bootstrap,
            verifier=_HmacVerifier(verified_at="2026-07-13T23:59:59.000000Z"),
        )

    assert ledger.audit().record_count == 0


def test_bootstrap_is_candidate_unique_frame_bound_and_ceiling_limited(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path, bindings=_bindings(bootstrap_limit=1))
    _append(ledger, _bootstrap())

    with pytest.raises(ScientificLedgerConflict, match="already has"):
        _append(
            ledger,
            _bootstrap(
                acquisition_id="bootstrap-a-second",
                status=EvidenceStatus.SUPPORTS_CORRECT,
            ),
        )
    with pytest.raises(ResourceCeilingExceeded, match="static acquisition"):
        _append(
            ledger,
            _bootstrap(
                candidate_id=CANDIDATE_B,
                acquisition_id="bootstrap-b",
            ),
        )
    with pytest.raises(ScientificLedgerError, match="outside the frozen frame"):
        _append(
            ledger,
            _bootstrap(
                candidate_id=f"sha256:{'e' * 64}",
                acquisition_id="bootstrap-outside",
            ),
        )

    assert ledger.audit().record_count == 1


def test_curator_stream_is_separate_typed_and_attempt_limited(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path, bindings=_bindings(curator_limit=1))
    curator = _curator()
    _append(ledger, curator)

    with pytest.raises(ScientificLedgerConflict, match="acquisition identity"):
        _append(ledger, replace(curator, artifact_sha256=_digest("changed")))
    with pytest.raises(ResourceCeilingExceeded, match="curator hardening"):
        _append(
            ledger,
            _curator(acquisition_id="curator-b", candidate_id=CANDIDATE_B),
        )

    audit = ledger.audit()
    assert audit.curator_receipt_count == 1
    assert audit.bootstrap_receipt_count == 0


def test_nonpolicy_acquisition_ids_are_global_across_record_kinds(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, _bootstrap(acquisition_id="shared-acquisition"))

    with pytest.raises(ScientificLedgerConflict, match="acquisition identity"):
        _append(ledger, _curator(acquisition_id="shared-acquisition"))

    assert ledger.audit().record_count == 1


def test_signed_envelope_prevents_cross_binding_replay(
    tmp_path: pathlib.Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = _ledger(first_root)
    second = _ledger(
        second_root,
        bindings=replace(
            first.bindings,
            protocol_sha256=_digest("different-protocol"),
        ),
    )
    bootstrap = _bootstrap()
    _append(first, bootstrap)
    first_signature = hmac.digest(
        _SECRET,
        signed_envelope_bytes(first.bindings, bootstrap),
        "sha256",
    )

    with pytest.raises(ScientificLedgerError, match="external signature verification failed"):
        second.append_signed(
            bootstrap,
            signature=first_signature,
            signature_scheme="hmac-sha256-test",
            signer_id=bootstrap.producer_id,
            key_id="fixture-key-v1",
            verifier=_HmacVerifier(),
        )

    assert second.audit().record_count == 0


def test_role_signers_must_match_subject_identity_and_frozen_role(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(ScientificLedgerError, match="bootstrap signer differs"):
        _append(ledger, _bootstrap(), signer_id="reviewer-1")
    with pytest.raises(ScientificLedgerError, match="curator signer differs"):
        _append(ledger, _curator(), signer_id="fixture-static-producer")
    reservation = _reservation()
    with pytest.raises(ScientificLedgerError, match="reservation signer differs"):
        _append(ledger, reservation, signer_id="resource-meter")
    reservation_receipt = _append(ledger, reservation)
    with pytest.raises(ScientificLedgerError, match="meter signer differs"):
        _append(
            ledger,
            _settlement(reservation, reservation_receipt),
            signer_id="provisioner",
        )
    with pytest.raises(ScientificLedgerError, match="cannot serve both"):
        replace(
            ledger.bindings,
            meter_signer_ids=("provisioner",),
        )

    assert ledger.audit().record_count == 1


def test_impossible_calendar_timestamp_is_rejected() -> None:
    with pytest.raises(ScientificLedgerError, match="not a real UTC timestamp"):
        _bootstrap(produced_at="2026-02-31T00:00:00.000000Z")


def test_resource_reservation_settlement_releases_unused_commitment(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    reservation = _reservation()
    reservation_receipt = _append(ledger, reservation, signer_id="provisioner")
    before = ledger.audit()
    settlement = _settlement(reservation, reservation_receipt)
    _append(ledger, settlement, signer_id="resource-meter")
    after = ledger.audit()

    assert before.active_reservation_count == 1
    assert before.committed_resource_usage == reservation.reserved
    assert after.active_reservation_count == 0
    assert after.resource_settlement_count == 1
    assert after.committed_resource_usage == settlement.actual


def test_resource_concurrency_and_aggregate_ceiling_fail_transactionally(
    tmp_path: pathlib.Path,
) -> None:
    maximum = ResourceUsage(
        acquisition_events=2,
        process_launches=2,
        cpu_micros=3_000_000,
        worker_wall_micros=4_000_000,
        peak_rss_bytes=600_000,
        storage_bytes=2_000,
        semantic_calls=1,
        input_tokens=100,
        output_tokens=100,
        usd_micros=100,
        human_minutes=10,
    )
    ledger = _ledger(tmp_path, bindings=_bindings(workers=1, maximum_usage=maximum))
    first = _reservation(
        reserved=ResourceUsage(
            acquisition_events=1,
            process_launches=1,
            cpu_micros=2_000_000,
            worker_wall_micros=3_000_000,
            peak_rss_bytes=500_000,
            storage_bytes=1_000,
        )
    )
    receipt = _append(ledger, first)

    with pytest.raises(ResourceCeilingExceeded, match="concurrent-worker"):
        _append(
            ledger,
            _reservation(
                "reservation-b",
                candidate_id=CANDIDATE_B,
                worker_ids=("worker-b",),
            ),
        )
    _append(ledger, _settlement(first, receipt, actual=ResourceUsage()))
    with pytest.raises(ResourceCeilingExceeded, match="aggregate resource ceiling"):
        _append(
            ledger,
            _reservation(
                "reservation-c",
                candidate_id=CANDIDATE_B,
                reserved=ResourceUsage(cpu_micros=3_000_001),
            ),
        )

    audit = ledger.audit()
    assert audit.record_count == 2
    assert audit.resource_reservation_count == 1
    assert audit.resource_settlement_count == 1


def test_worker_identity_and_count_are_enforced(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(ScientificLedgerError, match="worker_count differs"):
        replace(_reservation(), worker_count=2)
    with pytest.raises(ScientificLedgerError, match="requires at least one worker"):
        replace(_reservation(), worker_count=0, worker_ids=())

    ledger = _ledger(tmp_path, bindings=_bindings(workers=2))
    _append(ledger, _reservation(worker_ids=("worker-a",)))
    with pytest.raises(ScientificLedgerConflict, match="already active"):
        _append(
            ledger,
            _reservation(
                "reservation-b",
                candidate_id=CANDIDATE_B,
                worker_ids=("worker-a",),
            ),
        )

    assert ledger.audit().active_worker_count == 1


def test_settlement_must_match_reservation_scope_and_digest(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    reservation = _reservation()

    with pytest.raises(ScientificLedgerError, match="has no reservation"):
        _append(
            ledger,
            ResourceSettlement(
                reservation_id=reservation.reservation_id,
                reservation_record_sha256=_digest("absent"),
                meter_authority_id="resource-meter",
                actual=ResourceUsage(),
                outcome=ResourceOutcome.ABANDONED,
                usage_artifact_sha256=_digest("usage"),
                settled_at=T1,
                task_id=reservation.task_id,
                candidate_id=reservation.candidate_id,
            ),
        )
    receipt = _append(ledger, reservation)
    with pytest.raises(ScientificLedgerError, match="wrong reservation record"):
        _append(
            ledger,
            replace(
                _settlement(reservation, receipt),
                reservation_record_sha256=_digest("wrong-record"),
            ),
        )
    assert ledger.audit().active_reservation_count == 1


def test_overrun_settlement_is_inserted_retries_and_reaudits_exactly(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    reservation = _reservation()
    reservation_receipt = _append(ledger, reservation)
    settlement = _settlement(
        reservation,
        reservation_receipt,
        actual=replace(reservation.reserved, cpu_micros=3_000_000),
    )

    inserted = _append(ledger, settlement)
    retried = _append(ledger, settlement, verifier=_UnavailableVerifier())
    audit = ledger.audit()
    reopened = ScientificLedger(ledger.path, bindings=ledger.bindings)

    assert inserted.inserted is True
    assert retried == replace(inserted, inserted=False)
    assert audit == reopened.audit()
    assert audit.record_count == 2
    assert audit.resource_settlement_count == 1
    assert audit.active_reservation_count == 0
    assert audit.committed_resource_usage == settlement.actual
    assert audit.resource_deviation_count == 1
    assert audit.resource_deviation_dimension_count == 1
    assert audit.reservation_overrun_dimensions == ("cpu_micros",)
    assert audit.aggregate_ceiling_exceeded_dimensions == ()
    assert audit.ceiling_exceeded is False
    assert audit.halt_required is True
    assert audit.to_dict()["resource_deviations"] == {
        "settlement_count": 1,
        "dimension_count": 1,
        "reservation_overrun_dimensions": ["cpu_micros"],
        "aggregate_ceiling_exceeded_dimensions": [],
        "ceiling_exceeded": False,
        "halt_required": True,
    }


def test_aggregate_overrun_halts_new_work_but_outstanding_settlements_close(
    tmp_path: pathlib.Path,
) -> None:
    maximum = ResourceUsage(
        acquisition_events=10,
        process_launches=10,
        cpu_micros=3_000_000,
        worker_wall_micros=10_000_000,
        peak_rss_bytes=1_000_000,
        storage_bytes=10_000,
        semantic_calls=10,
        input_tokens=10_000,
        output_tokens=10_000,
        usd_micros=10_000,
        human_minutes=100,
    )
    ledger = _ledger(tmp_path, bindings=_bindings(workers=2, maximum_usage=maximum))
    first = _reservation(
        reserved=ResourceUsage(cpu_micros=1_500_000),
        worker_ids=("worker-a",),
    )
    second = _reservation(
        "reservation-b",
        candidate_id=CANDIDATE_B,
        reserved=ResourceUsage(cpu_micros=1_500_000),
        worker_ids=("worker-b",),
    )
    first_receipt = _append(ledger, first)
    second_receipt = _append(ledger, second)
    overrun = _settlement(
        first,
        first_receipt,
        actual=ResourceUsage(cpu_micros=2_500_000),
    )
    _append(ledger, overrun)

    halted = ledger.audit()
    assert halted.committed_resource_usage.cpu_micros == 4_000_000
    assert halted.aggregate_ceiling_exceeded_dimensions == ("cpu_micros",)
    assert halted.ceiling_exceeded is True
    assert halted.halt_required is True
    assert halted.active_reservation_count == 1
    assert _append(ledger, second, verifier=_UnavailableVerifier()) == replace(
        second_receipt,
        inserted=False,
    )

    for new_work in (
        _bootstrap(candidate_id=CANDIDATE_B, acquisition_id="bootstrap-after-overrun"),
        _curator(acquisition_id="curator-after-overrun", candidate_id=CANDIDATE_B),
        _reservation(
            "reservation-after-overrun",
            candidate_id=CANDIDATE_B,
            worker_ids=("worker-c",),
        ),
    ):
        with pytest.raises(ResourceCeilingExceeded, match="halted after a measured"):
            _append(ledger, new_work)

    abandoned = replace(
        _settlement(second, second_receipt, actual=ResourceUsage(), settled_at=T3),
        outcome=ResourceOutcome.ABANDONED,
    )
    _append(ledger, abandoned)
    closed = ledger.audit()

    assert closed.record_count == 4
    assert closed.resource_settlement_count == 2
    assert closed.active_reservation_count == 0
    assert closed.active_worker_count == 0
    assert closed.committed_resource_usage.cpu_micros == 2_500_000
    assert closed.resource_deviation_count == 1
    assert closed.resource_deviation_dimension_count == 1
    assert closed.reservation_overrun_dimensions == ("cpu_micros",)
    assert closed.aggregate_ceiling_exceeded_dimensions == ("cpu_micros",)
    assert closed.ceiling_exceeded is True
    assert closed.halt_required is True


def test_exclusive_resource_key_cannot_be_reused_after_settlement(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    reservation = _reservation()
    receipt = _append(ledger, reservation)
    _append(ledger, _settlement(reservation, receipt))

    with pytest.raises(ScientificLedgerConflict, match="resource_key"):
        _append(
            ledger,
            _reservation(
                "reservation-new",
                resource_key=reservation.resource_key,
                candidate_id=CANDIDATE_B,
            ),
        )


def test_hash_chain_and_canonical_subject_detect_direct_database_tampering(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, _bootstrap())

    connection = sqlite3.connect(ledger.path)
    try:
        connection.execute("DROP TRIGGER scientific_records_no_update")
        connection.execute(
            "UPDATE scientific_records SET payload_json = ? WHERE sequence = 1",
            ('{"tampered":true}',),
        )
        connection.execute(_SCIENTIFIC_RECORDS_NO_UPDATE_TRIGGER_SQL)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ScientificLedgerError, match="fields differ|record"):
        ledger.audit()


def test_audit_reapplies_frozen_signer_authorization(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, _bootstrap())

    connection = sqlite3.connect(ledger.path)
    try:
        connection.execute("DROP TRIGGER scientific_records_no_update")
        row = connection.execute(
            "SELECT verification_json FROM scientific_records WHERE sequence = 1"
        ).fetchone()
        assert row is not None
        forged = str(row[0]).replace(
            '"signer_id":"fixture-static-producer"',
            '"signer_id":"fixture-curator"',
        )
        connection.execute(
            "UPDATE scientific_records SET verification_json = ? WHERE sequence = 1",
            (forged,),
        )
        connection.execute(_SCIENTIFIC_RECORDS_NO_UPDATE_TRIGGER_SQL)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ScientificLedgerError, match="bootstrap signer differs"):
        ledger.audit()


def test_sqlite_append_only_triggers_reject_update_and_delete(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, _bootstrap())

    connection = sqlite3.connect(ledger.path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE scientific_records SET occurred_at = ? WHERE sequence = 1",
                (T1,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM scientific_records WHERE sequence = 1")
    finally:
        connection.close()


def test_export_is_exclusive_and_reopen_preserves_exact_audit(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, _bootstrap())
    expected = ledger.audit()
    output = tmp_path / "scientific-export.jsonl"

    size, digest = ledger.write_export(output)
    reopened = ScientificLedger(ledger.path, bindings=ledger.bindings)

    assert size == len(output.read_bytes())
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    assert reopened.audit() == expected
    with pytest.raises(ScientificLedgerConflict, match="will not be overwritten"):
        ledger.write_export(output)


def test_export_uses_one_read_snapshot_during_concurrent_append(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _ledger(tmp_path)
    writer = ScientificLedger(reader.path, bindings=reader.bindings)
    _append(reader, _bootstrap())
    original_audit = reader._audit_connection
    appended = False

    def audit_then_append(connection: sqlite3.Connection):  # type: ignore[no-untyped-def]
        nonlocal appended
        result = original_audit(connection)
        if not appended:
            appended = True
            _append(writer, _curator())
        return result

    monkeypatch.setattr(reader, "_audit_connection", audit_then_append)
    lines = reader.export_bytes().splitlines()
    header = strict_json_loads(lines[0].decode("utf-8"))

    assert isinstance(header, dict)
    assert header["record_count"] == 1
    assert len(lines) == 2
    assert writer.audit().record_count == 2


def test_ledger_rejects_symlink_path_and_binding_reuse(
    tmp_path: pathlib.Path,
) -> None:
    real = tmp_path / "real.sqlite3"
    ledger = ScientificLedger(real, bindings=_bindings())
    link = tmp_path / "linked.sqlite3"
    link.symlink_to(real)

    with pytest.raises(ScientificLedgerError, match="symlink"):
        ScientificLedger(link, bindings=_bindings())
    with pytest.raises(ScientificLedgerConflict, match="different protocol"):
        ScientificLedger(
            ledger.path,
            bindings=replace(
                ledger.bindings,
                protocol_sha256=_digest("different-protocol"),
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("maximum_concurrent_workers", True),
        ("maximum_concurrent_workers", 1.5),
        ("maximum_deterministic_static_acquisitions", False),
        ("maximum_deterministic_static_acquisitions", 2.0),
        ("maximum_curator_hardening_attempts", True),
        ("maximum_curator_hardening_attempts", 2.0),
    ),
)
def test_resource_limits_reject_boolean_and_float_counts(
    field_name: str,
    invalid_value: object,
) -> None:
    limits = _bindings().resource_limits

    with pytest.raises(ScientificLedgerError, match="must be a non-negative integer"):
        replace(limits, **{field_name: cast(Any, invalid_value)})


def test_ledger_rejects_permissive_existing_database_mode(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    os.chmod(ledger.path, 0o644)
    try:
        with pytest.raises(ScientificLedgerError, match="exactly 0600"):
            ScientificLedger(ledger.path, bindings=ledger.bindings)
        with pytest.raises(ScientificLedgerError, match="exactly 0600"):
            ledger.audit()
    finally:
        os.chmod(ledger.path, 0o600)


def test_trusted_trigger_name_cannot_hide_a_noop_contract(
    tmp_path: pathlib.Path,
) -> None:
    ledger = _ledger(tmp_path)
    connection = sqlite3.connect(ledger.path)
    try:
        connection.execute("DROP TRIGGER scientific_records_no_update")
        connection.execute(
            "CREATE TRIGGER scientific_records_no_update "
            "BEFORE UPDATE ON scientific_records BEGIN SELECT 1; END"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ScientificLedgerError, match="schema contract differs.*changed"):
        ScientificLedger(ledger.path, bindings=ledger.bindings)
    with pytest.raises(ScientificLedgerError, match="schema contract differs.*changed"):
        ledger.audit()
