"""Trajectory classifier for detecting benchmark leakage.

Primary approach: LLM analysis of the full trajectory to understand
agent behavior and identify leakage patterns.

Heuristic signals (patch similarity, pip installs, test references)
are computed first and fed to the LLM as supporting evidence, but
the LLM makes the final classification decision.

Tier 1: Heuristic signal extraction (fast, no LLM)
  - Gold patch similarity
  - pip install commands
  - F2P test name/value references

Tier 2: LLM analysis (primary classifier)
  - Feeds problem statement + trajectory + heuristic signals to LLM
  - LLM classifies with reasoning and confidence

Tier 3: Cross-agent comparison
  - If all agents produce identical patches, likely leakage
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from typing import Any

from bench_cleanser.trajectory.models import (
    ActionType,
    LeakagePattern,
    TrajectoryAction,
    TrajectoryAnalysis,
    TrajectoryRecord,
)

from bench_cleanser.models import AgentTrajectoryLabel

logger = logging.getLogger(__name__)

# Thresholds
GOLD_PATCH_SIMILARITY_THRESHOLD = 0.90
HIGH_SIMILARITY_THRESHOLD = 0.80
PIP_INSTALL_RE = re.compile(
    r"pip\s+install\s+(?:--upgrade\s+)?([a-zA-Z0-9_.-]+)",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────
# Tier 1: Heuristic signal extraction
# ──────────────────────────────────────────────────────────────────────


def compute_patch_similarity(patch_a: str, patch_b: str) -> float:
    """Compute similarity ratio between two patches using difflib.

    Returns a value between 0.0 (completely different) and 1.0 (identical).
    """
    if not patch_a or not patch_b:
        return 0.0

    # Normalize whitespace for fairer comparison
    lines_a = patch_a.strip().splitlines()
    lines_b = patch_b.strip().splitlines()

    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    return matcher.ratio()


def detect_pip_installs(trajectory: TrajectoryRecord) -> list[str]:
    """Find pip install commands in the trajectory."""
    installs = []
    for action in trajectory.actions:
        if action.action_type in (ActionType.TERMINAL, ActionType.OTHER):
            for match in PIP_INSTALL_RE.finditer(action.content):
                installs.append(match.group(0))
    return installs


def detect_test_references(
    trajectory: TrajectoryRecord,
    f2p_test_names: list[str],
) -> list[str]:
    """Check if trajectory actions reference F2P test names or values."""
    references = []
    for action in trajectory.actions:
        content = action.content
        for test_name in f2p_test_names:
            # Check for test function name (strip module path)
            short_name = test_name.rsplit("::", 1)[-1] if "::" in test_name else test_name
            if short_name in content:
                ref = f"References test '{short_name}' in {action.action_type.value} action"
                if ref not in references:
                    references.append(ref)
    return references


def extract_heuristic_signals(
    trajectory: TrajectoryRecord,
    gold_patch: str,
    f2p_test_names: list[str],
) -> dict[str, Any]:
    """Extract all heuristic signals for a trajectory.

    Returns a dict of signals to be fed to the LLM for analysis.
    """
    similarity = compute_patch_similarity(trajectory.final_patch, gold_patch)
    pip_installs = detect_pip_installs(trajectory)
    test_refs = detect_test_references(trajectory, f2p_test_names)

    return {
        "gold_patch_similarity": similarity,
        "pip_install_commands": pip_installs,
        "test_references": test_refs,
        "has_high_similarity": similarity >= HIGH_SIMILARITY_THRESHOLD,
        "has_gold_patch_match": similarity >= GOLD_PATCH_SIMILARITY_THRESHOLD,
        "has_pip_installs": len(pip_installs) > 0,
        "has_test_refs": len(test_refs) > 0,
    }


def classify_heuristic_only(
    trajectory: TrajectoryRecord,
    gold_patch: str,
    f2p_test_names: list[str],
) -> TrajectoryAnalysis:
    """Fallback: heuristic-only classification when LLM is unavailable.

    Used as a fallback when LLM analysis fails or is disabled.
    """
    signals = extract_heuristic_signals(trajectory, gold_patch, f2p_test_names)
    evidence = []
    similarity = signals["gold_patch_similarity"]
    pip_installs = signals["pip_install_commands"]
    test_refs = signals["test_references"]

    if signals["has_gold_patch_match"]:
        evidence.append(
            f"Final patch is {similarity:.1%} similar to gold patch "
            f"(threshold: {GOLD_PATCH_SIMILARITY_THRESHOLD:.0%})"
        )
        return TrajectoryAnalysis(
            instance_id=trajectory.instance_id,
            agent_name=trajectory.agent_name,
            leakage_pattern=LeakagePattern.GOLD_PATCH_LEAK,
            confidence=min(similarity, 0.95),
            evidence=evidence,
            gold_patch_similarity=similarity,
            pip_install_commands=pip_installs,
            test_references=test_refs,
        )

    if pip_installs:
        evidence.append(
            f"Found {len(pip_installs)} pip install command(s): "
            + "; ".join(pip_installs)
        )
        return TrajectoryAnalysis(
            instance_id=trajectory.instance_id,
            agent_name=trajectory.agent_name,
            leakage_pattern=LeakagePattern.PACKAGE_LEAK,
            confidence=0.7,
            evidence=evidence,
            gold_patch_similarity=similarity,
            pip_install_commands=pip_installs,
            test_references=test_refs,
        )

    if test_refs:
        evidence.extend(test_refs)
        return TrajectoryAnalysis(
            instance_id=trajectory.instance_id,
            agent_name=trajectory.agent_name,
            leakage_pattern=LeakagePattern.TEST_AWARE,
            confidence=0.6,
            evidence=evidence,
            gold_patch_similarity=similarity,
            pip_install_commands=pip_installs,
            test_references=test_refs,
        )

    if signals["has_high_similarity"]:
        evidence.append(
            f"Final patch has high similarity to gold patch ({similarity:.1%}) "
            f"but below leak threshold"
        )
        return TrajectoryAnalysis(
            instance_id=trajectory.instance_id,
            agent_name=trajectory.agent_name,
            leakage_pattern=LeakagePattern.PARTIAL_MATCH,
            confidence=0.5,
            evidence=evidence,
            gold_patch_similarity=similarity,
            pip_install_commands=pip_installs,
            test_references=test_refs,
        )

    return TrajectoryAnalysis(
        instance_id=trajectory.instance_id,
        agent_name=trajectory.agent_name,
        leakage_pattern=LeakagePattern.GENUINE_SOLUTION,
        confidence=0.5,
        evidence=["No deterministic leakage signals detected"],
        gold_patch_similarity=similarity,
        pip_install_commands=pip_installs,
        test_references=test_refs,
    )


# ──────────────────────────────────────────────────────────────────────
# Tier 2: LLM analysis (PRIMARY classifier)
# ──────────────────────────────────────────────────────────────────────

TRAJECTORY_ANALYSIS_SYSTEM_PROMPT = """\
You are a benchmark integrity analyst specializing in detecting \
benchmark leakage in AI agent evaluations.

You analyze agent trajectories on software engineering tasks to determine \
whether the agent derived its solution through genuine problem-solving \
or exhibited patterns indicating access to the correct answer (benchmark \
leakage).

Be thorough and precise. Look for subtle patterns such as:
- Agent jumping directly to the correct file/function without exploration
- Installing packages that contain the fix (PyPI leakage)
- Referencing test names or expected values not in the problem statement
- Producing patches suspiciously similar to the gold patch
- Skipping debugging/reasoning steps that would be expected
- Copying code from installed packages back into the source tree
- Applying a memorized template pattern without genuine task-specific reasoning

Consider the element of luck: agents may pass certain tests by coincidence.
A genuinely strong agent may solve a task correctly through legitimate
reasoning, even if the task is contaminated. Distinguish between skill
and leakage.

Classify using the v3 Axis 2 trajectory taxonomy:

PASSED LABELS (agent resolved the task):
- agent_passed_genuine: Legitimate problem-solving with progressive exploration
- agent_passed_leak: Patch matches gold too closely (similarity >= 0.90); \
jumped to correct file without search
- agent_passed_package_leak: Agent pip-installed newer version and copied \
fix from site-packages
- agent_passed_test_aware: Agent referenced F2P test names/values before \
discovering through exploration
- agent_passed_trained_hack: Applied memorized template without genuine \
problem-specific reasoning

FAILED LABELS (agent did NOT resolve the task):
- agent_failed_completed_intent: Agent's patch addresses the real problem \
but fails F2P tests due to task contamination (approach mismatch, etc.)
- agent_failed_no_intent: Agent didn't solve the problem at all; failure \
reflects skill gap, not unfairness

UNKNOWN:
- agent_unknown: Insufficient trajectory data to classify"""


def _build_trajectory_analysis_prompt(
    trajectory: TrajectoryRecord,
    gold_patch: str,
    problem_statement: str,
    f2p_test_names: list[str],
    heuristic_signals: dict[str, Any],
    contamination_context: str = "",
) -> str:
    """Build the prompt for LLM trajectory analysis."""
    # Summarize trajectory (use full content, large context window)
    action_summary = _summarize_actions(trajectory.actions, max_chars=30000)

    # Heuristic signals section
    signals_text = []
    if heuristic_signals["has_gold_patch_match"]:
        signals_text.append(
            f"- CRITICAL: Final patch is {heuristic_signals['gold_patch_similarity']:.1%} "
            f"similar to the gold patch (above {GOLD_PATCH_SIMILARITY_THRESHOLD:.0%} threshold)"
        )
    elif heuristic_signals["has_high_similarity"]:
        signals_text.append(
            f"- WARNING: Final patch is {heuristic_signals['gold_patch_similarity']:.1%} "
            f"similar to the gold patch"
        )
    if heuristic_signals["pip_install_commands"]:
        signals_text.append(
            f"- PIP INSTALLS detected: {'; '.join(heuristic_signals['pip_install_commands'])}"
        )
    if heuristic_signals["test_references"]:
        signals_text.append(
            f"- TEST REFERENCES detected: {'; '.join(heuristic_signals['test_references'])}"
        )
    if not signals_text:
        signals_text.append("- No strong heuristic leakage signals detected")

    signals_section = "\n".join(signals_text)

    contamination_section = ""
    if contamination_context:
        contamination_section = f"""
CONTAMINATION CONTEXT (from bench-cleanser pipeline):
{contamination_context}
"""

    return f"""Analyze this AI agent's trajectory on a software engineering task.

PROBLEM STATEMENT:
{problem_statement[:5000]}

GOLD PATCH (the correct solution — the agent should NOT have access to this):
{gold_patch[:5000]}

FAIL-TO-PASS TEST NAMES (used for evaluation):
{json.dumps(f2p_test_names[:20])}
{contamination_section}
HEURISTIC SIGNALS (pre-computed):
{signals_section}

AGENT: {trajectory.agent_name}
RESOLVED: {trajectory.resolved}

AGENT'S TRAJECTORY:
{action_summary}

AGENT'S FINAL PATCH:
{trajectory.final_patch[:5000]}

---

ANALYSIS INSTRUCTIONS:

1. Trace the agent's reasoning process step by step. Did it:
   a. Read and understand the problem statement?
   b. Explore the codebase to find relevant files?
   c. Formulate a hypothesis about the bug/feature?
   d. Implement a fix based on its understanding?
   e. Test and iterate on its solution?

2. Check for leakage indicators:
   a. Did the agent jump directly to the solution without exploration?
   b. Did it install any packages that might contain the fix?
   c. Did it reference test names or expected values not in the problem?
   d. Is the final patch suspiciously similar to the gold patch?
   e. Did it copy code from an installed package back to the source?
   f. Did its approach reflect genuine understanding or rote copying?

3. Consider the causal chain: What led the agent to its approach?
   Was there an infrastructure failure that forced workarounds?

4. Classify the trajectory.

Respond in JSON:
{{
    "pattern": "GENUINE_SOLUTION | GOLD_PATCH_LEAK | PACKAGE_LEAK | TEST_AWARE | PARTIAL_MATCH",
    "trajectory_label": "agent_passed_genuine | agent_passed_leak | agent_passed_package_leak | agent_passed_test_aware | agent_passed_trained_hack | agent_failed_completed_intent | agent_failed_no_intent | agent_unknown",
    "confidence": 0.0 to 1.0,
    "reasoning": "Detailed paragraph explaining the classification",
    "causal_chain": "Brief description of what led the agent to its approach",
    "key_evidence": ["list", "of", "key", "evidence", "points"],
    "agent_behavior_summary": "Brief characterization of agent behavior"
}}"""


async def classify_with_llm(
    trajectory: TrajectoryRecord,
    gold_patch: str,
    problem_statement: str,
    f2p_test_names: list[str],
    llm: Any,
    heuristic_signals: dict[str, Any] | None = None,
    contamination_context: str = "",
) -> TrajectoryAnalysis:
    """Tier 2: LLM-based trajectory classification (primary approach).

    Sends the full trajectory context to the LLM for analysis. The LLM
    receives heuristic signals as supporting evidence but makes the
    final classification decision.
    """
    if heuristic_signals is None:
        heuristic_signals = extract_heuristic_signals(
            trajectory, gold_patch, f2p_test_names
        )

    prompt = _build_trajectory_analysis_prompt(
        trajectory, gold_patch, problem_statement, f2p_test_names,
        heuristic_signals, contamination_context,
    )

    try:
        response = await llm.query(
            system=TRAJECTORY_ANALYSIS_SYSTEM_PROMPT,
            user=prompt,
            cache_key=f"trajectory_v2_{trajectory.instance_id}_{trajectory.agent_name}",
        )

        result = _parse_llm_response(response)
        pattern = LeakagePattern(result.get("pattern", "UNKNOWN"))
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "")
        causal_chain = result.get("causal_chain", "")
        key_evidence = result.get("key_evidence", [])

        # Extract v3 trajectory label (if provided by LLM)
        trajectory_label = None
        tl_str = result.get("trajectory_label", "")
        if tl_str:
            try:
                trajectory_label = AgentTrajectoryLabel(tl_str)
            except ValueError:
                pass

        evidence = []
        if reasoning:
            evidence.append(f"LLM analysis: {reasoning}")
        if causal_chain:
            evidence.append(f"Causal chain: {causal_chain}")
        evidence.extend(key_evidence)

        return TrajectoryAnalysis(
            instance_id=trajectory.instance_id,
            agent_name=trajectory.agent_name,
            leakage_pattern=pattern,
            confidence=confidence,
            evidence=evidence,
            gold_patch_similarity=heuristic_signals["gold_patch_similarity"],
            pip_install_commands=heuristic_signals["pip_install_commands"],
            test_references=heuristic_signals["test_references"],
            llm_reasoning=reasoning,
            causal_chain=causal_chain,
            agent_behavior_summary=result.get("agent_behavior_summary", ""),
            trajectory_label=trajectory_label,
        )
    except Exception as exc:
        logger.warning(
            "LLM trajectory analysis failed for %s/%s: %s — falling back to heuristics",
            trajectory.instance_id, trajectory.agent_name, exc,
        )
        return classify_heuristic_only(
            trajectory, gold_patch, f2p_test_names,
        )


def _parse_llm_response(response: str) -> dict[str, Any]:
    """Parse LLM JSON response with fallback for markdown fences."""
    text = response.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown fences
    import re
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding JSON object
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse LLM response as JSON")
    return {"pattern": "UNKNOWN", "confidence": 0.3, "reasoning": text[:500]}


# ──────────────────────────────────────────────────────────────────────
# Tier 3: Cross-agent comparison
# ──────────────────────────────────────────────────────────────────────


def classify_cross_agent(
    analyses: list[TrajectoryAnalysis],
    trajectories: list[TrajectoryRecord],
) -> list[TrajectoryAnalysis]:
    """Tier 3: Cross-agent comparison.

    If multiple agents produce nearly identical patches, upgrade
    confidence in GOLD_PATCH_LEAK classification.
    """
    if len(analyses) < 2:
        return analyses

    # Collect final patches
    patches = [t.final_patch for t in trajectories if t.final_patch]
    if len(patches) < 2:
        return analyses

    # Check pairwise similarity
    all_similar = True
    for i in range(len(patches)):
        for j in range(i + 1, len(patches)):
            sim = compute_patch_similarity(patches[i], patches[j])
            if sim < HIGH_SIMILARITY_THRESHOLD:
                all_similar = False
                break
        if not all_similar:
            break

    if all_similar:
        for analysis in analyses:
            if analysis.leakage_pattern in (
                LeakagePattern.GENUINE_SOLUTION,
                LeakagePattern.PARTIAL_MATCH,
            ):
                analysis.evidence.append(
                    "Cross-agent: all agents produced highly similar patches, "
                    "suggesting gold patch leakage rather than independent derivation"
                )
                analysis.leakage_pattern = LeakagePattern.GOLD_PATCH_LEAK
                analysis.confidence = max(analysis.confidence, 0.8)

    return analyses


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _summarize_actions(
    actions: list[TrajectoryAction], max_chars: int = 30000
) -> str:
    """Summarize trajectory actions, using large context window."""
    parts = []
    total = 0
    for i, action in enumerate(actions):
        # Use generous per-action limit for LLM analysis
        content_limit = min(len(action.content), 2000)
        line = f"[Step {i}] {action.action_type.value}: {action.content[:content_limit]}"
        if action.file_path:
            line += f" (file: {action.file_path})"
        if total + len(line) > max_chars:
            parts.append(f"... ({len(actions) - i} more actions truncated)")
            break
        parts.append(line)
        total += len(line)
    return "\n".join(parts)
