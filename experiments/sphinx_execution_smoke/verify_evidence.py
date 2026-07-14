#!/usr/bin/env python3
"""Verify the Sphinx 8475 container-free feasibility-execution record.

The checked-in manifest is the path-independent claim.  When the external
content-addressed bundle is supplied, this verifier also checks its complete
member set, every stream and JUnit digest, request identities, source-tree
receipts, and recomputes all 15 outcomes from the raw XML.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import sys
import tarfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "sphinx-execution-smoke-0.1.0"
STUDY_ID = "sphinx-8475-container-free-post-draft-pre-freeze-feasibility-v2"
MANIFEST_PATH = pathlib.Path(__file__).with_name("evidence-manifest.json")

BUNDLE_BYTES = 27_754
BUNDLE_SHA256 = "a6fef4316b9e60759b35eb9ecad27a1a162c80c9265e6746a4eb29041fba3a5b"
BUNDLE_ROOT = "bench-cleanser-independent-sphinx-8475-v2-evidence"
INDEX_BYTES = 12_519
INDEX_SHA256 = "4ade708a0ca31acdb4a4240ffbb2da9b928a0ed8895124f4abe745039aca30f9"
ENVIRONMENT_BYTES = 1_409
ENVIRONMENT_SHA256 = "59a3c04eeeb79b220b14d21faedd11eb12f371e5c6d7465dfd4567480ea8a4aa"
RUNNER_BYTES = 21_259
RUNNER_SHA256 = "08eebf973976003166567667f5bddd90c067d452257701179526b86a0b0ef118"

TARGET = "tests/test_build_linkcheck.py::test_TooManyRedirects_on_HEAD"
EXTERNAL_P2P = (
    "tests/test_build_linkcheck.py::test_defaults",
    "tests/test_build_linkcheck.py::test_defaults_json",
    "tests/test_build_linkcheck.py::test_anchors_ignored",
)
LOCAL_P2P = (
    "tests/test_build_linkcheck.py::test_raises_for_invalid_status",
    "tests/test_build_linkcheck.py::test_auth_header_uses_first_match",
    "tests/test_build_linkcheck.py::test_auth_header_no_match",
    "tests/test_build_linkcheck.py::test_linkcheck_request_headers",
    "tests/test_build_linkcheck.py::test_linkcheck_request_headers_no_slash",
    "tests/test_build_linkcheck.py::test_linkcheck_request_headers_default",
    "tests/test_build_linkcheck.py::test_follows_redirects_on_HEAD",
    "tests/test_build_linkcheck.py::test_follows_redirects_on_GET",
    "tests/test_build_linkcheck.py::test_invalid_ssl",
    "tests/test_build_linkcheck.py::test_connect_to_selfsigned_fails",
    "tests/test_build_linkcheck.py::test_connect_to_selfsigned_with_tls_verify_false",
    "tests/test_build_linkcheck.py::test_connect_to_selfsigned_with_tls_cacerts",
    "tests/test_build_linkcheck.py::test_connect_to_selfsigned_with_requests_env_var",
    "tests/test_build_linkcheck.py::test_connect_to_selfsigned_nonexistent_cert_file",
)
ALL_P2P = EXTERNAL_P2P + LOCAL_P2P

SCHEDULE = (
    (1, "baseline"),
    (1, "gpt5"),
    (1, "kimi_k2"),
    (1, "claude_4_sonnet"),
    (1, "gold"),
    (2, "gold"),
    (2, "claude_4_sonnet"),
    (2, "kimi_k2"),
    (2, "gpt5"),
    (2, "baseline"),
    (3, "kimi_k2"),
    (3, "baseline"),
    (3, "claude_4_sonnet"),
    (3, "gold"),
    (3, "gpt5"),
)

TREE_DIGESTS = {
    "baseline": "3d5ce696b4db6fffbd3c4b0b01f59e17e9645e5981f184742c2d8ca6de7e4909",
    "gpt5": "20ebd9cdb23bec46e1385add90b6dcb6f3c8578295afa0bbfbc7d82dca3b98ed",
    "kimi_k2": "ade4ebe3f0459054c0a1a56577241e5a37f0564b2224ea8ebcee8365aff7262f",
    "claude_4_sonnet": "32fa6988d6be5b699cc7d2a1f14b1576d847a47fea191842ed2e98f8ae9bcb65",
    "gold": "20ebd9cdb23bec46e1385add90b6dcb6f3c8578295afa0bbfbc7d82dca3b98ed",
}

PATCHES = {
    "gold": {
        "role": "canonical_gold_sanity_control",
        "bytes": 994,
        "sha256": "cf0c7fdff6180321a596c744be627230af58acbaa9e2c7aa3b3105a32e73a658",
        "source_submission_id": None,
        "source_url": None,
        "functional_diff_matches_gold": True,
        "unscored_extra_files": 0,
    },
    "gpt5": {
        "role": "candidate",
        "bytes": 1_072,
        "sha256": "8a9725217a4d60e5794753427717c89fa9dd4de3b5d3a743bb4e728ae7efa317",
        "source_submission_id": "20250807_openhands_gpt5",
        "source_url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            "20250807_openhands_gpt5/logs/sphinx-doc__sphinx-8475/patch.diff"
        ),
        "functional_diff_matches_gold": True,
        "unscored_extra_files": 0,
    },
    "kimi_k2": {
        "role": "candidate",
        "bytes": 25_646,
        "sha256": "9c31db10b7f534e4acbfe4d0bfc4182db78ab6e18f701402b73c49e008854ad8",
        "source_submission_id": "20250716_openhands_kimi_k2",
        "source_url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            "20250716_openhands_kimi_k2/logs/sphinx-doc__sphinx-8475/patch.diff"
        ),
        "functional_diff_matches_gold": True,
        "unscored_extra_files": 4,
    },
    "claude_4_sonnet": {
        "role": "candidate",
        "bytes": 19_740,
        "sha256": "f72188ee8d45ca089db5964c52b78740bb9d6315b0c6a65a5682f5a0f953457f",
        "source_submission_id": "20250524_openhands_claude_4_sonnet",
        "source_url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            "20250524_openhands_claude_4_sonnet/logs/sphinx-doc__sphinx-8475/patch.diff"
        ),
        "functional_diff_matches_gold": True,
        "unscored_extra_files": 3,
    },
}

EXPECTED_CLASSIFICATION = {
    "stage": "post_draft_pre_freeze_feasibility_execution",
    "claim_scope": "container_free_infrastructure_bring_up_only",
    "prospective": False,
    "blinded": False,
    "official_swe_bench_harness": False,
    "official_swe_bench_image": False,
    "task_count": 1,
    "candidate_count": 3,
    "repeat_count_per_variant": 3,
    "observation_count": 15,
    "phase_execution_count": 30,
    "supports_routing_claims": False,
    "supports_hypotheses_h1_h6": False,
}

EXPECTED_RESULTS = (
    {
        "variant": "baseline",
        "role": "base_plus_oracle_test_patch_control",
        "input_patch_sha256": None,
        "repeats": 3,
        "p2p_passed_each": 17,
        "p2p_total_each": 17,
        "target_status_each": "failed",
        "local_phase_return_code_each": 1,
        "supports": "incorrect",
    },
    *(
        {
            "variant": role,
            "role": "candidate",
            "input_patch_sha256": PATCHES[role]["sha256"],
            "repeats": 3,
            "p2p_passed_each": 17,
            "p2p_total_each": 17,
            "target_status_each": "passed",
            "local_phase_return_code_each": 0,
            "supports": "correct",
        }
        for role in ("gpt5", "kimi_k2", "claude_4_sonnet")
    ),
    {
        "variant": "gold",
        "role": "canonical_gold_sanity_control",
        "input_patch_sha256": PATCHES["gold"]["sha256"],
        "repeats": 3,
        "p2p_passed_each": 17,
        "p2p_total_each": 17,
        "target_status_each": "passed",
        "local_phase_return_code_each": 0,
        "supports": "correct",
    },
)

EXPECTED_AGGREGATE = {
    "valid_observations": 15,
    "expected_observations": 15,
    "p2p_passes": 255,
    "p2p_checks": 255,
    "baseline_target_failures": 3,
    "candidate_target_passes": 9,
    "gold_target_passes": 3,
    "candidate_disagreement": False,
    "model_discrimination_on_this_task": False,
}

EXPECTED_LIMITATIONS = (
    "one manually selected task; no population, calibration, cost, or routing estimate",
    "post-draft/pre-freeze retrospective feasibility execution; no clean-commit or registration freeze",
    "candidate patches and hosted labels were accessible before selection and execution; not blinded",
    "the runner and runtime were revised after unscored bring-up failures",
    "container-free macOS arm64 Python 3.9 substrate; no container or Linux equivalence claim",
    "not the official SWE-bench harness or official environment image",
    "the exact 18 scored tests were split into external and localhost phases because the managed proxy otherwise intercepts localhost",
    "the three public-link P2P tests depend on mutable external network responses",
    "dependency versions were reconstructed in 2026 and differ from the historical official image",
    "source files were read-only and complete trees were hashed before and after each phase; directories remained writable for copied-fixture build directories",
    "memory usage was not kernel-limited",
    "all three candidates implement the same functional two-line change as gold, so the task supplies no candidate discrimination",
    "Kimi K2 and Claude add unscored root-level test scripts that were present but not collected by the explicit SWE-bench node list",
    "the GPT-5 hosted report was unavailable in the matched acquisition, so hosted-label corroboration is incomplete",
    "gold is only a base-fails/gold-passes sanity control; execution does not establish semantic truth",
    "no routing evidence and no evidence for hypotheses H1-H6",
)

RAW_LIMITATIONS = (
    "one manually selected task; no population or routing estimate",
    "post-draft/pre-freeze retrospective feasibility execution; no clean-commit or registration freeze",
    "candidate patches and hosted labels were accessible before selection and execution; not blinded",
    "container-free macOS arm64 Python 3.9 substrate; no container or Linux equivalence claim",
    "not the official SWE-bench harness or official environment image",
    "the exact 18 scored tests were split into external and localhost phases because the managed proxy otherwise intercepts localhost",
    "the three external-link P2P tests depend on mutable public network responses",
    "dependency versions were reconstructed in 2026 and differ from the historical official image",
    "source files were read-only and complete trees were hashed before and after each phase; directories remained writable for copied-fixture build directories",
    "memory usage was not kernel-limited",
    "gold is only a base-fails/gold-passes sanity control; execution does not establish semantic truth",
    "hosted agreement is retrospective corroboration, not prospective evidence",
    "no routing evidence and no evidence for hypotheses H1-H6",
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ACQUISITION_RE = re.compile(r"acq-[0-9a-f]{32}\Z")


class EvidenceError(ValueError):
    """The checked-in claim or supplied raw evidence is invalid."""


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise EvidenceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise EvidenceError(f"non-finite JSON number: {value}")


def strict_json_loads(payload: bytes | str) -> Any:
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    except UnicodeDecodeError as exc:
        raise EvidenceError("JSON is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"invalid JSON: {exc}") from exc


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _as_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvidenceError(f"{path} must be an object")
    return value


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceError(f"{path} must be an array")
    return value


def _keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise EvidenceError(
            f"{path} keys differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _equal(actual: Any, expected: Any, path: str) -> None:
    if actual != expected:
        raise EvidenceError(f"{path} differs: expected {expected!r}, got {actual!r}")


def _digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise EvidenceError(f"{path} must be a lowercase SHA-256")
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvidenceError(f"{path} must be a positive integer")
    return value


def load_manifest(path: pathlib.Path = MANIFEST_PATH) -> dict[str, Any]:
    return _as_dict(strict_json_loads(path.read_bytes()), "manifest")


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    _keys(
        manifest,
        {
            "schema_version",
            "study_id",
            "classification",
            "protocol_state",
            "task",
            "sources",
            "preparation",
            "runtime",
            "execution_contract",
            "evidence_bundle",
            "results",
            "aggregate",
            "limitations",
        },
        "manifest",
    )
    _equal(manifest["schema_version"], SCHEMA_VERSION, "schema_version")
    _equal(manifest["study_id"], STUDY_ID, "study_id")
    _equal(manifest["classification"], EXPECTED_CLASSIFICATION, "classification")

    protocol = _as_dict(manifest["protocol_state"], "protocol_state")
    _keys(
        protocol,
        {
            "selection",
            "registration_freeze",
            "clean_commit_freeze",
            "bench_cleanser_commit",
            "bench_cleanser_tree",
            "precursor_bring_up",
        },
        "protocol_state",
    )
    _equal(
        protocol["selection"],
        "manual_feasibility_selection_after_candidate_patches_and_hosted_outcomes_were_available",
        "protocol_state.selection",
    )
    _equal(protocol["registration_freeze"], None, "protocol_state.registration_freeze")
    _equal(protocol["clean_commit_freeze"], None, "protocol_state.clean_commit_freeze")
    _equal(
        protocol["bench_cleanser_commit"],
        "0f82a1d2739fce5600bb481bac2a2c2c96630462",
        "protocol_state.bench_cleanser_commit",
    )
    _equal(
        protocol["bench_cleanser_tree"],
        "concurrently_dirty_and_not_a_claim_identity",
        "protocol_state.bench_cleanser_tree",
    )
    precursor = _as_dict(protocol["precursor_bring_up"], "protocol_state.precursor_bring_up")
    _keys(precursor, {"scored", "included_in_evidence_bundle", "events", "consequence"}, "protocol_state.precursor_bring_up")
    _equal(precursor["scored"], False, "protocol_state.precursor_bring_up.scored")
    _equal(
        precursor["included_in_evidence_bundle"],
        False,
        "protocol_state.precursor_bring_up.included_in_evidence_bundle",
    )
    _equal(
        precursor["events"],
        [
            "an unscored dependency preflight exposed incompatible docutils 0.23; the final runtime pins docutils 0.16",
            "an unscored v1 acquisition produced setup errors because the explicit pytest basetemp parent did not exist",
            "an unscored source-mode preflight showed that fully read-only fixture directories prevent temporary _build creation",
        ],
        "protocol_state.precursor_bring_up.events",
    )
    _equal(
        precursor["consequence"],
        "the v2 runner, runtime, source modes, and acquisition were revised after these failures; the result is feasibility evidence, not a prospective estimate",
        "protocol_state.precursor_bring_up.consequence",
    )

    task = _as_dict(manifest["task"], "task")
    _keys(
        task,
        {
            "instance_id",
            "repository",
            "version",
            "base_commit",
            "base_tree",
            "environment_setup_commit",
            "canonical_row",
            "oracle_tests",
            "patches",
        },
        "task",
    )
    expected_identity = {
        "instance_id": "sphinx-doc__sphinx-8475",
        "repository": "sphinx-doc/sphinx",
        "version": "3.4",
        "base_commit": "3ea1ec84cc610f7a9f4f6b354e264565254923ff",
        "base_tree": "3532e3bb4c25e44e2741eb63b5b634207583c743",
        "environment_setup_commit": "3f560cd67239f75840cc7a439ab54d8509c855f6",
    }
    for key, expected in expected_identity.items():
        _equal(task[key], expected, f"task.{key}")
    _equal(
        task["canonical_row"],
        {
            "serialization": "utf8-json-sort-keys-compact-all-canonical-columns-v1",
            "bytes": 4_777,
            "sha256": "ef2433e6fe3ae26641615610f6dfa3ae389267771456c67f013f4b4f5268986b",
        },
        "task.canonical_row",
    )
    _equal(
        task["oracle_tests"],
        {
            "test_patch_bytes": 1_277,
            "test_patch_sha256": "805ddf0fe1635f793420f7e16d069d216c3078aa2d0f7d70900c75809b3e0d9a",
            "test_patch_files": ["tests/test_build_linkcheck.py"],
            "fail_to_pass": [TARGET],
            "pass_to_pass": list(ALL_P2P),
        },
        "task.oracle_tests",
    )
    patches = _as_list(task["patches"], "task.patches")
    _equal([patch.get("variant") if isinstance(patch, dict) else None for patch in patches], ["gold", "gpt5", "kimi_k2", "claude_4_sonnet"], "task.patches order")
    for patch in patches:
        item = _as_dict(patch, "task.patches[]")
        variant = item.get("variant")
        if not isinstance(variant, str) or variant not in PATCHES:
            raise EvidenceError(f"unexpected task patch variant: {variant!r}")
        _equal(item, {"variant": variant, **PATCHES[variant]}, f"task.patches[{variant}]")

    sources = _as_dict(manifest["sources"], "sources")
    _keys(sources, {"canonical_dataset", "base_source_archive"}, "sources")
    dataset = _as_dict(sources["canonical_dataset"], "sources.canonical_dataset")
    _equal(
        dataset,
        {
            "dataset_id": "princeton-nlp/SWE-bench_Verified",
            "split": "test",
            "revision": "c104f840cc67f8b6eec6f759ebc8b2693d585d4a",
            "authoritative_url": "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/c104f840cc67f8b6eec6f759ebc8b2693d585d4a/data/test-00000-of-00001.parquet",
            "retrieval_url": "https://raw.githubusercontent.com/justin-napolitano/SWE-bench_Verified/f34deb86cca28b6050f181f5514a3eb7d7d70be4/data/test-00000-of-00001.parquet",
            "retrieval_revision": "f34deb86cca28b6050f181f5514a3eb7d7d70be4",
            "bytes": 2_096_679,
            "sha256": "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd",
        },
        "sources.canonical_dataset",
    )
    base_archive = _as_dict(sources["base_source_archive"], "sources.base_source_archive")
    _equal(
        base_archive,
        {
            "logical_filename": "sphinx-8475-3ea1ec84cc61.tar.gz",
            "bytes": 5_973_385,
            "sha256": "2e88bac2c9e5807f6435e790066b52263dbf3e872d7c3807e49fe1fd3d0dea71",
            "commit": "3ea1ec84cc610f7a9f4f6b354e264565254923ff",
            "tree": "3532e3bb4c25e44e2741eb63b5b634207583c743",
            "acquisition_url": None,
            "acquisition_url_receipt": "not_recorded",
        },
        "sources.base_source_archive",
    )

    preparation = _as_dict(manifest["preparation"], "preparation")
    _keys(
        preparation,
        {
            "ordered_steps",
            "candidate_test_patch_overlap",
            "official_reset_semantics_required",
            "source_trees",
            "gpt5_and_gold_complete_tree_identity",
        },
        "preparation",
    )
    _equal(preparation["candidate_test_patch_overlap"], False, "preparation.candidate_test_patch_overlap")
    _equal(preparation["official_reset_semantics_required"], False, "preparation.official_reset_semantics_required")
    _equal(preparation["source_trees"], TREE_DIGESTS, "preparation.source_trees")
    _equal(preparation["gpt5_and_gold_complete_tree_identity"], True, "preparation.gpt5_and_gold_complete_tree_identity")
    _equal(
        preparation["ordered_steps"],
        [
            "extract exact base source archive into a fresh per-role tree",
            "apply exact oracle test patch",
            "apply exact candidate patch, canonical gold patch, or no implementation patch for baseline",
            "remove write permission from source files while leaving directories writable for fixture copies",
            "compute a path-independent complete tree digest",
            "execute explicit scored node IDs with bytecode and pytest cache disabled",
            "recompute the complete tree digest before and after each phase",
        ],
        "preparation.ordered_steps",
    )

    runtime = _as_dict(manifest["runtime"], "runtime")
    _keys(runtime, {"substrate", "python", "key_dependencies", "environment_record"}, "runtime")
    _equal(
        runtime["substrate"],
        {
            "containerized": False,
            "os": "macOS",
            "platform": "macOS-26.5.1-arm64-arm-64bit",
            "architecture": "arm64",
        },
        "runtime.substrate",
    )
    _equal(
        runtime["python"],
        {
            "distribution": "python-build-standalone install_only",
            "version": "3.9.25",
            "archive_url": "https://github.com/astral-sh/python-build-standalone/releases/download/20251031/cpython-3.9.25%2B20251031-aarch64-apple-darwin-install_only.tar.gz",
            "archive_bytes": 18_471_356,
            "archive_sha256": "87275619c2706affa4d1090d2ca3dad354b6d69f8b85dbfafe38785870751b9a",
            "binary_bytes": 50_152,
            "binary_sha256": "26d9b2c90785be815d334df56afee46ff69fc6c24b006311d78597ad445ab267",
        },
        "runtime.python",
    )
    _equal(
        runtime["environment_record"],
        {"bytes": ENVIRONMENT_BYTES, "sha256": ENVIRONMENT_SHA256},
        "runtime.environment_record",
    )
    dependencies = _as_list(runtime["key_dependencies"], "runtime.key_dependencies")
    _equal(
        dependencies,
        [
            "docutils==0.16",
            "Jinja2==2.11.3",
            "MarkupSafe==2.0.1",
            "pytest==8.4.2",
            "requests==2.32.5",
            "Sphinx==3.4.0.dev20260713 editable source selected by PYTHONPATH",
        ],
        "runtime.key_dependencies",
    )

    contract = _as_dict(manifest["execution_contract"], "execution_contract")
    _keys(
        contract,
        {
            "shell",
            "phase_split_reason",
            "external_phase",
            "local_phase",
            "pytest_argv_template",
            "environment_policy",
            "limits",
            "schedule",
        },
        "execution_contract",
    )
    _equal(contract["shell"], False, "execution_contract.shell")
    _equal(
        contract["phase_split_reason"],
        "the managed external egress proxy intercepts localhost unless localhost is explicitly excluded; public-link P2P and localhost tests therefore require distinct proxy policies",
        "execution_contract.phase_split_reason",
    )
    external_phase = _as_dict(contract["external_phase"], "execution_contract.external_phase")
    _equal(
        external_phase,
        {
            "test_count": 3,
            "node_ids": list(EXTERNAL_P2P),
            "network_policy": "managed_external_egress_for_three_canonical_p2p_tests",
        },
        "execution_contract.external_phase",
    )
    local_phase = _as_dict(contract["local_phase"], "execution_contract.local_phase")
    _equal(
        local_phase,
        {
            "test_count": 15,
            "p2p_count": 14,
            "f2p_count": 1,
            "network_policy": "localhost_explicitly_excluded_from_managed_proxy",
        },
        "execution_contract.local_phase",
    )
    _equal(
        contract["pytest_argv_template"],
        [
            "{python}",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            "{scratch}",
            "--junitxml",
            "{junit}",
            "-q",
            "-ra",
            "{explicit_node_ids}",
        ],
        "execution_contract.pytest_argv_template",
    )
    _equal(
        contract["environment_policy"],
        "minimal_allowlist_with_phase_specific_proxy_keys",
        "execution_contract.environment_policy",
    )
    _equal(
        contract["limits"],
        {
            "cpu_seconds_per_phase": 60,
            "wall_seconds_per_phase": 60,
            "open_files": 256,
            "processes": 256,
            "file_bytes": 52_428_800,
            "memory": "not_enforced",
        },
        "execution_contract.limits",
    )
    schedule = _as_list(contract["schedule"], "execution_contract.schedule")
    _equal(schedule, [[repeat, role] for repeat, role in SCHEDULE], "execution_contract.schedule")

    evidence = _as_dict(manifest["evidence_bundle"], "evidence_bundle")
    _equal(
        evidence,
        {
            "logical_filename": "bench-cleanser-independent-sphinx-8475-v2-evidence.tar.gz",
            "media_type": "application/gzip",
            "bytes": BUNDLE_BYTES,
            "sha256": BUNDLE_SHA256,
            "root_directory": BUNDLE_ROOT,
            "file_member_count": 138,
            "directory_member_count": 18,
            "maximum_file_member_bytes": RUNNER_BYTES,
            "index": {"path": "index.json", "bytes": INDEX_BYTES, "sha256": INDEX_SHA256},
            "runner": {"path": "runner.py", "bytes": RUNNER_BYTES, "sha256": RUNNER_SHA256},
            "location_contract": "external_content_addressed_artifact; no mutable local path is canonical",
        },
        "evidence_bundle",
    )
    _equal(manifest["results"], list(EXPECTED_RESULTS), "results")
    _equal(manifest["aggregate"], EXPECTED_AGGREGATE, "aggregate")
    _equal(manifest["limitations"], list(EXPECTED_LIMITATIONS), "limitations")
    return {
        "study_id": STUDY_ID,
        "manifest_valid": True,
        "bundle_required": False,
        "observations": 15,
    }


def _member_sets() -> tuple[set[str], set[str]]:
    directories = {BUNDLE_ROOT, f"{BUNDLE_ROOT}/observations", f"{BUNDLE_ROOT}/scratch"}
    files = {
        f"{BUNDLE_ROOT}/environment.json",
        f"{BUNDLE_ROOT}/index.json",
        f"{BUNDLE_ROOT}/runner.py",
    }
    for repeat, role in SCHEDULE:
        prefix = f"{BUNDLE_ROOT}/observations/{repeat:02d}-{role}"
        directories.add(prefix)
        files.add(f"{prefix}/observation.json")
        for phase in ("external", "local"):
            for suffix in ("junit.xml", "record.json", "stderr.txt", "stdout.txt"):
                files.add(f"{prefix}/{phase}.{suffix}")
    return directories, files


def _read_bundle(path: pathlib.Path) -> dict[str, bytes]:
    payload = path.read_bytes()
    _equal(len(payload), BUNDLE_BYTES, "bundle bytes")
    _equal(sha256(payload), BUNDLE_SHA256, "bundle sha256")
    expected_directories, expected_files = _member_sets()
    files: dict[str, bytes] = {}
    seen: set[str] = set()
    directories: set[str] = set()
    try:
        with tarfile.open(fileobj=__import__("io").BytesIO(payload), mode="r:gz") as archive:
            members = archive.getmembers()
            _equal(len(members), len(expected_directories) + len(expected_files), "bundle member count")
            for member in members:
                name = member.name.rstrip("/")
                pure = pathlib.PurePosixPath(name)
                if (
                    not name
                    or name.startswith("/")
                    or pure.is_absolute()
                    or ".." in pure.parts
                    or "" in pure.parts
                ):
                    raise EvidenceError(f"unsafe archive member: {member.name!r}")
                if name in seen:
                    raise EvidenceError(f"duplicate archive member: {name}")
                seen.add(name)
                if member.isdir():
                    directories.add(name)
                    continue
                if not member.isfile():
                    raise EvidenceError(f"archive member is not a regular file: {name}")
                if member.size > RUNNER_BYTES:
                    raise EvidenceError(f"archive member exceeds size ceiling: {name}")
                stream = archive.extractfile(member)
                if stream is None:
                    raise EvidenceError(f"cannot read archive member: {name}")
                value = stream.read(RUNNER_BYTES + 1)
                if len(value) != member.size:
                    raise EvidenceError(f"archive member size drift: {name}")
                files[name] = value
    except (tarfile.TarError, OSError) as exc:
        raise EvidenceError(f"invalid evidence bundle: {exc}") from exc
    _equal(directories, expected_directories, "bundle directories")
    _equal(set(files), expected_files, "bundle files")
    return files


def _raw_inputs() -> dict[str, dict[str, Any]]:
    return {
        "source_archive": {
            "bytes": 5_973_385,
            "sha256": "2e88bac2c9e5807f6435e790066b52263dbf3e872d7c3807e49fe1fd3d0dea71",
            "scratch_path_suffix": "sphinx-8475-3ea1ec84cc61.tar.gz",
        },
        "runtime_archive": {
            "bytes": 18_471_356,
            "sha256": "87275619c2706affa4d1090d2ca3dad354b6d69f8b85dbfafe38785870751b9a",
            "scratch_path_suffix": "bench-cleanser-python39-20251031.tar.gz",
        },
        "runtime_binary": {
            "bytes": 50_152,
            "sha256": "26d9b2c90785be815d334df56afee46ff69fc6c24b006311d78597ad445ab267",
            "scratch_path_suffix": "python",
        },
        "dataset": {
            "bytes": 2_096_679,
            "sha256": "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd",
            "scratch_path_suffix": "swe-bench-verified-c104f840.parquet",
        },
        "test_patch": {
            "bytes": 1_277,
            "sha256": "805ddf0fe1635f793420f7e16d069d216c3078aa2d0f7d70900c75809b3e0d9a",
            "scratch_path_suffix": "test.patch",
        },
        "gold_patch": {
            "bytes": 994,
            "sha256": PATCHES["gold"]["sha256"],
            "scratch_path_suffix": "gold.patch",
        },
        **{
            f"{role}_patch": {
                "bytes": PATCHES[role]["bytes"],
                "sha256": PATCHES[role]["sha256"],
                "scratch_path_suffix": "patch.diff",
            }
            for role in ("gpt5", "kimi_k2", "claude_4_sonnet")
        },
    }


def _raw_task() -> dict[str, Any]:
    return {
        "instance_id": "sphinx-doc__sphinx-8475",
        "repository": "sphinx-doc/sphinx",
        "version": "3.4",
        "base_commit": "3ea1ec84cc610f7a9f4f6b354e264565254923ff",
        "base_tree": "3532e3bb4c25e44e2741eb63b5b634207583c743",
        "environment_setup_commit": "3f560cd67239f75840cc7a439ab54d8509c855f6",
        "canonical_row_bytes": 4_777,
        "canonical_row_sha256": "ef2433e6fe3ae26641615610f6dfa3ae389267771456c67f013f4b4f5268986b",
        "fail_to_pass": [TARGET],
        "pass_to_pass": list(ALL_P2P),
    }


def _raw_classification() -> dict[str, Any]:
    return {
        "stage": "post_draft_pre_freeze_feasibility_execution",
        "claim_scope": "container_free_infrastructure_bring_up_only",
        "prospective": False,
        "blinded": False,
        "task_count": 1,
        "candidate_count": 3,
        "repeat_count_per_variant": 3,
        "observation_count": 15,
        "phase_execution_count": 30,
    }


def _expected_observation(repeat: int, role: str) -> dict[str, Any]:
    target_status = "failed" if role == "baseline" else "passed"
    return {
        "schema_version": "sphinx-execution-observation-0.1.0",
        "study_id": STUDY_ID,
        "role": role,
        "repeat": repeat,
        "source_tree_sha256": TREE_DIGESTS[role],
        "phase_record_paths": [
            f"observations/{repeat:02d}-{role}/external.record.json",
            f"observations/{repeat:02d}-{role}/local.record.json",
        ],
        "p2p_passed": 17,
        "p2p_total": 17,
        "target_status": target_status,
        "supports": "incorrect" if role == "baseline" else "correct",
        "valid": True,
    }


def _validate_environment(payload: bytes) -> None:
    _equal(len(payload), ENVIRONMENT_BYTES, "environment bytes")
    _equal(sha256(payload), ENVIRONMENT_SHA256, "environment sha256")
    value = _as_dict(strict_json_loads(payload), "environment")
    _keys(value, {"python_binary_sha256", "runner_platform", "runtime"}, "environment")
    _equal(
        value["python_binary_sha256"],
        "26d9b2c90785be815d334df56afee46ff69fc6c24b006311d78597ad445ab267",
        "environment.python_binary_sha256",
    )
    _equal(value["runner_platform"], "macOS-26.5.1-arm64-arm-64bit", "environment.runner_platform")
    runtime = _as_dict(value["runtime"], "environment.runtime")
    _keys(runtime, {"packages", "platform", "python"}, "environment.runtime")
    _equal(runtime["platform"], "macOS-26.5.1-arm64-arm-64bit", "environment.runtime.platform")
    if not isinstance(runtime["python"], str) or not runtime["python"].startswith("3.9.25 "):
        raise EvidenceError("environment.runtime.python is not Python 3.9.25")
    packages = _as_list(runtime["packages"], "environment.runtime.packages")
    pairs: list[tuple[str, str]] = []
    for index, package in enumerate(packages):
        values = _as_list(package, f"environment.runtime.packages[{index}]")
        if len(values) != 2 or not all(isinstance(item, str) for item in values):
            raise EvidenceError(f"environment.runtime.packages[{index}] is invalid")
        pairs.append((values[0], values[1]))
    if len(pairs) != len(set(pairs)):
        raise EvidenceError("environment package inventory contains duplicates")
    required = {
        ("docutils", "0.16"),
        ("Jinja2", "2.11.3"),
        ("MarkupSafe", "2.0.1"),
        ("pytest", "8.4.2"),
        ("requests", "2.32.5"),
        ("Sphinx", "3.4.0.dev20260713"),
    }
    if not required.issubset(set(pairs)):
        raise EvidenceError("environment package inventory lacks a required exact dependency")


def _parse_junit(payload: bytes, path: str) -> dict[str, Any]:
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise EvidenceError(f"{path} contains a forbidden XML declaration")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise EvidenceError(f"invalid JUnit XML at {path}: {exc}") from exc
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise EvidenceError(f"{path} contains no test suite")
    cases: list[dict[str, str]] = []
    for suite in suites:
        for case in suite.findall("testcase"):
            status = "passed"
            if case.find("failure") is not None:
                status = "failed"
            elif case.find("error") is not None:
                status = "error"
            elif case.find("skipped") is not None:
                status = "skipped"
            cases.append(
                {
                    "classname": case.attrib.get("classname", ""),
                    "name": case.attrib.get("name", ""),
                    "status": status,
                }
            )
    counts = {
        status: sum(case["status"] == status for case in cases)
        for status in ("passed", "failed", "error", "skipped")
    }
    return {"counts": counts, "cases": cases}


def _expected_phase_cases(role: str, phase: str) -> list[dict[str, str]]:
    node_ids = EXTERNAL_P2P if phase == "external" else LOCAL_P2P + (TARGET,)
    return [
        {
            "classname": "tests.test_build_linkcheck",
            "name": node_id.rsplit("::", 1)[1],
            "status": (
                "failed"
                if phase == "local" and role == "baseline" and node_id == TARGET
                else "passed"
            ),
        }
        for node_id in node_ids
    ]


def _expected_request(repeat: int, role: str, phase: str) -> dict[str, Any]:
    local = phase == "local"
    node_ids = EXTERNAL_P2P if not local else LOCAL_P2P + (TARGET,)
    environment = {
        "HOME": "/private/tmp/bench-cleanser-sphinx-8475-home",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "PATH": "/private/tmp/bench-cleanser-sphinx-8475-py39/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONPATH": "<source>",
        "SOURCE_DATE_EPOCH": "1783900800",
        "TERM": "dumb",
        "TZ": "UTC",
    }
    if local:
        environment["NO_PROXY"] = "localhost,127.0.0.1"
        environment["no_proxy"] = "localhost,127.0.0.1"
    return {
        "role": role,
        "repeat": repeat,
        "phase": phase,
        "source_tree_sha256": TREE_DIGESTS[role],
        "argv": [
            "<python>",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            "<scratch>",
            "--junitxml",
            "<junit>",
            "-q",
            "-ra",
            *node_ids,
        ],
        "environment": dict(sorted(environment.items())),
        "limits": {
            "cpu_seconds": 60,
            "wall_seconds": 60,
            "open_files": 256,
            "processes": 256,
            "file_bytes": 52_428_800,
            "memory": "not_enforced",
        },
        "network_policy": (
            "localhost_explicitly_excluded_from_managed_proxy"
            if local
            else "managed_external_egress_for_three_canonical_p2p_tests"
        ),
    }


def _validate_timestamp(value: Any, path: str) -> dt.datetime:
    if not isinstance(value, str):
        raise EvidenceError(f"{path} must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise EvidenceError(f"{path} is not an ISO timestamp") from exc
    if parsed.utcoffset() != dt.timedelta(0):
        raise EvidenceError(f"{path} must be UTC")
    return parsed


def _validate_stream(
    record: Mapping[str, Any],
    key: str,
    expected_path: str,
    files: Mapping[str, bytes],
) -> None:
    stream = _as_dict(record[key], f"phase.{key}")
    _keys(stream, {"bytes", "sha256", "relative_path"}, f"phase.{key}")
    _equal(stream["relative_path"], expected_path, f"phase.{key}.relative_path")
    payload = files[f"{BUNDLE_ROOT}/{expected_path}"]
    _equal(stream["bytes"], len(payload), f"phase.{key}.bytes")
    _equal(_digest(stream["sha256"], f"phase.{key}.sha256"), sha256(payload), f"phase.{key}.sha256")


def _validate_phase(
    payload: bytes,
    files: Mapping[str, bytes],
    repeat: int,
    role: str,
    phase: str,
) -> dict[str, Any]:
    path_prefix = f"observations/{repeat:02d}-{role}/{phase}"
    record = _as_dict(strict_json_loads(payload), f"{path_prefix}.record.json")
    _keys(
        record,
        {
            "schema_version",
            "study_id",
            "acquisition_id",
            "request_sha256",
            "request",
            "started_at_utc",
            "ended_at_utc",
            "duration_seconds",
            "return_code",
            "timed_out",
            "stdout",
            "stderr",
            "junit",
            "source_tree_before_sha256",
            "source_tree_after_sha256",
        },
        f"{path_prefix}.record.json",
    )
    _equal(record["schema_version"], "sphinx-execution-phase-0.1.0", f"{path_prefix}.schema_version")
    _equal(record["study_id"], STUDY_ID, f"{path_prefix}.study_id")
    request = _as_dict(record["request"], f"{path_prefix}.request")
    _equal(request, _expected_request(repeat, role, phase), f"{path_prefix}.request")
    request_sha = sha256(canonical_json(request))
    _equal(_digest(record["request_sha256"], f"{path_prefix}.request_sha256"), request_sha, f"{path_prefix}.request_sha256")
    acquisition_id = record["acquisition_id"]
    if not isinstance(acquisition_id, str) or _ACQUISITION_RE.fullmatch(acquisition_id) is None:
        raise EvidenceError(f"{path_prefix}.acquisition_id is invalid")
    _equal(acquisition_id, f"acq-{request_sha[:32]}", f"{path_prefix}.acquisition_id")
    started = _validate_timestamp(record["started_at_utc"], f"{path_prefix}.started_at_utc")
    ended = _validate_timestamp(record["ended_at_utc"], f"{path_prefix}.ended_at_utc")
    if ended < started:
        raise EvidenceError(f"{path_prefix} ends before it starts")
    duration = record["duration_seconds"]
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not (0 < duration < 60):
        raise EvidenceError(f"{path_prefix}.duration_seconds is invalid")
    _equal(record["timed_out"], False, f"{path_prefix}.timed_out")
    expected_return_code = 1 if phase == "local" and role == "baseline" else 0
    _equal(record["return_code"], expected_return_code, f"{path_prefix}.return_code")
    _equal(record["source_tree_before_sha256"], TREE_DIGESTS[role], f"{path_prefix}.source_tree_before_sha256")
    _equal(record["source_tree_after_sha256"], TREE_DIGESTS[role], f"{path_prefix}.source_tree_after_sha256")
    _validate_stream(record, "stdout", f"{path_prefix}.stdout.txt", files)
    _validate_stream(record, "stderr", f"{path_prefix}.stderr.txt", files)

    junit = _as_dict(record["junit"], f"{path_prefix}.junit")
    _keys(junit, {"bytes", "sha256", "relative_path", "summary"}, f"{path_prefix}.junit")
    junit_path = f"{path_prefix}.junit.xml"
    _equal(junit["relative_path"], junit_path, f"{path_prefix}.junit.relative_path")
    junit_payload = files[f"{BUNDLE_ROOT}/{junit_path}"]
    _equal(junit["bytes"], len(junit_payload), f"{path_prefix}.junit.bytes")
    _equal(_digest(junit["sha256"], f"{path_prefix}.junit.sha256"), sha256(junit_payload), f"{path_prefix}.junit.sha256")
    parsed = _parse_junit(junit_payload, junit_path)
    _equal(junit["summary"], parsed, f"{path_prefix}.junit.summary")
    expected_cases = _expected_phase_cases(role, phase)
    _equal(parsed["cases"], expected_cases, f"{path_prefix}.junit.cases")
    expected_counts = {
        "passed": len(expected_cases) - (1 if role == "baseline" and phase == "local" else 0),
        "failed": 1 if role == "baseline" and phase == "local" else 0,
        "error": 0,
        "skipped": 0,
    }
    _equal(parsed["counts"], expected_counts, f"{path_prefix}.junit.counts")
    return parsed


def validate_bundle(path: pathlib.Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    files = _read_bundle(path)
    index_payload = files[f"{BUNDLE_ROOT}/index.json"]
    _equal(len(index_payload), INDEX_BYTES, "index bytes")
    _equal(sha256(index_payload), INDEX_SHA256, "index sha256")
    runner = files[f"{BUNDLE_ROOT}/runner.py"]
    _equal(len(runner), RUNNER_BYTES, "runner bytes")
    _equal(sha256(runner), RUNNER_SHA256, "runner sha256")
    _validate_environment(files[f"{BUNDLE_ROOT}/environment.json"])

    index = _as_dict(strict_json_loads(index_payload), "index")
    _keys(
        index,
        {
            "schema_version",
            "study_id",
            "classification",
            "task",
            "inputs",
            "source_trees",
            "schedule",
            "environment_path",
            "environment_sha256",
            "runner_path",
            "runner_sha256",
            "observations",
            "limitations",
        },
        "index",
    )
    _equal(index["schema_version"], "sphinx-execution-index-0.1.0", "index.schema_version")
    _equal(index["study_id"], STUDY_ID, "index.study_id")
    _equal(index["classification"], _raw_classification(), "index.classification")
    _equal(index["task"], _raw_task(), "index.task")
    _equal(index["inputs"], _raw_inputs(), "index.inputs")
    _equal(index["source_trees"], TREE_DIGESTS, "index.source_trees")
    _equal(
        index["schedule"],
        [{"repeat": repeat, "role": role} for repeat, role in SCHEDULE],
        "index.schedule",
    )
    _equal(index["environment_path"], "environment.json", "index.environment_path")
    _equal(index["environment_sha256"], ENVIRONMENT_SHA256, "index.environment_sha256")
    _equal(index["runner_path"], "runner.py", "index.runner_path")
    _equal(index["runner_sha256"], RUNNER_SHA256, "index.runner_sha256")
    _equal(index["limitations"], list(RAW_LIMITATIONS), "index.limitations")

    observations = _as_list(index["observations"], "index.observations")
    _equal(len(observations), 15, "index.observations length")
    p2p_passes = 0
    baseline_failures = 0
    candidate_passes = 0
    gold_passes = 0
    acquisition_ids: set[str] = set()
    for position, (repeat, role) in enumerate(SCHEDULE):
        expected = _expected_observation(repeat, role)
        observation = _as_dict(observations[position], f"index.observations[{position}]")
        _equal(observation, expected, f"index.observations[{position}]")
        relative = f"observations/{repeat:02d}-{role}/observation.json"
        raw_observation = _as_dict(
            strict_json_loads(files[f"{BUNDLE_ROOT}/{relative}"]),
            relative,
        )
        _equal(raw_observation, expected, relative)
        phase_summaries: dict[str, dict[str, Any]] = {}
        for phase in ("external", "local"):
            record_relative = f"observations/{repeat:02d}-{role}/{phase}.record.json"
            record_payload = files[f"{BUNDLE_ROOT}/{record_relative}"]
            record = _as_dict(strict_json_loads(record_payload), record_relative)
            acquisition_id = record.get("acquisition_id")
            if not isinstance(acquisition_id, str) or acquisition_id in acquisition_ids:
                raise EvidenceError(f"duplicate or invalid acquisition id in {record_relative}")
            acquisition_ids.add(acquisition_id)
            phase_summaries[phase] = _validate_phase(
                record_payload,
                files,
                repeat,
                role,
                phase,
            )
        external_cases = phase_summaries["external"]["cases"]
        local_cases = phase_summaries["local"]["cases"]
        p2p_cases = external_cases + local_cases[:-1]
        if len(p2p_cases) != 17 or not all(case["status"] == "passed" for case in p2p_cases):
            raise EvidenceError(f"P2P outcome mismatch for repeat={repeat}, role={role}")
        target_status = local_cases[-1]["status"]
        _equal(target_status, expected["target_status"], f"target status repeat={repeat}, role={role}")
        p2p_passes += 17
        if role == "baseline":
            baseline_failures += int(target_status == "failed")
        elif role == "gold":
            gold_passes += int(target_status == "passed")
        else:
            candidate_passes += int(target_status == "passed")
    _equal(len(acquisition_ids), 30, "unique acquisition count")
    recomputed = {
        "valid_observations": 15,
        "expected_observations": 15,
        "p2p_passes": p2p_passes,
        "p2p_checks": 255,
        "baseline_target_failures": baseline_failures,
        "candidate_target_passes": candidate_passes,
        "gold_target_passes": gold_passes,
        "candidate_disagreement": False,
        "model_discrimination_on_this_task": False,
    }
    _equal(recomputed, EXPECTED_AGGREGATE, "recomputed aggregate")
    return {
        "study_id": STUDY_ID,
        "manifest_valid": True,
        "bundle_valid": True,
        "observations": 15,
        "phase_executions": 30,
        "p2p_passes": 255,
        "p2p_checks": 255,
        "baseline_target_failures": 3,
        "candidate_target_passes": 9,
        "gold_target_passes": 3,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=MANIFEST_PATH,
        help="checked-in claim manifest",
    )
    parser.add_argument(
        "--bundle",
        type=pathlib.Path,
        help="optional external content-addressed raw-evidence bundle",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        result = (
            validate_bundle(args.bundle, manifest)
            if args.bundle is not None
            else validate_manifest(manifest)
        )
    except (EvidenceError, OSError) as exc:
        print(f"evidence verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
