"""Dual Taxonomy classifier: Axis 1 (task labels) + Axis 2 (agent labels).

Axis 1 assigns zero or more TaskContaminationLabel to each task.
Axis 2 assigns a single AgentTrajectoryLabel per agent-task pair.

7 binary labels, bucket-based severity, no ratio thresholds.

Taxonomy alignment with OpenAI's SWE-bench Verified audit (April 2026):
  - "Narrow test cases" (35.5% of audited failures) -> APPROACH_LOCK
  - "Wide test cases" (18.8% of audited failures)   -> OVER_TEST
  - Training contamination (gold patch memorization) -> Axis 2 agent_passed_leak

Uses structured output with strict JSON schema enforcement.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bench_cleanser.analysis.cross_ref import CrossReferenceResult
from bench_cleanser.models import (
    IntentStatement,
    PatchAnalysis,
    PatchVerdict,
    Severity,
    TaskContaminationLabel,
    TaskLabelAssignment,
    TaskRecord,
    TestAnalysis,
    DescriptionClarity,
)
from bench_cleanser.schemas import TaskClassificationResponse

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
    "over_test": {
        "display": "Over Test",
        "definition": (
            "F2P tests verify behavior or features that the problem "
            "statement does not describe.  The tests go beyond the stated "
            "acceptance criteria — they test additional functionality, "
            "edge cases, or code paths not mentioned.  Includes tests "
            "enforcing features the problem explicitly defers, and "
            "pre-existing tests modified to assert on behavior beyond "
            "what the problem description asks for."
        ),
        "openai_equivalent": "Wide test cases",
        "prompt": (
            "Do the F2P tests assert on behavior not described in the "
            "problem?  Is there at least one test or assertion that targets "
            "undescribed behavior?  Does the problem contain deferral "
            "language yet F2P tests exercise the deferred feature?  "
            "Were any pre-existing tests modified to introduce assertions "
            "beyond what the problem description requires?"
        ),
    },
    "over_patch": {
        "display": "Over Patch",
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
    "unclear_description": {
        "display": "Unclear Description",
        "definition": (
            "The problem description is too ambiguous or actively misleading "
            "to determine the correct solution.  Either key information is "
            "missing (no repro steps, no affected component, multiple valid "
            "interpretations) or the description points toward the wrong fix."
        ),
        "prompt": (
            "Can a competent developer determine the correct fix from the "
            "problem description alone?  Is the problem ambiguous enough that "
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
            "and not in the problem description.  The problem alone is "
            "insufficient; the hints contain the actual specification."
        ),
        "prompt": (
            "Does the hints text contain solution-critical information "
            "absent from the problem?  Function names, root cause, or "
            "design decisions not derivable from the problem alone?"
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
      - Both OVER_TEST and OVER_PATCH are present

    MODERATE:
      - OVER_TEST alone (without OVER_PATCH)

    MINOR:
      - OVER_PATCH alone, OR
      - UNCLEAR_DESCRIPTION alone, OR
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

    # SEVERE: approach_lock OR (over_test + over_patch)
    if TaskContaminationLabel.APPROACH_LOCK in label_set:
        return Severity.SEVERE
    if (TaskContaminationLabel.OVER_TEST in label_set
            and TaskContaminationLabel.OVER_PATCH in label_set):
        return Severity.SEVERE

    # MODERATE: over_test alone
    if TaskContaminationLabel.OVER_TEST in label_set:
        return Severity.MODERATE

    # MINOR: any remaining contamination label
    return Severity.MINOR



def _heuristic_labels(
    intent: IntentStatement,
    patch_analysis: PatchAnalysis,
    test_analysis: TestAnalysis,
    description_clarity: DescriptionClarity,
    record: TaskRecord | None = None,
    cross_ref: CrossReferenceResult | None = None,
) -> list[TaskLabelAssignment]:
    """Fast heuristic pre-classification from pipeline signals.

    Uses binary signals only — no ratio thresholds or counting.
    These serve as initial candidates for the LLM to refine.
    """
    candidates: list[TaskLabelAssignment] = []

    # OVER_TEST: any OFF_TOPIC assertion, UNRELATED test, or misaligned modified test
    has_off_topic = test_analysis.off_topic_assertions > 0
    has_unrelated_test = test_analysis.unrelated_count > 0
    has_misaligned_modification = False
    if has_off_topic or has_unrelated_test:
        evidence = []
        if has_off_topic:
            evidence.append(f"{test_analysis.off_topic_assertions} OFF_TOPIC assertions found")
        if has_unrelated_test:
            evidence.append(f"{test_analysis.unrelated_count} UNRELATED tests found")
        for tv in test_analysis.test_verdicts:
            if tv.is_modified and tv.off_topic_count > 0:
                evidence.append(
                    f"Modified test '{tv.test_name}' has {tv.off_topic_count} "
                    f"OFF_TOPIC assertions (pre-existing test with added excess)"
                )
            if tv.is_modified and not tv.modification_aligned:
                has_misaligned_modification = True
                evidence.append(
                    f"Modified test '{tv.test_name}' has misaligned changes "
                    f"(pre-existing test modified beyond problem scope)"
                )
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.OVER_TEST,
            evidence=evidence,
        ))
    elif test_analysis.has_modified_tests:
        # Check for misaligned modifications even without other signals
        for tv in test_analysis.test_verdicts:
            if tv.is_modified and not tv.modification_aligned:
                has_misaligned_modification = True
                candidates.append(TaskLabelAssignment(
                    label=TaskContaminationLabel.OVER_TEST,
                    evidence=[
                        f"Test '{tv.test_name}' is pre-existing and modified "
                        f"with changes beyond problem scope",
                    ],
                ))
                break

    # Pre-staged test value coupling (AUDIT Pattern 2)
    if test_analysis.test_verdicts:
        for tv in test_analysis.test_verdicts:
            if tv.off_topic_count > 0 and tv.is_modified:
                candidates.append(TaskLabelAssignment(
                    label=TaskContaminationLabel.OVER_TEST,
                    evidence=[
                        f"Pre-existing test '{tv.test_name}' modified with {tv.off_topic_count} "
                        f"OFF_TOPIC assertions — may assert on gold patch implementation values "
                        f"not derivable from problem statement",
                    ],
                ))
                break

    # OVER_PATCH: any UNRELATED hunk with behavioral changes
    # (pure ancillary does NOT trigger this)
    if patch_analysis.unrelated_count > 0:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.OVER_PATCH,
            evidence=[
                f"{patch_analysis.unrelated_count} UNRELATED hunks with "
                f"behavioral changes beyond problem scope",
            ],
        ))

    # Task/Patch Mismatch (AUDIT Pattern 1)
    if patch_analysis.required_count == 0 and patch_analysis.unrelated_count >= 2:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.APPROACH_LOCK,
            evidence=[
                f"Task/Patch Mismatch: 0 REQUIRED hunks, {patch_analysis.unrelated_count} UNRELATED hunks",
                "Gold patch implements entirely different functionality than problem describes",
            ],
        ))

    # Compilation barrier (AUDIT Pattern 3)
    monolithic_extensions = {".go", ".ts", ".tsx", ".rs"}
    if patch_analysis.unrelated_count > 0:
        unrelated_files = [hv.file_path for hv in patch_analysis.hunk_verdicts
                           if hv.verdict == PatchVerdict.UNRELATED]
        has_monolithic = any(
            any(f.endswith(ext) for ext in monolithic_extensions)
            for f in unrelated_files
        )
        if has_monolithic:
            candidates.append(TaskLabelAssignment(
                label=TaskContaminationLabel.APPROACH_LOCK,
                evidence=[
                    f"Potential compilation barrier: UNRELATED hunks in monolithic project files",
                    f"Files: {', '.join(unrelated_files[:5])}",
                    "In Go/TypeScript/Rust, unrelated changes may be required for compilation",
                ],
            ))

    # UNCLEAR_DESCRIPTION: high ambiguity score
    if description_clarity.score >= 0.4:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.UNCLEAR_DESCRIPTION,
            evidence=[f"Ambiguity score: {description_clarity.score:.2f}"],
        ))

    # HIDDEN_CONTEXT: check for self-referential problem description
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
                    evidence=[f'Problem contains "{phrase}"'],
                ))
                break

    # APPROACH_LOCK: reporter suggested a specific fix approach
    if intent.decomposition and intent.decomposition.suggested_fix:
        candidates.append(TaskLabelAssignment(
            label=TaskContaminationLabel.APPROACH_LOCK,
            evidence=[
                f"Reporter suggests fix approach: "
                f"{intent.decomposition.suggested_fix}",
            ],
        ))

    # APPROACH_LOCK: overpatch-overtest coupling (tests require out-of-scope hunks)
    if cross_ref and cross_ref.has_coupling:
        for cd in cross_ref.couplings:
            candidates.append(TaskLabelAssignment(
                label=TaskContaminationLabel.APPROACH_LOCK,
                evidence=[
                    cd.reasoning,
                    f"Linked UNRELATED hunks: {cd.linked_hunk_indices}",
                ],
            ))
            break

    # Pre-staged test detection (AUDIT_PROTOCOL Gap 1)
    if record:
        has_test_patch = bool(getattr(record, 'test_patch', '') and record.test_patch.strip())
        has_before_cmd = "git checkout" in getattr(record, 'before_repo_set_cmd', '')
        if (has_test_patch or has_before_cmd) and not test_analysis.has_modified_tests:
            candidates.append(TaskLabelAssignment(
                label=TaskContaminationLabel.APPROACH_LOCK,
                evidence=[
                    "Tests pre-staged via before_repo_set_cmd (git checkout from gold commit)",
                    "Pipeline is_modified=False but test_patch has content — gap in modification detection",
                    "Pre-staged tests may assert on exact implementation values from gold commit",
                ],
            ))

    return candidates



TASK_CLASSIFIER_SYSTEM_PROMPT = """\
You are a benchmark contamination analyst for SWE-bench, the standard benchmark \
for evaluating AI coding agents on real-world software engineering tasks. Your job \
is to classify HOW a benchmark task is contaminated using a structured taxonomy.

## BACKGROUND

SWE-bench tasks consist of:
1. A problem description (bug report / feature request from a real GitHub issue)
2. A gold patch (the actual fix committed by the developer)
3. F2P tests (fail-to-pass tests that the gold patch makes pass)
4. P2P tests (pass-to-pass tests that should continue to pass)

"Contamination" here means the task is unfair, misleading, or does not accurately \
measure agent capability. A contaminated task may cause:
- FALSE POSITIVES: agents that memorized the benchmark pass without understanding
- FALSE NEGATIVES: agents with genuine understanding fail due to unfair test design
- MISLEADING METRICS: the benchmark score doesn't reflect real coding ability

## YOUR INPUT

You will receive the COMPLETE pipeline analysis for one task:
- Problem description, requirements (SWE-bench Pro), interface spec, hints text
- Intent extraction (acceptance criteria, ambiguity, decomposition)
- Per-hunk patch verdicts (REQUIRED / ANCILLARY / UNRELATED)
- Per-test and per-assertion verdicts (ALIGNED/TANGENTIAL/UNRELATED, ON_TOPIC/OFF_TOPIC)
- Cross-reference analysis (overpatch-overtest coupling between tests and out-of-scope hunks)
- Heuristic pre-classification candidates (to refine or override)

## TAXONOMY: 6 CONTAMINATION LABELS + CLEAN

### approach_lock (SEVERE)
F2P tests require a SPECIFIC implementation approach that the problem description \
does not determine. An agent that solves the described problem correctly using \
a different valid approach WILL FAIL the tests.

SUBTYPES:
- **Narrow test assertions**: Tests check implementation details (specific class, \
method name, internal data structure) rather than observable behavior
- **Approach mismatch**: The gold patch uses a fundamentally different strategy \
than the problem description suggests, and the tests are written specifically for \
the gold patch's approach
- **Overpatch-overtest coupling**: Tests require UNRELATED patch hunks to pass \
— the tests exercise code that the problem doesn't ask for

IMPORTANT DISTINCTIONS:
- approach_lock is NOT about the tests being too strict in general — it's about \
the tests rejecting VALID ALTERNATIVE solutions
- A test that checks "output X equals Y" is fine even if strict, as long as any \
correct solution would produce the same output
- approach_lock IS present when tests check HOW the fix works (internal state, \
specific method calls) rather than WHAT it produces

### over_test (MODERATE-SEVERE)
F2P tests verify behavior or features that the problem description does NOT describe. \
The tests go beyond the stated acceptance criteria by testing additional \
functionality, edge cases, or code paths not mentioned in the problem. This also \
covers pre-existing tests that were modified to assert on behavior beyond the \
problem scope — making the task unreasonably harder than the problem requires.

SUBTYPES:
- **Extra assertions**: Some assertions in otherwise-aligned tests check undescribed behavior
- **Extra test functions**: Entire test functions target undescribed features
- **Deferred feature testing**: The problem explicitly defers a feature ("this can \
be handled later") but the F2P tests exercise that deferred feature
- **Modified test excess**: A pre-existing test was modified and the modifications \
introduce assertions beyond the problem scope

IMPORTANT DISTINCTIONS:
- over_test is about SCOPE (tests beyond what was asked)
- approach_lock is about CORRECTNESS (tests reject valid alternatives)
- A test can be BOTH over_test (tests extra stuff) AND approach-locking (requires specific impl)
- If the Requirements or Interface section describes the behavior, it is NOT over_test \
(SWE-bench Pro has narrow problem descriptions but detailed requirements)
- If a pre-existing test was modified to check the fixed behavior described in the \
problem, that is legitimate and NOT over_test

### over_patch (MINOR-SEVERE)
The gold patch contains behavioral code changes beyond what the problem asks for. \
This includes new features, unrelated bug fixes, broader refactoring, or scope \
expansion in the patch itself.

KEY INDICATORS:
- UNRELATED hunk verdicts (behavioral changes, not just imports/whitespace)
- Hunks modifying functions, classes, or files not mentioned in the problem
- The patch "while I'm here" includes opportunistic improvements

IMPORTANT: Pure ANCILLARY changes (imports, __init__.py exports, type annotations, \
whitespace-only changes, docstring updates) do NOT count as over_patch. Only count \
changes that introduce NEW BEHAVIOR beyond the problem scope.

### unclear_description (MINOR)
The problem description is too ambiguous or actively misleading to determine the \
correct solution. Key information is missing, or the description points toward \
the wrong fix.

KEY INDICATORS:
- Ambiguity score >= 0.4
- Multiple valid, incompatible interpretations of the problem
- Missing reproduction steps for a bug report
- Problem suggests an approach that differs from the gold patch
- Vague language ("should work better", "handle edge cases")

### hidden_context (MINOR)
Essential solution information exists ONLY in the hints text (code review comments, \
maintainer decisions) and NOT in the problem description. The problem alone is \
insufficient; the hints contain the actual specification.

KEY INDICATORS:
- Function names, root cause, or design decisions appear only in hints
- The problem is a one-liner but the hints contain detailed requirements
- Problem description references external resources not included in the task

### weak_coverage (MINOR)
The F2P tests or gold patch don't fully cover the stated acceptance criteria. \
A partial or incorrect fix could pass. This makes the task EASIER (not harder) \
— it's a benchmark quality issue, not a fairness issue.

KEY INDICATORS:
- Acceptance criteria items with no corresponding F2P test
- Tests that are too loose (check type but not value)
- Gold patch that leaves some stated requirements unaddressed

### clean
No contamination detected. The task is fair, well-specified, and the tests \
accurately measure whether an agent solved the described problem.

## CLASSIFICATION RULES

1. Assign EVERY label that applies (tasks commonly have multiple labels)
2. If ANY contamination label applies, do NOT assign clean
3. For each label: provide specific evidence and detailed reasoning
4. CITE SPECIFIC EVIDENCE: reference hunk indices, assertion indices, or quote \
problem description text
5. Be precise: distinguish approach_lock (rejects valid alternatives) from \
over_test (tests beyond scope)
6. Do NOT flag pure ancillary changes (imports, whitespace) as over_patch
7. For SWE-bench Pro tasks: consider Requirements + Interface as part of the \
full task specification — behavior described there is NOT excess
8. Consider the heuristic candidates as initial signals to REFINE or OVERRIDE. \
They may be correct, partially correct, or wrong.

## THE 1:1:1 PRINCIPLE (from human audit of 107 SEVERE cases)

- Problem:Test should be approximately 1:1 — tests evaluate what the problem asks
- Problem:Patch should be 1:>=1 — overpatch alone is a quality issue, NOT contamination
- Contamination = tests require code changes not derivable from the problem statement
- over_patch ALONE should NOT be classified as severe — it only becomes severe when \
F2P tests COUPLE to the excess patch hunks (overpatch-overtest coupling)
- A 100-hunk gold patch with 99 unrelated hunks is NOT contaminated if the 1 test \
only exercises the 1 relevant hunk

Key insight from audit: 40% of SEVERE classifications were overturned to CLEAN. \
The most common false positive was flagging tasks with large patches but minimal \
test coupling. Always verify: do the TESTS require the excess code?

## Known Contamination Pattern: Test Assertion Lock
Tests assert on exact naming conventions, internal data structures, enum values, \
or implementation-specific details NOT specified in the problem statement. Example: \
problem says "add stable test identifiers" but tests require exact strings like \
"attachment-list:header:spam-banner:phishing-banner". Any agent using a different \
(equally valid) naming scheme fails.
"""


def _build_task_classifier_user_prompt(
    intent: IntentStatement,
    patch_analysis: PatchAnalysis,
    test_analysis: TestAnalysis,
    description_clarity: DescriptionClarity,
    record: TaskRecord | None = None,
    heuristic_candidates: list[TaskLabelAssignment] | None = None,
    cross_ref: CrossReferenceResult | None = None,
) -> str:
    """Build the user prompt for the LLM task classifier."""
    parts: list[str] = []

    parts.append(f"INSTANCE: {intent.instance_id}")
    parts.append("")

    # Problem statement (full, un-truncated)
    if record and record.problem_statement:
        parts.append("PROBLEM STATEMENT:")
        parts.append(record.problem_statement)
        parts.append("")

    # Requirements (SWE-bench Pro, full)
    if record and record.requirements:
        parts.append("REQUIREMENTS:")
        parts.append(record.requirements)
        parts.append("")

    # Interface (SWE-bench Pro, full)
    if record and record.interface:
        parts.append("INTERFACE:")
        parts.append(record.interface)
        parts.append("")

    # Hints (full)
    if record and record.hints_text:
        parts.append("HINTS TEXT:")
        parts.append(record.hints_text)
        parts.append("")

    # Intent extraction
    parts.append("INTENT EXTRACTION:")
    parts.append(f"- Core requirement: {intent.core_requirement}")
    parts.append(f"- Behavioral contract: {intent.behavioral_contract}")
    parts.append(f"- Acceptance criteria: {json.dumps(intent.acceptance_criteria)}")
    parts.append(f"- Out of scope: {intent.out_of_scope}")
    parts.append(f"- Ambiguity score (raw LLM output, 0–1): {intent.ambiguity_score}")

    if intent.decomposition:
        d = intent.decomposition
        parts.append("")
        parts.append("PROBLEM DECOMPOSITION:")
        parts.append(f"- Bug description: {d.bug_description}")
        if d.suggested_fix:
            parts.append(f"- Reporter's suggested fix: {d.suggested_fix}")
            parts.append("  (Compare this to the gold patch — divergence signals APPROACH_LOCK)")
        parts.append(f"- Legitimacy: {d.legitimacy}")
        entities = []
        if d.mentioned_files:
            entities.append(f"Files: {', '.join(d.mentioned_files)}")
        if d.mentioned_functions:
            entities.append(f"Functions: {', '.join(d.mentioned_functions)}")
        if d.mentioned_classes:
            entities.append(f"Classes: {', '.join(d.mentioned_classes)}")
        if d.mentioned_variables:
            entities.append(f"Variables: {', '.join(d.mentioned_variables)}")
        if d.mentioned_modules:
            entities.append(f"Modules: {', '.join(d.mentioned_modules)}")
        if entities:
            parts.append(f"- Code entities: {'; '.join(entities)}")
    parts.append("")

    # Patch analysis
    parts.append("GOLD PATCH ANALYSIS:")
    parts.append(f"Hunks: {patch_analysis.total_hunks} "
                 f"(REQUIRED={patch_analysis.required_count}, "
                 f"ANCILLARY={patch_analysis.ancillary_count}, "
                 f"UNRELATED={patch_analysis.unrelated_count})")
    for hv in patch_analysis.hunk_verdicts:
        heuristic_tag = " [heuristic]" if hv.is_heuristic else ""
        parts.append(f"  Hunk {hv.hunk_index} [{hv.file_path}]: "
                     f"{hv.verdict.value} [{hv.evidence_strength}]{heuristic_tag} — "
                     f"{hv.reasoning}")
    parts.append("")

    # Test analysis
    parts.append("F2P TEST ANALYSIS:")
    parts.append(f"Tests: {test_analysis.total_tests} "
                 f"(ALIGNED={test_analysis.aligned_count}, "
                 f"TANGENTIAL={test_analysis.tangential_count}, "
                 f"UNRELATED={test_analysis.unrelated_count})")
    parts.append(f"Assertions: {test_analysis.total_assertions} "
                 f"(ON_TOPIC={test_analysis.on_topic_assertions}, "
                 f"OFF_TOPIC={test_analysis.off_topic_assertions})")
    parts.append(f"Has modified tests: {test_analysis.has_modified_tests}")
    for tv in test_analysis.test_verdicts:
        mod_tag = ""
        if tv.is_modified:
            mod_tag = " [MODIFIED pre-existing test"
            if not tv.modification_aligned:
                mod_tag += ", MISALIGNED changes"
            if tv.off_topic_count > 0:
                mod_tag += f", {tv.off_topic_count} OFF_TOPIC assertions"
            mod_tag += "]"
        parts.append(f"  Test '{tv.test_name}': {tv.intent_match.value} "
                     f"[{tv.evidence_strength}]{mod_tag}")
        if tv.reasoning:
            parts.append(f"    Reasoning: {tv.reasoning}")
        for av in tv.assertion_verdicts:
            reason_tag = f" — {av.reason}" if av.reason else ""
            parts.append(f"    [{av.verdict.value}] {av.statement}{reason_tag}")
    parts.append("")

    # Description clarity
    parts.append(f"DESCRIPTION CLARITY: score={description_clarity.score:.4f}")
    if description_clarity.reasoning:
        parts.append(f"  Reasoning: {description_clarity.reasoning}")
    parts.append("")

    if cross_ref and cross_ref.has_coupling:
        parts.append("CROSS-REFERENCE ANALYSIS (OVERPATCH-OVERTEST COUPLING):")
        parts.append(f"Overpatch-overtest couplings detected: {len(cross_ref.couplings)}")
        for cd in cross_ref.couplings:
            parts.append(f"  Test '{cd.test_name}' → UNRELATED hunks {cd.linked_hunk_indices} "
                         f"[{cd.evidence_strength}]")
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
            parts.append(f"  {hc.label.value}: "
                         f"{'; '.join(hc.evidence)}")
        parts.append("")

    return "\n".join(parts)


async def classify_task_labels(
    intent: IntentStatement,
    patch_analysis: PatchAnalysis,
    test_analysis: TestAnalysis,
    description_clarity: DescriptionClarity,
    record: TaskRecord | None = None,
    llm: Any | None = None,
    cross_ref: CrossReferenceResult | None = None,
) -> list[TaskLabelAssignment]:
    """Classify task contamination labels (Axis 1).

    If *llm* is provided, uses LLM for nuanced classification with
    heuristic candidates as guidance.  Otherwise falls back to pure
    heuristic classification.
    """
    heuristic = _heuristic_labels(intent, patch_analysis, test_analysis,
                                  description_clarity, record, cross_ref)

    if llm is None:
        # Pure heuristic fallback
        if not heuristic:
            return [TaskLabelAssignment(
                label=TaskContaminationLabel.CLEAN,
                evidence=["No heuristic signals detected"],
            )]
        return heuristic

    # Build LLM prompt
    user_prompt = _build_task_classifier_user_prompt(
        intent, patch_analysis, test_analysis, description_clarity, record, heuristic,
        cross_ref=cross_ref,
    )

    try:
        result: TaskClassificationResponse = await llm.query_structured(
            system_prompt=TASK_CLASSIFIER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=TaskClassificationResponse,
        )
        labels: list[TaskLabelAssignment] = []
        for item in result.labels:
            try:
                label_enum = TaskContaminationLabel(item.label)
            except ValueError:
                logger.warning("Unknown label from LLM: %s", item.label)
                continue
            labels.append(TaskLabelAssignment(
                label=label_enum,
                evidence=item.evidence,
                reasoning=item.reasoning,
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
                evidence=["LLM found no contamination signals"],
            )]
        return labels

    except Exception:
        logger.exception("LLM classification failed; falling back to heuristics")
        if not heuristic:
            return [TaskLabelAssignment(
                label=TaskContaminationLabel.CLEAN,
                evidence=["Heuristic fallback — no signals"],
            )]
        return heuristic

