"""Retrieve full source code from cloned repositories.

Provides functions to read complete test functions (pre- and post-patch),
extract imports and fixtures from test files, and read source files being
tested.
"""

from __future__ import annotations

import ast
import logging
import pathlib
import re
import textwrap
from typing import Sequence

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# AST-based function extraction
# -------------------------------------------------------------------

def extract_function_source(
    file_content: str,
    func_name: str,
    *,
    max_lines: int = 200,
) -> str:
    """Extract a single function's source from *file_content* using AST.

    Falls back to regex-based extraction if AST parsing fails.
    Returns ``""`` if the function is not found.
    """
    # Try AST first
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return _extract_function_regex(file_content, func_name, max_lines)

    lines = file_content.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                start = node.lineno - 1  # 0-indexed
                end = node.end_lineno or (start + 1)
                func_lines = lines[start:end]
                if len(func_lines) > max_lines:
                    func_lines = func_lines[:max_lines]
                    func_lines.append(f"    # ... truncated ({end - start} total lines)\n")
                return "".join(func_lines)

    # Fall back to regex
    return _extract_function_regex(file_content, func_name, max_lines)


def _extract_function_regex(
    file_content: str,
    func_name: str,
    max_lines: int,
) -> str:
    """Regex fallback for extracting a function."""
    pattern = re.compile(
        rf"^(\s*)(?:async\s+)?def\s+{re.escape(func_name)}\s*\(",
        re.MULTILINE,
    )
    m = pattern.search(file_content)
    if not m:
        return ""

    indent = len(m.group(1))
    lines = file_content.splitlines(keepends=True)
    start = file_content[:m.start()].count("\n")
    result: list[str] = [lines[start]]

    for i in range(start + 1, min(len(lines), start + max_lines)):
        line = lines[i]
        stripped = line.rstrip()
        if stripped == "":
            result.append(line)
            continue
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= indent and stripped and not stripped.startswith("#"):
            break
        result.append(line)

    return "".join(result)


# -------------------------------------------------------------------
# Full test source retrieval
# -------------------------------------------------------------------

def get_full_test_source(
    repo_path: pathlib.Path,
    test_file: str,
    test_name: str,
    *,
    max_lines: int = 200,
) -> str:
    """Read the full test function source from the pre-patch repo.

    Returns ``""`` if the file or function is not found.
    """
    file_path = repo_path / test_file
    if not file_path.exists():
        logger.debug("Test file not found: %s", file_path)
        return ""

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    return extract_function_source(content, test_name, max_lines=max_lines)


def get_post_patch_test_source(
    pre_patch_content: str,
    test_name: str,
    added_lines: list[str],
    removed_lines: list[str],
    *,
    max_lines: int = 200,
) -> str:
    """Reconstruct the post-patch test function.

    If we have the pre-patch content and diff info, apply the changes.
    Falls back to reconstructing from added_lines if needed.
    """
    if not pre_patch_content:
        # No pre-patch content — just use added lines
        return "\n".join(added_lines)

    # For a robust approach: find the function in pre_patch_content,
    # then apply the removed/added lines.  In practice, the simplest
    # approach is to reconstruct from the diff: take the pre-patch
    # function and apply line-level substitution.
    #
    # However, for our purposes, the most reliable method is:
    # - If the test is MODIFIED, the post-patch version is the pre-patch
    #   minus removed lines plus added lines.
    # - If the test is NEW, post_patch = added_lines.
    #
    # Since we don't have a proper diff application library, we use
    # the raw_diff reconstruction from test_parser.  For LLM analysis
    # purposes, providing both pre and post separately is sufficient.

    # Simple approach: return the added lines as post-patch source
    if added_lines:
        return "\n".join(added_lines)

    return pre_patch_content


# -------------------------------------------------------------------
# Import / fixture extraction
# -------------------------------------------------------------------

def extract_imports(file_content: str) -> str:
    """Extract import statements from a Python file.

    Returns a string of all import lines (``import x`` and ``from x import y``).
    """
    lines: list[str] = []
    in_multiline = False
    for line in file_content.splitlines():
        stripped = line.strip()
        if in_multiline:
            lines.append(line)
            if ")" in stripped:
                in_multiline = False
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            lines.append(line)
            if "(" in stripped and ")" not in stripped:
                in_multiline = True
    return "\n".join(lines)


def extract_fixtures(
    file_content: str,
    test_name: str,
) -> str:
    """Extract pytest fixtures and setup methods relevant to *test_name*.

    Looks for:
    - ``@pytest.fixture`` decorated functions
    - ``setup_method`` / ``setUp`` / ``tearDown``
    - conftest.py fixtures (by name reference)
    """
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return ""

    fixtures: list[str] = []
    lines = file_content.splitlines(keepends=True)

    # Find the test function to check its parameters (fixture injection)
    test_params: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == test_name:
                for arg in node.args.args:
                    if arg.arg not in ("self", "cls"):
                        test_params.add(arg.arg)

    # Find fixture definitions used by the test
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_fixture = False
            for dec in node.decorator_list:
                dec_str = ast.dump(dec)
                if "fixture" in dec_str:
                    is_fixture = True
                    break

            if is_fixture and node.name in test_params:
                start = node.lineno - 1
                end = node.end_lineno or (start + 1)
                func_lines = lines[start:min(end, start + 50)]
                fixtures.append("".join(func_lines))

            # Also capture setup/teardown
            if node.name in ("setup_method", "setUp", "tearDown", "setup", "teardown"):
                start = node.lineno - 1
                end = node.end_lineno or (start + 1)
                func_lines = lines[start:min(end, start + 30)]
                fixtures.append("".join(func_lines))

    return "\n\n".join(fixtures)


# -------------------------------------------------------------------
# Source file reading
# -------------------------------------------------------------------

def get_source_functions(
    repo_path: pathlib.Path,
    file_path: str,
    function_names: Sequence[str],
    *,
    max_lines: int = 200,
) -> dict[str, str]:
    """Read specific functions from a source file.

    Returns a dict mapping function name to source code.
    """
    full_path = repo_path / file_path
    if not full_path.exists():
        return {}

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    result: dict[str, str] = {}
    for name in function_names:
        source = extract_function_source(content, name, max_lines=max_lines)
        if source:
            result[name] = source

    return result


def get_class_with_method(
    repo_path: pathlib.Path,
    file_path: str,
    method_name: str,
    *,
    max_lines: int = 200,
) -> str:
    """Read a class method including its class context.

    Returns the class definition preamble + the method source.
    """
    full_path = repo_path / file_path
    if not full_path.exists():
        return ""

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content)
    except (OSError, SyntaxError):
        return ""

    lines = content.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == method_name:
                        # Get class header (first line or two)
                        class_start = node.lineno - 1
                        class_header = lines[class_start]

                        # Get method source
                        method_start = item.lineno - 1
                        method_end = item.end_lineno or (method_start + 1)
                        method_lines = lines[method_start:min(method_end, method_start + max_lines)]

                        return class_header + "    ...\n\n" + "".join(method_lines)

    return ""
