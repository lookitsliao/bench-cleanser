#!/usr/bin/env python3
"""Forensic analysis of v3 dual taxonomy pipeline results.

Mines all 500 SWE-bench Verified task reports and produces:
1. Label distribution and co-occurrence matrix
2. Per-label case inventories with evidence chains
3. Score distribution analysis
4. Edge case and outlier detection
5. V3 vs V2 comparison data
6. Reviewer-friendly triage CSV
"""

import json
import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from itertools import combinations

# ── Configuration ──────────────────────────────────────────────────────
REPORTS_DIR = Path("output_pro_v6/reports")
V2_REPORTS_DIR = Path("output_pro_v5/reports")
OUTPUT_DIR = Path("output_pro_v6")
ANALYSIS_DIR = Path("analysis_v3")
ANALYSIS_DIR.mkdir(exist_ok=True)

# Plain-English label explanations for reviewers (v4 taxonomy)
LABEL_EXPLANATIONS = {
    "clean": "No contamination. Problem, patch, and tests are all fair and aligned.",
    "approach_lock": "Tests require a specific implementation approach the problem doesn't determine. A correct-but-different solution would fail.",
    "wide_tests": "Tests check things BEYOND what the problem asked for. An agent solving only the stated problem would fail extra tests.",
    "test_mutation": "A pre-existing test was quietly modified to check new behavior not mentioned in the problem.",
    "scope_creep": "The gold patch includes behavioral changes beyond what the problem asks for (not just cleanup/imports).",
    "unclear_spec": "The problem is too ambiguous or actively misleading -- multiple incompatible approaches are equally reasonable.",
    "hidden_context": "Critical solution info (function names, root cause, design decisions) appears only in hints text, not the main problem.",
    "weak_coverage": "Tests or patch don't fully cover stated acceptance criteria. A partial fix could still pass.",
}

SEVERITY_ORDER = ["CLEAN", "MINOR", "MODERATE", "SEVERE"]

# v4: No weights — severity is bucket-based. Legacy mapping for backward compat only.
LABEL_WEIGHTS: dict[str, float] = {}


def load_reports(reports_dir: Path) -> list[dict]:
    """Load all JSON reports from a directory."""
    reports = []
    for f in sorted(reports_dir.iterdir()):
        if f.suffix == ".json":
            with open(f, encoding="utf-8") as fh:
                reports.append(json.load(fh))
    return reports


def extract_labels(report: dict) -> list[str]:
    """Extract label strings from a report."""
    return [la["label"] for la in report.get("task_labels", [])]


def extract_label_details(report: dict) -> list[dict]:
    """Extract full label details including confidence and evidence."""
    return report.get("task_labels", [])


def analyze_distributions(reports: list[dict]) -> dict:
    """Compute severity and label distributions."""
    severity_counts = Counter()
    label_counts = Counter()
    label_confidence = defaultdict(list)
    scores = []

    for r in reports:
        severity_counts[r["severity"]] += 1
        scores.append(r["combined_score"])
        for la in r.get("task_labels", []):
            label_counts[la["label"]] += 1
            label_confidence[la["label"]].append(la.get("confidence", 0.0))

    return {
        "severity_counts": dict(severity_counts),
        "label_counts": dict(label_counts.most_common()),
        "label_mean_confidence": {
            k: sum(v) / len(v) for k, v in label_confidence.items()
        },
        "score_stats": {
            "mean": sum(scores) / len(scores),
            "median": sorted(scores)[len(scores) // 2],
            "min": min(scores),
            "max": max(scores),
            "p25": sorted(scores)[len(scores) // 4],
            "p75": sorted(scores)[3 * len(scores) // 4],
        },
        "total": len(reports),
    }


def analyze_cooccurrence(reports: list[dict]) -> dict:
    """Build label co-occurrence matrix."""
    pair_counts = Counter()
    label_set_counts = Counter()

    for r in reports:
        labels = extract_labels(r)
        contam_labels = [l for l in labels if l != "clean"]
        label_set_counts[tuple(sorted(contam_labels))] += 1
        for a, b in combinations(sorted(set(contam_labels)), 2):
            pair_counts[(a, b)] += 1

    return {
        "pair_counts": {f"{a} + {b}": c for (a, b), c in pair_counts.most_common(30)},
        "common_label_sets": {
            " | ".join(k) if k else "(clean)": v
            for k, v in label_set_counts.most_common(20)
        },
    }


def find_case_studies(reports: list[dict]) -> dict:
    """Select representative cases for each label and edge case category."""
    cases = {}

    # Best example per label (highest confidence)
    label_examples = defaultdict(list)
    for r in reports:
        for la in r.get("task_labels", []):
            label_examples[la["label"]].append((
                la.get("confidence", 0.0),
                r["instance_id"],
                r["severity"],
                r["combined_score"],
                la.get("evidence", []),
                la.get("reasoning", ""),
                extract_labels(r),
            ))

    for label, examples in label_examples.items():
        examples.sort(key=lambda x: x[0], reverse=True)
        top3 = examples[:3]
        cases[label] = {
            "count": len(examples),
            "top_cases": [
                {
                    "instance_id": ex[1],
                    "severity": ex[2],
                    "combined_score": ex[3],
                    "confidence": ex[0],
                    "evidence": ex[4],
                    "reasoning": ex[5],
                    "all_labels": ex[6],
                }
                for ex in top3
            ],
        }

    # Edge cases: high score but CLEAN label
    edge_clean_high_score = [
        r for r in reports
        if r["severity"] == "CLEAN" and r["combined_score"] > 0.1
    ]
    cases["_edge_clean_high_score"] = [
        {"instance_id": r["instance_id"], "score": r["combined_score"],
         "labels": extract_labels(r)}
        for r in edge_clean_high_score[:5]
    ]

    # Edge cases: SEVERE with low score
    edge_severe_low_score = [
        r for r in reports
        if r["severity"] == "SEVERE" and r["combined_score"] < 0.5
    ]
    cases["_edge_severe_low_score"] = [
        {"instance_id": r["instance_id"], "score": r["combined_score"],
         "labels": extract_labels(r)}
        for r in edge_severe_low_score[:5]
    ]

    # Single-label SEVERE (clean signal)
    single_label_severe = [
        r for r in reports
        if r["severity"] == "SEVERE" and len(extract_labels(r)) == 1
    ]
    cases["_single_label_severe"] = [
        {"instance_id": r["instance_id"], "score": r["combined_score"],
         "label": extract_labels(r)[0]}
        for r in single_label_severe[:10]
    ]

    # Maximum label count
    max_labels = sorted(reports, key=lambda r: len(extract_labels(r)), reverse=True)
    cases["_most_labels"] = [
        {"instance_id": r["instance_id"], "label_count": len(extract_labels(r)),
         "labels": extract_labels(r), "severity": r["severity"],
         "score": r["combined_score"]}
        for r in max_labels[:5]
    ]

    return cases


def analyze_excess_patch_patterns(reports: list[dict]) -> dict:
    """Analyze excess patch scoring patterns."""
    ep_scores = []
    hunk_stats = {"total": 0, "required": 0, "ancillary": 0, "unrelated": 0}
    high_ep = []

    for r in reports:
        ep = r.get("excess_patch", {})
        ep_scores.append(ep.get("score", 0.0))
        hunk_stats["total"] += ep.get("total_hunks", 0)
        hunk_stats["required"] += ep.get("required", 0)
        hunk_stats["ancillary"] += ep.get("ancillary", 0)
        hunk_stats["unrelated"] += ep.get("unrelated", 0)
        if ep.get("score", 0) >= 0.5:
            high_ep.append({
                "instance_id": r["instance_id"],
                "ep_score": ep["score"],
                "hunks": f"{ep.get('required',0)}R/{ep.get('ancillary',0)}A/{ep.get('unrelated',0)}U",
                "severity": r["severity"],
            })

    return {
        "mean_ep_score": sum(ep_scores) / len(ep_scores) if ep_scores else 0,
        "hunk_stats": hunk_stats,
        "high_ep_cases": sorted(high_ep, key=lambda x: x["ep_score"], reverse=True)[:10],
    }


def analyze_excess_test_patterns(reports: list[dict]) -> dict:
    """Analyze excess test scoring patterns."""
    et_scores = []
    test_stats = {"total": 0, "aligned": 0, "tangential": 0, "unrelated": 0}
    assertion_stats = {"total": 0, "on_topic": 0, "off_topic": 0}
    modified_test_cases = []

    for r in reports:
        et = r.get("excess_test", {})
        et_scores.append(et.get("score", 0.0))
        test_stats["total"] += et.get("total_tests", 0)
        test_stats["aligned"] += et.get("aligned", 0)
        test_stats["tangential"] += et.get("tangential", 0)
        test_stats["unrelated"] += et.get("unrelated", 0)
        assertion_stats["total"] += et.get("total_assertions", 0)
        assertion_stats["on_topic"] += et.get("on_topic", 0)
        assertion_stats["off_topic"] += et.get("off_topic", 0)
        if et.get("has_modified_tests"):
            modified_test_cases.append({
                "instance_id": r["instance_id"],
                "et_score": et["score"],
                "severity": r["severity"],
            })

    return {
        "mean_et_score": sum(et_scores) / len(et_scores) if et_scores else 0,
        "test_stats": test_stats,
        "assertion_stats": assertion_stats,
        "modified_test_count": len(modified_test_cases),
        "modified_test_cases": modified_test_cases[:10],
    }


def analyze_vague_spec(reports: list[dict]) -> dict:
    """Analyze vague spec / ambiguity scoring."""
    vs_scores = []
    ambiguity_scores = []
    high_ambiguity = []

    for r in reports:
        vs = r.get("vague_spec", {})
        vs_scores.append(vs.get("score", 0.0))
        amb = r.get("intent", {}).get("ambiguity_score", 0.0)
        ambiguity_scores.append(amb)
        if amb >= 0.6:
            high_ambiguity.append({
                "instance_id": r["instance_id"],
                "ambiguity": amb,
                "vs_score": vs.get("score", 0),
                "severity": r["severity"],
            })

    return {
        "mean_vs_score": sum(vs_scores) / len(vs_scores) if vs_scores else 0,
        "mean_ambiguity": sum(ambiguity_scores) / len(ambiguity_scores) if ambiguity_scores else 0,
        "high_ambiguity_cases": sorted(high_ambiguity, key=lambda x: x["ambiguity"], reverse=True)[:10],
    }


def compare_v2_v3(v3_reports: list[dict], v2_dir: Path) -> dict:
    """Compare v3 vs v2 classifications where both exist."""
    if not v2_dir.exists():
        return {"available": False}

    v2_reports = load_reports(v2_dir)
    v2_map = {r["instance_id"]: r for r in v2_reports}

    agreements = 0
    disagreements = []
    v3_upgraded = []  # was CLEAN in v2, now contaminated in v3
    v3_downgraded = []  # was contaminated in v2, now CLEAN in v3

    for v3r in v3_reports:
        iid = v3r["instance_id"]
        if iid not in v2_map:
            continue
        v2r = v2_map[iid]
        v2_sev = v2r.get("severity", "UNKNOWN")
        v3_sev = v3r["severity"]
        if v2_sev == v3_sev:
            agreements += 1
        else:
            entry = {
                "instance_id": iid,
                "v2_severity": v2_sev,
                "v3_severity": v3_sev,
                "v3_labels": extract_labels(v3r),
                "v3_score": v3r["combined_score"],
            }
            disagreements.append(entry)
            if v2_sev == "CLEAN" and v3_sev != "CLEAN":
                v3_upgraded.append(entry)
            elif v2_sev != "CLEAN" and v3_sev == "CLEAN":
                v3_downgraded.append(entry)

    overlap = agreements + len(disagreements)
    return {
        "available": True,
        "overlap_count": overlap,
        "agreement_count": agreements,
        "agreement_rate": agreements / overlap if overlap else 0,
        "disagreements_count": len(disagreements),
        "v3_upgraded_count": len(v3_upgraded),
        "v3_downgraded_count": len(v3_downgraded),
        "top_disagreements": disagreements[:15],
        "top_upgraded": v3_upgraded[:10],
        "top_downgraded": v3_downgraded[:10],
    }


def build_triage_csv(reports: list[dict], output_path: Path):
    """Build reviewer-friendly triage CSV.

    Columns designed for human reviewers doing manual assessment:
    - instance_id, severity, combined_score
    - primary_label (most impactful label)
    - all_labels (comma-separated)
    - plain_english (human-readable explanation of what's wrong)
    - triage_priority (1=review first, 2=review second, 3=low priority)
    - core_requirement (what the task asks for)
    - ep_score, et_score, vs_score (sub-scores)
    - patch_hunks (R/A/U breakdown)
    - test_breakdown (aligned/tangential/unrelated)
    - evidence_summary (key evidence snippets)
    """
    rows = []
    for r in reports:
        labels = extract_labels(r)
        contam_labels = [l for l in labels if l != "clean"]

        # Primary label = first contamination label (no weights in v4)
        if contam_labels:
            primary = contam_labels[0]
        else:
            primary = labels[0] if labels else "clean"

        # Plain english: combine explanations for all labels
        explanations = []
        for l in contam_labels:
            explanations.append(f"[{l}] {LABEL_EXPLANATIONS.get(l, 'Unknown label')}")
        plain_english = " | ".join(explanations) if explanations else "Clean task -- no issues found."

        # Triage priority
        sev = r["severity"]
        if sev == "SEVERE":
            priority = 1
        elif sev == "MODERATE":
            priority = 2
        elif sev == "MINOR":
            priority = 3
        else:
            priority = 4

        # Sub-scores
        ep = r.get("excess_patch", {})
        et = r.get("excess_test", {})
        vs = r.get("vague_spec", {})

        # Evidence summary (first evidence item from each label)
        evidence_bits = []
        for la in r.get("task_labels", []):
            if la["label"] in contam_labels and la.get("evidence"):
                evidence_bits.append(f'[{la["label"]}] {la["evidence"][0][:200]}')

        rows.append({
            "instance_id": r["instance_id"],
            "severity": sev,
            "triage_priority": priority,
            "combined_score": round(r["combined_score"], 4),
            "primary_label": primary,
            "all_labels": ", ".join(labels),
            "label_count": len(labels),
            "plain_english": plain_english,
            "core_requirement": r.get("intent", {}).get("core_requirement", "")[:300],
            "ep_score": round(ep.get("score", 0), 4),
            "et_score": round(et.get("score", 0), 4),
            "vs_score": round(vs.get("score", 0), 4),
            "patch_hunks": f'{ep.get("required",0)}R/{ep.get("ancillary",0)}A/{ep.get("unrelated",0)}U',
            "test_breakdown": f'{et.get("aligned",0)}A/{et.get("tangential",0)}T/{et.get("unrelated",0)}U',
            "has_modified_tests": et.get("has_modified_tests", False),
            "ambiguity_score": r.get("intent", {}).get("ambiguity_score", 0),
            "evidence_summary": " || ".join(evidence_bits[:3]) if evidence_bits else "",
        })

    # Sort by triage priority then score descending
    rows.sort(key=lambda x: (x["triage_priority"], -x["combined_score"]))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def per_project_breakdown(reports: list[dict]) -> dict:
    """Break down contamination by source project (django, sympy, etc.)."""
    project_stats = defaultdict(lambda: {"total": 0, "severity": Counter(), "labels": Counter()})

    for r in reports:
        project = r["instance_id"].split("__")[0]
        project_stats[project]["total"] += 1
        project_stats[project]["severity"][r["severity"]] += 1
        for la in extract_labels(r):
            if la != "clean":
                project_stats[project]["labels"][la] += 1

    result = {}
    for proj, stats in sorted(project_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        contam_count = stats["total"] - stats["severity"].get("CLEAN", 0)
        result[proj] = {
            "total": stats["total"],
            "contamination_rate": round(contam_count / stats["total"] * 100, 1),
            "severity": dict(stats["severity"]),
            "top_labels": dict(stats["labels"].most_common(5)),
        }
    return result


def label_confidence_analysis(reports: list[dict]) -> dict:
    """Analyze confidence distributions per label."""
    label_conf = defaultdict(list)
    for r in reports:
        for la in r.get("task_labels", []):
            label_conf[la["label"]].append(la.get("confidence", 0))

    result = {}
    for label, confs in label_conf.items():
        confs_sorted = sorted(confs)
        n = len(confs)
        result[label] = {
            "count": n,
            "mean_confidence": round(sum(confs) / n, 3) if n else 0,
            "min_confidence": round(min(confs), 3) if n else 0,
            "max_confidence": round(max(confs), 3) if n else 0,
            "median_confidence": round(confs_sorted[n // 2], 3) if n else 0,
            "low_confidence_count": sum(1 for c in confs if c < 0.5),
        }
    return result


def main():
    print("=" * 70)
    print("V3 FORENSIC ANALYSIS — 500 SWE-bench Verified Tasks")
    print("=" * 70)

    # Load reports
    reports = load_reports(REPORTS_DIR)
    print(f"\nLoaded {len(reports)} reports")

    # 1. Distributions
    print("\n[1/8] Analyzing distributions...")
    dist = analyze_distributions(reports)
    print(f"  Severity: {dist['severity_counts']}")
    print(f"  Score stats: {dist['score_stats']}")

    # 2. Co-occurrence
    print("\n[2/8] Analyzing label co-occurrence...")
    cooc = analyze_cooccurrence(reports)
    print(f"  Top 5 pairs: {dict(list(cooc['pair_counts'].items())[:5])}")

    # 3. Case studies
    print("\n[3/8] Selecting case studies...")
    cases = find_case_studies(reports)
    print(f"  Labels with cases: {len([k for k in cases if not k.startswith('_')])}")
    print(f"  Most-labeled task: {cases['_most_labels'][0]['instance_id']} ({cases['_most_labels'][0]['label_count']} labels)")

    # 4. EP patterns
    print("\n[4/8] Analyzing excess patch patterns...")
    ep = analyze_excess_patch_patterns(reports)
    print(f"  Mean EP: {ep['mean_ep_score']:.4f}")
    print(f"  Hunk stats: {ep['hunk_stats']}")

    # 5. ET patterns
    print("\n[5/8] Analyzing excess test patterns...")
    et = analyze_excess_test_patterns(reports)
    print(f"  Mean ET: {et['mean_et_score']:.4f}")
    print(f"  Test stats: {et['test_stats']}")
    print(f"  Assertion stats: {et['assertion_stats']}")
    print(f"  Modified test cases: {et['modified_test_count']}")

    # 6. Vague spec
    print("\n[6/8] Analyzing vague spec/ambiguity...")
    vs = analyze_vague_spec(reports)
    print(f"  Mean VS: {vs['mean_vs_score']:.4f}, Mean ambiguity: {vs['mean_ambiguity']:.4f}")

    # 7. V2 comparison
    print("\n[7/8] Comparing v3 vs v2...")
    v2_comp = compare_v2_v3(reports, V2_REPORTS_DIR)
    if v2_comp["available"]:
        print(f"  Overlap: {v2_comp['overlap_count']} tasks")
        print(f"  Agreement: {v2_comp['agreement_count']} ({v2_comp['agreement_rate']:.1%})")
        print(f"  Upgraded (CLEAN→contaminated): {v2_comp['v3_upgraded_count']}")
        print(f"  Downgraded (contaminated→CLEAN): {v2_comp['v3_downgraded_count']}")
    else:
        print("  No v2 results available for comparison")

    # 8. Per-project breakdown
    print("\n[8/8] Per-project breakdown...")
    proj = per_project_breakdown(reports)
    for p, s in list(proj.items())[:5]:
        print(f"  {p}: {s['total']} tasks, {s['contamination_rate']}% contaminated")

    # Confidence analysis
    conf_analysis = label_confidence_analysis(reports)

    # Build triage CSV
    print("\n--- Building triage CSV ---")
    csv_path = OUTPUT_DIR / "triage_review.csv"
    n_rows = build_triage_csv(reports, csv_path)
    print(f"  Wrote {n_rows} rows to {csv_path}")

    # Save full analysis as JSON
    full_analysis = {
        "distributions": dist,
        "cooccurrence": cooc,
        "case_studies": cases,
        "excess_patch": ep,
        "excess_test": et,
        "vague_spec": vs,
        "v2_comparison": v2_comp,
        "per_project": proj,
        "confidence_analysis": conf_analysis,
    }

    analysis_path = ANALYSIS_DIR / "forensic_results.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(full_analysis, f, indent=2, default=str)
    print(f"\nFull analysis saved to {analysis_path}")

    return full_analysis


if __name__ == "__main__":
    analysis = main()
