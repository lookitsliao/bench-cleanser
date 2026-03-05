"""Stage 6: Per-category scoring and final classification.

Combines signals from Stages 2-5 into per-category confidence scores
and a composite contamination score.
"""

from __future__ import annotations

import logging
from functools import reduce

from bench_cleanser.classification.taxonomy import classify_severity
from bench_cleanser.models import (
    CategoryScore,
    ContaminationCategory,
    ContaminationReport,
    CrossReferenceAnalysis,
    PatchAnalysis,
    PipelineConfig,
    ScopeAnalysis,
    TestAnalysis,
)

logger = logging.getLogger(__name__)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def compute_category_scores(
    scope: ScopeAnalysis,
    patch: PatchAnalysis,
    tests: TestAnalysis,
    cross_ref: CrossReferenceAnalysis,
) -> dict[str, CategoryScore]:
    """Compute confidence scores for each contamination category.

    Returns a dict keyed by category name.
    """
    scores: dict[str, CategoryScore] = {}

    # C1: OVERTEST
    overtest_conf = _clamp(tests.overtest_score)
    overtest_evidence: list[str] = []
    if tests.misaligned_count > 0:
        overtest_evidence.append(
            f"{tests.misaligned_count} F2P test(s) misaligned with task scope"
        )
    if tests.sneaky_mod_count > 0:
        overtest_evidence.append(
            f"{tests.sneaky_mod_count} F2P test(s) are sneaky modifications"
        )
    scores[ContaminationCategory.OVERTEST.value] = CategoryScore(
        category=ContaminationCategory.OVERTEST,
        confidence=overtest_conf,
        evidence=overtest_evidence,
    )

    # C2: OVERPATCH
    overpatch_conf = _clamp(patch.overpatch_score)
    overpatch_evidence: list[str] = []
    if patch.out_of_scope_count > 0:
        overpatch_evidence.append(
            f"{patch.out_of_scope_count}/{patch.total_hunks} hunk(s) out of scope"
        )
    if patch.borderline_count > 0:
        overpatch_evidence.append(
            f"{patch.borderline_count} borderline hunk(s)"
        )
    scores[ContaminationCategory.OVERPATCH.value] = CategoryScore(
        category=ContaminationCategory.OVERPATCH,
        confidence=overpatch_conf,
        evidence=overpatch_evidence,
    )

    # C3: SNEAKY_TEST_MOD
    sneaky_conf = _clamp(tests.sneaky_test_mod_score)
    sneaky_evidence: list[str] = []
    has_misaligned_modified = False
    for tr in tests.test_reports:
        if tr.is_modified_existing:
            sneaky_evidence.append(
                f"{tr.test_id} existed at base_commit and was modified"
            )
            if tr.misaligned_assertion_count > 0:
                has_misaligned_modified = True
    if sneaky_evidence and has_misaligned_modified:
        sneaky_conf = max(sneaky_conf, 0.90)  # High confidence: modified tests with out-of-scope assertions
    elif sneaky_evidence:
        sneaky_conf = max(sneaky_conf, 0.30)  # Low confidence: modified but all assertions aligned
    scores[ContaminationCategory.SNEAKY_TEST_MOD.value] = CategoryScore(
        category=ContaminationCategory.SNEAKY_TEST_MOD,
        confidence=sneaky_conf,
        evidence=sneaky_evidence,
    )

    # C4: SCOPE_CREEP
    # Signal: many files in gold patch, especially if > 3 non-test files
    non_test_files = [
        hr.file_path
        for hr in patch.hunk_reports
        if "test" not in hr.file_path.lower()
    ]
    unique_non_test = len(set(non_test_files))
    scope_creep_conf = _clamp(0.0 if unique_non_test <= 2 else (unique_non_test - 2) * 0.15)
    scope_creep_evidence: list[str] = []
    if unique_non_test > 2:
        scope_creep_evidence.append(
            f"Gold patch touches {unique_non_test} non-test files"
        )
    scores[ContaminationCategory.SCOPE_CREEP.value] = CategoryScore(
        category=ContaminationCategory.SCOPE_CREEP,
        confidence=scope_creep_conf,
        evidence=scope_creep_evidence,
    )

    # C5: TEST_DESC_MISALIGN
    misaligned_assertions = sum(tr.misaligned_assertion_count for tr in tests.test_reports)
    total_assertions = sum(tr.assertion_count for tr in tests.test_reports) or 1
    misalign_conf = _clamp(misaligned_assertions / total_assertions)
    misalign_evidence: list[str] = []
    if misaligned_assertions > 0:
        misalign_evidence.append(
            f"{misaligned_assertions}/{total_assertions} assertion(s) check out-of-scope behavior"
        )
    scores[ContaminationCategory.TEST_DESC_MISALIGN.value] = CategoryScore(
        category=ContaminationCategory.TEST_DESC_MISALIGN,
        confidence=misalign_conf,
        evidence=misalign_evidence,
    )

    # C6: CIRCULAR_DEPENDENCY
    circular_conf = _clamp(cross_ref.circular_dependency_score)
    circular_evidence: list[str] = []
    for cd in cross_ref.circular_dependencies:
        circular_evidence.append(
            f"{cd.test_id} exercises {len(cd.out_of_scope_hunks)} OOS hunk(s)"
        )
    scores[ContaminationCategory.CIRCULAR_DEPENDENCY.value] = CategoryScore(
        category=ContaminationCategory.CIRCULAR_DEPENDENCY,
        confidence=circular_conf,
        evidence=circular_evidence,
    )

    # C7: AMBIGUOUS_SPEC
    ambig_conf = _clamp(scope.ambiguity_score)
    ambig_evidence: list[str] = []
    if scope.ambiguity_score > 0.5:
        ambig_evidence.append(
            f"Problem statement ambiguity score: {scope.ambiguity_score:.2f}"
        )
    scores[ContaminationCategory.AMBIGUOUS_SPEC.value] = CategoryScore(
        category=ContaminationCategory.AMBIGUOUS_SPEC,
        confidence=ambig_conf,
        evidence=ambig_evidence,
    )

    return scores


def compute_total_confidence(
    category_scores: dict[str, CategoryScore],
) -> float:
    """Compute total contamination score.

    Uses the formula: C_total = 1 - prod(1 - C_i) for all categories.
    """
    confidences = [cs.confidence for cs in category_scores.values()]
    if not confidences:
        return 0.0
    product = reduce(lambda acc, c: acc * (1.0 - c), confidences, 1.0)
    return _clamp(1.0 - product)


def build_evidence_summary(
    category_scores: dict[str, CategoryScore],
    compound_patterns: list[str],
) -> str:
    """Build a human-readable evidence summary."""
    parts: list[str] = []

    for name, cs in category_scores.items():
        if cs.confidence >= 0.2 and cs.evidence:
            parts.append(f"{name} ({cs.confidence:.2f}): {'; '.join(cs.evidence)}")

    if compound_patterns:
        parts.append(f"Compound patterns: {', '.join(compound_patterns)}")

    return " | ".join(parts) if parts else "No significant contamination signals"


def build_report(
    scope: ScopeAnalysis,
    patch: PatchAnalysis,
    tests: TestAnalysis,
    cross_ref: CrossReferenceAnalysis,
    config: PipelineConfig,
) -> ContaminationReport:
    """Build the final ContaminationReport from all analysis stages."""
    category_scores = compute_category_scores(scope, patch, tests, cross_ref)
    total_conf = compute_total_confidence(category_scores)
    severity = classify_severity(
        total_conf,
        clean_max=config.clean_max,
        minor_max=config.minor_max,
        moderate_max=config.moderate_max,
    )
    evidence = build_evidence_summary(
        category_scores, cross_ref.compound_patterns
    )

    return ContaminationReport(
        instance_id=scope.instance_id,
        severity=severity,
        total_confidence=total_conf,
        categories=category_scores,
        f2p_test_reports=tests.test_reports,
        patch_hunk_reports=patch.hunk_reports,
        compound_patterns=cross_ref.compound_patterns,
        evidence_summary=evidence,
    )
