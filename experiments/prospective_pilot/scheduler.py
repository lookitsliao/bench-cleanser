"""Deterministic three-candidate scheduler for the prospective pilot.

The package-level policy log records ``P(action | candidate, history)``.  This
study-local layer schedules one write-ahead decision for every nonterminal
candidate in a fixed candidate round, then records the product and summed-log
identity for the whole task trajectory.  Candidate scheduling itself is
deterministic and therefore has probability one.

The fixed order and action draws use the exact seeds and byte-level generator
contract in ``collection_policy.json``.  The schema contains only opaque
candidate identities, digest-bound safe state, a reason-free projection of the
bound router decision, complete action catalogs, probabilities, and hashes.  It
has no field for hosted outcomes, curator truth, model/submission names, rewards,
or free-form metadata.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from math import exp, fsum, isclose, isfinite, log
from typing import Any, TextIO, TypeVar, cast

from bench_cleanser.verification._io import (
    strict_json_dumps,
    strict_json_load,
    strict_json_loads,
)
from bench_cleanser.verification.models import (
    RouteAction,
    RouteDecision,
    ValidityManifest,
)
from bench_cleanser.verification.policy_log import (
    CANONICAL_SAMPLER_ID,
    CANONICAL_SAMPLER_VERSION,
    GENESIS_TRAJECTORY_HEAD_SHA256,
    ActionOffer,
    BehaviorProbability,
    LoggedPolicyDecision,
    RouterStateView,
    preferred_uniform_behavior_distribution,
    sample_behavior_action,
    validate_policy_decision_chain,
)
from bench_cleanser.verification.router import ConservativeRouter, RoutingPolicy
from experiments.prospective_pilot.proposal_policy import (
    ACCEPT_ACTION_ID,
    REJECT_ACTION_ID,
    TerminalProposal,
    terminal_proposal,
)
from experiments.prospective_pilot.proposal_policy import (
    preferred_action_id as proposal_preferred_action_id,
)

TASK_ROUND_SCHEMA_VERSION = "prospective-pilot-task-round-0.3.0"
TASK_SELECTION_SCHEMA_VERSION = "prospective-pilot-task-selection-0.1.0"
SCHEDULER_CHAIN_CONTRACT = "bench-cleanser-prospective-task-round-chain-v1"
SCHEDULER_STUDY_ID = "matched-24-independent-evidence-development-pilot-v2"
SCHEDULER_GENESIS_SHA256 = GENESIS_TRAJECTORY_HEAD_SHA256
BEHAVIOR_POLICY_ID = "prospective-pilot-behavior"
BEHAVIOR_POLICY_VERSION = "v3"
BEHAVIOR_SELECTION_REASON_CODE = "preferred_plus_uniform"

ACTION_DRAW_SEED_SHA256 = (
    "f79578fb9860ef0eb4bf02a62691e98c4002a5de96b8dda9ab2d3616f082b574"
)
CANDIDATE_ORDER_SEED_SHA256 = (
    "4521fcca1866d783919b9e3899e0c6e679f2a4c790e63420c2747abb6716f4eb"
)
TASK_ORDER_SEED_SHA256 = (
    "601dfd7774d58876b42240e4f98e897c19a55356eccca67a39f81a4c7299ca32"
)
ACTION_DRAW_DOMAIN = "bench-cleanser/prospective-pilot-v2/action-draw"
CANDIDATE_ORDER_DOMAIN = "bench-cleanser/prospective-pilot-v2/candidate-order"
TASK_ORDER_DOMAIN = "bench-cleanser/prospective-pilot-v2/task-order"

CANDIDATES_PER_TASK = 3
FUTURE_TASK_COUNT = 22
MAXIMUM_TASK_BATCH_SIZE = 4
MAXIMUM_CANDIDATE_DECISIONS = 5
MAXIMUM_NONTERMINAL_ACQUISITIONS = 4
EXPLORATION_MASS = 0.5
MINIMUM_ACTION_PROPENSITY = 0.5 / 7.0
ACTION_COUNTER_SLOTS_PER_TASK = (
    CANDIDATES_PER_TASK * MAXIMUM_CANDIDATE_DECISIONS
)

FRAME_MANIFEST_SCHEMA_VERSION = "prospective-pilot-frame-manifest-0.1.0"
FRAME_MANIFEST_RELATIVE_PATH = pathlib.Path(
    "experiments/prospective_pilot/frame_manifest.json"
)
COLLECTION_POLICY_RELATIVE_PATH = pathlib.Path(
    "experiments/prospective_pilot/collection_policy.json"
)
SCHEDULER_CONTRACT_RELATIVE_PATH = pathlib.Path(
    "experiments/prospective_pilot/scheduler_contract.json"
)
PROTOCOL_RELATIVE_PATH = pathlib.Path(
    "experiments/prospective_pilot/preregistration.json"
)
ROUTER_RELATIVE_PATH = pathlib.Path("bench_cleanser/verification/router.py")
ROUTER_SOURCE_SHA256 = (
    "47a64e8fb0e387c2199fb939e4eef6615f8b15f8b6578d79a97650327bfe40d4"
)
ROUTER_POLICY_VERSION = "conservative-v1"
ROUTER_POLICY_CONFIG = {
    "allow_semantic_accept_in_evaluation": False,
    "full_relative_cost": 0.70,
    "hardening_relative_cost": 1.00,
    "high_candidate_risk": 0.55,
    "high_verifier_risk": 0.40,
    "maximum_false_accept_risk": 0.02,
    "maximum_full_execution_attempts": 3,
    "maximum_hardening_attempts": 2,
    "minimum_authoritative_verifier_validity": 0.95,
    "minimum_full_execution_replicates": 2,
    "semantic_relative_cost": 0.05,
    "static_relative_cost": 0.01,
    "targeted_relative_cost": 0.20,
    "trusted_authoritative_bindings": [],
    "trusted_calibration_bindings": [],
    "version": ROUTER_POLICY_VERSION,
}
ROUTER_POLICY_CONFIG_SHA256 = hashlib.sha256(
    strict_json_dumps(ROUTER_POLICY_CONFIG).encode("utf-8")
).hexdigest()

COLLECTION_ACTION_ROUTE: Mapping[str, RouteAction] = {
    "abstain": RouteAction.ABSTAIN,
    "accept": RouteAction.ACCEPT,
    "full_primary": RouteAction.RUN_FULL,
    "full_repeat": RouteAction.RUN_FULL,
    "hardening_curator": RouteAction.HARDEN_ORACLE,
    "reject": RouteAction.REJECT,
    "semantic_primary": RouteAction.RUN_SEMANTIC,
    "static_bootstrap": RouteAction.RUN_STATIC,
    "targeted_primary": RouteAction.RUN_TARGETED,
}
COLLECTION_ACTION_IDS = tuple(COLLECTION_ACTION_ROUTE)
POLICY_ACTION_IDS = tuple(
    action_id
    for action_id in COLLECTION_ACTION_IDS
    if action_id not in {"hardening_curator", "static_bootstrap"}
)
_TERMINAL_ROUTE_ACTIONS = {
    RouteAction.ACCEPT,
    RouteAction.REJECT,
    RouteAction.ABSTAIN,
}
NONTERMINAL_ACTION_IDS = tuple(
    action_id
    for action_id in POLICY_ACTION_IDS
    if COLLECTION_ACTION_ROUTE[action_id] not in _TERMINAL_ROUTE_ACTIONS
)

_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_PROBABILITY_TOLERANCE = 1e-12
_PRIVILEGED_FRAGMENTS = {
    "adjudicat",
    "answerkey",
    "correct",
    "curator",
    "gold",
    "groundtruth",
    "hidden",
    "hosted",
    "human",
    "incorrect",
    "label",
    "outcome",
    "fail",
    "pass",
    "reference",
    "resolved",
    "reward",
    "safe",
    "submission",
    "truth",
    "unsafe",
}
_ALLOWED_AVAILABILITY_REASONS = {
    "acquisition_ceiling",
    "action_already_completed",
    "always_available",
    "proposal_terminal_available",
    "proposal_terminal_unavailable",
    "candidate_terminal",
    "curator_only_not_policy_available",
    "deterministic_bootstrap_completed",
    "execution_binding_available",
    "execution_binding_unavailable",
    "primary_full_required",
    "semantic_binding_available",
    "semantic_binding_unavailable",
    "terminal_governed",
}

_EnumT = TypeVar("_EnumT", bound=Enum)


class CandidateActivity(str, Enum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


class TaskSelectionDisposition(str, Enum):
    SELECT_CANDIDATE = "select_candidate"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class FrozenStudyFrame:
    """Exact outcome-unexposed task/candidate frame bound to the source freeze."""

    manifest_sha256: str
    tasks: tuple[tuple[str, tuple[str, ...]], ...]
    source_feature_freeze_sha256: str

    def __post_init__(self) -> None:
        _digest(self.manifest_sha256, "frame.manifest_sha256")
        if not isinstance(self.tasks, (list, tuple)):
            raise ValueError("frame tasks must be a sequence")
        tasks = tuple(self.tasks)
        if len(tasks) != FUTURE_TASK_COUNT:
            raise ValueError("frame must contain exactly 22 future task clusters")
        task_ids: list[str] = []
        all_candidates: list[str] = []
        normalized: list[tuple[str, tuple[str, ...]]] = []
        for task_index, item in enumerate(tasks):
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError(f"frame.tasks[{task_index}] must be a task/candidate pair")
            task_id = _safe_identifier(item[0], f"frame.tasks[{task_index}].task_id")
            candidates = tuple(
                _candidate_id(candidate, f"frame.tasks[{task_index}].candidate_ids[{index}]")
                for index, candidate in enumerate(item[1])
            )
            if len(candidates) != CANDIDATES_PER_TASK:
                raise ValueError("every frozen task must have exactly three candidates")
            if tuple(sorted(candidates)) != candidates or len(set(candidates)) != len(candidates):
                raise ValueError("frozen candidate IDs must be sorted and unique per task")
            task_ids.append(task_id)
            all_candidates.extend(candidates)
            normalized.append((task_id, candidates))
        if task_ids != sorted(task_ids) or len(task_ids) != len(set(task_ids)):
            raise ValueError("frozen task IDs must be sorted and unique")
        if len(all_candidates) != 66 or len(set(all_candidates)) != 66:
            raise ValueError("frame must contain 66 study-wide unique candidates")
        _digest(
            self.source_feature_freeze_sha256,
            "frame.source_feature_freeze_sha256",
        )
        object.__setattr__(self, "tasks", tuple(normalized))

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task_id for task_id, _ in self.tasks)

    def candidate_ids_for(self, task_id: str) -> tuple[str, ...]:
        task = _safe_identifier(task_id, "frame task_id")
        try:
            return dict(self.tasks)[task]
        except KeyError as exc:
            raise ValueError("task is absent from the exact frozen frame") from exc

    @classmethod
    def from_dict(cls, value: Any, *, manifest_sha256: str) -> FrozenStudyFrame:
        data = _object(value, "frame_manifest")
        _exact_fields(
            data,
            {
                "schema_version",
                "study_id",
                "status",
                "source_feature_freeze",
                "excluded_task_clusters",
                "task_count",
                "candidates_per_task",
                "candidate_count",
                "task_ids_sha256",
                "candidate_ids_sha256",
                "tasks_sha256",
                "tasks",
            },
            "frame_manifest",
        )
        if data["schema_version"] != FRAME_MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported frame-manifest schema")
        if data["study_id"] != SCHEDULER_STUDY_ID:
            raise ValueError("frame-manifest study identity differs")
        if data["status"] != "frozen_uncommitted":
            raise ValueError("frame manifest must be frozen_uncommitted before commit")
        if data["excluded_task_clusters"] != [
            "sympy__sympy-15976",
            "sphinx-doc__sphinx-8475",
        ]:
            raise ValueError("frame exclusions differ from the append-only prehistory")
        if (
            data["task_count"] != FUTURE_TASK_COUNT
            or data["candidates_per_task"] != CANDIDATES_PER_TASK
            or data["candidate_count"] != FUTURE_TASK_COUNT * CANDIDATES_PER_TASK
        ):
            raise ValueError("frame counts differ from the exact 22/66 contract")
        source = _object(data["source_feature_freeze"], "frame source_feature_freeze")
        _exact_fields(
            source,
            {
                "logical_name",
                "bytes",
                "sha256",
                "selected_instance_ids_sha256",
                "selected_task_identities_sha256",
            },
            "frame source_feature_freeze",
        )
        if (
            source["logical_name"] != "matched-rollout-v2-repaired-feature-freeze"
            or source["bytes"] != 301852
            or source["sha256"]
            != "b01e8c9408acce759b75bd299f4323a37398e417e80a97ef52f09b8a14abc01c"
            or source["selected_instance_ids_sha256"]
            != "601dfd7774d58876b42240e4f98e897c19a55356eccca67a39f81a4c7299ca32"
            or source["selected_task_identities_sha256"]
            != "4521fcca1866d783919b9e3899e0c6e679f2a4c790e63420c2747abb6716f4eb"
        ):
            raise ValueError("frame source feature-freeze identity differs")
        raw_tasks = _array(data["tasks"], "frame_manifest.tasks")
        tasks: list[tuple[str, tuple[str, ...]]] = []
        tasks_payload: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_tasks):
            item = _object(raw, f"frame_manifest.tasks[{index}]")
            _exact_fields(item, {"task_id", "candidate_ids"}, f"frame task {index}")
            task_id = _safe_identifier(item["task_id"], f"frame task {index} task_id")
            raw_candidates = _array(
                item["candidate_ids"],
                f"frame task {index} candidate_ids",
            )
            candidates = tuple(
                _candidate_id(candidate, f"frame task {index} candidate_ids[{candidate_index}]")
                for candidate_index, candidate in enumerate(raw_candidates)
            )
            tasks.append((task_id, candidates))
            tasks_payload.append({"task_id": task_id, "candidate_ids": list(candidates)})
        task_ids = [task_id for task_id, _ in tasks]
        candidate_ids = sorted(
            candidate for _, candidates in tasks for candidate in candidates
        )
        expected_hashes = {
            "task_ids_sha256": _canonical_sha256(task_ids),
            "candidate_ids_sha256": _canonical_sha256(candidate_ids),
            "tasks_sha256": _canonical_sha256(tasks_payload),
        }
        for name, expected in expected_hashes.items():
            if _digest(data[name], f"frame_manifest.{name}") != expected:
                raise ValueError(f"frame_manifest.{name} differs")
        return cls(
            manifest_sha256=manifest_sha256,
            tasks=tuple(tasks),
            source_feature_freeze_sha256=source["sha256"],
        )


@dataclass(frozen=True)
class SchedulerBindings:
    """Repository-validated identities required at every scheduler boundary."""

    repository_root: pathlib.Path
    frame: FrozenStudyFrame
    collection_policy_sha256: str
    scheduler_contract_sha256: str
    protocol_sha256: str
    router_source_sha256: str = ROUTER_SOURCE_SHA256
    router_policy_config_sha256: str = ROUTER_POLICY_CONFIG_SHA256

    def __post_init__(self) -> None:
        from experiments.prospective_pilot.validate_protocol import validate_protocol

        repository = pathlib.Path(self.repository_root).resolve()
        if not repository.is_dir():
            raise ValueError("scheduler binding root must be a repository directory")
        object.__setattr__(self, "repository_root", repository)
        if not isinstance(self.frame, FrozenStudyFrame):
            raise ValueError("scheduler bindings require a FrozenStudyFrame")
        for name in (
            "collection_policy_sha256",
            "scheduler_contract_sha256",
            "protocol_sha256",
        ):
            _digest(getattr(self, name), f"scheduler_bindings.{name}")
        if self.router_source_sha256 != ROUTER_SOURCE_SHA256:
            raise ValueError("scheduler router source differs from the frozen binding")
        if self.router_policy_config_sha256 != ROUTER_POLICY_CONFIG_SHA256:
            raise ValueError("scheduler router policy config differs from the frozen binding")
        expected_files = {
            "collection_policy_sha256": COLLECTION_POLICY_RELATIVE_PATH,
            "scheduler_contract_sha256": SCHEDULER_CONTRACT_RELATIVE_PATH,
            "protocol_sha256": PROTOCOL_RELATIVE_PATH,
        }
        for name, relative in expected_files.items():
            try:
                digest = hashlib.sha256((repository / relative).read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError(f"cannot read scheduler binding source {relative}") from exc
            if digest != getattr(self, name):
                raise ValueError(f"scheduler binding {name} is not the repository file")
        frame_digest = hashlib.sha256(
            (repository / FRAME_MANIFEST_RELATIVE_PATH).read_bytes()
        ).hexdigest()
        if frame_digest != self.frame.manifest_sha256:
            raise ValueError("scheduler frame is not the repository-bound manifest")
        router_digest = hashlib.sha256(
            (repository / ROUTER_RELATIVE_PATH).read_bytes()
        ).hexdigest()
        if router_digest != self.router_source_sha256:
            raise ValueError("scheduler router source is not the repository-bound file")
        validation = validate_protocol(repository)
        if (
            validation.protocol_sha256 != self.protocol_sha256
            or validation.configuration_sha256.get("collection_policy")
            != self.collection_policy_sha256
            or validation.configuration_sha256.get("scheduler_contract")
            != self.scheduler_contract_sha256
            or validation.configuration_sha256.get("frame_manifest")
            != self.frame.manifest_sha256
        ):
            raise ValueError("scheduler bindings differ from strict protocol validation")


def load_study_bindings(root: pathlib.Path) -> SchedulerBindings:
    """Load only repository-validated scheduler identities; caller hashes are forbidden."""

    from experiments.prospective_pilot.validate_protocol import validate_protocol

    repository = pathlib.Path(root).resolve()
    result = validate_protocol(repository)
    frame_path = repository / FRAME_MANIFEST_RELATIVE_PATH
    payload = frame_path.read_bytes()
    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid frozen frame manifest: {exc}") from exc
    frame = FrozenStudyFrame.from_dict(
        decoded,
        manifest_sha256=hashlib.sha256(payload).hexdigest(),
    )
    configuration = result.configuration_sha256
    try:
        collection_sha256 = configuration["collection_policy"]
        scheduler_sha256 = configuration["scheduler_contract"]
        validated_frame_sha256 = configuration["frame_manifest"]
    except KeyError as exc:
        raise ValueError("protocol validation omitted a scheduler activation binding") from exc
    if validated_frame_sha256 != frame.manifest_sha256:
        raise ValueError("validated frame digest differs from the loaded frame")
    return SchedulerBindings(
        repository_root=repository,
        frame=frame,
        collection_policy_sha256=collection_sha256,
        scheduler_contract_sha256=scheduler_sha256,
        protocol_sha256=result.protocol_sha256,
    )


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _array(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    field_name: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{field_name} fields differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: Any, field_name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty canonical string")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} cannot contain control characters")
    if identifier and _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a canonical identifier")
    return value


def _safe_identifier(value: Any, field_name: str) -> str:
    result = _string(value, field_name, identifier=True)
    fingerprint = re.sub(r"[^a-z0-9]+", "", result.casefold())
    if any(fragment in fingerprint for fragment in _PRIVILEGED_FRAGMENTS):
        raise ValueError(f"{field_name} may encode a privileged or hosted label")
    return result


def _code(value: Any, field_name: str) -> str:
    result = _string(value, field_name)
    if _CODE_RE.fullmatch(result) is None:
        raise ValueError(f"{field_name} must be a canonical reason code")
    fingerprint = re.sub(r"[^a-z0-9]+", "", result.casefold())
    if any(fragment in fingerprint for fragment in _PRIVILEGED_FRAGMENTS):
        raise ValueError(f"{field_name} may encode a privileged or hosted label")
    return result


def _digest(value: Any, field_name: str) -> str:
    result = _string(value, field_name)
    if _DIGEST_RE.fullmatch(result) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256")
    return result


def _candidate_id(value: Any, field_name: str) -> str:
    result = _string(value, field_name)
    if _CANDIDATE_RE.fullmatch(result) is None:
        raise ValueError(f"{field_name} must be an opaque lowercase sha256:<digest>")
    return result


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


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a JSON boolean")
    return value


def _enum(enum_type: type[_EnumT], value: Any, field_name: str) -> _EnumT:
    raw = _string(value, field_name)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} has unknown value {raw!r}") from exc


def _timestamp(value: Any, field_name: str) -> str:
    raw = _string(value, field_name)
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must use canonical UTC format "
            "YYYY-MM-DDTHH:MM:SS.ffffffZ"
        ) from exc
    canonical = parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if canonical != raw:
        raise ValueError(f"{field_name} is not a canonical UTC timestamp")
    return canonical


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(strict_json_dumps(value).encode("utf-8")).hexdigest()


def _probability(value: Any, field_name: str, *, positive: bool = True) -> float:
    result = _number(value, field_name)
    lower_ok = result > 0.0 if positive else result >= 0.0
    if not lower_ok or result > 1.0:
        bracket = "(0, 1]" if positive else "[0, 1]"
        raise ValueError(f"{field_name} must be in {bracket}")
    return result


def _counter_draw(seed_sha256: str, domain: str, counter: int) -> float:
    if isinstance(counter, bool) or not isinstance(counter, int) or not 0 <= counter < 2**64:
        raise ValueError("RNG counter must be an unsigned 64-bit integer")
    seed = bytes.fromhex(_digest(seed_sha256, "RNG seed"))
    domain_bytes = _string(domain, "RNG domain").encode("utf-8")
    digest = hashlib.sha256(
        seed + b"\x00" + domain_bytes + b"\x00" + counter.to_bytes(8, "big")
    ).digest()
    integer = int.from_bytes(digest[:8], "big") >> 11
    return integer / float(1 << 53)


def derive_action_draw(counter: int) -> float:
    """Apply the frozen action-draw generator byte for byte."""

    return _counter_draw(ACTION_DRAW_SEED_SHA256, ACTION_DRAW_DOMAIN, counter)


def _fixed_hash_order(
    values: Sequence[str],
    *,
    seed_sha256: str,
    domain: str,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence")
    normalized = tuple(_string(value, f"{field_name}[{index}]") for index, value in enumerate(values))
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} cannot contain duplicates")
    seed = bytes.fromhex(_digest(seed_sha256, f"{field_name} seed"))
    domain_bytes = _string(domain, f"{field_name} domain").encode("utf-8")
    return tuple(sorted(
        normalized,
        key=lambda value: (
            hashlib.sha256(
                seed + b"\x00" + domain_bytes + b"\x00" + value.encode("utf-8")
            ).hexdigest(),
            value,
        ),
    ))


def derive_candidate_order(candidate_ids: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(
        _candidate_id(value, f"candidate_ids[{index}]")
        for index, value in enumerate(candidate_ids)
    )
    if len(normalized) != CANDIDATES_PER_TASK:
        raise ValueError("candidate order requires exactly three candidates")
    return _fixed_hash_order(
        normalized,
        seed_sha256=CANDIDATE_ORDER_SEED_SHA256,
        domain=CANDIDATE_ORDER_DOMAIN,
        field_name="candidate_ids",
    )


def derive_task_order(task_ids: Sequence[str]) -> tuple[str, ...]:
    if len(task_ids) != FUTURE_TASK_COUNT:
        raise ValueError("task order requires the exact 22-task future frame")
    normalized = tuple(
        _safe_identifier(value, f"task_ids[{index}]")
        for index, value in enumerate(task_ids)
    )
    return _fixed_hash_order(
        normalized,
        seed_sha256=TASK_ORDER_SEED_SHA256,
        domain=TASK_ORDER_DOMAIN,
        field_name="task_ids",
    )


def derive_task_batches(task_ids: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    order = derive_task_order(task_ids)
    return tuple(
        tuple(order[start : start + MAXIMUM_TASK_BATCH_SIZE])
        for start in range(0, len(order), MAXIMUM_TASK_BATCH_SIZE)
    )


def _routing_policy_payload(policy: RoutingPolicy) -> dict[str, Any]:
    return {
        "allow_semantic_accept_in_evaluation": (
            policy.allow_semantic_accept_in_evaluation
        ),
        "full_relative_cost": policy.full_relative_cost,
        "hardening_relative_cost": policy.hardening_relative_cost,
        "high_candidate_risk": policy.high_candidate_risk,
        "high_verifier_risk": policy.high_verifier_risk,
        "maximum_false_accept_risk": policy.maximum_false_accept_risk,
        "maximum_full_execution_attempts": policy.maximum_full_execution_attempts,
        "maximum_hardening_attempts": policy.maximum_hardening_attempts,
        "minimum_authoritative_verifier_validity": (
            policy.minimum_authoritative_verifier_validity
        ),
        "minimum_full_execution_replicates": (
            policy.minimum_full_execution_replicates
        ),
        "semantic_relative_cost": policy.semantic_relative_cost,
        "static_relative_cost": policy.static_relative_cost,
        "targeted_relative_cost": policy.targeted_relative_cost,
        "trusted_authoritative_bindings": [
            [kind.value, source, version]
            for kind, source, version in sorted(
                policy.trusted_authoritative_bindings,
                key=lambda item: (item[0].value, item[1], item[2]),
            )
        ],
        "trusted_calibration_bindings": [
            list(item) for item in sorted(policy.trusted_calibration_bindings)
        ],
        "version": policy.version,
    }


def _manifest_from_router_state(state: RouterStateView) -> ValidityManifest:
    if not isinstance(state, RouterStateView):
        raise ValueError("router state must be a safe RouterStateView preimage")
    return ValidityManifest(
        instance_id=state.instance_id,
        candidate_id=state.candidate_id,
        lifecycle_stage=state.lifecycle_stage,
        risk_profile=state.risk_profile,
        provenance=dict(state.provenance),
        evidence=[
            *(item.observation for item in state.bootstrap_history),
            *state.evidence_history,
        ],
        route_history=[
            RouteDecision(
                    action=item.route.action,
                    policy_version=item.route.policy_version,
                    candidate_risk=item.route.candidate_risk,
                    verifier_risk=item.route.verifier_risk,
                    expected_information_gain=(
                        item.route.expected_information_gain
                    ),
                    estimated_relative_cost=item.route.estimated_relative_cost,
                    reasons=("frozen_deterministic_bootstrap",),
                    terminal=False,
                    scores_calibrated=item.route.scores_calibrated,
                    calibration_id=item.route.calibration_id,
                )
            for item in state.bootstrap_history
        ] + [
            RouteDecision(
                action=item.action,
                policy_version=item.policy_version,
                candidate_risk=item.candidate_risk,
                verifier_risk=item.verifier_risk,
                expected_information_gain=item.expected_information_gain,
                estimated_relative_cost=item.estimated_relative_cost,
                reasons=("frozen_prior_route",),
                terminal=False,
                scores_calibrated=item.scores_calibrated,
                calibration_id=item.calibration_id,
            )
            for item in state.route_history
        ],
    )


def _frozen_router_decision(state: RouterStateView) -> RouteDecision:
    policy = RoutingPolicy()
    payload = _routing_policy_payload(policy)
    if payload != ROUTER_POLICY_CONFIG or _canonical_sha256(payload) != (
        ROUTER_POLICY_CONFIG_SHA256
    ):
        raise ValueError("runtime RoutingPolicy defaults differ from the frozen config")
    return ConservativeRouter(policy).route(_manifest_from_router_state(state))


@dataclass(frozen=True)
class BoundRouterDecision:
    """Reason-free, digest-bound projection of the preferred router decision."""

    action: RouteAction
    router_state: RouterStateView
    router_state_sha256: str
    router_source_sha256: str
    router_policy_config_sha256: str
    terminal: bool
    policy_version: str
    candidate_risk: float
    verifier_risk: float
    expected_information_gain: float
    estimated_relative_cost: float
    scores_calibrated: bool
    calibration_id: str
    decision_sha256: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.action, RouteAction):
            raise ValueError("bound router action must be a RouteAction")
        if not isinstance(self.router_state, RouterStateView):
            raise ValueError("bound router decision requires a safe state preimage")
        _safe_identifier(
            self.router_state.risk_profile.language,
            "bound_router.router_state.risk_profile.language",
        )
        for key, value in self.router_state.provenance:
            _safe_identifier(key, "bound_router.router_state.provenance key")
            _safe_identifier(
                value,
                f"bound_router.router_state.provenance[{key!r}]",
            )
        for index, observation in enumerate(self.router_state.evidence_history):
            _safe_identifier(
                observation.source,
                f"bound_router.router_state.evidence_history[{index}].source",
            )
            if observation.source_version:
                _safe_identifier(
                    observation.source_version,
                    f"bound_router.router_state.evidence_history[{index}].source_version",
                )
            _safe_identifier(
                observation.acquisition_id,
                f"bound_router.router_state.evidence_history[{index}].acquisition_id",
            )
            if observation.calibration_id:
                _safe_identifier(
                    observation.calibration_id,
                    f"bound_router.router_state.evidence_history[{index}].calibration_id",
                )
        computed_state = self.router_state.canonical_digest()
        object.__setattr__(
            self,
            "router_state_sha256",
            _digest(
                self.router_state_sha256,
                "bound_router.router_state_sha256",
            ),
        )
        if self.router_state_sha256 != computed_state:
            raise ValueError("bound router state digest contradicts its safe preimage")
        if self.router_source_sha256 != ROUTER_SOURCE_SHA256:
            raise ValueError("bound router source differs from the frozen implementation")
        if self.router_policy_config_sha256 != ROUTER_POLICY_CONFIG_SHA256:
            raise ValueError("bound router policy config differs from the frozen policy")
        if not isinstance(self.terminal, bool):
            raise ValueError("bound router terminal must be a boolean")
        if self.terminal != (self.action in _TERMINAL_ROUTE_ACTIONS):
            raise ValueError("bound router terminal flag contradicts its action")
        _safe_identifier(self.policy_version, "bound_router.policy_version")
        for name in (
            "candidate_risk",
            "verifier_risk",
            "expected_information_gain",
        ):
            probability = _probability(
                getattr(self, name),
                f"bound_router.{name}",
                positive=False,
            )
            object.__setattr__(self, name, probability)
        cost = _number(self.estimated_relative_cost, "bound_router.estimated_relative_cost")
        if cost < 0.0:
            raise ValueError("bound router estimated cost cannot be negative")
        object.__setattr__(self, "estimated_relative_cost", cost)
        if not isinstance(self.scores_calibrated, bool):
            raise ValueError("bound router scores_calibrated must be a boolean")
        if self.calibration_id:
            _safe_identifier(self.calibration_id, "bound_router.calibration_id")
        if self.scores_calibrated != bool(self.calibration_id):
            raise ValueError("bound router calibration fields contradict each other")
        expected = _frozen_router_decision(self.router_state)
        projection = (
            self.action,
            self.terminal,
            self.policy_version,
            self.candidate_risk,
            self.verifier_risk,
            self.expected_information_gain,
            self.estimated_relative_cost,
            self.scores_calibrated,
            self.calibration_id,
        )
        expected_projection = (
            expected.action,
            expected.terminal,
            expected.policy_version,
            expected.candidate_risk,
            expected.verifier_risk,
            expected.expected_information_gain,
            expected.estimated_relative_cost,
            expected.scores_calibrated,
            expected.calibration_id,
        )
        if projection != expected_projection:
            raise ValueError("bound router projection differs from frozen-router recomputation")
        computed = _canonical_sha256(self._payload())
        if self.decision_sha256 and _digest(
            self.decision_sha256,
            "bound_router.decision_sha256",
        ) != computed:
            raise ValueError("bound router decision digest differs")
        object.__setattr__(self, "decision_sha256", computed)

    @classmethod
    def from_route_decision(
        cls,
        decision: RouteDecision,
        *,
        router_state: RouterStateView,
    ) -> BoundRouterDecision:
        if not isinstance(decision, RouteDecision):
            raise ValueError("decision must be a RouteDecision")
        return cls(
            action=decision.action,
            router_state=router_state,
            router_state_sha256=router_state.canonical_digest(),
            router_source_sha256=ROUTER_SOURCE_SHA256,
            router_policy_config_sha256=ROUTER_POLICY_CONFIG_SHA256,
            terminal=decision.terminal,
            policy_version=decision.policy_version,
            candidate_risk=decision.candidate_risk,
            verifier_risk=decision.verifier_risk,
            expected_information_gain=decision.expected_information_gain,
            estimated_relative_cost=decision.estimated_relative_cost,
            scores_calibrated=decision.scores_calibrated,
            calibration_id=decision.calibration_id,
        )

    @classmethod
    def from_router_state(cls, router_state: RouterStateView) -> BoundRouterDecision:
        if not isinstance(router_state, RouterStateView):
            raise ValueError("router_state must be a RouterStateView")
        return cls.from_route_decision(
            _frozen_router_decision(router_state),
            router_state=router_state,
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "router_state": self.router_state.to_dict(),
            "router_state_sha256": self.router_state_sha256,
            "router_source_sha256": self.router_source_sha256,
            "router_policy_config_sha256": self.router_policy_config_sha256,
            "terminal": self.terminal,
            "policy_version": self.policy_version,
            "candidate_risk": self.candidate_risk,
            "verifier_risk": self.verifier_risk,
            "expected_information_gain": self.expected_information_gain,
            "estimated_relative_cost": self.estimated_relative_cost,
            "scores_calibrated": self.scores_calibrated,
            "calibration_id": self.calibration_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "decision_sha256": self.decision_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> BoundRouterDecision:
        data = _object(value, "bound_router_decision")
        fields = {
            "action",
            "router_state",
            "router_state_sha256",
            "router_source_sha256",
            "router_policy_config_sha256",
            "terminal",
            "policy_version",
            "candidate_risk",
            "verifier_risk",
            "expected_information_gain",
            "estimated_relative_cost",
            "scores_calibrated",
            "calibration_id",
            "decision_sha256",
        }
        _exact_fields(data, fields, "bound_router_decision")
        calibration = data["calibration_id"]
        if not isinstance(calibration, str):
            raise ValueError("bound_router_decision.calibration_id must be a string")
        return cls(
            action=_enum(RouteAction, data["action"], "bound_router_decision.action"),
            router_state=RouterStateView.from_dict(data["router_state"]),
            router_state_sha256=_digest(
                data["router_state_sha256"],
                "bound_router_decision.router_state_sha256",
            ),
            router_source_sha256=_digest(
                data["router_source_sha256"],
                "bound_router_decision.router_source_sha256",
            ),
            router_policy_config_sha256=_digest(
                data["router_policy_config_sha256"],
                "bound_router_decision.router_policy_config_sha256",
            ),
            terminal=_boolean(data["terminal"], "bound_router_decision.terminal"),
            policy_version=_string(
                data["policy_version"],
                "bound_router_decision.policy_version",
            ),
            candidate_risk=_number(
                data["candidate_risk"],
                "bound_router_decision.candidate_risk",
            ),
            verifier_risk=_number(
                data["verifier_risk"],
                "bound_router_decision.verifier_risk",
            ),
            expected_information_gain=_number(
                data["expected_information_gain"],
                "bound_router_decision.expected_information_gain",
            ),
            estimated_relative_cost=_number(
                data["estimated_relative_cost"],
                "bound_router_decision.estimated_relative_cost",
            ),
            scores_calibrated=_boolean(
                data["scores_calibrated"],
                "bound_router_decision.scores_calibrated",
            ),
            calibration_id=calibration,
            decision_sha256=_digest(
                data["decision_sha256"],
                "bound_router_decision.decision_sha256",
            ),
        )


@dataclass(frozen=True)
class TerminalAdmissibility:
    accept_eligible: bool
    reject_eligible: bool
    abstain_eligible: bool
    reason_code: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, bool)
            for value in (
                self.accept_eligible,
                self.reject_eligible,
                self.abstain_eligible,
            )
        ):
            raise ValueError("terminal admissibility fields must be booleans")
        if self.accept_eligible and self.reject_eligible:
            raise ValueError("accept and reject cannot both be eligible")
        _code(self.reason_code, "terminal_admissibility.reason_code")

    @classmethod
    def from_proposal(
        cls,
        proposal: TerminalProposal,
    ) -> TerminalAdmissibility:
        if not isinstance(proposal, TerminalProposal):
            raise ValueError("terminal admissibility requires a TerminalProposal")
        if proposal.action_id == ACCEPT_ACTION_ID:
            return cls(True, False, True, proposal.reason_code)
        if proposal.action_id == REJECT_ACTION_ID:
            return cls(False, True, True, proposal.reason_code)
        return cls(False, False, True, proposal.reason_code)

    @classmethod
    def closed(cls) -> TerminalAdmissibility:
        return cls(False, False, False, "candidate_terminal")

    def to_dict(self) -> dict[str, Any]:
        return {
            "accept_eligible": self.accept_eligible,
            "reject_eligible": self.reject_eligible,
            "abstain_eligible": self.abstain_eligible,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TerminalAdmissibility:
        data = _object(value, "terminal_admissibility")
        fields = {
            "accept_eligible",
            "reject_eligible",
            "abstain_eligible",
            "reason_code",
        }
        _exact_fields(data, fields, "terminal_admissibility")
        return cls(
            accept_eligible=_boolean(
                data["accept_eligible"],
                "terminal_admissibility.accept_eligible",
            ),
            reject_eligible=_boolean(
                data["reject_eligible"],
                "terminal_admissibility.reject_eligible",
            ),
            abstain_eligible=_boolean(
                data["abstain_eligible"],
                "terminal_admissibility.abstain_eligible",
            ),
            reason_code=_string(
                data["reason_code"],
                "terminal_admissibility.reason_code",
            ),
        )


def _validate_catalog(action_catalog: Sequence[ActionOffer]) -> tuple[ActionOffer, ...]:
    if not isinstance(action_catalog, (list, tuple)) or any(
        not isinstance(item, ActionOffer) for item in action_catalog
    ):
        raise ValueError("action_catalog must contain ActionOffer values")
    catalog = tuple(action_catalog)
    action_ids = [item.action_id for item in catalog]
    if action_ids != sorted(action_ids):
        raise ValueError("action_catalog must be ordered by action_id")
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("action_catalog cannot contain duplicate action_id values")
    if tuple(action_ids) != COLLECTION_ACTION_IDS:
        raise ValueError("action_catalog must contain the complete nine-action catalog")
    for offer in catalog:
        if offer.route_action != COLLECTION_ACTION_ROUTE[offer.action_id]:
            raise ValueError(f"action {offer.action_id!r} has the wrong route binding")
        reason_field = (
            f"action_catalog[{offer.action_id!r}].availability_reason"
        )
        reason = (
            "curator_only_not_policy_available"
            if offer.availability_reason == "curator_only_not_policy_available"
            else _code(offer.availability_reason, reason_field)
        )
        if reason not in _ALLOWED_AVAILABILITY_REASONS:
            raise ValueError(
                f"action {offer.action_id!r} uses an unregistered availability reason"
            )
        available_reasons = {
            "always_available",
            "execution_binding_available",
            "proposal_terminal_available",
            "semantic_binding_available",
        }
        if offer.available != (reason in available_reasons):
            raise ValueError(
                f"action {offer.action_id!r} availability contradicts its reason code"
            )
        _safe_identifier(
            offer.adapter_id,
            f"action_catalog[{offer.action_id!r}].adapter_id",
        )
        _safe_identifier(
            offer.adapter_version,
            f"action_catalog[{offer.action_id!r}].adapter_version",
        )
    by_id = {item.action_id: item for item in catalog}
    if (
        by_id["full_primary"].action_spec_sha256
        == by_id["full_repeat"].action_spec_sha256
    ):
        raise ValueError("full_repeat requires a distinct fresh-worktree action spec")
    return catalog


def _canonical_catalog(
    catalog: Sequence[ActionOffer],
    *,
    activity: CandidateActivity,
    decisions: int,
    acquisitions: int,
    completed_nonterminal_action_ids: Sequence[str],
    admissibility: TerminalAdmissibility,
) -> tuple[ActionOffer, ...]:
    source = _validate_catalog(catalog)
    if activity != CandidateActivity.ACTIVE:
        return tuple(
            replace(item, available=False, availability_reason="candidate_terminal")
            for item in source
        )
    result: list[ActionOffer] = []
    for offer in source:
        if offer.action_id == "accept":
            result.append(replace(
                offer,
                available=admissibility.accept_eligible,
                availability_reason=(
                    "proposal_terminal_available"
                    if admissibility.accept_eligible
                    else "proposal_terminal_unavailable"
                ),
            ))
        elif offer.action_id == "reject":
            result.append(replace(
                offer,
                available=admissibility.reject_eligible,
                availability_reason=(
                    "proposal_terminal_available"
                    if admissibility.reject_eligible
                    else "proposal_terminal_unavailable"
                ),
            ))
        elif offer.action_id == "abstain":
            result.append(replace(
                offer,
                available=True,
                availability_reason="always_available",
            ))
        elif offer.action_id == "static_bootstrap":
            result.append(replace(
                offer,
                available=False,
                availability_reason="deterministic_bootstrap_completed",
            ))
        elif offer.action_id == "hardening_curator":
            result.append(replace(
                offer,
                available=False,
                availability_reason="curator_only_not_policy_available",
            ))
        elif offer.action_id in completed_nonterminal_action_ids:
            result.append(replace(
                offer,
                available=False,
                availability_reason="action_already_completed",
            ))
        elif (
            offer.action_id == "full_repeat"
            and "full_primary" not in completed_nonterminal_action_ids
        ):
            result.append(replace(
                offer,
                available=False,
                availability_reason="primary_full_required",
            ))
        elif (
            decisions >= MAXIMUM_CANDIDATE_DECISIONS - 1
            or acquisitions >= MAXIMUM_NONTERMINAL_ACQUISITIONS
        ):
            result.append(replace(
                offer,
                available=False,
                availability_reason="acquisition_ceiling",
            ))
        else:
            result.append(offer)
    normalized = tuple(result)
    available = [item for item in normalized if item.available]
    if len(available) > len(POLICY_ACTION_IDS):
        raise ValueError("available behavior catalog exceeds the seven-action ceiling")
    return normalized


@dataclass(frozen=True)
class CandidateRoundInput:
    candidate_id: str
    activity: CandidateActivity
    decision_count: int
    nonterminal_acquisition_count: int
    completed_nonterminal_action_ids: tuple[str, ...]
    router_state_sha256: str
    history_sha256: str
    policy_trajectory_head_sha256: str
    bound_router_decision: BoundRouterDecision | None
    action_catalog: tuple[ActionOffer, ...]

    def __post_init__(self) -> None:
        _validate_candidate_common(
            candidate_id=self.candidate_id,
            activity=self.activity,
            decision_count=self.decision_count,
            acquisition_count=self.nonterminal_acquisition_count,
            completed_nonterminal_action_ids=self.completed_nonterminal_action_ids,
            router_state_sha256=self.router_state_sha256,
            history_sha256=self.history_sha256,
            policy_head_sha256=self.policy_trajectory_head_sha256,
            bound_router_decision=self.bound_router_decision,
            action_catalog=self.action_catalog,
        )


def _validate_candidate_common(
    *,
    candidate_id: str,
    activity: CandidateActivity,
    decision_count: int,
    acquisition_count: int,
    completed_nonterminal_action_ids: Sequence[str],
    router_state_sha256: str,
    history_sha256: str,
    policy_head_sha256: str,
    bound_router_decision: BoundRouterDecision | None,
    action_catalog: Sequence[ActionOffer],
) -> None:
    _candidate_id(candidate_id, "candidate.candidate_id")
    if not isinstance(activity, CandidateActivity):
        raise ValueError("candidate.activity must be a CandidateActivity")
    decisions = _integer(decision_count, "candidate.decision_count")
    acquisitions = _integer(acquisition_count, "candidate.nonterminal_acquisition_count")
    if not 0 <= decisions <= MAXIMUM_CANDIDATE_DECISIONS:
        raise ValueError("candidate decision_count exceeds the frozen limit")
    if not 0 <= acquisitions <= MAXIMUM_NONTERMINAL_ACQUISITIONS:
        raise ValueError("candidate acquisition count exceeds the frozen limit")
    if acquisitions > decisions:
        raise ValueError("candidate acquisitions cannot exceed decisions")
    if not isinstance(completed_nonterminal_action_ids, (list, tuple)):
        raise ValueError("candidate completed action IDs must be a sequence")
    completed = tuple(completed_nonterminal_action_ids)
    if list(completed) != sorted(completed) or len(completed) != len(set(completed)):
        raise ValueError("candidate completed action IDs must be sorted and unique")
    if not set(completed).issubset(NONTERMINAL_ACTION_IDS):
        raise ValueError("candidate completed action IDs contain a terminal or unknown action")
    if len(completed) != acquisitions:
        raise ValueError("candidate completed action IDs must exactly match acquisitions")
    _digest(router_state_sha256, "candidate.router_state_sha256")
    _digest(history_sha256, "candidate.history_sha256")
    policy_head = _digest(
        policy_head_sha256,
        "candidate.policy_trajectory_head_sha256",
    )
    if decisions == 0 and policy_head != SCHEDULER_GENESIS_SHA256:
        raise ValueError("zero-decision candidate must use the policy genesis head")
    if decisions > 0 and policy_head == SCHEDULER_GENESIS_SHA256:
        raise ValueError("nonzero candidate cannot use the policy genesis head")
    _validate_catalog(action_catalog)
    if activity == CandidateActivity.ACTIVE:
        if decisions != acquisitions:
            raise ValueError("active candidate decisions must all be acquisitions")
        if decisions >= MAXIMUM_CANDIDATE_DECISIONS:
            raise ValueError("candidate cannot remain active after five decisions")
        if not isinstance(bound_router_decision, BoundRouterDecision):
            raise ValueError("active candidate requires a bound router decision")
        if bound_router_decision.router_state_sha256 != router_state_sha256:
            raise ValueError("bound router decision does not match router_state_sha256")
        if bound_router_decision.router_state.candidate_id != candidate_id:
            raise ValueError("bound router state belongs to a different candidate")
        if bound_router_decision.router_state.history_sha256() != history_sha256:
            raise ValueError("candidate history digest contradicts the safe router state")
        router_state = bound_router_decision.router_state
        if (
            len(router_state.bootstrap_history) != 1
            or router_state.bootstrap_history[0].route.action
            != RouteAction.RUN_STATIC
            or len(router_state.evidence_history) != acquisitions
            or len(router_state.route_history) != acquisitions
        ):
            raise ValueError(
                "active candidate requires one deterministic static bootstrap and "
                "one randomized route/evidence pair per acquisition"
            )
    else:
        if decisions < 1:
            raise ValueError("terminal candidate requires at least one decision")
        if decisions != acquisitions + 1:
            raise ValueError("terminal candidate requires exactly one terminal decision")
        if bound_router_decision is not None:
            raise ValueError("terminal candidate cannot carry a new router decision")


@dataclass(frozen=True)
class CandidateRoundState:
    candidate_id: str
    activity: CandidateActivity
    decision_count: int
    nonterminal_acquisition_count: int
    completed_nonterminal_action_ids: tuple[str, ...]
    router_state_sha256: str
    history_sha256: str
    policy_trajectory_head_sha256: str
    bound_router_decision: BoundRouterDecision | None
    terminal_admissibility: TerminalAdmissibility
    action_catalog: tuple[ActionOffer, ...]
    preferred_action_id: str | None

    def __post_init__(self) -> None:
        _validate_candidate_common(
            candidate_id=self.candidate_id,
            activity=self.activity,
            decision_count=self.decision_count,
            acquisition_count=self.nonterminal_acquisition_count,
            completed_nonterminal_action_ids=self.completed_nonterminal_action_ids,
            router_state_sha256=self.router_state_sha256,
            history_sha256=self.history_sha256,
            policy_head_sha256=self.policy_trajectory_head_sha256,
            bound_router_decision=self.bound_router_decision,
            action_catalog=self.action_catalog,
        )
        if not isinstance(self.terminal_admissibility, TerminalAdmissibility):
            raise ValueError("candidate terminal_admissibility is invalid")
        if self.activity == CandidateActivity.ACTIVE:
            assert self.bound_router_decision is not None
            proposal = terminal_proposal(
                self.bound_router_decision.router_state,
                completed_nonterminal_action_ids=(
                    self.completed_nonterminal_action_ids
                ),
            )
            expected_admissibility = TerminalAdmissibility.from_proposal(
                proposal
            )
            if self.terminal_admissibility != expected_admissibility:
                raise ValueError("terminal admissibility contradicts the bound router")
            expected_catalog = _canonical_catalog(
                self.action_catalog,
                activity=self.activity,
                decisions=self.decision_count,
                acquisitions=self.nonterminal_acquisition_count,
                completed_nonterminal_action_ids=(
                    self.completed_nonterminal_action_ids
                ),
                admissibility=expected_admissibility,
            )
            if self.action_catalog != expected_catalog:
                raise ValueError("candidate catalog contradicts terminal/ceiling rules")
            expected_preferred = proposal_preferred_action_id(
                router_action=self.bound_router_decision.action,
                action_catalog=expected_catalog,
                proposal=proposal,
            )
            if self.preferred_action_id != expected_preferred:
                raise ValueError("preferred action differs from the bound router/fallback rule")
        else:
            if self.terminal_admissibility != TerminalAdmissibility.closed():
                raise ValueError("terminal candidate must have closed admissibility")
            expected_catalog = _canonical_catalog(
                self.action_catalog,
                activity=self.activity,
                decisions=self.decision_count,
                acquisitions=self.nonterminal_acquisition_count,
                completed_nonterminal_action_ids=(
                    self.completed_nonterminal_action_ids
                ),
                admissibility=self.terminal_admissibility,
            )
            if self.action_catalog != expected_catalog:
                raise ValueError("terminal candidate catalog must be fully unavailable")
            if self.preferred_action_id is not None:
                raise ValueError("terminal candidate cannot have a preferred action")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "activity": self.activity.value,
            "decision_count": self.decision_count,
            "nonterminal_acquisition_count": self.nonterminal_acquisition_count,
            "completed_nonterminal_action_ids": list(
                self.completed_nonterminal_action_ids
            ),
            "router_state_sha256": self.router_state_sha256,
            "history_sha256": self.history_sha256,
            "policy_trajectory_head_sha256": self.policy_trajectory_head_sha256,
            "bound_router_decision": (
                None
                if self.bound_router_decision is None
                else self.bound_router_decision.to_dict()
            ),
            "terminal_admissibility": self.terminal_admissibility.to_dict(),
            "action_catalog": [item.to_dict() for item in self.action_catalog],
            "preferred_action_id": self.preferred_action_id,
        }

    @classmethod
    def from_dict(cls, value: Any, index: int = 0) -> CandidateRoundState:
        field_name = f"candidates[{index}]"
        data = _object(value, field_name)
        fields = {
            "candidate_id",
            "activity",
            "decision_count",
            "nonterminal_acquisition_count",
            "completed_nonterminal_action_ids",
            "router_state_sha256",
            "history_sha256",
            "policy_trajectory_head_sha256",
            "bound_router_decision",
            "terminal_admissibility",
            "action_catalog",
            "preferred_action_id",
        }
        _exact_fields(data, fields, field_name)
        raw_router = data["bound_router_decision"]
        raw_preferred = data["preferred_action_id"]
        if raw_preferred is not None and not isinstance(raw_preferred, str):
            raise ValueError(f"{field_name}.preferred_action_id must be string or null")
        catalog = _array(data["action_catalog"], f"{field_name}.action_catalog")
        completed = _array(
            data["completed_nonterminal_action_ids"],
            f"{field_name}.completed_nonterminal_action_ids",
        )
        return cls(
            candidate_id=_candidate_id(data["candidate_id"], f"{field_name}.candidate_id"),
            activity=_enum(CandidateActivity, data["activity"], f"{field_name}.activity"),
            decision_count=_integer(data["decision_count"], f"{field_name}.decision_count"),
            nonterminal_acquisition_count=_integer(
                data["nonterminal_acquisition_count"],
                f"{field_name}.nonterminal_acquisition_count",
            ),
            completed_nonterminal_action_ids=tuple(
                _string(item, f"{field_name}.completed_nonterminal_action_ids[{completed_index}]")
                for completed_index, item in enumerate(completed)
            ),
            router_state_sha256=_digest(
                data["router_state_sha256"],
                f"{field_name}.router_state_sha256",
            ),
            history_sha256=_digest(
                data["history_sha256"],
                f"{field_name}.history_sha256",
            ),
            policy_trajectory_head_sha256=_digest(
                data["policy_trajectory_head_sha256"],
                f"{field_name}.policy_trajectory_head_sha256",
            ),
            bound_router_decision=(
                None if raw_router is None else BoundRouterDecision.from_dict(raw_router)
            ),
            terminal_admissibility=TerminalAdmissibility.from_dict(
                data["terminal_admissibility"]
            ),
            action_catalog=tuple(
                ActionOffer.from_dict(item, action_index)
                for action_index, item in enumerate(catalog)
            ),
            preferred_action_id=raw_preferred,
        )


def _build_candidate_state(item: CandidateRoundInput) -> CandidateRoundState:
    if item.activity == CandidateActivity.ACTIVE:
        assert item.bound_router_decision is not None
        proposal = terminal_proposal(
            item.bound_router_decision.router_state,
            completed_nonterminal_action_ids=(
                item.completed_nonterminal_action_ids
            ),
        )
        admissibility = TerminalAdmissibility.from_proposal(proposal)
        catalog = _canonical_catalog(
            item.action_catalog,
            activity=item.activity,
            decisions=item.decision_count,
            acquisitions=item.nonterminal_acquisition_count,
            completed_nonterminal_action_ids=item.completed_nonterminal_action_ids,
            admissibility=admissibility,
        )
        preferred = proposal_preferred_action_id(
            router_action=item.bound_router_decision.action,
            action_catalog=catalog,
            proposal=proposal,
        )
    else:
        admissibility = TerminalAdmissibility.closed()
        catalog = _canonical_catalog(
            item.action_catalog,
            activity=item.activity,
            decisions=item.decision_count,
            acquisitions=item.nonterminal_acquisition_count,
            completed_nonterminal_action_ids=item.completed_nonterminal_action_ids,
            admissibility=admissibility,
        )
        preferred = None
    return CandidateRoundState(
        candidate_id=item.candidate_id,
        activity=item.activity,
        decision_count=item.decision_count,
        nonterminal_acquisition_count=item.nonterminal_acquisition_count,
        completed_nonterminal_action_ids=item.completed_nonterminal_action_ids,
        router_state_sha256=item.router_state_sha256,
        history_sha256=item.history_sha256,
        policy_trajectory_head_sha256=item.policy_trajectory_head_sha256,
        bound_router_decision=item.bound_router_decision,
        terminal_admissibility=admissibility,
        action_catalog=catalog,
        preferred_action_id=preferred,
    )


@dataclass(frozen=True)
class CandidateActionDecision:
    """One candidate's action draw inside a deterministic task round."""

    candidate_id: str
    candidate_position: int
    state_sha256: str
    candidate_scheduler_probability: float
    action_draw_counter: int
    sampler_draw: float
    behavior_distribution: tuple[BehaviorProbability, ...]
    chosen_action_id: str
    chosen_action_propensity: float
    chosen_log_action_propensity: float
    selection_identity_sha256: str
    logged_policy_decision: LoggedPolicyDecision

    def __post_init__(self) -> None:
        _candidate_id(self.candidate_id, "candidate_decision.candidate_id")
        position = _integer(
            self.candidate_position,
            "candidate_decision.candidate_position",
        )
        if not 0 <= position < CANDIDATES_PER_TASK:
            raise ValueError("candidate_position must be in [0, 3)")
        _digest(self.state_sha256, "candidate_decision.state_sha256")
        scheduler_probability = _probability(
            self.candidate_scheduler_probability,
            "candidate_decision.candidate_scheduler_probability",
        )
        if scheduler_probability != 1.0:
            raise ValueError("candidate scheduler probability must be exactly one")
        counter = _integer(
            self.action_draw_counter,
            "candidate_decision.action_draw_counter",
        )
        if not 0 <= counter < 2**64:
            raise ValueError("action_draw_counter must be uint64")
        draw = _number(self.sampler_draw, "candidate_decision.sampler_draw")
        if not 0.0 <= draw < 1.0:
            raise ValueError("candidate decision sampler_draw must be in [0, 1)")
        if not isinstance(self.behavior_distribution, (list, tuple)) or any(
            not isinstance(item, BehaviorProbability)
            for item in self.behavior_distribution
        ):
            raise ValueError("candidate behavior_distribution is invalid")
        distribution = tuple(self.behavior_distribution)
        action_ids = [item.action_id for item in distribution]
        if action_ids != sorted(action_ids):
            raise ValueError("candidate behavior distribution must be action-ID ordered")
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("candidate behavior distribution reuses action_id")
        if not isclose(
            fsum(item.propensity for item in distribution),
            1.0,
            rel_tol=0.0,
            abs_tol=_PROBABILITY_TOLERANCE,
        ):
            raise ValueError("candidate behavior distribution must sum to one")
        if self.chosen_action_id not in action_ids:
            raise ValueError("chosen action is absent from the behavior distribution")
        propensity = _probability(
            self.chosen_action_propensity,
            "candidate_decision.chosen_action_propensity",
        )
        expected_propensity = next(
            item.propensity
            for item in distribution
            if item.action_id == self.chosen_action_id
        )
        if propensity != expected_propensity:
            raise ValueError("chosen action propensity differs from its distribution entry")
        log_propensity = _number(
            self.chosen_log_action_propensity,
            "candidate_decision.chosen_log_action_propensity",
        )
        if log_propensity != log(propensity):
            raise ValueError("chosen log action propensity identity differs")
        if sample_behavior_action(distribution, sampler_draw=draw) != (
            self.chosen_action_id
        ):
            raise ValueError("chosen action differs from the canonical inverse-CDF sample")
        _digest(
            self.selection_identity_sha256,
            "candidate_decision.selection_identity_sha256",
        )
        if not isinstance(self.logged_policy_decision, LoggedPolicyDecision):
            raise ValueError(
                "candidate decision requires an exact LoggedPolicyDecision preimage"
            )
        logged = self.logged_policy_decision
        if (
            logged.candidate_id != self.candidate_id
            or logged.behavior_distribution != distribution
            or logged.chosen_action_id != self.chosen_action_id
            or logged.chosen_propensity != propensity
            or logged.sampler_draw != draw
            or logged.sampler_id != CANONICAL_SAMPLER_ID
            or logged.sampler_version != CANONICAL_SAMPLER_VERSION
            or logged.policy_id != BEHAVIOR_POLICY_ID
            or logged.policy_version != BEHAVIOR_POLICY_VERSION
            or logged.selection_reason_code != BEHAVIOR_SELECTION_REASON_CODE
            or logged.decision_sha256 != self.selection_identity_sha256
        ):
            raise ValueError(
                "candidate decision differs from its logged policy decision"
            )
        object.__setattr__(self, "behavior_distribution", distribution)
        object.__setattr__(self, "candidate_scheduler_probability", 1.0)
        object.__setattr__(self, "sampler_draw", draw)
        object.__setattr__(self, "chosen_action_propensity", propensity)
        object.__setattr__(self, "chosen_log_action_propensity", log_propensity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_position": self.candidate_position,
            "state_sha256": self.state_sha256,
            "candidate_scheduler_probability": self.candidate_scheduler_probability,
            "action_draw_counter": self.action_draw_counter,
            "sampler_draw": self.sampler_draw,
            "behavior_distribution": [
                item.to_dict() for item in self.behavior_distribution
            ],
            "chosen_action_id": self.chosen_action_id,
            "chosen_action_propensity": self.chosen_action_propensity,
            "chosen_log_action_propensity": self.chosen_log_action_propensity,
            "selection_identity_sha256": self.selection_identity_sha256,
            "logged_policy_decision": self.logged_policy_decision.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any, index: int = 0) -> CandidateActionDecision:
        field_name = f"scheduled_decisions[{index}]"
        data = _object(value, field_name)
        fields = {
            "candidate_id",
            "candidate_position",
            "state_sha256",
            "candidate_scheduler_probability",
            "action_draw_counter",
            "sampler_draw",
            "behavior_distribution",
            "chosen_action_id",
            "chosen_action_propensity",
            "chosen_log_action_propensity",
            "selection_identity_sha256",
            "logged_policy_decision",
        }
        _exact_fields(data, fields, field_name)
        distribution = _array(
            data["behavior_distribution"],
            f"{field_name}.behavior_distribution",
        )
        return cls(
            candidate_id=_candidate_id(
                data["candidate_id"],
                f"{field_name}.candidate_id",
            ),
            candidate_position=_integer(
                data["candidate_position"],
                f"{field_name}.candidate_position",
            ),
            state_sha256=_digest(
                data["state_sha256"],
                f"{field_name}.state_sha256",
            ),
            candidate_scheduler_probability=_number(
                data["candidate_scheduler_probability"],
                f"{field_name}.candidate_scheduler_probability",
            ),
            action_draw_counter=_integer(
                data["action_draw_counter"],
                f"{field_name}.action_draw_counter",
            ),
            sampler_draw=_number(
                data["sampler_draw"],
                f"{field_name}.sampler_draw",
            ),
            behavior_distribution=tuple(
                BehaviorProbability.from_dict(item, probability_index)
                for probability_index, item in enumerate(distribution)
            ),
            chosen_action_id=_string(
                data["chosen_action_id"],
                f"{field_name}.chosen_action_id",
            ),
            chosen_action_propensity=_number(
                data["chosen_action_propensity"],
                f"{field_name}.chosen_action_propensity",
            ),
            chosen_log_action_propensity=_number(
                data["chosen_log_action_propensity"],
                f"{field_name}.chosen_log_action_propensity",
            ),
            selection_identity_sha256=_digest(
                data["selection_identity_sha256"],
                f"{field_name}.selection_identity_sha256",
            ),
            logged_policy_decision=LoggedPolicyDecision.from_dict(
                data["logged_policy_decision"]
            ),
        )


@dataclass(frozen=True)
class ResultingCandidateDisposition:
    candidate_id: str
    activity: CandidateActivity
    policy_trajectory_head_sha256: str

    def __post_init__(self) -> None:
        _candidate_id(self.candidate_id, "resulting_disposition.candidate_id")
        if not isinstance(self.activity, CandidateActivity):
            raise ValueError("resulting disposition activity is invalid")
        _digest(
            self.policy_trajectory_head_sha256,
            "resulting_disposition.policy_trajectory_head_sha256",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "activity": self.activity.value,
            "policy_trajectory_head_sha256": self.policy_trajectory_head_sha256,
        }

    @classmethod
    def from_dict(cls, value: Any, index: int = 0) -> ResultingCandidateDisposition:
        field_name = f"resulting_dispositions[{index}]"
        data = _object(value, field_name)
        _exact_fields(
            data,
            {"candidate_id", "activity", "policy_trajectory_head_sha256"},
            field_name,
        )
        return cls(
            candidate_id=_candidate_id(
                data["candidate_id"],
                f"{field_name}.candidate_id",
            ),
            activity=_enum(
                CandidateActivity,
                data["activity"],
                f"{field_name}.activity",
            ),
            policy_trajectory_head_sha256=_digest(
                data["policy_trajectory_head_sha256"],
                f"{field_name}.policy_trajectory_head_sha256",
            ),
        )


def _state_digest(state: CandidateRoundState) -> str:
    return _canonical_sha256(state.to_dict())


def _resulting_policy_head(
    state: CandidateRoundState,
    decision: CandidateActionDecision | None,
) -> str:
    if decision is None:
        return state.policy_trajectory_head_sha256
    if (
        decision.logged_policy_decision.prior_trajectory_head_sha256
        != state.policy_trajectory_head_sha256
    ):
        raise ValueError("logged policy decision has the wrong prior trajectory head")
    return decision.logged_policy_decision.trajectory_head_sha256


def _expected_action_counter(
    task_order_index: int,
    round_index: int,
    candidate_position: int,
) -> int:
    return (
        task_order_index * ACTION_COUNTER_SLOTS_PER_TASK
        + round_index * CANDIDATES_PER_TASK
        + candidate_position
    )


def _build_action_decision(
    state: CandidateRoundState,
    *,
    task_id: str,
    task_order_index: int,
    round_index: int,
    candidate_position: int,
    scheduled_at: str,
    collection_policy_sha256: str,
) -> CandidateActionDecision:
    if state.activity != CandidateActivity.ACTIVE:
        raise ValueError("only active candidates receive round decisions")
    assert state.preferred_action_id is not None
    distribution = preferred_uniform_behavior_distribution(
        state.action_catalog,
        preferred_action_id=state.preferred_action_id,
        exploration_mass=EXPLORATION_MASS,
    )
    if min(item.propensity for item in distribution) < MINIMUM_ACTION_PROPENSITY:
        raise ValueError("candidate action propensity falls below the frozen floor")
    counter = _expected_action_counter(
        task_order_index,
        round_index,
        candidate_position,
    )
    draw = derive_action_draw(counter)
    chosen = sample_behavior_action(distribution, sampler_draw=draw)
    propensity = next(
        item.propensity for item in distribution if item.action_id == chosen
    )
    state_sha256 = _state_digest(state)
    identity_material = {
        "contract": SCHEDULER_CHAIN_CONTRACT,
        "task_id": task_id,
        "round_index": round_index,
        "candidate_id": state.candidate_id,
        "candidate_position": candidate_position,
        "state_sha256": state_sha256,
        "candidate_scheduler_probability": 1.0,
        "action_draw_counter": counter,
        "sampler_id": CANONICAL_SAMPLER_ID,
        "sampler_version": CANONICAL_SAMPLER_VERSION,
        "sampler_draw": draw,
        "behavior_distribution": [item.to_dict() for item in distribution],
        "chosen_action_id": chosen,
        "chosen_action_propensity": propensity,
        "chosen_log_action_propensity": log(propensity),
    }
    identity_seed = _canonical_sha256(identity_material)
    decision_id = "dec-" + _canonical_sha256({
        "kind": "prospective_policy_decision",
        "identity_seed": identity_seed,
    })[:32]
    route_action = COLLECTION_ACTION_ROUTE[chosen]
    acquisition_id = (
        None
        if route_action in _TERMINAL_ROUTE_ACTIONS
        else "acq-" + _canonical_sha256({
            "kind": "prospective_acquisition",
            "identity_seed": identity_seed,
        })[:32]
    )
    assert state.bound_router_decision is not None
    router_state = state.bound_router_decision.router_state
    logged = LoggedPolicyDecision(
        trajectory_id="traj-" + _canonical_sha256({
            "study_id": SCHEDULER_STUDY_ID,
            "task_id": task_id,
            "candidate_id": state.candidate_id,
        })[:32],
        decision_id=decision_id,
        acquisition_id=acquisition_id,
        decision_step=state.decision_count,
        decided_at=scheduled_at,
        instance_id=task_id,
        candidate_id=state.candidate_id,
        manifest_sha256=router_state.source_manifest_sha256,
        history_sha256=router_state.history_sha256(),
        router_state_sha256=router_state.canonical_digest(),
        prior_trajectory_head_sha256=state.policy_trajectory_head_sha256,
        policy_id=BEHAVIOR_POLICY_ID,
        policy_version=BEHAVIOR_POLICY_VERSION,
        policy_code_config_sha256=collection_policy_sha256,
        action_catalog=state.action_catalog,
        behavior_distribution=distribution,
        chosen_action_id=chosen,
        chosen_propensity=propensity,
        selection_reason_code=BEHAVIOR_SELECTION_REASON_CODE,
        sampler_id=CANONICAL_SAMPLER_ID,
        sampler_version=CANONICAL_SAMPLER_VERSION,
        sampler_draw=draw,
        router_state=router_state,
    )
    return CandidateActionDecision(
        candidate_id=state.candidate_id,
        candidate_position=candidate_position,
        state_sha256=state_sha256,
        candidate_scheduler_probability=1.0,
        action_draw_counter=counter,
        sampler_draw=draw,
        behavior_distribution=distribution,
        chosen_action_id=chosen,
        chosen_action_propensity=propensity,
        chosen_log_action_propensity=log(propensity),
        selection_identity_sha256=logged.decision_sha256,
        logged_policy_decision=logged,
    )


def _resulting_activity(
    state: CandidateRoundState,
    decision: CandidateActionDecision | None,
) -> CandidateActivity:
    if state.activity != CandidateActivity.ACTIVE:
        if decision is not None:
            raise ValueError("terminal candidate cannot receive a decision")
        return state.activity
    if decision is None:
        raise ValueError("active candidate is missing its round decision")
    route_action = COLLECTION_ACTION_ROUTE[decision.chosen_action_id]
    if route_action == RouteAction.ACCEPT:
        return CandidateActivity.ACCEPTED
    if route_action == RouteAction.REJECT:
        return CandidateActivity.REJECTED
    if route_action == RouteAction.ABSTAIN:
        return CandidateActivity.ABSTAINED
    return CandidateActivity.ACTIVE


@dataclass(frozen=True)
class TaskRoundDecision:
    """One write-ahead round over all nonterminal candidates in a task."""

    task_id: str
    task_order: tuple[str, ...]
    task_order_sha256: str
    task_order_index: int
    round_index: int
    scheduled_at: str
    prior_task_head_sha256: str
    prior_task_trajectory_probability: float
    prior_task_trajectory_log_probability: float
    collection_policy_sha256: str
    scheduler_contract_sha256: str
    frame_manifest_sha256: str
    protocol_sha256: str
    router_source_sha256: str
    router_policy_config_sha256: str
    candidate_order: tuple[str, ...]
    candidates: tuple[CandidateRoundState, ...]
    scheduled_decisions: tuple[CandidateActionDecision, ...]
    round_joint_probability: float
    round_joint_log_probability: float
    task_trajectory_action_log_propensities: tuple[float, ...]
    task_trajectory_probability: float
    task_trajectory_log_probability: float
    resulting_dispositions: tuple[ResultingCandidateDisposition, ...]
    completes_candidate_chains: bool
    task_state_sha256: str
    decision_sha256: str = ""
    task_head_sha256: str = ""
    schema_version: str = TASK_ROUND_SCHEMA_VERSION
    chain_contract: str = SCHEDULER_CHAIN_CONTRACT
    study_id: str = SCHEDULER_STUDY_ID
    action_draw_seed_sha256: str = ACTION_DRAW_SEED_SHA256
    candidate_order_seed_sha256: str = CANDIDATE_ORDER_SEED_SHA256
    task_order_seed_sha256: str = TASK_ORDER_SEED_SHA256
    action_draw_domain: str = ACTION_DRAW_DOMAIN
    candidate_order_domain: str = CANDIDATE_ORDER_DOMAIN
    task_order_domain: str = TASK_ORDER_DOMAIN
    sampler_id: str = CANONICAL_SAMPLER_ID
    sampler_version: str = CANONICAL_SAMPLER_VERSION

    def __post_init__(self) -> None:
        self._validate_identity_and_order()
        self._validate_candidates_and_decisions()
        self._validate_probabilities_and_dispositions()
        computed = _canonical_sha256(self._payload())
        if self.decision_sha256 and _digest(
            self.decision_sha256,
            "task_round.decision_sha256",
        ) != computed:
            raise ValueError("task round decision digest differs")
        object.__setattr__(self, "decision_sha256", computed)
        head = _canonical_sha256({
            "contract": SCHEDULER_CHAIN_CONTRACT,
            "prior_task_head_sha256": self.prior_task_head_sha256,
            "decision_sha256": computed,
        })
        if self.task_head_sha256 and _digest(
            self.task_head_sha256,
            "task_round.task_head_sha256",
        ) != head:
            raise ValueError("task round chain head differs")
        object.__setattr__(self, "task_head_sha256", head)

    def _validate_identity_and_order(self) -> None:
        expected_constants = {
            "schema_version": (self.schema_version, TASK_ROUND_SCHEMA_VERSION),
            "chain_contract": (self.chain_contract, SCHEDULER_CHAIN_CONTRACT),
            "study_id": (self.study_id, SCHEDULER_STUDY_ID),
            "action_draw_seed_sha256": (
                self.action_draw_seed_sha256,
                ACTION_DRAW_SEED_SHA256,
            ),
            "candidate_order_seed_sha256": (
                self.candidate_order_seed_sha256,
                CANDIDATE_ORDER_SEED_SHA256,
            ),
            "task_order_seed_sha256": (
                self.task_order_seed_sha256,
                TASK_ORDER_SEED_SHA256,
            ),
            "action_draw_domain": (self.action_draw_domain, ACTION_DRAW_DOMAIN),
            "candidate_order_domain": (
                self.candidate_order_domain,
                CANDIDATE_ORDER_DOMAIN,
            ),
            "task_order_domain": (self.task_order_domain, TASK_ORDER_DOMAIN),
            "sampler_id": (self.sampler_id, CANONICAL_SAMPLER_ID),
            "sampler_version": (self.sampler_version, CANONICAL_SAMPLER_VERSION),
        }
        for name, (actual, expected) in expected_constants.items():
            if actual != expected:
                raise ValueError(f"task round {name} differs from the frozen contract")
        task = _safe_identifier(self.task_id, "task_round.task_id")
        order = tuple(self.task_order)
        if order != derive_task_order(order):
            raise ValueError("task_order differs from the frozen seed derivation")
        if task not in order:
            raise ValueError("task_id is absent from task_order")
        expected_order_sha256 = _canonical_sha256(list(order))
        if _digest(self.task_order_sha256, "task_round.task_order_sha256") != (
            expected_order_sha256
        ):
            raise ValueError("task_order_sha256 differs")
        object.__setattr__(self, "task_order", order)
        object.__setattr__(self, "task_order_sha256", expected_order_sha256)
        index = _integer(self.task_order_index, "task_round.task_order_index")
        if index != order.index(task):
            raise ValueError("task_order_index differs from the frozen order")
        round_index = _integer(self.round_index, "task_round.round_index")
        if not 0 <= round_index < MAXIMUM_CANDIDATE_DECISIONS:
            raise ValueError("round_index exceeds the frozen candidate-chain limit")
        object.__setattr__(
            self,
            "scheduled_at",
            _timestamp(self.scheduled_at, "task_round.scheduled_at"),
        )
        prior_head = _digest(
            self.prior_task_head_sha256,
            "task_round.prior_task_head_sha256",
        )
        if round_index == 0 and prior_head != SCHEDULER_GENESIS_SHA256:
            raise ValueError("first task round must use the genesis prior head")
        if round_index > 0 and prior_head == SCHEDULER_GENESIS_SHA256:
            raise ValueError("nonzero task round cannot use the genesis prior head")
        _digest(self.collection_policy_sha256, "task_round.collection_policy_sha256")
        _digest(self.scheduler_contract_sha256, "task_round.scheduler_contract_sha256")
        _digest(self.frame_manifest_sha256, "task_round.frame_manifest_sha256")
        _digest(self.protocol_sha256, "task_round.protocol_sha256")
        if self.router_source_sha256 != ROUTER_SOURCE_SHA256:
            raise ValueError("task round router source differs from the frozen binding")
        if self.router_policy_config_sha256 != ROUTER_POLICY_CONFIG_SHA256:
            raise ValueError("task round router policy differs from the frozen binding")

    def _validate_candidates_and_decisions(self) -> None:
        if not isinstance(self.candidates, (list, tuple)) or any(
            not isinstance(item, CandidateRoundState) for item in self.candidates
        ):
            raise ValueError("task round candidates are invalid")
        candidates = tuple(self.candidates)
        if len(candidates) != CANDIDATES_PER_TASK:
            raise ValueError("task round requires exactly three candidate states")
        ids = tuple(item.candidate_id for item in candidates)
        expected_order = derive_candidate_order(ids)
        order = tuple(
            _candidate_id(item, f"candidate_order[{index}]")
            for index, item in enumerate(self.candidate_order)
        )
        if ids != expected_order or order != expected_order:
            raise ValueError("candidate state/order differs from the fixed seed derivation")
        if not any(item.activity == CandidateActivity.ACTIVE for item in candidates):
            raise ValueError("a completed task must use task selection, not another round")
        for state in candidates:
            if state.activity == CandidateActivity.ACTIVE:
                if state.decision_count != self.round_index:
                    raise ValueError(
                        "active candidate decision count must equal the round index"
                    )
                assert state.bound_router_decision is not None
                if state.bound_router_decision.router_state.instance_id != self.task_id:
                    raise ValueError("bound router state belongs to a different task")
            elif state.decision_count > self.round_index:
                raise ValueError("terminal candidate decision count exceeds round history")
        if self.round_index == 0 and any(
            state.activity != CandidateActivity.ACTIVE
            or state.decision_count != 0
            or state.nonterminal_acquisition_count != 0
            or state.completed_nonterminal_action_ids
            or state.policy_trajectory_head_sha256 != SCHEDULER_GENESIS_SHA256
            for state in candidates
        ):
            raise ValueError("round zero requires three active genesis candidate states")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "candidate_order", order)
        decisions = tuple(self.scheduled_decisions)
        if any(not isinstance(item, CandidateActionDecision) for item in decisions):
            raise ValueError("scheduled_decisions contains an invalid value")
        active = [item for item in candidates if item.activity == CandidateActivity.ACTIVE]
        if [item.candidate_id for item in decisions] != [item.candidate_id for item in active]:
            raise ValueError("every active candidate must receive exactly one ordered decision")
        by_candidate = {item.candidate_id: item for item in candidates}
        for decision in decisions:
            state = by_candidate[decision.candidate_id]
            position = order.index(decision.candidate_id)
            if decision.candidate_position != position:
                raise ValueError("candidate decision position differs from candidate order")
            if decision.state_sha256 != _state_digest(state):
                raise ValueError("candidate decision state digest differs")
            assert state.preferred_action_id is not None
            expected_distribution = preferred_uniform_behavior_distribution(
                state.action_catalog,
                preferred_action_id=state.preferred_action_id,
                exploration_mass=EXPLORATION_MASS,
            )
            if decision.behavior_distribution != expected_distribution:
                raise ValueError("candidate behavior distribution differs")
            counter = _expected_action_counter(
                self.task_order_index,
                self.round_index,
                position,
            )
            if decision.action_draw_counter != counter:
                raise ValueError("candidate action-draw counter differs")
            if decision.sampler_draw != derive_action_draw(counter):
                raise ValueError("candidate sampler draw differs from the frozen generator")
            identity_seed = _canonical_sha256({
                "contract": SCHEDULER_CHAIN_CONTRACT,
                "task_id": self.task_id,
                "round_index": self.round_index,
                "candidate_id": state.candidate_id,
                "candidate_position": position,
                "state_sha256": decision.state_sha256,
                "candidate_scheduler_probability": 1.0,
                "action_draw_counter": counter,
                "sampler_id": self.sampler_id,
                "sampler_version": self.sampler_version,
                "sampler_draw": decision.sampler_draw,
                "behavior_distribution": [
                    item.to_dict() for item in expected_distribution
                ],
                "chosen_action_id": decision.chosen_action_id,
                "chosen_action_propensity": decision.chosen_action_propensity,
                "chosen_log_action_propensity": (
                    decision.chosen_log_action_propensity
                ),
            })
            expected_decision_id = "dec-" + _canonical_sha256({
                "kind": "prospective_policy_decision",
                "identity_seed": identity_seed,
            })[:32]
            route_action = COLLECTION_ACTION_ROUTE[decision.chosen_action_id]
            expected_acquisition_id = (
                None
                if route_action in _TERMINAL_ROUTE_ACTIONS
                else "acq-" + _canonical_sha256({
                    "kind": "prospective_acquisition",
                    "identity_seed": identity_seed,
                })[:32]
            )
            logged = decision.logged_policy_decision
            assert state.bound_router_decision is not None
            router_state = state.bound_router_decision.router_state
            expected_trajectory_id = "traj-" + _canonical_sha256({
                "study_id": SCHEDULER_STUDY_ID,
                "task_id": self.task_id,
                "candidate_id": state.candidate_id,
            })[:32]
            if (
                logged.trajectory_id != expected_trajectory_id
                or logged.decision_id != expected_decision_id
                or logged.acquisition_id != expected_acquisition_id
                or logged.decision_step != state.decision_count
                or logged.decided_at != self.scheduled_at
                or logged.instance_id != self.task_id
                or logged.router_state != router_state
                or logged.manifest_sha256 != router_state.source_manifest_sha256
                or logged.history_sha256 != state.history_sha256
                or logged.router_state_sha256 != state.router_state_sha256
                or logged.prior_trajectory_head_sha256
                != state.policy_trajectory_head_sha256
                or logged.policy_code_config_sha256
                != self.collection_policy_sha256
                or logged.action_catalog != state.action_catalog
                or logged.decision_sha256
                != decision.selection_identity_sha256
            ):
                raise ValueError(
                    "candidate logged policy identity differs from the frozen round"
                )
        object.__setattr__(self, "scheduled_decisions", decisions)

    def _validate_probabilities_and_dispositions(self) -> None:
        expected_round_log = fsum(
            item.chosen_log_action_propensity for item in self.scheduled_decisions
        )
        expected_round_probability = exp(expected_round_log)
        if _number(
            self.round_joint_log_probability,
            "task_round.round_joint_log_probability",
        ) != expected_round_log:
            raise ValueError("round joint log probability is not the sum of action logs")
        if _number(
            self.round_joint_probability,
            "task_round.round_joint_probability",
        ) != expected_round_probability:
            raise ValueError("round joint reporting probability differs")
        if not isinstance(
            self.task_trajectory_action_log_propensities,
            (list, tuple),
        ):
            raise ValueError("task trajectory log-propensity terms must be a sequence")
        terms = tuple(
            _number(item, f"task_round.log_propensity_terms[{index}]")
            for index, item in enumerate(
                self.task_trajectory_action_log_propensities
            )
        )
        current_terms = tuple(
            item.chosen_log_action_propensity for item in self.scheduled_decisions
        )
        if len(terms) < len(current_terms) or terms[-len(current_terms) :] != current_terms:
            raise ValueError("task trajectory terms do not end with this round's actions")
        prior_terms = terms[: -len(current_terms)]
        prior_log = fsum(prior_terms)
        prior_probability = exp(prior_log)
        if _number(
            self.prior_task_trajectory_log_probability,
            "task_round.prior_task_trajectory_log_probability",
        ) != prior_log:
            raise ValueError("prior task log probability differs from its canonical terms")
        if _number(
            self.prior_task_trajectory_probability,
            "task_round.prior_task_trajectory_probability",
        ) != prior_probability:
            raise ValueError("prior task probability differs from its canonical terms")
        if self.round_index == 0 and prior_terms:
            raise ValueError("first task round cannot carry prior propensity terms")
        expected_task_log = fsum(terms)
        expected_task_probability = exp(expected_task_log)
        if _number(
            self.task_trajectory_log_probability,
            "task_round.task_trajectory_log_probability",
        ) != expected_task_log:
            raise ValueError("task trajectory log probability identity differs")
        if _number(
            self.task_trajectory_probability,
            "task_round.task_trajectory_probability",
        ) != expected_task_probability:
            raise ValueError("task trajectory reporting probability differs")
        decision_by_candidate = {
            item.candidate_id: item for item in self.scheduled_decisions
        }
        expected_dispositions = tuple(
            ResultingCandidateDisposition(
                candidate_id=state.candidate_id,
                activity=_resulting_activity(
                    state,
                    decision_by_candidate.get(state.candidate_id),
                ),
                policy_trajectory_head_sha256=_resulting_policy_head(
                    state,
                    decision_by_candidate.get(state.candidate_id),
                ),
            )
            for state in self.candidates
        )
        dispositions = tuple(self.resulting_dispositions)
        if dispositions != expected_dispositions:
            raise ValueError("resulting candidate dispositions differ")
        object.__setattr__(self, "resulting_dispositions", dispositions)
        complete = all(
            item.activity != CandidateActivity.ACTIVE for item in dispositions
        )
        if not isinstance(self.completes_candidate_chains, bool) or (
            self.completes_candidate_chains != complete
        ):
            raise ValueError("completes_candidate_chains differs")
        expected_state_sha256 = _canonical_sha256({
            "task_id": self.task_id,
            "task_order_sha256": self.task_order_sha256,
            "task_order_index": self.task_order_index,
            "round_index": self.round_index,
            "prior_task_head_sha256": self.prior_task_head_sha256,
            "collection_policy_sha256": self.collection_policy_sha256,
            "scheduler_contract_sha256": self.scheduler_contract_sha256,
            "frame_manifest_sha256": self.frame_manifest_sha256,
            "protocol_sha256": self.protocol_sha256,
            "router_source_sha256": self.router_source_sha256,
            "router_policy_config_sha256": self.router_policy_config_sha256,
            "candidate_order": list(self.candidate_order),
            "candidates": [item.to_dict() for item in self.candidates],
            "scheduled_decisions": [
                item.to_dict() for item in self.scheduled_decisions
            ],
        })
        if _digest(self.task_state_sha256, "task_round.task_state_sha256") != (
            expected_state_sha256
        ):
            raise ValueError("task_state_sha256 differs")
        object.__setattr__(self, "task_state_sha256", expected_state_sha256)
        object.__setattr__(self, "prior_task_trajectory_probability", prior_probability)
        object.__setattr__(self, "prior_task_trajectory_log_probability", prior_log)
        object.__setattr__(self, "round_joint_probability", expected_round_probability)
        object.__setattr__(self, "round_joint_log_probability", expected_round_log)
        object.__setattr__(self, "task_trajectory_action_log_propensities", terms)
        object.__setattr__(self, "task_trajectory_probability", expected_task_probability)
        object.__setattr__(self, "task_trajectory_log_probability", expected_task_log)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "chain_contract": self.chain_contract,
            "study_id": self.study_id,
            "action_draw_seed_sha256": self.action_draw_seed_sha256,
            "candidate_order_seed_sha256": self.candidate_order_seed_sha256,
            "task_order_seed_sha256": self.task_order_seed_sha256,
            "action_draw_domain": self.action_draw_domain,
            "candidate_order_domain": self.candidate_order_domain,
            "task_order_domain": self.task_order_domain,
            "sampler_id": self.sampler_id,
            "sampler_version": self.sampler_version,
            "task_id": self.task_id,
            "task_order": list(self.task_order),
            "task_order_sha256": self.task_order_sha256,
            "task_order_index": self.task_order_index,
            "round_index": self.round_index,
            "scheduled_at": self.scheduled_at,
            "prior_task_head_sha256": self.prior_task_head_sha256,
            "prior_task_trajectory_probability": (
                self.prior_task_trajectory_probability
            ),
            "prior_task_trajectory_log_probability": (
                self.prior_task_trajectory_log_probability
            ),
            "collection_policy_sha256": self.collection_policy_sha256,
            "scheduler_contract_sha256": self.scheduler_contract_sha256,
            "frame_manifest_sha256": self.frame_manifest_sha256,
            "protocol_sha256": self.protocol_sha256,
            "router_source_sha256": self.router_source_sha256,
            "router_policy_config_sha256": self.router_policy_config_sha256,
            "candidate_order": list(self.candidate_order),
            "candidates": [item.to_dict() for item in self.candidates],
            "scheduled_decisions": [
                item.to_dict() for item in self.scheduled_decisions
            ],
            "round_joint_probability": self.round_joint_probability,
            "round_joint_log_probability": self.round_joint_log_probability,
            "task_trajectory_action_log_propensities": list(
                self.task_trajectory_action_log_propensities
            ),
            "task_trajectory_probability": self.task_trajectory_probability,
            "task_trajectory_log_probability": (
                self.task_trajectory_log_probability
            ),
            "resulting_dispositions": [
                item.to_dict() for item in self.resulting_dispositions
            ],
            "completes_candidate_chains": self.completes_candidate_chains,
            "task_state_sha256": self.task_state_sha256,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._payload(),
            "decision_sha256": self.decision_sha256,
            "task_head_sha256": self.task_head_sha256,
        }

    def canonical_digest(self) -> str:
        computed = _canonical_sha256(self._payload())
        if computed != self.decision_sha256:
            raise ValueError("task round changed after validation")
        return computed

    def validate_against_bindings(self, bindings: SchedulerBindings) -> None:
        if not isinstance(bindings, SchedulerBindings):
            raise ValueError("task round requires validated scheduler bindings")
        expected = {
            "collection_policy_sha256": bindings.collection_policy_sha256,
            "scheduler_contract_sha256": bindings.scheduler_contract_sha256,
            "frame_manifest_sha256": bindings.frame.manifest_sha256,
            "protocol_sha256": bindings.protocol_sha256,
            "router_source_sha256": bindings.router_source_sha256,
            "router_policy_config_sha256": bindings.router_policy_config_sha256,
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValueError(f"task round {name} differs from validated bindings")
        expected_task_order = derive_task_order(bindings.frame.task_ids)
        if self.task_order != expected_task_order:
            raise ValueError("task round substitutes the exact frozen task frame")
        expected_candidates = set(bindings.frame.candidate_ids_for(self.task_id))
        if {item.candidate_id for item in self.candidates} != expected_candidates:
            raise ValueError("task round substitutes the frozen task candidate mapping")

    @classmethod
    def from_dict(cls, value: Any) -> TaskRoundDecision:
        data = _object(value, "task_round")
        fields = {
            "schema_version",
            "chain_contract",
            "study_id",
            "action_draw_seed_sha256",
            "candidate_order_seed_sha256",
            "task_order_seed_sha256",
            "action_draw_domain",
            "candidate_order_domain",
            "task_order_domain",
            "sampler_id",
            "sampler_version",
            "task_id",
            "task_order",
            "task_order_sha256",
            "task_order_index",
            "round_index",
            "scheduled_at",
            "prior_task_head_sha256",
            "prior_task_trajectory_probability",
            "prior_task_trajectory_log_probability",
            "collection_policy_sha256",
            "scheduler_contract_sha256",
            "frame_manifest_sha256",
            "protocol_sha256",
            "router_source_sha256",
            "router_policy_config_sha256",
            "candidate_order",
            "candidates",
            "scheduled_decisions",
            "round_joint_probability",
            "round_joint_log_probability",
            "task_trajectory_action_log_propensities",
            "task_trajectory_probability",
            "task_trajectory_log_probability",
            "resulting_dispositions",
            "completes_candidate_chains",
            "task_state_sha256",
            "decision_sha256",
            "task_head_sha256",
        }
        _exact_fields(data, fields, "task_round")
        task_order = _array(data["task_order"], "task_round.task_order")
        candidate_order = _array(
            data["candidate_order"],
            "task_round.candidate_order",
        )
        candidates = _array(data["candidates"], "task_round.candidates")
        scheduled = _array(
            data["scheduled_decisions"],
            "task_round.scheduled_decisions",
        )
        dispositions = _array(
            data["resulting_dispositions"],
            "task_round.resulting_dispositions",
        )
        log_terms = _array(
            data["task_trajectory_action_log_propensities"],
            "task_round.task_trajectory_action_log_propensities",
        )
        return cls(
            schema_version=_string(data["schema_version"], "task_round.schema_version"),
            chain_contract=_string(data["chain_contract"], "task_round.chain_contract"),
            study_id=_string(data["study_id"], "task_round.study_id"),
            action_draw_seed_sha256=_digest(
                data["action_draw_seed_sha256"],
                "task_round.action_draw_seed_sha256",
            ),
            candidate_order_seed_sha256=_digest(
                data["candidate_order_seed_sha256"],
                "task_round.candidate_order_seed_sha256",
            ),
            task_order_seed_sha256=_digest(
                data["task_order_seed_sha256"],
                "task_round.task_order_seed_sha256",
            ),
            action_draw_domain=_string(
                data["action_draw_domain"],
                "task_round.action_draw_domain",
            ),
            candidate_order_domain=_string(
                data["candidate_order_domain"],
                "task_round.candidate_order_domain",
            ),
            task_order_domain=_string(
                data["task_order_domain"],
                "task_round.task_order_domain",
            ),
            sampler_id=_string(data["sampler_id"], "task_round.sampler_id"),
            sampler_version=_string(
                data["sampler_version"],
                "task_round.sampler_version",
            ),
            task_id=_string(data["task_id"], "task_round.task_id"),
            task_order=tuple(
                _string(item, f"task_round.task_order[{index}]")
                for index, item in enumerate(task_order)
            ),
            task_order_sha256=_digest(
                data["task_order_sha256"],
                "task_round.task_order_sha256",
            ),
            task_order_index=_integer(
                data["task_order_index"],
                "task_round.task_order_index",
            ),
            round_index=_integer(data["round_index"], "task_round.round_index"),
            scheduled_at=_timestamp(data["scheduled_at"], "task_round.scheduled_at"),
            prior_task_head_sha256=_digest(
                data["prior_task_head_sha256"],
                "task_round.prior_task_head_sha256",
            ),
            prior_task_trajectory_probability=_number(
                data["prior_task_trajectory_probability"],
                "task_round.prior_task_trajectory_probability",
            ),
            prior_task_trajectory_log_probability=_number(
                data["prior_task_trajectory_log_probability"],
                "task_round.prior_task_trajectory_log_probability",
            ),
            collection_policy_sha256=_digest(
                data["collection_policy_sha256"],
                "task_round.collection_policy_sha256",
            ),
            scheduler_contract_sha256=_digest(
                data["scheduler_contract_sha256"],
                "task_round.scheduler_contract_sha256",
            ),
            frame_manifest_sha256=_digest(
                data["frame_manifest_sha256"],
                "task_round.frame_manifest_sha256",
            ),
            protocol_sha256=_digest(
                data["protocol_sha256"],
                "task_round.protocol_sha256",
            ),
            router_source_sha256=_digest(
                data["router_source_sha256"],
                "task_round.router_source_sha256",
            ),
            router_policy_config_sha256=_digest(
                data["router_policy_config_sha256"],
                "task_round.router_policy_config_sha256",
            ),
            candidate_order=tuple(
                _candidate_id(item, f"task_round.candidate_order[{index}]")
                for index, item in enumerate(candidate_order)
            ),
            candidates=tuple(
                CandidateRoundState.from_dict(item, index)
                for index, item in enumerate(candidates)
            ),
            scheduled_decisions=tuple(
                CandidateActionDecision.from_dict(item, index)
                for index, item in enumerate(scheduled)
            ),
            round_joint_probability=_number(
                data["round_joint_probability"],
                "task_round.round_joint_probability",
            ),
            round_joint_log_probability=_number(
                data["round_joint_log_probability"],
                "task_round.round_joint_log_probability",
            ),
            task_trajectory_action_log_propensities=tuple(
                _number(item, f"task_round.log_propensity_terms[{index}]")
                for index, item in enumerate(log_terms)
            ),
            task_trajectory_probability=_number(
                data["task_trajectory_probability"],
                "task_round.task_trajectory_probability",
            ),
            task_trajectory_log_probability=_number(
                data["task_trajectory_log_probability"],
                "task_round.task_trajectory_log_probability",
            ),
            resulting_dispositions=tuple(
                ResultingCandidateDisposition.from_dict(item, index)
                for index, item in enumerate(dispositions)
            ),
            completes_candidate_chains=_boolean(
                data["completes_candidate_chains"],
                "task_round.completes_candidate_chains",
            ),
            task_state_sha256=_digest(
                data["task_state_sha256"],
                "task_round.task_state_sha256",
            ),
            decision_sha256=_digest(
                data["decision_sha256"],
                "task_round.decision_sha256",
            ),
            task_head_sha256=_digest(
                data["task_head_sha256"],
                "task_round.task_head_sha256",
            ),
        )


def build_task_round_decision(
    *,
    bindings: SchedulerBindings,
    task_id: str,
    scheduled_at: str,
    candidates: Sequence[CandidateRoundInput],
    prior_rounds: Sequence[TaskRoundDecision] = (),
) -> TaskRoundDecision:
    """Build a deterministic write-ahead round for all active candidates."""

    if not isinstance(bindings, SchedulerBindings):
        raise ValueError("build requires repository-validated scheduler bindings")
    if not isinstance(prior_rounds, (list, tuple)) or any(
        not isinstance(item, TaskRoundDecision) for item in prior_rounds
    ):
        raise ValueError("prior_rounds must contain TaskRoundDecision values")
    prefix = tuple(prior_rounds)
    if prefix:
        validate_task_round_chain(prefix, bindings=bindings)
    if not isinstance(candidates, (list, tuple)) or any(
        not isinstance(item, CandidateRoundInput) for item in candidates
    ):
        raise ValueError("candidates must contain CandidateRoundInput values")
    inputs = tuple(candidates)
    if len(inputs) != CANDIDATES_PER_TASK:
        raise ValueError("task round requires exactly three candidate inputs")
    input_by_id = {item.candidate_id: item for item in inputs}
    if len(input_by_id) != CANDIDATES_PER_TASK:
        raise ValueError("task round candidate identities must be unique")
    task = _safe_identifier(task_id, "task_id")
    timestamp = _timestamp(scheduled_at, "scheduled_at")
    expected_candidate_ids = set(bindings.frame.candidate_ids_for(task))
    if set(input_by_id) != expected_candidate_ids:
        raise ValueError("candidate inputs differ from the frozen task mapping")
    candidate_order = derive_candidate_order(tuple(input_by_id))
    states = tuple(
        _build_candidate_state(input_by_id[candidate_id])
        for candidate_id in candidate_order
    )
    task_order = derive_task_order(bindings.frame.task_ids)
    task_order_index = task_order.index(task)
    round_index = len(prefix)
    if prefix and prefix[-1].task_id != task:
        raise ValueError("prior task-round prefix belongs to a different task")
    if prefix and prefix[-1].completes_candidate_chains:
        raise ValueError("a completed candidate trajectory cannot continue")
    prior_head = (
        SCHEDULER_GENESIS_SHA256 if not prefix else prefix[-1].task_head_sha256
    )
    prior_terms = (
        ()
        if not prefix
        else prefix[-1].task_trajectory_action_log_propensities
    )
    prior_log = fsum(prior_terms)
    prior_probability = exp(prior_log)
    decisions = tuple(
        _build_action_decision(
            state,
            task_id=task,
            task_order_index=task_order_index,
            round_index=round_index,
            candidate_position=position,
            scheduled_at=timestamp,
            collection_policy_sha256=bindings.collection_policy_sha256,
        )
        for position, state in enumerate(states)
        if state.activity == CandidateActivity.ACTIVE
    )
    if not decisions:
        raise ValueError("completed candidate chains require task selection")
    round_log = fsum(item.chosen_log_action_propensity for item in decisions)
    round_probability = exp(round_log)
    trajectory_terms = (
        *prior_terms,
        *(item.chosen_log_action_propensity for item in decisions),
    )
    task_log = fsum(trajectory_terms)
    task_probability = exp(task_log)
    decision_by_candidate = {item.candidate_id: item for item in decisions}
    dispositions = tuple(
        ResultingCandidateDisposition(
            candidate_id=state.candidate_id,
            activity=_resulting_activity(
                state,
                decision_by_candidate.get(state.candidate_id),
            ),
            policy_trajectory_head_sha256=_resulting_policy_head(
                state,
                decision_by_candidate.get(state.candidate_id),
            ),
        )
        for state in states
    )
    complete = all(item.activity != CandidateActivity.ACTIVE for item in dispositions)
    task_order_sha256 = _canonical_sha256(list(task_order))
    task_state_sha256 = _canonical_sha256({
        "task_id": task,
        "task_order_sha256": task_order_sha256,
        "task_order_index": task_order_index,
        "round_index": round_index,
        "prior_task_head_sha256": prior_head,
        "collection_policy_sha256": bindings.collection_policy_sha256,
        "scheduler_contract_sha256": bindings.scheduler_contract_sha256,
        "frame_manifest_sha256": bindings.frame.manifest_sha256,
        "protocol_sha256": bindings.protocol_sha256,
        "router_source_sha256": bindings.router_source_sha256,
        "router_policy_config_sha256": bindings.router_policy_config_sha256,
        "candidate_order": list(candidate_order),
        "candidates": [item.to_dict() for item in states],
        "scheduled_decisions": [item.to_dict() for item in decisions],
    })
    result = TaskRoundDecision(
        task_id=task,
        task_order=task_order,
        task_order_sha256=task_order_sha256,
        task_order_index=task_order_index,
        round_index=round_index,
        scheduled_at=timestamp,
        prior_task_head_sha256=prior_head,
        prior_task_trajectory_probability=prior_probability,
        prior_task_trajectory_log_probability=prior_log,
        collection_policy_sha256=bindings.collection_policy_sha256,
        scheduler_contract_sha256=bindings.scheduler_contract_sha256,
        frame_manifest_sha256=bindings.frame.manifest_sha256,
        protocol_sha256=bindings.protocol_sha256,
        router_source_sha256=bindings.router_source_sha256,
        router_policy_config_sha256=bindings.router_policy_config_sha256,
        candidate_order=candidate_order,
        candidates=states,
        scheduled_decisions=decisions,
        round_joint_probability=round_probability,
        round_joint_log_probability=round_log,
        task_trajectory_action_log_propensities=trajectory_terms,
        task_trajectory_probability=task_probability,
        task_trajectory_log_probability=task_log,
        resulting_dispositions=dispositions,
        completes_candidate_chains=complete,
        task_state_sha256=task_state_sha256,
    )
    result.validate_against_bindings(bindings)
    validate_task_round_chain((*prefix, result), bindings=bindings)
    return result


def load_task_round_decision(
    stream: TextIO,
    *,
    bindings: SchedulerBindings,
) -> TaskRoundDecision:
    """Load exactly one strict, self-verifying task round."""

    try:
        value = strict_json_load(stream)
    except ValueError as exc:
        raise ValueError(f"invalid task-round JSON: {exc}") from exc
    result = TaskRoundDecision.from_dict(value)
    result.validate_against_bindings(bindings)
    return result


def _offer_identity(offer: ActionOffer) -> tuple[Any, ...]:
    return (
        offer.route_action,
        offer.evidence_kind,
        offer.adapter_id,
        offer.adapter_version,
        offer.action_spec_sha256,
    )


def _decision_route(decision: CandidateActionDecision) -> RouteAction:
    return COLLECTION_ACTION_ROUTE[decision.chosen_action_id]


def validate_task_round_chain(
    decisions: Sequence[TaskRoundDecision],
    *,
    bindings: SchedulerBindings,
) -> None:
    """Validate a complete prefix of one task's candidate-round trajectory."""

    if not decisions:
        raise ValueError("task round chain cannot be empty")
    if any(not isinstance(item, TaskRoundDecision) for item in decisions):
        raise ValueError("task round chain contains an invalid value")
    if not isinstance(bindings, SchedulerBindings):
        raise ValueError("task round chain requires validated scheduler bindings")
    first = decisions[0]
    if first.round_index != 0:
        raise ValueError("task round chain must start at round zero")
    if any(item.activity != CandidateActivity.ACTIVE for item in first.candidates):
        raise ValueError("task round chain must start with three active candidates")
    if any(
        item.decision_count != 0
        or item.nonterminal_acquisition_count != 0
        or item.completed_nonterminal_action_ids
        or item.policy_trajectory_head_sha256 != SCHEDULER_GENESIS_SHA256
        for item in first.candidates
    ):
        raise ValueError("task round chain must start from zero-decision genesis states")
    bootstrap_steps = []
    for item in first.candidates:
        if item.bound_router_decision is None:
            raise ValueError("round zero candidate omits its bound router state")
        steps = item.bound_router_decision.router_state.bootstrap_history
        if len(steps) != 1:
            raise ValueError("round zero requires one bootstrap receipt per candidate")
        bootstrap_steps.append(steps[0])
    if len({item.receipt_sha256 for item in bootstrap_steps}) != CANDIDATES_PER_TASK:
        raise ValueError("round zero bootstrap receipt identities must be candidate-distinct")
    if len(
        {item.observation.acquisition_id for item in bootstrap_steps}
    ) != CANDIDATES_PER_TASK:
        raise ValueError("round zero bootstrap acquisition IDs must be candidate-distinct")
    seen_decisions: set[str] = set()
    for index, current in enumerate(decisions):
        if index > 0 and decisions[index - 1].completes_candidate_chains:
            raise ValueError("a completed candidate-round trajectory cannot continue")
        current.canonical_digest()
        current.validate_against_bindings(bindings)
        if current.decision_sha256 in seen_decisions:
            raise ValueError("task round chain repeats a decision identity")
        seen_decisions.add(current.decision_sha256)
        if current.round_index != index:
            raise ValueError("task round indices must be contiguous from zero")
        if index == 0:
            continue
        previous = decisions[index - 1]
        if (
            current.task_id != previous.task_id
            or current.task_order != previous.task_order
            or current.task_order_index != previous.task_order_index
            or current.candidate_order != previous.candidate_order
        ):
            raise ValueError("task round chain changes task/candidate identity")
        if (
            current.collection_policy_sha256 != previous.collection_policy_sha256
            or current.scheduler_contract_sha256
            != previous.scheduler_contract_sha256
            or current.frame_manifest_sha256 != previous.frame_manifest_sha256
            or current.protocol_sha256 != previous.protocol_sha256
            or current.router_source_sha256 != previous.router_source_sha256
            or current.router_policy_config_sha256
            != previous.router_policy_config_sha256
        ):
            raise ValueError("task round chain changes frozen configuration identity")
        if current.prior_task_head_sha256 != previous.task_head_sha256:
            raise ValueError("task round chain has a broken prior-head link")
        if (
            current.prior_task_trajectory_probability
            != previous.task_trajectory_probability
            or current.prior_task_trajectory_log_probability
            != previous.task_trajectory_log_probability
        ):
            raise ValueError("task round chain has a broken probability/log prefix")
        expected_terms = (
            *previous.task_trajectory_action_log_propensities,
            *(
                item.chosen_log_action_propensity
                for item in current.scheduled_decisions
            ),
        )
        if current.task_trajectory_action_log_propensities != expected_terms:
            raise ValueError("task round chain has a broken canonical log-term prefix")
        if current.scheduled_at < previous.scheduled_at:
            raise ValueError("task round timestamps run backwards")

        prior_state = {item.candidate_id: item for item in previous.candidates}
        current_state = {item.candidate_id: item for item in current.candidates}
        prior_action = {
            item.candidate_id: item for item in previous.scheduled_decisions
        }
        resulting = {
            item.candidate_id: item
            for item in previous.resulting_dispositions
        }
        for candidate_id in previous.candidate_order:
            old = prior_state[candidate_id]
            new = current_state[candidate_id]
            action = prior_action.get(candidate_id)
            if new.activity != resulting[candidate_id].activity:
                raise ValueError("candidate activity does not follow the prior round")
            if new.policy_trajectory_head_sha256 != (
                resulting[candidate_id].policy_trajectory_head_sha256
            ):
                raise ValueError("candidate policy head does not follow the prior decision")
            old_offers = {item.action_id: item for item in old.action_catalog}
            new_offers = {item.action_id: item for item in new.action_catalog}
            for action_id in COLLECTION_ACTION_IDS:
                if _offer_identity(old_offers[action_id]) != _offer_identity(
                    new_offers[action_id]
                ):
                    raise ValueError("stable action_id changes intervention identity")
            if old.activity != CandidateActivity.ACTIVE:
                if (
                    new.decision_count != old.decision_count
                    or new.nonterminal_acquisition_count
                    != old.nonterminal_acquisition_count
                    or new.completed_nonterminal_action_ids
                    != old.completed_nonterminal_action_ids
                    or new.router_state_sha256 != old.router_state_sha256
                    or new.history_sha256 != old.history_sha256
                ):
                    raise ValueError("terminal candidate state changed in a later round")
                continue
            assert action is not None
            route_action = _decision_route(action)
            acquisition = route_action not in _TERMINAL_ROUTE_ACTIONS
            if new.decision_count != old.decision_count + 1:
                raise ValueError("candidate decision count did not advance exactly once")
            expected_acquisitions = old.nonterminal_acquisition_count + int(acquisition)
            if new.nonterminal_acquisition_count != expected_acquisitions:
                raise ValueError("candidate acquisition count does not match prior action")
            completed_extension = (
                (action.chosen_action_id,) if acquisition else ()
            )
            expected_completed = tuple(sorted((
                *old.completed_nonterminal_action_ids,
                *completed_extension,
            )))
            if new.completed_nonterminal_action_ids != expected_completed:
                raise ValueError("candidate completed action IDs do not match prior action")
            if acquisition:
                if new.activity != CandidateActivity.ACTIVE:
                    raise ValueError("nonterminal acquisition cannot terminate a candidate")
                assert old.bound_router_decision is not None
                assert new.bound_router_decision is not None
                old_router_state = old.bound_router_decision.router_state
                new_router_state = new.bound_router_decision.router_state
                if (
                    new_router_state.bootstrap_history
                    != old_router_state.bootstrap_history
                    or
                    new_router_state.evidence_history[:-1]
                    != old_router_state.evidence_history
                    or len(new_router_state.evidence_history)
                    != len(old_router_state.evidence_history) + 1
                    or new_router_state.route_history[:-1]
                    != old_router_state.route_history
                    or len(new_router_state.route_history)
                    != len(old_router_state.route_history) + 1
                ):
                    raise ValueError(
                        "acquisition successor must append exactly one typed route/result"
                    )
                last_route = new_router_state.route_history[-1]
                if last_route.action != route_action:
                    raise ValueError("typed successor route differs from the sampled action")
                expected_route_projection = (
                    old.bound_router_decision.policy_version,
                    old.bound_router_decision.candidate_risk,
                    old.bound_router_decision.verifier_risk,
                    old.bound_router_decision.expected_information_gain,
                    old.bound_router_decision.estimated_relative_cost,
                    old.bound_router_decision.scores_calibrated,
                    old.bound_router_decision.calibration_id,
                )
                actual_route_projection = (
                    last_route.policy_version,
                    last_route.candidate_risk,
                    last_route.verifier_risk,
                    last_route.expected_information_gain,
                    last_route.estimated_relative_cost,
                    last_route.scores_calibrated,
                    last_route.calibration_id,
                )
                if actual_route_projection != expected_route_projection:
                    raise ValueError("typed successor route loses the bound-router identity")
                if (
                    new_router_state.source_manifest_sha256
                    == old_router_state.source_manifest_sha256
                ):
                    raise ValueError("acquisition successor must bind an updated manifest")
            elif (
                new.router_state_sha256 != old.router_state_sha256
                or new.history_sha256 != old.history_sha256
            ):
                raise ValueError("terminal action cannot fabricate acquisition history")

    policy_decisions_by_candidate: dict[str, list[LoggedPolicyDecision]] = {
        candidate_id: [] for candidate_id in first.candidate_order
    }
    for round_decision in decisions:
        for candidate_decision in round_decision.scheduled_decisions:
            policy_decisions_by_candidate[candidate_decision.candidate_id].append(
                candidate_decision.logged_policy_decision
            )
    for candidate_id in first.candidate_order:
        validate_policy_decision_chain(policy_decisions_by_candidate[candidate_id])


@dataclass(frozen=True)
class TaskSelectionDecision:
    """Separate deterministic task selection after all three chains terminate."""

    task_id: str
    scheduled_at: str
    round_decision_sha256s: tuple[str, ...]
    final_round_decision_sha256: str
    final_task_head_sha256: str
    final_task_action_log_propensities: tuple[float, ...]
    final_task_trajectory_probability: float
    final_task_trajectory_log_probability: float
    collection_policy_sha256: str
    scheduler_contract_sha256: str
    frame_manifest_sha256: str
    protocol_sha256: str
    router_source_sha256: str
    router_policy_config_sha256: str
    candidate_order: tuple[str, ...]
    final_dispositions: tuple[ResultingCandidateDisposition, ...]
    disposition: TaskSelectionDisposition
    selected_candidate_id: str | None
    selection_identity_sha256: str
    decision_sha256: str = ""
    schema_version: str = TASK_SELECTION_SCHEMA_VERSION
    study_id: str = SCHEDULER_STUDY_ID

    def __post_init__(self) -> None:
        if self.schema_version != TASK_SELECTION_SCHEMA_VERSION:
            raise ValueError("unsupported task-selection schema_version")
        if self.study_id != SCHEDULER_STUDY_ID:
            raise ValueError("task-selection study_id differs")
        _safe_identifier(self.task_id, "task_selection.task_id")
        object.__setattr__(
            self,
            "scheduled_at",
            _timestamp(self.scheduled_at, "task_selection.scheduled_at"),
        )
        if not isinstance(self.round_decision_sha256s, (list, tuple)):
            raise ValueError("task selection round identities must be a sequence")
        round_ids = tuple(
            _digest(item, f"task_selection.round_decision_sha256s[{index}]")
            for index, item in enumerate(self.round_decision_sha256s)
        )
        if not round_ids or len(round_ids) != len(set(round_ids)):
            raise ValueError("task selection requires unique nonempty round identities")
        final_round_id = _digest(
            self.final_round_decision_sha256,
            "task_selection.final_round_decision_sha256",
        )
        if round_ids[-1] != final_round_id:
            raise ValueError("task selection final round differs from its bound chain")
        _digest(self.final_task_head_sha256, "task_selection.final_task_head_sha256")
        if not isinstance(self.final_task_action_log_propensities, (list, tuple)):
            raise ValueError("task selection log propensity terms must be a sequence")
        log_terms = tuple(
            _number(item, f"task_selection.log_propensity_terms[{index}]")
            for index, item in enumerate(self.final_task_action_log_propensities)
        )
        if not log_terms:
            raise ValueError("task selection requires a nonempty action trajectory")
        log_probability = fsum(log_terms)
        probability = exp(log_probability)
        if _number(
            self.final_task_trajectory_probability,
            "task_selection.final_task_trajectory_probability",
        ) != probability:
            raise ValueError("final task probability differs from canonical action terms")
        if _number(
            self.final_task_trajectory_log_probability,
            "task_selection.final_task_trajectory_log_probability",
        ) != log_probability:
            raise ValueError("final task log probability differs from canonical action terms")
        for name in (
            "collection_policy_sha256",
            "scheduler_contract_sha256",
            "frame_manifest_sha256",
            "protocol_sha256",
        ):
            _digest(getattr(self, name), f"task_selection.{name}")
        if self.router_source_sha256 != ROUTER_SOURCE_SHA256:
            raise ValueError("task selection router source differs")
        if self.router_policy_config_sha256 != ROUTER_POLICY_CONFIG_SHA256:
            raise ValueError("task selection router policy config differs")
        order = tuple(
            _candidate_id(item, f"task_selection.candidate_order[{index}]")
            for index, item in enumerate(self.candidate_order)
        )
        if order != derive_candidate_order(order):
            raise ValueError("task-selection candidate order differs")
        if not isinstance(self.final_dispositions, (list, tuple)) or any(
            not isinstance(item, ResultingCandidateDisposition)
            for item in self.final_dispositions
        ):
            raise ValueError("task-selection final dispositions are invalid")
        dispositions = tuple(self.final_dispositions)
        if [item.candidate_id for item in dispositions] != list(order):
            raise ValueError("task-selection dispositions differ from candidate order")
        if any(item.activity == CandidateActivity.ACTIVE for item in dispositions):
            raise ValueError("task selection requires every candidate chain to terminate")
        accepted = [
            item.candidate_id
            for item in dispositions
            if item.activity == CandidateActivity.ACCEPTED
        ]
        expected_selected = accepted[0] if accepted else None
        expected_disposition = (
            TaskSelectionDisposition.SELECT_CANDIDATE
            if expected_selected is not None
            else TaskSelectionDisposition.ABSTAIN
        )
        if not isinstance(self.disposition, TaskSelectionDisposition) or (
            self.disposition != expected_disposition
        ):
            raise ValueError("task selection disposition differs")
        if self.selected_candidate_id != expected_selected:
            raise ValueError("task selection does not choose the first accepted candidate")
        expected_identity = _canonical_sha256({
            "study_id": self.study_id,
            "task_id": self.task_id,
            "round_decision_sha256s": list(round_ids),
            "final_round_decision_sha256": final_round_id,
            "final_task_head_sha256": self.final_task_head_sha256,
            "final_task_action_log_propensities": list(log_terms),
            "final_task_trajectory_probability": probability,
            "final_task_trajectory_log_probability": log_probability,
            "collection_policy_sha256": self.collection_policy_sha256,
            "scheduler_contract_sha256": self.scheduler_contract_sha256,
            "frame_manifest_sha256": self.frame_manifest_sha256,
            "protocol_sha256": self.protocol_sha256,
            "router_source_sha256": self.router_source_sha256,
            "router_policy_config_sha256": self.router_policy_config_sha256,
            "candidate_order": list(order),
            "final_dispositions": [item.to_dict() for item in dispositions],
            "disposition": expected_disposition.value,
            "selected_candidate_id": expected_selected,
        })
        if _digest(
            self.selection_identity_sha256,
            "task_selection.selection_identity_sha256",
        ) != expected_identity:
            raise ValueError("task selection identity differs")
        object.__setattr__(self, "candidate_order", order)
        object.__setattr__(self, "final_dispositions", dispositions)
        object.__setattr__(self, "round_decision_sha256s", round_ids)
        object.__setattr__(self, "final_round_decision_sha256", final_round_id)
        object.__setattr__(self, "final_task_action_log_propensities", log_terms)
        object.__setattr__(self, "final_task_trajectory_probability", probability)
        object.__setattr__(
            self,
            "final_task_trajectory_log_probability",
            log_probability,
        )
        computed = _canonical_sha256(self._payload())
        if self.decision_sha256 and _digest(
            self.decision_sha256,
            "task_selection.decision_sha256",
        ) != computed:
            raise ValueError("task-selection decision digest differs")
        object.__setattr__(self, "decision_sha256", computed)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "task_id": self.task_id,
            "scheduled_at": self.scheduled_at,
            "round_decision_sha256s": list(self.round_decision_sha256s),
            "final_round_decision_sha256": self.final_round_decision_sha256,
            "final_task_head_sha256": self.final_task_head_sha256,
            "final_task_action_log_propensities": list(
                self.final_task_action_log_propensities
            ),
            "final_task_trajectory_probability": (
                self.final_task_trajectory_probability
            ),
            "final_task_trajectory_log_probability": (
                self.final_task_trajectory_log_probability
            ),
            "collection_policy_sha256": self.collection_policy_sha256,
            "scheduler_contract_sha256": self.scheduler_contract_sha256,
            "frame_manifest_sha256": self.frame_manifest_sha256,
            "protocol_sha256": self.protocol_sha256,
            "router_source_sha256": self.router_source_sha256,
            "router_policy_config_sha256": self.router_policy_config_sha256,
            "candidate_order": list(self.candidate_order),
            "final_dispositions": [
                item.to_dict() for item in self.final_dispositions
            ],
            "disposition": self.disposition.value,
            "selected_candidate_id": self.selected_candidate_id,
            "selection_identity_sha256": self.selection_identity_sha256,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "decision_sha256": self.decision_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> TaskSelectionDecision:
        data = _object(value, "task_selection")
        fields = {
            "schema_version",
            "study_id",
            "task_id",
            "scheduled_at",
            "round_decision_sha256s",
            "final_round_decision_sha256",
            "final_task_head_sha256",
            "final_task_action_log_propensities",
            "final_task_trajectory_probability",
            "final_task_trajectory_log_probability",
            "collection_policy_sha256",
            "scheduler_contract_sha256",
            "frame_manifest_sha256",
            "protocol_sha256",
            "router_source_sha256",
            "router_policy_config_sha256",
            "candidate_order",
            "final_dispositions",
            "disposition",
            "selected_candidate_id",
            "selection_identity_sha256",
            "decision_sha256",
        }
        _exact_fields(data, fields, "task_selection")
        order = _array(data["candidate_order"], "task_selection.candidate_order")
        round_ids = _array(
            data["round_decision_sha256s"],
            "task_selection.round_decision_sha256s",
        )
        log_terms = _array(
            data["final_task_action_log_propensities"],
            "task_selection.final_task_action_log_propensities",
        )
        dispositions = _array(
            data["final_dispositions"],
            "task_selection.final_dispositions",
        )
        selected = data["selected_candidate_id"]
        if selected is not None:
            selected = _candidate_id(selected, "task_selection.selected_candidate_id")
        return cls(
            schema_version=_string(
                data["schema_version"],
                "task_selection.schema_version",
            ),
            study_id=_string(data["study_id"], "task_selection.study_id"),
            task_id=_string(data["task_id"], "task_selection.task_id"),
            scheduled_at=_timestamp(
                data["scheduled_at"],
                "task_selection.scheduled_at",
            ),
            round_decision_sha256s=tuple(
                _digest(item, f"task_selection.round_decision_sha256s[{index}]")
                for index, item in enumerate(round_ids)
            ),
            final_round_decision_sha256=_digest(
                data["final_round_decision_sha256"],
                "task_selection.final_round_decision_sha256",
            ),
            final_task_head_sha256=_digest(
                data["final_task_head_sha256"],
                "task_selection.final_task_head_sha256",
            ),
            final_task_action_log_propensities=tuple(
                _number(item, f"task_selection.log_propensity_terms[{index}]")
                for index, item in enumerate(log_terms)
            ),
            final_task_trajectory_probability=_number(
                data["final_task_trajectory_probability"],
                "task_selection.final_task_trajectory_probability",
            ),
            final_task_trajectory_log_probability=_number(
                data["final_task_trajectory_log_probability"],
                "task_selection.final_task_trajectory_log_probability",
            ),
            collection_policy_sha256=_digest(
                data["collection_policy_sha256"],
                "task_selection.collection_policy_sha256",
            ),
            scheduler_contract_sha256=_digest(
                data["scheduler_contract_sha256"],
                "task_selection.scheduler_contract_sha256",
            ),
            frame_manifest_sha256=_digest(
                data["frame_manifest_sha256"],
                "task_selection.frame_manifest_sha256",
            ),
            protocol_sha256=_digest(
                data["protocol_sha256"],
                "task_selection.protocol_sha256",
            ),
            router_source_sha256=_digest(
                data["router_source_sha256"],
                "task_selection.router_source_sha256",
            ),
            router_policy_config_sha256=_digest(
                data["router_policy_config_sha256"],
                "task_selection.router_policy_config_sha256",
            ),
            candidate_order=tuple(
                _candidate_id(item, f"task_selection.candidate_order[{index}]")
                for index, item in enumerate(order)
            ),
            final_dispositions=tuple(
                ResultingCandidateDisposition.from_dict(item, index)
                for index, item in enumerate(dispositions)
            ),
            disposition=_enum(
                TaskSelectionDisposition,
                data["disposition"],
                "task_selection.disposition",
            ),
            selected_candidate_id=cast(str | None, selected),
            selection_identity_sha256=_digest(
                data["selection_identity_sha256"],
                "task_selection.selection_identity_sha256",
            ),
            decision_sha256=_digest(
                data["decision_sha256"],
                "task_selection.decision_sha256",
            ),
        )


def build_task_selection_decision(
    rounds: Sequence[TaskRoundDecision],
    *,
    bindings: SchedulerBindings,
    scheduled_at: str,
) -> TaskSelectionDecision:
    if not isinstance(rounds, (list, tuple)) or any(
        not isinstance(item, TaskRoundDecision) for item in rounds
    ):
        raise ValueError("rounds must contain a complete TaskRoundDecision chain")
    chain = tuple(rounds)
    validate_task_round_chain(chain, bindings=bindings)
    final_round = chain[-1]
    if not final_round.completes_candidate_chains:
        raise ValueError("task selection requires a completed candidate-round trajectory")
    selection_time = _timestamp(scheduled_at, "task_selection.scheduled_at")
    if selection_time < final_round.scheduled_at:
        raise ValueError("task selection cannot predate the final task round")
    accepted = [
        item.candidate_id
        for item in final_round.resulting_dispositions
        if item.activity == CandidateActivity.ACCEPTED
    ]
    selected = accepted[0] if accepted else None
    disposition = (
        TaskSelectionDisposition.SELECT_CANDIDATE
        if selected is not None
        else TaskSelectionDisposition.ABSTAIN
    )
    identity = _canonical_sha256({
        "study_id": SCHEDULER_STUDY_ID,
        "task_id": final_round.task_id,
        "round_decision_sha256s": [item.decision_sha256 for item in chain],
        "final_round_decision_sha256": final_round.decision_sha256,
        "final_task_head_sha256": final_round.task_head_sha256,
        "final_task_action_log_propensities": list(
            final_round.task_trajectory_action_log_propensities
        ),
        "final_task_trajectory_probability": (
            final_round.task_trajectory_probability
        ),
        "final_task_trajectory_log_probability": (
            final_round.task_trajectory_log_probability
        ),
        "collection_policy_sha256": bindings.collection_policy_sha256,
        "scheduler_contract_sha256": bindings.scheduler_contract_sha256,
        "frame_manifest_sha256": bindings.frame.manifest_sha256,
        "protocol_sha256": bindings.protocol_sha256,
        "router_source_sha256": bindings.router_source_sha256,
        "router_policy_config_sha256": bindings.router_policy_config_sha256,
        "candidate_order": list(final_round.candidate_order),
        "final_dispositions": [
            item.to_dict() for item in final_round.resulting_dispositions
        ],
        "disposition": disposition.value,
        "selected_candidate_id": selected,
    })
    result = TaskSelectionDecision(
        task_id=final_round.task_id,
        scheduled_at=selection_time,
        round_decision_sha256s=tuple(item.decision_sha256 for item in chain),
        final_round_decision_sha256=final_round.decision_sha256,
        final_task_head_sha256=final_round.task_head_sha256,
        final_task_action_log_propensities=(
            final_round.task_trajectory_action_log_propensities
        ),
        final_task_trajectory_probability=final_round.task_trajectory_probability,
        final_task_trajectory_log_probability=(
            final_round.task_trajectory_log_probability
        ),
        collection_policy_sha256=bindings.collection_policy_sha256,
        scheduler_contract_sha256=bindings.scheduler_contract_sha256,
        frame_manifest_sha256=bindings.frame.manifest_sha256,
        protocol_sha256=bindings.protocol_sha256,
        router_source_sha256=bindings.router_source_sha256,
        router_policy_config_sha256=bindings.router_policy_config_sha256,
        candidate_order=final_round.candidate_order,
        final_dispositions=final_round.resulting_dispositions,
        disposition=disposition,
        selected_candidate_id=selected,
        selection_identity_sha256=identity,
    )
    validate_task_trajectory(chain, result, bindings=bindings)
    return result


def validate_task_trajectory(
    rounds: Sequence[TaskRoundDecision],
    selection: TaskSelectionDecision,
    *,
    bindings: SchedulerBindings,
) -> None:
    """Validate one genesis-rooted task chain and its terminal selection."""

    validate_task_round_chain(rounds, bindings=bindings)
    if not isinstance(selection, TaskSelectionDecision):
        raise ValueError("selection must be a TaskSelectionDecision")
    final_round = rounds[-1]
    if not final_round.completes_candidate_chains:
        raise ValueError("task trajectory is incomplete")
    if selection.scheduled_at < final_round.scheduled_at:
        raise ValueError("task selection predates its final round")
    expected = {
        "task_id": final_round.task_id,
        "round_decision_sha256s": tuple(item.decision_sha256 for item in rounds),
        "final_round_decision_sha256": final_round.decision_sha256,
        "final_task_head_sha256": final_round.task_head_sha256,
        "final_task_action_log_propensities": (
            final_round.task_trajectory_action_log_propensities
        ),
        "final_task_trajectory_probability": final_round.task_trajectory_probability,
        "final_task_trajectory_log_probability": (
            final_round.task_trajectory_log_probability
        ),
        "collection_policy_sha256": bindings.collection_policy_sha256,
        "scheduler_contract_sha256": bindings.scheduler_contract_sha256,
        "frame_manifest_sha256": bindings.frame.manifest_sha256,
        "protocol_sha256": bindings.protocol_sha256,
        "router_source_sha256": bindings.router_source_sha256,
        "router_policy_config_sha256": bindings.router_policy_config_sha256,
        "candidate_order": final_round.candidate_order,
        "final_dispositions": final_round.resulting_dispositions,
    }
    for name, value in expected.items():
        if getattr(selection, name) != value:
            raise ValueError(f"task selection {name} differs from its validated chain")


def load_task_selection_decision(
    stream: TextIO,
    *,
    rounds: Sequence[TaskRoundDecision],
    bindings: SchedulerBindings,
) -> TaskSelectionDecision:
    try:
        value = strict_json_load(stream)
    except ValueError as exc:
        raise ValueError(f"invalid task-selection JSON: {exc}") from exc
    result = TaskSelectionDecision.from_dict(value)
    validate_task_trajectory(rounds, result, bindings=bindings)
    return result


def validate_complete_study_ledger(
    rounds: Sequence[TaskRoundDecision],
    selections: Sequence[TaskSelectionDecision],
    *,
    bindings: SchedulerBindings,
) -> None:
    """Reject forks/replays/counter reuse in one complete in-memory study ledger.

    This validation does not provide the durable exclusive write-ahead commit
    needed for operational activation; that remains an explicit protocol blocker.
    """

    if not isinstance(rounds, (list, tuple)) or any(
        not isinstance(item, TaskRoundDecision) for item in rounds
    ):
        raise ValueError("study ledger rounds are invalid")
    if not isinstance(selections, (list, tuple)) or any(
        not isinstance(item, TaskSelectionDecision) for item in selections
    ):
        raise ValueError("study ledger selections are invalid")
    by_task: dict[str, list[TaskRoundDecision]] = {}
    round_keys: set[tuple[str, int]] = set()
    successor_keys: set[tuple[str, str]] = set()
    counters: set[int] = set()
    round_decision_ids: set[str] = set()
    for item in rounds:
        item.validate_against_bindings(bindings)
        key = (item.task_id, item.round_index)
        if key in round_keys:
            raise ValueError("study ledger contains a replay or task-round fork")
        round_keys.add(key)
        successor_key = (item.task_id, item.prior_task_head_sha256)
        if successor_key in successor_keys:
            raise ValueError("study ledger contains two successors for one task head")
        successor_keys.add(successor_key)
        if item.decision_sha256 in round_decision_ids:
            raise ValueError("study ledger repeats a round decision identity")
        round_decision_ids.add(item.decision_sha256)
        for decision in item.scheduled_decisions:
            if decision.action_draw_counter in counters:
                raise ValueError("study ledger reuses a reserved action-draw counter")
            counters.add(decision.action_draw_counter)
        by_task.setdefault(item.task_id, []).append(item)
    expected_tasks = set(bindings.frame.task_ids)
    if set(by_task) != expected_tasks:
        raise ValueError("complete study ledger differs from the exact frozen task frame")
    selection_by_task: dict[str, TaskSelectionDecision] = {}
    selection_ids: set[str] = set()
    for selection in selections:
        if selection.task_id in selection_by_task:
            raise ValueError("study ledger contains multiple task selections")
        if selection.decision_sha256 in selection_ids:
            raise ValueError("study ledger repeats a task-selection identity")
        selection_by_task[selection.task_id] = selection
        selection_ids.add(selection.decision_sha256)
    if set(selection_by_task) != expected_tasks:
        raise ValueError("complete study ledger requires exactly one selection per task")
    for task_id in bindings.frame.task_ids:
        chain = tuple(sorted(by_task[task_id], key=lambda item: item.round_index))
        validate_task_trajectory(
            chain,
            selection_by_task[task_id],
            bindings=bindings,
        )
