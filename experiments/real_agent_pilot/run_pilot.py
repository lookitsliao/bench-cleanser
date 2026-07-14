#!/usr/bin/env python3
"""Reproduce a source-locked convenience pilot over real SWE-agent patches."""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_loads,
)
from bench_cleanser.verification.manifest import build_candidate_manifest
from bench_cleanser.verification.models import LifecycleStage

PILOT_SCHEMA_VERSION = "0.1.0"
PILOT_REPORT_SCHEMA_VERSION = "0.1.0"
_ARTIFACT_NAMES = ("patch.diff", "report.json", "trajectory.json")
_INSTANCE_RE = re.compile(r"[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[0-9]+")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_ALLOWED_HOSTS = {"swe-bench-submissions.s3.amazonaws.com"}


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _array(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return value


def _string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a trimmed non-empty string")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} cannot contain control characters")
    return value


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    field_name: str,
) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ValueError(f"{field_name} has unknown fields: {unknown}")
    if missing:
        raise ValueError(f"{field_name} is missing fields: {missing}")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_cohort(path: pathlib.Path) -> dict[str, Any]:
    try:
        decoded = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"could not load strict cohort JSON: {exc}") from exc
    cohort = _object(decoded, "cohort")
    _exact_fields(
        cohort,
        {"schema_version", "study_id", "source", "candidates"},
        "cohort",
    )
    if cohort["schema_version"] != PILOT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported cohort schema {cohort['schema_version']!r}; "
            f"expected {PILOT_SCHEMA_VERSION!r}"
        )
    _string(cohort["study_id"], "cohort.study_id")
    source = _object(cohort["source"], "cohort.source")
    _exact_fields(
        source,
        {
            "repository",
            "revision",
            "submission_id",
            "submission_checked",
            "submission_metadata_url",
            "selection",
        },
        "cohort.source",
    )
    for key, value in source.items():
        if key == "submission_checked":
            continue
        _string(value, f"cohort.source.{key}")
    _boolean(source["submission_checked"], "cohort.source.submission_checked")
    if not _COMMIT_RE.fullmatch(source["revision"]):
        raise ValueError("cohort.source.revision must be a full lowercase Git hash")

    candidates = _array(cohort["candidates"], "cohort.candidates")
    if not candidates:
        raise ValueError("cohort.candidates cannot be empty")
    seen: set[str] = set()
    for index, raw_candidate in enumerate(candidates):
        field = f"cohort.candidates[{index}]"
        candidate = _object(raw_candidate, field)
        _exact_fields(
            candidate,
            {
                "instance_id",
                "repository",
                "base_commit",
                "official_resolved",
                "artifacts",
            },
            field,
        )
        instance_id = _string(candidate["instance_id"], f"{field}.instance_id")
        if not _INSTANCE_RE.fullmatch(instance_id):
            raise ValueError(f"{field}.instance_id is not a confined identifier")
        if instance_id in seen:
            raise ValueError(f"duplicate cohort instance_id {instance_id!r}")
        seen.add(instance_id)
        _string(candidate["repository"], f"{field}.repository")
        commit = _string(candidate["base_commit"], f"{field}.base_commit")
        if not _COMMIT_RE.fullmatch(commit):
            raise ValueError(f"{field}.base_commit must be a full lowercase Git hash")
        _boolean(candidate["official_resolved"], f"{field}.official_resolved")
        artifacts = _object(candidate["artifacts"], f"{field}.artifacts")
        _exact_fields(artifacts, set(_ARTIFACT_NAMES), f"{field}.artifacts")
        for name in _ARTIFACT_NAMES:
            artifact = _object(artifacts[name], f"{field}.artifacts[{name!r}]")
            _exact_fields(
                artifact,
                {"url", "sha256", "bytes"},
                f"{field}.artifacts[{name!r}]",
            )
            url = _string(artifact["url"], f"{field}.artifacts[{name!r}].url")
            parsed = urllib.parse.urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname not in _ALLOWED_HOSTS
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"{field}.artifacts[{name!r}].url is not allowlisted")
            digest = _string(
                artifact["sha256"],
                f"{field}.artifacts[{name!r}].sha256",
            )
            if not _SHA256_RE.fullmatch(digest):
                raise ValueError(
                    f"{field}.artifacts[{name!r}].sha256 must be lowercase SHA-256"
                )
            _integer(artifact["bytes"], f"{field}.artifacts[{name!r}].bytes")
    return cohort


def _artifact_path(root: pathlib.Path, instance_id: str, name: str) -> pathlib.Path:
    return root / instance_id / name


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


def _fetch_artifact(url: str, *, expected_bytes: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "bench-cleanser-real-agent-pilot/0.1"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in _ALLOWED_HOSTS:
            raise ValueError("artifact download redirected outside the allowlist")
        payload = response.read(expected_bytes + 1)
    if not isinstance(payload, bytes):
        raise TypeError("artifact response must be bytes")
    if len(payload) != expected_bytes:
        raise ValueError(
            f"artifact byte length mismatch: expected {expected_bytes}, got {len(payload)}"
        )
    return payload


def acquire_artifacts(
    cohort: Mapping[str, Any],
    artifact_root: pathlib.Path,
    *,
    fetch_missing: bool,
) -> None:
    artifact_root.mkdir(parents=True, exist_ok=True)
    for candidate in cohort["candidates"]:
        instance_id = candidate["instance_id"]
        for name in _ARTIFACT_NAMES:
            identity = candidate["artifacts"][name]
            path = _artifact_path(artifact_root, instance_id, name)
            if not path.exists():
                if not fetch_missing:
                    raise FileNotFoundError(
                        f"missing {path}; rerun with --fetch to acquire public artifacts"
                    )
                payload = _fetch_artifact(
                    identity["url"],
                    expected_bytes=identity["bytes"],
                )
                if _sha256_bytes(payload) != identity["sha256"]:
                    raise ValueError(f"downloaded {instance_id}/{name} has wrong SHA-256")
                _atomic_write_bytes(path, payload)
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"artifact must be a regular non-symlink file: {path}")
            payload = path.read_bytes()
            if len(payload) != identity["bytes"]:
                raise ValueError(f"artifact size mismatch for {instance_id}/{name}")
            if _sha256_bytes(payload) != identity["sha256"]:
                raise ValueError(f"artifact SHA-256 mismatch for {instance_id}/{name}")


def _test_counts(report: Mapping[str, Any], instance_id: str) -> dict[str, int]:
    tests = _object(report.get("tests_status"), f"report[{instance_id}].tests_status")
    result: dict[str, int] = {}
    for group in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        group_data = _object(tests.get(group), f"report[{instance_id}].{group}")
        success = _array(group_data.get("success"), f"report[{instance_id}].{group}.success")
        failure = _array(group_data.get("failure"), f"report[{instance_id}].{group}.failure")
        if any(not isinstance(item, str) for item in (*success, *failure)):
            raise ValueError(f"report[{instance_id}].{group} names must be strings")
        result[f"{group.lower()}_success"] = len(success)
        result[f"{group.lower()}_failure"] = len(failure)
    return result


def _trajectory_claim(trajectory: Any, instance_id: str) -> dict[str, Any]:
    events = _array(trajectory, f"trajectory[{instance_id}]")
    finishes = [event for event in events if isinstance(event, dict) and event.get("action") == "finish"]
    if len(finishes) != 1:
        raise ValueError(
            f"trajectory[{instance_id}] must contain exactly one finish action"
        )
    args = _object(finishes[0].get("args"), f"trajectory[{instance_id}].finish.args")
    final_thought = args.get("final_thought")
    if not isinstance(final_thought, str):
        raise ValueError(f"trajectory[{instance_id}] final_thought must be text")
    task_completed = args.get("task_completed")
    completed_claim = task_completed is True or (
        isinstance(task_completed, str) and task_completed.casefold() == "true"
    )
    successful_language = bool(
        re.search(r"\b(successfully|success|resolved|fixed)\b", final_thought, re.I)
    )
    return {
        "finish_count": 1,
        "task_completed_claim": completed_claim,
        "success_language_claim": successful_language,
        "optimistic_accept": completed_claim and successful_language,
        "final_thought_sha256": hashlib.sha256(
            final_thought.encode("utf-8")
        ).hexdigest(),
    }


def analyze_cohort(
    cohort_path: pathlib.Path,
    artifact_root: pathlib.Path,
    *,
    fetch_missing: bool = False,
) -> dict[str, Any]:
    cohort = _load_cohort(cohort_path)
    acquire_artifacts(cohort, artifact_root, fetch_missing=fetch_missing)
    candidates: list[dict[str, Any]] = []
    for candidate in cohort["candidates"]:
        instance_id = candidate["instance_id"]
        patch_bytes = _artifact_path(artifact_root, instance_id, "patch.diff").read_bytes()
        report_bytes = _artifact_path(artifact_root, instance_id, "report.json").read_bytes()
        trajectory_bytes = _artifact_path(
            artifact_root,
            instance_id,
            "trajectory.json",
        ).read_bytes()
        try:
            patch = patch_bytes.decode("utf-8")
            report_payload = strict_json_loads(report_bytes.decode("utf-8"))
            trajectory = strict_json_loads(trajectory_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"invalid UTF-8/strict JSON for {instance_id}: {exc}") from exc

        report_root = _object(report_payload, f"report[{instance_id}]")
        if set(report_root) != {instance_id}:
            raise ValueError(f"official report must contain only {instance_id!r}")
        report = _object(report_root[instance_id], f"report[{instance_id}]")
        resolved = _boolean(report.get("resolved"), f"report[{instance_id}].resolved")
        patch_applied = _boolean(
            report.get("patch_successfully_applied"),
            f"report[{instance_id}].patch_successfully_applied",
        )
        if resolved != candidate["official_resolved"]:
            raise ValueError(f"official result drift for {instance_id}")
        manifest = build_candidate_manifest(
            instance_id=instance_id,
            candidate_patch=patch,
            lifecycle_stage=LifecycleStage.ROLLOUT,
            provenance={
                "repository": candidate["repository"],
                "base_commit": candidate["base_commit"],
                "dataset_revision": (
                    f"{cohort['source']['repository']}@{cohort['source']['revision']}"
                ),
                "candidate_generator": cohort["source"]["submission_id"],
            },
        )
        claim = _trajectory_claim(trajectory, instance_id)
        candidates.append({
            "instance_id": instance_id,
            "candidate_id": manifest.candidate_id,
            "manifest_sha256": manifest.canonical_digest(),
            "base_commit": candidate["base_commit"],
            "official": {
                "resolved": resolved,
                "patch_successfully_applied": patch_applied,
                **_test_counts(report, instance_id),
            },
            "trajectory_claim": claim,
            "optimistic_claim_false_accept": (
                claim["optimistic_accept"] and not resolved
            ),
            "risk_profile": manifest.to_dict()["risk_profile"],
            "artifact_sha256": {
                name: candidate["artifacts"][name]["sha256"]
                for name in _ARTIFACT_NAMES
            },
        })

    optimistic = [item for item in candidates if item["trajectory_claim"]["optimistic_accept"]]
    false_accepts = [item for item in optimistic if not item["official"]["resolved"]]
    resolved_count = sum(item["official"]["resolved"] for item in candidates)
    return {
        "schema_version": PILOT_REPORT_SCHEMA_VERSION,
        "study_id": cohort["study_id"],
        "source": cohort["source"],
        "cohort_sha256": _sha256_bytes(cohort_path.read_bytes()),
        "candidates": candidates,
        "metrics": {
            "candidate_count": len(candidates),
            "official_resolved_count": resolved_count,
            "official_unresolved_count": len(candidates) - resolved_count,
            "optimistic_claim_accept_count": len(optimistic),
            "optimistic_claim_false_accept_count": len(false_accepts),
            "optimistic_claim_false_accept_rate": (
                len(false_accepts) / len(optimistic) if optimistic else None
            ),
        },
        "scientific_status": {
            "representative": False,
            "randomized": False,
            "blinded": False,
            "independent_reexecution": False,
            "supports_hypotheses_h1_to_h6": False,
            "purpose": (
                "source-locked real-agent integration pilot and optimistic-"
                "self-report counterexample"
            ),
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a source-locked real SWE-agent convenience pilot"
    )
    parser.add_argument(
        "--cohort",
        type=pathlib.Path,
        default=pathlib.Path(__file__).with_name("cohort.json"),
    )
    parser.add_argument("--artifact-dir", type=pathlib.Path, required=True)
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download missing public artifacts from the allowlisted S3 host",
    )
    parser.add_argument("--output", type=pathlib.Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        report = analyze_cohort(
            args.cohort,
            args.artifact_dir,
            fetch_missing=args.fetch,
        )
        rendered = strict_json_dumps(report, indent=2) + "\n"
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            atomic_write(args.output, rendered)
    except (OSError, TypeError, ValueError) as exc:
        raise SystemExit(f"real-agent pilot failed: {exc}") from exc


if __name__ == "__main__":
    main()
