"""Cross-reference analysis: detect circular dependencies between patch hunks and F2P tests.

When an F2P test exercises functions from UNRELATED patch hunks, the test
requires code the problem doesn't ask for.  This circular dependency is a
strong APPROACH_LOCK signal — the agent can't pass the test without
implementing out-of-scope changes.

Uses CodeContext call-graph data when available, falls back to identifier
overlap heuristics otherwise.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from bench_cleanser.models import (
    ExcessPatchDetail,
    ExcessTestDetail,
    PatchVerdict,
    TestHunk,
)

logger = logging.getLogger(__name__)


@dataclass
class CircularDependency:
    """A single circular dependency between an F2P test and out-of-scope hunks."""
    test_id: str
    test_name: str
    linked_hunk_indices: list[int]
    linked_files: list[str]
    confidence: float
    reasoning: str


@dataclass
class CrossReferenceResult:
    """Cross-reference analysis output."""
    circular_dependencies: list[CircularDependency] = field(default_factory=list)

    @property
    def has_circular(self) -> bool:
        return len(self.circular_dependencies) > 0

    @property
    def max_confidence(self) -> float:
        if not self.circular_dependencies:
            return 0.0
        return max(cd.confidence for cd in self.circular_dependencies)


_COMMON_IDENTIFIERS = frozenset({
    "test", "self", "assert", "True", "False", "None", "return",
    "import", "from", "class", "def", "for", "while", "with",
    "pass", "break", "continue", "raise", "try", "except", "finally",
    "module", "file", "path", "name", "value", "data", "result",
    "args", "kwargs", "index", "count", "item", "key", "scope",
    "hunk", "patch", "source", "line", "text", "string", "code",
})


def _extract_identifiers(text: str) -> set[str]:
    """Extract Python identifiers (4+ chars) for fallback overlap detection.

    Filters common language keywords and generic names to reduce false
    positives. Only identifiers likely to be project-specific are kept.
    """
    raw = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b", text))
    return raw - _COMMON_IDENTIFIERS


def _normalize_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("/").rstrip("/")


def analyze_cross_references(
    excess_patch: ExcessPatchDetail,
    excess_test: ExcessTestDetail,
    f2p_test_hunks: list[TestHunk],
) -> CrossReferenceResult:
    """Detect circular dependencies between UNRELATED patch hunks and F2P tests.

    A circular dependency exists when an F2P test calls into or exercises
    functions modified by a patch hunk that is UNRELATED to the problem.
    The test can't pass without the out-of-scope patch code, meaning the
    benchmark forces a specific implementation approach.
    """
    oos_hunk_indices: set[int] = set()
    oos_files: set[str] = set()
    oos_identifiers: dict[int, set[str]] = {}

    for hv in excess_patch.hunk_verdicts:
        if hv.verdict == PatchVerdict.UNRELATED:
            oos_hunk_indices.add(hv.hunk_index)
            oos_files.add(_normalize_path(hv.file_path))
            oos_identifiers[hv.hunk_index] = _extract_identifiers(
                hv.reasoning + " " + hv.file_path
            )

    if not oos_hunk_indices:
        return CrossReferenceResult()

    hunk_by_test: dict[str, TestHunk] = {
        th.full_test_id: th for th in f2p_test_hunks
    }

    circular_deps: list[CircularDependency] = []

    for tv in excess_test.test_verdicts:
        test_hunk = hunk_by_test.get(tv.test_id)
        ctx = test_hunk.code_context if test_hunk else None

        linked_indices: set[int] = set()
        linked_files: set[str] = set()

        if ctx is not None:
            for ct in ctx.call_targets:
                if ct.is_in_patch and ct.file_path:
                    norm = _normalize_path(ct.file_path)
                    if norm in oos_files:
                        linked_indices.update(
                            i for i, hv in enumerate(excess_patch.hunk_verdicts)
                            if hv.verdict == PatchVerdict.UNRELATED
                            and _normalize_path(hv.file_path) == norm
                        )
                        linked_files.add(norm)

            for tf in ctx.tested_functions:
                if tf.is_modified_by_patch and tf.file_path:
                    norm = _normalize_path(tf.file_path)
                    if norm in oos_files:
                        linked_indices.update(
                            i for i, hv in enumerate(excess_patch.hunk_verdicts)
                            if hv.verdict == PatchVerdict.UNRELATED
                            and _normalize_path(hv.file_path) == norm
                        )
                        linked_files.add(norm)
        else:
            test_text = tv.test_name
            if tv.reasoning:
                test_text += " " + tv.reasoning
            test_ids = _extract_identifiers(test_text)
            for hunk_idx, hunk_ids in oos_identifiers.items():
                if test_ids & hunk_ids:
                    linked_indices.add(hunk_idx)

        if linked_indices:
            confidence = min(0.95, 0.7 + 0.1 * len(linked_indices))
            if ctx is not None:
                confidence = min(0.98, confidence + 0.1)

            method = "call-graph" if ctx is not None else "identifier overlap"
            circular_deps.append(CircularDependency(
                test_id=tv.test_id,
                test_name=tv.test_name,
                linked_hunk_indices=sorted(linked_indices),
                linked_files=sorted(linked_files),
                confidence=confidence,
                reasoning=(
                    f"Test '{tv.test_name}' exercises code from "
                    f"{len(linked_indices)} UNRELATED hunk(s) "
                    f"(detected via {method})"
                ),
            ))

    return CrossReferenceResult(circular_dependencies=circular_deps)
