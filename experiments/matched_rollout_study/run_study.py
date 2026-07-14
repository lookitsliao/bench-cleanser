#!/usr/bin/env python3
"""Acquire and analyze a matched, three-rollout SWE-bench development cohort.

The study deliberately separates three phases:

1. freeze an outcome-blind common-task cohort and acquire opaque artifacts;
2. freeze patch-static/post-rollout-history features and every candidate order;
3. decode hosted outcomes and evaluate equal-budget Best-of-N policies.

Hosted SWE-bench reports are retrospective development proxies.  They are not
independently reproduced executions, semantic ground truth, or valid-task
adjudications.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import math
import os
import pathlib
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, TypeAlias

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_loads,
)
from bench_cleanser.verification.manifest import build_candidate_manifest
from bench_cleanser.verification.models import LifecycleStage
from bench_cleanser.verification.router import ConservativeRouter

ACQUISITION_SCHEMA_VERSION = "matched-rollout-acquisition-0.2.0"
FREEZE_SCHEMA_VERSION = "matched-rollout-feature-freeze-0.2.0"
REPORT_SCHEMA_VERSION = "matched-rollout-report-0.2.0"
STUDY_ID = "openhands-family-checked-three-model-matched-rollout-development-v2"
SOURCE_REVISION = "2f15350cd32becc4569e0d826361048555b605c0"
STUDY_CODE_LOGICAL_PATH = "experiments/matched_rollout_study/run_study.py"
CANONICAL_DATASET_ID = "princeton-nlp/SWE-bench_Verified"
CANONICAL_DATASET_REVISION = "c104f840cc67f8b6eec6f759ebc8b2693d585d4a"
CANONICAL_DATASET_AUTHORITATIVE_URL = (
    "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/"
    f"{CANONICAL_DATASET_REVISION}/data/test-00000-of-00001.parquet"
)
CANONICAL_DATASET_MIRROR_REVISION = "f34deb86cca28b6050f181f5514a3eb7d7d70be4"
CANONICAL_DATASET_RETRIEVAL_URL = (
    "https://raw.githubusercontent.com/justin-napolitano/SWE-bench_Verified/"
    f"{CANONICAL_DATASET_MIRROR_REVISION}/data/test-00000-of-00001.parquet"
)
CANONICAL_DATASET_BYTES = 2_096_679
CANONICAL_DATASET_SHA256 = "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"
CANONICAL_DATASET_PROJECTION_SHA256 = (
    "7524bf30de2473f870b23d407eccd489ec398cf4af8cedf11c9364d708582507"
)
CANONICAL_DATASET_PROJECTION_BYTES = 111_075
CANONICAL_DATASET_EXPECTED_COUNT = 500
CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT = "0ab58c120939093fea90822f376e1866fc714d1f"
CANONICAL_DATASET_PROJECTION_FIELDS = (
    "instance_id",
    "repo",
    "base_commit",
    "environment_setup_commit",
)
CANONICAL_DATASET_SCHEMA_FIELDS = (
    "repo",
    "instance_id",
    "base_commit",
    "patch",
    "test_patch",
    "problem_statement",
    "hints_text",
    "created_at",
    "version",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "environment_setup_commit",
    "difficulty",
)
CANONICAL_DATASET_LOCAL_NAME = "canonical-swe-bench-verified.parquet"
BUCKET_NAME = "swe-bench-submissions"
S3_HOST = "swe-bench-submissions.s3.amazonaws.com"
GIT_HOST = "raw.githubusercontent.com"
DEFAULT_REPOSITORY_COUNT = 4
DEFAULT_TASKS_PER_REPOSITORY = 6
DEFAULT_SELECTION_SEED = 20260713
DEFAULT_POLICY_SEED = 20260713
DEFAULT_WORKERS = 8
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_LISTING_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = {
    "patch.diff": 32 * 1024 * 1024,
    "report.json": 64 * 1024 * 1024,
    "trajectory.json": 128 * 1024 * 1024,
}
ARTIFACT_NAMES = tuple(MAX_ARTIFACT_BYTES)
POLICY_NAMES = (
    "hash_random",
    "router_low_risk",
    "patch_smallest",
    "rollout_history_shortest",
    "hybrid_rank_sum",
    "gpt5_first",
    "kimi_k2_first",
    "claude_4_sonnet_first",
)
FEATURE_CONTRACT = "patch-static-post-rollout-history-no-reference-v2"
ORDER_CONTRACT = "matched-task-complete-candidate-permutation-v2"
_S3_NAMESPACE = "http://s3.amazonaws.com/doc/2006-03-01/"
_INSTANCE_RE = re.compile(
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9_.-]*)__"
    r"(?P<repo>[A-Za-z0-9][A-Za-z0-9_.-]*)-(?P<number>[0-9]+)"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class SubmissionSpec:
    """One source-locked, single-attempt OpenHands submission."""

    key: str
    model_label: str
    submission_id: str
    expected_instance_count: int
    metadata_bytes: int
    metadata_sha256: str
    results_bytes: int
    results_sha256: str

    @property
    def root_prefix(self) -> str:
        return f"verified/{self.submission_id}/logs/"

    @property
    def metadata_url(self) -> str:
        return (
            "https://raw.githubusercontent.com/SWE-bench/experiments/"
            f"{SOURCE_REVISION}/evaluation/verified/{self.submission_id}/metadata.yaml"
        )

    @property
    def results_url(self) -> str:
        return (
            "https://raw.githubusercontent.com/SWE-bench/experiments/"
            f"{SOURCE_REVISION}/evaluation/verified/{self.submission_id}/"
            "results/results.json"
        )


SUBMISSIONS = (
    SubmissionSpec(
        key="gpt5",
        model_label="GPT-5",
        submission_id="20250807_openhands_gpt5",
        expected_instance_count=499,
        metadata_bytes=425,
        metadata_sha256=(
            "364c10779ef3e82ed4485b908402538f18b31bf50332e811b033957af012b2ea"  # pinned
        ),
        results_bytes=10_707,
        results_sha256=("4aba4bbf158e4cfb76d717cd617954749058cefecd364aec117bb45415f9b907"),
    ),
    SubmissionSpec(
        key="kimi_k2",
        model_label="Kimi K2",
        submission_id="20250716_openhands_kimi_k2",
        expected_instance_count=500,
        metadata_bytes=438,
        metadata_sha256=(
            "171fe9ec86b2d5380e22c561efb58c71df8cc2d0b000eefa78d16f73249be9bc"  # pinned
        ),
        results_bytes=9_737,
        results_sha256=("0472a5f20a09ef96b60cf45d544d7d19386d845a74a458f25fc30e9c6f898846"),
    ),
    SubmissionSpec(
        key="claude_4_sonnet",
        model_label="Claude 4 Sonnet",
        submission_id="20250524_openhands_claude_4_sonnet",
        expected_instance_count=500,
        metadata_bytes=458,
        metadata_sha256=(
            "0080cd23821dbb299696e808be619e9079c0bd34d1211310514b1ec3e62e881e"  # pinned
        ),
        results_bytes=10_475,
        results_sha256=("14bc7bdfcf3201976fd39c15f23905b112d2ed35ecbebfe656368935e34895d8"),
    ),
)


class TransientFetchError(RuntimeError):
    """A bounded retry may be appropriate for this fetch failure."""


class UnavailableFetchError(RuntimeError):
    """A selected public object is unavailable at its exact source URL."""


@dataclass(frozen=True)
class DownloadedObject:
    payload: bytes
    final_url: str


@dataclass(frozen=True)
class CanonicalTaskIdentity:
    instance_id: str
    repository: str
    base_commit: str
    environment_setup_commit: str

    def to_dict(self) -> dict[str, str]:
        return {
            "instance_id": self.instance_id,
            "repo": self.repository,
            "base_commit": self.base_commit,
            "environment_setup_commit": self.environment_setup_commit,
        }

    def canonical_digest(self) -> str:
        return _sha256(strict_json_dumps(self.to_dict()).encode())


@dataclass(frozen=True)
class FeatureArtifactIdentity:
    """Outcome-sanitized artifact identity allowed into feature construction."""

    instance_id: str
    repository: str
    submission_key: str
    name: str
    availability: str
    relative_path: str | None
    byte_count: int | None
    sha256: str | None
    error_code: str | None


@dataclass(frozen=True)
class FeatureBuildInput:
    """Closed pre-outcome interface: patch, rollout history, and task identity only."""

    selected_instance_ids: tuple[str, ...]
    selected_instance_ids_sha256: str
    submission_keys: tuple[str, ...]
    artifacts: tuple[FeatureArtifactIdentity, ...]
    canonical_task_identities: tuple[CanonicalTaskIdentity, ...]
    canonical_dataset_identity: Mapping[str, Any] | None
    acquisition_code_identity: Mapping[str, Any]


@dataclass(frozen=True)
class FeatureRow:
    instance_id: str
    repository: str
    submission_key: str
    rollout_id: str
    status: str
    candidate_risk: float | None
    files_changed: int | None
    lines_changed: int | None
    rollout_history_nodes: int | None
    feature_record: Mapping[str, Any]


@dataclass(frozen=True)
class OutcomeRow:
    instance_id: str
    repository: str
    submission_key: str
    hosted_resolved: bool | None
    disposition: str
    source: str
    report_record: Mapping[str, Any] | None


class DownloadBudget:
    """Thread-safe hard cap over bytes returned by all fetch attempts."""

    def __init__(self, limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("download byte limit must be a positive integer")
        self.limit = limit
        self._used = 0
        self._lock = threading.Lock()

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    def consume(self, amount: int) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("download accounting must be a non-negative integer")
        with self._lock:
            if self._used + amount > self.limit:
                raise ValueError(
                    "download byte budget exceeded: "
                    f"limit={self.limit}, attempted={self._used + amount}"
                )
            self._used += amount


FetchOnce: TypeAlias = Callable[..., DownloadedObject]
OutcomeDecoder: TypeAlias = Callable[
    [pathlib.Path, Mapping[str, Any], Sequence[SubmissionSpec]],
    tuple[OutcomeRow, ...],
]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _study_code_payload() -> bytes:
    path = pathlib.Path(__file__)
    if path.is_symlink() or not path.is_file():
        raise ValueError("matched-rollout study code must be a regular non-symlink file")
    return path.read_bytes()


def _study_code_identity(payload: bytes | None = None) -> dict[str, Any]:
    code = _study_code_payload() if payload is None else payload
    if not isinstance(code, bytes) or not code:
        raise ValueError("matched-rollout study code must be non-empty bytes")
    return {
        "logical_path": STUDY_CODE_LOGICAL_PATH,
        "bytes": len(code),
        "sha256": _sha256(code),
    }


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON array")
    return value


def _string(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field} must be a trimmed non-empty string")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        raise ValueError(f"{field} is missing fields: {missing}")
    if unknown:
        raise ValueError(f"{field} has unknown fields: {unknown}")


def infer_repository(instance_id: str) -> str:
    """Infer ``owner/repository`` from a confined SWE-bench instance ID."""

    if not isinstance(instance_id, str):
        raise ValueError("instance_id must be a string")
    match = _INSTANCE_RE.fullmatch(instance_id)
    if match is None:
        raise ValueError(f"unconfined or unsupported instance_id {instance_id!r}")
    if any(part in {".", ".."} for part in (match["owner"], match["repo"])):
        raise ValueError(f"instance_id contains a path-like component: {instance_id!r}")
    return f"{match['owner']}/{match['repo']}"


def _submission_map(specs: Sequence[SubmissionSpec]) -> dict[str, SubmissionSpec]:
    if len(specs) < 2:
        raise ValueError("matched-rollout study requires at least two submissions")
    result: dict[str, SubmissionSpec] = {}
    ids: set[str] = set()
    for spec in specs:
        if not isinstance(spec, SubmissionSpec):
            raise TypeError("submission specs must be SubmissionSpec values")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", spec.key):
            raise ValueError(f"invalid submission key {spec.key!r}")
        if spec.key in result or spec.submission_id in ids:
            raise ValueError("submission keys and IDs must be unique")
        if spec.expected_instance_count < 1:
            raise ValueError("expected submission frame count must be positive")
        if spec.metadata_bytes < 1 or spec.results_bytes < 1:
            raise ValueError("pinned source byte counts must be positive")
        if not _SHA256_RE.fullmatch(spec.metadata_sha256) or not _SHA256_RE.fullmatch(
            spec.results_sha256
        ):
            raise ValueError("pinned source digests must be lowercase SHA-256")
        result[spec.key] = spec
        ids.add(spec.submission_id)
    return result


def _frame_listing_url(spec: SubmissionSpec) -> str:
    query = urllib.parse.urlencode(
        {
            "list-type": "2",
            "prefix": spec.root_prefix,
            "delimiter": "/",
            "max-keys": "1000",
        }
    )
    return f"https://{S3_HOST}/?{query}"


def _artifact_url(spec: SubmissionSpec, instance_id: str, name: str) -> str:
    infer_repository(instance_id)
    if name not in ARTIFACT_NAMES:
        raise ValueError(f"artifact name {name!r} is not allowlisted")
    if name == "trajectory.json":
        return f"https://{S3_HOST}/verified/{spec.submission_id}/trajs/{instance_id}.json"
    return f"https://{S3_HOST}/{spec.root_prefix}{instance_id}/{name}"


def _validate_fetch_url(
    url: str,
    *,
    specs: Sequence[SubmissionSpec],
) -> None:
    allowed_sources = {
        source_url
        for spec in specs
        for source_url in (spec.metadata_url, spec.results_url, _frame_listing_url(spec))
    }
    if tuple(specs) == SUBMISSIONS:
        allowed_sources.add(CANONICAL_DATASET_RETRIEVAL_URL)
    if url in allowed_sources:
        parsed = urllib.parse.urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {S3_HOST, GIT_HOST}
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("source URL is not canonical HTTPS")
        return
    for spec in specs:
        logs_prefix = f"https://{S3_HOST}/{spec.root_prefix}"
        trajectory_prefix = f"https://{S3_HOST}/verified/{spec.submission_id}/trajs/"
        if url.startswith(logs_prefix):
            parsed = urllib.parse.urlsplit(url)
            if parsed.query or parsed.fragment or parsed.path.startswith("//"):
                raise ValueError("artifact URL cannot contain query or fragment data")
            relative = url[len(logs_prefix) :]
            try:
                instance_id, name = relative.split("/", 1)
            except ValueError as exc:
                raise ValueError("artifact URL shape is invalid") from exc
            if name not in {"patch.diff", "report.json"}:
                raise ValueError("artifact URL name is not allowlisted")
            infer_repository(instance_id)
            if url != _artifact_url(spec, instance_id, name):
                raise ValueError("artifact URL is not canonical")
            return
        if url.startswith(trajectory_prefix):
            parsed = urllib.parse.urlsplit(url)
            if parsed.query or parsed.fragment or parsed.path.startswith("//"):
                raise ValueError("trajectory URL cannot contain query or fragment data")
            filename = url[len(trajectory_prefix) :]
            if not filename.endswith(".json") or "/" in filename:
                raise ValueError("trajectory URL shape is invalid")
            instance_id = filename.removesuffix(".json")
            infer_repository(instance_id)
            if url != _artifact_url(spec, instance_id, "trajectory.json"):
                raise ValueError("trajectory URL is not canonical")
            return
    raise ValueError(f"fetch URL is outside the exact source allowlist: {url!r}")


def _fetch_once(
    url: str,
    *,
    maximum_bytes: int,
    timeout_seconds: float,
    budget: DownloadBudget,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
) -> DownloadedObject:
    _validate_fetch_url(url, specs=specs)
    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "bench-cleanser-matched-rollout-study/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            _validate_fetch_url(final_url, specs=specs)
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError as exc:
                    raise ValueError("source returned invalid Content-Length") from exc
                if declared_size < 0 or declared_size > maximum_bytes:
                    raise ValueError("source exceeds the per-object byte limit")
            payload = response.read(maximum_bytes + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 404}:
            raise UnavailableFetchError(f"HTTP {exc.code}") from exc
        if exc.code in {408, 425, 429, 500, 502, 503, 504}:
            raise TransientFetchError(f"HTTP {exc.code}") from exc
        raise ValueError(f"non-retriable HTTP status {exc.code}") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise TransientFetchError(type(exc).__name__) from exc
    if len(payload) > maximum_bytes:
        raise ValueError("source exceeds the per-object byte limit")
    budget.consume(len(payload))
    return DownloadedObject(payload=payload, final_url=final_url)


def _fetch_with_retries(
    url: str,
    *,
    maximum_bytes: int,
    timeout_seconds: float,
    retries: int,
    budget: DownloadBudget,
    fetch_once: FetchOnce,
    specs: Sequence[SubmissionSpec],
    sleep: Callable[[float], None],
) -> DownloadedObject:
    if isinstance(retries, bool) or not isinstance(retries, int) or not 1 <= retries <= 5:
        raise ValueError("retries must be an integer between 1 and 5")
    for attempt in range(1, retries + 1):
        try:
            return fetch_once(
                url,
                maximum_bytes=maximum_bytes,
                timeout_seconds=timeout_seconds,
                budget=budget,
                specs=specs,
            )
        except TypeError as exc:
            # Offline fetch fixtures from earlier studies did not accept specs.
            if "specs" not in str(exc):
                raise
            return fetch_once(
                url,
                maximum_bytes=maximum_bytes,
                timeout_seconds=timeout_seconds,
                budget=budget,
            )
        except TransientFetchError:
            if attempt == retries:
                raise
            sleep(min(2 ** (attempt - 1), 4))
    raise AssertionError("retry loop did not return or raise")


def enumerate_instance_ids(
    listing_payload: bytes,
    *,
    spec: SubmissionSpec,
) -> tuple[str, ...]:
    """Validate a complete single-page delimiter listing for one submission."""

    if not isinstance(listing_payload, bytes) or not listing_payload:
        raise ValueError("S3 frame listing must be non-empty bytes")
    if len(listing_payload) > MAX_LISTING_BYTES:
        raise ValueError("S3 frame listing exceeds the byte bound")
    upper = listing_payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/entity declarations are forbidden in S3 listings")
    try:
        root = ET.fromstring(listing_payload)
    except ET.ParseError as exc:
        raise ValueError(f"invalid S3 listing XML: {exc}") from exc
    namespace = f"{{{_S3_NAMESPACE}}}"
    if root.tag != f"{namespace}ListBucketResult":
        raise ValueError("unexpected S3 listing root or namespace")

    def required_text(name: str) -> str:
        elements = root.findall(f"{namespace}{name}")
        if len(elements) != 1 or elements[0].text is None:
            raise ValueError(f"S3 listing must contain exactly one {name}")
        return elements[0].text

    if required_text("Name") != BUCKET_NAME:
        raise ValueError("S3 listing bucket identity drifted")
    if required_text("Prefix") != spec.root_prefix:
        raise ValueError("S3 listing submission prefix drifted")
    if required_text("Delimiter") != "/":
        raise ValueError("S3 listing delimiter drifted")
    if required_text("IsTruncated") != "false":
        raise ValueError("S3 frame listing is truncated")
    try:
        key_count = int(required_text("KeyCount"))
        max_keys = int(required_text("MaxKeys"))
    except ValueError as exc:
        raise ValueError("S3 listing count fields must be integers") from exc
    if key_count != spec.expected_instance_count or max_keys < key_count:
        raise ValueError(
            f"S3 listing count drift for {spec.key}: "
            f"expected {spec.expected_instance_count}, got {key_count}"
        )
    if root.findall(f"{namespace}Contents"):
        raise ValueError("delimiter frame listing cannot contain object keys")
    if root.findall(f"{namespace}NextContinuationToken"):
        raise ValueError("non-truncated frame listing cannot contain a next token")

    instance_ids: list[str] = []
    for item in root.findall(f"{namespace}CommonPrefixes"):
        children = list(item)
        if len(children) != 1 or children[0].tag != f"{namespace}Prefix":
            raise ValueError("malformed CommonPrefixes entry")
        prefix = children[0].text
        if prefix is None or not prefix.startswith(spec.root_prefix) or not prefix.endswith("/"):
            raise ValueError("instance prefix escaped the submission frame")
        instance_id = prefix[len(spec.root_prefix) : -1]
        infer_repository(instance_id)
        if prefix != f"{spec.root_prefix}{instance_id}/":
            raise ValueError("instance prefix is not canonical")
        instance_ids.append(instance_id)
    if len(instance_ids) != key_count:
        raise ValueError("S3 KeyCount contradicts CommonPrefixes")
    if instance_ids != sorted(instance_ids) or len(instance_ids) != len(set(instance_ids)):
        raise ValueError("S3 instance prefixes are duplicate or non-canonical")
    return tuple(instance_ids)


def _selection_hash(instance_id: str, seed: int) -> str:
    material = f"matched-rollout-cohort-v1\0{seed}\0{instance_id}".encode()
    return _sha256(material)


def freeze_common_cohort(
    frames: Mapping[str, Sequence[str]],
    *,
    repository_count: int,
    tasks_per_repository: int,
    seed: int,
) -> dict[str, Any]:
    """Freeze a repository-stratified cohort from IDs only, never outcomes."""

    if not frames:
        raise ValueError("submission frames cannot be empty")
    if isinstance(repository_count, bool) or not isinstance(repository_count, int):
        raise ValueError("repository_count must be an integer")
    if isinstance(tasks_per_repository, bool) or not isinstance(tasks_per_repository, int):
        raise ValueError("tasks_per_repository must be an integer")
    if repository_count < 1 or tasks_per_repository < 1:
        raise ValueError("cohort dimensions must be positive")
    frame_sets = [set(frame) for frame in frames.values()]
    common = set.intersection(*frame_sets)
    if not common:
        raise ValueError("submission frames have no common tasks")
    by_repository: dict[str, list[str]] = defaultdict(list)
    for instance_id in sorted(common):
        by_repository[infer_repository(instance_id)].append(instance_id)
    eligible = [
        (repository, ids)
        for repository, ids in by_repository.items()
        if len(ids) >= tasks_per_repository
    ]
    eligible.sort(key=lambda item: (-len(item[1]), item[0]))
    if len(eligible) < repository_count:
        raise ValueError(
            f"only {len(eligible)} common repositories have at least "
            f"{tasks_per_repository} tasks; requested {repository_count}"
        )
    selected_repositories = eligible[:repository_count]
    selected: list[str] = []
    repository_rows: list[dict[str, Any]] = []
    for repository, ids in selected_repositories:
        ranked = sorted(ids, key=lambda value: (_selection_hash(value, seed), value))
        chosen = sorted(ranked[:tasks_per_repository])
        selected.extend(chosen)
        repository_rows.append(
            {
                "repository": repository,
                "common_task_count": len(ids),
                "selected_instance_ids": chosen,
                "selected_instance_ids_sha256": _sha256("\n".join(chosen).encode()),
            }
        )
    selected.sort()
    common_sorted = sorted(common)
    return {
        "selection_contract": "outcome-blind-common-frame-repository-stratified-v1",
        "selection_seed": seed,
        "repository_count": repository_count,
        "tasks_per_repository": tasks_per_repository,
        "common_instance_count": len(common_sorted),
        "common_instance_ids_sha256": _sha256("\n".join(common_sorted).encode()),
        "repositories": repository_rows,
        "selected_instance_ids": selected,
        "selected_instance_ids_sha256": _sha256("\n".join(selected).encode()),
        "selection_inputs": [
            "submission frame membership",
            "instance identifier",
            "repository identity inferred from instance identifier",
            "fixed selection seed",
        ],
        "excluded_selection_inputs": [
            "patch bytes",
            "trajectory bytes",
            "report bytes",
            "official result categories",
            "hosted resolved labels",
            "reference patches",
            "hidden tests",
        ],
    }


def _validate_pinned_frame_relationship(
    frames: Mapping[str, Sequence[str]],
) -> None:
    """Require the verified 499/500/500 frame relationship for live sources."""

    if set(frames) != {"gpt5", "kimi_k2", "claude_4_sonnet"}:
        raise ValueError("pinned three-submission frame keys drifted")
    gpt_frame = set(frames["gpt5"])
    kimi_frame = set(frames["kimi_k2"])
    claude_frame = set(frames["claude_4_sonnet"])
    if (
        len(gpt_frame) != 499
        or len(kimi_frame) != 500
        or len(claude_frame) != 500
        or kimi_frame != claude_frame
        or not gpt_frame < kimi_frame
        or kimi_frame - gpt_frame != {"django__django-13513"}
    ):
        raise ValueError("pinned three-submission frame relationship drifted")


def _atomic_write_bytes(path: pathlib.Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = pathlib.Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _acquisition_lock(target: pathlib.Path) -> tuple[int, pathlib.Path]:
    lock_path = target.with_name(f".{target.name}.lock")
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return descriptor, lock_path


def _validate_metadata(payload: bytes, spec: SubmissionSpec) -> dict[str, Any]:
    try:
        decoded = yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid source metadata for {spec.key}: {exc}") from exc
    metadata = _object(decoded, f"metadata[{spec.key}]")
    tags = _object(metadata.get("tags"), f"metadata[{spec.key}].tags")
    system = _object(tags.get("system"), f"metadata[{spec.key}].tags.system")
    assets = _object(metadata.get("assets"), f"metadata[{spec.key}].assets")
    if tags.get("checked") is not True:
        raise ValueError(f"submission {spec.key} is not metadata-checked")
    if system.get("attempts") != 1:
        raise ValueError(f"submission {spec.key} is not a single-attempt source")
    expected_logs = f"s3://{BUCKET_NAME}/{spec.root_prefix.removesuffix('/')}"
    expected_trajs = f"s3://{BUCKET_NAME}/verified/{spec.submission_id}/trajs"
    if assets.get("logs") != expected_logs or assets.get("trajs") != expected_trajs:
        raise ValueError(f"submission {spec.key} asset identity drifted")
    return {
        "submission_checked": True,
        "attempts": 1,
        "logs_asset": expected_logs,
        "trajectories_asset": expected_trajs,
    }


def _parse_canonical_dataset_projection(
    payload: bytes,
    *,
    expected_count: int,
) -> tuple[tuple[CanonicalTaskIdentity, ...], dict[str, Any]]:
    """Read only task identity columns; never project gold or oracle content."""

    if not isinstance(payload, bytes) or not payload:
        raise ValueError("canonical dataset parquet must be non-empty bytes")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int):
        raise ValueError("canonical dataset expected_count must be an integer")
    if expected_count < 1:
        raise ValueError("canonical dataset expected_count must be positive")
    try:
        parquet_file = pq.ParquetFile(pa.BufferReader(payload))
    except (pa.ArrowException, OSError, ValueError) as exc:
        raise ValueError(f"invalid canonical dataset parquet: {exc}") from exc
    if tuple(parquet_file.schema_arrow.names) != CANONICAL_DATASET_SCHEMA_FIELDS:
        raise ValueError("canonical dataset parquet schema fields drifted")
    if any(
        not pa.types.is_string(parquet_file.schema_arrow.field(name).type)
        for name in CANONICAL_DATASET_SCHEMA_FIELDS
    ):
        raise ValueError("canonical dataset parquet columns must all be strings")
    if parquet_file.metadata.num_rows != expected_count:
        raise ValueError(
            "canonical dataset row count drifted: "
            f"expected {expected_count}, got {parquet_file.metadata.num_rows}"
        )
    try:
        table = parquet_file.read(columns=list(CANONICAL_DATASET_PROJECTION_FIELDS))
    except (pa.ArrowException, OSError, ValueError) as exc:
        raise ValueError(f"cannot read canonical dataset identity projection: {exc}") from exc
    raw_rows = table.to_pylist()
    if len(raw_rows) != expected_count:
        raise ValueError("canonical dataset projection row count drifted")

    identities: list[CanonicalTaskIdentity] = []
    seen_ids: set[str] = set()
    instances_by_repo_commit: dict[tuple[str, str], list[str]] = defaultdict(list)
    repositories_by_commit: dict[str, set[str]] = defaultdict(set)
    repositories: set[str] = set()
    for index, raw_row in enumerate(raw_rows):
        row = _object(raw_row, f"canonical dataset row {index}")
        _exact_fields(
            row,
            set(CANONICAL_DATASET_PROJECTION_FIELDS),
            f"canonical dataset row {index}",
        )
        instance_id = _string(row["instance_id"], f"dataset[{index}].instance_id")
        if instance_id in seen_ids:
            raise ValueError(f"canonical dataset contains duplicate instance {instance_id}")
        seen_ids.add(instance_id)
        repository = _string(row["repo"], f"dataset[{index}].repo")
        if repository != infer_repository(instance_id):
            raise ValueError(
                f"canonical dataset repository mismatch for {instance_id}: {repository!r}"
            )
        base_commit = _string(row["base_commit"], f"dataset[{index}].base_commit")
        environment_commit = _string(
            row["environment_setup_commit"],
            f"dataset[{index}].environment_setup_commit",
        )
        if _COMMIT_RE.fullmatch(base_commit) is None:
            raise ValueError(
                f"canonical dataset base_commit is not lowercase 40-hex: {instance_id}"
            )
        if _COMMIT_RE.fullmatch(environment_commit) is None:
            raise ValueError(
                f"canonical dataset environment_setup_commit is not lowercase 40-hex: {instance_id}"
            )
        repositories.add(repository)
        instances_by_repo_commit[(repository, base_commit)].append(instance_id)
        repositories_by_commit[base_commit].add(repository)
        identities.append(
            CanonicalTaskIdentity(
                instance_id=instance_id,
                repository=repository,
                base_commit=base_commit,
                environment_setup_commit=environment_commit,
            )
        )
    identities.sort(key=lambda item: item.instance_id)
    cross_repository_collisions = [
        {"base_commit": commit, "repositories": sorted(commit_repositories)}
        for commit, commit_repositories in sorted(repositories_by_commit.items())
        if len(commit_repositories) > 1
    ]
    if cross_repository_collisions:
        raise ValueError(
            "canonical dataset reuses a base commit across repositories: "
            f"{cross_repository_collisions}"
        )
    duplicate_pairs = [
        {
            "repository": repository,
            "base_commit": commit,
            "instance_ids": sorted(instance_ids),
        }
        for (repository, commit), instance_ids in sorted(instances_by_repo_commit.items())
        if len(instance_ids) > 1
    ]
    projection_payload = (
        strict_json_dumps([identity.to_dict() for identity in identities], indent=2) + "\n"
    ).encode()
    summary = {
        "projection_contract": "instance-repo-base-environment-commit-v1",
        "projection_fields": list(CANONICAL_DATASET_PROJECTION_FIELDS),
        "projection_row_count": len(identities),
        "projection_bytes": len(projection_payload),
        "projection_sha256": _sha256(projection_payload),
        "unique_instance_count": len(seen_ids),
        "repository_count": len(repositories),
        "unique_repository_base_commit_pair_count": len(instances_by_repo_commit),
        "duplicate_repository_base_commit_pairs": duplicate_pairs,
        "cross_repository_base_commit_collision_count": 0,
    }
    return tuple(identities), summary


def _validate_pinned_canonical_dataset(
    payload: bytes,
) -> tuple[tuple[CanonicalTaskIdentity, ...], dict[str, Any]]:
    if len(payload) != CANONICAL_DATASET_BYTES or _sha256(payload) != (CANONICAL_DATASET_SHA256):
        raise ValueError("pinned canonical SWE-bench Verified parquet bytes drifted")
    identities, projection = _parse_canonical_dataset_projection(
        payload,
        expected_count=CANONICAL_DATASET_EXPECTED_COUNT,
    )
    if (
        projection["projection_bytes"] != CANONICAL_DATASET_PROJECTION_BYTES
        or projection["projection_sha256"] != CANONICAL_DATASET_PROJECTION_SHA256
        or projection["repository_count"] != 12
        or projection["unique_repository_base_commit_pair_count"] != 499
        or projection["cross_repository_base_commit_collision_count"] != 0
        or projection["duplicate_repository_base_commit_pairs"]
        != [
            {
                "repository": "django/django",
                "base_commit": CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT,
                "instance_ids": ["django__django-15268", "django__django-15278"],
            }
        ]
    ):
        raise ValueError("pinned canonical dataset identity projection drifted")
    return identities, projection


def _crosscheck_canonical_dataset_frames(
    identities: Sequence[CanonicalTaskIdentity],
    frames: Mapping[str, Sequence[str]],
    selected_instance_ids: Sequence[str],
) -> dict[str, Any]:
    dataset_by_id = {identity.instance_id: identity for identity in identities}
    if len(dataset_by_id) != len(identities):
        raise ValueError("canonical dataset task identities are duplicate")
    dataset_ids = set(dataset_by_id)
    frame_sets = {key: set(values) for key, values in frames.items()}
    if set(frame_sets) != {spec.key for spec in SUBMISSIONS}:
        raise ValueError("canonical frame cross-check requires the pinned submissions")
    if frame_sets["kimi_k2"] != dataset_ids or frame_sets["claude_4_sonnet"] != dataset_ids:
        raise ValueError("full submission frames do not exactly match the canonical dataset")
    expected_gpt5 = dataset_ids - {"django__django-13513"}
    if frame_sets["gpt5"] != expected_gpt5:
        raise ValueError("GPT-5 frame does not match the canonical dataset subset")
    common = set.intersection(*frame_sets.values())
    selected = set(selected_instance_ids)
    if not selected or not selected <= common:
        raise ValueError("selected cohort is not a non-empty canonical common-frame subset")
    selected_rows = [dataset_by_id[instance_id].to_dict() for instance_id in sorted(selected)]
    selected_payload = (strict_json_dumps(selected_rows, indent=2) + "\n").encode()
    return {
        "status": "exact_pinned_frame_match",
        "canonical_dataset_instance_count": len(dataset_ids),
        "gpt5_frame_count": len(frame_sets["gpt5"]),
        "kimi_k2_frame_count": len(frame_sets["kimi_k2"]),
        "claude_4_sonnet_frame_count": len(frame_sets["claude_4_sonnet"]),
        "common_frame_count": len(common),
        "selected_task_count": len(selected_rows),
        "selected_task_identities_sha256": _sha256(selected_payload),
        "base_commit_valid_count": len(dataset_ids),
        "environment_setup_commit_valid_count": len(dataset_ids),
    }


def _canonical_dataset_record(
    payload: bytes,
    downloaded: DownloadedObject,
    identities: Sequence[CanonicalTaskIdentity],
    projection: Mapping[str, Any],
    frame_crosscheck: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "provider": "Hugging Face",
        "dataset_id": CANONICAL_DATASET_ID,
        "revision": CANONICAL_DATASET_REVISION,
        "split": "test",
        "authoritative_url": CANONICAL_DATASET_AUTHORITATIVE_URL,
        "retrieval_transport": {
            "kind": "immutable_plain_git_mirror",
            "mirror_revision": CANONICAL_DATASET_MIRROR_REVISION,
            "source_url": CANONICAL_DATASET_RETRIEVAL_URL,
            "response_url": downloaded.final_url,
        },
        "relative_path": f"sources/{CANONICAL_DATASET_LOCAL_NAME}",
        "bytes": len(payload),
        "sha256": _sha256(payload),
        "projection": dict(projection),
        "frame_crosscheck": dict(frame_crosscheck),
        "task_identities": [identity.to_dict() for identity in identities],
        "excluded_privileged_columns": [
            "patch",
            "test_patch",
            "problem_statement",
            "hints_text",
            "FAIL_TO_PASS",
            "PASS_TO_PASS",
        ],
    }


def _file_record(
    *,
    relative_path: str,
    source_url: str,
    downloaded: DownloadedObject,
) -> dict[str, Any]:
    return {
        "relative_path": relative_path,
        "source_url": source_url,
        "response_url": downloaded.final_url,
        "bytes": len(downloaded.payload),
        "sha256": _sha256(downloaded.payload),
    }


def acquire_corpus(
    artifact_root: pathlib.Path,
    *,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
    repository_count: int = DEFAULT_REPOSITORY_COUNT,
    tasks_per_repository: int = DEFAULT_TASKS_PER_REPOSITORY,
    selection_seed: int = DEFAULT_SELECTION_SEED,
    workers: int = DEFAULT_WORKERS,
    retries: int = DEFAULT_RETRIES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    maximum_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    fetch_once: FetchOnce = _fetch_once,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Acquire one immutable matched cohort without decoding hosted outcomes."""

    spec_map = _submission_map(specs)
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 16:
        raise ValueError("workers must be an integer between 1 and 16")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError("timeout_seconds must be in (0, 120]")
    if (
        isinstance(selection_seed, bool)
        or not isinstance(selection_seed, int)
        or selection_seed < 0
    ):
        raise ValueError("selection_seed must be a non-negative integer")
    artifact_root = artifact_root.absolute()
    artifact_root.parent.mkdir(parents=True, exist_ok=True)
    if artifact_root.exists() or artifact_root.is_symlink():
        raise FileExistsError(
            f"acquisition target already exists; choose a new path: {artifact_root}"
        )
    lock_descriptor: int | None = None
    lock_path: pathlib.Path | None = None
    staging: pathlib.Path | None = None
    budget = DownloadBudget(maximum_total_bytes)
    try:
        lock_descriptor, lock_path = _acquisition_lock(artifact_root)
        staging = pathlib.Path(
            tempfile.mkdtemp(
                prefix=f".{artifact_root.name}.staging.",
                dir=artifact_root.parent,
            )
        )
        study_code_payload = _study_code_payload()
        study_code_relative = "sources/study-code.py"
        _atomic_write_bytes(staging / study_code_relative, study_code_payload)
        study_code_record = {
            **_study_code_identity(study_code_payload),
            "relative_path": study_code_relative,
        }
        source_rows: list[dict[str, Any]] = []
        frames: dict[str, tuple[str, ...]] = {}
        for spec in specs:
            source_payloads: dict[str, DownloadedObject] = {}
            for name, url, maximum in (
                ("metadata.yaml", spec.metadata_url, MAX_SOURCE_BYTES),
                ("results.json", spec.results_url, MAX_SOURCE_BYTES),
                ("frame-listing.xml", _frame_listing_url(spec), MAX_LISTING_BYTES),
            ):
                downloaded = _fetch_with_retries(
                    url,
                    maximum_bytes=maximum,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    budget=budget,
                    fetch_once=fetch_once,
                    specs=specs,
                    sleep=sleep,
                )
                if not downloaded.payload:
                    raise ValueError(f"empty required source {spec.key}/{name}")
                if name == "metadata.yaml" and (
                    len(downloaded.payload) != spec.metadata_bytes
                    or _sha256(downloaded.payload) != spec.metadata_sha256
                ):
                    raise ValueError(f"pinned metadata bytes drifted for {spec.key}")
                if name == "results.json" and (
                    len(downloaded.payload) != spec.results_bytes
                    or _sha256(downloaded.payload) != spec.results_sha256
                ):
                    raise ValueError(f"pinned results bytes drifted for {spec.key}")
                source_payloads[name] = downloaded
                relative = f"sources/{spec.key}/{name}"
                _atomic_write_bytes(staging / relative, downloaded.payload)
            semantics = _validate_metadata(source_payloads["metadata.yaml"].payload, spec)
            frames[spec.key] = enumerate_instance_ids(
                source_payloads["frame-listing.xml"].payload,
                spec=spec,
            )
            source_rows.append(
                {
                    "submission_key": spec.key,
                    "model_label": spec.model_label,
                    "submission_id": spec.submission_id,
                    "expected_instance_count": spec.expected_instance_count,
                    "root_prefix": spec.root_prefix,
                    "metadata_semantics": semantics,
                    "files": [
                        _file_record(
                            relative_path=f"sources/{spec.key}/{name}",
                            source_url=(
                                spec.metadata_url
                                if name == "metadata.yaml"
                                else spec.results_url
                                if name == "results.json"
                                else _frame_listing_url(spec)
                            ),
                            downloaded=source_payloads[name],
                        )
                        for name in ("metadata.yaml", "results.json", "frame-listing.xml")
                    ],
                }
            )

        cohort = freeze_common_cohort(
            frames,
            repository_count=repository_count,
            tasks_per_repository=tasks_per_repository,
            seed=selection_seed,
        )
        if tuple(specs) == SUBMISSIONS:
            if cohort["common_instance_count"] != 499:
                raise ValueError("pinned three-submission common frame must contain 499 tasks")
            _validate_pinned_frame_relationship(frames)
        canonical_dataset: dict[str, Any] | None = None
        if tuple(specs) == SUBMISSIONS:
            canonical_download = _fetch_with_retries(
                CANONICAL_DATASET_RETRIEVAL_URL,
                maximum_bytes=CANONICAL_DATASET_BYTES,
                timeout_seconds=timeout_seconds,
                retries=retries,
                budget=budget,
                fetch_once=fetch_once,
                specs=specs,
                sleep=sleep,
            )
            identities, projection = _validate_pinned_canonical_dataset(canonical_download.payload)
            frame_crosscheck = _crosscheck_canonical_dataset_frames(
                identities,
                frames,
                cohort["selected_instance_ids"],
            )
            canonical_relative = f"sources/{CANONICAL_DATASET_LOCAL_NAME}"
            _atomic_write_bytes(
                staging / canonical_relative,
                canonical_download.payload,
            )
            canonical_dataset = _canonical_dataset_record(
                canonical_download.payload,
                canonical_download,
                identities,
                projection,
                frame_crosscheck,
            )
        jobs = [
            (instance_id, spec, name)
            for instance_id in cohort["selected_instance_ids"]
            for spec in specs
            for name in ARTIFACT_NAMES
        ]

        def fetch_artifact(
            job: tuple[str, SubmissionSpec, str],
        ) -> tuple[tuple[str, SubmissionSpec, str], DownloadedObject | None, str | None]:
            instance_id, spec, name = job
            url = _artifact_url(spec, instance_id, name)
            try:
                downloaded = _fetch_with_retries(
                    url,
                    maximum_bytes=MAX_ARTIFACT_BYTES[name],
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    budget=budget,
                    fetch_once=fetch_once,
                    specs=specs,
                    sleep=sleep,
                )
            except UnavailableFetchError:
                return job, None, "source_unavailable"
            return job, downloaded, None

        fetched: dict[
            tuple[str, str, str],
            tuple[DownloadedObject | None, str | None],
        ] = {}
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(fetch_artifact, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    returned_job, artifact_download, error_code = future.result()
                except Exception as exc:
                    failures.append(f"{job[0]}/{job[1].key}/{job[2]}: {type(exc).__name__}: {exc}")
                    continue
                instance_id, spec, name = returned_job
                fetched[(instance_id, spec.key, name)] = (
                    artifact_download,
                    error_code,
                )
        if failures:
            raise RuntimeError("artifact acquisition failed: " + "; ".join(sorted(failures)))

        artifact_rows: list[dict[str, Any]] = []
        for instance_id, spec, name in jobs:
            artifact_download, error_code = fetched[(instance_id, spec.key, name)]
            source_url = _artifact_url(spec, instance_id, name)
            relative = f"artifacts/{instance_id}/{spec.key}/{name}"
            if artifact_download is None:
                artifact_rows.append(
                    {
                        "instance_id": instance_id,
                        "repository": infer_repository(instance_id),
                        "submission_key": spec.key,
                        "name": name,
                        "source_url": source_url,
                        "availability": "unavailable",
                        "relative_path": None,
                        "response_url": None,
                        "bytes": None,
                        "sha256": None,
                        "error_code": error_code,
                    }
                )
                continue
            _atomic_write_bytes(staging / relative, artifact_download.payload)
            artifact_rows.append(
                {
                    "instance_id": instance_id,
                    "repository": infer_repository(instance_id),
                    "submission_key": spec.key,
                    "name": name,
                    "source_url": source_url,
                    "availability": "downloaded",
                    "relative_path": relative,
                    "response_url": artifact_download.final_url,
                    "bytes": len(artifact_download.payload),
                    "sha256": _sha256(artifact_download.payload),
                    "error_code": None,
                }
            )
        artifact_rows.sort(key=lambda row: (row["instance_id"], row["submission_key"], row["name"]))
        manifest = {
            "schema_version": ACQUISITION_SCHEMA_VERSION,
            "study_id": STUDY_ID,
            "source_repository": "SWE-bench/experiments",
            "source_revision": SOURCE_REVISION,
            "study_code": study_code_record,
            "canonical_dataset": canonical_dataset,
            "phase_contract": ("cohort_and_artifact_identities_frozen_before_any_outcome_decode"),
            "submissions": source_rows,
            "cohort": cohort,
            "artifacts": artifact_rows,
            "totals": {
                "submission_count": len(spec_map),
                "task_count": len(cohort["selected_instance_ids"]),
                "candidate_count": len(cohort["selected_instance_ids"]) * len(spec_map),
                "artifact_record_count": len(artifact_rows),
                "downloaded_artifact_count": sum(
                    row["availability"] == "downloaded" for row in artifact_rows
                ),
                "unavailable_artifact_count": sum(
                    row["availability"] == "unavailable" for row in artifact_rows
                ),
                "downloaded_bytes_including_sources": budget.used,
            },
        }
        atomic_write(
            staging / "acquisition-manifest.json",
            strict_json_dumps(manifest, indent=2) + "\n",
        )
        os.replace(staging, artifact_root)
        staging = None
        if os.name != "nt":
            descriptor = os.open(artifact_root.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return manifest
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if lock_path is not None:
            lock_path.unlink(missing_ok=True)


def _load_acquisition_manifest(artifact_root: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    path = artifact_root / "acquisition-manifest.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError("acquisition manifest must be a regular non-symlink file")
    payload = path.read_bytes()
    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid acquisition manifest JSON: {exc}") from exc
    return _object(decoded, "acquisition manifest"), payload


def _safe_declared_file(root: pathlib.Path, relative: str) -> pathlib.Path:
    if (
        not isinstance(relative, str)
        or not relative
        or pathlib.PurePosixPath(relative).is_absolute()
    ):
        raise ValueError("declared file path must be non-empty and relative")
    pure = pathlib.PurePosixPath(relative)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"declared file path is unconfined: {relative!r}")
    path = root.joinpath(*pure.parts)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"declared file is absent or not regular: {relative!r}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"declared file escaped the acquisition root: {relative!r}") from exc
    return path


def _verify_file_identity(
    root: pathlib.Path,
    record: Mapping[str, Any],
    *,
    field: str,
) -> str:
    expected = {
        "relative_path",
        "source_url",
        "response_url",
        "bytes",
        "sha256",
    }
    _exact_fields(record, expected, field)
    relative = _string(record["relative_path"], f"{field}.relative_path")
    _string(record["source_url"], f"{field}.source_url")
    _string(record["response_url"], f"{field}.response_url")
    byte_count = _integer(record["bytes"], f"{field}.bytes")
    digest = _string(record["sha256"], f"{field}.sha256")
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    payload = _safe_declared_file(root, relative).read_bytes()
    if len(payload) != byte_count or _sha256(payload) != digest:
        raise ValueError(f"declared file identity drifted: {relative}")
    return relative


def _verify_study_code_record(
    root: pathlib.Path,
    value: Any,
) -> tuple[dict[str, Any], str]:
    record = _object(value, "acquisition.study_code")
    _exact_fields(
        record,
        {"logical_path", "relative_path", "bytes", "sha256"},
        "acquisition.study_code",
    )
    if record["logical_path"] != STUDY_CODE_LOGICAL_PATH:
        raise ValueError("acquisition study-code logical path drifted")
    relative = _string(record["relative_path"], "acquisition.study_code.relative_path")
    byte_count = _integer(record["bytes"], "acquisition.study_code.bytes")
    digest = _string(record["sha256"], "acquisition.study_code.sha256")
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError("acquisition study-code digest must be lowercase SHA-256")
    payload = _safe_declared_file(root, relative).read_bytes()
    if len(payload) != byte_count or _sha256(payload) != digest:
        raise ValueError("preserved acquisition study-code identity drifted")
    return {
        "logical_path": STUDY_CODE_LOGICAL_PATH,
        "bytes": byte_count,
        "sha256": digest,
    }, relative


def validate_acquisition(
    artifact_root: pathlib.Path,
    *,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
) -> tuple[dict[str, Any], bytes]:
    """Fail closed over the acquired tree without decoding outcome content."""

    spec_map = _submission_map(specs)
    artifact_root = artifact_root.absolute()
    if artifact_root.is_symlink() or not artifact_root.is_dir():
        raise ValueError("acquisition root must be a regular directory")
    manifest, manifest_payload = _load_acquisition_manifest(artifact_root)
    _exact_fields(
        manifest,
        {
            "schema_version",
            "study_id",
            "source_repository",
            "source_revision",
            "study_code",
            "canonical_dataset",
            "phase_contract",
            "submissions",
            "cohort",
            "artifacts",
            "totals",
        },
        "acquisition manifest",
    )
    if manifest["schema_version"] != ACQUISITION_SCHEMA_VERSION:
        raise ValueError("unsupported acquisition schema")
    if manifest["study_id"] != STUDY_ID or manifest["source_revision"] != SOURCE_REVISION:
        raise ValueError("acquisition study/source identity drifted")
    if manifest["source_repository"] != "SWE-bench/experiments":
        raise ValueError("acquisition source repository drifted")
    if manifest["phase_contract"] != (
        "cohort_and_artifact_identities_frozen_before_any_outcome_decode"
    ):
        raise ValueError("acquisition phase contract drifted")

    declared_files = {"acquisition-manifest.json"}
    _, study_code_relative = _verify_study_code_record(
        artifact_root,
        manifest["study_code"],
    )
    declared_files.add(study_code_relative)
    submission_rows = _array(manifest["submissions"], "acquisition.submissions")
    if len(submission_rows) != len(spec_map):
        raise ValueError("acquisition submission count drifted")
    seen_submission_keys: set[str] = set()
    validated_frames: dict[str, tuple[str, ...]] = {}
    for index, raw_row in enumerate(submission_rows):
        field = f"acquisition.submissions[{index}]"
        row = _object(raw_row, field)
        _exact_fields(
            row,
            {
                "submission_key",
                "model_label",
                "submission_id",
                "expected_instance_count",
                "root_prefix",
                "metadata_semantics",
                "files",
            },
            field,
        )
        key = _string(row["submission_key"], f"{field}.submission_key")
        if key in seen_submission_keys or key not in spec_map:
            raise ValueError("acquisition contains a duplicate or unknown submission")
        seen_submission_keys.add(key)
        spec = spec_map[key]
        if (
            row["model_label"] != spec.model_label
            or row["submission_id"] != spec.submission_id
            or row["expected_instance_count"] != spec.expected_instance_count
            or row["root_prefix"] != spec.root_prefix
        ):
            raise ValueError(f"submission identity drifted for {key}")
        semantics = _object(row["metadata_semantics"], f"{field}.metadata_semantics")
        if semantics.get("submission_checked") is not True or semantics.get("attempts") != 1:
            raise ValueError(f"checked/single-attempt semantics drifted for {key}")
        files = _array(row["files"], f"{field}.files")
        if len(files) != 3:
            raise ValueError(f"source file set is incomplete for {key}")
        source_by_name: dict[str, Mapping[str, Any]] = {}
        for file_index, raw_file in enumerate(files):
            file_record = _object(raw_file, f"{field}.files[{file_index}]")
            relative = _verify_file_identity(
                artifact_root,
                file_record,
                field=f"{field}.files[{file_index}]",
            )
            _validate_fetch_url(str(file_record["source_url"]), specs=specs)
            _validate_fetch_url(str(file_record["response_url"]), specs=specs)
            declared_files.add(relative)
            source_by_name[pathlib.PurePosixPath(relative).name] = file_record
        if set(source_by_name) != {"metadata.yaml", "results.json", "frame-listing.xml"}:
            raise ValueError(f"source file names drifted for {key}")
        metadata = source_by_name["metadata.yaml"]
        results = source_by_name["results.json"]
        if (
            metadata["source_url"] != spec.metadata_url
            or metadata["bytes"] != spec.metadata_bytes
            or metadata["sha256"] != spec.metadata_sha256
            or results["source_url"] != spec.results_url
            or results["bytes"] != spec.results_bytes
            or results["sha256"] != spec.results_sha256
        ):
            raise ValueError(f"pinned Git source identity drifted for {key}")
        listing = source_by_name["frame-listing.xml"]
        if listing["source_url"] != _frame_listing_url(spec):
            raise ValueError(f"frame listing URL drifted for {key}")
        listing_payload = _safe_declared_file(
            artifact_root,
            str(listing["relative_path"]),
        ).read_bytes()
        validated_frames[key] = enumerate_instance_ids(listing_payload, spec=spec)
    if seen_submission_keys != set(spec_map):
        raise ValueError("acquisition submission set is incomplete")
    if tuple(specs) == SUBMISSIONS:
        _validate_pinned_frame_relationship(validated_frames)

    cohort = _object(manifest["cohort"], "acquisition.cohort")
    _exact_fields(
        cohort,
        {
            "selection_contract",
            "selection_seed",
            "repository_count",
            "tasks_per_repository",
            "common_instance_count",
            "common_instance_ids_sha256",
            "repositories",
            "selected_instance_ids",
            "selected_instance_ids_sha256",
            "selection_inputs",
            "excluded_selection_inputs",
        },
        "acquisition.cohort",
    )
    rederived_cohort = freeze_common_cohort(
        validated_frames,
        repository_count=_integer(
            cohort["repository_count"],
            "acquisition.cohort.repository_count",
        ),
        tasks_per_repository=_integer(
            cohort["tasks_per_repository"],
            "acquisition.cohort.tasks_per_repository",
        ),
        seed=_integer(cohort["selection_seed"], "acquisition.cohort.selection_seed"),
    )
    if cohort != rederived_cohort:
        raise ValueError("frozen cohort cannot be rederived from the raw source frames")
    selected_values = _array(
        cohort.get("selected_instance_ids"),
        "acquisition.cohort.selected_instance_ids",
    )
    if any(not isinstance(value, str) for value in selected_values):
        raise ValueError("selected cohort must contain instance IDs")
    selected = [str(value) for value in selected_values]
    if not selected or selected != sorted(selected) or len(selected) != len(set(selected)):
        raise ValueError("selected cohort is empty, duplicate, or non-canonical")
    for instance_id in selected:
        infer_repository(instance_id)
    if cohort.get("selected_instance_ids_sha256") != _sha256("\n".join(selected).encode()):
        raise ValueError("selected cohort digest drifted")

    canonical_dataset_bytes = 0
    canonical_value = manifest["canonical_dataset"]
    if tuple(specs) == SUBMISSIONS:
        canonical = _object(canonical_value, "acquisition.canonical_dataset")
        relative = _string(
            canonical.get("relative_path"),
            "acquisition.canonical_dataset.relative_path",
        )
        if relative != f"sources/{CANONICAL_DATASET_LOCAL_NAME}":
            raise ValueError("canonical dataset local identity drifted")
        payload = _safe_declared_file(artifact_root, relative).read_bytes()
        identities, projection = _validate_pinned_canonical_dataset(payload)
        frame_crosscheck = _crosscheck_canonical_dataset_frames(
            identities,
            validated_frames,
            selected,
        )
        retrieval = _object(
            canonical.get("retrieval_transport"),
            "acquisition.canonical_dataset.retrieval_transport",
        )
        response_url = _string(
            retrieval.get("response_url"),
            "acquisition.canonical_dataset.retrieval_transport.response_url",
        )
        _validate_fetch_url(response_url, specs=specs)
        expected_canonical = _canonical_dataset_record(
            payload,
            DownloadedObject(payload=payload, final_url=response_url),
            identities,
            projection,
            frame_crosscheck,
        )
        if canonical != expected_canonical:
            raise ValueError("canonical dataset manifest identity or frame cross-check drifted")
        declared_files.add(relative)
        canonical_dataset_bytes = len(payload)
    elif canonical_value is not None:
        raise ValueError("non-production fixture cannot claim canonical dataset evidence")

    artifact_rows = _array(manifest["artifacts"], "acquisition.artifacts")
    expected_keys = {
        (instance_id, key, name)
        for instance_id in selected
        for key in spec_map
        for name in ARTIFACT_NAMES
    }
    seen_keys: set[tuple[str, str, str]] = set()
    for index, raw_row in enumerate(artifact_rows):
        field = f"acquisition.artifacts[{index}]"
        row = _object(raw_row, field)
        _exact_fields(
            row,
            {
                "instance_id",
                "repository",
                "submission_key",
                "name",
                "source_url",
                "availability",
                "relative_path",
                "response_url",
                "bytes",
                "sha256",
                "error_code",
            },
            field,
        )
        instance_id = _string(row["instance_id"], f"{field}.instance_id")
        key = _string(row["submission_key"], f"{field}.submission_key")
        name = _string(row["name"], f"{field}.name")
        record_key = (instance_id, key, name)
        if record_key not in expected_keys or record_key in seen_keys:
            raise ValueError("artifact record is duplicate or outside the frozen cohort")
        seen_keys.add(record_key)
        if row["repository"] != infer_repository(instance_id):
            raise ValueError("artifact repository identity drifted")
        if row["source_url"] != _artifact_url(spec_map[key], instance_id, name):
            raise ValueError("artifact source URL drifted")
        _validate_fetch_url(str(row["source_url"]), specs=specs)
        availability = row["availability"]
        if availability == "downloaded":
            if row["error_code"] is not None:
                raise ValueError("downloaded artifact cannot carry an error code")
            file_record = {
                "relative_path": row["relative_path"],
                "source_url": row["source_url"],
                "response_url": row["response_url"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
            declared_files.add(_verify_file_identity(artifact_root, file_record, field=field))
            _validate_fetch_url(str(row["response_url"]), specs=specs)
        elif availability == "unavailable":
            if (
                any(
                    row[field_name] is not None
                    for field_name in ("relative_path", "response_url", "bytes", "sha256")
                )
                or row["error_code"] != "source_unavailable"
            ):
                raise ValueError("unavailable artifact record is malformed")
        else:
            raise ValueError("artifact availability must be downloaded or unavailable")
    if seen_keys != expected_keys:
        raise ValueError("artifact record set is incomplete")

    totals = _object(manifest["totals"], "acquisition.totals")
    _exact_fields(
        totals,
        {
            "submission_count",
            "task_count",
            "candidate_count",
            "artifact_record_count",
            "downloaded_artifact_count",
            "unavailable_artifact_count",
            "downloaded_bytes_including_sources",
        },
        "acquisition.totals",
    )
    downloaded_rows = [row for row in artifact_rows if row["availability"] == "downloaded"]
    source_bytes = sum(
        int(file_record["bytes"])
        for submission in submission_rows
        for file_record in submission["files"]
    )
    expected_totals = {
        "submission_count": len(spec_map),
        "task_count": len(selected),
        "candidate_count": len(selected) * len(spec_map),
        "artifact_record_count": len(artifact_rows),
        "downloaded_artifact_count": len(downloaded_rows),
        "unavailable_artifact_count": len(artifact_rows) - len(downloaded_rows),
        "downloaded_bytes_including_sources": source_bytes
        + canonical_dataset_bytes
        + sum(int(row["bytes"]) for row in downloaded_rows),
    }
    if totals != expected_totals:
        raise ValueError("acquisition totals contradict declared source/artifact records")

    actual_files: set[str] = set()
    for path in artifact_root.rglob("*"):
        if path.is_symlink():
            raise ValueError("acquisition tree cannot contain symlinks")
        if path.is_file():
            actual_files.add(path.relative_to(artifact_root).as_posix())
    if actual_files != declared_files:
        raise ValueError(
            "acquisition tree contains missing or undeclared files: "
            f"missing={sorted(declared_files - actual_files)}, "
            f"undeclared={sorted(actual_files - declared_files)}"
        )
    return manifest, manifest_payload


def _artifact_index(manifest: Mapping[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_row in manifest["artifacts"]:
        row = _object(raw_row, "artifact record")
        result[(row["instance_id"], row["submission_key"], row["name"])] = row
    return result


def sanitize_feature_inputs(
    manifest: Mapping[str, Any],
    *,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
) -> FeatureBuildInput:
    """Project a validated acquisition onto a closed, outcome-free interface."""

    spec_map = _submission_map(specs)
    cohort = _object(manifest.get("cohort"), "acquisition.cohort")
    selected_values = _array(
        cohort.get("selected_instance_ids"),
        "acquisition.cohort.selected_instance_ids",
    )
    if any(not isinstance(value, str) for value in selected_values):
        raise ValueError("sanitized feature cohort must contain instance IDs")
    selected = tuple(str(value) for value in selected_values)
    if not selected or tuple(sorted(selected)) != selected or len(selected) != len(set(selected)):
        raise ValueError("sanitized feature cohort is empty, duplicate, or non-canonical")
    selected_digest = _string(
        cohort.get("selected_instance_ids_sha256"),
        "acquisition.cohort.selected_instance_ids_sha256",
    )
    if selected_digest != _sha256("\n".join(selected).encode()):
        raise ValueError("sanitized feature cohort digest drifted")

    expected_artifacts = {
        (instance_id, key, name)
        for instance_id in selected
        for key in spec_map
        for name in ("patch.diff", "trajectory.json")
    }
    artifacts: list[FeatureArtifactIdentity] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_record in _array(manifest.get("artifacts"), "acquisition.artifacts"):
        record = _object(raw_record, "acquisition artifact")
        artifact_key = (
            str(record.get("instance_id")),
            str(record.get("submission_key")),
            str(record.get("name")),
        )
        if artifact_key not in expected_artifacts:
            continue
        if artifact_key in seen:
            raise ValueError("sanitized feature artifact is duplicate")
        seen.add(artifact_key)
        instance_id, submission_key, name = artifact_key
        repository = _string(record.get("repository"), "artifact.repository")
        if repository != infer_repository(instance_id):
            raise ValueError("sanitized feature artifact repository drifted")
        availability = _string(record.get("availability"), "artifact.availability")
        if availability == "downloaded":
            relative_path: str | None = _string(
                record.get("relative_path"),
                "artifact.relative_path",
            )
            byte_count: int | None = _integer(record.get("bytes"), "artifact.bytes")
            digest_value = _string(record.get("sha256"), "artifact.sha256")
            digest: str | None = digest_value
            if not _SHA256_RE.fullmatch(digest_value):
                raise ValueError("sanitized feature artifact digest is not SHA-256")
            error_code: str | None = None
            if record.get("error_code") is not None:
                raise ValueError("downloaded sanitized feature artifact has an error")
        elif availability == "unavailable":
            if any(record.get(field) is not None for field in ("relative_path", "bytes", "sha256")):
                raise ValueError("unavailable sanitized feature artifact carries identity")
            relative_path = None
            byte_count = None
            digest = None
            error_code = _string(record.get("error_code"), "artifact.error_code")
        else:
            raise ValueError("sanitized feature artifact availability is invalid")
        artifacts.append(
            FeatureArtifactIdentity(
                instance_id=instance_id,
                repository=repository,
                submission_key=submission_key,
                name=name,
                availability=availability,
                relative_path=relative_path,
                byte_count=byte_count,
                sha256=digest,
                error_code=error_code,
            )
        )
    if seen != expected_artifacts:
        raise ValueError("sanitized feature artifact set is incomplete")
    artifacts.sort(key=lambda item: (item.instance_id, item.submission_key, item.name))

    canonical_task_identities: tuple[CanonicalTaskIdentity, ...] = ()
    canonical_dataset_identity: dict[str, Any] | None = None
    canonical_value = manifest.get("canonical_dataset")
    if canonical_value is not None:
        canonical = _object(canonical_value, "acquisition.canonical_dataset")
        raw_identities = _array(
            canonical.get("task_identities"),
            "acquisition.canonical_dataset.task_identities",
        )
        by_id: dict[str, CanonicalTaskIdentity] = {}
        for index, raw_identity in enumerate(raw_identities):
            identity_record = _object(raw_identity, f"canonical task identity {index}")
            _exact_fields(
                identity_record,
                set(CANONICAL_DATASET_PROJECTION_FIELDS),
                f"canonical task identity {index}",
            )
            task = CanonicalTaskIdentity(
                instance_id=_string(identity_record["instance_id"], "canonical.instance_id"),
                repository=_string(identity_record["repo"], "canonical.repo"),
                base_commit=_string(identity_record["base_commit"], "canonical.base_commit"),
                environment_setup_commit=_string(
                    identity_record["environment_setup_commit"],
                    "canonical.environment_setup_commit",
                ),
            )
            if (
                task.instance_id in by_id
                or task.repository != infer_repository(task.instance_id)
                or _COMMIT_RE.fullmatch(task.base_commit) is None
                or _COMMIT_RE.fullmatch(task.environment_setup_commit) is None
            ):
                raise ValueError("canonical task identity is duplicate or malformed")
            by_id[task.instance_id] = task
        if not set(selected) <= set(by_id):
            raise ValueError("canonical task identities do not cover the selected cohort")
        canonical_task_identities = tuple(by_id[instance_id] for instance_id in selected)
        projection = _object(canonical.get("projection"), "canonical.projection")
        crosscheck = _object(canonical.get("frame_crosscheck"), "canonical.frame_crosscheck")
        canonical_dataset_identity = {
            "dataset_id": _string(canonical.get("dataset_id"), "canonical.dataset_id"),
            "revision": _string(canonical.get("revision"), "canonical.revision"),
            "bytes": _integer(canonical.get("bytes"), "canonical.bytes"),
            "sha256": _string(canonical.get("sha256"), "canonical.sha256"),
            "identity_projection_sha256": _string(
                projection.get("projection_sha256"),
                "canonical.projection.projection_sha256",
            ),
            "selected_task_identities_sha256": _string(
                crosscheck.get("selected_task_identities_sha256"),
                "canonical.frame_crosscheck.selected_task_identities_sha256",
            ),
        }
        if (
            canonical_dataset_identity["dataset_id"] != CANONICAL_DATASET_ID
            or canonical_dataset_identity["revision"] != CANONICAL_DATASET_REVISION
            or canonical_dataset_identity["bytes"] != CANONICAL_DATASET_BYTES
            or canonical_dataset_identity["sha256"] != CANONICAL_DATASET_SHA256
            or canonical_dataset_identity["identity_projection_sha256"]
            != CANONICAL_DATASET_PROJECTION_SHA256
            or not _SHA256_RE.fullmatch(
                str(canonical_dataset_identity["selected_task_identities_sha256"])
            )
        ):
            raise ValueError("sanitized canonical dataset identity drifted")

    code = _object(manifest.get("study_code"), "acquisition.study_code")
    acquisition_code_identity = {
        "logical_path": _string(code.get("logical_path"), "study_code.logical_path"),
        "bytes": _integer(code.get("bytes"), "study_code.bytes"),
        "sha256": _string(code.get("sha256"), "study_code.sha256"),
    }
    if acquisition_code_identity[
        "logical_path"
    ] != STUDY_CODE_LOGICAL_PATH or not _SHA256_RE.fullmatch(
        str(acquisition_code_identity["sha256"])
    ):
        raise ValueError("acquisition study-code identity is malformed")
    return FeatureBuildInput(
        selected_instance_ids=selected,
        selected_instance_ids_sha256=selected_digest,
        submission_keys=tuple(spec_map),
        artifacts=tuple(artifacts),
        canonical_task_identities=canonical_task_identities,
        canonical_dataset_identity=canonical_dataset_identity,
        acquisition_code_identity=acquisition_code_identity,
    )


def _feature_artifact_index(
    feature_input: FeatureBuildInput,
) -> dict[tuple[str, str, str], FeatureArtifactIdentity]:
    if not isinstance(feature_input, FeatureBuildInput):
        raise TypeError("feature construction requires a sanitized FeatureBuildInput")
    result: dict[tuple[str, str, str], FeatureArtifactIdentity] = {}
    for artifact in feature_input.artifacts:
        key = (artifact.instance_id, artifact.submission_key, artifact.name)
        if key in result:
            raise ValueError("sanitized feature artifact identities are duplicate")
        result[key] = artifact
    expected = {
        (instance_id, submission_key, name)
        for instance_id in feature_input.selected_instance_ids
        for submission_key in feature_input.submission_keys
        for name in ("patch.diff", "trajectory.json")
    }
    if set(result) != expected:
        raise ValueError("sanitized feature artifact identity set drifted")
    return result


def _read_feature_artifact(
    artifact_root: pathlib.Path,
    record: FeatureArtifactIdentity,
) -> bytes | None:
    if record.availability == "unavailable":
        return None
    if (
        record.availability != "downloaded"
        or record.relative_path is None
        or record.byte_count is None
        or record.sha256 is None
    ):
        raise ValueError("sanitized feature artifact identity is incomplete")
    payload = _safe_declared_file(artifact_root, record.relative_path).read_bytes()
    if len(payload) != record.byte_count or _sha256(payload) != record.sha256:
        raise ValueError("sanitized feature artifact bytes drifted after acquisition validation")
    return payload


def _read_downloaded_artifact(
    artifact_root: pathlib.Path,
    record: Mapping[str, Any],
) -> bytes | None:
    if record["availability"] == "unavailable":
        return None
    relative = _string(record["relative_path"], "artifact.relative_path")
    return _safe_declared_file(artifact_root, relative).read_bytes()


def _trajectory_structure(payload: bytes) -> dict[str, Any]:
    """Extract post-rollout history structure, never semantic verdict text."""

    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid strict trajectory JSON: {exc}") from exc
    counts: Counter[str] = Counter()
    maximum_depth = 0
    stack: list[tuple[Any, int]] = [(decoded, 0)]
    while stack:
        value, depth = stack.pop()
        maximum_depth = max(maximum_depth, depth)
        counts["nodes"] += 1
        if isinstance(value, dict):
            counts["objects"] += 1
            counts["object_fields"] += len(value)
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            counts["arrays"] += 1
            counts["array_items"] += len(value)
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            counts["strings"] += 1
            counts["string_utf8_bytes"] += len(value.encode("utf-8"))
        elif isinstance(value, bool):
            counts["booleans"] += 1
        elif value is None:
            counts["nulls"] += 1
        elif isinstance(value, (int, float)):
            counts["numbers"] += 1
        else:
            raise ValueError(f"unsupported trajectory JSON value {type(value).__name__}")
        if counts["nodes"] > 2_000_000 or maximum_depth > 512:
            raise ValueError("trajectory JSON exceeds structural complexity bounds")
    return {
        "root_type": (
            "object"
            if isinstance(decoded, dict)
            else "array"
            if isinstance(decoded, list)
            else "scalar"
        ),
        "maximum_depth": maximum_depth,
        **{key: counts[key] for key in sorted(counts)},
    }


def _feature_row(
    artifact_root: pathlib.Path,
    *,
    instance_id: str,
    repository: str,
    spec: SubmissionSpec,
    artifacts: Mapping[tuple[str, str, str], FeatureArtifactIdentity],
    canonical_task: CanonicalTaskIdentity | None,
) -> FeatureRow:
    patch_record = artifacts[(instance_id, spec.key, "patch.diff")]
    trajectory_record = artifacts[(instance_id, spec.key, "trajectory.json")]
    patch_payload = _read_feature_artifact(artifact_root, patch_record)
    trajectory_payload = _read_feature_artifact(artifact_root, trajectory_record)
    patch_identity = {
        "availability": patch_record.availability,
        "bytes": patch_record.byte_count,
        "sha256": patch_record.sha256,
    }
    trajectory_identity = {
        "availability": trajectory_record.availability,
        "bytes": trajectory_record.byte_count,
        "sha256": trajectory_record.sha256,
    }
    static_features: Mapping[str, Any] | None = None
    trajectory_features: Mapping[str, Any] | None = None
    errors: list[str] = []
    candidate_risk: float | None = None
    files_changed: int | None = None
    lines_changed: int | None = None
    rollout_history_nodes: int | None = None
    patch_digest = patch_record.sha256
    rollout_id = (
        f"{instance_id}:{spec.key}:sha256:{patch_digest}"
        if isinstance(patch_digest, str)
        else f"{instance_id}:{spec.key}:unavailable"
    )
    if patch_payload is None:
        errors.append("patch_unavailable")
    else:
        try:
            patch_text = patch_payload.decode("utf-8")
            candidate_manifest = build_candidate_manifest(
                instance_id=instance_id,
                candidate_patch=patch_text,
                lifecycle_stage=LifecycleStage.ROLLOUT,
                provenance={
                    "repository": repository,
                    "candidate_generator": spec.submission_id,
                    "source_bucket": BUCKET_NAME,
                    "source_prefix": spec.root_prefix,
                },
            )
            decision = ConservativeRouter().route(candidate_manifest)
            manifest_record = candidate_manifest.to_dict()
            risk_profile = _object(manifest_record["risk_profile"], "risk profile")
            files_changed = int(risk_profile["files_changed"])
            lines_changed = int(risk_profile["lines_changed"])
            candidate_risk = decision.candidate_risk
            static_features = {
                "candidate_manifest_id": candidate_manifest.candidate_id,
                "candidate_manifest_sha256": candidate_manifest.canonical_digest(),
                "candidate_risk": candidate_risk,
                "router_policy_version": decision.policy_version,
                "initial_route_action": decision.action.value,
                "risk_profile": risk_profile,
            }
        except (UnicodeDecodeError, ValueError) as exc:
            errors.append(f"malformed_patch:{type(exc).__name__}")
    if trajectory_payload is None:
        errors.append("trajectory_unavailable")
    else:
        try:
            trajectory_features = _trajectory_structure(trajectory_payload)
            rollout_history_nodes = int(trajectory_features["nodes"])
        except ValueError as exc:
            errors.append(f"malformed_trajectory:{type(exc).__name__}")
    status = (
        "unavailable"
        if static_features is None
        else "complete"
        if trajectory_features is not None
        else "patch_only"
    )
    feature_record = {
        "instance_id": instance_id,
        "repository": repository,
        "submission_key": spec.key,
        "model_label": spec.model_label,
        "rollout_id": rollout_id,
        "feature_status": status,
        "errors": errors,
        "canonical_task_identity": (
            {
                "base_commit": canonical_task.base_commit,
                "environment_setup_commit": canonical_task.environment_setup_commit,
                "sha256": canonical_task.canonical_digest(),
            }
            if canonical_task is not None
            else None
        ),
        "patch_identity": patch_identity,
        "post_rollout_history_identity": trajectory_identity,
        "static_features": static_features,
        "post_rollout_history_structure": trajectory_features,
    }
    return FeatureRow(
        instance_id=instance_id,
        repository=repository,
        submission_key=spec.key,
        rollout_id=rollout_id,
        status=status,
        candidate_risk=candidate_risk,
        files_changed=files_changed,
        lines_changed=lines_changed,
        rollout_history_nodes=rollout_history_nodes,
        feature_record=feature_record,
    )


def _tie_hash(row: FeatureRow, policy: str, seed: int) -> str:
    material = (
        f"matched-rollout-policy-tie-v1\0{policy}\0{seed}\0"
        f"{row.instance_id}\0{row.submission_key}\0{row.rollout_id}"
    ).encode()
    return _sha256(material)


def _complete_policy_orders(
    rows: Sequence[FeatureRow],
    *,
    policy_seed: int,
) -> dict[str, list[dict[str, Any]]]:
    by_instance: dict[str, list[FeatureRow]] = defaultdict(list)
    for row in rows:
        by_instance[row.instance_id].append(row)
    orders: dict[str, list[dict[str, Any]]] = {policy: [] for policy in POLICY_NAMES}
    status_rank = {"complete": 0, "patch_only": 1, "unavailable": 2}

    for instance_id in sorted(by_instance):
        candidates = by_instance[instance_id]
        rollout_ids = [candidate.rollout_id for candidate in candidates]
        if len(rollout_ids) != len(set(rollout_ids)):
            raise ValueError(f"rollout identities collide for {instance_id}")

        def numeric(value: int | float | None) -> float:
            return math.inf if value is None else float(value)

        rank_sources = {
            "risk": sorted(
                candidates,
                key=lambda row: (
                    status_rank[row.status],
                    numeric(row.candidate_risk),
                    _tie_hash(row, "hybrid-risk", policy_seed),
                ),
            ),
            "patch": sorted(
                candidates,
                key=lambda row: (
                    status_rank[row.status],
                    numeric(row.lines_changed),
                    numeric(row.files_changed),
                    _tie_hash(row, "hybrid-patch", policy_seed),
                ),
            ),
            "rollout_history": sorted(
                candidates,
                key=lambda row: (
                    row.rollout_history_nodes is None,
                    numeric(row.rollout_history_nodes),
                    _tie_hash(row, "hybrid-rollout-history", policy_seed),
                ),
            ),
        }
        rank_sum: Counter[str] = Counter()
        for ranking in rank_sources.values():
            for rank, candidate in enumerate(ranking):
                rank_sum[candidate.rollout_id] += rank

        def policy_key(
            policy: str,
            row: FeatureRow,
            rank_sum_values: Mapping[str, int] = rank_sum,
        ) -> tuple[Any, ...]:
            tie = _tie_hash(row, policy, policy_seed)
            if policy == "hash_random":
                return (tie,)
            if policy == "router_low_risk":
                return (status_rank[row.status], numeric(row.candidate_risk), tie)
            if policy == "patch_smallest":
                return (
                    status_rank[row.status],
                    numeric(row.lines_changed),
                    numeric(row.files_changed),
                    tie,
                )
            if policy == "rollout_history_shortest":
                return (
                    row.rollout_history_nodes is None,
                    numeric(row.rollout_history_nodes),
                    tie,
                )
            if policy == "hybrid_rank_sum":
                return (status_rank[row.status], rank_sum_values[row.rollout_id], tie)
            preferred = {
                "gpt5_first": "gpt5",
                "kimi_k2_first": "kimi_k2",
                "claude_4_sonnet_first": "claude_4_sonnet",
            }[policy]
            return (row.submission_key != preferred, tie)

        for policy in POLICY_NAMES:
            ranked = sorted(candidates, key=lambda row: policy_key(policy, row))
            ordered_ids = [row.rollout_id for row in ranked]
            if set(ordered_ids) != set(rollout_ids) or len(ordered_ids) != len(rollout_ids):
                raise ValueError("policy order is not a complete candidate permutation")
            digest_payload = strict_json_dumps(
                {
                    "contract": ORDER_CONTRACT,
                    "instance_id": instance_id,
                    "policy": policy,
                    "ordered_rollout_ids": ordered_ids,
                }
            ).encode()
            orders[policy].append(
                {
                    "instance_id": instance_id,
                    "repository": ranked[0].repository,
                    "policy": policy,
                    "ordered_rollout_ids": ordered_ids,
                    "order_sha256": _sha256(digest_payload),
                }
            )
    return orders


def build_feature_freeze(
    artifact_root: pathlib.Path,
    feature_input: FeatureBuildInput,
    *,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
    policy_seed: int = DEFAULT_POLICY_SEED,
) -> tuple[dict[str, Any], tuple[FeatureRow, ...]]:
    """Build no-reference features from the closed, sanitized pre-outcome interface."""

    spec_map = _submission_map(specs)
    artifacts = _feature_artifact_index(feature_input)
    if feature_input.submission_keys != tuple(spec_map):
        raise ValueError("sanitized feature submission identity drifted")
    if isinstance(policy_seed, bool) or not isinstance(policy_seed, int) or policy_seed < 0:
        raise ValueError("policy_seed must be a non-negative integer")
    selected = list(feature_input.selected_instance_ids)
    if feature_input.selected_instance_ids_sha256 != _sha256("\n".join(selected).encode()):
        raise ValueError("sanitized selected-cohort digest drifted")
    canonical_by_id = {
        identity.instance_id: identity for identity in feature_input.canonical_task_identities
    }
    if len(canonical_by_id) != len(feature_input.canonical_task_identities):
        raise ValueError("sanitized canonical task identities are duplicate")
    if canonical_by_id and (
        set(canonical_by_id) != set(selected)
        or tuple(identity.instance_id for identity in feature_input.canonical_task_identities)
        != tuple(selected)
    ):
        raise ValueError("sanitized canonical task identities do not exactly match the cohort")
    if bool(canonical_by_id) != (feature_input.canonical_dataset_identity is not None):
        raise ValueError("sanitized canonical dataset/task provenance is incomplete")
    acquisition_code = dict(feature_input.acquisition_code_identity)
    _exact_fields(
        acquisition_code,
        {"logical_path", "bytes", "sha256"},
        "sanitized acquisition code identity",
    )
    if (
        acquisition_code["logical_path"] != STUDY_CODE_LOGICAL_PATH
        or isinstance(acquisition_code["bytes"], bool)
        or not isinstance(acquisition_code["bytes"], int)
        or acquisition_code["bytes"] < 1
        or not isinstance(acquisition_code["sha256"], str)
        or _SHA256_RE.fullmatch(acquisition_code["sha256"]) is None
    ):
        raise ValueError("sanitized acquisition code identity drifted")
    canonical_dataset_identity: dict[str, Any] | None = None
    if feature_input.canonical_dataset_identity is not None:
        canonical_dataset_identity = dict(feature_input.canonical_dataset_identity)
        _exact_fields(
            canonical_dataset_identity,
            {
                "dataset_id",
                "revision",
                "bytes",
                "sha256",
                "identity_projection_sha256",
                "selected_task_identities_sha256",
            },
            "sanitized canonical dataset identity",
        )
        selected_identity_payload = (
            strict_json_dumps(
                [canonical_by_id[instance_id].to_dict() for instance_id in selected],
                indent=2,
            )
            + "\n"
        ).encode()
        if (
            canonical_dataset_identity["dataset_id"] != CANONICAL_DATASET_ID
            or canonical_dataset_identity["revision"] != CANONICAL_DATASET_REVISION
            or canonical_dataset_identity["bytes"] != CANONICAL_DATASET_BYTES
            or canonical_dataset_identity["sha256"] != CANONICAL_DATASET_SHA256
            or canonical_dataset_identity["identity_projection_sha256"]
            != CANONICAL_DATASET_PROJECTION_SHA256
            or canonical_dataset_identity["selected_task_identities_sha256"]
            != _sha256(selected_identity_payload)
        ):
            raise ValueError("sanitized canonical dataset/task identity drifted")
        for identity in canonical_by_id.values():
            if (
                identity.repository != infer_repository(identity.instance_id)
                or _COMMIT_RE.fullmatch(identity.base_commit) is None
                or _COMMIT_RE.fullmatch(identity.environment_setup_commit) is None
            ):
                raise ValueError("sanitized canonical task commit identity drifted")
    rows: list[FeatureRow] = []
    for instance_id in selected:
        repository = infer_repository(instance_id)
        for key in spec_map:
            rows.append(
                _feature_row(
                    artifact_root,
                    instance_id=instance_id,
                    repository=repository,
                    spec=spec_map[key],
                    artifacts=artifacts,
                    canonical_task=canonical_by_id.get(instance_id),
                )
            )
    rows.sort(key=lambda row: (row.instance_id, row.submission_key))
    orders = _complete_policy_orders(rows, policy_seed=policy_seed)
    freeze = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "feature_contract": FEATURE_CONTRACT,
        "policy_order_contract": ORDER_CONTRACT,
        "policy_seed": policy_seed,
        "source_revision": SOURCE_REVISION,
        "analysis_code_identity": _study_code_identity(),
        "acquisition_code_identity": acquisition_code,
        "canonical_dataset_identity": canonical_dataset_identity,
        "cohort_identity": {
            "selected_instance_ids_sha256": feature_input.selected_instance_ids_sha256,
            "selected_instance_count": len(selected),
            "submission_keys": list(spec_map),
            "canonical_task_identity_count": len(canonical_by_id),
        },
        "rows": [dict(row.feature_record) for row in rows],
        "full_candidate_orders": orders,
        "phase_assertion": "serialized_before_any_hosted_outcome_decode",
        "included_inputs": [
            "frozen task and submission identities",
            "canonical repository, base commit, and environment commit when production-pinned",
            "patch bytes and SHA-256",
            "deployable patch-static manifest and initial router decision",
            "post-rollout trajectory bytes, SHA-256, and content-agnostic JSON structure",
            "fixed policy seed",
        ],
        "excluded_inputs": [
            "results.json bytes, digest, size, categories, or availability",
            "report.json bytes, digest, size, labels, tests, or availability",
            "test_output.txt",
            "reference patches",
            "hidden tests",
            "hosted resolved labels",
        ],
        "evidence_timing": {
            "patch_static": (
                "computed from candidate patch bytes without additional test execution"
            ),
            "post_rollout_history_structure": (
                "available only after the agent rollout; may encode prior shell/test tool use"
            ),
            "execution_cost_accounting": (
                "sunk rollout execution and tool cost is not reconstructed by this source"
            ),
        },
    }
    return freeze, tuple(rows)


def load_durable_feature_freeze(
    freeze_path: pathlib.Path,
    artifact_root: pathlib.Path,
    feature_input: FeatureBuildInput,
    *,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
    policy_seed: int = DEFAULT_POLICY_SEED,
) -> tuple[dict[str, Any], tuple[FeatureRow, ...], bytes]:
    """Reload and rederive the durable freeze before any outcome is decoded."""

    if freeze_path.is_symlink() or not freeze_path.is_file():
        raise ValueError("feature freeze must be a regular non-symlink file")
    payload = freeze_path.read_bytes()
    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid durable feature freeze: {exc}") from exc
    loaded = _object(decoded, "feature freeze")
    canonical_payload = (strict_json_dumps(loaded, indent=2) + "\n").encode()
    if payload != canonical_payload:
        raise ValueError("durable feature freeze JSON is not canonical")
    expected, expected_rows = build_feature_freeze(
        artifact_root,
        feature_input,
        specs=specs,
        policy_seed=policy_seed,
    )
    if loaded != expected:
        raise ValueError("durable feature freeze cannot be exactly rederived")
    expected_by_rollout = {row.rollout_id: row for row in expected_rows}
    durable_rows: list[FeatureRow] = []
    for raw_record in _array(loaded.get("rows"), "feature freeze.rows"):
        record = _object(raw_record, "feature freeze row")
        rollout_id = _string(record.get("rollout_id"), "feature freeze row.rollout_id")
        if rollout_id not in expected_by_rollout:
            raise ValueError("durable feature freeze contains an unknown rollout")
        expected_row = expected_by_rollout.pop(rollout_id)
        durable_rows.append(
            FeatureRow(
                instance_id=expected_row.instance_id,
                repository=expected_row.repository,
                submission_key=expected_row.submission_key,
                rollout_id=expected_row.rollout_id,
                status=expected_row.status,
                candidate_risk=expected_row.candidate_risk,
                files_changed=expected_row.files_changed,
                lines_changed=expected_row.lines_changed,
                rollout_history_nodes=expected_row.rollout_history_nodes,
                feature_record=record,
            )
        )
    if expected_by_rollout:
        raise ValueError("durable feature freeze omits expected rollouts")
    return loaded, tuple(durable_rows), payload


def _test_group_counts(
    report: Mapping[str, Any],
    instance_id: str,
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    tests = _object(report.get("tests_status"), f"report[{instance_id}].tests_status")
    expected_groups = {"FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_FAIL", "PASS_TO_FAIL"}
    _exact_fields(tests, expected_groups, f"report[{instance_id}].tests_status")
    counts: dict[str, dict[str, int]] = {}
    signature_groups: dict[str, list[str]] = {}
    seen_test_ids: set[str] = set()
    for group in sorted(tests):
        values = _object(tests[group], f"report[{instance_id}].{group}")
        _exact_fields(values, {"success", "failure"}, f"report[{instance_id}].{group}")
        success = _array(values["success"], f"report[{instance_id}].{group}.success")
        failure = _array(values["failure"], f"report[{instance_id}].{group}.failure")
        for disposition, names in (("success", success), ("failure", failure)):
            if any(not isinstance(name, str) or not name for name in names):
                raise ValueError(
                    f"report[{instance_id}].{group}.{disposition} must contain test IDs"
                )
            if len(names) != len(set(names)):
                raise ValueError(f"report[{instance_id}].{group}.{disposition} contains duplicates")
        if set(success) & set(failure):
            raise ValueError(f"report[{instance_id}].{group} contradicts itself")
        group_ids = set(success) | set(failure)
        if seen_test_ids & group_ids:
            raise ValueError(f"report[{instance_id}] repeats a test across groups")
        seen_test_ids.update(group_ids)
        counts[group] = {"success": len(success), "failure": len(failure)}
        signature_groups[group] = sorted(group_ids)
    signature_payload = strict_json_dumps(signature_groups).encode()
    signature = {
        "contract": "hosted-report-test-id-set-by-group-v1",
        "test_count": len(seen_test_ids),
        "sha256": _sha256(signature_payload),
    }
    return counts, signature


def parse_hosted_report(payload: bytes, instance_id: str) -> dict[str, Any]:
    """Strictly decode one outcome-bearing hosted report after the freeze."""

    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid hosted report for {instance_id}: {exc}") from exc
    root = _object(decoded, f"report[{instance_id}]")
    if set(root) != {instance_id}:
        raise ValueError(f"hosted report must contain only {instance_id!r}")
    report = _object(root[instance_id], f"report[{instance_id}]")
    _exact_fields(
        report,
        {
            "patch_exists",
            "patch_is_None",
            "patch_successfully_applied",
            "resolved",
            "tests_status",
        },
        f"report[{instance_id}]",
    )
    groups, test_signature = _test_group_counts(report, instance_id)
    result = {
        "hosted_resolved": _boolean(report["resolved"], "report.resolved"),
        "patch_exists": _boolean(report["patch_exists"], "report.patch_exists"),
        "patch_is_none": _boolean(report["patch_is_None"], "report.patch_is_None"),
        "patch_successfully_applied": _boolean(
            report["patch_successfully_applied"],
            "report.patch_successfully_applied",
        ),
        "fail_to_pass_success": groups["FAIL_TO_PASS"]["success"],
        "fail_to_pass_failure": groups["FAIL_TO_PASS"]["failure"],
        "pass_to_pass_success": groups["PASS_TO_PASS"]["success"],
        "pass_to_pass_failure": groups["PASS_TO_PASS"]["failure"],
        "all_test_group_counts": groups,
        "test_signature": test_signature,
    }
    if result["patch_exists"] == result["patch_is_none"]:
        raise ValueError(f"hosted report has contradictory patch presence for {instance_id}")
    if result["patch_successfully_applied"] and (
        not result["patch_exists"] or result["patch_is_none"]
    ):
        raise ValueError(f"hosted report applies an absent patch for {instance_id}")
    derived_resolved = bool(
        result["patch_successfully_applied"]
        and result["fail_to_pass_failure"] == 0
        and result["pass_to_pass_failure"] == 0
    )
    if result["hosted_resolved"] != derived_resolved:
        raise ValueError(
            f"hosted resolved label contradicts test/application fields for {instance_id}"
        )
    return result


def _parse_official_results(payload: bytes, *, spec: SubmissionSpec) -> dict[str, set[str]]:
    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid official results for {spec.key}: {exc}") from exc
    root = _object(decoded, f"results[{spec.key}]")
    _exact_fields(root, {"no_generation", "no_logs", "resolved"}, f"results[{spec.key}]")
    result: dict[str, set[str]] = {}
    seen: set[str] = set()
    for category in ("no_generation", "no_logs", "resolved"):
        values = _array(root[category], f"results[{spec.key}].{category}")
        if any(not isinstance(value, str) for value in values):
            raise ValueError("official result categories must contain instance IDs")
        typed = [str(value) for value in values]
        if typed != sorted(typed) or len(typed) != len(set(typed)):
            raise ValueError("official result category is duplicate or non-canonical")
        for instance_id in typed:
            infer_repository(instance_id)
        if seen & set(typed):
            raise ValueError("official result categories overlap")
        seen.update(typed)
        result[category] = set(typed)
    return result


def _canonical_task_ids_for_outcome_scope(
    manifest: Mapping[str, Any],
) -> set[str] | None:
    """Return the validated canonical task universe when one is declared.

    Official result files describe evaluation disposition, not only objects
    that reached the submission's log bucket. A ``no_generation``/``no_logs``
    task can therefore be canonical while having no artifact-frame prefix. The
    caller still requires every selected candidate to belong to its artifact
    frame and never permits an out-of-frame resolved label.
    """

    raw_canonical = manifest.get("canonical_dataset")
    if raw_canonical is None:
        return None
    canonical = _object(raw_canonical, "acquisition.canonical_dataset")
    if (
        canonical.get("dataset_id") != CANONICAL_DATASET_ID
        or canonical.get("revision") != CANONICAL_DATASET_REVISION
    ):
        raise ValueError("canonical dataset outcome universe identity drifted")
    rows = _array(
        canonical.get("task_identities"),
        "acquisition.canonical_dataset.task_identities",
    )
    instance_ids: list[str] = []
    for index, raw_row in enumerate(rows):
        field = f"acquisition.canonical_dataset.task_identities[{index}]"
        row = _object(raw_row, field)
        _exact_fields(row, set(CANONICAL_DATASET_PROJECTION_FIELDS), field)
        instance_id = _string(row["instance_id"], f"{field}.instance_id")
        repository = _string(row["repo"], f"{field}.repo")
        base_commit = _string(row["base_commit"], f"{field}.base_commit")
        environment_commit = _string(
            row["environment_setup_commit"],
            f"{field}.environment_setup_commit",
        )
        if repository != infer_repository(instance_id):
            raise ValueError("canonical outcome universe repository identity drifted")
        if (
            _COMMIT_RE.fullmatch(base_commit) is None
            or _COMMIT_RE.fullmatch(environment_commit) is None
        ):
            raise ValueError("canonical outcome universe commit identity drifted")
        instance_ids.append(instance_id)
    if (
        not instance_ids
        or instance_ids != sorted(instance_ids)
        or len(instance_ids) != len(set(instance_ids))
    ):
        raise ValueError("canonical outcome universe is empty, duplicate, or non-canonical")
    return set(instance_ids)


def _source_file_path(
    manifest: Mapping[str, Any],
    *,
    submission_key: str,
    name: str,
) -> str:
    matches: list[str] = []
    for raw_submission in manifest["submissions"]:
        submission = _object(raw_submission, "submission")
        if submission["submission_key"] != submission_key:
            continue
        for raw_file in submission["files"]:
            file_record = _object(raw_file, "source file")
            relative = str(file_record["relative_path"])
            if pathlib.PurePosixPath(relative).name == name:
                matches.append(relative)
    if len(matches) != 1:
        raise ValueError(f"expected one {submission_key}/{name} source file")
    return matches[0]


def decode_hosted_outcomes(
    artifact_root: pathlib.Path,
    manifest: Mapping[str, Any],
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
) -> tuple[OutcomeRow, ...]:
    """Decode hosted labels; callers must invoke only after writing the freeze."""

    artifacts = _artifact_index(manifest)
    selected = [str(value) for value in manifest["cohort"]["selected_instance_ids"]]
    selected_set = set(selected)
    canonical_task_ids = _canonical_task_ids_for_outcome_scope(manifest)
    outcomes: list[OutcomeRow] = []
    for spec in specs:
        results_relative = _source_file_path(
            manifest,
            submission_key=spec.key,
            name="results.json",
        )
        results_payload = _safe_declared_file(artifact_root, results_relative).read_bytes()
        categories = _parse_official_results(results_payload, spec=spec)
        frame_relative = _source_file_path(
            manifest,
            submission_key=spec.key,
            name="frame-listing.xml",
        )
        frame_ids = set(
            enumerate_instance_ids(
                _safe_declared_file(artifact_root, frame_relative).read_bytes(),
                spec=spec,
            )
        )
        categorized_ids = set().union(*categories.values())
        if not selected_set <= frame_ids:
            raise ValueError(f"selected candidates escape the {spec.key} artifact frame")
        permitted_ids = frame_ids if canonical_task_ids is None else canonical_task_ids
        if not categorized_ids <= permitted_ids:
            raise ValueError(
                f"official result categories escape the {spec.key} canonical task universe"
            )
        if categories["resolved"] - frame_ids:
            raise ValueError(
                f"official resolved categories escape the {spec.key} artifact frame"
            )
        for instance_id in selected:
            if instance_id in categories["no_generation"]:
                disposition = "no_generation"
                official_resolved: bool | None = None
            elif instance_id in categories["no_logs"]:
                disposition = "no_logs"
                official_resolved = None
            elif instance_id in categories["resolved"]:
                disposition = "resolved"
                official_resolved = True
            else:
                disposition = "failed"
                official_resolved = False
            report_record = artifacts[(instance_id, spec.key, "report.json")]
            report_payload = _read_downloaded_artifact(artifact_root, report_record)
            parsed_report: Mapping[str, Any] | None = None
            source = "pinned_official_results_only"
            if report_payload is not None:
                if official_resolved is None:
                    raise ValueError(
                        f"unknown official outcome unexpectedly has a report: "
                        f"{spec.key}/{instance_id}"
                    )
                parsed_report = parse_hosted_report(report_payload, instance_id)
                if parsed_report["hosted_resolved"] is not official_resolved:
                    raise ValueError(
                        f"official/report hosted outcome mismatch for {spec.key}/{instance_id}"
                    )
                source = "pinned_official_results_cross_checked_by_report"
            elif official_resolved:
                raise ValueError(
                    f"officially resolved candidate lacks a report: {spec.key}/{instance_id}"
                )
            outcomes.append(
                OutcomeRow(
                    instance_id=instance_id,
                    repository=infer_repository(instance_id),
                    submission_key=spec.key,
                    hosted_resolved=official_resolved,
                    disposition=disposition,
                    source=source,
                    report_record=parsed_report,
                )
            )
    outcomes.sort(key=lambda row: (row.instance_id, row.submission_key))
    return tuple(outcomes)


def _validated_orders(
    freeze: Mapping[str, Any],
    rows: Sequence[FeatureRow],
) -> dict[str, dict[str, tuple[str, ...]]]:
    expected_by_instance: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        expected_by_instance[row.instance_id].add(row.rollout_id)
    raw_orders = _object(freeze["full_candidate_orders"], "freeze.full_candidate_orders")
    if set(raw_orders) != set(POLICY_NAMES):
        raise ValueError("frozen policy set drifted")
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for policy in POLICY_NAMES:
        policy_rows = _array(raw_orders[policy], f"freeze.orders.{policy}")
        by_instance: dict[str, tuple[str, ...]] = {}
        for raw_order in policy_rows:
            order = _object(raw_order, f"freeze.orders.{policy}[]")
            instance_id = _string(order["instance_id"], "order.instance_id")
            if order.get("policy") != policy or instance_id in by_instance:
                raise ValueError("frozen order policy/instance identity drifted")
            values = _array(order.get("ordered_rollout_ids"), "order.ordered_rollout_ids")
            if any(not isinstance(value, str) for value in values):
                raise ValueError("frozen order must contain rollout IDs")
            ordered = tuple(str(value) for value in values)
            if set(ordered) != expected_by_instance[instance_id] or len(ordered) != len(
                expected_by_instance[instance_id]
            ):
                raise ValueError("frozen order is not a complete candidate permutation")
            digest_payload = strict_json_dumps(
                {
                    "contract": ORDER_CONTRACT,
                    "instance_id": instance_id,
                    "policy": policy,
                    "ordered_rollout_ids": list(ordered),
                }
            ).encode()
            if order.get("order_sha256") != _sha256(digest_payload):
                raise ValueError("frozen candidate-order digest drifted")
            by_instance[instance_id] = ordered
        if set(by_instance) != set(expected_by_instance):
            raise ValueError("frozen orders do not cover the complete cohort")
        result[policy] = by_instance
    return result


def _select_with_budget(
    order: Sequence[str],
    labels: Mapping[str, bool | None],
    *,
    maximum_reveals: int,
) -> tuple[str, int, tuple[str, ...], str]:
    if not 0 <= maximum_reveals <= len(order):
        raise ValueError("reveal budget is outside the candidate-order range")
    revealed: list[str] = []
    for rollout_id in order[:maximum_reveals]:
        revealed.append(rollout_id)
        if labels[rollout_id] is True:
            return rollout_id, len(revealed), tuple(revealed), "first_revealed_success"
    if maximum_reveals < len(order):
        selected = order[maximum_reveals]
        reason = (
            "highest_ranked_unrevealed_after_unknown_or_failed_outcomes"
            if any(labels[rollout_id] is None for rollout_id in revealed)
            else "highest_ranked_unrevealed_after_observed_failures"
        )
    else:
        unknown = [rollout_id for rollout_id in order if labels[rollout_id] is None]
        selected = unknown[0] if unknown else order[0]
        reason = (
            "all_candidates_revealed_with_unknown_outcomes"
            if unknown
            else "all_candidates_revealed_failed"
        )
    return selected, len(revealed), tuple(revealed), reason


def _policy_budget_result(
    *,
    policy: str,
    maximum_reveals: int,
    orders: Mapping[str, Sequence[str]],
    labels: Mapping[str, bool],
    repository_by_instance: Mapping[str, str],
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    repository_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for instance_id in sorted(orders):
        selected, reveals, revealed, reason = _select_with_budget(
            orders[instance_id],
            labels,
            maximum_reveals=maximum_reveals,
        )
        resolved = labels[selected]
        any_resolved = any(labels[rollout_id] for rollout_id in orders[instance_id])
        repository = repository_by_instance[instance_id]
        repository_counts[repository]["tasks"] += 1
        repository_counts[repository]["selected_resolved"] += int(resolved)
        repository_counts[repository]["oracle_resolvable"] += int(any_resolved)
        repository_counts[repository]["reveals"] += reveals
        decisions.append(
            {
                "instance_id": instance_id,
                "repository": repository,
                "ordered_rollout_ids": list(orders[instance_id]),
                "revealed_rollout_ids": list(revealed),
                "selected_rollout_id": selected,
                "selected_hosted_resolved": resolved,
                "any_candidate_hosted_resolved": any_resolved,
                "hosted_labels_revealed": reveals,
                "selection_reason": reason,
            }
        )
    task_count = len(decisions)
    resolved_count = sum(item["selected_hosted_resolved"] for item in decisions)
    oracle_count = sum(item["any_candidate_hosted_resolved"] for item in decisions)
    total_reveals = sum(item["hosted_labels_revealed"] for item in decisions)
    return {
        "policy": policy,
        "maximum_hosted_label_reveals_per_task": maximum_reveals,
        "task_count": task_count,
        "selected_hosted_resolved_count": resolved_count,
        "selected_hosted_resolved_rate": (resolved_count / task_count if task_count else None),
        "oracle_resolvable_task_count": oracle_count,
        "oracle_regret_count": oracle_count - resolved_count,
        "total_hosted_labels_revealed": total_reveals,
        "mean_hosted_labels_revealed_per_task": (
            total_reveals / task_count if task_count else None
        ),
        "by_repository": [
            {
                "repository": repository,
                "task_count": counts["tasks"],
                "selected_hosted_resolved_count": counts["selected_resolved"],
                "selected_hosted_resolved_rate": (counts["selected_resolved"] / counts["tasks"]),
                "oracle_resolvable_task_count": counts["oracle_resolvable"],
                "mean_hosted_labels_revealed_per_task": (counts["reveals"] / counts["tasks"]),
            }
            for repository, counts in sorted(repository_counts.items())
        ],
        "decisions": decisions,
    }


def _candidate_patch_diversity(rows: Sequence[FeatureRow]) -> dict[str, Any]:
    by_instance: dict[str, list[FeatureRow]] = defaultdict(list)
    for row in rows:
        by_instance[row.instance_id].append(row)
    tasks: list[dict[str, Any]] = []
    for instance_id, candidates in sorted(by_instance.items()):
        by_digest: dict[str, list[FeatureRow]] = defaultdict(list)
        unavailable: list[str] = []
        for candidate in candidates:
            patch = _object(
                candidate.feature_record.get("patch_identity"),
                "feature row.patch_identity",
            )
            digest = patch.get("sha256")
            if isinstance(digest, str) and _SHA256_RE.fullmatch(digest):
                by_digest[digest].append(candidate)
            else:
                unavailable.append(candidate.submission_key)
        duplicate_groups = [
            {
                "patch_sha256": digest,
                "submission_keys": sorted(row.submission_key for row in digest_rows),
                "rollout_ids": sorted(row.rollout_id for row in digest_rows),
            }
            for digest, digest_rows in sorted(by_digest.items())
            if len(digest_rows) > 1
        ]
        complete = (
            len(by_digest) + sum(len(group["submission_keys"]) - 1 for group in duplicate_groups)
            == len(candidates)
            and not unavailable
        )
        tasks.append(
            {
                "instance_id": instance_id,
                "candidate_count": len(candidates),
                "available_patch_count": sum(len(group) for group in by_digest.values()),
                "unique_patch_sha256_count": len(by_digest),
                "unavailable_submission_keys": sorted(unavailable),
                "duplicate_patch_groups": duplicate_groups,
                "complete_patch_set": complete,
                "all_candidate_patches_byte_distinct": (
                    complete and len(by_digest) == len(candidates)
                ),
            }
        )
    return {
        "identity_contract": "exact-patch-bytes-sha256-v1",
        "task_count": len(tasks),
        "complete_patch_set_task_count": sum(item["complete_patch_set"] for item in tasks),
        "all_candidate_patches_byte_distinct_task_count": sum(
            item["all_candidate_patches_byte_distinct"] for item in tasks
        ),
        "duplicate_patch_task_count": sum(bool(item["duplicate_patch_groups"]) for item in tasks),
        "incomplete_patch_task_count": sum(not item["complete_patch_set"] for item in tasks),
        "tasks": tasks,
    }


def _report_test_signature_comparability(
    selected_instance_ids: Sequence[str],
    outcomes: Sequence[OutcomeRow],
    *,
    specs: Sequence[SubmissionSpec],
) -> dict[str, Any]:
    by_pair = {(row.instance_id, row.submission_key): row for row in outcomes}
    tasks: list[dict[str, Any]] = []
    for instance_id in selected_instance_ids:
        signatures: dict[str, list[str]] = defaultdict(list)
        unavailable: list[str] = []
        for spec in specs:
            outcome = by_pair[(instance_id, spec.key)]
            if outcome.report_record is None:
                unavailable.append(spec.key)
                continue
            signature = _object(
                outcome.report_record.get("test_signature"),
                "hosted report.test_signature",
            )
            digest = _string(signature.get("sha256"), "test_signature.sha256")
            if not _SHA256_RE.fullmatch(digest):
                raise ValueError("hosted report test signature is not SHA-256")
            signatures[digest].append(spec.key)
        complete = not unavailable and sum(len(values) for values in signatures.values()) == len(
            specs
        )
        tasks.append(
            {
                "instance_id": instance_id,
                "report_available_candidate_count": sum(
                    len(values) for values in signatures.values()
                ),
                "unique_test_signature_count": len(signatures),
                "unavailable_submission_keys": sorted(unavailable),
                "signature_groups": [
                    {
                        "test_signature_sha256": digest,
                        "submission_keys": sorted(keys),
                    }
                    for digest, keys in sorted(signatures.items())
                ],
                "complete_report_set": complete,
                "exact_test_signature_match": (len(signatures) == 1 if complete else None),
            }
        )
    return {
        "signature_contract": "hosted-report-test-id-set-by-group-v1",
        "task_count": len(tasks),
        "complete_report_set_task_count": sum(item["complete_report_set"] for item in tasks),
        "exact_test_signature_match_task_count": sum(
            item["exact_test_signature_match"] is True for item in tasks
        ),
        "test_signature_mismatch_task_count": sum(
            item["exact_test_signature_match"] is False for item in tasks
        ),
        "incomplete_report_set_task_count": sum(not item["complete_report_set"] for item in tasks),
        "tasks": tasks,
    }


def analyze_study(
    artifact_root: pathlib.Path,
    *,
    freeze_output: pathlib.Path,
    report_output: pathlib.Path,
    specs: Sequence[SubmissionSpec] = SUBMISSIONS,
    policy_seed: int = DEFAULT_POLICY_SEED,
    outcome_decoder: OutcomeDecoder = decode_hosted_outcomes,
) -> dict[str, Any]:
    """Freeze predictors first, then decode outcomes and write the report."""

    artifact_root = artifact_root.absolute()
    freeze_output = freeze_output.absolute()
    report_output = report_output.absolute()
    for output in (freeze_output, report_output):
        with contextlib.suppress(ValueError):
            output.relative_to(artifact_root)
            raise ValueError("analysis outputs must be outside the immutable acquisition tree")
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"analysis output already exists: {output}")
    if freeze_output == report_output:
        raise ValueError("freeze and report outputs must be distinct")

    manifest, manifest_payload = validate_acquisition(artifact_root, specs=specs)
    feature_input = sanitize_feature_inputs(manifest, specs=specs)
    in_memory_freeze, _ = build_feature_freeze(
        artifact_root,
        feature_input,
        specs=specs,
        policy_seed=policy_seed,
    )
    atomic_write(
        freeze_output,
        strict_json_dumps(in_memory_freeze, indent=2) + "\n",
    )

    # The durable bytes are reloaded and exactly rederived before the one
    # deliberate transition to outcome-bearing sources.
    freeze, feature_rows, freeze_payload = load_durable_feature_freeze(
        freeze_output,
        artifact_root,
        feature_input,
        specs=specs,
        policy_seed=policy_seed,
    )
    outcomes = outcome_decoder(artifact_root, manifest, specs)
    outcome_by_pair = {(row.instance_id, row.submission_key): row for row in outcomes}
    expected_pairs = {(row.instance_id, row.submission_key) for row in feature_rows}
    if set(outcome_by_pair) != expected_pairs:
        raise ValueError("outcome decoder did not return the complete matched cohort")
    expected_dispositions = {
        "resolved": True,
        "failed": False,
        "no_generation": None,
        "no_logs": None,
    }
    for outcome in outcomes:
        if (
            outcome.disposition not in expected_dispositions
            or outcome.hosted_resolved is not expected_dispositions.get(outcome.disposition)
        ):
            raise ValueError("outcome decoder returned an invalid typed disposition")

    selected_ids = [str(value) for value in manifest["cohort"]["selected_instance_ids"]]
    quarantined_tasks: list[dict[str, Any]] = []
    eligible_ids: list[str] = []
    for instance_id in selected_ids:
        unknowns = [
            outcome_by_pair[(instance_id, spec.key)]
            for spec in specs
            if outcome_by_pair[(instance_id, spec.key)].hosted_resolved is None
        ]
        if unknowns:
            quarantined_tasks.append(
                {
                    "instance_id": instance_id,
                    "reason": "one_or_more_candidate_outcomes_unknown",
                    "unknown_candidates": [
                        {
                            "submission_key": outcome.submission_key,
                            "disposition": outcome.disposition,
                        }
                        for outcome in unknowns
                    ],
                }
            )
        else:
            eligible_ids.append(instance_id)
    eligible_set = set(eligible_ids)

    labels: dict[str, bool] = {}
    repository_by_instance: dict[str, str] = {}
    for row in feature_rows:
        if row.instance_id not in eligible_set:
            continue
        outcome = outcome_by_pair[(row.instance_id, row.submission_key)]
        if row.rollout_id in labels:
            raise ValueError("rollout IDs are not globally unique")
        if outcome.hosted_resolved is None:
            raise AssertionError("quarantined outcome entered the policy evaluator")
        labels[row.rollout_id] = outcome.hosted_resolved
        repository_by_instance[row.instance_id] = row.repository
    full_orders = _validated_orders(freeze, feature_rows)
    orders = {
        policy: {
            instance_id: order
            for instance_id, order in policy_orders.items()
            if instance_id in eligible_set
        }
        for policy, policy_orders in full_orders.items()
    }
    candidate_count = len(specs)
    policy_results = [
        _policy_budget_result(
            policy=policy,
            maximum_reveals=budget,
            orders=orders[policy],
            labels=labels,
            repository_by_instance=repository_by_instance,
        )
        for budget in range(candidate_count + 1)
        for policy in POLICY_NAMES
    ]

    model_results: list[dict[str, Any]] = []
    for spec in specs:
        all_outcomes = [outcome_by_pair[(instance_id, spec.key)] for instance_id in selected_ids]
        eligible_labels = [
            outcome_by_pair[(instance_id, spec.key)].hosted_resolved for instance_id in eligible_ids
        ]
        if any(value is None for value in eligible_labels):
            raise AssertionError("eligible model baseline contains an unknown outcome")
        resolved_count = sum(value is True for value in eligible_labels)
        model_results.append(
            {
                "submission_key": spec.key,
                "model_label": spec.model_label,
                "selected_cohort_disposition_counts": dict(
                    sorted(Counter(row.disposition for row in all_outcomes).items())
                ),
                "matched_known_task_count": len(eligible_ids),
                "hosted_resolved_count": resolved_count,
                "hosted_resolved_rate_among_matched_known_tasks": (
                    resolved_count / len(eligible_ids) if eligible_ids else None
                ),
            }
        )
    oracle_count = sum(
        any(outcome_by_pair[(instance_id, spec.key)].hosted_resolved is True for spec in specs)
        for instance_id in eligible_ids
    )
    best_single_count = max(
        (int(row["hosted_resolved_count"]) for row in model_results),
        default=0,
    )
    freeze_sha256 = _sha256(freeze_payload)
    patch_diversity = _candidate_patch_diversity(feature_rows)
    test_comparability = _report_test_signature_comparability(
        selected_ids,
        outcomes,
        specs=specs,
    )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "estimand": (
            "retrospective selected hosted-resolved rate among fully observed, "
            "same-task candidates from three checked OpenHands-family submissions "
            "under fixed maximum label-reveal budgets"
        ),
        "source_revision": SOURCE_REVISION,
        "study_code_identity": dict(freeze["analysis_code_identity"]),
        "acquisition_study_code_identity": dict(freeze["acquisition_code_identity"]),
        "study_code_identity_matches_acquisition": (
            freeze["analysis_code_identity"] == freeze["acquisition_code_identity"]
        ),
        "canonical_dataset_provenance": freeze["canonical_dataset_identity"],
        "acquisition_manifest_sha256": _sha256(manifest_payload),
        "feature_freeze": {
            "bytes": len(freeze_payload),
            "sha256": freeze_sha256,
            "completed_before_outcome_decode": True,
            "durable_reload_and_rederivation_validated_before_outcome_decode": True,
            "feature_contract": FEATURE_CONTRACT,
            "policy_order_contract": ORDER_CONTRACT,
        },
        "cohort": manifest["cohort"],
        "candidate_count_per_task": candidate_count,
        "outcome_quarantine": {
            "selected_task_count": len(selected_ids),
            "matched_known_task_count": len(eligible_ids),
            "quarantined_task_count": len(quarantined_tasks),
            "unknown_outcome_candidate_count": sum(
                len(task["unknown_candidates"]) for task in quarantined_tasks
            ),
            "policy": "exclude_the_entire_task_from_rates_if_any_candidate_is_unknown",
            "tasks": quarantined_tasks,
        },
        "candidate_feature_status_counts": dict(
            sorted(Counter(row.status for row in feature_rows).items())
        ),
        "post_rollout_history_evidence": {
            "candidate_count_with_structure": sum(
                row.rollout_history_nodes is not None for row in feature_rows
            ),
            "timing": "available_only_after_rollout_completion",
            "sunk_cost_limitation": (
                "trajectory structure may encode shell/test tool use, while its execution, "
                "latency, and infrastructure cost are not reconstructed"
            ),
        },
        "hosted_outcome_disposition_counts": dict(
            sorted(Counter(row.disposition for row in outcomes).items())
        ),
        "hosted_outcome_sources": dict(sorted(Counter(row.source for row in outcomes).items())),
        "candidate_patch_diversity": patch_diversity,
        "report_test_signature_comparability": test_comparability,
        "single_submission_baselines": model_results,
        "best_of_n_hosted_oracle_upper_bound": {
            "matched_known_task_count": len(eligible_ids),
            "any_candidate_hosted_resolved_count": oracle_count,
            "any_candidate_hosted_resolved_rate": (
                oracle_count / len(eligible_ids) if eligible_ids else None
            ),
            "best_single_submission_resolved_count": best_single_count,
            "diversity_headroom_count": oracle_count - best_single_count,
            "diversity_headroom_percentage_points": (
                100 * (oracle_count - best_single_count) / len(eligible_ids)
                if eligible_ids
                else None
            ),
            "interpretation": (
                "retrospective post-outcome ceiling with all labels; not a deployable selector"
            ),
        },
        "equal_maximum_reveal_budget_results": policy_results,
        "limitations": [
            "The checked flag is hosted-submission metadata, not independent reproduction.",
            "Only task identity and OpenHands submission family are matched; exact scaffold, prompt, configuration, environment, and resource budgets are not established.",
            "Hosted resolved labels are execution measurements, not semantic ground truth.",
            "No task-validity, oracle-validity, or candidate-correctness adjudication is present.",
            "The cohort is a small deterministic development slice, not a population sample.",
            "Model and generation date remain confounded across the three submissions.",
            "Post-rollout history features include sunk agent tool/execution evidence whose cost is not reconstructed.",
            "Label reveals simulate perfect verification and omit runtime, retry, and infrastructure cost.",
            "No reference patch, hidden test, or LLM judge is used by the selection policies.",
            "Results must not be presented as prospective evidence or a SWE-bench score.",
        ],
        "next_required_evidence": [
            "exact scaffold, prompt, environment, and resource-budget provenance",
            "two independent pinned executions per candidate with disagreement handling",
            "targeted, inherited-suite, repeated-full, and hardened-oracle evidence costs",
            "blinded multi-adjudicator task, candidate, and verifier validity labels",
            "a prospectively frozen policy evaluated on held-out repositories and tasks",
        ],
    }
    atomic_write(report_output, strict_json_dumps(report, indent=2) + "\n")
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire or analyze the checked three-submission matched-rollout "
            "development study; no LLM key is used"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    acquire = subparsers.add_parser("acquire")
    acquire.add_argument("--artifact-dir", type=pathlib.Path, required=True)
    acquire.add_argument("--repositories", type=int, default=DEFAULT_REPOSITORY_COUNT)
    acquire.add_argument(
        "--tasks-per-repository",
        type=int,
        default=DEFAULT_TASKS_PER_REPOSITORY,
    )
    acquire.add_argument("--selection-seed", type=int, default=DEFAULT_SELECTION_SEED)
    acquire.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    acquire.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    acquire.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    acquire.add_argument(
        "--maximum-total-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_BYTES,
    )
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--artifact-dir", type=pathlib.Path, required=True)
    analyze.add_argument("--freeze-output", type=pathlib.Path, required=True)
    analyze.add_argument("--output", type=pathlib.Path, required=True)
    analyze.add_argument("--policy-seed", type=int, default=DEFAULT_POLICY_SEED)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.command == "acquire":
        manifest = acquire_corpus(
            args.artifact_dir,
            repository_count=args.repositories,
            tasks_per_repository=args.tasks_per_repository,
            selection_seed=args.selection_seed,
            workers=args.workers,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            maximum_total_bytes=args.maximum_total_bytes,
        )
        print(strict_json_dumps(manifest["totals"], indent=2))
        return
    report = analyze_study(
        args.artifact_dir,
        freeze_output=args.freeze_output,
        report_output=args.output,
        policy_seed=args.policy_seed,
    )
    print(
        strict_json_dumps(
            {
                "feature_freeze_sha256": report["feature_freeze"]["sha256"],
                "task_count": len(report["cohort"]["selected_instance_ids"]),
                "report_output": str(args.output.absolute()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
