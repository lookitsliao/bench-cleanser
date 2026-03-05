"""Parse test_patch diffs from SWE-bench records.

Extracts individual test function diffs and classifies them as NEW or MODIFIED.
"""

from __future__ import annotations

import re

from bench_cleanser.models import PatchHunk, TestHunk, TestModificationType
from bench_cleanser.parsing.patch_parser import parse_patch


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DEF_TEST_RE = re.compile(r"^(\s*)def\s+(test_\w+)\s*\(")


def _strip_diff_prefix(line: str) -> str:
    """Remove the leading ``+`` or ``-`` from a diff line, if present."""
    if line.startswith("+") or line.startswith("-"):
        return line[1:]
    return line


def _is_function_def(line: str) -> bool:
    """Return True if *line* (without diff prefix) looks like ``def …(``."""
    stripped = _strip_diff_prefix(line)
    return bool(re.match(r"^\s*def\s+\w+\s*\(", stripped))


def _is_test_function_def(line: str) -> bool:
    """Return True if *line* (without diff prefix) defines a ``test_…`` function."""
    stripped = _strip_diff_prefix(line)
    return bool(_DEF_TEST_RE.match(stripped))


def _extract_test_name(line: str) -> str | None:
    """Extract the test function name from a line like ``def test_foo(…``."""
    stripped = _strip_diff_prefix(line)
    m = _DEF_TEST_RE.match(stripped)
    return m.group(2) if m else None


def _indent_level(line: str) -> int:
    """Return the number of leading spaces (after stripping diff prefix)."""
    stripped = _strip_diff_prefix(line)
    return len(stripped) - len(stripped.lstrip(" "))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_test_modification(hunk: PatchHunk) -> TestModificationType:
    """Determine whether a *PatchHunk* represents a NEW or MODIFIED test.

    Key signals:
    * If ``removed_lines`` contains any ``def test_`` or ``assert`` statement
      the test is **MODIFIED**.
    * If the hunk has both added and removed lines (body changes) it is
      **MODIFIED** — the function signature didn't change but its body did.
    * If only ``added_lines`` contain ``def test_``, the test is **NEW**.
    * If the ``@@`` header names a ``test_`` function and the hunk has both
      added and removed lines, it is **MODIFIED**.
    """
    for line in hunk.removed_lines:
        clean = line.lstrip("-").strip()
        if re.match(r"def\s+test_\w+\s*\(", clean):
            return TestModificationType.MODIFIED
        if clean.startswith("assert"):
            return TestModificationType.MODIFIED

    # If the @@ function context names a test function and there are both
    # added and removed lines, the test is being modified.
    if hunk.function_context and hunk.added_lines and hunk.removed_lines:
        if _DEF_TEST_RE.match(hunk.function_context.strip()):
            return TestModificationType.MODIFIED

    # Check added lines for test definitions.
    for line in hunk.added_lines:
        clean = line.lstrip("+").strip()
        if re.match(r"def\s+test_\w+\s*\(", clean):
            return TestModificationType.NEW

    return TestModificationType.UNKNOWN


def extract_test_functions_from_diff(hunk: PatchHunk) -> list[dict]:
    """Extract individual test function boundaries from a *PatchHunk*.

    Returns a list of dicts, each with keys:
    ``"name"``, ``"added_lines"``, ``"removed_lines"``, ``"full_source"``.

    Uses indentation-based parsing: a ``def test_`` at the function-level
    indentation starts a new function block; the next function definition (or
    the end of the hunk) closes the current block.

    Also handles the case where a modified test's ``def`` line appears in the
    ``@@`` hunk header (function context) rather than in the diff body. This
    happens when the function signature is unchanged but its body has
    modifications.
    """
    # Reconstruct the ordered sequence of diff lines so we can track
    # which test function each line belongs to.
    raw_lines = hunk.raw_diff.splitlines()

    # We need to walk through the diff body (skip the ``@@`` header line).
    body_lines: list[str] = []
    hunk_header_line: str = ""
    for line in raw_lines:
        if line.startswith("@@"):
            hunk_header_line = line
            # Everything after the first @@ header is body.
            idx = raw_lines.index(line)
            body_lines = raw_lines[idx + 1:]
            break

    if not body_lines:
        body_lines = raw_lines

    # Walk the body and slice into test-function segments.
    segments: list[dict] = []
    current: dict | None = None
    # Determine the base indent level for function definitions.  In most test
    # files this is 0 (top-level functions) or 4 (methods inside a class).  We
    # auto-detect from the first ``def test_`` we encounter.
    base_indent: int | None = None

    # Check whether the @@ header itself names a test function.  This happens
    # when the function definition line is a context line that precedes the
    # hunk (i.e., the function is being MODIFIED, not newly added).
    # Example: @@ -137,12 +164,12 @@ def test_csv_regex_error(capsys: ...)
    if hunk_header_line:
        header_match = re.search(
            r"@@.*@@\s*(.*)", hunk_header_line
        )
        if header_match:
            func_ctx = header_match.group(1).strip()
            header_test_match = _DEF_TEST_RE.match(func_ctx)
            if header_test_match:
                # The hunk header names a test function -- start a segment
                # for it immediately.  All body lines belong to this function
                # unless we encounter another def at the same indent level.
                indent = len(header_test_match.group(1))
                base_indent = indent
                current = {
                    "name": header_test_match.group(2),
                    "added_lines": [],
                    "removed_lines": [],
                    "_raw_added": [],
                }

    for line in body_lines:
        # Skip empty lines that are just context.
        is_added = line.startswith("+") and not line.startswith("+++")
        is_removed = line.startswith("-") and not line.startswith("---")
        is_context = not is_added and not is_removed

        # Check whether this line starts a new test function.
        stripped = _strip_diff_prefix(line) if (is_added or is_removed) else line
        # For context lines, strip the leading space from diff format
        if is_context and stripped.startswith(" "):
            stripped = stripped[1:]
        m = _DEF_TEST_RE.match(stripped)
        if m:
            indent = len(m.group(1))
            if base_indent is None:
                base_indent = indent

            # Only treat as a boundary if at the base indent level.
            if indent == base_indent:
                # Close the previous segment.
                if current is not None:
                    segments.append(current)
                current = {
                    "name": m.group(2),
                    "added_lines": [],
                    "removed_lines": [],
                    "_raw_added": [],  # keep for full_source reconstruction
                }

        # If we also encounter a non-test ``def`` at the base indent we close
        # the current segment (e.g. helper functions between tests).
        elif current is not None and not is_context:
            clean = stripped.strip()
            if base_indent is not None and re.match(r"def\s+\w+\s*\(", clean):
                line_indent = len(stripped) - len(stripped.lstrip(" "))
                if line_indent == base_indent:
                    segments.append(current)
                    current = None

        # Accumulate lines into the current segment.
        if current is not None:
            if is_added:
                current["added_lines"].append(line)
                current["_raw_added"].append(
                    _strip_diff_prefix(line) if is_added else stripped
                )
            elif is_removed:
                current["removed_lines"].append(line)

    # Don't forget the last segment.
    if current is not None:
        segments.append(current)

    # Build ``full_source`` from the added lines (stripping ``+`` prefix).
    results: list[dict] = []
    for seg in segments:
        full_source = "\n".join(seg.pop("_raw_added", []))
        seg["full_source"] = full_source
        results.append(seg)

    return results


def parse_test_patch(test_patch_text: str) -> list[TestHunk]:
    """Parse a ``test_patch`` unified diff into :class:`TestHunk` objects.

    1. Uses :func:`parse_patch` to get raw :class:`PatchHunk` objects.
    2. Extracts individual test functions from each hunk.
    3. Classifies each test as NEW or MODIFIED.
    """
    if not test_patch_text or not test_patch_text.strip():
        return []

    raw_hunks: list[PatchHunk] = parse_patch(test_patch_text)
    test_hunks: list[TestHunk] = []

    for hunk in raw_hunks:
        # Determine the overall modification type for the hunk.  Individual
        # functions inside the same hunk may differ, but we use the hunk-level
        # signal as the default and refine per-function below.
        hunk_mod_type = classify_test_modification(hunk)

        functions = extract_test_functions_from_diff(hunk)

        if not functions:
            # No ``def test_`` found -- skip (e.g. import-only hunks).
            continue

        for func in functions:
            name: str = func["name"]
            added: list[str] = func["added_lines"]
            removed: list[str] = func["removed_lines"]
            full_source: str = func["full_source"]

            # Per-function classification override: if this specific function
            # has removal lines containing ``def test_`` or ``assert``, it is
            # MODIFIED regardless of the hunk-level verdict.
            mod_type = _classify_function(added, removed, hunk_mod_type)

            full_test_id = f"{hunk.file_path}::{name}"

            test_hunks.append(
                TestHunk(
                    file_path=hunk.file_path,
                    test_name=name,
                    full_test_id=full_test_id,
                    modification_type=mod_type,
                    added_lines=added,
                    removed_lines=removed,
                    full_source=full_source,
                    raw_diff=hunk.raw_diff,
                )
            )

    return test_hunks


def match_f2p_tests_to_hunks(
    f2p_tests: list[str],
    test_hunks: list[TestHunk],
) -> tuple[list[TestHunk], list[str]]:
    """Match fail-to-pass test IDs to :class:`TestHunk` objects.

    Parameters
    ----------
    f2p_tests:
        List of F2P test IDs, e.g.
        ``"tests/config/test_config.py::test_csv_regex_error"``.
    test_hunks:
        All :class:`TestHunk` objects parsed from the test patch.

    Returns
    -------
    tuple[list[TestHunk], list[str]]
        ``(matched_hunks, unmatched_test_ids)``

        * ``matched_hunks`` -- hunks whose ``test_name`` matches an F2P ID.
        * ``unmatched_test_ids`` -- F2P IDs for which no hunk was found.  This
          typically means the test existed before and was not modified in the
          test patch (or was changed only in the gold patch).
    """
    # Build a lookup from test function name -> list of TestHunks.
    name_to_hunks: dict[str, list[TestHunk]] = {}
    for th in test_hunks:
        name_to_hunks.setdefault(th.test_name, []).append(th)

    matched: list[TestHunk] = []
    unmatched: list[str] = []

    for test_id in f2p_tests:
        # Extract the test function name -- the part after the last `::`.
        parts = test_id.split("::")
        func_name = parts[-1] if parts else test_id

        # Some test IDs include parameterised suffixes like ``[param]``.
        # Strip those so we match the base function name.
        base_name = func_name.split("[")[0]

        hunks_for_name = name_to_hunks.get(base_name)
        if hunks_for_name:
            # If there are multiple hunks for the same function name (rare),
            # add all of them.
            matched.extend(hunks_for_name)
        else:
            unmatched.append(test_id)

    return matched, unmatched


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _classify_function(
    added_lines: list[str],
    removed_lines: list[str],
    default: TestModificationType,
) -> TestModificationType:
    """Refine the modification type for a single test function.

    If the function's own ``removed_lines`` contain a ``def test_`` or
    ``assert`` call, classify it as MODIFIED regardless of the hunk-level
    default.  If only ``added_lines`` carry the definition, it is NEW.
    """
    for line in removed_lines:
        clean = _strip_diff_prefix(line).strip()
        if re.match(r"def\s+test_\w+\s*\(", clean):
            return TestModificationType.MODIFIED
        if clean.startswith("assert"):
            return TestModificationType.MODIFIED

    # If removed_lines are empty for this function, it is a pure addition.
    if not removed_lines:
        has_def = any(
            _is_test_function_def(l) for l in added_lines
        )
        if has_def:
            return TestModificationType.NEW

    return default
