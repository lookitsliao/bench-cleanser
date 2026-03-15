"""CLI entry point for generating deep-dive case study reports.

Reads completed v2 pipeline JSON reports and produces markdown documents
with assertion-level traceability matching the Case A-D format from
severe_deep_dive.md.

Usage:
    python run_deep_dive.py --reports-dir output_v2_no_fallback/reports
    python run_deep_dive.py --reports-dir output_v2_no_fallback/reports --severity SEVERE
    python run_deep_dive.py --reports-dir output_v2_no_fallback/reports --instance-ids django__django-10999 astropy__astropy-14182
    python run_deep_dive.py --reports-dir output_v2_no_fallback/reports --output case_studies/auto/deep_dive_auto.md
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run-deep-dive",
        description="Generate deep-dive case study reports from v2 pipeline JSON reports",
    )
    p.add_argument(
        "--reports-dir",
        required=True,
        help="Path to directory containing v2 JSON reports",
    )
    p.add_argument(
        "--severity",
        default="SEVERE",
        choices=["CLEAN", "MINOR", "MODERATE", "SEVERE"],
        help="Severity filter (default: SEVERE). Use --no-filter for all.",
    )
    p.add_argument(
        "--no-filter",
        action="store_true",
        help="Include all severities (ignores --severity)",
    )
    p.add_argument(
        "--instance-ids",
        nargs="+",
        default=None,
        help="Only include specific instance IDs (space-separated)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output markdown file path (default: stdout)",
    )
    p.add_argument(
        "--title",
        default="Deep-Dive Case Studies: SEVERE Contamination Cases",
        help="Document title",
    )
    p.add_argument(
        "--dataset-name",
        default="SWE-bench",
        help="Dataset name for the document header",
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

    from bench_cleanser.deep_dive import build_deep_dive

    severity_filter = None if args.no_filter else args.severity

    document = build_deep_dive(
        reports_dir=args.reports_dir,
        severity_filter=severity_filter,
        instance_ids=args.instance_ids,
        title=args.title,
        dataset_name=args.dataset_name,
    )

    if args.output:
        output_path = pathlib.Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
        logging.info("Deep-dive report written to %s", output_path)
        print(f"Deep-dive report written to: {output_path}")
    else:
        print(document)


if __name__ == "__main__":
    main()
