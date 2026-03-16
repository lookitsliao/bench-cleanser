"""Pipeline orchestrator: wires Stages 1-6 together.

v1: Processes tasks with 7-category taxonomy (Stages 1-6).
v2: Intent-matching pipeline with 4-verdict system (Stages 1-5).
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import pathlib
from typing import Any

import yaml
from tqdm import tqdm

from bench_cleanser.analysis.cross_ref import analyze_cross_references
from bench_cleanser.analysis.patch_analyzer import analyze_patch, analyze_patch_v2
from bench_cleanser.analysis.scope_analyzer import analyze_scope, extract_intent
from bench_cleanser.analysis.structural_diff import compute_structural_diff
from bench_cleanser.analysis.test_analyzer import analyze_tests, analyze_tests_v2
from bench_cleanser.cache import ResponseCache
from bench_cleanser.classification.scorer import (
    build_report,
    build_report_v2,
    build_report_v3,
)
from bench_cleanser.code_visitor import (
    extract_fixtures,
    extract_imports,
    get_full_test_source,
    get_post_patch_test_source,
)
from bench_cleanser.llm_client import LLMClient
from bench_cleanser.models import (
    CodeContext,
    ContaminationReport,
    ContaminationReportV2,
    DualTaxonomyReport,
    ParsedTask,
    PipelineConfig,
    RootCause,
    Severity,
    TaskRecord,
    VagueSpecDetail,
)
from bench_cleanser.parsing.patch_parser import get_files_from_patch, parse_patch
from bench_cleanser.parsing.test_parser import (
    match_f2p_tests_to_hunks,
    parse_test_patch,
)
from bench_cleanser.repo_manager import RepoManager
from bench_cleanser.static_analysis import (
    build_call_targets,
    extract_assertions,
    identify_tested_functions,
    resolve_imports,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Config loading
# ------------------------------------------------------------------


def load_config(config_path: str) -> PipelineConfig:
    """Load pipeline configuration from a YAML file.

    Environment variable references like ``${LLM_API_KEY}`` are expanded.
    """
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    def _expand(val: Any) -> Any:
        if isinstance(val, str) and "${" in val:
            import re

            def _repl(m: Any) -> str:
                return os.environ.get(m.group(1), m.group(0))

            return re.sub(r"\$\{(\w+)\}", _repl, val)
        return val

    llm = raw.get("llm", {})
    pipeline = raw.get("pipeline", {})
    thresholds = raw.get("thresholds", {})
    astred = raw.get("astred", {})
    code_visit = raw.get("code_visitation", {})

    return PipelineConfig(
        llm_base_url=_expand(llm.get("base_url", "https://cloudgpt-openai.azure-api.net/")),
        llm_api_version=llm.get("api_version", "2025-04-01-preview"),
        llm_model=llm.get("model", "gpt-5.2-20251211"),
        llm_max_tokens=llm.get("max_tokens", 16384),
        llm_reasoning_effort=llm.get("reasoning_effort", "high"),
        max_concurrent_requests=llm.get("max_concurrent_requests", 10),
        retry_attempts=llm.get("retry_attempts", 7),
        retry_delay_seconds=llm.get("retry_delay_seconds", 5.0),
        concurrency=pipeline.get("concurrency", 5),
        cache_dir=pipeline.get("cache_dir", ".cache/llm_responses"),
        output_dir=pipeline.get("output_dir", "output"),
        clean_max=thresholds.get("clean_max", 0.15),
        minor_max=thresholds.get("minor_max", 0.4),
        moderate_max=thresholds.get("moderate_max", 0.7),
        astred_enabled=astred.get("enabled", False),
        astred_binary_path=astred.get("binary_path", ""),
        code_visitation_enabled=code_visit.get("enabled", True),
        repo_cache_dir=code_visit.get("repo_cache_dir", ".cache/repos"),
        clone_timeout_seconds=code_visit.get("clone_timeout_seconds", 120),
        max_source_context_lines=code_visit.get("max_source_context_lines", 200),
    )


# ------------------------------------------------------------------
# Stage 1: Parse
# ------------------------------------------------------------------


def parse_task(record: TaskRecord) -> ParsedTask:
    """Stage 1: parse a raw task record into structured form."""
    patch_hunks = parse_patch(record.patch)
    test_hunks = parse_test_patch(record.test_patch)
    f2p_matched, f2p_unmatched = match_f2p_tests_to_hunks(
        record.fail_to_pass, test_hunks
    )

    return ParsedTask(
        record=record,
        patch_hunks=patch_hunks,
        test_hunks=test_hunks,
        f2p_test_hunks=f2p_matched,
        f2p_tests_with_no_hunk=f2p_unmatched,
        files_in_gold_patch=get_files_from_patch(record.patch),
        files_in_test_patch=get_files_from_patch(record.test_patch),
    )


# ------------------------------------------------------------------
# Stage 1.5: Code Visitation
# ------------------------------------------------------------------


def enrich_with_code_context(
    parsed: ParsedTask,
    repo_manager: RepoManager,
    config: PipelineConfig,
) -> None:
    """Stage 1.5: clone the repo and attach CodeContext to each F2P test hunk.

    Modifies *parsed.f2p_test_hunks* in place by setting their
    ``code_context`` attribute.
    """
    record = parsed.record
    repo_path = repo_manager.get_repo_path(record.repo, record.base_commit)
    if repo_path is None:
        logger.warning(
            "Code visitation skipped for %s: clone failed", record.instance_id
        )
        return

    max_lines = config.max_source_context_lines

    for test_hunk in parsed.f2p_test_hunks:
        try:
            test_file = test_hunk.file_path

            # Read the full test file from the pre-patch repo
            test_file_content = repo_manager.get_file(repo_path, test_file) or ""

            # Extract pre-patch test function
            pre_patch_source = get_full_test_source(
                repo_path, test_file, test_hunk.test_name, max_lines=max_lines
            )

            # Build post-patch test source from diff
            post_patch_source = get_post_patch_test_source(
                pre_patch_source,
                test_hunk.test_name,
                test_hunk.added_lines,
                test_hunk.removed_lines,
                max_lines=max_lines,
            )

            # Extract imports and fixtures
            imports_text = extract_imports(test_file_content) if test_file_content else ""
            fixtures_text = (
                extract_fixtures(test_file_content, test_hunk.test_name)
                if test_file_content
                else ""
            )

            # Resolve imports to file paths
            import_map = (
                resolve_imports(test_file_content, repo_path)
                if test_file_content
                else {}
            )

            # Identify tested functions (calls into patch files)
            analysis_source = post_patch_source or test_hunk.full_source
            tested_funcs = identify_tested_functions(
                analysis_source,
                import_map,
                parsed.files_in_gold_patch,
                repo_path,
                max_source_lines=max_lines,
            )

            # Build call targets
            call_targets = build_call_targets(
                analysis_source,
                import_map,
                parsed.files_in_gold_patch,
            )

            # Extract assertions
            assertions = extract_assertions(analysis_source)

            test_hunk.code_context = CodeContext(
                pre_patch_test_source=pre_patch_source,
                post_patch_test_source=post_patch_source,
                test_file_imports=imports_text,
                test_file_fixtures=fixtures_text,
                tested_functions=tested_funcs,
                call_targets=call_targets,
                assertions=assertions,
                test_file_path=test_file,
                repo_path=str(repo_path),
            )

            logger.debug(
                "Code context built for %s: %d tested funcs, %d calls, %d assertions",
                test_hunk.test_name,
                len(tested_funcs),
                len(call_targets),
                len(assertions),
            )

        except Exception as exc:
            logger.warning(
                "Code visitation failed for test %s: %s",
                test_hunk.test_name,
                exc,
            )

    # Also try to build CodeContext for unmatched F2P tests
    for test_id in parsed.f2p_tests_with_no_hunk:
        # Extract file path and test name from test ID
        parts = test_id.rsplit("::", 1)
        if len(parts) != 2:
            continue
        test_file, test_name = parts
        # Only extract test name (strip class if present)
        if "." in test_name:
            test_name = test_name.split(".")[-1]

        pre_patch_source = get_full_test_source(
            repo_path, test_file, test_name, max_lines=max_lines
        )
        if pre_patch_source:
            logger.info(
                "Found pre-patch source for unmatched F2P test %s (%d lines)",
                test_id,
                pre_patch_source.count("\n") + 1,
            )


# ------------------------------------------------------------------
# Single-task pipeline
# ------------------------------------------------------------------


async def process_single_task(
    record: TaskRecord,
    llm: LLMClient,
    config: PipelineConfig,
    repo_manager: RepoManager | None = None,
) -> ContaminationReport:
    """Run the full pipeline on a single task."""
    # Stage 1: Parse
    parsed = parse_task(record)

    # Stage 1.5: Code visitation (if enabled and repo_manager available)
    if config.code_visitation_enabled and repo_manager is not None:
        enrich_with_code_context(parsed, repo_manager, config)

    # Stage 2: Scope analysis (LLM, unanchored)
    scope = await analyze_scope(parsed.record, llm)

    # Stages 3 & 4 can run in parallel
    patch_task = analyze_patch(parsed, scope, llm)
    test_task = analyze_tests(parsed, scope, llm)
    patch_analysis, test_analysis = await asyncio.gather(patch_task, test_task)

    # Stage 5: Cross-reference (pass test hunks for code-context-aware analysis)
    cross_ref = analyze_cross_references(
        patch_analysis, test_analysis,
        f2p_test_hunks=parsed.f2p_test_hunks,
    )

    # Stage 6: Classification
    report = build_report(scope, patch_analysis, test_analysis, cross_ref, config)

    return report


# ------------------------------------------------------------------
# Batch pipeline
# ------------------------------------------------------------------


async def run_pipeline(
    records: list[TaskRecord],
    config: PipelineConfig,
) -> list[ContaminationReport]:
    """Run the pipeline on a batch of tasks with bounded concurrency.

    Reports are written to disk as they complete.
    """
    cache = ResponseCache(config.cache_dir)
    llm = LLMClient(config, cache=cache)

    # Set up repo manager for code visitation (if enabled)
    repo_manager: RepoManager | None = None
    if config.code_visitation_enabled:
        repo_manager = RepoManager(
            cache_dir=config.repo_cache_dir,
            clone_timeout=config.clone_timeout_seconds,
        )
        logger.info("Code visitation enabled — pre-cloning repos")
        clone_results = repo_manager.pre_clone_repos(records)
        logger.info(
            "Pre-clone complete: %d/%d repos available",
            sum(1 for v in clone_results.values() if v),
            len(clone_results),
        )

    output_dir = pathlib.Path(config.output_dir)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(config.concurrency)
    reports: list[ContaminationReport] = []
    progress = tqdm(total=len(records), desc="Processing tasks", unit="task")

    async def _process(record: TaskRecord) -> ContaminationReport:
        async with semaphore:
            try:
                report = await process_single_task(
                    record, llm, config, repo_manager=repo_manager
                )
            except Exception as exc:
                logger.error(
                    "Failed to process %s: %s", record.instance_id, exc,
                    exc_info=True,
                )
                # Return an error report — marked SEVERE so it stands out
                # in summary stats rather than hiding as CLEAN.
                report = ContaminationReport(
                    instance_id=record.instance_id,
                    severity=Severity.SEVERE,
                    total_confidence=0.0,
                    categories={},
                    f2p_test_reports=[],
                    patch_hunk_reports=[],
                    compound_patterns=[],
                    evidence_summary=f"PIPELINE_ERROR: {exc}",
                )

            # Write per-task report
            report_path = reports_dir / f"{record.instance_id}.json"
            report_path.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            progress.update(1)
            return report

    tasks = [_process(record) for record in records]
    reports = await asyncio.gather(*tasks)

    progress.close()

    # Write aggregate summary
    _write_summary(reports, output_dir)

    return list(reports)


def _write_summary(
    reports: list[ContaminationReport],
    output_dir: pathlib.Path,
) -> None:
    """Write aggregate summary CSV and stats JSON."""
    # CSV
    csv_path = output_dir / "summary.csv"
    header = (
        "instance_id,severity,total_confidence,"
        "C1_OVERTEST,C2_OVERPATCH,C3_SNEAKY_TEST_MOD,"
        "C4_SCOPE_CREEP,C5_TEST_DESC_MISALIGN,"
        "C6_CIRCULAR_DEPENDENCY,C7_AMBIGUOUS_SPEC,compound_patterns"
    )
    lines = [header]
    for r in reports:
        cats = r.categories
        row = [
            r.instance_id,
            r.severity.value,
            f"{r.total_confidence:.4f}",
        ]
        for cat_name in [
            "OVERTEST",
            "OVERPATCH",
            "SNEAKY_TEST_MOD",
            "SCOPE_CREEP",
            "TEST_DESC_MISALIGN",
            "CIRCULAR_DEPENDENCY",
            "AMBIGUOUS_SPEC",
        ]:
            cs = cats.get(cat_name)
            row.append(f"{cs.confidence:.4f}" if cs else "0.0000")
        row.append(";".join(r.compound_patterns) if r.compound_patterns else "")
        lines.append(",".join(row))

    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Stats JSON
    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in reports:
        severity_counts[r.severity.value] += 1

    stats = {
        "total_tasks": len(reports),
        "severity_distribution": severity_counts,
        "mean_confidence": (
            sum(r.total_confidence for r in reports) / len(reports)
            if reports
            else 0.0
        ),
    }
    stats_path = output_dir / "summary_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("Summary written to %s", output_dir)
    logger.info("Severity distribution: %s", severity_counts)


# ═══════════════════════════════════════════════════════════════════════
# v2 Pipeline: Intent-matching architecture
# ═══════════════════════════════════════════════════════════════════════


ROOT_CAUSE_SYSTEM_PROMPT = """\
You are a benchmark contamination analyst. Given a contamination report \
for a software engineering task, classify the root cause(s) of contamination.

A task can have MULTIPLE root causes. Only include root causes you are \
confident about (confidence >= 0.6).

Root cause categories:
1. APPROACH_MISMATCH — Gold patch takes a fundamentally different approach \
than the problem statement suggests. The problem describes fix X but the \
gold patch implements fix Y. An agent following the problem description \
would produce a different (but possibly valid) solution.

2. DEFERRED_REQUIREMENT — Tests enforce features explicitly deferred or \
disclaimed in the problem statement. Look for phrases like "I have yet to", \
"will add later", "not implemented yet", "future work", "TODO" in the \
problem statement, where the tests then require that deferred feature.

3. SCOPE_EXPANSION — Gold patch and/or tests extend beyond the stated \
problem scope. The problem asks for X but the gold patch or tests also \
cover Y. High OFF_TOPIC assertion ratio is a strong signal.

4. IMPLICIT_CONSENSUS — The solution requires knowledge from code review \
discussion or hints that extends the original problem statement. The hints \
contain design decisions not derivable from the problem alone.

5. INFRASTRUCTURE_LEAK — Tests require ancillary infrastructure changes \
not described in the feature specification. The F2P tests exercise \
infrastructure code paths not mentioned in the problem statement."""


async def _classify_root_causes(
    record: TaskRecord,
    report: ContaminationReportV2,
    llm: LLMClient,
) -> tuple[list[RootCause], dict[str, str]]:
    """Stage 6: Auto-detect root causes using LLM analysis.

    Returns (root_causes, root_cause_reasoning) where reasoning maps
    each root cause value to explanatory text.
    """
    ep = report.excess_patch
    et = report.excess_test
    intent = report.intent

    # Build context for the LLM
    prompt = f"""Analyze this contaminated SWE-bench task and identify root cause(s).

INSTANCE: {record.instance_id}
SEVERITY: {report.severity.value} (combined score: {report.combined_score:.3f})

PROBLEM STATEMENT (first 3000 chars):
{record.problem_statement[:3000]}

HINTS TEXT (first 2000 chars):
{record.hints_text[:2000] if record.hints_text else "(none)"}

INTENT EXTRACTION:
- Core requirement: {intent.core_requirement}
- Behavioral contract: {intent.behavioral_contract[:500]}
- Acceptance criteria: {'; '.join(intent.acceptance_criteria)}
- Out of scope: {intent.out_of_scope}

EXCESS_PATCH ANALYSIS (score: {ep.score:.3f}):
- Total hunks: {ep.total_hunks}
- REQUIRED: {ep.required_count}, ANCILLARY: {ep.ancillary_count}, UNRELATED: {ep.unrelated_count}
- Hunk details:
"""
    for h in ep.hunk_verdicts[:10]:
        prompt += f"  [{h.hunk_index}] {h.file_path}: {h.verdict.value} — {h.reasoning[:200]}\n"

    prompt += f"""
EXCESS_TEST ANALYSIS (score: {et.score:.3f}):
- Total tests: {et.total_tests}
- ALIGNED: {et.aligned_count}, TANGENTIAL: {et.tangential_count}, UNRELATED: {et.unrelated_count}
- Total assertions: {et.total_assertions}
- ON_TOPIC: {et.on_topic_assertions}, OFF_TOPIC: {et.off_topic_assertions}
"""
    for t in et.test_verdicts[:5]:
        prompt += f"  Test '{t.test_name}': {t.intent_match.value} (ON:{t.on_topic_count}, OFF:{t.off_topic_count})\n"

    prompt += f"""
VAGUE_SPEC: {report.vague_spec.score:.3f}

Respond in JSON:
{{
    "root_causes": [
        {{
            "category": "APPROACH_MISMATCH | DEFERRED_REQUIREMENT | SCOPE_EXPANSION | IMPLICIT_CONSENSUS | INFRASTRUCTURE_LEAK",
            "confidence": 0.0 to 1.0,
            "reasoning": "Explanation of why this root cause applies"
        }}
    ]
}}

Only include root causes with confidence >= 0.6. A task can have multiple root causes."""

    try:
        response = await llm.query(
            system=ROOT_CAUSE_SYSTEM_PROMPT,
            user=prompt,
            cache_key=f"root_cause_{record.instance_id}",
        )

        # Parse response
        result = _parse_root_cause_response(response)
        root_causes = []
        reasoning_map = {}

        for entry in result.get("root_causes", []):
            try:
                rc = RootCause(entry.get("category", ""))
                confidence = float(entry.get("confidence", 0.0))
                if confidence >= 0.6:
                    root_causes.append(rc)
                    reasoning_map[rc.value] = entry.get("reasoning", "")
            except (ValueError, KeyError):
                continue

        return root_causes, reasoning_map
    except Exception as exc:
        logger.warning("Root cause classification failed: %s", exc)
        return [], {}


def _parse_root_cause_response(response: str) -> dict:
    """Parse LLM JSON response for root cause classification."""
    import re as _re
    text = response.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence_match = _re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, _re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass
    return {"root_causes": []}


async def process_single_task_v2(
    record: TaskRecord,
    llm: LLMClient,
    config: PipelineConfig,
    repo_manager: RepoManager | None = None,
) -> ContaminationReportV2:
    """Run the v2 pipeline on a single task.

    Stages:
      1. PARSE — extract diffs from gold patch + test patch
      2. INTENT — extract ground truth intent from problem statement
      3. STRUCTURAL DIFF — astred_core-powered structural analysis
      4. INTENT MATCHING — match tests + patches against intent
      5. TRIAGE & REPORT — 4-category scoring + actionable report
    """
    # Stage 1: Parse (same as v1)
    parsed = parse_task(record)

    # Stage 1.5: Code visitation (same as v1, enriches test hunks)
    if config.code_visitation_enabled and repo_manager is not None:
        enrich_with_code_context(parsed, repo_manager, config)

    # Stage 2: Intent extraction (enhanced, returns IntentStatement)
    intent = await extract_intent(record, llm)

    # Stage 3: Structural diff (if repo available)
    structural_diff = None
    if repo_manager is not None:
        repo_path = repo_manager.get_repo_path(record.repo, record.base_commit)
        if repo_path is not None:
            try:
                structural_diff = compute_structural_diff(parsed, repo_path)
            except Exception as exc:
                logger.warning(
                    "Structural diff failed for %s: %s", record.instance_id, exc
                )

    # Stage 4: Intent matching (patch + test analysis in parallel)
    patch_task = analyze_patch_v2(parsed, intent, llm, structural_diff)
    test_task = analyze_tests_v2(parsed, intent, llm, structural_diff)
    excess_patch, excess_test = await asyncio.gather(patch_task, test_task)

    # Stage 5: Triage & report
    vague_spec = VagueSpecDetail(
        score=intent.ambiguity_score,
        reasoning=intent.raw_llm_response[:500] if intent.raw_llm_response else "",
    )

    report = build_report_v2(intent, excess_patch, excess_test, vague_spec, config)

    # Stage 6: Root-cause auto-detection (for non-CLEAN tasks)
    if report.severity != Severity.CLEAN:
        try:
            root_causes, root_cause_reasoning = await _classify_root_causes(
                record, report, llm,
            )
            report.root_causes = root_causes
            report.root_cause_reasoning = root_cause_reasoning
        except Exception as exc:
            logger.warning(
                "Root-cause classification failed for %s: %s",
                record.instance_id, exc,
            )

    return report


async def run_pipeline_v2(
    records: list[TaskRecord],
    config: PipelineConfig,
    *,
    resume: bool = True,
) -> list[ContaminationReportV2]:
    """Run the v2 pipeline on a batch of tasks with rich progress display.

    Reports are written to disk as they complete.

    Args:
        records: Tasks to process.
        config: Pipeline configuration.
        resume: If True, skip tasks that already have a report on disk
                and load those reports at the end for summary generation.
    """
    cache = ResponseCache(config.cache_dir)
    llm = LLMClient(config, cache=cache)

    # Set up repo manager for code visitation (if enabled)
    repo_manager: RepoManager | None = None
    if config.code_visitation_enabled:
        repo_manager = RepoManager(
            cache_dir=config.repo_cache_dir,
            clone_timeout=config.clone_timeout_seconds,
        )
        logger.info("Code visitation enabled — pre-cloning repos")
        clone_results = repo_manager.pre_clone_repos(records)
        logger.info(
            "Pre-clone complete: %d/%d repos available",
            sum(1 for v in clone_results.values() if v),
            len(clone_results),
        )

    output_dir = pathlib.Path(config.output_dir)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Resume: skip tasks that already have a report file on disk
    skipped_ids: set[str] = set()
    if resume:
        existing = {p.stem for p in reports_dir.glob("*.json")}
        skipped_ids = {r.instance_id for r in records if r.instance_id in existing}
        if skipped_ids:
            logger.info(
                "Resume: skipping %d/%d tasks with existing reports",
                len(skipped_ids),
                len(records),
            )
        records = [r for r in records if r.instance_id not in skipped_ids]

    semaphore = asyncio.Semaphore(config.concurrency)
    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}

    # Try to use rich for progress; fall back to tqdm
    try:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        use_rich = True
    except ImportError:
        use_rich = False

    reports: list[ContaminationReportV2] = []

    async def _process(
        record: TaskRecord,
        progress_callback: Any = None,
    ) -> ContaminationReportV2:
        async with semaphore:
            try:
                report = await process_single_task_v2(
                    record, llm, config, repo_manager=repo_manager
                )
            except Exception as exc:
                logger.error(
                    "Failed to process %s: %s", record.instance_id, exc,
                    exc_info=True,
                )
                from bench_cleanser.models import (
                    ExcessPatchDetail,
                    ExcessTestDetail,
                    IntentStatement,
                )
                # Return an error report — marked SEVERE so it stands out.
                dummy_intent = IntentStatement(
                    instance_id=record.instance_id,
                    core_requirement=f"PIPELINE_ERROR: {exc}",
                    behavioral_contract="",
                    acceptance_criteria=[],
                    out_of_scope="",
                    ambiguity_score=0.0,
                    raw_llm_response=f"Pipeline error: {exc}",
                )
                report = build_report_v2(
                    dummy_intent,
                    ExcessPatchDetail(score=0.0, total_hunks=0, required_count=0, ancillary_count=0, unrelated_count=0),
                    ExcessTestDetail(score=0.0, total_tests=0, aligned_count=0, tangential_count=0, unrelated_count=0, total_assertions=0, on_topic_assertions=0, off_topic_assertions=0, has_modified_tests=False),
                    VagueSpecDetail(score=0.0, reasoning=f"PIPELINE_ERROR: {exc}"),
                    config,
                )
                # Override severity — build_report_v2 scores 0.0 as CLEAN,
                # but errors should be visible in summaries.
                report.severity = Severity.SEVERE

            # Write per-task report
            report_path = reports_dir / f"{record.instance_id}.json"
            report_path.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            severity_counts[report.severity.value] += 1

            if progress_callback is not None:
                progress_callback()

            return report

    if use_rich:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        from rich.live import Live
        from rich.console import Console

        console = Console()

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]bench-cleanser v2"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("[dim]{task.fields[status]}"),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                "Processing",
                total=len(records),
                status="Starting...",
            )

            def _update_progress():
                status_parts = [
                    f"CLEAN:{severity_counts['CLEAN']}",
                    f"MINOR:{severity_counts['MINOR']}",
                    f"MOD:{severity_counts['MODERATE']}",
                    f"SEV:{severity_counts['SEVERE']}",
                ]
                progress.update(task_id, advance=1, status=" ".join(status_parts))

            tasks = [_process(record, _update_progress) for record in records]
            reports = list(await asyncio.gather(*tasks))
    else:
        # Fallback to tqdm
        progress_bar = tqdm(total=len(records), desc="bench-cleanser v2", unit="task")

        def _update_tqdm():
            progress_bar.update(1)
            progress_bar.set_postfix(severity_counts)

        tasks = [_process(record, _update_tqdm) for record in records]
        reports = list(await asyncio.gather(*tasks))
        progress_bar.close()

    # Load previously completed reports (from resume) and merge
    if skipped_ids:
        for report_path in reports_dir.glob("*.json"):
            if report_path.stem in skipped_ids:
                try:
                    data = json.loads(report_path.read_text(encoding="utf-8"))
                    resumed = ContaminationReportV2.from_dict(data)
                    reports.append(resumed)
                    severity_counts[resumed.severity.value] += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to load resumed report %s: %s",
                        report_path.stem, exc,
                    )

    # Write aggregate summary
    _write_summary_v2(reports, output_dir)

    return reports


def _write_summary_v2(
    reports: list[ContaminationReportV2],
    output_dir: pathlib.Path,
) -> None:
    """Write v2 aggregate summary CSV and stats JSON."""
    # CSV
    csv_path = output_dir / "summary.csv"
    fieldnames = [
        "instance_id", "severity", "combined_score",
        "excess_patch_score", "excess_test_score", "vague_spec_score",
        "patch_hunks_total", "patch_required", "patch_ancillary", "patch_unrelated",
        "tests_total", "tests_aligned", "tests_tangential", "tests_unrelated",
        "assertions_total", "assertions_on_topic", "assertions_off_topic",
        "has_modified_test", "root_causes", "recommendations",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in reports:
        writer.writerow({
            "instance_id": r.instance_id,
            "severity": r.severity.value,
            "combined_score": f"{r.combined_score:.4f}",
            "excess_patch_score": f"{r.excess_patch.score:.4f}",
            "excess_test_score": f"{r.excess_test.score:.4f}",
            "vague_spec_score": f"{r.vague_spec.score:.4f}",
            "patch_hunks_total": r.excess_patch.total_hunks,
            "patch_required": r.excess_patch.required_count,
            "patch_ancillary": r.excess_patch.ancillary_count,
            "patch_unrelated": r.excess_patch.unrelated_count,
            "tests_total": r.excess_test.total_tests,
            "tests_aligned": r.excess_test.aligned_count,
            "tests_tangential": r.excess_test.tangential_count,
            "tests_unrelated": r.excess_test.unrelated_count,
            "assertions_total": r.excess_test.total_assertions,
            "assertions_on_topic": r.excess_test.on_topic_assertions,
            "assertions_off_topic": r.excess_test.off_topic_assertions,
            "has_modified_test": r.excess_test.has_modified_tests,
            "root_causes": ";".join(rc.value for rc in r.root_causes),
            "recommendations": "; ".join(r.recommendations),
        })

    csv_path.write_text(output.getvalue(), encoding="utf-8")

    # Stats JSON
    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in reports:
        severity_counts[r.severity.value] += 1

    scores = [r.combined_score for r in reports]
    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    # Root cause distribution
    root_cause_counts: dict[str, int] = {}
    for r in reports:
        for rc in r.root_causes:
            root_cause_counts[rc.value] = root_cause_counts.get(rc.value, 0) + 1

    stats = {
        "total_tasks": len(reports),
        "severity_distribution": severity_counts,
        "root_cause_distribution": root_cause_counts,
        "mean_combined_score": (sum(scores) / n) if n else 0.0,
        "median_combined_score": (
            sorted_scores[n // 2] if n % 2 == 1
            else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
        ) if n else 0.0,
        "mean_excess_patch": (
            sum(r.excess_patch.score for r in reports) / n if n else 0.0
        ),
        "mean_excess_test": (
            sum(r.excess_test.score for r in reports) / n if n else 0.0
        ),
        "mean_vague_spec": (
            sum(r.vague_spec.score for r in reports) / n if n else 0.0
        ),
    }
    stats_path = output_dir / "summary_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("v2 Summary written to %s", output_dir)
    logger.info("Severity distribution: %s", severity_counts)


# ═══════════════════════════════════════════════════════════════════════
# v3 Pipeline: Dual Taxonomy architecture
# ═══════════════════════════════════════════════════════════════════════


async def process_single_task_v3(
    record: TaskRecord,
    llm: LLMClient,
    config: PipelineConfig,
    repo_manager: RepoManager | None = None,
) -> DualTaxonomyReport:
    """Run the v3 pipeline on a single task.

    Stages 1-4 are identical to v2.  Stage 5 uses the dual taxonomy
    classifier instead of the old root-cause detector.

    Stages:
      1. PARSE — extract diffs from gold patch + test patch
      2. INTENT — extract ground truth intent from problem statement
      3. STRUCTURAL DIFF — astred_core-powered structural analysis
      4. INTENT MATCHING — match tests + patches against intent
      5. DUAL TAXONOMY — multi-label classification + recalibrated severity
    """
    # Stage 1: Parse
    parsed = parse_task(record)

    # Stage 1.5: Code visitation
    if config.code_visitation_enabled and repo_manager is not None:
        enrich_with_code_context(parsed, repo_manager, config)

    # Stage 2: Intent extraction
    intent = await extract_intent(record, llm)

    # Stage 3: Structural diff
    structural_diff = None
    if repo_manager is not None:
        repo_path = repo_manager.get_repo_path(record.repo, record.base_commit)
        if repo_path is not None:
            try:
                structural_diff = compute_structural_diff(parsed, repo_path)
            except Exception as exc:
                logger.warning(
                    "Structural diff failed for %s: %s", record.instance_id, exc
                )

    # Stage 4: Intent matching (parallel)
    patch_task = analyze_patch_v2(parsed, intent, llm, structural_diff)
    test_task = analyze_tests_v2(parsed, intent, llm, structural_diff)
    excess_patch, excess_test = await asyncio.gather(patch_task, test_task)

    # Stage 5: Dual taxonomy classification
    vague_spec = VagueSpecDetail(
        score=intent.ambiguity_score,
        reasoning=intent.raw_llm_response[:500] if intent.raw_llm_response else "",
    )

    report = await build_report_v3(
        intent, excess_patch, excess_test, vague_spec, config,
        record=record, llm=llm,
    )

    return report


async def run_pipeline_v3(
    records: list[TaskRecord],
    config: PipelineConfig,
    *,
    resume: bool = True,
) -> list[DualTaxonomyReport]:
    """Run the v3 (dual taxonomy) pipeline on a batch of tasks.

    Same progress display and resume behavior as v2.
    """
    cache = ResponseCache(config.cache_dir)
    llm = LLMClient(config, cache=cache)

    repo_manager: RepoManager | None = None
    if config.code_visitation_enabled:
        repo_manager = RepoManager(
            cache_dir=config.repo_cache_dir,
            clone_timeout=config.clone_timeout_seconds,
        )
        logger.info("Code visitation enabled — pre-cloning repos")
        clone_results = repo_manager.pre_clone_repos(records)
        logger.info(
            "Pre-clone complete: %d/%d repos available",
            sum(1 for v in clone_results.values() if v),
            len(clone_results),
        )

    output_dir = pathlib.Path(config.output_dir)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Resume: skip tasks with existing reports
    skipped_ids: set[str] = set()
    if resume:
        existing = {p.stem for p in reports_dir.glob("*.json")}
        skipped_ids = {r.instance_id for r in records if r.instance_id in existing}
        if skipped_ids:
            logger.info(
                "Resume: skipping %d/%d tasks with existing reports",
                len(skipped_ids), len(records),
            )
        records = [r for r in records if r.instance_id not in skipped_ids]

    semaphore = asyncio.Semaphore(config.concurrency)
    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}

    try:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        use_rich = True
    except ImportError:
        use_rich = False

    reports: list[DualTaxonomyReport] = []

    async def _process(
        record: TaskRecord,
        progress_callback: Any = None,
    ) -> DualTaxonomyReport:
        async with semaphore:
            try:
                report = await process_single_task_v3(
                    record, llm, config, repo_manager=repo_manager
                )
            except Exception as exc:
                logger.error(
                    "Failed to process %s: %s", record.instance_id, exc,
                    exc_info=True,
                )
                from bench_cleanser.models import (
                    ExcessPatchDetail,
                    ExcessTestDetail,
                    IntentStatement,
                )
                dummy_intent = IntentStatement(
                    instance_id=record.instance_id,
                    core_requirement=f"PIPELINE_ERROR: {exc}",
                    behavioral_contract="",
                    acceptance_criteria=[],
                    out_of_scope="",
                    ambiguity_score=0.0,
                    raw_llm_response=f"Pipeline error: {exc}",
                )
                report = DualTaxonomyReport(
                    instance_id=record.instance_id,
                    severity=Severity.SEVERE,
                    combined_score=0.0,
                    intent=dummy_intent,
                    excess_patch=ExcessPatchDetail(
                        score=0.0, total_hunks=0, required_count=0,
                        ancillary_count=0, unrelated_count=0,
                    ),
                    excess_test=ExcessTestDetail(
                        score=0.0, total_tests=0, aligned_count=0,
                        tangential_count=0, unrelated_count=0,
                        total_assertions=0, on_topic_assertions=0,
                        off_topic_assertions=0, has_modified_tests=False,
                    ),
                    vague_spec=VagueSpecDetail(
                        score=0.0, reasoning=f"PIPELINE_ERROR: {exc}",
                    ),
                )

            report_path = reports_dir / f"{record.instance_id}.json"
            report_path.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            severity_counts[report.severity.value] += 1

            if progress_callback is not None:
                progress_callback()

            return report

    if use_rich:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        from rich.console import Console

        console = Console()

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]bench-cleanser v3"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("[dim]{task.fields[status]}"),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                "Processing", total=len(records), status="Starting...",
            )

            def _update_progress():
                status_parts = [
                    f"CLEAN:{severity_counts['CLEAN']}",
                    f"MINOR:{severity_counts['MINOR']}",
                    f"MOD:{severity_counts['MODERATE']}",
                    f"SEV:{severity_counts['SEVERE']}",
                ]
                progress.update(task_id, advance=1, status=" ".join(status_parts))

            tasks = [_process(record, _update_progress) for record in records]
            reports = list(await asyncio.gather(*tasks))
    else:
        progress_bar = tqdm(total=len(records), desc="bench-cleanser v3", unit="task")

        def _update_tqdm():
            progress_bar.update(1)
            progress_bar.set_postfix(severity_counts)

        tasks = [_process(record, _update_tqdm) for record in records]
        reports = list(await asyncio.gather(*tasks))
        progress_bar.close()

    # Load resumed reports
    if skipped_ids:
        for report_path in reports_dir.glob("*.json"):
            if report_path.stem in skipped_ids:
                try:
                    data = json.loads(report_path.read_text(encoding="utf-8"))
                    # Load as v2 for compat, wrap in DualTaxonomyReport
                    v2 = ContaminationReportV2.from_dict(data)
                    resumed = DualTaxonomyReport(
                        instance_id=v2.instance_id,
                        severity=v2.severity,
                        combined_score=v2.combined_score,
                        intent=v2.intent,
                        excess_patch=v2.excess_patch,
                        excess_test=v2.excess_test,
                        vague_spec=v2.vague_spec,
                        categories=v2.categories,
                        root_causes=v2.root_causes,
                        root_cause_reasoning=v2.root_cause_reasoning,
                        recommendations=v2.recommendations,
                    )
                    reports.append(resumed)
                    severity_counts[resumed.severity.value] += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to load resumed report %s: %s",
                        report_path.stem, exc,
                    )

    _write_summary_v3(reports, output_dir)

    return reports


def _write_summary_v3(
    reports: list[DualTaxonomyReport],
    output_dir: pathlib.Path,
) -> None:
    """Write v3 aggregate summary CSV and stats JSON."""
    csv_path = output_dir / "summary.csv"
    fieldnames = [
        "instance_id", "severity", "combined_score",
        "excess_patch_score", "excess_test_score", "vague_spec_score",
        "task_labels", "primary_label", "label_count",
        "patch_hunks_total", "patch_required", "patch_ancillary", "patch_unrelated",
        "tests_total", "tests_aligned", "tests_tangential", "tests_unrelated",
        "assertions_total", "assertions_on_topic", "assertions_off_topic",
        "recommendations",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in reports:
        # Determine primary label (highest weighted confidence)
        from bench_cleanser.classification.dual_taxonomy import LABEL_DEFINITIONS
        primary = ""
        best_score = -1.0
        for tl in r.task_labels:
            w = LABEL_DEFINITIONS.get(tl.label.value, {}).get("weight", 0.0)
            ws = w * tl.confidence
            if ws > best_score:
                best_score = ws
                primary = tl.label.value

        writer.writerow({
            "instance_id": r.instance_id,
            "severity": r.severity.value,
            "combined_score": f"{r.combined_score:.4f}",
            "excess_patch_score": f"{r.excess_patch.score:.4f}",
            "excess_test_score": f"{r.excess_test.score:.4f}",
            "vague_spec_score": f"{r.vague_spec.score:.4f}",
            "task_labels": ";".join(tl.label.value for tl in r.task_labels),
            "primary_label": primary,
            "label_count": len(r.task_labels),
            "patch_hunks_total": r.excess_patch.total_hunks,
            "patch_required": r.excess_patch.required_count,
            "patch_ancillary": r.excess_patch.ancillary_count,
            "patch_unrelated": r.excess_patch.unrelated_count,
            "tests_total": r.excess_test.total_tests,
            "tests_aligned": r.excess_test.aligned_count,
            "tests_tangential": r.excess_test.tangential_count,
            "tests_unrelated": r.excess_test.unrelated_count,
            "assertions_total": r.excess_test.total_assertions,
            "assertions_on_topic": r.excess_test.on_topic_assertions,
            "assertions_off_topic": r.excess_test.off_topic_assertions,
            "recommendations": "; ".join(r.recommendations),
        })

    csv_path.write_text(output.getvalue(), encoding="utf-8")

    # Stats JSON
    severity_counts: dict[str, int] = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in reports:
        severity_counts[r.severity.value] += 1

    # Label distribution
    label_counts: dict[str, int] = {}
    for r in reports:
        for tl in r.task_labels:
            label_counts[tl.label.value] = label_counts.get(tl.label.value, 0) + 1

    scores = [r.combined_score for r in reports]
    n = len(scores)
    sorted_scores = sorted(scores)

    stats = {
        "total_tasks": n,
        "severity_distribution": severity_counts,
        "label_distribution": label_counts,
        "mean_combined_score": (sum(scores) / n) if n else 0.0,
        "median_combined_score": (
            sorted_scores[n // 2] if n % 2 == 1
            else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
        ) if n else 0.0,
        "mean_excess_patch": (
            sum(r.excess_patch.score for r in reports) / n if n else 0.0
        ),
        "mean_excess_test": (
            sum(r.excess_test.score for r in reports) / n if n else 0.0
        ),
        "mean_vague_spec": (
            sum(r.vague_spec.score for r in reports) / n if n else 0.0
        ),
    }
    stats_path = output_dir / "summary_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("v3 Summary written to %s", output_dir)
    logger.info("Severity distribution: %s", severity_counts)
    logger.info("Label distribution: %s", label_counts)
