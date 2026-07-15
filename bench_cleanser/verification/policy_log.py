"""Versioned, write-ahead policy decisions for live verification routing.

This module is the migration boundary between the existing heuristic
``RouteDecision`` and corpus-only ``AcquisitionDecision`` schemas.  It replaces
neither schema and does not execute an action.  Instead it records the exact
safe state, complete action catalog, behavior distribution, sampler draw, and
chosen action that must be durably committed *before* an acquisition starts.

``RouteDecision`` remains the current router's compact recommendation and
``AcquisitionDecision`` remains the curated paired-collection schema.  Corpus
schema 0.4 can embed this live contract unchanged through
``bridge_logged_policy_observation``.  Decision, event, and acquisition
identities remain distinct, and the bridge never reconstructs propensities
after observing an acquisition result.

This contract validates logging and hash-chain integrity only.  It computes no
off-policy estimate and cannot prove that an external policy implementation
reported honest probabilities or persisted the record before acting.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import fsum, isclose, isfinite
from typing import Any, TextIO

from bench_cleanser.verification._io import strict_json_dumps, strict_json_load
from bench_cleanser.verification.manifest import validate_deployable_provenance
from bench_cleanser.verification.models import (
    EvidenceCost,
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RiskProfile,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)

POLICY_DECISION_SCHEMA_VERSION = "0.2.0"
ROUTER_STATE_SCHEMA_VERSION = "0.2.0"
POLICY_DECISION_CHAIN_CONTRACT = "bench-cleanser-policy-decision-chain-v1"
GENESIS_TRAJECTORY_HEAD_SHA256 = "0" * 64
CANONICAL_SAMPLER_ID = "inverse-cdf"
CANONICAL_SAMPLER_VERSION = "v1"
DETERMINISTIC_BOOTSTRAP_REASON = "deterministic_bootstrap"

_PROPENSITY_TOLERANCE = 1e-12
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_CANDIDATE_RE = re.compile(r"sha256:[0-9a-f]{64}")
_DECISION_ID_RE = re.compile(r"dec-[0-9a-f]{32}")
_ACQUISITION_ID_RE = re.compile(r"acq-[0-9a-f]{32}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")

_TERMINAL_ACTIONS = {
    RouteAction.ACCEPT,
    RouteAction.REJECT,
    RouteAction.ABSTAIN,
}
_ACTION_EVIDENCE_KIND: Mapping[RouteAction, EvidenceKind] = {
    RouteAction.RUN_STATIC: EvidenceKind.STATIC,
    RouteAction.RUN_SEMANTIC: EvidenceKind.SEMANTIC,
    RouteAction.RUN_TARGETED: EvidenceKind.TARGETED_EXECUTION,
    RouteAction.RUN_FULL: EvidenceKind.FULL_EXECUTION,
    RouteAction.HARDEN_ORACLE: EvidenceKind.ORACLE_HARDENING,
}
_ROUTER_PROVENANCE_KEYS = {
    "base_commit",
    "candidate_generator",
    "candidate_patch_sha256",
    "changed_files_sha256",
    "dataset_revision",
    "dependency_lock_digest",
    "environment_image_digest",
    "prompt_version",
    "repository",
    "risk_profile_version",
    "scaffold_version",
}
_OPERATIONAL_METADATA_KEYS = {
    "acquisition_schema_version",
    "artifact_locator",
    "artifact_sha256",
    "measured_cost_dimensions",
    "outcome",
    "return_code",
    "route_provenance",
    "runner",
    "runner_version",
    "stderr_truncated",
    "stdout_truncated",
}
_PRIVILEGED_METADATA_FRAGMENTS = {
    "adjudicat",
    "answerkey",
    "futurecommit",
    "gold",
    "groundtruth",
    "hidden",
    "human",
    "label",
    "outcomeverdict",
    "referencepatch",
    "referencesolution",
    "reward",
    "truth",
}


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _array(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return value


def _string(value: Any, field_name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if value != value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} cannot contain surrounding or control whitespace")
    if identifier and not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{field_name} is not a canonical identifier")
    return value


def _digest(value: Any, field_name: str) -> str:
    digest = _string(value, field_name)
    if not _DIGEST_RE.fullmatch(digest):
        raise ValueError(f"{field_name} must be 64 lowercase hexadecimal characters")
    return digest


def _candidate_id(value: Any, field_name: str) -> str:
    candidate = _string(value, field_name)
    if not _CANDIDATE_RE.fullmatch(candidate):
        raise ValueError(f"{field_name} must be a lowercase sha256:<digest> identity")
    return candidate


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a JSON boolean")
    return value


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a JSON integer")
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a JSON number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _optional_number(value: Any, field_name: str) -> float | None:
    return None if value is None else _number(value, field_name)


def _reject_unknown(
    data: Mapping[str, Any],
    allowed: set[str],
    field_name: str,
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{field_name} has unknown fields: {unknown}")


def _require_exact_fields(
    data: Mapping[str, Any],
    required: set[str],
    field_name: str,
) -> None:
    _reject_unknown(data, required, field_name)
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"{field_name} is missing required fields: {missing}")


def _enum(enum_type: type[Any], value: Any, field_name: str) -> Any:
    raw = _string(value, field_name)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} has unknown value {raw!r}") from exc


def _canonical_timestamp(value: Any, field_name: str) -> str:
    timestamp = _string(value, field_name)
    try:
        parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must use canonical UTC format YYYY-MM-DDTHH:MM:SS.ffffffZ"
        ) from exc
    canonical = parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if timestamp != canonical:
        raise ValueError(f"{field_name} is not a canonical UTC timestamp")
    return canonical


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(strict_json_dumps(value).encode("utf-8")).hexdigest()


def canonical_action_spec_sha256(action_spec: Mapping[str, Any]) -> str:
    """Digest one non-empty JSON action spec using the contract serializer."""

    if not isinstance(action_spec, Mapping) or not action_spec:
        raise ValueError("action_spec must be a non-empty JSON object")
    try:
        rendered = strict_json_dumps(dict(action_spec))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"action_spec is not canonical JSON: {exc}") from exc
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _cost_dict(cost: EvidenceCost) -> dict[str, Any]:
    return {
        "wall_seconds": float(cost.wall_seconds),
        "cpu_seconds": float(cost.cpu_seconds),
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "storage_bytes": cost.storage_bytes,
        "usd": float(cost.usd),
    }


def _cost_from_dict(value: Any, field_name: str) -> EvidenceCost:
    data = _object(value, field_name)
    fields = {
        "wall_seconds",
        "cpu_seconds",
        "input_tokens",
        "output_tokens",
        "storage_bytes",
        "usd",
    }
    _require_exact_fields(data, fields, field_name)
    return EvidenceCost(
        wall_seconds=_number(data["wall_seconds"], f"{field_name}.wall_seconds"),
        cpu_seconds=_number(data["cpu_seconds"], f"{field_name}.cpu_seconds"),
        input_tokens=_integer(data["input_tokens"], f"{field_name}.input_tokens"),
        output_tokens=_integer(data["output_tokens"], f"{field_name}.output_tokens"),
        storage_bytes=_integer(data["storage_bytes"], f"{field_name}.storage_bytes"),
        usd=_number(data["usd"], f"{field_name}.usd"),
    )


def _risk_profile_dict(profile: RiskProfile) -> dict[str, Any]:
    data = asdict(profile)
    data["semantic_disagreement"] = float(profile.semantic_disagreement)
    for name in (
        "historical_environment_error_rate",
        "oracle_strength",
        "observed_flake_rate",
    ):
        value = getattr(profile, name)
        data[name] = None if value is None else float(value)
    return data


def _risk_profile_from_dict(value: Any) -> RiskProfile:
    data = _object(value, "router_state.risk_profile")
    fields = set(asdict(RiskProfile()))
    _require_exact_fields(data, fields, "router_state.risk_profile")
    return RiskProfile(
        language=_string(data["language"], "router_state.risk_profile.language"),
        files_changed=_integer(
            data["files_changed"],
            "router_state.risk_profile.files_changed",
        ),
        lines_changed=_integer(
            data["lines_changed"],
            "router_state.risk_profile.lines_changed",
        ),
        compiled_language=_boolean(
            data["compiled_language"],
            "router_state.risk_profile.compiled_language",
        ),
        native_dependencies=_boolean(
            data["native_dependencies"],
            "router_state.risk_profile.native_dependencies",
        ),
        touches_dependency_or_build_files=_boolean(
            data["touches_dependency_or_build_files"],
            "router_state.risk_profile.touches_dependency_or_build_files",
        ),
        touches_schema_or_migration=_boolean(
            data["touches_schema_or_migration"],
            "router_state.risk_profile.touches_schema_or_migration",
        ),
        touches_security_or_auth=_boolean(
            data["touches_security_or_auth"],
            "router_state.risk_profile.touches_security_or_auth",
        ),
        touches_concurrency=_boolean(
            data["touches_concurrency"],
            "router_state.risk_profile.touches_concurrency",
        ),
        touches_tests=_boolean(
            data["touches_tests"],
            "router_state.risk_profile.touches_tests",
        ),
        generated_tests=_boolean(
            data["generated_tests"],
            "router_state.risk_profile.generated_tests",
        ),
        semantic_disagreement=_number(
            data["semantic_disagreement"],
            "router_state.risk_profile.semantic_disagreement",
        ),
        historical_environment_error_rate=_optional_number(
            data["historical_environment_error_rate"],
            "router_state.risk_profile.historical_environment_error_rate",
        ),
        oracle_strength=_optional_number(
            data["oracle_strength"],
            "router_state.risk_profile.oracle_strength",
        ),
        observed_flake_rate=_optional_number(
            data["observed_flake_rate"],
            "router_state.risk_profile.observed_flake_rate",
        ),
        targeted_execution_available=_boolean(
            data["targeted_execution_available"],
            "router_state.risk_profile.targeted_execution_available",
        ),
        full_execution_available=_boolean(
            data["full_execution_available"],
            "router_state.risk_profile.full_execution_available",
        ),
        oracle_hardening_available=_boolean(
            data["oracle_hardening_available"],
            "router_state.risk_profile.oracle_hardening_available",
        ),
    )


@dataclass(frozen=True)
class RouterRouteStep:
    """Allowlisted projection of a prior nonterminal route decision.

    Free-form reasons are deliberately absent because they could carry curator
    annotations or other undeclared policy inputs.
    """

    action: RouteAction
    policy_version: str
    candidate_risk: float
    verifier_risk: float
    expected_information_gain: float
    estimated_relative_cost: float
    scores_calibrated: bool
    calibration_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, RouteAction) or self.action in _TERMINAL_ACTIONS:
            raise ValueError("router route history requires a nonterminal RouteAction")
        _string(self.policy_version, "router route policy_version", identifier=True)
        for name in (
            "candidate_risk",
            "verifier_risk",
            "expected_information_gain",
        ):
            value = _number(getattr(self, name), f"router route {name}")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"router route {name} must be between 0 and 1")
            object.__setattr__(self, name, value)
        cost = _number(self.estimated_relative_cost, "router route estimated_relative_cost")
        if cost < 0.0:
            raise ValueError("router route estimated_relative_cost cannot be negative")
        object.__setattr__(self, "estimated_relative_cost", cost)
        if not isinstance(self.scores_calibrated, bool):
            raise ValueError("router route scores_calibrated must be a boolean")
        if self.calibration_id:
            _string(self.calibration_id, "router route calibration_id", identifier=True)
        if self.scores_calibrated and not self.calibration_id:
            raise ValueError("calibrated router route scores require calibration_id")
        if not self.scores_calibrated and self.calibration_id:
            raise ValueError("uncalibrated router route scores cannot claim calibration_id")

    @classmethod
    def from_route_decision(cls, decision: RouteDecision) -> RouterRouteStep:
        if not isinstance(decision, RouteDecision):
            raise ValueError("route history must contain RouteDecision values")
        if decision.terminal:
            raise ValueError("a terminal route decision cannot have a successor state")
        return cls(
            action=decision.action,
            policy_version=decision.policy_version,
            candidate_risk=decision.candidate_risk,
            verifier_risk=decision.verifier_risk,
            expected_information_gain=decision.expected_information_gain,
            estimated_relative_cost=decision.estimated_relative_cost,
            scores_calibrated=decision.scores_calibrated,
            calibration_id=decision.calibration_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "policy_version": self.policy_version,
            "candidate_risk": self.candidate_risk,
            "verifier_risk": self.verifier_risk,
            "expected_information_gain": self.expected_information_gain,
            "estimated_relative_cost": self.estimated_relative_cost,
            "scores_calibrated": self.scores_calibrated,
            "calibration_id": self.calibration_id,
        }


def _router_route_from_dict(value: Any, index: int) -> RouterRouteStep:
    field_name = f"router_state.route_history[{index}]"
    data = _object(value, field_name)
    fields = {
        "action",
        "policy_version",
        "candidate_risk",
        "verifier_risk",
        "expected_information_gain",
        "estimated_relative_cost",
        "scores_calibrated",
        "calibration_id",
    }
    _require_exact_fields(data, fields, field_name)
    return RouterRouteStep(
        action=_enum(RouteAction, data["action"], f"{field_name}.action"),
        policy_version=_string(
            data["policy_version"],
            f"{field_name}.policy_version",
        ),
        candidate_risk=_number(
            data["candidate_risk"],
            f"{field_name}.candidate_risk",
        ),
        verifier_risk=_number(
            data["verifier_risk"],
            f"{field_name}.verifier_risk",
        ),
        expected_information_gain=_number(
            data["expected_information_gain"],
            f"{field_name}.expected_information_gain",
        ),
        estimated_relative_cost=_number(
            data["estimated_relative_cost"],
            f"{field_name}.estimated_relative_cost",
        ),
        scores_calibrated=_boolean(
            data["scores_calibrated"],
            f"{field_name}.scores_calibrated",
        ),
        calibration_id=(
            _string(data["calibration_id"], f"{field_name}.calibration_id")
            if data["calibration_id"]
            else ""
        ),
    )


def _router_evidence_dict(observation: EvidenceObservation) -> dict[str, Any]:
    return {
        "kind": observation.kind.value,
        "status": observation.status.value,
        "source": observation.source,
        "source_version": observation.source_version,
        "acquisition_id": observation.acquisition_id,
        "confidence": (None if observation.confidence is None else float(observation.confidence)),
        "candidate_probability": (
            None
            if observation.candidate_probability is None
            else float(observation.candidate_probability)
        ),
        "verifier_validity": (
            None if observation.verifier_validity is None else float(observation.verifier_validity)
        ),
        "calibrated_risk_upper_bound": (
            None
            if observation.calibrated_risk_upper_bound is None
            else float(observation.calibrated_risk_upper_bound)
        ),
        "calibration_id": observation.calibration_id,
        "authoritative": observation.authoritative,
        "cost": _cost_dict(observation.cost),
    }


def _router_evidence_from_dict(value: Any, index: int) -> EvidenceObservation:
    field_name = f"router_state.evidence_history[{index}]"
    data = _object(value, field_name)
    fields = {
        "kind",
        "status",
        "source",
        "source_version",
        "acquisition_id",
        "confidence",
        "candidate_probability",
        "verifier_validity",
        "calibrated_risk_upper_bound",
        "calibration_id",
        "authoritative",
        "cost",
    }
    _require_exact_fields(data, fields, field_name)
    return EvidenceObservation(
        kind=_enum(EvidenceKind, data["kind"], f"{field_name}.kind"),
        status=_enum(EvidenceStatus, data["status"], f"{field_name}.status"),
        source=_string(data["source"], f"{field_name}.source"),
        source_version=(
            _string(data["source_version"], f"{field_name}.source_version")
            if data["source_version"]
            else ""
        ),
        acquisition_id=_string(
            data["acquisition_id"],
            f"{field_name}.acquisition_id",
        ),
        confidence=_optional_number(
            data["confidence"],
            f"{field_name}.confidence",
        ),
        candidate_probability=_optional_number(
            data["candidate_probability"],
            f"{field_name}.candidate_probability",
        ),
        verifier_validity=_optional_number(
            data["verifier_validity"],
            f"{field_name}.verifier_validity",
        ),
        calibrated_risk_upper_bound=_optional_number(
            data["calibrated_risk_upper_bound"],
            f"{field_name}.calibrated_risk_upper_bound",
        ),
        calibration_id=(
            _string(data["calibration_id"], f"{field_name}.calibration_id")
            if data["calibration_id"]
            else ""
        ),
        authoritative=_boolean(
            data["authoritative"],
            f"{field_name}.authoritative",
        ),
        cost=_cost_from_dict(data["cost"], f"{field_name}.cost"),
    )


def _metadata_fingerprint(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _validate_source_metadata(observation: EvidenceObservation, index: int) -> None:
    for key in observation.metadata:
        fingerprint = _metadata_fingerprint(key)
        if any(fragment in fingerprint for fragment in _PRIVILEGED_METADATA_FRAGMENTS):
            raise ValueError(f"evidence[{index}].metadata key {key!r} may encode privileged data")
        if key not in _OPERATIONAL_METADATA_KEYS:
            raise ValueError(f"evidence[{index}].metadata key {key!r} is not allowlisted")


@dataclass(frozen=True)
class BootstrapHistoryStep:
    """Deterministic pre-policy evidence bound without an invented propensity."""

    receipt_sha256: str
    route: RouterRouteStep
    observation: EvidenceObservation

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "receipt_sha256",
            _digest(self.receipt_sha256, "bootstrap_history.receipt_sha256"),
        )
        if not isinstance(self.route, RouterRouteStep):
            raise ValueError("bootstrap history route must be a RouterRouteStep")
        if self.route.action != RouteAction.RUN_STATIC:
            raise ValueError("bootstrap history route must be deterministic static")
        if not isinstance(self.observation, EvidenceObservation):
            raise ValueError("bootstrap history observation must be EvidenceObservation")
        observation = self.observation
        if observation.kind != EvidenceKind.STATIC:
            raise ValueError("bootstrap history observation must be static evidence")
        _string(observation.source, "bootstrap_history.observation.source")
        if observation.source_version:
            _string(
                observation.source_version,
                "bootstrap_history.observation.source_version",
            )
        _string(
            observation.acquisition_id,
            "bootstrap_history.observation.acquisition_id",
        )
        if observation.privileged_inputs:
            raise ValueError("privileged evidence cannot be deterministic bootstrap")
        if observation.metadata:
            raise ValueError("bootstrap observation metadata must be stripped")

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_sha256": self.receipt_sha256,
            "route": self.route.to_dict(),
            "observation": _router_evidence_dict(self.observation),
        }

    @classmethod
    def from_dict(cls, value: Any, index: int = 0) -> BootstrapHistoryStep:
        field_name = f"router_state.bootstrap_history[{index}]"
        data = _object(value, field_name)
        _require_exact_fields(
            data,
            {"receipt_sha256", "route", "observation"},
            field_name,
        )
        route_data = _object(data["route"], f"{field_name}.route")
        route_fields = {
            "action",
            "policy_version",
            "candidate_risk",
            "verifier_risk",
            "expected_information_gain",
            "estimated_relative_cost",
            "scores_calibrated",
            "calibration_id",
        }
        _require_exact_fields(route_data, route_fields, f"{field_name}.route")
        route = RouterRouteStep(
            action=_enum(
                RouteAction,
                route_data["action"],
                f"{field_name}.route.action",
            ),
            policy_version=_string(
                route_data["policy_version"],
                f"{field_name}.route.policy_version",
            ),
            candidate_risk=_number(
                route_data["candidate_risk"],
                f"{field_name}.route.candidate_risk",
            ),
            verifier_risk=_number(
                route_data["verifier_risk"],
                f"{field_name}.route.verifier_risk",
            ),
            expected_information_gain=_number(
                route_data["expected_information_gain"],
                f"{field_name}.route.expected_information_gain",
            ),
            estimated_relative_cost=_number(
                route_data["estimated_relative_cost"],
                f"{field_name}.route.estimated_relative_cost",
            ),
            scores_calibrated=_boolean(
                route_data["scores_calibrated"],
                f"{field_name}.route.scores_calibrated",
            ),
            calibration_id=(
                _string(
                    route_data["calibration_id"],
                    f"{field_name}.route.calibration_id",
                )
                if route_data["calibration_id"]
                else ""
            ),
        )
        observation_data = _object(
            data["observation"],
            f"{field_name}.observation",
        )
        observation = _router_evidence_from_dict(observation_data, index)
        return cls(
            receipt_sha256=_digest(
                data["receipt_sha256"],
                f"{field_name}.receipt_sha256",
            ),
            route=route,
            observation=observation,
        )


@dataclass(frozen=True)
class RouterStateView:
    """Only the typed, pre-decision state a live policy may inspect."""

    instance_id: str
    candidate_id: str
    lifecycle_stage: LifecycleStage
    risk_profile: RiskProfile
    provenance: tuple[tuple[str, str], ...]
    bootstrap_history: tuple[BootstrapHistoryStep, ...]
    evidence_history: tuple[EvidenceObservation, ...]
    route_history: tuple[RouterRouteStep, ...]
    source_manifest_sha256: str
    schema_version: str = ROUTER_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ROUTER_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported router-state schema_version {self.schema_version!r}; "
                f"expected {ROUTER_STATE_SCHEMA_VERSION!r}"
            )
        _string(self.instance_id, "router_state.instance_id")
        object.__setattr__(
            self,
            "candidate_id",
            _candidate_id(self.candidate_id, "router_state.candidate_id"),
        )
        if not isinstance(self.lifecycle_stage, LifecycleStage):
            raise ValueError("router_state.lifecycle_stage must be a LifecycleStage")
        if not isinstance(self.risk_profile, RiskProfile):
            raise ValueError("router_state.risk_profile must be a RiskProfile")
        _string(
            self.risk_profile.language,
            "router_state.risk_profile.language",
        )
        if not isinstance(self.provenance, (list, tuple)):
            raise ValueError("router_state.provenance must be a key/value sequence")
        provenance = tuple(self.provenance)
        if any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
            for item in provenance
        ):
            raise ValueError("router_state.provenance must contain string pairs")
        if list(provenance) != sorted(provenance):
            raise ValueError("router_state.provenance must be ordered by key")
        keys = [key for key, _ in provenance]
        if len(keys) != len(set(keys)):
            raise ValueError("router_state.provenance cannot contain duplicate keys")
        for key, value in provenance:
            _string(key, "router_state.provenance key")
            _string(value, f"router_state.provenance[{key!r}]")
        unknown_provenance = sorted(set(keys) - _ROUTER_PROVENANCE_KEYS)
        if unknown_provenance:
            raise ValueError(
                f"router_state.provenance has non-allowlisted keys: {unknown_provenance}"
            )
        validate_deployable_provenance(dict(provenance))
        object.__setattr__(self, "provenance", provenance)

        if not isinstance(self.bootstrap_history, (list, tuple)) or any(
            not isinstance(item, BootstrapHistoryStep) for item in self.bootstrap_history
        ):
            raise ValueError(
                "router_state.bootstrap_history must contain BootstrapHistoryStep values"
            )
        bootstrap = tuple(self.bootstrap_history)
        receipt_ids = [item.receipt_sha256 for item in bootstrap]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("router-state bootstrap receipt identities must be unique")
        object.__setattr__(self, "bootstrap_history", bootstrap)

        if not isinstance(self.evidence_history, (list, tuple)) or any(
            not isinstance(item, EvidenceObservation) for item in self.evidence_history
        ):
            raise ValueError(
                "router_state.evidence_history must contain EvidenceObservation values"
            )
        evidence = tuple(self.evidence_history)
        acquisition_ids = [
            *(item.observation.acquisition_id for item in bootstrap),
            *(item.acquisition_id for item in evidence),
        ]
        if any(not acquisition_id for acquisition_id in acquisition_ids):
            raise ValueError("router-state evidence requires acquisition_id")
        if len(acquisition_ids) != len(set(acquisition_ids)):
            raise ValueError("router-state acquisition_id values must be unique")
        for index, item in enumerate(evidence):
            _string(item.source, f"router_state.evidence_history[{index}].source")
            if item.source_version:
                _string(
                    item.source_version,
                    f"router_state.evidence_history[{index}].source_version",
                )
            _string(
                item.acquisition_id,
                f"router_state.evidence_history[{index}].acquisition_id",
            )
            if item.calibration_id:
                _string(
                    item.calibration_id,
                    f"router_state.evidence_history[{index}].calibration_id",
                )
            if item.kind == EvidenceKind.HUMAN_ADJUDICATION:
                raise ValueError("human adjudication is not a deployable router input")
            if item.privileged_inputs:
                raise ValueError("privileged evidence is not a deployable router input")
            if item.metadata:
                raise ValueError("router-state evidence metadata must be stripped")
        object.__setattr__(self, "evidence_history", evidence)

        if not isinstance(self.route_history, (list, tuple)) or any(
            not isinstance(item, RouterRouteStep) for item in self.route_history
        ):
            raise ValueError("router_state.route_history must contain RouterRouteStep values")
        routes = tuple(self.route_history)
        if len(routes) != len(evidence):
            raise ValueError("router-state route and evidence histories must be one-to-one")
        for index, (decision, observation) in enumerate(zip(routes, evidence)):
            expected_kind = _ACTION_EVIDENCE_KIND.get(decision.action)
            if expected_kind is None or observation.kind != expected_kind:
                raise ValueError(
                    f"router-state history step {index} has an action/evidence mismatch"
                )
        object.__setattr__(self, "route_history", routes)
        object.__setattr__(
            self,
            "source_manifest_sha256",
            _digest(
                self.source_manifest_sha256,
                "router_state.source_manifest_sha256",
            ),
        )

    @property
    def provenance_dict(self) -> dict[str, str]:
        return dict(self.provenance)

    @classmethod
    def from_manifest(
        cls,
        manifest: ValidityManifest,
        *,
        bootstrap_history: Sequence[BootstrapHistoryStep] = (),
    ) -> RouterStateView:
        """Project one manifest into a safe policy input or fail closed."""

        if not isinstance(manifest, ValidityManifest):
            raise ValueError("manifest must be a ValidityManifest")
        normalized_provenance = validate_deployable_provenance(manifest.provenance)
        unknown_provenance = sorted(set(normalized_provenance) - _ROUTER_PROVENANCE_KEYS)
        if unknown_provenance:
            raise ValueError(
                f"manifest provenance has non-allowlisted router keys: {unknown_provenance}"
            )
        safe_evidence: list[EvidenceObservation] = []
        for index, item in enumerate(manifest.evidence):
            if item.kind == EvidenceKind.HUMAN_ADJUDICATION:
                raise ValueError("human adjudication is not a deployable router input")
            if item.privileged_inputs:
                raise ValueError("privileged evidence is not a deployable router input")
            _validate_source_metadata(item, index)
            safe_evidence.append(
                EvidenceObservation(
                    kind=item.kind,
                    status=item.status,
                    source=item.source,
                    source_version=item.source_version,
                    acquisition_id=item.acquisition_id,
                    confidence=item.confidence,
                    candidate_probability=item.candidate_probability,
                    verifier_validity=item.verifier_validity,
                    calibrated_risk_upper_bound=item.calibrated_risk_upper_bound,
                    calibration_id=item.calibration_id,
                    authoritative=item.authoritative,
                    cost=item.cost,
                )
            )
        if not isinstance(bootstrap_history, (list, tuple)) or any(
            not isinstance(item, BootstrapHistoryStep) for item in bootstrap_history
        ):
            raise ValueError("bootstrap_history must contain BootstrapHistoryStep values")
        bootstrap = tuple(bootstrap_history)
        safe_routes = tuple(
            RouterRouteStep.from_route_decision(item) for item in manifest.route_history
        )
        prefix_length = len(bootstrap)
        if tuple(safe_evidence[:prefix_length]) != tuple(
            item.observation for item in bootstrap
        ) or safe_routes[:prefix_length] != tuple(item.route for item in bootstrap):
            raise ValueError("bootstrap_history does not match the exact manifest prefix")
        if any(
            item.reasons != (DETERMINISTIC_BOOTSTRAP_REASON,)
            for item in manifest.route_history[:prefix_length]
        ):
            raise ValueError(
                "bootstrap manifest routes must use the canonical deterministic bootstrap reason"
            )
        return cls(
            instance_id=manifest.instance_id,
            candidate_id=manifest.candidate_id,
            lifecycle_stage=manifest.lifecycle_stage,
            risk_profile=manifest.risk_profile,
            provenance=tuple(sorted(normalized_provenance.items())),
            bootstrap_history=bootstrap,
            evidence_history=tuple(safe_evidence[prefix_length:]),
            route_history=safe_routes[prefix_length:],
            source_manifest_sha256=manifest.canonical_digest(),
        )

    def history_sha256(self) -> str:
        return _canonical_sha256(
            {
                "contract": "bench-cleanser-router-history-v2",
                "bootstrap_steps": [item.to_dict() for item in self.bootstrap_history],
                "randomized_steps": [
                    {
                        "route": route.to_dict(),
                        "evidence": _router_evidence_dict(evidence),
                    }
                    for route, evidence in zip(
                        self.route_history,
                        self.evidence_history,
                    )
                ],
            }
        )

    def canonical_digest(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instance_id": self.instance_id,
            "candidate_id": self.candidate_id,
            "lifecycle_stage": self.lifecycle_stage.value,
            "risk_profile": _risk_profile_dict(self.risk_profile),
            "provenance": dict(self.provenance),
            "bootstrap_history": [item.to_dict() for item in self.bootstrap_history],
            "evidence_history": [_router_evidence_dict(item) for item in self.evidence_history],
            "route_history": [item.to_dict() for item in self.route_history],
            "source_manifest_sha256": self.source_manifest_sha256,
        }

    @classmethod
    def from_dict(cls, value: Any) -> RouterStateView:
        data = _object(value, "router_state")
        fields = {
            "schema_version",
            "instance_id",
            "candidate_id",
            "lifecycle_stage",
            "risk_profile",
            "provenance",
            "bootstrap_history",
            "evidence_history",
            "route_history",
            "source_manifest_sha256",
        }
        _require_exact_fields(data, fields, "router_state")
        provenance_data = _object(data["provenance"], "router_state.provenance")
        bootstrap_data = _array(
            data["bootstrap_history"],
            "router_state.bootstrap_history",
        )
        evidence_data = _array(
            data["evidence_history"],
            "router_state.evidence_history",
        )
        route_data = _array(data["route_history"], "router_state.route_history")
        return cls(
            schema_version=_string(data["schema_version"], "router_state.schema_version"),
            instance_id=_string(data["instance_id"], "router_state.instance_id"),
            candidate_id=_candidate_id(
                data["candidate_id"],
                "router_state.candidate_id",
            ),
            lifecycle_stage=_enum(
                LifecycleStage,
                data["lifecycle_stage"],
                "router_state.lifecycle_stage",
            ),
            risk_profile=_risk_profile_from_dict(data["risk_profile"]),
            provenance=tuple(
                sorted(
                    (
                        _string(key, "router_state.provenance key"),
                        _string(item, f"router_state.provenance[{key!r}]"),
                    )
                    for key, item in provenance_data.items()
                )
            ),
            bootstrap_history=tuple(
                BootstrapHistoryStep.from_dict(item, index)
                for index, item in enumerate(bootstrap_data)
            ),
            evidence_history=tuple(
                _router_evidence_from_dict(item, index) for index, item in enumerate(evidence_data)
            ),
            route_history=tuple(
                _router_route_from_dict(item, index) for index, item in enumerate(route_data)
            ),
            source_manifest_sha256=_digest(
                data["source_manifest_sha256"],
                "router_state.source_manifest_sha256",
            ),
        )


@dataclass(frozen=True)
class ActionOffer:
    """One stable action intervention in the complete policy catalog.

    ``action_spec_sha256`` should be produced with
    :func:`canonical_action_spec_sha256`; the immutable preimage must be stored
    by the eventual executor because this logging schema intentionally carries
    only its content identity.
    """

    action_id: str
    route_action: RouteAction
    evidence_kind: EvidenceKind | None
    adapter_id: str
    adapter_version: str
    action_spec_sha256: str
    available: bool
    availability_reason: str
    expected_cost: EvidenceCost

    def __post_init__(self) -> None:
        _string(self.action_id, "action_offer.action_id", identifier=True)
        if not isinstance(self.route_action, RouteAction):
            raise ValueError("action_offer.route_action must be a RouteAction")
        expected_kind = _ACTION_EVIDENCE_KIND.get(self.route_action)
        if self.route_action in _TERMINAL_ACTIONS:
            if self.evidence_kind is not None:
                raise ValueError("terminal action offers cannot declare evidence_kind")
            if self.expected_cost != EvidenceCost():
                raise ValueError("terminal action offers must have zero expected cost")
        elif expected_kind is None or self.evidence_kind != expected_kind:
            raise ValueError("acquisition action offer has an incompatible evidence_kind")
        _string(self.adapter_id, "action_offer.adapter_id", identifier=True)
        _string(
            self.adapter_version,
            "action_offer.adapter_version",
            identifier=True,
        )
        object.__setattr__(
            self,
            "action_spec_sha256",
            _digest(
                self.action_spec_sha256,
                "action_offer.action_spec_sha256",
            ),
        )
        if not isinstance(self.available, bool):
            raise ValueError("action_offer.available must be a boolean")
        _string(self.availability_reason, "action_offer.availability_reason")
        if not isinstance(self.expected_cost, EvidenceCost):
            raise ValueError("action_offer.expected_cost must be an EvidenceCost")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "route_action": self.route_action.value,
            "evidence_kind": (self.evidence_kind.value if self.evidence_kind is not None else None),
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "action_spec_sha256": self.action_spec_sha256,
            "available": self.available,
            "availability_reason": self.availability_reason,
            "expected_cost": _cost_dict(self.expected_cost),
        }

    @classmethod
    def from_dict(cls, value: Any, index: int = 0) -> ActionOffer:
        field_name = f"action_catalog[{index}]"
        data = _object(value, field_name)
        fields = {
            "action_id",
            "route_action",
            "evidence_kind",
            "adapter_id",
            "adapter_version",
            "action_spec_sha256",
            "available",
            "availability_reason",
            "expected_cost",
        }
        _require_exact_fields(data, fields, field_name)
        raw_kind = data["evidence_kind"]
        return cls(
            action_id=_string(
                data["action_id"],
                f"{field_name}.action_id",
                identifier=True,
            ),
            route_action=_enum(
                RouteAction,
                data["route_action"],
                f"{field_name}.route_action",
            ),
            evidence_kind=(
                None
                if raw_kind is None
                else _enum(
                    EvidenceKind,
                    raw_kind,
                    f"{field_name}.evidence_kind",
                )
            ),
            adapter_id=_string(
                data["adapter_id"],
                f"{field_name}.adapter_id",
                identifier=True,
            ),
            adapter_version=_string(
                data["adapter_version"],
                f"{field_name}.adapter_version",
                identifier=True,
            ),
            action_spec_sha256=_digest(
                data["action_spec_sha256"],
                f"{field_name}.action_spec_sha256",
            ),
            available=_boolean(data["available"], f"{field_name}.available"),
            availability_reason=_string(
                data["availability_reason"],
                f"{field_name}.availability_reason",
            ),
            expected_cost=_cost_from_dict(
                data["expected_cost"],
                f"{field_name}.expected_cost",
            ),
        )


@dataclass(frozen=True)
class BehaviorProbability:
    """Logged behavior-policy probability for one available action."""

    action_id: str
    propensity: float

    def __post_init__(self) -> None:
        _string(self.action_id, "behavior_probability.action_id", identifier=True)
        if (
            isinstance(self.propensity, bool)
            or not isinstance(self.propensity, (int, float))
            or not isfinite(self.propensity)
            or not 0.0 < self.propensity <= 1.0
        ):
            raise ValueError("behavior propensity must be finite and in (0, 1]")
        object.__setattr__(self, "propensity", float(self.propensity))

    def to_dict(self) -> dict[str, Any]:
        return {"action_id": self.action_id, "propensity": self.propensity}

    @classmethod
    def from_dict(cls, value: Any, index: int = 0) -> BehaviorProbability:
        field_name = f"behavior_distribution[{index}]"
        data = _object(value, field_name)
        _require_exact_fields(data, {"action_id", "propensity"}, field_name)
        return cls(
            action_id=_string(
                data["action_id"],
                f"{field_name}.action_id",
                identifier=True,
            ),
            propensity=_number(
                data["propensity"],
                f"{field_name}.propensity",
            ),
        )


def preferred_uniform_behavior_distribution(
    action_catalog: Sequence[ActionOffer],
    *,
    preferred_action_id: str,
    exploration_mass: float,
) -> tuple[BehaviorProbability, ...]:
    """Construct a positive-support preferred/uniform behavior policy.

    ``exploration_mass`` is spread uniformly over every available action and
    the remaining mass is assigned to ``preferred_action_id``.  Unavailable
    actions remain visible in the complete catalog but do not enter the
    distribution.  The returned order is the catalog's canonical action-ID
    order, suitable for :class:`LoggedPolicyDecision`.

    This function constructs declared propensities; it does not establish that
    the caller persisted them before acting or that the preferred action came
    from the declared policy implementation.
    """

    if not isinstance(action_catalog, (list, tuple)) or not action_catalog:
        raise ValueError("action_catalog must be a non-empty sequence")
    if any(not isinstance(offer, ActionOffer) for offer in action_catalog):
        raise ValueError("action_catalog must contain ActionOffer values")
    catalog = tuple(action_catalog)
    action_ids = [offer.action_id for offer in catalog]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("action_catalog cannot contain duplicate action_id values")
    if action_ids != sorted(action_ids):
        raise ValueError("action_catalog must be ordered by action_id")

    preferred = _string(
        preferred_action_id,
        "preferred_action_id",
        identifier=True,
    )
    if (
        isinstance(exploration_mass, bool)
        or not isinstance(exploration_mass, (int, float))
        or not isfinite(exploration_mass)
        or not 0.0 < exploration_mass <= 1.0
    ):
        raise ValueError("exploration_mass must be finite and in (0, 1]")
    exploration = float(exploration_mass)

    available = tuple(offer for offer in catalog if offer.available)
    if not available:
        raise ValueError("action_catalog must contain at least one available action")
    available_ids = {offer.action_id for offer in available}
    if preferred not in available_ids:
        raise ValueError("preferred_action_id must identify an available action")

    uniform_mass = exploration / len(available)
    exploitation_mass = 1.0 - exploration
    distribution = tuple(
        BehaviorProbability(
            action_id=offer.action_id,
            propensity=(
                fsum((uniform_mass, exploitation_mass))
                if offer.action_id == preferred
                else uniform_mass
            ),
        )
        for offer in available
    )
    if not isclose(
        fsum(item.propensity for item in distribution),
        1.0,
        rel_tol=0.0,
        abs_tol=_PROPENSITY_TOLERANCE,
    ):
        raise ValueError("constructed behavior propensities do not sum to 1")
    return distribution


def sample_behavior_action(
    distribution: Sequence[BehaviorProbability],
    *,
    sampler_draw: float,
) -> str:
    """Select one action with the policy log's canonical inverse-CDF rule."""

    if not isinstance(distribution, (list, tuple)) or not distribution:
        raise ValueError("behavior_distribution must be a non-empty sequence")
    if any(not isinstance(item, BehaviorProbability) for item in distribution):
        raise ValueError("behavior_distribution must contain BehaviorProbability values")
    normalized = tuple(distribution)
    action_ids = [item.action_id for item in normalized]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("behavior_distribution cannot contain duplicate action_id values")
    if action_ids != sorted(action_ids):
        raise ValueError("behavior_distribution must be ordered by action_id")
    if not isclose(
        fsum(item.propensity for item in normalized),
        1.0,
        rel_tol=0.0,
        abs_tol=_PROPENSITY_TOLERANCE,
    ):
        raise ValueError("behavior propensities must sum to 1")
    draw = _number(sampler_draw, "sampler_draw")
    if not 0.0 <= draw < 1.0:
        raise ValueError("sampler_draw must be in [0, 1)")
    return _sample_action(normalized, draw)


@dataclass(frozen=True)
class LoggedPolicyDecision:
    """One complete write-ahead policy decision and hash-chain link."""

    trajectory_id: str
    decision_id: str
    acquisition_id: str | None
    decision_step: int
    decided_at: str
    instance_id: str
    candidate_id: str
    manifest_sha256: str
    history_sha256: str
    router_state_sha256: str
    prior_trajectory_head_sha256: str
    policy_id: str
    policy_version: str
    policy_code_config_sha256: str
    action_catalog: tuple[ActionOffer, ...]
    behavior_distribution: tuple[BehaviorProbability, ...]
    chosen_action_id: str
    chosen_propensity: float
    selection_reason_code: str
    sampler_id: str
    sampler_version: str
    sampler_draw: float
    router_state: RouterStateView
    decision_sha256: str = ""
    trajectory_head_sha256: str = ""
    schema_version: str = POLICY_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != POLICY_DECISION_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported policy-decision schema_version {self.schema_version!r}; "
                f"expected {POLICY_DECISION_SCHEMA_VERSION!r}"
            )
        _string(self.trajectory_id, "trajectory_id", identifier=True)
        decision_id = _string(self.decision_id, "decision_id")
        if not _DECISION_ID_RE.fullmatch(decision_id):
            raise ValueError("decision_id must be 'dec-' plus 32 lowercase hex characters")
        if self.acquisition_id is not None:
            acquisition_id = _string(self.acquisition_id, "acquisition_id")
            if not _ACQUISITION_ID_RE.fullmatch(acquisition_id):
                raise ValueError("acquisition_id must be 'acq-' plus 32 lowercase hex characters")
        if (
            isinstance(self.decision_step, bool)
            or not isinstance(self.decision_step, int)
            or self.decision_step < 0
        ):
            raise ValueError("decision_step must be a non-negative integer")
        object.__setattr__(
            self,
            "decided_at",
            _canonical_timestamp(self.decided_at, "decided_at"),
        )
        _string(self.instance_id, "instance_id")
        object.__setattr__(
            self,
            "candidate_id",
            _candidate_id(self.candidate_id, "candidate_id"),
        )
        for name in (
            "manifest_sha256",
            "history_sha256",
            "router_state_sha256",
            "prior_trajectory_head_sha256",
            "policy_code_config_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        for name in ("policy_id", "policy_version", "sampler_id", "sampler_version"):
            _string(getattr(self, name), name, identifier=True)
        if (
            self.sampler_id != CANONICAL_SAMPLER_ID
            or self.sampler_version != CANONICAL_SAMPLER_VERSION
        ):
            raise ValueError("policy decisions require the canonical inverse-cdf/v1 sampler")
        if not isinstance(self.router_state, RouterStateView):
            raise ValueError("router_state must be a RouterStateView")
        if self.instance_id != self.router_state.instance_id:
            raise ValueError("instance_id contradicts router_state")
        if self.candidate_id != self.router_state.candidate_id:
            raise ValueError("candidate_id contradicts router_state")
        if self.manifest_sha256 != self.router_state.source_manifest_sha256:
            raise ValueError("manifest_sha256 contradicts router_state")
        if self.history_sha256 != self.router_state.history_sha256():
            raise ValueError("history_sha256 contradicts router_state")
        if self.router_state_sha256 != self.router_state.canonical_digest():
            raise ValueError("router_state_sha256 contradicts router_state")
        if self.decision_step != len(self.router_state.evidence_history):
            raise ValueError("decision_step must equal the completed router history length")
        if self.decision_step == 0:
            if self.prior_trajectory_head_sha256 != GENESIS_TRAJECTORY_HEAD_SHA256:
                raise ValueError("decision step zero must use the genesis prior head")
        elif self.prior_trajectory_head_sha256 == GENESIS_TRAJECTORY_HEAD_SHA256:
            raise ValueError("nonzero decision steps cannot use the genesis prior head")

        if not isinstance(self.action_catalog, (list, tuple)) or any(
            not isinstance(item, ActionOffer) for item in self.action_catalog
        ):
            raise ValueError("action_catalog must contain ActionOffer values")
        catalog = tuple(self.action_catalog)
        action_ids = [item.action_id for item in catalog]
        if action_ids != sorted(action_ids):
            raise ValueError("action_catalog must be ordered by action_id")
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("action_catalog cannot contain duplicate action_id values")
        route_actions = [item.route_action for item in catalog]
        missing_actions = sorted(action.value for action in set(RouteAction) - set(route_actions))
        extra_actions = sorted(action.value for action in set(route_actions) - set(RouteAction))
        if missing_actions or extra_actions:
            raise ValueError(
                "action_catalog must represent every RouteAction; "
                f"missing={missing_actions}, extra={extra_actions}"
            )
        terminal_counts = {action: route_actions.count(action) for action in _TERMINAL_ACTIONS}
        invalid_terminal_counts = {
            action.value: count for action, count in terminal_counts.items() if count != 1
        }
        if invalid_terminal_counts:
            raise ValueError(
                "terminal RouteAction values must each have exactly one offer; "
                f"counts={invalid_terminal_counts}"
            )
        abstain_offer = next(item for item in catalog if item.route_action == RouteAction.ABSTAIN)
        if not abstain_offer.available:
            raise ValueError("action_catalog must provide positive behavior support for abstention")
        declared_availability = {
            RouteAction.RUN_TARGETED: (self.router_state.risk_profile.targeted_execution_available),
            RouteAction.RUN_FULL: (self.router_state.risk_profile.full_execution_available),
            RouteAction.HARDEN_ORACLE: (self.router_state.risk_profile.oracle_hardening_available),
        }
        contradictory_actions = sorted(
            offer.route_action.value
            for offer in catalog
            if offer.available
            and offer.route_action in declared_availability
            and not declared_availability[offer.route_action]
        )
        if contradictory_actions:
            raise ValueError(
                "available action mask contradicts the router risk profile: "
                f"{contradictory_actions}"
            )
        object.__setattr__(self, "action_catalog", catalog)

        if not isinstance(self.behavior_distribution, (list, tuple)) or any(
            not isinstance(item, BehaviorProbability) for item in self.behavior_distribution
        ):
            raise ValueError("behavior_distribution must contain BehaviorProbability values")
        distribution = tuple(self.behavior_distribution)
        distribution_ids = [item.action_id for item in distribution]
        if distribution_ids != sorted(distribution_ids):
            raise ValueError("behavior_distribution must be ordered by action_id")
        if len(distribution_ids) != len(set(distribution_ids)):
            raise ValueError("behavior_distribution cannot contain duplicate action_id values")
        available_ids = {item.action_id for item in catalog if item.available}
        if set(distribution_ids) != available_ids:
            missing = sorted(available_ids - set(distribution_ids))
            unavailable = sorted(set(distribution_ids) - available_ids)
            raise ValueError(
                "behavior_distribution must cover exactly the available actions; "
                f"missing={missing}, unavailable={unavailable}"
            )
        if not isclose(
            fsum(item.propensity for item in distribution),
            1.0,
            rel_tol=0.0,
            abs_tol=_PROPENSITY_TOLERANCE,
        ):
            raise ValueError("behavior propensities must sum to 1")
        object.__setattr__(self, "behavior_distribution", distribution)

        chosen_action_id = _string(
            self.chosen_action_id,
            "chosen_action_id",
            identifier=True,
        )
        probability_by_id = {item.action_id: item.propensity for item in distribution}
        chosen_probability = probability_by_id.get(chosen_action_id)
        if chosen_probability is None:
            raise ValueError("chosen_action_id must identify an available action")
        if (
            isinstance(self.chosen_propensity, bool)
            or not isinstance(self.chosen_propensity, (int, float))
            or not isfinite(self.chosen_propensity)
            or not 0.0 < self.chosen_propensity <= 1.0
        ):
            raise ValueError("chosen_propensity must be finite and in (0, 1]")
        if float(self.chosen_propensity) != chosen_probability:
            raise ValueError("chosen_propensity does not match the behavior distribution")
        object.__setattr__(self, "chosen_propensity", float(self.chosen_propensity))
        _string(
            self.selection_reason_code,
            "selection_reason_code",
            identifier=True,
        )
        sampler_draw = _number(self.sampler_draw, "sampler_draw")
        if not 0.0 <= sampler_draw < 1.0:
            raise ValueError("sampler_draw must be in [0, 1)")
        object.__setattr__(self, "sampler_draw", sampler_draw)
        sampled_action = _sample_action(distribution, sampler_draw)
        if sampled_action != chosen_action_id:
            raise ValueError("chosen_action_id does not match the canonical sampler draw")
        catalog_by_id = {item.action_id: item for item in catalog}
        chosen_offer = catalog_by_id[chosen_action_id]
        if chosen_offer.route_action in _TERMINAL_ACTIONS:
            if self.acquisition_id is not None:
                raise ValueError("terminal policy decisions cannot allocate acquisition_id")
        elif self.acquisition_id is None:
            raise ValueError("acquisition policy decisions require acquisition_id")

        computed_decision_sha256 = _canonical_sha256(self._decision_payload())
        if self.decision_sha256:
            supplied_decision_sha256 = _digest(
                self.decision_sha256,
                "decision_sha256",
            )
            if supplied_decision_sha256 != computed_decision_sha256:
                raise ValueError("decision_sha256 does not match canonical decision content")
        object.__setattr__(self, "decision_sha256", computed_decision_sha256)
        computed_head = _canonical_sha256(
            {
                "contract": POLICY_DECISION_CHAIN_CONTRACT,
                "prior_trajectory_head_sha256": self.prior_trajectory_head_sha256,
                "decision_sha256": computed_decision_sha256,
            }
        )
        if self.trajectory_head_sha256:
            supplied_head = _digest(
                self.trajectory_head_sha256,
                "trajectory_head_sha256",
            )
            if supplied_head != computed_head:
                raise ValueError("trajectory_head_sha256 does not match the decision chain")
        object.__setattr__(self, "trajectory_head_sha256", computed_head)

    @property
    def chosen_offer(self) -> ActionOffer:
        return next(item for item in self.action_catalog if item.action_id == self.chosen_action_id)

    @property
    def terminal(self) -> bool:
        return self.chosen_offer.route_action in _TERMINAL_ACTIONS

    def _decision_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trajectory_id": self.trajectory_id,
            "decision_id": self.decision_id,
            "acquisition_id": self.acquisition_id,
            "decision_step": self.decision_step,
            "decided_at": self.decided_at,
            "instance_id": self.instance_id,
            "candidate_id": self.candidate_id,
            "manifest_sha256": self.manifest_sha256,
            "history_sha256": self.history_sha256,
            "router_state_sha256": self.router_state_sha256,
            "prior_trajectory_head_sha256": self.prior_trajectory_head_sha256,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_code_config_sha256": self.policy_code_config_sha256,
            "action_catalog": [item.to_dict() for item in self.action_catalog],
            "behavior_distribution": [item.to_dict() for item in self.behavior_distribution],
            "chosen_action_id": self.chosen_action_id,
            "chosen_propensity": self.chosen_propensity,
            "selection_reason_code": self.selection_reason_code,
            "sampler_id": self.sampler_id,
            "sampler_version": self.sampler_version,
            "sampler_draw": self.sampler_draw,
            "router_state": self.router_state.to_dict(),
        }

    def canonical_digest(self) -> str:
        computed = _canonical_sha256(self._decision_payload())
        if computed != self.decision_sha256:
            raise ValueError("policy decision changed after validation")
        computed_head = _canonical_sha256(
            {
                "contract": POLICY_DECISION_CHAIN_CONTRACT,
                "prior_trajectory_head_sha256": self.prior_trajectory_head_sha256,
                "decision_sha256": computed,
            }
        )
        if computed_head != self.trajectory_head_sha256:
            raise ValueError("policy decision chain head changed after validation")
        return computed

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._decision_payload(),
            "decision_sha256": self.decision_sha256,
            "trajectory_head_sha256": self.trajectory_head_sha256,
        }

    @classmethod
    def from_dict(cls, value: Any) -> LoggedPolicyDecision:
        data = _object(value, "policy_decision")
        fields = {
            "schema_version",
            "trajectory_id",
            "decision_id",
            "acquisition_id",
            "decision_step",
            "decided_at",
            "instance_id",
            "candidate_id",
            "manifest_sha256",
            "history_sha256",
            "router_state_sha256",
            "prior_trajectory_head_sha256",
            "policy_id",
            "policy_version",
            "policy_code_config_sha256",
            "action_catalog",
            "behavior_distribution",
            "chosen_action_id",
            "chosen_propensity",
            "selection_reason_code",
            "sampler_id",
            "sampler_version",
            "sampler_draw",
            "router_state",
            "decision_sha256",
            "trajectory_head_sha256",
        }
        _require_exact_fields(data, fields, "policy_decision")
        catalog = _array(data["action_catalog"], "policy_decision.action_catalog")
        distribution = _array(
            data["behavior_distribution"],
            "policy_decision.behavior_distribution",
        )
        acquisition_value = data["acquisition_id"]
        if acquisition_value is not None and not isinstance(acquisition_value, str):
            raise ValueError("policy_decision.acquisition_id must be a string or null")
        return cls(
            schema_version=_string(
                data["schema_version"],
                "policy_decision.schema_version",
            ),
            trajectory_id=_string(
                data["trajectory_id"],
                "policy_decision.trajectory_id",
                identifier=True,
            ),
            decision_id=_string(data["decision_id"], "policy_decision.decision_id"),
            acquisition_id=acquisition_value,
            decision_step=_integer(
                data["decision_step"],
                "policy_decision.decision_step",
            ),
            decided_at=_canonical_timestamp(
                data["decided_at"],
                "policy_decision.decided_at",
            ),
            instance_id=_string(data["instance_id"], "policy_decision.instance_id"),
            candidate_id=_candidate_id(
                data["candidate_id"],
                "policy_decision.candidate_id",
            ),
            manifest_sha256=_digest(
                data["manifest_sha256"],
                "policy_decision.manifest_sha256",
            ),
            history_sha256=_digest(
                data["history_sha256"],
                "policy_decision.history_sha256",
            ),
            router_state_sha256=_digest(
                data["router_state_sha256"],
                "policy_decision.router_state_sha256",
            ),
            prior_trajectory_head_sha256=_digest(
                data["prior_trajectory_head_sha256"],
                "policy_decision.prior_trajectory_head_sha256",
            ),
            policy_id=_string(
                data["policy_id"],
                "policy_decision.policy_id",
                identifier=True,
            ),
            policy_version=_string(
                data["policy_version"],
                "policy_decision.policy_version",
                identifier=True,
            ),
            policy_code_config_sha256=_digest(
                data["policy_code_config_sha256"],
                "policy_decision.policy_code_config_sha256",
            ),
            action_catalog=tuple(
                ActionOffer.from_dict(item, index) for index, item in enumerate(catalog)
            ),
            behavior_distribution=tuple(
                BehaviorProbability.from_dict(item, index)
                for index, item in enumerate(distribution)
            ),
            chosen_action_id=_string(
                data["chosen_action_id"],
                "policy_decision.chosen_action_id",
                identifier=True,
            ),
            chosen_propensity=_number(
                data["chosen_propensity"],
                "policy_decision.chosen_propensity",
            ),
            selection_reason_code=_string(
                data["selection_reason_code"],
                "policy_decision.selection_reason_code",
                identifier=True,
            ),
            sampler_id=_string(
                data["sampler_id"],
                "policy_decision.sampler_id",
                identifier=True,
            ),
            sampler_version=_string(
                data["sampler_version"],
                "policy_decision.sampler_version",
                identifier=True,
            ),
            sampler_draw=_number(
                data["sampler_draw"],
                "policy_decision.sampler_draw",
            ),
            router_state=RouterStateView.from_dict(data["router_state"]),
            decision_sha256=_digest(
                data["decision_sha256"],
                "policy_decision.decision_sha256",
            ),
            trajectory_head_sha256=_digest(
                data["trajectory_head_sha256"],
                "policy_decision.trajectory_head_sha256",
            ),
        )


def _sample_action(
    distribution: Sequence[BehaviorProbability],
    draw: float,
) -> str:
    cumulative = 0.0
    for index, item in enumerate(distribution):
        cumulative = fsum((cumulative, item.propensity))
        if draw < cumulative or index == len(distribution) - 1:
            return item.action_id
    raise ValueError("behavior distribution is empty")  # pragma: no cover


def load_logged_policy_decision(stream: TextIO) -> LoggedPolicyDecision:
    """Load exactly one strict, self-verifying policy decision."""

    try:
        value = strict_json_load(stream)
    except ValueError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    return LoggedPolicyDecision.from_dict(value)


def validate_policy_decision_chain(
    decisions: Sequence[LoggedPolicyDecision],
) -> None:
    """Validate one complete trajectory without computing an OPE estimate."""

    if not decisions:
        raise ValueError("policy decision chain cannot be empty")
    seen_decision_ids: set[str] = set()
    seen_acquisition_ids: set[str] = set()
    for index, current in enumerate(decisions):
        if not isinstance(current, LoggedPolicyDecision):
            raise ValueError(f"decisions[{index}] must be a LoggedPolicyDecision")
        if current.decision_id in seen_decision_ids:
            raise ValueError("policy decision chain reuses decision_id")
        seen_decision_ids.add(current.decision_id)
        if current.acquisition_id is not None:
            if current.acquisition_id in seen_acquisition_ids:
                raise ValueError("policy decision chain reuses acquisition_id")
            seen_acquisition_ids.add(current.acquisition_id)
        if current.decision_step != index:
            raise ValueError("policy decision chain steps must start at zero and be contiguous")
        current.canonical_digest()
        if index == 0:
            if current.prior_trajectory_head_sha256 != (GENESIS_TRAJECTORY_HEAD_SHA256):
                raise ValueError("first policy decision does not use the genesis head")
            continue
        previous = decisions[index - 1]
        if previous.terminal:
            raise ValueError("terminal policy decisions cannot have successors")
        if current.trajectory_id != previous.trajectory_id:
            raise ValueError("policy decision chain changes trajectory_id")
        if (
            current.instance_id != previous.instance_id
            or current.candidate_id != previous.candidate_id
        ):
            raise ValueError("policy decision chain changes candidate identity")
        if current.prior_trajectory_head_sha256 != previous.trajectory_head_sha256:
            raise ValueError("policy decision chain has a broken prior-head link")
        if current.decided_at < previous.decided_at:
            raise ValueError("policy decision timestamps run backwards")
        prior_state = previous.router_state
        current_state = current.router_state
        if (
            current_state.lifecycle_stage != prior_state.lifecycle_stage
            or current_state.risk_profile != prior_state.risk_profile
            or current_state.provenance != prior_state.provenance
            or current_state.bootstrap_history != prior_state.bootstrap_history
        ):
            raise ValueError("policy decision chain changes immutable router baseline")
        prior_offers = {item.action_id: item for item in previous.action_catalog}
        current_offers = {item.action_id: item for item in current.action_catalog}
        for action_id in set(prior_offers).intersection(current_offers):
            prior_offer = prior_offers[action_id]
            current_offer = current_offers[action_id]
            prior_identity = (
                prior_offer.route_action,
                prior_offer.evidence_kind,
                prior_offer.adapter_id,
                prior_offer.adapter_version,
                prior_offer.action_spec_sha256,
            )
            current_identity = (
                current_offer.route_action,
                current_offer.evidence_kind,
                current_offer.adapter_id,
                current_offer.adapter_version,
                current_offer.action_spec_sha256,
            )
            if current_identity != prior_identity:
                raise ValueError(f"stable action_id {action_id!r} changes intervention identity")
        if current_state.evidence_history[:-1] != prior_state.evidence_history:
            raise ValueError("successor router state changes prior evidence history")
        if current_state.route_history[:-1] != prior_state.route_history:
            raise ValueError("successor router state changes prior route history")
        latest_evidence = current_state.evidence_history[-1]
        latest_route = current_state.route_history[-1]
        if latest_evidence.acquisition_id != previous.acquisition_id:
            raise ValueError("successor state does not contain the prior acquisition_id")
        if latest_route.action != previous.chosen_offer.route_action:
            raise ValueError("successor state route action contradicts the prior choice")
        if latest_evidence.kind != previous.chosen_offer.evidence_kind:
            raise ValueError("successor state evidence kind contradicts the prior choice")
