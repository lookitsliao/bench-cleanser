"""Stage 2: LLM-based scope analysis of problem statements.

The LLM analyzes the problem_statement WITHOUT seeing the gold patch to
determine what the task actually asks for.  This prevents anchoring bias.
"""

from __future__ import annotations

import logging

from bench_cleanser.llm_client import LLMClient
from bench_cleanser.models import ScopeAnalysis, TaskRecord

logger = logging.getLogger(__name__)

SCOPE_SYSTEM_PROMPT = """\
You are an expert software engineer analyzing a bug report / feature request
from an open-source project.  Your job is to determine EXACTLY what the task
asks the developer to do — nothing more, nothing less.

You will be given:
  - The repository name
  - The instance_id (for reference)
  - The problem statement (bug report, issue description, or PR description)

IMPORTANT: You have NOT been shown the gold patch. Do NOT speculate about
what the fix looks like.  Focus only on what the problem statement says.

Think through this step by step:
1. Read the problem statement carefully and identify the core bug or feature request.
2. List every component, file, or module explicitly mentioned.
3. Determine the precise behavioral change being requested.
4. Identify what is explicitly NOT being asked for.
5. Assess how clear and unambiguous the specification is.

Respond in JSON with these keys:
{
  "core_requirement": "<one-paragraph description of what the task asks>",
  "affected_components": ["<list of files, modules, or subsystems mentioned>"],
  "behavioral_contract": "<what behavior should change, and how>",
  "out_of_scope": "<things NOT asked for: refactors, style changes, unrelated features>",
  "ambiguity_score": <float 0.0-1.0, where 0 = perfectly clear, 1 = very ambiguous>
}
"""


def _build_user_prompt(record: TaskRecord) -> str:
    """Build the user prompt for scope analysis."""
    return (
        f"Repository: {record.repo}\n"
        f"Instance ID: {record.instance_id}\n\n"
        f"Problem Statement:\n{record.problem_statement}\n"
    )


async def analyze_scope(
    record: TaskRecord,
    llm: LLMClient,
) -> ScopeAnalysis:
    """Run Stage 2 scope analysis on a single task.

    The LLM is given ONLY the problem_statement (never the gold patch)
    and asked to determine the task scope.
    """
    user_prompt = _build_user_prompt(record)

    # Retry up to 2 extra times if the LLM returns empty or missing fields
    max_scope_attempts = 3
    result: dict = {}
    for attempt in range(1, max_scope_attempts + 1):
        result = await llm.query_json(
            SCOPE_SYSTEM_PROMPT,
            user_prompt,
            skip_cache=(attempt > 1),
        )

        if result and result.get("core_requirement"):
            break

        logger.warning(
            "Scope analysis attempt %d/%d for %s returned empty/incomplete: %s",
            attempt,
            max_scope_attempts,
            record.instance_id,
            result,
        )
        result = {}

    if not result or not result.get("core_requirement"):
        logger.error(
            "All scope analysis attempts failed for %s — using fallback",
            record.instance_id,
        )
        return ScopeAnalysis(
            instance_id=record.instance_id,
            core_requirement="",
            affected_components=[],
            behavioral_contract="",
            out_of_scope="",
            ambiguity_score=1.0,
            raw_llm_response="",
        )

    return ScopeAnalysis(
        instance_id=record.instance_id,
        core_requirement=result.get("core_requirement", ""),
        affected_components=result.get("affected_components", []),
        behavioral_contract=result.get("behavioral_contract", ""),
        out_of_scope=result.get("out_of_scope", ""),
        ambiguity_score=float(result.get("ambiguity_score", 0.5)),
        raw_llm_response=str(result),
    )
