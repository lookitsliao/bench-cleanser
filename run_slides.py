"""CLI entry point for generating MARP slide decks from bench-cleanser outputs.

Reads v2 pipeline reports, deep-dive case studies, and trajectory analysis
to produce a presentation-ready MARP markdown file.

Usage:
    python run_slides.py --reports-dir output_v2_no_fallback/reports
    python run_slides.py --reports-dir output_v2_no_fallback/reports \
        --deep-dive case_studies/auto/deep_dive_auto.md \
        --trajectory trajectory_analysis.md \
        --output slides/bench_cleanser_findings.md
"""

from __future__ import annotations

import argparse
import logging
import pathlib


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run-slides",
        description="Generate MARP slide deck from bench-cleanser analysis outputs",
    )
    p.add_argument(
        "--reports-dir",
        required=True,
        help="Path to directory containing v2 JSON reports",
    )
    p.add_argument(
        "--deep-dive",
        default=None,
        help="Path to deep-dive markdown document (for SEVERE case details)",
    )
    p.add_argument(
        "--trajectory",
        default=None,
        help="Path to trajectory analysis output (markdown or JSON)",
    )
    p.add_argument(
        "--output",
        default="slides/bench_cleanser_findings.md",
        help="Output MARP markdown file (default: slides/bench_cleanser_findings.md)",
    )
    p.add_argument(
        "--title",
        default="SWE-bench Contamination Analysis",
        help="Presentation title",
    )
    p.add_argument(
        "--subtitle",
        default="bench-cleanser Findings",
        help="Presentation subtitle",
    )
    p.add_argument(
        "--author",
        default="",
        help="Author name for title slide",
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

    from bench_cleanser.presentation import build_slide_deck

    deck = build_slide_deck(
        reports_dir=args.reports_dir,
        deep_dive_path=args.deep_dive,
        trajectory_path=args.trajectory,
        title=args.title,
        subtitle=args.subtitle,
        author=args.author,
    )

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(deck, encoding="utf-8")

    logging.info("MARP slide deck written to %s", output_path)
    print(f"Slide deck written to: {output_path}")
    print(f"To convert to HTML: npx @marp-team/marp-cli {output_path}")
    print(f"To convert to PDF:  npx @marp-team/marp-cli --pdf {output_path}")


if __name__ == "__main__":
    main()
