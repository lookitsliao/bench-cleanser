"""Stage 4A: Gold patch intent matching (batched).

All hunks in the gold patch are classified as REQUIRED, ANCILLARY, or
UNRELATED in a SINGLE batched LLM call against the intent from Stage 2.
Structural context from Stage 3 is included when available.

Uses structured output with strict JSON schema enforcement.
No regex heuristics — all classification goes through the LLM.
"""

from __future__ import annotations

import logging

from bench_cleanser.llm_client import LLMClient
from bench_cleanser.models import (
    PatchAnalysis,
    HunkVerdict,
    IntentStatement,
    ParsedTask,
    PatchHunk,
    PatchVerdict,
    StructuralDiff,
)
from bench_cleanser.schemas import BatchPatchVerdictsResponse

logger = logging.getLogger(__name__)

BATCH_PATCH_SYSTEM_PROMPT = """\
You are an expert software engineer performing **intent matching** between a \
problem description and a gold (reference) code patch from a software benchmark.

## YOUR MISSION

You will receive the COMPLETE intent extracted from the problem statement and \
ALL hunks from the gold patch at once. Your job is to classify EVERY hunk in \
a single pass, producing a verdict for each.

## CLASSIFICATION TAXONOMY

For each hunk, assign one of three verdicts:

### REQUIRED
The change DIRECTLY implements behavior described in the acceptance criteria. \
A correct solution MUST include this change (or a semantically equivalent one). \
If removing this hunk would break at least one acceptance criterion, it is REQUIRED.

Indicators of REQUIRED:
- modifies the function/class/module responsible for the buggy behavior
- implements the core logic that produces the new correct output
- fixes the exception path or error handling described in the problem
- is the minimal code change needed to satisfy an acceptance criterion

### ANCILLARY
The change supports the fix but is NOT described in the problem statement. \
It is reasonable infrastructure that a developer might need for their fix. \
NOT harmful, but NOT demanded by the acceptance criteria.

Indicators of ANCILLARY:
- import statements needed for REQUIRED changes
- __init__.py export additions for new modules/classes
- type annotations or type stubs
- configuration changes (settings, manifests)
- whitespace-only refactoring within the same function
- docstring updates describing the new behavior

### UNRELATED
The change modifies behavior NOT described in the problem and NOT required \
to support the fix. This is code that goes beyond the problem scope — new \
features, fixes for unrelated bugs, broader refactoring, documentation for \
other features, changelog entries.

Indicators of UNRELATED:
- changes to files, functions, or classes not mentioned in the problem
- introduces new functionality beyond acceptance criteria
- changelog/release notes entries (these describe, not implement)
- documentation changes for features unrelated to the bug
- refactoring of code paths not relevant to the acceptance criteria
- test infrastructure changes (conftest.py, test utilities) unrelated to the fix

## ANALYSIS GUIDELINES

1. Start by carefully reading ALL acceptance criteria and the out-of-scope statement
2. For each hunk, trace causality: "Does removing this hunk break any acceptance criterion?"
3. When analyzing hunks together: consider whether hunk A is only REQUIRED because \
hunk B introduces new behavior not in the problem. If so, both may be UNRELATED.
4. Infrastructure changes (imports, __init__.py) are ANCILLARY, not UNRELATED — \
they are normal development overhead
5. Changes to documentation/changelog files are almost always UNRELATED
6. When uncertain between REQUIRED and ANCILLARY, prefer REQUIRED (conservative)
7. When uncertain between ANCILLARY and UNRELATED, prefer ANCILLARY (conservative)
8. Consider the STRUCTURAL CONTEXT when available — the full function source \
before the patch helps you understand what is being changed and why

## IMPORTANT: BATCH ANALYSIS

You are seeing ALL hunks at once to enable cross-hunk reasoning. Take advantage:
- A hunk might be REQUIRED only because it supports another REQUIRED hunk
- Multiple UNRELATED hunks in different files may form a coherent but out-of-scope \
feature addition — classify them as a group
- Consider whether the patch as a whole exceeds the scope, or whether each hunk \
individually is justified

Provide one verdict per hunk, referencing the hunk by its index.
"""


def _build_batch_patch_prompt(
    intent: IntentStatement,
    hunks: list[PatchHunk],
    structural_diff: StructuralDiff | None = None,
) -> str:
    """Build user prompt with all hunks for batch classification."""
    parts: list[str] = []

    # Intent section
    parts.append(
        "=== INTENT (from problem statement only — no gold patch was seen) ===\n"
        f"Core requirement: {intent.core_requirement}\n\n"
        f"Behavioral contract: {intent.behavioral_contract}\n\n"
        "Acceptance criteria:\n"
        + "\n".join(f"  {i+1}. {c}" for i, c in enumerate(intent.acceptance_criteria)) + "\n\n"
        f"Out of scope: {intent.out_of_scope}"
    )

    if intent.decomposition:
        d = intent.decomposition
        parts.append(
            "=== PROBLEM DECOMPOSITION ===\n"
            f"Bug description: {d.bug_description}\n"
            f"Reporter's suggested fix: {d.suggested_fix or '(none)'}\n"
            f"Legitimacy: {d.legitimacy}"
        )

    # All hunks
    for i, hunk in enumerate(hunks):
        hunk_section = (
            f"=== HUNK {i} ===\n"
            f"File: {hunk.file_path}\n"
            f"Function context: {hunk.function_context}\n"
            f"Is test file: {hunk.is_test_file}\n"
            f"Is __init__.py: {hunk.is_init_file}\n"
            f"Is doc/changelog: {hunk.is_doc_file}\n"
            f"Lines added: {len(hunk.added_lines)}\n"
            f"Lines removed: {len(hunk.removed_lines)}\n\n"
            f"Diff:\n{hunk.raw_diff}"
        )

        # Add structural context if available
        if structural_diff:
            for cb in structural_diff.changed_blocks:
                if cb.file_path == hunk.file_path and cb.pre_source:
                    hunk_section += (
                        f"\n\nFull function source (pre-patch):\n"
                        f"--- {cb.block_name} ({cb.block_type}, {cb.edit_status}) ---\n"
                        f"{cb.pre_source}"
                    )

        parts.append(hunk_section)

    return "\n\n".join(parts)


async def analyze_patch(
    parsed: ParsedTask,
    intent: IntentStatement,
    llm: LLMClient,
    structural_diff: StructuralDiff | None = None,
) -> PatchAnalysis:
    """Stage 4A: classify all gold patch hunks against intent in a single batched LLM call."""
    if not parsed.patch_hunks:
        return PatchAnalysis(
            total_hunks=0, required_count=0,
            ancillary_count=0, unrelated_count=0,
        )

    user_prompt = _build_batch_patch_prompt(
        intent, parsed.patch_hunks, structural_diff,
    )

    result: BatchPatchVerdictsResponse = await llm.query_structured(
        BATCH_PATCH_SYSTEM_PROMPT,
        user_prompt,
        BatchPatchVerdictsResponse,
    )

    # Map results to HunkVerdict objects
    hunk_verdicts: list[HunkVerdict] = []
    result_by_index = {v.hunk_index: v for v in result.verdicts}

    for i, hunk in enumerate(parsed.patch_hunks):
        verdict_item = result_by_index.get(i)
        if verdict_item is None:
            logger.warning(
                "Missing verdict for hunk %d (%s) — defaulting to ANCILLARY",
                i, hunk.file_path,
            )
            hunk_verdicts.append(HunkVerdict(
                hunk_index=i, file_path=hunk.file_path,
                verdict=PatchVerdict.ANCILLARY, evidence_strength="weak",
                reasoning="No verdict returned by LLM for this hunk",
            ))
            continue

        try:
            verdict = PatchVerdict(verdict_item.verdict)
        except ValueError:
            verdict = PatchVerdict.ANCILLARY

        hunk_verdicts.append(HunkVerdict(
            hunk_index=i, file_path=hunk.file_path,
            verdict=verdict, evidence_strength=verdict_item.evidence_strength,
            reasoning=verdict_item.reasoning,
        ))

    required = sum(1 for v in hunk_verdicts if v.verdict == PatchVerdict.REQUIRED)
    ancillary = sum(1 for v in hunk_verdicts if v.verdict == PatchVerdict.ANCILLARY)
    unrelated = sum(1 for v in hunk_verdicts if v.verdict == PatchVerdict.UNRELATED)

    return PatchAnalysis(
        total_hunks=len(hunk_verdicts),
        required_count=required,
        ancillary_count=ancillary,
        unrelated_count=unrelated,
        hunk_verdicts=hunk_verdicts,
    )
