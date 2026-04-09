"""CLI entry point for trajectory analysis.

Analyzes agent trajectories against contamination cases to classify
whether solutions show genuine problem-solving or benchmark leakage.

Uses LLM-primary analysis by default — the LLM receives the full
trajectory context plus heuristic signals and makes the final
classification decision.

Usage:
    python run_trajectory_analysis.py \
        --reports-dir output_pro_v6/reports \
        --trajectory-source trajectories/ \
        --output trajectory_analysis.md

    # Load from Docent collection
    python run_trajectory_analysis.py \
        --reports-dir output_pro_v6/reports \
        --trajectory-source 032fb63d-4992-4bfc-911d-3b7dafcb931f \
        --docent-api-key dk_... \
        --model-filter "Gemini 2.5 Pro Preview" \
        --output trajectory_analysis.md

    # Load from HuggingFace
    python run_trajectory_analysis.py \
        --reports-dir output_pro_v6/reports \
        --trajectory-source SWE-bench-Live/SWE-agent-trajectories \
        --hf-split train \
        --output trajectory_analysis.md
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run-trajectory-analysis",
        description="Analyze agent trajectories for benchmark leakage patterns",
    )
    p.add_argument(
        "--reports-dir",
        required=True,
        help="Path to directory containing v2 pipeline JSON reports",
    )
    p.add_argument(
        "--trajectory-source",
        required=True,
        help=(
            "Trajectory source: path to JSONL file, JSON directory, "
            "HuggingFace dataset name, or Docent collection UUID"
        ),
    )
    p.add_argument(
        "--severity",
        default="SEVERE",
        choices=["CLEAN", "MINOR", "MODERATE", "SEVERE"],
        help="Only analyze trajectories for this severity (default: SEVERE)",
    )
    p.add_argument(
        "--instance-ids",
        nargs="+",
        default=None,
        help="Only analyze specific instance IDs",
    )
    p.add_argument(
        "--agent-name",
        default="",
        help="Override agent name (useful for HuggingFace sources)",
    )
    p.add_argument(
        "--hf-split",
        default="train",
        help="HuggingFace dataset split (default: train)",
    )
    p.add_argument(
        "--docent-api-key",
        default="",
        help="Docent API key (or set DOCENT_API_KEY env var)",
    )
    p.add_argument(
        "--model-filter",
        default="",
        help="Filter trajectories by model name (Docent sources)",
    )
    p.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML for LLM settings (default: config.yaml)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output markdown file path (default: stdout)",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Set up LLM client
    llm = None
    try:
        from bench_cleanser.pipeline import load_config
        from bench_cleanser.cache import ResponseCache
        from bench_cleanser.llm_client import LLMClient

        config = load_config(args.config)
        cache = ResponseCache(config.cache_dir)
        llm = LLMClient(config, cache=cache)
        logging.info("LLM-primary trajectory analysis enabled (%s)", config.llm_model)
    except Exception as exc:
        logging.warning("Failed to initialize LLM client: %s — using heuristic fallback", exc)

    from bench_cleanser.trajectory.analyzer import run_trajectory_analysis

    summary = asyncio.run(run_trajectory_analysis(
        reports_dir=args.reports_dir,
        trajectory_source=args.trajectory_source,
        output_path=args.output,
        severity_filter=args.severity,
        instance_ids=args.instance_ids,
        agent_name=args.agent_name,
        hf_split=args.hf_split,
        llm=llm,
        api_key=args.docent_api_key,
        model_filter=args.model_filter,
    ))

    if not args.output:
        print(summary)
    else:
        print(f"Trajectory analysis written to: {args.output}")


if __name__ == "__main__":
    main()
