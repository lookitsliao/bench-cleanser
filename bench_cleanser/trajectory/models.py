"""Data models for trajectory validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LeakagePattern(str, Enum):
    """Classification of how an agent arrived at its solution."""
    GENUINE_SOLUTION = "GENUINE_SOLUTION"      # Derived from problem statement
    GOLD_PATCH_LEAK = "GOLD_PATCH_LEAK"        # Patch matches gold patch too closely
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryAction:
        action_type_str = data.get("action_type", data.get("type", "OTHER"))
        try:
            action_type = ActionType(action_type_str.upper())
        except ValueError:
            action_type = ActionType.OTHER
        return cls(
            action_type=action_type,
            content=data.get("content", data.get("command", "")),
            file_path=data.get("file_path", data.get("path", "")),
            timestamp=data.get("timestamp", ""),
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryRecord:
        actions = [
            TrajectoryAction.from_dict(a)
            for a in data.get("actions", data.get("trajectory", []))
        ]
        return cls(
            instance_id=data.get("instance_id", ""),
            agent_name=data.get("agent_name", data.get("model_name_or_path", "")),
            actions=actions,
            final_patch=data.get("final_patch", data.get("model_patch", "")),
            passed_tests=data.get("passed_tests", data.get("resolved", False)),
            resolved=data.get("resolved", False),
            model_name=data.get("model_name", data.get("model_name_or_path", "")),
        )


@dataclass
class TrajectoryAnalysis:
    """Analysis result for a single trajectory."""
    instance_id: str
    agent_name: str
    leakage_pattern: LeakagePattern
    confidence: float                           # 0-1
    evidence: list[str] = field(default_factory=list)
    gold_patch_similarity: float = 0.0          # 0-1, difflib ratio
    pip_install_commands: list[str] = field(default_factory=list)
    test_references: list[str] = field(default_factory=list)
    llm_reasoning: str = ""                     # LLM's detailed reasoning
    causal_chain: str = ""                      # What led the agent to its approach
    agent_behavior_summary: str = ""            # Brief characterization of agent behavior

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "agent_name": self.agent_name,
            "leakage_pattern": self.leakage_pattern.value,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "gold_patch_similarity": round(self.gold_patch_similarity, 4),
            "pip_install_commands": self.pip_install_commands,
            "test_references": self.test_references,
            "llm_reasoning": self.llm_reasoning,
            "causal_chain": self.causal_chain,
            "agent_behavior_summary": self.agent_behavior_summary,
        }
