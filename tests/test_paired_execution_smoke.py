"""Offline checks for the paired Linux-container SymPy feasibility record."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import pathlib
import sys
import tarfile
from typing import Any

import pytest

SCRIPT = (
    pathlib.Path(__file__).parents[1]
    / "experiments"
    / "paired_execution_smoke"
    / "verify_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("paired_execution_smoke", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)


def _write_archive(
    path: pathlib.Path,
    entries: list[tuple[str, bytes, bytes | None]],
) -> None:
    """Write name/payload/link-target fixtures; a link target makes a symlink."""

    with tarfile.open(path, "w:gz") as handle:
        for name, payload, link_target in entries:
            info = tarfile.TarInfo(name)
            if link_target is None:
                info.size = len(payload)
                handle.addfile(info, io.BytesIO(payload))
            else:
                info.type = tarfile.SYMTYPE
                info.linkname = link_target.decode()
                handle.addfile(info)


def _passing_log() -> bytes:
    return (
        b"============================= test process starts ==============================\n"
        b"executable:         /opt/python/bin/python  (3.9.25-final-0) [CPython]\n"
        b"architecture:       64-bit\n"
        b"sympy/printing/tests/test_mathml.py[39] \n"
        b"test_presentation_symbol ok\n"
        b"================== tests finished: 39 passed, in 0.06 seconds ==================\n"
    )


def test_checked_in_manifest_is_strict_path_independent_and_narrow() -> None:
    manifest = smoke.load_manifest()
    smoke.verify_manifest(manifest)
    smoke.verify_local_independent_relation(manifest)

    classification = manifest["classification"]
    assert classification["prospective"] is False
    assert classification["official_swe_bench_image"] is False
    assert classification["supports_routing_claims"] is False
    assert classification["supports_hypotheses_h1_h6"] is False
    assert "/private/tmp/" not in SCRIPT.with_name("evidence-manifest.json").read_text()


def test_strict_json_and_schema_reject_duplicates_nonfinite_and_unknown_fields() -> None:
    with pytest.raises(smoke.EvidenceError, match="duplicate JSON key"):
        smoke.strict_json_loads('{"key": 1, "key": 2}')
    with pytest.raises(smoke.EvidenceError, match="non-finite"):
        smoke.strict_json_loads('{"key": NaN}')

    manifest = smoke.load_manifest()
    manifest["runtime"]["docker"]["unreviewed"] = True
    with pytest.raises(smoke.EvidenceError, match="unknown"):
        smoke.verify_manifest(manifest)


def test_manifest_identity_result_and_aggregate_tampering_are_rejected() -> None:
    manifest = smoke.load_manifest()
    manifest["runtime"]["image"]["id"] = "sha256:" + "0" * 64
    with pytest.raises(smoke.EvidenceError, match="runtime.image differs"):
        smoke.verify_manifest(manifest)

    manifest = smoke.load_manifest()
    manifest["runs"][3]["result"]["passed"] = 38
    with pytest.raises(smoke.EvidenceError, match="result differs"):
        smoke.verify_manifest(manifest)

    manifest = smoke.load_manifest()
    manifest["aggregate"]["passed_run_count"] += 1
    with pytest.raises(smoke.EvidenceError, match="derived from runs"):
        smoke.verify_manifest(manifest)


def test_test_summary_is_recomputed_and_ambiguous_or_impossible_logs_fail_closed() -> None:
    assert smoke._parse_log(_passing_log()) == smoke.PASS_RESULT

    wrong_total = _passing_log().replace(b"39 passed", b"40 passed")
    with pytest.raises(smoke.EvidenceError, match="total 39"):
        smoke._parse_log(wrong_total)

    duplicate_target = _passing_log() + b"test_presentation_symbol ok\n"
    with pytest.raises(smoke.EvidenceError, match="unambiguous"):
        smoke._parse_log(duplicate_target)


@pytest.mark.parametrize(
    "entries, message",
    [
        (
            [("paired-root/../escape", b"bad", None)],
            "unsafe archive member",
        ),
        (
            [
                ("paired-root/evidence.log", b"one", None),
                ("paired-root/evidence.log", b"two", None),
            ],
            "duplicate archive member",
        ),
        (
            [("paired-root/link", b"", b"target")],
            "non-regular archive member",
        ),
    ],
)
def test_archive_rejects_unsafe_duplicate_and_link_members(
    tmp_path: pathlib.Path,
    entries: list[tuple[str, bytes, bytes | None]],
    message: str,
) -> None:
    archive = tmp_path / "evidence.tar.gz"
    _write_archive(archive, entries)
    with pytest.raises(smoke.EvidenceError, match=message):
        smoke._read_archive_members(
            archive,
            root="paired-root",
            maximum_member_bytes=1_024,
        )


def test_archive_outer_identity_and_acquisition_duplicates_are_rejected(
    tmp_path: pathlib.Path,
) -> None:
    archive = tmp_path / "evidence.tar.gz"
    _write_archive(archive, [("paired-root/evidence.log", b"evidence", None)])
    with pytest.raises(smoke.EvidenceError, match="SHA-256 differs"):
        smoke._read_archive_members(
            archive,
            root="paired-root",
            maximum_member_bytes=1_024,
            expected_sha256="0" * 64,
        )

    header = (
        "role\trepeat\tstarted_at\tfinished_at\treturn_code\tlog_bytes\tlog_sha256\n"
    )
    row = (
        "baseline\t1\t2026-07-13T13:18:51Z\t2026-07-13T13:18:52Z\t1\t2080\t"
        + "0" * 64
        + "\n"
    )
    with pytest.raises(smoke.EvidenceError, match="duplicate acquisition"):
        smoke._parse_acquisitions((header + row + row).encode())


def test_supporting_member_identity_set_is_complete_and_nonoverlapping() -> None:
    manifest: dict[str, Any] = copy.deepcopy(smoke.load_manifest())
    expected = smoke._expected_member_identities(manifest)
    assert len(expected) == 24
    assert len(set(expected)) == 24
    assert "runner/run_paired_sympy.sh" in expected
    assert "raw/gold-repeat-3.log" in expected


def test_cli_verifies_manifest_without_reexecuting_docker(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["manifest_verified"] is True
    assert output["bundle_verified"] is False
