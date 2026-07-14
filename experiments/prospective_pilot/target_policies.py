"""Frozen truth-free target policies for prospective-pilot diagnostics.

The functions in this module consume only scheduler-validated pre-action state,
available-action catalogs, and logged behavior propensities.  They never consume
adjudication, hosted outcomes, rewards, or later evidence.  The resulting
importance weights are descriptive/OPE inputs; they are not policy-performance
claims and are omitted by the analysis layer when support or effective-sample-
size requirements fail.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from math import exp, fsum, isclose, isfinite, log
from typing import Any

from bench_cleanser.verification._io import strict_json_dumps
from experiments.prospective_pilot.scheduler import (
    EXPLORATION_MASS,
    CandidateActionDecision,
    CandidateRoundState,
    SchedulerBindings,
    TaskRoundDecision,
    TaskSelectionDecision,
    validate_task_trajectory,
)

TARGET_POLICY_SCHEMA_VERSION = "prospective-pilot-target-policy-trace-0.1.0"
TARGET_POLICY_MANIFEST_SCHEMA_VERSION = (
    "prospective-pilot-target-policy-manifest-0.1.0"
)
TARGET_POLICY_IMPLEMENTATION_LOGICAL_PATH = (
    "experiments/prospective_pilot/target_policies.py"
)
TARGET_POLICY_MANIFEST_LOGICAL_PATH = (
    "experiments/prospective_pilot/target_policy_manifest.json"
)

_PROBABILITY_TOLERANCE = 1e-12
_TERMINAL_ACTION_IDS = frozenset({"abstain", "accept", "reject"})


class TargetPolicyId(str, Enum):
    BEHAVIOR_MIXTURE = "behavior-mixture-v1"
    ALWAYS_FULL_REPEAT = "always-full-repeat-v1"
    STATIC_TARGETED_FULL = "static-targeted-full-v1"
    CONSERVATIVE_PREFERRED = "conservative-v1-preferred-v1"
    SEMANTIC_ONLY = "semantic-only-v1"
    HASH_PRIORITY_NO_RUNTIME = "hash-priority-no-runtime-v1"


TARGET_POLICY_RULES: Mapping[TargetPolicyId, tuple[str, bool]] = {
    TargetPolicyId.BEHAVIOR_MIXTURE: (
        "the_exact_logged_0.5_preferred_plus_0.5_uniform_behavior_policy",
        True,
    ),
    TargetPolicyId.ALWAYS_FULL_REPEAT: (
        "full_execution_then_fresh_worktree_repeat_then_frozen_terminal_rule_for_every_candidate",
        False,
    ),
    TargetPolicyId.STATIC_TARGETED_FULL: (
        "deterministic_static_then_targeted_then_full_then_repeat_then_frozen_terminal_rule",
        False,
    ),
    TargetPolicyId.CONSERVATIVE_PREFERRED: (
        "follow_the_bound_conservative_v1_preferred_action_with_no_exploration",
        True,
    ),
    TargetPolicyId.SEMANTIC_ONLY: (
        "semantic_once_then_the_frozen_terminal_rule_without_runtime_evidence",
        True,
    ),
    TargetPolicyId.HASH_PRIORITY_NO_RUNTIME: (
        "select_the_first_candidate_in_frozen_opaque_candidate_order_without_runtime_evidence",
        False,
    ),
}


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(strict_json_dumps(value).encode("utf-8")).hexdigest()


def _policy_id(value: TargetPolicyId | str) -> TargetPolicyId:
    if isinstance(value, TargetPolicyId):
        return value
    if not isinstance(value, str):
        raise ValueError("target policy ID must be a string or TargetPolicyId")
    try:
        return TargetPolicyId(value)
    except ValueError as exc:
        raise ValueError(f"unknown target policy {value!r}") from exc


@dataclass(frozen=True)
class TargetProbability:
    action_id: str
    probability: float

    def __post_init__(self) -> None:
        if not isinstance(self.action_id, str) or not self.action_id:
            raise ValueError("target action ID must be a non-empty string")
        if (
            isinstance(self.probability, bool)
            or not isinstance(self.probability, (int, float))
            or not isfinite(float(self.probability))
            or not 0.0 <= float(self.probability) <= 1.0
        ):
            raise ValueError("target action probability must be finite in [0, 1]")
        object.__setattr__(self, "probability", float(self.probability))

    def to_dict(self) -> dict[str, Any]:
        return {"action_id": self.action_id, "probability": self.probability}


@dataclass(frozen=True)
class TargetDistribution:
    policy_id: TargetPolicyId
    probabilities: tuple[TargetProbability, ...]
    positive_actions_outside_behavior_support: tuple[str, ...]
    desired_action_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, TargetPolicyId):
            raise ValueError("target distribution policy ID is invalid")
        if not isinstance(self.probabilities, (list, tuple)) or any(
            not isinstance(item, TargetProbability) for item in self.probabilities
        ):
            raise ValueError("target distribution probabilities are invalid")
        probabilities = tuple(self.probabilities)
        action_ids = [item.action_id for item in probabilities]
        if action_ids != sorted(action_ids) or len(action_ids) != len(set(action_ids)):
            raise ValueError("target distribution action IDs must be sorted and unique")
        if not isclose(
            fsum(item.probability for item in probabilities),
            1.0,
            rel_tol=0.0,
            abs_tol=_PROBABILITY_TOLERANCE,
        ):
            raise ValueError("target distribution must sum to one")
        outside = tuple(self.positive_actions_outside_behavior_support)
        if list(outside) != sorted(outside) or len(outside) != len(set(outside)):
            raise ValueError("target support violations must be sorted and unique")
        positive = {
            item.action_id for item in probabilities if item.probability > 0.0
        }
        if not set(outside).issubset(positive):
            raise ValueError("support violation must have positive target probability")
        if self.desired_action_id is not None and self.desired_action_id not in action_ids:
            raise ValueError("desired action is absent from target distribution")
        object.__setattr__(self, "probabilities", probabilities)
        object.__setattr__(self, "positive_actions_outside_behavior_support", outside)

    def probability(self, action_id: str) -> float:
        for item in self.probabilities:
            if item.action_id == action_id:
                return item.probability
        raise ValueError(f"action {action_id!r} is absent from target distribution")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id.value,
            "probabilities": [item.to_dict() for item in self.probabilities],
            "positive_actions_outside_behavior_support": list(
                self.positive_actions_outside_behavior_support
            ),
            "desired_action_id": self.desired_action_id,
        }


def _available_action_ids(state: CandidateRoundState) -> tuple[str, ...]:
    return tuple(
        item.action_id for item in state.action_catalog if item.available
    )


def _terminal_action(state: CandidateRoundState) -> str:
    preferred = state.preferred_action_id
    available = set(_available_action_ids(state))
    if preferred in _TERMINAL_ACTION_IDS and preferred in available:
        return preferred
    return "abstain"


def _desired_action(
    policy_id: TargetPolicyId,
    state: CandidateRoundState,
    *,
    candidate_position: int,
) -> str:
    completed = set(state.completed_nonterminal_action_ids)
    if policy_id == TargetPolicyId.CONSERVATIVE_PREFERRED:
        if state.preferred_action_id is None:
            raise ValueError("active candidate is missing its preferred action")
        return state.preferred_action_id
    if policy_id == TargetPolicyId.ALWAYS_FULL_REPEAT:
        if "full_primary" not in completed:
            return "full_primary"
        if "full_repeat" not in completed:
            return "full_repeat"
        return _terminal_action(state)
    if policy_id == TargetPolicyId.STATIC_TARGETED_FULL:
        if "targeted_primary" not in completed:
            return "targeted_primary"
        if "full_primary" not in completed:
            return "full_primary"
        if "full_repeat" not in completed:
            return "full_repeat"
        return _terminal_action(state)
    if policy_id == TargetPolicyId.SEMANTIC_ONLY:
        if "semantic_primary" not in completed:
            return "semantic_primary"
        return _terminal_action(state)
    if policy_id == TargetPolicyId.HASH_PRIORITY_NO_RUNTIME:
        if state.decision_count == 0 and candidate_position == 0:
            return "accept"
        return "abstain"
    raise ValueError(f"policy {policy_id.value!r} has no deterministic rule")


def target_distribution(
    policy_id: TargetPolicyId | str,
    state: CandidateRoundState,
    *,
    candidate_position: int,
) -> TargetDistribution:
    """Return a frozen target distribution for one scheduler pre-action state."""

    policy = _policy_id(policy_id)
    if not isinstance(state, CandidateRoundState):
        raise ValueError("target policy requires CandidateRoundState")
    if isinstance(candidate_position, bool) or not isinstance(candidate_position, int):
        raise ValueError("candidate position must be an integer")
    if not 0 <= candidate_position < 3:
        raise ValueError("candidate position must be in [0, 3)")
    catalog_ids = tuple(item.action_id for item in state.action_catalog)
    available = set(_available_action_ids(state))
    if policy == TargetPolicyId.BEHAVIOR_MIXTURE:
        preferred = state.preferred_action_id
        if preferred is None or preferred not in available:
            raise ValueError("behavior target requires an available preferred action")
        uniform = EXPLORATION_MASS / len(available)
        probabilities = tuple(
            TargetProbability(
                action_id,
                (uniform + (1.0 - EXPLORATION_MASS))
                if action_id == preferred
                else uniform if action_id in available else 0.0,
            )
            for action_id in catalog_ids
        )
        return TargetDistribution(policy, probabilities, (), preferred)
    desired = _desired_action(
        policy,
        state,
        candidate_position=candidate_position,
    )
    if desired not in catalog_ids:
        raise ValueError("target policy requested an action outside the frozen catalog")
    probabilities = tuple(
        TargetProbability(action_id, float(action_id == desired))
        for action_id in catalog_ids
    )
    outside = () if desired in available else (desired,)
    return TargetDistribution(policy, probabilities, outside, desired)


@dataclass(frozen=True)
class TargetPolicyStep:
    round_index: int
    candidate_id: str
    candidate_position: int
    state_sha256: str
    selection_identity_sha256: str
    chosen_action_id: str
    behavior_probability: float
    target_probability: float
    log_importance_ratio: float | None
    distribution: TargetDistribution

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "candidate_id": self.candidate_id,
            "candidate_position": self.candidate_position,
            "state_sha256": self.state_sha256,
            "selection_identity_sha256": self.selection_identity_sha256,
            "chosen_action_id": self.chosen_action_id,
            "behavior_probability": self.behavior_probability,
            "target_probability": self.target_probability,
            "log_importance_ratio": self.log_importance_ratio,
            "distribution": self.distribution.to_dict(),
        }


@dataclass(frozen=True)
class TargetPolicyTrace:
    task_id: str
    policy_id: TargetPolicyId
    task_selection_sha256: str
    steps: tuple[TargetPolicyStep, ...]
    support_violation_actions: tuple[str, ...]
    target_trajectory_probability: float
    behavior_trajectory_probability: float
    importance_weight: float | None
    trace_sha256: str
    schema_version: str = TARGET_POLICY_SCHEMA_VERSION

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "policy_id": self.policy_id.value,
            "task_selection_sha256": self.task_selection_sha256,
            "steps": [item.to_dict() for item in self.steps],
            "support_violation_actions": list(self.support_violation_actions),
            "target_trajectory_probability": self.target_trajectory_probability,
            "behavior_trajectory_probability": self.behavior_trajectory_probability,
            "importance_weight": self.importance_weight,
        }

    def __post_init__(self) -> None:
        if self.schema_version != TARGET_POLICY_SCHEMA_VERSION:
            raise ValueError("target trace schema version differs")
        if not isinstance(self.policy_id, TargetPolicyId):
            raise ValueError("target trace policy ID is invalid")
        if not isinstance(self.steps, (list, tuple)) or not self.steps:
            raise ValueError("target trace requires at least one policy step")
        if any(not isinstance(item, TargetPolicyStep) for item in self.steps):
            raise ValueError("target trace steps are invalid")
        violations = tuple(self.support_violation_actions)
        if list(violations) != sorted(violations) or len(violations) != len(set(violations)):
            raise ValueError("target trace support violations must be sorted and unique")
        for name in (
            "target_trajectory_probability",
            "behavior_trajectory_probability",
        ):
            value = getattr(self, name)
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite in [0, 1]")
        if self.importance_weight is not None and (
            not isfinite(self.importance_weight) or self.importance_weight < 0.0
        ):
            raise ValueError("importance weight must be finite and nonnegative")
        if violations and self.importance_weight is not None:
            raise ValueError("support-violating target trace cannot expose a weight")
        computed = _canonical_sha256(self._payload())
        if self.trace_sha256 and self.trace_sha256 != computed:
            raise ValueError("target trace digest differs")
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "support_violation_actions", violations)
        object.__setattr__(self, "trace_sha256", computed)

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "trace_sha256": self.trace_sha256}


def _step(
    policy_id: TargetPolicyId,
    state: CandidateRoundState,
    decision: CandidateActionDecision,
    *,
    round_index: int,
) -> TargetPolicyStep:
    distribution = target_distribution(
        policy_id,
        state,
        candidate_position=decision.candidate_position,
    )
    target_probability = distribution.probability(decision.chosen_action_id)
    ratio = (
        log(target_probability) - decision.chosen_log_action_propensity
        if target_probability > 0.0
        else None
    )
    return TargetPolicyStep(
        round_index=round_index,
        candidate_id=decision.candidate_id,
        candidate_position=decision.candidate_position,
        state_sha256=decision.state_sha256,
        selection_identity_sha256=decision.selection_identity_sha256,
        chosen_action_id=decision.chosen_action_id,
        behavior_probability=decision.chosen_action_propensity,
        target_probability=target_probability,
        log_importance_ratio=ratio,
        distribution=distribution,
    )


def evaluate_target_policy(
    policy_id: TargetPolicyId | str,
    rounds: Sequence[TaskRoundDecision],
    selection: TaskSelectionDecision,
    *,
    bindings: SchedulerBindings,
) -> TargetPolicyTrace:
    """Evaluate one target policy on a complete validated behavior trajectory."""

    policy = _policy_id(policy_id)
    validate_task_trajectory(rounds, selection, bindings=bindings)
    steps: list[TargetPolicyStep] = []
    violations: set[str] = set()
    for round_decision in rounds:
        states = {item.candidate_id: item for item in round_decision.candidates}
        for decision in round_decision.scheduled_decisions:
            state = states[decision.candidate_id]
            item = _step(
                policy,
                state,
                decision,
                round_index=round_decision.round_index,
            )
            steps.append(item)
            violations.update(
                item.distribution.positive_actions_outside_behavior_support
            )
    if not steps:
        raise ValueError("target policy cannot evaluate an empty trajectory")
    target_zero = any(item.target_probability == 0.0 for item in steps)
    target_probability = (
        0.0
        if target_zero
        else exp(fsum(log(item.target_probability) for item in steps))
    )
    behavior_log_probability = fsum(
        log(item.behavior_probability) for item in steps
    )
    behavior_probability = exp(behavior_log_probability)
    if (
        behavior_log_probability
        != selection.final_task_trajectory_log_probability
        or behavior_probability != selection.final_task_trajectory_probability
    ):
        raise ValueError("target-policy traversal differs from the bound task propensity")
    if violations:
        weight: float | None = None
    elif target_zero:
        weight = 0.0
    else:
        weight = exp(
            fsum(
                item.log_importance_ratio
                for item in steps
                if item.log_importance_ratio is not None
            )
        )
    return TargetPolicyTrace(
        task_id=selection.task_id,
        policy_id=policy,
        task_selection_sha256=selection.decision_sha256,
        steps=tuple(steps),
        support_violation_actions=tuple(sorted(violations)),
        target_trajectory_probability=target_probability,
        behavior_trajectory_probability=behavior_probability,
        importance_weight=weight,
        trace_sha256="",
    )


def evaluate_all_target_policies(
    rounds: Sequence[TaskRoundDecision],
    selection: TaskSelectionDecision,
    *,
    bindings: SchedulerBindings,
) -> tuple[TargetPolicyTrace, ...]:
    return tuple(
        evaluate_target_policy(policy_id, rounds, selection, bindings=bindings)
        for policy_id in TargetPolicyId
    )
