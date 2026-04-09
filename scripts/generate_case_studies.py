"""Generate 25 detailed case study markdown files from SWE-bench Pro SEVERE reports.

Each case study includes:
- Full problem statement from SWE-bench Pro
- Pipeline intent extraction and behavioral contract
- Detailed patch analysis with hunk-by-hunk verdicts
- Test assessment with F2P test alignment analysis
- Evidence-backed contamination labels with reasoning
- False positive evaluation and confidence calibration
- Recommendations and severity justification
"""

import json
import os
import glob
import textwrap
from datasets import load_dataset


REPORTS_DIR = "output_pro_v6/reports"
OUTPUT_DIR = "case_studies/pro_severe"
NUM_CASES = 25


def load_swebench_pro_lookup():
    """Load SWE-bench Pro dataset into a lookup dict by instance_id."""
    print("Loading SWE-bench Pro dataset from HuggingFace...")
    ds = load_dataset("ScaleAI/SWE-bench_Pro", split="test")
    lookup = {}
    for row in ds:
        lookup[row["instance_id"]] = dict(row)
    print(f"  Loaded {len(lookup)} tasks")
    return lookup


def load_reports():
    """Load all reports and return sorted SEVERE cases."""
    severe = []
    for f in glob.glob(os.path.join(REPORTS_DIR, "*.json")):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("severity") == "SEVERE":
            labels = data.get("task_labels", [])
            confs = [l["confidence"] for l in labels]
            max_conf = max(confs) if confs else 0
            # Also consider diversity of labels
            num_labels = len(labels)
            # Score: weighted by confidence and label count
            score = max_conf * 0.7 + min(num_labels / 5, 1.0) * 0.3
            severe.append((score, max_conf, num_labels, data, f))
    severe.sort(key=lambda x: -x[0])
    return severe


def find_original_instance_id(report_id, lookup):
    """Map report instance_id back to the original SWE-bench Pro instance_id."""
    # Report IDs have format: instance_<repo>_<repo>-<commit>-v<version>
    # Original IDs have format: <repo>/<repo>__<commit> or similar
    # Try stripping "instance_" prefix and matching
    stripped = report_id
    if stripped.startswith("instance_"):
        stripped = stripped[len("instance_"):]

    # Direct match attempt
    if stripped in lookup:
        return stripped

    # Try matching by commit hash
    # Extract commit-like portion
    parts = stripped.split("-")
    for key in lookup:
        for part in parts:
            if len(part) >= 10 and part in key:
                return key

    # Fuzzy: match by repo name and commit prefix
    for key in lookup:
        # Normalize both
        key_norm = key.replace("/", "__").replace("-", "")
        stripped_norm = stripped.replace("-", "")
        if key_norm[:30] == stripped_norm[:30]:
            return key

    return None


def wrap_text(text, width=100):
    """Wrap text for markdown readability."""
    if not text:
        return ""
    paragraphs = text.split("\n\n")
    wrapped = []
    for p in paragraphs:
        lines = p.strip().splitlines()
        for line in lines:
            if line.strip().startswith(("-", "*", "#", ">", "|", "```")):
                wrapped.append(line)
            else:
                wrapped.append(textwrap.fill(line, width=width))
        wrapped.append("")
    return "\n".join(wrapped)


def format_hunk_table(hunks):
    """Format patch hunks into a detailed markdown table."""
    if not hunks:
        return "_No hunk analysis available._\n"

    lines = []
    lines.append("| # | File | Verdict | Conf. | Reason |")
    lines.append("|---|------|---------|-------|--------|")
    for i, h in enumerate(hunks):
        file = h.get("file", "?")
        verdict = h.get("verdict", "?")
        conf = h.get("confidence", 0)
        reason = h.get("reason", "")
        # Truncate reason for table, full below
        reason_short = reason[:120].replace("|", "/").replace("\n", " ")
        if len(reason) > 120:
            reason_short += "..."
        emoji = {"REQUIRED": "✅", "ANCILLARY": "🔧", "UNRELATED": "❌"}.get(verdict, "❓")
        lines.append(f"| {h.get('hunk_index', i)} | `{file}` | {emoji} {verdict} | {conf:.2f} | {reason_short} |")
    return "\n".join(lines) + "\n"


def format_test_details(tests):
    """Format test analysis into detailed markdown."""
    if not tests:
        return "_No F2P tests analyzed._\n"

    lines = []
    for t in tests:
        match = t.get("intent_match", "UNKNOWN")
        emoji = {"ALIGNED": "✅", "TANGENTIAL": "⚠️", "UNRELATED": "❌"}.get(match, "❓")
        lines.append(f"#### {emoji} `{t.get('test_id', 'unknown')}`\n")
        lines.append(f"- **Intent Match**: {match}")
        lines.append(f"- **Is Modified**: {t.get('is_modified', False)}")
        lines.append(f"- **Modification Aligned**: {t.get('modification_aligned', 'N/A')}")
        if t.get("assertions"):
            lines.append(f"- **Assertions** ({len(t['assertions'])}):")
            for a in t["assertions"][:10]:
                lines.append(f"  - `{a}`")
        else:
            lines.append("- **Assertions**: None detected")
        lines.append("")
    return "\n".join(lines) + "\n"


def format_label_analysis(labels):
    """Format contamination labels into detailed evidence sections."""
    if not labels:
        return "_No contamination labels assigned._\n"

    LABEL_DESCRIPTIONS = {
        "approach_lock": "Tests require a specific implementation approach that the problem statement does not determine",
        "wide_tests": "F2P tests verify behavior not described in the problem statement",
        "test_mutation": "Pre-existing tests are silently modified to assert undescribed behavior",
        "scope_creep": "Gold patch includes behavioral changes beyond what the problem scope requires",
        "unclear_spec": "Problem statement is too ambiguous to determine a single correct solution",
        "hidden_context": "Essential information exists only in hints_text, not the problem statement",
        "weak_coverage": "F2P tests do not fully cover the stated acceptance criteria",
        "clean": "No contamination detected",
    }

    lines = []
    for label_obj in labels:
        label = label_obj.get("label", "unknown")
        conf = label_obj.get("confidence", 0)
        evidence = label_obj.get("evidence", [])
        reasoning = label_obj.get("reasoning", "")
        desc = LABEL_DESCRIPTIONS.get(label, "Unknown label type")

        # Confidence assessment
        if conf >= 0.9:
            conf_text = "Very High"
            conf_emoji = "🔴"
        elif conf >= 0.7:
            conf_text = "High"
            conf_emoji = "🟠"
        elif conf >= 0.5:
            conf_text = "Moderate"
            conf_emoji = "🟡"
        else:
            conf_text = "Low"
            conf_emoji = "🟢"

        lines.append(f"### `{label.upper()}` — Confidence: {conf:.2f} ({conf_text}) {conf_emoji}\n")
        lines.append(f"> **Definition**: {desc}\n")
        lines.append(f"**Reasoning**: {reasoning}\n")

        if evidence:
            lines.append("**Evidence chain**:\n")
            for j, ev in enumerate(evidence, 1):
                lines.append(f"{j}. {ev}")
            lines.append("")

    return "\n".join(lines) + "\n"


def evaluate_false_positive_risk(report, original_data):
    """Assess FP risk for each label and provide critical evaluation."""
    labels = report.get("task_labels", [])
    intent = report.get("intent", {})
    excess_patch = report.get("excess_patch", {})
    excess_test = report.get("excess_test", {})

    lines = []

    for label_obj in labels:
        label = label_obj.get("label", "")
        conf = label_obj.get("confidence", 0)
        evidence = label_obj.get("evidence", [])
        reasoning = label_obj.get("reasoning", "")

        lines.append(f"### FP Assessment: `{label.upper()}` (conf={conf:.2f})\n")

        # Evaluate based on label type
        fp_risk = "LOW"
        fp_reasoning = ""

        if label == "approach_lock":
            # Check if the problem statement really is open-ended
            ambiguity = intent.get("ambiguity_score", 0)
            if ambiguity < 0.3:
                fp_risk = "MODERATE"
                fp_reasoning = (
                    f"The problem statement has low ambiguity (score={ambiguity:.1f}), "
                    f"which means the fix may be more constrained than the label implies. "
                    f"However, even well-specified problems can have multiple valid "
                    f"implementation approaches. The key question is whether the tests "
                    f"reject semantically correct alternatives."
                )
            else:
                fp_risk = "LOW"
                fp_reasoning = (
                    f"Ambiguity score is {ambiguity:.1f}, confirming the spec leaves room "
                    f"for multiple approaches. The approach_lock label is well-supported."
                )

        elif label == "wide_tests":
            n_tests = excess_test.get("total_tests", 0)
            tangential = excess_test.get("tangential", 0)
            unrelated = excess_test.get("unrelated", 0)
            if tangential + unrelated == 0 and n_tests > 0:
                fp_risk = "HIGH"
                fp_reasoning = (
                    f"All {n_tests} F2P tests were classified as ALIGNED, yet the label "
                    f"'wide_tests' was assigned. This may be a false positive — the LLM "
                    f"classifier and the test analyzer disagree. Needs manual review."
                )
            elif tangential + unrelated > 0:
                fp_risk = "LOW"
                fp_reasoning = (
                    f"{tangential} tangential + {unrelated} unrelated tests detected out of "
                    f"{n_tests} total. Concrete evidence supports the label."
                )
            else:
                fp_risk = "MODERATE"
                fp_reasoning = (
                    f"No detailed test analysis available (total_tests={n_tests}). "
                    f"Label relies on LLM reasoning alone without structural confirmation."
                )

        elif label == "scope_creep":
            total = excess_patch.get("total_hunks", 0)
            unrelated = excess_patch.get("unrelated", 0)
            if unrelated == 0:
                fp_risk = "HIGH"
                fp_reasoning = (
                    f"No UNRELATED hunks detected in patch analysis ({total} total hunks), "
                    f"but scope_creep was labeled. Possible FP — the patch may be larger "
                    f"than minimal but still within scope."
                )
            elif unrelated >= 2:
                fp_risk = "LOW"
                fp_reasoning = (
                    f"{unrelated} out of {total} hunks classified as UNRELATED. "
                    f"Strong structural evidence for excess patch changes."
                )
            else:
                fp_risk = "LOW-MODERATE"
                fp_reasoning = (
                    f"{unrelated} out of {total} hunks classified as UNRELATED. "
                    f"Evidence present but borderline — single unrelated hunk could be debatable."
                )

        elif label == "test_mutation":
            has_modified = excess_test.get("has_modified_tests", False)
            if not has_modified:
                fp_risk = "MODERATE"
                fp_reasoning = (
                    "No modified tests detected by structural analysis, but test_mutation "
                    "was flagged. The LLM may have identified implicit test modifications "
                    "not captured by diff parsing. Needs manual verification."
                )
            else:
                fp_risk = "LOW"
                fp_reasoning = (
                    "Modified pre-existing tests confirmed by structural analysis. "
                    "Test mutation is structurally supported."
                )

        elif label == "unclear_spec":
            ambiguity = intent.get("ambiguity_score", 0)
            if ambiguity >= 0.5:
                fp_risk = "LOW"
                fp_reasoning = f"High ambiguity score ({ambiguity:.1f}) confirms spec is genuinely unclear."
            else:
                fp_risk = "MODERATE"
                fp_reasoning = (
                    f"Ambiguity score is only {ambiguity:.1f}, suggesting the spec may be "
                    f"clearer than the label implies. Could be FP."
                )

        elif label == "weak_coverage":
            fp_risk = "LOW-MODERATE"
            fp_reasoning = (
                "Weak coverage labels indicate F2P tests don't fully cover stated criteria. "
                "This is often valid but can be subjective — depends on interpretation "
                "of what 'full coverage' means for the stated requirements."
            )

        else:
            fp_risk = "UNKNOWN"
            fp_reasoning = "No specific FP heuristic available for this label type."

        risk_emoji = {
            "LOW": "✅", "LOW-MODERATE": "🟡", "MODERATE": "⚠️", "HIGH": "🔴", "UNKNOWN": "❓"
        }.get(fp_risk, "❓")

        lines.append(f"**FP Risk**: {risk_emoji} **{fp_risk}**\n")
        lines.append(f"{fp_reasoning}\n")

    return "\n".join(lines) + "\n"


def generate_case_study(idx, report, original_data):
    """Generate a single comprehensive case study markdown file."""
    instance_id = report.get("instance_id", "unknown")
    severity = report.get("severity", "UNKNOWN")
    intent = report.get("intent", {})
    excess_patch = report.get("excess_patch", {})
    excess_test = report.get("excess_test", {})
    vague_spec = report.get("vague_spec", {})
    labels = report.get("task_labels", [])
    recommendations = report.get("recommendations", [])

    # Original data fields
    repo = original_data.get("repo", "unknown") if original_data else "unknown"
    problem_statement = original_data.get("problem_statement", "_Not available_") if original_data else "_Not available_"
    hints_text = original_data.get("hints_text", "") if original_data else ""
    patch = original_data.get("patch", "") if original_data else ""
    test_patch = original_data.get("test_patch", "") if original_data else ""
    base_commit = original_data.get("base_commit", "") if original_data else ""
    f2p_raw = original_data.get("fail_to_pass", original_data.get("FAIL_TO_PASS", "[]")) if original_data else "[]"
    p2p_raw = original_data.get("pass_to_pass", original_data.get("PASS_TO_PASS", "[]")) if original_data else "[]"
    repo_language = original_data.get("repo_language", "unknown") if original_data else "unknown"

    # Parse F2P/P2P
    if isinstance(f2p_raw, str):
        try:
            import ast as _ast
            f2p_list = _ast.literal_eval(f2p_raw)
        except:
            f2p_list = []
    else:
        f2p_list = f2p_raw if isinstance(f2p_raw, list) else []

    if isinstance(p2p_raw, str):
        try:
            import ast as _ast
            p2p_list = _ast.literal_eval(p2p_raw)
        except:
            p2p_list = []
    else:
        p2p_list = p2p_raw if isinstance(p2p_raw, list) else []

    # Label summary
    label_names = [l["label"].upper() for l in labels]
    label_summary = ", ".join(label_names) if label_names else "NONE"
    max_conf = max((l["confidence"] for l in labels), default=0)

    # Build the markdown
    md = []

    # ─── Header ───
    md.append(f"# Case Study {idx:02d}: {repo}")
    md.append(f"## Instance: `{instance_id}`\n")
    md.append(f"**Severity**: 🔴 **{severity}**  ")
    md.append(f"**Contamination Labels**: {label_summary}  ")
    md.append(f"**Max Confidence**: {max_conf:.2f}  ")
    md.append(f"**Language**: {repo_language}  ")
    md.append(f"**Base Commit**: `{base_commit[:12] if base_commit else 'N/A'}`  ")
    md.append(f"**F2P Tests**: {len(f2p_list)} | **P2P Tests**: {len(p2p_list)}\n")

    md.append("---\n")

    # ─── Section 1: Problem Statement (Full Context) ───
    md.append("## 1. Problem Statement (Original from SWE-bench Pro)\n")
    md.append("The following is the complete, unmodified problem statement as it appears in the SWE-bench Pro dataset.\n")
    md.append("<details><summary>Click to expand full problem statement</summary>\n")
    md.append(f"{problem_statement}\n")
    md.append("</details>\n")

    if hints_text and hints_text.strip():
        md.append("### Hints Text\n")
        md.append("<details><summary>Click to expand hints</summary>\n")
        md.append(f"{hints_text}\n")
        md.append("</details>\n")

    # ─── Section 2: Pipeline Intent Extraction ───
    md.append("## 2. Pipeline Intent Extraction\n")
    md.append("The pipeline extracts intent from the problem statement **without seeing the gold patch**. "
              "This blind extraction establishes the behavioral contract that the patch and tests are measured against.\n")

    md.append(f"### Core Requirement\n{intent.get('core_requirement', 'N/A')}\n")
    md.append(f"### Behavioral Contract\n{intent.get('behavioral_contract', 'N/A')}\n")

    criteria = intent.get("acceptance_criteria", [])
    if criteria:
        md.append("### Acceptance Criteria\n")
        for i, c in enumerate(criteria, 1):
            md.append(f"{i}. {c}")
        md.append("")

    md.append(f"### Out of Scope\n{intent.get('out_of_scope', 'N/A')}\n")
    md.append(f"### Ambiguity Score: **{intent.get('ambiguity_score', 'N/A')}** / 1.0\n")

    decomp = intent.get("decomposition", {})
    if decomp:
        md.append("### Bug Decomposition\n")
        md.append(f"- **Description**: {decomp.get('bug_description', 'N/A')}")
        md.append(f"- **Legitimacy**: {decomp.get('legitimacy', 'N/A')}")
        if decomp.get("mentioned_files"):
            md.append(f"- **Mentioned Files**: {', '.join(decomp['mentioned_files'])}")
        if decomp.get("mentioned_functions"):
            md.append(f"- **Mentioned Functions**: {', '.join(decomp['mentioned_functions'])}")
        md.append("")

    # ─── Section 3: Gold Patch Analysis ───
    md.append("## 3. Gold Patch Analysis\n")
    total_hunks = excess_patch.get("total_hunks", 0)
    required = excess_patch.get("required", 0)
    ancillary = excess_patch.get("ancillary", 0)
    unrelated = excess_patch.get("unrelated", 0)
    has_excess = excess_patch.get("has_excess", False)

    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Total Hunks | {total_hunks} |")
    md.append(f"| ✅ Required | {required} |")
    md.append(f"| 🔧 Ancillary | {ancillary} |")
    md.append(f"| ❌ Unrelated | {unrelated} |")
    md.append(f"| Has Excess | {'Yes 🔴' if has_excess else 'No ✅'} |")
    md.append("")

    if required + ancillary + unrelated > 0:
        req_pct = required / total_hunks * 100 if total_hunks else 0
        anc_pct = ancillary / total_hunks * 100 if total_hunks else 0
        unr_pct = unrelated / total_hunks * 100 if total_hunks else 0
        md.append(f"**Distribution**: {req_pct:.0f}% required, {anc_pct:.0f}% ancillary, {unr_pct:.0f}% unrelated\n")

    md.append("### Hunk-by-Hunk Verdict\n")
    md.append(format_hunk_table(excess_patch.get("hunks", [])))

    # Full hunk details for UNRELATED/interesting hunks
    unrelated_hunks = [h for h in excess_patch.get("hunks", []) if h.get("verdict") == "UNRELATED"]
    if unrelated_hunks:
        md.append("### Detailed Analysis of UNRELATED Hunks\n")
        md.append("These hunks are the primary evidence for excess patch contamination.\n")
        for h in unrelated_hunks:
            md.append(f"#### `{h.get('file', '?')}` (hunk {h.get('hunk_index', '?')})\n")
            md.append(f"**Confidence**: {h.get('confidence', 0):.2f}\n")
            md.append(f"**Full Reasoning**: {h.get('reason', 'N/A')}\n")

    # ─── Section 4: Test Assessment ───
    md.append("## 4. F2P Test Assessment\n")
    total_tests = excess_test.get("total_tests", 0)
    aligned = excess_test.get("aligned", 0)
    tangential = excess_test.get("tangential", 0)
    unrelated_tests = excess_test.get("unrelated", 0)
    total_assertions = excess_test.get("total_assertions", 0)
    on_topic = excess_test.get("on_topic", 0)
    off_topic = excess_test.get("off_topic", 0)
    has_modified = excess_test.get("has_modified_tests", False)
    has_excess_tests = excess_test.get("has_excess", False)

    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Total F2P Tests Analyzed | {total_tests} |")
    md.append(f"| ✅ Aligned | {aligned} |")
    md.append(f"| ⚠️ Tangential | {tangential} |")
    md.append(f"| ❌ Unrelated | {unrelated_tests} |")
    md.append(f"| Total Assertions | {total_assertions} |")
    md.append(f"| On-Topic Assertions | {on_topic} |")
    md.append(f"| Off-Topic Assertions | {off_topic} |")
    md.append(f"| Has Modified Tests | {'Yes' if has_modified else 'No'} |")
    md.append(f"| Has Excess | {'Yes 🔴' if has_excess_tests else 'No ✅'} |")
    md.append("")

    md.append("### F2P Test List (from SWE-bench Pro)\n")
    if f2p_list:
        for t in f2p_list:
            md.append(f"- `{t}`")
        md.append("")
    else:
        md.append("_No F2P tests listed._\n")

    md.append("### Individual Test Analysis\n")
    md.append(format_test_details(excess_test.get("tests", [])))

    # ─── Section 5: Specification Clarity ───
    md.append("## 5. Specification Clarity Assessment\n")
    vague_score = vague_spec.get("score", "N/A")
    vague_reasoning = vague_spec.get("reasoning", "N/A")
    if isinstance(vague_score, (int, float)):
        if vague_score >= 0.7:
            spec_verdict = "🔴 HIGHLY AMBIGUOUS"
        elif vague_score >= 0.4:
            spec_verdict = "🟡 MODERATELY AMBIGUOUS"
        else:
            spec_verdict = "✅ REASONABLY CLEAR"
        md.append(f"**Ambiguity Score**: {vague_score:.1f} / 1.0 — {spec_verdict}\n")
    else:
        md.append(f"**Ambiguity Score**: {vague_score}\n")
    md.append(f"**Analysis**: {vague_reasoning}\n")

    # ─── Section 6: Contamination Labels ───
    md.append("## 6. Contamination Labels — Detailed Evidence\n")
    md.append("Each label represents a specific type of benchmark contamination detected by the pipeline. "
              "Labels are assigned based on converging evidence from structural analysis, intent extraction, "
              "and LLM-based classification.\n")
    md.append(format_label_analysis(labels))

    # ─── Section 7: False Positive Evaluation ───
    md.append("## 7. False Positive Evaluation\n")
    md.append("This section critically evaluates each contamination label for potential false positives. "
              "Due diligence requires examining whether structural evidence supports the LLM's reasoning, "
              "whether the confidence is calibrated, and whether alternative interpretations exist.\n")
    md.append(evaluate_false_positive_risk(report, original_data))

    # ─── Section 8: Recommendations ───
    md.append("## 8. Pipeline Recommendations\n")
    if recommendations:
        for r in recommendations:
            md.append(f"- {r}")
        md.append("")
    else:
        md.append("_No specific recommendations generated._\n")

    # ─── Section 9: Gold Patch Diff ───
    md.append("## 9. Gold Patch (Reference Diff)\n")
    md.append("<details><summary>Click to expand full gold patch</summary>\n")
    md.append("```diff")
    if patch:
        # Truncate very long patches
        patch_lines = patch.splitlines()
        if len(patch_lines) > 500:
            md.append("\n".join(patch_lines[:500]))
            md.append(f"\n... [{len(patch_lines) - 500} more lines truncated]")
        else:
            md.append(patch)
    else:
        md.append("# Not available")
    md.append("```\n")
    md.append("</details>\n")

    # ─── Section 10: Test Patch Diff ───
    md.append("## 10. Test Patch (F2P Test Diff)\n")
    md.append("<details><summary>Click to expand full test patch</summary>\n")
    md.append("```diff")
    if test_patch:
        test_lines = test_patch.splitlines()
        if len(test_lines) > 500:
            md.append("\n".join(test_lines[:500]))
            md.append(f"\n... [{len(test_lines) - 500} more lines truncated]")
        else:
            md.append(test_patch)
    else:
        md.append("# Not available")
    md.append("```\n")
    md.append("</details>\n")

    # ─── Section 11: Overall Verdict ───
    md.append("## 11. Overall Verdict\n")

    # Count FP risks
    fp_low = sum(1 for l in labels if _get_fp_risk(l, report, original_data) in ("LOW",))
    fp_mod = sum(1 for l in labels if _get_fp_risk(l, report, original_data) in ("MODERATE", "LOW-MODERATE"))
    fp_high = sum(1 for l in labels if _get_fp_risk(l, report, original_data) in ("HIGH",))

    md.append(f"| Assessment | Result |")
    md.append(f"|------------|--------|")
    md.append(f"| Severity | 🔴 SEVERE |")
    md.append(f"| Labels Assigned | {len(labels)} |")
    md.append(f"| Low FP Risk Labels | {fp_low} |")
    md.append(f"| Moderate FP Risk Labels | {fp_mod} |")
    md.append(f"| High FP Risk Labels | {fp_high} |")
    md.append(f"| Max Label Confidence | {max_conf:.2f} |")
    md.append("")

    if fp_high == 0 and fp_low >= 2:
        md.append("**Conclusion**: This case presents **strong, multi-signal evidence** of benchmark contamination. "
                   "Multiple independent analysis stages (patch structure, test alignment, intent comparison) "
                   "converge on the same verdict. The SEVERE classification is well-supported.\n")
    elif fp_high > 0:
        md.append("**Conclusion**: This case has **mixed evidence**. While some contamination signals are strong, "
                   f"{fp_high} label(s) have elevated false positive risk. Manual review is recommended to "
                   "confirm the SEVERE classification.\n")
    else:
        md.append("**Conclusion**: This case shows **moderate-to-strong evidence** of contamination. "
                   "The overall signal supports the SEVERE classification, though some labels warrant "
                   "closer inspection.\n")

    md.append("---\n")
    md.append("*Generated by bench-cleanser v4 (gpt-5.4-20260305) — SWE-bench Pro Contamination Analysis*\n")

    return "\n".join(md)


def _get_fp_risk(label_obj, report, original_data):
    """Quick FP risk lookup (mirrors evaluate_false_positive_risk logic)."""
    label = label_obj.get("label", "")
    conf = label_obj.get("confidence", 0)
    intent = report.get("intent", {})
    excess_patch = report.get("excess_patch", {})
    excess_test = report.get("excess_test", {})

    if label == "scope_creep":
        unrelated = excess_patch.get("unrelated", 0)
        return "HIGH" if unrelated == 0 else "LOW"
    elif label == "wide_tests":
        tangential = excess_test.get("tangential", 0)
        unrelated_t = excess_test.get("unrelated", 0)
        total = excess_test.get("total_tests", 0)
        if tangential + unrelated_t == 0 and total > 0:
            return "HIGH"
        elif tangential + unrelated_t > 0:
            return "LOW"
        return "MODERATE"
    elif label == "approach_lock":
        ambiguity = intent.get("ambiguity_score", 0)
        return "MODERATE" if ambiguity < 0.3 else "LOW"
    elif label == "test_mutation":
        return "LOW" if excess_test.get("has_modified_tests") else "MODERATE"
    elif label == "unclear_spec":
        ambiguity = intent.get("ambiguity_score", 0)
        return "LOW" if ambiguity >= 0.5 else "MODERATE"
    return "LOW-MODERATE"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load original dataset for full context
    lookup = load_swebench_pro_lookup()

    # Load and rank SEVERE reports
    severe_cases = load_reports()
    print(f"Found {len(severe_cases)} SEVERE cases")
    print(f"Selecting top {NUM_CASES} for case studies\n")

    for idx, (score, max_conf, num_labels, report, filepath) in enumerate(severe_cases[:NUM_CASES], 1):
        instance_id = report["instance_id"]
        print(f"[{idx:02d}/{NUM_CASES}] Generating: {instance_id}")

        # Find the original SWE-bench Pro data
        original_id = find_original_instance_id(instance_id, lookup)
        original_data = lookup.get(original_id) if original_id else None
        if not original_data:
            print(f"  WARNING: Could not match to original dataset entry")

        # Generate case study
        md_content = generate_case_study(idx, report, original_data)

        # Write file
        safe_name = instance_id.replace("/", "_").replace("\\", "_")
        # Truncate filename if too long
        if len(safe_name) > 100:
            safe_name = safe_name[:100]
        output_path = os.path.join(OUTPUT_DIR, f"case_{idx:02d}_{safe_name}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"  -> {output_path}")

    print(f"\nDone! {NUM_CASES} case studies written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
