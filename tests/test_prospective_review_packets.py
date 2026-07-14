"""Fail-closed contracts for prospective blinded review packets."""

from __future__ import annotations

import hashlib
import json
import pathlib
from copy import deepcopy
from typing import Any

import pytest

from bench_cleanser.verification._io import strict_json_dumps
from experiments.prospective_pilot.review_packets import (
    EXPECTED_CANDIDATE_COUNT,
    EXPECTED_EXCLUDED_TASK_CLUSTERS,
    EXPECTED_SOURCE_FEATURE_FREEZE,
    EXPECTED_TASK_COUNT,
    FRAME_MANIFEST_SCHEMA_VERSION,
    FRAME_MANIFEST_STATUS,
    MANIFEST_SCHEMA_VERSION,
    SOURCE_SCHEMA_VERSION,
    STUDY_ID,
    PacketError,
    build_bundle,
    derive_candidate_id,
    derive_event_id,
    main,
    project_source,
    validate_frame_manifest,
    verify_bundle,
)

_BLINDING_KEY = b"prospective-review-test-key-0001"
_CHECKED_IN_FRAME = (
    pathlib.Path(__file__).parents[1]
    / "experiments"
    / "prospective_pilot"
    / "frame_manifest.json"
)
_CHECKED_IN_FRAME_SHA256 = hashlib.sha256(_CHECKED_IN_FRAME.read_bytes()).hexdigest()


def _digest(value: str | bytes) -> str:
    payload = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _blob(
    content: str,
    *,
    role: str = "report",
    path: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "bytes": len(content.encode()),
        "content": content,
        "media_type": "text/plain",
        "role": role,
        "sha256": _digest(content),
    }
    if path is not None:
        value["path"] = path
    return value


def _source(*, task_count: int = EXPECTED_TASK_COUNT) -> dict[str, Any]:
    tasks = []
    candidate_counter = 1
    for task_index in range(task_count):
        task_id = f"opaque-task-{task_index:02d}"
        candidates = []
        for _ in range(3):
            patch = (
                "diff --git a/value.py b/value.py\n"
                "--- a/value.py\n"
                "+++ b/value.py\n"
                f"@@ -1 +1 @@\n-return {candidate_counter}\n+return {candidate_counter + 1}\n"
            )
            patch_digest = _digest(patch)
            candidate_id = derive_candidate_id(
                _BLINDING_KEY,
                task_id,
                patch_digest,
            )
            event_content = f"targeted check for opaque candidate {candidate_counter}\n"
            packet_event_without_id = {
                "artifacts": [_blob(event_content, role="stdout")],
                "kind": "targeted_execution",
                "source_class": "targeted_execution",
            }
            source_status = (
                "supports_correct"
                if candidate_counter % 2
                else "supports_incorrect"
            )
            candidates.append({
                "candidate_patch": patch,
                "candidate_patch_sha256": patch_digest,
                "evidence_events": [{
                    **packet_event_without_id,
                    "event_id": derive_event_id(
                        _BLINDING_KEY,
                        candidate_id,
                        packet_event_without_id,
                    ),
                    "status": source_status,
                }],
                "opaque_candidate_id": candidate_id,
            })
            candidate_counter += 1
        tasks.append({
            "base_commit": f"{task_index + 10:040x}",
            "candidates": candidates,
            "opaque_task_id": task_id,
            "problem_statement": f"Repair opaque behavior {task_index}.",
            "repository_context": [
                _blob("def value():\n    return 1\n", path="value.py")
            ],
        })
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "tasks": tasks,
    }


def _source_bytes(source: dict[str, Any]) -> bytes:
    return (strict_json_dumps(source) + "\n").encode()


def _canonical_digest(value: Any) -> str:
    return _digest(strict_json_dumps(value))


def _frame_manifest(source: dict[str, Any]) -> dict[str, Any]:
    tasks = sorted(
        (
            {
                "candidate_ids": sorted(
                    "sha256:" + candidate["candidate_patch_sha256"]
                    for candidate in task["candidates"]
                ),
                "task_id": task["opaque_task_id"],
            }
            for task in source["tasks"]
        ),
        key=lambda item: item["task_id"],
    )
    task_ids = [task["task_id"] for task in tasks]
    candidate_ids = sorted(
        candidate_id
        for task in tasks
        for candidate_id in task["candidate_ids"]
    )
    return {
        "candidate_count": len(candidate_ids),
        "candidate_ids_sha256": _canonical_digest(candidate_ids),
        "candidates_per_task": 3,
        "excluded_task_clusters": list(EXPECTED_EXCLUDED_TASK_CLUSTERS),
        "schema_version": FRAME_MANIFEST_SCHEMA_VERSION,
        "source_feature_freeze": dict(EXPECTED_SOURCE_FEATURE_FREEZE),
        "status": FRAME_MANIFEST_STATUS,
        "study_id": STUDY_ID,
        "task_count": len(tasks),
        "task_ids_sha256": _canonical_digest(task_ids),
        "tasks": tasks,
        "tasks_sha256": _canonical_digest(tasks),
    }


def _frame_bytes(source: dict[str, Any]) -> bytes:
    return (strict_json_dumps(_frame_manifest(source)) + "\n").encode()


def _build(
    output: pathlib.Path,
    source_bytes: bytes,
    frame_bytes: bytes,
) -> dict[str, Any]:
    return build_bundle(
        source_bytes,
        output,
        blinding_key=_BLINDING_KEY,
        frame_manifest_bytes=frame_bytes,
        expected_frame_manifest_sha256=_digest(frame_bytes),
    )


def _rewrite_canonical(path: pathlib.Path, value: Any) -> bytes:
    payload = (strict_json_dumps(value) + "\n").encode()
    path.write_bytes(payload)
    return payload


def _manifest_sha256(output: pathlib.Path) -> str:
    return _digest((output / "packet-manifest.json").read_bytes())


def _verify(
    output: pathlib.Path,
    source_bytes: bytes,
    frame_bytes: bytes,
    *,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    return verify_bundle(
        output,
        source_bytes=source_bytes,
        blinding_key=_BLINDING_KEY,
        frame_manifest_bytes=frame_bytes,
        expected_frame_manifest_sha256=_digest(frame_bytes),
        expected_manifest_sha256=(
            expected_manifest_sha256 or _manifest_sha256(output)
        ),
    )


def test_build_verify_and_exact_blinding_projection(tmp_path: pathlib.Path) -> None:
    source = _source()
    source_bytes = _source_bytes(source)
    frame_bytes = _frame_bytes(source)
    output = tmp_path / "packets"
    manifest = _build(output, source_bytes, frame_bytes)

    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["task_count"] == EXPECTED_TASK_COUNT
    assert manifest["candidate_count"] == EXPECTED_CANDIDATE_COUNT
    assert manifest["frame_manifest"]["sha256"] == _digest(frame_bytes)
    assert "source_bytes_sha256" not in manifest
    assert "source_canonical_sha256" not in manifest
    assert "source_bytes_hmac_sha256" in manifest
    assert "source_canonical_hmac_sha256" in manifest
    assert _verify(output, source_bytes, frame_bytes) == manifest
    assert manifest["blinding_boundary"].endswith(
        "named_custodian_content_attestation_still_required"
    )

    task_contexts: dict[str, set[str]] = {}
    for row in manifest["packets"]:
        task_contexts.setdefault(row["opaque_task_id"], set()).add(
            row["task_context_sha256"]
        )
        packet_text = (output / row["logical_path"]).read_text()
        packet = json.loads(packet_text)
        assert "cost" not in packet_text
        assert "model_name" not in packet_text
        assert "submission_name" not in packet_text
        assert "candidate_priority_order" not in packet_text
        assert "supports_correct" not in packet_text
        assert "supports_incorrect" not in packet_text
        assert set(packet) == {
            "candidate_patch",
            "candidate_patch_sha256",
            "evidence_events",
            "opaque_candidate_id",
            "opaque_task_id",
            "schema_version",
            "study_id",
            "task_context",
        }
        assert all(
            set(event) == {"artifacts", "event_id", "kind", "source_class"}
            for event in packet["evidence_events"]
        )
    assert all(len(digests) == 1 for digests in task_contexts.values())


def test_projection_is_deterministic_under_input_reordering(
    tmp_path: pathlib.Path,
) -> None:
    source = _source()
    reversed_source = deepcopy(source)
    reversed_source["tasks"].reverse()
    for task in reversed_source["tasks"]:
        task["candidates"].reverse()

    first = tmp_path / "first"
    second = tmp_path / "second"
    frame_bytes = _frame_bytes(source)
    first_manifest = _build(first, _source_bytes(source), frame_bytes)
    second_manifest = _build(second, _source_bytes(reversed_source), frame_bytes)

    # Raw/canonical source commitments differ because task arrays are
    # semantically ordered inputs, but packet identities and bytes are identical.
    for manifest in (first_manifest, second_manifest):
        manifest.pop("source_bytes_hmac_sha256")
        manifest.pop("source_canonical_hmac_sha256")
    assert first_manifest == second_manifest
    first_files = {
        path.relative_to(first): path.read_bytes()
        for path in first.rglob("*.json")
        if path.name != "packet-manifest.json"
    }
    second_files = {
        path.relative_to(second): path.read_bytes()
        for path in second.rglob("*.json")
        if path.name != "packet-manifest.json"
    }
    assert first_files == second_files


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda value: value["tasks"][0]["candidates"][0].__setitem__(
                "cost", {"usd": 1.0}
            ),
            "unknown=.*cost",
        ),
        (
            lambda value: value["tasks"][0].__setitem__(
                "problem_statement", "Reveal the model_name before review."
            ),
            "prohibited blinding marker",
        ),
        (
            lambda value: value["tasks"][0]["candidates"][0][
                "evidence_events"
            ][0].__setitem__("source_class", "masked_semantic"),
            "does not match",
        ),
        (
            lambda value: value["tasks"][0]["repository_context"][0].__setitem__(
                "path", "../secret"
            ),
            "confined canonical relative path",
        ),
        (
            lambda value: value["tasks"][0]["repository_context"][0].__setitem__(
                "path", "claude/output.py"
            ),
            "prohibited blinding marker",
        ),
    ],
)
def test_source_rejects_leaks_unknown_fields_and_unsafe_paths(
    mutator: Any,
    match: str,
) -> None:
    source = _source()
    frame_bytes = _frame_bytes(source)
    mutator(source)
    with pytest.raises(PacketError, match=match):
        project_source(
            source,
            blinding_key=_BLINDING_KEY,
            frame_manifest_bytes=frame_bytes,
            expected_frame_manifest_sha256=_digest(frame_bytes),
        )


def test_source_rejects_duplicate_and_nonfinite_json(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "packets"
    frame_bytes = _frame_bytes(_source())
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        build_bundle(
            b'{"schema_version":"x","schema_version":"y"}',
            output,
            blinding_key=_BLINDING_KEY,
            frame_manifest_bytes=frame_bytes,
            expected_frame_manifest_sha256=_digest(frame_bytes),
        )
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        build_bundle(
            b'{"value":NaN}',
            output,
            blinding_key=_BLINDING_KEY,
            frame_manifest_bytes=frame_bytes,
            expected_frame_manifest_sha256=_digest(frame_bytes),
        )


def test_verify_rejects_packet_tampering_even_with_rehashed_row(
    tmp_path: pathlib.Path,
) -> None:
    output = tmp_path / "packets"
    source = _source()
    source_bytes = _source_bytes(source)
    frame_bytes = _frame_bytes(source)
    manifest = _build(output, source_bytes, frame_bytes)
    frozen_manifest_sha256 = _manifest_sha256(output)
    row = manifest["packets"][0]
    packet_path = output / row["logical_path"]
    packet = json.loads(packet_path.read_text())
    packet["task_context"]["problem_statement"] = "Different task context."
    packet_payload = _rewrite_canonical(packet_path, packet)
    row["bytes"] = len(packet_payload)
    row["packet_sha256"] = _digest(packet_payload)
    context_payload = (
        strict_json_dumps(packet["task_context"]) + "\n"
    ).encode()
    row["task_context_sha256"] = _digest(context_payload)
    _rewrite_canonical(output / "packet-manifest.json", manifest)

    with pytest.raises(PacketError, match="external freeze digest"):
        _verify(
            output,
            source_bytes,
            frame_bytes,
            expected_manifest_sha256=frozen_manifest_sha256,
        )
    with pytest.raises(PacketError, match="does not regenerate"):
        _verify(output, source_bytes, frame_bytes)


def test_verify_rejects_unknown_files_and_output_reuse(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "packets"
    source = _source()
    payload = _source_bytes(source)
    frame_bytes = _frame_bytes(source)
    _build(output, payload, frame_bytes)
    (output / "unexpected.txt").write_text("drift")
    with pytest.raises(PacketError, match="bundle files differ"):
        _verify(output, payload, frame_bytes)
    with pytest.raises(PacketError, match="already exists"):
        _build(output, payload, frame_bytes)


def test_verify_rejects_unknown_empty_directories(tmp_path: pathlib.Path) -> None:
    source = _source()
    payload = _source_bytes(source)
    frame_bytes = _frame_bytes(source)
    output = tmp_path / "packets"
    _build(output, payload, frame_bytes)
    (output / "producer-claude-candidate-1").mkdir()

    with pytest.raises(PacketError, match="symlink|directories differ|blinding marker"):
        _verify(output, payload, frame_bytes)


def test_patch_rehash_attack_cannot_preserve_opaque_identity(
    tmp_path: pathlib.Path,
) -> None:
    source = _source()
    payload = _source_bytes(source)
    frame_bytes = _frame_bytes(source)
    output = tmp_path / "packets"
    manifest = _build(output, payload, frame_bytes)
    row = manifest["packets"][0]
    packet_path = output / row["logical_path"]
    packet = json.loads(packet_path.read_text())
    packet["candidate_patch"] += "# attacker rewrite\n"
    packet["candidate_patch_sha256"] = _digest(packet["candidate_patch"])
    packet_payload = _rewrite_canonical(packet_path, packet)
    row["bytes"] = len(packet_payload)
    row["packet_sha256"] = _digest(packet_payload)
    _rewrite_canonical(output / "packet-manifest.json", manifest)

    with pytest.raises(PacketError, match="does not regenerate|commitment differs"):
        _verify(output, payload, frame_bytes)


def test_source_requires_exact_frozen_scope_and_nonempty_evidence() -> None:
    full_source = _source()
    frame_bytes = _frame_bytes(full_source)
    with pytest.raises(PacketError, match="exact frozen frame"):
        project_source(
            _source(task_count=1),
            blinding_key=_BLINDING_KEY,
            frame_manifest_bytes=frame_bytes,
            expected_frame_manifest_sha256=_digest(frame_bytes),
        )

    source = deepcopy(full_source)
    source["tasks"][0]["candidates"][0]["evidence_events"] = []
    with pytest.raises(PacketError, match="must contain 1-32 evidence events"):
        project_source(
            source,
            blinding_key=_BLINDING_KEY,
            frame_manifest_bytes=frame_bytes,
            expected_frame_manifest_sha256=_digest(frame_bytes),
        )


def test_checked_in_frame_manifest_has_exact_external_identity() -> None:
    payload = _CHECKED_IN_FRAME.read_bytes()
    assert _digest(payload) == _CHECKED_IN_FRAME_SHA256
    identity = validate_frame_manifest(
        payload,
        expected_frame_manifest_sha256=_CHECKED_IN_FRAME_SHA256,
    )
    assert identity["task_count"] == EXPECTED_TASK_COUNT
    assert identity["candidate_count"] == EXPECTED_CANDIDATE_COUNT
    assert identity["excluded_task_clusters"] == list(
        EXPECTED_EXCLUDED_TASK_CLUSTERS
    )
    assert identity["source_feature_freeze"] == EXPECTED_SOURCE_FEATURE_FREEZE


def test_frame_manifest_requires_external_raw_byte_freeze() -> None:
    payload = _frame_bytes(_source())
    with pytest.raises(PacketError, match="external freeze digest"):
        validate_frame_manifest(
            payload + b" ",
            expected_frame_manifest_sha256=_digest(payload),
        )


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda frame: frame.__setitem__("schema_version", "frame-v999"),
            "schema, study, or frozen status",
        ),
        (
            lambda frame: frame.__setitem__("status", "draft"),
            "schema, study, or frozen status",
        ),
        (
            lambda frame: frame["source_feature_freeze"].__setitem__(
                "bytes", 301853
            ),
            "source-feature-freeze identity",
        ),
        (
            lambda frame: frame["excluded_task_clusters"].reverse(),
            "exclusions differ",
        ),
        (
            lambda frame: frame.__setitem__("candidate_count", 65),
            "counts differ",
        ),
    ],
)
def test_frame_manifest_semantics_reject_self_consistent_raw_rehash(
    mutator: Any,
    match: str,
) -> None:
    frame = _frame_manifest(_source())
    mutator(frame)
    payload = (strict_json_dumps(frame) + "\n").encode()
    with pytest.raises(PacketError, match=match):
        validate_frame_manifest(
            payload,
            expected_frame_manifest_sha256=_digest(payload),
        )


@pytest.mark.parametrize(
    "digest_field",
    ["task_ids_sha256", "candidate_ids_sha256", "tasks_sha256"],
)
def test_frame_manifest_recomputes_canonical_digest_summaries(
    digest_field: str,
) -> None:
    frame = _frame_manifest(_source())
    frame[digest_field] = "0" * 64
    payload = (strict_json_dumps(frame) + "\n").encode()
    with pytest.raises(PacketError, match=f"{digest_field} is not canonical"):
        validate_frame_manifest(
            payload,
            expected_frame_manifest_sha256=_digest(payload),
        )


@pytest.mark.parametrize("mutation", ["task", "candidate"])
def test_source_must_match_frame_per_task_patch_sets(mutation: str) -> None:
    source = _source()
    frame_bytes = _frame_bytes(source)
    if mutation == "task":
        source["tasks"][0]["opaque_task_id"] = "opaque-task-replacement"
    else:
        first = source["tasks"][0]["candidates"]
        second = source["tasks"][1]["candidates"]
        first[0], second[0] = second[0], first[0]
    with pytest.raises(PacketError, match="per-task candidate patch SHA-256 sets"):
        project_source(
            source,
            blinding_key=_BLINDING_KEY,
            frame_manifest_bytes=frame_bytes,
            expected_frame_manifest_sha256=_digest(frame_bytes),
        )


def test_packet_manifest_frame_identity_cannot_be_rehashed(
    tmp_path: pathlib.Path,
) -> None:
    source = _source()
    source_bytes = _source_bytes(source)
    frame_bytes = _frame_bytes(source)
    output = tmp_path / "packets"
    manifest = _build(output, source_bytes, frame_bytes)
    manifest["frame_manifest"]["sha256"] = "0" * 64
    rewritten = _rewrite_canonical(output / "packet-manifest.json", manifest)
    with pytest.raises(PacketError, match="does not regenerate"):
        _verify(
            output,
            source_bytes,
            frame_bytes,
            expected_manifest_sha256=_digest(rewritten),
        )


def test_cli_build_and_verify_require_and_report_frame_identity(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source()
    source_path = tmp_path / "source.json"
    frame_path = tmp_path / "frame.json"
    key_path = tmp_path / "blinding.key"
    output = tmp_path / "packets"
    source_path.write_bytes(_source_bytes(source))
    frame_bytes = _frame_bytes(source)
    frame_path.write_bytes(frame_bytes)
    key_path.write_bytes(_BLINDING_KEY)
    frame_sha256 = _digest(frame_bytes)

    assert main([
        "build",
        str(source_path),
        str(output),
        "--blinding-key-file",
        str(key_path),
        "--frame-manifest",
        str(frame_path),
        "--expected-frame-manifest-sha256",
        frame_sha256,
    ]) == 0
    build_result = json.loads(capsys.readouterr().out)
    assert build_result["frame_manifest_sha256"] == frame_sha256
    assert build_result["verified"] is False

    assert main([
        "verify",
        str(output),
        "--source",
        str(source_path),
        "--blinding-key-file",
        str(key_path),
        "--frame-manifest",
        str(frame_path),
        "--expected-frame-manifest-sha256",
        frame_sha256,
        "--expected-manifest-sha256",
        build_result["manifest_sha256"],
    ]) == 0
    verify_result = json.loads(capsys.readouterr().out)
    assert verify_result["frame_manifest_sha256"] == frame_sha256
    assert verify_result["verified"] is True
