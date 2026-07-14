"""Parse test_patch diffs from SWE-bench records.

Extracts individual test function diffs and classifies them as NEW or MODIFIED.
Supports Python, Go, JavaScript/TypeScript, Ruby, Rust, and Java test patterns.
"""

from __future__ import annotations

import re

from bench_cleanser.models import PatchHunk, TestHunk, TestModificationType
from bench_cleanser.parsing.patch_parser import parse_patch

_DEF_TEST_RE = re.compile(r"^(\s*)def\s+(test_\w+)\s*\(")

# Multi-language test function patterns
_LANG_TEST_PATTERNS: list[tuple[re.Pattern, int, int]] = [
    # Python: def test_foo(...)
    (re.compile(r"^(\s*)def\s+(test_\w+)\s*\("), 1, 2),
    # Go: func TestFoo(t *testing.T) or func (s *Suite) TestFoo(...)
    (re.compile(r"^(\s*)func\s+(?:\([^)]*\)\s+)?(Test\w+)\s*\("), 1, 2),
    # JavaScript/TypeScript: it('description', ...) / test('description', ...)
    (re.compile(r"""^(\s*)(?:it|test)\s*\(\s*['"`]([^'"`]+)['"`]"""), 1, 2),
    # JavaScript/TypeScript: describe('...')
    (re.compile(r"""^(\s*)describe\s*\(\s*['"`]([^'"`]+)['"`]"""), 1, 2),
    # Ruby: def test_foo / it 'description'
    (re.compile(r"^(\s*)def\s+(test_\w+)"), 1, 2),
    (re.compile(r"""^(\s*)it\s+['"]([^'"]+)['"]"""), 1, 2),
    # Rust: #[test] fn test_foo() or fn test_foo()
    (re.compile(r"^(\s*)(?:pub\s+)?fn\s+(test_\w+)\s*\("), 1, 2),
    # Java/Kotlin: @Test ... void testFoo() or public void testFoo()
    (re.compile(r"^(\s*)(?:public\s+)?(?:void\s+|fun\s+)(test\w+)\s*\("), 1, 2),
]

# Pattern for any function definition (multi-language)
_ANY_FUNC_DEF_RE = re.compile(
    r"^\s*(?:"
    r"def\s+\w+\s*\("               # Python/Ruby
    r"|func\s+(?:\([^)]*\)\s+)?\w+\s*\("  # Go
    r"|(?:pub\s+)?fn\s+\w+\s*\("    # Rust
    r"|(?:(?:public|private|protected|static)\s+)*(?:void|int|bool|string|[A-Z]\w*)\s+\w+\s*\("  # Java/C#
    r"|(?:function|const|let|var)\s+\w+"  # JavaScript
    r"|(?:export\s+)?(?:async\s+)?function\s+\w+\s*\("  # JS/TS
    r")"
)


def _strip_diff_prefix(line: str) -> str:
    """Remove the leading ``+`` or ``-`` from a diff line, if present."""
    if line.startswith("+") or line.startswith("-"):
        return line[1:]
    return line


def _is_function_def(line: str) -> bool:
    """Return True if *line* (without diff prefix) looks like a function def."""
    stripped = _strip_diff_prefix(line)
    return bool(_ANY_FUNC_DEF_RE.match(stripped))


def _match_test_function(line: str) -> tuple[str | None, int | None]:
    """Try to match a test function definition in any supported language.

    Returns (test_name, indent) or (None, None).
    """
    for pattern, indent_group, name_group in _LANG_TEST_PATTERNS:
        m = pattern.match(line)
        if m:
            return m.group(name_group), len(m.group(indent_group))
    return None, None


def _is_test_function_def(line: str) -> bool:
    """Return True if *line* (without diff prefix) defines a test function."""
    stripped = _strip_diff_prefix(line)
    name, _ = _match_test_function(stripped)
    return name is not None


def _extract_test_name(line: str) -> str | None:
    """Extract the test function name from a line."""
    stripped = _strip_diff_prefix(line)
    name, _ = _match_test_function(stripped)
    return name


def _indent_level(line: str) -> int:
    """Return the number of leading spaces (after stripping diff prefix)."""
    stripped = _strip_diff_prefix(line)
    return len(stripped) - len(stripped.lstrip(" "))


def classify_test_modification(hunk: PatchHunk) -> TestModificationType:
    """Determine whether a *PatchHunk* represents a NEW or MODIFIED test.

    Supports multi-language test patterns (Python, Go, JS/TS, Ruby, Rust, Java).
    """
    for line in hunk.removed_lines:
        clean = line.lstrip("-").strip()
        name, _ = _match_test_function(clean)
        if name is not None:
            return TestModificationType.MODIFIED
        if clean.startswith("assert") or clean.startswith("self.assert"):
            return TestModificationType.MODIFIED

    # If the @@ function context names a test function and there are both
    # added and removed lines, the test is being modified.
    if hunk.function_context and hunk.added_lines and hunk.removed_lines:
        ctx_name, _ = _match_test_function(hunk.function_context.strip())
        if ctx_name is not None:
            return TestModificationType.MODIFIED

    # Check added lines for test definitions.
    for line in hunk.added_lines:
        clean = line.lstrip("+").strip()
        name, _ = _match_test_function(clean)
        if name is not None:
            return TestModificationType.NEW

    return TestModificationType.UNKNOWN


def extract_test_functions_from_diff(hunk: PatchHunk) -> list[dict]:
    """Extract individual test function boundaries from a *PatchHunk*.

    Returns a list of dicts, each with keys:
    ``"name"``, ``"added_lines"``, ``"removed_lines"``, ``"full_source"``.

    Supports multi-language test patterns (Python, Go, JS/TS, Ruby, Rust, Java).
    Uses indentation/brace-based parsing to delineate function boundaries.
    """
    # Reconstruct the ordered sequence of diff lines so we can track
    # which test function each line belongs to.
    raw_lines = hunk.raw_diff.splitlines()

    # We need to walk through the diff body (skip the ``@@`` header line).
    body_lines: list[str] = []
    hunk_header_line: str = ""
    for idx, line in enumerate(raw_lines):
        if line.startswith("@@"):
            hunk_header_line = line
            # Everything after the first @@ header is body.
            body_lines = raw_lines[idx + 1:]
            break

    if not body_lines:
        body_lines = raw_lines

    # Walk the body and slice into test-function segments.
    segments: list[dict] = []
    current: dict | None = None
    base_indent: int | None = None

    # Check whether the @@ header itself names a test function.
    if hunk_header_line:
        header_match = re.search(
            r"@@.*@@\s*(.*)", hunk_header_line
        )
        if header_match:
            func_ctx = header_match.group(1).strip()
            ctx_name, ctx_indent = _match_test_function(func_ctx)
            if ctx_name is not None:
                base_indent = ctx_indent
                current = {
                    "name": ctx_name,
                    "added_lines": [],
                    "removed_lines": [],
                    "_raw_post": [],
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
        test_name, test_indent = _match_test_function(stripped)
        if test_name is not None:
            if base_indent is None:
                base_indent = test_indent

            # Only treat as a boundary if at the base indent level.
            if test_indent == base_indent:
                # A modified definition is represented by a removed ``def``
                # immediately followed by an added ``def`` with the same
                # name.  Keep those lines in one segment; splitting them
                # creates a bogus removed-only test plus a bogus new test.
                if current is not None and current["name"] != test_name:
                    segments.append(current)
                    current = None
                if current is None:
                    current = {
                        "name": test_name,
                        "added_lines": [],
                        "removed_lines": [],
                        # Ordered post-patch lines: diff context plus additions,
                        # never removals.  This is materially more useful than
                        # the previous added-lines-only pseudo-source.
                        "_raw_post": [],
                    }

        # If we encounter a non-test function def at the base indent we close
        # the current segment (e.g. helper functions between tests).
        elif current is not None:
            if base_indent is not None and _is_function_def(line):
                clean_stripped = _strip_diff_prefix(line) if (is_added or is_removed) else line
                if is_context and clean_stripped.startswith(" "):
                    clean_stripped = clean_stripped[1:]
                line_indent = len(clean_stripped) - len(clean_stripped.lstrip(" "))
                if line_indent == base_indent:
                    segments.append(current)
                    current = None

        # Accumulate lines into the current segment.
        if current is not None:
            if is_added:
                current["added_lines"].append(line)
                current["_raw_post"].append(_strip_diff_prefix(line))
            elif is_removed:
                current["removed_lines"].append(line)
            else:
                # Unified-diff context has one marker space which is not part
                # of the source text.
                post_line = line[1:] if line.startswith(" ") else line
                current["_raw_post"].append(post_line)

    # Don't forget the last segment.
    if current is not None:
        segments.append(current)

    # Build ``full_source`` from the ordered post-patch hunk context.  For a
    # new test this is normally the complete function; for a modified test it
    # is a faithful changed slice and Stage 1.5 can merge it with the complete
    # pre-patch function.
    results: list[dict] = []
    for seg in segments:
        full_source = "\n".join(seg.pop("_raw_post", []))
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
    # Build a lookup from test function name to *file identities*.  A test
    # name alone is not an identity: large repositories routinely define
    # ``test_repr`` or ``test_default`` in multiple files.
    name_to_hunks: dict[str, dict[str, list[TestHunk]]] = {}
    for th in test_hunks:
        path = _normalize_test_path(th.file_path)
        name_to_hunks.setdefault(th.test_name, {}).setdefault(path, []).append(th)

    matched: list[TestHunk] = []
    matched_ids: set[int] = set()
    unmatched: list[str] = []

    for test_id in f2p_tests:
        test_path, base_name = _f2p_test_identity(test_id)
        by_path = name_to_hunks.get(base_name, {})

        selected: list[TestHunk] = []
        if test_path:
            exact = by_path.get(test_path, [])
            if exact:
                selected = exact
            else:
                # Some harnesses report paths relative to a package root
                # while the patch records repository-relative paths.  A
                # suffix match is safe only when it identifies one file.
                suffix_matches = [
                    hunks
                    for path, hunks in by_path.items()
                    if _paths_refer_to_same_file(path, test_path)
                ]
                if len(suffix_matches) == 1:
                    selected = suffix_matches[0]
        elif len(by_path) == 1:
            # Dotted unittest IDs do not always carry a reliable filename.
            # Fall back to the function name only when it is unambiguous.
            selected = next(iter(by_path.values()))

        if selected:
            for hunk in selected:
                if id(hunk) not in matched_ids:
                    matched.append(hunk)
                    matched_ids.add(id(hunk))
        else:
            unmatched.append(test_id)

    return matched, unmatched


def _normalize_test_path(path: str) -> str:
    """Normalize a test path without discarding filename information."""
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith(("a/", "b/")):
        normalized = normalized[2:]
    return normalized.strip("/")


def _f2p_test_identity(test_id: str) -> tuple[str, str]:
    """Return ``(explicit_file_path, base_test_name)`` for an F2P ID.

    The path is empty when the harness format does not identify a file
    reliably (for example ``test_x (package.module.TestCase)``).  Callers
    must then require a unique name match.
    """
    raw = test_id.strip()
    if "::" in raw:
        parts = raw.split("::")
        path = _normalize_test_path(parts[0])
        name = parts[-1].split("[", 1)[0]
        return path, name
    if " (" in raw:
        name = raw.split(" (", 1)[0].split(".")[-1]
        return "", name.split("[", 1)[0]
    name = raw.rsplit(".", 1)[-1].split("[", 1)[0]
    return "", name


def _paths_refer_to_same_file(left: str, right: str) -> bool:
    left = _normalize_test_path(left)
    right = _normalize_test_path(right)
    return bool(
        left == right
        or left.endswith("/" + right)
        or right.endswith("/" + left)
    )


def _classify_function(
    added_lines: list[str],
    removed_lines: list[str],
    default: TestModificationType,
) -> TestModificationType:
    """Refine the modification type for a single test function.

    Multi-language aware: checks for test function definitions and assertion
    patterns across Python, Go, JS/TS, Ruby, Rust, and Java.
    """
    if removed_lines:
        # Any removal inside this function proves it pre-existed.  Restricting
        # this to removed ``def``/``assert`` lines misclassified ordinary body
        # edits as UNKNOWN or NEW.
        return TestModificationType.MODIFIED

    # If removed_lines are empty for this function, it is a pure addition.
    if not removed_lines:
        has_def = any(
            _is_test_function_def(l) for l in added_lines
        )
        if has_def:
            return TestModificationType.NEW

    return default
