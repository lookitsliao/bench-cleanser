"""Externally anchored structural StudyBundle compiler for the prospective pilot.

The prospective scheduler ledger is self-authenticating only against accidental
or local corruption: an attacker can always rewrite a ledger and recompute its
hash chains.  This module therefore requires a *separately pinned* trust-anchor
digest before it will expose an :class:`AuditedLedgerSnapshot`.  The expected
anchor digest is deliberately never inferred from the files being loaded.

The current compiler emits a structural bundle.  It derives policy decisions,
terminal actions, task selections, acquisition outcomes, and cost declarations
from the audited ledger rather than accepting those fields from an evaluation
caller.  Independent task/candidate truth and event-quality adjudication are
not yet represented by the current corpus schema, so the compiler always keeps
the scientific profiles closed.  This is an intentional fail-closed bridge to
the incompatible oracle/corpus schema revision, not a scientific-result
generator.
"""

from __future__ import annotations

import base64
import hashlib
import math
import os
import pathlib
import re
import stat
import tempfile
import urllib.parse
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from bench_cleanser.verification._io import (
    strict_json_dumps,
    strict_json_loads,
)
from bench_cleanser.verification.models import EvidenceKind, EvidenceObservation
from bench_cleanser.verification.policy_log import LoggedPolicyDecision
from experiments.prospective_pilot.ledger import (
    PROTOCOL_RESULT_VALIDATION_CONTRACT,
    ExecutableActionSpec,
    ExportAudit,
    ReservationRequest,
    audit_jsonl_export,
)
from experiments.prospective_pilot.scheduler import (
    SCHEDULER_STUDY_ID,
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    load_study_bindings,
)

TRUST_ANCHOR_SCHEMA_VERSION = "prospective-ledger-trust-anchor-0.1.0"
STRUCTURAL_BUNDLE_SCHEMA_VERSION = "verification-gap-study-bundle-0.2.0"
TRUST_MODEL = "out_of_band_sha256_v1"
TRAJECTORY_DIGEST_CONTRACT = "verification-gap-candidate-trajectory-v2"
TASK_TRAJECTORY_DIGEST_CONTRACT = "verification-gap-task-trajectory-v2"
BUNDLE_DIGEST_CONTRACT = "verification-gap-structural-study-bundle-v2"

_MAX_LEDGER_EXPORT_BYTES = 512 * 1024 * 1024
_MAX_TRUST_ANCHOR_BYTES = 256 * 1024
_MAX_BOUND_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
_MAX_ACQUISITION_ARTIFACT_BYTES = 512 * 1024 * 1024
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_TABLE_ORDER = (
    "ledger_meta",
    "action_specs",
    "rounds",
    "policy_decisions",
    "dispatch_intents",
    "resource_reservations",
    "claims",
    "results",
    "incidents",
    "selections",
    "events",
)
_BINDING_KEYS = (
    "candidate_ids_sha256",
    "collection_policy_sha256",
    "frame_manifest_sha256",
    "protocol_sha256",
    "router_policy_config_sha256",
    "router_source_sha256",
    "scheduler_contract_sha256",
    "source_feature_freeze_sha256",
    "task_ids_sha256",
)
_SCIENTIFIC_INPUT_NAMES = (
    "candidate_registry",
    "bootstrap_stream",
    "curator_stream",
    "adjudications",
    "resource_receipts",
    "run_manifest",
    "score_receipts",
)
_EXECUTION_KINDS = {
    EvidenceKind.TARGETED_EXECUTION,
    EvidenceKind.FULL_EXECUTION,
}


class ReleaseBundleError(ValueError):
    """The trust boundary or structural release projection is invalid."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256(strict_json_dumps(value).encode("utf-8"))


def _digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ReleaseBundleError(f"{field_name} must be 64 lowercase hexadecimal characters")
    return value


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ReleaseBundleError(f"{field_name} must be a safe identifier")
    return value


def _nonnegative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReleaseBundleError(f"{field_name} must be a non-negative integer")
    return value


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ReleaseBundleError(f"{field_name} must be a boolean")
    return value


def _exact_object(
    value: Any,
    fields: set[str],
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReleaseBundleError(f"{field_name} must be a JSON object")
    result = cast(dict[str, Any], value)
    if set(result) != fields:
        missing = sorted(fields - set(result))
        extra = sorted(set(result) - fields)
        raise ReleaseBundleError(f"{field_name} fields differ; missing={missing}, extra={extra}")
    return result


def _read_regular_file(path: pathlib.Path, *, maximum_bytes: int) -> bytes:
    """Read one stable regular file while rejecting a symlink leaf."""

    source = pathlib.Path(path).absolute()
    try:
        before = source.lstat()
    except OSError as exc:
        raise ReleaseBundleError(f"cannot stat release input {source}: {exc}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise ReleaseBundleError(f"release input must be a regular non-symlink file: {source}")
    if before.st_size > maximum_bytes:
        raise ReleaseBundleError(f"release input exceeds its byte ceiling: {source}")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise ReleaseBundleError(f"cannot open release input {source}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            raise ReleaseBundleError(f"release input changed while opening: {source}")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            after.st_dev != opened.st_dev
            or after.st_ino != opened.st_ino
            or after.st_size != opened.st_size
            or len(payload) != opened.st_size
        ):
            raise ReleaseBundleError(f"release input changed while reading: {source}")
        if len(payload) > maximum_bytes:
            raise ReleaseBundleError(f"release input exceeds its byte ceiling: {source}")
        return payload
    finally:
        os.close(descriptor)


def _binding_payload(bindings: SchedulerBindings) -> dict[str, str]:
    task_ids = list(bindings.frame.task_ids)
    candidate_ids = sorted(
        candidate_id
        for task_id in bindings.frame.task_ids
        for candidate_id in bindings.frame.candidate_ids_for(task_id)
    )
    return {
        "candidate_ids_sha256": _canonical_sha256(candidate_ids),
        "collection_policy_sha256": bindings.collection_policy_sha256,
        "frame_manifest_sha256": bindings.frame.manifest_sha256,
        "protocol_sha256": bindings.protocol_sha256,
        "router_policy_config_sha256": bindings.router_policy_config_sha256,
        "router_source_sha256": bindings.router_source_sha256,
        "scheduler_contract_sha256": bindings.scheduler_contract_sha256,
        "source_feature_freeze_sha256": (bindings.frame.source_feature_freeze_sha256),
        "task_ids_sha256": _canonical_sha256(task_ids),
    }


def _fresh_bindings(bindings: SchedulerBindings) -> SchedulerBindings:
    if not isinstance(bindings, SchedulerBindings):
        raise ReleaseBundleError("release loading requires SchedulerBindings")
    try:
        fresh = load_study_bindings(bindings.repository_root)
    except (OSError, ValueError) as exc:
        raise ReleaseBundleError(f"cannot refresh repository bindings: {exc}") from exc
    if _binding_payload(fresh) != _binding_payload(bindings):
        raise ReleaseBundleError("scheduler bindings changed after they were loaded")
    return fresh


@dataclass(frozen=True)
class LedgerExportTrustAnchor:
    """A ledger identity intended to be pinned outside the ledger directory.

    ``attestor_id`` is descriptive provenance, not a cryptographic signature.
    Authenticity comes from the independently supplied SHA-256 of the exact
    canonical anchor bytes.
    """

    artifact_id: str
    attestor_id: str
    ledger_export_sha256: str
    export_head_sha256: str
    event_head_sha256: str
    record_count: int
    table_counts: tuple[tuple[str, int], ...]
    complete: bool
    analysis_ready: bool
    binding_items: tuple[tuple[str, str], ...]
    schema_version: str = TRUST_ANCHOR_SCHEMA_VERSION
    study_id: str = SCHEDULER_STUDY_ID
    trust_model: str = TRUST_MODEL

    def __post_init__(self) -> None:
        if self.schema_version != TRUST_ANCHOR_SCHEMA_VERSION:
            raise ReleaseBundleError("unsupported ledger trust-anchor schema")
        if self.study_id != SCHEDULER_STUDY_ID:
            raise ReleaseBundleError("ledger trust anchor uses a different study_id")
        if self.trust_model != TRUST_MODEL:
            raise ReleaseBundleError("ledger trust anchor uses an unsupported trust model")
        _identifier(self.artifact_id, "trust_anchor.artifact_id")
        _identifier(self.attestor_id, "trust_anchor.attestor_id")
        for name in (
            "ledger_export_sha256",
            "export_head_sha256",
            "event_head_sha256",
        ):
            _digest(getattr(self, name), f"trust_anchor.{name}")
        _nonnegative_integer(self.record_count, "trust_anchor.record_count")
        if not isinstance(self.table_counts, (list, tuple)):
            raise ReleaseBundleError("trust_anchor.table_counts must be a sequence")
        table_counts = tuple(self.table_counts)
        if tuple(name for name, _ in table_counts) != _TABLE_ORDER:
            raise ReleaseBundleError("trust-anchor table order differs from ledger schema")
        for name, count in table_counts:
            _nonnegative_integer(count, f"trust_anchor.table_counts[{name}]")
        if sum(count for _, count in table_counts) != self.record_count:
            raise ReleaseBundleError("trust-anchor table counts do not sum to record_count")
        object.__setattr__(self, "table_counts", table_counts)
        _boolean(self.complete, "trust_anchor.complete")
        _boolean(self.analysis_ready, "trust_anchor.analysis_ready")
        if self.analysis_ready and not self.complete:
            raise ReleaseBundleError("analysis-ready anchor cannot be incomplete")
        if not isinstance(self.binding_items, (list, tuple)):
            raise ReleaseBundleError("trust_anchor.bindings must be a sequence")
        bindings = tuple(self.binding_items)
        if tuple(name for name, _ in bindings) != _BINDING_KEYS:
            raise ReleaseBundleError("trust-anchor binding set or order differs")
        for name, digest in bindings:
            _digest(digest, f"trust_anchor.bindings.{name}")
        object.__setattr__(self, "binding_items", bindings)

    @property
    def bindings(self) -> dict[str, str]:
        return dict(self.binding_items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "trust_model": self.trust_model,
            "artifact_id": self.artifact_id,
            "attestor_id": self.attestor_id,
            "ledger_export_sha256": self.ledger_export_sha256,
            "export_head_sha256": self.export_head_sha256,
            "event_head_sha256": self.event_head_sha256,
            "record_count": self.record_count,
            "table_counts": {name: count for name, count in self.table_counts},
            "complete": self.complete,
            "analysis_ready": self.analysis_ready,
            "bindings": self.bindings,
        }

    def canonical_bytes(self) -> bytes:
        return (strict_json_dumps(self.to_dict()) + "\n").encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> LedgerExportTrustAnchor:
        try:
            text = payload.decode("utf-8")
            decoded = strict_json_loads(text)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ReleaseBundleError(f"invalid ledger trust-anchor JSON: {exc}") from exc
        data = _exact_object(
            decoded,
            {
                "schema_version",
                "study_id",
                "trust_model",
                "artifact_id",
                "attestor_id",
                "ledger_export_sha256",
                "export_head_sha256",
                "event_head_sha256",
                "record_count",
                "table_counts",
                "complete",
                "analysis_ready",
                "bindings",
            },
            "trust_anchor",
        )
        raw_counts = _exact_object(
            data["table_counts"], set(_TABLE_ORDER), "trust_anchor.table_counts"
        )
        raw_bindings = _exact_object(data["bindings"], set(_BINDING_KEYS), "trust_anchor.bindings")
        result = cls(
            schema_version=cast(str, data["schema_version"]),
            study_id=cast(str, data["study_id"]),
            trust_model=cast(str, data["trust_model"]),
            artifact_id=cast(str, data["artifact_id"]),
            attestor_id=cast(str, data["attestor_id"]),
            ledger_export_sha256=cast(str, data["ledger_export_sha256"]),
            export_head_sha256=cast(str, data["export_head_sha256"]),
            event_head_sha256=cast(str, data["event_head_sha256"]),
            record_count=_nonnegative_integer(data["record_count"], "trust_anchor.record_count"),
            table_counts=tuple(
                (name, _nonnegative_integer(raw_counts[name], f"trust_anchor.table_counts.{name}"))
                for name in _TABLE_ORDER
            ),
            complete=_boolean(data["complete"], "trust_anchor.complete"),
            analysis_ready=_boolean(data["analysis_ready"], "trust_anchor.analysis_ready"),
            binding_items=tuple(
                (name, _digest(raw_bindings[name], f"trust_anchor.bindings.{name}"))
                for name in _BINDING_KEYS
            ),
        )
        if result.canonical_bytes() != payload:
            raise ReleaseBundleError("ledger trust anchor is not canonical JSONL")
        return result


def _anchor_from_audit(
    *,
    artifact_id: str,
    attestor_id: str,
    export_sha256: str,
    audit: ExportAudit,
    bindings: SchedulerBindings,
) -> LedgerExportTrustAnchor:
    return LedgerExportTrustAnchor(
        artifact_id=artifact_id,
        attestor_id=attestor_id,
        ledger_export_sha256=export_sha256,
        export_head_sha256=audit.export_head_sha256,
        event_head_sha256=audit.event_head_sha256,
        record_count=audit.record_count,
        table_counts=audit.table_counts,
        complete=audit.complete,
        analysis_ready=audit.analysis_ready,
        binding_items=tuple(sorted(_binding_payload(bindings).items())),
    )


def build_ledger_export_trust_anchor(
    ledger_export_path: pathlib.Path,
    *,
    bindings: SchedulerBindings,
    artifact_id: str,
    attestor_id: str,
    require_complete: bool = False,
) -> tuple[bytes, str]:
    """Audit an export and render the anchor bytes that must be published/pinned.

    Returning an anchor does not authenticate it.  A release process must publish
    the returned digest through an independent channel (for example a signed
    release manifest or DOI record), and consumers must pass that pinned digest
    to :func:`load_audited_export`.
    """

    fresh = _fresh_bindings(bindings)
    payload = _read_regular_file(ledger_export_path, maximum_bytes=_MAX_LEDGER_EXPORT_BYTES)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseBundleError("ledger export is not UTF-8") from exc
    try:
        audit = audit_jsonl_export(
            text,
            bindings=fresh,
            require_complete=require_complete,
        )
    except ValueError as exc:
        raise ReleaseBundleError(f"ledger export audit failed: {exc}") from exc
    anchor = _anchor_from_audit(
        artifact_id=artifact_id,
        attestor_id=attestor_id,
        export_sha256=_sha256(payload),
        audit=audit,
        bindings=fresh,
    )
    rendered = anchor.canonical_bytes()
    return rendered, _sha256(rendered)


def _record_json_by_table(export_text: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    result: dict[str, list[str]] = {table: [] for table in _TABLE_ORDER}
    for line_number, raw_line in enumerate(export_text.splitlines(), start=1):
        try:
            value = strict_json_loads(raw_line)
        except ValueError as exc:  # pragma: no cover - audited immediately before
            raise ReleaseBundleError(f"invalid audited export line {line_number}: {exc}") from exc
        if not isinstance(value, dict):  # pragma: no cover - enforced by ledger audit
            raise ReleaseBundleError("audited export line is not an object")
        table = value.get("table")
        record = value.get("record")
        if table not in result or not isinstance(record, dict):
            raise ReleaseBundleError("audited export line lost its table/record")
        result[cast(str, table)].append(strict_json_dumps(record))
    return tuple((table, tuple(result[table])) for table in _TABLE_ORDER)


@dataclass(frozen=True)
class AuditedLedgerSnapshot:
    """A repository-bound ledger export whose anchor digest is out-of-band pinned."""

    ledger_export_path: pathlib.Path
    trust_anchor_path: pathlib.Path
    expected_trust_anchor_sha256: str
    bindings: SchedulerBindings
    require_complete: bool = False
    audit: ExportAudit = field(init=False)
    trust_anchor: LedgerExportTrustAnchor = field(init=False)
    ledger_export_sha256: str = field(init=False)
    trust_anchor_sha256: str = field(init=False)
    _record_json: tuple[tuple[str, tuple[str, ...]], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        expected = _digest(
            self.expected_trust_anchor_sha256,
            "expected_trust_anchor_sha256",
        )
        fresh = _fresh_bindings(self.bindings)
        export_path = pathlib.Path(self.ledger_export_path).absolute()
        anchor_path = pathlib.Path(self.trust_anchor_path).absolute()
        export_bytes = _read_regular_file(export_path, maximum_bytes=_MAX_LEDGER_EXPORT_BYTES)
        anchor_bytes = _read_regular_file(anchor_path, maximum_bytes=_MAX_TRUST_ANCHOR_BYTES)
        anchor_digest = _sha256(anchor_bytes)
        if anchor_digest != expected:
            raise ReleaseBundleError(
                "trust-anchor bytes do not match the independently pinned digest"
            )
        anchor = LedgerExportTrustAnchor.from_bytes(anchor_bytes)
        export_digest = _sha256(export_bytes)
        if export_digest != anchor.ledger_export_sha256:
            raise ReleaseBundleError("ledger export differs from its pinned trust anchor")
        if anchor.bindings != _binding_payload(fresh):
            raise ReleaseBundleError("ledger trust anchor differs from repository bindings")
        try:
            export_text = export_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReleaseBundleError("ledger export is not UTF-8") from exc
        try:
            audit = audit_jsonl_export(
                export_text,
                bindings=fresh,
                require_complete=self.require_complete,
            )
        except ValueError as exc:
            raise ReleaseBundleError(f"ledger export audit failed: {exc}") from exc
        audit_identity = {
            "export_head_sha256": audit.export_head_sha256,
            "event_head_sha256": audit.event_head_sha256,
            "record_count": audit.record_count,
            "table_counts": audit.table_counts,
            "complete": audit.complete,
            "analysis_ready": audit.analysis_ready,
        }
        anchor_identity = {
            "export_head_sha256": anchor.export_head_sha256,
            "event_head_sha256": anchor.event_head_sha256,
            "record_count": anchor.record_count,
            "table_counts": anchor.table_counts,
            "complete": anchor.complete,
            "analysis_ready": anchor.analysis_ready,
        }
        if audit_identity != anchor_identity:
            raise ReleaseBundleError("ledger audit result differs from its trust anchor")
        object.__setattr__(self, "ledger_export_path", export_path)
        object.__setattr__(self, "trust_anchor_path", anchor_path)
        object.__setattr__(self, "expected_trust_anchor_sha256", expected)
        object.__setattr__(self, "bindings", fresh)
        object.__setattr__(self, "audit", audit)
        object.__setattr__(self, "trust_anchor", anchor)
        object.__setattr__(self, "ledger_export_sha256", export_digest)
        object.__setattr__(self, "trust_anchor_sha256", anchor_digest)
        object.__setattr__(self, "_record_json", _record_json_by_table(export_text))

    def records(self, table: str) -> tuple[dict[str, Any], ...]:
        if table not in _TABLE_ORDER:
            raise ReleaseBundleError(f"unknown ledger table {table!r}")
        encoded = dict(self._record_json)[table]
        return tuple(cast(dict[str, Any], strict_json_loads(item)) for item in encoded)

    def revalidate(self) -> AuditedLedgerSnapshot:
        """Reopen every source byte before a downstream compilation."""

        return AuditedLedgerSnapshot(
            ledger_export_path=self.ledger_export_path,
            trust_anchor_path=self.trust_anchor_path,
            expected_trust_anchor_sha256=self.expected_trust_anchor_sha256,
            bindings=self.bindings,
            require_complete=self.require_complete,
        )


def load_audited_export(
    ledger_export_path: pathlib.Path,
    trust_anchor_path: pathlib.Path,
    *,
    expected_trust_anchor_sha256: str,
    bindings: SchedulerBindings,
    require_complete: bool = False,
) -> AuditedLedgerSnapshot:
    """Load a ledger only after external digest pinning and semantic re-audit."""

    return AuditedLedgerSnapshot(
        ledger_export_path=ledger_export_path,
        trust_anchor_path=trust_anchor_path,
        expected_trust_anchor_sha256=expected_trust_anchor_sha256,
        bindings=bindings,
        require_complete=require_complete,
    )


@dataclass(frozen=True)
class BoundReleaseArtifact:
    """One additional release input whose bytes are pinned out of band."""

    logical_name: str
    path: pathlib.Path
    expected_sha256: str
    media_type: str = "application/json"
    byte_count: int = field(init=False)

    def __post_init__(self) -> None:
        _identifier(self.logical_name, "bound_artifact.logical_name")
        expected = _digest(self.expected_sha256, "bound_artifact.expected_sha256")
        if not isinstance(self.media_type, str) or not self.media_type.strip():
            raise ReleaseBundleError("bound artifact media_type must be non-empty")
        source = pathlib.Path(self.path).absolute()
        payload = _read_regular_file(source, maximum_bytes=_MAX_BOUND_ARTIFACT_BYTES)
        if _sha256(payload) != expected:
            raise ReleaseBundleError(
                f"bound artifact {self.logical_name!r} differs from its pinned digest"
            )
        object.__setattr__(self, "path", source)
        object.__setattr__(self, "expected_sha256", expected)
        object.__setattr__(self, "byte_count", len(payload))

    def revalidate(self) -> BoundReleaseArtifact:
        return BoundReleaseArtifact(
            logical_name=self.logical_name,
            path=self.path,
            expected_sha256=self.expected_sha256,
            media_type=self.media_type,
        )

    def binding(self) -> dict[str, Any]:
        return {
            "logical_name": self.logical_name,
            "sha256": self.expected_sha256,
            "bytes": self.byte_count,
            "media_type": self.media_type,
        }


@dataclass(frozen=True)
class ProspectiveReleaseBundle:
    """Canonical structural StudyBundle with a digest over every projection."""

    _payload_json: str = field(repr=False)
    bundle_sha256: str

    def __post_init__(self) -> None:
        digest = _digest(self.bundle_sha256, "bundle_sha256")
        try:
            payload = strict_json_loads(self._payload_json)
        except ValueError as exc:
            raise ReleaseBundleError(f"invalid bundle payload JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ReleaseBundleError("bundle payload must be a JSON object")
        if strict_json_dumps(payload) != self._payload_json:
            raise ReleaseBundleError("bundle payload is not canonical JSON")
        if payload.get("schema_version") != STRUCTURAL_BUNDLE_SCHEMA_VERSION:
            raise ReleaseBundleError("unsupported structural bundle schema")
        if _sha256(self._payload_json.encode("utf-8")) != digest:
            raise ReleaseBundleError("bundle digest differs from canonical payload")

    def to_dict(self) -> dict[str, Any]:
        payload = cast(dict[str, Any], strict_json_loads(self._payload_json))
        return {**payload, "bundle_sha256": self.bundle_sha256}

    def canonical_json(self) -> str:
        return strict_json_dumps(self.to_dict()) + "\n"


def _action_spec_preimages(
    snapshot: AuditedLedgerSnapshot,
) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for record in snapshot.records("action_specs"):
        digest = _digest(
            record.get("action_spec_sha256"),
            "action_spec.action_spec_sha256",
        )
        encoded = record.get("preimage_base64")
        if not isinstance(encoded, str):
            raise ReleaseBundleError("action-spec preimage must be base64 text")
        try:
            preimage = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ReleaseBundleError("action-spec preimage is not canonical base64") from exc
        if base64.b64encode(preimage).decode("ascii") != encoded:
            raise ReleaseBundleError("action-spec preimage base64 spelling differs")
        if _sha256(preimage) != digest:
            raise ReleaseBundleError("action-spec preimage bytes differ from their digest")
        result[digest] = preimage
    return result


def _typed_action_spec(
    preimages: Mapping[str, bytes],
    digest: str,
    *,
    field_name: str,
) -> ExecutableActionSpec:
    try:
        preimage = preimages[digest]
    except KeyError as exc:  # pragma: no cover - ledger audit already proves presence
        raise ReleaseBundleError(f"{field_name} preimage is absent") from exc
    try:
        spec = ExecutableActionSpec.from_preimage(preimage)
    except ValueError as exc:
        raise ReleaseBundleError(
            f"{field_name} is not a typed executable action spec: {exc}"
        ) from exc
    if spec.canonical_digest() != digest:
        raise ReleaseBundleError(f"{field_name} typed spec digest differs")
    return spec


def _artifact_path_from_locator(locator: Any) -> pathlib.Path:
    if not isinstance(locator, str) or not locator:
        raise ReleaseBundleError("protocol result artifact locator is missing")
    parsed = urllib.parse.urlparse(locator)
    if parsed.scheme != "file" or parsed.netloc or parsed.params or parsed.query or parsed.fragment:
        raise ReleaseBundleError("protocol result artifact locator must be a local file URI")
    path = pathlib.Path(urllib.parse.unquote(parsed.path))
    if not path.is_absolute():
        raise ReleaseBundleError("protocol result artifact locator must be absolute")
    return path


def _revalidate_protocol_artifacts(
    snapshot: AuditedLedgerSnapshot,
) -> dict[str, int]:
    """Revalidate every behavior-available intervention and retained result byte.

    The ledger's generic preimage contract is useful for write-ahead integrity,
    but a release bundle needs the stricter executable schema for every action
    that had positive behavior support.  Otherwise the purported intervention
    set could contain offers that were never executable.
    """

    preimages = _action_spec_preimages(snapshot)
    dispatch_by_decision = {
        cast(str, record["decision_id"]): record for record in snapshot.records("dispatch_intents")
    }
    reservation_by_dispatch = {
        cast(str, record["dispatch_id"]): record
        for record in snapshot.records("resource_reservations")
    }
    result_by_acquisition = {
        cast(str, record["acquisition_id"]): record for record in snapshot.records("results")
    }
    typed_digests: set[str] = set()
    available_offer_count = 0
    chosen_nonterminal_count = 0
    reopened_result_count = 0

    for policy_record in snapshot.records("policy_decisions"):
        decision = LoggedPolicyDecision.from_dict(policy_record["decision"])
        specs_for_decision: dict[str, ExecutableActionSpec] = {}
        for offer in decision.action_catalog:
            if not offer.available or offer.evidence_kind is None:
                continue
            available_offer_count += 1
            spec = _typed_action_spec(
                preimages,
                offer.action_spec_sha256,
                field_name=(f"decision {decision.decision_id} available offer {offer.action_id}"),
            )
            if (
                spec.action_id != offer.action_id
                or spec.route_action != offer.route_action
                or spec.evidence_kind != offer.evidence_kind
                or spec.adapter_id != offer.adapter_id
                or spec.adapter_version != offer.adapter_version
            ):
                raise ReleaseBundleError(
                    "typed action spec differs from its behavior-available offer"
                )
            manifest = spec.manifest_before()
            dummy_plan = spec.realized_plan("acq-" + "0" * 32)
            if (
                manifest.instance_id != decision.instance_id
                or manifest.candidate_id != decision.candidate_id
                or dummy_plan.instance_id != decision.instance_id
                or dummy_plan.candidate_id != decision.candidate_id
            ):
                raise ReleaseBundleError(
                    "typed action spec belongs to a different task or candidate"
                )
            specs_for_decision[offer.action_id] = spec
            typed_digests.add(spec.canonical_digest())

        for spec in specs_for_decision.values():
            if spec.action_id != "full_repeat":
                continue
            assert spec.repeat_of_action_spec_sha256 is not None
            primary = _typed_action_spec(
                preimages,
                spec.repeat_of_action_spec_sha256,
                field_name=f"decision {decision.decision_id} full-repeat primary",
            )
            try:
                spec.validate_repeat_of(primary)
            except ValueError as exc:
                raise ReleaseBundleError(
                    f"full-repeat action spec is not equivalent to its primary: {exc}"
                ) from exc

        if decision.terminal:
            continue
        chosen_nonterminal_count += 1
        try:
            dispatch = dispatch_by_decision[decision.decision_id]
        except KeyError as exc:  # pragma: no cover - audited join
            raise ReleaseBundleError("chosen nonterminal action has no dispatch") from exc
        chosen = _typed_action_spec(
            preimages,
            decision.chosen_offer.action_spec_sha256,
            field_name=f"decision {decision.decision_id} chosen offer",
        )
        dispatch_id = cast(str, dispatch["dispatch_id"])
        try:
            raw_reservation = reservation_by_dispatch[dispatch_id]
        except KeyError as exc:  # pragma: no cover - audited join
            raise ReleaseBundleError("chosen nonterminal action has no reservation") from exc
        reservation = ReservationRequest(
            acquisition_id=cast(str, raw_reservation["acquisition_id"]),
            resource_kind=cast(str, raw_reservation["resource_kind"]),
            resource_key=cast(str, raw_reservation["resource_key"]),
            details=cast(Mapping[str, Any], raw_reservation["details"]),
        )
        assert decision.acquisition_id is not None
        plan = chosen.realized_plan(decision.acquisition_id)
        try:
            chosen.validate_dispatch(
                action_spec_sha256=decision.chosen_offer.action_spec_sha256,
                decision=decision,
                reservation=reservation,
                plan=plan,
            )
        except ValueError as exc:
            raise ReleaseBundleError(f"chosen action spec/dispatch join is invalid: {exc}") from exc

        result = result_by_acquisition.get(decision.acquisition_id)
        if result is None:
            continue
        if result.get("validation_contract") != PROTOCOL_RESULT_VALIDATION_CONTRACT:
            raise ReleaseBundleError(
                "release bundle cannot include a non-protocol synthetic result"
            )
        observation = EvidenceObservation.from_dict(result["observation"])
        artifact_path = _artifact_path_from_locator(observation.metadata.get("artifact_locator"))
        artifact_bytes = _read_regular_file(
            artifact_path,
            maximum_bytes=_MAX_ACQUISITION_ARTIFACT_BYTES,
        )
        if _sha256(artifact_bytes) != result.get("artifact_sha256"):
            raise ReleaseBundleError(
                "retained acquisition artifact bytes differ from the ledger result"
            )
        output_bytes = _read_regular_file(
            pathlib.Path(plan.output_path),
            maximum_bytes=_MAX_ACQUISITION_ARTIFACT_BYTES,
        )
        if _sha256(output_bytes) != result.get("completed_output_sha256"):
            raise ReleaseBundleError("completed output bytes differ from the ledger result")
        reopened_result_count += 1

    return {
        "behavior_available_offer_count": available_offer_count,
        "unique_typed_action_spec_count": len(typed_digests),
        "chosen_nonterminal_count": chosen_nonterminal_count,
        "reopened_protocol_result_count": reopened_result_count,
    }


def _zero_cost() -> dict[str, int | float]:
    return {
        "wall_seconds": 0.0,
        "cpu_seconds": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "storage_bytes": 0,
        "usd": 0.0,
    }


def _sum_costs(costs: Sequence[Mapping[str, Any]]) -> dict[str, int | float]:
    result = _zero_cost()
    for name in ("wall_seconds", "cpu_seconds", "usd"):
        result[name] = math.fsum(float(cost[name]) for cost in costs)
    for name in ("input_tokens", "output_tokens", "storage_bytes"):
        result[name] = sum(int(cost[name]) for cost in costs)
    return result


def _provisioning_receipt_projection(spec: ExecutableActionSpec) -> dict[str, Any]:
    receipt = spec.provisioning_receipt
    return {
        "receipt_sha256": receipt.receipt_sha256,
        "provisioner_id": receipt.provisioner_id,
        "provisioner_version": receipt.provisioner_version,
        "architecture": receipt.architecture,
        "substrate": receipt.substrate,
        "image_digest": receipt.image_digest,
    }


def _result_projection(
    record: Mapping[str, Any],
    *,
    provisioning_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    observation = EvidenceObservation.from_dict(record["observation"])
    measured_raw = observation.metadata.get("measured_cost_dimensions", ())
    declared_raw = observation.metadata.get("producer_declared_cost_dimensions", ())
    measured = (
        tuple(measured_raw)
        if isinstance(measured_raw, (list, tuple))
        and all(isinstance(item, str) for item in measured_raw)
        else ()
    )
    producer_declared = (
        tuple(declared_raw)
        if isinstance(declared_raw, (list, tuple))
        and all(isinstance(item, str) for item in declared_raw)
        else ()
    )
    cost = asdict(observation.cost)
    cost_status: dict[str, str] = {}
    for name, value in cost.items():
        if name in measured:
            status = "measured"
        elif name in producer_declared:
            status = "producer_declared"
        elif value == 0:
            status = "unreported_zero"
        else:
            status = "unattributed"
        cost_status[name] = status
    return {
        "result_id": record["result_id"],
        "acquisition_id": record["acquisition_id"],
        "completed_at": record["completed_at"],
        "artifact_sha256": record["artifact_sha256"],
        "completed_output_sha256": record["completed_output_sha256"],
        "validation_contract": record["validation_contract"],
        "evidence_kind": observation.kind.value,
        "observation_status": observation.status.value,
        "observation_source": observation.source,
        "observation_source_version": observation.source_version,
        "provisioning_receipt": dict(provisioning_receipt),
        "cost": cost,
        "cost_dimension_status": cost_status,
    }


def _decision_projection(
    decision: LoggedPolicyDecision,
    *,
    action_spec: ExecutableActionSpec | None,
    result: Mapping[str, Any] | None,
    incident: Mapping[str, Any] | None,
) -> dict[str, Any]:
    offer = decision.chosen_offer
    if decision.terminal != (action_spec is None):
        raise ReleaseBundleError("terminal decision and executable action-spec presence disagree")
    provisioning_receipt = (
        None if action_spec is None else _provisioning_receipt_projection(action_spec)
    )
    projected_result: dict[str, Any] | None = None
    if result is not None:
        if provisioning_receipt is None:
            raise ReleaseBundleError("terminal decision cannot have an acquisition result")
        projected_result = _result_projection(
            result,
            provisioning_receipt=provisioning_receipt,
        )
    projection: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "decision_sha256": decision.decision_sha256,
        "trajectory_head_sha256": decision.trajectory_head_sha256,
        "decision_step": decision.decision_step,
        "decided_at": decision.decided_at,
        "history_sha256": decision.history_sha256,
        "router_state_sha256": decision.router_state_sha256,
        "policy_id": decision.policy_id,
        "policy_version": decision.policy_version,
        "policy_code_config_sha256": decision.policy_code_config_sha256,
        "chosen_action_id": decision.chosen_action_id,
        "route_action": offer.route_action.value,
        "evidence_kind": None if offer.evidence_kind is None else offer.evidence_kind.value,
        "action_spec_sha256": offer.action_spec_sha256,
        "provisioning_receipt": provisioning_receipt,
        "chosen_propensity": decision.chosen_propensity,
        "acquisition_id": decision.acquisition_id,
        "terminal": decision.terminal,
        "result": projected_result,
        "incident": None,
    }
    if incident is not None:
        projection["incident"] = {
            "incident_id": incident["incident_id"],
            "occurred_at": incident["occurred_at"],
            "reason_code": incident["reason_code"],
        }
    return projection


def _candidate_status(
    *,
    task_halted: bool,
    selection: TaskSelectionDecision | None,
    decisions: Sequence[dict[str, Any]],
) -> str:
    if task_halted:
        return "halted"
    if selection is not None:
        return (
            "selected"
            if selection.selected_candidate_id
            == (decisions[0]["candidate_id"] if decisions else None)
            else "complete_not_selected"
        )
    if not decisions:
        return "unstarted"
    final = decisions[-1]["projection"]
    if final["terminal"]:
        return "terminal_selection_uncommitted"
    if final["incident"] is not None:
        return "halted"
    if final["result"] is None:
        return "pending_acquisition"
    return "awaiting_successor_round"


def _compile_policy_projection(snapshot: AuditedLedgerSnapshot) -> dict[str, Any]:
    frame = snapshot.bindings.frame
    round_rows = snapshot.records("rounds")
    policy_rows = snapshot.records("policy_decisions")
    result_rows = snapshot.records("results")
    incident_rows = snapshot.records("incidents")
    selection_rows = snapshot.records("selections")
    action_spec_preimages = _action_spec_preimages(snapshot)

    round_decisions = {
        cast(str, row["round_sha256"]): TaskRoundDecision.from_dict(row["round"])
        for row in round_rows
    }
    round_identity = {
        round_sha256: (round_decision.task_id, round_decision.round_index)
        for round_sha256, round_decision in round_decisions.items()
    }
    latest_round_by_task: dict[str, TaskRoundDecision] = {}
    for round_decision in round_decisions.values():
        previous = latest_round_by_task.get(round_decision.task_id)
        if previous is None or round_decision.round_index > previous.round_index:
            latest_round_by_task[round_decision.task_id] = round_decision
    result_by_acquisition = {cast(str, row["acquisition_id"]): row for row in result_rows}
    incident_by_acquisition = {cast(str, row["acquisition_id"]): row for row in incident_rows}
    selection_by_task = {
        cast(str, row["task_id"]): TaskSelectionDecision.from_dict(row["selection"])
        for row in selection_rows
    }
    halted_tasks = {cast(str, row["task_id"]) for row in incident_rows}

    decisions_by_candidate: dict[tuple[str, str], list[tuple[int, LoggedPolicyDecision]]] = (
        defaultdict(list)
    )
    for row in policy_rows:
        round_sha = cast(str, row["round_sha256"])
        try:
            task_id, round_index = round_identity[round_sha]
        except KeyError as exc:  # pragma: no cover - ledger audit proves the join
            raise ReleaseBundleError("policy decision lost its audited round") from exc
        decision = LoggedPolicyDecision.from_dict(row["decision"])
        if decision.instance_id != task_id:
            raise ReleaseBundleError("policy instance_id differs from its audited task")
        decisions_by_candidate[(task_id, decision.candidate_id)].append((round_index, decision))

    candidate_rows: list[dict[str, Any]] = []
    candidates_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task_id in frame.task_ids:
        selection = selection_by_task.get(task_id)
        for candidate_id in frame.candidate_ids_for(task_id):
            typed_decisions = [
                decision
                for _, decision in sorted(
                    decisions_by_candidate.get((task_id, candidate_id), []),
                    key=lambda item: (item[0], item[1].decision_step),
                )
            ]
            staged: list[dict[str, Any]] = []
            for decision in typed_decisions:
                acquisition_id = decision.acquisition_id
                action_spec = (
                    None
                    if decision.terminal
                    else _typed_action_spec(
                        action_spec_preimages,
                        decision.chosen_offer.action_spec_sha256,
                        field_name=f"decision {decision.decision_id} chosen offer",
                    )
                )
                result = (
                    None if acquisition_id is None else result_by_acquisition.get(acquisition_id)
                )
                incident = (
                    None if acquisition_id is None else incident_by_acquisition.get(acquisition_id)
                )
                staged.append(
                    {
                        "candidate_id": candidate_id,
                        "projection": _decision_projection(
                            decision,
                            action_spec=action_spec,
                            result=result,
                            incident=incident,
                        ),
                    }
                )
            projections = [item["projection"] for item in staged]
            result_projections = [
                cast(dict[str, Any], item["result"])
                for item in projections
                if item["result"] is not None
            ]
            execution_results = [
                item
                for item in result_projections
                if item["evidence_kind"] in {kind.value for kind in _EXECUTION_KINDS}
            ]
            costs = [cast(dict[str, Any], item["cost"]) for item in result_projections]
            cost_status = {
                name: sorted(
                    {
                        cast(dict[str, str], item["cost_dimension_status"])[name]
                        for item in result_projections
                    }
                )
                for name in _zero_cost()
            }
            terminal = projections[-1] if projections and projections[-1]["terminal"] else None
            selection_sha = None if selection is None else selection.decision_sha256
            selected_candidate_id = None if selection is None else selection.selected_candidate_id
            trajectory_material = {
                "contract": TRAJECTORY_DIGEST_CONTRACT,
                "task_id": task_id,
                "candidate_id": candidate_id,
                "decision_sha256s": [item["decision_sha256"] for item in projections],
                "trajectory_head_sha256s": [item["trajectory_head_sha256"] for item in projections],
                "result_ids": [item["result_id"] for item in result_projections],
                "incident_ids": [
                    item["incident"]["incident_id"]
                    for item in projections
                    if item["incident"] is not None
                ],
                "nonterminal_provisioning_receipt_sha256s": [
                    cast(dict[str, Any], item["provisioning_receipt"])["receipt_sha256"]
                    for item in projections
                    if item["provisioning_receipt"] is not None
                ],
                "resolved_execution_provisioning": [
                    {
                        "result_id": item["result_id"],
                        **cast(dict[str, Any], item["provisioning_receipt"]),
                    }
                    for item in execution_results
                ],
                "terminal_decision_sha256": (
                    None if terminal is None else terminal["decision_sha256"]
                ),
                "terminal_action": None if terminal is None else terminal["route_action"],
                "task_selection_sha256": selection_sha,
                "selected_candidate_id": selected_candidate_id,
            }
            candidate = {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "status": _candidate_status(
                    task_halted=task_id in halted_tasks,
                    selection=selection,
                    decisions=staged,
                ),
                "selected": selected_candidate_id == candidate_id,
                "decision_count": len(projections),
                "acquisition_count": sum(not item["terminal"] for item in projections),
                "resolved_acquisition_count": len(result_projections),
                "execution_acquisition_count": len(execution_results),
                "full_execution_acquisition_count": sum(
                    item["evidence_kind"] == EvidenceKind.FULL_EXECUTION.value
                    for item in execution_results
                ),
                "execution_substrate_counts": dict(
                    sorted(
                        Counter(
                            cast(dict[str, Any], item["provisioning_receipt"])["substrate"]
                            for item in execution_results
                        ).items()
                    )
                ),
                "image_bound_execution_acquisition_count": sum(
                    cast(dict[str, Any], item["provisioning_receipt"])["image_digest"] is not None
                    for item in execution_results
                ),
                "ledger_observation_cost": _sum_costs(costs),
                "cost_dimension_status": cost_status,
                "terminal_action": None if terminal is None else terminal["route_action"],
                "terminal_decision_sha256": (
                    None if terminal is None else terminal["decision_sha256"]
                ),
                "task_selection_sha256": selection_sha,
                "policy_trajectory_probability": (
                    math.prod(item["chosen_propensity"] for item in projections)
                    if projections
                    else 1.0
                ),
                "policy_trajectory_log_probability": math.fsum(
                    math.log(item["chosen_propensity"]) for item in projections
                ),
                "candidate_trajectory_sha256": _canonical_sha256(trajectory_material),
                "decisions": projections,
            }
            candidate_rows.append(candidate)
            candidates_by_task[task_id].append(candidate)

    task_rows: list[dict[str, Any]] = []
    for task_id in frame.task_ids:
        selection = selection_by_task.get(task_id)
        latest_round = latest_round_by_task.get(task_id)
        task_candidates = candidates_by_task[task_id]
        if latest_round is None:
            task_log_propensities: tuple[float, ...] = ()
            task_probability = 1.0
            task_log_probability = 0.0
        else:
            task_log_propensities = latest_round.task_trajectory_action_log_propensities
            task_probability = latest_round.task_trajectory_probability
            task_log_probability = latest_round.task_trajectory_log_probability
        if selection is not None and (
            latest_round is None
            or selection.final_round_decision_sha256 != latest_round.decision_sha256
            or selection.final_task_action_log_propensities != task_log_propensities
            or selection.final_task_trajectory_probability != task_probability
            or selection.final_task_trajectory_log_probability != task_log_probability
        ):
            raise ReleaseBundleError(
                "completed task selection differs from its canonical latest-round propensity"
            )
        if task_id in halted_tasks:
            status = "halted"
        elif selection is None:
            status = (
                "unstarted"
                if all(item["status"] == "unstarted" for item in task_candidates)
                else "incomplete"
            )
        elif selection.selected_candidate_id is None:
            status = "abstained"
        else:
            status = "selected_candidate"
        task_material = {
            "contract": TASK_TRAJECTORY_DIGEST_CONTRACT,
            "task_id": task_id,
            "candidate_trajectory_sha256s": [
                item["candidate_trajectory_sha256"] for item in task_candidates
            ],
            "task_selection_sha256": (None if selection is None else selection.decision_sha256),
            "selected_candidate_id": (
                None if selection is None else selection.selected_candidate_id
            ),
            "task_trajectory_action_log_propensities": list(task_log_propensities),
            "task_trajectory_probability": task_probability,
            "task_trajectory_log_probability": task_log_probability,
        }
        task_rows.append(
            {
                "task_id": task_id,
                "status": status,
                "selected_candidate_id": (
                    None if selection is None else selection.selected_candidate_id
                ),
                "task_selection_sha256": (None if selection is None else selection.decision_sha256),
                "task_trajectory_action_log_propensities": list(task_log_propensities),
                "task_trajectory_probability": task_probability,
                "task_trajectory_log_probability": task_log_probability,
                "candidate_trajectory_sha256s": [
                    item["candidate_trajectory_sha256"] for item in task_candidates
                ],
                "task_trajectory_sha256": _canonical_sha256(task_material),
            }
        )

    return {
        "tasks": task_rows,
        "candidates": candidate_rows,
        "task_status_counts": dict(sorted(Counter(item["status"] for item in task_rows).items())),
        "candidate_status_counts": dict(
            sorted(Counter(item["status"] for item in candidate_rows).items())
        ),
    }


def _validated_artifacts(
    *,
    candidate_registry: BoundReleaseArtifact | None,
    bootstrap_stream: BoundReleaseArtifact | None,
    curator_stream: BoundReleaseArtifact | None,
    adjudications: BoundReleaseArtifact | None,
    resource_receipts: BoundReleaseArtifact | None,
    published_artifacts: Sequence[BoundReleaseArtifact],
    run_manifest: BoundReleaseArtifact | None,
    score_receipts: BoundReleaseArtifact | None,
) -> tuple[dict[str, BoundReleaseArtifact], tuple[BoundReleaseArtifact, ...]]:
    named = {
        "candidate_registry": candidate_registry,
        "bootstrap_stream": bootstrap_stream,
        "curator_stream": curator_stream,
        "adjudications": adjudications,
        "resource_receipts": resource_receipts,
        "run_manifest": run_manifest,
        "score_receipts": score_receipts,
    }
    validated: dict[str, BoundReleaseArtifact] = {}
    for name, artifact in named.items():
        if artifact is None:
            continue
        if not isinstance(artifact, BoundReleaseArtifact):
            raise ReleaseBundleError(f"{name} must be a BoundReleaseArtifact")
        if artifact.logical_name != name:
            raise ReleaseBundleError(f"{name} artifact must use logical_name={name!r}")
        validated[name] = artifact.revalidate()
    if not isinstance(published_artifacts, (list, tuple)) or any(
        not isinstance(item, BoundReleaseArtifact) for item in published_artifacts
    ):
        raise ReleaseBundleError("published_artifacts must contain BoundReleaseArtifact values")
    published = tuple(item.revalidate() for item in published_artifacts)
    published_names = [item.logical_name for item in published]
    if published_names != sorted(published_names) or len(published_names) != len(
        set(published_names)
    ):
        raise ReleaseBundleError("published_artifacts must have sorted unique logical names")
    overlap = set(validated).intersection(published_names)
    if overlap:
        raise ReleaseBundleError(
            f"published artifact names overlap scientific inputs: {sorted(overlap)}"
        )
    return validated, published


def compile_prospective_release(
    snapshot: AuditedLedgerSnapshot,
    *,
    candidate_registry: BoundReleaseArtifact | None = None,
    bootstrap_stream: BoundReleaseArtifact | None = None,
    curator_stream: BoundReleaseArtifact | None = None,
    adjudications: BoundReleaseArtifact | None = None,
    resource_receipts: BoundReleaseArtifact | None = None,
    published_artifacts: Sequence[BoundReleaseArtifact] = (),
    run_manifest: BoundReleaseArtifact | None = None,
    score_receipts: BoundReleaseArtifact | None = None,
) -> ProspectiveReleaseBundle:
    """Compile a receipt-derived structural bundle and keep science gates closed.

    Every supplied input is reopened during this call.  Additional streams are
    bound into the bundle, but this schema does not interpret them as scientific
    truth.  A future incompatible compiler must validate typed raw reviewer
    votes, curator dossiers, receipts, and score calibration before enabling the
    logged-policy or paired-sensor profiles.
    """

    if not isinstance(snapshot, AuditedLedgerSnapshot):
        raise ReleaseBundleError("snapshot must be an AuditedLedgerSnapshot")
    current = snapshot.revalidate()
    scientific, published = _validated_artifacts(
        candidate_registry=candidate_registry,
        bootstrap_stream=bootstrap_stream,
        curator_stream=curator_stream,
        adjudications=adjudications,
        resource_receipts=resource_receipts,
        published_artifacts=published_artifacts,
        run_manifest=run_manifest,
        score_receipts=score_receipts,
    )
    protocol_artifact_audit = _revalidate_protocol_artifacts(current)
    projection = _compile_policy_projection(current)
    audit = current.audit
    audit_payload = {
        "record_count": audit.record_count,
        "export_head_sha256": audit.export_head_sha256,
        "event_head_sha256": audit.event_head_sha256,
        "table_counts": {name: count for name, count in audit.table_counts},
        "complete": audit.complete,
        "analysis_ready": audit.analysis_ready,
        "committed_task_count": audit.committed_task_count,
        "selected_task_count": audit.selected_task_count,
        "pending_dispatch_count": audit.pending_dispatch_count,
        "halted_task_count": audit.halted_task_count,
        "protocol_result_count": audit.protocol_result_count,
    }
    missing_inputs = [name for name in _SCIENTIFIC_INPUT_NAMES if name not in scientific]
    blockers = []
    if not audit.analysis_ready:
        blockers.append("behavior_ledger_does_not_cover_complete_frozen_frame")
    blockers.extend(f"missing_{name}" for name in missing_inputs)
    blockers.append("typed_independent_truth_and_event_quality_compiler_requires_schema_vnext")
    payload = {
        "schema_version": STRUCTURAL_BUNDLE_SCHEMA_VERSION,
        "contract": BUNDLE_DIGEST_CONTRACT,
        "study_id": SCHEDULER_STUDY_ID,
        "profile": "STRUCTURAL",
        "source_bindings": {
            "ledger_artifact_id": current.trust_anchor.artifact_id,
            "ledger_attestor_id": current.trust_anchor.attestor_id,
            "ledger_export_sha256": current.ledger_export_sha256,
            "ledger_trust_anchor_sha256": current.trust_anchor_sha256,
            "ledger_export_head_sha256": audit.export_head_sha256,
            "ledger_event_head_sha256": audit.event_head_sha256,
            "repository_bindings": _binding_payload(current.bindings),
            "scientific_inputs": [scientific[name].binding() for name in sorted(scientific)],
            "published_artifacts": [item.binding() for item in published],
        },
        "ledger_audit": audit_payload,
        "protocol_artifact_audit": protocol_artifact_audit,
        "frame": {
            "expected_task_count": len(current.bindings.frame.task_ids),
            "expected_candidate_count": sum(
                len(current.bindings.frame.candidate_ids_for(task_id))
                for task_id in current.bindings.frame.task_ids
            ),
            "task_status_counts": projection["task_status_counts"],
            "candidate_status_counts": projection["candidate_status_counts"],
        },
        "profiles": {
            "STRUCTURAL": {
                "eligible": True,
                "reason": "pinned_export_reaudited_and_projection_derived",
            },
            "LOGGED_POLICY_EVALUABLE": {
                "eligible": False,
                "reason": "independent_truth_and_typed_score_receipts_not_compiled",
            },
            "PAIRED_SENSOR": {
                "eligible": False,
                "reason": "paired_curator_receipts_and_event_quality_votes_not_compiled",
            },
        },
        "scientific_release_ready": False,
        "activation_blockers": blockers,
        "tasks": projection["tasks"],
        "candidates": projection["candidates"],
    }
    canonical = strict_json_dumps(payload)
    return ProspectiveReleaseBundle(
        _payload_json=canonical,
        bundle_sha256=_sha256(canonical.encode("utf-8")),
    )


def write_prospective_release_bundle(
    bundle: ProspectiveReleaseBundle,
    output_path: pathlib.Path,
) -> None:
    if not isinstance(bundle, ProspectiveReleaseBundle):
        raise ReleaseBundleError("bundle must be a ProspectiveReleaseBundle")
    target = pathlib.Path(output_path)
    if bundle.bundle_sha256 not in target.name:
        raise ReleaseBundleError("release bundle filename must contain its complete content digest")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = pathlib.Path(stream.name)
            stream.write(bundle.canonical_json().encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ReleaseBundleError(
                "release bundle path already exists; immutable outputs are never replaced"
            ) from exc
        if os.name != "nt":
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
