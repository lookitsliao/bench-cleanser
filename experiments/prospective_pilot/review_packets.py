#!/usr/bin/env python3
"""Build and verify structurally blinded prospective-review packets.

The generator is deterministic and deliberately narrow.  It requires an
externally frozen exact-frame digest, projects only matching task/patch
identities, removes cost, producer identity, and directional evidence status,
binds every embedded byte string to SHA-256, and emits one packet per opaque
candidate plus a content-addressed manifest.  It cannot determine whether
free-form source text itself reveals a model or submission; a named opaque-map
custodian must attest to that residual content-level boundary before the
packets are released to reviewers.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import pathlib
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from bench_cleanser.verification.models import EvidenceKind, EvidenceStatus

STUDY_ID = "matched-24-independent-evidence-development-pilot-v2"
SOURCE_SCHEMA_VERSION = "prospective-pilot-review-source-0.1.0"
PACKET_SCHEMA_VERSION = "prospective-pilot-review-packet-0.1.0"
MANIFEST_SCHEMA_VERSION = "prospective-pilot-review-packet-manifest-0.2.0"
FRAME_MANIFEST_SCHEMA_VERSION = "prospective-pilot-frame-manifest-0.1.0"
FRAME_MANIFEST_STATUS = "frozen_uncommitted"
GENERATOR_LOGICAL_PATH = "experiments/prospective_pilot/review_packets.py"

CANDIDATES_PER_TASK = 3
EXPECTED_TASK_COUNT = 22
EXPECTED_CANDIDATE_COUNT = EXPECTED_TASK_COUNT * CANDIDATES_PER_TASK
MIN_BLINDING_KEY_BYTES = 32
MAX_BLINDING_KEY_BYTES = 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_FRAME_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_PACKET_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_CONTEXT_FILES = 256
MAX_EVIDENCE_EVENTS = 32
MAX_ARTIFACTS_PER_EVENT = 16

EXPECTED_EXCLUDED_TASK_CLUSTERS = (
    "sympy__sympy-15976",
    "sphinx-doc__sphinx-8475",
)
EXPECTED_SOURCE_FEATURE_FREEZE: Mapping[str, str | int] = MappingProxyType({
    "logical_name": "matched-rollout-v2-repaired-feature-freeze",
    "bytes": 301852,
    "sha256": "b01e8c9408acce759b75bd299f4323a37398e417e80a97ef52f09b8a14abc01c",
    "selected_instance_ids_sha256": (
        "601dfd7774d58876b42240e4f98e897c19a55356eccca67a39f81a4c7299ca32"
    ),
    "selected_task_identities_sha256": (
        "4521fcca1866d783919b9e3899e0c6e679f2a4c790e63420c2747abb6716f4eb"
    ),
})

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_CANDIDATE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TASK_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_MEDIA_TYPES = {"application/json", "text/plain"}
_ARTIFACT_ROLES = {
    "diagnostic",
    "report",
    "static_finding",
    "stderr",
    "stdout",
}
_SOURCE_CLASS_BY_KIND = {
    EvidenceKind.STATIC: "deterministic_static",
    EvidenceKind.SEMANTIC: "masked_semantic",
    EvidenceKind.TARGETED_EXECUTION: "targeted_execution",
    EvidenceKind.FULL_EXECUTION: "full_execution",
    EvidenceKind.ORACLE_HARDENING: "oracle_hardening",
}
_PROHIBITED_CONTENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"submission[ _-]?name",
        r"model[ _-]?name",
        r"hosted[ _-]?outcome",
        r"gold[ _-]?patch",
        r"official[ _-]?resolved[ _-]?label",
        r"router[ _-]?terminal[ _-]?decision",
        r"other[ _-]?reviewer[ _-]?labels?",
        r"candidate[ _-]?priority[ _-]?order",
        r"prospective[ _-]?analysis[ _-]?outputs?",
        r"\bsupports[ _-]?correct\b",
        r"\bsupports[ _-]?incorrect\b",
        r"\bclaude(?:[- _]?[0-9a-z.]+)?\b",
        r"\bgpt(?:[- _]?[0-9a-z.]+)?\b",
        r"\bkimi(?:[- _]?[0-9a-z.]+)?\b",
        r"\bopenhands\b",
    )
)


class PacketError(ValueError):
    """A packet source, packet bundle, or blinding projection is invalid."""


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PacketError(f"{field} must be a JSON object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise PacketError(f"{field} must be a JSON array")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        raise PacketError(
            f"{field} fields differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PacketError(f"{field} must be a string")
    if not allow_empty and not value:
        raise PacketError(f"{field} must be non-empty")
    if "\x00" in value:
        raise PacketError(f"{field} cannot contain NUL")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PacketError(f"{field} must be an integer at least {minimum}")
    return value


def _sha256(value: Any, field: str) -> str:
    result = _string(value, field)
    if _SHA256_RE.fullmatch(result) is None:
        raise PacketError(f"{field} must be a lowercase SHA-256")
    return result


def _digest(payload: bytes | str) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(raw).hexdigest()


def _blinding_key(value: bytes) -> bytes:
    if not isinstance(value, bytes) or not MIN_BLINDING_KEY_BYTES <= len(value) <= MAX_BLINDING_KEY_BYTES:
        raise PacketError(
            f"blinding key must contain {MIN_BLINDING_KEY_BYTES}-"
            f"{MAX_BLINDING_KEY_BYTES} bytes"
        )
    return value


def _commitment(blinding_key: bytes, domain: str, *parts: str) -> str:
    key = _blinding_key(blinding_key)
    payload = bytearray(domain.encode("utf-8"))
    for part in parts:
        encoded = part.encode("utf-8")
        payload.extend(len(encoded).to_bytes(8, "big"))
        payload.extend(encoded)
    return hmac.new(key, bytes(payload), hashlib.sha256).hexdigest()


def derive_candidate_id(
    blinding_key: bytes,
    opaque_task_id: str,
    candidate_patch_sha256: str,
) -> str:
    """Derive the source-bound opaque candidate commitment."""

    return "sha256:" + _commitment(
        blinding_key,
        "bench-cleanser/prospective-review/candidate/v1",
        opaque_task_id,
        candidate_patch_sha256,
    )


def derive_event_id(
    blinding_key: bytes,
    opaque_candidate_id: str,
    event_without_id: Mapping[str, Any],
) -> str:
    """Derive the candidate-bound opaque evidence-event commitment."""

    return "sha256:" + _commitment(
        blinding_key,
        "bench-cleanser/prospective-review/evidence-event/v1",
        opaque_candidate_id,
        strict_json_dumps(event_without_id),
    )


def _canonical_bytes(value: Any) -> bytes:
    return (strict_json_dumps(value) + "\n").encode("utf-8")


def _canonical_digest(value: Any) -> str:
    return _digest(strict_json_dumps(value))


def _bounded_text(value: Any, field: str) -> str:
    result = _string(value, field)
    if len(result.encode("utf-8")) > MAX_TEXT_BYTES:
        raise PacketError(f"{field} exceeds the {MAX_TEXT_BYTES}-byte limit")
    for pattern in _PROHIBITED_CONTENT_PATTERNS:
        if pattern.search(result) is not None:
            raise PacketError(f"{field} contains a prohibited blinding marker")
    return result


def _scan_blinding_marker(value: str, field: str) -> None:
    for pattern in _PROHIBITED_CONTENT_PATTERNS:
        if pattern.search(value) is not None:
            raise PacketError(f"{field} contains a prohibited blinding marker")


def _opaque_task_id(value: Any, field: str) -> str:
    result = _string(value, field)
    if _TASK_RE.fullmatch(result) is None:
        raise PacketError(f"{field} must be an opaque canonical identifier")
    lowered = re.sub(r"[^a-z0-9]+", "", result.casefold())
    for fragment in ("claude", "gpt", "hosted", "kimi", "model", "submission"):
        if fragment in lowered:
            raise PacketError(f"{field} may encode a producer or hosted identity")
    return result


def _opaque_candidate_id(value: Any, field: str) -> str:
    result = _string(value, field)
    if _CANDIDATE_RE.fullmatch(result) is None:
        raise PacketError(f"{field} must be an opaque sha256:<digest> identifier")
    return result


@dataclass(frozen=True)
class _FrozenFrame:
    identity: dict[str, Any]
    task_candidates: tuple[tuple[str, tuple[str, ...]], ...]


def _validated_frozen_frame(
    frame_manifest_bytes: bytes,
    *,
    expected_frame_manifest_sha256: str,
) -> _FrozenFrame:
    if not isinstance(frame_manifest_bytes, bytes):
        raise PacketError("frame manifest must be supplied as bytes")
    if not frame_manifest_bytes or len(frame_manifest_bytes) > MAX_FRAME_MANIFEST_BYTES:
        raise PacketError("frame manifest has an invalid byte count")
    expected_digest = _sha256(
        expected_frame_manifest_sha256,
        "expected frame-manifest SHA-256",
    )
    actual_digest = _digest(frame_manifest_bytes)
    if not hmac.compare_digest(actual_digest, expected_digest):
        raise PacketError("frame manifest differs from its external freeze digest")
    try:
        frame_text = frame_manifest_bytes.decode("utf-8")
        frame_value = strict_json_loads(frame_text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PacketError("frame manifest is not strict UTF-8 JSON") from exc
    frame = _object(frame_value, "frame manifest")
    _exact_fields(
        frame,
        {
            "candidate_count",
            "candidate_ids_sha256",
            "candidates_per_task",
            "excluded_task_clusters",
            "schema_version",
            "source_feature_freeze",
            "status",
            "study_id",
            "task_count",
            "task_ids_sha256",
            "tasks",
            "tasks_sha256",
        },
        "frame manifest",
    )
    if (
        frame["schema_version"] != FRAME_MANIFEST_SCHEMA_VERSION
        or frame["study_id"] != STUDY_ID
        or frame["status"] != FRAME_MANIFEST_STATUS
    ):
        raise PacketError("frame manifest schema, study, or frozen status differs")

    source_freeze_raw = _object(
        frame["source_feature_freeze"],
        "frame manifest.source_feature_freeze",
    )
    _exact_fields(
        source_freeze_raw,
        {
            "bytes",
            "logical_name",
            "selected_instance_ids_sha256",
            "selected_task_identities_sha256",
            "sha256",
        },
        "frame manifest.source_feature_freeze",
    )
    source_freeze = {
        "bytes": _integer(
            source_freeze_raw["bytes"],
            "frame manifest.source_feature_freeze.bytes",
            minimum=1,
        ),
        "logical_name": _string(
            source_freeze_raw["logical_name"],
            "frame manifest.source_feature_freeze.logical_name",
        ),
        "selected_instance_ids_sha256": _sha256(
            source_freeze_raw["selected_instance_ids_sha256"],
            "frame manifest.source_feature_freeze.selected_instance_ids_sha256",
        ),
        "selected_task_identities_sha256": _sha256(
            source_freeze_raw["selected_task_identities_sha256"],
            "frame manifest.source_feature_freeze.selected_task_identities_sha256",
        ),
        "sha256": _sha256(
            source_freeze_raw["sha256"],
            "frame manifest.source_feature_freeze.sha256",
        ),
    }
    if source_freeze != EXPECTED_SOURCE_FEATURE_FREEZE:
        raise PacketError("frame manifest source-feature-freeze identity differs")

    exclusions = tuple(
        _opaque_task_id(item, f"frame manifest.excluded_task_clusters[{index}]")
        for index, item in enumerate(
            _array(
                frame["excluded_task_clusters"],
                "frame manifest.excluded_task_clusters",
            )
        )
    )
    if exclusions != EXPECTED_EXCLUDED_TASK_CLUSTERS:
        raise PacketError("frame manifest exclusions differ from the frozen protocol")

    task_count = _integer(frame["task_count"], "frame manifest.task_count", minimum=1)
    candidates_per_task = _integer(
        frame["candidates_per_task"],
        "frame manifest.candidates_per_task",
        minimum=1,
    )
    candidate_count = _integer(
        frame["candidate_count"],
        "frame manifest.candidate_count",
        minimum=1,
    )
    if (
        task_count != EXPECTED_TASK_COUNT
        or candidates_per_task != CANDIDATES_PER_TASK
        or candidate_count != EXPECTED_CANDIDATE_COUNT
        or candidate_count != task_count * candidates_per_task
    ):
        raise PacketError("frame manifest counts differ from the frozen study scope")

    tasks_raw = _array(frame["tasks"], "frame manifest.tasks")
    if len(tasks_raw) != task_count:
        raise PacketError("frame manifest task array count differs")
    normalized_tasks: list[dict[str, Any]] = []
    task_candidates: list[tuple[str, tuple[str, ...]]] = []
    task_ids: list[str] = []
    all_candidate_ids: list[str] = []
    for task_index, raw_task in enumerate(tasks_raw):
        field = f"frame manifest.tasks[{task_index}]"
        task = _object(raw_task, field)
        _exact_fields(task, {"candidate_ids", "task_id"}, field)
        task_id = _opaque_task_id(task["task_id"], f"{field}.task_id")
        candidate_ids = tuple(
            _opaque_candidate_id(item, f"{field}.candidate_ids[{candidate_index}]")
            for candidate_index, item in enumerate(
                _array(task["candidate_ids"], f"{field}.candidate_ids")
            )
        )
        if (
            len(candidate_ids) != candidates_per_task
            or candidate_ids != tuple(sorted(set(candidate_ids)))
        ):
            raise PacketError(
                f"{field}.candidate_ids must contain three unique sorted patch identities"
            )
        if task_id in exclusions:
            raise PacketError(f"{field}.task_id is an excluded pre-freeze task")
        task_ids.append(task_id)
        all_candidate_ids.extend(candidate_ids)
        normalized_tasks.append({
            "candidate_ids": list(candidate_ids),
            "task_id": task_id,
        })
        task_candidates.append((task_id, candidate_ids))
    if task_ids != sorted(set(task_ids)):
        raise PacketError("frame manifest task IDs must be unique and sorted")
    if len(all_candidate_ids) != len(set(all_candidate_ids)):
        raise PacketError("frame manifest patch identities must be study-wide unique")

    declared_task_ids_digest = _sha256(
        frame["task_ids_sha256"],
        "frame manifest.task_ids_sha256",
    )
    declared_candidate_ids_digest = _sha256(
        frame["candidate_ids_sha256"],
        "frame manifest.candidate_ids_sha256",
    )
    declared_tasks_digest = _sha256(
        frame["tasks_sha256"],
        "frame manifest.tasks_sha256",
    )
    if not hmac.compare_digest(
        declared_task_ids_digest,
        _canonical_digest(task_ids),
    ):
        raise PacketError("frame manifest task_ids_sha256 is not canonical")
    if not hmac.compare_digest(
        declared_candidate_ids_digest,
        _canonical_digest(sorted(all_candidate_ids)),
    ):
        raise PacketError("frame manifest candidate_ids_sha256 is not canonical")
    if not hmac.compare_digest(
        declared_tasks_digest,
        _canonical_digest(normalized_tasks),
    ):
        raise PacketError("frame manifest tasks_sha256 is not canonical")

    identity = {
        "bytes": len(frame_manifest_bytes),
        "candidate_count": candidate_count,
        "candidate_ids_sha256": declared_candidate_ids_digest,
        "candidates_per_task": candidates_per_task,
        "excluded_task_clusters": list(exclusions),
        "schema_version": FRAME_MANIFEST_SCHEMA_VERSION,
        "sha256": actual_digest,
        "source_feature_freeze": source_freeze,
        "status": FRAME_MANIFEST_STATUS,
        "study_id": STUDY_ID,
        "task_count": task_count,
        "task_ids_sha256": declared_task_ids_digest,
        "tasks_sha256": declared_tasks_digest,
    }
    return _FrozenFrame(
        identity=identity,
        task_candidates=tuple(task_candidates),
    )


def validate_frame_manifest(
    frame_manifest_bytes: bytes,
    *,
    expected_frame_manifest_sha256: str,
) -> dict[str, Any]:
    """Validate and summarize an externally frozen exact frame manifest."""

    return _validated_frozen_frame(
        frame_manifest_bytes,
        expected_frame_manifest_sha256=expected_frame_manifest_sha256,
    ).identity


def _relative_path(value: Any, field: str) -> str:
    raw = _string(value, field)
    _scan_blinding_marker(raw, field)
    if "\\" in raw:
        raise PacketError(f"{field} must use POSIX separators")
    path = pathlib.PurePosixPath(raw)
    if (
        path.is_absolute()
        or raw != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or ".git" in path.parts
    ):
        raise PacketError(f"{field} must be a confined canonical relative path")
    return raw


def _project_blob(value: Any, field: str, *, path_required: bool) -> dict[str, Any]:
    data = _object(value, field)
    expected = {"bytes", "content", "media_type", "role", "sha256"}
    if path_required:
        expected.add("path")
    _exact_fields(data, expected, field)
    content = _bounded_text(data["content"], f"{field}.content")
    content_bytes = content.encode("utf-8")
    declared_bytes = _integer(data["bytes"], f"{field}.bytes")
    declared_digest = _sha256(data["sha256"], f"{field}.sha256")
    if declared_bytes != len(content_bytes) or declared_digest != _digest(content_bytes):
        raise PacketError(f"{field} byte identity differs from its content")
    media_type = _string(data["media_type"], f"{field}.media_type")
    if media_type not in _MEDIA_TYPES:
        raise PacketError(f"{field}.media_type is not allowed")
    role = _string(data["role"], f"{field}.role")
    if role not in _ARTIFACT_ROLES:
        raise PacketError(f"{field}.role is not allowed")
    result: dict[str, Any] = {
        "bytes": declared_bytes,
        "content": content,
        "media_type": media_type,
        "role": role,
        "sha256": declared_digest,
    }
    if path_required:
        result["path"] = _relative_path(data["path"], f"{field}.path")
    return result


def _project_evidence_event(
    value: Any,
    field: str,
    *,
    blinding_key: bytes,
    candidate_id: str,
    source_has_status: bool,
) -> dict[str, Any]:
    data = _object(value, field)
    expected_fields = {"artifacts", "event_id", "kind", "source_class"}
    if source_has_status:
        expected_fields.add("status")
    _exact_fields(
        data,
        expected_fields,
        field,
    )
    event_id = _opaque_candidate_id(data["event_id"], f"{field}.event_id")
    try:
        kind = EvidenceKind(_string(data["kind"], f"{field}.kind"))
    except ValueError as exc:
        raise PacketError(f"{field} contains an unknown evidence enum") from exc
    status: EvidenceStatus | None = None
    if source_has_status:
        try:
            status = EvidenceStatus(_string(data["status"], f"{field}.status"))
        except ValueError as exc:
            raise PacketError(f"{field} contains an unknown evidence enum") from exc
    if kind not in _SOURCE_CLASS_BY_KIND:
        raise PacketError(f"{field}.kind cannot enter a blinded review packet")
    source_class = _string(data["source_class"], f"{field}.source_class")
    if source_class != _SOURCE_CLASS_BY_KIND[kind]:
        raise PacketError(f"{field}.source_class does not match its evidence kind")
    artifacts_raw = _array(data["artifacts"], f"{field}.artifacts")
    if len(artifacts_raw) > MAX_ARTIFACTS_PER_EVENT:
        raise PacketError(f"{field} has too many artifacts")
    if source_has_status and not artifacts_raw and status != EvidenceStatus.UNAVAILABLE:
        raise PacketError(f"{field} requires raw artifacts unless unavailable")
    artifacts = [
        _project_blob(item, f"{field}.artifacts[{index}]", path_required=False)
        for index, item in enumerate(artifacts_raw)
    ]
    artifact_ids = [(item["role"], item["sha256"]) for item in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise PacketError(f"{field} contains duplicate artifact identities")
    artifacts.sort(key=lambda item: (item["role"], item["sha256"]))
    projected_without_id = {
        "artifacts": artifacts,
        "kind": kind.value,
        "source_class": source_class,
    }
    expected_event_id = derive_event_id(
        blinding_key,
        candidate_id,
        projected_without_id,
    )
    if not hmac.compare_digest(event_id, expected_event_id):
        raise PacketError(f"{field}.event_id is not the bound opaque commitment")
    return {**projected_without_id, "event_id": event_id}


def _project_task_context(value: Any, field: str) -> dict[str, Any]:
    data = _object(value, field)
    _exact_fields(data, {"base_commit", "problem_statement", "repository_context"}, field)
    base_commit = _string(data["base_commit"], f"{field}.base_commit")
    if _GIT_OID_RE.fullmatch(base_commit) is None:
        raise PacketError(f"{field}.base_commit must be a full Git object ID")
    context_raw = _array(data["repository_context"], f"{field}.repository_context")
    if not context_raw or len(context_raw) > MAX_CONTEXT_FILES:
        raise PacketError(
            f"{field}.repository_context must contain 1-{MAX_CONTEXT_FILES} files"
        )
    context = [
        _project_blob(item, f"{field}.repository_context[{item_index}]", path_required=True)
        for item_index, item in enumerate(context_raw)
    ]
    paths = [item["path"] for item in context]
    if len(paths) != len(set(paths)):
        raise PacketError(f"{field}.repository_context contains duplicate paths")
    context.sort(key=lambda item: item["path"])
    return {
        "base_commit": base_commit,
        "problem_statement": _bounded_text(data["problem_statement"], f"{field}.problem_statement"),
        "repository_context": context,
    }


def _project_task(
    value: Any,
    index: int,
    *,
    blinding_key: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    field = f"source.tasks[{index}]"
    data = _object(value, field)
    _exact_fields(
        data,
        {
            "base_commit",
            "candidates",
            "opaque_task_id",
            "problem_statement",
            "repository_context",
        },
        field,
    )
    task_id = _opaque_task_id(data["opaque_task_id"], f"{field}.opaque_task_id")
    task_context = _project_task_context(
        {
            "base_commit": data["base_commit"],
            "problem_statement": data["problem_statement"],
            "repository_context": data["repository_context"],
        },
        f"{field}.task_context",
    )

    candidates_raw = _array(data["candidates"], f"{field}.candidates")
    if len(candidates_raw) != CANDIDATES_PER_TASK:
        raise PacketError(f"{field} must contain exactly three candidates")
    candidates: list[dict[str, Any]] = []
    for candidate_index, candidate_value in enumerate(candidates_raw):
        candidate_field = f"{field}.candidates[{candidate_index}]"
        candidate = _object(candidate_value, candidate_field)
        _exact_fields(
            candidate,
            {
                "candidate_patch",
                "candidate_patch_sha256",
                "evidence_events",
                "opaque_candidate_id",
            },
            candidate_field,
        )
        patch = _bounded_text(candidate["candidate_patch"], f"{candidate_field}.candidate_patch")
        patch_digest = _sha256(
            candidate["candidate_patch_sha256"],
            f"{candidate_field}.candidate_patch_sha256",
        )
        if patch_digest != _digest(patch):
            raise PacketError(f"{candidate_field}.candidate_patch_sha256 differs")
        candidate_id = _opaque_candidate_id(
            candidate["opaque_candidate_id"],
            f"{candidate_field}.opaque_candidate_id",
        )
        expected_candidate_id = derive_candidate_id(
            blinding_key,
            task_id,
            patch_digest,
        )
        if not hmac.compare_digest(candidate_id, expected_candidate_id):
            raise PacketError(
                f"{candidate_field}.opaque_candidate_id is not the bound commitment"
            )
        events_raw = _array(candidate["evidence_events"], f"{candidate_field}.evidence_events")
        if not events_raw or len(events_raw) > MAX_EVIDENCE_EVENTS:
            raise PacketError(
                f"{candidate_field} must contain 1-{MAX_EVIDENCE_EVENTS} evidence events"
            )
        events = [
            _project_evidence_event(
                item,
                f"{candidate_field}.evidence_events[{event_index}]",
                blinding_key=blinding_key,
                candidate_id=candidate_id,
                source_has_status=True,
            )
            for event_index, item in enumerate(events_raw)
        ]
        event_ids = [event["event_id"] for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise PacketError(f"{candidate_field} contains duplicate event IDs")
        events.sort(key=lambda event: event["event_id"])
        candidates.append({
            "candidate_patch": patch,
            "candidate_patch_sha256": patch_digest,
            "evidence_events": events,
            "opaque_candidate_id": candidate_id,
        })
    candidate_ids = [candidate["opaque_candidate_id"] for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise PacketError(f"{field} contains duplicate opaque candidate IDs")
    candidates.sort(key=lambda candidate: candidate["opaque_candidate_id"])
    return {"opaque_task_id": task_id, "task_context": task_context}, candidates


def _validate_source_frame_membership(
    source: dict[str, Any],
    frame: _FrozenFrame,
) -> list[Any]:
    _exact_fields(source, {"schema_version", "study_id", "tasks"}, "source")
    if source["schema_version"] != SOURCE_SCHEMA_VERSION or source["study_id"] != STUDY_ID:
        raise PacketError("source schema or study identity differs")
    tasks_raw = _array(source["tasks"], "source.tasks")
    if len(tasks_raw) != frame.identity["task_count"]:
        raise PacketError("source.tasks count differs from the exact frozen frame")
    actual: dict[str, tuple[str, ...]] = {}
    for task_index, raw_task in enumerate(tasks_raw):
        field = f"source.tasks[{task_index}]"
        task = _object(raw_task, field)
        _exact_fields(
            task,
            {
                "base_commit",
                "candidates",
                "opaque_task_id",
                "problem_statement",
                "repository_context",
            },
            field,
        )
        task_id = _opaque_task_id(task["opaque_task_id"], f"{field}.opaque_task_id")
        if task_id in actual:
            raise PacketError("source.tasks contains a duplicate opaque task ID")
        candidates_raw = _array(task["candidates"], f"{field}.candidates")
        if len(candidates_raw) != CANDIDATES_PER_TASK:
            raise PacketError(f"{field} must contain exactly three candidates")
        patch_ids: list[str] = []
        for candidate_index, raw_candidate in enumerate(candidates_raw):
            candidate_field = f"{field}.candidates[{candidate_index}]"
            candidate = _object(raw_candidate, candidate_field)
            _exact_fields(
                candidate,
                {
                    "candidate_patch",
                    "candidate_patch_sha256",
                    "evidence_events",
                    "opaque_candidate_id",
                },
                candidate_field,
            )
            patch = _bounded_text(
                candidate["candidate_patch"],
                f"{candidate_field}.candidate_patch",
            )
            patch_digest = _sha256(
                candidate["candidate_patch_sha256"],
                f"{candidate_field}.candidate_patch_sha256",
            )
            if not hmac.compare_digest(patch_digest, _digest(patch)):
                raise PacketError(f"{candidate_field}.candidate_patch_sha256 differs")
            patch_ids.append(f"sha256:{patch_digest}")
        if len(patch_ids) != len(set(patch_ids)):
            raise PacketError(f"{field} contains duplicate candidate patch identities")
        actual[task_id] = tuple(sorted(patch_ids))
    expected = dict(frame.task_candidates)
    if actual != expected:
        raise PacketError(
            "source task IDs and per-task candidate patch SHA-256 sets differ "
            "from the exact frozen frame"
        )
    return tasks_raw


def _project_source_for_frame(
    value: Any,
    *,
    blinding_key: bytes,
    frame: _FrozenFrame,
) -> list[dict[str, Any]]:
    source = _object(value, "source")
    tasks_raw = _validate_source_frame_membership(source, frame)
    packets: list[dict[str, Any]] = []
    seen_tasks: set[str] = set()
    seen_candidates: set[str] = set()
    seen_events: set[str] = set()
    for index, task_value in enumerate(tasks_raw):
        task, candidates = _project_task(
            task_value,
            index,
            blinding_key=blinding_key,
        )
        task_id = task["opaque_task_id"]
        if task_id in seen_tasks:
            raise PacketError("source.tasks contains a duplicate opaque task ID")
        seen_tasks.add(task_id)
        for candidate in candidates:
            candidate_id = candidate["opaque_candidate_id"]
            if candidate_id in seen_candidates:
                raise PacketError("opaque candidate IDs must be study-wide unique")
            seen_candidates.add(candidate_id)
            for event in candidate["evidence_events"]:
                event_id = event["event_id"]
                if event_id in seen_events:
                    raise PacketError("opaque event IDs must be study-wide unique")
                seen_events.add(event_id)
            packets.append({
                "candidate_patch": candidate["candidate_patch"],
                "candidate_patch_sha256": candidate["candidate_patch_sha256"],
                "evidence_events": candidate["evidence_events"],
                "opaque_candidate_id": candidate_id,
                "opaque_task_id": task_id,
                "schema_version": PACKET_SCHEMA_VERSION,
                "study_id": STUDY_ID,
                "task_context": task["task_context"],
            })
    packets.sort(key=lambda packet: (packet["opaque_task_id"], packet["opaque_candidate_id"]))
    if len(packets) != EXPECTED_CANDIDATE_COUNT:
        raise PacketError("projected packet count differs from the frozen study scope")
    return packets


def project_source(
    value: Any,
    *,
    blinding_key: bytes,
    frame_manifest_bytes: bytes,
    expected_frame_manifest_sha256: str,
) -> list[dict[str, Any]]:
    """Validate exact source/frame membership and return canonical packets."""

    frame = _validated_frozen_frame(
        frame_manifest_bytes,
        expected_frame_manifest_sha256=expected_frame_manifest_sha256,
    )
    return _project_source_for_frame(
        value,
        blinding_key=blinding_key,
        frame=frame,
    )


def _generator_sha256() -> str:
    return _digest(pathlib.Path(__file__).read_bytes())


def _render_bundle(
    source_bytes: bytes,
    *,
    blinding_key: bytes,
    frame_manifest_bytes: bytes,
    expected_frame_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, bytes], bytes]:
    frame = _validated_frozen_frame(
        frame_manifest_bytes,
        expected_frame_manifest_sha256=expected_frame_manifest_sha256,
    )
    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise PacketError(f"source exceeds the {MAX_SOURCE_BYTES}-byte limit")
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PacketError("source must be UTF-8 JSON") from exc
    source_value = strict_json_loads(source_text)
    key = _blinding_key(blinding_key)
    packets = _project_source_for_frame(
        source_value,
        blinding_key=key,
        frame=frame,
    )
    canonical_source_sha256 = _digest(_canonical_bytes(source_value))
    rows: list[dict[str, Any]] = []
    packet_payloads: dict[str, bytes] = {}
    for packet in packets:
        task_hash = _digest(packet["opaque_task_id"])
        candidate_hash = packet["opaque_candidate_id"].removeprefix("sha256:")
        relative = f"packets/{task_hash}/{candidate_hash}.json"
        payload = _canonical_bytes(packet)
        if len(payload) > MAX_PACKET_BYTES:
            raise PacketError(f"packet {relative} exceeds the packet byte limit")
        context_digest = _digest(_canonical_bytes(packet["task_context"]))
        packet_payloads[relative] = payload
        rows.append({
            "bytes": len(payload),
            "logical_path": relative,
            "opaque_candidate_id": packet["opaque_candidate_id"],
            "opaque_task_id": packet["opaque_task_id"],
            "packet_sha256": _digest(payload),
            "task_context_sha256": context_digest,
        })
    manifest = {
        "blinding_key_sha256": _digest(key),
        "blinding_boundary": (
            "structural_allowlist_and_prohibited_marker_scan_only; "
            "named_custodian_content_attestation_still_required"
        ),
        "candidate_count": len(packets),
        "frame_manifest": frame.identity,
        "generator": {
            "logical_path": GENERATOR_LOGICAL_PATH,
            "sha256": _generator_sha256(),
        },
        "packets": rows,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_bytes_hmac_sha256": _commitment(
            key,
            "bench-cleanser/prospective-review/source-bytes/v1",
            _digest(source_bytes),
        ),
        "source_canonical_hmac_sha256": _commitment(
            key,
            "bench-cleanser/prospective-review/source-canonical/v1",
            canonical_source_sha256,
        ),
        "study_id": STUDY_ID,
        "task_count": len(packets) // CANDIDATES_PER_TASK,
    }
    manifest_payload = _canonical_bytes(manifest)
    return manifest, packet_payloads, manifest_payload


def build_bundle(
    source_bytes: bytes,
    output: pathlib.Path,
    *,
    blinding_key: bytes,
    frame_manifest_bytes: bytes,
    expected_frame_manifest_sha256: str,
) -> dict[str, Any]:
    """Build a deterministic packet directory at a new path."""

    manifest, packet_payloads, manifest_payload = _render_bundle(
        source_bytes,
        blinding_key=blinding_key,
        frame_manifest_bytes=frame_manifest_bytes,
        expected_frame_manifest_sha256=expected_frame_manifest_sha256,
    )
    if output.exists() or output.is_symlink():
        raise PacketError("output path already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = pathlib.Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for relative, payload in packet_payloads.items():
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        with (temporary / "packet-manifest.json").open("xb") as handle:
            handle.write(manifest_payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def _load_canonical_json(path: pathlib.Path, *, maximum_bytes: int, field: str) -> tuple[Any, bytes]:
    if path.is_symlink() or not path.is_file():
        raise PacketError(f"{field} must be a regular non-symlink file")
    payload = path.read_bytes()
    if not payload or len(payload) > maximum_bytes:
        raise PacketError(f"{field} has an invalid byte count")
    try:
        value = strict_json_loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PacketError(f"{field} is not strict UTF-8 JSON") from exc
    if payload != _canonical_bytes(value):
        raise PacketError(f"{field} is not canonical JSON")
    return value, payload


def _confined_bundle_path(root: pathlib.Path, relative: str) -> pathlib.Path:
    root_resolved = root.resolve(strict=True)
    candidate = root / relative
    current = root
    for part in pathlib.PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise PacketError(f"packet path {relative!r} contains a symlink")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise PacketError(f"packet path {relative!r} escapes or is missing") from exc
    return resolved


def verify_bundle(
    root: pathlib.Path,
    *,
    source_bytes: bytes,
    blinding_key: bytes,
    frame_manifest_bytes: bytes,
    expected_frame_manifest_sha256: str,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    """Verify packet bytes, paths, identities, and within-task context parity."""

    if root.is_symlink() or not root.is_dir():
        raise PacketError("bundle root must be a directory, not a symlink")
    expected_digest = _sha256(
        expected_manifest_sha256,
        "expected packet-manifest SHA-256",
    )
    manifest_value, manifest_payload = _load_canonical_json(
        root / "packet-manifest.json",
        maximum_bytes=MAX_PACKET_BYTES,
        field="packet manifest",
    )
    if not hmac.compare_digest(_digest(manifest_payload), expected_digest):
        raise PacketError("packet manifest differs from its external freeze digest")
    manifest = _object(manifest_value, "packet manifest")
    expected_manifest, expected_packet_payloads, expected_manifest_payload = _render_bundle(
        source_bytes,
        blinding_key=blinding_key,
        frame_manifest_bytes=frame_manifest_bytes,
        expected_frame_manifest_sha256=expected_frame_manifest_sha256,
    )
    if manifest_payload != expected_manifest_payload or manifest != expected_manifest:
        raise PacketError("packet manifest does not regenerate from the frozen source")
    _exact_fields(
        manifest,
        {
            "blinding_key_sha256",
            "blinding_boundary",
            "candidate_count",
            "frame_manifest",
            "generator",
            "packets",
            "schema_version",
            "source_bytes_hmac_sha256",
            "source_canonical_hmac_sha256",
            "study_id",
            "task_count",
        },
        "packet manifest",
    )
    if manifest["blinding_key_sha256"] != _digest(_blinding_key(blinding_key)):
        raise PacketError("packet manifest blinding-key commitment differs")
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION or manifest["study_id"] != STUDY_ID:
        raise PacketError("packet manifest identity differs")
    if manifest["blinding_boundary"] != (
        "structural_allowlist_and_prohibited_marker_scan_only; "
        "named_custodian_content_attestation_still_required"
    ):
        raise PacketError("packet manifest blinding boundary differs")
    _sha256(
        manifest["source_bytes_hmac_sha256"],
        "packet manifest source-bytes HMAC",
    )
    _sha256(
        manifest["source_canonical_hmac_sha256"],
        "packet manifest canonical-source HMAC",
    )
    frame_identity = _object(manifest["frame_manifest"], "packet manifest frame identity")
    _exact_fields(
        frame_identity,
        {
            "bytes",
            "candidate_count",
            "candidate_ids_sha256",
            "candidates_per_task",
            "excluded_task_clusters",
            "schema_version",
            "sha256",
            "source_feature_freeze",
            "status",
            "study_id",
            "task_count",
            "task_ids_sha256",
            "tasks_sha256",
        },
        "packet manifest frame identity",
    )
    if frame_identity != expected_manifest["frame_manifest"]:
        raise PacketError("packet manifest frame identity differs")
    generator = _object(manifest["generator"], "packet manifest generator")
    _exact_fields(generator, {"logical_path", "sha256"}, "packet manifest generator")
    if generator != {"logical_path": GENERATOR_LOGICAL_PATH, "sha256": _generator_sha256()}:
        raise PacketError("packet manifest generator identity differs")
    rows_raw = _array(manifest["packets"], "packet manifest packets")
    candidate_count = _integer(manifest["candidate_count"], "candidate_count", minimum=1)
    task_count = _integer(manifest["task_count"], "task_count", minimum=1)
    if (
        candidate_count != EXPECTED_CANDIDATE_COUNT
        or task_count != EXPECTED_TASK_COUNT
        or candidate_count != len(rows_raw)
        or candidate_count != task_count * CANDIDATES_PER_TASK
        or candidate_count != frame_identity["candidate_count"]
        or task_count != frame_identity["task_count"]
    ):
        raise PacketError("packet manifest counts differ")

    expected_files = {"packet-manifest.json"}
    seen_paths: set[str] = set()
    seen_candidates: set[str] = set()
    task_contexts: dict[str, set[str]] = {}
    task_candidate_counts: dict[str, int] = {}
    prior_order: tuple[str, str] | None = None
    for index, raw_row in enumerate(rows_raw):
        field = f"packet manifest packets[{index}]"
        row = _object(raw_row, field)
        _exact_fields(
            row,
            {
                "bytes",
                "logical_path",
                "opaque_candidate_id",
                "opaque_task_id",
                "packet_sha256",
                "task_context_sha256",
            },
            field,
        )
        relative = _relative_path(row["logical_path"], f"{field}.logical_path")
        if relative in seen_paths or not relative.startswith("packets/") or not relative.endswith(".json"):
            raise PacketError(f"{field}.logical_path is duplicate or outside packets/")
        seen_paths.add(relative)
        expected_files.add(relative)
        packet_value, payload = _load_canonical_json(
            _confined_bundle_path(root, relative),
            maximum_bytes=MAX_PACKET_BYTES,
            field=f"packet {relative}",
        )
        if payload != expected_packet_payloads.get(relative):
            raise PacketError(f"packet {relative} does not regenerate from frozen source")
        if len(payload) != _integer(row["bytes"], f"{field}.bytes", minimum=1):
            raise PacketError(f"{field}.bytes differs")
        if _digest(payload) != _sha256(row["packet_sha256"], f"{field}.packet_sha256"):
            raise PacketError(f"{field}.packet_sha256 differs")
        packet = _object(packet_value, f"packet {relative}")
        _exact_fields(
            packet,
            {
                "candidate_patch",
                "candidate_patch_sha256",
                "evidence_events",
                "opaque_candidate_id",
                "opaque_task_id",
                "schema_version",
                "study_id",
                "task_context",
            },
            f"packet {relative}",
        )
        if packet["schema_version"] != PACKET_SCHEMA_VERSION or packet["study_id"] != STUDY_ID:
            raise PacketError(f"packet {relative} identity differs")
        task_id = _opaque_task_id(packet["opaque_task_id"], f"packet {relative} task")
        candidate_id = _opaque_candidate_id(
            packet["opaque_candidate_id"], f"packet {relative} candidate"
        )
        if row["opaque_task_id"] != task_id or row["opaque_candidate_id"] != candidate_id:
            raise PacketError(f"packet {relative} identity differs from manifest")
        if candidate_id in seen_candidates:
            raise PacketError("packet manifest repeats an opaque candidate")
        seen_candidates.add(candidate_id)
        order = (task_id, candidate_id)
        if prior_order is not None and order <= prior_order:
            raise PacketError("packet manifest rows are not in canonical order")
        prior_order = order
        expected_relative = f"packets/{_digest(task_id)}/{candidate_id.removeprefix('sha256:')}.json"
        if relative != expected_relative:
            raise PacketError(f"packet {relative} path does not match opaque identities")
        patch = _bounded_text(packet["candidate_patch"], f"packet {relative} patch")
        if _digest(patch) != _sha256(
            packet["candidate_patch_sha256"], f"packet {relative} patch digest"
        ):
            raise PacketError(f"packet {relative} patch digest differs")
        if candidate_id != derive_candidate_id(
            blinding_key,
            task_id,
            packet["candidate_patch_sha256"],
        ):
            raise PacketError(f"packet {relative} candidate commitment differs")
        context = _project_task_context(
            packet["task_context"], f"packet {relative} task context"
        )
        if context != packet["task_context"]:
            raise PacketError(f"packet {relative} task context is not canonical")
        context_digest = _digest(_canonical_bytes(context))
        if context_digest != _sha256(
            row["task_context_sha256"], f"{field}.task_context_sha256"
        ):
            raise PacketError(f"packet {relative} task context digest differs")
        task_contexts.setdefault(task_id, set()).add(context_digest)
        task_candidate_counts[task_id] = task_candidate_counts.get(task_id, 0) + 1
        events = _array(packet["evidence_events"], f"packet {relative} evidence events")
        projected_events: list[dict[str, Any]] = []
        for event_index, event in enumerate(events):
            projected = _project_evidence_event(
                event,
                f"packet {relative}.evidence_events[{event_index}]",
                blinding_key=blinding_key,
                candidate_id=candidate_id,
                source_has_status=False,
            )
            if projected != event:
                raise PacketError(f"packet {relative} evidence is not canonical")
            projected_events.append(projected)
        if projected_events != sorted(projected_events, key=lambda event: event["event_id"]):
            raise PacketError(f"packet {relative} evidence order is not canonical")
    if any(value != CANDIDATES_PER_TASK for value in task_candidate_counts.values()):
        raise PacketError("every task must have exactly three packet candidates")
    if any(len(value) != 1 for value in task_contexts.values()):
        raise PacketError("candidate packets for one task do not share exact context")

    expected_directories = {"packets"}
    for relative in expected_files:
        parent = pathlib.PurePosixPath(relative).parent
        while parent.as_posix() not in {".", ""}:
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PacketError("packet bundle cannot contain symlinks")
        if path.is_file():
            actual_files.add(path.relative_to(root).as_posix())
        elif path.is_dir():
            actual_directories.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise PacketError("packet bundle contains a non-regular entry")
    if actual_files != expected_files:
        raise PacketError(
            f"packet bundle files differ: missing={sorted(expected_files - actual_files)}, "
            f"unknown={sorted(actual_files - expected_files)}"
        )
    if actual_directories != expected_directories:
        raise PacketError(
            "packet bundle directories differ: "
            f"missing={sorted(expected_directories - actual_directories)}, "
            f"unknown={sorted(actual_directories - expected_directories)}"
        )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build a new packet directory")
    build.add_argument("source", type=pathlib.Path)
    build.add_argument("output", type=pathlib.Path)
    build.add_argument("--blinding-key-file", type=pathlib.Path, required=True)
    build.add_argument("--frame-manifest", type=pathlib.Path, required=True)
    build.add_argument("--expected-frame-manifest-sha256", required=True)
    verify = subparsers.add_parser("verify", help="verify an existing packet directory")
    verify.add_argument("bundle", type=pathlib.Path)
    verify.add_argument("--source", type=pathlib.Path, required=True)
    verify.add_argument("--blinding-key-file", type=pathlib.Path, required=True)
    verify.add_argument("--frame-manifest", type=pathlib.Path, required=True)
    verify.add_argument("--expected-frame-manifest-sha256", required=True)
    verify.add_argument("--expected-manifest-sha256", required=True)
    return parser


def _read_blinding_key(path: pathlib.Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PacketError("blinding key must be a regular non-symlink file")
    return _blinding_key(path.read_bytes())


def _read_regular_bytes(
    path: pathlib.Path,
    *,
    field: str,
    maximum_bytes: int,
) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PacketError(f"{field} must be a regular non-symlink file")
    size = path.stat().st_size
    if size <= 0 or size > maximum_bytes:
        raise PacketError(f"{field} has an invalid byte count")
    payload = path.read_bytes()
    if len(payload) != size:
        raise PacketError(f"{field} changed while it was read")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        key = _read_blinding_key(args.blinding_key_file)
        frame_manifest_bytes = _read_regular_bytes(
            args.frame_manifest,
            field="frame manifest",
            maximum_bytes=MAX_FRAME_MANIFEST_BYTES,
        )
        if args.command == "build":
            source_bytes = _read_regular_bytes(
                args.source,
                field="source",
                maximum_bytes=MAX_SOURCE_BYTES,
            )
            result = build_bundle(
                source_bytes,
                args.output,
                blinding_key=key,
                frame_manifest_bytes=frame_manifest_bytes,
                expected_frame_manifest_sha256=(
                    args.expected_frame_manifest_sha256
                ),
            )
            manifest_sha256 = _digest(
                (args.output / "packet-manifest.json").read_bytes()
            )
        else:
            source_bytes = _read_regular_bytes(
                args.source,
                field="source",
                maximum_bytes=MAX_SOURCE_BYTES,
            )
            result = verify_bundle(
                args.bundle,
                source_bytes=source_bytes,
                blinding_key=key,
                frame_manifest_bytes=frame_manifest_bytes,
                expected_frame_manifest_sha256=(
                    args.expected_frame_manifest_sha256
                ),
                expected_manifest_sha256=args.expected_manifest_sha256,
            )
            manifest_sha256 = args.expected_manifest_sha256
    except (OSError, PacketError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(strict_json_dumps({
        "candidate_count": result["candidate_count"],
        "frame_manifest_sha256": result["frame_manifest"]["sha256"],
        "frame_tasks_sha256": result["frame_manifest"]["tasks_sha256"],
        "manifest_sha256": manifest_sha256,
        "schema_version": result["schema_version"],
        "study_id": result["study_id"],
        "task_count": result["task_count"],
        "verified": args.command == "verify",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
