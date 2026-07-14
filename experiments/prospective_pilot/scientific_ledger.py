"""Durable non-policy evidence and resource ledger for the pilot.

The behavior-policy ledger deliberately cannot contain curator-only evidence.
This module provides a separate append-only boundary for curator records, resource
settlement, and the deterministic bootstrap intended to precede policy round
zero.  Human adjudication is intentionally deferred until an opaque packet and
custodian-map contract can avoid exposing real frame identities.

Authentication remains an explicit external boundary.  A caller must supply a
``SignatureVerifier`` which verifies the exact domain-bound envelope bytes and
returns an independently retained verification-artifact digest.  The ledger
stores the detached signature bytes and verifier identity, but never claims
that a self-declared digest is a signature or that a later audit re-ran the
external verifier.

The local hash chain detects accidental or unsophisticated row mutation.  It
does not prevent a database writer from reordering a valid signed record set or
truncating a suffix; an independently signed checkpoint remains required.

This module is collection infrastructure.  It does not activate the protocol,
name reviewers or custodians, authenticate a Docker provisioner, or make a
scientific-readiness claim.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import pathlib
import re
import sqlite3
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, cast

from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    RouteAction,
)
from bench_cleanser.verification.policy_log import RouterRouteStep

SCIENTIFIC_LEDGER_SCHEMA_VERSION = "prospective-pilot-scientific-ledger-0.1.0"
SCIENTIFIC_RECORD_SCHEMA_VERSION = "prospective-pilot-scientific-record-0.1.0"
SCIENTIFIC_EXPORT_SCHEMA_VERSION = "prospective-pilot-scientific-export-0.1.0"
BOOTSTRAP_RECEIPT_SCHEMA_VERSION = "prospective-pilot-bootstrap-receipt-0.1.0"
CURATOR_RECEIPT_SCHEMA_VERSION = "prospective-pilot-curator-receipt-0.1.0"
RESOURCE_RESERVATION_SCHEMA_VERSION = "prospective-pilot-resource-reservation-0.1.0"
RESOURCE_SETTLEMENT_SCHEMA_VERSION = "prospective-pilot-resource-settlement-0.1.0"
SIGNATURE_VERIFICATION_SCHEMA_VERSION = "prospective-pilot-signature-verification-0.1.0"
SIGNED_ENVELOPE_SCHEMA_VERSION = "prospective-pilot-signed-envelope-0.1.0"
STUDY_ID = "matched-24-independent-evidence-development-pilot-v2"
GENESIS_RECORD_SHA256 = "0" * 64
_MAX_SIGNATURE_BYTES = 1024 * 1024
_MAX_RECORD_BYTES = 4 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+@-]{0,254}\Z")
_TIMESTAMP_RE = re.compile(
    r"(?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12][0-9]|3[01])T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{6}Z\Z"
)

_LEDGER_BINDINGS_TABLE_SQL = (
    "CREATE TABLE ledger_bindings ("
    "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
    "binding_json TEXT NOT NULL, "
    "binding_sha256 TEXT NOT NULL)"
)
_SCIENTIFIC_RECORDS_TABLE_SQL = (
    "CREATE TABLE scientific_records ("
    "sequence INTEGER PRIMARY KEY, "
    "kind TEXT NOT NULL, "
    "record_id TEXT NOT NULL UNIQUE, "
    "task_id TEXT, "
    "candidate_id TEXT, "
    "occurred_at TEXT NOT NULL, "
    "payload_json TEXT NOT NULL, "
    "verification_json TEXT NOT NULL, "
    "previous_record_sha256 TEXT NOT NULL, "
    "record_json TEXT NOT NULL, "
    "record_sha256 TEXT NOT NULL UNIQUE)"
)
_SCIENTIFIC_RECORDS_NO_UPDATE_TRIGGER_SQL = (
    "CREATE TRIGGER scientific_records_no_update "
    "BEFORE UPDATE ON scientific_records "
    "BEGIN SELECT RAISE(ABORT, 'scientific records are append-only'); END"
)
_SCIENTIFIC_RECORDS_NO_DELETE_TRIGGER_SQL = (
    "CREATE TRIGGER scientific_records_no_delete "
    "BEFORE DELETE ON scientific_records "
    "BEGIN SELECT RAISE(ABORT, 'scientific records are append-only'); END"
)
_LEDGER_BINDINGS_NO_UPDATE_TRIGGER_SQL = (
    "CREATE TRIGGER ledger_bindings_no_update "
    "BEFORE UPDATE ON ledger_bindings "
    "BEGIN SELECT RAISE(ABORT, 'ledger bindings are immutable'); END"
)
_LEDGER_BINDINGS_NO_DELETE_TRIGGER_SQL = (
    "CREATE TRIGGER ledger_bindings_no_delete "
    "BEFORE DELETE ON ledger_bindings "
    "BEGIN SELECT RAISE(ABORT, 'ledger bindings are immutable'); END"
)
_SCHEMA_OBJECTS = {
    ("table", "ledger_bindings"): (
        "ledger_bindings",
        _LEDGER_BINDINGS_TABLE_SQL,
    ),
    ("table", "scientific_records"): (
        "scientific_records",
        _SCIENTIFIC_RECORDS_TABLE_SQL,
    ),
    ("trigger", "scientific_records_no_update"): (
        "scientific_records",
        _SCIENTIFIC_RECORDS_NO_UPDATE_TRIGGER_SQL,
    ),
    ("trigger", "scientific_records_no_delete"): (
        "scientific_records",
        _SCIENTIFIC_RECORDS_NO_DELETE_TRIGGER_SQL,
    ),
    ("trigger", "ledger_bindings_no_update"): (
        "ledger_bindings",
        _LEDGER_BINDINGS_NO_UPDATE_TRIGGER_SQL,
    ),
    ("trigger", "ledger_bindings_no_delete"): (
        "ledger_bindings",
        _LEDGER_BINDINGS_NO_DELETE_TRIGGER_SQL,
    ),
}


class ScientificLedgerError(ValueError):
    """A scientific-ledger record or durable state is invalid."""


class ScientificLedgerConflict(ScientificLedgerError):
    """An immutable scientific identity already has different content."""


class ResourceCeilingExceeded(ScientificLedgerError):
    """A reservation or settlement would exceed the frozen resource ceiling."""


class ScientificRecordKind(str, Enum):
    BOOTSTRAP = "bootstrap"
    CURATOR = "curator"
    RESOURCE_RESERVATION = "resource_reservation"
    RESOURCE_SETTLEMENT = "resource_settlement"


class ResourceOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return strict_json_dumps(value).encode("utf-8")


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ScientificLedgerError(f"{field_name} must be a JSON object")
    return value


def _array(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ScientificLedgerError(f"{field_name} must be a JSON array")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], field_name: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ScientificLedgerError(
            f"{field_name} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: Any, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ScientificLedgerError(
            f"{field_name} must be a non-empty trimmed string without controls"
        )
    return value


def _identifier(value: Any, field_name: str) -> str:
    result = _string(value, field_name)
    if _IDENTIFIER_RE.fullmatch(result) is None:
        raise ScientificLedgerError(f"{field_name} must be a safe identifier")
    return result


def _digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ScientificLedgerError(f"{field_name} must be a lowercase SHA-256")
    return value


def _candidate(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _CANDIDATE_RE.fullmatch(value) is None:
        raise ScientificLedgerError(f"{field_name} must be a sha256:-prefixed candidate identity")
    return value


def _timestamp(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _TIMESTAMP_RE.fullmatch(value) is None:
        raise ScientificLedgerError(f"{field_name} must be UTC with six fractional digits")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ScientificLedgerError(f"{field_name} is not a real UTC timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise ScientificLedgerError(f"{field_name} is not canonical UTC")
    return value


def _nonnegative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScientificLedgerError(f"{field_name} must be a non-negative integer")
    return value


def _optional_task(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field_name)


def _optional_candidate(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _candidate(value, field_name)


def _route_from_dict(value: Any) -> RouterRouteStep:
    data = _object(value, "bootstrap.route")
    _exact_fields(
        data,
        {
            "action",
            "policy_version",
            "candidate_risk",
            "verifier_risk",
            "expected_information_gain",
            "estimated_relative_cost",
            "scores_calibrated",
            "calibration_id",
        },
        "bootstrap.route",
    )
    try:
        action = RouteAction(data["action"])
    except (TypeError, ValueError) as exc:
        raise ScientificLedgerError("bootstrap.route.action is invalid") from exc
    try:
        return RouterRouteStep(
            action=action,
            policy_version=cast(str, data["policy_version"]),
            candidate_risk=cast(float, data["candidate_risk"]),
            verifier_risk=cast(float, data["verifier_risk"]),
            expected_information_gain=cast(float, data["expected_information_gain"]),
            estimated_relative_cost=cast(float, data["estimated_relative_cost"]),
            scores_calibrated=cast(bool, data["scores_calibrated"]),
            calibration_id=cast(str, data["calibration_id"]),
        )
    except (TypeError, ValueError) as exc:
        raise ScientificLedgerError(f"invalid bootstrap route: {exc}") from exc


@dataclass(frozen=True)
class ResourceUsage:
    """Dimension-qualified integer usage; time is represented in microseconds."""

    acquisition_events: int = 0
    process_launches: int = 0
    cpu_micros: int = 0
    worker_wall_micros: int = 0
    peak_rss_bytes: int = 0
    storage_bytes: int = 0
    semantic_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usd_micros: int = 0
    human_minutes: int = 0

    def __post_init__(self) -> None:
        for name in self.field_names():
            _nonnegative_integer(getattr(self, name), f"resource_usage.{name}")

    @staticmethod
    def field_names() -> tuple[str, ...]:
        return (
            "acquisition_events",
            "process_launches",
            "cpu_micros",
            "worker_wall_micros",
            "peak_rss_bytes",
            "storage_bytes",
            "semantic_calls",
            "input_tokens",
            "output_tokens",
            "usd_micros",
            "human_minutes",
        )

    def to_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.field_names()}

    @classmethod
    def from_dict(cls, value: Any) -> ResourceUsage:
        data = _object(value, "resource_usage")
        _exact_fields(data, set(cls.field_names()), "resource_usage")
        return cls(
            **{
                name: _nonnegative_integer(data[name], f"resource_usage.{name}")
                for name in cls.field_names()
            }
        )

    def is_zero(self) -> bool:
        return all(getattr(self, name) == 0 for name in self.field_names())

    def plus(self, other: ResourceUsage) -> ResourceUsage:
        if not isinstance(other, ResourceUsage):
            raise ScientificLedgerError("resource usage can only add ResourceUsage")
        values = {
            name: (
                max(getattr(self, name), getattr(other, name))
                if name == "peak_rss_bytes"
                else getattr(self, name) + getattr(other, name)
            )
            for name in self.field_names()
        }
        return ResourceUsage(**values)

    def no_more_than(self, other: ResourceUsage) -> bool:
        if not isinstance(other, ResourceUsage):
            return False
        return all(getattr(self, name) <= getattr(other, name) for name in self.field_names())


@dataclass(frozen=True)
class ResourceLimits:
    maximum_concurrent_workers: int
    maximum_usage: ResourceUsage
    maximum_deterministic_static_acquisitions: int
    maximum_curator_hardening_attempts: int

    def __post_init__(self) -> None:
        if (
            _nonnegative_integer(
                self.maximum_concurrent_workers,
                "resource_limits.maximum_concurrent_workers",
            )
            == 0
        ):
            raise ScientificLedgerError("maximum_concurrent_workers must be positive")
        if not isinstance(self.maximum_usage, ResourceUsage):
            raise ScientificLedgerError("maximum_usage must be ResourceUsage")
        if self.maximum_usage.is_zero():
            raise ScientificLedgerError("maximum_usage cannot be all zero")
        if (
            _nonnegative_integer(
                self.maximum_deterministic_static_acquisitions,
                "resource_limits.maximum_deterministic_static_acquisitions",
            )
            == 0
        ):
            raise ScientificLedgerError(
                "maximum_deterministic_static_acquisitions must be positive"
            )
        if (
            _nonnegative_integer(
                self.maximum_curator_hardening_attempts,
                "resource_limits.maximum_curator_hardening_attempts",
            )
            == 0
        ):
            raise ScientificLedgerError("maximum_curator_hardening_attempts must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "maximum_concurrent_workers": self.maximum_concurrent_workers,
            "maximum_usage": self.maximum_usage.to_dict(),
            "maximum_deterministic_static_acquisitions": (
                self.maximum_deterministic_static_acquisitions
            ),
            "maximum_curator_hardening_attempts": (self.maximum_curator_hardening_attempts),
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceLimits:
        data = _object(value, "resource_limits")
        _exact_fields(
            data,
            {
                "maximum_concurrent_workers",
                "maximum_usage",
                "maximum_deterministic_static_acquisitions",
                "maximum_curator_hardening_attempts",
            },
            "resource_limits",
        )
        return cls(
            maximum_concurrent_workers=_nonnegative_integer(
                data["maximum_concurrent_workers"],
                "resource_limits.maximum_concurrent_workers",
            ),
            maximum_usage=ResourceUsage.from_dict(data["maximum_usage"]),
            maximum_deterministic_static_acquisitions=_nonnegative_integer(
                data["maximum_deterministic_static_acquisitions"],
                "resource_limits.maximum_deterministic_static_acquisitions",
            ),
            maximum_curator_hardening_attempts=_nonnegative_integer(
                data["maximum_curator_hardening_attempts"],
                "resource_limits.maximum_curator_hardening_attempts",
            ),
        )


@dataclass(frozen=True)
class ScientificLedgerBindings:
    """Exact protocol/frame/resource identities governing one ledger."""

    protocol_sha256: str
    frame_manifest_sha256: str
    resource_ceiling_sha256: str
    task_candidates: tuple[tuple[str, tuple[str, ...]], ...]
    resource_limits: ResourceLimits
    bootstrap_signer_ids: tuple[str, ...] = ()
    curator_signer_ids: tuple[str, ...] = ()
    reservation_signer_ids: tuple[str, ...] = ()
    meter_signer_ids: tuple[str, ...] = ()
    study_id: str = STUDY_ID
    schema_version: str = SCIENTIFIC_LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCIENTIFIC_LEDGER_SCHEMA_VERSION:
            raise ScientificLedgerError("unsupported scientific-ledger schema")
        if self.study_id != STUDY_ID:
            raise ScientificLedgerError("scientific ledger uses a different study_id")
        for name in (
            "protocol_sha256",
            "frame_manifest_sha256",
            "resource_ceiling_sha256",
        ):
            _digest(getattr(self, name), f"bindings.{name}")
        if not isinstance(self.task_candidates, (list, tuple)):
            raise ScientificLedgerError("task_candidates must be a sequence")
        normalized = tuple(
            (
                _identifier(task_id, f"task_candidates[{index}].task_id"),
                tuple(
                    _candidate(candidate_id, f"task_candidates[{index}].candidate")
                    for candidate_id in candidates
                ),
            )
            for index, (task_id, candidates) in enumerate(self.task_candidates)
        )
        if tuple(task_id for task_id, _ in normalized) != tuple(
            sorted(task_id for task_id, _ in normalized)
        ):
            raise ScientificLedgerError("task_candidates must be sorted by task_id")
        if len({task_id for task_id, _ in normalized}) != len(normalized):
            raise ScientificLedgerError("task_candidates contains duplicate tasks")
        all_candidates: list[str] = []
        for task_id, candidates in normalized:
            if not candidates or tuple(sorted(candidates)) != candidates:
                raise ScientificLedgerError(
                    f"candidates for {task_id} must be non-empty and sorted"
                )
            if len(candidates) != len(set(candidates)):
                raise ScientificLedgerError(f"candidates for {task_id} repeat")
            all_candidates.extend(candidates)
        if len(all_candidates) != len(set(all_candidates)):
            raise ScientificLedgerError("candidate identities must be globally unique")
        if not isinstance(self.resource_limits, ResourceLimits):
            raise ScientificLedgerError("resource_limits must be ResourceLimits")
        role_signers: dict[str, tuple[str, ...]] = {}
        for role in ("bootstrap", "curator", "reservation", "meter"):
            raw = getattr(self, f"{role}_signer_ids")
            if not isinstance(raw, (list, tuple)):
                raise ScientificLedgerError(f"{role}_signer_ids must be a sequence")
            signers = tuple(
                _identifier(item, f"{role}_signer_ids[{index}]") for index, item in enumerate(raw)
            )
            if signers != tuple(sorted(signers)) or len(signers) != len(set(signers)):
                raise ScientificLedgerError(f"{role}_signer_ids must be sorted and unique")
            object.__setattr__(self, f"{role}_signer_ids", signers)
            role_signers[role] = signers
        seen_signers: dict[str, str] = {}
        for role, signers in role_signers.items():
            for signer in signers:
                prior_role = seen_signers.get(signer)
                if prior_role is not None:
                    raise ScientificLedgerError(
                        f"signer {signer!r} cannot serve both {prior_role} and {role} roles"
                    )
                seen_signers[signer] = role
        object.__setattr__(self, "task_candidates", normalized)

    @property
    def candidate_count(self) -> int:
        return sum(len(candidates) for _, candidates in self.task_candidates)

    @property
    def task_count(self) -> int:
        return len(self.task_candidates)

    def candidates_for(self, task_id: str) -> tuple[str, ...]:
        for bound_task_id, candidates in self.task_candidates:
            if bound_task_id == task_id:
                return candidates
        raise ScientificLedgerError(f"task {task_id!r} is outside the frozen frame")

    def assert_candidate(self, task_id: str, candidate_id: str) -> None:
        if candidate_id not in self.candidates_for(task_id):
            raise ScientificLedgerError("task/candidate pair is outside the frozen frame")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "protocol_sha256": self.protocol_sha256,
            "frame_manifest_sha256": self.frame_manifest_sha256,
            "resource_ceiling_sha256": self.resource_ceiling_sha256,
            "task_candidates": [
                {"task_id": task_id, "candidate_ids": list(candidates)}
                for task_id, candidates in self.task_candidates
            ],
            "resource_limits": self.resource_limits.to_dict(),
            "authority_policy": {
                "bootstrap_signer_ids": list(self.bootstrap_signer_ids),
                "curator_signer_ids": list(self.curator_signer_ids),
                "reservation_signer_ids": list(self.reservation_signer_ids),
                "meter_signer_ids": list(self.meter_signer_ids),
            },
        }

    @classmethod
    def from_dict(cls, value: Any) -> ScientificLedgerBindings:
        data = _object(value, "bindings")
        _exact_fields(
            data,
            {
                "schema_version",
                "study_id",
                "protocol_sha256",
                "frame_manifest_sha256",
                "resource_ceiling_sha256",
                "task_candidates",
                "resource_limits",
                "authority_policy",
            },
            "bindings",
        )
        tasks = _array(data["task_candidates"], "bindings.task_candidates")
        authority = _object(data["authority_policy"], "bindings.authority_policy")
        _exact_fields(
            authority,
            {
                "bootstrap_signer_ids",
                "curator_signer_ids",
                "reservation_signer_ids",
                "meter_signer_ids",
            },
            "bindings.authority_policy",
        )
        signer_values: dict[str, tuple[str, ...]] = {}
        for role in ("bootstrap", "curator", "reservation", "meter"):
            raw_signers = _array(
                authority[f"{role}_signer_ids"],
                f"bindings.authority_policy.{role}_signer_ids",
            )
            signer_values[role] = tuple(cast(str, item) for item in raw_signers)
        normalized: list[tuple[str, tuple[str, ...]]] = []
        for index, raw in enumerate(tasks):
            item = _object(raw, f"bindings.task_candidates[{index}]")
            _exact_fields(
                item,
                {"task_id", "candidate_ids"},
                f"bindings.task_candidates[{index}]",
            )
            candidates = _array(
                item["candidate_ids"],
                f"bindings.task_candidates[{index}].candidate_ids",
            )
            normalized.append(
                (
                    cast(str, item["task_id"]),
                    tuple(cast(str, candidate) for candidate in candidates),
                )
            )
        return cls(
            schema_version=cast(str, data["schema_version"]),
            study_id=cast(str, data["study_id"]),
            protocol_sha256=cast(str, data["protocol_sha256"]),
            frame_manifest_sha256=cast(str, data["frame_manifest_sha256"]),
            resource_ceiling_sha256=cast(str, data["resource_ceiling_sha256"]),
            task_candidates=tuple(normalized),
            resource_limits=ResourceLimits.from_dict(data["resource_limits"]),
            bootstrap_signer_ids=signer_values["bootstrap"],
            curator_signer_ids=signer_values["curator"],
            reservation_signer_ids=signer_values["reservation"],
            meter_signer_ids=signer_values["meter"],
        )

    @property
    def canonical_sha256(self) -> str:
        return _sha256(_canonical_bytes(self.to_dict()))


def load_scientific_ledger_bindings(root: pathlib.Path) -> ScientificLedgerBindings:
    """Load bytes only after the authoritative draft validator accepts them."""

    repository_root = pathlib.Path(root).resolve(strict=True)
    protocol_path = repository_root / "experiments/prospective_pilot/preregistration.json"
    frame_path = repository_root / "experiments/prospective_pilot/frame_manifest.json"
    resource_path = repository_root / "experiments/prospective_pilot/resource_ceiling.json"
    protocol_bytes = protocol_path.read_bytes()
    frame_bytes = frame_path.read_bytes()
    resource_bytes = resource_path.read_bytes()
    try:
        from experiments.prospective_pilot.validate_protocol import validate_protocol

        validated = validate_protocol(repository_root)
    except (OSError, ValueError) as exc:
        raise ScientificLedgerError(
            f"authoritative prospective protocol validation failed: {exc}"
        ) from exc
    expected_hashes = {
        "protocol": _sha256(protocol_bytes),
        "frame_manifest": _sha256(frame_bytes),
        "resource_ceiling": _sha256(resource_bytes),
    }
    if (
        validated.protocol_sha256 != expected_hashes["protocol"]
        or validated.configuration_sha256.get("frame_manifest") != expected_hashes["frame_manifest"]
        or validated.configuration_sha256.get("resource_ceiling")
        != expected_hashes["resource_ceiling"]
    ):
        raise ScientificLedgerError(
            "authoritative validator returned different protocol/frame/resource hashes"
        )
    try:
        protocol = _object(strict_json_loads(protocol_bytes.decode("utf-8")), "protocol")
        frame = _object(strict_json_loads(frame_bytes.decode("utf-8")), "frame")
        resource = _object(strict_json_loads(resource_bytes.decode("utf-8")), "resource_ceiling")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ScientificLedgerError(f"invalid repository binding JSON: {exc}") from exc
    if (
        protocol.get("study_id") != STUDY_ID
        or frame.get("study_id") != STUDY_ID
        or resource.get("study_id") != STUDY_ID
    ):
        raise ScientificLedgerError("repository binding study identities differ")
    raw_tasks = _array(frame.get("tasks"), "frame.tasks")
    tasks: list[tuple[str, tuple[str, ...]]] = []
    for index, raw in enumerate(raw_tasks):
        item = _object(raw, f"frame.tasks[{index}]")
        _exact_fields(item, {"task_id", "candidate_ids"}, f"frame.tasks[{index}]")
        candidates = _array(item["candidate_ids"], f"frame.tasks[{index}].candidate_ids")
        tasks.append(
            (
                cast(str, item["task_id"]),
                tuple(cast(str, candidate) for candidate in candidates),
            )
        )
    decision = _object(resource.get("decision_limits"), "resource.decision_limits")
    compute = _object(resource.get("compute_limits"), "resource.compute_limits")
    semantic = _object(resource.get("semantic_limits"), "resource.semantic_limits")
    human = _object(resource.get("human_limits"), "resource.human_limits")
    maximum_usage = ResourceUsage(
        acquisition_events=_nonnegative_integer(
            decision.get("maximum_total_acquisition_events"),
            "resource.maximum_total_acquisition_events",
        ),
        process_launches=_nonnegative_integer(
            compute.get("maximum_total_process_launches"),
            "resource.maximum_total_process_launches",
        ),
        cpu_micros=_nonnegative_integer(
            compute.get("maximum_cumulative_cpu_seconds"),
            "resource.maximum_cumulative_cpu_seconds",
        )
        * 1_000_000,
        worker_wall_micros=_nonnegative_integer(
            compute.get("maximum_cumulative_worker_wall_seconds"),
            "resource.maximum_cumulative_worker_wall_seconds",
        )
        * 1_000_000,
        peak_rss_bytes=_nonnegative_integer(
            compute.get("maximum_peak_rss_bytes_per_process"),
            "resource.maximum_peak_rss_bytes_per_process",
        ),
        storage_bytes=_nonnegative_integer(
            compute.get("maximum_total_storage_bytes"),
            "resource.maximum_total_storage_bytes",
        ),
        semantic_calls=_nonnegative_integer(
            semantic.get("maximum_calls"), "resource.maximum_calls"
        ),
        input_tokens=_nonnegative_integer(
            semantic.get("maximum_input_tokens"), "resource.maximum_input_tokens"
        ),
        output_tokens=_nonnegative_integer(
            semantic.get("maximum_output_tokens"), "resource.maximum_output_tokens"
        ),
        usd_micros=_nonnegative_integer(
            semantic.get("maximum_usd_micros"), "resource.maximum_usd_micros"
        ),
        human_minutes=_nonnegative_integer(
            human.get("maximum_human_minutes"), "resource.maximum_human_minutes"
        ),
    )
    limits = ResourceLimits(
        maximum_concurrent_workers=_nonnegative_integer(
            compute.get("maximum_concurrent_workers"),
            "resource.maximum_concurrent_workers",
        ),
        maximum_usage=maximum_usage,
        maximum_deterministic_static_acquisitions=_nonnegative_integer(
            decision.get("maximum_deterministic_static_acquisitions"),
            "resource.maximum_deterministic_static_acquisitions",
        ),
        maximum_curator_hardening_attempts=_nonnegative_integer(
            decision.get("maximum_curator_hardening_attempts"),
            "resource.maximum_curator_hardening_attempts",
        ),
    )
    return ScientificLedgerBindings(
        protocol_sha256=expected_hashes["protocol"],
        frame_manifest_sha256=expected_hashes["frame_manifest"],
        resource_ceiling_sha256=expected_hashes["resource_ceiling"],
        task_candidates=tuple(tasks),
        resource_limits=limits,
    )


@dataclass(frozen=True)
class VerifierAttestation:
    """Identity returned only after an external verifier accepts a signature."""

    verifier_id: str
    verifier_version: str
    verification_artifact_sha256: str
    verified_at: str

    def __post_init__(self) -> None:
        _identifier(self.verifier_id, "verifier_attestation.verifier_id")
        _identifier(self.verifier_version, "verifier_attestation.verifier_version")
        _digest(
            self.verification_artifact_sha256,
            "verifier_attestation.verification_artifact_sha256",
        )
        _timestamp(self.verified_at, "verifier_attestation.verified_at")


class SignatureVerifier(Protocol):
    """External authority boundary for exact detached-signature verification."""

    def verify(
        self,
        *,
        subject: bytes,
        signature: bytes,
        signature_scheme: str,
        signer_id: str,
        key_id: str,
    ) -> VerifierAttestation:
        """Raise on failure and return an independently retained attestation."""


@dataclass(frozen=True)
class SignatureVerification:
    signature_scheme: str
    signer_id: str
    key_id: str
    subject_sha256: str
    signature_base64: str
    signature_sha256: str
    verifier_id: str
    verifier_version: str
    verification_artifact_sha256: str
    verified_at: str
    schema_version: str = SIGNATURE_VERIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SIGNATURE_VERIFICATION_SCHEMA_VERSION:
            raise ScientificLedgerError("unsupported signature-verification schema")
        for name in (
            "signature_scheme",
            "signer_id",
            "key_id",
            "verifier_id",
            "verifier_version",
        ):
            _identifier(getattr(self, name), f"signature_verification.{name}")
        _digest(self.subject_sha256, "signature_verification.subject_sha256")
        _digest(self.signature_sha256, "signature_verification.signature_sha256")
        _digest(
            self.verification_artifact_sha256,
            "signature_verification.verification_artifact_sha256",
        )
        _timestamp(self.verified_at, "signature_verification.verified_at")
        if not isinstance(self.signature_base64, str) or not self.signature_base64:
            raise ScientificLedgerError("signature_base64 must be non-empty")
        try:
            decoded = base64.b64decode(self.signature_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ScientificLedgerError("signature_base64 is invalid") from exc
        if not decoded or len(decoded) > _MAX_SIGNATURE_BYTES:
            raise ScientificLedgerError("detached signature size is invalid")
        if _sha256(decoded) != self.signature_sha256:
            raise ScientificLedgerError("signature bytes differ from signature_sha256")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "signature_scheme": self.signature_scheme,
            "signer_id": self.signer_id,
            "key_id": self.key_id,
            "subject_sha256": self.subject_sha256,
            "signature_base64": self.signature_base64,
            "signature_sha256": self.signature_sha256,
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "verification_artifact_sha256": self.verification_artifact_sha256,
            "verified_at": self.verified_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SignatureVerification:
        data = _object(value, "signature_verification")
        fields = {
            "schema_version",
            "signature_scheme",
            "signer_id",
            "key_id",
            "subject_sha256",
            "signature_base64",
            "signature_sha256",
            "verifier_id",
            "verifier_version",
            "verification_artifact_sha256",
            "verified_at",
        }
        _exact_fields(data, fields, "signature_verification")
        return cls(**{name: cast(str, data[name]) for name in fields})


def _verify_signature(
    subject: bytes,
    *,
    signature: bytes,
    signature_scheme: str,
    signer_id: str,
    key_id: str,
    verifier: SignatureVerifier,
) -> SignatureVerification:
    if not isinstance(subject, bytes) or not subject or len(subject) > _MAX_RECORD_BYTES:
        raise ScientificLedgerError("signature subject size is invalid")
    if not isinstance(signature, bytes) or not signature or len(signature) > _MAX_SIGNATURE_BYTES:
        raise ScientificLedgerError("detached signature size is invalid")
    scheme = _identifier(signature_scheme, "signature_scheme")
    signer = _identifier(signer_id, "signer_id")
    key = _identifier(key_id, "key_id")
    try:
        attestation = verifier.verify(
            subject=subject,
            signature=signature,
            signature_scheme=scheme,
            signer_id=signer,
            key_id=key,
        )
    except ScientificLedgerError:
        raise
    except Exception as exc:
        raise ScientificLedgerError("external signature verification failed") from exc
    if not isinstance(attestation, VerifierAttestation):
        raise ScientificLedgerError("signature verifier must return VerifierAttestation")
    return SignatureVerification(
        signature_scheme=scheme,
        signer_id=signer,
        key_id=key,
        subject_sha256=_sha256(subject),
        signature_base64=base64.b64encode(signature).decode("ascii"),
        signature_sha256=_sha256(signature),
        verifier_id=attestation.verifier_id,
        verifier_version=attestation.verifier_version,
        verification_artifact_sha256=attestation.verification_artifact_sha256,
        verified_at=attestation.verified_at,
    )


@dataclass(frozen=True)
class BootstrapReceipt:
    task_id: str
    candidate_id: str
    acquisition_id: str
    route: RouterRouteStep
    observation: EvidenceObservation
    producer_id: str
    producer_version: str
    artifact_sha256: str
    produced_at: str
    schema_version: str = BOOTSTRAP_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != BOOTSTRAP_RECEIPT_SCHEMA_VERSION:
            raise ScientificLedgerError("unsupported bootstrap-receipt schema")
        _identifier(self.task_id, "bootstrap.task_id")
        _candidate(self.candidate_id, "bootstrap.candidate_id")
        _identifier(self.acquisition_id, "bootstrap.acquisition_id")
        if not isinstance(self.route, RouterRouteStep):
            raise ScientificLedgerError("bootstrap route must be RouterRouteStep")
        if self.route.action != RouteAction.RUN_STATIC:
            raise ScientificLedgerError("bootstrap route must be deterministic static")
        if not isinstance(self.observation, EvidenceObservation):
            raise ScientificLedgerError("bootstrap observation is invalid")
        if (
            self.observation.kind != EvidenceKind.STATIC
            or self.observation.acquisition_id != self.acquisition_id
            or self.observation.privileged_inputs
            or self.observation.metadata
        ):
            raise ScientificLedgerError(
                "bootstrap observation must be stripped, non-privileged static evidence"
            )
        _identifier(self.producer_id, "bootstrap.producer_id")
        _identifier(self.producer_version, "bootstrap.producer_version")
        _digest(self.artifact_sha256, "bootstrap.artifact_sha256")
        _timestamp(self.produced_at, "bootstrap.produced_at")

    @property
    def event_time(self) -> str:
        return self.produced_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
            "acquisition_id": self.acquisition_id,
            "route": self.route.to_dict(),
            "observation": self.observation.to_dict(),
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "artifact_sha256": self.artifact_sha256,
            "produced_at": self.produced_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> BootstrapReceipt:
        data = _object(value, "bootstrap")
        fields = {
            "schema_version",
            "task_id",
            "candidate_id",
            "acquisition_id",
            "route",
            "observation",
            "producer_id",
            "producer_version",
            "artifact_sha256",
            "produced_at",
        }
        _exact_fields(data, fields, "bootstrap")
        try:
            observation = EvidenceObservation.from_dict(data["observation"])
        except ValueError as exc:
            raise ScientificLedgerError(f"invalid bootstrap observation: {exc}") from exc
        return cls(
            schema_version=cast(str, data["schema_version"]),
            task_id=cast(str, data["task_id"]),
            candidate_id=cast(str, data["candidate_id"]),
            acquisition_id=cast(str, data["acquisition_id"]),
            route=_route_from_dict(data["route"]),
            observation=observation,
            producer_id=cast(str, data["producer_id"]),
            producer_version=cast(str, data["producer_version"]),
            artifact_sha256=cast(str, data["artifact_sha256"]),
            produced_at=cast(str, data["produced_at"]),
        )

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict())

    @property
    def record_id(self) -> str:
        return _sha256(self.canonical_bytes)


@dataclass(frozen=True)
class CuratorReceipt:
    task_id: str
    candidate_id: str
    acquisition_id: str
    task_selection_sha256: str
    action_spec_sha256: str
    observation: EvidenceObservation
    artifact_sha256: str
    curator_protocol_sha256: str
    producer_id: str
    producer_version: str
    produced_at: str
    schema_version: str = CURATOR_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CURATOR_RECEIPT_SCHEMA_VERSION:
            raise ScientificLedgerError("unsupported curator-receipt schema")
        _identifier(self.task_id, "curator.task_id")
        _candidate(self.candidate_id, "curator.candidate_id")
        _identifier(self.acquisition_id, "curator.acquisition_id")
        _digest(self.task_selection_sha256, "curator.task_selection_sha256")
        _digest(self.action_spec_sha256, "curator.action_spec_sha256")
        if not isinstance(self.observation, EvidenceObservation):
            raise ScientificLedgerError("curator observation is invalid")
        if (
            self.observation.kind != EvidenceKind.ORACLE_HARDENING
            or self.observation.acquisition_id != self.acquisition_id
        ):
            raise ScientificLedgerError(
                "curator receipt requires matching oracle-hardening evidence"
            )
        _digest(self.artifact_sha256, "curator.artifact_sha256")
        _digest(self.curator_protocol_sha256, "curator.curator_protocol_sha256")
        _identifier(self.producer_id, "curator.producer_id")
        _identifier(self.producer_version, "curator.producer_version")
        _timestamp(self.produced_at, "curator.produced_at")

    @property
    def event_time(self) -> str:
        return self.produced_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
            "acquisition_id": self.acquisition_id,
            "task_selection_sha256": self.task_selection_sha256,
            "action_spec_sha256": self.action_spec_sha256,
            "observation": self.observation.to_dict(),
            "artifact_sha256": self.artifact_sha256,
            "curator_protocol_sha256": self.curator_protocol_sha256,
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "produced_at": self.produced_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CuratorReceipt:
        data = _object(value, "curator")
        fields = {
            "schema_version",
            "task_id",
            "candidate_id",
            "acquisition_id",
            "task_selection_sha256",
            "action_spec_sha256",
            "observation",
            "artifact_sha256",
            "curator_protocol_sha256",
            "producer_id",
            "producer_version",
            "produced_at",
        }
        _exact_fields(data, fields, "curator")
        try:
            observation = EvidenceObservation.from_dict(data["observation"])
        except ValueError as exc:
            raise ScientificLedgerError(f"invalid curator observation: {exc}") from exc
        return cls(
            schema_version=cast(str, data["schema_version"]),
            task_id=cast(str, data["task_id"]),
            candidate_id=cast(str, data["candidate_id"]),
            acquisition_id=cast(str, data["acquisition_id"]),
            task_selection_sha256=cast(str, data["task_selection_sha256"]),
            action_spec_sha256=cast(str, data["action_spec_sha256"]),
            observation=observation,
            artifact_sha256=cast(str, data["artifact_sha256"]),
            curator_protocol_sha256=cast(str, data["curator_protocol_sha256"]),
            producer_id=cast(str, data["producer_id"]),
            producer_version=cast(str, data["producer_version"]),
            produced_at=cast(str, data["produced_at"]),
        )

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict())

    @property
    def record_id(self) -> str:
        return _sha256(self.canonical_bytes)


@dataclass(frozen=True)
class ResourceReservation:
    reservation_id: str
    resource_key: str
    reservation_authority_id: str
    worker_count: int
    worker_ids: tuple[str, ...]
    task_id: str | None
    candidate_id: str | None
    acquisition_id: str | None
    reserved: ResourceUsage
    reserved_at: str
    schema_version: str = RESOURCE_RESERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESOURCE_RESERVATION_SCHEMA_VERSION:
            raise ScientificLedgerError("unsupported resource-reservation schema")
        _identifier(self.reservation_id, "resource_reservation.reservation_id")
        _identifier(self.resource_key, "resource_reservation.resource_key")
        _identifier(
            self.reservation_authority_id,
            "resource_reservation.reservation_authority_id",
        )
        _nonnegative_integer(self.worker_count, "resource_reservation.worker_count")
        if not isinstance(self.worker_ids, (list, tuple)):
            raise ScientificLedgerError("resource reservation worker_ids must be a sequence")
        workers = tuple(
            _identifier(item, f"resource_reservation.worker_ids[{index}]")
            for index, item in enumerate(self.worker_ids)
        )
        if len(workers) != self.worker_count:
            raise ScientificLedgerError("worker_count differs from worker_ids")
        if workers != tuple(sorted(workers)) or len(workers) != len(set(workers)):
            raise ScientificLedgerError("worker_ids must be sorted and unique")
        object.__setattr__(self, "worker_ids", workers)
        task = _optional_task(self.task_id, "resource_reservation.task_id")
        candidate = _optional_candidate(self.candidate_id, "resource_reservation.candidate_id")
        if candidate is not None and task is None:
            raise ScientificLedgerError("candidate-scoped reservation requires task_id")
        if self.acquisition_id is not None:
            _identifier(self.acquisition_id, "resource_reservation.acquisition_id")
        if not isinstance(self.reserved, ResourceUsage) or self.reserved.is_zero():
            raise ScientificLedgerError("resource reservation cannot be all zero")
        if self.worker_count == 0 and any(
            (
                self.reserved.process_launches,
                self.reserved.cpu_micros,
                self.reserved.worker_wall_micros,
                self.reserved.peak_rss_bytes,
            )
        ):
            raise ScientificLedgerError(
                "compute-bearing reservation requires at least one worker identity"
            )
        _timestamp(self.reserved_at, "resource_reservation.reserved_at")

    @property
    def event_time(self) -> str:
        return self.reserved_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reservation_id": self.reservation_id,
            "resource_key": self.resource_key,
            "reservation_authority_id": self.reservation_authority_id,
            "worker_count": self.worker_count,
            "worker_ids": list(self.worker_ids),
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
            "acquisition_id": self.acquisition_id,
            "reserved": self.reserved.to_dict(),
            "reserved_at": self.reserved_at,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceReservation:
        data = _object(value, "resource_reservation")
        fields = {
            "schema_version",
            "reservation_id",
            "resource_key",
            "reservation_authority_id",
            "worker_count",
            "worker_ids",
            "task_id",
            "candidate_id",
            "acquisition_id",
            "reserved",
            "reserved_at",
        }
        _exact_fields(data, fields, "resource_reservation")
        return cls(
            schema_version=cast(str, data["schema_version"]),
            reservation_id=cast(str, data["reservation_id"]),
            resource_key=cast(str, data["resource_key"]),
            reservation_authority_id=cast(str, data["reservation_authority_id"]),
            worker_count=cast(int, data["worker_count"]),
            worker_ids=tuple(
                cast(str, item)
                for item in _array(data["worker_ids"], "resource_reservation.worker_ids")
            ),
            task_id=cast(str | None, data["task_id"]),
            candidate_id=cast(str | None, data["candidate_id"]),
            acquisition_id=cast(str | None, data["acquisition_id"]),
            reserved=ResourceUsage.from_dict(data["reserved"]),
            reserved_at=cast(str, data["reserved_at"]),
        )

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict())

    @property
    def record_id(self) -> str:
        return _sha256(self.canonical_bytes)


@dataclass(frozen=True)
class ResourceSettlement:
    reservation_id: str
    reservation_record_sha256: str
    meter_authority_id: str
    actual: ResourceUsage
    outcome: ResourceOutcome
    usage_artifact_sha256: str
    settled_at: str
    task_id: str | None = None
    candidate_id: str | None = None
    schema_version: str = RESOURCE_SETTLEMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESOURCE_SETTLEMENT_SCHEMA_VERSION:
            raise ScientificLedgerError("unsupported resource-settlement schema")
        _identifier(self.reservation_id, "resource_settlement.reservation_id")
        _identifier(
            self.meter_authority_id,
            "resource_settlement.meter_authority_id",
        )
        _digest(
            self.reservation_record_sha256,
            "resource_settlement.reservation_record_sha256",
        )
        if not isinstance(self.actual, ResourceUsage):
            raise ScientificLedgerError("resource settlement actual usage is invalid")
        if not isinstance(self.outcome, ResourceOutcome):
            raise ScientificLedgerError("resource settlement outcome is invalid")
        _digest(self.usage_artifact_sha256, "resource_settlement.usage_artifact_sha256")
        _timestamp(self.settled_at, "resource_settlement.settled_at")
        task = _optional_task(self.task_id, "resource_settlement.task_id")
        candidate = _optional_candidate(self.candidate_id, "resource_settlement.candidate_id")
        if candidate is not None and task is None:
            raise ScientificLedgerError("candidate-scoped settlement requires task_id")

    @property
    def event_time(self) -> str:
        return self.settled_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reservation_id": self.reservation_id,
            "reservation_record_sha256": self.reservation_record_sha256,
            "meter_authority_id": self.meter_authority_id,
            "actual": self.actual.to_dict(),
            "outcome": self.outcome.value,
            "usage_artifact_sha256": self.usage_artifact_sha256,
            "settled_at": self.settled_at,
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ResourceSettlement:
        data = _object(value, "resource_settlement")
        fields = {
            "schema_version",
            "reservation_id",
            "reservation_record_sha256",
            "meter_authority_id",
            "actual",
            "outcome",
            "usage_artifact_sha256",
            "settled_at",
            "task_id",
            "candidate_id",
        }
        _exact_fields(data, fields, "resource_settlement")
        try:
            outcome = ResourceOutcome(data["outcome"])
        except (TypeError, ValueError) as exc:
            raise ScientificLedgerError("resource settlement outcome is invalid") from exc
        return cls(
            schema_version=cast(str, data["schema_version"]),
            reservation_id=cast(str, data["reservation_id"]),
            reservation_record_sha256=cast(str, data["reservation_record_sha256"]),
            meter_authority_id=cast(str, data["meter_authority_id"]),
            actual=ResourceUsage.from_dict(data["actual"]),
            outcome=outcome,
            usage_artifact_sha256=cast(str, data["usage_artifact_sha256"]),
            settled_at=cast(str, data["settled_at"]),
            task_id=cast(str | None, data["task_id"]),
            candidate_id=cast(str | None, data["candidate_id"]),
        )

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict())

    @property
    def record_id(self) -> str:
        return _sha256(self.canonical_bytes)


SignedSubject = BootstrapReceipt | CuratorReceipt | ResourceReservation | ResourceSettlement


def _record_kind(subject: SignedSubject) -> ScientificRecordKind:
    if isinstance(subject, BootstrapReceipt):
        return ScientificRecordKind.BOOTSTRAP
    if isinstance(subject, CuratorReceipt):
        return ScientificRecordKind.CURATOR
    if isinstance(subject, ResourceReservation):
        return ScientificRecordKind.RESOURCE_RESERVATION
    if isinstance(subject, ResourceSettlement):
        return ScientificRecordKind.RESOURCE_SETTLEMENT
    raise ScientificLedgerError("unsupported scientific record type")


def _subject_from_dict(kind: ScientificRecordKind, value: Any) -> SignedSubject:
    if kind == ScientificRecordKind.BOOTSTRAP:
        return BootstrapReceipt.from_dict(value)
    if kind == ScientificRecordKind.CURATOR:
        return CuratorReceipt.from_dict(value)
    if kind == ScientificRecordKind.RESOURCE_RESERVATION:
        return ResourceReservation.from_dict(value)
    if kind == ScientificRecordKind.RESOURCE_SETTLEMENT:
        return ResourceSettlement.from_dict(value)
    raise ScientificLedgerError("unknown scientific record kind")


def _signed_envelope(
    bindings: ScientificLedgerBindings,
    kind: ScientificRecordKind,
    subject: SignedSubject,
) -> dict[str, Any]:
    return {
        "schema_version": SIGNED_ENVELOPE_SCHEMA_VERSION,
        "study_id": bindings.study_id,
        "bindings_sha256": bindings.canonical_sha256,
        "kind": kind.value,
        "subject_record_id": subject.record_id,
        "subject": subject.to_dict(),
    }


def signed_envelope_bytes(
    bindings: ScientificLedgerBindings,
    subject: SignedSubject,
) -> bytes:
    """Return the exact domain-bound bytes an external authority must sign."""

    if not isinstance(bindings, ScientificLedgerBindings):
        raise TypeError("bindings must be ScientificLedgerBindings")
    return _canonical_bytes(_signed_envelope(bindings, _record_kind(subject), subject))


@dataclass(frozen=True)
class AppendReceipt:
    record_id: str
    record_sha256: str
    sequence: int
    inserted: bool


@dataclass(frozen=True)
class ScientificLedgerAudit:
    bindings_sha256: str
    record_count: int
    record_head_sha256: str
    bootstrap_receipt_count: int
    bootstrap_candidate_count: int
    curator_receipt_count: int
    resource_reservation_count: int
    resource_settlement_count: int
    active_reservation_count: int
    active_worker_count: int
    expected_task_count: int
    expected_candidate_count: int
    observed_task_count: int
    observed_candidate_count: int
    complete_bootstrap_candidate_coverage: bool
    committed_resource_usage: ResourceUsage

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCIENTIFIC_EXPORT_SCHEMA_VERSION,
            "bindings_sha256": self.bindings_sha256,
            "record_count": self.record_count,
            "record_head_sha256": self.record_head_sha256,
            "stored_external_verification_receipt_structure_validated": True,
            "detached_signatures_cryptographically_reverified_during_audit": False,
            "signed_envelopes_domain_bound": True,
            "signer_key_scheme_verifier_profiles_frozen": False,
            "resource_reservations_joined_to_acquisitions": False,
            "resource_overrun_or_deviation_records_supported": False,
            "bootstrap_manifest_frozen_and_recomputed": False,
            "external_checkpoint_present": False,
            "externally_immutable_storage_bound": False,
            "writer_reordering_detected_by_external_anchor": False,
            "prefix_truncation_detected_by_external_anchor": False,
            "activation_calendar_bound_and_checked": False,
            "human_adjudication_supported": False,
            "counts": {
                "bootstrap_receipts": self.bootstrap_receipt_count,
                "bootstrap_candidates": self.bootstrap_candidate_count,
                "curator_receipts": self.curator_receipt_count,
                "resource_reservations": self.resource_reservation_count,
                "resource_settlements": self.resource_settlement_count,
                "active_reservations": self.active_reservation_count,
                "active_workers": self.active_worker_count,
            },
            "partial_frame": {
                "expected_tasks": self.expected_task_count,
                "expected_candidates": self.expected_candidate_count,
                "observed_tasks": self.observed_task_count,
                "observed_candidates": self.observed_candidate_count,
                "complete_bootstrap_candidate_coverage": (
                    self.complete_bootstrap_candidate_coverage
                ),
                "bootstrap_precedes_behavior_round_zero_proven": False,
            },
            "committed_resource_usage": self.committed_resource_usage.to_dict(),
            "claim_boundary": (
                "durable typed non-policy records only; no activation, producer "
                "authentication, behavior-ledger chronology join, human "
                "adjudication, external chain anchoring, or scientific readiness claim"
            ),
        }


@dataclass
class _DerivedState:
    bootstraps: dict[str, BootstrapReceipt] = field(default_factory=dict)
    curator_acquisitions: dict[str, CuratorReceipt] = field(default_factory=dict)
    acquisitions: dict[str, tuple[str, str, str, ScientificRecordKind]] = field(
        default_factory=dict
    )
    reservations: dict[str, tuple[ResourceReservation, str]] = field(default_factory=dict)
    settlements: dict[str, ResourceSettlement] = field(default_factory=dict)
    observed_tasks: set[str] = field(default_factory=set)
    observed_candidates: set[str] = field(default_factory=set)

    def committed_usage(self) -> ResourceUsage:
        result = ResourceUsage()
        for reservation_id, (reservation, _) in self.reservations.items():
            settlement = self.settlements.get(reservation_id)
            result = result.plus(reservation.reserved if settlement is None else settlement.actual)
        return result

    @property
    def active_reservation_count(self) -> int:
        return len(set(self.reservations) - set(self.settlements))

    @property
    def active_worker_ids(self) -> set[str]:
        result: set[str] = set()
        for reservation_id, (reservation, _) in self.reservations.items():
            if reservation_id not in self.settlements:
                result.update(reservation.worker_ids)
        return result


def _assert_bound_subject(bindings: ScientificLedgerBindings, subject: SignedSubject) -> None:
    task_id = subject.task_id
    candidate_id = subject.candidate_id
    if task_id is not None:
        bindings.candidates_for(task_id)
    if candidate_id is not None:
        assert task_id is not None
        bindings.assert_candidate(task_id, candidate_id)


def _assert_signer_authorized(
    bindings: ScientificLedgerBindings,
    subject: SignedSubject,
    signer_id: str,
) -> None:
    signer = _identifier(signer_id, "signer_id")
    if isinstance(subject, BootstrapReceipt):
        allowed = bindings.bootstrap_signer_ids
        declared = subject.producer_id
        role = "bootstrap"
    elif isinstance(subject, CuratorReceipt):
        allowed = bindings.curator_signer_ids
        declared = subject.producer_id
        role = "curator"
    elif isinstance(subject, ResourceReservation):
        allowed = bindings.reservation_signer_ids
        declared = subject.reservation_authority_id
        role = "reservation"
    elif isinstance(subject, ResourceSettlement):
        allowed = bindings.meter_signer_ids
        declared = subject.meter_authority_id
        role = "meter"
    else:  # pragma: no cover - SignedSubject exhaustiveness.
        raise ScientificLedgerError("unsupported scientific signer role")
    if not allowed:
        raise ScientificLedgerError(f"{role} signer role has no frozen external authority binding")
    if signer != declared:
        raise ScientificLedgerError(
            f"{role} signer differs from the identity declared in the signed subject"
        )
    if signer not in allowed:
        raise ScientificLedgerError(f"{role} signer is outside the frozen role allowlist")


def _assert_usage_within_limits(
    usage: ResourceUsage,
    limits: ResourceLimits,
) -> None:
    if not usage.no_more_than(limits.maximum_usage):
        exceeded = [
            name
            for name in ResourceUsage.field_names()
            if getattr(usage, name) > getattr(limits.maximum_usage, name)
        ]
        raise ResourceCeilingExceeded(f"aggregate resource ceiling exceeded: {exceeded}")


def _apply_subject(
    state: _DerivedState,
    bindings: ScientificLedgerBindings,
    subject: SignedSubject,
    *,
    record_sha256: str,
) -> None:
    _assert_bound_subject(bindings, subject)
    if subject.task_id is not None:
        state.observed_tasks.add(subject.task_id)
    if subject.candidate_id is not None:
        state.observed_candidates.add(subject.candidate_id)
    if isinstance(subject, BootstrapReceipt):
        if subject.acquisition_id in state.acquisitions:
            raise ScientificLedgerConflict(
                "acquisition identity is already used by non-policy evidence"
            )
        if subject.candidate_id in state.bootstraps:
            raise ScientificLedgerConflict("a candidate already has an immutable bootstrap receipt")
        if len(state.bootstraps) >= (
            bindings.resource_limits.maximum_deterministic_static_acquisitions
        ):
            raise ResourceCeilingExceeded("deterministic static acquisition ceiling exceeded")
        state.bootstraps[subject.candidate_id] = subject
        state.acquisitions[subject.acquisition_id] = (
            subject.task_id,
            subject.candidate_id,
            subject.produced_at,
            ScientificRecordKind.BOOTSTRAP,
        )
        return
    if isinstance(subject, CuratorReceipt):
        if subject.acquisition_id in state.acquisitions:
            raise ScientificLedgerConflict(
                "acquisition identity is already used by non-policy evidence"
            )
        if len(state.curator_acquisitions) >= (
            bindings.resource_limits.maximum_curator_hardening_attempts
        ):
            raise ResourceCeilingExceeded("curator hardening ceiling exceeded")
        state.curator_acquisitions[subject.acquisition_id] = subject
        state.acquisitions[subject.acquisition_id] = (
            subject.task_id,
            subject.candidate_id,
            subject.produced_at,
            ScientificRecordKind.CURATOR,
        )
        return
    if isinstance(subject, ResourceReservation):
        if subject.reservation_id in state.reservations:
            raise ScientificLedgerConflict("resource reservation identity already exists")
        if any(
            reservation.resource_key == subject.resource_key
            for reservation, _ in state.reservations.values()
        ):
            raise ScientificLedgerConflict("exclusive resource_key was already reserved")
        active_workers = state.active_worker_ids
        overlapping_workers = active_workers.intersection(subject.worker_ids)
        if overlapping_workers:
            raise ScientificLedgerConflict(
                f"worker identities are already active: {sorted(overlapping_workers)}"
            )
        if (
            len(active_workers) + subject.worker_count
            > bindings.resource_limits.maximum_concurrent_workers
        ):
            raise ResourceCeilingExceeded("concurrent-worker ceiling exceeded")
        prospective = state.committed_usage().plus(subject.reserved)
        _assert_usage_within_limits(prospective, bindings.resource_limits)
        state.reservations[subject.reservation_id] = (subject, record_sha256)
        return
    if isinstance(subject, ResourceSettlement):
        bound = state.reservations.get(subject.reservation_id)
        if bound is None:
            raise ScientificLedgerError("resource settlement has no reservation")
        if subject.reservation_id in state.settlements:
            raise ScientificLedgerConflict("resource reservation is already settled")
        reservation, reservation_record_sha256 = bound
        if subject.reservation_record_sha256 != reservation_record_sha256:
            raise ScientificLedgerError(
                "resource settlement references the wrong reservation record"
            )
        if (
            subject.task_id != reservation.task_id
            or subject.candidate_id != reservation.candidate_id
        ):
            raise ScientificLedgerError("resource settlement scope differs from its reservation")
        if subject.settled_at < reservation.reserved_at:
            raise ScientificLedgerError("resource settlement predates its reservation")
        if not subject.actual.no_more_than(reservation.reserved):
            raise ResourceCeilingExceeded("resource settlement exceeds its committed reservation")
        state.settlements[subject.reservation_id] = subject
        _assert_usage_within_limits(state.committed_usage(), bindings.resource_limits)
        return
    raise ScientificLedgerError("unsupported scientific record")


def _record_preimage(
    *,
    sequence: int,
    kind: ScientificRecordKind,
    record_id: str,
    task_id: str | None,
    candidate_id: str | None,
    occurred_at: str,
    payload: Mapping[str, Any],
    verification: SignatureVerification,
    previous_record_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCIENTIFIC_RECORD_SCHEMA_VERSION,
        "sequence": sequence,
        "kind": kind.value,
        "record_id": record_id,
        "task_id": task_id,
        "candidate_id": candidate_id,
        "occurred_at": occurred_at,
        "payload": dict(payload),
        "signature_verification": verification.to_dict(),
        "previous_record_sha256": previous_record_sha256,
    }


def _validate_database_metadata(
    path: pathlib.Path,
    metadata: os.stat_result,
) -> None:
    if stat.S_ISLNK(metadata.st_mode):
        raise ScientificLedgerError("scientific ledger path cannot be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ScientificLedgerError("scientific ledger path must be a regular file")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ScientificLedgerError("scientific ledger file mode must be exactly 0600")
    if metadata.st_uid != os.geteuid():
        raise ScientificLedgerError("scientific ledger must be owned by the current user")
    if metadata.st_nlink != 1:
        raise ScientificLedgerError("scientific ledger cannot be hard-linked")


def _validate_database_file(path: pathlib.Path) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ScientificLedgerError("scientific ledger file does not exist") from exc
    _validate_database_metadata(path, metadata)
    return metadata


def _create_database_file(path: pathlib.Path) -> bool:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        _validate_database_file(path)
        return False
    try:
        os.fchmod(descriptor, 0o600)
        _validate_database_metadata(path, os.fstat(descriptor))
    finally:
        os.close(descriptor)
    return True


def _connect(path: pathlib.Path) -> sqlite3.Connection:
    before = _validate_database_file(path)
    try:
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=rw",
            timeout=30.0,
            uri=True,
        )
    except sqlite3.Error as exc:
        raise ScientificLedgerError("scientific ledger could not be opened read-write") from exc
    try:
        after = _validate_database_file(path)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ScientificLedgerError("scientific ledger file changed while it was opened")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection
    except BaseException:
        connection.close()
        raise


def _create_schema(connection: sqlite3.Connection) -> None:
    for statement in (
        _LEDGER_BINDINGS_TABLE_SQL,
        _SCIENTIFIC_RECORDS_TABLE_SQL,
        _SCIENTIFIC_RECORDS_NO_UPDATE_TRIGGER_SQL,
        _SCIENTIFIC_RECORDS_NO_DELETE_TRIGGER_SQL,
        _LEDGER_BINDINGS_NO_UPDATE_TRIGGER_SQL,
        _LEDGER_BINDINGS_NO_DELETE_TRIGGER_SQL,
    ):
        connection.execute(statement)


def _validate_schema(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE type IN ('table', 'index', 'trigger', 'view') "
        "AND name NOT GLOB 'sqlite_*'"
    ).fetchall()
    actual = {
        (cast(str, row["type"]), cast(str, row["name"])): (
            cast(str, row["tbl_name"]),
            cast(str, row["sql"]),
        )
        for row in rows
    }
    if actual != _SCHEMA_OBJECTS:
        missing = sorted(set(_SCHEMA_OBJECTS) - set(actual))
        unexpected = sorted(set(actual) - set(_SCHEMA_OBJECTS))
        changed = sorted(
            key
            for key in set(actual).intersection(_SCHEMA_OBJECTS)
            if actual[key] != _SCHEMA_OBJECTS[key]
        )
        raise ScientificLedgerError(
            "scientific ledger schema contract differs; "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )


class ScientificLedger:
    """Single-host append-only store for signed non-policy scientific records."""

    def __init__(
        self,
        path: pathlib.Path,
        *,
        bindings: ScientificLedgerBindings,
    ) -> None:
        if not isinstance(bindings, ScientificLedgerBindings):
            raise TypeError("bindings must be ScientificLedgerBindings")
        target = pathlib.Path(path).absolute()
        if not target.parent.is_dir():
            raise ScientificLedgerError("scientific ledger parent must exist")
        if target.parent.is_symlink() or target.is_symlink():
            raise ScientificLedgerError("scientific ledger path cannot use symlinks")
        self.path = target
        self.bindings = bindings
        existed = self.path.exists()
        if existed:
            _validate_database_file(self.path)
            created = False
        else:
            created = _create_database_file(self.path)
        self._initialize(created=created)

    def _initialize(self, *, created: bool) -> None:
        connection = _connect(self.path)
        try:
            if created:
                _create_schema(connection)
            _validate_schema(connection)
            connection.execute("PRAGMA journal_mode = WAL")
            binding_json = strict_json_dumps(self.bindings.to_dict())
            row = connection.execute(
                "SELECT binding_json, binding_sha256 FROM ledger_bindings WHERE singleton = 1"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO ledger_bindings(singleton, binding_json, binding_sha256) "
                    "VALUES (1, ?, ?)",
                    (binding_json, self.bindings.canonical_sha256),
                )
            elif (
                row["binding_json"] != binding_json
                or row["binding_sha256"] != self.bindings.canonical_sha256
            ):
                raise ScientificLedgerConflict(
                    "existing ledger uses different protocol/frame/resource bindings"
                )
            connection.commit()
        finally:
            connection.close()

    def _audit_connection(
        self, connection: sqlite3.Connection
    ) -> tuple[ScientificLedgerAudit, _DerivedState]:
        _validate_schema(connection)
        binding_row = connection.execute(
            "SELECT binding_json, binding_sha256 FROM ledger_bindings WHERE singleton = 1"
        ).fetchone()
        if binding_row is None:
            raise ScientificLedgerError("scientific ledger omits its bindings")
        try:
            binding_value = strict_json_loads(cast(str, binding_row["binding_json"]))
        except ValueError as exc:
            raise ScientificLedgerError("scientific ledger binding JSON is invalid") from exc
        restored_bindings = ScientificLedgerBindings.from_dict(binding_value)
        canonical_binding_json = strict_json_dumps(restored_bindings.to_dict())
        if (
            binding_row["binding_json"] != canonical_binding_json
            or binding_row["binding_sha256"] != restored_bindings.canonical_sha256
            or restored_bindings.to_dict() != self.bindings.to_dict()
        ):
            raise ScientificLedgerError("scientific ledger bindings were altered")
        rows = connection.execute("SELECT * FROM scientific_records ORDER BY sequence").fetchall()
        head = GENESIS_RECORD_SHA256
        state = _DerivedState()
        for expected_sequence, row in enumerate(rows, start=1):
            if row["sequence"] != expected_sequence:
                raise ScientificLedgerError("scientific record sequence is not contiguous")
            try:
                kind = ScientificRecordKind(row["kind"])
            except ValueError as exc:
                raise ScientificLedgerError("scientific record kind is invalid") from exc
            try:
                payload_value = strict_json_loads(cast(str, row["payload_json"]))
                verification_value = strict_json_loads(cast(str, row["verification_json"]))
                record_value = strict_json_loads(cast(str, row["record_json"]))
            except ValueError as exc:
                raise ScientificLedgerError("scientific record JSON is invalid") from exc
            subject = _subject_from_dict(kind, payload_value)
            verification = SignatureVerification.from_dict(verification_value)
            payload_json = strict_json_dumps(subject.to_dict())
            verification_json = strict_json_dumps(verification.to_dict())
            envelope_bytes = signed_envelope_bytes(self.bindings, subject)
            _assert_signer_authorized(
                self.bindings,
                subject,
                verification.signer_id,
            )
            if (
                row["payload_json"] != payload_json
                or row["verification_json"] != verification_json
                or verification.subject_sha256 != _sha256(envelope_bytes)
                or row["record_id"] != subject.record_id
                or row["task_id"] != subject.task_id
                or row["candidate_id"] != subject.candidate_id
                or row["occurred_at"] != subject.event_time
                or row["previous_record_sha256"] != head
                or verification.verified_at < subject.event_time
            ):
                raise ScientificLedgerError(
                    "scientific record columns, subject, or verification differ"
                )
            expected_preimage = _record_preimage(
                sequence=expected_sequence,
                kind=kind,
                record_id=subject.record_id,
                task_id=subject.task_id,
                candidate_id=subject.candidate_id,
                occurred_at=subject.event_time,
                payload=subject.to_dict(),
                verification=verification,
                previous_record_sha256=head,
            )
            expected_json = strict_json_dumps(expected_preimage)
            expected_sha = _sha256(expected_json.encode("utf-8"))
            if (
                row["record_json"] != expected_json
                or record_value != expected_preimage
                or row["record_sha256"] != expected_sha
            ):
                raise ScientificLedgerError("scientific record hash chain was altered")
            _apply_subject(
                state,
                self.bindings,
                subject,
                record_sha256=expected_sha,
            )
            head = expected_sha
        committed = state.committed_usage()
        _assert_usage_within_limits(committed, self.bindings.resource_limits)
        audit = ScientificLedgerAudit(
            bindings_sha256=self.bindings.canonical_sha256,
            record_count=len(rows),
            record_head_sha256=head,
            bootstrap_receipt_count=len(state.bootstraps),
            bootstrap_candidate_count=len(state.bootstraps),
            curator_receipt_count=len(state.curator_acquisitions),
            resource_reservation_count=len(state.reservations),
            resource_settlement_count=len(state.settlements),
            active_reservation_count=state.active_reservation_count,
            active_worker_count=len(state.active_worker_ids),
            expected_task_count=self.bindings.task_count,
            expected_candidate_count=self.bindings.candidate_count,
            observed_task_count=len(state.observed_tasks),
            observed_candidate_count=len(state.observed_candidates),
            complete_bootstrap_candidate_coverage=(
                len(state.bootstraps) == self.bindings.candidate_count
            ),
            committed_resource_usage=committed,
        )
        return audit, state

    def audit(self) -> ScientificLedgerAudit:
        connection = _connect(self.path)
        try:
            return self._audit_connection(connection)[0]
        finally:
            connection.close()

    def append_signed(
        self,
        subject: SignedSubject,
        *,
        signature: bytes,
        signature_scheme: str,
        signer_id: str,
        key_id: str,
        verifier: SignatureVerifier,
    ) -> AppendReceipt:
        if not isinstance(
            subject,
            (
                BootstrapReceipt,
                CuratorReceipt,
                ResourceReservation,
                ResourceSettlement,
            ),
        ):
            raise TypeError("subject must be a typed scientific-ledger record")
        kind = _record_kind(subject)
        _assert_signer_authorized(self.bindings, subject, signer_id)
        envelope_bytes = signed_envelope_bytes(self.bindings, subject)
        if (
            not isinstance(signature, bytes)
            or not signature
            or len(signature) > _MAX_SIGNATURE_BYTES
        ):
            raise ScientificLedgerError("detached signature size is invalid")
        scheme = _identifier(signature_scheme, "signature_scheme")
        signer = _identifier(signer_id, "signer_id")
        key = _identifier(key_id, "key_id")
        retry_identity = (
            scheme,
            signer,
            key,
            _sha256(envelope_bytes),
            base64.b64encode(signature).decode("ascii"),
            _sha256(signature),
        )
        payload_json = strict_json_dumps(subject.to_dict())

        # A durable exact record is already success after acknowledgement loss.
        # Requiring the external verifier again would make recovery depend on
        # verifier availability and on a byte-identical fresh timestamp/receipt.
        recovery = _connect(self.path)
        try:
            recovery.execute("BEGIN")
            self._audit_connection(recovery)
            existing = recovery.execute(
                "SELECT sequence, payload_json, verification_json, record_sha256 "
                "FROM scientific_records WHERE record_id = ?",
                (subject.record_id,),
            ).fetchone()
            if existing is not None:
                existing_verification = SignatureVerification.from_dict(
                    strict_json_loads(cast(str, existing["verification_json"]))
                )
                existing_identity = (
                    existing_verification.signature_scheme,
                    existing_verification.signer_id,
                    existing_verification.key_id,
                    existing_verification.subject_sha256,
                    existing_verification.signature_base64,
                    existing_verification.signature_sha256,
                )
                if existing["payload_json"] != payload_json or existing_identity != retry_identity:
                    raise ScientificLedgerConflict(
                        "signed record retry differs from immutable content"
                    )
                recovery.rollback()
                return AppendReceipt(
                    record_id=subject.record_id,
                    record_sha256=cast(str, existing["record_sha256"]),
                    sequence=cast(int, existing["sequence"]),
                    inserted=False,
                )
            recovery.rollback()
        finally:
            if recovery.in_transaction:
                recovery.rollback()
            recovery.close()

        verification = _verify_signature(
            envelope_bytes,
            signature=signature,
            signature_scheme=scheme,
            signer_id=signer,
            key_id=key,
            verifier=verifier,
        )
        if verification.verified_at < subject.event_time:
            raise ScientificLedgerError("signature verification predates the signed event")
        connection = _connect(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            audit, state = self._audit_connection(connection)
            existing = connection.execute(
                "SELECT sequence, payload_json, verification_json, record_sha256 "
                "FROM scientific_records WHERE record_id = ?",
                (subject.record_id,),
            ).fetchone()
            verification_json = strict_json_dumps(verification.to_dict())
            if existing is not None:
                try:
                    existing_verification = SignatureVerification.from_dict(
                        strict_json_loads(cast(str, existing["verification_json"]))
                    )
                except ValueError as exc:  # pragma: no cover - audited above.
                    raise ScientificLedgerError(
                        "existing signature verification is invalid"
                    ) from exc
                existing_identity = (
                    existing_verification.signature_scheme,
                    existing_verification.signer_id,
                    existing_verification.key_id,
                    existing_verification.subject_sha256,
                    existing_verification.signature_base64,
                    existing_verification.signature_sha256,
                )
                if existing["payload_json"] != payload_json or existing_identity != retry_identity:
                    raise ScientificLedgerConflict(
                        "signed record retry differs from immutable content"
                    )
                connection.rollback()
                return AppendReceipt(
                    record_id=subject.record_id,
                    record_sha256=cast(str, existing["record_sha256"]),
                    sequence=cast(int, existing["sequence"]),
                    inserted=False,
                )
            sequence = audit.record_count + 1
            preimage = _record_preimage(
                sequence=sequence,
                kind=kind,
                record_id=subject.record_id,
                task_id=subject.task_id,
                candidate_id=subject.candidate_id,
                occurred_at=subject.event_time,
                payload=subject.to_dict(),
                verification=verification,
                previous_record_sha256=audit.record_head_sha256,
            )
            record_json = strict_json_dumps(preimage)
            if len(record_json.encode("utf-8")) > _MAX_RECORD_BYTES:
                raise ScientificLedgerError("scientific record exceeds byte ceiling")
            record_sha256 = _sha256(record_json.encode("utf-8"))
            _apply_subject(
                state,
                self.bindings,
                subject,
                record_sha256=record_sha256,
            )
            connection.execute(
                """
                INSERT INTO scientific_records(
                    sequence, kind, record_id, task_id, candidate_id, occurred_at,
                    payload_json, verification_json, previous_record_sha256,
                    record_json, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sequence,
                    kind.value,
                    subject.record_id,
                    subject.task_id,
                    subject.candidate_id,
                    subject.event_time,
                    payload_json,
                    verification_json,
                    audit.record_head_sha256,
                    record_json,
                    record_sha256,
                ),
            )
            connection.commit()
            return AppendReceipt(
                record_id=subject.record_id,
                record_sha256=record_sha256,
                sequence=sequence,
                inserted=True,
            )
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def export_bytes(self) -> bytes:
        connection = _connect(self.path)
        try:
            connection.execute("BEGIN")
            audit, _ = self._audit_connection(connection)
            rows = connection.execute(
                "SELECT record_json FROM scientific_records ORDER BY sequence"
            ).fetchall()
            header = {
                "schema_version": SCIENTIFIC_EXPORT_SCHEMA_VERSION,
                "kind": "scientific_ledger_export_header",
                "bindings": self.bindings.to_dict(),
                "bindings_sha256": self.bindings.canonical_sha256,
                "record_count": audit.record_count,
                "record_head_sha256": audit.record_head_sha256,
                "audit": audit.to_dict(),
            }
            lines = [strict_json_dumps(header)]
            lines.extend(cast(str, row["record_json"]) for row in rows)
            return ("\n".join(lines) + "\n").encode("utf-8")
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()

    def write_export(self, output_path: pathlib.Path) -> tuple[int, str]:
        payload = self.export_bytes()
        target = pathlib.Path(output_path).absolute()
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise ScientificLedgerError("export parent must be a real directory")
        descriptor: int | None = None
        try:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                descriptor = None
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise ScientificLedgerConflict(
                "scientific ledger export is immutable and will not be overwritten"
            ) from exc
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            target.unlink(missing_ok=True)
            raise
        return len(payload), _sha256(payload)
