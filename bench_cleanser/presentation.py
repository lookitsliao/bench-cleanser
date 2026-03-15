"""Generate MARP markdown slide decks from bench-cleanser analysis outputs.

Produces presentation-ready markdown using MARP (Markdown Presentation
Ecosystem) format, which can be converted to HTML/PDF via marp-cli.
Supports KaTeX math, code blocks, and tables natively.
"""

from __future__ import annotations

import json
import logging
import pathlib
from collections import defaultdict
from datetime import datetime
from typing import Any

from bench_cleanser.models import ContaminationReportV2, RootCause, Severity

logger = logging.getLogger(__name__)


def generate_slide_deck(
    reports: list[ContaminationReportV2],
    deep_dive_path: str | pathlib.Path | None = None,
    trajectory_path: str | pathlib.Path | None = None,
    title: str = "SWE-bench Contamination Analysis",
    subtitle: str = "bench-cleanser Findings",
    author: str = "",
) -> str:
    """Generate a complete MARP slide deck from analysis outputs."""
    slides = []

    # Frontmatter
    slides.append(_frontmatter(title))

    # Title
    slides.append(_title_slide(title, subtitle, author))

    # Problem statement
    slides.append(_problem_slide())

    # Methodology overview
    slides.append(_methodology_slide())

    # Scoring formula
    slides.append(_scoring_slide())

    # Root cause taxonomy
    slides.append(_root_cause_taxonomy_slide())

    # Dataset summary
    severity_dist = _compute_severity_distribution(reports)
    slides.append(_dataset_summary_slide(reports, severity_dist))

    # Score distribution
    slides.append(_score_distribution_slide(reports))

    # Root cause distribution
    slides.append(_root_cause_distribution_slide(reports))

    # Case highlights (SEVERE cases)
    severe_reports = [r for r in reports if r.severity == Severity.SEVERE]
    for i, report in enumerate(severe_reports[:8]):
        slides.append(_case_highlight_slide(report, i))

    # Cross-case patterns
    if severe_reports:
        slides.append(_pattern_taxonomy_slide(severe_reports))

    # Agent impact / trajectory
    if trajectory_path:
        trajectory_data = _load_trajectory_data(trajectory_path)
        if trajectory_data:
            slides.append(_trajectory_slide(trajectory_data))
            slides.append(_agent_impact_slide(trajectory_data))

    # Key finding: test patch difficulty
    slides.append(_test_patch_difficulty_slide(severe_reports))

    # Sensitivity analysis
    slides.append(_sensitivity_slide(reports, severity_dist))

    # Recommendations
    slides.append(_recommendations_slide(severe_reports, reports))

    # Appendix
    slides.append(_appendix_methodology_slide())
    slides.append(_appendix_thresholds_slide())

    return "\n".join(slides)


# ──────────────────────────────────────────────────────────────────────
# Individual slide generators
# ──────────────────────────────────────────────────────────────────────


def _frontmatter(title: str) -> str:
    return f"""---
marp: true
theme: default
paginate: true
title: {title}
math: katex
style: |
  section {{
    font-size: 22px;
  }}
  h1 {{
    color: #1a1a2e;
  }}
  h2 {{
    color: #16213e;
  }}
  table {{
    font-size: 16px;
  }}
  .severe {{ color: #e63946; font-weight: bold; }}
  .moderate {{ color: #f4a261; font-weight: bold; }}
  .minor {{ color: #e9c46a; }}
  .clean {{ color: #2a9d8f; }}
  .rc {{ color: #6c5ce7; font-weight: bold; }}
  blockquote {{ font-size: 18px; }}
---
"""


def _title_slide(title: str, subtitle: str, author: str) -> str:
    now = datetime.now().strftime("%B %Y")
    author_line = f"\n**{author}**" if author else ""
    return f"""
# {title}

## {subtitle}
{author_line}
{now}

---
"""


def _problem_slide() -> str:
    return """
# The Problem: SWE-bench Contamination

SWE-bench evaluates AI agents on real-world software engineering tasks.
However, some tasks have **contaminated evaluation criteria**:

- **EXCESS_PATCH**: Gold patch implements changes not described in the issue
  - Agent solves the *stated* problem but fails because the gold patch took a different approach
- **EXCESS_TEST**: F2P tests verify behavior beyond the stated problem
  - Tests assert on undescribed functionality; agent can't know what to implement
- **VAGUE_SPEC**: Problem statement is ambiguous, allowing over-specific tests

> An agent that perfectly solves the stated problem can score **0%** on contaminated tasks.
> This artificially rewards agents with access to the gold patch over those that reason independently.

---
"""


def _methodology_slide() -> str:
    return """
# bench-cleanser: 6-Stage Pipeline

```
┌─────────┐   ┌──────────┐   ┌────────┐   ┌──────────────┐   ┌────────┐   ┌──────────┐
│  PARSE  │──>│   CODE   │──>│ INTENT │──>│    INTENT    │──>│ TRIAGE │──>│  ROOT    │
│         │   │VISITATION│   │EXTRACT │   │   MATCHING   │   │& SCORE │   │  CAUSE   │
└─────────┘   └──────────┘   └────────┘   └──────────────┘   └────────┘   └──────────┘
 Diff parse    Clone repo     LLM-based    Per-hunk patch     Combined     Auto-detect
 Hunk split    AST analysis   Ground truth  Per-assertion     scoring      root cause
 F2P match     Source code    from problem   test verdicts    & severity   classification
```

- **Stage 1-1.5**: Parse diffs, clone repo, extract code context
- **Stage 2**: Extract ground-truth intent from problem statement (LLM)
- **Stage 3**: Structural diff with code visitation (AST-level)
- **Stage 4**: Match each hunk/assertion against intent (LLM)
- **Stage 5**: Score and classify severity
- **Stage 6**: Auto-detect root cause(s) via LLM analysis

---
"""


def _scoring_slide() -> str:
    return """
# Scoring Formula

Each task receives three independent scores:

| Component | Measures |
|---|---|
| **EXCESS_PATCH** (EP) | Fraction of gold patch hunks beyond problem scope |
| **EXCESS_TEST** (ET) | Fraction of F2P test assertions beyond problem scope |
| **VAGUE_SPEC** (VS) | Ambiguity level of the problem statement |

Combined using complementary probability:

$$\\text{combined} = 1 - (1 - \\text{EP}) \\times (1 - \\text{ET}) \\times (1 - \\text{VS})$$

| Severity | Threshold |
|---|---|
| <span class="clean">CLEAN</span> | combined < 0.15 |
| <span class="minor">MINOR</span> | 0.15 ≤ combined < 0.4 |
| <span class="moderate">MODERATE</span> | 0.4 ≤ combined < 0.7 |
| <span class="severe">SEVERE</span> | combined ≥ 0.7 |

---
"""


def _root_cause_taxonomy_slide() -> str:
    return """
# Root Cause Taxonomy

Each contaminated task is classified with one or more root causes:

| Root Cause | Description | Detection Signal |
|---|---|---|
| <span class="rc">APPROACH_MISMATCH</span> | Gold patch uses different approach than problem suggests | High UNRELATED hunks, approach-level divergence |
| <span class="rc">DEFERRED_REQUIREMENT</span> | Tests enforce features explicitly deferred in problem | Deferral language + OFF_TOPIC assertions |
| <span class="rc">SCOPE_EXPANSION</span> | Gold patch/tests cover functionality beyond what was asked | High OFF_TOPIC ratio, tests on unmentioned paths |
| <span class="rc">IMPLICIT_CONSENSUS</span> | Solution requires knowledge from code review discussions | Hints contain decisions not in problem statement |
| <span class="rc">INFRASTRUCTURE_LEAK</span> | Tests require infrastructure changes not in the spec | F2P tests exercising infrastructure code paths |

> Root causes are auto-detected by the pipeline using LLM analysis (Stage 6).
> A task can have **multiple** root causes.

---
"""

def _dataset_summary_slide(
    reports: list[ContaminationReportV2],
    severity_dist: dict[str, int],
) -> str:
    total = len(reports)
    if total == 0:
        return "# Dataset Summary\n\nNo reports available.\n\n---\n"

    table_rows = []
    for sev in ["CLEAN", "MINOR", "MODERATE", "SEVERE"]:
        count = severity_dist.get(sev, 0)
        pct = count / total * 100
        css_class = sev.lower()
        table_rows.append(
            f"| <span class=\"{css_class}\">{sev}</span> | {count} | {pct:.1f}% |"
        )

    contaminated = severity_dist.get("MODERATE", 0) + severity_dist.get("SEVERE", 0)
    contaminated_pct = contaminated / total * 100 if total else 0

    scores = [r.combined_score for r in reports]
    mean_score = sum(scores) / total
    mean_ep = sum(r.excess_patch.score for r in reports) / total
    mean_et = sum(r.excess_test.score for r in reports) / total

    return f"""
# Dataset Summary

**Total tasks analyzed:** {total} | **Contaminated (MODERATE+SEVERE):** {contaminated} ({contaminated_pct:.1f}%)

| Severity | Count | Percentage |
|---|---|---|
{chr(10).join(table_rows)}

| Metric | Value |
|---|---|
| Mean combined score | {mean_score:.4f} |
| Mean EXCESS_PATCH | {mean_ep:.4f} |
| Mean EXCESS_TEST | {mean_et:.4f} |

---
"""


def _score_distribution_slide(reports: list[ContaminationReportV2]) -> str:
    if not reports:
        return ""

    buckets = [0] * 10
    for r in reports:
        idx = min(int(r.combined_score * 10), 9)
        buckets[idx] += 1

    max_count = max(buckets) if buckets else 1
    histogram_lines = []
    for i, count in enumerate(buckets):
        bar = "█" * int(count / max_count * 30) if max_count > 0 else ""
        low = i / 10
        high = (i + 1) / 10
        histogram_lines.append(f"  {low:.1f}-{high:.1f} | {bar} {count}")

    hist_text = "\n".join(histogram_lines)

    return f"""
# Score Distribution

```
Combined Contamination Score Distribution
{hist_text}
```

- Tasks with score ≥ 0.7 are flagged as <span class="severe">SEVERE</span>
- Tasks with score ≥ 0.4 are flagged as <span class="moderate">MODERATE</span>
- The tail of the distribution represents the strongest contamination signals

---
"""


def _root_cause_distribution_slide(reports: list[ContaminationReportV2]) -> str:
    rc_counts: dict[str, int] = defaultdict(int)
    for r in reports:
        for rc in r.root_causes:
            rc_counts[rc.value] += 1

    if not rc_counts:
        return ""

    rows = []
    total_with_rc = sum(1 for r in reports if r.root_causes)
    for rc_name in ["APPROACH_MISMATCH", "DEFERRED_REQUIREMENT", "SCOPE_EXPANSION",
                     "IMPLICIT_CONSENSUS", "INFRASTRUCTURE_LEAK"]:
        count = rc_counts.get(rc_name, 0)
        if count > 0:
            rows.append(f"| <span class=\"rc\">{rc_name}</span> | {count} |")

    if not rows:
        return ""

    return f"""
# Root Cause Distribution

**Tasks with root cause classification:** {total_with_rc}/{len(reports)}

| Root Cause | Count |
|---|---|
{chr(10).join(rows)}

> Tasks can have multiple root causes. Auto-detected by LLM analysis.

---
"""


def _case_highlight_slide(report: ContaminationReportV2, index: int) -> str:
    iid = report.instance_id
    ep = report.excess_patch
    et = report.excess_test

    if ep.score > et.score:
        primary = "Excess Patch"
        detail = (
            f"{ep.unrelated_count} UNRELATED + {ep.ancillary_count} ANCILLARY "
            f"/ {ep.total_hunks} total hunks"
        )
    else:
        primary = "Excess Test"
        detail = (
            f"{et.off_topic_assertions} OFF_TOPIC / {et.total_assertions} "
            f"total assertions"
        )

    core_req = report.intent.core_requirement[:200]
    rc_str = ", ".join(f"`{rc.value}`" for rc in report.root_causes) if report.root_causes else "—"

    return f"""
# Case: `{iid}`

**Combined Score:** <span class="severe">{report.combined_score:.3f}</span> | **Primary Signal:** {primary}
**Root Causes:** {rc_str}

**Problem asks:** {core_req}

| Component | Score | Detail |
|---|---|---|
| EXCESS_PATCH | {ep.score:.4f} | {ep.required_count}R / {ep.ancillary_count}A / {ep.unrelated_count}U of {ep.total_hunks} hunks |
| EXCESS_TEST | {et.score:.4f} | {et.on_topic_assertions} on-topic / {et.off_topic_assertions} off-topic of {et.total_assertions} assertions |
| VAGUE_SPEC | {report.vague_spec.score:.4f} | Ambiguity assessment |

$$\\text{{combined}} = 1 - (1-{ep.score:.3f})(1-{et.score:.3f})(1-{report.vague_spec.score:.3f}) = {report.combined_score:.3f}$$

---
"""


def _pattern_taxonomy_slide(severe_reports: list[ContaminationReportV2]) -> str:
    rc_cases: dict[str, list[str]] = defaultdict(list)
    for r in severe_reports:
        for rc in r.root_causes:
            rc_cases[rc.value].append(r.instance_id[:30])

    rows = []
    for rc_name in ["APPROACH_MISMATCH", "DEFERRED_REQUIREMENT", "SCOPE_EXPANSION",
                     "IMPLICIT_CONSENSUS", "INFRASTRUCTURE_LEAK"]:
        cases = rc_cases.get(rc_name, [])
        if cases:
            rows.append(
                f"| <span class=\"rc\">{rc_name}</span> | {len(cases)} | "
                f"{', '.join(cases[:3])}{'...' if len(cases) > 3 else ''} |"
            )

    # Fallback to old heuristic patterns if no root causes
    if not rows:
        for r in severe_reports:
            if r.excess_patch.unrelated_count > 0 and r.excess_patch.score >= 0.5:
                rows.append(
                    f"| **Approach Mismatch** (inferred) | — | `{r.instance_id}` |"
                )
            if r.excess_test.off_topic_assertions > 0 and r.excess_test.score >= 0.5:
                rows.append(
                    f"| **Scope Expansion** (inferred) | — | `{r.instance_id}` |"
                )

    return f"""
# Contamination Patterns Across SEVERE Cases

| Root Cause | Count | Example Cases |
|---|---|---|
{chr(10).join(rows)}

**Impact on evaluation:**
1. Agents that correctly solve the stated problem can fail the tests
2. Knowledge of the gold patch or code review is required to pass
3. Leaderboard rankings reflect contamination tolerance, not engineering skill

---
"""


def _trajectory_slide(trajectory_data: dict[str, Any]) -> str:
    rates = trajectory_data.get("leakage_rates", {})
    if not rates:
        return ""

    rows = []
    for agent, stats in sorted(rates.items()):
        rows.append(
            f"| {agent} | {stats['total']} | {stats['genuine']} | "
            f"{stats['leaked']} | {stats['leakage_rate']:.1%} | "
            f"{stats['mean_gold_patch_similarity']:.3f} |"
        )

    return f"""
# Trajectory Analysis: Agent Leakage Rates

| Agent | Total | Genuine | Leaked | Rate | Mean Similarity |
|---|---|---|---|---|---|
{chr(10).join(rows)}

**Leakage patterns detected:**
- **GOLD_PATCH_LEAK**: Final patch ≥90% similar to gold patch
- **PACKAGE_LEAK**: Agent installed solution from PyPI (e.g., future package version)
- **TEST_AWARE**: Agent referenced F2P test details not in the problem

> Trajectory analysis uses LLM-primary classification with full trajectory context.

---
"""


def _agent_impact_slide(trajectory_data: dict[str, Any]) -> str:
    analyses = trajectory_data.get("analyses", [])
    if not analyses:
        return ""

    # Group by instance_id, show cases where agents cheated
    by_instance: dict[str, list[dict]] = defaultdict(list)
    for a in analyses:
        by_instance[a.get("instance_id", "")].append(a)

    cheated_instances = []
    for iid, instance_analyses in by_instance.items():
        leaked = sum(
            1 for a in instance_analyses
            if a.get("leakage_pattern") in ("GOLD_PATCH_LEAK", "PACKAGE_LEAK", "TEST_AWARE")
        )
        if leaked > 0:
            cheated_instances.append((iid, leaked, len(instance_analyses)))

    if not cheated_instances:
        return ""

    rows = []
    for iid, leaked, total in cheated_instances[:6]:
        rows.append(f"| `{iid[:30]}` | {leaked}/{total} | {leaked/total:.0%} |")

    return f"""
# Agent Impact: Leakage on Contaminated Tasks

| Instance | Agents Leaked / Total | Rate |
|---|---|---|
{chr(10).join(rows)}

**Key finding:** On contaminated tasks, top-performing agents frequently show
leakage patterns — installing future package versions, copying gold patches,
or referencing undisclosed test details.

> The contamination doesn't just make tasks unfair — it actively incentivizes
> and rewards agents that access the answer rather than reason independently.

---
"""


def _test_patch_difficulty_slide(severe_reports: list[ContaminationReportV2]) -> str:
    high_off_topic = [
        r for r in severe_reports
        if r.excess_test.off_topic_assertions >= 5
    ]

    if not high_off_topic:
        return ""

    rows = []
    for r in high_off_topic[:5]:
        et = r.excess_test
        rows.append(
            f"| `{r.instance_id[:30]}` | {et.total_assertions} | "
            f"{et.off_topic_assertions} | {et.off_topic_assertions/max(et.total_assertions,1):.0%} |"
        )

    return f"""
# Test Patch Difficulty: Unreasonable Expectations

Some test patches require agents to write tests exercising functionality
not described in the problem — an unreasonably hard task:

| Instance | Total Assertions | OFF_TOPIC | OFF_TOPIC % |
|---|---|---|---|
{chr(10).join(rows)}

> When OFF_TOPIC assertions are in the **test patch** (not pre-existing),
> the agent must independently derive and write tests for undescribed behavior.
> This is polluted *if and only if* these assertions are in the test patch —
> the agent has to WRITE them, which is unreasonably hard.

---
"""


def _sensitivity_slide(
    reports: list[ContaminationReportV2],
    severity_dist: dict[str, int],
) -> str:
    total = len(reports) or 1
    moderate_plus = severity_dist.get("MODERATE", 0) + severity_dist.get("SEVERE", 0)
    minor_plus = moderate_plus + severity_dist.get("MINOR", 0)

    return f"""
# Sensitivity Analysis

| Metric | Count | Percentage |
|---|---|---|
| SEVERE (combined ≥ 0.7) | {severity_dist.get('SEVERE', 0)} | {severity_dist.get('SEVERE', 0)/total*100:.1f}% |
| MODERATE+ (combined ≥ 0.4) | {moderate_plus} | {moderate_plus/total*100:.1f}% |
| MINOR+ (combined ≥ 0.15) | {minor_plus} | {minor_plus/total*100:.1f}% |
| Non-contaminated (CLEAN) | {severity_dist.get('CLEAN', 0)} | {severity_dist.get('CLEAN', 0)/total*100:.1f}% |

**Interpretation:**
- The contamination ratio is likely **higher** than the SEVERE-only count suggests
- MODERATE cases have real contamination signals that affect agent evaluation
- More sensitive thresholds surface additional cases for manual review
- Tasks with even MINOR contamination may produce unfair rankings

---
"""


def _recommendations_slide(
    severe_reports: list[ContaminationReportV2],
    all_reports: list[ContaminationReportV2] | None = None,
) -> str:
    n_severe = len(severe_reports)
    n_total = len(all_reports) if all_reports else n_severe

    return f"""
# Recommendations

Based on **{n_severe} SEVERE** and analysis of **{n_total}** total tasks:

1. **Flag contaminated tasks** in SWE-bench evaluation
   - Tasks with combined score ≥ 0.7 should be excluded or down-weighted
   - Assertion-level traceability enables surgical removal of off-topic tests

2. **Root-cause-specific remediation**
   - APPROACH_MISMATCH: Accept alternative valid solutions
   - SCOPE_EXPANSION: Remove off-topic assertions from test patches
   - DEFERRED_REQUIREMENT: Remove tests for explicitly deferred features
   - INFRASTRUCTURE_LEAK: Separate infrastructure tests from feature tests

3. **Trajectory auditing for leaderboard integrity**
   - Check if agents access gold patches via PyPI/package installs
   - Cross-agent patch similarity reveals systemic leakage
   - LLM-based trajectory analysis detects subtle cheating patterns

4. **Spec improvement for future tasks**
   - Ensure problem statements include all required behavior
   - Reduce gap between problem statement and F2P test expectations

---
"""


def _appendix_methodology_slide() -> str:
    return """
# Appendix: Detailed Methodology

**Per-hunk patch classification:**
- **REQUIRED**: Directly implements the described fix
- **ANCILLARY**: Supports the fix (imports, infrastructure)
- **UNRELATED**: Changes behavior not described in the problem

**Per-assertion test classification:**
- **ON_TOPIC**: Assertion checks behavior described in the problem
- **OFF_TOPIC**: Assertion checks behavior NOT described

**Per-test classification:**
- **ALIGNED**: Test targets the described problem
- **TANGENTIAL**: Test partially targets the problem
- **UNRELATED**: Test doesn't target the described problem

**LLM model:** gpt-5.2-20251211 (reasoning_effort=high, max_tokens=16384)
**Trajectory analysis:** LLM-primary with heuristic signals as supporting evidence
**Cache:** Response-level caching with content hashing

---
"""


def _appendix_thresholds_slide() -> str:
    return """
# Appendix: Scoring Thresholds

**Combined score formula:**
$$\\text{combined} = 1 - (1 - \\text{EP}) \\times (1 - \\text{ET}) \\times (1 - \\text{VS})$$

**EXCESS_PATCH score:**
$$\\text{EP} = \\frac{\\text{UNRELATED} + 0.5 \\times \\text{ANCILLARY}}{\\text{total hunks}}$$

**EXCESS_TEST score:**
$$\\text{ET} = \\frac{\\text{OFF\\_TOPIC} + 0.3 \\times \\text{TANGENTIAL\\_equiv} + \\text{UNRELATED\\_equiv}}{\\text{total assertions}}$$

**Severity thresholds:**

| Severity | Combined Score |
|---|---|
| CLEAN | < 0.15 |
| MINOR | 0.15 – 0.4 |
| MODERATE | 0.4 – 0.7 |
| SEVERE | ≥ 0.7 |

---
"""


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _compute_severity_distribution(
    reports: list[ContaminationReportV2],
) -> dict[str, int]:
    dist: dict[str, int] = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in reports:
        dist[r.severity.value] += 1
    return dist


def _load_trajectory_data(path: str | pathlib.Path) -> dict[str, Any]:
    """Load trajectory analysis JSON data."""
    p = pathlib.Path(path)
    json_path = p.with_suffix(".json") if p.suffix != ".json" else p
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load trajectory data from %s: %s", json_path, exc)
    return {}


# ──────────────────────────────────────────────────────────────────────
# High-level entry point
# ──────────────────────────────────────────────────────────────────────


def build_slide_deck(
    reports_dir: str | pathlib.Path,
    deep_dive_path: str | pathlib.Path | None = None,
    trajectory_path: str | pathlib.Path | None = None,
    title: str = "SWE-bench Contamination Analysis",
    subtitle: str = "bench-cleanser Findings",
    author: str = "",
) -> str:
    """Load reports and generate a MARP slide deck."""
    from bench_cleanser.deep_dive import load_reports_from_dir

    reports = load_reports_from_dir(reports_dir, severity_filter=None)
    logger.info("Loaded %d reports for slide deck", len(reports))

    return generate_slide_deck(
        reports,
        deep_dive_path=deep_dive_path,
        trajectory_path=trajectory_path,
        title=title,
        subtitle=subtitle,
        author=author,
    )
