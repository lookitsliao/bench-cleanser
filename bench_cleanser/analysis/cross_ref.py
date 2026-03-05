"""Stage 5: Cross-reference analysis.

Detects circular dependencies between F2P tests and out-of-scope patch
hunks, and identifies compound contamination patterns.

When ``CodeContext`` (from code visitation) is available the analysis uses
real call-graph data: ``CallTarget.is_in_patch``, ``TestedFunction``
objects, and structured ``Assertion`` data to detect true circular
dependencies instead of relying on identifier overlap heuristics.
"""

from __future__ import annotations

import logging
import re

from bench_cleanser.models import (
    CircularDependency,
    CrossReferenceAnalysis,
    HunkClassification,
    PatchAnalysis,
    TestAnalysis,
    TestClassification,
    TestHunk,
)

logger = logging.getLogger(__name__)


def _extract_identifiers(text: str) -> set[str]:
    """Extract Python identifiers from a block of text.

    Used as a fallback to find function names, variable names, and module
    references that can link tests to patch hunks.
    """
    return set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", text))


def _normalize_path(p: str) -> str:
    """Normalize a file path for comparison."""
    return p.replace("\\", "/").lstrip("/").rstrip("/")


def analyze_cross_references(
    patch_analysis: PatchAnalysis,
    test_analysis: TestAnalysis,
    f2p_test_hunks: list[TestHunk] | None = None,
) -> CrossReferenceAnalysis:
    """Run Stage 5 cross-reference analysis.

    Detects:
    1. Circular dependencies: F2P tests that exercise functions/identifiers
       found in OUT_OF_SCOPE or BORDERLINE patch hunks.
    2. Compound contamination patterns (e.g., SNEAKY + CIRCULAR).

    When *f2p_test_hunks* is provided (with ``CodeContext``), the analysis
    uses real call-graph data for precise dependency detection.
    """
    instance_id = patch_analysis.instance_id

    # Build sets of out-of-scope files and hunk indices
    oos_hunk_indices: set[int] = set()
    oos_files: set[str] = set()
    oos_hunk_ids: dict[int, set[str]] = {}

    for hr in patch_analysis.hunk_reports:
        if hr.classification in (
            HunkClassification.OUT_OF_SCOPE,
            HunkClassification.BORDERLINE,
        ):
            oos_hunk_indices.add(hr.hunk_index)
            oos_files.add(_normalize_path(hr.file_path))
            # Fallback identifier extraction from report reasoning
            oos_hunk_ids[hr.hunk_index] = _extract_identifiers(
                hr.reasoning + " " + hr.file_path
            )

    # Build a lookup from test_id to TestHunk for code-context access
    hunk_by_test_id: dict[str, TestHunk] = {}
    if f2p_test_hunks:
        for th in f2p_test_hunks:
            hunk_by_test_id[th.full_test_id] = th

    circular_deps: list[CircularDependency] = []

    for tr in test_analysis.test_reports:
        if tr.classification not in (
            TestClassification.MISALIGNED,
            TestClassification.SNEAKY_MODIFICATION,
            TestClassification.PARTIALLY_ALIGNED,
        ):
            continue

        test_hunk = hunk_by_test_id.get(tr.test_id)
        ctx = test_hunk.code_context if test_hunk else None

        if ctx is not None:
            # --- Enhanced path: use real call-graph data ---
            overlapping_hunks = _check_code_context_overlap(
                ctx, oos_files, oos_hunk_indices
            )
        else:
            # --- Fallback: identifier overlap heuristic ---
            overlapping_hunks = _check_identifier_overlap(
                tr.reasoning + " " + tr.test_name, oos_hunk_ids
            )

        if overlapping_hunks:
            confidence = min(0.95, 0.7 + 0.1 * len(overlapping_hunks))
            # Boost confidence when we have code-context evidence
            if ctx is not None:
                confidence = min(0.98, confidence + 0.1)

            circular_deps.append(
                CircularDependency(
                    test_id=tr.test_id,
                    out_of_scope_hunks=overlapping_hunks,
                    confidence=confidence,
                    reasoning=_build_circular_reasoning(
                        tr.test_name, tr.classification, overlapping_hunks,
                        ctx is not None,
                    ),
                )
            )

    # Detect compound patterns
    compound_patterns = _detect_compound_patterns(
        test_analysis, patch_analysis, circular_deps
    )

    # Compute circular dependency score
    if circular_deps:
        circular_score = max(cd.confidence for cd in circular_deps)
    else:
        circular_score = 0.0

    return CrossReferenceAnalysis(
        instance_id=instance_id,
        circular_dependencies=circular_deps,
        compound_patterns=compound_patterns,
        circular_dependency_score=circular_score,
    )


# ---------------------------------------------------------------------------
# Enhanced overlap detection (using CodeContext)
# ---------------------------------------------------------------------------

def _check_code_context_overlap(
    ctx, oos_files: set[str], oos_hunk_indices: set[int],
) -> list[int]:
    """Check if any call targets or tested functions overlap with OOS hunks."""
    overlapping: set[int] = set()

    # Check call targets that point to OOS files
    for ct in ctx.call_targets:
        if ct.is_in_patch and ct.file_path:
            normalized = _normalize_path(ct.file_path)
            if normalized in oos_files:
                # Find which OOS hunk indices correspond to this file
                overlapping.update(oos_hunk_indices)

    # Check tested functions in OOS files
    for tf in ctx.tested_functions:
        if tf.is_modified_by_patch and tf.file_path:
            normalized = _normalize_path(tf.file_path)
            if normalized in oos_files:
                overlapping.update(oos_hunk_indices)

    return sorted(overlapping)


# ---------------------------------------------------------------------------
# Fallback identifier overlap (no CodeContext)
# ---------------------------------------------------------------------------

def _check_identifier_overlap(
    test_text: str, oos_hunk_ids: dict[int, set[str]],
) -> list[int]:
    """Fallback: check identifier overlap between test and OOS hunks."""
    test_ids = _extract_identifiers(test_text)
    overlapping: list[int] = []
    for hunk_idx, hunk_ids in oos_hunk_ids.items():
        if test_ids & hunk_ids:
            overlapping.append(hunk_idx)
    return overlapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_circular_reasoning(
    test_name: str,
    classification: TestClassification,
    overlapping_hunks: list[int],
    has_code_context: bool,
) -> str:
    """Build a human-readable reasoning string."""
    method = "call-graph analysis" if has_code_context else "identifier overlap"
    return (
        f"Test {test_name} ({classification.value}) exercises code from "
        f"{len(overlapping_hunks)} out-of-scope hunk(s): {overlapping_hunks} "
        f"(detected via {method})"
    )


def _detect_compound_patterns(
    test_analysis: TestAnalysis,
    patch_analysis: PatchAnalysis,
    circular_deps: list[CircularDependency],
) -> list[str]:
    """Detect compound contamination patterns."""
    compound_patterns: list[str] = []

    has_sneaky = test_analysis.sneaky_mod_count > 0
    has_circular = len(circular_deps) > 0
    has_overpatch = patch_analysis.overpatch_score > 0.3
    has_overtest = test_analysis.overtest_score > 0.3

    if has_sneaky and has_circular:
        compound_patterns.append("SNEAKY+CIRCULAR")
    if has_overpatch and has_overtest:
        compound_patterns.append("OVERPATCH+OVERTEST")
    if patch_analysis.out_of_scope_count > 2 and has_overtest:
        compound_patterns.append("SCOPE_CREEP+OVERTEST")

    return compound_patterns
