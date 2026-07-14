#!/usr/bin/env python3
"""Verify the retrospective paired Linux-container SymPy feasibility arm.

The verifier never runs Docker or SymPy.  It validates the path-independent
claim, and optionally authenticates the external content-addressed archive and
recomputes all 15 test summaries from the captured logs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import pathlib
import re
import sys
import tarfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, NoReturn

SCHEMA_VERSION = "paired-execution-smoke-0.1.0"
STUDY_ID = "sympy-15976-locally-constructed-container-paired-retrospective-v1"
MANIFEST_PATH = pathlib.Path(__file__).with_name("evidence-manifest.json")

BUNDLE_BYTES = 18_299
BUNDLE_SHA256 = "90729da3d543fb3ac75405bb782d056a90ae6b1bbb9219a7016404f489aaea3c"
BUNDLE_ROOT = "bench-cleanser-paired-sympy-15976-evidence"
IMAGE_ID = "sha256:131da93f75269d9db60c3e1e7e5f412d6b05445d6b92e55b134d202fd83d074e"
BASE_IMAGE_ID = "sha256:c6ae79e38498325db67193d391e6ec1d224d96c693a8a4d943498556716d3783"
DOCKERFILE_SHA256 = "ab835600739006acdf122a11a246561499f2eca13e02a5bbc86d46f7c23296a9"
PYTHON_ARCHIVE_SHA256 = "6112d46355857680b81849764a6cf9f38cc4cd0d1cf29d432bc12fe5aeedf9d0"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SUMMARY_RE = re.compile(
    r"tests finished: (?P<passed>[0-9]+) passed"
    r"(?:, (?P<failed>[0-9]+) failed)?, in [0-9.]+ seconds"
)
_TARGET_RE = re.compile(r"^test_presentation_symbol (?P<status>ok|F)$", re.MULTILINE)
_TREE_LINE_RE = re.compile(r"(?P<sha>[0-9a-f]{64})\t(?P<bytes>[0-9]+)\t(?P<path>[^\r\n]+)\Z")

ROLE_ORDER = ("baseline", "gpt5", "kimi_k2", "claude_4_sonnet", "gold")

EXPECTED_CLASSIFICATION = {
    "stage": "retrospective_post_draft_locally_constructed_paired_container_feasibility",
    "claim_scope": "one_task_paired_substrate_feasibility_only",
    "prospective": False,
    "blinded": False,
    "official_swe_bench_image": False,
    "task_count": 1,
    "candidate_count": 3,
    "repeat_count_per_role": 3,
    "execution_count": 15,
    "supports_routing_claims": False,
    "supports_hypotheses_h1_h6": False,
}

EXPECTED_TASK = {
    "instance_id": "sympy__sympy-15976",
    "repository": "sympy/sympy",
    "version": "1.4",
    "base_commit": "701441853569d370506514083b995d11f9a130bd",
    "base_tree": "d1b60b750de1bab2c5a69738e93fcd7110423117",
    "environment_setup_commit": "73b3f90093754c5ed1561bd885242330e3583004",
    "targeted_test_file": "sympy/printing/tests/test_mathml.py",
    "fail_to_pass": ["test_presentation_symbol"],
    "executed_test_count": 39,
    "preparation": (
        "reuse_exact_prepared_workspaces_from_independent_execution_smoke_"
        "as_read_only_mounts"
    ),
}

EXPECTED_RELATION = {
    "study_id": "sympy-15976-container-free-post-draft-pre-freeze-feasibility-v1",
    "manifest": {
        "logical_path": "experiments/independent_execution_smoke/evidence-manifest.json",
        "bytes": 35_718,
        "sha256": "b0bcec424a570d80a88d06584beb7fad1259fe9fa4fe67db1f4d306ac251e21c",
    },
    "comparison_axis": (
        "container_free_macos_arm64_vs_locally_constructed_linux_arm64_container"
    ),
    "same_prepared_workspaces": True,
    "observed_role_pattern_agreement": True,
    "claim": "one_task_retrospective_substrate_pair_only",
}

EXPECTED_DOCKER = {
    "client_version": "28.1.1",
    "server_version": "28.1.1",
    "desktop_version": "4.41.2",
    "server_os": "linux",
    "server_architecture": "arm64",
}

EXPECTED_IMAGE = {
    "construction": "locally_constructed_for_feasibility",
    "official_swe_bench_image": False,
    "id": IMAGE_ID,
    "repo_digest": f"bench-cleanser/sympy-paired-runtime@{IMAGE_ID}",
    "os": "linux",
    "architecture": "arm64",
    "size_bytes": 469_094_980,
    "base_reference": "node:18",
    "base_image_id": BASE_IMAGE_ID,
    "base_platform": "linux/arm64",
    "dockerfile_base_digest_pinned": False,
    "base_identity_receipt": (
        "recorded_during_local_build_setup_but_not_preserved_as_a_"
        "contemporaneous_inspect_record"
    ),
}

EXPECTED_DOCKERFILE = {
    "member": "build/Dockerfile",
    "bytes": 504,
    "sha256": DOCKERFILE_SHA256,
}

EXPECTED_PYTHON = {
    "distribution": "python-build-standalone install_only",
    "version": "3.9.25",
    "archive_filename": (
        "cpython-3.9.25-20251031-aarch64-linux-gnu-install_only.tar.gz"
    ),
    "archive_bytes": 41_536_085,
    "archive_sha256": PYTHON_ARCHIVE_SHA256,
    "archive_url": (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        "20251031/cpython-3.9.25%2B20251031-aarch64-unknown-linux-gnu-"
        "install_only.tar.gz"
    ),
    "container_binary": "/opt/python/bin/python",
}

EXPECTED_MPMATH = {
    "declared_version": "1.3.0",
    "container_target": "/opt/site-packages/mpmath",
    "mount_read_only": True,
    "metadata_member": "dependencies/mpmath-1.3.0-METADATA",
    "metadata_bytes": 8_630,
    "metadata_sha256": "44b66ea444b9c0d19ae94815d356bf047ae6b680c19268b5c265687cd6a81406",
    "mounted_tree_manifest_member": "dependencies/mpmath-mounted-tree.tsv",
    "mounted_tree_manifest_bytes": 19_122,
    "mounted_tree_manifest_sha256": (
        "df5f953e1a9a06c64dc2ee7361d1eae06be1ccb3bb80362a4399692984dedae9"
    ),
    "mounted_file_count": 174,
    "mounted_total_bytes": 3_603_837,
    "receipt_timing": "package_metadata_and_mounted_tree_recorded_after_execution",
}

EXPECTED_DOCKER_ARGV = [
    "docker",
    "run",
    "--rm",
    "--pull=never",
    "--network",
    "none",
    "--read-only",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "128",
    "--memory",
    "2g",
    "--memory-swap",
    "2g",
    "--cpus",
    "2",
    "--user",
    "65534:65534",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,nodev,size=512m",
    "--mount",
    "type=bind,src={prepared_source},dst=/workspace,readonly",
    "--mount",
    "type=bind,src={mpmath_source},dst=/opt/site-packages/mpmath,readonly",
    "--env",
    "HOME=/tmp",
    "--env",
    "TEMP=/tmp",
    "--env",
    "TMP=/tmp",
    "--env",
    "TMPDIR=/tmp",
    "--env",
    "NO_COLOR=1",
    "--env",
    "TERM=dumb",
    IMAGE_ID,
    "-W",
    "ignore::UserWarning",
    "-W",
    "ignore::SyntaxWarning",
    "bin/test",
    "-C",
    "--verbose",
    "sympy/printing/tests/test_mathml.py",
]

EXPECTED_EXECUTION_CONTRACT = {
    "runner_member": "runner/run_paired_sympy.sh",
    "runner_bytes": 2_431,
    "runner_sha256": "57716a5f380e9cb4b2f20a2b79920aaebe8e6170d93d17ed1b327f9055071f94",
    "shell": "/bin/bash",
    "timeout_seconds": None,
    "stdout_stderr_capture": "combined_complete_log",
    "prepared_source_placeholder": "{prepared_source}",
    "mpmath_source_placeholder": "{mpmath_source}",
    "docker_argv_template": EXPECTED_DOCKER_ARGV,
}

EXPECTED_ROLES = {
    "baseline": {
        "name": "baseline",
        "kind": "base_plus_oracle_test_patch_control",
        "input_patch_sha256": None,
    },
    "gpt5": {
        "name": "gpt5",
        "kind": "candidate",
        "input_patch_sha256": (
            "e2fd0256c4495c795129805efd83292f35d9ae656a67bbe55317382d88571971"
        ),
    },
    "kimi_k2": {
        "name": "kimi_k2",
        "kind": "candidate",
        "input_patch_sha256": (
            "3e098af68d2c527fdcd4344effbc71789965cb74f14d20b69eb8458080787686"
        ),
    },
    "claude_4_sonnet": {
        "name": "claude_4_sonnet",
        "kind": "candidate",
        "input_patch_sha256": (
            "47ac3303f188d01602f5fb74b14b8f4f10281cfbc87707d17bde2e088c7c3585"
        ),
    },
    "gold": {
        "name": "gold",
        "kind": "canonical_gold_sanity_control",
        "input_patch_sha256": (
            "cb296790ccb26aebc97be249df44650cf9cb0653637fd340996e384e632196ae"
        ),
    },
}

PASS_RESULT = {"status": "passed", "passed": 39, "failed": 0, "total": 39, "target": "passed"}
FAIL_RESULT = {"status": "failed", "passed": 38, "failed": 1, "total": 39, "target": "failed"}
EXPECTED_RESULTS = {
    "baseline": FAIL_RESULT,
    "gpt5": PASS_RESULT,
    "kimi_k2": FAIL_RESULT,
    "claude_4_sonnet": PASS_RESULT,
    "gold": PASS_RESULT,
}

# started, finished, return code, log bytes, log SHA-256
EXPECTED_RUN_RECEIPTS: dict[tuple[str, int], tuple[str, str, int, int, str]] = {
    ("baseline", 1): (
        "2026-07-13T13:18:51Z",
        "2026-07-13T13:18:52Z",
        1,
        2_080,
        "76ba853d1b430062a3281f64aedef40ea7eb838a5c529a1e87aa2b2f0757e0a4",
    ),
    ("baseline", 2): (
        "2026-07-13T13:18:52Z",
        "2026-07-13T13:18:54Z",
        1,
        2_080,
        "384c2efcedf6a1182c695599d7ef812c29992bda9f562f854fdeb338745a7ad5",
    ),
    ("baseline", 3): (
        "2026-07-13T13:18:54Z",
        "2026-07-13T13:18:55Z",
        1,
        2_079,
        "8b1c9f37b4adc7ab596d36fb68579fac3fd716b02afc958ae55ab9377b6b1d31",
    ),
    ("gpt5", 1): (
        "2026-07-13T13:18:55Z",
        "2026-07-13T13:18:56Z",
        0,
        1_722,
        "d9a039426aa030aebade85fb7f50bfb02d1a1e6d87fdddbac6237e337093b300",
    ),
    ("gpt5", 2): (
        "2026-07-13T13:18:56Z",
        "2026-07-13T13:18:57Z",
        0,
        1_722,
        "c72e2e2449ddf8aaee7912b6cbd901f1a6254043cdd2f99f5eea9d86132bc552",
    ),
    ("gpt5", 3): (
        "2026-07-13T13:18:57Z",
        "2026-07-13T13:18:58Z",
        0,
        1_721,
        "4ad655477c70a2e64899d4f06924fcc6c68f1ec4df4dd50b8341439c95e42ef5",
    ),
    ("kimi_k2", 1): (
        "2026-07-13T13:18:58Z",
        "2026-07-13T13:19:00Z",
        1,
        2_080,
        "e83647409cb9086f71383cf30e3d3e30cb0dc3aec2c27335c93b779687fa7258",
    ),
    ("kimi_k2", 2): (
        "2026-07-13T13:19:00Z",
        "2026-07-13T13:19:01Z",
        1,
        2_080,
        "e5ac3d752a6bf5217697c7949db70bb5d1e1d137acca5bb751ff7309e4806aaf",
    ),
    ("kimi_k2", 3): (
        "2026-07-13T13:19:01Z",
        "2026-07-13T13:19:02Z",
        1,
        2_079,
        "16664591d8c7aa3e375dc90b3b194d9e51accba532ca01ff4b680198be476a50",
    ),
    ("claude_4_sonnet", 1): (
        "2026-07-13T13:19:02Z",
        "2026-07-13T13:19:03Z",
        0,
        1_722,
        "5241726788bcbdf6c999adfc7489fc670ad23d562fb72c923ed34bf27bcb55e2",
    ),
    ("claude_4_sonnet", 2): (
        "2026-07-13T13:19:03Z",
        "2026-07-13T13:19:05Z",
        0,
        1_722,
        "bbdfe6669563ec796be90d1527d0638ae007606cd9e3e9c996928c7b20b018cd",
    ),
    ("claude_4_sonnet", 3): (
        "2026-07-13T13:19:05Z",
        "2026-07-13T13:19:06Z",
        0,
        1_722,
        "9ee9cf75cc8d53d5c69917d302f44f9d9664b83775a144337ac5e0ec3d36dd78",
    ),
    ("gold", 1): (
        "2026-07-13T13:19:06Z",
        "2026-07-13T13:19:07Z",
        0,
        1_722,
        "39a64417310e518ada8070dc44b1e81e97e92480a3930aa73d55e7a5e7ccb4f4",
    ),
    ("gold", 2): (
        "2026-07-13T13:19:07Z",
        "2026-07-13T13:19:08Z",
        0,
        1_722,
        "c1ed8beed163460063fcc55e3014f8de239327cf49430046e960cbe6c8f65db7",
    ),
    ("gold", 3): (
        "2026-07-13T13:19:08Z",
        "2026-07-13T13:19:09Z",
        0,
        1_722,
        "f84de4a195bef9c313f665e9bae895d8f78789b6df8af3e2325062357261b6de",
    ),
}

EXPECTED_SUPPORTING_MEMBERS = {
    "build/Dockerfile": (504, DOCKERFILE_SHA256),
    "dependencies/mpmath-1.3.0-METADATA": (
        8_630,
        "44b66ea444b9c0d19ae94815d356bf047ae6b680c19268b5c265687cd6a81406",
    ),
    "dependencies/mpmath-mounted-tree.tsv": (
        19_122,
        "df5f953e1a9a06c64dc2ee7361d1eae06be1ccb3bb80362a4399692984dedae9",
    ),
    "raw/acquisitions.tsv": (
        1_937,
        "171ad013ad614977c40c700398eacbfba853b6356202f37703749cd06ca7fd11",
    ),
    "raw/build-inputs.sha256": (
        319,
        "1a1a4c30db8836b6a0e108446ac35889f87f0ab7189483c49d7e7998ae86014c",
    ),
    "raw/docker-version.txt": (
        754,
        "3b8440f29d2a83a9adcbd4814ea4c5992d69074ec9fbebe7b864fc92acdb0e04",
    ),
    "raw/host-uname.txt": (
        150,
        "73e7a99fa63b21fe92beef9f978b6f7ff8fb2a5e0d35eaf1f0007b9b947435e2",
    ),
    "raw/image-inspect.json": (
        3_151,
        "ec02e35264c36fc614a7dcd2ba0771f9856e2fd7af8787654f5c88c6366b86de",
    ),
    "runner/run_paired_sympy.sh": (
        2_431,
        "57716a5f380e9cb4b2f20a2b79920aaebe8e6170d93d17ed1b327f9055071f94",
    ),
}

EXPECTED_LIMITATIONS = (
    "one manually selected task; no population estimate or routing evidence",
    "retrospective post-draft execution; candidate patches and hosted outcomes were already visible",
    "locally constructed Linux arm64 image; not an official SWE-bench image or official harness reproduction",
    "the Dockerfile names node:18 rather than pinning its digest; the exact local base image ID is bound separately but lacks a contemporaneous inspect receipt in the bundle",
    "the container reused prepared workspaces from the container-free arm; preparation was not independently repeated or re-attested",
    "one targeted test file, not the complete SWE-bench harness or full repository suite",
    "the mpmath metadata and mounted-tree receipt were collected after execution, not as a before-and-after attestation",
    "Docker Desktop virtualization on one arm64 host; no remote Linux CI or cross-architecture evidence",
    "the runner imposed resource and sandbox bounds but no wall-clock timeout",
    "test and hash-randomization seeds varied between repeats and were not controlled",
    "execution is a fallible measurement; base-fails and gold-passes are sanity controls, not semantic ground truth",
    "no prospective claim, no policy comparison, and no evidence for hypotheses H1-H6",
)


class EvidenceError(ValueError):
    """The checked-in claim or its external evidence is invalid."""


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> NoReturn:
    raise EvidenceError(f"non-finite JSON number: {value}")


def strict_json_loads(payload: bytes | str) -> Any:
    """Decode UTF-8 JSON while rejecting duplicate keys and non-finite numbers."""

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


def _as_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvidenceError(f"{path} must be an object with string keys")
    return value


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceError(f"{path} must be an array")
    return value


def _expect_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise EvidenceError(
            f"{path} keys differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _strictly_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _strictly_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strictly_equal(left, right) for left, right in zip(actual, expected)
        )
    return bool(actual == expected)


def _expect_equal(actual: Any, expected: Any, path: str) -> None:
    if not _strictly_equal(actual, expected):
        raise EvidenceError(f"{path} differs: expected {expected!r}, got {actual!r}")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _expect_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise EvidenceError(f"{path} must be a lowercase SHA-256")
    return value


def _expect_nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceError(f"{path} must be a non-negative integer")
    return value


def _parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceError(f"{path} must be an ISO UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"{path} is not a valid timestamp") from exc


def _safe_relative_path(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise EvidenceError(f"{path} must be a portable relative path")
    pure = pathlib.PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or value != pure.as_posix():
        raise EvidenceError(f"{path} must be a confined relative path")
    return value


def _validate_identity(value: Any, path: str) -> tuple[str, int, str]:
    identity = _as_dict(value, path)
    _expect_keys(identity, {"path", "bytes", "sha256"}, path)
    member = _safe_relative_path(identity["path"], f"{path}.path")
    byte_count = _expect_nonnegative_int(identity["bytes"], f"{path}.bytes")
    digest = _expect_sha256(identity["sha256"], f"{path}.sha256")
    return member, byte_count, digest


def load_manifest(path: pathlib.Path = MANIFEST_PATH) -> dict[str, Any]:
    return _as_dict(strict_json_loads(path.read_bytes()), "manifest")


def _validate_fixed_object(value: Any, expected: dict[str, Any], path: str) -> None:
    item = _as_dict(value, path)
    _expect_keys(item, set(expected), path)
    _expect_equal(item, expected, path)


def _validate_roles(value: Any) -> None:
    roles = _as_list(value, "roles")
    if len(roles) != len(ROLE_ORDER):
        raise EvidenceError("roles must contain exactly five entries")
    seen: set[str] = set()
    for index, raw_role in enumerate(roles):
        role = _as_dict(raw_role, f"roles[{index}]")
        _expect_keys(role, {"name", "kind", "input_patch_sha256"}, f"roles[{index}]")
        name = role.get("name")
        if not isinstance(name, str) or name not in EXPECTED_ROLES or name in seen:
            raise EvidenceError(f"invalid or duplicate role: {name!r}")
        seen.add(name)
        _expect_equal(role, EXPECTED_ROLES[name], f"role {name}")
    _expect_equal([role["name"] for role in roles], list(ROLE_ORDER), "role order")


def _validate_supporting_members(value: Any) -> dict[str, tuple[int, str]]:
    members = _as_list(value, "evidence_bundle.supporting_members")
    if len(members) != len(EXPECTED_SUPPORTING_MEMBERS):
        raise EvidenceError("supporting member count differs")
    result: dict[str, tuple[int, str]] = {}
    for index, raw_member in enumerate(members):
        member, byte_count, digest = _validate_identity(
            raw_member, f"evidence_bundle.supporting_members[{index}]"
        )
        if member in result:
            raise EvidenceError(f"duplicate supporting member: {member}")
        result[member] = (byte_count, digest)
    _expect_equal(result, EXPECTED_SUPPORTING_MEMBERS, "supporting member identities")
    return result


def _validate_runs(value: Any) -> list[dict[str, Any]]:
    runs = _as_list(value, "runs")
    if len(runs) != len(EXPECTED_RUN_RECEIPTS):
        raise EvidenceError("runs must contain exactly 15 acquisitions")
    seen: set[tuple[str, int]] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw_run in enumerate(runs):
        run = _as_dict(raw_run, f"runs[{index}]")
        _expect_keys(
            run,
            {"role", "repeat", "started_at", "finished_at", "return_code", "log", "result"},
            f"runs[{index}]",
        )
        role = run.get("role")
        repeat = run.get("repeat")
        if not isinstance(role, str) or role not in EXPECTED_RESULTS:
            raise EvidenceError(f"runs[{index}].role is invalid")
        if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat not in {1, 2, 3}:
            raise EvidenceError(f"runs[{index}].repeat is invalid")
        key = (role, repeat)
        if key in seen or key not in EXPECTED_RUN_RECEIPTS:
            raise EvidenceError(f"duplicate or unexpected run: {key!r}")
        seen.add(key)

        started, finished, return_code, log_bytes, log_sha = EXPECTED_RUN_RECEIPTS[key]
        _expect_equal(run["started_at"], started, f"{key}.started_at")
        _expect_equal(run["finished_at"], finished, f"{key}.finished_at")
        _expect_equal(run["return_code"], return_code, f"{key}.return_code")
        start_dt = _parse_timestamp(run["started_at"], f"{key}.started_at")
        finish_dt = _parse_timestamp(run["finished_at"], f"{key}.finished_at")
        if finish_dt < start_dt:
            raise EvidenceError(f"{key} finished before it started")

        member, byte_count, digest = _validate_identity(run["log"], f"{key}.log")
        expected_member = f"raw/{role}-repeat-{repeat}.log"
        _expect_equal(member, expected_member, f"{key}.log.path")
        _expect_equal(byte_count, log_bytes, f"{key}.log.bytes")
        _expect_equal(digest, log_sha, f"{key}.log.sha256")
        _validate_fixed_object(run["result"], EXPECTED_RESULTS[role], f"{key}.result")
        normalized.append(run)

    _expect_equal(
        [(run["role"], run["repeat"]) for run in normalized],
        [(role, repeat) for role in ROLE_ORDER for repeat in (1, 2, 3)],
        "run order",
    )
    return normalized


def _derive_aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    passed_runs = sum(run["result"]["status"] == "passed" for run in runs)
    intervals = []
    for run in runs:
        started = _parse_timestamp(run["started_at"], "run.started_at")
        finished = _parse_timestamp(run["finished_at"], "run.finished_at")
        intervals.append((finished - started).total_seconds())
    role_results: list[dict[str, Any]] = []
    all_agree = True
    for role in ROLE_ORDER:
        selected = [run for run in runs if run["role"] == role]
        expected = EXPECTED_RESULTS[role]
        all_agree = all_agree and len(selected) == 3 and all(
            _strictly_equal(run["result"], expected) for run in selected
        )
        role_results.append(
            {"role": role, "repeat_count": len(selected), **expected}
        )
    return {
        "execution_count": len(runs),
        "passed_run_count": passed_runs,
        "failed_run_count": len(runs) - passed_runs,
        "recorded_interval_seconds": int(math.fsum(intervals)),
        "all_role_repeats_agree": all_agree,
        "paired_arm_matches_independent_arm": True,
        "role_results": role_results,
    }


def _validate_aggregate(value: Any, runs: list[dict[str, Any]]) -> None:
    aggregate = _as_dict(value, "aggregate")
    _expect_keys(
        aggregate,
        {
            "execution_count",
            "passed_run_count",
            "failed_run_count",
            "recorded_interval_seconds",
            "all_role_repeats_agree",
            "paired_arm_matches_independent_arm",
            "role_results",
        },
        "aggregate",
    )
    role_results = _as_list(aggregate["role_results"], "aggregate.role_results")
    for index, raw_result in enumerate(role_results):
        result = _as_dict(raw_result, f"aggregate.role_results[{index}]")
        _expect_keys(
            result,
            {"role", "repeat_count", "status", "passed", "failed", "total", "target"},
            f"aggregate.role_results[{index}]",
        )
    _expect_equal(aggregate, _derive_aggregate(runs), "aggregate derived from runs")


def verify_manifest(manifest: dict[str, Any]) -> None:
    """Validate the canonical schema, identities, outcomes, and claim boundary."""

    _expect_keys(
        manifest,
        {
            "schema_version",
            "study_id",
            "classification",
            "task",
            "relation_to_independent_smoke",
            "runtime",
            "roles",
            "evidence_bundle",
            "runs",
            "aggregate",
            "limitations",
        },
        "manifest",
    )
    _expect_equal(manifest["schema_version"], SCHEMA_VERSION, "schema_version")
    _expect_equal(manifest["study_id"], STUDY_ID, "study_id")
    _validate_fixed_object(manifest["classification"], EXPECTED_CLASSIFICATION, "classification")
    _validate_fixed_object(manifest["task"], EXPECTED_TASK, "task")

    relation = _as_dict(manifest["relation_to_independent_smoke"], "relation")
    _expect_keys(relation, set(EXPECTED_RELATION), "relation")
    _validate_fixed_object(
        relation["manifest"],
        _as_dict(EXPECTED_RELATION["manifest"], "expected relation manifest"),
        "relation.manifest",
    )
    _expect_equal(relation, EXPECTED_RELATION, "relation")

    runtime = _as_dict(manifest["runtime"], "runtime")
    _expect_keys(
        runtime,
        {"docker", "image", "dockerfile", "python", "mpmath", "execution_contract"},
        "runtime",
    )
    _validate_fixed_object(runtime["docker"], EXPECTED_DOCKER, "runtime.docker")
    _validate_fixed_object(runtime["image"], EXPECTED_IMAGE, "runtime.image")
    _validate_fixed_object(runtime["dockerfile"], EXPECTED_DOCKERFILE, "runtime.dockerfile")
    _validate_fixed_object(runtime["python"], EXPECTED_PYTHON, "runtime.python")
    _validate_fixed_object(runtime["mpmath"], EXPECTED_MPMATH, "runtime.mpmath")
    _validate_fixed_object(
        runtime["execution_contract"], EXPECTED_EXECUTION_CONTRACT, "runtime.execution_contract"
    )
    _validate_roles(manifest["roles"])

    bundle = _as_dict(manifest["evidence_bundle"], "evidence_bundle")
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
            "supporting_members",
        },
        "evidence_bundle",
    )
    _expect_equal(
        {key: bundle[key] for key in bundle if key != "supporting_members"},
        {
            "logical_filename": "bench-cleanser-paired-sympy-15976-evidence.tar.gz",
            "media_type": "application/gzip",
            "bytes": BUNDLE_BYTES,
            "sha256": BUNDLE_SHA256,
            "root_directory": BUNDLE_ROOT,
            "file_member_count": 24,
            "maximum_file_member_bytes": 19_122,
            "location_contract": (
                "external_content_addressed_artifact; no mutable local path is canonical"
            ),
        },
        "evidence_bundle identity",
    )
    _validate_supporting_members(bundle["supporting_members"])
    runs = _validate_runs(manifest["runs"])
    _validate_aggregate(manifest["aggregate"], runs)
    _expect_equal(manifest["limitations"], list(EXPECTED_LIMITATIONS), "limitations")

    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    if "/private/tmp/" in serialized or "file:///tmp/" in serialized:
        raise EvidenceError("canonical manifest contains a mutable host scratch path")


def _expected_member_identities(manifest: dict[str, Any]) -> dict[str, tuple[int, str]]:
    bundle = _as_dict(manifest["evidence_bundle"], "evidence_bundle")
    result = _validate_supporting_members(bundle["supporting_members"])
    for raw_run in _as_list(manifest["runs"], "runs"):
        run = _as_dict(raw_run, "run")
        member, byte_count, digest = _validate_identity(run["log"], "run.log")
        if member in result:
            raise EvidenceError(f"evidence member identity reused: {member}")
        result[member] = (byte_count, digest)
    return result


def _read_archive_members(
    path: pathlib.Path,
    *,
    root: str,
    maximum_member_bytes: int,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
) -> dict[str, bytes]:
    """Read confined regular members; optional identity checks support unit tests."""

    archive = path.read_bytes()
    if expected_bytes is not None and len(archive) != expected_bytes:
        raise EvidenceError("external evidence archive byte count differs")
    if expected_sha256 is not None and _sha256(archive) != expected_sha256:
        raise EvidenceError("external evidence archive SHA-256 differs")
    result: dict[str, bytes] = {}
    seen_names: set[str] = set()
    try:
        with tarfile.open(path, mode="r:gz") as handle:
            for member in handle.getmembers():
                if member.name in seen_names:
                    raise EvidenceError(f"duplicate archive member: {member.name}")
                seen_names.add(member.name)
                if "\\" in member.name:
                    raise EvidenceError(f"non-portable archive member: {member.name}")
                pure = pathlib.PurePosixPath(member.name)
                if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                    raise EvidenceError(f"unsafe archive member: {member.name}")
                if pure.parts[0] != root:
                    raise EvidenceError(f"unexpected archive root: {member.name}")
                if member.isdir():
                    continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise EvidenceError(f"non-regular archive member: {member.name}")
                if member.size <= 0 or member.size > maximum_member_bytes:
                    raise EvidenceError(f"archive member outside byte bound: {member.name}")
                if len(pure.parts) < 2:
                    raise EvidenceError(f"archive file cannot be the root: {member.name}")
                relative = pathlib.PurePosixPath(*pure.parts[1:]).as_posix()
                if relative in result:
                    raise EvidenceError(f"duplicate archive member: {relative}")
                stream = handle.extractfile(member)
                if stream is None:
                    raise EvidenceError(f"cannot read archive member: {member.name}")
                payload = stream.read(maximum_member_bytes + 1)
                if len(payload) != member.size:
                    raise EvidenceError(f"archive member size mismatch: {member.name}")
                result[relative] = payload
    except tarfile.TarError as exc:
        raise EvidenceError("invalid evidence tar archive") from exc
    return result


def _parse_log(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError("execution log is not UTF-8") from exc
    summaries = list(_SUMMARY_RE.finditer(text))
    targets = list(_TARGET_RE.finditer(text))
    if len(summaries) != 1 or len(targets) != 1:
        raise EvidenceError("execution log lacks one unambiguous summary and target status")
    if text.count("sympy/printing/tests/test_mathml.py[39]") != 1:
        raise EvidenceError("execution log does not bind the expected 39-test file")
    if text.count("/opt/python/bin/python  (3.9.25-final-0) [CPython]") != 1:
        raise EvidenceError("execution log does not bind CPython 3.9.25")
    passed = int(summaries[0].group("passed"))
    failed_text = summaries[0].group("failed")
    failed = 0 if failed_text is None else int(failed_text)
    target = "passed" if targets[0].group("status") == "ok" else "failed"
    if passed + failed != 39:
        raise EvidenceError("execution log summary does not total 39 tests")
    status = "passed" if failed == 0 else "failed"
    if (target == "passed") != (status == "passed"):
        raise EvidenceError("target and aggregate status conflict")
    return {"status": status, "passed": passed, "failed": failed, "total": 39, "target": target}


def _parse_acquisitions(payload: bytes) -> dict[tuple[str, int], dict[str, Any]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError("acquisitions table is not UTF-8") from exc
    expected_header = [
        "role",
        "repeat",
        "started_at",
        "finished_at",
        "return_code",
        "log_bytes",
        "log_sha256",
    ]
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if reader.fieldnames != expected_header or len(set(reader.fieldnames or [])) != len(expected_header):
        raise EvidenceError("acquisitions table header differs or contains duplicates")
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for row_index, raw_row in enumerate(reader, start=2):
        if set(raw_row) != set(expected_header) or any(value is None for value in raw_row.values()):
            raise EvidenceError(f"malformed acquisitions row {row_index}")
        try:
            repeat = int(raw_row["repeat"] or "")
            return_code = int(raw_row["return_code"] or "")
            log_bytes = int(raw_row["log_bytes"] or "")
        except ValueError as exc:
            raise EvidenceError(f"non-integer acquisitions value on row {row_index}") from exc
        role = raw_row["role"] or ""
        key = (role, repeat)
        if key in result:
            raise EvidenceError(f"duplicate acquisition row: {key!r}")
        digest = _expect_sha256(raw_row["log_sha256"], f"acquisitions row {row_index}")
        result[key] = {
            "role": role,
            "repeat": repeat,
            "started_at": raw_row["started_at"],
            "finished_at": raw_row["finished_at"],
            "return_code": return_code,
            "log_bytes": log_bytes,
            "log_sha256": digest,
        }
    if len(result) != 15:
        raise EvidenceError("acquisitions table must contain 15 rows")
    return result


def _validate_mpmath_receipts(members: Mapping[str, bytes]) -> None:
    metadata = members["dependencies/mpmath-1.3.0-METADATA"]
    try:
        metadata_text = metadata.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError("mpmath METADATA is not UTF-8") from exc
    if metadata_text.count("\nName: mpmath\n") != 1 or metadata_text.count("\nVersion: 1.3.0\n") != 1:
        raise EvidenceError("mpmath METADATA does not bind name and version")

    tree = members["dependencies/mpmath-mounted-tree.tsv"]
    try:
        tree_text = tree.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError("mpmath tree receipt is not UTF-8") from exc
    seen: set[str] = set()
    total_bytes = 0
    lines = tree_text.splitlines()
    for index, line in enumerate(lines, start=1):
        match = _TREE_LINE_RE.fullmatch(line)
        if match is None:
            raise EvidenceError(f"invalid mpmath tree receipt line {index}")
        relative = _safe_relative_path(match.group("path"), f"mpmath tree line {index}")
        if not relative.startswith("mpmath/") or relative in seen:
            raise EvidenceError(f"invalid or duplicate mpmath path: {relative}")
        seen.add(relative)
        total_bytes += int(match.group("bytes"))
    if len(seen) != 174 or total_bytes != 3_603_837:
        raise EvidenceError("mpmath mounted-tree aggregate differs")


def _validate_image_receipt(payload: bytes) -> None:
    raw = _as_list(strict_json_loads(payload), "image inspect")
    if len(raw) != 1:
        raise EvidenceError("image inspect must contain one image")
    image = _as_dict(raw[0], "image inspect[0]")
    _expect_equal(image.get("Id"), IMAGE_ID, "image Id")
    _expect_equal(image.get("RepoDigests"), [f"bench-cleanser/sympy-paired-runtime@{IMAGE_ID}"], "image RepoDigests")
    _expect_equal(image.get("Architecture"), "arm64", "image architecture")
    _expect_equal(image.get("Os"), "linux", "image os")
    _expect_equal(image.get("Size"), 469_094_980, "image size")
    config = _as_dict(image.get("Config"), "image Config")
    _expect_equal(config.get("Entrypoint"), ["/opt/python/bin/python"], "image Entrypoint")
    _expect_equal(config.get("WorkingDir"), "/workspace", "image WorkingDir")
    env = config.get("Env")
    if not isinstance(env, list) or not all(isinstance(item, str) for item in env):
        raise EvidenceError("image Env must be a string array")
    required_env = {
        "PATH=/opt/python/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH=/opt/site-packages",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        "TZ=UTC",
    }
    if not required_env.issubset(set(env)):
        raise EvidenceError("image Env lacks required runtime values")


def _validate_supporting_content(members: Mapping[str, bytes]) -> None:
    dockerfile = members["build/Dockerfile"].decode("utf-8")
    if not dockerfile.startswith("FROM node:18\n") or "FROM node:18@sha256:" in dockerfile:
        raise EvidenceError("Dockerfile base reference differs")
    if "COPY cpython-3.9.25-20251031-aarch64-linux-gnu-install_only.tar.gz" not in dockerfile:
        raise EvidenceError("Dockerfile does not bind the expected Python archive name")

    runner = members["runner/run_paired_sympy.sh"].decode("utf-8")
    required_runner_fragments = (
        f"image={IMAGE_ID}",
        "--pull=never",
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--pids-limit 128",
        "--memory 2g",
        "--memory-swap 2g",
        "--cpus 2",
        "--user 65534:65534",
        "dst=/workspace,readonly",
        "dst=/opt/site-packages/mpmath,readonly",
        "bin/test -C --verbose sympy/printing/tests/test_mathml.py",
    )
    if any(fragment not in runner for fragment in required_runner_fragments):
        raise EvidenceError("runner bytes do not implement the canonical sandbox/CLI contract")

    build_inputs = members["raw/build-inputs.sha256"].decode("utf-8").splitlines()
    parsed_inputs: dict[str, str] = {}
    for line in build_inputs:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise EvidenceError("invalid build-input receipt")
        name = pathlib.PurePosixPath(match.group(2)).name
        if name in parsed_inputs:
            raise EvidenceError(f"duplicate build input: {name}")
        parsed_inputs[name] = match.group(1)
    _expect_equal(
        parsed_inputs,
        {
            "Dockerfile": DOCKERFILE_SHA256,
            "cpython-3.9.25-20251031-aarch64-linux-gnu-install_only.tar.gz": (
                PYTHON_ARCHIVE_SHA256
            ),
        },
        "build inputs",
    )

    docker_version = members["raw/docker-version.txt"].decode("utf-8")
    if len(re.findall(r"(?m)^ +Version: +28\.1\.1$", docker_version)) != 2:
        raise EvidenceError("Docker client/server version receipt differs")
    if "OS/Arch:          linux/arm64" not in docker_version:
        raise EvidenceError("Docker server platform receipt differs")
    host = members["raw/host-uname.txt"].decode("utf-8")
    if not host.startswith("Darwin ") or not host.rstrip().endswith("arm64"):
        raise EvidenceError("host uname receipt differs")
    _validate_image_receipt(members["raw/image-inspect.json"])
    _validate_mpmath_receipts(members)


def verify_external_bundle(manifest: dict[str, Any], bundle_path: pathlib.Path) -> None:
    """Authenticate every member and recompute all run and aggregate results."""

    verify_manifest(manifest)
    bundle = _as_dict(manifest["evidence_bundle"], "evidence_bundle")
    members = _read_archive_members(
        bundle_path,
        root=BUNDLE_ROOT,
        maximum_member_bytes=int(bundle["maximum_file_member_bytes"]),
        expected_bytes=BUNDLE_BYTES,
        expected_sha256=BUNDLE_SHA256,
    )
    expected = _expected_member_identities(manifest)
    if set(members) != set(expected):
        raise EvidenceError(
            f"evidence member set differs: missing={sorted(set(expected) - set(members))}, "
            f"unknown={sorted(set(members) - set(expected))}"
        )
    for member, (byte_count, digest) in expected.items():
        payload = members[member]
        _expect_equal(len(payload), byte_count, f"{member} byte count")
        _expect_equal(_sha256(payload), digest, f"{member} SHA-256")

    acquisitions = _parse_acquisitions(members["raw/acquisitions.tsv"])
    raw_runs: list[dict[str, Any]] = []
    for raw_run in _as_list(manifest["runs"], "runs"):
        run = _as_dict(raw_run, "run")
        role = str(run["role"])
        repeat = int(run["repeat"])
        key = (role, repeat)
        log_identity = _as_dict(run["log"], "run.log")
        acquisition = acquisitions.get(key)
        if acquisition is None:
            raise EvidenceError(f"missing acquisition row: {key!r}")
        _expect_equal(acquisition["started_at"], run["started_at"], f"{key} acquisition start")
        _expect_equal(acquisition["finished_at"], run["finished_at"], f"{key} acquisition finish")
        _expect_equal(acquisition["return_code"], run["return_code"], f"{key} acquisition return")
        _expect_equal(acquisition["log_bytes"], log_identity["bytes"], f"{key} acquisition bytes")
        _expect_equal(acquisition["log_sha256"], log_identity["sha256"], f"{key} acquisition SHA")

        parsed = _parse_log(members[str(log_identity["path"])])
        _expect_equal(parsed, run["result"], f"{key} result recomputed from raw log")
        expected_return = 0 if parsed["status"] == "passed" else 1
        _expect_equal(run["return_code"], expected_return, f"{key} return/result mapping")
        raw_runs.append({**run, "result": parsed})

    _expect_equal(
        _derive_aggregate(raw_runs),
        manifest["aggregate"],
        "aggregate recomputed from raw logs",
    )
    _validate_supporting_content(members)


def verify_local_independent_relation(manifest: dict[str, Any]) -> None:
    """Verify the related checked-in independent-smoke manifest when present."""

    relation = _as_dict(manifest["relation_to_independent_smoke"], "relation")
    identity = _as_dict(relation["manifest"], "relation.manifest")
    repository_root = pathlib.Path(__file__).resolve().parents[2]
    logical = _safe_relative_path(identity["logical_path"], "relation.manifest.logical_path")
    path = repository_root / logical
    payload = path.read_bytes()
    _expect_equal(len(payload), identity["bytes"], "independent manifest byte count")
    _expect_equal(_sha256(payload), identity["sha256"], "independent manifest SHA-256")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=pathlib.Path, default=MANIFEST_PATH)
    parser.add_argument("--bundle", type=pathlib.Path, help="external content-addressed .tar.gz")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        verify_manifest(manifest)
        verify_local_independent_relation(manifest)
        if args.bundle is not None:
            verify_external_bundle(manifest, args.bundle)
    except (EvidenceError, OSError, UnicodeDecodeError) as exc:
        print(f"evidence verification failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "bundle_verified": args.bundle is not None,
                "classification": EXPECTED_CLASSIFICATION["stage"],
                "execution_count": EXPECTED_CLASSIFICATION["execution_count"],
                "independent_relation_verified": True,
                "manifest_verified": True,
                "study_id": STUDY_ID,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
