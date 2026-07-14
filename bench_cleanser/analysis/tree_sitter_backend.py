"""Optional public tree-sitter backend for multilingual changed blocks.

``tree-sitter-language-pack`` is a public, dual-licensed PyPI package.  The
supported 0.9.1 release ships parser assets in platform wheels, avoiding the
runtime downloads introduced by its later 1.x line. This backend is optional:
the core parser still produces conservative hunk-level blocks when unavailable.
"""

from __future__ import annotations

import logging
import pathlib
import re
from typing import Any, cast

from bench_cleanser.models import ChangedBlock, PatchHunk
from bench_cleanser.repo_manager import validate_relative_file_path

logger = logging.getLogger(__name__)

_HUNK_RANGE = re.compile(
    r"@@\s+-(?P<old_start>\d+)(?:,(?P<old_count>\d+))?\s+"
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))?\s+@@"
)

# Common grammar node names. Unknown languages still fall back to the hunk
# context instead of guessing from every named syntax node.
_FUNCTION_NODES = {
    "function_definition",
    "function_declaration",
    "function_expression",
    "function_item",
    "method",
    "method_declaration",
    "method_definition",
    "constructor_declaration",
    "arrow_function",
}
_CLASS_NODES = {
    "class_definition",
    "class_declaration",
    "interface_declaration",
    "struct_item",
    "struct_specifier",
    "enum_item",
    "impl_item",
}
_BLOCK_NODES = _FUNCTION_NODES | _CLASS_NODES

_LANGUAGE_BY_SUFFIX = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".cxx": "cpp",
    ".go": "go",
    ".h": "c",
    ".hpp": "cpp",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".m": "objc",
    ".mm": "cpp",
    ".php": "php",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".sh": "bash",
    ".sql": "sql",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "tsx",
}


def _confined_source_path(repo_path: pathlib.Path, file_path: str) -> pathlib.Path:
    """Resolve a repository file without following a symlink outside root."""

    relative = validate_relative_file_path(file_path)
    root = pathlib.Path(repo_path).resolve(strict=True)
    candidate = (root / relative).resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError(f"source path escapes repository checkout: {file_path!r}")
    return candidate


def _changed_old_range(hunk: PatchHunk) -> tuple[int, int]:
    match = _HUNK_RANGE.search(hunk.header) or _HUNK_RANGE.search(hunk.raw_diff)
    if match is None:
        return 0, 0
    start = max(int(match.group("old_start")) - 1, 0)
    count = int(match.group("old_count") or "1")
    # A pure insertion is anchored at the preceding/current source line.
    end = start if count == 0 else start + count - 1
    return start, end


def _smallest_enclosing_block(root: Any, start_row: int, end_row: int) -> Any | None:
    candidates: list[Any] = []
    stack = [root]
    while stack:
        node = stack.pop()
        node_start = int(node.start_point[0])
        node_end = int(node.end_point[0])
        overlaps = node_start <= end_row and node_end >= start_row
        if not overlaps:
            continue
        if str(node.type) in _BLOCK_NODES:
            candidates.append(node)
        stack.extend(getattr(node, "named_children", ()))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda node: (
            int(node.end_point[0]) - int(node.start_point[0]),
            int(node.end_byte) - int(node.start_byte),
        ),
    )


def _node_name(node: Any, source: bytes, fallback: str) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        name = source[name_node.start_byte:name_node.end_byte].decode(
            "utf-8", errors="replace"
        )
        if name.strip():
            return name.strip()
    return fallback or str(node.type)


def _edit_status(hunk: PatchHunk) -> str:
    if hunk.added_lines and hunk.removed_lines:
        return "UPDATE"
    if hunk.added_lines:
        return "INSERT"
    return "DELETE"


def extract_changed_blocks(
    hunks: list[PatchHunk],
    repo_path: pathlib.Path,
) -> tuple[list[ChangedBlock], bool]:
    """Return multilingual changed blocks and backend availability.

    Individual file/parser errors are logged and skipped; they never cause a
    fabricated AST result. The caller can merge conservative hunk fallbacks.
    """

    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        return [], False

    blocks: list[ChangedBlock] = []
    seen: set[tuple[str, str, str]] = set()
    for hunk in hunks:
        try:
            source_path = _confined_source_path(repo_path, hunk.file_path)
            language = _LANGUAGE_BY_SUFFIX.get(source_path.suffix.lower())
            if not language:
                continue
            source = source_path.read_bytes()
            # Runtime values come from the closed mapping above. The optional
            # package exposes an exhaustive Literal type that mypy cannot
            # infer through a dict lookup.
            tree = get_parser(cast(Any, language)).parse(source)
            start_row, end_row = _changed_old_range(hunk)
            node = _smallest_enclosing_block(tree.root_node, start_row, end_row)
            if node is None:
                continue
            name = _node_name(node, source, hunk.function_context.strip())
            block_type = "class" if str(node.type) in _CLASS_NODES else "function"
            key = (hunk.file_path, name, _edit_status(hunk))
            if key in seen:
                continue
            seen.add(key)
            blocks.append(
                ChangedBlock(
                    file_path=hunk.file_path,
                    block_name=name,
                    block_type=block_type,
                    edit_status=_edit_status(hunk),
                    pre_source=source[node.start_byte:node.end_byte].decode(
                        "utf-8", errors="replace"
                    ),
                )
            )
        except (ImportError, LookupError, OSError, ValueError, RuntimeError) as exc:
            logger.warning(
                "tree-sitter analysis skipped %s hunk %s: %s",
                hunk.file_path,
                hunk.hunk_index,
                exc,
            )
    return blocks, True
