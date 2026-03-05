"""Contamination taxonomy: category definitions and severity thresholds."""

from __future__ import annotations

from bench_cleanser.models import ContaminationCategory, Severity


# Map categories to human-readable descriptions
CATEGORY_DESCRIPTIONS: dict[ContaminationCategory, str] = {
    ContaminationCategory.OVERTEST: (
        "F2P tests verify functionality beyond the task scope"
    ),
    ContaminationCategory.OVERPATCH: (
        "Gold patch contains changes beyond the required fix"
    ),
    ContaminationCategory.SNEAKY_TEST_MOD: (
        "Pre-existing tests are modified in the F2P set"
    ),
    ContaminationCategory.SCOPE_CREEP: (
        "The PR bundles multiple independent changes"
    ),
    ContaminationCategory.TEST_DESC_MISALIGN: (
        "Tests assert on specific behavior not described in the problem statement"
    ),
    ContaminationCategory.CIRCULAR_DEPENDENCY: (
        "F2P tests require out-of-scope patch changes to pass"
    ),
    ContaminationCategory.AMBIGUOUS_SPEC: (
        "Problem statement too vague to determine a unique correct solution"
    ),
}


def classify_severity(
    total_confidence: float,
    clean_max: float = 0.2,
    minor_max: float = 0.5,
    moderate_max: float = 0.8,
) -> Severity:
    """Map a total contamination confidence score to a severity level.

    Parameters
    ----------
    total_confidence:
        Combined contamination score in [0, 1].
    clean_max, minor_max, moderate_max:
        Threshold boundaries.  Anything above *moderate_max* is SEVERE.
    """
    if total_confidence < clean_max:
        return Severity.CLEAN
    if total_confidence < minor_max:
        return Severity.MINOR
    if total_confidence < moderate_max:
        return Severity.MODERATE
    return Severity.SEVERE
