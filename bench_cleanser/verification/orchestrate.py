"""Fail-closed orchestration from a recorded route action to one acquisition.

The orchestrator never invents a command.  An operator-owned, strict plan maps
eligible route actions to complete :class:`AcquisitionRequest` values and binds
that mapping to a manifest, candidate, base commit, canonical workspace root,
and a provisioner-owned workspace identity marker.  Reservations provide
at-most-once exclusion only when contenders share the configured coordination
directory and decision key, or the same output path, artifact directory, and
acquisition ID.  They are not a global CAS, execution recovery protocol, or
exactly-once guarantee.

A completed output can be reloaded only by supplying the independently retained
pre-execution manifest, exact route decision, and operator plan.  The loader
revalidates the prepared envelope, raw artifact, routed observation, and exact
manifest successor.  It enables conservative ingestion by an external durable
ledger; it does not decide whether an ambiguous claimed attempt may be retried.

This module verifies a provisioner marker binding; it does not attest the whole
workspace or provide an operating-system sandbox.  The command still has the
permissions of the calling user, as documented by :mod:`verification.acquire`.
"""

from __future__ import annotations

import base64
import hashlib
import math
import os
import pathlib
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, TextIO
from urllib.parse import urlparse
from urllib.request import url2pathname

from bench_cleanser import __version__
from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_load,
    strict_json_loads,
)
from bench_cleanser.verification.acquire import (
    ACQUISITION_SCHEMA_VERSION,
    SEMANTIC_OUTPUT_SCHEMA_VERSION,
    SEMANTIC_PRODUCER_DECLARED_FIELDS,
    AcquisitionRequest,
    acquire_evidence,
    decode_semantic_output,
)
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)

ORCHESTRATION_SCHEMA_VERSION = "0.2.0"
WORKSPACE_IDENTITY_SCHEMA_VERSION = "0.1.0"
MAX_WORKSPACE_IDENTITY_BYTES = 1024 * 1024
MAX_ACQUISITION_ARTIFACT_OVERHEAD_BYTES = 4 * 1024 * 1024
MAX_ORCHESTRATION_RECORD_BYTES = 16 * 1024 * 1024
ATTEMPT_SEMANTICS = "at_most_once"
ATTEMPT_SCOPE = (
    "shared_coordination_directory_decision_key_output_path_and_artifact_id"
)
WORKSPACE_IDENTITY_SCOPE = "provisioner_marker_only"
EXECUTION_BACKEND = "local_process_unsafe_non_isolated"
DETACHED_CHILD_CONTAINMENT = "not_guaranteed"

_ACTION_EVIDENCE_KIND: Mapping[RouteAction, EvidenceKind] = MappingProxyType({
    RouteAction.RUN_STATIC: EvidenceKind.STATIC,
    RouteAction.RUN_SEMANTIC: EvidenceKind.SEMANTIC,
    RouteAction.RUN_TARGETED: EvidenceKind.TARGETED_EXECUTION,
    RouteAction.RUN_FULL: EvidenceKind.FULL_EXECUTION,
    RouteAction.HARDEN_ORACLE: EvidenceKind.ORACLE_HARDENING,
})
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_CANDIDATE_ID_RE = re.compile(r"sha256:[0-9a-f]{64}")
_BASE_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}")
_ACQUISITION_ID_RE = re.compile(r"acq-[0-9a-f]{32}")


def _string(value: Any, field_name: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a JSON string")
    if "\x00" in value:
        raise ValueError(f"{field_name} cannot contain NUL bytes")
    if nonempty and (not value.strip() or value != value.strip()):
        raise ValueError(
            f"{field_name} must be non-empty and have no surrounding whitespace"
        )
    return value


def _sha256(value: Any, field_name: str) -> str:
    digest = _string(value, field_name, nonempty=True)
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"{field_name} must be 64 lowercase hexadecimal characters")
    return digest


def _candidate_id(value: Any, field_name: str) -> str:
    candidate = _string(value, field_name, nonempty=True)
    if not _CANDIDATE_ID_RE.fullmatch(candidate):
        raise ValueError(f"{field_name} must be a lowercase sha256:<digest> identity")
    return candidate


def _exact_object(
    value: Any,
    fields: set[str],
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    unknown = sorted(set(value).difference(fields))
    missing = sorted(fields.difference(value))
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {unknown}")
    if missing:
        raise ValueError(f"{field_name} is missing fields: {missing}")
    return value


def _base_commit(value: Any, field_name: str) -> str:
    commit = _string(value, field_name, nonempty=True)
    if not _BASE_COMMIT_RE.fullmatch(commit):
        raise ValueError(f"{field_name} must be a full 40- or 64-character hash")
    return commit.casefold()


def _relative_marker_path(value: Any) -> str:
    raw = _string(value, "workspace_identity_path", nonempty=True)
    path = pathlib.Path(raw)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError(
            "workspace_identity_path must be a confined relative file path"
        )
    if path == pathlib.Path("."):
        raise ValueError("workspace_identity_path must name a file")
    return raw


def _decision_dict(decision: RouteDecision) -> dict[str, Any]:
    return {
        "action": decision.action.value,
        "policy_version": decision.policy_version,
        "candidate_risk": decision.candidate_risk,
        "verifier_risk": decision.verifier_risk,
        "expected_information_gain": decision.expected_information_gain,
        "estimated_relative_cost": decision.estimated_relative_cost,
        "reasons": list(decision.reasons),
        "terminal": decision.terminal,
        "scores_calibrated": decision.scores_calibrated,
        "calibration_id": decision.calibration_id,
    }


def _canonical_sha256(value: Any) -> str:
    payload = strict_json_dumps(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _strict_utc_timestamp(value: Any, field_name: str) -> datetime:
    timestamp = _string(value, field_name, nonempty=True)
    if not timestamp.endswith("Z") or "T" not in timestamp:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp") from exc
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    canonical = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if timestamp != canonical:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    return parsed


@dataclass(frozen=True)
class RouteAcquisitionPlan:
    """Operator-owned action mapping bound to one routed candidate state."""

    instance_id: str
    candidate_id: str
    manifest_sha256: str
    base_commit: str
    workspace_root: str
    workspace_id: str
    workspace_identity_path: str
    workspace_identity_sha256: str
    acquisition_id: str
    coordination_directory: str
    artifact_directory: str
    output_path: str
    requests: Mapping[RouteAction, AcquisitionRequest]
    schema_version: str = ORCHESTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ORCHESTRATION_SCHEMA_VERSION:
            raise ValueError(
                "unsupported orchestration schema version "
                f"{self.schema_version!r}; expected {ORCHESTRATION_SCHEMA_VERSION!r}"
            )
        _string(self.instance_id, "instance_id", nonempty=True)
        object.__setattr__(
            self,
            "candidate_id",
            _candidate_id(self.candidate_id, "candidate_id"),
        )
        object.__setattr__(
            self,
            "manifest_sha256",
            _sha256(self.manifest_sha256, "manifest_sha256"),
        )
        object.__setattr__(
            self,
            "base_commit",
            _base_commit(self.base_commit, "base_commit"),
        )
        workspace_root = _string(
            self.workspace_root,
            "workspace_root",
            nonempty=True,
        )
        if not pathlib.Path(workspace_root).is_absolute():
            raise ValueError("workspace_root must be an absolute path")
        workspace_id = _string(self.workspace_id, "workspace_id", nonempty=True)
        if not _CANDIDATE_ID_RE.fullmatch(workspace_id):
            raise ValueError("workspace_id must be a lowercase sha256:<digest> identity")
        object.__setattr__(
            self,
            "workspace_identity_path",
            _relative_marker_path(self.workspace_identity_path),
        )
        object.__setattr__(
            self,
            "workspace_identity_sha256",
            _sha256(
                self.workspace_identity_sha256,
                "workspace_identity_sha256",
            ),
        )
        acquisition_id = _string(
            self.acquisition_id,
            "acquisition_id",
            nonempty=True,
        )
        if not _ACQUISITION_ID_RE.fullmatch(acquisition_id):
            raise ValueError(
                "acquisition_id must have the form 'acq-' followed by "
                "32 lowercase hexadecimal characters"
            )
        for name in ("coordination_directory", "artifact_directory", "output_path"):
            raw_path = _string(getattr(self, name), name, nonempty=True)
            if not pathlib.Path(raw_path).is_absolute():
                raise ValueError(f"{name} must be an absolute path")

        if not isinstance(self.requests, Mapping) or not self.requests:
            raise ValueError("requests must be a non-empty action mapping")
        normalized: dict[RouteAction, AcquisitionRequest] = {}
        for action, request in self.requests.items():
            if not isinstance(action, RouteAction):
                raise ValueError("request mapping keys must be RouteAction values")
            expected_kind = _ACTION_EVIDENCE_KIND.get(action)
            if expected_kind is None:
                raise ValueError(
                    f"route action {action.value!r} has no bounded acquisition mapping"
                )
            if not isinstance(request, AcquisitionRequest):
                raise ValueError(
                    f"request mapping for {action.value!r} must be an AcquisitionRequest"
                )
            if request.kind != expected_kind:
                raise ValueError(
                    f"route action {action.value!r} requires evidence kind "
                    f"{expected_kind.value!r}, got {request.kind.value!r}"
                )
            normalized[action] = request
        object.__setattr__(self, "requests", MappingProxyType(normalized))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instance_id": self.instance_id,
            "candidate_id": self.candidate_id,
            "manifest_sha256": self.manifest_sha256,
            "base_commit": self.base_commit,
            "workspace_root": self.workspace_root,
            "workspace_id": self.workspace_id,
            "workspace_identity_path": self.workspace_identity_path,
            "workspace_identity_sha256": self.workspace_identity_sha256,
            "acquisition_id": self.acquisition_id,
            "coordination_directory": self.coordination_directory,
            "artifact_directory": self.artifact_directory,
            "output_path": self.output_path,
            "requests": {
                action.value: request.to_dict()
                for action, request in sorted(
                    self.requests.items(),
                    key=lambda item: item[0].value,
                )
            },
        }

    @classmethod
    def from_dict(cls, value: Any) -> RouteAcquisitionPlan:
        if not isinstance(value, dict):
            raise ValueError("route acquisition plan must be a JSON object")
        allowed = {
            "schema_version",
            "instance_id",
            "candidate_id",
            "manifest_sha256",
            "base_commit",
            "workspace_root",
            "workspace_id",
            "workspace_identity_path",
            "workspace_identity_sha256",
            "acquisition_id",
            "coordination_directory",
            "artifact_directory",
            "output_path",
            "requests",
        }
        unknown = sorted(set(value).difference(allowed))
        if unknown:
            raise ValueError(f"route acquisition plan contains unknown fields: {unknown}")
        missing = sorted(allowed.difference(value))
        if missing:
            raise ValueError(f"route acquisition plan is missing required fields: {missing}")
        requests_value = value["requests"]
        if not isinstance(requests_value, dict):
            raise ValueError("requests must be a JSON object keyed by route action")
        requests: dict[RouteAction, AcquisitionRequest] = {}
        for raw_action, raw_request in requests_value.items():
            action_text = _string(raw_action, "requests action", nonempty=True)
            try:
                action = RouteAction(action_text)
            except ValueError as exc:
                raise ValueError(f"requests contains unknown route action {action_text!r}") from exc
            if action in requests:
                raise ValueError(f"requests contains duplicate route action {action_text!r}")
            requests[action] = AcquisitionRequest.from_dict(raw_request)
        return cls(
            schema_version=_string(
                value["schema_version"],
                "schema_version",
                nonempty=True,
            ),
            instance_id=_string(value["instance_id"], "instance_id", nonempty=True),
            candidate_id=_candidate_id(value["candidate_id"], "candidate_id"),
            manifest_sha256=_sha256(
                value["manifest_sha256"],
                "manifest_sha256",
            ),
            base_commit=_base_commit(value["base_commit"], "base_commit"),
            workspace_root=_string(
                value["workspace_root"],
                "workspace_root",
                nonempty=True,
            ),
            workspace_id=_string(
                value["workspace_id"],
                "workspace_id",
                nonempty=True,
            ),
            workspace_identity_path=_relative_marker_path(
                value["workspace_identity_path"]
            ),
            workspace_identity_sha256=_sha256(
                value["workspace_identity_sha256"],
                "workspace_identity_sha256",
            ),
            acquisition_id=_string(
                value["acquisition_id"],
                "acquisition_id",
                nonempty=True,
            ),
            coordination_directory=_string(
                value["coordination_directory"],
                "coordination_directory",
                nonempty=True,
            ),
            artifact_directory=_string(
                value["artifact_directory"],
                "artifact_directory",
                nonempty=True,
            ),
            output_path=_string(
                value["output_path"],
                "output_path",
                nonempty=True,
            ),
            requests=requests,
        )


def load_route_acquisition_plan(stream: TextIO) -> RouteAcquisitionPlan:
    """Load one strict route-acquisition plan from a text stream."""

    try:
        value = strict_json_load(stream)
    except ValueError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    return RouteAcquisitionPlan.from_dict(value)


def load_route_acquisition_record(stream: TextIO) -> dict[str, Any]:
    """Load one canonical completed orchestration record without trusting it.

    This performs syntax, duplicate-key, size, canonical-rendering, and top-level
    envelope checks.  Call :func:`validate_completed_route_acquisition` with the
    independently retained manifest, route decision, and plan before using any
    value from the returned mapping.
    """

    text = stream.read(MAX_ORCHESTRATION_RECORD_BYTES + 1)
    if not isinstance(text, str):  # pragma: no cover - TextIO contract
        raise ValueError("orchestration record must be text")
    if len(text) > MAX_ORCHESTRATION_RECORD_BYTES:
        raise ValueError("orchestration record exceeds the bounded envelope")
    try:
        value = strict_json_loads(text)
    except ValueError as exc:
        raise ValueError(f"invalid orchestration record JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("orchestration record must be a JSON object")
    fields = {
        "schema_version",
        "state",
        "orchestrator",
        "attempt_semantics",
        "attempt_scope",
        "workspace_identity_scope",
        "prepared",
        "acquisition_id",
        "plan_sha256",
        "plan",
        "request_sha256",
        "manifest_sha256_before",
        "manifest_sha256_after",
        "route",
        "workspace",
        "observation",
        "manifest",
    }
    unknown = sorted(set(value).difference(fields))
    missing = sorted(fields.difference(value))
    if unknown:
        raise ValueError(f"orchestration record contains unknown fields: {unknown}")
    if missing:
        raise ValueError(f"orchestration record is missing fields: {missing}")
    if value["state"] != "completed":
        raise ValueError("orchestration record is not completed")
    canonical = strict_json_dumps(value, indent=2) + "\n"
    if text != canonical:
        raise ValueError("orchestration record is not in canonical durable form")
    return value


@dataclass(frozen=True)
class RouteAcquisitionResult:
    """In-memory handle to the exact durable orchestration output."""

    manifest: ValidityManifest
    observation: EvidenceObservation
    output_path: pathlib.Path
    output_sha256: str
    manifest_sha256_before: str
    manifest_sha256_after: str
    plan_sha256: str
    route_decision_sha256: str
    prepared_at: str
    prepared_envelope_sha256: str


def _resolve_workspace(plan: RouteAcquisitionPlan) -> pathlib.Path:
    declared_root = pathlib.Path(plan.workspace_root)
    root = declared_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace_root must resolve to a directory")
    if declared_root != root:
        raise ValueError("plan workspace_root must be a canonical physical path")
    for action, request in plan.requests.items():
        request_path = pathlib.Path(request.workspace_root)
        if not request_path.is_absolute():
            raise ValueError(
                f"request for {action.value!r} must use an absolute workspace_root"
            )
        request_root = request_path.resolve(strict=True)
        if request_path != root or request_root != root:
            raise ValueError(
                f"request for {action.value!r} does not use the exact canonical "
                "plan workspace_root"
            )
        relative = pathlib.Path(request.working_directory)
        if relative.is_absolute():
            raise ValueError(
                f"request for {action.value!r} has an absolute working_directory"
            )
        if any(part == ".." for part in relative.parts):
            raise ValueError(
                f"request for {action.value!r} working_directory contains traversal"
            )
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"request for {action.value!r} working_directory uses a symlink"
                )
        working = (root / relative).resolve(strict=True)
        try:
            working.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"request for {action.value!r} escapes the plan workspace_root"
            ) from exc
        if not working.is_dir():
            raise ValueError(
                f"request for {action.value!r} working_directory is not a directory"
            )
    return root


def _workspace_marker(
    plan: RouteAcquisitionPlan,
    manifest: ValidityManifest,
    root: pathlib.Path,
) -> pathlib.Path:
    lexical = root / plan.workspace_identity_path
    if lexical.is_symlink():
        raise ValueError("workspace identity marker cannot be a symbolic link")
    marker = lexical.resolve(strict=True)
    try:
        marker.relative_to(root)
    except ValueError as exc:
        raise ValueError("workspace identity marker escapes workspace_root") from exc
    if not marker.is_file():
        raise ValueError("workspace identity marker must be a regular file")
    with marker.open("rb") as stream:
        payload = stream.read(MAX_WORKSPACE_IDENTITY_BYTES + 1)
    if len(payload) > MAX_WORKSPACE_IDENTITY_BYTES:
        raise ValueError(
            f"workspace identity marker exceeds {MAX_WORKSPACE_IDENTITY_BYTES} bytes"
        )
    if hashlib.sha256(payload).hexdigest() != plan.workspace_identity_sha256:
        raise ValueError("workspace identity marker SHA-256 does not match the plan")
    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"workspace identity marker is not strict UTF-8 JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("workspace identity marker must be a JSON object")
    allowed = {
        "schema_version",
        "instance_id",
        "candidate_id",
        "base_commit",
        "workspace_id",
    }
    unknown = sorted(set(decoded).difference(allowed))
    missing = sorted(allowed.difference(decoded))
    if unknown:
        raise ValueError(f"workspace identity marker contains unknown fields: {unknown}")
    if missing:
        raise ValueError(f"workspace identity marker is missing fields: {missing}")
    schema_version = _string(
        decoded["schema_version"],
        "workspace marker schema_version",
        nonempty=True,
    )
    if schema_version != WORKSPACE_IDENTITY_SCHEMA_VERSION:
        raise ValueError(
            "unsupported workspace identity schema version "
            f"{schema_version!r}; expected {WORKSPACE_IDENTITY_SCHEMA_VERSION!r}"
        )
    if _string(decoded["instance_id"], "workspace marker instance_id", nonempty=True) != (
        manifest.instance_id
    ):
        raise ValueError("workspace identity marker instance_id contradicts the manifest")
    if _candidate_id(decoded["candidate_id"], "workspace marker candidate_id") != (
        manifest.candidate_id
    ):
        raise ValueError("workspace identity marker candidate_id contradicts the manifest")
    if _base_commit(decoded["base_commit"], "workspace marker base_commit") != (
        plan.base_commit
    ):
        raise ValueError("workspace identity marker base_commit contradicts the plan")
    marker_workspace_id = _string(
        decoded["workspace_id"],
        "workspace marker workspace_id",
        nonempty=True,
    )
    if marker_workspace_id != plan.workspace_id:
        raise ValueError("workspace identity marker workspace_id contradicts the plan")
    return marker


def _validate_manifest_and_route(
    manifest: ValidityManifest,
    decision: RouteDecision,
    plan: RouteAcquisitionPlan,
) -> tuple[str, str, int, AcquisitionRequest]:
    if not isinstance(manifest, ValidityManifest):
        raise ValueError("manifest must be a ValidityManifest")
    if not isinstance(decision, RouteDecision):
        raise ValueError("decision must be a RouteDecision")
    if not isinstance(plan, RouteAcquisitionPlan):
        raise ValueError("plan must be a RouteAcquisitionPlan")

    manifest_sha256 = manifest.canonical_digest()
    if manifest_sha256 != plan.manifest_sha256:
        raise ValueError("manifest SHA-256 does not match the operator plan")
    if manifest.instance_id != plan.instance_id:
        raise ValueError("manifest instance_id does not match the operator plan")
    if manifest.candidate_id != plan.candidate_id:
        raise ValueError("manifest candidate_id does not match the operator plan")
    candidate_patch_sha256 = manifest.provenance.get("candidate_patch_sha256")
    if candidate_patch_sha256 != manifest.candidate_id.removeprefix("sha256:"):
        raise ValueError(
            "manifest candidate_patch_sha256 does not match its candidate_id"
        )
    manifest_base_commit = manifest.provenance.get("base_commit", "")
    if _base_commit(manifest_base_commit, "manifest provenance base_commit") != (
        plan.base_commit
    ):
        raise ValueError("manifest base_commit does not match the operator plan")

    if not manifest.route_history:
        raise ValueError("manifest has no recorded route decision")
    route_index = len(manifest.route_history) - 1
    if any(item.terminal for item in manifest.route_history[:route_index]):
        raise ValueError("manifest contains an earlier terminal route decision")
    if manifest.route_history[route_index] != decision:
        raise ValueError("route decision is not the manifest's exact last decision")
    if decision.terminal:
        raise ValueError("terminal route decisions cannot acquire evidence")
    expected_kind = _ACTION_EVIDENCE_KIND.get(decision.action)
    if expected_kind is None:
        raise ValueError(
            f"route action {decision.action.value!r} has no bounded acquisition adapter"
        )
    request = plan.requests.get(decision.action)
    if request is None:
        raise ValueError(
            f"operator plan has no request for route action {decision.action.value!r}"
        )
    if request.kind != expected_kind:
        raise ValueError(
            f"route action {decision.action.value!r} requires evidence kind "
            f"{expected_kind.value!r}"
        )

    if any(
        observation.acquisition_id == plan.acquisition_id
        for observation in manifest.evidence
    ):
        raise ValueError(
            "plan acquisition_id already exists in the manifest evidence ledger"
        )

    decision_sha256 = _canonical_sha256(_decision_dict(decision))
    for observation in manifest.evidence:
        route_provenance = observation.metadata.get("route_provenance")
        if route_provenance is None:
            continue
        if not isinstance(route_provenance, Mapping):
            raise ValueError("existing evidence contains malformed route provenance")
        if route_provenance.get("route_history_index") == route_index:
            raise ValueError(
                "the manifest's last route decision already has acquired evidence"
            )
    return manifest_sha256, decision_sha256, route_index, request


def verify_acquisition_artifact(
    observation: EvidenceObservation,
    request: AcquisitionRequest,
    artifact_directory: pathlib.Path,
    acquisition_id: str,
    request_sha256: str,
    workspace_root: pathlib.Path,
) -> pathlib.Path:
    if observation.kind != request.kind:
        raise ValueError("acquisition returned the wrong evidence kind")
    if observation.source != request.source or (
        observation.source_version != request.source_version
    ):
        raise ValueError("acquisition returned the wrong source identity")
    if observation.acquisition_id != acquisition_id:
        raise ValueError("acquisition returned the wrong preallocated acquisition_id")
    if observation.authoritative:
        raise ValueError("bounded acquisition cannot return authoritative evidence")
    semantic = request.kind == EvidenceKind.SEMANTIC
    if observation.confidence is not None:
        raise ValueError("bounded acquisition cannot return confidence metadata")
    if not semantic:
        if observation.privileged_inputs:
            raise ValueError("bounded acquisition cannot declare privileged inputs")
        if (
            observation.candidate_probability is not None
            or observation.calibrated_risk_upper_bound is not None
            or observation.calibration_id
        ):
            raise ValueError("bounded acquisition returned unsupported scoring metadata")
        expected_validity = (
            0.0 if observation.status == EvidenceStatus.INCONCLUSIVE else None
        )
        if observation.verifier_validity != expected_validity:
            raise ValueError("acquisition observation verifier_validity does not match")
    expected_metadata_fields = {
        "acquisition_schema_version",
        "runner",
        "runner_version",
        "outcome",
        "return_code",
        "capture_incomplete",
        "artifact_sha256",
        "artifact_locator",
        "capture_bindings",
        "stdout_truncated",
        "stderr_truncated",
        "measured_cost_dimensions",
    }
    if semantic:
        expected_metadata_fields.update({
            "semantic_output_schema_version",
            "semantic_output_sha256",
            "semantic_output_error",
            "semantic_output_valid",
            "producer_declared_semantic_fields",
            "producer_declared_cost_dimensions",
        })
    if set(observation.metadata) != expected_metadata_fields:
        raise ValueError("acquisition observation metadata envelope does not match")
    if observation.metadata.get("acquisition_schema_version") != (
        ACQUISITION_SCHEMA_VERSION
    ):
        raise ValueError("acquisition returned an unsupported schema version")
    if observation.metadata.get("runner") != "bench-cleanser-acquire" or (
        observation.metadata.get("runner_version") != __version__
    ):
        raise ValueError("acquisition observation runner identity does not match")
    measured_dimensions = observation.metadata.get("measured_cost_dimensions")
    if not isinstance(measured_dimensions, (list, tuple)):
        raise ValueError("acquisition observation cost dimensions are malformed")
    if tuple(measured_dimensions) != ("wall_seconds", "storage_bytes"):
        raise ValueError("acquisition observation cost dimensions do not match")
    if observation.cost.cpu_seconds:
        raise ValueError("acquisition observation contains unmeasured cost dimensions")
    if not semantic and any(
        (
            observation.cost.input_tokens,
            observation.cost.output_tokens,
            observation.cost.usd,
        )
    ):
        raise ValueError("acquisition observation contains unmeasured cost dimensions")
    artifact_sha256 = _sha256(
        observation.metadata.get("artifact_sha256"),
        "observation artifact_sha256",
    )
    locator = _string(
        observation.metadata.get("artifact_locator"),
        "observation artifact_locator",
        nonempty=True,
    )
    parsed = urlparse(locator)
    if (
        parsed.scheme != "file"
        or parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("acquisition artifact locator must be a local credential-free file URI")
    artifact_path = pathlib.Path(url2pathname(parsed.path))
    if artifact_path.is_symlink():
        raise ValueError("acquisition artifact cannot be a symbolic link")
    artifact = artifact_path.resolve(strict=True)
    artifact_root = artifact_directory.resolve(strict=True)
    if artifact_directory.is_symlink() or artifact_root != artifact_directory:
        raise ValueError("artifact_directory changed during acquisition")
    try:
        artifact.relative_to(artifact_root)
    except ValueError as exc:
        raise ValueError("acquisition artifact is outside artifact_directory") from exc
    if artifact.is_symlink() or not artifact.is_file():
        raise ValueError("acquisition artifact must be a regular non-symlink file")
    expected_artifact = artifact_root / f"{acquisition_id}.json"
    if artifact != expected_artifact:
        raise ValueError("acquisition artifact path is not bound to acquisition_id")
    request_bytes = len(strict_json_dumps(request.to_dict()).encode("utf-8"))
    maximum_size = (
        12 * request.max_capture_bytes
        + MAX_ACQUISITION_ARTIFACT_OVERHEAD_BYTES
        + 6 * request_bytes
    )
    with artifact.open("rb") as stream:
        artifact_bytes = stream.read(maximum_size + 1)
    if len(artifact_bytes) > maximum_size:
        raise ValueError("acquisition artifact exceeds the bounded artifact envelope")
    size = len(artifact_bytes)
    if hashlib.sha256(artifact_bytes).hexdigest() != artifact_sha256:
        raise ValueError("acquisition artifact SHA-256 does not match the observation")
    if size != observation.cost.storage_bytes:
        raise ValueError("acquisition artifact size does not match measured storage cost")
    try:
        raw = strict_json_loads(artifact_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"acquisition artifact is not strict UTF-8 JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("acquisition artifact must be a JSON object")
    allowed_top_level = {
        "schema_version",
        "runner",
        "acquisition_id",
        "request_sha256",
        "kind",
        "source",
        "source_version",
        "argv",
        "workspace_root",
        "working_directory",
        "execution",
        "stdout",
        "stderr",
    }
    if semantic:
        allowed_top_level.add("semantic")
    unknown = sorted(set(raw).difference(allowed_top_level))
    missing = sorted(allowed_top_level.difference(raw))
    if unknown:
        raise ValueError(f"acquisition artifact contains unknown fields: {unknown}")
    if missing:
        raise ValueError(f"acquisition artifact is missing fields: {missing}")
    if raw["schema_version"] != ACQUISITION_SCHEMA_VERSION:
        raise ValueError("acquisition artifact schema_version does not match")
    if raw["acquisition_id"] != acquisition_id:
        raise ValueError("acquisition artifact acquisition_id does not match")
    if raw["request_sha256"] != request_sha256:
        raise ValueError("acquisition artifact request_sha256 does not match")
    if raw["kind"] != request.kind.value:
        raise ValueError("acquisition artifact evidence kind does not match")
    if raw["source"] != request.source or raw["source_version"] != request.source_version:
        raise ValueError("acquisition artifact source identity does not match")
    if raw["argv"] != list(request.argv):
        raise ValueError("acquisition artifact argv does not match the request")
    if raw["workspace_root"] != str(workspace_root):
        raise ValueError("acquisition artifact workspace_root is not canonical or bound")
    expected_working = (workspace_root / request.working_directory).resolve(strict=True)
    expected_relative_working = str(expected_working.relative_to(workspace_root)) or "."
    if raw["working_directory"] != expected_relative_working:
        raise ValueError("acquisition artifact working_directory is not canonical or bound")

    runner = raw["runner"]
    if not isinstance(runner, dict) or set(runner) != {"name", "version"}:
        raise ValueError("acquisition artifact runner identity is malformed")
    if runner != {"name": "bench-cleanser-acquire", "version": __version__}:
        raise ValueError("acquisition artifact runner identity does not match")

    execution = raw["execution"]
    execution_fields = {
        "started_at",
        "finished_at",
        "wall_seconds",
        "timeout_seconds",
        "outcome",
        "return_code",
        "timed_out",
        "residual_process_group",
        "capture_incomplete",
        "setup_error",
        "cleanup_errors",
        "supports_correct_exit_codes",
        "supports_incorrect_exit_codes",
        "shell",
        "sandbox",
        "environment_policy",
        "supplied_environment_keys",
    }
    if not isinstance(execution, dict) or set(execution) != execution_fields:
        raise ValueError("acquisition artifact execution bindings are malformed")
    timeout_seconds = execution["timeout_seconds"]
    if (
        not isinstance(timeout_seconds, float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds != request.timeout_seconds
    ):
        raise ValueError("acquisition artifact timeout binding does not match")
    for field_name, expected_codes in (
        ("supports_correct_exit_codes", request.supports_correct_exit_codes),
        ("supports_incorrect_exit_codes", request.supports_incorrect_exit_codes),
    ):
        raw_codes = execution[field_name]
        if (
            not isinstance(raw_codes, list)
            or any(isinstance(item, bool) or not isinstance(item, int) for item in raw_codes)
            or raw_codes != list(expected_codes)
        ):
            raise ValueError("acquisition artifact exit-code bindings do not match")
    if execution["shell"] is not False or execution["sandbox"] != "not_provided":
        raise ValueError("acquisition artifact isolation bindings do not match")
    if execution["environment_policy"] != "minimal-allowlist-v1":
        raise ValueError("acquisition artifact environment policy does not match")
    started_at = _strict_utc_timestamp(
        execution["started_at"],
        "acquisition artifact started_at",
    )
    finished_at = _strict_utc_timestamp(
        execution["finished_at"],
        "acquisition artifact finished_at",
    )
    if finished_at < started_at:
        raise ValueError("acquisition artifact timestamps are out of order")
    if (
        isinstance(execution["wall_seconds"], bool)
        or not isinstance(execution["wall_seconds"], (int, float))
        or not math.isfinite(execution["wall_seconds"])
        or execution["wall_seconds"] < 0
        or execution["wall_seconds"] != observation.cost.wall_seconds
    ):
        raise ValueError("acquisition artifact wall cost does not match the observation")
    if any(
        not isinstance(execution[name], bool)
        for name in (
            "timed_out",
            "residual_process_group",
            "capture_incomplete",
        )
    ):
        raise ValueError("acquisition artifact process-state bindings are malformed")
    return_code = execution["return_code"]
    if return_code is not None and (
        isinstance(return_code, bool) or not isinstance(return_code, int)
    ):
        raise ValueError("acquisition artifact return_code is malformed")
    observation_return_code = observation.metadata.get("return_code")
    if observation_return_code is not None and (
        isinstance(observation_return_code, bool)
        or not isinstance(observation_return_code, int)
    ):
        raise ValueError("acquisition observation return_code is malformed")
    if type(return_code) is not type(observation_return_code) or (
        return_code != observation_return_code
    ):
        raise ValueError("acquisition artifact return_code does not match the observation")
    observation_capture_incomplete = observation.metadata.get("capture_incomplete")
    if not isinstance(observation_capture_incomplete, bool):
        raise ValueError("acquisition observation capture_incomplete is malformed")
    if observation_capture_incomplete is not execution["capture_incomplete"]:
        raise ValueError(
            "acquisition artifact capture_incomplete does not match the observation"
        )
    setup_error = execution["setup_error"]
    if setup_error is not None and (
        not isinstance(setup_error, str) or not setup_error
    ):
        raise ValueError("acquisition artifact setup_error is malformed")
    cleanup_errors = execution["cleanup_errors"]
    if not isinstance(cleanup_errors, list) or any(
        not isinstance(item, str) or not item for item in cleanup_errors
    ):
        raise ValueError("acquisition artifact cleanup_errors are malformed")
    environment_keys = execution["supplied_environment_keys"]
    expected_environment_keys = {
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "TZ",
        "TERM",
        "NO_COLOR",
        "PYTHONUNBUFFERED",
    }
    if os.name == "nt":  # pragma: no cover - platform-specific
        expected_environment_keys.add("USERPROFILE")
        expected_environment_keys.update(
            key
            for key in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT")
            if key in os.environ
        )
    environment_was_not_prepared = (
        setup_error is not None
        and return_code is None
        and environment_keys == []
    )
    if (
        environment_keys != sorted(expected_environment_keys)
        and not environment_was_not_prepared
    ):
        raise ValueError("acquisition artifact supplied environment keys are malformed")
    outcome = execution["outcome"]
    if not isinstance(outcome, str):
        raise ValueError("acquisition artifact outcome is malformed")
    status_by_outcome = {
        "supports_correct": EvidenceStatus.SUPPORTS_CORRECT,
        "supports_incorrect": EvidenceStatus.SUPPORTS_INCORRECT,
        "setup_failure": EvidenceStatus.INCONCLUSIVE,
        "timeout": EvidenceStatus.INCONCLUSIVE,
        "capture_or_cleanup_failure": EvidenceStatus.INCONCLUSIVE,
        "residual_process_group": EvidenceStatus.INCONCLUSIVE,
        "signaled": EvidenceStatus.INCONCLUSIVE,
        "unmapped_exit": EvidenceStatus.INCONCLUSIVE,
        "semantic_nonzero_exit": EvidenceStatus.INCONCLUSIVE,
        "semantic_truncated_output": EvidenceStatus.INCONCLUSIVE,
        "semantic_invalid_output": EvidenceStatus.INCONCLUSIVE,
    }
    if outcome != "semantic_result" and status_by_outcome.get(outcome) != observation.status:
        raise ValueError("acquisition artifact outcome does not match observation status")
    if outcome != observation.metadata.get("outcome"):
        raise ValueError("acquisition artifact outcome does not match observation metadata")

    capture_bindings = observation.metadata.get("capture_bindings")
    if not isinstance(capture_bindings, Mapping) or set(capture_bindings) != {
        "stdout",
        "stderr",
    }:
        raise ValueError("acquisition observation capture bindings are malformed")
    stream_fields = {
        "text",
        "encoding",
        "captured_bytes",
        "total_bytes",
        "truncated",
        "sha256",
        "read_error",
    }
    capture_binding_fields = {
        "captured_bytes",
        "total_bytes",
        "truncated",
        "sha256",
        "read_error",
    }
    capture_read_failed = False
    for stream_name in ("stdout", "stderr"):
        stream_data = raw[stream_name]
        if not isinstance(stream_data, dict) or set(stream_data) != stream_fields:
            raise ValueError(f"acquisition artifact {stream_name} capture is malformed")
        if stream_data["encoding"] != "utf-8-replace" or not isinstance(
            stream_data["text"], str
        ):
            raise ValueError(f"acquisition artifact {stream_name} encoding is malformed")
        for count_name in ("captured_bytes", "total_bytes"):
            count = stream_data[count_name]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(
                    f"acquisition artifact {stream_name} {count_name} is malformed"
                )
        if stream_data["captured_bytes"] != min(
            stream_data["total_bytes"],
            request.max_capture_bytes,
        ):
            raise ValueError(f"acquisition artifact {stream_name} capture bound is invalid")
        if not isinstance(stream_data["truncated"], bool) or (
            stream_data["truncated"]
            != (stream_data["total_bytes"] > request.max_capture_bytes)
        ):
            raise ValueError(f"acquisition artifact {stream_name} truncation is invalid")
        _sha256(stream_data["sha256"], f"acquisition artifact {stream_name} sha256")
        read_error = stream_data["read_error"]
        if read_error is not None and (
            not isinstance(read_error, str) or not read_error
        ):
            raise ValueError(f"acquisition artifact {stream_name} read_error is malformed")
        capture_read_failed = capture_read_failed or read_error is not None
        observation_truncated = observation.metadata.get(
            f"{stream_name}_truncated"
        )
        if not isinstance(observation_truncated, bool) or (
            observation_truncated is not stream_data["truncated"]
        ):
            raise ValueError(
                f"acquisition artifact {stream_name} truncation contradicts observation"
            )
        binding = capture_bindings[stream_name]
        if not isinstance(binding, Mapping) or set(binding) != capture_binding_fields:
            raise ValueError(
                f"acquisition observation {stream_name} capture binding is malformed"
            )
        for count_name in ("captured_bytes", "total_bytes"):
            bound_count = binding[count_name]
            if (
                isinstance(bound_count, bool)
                or not isinstance(bound_count, int)
                or bound_count < 0
            ):
                raise ValueError(
                    f"acquisition observation {stream_name} capture binding is malformed"
                )
        if not isinstance(binding["truncated"], bool):
            raise ValueError(
                f"acquisition observation {stream_name} capture binding is malformed"
            )
        _sha256(
            binding["sha256"],
            f"acquisition observation {stream_name} capture sha256",
        )
        bound_read_error = binding["read_error"]
        if bound_read_error is not None and (
            not isinstance(bound_read_error, str) or not bound_read_error
        ):
            raise ValueError(
                f"acquisition observation {stream_name} capture binding is malformed"
            )
        if any(
            type(binding[name]) is not type(stream_data[name])
            or binding[name] != stream_data[name]
            for name in capture_binding_fields
        ):
            raise ValueError(
                f"acquisition artifact {stream_name} capture contradicts observation"
            )

    expected_semantic_outcome: str | None = None
    if semantic:
        semantic_data = raw["semantic"]
        if not isinstance(semantic_data, dict) or set(semantic_data) != {
            "output_schema_version",
            "raw_stdout",
            "parsed",
            "error_code",
        }:
            raise ValueError("acquisition artifact semantic envelope is malformed")
        if semantic_data["output_schema_version"] != SEMANTIC_OUTPUT_SCHEMA_VERSION:
            raise ValueError("acquisition artifact semantic schema version does not match")
        raw_stdout = semantic_data["raw_stdout"]
        raw_stdout_fields = {
            "encoding",
            "data",
            "captured_bytes",
            "total_bytes",
            "truncated",
            "sha256",
        }
        if not isinstance(raw_stdout, dict) or set(raw_stdout) != raw_stdout_fields:
            raise ValueError("acquisition artifact semantic raw stdout is malformed")
        if raw_stdout["encoding"] != "base64" or not isinstance(
            raw_stdout["data"], str
        ):
            raise ValueError("acquisition artifact semantic raw stdout encoding is malformed")
        try:
            retained_stdout = base64.b64decode(
                raw_stdout["data"],
                validate=True,
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "acquisition artifact semantic raw stdout is not strict base64"
            ) from exc
        stdout_stream = raw["stdout"]
        if (
            raw_stdout["captured_bytes"] != len(retained_stdout)
            or raw_stdout["captured_bytes"] != stdout_stream["captured_bytes"]
            or raw_stdout["total_bytes"] != stdout_stream["total_bytes"]
            or raw_stdout["truncated"] is not stdout_stream["truncated"]
            or raw_stdout["sha256"] != stdout_stream["sha256"]
        ):
            raise ValueError(
                "acquisition artifact semantic raw stdout contradicts stream capture"
            )
        if not raw_stdout["truncated"] and raw_stdout["sha256"] != hashlib.sha256(
            retained_stdout
        ).hexdigest():
            raise ValueError(
                "acquisition artifact semantic raw stdout digest does not match "
                "retained bytes"
            )
        if not raw_stdout["truncated"] and stdout_stream["text"] != retained_stdout.decode(
            "utf-8",
            errors="replace",
        ):
            raise ValueError(
                "acquisition artifact semantic raw stdout contradicts captured text"
            )

        parsed_semantic = None
        semantic_error: str | None
        if setup_error is not None:
            semantic_error = "setup_failure"
            expected_semantic_outcome = "setup_failure"
        elif execution["timed_out"]:
            semantic_error = "timeout"
            expected_semantic_outcome = "timeout"
        elif execution["capture_incomplete"] or capture_read_failed or cleanup_errors:
            semantic_error = "capture_or_cleanup_failure"
            expected_semantic_outcome = "capture_or_cleanup_failure"
        elif execution["residual_process_group"]:
            semantic_error = "residual_process_group"
            expected_semantic_outcome = "residual_process_group"
        elif return_code is None or return_code < 0:
            semantic_error = "signaled"
            expected_semantic_outcome = "signaled"
        elif stdout_stream["truncated"] or raw["stderr"]["truncated"]:
            semantic_error = "capture_truncated"
            expected_semantic_outcome = "semantic_truncated_output"
        elif return_code != 0:
            semantic_error = "nonzero_exit"
            expected_semantic_outcome = "semantic_nonzero_exit"
        else:
            parsed_semantic, semantic_error = decode_semantic_output(retained_stdout)
            expected_semantic_outcome = (
                "semantic_result"
                if parsed_semantic is not None
                else "semantic_invalid_output"
            )
        expected_parsed = (
            parsed_semantic.to_dict() if parsed_semantic is not None else None
        )
        if semantic_data["parsed"] != expected_parsed:
            raise ValueError("acquisition artifact semantic parsed output does not match raw")
        if semantic_data["error_code"] != semantic_error:
            raise ValueError("acquisition artifact semantic error code does not match raw")
        if observation.metadata.get("semantic_output_schema_version") != (
            SEMANTIC_OUTPUT_SCHEMA_VERSION
        ):
            raise ValueError("semantic observation schema version does not match")
        if observation.metadata.get("semantic_output_sha256") != stdout_stream["sha256"]:
            raise ValueError("semantic observation output digest does not match")
        if observation.metadata.get("semantic_output_error") != semantic_error:
            raise ValueError("semantic observation error code does not match")
        if observation.metadata.get("semantic_output_valid") is not (
            parsed_semantic is not None
        ):
            raise ValueError("semantic observation validity flag does not match")

        expected_declared_dimensions: list[str] = []
        expected_declared_semantic_fields: tuple[str, ...] = ()
        if parsed_semantic is not None:
            expected_declared_semantic_fields = SEMANTIC_PRODUCER_DECLARED_FIELDS
            for name in ("input_tokens", "output_tokens", "usd"):
                if getattr(parsed_semantic, name) is not None:
                    expected_declared_dimensions.append(name)
            if observation.status != parsed_semantic.status:
                raise ValueError("semantic observation status does not match parsed output")
            if observation.candidate_probability != parsed_semantic.candidate_probability:
                raise ValueError(
                    "semantic observation candidate probability does not match"
                )
            if observation.calibrated_risk_upper_bound != (
                parsed_semantic.calibrated_risk_upper_bound
            ) or observation.calibration_id != parsed_semantic.calibration_id:
                raise ValueError("semantic observation calibration fields do not match")
            if observation.verifier_validity != parsed_semantic.verifier_validity:
                raise ValueError("semantic observation verifier validity does not match")
            if observation.privileged_inputs != parsed_semantic.privileged_inputs:
                raise ValueError("semantic observation privileged inputs do not match")
            if observation.cost.input_tokens != (parsed_semantic.input_tokens or 0):
                raise ValueError("semantic observation input-token cost does not match")
            if observation.cost.output_tokens != (parsed_semantic.output_tokens or 0):
                raise ValueError("semantic observation output-token cost does not match")
            if observation.cost.usd != (parsed_semantic.usd or 0.0):
                raise ValueError("semantic observation USD cost does not match")
        else:
            if observation.status != EvidenceStatus.INCONCLUSIVE:
                raise ValueError("failed semantic acquisition must be inconclusive")
            if (
                observation.candidate_probability is not None
                or observation.calibrated_risk_upper_bound is not None
                or observation.calibration_id
                or observation.privileged_inputs
            ):
                raise ValueError("failed semantic acquisition leaked scoring metadata")
            if observation.verifier_validity != 0.0:
                raise ValueError("failed semantic acquisition verifier validity must be zero")
            if any(
                (
                    observation.cost.input_tokens,
                    observation.cost.output_tokens,
                    observation.cost.usd,
                )
            ):
                raise ValueError("failed semantic acquisition leaked declared costs")
        declared_semantic_fields = observation.metadata.get(
            "producer_declared_semantic_fields"
        )
        if not isinstance(declared_semantic_fields, (list, tuple)) or tuple(
            declared_semantic_fields
        ) != expected_declared_semantic_fields:
            raise ValueError(
                "semantic observation producer-declared fields do not match"
            )
        declared_dimensions = observation.metadata.get(
            "producer_declared_cost_dimensions"
        )
        if not isinstance(declared_dimensions, (list, tuple)) or tuple(
            declared_dimensions
        ) != tuple(expected_declared_dimensions):
            raise ValueError(
                "semantic observation producer-declared cost dimensions do not match"
            )

    if setup_error is not None:
        empty_capture_sha256 = hashlib.sha256(b"").hexdigest()
        setup_has_process_state = (
            return_code is not None
            or execution["timed_out"]
            or execution["residual_process_group"]
            or execution["capture_incomplete"]
        )
        setup_has_capture = any(
            raw[stream_name]["text"] != ""
            or raw[stream_name]["captured_bytes"] != 0
            or raw[stream_name]["total_bytes"] != 0
            or raw[stream_name]["truncated"]
            or raw[stream_name]["sha256"] != empty_capture_sha256
            or raw[stream_name]["read_error"] is not None
            for stream_name in ("stdout", "stderr")
        )
        if setup_has_process_state or setup_has_capture:
            raise ValueError(
                "acquisition artifact setup failure contains launched-process state"
            )
    elif execution["timed_out"] and execution["residual_process_group"]:
        raise ValueError(
            "acquisition artifact timeout cannot also report a residual process group"
        )
    elif not execution["timed_out"] and return_code is None:
        raise ValueError(
            "acquisition artifact non-timeout execution is missing return_code"
        )

    if semantic:
        assert expected_semantic_outcome is not None
        expected_outcome = expected_semantic_outcome
    elif setup_error is not None:
        expected_outcome = "setup_failure"
    elif execution["timed_out"]:
        expected_outcome = "timeout"
    elif execution["capture_incomplete"] or capture_read_failed or cleanup_errors:
        expected_outcome = "capture_or_cleanup_failure"
    elif execution["residual_process_group"]:
        expected_outcome = "residual_process_group"
    elif return_code is not None and return_code < 0:
        expected_outcome = "signaled"
    elif return_code in request.supports_correct_exit_codes:
        expected_outcome = "supports_correct"
    elif return_code in request.supports_incorrect_exit_codes:
        expected_outcome = "supports_incorrect"
    else:
        expected_outcome = "unmapped_exit"
    if outcome != expected_outcome:
        raise ValueError("acquisition artifact execution outcome is internally inconsistent")
    return artifact


def _observation_with_route_provenance(
    observation: EvidenceObservation,
    *,
    manifest_sha256: str,
    decision: RouteDecision,
    decision_sha256: str,
    route_index: int,
    plan: RouteAcquisitionPlan,
    plan_sha256: str,
    request_sha256: str,
    prepared_at: str,
    prepared_envelope_sha256: str,
) -> EvidenceObservation:
    data = observation.to_dict()
    metadata = data["metadata"]
    if not isinstance(metadata, dict):  # pragma: no cover - model invariant
        raise ValueError("acquisition observation metadata is not a JSON object")
    if "route_provenance" in metadata:
        raise ValueError("acquisition observation already contains route provenance")
    metadata["route_provenance"] = {
        "orchestration_schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "manifest_sha256_before_acquisition": manifest_sha256,
        "route_history_index": route_index,
        "route_decision_sha256": decision_sha256,
        "route_action": decision.action.value,
        "policy_version": decision.policy_version,
        "expected_evidence_kind": observation.kind.value,
        "plan_sha256": plan_sha256,
        "request_sha256": request_sha256,
        "instance_id": plan.instance_id,
        "candidate_id": plan.candidate_id,
        "base_commit": plan.base_commit,
        "workspace_id": plan.workspace_id,
        "workspace_identity_sha256": plan.workspace_identity_sha256,
        "acquisition_id": plan.acquisition_id,
        "prepared_at": prepared_at,
        "prepared_envelope_sha256": prepared_envelope_sha256,
        "attempt_semantics": ATTEMPT_SEMANTICS,
        "attempt_scope": ATTEMPT_SCOPE,
        "workspace_identity_scope": WORKSPACE_IDENTITY_SCOPE,
        "execution_backend": EXECUTION_BACKEND,
        "detached_child_containment": DETACHED_CHILD_CONTAINMENT,
    }
    return EvidenceObservation.from_dict(data)


def validate_completed_route_acquisition(
    record: Mapping[str, Any],
    *,
    manifest_before: ValidityManifest,
    decision: RouteDecision,
    plan: RouteAcquisitionPlan,
) -> RouteAcquisitionResult:
    """Revalidate and load one exact completed acquisition without executing.

    The three keyword arguments are independently retained preimages.  A record
    that merely recomputes its own internal hashes is insufficient: it must also
    match those preimages, the prepared write-ahead envelope, the raw acquisition
    artifact, the route provenance, and the one-observation manifest successor.
    """

    if not isinstance(record, dict):
        raise ValueError("completed orchestration record must be a JSON object")
    fields = {
        "schema_version",
        "state",
        "orchestrator",
        "attempt_semantics",
        "attempt_scope",
        "workspace_identity_scope",
        "prepared",
        "acquisition_id",
        "plan_sha256",
        "plan",
        "request_sha256",
        "manifest_sha256_before",
        "manifest_sha256_after",
        "route",
        "workspace",
        "observation",
        "manifest",
    }
    _exact_object(record, fields, "completed orchestration record")
    if record["schema_version"] != ORCHESTRATION_SCHEMA_VERSION:
        raise ValueError("completed orchestration schema version does not match")
    if record["state"] != "completed":
        raise ValueError("completed orchestration record has the wrong state")
    if record["orchestrator"] != _orchestrator_contract():
        raise ValueError("completed orchestration runner contract does not match")
    if (
        record["attempt_semantics"] != ATTEMPT_SEMANTICS
        or record["attempt_scope"] != ATTEMPT_SCOPE
        or record["workspace_identity_scope"] != WORKSPACE_IDENTITY_SCOPE
    ):
        raise ValueError("completed orchestration attempt contract does not match")
    if not isinstance(manifest_before, ValidityManifest):
        raise ValueError("manifest_before must be a ValidityManifest")
    if not isinstance(decision, RouteDecision):
        raise ValueError("decision must be a RouteDecision")
    if not isinstance(plan, RouteAcquisitionPlan):
        raise ValueError("plan must be a RouteAcquisitionPlan")

    recorded_plan = RouteAcquisitionPlan.from_dict(record["plan"])
    plan_dict = plan.to_dict()
    if recorded_plan.to_dict() != plan_dict:
        raise ValueError("completed orchestration plan differs from retained preimage")
    plan_sha256 = _canonical_sha256(plan_dict)
    if _sha256(record["plan_sha256"], "record.plan_sha256") != plan_sha256:
        raise ValueError("completed orchestration plan digest does not match")

    (
        manifest_sha256,
        decision_sha256,
        route_index,
        request,
    ) = _validate_manifest_and_route(manifest_before, decision, plan)
    request_dict = request.to_dict()
    request_sha256 = _canonical_sha256(request_dict)
    if (
        record["acquisition_id"] != plan.acquisition_id
        or _sha256(
            record["request_sha256"],
            "record.request_sha256",
        )
        != request_sha256
        or _sha256(
            record["manifest_sha256_before"],
            "record.manifest_sha256_before",
        )
        != manifest_sha256
    ):
        raise ValueError("completed orchestration input identity does not match")

    root = _resolve_workspace(plan)
    _workspace_marker(plan, manifest_before, root)
    coordination = pathlib.Path(plan.coordination_directory)
    if coordination.is_symlink():
        raise ValueError("coordination_directory cannot be a symbolic link")
    resolved_coordination = coordination.resolve(strict=True)
    if resolved_coordination != coordination or not coordination.is_dir():
        raise ValueError("coordination_directory is not the retained canonical directory")

    route_payload = {
        "history_index": route_index,
        "decision_sha256": decision_sha256,
        "decision": _decision_dict(decision),
    }
    workspace_payload = {
        "root": str(root),
        "workspace_id": plan.workspace_id,
        "identity_path": plan.workspace_identity_path,
        "identity_sha256": plan.workspace_identity_sha256,
        "base_commit": plan.base_commit,
        "candidate_id": plan.candidate_id,
        "identity_scope": WORKSPACE_IDENTITY_SCOPE,
    }
    prepared = _exact_object(
        record["prepared"],
        {"envelope", "envelope_sha256", "record_sha256"},
        "completed orchestration prepared record",
    )
    envelope = _exact_object(
        prepared["envelope"],
        {
            "schema_version",
            "state",
            "prepared_at",
            "orchestrator",
            "attempt_semantics",
            "attempt_scope",
            "workspace_identity_scope",
            "acquisition_id",
            "plan_sha256",
            "plan",
            "request_sha256",
            "manifest_sha256_before",
            "coordination",
            "route",
            "workspace",
            "request",
        },
        "completed orchestration prepared envelope",
    )
    _strict_utc_timestamp(envelope["prepared_at"], "prepared.envelope.prepared_at")
    decision_key = _canonical_sha256({
        "manifest_sha256": manifest_sha256,
        "route_history_index": route_index,
        "route_decision_sha256": decision_sha256,
    })
    expected_envelope = {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "state": "prepared",
        "prepared_at": envelope["prepared_at"],
        "orchestrator": _orchestrator_contract(),
        "attempt_semantics": ATTEMPT_SEMANTICS,
        "attempt_scope": ATTEMPT_SCOPE,
        "workspace_identity_scope": WORKSPACE_IDENTITY_SCOPE,
        "acquisition_id": plan.acquisition_id,
        "plan_sha256": plan_sha256,
        "plan": plan_dict,
        "request_sha256": request_sha256,
        "manifest_sha256_before": manifest_sha256,
        "coordination": {
            "directory": str(resolved_coordination),
            "decision_key": decision_key,
        },
        "route": route_payload,
        "workspace": workspace_payload,
        "request": request_dict,
    }
    if envelope != expected_envelope:
        raise ValueError("prepared orchestration envelope differs from retained preimages")
    prepared_envelope_sha256 = _canonical_sha256(envelope)
    if _sha256(
        prepared["envelope_sha256"],
        "prepared.envelope_sha256",
    ) != prepared_envelope_sha256:
        raise ValueError("prepared orchestration envelope digest does not match")
    prepared_text = strict_json_dumps(envelope, indent=2) + "\n"
    if _sha256(
        prepared["record_sha256"],
        "prepared.record_sha256",
    ) != hashlib.sha256(prepared_text.encode("utf-8")).hexdigest():
        raise ValueError("prepared orchestration record digest does not match")
    if record["route"] != route_payload or record["workspace"] != workspace_payload:
        raise ValueError("completed route/workspace projection differs from prepared intent")

    observation = EvidenceObservation.from_dict(record["observation"])
    if record["observation"] != observation.to_dict():
        raise ValueError("completed observation is not in canonical full form")
    route_provenance = observation.metadata.get("route_provenance")
    expected_route_provenance = {
        "orchestration_schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "manifest_sha256_before_acquisition": manifest_sha256,
        "route_history_index": route_index,
        "route_decision_sha256": decision_sha256,
        "route_action": decision.action.value,
        "policy_version": decision.policy_version,
        "expected_evidence_kind": observation.kind.value,
        "plan_sha256": plan_sha256,
        "request_sha256": request_sha256,
        "instance_id": plan.instance_id,
        "candidate_id": plan.candidate_id,
        "base_commit": plan.base_commit,
        "workspace_id": plan.workspace_id,
        "workspace_identity_sha256": plan.workspace_identity_sha256,
        "acquisition_id": plan.acquisition_id,
        "prepared_at": envelope["prepared_at"],
        "prepared_envelope_sha256": prepared_envelope_sha256,
        "attempt_semantics": ATTEMPT_SEMANTICS,
        "attempt_scope": ATTEMPT_SCOPE,
        "workspace_identity_scope": WORKSPACE_IDENTITY_SCOPE,
        "execution_backend": EXECUTION_BACKEND,
        "detached_child_containment": DETACHED_CHILD_CONTAINMENT,
    }
    if route_provenance != expected_route_provenance:
        raise ValueError("completed observation route provenance does not match")
    raw_observation_data = observation.to_dict()
    raw_metadata = raw_observation_data["metadata"]
    assert isinstance(raw_metadata, dict)
    raw_metadata.pop("route_provenance")
    raw_observation = EvidenceObservation.from_dict(raw_observation_data)
    artifact_path = verify_acquisition_artifact(
        raw_observation,
        request,
        pathlib.Path(plan.artifact_directory),
        plan.acquisition_id,
        request_sha256,
        root,
    )

    updated_manifest = ValidityManifest.from_dict(record["manifest"])
    if record["manifest"] != updated_manifest.to_dict():
        raise ValueError("completed manifest is not in canonical full form")
    expected_manifest = ValidityManifest.from_dict(manifest_before.to_dict())
    expected_manifest.add_evidence(observation)
    if updated_manifest.to_dict() != expected_manifest.to_dict():
        raise ValueError("completed manifest is not the exact one-observation successor")
    manifest_sha256_after = updated_manifest.canonical_digest()
    if _sha256(
        record["manifest_sha256_after"],
        "record.manifest_sha256_after",
    ) != manifest_sha256_after:
        raise ValueError("completed manifest digest does not match")

    output = pathlib.Path(plan.output_path)
    if output.is_symlink():
        raise ValueError("completed orchestration output cannot be a symbolic link")
    resolved_output = output.resolve(strict=True)
    if resolved_output != output or not output.is_file():
        raise ValueError("completed orchestration output is not the retained canonical file")
    canonical_text = strict_json_dumps(record, indent=2) + "\n"
    canonical_bytes = canonical_text.encode("utf-8")
    if len(canonical_bytes) > MAX_ORCHESTRATION_RECORD_BYTES:
        raise ValueError("completed orchestration output exceeds the bounded envelope")
    with output.open("rb") as stream:
        durable_bytes = stream.read(MAX_ORCHESTRATION_RECORD_BYTES + 1)
    if durable_bytes != canonical_bytes:
        raise ValueError("completed orchestration durable output differs from loaded record")
    expected_artifact_sha256 = _sha256(
        raw_observation.metadata.get("artifact_sha256"),
        "observation artifact_sha256",
    )
    if (
        artifact_path.is_symlink()
        or not artifact_path.is_file()
        or _file_sha256(artifact_path) != expected_artifact_sha256
    ):
        raise ValueError("acquisition artifact changed during completed-output validation")
    return RouteAcquisitionResult(
        manifest=updated_manifest,
        observation=observation,
        output_path=output,
        output_sha256=hashlib.sha256(durable_bytes).hexdigest(),
        manifest_sha256_before=manifest_sha256,
        manifest_sha256_after=manifest_sha256_after,
        plan_sha256=plan_sha256,
        route_decision_sha256=decision_sha256,
        prepared_at=envelope["prepared_at"],
        prepared_envelope_sha256=prepared_envelope_sha256,
    )


def _file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _orchestrator_contract() -> dict[str, str]:
    return {
        "name": "bench-cleanser-route-acquisition",
        "version": __version__,
        "sandbox": "not_provided",
        "execution_backend": EXECUTION_BACKEND,
        "detached_child_containment": DETACHED_CHILD_CONTAINMENT,
        "attempt_semantics": ATTEMPT_SEMANTICS,
        "attempt_scope": ATTEMPT_SCOPE,
        "workspace_identity_scope": WORKSPACE_IDENTITY_SCOPE,
    }


@dataclass(frozen=True)
class _OwnedReservation:
    path: pathlib.Path
    device: int
    inode: int

    def release(self) -> None:
        try:
            current = self.path.stat(follow_symlinks=False)
        except FileNotFoundError as exc:
            raise OSError("coordination reservation disappeared before release") from exc
        if (current.st_dev, current.st_ino) != (self.device, self.inode):
            raise OSError("coordination reservation identity changed before release")
        self.path.unlink()
        if os.name != "nt":
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)


def _reserve_file(
    path: pathlib.Path,
    payload: Mapping[str, Any],
    *,
    conflict_message: str,
) -> _OwnedReservation:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as exc:
        raise FileExistsError(conflict_message) from exc
    reservation_stat = os.fstat(descriptor)
    reservation = _OwnedReservation(
        path=path,
        device=reservation_stat.st_dev,
        inode=reservation_stat.st_ino,
    )
    try:
        encoded = strict_json_dumps(dict(payload)).encode("utf-8") + b"\n"
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        reservation.release()
        raise
    else:
        os.close(descriptor)
    try:
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except BaseException:
        reservation.release()
        raise
    return reservation


def _reserve_output(
    output: pathlib.Path,
    *,
    acquisition_id: str,
    plan_sha256: str,
) -> _OwnedReservation:
    lock = output.parent / f".{output.name}.lock"
    reservation = _reserve_file(
        lock,
        {
            "acquisition_id": acquisition_id,
            "plan_sha256": plan_sha256,
        },
        conflict_message="orchestration output is already reserved",
    )
    if output.exists():
        reservation.release()
        raise FileExistsError("orchestration output appeared while reserving it")
    return reservation


def _atomic_create(path: pathlib.Path, content: str) -> None:
    """Atomically publish complete UTF-8 text without replacing an existing path."""

    if not isinstance(content, str):
        raise TypeError("_atomic_create content must be text")
    temporary: pathlib.Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = pathlib.Path(handle.name)
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(
                "orchestration output appeared before prepared intent publication"
            ) from exc
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
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


def _resolve_coordination_paths(
    plan: RouteAcquisitionPlan,
    workspace_root: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    declared_coordination = pathlib.Path(plan.coordination_directory)
    try:
        coordination = declared_coordination.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("coordination_directory must already exist") from exc
    if declared_coordination != coordination:
        raise ValueError("coordination_directory must be a canonical physical path")
    if not coordination.is_dir():
        raise ValueError("coordination_directory must resolve to a directory")
    try:
        coordination.relative_to(workspace_root)
    except ValueError:
        pass
    else:
        raise ValueError("coordination_directory must be outside workspace_root")
    try:
        workspace_root.relative_to(coordination)
    except ValueError:
        pass
    else:
        raise ValueError(
            "coordination_directory and workspace_root must be disjoint trees"
        )
    declared_artifacts = pathlib.Path(plan.artifact_directory)
    declared_output = pathlib.Path(plan.output_path)
    artifacts = declared_artifacts.resolve(strict=False)
    output = declared_output.resolve(strict=False)
    for declared, path, name in (
        (declared_artifacts, artifacts, "artifact_directory"),
        (declared_output, output, "output_path"),
    ):
        if declared != path:
            raise ValueError(f"{name} must be a canonical physical path")
        if path == coordination:
            raise ValueError(f"{name} must be below coordination_directory")
        try:
            path.relative_to(coordination)
        except ValueError as exc:
            raise ValueError(f"{name} must be under coordination_directory") from exc
    if artifacts.exists() and not artifacts.is_dir():
        raise ValueError("artifact_directory must resolve to a directory")
    artifacts.mkdir(parents=True, exist_ok=True)
    if artifacts.resolve(strict=True) != artifacts:
        raise ValueError("artifact_directory changed while being prepared")
    return coordination, artifacts, output


def execute_route_acquisition(
    manifest: ValidityManifest,
    decision: RouteDecision,
    plan: RouteAcquisitionPlan,
) -> RouteAcquisitionResult:
    """Attempt the exact recorded action and durably emit an updated manifest.

    All identity and mapping checks occur before execution.  A durable prepared
    record containing the selected request and preallocated acquisition ID is
    written before the subprocess starts.  The caller's manifest is never
    mutated; a validated clone appears only in the completed durable output.
    If a post-execution check fails, the prepared record and raw acquisition
    artifact remain for diagnosis, but no completed updated manifest is emitted
    and callers sharing the decision-key coordination directory, output path,
    or artifact path and ID cannot silently rerun it. This is scoped
    at-most-once exclusion, not recovery or exactly-once execution.
    """

    (
        manifest_sha256,
        decision_sha256,
        route_index,
        request,
    ) = _validate_manifest_and_route(manifest, decision, plan)
    root = _resolve_workspace(plan)
    marker = _workspace_marker(plan, manifest, root)
    coordination, artifacts, output = _resolve_coordination_paths(plan, root)
    if output.exists():
        raise ValueError("orchestration output already exists")
    if output == marker:
        raise ValueError("orchestration output cannot replace the workspace identity marker")
    if output == artifacts / f"{plan.acquisition_id}.json":
        raise ValueError("orchestration output cannot replace the acquisition artifact")

    plan_dict = plan.to_dict()
    plan_sha256 = _canonical_sha256(plan_dict)
    request_sha256 = _canonical_sha256(request.to_dict())
    working_manifest = ValidityManifest.from_dict(manifest.to_dict())
    prepared_at = _utc_timestamp()
    decision_key = _canonical_sha256({
        "manifest_sha256": manifest_sha256,
        "route_history_index": route_index,
        "route_decision_sha256": decision_sha256,
    })
    prepared_payload = {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "state": "prepared",
        "prepared_at": prepared_at,
        "orchestrator": _orchestrator_contract(),
        "attempt_semantics": ATTEMPT_SEMANTICS,
        "attempt_scope": ATTEMPT_SCOPE,
        "workspace_identity_scope": WORKSPACE_IDENTITY_SCOPE,
        "acquisition_id": plan.acquisition_id,
        "plan_sha256": plan_sha256,
        "plan": plan_dict,
        "request_sha256": request_sha256,
        "manifest_sha256_before": manifest_sha256,
        "coordination": {
            "directory": str(coordination),
            "decision_key": decision_key,
        },
        "route": {
            "history_index": route_index,
            "decision_sha256": decision_sha256,
            "decision": _decision_dict(decision),
        },
        "workspace": {
            "root": str(root),
            "workspace_id": plan.workspace_id,
            "identity_path": plan.workspace_identity_path,
            "identity_sha256": plan.workspace_identity_sha256,
            "base_commit": plan.base_commit,
            "candidate_id": plan.candidate_id,
            "identity_scope": WORKSPACE_IDENTITY_SCOPE,
        },
        "request": request.to_dict(),
    }
    prepared_envelope_sha256 = _canonical_sha256(prepared_payload)
    prepared_text = strict_json_dumps(prepared_payload, indent=2) + "\n"
    prepared_record_sha256 = hashlib.sha256(prepared_text.encode("utf-8")).hexdigest()

    decision_reservation = _reserve_file(
        coordination / f".decision-{decision_key}.lock",
        {
            "acquisition_id": plan.acquisition_id,
            "manifest_sha256": manifest_sha256,
            "route_history_index": route_index,
            "route_decision_sha256": decision_sha256,
            "plan_sha256": plan_sha256,
            "attempt_semantics": ATTEMPT_SEMANTICS,
            "attempt_scope": ATTEMPT_SCOPE,
        },
        conflict_message="route decision is already reserved in coordination_directory",
    )
    output_reservation: _OwnedReservation | None = None
    try:
        output_reservation = _reserve_output(
            output,
            acquisition_id=plan.acquisition_id,
            plan_sha256=plan_sha256,
        )
        output_reservation_sha256 = _file_sha256(output_reservation.path)
        decision_reservation_sha256 = _file_sha256(decision_reservation.path)
        _atomic_create(output, prepared_text)
    except BaseException:
        try:
            if output_reservation is not None:
                output_reservation.release()
        finally:
            decision_reservation.release()
        raise

    observation = acquire_evidence(
        request,
        artifact_directory=artifacts,
        acquisition_id=plan.acquisition_id,
    )
    verify_acquisition_artifact(
        observation,
        request,
        artifacts,
        plan.acquisition_id,
        request_sha256,
        root,
    )
    for path, name in (
        (coordination, "coordination_directory"),
        (output, "orchestration output"),
    ):
        try:
            resolved_path = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"{name} disappeared during acquisition") from exc
        if path.is_symlink() or resolved_path != path:
            raise ValueError(f"{name} changed during acquisition")
    # The command is not sandboxed and could modify the marker.  Re-verify it
    # before binding the observation to this workspace identity.
    _workspace_marker(plan, manifest, root)
    if manifest.canonical_digest() != manifest_sha256:
        raise ValueError("input manifest changed during acquisition")
    if _canonical_sha256(plan.to_dict()) != plan_sha256:
        raise ValueError("operator plan changed during acquisition")
    if not output.is_file() or _file_sha256(output) != prepared_record_sha256:
        raise ValueError("prepared orchestration record changed during acquisition")
    if (
        not output_reservation.path.is_file()
        or _file_sha256(output_reservation.path) != output_reservation_sha256
    ):
        raise ValueError("orchestration output reservation changed during acquisition")
    if (
        not decision_reservation.path.is_file()
        or _file_sha256(decision_reservation.path)
        != decision_reservation_sha256
    ):
        raise ValueError("route-decision reservation changed during acquisition")

    routed_observation = _observation_with_route_provenance(
        observation,
        manifest_sha256=manifest_sha256,
        decision=decision,
        decision_sha256=decision_sha256,
        route_index=route_index,
        plan=plan,
        plan_sha256=plan_sha256,
        request_sha256=request_sha256,
        prepared_at=prepared_at,
        prepared_envelope_sha256=prepared_envelope_sha256,
    )
    working_manifest.add_evidence(routed_observation)
    manifest_sha256_after = working_manifest.canonical_digest()
    payload = {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "state": "completed",
        "orchestrator": _orchestrator_contract(),
        "attempt_semantics": ATTEMPT_SEMANTICS,
        "attempt_scope": ATTEMPT_SCOPE,
        "workspace_identity_scope": WORKSPACE_IDENTITY_SCOPE,
        "prepared": {
            "envelope": prepared_payload,
            "envelope_sha256": prepared_envelope_sha256,
            "record_sha256": prepared_record_sha256,
        },
        "acquisition_id": plan.acquisition_id,
        "plan_sha256": plan_sha256,
        "plan": plan_dict,
        "request_sha256": request_sha256,
        "manifest_sha256_before": manifest_sha256,
        "manifest_sha256_after": manifest_sha256_after,
        "route": {
            "history_index": route_index,
            "decision_sha256": decision_sha256,
            "decision": _decision_dict(decision),
        },
        "workspace": {
            "root": str(root),
            "workspace_id": plan.workspace_id,
            "identity_path": plan.workspace_identity_path,
            "identity_sha256": plan.workspace_identity_sha256,
            "base_commit": plan.base_commit,
            "candidate_id": plan.candidate_id,
            "identity_scope": WORKSPACE_IDENTITY_SCOPE,
        },
        "observation": routed_observation.to_dict(),
        "manifest": working_manifest.to_dict(),
    }
    rendered = strict_json_dumps(payload, indent=2) + "\n"
    output_bytes = rendered.encode("utf-8")
    atomic_write(output, rendered)
    output_reservation.release()
    return RouteAcquisitionResult(
        manifest=working_manifest,
        observation=routed_observation,
        output_path=output,
        output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        manifest_sha256_before=manifest_sha256,
        manifest_sha256_after=manifest_sha256_after,
        plan_sha256=plan_sha256,
        route_decision_sha256=decision_sha256,
        prepared_at=prepared_at,
        prepared_envelope_sha256=prepared_envelope_sha256,
    )
