#!/usr/bin/env python3
"""Verify the source-locked SymPy 15976 feasibility-execution record.

This module does not rerun SymPy.  It validates the checked-in, path-independent
manifest and, when supplied, the external bounded raw-evidence bundle.  The
record is intentionally classified as post-draft/pre-freeze infrastructure
bring-up, not prospective evidence or candidate ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import sys
import tarfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "independent-execution-smoke-0.1.0"
STUDY_ID = "sympy-15976-container-free-post-draft-pre-freeze-feasibility-v1"
MANIFEST_PATH = pathlib.Path(__file__).with_name("evidence-manifest.json")

EXPECTED_BUNDLE_BYTES = 7_652
EXPECTED_BUNDLE_SHA256 = (
    "fe563f4f7b7dda0168dfdd3e9bde7d91f0c6363b36a0c825dc2e6da343f12553"
)
EXPECTED_BUNDLE_ROOT = "bench-cleanser-independent-sympy-15976-evidence"
EXPECTED_SOURCE_ARCHIVE_SHA256 = (
    "49627498facf43ff5778d547e9e208e284acc71a7cab92fc3b92cb1e2ee166a7"
)
EXPECTED_DATASET_SHA256 = (
    "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"
)
EXPECTED_ACQUISITION_MANIFEST_SHA256 = (
    "f79578fb9860ef0eb4bf02a62691e98c4002a5de96b8dda9ab2d3616f082b574"
)
EXPECTED_RUNTIME_ARCHIVE_SHA256 = (
    "87275619c2706affa4d1090d2ca3dad354b6d69f8b85dbfafe38785870751b9a"
)
EXPECTED_RUNTIME_BINARY_SHA256 = (
    "26d9b2c90785be815d334df56afee46ff69fc6c24b006311d78597ad445ab267"
)

EXPECTED_CLASSIFICATION = {
    "stage": "post_draft_pre_freeze_feasibility_execution",
    "claim_scope": "container_free_infrastructure_bring_up_only",
    "prospective": False,
    "blinded": False,
    "task_count": 1,
    "candidate_count": 3,
    "repeat_count_per_variant": 3,
    "execution_count": 15,
}

PASS_TO_PASS = (
    "test_mathml_printer",
    "test_content_printmethod",
    "test_content_mathml_core",
    "test_content_mathml_functions",
    "test_content_mathml_limits",
    "test_content_mathml_integrals",
    "test_content_mathml_matrices",
    "test_content_mathml_sums",
    "test_content_mathml_tuples",
    "test_content_mathml_add",
    "test_content_mathml_Rational",
    "test_content_mathml_constants",
    "test_content_mathml_trig",
    "test_content_mathml_relational",
    "test_content_symbol",
    "test_content_mathml_greek",
    "test_content_mathml_order",
    "test_content_settings",
    "test_presentation_printmethod",
    "test_presentation_mathml_core",
    "test_presentation_mathml_functions",
    "test_presentation_mathml_limits",
    "test_presentation_mathml_integrals",
    "test_presentation_mathml_matrices",
    "test_presentation_mathml_sums",
    "test_presentation_mathml_add",
    "test_presentation_mathml_Rational",
    "test_presentation_mathml_constants",
    "test_presentation_mathml_trig",
    "test_presentation_mathml_relational",
    "test_presentation_mathml_greek",
    "test_presentation_mathml_order",
    "test_presentation_settings",
    "test_toprettyxml_hooking",
    "test_print_basic",
    "test_root_notation_print",
    "test_print_matrix_symbol",
)

EXPECTED_PATCHES: dict[str, dict[str, Any]] = {
    "gold": {
        "role": "canonical_gold_sanity_control",
        "bytes": 2_040,
        "sha256": "cb296790ccb26aebc97be249df44650cf9cb0653637fd340996e384e632196ae",
        "source_submission_id": None,
        "source_url": None,
    },
    "gpt5": {
        "role": "candidate",
        "bytes": 5_865,
        "sha256": "e2fd0256c4495c795129805efd83292f35d9ae656a67bbe55317382d88571971",
        "source_submission_id": "20250807_openhands_gpt5",
        "source_url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            "20250807_openhands_gpt5/logs/sympy__sympy-15976/patch.diff"
        ),
    },
    "kimi_k2": {
        "role": "candidate",
        "bytes": 9_678,
        "sha256": "3e098af68d2c527fdcd4344effbc71789965cb74f14d20b69eb8458080787686",
        "source_submission_id": "20250716_openhands_kimi_k2",
        "source_url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            "20250716_openhands_kimi_k2/logs/sympy__sympy-15976/patch.diff"
        ),
    },
    "claude_4_sonnet": {
        "role": "candidate",
        "bytes": 18_551,
        "sha256": "47ac3303f188d01602f5fb74b14b8f4f10281cfbc87707d17bde2e088c7c3585",
        "source_submission_id": "20250524_openhands_claude_4_sonnet",
        "source_url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            "20250524_openhands_claude_4_sonnet/logs/sympy__sympy-15976/patch.diff"
        ),
    },
}

EXPECTED_VARIANTS: dict[str, dict[str, Any]] = {
    "baseline": {
        "role": "base_plus_oracle_test_patch_control",
        "input_patch_sha256": None,
        "outcome": "supports_incorrect",
        "return_code": 1,
        "passed": 38,
        "failed": 1,
        "target": "failed",
        "request_sha256": "2432c359de56711701a68cbaec5da44f2d6f4c1e07145cfeac0c36dc13d50779",
        "workspace_suffix": "bench-cleanser-sympy-15976-baseline",
    },
    "gpt5": {
        "role": "candidate",
        "input_patch_sha256": EXPECTED_PATCHES["gpt5"]["sha256"],
        "outcome": "supports_correct",
        "return_code": 0,
        "passed": 39,
        "failed": 0,
        "target": "passed",
        "request_sha256": "cf8e8893fda472cad906c91ac19caca1cac6c12a912dc567600819fb830c50b1",
        "workspace_suffix": "bench-cleanser-sympy-15976-gpt5",
    },
    "kimi_k2": {
        "role": "candidate",
        "input_patch_sha256": EXPECTED_PATCHES["kimi_k2"]["sha256"],
        "outcome": "supports_incorrect",
        "return_code": 1,
        "passed": 38,
        "failed": 1,
        "target": "failed",
        "request_sha256": "5be4044e4a5d24ca103b525ca99f0bf9f326cd21e7d1f67b7f6001f58060e474",
        "workspace_suffix": "bench-cleanser-sympy-15976-kimi_k2",
    },
    "claude_4_sonnet": {
        "role": "candidate",
        "input_patch_sha256": EXPECTED_PATCHES["claude_4_sonnet"]["sha256"],
        "outcome": "supports_correct",
        "return_code": 0,
        "passed": 39,
        "failed": 0,
        "target": "passed",
        "request_sha256": "97c4aea5fd2596f14174f8f56f2a69419812e68a7a220598ddee85f3f132c252",
        "workspace_suffix": "bench-cleanser-sympy-15976-claude_4_sonnet",
    },
    "gold": {
        "role": "canonical_gold_sanity_control",
        "input_patch_sha256": EXPECTED_PATCHES["gold"]["sha256"],
        "outcome": "supports_correct",
        "return_code": 0,
        "passed": 39,
        "failed": 0,
        "target": "passed",
        "request_sha256": "f96c04a211698dfd2ba8c0a632d9087abbaea17c34f55a373eed13c6e7b20c22",
        "workspace_suffix": "bench-cleanser-sympy-15976-gold",
    },
}

EXPECTED_ENVIRONMENT_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "NO_COLOR",
    "PATH",
    "PYTHONUNBUFFERED",
    "TEMP",
    "TERM",
    "TMP",
    "TMPDIR",
    "TZ",
)

EXPECTED_ARGV_TAIL = (
    "-W",
    "ignore::UserWarning",
    "-W",
    "ignore::SyntaxWarning",
    "bin/test",
    "-C",
    "--verbose",
    "sympy/printing/tests/test_mathml.py",
)

EXPECTED_LIMITATIONS = (
    "one manually selected task; no population or routing estimate",
    "post-draft/pre-freeze feasibility execution; draft bytes existed but lacked a clean-commit or registration freeze",
    "candidate patches and hosted labels were accessible before execution; selection and execution were not blinded",
    "container-free macOS arm64 Python 3.9 substrate; no container or Linux equivalence claim",
    "one targeted test file, not the complete official SWE-bench harness or repository test suite",
    "gold is only a base-fails/gold-passes sanity control; it does not make candidate execution semantic truth",
    "hosted agreement is one-task retrospective corroboration, not prospective evidence",
    "no routing evidence and no evidence for hypotheses H1-H6",
    "the base-source archive retrieval URL and preparation command transcript were not recorded",
    "environment key names were captured but their values were not retained",
    "the bench-cleanser commit and dirty-tree digest at execution time were not recorded",
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ACQUISITION_ID_RE = re.compile(r"acq-[0-9a-f]{32}\Z")
_SUMMARY_RE = re.compile(
    r"tests finished: (?P<passed>[0-9]+) passed"
    r"(?:, (?P<failed>[0-9]+) failed)?, in [0-9.]+ seconds"
)
_TARGET_RE = re.compile(r"^test_presentation_symbol (?P<status>ok|F)$", re.MULTILINE)


class EvidenceError(ValueError):
    """The checked-in claim or its external evidence is invalid."""


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
    """Decode JSON while rejecting duplicate keys and non-finite numbers."""

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


def load_manifest(path: pathlib.Path = MANIFEST_PATH) -> dict[str, Any]:
    value = strict_json_loads(path.read_bytes())
    return _as_dict(value, "manifest")


def _as_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvidenceError(f"{path} must be a JSON object")
    return value


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceError(f"{path} must be a JSON array")
    return value


def _expect_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise EvidenceError(
            f"{path} keys differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _expect_equal(actual: Any, expected: Any, path: str) -> None:
    if actual != expected:
        raise EvidenceError(f"{path} differs: expected {expected!r}, got {actual!r}")


def _expect_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise EvidenceError(f"{path} must be a lowercase SHA-256")
    return value


def _expect_positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvidenceError(f"{path} must be a positive integer")
    return value


def _expect_nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceError(f"{path} must be a non-negative integer")
    return value


def _expect_nonnegative_float(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise EvidenceError(f"{path} must be finite and non-negative")
    return result


def _parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceError(f"{path} must be a UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"{path} is not an ISO timestamp") from exc


def _validate_task(task: dict[str, Any]) -> None:
    _expect_keys(
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
    _expect_equal(task["instance_id"], "sympy__sympy-15976", "task.instance_id")
    _expect_equal(task["repository"], "sympy/sympy", "task.repository")
    _expect_equal(task["version"], "1.4", "task.version")
    _expect_equal(
        task["base_commit"],
        "701441853569d370506514083b995d11f9a130bd",
        "task.base_commit",
    )
    _expect_equal(
        task["base_tree"], "d1b60b750de1bab2c5a69738e93fcd7110423117", "task.base_tree"
    )
    _expect_equal(
        task["environment_setup_commit"],
        "73b3f90093754c5ed1561bd885242330e3583004",
        "task.environment_setup_commit",
    )

    row = _as_dict(task["canonical_row"], "task.canonical_row")
    _expect_keys(row, {"serialization", "bytes", "sha256"}, "task.canonical_row")
    _expect_equal(
        row["serialization"],
        "utf8-json-sort-keys-compact-all-canonical-columns-v1",
        "task.canonical_row.serialization",
    )
    _expect_equal(row["bytes"], 15_708, "task.canonical_row.bytes")
    _expect_equal(
        row["sha256"],
        "080f2dad36f0177744524af22b615564da264c05e660d6fc0a87f5b41f9dfebf",
        "task.canonical_row.sha256",
    )

    oracle = _as_dict(task["oracle_tests"], "task.oracle_tests")
    _expect_keys(
        oracle,
        {
            "test_patch_bytes",
            "test_patch_sha256",
            "test_patch_files",
            "fail_to_pass",
            "pass_to_pass",
            "incidental_unscored_tests",
        },
        "task.oracle_tests",
    )
    _expect_equal(oracle["test_patch_bytes"], 8_407, "task.oracle_tests.test_patch_bytes")
    _expect_equal(
        oracle["test_patch_sha256"],
        "a63da41ccb4b4bb9ece78bd8350dc3dd9702ba18c6f1c09a540552296df56ac7",
        "task.oracle_tests.test_patch_sha256",
    )
    _expect_equal(
        oracle["test_patch_files"],
        ["sympy/printing/tests/test_mathml.py"],
        "task.oracle_tests.test_patch_files",
    )
    _expect_equal(
        oracle["fail_to_pass"], ["test_presentation_symbol"], "task.oracle_tests.fail_to_pass"
    )
    _expect_equal(oracle["pass_to_pass"], list(PASS_TO_PASS), "task.oracle_tests.pass_to_pass")
    _expect_equal(
        oracle["incidental_unscored_tests"],
        ["test_print_random_symbol"],
        "task.oracle_tests.incidental_unscored_tests",
    )

    patches = _as_list(task["patches"], "task.patches")
    if len(patches) != len(EXPECTED_PATCHES):
        raise EvidenceError("task.patches must contain gold plus three candidates")
    seen: set[str] = set()
    for index, raw_patch in enumerate(patches):
        patch = _as_dict(raw_patch, f"task.patches[{index}]")
        _expect_keys(
            patch,
            {
                "variant",
                "role",
                "bytes",
                "sha256",
                "source_submission_id",
                "source_url",
            },
            f"task.patches[{index}]",
        )
        variant = patch["variant"]
        if not isinstance(variant, str) or variant not in EXPECTED_PATCHES or variant in seen:
            raise EvidenceError(f"invalid or duplicate patch variant: {variant!r}")
        seen.add(variant)
        _expect_equal(patch, {"variant": variant, **EXPECTED_PATCHES[variant]}, f"patch {variant}")


def _validate_sources(sources: dict[str, Any]) -> None:
    _expect_keys(
        sources,
        {"canonical_dataset", "matched_acquisition_manifest", "base_source_archive"},
        "sources",
    )
    dataset = _as_dict(sources["canonical_dataset"], "sources.canonical_dataset")
    _expect_keys(
        dataset,
        {
            "dataset_id",
            "split",
            "revision",
            "authoritative_url",
            "retrieval_url",
            "retrieval_revision",
            "bytes",
            "sha256",
        },
        "sources.canonical_dataset",
    )
    _expect_equal(dataset["dataset_id"], "princeton-nlp/SWE-bench_Verified", "dataset_id")
    _expect_equal(dataset["split"], "test", "dataset split")
    _expect_equal(
        dataset["revision"], "c104f840cc67f8b6eec6f759ebc8b2693d585d4a", "dataset revision"
    )
    _expect_equal(dataset["bytes"], 2_096_679, "dataset bytes")
    _expect_equal(dataset["sha256"], EXPECTED_DATASET_SHA256, "dataset sha256")

    acquisition = _as_dict(
        sources["matched_acquisition_manifest"], "sources.matched_acquisition_manifest"
    )
    _expect_keys(acquisition, {"schema_version", "bytes", "sha256"}, "acquisition manifest")
    _expect_equal(acquisition["schema_version"], "matched-rollout-acquisition-0.2.0", "schema")
    _expect_equal(acquisition["bytes"], 289_653, "acquisition manifest bytes")
    _expect_equal(
        acquisition["sha256"], EXPECTED_ACQUISITION_MANIFEST_SHA256, "acquisition sha256"
    )

    archive = _as_dict(sources["base_source_archive"], "sources.base_source_archive")
    _expect_keys(
        archive,
        {
            "logical_filename",
            "bytes",
            "sha256",
            "commit",
            "tree",
            "acquisition_url",
            "acquisition_url_receipt",
        },
        "base source archive",
    )
    _expect_equal(archive["bytes"], 6_487_628, "base source archive bytes")
    _expect_equal(archive["sha256"], EXPECTED_SOURCE_ARCHIVE_SHA256, "base source sha256")
    _expect_equal(archive["acquisition_url"], None, "base source acquisition_url")
    _expect_equal(
        archive["acquisition_url_receipt"], "not_recorded", "base source URL receipt"
    )


def _validate_harness(harness: dict[str, Any]) -> None:
    _expect_keys(harness, {"repository", "commit", "files"}, "harness")
    _expect_equal(harness["repository"], "SWE-bench/SWE-bench", "harness.repository")
    _expect_equal(
        harness["commit"], "f7bbbb2ccdf479001d6467c9e34af59e44a840f9", "harness.commit"
    )
    expected_files = {
        "swebench/harness/constants/python.py": (
            "5ffc3eb97774955b9cfe8491bb5c9608ec108bf9fdfbb3354de85cf0df9ced4c"
        ),
        "swebench/harness/test_spec/python.py": (
            "c956c3afe41a68fe9849895bdff4dbba838881ba227031d706166b28a5f85523"
        ),
        "swebench/harness/test_spec/test_spec.py": (
            "14b86fa885af3c4705aec4a55b3f8c5ff28b008611976b3cd173db3ec614e231"
        ),
    }
    files = _as_list(harness["files"], "harness.files")
    actual: dict[str, str] = {}
    for index, raw_file in enumerate(files):
        file = _as_dict(raw_file, f"harness.files[{index}]")
        _expect_keys(file, {"path", "sha256"}, f"harness.files[{index}]")
        path = file["path"]
        digest = _expect_sha256(file["sha256"], f"harness.files[{index}].sha256")
        if not isinstance(path, str) or path in actual:
            raise EvidenceError("invalid or duplicate harness path")
        actual[path] = digest
    _expect_equal(actual, expected_files, "harness.files")


def _validate_preparation(preparation: dict[str, Any]) -> None:
    _expect_keys(
        preparation,
        {
            "semantics",
            "ordered_steps",
            "reset_test_patch_files_to_base",
            "variants_that_touched_test_patch_files",
            "official_reset_semantics_reproduced",
            "preparation_command_receipt",
            "prepared_tree_digest_receipt",
        },
        "preparation",
    )
    _expect_equal(
        preparation["semantics"],
        "candidate_or_gold_then_reset_oracle_test_files_to_base_then_apply_test_patch",
        "preparation.semantics",
    )
    _expect_equal(
        preparation["ordered_steps"],
        [
            "materialize_exact_base_source",
            "apply_candidate_patch_or_gold_patch_or_no_patch_for_baseline",
            "reset_each_test_patch_file_to_base_commit",
            "apply_exact_oracle_test_patch",
            "execute_targeted_test_argv",
        ],
        "preparation.ordered_steps",
    )
    _expect_equal(
        preparation["reset_test_patch_files_to_base"],
        ["sympy/printing/tests/test_mathml.py"],
        "preparation.reset_test_patch_files_to_base",
    )
    _expect_equal(
        preparation["variants_that_touched_test_patch_files"],
        ["kimi_k2", "claude_4_sonnet"],
        "preparation.variants_that_touched_test_patch_files",
    )
    _expect_equal(
        preparation["official_reset_semantics_reproduced"],
        True,
        "preparation.official_reset_semantics_reproduced",
    )
    _expect_equal(
        preparation["preparation_command_receipt"],
        "not_recorded",
        "preparation.preparation_command_receipt",
    )
    _expect_equal(
        preparation["prepared_tree_digest_receipt"],
        "not_recorded",
        "preparation.prepared_tree_digest_receipt",
    )


def _validate_runtime(runtime: dict[str, Any]) -> None:
    _expect_keys(runtime, {"substrate", "python", "dependencies", "execution_contract"}, "runtime")
    substrate = _as_dict(runtime["substrate"], "runtime.substrate")
    _expect_keys(
        substrate,
        {"containerized", "os", "os_version", "os_build", "kernel", "architecture"},
        "runtime.substrate",
    )
    _expect_equal(substrate["containerized"], False, "runtime.substrate.containerized")
    _expect_equal(substrate["os"], "macOS", "runtime.substrate.os")
    _expect_equal(substrate["os_version"], "26.5.1", "runtime.substrate.os_version")
    _expect_equal(substrate["os_build"], "25F80", "runtime.substrate.os_build")
    _expect_equal(substrate["architecture"], "arm64", "runtime.substrate.architecture")

    python = _as_dict(runtime["python"], "runtime.python")
    _expect_keys(
        python,
        {
            "distribution",
            "version",
            "archive_url",
            "archive_bytes",
            "archive_sha256",
            "binary_sha256",
        },
        "runtime.python",
    )
    _expect_equal(python["version"], "3.9.25", "runtime.python.version")
    _expect_equal(python["archive_bytes"], 18_471_356, "runtime.python.archive_bytes")
    _expect_equal(
        python["archive_sha256"], EXPECTED_RUNTIME_ARCHIVE_SHA256, "runtime archive sha256"
    )
    _expect_equal(
        python["binary_sha256"], EXPECTED_RUNTIME_BINARY_SHA256, "runtime binary sha256"
    )
    _expect_equal(
        runtime["dependencies"],
        [
            "flake8==7.3.0",
            "flake8-comprehensions==3.17.0",
            "mccabe==0.7.0",
            "mpmath==1.3.0",
            "pip==23.0.1",
            "pycodestyle==2.14.0",
            "pyflakes==3.4.0",
            "setuptools==79.0.1",
            "sympy==1.4.dev0 editable at base_commit",
        ],
        "runtime.dependencies",
    )

    contract = _as_dict(runtime["execution_contract"], "runtime.execution_contract")
    _expect_keys(
        contract,
        {
            "runner",
            "runner_version",
            "argv_template",
            "working_directory",
            "shell",
            "timeout_seconds",
            "sandbox",
            "environment_policy",
            "supplied_environment_keys",
            "environment_value_receipt",
            "supports_correct_exit_codes",
            "supports_incorrect_exit_codes",
        },
        "runtime.execution_contract",
    )
    _expect_equal(
        contract["argv_template"],
        ["{runtime_root}/bin/python", *EXPECTED_ARGV_TAIL],
        "runtime.execution_contract.argv_template",
    )
    _expect_equal(contract["supplied_environment_keys"], list(EXPECTED_ENVIRONMENT_KEYS), "env keys")
    _expect_equal(contract["environment_value_receipt"], "not_captured", "env receipt")


def _validate_evidence_bundle(bundle: dict[str, Any]) -> None:
    _expect_keys(
        bundle,
        {
            "logical_filename",
            "media_type",
            "bytes",
            "sha256",
            "root_directory",
            "file_member_count",
            "maximum_file_member_bytes",
            "location_contract",
        },
        "evidence_bundle",
    )
    _expect_equal(bundle["bytes"], EXPECTED_BUNDLE_BYTES, "evidence_bundle.bytes")
    _expect_equal(bundle["sha256"], EXPECTED_BUNDLE_SHA256, "evidence_bundle.sha256")
    _expect_equal(bundle["root_directory"], EXPECTED_BUNDLE_ROOT, "evidence bundle root")
    _expect_equal(bundle["file_member_count"], 30, "evidence bundle member count")
    maximum = _expect_positive_int(
        bundle["maximum_file_member_bytes"], "evidence_bundle.maximum_file_member_bytes"
    )
    if maximum > 1_048_576:
        raise EvidenceError("evidence bundle member bound is too large")
    _expect_equal(
        bundle["location_contract"],
        "external_content_addressed_artifact; no local absolute path is canonical",
        "evidence bundle location contract",
    )


def _expected_observation_path(variant: str, repeat: int) -> str:
    if variant == "gold":
        return f"gold-r{repeat}-observation.json"
    suffix = "" if repeat == 1 else f"-r{repeat}"
    return f"{variant}{suffix}-observation.json"


def _expected_artifact_prefix(variant: str, repeat: int) -> str:
    if variant == "gold":
        return f"gold-r{repeat}-artifacts/"
    suffix = "" if repeat == 1 else f"-r{repeat}"
    return f"{variant}{suffix}-artifacts/"


def _validate_file_identity(value: Any, path: str) -> tuple[str, str]:
    identity = _as_dict(value, path)
    _expect_keys(identity, {"path", "sha256"}, path)
    member_path = identity["path"]
    if not isinstance(member_path, str):
        raise EvidenceError(f"{path}.path must be a string")
    pure = pathlib.PurePosixPath(member_path)
    if pure.is_absolute() or ".." in pure.parts or member_path != pure.as_posix():
        raise EvidenceError(f"{path}.path is not a confined relative path")
    digest = _expect_sha256(identity["sha256"], f"{path}.sha256")
    return member_path, digest


def _validate_execution_groups(groups_value: Any) -> list[dict[str, Any]]:
    groups = _as_list(groups_value, "execution_groups")
    if len(groups) != len(EXPECTED_VARIANTS):
        raise EvidenceError("execution_groups must contain five distinct roles")
    seen_variants: set[str] = set()
    seen_run_ids: set[str] = set()
    seen_members: set[str] = set()
    normalized_groups: list[dict[str, Any]] = []

    for group_index, raw_group in enumerate(groups):
        group = _as_dict(raw_group, f"execution_groups[{group_index}]")
        _expect_keys(group, {"variant", "role", "input_patch_sha256", "repeats"}, "execution group")
        variant = group["variant"]
        if not isinstance(variant, str) or variant not in EXPECTED_VARIANTS or variant in seen_variants:
            raise EvidenceError(f"invalid or duplicate execution variant: {variant!r}")
        seen_variants.add(variant)
        expected = EXPECTED_VARIANTS[variant]
        _expect_equal(group["role"], expected["role"], f"{variant}.role")
        _expect_equal(
            group["input_patch_sha256"], expected["input_patch_sha256"], f"{variant}.input_patch_sha256"
        )
        repeats = _as_list(group["repeats"], f"{variant}.repeats")
        if len(repeats) != 3:
            raise EvidenceError(f"{variant} must contain exactly three repeats")

        repeat_numbers: set[int] = set()
        for repeat_index, raw_repeat in enumerate(repeats):
            run = _as_dict(raw_repeat, f"{variant}.repeats[{repeat_index}]")
            _expect_keys(
                run,
                {
                    "run_id",
                    "repeat",
                    "provenance",
                    "observation",
                    "artifact",
                    "acquisition_id",
                    "request_sha256",
                    "started_at",
                    "finished_at",
                    "run_status",
                    "outcome",
                    "return_code",
                    "wall_seconds",
                    "storage_bytes",
                    "tests",
                    "stdout",
                    "stderr",
                },
                f"{variant}.repeat",
            )
            repeat = _expect_positive_int(run["repeat"], f"{variant}.repeat")
            if repeat not in {1, 2, 3} or repeat in repeat_numbers:
                raise EvidenceError(f"{variant} repeat numbers must be exactly 1, 2, 3")
            repeat_numbers.add(repeat)
            run_id = f"{variant}-r{repeat}"
            _expect_equal(run["run_id"], run_id, f"{variant}.run_id")
            if run_id in seen_run_ids:
                raise EvidenceError(f"duplicate run_id: {run_id}")
            seen_run_ids.add(run_id)
            _expect_equal(run["provenance"], "independent_execution", f"{run_id}.provenance")
            _expect_equal(run["run_status"], "completed", f"{run_id}.run_status")
            _expect_equal(run["outcome"], expected["outcome"], f"{run_id}.outcome")
            _expect_equal(run["return_code"], expected["return_code"], f"{run_id}.return_code")
            _expect_equal(run["request_sha256"], expected["request_sha256"], f"{run_id}.request")
            if not isinstance(run["acquisition_id"], str) or _ACQUISITION_ID_RE.fullmatch(
                run["acquisition_id"]
            ) is None:
                raise EvidenceError(f"{run_id}.acquisition_id is invalid")
            started = _parse_timestamp(run["started_at"], f"{run_id}.started_at")
            finished = _parse_timestamp(run["finished_at"], f"{run_id}.finished_at")
            if finished < started:
                raise EvidenceError(f"{run_id} finished before it started")
            _expect_nonnegative_float(run["wall_seconds"], f"{run_id}.wall_seconds")
            _expect_positive_int(run["storage_bytes"], f"{run_id}.storage_bytes")

            observation_path, _ = _validate_file_identity(run["observation"], f"{run_id}.observation")
            artifact_path, _ = _validate_file_identity(run["artifact"], f"{run_id}.artifact")
            _expect_equal(
                observation_path,
                _expected_observation_path(variant, repeat),
                f"{run_id}.observation.path",
            )
            if not artifact_path.startswith(_expected_artifact_prefix(variant, repeat)):
                raise EvidenceError(f"{run_id}.artifact.path has the wrong repeat directory")
            if pathlib.PurePosixPath(artifact_path).name != f"{run['acquisition_id']}.json":
                raise EvidenceError(f"{run_id}.artifact.path is not bound to acquisition_id")
            for member in (observation_path, artifact_path):
                if member in seen_members:
                    raise EvidenceError(f"evidence member reused by multiple runs: {member}")
                seen_members.add(member)

            tests = _as_dict(run["tests"], f"{run_id}.tests")
            _expect_keys(tests, {"passed", "failed", "total", "target"}, f"{run_id}.tests")
            _expect_equal(tests["passed"], expected["passed"], f"{run_id}.tests.passed")
            _expect_equal(tests["failed"], expected["failed"], f"{run_id}.tests.failed")
            _expect_equal(tests["total"], 39, f"{run_id}.tests.total")
            _expect_equal(tests["target"], expected["target"], f"{run_id}.tests.target")

            for stream_name in ("stdout", "stderr"):
                stream = _as_dict(run[stream_name], f"{run_id}.{stream_name}")
                _expect_keys(stream, {"captured_bytes", "sha256", "truncated"}, f"{run_id}.{stream_name}")
                _expect_nonnegative_int(stream["captured_bytes"], f"{run_id}.{stream_name}.captured_bytes")
                _expect_sha256(stream["sha256"], f"{run_id}.{stream_name}.sha256")
                _expect_equal(stream["truncated"], False, f"{run_id}.{stream_name}.truncated")
            normalized_groups.append({"variant": variant, "group": group, "run": run})

    if seen_members and len(seen_members) != 30:
        raise EvidenceError("the 15 runs must bind exactly 30 distinct raw JSON files")
    return normalized_groups


def _validate_hosted_priors(value: Any) -> None:
    priors = _as_list(value, "hosted_prior_measurements")
    expected = {
        "gpt5": (
            "20250807_openhands_gpt5",
            True,
            2_601,
            "a9975dfc1b9567a907870747e3e644dec52ada1ed34ad1536b1a5342ecd2efc2",
        ),
        "kimi_k2": (
            "20250716_openhands_kimi_k2",
            False,
            2_602,
            "7e45f9927ef58b47eac001ad9f57b66bcf44d73a7b0fb557e782da7582e3bdd7",
        ),
        "claude_4_sonnet": (
            "20250524_openhands_claude_4_sonnet",
            True,
            2_601,
            "a9975dfc1b9567a907870747e3e644dec52ada1ed34ad1536b1a5342ecd2efc2",
        ),
    }
    if len(priors) != 3:
        raise EvidenceError("hosted_prior_measurements must contain exactly three candidates")
    seen: set[str] = set()
    for index, raw_prior in enumerate(priors):
        prior = _as_dict(raw_prior, f"hosted_prior_measurements[{index}]")
        _expect_keys(
            prior,
            {
                "variant",
                "provenance",
                "submission_id",
                "resolved",
                "report_bytes",
                "report_sha256",
                "source_url",
                "accessed_before_execution",
            },
            "hosted prior",
        )
        variant = prior["variant"]
        if not isinstance(variant, str) or variant not in expected or variant in seen:
            raise EvidenceError(f"invalid or duplicate hosted prior: {variant!r}")
        seen.add(variant)
        submission, resolved, byte_count, digest = expected[variant]
        _expect_equal(prior["provenance"], "hosted_prior_measurement", f"{variant}.provenance")
        _expect_equal(prior["submission_id"], submission, f"{variant}.submission_id")
        _expect_equal(prior["resolved"], resolved, f"{variant}.resolved")
        _expect_equal(prior["report_bytes"], byte_count, f"{variant}.report_bytes")
        _expect_equal(prior["report_sha256"], digest, f"{variant}.report_sha256")
        _expect_equal(prior["accessed_before_execution"], True, f"{variant}.access")
        if not isinstance(prior["source_url"], str) or submission not in prior["source_url"]:
            raise EvidenceError(f"{variant}.source_url is not submission-bound")


def _validate_aggregate(aggregate: dict[str, Any], normalized: list[dict[str, Any]]) -> None:
    _expect_keys(
        aggregate,
        {"execution_count", "total_wall_seconds", "total_storage_bytes", "variant_outcomes"},
        "aggregate",
    )
    runs = [entry["run"] for entry in normalized]
    _expect_equal(aggregate["execution_count"], len(runs), "aggregate.execution_count")
    expected_wall = math.fsum(float(run["wall_seconds"]) for run in runs)
    actual_wall = _expect_nonnegative_float(aggregate["total_wall_seconds"], "aggregate.total_wall_seconds")
    if not math.isclose(actual_wall, expected_wall, rel_tol=0.0, abs_tol=1e-15):
        raise EvidenceError("aggregate.total_wall_seconds is not derived from executed runs")
    _expect_equal(
        aggregate["total_storage_bytes"],
        sum(int(run["storage_bytes"]) for run in runs),
        "aggregate.total_storage_bytes",
    )
    outcomes = _as_list(aggregate["variant_outcomes"], "aggregate.variant_outcomes")
    if len(outcomes) != 5:
        raise EvidenceError("aggregate.variant_outcomes must contain five variants")
    seen: set[str] = set()
    for index, raw_outcome in enumerate(outcomes):
        outcome = _as_dict(raw_outcome, f"variant_outcomes[{index}]")
        _expect_keys(
            outcome,
            {"variant", "role", "repeat_count", "all_repeats_agree", "outcome", "tests"},
            "variant outcome",
        )
        variant = outcome["variant"]
        if not isinstance(variant, str) or variant not in EXPECTED_VARIANTS or variant in seen:
            raise EvidenceError("invalid or duplicate aggregate variant")
        seen.add(variant)
        expected = EXPECTED_VARIANTS[variant]
        _expect_equal(outcome["role"], expected["role"], f"aggregate.{variant}.role")
        _expect_equal(outcome["repeat_count"], 3, f"aggregate.{variant}.repeat_count")
        _expect_equal(outcome["all_repeats_agree"], True, f"aggregate.{variant}.agreement")
        _expect_equal(outcome["outcome"], expected["outcome"], f"aggregate.{variant}.outcome")
        _expect_equal(
            outcome["tests"],
            {
                "passed": expected["passed"],
                "failed": expected["failed"],
                "total": 39,
                "target": expected["target"],
            },
            f"aggregate.{variant}.tests",
        )


def verify_manifest(manifest: dict[str, Any]) -> None:
    """Validate schema, fixed identities, outcomes, aggregation, and caveats."""

    _expect_keys(
        manifest,
        {
            "schema_version",
            "study_id",
            "classification",
            "protocol_state",
            "task",
            "sources",
            "harness",
            "preparation",
            "runtime",
            "evidence_bundle",
            "execution_groups",
            "hosted_prior_measurements",
            "aggregate",
            "limitations",
        },
        "manifest",
    )
    _expect_equal(manifest["schema_version"], SCHEMA_VERSION, "schema_version")
    _expect_equal(manifest["study_id"], STUDY_ID, "study_id")
    _expect_equal(manifest["classification"], EXPECTED_CLASSIFICATION, "classification")

    protocol = _as_dict(manifest["protocol_state"], "protocol_state")
    _expect_keys(
        protocol,
        {
            "draft_protocol_status",
            "draft_artifacts",
            "selection",
            "candidate_and_label_access",
            "bench_cleanser_tree_at_execution",
        },
        "protocol_state",
    )
    _expect_equal(
        protocol["draft_protocol_status"],
        "draft_bytes_existed_but_no_clean_commit_or_registration_freeze",
        "protocol_state.draft_protocol_status",
    )
    draft_artifacts = _as_list(protocol["draft_artifacts"], "protocol_state.draft_artifacts")
    expected_drafts = {
        "experiments/prospective_pilot/preregistration.json": (
            "0f85f26414fd31d898b9187ed943f71d77ca01b5d0adf84856fe8ccec0db55af"
        ),
        "experiments/prospective_pilot/PREREGISTRATION.md": (
            "9df03e38a6fd362d6f779991ff6491b862341b27cda2b1eff2ce08417238e9e4"
        ),
    }
    actual_drafts: dict[str, str] = {}
    for index, raw_draft in enumerate(draft_artifacts):
        draft = _as_dict(raw_draft, f"protocol_state.draft_artifacts[{index}]")
        _expect_keys(
            draft,
            {
                "logical_path",
                "sha256",
                "bytes",
                "byte_count_receipt",
                "mtime_receipt",
            },
            f"protocol_state.draft_artifacts[{index}]",
        )
        logical_path = draft["logical_path"]
        if not isinstance(logical_path, str) or logical_path in actual_drafts:
            raise EvidenceError("invalid or duplicate old-draft logical path")
        actual_drafts[logical_path] = _expect_sha256(
            draft["sha256"], f"protocol_state.draft_artifacts[{index}].sha256"
        )
        _expect_equal(draft["bytes"], None, f"{logical_path}.bytes")
        _expect_equal(draft["byte_count_receipt"], "not_recorded", f"{logical_path}.byte receipt")
        _expect_equal(
            draft["mtime_receipt"],
            "local_unauthenticated_not_identity",
            f"{logical_path}.mtime receipt",
        )
    _expect_equal(actual_drafts, expected_drafts, "protocol_state.draft_artifacts")
    _expect_equal(
        protocol["selection"],
        "manual_feasibility_selection_after_hosted_outcomes_were_available",
        "protocol_state.selection",
    )
    _expect_equal(
        protocol["candidate_and_label_access"],
        "candidate_patches_and_hosted_labels_accessible_before_execution",
        "protocol_state.candidate_and_label_access",
    )
    tree = _as_dict(protocol["bench_cleanser_tree_at_execution"], "bench_cleanser tree")
    _expect_equal(
        tree,
        {"commit": None, "dirty_tree_digest": None, "receipt_status": "not_recorded"},
        "protocol_state.bench_cleanser_tree_at_execution",
    )

    _validate_task(_as_dict(manifest["task"], "task"))
    _validate_sources(_as_dict(manifest["sources"], "sources"))
    _validate_harness(_as_dict(manifest["harness"], "harness"))
    _validate_preparation(_as_dict(manifest["preparation"], "preparation"))
    _validate_runtime(_as_dict(manifest["runtime"], "runtime"))
    _validate_evidence_bundle(_as_dict(manifest["evidence_bundle"], "evidence_bundle"))
    normalized = _validate_execution_groups(manifest["execution_groups"])
    _validate_hosted_priors(manifest["hosted_prior_measurements"])
    _validate_aggregate(_as_dict(manifest["aggregate"], "aggregate"), normalized)
    _expect_equal(manifest["limitations"], list(EXPECTED_LIMITATIONS), "limitations")

    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    if "/private/tmp/" in serialized or "file:///private/tmp/" in serialized:
        raise EvidenceError("manifest must not make a mutable /private/tmp path canonical")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _expected_member_identities(manifest: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    groups = _as_list(manifest["execution_groups"], "execution_groups")
    for raw_group in groups:
        group = _as_dict(raw_group, "execution group")
        for raw_run in _as_list(group["repeats"], "repeats"):
            run = _as_dict(raw_run, "run")
            for name in ("observation", "artifact"):
                member, digest = _validate_file_identity(run[name], f"run.{name}")
                result[member] = digest
    return result


def _read_directory_members(root: pathlib.Path, maximum_bytes: int) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise EvidenceError(f"symlink is not allowed in evidence directory: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise EvidenceError(f"non-regular evidence member: {path}")
        payload = path.read_bytes()
        if not payload or len(payload) > maximum_bytes:
            raise EvidenceError(f"evidence member outside byte bound: {path}")
        result[path.relative_to(root).as_posix()] = payload
    return result


def _read_archive_members(path: pathlib.Path, maximum_bytes: int) -> dict[str, bytes]:
    archive = path.read_bytes()
    if len(archive) != EXPECTED_BUNDLE_BYTES or _sha256(archive) != EXPECTED_BUNDLE_SHA256:
        raise EvidenceError("external evidence archive bytes or SHA-256 differ")
    result: dict[str, bytes] = {}
    try:
        with tarfile.open(path, mode="r:gz") as handle:
            for member in handle.getmembers():
                pure = pathlib.PurePosixPath(member.name)
                if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                    raise EvidenceError(f"unconfined archive member: {member.name}")
                if pure.parts[0] != EXPECTED_BUNDLE_ROOT:
                    raise EvidenceError(f"unexpected archive root: {member.name}")
                if member.isdir():
                    continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise EvidenceError(f"non-regular archive member: {member.name}")
                if member.size <= 0 or member.size > maximum_bytes:
                    raise EvidenceError(f"archive member outside byte bound: {member.name}")
                relative = pathlib.PurePosixPath(*pure.parts[1:]).as_posix()
                if relative in result:
                    raise EvidenceError(f"duplicate archive member: {relative}")
                stream = handle.extractfile(member)
                if stream is None:
                    raise EvidenceError(f"cannot read archive member: {member.name}")
                payload = stream.read(maximum_bytes + 1)
                if len(payload) != member.size:
                    raise EvidenceError(f"archive member size mismatch: {member.name}")
                result[relative] = payload
    except tarfile.TarError as exc:
        raise EvidenceError("invalid evidence tar archive") from exc
    return result


def _parse_test_output(text: str) -> dict[str, Any]:
    summaries = list(_SUMMARY_RE.finditer(text))
    targets = list(_TARGET_RE.finditer(text))
    if len(summaries) != 1 or len(targets) != 1:
        raise EvidenceError("test stdout lacks one unambiguous summary and target status")
    passed = int(summaries[0].group("passed"))
    failed_group = summaries[0].group("failed")
    failed = 0 if failed_group is None else int(failed_group)
    target = "passed" if targets[0].group("status") == "ok" else "failed"
    if passed + failed != 39 or "sympy/printing/tests/test_mathml.py[39]" not in text:
        raise EvidenceError("test stdout does not bind the expected 39-test file")
    return {"passed": passed, "failed": failed, "total": 39, "target": target}


def _validate_stream(
    artifact_stream: Any,
    manifest_stream: Any,
    *,
    path: str,
) -> None:
    raw = _as_dict(artifact_stream, f"artifact.{path}")
    declared = _as_dict(manifest_stream, f"manifest.{path}")
    text = raw.get("text")
    if not isinstance(text, str):
        raise EvidenceError(f"artifact.{path}.text must be a string")
    encoded = text.encode("utf-8")
    digest = _sha256(encoded)
    for field, expected in (
        ("captured_bytes", len(encoded)),
        ("total_bytes", len(encoded)),
        ("sha256", digest),
        ("truncated", False),
        ("read_error", None),
    ):
        _expect_equal(raw.get(field), expected, f"artifact.{path}.{field}")
    _expect_equal(
        declared,
        {"captured_bytes": len(encoded), "sha256": digest, "truncated": False},
        f"manifest.{path}",
    )


def _validate_run_evidence(
    run: dict[str, Any],
    variant: str,
    observation_bytes: bytes,
    artifact_bytes: bytes,
    runtime: dict[str, Any],
) -> None:
    observation_identity = _as_dict(run["observation"], "run.observation")
    artifact_identity = _as_dict(run["artifact"], "run.artifact")
    _expect_equal(_sha256(observation_bytes), observation_identity["sha256"], "observation file digest")
    _expect_equal(_sha256(artifact_bytes), artifact_identity["sha256"], "artifact file digest")

    observation = _as_dict(strict_json_loads(observation_bytes), "raw observation")
    artifact = _as_dict(strict_json_loads(artifact_bytes), "raw artifact")
    expected_kind = "oracle_hardening" if variant == "gold" else "targeted_execution"
    expected_source = (
        "sympy-15976-container-free-gold-sanity"
        if variant == "gold"
        else "sympy-15976-container-free-pilot"
    )
    _expect_equal(observation.get("acquisition_id"), run["acquisition_id"], "observation acquisition_id")
    _expect_equal(artifact.get("acquisition_id"), run["acquisition_id"], "artifact acquisition_id")
    _expect_equal(artifact.get("request_sha256"), run["request_sha256"], "artifact request_sha256")
    _expect_equal(observation.get("kind"), expected_kind, "observation kind")
    _expect_equal(artifact.get("kind"), expected_kind, "artifact kind")
    _expect_equal(observation.get("source"), expected_source, "observation source")
    _expect_equal(artifact.get("source"), expected_source, "artifact source")
    _expect_equal(observation.get("authoritative"), False, "observation authoritative")
    _expect_equal(observation.get("privileged_inputs"), [], "observation privileged_inputs")
    _expect_equal(observation.get("status"), run["outcome"], "observation status")

    metadata = _as_dict(observation.get("metadata"), "observation.metadata")
    _expect_equal(metadata.get("artifact_sha256"), artifact_identity["sha256"], "artifact binding")
    locator = metadata.get("artifact_locator")
    if not isinstance(locator, str) or pathlib.PurePosixPath(urlparse(locator).path).name != pathlib.PurePosixPath(
        artifact_identity["path"]
    ).name:
        raise EvidenceError("observation artifact locator basename differs")
    _expect_equal(metadata.get("outcome"), run["outcome"], "observation outcome")
    _expect_equal(metadata.get("return_code"), run["return_code"], "observation return_code")
    _expect_equal(metadata.get("capture_incomplete"), False, "observation capture_incomplete")

    execution = _as_dict(artifact.get("execution"), "artifact.execution")
    for field in ("started_at", "finished_at", "return_code", "wall_seconds", "outcome"):
        _expect_equal(execution.get(field), run[field], f"artifact.execution.{field}")
    for field, expected in (
        ("timed_out", False),
        ("setup_error", None),
        ("shell", False),
        ("timeout_seconds", 120.0),
        ("sandbox", "not_provided"),
        ("environment_policy", "minimal-allowlist-v1"),
        ("supplied_environment_keys", list(EXPECTED_ENVIRONMENT_KEYS)),
        ("supports_correct_exit_codes", [0]),
        ("supports_incorrect_exit_codes", [1]),
    ):
        _expect_equal(execution.get(field), expected, f"artifact.execution.{field}")

    cost = _as_dict(observation.get("cost"), "observation.cost")
    _expect_equal(cost.get("wall_seconds"), run["wall_seconds"], "observation cost wall")
    _expect_equal(cost.get("storage_bytes"), run["storage_bytes"], "observation storage")
    _expect_equal(len(artifact_bytes), run["storage_bytes"], "artifact byte cost")

    argv = artifact.get("argv")
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise EvidenceError("artifact argv must be a string array")
    if len(argv) != 1 + len(EXPECTED_ARGV_TAIL):
        raise EvidenceError("artifact argv length differs")
    if not argv[0].endswith("/bench-cleanser-sympy-15976-py39/bin/python"):
        raise EvidenceError("artifact argv runtime path has the wrong logical suffix")
    _expect_equal(argv[1:], list(EXPECTED_ARGV_TAIL), "artifact argv tail")
    _expect_equal(artifact.get("working_directory"), ".", "artifact working_directory")
    workspace = artifact.get("workspace_root")
    expected_workspace = EXPECTED_VARIANTS[variant]["workspace_suffix"]
    if not isinstance(workspace, str) or not workspace.endswith(f"/{expected_workspace}"):
        raise EvidenceError("artifact workspace has the wrong logical suffix")

    _validate_stream(artifact.get("stdout"), run["stdout"], path="stdout")
    _validate_stream(artifact.get("stderr"), run["stderr"], path="stderr")
    stdout = _as_dict(artifact.get("stdout"), "artifact.stdout")
    _expect_equal(_parse_test_output(stdout["text"]), run["tests"], "parsed test summary")

    contract = _as_dict(runtime["execution_contract"], "runtime.execution_contract")
    _expect_equal(contract["runner"], "bench-cleanser-acquire", "runner")
    _expect_equal(contract["runner_version"], "0.1.0", "runner version")


def verify_external_bundle(manifest: dict[str, Any], bundle_path: pathlib.Path) -> None:
    """Validate exact external members and recompute all 15 execution outcomes."""

    verify_manifest(manifest)
    bundle = _as_dict(manifest["evidence_bundle"], "evidence_bundle")
    maximum = int(bundle["maximum_file_member_bytes"])
    members = (
        _read_directory_members(bundle_path, maximum)
        if bundle_path.is_dir()
        else _read_archive_members(bundle_path, maximum)
    )
    expected = _expected_member_identities(manifest)
    if set(members) != set(expected):
        raise EvidenceError(
            f"evidence member set differs: missing={sorted(set(expected) - set(members))}, "
            f"unknown={sorted(set(members) - set(expected))}"
        )
    for member, digest in expected.items():
        _expect_equal(_sha256(members[member]), digest, f"evidence member {member}")

    runtime = _as_dict(manifest["runtime"], "runtime")
    for raw_group in _as_list(manifest["execution_groups"], "execution_groups"):
        group = _as_dict(raw_group, "execution group")
        variant = str(group["variant"])
        for raw_run in _as_list(group["repeats"], "repeats"):
            run = _as_dict(raw_run, "run")
            observation = _as_dict(run["observation"], "run.observation")
            artifact = _as_dict(run["artifact"], "run.artifact")
            _validate_run_evidence(
                run,
                variant,
                members[str(observation["path"])],
                members[str(artifact["path"])],
                runtime,
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=pathlib.Path, default=MANIFEST_PATH)
    parser.add_argument(
        "--bundle",
        type=pathlib.Path,
        help="optional external .tar.gz artifact or extracted evidence directory",
    )
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        verify_manifest(manifest)
        if args.bundle is not None:
            verify_external_bundle(manifest, args.bundle)
    except (EvidenceError, OSError) as exc:
        print(f"evidence verification failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "bundle_verified": args.bundle is not None,
                "classification": EXPECTED_CLASSIFICATION["stage"],
                "execution_count": EXPECTED_CLASSIFICATION["execution_count"],
                "manifest_verified": True,
                "study_id": STUDY_ID,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
