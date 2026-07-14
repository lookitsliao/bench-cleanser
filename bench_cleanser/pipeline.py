"""Pipeline orchestrator: wires Stages 1-6 together.

Provides rich terminal progress monitoring with per-stage timing,
severity distribution dashboard, and detailed per-task logging.
"""

from __future__ import annotations

import asyncio
import csv
import dataclasses
import hashlib
import io
import json
import logging
import os
import pathlib
import re
import time
from typing import Any

import yaml
from tqdm import tqdm

from bench_cleanser.analysis.cross_ref import analyze_cross_references
from bench_cleanser.analysis.patch_analyzer import analyze_patch
from bench_cleanser.analysis.scope_analyzer import extract_intent
from bench_cleanser.analysis.structural_diff import compute_structural_diff
from bench_cleanser.analysis.test_analyzer import analyze_tests
from bench_cleanser.cache import ResponseCache
from bench_cleanser.classification.scorer import build_report
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
    DescriptionClarity,
    IntentStatement,
    ParsedTask,
    PatchAnalysis,
    PipelineConfig,
    Severity,
    TaskContaminationLabel,
    TaskRecord,
    TestAnalysis,
)
from bench_cleanser.parsing.patch_parser import get_files_from_patch, parse_patch
from bench_cleanser.parsing.test_parser import (
    match_f2p_tests_to_hunks,
    parse_test_patch,
)
from bench_cleanser.repo_manager import RepoManager, validate_relative_file_path
from bench_cleanser.static_analysis import (
    build_call_targets,
    extract_assertions,
    identify_tested_functions,
    resolve_imports,
)

logger = logging.getLogger(__name__)

_PROVENANCE_VERSION = 1
_INSTANCE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_REPORT_REQUIRED_KEYS = {
    "instance_id",
    "severity",
    "intent",
    "patch_analysis",
    "test_analysis",
    "description_clarity",
    "task_labels",
    "agent_labels",
    "recommendations",
    "_provenance",
}


class PipelineRunReports(list[ContaminationReport]):
    """List-compatible pipeline result with invocation-level failure counts."""

    def __init__(
        self,
        reports: list[ContaminationReport],
        *,
        attempted_count: int,
        resumed_count: int,
        new_success_count: int,
        new_failure_count: int,
    ) -> None:
        super().__init__(reports)
        self.attempted_count = attempted_count
        self.resumed_count = resumed_count
        self.new_success_count = new_success_count
        self.new_failure_count = new_failure_count


def validate_instance_id(instance_id: str) -> str:
    """Validate an instance identifier before using it as an output name."""
    if not isinstance(instance_id, str) or not _INSTANCE_ID_RE.fullmatch(instance_id):
        raise ValueError(f"Unsafe instance_id for report output: {instance_id!r}")
    return instance_id


def _safe_report_path(reports_dir: pathlib.Path, instance_id: str) -> pathlib.Path:
    """Return the confined report path for a validated instance identifier."""
    instance_id = validate_instance_id(instance_id)
    root = reports_dir.resolve()
    candidate = (root / f"{instance_id}.json").resolve(strict=False)
    if candidate.parent != root:
        raise ValueError(f"Report path escapes output directory: {candidate}")
    return candidate


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _report_provenance(record: TaskRecord, config: PipelineConfig) -> dict[str, Any]:
    """Build deterministic input/config fingerprints for safe resume."""
    config_data = dataclasses.asdict(config)
    # Preserve dynamically-added compatibility fields until all callers use
    # the latest PipelineConfig dataclass (notably code_visitation_enabled).
    for key, value in vars(config).items():
        config_data.setdefault(key, value)
    # Credentials authorize the same analytical configuration; rotating a key
    # must not invalidate reports, and secret-derived material does not belong
    # in persisted provenance even as a one-way digest input.
    config_data.pop("llm_api_key", None)
    return {
        "version": _PROVENANCE_VERSION,
        "input_sha256": _canonical_digest(dataclasses.asdict(record)),
        "config_sha256": _canonical_digest(config_data),
    }


def _report_payload(
    report: ContaminationReport,
    record: TaskRecord,
    config: PipelineConfig,
) -> dict[str, Any]:
    payload = report.to_dict()
    payload["_provenance"] = _report_provenance(record, config)
    return payload


def _require_complete_report_shape(data: dict[str, Any]) -> None:
    missing = _REPORT_REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"report is incomplete; missing {sorted(missing)}")
    nested_requirements = {
        "intent": {
            "core_requirement", "behavioral_contract", "acceptance_criteria",
            "out_of_scope", "ambiguity_score",
        },
        "patch_analysis": {
            "total_hunks", "required_count", "ancillary_count", "unrelated_count", "hunks",
        },
        "test_analysis": {
            "total_tests", "aligned_count", "tangential_count", "unrelated_count",
            "total_assertions", "on_topic_assertions", "off_topic_assertions",
            "has_modified_tests", "tests",
        },
        "description_clarity": {"score", "reasoning"},
    }
    for section, required in nested_requirements.items():
        value = data.get(section)
        if not isinstance(value, dict):
            raise ValueError(f"report section {section!r} is not an object")
        section_missing = required - value.keys()
        if section_missing:
            raise ValueError(
                f"report section {section!r} is incomplete; missing {sorted(section_missing)}"
            )
    if not isinstance(data["task_labels"], list):
        raise ValueError("report task_labels is not a list")
    if not isinstance(data["agent_labels"], dict):
        raise ValueError("report agent_labels is not an object")
    if not isinstance(data["recommendations"], list):
        raise ValueError("report recommendations is not a list")


def _load_resumable_report(
    report_path: pathlib.Path,
    record: TaskRecord,
    config: PipelineConfig,
) -> ContaminationReport | None:
    """Load a complete, successful, provenance-matched report or return None."""
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("report root is not an object")
        _require_complete_report_shape(data)
        if data.get("instance_id") != record.instance_id:
            raise ValueError("report instance_id does not match input task")
        if data.get("pipeline_error"):
            raise ValueError("report records a pipeline error")
        if data.get("_provenance") != _report_provenance(record, config):
            raise ValueError("report provenance is stale or does not match this run")
        report = ContaminationReport.from_dict(data)
        if report.pipeline_error is not None:
            raise ValueError("report records a pipeline error")
        return report
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("Resume rejected report %s: %s", report_path, exc)
        return None


def _validate_patch_paths(patch_text: str, field_name: str) -> None:
    """Reject absolute or traversing paths in every unified-diff header."""
    if not patch_text:
        return
    for raw_line in patch_text.splitlines():
        paths: list[str] = []
        match = re.match(r"^diff --git a/(.+?) b/(.+)$", raw_line)
        if match:
            paths.extend(match.groups())
        elif raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            path = raw_line[4:].split("\t", 1)[0]
            if path == "/dev/null":
                continue
            if path.startswith("a/") or path.startswith("b/"):
                path = path[2:]
            paths.append(path)
        for path in paths:
            try:
                validate_relative_file_path(path)
            except ValueError as exc:
                raise ValueError(f"Unsafe path in {field_name}: {path!r}") from exc


def _atomic_write_text(path: pathlib.Path, payload: str) -> None:
    """Atomically write *payload* to *path* via a same-directory tempfile.

    A bare ``Path.write_text`` is not atomic: an interrupt mid-write leaves
    a truncated file on disk, which ``--resume`` will then re-load as if it
    were a real report. ``os.replace`` is atomic on POSIX and on Windows
    NTFS, so a reader either sees the previous contents or the new ones.
    """
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_config(config_path: str | os.PathLike[str] | None = None) -> PipelineConfig:
    """Load configuration from *config_path* or the packaged default.

    Using a package resource for the default keeps the console scripts usable
    after a wheel is installed from outside the source checkout.
    """
    if config_path is None:
        from importlib.resources import files

        config_text = (
            files("bench_cleanser")
            .joinpath("default_config.yaml")
            .read_text(encoding="utf-8")
        )
        raw = yaml.safe_load(config_text) or {}
    else:
        with open(config_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    def _expand(val: Any) -> Any:
        if isinstance(val, str) and "${" in val:
            import re
            return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), val)
        return val

    llm = raw.get("llm", {})
    pipeline = raw.get("pipeline", {})
    code_visit = raw.get("code_visitation", {})

    api_key_env = str(llm.get("api_key_env", "OPENAI_API_KEY"))
    configured_api_key = _expand(llm.get("api_key", ""))
    # An unresolved ${VAR} is not a credential and should fail with the
    # client's actionable missing-key message rather than being sent upstream.
    if isinstance(configured_api_key, str) and "${" in configured_api_key:
        configured_api_key = ""
    api_key = str(configured_api_key or os.environ.get(api_key_env, ""))

    base_url_env = str(llm.get("base_url_env", "OPENAI_BASE_URL"))
    configured_base_url = _expand(
        llm.get("base_url", "https://api.openai.com/v1")
    )
    base_url = os.environ.get(base_url_env) or configured_base_url

    return PipelineConfig(
        llm_provider=str(llm.get("provider", "openai-compatible")),
        llm_api_key=api_key,
        llm_api_key_env=api_key_env,
        llm_base_url=str(base_url),
        llm_model=str(llm.get("model", "gpt-4.1")),
        llm_max_tokens=int(llm.get("max_tokens", 32768)),
        llm_reasoning_effort=llm.get("reasoning_effort"),
        llm_request_timeout_seconds=float(llm.get("request_timeout_seconds", 180.0)),
        llm_retry_timeout_seconds=float(llm.get("retry_timeout_seconds", 600.0)),
        max_concurrent_requests=llm.get("max_concurrent_requests", 10),
        retry_attempts=llm.get("retry_attempts", 7),
        retry_delay_seconds=llm.get("retry_delay_seconds", 5.0),
        concurrency=pipeline.get("concurrency", 5),
        cache_dir=pipeline.get("cache_dir", ".cache/llm_responses"),
        output_dir=pipeline.get("output_dir", "output"),
        code_visitation_enabled=bool(code_visit.get("enabled", True)),
        repo_cache_dir=code_visit.get("repo_cache_dir", ".cache/repos"),
        clone_timeout_seconds=code_visit.get("clone_timeout_seconds", 120),
        max_source_context_lines=code_visit.get("max_source_context_lines", 200),
    )


def parse_task(record: TaskRecord) -> ParsedTask:
    """Stage 1: parse a raw task record into structured form."""
    _validate_patch_paths(record.patch, "patch")
    _validate_patch_paths(record.test_patch, "test_patch")
    patch_hunks = parse_patch(record.patch)
    test_hunks = parse_test_patch(record.test_patch)
    gold_files = get_files_from_patch(record.patch)
    test_files = get_files_from_patch(record.test_patch)
    for file_path in [
        *(hunk.file_path for hunk in patch_hunks),
        *(hunk.file_path for hunk in test_hunks),
        *gold_files,
        *test_files,
    ]:
        validate_relative_file_path(file_path)
    f2p_matched, f2p_unmatched = match_f2p_tests_to_hunks(
        record.fail_to_pass, test_hunks
    )
    return ParsedTask(
        record=record,
        patch_hunks=patch_hunks,
        test_hunks=test_hunks,
        f2p_test_hunks=f2p_matched,
        f2p_tests_with_no_hunk=f2p_unmatched,
        files_in_gold_patch=gold_files,
        files_in_test_patch=test_files,
    )


def enrich_with_code_context(
    parsed: ParsedTask,
    repo_manager: RepoManager,
    config: PipelineConfig,
) -> None:
    """Stage 1.5: clone the repo and attach CodeContext to each F2P test hunk."""
    record = parsed.record
    repo_path = repo_manager.get_repo_path(record.repo, record.base_commit)
    if repo_path is None:
        logger.warning("Code visitation skipped for %s: clone failed", record.instance_id)
        return

    max_lines = config.max_source_context_lines

    for test_hunk in parsed.f2p_test_hunks:
        try:
            test_file = test_hunk.file_path
            test_file_content = repo_manager.get_file(repo_path, test_file) or ""

            pre_patch_source = get_full_test_source(
                repo_path, test_file, test_hunk.test_name, max_lines=max_lines
            )
            post_patch_source = get_post_patch_test_source(
                pre_patch_source, test_hunk.test_name,
                test_hunk.added_lines, test_hunk.removed_lines,
                raw_diff=test_hunk.raw_diff,
                max_lines=max_lines,
            )

            imports_text = extract_imports(test_file_content) if test_file_content else ""
            fixtures_text = extract_fixtures(test_file_content, test_hunk.test_name) if test_file_content else ""
            import_map = resolve_imports(test_file_content, repo_path) if test_file_content else {}

            analysis_source = post_patch_source or test_hunk.full_source
            tested_funcs = identify_tested_functions(
                analysis_source, import_map, parsed.files_in_gold_patch,
                repo_path, max_source_lines=max_lines,
            )
            call_targets = build_call_targets(analysis_source, import_map, parsed.files_in_gold_patch)
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
                "Code context: %s — %d tested funcs, %d calls, %d assertions",
                test_hunk.test_name, len(tested_funcs), len(call_targets), len(assertions),
            )
        except Exception as exc:
            logger.warning(
                "Code visitation failed for %s: %s",
                test_hunk.test_name,
                exc,
                exc_info=True,
            )


def _log_code_context(parsed: ParsedTask, instance_id: str) -> None:
    """Emit per-test code-context summaries at DEBUG level (visible with ``-v``).

    A missing context block is a real signal and stays at WARNING.
    """
    for th in parsed.f2p_test_hunks:
        ctx = th.code_context
        if ctx is None:
            logger.warning("[%s] %s: NO code context", instance_id, th.test_name)
            continue
        logger.debug(
            "[%s] %s: %d tested functions, %d call targets, "
            "%d assertions, pre_patch=%s",
            instance_id, th.test_name,
            len(ctx.tested_functions), len(ctx.call_targets),
            len(ctx.assertions),
            "yes" if ctx.pre_patch_test_source else "no",
        )
        for tf in ctx.tested_functions:
            tag = "PATCHED" if tf.is_modified_by_patch else "unpatched"
            logger.debug(
                "  -> %s [%s] %s (%d lines)",
                tf.name, tag, tf.file_path,
                len(tf.source.splitlines()) if tf.source else 0,
            )


async def process_single_task(
    record: TaskRecord,
    llm: LLMClient,
    config: PipelineConfig,
    repo_manager: RepoManager | None = None,
) -> ContaminationReport:
    """Run the full pipeline on a single task with per-stage timing.

    Stages:
      1.  PARSE — extract diffs from gold patch + test patch
      1.5 CODE VISITATION — clone repo, attach full test/function source
      2.  INTENT — extract intent from problem statement (blind to patch)
      3.  STRUCTURAL DIFF — AST-level changed block + test block extraction
      4.  INTENT MATCHING — classify patches (4A) and tests (4B) in parallel
      5.  CLASSIFICATION — dual taxonomy labels + bucket severity
    """
    stage_times: dict[str, float] = {}
    iid = record.instance_id

    # Stage 1: PARSE
    t0 = time.monotonic()
    parsed = parse_task(record)
    stage_times["parse"] = time.monotonic() - t0

    # Stage 1.5: CODE VISITATION
    t0 = time.monotonic()
    code_visitation_enabled = bool(getattr(config, "code_visitation_enabled", True))
    if repo_manager is not None and code_visitation_enabled:
        enrich_with_code_context(parsed, repo_manager, config)
    stage_times["code_visit"] = time.monotonic() - t0

    # Stage 2: INTENT
    t0 = time.monotonic()
    intent = await extract_intent(record, llm, problem_code_context=parsed.problem_code_context)
    stage_times["intent"] = time.monotonic() - t0

    # Stage 3: STRUCTURAL DIFF
    t0 = time.monotonic()
    structural_diff = None
    if repo_manager is not None and code_visitation_enabled:
        repo_path = repo_manager.get_repo_path(record.repo, record.base_commit)
        if repo_path is not None:
            try:
                structural_diff = compute_structural_diff(parsed, repo_path)
            except Exception as exc:
                logger.error("Structural diff failed for %s: %s", iid, exc, exc_info=True)
    if structural_diff is None:
        logger.warning(
            "No structural context for %s — intent matching will run without "
            "call graph or function source. Results may be less precise.",
            iid,
        )
    stage_times["structural"] = time.monotonic() - t0

    _log_code_context(parsed, iid)

    # Stage 4: INTENT MATCHING (4A + 4B in parallel)
    t0 = time.monotonic()
    patch_task = analyze_patch(parsed, intent, llm, structural_diff)
    test_task = analyze_tests(parsed, intent, llm, structural_diff)
    patch_analysis, test_analysis = await asyncio.gather(patch_task, test_task)
    stage_times["intent_match"] = time.monotonic() - t0

    # Cross-reference analysis
    t0 = time.monotonic()
    cross_ref = analyze_cross_references(
        patch_analysis=patch_analysis,
        test_analysis=test_analysis,
        f2p_test_hunks=parsed.f2p_test_hunks,
        structural_diff=structural_diff,
    )
    if cross_ref.has_coupling:
        logger.info(
            "[%s] Cross-reference: %d overpatch-overtest coupling(s) detected",
            iid, len(cross_ref.couplings),
        )
    stage_times["cross_ref"] = time.monotonic() - t0

    description_clarity = DescriptionClarity(
        score=intent.ambiguity_score,
        reasoning=intent.behavioral_contract[:500] if intent.behavioral_contract else "",
    )

    # Stage 5: CLASSIFICATION
    t0 = time.monotonic()
    report = await build_report(
        intent, patch_analysis, test_analysis, description_clarity, config,
        record=record, llm=llm, cross_ref=cross_ref,
    )
    stage_times["classify"] = time.monotonic() - t0

    total = sum(stage_times.values())
    logger.info(
        "[%s] %s (%.1fs) | parse=%.1f intent=%.1f struct=%.1f "
        "match=%.1f xref=%.1f classify=%.1f",
        iid, report.severity.value, total,
        stage_times["parse"], stage_times["intent"],
        stage_times["structural"], stage_times["intent_match"],
        stage_times["cross_ref"], stage_times["classify"],
    )

    return report


async def run_pipeline(
    records: list[TaskRecord],
    config: PipelineConfig,
    *,
    resume: bool = True,
) -> list[ContaminationReport]:
    """Run the pipeline on a batch of tasks with progress display.

    Reports are written to disk as they complete. With ``resume=True``, only
    complete, successful reports whose input and configuration fingerprints
    match this invocation are reused.
    """
    original_records = list(records)
    seen_ids: set[str] = set()
    for record in original_records:
        instance_id = validate_instance_id(record.instance_id)
        if instance_id in seen_ids:
            raise ValueError(f"Duplicate instance_id in pipeline input: {instance_id!r}")
        seen_ids.add(instance_id)

    cache = ResponseCache(config.cache_dir)
    llm = LLMClient(config, cache=cache)

    repo_manager: RepoManager | None = None
    if bool(getattr(config, "code_visitation_enabled", True)):
        repo_manager = RepoManager(
            cache_dir=config.repo_cache_dir,
            clone_timeout=config.clone_timeout_seconds,
        )
        logger.info("Pre-cloning repos for code visitation and structural analysis")
        clone_results = repo_manager.pre_clone_repos(original_records)
        logger.info(
            "Pre-clone complete: %d/%d repos available",
            sum(1 for value in clone_results.values() if value),
            len(clone_results),
        )
    else:
        logger.info("Code visitation disabled; skipping repository clones and structural analysis")

    output_dir = pathlib.Path(config.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    reports_dir = (output_dir / "reports").resolve(strict=False)
    if reports_dir.parent != output_dir:
        raise ValueError(f"Reports directory escapes output root: {reports_dir}")
    reports_dir.mkdir(parents=True, exist_ok=True)

    resumed_reports: dict[str, ContaminationReport] = {}
    pending_records: list[TaskRecord] = []
    if resume:
        for record in original_records:
            report_path = _safe_report_path(reports_dir, record.instance_id)
            resumed = (
                _load_resumable_report(report_path, record, config)
                if report_path.is_file()
                else None
            )
            if resumed is None:
                pending_records.append(record)
            else:
                resumed_reports[record.instance_id] = resumed
        if resumed_reports:
            logger.info(
                "Resume: reusing %d/%d provenance-matched reports",
                len(resumed_reports),
                len(original_records),
            )
    else:
        pending_records = original_records
    records = pending_records

    semaphore = asyncio.Semaphore(config.concurrency)
    severity_counts = {sev.value: 0 for sev in Severity}
    for report in resumed_reports.values():
        severity_counts[report.severity.value] += 1

    try:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )
        from rich.table import Table

        from bench_cleanser._console import get_console, truncate_status
        use_rich = True
    except ImportError:
        use_rich = False

    reports: list[ContaminationReport] = list(resumed_reports.values())
    new_reports: list[ContaminationReport] = []
    error_count = 0
    start_time = time.monotonic()

    async def _process(record: TaskRecord, progress_callback: Any = None) -> ContaminationReport:
        nonlocal error_count
        async with semaphore:
            try:
                report = await process_single_task(record, llm, config, repo_manager=repo_manager)
            except Exception as exc:
                error_count += 1
                logger.error("Failed to process %s: %s", record.instance_id, exc, exc_info=True)
                dummy_intent = IntentStatement(
                    instance_id=record.instance_id,
                    core_requirement=f"PIPELINE_ERROR: {exc}",
                    behavioral_contract="", acceptance_criteria=[], out_of_scope="",
                    ambiguity_score=0.0, raw_llm_response=f"Pipeline error: {exc}",
                )
                # Pipeline errors are not contamination findings; SEVERE
                # would inflate counts and trip Stage-7 into spurious
                # CONTAMINATED_PASS. `pipeline_error` is the filter flag.
                report = ContaminationReport(
                    instance_id=record.instance_id,
                    severity=Severity.CLEAN,
                    intent=dummy_intent,
                    patch_analysis=PatchAnalysis(total_hunks=0, required_count=0, ancillary_count=0, unrelated_count=0),
                    test_analysis=TestAnalysis(total_tests=0, aligned_count=0, tangential_count=0, unrelated_count=0, total_assertions=0, on_topic_assertions=0, off_topic_assertions=0, has_modified_tests=False),
                    description_clarity=DescriptionClarity(score=0.0, reasoning=f"PIPELINE_ERROR: {exc}"),
                    pipeline_error=f"{type(exc).__name__}: {exc}",
                )

            report_path = _safe_report_path(reports_dir, record.instance_id)
            # Atomic write so an interrupt or concurrent reader can never
            # observe a half-written report. --resume scans for these files
            # by name; truncated JSON would silently poison the next run.
            _atomic_write_text(
                report_path,
                json.dumps(
                    _report_payload(report, record, config),
                    indent=2,
                    ensure_ascii=False,
                ),
            )
            # Exclude pipeline-error rows from the live severity dashboard
            # so CLEAN doesn't get inflated by failures.
            if report.pipeline_error is None:
                severity_counts[report.severity.value] += 1
            if progress_callback is not None:
                progress_callback()
            return report

    if use_rich:
        console = get_console()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]bench-cleanser"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("|"),
            TimeRemainingColumn(),
            TextColumn("|"),
            TextColumn("[dim]{task.fields[status]}"),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                "Processing", total=len(records),
                status="Starting...",
            )
            def _update_progress():
                elapsed = time.monotonic() - start_time
                completed = sum(severity_counts.values())
                rate_per_min = (completed / elapsed * 60) if elapsed > 0 else 0
                status_parts = [
                    f"[green]CLEAN:{severity_counts['CLEAN']}[/green]",
                    f"[yellow]MINOR:{severity_counts['MINOR']}[/yellow]",
                    f"[orange3]MOD:{severity_counts['MODERATE']}[/orange3]",
                    f"[red]SEV:{severity_counts['SEVERE']}[/red]",
                ]
                if error_count:
                    status_parts.append(f"[red bold]ERR:{error_count}[/red bold]")
                status_parts.append(f"[dim]{rate_per_min:.1f}/min[/dim]")
                progress.update(task_id, advance=1, status=truncate_status(status_parts))
            tasks = [_process(record, _update_progress) for record in records]
            new_reports = list(await asyncio.gather(*tasks))
            reports.extend(new_reports)

        final_table = Table(title="Pipeline Complete", show_header=True, header_style="bold")
        final_table.add_column("Metric", style="bold")
        final_table.add_column("Value", justify="right")
        total_time = time.monotonic() - start_time
        analytic_count = sum(1 for r in reports if r.pipeline_error is None)
        error_reports_count = sum(1 for r in reports if r.pipeline_error is not None)
        final_table.add_row("Total tasks", str(len(reports)))
        final_table.add_row("Analytic tasks", str(analytic_count))
        if error_reports_count:
            final_table.add_row(
                "[red bold]Pipeline errors[/red bold]", str(error_reports_count),
            )
        final_table.add_row("Elapsed", f"{total_time:.1f}s")
        final_table.add_row("Rate", f"{len(reports)/total_time*60:.1f}/min" if total_time > 0 else "N/A")
        final_table.add_row("[green]CLEAN[/green]", str(severity_counts["CLEAN"]))
        final_table.add_row("[yellow]MINOR[/yellow]", str(severity_counts["MINOR"]))
        final_table.add_row("[orange3]MODERATE[/orange3]", str(severity_counts["MODERATE"]))
        final_table.add_row("[red]SEVERE[/red]", str(severity_counts["SEVERE"]))
        if error_count:
            final_table.add_row("[red bold]ERRORS[/red bold]", str(error_count))
        console.print()
        console.print(final_table)
    else:
        progress_bar = tqdm(total=len(records), desc="bench-cleanser", unit="task")
        def _update_tqdm():
            progress_bar.update(1)
            progress_bar.set_postfix(severity_counts)
        tasks = [_process(record, _update_tqdm) for record in records]
        new_reports = list(await asyncio.gather(*tasks))
        reports.extend(new_reports)
        progress_bar.close()

    reports_by_id = {report.instance_id: report for report in reports}
    ordered_reports = [reports_by_id[record.instance_id] for record in original_records]
    new_failure_count = sum(report.pipeline_error is not None for report in new_reports)
    new_success_count = len(new_reports) - new_failure_count
    run_stats = {
        "attempted_tasks": len(records),
        "resumed_tasks": len(resumed_reports),
        "new_successes": new_success_count,
        "new_failures": new_failure_count,
    }
    result = PipelineRunReports(
        ordered_reports,
        attempted_count=len(records),
        resumed_count=len(resumed_reports),
        new_success_count=new_success_count,
        new_failure_count=new_failure_count,
    )
    _write_summary(result, output_dir, run_stats=run_stats)
    return result


def _write_summary(
    reports: list[ContaminationReport],
    output_dir: pathlib.Path,
    *,
    run_stats: dict[str, int] | None = None,
) -> None:
    """Write aggregate summary CSV and stats JSON.

    Pipeline-error rows are written to the CSV with a clear marker so the
    operator can see them, but are excluded from the aggregate severity
    and label distributions — they carry no analytic signal and would
    otherwise inflate the published numbers.
    """
    output_dir = output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    csv_path = output_dir / "summary.csv"
    fieldnames = [
        "instance_id", "severity",
        "task_labels", "primary_label", "label_count",
        "patch_hunks_total", "patch_unrelated", "has_unrelated_hunks",
        "tests_total", "tests_unrelated", "has_off_topic_assertions",
        "has_modified_tests", "clarity_score",
        "legitimacy", "suggested_fix",
        "mentioned_entities",
        "recommendations",
        "pipeline_error",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    LABEL_PRIORITY = [
        TaskContaminationLabel.APPROACH_LOCK,
        TaskContaminationLabel.OVER_TEST,
        TaskContaminationLabel.OVER_PATCH,
        TaskContaminationLabel.UNCLEAR_DESCRIPTION,
        TaskContaminationLabel.HIDDEN_CONTEXT,
        TaskContaminationLabel.WEAK_COVERAGE,
        TaskContaminationLabel.CLEAN,
    ]

    for r in reports:
        primary = min(r.task_labels, key=lambda tl: LABEL_PRIORITY.index(tl.label)).label.value if r.task_labels else ""

        decomp = r.intent.decomposition
        entities = []
        if decomp:
            for name in decomp.mentioned_files + decomp.mentioned_functions + decomp.mentioned_classes:
                if name and name not in entities:
                    entities.append(name)

        writer.writerow({
            "instance_id": r.instance_id,
            "severity": r.severity.value,
            "task_labels": ";".join(tl.label.value for tl in r.task_labels),
            "primary_label": primary,
            "label_count": len(r.task_labels),
            "patch_hunks_total": r.patch_analysis.total_hunks,
            "patch_unrelated": r.patch_analysis.unrelated_count,
            "has_unrelated_hunks": r.patch_analysis.unrelated_count > 0,
            "tests_total": r.test_analysis.total_tests,
            "tests_unrelated": r.test_analysis.unrelated_count,
            "has_off_topic_assertions": r.test_analysis.off_topic_assertions > 0 or r.test_analysis.unrelated_count > 0,
            "has_modified_tests": r.test_analysis.has_modified_tests,
            "clarity_score": f"{r.description_clarity.score:.4f}",
            "legitimacy": decomp.legitimacy if decomp else "",
            "suggested_fix": (decomp.suggested_fix[:200] if decomp and decomp.suggested_fix else ""),
            "mentioned_entities": ";".join(entities[:15]),
            "recommendations": "; ".join(r.recommendations),
            "pipeline_error": r.pipeline_error or "",
        })

    _atomic_write_text(csv_path, output.getvalue())

    # Pipeline-error rows are excluded from the aggregate distributions but
    # surfaced separately so the operator can see they exist.
    analytic_reports = [r for r in reports if r.pipeline_error is None]
    error_reports = [r for r in reports if r.pipeline_error is not None]

    severity_counts: dict[str, int] = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in analytic_reports:
        severity_counts[r.severity.value] += 1

    label_counts: dict[str, int] = {}
    for r in analytic_reports:
        for tl in r.task_labels:
            label_counts[tl.label.value] = label_counts.get(tl.label.value, 0) + 1

    stats = {
        "total_tasks": len(reports),
        "analytic_tasks": len(analytic_reports),
        "pipeline_errors": len(error_reports),
        "failed_tasks": [
            {"instance_id": report.instance_id, "error": report.pipeline_error}
            for report in error_reports
        ],
        "severity_distribution": severity_counts,
        "label_distribution": label_counts,
    }
    if run_stats is not None:
        stats["run"] = run_stats
    stats_path = output_dir / "summary_stats.json"
    _atomic_write_text(
        stats_path,
        json.dumps(stats, indent=2, ensure_ascii=False),
    )

    logger.debug("Summary written to %s", output_dir)
    logger.debug("Severity: %s", severity_counts)
    logger.debug("Labels: %s", label_counts)
