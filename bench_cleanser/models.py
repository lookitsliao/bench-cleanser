"""Core data models for the bench-cleanser pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContaminationCategory(str, Enum):
    """Taxonomy of benchmark contamination types."""
    OVERTEST = "OVERTEST"
    OVERPATCH = "OVERPATCH"
    SNEAKY_TEST_MOD = "SNEAKY_TEST_MOD"
    SCOPE_CREEP = "SCOPE_CREEP"
    TEST_DESC_MISALIGN = "TEST_DESC_MISALIGN"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    AMBIGUOUS_SPEC = "AMBIGUOUS_SPEC"


class Severity(str, Enum):
    """Severity classification for contaminated tasks."""
    CLEAN = "CLEAN"
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


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


@dataclass
class PipelineConfig:
    """Configuration for the pipeline."""
    llm_base_url: str = "https://cloudgpt-openai.azure-api.net/"
    llm_api_version: str = "2025-04-01-preview"
    llm_model: str = "gpt-5.2-20251211"
    llm_max_tokens: int = 4096
    llm_reasoning_effort: str = "high"
    max_concurrent_requests: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: float = 2.0
    concurrency: int = 5
    cache_dir: str = ".cache/llm_responses"
    output_dir: str = "output"
    clean_max: float = 0.2
    minor_max: float = 0.5
    moderate_max: float = 0.8
    astred_enabled: bool = False
    astred_binary_path: str = ""
    code_visitation_enabled: bool = True
    repo_cache_dir: str = ".cache/repos"
    clone_timeout_seconds: int = 120
    max_source_context_lines: int = 200
