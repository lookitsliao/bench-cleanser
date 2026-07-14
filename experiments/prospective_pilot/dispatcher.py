"""Claim-before-launch dispatcher for the prospective pilot.

The dispatcher composes the durable scheduler ledger with the bounded route
orchestrator.  It is deliberately single-host and at-most-once: a permanent
claim is never leased, stolen, expired, or replayed.  A hard process death after
claim therefore requires :meth:`ProspectiveDispatcher.recover_claim`; recovery
may ingest an already-completed exact output or halt the task, but never launch
the action again.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import unquote, urlparse

from bench_cleanser.verification.orchestrate import (
    execute_route_acquisition,
    load_route_acquisition_record,
    validate_completed_route_acquisition,
)
from experiments.prospective_pilot.ledger import (
    ClaimedDispatchEnvelope,
    ExecutableActionSpec,
    IncidentReceipt,
    LedgerConflict,
    ProspectiveLedger,
    ReservationRequest,
    ResultReceipt,
    RoundCommitReceipt,
)
from experiments.prospective_pilot.scheduler import TaskRoundDecision

DispatchState = Literal["already_claimed", "completed", "recovered", "halted"]


class DispatchExecutionError(RuntimeError):
    """A permanently claimed dispatch failed and was conservatively halted."""

    def __init__(
        self,
        *,
        phase: str,
        claim_id: str,
        incident_id: str | None,
    ) -> None:
        self.phase = phase
        self.claim_id = claim_id
        self.incident_id = incident_id
        suffix = "" if incident_id is None else f"; incident={incident_id}"
        super().__init__(
            f"permanently claimed dispatch failed during {phase}{suffix}"
        )


@dataclass(frozen=True)
class DispatchOutcome:
    """Typed outcome that never mistakes a losing claim for completed work."""

    state: DispatchState
    dispatch_id: str
    acquisition_id: str
    claim_id: str | None
    envelope_sha256: str
    result: ResultReceipt | None = None
    incident: IncidentReceipt | None = None
    artifact_store_id: str | None = None
    artifact_locator: str | None = None
    artifact_sha256: str | None = None



@dataclass(frozen=True)
class WorkerExitReceipt:
    """Operator evidence required before halting an ambiguous permanent claim."""

    operator_id: str
    claimant: str
    worker_exit_receipt_sha256: str
    observed_at: str
    exit_code: int | None

    def __post_init__(self) -> None:
        for name in ("operator_id", "claimant"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty identifier")
        if not re.fullmatch(r"[0-9a-f]{64}", self.worker_exit_receipt_sha256):
            raise ValueError("worker exit receipt must be a lowercase SHA-256")
        datetime.strptime(self.observed_at, "%Y-%m-%dT%H:%M:%S.%fZ")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ValueError("worker exit_code must be null or an integer")


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _retained_artifact_identity(
    claimed: ClaimedDispatchEnvelope,
    record: dict[str, object],
) -> tuple[str, str]:
    observation = record.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("completed output omits its typed observation")
    metadata = observation.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("completed output omits observation metadata")
    locator = metadata.get("artifact_locator")
    digest = metadata.get("artifact_sha256")
    if not isinstance(locator, str) or not isinstance(digest, str):
        raise ValueError("completed output omits raw-artifact identity")
    parsed = urlparse(locator)
    if parsed.scheme != "file" or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("raw-artifact locator is not a credential-free local file")
    declared_artifact = pathlib.Path(unquote(parsed.path))
    if declared_artifact.is_symlink():
        raise ValueError("raw-artifact locator cannot reference a symbolic link")
    artifact = declared_artifact.resolve(strict=True)
    retention = claimed.dispatch.action_spec.artifact_retention
    declared_root = pathlib.Path(retention.artifact_directory)
    if declared_root.is_symlink():
        raise ValueError("raw-artifact retention root cannot be a symbolic link")
    root = declared_root.resolve(strict=True)
    if root != declared_root:
        raise ValueError("raw-artifact retention root must be canonical")
    expected_declared = declared_root / f"{claimed.dispatch.acquisition_id}.json"
    if expected_declared.is_symlink():
        raise ValueError("retained raw artifact cannot be a symbolic link")
    expected = expected_declared.resolve(strict=True)
    if artifact != expected or not artifact.is_file():
        raise ValueError("raw artifact differs from its committed retention identity")
    payload = artifact.read_bytes()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("retained raw-artifact digest differs from the observation")
    return locator, digest


class ProspectiveDispatcher:
    """Production boundary for durable commit, permanent claim, and launch."""

    def __init__(self, ledger: ProspectiveLedger, *, claimant: str) -> None:
        if not isinstance(ledger, ProspectiveLedger):
            raise TypeError("ledger must be a ProspectiveLedger")
        if not isinstance(claimant, str) or not claimant:
            raise ValueError("claimant must be a non-empty identifier")
        self.ledger = ledger
        self.claimant = claimant

    def commit_round(
        self,
        round_decision: TaskRoundDecision,
        *,
        committed_at: str,
        action_spec_preimages: dict[str, bytes],
        reservations: tuple[ReservationRequest, ...],
    ) -> RoundCommitReceipt:
        """Commit the complete sibling round and all launch preimages atomically."""

        reservations_by_acquisition = {
            item.acquisition_id: item for item in reservations
        }
        for scheduled in round_decision.scheduled_decisions:
            decision = scheduled.logged_policy_decision
            if decision.terminal:
                continue
            assert decision.acquisition_id is not None
            preimage = action_spec_preimages.get(
                decision.chosen_offer.action_spec_sha256
            )
            if preimage is None:
                raise ValueError("chosen action omits its executable spec preimage")
            spec = ExecutableActionSpec.from_preimage(preimage)
            reservation = reservations_by_acquisition.get(decision.acquisition_id)
            if reservation is None:
                raise ValueError("chosen action omits its resource reservation")
            spec.validate_dispatch(
                action_spec_sha256=decision.chosen_offer.action_spec_sha256,
                decision=decision,
                reservation=reservation,
                plan=spec.realized_plan(decision.acquisition_id),
            )
        return self.ledger.commit_round(
            round_decision,
            committed_at=committed_at,
            action_spec_preimages=action_spec_preimages,
            reservations=reservations,
        )

    def commit_and_dispatch(
        self,
        round_decision: TaskRoundDecision,
        *,
        committed_at: str,
        action_spec_preimages: dict[str, bytes],
        reservations: tuple[ReservationRequest, ...],
        acquisition_id: str,
        claimed_at: str | None = None,
        completed_at: str | None = None,
    ) -> tuple[RoundCommitReceipt, DispatchOutcome]:
        """Atomically commit the round before claiming and launching one action."""

        receipt = self.commit_round(
            round_decision,
            committed_at=committed_at,
            action_spec_preimages=action_spec_preimages,
            reservations=reservations,
        )
        outcome = self.dispatch_committed(
            acquisition_id=acquisition_id,
            claimed_at=claimed_at,
            completed_at=completed_at,
        )
        return receipt, outcome

    def dispatch_committed(
        self,
        *,
        acquisition_id: str,
        claimed_at: str | None = None,
        completed_at: str | None = None,
    ) -> DispatchOutcome:
        """Claim exactly once, launch, validate, ingest, and retain one action."""

        envelope = self.ledger.load_dispatch_envelope(acquisition_id)
        manifest_before, route_decision, plan = envelope.action_spec.execution_inputs(
            acquisition_id
        )
        envelope.validate_execution_inputs(
            manifest_before=manifest_before,
            route_decision=route_decision,
            plan=plan,
        )
        claimed = self.ledger.claim_executable_dispatch(
            acquisition_id,
            claimant=self.claimant,
            claimed_at=claimed_at or _utc_timestamp(),
            manifest_before=manifest_before,
            route_decision=route_decision,
            plan=plan,
        )
        if claimed is None:
            return DispatchOutcome(
                state="already_claimed",
                dispatch_id=envelope.dispatch_id,
                acquisition_id=envelope.acquisition_id,
                claim_id=None,
                envelope_sha256=envelope.envelope_sha256,
            )

        phase = "post_claim_preflight"
        try:
            if claimed.dispatch.envelope_sha256 != envelope.envelope_sha256:
                raise ValueError("dispatch envelope changed across the permanent claim")
            claimed.dispatch.validate_execution_inputs(
                manifest_before=manifest_before,
                route_decision=route_decision,
                plan=plan,
            )
            phase = "route_acquisition"
            execute_route_acquisition(manifest_before, route_decision, plan)
            phase = "completed_output_load"
            with pathlib.Path(plan.output_path).open(encoding="utf-8") as stream:
                record = load_route_acquisition_record(stream)
            phase = "raw_artifact_retention_pre_ingest"
            locator, artifact_sha256 = _retained_artifact_identity(claimed, record)
            phase = "strict_result_ingest"
            result = self.ledger.ingest_completed_route_acquisition(
                claim_id=claimed.claim.claim_id,
                record=record,
                manifest_before=manifest_before,
                decision=route_decision,
                plan=plan,
                completed_at=completed_at or _utc_timestamp(),
            )
            phase = "raw_artifact_retention_post_ingest"
            post_locator, post_sha256 = _retained_artifact_identity(claimed, record)
            if post_locator != locator or post_sha256 != artifact_sha256:
                raise ValueError("raw-artifact retention identity changed after ingest")
            return DispatchOutcome(
                state="completed",
                dispatch_id=envelope.dispatch_id,
                acquisition_id=envelope.acquisition_id,
                claim_id=claimed.claim.claim_id,
                envelope_sha256=envelope.envelope_sha256,
                result=result,
                artifact_store_id=envelope.action_spec.artifact_retention.store_id,
                artifact_locator=locator,
                artifact_sha256=artifact_sha256,
            )
        except BaseException as exc:
            if pathlib.Path(plan.output_path).is_file():
                try:
                    return self.recover_completed_claim(
                        claim_id=claimed.claim.claim_id,
                        completed_at=completed_at,
                    )
                except BaseException:
                    pass
            raise DispatchExecutionError(
                phase=phase,
                claim_id=claimed.claim.claim_id,
                incident_id=None,
            ) from exc

    def recover_completed_claim(
        self,
        *,
        claim_id: str,
        completed_at: str | None = None,
    ) -> DispatchOutcome:
        """Ingest an existing exact output; never execute and never auto-halt."""

        claimed = self.ledger.load_claimed_dispatch_envelope(claim_id)
        envelope = claimed.dispatch
        manifest_before, route_decision, plan = envelope.action_spec.execution_inputs(
            envelope.acquisition_id
        )
        envelope.validate_execution_inputs(
            manifest_before=manifest_before,
            route_decision=route_decision,
            plan=plan,
        )
        with pathlib.Path(plan.output_path).open(encoding="utf-8") as stream:
            record = load_route_acquisition_record(stream)
        locator, artifact_sha256 = _retained_artifact_identity(claimed, record)
        validated = validate_completed_route_acquisition(
            record,
            manifest_before=manifest_before,
            decision=route_decision,
            plan=plan,
        )
        existing = self.ledger.load_result_identity_for_claim(claim_id)
        if existing is not None:
            if (
                existing.completed_output_sha256 != validated.output_sha256
                or existing.artifact_sha256 != artifact_sha256
            ):
                raise LedgerConflict(
                    "existing result differs from the recoverable completed output"
                )
            result = existing.receipt
        else:
            result = self.ledger.ingest_completed_route_acquisition(
                claim_id=claim_id,
                record=record,
                manifest_before=manifest_before,
                decision=route_decision,
                plan=plan,
                completed_at=completed_at or _utc_timestamp(),
            )
        return DispatchOutcome(
            state="recovered",
            dispatch_id=envelope.dispatch_id,
            acquisition_id=envelope.acquisition_id,
            claim_id=claim_id,
            envelope_sha256=envelope.envelope_sha256,
            result=result,
            artifact_store_id=envelope.action_spec.artifact_retention.store_id,
            artifact_locator=locator,
            artifact_sha256=artifact_sha256,
        )

    def halt_abandoned_claim(
        self,
        *,
        claim_id: str,
        worker_exit: WorkerExitReceipt,
        halted_at: str,
    ) -> IncidentReceipt:
        """Explicitly halt a confirmed-dead claimant without ever redispatching."""

        claimed = self.ledger.load_claimed_dispatch_envelope(claim_id)
        if worker_exit.claimant != claimed.claim.claimant:
            raise ValueError("worker-exit receipt names a different claimant")
        try:
            self.recover_completed_claim(claim_id=claim_id)
        except BaseException:
            pass
        else:
            raise LedgerConflict(
                "a valid completed output exists; the claim cannot be halted"
            )
        return self.ledger.record_claimed_crash(
            claim_id=claim_id,
            occurred_at=halted_at,
            reason_code="operator_confirmed_worker_exit",
            details={
                "operator_id": worker_exit.operator_id,
                "worker_exit_receipt_sha256": (
                    worker_exit.worker_exit_receipt_sha256
                ),
                "worker_exit_observed_at": worker_exit.observed_at,
                "exit_code": worker_exit.exit_code,
                "operator_action": "halt_without_replay",
            },
        )
