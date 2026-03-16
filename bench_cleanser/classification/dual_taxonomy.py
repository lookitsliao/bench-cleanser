"""v3 Dual Taxonomy classifier: Axis 1 (task labels) + Axis 2 (agent labels).

Axis 1 assigns zero or more TaskContaminationLabel to each task based on
pipeline signals (EP, ET, VS, intent, hints).  Axis 2 assigns a single
AgentTrajectoryLabel per agent-task pair based on trajectory analysis.

Both axes use a structured LLM call with the full taxonomy definitions
embedded in the system prompt.
"""

from __future__ import annotations

import json
import logging
from functools import reduce
from typing import Any

from bench_cleanser.models import (
    AgentLabelAssignment,
    AgentTrajectoryLabel,
    DualTaxonomyReport,
    ExcessPatchDetail,
    ExcessTestDetail,
    IntentStatement,
    PipelineConfig,
    Severity,
    TaskContaminationLabel,
    TaskLabelAssignment,
    TaskRecord,
    VagueSpecDetail,
    VerdictScore,
)

logger = logging.getLogger(__name__)


# ── Label definitions: weight, display name, definition, detection prompt ───


LABEL_DEFINITIONS: dict[str, dict[str, Any]] = {
    # ── Group A: Test Contamination ───────────────────────────────
    "mistest_overtest": {
        "weight": 0.7,
        "display": "Overtest — Tests Beyond Scope",
        "definition": (
            "F2P tests verify behavior or functionality beyond the problem "
            "scope.  The tests exercise code paths, features, or edge cases "
            "that the problem statement does not describe."
        ),
        "prompt": (
            "Examine each assertion in the F2P tests.  Does the problem "
            "statement require verifying this behavior?  If OFF_TOPIC "
            "assertion ratio >= 0.3 or any test is UNRELATED, flag this."
        ),
    },
    "mistest_undertest": {
        "weight": 0.2,
        "display": "Undertest — Insufficient Coverage",
        "definition": (
            "F2P tests do not fully cover stated acceptance criteria.  A "
            "partial or incorrect fix can pass.  Less severe because it "
            "makes the task easier rather than harder."
        ),
        "prompt": (
            "Compare acceptance_criteria against F2P test assertions.  Are "
            "there described behaviors that NO test verifies?"
        ),
    },
    "mistest_customtest": {
        "weight": 0.9,
        "display": "Custom Test — Implementation-Locked",
        "definition": (
            "Tests assert on implementation details so specific to the gold "
            "patch that other valid solutions would fail.  The tests lock in "
            "one approach rather than testing the behavioral contract."
        ),
        "prompt": (
            "Would a different but equally valid solution fail this test?  "
            "Does the test assert on private methods, exact values tied to "
            "one algorithm, or implementation structure rather than behavior?"
        ),
    },
    "mistest_sneaky_modification": {
        "weight": 0.8,
        "display": "Sneaky Test Modification",
        "definition": (
            "A pre-existing test is modified to assert on NEW behavior not "
            "in the problem statement.  The test already existed so it "
            "appears legitimate, but the PR author silently altered it."
        ),
        "prompt": (
            "Is the test MODIFIED (pre-existing)?  If so, do the changes "
            "add assertions or expected values for behavior NOT described in "
            "the problem statement?"
        ),
    },
    "mistest_deferred_requirement": {
        "weight": 0.9,
        "display": "Deferred Requirement Enforced",
        "definition": (
            "Tests require features the problem explicitly defers "
            "('I have yet to add X', 'future work', 'TODO').  An honest "
            "agent is told NOT to implement X, but tests fail without X."
        ),
        "prompt": (
            "Does the problem contain deferral language ('I have yet to', "
            "'will add later', 'future work')?  Do F2P tests exercise the "
            "deferred feature?"
        ),
    },
    # ── Group B: Patch Contamination ──────────────────────────────
    "mispatch_overpatch": {
        "weight": 0.5,
        "display": "Overpatch — Exceeds Scope",
        "definition": (
            "Gold patch includes code changes beyond problem scope: new "
            "features, unrelated refactoring, or functionality additions "
            "not described in the problem."
        ),
        "prompt": (
            "Are there UNRELATED hunks that introduce NEW behavior not "
            "described in the problem?  Ignore ANCILLARY infrastructure."
        ),
    },
    "mispatch_underpatch": {
        "weight": 0.2,
        "display": "Underpatch — Incomplete Fix",
        "definition": (
            "Gold patch does not fully address stated requirements.  Some "
            "acceptance criteria remain unfixed yet F2P tests still pass."
        ),
        "prompt": (
            "Does the gold patch address every requirement in the problem?  "
            "Are there acceptance criteria with no corresponding hunk?"
        ),
    },
    "mispatch_approach_mismatch": {
        "weight": 1.0,
        "display": "Approach Mismatch",
        "definition": (
            "Gold patch takes a fundamentally different strategy than what "
            "the problem suggests.  The problem describes fix X, gold patch "
            "implements fix Y.  An agent following the problem would fail."
        ),
        "prompt": (
            "Does the problem contain an explicit code suggestion or "
            "approach that DIFFERS from the gold patch?  Does the gold "
            "patch modify a different class/function than the problem "
            "implies?"
        ),
    },
    "mispatch_ancillary_bundling": {
        "weight": 0.3,
        "display": "Ancillary Bundling",
        "definition": (
            "Cleanup or refactoring bundled alongside the fix: whitespace, "
            "imports, docstrings, dead code removal.  These are not needed "
            "to solve the problem."
        ),
        "prompt": (
            "Are there ANCILLARY hunks that are purely cleanup (whitespace, "
            "comments, imports, docstrings)?  If ancillary_count >= 2, flag."
        ),
    },
    # ── Group C: Description Contamination ────────────────────────
    "desc_misleading": {
        "weight": 0.7,
        "display": "Misleading Description",
        "definition": (
            "Problem statement actively directs toward a wrong approach: "
            "suggests a specific fix that is not what the gold patch does."
        ),
        "prompt": (
            "Does the problem contain an explicit code suggestion or fix "
            "strategy that is INCORRECT per the gold patch?  Does the "
            "problem's root cause analysis point to the wrong location?"
        ),
    },
    "desc_incomplete": {
        "weight": 0.4,
        "display": "Incomplete Description",
        "definition": (
            "Problem missing key information: no reproduction steps, no "
            "affected file, no root cause.  Multiple valid interpretations "
            "possible."
        ),
        "prompt": (
            "Does the problem provide: clear symptom, reproduction steps, "
            "expected vs actual behavior, affected component?  If "
            "ambiguity_score >= 0.4, consider this label."
        ),
    },
    "desc_hidden_in_hints": {
        "weight": 0.4,
        "display": "Critical Info Hidden in Hints",
        "definition": (
            "Essential solution info exists only in hints text: function "
            "names, root cause diagnosis, or maintainer design decisions "
            "not in the problem statement."
        ),
        "prompt": (
            "Compare problem-only solvability vs problem+hints.  Do hints "
            "contain: exact function/class names from the gold patch, root "
            "cause not in problem, or design decisions about approach?"
        ),
    },
    "desc_self_referential": {
        "weight": 0.5,
        "display": "Self-Referential Spec",
        "definition": (
            "Problem references its own patch or test artifacts to define "
            "behavior: 'see the test case of the patch', 'attached PR'."
        ),
        "prompt": (
            "Does the problem reference 'see the patch', 'test case of "
            "the patch', 'attached PR', or similar self-references that "
            "delegate the specification to the solution?"
        ),
    },
    # ── Group D: Structural Contamination ─────────────────────────
    "scope_expansion": {
        "weight": 0.6,
        "display": "Scope Expansion",
        "definition": (
            "Fix modifies parent class or broader API than described.  "
            "Problem describes a specific-case bug but the patch changes "
            "a base class or public API affecting additional code paths."
        ),
        "prompt": (
            "Does the gold patch modify code at a BROADER scope than the "
            "problem describes?  Base class changes for a subclass bug, "
            "new public API additions?"
        ),
    },
    "circular_test_patch_dependency": {
        "weight": 0.85,
        "display": "Circular Dependency",
        "definition": (
            "F2P tests require out-of-scope patch changes to pass — a "
            "circular dependency.  Agent solving only the described "
            "problem would have tests that fail due to missing unrelated "
            "changes."
        ),
        "prompt": (
            "Do any F2P tests exercise code introduced by UNRELATED or "
            "ANCILLARY hunks?  If removing those hunks would cause test "
            "failures even with the core fix, this is a circular dependency."
        ),
    },
    # ── Group E: Clean ────────────────────────────────────────────
    "clean": {
        "weight": 0.0,
        "display": "Clean Task",
        "definition": (
            "No contamination.  Problem is clear, gold patch addresses "
            "exactly the stated problem, tests verify the described "
            "behavioral contract."
        ),
        "prompt": (
            "All hunks REQUIRED, all assertions ON_TOPIC, problem clear."
        ),
    },
    "hard_but_clean": {
        "weight": 0.0,
        "display": "Hard But Clean",
        "definition": (
            "Genuinely difficult task but fairly evaluated.  Difficulty "
            "is inherent (domain knowledge, multi-file, complex debugging), "
            "not from contamination."
        ),
        "prompt": (
            "No contamination signals AND task appears complex (many files, "
            "deep domain knowledge)."
        ),
    },
}


# ── Severity computation from weighted labels ─────────────────────────


def compute_task_severity(
    labels: list[TaskLabelAssignment],
    clean_max: float = 0.15,
    minor_max: float = 0.4,
    moderate_max: float = 0.7,
) -> tuple[Severity, float]:
    """Compute task severity from weighted label confidences.

    Formula: severity = 1 - prod(1 - w_i * c_i) for all assigned labels.

    Returns (severity_enum, score).
    """
    if not labels:
        return Severity.CLEAN, 0.0

    # Filter to contamination labels (exclude clean/hard_but_clean)
    contamination_labels = [
        la for la in labels
        if la.label not in (
            TaskContaminationLabel.CLEAN,
            TaskContaminationLabel.HARD_BUT_CLEAN,
        )
    ]
    if not contamination_labels:
        return Severity.CLEAN, 0.0

    weighted_scores = []
    for la in contamination_labels:
        weight = LABEL_DEFINITIONS.get(la.label.value, {}).get("weight", 0.5)
        weighted_scores.append(weight * la.confidence)

    score = 1.0 - reduce(
        lambda acc, ws: acc * (1.0 - ws), weighted_scores, 1.0
    )
    score = max(0.0, min(1.0, score))

    if score < clean_max:
        return Severity.CLEAN, score
    if score < minor_max:
        return Severity.MINOR, score
    if score < moderate_max:
        return Severity.MODERATE, score
    return Severity.SEVERE, score


# ── Heuristic pre-classification ──────────────────────────────────────


def _heuristic_labels(
    intent: IntentStatement,
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    vague_spec: VagueSpecDetail,
    record: TaskRecord | None = None,
) -> list[TaskLabelAssignment]:
    """Fast heuristic pre-classification from pipeline signals.

    Returns labels with confidence based on numerical thresholds.
    These serve as initial candidates for the LLM to refine.
    """
    candidates: list[TaskLabelAssignment] = []

    # A1: mistest_overtest — off-topic assertion ratio
    if excess_test.total_assertions > 0:
        off_ratio = excess_test.off_topic_assertions / excess_test.total_assertions
        if off_ratio >= 0.3 or excess_test.unrelated_count > 0:
            candidates.append(TaskLabelAssignment(
                label=TaskContaminationLabel.MISTEST_OVERTEST,
                confidence=min(off_ratio + 0.1, 1.0),
                evidence=[
                    f"{excess_test.off_topic_assertions}/{excess_test.total_assertions} "
                    f"OFF_TOPIC assertions",
                    f"{excess_test.unrelated_count} UNRELATED tests",
                ],
            ))

    # A4: mistest_sneaky_modification — modified tests with misaligned changes
    if excess_test.has_modified_tests:
        for tv in excess_test.test_verdicts:
            if tv.is_modified and not tv.modification_aligned:
                candidates.append(TaskLabelAssignment(
                    label=TaskContaminationLabel.MISTEST_SNEAKY_MODIFICATION,
                    confidence=0.8,
                    evidence=[
                        f"Test '{tv.test_name}' is pre-existing and modified "
                        f"with misaligned changes",
                    ],
                ))
                break

    # B1: mispatch_overpatch — unrelated hunks
    if excess_patch.unrelated_count > 0:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.MISPATCH_OVERPATCH,
            confidence=min(
                excess_patch.unrelated_count / max(excess_patch.total_hunks, 1),
                1.0,
            ),
            evidence=[
                f"{excess_patch.unrelated_count}/{excess_patch.total_hunks} "
                f"UNRELATED hunks",
            ],
        ))

    # B4: mispatch_ancillary_bundling
    if excess_patch.ancillary_count >= 2:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.MISPATCH_ANCILLARY_BUNDLING,
            confidence=0.6,
            evidence=[
                f"{excess_patch.ancillary_count} ANCILLARY hunks (cleanup/infra)",
            ],
        ))

    # C2: desc_incomplete — high ambiguity
    if vague_spec.score >= 0.4:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.DESC_INCOMPLETE,
            confidence=min(vague_spec.score, 1.0),
            evidence=[f"Ambiguity score: {vague_spec.score:.2f}"],
        ))

    # C4: desc_self_referential — check problem statement text
    if record and record.problem_statement:
        ps_lower = record.problem_statement.lower()
        self_ref_phrases = [
            "see the patch", "test case of the patch",
            "attached pr", "see the pr", "in the attached",
        ]
        for phrase in self_ref_phrases:
            if phrase in ps_lower:
                candidates.append(TaskLabelAssignment(
                    label=TaskContaminationLabel.DESC_SELF_REFERENTIAL,
                    confidence=0.7,
                    evidence=[f'Problem contains "{phrase}"'],
                ))
                break

    # D1: scope_expansion — UNRELATED hunks modifying different classes
    # (A rough heuristic; the LLM refines this)
    if excess_patch.unrelated_count > 0 and excess_patch.total_hunks >= 2:
        unrelated_files = set()
        for hv in excess_patch.hunk_verdicts:
            if hv.verdict.value == "UNRELATED":
                unrelated_files.add(hv.file_path)
        if len(unrelated_files) > 1:
            candidates.append(TaskLabelAssignment(
                label=TaskContaminationLabel.SCOPE_EXPANSION,
                confidence=0.5,
                evidence=[
                    f"UNRELATED hunks span {len(unrelated_files)} files: "
                    f"{', '.join(sorted(unrelated_files))}",
                ],
            ))

    return candidates


# ── LLM-based classification ─────────────────────────────────────────


TASK_CLASSIFIER_SYSTEM_PROMPT = """\
You are a benchmark contamination analyst for SWE-bench.  Your job is to
classify HOW a benchmark task is contaminated using a structured taxonomy.

You will receive the problem statement, hints text, intent extraction,
per-hunk patch verdicts, and per-assertion test verdicts.

Assign ZERO OR MORE contamination labels from this taxonomy:

TEST CONTAMINATION:
- mistest_overtest: Tests verify behavior beyond problem scope
- mistest_undertest: Tests don't fully cover the problem
- mistest_customtest: Tests so specific they reject other valid fixes
- mistest_sneaky_modification: Pre-existing test modified to assert new behavior
- mistest_deferred_requirement: Tests enforce features explicitly deferred

PATCH CONTAMINATION:
- mispatch_overpatch: Gold patch includes changes beyond problem scope
- mispatch_underpatch: Gold patch doesn't fully solve stated problem
- mispatch_approach_mismatch: Gold patch uses fundamentally different approach \
than problem suggests
- mispatch_ancillary_bundling: Cleanup/refactoring bundled alongside fix

DESCRIPTION CONTAMINATION:
- desc_misleading: Problem statement suggests wrong approach
- desc_incomplete: Problem missing key information
- desc_hidden_in_hints: Critical info only in hints, not problem
- desc_self_referential: Problem references its own patch/tests

STRUCTURAL CONTAMINATION:
- scope_expansion: Fix changes parent class or broader API than described
- circular_test_patch_dependency: F2P tests require out-of-scope patch changes

CLEAN:
- clean: No contamination detected
- hard_but_clean: Legitimately difficult but fairly evaluated

RULES:
1. Assign EVERY label that applies (tasks can have multiple labels)
2. If ANY contamination label applies, do NOT assign clean or hard_but_clean
3. For each label, provide confidence (0.0-1.0) and specific evidence
4. Only assign labels with confidence >= 0.4
5. Cite specific hunks, assertions, or problem statement text as evidence
6. Be PRECISE: distinguish mistest_overtest (tests beyond scope) from \
mistest_customtest (tests lock in one implementation approach)

Respond in valid JSON (no markdown fences):
{
    "labels": [
        {
            "label": "<taxonomy_label>",
            "confidence": 0.0-1.0,
            "evidence": ["specific evidence 1", "specific evidence 2"],
            "reasoning": "detailed explanation"
        }
    ]
}
"""


def _build_task_classifier_user_prompt(
    intent: IntentStatement,
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    vague_spec: VagueSpecDetail,
    record: TaskRecord | None = None,
    heuristic_candidates: list[TaskLabelAssignment] | None = None,
) -> str:
    """Build the user prompt for the LLM task classifier."""
    parts: list[str] = []

    parts.append(f"INSTANCE: {intent.instance_id}")
    parts.append("")

    # Problem statement
    if record and record.problem_statement:
        parts.append("PROBLEM STATEMENT:")
        parts.append(record.problem_statement[:4000])
        parts.append("")

    # Hints
    if record and record.hints_text:
        parts.append("HINTS TEXT:")
        parts.append(record.hints_text[:3000])
        parts.append("")

    # Intent extraction
    parts.append("INTENT EXTRACTION:")
    parts.append(f"- Core requirement: {intent.core_requirement}")
    parts.append(f"- Behavioral contract: {intent.behavioral_contract[:500]}")
    parts.append(f"- Acceptance criteria: {json.dumps(intent.acceptance_criteria)}")
    parts.append(f"- Out of scope: {intent.out_of_scope[:300]}")
    parts.append(f"- Ambiguity score: {intent.ambiguity_score}")
    parts.append("")

    # Patch analysis
    parts.append("GOLD PATCH ANALYSIS:")
    parts.append(f"Score: {excess_patch.score:.4f} | "
                 f"Hunks: {excess_patch.total_hunks} "
                 f"(REQUIRED={excess_patch.required_count}, "
                 f"ANCILLARY={excess_patch.ancillary_count}, "
                 f"UNRELATED={excess_patch.unrelated_count})")
    for hv in excess_patch.hunk_verdicts:
        parts.append(f"  Hunk {hv.hunk_index} [{hv.file_path}]: "
                     f"{hv.verdict.value} (conf={hv.confidence:.2f}) — "
                     f"{hv.reasoning[:200]}")
    parts.append("")

    # Test analysis
    parts.append("F2P TEST ANALYSIS:")
    parts.append(f"Score: {excess_test.score:.4f} | "
                 f"Tests: {excess_test.total_tests} "
                 f"(ALIGNED={excess_test.aligned_count}, "
                 f"TANGENTIAL={excess_test.tangential_count}, "
                 f"UNRELATED={excess_test.unrelated_count})")
    parts.append(f"Assertions: {excess_test.total_assertions} "
                 f"(ON_TOPIC={excess_test.on_topic_assertions}, "
                 f"OFF_TOPIC={excess_test.off_topic_assertions})")
    parts.append(f"Has modified tests: {excess_test.has_modified_tests}")
    for tv in excess_test.test_verdicts:
        parts.append(f"  Test '{tv.test_name}': {tv.intent_match.value} "
                     f"(modified={tv.is_modified}, "
                     f"mod_aligned={tv.modification_aligned})")
        for av in tv.assertion_verdicts[:10]:
            parts.append(f"    [{av.verdict.value}] {av.statement[:120]}")
    parts.append("")

    # Vague spec
    parts.append(f"VAGUE SPEC: score={vague_spec.score:.4f}")
    parts.append("")

    # Heuristic candidates (guidance for LLM)
    if heuristic_candidates:
        parts.append("HEURISTIC PRE-CLASSIFICATION (refine or override):")
        for hc in heuristic_candidates:
            parts.append(f"  {hc.label.value} (conf={hc.confidence:.2f}): "
                         f"{'; '.join(hc.evidence)}")
        parts.append("")

    return "\n".join(parts)


async def classify_task_labels(
    intent: IntentStatement,
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    vague_spec: VagueSpecDetail,
    record: TaskRecord | None = None,
    llm: Any | None = None,
) -> list[TaskLabelAssignment]:
    """Classify task contamination labels (Axis 1).

    If *llm* is provided, uses LLM for nuanced classification with
    heuristic candidates as guidance.  Otherwise falls back to pure
    heuristic classification.
    """
    heuristic = _heuristic_labels(intent, excess_patch, excess_test,
                                  vague_spec, record)

    if llm is None:
        # Pure heuristic fallback
        if not heuristic:
            return [TaskLabelAssignment(
                label=TaskContaminationLabel.CLEAN,
                confidence=0.8,
                evidence=["No heuristic signals detected"],
            )]
        return heuristic

    # Build LLM prompt
    user_prompt = _build_task_classifier_user_prompt(
        intent, excess_patch, excess_test, vague_spec, record, heuristic,
    )

    try:
        response = await llm.chat(
            system_prompt=TASK_CLASSIFIER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format="json",
        )
        result = json.loads(response)
        labels: list[TaskLabelAssignment] = []
        for item in result.get("labels", []):
            label_str = item.get("label", "")
            try:
                label_enum = TaskContaminationLabel(label_str)
            except ValueError:
                logger.warning("Unknown label from LLM: %s", label_str)
                continue
            confidence = float(item.get("confidence", 0.0))
            if confidence < 0.4:
                continue
            labels.append(TaskLabelAssignment(
                label=label_enum,
                confidence=confidence,
                evidence=item.get("evidence", []),
                reasoning=item.get("reasoning", ""),
            ))

        # Enforce co-occurrence rules
        has_contamination = any(
            la.label not in (
                TaskContaminationLabel.CLEAN,
                TaskContaminationLabel.HARD_BUT_CLEAN,
            )
            for la in labels
        )
        if has_contamination:
            labels = [
                la for la in labels
                if la.label not in (
                    TaskContaminationLabel.CLEAN,
                    TaskContaminationLabel.HARD_BUT_CLEAN,
                )
            ]

        if not labels:
            labels = [TaskLabelAssignment(
                label=TaskContaminationLabel.CLEAN,
                confidence=0.7,
                evidence=["LLM found no contamination signals"],
            )]
        return labels

    except Exception:
        logger.exception("LLM classification failed; falling back to heuristics")
        if not heuristic:
            return [TaskLabelAssignment(
                label=TaskContaminationLabel.CLEAN,
                confidence=0.5,
                evidence=["Heuristic fallback — no signals"],
            )]
        return heuristic


# ── Agent trajectory classification ───────────────────────────────────


AGENT_CLASSIFIER_SYSTEM_PROMPT = """\
You are a trajectory analyst for SWE-bench agent runs.  Classify HOW the
agent behaved on a task.

Assign exactly ONE primary label:

PASSED LABELS (agent resolved the task):
- agent_passed_genuine: Legitimate problem-solving with progressive exploration
- agent_passed_leak: Patch matches gold too closely; jumped to answer
- agent_passed_package_leak: Installed newer package and copied fix
- agent_passed_test_aware: Referenced F2P test names/values before discovering them
- agent_passed_trained_hack: Applied memorized template without genuine reasoning

FAILED LABELS (agent did NOT resolve the task):
- agent_failed_completed_intent: Patch addresses real problem but fails F2P tests
- agent_failed_no_intent: Did not solve the problem at all

UNKNOWN:
- agent_unknown: Insufficient trajectory data

Respond in valid JSON (no markdown fences):
{
    "label": "<label>",
    "confidence": 0.0-1.0,
    "evidence": ["evidence 1", "evidence 2"],
    "reasoning": "explanation"
}
"""


async def classify_agent_label(
    trajectory_data: dict[str, Any],
    task_labels: list[TaskLabelAssignment],
    llm: Any | None = None,
) -> AgentLabelAssignment:
    """Classify an agent's trajectory on a task (Axis 2).

    Parameters
    ----------
    trajectory_data : dict
        Must contain at minimum: 'resolved' (bool), 'final_patch' (str),
        'actions' (list), optionally 'gold_patch_similarity' (float).
    task_labels : list
        Axis 1 labels for context (helps distinguish failed-completed-intent).
    llm : optional
        LLM client for nuanced classification.
    """
    resolved = trajectory_data.get("resolved", False)
    similarity = trajectory_data.get("gold_patch_similarity", 0.0)
    actions = trajectory_data.get("actions", [])

    # Quick heuristic checks
    if not actions or len(actions) < 3:
        return AgentLabelAssignment(
            label=AgentTrajectoryLabel.AGENT_UNKNOWN,
            confidence=0.9,
            evidence=["Trajectory has fewer than 3 actions"],
        )

    if resolved and similarity >= 0.95:
        return AgentLabelAssignment(
            label=AgentTrajectoryLabel.AGENT_PASSED_LEAK,
            confidence=0.85,
            evidence=[f"Gold patch similarity: {similarity:.4f}"],
        )

    # Check for pip install leakage
    pip_commands = trajectory_data.get("pip_install_commands", [])
    if resolved and pip_commands:
        return AgentLabelAssignment(
            label=AgentTrajectoryLabel.AGENT_PASSED_PACKAGE_LEAK,
            confidence=0.7,
            evidence=[f"pip install commands: {pip_commands[:3]}"],
        )

    if llm is None:
        # Heuristic fallback
        if resolved:
            return AgentLabelAssignment(
                label=AgentTrajectoryLabel.AGENT_PASSED_GENUINE,
                confidence=0.5,
                evidence=["Heuristic: resolved without leakage signals"],
            )
        # Check if agent completed problem intent despite failing
        has_approach_mismatch = any(
            la.label == TaskContaminationLabel.MISPATCH_APPROACH_MISMATCH
            for la in task_labels
        )
        if has_approach_mismatch and trajectory_data.get("final_patch"):
            return AgentLabelAssignment(
                label=AgentTrajectoryLabel.AGENT_FAILED_COMPLETED_INTENT,
                confidence=0.4,
                evidence=[
                    "Task has approach mismatch and agent produced a patch",
                ],
            )
        return AgentLabelAssignment(
            label=AgentTrajectoryLabel.AGENT_FAILED_NO_INTENT,
            confidence=0.5,
            evidence=["Heuristic: not resolved, no special signals"],
        )

    # Full LLM classification
    try:
        user_parts = [
            f"RESOLVED: {resolved}",
            f"GOLD_PATCH_SIMILARITY: {similarity:.4f}",
            f"NUM_ACTIONS: {len(actions)}",
            f"TASK_LABELS: {[la.label.value for la in task_labels]}",
        ]
        if trajectory_data.get("final_patch"):
            user_parts.append(f"FINAL_PATCH_EXCERPT:\n{trajectory_data['final_patch'][:2000]}")

        # Include trajectory summary
        action_summary = []
        for act in actions[:30]:
            if isinstance(act, dict):
                action_summary.append(
                    f"[{act.get('action_type', '?')}] "
                    f"{str(act.get('content', ''))[:150]}"
                )
        if action_summary:
            user_parts.append("TRAJECTORY:\n" + "\n".join(action_summary))

        response = await llm.chat(
            system_prompt=AGENT_CLASSIFIER_SYSTEM_PROMPT,
            user_prompt="\n\n".join(user_parts),
            response_format="json",
        )
        result = json.loads(response)
        label_str = result.get("label", "agent_unknown")
        try:
            label_enum = AgentTrajectoryLabel(label_str)
        except ValueError:
            label_enum = AgentTrajectoryLabel.AGENT_UNKNOWN

        return AgentLabelAssignment(
            label=label_enum,
            confidence=float(result.get("confidence", 0.5)),
            evidence=result.get("evidence", []),
            reasoning=result.get("reasoning", ""),
        )

    except Exception:
        logger.exception("Agent LLM classification failed")
        if resolved:
            return AgentLabelAssignment(
                label=AgentTrajectoryLabel.AGENT_PASSED_GENUINE,
                confidence=0.3,
                evidence=["LLM fallback"],
            )
        return AgentLabelAssignment(
            label=AgentTrajectoryLabel.AGENT_FAILED_NO_INTENT,
            confidence=0.3,
            evidence=["LLM fallback"],
        )


# ── Backward compatibility mapping ───────────────────────────────────


# Map old LeakagePattern values to new AgentTrajectoryLabel
LEAKAGE_PATTERN_MAP: dict[str, AgentTrajectoryLabel] = {
    "GENUINE_SOLUTION": AgentTrajectoryLabel.AGENT_PASSED_GENUINE,
    "GOLD_PATCH_LEAK": AgentTrajectoryLabel.AGENT_PASSED_LEAK,
    "PACKAGE_LEAK": AgentTrajectoryLabel.AGENT_PASSED_PACKAGE_LEAK,
    "TEST_AWARE": AgentTrajectoryLabel.AGENT_PASSED_TEST_AWARE,
    "PARTIAL_MATCH": AgentTrajectoryLabel.AGENT_UNKNOWN,
    "UNKNOWN": AgentTrajectoryLabel.AGENT_UNKNOWN,
}
