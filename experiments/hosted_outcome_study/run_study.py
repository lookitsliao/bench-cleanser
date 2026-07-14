#!/usr/bin/env python3
"""Acquire and analyze one complete hosted SWE-bench submission.

This is a retrospective development study.  The hosted reports are unchecked
labels from one public submission, not independently reproduced ground truth.
The implementation deliberately keeps report-derived outcomes out of the
reference-free manifest and router inputs.
"""

from __future__ import annotations

import argparse
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
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

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

ACQUISITION_SCHEMA_VERSION = "0.3.0"
STUDY_REPORT_SCHEMA_VERSION = "0.3.0"
STUDY_ID = "openhands-qwen3-coder-hosted-outcome-development-v3"
SUBMISSION_ID = "20250805-openhands-Qwen3-Coder-30B-A3B-Instruct"
SUBMISSION_METADATA_URL = (
    "https://raw.githubusercontent.com/SWE-bench/experiments/"
    "2f15350cd32becc4569e0d826361048555b605c0/evaluation/verified/"
    "20250805_openhands-Qwen3-Coder-30B-A3B-Instruct/metadata.yml"
)
SUBMISSION_METADATA_SHA256 = (
    "54c2a3eacf6f51bcb63b66c2aa1e9d74f3fde5070c29604396a233325a24faaf"
)
SUBMISSION_RESULTS_URL = (
    "https://raw.githubusercontent.com/SWE-bench/experiments/"
    "2f15350cd32becc4569e0d826361048555b605c0/evaluation/verified/"
    "20250805_openhands-Qwen3-Coder-30B-A3B-Instruct/results/results.json"
)
SUBMISSION_RESULTS_SHA256 = (
    "1730846aa8e8f1d91ed6274aee798a02d89ba12a9ef1a66555a3cf12a1a0eac2"
)
PINNED_SUBMISSION_SOURCES = {
    "metadata.yml": (SUBMISSION_METADATA_URL, SUBMISSION_METADATA_SHA256),
    "results.json": (SUBMISSION_RESULTS_URL, SUBMISSION_RESULTS_SHA256),
}
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
CANONICAL_DATASET_SHA256 = (
    "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"
)
CANONICAL_DATASET_PROJECTION_SHA256 = (
    "7524bf30de2473f870b23d407eccd489ec398cf4af8cedf11c9364d708582507"
)
CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT = (
    "0ab58c120939093fea90822f376e1866fc714d1f"
)
CANONICAL_DATASET_PROJECTION_BYTES = 111_075
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
ALLOWED_HOST = "swe-bench-submissions.s3.amazonaws.com"
ROOT_PREFIX = f"verified/{SUBMISSION_ID}/logs/"
EXPECTED_INSTANCE_COUNT = 500
ARTIFACT_NAMES = ("patch.diff", "report.json")
DEFAULT_BUDGET_FRACTIONS = (0.10, 0.25, 0.50, 0.75)
DEFAULT_RANDOM_SEED = 20250805
DEFAULT_WORKERS = 8
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_TOTAL_BYTES = 512 * 1024 * 1024
POLICY_ORDER_CONTRACT = "bench-cleanser-hosted-study-patch-only-order-v3"
TRIAGE_POLICIES = (
    "risk_top_budget",
    "patch_size_top_budget",
    "touches_tests_first",
    "seeded_random",
)
TIE_SENSITIVE_POLICIES = (
    "risk_top_budget",
    "patch_size_top_budget",
    "touches_tests_first",
)
TIE_SENSITIVITY_SEED_COUNT = 16
MAX_LISTING_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = {
    "patch.diff": 32 * 1024 * 1024,
    "report.json": 64 * 1024 * 1024,
}

_S3_NAMESPACE = "http://s3.amazonaws.com/doc/2006-03-01/"
_INSTANCE_RE = re.compile(
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9_.-]*)__"
    r"(?P<repo>[A-Za-z0-9][A-Za-z0-9_.-]*)-(?P<number>[0-9]+)"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_ARTIFACT_RELATIVE_RE = re.compile(
    r"(?P<instance>[A-Za-z0-9_.-]+__(?:[A-Za-z0-9_.-]+)-[0-9]+)/"
    r"(?P<name>patch\.diff|report\.json)"
)


class TransientFetchError(RuntimeError):
    """A bounded retry may be appropriate for this download failure."""


class UnavailableFetchError(RuntimeError):
    """The pinned object is unavailable after a valid, bounded request."""


@dataclass(frozen=True)
class DownloadedObject:
    payload: bytes
    final_url: str


@dataclass(frozen=True)
class ListedObject:
    key: str
    size: int


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
class PolicyCandidate:
    instance_id: str
    repository: str
    candidate_id: str
    manifest_sha256: str
    candidate_risk: float
    router_policy_version: str
    initial_route_action: str
    risk_profile: Mapping[str, Any]
    patch_bytes: int
    patch_sha256: str


@dataclass(frozen=True)
class PatchArtifactIdentity:
    """Sanitized patch-only acquisition identity available before label reveal."""

    instance_id: str
    repository: str
    availability: str
    byte_count: int | None
    sha256: str | None
    error_code: str | None
    base_commit: str | None = None
    environment_setup_commit: str | None = None
    canonical_task_identity_sha256: str | None = None


@dataclass(frozen=True)
class PatchPhaseRow:
    """Patch-derived state frozen before any hosted outcome is decoded."""

    patch_identity: PatchArtifactIdentity
    patch_error: str | None
    reference_free: Mapping[str, Any] | None
    policy_candidate: PolicyCandidate | None


@dataclass(frozen=True)
class Candidate:
    policy_candidate: PolicyCandidate
    report_bytes: int
    report_sha256: str
    hosted_resolved: bool
    patch_exists: bool
    patch_is_none: bool
    patch_successfully_applied: bool
    fail_to_pass_success: int
    fail_to_pass_failure: int
    pass_to_pass_success: int
    pass_to_pass_failure: int
    all_test_group_counts: Mapping[str, Mapping[str, int]]

    @property
    def instance_id(self) -> str:
        return self.policy_candidate.instance_id

    @property
    def repository(self) -> str:
        return self.policy_candidate.repository

    @property
    def candidate_id(self) -> str:
        return self.policy_candidate.candidate_id

    @property
    def manifest_sha256(self) -> str:
        return self.policy_candidate.manifest_sha256


@dataclass(frozen=True)
class FrameRow:
    """One sampling-frame row, including unavailable or malformed candidates."""

    instance_id: str
    repository: str
    patch_availability: str
    report_availability: str
    patch_error: str | None
    report_error: str | None
    artifact_records: Mapping[str, Any]
    policy_candidate: PolicyCandidate | None
    candidate: Candidate | None
    reference_free: Mapping[str, Any] | None
    hosted_outcome: Mapping[str, Any] | None

    @property
    def analyzable(self) -> bool:
        return self.candidate is not None


class DownloadBudget:
    """Thread-safe upper bound on bytes read across successful and failed attempts."""

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
        if amount < 0:
            raise ValueError("download byte accounting cannot be negative")
        with self._lock:
            if self._used + amount > self.limit:
                raise ValueError(
                    f"download byte budget exceeded: limit={self.limit}, "
                    f"attempted={self._used + amount}"
                )
            self._used += amount


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
    """Infer ``owner/repository`` from one confined SWE-bench instance ID."""

    if not isinstance(instance_id, str):
        raise ValueError("instance_id must be a string")
    match = _INSTANCE_RE.fullmatch(instance_id)
    if match is None:
        raise ValueError(f"unconfined or unsupported instance_id {instance_id!r}")
    if any(part in {".", ".."} for part in (match["owner"], match["repo"])):
        raise ValueError(f"instance_id contains a path-like component: {instance_id!r}")
    return f"{match['owner']}/{match['repo']}"


def _frame_listing_url() -> str:
    query = urllib.parse.urlencode({
        "list-type": "2",
        "prefix": ROOT_PREFIX,
        "delimiter": "/",
        "max-keys": "1000",
    })
    return f"https://{ALLOWED_HOST}/?{query}"


def _object_listing_url(continuation_token: str | None = None) -> str:
    query_values = {
        "list-type": "2",
        "prefix": ROOT_PREFIX,
        "max-keys": "1000",
    }
    if continuation_token is not None:
        if (
            not isinstance(continuation_token, str)
            or not continuation_token
            or len(continuation_token) > 2048
            or any(ord(character) < 32 for character in continuation_token)
        ):
            raise ValueError("invalid S3 continuation token")
        query_values["continuation-token"] = continuation_token
    return f"https://{ALLOWED_HOST}/?{urllib.parse.urlencode(query_values)}"


def _artifact_url(instance_id: str, name: str) -> str:
    infer_repository(instance_id)
    if name not in ARTIFACT_NAMES:
        raise ValueError(f"artifact name {name!r} is not allowed")
    return f"https://{ALLOWED_HOST}/{ROOT_PREFIX}{instance_id}/{name}"


def _is_listing_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return parsed.path == "/" and bool(parsed.query)


def _validate_source_url(url: str, *, listing: bool = False) -> None:
    parsed = urllib.parse.urlsplit(url)
    pinned_git_urls = {
        *(identity[0] for identity in PINNED_SUBMISSION_SOURCES.values()),
        CANONICAL_DATASET_RETRIEVAL_URL,
    }
    if url in pinned_git_urls:
        if (
            parsed.scheme != "https"
            or parsed.hostname != "raw.githubusercontent.com"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("pinned Git source URL is not canonical HTTPS")
        return
    if (
        parsed.scheme != "https"
        or parsed.hostname != ALLOWED_HOST
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(f"source URL is outside the exact HTTPS allowlist: {url!r}")
    if listing:
        if parsed.path != "/":
            raise ValueError("listing URL must address the bucket root")
        pairs = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
        if len(pairs) != len({key for key, _ in pairs}):
            raise ValueError("listing URL contains duplicate query fields")
        values = dict(pairs)
        allowed = {"list-type", "prefix", "max-keys", "delimiter", "continuation-token"}
        if set(values) - allowed:
            raise ValueError("listing URL contains unknown query fields")
        if (
            values.get("list-type") != "2"
            or values.get("prefix") != ROOT_PREFIX
            or values.get("max-keys") != "1000"
        ):
            raise ValueError("listing URL does not match the pinned S3 request")
        if "delimiter" in values:
            if values["delimiter"] != "/" or "continuation-token" in values:
                raise ValueError("frame listing query is not canonical")
        else:
            token = values.get("continuation-token")
            if token is not None and (
                not token
                or len(token) > 2048
                or any(ord(character) < 32 for character in token)
            ):
                raise ValueError("object listing continuation token is invalid")
        return
    if parsed.query or parsed.path.startswith("//"):
        raise ValueError("artifact URL cannot contain a query or ambiguous path")
    relative = parsed.path.removeprefix(f"/{ROOT_PREFIX}")
    if relative == parsed.path or _ARTIFACT_RELATIVE_RE.fullmatch(relative) is None:
        raise ValueError("artifact URL does not match the pinned submission prefix")


def _read_response(
    response: Any,
    *,
    maximum_bytes: int,
    budget: DownloadBudget,
) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise ValueError("response has an invalid Content-Length") from exc
        if declared < 0 or declared > maximum_bytes:
            raise ValueError(
                f"response Content-Length {declared} exceeds object bound {maximum_bytes}"
            )
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = response.read(min(64 * 1024, maximum_bytes + 1 - size))
        if not isinstance(chunk, bytes):
            raise ValueError("network response returned non-byte content")
        if not chunk:
            break
        size += len(chunk)
        budget.consume(len(chunk))
        if size > maximum_bytes:
            raise ValueError(f"response exceeded object bound {maximum_bytes}")
        chunks.append(chunk)
    if content_length is not None and size != declared:
        raise ValueError(
            f"response body length {size} contradicts Content-Length {declared}"
        )
    return b"".join(chunks)


def _fetch_once(
    url: str,
    *,
    maximum_bytes: int,
    timeout_seconds: float,
    budget: DownloadBudget,
) -> DownloadedObject:
    """Fetch one exact allowlisted URL and validate any redirect target."""

    listing = _is_listing_url(url)
    _validate_source_url(url, listing=listing)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "bench-cleanser-hosted-outcome-study/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status != 200:
                raise ValueError(f"unexpected HTTP status {status!r} for {url}")
            final_url = response.geturl()
            _validate_source_url(final_url, listing=listing)
            if final_url != url:
                raise ValueError("redirected source URL differs from the pinned URL")
            payload = _read_response(
                response,
                maximum_bytes=maximum_bytes,
                budget=budget,
            )
    except urllib.error.HTTPError as exc:
        if exc.code in {408, 425, 429, 500, 502, 503, 504}:
            raise TransientFetchError(f"transient HTTP {exc.code} for {url}") from exc
        if exc.code in {403, 404, 410}:
            raise UnavailableFetchError(f"http_{exc.code}") from exc
        raise ValueError(f"permanent HTTP {exc.code} for {url}") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise TransientFetchError(f"transient network failure for {url}: {exc}") from exc
    return DownloadedObject(payload=payload, final_url=final_url)


FetchOnce = Callable[..., DownloadedObject]


def _fetch_with_retries(
    url: str,
    *,
    maximum_bytes: int,
    timeout_seconds: float,
    retries: int,
    budget: DownloadBudget,
    fetch_once: FetchOnce = _fetch_once,
    sleep: Callable[[float], None] = time.sleep,
) -> DownloadedObject:
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 1 or retries > 5:
        raise ValueError("retries must be an integer between 1 and 5")
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise ValueError("timeout_seconds must be in (0, 120]")
    for attempt in range(1, retries + 1):
        try:
            return fetch_once(
                url,
                maximum_bytes=maximum_bytes,
                timeout_seconds=timeout_seconds,
                budget=budget,
            )
        except TransientFetchError:
            if attempt == retries:
                raise
            sleep(0.25 * (2 ** (attempt - 1)))
    raise AssertionError("retry loop did not terminate")


def enumerate_instance_ids(
    listing_payload: bytes,
    *,
    expected_count: int = EXPECTED_INSTANCE_COUNT,
) -> tuple[str, ...]:
    """Validate a complete, single-page delimiter listing of the sampling frame."""

    if not isinstance(listing_payload, bytes) or not listing_payload:
        raise ValueError("S3 listing must be non-empty bytes")
    if len(listing_payload) > MAX_LISTING_BYTES:
        raise ValueError("S3 listing exceeds the configured byte bound")
    if b"<!DOCTYPE" in listing_payload.upper() or b"<!ENTITY" in listing_payload.upper():
        raise ValueError("DTD/entity declarations are forbidden in the S3 listing")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 1:
        raise ValueError("expected_count must be a positive integer")
    try:
        root = ET.fromstring(listing_payload)
    except ET.ParseError as exc:
        raise ValueError(f"invalid S3 listing XML: {exc}") from exc
    namespace = f"{{{_S3_NAMESPACE}}}"
    if root.tag != f"{namespace}ListBucketResult":
        raise ValueError("unexpected S3 listing root or XML namespace")

    def required_text(name: str) -> str:
        elements = root.findall(f"{namespace}{name}")
        if len(elements) != 1 or elements[0].text is None:
            raise ValueError(f"S3 listing must contain exactly one {name}")
        return elements[0].text

    if required_text("Name") != BUCKET_NAME:
        raise ValueError("S3 listing bucket name drifted")
    if required_text("Prefix") != ROOT_PREFIX:
        raise ValueError("S3 listing prefix drifted")
    if required_text("Delimiter") != "/":
        raise ValueError("S3 listing delimiter drifted")
    if required_text("IsTruncated") != "false":
        raise ValueError("S3 listing is truncated; the sampling frame is incomplete")
    try:
        key_count = int(required_text("KeyCount"))
        max_keys = int(required_text("MaxKeys"))
    except ValueError as exc:
        raise ValueError("S3 listing has non-integer count fields") from exc
    if max_keys < expected_count or key_count != expected_count:
        raise ValueError(
            f"S3 listing count drift: expected {expected_count}, got {key_count}"
        )
    if root.findall(f"{namespace}Contents"):
        raise ValueError("top-level S3 listing unexpectedly contains object keys")
    if root.findall(f"{namespace}NextContinuationToken"):
        raise ValueError("non-truncated S3 listing cannot carry a continuation token")

    prefixes: list[str] = []
    for item in root.findall(f"{namespace}CommonPrefixes"):
        children = list(item)
        if len(children) != 1 or children[0].tag != f"{namespace}Prefix":
            raise ValueError("malformed CommonPrefixes entry")
        prefix = children[0].text
        if prefix is None or not prefix.startswith(ROOT_PREFIX) or not prefix.endswith("/"):
            raise ValueError("instance prefix escaped the pinned sampling frame")
        instance_id = prefix[len(ROOT_PREFIX) : -1]
        infer_repository(instance_id)
        if prefix != f"{ROOT_PREFIX}{instance_id}/":
            raise ValueError("instance prefix is not canonical")
        prefixes.append(instance_id)
    if len(prefixes) != expected_count:
        raise ValueError(
            f"expected {expected_count} instance prefixes, found {len(prefixes)}"
        )
    if len(prefixes) != len(set(prefixes)):
        raise ValueError("S3 listing contains duplicate instance prefixes")
    if prefixes != sorted(prefixes):
        raise ValueError("S3 instance prefixes are not in canonical lexical order")
    return tuple(prefixes)


def parse_object_listing_page(
    listing_payload: bytes,
    *,
    expected_continuation_token: str | None,
) -> tuple[tuple[ListedObject, ...], str | None]:
    """Parse one strict page from the complete no-delimiter object inventory."""

    if not isinstance(listing_payload, bytes) or not listing_payload:
        raise ValueError("S3 object listing page must be non-empty bytes")
    if len(listing_payload) > MAX_LISTING_BYTES:
        raise ValueError("S3 object listing page exceeds the byte bound")
    upper = listing_payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/entity declarations are forbidden in object listings")
    try:
        root = ET.fromstring(listing_payload)
    except ET.ParseError as exc:
        raise ValueError(f"invalid S3 object listing XML: {exc}") from exc
    namespace = f"{{{_S3_NAMESPACE}}}"
    if root.tag != f"{namespace}ListBucketResult":
        raise ValueError("unexpected object listing root or XML namespace")

    def texts(name: str) -> list[str]:
        result: list[str] = []
        for element in root.findall(f"{namespace}{name}"):
            if element.text is None:
                raise ValueError(f"empty {name} in object listing")
            result.append(element.text)
        return result

    def required(name: str) -> str:
        values = texts(name)
        if len(values) != 1:
            raise ValueError(f"object listing must contain exactly one {name}")
        return values[0]

    if required("Name") != BUCKET_NAME or required("Prefix") != ROOT_PREFIX:
        raise ValueError("object listing source identity drifted")
    if root.findall(f"{namespace}Delimiter") or root.findall(f"{namespace}CommonPrefixes"):
        raise ValueError("object inventory must be a no-delimiter listing")
    if required("MaxKeys") != "1000":
        raise ValueError("object listing MaxKeys drifted")
    continuation_values = texts("ContinuationToken")
    if expected_continuation_token is None:
        if continuation_values:
            raise ValueError("initial object listing unexpectedly echoes a token")
    elif continuation_values != [expected_continuation_token]:
        raise ValueError("object listing continuation token chain drifted")

    truncated_text = required("IsTruncated")
    if truncated_text not in {"true", "false"}:
        raise ValueError("object listing IsTruncated must be true or false")
    next_tokens = texts("NextContinuationToken")
    if truncated_text == "true":
        if len(next_tokens) != 1 or not next_tokens[0] or len(next_tokens[0]) > 2048:
            raise ValueError("truncated object listing lacks one valid next token")
        next_token: str | None = next_tokens[0]
    else:
        if next_tokens:
            raise ValueError("final object listing cannot carry a next token")
        next_token = None

    objects: list[ListedObject] = []
    for index, content in enumerate(root.findall(f"{namespace}Contents")):
        key_elements = content.findall(f"{namespace}Key")
        size_elements = content.findall(f"{namespace}Size")
        if (
            len(key_elements) != 1
            or key_elements[0].text is None
            or len(size_elements) != 1
            or size_elements[0].text is None
        ):
            raise ValueError(f"malformed object listing entry {index}")
        key = key_elements[0].text
        if not key.startswith(ROOT_PREFIX):
            raise ValueError("listed object escaped the pinned root prefix")
        try:
            size = int(size_elements[0].text)
        except ValueError as exc:
            raise ValueError("listed object has a non-integer size") from exc
        if size < 0:
            raise ValueError("listed object has a negative size")
        objects.append(ListedObject(key=key, size=size))
    try:
        key_count = int(required("KeyCount"))
    except ValueError as exc:
        raise ValueError("object listing KeyCount is not an integer") from exc
    if key_count != len(objects):
        raise ValueError("object listing KeyCount contradicts Contents")
    keys = [item.key for item in objects]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("object listing page keys are duplicate or non-canonical")
    return tuple(objects), next_token


def enumerate_object_inventory(
    *,
    budget: DownloadBudget,
    timeout_seconds: float,
    retries: int,
    fetch_once: FetchOnce,
    sleep: Callable[[float], None],
) -> tuple[dict[str, ListedObject], list[dict[str, Any]], list[bytes]]:
    """Fetch every page in the pinned object inventory with a strict token chain."""

    inventory: dict[str, ListedObject] = {}
    pages: list[dict[str, Any]] = []
    page_payloads: list[bytes] = []
    continuation_token: str | None = None
    seen_tokens: set[str] = set()
    for page_index in range(1, 101):
        url = _object_listing_url(continuation_token)
        downloaded = _fetch_with_retries(
            url,
            maximum_bytes=MAX_LISTING_BYTES,
            timeout_seconds=timeout_seconds,
            retries=retries,
            budget=budget,
            fetch_once=fetch_once,
            sleep=sleep,
        )
        objects, next_token = parse_object_listing_page(
            downloaded.payload,
            expected_continuation_token=continuation_token,
        )
        if objects and inventory and objects[0].key <= max(inventory):
            raise ValueError("object listing page order overlaps or regresses")
        for item in objects:
            if item.key in inventory:
                raise ValueError(f"duplicate key across object listing pages: {item.key}")
            inventory[item.key] = item
        pages.append({
            "page_index": page_index,
            "source_url": url,
            "bytes": len(downloaded.payload),
            "sha256": _sha256(downloaded.payload),
            "object_count": len(objects),
        })
        page_payloads.append(downloaded.payload)
        if next_token is None:
            return inventory, pages, page_payloads
        if next_token in seen_tokens:
            raise ValueError("object listing continuation token cycle detected")
        seen_tokens.add(next_token)
        continuation_token = next_token
    raise ValueError("object listing exceeded the 100-page safety bound")


def _safe_artifact_path(root: pathlib.Path, instance_id: str, name: str) -> pathlib.Path:
    infer_repository(instance_id)
    if name not in ARTIFACT_NAMES:
        raise ValueError(f"artifact name {name!r} is not allowed")
    path = root / instance_id / name
    if path.parent.parent != root:
        raise ValueError("artifact path escaped its acquisition root")
    return path


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
    lock = target.with_name(f".{target.name}.lock")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(lock, flags, 0o600)
    return descriptor, lock


def _validate_pinned_submission_sources_without_outcomes(
    payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    """Validate pinned bytes and non-outcome metadata without decoding results.

    ``results.json`` is deliberately treated as opaque authenticated-by-digest
    bytes here. Its category lists are not decoded until the patch-only feature
    table and every base/sensitivity policy permutation have been frozen.
    """

    if set(payloads) != set(PINNED_SUBMISSION_SOURCES):
        raise ValueError("pinned submission source set is incomplete")
    for name, payload in payloads.items():
        expected_digest = PINNED_SUBMISSION_SOURCES[name][1]
        if not payload or _sha256(payload) != expected_digest:
            raise ValueError(f"pinned submission source digest drifted: {name}")
    try:
        metadata = yaml.safe_load(payloads["metadata.yml"].decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid pinned metadata YAML: {exc}") from exc
    metadata_root = _object(metadata, "submission metadata")
    tags = _object(metadata_root.get("tags"), "submission metadata.tags")
    system = _object(tags.get("system"), "submission metadata.tags.system")
    assets = _object(metadata_root.get("assets"), "submission metadata.assets")
    if tags.get("checked") is not False or system.get("attempts") != 1:
        raise ValueError("pinned metadata checked/attempts semantics drifted")
    if assets.get("logs") != f"s3://{BUCKET_NAME}/{ROOT_PREFIX.removesuffix('/')}" or assets.get(
        "trajs"
    ) != f"s3://{BUCKET_NAME}/verified/{SUBMISSION_ID}/trajs":
        raise ValueError("pinned metadata S3 asset identity drifted")

    return {
        "submission_checked": False,
        "attempts": 1,
        "official_results_decode": (
            "deferred_until_after_patch_only_feature_and_policy_order_freeze"
        ),
    }


def _parse_canonical_dataset_projection(
    payload: bytes,
    *,
    expected_count: int,
) -> tuple[tuple[CanonicalTaskIdentity, ...], dict[str, Any]]:
    """Read only deployable task identity columns from the canonical parquet.

    The gold patch, test patch, problem statement, hints, and oracle columns are
    deliberately outside the selected Arrow projection and never enter the
    patch-only feature builder.
    """

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
    commits_by_repository: dict[str, set[str]] = defaultdict(set)
    instances_by_repo_commit: dict[tuple[str, str], list[str]] = defaultdict(list)
    repositories_by_commit: dict[str, set[str]] = defaultdict(set)
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
            raise ValueError(f"canonical dataset base_commit is not lowercase 40-hex: {instance_id}")
        if _COMMIT_RE.fullmatch(environment_commit) is None:
            raise ValueError(
                "canonical dataset environment_setup_commit is not lowercase 40-hex: "
                f"{instance_id}"
            )
        commits_by_repository[repository].add(base_commit)
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
        {
            "base_commit": commit,
            "repositories": sorted(repositories),
        }
        for commit, repositories in sorted(repositories_by_commit.items())
        if len(repositories) > 1
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
        for (repository, commit), instance_ids in sorted(
            instances_by_repo_commit.items()
        )
        if len(instance_ids) > 1
    ]
    projection_rows = [identity.to_dict() for identity in identities]
    projection_payload = (
        strict_json_dumps(projection_rows, indent=2) + "\n"
    ).encode()
    summary = {
        "projection_contract": "instance-repo-base-environment-commit-v1",
        "projection_fields": list(CANONICAL_DATASET_PROJECTION_FIELDS),
        "projection_row_count": len(projection_rows),
        "projection_bytes": len(projection_payload),
        "projection_sha256": _sha256(projection_payload),
        "unique_instance_count": len(seen_ids),
        "repository_count": len(commits_by_repository),
        "unique_repository_base_commit_pair_count": len(instances_by_repo_commit),
        "duplicate_repository_base_commit_pairs": duplicate_pairs,
        "cross_repository_base_commit_collision_count": 0,
    }
    return tuple(identities), summary


def _crosscheck_canonical_dataset_frame(
    identities: Sequence[CanonicalTaskIdentity],
    instance_ids: Sequence[str],
) -> dict[str, Any]:
    dataset_by_id = {identity.instance_id: identity for identity in identities}
    frame = set(instance_ids)
    dataset = set(dataset_by_id)
    missing_from_dataset = sorted(frame - dataset)
    dataset_only = sorted(dataset - frame)
    if missing_from_dataset or dataset_only:
        raise ValueError(
            "canonical dataset/S3 frame identity mismatch: "
            f"missing_from_dataset={missing_from_dataset}, dataset_only={dataset_only}"
        )
    repository_mismatches = [
        instance_id
        for instance_id in sorted(frame)
        if dataset_by_id[instance_id].repository != infer_repository(instance_id)
    ]
    if repository_mismatches:
        raise ValueError(
            "canonical dataset/S3 repository mismatch: "
            f"{repository_mismatches}"
        )
    return {
        "status": "exact_match",
        "s3_instance_count": len(frame),
        "canonical_dataset_instance_count": len(dataset),
        "instance_set_match": True,
        "repository_mismatch_count": 0,
        "base_commit_valid_count": len(dataset),
        "environment_setup_commit_valid_count": len(dataset),
    }


def _validate_pinned_canonical_dataset(
    payload: bytes,
) -> tuple[tuple[CanonicalTaskIdentity, ...], dict[str, Any]]:
    if len(payload) != CANONICAL_DATASET_BYTES or _sha256(payload) != (
        CANONICAL_DATASET_SHA256
    ):
        raise ValueError("pinned canonical SWE-bench Verified parquet bytes drifted")
    identities, projection = _parse_canonical_dataset_projection(
        payload,
        expected_count=EXPECTED_INSTANCE_COUNT,
    )
    if (
        projection["projection_bytes"] != CANONICAL_DATASET_PROJECTION_BYTES
        or projection["projection_sha256"]
        != CANONICAL_DATASET_PROJECTION_SHA256
        or projection["repository_count"] != 12
        or projection["unique_repository_base_commit_pair_count"] != 499
        or projection["cross_repository_base_commit_collision_count"] != 0
        or projection["duplicate_repository_base_commit_pairs"]
        != [
            {
                "repository": "django/django",
                "base_commit": CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT,
                "instance_ids": [
                    "django__django-15268",
                    "django__django-15278",
                ],
            }
        ]
    ):
        raise ValueError("pinned canonical dataset identity projection drifted")
    return identities, projection


def _canonical_dataset_record(
    payload: bytes,
    downloaded: DownloadedObject,
    identities: Sequence[CanonicalTaskIdentity],
    projection_summary: Mapping[str, Any],
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
        "bytes": len(payload),
        "sha256": _sha256(payload),
        "projection": dict(projection_summary),
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


def _parse_pinned_submission_results(payload: bytes) -> dict[str, list[str]]:
    """Decode official result categories only in the post-freeze reveal phase."""

    try:
        results_value = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid pinned results JSON: {exc}") from exc
    results = _object(results_value, "submission results")
    _exact_fields(results, {"no_generation", "no_logs", "resolved"}, "submission results")
    normalized: dict[str, list[str]] = {}
    seen: set[str] = set()
    for category in ("no_generation", "no_logs", "resolved"):
        values = _array(results[category], f"submission results.{category}")
        if any(not isinstance(value, str) for value in values):
            raise ValueError(f"submission results.{category} must contain instance IDs")
        typed_values = [str(value) for value in values]
        if typed_values != sorted(typed_values) or len(typed_values) != len(set(typed_values)):
            raise ValueError(f"submission results.{category} is duplicate or unsorted")
        for instance_id in typed_values:
            infer_repository(instance_id)
        if seen & set(typed_values):
            raise ValueError("pinned results categories overlap")
        seen.update(typed_values)
        normalized[category] = typed_values
    return normalized


def acquire_corpus(
    artifact_root: pathlib.Path,
    *,
    expected_count: int = EXPECTED_INSTANCE_COUNT,
    workers: int = DEFAULT_WORKERS,
    retries: int = DEFAULT_RETRIES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    maximum_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    fetch_once: FetchOnce = _fetch_once,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Acquire the exact frame, preserving missing/unavailable objects explicitly."""

    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 16:
        raise ValueError("workers must be an integer between 1 and 16")
    artifact_root = artifact_root.absolute()
    artifact_root.parent.mkdir(parents=True, exist_ok=True)
    if artifact_root.exists() or artifact_root.is_symlink():
        raise FileExistsError(
            f"acquisition target already exists; choose a new directory: {artifact_root}"
        )
    lock_descriptor: int | None = None
    lock_path: pathlib.Path | None = None
    staging: pathlib.Path | None = None
    budget = DownloadBudget(maximum_total_bytes)
    try:
        lock_descriptor, lock_path = _acquisition_lock(artifact_root)
        staging = pathlib.Path(
            tempfile.mkdtemp(prefix=f".{artifact_root.name}.staging.", dir=artifact_root.parent)
        )
        staging_root = staging
        pinned_source_records: list[dict[str, Any]] = []
        pinned_metadata_semantics: dict[str, Any] | None = None
        canonical_dataset_download: DownloadedObject | None = None
        canonical_dataset_identities: tuple[CanonicalTaskIdentity, ...] = ()
        canonical_dataset_projection: dict[str, Any] | None = None
        if expected_count == EXPECTED_INSTANCE_COUNT:
            pinned_payloads: dict[str, bytes] = {}
            for name, (url, expected_digest) in PINNED_SUBMISSION_SOURCES.items():
                downloaded_source = _fetch_with_retries(
                    url,
                    maximum_bytes=1024 * 1024,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    budget=budget,
                    fetch_once=fetch_once,
                    sleep=sleep,
                )
                if _sha256(downloaded_source.payload) != expected_digest:
                    raise ValueError(f"pinned submission source digest drifted: {name}")
                pinned_payloads[name] = downloaded_source.payload
                _atomic_write_bytes(
                    staging_root / f"submission-{name}",
                    downloaded_source.payload,
                )
                pinned_source_records.append({
                    "name": name,
                    "source_url": url,
                    "response_url": downloaded_source.final_url,
                    "bytes": len(downloaded_source.payload),
                    "sha256": expected_digest,
                })
            pinned_metadata_semantics = (
                _validate_pinned_submission_sources_without_outcomes(
                    pinned_payloads
                )
            )
            canonical_dataset_download = _fetch_with_retries(
                CANONICAL_DATASET_RETRIEVAL_URL,
                maximum_bytes=CANONICAL_DATASET_BYTES,
                timeout_seconds=timeout_seconds,
                retries=retries,
                budget=budget,
                fetch_once=fetch_once,
                sleep=sleep,
            )
            (
                canonical_dataset_identities,
                canonical_dataset_projection,
            ) = _validate_pinned_canonical_dataset(
                canonical_dataset_download.payload
            )
            _atomic_write_bytes(
                staging_root / CANONICAL_DATASET_LOCAL_NAME,
                canonical_dataset_download.payload,
            )
        listing_url = _frame_listing_url()
        listing = _fetch_with_retries(
            listing_url,
            maximum_bytes=MAX_LISTING_BYTES,
            timeout_seconds=timeout_seconds,
            retries=retries,
            budget=budget,
            fetch_once=fetch_once,
            sleep=sleep,
        )
        instance_ids = enumerate_instance_ids(
            listing.payload,
            expected_count=expected_count,
        )
        canonical_dataset: dict[str, Any] | None = None
        if expected_count == EXPECTED_INSTANCE_COUNT:
            if (
                canonical_dataset_download is None
                or canonical_dataset_projection is None
            ):
                raise AssertionError("canonical dataset acquisition state is incomplete")
            frame_crosscheck = _crosscheck_canonical_dataset_frame(
                canonical_dataset_identities,
                instance_ids,
            )
            canonical_dataset = _canonical_dataset_record(
                canonical_dataset_download.payload,
                canonical_dataset_download,
                canonical_dataset_identities,
                canonical_dataset_projection,
                frame_crosscheck,
            )
        _atomic_write_bytes(staging_root / "listing.xml", listing.payload)

        inventory, inventory_pages, inventory_payloads = enumerate_object_inventory(
            budget=budget,
            timeout_seconds=timeout_seconds,
            retries=retries,
            fetch_once=fetch_once,
            sleep=sleep,
        )
        for page, payload in zip(inventory_pages, inventory_payloads, strict=True):
            _atomic_write_bytes(
                staging_root / f"object-listing-page-{page['page_index']:04d}.xml",
                payload,
            )

        frame = set(instance_ids)
        selected_inventory: dict[tuple[str, str], ListedObject] = {}
        for key, listed in inventory.items():
            relative = key.removeprefix(ROOT_PREFIX)
            if relative == key or "/" not in relative:
                raise ValueError(f"listed key is not nested under an instance: {key!r}")
            instance_id, remainder = relative.split("/", 1)
            infer_repository(instance_id)
            if instance_id not in frame:
                raise ValueError(
                    f"object inventory contains an instance outside the 500-prefix frame: "
                    f"{instance_id}"
                )
            if remainder in ARTIFACT_NAMES:
                identity = (instance_id, remainder)
                if identity in selected_inventory:
                    raise ValueError(f"duplicate selected object key {key!r}")
                if listed.size > MAX_ARTIFACT_BYTES[remainder]:
                    raise ValueError(f"listed object exceeds its byte bound: {key!r}")
                selected_inventory[identity] = listed

        identities = [
            (instance_id, name)
            for instance_id in instance_ids
            for name in ARTIFACT_NAMES
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate artifact identity in acquisition plan")

        def download(identity: tuple[str, str]) -> dict[str, Any]:
            instance_id, name = identity
            url = _artifact_url(instance_id, name)
            listed = selected_inventory.get(identity)
            base = {
                "instance_id": instance_id,
                "repository": infer_repository(instance_id),
                "artifact_name": name,
                "source_url": url,
                "listed_bytes": listed.size if listed is not None else None,
            }
            if listed is None:
                return {
                    **base,
                    "availability": "missing_from_complete_object_listing",
                    "response_url": None,
                    "bytes": None,
                    "sha256": None,
                    "error_code": "not_listed",
                }
            try:
                downloaded = _fetch_with_retries(
                    url,
                    maximum_bytes=MAX_ARTIFACT_BYTES[name],
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    budget=budget,
                    fetch_once=fetch_once,
                    sleep=sleep,
                )
            except UnavailableFetchError as exc:
                return {
                    **base,
                    "availability": "download_error",
                    "response_url": None,
                    "bytes": None,
                    "sha256": None,
                    "error_code": str(exc),
                }
            except TransientFetchError:
                return {
                    **base,
                    "availability": "download_error",
                    "response_url": None,
                    "bytes": None,
                    "sha256": None,
                    "error_code": "retry_limit_exhausted",
                }
            if not downloaded.payload:
                raise ValueError(f"empty hosted artifact: {instance_id}/{name}")
            if len(downloaded.payload) != listed.size:
                raise ValueError(
                    f"downloaded byte length contradicts complete object listing for "
                    f"{instance_id}/{name}"
                )
            path = _safe_artifact_path(staging_root, instance_id, name)
            _atomic_write_bytes(path, downloaded.payload)
            return {
                **base,
                "availability": "downloaded",
                "response_url": downloaded.final_url,
                "bytes": len(downloaded.payload),
                "sha256": _sha256(downloaded.payload),
                "error_code": None,
            }

        objects: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(download, identity): identity for identity in identities}
            for future in as_completed(futures):
                identity = futures[future]
                try:
                    objects.append(future.result())
                except Exception as exc:
                    for pending in futures:
                        pending.cancel()
                    raise RuntimeError(
                        f"acquisition failed for {identity[0]}/{identity[1]}: {exc}"
                    ) from exc
        objects.sort(key=lambda item: (item["instance_id"], item["artifact_name"]))
        successful_bytes = sum(
            item["bytes"] for item in objects if item["bytes"] is not None
        )
        downloaded_count = sum(item["availability"] == "downloaded" for item in objects)
        missing_count = sum(
            item["availability"] == "missing_from_complete_object_listing"
            for item in objects
        )
        error_count = sum(item["availability"] == "download_error" for item in objects)
        manifest = {
            "schema_version": ACQUISITION_SCHEMA_VERSION,
            "study_id": STUDY_ID,
            "source": {
                "bucket": BUCKET_NAME,
                "host": ALLOWED_HOST,
                "submission_id": SUBMISSION_ID,
                "submission_metadata_url": SUBMISSION_METADATA_URL,
                "submission_metadata_sha256": SUBMISSION_METADATA_SHA256,
                "submission_attempts": 1,
                "root_prefix": ROOT_PREFIX,
                "submission_checked": False,
                "listing_url": listing_url,
                "listing_bytes": len(listing.payload),
                "listing_sha256": _sha256(listing.payload),
                "expected_instance_count": expected_count,
                "observed_instance_count": len(instance_ids),
                "artifact_allowlist": list(ARTIFACT_NAMES),
                "object_listing_pages": inventory_pages,
                "listed_object_count": len(inventory),
                "pinned_submission_sources": pinned_source_records,
                "pinned_submission_metadata_semantics": pinned_metadata_semantics,
                "canonical_dataset": canonical_dataset,
                "official_results_parse_policy": (
                    "post_patch_only_feature_and_all_policy_order_freeze"
                    if expected_count == EXPECTED_INSTANCE_COUNT
                    else None
                ),
            },
            "objects": objects,
            "totals": {
                "object_count": len(objects),
                "downloaded_object_count": downloaded_count,
                "missing_object_count": missing_count,
                "download_error_count": error_count,
                "successful_artifact_bytes": successful_bytes,
                "network_bytes_including_retries_and_listing": budget.used,
            },
        }
        atomic_write(
            staging_root / "source_manifest.json",
            strict_json_dumps(manifest, indent=2) + "\n",
        )
        if artifact_root.exists() or artifact_root.is_symlink():
            raise FileExistsError("acquisition target appeared during publication")
        os.replace(staging_root, artifact_root)
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


def _validate_acquisition_manifest(
    artifact_root: pathlib.Path,
    *,
    expected_count: int,
) -> dict[str, Any]:
    manifest_path = artifact_root / "source_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("source_manifest.json must be a regular non-symlink file")
    try:
        decoded = strict_json_loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid acquisition manifest: {exc}") from exc
    manifest = _object(decoded, "source_manifest")
    _exact_fields(
        manifest,
        {"schema_version", "study_id", "source", "objects", "totals"},
        "source_manifest",
    )
    if manifest["schema_version"] != ACQUISITION_SCHEMA_VERSION:
        raise ValueError("unsupported acquisition manifest schema")
    if manifest["study_id"] != STUDY_ID:
        raise ValueError("acquisition manifest study_id drifted")
    source = _object(manifest["source"], "source_manifest.source")
    _exact_fields(
        source,
        {
            "bucket",
            "host",
            "submission_id",
            "submission_metadata_url",
            "submission_metadata_sha256",
            "submission_attempts",
            "root_prefix",
            "submission_checked",
            "listing_url",
            "listing_bytes",
            "listing_sha256",
            "expected_instance_count",
            "observed_instance_count",
            "artifact_allowlist",
            "object_listing_pages",
            "listed_object_count",
            "pinned_submission_sources",
            "pinned_submission_metadata_semantics",
            "canonical_dataset",
            "official_results_parse_policy",
        },
        "source_manifest.source",
    )
    if (
        source["bucket"] != BUCKET_NAME
        or source["host"] != ALLOWED_HOST
        or source["submission_id"] != SUBMISSION_ID
        or source["submission_metadata_url"] != SUBMISSION_METADATA_URL
        or source["submission_metadata_sha256"] != SUBMISSION_METADATA_SHA256
        or source["submission_attempts"] != 1
        or source["root_prefix"] != ROOT_PREFIX
        or source["submission_checked"] is not False
        or source["listing_url"] != _frame_listing_url()
        or source["artifact_allowlist"] != list(ARTIFACT_NAMES)
        or source["expected_instance_count"] != expected_count
        or source["observed_instance_count"] != expected_count
    ):
        raise ValueError("acquisition source identity or sampling frame drifted")
    listing_path = artifact_root / "listing.xml"
    if listing_path.is_symlink() or not listing_path.is_file():
        raise ValueError("listing.xml must be a regular non-symlink file")
    listing = listing_path.read_bytes()
    if len(listing) != _integer(source["listing_bytes"], "source.listing_bytes"):
        raise ValueError("listing.xml byte length drifted")
    listing_digest = _string(source["listing_sha256"], "source.listing_sha256")
    if _SHA256_RE.fullmatch(listing_digest) is None or _sha256(listing) != listing_digest:
        raise ValueError("listing.xml digest drifted")
    instance_ids = enumerate_instance_ids(listing, expected_count=expected_count)

    canonical_dataset_record = source["canonical_dataset"]
    canonical_dataset_bytes = 0
    if expected_count == EXPECTED_INSTANCE_COUNT:
        canonical_dataset_value = _object(
            canonical_dataset_record,
            "source.canonical_dataset",
        )
        dataset_path = artifact_root / CANONICAL_DATASET_LOCAL_NAME
        if dataset_path.is_symlink() or not dataset_path.is_file():
            raise ValueError("canonical dataset parquet must be a regular file")
        dataset_payload = dataset_path.read_bytes()
        identities, projection = _validate_pinned_canonical_dataset(dataset_payload)
        frame_crosscheck = _crosscheck_canonical_dataset_frame(
            identities,
            instance_ids,
        )
        expected_dataset_record = _canonical_dataset_record(
            dataset_payload,
            DownloadedObject(
                payload=dataset_payload,
                final_url=CANONICAL_DATASET_RETRIEVAL_URL,
            ),
            identities,
            projection,
            frame_crosscheck,
        )
        if canonical_dataset_value != expected_dataset_record:
            raise ValueError("canonical dataset manifest identity or cross-check drifted")
        canonical_dataset_bytes = len(dataset_payload)
    elif canonical_dataset_record is not None:
        raise ValueError("non-production fixture frame cannot claim canonical dataset evidence")

    inventory: dict[str, ListedObject] = {}
    expected_token: str | None = None
    page_records = _array(source["object_listing_pages"], "source.object_listing_pages")
    if not page_records or len(page_records) > 100:
        raise ValueError("object listing page manifest is empty or exceeds its bound")
    for index, raw_page in enumerate(page_records, start=1):
        field = f"source.object_listing_pages[{index - 1}]"
        page = _object(raw_page, field)
        _exact_fields(
            page,
            {"page_index", "source_url", "bytes", "sha256", "object_count"},
            field,
        )
        expected_url = _object_listing_url(expected_token)
        if page["page_index"] != index or page["source_url"] != expected_url:
            raise ValueError("object listing page chain or index drifted")
        page_path = artifact_root / f"object-listing-page-{index:04d}.xml"
        if page_path.is_symlink() or not page_path.is_file():
            raise ValueError(f"object listing page must be a regular file: {page_path}")
        payload = page_path.read_bytes()
        digest = _string(page["sha256"], f"{field}.sha256")
        if (
            len(payload) != _integer(page["bytes"], f"{field}.bytes")
            or _SHA256_RE.fullmatch(digest) is None
            or _sha256(payload) != digest
        ):
            raise ValueError(f"object listing page {index} bytes or digest drifted")
        page_items, next_token = parse_object_listing_page(
            payload,
            expected_continuation_token=expected_token,
        )
        if len(page_items) != page["object_count"]:
            raise ValueError(f"object listing page {index} count drifted")
        for page_item in page_items:
            if page_item.key in inventory:
                raise ValueError(
                    f"duplicate key across preserved object pages: {page_item.key}"
                )
            inventory[page_item.key] = page_item
        if next_token is None and index != len(page_records):
            raise ValueError("object listing manifest continues after a final page")
        if next_token is not None and index == len(page_records):
            raise ValueError("object listing manifest stops before the final page")
        expected_token = next_token
    if expected_token is not None:
        raise ValueError("object listing token chain remains truncated")
    if source["listed_object_count"] != len(inventory):
        raise ValueError("listed_object_count drifted")

    pinned_records = _array(
        source["pinned_submission_sources"],
        "source.pinned_submission_sources",
    )
    if expected_count == EXPECTED_INSTANCE_COUNT:
        if len(pinned_records) != len(PINNED_SUBMISSION_SOURCES):
            raise ValueError("pinned submission source records are incomplete")
        pinned_payloads: dict[str, bytes] = {}
        for index, raw_record in enumerate(pinned_records):
            field = f"source.pinned_submission_sources[{index}]"
            record = _object(raw_record, field)
            _exact_fields(
                record,
                {"name", "source_url", "response_url", "bytes", "sha256"},
                field,
            )
            name = _string(record["name"], f"{field}.name")
            if name not in PINNED_SUBMISSION_SOURCES:
                raise ValueError(f"unexpected pinned source name {name!r}")
            url, digest = PINNED_SUBMISSION_SOURCES[name]
            if (
                record["source_url"] != url
                or record["response_url"] != url
                or record["sha256"] != digest
            ):
                raise ValueError(f"pinned source identity drift for {name}")
            path = artifact_root / f"submission-{name}"
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"pinned source must be a regular file: {path}")
            payload = path.read_bytes()
            if len(payload) != record["bytes"] or _sha256(payload) != digest:
                raise ValueError(f"pinned source bytes drift for {name}")
            pinned_payloads[name] = payload
        metadata_semantics = _validate_pinned_submission_sources_without_outcomes(
            pinned_payloads
        )
        if source["pinned_submission_metadata_semantics"] != metadata_semantics:
            raise ValueError("pinned submission metadata summary drifted")
        if source["official_results_parse_policy"] != (
            "post_patch_only_feature_and_all_policy_order_freeze"
        ):
            raise ValueError("official results parse policy drifted")
    elif (
        pinned_records
        or source["pinned_submission_metadata_semantics"] is not None
        or source["official_results_parse_policy"] is not None
    ):
        raise ValueError("non-production fixture frame cannot claim pinned source evidence")

    frame = set(instance_ids)
    for key in inventory:
        relative = key.removeprefix(ROOT_PREFIX)
        if relative == key or "/" not in relative:
            raise ValueError("preserved object inventory contains an unconfined key")
        instance_id = relative.split("/", 1)[0]
        infer_repository(instance_id)
        if instance_id not in frame:
            raise ValueError("preserved inventory escaped the exact prefix frame")

    objects = _array(manifest["objects"], "source_manifest.objects")
    if len(objects) != expected_count * len(ARTIFACT_NAMES):
        raise ValueError("acquisition manifest does not contain the complete artifact frame")
    expected_identities = {
        (instance_id, name)
        for instance_id in instance_ids
        for name in ARTIFACT_NAMES
    }
    seen: set[tuple[str, str]] = set()
    successful_bytes = 0
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(objects):
        field = f"source_manifest.objects[{index}]"
        item = _object(raw, field)
        _exact_fields(
            item,
            {
                "instance_id",
                "repository",
                "artifact_name",
                "source_url",
                "listed_bytes",
                "availability",
                "response_url",
                "bytes",
                "sha256",
                "error_code",
            },
            field,
        )
        instance_id = _string(item["instance_id"], f"{field}.instance_id")
        name = _string(item["artifact_name"], f"{field}.artifact_name")
        identity = (instance_id, name)
        if identity not in expected_identities or identity in seen:
            raise ValueError(f"unexpected or duplicate artifact identity {identity!r}")
        seen.add(identity)
        if item["repository"] != infer_repository(instance_id):
            raise ValueError(f"repository inference drift for {instance_id}")
        expected_url = _artifact_url(instance_id, name)
        if item["source_url"] != expected_url:
            raise ValueError(f"source URL drift for {instance_id}/{name}")
        listed = inventory.get(f"{ROOT_PREFIX}{instance_id}/{name}")
        if item["listed_bytes"] != (listed.size if listed is not None else None):
            raise ValueError(f"listed byte identity drift for {instance_id}/{name}")
        path = _safe_artifact_path(artifact_root, instance_id, name)
        availability = item["availability"]
        if availability == "downloaded":
            if listed is None or item["response_url"] != expected_url or item["error_code"] is not None:
                raise ValueError(f"downloaded artifact identity drift for {instance_id}/{name}")
            byte_count = _integer(item["bytes"], f"{field}.bytes")
            digest = _string(item["sha256"], f"{field}.sha256")
            if byte_count != listed.size or _SHA256_RE.fullmatch(digest) is None:
                raise ValueError(f"invalid downloaded metadata for {instance_id}/{name}")
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"artifact must be a regular non-symlink file: {path}")
            payload = path.read_bytes()
            if len(payload) != byte_count or _sha256(payload) != digest:
                raise ValueError(f"artifact bytes or digest drift for {instance_id}/{name}")
            successful_bytes += byte_count
        elif availability == "missing_from_complete_object_listing":
            if (
                listed is not None
                or item["response_url"] is not None
                or item["bytes"] is not None
                or item["sha256"] is not None
                or item["error_code"] != "not_listed"
                or path.exists()
                or path.is_symlink()
            ):
                raise ValueError(f"missing-object record drift for {instance_id}/{name}")
        elif availability == "download_error":
            error_code = item["error_code"]
            if (
                listed is None
                or item["response_url"] is not None
                or item["bytes"] is not None
                or item["sha256"] is not None
                or error_code not in {"http_403", "http_404", "http_410", "retry_limit_exhausted"}
                or path.exists()
                or path.is_symlink()
            ):
                raise ValueError(f"download-error record drift for {instance_id}/{name}")
        else:
            raise ValueError(f"unsupported artifact availability {availability!r}")
        normalized.append(item)
    if seen != expected_identities:
        raise ValueError("acquisition manifest is missing expected artifacts")
    allowed_files = {
        artifact_root / "source_manifest.json",
        artifact_root / "listing.xml",
        *(
            [artifact_root / CANONICAL_DATASET_LOCAL_NAME]
            if expected_count == EXPECTED_INSTANCE_COUNT
            else []
        ),
        *(
            artifact_root / f"object-listing-page-{index:04d}.xml"
            for index in range(1, len(page_records) + 1)
        ),
        *(
            artifact_root / f"submission-{record['name']}"
            for record in pinned_records
        ),
        *(
            _safe_artifact_path(
                artifact_root,
                record["instance_id"],
                record["artifact_name"],
            )
            for record in normalized
            if record["availability"] == "downloaded"
        ),
    }
    for path in artifact_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"acquisition tree cannot contain symlinks: {path}")
        if path.is_file() and path not in allowed_files:
            raise ValueError(f"unexpected file in acquisition tree: {path}")
        if path.is_dir():
            relative_path = path.relative_to(artifact_root)
            if len(relative_path.parts) != 1 or relative_path.name not in frame:
                raise ValueError(f"unexpected directory in acquisition tree: {path}")
    totals = _object(manifest["totals"], "source_manifest.totals")
    _exact_fields(
        totals,
        {
            "object_count",
            "downloaded_object_count",
            "missing_object_count",
            "download_error_count",
            "successful_artifact_bytes",
            "network_bytes_including_retries_and_listing",
        },
        "source_manifest.totals",
    )
    if (
        totals["object_count"] != len(objects)
        or totals["downloaded_object_count"]
        != sum(item["availability"] == "downloaded" for item in objects)
        or totals["missing_object_count"]
        != sum(
            item["availability"] == "missing_from_complete_object_listing"
            for item in objects
        )
        or totals["download_error_count"]
        != sum(item["availability"] == "download_error" for item in objects)
        or totals["successful_artifact_bytes"] != successful_bytes
        or _integer(
            totals["network_bytes_including_retries_and_listing"],
            "source_manifest.totals.network_bytes_including_retries_and_listing",
        )
        < successful_bytes
        + len(listing)
        + canonical_dataset_bytes
        + sum(page["bytes"] for page in page_records)
        + sum(record["bytes"] for record in pinned_records)
    ):
        raise ValueError("acquisition byte totals drifted")
    return manifest


def _test_group_counts(
    report: Mapping[str, Any],
    instance_id: str,
) -> dict[str, dict[str, int]]:
    tests = _object(report.get("tests_status"), f"report[{instance_id}].tests_status")
    expected_groups = {"FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_FAIL", "PASS_TO_FAIL"}
    _exact_fields(tests, expected_groups, f"report[{instance_id}].tests_status")
    result: dict[str, dict[str, int]] = {}
    seen_test_ids: set[str] = set()
    for group in sorted(tests):
        if not isinstance(group, str) or not group or any(ord(character) < 32 for character in group):
            raise ValueError(f"report[{instance_id}] has an invalid test-group name")
        values = _object(tests[group], f"report[{instance_id}].{group}")
        _exact_fields(values, {"success", "failure"}, f"report[{instance_id}].{group}")
        success = _array(values.get("success"), f"report[{instance_id}].{group}.success")
        failure = _array(values.get("failure"), f"report[{instance_id}].{group}.failure")
        for disposition, names in (("success", success), ("failure", failure)):
            if any(not isinstance(name, str) or not name for name in names):
                raise ValueError(
                    f"report[{instance_id}].{group}.{disposition} must contain test names"
                )
            if len(names) != len(set(names)):
                raise ValueError(
                    f"report[{instance_id}].{group}.{disposition} contains duplicates"
                )
        if set(success) & set(failure):
            raise ValueError(f"report[{instance_id}].{group} contradicts itself")
        group_test_ids = set(success) | set(failure)
        if seen_test_ids & group_test_ids:
            raise ValueError(f"report[{instance_id}] repeats a test ID across groups")
        seen_test_ids.update(group_test_ids)
        result[group] = {"success": len(success), "failure": len(failure)}
    return result


def _parse_hosted_report(payload: bytes, instance_id: str) -> dict[str, Any]:
    try:
        decoded = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid strict report JSON for {instance_id}: {exc}") from exc
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
    all_test_groups = _test_group_counts(report, instance_id)
    result = {
        "hosted_resolved": _boolean(
            report.get("resolved"), f"report[{instance_id}].resolved"
        ),
        "patch_exists": _boolean(
            report.get("patch_exists"), f"report[{instance_id}].patch_exists"
        ),
        "patch_is_none": _boolean(
            report.get("patch_is_None"), f"report[{instance_id}].patch_is_None"
        ),
        "patch_successfully_applied": _boolean(
            report.get("patch_successfully_applied"),
            f"report[{instance_id}].patch_successfully_applied",
        ),
        "fail_to_pass_success": all_test_groups["FAIL_TO_PASS"]["success"],
        "fail_to_pass_failure": all_test_groups["FAIL_TO_PASS"]["failure"],
        "pass_to_pass_success": all_test_groups["PASS_TO_PASS"]["success"],
        "pass_to_pass_failure": all_test_groups["PASS_TO_PASS"]["failure"],
        "all_test_group_counts": all_test_groups,
    }
    if result["patch_exists"] == result["patch_is_none"]:
        raise ValueError(f"hosted report has contradictory patch presence for {instance_id}")
    if result["patch_successfully_applied"] and (
        not result["patch_exists"] or result["patch_is_none"]
    ):
        raise ValueError(
            f"hosted report applies an absent patch for {instance_id}"
        )
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


def _sanitized_patch_identities(
    manifest: Mapping[str, Any],
) -> tuple[PatchArtifactIdentity, ...]:
    """Project the validated acquisition onto patch-only identities."""

    source = _object(manifest["source"], "source_manifest.source")
    canonical_dataset = source.get("canonical_dataset")
    canonical_by_id: dict[str, CanonicalTaskIdentity] = {}
    if canonical_dataset is not None:
        dataset_record = _object(canonical_dataset, "source.canonical_dataset")
        for index, raw_identity in enumerate(dataset_record["task_identities"]):
            identity = _object(raw_identity, f"canonical task identity {index}")
            task = CanonicalTaskIdentity(
                instance_id=str(identity["instance_id"]),
                repository=str(identity["repo"]),
                base_commit=str(identity["base_commit"]),
                environment_setup_commit=str(
                    identity["environment_setup_commit"]
                ),
            )
            if task.instance_id in canonical_by_id:
                raise ValueError("canonical task projection contains duplicate IDs")
            canonical_by_id[task.instance_id] = task

    identities = [
        PatchArtifactIdentity(
            instance_id=str(item["instance_id"]),
            repository=str(item["repository"]),
            availability=str(item["availability"]),
            byte_count=(int(item["bytes"]) if item["bytes"] is not None else None),
            sha256=(str(item["sha256"]) if item["sha256"] is not None else None),
            error_code=(
                str(item["error_code"])
                if item["error_code"] is not None
                else None
            ),
            base_commit=(
                canonical_by_id[str(item["instance_id"])].base_commit
                if str(item["instance_id"]) in canonical_by_id
                else None
            ),
            environment_setup_commit=(
                canonical_by_id[
                    str(item["instance_id"])
                ].environment_setup_commit
                if str(item["instance_id"]) in canonical_by_id
                else None
            ),
            canonical_task_identity_sha256=(
                canonical_by_id[str(item["instance_id"])].canonical_digest()
                if str(item["instance_id"]) in canonical_by_id
                else None
            ),
        )
        for item in manifest["objects"]
        if item["artifact_name"] == "patch.diff"
    ]
    identities.sort(key=lambda item: item.instance_id)
    if len(identities) != len({item.instance_id for item in identities}):
        raise ValueError("sanitized patch frame contains duplicate instance IDs")
    if canonical_by_id and set(canonical_by_id) != {
        identity.instance_id for identity in identities
    }:
        raise ValueError("canonical task projection does not match the patch frame")
    return tuple(identities)


def _build_patch_only_freeze(
    artifact_root: pathlib.Path,
    patch_identities: Sequence[PatchArtifactIdentity],
    *,
    policy_seed: int,
) -> tuple[list[PatchPhaseRow], dict[str, Any]]:
    """Build all features and order permutations from patch identities only."""

    if any(not isinstance(item, PatchArtifactIdentity) for item in patch_identities):
        raise TypeError("patch-only freeze accepts only PatchArtifactIdentity values")
    router = ConservativeRouter()
    patch_rows: list[PatchPhaseRow] = []

    for patch_identity in patch_identities:
        instance_id = patch_identity.instance_id
        repository = patch_identity.repository
        if repository != infer_repository(instance_id):
            raise ValueError("sanitized patch identity repository drifted")
        canonical_values = (
            patch_identity.base_commit,
            patch_identity.environment_setup_commit,
            patch_identity.canonical_task_identity_sha256,
        )
        if any(value is not None for value in canonical_values) and not all(
            value is not None for value in canonical_values
        ):
            raise ValueError("sanitized canonical task identity is incomplete")
        if patch_identity.base_commit is not None:
            assert patch_identity.environment_setup_commit is not None
            assert patch_identity.canonical_task_identity_sha256 is not None
            canonical_task = CanonicalTaskIdentity(
                instance_id=instance_id,
                repository=repository,
                base_commit=patch_identity.base_commit,
                environment_setup_commit=patch_identity.environment_setup_commit,
            )
            if (
                _COMMIT_RE.fullmatch(canonical_task.base_commit) is None
                or _COMMIT_RE.fullmatch(canonical_task.environment_setup_commit)
                is None
                or canonical_task.canonical_digest()
                != patch_identity.canonical_task_identity_sha256
            ):
                raise ValueError("sanitized canonical task identity drifted")
        patch_error = patch_identity.error_code
        reference_free: dict[str, Any] | None = None
        policy_candidate: PolicyCandidate | None = None
        if patch_identity.availability == "downloaded":
            if patch_identity.byte_count is None or patch_identity.sha256 is None:
                raise ValueError("downloaded patch identity lacks bytes or digest")
            patch_payload = _safe_artifact_path(
                artifact_root, instance_id, "patch.diff"
            ).read_bytes()
            try:
                patch = patch_payload.decode("utf-8")
                provenance = {
                    "repository": repository,
                    "candidate_generator": SUBMISSION_ID,
                    "source_bucket": BUCKET_NAME,
                    "source_prefix": ROOT_PREFIX,
                }
                if (
                    patch_identity.base_commit is not None
                    and patch_identity.environment_setup_commit is not None
                    and patch_identity.canonical_task_identity_sha256 is not None
                ):
                    provenance.update(
                        {
                            "base_commit": patch_identity.base_commit,
                            "environment_setup_commit": (
                                patch_identity.environment_setup_commit
                            ),
                            "dataset": CANONICAL_DATASET_ID,
                            "dataset_revision": CANONICAL_DATASET_REVISION,
                            "canonical_task_identity_sha256": (
                                patch_identity.canonical_task_identity_sha256
                            ),
                        }
                    )
                candidate_manifest = build_candidate_manifest(
                    instance_id=instance_id,
                    candidate_patch=patch,
                    lifecycle_stage=LifecycleStage.ROLLOUT,
                    provenance=provenance,
                )
                initial_decision = router.route(candidate_manifest)
                manifest_dict = candidate_manifest.to_dict()
                tie_material = (
                    f"bench-cleanser-hosted-study-tie-v1\0{policy_seed}\0{instance_id}\0"
                    f"{candidate_manifest.candidate_id}"
                )
                reference_free = {
                    "candidate_id": candidate_manifest.candidate_id,
                    "manifest_sha256": candidate_manifest.canonical_digest(),
                    "candidate_risk": initial_decision.candidate_risk,
                    "router_policy_version": initial_decision.policy_version,
                    "initial_route_action": initial_decision.action.value,
                    "risk_profile": manifest_dict["risk_profile"],
                    "canonical_task_identity": (
                        {
                            "base_commit": patch_identity.base_commit,
                            "environment_setup_commit": (
                                patch_identity.environment_setup_commit
                            ),
                            "sha256": (
                                patch_identity.canonical_task_identity_sha256
                            ),
                        }
                        if patch_identity.base_commit is not None
                        else None
                    ),
                    "tie_break_sha256": hashlib.sha256(
                        tie_material.encode()
                    ).hexdigest(),
                }
                policy_candidate = PolicyCandidate(
                    instance_id=instance_id,
                    repository=repository,
                    candidate_id=candidate_manifest.candidate_id,
                    manifest_sha256=candidate_manifest.canonical_digest(),
                    candidate_risk=initial_decision.candidate_risk,
                    router_policy_version=initial_decision.policy_version,
                    initial_route_action=initial_decision.action.value,
                    risk_profile=manifest_dict["risk_profile"],
                    patch_bytes=patch_identity.byte_count,
                    patch_sha256=patch_identity.sha256,
                )
            except (UnicodeDecodeError, ValueError):
                patch_error = "malformed_patch"
        patch_rows.append(PatchPhaseRow(
            patch_identity=patch_identity,
            patch_error=patch_error,
            reference_free=reference_free,
            policy_candidate=policy_candidate,
        ))

    frozen_rows = [
        {
            "instance_id": row.patch_identity.instance_id,
            "repository": row.patch_identity.repository,
            "patch_availability": row.patch_identity.availability,
            "patch_error": row.patch_error,
            "canonical_task_identity": (
                {
                    "base_commit": row.patch_identity.base_commit,
                    "environment_setup_commit": (
                        row.patch_identity.environment_setup_commit
                    ),
                    "sha256": row.patch_identity.canonical_task_identity_sha256,
                }
                if row.patch_identity.base_commit is not None
                else None
            ),
            "reference_free": row.reference_free,
        }
        for row in patch_rows
    ]
    frozen_policy_candidates = [
        row.policy_candidate
        for row in patch_rows
        if row.policy_candidate is not None
    ]
    base_full_policy_orders = {
        policy: _freeze_policy_order(
            frozen_policy_candidates,
            policy,
            seed=policy_seed,
        )
        for policy in TRIAGE_POLICIES
    }
    tie_seed_full_policy_orders = {
        policy: [
            _freeze_policy_order(
                frozen_policy_candidates,
                policy,
                seed=seed,
            )
            for seed in range(
                policy_seed,
                policy_seed + TIE_SENSITIVITY_SEED_COUNT,
            )
        ]
        for policy in TIE_SENSITIVE_POLICIES
    }
    frozen_document = {
        "schema": "patch-only-feature-freeze-v3",
        "policy_order_contract": POLICY_ORDER_CONTRACT,
        "policy_seed": policy_seed,
        "rows": frozen_rows,
        "base_full_policy_orders": base_full_policy_orders,
        "tie_seed_full_policy_orders": tie_seed_full_policy_orders,
    }
    frozen_payload = (strict_json_dumps(frozen_document) + "\n").encode()
    feature_freeze = {
        **frozen_document,
        "row_count": len(frozen_rows),
        "bytes": len(frozen_payload),
        "sha256": _sha256(frozen_payload),
        "completed_before_any_outcome_decode": True,
        "base_policy_order_count": len(base_full_policy_orders),
        "tie_seed_policy_order_count": sum(
            len(records) for records in tie_seed_full_policy_orders.values()
        ),
        "excluded_inputs": [
            "official results category lists",
            "report URL",
            "report listed/downloaded bytes",
            "report digest",
            "report availability",
            "hosted resolved label",
            "hosted test counts",
            "canonical gold patch",
            "canonical test patch and test identifiers",
            "canonical problem statement and hints",
        ],
    }
    return patch_rows, feature_freeze


def _reveal_pinned_official_results(
    artifact_root: pathlib.Path,
    *,
    expected_count: int,
    feature_freeze: Mapping[str, Any],
) -> dict[str, list[str]] | None:
    if feature_freeze.get("completed_before_any_outcome_decode") is not True:
        raise ValueError("official results cannot be decoded before feature freeze")
    _string(feature_freeze.get("sha256"), "feature freeze sha256")
    if expected_count != EXPECTED_INSTANCE_COUNT:
        return None
    path = artifact_root / "submission-results.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("pinned official results must be a regular file")
    payload = path.read_bytes()
    if _sha256(payload) != SUBMISSION_RESULTS_SHA256:
        raise ValueError("pinned official results digest drifted during reveal")
    return _parse_pinned_submission_results(payload)


def _reveal_frame_rows(
    artifact_root: pathlib.Path,
    manifest: Mapping[str, Any],
    patch_rows: Sequence[PatchPhaseRow],
    *,
    feature_freeze: Mapping[str, Any],
) -> list[FrameRow]:
    """Decode hosted reports only after the supplied complete freeze exists."""

    if feature_freeze.get("completed_before_any_outcome_decode") is not True:
        raise ValueError("hosted reports cannot be decoded before feature freeze")
    identities: dict[tuple[str, str], Mapping[str, Any]] = {
        (item["instance_id"], item["artifact_name"]): item
        for item in manifest["objects"]
    }
    rows: list[FrameRow] = []
    for partial in patch_rows:
        instance_id = partial.patch_identity.instance_id
        repository = partial.patch_identity.repository
        patch_identity = identities[(instance_id, "patch.diff")]
        report_identity = identities[(instance_id, "report.json")]
        report_availability = str(report_identity["availability"])
        report_error = (
            str(report_identity["error_code"])
            if report_identity["error_code"] is not None
            else None
        )
        reference_free = partial.reference_free
        outcome: dict[str, Any] | None = None

        if report_availability == "downloaded":
            report_payload = _safe_artifact_path(
                artifact_root, instance_id, "report.json"
            ).read_bytes()
            try:
                outcome = _parse_hosted_report(report_payload, instance_id)
            except ValueError:
                report_error = "malformed_report"

        candidate: Candidate | None = None
        policy_candidate = partial.policy_candidate
        if policy_candidate is not None and outcome is not None:
            candidate = Candidate(
                policy_candidate=policy_candidate,
                report_bytes=report_identity["bytes"],
                report_sha256=report_identity["sha256"],
                **outcome,
            )
        rows.append(FrameRow(
            instance_id=instance_id,
            repository=repository,
            patch_availability=partial.patch_identity.availability,
            report_availability=report_availability,
            patch_error=partial.patch_error,
            report_error=report_error,
            artifact_records={
                "patch.diff": dict(patch_identity),
                "report.json": dict(report_identity),
            },
            policy_candidate=policy_candidate,
            candidate=candidate,
            reference_free=reference_free,
            hosted_outcome=outcome,
        ))
    return rows


def _deterministic_random_key(instance_id: str, seed: int) -> str:
    material = f"bench-cleanser-hosted-study-v1\0{seed}\0{instance_id}"
    return hashlib.sha256(material.encode()).hexdigest()


def _outcome_blind_tie_key(candidate: PolicyCandidate, seed: int) -> str:
    material = (
        f"bench-cleanser-hosted-study-tie-v1\0{seed}\0{candidate.instance_id}\0"
        f"{candidate.candidate_id}"
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _collision_checked_hashes(
    candidates: Sequence[PolicyCandidate],
    key: Callable[[PolicyCandidate], str],
    *,
    field: str,
) -> dict[str, str]:
    if len(candidates) != len({item.instance_id for item in candidates}):
        raise ValueError("policy candidates contain duplicate instance IDs")
    result: dict[str, str] = {}
    seen: dict[str, str] = {}
    for candidate in candidates:
        digest = key(candidate)
        prior = seen.get(digest)
        if prior is not None:
            raise ValueError(
                f"{field} SHA-256 collision between {prior!r} and "
                f"{candidate.instance_id!r}; refusing an implicit ordering fallback"
            )
        seen[digest] = candidate.instance_id
        result[candidate.instance_id] = digest
    return result


def _policy_order(
    candidates: Sequence[PolicyCandidate],
    policy: str,
    *,
    seed: int,
) -> list[PolicyCandidate]:
    tie_hashes = _collision_checked_hashes(
        candidates,
        lambda item: _outcome_blind_tie_key(item, seed),
        field="outcome-blind tie",
    )
    if policy == "risk_top_budget":
        return sorted(
            candidates,
            key=lambda item: (-item.candidate_risk, tie_hashes[item.instance_id]),
        )
    if policy == "patch_size_top_budget":
        return sorted(
            candidates,
            key=lambda item: (
                -int(item.risk_profile["lines_changed"]),
                -int(item.risk_profile["files_changed"]),
                tie_hashes[item.instance_id],
            ),
        )
    if policy == "touches_tests_first":
        return sorted(
            candidates,
            key=lambda item: (
                -int(bool(item.risk_profile["touches_tests"])),
                tie_hashes[item.instance_id],
            ),
        )
    if policy == "seeded_random":
        random_hashes = _collision_checked_hashes(
            candidates,
            lambda item: _deterministic_random_key(item.instance_id, seed),
            field="seeded-random",
        )
        return sorted(
            candidates,
            key=lambda item: random_hashes[item.instance_id],
        )
    raise ValueError(f"unknown triage policy {policy!r}")


def _freeze_policy_order(
    candidates: Sequence[PolicyCandidate],
    policy: str,
    *,
    seed: int,
) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("policy-order seed must be a non-negative integer")
    if policy not in TRIAGE_POLICIES:
        raise ValueError(f"unknown triage policy {policy!r}")
    ordered = _policy_order(candidates, policy, seed=seed)
    payload = {
        "contract": POLICY_ORDER_CONTRACT,
        "policy": policy,
        "seed": seed,
        "candidate_count": len(ordered),
        "ordered_candidates": [
            {
                "instance_id": item.instance_id,
                "candidate_id": item.candidate_id,
            }
            for item in ordered
        ],
    }
    return {
        **payload,
        "sha256": _sha256(strict_json_dumps(payload).encode()),
    }


def _consume_frozen_policy_order(
    candidates: Sequence[PolicyCandidate],
    record: Mapping[str, Any],
    *,
    policy: str,
    seed: int,
) -> list[PolicyCandidate]:
    """Validate and consume one complete pre-label candidate permutation."""

    _exact_fields(
        record,
        {
            "contract",
            "policy",
            "seed",
            "candidate_count",
            "ordered_candidates",
            "sha256",
        },
        "frozen policy order",
    )
    record_contract = _string(record["contract"], "frozen policy order contract")
    record_policy = _string(record["policy"], "frozen policy order policy")
    record_seed = _integer(record["seed"], "frozen policy order seed")
    record_candidate_count = _integer(
        record["candidate_count"],
        "frozen policy order candidate_count",
    )
    if (
        record_contract != POLICY_ORDER_CONTRACT
        or record_policy != policy
        or record_seed != seed
        or record_candidate_count != len(candidates)
    ):
        raise ValueError("frozen policy order identity drifted")
    supplied_digest = _string(record["sha256"], "frozen policy order sha256")
    if _SHA256_RE.fullmatch(supplied_digest) is None:
        raise ValueError("frozen policy order sha256 is malformed")
    payload = {key: value for key, value in record.items() if key != "sha256"}
    if _sha256(strict_json_dumps(payload).encode()) != supplied_digest:
        raise ValueError("frozen policy order digest drifted")

    candidate_by_instance = {item.instance_id: item for item in candidates}
    if len(candidate_by_instance) != len(candidates):
        raise ValueError("policy candidates contain duplicate instance IDs")
    ordered_values = _array(
        record["ordered_candidates"],
        "frozen policy order.ordered_candidates",
    )
    ordered: list[PolicyCandidate] = []
    seen: set[str] = set()
    for index, value in enumerate(ordered_values):
        field = f"frozen policy order.ordered_candidates[{index}]"
        identity = _object(value, field)
        _exact_fields(identity, {"instance_id", "candidate_id"}, field)
        instance_id = _string(identity["instance_id"], f"{field}.instance_id")
        candidate_id = _string(identity["candidate_id"], f"{field}.candidate_id")
        candidate = candidate_by_instance.get(instance_id)
        if candidate is None or candidate.candidate_id != candidate_id:
            raise ValueError("frozen policy order contains an unknown candidate identity")
        if instance_id in seen:
            raise ValueError("frozen policy order repeats an instance ID")
        seen.add(instance_id)
        ordered.append(candidate)
    if len(ordered) != len(candidates) or seen != set(candidate_by_instance):
        raise ValueError("frozen policy order is not a full candidate permutation")
    return ordered


def _subgroup_memberships(
    candidate: PolicyCandidate,
    high_risk: float,
) -> tuple[str, ...]:
    profile = candidate.risk_profile
    lines = int(profile["lines_changed"])
    patch_size = "small_le_20" if lines <= 20 else "medium_21_100" if lines <= 100 else "large_gt_100"
    values = [
        f"touches_tests={str(bool(profile['touches_tests'])).lower()}",
        f"compiled_language={str(bool(profile['compiled_language'])).lower()}",
        "touches_dependency_or_build_files="
        f"{str(bool(profile['touches_dependency_or_build_files'])).lower()}",
        f"touches_security_or_auth={str(bool(profile['touches_security_or_auth'])).lower()}",
        f"touches_concurrency={str(bool(profile['touches_concurrency'])).lower()}",
        f"touches_schema_or_migration={str(bool(profile['touches_schema_or_migration'])).lower()}",
        f"initial_candidate_risk_ge_{high_risk:.2f}="
        f"{str(candidate.candidate_risk >= high_risk).lower()}",
        f"patch_size={patch_size}",
    ]
    return tuple(values)


def _policy_metrics(
    rows: Sequence[FrameRow],
    executed: set[str],
) -> dict[str, Any]:
    candidates = [row.candidate for row in rows if row.candidate is not None]
    accepted = [item for item in candidates if item.instance_id not in executed or item.hosted_resolved]
    rejected = [item for item in candidates if item.instance_id in executed and not item.hosted_resolved]
    false_accepts = [item for item in accepted if not item.hosted_resolved]
    false_rejects = [item for item in rejected if item.hosted_resolved]
    unresolved = sum(not item.hosted_resolved for item in candidates)
    resolved = len(candidates) - unresolved
    quarantined = len(rows) - len(candidates)
    selectable_ids = {
        row.policy_candidate.instance_id
        for row in rows
        if row.policy_candidate is not None
    }
    executed_ids = executed & selectable_ids
    unknown_outcome_rows = [row for row in rows if row.hosted_outcome is None]
    selected_unknown_outcomes = sum(
        row.instance_id in executed_ids for row in unknown_outcome_rows
    )
    failure_capture_if_unknown_resolved = len(rejected) / unresolved if unresolved else None
    worst_case_failure_total = unresolved + len(unknown_outcome_rows)
    failure_capture_if_unknown_failed = (
        (len(rejected) + selected_unknown_outcomes) / worst_case_failure_total
        if worst_case_failure_total
        else None
    )
    return {
        "frame_candidate_count": len(rows),
        "analyzable_candidate_count": len(candidates),
        "quarantined_candidate_count": quarantined,
        "hosted_harness_resolved_count": resolved,
        "hosted_harness_failure_count": unresolved,
        "policy_feature_or_outcome_quarantine_count": quarantined,
        "unknown_hosted_outcome_count": len(unknown_outcome_rows),
        "selected_unknown_hosted_outcome_count": selected_unknown_outcomes,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "hosted_failures_captured": len(rejected),
        "hosted_failure_capture_fraction": len(rejected) / unresolved if unresolved else None,
        "hosted_failure_capture_fraction_unknown_label_sensitivity": {
            "unknown_labels_all_resolved": failure_capture_if_unknown_resolved,
            "unknown_labels_all_failed": failure_capture_if_unknown_failed,
        },
        "verification_yield_failures_per_execution": (
            len(rejected) / len(executed_ids) if executed_ids else None
        ),
        "false_accept_count": len(false_accepts),
        "false_accepts_remaining_fraction_of_all_hosted_failures": (
            len(false_accepts) / unresolved if unresolved else None
        ),
        "false_accepts_remaining_numerator": len(false_accepts),
        "all_hosted_failures_denominator": unresolved,
        "false_accept_fraction_among_accepted": (
            len(false_accepts) / len(accepted) if accepted else None
        ),
        "false_reject_count": len(false_rejects),
        "false_reject_fraction_among_hosted_resolved": (
            len(false_rejects) / resolved if resolved else None
        ),
        "execution_count": len(executed_ids),
        "execution_fraction_of_full_frame": (
            len(executed_ids) / len(rows)
            if rows
            else None
        ),
        "policy_feature_coverage_fraction": len(selectable_ids) / len(rows) if rows else None,
        "hosted_label_coverage_fraction": (
            sum(row.hosted_outcome is not None for row in rows) / len(rows)
            if rows
            else None
        ),
        "joint_policy_and_label_coverage_fraction": (
            len(candidates) / len(rows) if rows else None
        ),
        "false_reject_is_tautologically_zero_under_hosted_label_terminal_rule": True,
    }


def _slice_metrics(
    rows: Sequence[FrameRow],
    executed: set[str],
    *,
    high_risk: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    repositories: dict[str, list[FrameRow]] = defaultdict(list)
    subgroups: dict[str, list[FrameRow]] = defaultdict(list)
    for row in rows:
        repositories[row.repository].append(row)
        status = "analyzable" if row.analyzable else "quarantined"
        subgroups[f"analysis_status={status}"].append(row)
        subgroups[f"patch_availability={row.patch_availability}"].append(row)
        subgroups[f"report_availability={row.report_availability}"].append(row)
        if row.policy_candidate is not None:
            for subgroup in _subgroup_memberships(row.policy_candidate, high_risk):
                subgroups[subgroup].append(row)
    by_repository = [
        {"repository": key, **_policy_metrics(values, executed)}
        for key, values in sorted(repositories.items())
    ]
    by_subgroup = [
        {"subgroup": key, **_policy_metrics(values, executed)}
        for key, values in sorted(subgroups.items())
    ]
    return by_repository, by_subgroup


def _hypergeometric_randomization_distribution(
    *,
    population: int,
    hosted_failures: int,
    unknown_outcomes: int,
    execution_count: int,
) -> dict[str, Any]:
    unresolved = hosted_failures
    resolved = population - hosted_failures - unknown_outcomes
    if (
        not 0 <= hosted_failures <= population
        or not 0 <= unknown_outcomes <= population - hosted_failures
    ):
        raise ValueError("hypergeometric category counts are out of range")
    if not 0 <= execution_count <= population:
        raise ValueError("hypergeometric execution count is out of range")
    denominator = math.comb(population, execution_count)
    support: list[dict[str, Any]] = []
    lower = max(0, execution_count - resolved - unknown_outcomes)
    upper = min(execution_count, unresolved)
    for caught in range(lower, upper + 1):
        for selected_unknown in range(0, min(unknown_outcomes, execution_count - caught) + 1):
            selected_resolved = execution_count - caught - selected_unknown
            if not 0 <= selected_resolved <= resolved:
                continue
            probability = (
                math.comb(unresolved, caught)
                * math.comb(unknown_outcomes, selected_unknown)
                * math.comb(resolved, selected_resolved)
                / denominator
            )
            false_accepts = unresolved - caught
            accepted = unresolved + resolved - caught
            support.append({
                "caught_hosted_unresolved": caught,
                "selected_unknown_outcomes": selected_unknown,
                "false_accept_count": false_accepts,
                "false_accept_fraction_among_accepted": false_accepts / accepted,
                "probability": probability,
            })
    support.sort(
        key=lambda item: (
            item["caught_hosted_unresolved"],
            item["selected_unknown_outcomes"],
        )
    )

    def quantile(probability: float, key: str) -> float | int:
        cumulative = 0.0
        ordered = sorted(support, key=lambda item: (item[key], item["selected_unknown_outcomes"]))
        for item in ordered:
            cumulative += item["probability"]
            if cumulative + 1e-15 >= probability:
                value = item[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"finite-frame support field {key!r} is not numeric")
                return value
        value = ordered[-1][key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"finite-frame support field {key!r} is not numeric")
        return value

    return {
        "status": "exact_finite_frame_randomization_distribution",
        "design": "uniform execution set of size k without replacement",
        "population_size": population,
        "hosted_unresolved_count": unresolved,
        "unknown_outcome_count": unknown_outcomes,
        "execution_count": execution_count,
        "expected_caught_hosted_unresolved": execution_count * unresolved / population,
        "caught_hosted_unresolved_quantiles": {
            "q025": quantile(0.025, "caught_hosted_unresolved"),
            "q50": quantile(0.50, "caught_hosted_unresolved"),
            "q975": quantile(0.975, "caught_hosted_unresolved"),
        },
        "false_accept_fraction_quantiles": {
            "q025": quantile(0.025, "false_accept_fraction_among_accepted"),
            "q50": quantile(0.50, "false_accept_fraction_among_accepted"),
            "q975": quantile(0.975, "false_accept_fraction_among_accepted"),
        },
        "support": support,
    }


def _repository_stratified_randomization_distribution(
    rows: Sequence[FrameRow],
    *,
    execution_count: int,
) -> dict[str, Any]:
    selectable_rows = [row for row in rows if row.policy_candidate is not None]
    by_repository: dict[str, list[FrameRow]] = defaultdict(list)
    for row in selectable_rows:
        by_repository[row.repository].append(row)
    population = len(selectable_rows)
    if not 0 <= execution_count <= population:
        raise ValueError("stratified execution count is out of range")

    allocation: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    allocated = 0
    for repository, values in sorted(by_repository.items()):
        exact = execution_count * len(values) / population
        floor = math.floor(exact)
        allocation[repository] = floor
        allocated += floor
        remainders.append((exact - floor, repository))
    for _, repository in sorted(remainders, key=lambda item: (-item[0], item[1]))[
        : execution_count - allocated
    ]:
        allocation[repository] += 1

    distribution: dict[tuple[int, int], float] = {(0, 0): 1.0}
    strata: list[dict[str, Any]] = []
    for repository, values in sorted(by_repository.items()):
        size = len(values)
        failures = sum(
            row.hosted_outcome is not None
            and not bool(row.hosted_outcome["hosted_resolved"])
            for row in values
        )
        resolved = sum(
            row.hosted_outcome is not None
            and bool(row.hosted_outcome["hosted_resolved"])
            for row in values
        )
        unknown = sum(row.hosted_outcome is None for row in values)
        if failures + resolved + unknown != size:
            raise ValueError("repository outcome categories do not partition the stratum")
        draw = allocation[repository]
        denominator = math.comb(size, draw)
        stratum_distribution: dict[tuple[int, int], float] = {}
        for caught in range(0, min(draw, failures) + 1):
            for selected_unknown in range(0, min(unknown, draw - caught) + 1):
                selected_resolved = draw - caught - selected_unknown
                if not 0 <= selected_resolved <= resolved:
                    continue
                stratum_distribution[(caught, selected_unknown)] = (
                    math.comb(failures, caught)
                    * math.comb(unknown, selected_unknown)
                    * math.comb(resolved, selected_resolved)
                    / denominator
                )
        combined: dict[tuple[int, int], float] = defaultdict(float)
        for (total_caught, total_unknown), total_probability in distribution.items():
            for (caught, selected_unknown), probability in stratum_distribution.items():
                combined[(
                    total_caught + caught,
                    total_unknown + selected_unknown,
                )] += total_probability * probability
        distribution = dict(combined)
        strata.append({
            "repository": repository,
            "candidate_count": size,
            "hosted_harness_failure_count": failures,
            "hosted_harness_resolved_count": resolved,
            "unknown_quarantine_count": unknown,
            "execution_allocation": draw,
        })

    unresolved = sum(
        row.hosted_outcome is not None
        and not bool(row.hosted_outcome["hosted_resolved"])
        for row in selectable_rows
    )
    resolved = sum(
        row.hosted_outcome is not None
        and bool(row.hosted_outcome["hosted_resolved"])
        for row in selectable_rows
    )
    unknown = sum(row.hosted_outcome is None for row in selectable_rows)
    support: list[dict[str, Any]] = []
    for (caught, selected_unknown), probability in sorted(distribution.items()):
        false_accepts = unresolved - caught
        accepted = unresolved + resolved - caught
        support.append({
            "caught_hosted_unresolved": caught,
            "selected_unknown_outcomes": selected_unknown,
            "false_accept_count": false_accepts,
            "accepted_known_outcome_count": accepted,
            "quarantined_unknown_outcome_count": unknown,
            "false_accept_fraction_among_accepted": (
                false_accepts / accepted if accepted else None
            ),
            "probability": probability,
        })
    if not math.isclose(
        sum(item["probability"] for item in support),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("repository-stratified probability mass does not sum to one")
    return {
        "status": (
            "exact_repository_stratified_three_category_randomization_distribution"
        ),
        "allocation_rule": (
            "proportional largest remainder by repository; fractional ties by repository name"
        ),
        "terminal_semantics": (
            "known failures selected are rejected; known resolved are accepted; "
            "unknown outcomes remain quarantined whether selected or skipped"
        ),
        "population_size": population,
        "hosted_unresolved_count": unresolved,
        "hosted_resolved_count": resolved,
        "unknown_quarantine_count": unknown,
        "execution_count": execution_count,
        "strata": strata,
        "expected_caught_hosted_unresolved": sum(
            item["caught_hosted_unresolved"] * item["probability"] for item in support
        ),
        "expected_selected_unknown_outcomes": sum(
            item["selected_unknown_outcomes"] * item["probability"]
            for item in support
        ),
        "support": support,
    }


def _leave_one_repository_out(
    rows: Sequence[FrameRow],
    executed: set[str],
) -> list[dict[str, Any]]:
    repositories = sorted({row.repository for row in rows})
    return [
        {
            "excluded_repository": repository,
            **_policy_metrics(
                [row for row in rows if row.repository != repository],
                executed,
            ),
        }
        for repository in repositories
    ]


def _macro_repository_summary(by_repository: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def mean_for(key: str, denominator_key: str) -> tuple[float | None, int]:
        values = [
            float(item[key])
            for item in by_repository
            if item[denominator_key] > 0 and item[key] is not None
        ]
        return (sum(values) / len(values) if values else None, len(values))

    capture, capture_repositories = mean_for(
        "hosted_failure_capture_fraction",
        "hosted_harness_failure_count",
    )
    false_accept, accepted_repositories = mean_for(
        "false_accept_fraction_among_accepted",
        "accepted_count",
    )
    execution = [float(item["execution_fraction_of_full_frame"]) for item in by_repository]
    return {
        "repository_count": len(by_repository),
        "macro_hosted_failure_capture_fraction": capture,
        "repositories_with_hosted_failures": capture_repositories,
        "macro_false_accept_fraction_among_accepted": false_accept,
        "repositories_with_accepted_candidates": accepted_repositories,
        "macro_execution_fraction": sum(execution) / len(execution) if execution else None,
    }


def _finite_frame_roc_auc(
    scored_outcomes: Sequence[tuple[float, bool]],
) -> float | None:
    """Pairwise finite-frame AUC with hosted failure as the positive class."""

    positives = [score for score, failed in scored_outcomes if failed]
    negatives = [score for score, failed in scored_outcomes if not failed]
    if not positives or not negatives:
        return None
    concordance = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                concordance += 1.0
            elif positive == negative:
                concordance += 0.5
    return concordance / (len(positives) * len(negatives))


def _post_hoc_discrimination_diagnostic(
    rows: Sequence[FrameRow],
) -> dict[str, Any]:
    """Describe signal discrimination after labels are revealed; never route on it."""

    labeled = [
        row
        for row in rows
        if row.policy_candidate is not None and row.hosted_outcome is not None
    ]
    signals: tuple[tuple[str, Callable[[PolicyCandidate], float]], ...] = (
        ("candidate_risk", lambda item: float(item.candidate_risk)),
        (
            "lines_changed",
            lambda item: float(item.risk_profile["lines_changed"]),
        ),
        (
            "files_changed",
            lambda item: float(item.risk_profile["files_changed"]),
        ),
        (
            "touches_tests",
            lambda item: float(bool(item.risk_profile["touches_tests"])),
        ),
    )
    results: dict[str, Any] = {}
    repositories = sorted({row.repository for row in labeled})
    for name, score in signals:
        scored = [
            (
                score(row.policy_candidate),
                not bool(row.hosted_outcome["hosted_resolved"]),
            )
            for row in labeled
            if row.policy_candidate is not None and row.hosted_outcome is not None
        ]
        repository_aucs = []
        for repository in repositories:
            repository_scored = [
                (
                    score(row.policy_candidate),
                    not bool(row.hosted_outcome["hosted_resolved"]),
                )
                for row in labeled
                if row.repository == repository
                and row.policy_candidate is not None
                and row.hosted_outcome is not None
            ]
            auc = _finite_frame_roc_auc(repository_scored)
            if auc is not None:
                repository_aucs.append(auc)
        counts: dict[float, int] = defaultdict(int)
        for value, _ in scored:
            counts[value] += 1
        tie_groups = [
            {"score": value, "candidate_count": count}
            for value, count in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if count > 1
        ]
        results[name] = {
            "higher_score_predicts_hosted_failure": True,
            "finite_frame_roc_auc": _finite_frame_roc_auc(scored),
            "repository_macro_roc_auc": (
                sum(repository_aucs) / len(repository_aucs)
                if repository_aucs
                else None
            ),
            "repository_macro_eligible_count": len(repository_aucs),
            "distinct_score_count": len(counts),
            "largest_tie_groups": tie_groups[:10],
        }
    return {
        "status": "post_hoc_finite_frame_descriptive_diagnostic",
        "computed_only_after_outcome_reveal": True,
        "outcome_positive_class": "hosted_harness_unresolved",
        "calibration_claim": False,
        "confidence_interval_reported": False,
        "selection_or_policy_input": False,
        "signals": results,
    }


def _tie_seed_sensitivity(
    rows: Sequence[FrameRow],
    *,
    policy: str,
    execution_count: int,
    base_seed: int,
    frozen_orders: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if policy not in TIE_SENSITIVE_POLICIES:
        if frozen_orders is not None:
            raise ValueError("non-tie-sensitive policy cannot supply sensitivity orders")
        return {"status": "not_applicable"}
    if frozen_orders is None or len(frozen_orders) != TIE_SENSITIVITY_SEED_COUNT:
        raise ValueError("tie sensitivity requires all frozen seed permutations")
    candidates = [row.policy_candidate for row in rows if row.policy_candidate is not None]
    records: list[dict[str, Any]] = []
    for offset, frozen_order in enumerate(frozen_orders):
        seed = base_seed + offset
        ordered = _consume_frozen_policy_order(
            candidates,
            frozen_order,
            policy=policy,
            seed=seed,
        )
        selected = sorted(
            item.instance_id
            for item in ordered[:execution_count]
        )
        metrics = _policy_metrics(rows, set(selected))
        records.append({
            "seed": seed,
            "frozen_full_order_sha256": frozen_order["sha256"],
            "selected_instance_ids_sha256": _sha256(
                ("\n".join(selected) + "\n").encode()
            ),
            "hosted_failures_captured": metrics["hosted_failures_captured"],
            "selected_unknown_hosted_outcome_count": metrics[
                "selected_unknown_hosted_outcome_count"
            ],
            "false_accept_fraction_among_accepted": metrics[
                "false_accept_fraction_among_accepted"
            ],
        })
    captured = [item["hosted_failures_captured"] for item in records]
    return {
        "status": "fixed_outcome_blind_seed_grid",
        "seed_start_inclusive": base_seed,
        "seed_end_inclusive": base_seed + TIE_SENSITIVITY_SEED_COUNT - 1,
        "minimum_hosted_failures_captured": min(captured),
        "maximum_hosted_failures_captured": max(captured),
        "records": records,
    }


def _policy_result(
    rows: Sequence[FrameRow],
    *,
    policy: str,
    budget_count: int,
    seed: int,
    high_risk: float,
    base_full_policy_orders: Mapping[str, Mapping[str, Any]],
    tie_seed_full_policy_orders: Mapping[
        str,
        Sequence[Mapping[str, Any]],
    ],
) -> dict[str, Any]:
    policy_candidates = [
        row.policy_candidate for row in rows if row.policy_candidate is not None
    ]
    if budget_count < 0 or budget_count > len(rows):
        raise ValueError("policy execution budget is out of range")
    if policy == "accept_all":
        if budget_count != 0:
            raise ValueError("accept_all requires a zero execution budget")
        ordered: list[PolicyCandidate] = list(policy_candidates)
    elif policy == "execute_all":
        if budget_count != len(rows):
            raise ValueError("execute_all requires the full-frame requested budget")
        ordered = list(policy_candidates)
    else:
        frozen_order = base_full_policy_orders.get(policy)
        if frozen_order is None:
            raise ValueError(f"missing frozen base order for {policy!r}")
        ordered = _consume_frozen_policy_order(
            policy_candidates,
            frozen_order,
            policy=policy,
            seed=seed,
        )
    realized_budget = min(budget_count, len(ordered))
    executed = {item.instance_id for item in ordered[:realized_budget]}
    metrics = _policy_metrics(rows, executed)
    by_repository, by_subgroup = _slice_metrics(
        rows, executed, high_risk=high_risk
    )
    downloaded_patch_bytes = sum(
        int(row.artifact_records["patch.diff"]["bytes"] or 0) for row in rows
    )
    downloaded_report_bytes = sum(
        int(row.artifact_records["report.json"]["bytes"] or 0) for row in rows
    )
    selectable_rows = [row for row in rows if row.policy_candidate is not None]
    known_failures = sum(
        row.hosted_outcome is not None
        and not bool(row.hosted_outcome["hosted_resolved"])
        for row in selectable_rows
    )
    unknown_outcomes = sum(row.hosted_outcome is None for row in selectable_rows)
    uniform_reference = _hypergeometric_randomization_distribution(
        population=len(policy_candidates),
        hosted_failures=known_failures,
        unknown_outcomes=unknown_outcomes,
        execution_count=realized_budget,
    )
    uniform_expected_false_accept_fraction = sum(
        item["false_accept_fraction_among_accepted"] * item["probability"]
        for item in uniform_reference["support"]
    )
    executed_ids = sorted(executed)
    return {
        "policy": policy,
        "requested_budget_count": budget_count,
        "requested_budget_fraction_of_full_frame": budget_count / len(rows),
        "realized_execution_count": realized_budget,
        "selection_semantics": "retrospective_hosted_label_reveal_no_reexecution",
        "executed_instance_ids": executed_ids,
        "executed_instance_ids_sha256": _sha256(
            ("\n".join(executed_ids) + "\n").encode()
        ),
        "metrics": metrics,
        "execution_cost_proxy": {
            "execution_units": realized_budget,
            "selected_hosted_label_reveal_units": realized_budget,
            "actual_repository_or_test_execution_performed": False,
            "execution_fraction_of_full_frame": realized_budget / len(rows),
            "execution_fraction_of_policy_feature_frame": (
                realized_budget / len(policy_candidates)
            ),
            "runtime_seconds_unavailable": True,
            "docker_cost_unavailable": True,
        },
        "acquisition_overhead": {
            "downloaded_patch_bytes": downloaded_patch_bytes,
            "downloaded_report_bytes": downloaded_report_bytes,
            "not_an_execution_cost": True,
        },
        "by_repository": by_repository,
        "macro_repository_summary": _macro_repository_summary(by_repository),
        "by_subgroup": by_subgroup,
        "tie_seed_sensitivity": _tie_seed_sensitivity(
            rows,
            policy=policy,
            execution_count=realized_budget,
            base_seed=seed,
            frozen_orders=tie_seed_full_policy_orders.get(policy),
        ),
        "leave_one_repository_out_fixed_decision_deletion_sensitivity": (
            _leave_one_repository_out(rows, executed)
        ),
        "descriptive_delta_vs_uniform_random_expectation": {
            "hosted_failures_captured_delta": (
                metrics["hosted_failures_captured"]
                - uniform_reference["expected_caught_hosted_unresolved"]
            ),
            "false_accept_fraction_delta": (
                metrics["false_accept_fraction_among_accepted"]
                - uniform_expected_false_accept_fraction
                if metrics["false_accept_fraction_among_accepted"] is not None
                else None
            ),
            "actual_numerator_hosted_failures_captured": metrics[
                "hosted_failures_captured"
            ],
            "actual_denominator_hosted_failures": metrics[
                "hosted_harness_failure_count"
            ],
        },
        "uniform_random_matched_budget_reference": uniform_reference,
        "repository_stratified_random_matched_budget_reference": (
            _repository_stratified_randomization_distribution(
                rows,
                execution_count=realized_budget,
            )
        ),
        "sampling_uncertainty": {
            "status": "not_applicable_to_complete_finite_submission_frame",
            "cluster_bootstrap_reported": False,
            "reason": (
                "The estimand is this complete finite submission frame; 12 imbalanced "
                "repositories do not justify a population-generalization interval."
            ),
        },
    }


def _candidate_record(row: FrameRow) -> dict[str, Any]:
    policy_candidate = row.policy_candidate
    outcome = row.hosted_outcome
    return {
        "instance_id": row.instance_id,
        "repository": row.repository,
        "analysis_status": "analyzable" if row.analyzable else "mandatory_quarantine",
        "patch_error": row.patch_error,
        "report_error": row.report_error,
        "candidate_id": (
            policy_candidate.candidate_id if policy_candidate is not None else None
        ),
        "manifest_sha256": (
            policy_candidate.manifest_sha256 if policy_candidate is not None else None
        ),
        "canonical_task_identity": (
            dict(row.reference_free["canonical_task_identity"])
            if row.reference_free is not None
            and row.reference_free.get("canonical_task_identity") is not None
            else None
        ),
        "reference_free": dict(row.reference_free) if row.reference_free is not None else None,
        "hosted_outcome": (
            {
                "hosted_harness_resolved": outcome["hosted_resolved"],
                "patch_exists": outcome["patch_exists"],
                "patch_is_none": outcome["patch_is_none"],
                "patch_successfully_applied": outcome["patch_successfully_applied"],
                "fail_to_pass_success": outcome["fail_to_pass_success"],
                "fail_to_pass_failure": outcome["fail_to_pass_failure"],
                "pass_to_pass_success": outcome["pass_to_pass_success"],
                "pass_to_pass_failure": outcome["pass_to_pass_failure"],
                "all_test_group_counts": outcome["all_test_group_counts"],
            }
            if outcome is not None
            else None
        ),
        "artifacts": dict(row.artifact_records),
    }


def analyze_study(
    artifact_root: pathlib.Path,
    *,
    expected_count: int = EXPECTED_INSTANCE_COUNT,
    budget_fractions: Sequence[float] = DEFAULT_BUDGET_FRACTIONS,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, Any]:
    """Analyze a complete acquisition without network access or LLM calls."""

    artifact_root = artifact_root.absolute()
    manifest = _validate_acquisition_manifest(
        artifact_root,
        expected_count=expected_count,
    )
    patch_identities = _sanitized_patch_identities(manifest)
    patch_rows, feature_freeze = _build_patch_only_freeze(
        artifact_root,
        patch_identities,
        policy_seed=random_seed,
    )
    pinned_semantics = _reveal_pinned_official_results(
        artifact_root,
        expected_count=expected_count,
        feature_freeze=feature_freeze,
    )
    rows = _reveal_frame_rows(
        artifact_root,
        manifest,
        patch_rows,
        feature_freeze=feature_freeze,
    )
    if len(rows) != expected_count:
        raise ValueError("candidate frame is incomplete after acquisition validation")
    if len({item.instance_id for item in rows}) != len(rows):
        raise ValueError("candidate frame contains duplicate instance IDs")
    candidates = [row.candidate for row in rows if row.candidate is not None]
    policy_candidates = [
        row.policy_candidate for row in rows if row.policy_candidate is not None
    ]
    if len(policy_candidates) != expected_count:
        raise ValueError(
            "all 500 frame rows must have frozen patch-only policy features; "
            f"found {len(policy_candidates)}"
        )
    if expected_count == EXPECTED_INSTANCE_COUNT and any(
        row.reference_free is None
        or row.reference_free.get("canonical_task_identity") is None
        for row in rows
    ):
        raise ValueError(
            "all production frame rows must bind canonical dataset task identity"
        )
    router = ConservativeRouter()
    high_risk = router.policy.high_candidate_risk
    base_full_policy_orders = _object(
        feature_freeze["base_full_policy_orders"],
        "patch_only_feature_freeze.base_full_policy_orders",
    )
    tie_seed_full_policy_orders = _object(
        feature_freeze["tie_seed_full_policy_orders"],
        "patch_only_feature_freeze.tie_seed_full_policy_orders",
    )

    budgets: list[int] = []
    for fraction in budget_fractions:
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            raise ValueError("budget fractions must be numbers")
        if not 0.0 < fraction < 1.0:
            raise ValueError("triage budget fractions must be strictly between 0 and 1")
        count = round(len(rows) * float(fraction))
        if not 0 < count < len(rows):
            raise ValueError("budget fraction rounds outside the triage range")
        budgets.append(count)
    if len(budgets) != len(set(budgets)):
        raise ValueError("budget fractions produce duplicate execution counts")
    budgets.sort()

    policy_definitions = {
        "accept_all": (
            "Select zero rows for retrospective hosted-label reveal and accept only rows "
            "with available hosted labels; unavailable/malformed rows remain mandatory "
            "quarantine, not accepted. No repository or test is executed by this study."
        ),
        "execute_all": (
            "Select every policy-feature row for retrospective hosted-label reveal, including "
            "rows whose hosted outcome is unavailable; accept hosted-harness resolved, reject "
            "hosted-harness failed, and mandatory-quarantine unavailable/malformed outcomes "
            "after they consume a slot. This does not re-execute a repository or test."
        ),
        "risk_top_budget": (
            "Select the exact label-reveal budget with highest ConservativeRouter initial "
            "candidate_risk; break ties by a domain-separated SHA-256 of pre-outcome "
            "instance and candidate IDs."
        ),
        "patch_size_top_budget": (
            "Select the exact label-reveal budget by descending reference-free lines_changed, "
            "then files_changed, then the same pre-outcome tie hash."
        ),
        "touches_tests_first": (
            "Select test-touching patches first for label reveal; within indicator groups "
            "use only the pre-outcome seeded tie hash."
        ),
        "seeded_random": (
            "Select the exact label-reveal budget by ascending SHA-256 of domain, seed, and "
            f"instance_id; seed={random_seed}."
        ),
        "terminal_rule": (
            "A selected row reveals its already-downloaded hosted resolved label; skipped "
            "labeled rows are accepted. Unavailable/malformed rows are always quarantined. "
            "This retrospective label-reveal simulation performs no new execution and "
            "tautologically cannot produce false rejects relative to the same hosted labels."
        ),
    }
    policies = [
        _policy_result(
            rows,
            policy="accept_all",
            budget_count=0,
            seed=random_seed,
            high_risk=high_risk,
            base_full_policy_orders=base_full_policy_orders,
            tie_seed_full_policy_orders=tie_seed_full_policy_orders,
        )
    ]
    for policy in (
        "risk_top_budget",
        "patch_size_top_budget",
        "touches_tests_first",
        "seeded_random",
    ):
        for budget in budgets:
            policies.append(_policy_result(
                rows,
                policy=policy,
                budget_count=budget,
                seed=random_seed,
                high_risk=high_risk,
                base_full_policy_orders=base_full_policy_orders,
                tie_seed_full_policy_orders=tie_seed_full_policy_orders,
            ))
    policies.append(_policy_result(
        rows,
        policy="execute_all",
        budget_count=len(rows),
        seed=random_seed,
        high_risk=high_risk,
        base_full_policy_orders=base_full_policy_orders,
        tie_seed_full_policy_orders=tie_seed_full_policy_orders,
    ))

    acquisition_manifest_bytes = (artifact_root / "source_manifest.json").read_bytes()
    outcomes = [row.hosted_outcome for row in rows if row.hosted_outcome is not None]
    resolved_count = sum(bool(item["hosted_resolved"]) for item in outcomes)
    failure_count = len(outcomes) - resolved_count
    missing_outcome_count = len(rows) - len(outcomes)
    repository_counts = [
        {"repository": repository, "candidate_count": count, "frame_fraction": count / len(rows)}
        for repository, count in sorted(
            (
                (repository, sum(row.repository == repository for row in rows))
                for repository in {row.repository for row in rows}
            ),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    reference_rows = [row for row in rows if row.reference_free is not None]
    language_counts: dict[str, int] = defaultdict(int)
    for row in reference_rows:
        assert row.reference_free is not None
        language_counts[str(row.reference_free["risk_profile"]["language"])] += 1
    malformed_patch_count = sum(row.patch_error == "malformed_patch" for row in rows)
    malformed_report_count = sum(row.report_error == "malformed_report" for row in rows)
    official_results_crosscheck: dict[str, Any]
    if pinned_semantics is not None:
        missing_report_ids = sorted(
            row.instance_id for row in rows if row.hosted_outcome is None
        )
        resolved_ids = sorted(
            row.instance_id
            for row in rows
            if row.hosted_outcome is not None
            and bool(row.hosted_outcome["hosted_resolved"])
        )
        if (
            pinned_semantics["no_generation"] != []
            or pinned_semantics["no_logs"] != missing_report_ids
            or pinned_semantics["resolved"] != resolved_ids
        ):
            raise ValueError(
                "per-instance reports/object missingness contradict pinned official results.json"
            )
        official_results_crosscheck = {
            "status": "exact_match",
            "decoded_only_after_feature_freeze_sha256": feature_freeze["sha256"],
            "no_generation_count": 0,
            "no_logs_count": len(missing_report_ids),
            "resolved_count": len(resolved_ids),
        }
    else:
        official_results_crosscheck = {
            "status": "not_applicable_nonproduction_fixture_frame"
        }
    source_dataset = manifest["source"]["canonical_dataset"]
    if source_dataset is not None:
        canonical_dataset_crosscheck = {
            "status": source_dataset["frame_crosscheck"]["status"],
            "dataset_id": source_dataset["dataset_id"],
            "revision": source_dataset["revision"],
            "authoritative_url": source_dataset["authoritative_url"],
            "retrieval_transport": source_dataset["retrieval_transport"],
            "bytes": source_dataset["bytes"],
            "sha256": source_dataset["sha256"],
            "projection": source_dataset["projection"],
            "frame_crosscheck": source_dataset["frame_crosscheck"],
        }
    else:
        canonical_dataset_crosscheck = {
            "status": "not_applicable_nonproduction_fixture_frame"
        }
    return {
        "schema_version": STUDY_REPORT_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "source": {
            **manifest["source"],
            "source_manifest_sha256": _sha256(acquisition_manifest_bytes),
            "source_manifest_bytes": len(acquisition_manifest_bytes),
        },
        "patch_only_feature_freeze": feature_freeze,
        "official_results_crosscheck": official_results_crosscheck,
        "canonical_dataset_crosscheck": canonical_dataset_crosscheck,
        "sampling_frame": {
            "definition": (
                f"All {expected_count} instance prefixes returned by the complete pinned "
                f"S3 delimiter listing under {ROOT_PREFIX}"
            ),
            "candidate_count": len(rows),
            "analyzable_candidate_count": len(candidates),
            "mandatory_quarantine_count": len(rows) - len(candidates),
            "repository_count": len({item.repository for item in rows}),
            "repository_distribution": repository_counts,
            "largest_repository_fraction": repository_counts[0]["frame_fraction"],
            "top_three_repository_fraction": sum(
                item["frame_fraction"] for item in repository_counts[:3]
            ),
            "reference_free_language_counts": dict(sorted(language_counts.items())),
            "hosted_harness_resolved_count": resolved_count,
            "hosted_harness_failure_count": failure_count,
            "hosted_harness_outcome_unavailable_count": missing_outcome_count,
            "hosted_harness_failure_prevalence_bounds_over_full_frame": {
                "best_case_unknown_labels_resolved": failure_count / len(rows),
                "worst_case_unknown_labels_failed": (
                    failure_count + missing_outcome_count
                ) / len(rows),
            },
            "missing_patch_count": sum(
                row.patch_availability == "missing_from_complete_object_listing"
                for row in rows
            ),
            "patch_download_error_count": sum(
                row.patch_availability == "download_error" for row in rows
            ),
            "malformed_patch_count": malformed_patch_count,
            "missing_report_count": sum(
                row.report_availability == "missing_from_complete_object_listing"
                for row in rows
            ),
            "report_download_error_count": sum(
                row.report_availability == "download_error" for row in rows
            ),
            "malformed_report_count": malformed_report_count,
            "budget_counts": budgets,
            "budget_fractions_requested": [float(item) for item in budget_fractions],
        },
        "policy_definitions": policy_definitions,
        "post_hoc_discrimination_diagnostic": (
            _post_hoc_discrimination_diagnostic(rows)
        ),
        "policies": policies,
        "candidates": [_candidate_record(row) for row in rows],
        "scientific_status": {
            "submission_checked": False,
            "independent_reexecution": False,
            "actual_repository_or_test_execution_in_this_study": False,
            "retrospective_hosted_label_reveal_simulation": True,
            "independent_truth": False,
            "prospective": False,
            "randomized_policy_assignment": False,
            "single_submission": True,
            "single_model_scaffold_pass_at_1": True,
            "one_candidate_per_task_confounding": True,
            "complete_finite_prefix_frame": True,
            "fully_observed_hosted_outcomes": missing_outcome_count == 0,
            "retrospective_development_evidence": True,
            "supports_hypotheses_h1_to_h6": False,
            "pinned_submission_metadata_and_results_crosscheck": (
                official_results_crosscheck["status"]
            ),
            "canonical_dataset_base_commit_crosscheck": (
                canonical_dataset_crosscheck
            ),
            "estimand": (
                "Allocation performance for predicting this submission's unchecked hosted "
                "SWE-bench harness resolved label, not semantic correctness or oracle validity."
            ),
            "claim_boundary": (
                "Exact finite-frame descriptive development evidence against hosted, unchecked "
                "labels. It is not a calibrated risk guarantee, causal policy evaluation, "
                "independent benchmark audit, semantic-correctness result, or population estimate. "
                "With one candidate per task, candidate risk is confounded with task/repository "
                "difficulty and cannot identify within-task rollout-selection performance."
            ),
        },
    }


def _parse_budget_fractions(value: str) -> tuple[float, ...]:
    try:
        fractions = tuple(float(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("budget fractions must be comma-separated numbers") from exc
    if not fractions:
        raise argparse.ArgumentTypeError("at least one budget fraction is required")
    return fractions


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire and analyze the pinned hosted SWE-bench development study"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    acquire = subparsers.add_parser("acquire", help="atomically acquire the pinned corpus")
    acquire.add_argument("--artifact-dir", type=pathlib.Path, required=True)
    acquire.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    acquire.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    acquire.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    acquire.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)

    analyze = subparsers.add_parser("analyze", help="analyze a complete local acquisition")
    analyze.add_argument("--artifact-dir", type=pathlib.Path, required=True)
    analyze.add_argument("--output", type=pathlib.Path, required=True)
    analyze.add_argument(
        "--budget-fractions",
        type=_parse_budget_fractions,
        default=DEFAULT_BUDGET_FRACTIONS,
    )
    analyze.add_argument("--random-seed", type=int, default=DEFAULT_RANDOM_SEED)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if args.command == "acquire":
            result = acquire_corpus(
                args.artifact_dir,
                workers=args.workers,
                retries=args.retries,
                timeout_seconds=args.timeout_seconds,
                maximum_total_bytes=args.max_total_bytes,
            )
            print(strict_json_dumps(result["totals"], indent=2))
            return
        result = analyze_study(
            args.artifact_dir,
            budget_fractions=args.budget_fractions,
            random_seed=args.random_seed,
        )
        atomic_write(args.output, strict_json_dumps(result, indent=2) + "\n")
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"hosted outcome study failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
