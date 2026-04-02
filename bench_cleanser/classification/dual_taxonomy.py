"""Dual Taxonomy classifier: Axis 1 (task labels) + Axis 2 (agent labels).

Axis 1 assigns zero or more TaskContaminationLabel to each task.
Axis 2 assigns a single AgentTrajectoryLabel per agent-task pair.

8 binary labels, bucket-based severity, no ratio thresholds.

Taxonomy alignment with OpenAI's SWE-bench Verified audit (April 2026):
  - "Narrow test cases" (35.5% of audited failures) -> APPROACH_LOCK
  - "Wide test cases" (18.8% of audited failures)   -> WIDE_TESTS
  - Training contamination (gold patch memorization) -> Axis 2 agent_passed_leak

See: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bench_cleanser.analysis.cross_ref import CrossReferenceResult
from bench_cleanser.models import (
    AgentLabelAssignment,
    AgentTrajectoryLabel,
    ExcessPatchDetail,
    ExcessTestDetail,
    IntentStatement,
    Severity,
    TaskContaminationLabel,
    TaskLabelAssignment,
    TaskRecord,
    VagueSpecDetail,
)

logger = logging.getLogger(__name__)


LABEL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "approach_lock": {
        "display": "Approach Lock",
        "definition": (
            "The F2P tests require a specific implementation approach that "
            "the problem statement does not determine.  An agent that solves "
            "the described problem using a different valid approach will fail "
            "the tests."
        ),
        "openai_equivalent": "Narrow test cases",
        "prompt": (
            "Would a correct-but-different solution fail the F2P tests?  "
            "Do the tests assert on implementation details (specific class, "
            "method, or code structure) rather than on observable behavior?  "
            "Does the gold patch take a fundamentally different approach "
            "than the problem statement suggests?"
        ),
    },
    "wide_tests": {
        "display": "Wide Tests",
        "definition": (
            "F2P tests verify behavior or features that the problem "
            "statement does not describe.  The tests go beyond the stated "
            "acceptance criteria — they test additional functionality, "
            "edge cases, or code paths not mentioned.  Includes tests "
            "enforcing features the problem explicitly defers."
        ),
        "openai_equivalent": "Wide test cases",
        "prompt": (
            "Do the F2P tests assert on behavior not described in the "
            "problem?  Is there at least one test or assertion that targets "
            "undescribed behavior?  Does the problem contain deferral "
            "language yet F2P tests exercise the deferred feature?"
        ),
    },
    "test_mutation": {
        "display": "Test Mutation",
        "definition": (
            "A pre-existing test was modified to assert on new behavior "
            "not described in the problem statement.  The test existed "
            "before the PR, making it look legitimate, but the PR author "
            "silently changed assertions or expected values."
        ),
        "prompt": (
            "Is there a MODIFIED (pre-existing) test?  If so, do the "
            "changes add assertions or expected values for behavior NOT "
            "described in the problem statement?"
        ),
    },
    "scope_creep": {
        "display": "Scope Creep",
        "definition": (
            "The gold patch contains behavioral code changes beyond what "
            "the problem asks for — new features, unrelated refactoring, "
            "scope expansion.  Pure ancillary changes (imports, whitespace, "
            "docstrings) do NOT count; only behavioral excess matters."
        ),
        "prompt": (
            "Does the gold patch modify code that the problem doesn't ask "
            "for?  Are there hunks introducing NEW behavior beyond problem "
            "scope?  Ignore purely ancillary changes (imports, whitespace, "
            "docstrings).  Does the patch modify broader scope (base class, "
            "public API) than the problem describes?"
        ),
    },
    "unclear_spec": {
        "display": "Unclear Spec",
        "definition": (
            "The problem statement is too ambiguous or actively misleading "
            "to determine the correct solution.  Either key information is "
            "missing (no repro steps, no affected component, multiple valid "
            "interpretations) or the description points toward the wrong fix."
        ),
        "prompt": (
            "Can a competent developer determine the correct fix from the "
            "problem statement alone?  Is the problem ambiguous enough that "
            "multiple incompatible approaches are equally reasonable?  Does "
            "the problem suggest a specific fix strategy that is incorrect "
            "per the gold patch?"
        ),
    },
    "hidden_context": {
        "display": "Hidden Context",
        "definition": (
            "Essential information needed to solve the problem exists only "
            "in the hints text (code review comments, maintainer decisions) "
            "and not in the problem statement.  The problem alone is "
            "insufficient; the hints contain the actual specification.  "
            "Includes problems that reference their own patch/tests."
        ),
        "prompt": (
            "Does the hints text contain solution-critical information "
            "absent from the problem?  Function names, root cause, or "
            "design decisions not derivable from the problem alone?  Does "
            "the problem reference 'see the patch' or 'attached PR'?"
        ),
    },
    "weak_coverage": {
        "display": "Weak Coverage",
        "definition": (
            "The F2P tests or gold patch don't fully cover the stated "
            "acceptance criteria.  A partial or incorrect fix can pass.  "
            "This makes the task easier (not harder) — it's a benchmark "
            "quality issue, not a fairness issue."
        ),
        "prompt": (
            "Can an incomplete fix pass the F2P tests?  Are there "
            "acceptance criteria items that no F2P test verifies?  Does "
            "the gold patch leave some stated requirements unaddressed?"
        ),
    },
}



def compute_task_severity(
    labels: list[TaskLabelAssignment],
) -> Severity:
    """Compute task severity from bucket-based rules (no math, no weights).

    Severity is determined entirely by WHICH labels are present:

    SEVERE:
      - APPROACH_LOCK is present, OR
      - Both WIDE_TESTS and SCOPE_CREEP are present

    MODERATE:
      - TEST_MUTATION is present, OR
      - WIDE_TESTS alone (without SCOPE_CREEP)

    MINOR:
      - SCOPE_CREEP alone, OR
      - UNCLEAR_SPEC alone, OR
      - HIDDEN_CONTEXT alone, OR
      - WEAK_COVERAGE alone

    CLEAN:
      - No contamination labels
    """
    if not labels:
        return Severity.CLEAN

    label_set = {
        la.label for la in labels
        if la.label != TaskContaminationLabel.CLEAN
    }

    if not label_set:
        return Severity.CLEAN

    # SEVERE: approach_lock OR (wide_tests + scope_creep)
    if TaskContaminationLabel.APPROACH_LOCK in label_set:
        return Severity.SEVERE
    if (TaskContaminationLabel.WIDE_TESTS in label_set
            and TaskContaminationLabel.SCOPE_CREEP in label_set):
        return Severity.SEVERE

    # MODERATE: test_mutation OR wide_tests alone
    if TaskContaminationLabel.TEST_MUTATION in label_set:
        return Severity.MODERATE
    if TaskContaminationLabel.WIDE_TESTS in label_set:
        return Severity.MODERATE

    # MINOR: any remaining contamination label
    return Severity.MINOR



def _heuristic_labels(
    intent: IntentStatement,
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    vague_spec: VagueSpecDetail,
    record: TaskRecord | None = None,
    cross_ref: CrossReferenceResult | None = None,
) -> list[TaskLabelAssignment]:
    """Fast heuristic pre-classification from pipeline signals.

    Uses binary signals only — no ratio thresholds or counting.
    These serve as initial candidates for the LLM to refine.
    """
    candidates: list[TaskLabelAssignment] = []

    # WIDE_TESTS: any OFF_TOPIC assertion or UNRELATED test
    has_off_topic = excess_test.off_topic_assertions > 0
    has_unrelated_test = excess_test.unrelated_count > 0
    if has_off_topic or has_unrelated_test:
        evidence = []
        if has_off_topic:
            evidence.append(f"{excess_test.off_topic_assertions} OFF_TOPIC assertions found")
        if has_unrelated_test:
            evidence.append(f"{excess_test.unrelated_count} UNRELATED tests found")
        for tv in excess_test.test_verdicts:
            if tv.is_modified and tv.off_topic_count > 0:
                evidence.append(
                    f"Modified test '{tv.test_name}' has {tv.off_topic_count} "
                    f"OFF_TOPIC assertions (pre-existing test with added excess)"
                )
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.WIDE_TESTS,
            confidence=0.7,
            evidence=evidence,
        ))

    # TEST_MUTATION: any modified test with misaligned changes
    if excess_test.has_modified_tests:
        for tv in excess_test.test_verdicts:
            if tv.is_modified and not tv.modification_aligned:
                candidates.append(TaskLabelAssignment(
                    label=TaskContaminationLabel.TEST_MUTATION,
                    confidence=0.8,
                    evidence=[
                        f"Test '{tv.test_name}' is pre-existing and modified "
                        f"with misaligned changes",
                    ],
                ))
                break

    # SCOPE_CREEP: any UNRELATED hunk with behavioral changes
    # (pure ancillary does NOT trigger this)
    if excess_patch.unrelated_count > 0:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.SCOPE_CREEP,
            confidence=0.7,
            evidence=[
                f"{excess_patch.unrelated_count} UNRELATED hunks with "
                f"behavioral changes beyond problem scope",
            ],
        ))

    # UNCLEAR_SPEC: high ambiguity score
    if vague_spec.score >= 0.4:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.UNCLEAR_SPEC,
            confidence=0.6,
            evidence=[f"Ambiguity score: {vague_spec.score:.2f}"],
        ))

    # HIDDEN_CONTEXT: check for self-referential problem statement
    if record and record.problem_statement:
        ps_lower = record.problem_statement.lower()
        self_ref_phrases = [
            "see the patch", "test case of the patch",
            "attached pr", "see the pr", "in the attached",
        ]
        for phrase in self_ref_phrases:
            if phrase in ps_lower:
                candidates.append(TaskLabelAssignment(
                    label=TaskContaminationLabel.HIDDEN_CONTEXT,
                    confidence=0.7,
                    evidence=[f'Problem contains "{phrase}"'],
                ))
                break

    # APPROACH_LOCK: reporter suggested a specific fix approach
    if intent.decomposition and intent.decomposition.suggested_fix:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.APPROACH_LOCK,
            confidence=0.4,
            evidence=[
                f"Reporter suggests fix approach: "
                f"{intent.decomposition.suggested_fix[:200]}",
            ],
        ))

    # APPROACH_LOCK: circular dependency between tests and out-of-scope hunks
    if cross_ref and cross_ref.has_circular:
        for cd in cross_ref.circular_dependencies:
            candidates.append(TaskLabelAssignment(
                label=TaskContaminationLabel.APPROACH_LOCK,
                confidence=cd.confidence,
                evidence=[
                    cd.reasoning,
                    f"Linked UNRELATED hunks: {cd.linked_hunk_indices}",
                ],
            ))
            break

    return candidates



TASK_CLASSIFIER_SYSTEM_PROMPT = """\
You are a benchmark contamination analyst for SWE-bench.  Your job is to
classify HOW a benchmark task is contaminated using a structured taxonomy.

You will receive the problem statement, requirements (if any), interface
specification (if any), hints text, intent extraction, per-hunk patch
verdicts, and per-assertion test verdicts.

NOTE: For SWE-bench Pro tasks, the problem statement is narrow but the
requirements and interface fields contain the full specification.  When
evaluating contamination, consider ALL three fields together as the complete
task description.  Do NOT flag behavior as "excess" if it is described in
the requirements or interface sections.

Assign ZERO OR MORE contamination labels from this taxonomy:

- approach_lock: F2P tests require a specific implementation approach the \
problem doesn't determine.  A correct-but-different solution would fail.  \
This includes approach mismatch (gold patch uses a fundamentally different \
strategy than the problem suggests) and circular test-patch dependencies \
(tests require out-of-scope patch changes).

- wide_tests: F2P tests verify behavior or features not described in the \
problem.  Tests go beyond the stated acceptance criteria.  Includes tests \
enforcing features the problem explicitly defers.

- test_mutation: A pre-existing test was modified to assert on new behavior \
not in the problem statement.  The test looked legitimate but was silently \
changed.

- scope_creep: Gold patch contains behavioral code changes beyond what the \
problem asks for.  New features, unrelated refactoring, scope expansion.  \
Pure ancillary changes (imports, whitespace, docstrings) do NOT count.

- unclear_spec: Problem statement is too ambiguous or actively misleading \
to determine the correct solution.  Key info missing or description points \
toward wrong fix.

- hidden_context: Essential solution info exists only in hints text \
(code review comments, maintainer decisions), not in the problem.  \
Includes self-referential problems that reference their own patch/tests.

- weak_coverage: F2P tests or gold patch don't fully cover stated acceptance \
criteria.  A partial fix can pass.  This is a benchmark quality issue, \
not a fairness issue.

CLEAN:
- clean: No contamination detected.

RULES:
1. Assign EVERY label that applies (tasks can have multiple labels)
2. If ANY contamination label applies, do NOT assign clean
3. For each label, provide confidence (0.0-1.0) and specific evidence
4. Only assign labels with confidence >= 0.4
5. Cite specific hunks, assertions, or problem statement text as evidence
6. Be PRECISE: distinguish approach_lock (tests reject valid alternatives) \
from wide_tests (tests go beyond scope but don't lock approach)
7. Do NOT flag pure ancillary changes (imports, whitespace) as scope_creep

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
    cross_ref: CrossReferenceResult | None = None,
) -> str:
    """Build the user prompt for the LLM task classifier."""
    parts: list[str] = []

    parts.append(f"INSTANCE: {intent.instance_id}")
    parts.append("")

    # Problem statement
    if record and record.problem_statement:
        parts.append("PROBLEM STATEMENT:")
        parts.append(record.problem_statement[:16000])
        parts.append("")

    # Requirements (SWE-bench Pro)
    if record and record.requirements:
        parts.append("REQUIREMENTS:")
        parts.append(record.requirements[:16000])
        parts.append("")

    # Interface (SWE-bench Pro)
    if record and record.interface:
        parts.append("INTERFACE:")
        parts.append(record.interface[:8000])
        parts.append("")

    # Hints
    if record and record.hints_text:
        parts.append("HINTS TEXT:")
        parts.append(record.hints_text[:8000])
        parts.append("")

    # Intent extraction
    parts.append("INTENT EXTRACTION:")
    parts.append(f"- Core requirement: {intent.core_requirement}")
    parts.append(f"- Behavioral contract: {intent.behavioral_contract[:2000]}")
    parts.append(f"- Acceptance criteria: {json.dumps(intent.acceptance_criteria)}")
    parts.append(f"- Out of scope: {intent.out_of_scope[:1000]}")
    parts.append(f"- Ambiguity score: {intent.ambiguity_score}")

    if intent.decomposition:
        d = intent.decomposition
        parts.append("")
        parts.append("PROBLEM DECOMPOSITION:")
        parts.append(f"- Bug description: {d.bug_description[:2000]}")
        if d.suggested_fix:
            parts.append(f"- Reporter's suggested fix: {d.suggested_fix[:2000]}")
            parts.append("  (Compare this to the gold patch — divergence signals APPROACH_LOCK)")
        parts.append(f"- Legitimacy: {d.legitimacy}")
        entities = []
        if d.mentioned_files:
            entities.append(f"Files: {', '.join(d.mentioned_files[:10])}")
        if d.mentioned_functions:
            entities.append(f"Functions: {', '.join(d.mentioned_functions[:10])}")
        if d.mentioned_classes:
            entities.append(f"Classes: {', '.join(d.mentioned_classes[:10])}")
        if d.mentioned_variables:
            entities.append(f"Variables: {', '.join(d.mentioned_variables[:10])}")
        if d.mentioned_modules:
            entities.append(f"Modules: {', '.join(d.mentioned_modules[:10])}")
        if entities:
            parts.append(f"- Code entities: {'; '.join(entities)}")
    parts.append("")

    # Patch analysis
    parts.append("GOLD PATCH ANALYSIS:")
    parts.append(f"Has excess: {excess_patch.has_excess} | "
                 f"Hunks: {excess_patch.total_hunks} "
                 f"(REQUIRED={excess_patch.required_count}, "
                 f"ANCILLARY={excess_patch.ancillary_count}, "
                 f"UNRELATED={excess_patch.unrelated_count})")
    for hv in excess_patch.hunk_verdicts:
        heuristic_tag = " [heuristic]" if hv.is_heuristic else ""
        parts.append(f"  Hunk {hv.hunk_index} [{hv.file_path}]: "
                     f"{hv.verdict.value} (conf={hv.confidence:.2f}){heuristic_tag} — "
                     f"{hv.reasoning[:1000]}")
    parts.append("")

    # Test analysis
    parts.append("F2P TEST ANALYSIS:")
    parts.append(f"Has excess: {excess_test.has_excess} | "
                 f"Tests: {excess_test.total_tests} "
                 f"(ALIGNED={excess_test.aligned_count}, "
                 f"TANGENTIAL={excess_test.tangential_count}, "
                 f"UNRELATED={excess_test.unrelated_count})")
    parts.append(f"Assertions: {excess_test.total_assertions} "
                 f"(ON_TOPIC={excess_test.on_topic_assertions}, "
                 f"OFF_TOPIC={excess_test.off_topic_assertions})")
    parts.append(f"Has modified tests: {excess_test.has_modified_tests}")
    for tv in excess_test.test_verdicts:
        mod_tag = ""
        if tv.is_modified:
            mod_tag = " [MODIFIED pre-existing test"
            if not tv.modification_aligned:
                mod_tag += ", MISALIGNED changes"
            if tv.off_topic_count > 0:
                mod_tag += f", {tv.off_topic_count} OFF_TOPIC assertions"
            mod_tag += "]"
        parts.append(f"  Test '{tv.test_name}': {tv.intent_match.value} "
                     f"(conf={tv.confidence:.2f}){mod_tag}")
        if tv.reasoning:
            parts.append(f"    Reasoning: {tv.reasoning[:1000]}")
        for av in tv.assertion_verdicts[:50]:
            reason_tag = f" — {av.reason[:100]}" if av.reason else ""
            parts.append(f"    [{av.verdict.value}] {av.statement[:120]}{reason_tag}")
    parts.append("")

    # Vague spec
    parts.append(f"VAGUE SPEC: score={vague_spec.score:.4f}")
    if vague_spec.reasoning:
        parts.append(f"  Reasoning: {vague_spec.reasoning[:1000]}")
    parts.append("")

    if cross_ref and cross_ref.has_circular:
        parts.append("CROSS-REFERENCE ANALYSIS:")
        parts.append(f"Circular dependencies detected: {len(cross_ref.circular_dependencies)}")
        for cd in cross_ref.circular_dependencies:
            parts.append(f"  Test '{cd.test_name}' → UNRELATED hunks {cd.linked_hunk_indices} "
                         f"(conf={cd.confidence:.2f})")
            if cd.linked_files:
                parts.append(f"    Files: {', '.join(cd.linked_files)}")
            parts.append(f"    {cd.reasoning}")
        parts.append("  This is a strong APPROACH_LOCK signal: tests require code "
                     "the problem doesn't ask for.")
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
    cross_ref: CrossReferenceResult | None = None,
) -> list[TaskLabelAssignment]:
    """Classify task contamination labels (Axis 1).

    If *llm* is provided, uses LLM for nuanced classification with
    heuristic candidates as guidance.  Otherwise falls back to pure
    heuristic classification.
    """
    heuristic = _heuristic_labels(intent, excess_patch, excess_test,
                                  vague_spec, record, cross_ref)

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
        cross_ref=cross_ref,
    )

    try:
        result = await llm.query_json(
            system_prompt=TASK_CLASSIFIER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
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
            la.label != TaskContaminationLabel.CLEAN
            for la in labels
        )
        if has_contamination:
            labels = [
                la for la in labels
                if la.label != TaskContaminationLabel.CLEAN
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
        has_approach_lock = any(
            la.label == TaskContaminationLabel.APPROACH_LOCK
            for la in task_labels
        )
        if has_approach_lock and trajectory_data.get("final_patch"):
            return AgentLabelAssignment(
                label=AgentTrajectoryLabel.AGENT_FAILED_COMPLETED_INTENT,
                confidence=0.4,
                evidence=[
                    "Task has approach lock and agent produced a patch",
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
            user_parts.append(f"FINAL_PATCH_EXCERPT:\n{trajectory_data['final_patch'][:20000]}")

        # Include trajectory summary
        action_summary = []
        for act in actions[:100]:
            if isinstance(act, dict):
                action_summary.append(
                    f"[{act.get('action_type', '?')}] "
                    f"{str(act.get('content', ''))[:2000]}"
                )
        if action_summary:
            user_parts.append("TRAJECTORY:\n" + "\n".join(action_summary))

        result = await llm.query_json(
            system_prompt=AGENT_CLASSIFIER_SYSTEM_PROMPT,
            user_prompt="\n\n".join(user_parts),
        )
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

