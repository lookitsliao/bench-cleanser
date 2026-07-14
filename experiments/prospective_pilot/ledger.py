"""Durable append-only scheduler ledger for the prospective pilot.

This module implements a single-host SQLite durability boundary.  It does not
activate the study: repository source bindings, execution registries, reviewer
attestations, and external producer identities remain protocol concerns.  The
ledger's narrower job is to make one already-validated scheduler trajectory
durable before dispatch and to prevent ambiguous work from being dispatched a
second time.

Every writer uses ``BEGIN IMMEDIATE`` with SQLite's rollback journal,
``synchronous=FULL``, and foreign-key enforcement.  Claims are permanent: there
is deliberately no lease, expiry, heartbeat, or claim-stealing operation.  If a
worker disappears after claiming an acquisition, an operator may either ingest
the exact completed output or append a task-halting incident; automatic replay
is forbidden.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import pathlib
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)
from bench_cleanser.verification.orchestrate import (
    RouteAcquisitionPlan,
    load_route_acquisition_record,
    validate_completed_route_acquisition,
)
from bench_cleanser.verification.policy_log import (
    LoggedPolicyDecision,
    RouterStateView,
    canonical_action_spec_sha256,
)
from experiments.prospective_pilot.scheduler import (
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    validate_task_round_chain,
    validate_task_trajectory,
)

LEDGER_SCHEMA_VERSION = "prospective-pilot-ledger-0.1.0"
EXPORT_SCHEMA_VERSION = "prospective-pilot-ledger-export-0.1.0"
EXECUTABLE_ACTION_SPEC_SCHEMA_VERSION = (
    "prospective-pilot-executable-action-spec-0.1.0"
)
PROVISIONING_RECEIPT_SCHEMA_VERSION = (
    "prospective-pilot-provisioning-receipt-0.1.0"
)
ARTIFACT_RETENTION_SCHEMA_VERSION = (
    "prospective-pilot-artifact-retention-0.1.0"
)
PLAN_ACQUISITION_ID_PLACEHOLDER = "${ACQUISITION_ID}"
_PLAN_PLACEHOLDER_ACQUISITION_ID = "acq-" + "0" * 32
EVENT_CHAIN_CONTRACT = "bench-cleanser-prospective-ledger-event-chain-v1"
EXPORT_CHAIN_CONTRACT = "bench-cleanser-prospective-ledger-export-chain-v1"
PROTOCOL_RESULT_VALIDATION_CONTRACT = (
    "bench_cleanser.verification.orchestrate."
    "validate_completed_route_acquisition"
)
_TEST_ONLY_RESULT_VALIDATION_CONTRACT = "test_only_synthetic_result"
EVENT_GENESIS_SHA256 = hashlib.sha256(
    f"{EVENT_CHAIN_CONTRACT}:genesis".encode()
).hexdigest()
EXPORT_GENESIS_SHA256 = hashlib.sha256(
    f"{EXPORT_CHAIN_CONTRACT}:genesis".encode()
).hexdigest()

_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_ACQUISITION_RE = re.compile(r"acq-[0-9a-f]{32}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_REASON_RE = re.compile(r"[a-z][a-z0-9_]{0,127}\Z")
_SECRET_VALUE_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/-]{12,}|\bsk-[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)
_SECRET_KEY_FINGERPRINTS = {
    "accesstoken",
    "apikey",
    "authorization",
    "authtoken",
    "bearertoken",
    "clientsecret",
    "credentialvalue",
    "password",
    "secret",
    "token",
}

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
_TABLE_PRIMARY_KEYS = {
    "ledger_meta": "meta_key",
    "action_specs": "action_spec_sha256",
    "rounds": "round_sha256",
    "policy_decisions": "decision_id",
    "dispatch_intents": "dispatch_id",
    "resource_reservations": "reservation_id",
    "claims": "claim_id",
    "results": "result_id",
    "incidents": "incident_id",
    "selections": "selection_sha256",
    "events": "event_sequence",
}


def _ordered_record_key(table: str, value: Any) -> str:
    if table == "events":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise LedgerError("event export key must be a non-negative integer")
        return f"{value:020d}"
    return str(value)


class LedgerError(ValueError):
    """Base class for fail-closed ledger errors."""


class LedgerConflict(LedgerError):
    """An immutable identity already exists with different content."""


class RoundNotReady(LedgerError):
    """A successor round was offered before every sibling result existed."""


class TaskHalted(LedgerError):
    """The task has an append-only halt incident and cannot advance."""


def _canonical_json(value: Any, field_name: str) -> tuple[str, Any]:
    try:
        rendered = strict_json_dumps(value)
        decoded = strict_json_loads(rendered)
    except (TypeError, ValueError) as exc:
        raise LedgerError(f"{field_name} must be strict canonical JSON: {exc}") from exc
    return rendered, decoded


def _canonical_object(value: Any, field_name: str) -> tuple[str, dict[str, Any]]:
    rendered, decoded = _canonical_json(value, field_name)
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) for key in decoded
    ):
        raise LedgerError(f"{field_name} must be a JSON object")
    return rendered, cast(dict[str, Any], decoded)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    rendered, _ = _canonical_json(value, "digest payload")
    return _sha256_bytes(rendered.encode("utf-8"))


def _digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise LedgerError(f"{field_name} must be a lowercase SHA-256")
    return value


def _acquisition_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _ACQUISITION_RE.fullmatch(value) is None:
        raise LedgerError(
            f"{field_name} must be 'acq-' plus 32 lowercase hexadecimal characters"
        )
    return value


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise LedgerError(f"{field_name} must be a canonical identifier")
    return value


def _reason(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _REASON_RE.fullmatch(value) is None:
        raise LedgerError(f"{field_name} must be a canonical reason code")
    return value


def _timestamp(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise LedgerError(f"{field_name} must be a canonical UTC timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=UTC
        )
    except ValueError as exc:
        raise LedgerError(
            f"{field_name} must use YYYY-MM-DDTHH:MM:SS.ffffffZ"
        ) from exc
    canonical = parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if canonical != value:
        raise LedgerError(f"{field_name} is not canonical UTC")
    return canonical


def _record(value: Mapping[str, Any], field_name: str) -> tuple[str, str]:
    rendered, _ = _canonical_object(dict(value), field_name)
    return rendered, _sha256_bytes(rendered.encode("utf-8"))


def _router_observation_projection(
    observation: EvidenceObservation,
) -> EvidenceObservation:
    """Match ``RouterStateView.from_manifest``'s deployable evidence view."""

    value = observation.to_dict()
    value["metadata"] = {}
    return EvidenceObservation.from_dict(value)


def _reject_credential_material(value: Any, field_name: str) -> None:
    """Allow credential names/handles while rejecting persisted secret values."""

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise LedgerError(f"{field_name} contains a non-string key")
            fingerprint = re.sub(r"[^a-z0-9]+", "", key.casefold())
            if fingerprint in _SECRET_KEY_FINGERPRINTS:
                raise LedgerError(
                    f"{field_name} contains secret-bearing key {key!r}; use "
                    "credential_names with names/handles only"
                )
            _reject_credential_material(item, f"{field_name}[{key!r}]")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_credential_material(item, f"{field_name}[{index}]")
        return
    if isinstance(value, str) and _SECRET_VALUE_RE.search(value):
        raise LedgerError(f"{field_name} appears to contain credential material")


def _decode_record(value: str, field_name: str) -> dict[str, Any]:
    try:
        decoded = strict_json_loads(value)
    except ValueError as exc:
        raise LedgerError(f"{field_name} is invalid strict JSON: {exc}") from exc
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) for key in decoded
    ):
        raise LedgerError(f"{field_name} must decode to an object")
    if strict_json_dumps(decoded) != value:
        raise LedgerError(f"{field_name} is not canonical JSON")
    return cast(dict[str, Any], decoded)


def _exact_object(
    value: Any,
    expected: set[str],
    field_name: str,
) -> dict[str, Any]:
    _, decoded = _canonical_object(value, field_name)
    actual = set(decoded)
    if actual != expected:
        raise LedgerError(
            f"{field_name} fields differ: "
            f"missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )
    return decoded


def _plain_string(value: Any, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise LedgerError(
            f"{field_name} must be nonempty and free of control whitespace"
        )
    return value


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise LedgerError(f"{field_name} must be a JSON boolean")
    return value


def _candidate_id(value: Any, field_name: str) -> str:
    candidate = _plain_string(value, field_name)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", candidate):
        raise LedgerError(f"{field_name} must be a lowercase sha256 identity")
    return candidate


def _base_commit(value: Any, field_name: str) -> str:
    commit = _plain_string(value, field_name)
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise LedgerError(f"{field_name} must be a 40- or 64-character commit digest")
    return commit


def _optional_image_digest(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    image = _plain_string(value, field_name)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise LedgerError(f"{field_name} must be null or a sha256 image digest")
    return image


def _value_occurrences(value: Any, target: str) -> int:
    if isinstance(value, dict):
        return sum(_value_occurrences(item, target) for item in value.values())
    if isinstance(value, list):
        return sum(_value_occurrences(item, target) for item in value)
    return int(value == target)


@dataclass(frozen=True)
class ProvisioningReceipt:
    """Credential-free identity of the workspace and execution substrate."""

    provisioner_id: str
    provisioner_version: str
    receipt_sha256: str
    workspace_id: str
    workspace_identity_sha256: str
    base_commit: str
    candidate_id: str
    architecture: str
    substrate: str
    harness_sha256: str
    image_digest: str | None
    dependency_lock_sha256: str
    execution_spec_sha256: str
    test_spec_sha256: str
    clean_start: bool
    fresh_worktree: bool
    credential_names: tuple[str, ...] = ()
    schema_version: str = PROVISIONING_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROVISIONING_RECEIPT_SCHEMA_VERSION:
            raise LedgerError("unsupported provisioning-receipt schema version")
        for name in ("provisioner_id", "provisioner_version"):
            _identifier(getattr(self, name), f"provisioning_receipt.{name}")
        for name in (
            "receipt_sha256",
            "workspace_identity_sha256",
            "harness_sha256",
            "dependency_lock_sha256",
            "execution_spec_sha256",
            "test_spec_sha256",
        ):
            _digest(getattr(self, name), f"provisioning_receipt.{name}")
        _identifier(self.workspace_id, "provisioning_receipt.workspace_id")
        _base_commit(self.base_commit, "provisioning_receipt.base_commit")
        _candidate_id(self.candidate_id, "provisioning_receipt.candidate_id")
        _identifier(self.architecture, "provisioning_receipt.architecture")
        _identifier(self.substrate, "provisioning_receipt.substrate")
        _optional_image_digest(
            self.image_digest,
            "provisioning_receipt.image_digest",
        )
        _boolean(self.clean_start, "provisioning_receipt.clean_start")
        _boolean(self.fresh_worktree, "provisioning_receipt.fresh_worktree")
        if not self.clean_start:
            raise LedgerError("executable action specs require clean-start provisioning")
        if not isinstance(self.credential_names, (list, tuple)):
            raise LedgerError("provisioning credential_names must be a sequence")
        credentials = tuple(
            _identifier(item, f"provisioning_receipt.credential_names[{index}]")
            for index, item in enumerate(self.credential_names)
        )
        if len(credentials) != len(set(credentials)):
            raise LedgerError("provisioning credential_names cannot repeat")
        object.__setattr__(self, "credential_names", credentials)
        if self.receipt_sha256 != _canonical_sha256(self._identity_payload()):
            raise LedgerError(
                "provisioning receipt digest differs from its exact identity payload"
            )

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provisioner_id": self.provisioner_id,
            "provisioner_version": self.provisioner_version,
            "workspace_id": self.workspace_id,
            "workspace_identity_sha256": self.workspace_identity_sha256,
            "base_commit": self.base_commit,
            "candidate_id": self.candidate_id,
            "architecture": self.architecture,
            "substrate": self.substrate,
            "harness_sha256": self.harness_sha256,
            "image_digest": self.image_digest,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "execution_spec_sha256": self.execution_spec_sha256,
            "test_spec_sha256": self.test_spec_sha256,
            "clean_start": self.clean_start,
            "fresh_worktree": self.fresh_worktree,
            "credential_names": list(self.credential_names),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._identity_payload(),
            "receipt_sha256": self.receipt_sha256,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ProvisioningReceipt:
        fields = {
            "schema_version",
            "provisioner_id",
            "provisioner_version",
            "receipt_sha256",
            "workspace_id",
            "workspace_identity_sha256",
            "base_commit",
            "candidate_id",
            "architecture",
            "substrate",
            "harness_sha256",
            "image_digest",
            "dependency_lock_sha256",
            "execution_spec_sha256",
            "test_spec_sha256",
            "clean_start",
            "fresh_worktree",
            "credential_names",
        }
        data = _exact_object(value, fields, "provisioning_receipt")
        credentials = data["credential_names"]
        if not isinstance(credentials, list):
            raise LedgerError("provisioning credential_names must be a JSON array")
        return cls(
            schema_version=_plain_string(
                data["schema_version"],
                "provisioning_receipt.schema_version",
            ),
            provisioner_id=_identifier(
                data["provisioner_id"],
                "provisioning_receipt.provisioner_id",
            ),
            provisioner_version=_identifier(
                data["provisioner_version"],
                "provisioning_receipt.provisioner_version",
            ),
            receipt_sha256=_digest(
                data["receipt_sha256"],
                "provisioning_receipt.receipt_sha256",
            ),
            workspace_id=_identifier(
                data["workspace_id"],
                "provisioning_receipt.workspace_id",
            ),
            workspace_identity_sha256=_digest(
                data["workspace_identity_sha256"],
                "provisioning_receipt.workspace_identity_sha256",
            ),
            base_commit=_base_commit(
                data["base_commit"],
                "provisioning_receipt.base_commit",
            ),
            candidate_id=_candidate_id(
                data["candidate_id"],
                "provisioning_receipt.candidate_id",
            ),
            architecture=_identifier(
                data["architecture"],
                "provisioning_receipt.architecture",
            ),
            substrate=_identifier(
                data["substrate"],
                "provisioning_receipt.substrate",
            ),
            harness_sha256=_digest(
                data["harness_sha256"],
                "provisioning_receipt.harness_sha256",
            ),
            image_digest=_optional_image_digest(
                data["image_digest"],
                "provisioning_receipt.image_digest",
            ),
            dependency_lock_sha256=_digest(
                data["dependency_lock_sha256"],
                "provisioning_receipt.dependency_lock_sha256",
            ),
            execution_spec_sha256=_digest(
                data["execution_spec_sha256"],
                "provisioning_receipt.execution_spec_sha256",
            ),
            test_spec_sha256=_digest(
                data["test_spec_sha256"],
                "provisioning_receipt.test_spec_sha256",
            ),
            clean_start=_boolean(
                data["clean_start"],
                "provisioning_receipt.clean_start",
            ),
            fresh_worktree=_boolean(
                data["fresh_worktree"],
                "provisioning_receipt.fresh_worktree",
            ),
            credential_names=tuple(credentials),
        )


@dataclass(frozen=True)
class ArtifactRetention:
    """Immutable raw-artifact store identity declared before dispatch."""

    store_id: str
    artifact_directory: str
    layout: str = "acquisition_id_json"
    immutable: bool = True
    schema_version: str = ARTIFACT_RETENTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ARTIFACT_RETENTION_SCHEMA_VERSION:
            raise LedgerError("unsupported artifact-retention schema version")
        _identifier(self.store_id, "artifact_retention.store_id")
        directory = _plain_string(
            self.artifact_directory,
            "artifact_retention.artifact_directory",
        )
        if not pathlib.Path(directory).is_absolute():
            raise LedgerError("artifact-retention directory must be absolute")
        if self.layout != "acquisition_id_json":
            raise LedgerError("unsupported raw-artifact retention layout")
        if self.immutable is not True:
            raise LedgerError("raw-artifact retention must be immutable")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "store_id": self.store_id,
            "artifact_directory": self.artifact_directory,
            "layout": self.layout,
            "immutable": self.immutable,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ArtifactRetention:
        data = _exact_object(
            value,
            {
                "schema_version",
                "store_id",
                "artifact_directory",
                "layout",
                "immutable",
            },
            "artifact_retention",
        )
        return cls(
            schema_version=_plain_string(
                data["schema_version"],
                "artifact_retention.schema_version",
            ),
            store_id=_identifier(
                data["store_id"],
                "artifact_retention.store_id",
            ),
            artifact_directory=_plain_string(
                data["artifact_directory"],
                "artifact_retention.artifact_directory",
            ),
            layout=_plain_string(
                data["layout"],
                "artifact_retention.layout",
            ),
            immutable=_boolean(
                data["immutable"],
                "artifact_retention.immutable",
            ),
        )


@dataclass(frozen=True)
class ExecutableActionSpec:
    """Strict pre-execution realization of one nonterminal action offer.

    The acquisition identity is the sole dynamic value because it is allocated by
    the write-ahead policy decision. Every other plan and request byte is fixed in
    ``plan_template`` before the scheduler draw.
    """

    action_id: str
    route_action: RouteAction
    evidence_kind: EvidenceKind
    adapter_id: str
    adapter_version: str
    manifest_before_sha256: str
    plan_template_sha256: str
    selected_request_sha256: str
    resource_kind: str
    resource_key: str
    provisioning_receipt: ProvisioningReceipt
    artifact_retention: ArtifactRetention
    repeat_of_action_spec_sha256: str | None
    _manifest_before_json: str = field(repr=False)
    _plan_template_json: str = field(repr=False)
    schema_version: str = EXECUTABLE_ACTION_SPEC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXECUTABLE_ACTION_SPEC_SCHEMA_VERSION:
            raise LedgerError("unsupported executable-action-spec schema version")
        _identifier(self.action_id, "executable_action_spec.action_id")
        if not isinstance(self.route_action, RouteAction):
            raise LedgerError("executable action route_action is invalid")
        if self.route_action in {
            RouteAction.ACCEPT,
            RouteAction.REJECT,
            RouteAction.ABSTAIN,
        }:
            raise LedgerError("terminal policy actions cannot have executable specs")
        if not isinstance(self.evidence_kind, EvidenceKind):
            raise LedgerError("executable action evidence_kind is invalid")
        _identifier(self.adapter_id, "executable_action_spec.adapter_id")
        _identifier(self.adapter_version, "executable_action_spec.adapter_version")
        _digest(
            self.manifest_before_sha256,
            "executable_action_spec.manifest_before_sha256",
        )
        _digest(
            self.plan_template_sha256,
            "executable_action_spec.plan_template_sha256",
        )
        _digest(
            self.selected_request_sha256,
            "executable_action_spec.selected_request_sha256",
        )
        _identifier(self.resource_kind, "executable_action_spec.resource_kind")
        _plain_string(self.resource_key, "executable_action_spec.resource_key")
        if not isinstance(self.provisioning_receipt, ProvisioningReceipt):
            raise LedgerError("executable action provisioning receipt is invalid")
        if not isinstance(self.artifact_retention, ArtifactRetention):
            raise LedgerError("executable action artifact retention is invalid")
        if self.repeat_of_action_spec_sha256 is not None:
            _digest(
                self.repeat_of_action_spec_sha256,
                "executable_action_spec.repeat_of_action_spec_sha256",
            )
        if self.action_id == "full_repeat":
            if (
                self.repeat_of_action_spec_sha256 is None
                or self.resource_kind != "fresh_worktree"
                or not self.provisioning_receipt.fresh_worktree
            ):
                raise LedgerError(
                    "full_repeat requires a primary-spec reference and fresh worktree"
                )
        elif self.repeat_of_action_spec_sha256 is not None:
            raise LedgerError("only full_repeat may reference a primary action spec")

    @classmethod
    def from_dict(cls, value: Any) -> ExecutableActionSpec:
        fields = {
            "schema_version",
            "action_id",
            "route_action",
            "evidence_kind",
            "adapter_id",
            "adapter_version",
            "manifest_before_sha256",
            "manifest_before",
            "plan_template_sha256",
            "selected_request_sha256",
            "plan_template",
            "reservation",
            "provisioning_receipt",
            "artifact_retention",
            "repeat_of_action_spec_sha256",
        }
        data = _exact_object(value, fields, "executable_action_spec")
        _reject_credential_material(data, "executable_action_spec")
        if data["schema_version"] != EXECUTABLE_ACTION_SPEC_SCHEMA_VERSION:
            raise LedgerError("unsupported executable-action-spec schema version")
        try:
            route_action = RouteAction(
                _plain_string(data["route_action"], "action_spec.route_action")
            )
            evidence_kind = EvidenceKind(
                _plain_string(data["evidence_kind"], "action_spec.evidence_kind")
            )
        except ValueError as exc:
            raise LedgerError("executable action uses an unknown route or kind") from exc
        reservation = _exact_object(
            data["reservation"],
            {"resource_kind", "resource_key"},
            "executable_action_spec.reservation",
        )
        template_json, template = _canonical_object(
            data["plan_template"],
            "executable_action_spec.plan_template",
        )
        if template.get("acquisition_id") != PLAN_ACQUISITION_ID_PLACEHOLDER:
            raise LedgerError(
                "action-spec plan template must use the acquisition-id placeholder"
            )
        if _value_occurrences(template, PLAN_ACQUISITION_ID_PLACEHOLDER) != 1:
            raise LedgerError(
                "the acquisition-id placeholder must occur only in plan.acquisition_id"
            )
        realized = cast(dict[str, Any], strict_json_loads(template_json))
        realized["acquisition_id"] = _PLAN_PLACEHOLDER_ACQUISITION_ID
        try:
            plan = RouteAcquisitionPlan.from_dict(realized)
        except ValueError as exc:
            raise LedgerError(f"action-spec plan template is invalid: {exc}") from exc
        if set(plan.requests) != {route_action}:
            raise LedgerError(
                "action-spec plan must contain exactly the selected route request"
            )
        request = plan.requests[route_action]
        if request.kind != evidence_kind:
            raise LedgerError("action-spec selected request has the wrong evidence kind")
        plan_digest = _canonical_sha256(template)
        request_digest = _canonical_sha256(request.to_dict())
        if data["plan_template_sha256"] != plan_digest:
            raise LedgerError("action-spec plan-template digest differs")
        if data["selected_request_sha256"] != request_digest:
            raise LedgerError("action-spec selected-request digest differs")
        manifest_json, manifest_value = _canonical_object(
            data["manifest_before"],
            "executable_action_spec.manifest_before",
        )
        try:
            manifest_before = ValidityManifest.from_dict(manifest_value)
        except ValueError as exc:
            raise LedgerError(f"action-spec routed manifest is invalid: {exc}") from exc
        manifest_digest = manifest_before.canonical_digest()
        if data["manifest_before_sha256"] != manifest_digest:
            raise LedgerError("action-spec routed-manifest digest differs")
        if (
            manifest_digest != plan.manifest_sha256
            or manifest_before.instance_id != plan.instance_id
            or manifest_before.candidate_id != plan.candidate_id
            or not manifest_before.route_history
            or manifest_before.route_history[-1].terminal
            or manifest_before.route_history[-1].action != route_action
        ):
            raise LedgerError(
                "action-spec routed manifest contradicts its exact plan/action"
            )
        receipt = ProvisioningReceipt.from_dict(data["provisioning_receipt"])
        retention = ArtifactRetention.from_dict(data["artifact_retention"])
        if (
            receipt.workspace_id != plan.workspace_id
            or receipt.workspace_identity_sha256 != plan.workspace_identity_sha256
            or receipt.base_commit != plan.base_commit
            or receipt.candidate_id != plan.candidate_id
        ):
            raise LedgerError(
                "provisioning receipt contradicts the exact plan workspace identity"
            )
        if retention.artifact_directory != plan.artifact_directory:
            raise LedgerError("artifact-retention identity contradicts the plan")
        repeat = data["repeat_of_action_spec_sha256"]
        if repeat is not None:
            repeat = _digest(repeat, "action_spec.repeat_of_action_spec_sha256")
        return cls(
            schema_version=cast(str, data["schema_version"]),
            action_id=_identifier(data["action_id"], "action_spec.action_id"),
            route_action=route_action,
            evidence_kind=evidence_kind,
            adapter_id=_identifier(data["adapter_id"], "action_spec.adapter_id"),
            adapter_version=_identifier(
                data["adapter_version"],
                "action_spec.adapter_version",
            ),
            manifest_before_sha256=manifest_digest,
            plan_template_sha256=plan_digest,
            selected_request_sha256=request_digest,
            resource_kind=_identifier(
                reservation["resource_kind"],
                "action_spec.reservation.resource_kind",
            ),
            resource_key=_plain_string(
                reservation["resource_key"],
                "action_spec.reservation.resource_key",
            ),
            provisioning_receipt=receipt,
            artifact_retention=retention,
            repeat_of_action_spec_sha256=cast(str | None, repeat),
            _manifest_before_json=manifest_json,
            _plan_template_json=template_json,
        )

    @classmethod
    def from_plan(
        cls,
        *,
        action_id: str,
        route_action: RouteAction,
        evidence_kind: EvidenceKind,
        adapter_id: str,
        adapter_version: str,
        manifest_before: ValidityManifest,
        plan: RouteAcquisitionPlan,
        resource_kind: str,
        resource_key: str,
        provisioning_receipt: ProvisioningReceipt,
        artifact_retention: ArtifactRetention,
        repeat_of_action_spec_sha256: str | None = None,
    ) -> ExecutableActionSpec:
        template = plan.to_dict()
        template["acquisition_id"] = PLAN_ACQUISITION_ID_PLACEHOLDER
        request = plan.requests.get(route_action)
        if request is None:
            raise LedgerError("plan omits the action spec's selected route request")
        return cls.from_dict({
            "schema_version": EXECUTABLE_ACTION_SPEC_SCHEMA_VERSION,
            "action_id": action_id,
            "route_action": route_action.value,
            "evidence_kind": evidence_kind.value,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "manifest_before_sha256": manifest_before.canonical_digest(),
            "manifest_before": manifest_before.to_dict(),
            "plan_template_sha256": _canonical_sha256(template),
            "selected_request_sha256": _canonical_sha256(request.to_dict()),
            "plan_template": template,
            "reservation": {
                "resource_kind": resource_kind,
                "resource_key": resource_key,
            },
            "provisioning_receipt": provisioning_receipt.to_dict(),
            "artifact_retention": artifact_retention.to_dict(),
            "repeat_of_action_spec_sha256": repeat_of_action_spec_sha256,
        })

    @classmethod
    def from_preimage(cls, preimage: bytes) -> ExecutableActionSpec:
        try:
            text = preimage.decode("utf-8")
            value = strict_json_loads(text)
        except (UnicodeDecodeError, ValueError) as exc:
            raise LedgerError("executable action preimage is not strict UTF-8 JSON") from exc
        if strict_json_dumps(value).encode("utf-8") != preimage:
            raise LedgerError("executable action preimage is not canonical JSON")
        return cls.from_dict(value)

    def plan_template_dict(self) -> dict[str, Any]:
        return _decode_record(
            self._plan_template_json,
            "executable_action_spec.plan_template",
        )

    def manifest_before(self) -> ValidityManifest:
        return ValidityManifest.from_dict(
            _decode_record(
                self._manifest_before_json,
                "executable_action_spec.manifest_before",
            )
        )

    def route_decision(self) -> RouteDecision:
        manifest = self.manifest_before()
        if not manifest.route_history:  # pragma: no cover - constructor invariant.
            raise LedgerError("executable action manifest omits its route decision")
        return manifest.route_history[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action_id": self.action_id,
            "route_action": self.route_action.value,
            "evidence_kind": self.evidence_kind.value,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "manifest_before_sha256": self.manifest_before_sha256,
            "manifest_before": self.manifest_before().to_dict(),
            "plan_template_sha256": self.plan_template_sha256,
            "selected_request_sha256": self.selected_request_sha256,
            "plan_template": self.plan_template_dict(),
            "reservation": {
                "resource_kind": self.resource_kind,
                "resource_key": self.resource_key,
            },
            "provisioning_receipt": self.provisioning_receipt.to_dict(),
            "artifact_retention": self.artifact_retention.to_dict(),
            "repeat_of_action_spec_sha256": self.repeat_of_action_spec_sha256,
        }

    def canonical_preimage(self) -> bytes:
        return strict_json_dumps(self.to_dict()).encode("utf-8")

    def canonical_digest(self) -> str:
        return canonical_action_spec_sha256(self.to_dict())

    def realized_plan(self, acquisition_id: str) -> RouteAcquisitionPlan:
        acquisition = _acquisition_id(acquisition_id, "dispatch acquisition_id")
        value = self.plan_template_dict()
        value["acquisition_id"] = acquisition
        try:
            return RouteAcquisitionPlan.from_dict(value)
        except ValueError as exc:  # pragma: no cover - template parsed at construction.
            raise LedgerError(f"realized executable plan is invalid: {exc}") from exc

    def execution_inputs(
        self,
        acquisition_id: str,
    ) -> tuple[ValidityManifest, RouteDecision, RouteAcquisitionPlan]:
        manifest = self.manifest_before()
        return manifest, self.route_decision(), self.realized_plan(acquisition_id)

    def reservation_details(self) -> dict[str, Any]:
        return {
            "provisioning_receipt": self.provisioning_receipt.to_dict(),
            "artifact_retention": self.artifact_retention.to_dict(),
        }

    def validate_dispatch(
        self,
        *,
        action_spec_sha256: str,
        decision: LoggedPolicyDecision,
        reservation: ReservationRequest,
        plan: RouteAcquisitionPlan,
    ) -> None:
        if decision.terminal or decision.acquisition_id is None:
            raise LedgerError("terminal decisions cannot realize executable action specs")
        offer = decision.chosen_offer
        if (
            self.canonical_digest() != action_spec_sha256
            or offer.action_spec_sha256 != action_spec_sha256
            or self.action_id != decision.chosen_action_id
            or self.route_action != offer.route_action
            or self.evidence_kind != offer.evidence_kind
            or self.adapter_id != offer.adapter_id
            or self.adapter_version != offer.adapter_version
        ):
            raise LedgerError(
                "executable action spec differs from the concrete policy action"
            )
        if (
            plan.instance_id != decision.instance_id
            or plan.candidate_id != decision.candidate_id
            or plan.acquisition_id != decision.acquisition_id
            or plan.to_dict()
            != self.realized_plan(decision.acquisition_id).to_dict()
        ):
            raise LedgerError(
                "RouteAcquisitionPlan differs from the committed action-spec preimage"
            )
        if self.manifest_before().canonical_digest() != plan.manifest_sha256:
            raise LedgerError("action-spec routed manifest differs from its plan")
        if (
            reservation.acquisition_id != decision.acquisition_id
            or reservation.resource_kind != self.resource_kind
            or reservation.resource_key != self.resource_key
            or reservation.details_object() != self.reservation_details()
        ):
            raise LedgerError(
                "resource reservation differs from the executable action spec"
            )

    def validate_repeat_of(self, primary: ExecutableActionSpec) -> None:
        if self.action_id != "full_repeat" or primary.action_id != "full_primary":
            raise LedgerError("repeat equivalence requires full_primary/full_repeat")
        if self.repeat_of_action_spec_sha256 != primary.canonical_digest():
            raise LedgerError("full_repeat references the wrong primary action spec")
        current_plan = self.realized_plan(_PLAN_PLACEHOLDER_ACQUISITION_ID)
        primary_plan = primary.realized_plan(_PLAN_PLACEHOLDER_ACQUISITION_ID)
        current_request = current_plan.requests[self.route_action].to_dict()
        primary_request = primary_plan.requests[primary.route_action].to_dict()
        current_request.pop("workspace_root")
        primary_request.pop("workspace_root")
        comparable_receipt_fields = (
            "architecture",
            "substrate",
            "harness_sha256",
            "image_digest",
            "dependency_lock_sha256",
            "execution_spec_sha256",
            "test_spec_sha256",
            "credential_names",
        )
        if (
            current_plan.instance_id != primary_plan.instance_id
            or current_plan.candidate_id != primary_plan.candidate_id
            or current_plan.base_commit != primary_plan.base_commit
            or current_request != primary_request
            or any(
                getattr(self.provisioning_receipt, name)
                != getattr(primary.provisioning_receipt, name)
                for name in comparable_receipt_fields
            )
        ):
            raise LedgerError(
                "full_repeat changes the primary execution/test/request contract"
            )
        if (
            current_plan.workspace_root == primary_plan.workspace_root
            or current_plan.workspace_id == primary_plan.workspace_id
            or current_plan.workspace_identity_sha256
            == primary_plan.workspace_identity_sha256
            or current_plan.output_path == primary_plan.output_path
            or self.resource_key == primary.resource_key
            or self.provisioning_receipt.receipt_sha256
            == primary.provisioning_receipt.receipt_sha256
            or not self.provisioning_receipt.clean_start
            or not self.provisioning_receipt.fresh_worktree
        ):
            raise LedgerError(
                "full_repeat lacks distinct clean/fresh provisioning identities"
            )


@dataclass(frozen=True)
class ReservationRequest:
    """The complete exclusive resource bundle for one dispatch intent.

    ``details`` may enumerate multiple bounded resources, but ``resource_key``
    is the unique identity of the bundle and cannot ever be reused by another
    acquisition in this ledger.
    """

    acquisition_id: str
    resource_kind: str
    resource_key: str
    details: Mapping[str, Any] = field(default_factory=dict)
    _details_json: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acquisition_id",
            _acquisition_id(self.acquisition_id, "reservation.acquisition_id"),
        )
        _identifier(self.resource_kind, "reservation.resource_kind")
        if (
            not isinstance(self.resource_key, str)
            or not self.resource_key
            or self.resource_key != self.resource_key.strip()
            or any(ord(character) < 32 for character in self.resource_key)
        ):
            raise LedgerError(
                "reservation.resource_key must be nonempty and free of control whitespace"
            )
        details_json, _ = _canonical_object(
            dict(self.details), "reservation.details"
        )
        _reject_credential_material(
            strict_json_loads(details_json), "reservation.details"
        )
        object.__setattr__(self, "_details_json", details_json)

    def details_object(self) -> dict[str, Any]:
        return _decode_record(self._details_json, "reservation.details")


@dataclass(frozen=True)
class DispatchEnvelope:
    """Immutable executable view of one already-committed dispatch intent."""

    dispatch_id: str
    round_sha256: str
    task_id: str
    committed_at: str
    action_spec_sha256: str
    action_spec_preimage: bytes
    decision: LoggedPolicyDecision
    reservation: ReservationRequest
    action_spec: ExecutableActionSpec
    envelope_sha256: str

    def __post_init__(self) -> None:
        _identifier(self.dispatch_id, "dispatch_envelope.dispatch_id")
        _digest(self.round_sha256, "dispatch_envelope.round_sha256")
        _identifier(self.task_id, "dispatch_envelope.task_id")
        _timestamp(self.committed_at, "dispatch_envelope.committed_at")
        digest = _digest(
            self.action_spec_sha256,
            "dispatch_envelope.action_spec_sha256",
        )
        if not isinstance(self.action_spec_preimage, bytes):
            raise LedgerError("dispatch-envelope action preimage must be bytes")
        if (
            _sha256_bytes(self.action_spec_preimage) != digest
            or self.action_spec.canonical_preimage() != self.action_spec_preimage
        ):
            raise LedgerError("dispatch-envelope action preimage identity differs")
        if not isinstance(self.decision, LoggedPolicyDecision):
            raise LedgerError("dispatch envelope has an invalid policy decision")
        if not isinstance(self.reservation, ReservationRequest):
            raise LedgerError("dispatch envelope has an invalid reservation")
        if not isinstance(self.action_spec, ExecutableActionSpec):
            raise LedgerError("dispatch envelope has an invalid executable action spec")
        if self.decision.acquisition_id is None:
            raise LedgerError("dispatch envelope cannot contain a terminal decision")
        expected = _canonical_sha256(self._payload())
        if self.envelope_sha256 != expected:
            raise LedgerError("dispatch-envelope digest differs from its content")

    @property
    def acquisition_id(self) -> str:
        assert self.decision.acquisition_id is not None
        return self.decision.acquisition_id

    def _payload(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "round_sha256": self.round_sha256,
            "task_id": self.task_id,
            "committed_at": self.committed_at,
            "action_spec_sha256": self.action_spec_sha256,
            "action_spec_preimage_base64": base64.b64encode(
                self.action_spec_preimage
            ).decode("ascii"),
            "decision": self.decision.to_dict(),
            "reservation": {
                "acquisition_id": self.reservation.acquisition_id,
                "resource_kind": self.reservation.resource_kind,
                "resource_key": self.reservation.resource_key,
                "details": self.reservation.details_object(),
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "envelope_sha256": self.envelope_sha256}

    def validate_execution_inputs(
        self,
        *,
        manifest_before: ValidityManifest,
        route_decision: RouteDecision,
        plan: RouteAcquisitionPlan,
    ) -> None:
        self.action_spec.validate_dispatch(
            action_spec_sha256=self.action_spec_sha256,
            decision=self.decision,
            reservation=self.reservation,
            plan=plan,
        )
        if not isinstance(manifest_before, ValidityManifest):
            raise LedgerError("dispatch manifest_before is invalid")
        if not isinstance(route_decision, RouteDecision):
            raise LedgerError("dispatch route_decision is invalid")
        if (
            route_decision.terminal
            or route_decision.action != self.action_spec.route_action
            or route_decision != self.action_spec.route_decision()
            or manifest_before.to_dict()
            != self.action_spec.manifest_before().to_dict()
            or manifest_before.instance_id != self.decision.instance_id
            or manifest_before.candidate_id != self.decision.candidate_id
            or manifest_before.canonical_digest() != plan.manifest_sha256
            or not manifest_before.route_history
            or manifest_before.route_history[-1] != route_decision
        ):
            raise LedgerError(
                "manifest/route preimages differ from the committed executable action"
            )
        pre_route_value = manifest_before.to_dict()
        route_history = pre_route_value.get("route_history")
        if not isinstance(route_history, list) or not route_history:
            raise LedgerError("routed manifest has no removable last route decision")
        route_history.pop()
        pre_route_manifest = ValidityManifest.from_dict(pre_route_value)
        if (
            pre_route_manifest.canonical_digest() != self.decision.manifest_sha256
            or RouterStateView.from_manifest(
                pre_route_manifest,
                bootstrap_history=self.decision.router_state.bootstrap_history,
            )
            != self.decision.router_state
        ):
            raise LedgerError(
                "routed manifest does not have the logged pre-route state as parent"
            )
        candidate_patch = manifest_before.provenance.get(
            "candidate_patch_sha256"
        )
        if (
            candidate_patch != self.decision.candidate_id.removeprefix("sha256:")
            or manifest_before.provenance.get("base_commit") != plan.base_commit
        ):
            raise LedgerError(
                "manifest provenance differs from the executable plan subject"
            )


@dataclass(frozen=True)
class RoundCommitReceipt:
    round_sha256: str
    committed_at: str
    inserted: bool
    dispatch_ids: tuple[str, ...]
    reservation_ids: tuple[str, ...]


@dataclass(frozen=True)
class ClaimReceipt:
    claim_id: str
    dispatch_id: str
    acquisition_id: str
    claimant: str
    claimed_at: str


@dataclass(frozen=True)
class ClaimedDispatchEnvelope:
    claim: ClaimReceipt
    dispatch: DispatchEnvelope

    def __post_init__(self) -> None:
        if self.claim.dispatch_id != self.dispatch.dispatch_id or (
            self.claim.acquisition_id != self.dispatch.acquisition_id
        ):
            raise LedgerError("claimed dispatch envelope joins different identities")


@dataclass(frozen=True)
class ResultReceipt:
    result_id: str
    acquisition_id: str
    result_sha256: str
    inserted: bool


@dataclass(frozen=True)
class CommittedResultIdentity:
    receipt: ResultReceipt
    completed_at: str
    artifact_sha256: str
    completed_output_sha256: str


@dataclass(frozen=True)
class IncidentReceipt:
    incident_id: str
    acquisition_id: str
    incident_sha256: str
    inserted: bool


@dataclass(frozen=True)
class SelectionCommitReceipt:
    selection_sha256: str
    committed_at: str
    inserted: bool


@dataclass(frozen=True)
class ExportAudit:
    record_count: int
    export_head_sha256: str
    event_head_sha256: str
    table_counts: tuple[tuple[str, int], ...]
    complete: bool
    analysis_ready: bool
    committed_task_count: int
    selected_task_count: int
    pending_dispatch_count: int
    halted_task_count: int
    protocol_result_count: int


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS ledger_meta (
        meta_key TEXT PRIMARY KEY,
        meta_value TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_specs (
        action_spec_sha256 TEXT PRIMARY KEY,
        preimage BLOB NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rounds (
        round_sha256 TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        round_index INTEGER NOT NULL CHECK(round_index >= 0),
        prior_task_head_sha256 TEXT NOT NULL,
        task_head_sha256 TEXT NOT NULL UNIQUE,
        round_json TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE,
        UNIQUE(task_id, round_index),
        UNIQUE(task_id, prior_task_head_sha256)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_decisions (
        decision_id TEXT PRIMARY KEY,
        decision_sha256 TEXT NOT NULL UNIQUE,
        round_sha256 TEXT NOT NULL REFERENCES rounds(round_sha256),
        task_id TEXT NOT NULL,
        candidate_id TEXT NOT NULL,
        candidate_position INTEGER NOT NULL CHECK(candidate_position >= 0),
        decision_step INTEGER NOT NULL CHECK(decision_step >= 0),
        acquisition_id TEXT UNIQUE,
        action_id TEXT NOT NULL,
        action_spec_sha256 TEXT NOT NULL REFERENCES action_specs(action_spec_sha256),
        terminal INTEGER NOT NULL CHECK(terminal IN (0, 1)),
        decision_json TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE,
        UNIQUE(round_sha256, candidate_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dispatch_intents (
        dispatch_id TEXT PRIMARY KEY,
        round_sha256 TEXT NOT NULL REFERENCES rounds(round_sha256),
        decision_id TEXT NOT NULL UNIQUE REFERENCES policy_decisions(decision_id),
        acquisition_id TEXT NOT NULL UNIQUE,
        candidate_id TEXT NOT NULL,
        action_id TEXT NOT NULL,
        action_spec_sha256 TEXT NOT NULL REFERENCES action_specs(action_spec_sha256),
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resource_reservations (
        reservation_id TEXT PRIMARY KEY,
        dispatch_id TEXT NOT NULL UNIQUE REFERENCES dispatch_intents(dispatch_id),
        acquisition_id TEXT NOT NULL UNIQUE,
        resource_kind TEXT NOT NULL,
        resource_key TEXT NOT NULL UNIQUE,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claims (
        claim_id TEXT PRIMARY KEY,
        dispatch_id TEXT NOT NULL UNIQUE REFERENCES dispatch_intents(dispatch_id),
        acquisition_id TEXT NOT NULL UNIQUE,
        claimant TEXT NOT NULL,
        claimed_at TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS results (
        result_id TEXT PRIMARY KEY,
        dispatch_id TEXT NOT NULL UNIQUE REFERENCES dispatch_intents(dispatch_id),
        claim_id TEXT NOT NULL UNIQUE REFERENCES claims(claim_id),
        acquisition_id TEXT NOT NULL UNIQUE,
        completed_at TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        completed_output_sha256 TEXT NOT NULL,
        validation_contract TEXT NOT NULL,
        observation_json TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        dispatch_id TEXT NOT NULL UNIQUE REFERENCES dispatch_intents(dispatch_id),
        claim_id TEXT NOT NULL UNIQUE REFERENCES claims(claim_id),
        acquisition_id TEXT NOT NULL UNIQUE,
        occurred_at TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        details_json TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS selections (
        selection_sha256 TEXT PRIMARY KEY,
        task_id TEXT NOT NULL UNIQUE,
        final_round_sha256 TEXT NOT NULL REFERENCES rounds(round_sha256),
        selection_json TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        event_sequence INTEGER PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE,
        event_kind TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        prior_event_sha256 TEXT NOT NULL,
        event_sha256 TEXT NOT NULL UNIQUE,
        record_json TEXT NOT NULL,
        record_sha256 TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS results_reject_incident
    BEFORE INSERT ON results
    WHEN EXISTS (
        SELECT 1 FROM incidents WHERE acquisition_id = NEW.acquisition_id
    )
    BEGIN
        SELECT RAISE(ABORT, 'result conflicts with task-halt incident');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS incidents_reject_result
    BEFORE INSERT ON incidents
    WHEN EXISTS (
        SELECT 1 FROM results WHERE acquisition_id = NEW.acquisition_id
    )
    BEGIN
        SELECT RAISE(ABORT, 'task-halt incident conflicts with result');
    END
    """,
)


@contextmanager
def _immediate_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def _dispatch_record(
    round_sha256: str,
    decision: LoggedPolicyDecision,
    candidate_position: int,
) -> dict[str, Any]:
    if decision.terminal or decision.acquisition_id is None:
        raise LedgerError("terminal policy decisions cannot create dispatch intents")
    offer = decision.chosen_offer
    body = {
        "round_sha256": round_sha256,
        "decision_id": decision.decision_id,
        "decision_sha256": decision.decision_sha256,
        "acquisition_id": decision.acquisition_id,
        "candidate_id": decision.candidate_id,
        "candidate_position": candidate_position,
        "action_id": decision.chosen_action_id,
        "route_action": offer.route_action.value,
        "evidence_kind": (
            None if offer.evidence_kind is None else offer.evidence_kind.value
        ),
        "action_spec_sha256": offer.action_spec_sha256,
    }
    return {
        "dispatch_id": "dsp-" + _canonical_sha256(body)[:32],
        **body,
    }


def _reservation_record(
    dispatch: Mapping[str, Any],
    request: ReservationRequest,
) -> dict[str, Any]:
    acquisition = cast(str, dispatch["acquisition_id"])
    if request.acquisition_id != acquisition:
        raise LedgerError("reservation acquisition differs from its dispatch")
    body = {
        "dispatch_id": dispatch["dispatch_id"],
        "acquisition_id": acquisition,
        "resource_kind": request.resource_kind,
        "resource_key": request.resource_key,
        "details": request.details_object(),
    }
    return {
        "reservation_id": "rsv-" + _canonical_sha256(body)[:32],
        **body,
    }


class ProspectiveLedger:
    """Single-host append-only persistence and dispatch-claim boundary."""

    def __init__(
        self,
        path: pathlib.Path,
        *,
        bindings: SchedulerBindings | None = None,
        busy_timeout_ms: int = 10_000,
    ) -> None:
        database = pathlib.Path(path).resolve()
        if database.exists() and database.is_dir():
            raise LedgerError("ledger path cannot be a directory")
        if (
            isinstance(busy_timeout_ms, bool)
            or not isinstance(busy_timeout_ms, int)
            or busy_timeout_ms < 1
        ):
            raise LedgerError("busy_timeout_ms must be a positive integer")
        if bindings is not None and not isinstance(bindings, SchedulerBindings):
            raise LedgerError("bindings must be SchedulerBindings or None")
        database.parent.mkdir(parents=True, exist_ok=True)
        existed = database.exists()
        self.path = database
        self.bindings = bindings
        self.busy_timeout_ms = busy_timeout_ms
        self._initialize()
        if not existed:
            self._fsync_parent()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        journal = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        synchronous = connection.execute("PRAGMA synchronous").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        if (
            journal is None
            or str(journal[0]).casefold() != "delete"
            or synchronous is None
            or int(synchronous[0]) != 2
            or foreign_keys is None
            or int(foreign_keys[0]) != 1
        ):
            connection.close()
            raise LedgerError("SQLite durability pragmas could not be enforced")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            with _immediate_transaction(connection):
                for statement in _SCHEMA_STATEMENTS:
                    connection.execute(statement)
                meta = {
                    "meta_key": "schema_version",
                    "meta_value": LEDGER_SCHEMA_VERSION,
                }
                record_json, record_sha = _record(meta, "ledger meta")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO ledger_meta(
                        meta_key, meta_value, record_json, record_sha256
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        meta["meta_key"],
                        meta["meta_value"],
                        record_json,
                        record_sha,
                    ),
                )
                row = connection.execute(
                    "SELECT meta_value, record_json FROM ledger_meta "
                    "WHERE meta_key = 'schema_version'"
                ).fetchone()
                if (
                    row is None
                    or row["meta_value"] != LEDGER_SCHEMA_VERSION
                    or row["record_json"] != record_json
                ):
                    raise LedgerConflict("ledger schema identity differs")
                for table in _TABLE_ORDER:
                    connection.execute(
                        f"""
                        CREATE TRIGGER IF NOT EXISTS {table}_deny_update
                        BEFORE UPDATE ON {table}
                        BEGIN
                            SELECT RAISE(ABORT, 'immutable table {table}');
                        END
                        """
                    )
                    connection.execute(
                        f"""
                        CREATE TRIGGER IF NOT EXISTS {table}_deny_delete
                        BEFORE DELETE ON {table}
                        BEGIN
                            SELECT RAISE(ABORT, 'immutable table {table}');
                        END
                        """
                    )
        finally:
            connection.close()

    def _fsync_parent(self) -> None:
        if os.name == "nt":  # pragma: no cover - Windows is not the study host.
            return
        descriptor = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def sqlite_settings(self) -> dict[str, str | int]:
        connection = self._connect()
        try:
            journal = connection.execute("PRAGMA journal_mode").fetchone()
            synchronous = connection.execute("PRAGMA synchronous").fetchone()
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
            return {
                "journal_mode": str(journal[0]).casefold(),
                "synchronous": int(synchronous[0]),
                "foreign_keys": int(foreign_keys[0]),
            }
        finally:
            connection.close()

    def _require_bindings(self) -> SchedulerBindings:
        if self.bindings is None:
            raise LedgerError("scheduler bindings are required for this operation")
        return self.bindings

    @staticmethod
    def _expected_spec_digests(round_decision: TaskRoundDecision) -> set[str]:
        return {
            offer.action_spec_sha256
            for state in round_decision.candidates
            for offer in state.action_catalog
        }

    @staticmethod
    def _normalize_preimages(
        expected: set[str],
        supplied: Mapping[str, bytes],
    ) -> dict[str, bytes]:
        if not isinstance(supplied, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, bytes)
            for key, value in supplied.items()
        ):
            raise LedgerError("action_spec_preimages must map digests to bytes")
        normalized = dict(supplied)
        if set(normalized) != expected:
            raise LedgerError(
                "action-spec preimages differ from the complete round catalog; "
                f"missing={sorted(expected - set(normalized))}, "
                f"extra={sorted(set(normalized) - expected)}"
            )
        for digest, preimage in normalized.items():
            _digest(digest, "action-spec preimage key")
            try:
                text = preimage.decode("utf-8")
                decoded = strict_json_loads(text)
            except (UnicodeDecodeError, ValueError) as exc:
                raise LedgerError(
                    "action-spec preimage must be strict UTF-8 JSON"
                ) from exc
            if not isinstance(decoded, dict) or not decoded:
                raise LedgerError("action-spec preimage must be a nonempty JSON object")
            _reject_credential_material(decoded, "action-spec preimage")
            if strict_json_dumps(decoded).encode() != preimage:
                raise LedgerError("action-spec preimage must use canonical JSON bytes")
            if canonical_action_spec_sha256(decoded) != digest:
                raise LedgerError("action-spec preimage digest differs from its key")
        return normalized

    @staticmethod
    def _normalize_reservations(
        round_decision: TaskRoundDecision,
        supplied: Sequence[ReservationRequest],
    ) -> dict[str, ReservationRequest]:
        if not isinstance(supplied, (list, tuple)) or any(
            not isinstance(item, ReservationRequest) for item in supplied
        ):
            raise LedgerError(
                "reservations must be a sequence of ReservationRequest values"
            )
        result = {item.acquisition_id: item for item in supplied}
        if len(result) != len(supplied):
            raise LedgerError("reservations cannot repeat acquisition_id")
        expected = {
            item.logged_policy_decision.acquisition_id
            for item in round_decision.scheduled_decisions
            if not item.logged_policy_decision.terminal
        }
        if None in expected:
            raise LedgerError("nonterminal decision omitted acquisition_id")
        expected_ids = cast(set[str], expected)
        if set(result) != expected_ids:
            raise LedgerError(
                "reservations must cover exactly the round's nonterminal decisions"
            )
        by_acquisition = {
            item.logged_policy_decision.acquisition_id: item
            for item in round_decision.scheduled_decisions
            if not item.logged_policy_decision.terminal
        }
        for acquisition_id, request in result.items():
            scheduled = by_acquisition[acquisition_id]
            if (
                scheduled.chosen_action_id == "full_repeat"
                and request.resource_kind != "fresh_worktree"
            ):
                raise LedgerError(
                    "full_repeat requires a fresh_worktree resource reservation"
                )
        return result

    @staticmethod
    def _load_rounds(
        connection: sqlite3.Connection,
        task_id: str,
    ) -> tuple[TaskRoundDecision, ...]:
        rows = connection.execute(
            "SELECT round_json FROM rounds WHERE task_id = ? ORDER BY round_index",
            (task_id,),
        ).fetchall()
        return tuple(
            TaskRoundDecision.from_dict(
                _decode_record(cast(str, row["round_json"]), "stored round")
            )
            for row in rows
        )

    @staticmethod
    def _task_incident(
        connection: sqlite3.Connection,
        task_id: str,
    ) -> sqlite3.Row | None:
        row = connection.execute(
            "SELECT incident_id, reason_code FROM incidents "
            "WHERE task_id = ? ORDER BY incident_id LIMIT 1",
            (task_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    @staticmethod
    def _assert_all_prior_dispatches_resolved(
        connection: sqlite3.Connection,
        task_id: str,
    ) -> None:
        unresolved = connection.execute(
            """
            SELECT d.acquisition_id
            FROM dispatch_intents AS d
            JOIN rounds AS r ON r.round_sha256 = d.round_sha256
            LEFT JOIN results AS o ON o.dispatch_id = d.dispatch_id
            WHERE r.task_id = ? AND o.result_id IS NULL
            ORDER BY d.acquisition_id
            """,
            (task_id,),
        ).fetchall()
        if unresolved:
            acquisitions = [cast(str, row["acquisition_id"]) for row in unresolved]
            raise RoundNotReady(
                "next round is blocked until every nonterminal sibling has an "
                f"exact result: {acquisitions}"
            )

    @staticmethod
    def _assert_successor_matches_results(
        connection: sqlite3.Connection,
        previous: TaskRoundDecision,
        current: TaskRoundDecision,
    ) -> None:
        current_states = {item.candidate_id: item for item in current.candidates}
        for scheduled in previous.scheduled_decisions:
            logged = scheduled.logged_policy_decision
            if logged.terminal:
                continue
            assert logged.acquisition_id is not None
            row = connection.execute(
                "SELECT observation_json FROM results WHERE acquisition_id = ?",
                (logged.acquisition_id,),
            ).fetchone()
            if row is None:
                raise RoundNotReady(
                    "successor round is missing a persisted sibling result"
                )
            successor = current_states[logged.candidate_id]
            if successor.bound_router_decision is None:
                raise LedgerConflict(
                    "nonterminal result cannot lead directly to a terminal state"
                )
            history = successor.bound_router_decision.router_state.evidence_history
            if not history:
                raise LedgerConflict("successor state omitted its persisted result")
            persisted = EvidenceObservation.from_dict(
                _decode_record(
                    cast(str, row["observation_json"]),
                    "stored result observation",
                )
            )
            if history[-1] != _router_observation_projection(persisted):
                raise LedgerConflict(
                    "successor router observation differs from the persisted result"
                )

    @staticmethod
    def _insert_action_specs(
        connection: sqlite3.Connection,
        preimages: Mapping[str, bytes],
    ) -> None:
        for digest in sorted(preimages):
            preimage = preimages[digest]
            payload = {
                "action_spec_sha256": digest,
                "preimage_base64": base64.b64encode(preimage).decode("ascii"),
            }
            record_json, record_sha = _record(payload, "action-spec record")
            existing = connection.execute(
                "SELECT preimage, record_json FROM action_specs "
                "WHERE action_spec_sha256 = ?",
                (digest,),
            ).fetchone()
            if existing is not None:
                if (
                    bytes(existing["preimage"]) != preimage
                    or existing["record_json"] != record_json
                ):
                    raise LedgerConflict(
                        "existing action-spec digest has different preimage content"
                    )
                continue
            connection.execute(
                """
                INSERT INTO action_specs(
                    action_spec_sha256, preimage, record_json, record_sha256
                ) VALUES (?, ?, ?, ?)
                """,
                (digest, preimage, record_json, record_sha),
            )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        event_kind: str,
        subject_id: str,
        occurred_at: str,
        details: Mapping[str, Any],
    ) -> None:
        _identifier(event_kind, "event_kind")
        _identifier(subject_id, "event subject_id")
        _timestamp(occurred_at, "event occurred_at")
        latest = connection.execute(
            "SELECT event_sequence, event_sha256 FROM events "
            "ORDER BY event_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = 0 if latest is None else int(latest["event_sequence"]) + 1
        prior = (
            EVENT_GENESIS_SHA256
            if latest is None
            else cast(str, latest["event_sha256"])
        )
        payload = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "chain_contract": EVENT_CHAIN_CONTRACT,
            "event_sequence": sequence,
            "event_kind": event_kind,
            "subject_id": subject_id,
            "occurred_at": occurred_at,
            "details": dict(details),
            "prior_event_sha256": prior,
        }
        event_sha = _canonical_sha256(payload)
        record = {
            **payload,
            "event_id": "evt-" + event_sha[:32],
            "event_sha256": event_sha,
        }
        record_json, record_sha = _record(record, "ledger event")
        connection.execute(
            """
            INSERT INTO events(
                event_sequence, event_id, event_kind, subject_id,
                prior_event_sha256, event_sha256, record_json, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                record["event_id"],
                event_kind,
                subject_id,
                prior,
                event_sha,
                record_json,
                record_sha,
            ),
        )

    def commit_round(
        self,
        round_decision: TaskRoundDecision,
        *,
        committed_at: str,
        action_spec_preimages: Mapping[str, bytes],
        reservations: Sequence[ReservationRequest],
    ) -> RoundCommitReceipt:
        """Atomically persist a whole round and every pre-dispatch dependency."""

        bindings = self._require_bindings()
        if not isinstance(round_decision, TaskRoundDecision):
            raise LedgerError("round_decision must be a TaskRoundDecision")
        round_decision.canonical_digest()
        round_decision.validate_against_bindings(bindings)
        committed = _timestamp(committed_at, "committed_at")
        if committed < round_decision.scheduled_at:
            raise LedgerError("round commit cannot predate its scheduled decision")
        expected_specs = self._expected_spec_digests(round_decision)
        preimages = self._normalize_preimages(
            expected_specs, action_spec_preimages
        )
        requests = self._normalize_reservations(round_decision, reservations)
        round_json = strict_json_dumps(round_decision.to_dict())

        dispatch_records: list[dict[str, Any]] = []
        reservation_records: list[dict[str, Any]] = []
        for scheduled in round_decision.scheduled_decisions:
            logged = scheduled.logged_policy_decision
            if logged.terminal:
                continue
            assert logged.acquisition_id is not None
            dispatch = _dispatch_record(
                round_decision.decision_sha256,
                logged,
                scheduled.candidate_position,
            )
            dispatch_records.append(dispatch)
            reservation_records.append(
                _reservation_record(dispatch, requests[logged.acquisition_id])
            )

        connection = self._connect()
        try:
            try:
                with _immediate_transaction(connection):
                    existing = connection.execute(
                        "SELECT round_sha256, round_json, committed_at FROM rounds "
                        "WHERE task_id = ? AND round_index = ?",
                        (round_decision.task_id, round_decision.round_index),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["round_sha256"]
                            != round_decision.decision_sha256
                            or existing["round_json"] != round_json
                        ):
                            raise LedgerConflict(
                                "task round slot already contains different content"
                            )
                        self._assert_existing_round_plan(
                            connection,
                            round_decision,
                            preimages,
                            dispatch_records,
                            reservation_records,
                        )
                        return RoundCommitReceipt(
                            round_sha256=round_decision.decision_sha256,
                            committed_at=cast(str, existing["committed_at"]),
                            inserted=False,
                            dispatch_ids=tuple(
                                cast(str, item["dispatch_id"])
                                for item in dispatch_records
                            ),
                            reservation_ids=tuple(
                                cast(str, item["reservation_id"])
                                for item in reservation_records
                            ),
                        )

                    incident = self._task_incident(connection, round_decision.task_id)
                    if incident is not None:
                        raise TaskHalted(
                            "task has a permanent halt incident "
                            f"{incident['incident_id']}"
                        )
                    prior = self._load_rounds(connection, round_decision.task_id)
                    if round_decision.round_index != len(prior):
                        raise LedgerConflict(
                            "round index is not the next contiguous durable task round"
                        )
                    validate_task_round_chain(
                        (*prior, round_decision), bindings=bindings
                    )
                    if prior:
                        self._assert_all_prior_dispatches_resolved(
                            connection, round_decision.task_id
                        )
                        self._assert_successor_matches_results(
                            connection, prior[-1], round_decision
                        )

                    self._insert_action_specs(connection, preimages)
                    round_record = {
                        "round_sha256": round_decision.decision_sha256,
                        "task_id": round_decision.task_id,
                        "round_index": round_decision.round_index,
                        "committed_at": committed,
                        "round": round_decision.to_dict(),
                    }
                    round_record_json, round_record_sha = _record(
                        round_record, "round record"
                    )
                    connection.execute(
                        """
                        INSERT INTO rounds(
                            round_sha256, task_id, round_index,
                            prior_task_head_sha256, task_head_sha256, round_json,
                            committed_at, record_json, record_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            round_decision.decision_sha256,
                            round_decision.task_id,
                            round_decision.round_index,
                            round_decision.prior_task_head_sha256,
                            round_decision.task_head_sha256,
                            round_json,
                            committed,
                            round_record_json,
                            round_record_sha,
                        ),
                    )

                    for scheduled in round_decision.scheduled_decisions:
                        logged = scheduled.logged_policy_decision
                        policy_record = {
                            "decision_id": logged.decision_id,
                            "round_sha256": round_decision.decision_sha256,
                            "candidate_position": scheduled.candidate_position,
                            "decision": logged.to_dict(),
                        }
                        policy_record_json, policy_record_sha = _record(
                            policy_record, "policy-decision record"
                        )
                        connection.execute(
                            """
                            INSERT INTO policy_decisions(
                                decision_id, decision_sha256, round_sha256,
                                task_id, candidate_id, candidate_position,
                                decision_step, acquisition_id, action_id,
                                action_spec_sha256, terminal, decision_json,
                                record_json, record_sha256
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                logged.decision_id,
                                logged.decision_sha256,
                                round_decision.decision_sha256,
                                round_decision.task_id,
                                logged.candidate_id,
                                scheduled.candidate_position,
                                logged.decision_step,
                                logged.acquisition_id,
                                logged.chosen_action_id,
                                logged.chosen_offer.action_spec_sha256,
                                int(logged.terminal),
                                strict_json_dumps(logged.to_dict()),
                                policy_record_json,
                                policy_record_sha,
                            ),
                        )

                    for dispatch, reservation in zip(
                        dispatch_records, reservation_records, strict=True
                    ):
                        dispatch_json, dispatch_sha = _record(
                            dispatch, "dispatch-intent record"
                        )
                        connection.execute(
                            """
                            INSERT INTO dispatch_intents(
                                dispatch_id, round_sha256, decision_id,
                                acquisition_id, candidate_id, action_id,
                                action_spec_sha256, record_json, record_sha256
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                dispatch["dispatch_id"],
                                dispatch["round_sha256"],
                                dispatch["decision_id"],
                                dispatch["acquisition_id"],
                                dispatch["candidate_id"],
                                dispatch["action_id"],
                                dispatch["action_spec_sha256"],
                                dispatch_json,
                                dispatch_sha,
                            ),
                        )
                        reservation_json, reservation_sha = _record(
                            reservation, "resource-reservation record"
                        )
                        connection.execute(
                            """
                            INSERT INTO resource_reservations(
                                reservation_id, dispatch_id, acquisition_id,
                                resource_kind, resource_key,
                                record_json, record_sha256
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                reservation["reservation_id"],
                                reservation["dispatch_id"],
                                reservation["acquisition_id"],
                                reservation["resource_kind"],
                                reservation["resource_key"],
                                reservation_json,
                                reservation_sha,
                            ),
                        )

                    self._append_event(
                        connection,
                        event_kind="round_committed",
                        subject_id=round_decision.decision_sha256,
                        occurred_at=committed,
                        details={
                            "task_id": round_decision.task_id,
                            "round_index": round_decision.round_index,
                            "policy_decision_ids": [
                                item.logged_policy_decision.decision_id
                                for item in round_decision.scheduled_decisions
                            ],
                            "dispatch_ids": [
                                item["dispatch_id"] for item in dispatch_records
                            ],
                            "action_spec_sha256s": sorted(preimages),
                        },
                    )
            except sqlite3.IntegrityError as exc:
                raise LedgerConflict(f"atomic round commit rejected: {exc}") from exc
        finally:
            connection.close()
        return RoundCommitReceipt(
            round_sha256=round_decision.decision_sha256,
            committed_at=committed,
            inserted=True,
            dispatch_ids=tuple(
                cast(str, item["dispatch_id"]) for item in dispatch_records
            ),
            reservation_ids=tuple(
                cast(str, item["reservation_id"])
                for item in reservation_records
            ),
        )

    @staticmethod
    def _assert_existing_round_plan(
        connection: sqlite3.Connection,
        round_decision: TaskRoundDecision,
        preimages: Mapping[str, bytes],
        dispatch_records: Sequence[Mapping[str, Any]],
        reservation_records: Sequence[Mapping[str, Any]],
    ) -> None:
        for digest, preimage in preimages.items():
            row = connection.execute(
                "SELECT preimage FROM action_specs WHERE action_spec_sha256 = ?",
                (digest,),
            ).fetchone()
            if row is None or bytes(row["preimage"]) != preimage:
                raise LedgerConflict("idempotent round retry changes an action spec")
        expected_policy = {
            item.logged_policy_decision.decision_id: strict_json_dumps(
                item.logged_policy_decision.to_dict()
            )
            for item in round_decision.scheduled_decisions
        }
        rows = connection.execute(
            "SELECT decision_id, decision_json FROM policy_decisions "
            "WHERE round_sha256 = ?",
            (round_decision.decision_sha256,),
        ).fetchall()
        actual_policy = {
            cast(str, row["decision_id"]): cast(str, row["decision_json"])
            for row in rows
        }
        if actual_policy != expected_policy:
            raise LedgerConflict("idempotent round retry changes policy decisions")
        expected_dispatch = {
            cast(str, item["dispatch_id"]): _record(
                item, "expected dispatch"
            )[0]
            for item in dispatch_records
        }
        rows = connection.execute(
            "SELECT dispatch_id, record_json FROM dispatch_intents "
            "WHERE round_sha256 = ?",
            (round_decision.decision_sha256,),
        ).fetchall()
        actual_dispatch = {
            cast(str, row["dispatch_id"]): cast(str, row["record_json"])
            for row in rows
        }
        if actual_dispatch != expected_dispatch:
            raise LedgerConflict("idempotent round retry changes dispatch intents")
        expected_reservations = {
            cast(str, item["reservation_id"]): _record(
                item, "expected reservation"
            )[0]
            for item in reservation_records
        }
        rows = connection.execute(
            """
            SELECT r.reservation_id, r.record_json
            FROM resource_reservations AS r
            JOIN dispatch_intents AS d ON d.dispatch_id = r.dispatch_id
            WHERE d.round_sha256 = ?
            """,
            (round_decision.decision_sha256,),
        ).fetchall()
        actual_reservations = {
            cast(str, row["reservation_id"]): cast(str, row["record_json"])
            for row in rows
        }
        if actual_reservations != expected_reservations:
            raise LedgerConflict("idempotent round retry changes reservations")

    def load_dispatch_envelope(self, acquisition_id: str) -> DispatchEnvelope:
        """Load and validate the immutable executable inputs for one dispatch.

        This is the only production-facing read boundary for workers. It joins
        the committed policy decision, exact action-spec preimage, and exclusive
        reservation before a permanent claim is attempted.
        """

        acquisition = _acquisition_id(acquisition_id, "acquisition_id")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                """
                SELECT d.dispatch_id, d.round_sha256,
                       d.action_spec_sha256, d.record_json AS dispatch_json,
                       r.task_id, r.committed_at,
                       p.decision_json, p.candidate_position, p.decision_step,
                       a.preimage,
                       q.resource_kind, q.resource_key,
                       q.record_json AS reservation_json
                FROM dispatch_intents AS d
                JOIN rounds AS r ON r.round_sha256 = d.round_sha256
                JOIN policy_decisions AS p ON p.decision_id = d.decision_id
                JOIN action_specs AS a
                  ON a.action_spec_sha256 = d.action_spec_sha256
                JOIN resource_reservations AS q
                  ON q.dispatch_id = d.dispatch_id
                WHERE d.acquisition_id = ?
                """,
                (acquisition,),
            ).fetchone()
            if row is None:
                raise LedgerError("acquisition has no committed dispatch envelope")
            decision = LoggedPolicyDecision.from_dict(
                _decode_record(
                    cast(str, row["decision_json"]),
                    "dispatch-envelope policy decision",
                )
            )
            if decision.acquisition_id != acquisition:
                raise LedgerError("dispatch-envelope policy acquisition differs")
            preimage = bytes(row["preimage"])
            action_spec_sha256 = _digest(
                row["action_spec_sha256"],
                "dispatch-envelope action_spec_sha256",
            )
            if _sha256_bytes(preimage) != action_spec_sha256:
                raise LedgerError("stored executable action preimage digest differs")
            action_spec = ExecutableActionSpec.from_preimage(preimage)
            if action_spec.canonical_digest() != action_spec_sha256:
                raise LedgerError("stored executable action-spec identity differs")

            expected_dispatch = _dispatch_record(
                cast(str, row["round_sha256"]),
                decision,
                cast(int, row["candidate_position"]),
            )
            if _decode_record(
                cast(str, row["dispatch_json"]),
                "dispatch-envelope dispatch record",
            ) != expected_dispatch:
                raise LedgerError("stored dispatch intent differs from its policy action")
            reservation_record = _decode_record(
                cast(str, row["reservation_json"]),
                "dispatch-envelope reservation record",
            )
            reservation = ReservationRequest(
                acquisition_id=acquisition,
                resource_kind=cast(str, row["resource_kind"]),
                resource_key=cast(str, row["resource_key"]),
                details=cast(Mapping[str, Any], reservation_record.get("details")),
            )
            if reservation_record != _reservation_record(
                expected_dispatch,
                reservation,
            ):
                raise LedgerError("stored reservation differs from its dispatch intent")
            action_spec.validate_dispatch(
                action_spec_sha256=action_spec_sha256,
                decision=decision,
                reservation=reservation,
                plan=action_spec.realized_plan(acquisition),
            )

            if action_spec.action_id == "full_repeat":
                primary_rows = connection.execute(
                    """
                    SELECT p.action_spec_sha256, a.preimage
                    FROM policy_decisions AS p
                    JOIN action_specs AS a
                      ON a.action_spec_sha256 = p.action_spec_sha256
                    WHERE p.task_id = ? AND p.candidate_id = ?
                      AND p.action_id = 'full_primary'
                      AND p.decision_step < ?
                    ORDER BY p.decision_step
                    """,
                    (
                        decision.instance_id,
                        decision.candidate_id,
                        decision.decision_step,
                    ),
                ).fetchall()
                if len(primary_rows) != 1:
                    raise LedgerError(
                        "full_repeat requires exactly one earlier committed full_primary"
                    )
                primary_preimage = bytes(primary_rows[0]["preimage"])
                primary_sha256 = _digest(
                    primary_rows[0]["action_spec_sha256"],
                    "primary action_spec_sha256",
                )
                if _sha256_bytes(primary_preimage) != primary_sha256:
                    raise LedgerError("primary action-spec preimage digest differs")
                primary = ExecutableActionSpec.from_preimage(primary_preimage)
                if primary.canonical_digest() != primary_sha256:
                    raise LedgerError("primary executable action-spec identity differs")
                action_spec.validate_repeat_of(primary)

            payload = {
                "dispatch_id": row["dispatch_id"],
                "round_sha256": row["round_sha256"],
                "task_id": row["task_id"],
                "committed_at": row["committed_at"],
                "action_spec_sha256": action_spec_sha256,
                "action_spec_preimage_base64": base64.b64encode(preimage).decode(
                    "ascii"
                ),
                "decision": decision.to_dict(),
                "reservation": {
                    "acquisition_id": reservation.acquisition_id,
                    "resource_kind": reservation.resource_kind,
                    "resource_key": reservation.resource_key,
                    "details": reservation.details_object(),
                },
            }
            envelope = DispatchEnvelope(
                dispatch_id=cast(str, row["dispatch_id"]),
                round_sha256=cast(str, row["round_sha256"]),
                task_id=cast(str, row["task_id"]),
                committed_at=cast(str, row["committed_at"]),
                action_spec_sha256=action_spec_sha256,
                action_spec_preimage=preimage,
                decision=decision,
                reservation=reservation,
                action_spec=action_spec,
                envelope_sha256=_canonical_sha256(payload),
            )
            connection.commit()
            return envelope
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def load_claimed_dispatch_envelope(
        self,
        claim_id: str,
    ) -> ClaimedDispatchEnvelope:
        """Recover the immutable dispatch envelope for a permanent claim."""

        claim_identity = _identifier(claim_id, "claim_id")
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT claim_id, dispatch_id, acquisition_id, claimant, claimed_at
                FROM claims WHERE claim_id = ?
                """,
                (claim_identity,),
            ).fetchone()
            if row is None:
                raise LedgerError("claim_id is absent from the ledger")
            claim = ClaimReceipt(
                claim_id=cast(str, row["claim_id"]),
                dispatch_id=cast(str, row["dispatch_id"]),
                acquisition_id=cast(str, row["acquisition_id"]),
                claimant=cast(str, row["claimant"]),
                claimed_at=cast(str, row["claimed_at"]),
            )
        finally:
            connection.close()
        return ClaimedDispatchEnvelope(
            claim=claim,
            dispatch=self.load_dispatch_envelope(claim.acquisition_id),
        )

    def load_result_identity_for_claim(
        self,
        claim_id: str,
    ) -> CommittedResultIdentity | None:
        """Return an already-committed result without changing its identity."""

        claim_identity = _identifier(claim_id, "claim_id")
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT result_id, acquisition_id, record_sha256, completed_at,
                       artifact_sha256, completed_output_sha256
                FROM results WHERE claim_id = ?
                """,
                (claim_identity,),
            ).fetchone()
            if row is None:
                return None
            return CommittedResultIdentity(
                receipt=ResultReceipt(
                    result_id=cast(str, row["result_id"]),
                    acquisition_id=cast(str, row["acquisition_id"]),
                    result_sha256=cast(str, row["record_sha256"]),
                    inserted=False,
                ),
                completed_at=cast(str, row["completed_at"]),
                artifact_sha256=cast(str, row["artifact_sha256"]),
                completed_output_sha256=cast(
                    str,
                    row["completed_output_sha256"],
                ),
            )
        finally:
            connection.close()

    def claim_executable_dispatch(
        self,
        acquisition_id: str,
        *,
        claimant: str,
        claimed_at: str,
        manifest_before: ValidityManifest,
        route_decision: RouteDecision,
        plan: RouteAcquisitionPlan,
    ) -> ClaimedDispatchEnvelope | None:
        """Validate the exact executable envelope, then permanently claim it.

        All joined ledger rows are append-only. The envelope is validated both
        before and after the atomic claim transaction, making a successful return
        a stable claim-to-preimage boundary rather than a sparse claim receipt.
        """

        envelope = self.load_dispatch_envelope(acquisition_id)
        envelope.validate_execution_inputs(
            manifest_before=manifest_before,
            route_decision=route_decision,
            plan=plan,
        )
        claim = self.claim_dispatch(
            acquisition_id,
            claimant=claimant,
            claimed_at=claimed_at,
        )
        if claim is None:
            return None
        claimed = self.load_claimed_dispatch_envelope(claim.claim_id)
        if claimed.dispatch.envelope_sha256 != envelope.envelope_sha256:
            raise LedgerConflict("dispatch envelope changed across its permanent claim")
        claimed.dispatch.validate_execution_inputs(
            manifest_before=manifest_before,
            route_decision=route_decision,
            plan=plan,
        )
        return claimed

    def claim_dispatch(
        self,
        acquisition_id: str,
        *,
        claimant: str,
        claimed_at: str,
    ) -> ClaimReceipt | None:
        """Permanently claim one dispatch; an existing claim always returns ``None``."""

        acquisition = _acquisition_id(acquisition_id, "acquisition_id")
        owner = _identifier(claimant, "claimant")
        timestamp = _timestamp(claimed_at, "claimed_at")
        connection = self._connect()
        try:
            with _immediate_transaction(connection):
                dispatch = connection.execute(
                    """
                    SELECT d.dispatch_id, d.acquisition_id, r.task_id,
                           r.committed_at
                    FROM dispatch_intents AS d
                    JOIN rounds AS r ON r.round_sha256 = d.round_sha256
                    WHERE d.acquisition_id = ?
                    """,
                    (acquisition,),
                ).fetchone()
                if dispatch is None:
                    raise LedgerError("acquisition has no committed dispatch intent")
                if timestamp < dispatch["committed_at"]:
                    raise LedgerError("claim cannot predate its committed round")
                existing = connection.execute(
                    "SELECT 1 FROM claims WHERE acquisition_id = ?",
                    (acquisition,),
                ).fetchone()
                if existing is not None:
                    return None
                if connection.execute(
                    "SELECT 1 FROM results WHERE acquisition_id = ?",
                    (acquisition,),
                ).fetchone() is not None:
                    raise LedgerConflict("completed dispatch cannot be claimed")
                if self._task_incident(
                    connection, cast(str, dispatch["task_id"])
                ) is not None:
                    raise TaskHalted("task is halted and cannot dispatch more work")
                body = {
                    "dispatch_id": dispatch["dispatch_id"],
                    "acquisition_id": acquisition,
                    "claimant": owner,
                    "claimed_at": timestamp,
                }
                claim_id = "clm-" + _canonical_sha256(body)[:32]
                record = {"claim_id": claim_id, **body}
                record_json, record_sha = _record(record, "claim record")
                connection.execute(
                    """
                    INSERT INTO claims(
                        claim_id, dispatch_id, acquisition_id, claimant,
                        claimed_at, record_json, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        dispatch["dispatch_id"],
                        acquisition,
                        owner,
                        timestamp,
                        record_json,
                        record_sha,
                    ),
                )
                self._append_event(
                    connection,
                    event_kind="dispatch_claimed",
                    subject_id=claim_id,
                    occurred_at=timestamp,
                    details={
                        "dispatch_id": dispatch["dispatch_id"],
                        "acquisition_id": acquisition,
                        "claimant": owner,
                    },
                )
                return ClaimReceipt(
                    claim_id=claim_id,
                    dispatch_id=cast(str, dispatch["dispatch_id"]),
                    acquisition_id=acquisition,
                    claimant=owner,
                    claimed_at=timestamp,
                )
        finally:
            connection.close()

    def _append_validated_result(
        self,
        *,
        claim_id: str,
        observation: EvidenceObservation,
        completed_at: str,
        artifact_sha256: str,
        completed_output_sha256: str,
        payload: Mapping[str, Any],
        validation_contract: str,
    ) -> ResultReceipt:
        """Append output already validated by the named in-process contract.

        This is private so callers cannot bypass
        :meth:`ingest_completed_route_acquisition`.  The synthetic contract is
        retained solely for crash/transaction unit tests and can never make an
        export complete or analysis-ready.
        """

        claim_identity = _identifier(claim_id, "claim_id")
        if not isinstance(observation, EvidenceObservation):
            raise LedgerError("observation must be an EvidenceObservation")
        completed = _timestamp(completed_at, "completed_at")
        artifact = _digest(artifact_sha256, "artifact_sha256")
        completed_output = _digest(
            completed_output_sha256, "completed_output_sha256"
        )
        if validation_contract not in {
            PROTOCOL_RESULT_VALIDATION_CONTRACT,
            _TEST_ONLY_RESULT_VALIDATION_CONTRACT,
        }:
            raise LedgerError("unknown completed-result validation contract")
        if observation.metadata.get("artifact_sha256") != artifact:
            raise LedgerError(
                "observation artifact_sha256 differs from the raw artifact identity"
            )
        _, payload_object = _canonical_object(dict(payload), "result payload")
        _reject_credential_material(payload_object, "result payload")
        if validation_contract == PROTOCOL_RESULT_VALIDATION_CONTRACT:
            canonical_output = strict_json_dumps(payload_object, indent=2) + "\n"
            loaded_payload = load_route_acquisition_record(
                io.StringIO(canonical_output)
            )
            if (
                loaded_payload != payload_object
                or payload_object.get("observation") != observation.to_dict()
                or payload_object.get("acquisition_id")
                != observation.acquisition_id
                or _sha256_bytes(canonical_output.encode()) != completed_output
            ):
                raise LedgerError(
                    "validated orchestration payload differs from its exact result"
                )
        connection = self._connect()
        try:
            with _immediate_transaction(connection):
                row = connection.execute(
                    """
                    SELECT c.claim_id, c.claimed_at, c.dispatch_id,
                           c.acquisition_id, p.decision_json
                    FROM claims AS c
                    JOIN dispatch_intents AS d ON d.dispatch_id = c.dispatch_id
                    JOIN policy_decisions AS p ON p.decision_id = d.decision_id
                    WHERE c.claim_id = ?
                    """,
                    (claim_identity,),
                ).fetchone()
                if row is None:
                    raise LedgerError("result claim_id is absent from the ledger")
                acquisition = cast(str, row["acquisition_id"])
                if completed < row["claimed_at"]:
                    raise LedgerError("completed_at cannot precede claimed_at")
                if observation.acquisition_id != acquisition:
                    raise LedgerError(
                        "result observation does not use the claimed acquisition_id"
                    )
                if observation.privileged_inputs:
                    raise LedgerError(
                        "live policy results cannot contain privileged inputs"
                    )
                decision = LoggedPolicyDecision.from_dict(
                    _decode_record(
                        cast(str, row["decision_json"]), "stored policy decision"
                    )
                )
                if (
                    decision.terminal
                    or decision.chosen_offer.evidence_kind != observation.kind
                ):
                    raise LedgerError(
                        "result observation kind differs from the concrete policy action"
                    )
                if validation_contract == PROTOCOL_RESULT_VALIDATION_CONTRACT:
                    route_provenance = observation.metadata.get("route_provenance")
                    if not isinstance(route_provenance, Mapping):
                        raise LedgerError(
                            "protocol result omits validated route provenance"
                        )
                    expected_route_identity = {
                        "instance_id": decision.instance_id,
                        "candidate_id": decision.candidate_id,
                        "acquisition_id": acquisition,
                        "route_action": decision.chosen_offer.route_action.value,
                        "expected_evidence_kind": observation.kind.value,
                    }
                    if any(
                        route_provenance.get(key) != expected
                        for key, expected in expected_route_identity.items()
                    ):
                        raise LedgerError(
                            "validated route provenance differs from the concrete "
                            "logged policy decision"
                        )
                record_body = {
                    "dispatch_id": row["dispatch_id"],
                    "claim_id": claim_identity,
                    "acquisition_id": acquisition,
                    "completed_at": completed,
                    "artifact_sha256": artifact,
                    "completed_output_sha256": completed_output,
                    "validation_contract": validation_contract,
                    "observation": observation.to_dict(),
                    "payload": payload_object,
                }
                result_id = "out-" + _canonical_sha256(record_body)[:32]
                record = {"result_id": result_id, **record_body}
                record_json, record_sha = _record(record, "result record")
                existing = connection.execute(
                    "SELECT result_id, record_json, record_sha256 FROM results "
                    "WHERE acquisition_id = ?",
                    (acquisition,),
                ).fetchone()
                if existing is not None:
                    if existing["record_json"] != record_json:
                        raise LedgerConflict(
                            "result retry differs from the immutable completed output"
                        )
                    return ResultReceipt(
                        result_id=cast(str, existing["result_id"]),
                        acquisition_id=acquisition,
                        result_sha256=cast(str, existing["record_sha256"]),
                        inserted=False,
                    )
                if connection.execute(
                    "SELECT 1 FROM incidents WHERE acquisition_id = ?",
                    (acquisition,),
                ).fetchone() is not None:
                    raise TaskHalted(
                        "task-halt incident already resolved the ambiguous claim"
                    )
                observation_json = strict_json_dumps(observation.to_dict())
                payload_json = strict_json_dumps(payload_object)
                connection.execute(
                    """
                    INSERT INTO results(
                        result_id, dispatch_id, claim_id, acquisition_id,
                        completed_at, artifact_sha256, observation_json,
                        completed_output_sha256, validation_contract, payload_json,
                        record_json, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_id,
                        row["dispatch_id"],
                        claim_identity,
                        acquisition,
                        completed,
                        artifact,
                        observation_json,
                        completed_output,
                        validation_contract,
                        payload_json,
                        record_json,
                        record_sha,
                    ),
                )
                self._append_event(
                    connection,
                    event_kind="result_ingested",
                    subject_id=result_id,
                    occurred_at=completed,
                    details={
                        "claim_id": claim_identity,
                        "acquisition_id": acquisition,
                        "artifact_sha256": artifact,
                        "completed_output_sha256": completed_output,
                        "validation_contract": validation_contract,
                    },
                )
                return ResultReceipt(
                    result_id=result_id,
                    acquisition_id=acquisition,
                    result_sha256=record_sha,
                    inserted=True,
                )
        finally:
            connection.close()

    def ingest_completed_route_acquisition(
        self,
        *,
        claim_id: str,
        record: Mapping[str, Any],
        manifest_before: ValidityManifest,
        decision: RouteDecision,
        plan: RouteAcquisitionPlan,
        completed_at: str,
    ) -> ResultReceipt:
        """Validate the retained orchestrator output, then append it exactly.

        The orchestration validator re-reads the durable output and raw artifact
        and binds them to independently retained plan/manifest/route preimages.
        The ledger then stores that canonical completed record unchanged as the
        result payload; it does not define a competing receipt format.
        """

        claimed = self.load_claimed_dispatch_envelope(claim_id)
        claimed.dispatch.validate_execution_inputs(
            manifest_before=manifest_before,
            route_decision=decision,
            plan=plan,
        )
        result = validate_completed_route_acquisition(
            record,
            manifest_before=manifest_before,
            decision=decision,
            plan=plan,
        )
        raw_artifact_sha256 = _digest(
            result.observation.metadata.get("artifact_sha256"),
            "validated observation artifact_sha256",
        )
        return self._append_validated_result(
            claim_id=claim_id,
            observation=result.observation,
            completed_at=completed_at,
            artifact_sha256=raw_artifact_sha256,
            completed_output_sha256=result.output_sha256,
            payload=record,
            validation_contract=PROTOCOL_RESULT_VALIDATION_CONTRACT,
        )

    def _ingest_completed_route_acquisition_for_test_only(
        self,
        *,
        claim_id: str,
        record: Mapping[str, Any],
        manifest_before: ValidityManifest,
        decision: RouteDecision,
        plan: RouteAcquisitionPlan,
        completed_at: str,
    ) -> ResultReceipt:
        """Exercise strict orchestration recovery without a production spec.

        This compatibility seam is deliberately private and its validation
        contract can never make an export complete or analysis-ready.
        """

        result = validate_completed_route_acquisition(
            record,
            manifest_before=manifest_before,
            decision=decision,
            plan=plan,
        )
        raw_artifact_sha256 = _digest(
            result.observation.metadata.get("artifact_sha256"),
            "validated observation artifact_sha256",
        )
        return self._append_validated_result(
            claim_id=claim_id,
            observation=result.observation,
            completed_at=completed_at,
            artifact_sha256=raw_artifact_sha256,
            completed_output_sha256=result.output_sha256,
            payload=record,
            validation_contract=_TEST_ONLY_RESULT_VALIDATION_CONTRACT,
        )

    def record_claimed_crash(
        self,
        *,
        claim_id: str,
        occurred_at: str,
        reason_code: str,
        details: Mapping[str, Any],
    ) -> IncidentReceipt:
        """Resolve an ambiguous permanent claim by halting its task."""

        claim_identity = _identifier(claim_id, "claim_id")
        occurred = _timestamp(occurred_at, "occurred_at")
        reason = _reason(reason_code, "reason_code")
        _, details_object = _canonical_object(dict(details), "incident details")
        _reject_credential_material(details_object, "incident details")
        connection = self._connect()
        try:
            with _immediate_transaction(connection):
                row = connection.execute(
                    """
                    SELECT c.dispatch_id, c.acquisition_id, c.claimed_at,
                           r.task_id
                    FROM claims AS c
                    JOIN dispatch_intents AS d ON d.dispatch_id = c.dispatch_id
                    JOIN rounds AS r ON r.round_sha256 = d.round_sha256
                    WHERE c.claim_id = ?
                    """,
                    (claim_identity,),
                ).fetchone()
                if row is None:
                    raise LedgerError("incident claim_id is absent from the ledger")
                acquisition = cast(str, row["acquisition_id"])
                if occurred < row["claimed_at"]:
                    raise LedgerError("incident cannot predate its permanent claim")
                body = {
                    "task_id": row["task_id"],
                    "dispatch_id": row["dispatch_id"],
                    "claim_id": claim_identity,
                    "acquisition_id": acquisition,
                    "occurred_at": occurred,
                    "reason_code": reason,
                    "details": details_object,
                }
                incident_id = "inc-" + _canonical_sha256(body)[:32]
                record = {"incident_id": incident_id, **body}
                record_json, record_sha = _record(record, "incident record")
                existing = connection.execute(
                    "SELECT incident_id, record_json, record_sha256 FROM incidents "
                    "WHERE acquisition_id = ?",
                    (acquisition,),
                ).fetchone()
                if existing is not None:
                    if existing["record_json"] != record_json:
                        raise LedgerConflict(
                            "incident retry differs from the immutable halt record"
                        )
                    return IncidentReceipt(
                        incident_id=cast(str, existing["incident_id"]),
                        acquisition_id=acquisition,
                        incident_sha256=cast(str, existing["record_sha256"]),
                        inserted=False,
                    )
                if connection.execute(
                    "SELECT 1 FROM results WHERE acquisition_id = ?",
                    (acquisition,),
                ).fetchone() is not None:
                    raise LedgerConflict(
                        "completed result cannot be replaced by a crash incident"
                    )
                connection.execute(
                    """
                    INSERT INTO incidents(
                        incident_id, task_id, dispatch_id, claim_id,
                        acquisition_id, occurred_at, reason_code, details_json,
                        record_json, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        row["task_id"],
                        row["dispatch_id"],
                        claim_identity,
                        acquisition,
                        occurred,
                        reason,
                        strict_json_dumps(details_object),
                        record_json,
                        record_sha,
                    ),
                )
                self._append_event(
                    connection,
                    event_kind="task_halted",
                    subject_id=incident_id,
                    occurred_at=occurred,
                    details={
                        "task_id": row["task_id"],
                        "claim_id": claim_identity,
                        "acquisition_id": acquisition,
                        "reason_code": reason,
                    },
                )
                return IncidentReceipt(
                    incident_id=incident_id,
                    acquisition_id=acquisition,
                    incident_sha256=record_sha,
                    inserted=True,
                )
        finally:
            connection.close()

    def commit_selection(
        self,
        selection: TaskSelectionDecision,
        *,
        committed_at: str,
    ) -> SelectionCommitReceipt:
        bindings = self._require_bindings()
        if not isinstance(selection, TaskSelectionDecision):
            raise LedgerError("selection must be a TaskSelectionDecision")
        committed = _timestamp(committed_at, "selection committed_at")
        if committed < selection.scheduled_at:
            raise LedgerError("selection commit cannot predate its decision")
        selection_json = strict_json_dumps(selection.to_dict())
        connection = self._connect()
        try:
            with _immediate_transaction(connection):
                existing = connection.execute(
                    "SELECT selection_sha256, selection_json, committed_at "
                    "FROM selections WHERE task_id = ?",
                    (selection.task_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["selection_sha256"] != selection.decision_sha256
                        or existing["selection_json"] != selection_json
                    ):
                        raise LedgerConflict(
                            "task already has a different immutable selection"
                        )
                    return SelectionCommitReceipt(
                        selection_sha256=selection.decision_sha256,
                        committed_at=cast(str, existing["committed_at"]),
                        inserted=False,
                    )
                incident = self._task_incident(connection, selection.task_id)
                if incident is not None:
                    raise TaskHalted("halted task cannot commit a selection")
                rounds = self._load_rounds(connection, selection.task_id)
                if not rounds:
                    raise RoundNotReady("selection requires a durable task trajectory")
                self._assert_all_prior_dispatches_resolved(
                    connection, selection.task_id
                )
                validate_task_trajectory(rounds, selection, bindings=bindings)
                record = {
                    "selection_sha256": selection.decision_sha256,
                    "task_id": selection.task_id,
                    "final_round_sha256": rounds[-1].decision_sha256,
                    "committed_at": committed,
                    "selection": selection.to_dict(),
                }
                record_json, record_sha = _record(record, "selection record")
                connection.execute(
                    """
                    INSERT INTO selections(
                        selection_sha256, task_id, final_round_sha256,
                        selection_json, committed_at, record_json, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        selection.decision_sha256,
                        selection.task_id,
                        rounds[-1].decision_sha256,
                        selection_json,
                        committed,
                        record_json,
                        record_sha,
                    ),
                )
                self._append_event(
                    connection,
                    event_kind="selection_committed",
                    subject_id=selection.decision_sha256,
                    occurred_at=committed,
                    details={
                        "task_id": selection.task_id,
                        "final_round_sha256": rounds[-1].decision_sha256,
                    },
                )
                return SelectionCommitReceipt(
                    selection_sha256=selection.decision_sha256,
                    committed_at=committed,
                    inserted=True,
                )
        finally:
            connection.close()

    def table_counts(self) -> dict[str, int]:
        connection = self._connect()
        try:
            return {
                table: int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in _TABLE_ORDER
            }
        finally:
            connection.close()

    def export_jsonl(self) -> str:
        """Return a deterministic, line-hash-chained archival representation."""

        connection = self._connect()
        lines: list[str] = []
        prior = EXPORT_GENESIS_SHA256
        sequence = 0
        try:
            connection.execute("BEGIN")
            for table in _TABLE_ORDER:
                primary_key = _TABLE_PRIMARY_KEYS[table]
                rows = connection.execute(
                    f"SELECT {primary_key}, record_json, record_sha256 "
                    f"FROM {table} ORDER BY {primary_key}"
                ).fetchall()
                for row in rows:
                    record = _decode_record(
                        cast(str, row["record_json"]),
                        f"{table} export record",
                    )
                    body = {
                        "schema_version": EXPORT_SCHEMA_VERSION,
                        "chain_contract": EXPORT_CHAIN_CONTRACT,
                        "sequence": sequence,
                        "table": table,
                        "record_key": _ordered_record_key(
                            table, row[primary_key]
                        ),
                        "record_sha256": row["record_sha256"],
                        "record": record,
                        "prior_line_sha256": prior,
                    }
                    line_sha = _canonical_sha256(body)
                    line = {**body, "line_sha256": line_sha}
                    lines.append(strict_json_dumps(line))
                    prior = line_sha
                    sequence += 1
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return "\n".join(lines) + "\n"

    def audit(self, *, require_complete: bool = False) -> ExportAudit:
        """Check SQLite integrity, foreign keys, export chain, and scheduler joins."""

        bindings = self._require_bindings()
        connection = self._connect()
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchall()
            if [row[0] for row in integrity] != ["ok"]:
                raise LedgerError(f"SQLite integrity_check failed: {integrity}")
            foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign:
                raise LedgerError(f"SQLite foreign_key_check failed: {foreign}")
        finally:
            connection.close()
        return audit_jsonl_export(
            self.export_jsonl(),
            bindings=bindings,
            require_complete=require_complete,
        )

    def assert_analysis_ready(self) -> ExportAudit:
        """Require a complete exact-frame ledger before any OPE analysis."""

        audit = self.audit(require_complete=True)
        if not audit.analysis_ready:
            raise RoundNotReady(
                "ledger is internally complete but does not cover the exact frozen task frame"
            )
        return audit


def _export_record_key(table: str, record: Mapping[str, Any]) -> str:
    fields = {
        "ledger_meta": "meta_key",
        "action_specs": "action_spec_sha256",
        "rounds": "round_sha256",
        "policy_decisions": "decision_id",
        "dispatch_intents": "dispatch_id",
        "resource_reservations": "reservation_id",
        "claims": "claim_id",
        "results": "result_id",
        "incidents": "incident_id",
        "selections": "selection_sha256",
        "events": "event_sequence",
    }
    field_name = fields[table]
    if field_name not in record:
        raise LedgerError(f"{table} export record omits {field_name}")
    return _ordered_record_key(table, record[field_name])


def _audit_event_chain(records: Sequence[dict[str, Any]]) -> str:
    prior = EVENT_GENESIS_SHA256
    for sequence, record in enumerate(records):
        expected_fields = {
            "schema_version",
            "chain_contract",
            "event_sequence",
            "event_kind",
            "subject_id",
            "occurred_at",
            "details",
            "prior_event_sha256",
            "event_id",
            "event_sha256",
        }
        if set(record) != expected_fields:
            raise LedgerError("event record fields differ from the frozen schema")
        if (
            record["schema_version"] != LEDGER_SCHEMA_VERSION
            or record["chain_contract"] != EVENT_CHAIN_CONTRACT
            or record["event_sequence"] != sequence
            or record["prior_event_sha256"] != prior
        ):
            raise LedgerError("event hash chain identity or sequence differs")
        _timestamp(record["occurred_at"], "event occurred_at")
        body = {key: value for key, value in record.items() if key not in {
            "event_id",
            "event_sha256",
        }}
        expected_sha = _canonical_sha256(body)
        if (
            record["event_sha256"] != expected_sha
            or record["event_id"] != "evt-" + expected_sha[:32]
        ):
            raise LedgerError("event digest differs from its canonical content")
        prior = expected_sha
    return prior


def audit_jsonl_export(
    value: str,
    *,
    bindings: SchedulerBindings,
    require_complete: bool = False,
) -> ExportAudit:
    """Strictly reload and semantically audit one deterministic ledger export."""

    if not isinstance(bindings, SchedulerBindings):
        raise LedgerError("export audit requires SchedulerBindings")
    if not isinstance(value, str) or not value.endswith("\n"):
        raise LedgerError("ledger export must be newline-terminated text")
    raw_lines = value.splitlines()
    if not raw_lines:
        raise LedgerError("ledger export cannot be empty")
    records: dict[str, list[dict[str, Any]]] = {
        table: [] for table in _TABLE_ORDER
    }
    prior = EXPORT_GENESIS_SHA256
    previous_table_index = -1
    previous_key = ""
    for sequence, raw_line in enumerate(raw_lines):
        try:
            decoded = strict_json_loads(raw_line)
        except ValueError as exc:
            raise LedgerError(f"invalid export line {sequence}: {exc}") from exc
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) for key in decoded
        ):
            raise LedgerError("every export line must be a JSON object")
        line = cast(dict[str, Any], decoded)
        if strict_json_dumps(line) != raw_line:
            raise LedgerError("export line is not canonical JSON")
        expected_fields = {
            "schema_version",
            "chain_contract",
            "sequence",
            "table",
            "record_key",
            "record_sha256",
            "record",
            "prior_line_sha256",
            "line_sha256",
        }
        if set(line) != expected_fields:
            raise LedgerError("export line fields differ from the frozen schema")
        if (
            line["schema_version"] != EXPORT_SCHEMA_VERSION
            or line["chain_contract"] != EXPORT_CHAIN_CONTRACT
            or line["sequence"] != sequence
            or line["prior_line_sha256"] != prior
        ):
            raise LedgerError("export sequence or prior-line hash differs")
        table = line["table"]
        if not isinstance(table, str) or table not in records:
            raise LedgerError("export line names an unknown table")
        table_index = _TABLE_ORDER.index(table)
        key = line["record_key"]
        if not isinstance(key, str):
            raise LedgerError("export record_key must be a string")
        if table_index < previous_table_index or (
            table_index == previous_table_index and key <= previous_key
        ):
            raise LedgerError("export records are not in deterministic key order")
        if table_index != previous_table_index:
            previous_key = ""
        previous_table_index = table_index
        previous_key = key
        record = line["record"]
        if not isinstance(record, dict) or not all(
            isinstance(item, str) for item in record
        ):
            raise LedgerError("export record must be a JSON object")
        record_object = cast(dict[str, Any], record)
        record_sha = _canonical_sha256(record_object)
        if (
            line["record_sha256"] != record_sha
            or _export_record_key(table, record_object) != key
        ):
            raise LedgerError("export record key or content digest differs")
        body = {key_name: item for key_name, item in line.items() if key_name != "line_sha256"}
        expected_line_sha = _canonical_sha256(body)
        if line["line_sha256"] != expected_line_sha:
            raise LedgerError("export line hash differs from canonical content")
        prior = expected_line_sha
        records[table].append(record_object)

    meta = records["ledger_meta"]
    if meta != [{"meta_key": "schema_version", "meta_value": LEDGER_SCHEMA_VERSION}]:
        raise LedgerError("export ledger schema identity differs")

    for spec in records["action_specs"]:
        if set(spec) != {"action_spec_sha256", "preimage_base64"}:
            raise LedgerError("action-spec export fields differ")
        digest = _digest(spec["action_spec_sha256"], "action spec digest")
        try:
            preimage = base64.b64decode(
                cast(str, spec["preimage_base64"]), validate=True
            )
        except (TypeError, ValueError) as exc:
            raise LedgerError("action-spec preimage is not canonical base64") from exc
        if base64.b64encode(preimage).decode("ascii") != spec["preimage_base64"]:
            raise LedgerError("action-spec base64 spelling is not canonical")
        try:
            spec_value = strict_json_loads(preimage.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise LedgerError("export action spec is not strict UTF-8 JSON") from exc
        if (
            not isinstance(spec_value, dict)
            or not spec_value
            or strict_json_dumps(spec_value).encode() != preimage
            or canonical_action_spec_sha256(spec_value) != digest
        ):
            raise LedgerError("export action-spec canonical preimage digest differs")
        _reject_credential_material(spec_value, "export action-spec preimage")
    spec_ids = {
        cast(str, item["action_spec_sha256"])
        for item in records["action_specs"]
    }

    rounds_by_sha: dict[str, TaskRoundDecision] = {}
    rounds_by_task: dict[str, list[TaskRoundDecision]] = defaultdict(list)
    round_committed_at: dict[str, str] = {}
    for record in records["rounds"]:
        if set(record) != {
            "round_sha256",
            "task_id",
            "round_index",
            "committed_at",
            "round",
        }:
            raise LedgerError("round export fields differ from the frozen schema")
        round_value = record.get("round")
        round_decision = TaskRoundDecision.from_dict(round_value)
        if (
            record.get("round_sha256") != round_decision.decision_sha256
            or record.get("task_id") != round_decision.task_id
            or record.get("round_index") != round_decision.round_index
        ):
            raise LedgerError("round export metadata contradicts its exact decision")
        committed_at = _timestamp(
            record.get("committed_at"), "round committed_at"
        )
        if committed_at < round_decision.scheduled_at:
            raise LedgerError("round export commit predates its decision")
        round_decision.validate_against_bindings(bindings)
        if round_decision.decision_sha256 in rounds_by_sha:
            raise LedgerError("export repeats a round identity")
        rounds_by_sha[round_decision.decision_sha256] = round_decision
        round_committed_at[round_decision.decision_sha256] = committed_at
        rounds_by_task[round_decision.task_id].append(round_decision)
    for task_rounds in rounds_by_task.values():
        task_rounds.sort(key=lambda item: item.round_index)
        validate_task_round_chain(task_rounds, bindings=bindings)

    policy_by_id: dict[str, tuple[LoggedPolicyDecision, str, int]] = {}
    for record in records["policy_decisions"]:
        if set(record) != {
            "decision_id",
            "round_sha256",
            "candidate_position",
            "decision",
        }:
            raise LedgerError(
                "policy-decision export fields differ from the frozen schema"
            )
        decision = LoggedPolicyDecision.from_dict(record.get("decision"))
        if record.get("decision_id") != decision.decision_id:
            raise LedgerError("policy record decision_id contradicts its decision")
        round_sha = _digest(record.get("round_sha256"), "policy round_sha256")
        position = record.get("candidate_position")
        if isinstance(position, bool) or not isinstance(position, int):
            raise LedgerError("policy candidate_position must be an integer")
        if round_sha not in rounds_by_sha:
            raise LedgerError("policy decision references an absent round")
        if decision.decision_id in policy_by_id:
            raise LedgerError("export repeats a policy decision_id")
        policy_by_id[decision.decision_id] = (decision, round_sha, position)

    embedded_policy: dict[str, tuple[LoggedPolicyDecision, str, int]] = {}
    for round_sha, round_decision in rounds_by_sha.items():
        for scheduled in round_decision.scheduled_decisions:
            logged = scheduled.logged_policy_decision
            embedded_policy[logged.decision_id] = (
                logged,
                round_sha,
                scheduled.candidate_position,
            )
    if set(policy_by_id) != set(embedded_policy):
        raise LedgerError("export policy rows differ from embedded round decisions")
    for decision_id, (decision, round_sha, position) in policy_by_id.items():
        expected_decision, expected_round, expected_position = embedded_policy[
            decision_id
        ]
        if (
            decision.to_dict() != expected_decision.to_dict()
            or round_sha != expected_round
            or position != expected_position
            or decision.chosen_offer.action_spec_sha256 not in spec_ids
        ):
            raise LedgerError("policy row differs from its exact embedded decision")

    expected_spec_ids = {
        offer.action_spec_sha256
        for round_decision in rounds_by_sha.values()
        for state in round_decision.candidates
        for offer in state.action_catalog
    }
    if spec_ids != expected_spec_ids:
        raise LedgerError(
            "action-spec export differs from every complete round catalog preimage"
        )

    dispatch_by_id: dict[str, dict[str, Any]] = {}
    dispatch_by_acquisition: dict[str, dict[str, Any]] = {}
    for record in records["dispatch_intents"]:
        dispatch_id = cast(str, record.get("dispatch_id"))
        decision_id = cast(str, record.get("decision_id"))
        if decision_id not in policy_by_id:
            raise LedgerError("dispatch references an absent policy decision")
        decision, round_sha, position = policy_by_id[decision_id]
        if decision.terminal:
            raise LedgerError("terminal policy decision has a dispatch intent")
        expected = _dispatch_record(round_sha, decision, position)
        if record != expected:
            raise LedgerError("dispatch record differs from the concrete policy action")
        acquisition = cast(str, record["acquisition_id"])
        if dispatch_id in dispatch_by_id or acquisition in dispatch_by_acquisition:
            raise LedgerError("export repeats a dispatch or acquisition identity")
        dispatch_by_id[dispatch_id] = record
        dispatch_by_acquisition[acquisition] = record
    expected_dispatch_decisions = {
        decision_id
        for decision_id, (decision, _, _) in policy_by_id.items()
        if not decision.terminal
    }
    if {
        cast(str, item["decision_id"]) for item in dispatch_by_id.values()
    } != expected_dispatch_decisions:
        raise LedgerError("dispatch set differs from all nonterminal policy decisions")

    reservation_by_dispatch: dict[str, dict[str, Any]] = {}
    resource_keys: set[str] = set()
    for record in records["resource_reservations"]:
        dispatch_id = cast(str, record.get("dispatch_id"))
        if dispatch_id not in dispatch_by_id or dispatch_id in reservation_by_dispatch:
            raise LedgerError("reservation dispatch identity is absent or repeated")
        request = ReservationRequest(
            acquisition_id=cast(str, record.get("acquisition_id")),
            resource_kind=cast(str, record.get("resource_kind")),
            resource_key=cast(str, record.get("resource_key")),
            details=cast(Mapping[str, Any], record.get("details")),
        )
        expected = _reservation_record(dispatch_by_id[dispatch_id], request)
        if record != expected:
            raise LedgerError("reservation differs from its dispatch-bound identity")
        if request.resource_key in resource_keys:
            raise LedgerError("export reuses an exclusive resource key")
        resource_keys.add(request.resource_key)
        decision = policy_by_id[
            cast(str, dispatch_by_id[dispatch_id]["decision_id"])
        ][0]
        if (
            decision.chosen_action_id == "full_repeat"
            and request.resource_kind != "fresh_worktree"
        ):
            raise LedgerError("full_repeat export lacks a fresh worktree reservation")
        reservation_by_dispatch[dispatch_id] = record
    if set(reservation_by_dispatch) != set(dispatch_by_id):
        raise LedgerError("every dispatch must have exactly one durable reservation")

    claims_by_id: dict[str, dict[str, Any]] = {}
    claim_by_dispatch: dict[str, dict[str, Any]] = {}
    for record in records["claims"]:
        if set(record) != {
            "claim_id",
            "dispatch_id",
            "acquisition_id",
            "claimant",
            "claimed_at",
        }:
            raise LedgerError("claim export fields differ from the frozen schema")
        claim_id = cast(str, record.get("claim_id"))
        dispatch_id = cast(str, record.get("dispatch_id"))
        if dispatch_id not in dispatch_by_id or dispatch_id in claim_by_dispatch:
            raise LedgerError("claim dispatch identity is absent or repeated")
        body = {key: item for key, item in record.items() if key != "claim_id"}
        if claim_id != "clm-" + _canonical_sha256(body)[:32]:
            raise LedgerError("claim identity differs from its immutable content")
        if record.get("acquisition_id") != dispatch_by_id[dispatch_id]["acquisition_id"]:
            raise LedgerError("claim acquisition differs from its dispatch")
        _identifier(record.get("claimant"), "export claimant")
        claimed_at = _timestamp(record.get("claimed_at"), "export claimed_at")
        dispatch_round_sha = cast(
            str, dispatch_by_id[dispatch_id]["round_sha256"]
        )
        if claimed_at < round_committed_at[dispatch_round_sha]:
            raise LedgerError("export claim predates its committed round")
        claims_by_id[claim_id] = record
        claim_by_dispatch[dispatch_id] = record

    results_by_acquisition: dict[str, dict[str, Any]] = {}
    protocol_result_acquisitions: set[str] = set()
    for record in records["results"]:
        expected_result_fields = {
            "result_id",
            "dispatch_id",
            "claim_id",
            "acquisition_id",
            "completed_at",
            "artifact_sha256",
            "completed_output_sha256",
            "validation_contract",
            "observation",
            "payload",
        }
        if set(record) != expected_result_fields:
            raise LedgerError("result export fields differ from the frozen schema")
        result_id = cast(str, record.get("result_id"))
        claim_id = cast(str, record.get("claim_id"))
        if claim_id not in claims_by_id:
            raise LedgerError("result references an absent permanent claim")
        claim = claims_by_id[claim_id]
        acquisition = cast(str, record.get("acquisition_id"))
        if (
            acquisition != claim["acquisition_id"]
            or record.get("dispatch_id") != claim["dispatch_id"]
            or acquisition in results_by_acquisition
        ):
            raise LedgerError("result claim/acquisition identity differs or repeats")
        body = {key: item for key, item in record.items() if key != "result_id"}
        if result_id != "out-" + _canonical_sha256(body)[:32]:
            raise LedgerError("result identity differs from its exact content")
        if record.get("completed_at") < claim["claimed_at"]:
            raise LedgerError("export result predates its claim")
        _timestamp(record.get("completed_at"), "export result completed_at")
        _digest(record.get("artifact_sha256"), "export artifact_sha256")
        _digest(
            record.get("completed_output_sha256"),
            "export completed_output_sha256",
        )
        validation_contract = record.get("validation_contract")
        _reject_credential_material(record.get("payload"), "export result payload")
        if validation_contract == PROTOCOL_RESULT_VALIDATION_CONTRACT:
            payload = record.get("payload")
            canonical_output = strict_json_dumps(payload, indent=2) + "\n"
            loaded = load_route_acquisition_record(io.StringIO(canonical_output))
            if loaded != payload or _sha256_bytes(canonical_output.encode()) != (
                record.get("completed_output_sha256")
            ):
                raise LedgerError(
                    "protocol result payload/output digest differs from its completed record"
                )
            protocol_result_acquisitions.add(acquisition)
        elif validation_contract != _TEST_ONLY_RESULT_VALIDATION_CONTRACT:
            raise LedgerError("result export has an unknown validation contract")
        observation = EvidenceObservation.from_dict(record.get("observation"))
        dispatch = dispatch_by_id[cast(str, claim["dispatch_id"])]
        decision = policy_by_id[cast(str, dispatch["decision_id"])][0]
        if (
            observation.acquisition_id != acquisition
            or observation.kind != decision.chosen_offer.evidence_kind
            or observation.privileged_inputs
            or observation.metadata.get("artifact_sha256")
            != record.get("artifact_sha256")
        ):
            raise LedgerError("export result is not the typed policy acquisition")
        if validation_contract == PROTOCOL_RESULT_VALIDATION_CONTRACT:
            route_provenance = observation.metadata.get("route_provenance")
            expected_route_identity = {
                "instance_id": decision.instance_id,
                "candidate_id": decision.candidate_id,
                "acquisition_id": acquisition,
                "route_action": decision.chosen_offer.route_action.value,
                "expected_evidence_kind": observation.kind.value,
            }
            if not isinstance(route_provenance, Mapping) or any(
                route_provenance.get(key) != expected
                for key, expected in expected_route_identity.items()
            ):
                raise LedgerError(
                    "protocol result route provenance differs from its policy decision"
                )
        results_by_acquisition[acquisition] = record

    incidents_by_acquisition: dict[str, dict[str, Any]] = {}
    halted_tasks: set[str] = set()
    halted_at_round: dict[str, int] = {}
    for record in records["incidents"]:
        if set(record) != {
            "incident_id",
            "task_id",
            "dispatch_id",
            "claim_id",
            "acquisition_id",
            "occurred_at",
            "reason_code",
            "details",
        }:
            raise LedgerError("incident export fields differ from the frozen schema")
        incident_id = cast(str, record.get("incident_id"))
        claim_id = cast(str, record.get("claim_id"))
        if claim_id not in claims_by_id:
            raise LedgerError("incident references an absent permanent claim")
        claim = claims_by_id[claim_id]
        acquisition = cast(str, record.get("acquisition_id"))
        body = {key: item for key, item in record.items() if key != "incident_id"}
        if (
            incident_id != "inc-" + _canonical_sha256(body)[:32]
            or acquisition != claim["acquisition_id"]
            or record.get("dispatch_id") != claim["dispatch_id"]
            or acquisition in incidents_by_acquisition
            or acquisition in results_by_acquisition
        ):
            raise LedgerError("incident identity differs, repeats, or conflicts")
        _timestamp(record.get("occurred_at"), "export incident occurred_at")
        if record.get("occurred_at") < claim["claimed_at"]:
            raise LedgerError("export incident predates its permanent claim")
        _reason(record.get("reason_code"), "export incident reason_code")
        _reject_credential_material(
            record.get("details"), "export incident details"
        )
        task_id = cast(str, record.get("task_id"))
        dispatch_round = rounds_by_sha[
            cast(str, dispatch_by_id[cast(str, claim["dispatch_id"])]["round_sha256"])
        ]
        if task_id != dispatch_round.task_id:
            raise LedgerError("incident task differs from its dispatch round")
        incidents_by_acquisition[acquisition] = record
        halted_tasks.add(task_id)
        halted_at_round[task_id] = dispatch_round.round_index

    for task_id, task_rounds in rounds_by_task.items():
        for previous, current in zip(task_rounds, task_rounds[1:]):
            prior_acquisitions = {
                item.logged_policy_decision.acquisition_id
                for item in previous.scheduled_decisions
                if not item.logged_policy_decision.terminal
            }
            if not cast(set[str], prior_acquisitions).issubset(results_by_acquisition):
                raise LedgerError(
                    "export advances a round before all sibling results exist"
                )
            halt_round = halted_at_round.get(task_id)
            if halt_round is not None and current.round_index > halt_round:
                raise LedgerError("export advances a task after a halt incident")
            current_states = {item.candidate_id: item for item in current.candidates}
            for scheduled in previous.scheduled_decisions:
                decision = scheduled.logged_policy_decision
                if decision.terminal:
                    continue
                assert decision.acquisition_id is not None
                successor = current_states[decision.candidate_id]
                assert successor.bound_router_decision is not None
                observation = (
                    successor.bound_router_decision.router_state.evidence_history[-1]
                )
                persisted = EvidenceObservation.from_dict(
                    results_by_acquisition[decision.acquisition_id]["observation"]
                )
                if observation != _router_observation_projection(persisted):
                    raise LedgerError(
                        "export successor state differs from the durable result"
                    )

    selections_by_task: dict[str, TaskSelectionDecision] = {}
    for record in records["selections"]:
        if set(record) != {
            "selection_sha256",
            "task_id",
            "final_round_sha256",
            "committed_at",
            "selection",
        }:
            raise LedgerError("selection export fields differ from the frozen schema")
        selection = TaskSelectionDecision.from_dict(record.get("selection"))
        if (
            record.get("selection_sha256") != selection.decision_sha256
            or record.get("task_id") != selection.task_id
            or selection.task_id in selections_by_task
        ):
            raise LedgerError("selection export identity differs or repeats")
        if selection.task_id in halted_tasks:
            raise LedgerError("halted task cannot have a selection")
        task_rounds = rounds_by_task.get(selection.task_id, [])
        if not task_rounds:
            raise LedgerError("selection export has no durable round chain")
        all_acquisitions = {
            item.logged_policy_decision.acquisition_id
            for round_decision in task_rounds
            for item in round_decision.scheduled_decisions
            if not item.logged_policy_decision.terminal
        }
        if not cast(set[str], all_acquisitions).issubset(results_by_acquisition):
            raise LedgerError("selection precedes one or more durable results")
        validate_task_trajectory(task_rounds, selection, bindings=bindings)
        if record.get("final_round_sha256") != task_rounds[-1].decision_sha256:
            raise LedgerError("selection final-round identity differs")
        committed_at = _timestamp(
            record.get("committed_at"), "selection committed_at"
        )
        if committed_at < selection.scheduled_at:
            raise LedgerError("selection export commit predates its decision")
        selections_by_task[selection.task_id] = selection

    event_head = _audit_event_chain(records["events"])
    event_pairs = Counter(
        (cast(str, item["event_kind"]), cast(str, item["subject_id"]))
        for item in records["events"]
    )
    expected_pairs = Counter(
        [("round_committed", key) for key in rounds_by_sha]
        + [("dispatch_claimed", key) for key in claims_by_id]
        + [
            ("result_ingested", cast(str, item["result_id"]))
            for item in results_by_acquisition.values()
        ]
        + [
            ("task_halted", cast(str, item["incident_id"]))
            for item in incidents_by_acquisition.values()
        ]
        + [
            ("selection_committed", item.decision_sha256)
            for item in selections_by_task.values()
        ]
    )
    if event_pairs != expected_pairs:
        raise LedgerError("event records do not exactly cover durable mutations")

    committed_tasks = set(rounds_by_task)
    selected_tasks = set(selections_by_task)
    resolved_acquisitions = set(results_by_acquisition).union(
        incidents_by_acquisition
    )
    pending_dispatch_count = len(
        set(dispatch_by_acquisition).difference(resolved_acquisitions)
    )
    all_dispatches_have_protocol_results = (
        set(dispatch_by_acquisition) == protocol_result_acquisitions
    )
    complete = (
        bool(committed_tasks)
        and pending_dispatch_count == 0
        and not halted_tasks
        and selected_tasks == committed_tasks
        and set(dispatch_by_acquisition) == set(results_by_acquisition)
        and all_dispatches_have_protocol_results
    )
    analysis_ready = complete and committed_tasks == set(bindings.frame.task_ids)
    if require_complete and not complete:
        raise RoundNotReady(
            "ledger is not complete: every committed task requires a valid selection, "
            "every dispatch requires a protocol-validated result, and incidents are forbidden"
        )

    counts = tuple((table, len(records[table])) for table in _TABLE_ORDER)
    return ExportAudit(
        record_count=sum(count for _, count in counts),
        export_head_sha256=prior,
        event_head_sha256=event_head,
        table_counts=counts,
        complete=complete,
        analysis_ready=analysis_ready,
        committed_task_count=len(committed_tasks),
        selected_task_count=len(selected_tasks),
        pending_dispatch_count=pending_dispatch_count,
        halted_task_count=len(halted_tasks),
        protocol_result_count=len(protocol_result_acquisitions),
    )
