"""CLI entry point for bench-cleanser."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from bench_cleanser.data_loader import (
    load_all,
    load_single_task,
    load_swebench_live,
    load_swebench_pro,
    load_swebench_verified,
)
from bench_cleanser.pipeline import (
    load_config,
    run_pipeline,
    run_pipeline_v2,
    run_pipeline_v3,
    process_single_task,
)
from bench_cleanser.cache import ResponseCache
from bench_cleanser.llm_client import LLMClient


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench-cleanser",
        description="SWE-bench benchmark contamination detector",
    )
    p.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration YAML file (default: config.yaml)",
    )
    p.add_argument(
        "--dataset",
        choices=["verified", "pro", "live", "both"],
        default="verified",
        help="Which SWE-bench dataset(s) to analyse (default: verified)",
    )
    p.add_argument(
        "--max-tasks",
        type=int,
        default=500,
        help="Maximum tasks per dataset (default: 500)",
    )
    p.add_argument(
        "--instance-id",
        default=None,
        help="Analyse a single instance by ID (overrides --dataset)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output directory (overrides config file setting)",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Number of tasks to process in parallel (overrides config)",
    )
    p.add_argument(
        "--v2",
        action="store_true",
        help="Use v2 intent-matching pipeline (4-verdict taxonomy)",
    )
    p.add_argument(
        "--v3",
        action="store_true",
        help="Use v3 dual taxonomy pipeline (17-label Axis 1 + 8-label Axis 2)",
    )
    p.add_argument(
        "--split",
        default=None,
        help="Dataset split for SWE-bench Live (e.g., test, verified, full)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume from checkpoint — skip tasks with existing reports",
    )
    p.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Reprocess all tasks even if reports already exist (default)",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    return p.parse_args()


def _print_v1_summary(reports: list) -> None:
    """Print v1 summary to terminal."""
    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in reports:
        severity_counts[r.severity.value] += 1

    print("\n=== bench-cleanser results ===")
    print(f"Total tasks analysed: {len(reports)}")
    for sev, count in severity_counts.items():
        pct = (count / len(reports) * 100) if reports else 0
        print(f"  {sev:10s}: {count:4d}  ({pct:.1f}%)")

    mean_conf = (
        sum(r.total_confidence for r in reports) / len(reports)
        if reports
        else 0.0
    )
    print(f"Mean contamination score: {mean_conf:.4f}")


def _print_v2_summary(reports: list) -> None:
    """Print v2 summary to terminal with rich formatting if available."""
    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    for r in reports:
        severity_counts[r.severity.value] += 1

    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()

        # Summary panel
        table = Table(title="bench-cleanser v2 Results", show_header=True)
        table.add_column("Severity", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Percentage", justify="right")

        colors = {"CLEAN": "green", "MINOR": "yellow", "MODERATE": "orange3", "SEVERE": "red"}
        for sev, count in severity_counts.items():
            pct = (count / len(reports) * 100) if reports else 0
            table.add_row(
                f"[{colors[sev]}]{sev}[/{colors[sev]}]",
                str(count),
                f"{pct:.1f}%",
            )

        console.print()
        console.print(table)

        # Score summary
        mean_combined = sum(r.combined_score for r in reports) / len(reports) if reports else 0.0
        mean_ep = sum(r.excess_patch.score for r in reports) / len(reports) if reports else 0.0
        mean_et = sum(r.excess_test.score for r in reports) / len(reports) if reports else 0.0
        mean_vs = sum(r.vague_spec.score for r in reports) / len(reports) if reports else 0.0

        console.print(f"\n  Total tasks: {len(reports)}")
        console.print(f"  Mean combined score:    {mean_combined:.4f}")
        console.print(f"  Mean EXCESS_PATCH:      {mean_ep:.4f}")
        console.print(f"  Mean EXCESS_TEST:       {mean_et:.4f}")
        console.print(f"  Mean VAGUE_SPEC:        {mean_vs:.4f}")

    except ImportError:
        # Fallback to plain text
        print("\n=== bench-cleanser v2 results ===")
        print(f"Total tasks analysed: {len(reports)}")
        for sev, count in severity_counts.items():
            pct = (count / len(reports) * 100) if reports else 0
            print(f"  {sev:10s}: {count:4d}  ({pct:.1f}%)")

        mean_combined = sum(r.combined_score for r in reports) / len(reports) if reports else 0.0
        print(f"Mean combined score: {mean_combined:.4f}")


def _print_v3_summary(reports: list) -> None:
    """Print v3 dual taxonomy summary to terminal."""
    from collections import Counter

    severity_counts = {"CLEAN": 0, "MINOR": 0, "MODERATE": 0, "SEVERE": 0}
    label_counter: Counter = Counter()
    for r in reports:
        severity_counts[r.severity.value] += 1
        for la in r.task_labels:
            label_counter[la.label.value] += 1

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()

        # Severity table
        sev_table = Table(title="bench-cleanser v3 Results (Dual Taxonomy)", show_header=True)
        sev_table.add_column("Severity", style="bold")
        sev_table.add_column("Count", justify="right")
        sev_table.add_column("Percentage", justify="right")

        colors = {"CLEAN": "green", "MINOR": "yellow", "MODERATE": "orange3", "SEVERE": "red"}
        for sev, count in severity_counts.items():
            pct = (count / len(reports) * 100) if reports else 0
            sev_table.add_row(
                f"[{colors[sev]}]{sev}[/{colors[sev]}]",
                str(count),
                f"{pct:.1f}%",
            )

        console.print()
        console.print(sev_table)

        # Label distribution table
        if label_counter:
            label_table = Table(title="Axis 1 — Task Label Distribution", show_header=True)
            label_table.add_column("Label", style="bold")
            label_table.add_column("Count", justify="right")

            for label, count in label_counter.most_common():
                label_table.add_row(label, str(count))

            console.print()
            console.print(label_table)

        # Score summary
        mean_combined = sum(r.combined_score for r in reports) / len(reports) if reports else 0.0
        mean_ep = sum(r.excess_patch.score for r in reports) / len(reports) if reports else 0.0
        mean_et = sum(r.excess_test.score for r in reports) / len(reports) if reports else 0.0
        mean_vs = sum(r.vague_spec.score for r in reports) / len(reports) if reports else 0.0

        console.print(f"\n  Total tasks: {len(reports)}")
        console.print(f"  Mean combined score:    {mean_combined:.4f}")
        console.print(f"  Mean EXCESS_PATCH:      {mean_ep:.4f}")
        console.print(f"  Mean EXCESS_TEST:       {mean_et:.4f}")
        console.print(f"  Mean VAGUE_SPEC:        {mean_vs:.4f}")

    except ImportError:
        print("\n=== bench-cleanser v3 results (Dual Taxonomy) ===")
        print(f"Total tasks analysed: {len(reports)}")
        for sev, count in severity_counts.items():
            pct = (count / len(reports) * 100) if reports else 0
            print(f"  {sev:10s}: {count:4d}  ({pct:.1f}%)")

        if label_counter:
            print("\nAxis 1 — Task Label Distribution:")
            for label, count in label_counter.most_common():
                print(f"  {label:40s}: {count:4d}")

        mean_combined = sum(r.combined_score for r in reports) / len(reports) if reports else 0.0
        print(f"Mean combined score: {mean_combined:.4f}")


def main() -> None:
    args = _parse_args()

    # Logging setup
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    config = load_config(args.config)
    if args.output:
        config.output_dir = args.output
    if args.concurrency:
        config.concurrency = args.concurrency

    # Load tasks
    if args.instance_id:
        logging.info("Loading single task: %s", args.instance_id)
        record = load_single_task(args.instance_id)
        if record is None:
            logging.error("Instance %s not found in any dataset", args.instance_id)
            sys.exit(1)
        records = [record]
    else:
        logging.info("Loading dataset: %s (max %d per set)", args.dataset, args.max_tasks)
        if args.dataset == "verified":
            records = load_swebench_verified(max_tasks=args.max_tasks)
        elif args.dataset == "pro":
            records = load_swebench_pro(max_tasks=args.max_tasks)
        elif args.dataset == "live":
            split_kw = {"split": args.split} if args.split else {}
            records = load_swebench_live(max_tasks=args.max_tasks, **split_kw)
        else:
            records = load_all(max_per_dataset=args.max_tasks)

    logging.info("Loaded %d task(s)", len(records))

    # Run pipeline
    if args.v3:
        logging.info("Using v3 dual taxonomy pipeline")
        reports = asyncio.run(run_pipeline_v3(records, config, resume=args.resume))
        _print_v3_summary(reports)
    elif args.v2:
        logging.info("Using v2 intent-matching pipeline")
        reports = asyncio.run(run_pipeline_v2(records, config, resume=args.resume))
        _print_v2_summary(reports)
    else:
        reports = asyncio.run(run_pipeline(records, config))
        _print_v1_summary(reports)

    print(f"Output written to: {config.output_dir}/")


if __name__ == "__main__":
    main()
