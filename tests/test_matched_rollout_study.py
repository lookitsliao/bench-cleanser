"""Offline contract tests for the matched three-rollout development study."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import threading
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from bench_cleanser.verification._io import strict_json_dumps

SCRIPT = (
    pathlib.Path(__file__).parents[1] / "experiments" / "matched_rollout_study" / "run_study.py"
)
SPEC = importlib.util.spec_from_file_location("matched_rollout_study", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
study = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = study
SPEC.loader.exec_module(study)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _metadata(submission_id: str) -> bytes:
    return (
        "assets:\n"
        f"  logs: s3://{study.BUCKET_NAME}/verified/{submission_id}/logs\n"
        f"  trajs: s3://{study.BUCKET_NAME}/verified/{submission_id}/trajs\n"
        "tags:\n"
        "  checked: true\n"
        "  os_system: true\n"
        "  system:\n"
        "    attempts: 1\n"
    ).encode()


def _results(
    resolved: Sequence[str],
    *,
    no_generation: Sequence[str] = (),
    no_logs: Sequence[str] = (),
) -> bytes:
    return (
        strict_json_dumps(
            {
                "no_generation": sorted(no_generation),
                "no_logs": sorted(no_logs),
                "resolved": sorted(resolved),
            },
            indent=2,
        )
        + "\n"
    ).encode()


def _spec(
    key: str,
    model_label: str,
    submission_id: str,
    *,
    count: int,
    resolved: Sequence[str],
    no_generation: Sequence[str] = (),
    no_logs: Sequence[str] = (),
) -> tuple[Any, bytes, bytes]:
    metadata = _metadata(submission_id)
    results = _results(
        resolved,
        no_generation=no_generation,
        no_logs=no_logs,
    )
    spec = study.SubmissionSpec(
        key=key,
        model_label=model_label,
        submission_id=submission_id,
        expected_instance_count=count,
        metadata_bytes=len(metadata),
        metadata_sha256=_sha256(metadata),
        results_bytes=len(results),
        results_sha256=_sha256(results),
    )
    return spec, metadata, results


def _listing(spec: Any, instance_ids: Sequence[str], *, truncated: bool = False) -> bytes:
    namespace = "http://s3.amazonaws.com/doc/2006-03-01/"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}ListBucketResult")
    for name, value in (
        ("Name", study.BUCKET_NAME),
        ("Prefix", spec.root_prefix),
        ("KeyCount", str(len(instance_ids))),
        ("MaxKeys", "1000"),
        ("Delimiter", "/"),
        ("IsTruncated", str(truncated).lower()),
    ):
        ET.SubElement(root, f"{{{namespace}}}{name}").text = value
    for instance_id in instance_ids:
        common = ET.SubElement(root, f"{{{namespace}}}CommonPrefixes")
        ET.SubElement(common, f"{{{namespace}}}Prefix").text = f"{spec.root_prefix}{instance_id}/"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _patch(instance_id: str, submission_key: str) -> bytes:
    number = int(instance_id.rsplit("-", 1)[1])
    path = f"src/{submission_key}_{number}.py"
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        "-old_value = 0\n"
        f"+new_value = {number}\n"
    ).encode()


def _trajectory(instance_id: str, submission_key: str) -> bytes:
    return (
        strict_json_dumps(
            [
                {"kind": "message", "payload": {"length": len(instance_id)}},
                {"kind": "action", "payload": [submission_key, 1, True]},
            ]
        )
        + "\n"
    ).encode()


def _report(instance_id: str, *, resolved: bool) -> bytes:
    report = {
        instance_id: {
            "patch_exists": True,
            "patch_is_None": False,
            "patch_successfully_applied": True,
            "resolved": resolved,
            "tests_status": {
                "FAIL_TO_PASS": {
                    "success": ["target"] if resolved else [],
                    "failure": [] if resolved else ["target"],
                },
                "PASS_TO_PASS": {"success": ["regression"], "failure": []},
                "FAIL_TO_FAIL": {"success": ["known_failure"], "failure": []},
                "PASS_TO_FAIL": {"success": ["new_failure_guard"], "failure": []},
            },
        }
    }
    return (strict_json_dumps(report, indent=2) + "\n").encode()


def _dataset_row(
    instance_id: str,
    *,
    base_commit: str,
    environment_setup_commit: str,
) -> dict[str, str]:
    row = {field: "" for field in study.CANONICAL_DATASET_SCHEMA_FIELDS}
    row.update(
        {
            "repo": study.infer_repository(instance_id),
            "instance_id": instance_id,
            "base_commit": base_commit,
            "environment_setup_commit": environment_setup_commit,
        }
    )
    return row


def _canonical_parquet(rows: Sequence[Mapping[str, str]]) -> bytes:
    table = study.pa.table(
        {field: [row[field] for row in rows] for field in study.CANONICAL_DATASET_SCHEMA_FIELDS}
    )
    sink = study.pa.BufferOutputStream()
    study.pq.write_table(table, sink)
    return sink.getvalue().to_pybytes()


def _fixture(
    *,
    labels: Mapping[str, frozenset[str]] | None = None,
    no_generation: Mapping[str, frozenset[str]] | None = None,
    no_logs: Mapping[str, frozenset[str]] | None = None,
    missing: frozenset[tuple[str, str, str]] = frozenset(),
) -> tuple[tuple[Any, ...], dict[str, bytes], list[str]]:
    instance_ids = [
        "alpha__repo-1",
        "alpha__repo-2",
        "beta__repo-3",
        "beta__repo-4",
    ]
    labels = labels or {
        "gpt5": frozenset({instance_ids[0], instance_ids[2]}),
        "kimi_k2": frozenset({instance_ids[1], instance_ids[2]}),
        "claude_4_sonnet": frozenset({instance_ids[3]}),
    }
    no_generation = no_generation or {key: frozenset() for key in labels}
    no_logs = no_logs or {key: frozenset() for key in labels}
    identities = (
        ("gpt5", "GPT-5", "fixture_openhands_gpt5"),
        ("kimi_k2", "Kimi K2", "fixture_openhands_kimi_k2"),
        ("claude_4_sonnet", "Claude 4 Sonnet", "fixture_openhands_claude"),
    )
    specs: list[Any] = []
    payloads: dict[str, bytes] = {}
    for key, model_label, submission_id in identities:
        spec, metadata, results = _spec(
            key,
            model_label,
            submission_id,
            count=len(instance_ids),
            resolved=sorted(labels[key]),
            no_generation=sorted(no_generation[key]),
            no_logs=sorted(no_logs[key]),
        )
        specs.append(spec)
        payloads[spec.metadata_url] = metadata
        payloads[spec.results_url] = results
        payloads[study._frame_listing_url(spec)] = _listing(spec, instance_ids)
        for instance_id in instance_ids:
            artifacts = {
                "patch.diff": _patch(instance_id, key),
                "trajectory.json": _trajectory(instance_id, key),
            }
            if instance_id not in no_generation[key] and instance_id not in no_logs[key]:
                artifacts["report.json"] = _report(
                    instance_id,
                    resolved=instance_id in labels[key],
                )
            for name, payload in artifacts.items():
                if (instance_id, key, name) not in missing:
                    payloads[study._artifact_url(spec, instance_id, name)] = payload
    return tuple(specs), payloads, instance_ids


def _fake_fetcher(payloads: Mapping[str, bytes]) -> tuple[Any, dict[str, int]]:
    calls: dict[str, int] = {}
    lock = threading.Lock()

    def fetch(
        url: str,
        *,
        maximum_bytes: int,
        timeout_seconds: float,
        budget: Any,
        specs: Sequence[Any],
    ) -> Any:
        assert specs
        assert 0 < timeout_seconds <= 120
        with lock:
            calls[url] = calls.get(url, 0) + 1
        if url not in payloads:
            raise study.UnavailableFetchError("fixture object absent")
        payload = payloads[url]
        assert len(payload) <= maximum_bytes
        budget.consume(len(payload))
        return study.DownloadedObject(payload=payload, final_url=url)

    return fetch, calls


def _acquire(
    tmp_path: pathlib.Path,
    *,
    labels: Mapping[str, frozenset[str]] | None = None,
    no_generation: Mapping[str, frozenset[str]] | None = None,
    no_logs: Mapping[str, frozenset[str]] | None = None,
    missing: frozenset[tuple[str, str, str]] = frozenset(),
    name: str = "acquisition",
) -> tuple[pathlib.Path, tuple[Any, ...], dict[str, bytes]]:
    specs, payloads, _ = _fixture(
        labels=labels,
        no_generation=no_generation,
        no_logs=no_logs,
        missing=missing,
    )
    fetch, _ = _fake_fetcher(payloads)
    root = tmp_path / name
    study.acquire_corpus(
        root,
        specs=specs,
        repository_count=2,
        tasks_per_repository=2,
        workers=4,
        retries=1,
        fetch_once=fetch,
        sleep=lambda _: None,
    )
    return root, specs, payloads


def test_listing_validation_is_complete_confined_and_non_truncated() -> None:
    specs, _, instance_ids = _fixture()
    assert study.enumerate_instance_ids(
        _listing(specs[0], instance_ids),
        spec=specs[0],
    ) == tuple(instance_ids)
    with pytest.raises(ValueError, match="truncated"):
        study.enumerate_instance_ids(
            _listing(specs[0], instance_ids, truncated=True),
            spec=specs[0],
        )
    with pytest.raises(ValueError, match="duplicate|canonical"):
        study.enumerate_instance_ids(
            _listing(specs[0], [*instance_ids[:-1], instance_ids[0]]),
            spec=specs[0],
        )
    with pytest.raises(ValueError, match="DTD/entity"):
        study.enumerate_instance_ids(
            b'<!DOCTYPE x [<!ENTITY e "x">]><x>&e;</x>',
            spec=specs[0],
        )


def test_cohort_freeze_uses_only_common_ids_and_repository_strata() -> None:
    frames = {
        "a": ["alpha__repo-1", "alpha__repo-2", "beta__repo-3", "beta__repo-4"],
        "b": [
            "alpha__repo-1",
            "alpha__repo-2",
            "beta__repo-3",
            "beta__repo-4",
            "gamma__repo-5",
        ],
    }
    first = study.freeze_common_cohort(
        frames,
        repository_count=2,
        tasks_per_repository=2,
        seed=17,
    )
    second = study.freeze_common_cohort(
        dict(reversed(list(frames.items()))),
        repository_count=2,
        tasks_per_repository=2,
        seed=17,
    )
    assert first == second
    assert first["common_instance_count"] == 4
    assert first["selected_instance_ids"] == sorted(frames["a"])
    assert "hosted resolved labels" in first["excluded_selection_inputs"]


def test_live_frame_contract_is_exact_subset_with_one_known_missing_task() -> None:
    gpt = [f"django__django-{number}" for number in range(1, 500)]
    full = sorted([*gpt, "django__django-13513"])
    frames = {
        "gpt5": gpt,
        "kimi_k2": full,
        "claude_4_sonnet": full,
    }
    study._validate_pinned_frame_relationship(frames)

    drifted = {**frames, "claude_4_sonnet": full[:-1]}
    with pytest.raises(ValueError, match="relationship drifted"):
        study._validate_pinned_frame_relationship(drifted)


def test_acquisition_pins_sources_artifacts_and_flat_trajectories(
    tmp_path: pathlib.Path,
) -> None:
    specs, payloads, instance_ids = _fixture()
    fetch, calls = _fake_fetcher(payloads)
    root = tmp_path / "corpus"
    manifest = study.acquire_corpus(
        root,
        specs=specs,
        repository_count=2,
        tasks_per_repository=2,
        workers=4,
        retries=1,
        fetch_once=fetch,
        sleep=lambda _: None,
    )

    assert manifest["totals"]["task_count"] == 4
    assert manifest["totals"]["candidate_count"] == 12
    assert manifest["totals"]["artifact_record_count"] == 36
    assert manifest["totals"]["unavailable_artifact_count"] == 0
    assert not (tmp_path / ".corpus.lock").exists()
    assert not list(tmp_path.glob(".corpus.staging.*"))
    for spec in specs:
        for instance_id in instance_ids:
            trajectory_url = study._artifact_url(spec, instance_id, "trajectory.json")
            assert "/trajs/" in trajectory_url
            assert trajectory_url.endswith(f"/{instance_id}.json")
            assert calls[trajectory_url] == 1
    validated, _ = study.validate_acquisition(root, specs=specs)
    assert validated == manifest


def test_feature_freeze_is_written_before_any_outcome_decode(
    tmp_path: pathlib.Path,
) -> None:
    root, specs, _ = _acquire(tmp_path)
    freeze_path = tmp_path / "feature-freeze.json"
    report_path = tmp_path / "report.json"
    observed: dict[str, bool] = {}

    def decoder(
        artifact_root: pathlib.Path,
        manifest: Mapping[str, Any],
        decoder_specs: Sequence[Any],
    ) -> tuple[Any, ...]:
        observed["freeze_exists"] = freeze_path.is_file()
        freeze = study.strict_json_loads(freeze_path.read_text(encoding="utf-8"))
        observed["phase_assertion"] = (
            freeze["phase_assertion"] == "serialized_before_any_hosted_outcome_decode"
        )
        return study.decode_hosted_outcomes(artifact_root, manifest, decoder_specs)

    report = study.analyze_study(
        root,
        freeze_output=freeze_path,
        report_output=report_path,
        specs=specs,
        outcome_decoder=decoder,
    )

    assert observed == {"freeze_exists": True, "phase_assertion": True}
    assert report["feature_freeze"]["completed_before_outcome_decode"] is True
    assert (
        report["feature_freeze"]["durable_reload_and_rederivation_validated_before_outcome_decode"]
        is True
    )
    assert "path" not in report["feature_freeze"]
    assert report["candidate_count_per_task"] == 3
    assert len(report["equal_maximum_reveal_budget_results"]) == (4 * len(study.POLICY_NAMES))
    assert (
        report["candidate_patch_diversity"]["all_candidate_patches_byte_distinct_task_count"] == 4
    )
    assert (
        report["report_test_signature_comparability"]["exact_test_signature_match_task_count"] == 4
    )
    assert report["outcome_quarantine"]["quarantined_task_count"] == 0
    assert report_path.is_file()


def test_outcome_flip_cannot_change_features_or_candidate_orders(
    tmp_path: pathlib.Path,
) -> None:
    first_labels = {
        "gpt5": frozenset({"alpha__repo-1"}),
        "kimi_k2": frozenset({"beta__repo-3"}),
        "claude_4_sonnet": frozenset({"beta__repo-4"}),
    }
    second_labels = {
        "gpt5": frozenset({"beta__repo-4"}),
        "kimi_k2": frozenset({"alpha__repo-2"}),
        "claude_4_sonnet": frozenset({"alpha__repo-1", "beta__repo-3"}),
    }
    first_root, first_specs, _ = _acquire(
        tmp_path,
        labels=first_labels,
        name="first",
    )
    second_root, second_specs, _ = _acquire(
        tmp_path,
        labels=second_labels,
        name="second",
    )
    first_manifest, _ = study.validate_acquisition(first_root, specs=first_specs)
    second_manifest, _ = study.validate_acquisition(second_root, specs=second_specs)
    first_input = study.sanitize_feature_inputs(first_manifest, specs=first_specs)
    second_input = study.sanitize_feature_inputs(second_manifest, specs=second_specs)
    first_freeze, _ = study.build_feature_freeze(
        first_root,
        first_input,
        specs=first_specs,
        policy_seed=11,
    )
    second_freeze, _ = study.build_feature_freeze(
        second_root,
        second_input,
        specs=second_specs,
        policy_seed=11,
    )

    assert first_freeze == second_freeze
    assert any(value.startswith("report.json bytes") for value in first_freeze["excluded_inputs"])
    first_outcomes = study.decode_hosted_outcomes(first_root, first_manifest, first_specs)
    second_outcomes = study.decode_hosted_outcomes(second_root, second_manifest, second_specs)
    assert [row.hosted_resolved for row in first_outcomes] != [
        row.hosted_resolved for row in second_outcomes
    ]


def test_feature_builder_requires_sanitized_patch_and_history_projection(
    tmp_path: pathlib.Path,
) -> None:
    root, specs, _ = _acquire(tmp_path)
    manifest, _ = study.validate_acquisition(root, specs=specs)
    feature_input = study.sanitize_feature_inputs(manifest, specs=specs)

    assert {artifact.name for artifact in feature_input.artifacts} == {
        "patch.diff",
        "trajectory.json",
    }
    assert all(not hasattr(artifact, "source_url") for artifact in feature_input.artifacts)
    assert all(not hasattr(artifact, "response_url") for artifact in feature_input.artifacts)
    with pytest.raises(TypeError, match="sanitized FeatureBuildInput"):
        study.build_feature_freeze(root, manifest, specs=specs)


def test_unknown_outcomes_are_typed_and_quarantine_the_matched_task(
    tmp_path: pathlib.Path,
) -> None:
    empty: frozenset[str] = frozenset()
    root, specs, _ = _acquire(
        tmp_path,
        no_generation={
            "gpt5": frozenset({"alpha__repo-2"}),
            "kimi_k2": empty,
            "claude_4_sonnet": empty,
        },
        no_logs={
            "gpt5": empty,
            "kimi_k2": frozenset({"beta__repo-4"}),
            "claude_4_sonnet": empty,
        },
    )
    manifest, _ = study.validate_acquisition(root, specs=specs)
    outcomes = study.decode_hosted_outcomes(root, manifest, specs)
    by_pair = {(row.instance_id, row.submission_key): row for row in outcomes}
    assert by_pair[("alpha__repo-2", "gpt5")].disposition == "no_generation"
    assert by_pair[("alpha__repo-2", "gpt5")].hosted_resolved is None
    assert by_pair[("beta__repo-4", "kimi_k2")].disposition == "no_logs"
    assert by_pair[("beta__repo-4", "kimi_k2")].hosted_resolved is None

    report = study.analyze_study(
        root,
        freeze_output=tmp_path / "unknown-freeze.json",
        report_output=tmp_path / "unknown-report.json",
        specs=specs,
    )
    assert report["hosted_outcome_disposition_counts"] == {
        "failed": 5,
        "no_generation": 1,
        "no_logs": 1,
        "resolved": 5,
    }
    assert report["outcome_quarantine"]["matched_known_task_count"] == 2
    assert report["outcome_quarantine"]["quarantined_task_count"] == 2
    assert all(row["task_count"] == 2 for row in report["equal_maximum_reveal_budget_results"])

    labels = {"a": None, "b": True, "c": False}
    assert study._select_with_budget(("a", "b", "c"), labels, maximum_reveals=1) == (
        "b",
        1,
        ("a",),
        "highest_ranked_unrevealed_after_unknown_or_failed_outcomes",
    )
    assert study._select_with_budget(("a", "b", "c"), labels, maximum_reveals=2) == (
        "b",
        2,
        ("a", "b"),
        "first_revealed_success",
    )


def test_official_unknown_may_be_canonical_without_an_artifact_frame(
    tmp_path: pathlib.Path,
) -> None:
    root, specs, _ = _acquire(tmp_path, name="canonical-unknown")
    manifest, _ = study.validate_acquisition(root, specs=specs)
    instance_ids = [
        "alpha__repo-1",
        "alpha__repo-2",
        "beta__repo-3",
        "beta__repo-4",
        "gamma__repo-5",
    ]
    manifest["canonical_dataset"] = {
        "dataset_id": study.CANONICAL_DATASET_ID,
        "revision": study.CANONICAL_DATASET_REVISION,
        "task_identities": [
            {
                "instance_id": instance_id,
                "repo": study.infer_repository(instance_id),
                "base_commit": f"{index:x}" * 40,
                "environment_setup_commit": f"{index + 5:x}" * 40,
            }
            for index, instance_id in enumerate(instance_ids, 1)
        ],
    }
    gpt_results = root / study._source_file_path(
        manifest,
        submission_key="gpt5",
        name="results.json",
    )
    decoded = study.strict_json_loads(gpt_results.read_text(encoding="utf-8"))
    decoded["no_generation"] = ["gamma__repo-5"]
    gpt_results.write_text(strict_json_dumps(decoded) + "\n", encoding="utf-8")

    outcomes = study.decode_hosted_outcomes(root, manifest, specs)
    assert len(outcomes) == 12

    decoded["no_generation"] = []
    decoded["resolved"].append("gamma__repo-5")
    decoded["resolved"].sort()
    gpt_results.write_text(strict_json_dumps(decoded) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="resolved categories escape.*artifact frame"):
        study.decode_hosted_outcomes(root, manifest, specs)

    decoded["resolved"].remove("gamma__repo-5")
    decoded["no_generation"] = ["outside__repo-6"]
    gpt_results.write_text(strict_json_dumps(decoded) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="canonical task universe"):
        study.decode_hosted_outcomes(root, manifest, specs)


def test_report_content_is_independent_of_output_paths(tmp_path: pathlib.Path) -> None:
    root, specs, _ = _acquire(tmp_path)
    first = study.analyze_study(
        root,
        freeze_output=tmp_path / "one" / "freeze.json",
        report_output=tmp_path / "one" / "report.json",
        specs=specs,
    )
    second = study.analyze_study(
        root,
        freeze_output=tmp_path / "different" / "freeze.json",
        report_output=tmp_path / "different" / "report.json",
        specs=specs,
    )
    assert first == second
    assert (tmp_path / "one" / "report.json").read_bytes() == (
        tmp_path / "different" / "report.json"
    ).read_bytes()
    assert first["study_code_identity"]["logical_path"] == study.STUDY_CODE_LOGICAL_PATH
    assert not first["study_code_identity"]["logical_path"].startswith("/")
    assert first["study_code_identity_matches_acquisition"] is True


def test_patch_diversity_and_test_signature_metrics_detect_collisions(
    tmp_path: pathlib.Path,
) -> None:
    specs, payloads, _ = _fixture()
    by_key = {spec.key: spec for spec in specs}
    instance_id = "alpha__repo-1"
    gpt_patch_url = study._artifact_url(by_key["gpt5"], instance_id, "patch.diff")
    kimi_patch_url = study._artifact_url(by_key["kimi_k2"], instance_id, "patch.diff")
    payloads[kimi_patch_url] = payloads[gpt_patch_url]
    claude_report_url = study._artifact_url(
        by_key["claude_4_sonnet"],
        instance_id,
        "report.json",
    )
    payloads[claude_report_url] = payloads[claude_report_url].replace(
        b'"regression"',
        b'"different_regression"',
    )
    fetch, _ = _fake_fetcher(payloads)
    root = tmp_path / "metric-corpus"
    study.acquire_corpus(
        root,
        specs=specs,
        repository_count=2,
        tasks_per_repository=2,
        workers=4,
        retries=1,
        fetch_once=fetch,
        sleep=lambda _: None,
    )
    report = study.analyze_study(
        root,
        freeze_output=tmp_path / "metric-freeze.json",
        report_output=tmp_path / "metric-report.json",
        specs=specs,
    )
    diversity_task = next(
        task
        for task in report["candidate_patch_diversity"]["tasks"]
        if task["instance_id"] == instance_id
    )
    signature_task = next(
        task
        for task in report["report_test_signature_comparability"]["tasks"]
        if task["instance_id"] == instance_id
    )
    assert diversity_task["unique_patch_sha256_count"] == 2
    assert len(diversity_task["duplicate_patch_groups"]) == 1
    assert signature_task["exact_test_signature_match"] is False
    assert report["report_test_signature_comparability"]["test_signature_mismatch_task_count"] == 1


def test_canonical_dataset_projection_and_task_identity_binding(
    tmp_path: pathlib.Path,
) -> None:
    rows = [
        _dataset_row(
            "alpha__repo-1",
            base_commit="a" * 40,
            environment_setup_commit="b" * 40,
        ),
        _dataset_row(
            "alpha__repo-2",
            base_commit="c" * 40,
            environment_setup_commit="d" * 40,
        ),
    ]
    identities, summary = study._parse_canonical_dataset_projection(
        _canonical_parquet(rows),
        expected_count=2,
    )
    assert [identity.instance_id for identity in identities] == [
        "alpha__repo-1",
        "alpha__repo-2",
    ]
    assert summary["projection_fields"] == list(study.CANONICAL_DATASET_PROJECTION_FIELDS)
    assert identities[0].canonical_digest() != identities[1].canonical_digest()

    root, specs, _ = _acquire(tmp_path, name="canonical-binding")
    manifest, _ = study.validate_acquisition(root, specs=specs)
    sanitized = study.sanitize_feature_inputs(manifest, specs=specs)
    task_identities = tuple(
        study.CanonicalTaskIdentity(
            instance_id=instance_id,
            repository=study.infer_repository(instance_id),
            base_commit=character * 40,
            environment_setup_commit=character * 40,
        )
        for instance_id, character in zip(
            sanitized.selected_instance_ids,
            ("a", "b", "c", "d"),
            strict=True,
        )
    )
    selected_payload = (
        strict_json_dumps(
            [identity.to_dict() for identity in task_identities],
            indent=2,
        )
        + "\n"
    ).encode()
    bound_input = study.FeatureBuildInput(
        selected_instance_ids=sanitized.selected_instance_ids,
        selected_instance_ids_sha256=sanitized.selected_instance_ids_sha256,
        submission_keys=sanitized.submission_keys,
        artifacts=sanitized.artifacts,
        canonical_task_identities=task_identities,
        canonical_dataset_identity={
            "dataset_id": study.CANONICAL_DATASET_ID,
            "revision": study.CANONICAL_DATASET_REVISION,
            "bytes": study.CANONICAL_DATASET_BYTES,
            "sha256": study.CANONICAL_DATASET_SHA256,
            "identity_projection_sha256": study.CANONICAL_DATASET_PROJECTION_SHA256,
            "selected_task_identities_sha256": _sha256(selected_payload),
        },
        acquisition_code_identity=sanitized.acquisition_code_identity,
    )
    freeze, _ = study.build_feature_freeze(root, bound_input, specs=specs)
    assert freeze["cohort_identity"]["canonical_task_identity_count"] == 4
    assert all(row["canonical_task_identity"] is not None for row in freeze["rows"])


def test_missing_trajectory_is_explicit_patch_only_state(tmp_path: pathlib.Path) -> None:
    missing = frozenset({("alpha__repo-1", "gpt5", "trajectory.json")})
    root, specs, _ = _acquire(tmp_path, missing=missing)
    manifest, _ = study.validate_acquisition(root, specs=specs)
    feature_input = study.sanitize_feature_inputs(manifest, specs=specs)
    freeze, rows = study.build_feature_freeze(root, feature_input, specs=specs)
    target = next(
        row for row in rows if row.instance_id == "alpha__repo-1" and row.submission_key == "gpt5"
    )
    assert target.status == "patch_only"
    assert target.rollout_history_nodes is None
    assert target.feature_record["post_rollout_history_identity"]["availability"] == "unavailable"
    for policy_orders in freeze["full_candidate_orders"].values():
        assert all(len(order["ordered_rollout_ids"]) == 3 for order in policy_orders)


def test_tampered_artifact_and_candidate_order_fail_closed(tmp_path: pathlib.Path) -> None:
    root, specs, _ = _acquire(tmp_path)
    manifest, _ = study.validate_acquisition(root, specs=specs)
    feature_input = study.sanitize_feature_inputs(manifest, specs=specs)
    freeze, rows = study.build_feature_freeze(root, feature_input, specs=specs)
    freeze["full_candidate_orders"]["hash_random"][0]["ordered_rollout_ids"].reverse()
    with pytest.raises(ValueError, match="digest drifted"):
        study._validated_orders(freeze, rows)
    freeze_path = tmp_path / "tampered-freeze.json"
    study.atomic_write(freeze_path, strict_json_dumps(freeze, indent=2) + "\n")
    with pytest.raises(ValueError, match="cannot be exactly rederived"):
        study.load_durable_feature_freeze(
            freeze_path,
            root,
            feature_input,
            specs=specs,
        )

    patch_path = next(root.glob("artifacts/*/gpt5/patch.diff"))
    patch_path.write_bytes(patch_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="identity drifted"):
        study.validate_acquisition(root, specs=specs)


def test_hosted_report_rejects_contradictory_resolved_label() -> None:
    instance_id = "alpha__repo-1"
    valid = study.parse_hosted_report(_report(instance_id, resolved=True), instance_id)
    assert valid["hosted_resolved"] is True
    decoded = study.strict_json_loads(_report(instance_id, resolved=True).decode())
    decoded[instance_id]["resolved"] = False
    contradictory = (strict_json_dumps(decoded) + "\n").encode()
    with pytest.raises(ValueError, match="contradicts"):
        study.parse_hosted_report(contradictory, instance_id)


def test_best_of_n_budget_consumes_frozen_order_without_backfill() -> None:
    order = ("a", "b", "c")
    labels = {"a": False, "b": True, "c": False}
    assert study._select_with_budget(order, labels, maximum_reveals=0) == (
        "a",
        0,
        (),
        "highest_ranked_unrevealed_after_observed_failures",
    )
    assert study._select_with_budget(order, labels, maximum_reveals=1) == (
        "b",
        1,
        ("a",),
        "highest_ranked_unrevealed_after_observed_failures",
    )
    assert study._select_with_budget(order, labels, maximum_reveals=2) == (
        "b",
        2,
        ("a", "b"),
        "first_revealed_success",
    )
