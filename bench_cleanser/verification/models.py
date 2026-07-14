"""Versioned data structures for selective SWE verification.

These models deliberately distinguish candidate evidence from verifier health.
An environment crash is not a failed candidate, and a passing weak test is not
an authoritative correctness label.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from math import isfinite
from typing import Any

MANIFEST_SCHEMA_VERSION = "0.2.0"


class _FrozenJSONDict(dict[str, Any]):
    """A JSON-native mapping that cannot be mutated after construction."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("verification metadata is immutable")

    __delitem__ = _immutable
    __ior__ = _immutable  # type: ignore[assignment]
    __setitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable  # type: ignore[assignment]
    setdefault = _immutable
    update = _immutable


def _freeze_json(
    value: Any,
    field_name: str,
    *,
    _seen: set[int] | None = None,
) -> Any:
    """Validate and defensively freeze a JSON-compatible value."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite number")
        return value

    seen = _seen if _seen is not None else set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen:
            raise ValueError(f"{field_name} contains a reference cycle")
        seen.add(identity)
        try:
            frozen: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{field_name} keys must be strings")
                frozen[key] = _freeze_json(
                    item,
                    f"{field_name}[{key!r}]",
                    _seen=seen,
                )
            return _FrozenJSONDict(frozen)
        finally:
            seen.remove(identity)

    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            raise ValueError(f"{field_name} contains a reference cycle")
        seen.add(identity)
        try:
            return tuple(
                _freeze_json(item, f"{field_name}[{index}]", _seen=seen)
                for index, item in enumerate(value)
            )
        finally:
            seen.remove(identity)

    raise ValueError(
        f"{field_name} contains non-JSON value of type {type(value).__name__}"
    )


class LifecycleStage(str, Enum):
    TRAINING = "training"
    ROLLOUT = "rollout"
    EVALUATION = "evaluation"


class EvidenceKind(str, Enum):
    STATIC = "static"
    SEMANTIC = "semantic"
    TARGETED_EXECUTION = "targeted_execution"
    FULL_EXECUTION = "full_execution"
    ORACLE_HARDENING = "oracle_hardening"
    HUMAN_ADJUDICATION = "human_adjudication"


class EvidenceStatus(str, Enum):
    SUPPORTS_CORRECT = "supports_correct"
    SUPPORTS_INCORRECT = "supports_incorrect"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


class RouteAction(str, Enum):
    RUN_STATIC = "run_static"
    RUN_SEMANTIC = "run_semantic"
    RUN_TARGETED = "run_targeted_execution"
    RUN_FULL = "run_full_execution"
    HARDEN_ORACLE = "harden_oracle"
    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"


def _check_probability(name: str, value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number between 0 and 1")
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value!r}")


@dataclass(frozen=True)
class EvidenceCost:
    """Measured acquisition cost; unset dimensions remain zero."""

    wall_seconds: float = 0.0
    cpu_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    storage_bytes: int = 0
    usd: float = 0.0

    def __post_init__(self) -> None:
        for name in ("wall_seconds", "cpu_seconds", "usd"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number")
            if value < 0:
                raise ValueError("evidence costs cannot be negative")
        for name in ("input_tokens", "output_tokens", "storage_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
            if value < 0:
                raise ValueError("evidence costs cannot be negative")


@dataclass(frozen=True)
class RiskProfile:
    """Deployable features known before the requested execution action.

    Gold patches, hidden tests, future commits, and eventual execution labels
    must not be encoded here.  They may appear in curator-only evidence records
    with ``privileged_inputs`` declared explicitly.
    """

    language: str = "unknown"
    files_changed: int = 0
    lines_changed: int = 0
    compiled_language: bool = False
    native_dependencies: bool = False
    touches_dependency_or_build_files: bool = False
    touches_schema_or_migration: bool = False
    touches_security_or_auth: bool = False
    touches_concurrency: bool = False
    touches_tests: bool = False
    generated_tests: bool = False
    semantic_disagreement: float = 0.0
    historical_environment_error_rate: float | None = None
    oracle_strength: float | None = None
    observed_flake_rate: float | None = None
    targeted_execution_available: bool = True
    full_execution_available: bool = True
    oracle_hardening_available: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.language, str) or not self.language.strip():
            raise ValueError("language must be a non-empty string")
        if (
            isinstance(self.files_changed, bool)
            or not isinstance(self.files_changed, int)
            or isinstance(self.lines_changed, bool)
            or not isinstance(self.lines_changed, int)
        ):
            raise ValueError("patch sizes must be integers")
        if self.files_changed < 0 or self.lines_changed < 0:
            raise ValueError("patch sizes cannot be negative")
        for name in (
            "compiled_language",
            "native_dependencies",
            "touches_dependency_or_build_files",
            "touches_schema_or_migration",
            "touches_security_or_auth",
            "touches_concurrency",
            "touches_tests",
            "generated_tests",
            "targeted_execution_available",
            "full_execution_available",
            "oracle_hardening_available",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")
        for name in (
            "semantic_disagreement",
            "historical_environment_error_rate",
            "oracle_strength",
            "observed_flake_rate",
        ):
            _check_probability(name, getattr(self, name))


@dataclass(frozen=True)
class EvidenceObservation:
    """One evidence acquisition event with explicit reliability metadata."""

    kind: EvidenceKind
    status: EvidenceStatus
    source: str
    source_version: str = ""
    acquisition_id: str = ""
    confidence: float | None = None
    candidate_probability: float | None = None
    verifier_validity: float | None = None
    calibrated_risk_upper_bound: float | None = None
    calibration_id: str = ""
    authoritative: bool = False
    privileged_inputs: tuple[str, ...] = ()
    cost: EvidenceCost = field(default_factory=EvidenceCost)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            raise ValueError("evidence kind must be an EvidenceKind")
        if not isinstance(self.status, EvidenceStatus):
            raise ValueError("evidence status must be an EvidenceStatus")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("evidence source cannot be empty")
        for name in ("source_version", "acquisition_id", "calibration_id"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be a string")
        if self.acquisition_id != self.acquisition_id.strip():
            raise ValueError("acquisition_id cannot have surrounding whitespace")
        if not isinstance(self.authoritative, bool):
            raise ValueError("authoritative must be a boolean")
        if not isinstance(self.cost, EvidenceCost):
            raise ValueError("cost must be an EvidenceCost")
        if not isinstance(self.privileged_inputs, (list, tuple)):
            raise ValueError("privileged_inputs must be a sequence of strings")
        privileged = tuple(self.privileged_inputs)
        if any(not isinstance(item, str) or not item.strip() for item in privileged):
            raise ValueError("privileged_inputs must contain non-empty strings")
        if len(privileged) != len(set(privileged)):
            raise ValueError("privileged_inputs cannot contain duplicates")
        object.__setattr__(self, "privileged_inputs", privileged)
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a JSON object")
        object.__setattr__(self, "metadata", _freeze_json(self.metadata, "metadata"))
        for name in (
            "confidence",
            "candidate_probability",
            "verifier_validity",
            "calibrated_risk_upper_bound",
        ):
            _check_probability(name, getattr(self, name))
        if self.calibrated_risk_upper_bound is not None and not self.calibration_id:
            raise ValueError("a calibrated risk bound requires calibration_id")
        if self.status in {EvidenceStatus.ERROR, EvidenceStatus.UNAVAILABLE}:
            if self.authoritative:
                raise ValueError("failed or unavailable evidence cannot be authoritative")
            if self.candidate_probability is not None:
                raise ValueError(
                    "verifier failure cannot carry a candidate correctness probability"
                )

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""

        return {
            "kind": self.kind.value,
            "status": self.status.value,
            "source": self.source,
            "source_version": self.source_version,
            "acquisition_id": self.acquisition_id,
            "confidence": self.confidence,
            "candidate_probability": self.candidate_probability,
            "verifier_validity": self.verifier_validity,
            "calibrated_risk_upper_bound": self.calibrated_risk_upper_bound,
            "calibration_id": self.calibration_id,
            "authoritative": self.authoritative,
            "privileged_inputs": list(self.privileged_inputs),
            "cost": _json_safe(asdict(self.cost)),
            "metadata": _json_safe(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Any) -> EvidenceObservation:
        """Load one strict evidence observation from decoded JSON."""

        return _parse_evidence(value, 0)


@dataclass(frozen=True)
class RouteDecision:
    action: RouteAction
    policy_version: str
    candidate_risk: float
    verifier_risk: float
    expected_information_gain: float
    estimated_relative_cost: float
    reasons: tuple[str, ...]
    terminal: bool = False
    scores_calibrated: bool = False
    calibration_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.action, RouteAction):
            raise ValueError("route action must be a RouteAction")
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ValueError("policy_version must be a non-empty string")
        for name in ("candidate_risk", "verifier_risk", "expected_information_gain"):
            _check_probability(name, getattr(self, name))
        if (
            isinstance(self.estimated_relative_cost, bool)
            or not isinstance(self.estimated_relative_cost, (int, float))
            or not isfinite(self.estimated_relative_cost)
        ):
            raise ValueError("estimated relative cost must be finite")
        if self.estimated_relative_cost < 0:
            raise ValueError("estimated relative cost cannot be negative")
        if not isinstance(self.reasons, (list, tuple)):
            raise ValueError("route decision reasons must be a sequence")
        reasons = tuple(self.reasons)
        if not reasons:
            raise ValueError("a route decision must explain itself")
        if any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
            raise ValueError("route decision reasons must be non-empty strings")
        object.__setattr__(self, "reasons", reasons)
        if not isinstance(self.terminal, bool) or not isinstance(
            self.scores_calibrated, bool
        ):
            raise ValueError("terminal and scores_calibrated must be booleans")
        if not isinstance(self.calibration_id, str):
            raise ValueError("calibration_id must be a string")
        if self.scores_calibrated and not self.calibration_id:
            raise ValueError("calibrated route scores require calibration_id")
        if not self.scores_calibrated and self.calibration_id:
            raise ValueError("uncalibrated route scores cannot claim calibration_id")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("canonical JSON cannot contain non-finite numbers")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError(f"canonical JSON cannot contain {type(value).__name__}")


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


def _optional_number(value: Any, field_name: str) -> float | None:
    return None if value is None else _number(value, field_name)


def _reject_unknown_fields(
    data: dict[str, Any],
    allowed: set[str],
    field_name: str,
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{field_name} has unknown fields: {unknown}")


def _parse_risk_profile(value: Any) -> RiskProfile:
    data = _object(value, "risk_profile")
    allowed = {
        "language",
        "files_changed",
        "lines_changed",
        "compiled_language",
        "native_dependencies",
        "touches_dependency_or_build_files",
        "touches_schema_or_migration",
        "touches_security_or_auth",
        "touches_concurrency",
        "touches_tests",
        "generated_tests",
        "semantic_disagreement",
        "historical_environment_error_rate",
        "oracle_strength",
        "observed_flake_rate",
        "targeted_execution_available",
        "full_execution_available",
        "oracle_hardening_available",
    }
    _reject_unknown_fields(data, allowed, "risk_profile")
    defaults = RiskProfile()
    return RiskProfile(
        language=_string(data.get("language", defaults.language), "risk_profile.language"),
        files_changed=_integer(
            data.get("files_changed", defaults.files_changed),
            "risk_profile.files_changed",
        ),
        lines_changed=_integer(
            data.get("lines_changed", defaults.lines_changed),
            "risk_profile.lines_changed",
        ),
        compiled_language=_boolean(
            data.get("compiled_language", defaults.compiled_language),
            "risk_profile.compiled_language",
        ),
        native_dependencies=_boolean(
            data.get("native_dependencies", defaults.native_dependencies),
            "risk_profile.native_dependencies",
        ),
        touches_dependency_or_build_files=_boolean(
            data.get(
                "touches_dependency_or_build_files",
                defaults.touches_dependency_or_build_files,
            ),
            "risk_profile.touches_dependency_or_build_files",
        ),
        touches_schema_or_migration=_boolean(
            data.get(
                "touches_schema_or_migration",
                defaults.touches_schema_or_migration,
            ),
            "risk_profile.touches_schema_or_migration",
        ),
        touches_security_or_auth=_boolean(
            data.get(
                "touches_security_or_auth",
                defaults.touches_security_or_auth,
            ),
            "risk_profile.touches_security_or_auth",
        ),
        touches_concurrency=_boolean(
            data.get("touches_concurrency", defaults.touches_concurrency),
            "risk_profile.touches_concurrency",
        ),
        touches_tests=_boolean(
            data.get("touches_tests", defaults.touches_tests),
            "risk_profile.touches_tests",
        ),
        generated_tests=_boolean(
            data.get("generated_tests", defaults.generated_tests),
            "risk_profile.generated_tests",
        ),
        semantic_disagreement=_number(
            data.get("semantic_disagreement", defaults.semantic_disagreement),
            "risk_profile.semantic_disagreement",
        ),
        historical_environment_error_rate=_optional_number(
            data.get(
                "historical_environment_error_rate",
                defaults.historical_environment_error_rate,
            ),
            "risk_profile.historical_environment_error_rate",
        ),
        oracle_strength=_optional_number(
            data.get("oracle_strength", defaults.oracle_strength),
            "risk_profile.oracle_strength",
        ),
        observed_flake_rate=_optional_number(
            data.get("observed_flake_rate", defaults.observed_flake_rate),
            "risk_profile.observed_flake_rate",
        ),
        targeted_execution_available=_boolean(
            data.get(
                "targeted_execution_available",
                defaults.targeted_execution_available,
            ),
            "risk_profile.targeted_execution_available",
        ),
        full_execution_available=_boolean(
            data.get("full_execution_available", defaults.full_execution_available),
            "risk_profile.full_execution_available",
        ),
        oracle_hardening_available=_boolean(
            data.get(
                "oracle_hardening_available",
                defaults.oracle_hardening_available,
            ),
            "risk_profile.oracle_hardening_available",
        ),
    )


def _parse_cost(value: Any, field_name: str) -> EvidenceCost:
    data = _object(value, field_name)
    allowed = {
        "wall_seconds",
        "cpu_seconds",
        "input_tokens",
        "output_tokens",
        "storage_bytes",
        "usd",
    }
    _reject_unknown_fields(data, allowed, field_name)
    return EvidenceCost(
        wall_seconds=_number(data.get("wall_seconds", 0.0), f"{field_name}.wall_seconds"),
        cpu_seconds=_number(data.get("cpu_seconds", 0.0), f"{field_name}.cpu_seconds"),
        input_tokens=_integer(data.get("input_tokens", 0), f"{field_name}.input_tokens"),
        output_tokens=_integer(data.get("output_tokens", 0), f"{field_name}.output_tokens"),
        storage_bytes=_integer(data.get("storage_bytes", 0), f"{field_name}.storage_bytes"),
        usd=_number(data.get("usd", 0.0), f"{field_name}.usd"),
    )


def _parse_evidence(value: Any, index: int) -> EvidenceObservation:
    field_name = f"evidence[{index}]"
    data = _object(value, field_name)
    allowed = {
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
        "privileged_inputs",
        "cost",
        "metadata",
    }
    _reject_unknown_fields(data, allowed, field_name)
    try:
        kind = EvidenceKind(_string(data.get("kind"), f"{field_name}.kind"))
        status = EvidenceStatus(_string(data.get("status"), f"{field_name}.status"))
    except ValueError as exc:
        raise ValueError(f"{field_name} contains an unknown enum value: {exc}") from exc
    privileged = _array(data.get("privileged_inputs", []), f"{field_name}.privileged_inputs")
    metadata = _object(data.get("metadata", {}), f"{field_name}.metadata")
    return EvidenceObservation(
        kind=kind,
        status=status,
        source=_string(data.get("source"), f"{field_name}.source", nonempty=True),
        source_version=_string(
            data.get("source_version", ""),
            f"{field_name}.source_version",
        ),
        acquisition_id=_string(
            data.get("acquisition_id", ""),
            f"{field_name}.acquisition_id",
        ),
        confidence=_optional_number(data.get("confidence"), f"{field_name}.confidence"),
        candidate_probability=_optional_number(
            data.get("candidate_probability"),
            f"{field_name}.candidate_probability",
        ),
        verifier_validity=_optional_number(
            data.get("verifier_validity"),
            f"{field_name}.verifier_validity",
        ),
        calibrated_risk_upper_bound=_optional_number(
            data.get("calibrated_risk_upper_bound"),
            f"{field_name}.calibrated_risk_upper_bound",
        ),
        calibration_id=_string(
            data.get("calibration_id", ""),
            f"{field_name}.calibration_id",
        ),
        authoritative=_boolean(
            data.get("authoritative", False),
            f"{field_name}.authoritative",
        ),
        privileged_inputs=tuple(
            _string(item, f"{field_name}.privileged_inputs[{item_index}]", nonempty=True)
            for item_index, item in enumerate(privileged)
        ),
        cost=_parse_cost(data.get("cost", {}), f"{field_name}.cost"),
        metadata=dict(metadata),
    )


def _parse_decision(value: Any, index: int) -> RouteDecision:
    field_name = f"route_history[{index}]"
    data = _object(value, field_name)
    allowed = {
        "action",
        "policy_version",
        "candidate_risk",
        "verifier_risk",
        "expected_information_gain",
        "estimated_relative_cost",
        "reasons",
        "terminal",
        "scores_calibrated",
        "calibration_id",
    }
    _reject_unknown_fields(data, allowed, field_name)
    try:
        action = RouteAction(_string(data.get("action"), f"{field_name}.action"))
    except ValueError as exc:
        raise ValueError(f"{field_name} contains an unknown action: {exc}") from exc
    reasons = _array(data.get("reasons"), f"{field_name}.reasons")
    return RouteDecision(
        action=action,
        policy_version=_string(
            data.get("policy_version"),
            f"{field_name}.policy_version",
            nonempty=True,
        ),
        candidate_risk=_number(
            data.get("candidate_risk"),
            f"{field_name}.candidate_risk",
        ),
        verifier_risk=_number(
            data.get("verifier_risk"),
            f"{field_name}.verifier_risk",
        ),
        expected_information_gain=_number(
            data.get("expected_information_gain"),
            f"{field_name}.expected_information_gain",
        ),
        estimated_relative_cost=_number(
            data.get("estimated_relative_cost"),
            f"{field_name}.estimated_relative_cost",
        ),
        reasons=tuple(
            _string(item, f"{field_name}.reasons[{item_index}]", nonempty=True)
            for item_index, item in enumerate(reasons)
        ),
        terminal=_boolean(data.get("terminal", False), f"{field_name}.terminal"),
        scores_calibrated=_boolean(
            data.get("scores_calibrated", False),
            f"{field_name}.scores_calibrated",
        ),
        calibration_id=_string(
            data.get("calibration_id", ""),
            f"{field_name}.calibration_id",
        ),
    )


@dataclass
class ValidityManifest:
    """Append-only evidence record shared across the SWE lifecycle."""

    instance_id: str
    candidate_id: str
    lifecycle_stage: LifecycleStage
    risk_profile: RiskProfile
    provenance: dict[str, str]
    evidence: list[EvidenceObservation] = field(default_factory=list)
    route_history: list[RouteDecision] = field(default_factory=list)
    schema_version: str = MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            not isinstance(self.instance_id, str)
            or not self.instance_id.strip()
            or not isinstance(self.candidate_id, str)
            or not self.candidate_id.strip()
        ):
            raise ValueError("instance_id and candidate_id are required")
        if not isinstance(self.lifecycle_stage, LifecycleStage):
            raise ValueError("lifecycle_stage must be a LifecycleStage")
        if not isinstance(self.risk_profile, RiskProfile):
            raise ValueError("risk_profile must be a RiskProfile")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a string mapping")
        normalized_provenance: dict[str, str] = {}
        for key, value in self.provenance.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("provenance keys must be non-empty strings")
            if not isinstance(value, str):
                raise ValueError(f"provenance value for {key!r} must be a string")
            normalized_provenance[key] = value
        self.provenance = normalized_provenance
        if not isinstance(self.evidence, list) or any(
            not isinstance(item, EvidenceObservation) for item in self.evidence
        ):
            raise ValueError("evidence must be a list of EvidenceObservation values")
        acquisition_ids = [
            item.acquisition_id for item in self.evidence if item.acquisition_id
        ]
        if len(acquisition_ids) != len(set(acquisition_ids)):
            raise ValueError("evidence acquisition_id values must be unique")
        if not isinstance(self.route_history, list) or any(
            not isinstance(item, RouteDecision) for item in self.route_history
        ):
            raise ValueError("route_history must be a list of RouteDecision values")
        self.evidence = list(self.evidence)
        self.route_history = list(self.route_history)
        if not isinstance(self.schema_version, str):
            raise ValueError("schema_version must be a string")
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported manifest schema_version {self.schema_version!r}; "
                f"expected {MANIFEST_SCHEMA_VERSION!r}"
            )

    def add_evidence(self, observation: EvidenceObservation) -> None:
        if not isinstance(observation, EvidenceObservation):
            raise ValueError("observation must be an EvidenceObservation")
        if observation.acquisition_id and any(
            item.acquisition_id == observation.acquisition_id
            for item in self.evidence
        ):
            raise ValueError(
                f"duplicate evidence acquisition_id {observation.acquisition_id!r}"
            )
        self.evidence.append(observation)

    def add_decision(self, decision: RouteDecision) -> None:
        if not isinstance(decision, RouteDecision):
            raise ValueError("decision must be a RouteDecision")
        self.route_history.append(decision)

    def to_dict(self) -> dict[str, Any]:
        if (
            not isinstance(self.instance_id, str)
            or not self.instance_id.strip()
            or not isinstance(self.candidate_id, str)
            or not self.candidate_id.strip()
        ):
            raise ValueError("instance_id and candidate_id are required")
        if not isinstance(self.lifecycle_stage, LifecycleStage):
            raise ValueError("lifecycle_stage must be a LifecycleStage")
        if not isinstance(self.risk_profile, RiskProfile):
            raise ValueError("risk_profile must be a RiskProfile")
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError("manifest schema_version changed after validation")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a string mapping")
        if not isinstance(self.evidence, list):
            raise ValueError("evidence must be a list")
        if not isinstance(self.route_history, list):
            raise ValueError("route_history must be a list")
        provenance: dict[str, str] = {}
        for key, value in self.provenance.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("provenance keys must be non-empty strings")
            if not isinstance(value, str):
                raise ValueError(f"provenance value for {key!r} must be a string")
            provenance[key] = value
        if any(not isinstance(item, EvidenceObservation) for item in self.evidence):
            raise ValueError("evidence contains an invalid observation")
        acquisition_ids = [
            item.acquisition_id for item in self.evidence if item.acquisition_id
        ]
        if len(acquisition_ids) != len(set(acquisition_ids)):
            raise ValueError("evidence acquisition_id values must be unique")
        if any(not isinstance(item, RouteDecision) for item in self.route_history):
            raise ValueError("route_history contains an invalid decision")
        return {
            "instance_id": self.instance_id,
            "candidate_id": self.candidate_id,
            "lifecycle_stage": self.lifecycle_stage.value,
            "risk_profile": _json_safe(asdict(self.risk_profile)),
            "provenance": provenance,
            "evidence": [item.to_dict() for item in self.evidence],
            "route_history": [
                _json_safe(asdict(item)) for item in self.route_history
            ],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ValidityManifest:
        """Load a strict, versioned manifest from decoded JSON data."""

        data = _object(value, "manifest")
        allowed = {
            "instance_id",
            "candidate_id",
            "lifecycle_stage",
            "risk_profile",
            "provenance",
            "evidence",
            "route_history",
            "schema_version",
        }
        _reject_unknown_fields(data, allowed, "manifest")
        schema_version = _string(
            data.get("schema_version"),
            "manifest.schema_version",
            nonempty=True,
        )
        if schema_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported manifest schema_version {schema_version!r}; "
                f"expected {MANIFEST_SCHEMA_VERSION!r}"
            )
        try:
            lifecycle_stage = LifecycleStage(
                _string(data.get("lifecycle_stage"), "manifest.lifecycle_stage")
            )
        except ValueError as exc:
            raise ValueError(f"manifest has unknown lifecycle_stage: {exc}") from exc
        provenance_data = _object(data.get("provenance"), "manifest.provenance")
        provenance = {
            _string(key, "manifest.provenance key", nonempty=True): _string(
                item,
                f"manifest.provenance[{key!r}]",
            )
            for key, item in provenance_data.items()
        }
        evidence_data = _array(data.get("evidence", []), "manifest.evidence")
        route_data = _array(data.get("route_history", []), "manifest.route_history")
        return cls(
            instance_id=_string(
                data.get("instance_id"),
                "manifest.instance_id",
                nonempty=True,
            ),
            candidate_id=_string(
                data.get("candidate_id"),
                "manifest.candidate_id",
                nonempty=True,
            ),
            lifecycle_stage=lifecycle_stage,
            risk_profile=_parse_risk_profile(data.get("risk_profile")),
            provenance=provenance,
            evidence=[
                _parse_evidence(item, index)
                for index, item in enumerate(evidence_data)
            ],
            route_history=[
                _parse_decision(item, index)
                for index, item in enumerate(route_data)
            ],
            schema_version=schema_version,
        )

    def canonical_digest(self) -> str:
        """Return a stable content digest for provenance joins."""

        encoded = json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
