"""Data models for trajectory validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bench_cleanser.models import AgentTrajectoryLabel


def _text(value: Any) -> str:
    """Normalize structured tool payloads without Python repr instability."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _outcome(value: Any, field_name: str) -> bool:
    """Normalize common serialized booleans without truthiness mistakes."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError(f"{field_name} must be a boolean, got {value!r}")


def _canonical_outcome(data: dict[str, Any]) -> bool:
    """Return one observed outcome without turning missing data into failure."""

    supplied: list[tuple[str, bool]] = []
    for field_name in ("resolved", "passed_tests"):
        if field_name in data:
            supplied.append((field_name, _outcome(data[field_name], field_name)))
    if not supplied:
        raise ValueError("trajectory outcome is required (resolved or passed_tests)")
    if len({value for _, value in supplied}) != 1:
        raise ValueError("resolved and passed_tests contradict each other")
    return supplied[0][1]


def _nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value)
    else:
        raise ValueError(f"{field_name} must be a non-negative integer")
    if result < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return result


class LeakagePattern(str, Enum):
    """Classification of how an agent arrived at its solution."""
    GENUINE_SOLUTION = "GENUINE_SOLUTION"      # Derived from problem statement
    GOLD_PATCH_LEAK = "GOLD_PATCH_LEAK"        # Direct evidence of prohibited gold access/use
    PACKAGE_LEAK = "PACKAGE_LEAK"              # Solution installed from PyPI/package
    TEST_AWARE = "TEST_AWARE"                  # References F2P test names/values
    PARTIAL_MATCH = "PARTIAL_MATCH"            # Some leakage signals, inconclusive
    UNKNOWN = "UNKNOWN"                        # Not enough data to classify


class ActionType(str, Enum):
    """Types of actions in an agent trajectory."""
    EDIT = "EDIT"
    TERMINAL = "TERMINAL"
    BROWSE = "BROWSE"
    THINK = "THINK"
    SEARCH = "SEARCH"
    READ = "READ"
    WRITE = "WRITE"
    OTHER = "OTHER"


@dataclass
class TrajectoryAction:
    """A single action taken by an agent during its trajectory."""
    action_type: ActionType
    content: str
    file_path: str = ""
    timestamp: str = ""
    observation: str = ""
    role: str = ""
    tool_name: str = ""
    tool_call_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryAction:
        if not isinstance(data, dict):
            raise ValueError("trajectory action must be an object")
        action_type_str = data.get("action_type", data.get("type", "OTHER"))
        try:
            action_type = ActionType(_text(action_type_str).upper())
        except (TypeError, ValueError):
            action_type = ActionType.OTHER
        return cls(
            action_type=action_type,
            content=_text(data.get("content", data.get("command", ""))),
            file_path=_text(data.get("file_path", data.get("path", ""))),
            timestamp=_text(data.get("timestamp", "")),
            observation=_text(data.get("observation", data.get("output", ""))),
            role=_text(data.get("role", "")),
            tool_name=_text(data.get("tool_name", data.get("function", ""))),
            tool_call_id=_text(
                data.get("tool_call_id", data.get("tool_use_id", data.get("id", "")))
            ),
        )


@dataclass
class TrajectoryRecord:
    """Complete trajectory for a single agent on a single task."""
    instance_id: str
    agent_name: str
    actions: list[TrajectoryAction]
    final_patch: str = ""
    passed_tests: bool = False
    resolved: bool = False
    model_name: str = ""
    total_tokens: int = 0
    turn_count: int = 0
    raw_messages: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryRecord:
        if not isinstance(data, dict):
            raise ValueError("trajectory record must be an object")
        instance_id = _text(data.get("instance_id", "")).strip()
        if not instance_id:
            raise ValueError("trajectory instance_id is required")
        raw_actions = data.get("actions", data.get("trajectory", []))
        if raw_actions is None:
            raw_actions = []
        if not isinstance(raw_actions, list):
            raise ValueError("trajectory actions must be an array")
        actions = [
            a if isinstance(a, TrajectoryAction) else TrajectoryAction.from_dict(a)
            for a in raw_actions
        ]
        # Only observed outcomes enter Stage 7. ``passed_tests`` is accepted
        # as an alias, while missing or contradictory aliases are rejected.
        resolved = _canonical_outcome(data)
        raw_messages = data.get("raw_messages", data.get("messages", []))
        if raw_messages is None:
            raw_messages = []
        if not isinstance(raw_messages, list) or any(
            not isinstance(message, dict) for message in raw_messages
        ):
            raise ValueError("raw_messages must be an array of objects")
        return cls(
            instance_id=instance_id,
            agent_name=_text(data.get("agent_name", data.get("model_name_or_path", ""))),
            actions=actions,
            final_patch=_text(data.get("final_patch", data.get("model_patch", ""))),
            passed_tests=resolved,
            resolved=resolved,
            model_name=_text(data.get("model_name", data.get("model_name_or_path", ""))),
            total_tokens=_nonnegative_int(
                data.get("total_tokens", data.get("token_count", 0)),
                "total_tokens",
            ),
            turn_count=_nonnegative_int(
                data.get("turn_count", data.get("num_turns", 0)),
                "turn_count",
            ),
            raw_messages=list(raw_messages),
        )


@dataclass
class TrajectoryAnalysis:
    """Analysis result for a single trajectory."""
    instance_id: str
    agent_name: str
    leakage_pattern: LeakagePattern
    evidence_strength: str = "moderate"
    evidence: list[str] = field(default_factory=list)
    gold_patch_similarity: float = 0.0          # 0-1, difflib ratio
    pip_install_commands: list[str] = field(default_factory=list)
    test_references: list[str] = field(default_factory=list)
    llm_reasoning: str = ""                     # LLM's detailed reasoning
    causal_chain: str = ""                      # What led the agent to its approach
    agent_behavior_summary: str = ""            # Brief characterization of agent behavior
    trajectory_label: AgentTrajectoryLabel | None = None
    # The agent's reported outcome on the F2P tests — propagated from the
    # source TrajectoryRecord. Stage 7 fusion needs it to distinguish
    # AMBIGUOUS_PASS (passed with UNKNOWN trajectory) from a failed-and-
    # uncharacterised attempt.
    resolved: bool = False

    @property
    def agent_trajectory_label(self) -> AgentTrajectoryLabel:
        """Return an outcome-consistent trajectory label.

        ``passed_*`` labels cannot be inferred for a failed rollout.  Treat a
        contradictory explicit LLM label as unknown rather than allowing it
        to flow into a FAIR_PASS/AGENT_CHEATED fusion verdict.
        """
        if self.trajectory_label is not None:
            passed_labels = {
                AgentTrajectoryLabel.AGENT_PASSED_GENUINE,
                AgentTrajectoryLabel.AGENT_PASSED_LEAK,
                AgentTrajectoryLabel.AGENT_PASSED_PACKAGE_LEAK,
                AgentTrajectoryLabel.AGENT_PASSED_TEST_AWARE,
                AgentTrajectoryLabel.AGENT_PASSED_TRAINED_HACK,
            }
            failed_labels = {
                AgentTrajectoryLabel.AGENT_FAILED_COMPLETED_INTENT,
                AgentTrajectoryLabel.AGENT_FAILED_NO_INTENT,
            }
            if self.trajectory_label in passed_labels and not self.resolved:
                return AgentTrajectoryLabel.AGENT_UNKNOWN
            if self.trajectory_label in failed_labels and self.resolved:
                return AgentTrajectoryLabel.AGENT_UNKNOWN
            return self.trajectory_label
        if not self.resolved:
            return AgentTrajectoryLabel.AGENT_UNKNOWN
        _map = {
            LeakagePattern.GENUINE_SOLUTION: AgentTrajectoryLabel.AGENT_PASSED_GENUINE,
            LeakagePattern.GOLD_PATCH_LEAK: AgentTrajectoryLabel.AGENT_PASSED_LEAK,
            LeakagePattern.PACKAGE_LEAK: AgentTrajectoryLabel.AGENT_PASSED_PACKAGE_LEAK,
            LeakagePattern.TEST_AWARE: AgentTrajectoryLabel.AGENT_PASSED_TEST_AWARE,
            LeakagePattern.PARTIAL_MATCH: AgentTrajectoryLabel.AGENT_UNKNOWN,
            LeakagePattern.UNKNOWN: AgentTrajectoryLabel.AGENT_UNKNOWN,
        }
        return _map.get(self.leakage_pattern, AgentTrajectoryLabel.AGENT_UNKNOWN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "agent_name": self.agent_name,
            "leakage_pattern": self.leakage_pattern.value,
            "trajectory_label": self.agent_trajectory_label.value,
            "evidence_strength": self.evidence_strength,
            "evidence": self.evidence,
            "gold_patch_similarity": round(self.gold_patch_similarity, 4),
            "pip_install_commands": self.pip_install_commands,
            "test_references": self.test_references,
            "llm_reasoning": self.llm_reasoning,
            "causal_chain": self.causal_chain,
            "agent_behavior_summary": self.agent_behavior_summary,
            "resolved": self.resolved,
        }
