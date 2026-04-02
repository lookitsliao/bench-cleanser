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
    ExcessPatchDetail,
    ExcessTestDetail,
    IntentStatement,
    PipelineConfig,
    TaskRecord,
    VagueSpecDetail,
)

logger = logging.getLogger(__name__)


async def build_report(
    intent: IntentStatement,
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    vague_spec: VagueSpecDetail,
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
        intent, excess_patch, excess_test, vague_spec,
        record=record, llm=llm, cross_ref=cross_ref,
    )

    severity = compute_task_severity(task_labels)

    recommendations = _build_recommendations(excess_patch, excess_test, vague_spec, cross_ref)

    return ContaminationReport(
        instance_id=intent.instance_id,
        severity=severity,
        intent=intent,
        excess_patch=excess_patch,
        excess_test=excess_test,
        vague_spec=vague_spec,
        task_labels=task_labels,
        recommendations=recommendations,
    )


def _build_recommendations(
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    vague_spec: VagueSpecDetail,
    cross_ref: CrossReferenceResult | None = None,
) -> list[str]:
    """Build actionable recommendations based on binary signals."""
    recs: list[str] = []

    if excess_patch.has_excess:
        recs.append(
            f"SCOPE_CREEP: {excess_patch.unrelated_count} hunk(s) modify code "
            f"unrelated to the problem description."
        )

    if excess_test.has_excess:
        parts = []
        if excess_test.off_topic_assertions > 0:
            parts.append(f"{excess_test.off_topic_assertions} OFF_TOPIC assertions")
        if excess_test.unrelated_count > 0:
            parts.append(f"{excess_test.unrelated_count} UNRELATED tests")
        recs.append(f"WIDE_TESTS: {'; '.join(parts)} beyond problem scope.")

    if cross_ref and cross_ref.has_circular:
        tests = [cd.test_name for cd in cross_ref.circular_dependencies]
        recs.append(
            f"CROSS_REF: {len(cross_ref.circular_dependencies)} circular "
            f"dependency(ies) — tests [{', '.join(tests)}] require UNRELATED "
            f"patch hunks to pass."
        )

    if vague_spec.score > 0.5:
        recs.append("VAGUE_SPEC: Problem statement has significant ambiguity.")
    elif vague_spec.score > 0.3:
        recs.append("VAGUE_SPEC: Problem statement has moderate ambiguity.")

    if not recs:
        recs.append("No contamination signals detected.")

    return recs
