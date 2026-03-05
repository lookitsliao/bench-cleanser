"""CLI entry point for bench-cleanser."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from bench_cleanser.data_loader import (
    load_all,
    load_single_task,
    load_swebench_lite,
    load_swebench_verified,
)
from bench_cleanser.pipeline import load_config, run_pipeline, process_single_task
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
        choices=["verified", "lite", "both"],
        default="both",
        help="Which SWE-bench dataset(s) to analyse (default: both)",
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
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    return p.parse_args()


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
        elif args.dataset == "lite":
            records = load_swebench_lite(max_tasks=args.max_tasks)
        else:
            records = load_all(max_per_dataset=args.max_tasks)

    logging.info("Loaded %d task(s)", len(records))

    # Run pipeline
    reports = asyncio.run(run_pipeline(records, config))

    # Print summary
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
    print(f"Output written to: {config.output_dir}/")


if __name__ == "__main__":
    main()
