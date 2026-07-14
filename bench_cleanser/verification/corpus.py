"""Strict paired-corpus contract for learning selective SWE verification.

The deployable pre-execution manifest is deliberately separated from labels
and counterfactual evidence.  This prevents a learned router from accidentally
receiving gold patches, hidden tests, human truth, or eventual execution
outcomes as inference features.  Curated counterfactual collection decisions
and exact live policy decisions are explicitly discriminated: live decisions
are embedded unchanged instead of being projected onto modality-level fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from math import isclose, isfinite, log
from typing import Any, TextIO
from urllib.parse import urlparse

from bench_cleanser import __version__
from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_loads,
)
from bench_cleanser.verification.manifest import validate_deployable_provenance
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    ValidityManifest,
)
from bench_cleanser.verification.policy_log import (
    LoggedPolicyDecision,
    RouterStateView,
    validate_policy_decision_chain,
)

CORPUS_SCHEMA_VERSION = "0.5.0"
MIN_ADJUDICATOR_AGREEMENT = 0.80
_PROPENSITY_TOLERANCE = 1e-12
_ACQUISITION_TRAJECTORY_CONTRACT = "bench-cleanser-acquisition-trajectory-v2"
_ROUTER_HISTORY_CONTRACT = "bench-cleanser-router-history-v1"
_ROUTER_STATE_CONTRACT = "bench-cleanser-router-state-v1"
_CURATED_DECISION_CONTRACT = "curated_collection"
_LOGGED_POLICY_DECISION_CONTRACT = "logged_policy"


class CorpusSplit(str, Enum):
    DEVELOPMENT = "development"
    CALIBRATION = "calibration"
    TEST = "test"


class CandidateType(str, Enum):
    GOLD = "gold"
    NO_OP = "no_op"
    UNDER_FIX = "under_fix"
    WRONG_FILE = "wrong_file"
    TEST_OVERFIT = "test_overfit"
    REGRESSION_INDUCING = "regression_inducing"
    EQUIVALENT_ALTERNATIVE = "equivalent_alternative"
    ALTERNATIVE_CORRECT = "alternative_correct"
    AGENT = "agent"


class EvidenceValidity(str, Enum):
    """Blinded adjudication of whether an evidence event gives a valid label."""

    VALID = "valid"
    INVALID = "invalid"
    INDETERMINATE = "indeterminate"


def _validate_adjudication_metadata(
    *,
    source: str,
    protocol_version: str,
    blinded: bool,
    annotator_count: int,
    agreement: float | None,
    notes: str,
    field_name: str,
) -> None:
    if (
        not isinstance(source, str)
        or not source.strip()
        or source != source.strip()
        or not isinstance(protocol_version, str)
        or not protocol_version.strip()
        or protocol_version != protocol_version.strip()
    ):
        raise ValueError(
            f"{field_name} source and protocol_version must be trimmed and non-empty"
        )
    if not isinstance(blinded, bool):
        raise ValueError(f"{field_name} blinded must be a boolean")
    if (
        isinstance(annotator_count, bool)
        or not isinstance(annotator_count, int)
        or annotator_count < 1
    ):
        raise ValueError(f"{field_name} annotator_count must be positive")
    if agreement is not None and (
        isinstance(agreement, bool)
        or not isinstance(agreement, (int, float))
        or not isfinite(agreement)
        or not 0.0 <= agreement <= 1.0
    ):
        raise ValueError(f"{field_name} agreement must be between 0 and 1")
    if not isinstance(notes, str):
        raise ValueError(f"{field_name} notes must be a string")


@dataclass(frozen=True)
class EvidenceValidityAdjudication:
    """Provenance-bearing truth about whether one evidence event is valid."""

    validity: EvidenceValidity
    source: str
    protocol_version: str
    blinded: bool
    annotator_count: int
    agreement: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.validity, bool) or not isinstance(
            self.validity, EvidenceValidity
        ):
            raise ValueError("validity must be an EvidenceValidity enum")
        _validate_adjudication_metadata(
            source=self.source,
            protocol_version=self.protocol_version,
            blinded=self.blinded,
            annotator_count=self.annotator_count,
            agreement=self.agreement,
            notes=self.notes,
            field_name="evidence_validity_adjudication",
        )

    @property
    def determinate_paired_ready(self) -> bool:
        return (
            self.validity != EvidenceValidity.INDETERMINATE
            and self.blinded
            and self.annotator_count >= 2
            and self.agreement is not None
            and self.agreement >= MIN_ADJUDICATOR_AGREEMENT
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "validity": self.validity.value,
            "source": self.source,
            "protocol_version": self.protocol_version,
            "blinded": self.blinded,
            "annotator_count": self.annotator_count,
            "agreement": self.agreement,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        field_name: str = "validity_adjudication",
    ) -> EvidenceValidityAdjudication:
        data = _object(value, field_name)
        allowed = {
            "validity",
            "source",
            "protocol_version",
            "blinded",
            "annotator_count",
            "agreement",
            "notes",
        }
        _reject_unknown(data, allowed, field_name)
        agreement_value = data.get("agreement")
        return cls(
            validity=_enum(
                EvidenceValidity,
                data.get("validity"),
                f"{field_name}.validity",
            ),
            source=_string(
                data.get("source"), f"{field_name}.source", nonempty=True
            ),
            protocol_version=_string(
                data.get("protocol_version"),
                f"{field_name}.protocol_version",
                nonempty=True,
            ),
            blinded=_boolean(data.get("blinded"), f"{field_name}.blinded"),
            annotator_count=_integer(
                data.get("annotator_count"), f"{field_name}.annotator_count"
            ),
            agreement=(
                None
                if agreement_value is None
                else _number(agreement_value, f"{field_name}.agreement")
            ),
            notes=_string(data.get("notes", ""), f"{field_name}.notes"),
        )


class TaskValidity(str, Enum):
    """Blinded adjudication of whether candidate correctness is well-defined."""

    VALID = "valid"
    INVALID = "invalid"
    INDETERMINATE = "indeterminate"


class CandidateCorrectness(str, Enum):
    """Candidate truth conditional on the separately adjudicated task validity."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    NOT_APPLICABLE = "not_applicable"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class ActionPropensity:
    """One curated evidence modality and its collection probability.

    An action absent from the tuple is declared unavailable at that decision.
    Every action present must have strictly positive support.  A complete tuple
    records the full modality distribution for a curated collection protocol.
    It is never used to encode a live policy action: live action IDs, adapters,
    specs, terminal offers, and propensities remain in LoggedPolicyDecision.
    """

    action: EvidenceKind
    propensity: float

    def __post_init__(self) -> None:
        if not isinstance(self.action, EvidenceKind):
            raise ValueError("available action must be an EvidenceKind")
        if (
            isinstance(self.propensity, bool)
            or not isinstance(self.propensity, (int, float))
            or not isfinite(self.propensity)
            or not 0.0 < self.propensity <= 1.0
        ):
            raise ValueError("action propensity must be finite and in (0, 1]")
        object.__setattr__(self, "propensity", float(self.propensity))

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action.value, "propensity": self.propensity}

    @classmethod
    def from_dict(cls, value: Any, *, index: int = 0) -> ActionPropensity:
        field_name = f"available_actions[{index}]"
        data = _object(value, field_name)
        _reject_unknown(data, {"action", "propensity"}, field_name)
        return cls(
            action=_enum(
                EvidenceKind,
                data.get("action"),
                f"{field_name}.action",
            ),
            propensity=_number(
                data.get("propensity"),
                f"{field_name}.propensity",
            ),
        )


@dataclass(frozen=True)
class AcquisitionDecision:
    """Pre-observation curated-collection decision for one evidence event.

    ``history_sha256`` and ``router_state_sha256`` are not opaque caller
    metadata.  :class:`VerificationGapRecord` recomputes both from the exact
    prior event prefix and the deployable manifest.  Curator labels, artifact
    payloads, human adjudication, privileged evidence, and arbitrary evidence
    metadata are deliberately outside that projection.
    """

    decision_id: str
    decision_step: int
    candidate_id: str
    collection_policy: str
    collection_policy_version: str
    history_event_ids: tuple[str, ...]
    history_sha256: str
    router_state_sha256: str
    available_actions: tuple[ActionPropensity, ...]
    chosen_action: EvidenceKind
    history_conditioned_propensity: float
    selection_reason: str

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "candidate_id",
            "collection_policy",
            "collection_policy_version",
            "selection_reason",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            if value != value.strip() or any(ord(character) < 32 for character in value):
                raise ValueError(f"{name} cannot contain surrounding or control whitespace")
        if (
            isinstance(self.decision_step, bool)
            or not isinstance(self.decision_step, int)
            or self.decision_step < 0
        ):
            raise ValueError("decision_step must be a non-negative integer")
        if not isinstance(self.history_event_ids, (list, tuple)):
            raise ValueError("history_event_ids must be a sequence")
        history_event_ids = tuple(self.history_event_ids)
        if any(
            not isinstance(event_id, str)
            or not event_id.strip()
            or event_id != event_id.strip()
            for event_id in history_event_ids
        ):
            raise ValueError("history_event_ids must contain trimmed non-empty strings")
        if len(history_event_ids) != len(set(history_event_ids)):
            raise ValueError("history_event_ids cannot contain duplicates")
        if len(history_event_ids) != self.decision_step:
            raise ValueError("history_event_ids length must equal decision_step")
        object.__setattr__(self, "history_event_ids", history_event_ids)
        for name in ("history_sha256", "router_state_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
        if not isinstance(self.available_actions, (list, tuple)):
            raise ValueError("available_actions must be a sequence")
        available_actions = tuple(self.available_actions)
        if not available_actions or any(
            not isinstance(item, ActionPropensity) for item in available_actions
        ):
            raise ValueError("available_actions must contain ActionPropensity values")
        action_values = [item.action.value for item in available_actions]
        if action_values != sorted(action_values):
            raise ValueError("available_actions must be ordered by action name")
        if len(action_values) != len(set(action_values)):
            raise ValueError("available_actions cannot contain duplicate actions")
        propensity_sum = sum(item.propensity for item in available_actions)
        if not isclose(
            propensity_sum,
            1.0,
            rel_tol=0.0,
            abs_tol=_PROPENSITY_TOLERANCE,
        ):
            raise ValueError("available action propensities must sum to 1")
        object.__setattr__(self, "available_actions", available_actions)
        if not isinstance(self.chosen_action, EvidenceKind):
            raise ValueError("chosen_action must be an EvidenceKind")
        propensity_by_action = {
            item.action: item.propensity for item in available_actions
        }
        if self.chosen_action not in propensity_by_action:
            raise ValueError("chosen_action must be in available_actions")
        if (
            isinstance(self.history_conditioned_propensity, bool)
            or not isinstance(self.history_conditioned_propensity, (int, float))
            or not isfinite(self.history_conditioned_propensity)
            or not 0.0 < self.history_conditioned_propensity <= 1.0
        ):
            raise ValueError("history_conditioned_propensity must be in (0, 1]")
        if not isclose(
            float(self.history_conditioned_propensity),
            propensity_by_action[self.chosen_action],
            rel_tol=0.0,
            abs_tol=_PROPENSITY_TOLERANCE,
        ):
            raise ValueError(
                "history_conditioned_propensity must equal the chosen action propensity"
            )
        object.__setattr__(
            self,
            "history_conditioned_propensity",
            float(self.history_conditioned_propensity),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_step": self.decision_step,
            "candidate_id": self.candidate_id,
            "collection_policy": self.collection_policy,
            "collection_policy_version": self.collection_policy_version,
            "history_event_ids": list(self.history_event_ids),
            "history_sha256": self.history_sha256,
            "router_state_sha256": self.router_state_sha256,
            "available_actions": [item.to_dict() for item in self.available_actions],
            "chosen_action": self.chosen_action.value,
            "history_conditioned_propensity": self.history_conditioned_propensity,
            "selection_reason": self.selection_reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> AcquisitionDecision:
        data = _object(value, "decision")
        allowed = {
            "decision_id",
            "decision_step",
            "candidate_id",
            "collection_policy",
            "collection_policy_version",
            "history_event_ids",
            "history_sha256",
            "router_state_sha256",
            "available_actions",
            "chosen_action",
            "history_conditioned_propensity",
            "selection_reason",
        }
        _reject_unknown(data, allowed, "decision")
        history = _array(data.get("history_event_ids"), "decision.history_event_ids")
        actions = _array(data.get("available_actions"), "decision.available_actions")
        return cls(
            decision_id=_string(
                data.get("decision_id"),
                "decision.decision_id",
                nonempty=True,
            ),
            decision_step=_integer(
                data.get("decision_step"),
                "decision.decision_step",
            ),
            candidate_id=_string(
                data.get("candidate_id"),
                "decision.candidate_id",
                nonempty=True,
            ),
            collection_policy=_string(
                data.get("collection_policy"),
                "decision.collection_policy",
                nonempty=True,
            ),
            collection_policy_version=_string(
                data.get("collection_policy_version"),
                "decision.collection_policy_version",
                nonempty=True,
            ),
            history_event_ids=tuple(
                _string(
                    item,
                    f"decision.history_event_ids[{index}]",
                    nonempty=True,
                )
                for index, item in enumerate(history)
            ),
            history_sha256=_string(
                data.get("history_sha256"),
                "decision.history_sha256",
                nonempty=True,
            ),
            router_state_sha256=_string(
                data.get("router_state_sha256"),
                "decision.router_state_sha256",
                nonempty=True,
            ),
            available_actions=tuple(
                ActionPropensity.from_dict(item, index=index)
                for index, item in enumerate(actions)
            ),
            chosen_action=_enum(
                EvidenceKind,
                data.get("chosen_action"),
                "decision.chosen_action",
            ),
            history_conditioned_propensity=_number(
                data.get("history_conditioned_propensity"),
                "decision.history_conditioned_propensity",
            ),
            selection_reason=_string(
                data.get("selection_reason"),
                "decision.selection_reason",
                nonempty=True,
            ),
        )


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _array(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return value


def _string(value: Any, field_name: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if nonempty and not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    return value


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a JSON boolean")
    return value


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _reject_unknown(data: dict[str, Any], allowed: set[str], field_name: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{field_name} has unknown fields: {unknown}")


def _enum(enum_type: type[Enum], value: Any, field_name: str) -> Any:
    raw = _string(value, field_name)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} has unknown value {raw!r}") from exc


def _timestamp(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed


def _artifact_locator(value: Any, field_name: str, *, required: bool) -> str:
    locator = _string(value, field_name, nonempty=required)
    if not locator:
        return locator
    if locator != locator.strip() or any(ord(character) < 32 for character in locator):
        raise ValueError(f"{field_name} cannot contain surrounding or control whitespace")
    parsed = urlparse(locator)
    if (
        not parsed.scheme
        or not (parsed.netloc or parsed.path)
        or parsed.username is not None
        or parsed.password is not None
        or locator.casefold() in {"n/a", "none", "tbd", "unknown"}
    ):
        raise ValueError(
            f"{field_name} must be a credential-free, non-placeholder URI"
        )
    return locator


def normalize_repository_identity(value: str) -> str:
    """Return a conservative canonical GitHub ``owner/repository`` identity.

    GitHub HTTPS/SSH/SCP aliases, an optional ``github.com/`` prefix, a
    trailing slash, and ``.git`` are normalized. Other hosts and nested paths
    are rejected rather than guessed; repository split isolation then uses an
    exact comparison of this case-folded canonical identity.
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("repository identity must be a non-empty string")
    raw = value.strip()
    lowered = raw.casefold()
    if lowered.startswith("git@github.com:"):
        raw = raw.split(":", 1)[1]
    elif "://" in raw:
        parsed = urlparse(raw)
        if parsed.hostname is None or parsed.hostname.casefold() not in {
            "github.com",
            "www.github.com",
        }:
            raise ValueError("repository URL must use github.com")
        if parsed.query or parsed.fragment:
            raise ValueError("repository URL cannot contain a query or fragment")
        raw = parsed.path
    elif lowered.startswith("github.com/"):
        raw = raw[len("github.com/"):]

    raw = raw.strip("/")
    if raw.casefold().endswith(".git"):
        raw = raw[:-4]
    parts = raw.split("/")
    if len(parts) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts
    ):
        raise ValueError(
            "repository identity must be a GitHub owner/repository pair"
        )
    return "/".join(part.casefold() for part in parts)


@dataclass(frozen=True)
class PairedEvidence:
    """One evidence event, its pre-observation decision, and curator labels."""

    event_id: str
    observation: EvidenceObservation
    decision: AcquisitionDecision | LoggedPolicyDecision
    validity_adjudication: EvidenceValidityAdjudication
    subject_candidate_id: str = ""
    replicate: int = 0
    artifact_sha256: str = ""
    artifact_locator: str = ""
    collected_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("paired evidence event_id cannot be empty")
        if self.event_id != self.event_id.strip() or any(
            ord(character) < 32 for character in self.event_id
        ):
            raise ValueError(
                "paired evidence event_id cannot contain surrounding or control "
                "whitespace"
            )
        if not isinstance(self.observation, EvidenceObservation):
            raise ValueError("paired evidence observation must be an EvidenceObservation")
        acquisition_id = self.observation.acquisition_id
        if not acquisition_id:
            raise ValueError("paired evidence observation requires acquisition_id")
        if acquisition_id != acquisition_id.strip() or any(
            ord(character) < 32 for character in acquisition_id
        ):
            raise ValueError(
                "paired evidence acquisition_id cannot contain surrounding or "
                "control whitespace"
            )
        if acquisition_id == self.event_id:
            raise ValueError(
                "observation acquisition_id must be distinct from paired evidence event_id"
            )
        if isinstance(self.decision, AcquisitionDecision):
            if self.decision.decision_id in {self.event_id, acquisition_id}:
                raise ValueError(
                    "curated decision_id, event_id, and acquisition_id must be distinct"
                )
            if self.decision.chosen_action != self.observation.kind:
                raise ValueError("chosen_action must equal the evidence observation kind")
        elif isinstance(self.decision, LoggedPolicyDecision):
            if self.decision.terminal:
                raise ValueError(
                    "terminal policy decisions cannot be paired with an observation"
                )
            if self.decision.acquisition_id != acquisition_id:
                raise ValueError(
                    "logged policy acquisition_id must equal observation acquisition_id"
                )
            if self.decision.decision_id in {self.event_id, acquisition_id}:
                raise ValueError(
                    "logged decision_id, event_id, and acquisition_id must be distinct"
                )
            if self.decision.chosen_offer.evidence_kind != self.observation.kind:
                raise ValueError(
                    "logged chosen action must produce the evidence observation kind"
                )
            if self.observation.kind == EvidenceKind.HUMAN_ADJUDICATION:
                raise ValueError(
                    "human adjudication cannot result from a deployable live policy action"
                )
            if self.observation.privileged_inputs:
                raise ValueError(
                    "live policy observations cannot depend on privileged inputs"
                )
        else:
            raise ValueError(
                "paired evidence decision must be an AcquisitionDecision or "
                "LoggedPolicyDecision"
            )
        if not isinstance(
            self.validity_adjudication, EvidenceValidityAdjudication
        ):
            raise ValueError(
                "validity_adjudication must be an EvidenceValidityAdjudication"
            )
        if (
            not isinstance(self.subject_candidate_id, str)
            or not self.subject_candidate_id.strip()
        ):
            raise ValueError("subject_candidate_id must be a non-empty string")
        if self.subject_candidate_id != self.decision.candidate_id:
            raise ValueError("decision candidate_id must equal subject_candidate_id")
        if (
            isinstance(self.replicate, bool)
            or not isinstance(self.replicate, int)
            or self.replicate < 0
        ):
            raise ValueError("paired evidence replicate cannot be negative")
        if not isinstance(self.artifact_sha256, str):
            raise ValueError("artifact_sha256 must be a string")
        if self.artifact_sha256 and not re.fullmatch(
            r"[0-9a-f]{64}", self.artifact_sha256
        ):
            raise ValueError("artifact_sha256 must be 64 lowercase hexadecimal characters")
        _artifact_locator(self.artifact_locator, "artifact_locator", required=False)
        if not isinstance(self.collected_at, str):
            raise ValueError("collected_at must be a string")
        if isinstance(self.decision, LoggedPolicyDecision) and not self.collected_at:
            raise ValueError("logged policy evidence requires collected_at")
        if self.collected_at:
            collected_at = _timestamp(self.collected_at, "collected_at")
            if isinstance(self.decision, LoggedPolicyDecision):
                decided_at = _timestamp(self.decision.decided_at, "decision.decided_at")
                if collected_at < decided_at:
                    raise ValueError("collected_at cannot precede the logged decision")
        if (
            self.observation.status in {EvidenceStatus.ERROR, EvidenceStatus.UNAVAILABLE}
            and self.validity_adjudication.validity == EvidenceValidity.VALID
        ):
            raise ValueError("failed or unavailable evidence cannot have a valid label")

    @property
    def validity(self) -> EvidenceValidity:
        return self.validity_adjudication.validity

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "observation": self.observation.to_dict(),
            "decision_contract": (
                _LOGGED_POLICY_DECISION_CONTRACT
                if isinstance(self.decision, LoggedPolicyDecision)
                else _CURATED_DECISION_CONTRACT
            ),
            "decision": self.decision.to_dict(),
            "validity_adjudication": self.validity_adjudication.to_dict(),
            "subject_candidate_id": self.subject_candidate_id,
            "replicate": self.replicate,
            "artifact_sha256": self.artifact_sha256,
            "artifact_locator": self.artifact_locator,
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_dict(cls, value: Any, *, index: int = 0) -> PairedEvidence:
        field_name = f"observations[{index}]"
        data = _object(value, field_name)
        if "validity_label" in data:
            raise ValueError(
                f"legacy {field_name}.validity_label is unsupported in corpus 0.5.0; "
                "provide provenance-bearing validity_adjudication"
            )
        allowed = {
            "event_id",
            "observation",
            "decision_contract",
            "decision",
            "validity_adjudication",
            "subject_candidate_id",
            "replicate",
            "artifact_sha256",
            "artifact_locator",
            "collected_at",
        }
        _reject_unknown(data, allowed, field_name)
        decision_contract = _string(
            data.get("decision_contract"),
            f"{field_name}.decision_contract",
            nonempty=True,
        )
        if decision_contract == _CURATED_DECISION_CONTRACT:
            decision: AcquisitionDecision | LoggedPolicyDecision = (
                AcquisitionDecision.from_dict(data.get("decision"))
            )
        elif decision_contract == _LOGGED_POLICY_DECISION_CONTRACT:
            decision = LoggedPolicyDecision.from_dict(data.get("decision"))
        else:
            raise ValueError(
                f"{field_name}.decision_contract has unknown value "
                f"{decision_contract!r}"
            )
        return cls(
            event_id=_string(data.get("event_id"), f"{field_name}.event_id", nonempty=True),
            observation=EvidenceObservation.from_dict(data.get("observation")),
            decision=decision,
            validity_adjudication=EvidenceValidityAdjudication.from_dict(
                data.get("validity_adjudication"),
                field_name=f"{field_name}.validity_adjudication",
            ),
            subject_candidate_id=_string(
                data.get("subject_candidate_id", ""),
                f"{field_name}.subject_candidate_id",
            ),
            replicate=_integer(data.get("replicate", 0), f"{field_name}.replicate"),
            artifact_sha256=_string(
                data.get("artifact_sha256", ""),
                f"{field_name}.artifact_sha256",
            ),
            artifact_locator=_string(
                data.get("artifact_locator", ""),
                f"{field_name}.artifact_locator",
            ),
            collected_at=_string(
                data.get("collected_at", ""),
                f"{field_name}.collected_at",
            ),
        )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(strict_json_dumps(value).encode()).hexdigest()


def _router_visible_observation(item: PairedEvidence) -> dict[str, Any]:
    """Return the only evidence fields allowed in a later router state.

    The output intentionally excludes curator validity, artifacts, timestamps,
    selection explanations, and unstructured metadata. Metadata remains in the
    auditable acquisition trajectory but is not a declared router input; a
    collection policy that reads it violates this contract. Human adjudication
    and observations that declare any privileged input may never become history
    for another acquisition decision.
    """

    observation = item.observation
    if observation.kind == EvidenceKind.HUMAN_ADJUDICATION:
        raise ValueError("human adjudication cannot enter later router history")
    if observation.privileged_inputs:
        raise ValueError("privileged evidence cannot enter later router history")
    return {
        "event_id": item.event_id,
        "kind": observation.kind.value,
        "status": observation.status.value,
        "source": observation.source,
        "source_version": observation.source_version,
        "acquisition_id": observation.acquisition_id,
        "confidence": observation.confidence,
        "candidate_probability": observation.candidate_probability,
        "verifier_validity": observation.verifier_validity,
        "calibrated_risk_upper_bound": observation.calibrated_risk_upper_bound,
        "calibration_id": observation.calibration_id,
        "authoritative": observation.authoritative,
        "cost": asdict(observation.cost),
    }


def _deployable_observation_projection(
    observation: EvidenceObservation,
) -> EvidenceObservation:
    """Strip post-acquisition audit fields exactly as the live router does."""

    if observation.kind == EvidenceKind.HUMAN_ADJUDICATION:
        raise ValueError("human adjudication is not a deployable router input")
    if observation.privileged_inputs:
        raise ValueError("privileged evidence is not a deployable router input")
    return EvidenceObservation(
        kind=observation.kind,
        status=observation.status,
        source=observation.source,
        source_version=observation.source_version,
        acquisition_id=observation.acquisition_id,
        confidence=observation.confidence,
        candidate_probability=observation.candidate_probability,
        verifier_validity=observation.verifier_validity,
        calibrated_risk_upper_bound=observation.calibrated_risk_upper_bound,
        calibration_id=observation.calibration_id,
        authoritative=observation.authoritative,
        cost=observation.cost,
    )


def _router_history_sha256(prior_observations: Sequence[PairedEvidence]) -> str:
    return _sha256_json({
        "contract": _ROUTER_HISTORY_CONTRACT,
        "events": [_router_visible_observation(item) for item in prior_observations],
    })


def _router_state_sha256(
    *,
    manifest: ValidityManifest,
    collection_policy: str,
    collection_policy_version: str,
    decision_step: int,
    history_event_ids: Sequence[str],
    history_sha256: str,
    available_actions: Sequence[ActionPropensity],
) -> str:
    return _sha256_json({
        "contract": _ROUTER_STATE_CONTRACT,
        "manifest_sha256": manifest.canonical_digest(),
        "candidate_id": manifest.candidate_id,
        "collection_policy": collection_policy,
        "collection_policy_version": collection_policy_version,
        "decision_step": decision_step,
        "history_event_ids": list(history_event_ids),
        "history_sha256": history_sha256,
        "available_actions": [item.action.value for item in available_actions],
    })


def build_acquisition_decision(
    *,
    decision_id: str,
    manifest: ValidityManifest,
    collection_policy: str,
    collection_policy_version: str,
    prior_observations: Sequence[PairedEvidence],
    available_actions: (
        Mapping[EvidenceKind, float] | Sequence[ActionPropensity]
    ),
    chosen_action: EvidenceKind,
    selection_reason: str,
) -> AcquisitionDecision:
    """Build a curated pre-observation decision from an exact event prefix."""

    if not isinstance(manifest, ValidityManifest):
        raise ValueError("manifest must be a ValidityManifest")
    if manifest.evidence or manifest.route_history:
        raise ValueError("acquisition decisions require a pre-execution manifest")
    validate_deployable_provenance(manifest.provenance)
    if not isinstance(prior_observations, Sequence) or any(
        not isinstance(item, PairedEvidence) for item in prior_observations
    ):
        raise ValueError("prior_observations must contain PairedEvidence values")
    prior = tuple(prior_observations)
    if isinstance(available_actions, Mapping):
        action_probabilities = tuple(
            sorted(
                (
                    ActionPropensity(action=action, propensity=propensity)
                    for action, propensity in available_actions.items()
                ),
                key=lambda item: item.action.value,
            )
        )
    elif isinstance(available_actions, Sequence):
        action_probabilities = tuple(available_actions)
    else:
        raise ValueError("available_actions must be a mapping or sequence")
    history_event_ids = tuple(item.event_id for item in prior)
    history_sha256 = _router_history_sha256(prior)
    propensity_by_action = {
        item.action: item.propensity for item in action_probabilities
        if isinstance(item, ActionPropensity)
    }
    chosen_propensity = propensity_by_action.get(chosen_action)
    if chosen_propensity is None:
        raise ValueError("chosen_action must have a logged available-action propensity")
    return AcquisitionDecision(
        decision_id=decision_id,
        decision_step=len(prior),
        candidate_id=manifest.candidate_id,
        collection_policy=collection_policy,
        collection_policy_version=collection_policy_version,
        history_event_ids=history_event_ids,
        history_sha256=history_sha256,
        router_state_sha256=_router_state_sha256(
            manifest=manifest,
            collection_policy=collection_policy,
            collection_policy_version=collection_policy_version,
            decision_step=len(prior),
            history_event_ids=history_event_ids,
            history_sha256=history_sha256,
            available_actions=action_probabilities,
        ),
        available_actions=action_probabilities,
        chosen_action=chosen_action,
        history_conditioned_propensity=chosen_propensity,
        selection_reason=selection_reason,
    )


def bridge_logged_policy_observation(
    *,
    event_id: str,
    policy_decision: LoggedPolicyDecision,
    observation: EvidenceObservation,
    validity_adjudication: EvidenceValidityAdjudication,
    collected_at: str,
    prior_observations: Sequence[PairedEvidence] = (),
    subject_candidate_id: str | None = None,
    replicate: int = 0,
    artifact_sha256: str = "",
    artifact_locator: str = "",
) -> PairedEvidence:
    """Losslessly bind a write-ahead live decision to its resulting evidence.

    The original :class:`LoggedPolicyDecision` is embedded unchanged.  In
    particular, this function never derives a modality-level probability from
    the chosen observation or rebuilds the behavior distribution after the
    result is known.  A non-empty prefix must itself be an exact live-policy
    chain so that acquisition identities can be joined to prior corpus event
    identities without weakening either contract.
    """

    if not isinstance(policy_decision, LoggedPolicyDecision):
        raise ValueError("policy_decision must be a LoggedPolicyDecision")
    if policy_decision.terminal:
        raise ValueError(
            "terminal policy decisions cannot be bridged to evidence observations"
        )
    if not isinstance(observation, EvidenceObservation):
        raise ValueError("observation must be an EvidenceObservation")
    if not isinstance(prior_observations, Sequence) or any(
        not isinstance(item, PairedEvidence) for item in prior_observations
    ):
        raise ValueError("prior_observations must contain PairedEvidence values")
    prior = tuple(prior_observations)
    prior_decisions: list[LoggedPolicyDecision] = []
    for item in prior:
        if not isinstance(item.decision, LoggedPolicyDecision):
            raise ValueError(
                "a live-policy bridge cannot follow a curated collection decision"
            )
        prior_decisions.append(item.decision)
    validate_policy_decision_chain([*prior_decisions, policy_decision])
    expected_history = tuple(
        _deployable_observation_projection(item.observation) for item in prior
    )
    if policy_decision.router_state.evidence_history != expected_history:
        raise ValueError(
            "policy router state does not match the exact prior corpus observations"
        )
    if policy_decision.decision_step != len(prior):
        raise ValueError(
            "policy decision_step does not match the prior corpus event count"
        )
    if prior:
        prior_collected_at = _timestamp(
            prior[-1].collected_at,
            "prior_observations[-1].collected_at",
        )
        decided_at = _timestamp(
            policy_decision.decided_at,
            "policy_decision.decided_at",
        )
        if decided_at < prior_collected_at:
            raise ValueError(
                "policy decision cannot precede its latest observed evidence"
            )
    return PairedEvidence(
        event_id=event_id,
        observation=observation,
        decision=policy_decision,
        validity_adjudication=validity_adjudication,
        subject_candidate_id=(
            policy_decision.candidate_id
            if subject_candidate_id is None
            else subject_candidate_id
        ),
        replicate=replicate,
        artifact_sha256=artifact_sha256,
        artifact_locator=artifact_locator,
        collected_at=collected_at,
    )

@dataclass(frozen=True)
class TaskAdjudication:
    """Privileged task-validity truth kept outside deployable router inputs."""

    task_validity: TaskValidity
    source: str
    protocol_version: str
    blinded: bool
    annotator_count: int
    agreement: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.task_validity, bool) or not isinstance(
            self.task_validity, TaskValidity
        ):
            raise ValueError(
                "task_validity must be a TaskValidity enum; legacy booleans cannot "
                "establish a valid task"
            )
        _validate_adjudication_metadata(
            source=self.source,
            protocol_version=self.protocol_version,
            blinded=self.blinded,
            annotator_count=self.annotator_count,
            agreement=self.agreement,
            notes=self.notes,
            field_name="task_adjudication",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_validity": self.task_validity.value,
            "source": self.source,
            "protocol_version": self.protocol_version,
            "blinded": self.blinded,
            "annotator_count": self.annotator_count,
            "agreement": self.agreement,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TaskAdjudication:
        data = _object(value, "task_adjudication")
        if "task_valid" in data or isinstance(data.get("task_validity"), bool):
            raise ValueError(
                "legacy boolean task validity is unsupported in corpus 0.5.0; use "
                "task_validity=invalid or indeterminate unless validity was separately "
                "adjudicated"
            )
        allowed = {
            "task_validity",
            "source",
            "protocol_version",
            "blinded",
            "annotator_count",
            "agreement",
            "notes",
        }
        _reject_unknown(data, allowed, "task_adjudication")
        agreement_value = data.get("agreement")
        return cls(
            task_validity=_enum(
                TaskValidity,
                data.get("task_validity"),
                "task_adjudication.task_validity",
            ),
            source=_string(
                data.get("source"), "task_adjudication.source", nonempty=True
            ),
            protocol_version=_string(
                data.get("protocol_version"),
                "task_adjudication.protocol_version",
                nonempty=True,
            ),
            blinded=_boolean(
                data.get("blinded"), "task_adjudication.blinded"
            ),
            annotator_count=_integer(
                data.get("annotator_count"),
                "task_adjudication.annotator_count",
            ),
            agreement=(
                None
                if agreement_value is None
                else _number(agreement_value, "task_adjudication.agreement")
            ),
            notes=_string(data.get("notes", ""), "task_adjudication.notes"),
        )


@dataclass(frozen=True)
class CandidateAdjudication:
    """Privileged conditional candidate truth, separate from task validity."""

    candidate_correctness: CandidateCorrectness
    source: str
    protocol_version: str
    blinded: bool
    annotator_count: int
    agreement: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.candidate_correctness, bool) or not isinstance(
            self.candidate_correctness, CandidateCorrectness
        ):
            raise ValueError(
                "candidate_correctness must be a CandidateCorrectness enum; legacy "
                "candidate_correct booleans are unsupported in corpus 0.5.0"
            )
        _validate_adjudication_metadata(
            source=self.source,
            protocol_version=self.protocol_version,
            blinded=self.blinded,
            annotator_count=self.annotator_count,
            agreement=self.agreement,
            notes=self.notes,
            field_name="candidate_adjudication",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_correctness": self.candidate_correctness.value,
            "source": self.source,
            "protocol_version": self.protocol_version,
            "blinded": self.blinded,
            "annotator_count": self.annotator_count,
            "agreement": self.agreement,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, value: Any) -> CandidateAdjudication:
        data = _object(value, "candidate_adjudication")
        if "candidate_correct" in data or isinstance(
            data.get("candidate_correctness"), bool
        ):
            raise ValueError(
                "legacy boolean candidate correctness is unsupported in corpus 0.5.0; "
                "use task_adjudication plus candidate_correctness"
            )
        allowed = {
            "candidate_correctness",
            "source",
            "protocol_version",
            "blinded",
            "annotator_count",
            "agreement",
            "notes",
        }
        _reject_unknown(data, allowed, "candidate_adjudication")
        agreement_value = data.get("agreement")
        return cls(
            candidate_correctness=_enum(
                CandidateCorrectness,
                data.get("candidate_correctness"),
                "candidate_adjudication.candidate_correctness",
            ),
            source=_string(
                data.get("source"),
                "candidate_adjudication.source",
                nonempty=True,
            ),
            protocol_version=_string(
                data.get("protocol_version"),
                "candidate_adjudication.protocol_version",
                nonempty=True,
            ),
            blinded=_boolean(
                data.get("blinded"), "candidate_adjudication.blinded"
            ),
            annotator_count=_integer(
                data.get("annotator_count"),
                "candidate_adjudication.annotator_count",
            ),
            agreement=(
                None
                if agreement_value is None
                else _number(agreement_value, "candidate_adjudication.agreement")
            ),
            notes=_string(
                data.get("notes", ""), "candidate_adjudication.notes"
            ),
        )


@dataclass(frozen=True)
class VerificationGapRecord:
    """One task/candidate with paired evidence and blinded ground truth."""

    manifest: ValidityManifest
    split: CorpusSplit
    repository: str
    base_commit: str
    task_created_at: str
    candidate_generated_at: str
    candidate_artifact_locator: str
    candidate_type: CandidateType
    collection_policy: str
    collection_policy_version: str
    observations: tuple[PairedEvidence, ...]
    task_adjudication: TaskAdjudication
    candidate_adjudication: CandidateAdjudication
    schema_version: str = CORPUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CORPUS_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported corpus schema_version {self.schema_version!r}; "
                f"expected {CORPUS_SCHEMA_VERSION!r}"
            )
        if not isinstance(self.manifest, ValidityManifest):
            raise ValueError("manifest must be a ValidityManifest")
        if not isinstance(self.split, CorpusSplit):
            raise ValueError("split must be a CorpusSplit")
        if not isinstance(self.task_created_at, str) or not self.task_created_at.strip():
            raise ValueError("task_created_at is required")
        if (
            not isinstance(self.candidate_generated_at, str)
            or not self.candidate_generated_at.strip()
        ):
            raise ValueError("candidate_generated_at is required")
        task_time = _timestamp(self.task_created_at, "task_created_at")
        candidate_time = _timestamp(
            self.candidate_generated_at,
            "candidate_generated_at",
        )
        if candidate_time < task_time:
            raise ValueError("candidate_generated_at cannot precede task_created_at")
        _artifact_locator(
            self.candidate_artifact_locator,
            "candidate_artifact_locator",
            required=True,
        )
        if not isinstance(self.candidate_type, CandidateType):
            raise ValueError("candidate_type must be a CandidateType")
        if not isinstance(self.observations, (list, tuple)) or any(
            not isinstance(item, PairedEvidence) for item in self.observations
        ):
            raise ValueError("observations must contain PairedEvidence values")
        object.__setattr__(self, "observations", tuple(self.observations))
        if not self.observations:
            raise ValueError("observations cannot be empty")
        for observation in self.observations:
            if observation.collected_at and _timestamp(
                observation.collected_at,
                "observation.collected_at",
            ) < candidate_time:
                raise ValueError(
                    "evidence collected_at cannot precede candidate_generated_at"
                )
        if not isinstance(self.task_adjudication, TaskAdjudication):
            raise ValueError("task_adjudication must be a TaskAdjudication")
        if not isinstance(self.candidate_adjudication, CandidateAdjudication):
            raise ValueError(
                "candidate_adjudication must be a CandidateAdjudication"
            )
        task_validity = self.task_adjudication.task_validity
        candidate_correctness = (
            self.candidate_adjudication.candidate_correctness
        )
        if (
            task_validity == TaskValidity.INVALID
            and candidate_correctness != CandidateCorrectness.NOT_APPLICABLE
        ):
            raise ValueError(
                "invalid task validity requires candidate correctness not_applicable"
            )
        if (
            task_validity == TaskValidity.INDETERMINATE
            and candidate_correctness != CandidateCorrectness.INDETERMINATE
        ):
            raise ValueError(
                "indeterminate task validity requires indeterminate candidate correctness"
            )
        if (
            task_validity == TaskValidity.VALID
            and candidate_correctness == CandidateCorrectness.NOT_APPLICABLE
        ):
            raise ValueError(
                "valid task validity cannot have not_applicable candidate correctness"
            )
        canonical_repository = normalize_repository_identity(self.repository)
        object.__setattr__(self, "repository", canonical_repository)
        if not isinstance(self.base_commit, str):
            raise ValueError("base_commit must be a string")
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", self.base_commit):
            raise ValueError("base_commit must be a full 40- or 64-character hash")
        object.__setattr__(self, "base_commit", self.base_commit.casefold())
        if (
            not isinstance(self.collection_policy, str)
            or not self.collection_policy.strip()
            or not isinstance(self.collection_policy_version, str)
            or not self.collection_policy_version.strip()
        ):
            raise ValueError("collection policy name and version are required")
        if (
            self.collection_policy != self.collection_policy.strip()
            or self.collection_policy_version != self.collection_policy_version.strip()
        ):
            raise ValueError("collection policy name and version must be trimmed")
        if self.manifest.evidence or self.manifest.route_history:
            raise ValueError(
                "corpus manifest must be pre-execution; paired observations and "
                "route history belong outside deployable inputs"
            )
        validate_deployable_provenance(self.manifest.provenance)
        manifest_repository = self.manifest.provenance.get("repository")
        if (
            manifest_repository is not None
            and normalize_repository_identity(manifest_repository) != self.repository
        ):
            raise ValueError("manifest repository provenance contradicts corpus record")
        manifest_commit = self.manifest.provenance.get("base_commit")
        if (
            manifest_commit is not None
            and manifest_commit.casefold() != self.base_commit
        ):
            raise ValueError("manifest base_commit provenance contradicts corpus record")
        event_ids = [item.event_id for item in self.observations]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("paired evidence event_id values must be unique per record")
        decision_ids = [item.decision.decision_id for item in self.observations]
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("paired evidence decision_id values must be unique per record")
        acquisition_ids = [
            item.observation.acquisition_id for item in self.observations
        ]
        if len(acquisition_ids) != len(set(acquisition_ids)):
            raise ValueError(
                "paired evidence acquisition_id values must be unique per record"
            )
        identity_overlap = {
            "event/decision": sorted(set(event_ids).intersection(decision_ids)),
            "event/acquisition": sorted(set(event_ids).intersection(acquisition_ids)),
            "decision/acquisition": sorted(
                set(decision_ids).intersection(acquisition_ids)
            ),
        }
        identity_overlap = {
            namespace_pair: values
            for namespace_pair, values in identity_overlap.items()
            if values
        }
        if identity_overlap:
            raise ValueError(
                "event_id, decision_id, and acquisition_id namespaces must be "
                f"disjoint per record: {identity_overlap}"
            )
        _validate_acquisition_sequence(self)

    @property
    def key(self) -> tuple[str, str]:
        # Lifecycle is policy context, not candidate identity. Including it
        # here would let the same labeled pair bypass duplicate detection.
        return self.manifest.instance_id, self.manifest.candidate_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest": self.manifest.to_dict(),
            "split": self.split.value,
            "repository": self.repository,
            "base_commit": self.base_commit,
            "task_created_at": self.task_created_at,
            "candidate_generated_at": self.candidate_generated_at,
            "candidate_artifact_locator": self.candidate_artifact_locator,
            "candidate_type": self.candidate_type.value,
            "collection_policy": self.collection_policy,
            "collection_policy_version": self.collection_policy_version,
            "observations": [item.to_dict() for item in self.observations],
            "task_adjudication": self.task_adjudication.to_dict(),
            "candidate_adjudication": self.candidate_adjudication.to_dict(),
        }

    def canonical_digest(self) -> str:
        payload = strict_json_dumps(self.to_dict())
        return hashlib.sha256(payload.encode()).hexdigest()

    def acquisition_trajectory_digest(self) -> str:
        """Digest policy-visible acquisition events without curator labels.

        This join identity excludes evidence-validity labels, candidate type,
        split assignment, and final adjudication.  It is not a propensity or a
        causal estimate; it only binds a terminal evaluation row to the exact
        logged acquisition trajectory that produced it.
        """

        return _sha256_json({
            "contract": _ACQUISITION_TRAJECTORY_CONTRACT,
            "manifest_sha256": self.manifest.canonical_digest(),
            "candidate_generated_at": self.candidate_generated_at,
            "candidate_artifact_locator": self.candidate_artifact_locator,
            "collection_policy": self.collection_policy,
            "collection_policy_version": self.collection_policy_version,
            "events": [
                {
                    "event_id": item.event_id,
                    "observation": item.observation.to_dict(),
                    "decision_contract": (
                        _LOGGED_POLICY_DECISION_CONTRACT
                        if isinstance(item.decision, LoggedPolicyDecision)
                        else _CURATED_DECISION_CONTRACT
                    ),
                    "decision": item.decision.to_dict(),
                    "subject_candidate_id": item.subject_candidate_id,
                    "replicate": item.replicate,
                    "artifact_sha256": item.artifact_sha256,
                    "artifact_locator": item.artifact_locator,
                    "collected_at": item.collected_at,
                }
                for item in self.observations
            ],
        })

    @classmethod
    def from_dict(cls, value: Any) -> VerificationGapRecord:
        data = _object(value, "record")
        if "adjudication" in data:
            raise ValueError(
                "legacy record.adjudication is unsupported in corpus 0.5.0; "
                "provide task_adjudication and candidate_adjudication"
            )
        allowed = {
            "schema_version",
            "manifest",
            "split",
            "repository",
            "base_commit",
            "task_created_at",
            "candidate_generated_at",
            "candidate_artifact_locator",
            "candidate_type",
            "collection_policy",
            "collection_policy_version",
            "observations",
            "task_adjudication",
            "candidate_adjudication",
        }
        _reject_unknown(data, allowed, "record")
        schema_version = _string(
            data.get("schema_version"),
            "record.schema_version",
            nonempty=True,
        )
        if schema_version != CORPUS_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported corpus schema_version {schema_version!r}; "
                f"expected {CORPUS_SCHEMA_VERSION!r}"
            )
        observations = _array(data.get("observations"), "observations")
        return cls(
            schema_version=schema_version,
            manifest=ValidityManifest.from_dict(data.get("manifest")),
            split=_enum(CorpusSplit, data.get("split"), "record.split"),
            repository=_string(
                data.get("repository"),
                "record.repository",
                nonempty=True,
            ),
            base_commit=_string(
                data.get("base_commit"),
                "record.base_commit",
                nonempty=True,
            ),
            task_created_at=_string(
                data.get("task_created_at"),
                "record.task_created_at",
                nonempty=True,
            ),
            candidate_generated_at=_string(
                data.get("candidate_generated_at"),
                "record.candidate_generated_at",
                nonempty=True,
            ),
            candidate_artifact_locator=_string(
                data.get("candidate_artifact_locator"),
                "record.candidate_artifact_locator",
                nonempty=True,
            ),
            candidate_type=_enum(
                CandidateType,
                data.get("candidate_type"),
                "record.candidate_type",
            ),
            collection_policy=_string(
                data.get("collection_policy"),
                "record.collection_policy",
                nonempty=True,
            ),
            collection_policy_version=_string(
                data.get("collection_policy_version"),
                "record.collection_policy_version",
                nonempty=True,
            ),
            observations=tuple(
                PairedEvidence.from_dict(item, index=index)
                for index, item in enumerate(observations)
            ),
            task_adjudication=TaskAdjudication.from_dict(
                data.get("task_adjudication")
            ),
            candidate_adjudication=CandidateAdjudication.from_dict(
                data.get("candidate_adjudication")
            ),
        )


def _validate_acquisition_sequence(record: VerificationGapRecord) -> None:
    """Verify the event log is one ordered, pre-observation decision trajectory."""

    prior: list[PairedEvidence] = []
    prior_collected_at: datetime | None = None
    live_decisions: list[LoggedPolicyDecision] = []
    curated_suffix_started = False
    for expected_step, item in enumerate(record.observations):
        decision = item.decision
        if decision.decision_step != expected_step:
            raise ValueError(
                "acquisition decision_step values must be unique, contiguous, and ordered"
            )
        if decision.candidate_id != record.manifest.candidate_id:
            raise ValueError("decision candidate_id contradicts the manifest candidate_id")
        if isinstance(decision, LoggedPolicyDecision):
            if curated_suffix_started:
                raise ValueError(
                    "live policy decisions must form a contiguous trajectory prefix"
                )
            if (
                decision.policy_id != record.collection_policy
                or decision.policy_version != record.collection_policy_version
            ):
                raise ValueError(
                    "logged policy name/version contradicts the corpus record"
                )
            state = decision.router_state
            initial_state = RouterStateView.from_manifest(record.manifest)
            if (
                state.instance_id != record.manifest.instance_id
                or state.lifecycle_stage != record.manifest.lifecycle_stage
                or state.risk_profile != record.manifest.risk_profile
                or state.provenance != initial_state.provenance
            ):
                raise ValueError(
                    "logged router baseline contradicts the pre-execution manifest"
                )
            if not live_decisions and (
                state.source_manifest_sha256 != record.manifest.canonical_digest()
            ):
                raise ValueError(
                    "first logged decision is not bound to the corpus manifest"
                )
            if prior:
                latest_collected_at = _timestamp(
                    prior[-1].collected_at,
                    "prior observation.collected_at",
                )
                decided_at = _timestamp(decision.decided_at, "decision.decided_at")
                if decided_at < latest_collected_at:
                    raise ValueError(
                        "logged decision cannot precede its latest observed evidence"
                    )
            expected_live_history = tuple(
                _deployable_observation_projection(event.observation)
                for event in prior
            )
            if state.evidence_history != expected_live_history:
                raise ValueError(
                    "logged router state does not match the exact prior event prefix"
                )
            live_decisions.append(decision)
        else:
            curated_suffix_started = True
            expected_history_ids = tuple(event.event_id for event in prior)
            if decision.history_event_ids != expected_history_ids:
                raise ValueError(
                    "decision history_event_ids must equal the exact prior event prefix"
                )
            if (
                decision.collection_policy != record.collection_policy
                or decision.collection_policy_version != record.collection_policy_version
            ):
                raise ValueError(
                    "decision collection policy name/version contradicts the corpus record"
                )
            expected_history_sha256 = _router_history_sha256(prior)
            if decision.history_sha256 != expected_history_sha256:
                raise ValueError(
                    "history_sha256 does not match the non-privileged prior event prefix"
                )
            expected_state_sha256 = _router_state_sha256(
                manifest=record.manifest,
                collection_policy=record.collection_policy,
                collection_policy_version=record.collection_policy_version,
                decision_step=expected_step,
                history_event_ids=expected_history_ids,
                history_sha256=expected_history_sha256,
                available_actions=decision.available_actions,
            )
            if decision.router_state_sha256 != expected_state_sha256:
                raise ValueError(
                    "router_state_sha256 does not match the declared deployable "
                    "router state"
                )
        if item.collected_at:
            collected_at = _timestamp(item.collected_at, "observation.collected_at")
            if prior_collected_at is not None and collected_at < prior_collected_at:
                raise ValueError(
                    "evidence collection timestamps must follow decision_step order"
                )
            prior_collected_at = collected_at
        prior.append(item)
    if live_decisions:
        validate_policy_decision_chain(live_decisions)


_REQUIRED_EVIDENCE_KINDS = set(EvidenceKind)
_REQUIRED_PROVENANCE = {
    "base_commit",
    "candidate_generator",
    "candidate_patch_sha256",
    "dataset_revision",
    "dependency_lock_digest",
    "environment_image_digest",
    "prompt_version",
    "repository",
    "scaffold_version",
}

_CONCLUSIVE_STATUSES = {
    EvidenceStatus.SUPPORTS_CORRECT,
    EvidenceStatus.SUPPORTS_INCORRECT,
}


def _is_deterministic_collection(
    decision: AcquisitionDecision | LoggedPolicyDecision,
) -> bool:
    if isinstance(decision, LoggedPolicyDecision):
        return (
            len(decision.behavior_distribution) == 1
            and decision.chosen_propensity == 1.0
        )
    return (
        len(decision.available_actions) == 1
        and decision.history_conditioned_propensity == 1.0
    )


def _paired_errors(record: VerificationGapRecord) -> list[str]:
    errors: list[str] = []
    observed_kinds = {item.observation.kind for item in record.observations}
    missing_kinds = sorted(kind.value for kind in _REQUIRED_EVIDENCE_KINDS - observed_kinds)
    if missing_kinds:
        errors.append(f"missing evidence kinds {missing_kinds}")

    availability = {
        EvidenceKind.TARGETED_EXECUTION: (
            record.manifest.risk_profile.targeted_execution_available
        ),
        EvidenceKind.FULL_EXECUTION: record.manifest.risk_profile.full_execution_available,
        EvidenceKind.ORACLE_HARDENING: (
            record.manifest.risk_profile.oracle_hardening_available
        ),
    }
    for kind, declared_available in availability.items():
        events = [item for item in record.observations if item.observation.kind == kind]
        acquired = any(
            item.observation.status != EvidenceStatus.UNAVAILABLE for item in events
        )
        if declared_available != acquired:
            errors.append(
                f"{kind.value} availability contradicts its evidence observations"
            )

    missing_provenance = sorted(
        key
        for key in _REQUIRED_PROVENANCE
        if not record.manifest.provenance.get(key, "").strip()
    )
    if missing_provenance:
        errors.append(f"missing or blank provenance {missing_provenance}")

    candidate_patch_sha256 = record.manifest.provenance.get(
        "candidate_patch_sha256",
        "",
    )
    if candidate_patch_sha256 and not re.fullmatch(
        r"[0-9a-f]{64}", candidate_patch_sha256
    ):
        errors.append("candidate_patch_sha256 is not a lowercase SHA-256 digest")
    elif candidate_patch_sha256 and record.manifest.candidate_id != (
        f"sha256:{candidate_patch_sha256}"
    ):
        errors.append("candidate_id does not match candidate_patch_sha256")

    full_runs = [
        item for item in record.observations
        if item.observation.kind == EvidenceKind.FULL_EXECUTION
        and item.observation.status in _CONCLUSIVE_STATUSES
    ]
    if len(full_runs) < 2:
        errors.append("fewer than two conclusive full-execution replicates")
    elif len({item.replicate for item in full_runs}) != len(full_runs):
        errors.append("full-execution replicate identifiers are not unique")

    if any(not _is_deterministic_collection(item.decision) for item in record.observations):
        errors.append(
            "counterfactual evidence was not acquired by a deterministic "
            "probability-1 collection decision"
        )
    if any(
        item.subject_candidate_id != record.manifest.candidate_id
        for item in record.observations
    ):
        errors.append("an evidence event is not tied to the manifest candidate_id")
    if any(not item.observation.source_version.strip() for item in record.observations):
        errors.append("an evidence source_version is missing")
    if any(not item.collected_at.strip() for item in record.observations):
        errors.append("an evidence collection timestamp is missing")
    for item in record.observations:
        adjudication = item.validity_adjudication
        if (
            adjudication.validity != EvidenceValidity.INDETERMINATE
            and not adjudication.determinate_paired_ready
        ):
            errors.append(
                "determinate evidence-validity adjudication is not blinded, "
                "multi-reviewer, and above the agreement threshold for event "
                f"{item.event_id!r}"
            )
    acquired_events = [
        item for item in record.observations
        if item.observation.status != EvidenceStatus.UNAVAILABLE
    ]
    if any(
        not item.artifact_sha256 or not item.artifact_locator.strip()
        for item in acquired_events
    ):
        errors.append("an acquired evidence artifact digest or locator is missing")
    artifact_locators = [item.artifact_locator for item in acquired_events]
    if len(artifact_locators) != len(set(artifact_locators)):
        errors.append("acquired evidence artifact locators are not unique per event")

    human = [
        item for item in record.observations
        if item.observation.kind == EvidenceKind.HUMAN_ADJUDICATION
    ]
    candidate_correctness = (
        record.candidate_adjudication.candidate_correctness
    )
    if (
        record.task_adjudication.task_validity == TaskValidity.VALID
        and candidate_correctness == CandidateCorrectness.INDETERMINATE
    ):
        errors.append(
            "valid task has indeterminate candidate correctness for paired-ready data"
        )
    expected_human_status = {
        CandidateCorrectness.CORRECT: EvidenceStatus.SUPPORTS_CORRECT,
        CandidateCorrectness.INCORRECT: EvidenceStatus.SUPPORTS_INCORRECT,
        CandidateCorrectness.NOT_APPLICABLE: EvidenceStatus.INCONCLUSIVE,
        CandidateCorrectness.INDETERMINATE: EvidenceStatus.INCONCLUSIVE,
    }[candidate_correctness]
    if len(human) != 1:
        errors.append("exactly one human-adjudication event is required")
    elif (
        human[0].observation.status != expected_human_status
        or not human[0].observation.authoritative
        or human[0].validity != EvidenceValidity.VALID
    ):
        errors.append("human-adjudication event contradicts authoritative truth")

    for name, truth_adjudication in (
        ("task", record.task_adjudication),
        ("candidate", record.candidate_adjudication),
    ):
        if not truth_adjudication.blinded:
            errors.append(f"{name} adjudication is not blinded")
        if truth_adjudication.annotator_count < 2:
            errors.append(f"{name} adjudication has fewer than two adjudicators")
        if truth_adjudication.agreement is None:
            errors.append(f"{name} inter-annotator agreement is missing")
        elif truth_adjudication.agreement < MIN_ADJUDICATOR_AGREEMENT:
            errors.append(
                f"{name} inter-annotator agreement is below the schema threshold "
                f"{MIN_ADJUDICATOR_AGREEMENT:.2f}"
            )
    return errors


def validate_corpus(
    records: list[VerificationGapRecord],
    *,
    require_paired: bool = False,
) -> None:
    """Validate uniqueness, repository-disjoint splits, and paired completeness."""

    if not records:
        raise ValueError("corpus contains no records")
    seen: set[tuple[str, str]] = set()
    task_adjudications: dict[str, tuple[str, tuple[str, str]]] = {}
    identity_owners: dict[str, tuple[str, tuple[str, str]]] = {}
    trajectory_owners: dict[str, tuple[str, str]] = {}
    policy_implementations: dict[
        tuple[str, str],
        tuple[str, tuple[str, str]],
    ] = {}
    policy_action_identities: dict[
        tuple[str, str, str],
        tuple[tuple[str, str | None, str, str, str], tuple[str, str]],
    ] = {}
    repository_splits: dict[str, set[CorpusSplit]] = defaultdict(set)
    split_times: dict[CorpusSplit, list[datetime]] = defaultdict(list)
    for record in records:
        if record.key in seen:
            raise ValueError(f"duplicate instance/candidate pair {record.key!r}")
        seen.add(record.key)
        serialized_task_adjudication = strict_json_dumps(
            record.task_adjudication.to_dict()
        )
        prior_task_adjudication = task_adjudications.get(
            record.manifest.instance_id
        )
        if (
            prior_task_adjudication is not None
            and prior_task_adjudication[0] != serialized_task_adjudication
        ):
            raise ValueError(
                "task adjudication changes across candidates for instance_id "
                f"{record.manifest.instance_id!r}; first={prior_task_adjudication[1]!r}, "
                f"current={record.key!r}"
            )
        task_adjudications[record.manifest.instance_id] = (
            serialized_task_adjudication,
            record.key,
        )
        for item in record.observations:
            identities = {
                "event_id": item.event_id,
                "decision_id": item.decision.decision_id,
                "acquisition_id": item.observation.acquisition_id,
            }
            for namespace, identity in identities.items():
                previous = identity_owners.get(identity)
                if previous is not None:
                    previous_namespace, previous_key = previous
                    raise ValueError(
                        f"corpus identity {identity!r} is reused as {namespace} "
                        f"for {record.key!r}; first used as {previous_namespace} "
                        f"for {previous_key!r}"
                    )
                identity_owners[identity] = (namespace, record.key)
            if isinstance(item.decision, LoggedPolicyDecision):
                decision = item.decision
                trajectory_owner = trajectory_owners.get(decision.trajectory_id)
                if trajectory_owner is not None and trajectory_owner != record.key:
                    raise ValueError(
                        f"live trajectory_id {decision.trajectory_id!r} crosses "
                        f"corpus records {trajectory_owner!r} and {record.key!r}"
                    )
                trajectory_owners[decision.trajectory_id] = record.key
                policy_key = (decision.policy_id, decision.policy_version)
                previous_implementation = policy_implementations.get(policy_key)
                if (
                    previous_implementation is not None
                    and previous_implementation[0]
                    != decision.policy_code_config_sha256
                ):
                    raise ValueError(
                        "stable policy name/version changes code/config identity "
                        f"across corpus events: {policy_key!r}, "
                        f"first={previous_implementation[1]!r}, "
                        f"current={record.key!r}"
                    )
                policy_implementations[policy_key] = (
                    decision.policy_code_config_sha256,
                    record.key,
                )
                for offer in decision.action_catalog:
                    action_key = (
                        decision.policy_id,
                        decision.policy_version,
                        offer.action_id,
                    )
                    action_identity = (
                        offer.route_action.value,
                        (
                            offer.evidence_kind.value
                            if offer.evidence_kind is not None
                            else None
                        ),
                        offer.adapter_id,
                        offer.adapter_version,
                        offer.action_spec_sha256,
                    )
                    previous_action = policy_action_identities.get(action_key)
                    if (
                        previous_action is not None
                        and previous_action[0] != action_identity
                    ):
                        raise ValueError(
                            "stable policy action_id changes intervention identity "
                            f"across corpus records: {action_key!r}, "
                            f"first={previous_action[1]!r}, current={record.key!r}"
                        )
                    policy_action_identities[action_key] = (
                        action_identity,
                        record.key,
                    )
        repository_splits[record.repository].add(record.split)
        split_times[record.split].append(
            _timestamp(record.task_created_at, "task_created_at")
        )
        if require_paired:
            errors = _paired_errors(record)
            if errors:
                raise ValueError(f"record {record.key!r} is not paired-complete: {'; '.join(errors)}")
    leaking = {
        repository: sorted(split.value for split in splits)
        for repository, splits in repository_splits.items()
        if len(splits) > 1
    }
    if leaking:
        raise ValueError(f"repositories cross corpus splits: {leaking}")
    if require_paired:
        ordered_splits = [
            CorpusSplit.DEVELOPMENT,
            CorpusSplit.CALIBRATION,
            CorpusSplit.TEST,
        ]
        populated = [split for split in ordered_splits if split_times[split]]
        for earlier, later in zip(populated, populated[1:]):
            if max(split_times[earlier]) > min(split_times[later]):
                raise ValueError(
                    "corpus time splits overlap or run backwards: "
                    f"{earlier.value} -> {later.value}"
                )


def load_corpus(stream: TextIO) -> list[VerificationGapRecord]:
    """Load strict JSONL without silently changing the corpus denominator."""

    records: list[VerificationGapRecord] = []
    for line_number, raw_line in enumerate(stream, 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            decoded = strict_json_loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
                raise ValueError(f"line {line_number}: invalid JSON: {exc}") from exc
            raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        try:
            records.append(VerificationGapRecord.from_dict(decoded))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"line {line_number}: invalid record: {exc}") from exc
    validate_corpus(records)
    return records


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _chosen_propensity(
    decision: AcquisitionDecision | LoggedPolicyDecision,
) -> float:
    if isinstance(decision, LoggedPolicyDecision):
        return decision.chosen_propensity
    return decision.history_conditioned_propensity


def _available_evidence_probabilities(
    decision: AcquisitionDecision | LoggedPolicyDecision,
) -> dict[EvidenceKind, float]:
    if isinstance(decision, AcquisitionDecision):
        return {item.action: item.propensity for item in decision.available_actions}
    catalog = {item.action_id: item for item in decision.action_catalog}
    by_kind: dict[EvidenceKind, float] = defaultdict(float)
    for probability in decision.behavior_distribution:
        kind = catalog[probability.action_id].evidence_kind
        if kind is not None:
            by_kind[kind] += probability.propensity
    return dict(by_kind)


def _chosen_evidence_kind(
    decision: AcquisitionDecision | LoggedPolicyDecision,
) -> EvidenceKind | None:
    if isinstance(decision, AcquisitionDecision):
        return decision.chosen_action
    return decision.chosen_offer.evidence_kind


def _logged_action_level_summary(
    decisions: Sequence[AcquisitionDecision | LoggedPolicyDecision],
) -> dict[str, Any]:
    grouped: dict[
        tuple[str, str, str | None, str, str, str],
        dict[str, Any],
    ] = {}
    logged_count = 0
    for decision in decisions:
        if not isinstance(decision, LoggedPolicyDecision):
            continue
        logged_count += 1
        probability_by_id = {
            item.action_id: item.propensity
            for item in decision.behavior_distribution
        }
        for offer in decision.action_catalog:
            identity = (
                offer.action_id,
                offer.route_action.value,
                offer.evidence_kind.value if offer.evidence_kind is not None else None,
                offer.adapter_id,
                offer.adapter_version,
                offer.action_spec_sha256,
            )
            row = grouped.setdefault(identity, {
                "action_id": offer.action_id,
                "route_action": offer.route_action.value,
                "evidence_kind": (
                    offer.evidence_kind.value
                    if offer.evidence_kind is not None
                    else None
                ),
                "adapter_id": offer.adapter_id,
                "adapter_version": offer.adapter_version,
                "action_spec_sha256": offer.action_spec_sha256,
                "catalog_decisions": 0,
                "available_decisions": 0,
                "unavailable_decisions": 0,
                "chosen_decisions": 0,
                "propensities": [],
            })
            row["catalog_decisions"] += 1
            if offer.available:
                row["available_decisions"] += 1
                row["propensities"].append(probability_by_id[offer.action_id])
            else:
                row["unavailable_decisions"] += 1
            if offer.action_id == decision.chosen_action_id:
                row["chosen_decisions"] += 1
    rows: list[dict[str, Any]] = []
    for identity in sorted(grouped, key=strict_json_dumps):
        row = grouped[identity]
        propensities = row.pop("propensities")
        row["mean_logged_propensity_when_available"] = _mean(propensities)
        row["minimum_logged_propensity_when_available"] = (
            min(propensities) if propensities else None
        )
        row["maximum_logged_propensity_when_available"] = (
            max(propensities) if propensities else None
        )
        rows.append(row)
    return {
        "scope": "exact_logged_policy_action_offers",
        "logged_policy_decisions": logged_count,
        "curated_collection_decisions_excluded": len(decisions) - logged_count,
        "offers": rows,
    }


def _propensity_summary(records: Sequence[VerificationGapRecord]) -> dict[str, Any]:
    decisions = [
        item.decision
        for record in records
        for item in record.observations
    ]
    chosen_propensities = [
        _chosen_propensity(decision) for decision in decisions
    ]
    action_sets = Counter(
        ",".join(
            item.action_id
            for item in decision.behavior_distribution
        )
        if isinstance(decision, LoggedPolicyDecision)
        else ",".join(item.action.value for item in decision.available_actions)
        for decision in decisions
    )
    action_rows: dict[str, dict[str, Any]] = {}
    never_available: list[str] = []
    available_never_chosen: list[str] = []
    for kind in EvidenceKind:
        available: list[float] = []
        for decision in decisions:
            probabilities = _available_evidence_probabilities(decision)
            if kind in probabilities:
                available.append(probabilities[kind])
        chosen = [
            _chosen_propensity(decision)
            for decision in decisions
            if _chosen_evidence_kind(decision) == kind
        ]
        if not available:
            never_available.append(kind.value)
        elif not chosen:
            available_never_chosen.append(kind.value)
        action_rows[kind.value] = {
            "available_decisions": len(available),
            "chosen_decisions": len(chosen),
            "empirical_selection_rate_when_available": (
                len(chosen) / len(available) if available else None
            ),
            "mean_logged_propensity_when_available": _mean(available),
            "minimum_logged_propensity_when_available": (
                min(available) if available else None
            ),
            "maximum_logged_propensity_when_available": (
                max(available) if available else None
            ),
            "mean_logged_propensity_when_chosen": _mean(chosen),
        }

    trajectory_negative_log_probabilities = [
        -sum(log(_chosen_propensity(item.decision)) for item in record.observations)
        for record in records
    ]
    return {
        "records": len(records),
        "decisions": len(decisions),
        "deterministic_decisions": sum(
            _is_deterministic_collection(decision) for decision in decisions
        ),
        "randomized_decisions": sum(
            not _is_deterministic_collection(decision) for decision in decisions
        ),
        "all_available_actions_have_strictly_positive_logged_propensity": True,
        "minimum_chosen_propensity": min(chosen_propensities),
        "mean_chosen_propensity": _mean(chosen_propensities),
        "maximum_negative_log_chosen_propensity": max(
            -log(value) for value in chosen_propensities
        ),
        "small_chosen_propensity_counts": {
            "below_0.01": sum(value < 0.01 for value in chosen_propensities),
            "below_0.05": sum(value < 0.05 for value in chosen_propensities),
            "below_0.10": sum(value < 0.10 for value in chosen_propensities),
        },
        "trajectory_negative_log_probability": {
            "minimum": min(trajectory_negative_log_probabilities),
            "mean": _mean(trajectory_negative_log_probabilities),
            "maximum": max(trajectory_negative_log_probabilities),
        },
        "available_action_set_counts": dict(sorted(action_sets.items())),
        "per_action": action_rows,
        "action_level_behavior": _logged_action_level_summary(decisions),
        "actions_never_available": never_available,
        "actions_available_but_never_selected": available_never_chosen,
    }


def _propensity_diagnostics(
    records: Sequence[VerificationGapRecord],
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[VerificationGapRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.collection_policy, record.collection_policy_version)].append(record)
    return {
        "scope": "descriptive_logged_behavior_policy_only",
        "router_history_contract": _ROUTER_HISTORY_CONTRACT,
        "router_state_contract": _ROUTER_STATE_CONTRACT,
        "overall": _propensity_summary(records),
        "by_collection_policy": [
            {
                "collection_policy": policy,
                "collection_policy_version": version,
                **_propensity_summary(rows),
            }
            for (policy, version), rows in sorted(grouped.items())
        ],
        "contextual_overlap": {
            "assessed": False,
            "reason": (
                "Positive logged support on declared available actions and aggregate "
                "action counts do not establish overlap with an unspecified target "
                "policy at each history-conditioned state."
            ),
        },
        "causal_validity": {
            "assessed": False,
            "off_policy_estimates_computed": False,
            "reason": (
                "The schema cannot verify sequential ignorability, behavior-logger "
                "correctness, reward consistency, or target-policy propensities. "
                "Events within a candidate trajectory are dependent and are not "
                "independent samples."
            ),
        },
    }


def corpus_digest(records: Sequence[VerificationGapRecord]) -> str:
    """Bind one exact corpus to the canonical digests of its sorted records."""

    if not records:
        raise ValueError("corpus contains no records")
    if any(not isinstance(record, VerificationGapRecord) for record in records):
        raise ValueError("corpus digest requires VerificationGapRecord values")
    ordered_records = sorted(records, key=lambda record: record.key)
    payload = "\n".join(record.canonical_digest() for record in ordered_records)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_corpus_report(records: list[VerificationGapRecord]) -> dict[str, Any]:
    """Return auditable denominators, completeness, validity, and measured cost."""

    validate_corpus(records)
    split_counts = Counter(record.split.value for record in records)
    candidate_counts = Counter(record.candidate_type.value for record in records)
    task_validity_counts = Counter(
        record.task_adjudication.task_validity.value for record in records
    )
    candidate_correctness_counts = Counter(
        record.candidate_adjudication.candidate_correctness.value
        for record in records
    )
    evidence_counts: Counter[str] = Counter()
    status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    validity_counts: dict[str, Counter[str]] = defaultdict(Counter)
    validity_adjudication_status_counts: dict[str, Counter[str]] = defaultdict(
        Counter
    )
    validity_adjudication_protocol_counts: dict[str, Counter[str]] = defaultdict(
        Counter
    )
    incomplete: list[dict[str, Any]] = []
    cost_totals: dict[str, float | int] = {
        "wall_seconds": 0.0,
        "cpu_seconds": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "storage_bytes": 0,
        "usd": 0.0,
    }

    for record in records:
        errors = _paired_errors(record)
        if errors:
            incomplete.append({
                "instance_id": record.manifest.instance_id,
                "candidate_id": record.manifest.candidate_id,
                "lifecycle_stage": record.manifest.lifecycle_stage.value,
                "errors": errors,
            })
        for item in record.observations:
            kind = item.observation.kind.value
            evidence_counts[kind] += 1
            status_counts[kind][item.observation.status.value] += 1
            adjudication = item.validity_adjudication
            validity_counts[kind][adjudication.validity.value] += 1
            if adjudication.validity == EvidenceValidity.INDETERMINATE:
                adjudication_status = "indeterminate_excluded"
            elif adjudication.determinate_paired_ready:
                adjudication_status = "paired_ready_determinate"
            else:
                adjudication_status = "incomplete_determinate"
            validity_adjudication_status_counts[kind][adjudication_status] += 1
            protocol_identity = (
                f"{adjudication.source}@{adjudication.protocol_version}"
            )
            validity_adjudication_protocol_counts[kind][protocol_identity] += 1
            for field_name, value in asdict(item.observation.cost).items():
                cost_totals[field_name] += value

    ordered_records = sorted(records, key=lambda record: record.key)
    task_time_ranges = {
        split.value: {
            "minimum": min(
                record.task_created_at for record in records if record.split == split
            ),
            "maximum": max(
                record.task_created_at for record in records if record.split == split
            ),
        }
        for split in CorpusSplit
        if any(record.split == split for record in records)
    }
    candidate_time_ranges = {
        split.value: {
            "minimum": min(
                record.candidate_generated_at
                for record in records
                if record.split == split
            ),
            "maximum": max(
                record.candidate_generated_at
                for record in records
                if record.split == split
            ),
        }
        for split in CorpusSplit
        if any(record.split == split for record in records)
    }
    evidence_times = [
        item.collected_at
        for record in records
        for item in record.observations
        if item.collected_at
    ]
    return {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "corpus_digest": corpus_digest(records),
        "record_digests": [
            {
                "instance_id": record.manifest.instance_id,
                "candidate_id": record.manifest.candidate_id,
                "record_sha256": record.canonical_digest(),
            }
            for record in ordered_records
        ],
        "acquisition_trajectory_contract": _ACQUISITION_TRAJECTORY_CONTRACT,
        "acquisition_trajectories": [
            {
                "instance_id": record.manifest.instance_id,
                "candidate_id": record.manifest.candidate_id,
                "collection_policy": record.collection_policy,
                "collection_policy_version": record.collection_policy_version,
                "acquisition_trajectory_digest": (
                    record.acquisition_trajectory_digest()
                ),
            }
            for record in ordered_records
        ],
        "records": len(records),
        "repositories": len({record.repository for record in records}),
        "split_counts": dict(sorted(split_counts.items())),
        "task_time_ranges": task_time_ranges,
        "candidate_time_ranges": candidate_time_ranges,
        "evidence_time_range": (
            {"minimum": min(evidence_times), "maximum": max(evidence_times)}
            if evidence_times
            else None
        ),
        "missing_splits": sorted(
            split.value for split in set(CorpusSplit) - {record.split for record in records}
        ),
        "candidate_type_counts": dict(sorted(candidate_counts.items())),
        "missing_candidate_types": sorted(
            candidate_type.value
            for candidate_type in set(CandidateType) - {
                record.candidate_type for record in records
            }
        ),
        "task_validity_counts": dict(sorted(task_validity_counts.items())),
        "candidate_correctness_counts": dict(
            sorted(candidate_correctness_counts.items())
        ),
        "evidence_event_counts": dict(sorted(evidence_counts.items())),
        "evidence_status_counts": {
            key: dict(sorted(value.items())) for key, value in sorted(status_counts.items())
        },
        "evidence_validity_counts": {
            key: dict(sorted(value.items()))
            for key, value in sorted(validity_counts.items())
        },
        "evidence_validity_adjudication_status_counts": {
            key: dict(sorted(value.items()))
            for key, value in sorted(
                validity_adjudication_status_counts.items()
            )
        },
        "evidence_validity_adjudication_protocol_counts": {
            key: dict(sorted(value.items()))
            for key, value in sorted(
                validity_adjudication_protocol_counts.items()
            )
        },
        "propensity_diagnostics": _propensity_diagnostics(records),
        "paired_complete_records": len(records) - len(incomplete),
        "completeness_scope": "schema_and_collection_protocol_only",
        "scientific_adequacy": {
            "assessed": False,
            "reason": (
                "Schema completeness does not establish sample size, statistical "
                "power, representativeness, calibration, or downstream model value."
            ),
        },
        "minimum_adjudicator_agreement": MIN_ADJUDICATOR_AGREEMENT,
        "incomplete_records": incomplete,
        "cost_totals": cost_totals,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench-cleanser-corpus",
        description=(
            "Validate and summarize a paired verification-gap JSONL corpus "
            "without leaking privileged labels into router inputs"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("corpus", help="Verification-gap JSONL file, or '-' for stdin")
    parser.add_argument(
        "--require-paired",
        action="store_true",
        help="Require every modality, repeated full execution, and blinded adjudication",
    )
    parser.add_argument("--output", help="Write JSON report here instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if args.corpus == "-":
            records = load_corpus(sys.stdin)
        else:
            with pathlib.Path(args.corpus).open(encoding="utf-8") as stream:
                records = load_corpus(stream)
        validate_corpus(records, require_paired=args.require_paired)
        report = build_corpus_report(records)
        rendered = strict_json_dumps(report, indent=2) + "\n"
        if args.output:
            atomic_write(pathlib.Path(args.output), rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, ValueError) as exc:
        raise SystemExit(f"verification corpus validation failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - console entry point
    main()
