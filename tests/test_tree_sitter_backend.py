"""Offline contract tests for the optional public structural backend."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from bench_cleanser.analysis.structural_diff import compute_structural_diff
from bench_cleanser.analysis.tree_sitter_backend import extract_changed_blocks
from bench_cleanser.models import ParsedTask, PatchHunk, TaskRecord


class _Node:
    def __init__(
        self,
        node_type: str,
        start_row: int,
        end_row: int,
        start_byte: int,
        end_byte: int,
        *,
        children: list["_Node"] | None = None,
        name: "_Node | None" = None,
    ) -> None:
        self.type = node_type
        self.start_point = (start_row, 0)
        self.end_point = (end_row, 0)
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.named_children = children or []
        self._name = name

    def child_by_field_name(self, field: str) -> "_Node | None":
        return self._name if field == "name" else None


def _hunk() -> PatchHunk:
    return PatchHunk(
        file_path="src/example.py",
        hunk_index=0,
        header="@@ -2,2 +2,2 @@ def target():",
        added_lines=["+    return 2"],
        removed_lines=["-    return 1"],
        context_lines=[],
        function_context="def target():",
        raw_diff="@@ -2,2 +2,2 @@ def target():\n-    return 1\n+    return 2",
    )


def test_tree_sitter_backend_extracts_smallest_named_block(tmp_path, monkeypatch) -> None:
    source = "\ndef target():\n    return 1\n"
    source_path = tmp_path / "src" / "example.py"
    source_path.parent.mkdir()
    source_path.write_text(source, encoding="utf-8")

    name_start = source.index("target")
    name = _Node("identifier", 1, 1, name_start, name_start + len("target"))
    function = _Node(
        "function_definition",
        1,
        2,
        1,
        len(source),
        name=name,
    )
    root = _Node("module", 0, 3, 0, len(source), children=[function])
    parser = SimpleNamespace(parse=lambda _: SimpleNamespace(root_node=root))
    fake_package = SimpleNamespace(
        get_parser=lambda _: parser,
    )
    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", fake_package)

    blocks, available = extract_changed_blocks([_hunk()], tmp_path)

    assert available is True
    assert len(blocks) == 1
    assert blocks[0].block_name == "target"
    assert blocks[0].block_type == "function"
    assert "return 1" in blocks[0].pre_source


def test_tree_sitter_backend_does_not_follow_source_symlink_outside_repo(
    tmp_path,
    monkeypatch,
) -> None:
    outside = tmp_path.parent / "outside.py"
    outside.write_text("SECRET = 'must not be read'", encoding="utf-8")
    source_path = tmp_path / "src" / "example.py"
    source_path.parent.mkdir()
    source_path.symlink_to(outside)

    fake_package = SimpleNamespace(
        get_parser=lambda _: (_ for _ in ()).throw(AssertionError("must not parse")),
    )
    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", fake_package)

    blocks, available = extract_changed_blocks([_hunk()], tmp_path)

    assert available is True
    assert blocks == []


def test_installed_tree_sitter_extra_matches_backend_api(tmp_path) -> None:
    """Exercise the real optional package when the structural extra is installed."""

    pytest.importorskip("tree_sitter_language_pack")
    source_path = tmp_path / "src" / "example.py"
    source_path.parent.mkdir()
    source_path.write_text("\ndef target():\n    return 1\n", encoding="utf-8")

    blocks, available = extract_changed_blocks([_hunk()], tmp_path)

    assert available is True
    assert len(blocks) == 1
    assert blocks[0].block_name == "target"
    assert blocks[0].block_type == "function"
    assert "return 1" in blocks[0].pre_source


def test_structural_stage_uses_public_backend_when_installed(tmp_path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    source_path = tmp_path / "src" / "example.py"
    source_path.parent.mkdir()
    source_path.write_text("\ndef target():\n    return 1\n", encoding="utf-8")
    record = TaskRecord(
        instance_id="owner__repo-tree-sitter",
        repo="owner/repo",
        base_commit="a" * 40,
        patch="",
        test_patch="",
        problem_statement="Change target.",
        hints_text="",
        fail_to_pass=[],
        pass_to_pass=[],
        version="1",
    )
    parsed = ParsedTask(
        record=record,
        patch_hunks=[_hunk()],
        test_hunks=[],
        f2p_test_hunks=[],
        f2p_tests_with_no_hunk=[],
        files_in_gold_patch=["src/example.py"],
        files_in_test_patch=[],
    )

    structural = compute_structural_diff(parsed, tmp_path)

    assert structural.multilingual_ast_available is True
    assert len(structural.changed_blocks) == 1
    assert structural.changed_blocks[0].block_name == "target"
    assert "return 1" in structural.changed_blocks[0].pre_source


def test_structural_stage_falls_back_when_extra_is_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "src" / "example.py"
    source_path.parent.mkdir()
    source_path.write_text("\ndef target():\n    return 1\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", None)
    record = TaskRecord(
        instance_id="owner__repo-fallback",
        repo="owner/repo",
        base_commit="a" * 40,
        patch="",
        test_patch="",
        problem_statement="Change target.",
        hints_text="",
        fail_to_pass=[],
        pass_to_pass=[],
        version="1",
    )
    parsed = ParsedTask(
        record=record,
        patch_hunks=[_hunk()],
        test_hunks=[],
        f2p_test_hunks=[],
        f2p_tests_with_no_hunk=[],
        files_in_gold_patch=["src/example.py"],
        files_in_test_patch=[],
    )

    structural = compute_structural_diff(parsed, tmp_path)

    assert structural.multilingual_ast_available is False
    assert len(structural.changed_blocks) == 1
    assert structural.changed_blocks[0].block_name == "target"
    assert "return 1" in structural.changed_blocks[0].pre_source
