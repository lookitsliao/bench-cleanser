"""Stage 2: Intent extraction and problem decomposition.

The LLM analyzes the problem_statement WITHOUT seeing the gold patch to:
1. Extract acceptance criteria (intent)
2. Decompose the problem into bug / suggested fix / legitimacy
3. Identify specific code entities (files, functions, classes, variables)
"""

from __future__ import annotations

import logging

from bench_cleanser.llm_client import LLMClient
from bench_cleanser.models import IntentStatement, ProblemDecomposition, TaskRecord

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """\
You are an expert software engineer analyzing a bug report / feature request
from an open-source project.  Your job is to determine EXACTLY what the task
asks the developer to do — nothing more, nothing less.

You will be given:
  - The repository name
  - The instance_id (for reference)
  - The problem statement (bug report, issue description, or PR description)
  - Optionally, a Requirements section with detailed implementation requirements
  - Optionally, an Interface section describing new public interfaces

IMPORTANT: You have NOT been shown any code patch.  Do NOT speculate about
what the fix looks like.  Focus ONLY on what the problem statement,
requirements, and interface sections say.

Think through this carefully:

1. **Core requirement**: What is the ONE primary bug or feature being reported?
   Be precise — do not inflate the scope.

2. **Behavioral contract**: What observable behavior should change after the fix?
   Describe the BEFORE vs AFTER state concretely.

3. **Acceptance criteria**: List EACH specific, testable behavior that the
   problem description explicitly asks for.  These must be things a test could
   verify.  Only include behaviors that are DIRECTLY STATED or CLEARLY IMPLIED
   by the problem statement.  Do NOT extrapolate.

   Good examples:
   - "modelform_factory should preserve formfield_callback from Meta"
   - "minversion('1.0.dev1') should return True"

   Bad examples (over-extrapolation):
   - "All forms should inherit all attributes from parents"
   - "All version comparison functions should handle dev tags"

4. **Out of scope**: What behaviors, features, or refactors are NOT asked for?
   Be explicit about what the description does NOT request.

5. **Ambiguity score**: How clear is the specification?
   - 0.0 = perfectly clear, single valid interpretation
   - 0.3 = mostly clear, minor edge cases undefined
   - 0.5 = moderately ambiguous, multiple reasonable interpretations
   - 0.7 = significantly ambiguous, scope could vary widely
   - 1.0 = extremely vague, almost anything could be in scope

6. **Problem decomposition**: Separate the problem into three parts:
   - **bug_description**: What is actually broken? The observable defect or
     missing capability. Stick to the symptom and reproduction steps.
   - **suggested_fix**: If the reporter suggests HOW to fix it (specific
     approach, method, class to change), capture that separately.  Many reporters
     suggest a fix that differs from the actual gold patch — this is valuable
     signal for APPROACH_LOCK detection.  If no suggestion, use empty string.
   - **legitimacy**: Is this a genuine bug report, a feature request, a
     discussion, or something else? Values: "bug", "feature_request",
     "enhancement", "question", "discussion", "unclear".

7. **Code entities**: Extract ALL specific code entities mentioned in the
   problem statement. Be precise — only include identifiers that appear
   literally in the text.
   - **files**: File paths (e.g., "django/forms/models.py", "tests/test_foo.py")
   - **functions**: Function or method names (e.g., "modelform_factory", "__str__")
   - **classes**: Class names (e.g., "ModelForm", "Duration")
   - **variables**: Variable, attribute, or setting names (e.g., "formfield_callback", "USE_TZ")
   - **modules**: Module or package names (e.g., "django.forms", "astropy.units")

Respond in JSON with these keys:
{
  "core_requirement": "<one-sentence description of the primary bug/feature>",
  "behavioral_contract": "<concrete BEFORE vs AFTER behavior change>",
  "acceptance_criteria": ["<specific testable behavior 1>", "<specific testable behavior 2>", ...],
  "out_of_scope": "<things NOT asked for, even if related>",
  "ambiguity_score": <float 0.0-1.0>,
  "bug_description": "<what is actually broken — symptom only>",
  "suggested_fix": "<reporter's suggested approach, or empty string>",
  "legitimacy": "<bug|feature_request|enhancement|question|discussion|unclear>",
  "mentioned_files": ["<file path 1>", ...],
  "mentioned_functions": ["<function name 1>", ...],
  "mentioned_classes": ["<class name 1>", ...],
  "mentioned_variables": ["<variable name 1>", ...],
  "mentioned_modules": ["<module name 1>", ...]
}
"""


def _build_user_prompt(record: TaskRecord) -> str:
    parts = [
        f"Repository: {record.repo}",
        f"Instance ID: {record.instance_id}",
        "",
        f"Problem Statement:\n{record.problem_statement}",
    ]
    if record.requirements:
        parts.append(f"\nRequirements:\n{record.requirements}")
    if record.interface:
        parts.append(f"\nInterface:\n{record.interface}")
    return "\n".join(parts) + "\n"


async def extract_intent(
    record: TaskRecord,
    llm: LLMClient,
) -> IntentStatement:
    """Stage 2: extract intent and decompose problem statement.

    The LLM is given ONLY the problem_statement (never the gold patch).
    Returns an IntentStatement with acceptance criteria and a
    ProblemDecomposition with entity tracking.
    """
    user_prompt = _build_user_prompt(record)

    max_attempts = 3
    result: dict = {}
    for attempt in range(1, max_attempts + 1):
        result = await llm.query_json(
            INTENT_SYSTEM_PROMPT, user_prompt,
            skip_cache=(attempt > 1),
        )
        if result and result.get("core_requirement") and result.get("acceptance_criteria"):
            break
        logger.warning(
            "Intent extraction attempt %d/%d for %s returned incomplete",
            attempt, max_attempts, record.instance_id,
        )
        result = {}

    if not result or not result.get("core_requirement"):
        raise RuntimeError(
            f"Intent extraction failed for {record.instance_id} after {max_attempts} attempts"
        )

    decomposition = ProblemDecomposition(
        bug_description=result.get("bug_description", ""),
        suggested_fix=result.get("suggested_fix", ""),
        legitimacy=result.get("legitimacy", "unclear"),
        mentioned_files=result.get("mentioned_files", []),
        mentioned_functions=result.get("mentioned_functions", []),
        mentioned_classes=result.get("mentioned_classes", []),
        mentioned_variables=result.get("mentioned_variables", []),
        mentioned_modules=result.get("mentioned_modules", []),
    )

    return IntentStatement(
        instance_id=record.instance_id,
        core_requirement=result.get("core_requirement", ""),
        behavioral_contract=result.get("behavioral_contract", ""),
        acceptance_criteria=result.get("acceptance_criteria", []),
        out_of_scope=result.get("out_of_scope", ""),
        ambiguity_score=float(result.get("ambiguity_score", 0.5)),
        raw_llm_response=str(result),
        decomposition=decomposition,
    )
