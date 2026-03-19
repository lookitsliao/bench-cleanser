"""Stage 4A: Gold patch intent matching.

Each hunk in the gold patch is classified as REQUIRED, ANCILLARY, or
UNRELATED by comparing it against the intent extracted in Stage 2.
Structural context from Stage 3 is included when available.
"""

from __future__ import annotations

import logging

from bench_cleanser.llm_client import LLMClient
from bench_cleanser.models import (
    ExcessPatchDetail,
    HunkVerdict,
    IntentStatement,
    ParsedTask,
    PatchHunk,
    PatchVerdict,
    StructuralDiff,
)
from bench_cleanser.parsing.patch_parser import hunk_is_import_only

logger = logging.getLogger(__name__)

PATCH_INTENT_SYSTEM_PROMPT = """\
You are an expert software engineer performing **intent matching** between a
problem description and a code change.

You are given:
1. The **intent** extracted from the problem statement — including core
   requirement, behavioral contract, acceptance criteria, and out-of-scope.
2. A single hunk from the gold (reference) patch with its diff.
3. Optionally, the full source of the function/class being modified (from
   structural analysis).

Classify this hunk as one of:

  **REQUIRED**: The change directly implements behavior described in the
    acceptance criteria.  A correct solution MUST include this change (or an
    equivalent).

  **ANCILLARY**: The change supports the fix but is NOT described in the
    problem.  Reasonable infrastructure.  Examples: imports, __init__.py
    exports, type annotations, configuration.

  **UNRELATED**: The change modifies behavior NOT described in the problem
    and NOT required to support the fix.  Examples: refactoring other code,
    fixing unrelated bugs, adding unrelated features, documentation changes.

Guidelines:
- Focus on ACCEPTANCE CRITERIA — each is a specific testable behavior.
- A hunk is REQUIRED only if removing it would break an acceptance criterion.
- Infrastructure changes (imports, __init__.py) are ANCILLARY, not UNRELATED.
- When uncertain REQUIRED vs ANCILLARY, prefer REQUIRED.
- When uncertain ANCILLARY vs UNRELATED, prefer ANCILLARY.

Respond in JSON:
{
  "verdict": "REQUIRED|ANCILLARY|UNRELATED",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation citing specific acceptance criteria>"
}
"""


def _apply_heuristics(hunk: PatchHunk) -> HunkVerdict | None:
    if hunk.is_init_file and hunk_is_import_only(hunk):
        return HunkVerdict(
            hunk_index=hunk.hunk_index, file_path=hunk.file_path,
            verdict=PatchVerdict.ANCILLARY, confidence=0.95,
            reasoning="__init__.py hunk with only import/export changes",
            is_heuristic=True,
        )
    if hunk.is_doc_file:
        return HunkVerdict(
            hunk_index=hunk.hunk_index, file_path=hunk.file_path,
            verdict=PatchVerdict.UNRELATED, confidence=0.90,
            reasoning="Change in documentation/changelog file",
            is_heuristic=True,
        )
    return None


def _build_intent_hunk_prompt(
    intent: IntentStatement,
    hunk: PatchHunk,
    structural_context: str = "",
) -> str:
    parts: list[str] = []
    parts.append(
        "=== INTENT (from problem statement only) ===\n"
        f"Core requirement: {intent.core_requirement}\n"
        f"Behavioral contract: {intent.behavioral_contract}\n"
        "Acceptance criteria:\n"
        + "\n".join(f"  - {c}" for c in intent.acceptance_criteria) + "\n"
        f"Out of scope: {intent.out_of_scope}"
    )
    parts.append(
        "=== PATCH HUNK ===\n"
        f"File: {hunk.file_path}\n"
        f"Function context: {hunk.function_context}\n"
        f"Lines added: {len(hunk.added_lines)}\n"
        f"Lines removed: {len(hunk.removed_lines)}\n\n"
        f"Diff:\n{hunk.raw_diff}"
    )
    if structural_context:
        parts.append("=== STRUCTURAL CONTEXT (full function source) ===\n" + structural_context)
    return "\n\n".join(parts)


async def _classify_hunk(
    hunk: PatchHunk,
    intent: IntentStatement,
    llm: LLMClient,
    structural_diff: StructuralDiff | None = None,
) -> HunkVerdict:
    heuristic = _apply_heuristics(hunk)
    if heuristic is not None:
        return heuristic

    structural_context = ""
    if structural_diff:
        for cb in structural_diff.changed_blocks:
            if cb.file_path == hunk.file_path and cb.pre_source:
                structural_context += f"--- {cb.block_name} ({cb.block_type}, {cb.edit_status}) ---\n"
                structural_context += cb.pre_source + "\n\n"

    user_prompt = _build_intent_hunk_prompt(intent, hunk, structural_context)
    result = await llm.query_json(PATCH_INTENT_SYSTEM_PROMPT, user_prompt)

    verdict_str = result.get("verdict", "ANCILLARY")
    try:
        verdict = PatchVerdict(verdict_str)
    except ValueError:
        verdict = PatchVerdict.ANCILLARY

    return HunkVerdict(
        hunk_index=hunk.hunk_index, file_path=hunk.file_path,
        verdict=verdict, confidence=float(result.get("confidence", 0.5)),
        reasoning=result.get("reasoning", ""), is_heuristic=False,
    )


async def analyze_patch(
    parsed: ParsedTask,
    intent: IntentStatement,
    llm: LLMClient,
    structural_diff: StructuralDiff | None = None,
) -> ExcessPatchDetail:
    """Stage 4A: classify each gold patch hunk against extracted intent."""
    hunk_verdicts: list[HunkVerdict] = []
    for hunk in parsed.patch_hunks:
        verdict = await _classify_hunk(hunk, intent, llm, structural_diff)
        hunk_verdicts.append(verdict)

    required = sum(1 for v in hunk_verdicts if v.verdict == PatchVerdict.REQUIRED)
    ancillary = sum(1 for v in hunk_verdicts if v.verdict == PatchVerdict.ANCILLARY)
    unrelated = sum(1 for v in hunk_verdicts if v.verdict == PatchVerdict.UNRELATED)

    return ExcessPatchDetail(
        total_hunks=len(hunk_verdicts),
        required_count=required,
        ancillary_count=ancillary,
        unrelated_count=unrelated,
        hunk_verdicts=hunk_verdicts,
    )
