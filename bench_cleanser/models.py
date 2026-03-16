"""Core data models for the bench-cleanser pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContaminationCategory(str, Enum):
    """Taxonomy of benchmark contamination types (v1 — 7 categories)."""
    OVERTEST = "OVERTEST"
    OVERPATCH = "OVERPATCH"
    SNEAKY_TEST_MOD = "SNEAKY_TEST_MOD"
    SCOPE_CREEP = "SCOPE_CREEP"
    TEST_DESC_MISALIGN = "TEST_DESC_MISALIGN"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    AMBIGUOUS_SPEC = "AMBIGUOUS_SPEC"


# ── v2 Taxonomy: 4 Verdict Categories ────────────────────────────────


class VerdictCategory(str, Enum):
    """v2 taxonomy: non-overlapping, actionable verdict categories."""
    EXCESS_PATCH = "EXCESS_PATCH"    # Gold patch includes changes beyond task scope
    EXCESS_TEST = "EXCESS_TEST"      # F2P tests verify behavior beyond task scope
    VAGUE_SPEC = "VAGUE_SPEC"        # Problem statement is ambiguous
    CLEAN = "CLEAN"                  # No contamination detected


class PatchVerdict(str, Enum):
    """Per-hunk verdict for gold patch intent matching."""
    REQUIRED = "REQUIRED"        # Directly implements the described fix
    ANCILLARY = "ANCILLARY"      # Supports the fix but isn't described (imports, infra)
    UNRELATED = "UNRELATED"      # Changes behavior not described in the problem


class TestVerdict(str, Enum):
    """Per-test verdict for F2P test intent matching."""
    ALIGNED = "ALIGNED"          # Test targets the described problem
    TANGENTIAL = "TANGENTIAL"    # Test partially targets the problem
    UNRELATED = "UNRELATED"      # Test doesn't target the described problem


class AssertionVerdict(str, Enum):
    """Per-assertion verdict for F2P test intent matching."""
    ON_TOPIC = "ON_TOPIC"        # Assertion checks behavior described in the problem
    OFF_TOPIC = "OFF_TOPIC"      # Assertion checks behavior NOT described in the problem


class Severity(str, Enum):
    """Severity classification for contaminated tasks."""
    CLEAN = "CLEAN"
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class RootCause(str, Enum):
    """Root-cause taxonomy for contaminated tasks.

    A task can have multiple root causes. These categories explain *why*
    the contamination exists, distinct from the verdict *scores* (EP/ET/VS)
    which measure *how much* contamination is present.
    """
    APPROACH_MISMATCH = "APPROACH_MISMATCH"
    """Gold patch takes a fundamentally different approach than the problem
    statement suggests.  Detection: High EXCESS_PATCH with UNRELATED hunks
    implementing an approach-level divergence from the described fix.
    Example: django-10999 — problem says "add lookahead"; gold patch adds
    a regex sign-group instead."""

    DEFERRED_REQUIREMENT = "DEFERRED_REQUIREMENT"
    """Tests enforce features explicitly deferred or disclaimed in the problem
    statement.  Detection: Explicit deferral language in the problem + OFF_TOPIC
    assertions that exercise the deferred feature.
    Example: astropy-13398 — "I have yet to add refraction" but F2P tests
    require refraction support."""

    SCOPE_EXPANSION = "SCOPE_EXPANSION"
    """Gold patch and/or tests cover functionality beyond what was asked.
    Detection: High OFF_TOPIC assertion ratio, tests exercising code paths
    not mentioned in the problem.
    Example: astropy-14182 — problem asks for RST writer fix; tests exercise
    RST reader round-trip."""

    IMPLICIT_CONSENSUS = "IMPLICIT_CONSENSUS"
    """Solution requires knowledge from code review discussion or hints that
    contradicts or extends the original problem statement.  Detection: Hints
    contain design decisions not derivable from the problem statement alone.
    Example: django-10999 — maintainer decided "leading sign negates all"
    during code review, not stated in the original issue."""

    INFRASTRUCTURE_LEAK = "INFRASTRUCTURE_LEAK"
    """Tests require ancillary infrastructure changes not described in the
    feature specification.  Detection: F2P tests exercising infrastructure
    code paths not mentioned in the problem statement.
    Example: astropy-13398 — CIRS round-trip tests requiring coordinate
    transform infrastructure not described in the spec."""


# ── v3 Dual Taxonomy ──────────────────────────────────────────────────


class TaskContaminationLabel(str, Enum):
    """Axis 1: task-level contamination labels (multi-label per task).

    Groups:
      A – Test contamination
      B – Patch contamination
      C – Description contamination
      D – Structural contamination
      E – Clean
    """
    # Group A – Test Contamination
    MISTEST_OVERTEST = "mistest_overtest"
    MISTEST_UNDERTEST = "mistest_undertest"
    MISTEST_CUSTOMTEST = "mistest_customtest"
    MISTEST_SNEAKY_MODIFICATION = "mistest_sneaky_modification"
    MISTEST_DEFERRED_REQUIREMENT = "mistest_deferred_requirement"
    # Group B – Patch Contamination
    MISPATCH_OVERPATCH = "mispatch_overpatch"
    MISPATCH_UNDERPATCH = "mispatch_underpatch"
    MISPATCH_APPROACH_MISMATCH = "mispatch_approach_mismatch"
    MISPATCH_ANCILLARY_BUNDLING = "mispatch_ancillary_bundling"
    # Group C – Description Contamination
    DESC_MISLEADING = "desc_misleading"
    DESC_INCOMPLETE = "desc_incomplete"
    DESC_HIDDEN_IN_HINTS = "desc_hidden_in_hints"
    DESC_SELF_REFERENTIAL = "desc_self_referential"
    # Group D – Structural Contamination
    SCOPE_EXPANSION = "scope_expansion"
    CIRCULAR_TEST_PATCH_DEPENDENCY = "circular_test_patch_dependency"
    # Group E – Clean
    CLEAN = "clean"
    HARD_BUT_CLEAN = "hard_but_clean"


class AgentTrajectoryLabel(str, Enum):
    """Axis 2: per-agent-task trajectory classification (single primary label)."""
    AGENT_PASSED_GENUINE = "agent_passed_genuine"
    AGENT_PASSED_LEAK = "agent_passed_leak"
    AGENT_PASSED_PACKAGE_LEAK = "agent_passed_package_leak"
    AGENT_PASSED_TEST_AWARE = "agent_passed_test_aware"
    AGENT_PASSED_TRAINED_HACK = "agent_passed_trained_hack"
    AGENT_FAILED_COMPLETED_INTENT = "agent_failed_completed_intent"
    AGENT_FAILED_NO_INTENT = "agent_failed_no_intent"
    AGENT_UNKNOWN = "agent_unknown"


@dataclass
class TaskLabelAssignment:
    """A single Axis 1 label assigned to a task with evidence."""
    label: TaskContaminationLabel
    confidence: float                  # 0.0–1.0
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
class DualTaxonomyReport:
    """v3 contamination report combining task labels and agent trajectory labels.

    Preserves all v2 fields (EP/ET/VS, intent, severity) for backward
    compatibility, plus the new multi-label dual taxonomy output.
    """
    instance_id: str
    severity: Severity
    combined_score: float
    intent: IntentStatement
    excess_patch: ExcessPatchDetail
    excess_test: ExcessTestDetail
    vague_spec: VagueSpecDetail
    task_labels: list[TaskLabelAssignment] = field(default_factory=list)
    agent_labels: dict[str, AgentLabelAssignment] = field(default_factory=dict)
    # Preserved v2 fields
    categories: dict[str, VerdictScore] = field(default_factory=dict)
    root_causes: list[RootCause] = field(default_factory=list)
    root_cause_reasoning: dict[str, str] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict (v3 superset of v2)."""
        # Base v2-compatible output
        base = ContaminationReportV2(
            instance_id=self.instance_id,
            severity=self.severity,
            combined_score=self.combined_score,
            intent=self.intent,
            excess_patch=self.excess_patch,
            excess_test=self.excess_test,
            vague_spec=self.vague_spec,
            categories=self.categories,
            root_causes=self.root_causes,
            root_cause_reasoning=self.root_cause_reasoning,
            recommendations=self.recommendations,
        ).to_dict()
        # Add v3 dual taxonomy fields
        base["task_labels"] = [
            {
                "label": tl.label.value,
                "confidence": round(tl.confidence, 4),
                "evidence": tl.evidence,
                "reasoning": tl.reasoning,
            }
            for tl in self.task_labels
        ]
        base["agent_labels"] = {
            agent: {
                "label": al.label.value,
                "confidence": round(al.confidence, 4),
                "evidence": al.evidence,
                "reasoning": al.reasoning,
            }
            for agent, al in self.agent_labels.items()
        }
        return base


class HunkClassification(str, Enum):
    """Classification of a gold patch hunk relative to task scope."""
    IN_SCOPE = "IN_SCOPE"
    BORDERLINE = "BORDERLINE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class TestClassification(str, Enum):
    """Classification of an F2P test relative to task scope."""
    ALIGNED = "ALIGNED"
    PARTIALLY_ALIGNED = "PARTIALLY_ALIGNED"
    MISALIGNED = "MISALIGNED"
    SNEAKY_MODIFICATION = "SNEAKY_MODIFICATION"


class TestModificationType(str, Enum):
    """Whether a test in the test_patch is new or modified."""
    NEW = "NEW"
    MODIFIED = "MODIFIED"
    UNKNOWN = "UNKNOWN"


# --- Stage 1: Parsing ---

@dataclass
class TaskRecord:
    """Raw SWE-bench task record."""
    instance_id: str
    repo: str
    base_commit: str
    patch: str  # gold patch (unified diff)
    test_patch: str  # test modifications (unified diff)
    problem_statement: str
    hints_text: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    version: str
    environment_setup_commit: str = ""
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        """Create from a SWE-bench dataset row."""
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
    hunk_index: int  # Index within the file's hunks
    header: str  # @@ line
    added_lines: list[str]
    removed_lines: list[str]
    context_lines: list[str]
    function_context: str  # Function name from @@ header if available
    raw_diff: str  # The raw hunk text

    @property
    def is_test_file(self) -> bool:
        return "test" in self.file_path.lower()

    @property
    def is_init_file(self) -> bool:
        return self.file_path.endswith("__init__.py")

    @property
    def is_doc_file(self) -> bool:
        lower = self.file_path.lower()
        # Only match standalone docs/ directories, not substrings like "admindocs/"
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
    name: str                    # e.g., "Run", "_check_regexp_csv"
    module: str                  # resolved module path (or "" if unresolved)
    file_path: str               # resolved file in repo (or "")
    line_number: int             # line in test source
    is_in_patch: bool            # True if this target is in a gold-patch file


@dataclass
class Assertion:
    """A structured assertion extracted from a test via AST."""
    statement: str               # full assertion line
    assertion_type: str          # "assert", "assertEqual", "assertRaises", etc.
    target_expression: str       # what's being asserted on
    expected_value: str          # expected result (if extractable)


@dataclass
class TestedFunction:
    """A source function that a test exercises."""
    name: str
    file_path: str
    source: str                  # full function source from repo
    is_modified_by_patch: bool   # True if gold patch modifies this function


@dataclass
class CodeContext:
    """Full code context retrieved via code visitation (repo clone)."""
    pre_patch_test_source: str       # full test function BEFORE patch
    post_patch_test_source: str      # full test function AFTER patch
    test_file_imports: str           # import block from test file
    test_file_fixtures: str          # fixtures/setup used by test
    tested_functions: list[TestedFunction]  # source code being tested
    call_targets: list[CallTarget]   # all calls from test body
    assertions: list[Assertion]      # structured assertions
    test_file_path: str
    repo_path: str                   # local clone path


@dataclass
class TestHunk:
    """A test function diff extracted from the test_patch."""
    file_path: str
    test_name: str  # e.g., "test_csv_regex_error"
    full_test_id: str  # e.g., "tests/config/test_config.py::test_csv_regex_error"
    modification_type: TestModificationType
    added_lines: list[str]
    removed_lines: list[str]
    full_source: str  # Reconstructed test function source (from + lines)
    raw_diff: str
    code_context: CodeContext | None = None  # populated by code visitation


@dataclass
class ParsedTask:
    """Fully parsed SWE-bench task, ready for analysis."""
    record: TaskRecord
    patch_hunks: list[PatchHunk]
    test_hunks: list[TestHunk]
    f2p_test_hunks: list[TestHunk]  # Test hunks matching F2P test IDs
    f2p_tests_with_no_hunk: list[str]  # F2P test IDs with no matching hunk
    files_in_gold_patch: list[str]
    files_in_test_patch: list[str]


# --- Stage 2: Scope Analysis ---

@dataclass
class ScopeAnalysis:
    """LLM-derived analysis of what the task actually asks for."""
    instance_id: str
    core_requirement: str
    affected_components: list[str]
    behavioral_contract: str
    out_of_scope: str
    ambiguity_score: float  # 0.0 = perfectly clear, 1.0 = very ambiguous
    raw_llm_response: str = ""


# --- Stage 3: Patch Analysis ---

@dataclass
class HunkReport:
    """Analysis result for a single gold patch hunk."""
    hunk_index: int
    file_path: str
    classification: HunkClassification
    confidence: float
    reasoning: str
    is_heuristic: bool  # True if classified by heuristic, False if by LLM


@dataclass
class PatchAnalysis:
    """Complete analysis of the gold patch."""
    instance_id: str
    hunk_reports: list[HunkReport]
    total_hunks: int
    in_scope_count: int
    out_of_scope_count: int
    borderline_count: int
    infrastructure_count: int
    overpatch_score: float  # Fraction of out-of-scope hunks


# --- Stage 4: Test Analysis ---

@dataclass
class TestReport:
    """Analysis result for a single F2P test."""
    test_id: str
    test_name: str
    modification_type: TestModificationType
    classification: TestClassification
    confidence: float
    reasoning: str
    is_modified_existing: bool  # Deterministic signal: test existed before
    assertion_count: int
    misaligned_assertion_count: int


@dataclass
class TestAnalysis:
    """Complete analysis of the test patch and F2P tests."""
    instance_id: str
    test_reports: list[TestReport]
    total_f2p_tests: int
    aligned_count: int
    misaligned_count: int
    sneaky_mod_count: int
    overtest_score: float
    sneaky_test_mod_score: float


# --- Stage 5: Cross-Reference ---

@dataclass
class CircularDependency:
    """A detected circular dependency between an F2P test and out-of-scope hunks."""
    test_id: str
    out_of_scope_hunks: list[int]  # Indices of OOS hunks the test exercises
    confidence: float
    reasoning: str


@dataclass
class CrossReferenceAnalysis:
    """Cross-reference analysis results."""
    instance_id: str
    circular_dependencies: list[CircularDependency]
    compound_patterns: list[str]  # e.g., ["SNEAKY+CIRCULAR", "OVERPATCH+OVERTEST"]
    circular_dependency_score: float


# --- Stage 6: Classification ---

@dataclass
class CategoryScore:
    """Confidence score for a single contamination category."""
    category: ContaminationCategory
    confidence: float
    evidence: list[str]


@dataclass
class ContaminationReport:
    """Final contamination report for a single task."""
    instance_id: str
    severity: Severity
    total_confidence: float
    categories: dict[str, CategoryScore]
    f2p_test_reports: list[TestReport]
    patch_hunk_reports: list[HunkReport]
    compound_patterns: list[str]
    evidence_summary: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "instance_id": self.instance_id,
            "severity": self.severity.value,
            "total_confidence": round(self.total_confidence, 4),
            "categories": {
                name: {
                    "category": score.category.value,
                    "confidence": round(score.confidence, 4),
                    "evidence": score.evidence,
                }
                for name, score in self.categories.items()
            },
            "f2p_test_reports": [
                {
                    "test_id": tr.test_id,
                    "test_name": tr.test_name,
                    "modification_type": tr.modification_type.value,
                    "classification": tr.classification.value,
                    "confidence": round(tr.confidence, 4),
                    "reasoning": tr.reasoning,
                    "is_modified_existing": tr.is_modified_existing,
                    "assertion_count": tr.assertion_count,
                    "misaligned_assertion_count": tr.misaligned_assertion_count,
                }
                for tr in self.f2p_test_reports
            ],
            "patch_hunk_reports": [
                {
                    "hunk_index": hr.hunk_index,
                    "file_path": hr.file_path,
                    "classification": hr.classification.value,
                    "confidence": round(hr.confidence, 4),
                    "reasoning": hr.reasoning,
                    "is_heuristic": hr.is_heuristic,
                }
                for hr in self.patch_hunk_reports
            ],
            "compound_patterns": self.compound_patterns,
            "evidence_summary": self.evidence_summary,
        }


# ── v2 Models ─────────────────────────────────────────────────────────


@dataclass
class IntentStatement:
    """Ground truth intent extracted from the problem statement (Stage 2 v2).

    The acceptance_criteria list is the key addition: explicit testable behaviors
    that the problem description asks for.  This becomes the reference for
    matching patches and tests against the described intent.
    """
    instance_id: str
    core_requirement: str              # What must change
    behavioral_contract: str           # How behavior should differ after fix
    acceptance_criteria: list[str]     # Specific verifiable claims from description
    out_of_scope: str                  # What is NOT asked for
    ambiguity_score: float             # 0-1
    raw_llm_response: str = ""


@dataclass
class ChangedBlock:
    """A source code block changed by the gold patch (Stage 3 v2)."""
    file_path: str
    block_name: str            # function/class name
    block_type: str            # "function", "class", "method", "statement"
    edit_status: str           # "INSERT", "DELETE", "UPDATE" (from astred_core)
    pre_source: str = ""       # source before patch
    post_source: str = ""      # source after patch


@dataclass
class AssertionDetail:
    """A single assertion extracted from a test function."""
    statement: str             # full assertion source line
    verdict: AssertionVerdict = AssertionVerdict.ON_TOPIC
    reason: str = ""


@dataclass
class TestBlock:
    """An F2P test function with extracted assertions (Stage 3 v2)."""
    test_id: str
    test_name: str
    file_path: str
    full_source: str
    assertions: list[AssertionDetail] = field(default_factory=list)
    called_functions: list[str] = field(default_factory=list)  # names of functions called


@dataclass
class StructuralDiff:
    """Structural analysis output from astred_core (Stage 3 v2)."""
    instance_id: str
    changed_blocks: list[ChangedBlock]       # Functions/classes changed by gold patch
    test_blocks: list[TestBlock]             # F2P test functions with assertions
    call_edges: list[tuple[str, str]]        # (test_function, changed_function) pairs
    astred_available: bool = True            # False if fell back to Python ast


# ── v2 Verdict Reports ───────────────────────────────────────────────


@dataclass
class HunkVerdict:
    """Intent-matching verdict for a single gold patch hunk (Stage 4A v2)."""
    hunk_index: int
    file_path: str
    verdict: PatchVerdict
    confidence: float
    reasoning: str
    is_heuristic: bool = False


@dataclass
class AssertionVerdictReport:
    """Intent-matching verdict for a single assertion within an F2P test."""
    statement: str
    verdict: AssertionVerdict
    reason: str = ""


@dataclass
class TestVerdictReport:
    """Intent-matching verdict for a single F2P test (Stage 4B v2)."""
    test_id: str
    test_name: str
    intent_match: TestVerdict
    confidence: float
    reasoning: str
    is_modified: bool                        # Was test pre-existing and modified?
    modification_aligned: bool = True        # If modified, is the modification aligned?
    assertion_verdicts: list[AssertionVerdictReport] = field(default_factory=list)

    @property
    def on_topic_count(self) -> int:
        return sum(1 for a in self.assertion_verdicts if a.verdict == AssertionVerdict.ON_TOPIC)

    @property
    def off_topic_count(self) -> int:
        return sum(1 for a in self.assertion_verdicts if a.verdict == AssertionVerdict.OFF_TOPIC)


@dataclass
class ExcessPatchDetail:
    """Detailed EXCESS_PATCH scoring breakdown."""
    score: float
    total_hunks: int
    required_count: int
    ancillary_count: int
    unrelated_count: int
    hunk_verdicts: list[HunkVerdict] = field(default_factory=list)


@dataclass
class ExcessTestDetail:
    """Detailed EXCESS_TEST scoring breakdown."""
    score: float
    total_tests: int
    aligned_count: int
    tangential_count: int
    unrelated_count: int
    total_assertions: int
    on_topic_assertions: int
    off_topic_assertions: int
    has_modified_tests: bool
    test_verdicts: list[TestVerdictReport] = field(default_factory=list)


@dataclass
class VagueSpecDetail:
    """Detailed VAGUE_SPEC scoring breakdown."""
    score: float
    reasoning: str = ""


@dataclass
class VerdictScore:
    """Confidence score for a single v2 verdict category."""
    category: VerdictCategory
    confidence: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class ContaminationReportV2:
    """v2 contamination report with intent-matching verdicts."""
    instance_id: str
    severity: Severity
    combined_score: float
    intent: IntentStatement
    excess_patch: ExcessPatchDetail
    excess_test: ExcessTestDetail
    vague_spec: VagueSpecDetail
    categories: dict[str, VerdictScore] = field(default_factory=dict)
    root_causes: list[RootCause] = field(default_factory=list)
    root_cause_reasoning: dict[str, str] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "instance_id": self.instance_id,
            "severity": self.severity.value,
            "combined_score": round(self.combined_score, 4),
            "intent": {
                "core_requirement": self.intent.core_requirement,
                "behavioral_contract": self.intent.behavioral_contract,
                "acceptance_criteria": self.intent.acceptance_criteria,
                "out_of_scope": self.intent.out_of_scope,
                "ambiguity_score": round(self.intent.ambiguity_score, 4),
            },
            "excess_patch": {
                "score": round(self.excess_patch.score, 4),
                "total_hunks": self.excess_patch.total_hunks,
                "required": self.excess_patch.required_count,
                "ancillary": self.excess_patch.ancillary_count,
                "unrelated": self.excess_patch.unrelated_count,
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
                "score": round(self.excess_test.score, 4),
                "total_tests": self.excess_test.total_tests,
                "aligned": self.excess_test.aligned_count,
                "tangential": self.excess_test.tangential_count,
                "unrelated": self.excess_test.unrelated_count,
                "total_assertions": self.excess_test.total_assertions,
                "on_topic": self.excess_test.on_topic_assertions,
                "off_topic": self.excess_test.off_topic_assertions,
                "has_modified_tests": self.excess_test.has_modified_tests,
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
            "recommendations": self.recommendations,
            "root_causes": [rc.value for rc in self.root_causes],
            "root_cause_reasoning": self.root_cause_reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContaminationReportV2:
        """Reconstruct from a JSON-compatible dict (inverse of to_dict)."""
        intent_d = data.get("intent", {})
        intent = IntentStatement(
            instance_id=data["instance_id"],
            core_requirement=intent_d.get("core_requirement", ""),
            behavioral_contract=intent_d.get("behavioral_contract", ""),
            acceptance_criteria=intent_d.get("acceptance_criteria", []),
            out_of_scope=intent_d.get("out_of_scope", ""),
            ambiguity_score=intent_d.get("ambiguity_score", 0.0),
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
            score=ep_d.get("score", 0.0),
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
            score=et_d.get("score", 0.0),
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

        root_causes = []
        for rc_str in data.get("root_causes", []):
            try:
                root_causes.append(RootCause(rc_str))
            except ValueError:
                pass

        return cls(
            instance_id=data["instance_id"],
            severity=Severity(data.get("severity", "CLEAN")),
            combined_score=data.get("combined_score", 0.0),
            intent=intent,
            excess_patch=excess_patch,
            excess_test=excess_test,
            vague_spec=vague_spec,
            root_causes=root_causes,
            root_cause_reasoning=data.get("root_cause_reasoning", {}),
            recommendations=data.get("recommendations", []),
        )


@dataclass
class PipelineConfig:
    """Configuration for the pipeline."""
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
    clean_max: float = 0.15
    minor_max: float = 0.4
    moderate_max: float = 0.7
    astred_enabled: bool = False
    astred_binary_path: str = ""
    code_visitation_enabled: bool = True
    repo_cache_dir: str = ".cache/repos"
    clone_timeout_seconds: int = 120
    max_source_context_lines: int = 200
