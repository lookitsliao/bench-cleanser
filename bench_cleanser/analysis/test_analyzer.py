"""Stage 4B: F2P test intent matching.

Each F2P test is classified as ALIGNED, TANGENTIAL, or UNRELATED relative
to the intent extracted in Stage 2.  Individual assertions get ON_TOPIC or
OFF_TOPIC verdicts.  Code context from Stage 1.5 and structural analysis
from Stage 3 enrich the LLM prompt.
"""

from __future__ import annotations

import ast
import logging
import re

from bench_cleanser.llm_client import LLMClient
from bench_cleanser.models import (
    AssertionVerdict,
    AssertionVerdictReport,
    ExcessTestDetail,
    IntentStatement,
    ParsedTask,
    StructuralDiff,
    TestHunk,
    TestModificationType,
    TestVerdict,
    TestVerdictReport,
)

logger = logging.getLogger(__name__)

TEST_INTENT_SYSTEM_PROMPT = """\
You are an expert software engineer performing **intent matching** between a
problem description and a test function.

You are given:
1. The **intent** extracted from the problem statement — including core
   requirement, behavioral contract, acceptance criteria, and out-of-scope.
2. The full source of an F2P (fail-to-pass) test function.
3. A list of assertions extracted from the test, numbered for reference.
4. Whether the test is NEW (added by the patch) or MODIFIED (existed before).
5. Optionally, structural context (call graph, changed functions).
6. Optionally, full pre-patch and post-patch test source with code context.

**PART 1 — Test-level verdict:**

  **ALIGNED**: The test targets the described problem.  Its primary purpose
    is to verify behavior from the acceptance criteria.

  **TANGENTIAL**: The test partially targets the problem but includes
    significant behavior beyond the acceptance criteria.

  **UNRELATED**: The test does not target the described problem at all.

**PART 2 — Per-assertion verdicts:**
For EACH assertion (by index):

  **ON_TOPIC**: Checks behavior described in the acceptance criteria.

  **OFF_TOPIC**: Checks behavior NOT described in the problem statement.

**PART 3 — Modification analysis (for MODIFIED tests only):**
If the test was MODIFIED from a pre-existing test, assess whether the
modifications are aligned with the acceptance criteria.  A modification
that adds assertions on behavior NOT described in the problem — while
the test looks legitimate because it existed before — is a significant
contamination signal.  Only flag `is_modification_aligned: false` when
the modifications themselves are MISALIGNED with the problem statement.

Guidelines:
- Focus on ACCEPTANCE CRITERIA.
- An assertion is ON_TOPIC only if it verifies at least one criterion.
- Be conservative — if behavior is plausible but not described, OFF_TOPIC.

Respond in JSON:
{
  "test_verdict": "ALIGNED|TANGENTIAL|UNRELATED",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<concise explanation>",
  "is_modification_aligned": <bool>,
  "assertion_verdicts": [
    {"index": 0, "verdict": "ON_TOPIC|OFF_TOPIC", "reason": "<brief>"},
    ...
  ]
}
"""


def _count_assertions(source: str) -> tuple[int, list[str]]:
    """Count assert statements in test source via AST parsing.

    Falls back to multi-language regex matching when AST parsing fails
    (i.e., for non-Python languages like Go, JS/TS, Ruby, Rust, Java).
    """
    lines = []
    for line in source.splitlines():
        clean = line
        if clean.startswith("+"):
            clean = clean[1:]
        lines.append(clean)
    cleaned = "\n".join(lines)

    assertions: list[str] = []
    try:
        tree = ast.parse(cleaned)
    except SyntaxError:
        # Multi-language assertion pattern matching
        _ASSERTION_PATTERNS = [
            # Python: assert, self.assert*
            re.compile(r"^\s*(assert\b.+)"),
            re.compile(r"^\s*(self\.assert\w+\(.+)"),
            # Go testify: assert.*, require.*
            re.compile(r"^\s*(assert\.\w+\(.+)"),
            re.compile(r"^\s*(require\.\w+\(.+)"),
            # Go stdlib: t.Error, t.Fatal, t.Log + if-based checks
            re.compile(r"^\s*(t\.(?:Error|Errorf|Fatal|Fatalf|Fail|FailNow)\(.+)"),
            # JavaScript/TypeScript: expect(...), chai assert
            re.compile(r"^\s*(expect\(.+)"),
            re.compile(r"^\s*(assert\.\w+\(.+)"),
            # Ruby: assert_*, expect(...).to
            re.compile(r"^\s*(assert_\w+.+)"),
            re.compile(r"^\s*(expect\(.+\.to\b.+)"),
            # Rust: assert!, assert_eq!, assert_ne!
            re.compile(r"^\s*(assert(?:_eq|_ne)?!\(.+)"),
            # Java: Assert.*, assertEquals, assertTrue, etc.
            re.compile(r"^\s*(Assert\.\w+\(.+)"),
            re.compile(r"^\s*(assert(?:Equals|True|False|NotNull|Null|That|Throws)\(.+)"),
            # C#: Assert.*
            re.compile(r"^\s*(Assert\.\w+\(.+)"),
        ]
        for line in lines:
            stripped = line.strip()
            for pattern in _ASSERTION_PATTERNS:
                m = pattern.match(stripped)
                if m:
                    assertions.append(m.group(1))
                    break
        return len(assertions), assertions

    UNITTEST_ASSERT_METHODS = {
        "assertEqual", "assertRaises", "assertTrue", "assertFalse",
        "assertIn", "assertNotIn", "assertIsNone", "assertIsNotNone",
        "assertAlmostEqual", "assertGreater", "assertLess", "assertRegex",
        "assertNotEqual", "assertIs", "assertIsNot", "assertCountEqual",
        "assertSequenceEqual", "assertListEqual", "assertDictEqual",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            try:
                assertions.append(ast.unparse(node))
            except Exception:
                assertions.append(f"assert at line {node.lineno}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name.startswith("assert") or name in UNITTEST_ASSERT_METHODS:
                try:
                    assertions.append(ast.unparse(node))
                except Exception:
                    assertions.append(f"{name}() at line {node.lineno}")

    return len(assertions), assertions


def _truncate(text: str, max_lines: int = 500) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n[...truncated, {len(lines) - max_lines} more lines...]"


def _build_test_intent_prompt(
    intent: IntentStatement,
    test_hunk: TestHunk,
    assertions: list[str],
    structural_context: str = "",
    problem_statement: str = "",
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

    if problem_statement:
        parts.append(f"=== PROBLEM STATEMENT ===\n{_truncate(problem_statement, max_lines=100)}")

    parts.append(
        "=== TEST METADATA ===\n"
        f"File: {test_hunk.file_path}\n"
        f"Test name: {test_hunk.test_name}\n"
        f"Test ID: {test_hunk.full_test_id}\n"
        f"Modification type: {test_hunk.modification_type.value}"
    )

    ctx = test_hunk.code_context
    if ctx and ctx.pre_patch_test_source:
        parts.append(f"=== PRE-PATCH TEST (before this PR) ===\n{_truncate(ctx.pre_patch_test_source)}")

    parts.append(f"=== POST-PATCH TEST SOURCE ===\n{_truncate(test_hunk.full_source)}")

    if assertions:
        assert_lines = [f"  [{i}] {a}" for i, a in enumerate(assertions)]
        parts.append("=== ASSERTIONS (number each verdict by index) ===\n" + "\n".join(assert_lines))

    if ctx:
        if ctx.tested_functions:
            tf_parts: list[str] = []
            for tf in ctx.tested_functions:
                entry = f"Function: {tf.name} (file: {tf.file_path}, patch: {'YES' if tf.is_modified_by_patch else 'NO'})\n"
                if tf.source:
                    entry += f"Source:\n{_truncate(tf.source)}"
                tf_parts.append(entry)
            parts.append("=== TESTED SOURCE CODE ===\n" + "\n\n---\n".join(tf_parts))

        if ctx.call_targets:
            call_lines = []
            for ct in ctx.call_targets:
                tag = "IN GOLD PATCH" if ct.is_in_patch else "not in patch"
                loc = f" in {ct.file_path}" if ct.file_path else ""
                call_lines.append(f"  - {ct.name}{loc} ({tag})")
            parts.append("=== CALL ANALYSIS ===\nFunctions called by this test:\n" + "\n".join(call_lines))

    if structural_context:
        parts.append("=== STRUCTURAL CONTEXT ===\n" + structural_context)

    return "\n\n".join(parts)


async def _analyze_test(
    test_hunk: TestHunk,
    intent: IntentStatement,
    llm: LLMClient,
    structural_diff: StructuralDiff | None = None,
    problem_statement: str = "",
) -> TestVerdictReport:
    is_modified = test_hunk.modification_type == TestModificationType.MODIFIED

    _count, assertion_strs = _count_assertions(test_hunk.full_source)

    structural_context = ""
    if structural_diff:
        for edge_test, edge_func in structural_diff.call_edges:
            if edge_test == test_hunk.test_name:
                for cb in structural_diff.changed_blocks:
                    if cb.block_name == edge_func:
                        structural_context += (
                            f"Calls -> {cb.block_name} ({cb.block_type}, {cb.edit_status}) "
                            f"in {cb.file_path}\n"
                        )

    user_prompt = _build_test_intent_prompt(
        intent, test_hunk, assertion_strs,
        structural_context=structural_context,
        problem_statement=problem_statement,
    )

    ctx = test_hunk.code_context
    if ctx:
        logger.info(
            "Test %s: %d tested funcs, %d calls, pre=%s, post=%s",
            test_hunk.test_name, len(ctx.tested_functions), len(ctx.call_targets),
            "yes" if ctx.pre_patch_test_source else "no",
            "yes" if ctx.post_patch_test_source else "no",
        )

    result = await llm.query_json(TEST_INTENT_SYSTEM_PROMPT, user_prompt)

    verdict_str = result.get("test_verdict", "TANGENTIAL")
    try:
        test_verdict = TestVerdict(verdict_str)
    except ValueError:
        test_verdict = TestVerdict.TANGENTIAL

    assertion_verdicts: list[AssertionVerdictReport] = []
    raw_verdicts = result.get("assertion_verdicts", [])
    for i, assertion_str in enumerate(assertion_strs):
        av = AssertionVerdict.ON_TOPIC
        reason = ""
        for rv in raw_verdicts:
            if rv.get("index") == i:
                try:
                    av = AssertionVerdict(rv.get("verdict", "ON_TOPIC"))
                except ValueError:
                    av = AssertionVerdict.ON_TOPIC
                reason = rv.get("reason", "")
                break
        assertion_verdicts.append(AssertionVerdictReport(statement=assertion_str, verdict=av, reason=reason))

    modification_aligned = result.get("is_modification_aligned", True)

    return TestVerdictReport(
        test_id=test_hunk.full_test_id, test_name=test_hunk.test_name,
        intent_match=test_verdict, confidence=float(result.get("confidence", 0.5)),
        reasoning=result.get("reasoning", ""), is_modified=is_modified,
        modification_aligned=modification_aligned, assertion_verdicts=assertion_verdicts,
    )


async def _analyze_unmatched_test(test_id: str, intent: IntentStatement) -> TestVerdictReport:
    parts = test_id.split("::")
    test_name = parts[-1].split("[")[0] if parts else test_id
    return TestVerdictReport(
        test_id=test_id, test_name=test_name,
        intent_match=TestVerdict.ALIGNED, confidence=0.3,
        reasoning="F2P test with no matching hunk — test was not modified, likely exercises gold patch behavior",
        is_modified=False, modification_aligned=True, assertion_verdicts=[],
    )


async def analyze_tests(
    parsed: ParsedTask,
    intent: IntentStatement,
    llm: LLMClient,
    structural_diff: StructuralDiff | None = None,
) -> ExcessTestDetail:
    """Stage 4B: classify each F2P test against extracted intent."""
    test_verdicts: list[TestVerdictReport] = []
    problem_statement = parsed.record.full_problem_context

    for test_hunk in parsed.f2p_test_hunks:
        verdict = await _analyze_test(
            test_hunk, intent, llm, structural_diff,
            problem_statement=problem_statement,
        )
        test_verdicts.append(verdict)

    for test_id in parsed.f2p_tests_with_no_hunk:
        verdict = await _analyze_unmatched_test(test_id, intent)
        test_verdicts.append(verdict)

    aligned = sum(1 for v in test_verdicts if v.intent_match == TestVerdict.ALIGNED)
    tangential = sum(1 for v in test_verdicts if v.intent_match == TestVerdict.TANGENTIAL)
    unrelated = sum(1 for v in test_verdicts if v.intent_match == TestVerdict.UNRELATED)

    total_assertions = sum(len(v.assertion_verdicts) for v in test_verdicts)
    on_topic = sum(v.on_topic_count for v in test_verdicts)
    off_topic = sum(v.off_topic_count for v in test_verdicts)
    has_modified = any(v.is_modified for v in test_verdicts)

    return ExcessTestDetail(
        total_tests=len(test_verdicts),
        aligned_count=aligned,
        tangential_count=tangential,
        unrelated_count=unrelated,
        total_assertions=total_assertions,
        on_topic_assertions=on_topic,
        off_topic_assertions=off_topic,
        has_modified_tests=has_modified,
        test_verdicts=test_verdicts,
    )
