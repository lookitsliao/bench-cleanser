"""Stage 3: structural diff analysis with an optional public AST backend.

Parses source files and patch hunks to extract:
- Changed blocks (functions/classes) with edit status
- Test functions with extracted assertions
- Call graph edges between tests and changed source

The public tree-sitter extra provides multilingual source blocks when present.
Every unresolved hunk falls back to conservative standard-library/patch
analysis, so optional-backend failures never fabricate or drop the whole task.
"""

from __future__ import annotations

import ast
import logging
import pathlib
import re

from bench_cleanser.models import (
    AssertionDetail,
    AssertionVerdict,
    ChangedBlock,
    ParsedTask,
    PatchHunk,
    StructuralDiff,
    TestBlock,
)
from bench_cleanser.repo_manager import resolve_confined_repo_file
from bench_cleanser.static_analysis import extract_assertions, extract_test_calls

logger = logging.getLogger(__name__)


def compute_structural_diff(
    parsed_task: ParsedTask,
    repo_path: pathlib.Path | None,
) -> StructuralDiff:
    """Compute a structural diff using repository source and patch hunks."""
    return _compute_structural(parsed_task, repo_path)


def _compute_structural(
    parsed_task: ParsedTask,
    repo_path: pathlib.Path | None,
) -> StructuralDiff:
    """Compute structural analysis with tree-sitter and conservative fallback."""
    instance_id = parsed_task.record.instance_id

    changed_blocks, multilingual_ast_available = _extract_changed_blocks(
        parsed_task.patch_hunks,
        repo_path,
    )

    # Extract test blocks
    test_blocks = _extract_test_blocks(parsed_task, repo_path)

    # Build call edges
    call_edges = _build_call_edges(test_blocks, changed_blocks)

    return StructuralDiff(
        instance_id=instance_id,
        changed_blocks=changed_blocks,
        test_blocks=test_blocks,
        call_edges=call_edges,
        multilingual_ast_available=multilingual_ast_available,
    )


def _extract_changed_blocks(
    hunks: list[PatchHunk],
    repo_path: pathlib.Path | None,
) -> tuple[list[ChangedBlock], bool]:
    """Prefer public multilingual AST blocks and fall back per unresolved hunk."""

    if repo_path is None:
        return _extract_changed_blocks_from_hunks(hunks, repo_path), False

    from bench_cleanser.analysis.tree_sitter_backend import extract_changed_blocks

    changed: list[ChangedBlock] = []
    seen: set[tuple[str, str, str]] = set()
    backend_available = False
    for hunk in hunks:
        backend_blocks, available = extract_changed_blocks([hunk], repo_path)
        backend_available = backend_available or available
        selected = backend_blocks or _extract_changed_blocks_from_hunks([hunk], repo_path)
        for block in selected:
            key = (block.file_path, block.block_name, block.edit_status)
            if key in seen:
                continue
            seen.add(key)
            changed.append(block)
    return changed, backend_available


def _extract_changed_blocks_from_hunks(
    hunks: list[PatchHunk],
    repo_path: pathlib.Path | None,
) -> list[ChangedBlock]:
    """Extract changed blocks by parsing patch hunks."""
    changed: list[ChangedBlock] = []
    seen: set[tuple[str, str]] = set()

    # File extensions we can meaningfully analyze
    _SUPPORTED_EXTS = {
        ".py", ".go", ".js", ".ts", ".jsx", ".tsx", ".rb",
        ".rs", ".java", ".kt", ".cs", ".c", ".cpp", ".h", ".hpp",
    }

    for hunk in hunks:
        ext = pathlib.Path(hunk.file_path).suffix.lower()
        if ext not in _SUPPORTED_EXTS:
            continue

        # Use function context from the @@ header
        func_name = hunk.function_context.strip()
        if func_name:
            # Clean up function context (e.g., "def foo(...):" → "foo")
            func_name = _clean_function_context(func_name)

        # Determine edit status from hunk content
        has_added = bool(hunk.added_lines)
        has_removed = bool(hunk.removed_lines)
        if has_added and has_removed:
            edit_status = "UPDATE"
        elif has_added:
            edit_status = "INSERT"
        elif has_removed:
            edit_status = "DELETE"
        else:
            continue

        # Try to read full function source from repo
        pre_source = ""
        if repo_path and func_name:
            try:
                file_path = resolve_confined_repo_file(repo_path, hunk.file_path)
            except ValueError:
                logger.debug("Ignoring unsafe structural-diff path: %r", hunk.file_path)
                file_path = None
            if file_path is not None and file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    pre_source = _extract_function_source_ast(content, func_name)
                except OSError:
                    pass

        # Determine block type from diff content heuristics
        block_type = _infer_block_type(hunk, func_name)

        key = (hunk.file_path, func_name or f"hunk_{hunk.hunk_index}")
        if key not in seen:
            seen.add(key)
            changed.append(ChangedBlock(
                file_path=hunk.file_path,
                block_name=func_name or f"(hunk {hunk.hunk_index})",
                block_type=block_type,
                edit_status=edit_status,
                pre_source=pre_source,
            ))

    return changed


def _clean_function_context(ctx: str) -> str:
    """Extract the function/class/method name from a @@ context header.

    Handles Python, Go, JavaScript/TypeScript, Rust, Java, Ruby, C/C++.
    """
    # Python/Ruby: def foo(...): / class Foo(...):
    m = re.search(r"(?:def|class)\s+(\w+)", ctx)
    if m:
        return m.group(1)
    # Go: func (receiver) FuncName(...) or func FuncName(...)
    m = re.search(r"func\s+(?:\([^)]*\)\s+)?(\w+)", ctx)
    if m:
        return m.group(1)
    # Rust: fn func_name(...) or pub fn func_name(...)
    m = re.search(r"(?:pub\s+)?fn\s+(\w+)", ctx)
    if m:
        return m.group(1)
    # Java/C#/C++: type FuncName(...) or void FuncName(...)
    m = re.search(r"(?:(?:public|private|protected|static|void|int|bool|string)\s+)+(\w+)\s*\(", ctx)
    if m:
        return m.group(1)
    # JavaScript/TypeScript: function funcName(...) or const funcName
    m = re.search(r"(?:function|const|let|var)\s+(\w+)", ctx)
    if m:
        return m.group(1)
    # If it's just a name
    m = re.match(r"(\w+)", ctx.strip())
    return m.group(1) if m else ctx.strip()


def _infer_block_type(hunk: PatchHunk, func_name: str) -> str:
    """Infer block type from hunk content (multi-language)."""
    all_lines = "\n".join(hunk.added_lines + hunk.removed_lines + hunk.context_lines)
    # Python/Java/C#/Go/Rust class/struct/interface
    if re.search(r"^\s*(?:class|struct|interface|impl|type\s+\w+\s+struct)\s+", all_lines, re.MULTILINE):
        return "class"
    # Python/JS/Rust/Go function definitions
    if re.search(r"^\s*(?:async\s+)?(?:def|func|fn|function)\s+", all_lines, re.MULTILINE):
        return "function"
    if re.search(r"^\s*(?:(?:public|private|protected|static)\s+)*(?:void|int|bool|string|[A-Z]\w*)\s+\w+\s*\(", all_lines, re.MULTILINE):
        return "function"
    if hunk.is_init_file:
        return "import"
    return "statement"


def _extract_function_source_ast(content: str, func_name: str) -> str:
    """Extract function source using Python ast."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return ""

    lines = content.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                start = node.lineno - 1
                end = node.end_lineno or (start + 1)
                return "".join(lines[start:end])
        elif isinstance(node, ast.ClassDef):
            if node.name == func_name:
                start = node.lineno - 1
                end = node.end_lineno or (start + 1)
                return "".join(lines[start:end])
    return ""


# ── Test block extraction ─────────────────────────────────────────────


def _extract_test_blocks(
    parsed_task: ParsedTask,
    repo_path: pathlib.Path | None,
) -> list[TestBlock]:
    """Extract F2P test functions with assertions."""
    test_blocks: list[TestBlock] = []

    for th in parsed_task.f2p_test_hunks:
        # Get test source: prefer code_context post-patch, fallback to reconstructed
        test_source = th.full_source
        if th.code_context and th.code_context.post_patch_test_source:
            test_source = th.code_context.post_patch_test_source

        # Extract assertions using existing static_analysis module
        raw_assertions = extract_assertions(test_source)
        assertion_details = [
            AssertionDetail(
                statement=a.statement,
                verdict=AssertionVerdict.ON_TOPIC,  # default; overwritten by Stage 4
                reason="",
            )
            for a in raw_assertions
        ]

        # Extract called functions
        called_funcs = extract_test_calls(test_source)

        test_blocks.append(TestBlock(
            test_id=th.full_test_id,
            test_name=th.test_name,
            file_path=th.file_path,
            full_source=test_source,
            assertions=assertion_details,
            called_functions=called_funcs,
        ))

    # Also handle F2P tests with no matching hunk (they exist in the repo)
    for test_id in parsed_task.f2p_tests_with_no_hunk:
        if not repo_path:
            continue
        # Try to find the test source from the repo
        test_source = _find_test_source_in_repo(test_id, repo_path)
        if not test_source:
            continue

        # Extract test name from the test ID
        test_name = _test_name_from_id(test_id)

        raw_assertions = extract_assertions(test_source)
        assertion_details = [
            AssertionDetail(
                statement=a.statement,
                verdict=AssertionVerdict.ON_TOPIC,
                reason="",
            )
            for a in raw_assertions
        ]
        called_funcs = extract_test_calls(test_source)

        test_blocks.append(TestBlock(
            test_id=test_id,
            test_name=test_name,
            file_path=_file_path_from_test_id(test_id),
            full_source=test_source,
            assertions=assertion_details,
            called_functions=called_funcs,
        ))

    return test_blocks


def _find_test_source_in_repo(test_id: str, repo_path: pathlib.Path) -> str:
    """Try to find a test function's source in the repo by its test ID.

    Test IDs look like:
    - "tests.model_forms.tests.FormFieldCallbackTests.test_custom_callback_in_meta"
    - "test_custom_callback_in_meta (model_forms.tests.FormFieldCallbackTests)"
    """
    from bench_cleanser.code_visitor import extract_function_source

    # Try both ID formats
    test_name = _test_name_from_id(test_id)
    file_path = _file_path_from_test_id(test_id)

    if file_path and test_name:
        try:
            full_path = resolve_confined_repo_file(repo_path, file_path)
        except ValueError:
            logger.debug("Ignoring unsafe test-id path: %r", file_path)
            return ""
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                return extract_function_source(content, test_name)
            except OSError:
                pass

    return ""


def _test_name_from_id(test_id: str) -> str:
    """Extract just the test function name from a test ID."""
    # Format: "test_foo (module.Class)" or "module.Class.test_foo"
    if " (" in test_id:
        return test_id.split(" (")[0].split(".")[-1]
    return test_id.split(".")[-1].split("[")[0]


def _file_path_from_test_id(test_id: str) -> str:
    """Try to extract a file path from a test ID."""
    # Format: "tests/foo/test_bar.py::test_baz"
    if "::" in test_id:
        return test_id.split("::")[0]

    # Format: "test_foo (module.tests.ClassName)"
    if " (" in test_id:
        module = test_id.split("(")[1].rstrip(")")
        parts = module.split(".")
        # Convert module path to file path guess
        # e.g. "model_forms.tests.FormFieldCallbackTests" → "tests/model_forms/tests.py"
        # This is approximate; the pipeline's parsed data is more reliable
        if len(parts) >= 2:
            file_parts = parts[:-1]  # drop the class name
            return "/".join(file_parts) + ".py"

    return ""


# ── Call graph construction ───────────────────────────────────────────


def _build_call_edges(
    test_blocks: list[TestBlock],
    changed_blocks: list[ChangedBlock],
) -> list[tuple[str, str]]:
    """Build call edges: (test_name, changed_block_name) pairs.

    A test is linked to a changed block if it calls a function with the
    same name as the changed block.
    """
    changed_names = {cb.block_name for cb in changed_blocks}
    edges: list[tuple[str, str]] = []

    for tb in test_blocks:
        for call_name in tb.called_functions:
            # Match by base name (last part of dotted name)
            base_call = call_name.split(".")[-1]
            if base_call in changed_names:
                edges.append((tb.test_name, base_call))

    return edges
