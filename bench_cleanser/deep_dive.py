"""Auto-generate deep-dive case study reports from v2 pipeline JSON reports.

Post-processing module that reads completed v2 JSON reports + original dataset
records and produces Case A-D style markdown documents with assertion-level
traceability.  Separated from the pipeline so deep dives can be regenerated
without re-running expensive LLM scoring.
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bench_cleanser.models import (
    ContaminationReportV2,
    RootCause,
    Severity,
    TaskRecord,
)

logger = logging.getLogger(__name__)

# Case letter sequence for labelling
_CASE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class DeepDiveContext:
    """All data needed to render a single deep-dive case study."""
    case_index: int          # 0-based
    report: ContaminationReportV2
    record: TaskRecord


# ──────────────────────────────────────────────────────────────────────
# Section generators — each returns a markdown string
# ──────────────────────────────────────────────────────────────────────


def _case_letter(idx: int) -> str:
    if idx < len(_CASE_LETTERS):
        return _CASE_LETTERS[idx]
    return f"Case{idx + 1}"


def generate_header(ctx: DeepDiveContext) -> str:
    """Generate the case header with anchor."""
    letter = _case_letter(ctx.case_index)
    iid = ctx.record.instance_id
    anchor = f'<a name="case-{letter.lower()}-{iid}"></a>'
    return f"""{anchor}
## Case {letter}: `{iid}`

"""


def generate_dataset_record_table(ctx: DeepDiveContext) -> str:
    """X.1: HuggingFace metadata table."""
    letter = _case_letter(ctx.case_index)
    r = ctx.record
    f2p_str = json.dumps(r.fail_to_pass)
    p2p_count = len(r.pass_to_pass)

    lines = [
        f"### {letter}.1 HuggingFace Dataset Record\n",
        "| Field | Value |",
        "|---|---|",
        f"| **instance_id** | `{r.instance_id}` |",
        f"| **repo** | `{r.repo}` |",
        f"| **base_commit** | `{r.base_commit}` |",
        f"| **version** | `{r.version}` |",
        f"| **created_at** | `{r.created_at}` |",
        f"| **environment_setup_commit** | `{r.environment_setup_commit}` |",
        f"| **FAIL_TO_PASS** | `{f2p_str}` |",
        f"| **PASS_TO_PASS** | {p2p_count} tests |",
        "",
    ]
    return "\n".join(lines)


def generate_problem_statement_section(ctx: DeepDiveContext) -> str:
    """X.2: Verbatim problem statement."""
    letter = _case_letter(ctx.case_index)
    ps = ctx.record.problem_statement.strip()
    return f"""### {letter}.2 Verbatim Problem Statement

> {_blockquote(ps)}

"""


def generate_hints_section(ctx: DeepDiveContext) -> str:
    """X.3: Hints text (if non-empty)."""
    letter = _case_letter(ctx.case_index)
    hints = ctx.record.hints_text.strip()
    if not hints:
        return f"### {letter}.3 Hints Text\n\n*(No hints text provided for this instance.)*\n\n"
    # Truncate very long hints
    if len(hints) > 4000:
        hints = hints[:4000] + "\n\n*(truncated — full hints text is " + str(len(ctx.record.hints_text)) + " characters)*"
    return f"""### {letter}.3 Hints Text

> {_blockquote(hints)}

"""


def generate_gold_patch_section(ctx: DeepDiveContext) -> str:
    """X.4: Gold patch with per-hunk annotations from report JSON."""
    letter = _case_letter(ctx.case_index)
    patch = ctx.record.patch.strip()
    ep = ctx.report.excess_patch

    lines = [f"### {letter}.4 Gold Patch Analysis\n"]

    # Hunk verdict summary table
    if ep.hunk_verdicts:
        lines.append("#### Per-Hunk Verdicts\n")
        lines.append("| Hunk | File | Verdict | Confidence | Reasoning |")
        lines.append("|---|---|---|---|---|")
        for h in ep.hunk_verdicts:
            verdict_fmt = f"**{h.verdict.value}**" if h.verdict.value == "UNRELATED" else h.verdict.value
            reason = h.reasoning[:200].replace("|", "\\|") if h.reasoning else ""
            lines.append(
                f"| {h.hunk_index} | `{h.file_path}` | {verdict_fmt} "
                f"| {h.confidence:.2f} | {reason} |"
            )
        lines.append("")

    # Score summary
    lines.append("#### Patch Score Summary\n")
    lines.append(f"- **Total hunks:** {ep.total_hunks}")
    lines.append(f"- **REQUIRED:** {ep.required_count}")
    lines.append(f"- **ANCILLARY:** {ep.ancillary_count}")
    lines.append(f"- **UNRELATED:** {ep.unrelated_count}")
    lines.append(f"- **EXCESS_PATCH score:** {ep.score:.4f}")
    lines.append("")

    # Raw patch in fenced block
    lines.append("<details>")
    lines.append("<summary>Full gold patch diff</summary>\n")
    lines.append("```diff")
    lines.append(patch)
    lines.append("```\n")
    lines.append("</details>\n")

    return "\n".join(lines)


def generate_test_analysis_section(ctx: DeepDiveContext) -> str:
    """X.5: Line-by-line assertion analysis with ON_TOPIC/OFF_TOPIC."""
    letter = _case_letter(ctx.case_index)
    et = ctx.report.excess_test

    lines = [f"### {letter}.5 Test Patch Analysis\n"]

    # Test verdict summary table
    if et.test_verdicts:
        lines.append("#### Per-Test Verdicts\n")
        lines.append("| Test | Verdict | ON_TOPIC | OFF_TOPIC |")
        lines.append("|---|---|---|---|")
        for t in et.test_verdicts:
            on = t.on_topic_count
            off = t.off_topic_count
            lines.append(
                f"| `{t.test_name}` | {t.intent_match.value} | {on} | {off} |"
            )
        total_on = et.on_topic_assertions
        total_off = et.off_topic_assertions
        lines.append(f"| **Total** | | **{total_on}** | **{total_off}** |")
        lines.append("")

    # Per-assertion detail for each test
    for t in et.test_verdicts:
        if t.assertion_verdicts:
            lines.append(f"#### `{t.test_name}` — Per-Assertion Verdicts\n")
            lines.append("| # | Assertion | Verdict | Reason |")
            lines.append("|---|---|---|---|")
            for i, a in enumerate(t.assertion_verdicts):
                stmt = a.statement[:120].replace("|", "\\|") if a.statement else ""
                reason = a.reason[:200].replace("|", "\\|") if a.reason else ""
                lines.append(
                    f"| {i} | `{stmt}` | **{a.verdict.value}** | {reason} |"
                )
            lines.append("")

    # Score summary
    lines.append("#### Test Score Summary\n")
    lines.append(f"- **Total tests:** {et.total_tests}")
    lines.append(f"- **ALIGNED:** {et.aligned_count}")
    lines.append(f"- **TANGENTIAL:** {et.tangential_count}")
    lines.append(f"- **UNRELATED:** {et.unrelated_count}")
    lines.append(f"- **Total assertions:** {et.total_assertions}")
    lines.append(f"- **ON_TOPIC assertions:** {et.on_topic_assertions}")
    lines.append(f"- **OFF_TOPIC assertions:** {et.off_topic_assertions}")
    lines.append(f"- **Has modified tests:** {'Yes' if et.has_modified_tests else 'No'}")
    lines.append(f"- **EXCESS_TEST score:** {et.score:.4f}")
    lines.append("")

    # Test patch in fenced block
    test_patch = ctx.record.test_patch.strip()
    if test_patch:
        lines.append("<details>")
        lines.append("<summary>Full test patch diff</summary>\n")
        lines.append("```diff")
        lines.append(test_patch)
        lines.append("```\n")
        lines.append("</details>\n")

    return "\n".join(lines)


def generate_pipeline_verdict_section(ctx: DeepDiveContext) -> str:
    """X.6: Intent extraction + scoring breakdown with formula verification."""
    letter = _case_letter(ctx.case_index)
    rpt = ctx.report
    intent = rpt.intent

    ep = rpt.excess_patch.score
    et = rpt.excess_test.score
    vs = rpt.vague_spec.score
    manual = 1.0 - (1.0 - ep) * (1.0 - et) * (1.0 - vs)

    lines = [f"### {letter}.6 Pipeline Verdict Detail\n"]

    # Intent extraction
    lines.append("#### Intent Extraction (Stage 2)\n")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **core_requirement** | {intent.core_requirement} |")
    lines.append(f"| **behavioral_contract** | {intent.behavioral_contract[:300]} |")
    ac_str = "; ".join(f"({i+1}) {c}" for i, c in enumerate(intent.acceptance_criteria))
    lines.append(f"| **acceptance_criteria** | {ac_str} |")
    lines.append(f"| **out_of_scope** | {intent.out_of_scope} |")
    lines.append(f"| **ambiguity_score** | {intent.ambiguity_score:.2f} |")
    lines.append("")

    # Scoring breakdown
    lines.append("#### Scoring Breakdown\n")
    lines.append("| Component | Score | Description |")
    lines.append("|---|---|---|")
    lines.append(
        f"| EXCESS_PATCH | {ep:.4f} | "
        f"{rpt.excess_patch.unrelated_count} UNRELATED + "
        f"{rpt.excess_patch.ancillary_count} ANCILLARY / "
        f"{rpt.excess_patch.total_hunks} total hunks |"
    )
    lines.append(
        f"| EXCESS_TEST | {et:.4f} | "
        f"{rpt.excess_test.off_topic_assertions} OFF_TOPIC / "
        f"{rpt.excess_test.total_assertions} total assertions |"
    )
    lines.append(
        f"| VAGUE_SPEC | {vs:.4f} | "
        f"LLM ambiguity assessment |"
    )
    lines.append("")

    # Formula verification
    lines.append(
        f"$$\\text{{combined}} = 1 - (1 - {ep:.4f})(1 - {et:.4f})(1 - {vs:.4f}) "
        f"= \\mathbf{{{manual:.4f}}}$$"
    )
    lines.append("")
    lines.append(
        f"**Report combined_score:** {rpt.combined_score:.4f} | "
        f"**Manual calculation:** {manual:.4f} | "
        f"**Match:** {'Yes' if abs(manual - rpt.combined_score) < 0.002 else 'No'}"
    )
    lines.append("")

    # Recommendations
    if rpt.recommendations:
        lines.append("#### Recommendations\n")
        for rec in rpt.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)


def generate_independent_analysis_section(
    ctx: DeepDiveContext,
    llm_analysis: str | None = None,
) -> str:
    """X.7: Root cause taxonomy and independent analysis."""
    letter = _case_letter(ctx.case_index)
    rpt = ctx.report

    lines = [f"### {letter}.7 Root Cause Analysis\n"]

    # Root cause labels
    if rpt.root_causes:
        lines.append("#### Root Cause Classification\n")
        lines.append("| Root Cause | Reasoning |")
        lines.append("|---|---|")
        for rc in rpt.root_causes:
            reasoning = rpt.root_cause_reasoning.get(rc.value, "")
            if not reasoning:
                reasoning = _default_root_cause_short(rc)
            reasoning_clean = reasoning[:300].replace("|", "\\|")
            lines.append(f"| **{rc.value}** | {reasoning_clean} |")
        lines.append("")
    else:
        lines.append("*(Root cause classification not yet available — re-run pipeline to auto-detect.)*\n")

    # Independent analysis
    lines.append(f"### {letter}.8 Independent Analysis\n")

    if llm_analysis:
        lines.append(llm_analysis)
    else:
        lines.append(_auto_analyze(ctx))

    lines.append("")
    confidence = "HIGH" if rpt.combined_score >= 0.9 else (
        "MEDIUM-HIGH" if rpt.combined_score >= 0.7 else "MODERATE"
    )
    lines.append(
        f"**Contamination verdict: CONFIRMED — {confidence} CONFIDENCE.**"
    )
    lines.append("")
    lines.append("---\n")
    return "\n".join(lines)


def _auto_analyze(ctx: DeepDiveContext) -> str:
    """Generate basic analysis from report data without LLM call."""
    rpt = ctx.report
    et = rpt.excess_test
    ep = rpt.excess_patch

    findings = []

    # Patch analysis
    if ep.unrelated_count > 0:
        findings.append(
            f"**Patch approach divergence:** {ep.unrelated_count} of "
            f"{ep.total_hunks} gold patch hunk(s) are classified as UNRELATED "
            f"to the problem statement, indicating the gold patch implements "
            f"changes beyond what was described."
        )
    if ep.ancillary_count > 0 and ep.ancillary_count == ep.total_hunks - ep.required_count:
        findings.append(
            f"**Infrastructure overhead:** {ep.ancillary_count} ANCILLARY "
            f"hunk(s) add supporting changes not directly derivable from the "
            f"problem statement."
        )

    # Test analysis
    if et.off_topic_assertions > 0:
        pct = et.off_topic_assertions / max(et.total_assertions, 1) * 100
        findings.append(
            f"**Off-topic test assertions:** {et.off_topic_assertions} of "
            f"{et.total_assertions} assertions ({pct:.0f}%) verify behavior "
            f"beyond the stated problem scope."
        )

    # Modified tests
    if et.has_modified_tests:
        findings.append(
            "**Modified existing tests:** The test patch modifies pre-existing "
            "test functions, changing expected values to match the gold patch's "
            "specific implementation approach."
        )

    # Unrelated tests
    if et.unrelated_count > 0:
        findings.append(
            f"**Unrelated tests:** {et.unrelated_count} F2P test(s) are "
            f"fully unrelated to the problem statement."
        )

    if not findings:
        findings.append(
            "The pipeline flagged this task as SEVERE based on the combined "
            "scoring formula, but no single strong contamination signal dominates."
        )

    return "\n\n".join(findings)


# ──────────────────────────────────────────────────────────────────────
# Cross-case synthesis
# ──────────────────────────────────────────────────────────────────────


def generate_cross_case_synthesis(cases: list[DeepDiveContext]) -> str:
    """Generate the cross-case synthesis section with 5-category taxonomy."""
    lines = ["## Cross-Case Synthesis\n"]

    # Root cause taxonomy
    lines.append("### Root Cause Taxonomy\n")
    lines.append("| Root Cause | Cases | Description |")
    lines.append("|---|---|---|")

    rc_cases: dict[str, list[str]] = {}
    for ctx in cases:
        letter = _case_letter(ctx.case_index)
        for rc in ctx.report.root_causes:
            rc_cases.setdefault(rc.value, []).append(letter)

    rc_descriptions = {
        "APPROACH_MISMATCH": "Problem suggests fix X; gold patch implements fix Y; tests enforce Y",
        "DEFERRED_REQUIREMENT": "Tests enforce features explicitly deferred in problem statement",
        "SCOPE_EXPANSION": "Tests verify behavior explicitly beyond the stated problem scope",
        "IMPLICIT_CONSENSUS": "Solution requires knowledge from code review not in problem",
        "INFRASTRUCTURE_LEAK": "Tests require infrastructure changes not described in the spec",
    }

    for rc_name in ["APPROACH_MISMATCH", "DEFERRED_REQUIREMENT", "SCOPE_EXPANSION",
                     "IMPLICIT_CONSENSUS", "INFRASTRUCTURE_LEAK"]:
        case_letters = rc_cases.get(rc_name, [])
        if case_letters:
            desc = rc_descriptions.get(rc_name, "")
            lines.append(f"| **{rc_name}** | {', '.join(case_letters)} | {desc} |")

    # Fallback: also detect from score patterns for cases without root causes
    for ctx in cases:
        if not ctx.report.root_causes:
            letter = _case_letter(ctx.case_index)
            ep = ctx.report.excess_patch
            et = ctx.report.excess_test
            if ep.unrelated_count > 0 and ep.score >= 0.5:
                if "APPROACH_MISMATCH" not in rc_cases:
                    rc_cases["APPROACH_MISMATCH"] = []
                lines.append(
                    f"| **APPROACH_MISMATCH** (inferred) | {letter} | "
                    f"High UNRELATED hunk count suggests approach divergence |"
                )
            if et.off_topic_assertions > 0 and et.score >= 0.5:
                if "SCOPE_EXPANSION" not in rc_cases:
                    rc_cases["SCOPE_EXPANSION"] = []
                lines.append(
                    f"| **SCOPE_EXPANSION** (inferred) | {letter} | "
                    f"High OFF_TOPIC assertion count suggests scope expansion |"
                )
    lines.append("")

    # Scoring validation table
    lines.append("### Scoring Formula Validation\n")
    lines.append(
        "All cases verified against: "
        "$\\text{combined} = 1 - (1 - \\text{EP}) \\times (1 - \\text{ET}) \\times (1 - \\text{VS})$\n"
    )
    lines.append("| Case | Instance | EP | ET | VS | Manual Calc | Report | Match |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for ctx in cases:
        letter = _case_letter(ctx.case_index)
        rpt = ctx.report
        ep = rpt.excess_patch.score
        et = rpt.excess_test.score
        vs = rpt.vague_spec.score
        manual = 1.0 - (1.0 - ep) * (1.0 - et) * (1.0 - vs)
        match = "Yes" if abs(manual - rpt.combined_score) < 0.002 else "No"
        lines.append(
            f"| {letter} | `{rpt.instance_id}` | {ep:.4f} | {et:.4f} | "
            f"{vs:.4f} | {manual:.4f} | {rpt.combined_score:.4f} | {match} |"
        )
    lines.append("")

    # Confidence summary
    lines.append("### Confidence Summary\n")
    lines.append("| Case | Instance | Combined | Primary Signal | Root Causes | Confidence |")
    lines.append("|---|---|---|---|---|---|")

    for ctx in cases:
        letter = _case_letter(ctx.case_index)
        rpt = ctx.report
        signals = {
            "Excess patch": rpt.excess_patch.score,
            "Excess test": rpt.excess_test.score,
            "Vague spec": rpt.vague_spec.score,
        }
        primary = max(signals, key=signals.get)  # type: ignore[arg-type]
        confidence = "HIGH" if rpt.combined_score >= 0.9 else (
            "MEDIUM-HIGH" if rpt.combined_score >= 0.7 else "MODERATE"
        )
        rc_str = ", ".join(rc.value for rc in rpt.root_causes) if rpt.root_causes else "—"
        lines.append(
            f"| {letter} | `{rpt.instance_id}` | {rpt.combined_score:.3f} | "
            f"{primary} ({signals[primary]:.3f}) | {rc_str} | **{confidence}** |"
        )
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Assembly — combine all sections into a complete document
# ──────────────────────────────────────────────────────────────────────


def generate_deep_dive_document(
    cases: list[DeepDiveContext],
    title: str = "Deep-Dive Case Studies: SEVERE Contamination Cases",
    pipeline_version: str = "v2",
    dataset_name: str = "SWE-bench Verified",
) -> str:
    """Assemble a complete deep-dive markdown document from case contexts."""
    now = datetime.now().strftime("%Y-%m-%d")

    parts = []

    # Document header
    parts.append(f"# {title}\n")
    parts.append(f"> **Generated:** {now}")
    parts.append(f"> **Pipeline:** bench-cleanser {pipeline_version}")
    parts.append(f"> **Dataset:** {dataset_name}")
    parts.append(
        f"> **Cases:** {len(cases)} SEVERE contamination instances "
        f"with assertion-level traceability"
    )
    parts.append("\n---\n")

    # Table of contents
    parts.append("## Table of Contents\n")
    for ctx in cases:
        letter = _case_letter(ctx.case_index)
        iid = ctx.record.instance_id
        anchor = f"case-{letter.lower()}-{iid}"
        parts.append(f"{ctx.case_index + 1}. [Case {letter}: {iid}](#{anchor})")
    parts.append("")
    parts.append("---\n")

    # Per-case sections
    for ctx in cases:
        parts.append(generate_header(ctx))
        parts.append(generate_dataset_record_table(ctx))
        parts.append(generate_problem_statement_section(ctx))
        parts.append(generate_hints_section(ctx))
        parts.append(generate_gold_patch_section(ctx))
        parts.append(generate_test_analysis_section(ctx))
        parts.append(generate_pipeline_verdict_section(ctx))
        parts.append(generate_independent_analysis_section(ctx))

    # Cross-case synthesis
    if len(cases) > 1:
        parts.append(generate_cross_case_synthesis(cases))

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Loading and batch processing
# ──────────────────────────────────────────────────────────────────────


def load_reports_from_dir(
    reports_dir: str | pathlib.Path,
    severity_filter: str | None = "SEVERE",
    instance_ids: list[str] | None = None,
) -> list[ContaminationReportV2]:
    """Load v2 JSON reports from a directory.

    Args:
        reports_dir: Path to the reports directory.
        severity_filter: Only include reports with this severity (None = all).
        instance_ids: Only include these specific instance IDs (None = all).

    Returns:
        List of ContaminationReportV2 objects, sorted by combined_score descending.
    """
    reports_path = pathlib.Path(reports_dir)
    reports = []

    for report_file in reports_path.glob("*.json"):
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            report = ContaminationReportV2.from_dict(data)

            if severity_filter and report.severity.value != severity_filter:
                continue
            if instance_ids and report.instance_id not in instance_ids:
                continue

            reports.append(report)
        except Exception as exc:
            logger.warning("Failed to load report %s: %s", report_file.name, exc)

    reports.sort(key=lambda r: r.combined_score, reverse=True)
    return reports


def load_records_for_reports(
    reports: list[ContaminationReportV2],
) -> dict[str, TaskRecord]:
    """Load TaskRecord objects from HuggingFace for the given reports.

    Returns a dict mapping instance_id to TaskRecord.
    """
    from bench_cleanser.data_loader import load_single_task

    records: dict[str, TaskRecord] = {}
    for report in reports:
        iid = report.instance_id
        try:
            record = load_single_task(iid)
            if record is not None:
                records[iid] = record
            else:
                logger.warning("Instance %s not found in any dataset", iid)
        except Exception as exc:
            logger.warning("Failed to load record for %s: %s", iid, exc)

    return records


def build_deep_dive(
    reports_dir: str | pathlib.Path,
    severity_filter: str | None = "SEVERE",
    instance_ids: list[str] | None = None,
    title: str = "Deep-Dive Case Studies: SEVERE Contamination Cases",
    dataset_name: str = "SWE-bench",
) -> str:
    """High-level entry point: load reports, fetch records, generate document.

    Args:
        reports_dir: Path to the directory containing v2 JSON reports.
        severity_filter: Only include reports with this severity.
        instance_ids: Only include these specific instances.
        title: Document title.
        dataset_name: Dataset name for the header.

    Returns:
        The complete markdown document as a string.
    """
    logger.info("Loading reports from %s", reports_dir)
    reports = load_reports_from_dir(reports_dir, severity_filter, instance_ids)
    logger.info("Found %d matching report(s)", len(reports))

    if not reports:
        return f"# {title}\n\nNo matching reports found.\n"

    logger.info("Loading dataset records from HuggingFace...")
    records = load_records_for_reports(reports)
    logger.info("Loaded %d record(s)", len(records))

    cases = []
    for i, report in enumerate(reports):
        if report.instance_id not in records:
            logger.warning(
                "Skipping %s: no dataset record available", report.instance_id
            )
            continue
        cases.append(DeepDiveContext(
            case_index=i,
            report=report,
            record=records[report.instance_id],
        ))

    return generate_deep_dive_document(
        cases, title=title, dataset_name=dataset_name,
    )


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _blockquote(text: str) -> str:
    """Convert multi-line text to blockquote format."""
    return "\n> ".join(text.split("\n"))


def _default_root_cause_short(rc: RootCause) -> str:
    """Short explanation for a root cause when no LLM reasoning is available."""
    return {
        RootCause.APPROACH_MISMATCH: "Gold patch uses a different approach than problem suggests",
        RootCause.DEFERRED_REQUIREMENT: "Tests enforce features deferred in the problem statement",
        RootCause.SCOPE_EXPANSION: "Gold patch/tests extend beyond stated problem scope",
        RootCause.IMPLICIT_CONSENSUS: "Solution requires knowledge from code review discussions",
        RootCause.INFRASTRUCTURE_LEAK: "Tests require infrastructure changes not in the spec",
    }.get(rc, "")
