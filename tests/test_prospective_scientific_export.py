"""Adversarial tests for externally pinned scientific-ledger exports."""

from __future__ import annotations

import hashlib
import hmac
import pathlib
from typing import Any, cast

import pytest

import experiments.prospective_pilot.scientific_ledger as scientific_ledger_module
from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    RouteAction,
)
from bench_cleanser.verification.policy_log import RouterRouteStep
from experiments.prospective_pilot.scientific_ledger import (
    BootstrapReceipt,
    CuratorReceipt,
    ResourceLimits,
    ResourceOutcome,
    ResourceReservation,
    ResourceSettlement,
    ResourceUsage,
    ScientificLedger,
    ScientificLedgerBindings,
    ScientificLedgerError,
    ScientificLedgerExportSnapshot,
    SignatureVerifier,
    VerifierAttestation,
    audit_scientific_ledger_export,
    signed_envelope_bytes,
)

TASK_ID = "project__project-100"
CANDIDATE_A = f"sha256:{'a' * 64}"
CANDIDATE_B = f"sha256:{'b' * 64}"
T0 = "2026-07-14T00:00:00.000000Z"
T1 = "2026-07-14T00:01:00.000000Z"
T2 = "2026-07-14T00:02:00.000000Z"
T3 = "2026-07-14T00:03:00.000000Z"
T4 = "2026-07-14T00:04:00.000000Z"
_SECRET = b"scientific-export-test-secret"


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class _Verifier(SignatureVerifier):
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
            raise ValueError("wrong signature scheme")
        if not hmac.compare_digest(signature, hmac.digest(_SECRET, subject, "sha256")):
            raise ValueError("wrong signature")
        return VerifierAttestation(
            verifier_id="fixture-verifier",
            verifier_version="v1",
            verification_artifact_sha256=_digest_bytes(b"verified\0" + subject + b"\0" + signature),
            verified_at=T4,
        )


def _bindings() -> ScientificLedgerBindings:
    return ScientificLedgerBindings(
        protocol_sha256=_digest_text("protocol"),
        frame_manifest_sha256=_digest_text("frame"),
        resource_ceiling_sha256=_digest_text("resource-ceiling"),
        task_candidates=((TASK_ID, (CANDIDATE_A, CANDIDATE_B)),),
        resource_limits=ResourceLimits(
            maximum_concurrent_workers=2,
            maximum_usage=ResourceUsage(
                acquisition_events=10,
                process_launches=10,
                cpu_micros=10_000,
                worker_wall_micros=10_000,
                peak_rss_bytes=10_000,
                storage_bytes=10_000,
                semantic_calls=10,
                input_tokens=10_000,
                output_tokens=10_000,
                usd_micros=10_000,
                human_minutes=10,
            ),
            maximum_deterministic_static_acquisitions=2,
            maximum_curator_hardening_attempts=2,
        ),
        bootstrap_signer_ids=("static-producer",),
        curator_signer_ids=("curator",),
        reservation_signer_ids=("provisioner",),
        meter_signer_ids=("resource-meter",),
    )


def _bootstrap() -> BootstrapReceipt:
    return BootstrapReceipt(
        task_id=TASK_ID,
        candidate_id=CANDIDATE_A,
        acquisition_id="bootstrap-a",
        route=RouterRouteStep(
            action=RouteAction.RUN_STATIC,
            policy_version="static-v1",
            candidate_risk=0.5,
            verifier_risk=0.5,
            expected_information_gain=0.2,
            estimated_relative_cost=0.01,
            scores_calibrated=False,
            calibration_id="",
        ),
        observation=EvidenceObservation(
            kind=EvidenceKind.STATIC,
            status=EvidenceStatus.INCONCLUSIVE,
            source="fixture-static",
            source_version="v1",
            acquisition_id="bootstrap-a",
        ),
        producer_id="static-producer",
        producer_version="v1",
        artifact_sha256=_digest_text("bootstrap-artifact"),
        produced_at=T0,
    )


def _curator() -> CuratorReceipt:
    return CuratorReceipt(
        task_id=TASK_ID,
        candidate_id=CANDIDATE_B,
        acquisition_id="curator-b",
        task_selection_sha256=_digest_text("selection"),
        action_spec_sha256=_digest_text("action-spec"),
        observation=EvidenceObservation(
            kind=EvidenceKind.ORACLE_HARDENING,
            status=EvidenceStatus.SUPPORTS_CORRECT,
            source="fixture-curator",
            source_version="v1",
            acquisition_id="curator-b",
            authoritative=True,
            privileged_inputs=("gold_patch",),
        ),
        artifact_sha256=_digest_text("curator-artifact"),
        curator_protocol_sha256=_digest_text("curator-protocol"),
        producer_id="curator",
        producer_version="v1",
        produced_at=T1,
    )


def _reservation() -> ResourceReservation:
    return ResourceReservation(
        reservation_id="reservation-a",
        resource_key="workspace:reservation-a",
        reservation_authority_id="provisioner",
        worker_count=1,
        worker_ids=("worker-a",),
        task_id=TASK_ID,
        candidate_id=CANDIDATE_A,
        acquisition_id="execution-a",
        reserved=ResourceUsage(
            acquisition_events=1,
            process_launches=1,
            cpu_micros=1_000,
            worker_wall_micros=2_000,
            peak_rss_bytes=3_000,
            storage_bytes=4_000,
        ),
        reserved_at=T2,
    )


def _append(ledger: ScientificLedger, subject: Any, *, signer_id: str) -> Any:
    envelope = signed_envelope_bytes(ledger.bindings, subject)
    return ledger.append_signed(
        subject,
        signature=hmac.digest(_SECRET, envelope, "sha256"),
        signature_scheme="hmac-sha256-test",
        signer_id=signer_id,
        key_id=f"{signer_id}-key",
        verifier=_Verifier(),
    )


@pytest.fixture
def valid_export(tmp_path: pathlib.Path) -> bytes:
    ledger = ScientificLedger(tmp_path / "scientific.sqlite3", bindings=_bindings())
    _append(ledger, _bootstrap(), signer_id="static-producer")
    _append(ledger, _curator(), signer_id="curator")
    reservation = _reservation()
    reservation_receipt = _append(ledger, reservation, signer_id="provisioner")
    settlement = ResourceSettlement(
        reservation_id=reservation.reservation_id,
        reservation_record_sha256=reservation_receipt.record_sha256,
        meter_authority_id="resource-meter",
        actual=ResourceUsage(
            acquisition_events=1,
            process_launches=1,
            cpu_micros=800,
            worker_wall_micros=1_500,
            peak_rss_bytes=2_500,
            storage_bytes=3_500,
        ),
        outcome=ResourceOutcome.COMPLETED,
        usage_artifact_sha256=_digest_text("usage-artifact"),
        settled_at=T3,
        task_id=TASK_ID,
        candidate_id=CANDIDATE_A,
    )
    _append(ledger, settlement, signer_id="resource-meter")
    return ledger.export_bytes()


@pytest.fixture
def overrun_export(tmp_path: pathlib.Path) -> bytes:
    ledger = ScientificLedger(tmp_path / "overrun.sqlite3", bindings=_bindings())
    reservation = _reservation()
    reservation_receipt = _append(ledger, reservation, signer_id="provisioner")
    settlement = ResourceSettlement(
        reservation_id=reservation.reservation_id,
        reservation_record_sha256=reservation_receipt.record_sha256,
        meter_authority_id="resource-meter",
        actual=ResourceUsage(cpu_micros=20_000),
        outcome=ResourceOutcome.COMPLETED,
        usage_artifact_sha256=_digest_text("overrun-usage-artifact"),
        settled_at=T3,
        task_id=TASK_ID,
        candidate_id=CANDIDATE_A,
    )
    _append(ledger, settlement, signer_id="resource-meter")
    return ledger.export_bytes()


def _audit(value: bytes) -> ScientificLedgerExportSnapshot:
    return audit_scientific_ledger_export(
        value,
        expected_export_sha256=_digest_bytes(value),
    )


def _rewrite_line(value: bytes, index: int, mutation: str) -> bytes:
    lines = value.decode("utf-8").splitlines()
    decoded = strict_json_loads(lines[index])
    assert isinstance(decoded, dict)
    line = cast(dict[str, Any], decoded)
    if mutation == "signature_subject":
        verification = cast(dict[str, Any], line["signature_verification"])
        verification["subject_sha256"] = "f" * 64
    elif mutation == "unauthorized_signer":
        verification = cast(dict[str, Any], line["signature_verification"])
        verification["signer_id"] = "intruder"
    elif mutation == "header_count":
        line["record_count"] = cast(int, line["record_count"]) + 1
    elif mutation == "header_head":
        line["record_head_sha256"] = "0" * 64
    elif mutation == "audit_count":
        audit = cast(dict[str, Any], line["audit"])
        counts = cast(dict[str, Any], audit["counts"])
        counts["bootstrap_receipts"] = cast(int, counts["bootstrap_receipts"]) + 1
    elif mutation == "audit_crypto_claim":
        audit = cast(dict[str, Any], line["audit"])
        audit["detached_signatures_cryptographically_reverified_during_audit"] = True
    elif mutation == "audit_deviation_count":
        audit = cast(dict[str, Any], line["audit"])
        deviations = cast(dict[str, Any], audit["resource_deviations"])
        deviations["settlement_count"] = cast(int, deviations["settlement_count"]) + 1
    elif mutation == "audit_deviation_dimensions":
        audit = cast(dict[str, Any], line["audit"])
        deviations = cast(dict[str, Any], audit["resource_deviations"])
        deviations["reservation_overrun_dimensions"] = ["storage_bytes"]
    elif mutation == "audit_halt":
        audit = cast(dict[str, Any], line["audit"])
        deviations = cast(dict[str, Any], audit["resource_deviations"])
        deviations["halt_required"] = False
    elif mutation == "audit_deviation_capability":
        audit = cast(dict[str, Any], line["audit"])
        audit["resource_overrun_or_deviation_records_supported"] = False
    else:  # pragma: no cover - fixture programming error.
        raise AssertionError(f"unknown mutation {mutation}")
    lines[index] = strict_json_dumps(line)
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_pinned_export_reconstructs_all_typed_records(valid_export: bytes) -> None:
    snapshot = _audit(valid_export)

    assert snapshot.export_sha256 == _digest_bytes(valid_export)
    assert snapshot.bindings == _bindings()
    assert snapshot.audit.record_count == 4
    assert snapshot.audit.resource_settlement_count == 1
    assert snapshot.detached_signatures_cryptographically_reverified_during_audit is False
    assert tuple(entry.sequence for entry in snapshot.records) == (1, 2, 3, 4)
    assert tuple(type(entry.subject) for entry in snapshot.records) == (
        BootstrapReceipt,
        CuratorReceipt,
        ResourceReservation,
        ResourceSettlement,
    )
    assert snapshot.audit.record_head_sha256 == snapshot.records[-1].record_sha256
    frozen_field = "export_sha256"
    with pytest.raises(AttributeError):
        setattr(snapshot, frozen_field, "0" * 64)


def test_export_replays_signed_overrun_and_fail_closed_halt(overrun_export: bytes) -> None:
    snapshot = _audit(overrun_export)

    assert snapshot.audit.record_count == 2
    assert snapshot.audit.resource_settlement_count == 1
    assert snapshot.audit.committed_resource_usage.cpu_micros == 20_000
    assert snapshot.audit.resource_deviation_count == 1
    assert snapshot.audit.resource_deviation_dimension_count == 1
    assert snapshot.audit.reservation_overrun_dimensions == ("cpu_micros",)
    assert snapshot.audit.aggregate_ceiling_exceeded_dimensions == ("cpu_micros",)
    assert snapshot.audit.ceiling_exceeded is True
    assert snapshot.audit.halt_required is True
    assert snapshot.audit.to_dict()["resource_overrun_or_deviation_records_supported"] is True


def test_export_requires_the_callers_exact_full_byte_anchor(valid_export: bytes) -> None:
    with pytest.raises(ScientificLedgerError, match="independently pinned digest"):
        audit_scientific_ledger_export(
            valid_export,
            expected_export_sha256="0" * 64,
        )


@pytest.mark.parametrize("drop_final_newline", [False, True])
def test_export_rejects_truncation(
    valid_export: bytes,
    drop_final_newline: bool,
) -> None:
    if drop_final_newline:
        truncated = valid_export[:-1]
    else:
        truncated = b"\n".join(valid_export.splitlines()[:-1]) + b"\n"
    with pytest.raises(ScientificLedgerError):
        _audit(truncated)


def test_export_rejects_reordered_records_with_a_matching_new_anchor(
    valid_export: bytes,
) -> None:
    lines = valid_export.splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    reordered = b"\n".join(lines) + b"\n"

    with pytest.raises(ScientificLedgerError, match="sequence is not contiguous"):
        _audit(reordered)


@pytest.mark.parametrize("mutation", ["signature_subject", "unauthorized_signer"])
def test_export_rejects_record_tampering_even_when_the_new_bytes_are_pinned(
    valid_export: bytes,
    mutation: str,
) -> None:
    tampered = _rewrite_line(valid_export, 1, mutation)

    with pytest.raises(ScientificLedgerError):
        _audit(tampered)


def test_export_replays_uniqueness_state_instead_of_trusting_header_counts(
    valid_export: bytes,
) -> None:
    lines = valid_export.decode("utf-8").splitlines()
    first_record = cast(dict[str, Any], strict_json_loads(lines[1]))
    duplicate = cast(dict[str, Any], strict_json_loads(strict_json_dumps(first_record)))
    duplicate["sequence"] = 2
    duplicate["previous_record_sha256"] = _digest_text(lines[1])
    lines[2] = strict_json_dumps(duplicate)
    forged = ("\n".join(lines) + "\n").encode("utf-8")

    with pytest.raises(ScientificLedgerError, match="identity is already used"):
        _audit(forged)


def test_export_replays_resource_ceiling_state_without_reverifying_signature(
    valid_export: bytes,
) -> None:
    lines = valid_export.decode("utf-8").splitlines()
    header = cast(dict[str, Any], strict_json_loads(lines[0]))
    bindings = ScientificLedgerBindings.from_dict(header["bindings"])
    record = cast(dict[str, Any], strict_json_loads(lines[3]))
    payload = cast(dict[str, Any], record["payload"])
    reserved = cast(dict[str, Any], payload["reserved"])
    reserved["cpu_micros"] = 10_001
    subject = ResourceReservation.from_dict(payload)
    verification = cast(dict[str, Any], record["signature_verification"])
    verification["subject_sha256"] = _digest_bytes(signed_envelope_bytes(bindings, subject))
    record["record_id"] = subject.record_id
    lines[3] = strict_json_dumps(record)
    forged = ("\n".join(lines) + "\n").encode("utf-8")

    with pytest.raises(ScientificLedgerError, match="resource ceiling exceeded"):
        _audit(forged)


@pytest.mark.parametrize(
    "mutation",
    ["header_count", "header_head", "audit_count", "audit_crypto_claim"],
)
def test_export_rejects_header_and_audit_lies(
    valid_export: bytes,
    mutation: str,
) -> None:
    lying = _rewrite_line(valid_export, 0, mutation)

    with pytest.raises(ScientificLedgerError):
        _audit(lying)


@pytest.mark.parametrize(
    "mutation",
    [
        "audit_deviation_count",
        "audit_deviation_dimensions",
        "audit_halt",
        "audit_deviation_capability",
    ],
)
def test_export_rejects_tampered_deviation_audit(
    overrun_export: bytes,
    mutation: str,
) -> None:
    lying = _rewrite_line(overrun_export, 0, mutation)

    with pytest.raises(ScientificLedgerError):
        _audit(lying)


def test_export_rejects_noncanonical_blank_and_extra_lines(valid_export: bytes) -> None:
    malformed = (
        b" " + valid_export,
        valid_export.replace(b"\n", b"\n\n", 1),
        valid_export + b"{}\n",
    )
    for value in malformed:
        with pytest.raises(ScientificLedgerError):
            _audit(value)


def test_export_enforces_exact_bytes_utf8_and_size(
    valid_export: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        audit_scientific_ledger_export(
            cast(bytes, "not-bytes"),
            expected_export_sha256=_digest_text("not-bytes"),
        )
    invalid_utf8 = b"\xff\n"
    with pytest.raises(ScientificLedgerError, match="not UTF-8"):
        _audit(invalid_utf8)
    monkeypatch.setattr(
        scientific_ledger_module,
        "_MAX_SCIENTIFIC_EXPORT_BYTES",
        len(valid_export) - 1,
    )
    with pytest.raises(ScientificLedgerError, match="byte ceiling"):
        _audit(valid_export)
