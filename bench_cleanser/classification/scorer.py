"""Stage 6: Final classification and report building.

Combines intent-matching verdicts (Stages 4A/4B) and cross-reference
analysis with the dual taxonomy classifier to produce a ContaminationReport
with binary labels and bucket-based severity.
"""

from __future__ import annotations

import logging
from typing import Any

from bench_cleanser.analysis.cross_ref import CrossReferenceResult
from bench_cleanser.models import (
    ContaminationReport,
    DescriptionClarity,
    IntentStatement,
    PatchAnalysis,
    PipelineConfig,
    TaskRecord,
    TestAnalysis,
)

logger = logging.getLogger(__name__)


async def build_report(
    intent: IntentStatement,
    patch_analysis: PatchAnalysis,
    test_analysis: TestAnalysis,
    description_clarity: DescriptionClarity,
    config: PipelineConfig,
    record: TaskRecord | None = None,
    llm: Any = None,
    cross_ref: CrossReferenceResult | None = None,
) -> ContaminationReport:
    """Build final ContaminationReport from intent-matching + dual taxonomy.

    Runs the dual taxonomy classifier (Axis 1) for multi-label output
    then determines severity via bucket rules.
    """
    from bench_cleanser.classification.dual_taxonomy import (
        classify_task_labels,
        compute_task_severity,
    )

    task_labels = await classify_task_labels(
        intent, patch_analysis=patch_analysis, test_analysis=test_analysis,
        description_clarity=description_clarity,
        record=record, llm=llm, cross_ref=cross_ref,
    )

    severity = compute_task_severity(task_labels)

    recommendations = _build_recommendations(
        task_labels, patch_analysis, test_analysis, cross_ref,
    )

    return ContaminationReport(
        instance_id=intent.instance_id,
        severity=severity,
        intent=intent,
        patch_analysis=patch_analysis,
        test_analysis=test_analysis,
        description_clarity=description_clarity,
        task_labels=task_labels,
        recommendations=recommendations,
    )


def _build_recommendations(
    task_labels: list,
    patch_analysis: PatchAnalysis,
    test_analysis: TestAnalysis,
    cross_ref: CrossReferenceResult | None = None,
) -> list[str]:
    """Build actionable recommendations gated by the FINAL task label set.

    Recommendations are generated only for labels actually assigned by the
    dual-taxonomy classifier (binary presence), so the textual output never
    contradicts the severity bucket decision.
    """
    from bench_cleanser.models import TaskContaminationLabel

    assigned = {tl.label for tl in task_labels}
    recs: list[str] = []

    if TaskContaminationLabel.OVER_PATCH in assigned:
        recs.append(
            f"OVER_PATCH: {patch_analysis.unrelated_count} hunk(s) modify code "
            f"unrelated to the problem description."
        )

    if TaskContaminationLabel.OVER_TEST in assigned:
        parts = []
        if test_analysis.off_topic_assertions > 0:
            parts.append(f"{test_analysis.off_topic_assertions} OFF_TOPIC assertions")
        if test_analysis.unrelated_count > 0:
            parts.append(f"{test_analysis.unrelated_count} UNRELATED tests")
        if test_analysis.has_modified_tests:
            parts.append("pre-existing tests modified")
        detail = "; ".join(parts) if parts else "F2P tests exceed problem scope"
        recs.append(f"OVER_TEST: {detail}.")

    if TaskContaminationLabel.APPROACH_LOCK in assigned:
        if cross_ref and cross_ref.has_coupling:
            tests = [cd.test_name for cd in cross_ref.couplings]
            recs.append(
                f"APPROACH_LOCK: {len(cross_ref.couplings)} overpatch-overtest "
                f"coupling(s) — tests [{', '.join(tests)}] require UNRELATED "
                f"patch hunks to pass."
            )
        else:
            recs.append(
                "APPROACH_LOCK: F2P tests require a specific implementation approach "
                "not determined by the problem statement."
            )

    if TaskContaminationLabel.UNCLEAR_DESCRIPTION in assigned:
        recs.append("UNCLEAR_DESCRIPTION: Problem statement is ambiguous — multiple valid interpretations.")

    if TaskContaminationLabel.HIDDEN_CONTEXT in assigned:
        recs.append("HIDDEN_CONTEXT: Solution-critical information lives in hints text, not the problem statement.")

    if TaskContaminationLabel.WEAK_COVERAGE in assigned:
        recs.append("WEAK_COVERAGE: F2P tests or gold patch do not fully cover the stated acceptance criteria.")

    if not recs:
        recs.append("No contamination signals detected.")

    return recs
