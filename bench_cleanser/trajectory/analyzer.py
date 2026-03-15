"""Orchestrator for trajectory analysis.

Coordinates loading, classification, and reporting of agent trajectories.
Uses LLM-primary analysis for trajectory classification — heuristics
provide supporting signals but the LLM makes the final decision.
"""

from __future__ import annotations

import json
import logging
import pathlib
from collections import defaultdict
from typing import Any

from bench_cleanser.models import ContaminationReportV2, RootCause, TaskRecord
from bench_cleanser.trajectory.classifier import (
    classify_cross_agent,
    classify_heuristic_only,
    classify_with_llm,
    extract_heuristic_signals,
)
from bench_cleanser.trajectory.loader import load_trajectories
from bench_cleanser.trajectory.models import (
    LeakagePattern,
    TrajectoryAnalysis,
    TrajectoryRecord,
)

logger = logging.getLogger(__name__)


async def analyze_trajectories(
    trajectories: list[TrajectoryRecord],
    gold_patches: dict[str, str],
    f2p_tests: dict[str, list[str]],
    problem_statements: dict[str, str],
    llm: Any | None = None,
    contamination_reports: dict[str, ContaminationReportV2] | None = None,
) -> list[TrajectoryAnalysis]:
    """Analyze a batch of trajectories using LLM-primary classification.

    Args:
        trajectories: Trajectory records to analyze.
        gold_patches: Mapping of instance_id -> gold patch text.
        f2p_tests: Mapping of instance_id -> F2P test name list.
        problem_statements: Mapping of instance_id -> problem statement text.
        llm: LLMClient for trajectory analysis (required for LLM mode).
        contamination_reports: Optional v2 pipeline reports for context.

    Returns:
        List of TrajectoryAnalysis results.
    """
    analyses = []

    for traj in trajectories:
        gold_patch = gold_patches.get(traj.instance_id, "")
        test_names = f2p_tests.get(traj.instance_id, [])
        problem = problem_statements.get(traj.instance_id, "")

        # Extract heuristic signals first (fast)
        heuristic_signals = extract_heuristic_signals(traj, gold_patch, test_names)

        # Build contamination context from pipeline report
        contamination_context = ""
        if contamination_reports and traj.instance_id in contamination_reports:
            report = contamination_reports[traj.instance_id]
            contamination_context = _build_contamination_context(report)

        if llm is not None and problem:
            # LLM-primary classification
            result = await classify_with_llm(
                traj, gold_patch, problem, test_names, llm,
                heuristic_signals=heuristic_signals,
                contamination_context=contamination_context,
            )
        else:
            # Fallback to heuristic-only
            result = classify_heuristic_only(traj, gold_patch, test_names)

        analyses.append(result)

        logger.debug(
            "%s/%s: %s (conf=%.2f, sim=%.2f)",
            traj.instance_id, traj.agent_name,
            result.leakage_pattern.value, result.confidence,
            result.gold_patch_similarity,
        )

    # Tier 3: cross-agent comparison (group by instance_id)
    by_instance: dict[str, list[int]] = defaultdict(list)
    for i, traj in enumerate(trajectories):
        by_instance[traj.instance_id].append(i)

    for iid, indices in by_instance.items():
        if len(indices) >= 2:
            group_analyses = [analyses[i] for i in indices]
            group_trajs = [trajectories[i] for i in indices]
            updated = classify_cross_agent(group_analyses, group_trajs)
            for idx, analysis in zip(indices, updated):
                analyses[idx] = analysis

    return analyses


def _build_contamination_context(report: ContaminationReportV2) -> str:
    """Build contamination context string from a pipeline report."""
    lines = []
    lines.append(f"Severity: {report.severity.value} (combined score: {report.combined_score:.3f})")
    lines.append(f"EXCESS_PATCH: {report.excess_patch.score:.3f} "
                 f"({report.excess_patch.unrelated_count} UNRELATED / {report.excess_patch.total_hunks} hunks)")
    lines.append(f"EXCESS_TEST: {report.excess_test.score:.3f} "
                 f"({report.excess_test.off_topic_assertions} OFF_TOPIC / "
                 f"{report.excess_test.total_assertions} assertions)")
    if report.root_causes:
        lines.append(f"Root causes: {', '.join(rc.value for rc in report.root_causes)}")
    lines.append(f"Core requirement: {report.intent.core_requirement[:300]}")
    return "\n".join(lines)


def generate_trajectory_summary(
    analyses: list[TrajectoryAnalysis],
) -> str:
    """Generate a markdown summary of trajectory analysis results."""
    lines = ["## Trajectory Analysis Results\n"]

    # Summary statistics
    pattern_counts: dict[str, int] = defaultdict(int)
    for a in analyses:
        pattern_counts[a.leakage_pattern.value] += 1

    lines.append("### Overview\n")
    lines.append(f"- **Total trajectories analyzed:** {len(analyses)}")
    for pattern, count in sorted(pattern_counts.items()):
        pct = count / max(len(analyses), 1) * 100
        lines.append(f"- **{pattern}:** {count} ({pct:.1f}%)")
    lines.append("")

    # Per-instance detail
    by_instance: dict[str, list[TrajectoryAnalysis]] = defaultdict(list)
    for a in analyses:
        by_instance[a.instance_id].append(a)

    lines.append("### Per-Instance Results\n")

    for iid, instance_analyses in sorted(by_instance.items()):
        lines.append(f"#### `{iid}`\n")
        lines.append(
            "| Agent | Pattern | Confidence | "
            "Gold Sim | Pip Installs | Test Refs | Behavior Summary |"
        )
        lines.append("|---|---|---|---|---|---|---|")

        for a in instance_analyses:
            behavior = a.agent_behavior_summary[:100] if a.agent_behavior_summary else ""
            pip_str = str(len(a.pip_install_commands))
            ref_str = str(len(a.test_references))
            lines.append(
                f"| {a.agent_name} | **{a.leakage_pattern.value}** | "
                f"{a.confidence:.2f} | {a.gold_patch_similarity:.2f} | "
                f"{pip_str} | {ref_str} | {behavior} |"
            )

        # Add causal chain if available
        for a in instance_analyses:
            if a.causal_chain:
                lines.append(f"\n**Causal chain ({a.agent_name}):** {a.causal_chain}")
            if a.llm_reasoning:
                lines.append(f"\n<details><summary>LLM reasoning ({a.agent_name})</summary>\n")
                lines.append(a.llm_reasoning)
                lines.append("\n</details>")

        lines.append("")

    return "\n".join(lines)


def compute_leakage_rates(
    analyses: list[TrajectoryAnalysis],
) -> dict[str, dict[str, Any]]:
    """Compute per-agent leakage statistics.

    Returns a dict mapping agent_name to their stats.
    """
    by_agent: dict[str, list[TrajectoryAnalysis]] = defaultdict(list)
    for a in analyses:
        by_agent[a.agent_name].append(a)

    rates = {}
    for agent_name, agent_analyses in by_agent.items():
        total = len(agent_analyses)
        genuine = sum(
            1 for a in agent_analyses
            if a.leakage_pattern == LeakagePattern.GENUINE_SOLUTION
        )
        leaked = sum(
            1 for a in agent_analyses
            if a.leakage_pattern in (
                LeakagePattern.GOLD_PATCH_LEAK,
                LeakagePattern.PACKAGE_LEAK,
                LeakagePattern.TEST_AWARE,
            )
        )
        partial = sum(
            1 for a in agent_analyses
            if a.leakage_pattern == LeakagePattern.PARTIAL_MATCH
        )
        mean_sim = (
            sum(a.gold_patch_similarity for a in agent_analyses) / total
            if total > 0 else 0.0
        )

        rates[agent_name] = {
            "total": total,
            "genuine": genuine,
            "leaked": leaked,
            "partial": partial,
            "leakage_rate": leaked / total if total > 0 else 0.0,
            "mean_gold_patch_similarity": round(mean_sim, 4),
        }

    return rates


def generate_narrative(
    report: ContaminationReportV2,
    record: TaskRecord,
    analyses: list[TrajectoryAnalysis],
) -> str:
    """Generate an end-to-end narrative for a contaminated task.

    Produces a complete story starting from the contaminated task,
    through agent evaluation behavior, to a focused diagnosis.
    """
    lines = []
    iid = report.instance_id

    # Header
    lines.append(f"## Contamination Narrative: `{iid}`\n")

    # Task context
    lines.append("### Task Context\n")
    lines.append(f"**Repository:** `{record.repo}` (version {record.version})")
    lines.append(f"**Core requirement:** {report.intent.core_requirement}")
    lines.append(f"**Severity:** {report.severity.value} (combined: {report.combined_score:.3f})")
    if report.root_causes:
        rc_labels = ", ".join(f"`{rc.value}`" for rc in report.root_causes)
        lines.append(f"**Root causes:** {rc_labels}")
    lines.append("")

    # Contamination signals
    lines.append("### Contamination Signals\n")
    ep = report.excess_patch
    et = report.excess_test
    if ep.unrelated_count > 0:
        lines.append(
            f"- **EXCESS_PATCH ({ep.score:.3f}):** {ep.unrelated_count} of "
            f"{ep.total_hunks} hunks are UNRELATED to the stated problem"
        )
    if et.off_topic_assertions > 0:
        pct = et.off_topic_assertions / max(et.total_assertions, 1) * 100
        lines.append(
            f"- **EXCESS_TEST ({et.score:.3f}):** {et.off_topic_assertions} of "
            f"{et.total_assertions} assertions ({pct:.0f}%) are OFF_TOPIC"
        )
    if report.vague_spec.score > 0.3:
        lines.append(
            f"- **VAGUE_SPEC ({report.vague_spec.score:.3f}):** Problem statement "
            f"is ambiguous"
        )
    lines.append("")

    # Root cause explanation
    if report.root_causes:
        lines.append("### Root Cause Analysis\n")
        for rc in report.root_causes:
            reasoning = report.root_cause_reasoning.get(rc.value, "")
            lines.append(f"**{rc.value}:**")
            if reasoning:
                lines.append(f"{reasoning}")
            else:
                lines.append(_default_root_cause_explanation(rc))
            lines.append("")

    # Agent trajectory analysis
    if analyses:
        lines.append("### Agent Evaluation Behavior\n")
        instance_analyses = [a for a in analyses if a.instance_id == iid]

        for a in instance_analyses:
            lines.append(f"#### Agent: {a.agent_name}\n")
            lines.append(f"- **Classification:** {a.leakage_pattern.value} "
                        f"(confidence: {a.confidence:.2f})")
            lines.append(f"- **Gold patch similarity:** {a.gold_patch_similarity:.1%}")
            if a.pip_install_commands:
                lines.append(f"- **Pip installs:** {', '.join(a.pip_install_commands)}")
            if a.causal_chain:
                lines.append(f"- **Causal chain:** {a.causal_chain}")
            if a.agent_behavior_summary:
                lines.append(f"- **Behavior:** {a.agent_behavior_summary}")
            if a.llm_reasoning:
                lines.append(f"\n> {a.llm_reasoning[:500]}")
            lines.append("")

    # Diagnosis
    lines.append("### Diagnosis\n")
    lines.append(_generate_diagnosis(report, analyses))
    lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _default_root_cause_explanation(rc: RootCause) -> str:
    """Provide default explanation for a root cause category."""
    explanations = {
        RootCause.APPROACH_MISMATCH: (
            "The gold patch implements a fundamentally different approach "
            "than what the problem statement suggests. An agent following "
            "the problem description would produce a different solution."
        ),
        RootCause.DEFERRED_REQUIREMENT: (
            "The F2P tests enforce features that the problem statement "
            "explicitly defers or disclaims. An agent cannot be expected "
            "to implement deferred requirements."
        ),
        RootCause.SCOPE_EXPANSION: (
            "The gold patch and/or tests extend beyond the stated problem "
            "scope. Tests exercise code paths not mentioned in the problem."
        ),
        RootCause.IMPLICIT_CONSENSUS: (
            "The solution requires knowledge from code review discussions "
            "or hints that extend the original problem statement."
        ),
        RootCause.INFRASTRUCTURE_LEAK: (
            "The F2P tests require ancillary infrastructure changes not "
            "described in the feature specification."
        ),
    }
    return explanations.get(rc, "")


def _generate_diagnosis(
    report: ContaminationReportV2,
    analyses: list[TrajectoryAnalysis],
) -> str:
    """Generate a focused diagnosis for a contaminated task."""
    parts = []

    # Impact assessment
    instance_analyses = [a for a in analyses if a.instance_id == report.instance_id]
    leaked_count = sum(
        1 for a in instance_analyses
        if a.leakage_pattern in (
            LeakagePattern.GOLD_PATCH_LEAK,
            LeakagePattern.PACKAGE_LEAK,
            LeakagePattern.TEST_AWARE,
        )
    )
    total = len(instance_analyses)

    if total > 0:
        parts.append(
            f"**Agent impact:** {leaked_count}/{total} analyzed agents showed "
            f"leakage patterns on this task."
        )

    # Actionable recommendation
    if report.excess_test.off_topic_assertions > 0:
        parts.append(
            f"**Action:** Remove or quarantine {report.excess_test.off_topic_assertions} "
            f"OFF_TOPIC assertions from the test patch."
        )
    if report.excess_patch.unrelated_count > 0:
        parts.append(
            f"**Action:** Review {report.excess_patch.unrelated_count} UNRELATED "
            f"patch hunks — the gold patch may need to be scoped down."
        )

    return " ".join(parts) if parts else "Task flagged for manual review."


async def run_trajectory_analysis(
    reports_dir: str | pathlib.Path,
    trajectory_source: str,
    output_path: str | pathlib.Path | None = None,
    severity_filter: str = "SEVERE",
    instance_ids: list[str] | None = None,
    agent_name: str = "",
    hf_split: str = "train",
    llm: Any | None = None,
) -> str:
    """High-level entry point: load reports, load trajectories, analyze, report.

    Args:
        reports_dir: Path to v2 pipeline JSON reports.
        trajectory_source: Path or HuggingFace dataset for trajectories.
        output_path: Where to write the markdown report (None = return string).
        severity_filter: Only analyze trajectories for this severity level.
        instance_ids: Only analyze these specific instances.
        agent_name: Override agent name for trajectory source.
        hf_split: HuggingFace dataset split.
        llm: LLMClient for LLM-primary trajectory analysis.

    Returns:
        The markdown report as a string.
    """
    from bench_cleanser.deep_dive import load_reports_from_dir

    # Load contamination reports
    reports = load_reports_from_dir(
        reports_dir, severity_filter=severity_filter, instance_ids=instance_ids,
    )
    logger.info("Found %d matching contamination reports", len(reports))

    if not reports:
        return "No matching contamination reports found."

    # Build lookup dicts
    target_ids = {r.instance_id for r in reports}
    gold_patches: dict[str, str] = {}
    f2p_tests: dict[str, list[str]] = {}
    problem_statements: dict[str, str] = {}
    contamination_reports: dict[str, ContaminationReportV2] = {}

    # Load TaskRecords for gold patches, F2P tests, and problem statements
    from bench_cleanser.data_loader import load_single_task
    for report in reports:
        record = load_single_task(report.instance_id)
        if record:
            gold_patches[report.instance_id] = record.patch
            f2p_tests[report.instance_id] = record.fail_to_pass
            problem_statements[report.instance_id] = record.problem_statement
        contamination_reports[report.instance_id] = report

    # Load trajectories
    trajectories = load_trajectories(
        trajectory_source,
        instance_ids=target_ids,
        agent_name=agent_name,
        hf_split=hf_split,
    )
    logger.info("Loaded %d trajectories for %d target instances",
                len(trajectories), len(target_ids))

    if not trajectories:
        return "No trajectories found for the target instances."

    # Analyze with LLM-primary approach
    analyses = await analyze_trajectories(
        trajectories, gold_patches, f2p_tests, problem_statements,
        llm=llm,
        contamination_reports=contamination_reports,
    )

    # Generate report
    summary = generate_trajectory_summary(analyses)

    # Add leakage rates
    rates = compute_leakage_rates(analyses)
    summary += "\n### Per-Agent Leakage Rates\n\n"
    summary += "| Agent | Total | Genuine | Leaked | Partial | Leakage Rate | Mean Similarity |\n"
    summary += "|---|---|---|---|---|---|---|\n"
    for agent, stats in sorted(rates.items()):
        summary += (
            f"| {agent} | {stats['total']} | {stats['genuine']} | "
            f"{stats['leaked']} | {stats['partial']} | "
            f"{stats['leakage_rate']:.1%} | "
            f"{stats['mean_gold_patch_similarity']:.3f} |\n"
        )

    # Generate end-to-end narratives for each instance
    records_map: dict[str, TaskRecord] = {}
    for report in reports:
        record = load_single_task(report.instance_id)
        if record:
            records_map[report.instance_id] = record

    summary += "\n---\n\n# End-to-End Contamination Narratives\n"
    for report in reports:
        if report.instance_id in records_map:
            summary += "\n" + generate_narrative(
                report, records_map[report.instance_id], analyses,
            )

    # Write output
    if output_path:
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(summary, encoding="utf-8")
        logger.info("Trajectory analysis written to %s", out)

    # Write JSON results
    if output_path:
        json_path = pathlib.Path(output_path).with_suffix(".json")
        json_data = {
            "analyses": [a.to_dict() for a in analyses],
            "leakage_rates": rates,
        }
        json_path.write_text(
            json.dumps(json_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return summary
