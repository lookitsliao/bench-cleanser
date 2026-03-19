"""Core data models for the bench-cleanser pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PatchVerdict(str, Enum):
    REQUIRED = "REQUIRED"
    ANCILLARY = "ANCILLARY"
    UNRELATED = "UNRELATED"


class TestVerdict(str, Enum):
    ALIGNED = "ALIGNED"
    TANGENTIAL = "TANGENTIAL"
    UNRELATED = "UNRELATED"


class AssertionVerdict(str, Enum):
    ON_TOPIC = "ON_TOPIC"
    OFF_TOPIC = "OFF_TOPIC"


class Severity(str, Enum):
    CLEAN = "CLEAN"
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class TaskContaminationLabel(str, Enum):
    """Axis 1: task-level contamination labels (8 binary labels).

    Labels 1-7 are contamination signals (multi-label, co-occur freely).
    CLEAN is exclusive — cannot co-occur with any other label.
    """
    APPROACH_LOCK = "approach_lock"
    EXCESS_TESTS = "excess_tests"
    SNEAKY_EDIT = "sneaky_edit"
    EXCESS_PATCH = "excess_patch"
    UNCLEAR_SPEC = "unclear_spec"
    HIDDEN_CONTEXT = "hidden_context"
    UNDERSPEC = "underspec"
    CLEAN = "clean"


class AgentTrajectoryLabel(str, Enum):
    """Axis 2: per-agent-task trajectory classification."""
    AGENT_PASSED_GENUINE = "agent_passed_genuine"
    AGENT_PASSED_LEAK = "agent_passed_leak"
    AGENT_PASSED_PACKAGE_LEAK = "agent_passed_package_leak"
    AGENT_PASSED_TEST_AWARE = "agent_passed_test_aware"
    AGENT_PASSED_TRAINED_HACK = "agent_passed_trained_hack"
    AGENT_FAILED_COMPLETED_INTENT = "agent_failed_completed_intent"
    AGENT_FAILED_NO_INTENT = "agent_failed_no_intent"
    AGENT_UNKNOWN = "agent_unknown"


class TestModificationType(str, Enum):
    NEW = "NEW"
    MODIFIED = "MODIFIED"
    UNKNOWN = "UNKNOWN"


@dataclass
class TaskRecord:
    """Raw SWE-bench task record."""
    instance_id: str
    repo: str
    base_commit: str
    patch: str
    test_patch: str
    problem_statement: str
    hints_text: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    version: str
    environment_setup_commit: str = ""
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        f2p = data.get("FAIL_TO_PASS", "[]")
        p2p = data.get("PASS_TO_PASS", "[]")
        if isinstance(f2p, str):
            f2p = json.loads(f2p)
        if isinstance(p2p, str):
            p2p = json.loads(p2p)
        return cls(
            instance_id=data["instance_id"],
            repo=data.get("repo", ""),
            base_commit=data.get("base_commit", ""),
            patch=data.get("patch", ""),
            test_patch=data.get("test_patch", ""),
            problem_statement=data.get("problem_statement", ""),
            hints_text=data.get("hints_text", ""),
            fail_to_pass=f2p,
            pass_to_pass=p2p,
            version=data.get("version", ""),
            environment_setup_commit=data.get("environment_setup_commit", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class PatchHunk:
    """A single hunk from a unified diff."""
    file_path: str
    hunk_index: int
    header: str
    added_lines: list[str]
    removed_lines: list[str]
    context_lines: list[str]
    function_context: str
    raw_diff: str

    @property
    def is_test_file(self) -> bool:
        return "test" in self.file_path.lower()

    @property
    def is_init_file(self) -> bool:
        return self.file_path.endswith("__init__.py")

    @property
    def is_doc_file(self) -> bool:
        lower = self.file_path.lower()
        parts = lower.replace("\\", "/").split("/")
        if any(p == "docs" for p in parts):
            return True
        return any(
            pat in lower
            for pat in ["readme", "changelog", "contributing", ".md", ".rst"]
        ) and not lower.endswith(".py")

    @property
    def net_lines_changed(self) -> int:
        return len(self.added_lines) + len(self.removed_lines)


@dataclass
class CallTarget:
    """A function/method call found in test source via AST."""
    name: str
    module: str
    file_path: str
    line_number: int
    is_in_patch: bool


@dataclass
class Assertion:
    """A structured assertion extracted from a test via AST."""
    statement: str
    assertion_type: str
    target_expression: str
    expected_value: str


@dataclass
class TestedFunction:
    """A source function that a test exercises."""
    name: str
    file_path: str
    source: str
    is_modified_by_patch: bool


@dataclass
class CodeContext:
    """Full code context retrieved via code visitation (repo clone)."""
    pre_patch_test_source: str
    post_patch_test_source: str
    test_file_imports: str
    test_file_fixtures: str
    tested_functions: list[TestedFunction]
    call_targets: list[CallTarget]
    assertions: list[Assertion]
    test_file_path: str
    repo_path: str


@dataclass
class TestHunk:
    """A test function diff extracted from the test_patch."""
    file_path: str
    test_name: str
    full_test_id: str
    modification_type: TestModificationType
    added_lines: list[str]
    removed_lines: list[str]
    full_source: str
    raw_diff: str
    code_context: CodeContext | None = None


@dataclass
class ParsedTask:
    """Fully parsed SWE-bench task, ready for analysis."""
    record: TaskRecord
    patch_hunks: list[PatchHunk]
    test_hunks: list[TestHunk]
    f2p_test_hunks: list[TestHunk]
    f2p_tests_with_no_hunk: list[str]
    files_in_gold_patch: list[str]
    files_in_test_patch: list[str]


@dataclass
class ProblemDecomposition:
    """Structured decomposition of the problem statement.

    Separates the problem into its component parts so downstream stages
    can distinguish what the reporter actually asked for vs. what they
    suggested as a fix approach.
    """
    bug_description: str
    suggested_fix: str
    legitimacy: str
    mentioned_files: list[str] = field(default_factory=list)
    mentioned_functions: list[str] = field(default_factory=list)
    mentioned_classes: list[str] = field(default_factory=list)
    mentioned_variables: list[str] = field(default_factory=list)
    mentioned_modules: list[str] = field(default_factory=list)


@dataclass
class IntentStatement:
    """Intent extracted from the problem statement (blind to gold patch).

    The acceptance_criteria list is key: explicit testable behaviors the
    problem asks for — the reference for matching patches and tests.
    """
    instance_id: str
    core_requirement: str
    behavioral_contract: str
    acceptance_criteria: list[str]
    out_of_scope: str
    ambiguity_score: float
    raw_llm_response: str = ""
    decomposition: ProblemDecomposition | None = None


@dataclass
class ChangedBlock:
    """A source code block changed by the gold patch."""
    file_path: str
    block_name: str
    block_type: str
    edit_status: str
    pre_source: str = ""
    post_source: str = ""


@dataclass
class AssertionDetail:
    """A single assertion extracted from a test function."""
    statement: str
    verdict: AssertionVerdict = AssertionVerdict.ON_TOPIC
    reason: str = ""


@dataclass
class TestBlock:
    """An F2P test function with extracted assertions."""
    test_id: str
    test_name: str
    file_path: str
    full_source: str
    assertions: list[AssertionDetail] = field(default_factory=list)
    called_functions: list[str] = field(default_factory=list)


@dataclass
class StructuralDiff:
    """Structural analysis output."""
    instance_id: str
    changed_blocks: list[ChangedBlock]
    test_blocks: list[TestBlock]
    call_edges: list[tuple[str, str]]
    astred_available: bool = True


@dataclass
class HunkVerdict:
    """Intent-matching verdict for a single gold patch hunk."""
    hunk_index: int
    file_path: str
    verdict: PatchVerdict
    confidence: float
    reasoning: str
    is_heuristic: bool = False


@dataclass
class AssertionVerdictReport:
    """Intent-matching verdict for a single assertion."""
    statement: str
    verdict: AssertionVerdict
    reason: str = ""


@dataclass
class TestVerdictReport:
    """Intent-matching verdict for a single F2P test."""
    test_id: str
    test_name: str
    intent_match: TestVerdict
    confidence: float
    reasoning: str
    is_modified: bool
    modification_aligned: bool = True
    assertion_verdicts: list[AssertionVerdictReport] = field(default_factory=list)

    @property
    def on_topic_count(self) -> int:
        return sum(1 for a in self.assertion_verdicts if a.verdict == AssertionVerdict.ON_TOPIC)

    @property
    def off_topic_count(self) -> int:
        return sum(1 for a in self.assertion_verdicts if a.verdict == AssertionVerdict.OFF_TOPIC)


@dataclass
class ExcessPatchDetail:
    """Patch analysis results: per-hunk verdicts and binary signal."""
    total_hunks: int
    required_count: int
    ancillary_count: int
    unrelated_count: int
    hunk_verdicts: list[HunkVerdict] = field(default_factory=list)

    @property
    def has_excess(self) -> bool:
        return self.unrelated_count > 0


@dataclass
class ExcessTestDetail:
    """Test analysis results: per-test verdicts and binary signals."""
    total_tests: int
    aligned_count: int
    tangential_count: int
    unrelated_count: int
    total_assertions: int
    on_topic_assertions: int
    off_topic_assertions: int
    has_modified_tests: bool
    test_verdicts: list[TestVerdictReport] = field(default_factory=list)

    @property
    def has_excess(self) -> bool:
        return self.off_topic_assertions > 0 or self.unrelated_count > 0


@dataclass
class VagueSpecDetail:
    """Spec ambiguity analysis result."""
    score: float
    reasoning: str = ""


@dataclass
class TaskLabelAssignment:
    """A single Axis 1 label assigned to a task with evidence."""
    label: TaskContaminationLabel
    confidence: float
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class AgentLabelAssignment:
    """A single Axis 2 label assigned to an agent-task pair with evidence."""
    label: AgentTrajectoryLabel
    confidence: float
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class ContaminationReport:
    """Final contamination report for a single task."""
    instance_id: str
    severity: Severity
    intent: IntentStatement
    excess_patch: ExcessPatchDetail
    excess_test: ExcessTestDetail
    vague_spec: VagueSpecDetail
    task_labels: list[TaskLabelAssignment] = field(default_factory=list)
    agent_labels: dict[str, AgentLabelAssignment] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "severity": self.severity.value,
            "intent": {
                "core_requirement": self.intent.core_requirement,
                "behavioral_contract": self.intent.behavioral_contract,
                "acceptance_criteria": self.intent.acceptance_criteria,
                "out_of_scope": self.intent.out_of_scope,
                "ambiguity_score": round(self.intent.ambiguity_score, 4),
                **({"decomposition": {
                    "bug_description": self.intent.decomposition.bug_description,
                    "suggested_fix": self.intent.decomposition.suggested_fix,
                    "legitimacy": self.intent.decomposition.legitimacy,
                    "mentioned_files": self.intent.decomposition.mentioned_files,
                    "mentioned_functions": self.intent.decomposition.mentioned_functions,
                    "mentioned_classes": self.intent.decomposition.mentioned_classes,
                    "mentioned_variables": self.intent.decomposition.mentioned_variables,
                    "mentioned_modules": self.intent.decomposition.mentioned_modules,
                }} if self.intent.decomposition else {}),
            },
            "excess_patch": {
                "total_hunks": self.excess_patch.total_hunks,
                "required": self.excess_patch.required_count,
                "ancillary": self.excess_patch.ancillary_count,
                "unrelated": self.excess_patch.unrelated_count,
                "has_excess": self.excess_patch.has_excess,
                "hunks": [
                    {
                        "hunk_index": h.hunk_index,
                        "file": h.file_path,
                        "verdict": h.verdict.value,
                        "confidence": round(h.confidence, 4),
                        "reason": h.reasoning,
                    }
                    for h in self.excess_patch.hunk_verdicts
                ],
            },
            "excess_test": {
                "total_tests": self.excess_test.total_tests,
                "aligned": self.excess_test.aligned_count,
                "tangential": self.excess_test.tangential_count,
                "unrelated": self.excess_test.unrelated_count,
                "total_assertions": self.excess_test.total_assertions,
                "on_topic": self.excess_test.on_topic_assertions,
                "off_topic": self.excess_test.off_topic_assertions,
                "has_modified_tests": self.excess_test.has_modified_tests,
                "has_excess": self.excess_test.has_excess,
                "tests": [
                    {
                        "test_id": t.test_id,
                        "test_name": t.test_name,
                        "intent_match": t.intent_match.value,
                        "is_modified": t.is_modified,
                        "modification_aligned": t.modification_aligned,
                        "assertions": [
                            {
                                "statement": a.statement,
                                "verdict": a.verdict.value,
                                "reason": a.reason,
                            }
                            for a in t.assertion_verdicts
                        ],
                    }
                    for t in self.excess_test.test_verdicts
                ],
            },
            "vague_spec": {
                "score": round(self.vague_spec.score, 4),
                "reasoning": self.vague_spec.reasoning,
            },
            "task_labels": [
                {
                    "label": tl.label.value,
                    "confidence": round(tl.confidence, 4),
                    "evidence": tl.evidence,
                    "reasoning": tl.reasoning,
                }
                for tl in self.task_labels
            ],
            "agent_labels": {
                agent: {
                    "label": al.label.value,
                    "confidence": round(al.confidence, 4),
                    "evidence": al.evidence,
                    "reasoning": al.reasoning,
                }
                for agent, al in self.agent_labels.items()
            },
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContaminationReport:
        intent_d = data.get("intent", {})
        decomp_d = intent_d.get("decomposition")
        decomposition = None
        if decomp_d:
            decomposition = ProblemDecomposition(
                bug_description=decomp_d.get("bug_description", ""),
                suggested_fix=decomp_d.get("suggested_fix", ""),
                legitimacy=decomp_d.get("legitimacy", "unclear"),
                mentioned_files=decomp_d.get("mentioned_files", []),
                mentioned_functions=decomp_d.get("mentioned_functions", []),
                mentioned_classes=decomp_d.get("mentioned_classes", []),
                mentioned_variables=decomp_d.get("mentioned_variables", []),
                mentioned_modules=decomp_d.get("mentioned_modules", []),
            )
        intent = IntentStatement(
            instance_id=data["instance_id"],
            core_requirement=intent_d.get("core_requirement", ""),
            behavioral_contract=intent_d.get("behavioral_contract", ""),
            acceptance_criteria=intent_d.get("acceptance_criteria", []),
            out_of_scope=intent_d.get("out_of_scope", ""),
            ambiguity_score=intent_d.get("ambiguity_score", 0.0),
            decomposition=decomposition,
        )

        ep_d = data.get("excess_patch", {})
        hunk_verdicts = [
            HunkVerdict(
                hunk_index=h.get("hunk_index", 0),
                file_path=h.get("file", ""),
                verdict=PatchVerdict(h.get("verdict", "REQUIRED")),
                confidence=h.get("confidence", 0.0),
                reasoning=h.get("reason", ""),
            )
            for h in ep_d.get("hunks", [])
        ]
        excess_patch = ExcessPatchDetail(
            total_hunks=ep_d.get("total_hunks", 0),
            required_count=ep_d.get("required", 0),
            ancillary_count=ep_d.get("ancillary", 0),
            unrelated_count=ep_d.get("unrelated", 0),
            hunk_verdicts=hunk_verdicts,
        )

        et_d = data.get("excess_test", {})
        test_verdicts = []
        for t in et_d.get("tests", []):
            assertion_verdicts = [
                AssertionVerdictReport(
                    statement=a.get("statement", ""),
                    verdict=AssertionVerdict(a.get("verdict", "ON_TOPIC")),
                    reason=a.get("reason", ""),
                )
                for a in t.get("assertions", [])
            ]
            test_verdicts.append(TestVerdictReport(
                test_id=t.get("test_id", ""),
                test_name=t.get("test_name", ""),
                intent_match=TestVerdict(t.get("intent_match", "ALIGNED")),
                confidence=t.get("confidence", 0.0),
                reasoning=t.get("reasoning", ""),
                is_modified=t.get("is_modified", False),
                modification_aligned=t.get("modification_aligned", True),
                assertion_verdicts=assertion_verdicts,
            ))
        excess_test = ExcessTestDetail(
            total_tests=et_d.get("total_tests", 0),
            aligned_count=et_d.get("aligned", 0),
            tangential_count=et_d.get("tangential", 0),
            unrelated_count=et_d.get("unrelated", 0),
            total_assertions=et_d.get("total_assertions", 0),
            on_topic_assertions=et_d.get("on_topic", 0),
            off_topic_assertions=et_d.get("off_topic", 0),
            has_modified_tests=et_d.get("has_modified_tests", False),
            test_verdicts=test_verdicts,
        )

        vs_d = data.get("vague_spec", {})
        vague_spec = VagueSpecDetail(
            score=vs_d.get("score", 0.0),
            reasoning=vs_d.get("reasoning", ""),
        )

        task_labels = []
        for tl_d in data.get("task_labels", []):
            try:
                task_labels.append(TaskLabelAssignment(
                    label=TaskContaminationLabel(tl_d.get("label", "clean")),
                    confidence=tl_d.get("confidence", 0.0),
                    evidence=tl_d.get("evidence", []),
                    reasoning=tl_d.get("reasoning", ""),
                ))
            except ValueError:
                pass

        return cls(
            instance_id=data["instance_id"],
            severity=Severity(data.get("severity", "CLEAN")),
            intent=intent,
            excess_patch=excess_patch,
            excess_test=excess_test,
            vague_spec=vague_spec,
            task_labels=task_labels,
            recommendations=data.get("recommendations", []),
        )


@dataclass
class PipelineConfig:
    llm_base_url: str = "https://cloudgpt-openai.azure-api.net/"
    llm_api_version: str = "2025-04-01-preview"
    llm_model: str = "gpt-5.2-20251211"
    llm_max_tokens: int = 16384
    llm_reasoning_effort: str = "high"
    max_concurrent_requests: int = 10
    retry_attempts: int = 7
    retry_delay_seconds: float = 5.0
    concurrency: int = 5
    cache_dir: str = ".cache/llm_responses"
    output_dir: str = "output"
    repo_cache_dir: str = ".cache/repos"
    clone_timeout_seconds: int = 120
    max_source_context_lines: int = 200
