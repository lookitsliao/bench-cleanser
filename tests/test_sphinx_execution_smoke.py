"""Offline checks for the Sphinx 8475 feasibility-execution record."""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

SCRIPT = (
    pathlib.Path(__file__).parents[1]
    / "experiments"
    / "sphinx_execution_smoke"
    / "verify_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("sphinx_execution_smoke", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
previous_dont_write_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    SPEC.loader.exec_module(smoke)
finally:
    sys.dont_write_bytecode = previous_dont_write_bytecode


def test_checked_in_manifest_is_strict_and_path_independent() -> None:
    manifest = smoke.load_manifest()
    result = smoke.validate_manifest(manifest)

    assert result["manifest_valid"] is True
    assert manifest["classification"]["prospective"] is False
    assert manifest["classification"]["official_swe_bench_harness"] is False
    assert manifest["aggregate"]["model_discrimination_on_this_task"] is False
    assert "/private/tmp/" not in SCRIPT.with_name("evidence-manifest.json").read_text()


def test_strict_json_and_schema_reject_duplicate_or_unknown_fields() -> None:
    with pytest.raises(smoke.EvidenceError, match="duplicate JSON key"):
        smoke.strict_json_loads('{"key": 1, "key": 2}')

    manifest = smoke.load_manifest()
    manifest["unsupported_claim"] = True
    with pytest.raises(smoke.EvidenceError, match="unknown"):
        smoke.validate_manifest(manifest)


def test_claim_cannot_drop_bring_up_or_no_discrimination_caveats() -> None:
    manifest = smoke.load_manifest()
    manifest["protocol_state"]["precursor_bring_up"]["scored"] = True
    with pytest.raises(smoke.EvidenceError, match="precursor_bring_up.scored"):
        smoke.validate_manifest(manifest)

    manifest = smoke.load_manifest()
    manifest["aggregate"]["model_discrimination_on_this_task"] = True
    with pytest.raises(smoke.EvidenceError, match="aggregate"):
        smoke.validate_manifest(manifest)


def test_patch_or_outcome_relabeling_is_rejected() -> None:
    manifest = smoke.load_manifest()
    manifest["task"]["patches"][2]["sha256"] = "0" * 64
    with pytest.raises(smoke.EvidenceError, match=r"patches\[kimi_k2\]"):
        smoke.validate_manifest(manifest)

    manifest = smoke.load_manifest()
    manifest["results"][0]["target_status_each"] = "passed"
    with pytest.raises(smoke.EvidenceError, match="results"):
        smoke.validate_manifest(manifest)


def test_junit_parser_rejects_entities_and_recomputes_cases() -> None:
    with pytest.raises(smoke.EvidenceError, match="forbidden XML"):
        smoke._parse_junit(
            b'<!DOCTYPE x [<!ENTITY e "value">]><testsuite/>',
            "unsafe.xml",
        )

    parsed = smoke._parse_junit(
        b'<testsuites><testsuite><testcase classname="tests.test_build_linkcheck" '
        b'name="test_defaults"/></testsuite></testsuites>',
        "safe.xml",
    )
    assert parsed == {
        "counts": {"passed": 1, "failed": 0, "error": 0, "skipped": 0},
        "cases": [
            {
                "classname": "tests.test_build_linkcheck",
                "name": "test_defaults",
                "status": "passed",
            }
        ],
    }


def test_results_document_preserves_the_claim_boundary() -> None:
    results = SCRIPT.with_name("RESULTS.md").read_text()
    readme = SCRIPT.with_name("README.md").read_text()

    assert "255/255 P2P checks passed" in results
    assert "no candidate or\nmodel discrimination" in readme
    assert "not the official SWE-bench harness" in results
    assert smoke.BUNDLE_SHA256 in readme
