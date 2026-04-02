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

from bench_cleanser.models import ContaminationReport, TaskRecord
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
    contamination_reports: dict[str, ContaminationReport] | None = None,
) -> list[TrajectoryAnalysis]:
    import asyncio

    async def _analyze_one(traj: TrajectoryRecord) -> TrajectoryAnalysis:
        gold_patch = gold_patches.get(traj.instance_id, "")
        test_names = f2p_tests.get(traj.instance_id, [])
        problem = problem_statements.get(traj.instance_id, "")

        heuristic_signals = extract_heuristic_signals(traj, gold_patch, test_names)

        contamination_context = ""
        if contamination_reports and traj.instance_id in contamination_reports:
            report = contamination_reports[traj.instance_id]
            contamination_context = _build_contamination_context(report)

        if llm is not None and problem:
            result = await classify_with_llm(
                traj, gold_patch, problem, test_names, llm,
                heuristic_signals=heuristic_signals,
                contamination_context=contamination_context,
            )
        else:
            result = classify_heuristic_only(traj, gold_patch, test_names)

        logger.debug(
            "%s/%s: %s (conf=%.2f, sim=%.2f)",
            traj.instance_id, traj.agent_name,
            result.leakage_pattern.value, result.confidence,
            result.gold_patch_similarity,
        )
        return result

    # Run all trajectory analyses in parallel
    analyses = await asyncio.gather(*[_analyze_one(t) for t in trajectories])

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


def _build_contamination_context(report: ContaminationReport) -> str:
    lines = []
    lines.append(f"Severity: {report.severity.value}")

    labels = [tl.label.value for tl in report.task_labels]
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")

    ep = report.excess_patch
    if ep.has_excess:
        lines.append(f"SCOPE_CREEP: {ep.unrelated_count} UNRELATED / {ep.total_hunks} hunks")

    et = report.excess_test
    if et.has_excess:
        lines.append(
            f"WIDE_TESTS: {et.off_topic_assertions} OFF_TOPIC / "
            f"{et.total_assertions} assertions"
        )

    lines.append(f"Core requirement: {report.intent.core_requirement[:300]}")
    return "\n".join(lines)


def generate_trajectory_summary(
    analyses: list[TrajectoryAnalysis],
) -> str:
    lines = ["## Trajectory Analysis Results\n"]

    pattern_counts: dict[str, int] = defaultdict(int)
    for a in analyses:
        pattern_counts[a.leakage_pattern.value] += 1

    lines.append("### Overview\n")
    lines.append(f"- **Total trajectories analyzed:** {len(analyses)}")
    for pattern, count in sorted(pattern_counts.items()):
        pct = count / max(len(analyses), 1) * 100
        lines.append(f"- **{pattern}:** {count} ({pct:.1f}%)")
    lines.append("")

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
    report: ContaminationReport,
    record: TaskRecord,
    analyses: list[TrajectoryAnalysis],
) -> str:
    lines = []
    iid = report.instance_id

    lines.append(f"## Contamination Narrative: `{iid}`\n")

    lines.append("### Task Context\n")
    lines.append(f"**Repository:** `{record.repo}` (version {record.version})")
    lines.append(f"**Core requirement:** {report.intent.core_requirement}")
    lines.append(f"**Severity:** {report.severity.value}")
    labels = ", ".join(f"`{tl.label.value}`" for tl in report.task_labels)
    if labels:
        lines.append(f"**Labels:** {labels}")
    lines.append("")

    lines.append("### Contamination Signals\n")
    ep = report.excess_patch
    et = report.excess_test
    if ep.has_excess:
        lines.append(
            f"- **SCOPE_CREEP:** {ep.unrelated_count} of "
            f"{ep.total_hunks} hunks are UNRELATED to the stated problem"
        )
    if et.has_excess:
        parts = []
        if et.off_topic_assertions > 0:
            pct = et.off_topic_assertions / max(et.total_assertions, 1) * 100
            parts.append(f"{et.off_topic_assertions} of {et.total_assertions} assertions ({pct:.0f}%) are OFF_TOPIC")
        if et.unrelated_count > 0:
            parts.append(f"{et.unrelated_count} UNRELATED tests")
        for part in parts:
            lines.append(f"- **WIDE_TESTS:** {part}")
    if report.vague_spec.score > 0.3:
        lines.append(f"- **VAGUE_SPEC:** Problem statement has significant ambiguity ({report.vague_spec.score:.2f})")
    lines.append("")

    if report.task_labels:
        lines.append("### Label Analysis\n")
        for tl in report.task_labels:
            lines.append(f"**{tl.label.value}** (confidence: {tl.confidence:.2f}):")
            if tl.reasoning:
                lines.append(f"  {tl.reasoning}")
            if tl.evidence:
                for ev in tl.evidence[:3]:
                    lines.append(f"  - {ev}")
        lines.append("")

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

    lines.append("### Diagnosis\n")
    lines.append(_generate_diagnosis(report, analyses))
    lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _generate_diagnosis(
    report: ContaminationReport,
    analyses: list[TrajectoryAnalysis],
) -> str:
    parts = []

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
    api_key: str = "",
    model_filter: str = "",
) -> str:
    from bench_cleanser.deep_dive import load_reports_from_dir

    reports = load_reports_from_dir(
        reports_dir, severity_filter=severity_filter, instance_ids=instance_ids,
    )
    logger.info("Found %d matching contamination reports", len(reports))

    if not reports:
        return "No matching contamination reports found."

    target_ids = {r.instance_id for r in reports}
    gold_patches: dict[str, str] = {}
    f2p_tests: dict[str, list[str]] = {}
    problem_statements: dict[str, str] = {}
    contamination_reports: dict[str, ContaminationReport] = {}

    from bench_cleanser.data_loader import load_single_task
    for report in reports:
        record = load_single_task(report.instance_id)
        if record:
            gold_patches[report.instance_id] = record.patch
            f2p_tests[report.instance_id] = record.fail_to_pass
            problem_statements[report.instance_id] = record.full_problem_context
        contamination_reports[report.instance_id] = report

    trajectories = load_trajectories(
        trajectory_source,
        instance_ids=target_ids,
        agent_name=agent_name,
        hf_split=hf_split,
        api_key=api_key,
        model_filter=model_filter,
    )
    logger.info("Loaded %d trajectories for %d target instances",
                len(trajectories), len(target_ids))

    if not trajectories:
        return "No trajectories found for the target instances."

    analyses = await analyze_trajectories(
        trajectories, gold_patches, f2p_tests, problem_statements,
        llm=llm,
        contamination_reports=contamination_reports,
    )

    summary = generate_trajectory_summary(analyses)

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

    if output_path:
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(summary, encoding="utf-8")
        logger.info("Trajectory analysis written to %s", out)

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
