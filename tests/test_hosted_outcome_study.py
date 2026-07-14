"""Offline tests for the bounded hosted-outcome development study."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import threading
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bench_cleanser.verification._io import strict_json_dumps
from bench_cleanser.verification.manifest import build_candidate_manifest
from bench_cleanser.verification.models import LifecycleStage
from bench_cleanser.verification.router import ConservativeRouter

SCRIPT = (
    pathlib.Path(__file__).parents[1]
    / "experiments"
    / "hosted_outcome_study"
    / "run_study.py"
)
SPEC = importlib.util.spec_from_file_location("hosted_outcome_study", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
study = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = study
SPEC.loader.exec_module(study)


def _listing(instance_ids: list[str], *, truncated: bool = False) -> bytes:
    namespace = "http://s3.amazonaws.com/doc/2006-03-01/"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}ListBucketResult")
    for name, value in (
        ("Name", study.BUCKET_NAME),
        ("Prefix", study.ROOT_PREFIX),
        ("KeyCount", str(len(instance_ids))),
        ("MaxKeys", "1000"),
        ("Delimiter", "/"),
        ("IsTruncated", str(truncated).lower()),
    ):
        ET.SubElement(root, f"{{{namespace}}}{name}").text = value
    for instance_id in instance_ids:
        common = ET.SubElement(root, f"{{{namespace}}}CommonPrefixes")
        ET.SubElement(common, f"{{{namespace}}}Prefix").text = (
            f"{study.ROOT_PREFIX}{instance_id}/"
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _object_listing(objects: Mapping[str, bytes]) -> bytes:
    namespace = "http://s3.amazonaws.com/doc/2006-03-01/"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}ListBucketResult")
    for name, value in (
        ("Name", study.BUCKET_NAME),
        ("Prefix", study.ROOT_PREFIX),
        ("KeyCount", str(len(objects))),
        ("MaxKeys", "1000"),
        ("IsTruncated", "false"),
    ):
        ET.SubElement(root, f"{{{namespace}}}{name}").text = value
    for key, payload in sorted(objects.items()):
        content = ET.SubElement(root, f"{{{namespace}}}Contents")
        ET.SubElement(content, f"{{{namespace}}}Key").text = key
        ET.SubElement(content, f"{{{namespace}}}Size").text = str(len(payload))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _patch(instance_id: str, index: int) -> bytes:
    test_path = f"tests/test_{index}.py" if index % 2 else f"src/module_{index}.py"
    additions = "".join(f"+value_{line} = {line}\n" for line in range(index + 1))
    return (
        f"diff --git a/{test_path} b/{test_path}\n"
        f"--- a/{test_path}\n"
        f"+++ b/{test_path}\n"
        f"@@ -1 +1,{index + 1} @@\n"
        "-value = 0\n"
        f"{additions}"
    ).encode()


def _report(instance_id: str, *, resolved: bool) -> bytes:
    payload = {
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
                "FAIL_TO_FAIL": {"success": ["still_fails"], "failure": []},
                "PASS_TO_FAIL": {"success": ["new_failure_check"], "failure": []},
            },
        }
    }
    return (strict_json_dumps(payload, indent=2) + "\n").encode()


def _dataset_row(
    instance_id: str,
    *,
    repository: str | None = None,
    base_commit: str = "a" * 40,
    environment_setup_commit: str = "b" * 40,
) -> dict[str, str]:
    return {
        "repo": repository or study.infer_repository(instance_id),
        "instance_id": instance_id,
        "base_commit": base_commit,
        "patch": "privileged gold patch",
        "test_patch": "privileged oracle patch",
        "problem_statement": "privileged task text",
        "hints_text": "privileged hints",
        "created_at": "2024-01-01T00:00:00Z",
        "version": "1.0",
        "FAIL_TO_PASS": '["target"]',
        "PASS_TO_PASS": '["regression"]',
        "environment_setup_commit": environment_setup_commit,
        "difficulty": "medium",
    }


def _canonical_parquet(rows: list[dict[str, str]]) -> bytes:
    schema = pa.schema(
        [pa.field(name, pa.string(), nullable=True) for name in study.CANONICAL_DATASET_SCHEMA_FIELDS]
    )
    table = pa.Table.from_pylist(rows, schema=schema)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    return sink.getvalue().to_pybytes()


def _frame(
    count: int = 8,
    *,
    missing_reports: frozenset[str] = frozenset(),
    flip_labels: bool = False,
    instance_ids_override: list[str] | None = None,
) -> tuple[list[str], dict[str, bytes]]:
    instance_ids = (
        sorted(instance_ids_override)
        if instance_ids_override is not None
        else sorted(f"owner{index}__repo{index}-{100 + index}" for index in range(count))
    )
    if len(instance_ids) != count:
        raise ValueError("fixture instance ID count drifted")
    payloads = {study._frame_listing_url(): _listing(instance_ids)}
    object_payloads: dict[str, bytes] = {}
    for index, instance_id in enumerate(instance_ids, start=1):
        patch = _patch(instance_id, index)
        patch_url = study._artifact_url(instance_id, "patch.diff")
        payloads[patch_url] = patch
        object_payloads[f"{study.ROOT_PREFIX}{instance_id}/patch.diff"] = patch
        if instance_id not in missing_reports:
            report = _report(instance_id, resolved=index % 2 == 0)
            if flip_labels:
                report = _report(instance_id, resolved=index % 2 != 0)
            report_url = study._artifact_url(instance_id, "report.json")
            payloads[report_url] = report
            object_payloads[f"{study.ROOT_PREFIX}{instance_id}/report.json"] = report
    payloads[study._object_listing_url()] = _object_listing(object_payloads)
    return instance_ids, payloads


def _fake_fetcher(
    payloads: Mapping[str, bytes],
    *,
    transient_url: str | None = None,
    permanent_url: str | None = None,
) -> tuple[Any, dict[str, int]]:
    calls: dict[str, int] = {}
    lock = threading.Lock()

    def fetch(
        url: str,
        *,
        maximum_bytes: int,
        timeout_seconds: float,
        budget: Any,
    ) -> Any:
        assert 0 < timeout_seconds <= 120
        with lock:
            calls[url] = calls.get(url, 0) + 1
            attempt = calls[url]
        if url == transient_url and attempt == 1:
            raise study.TransientFetchError("fixture timeout")
        if url == permanent_url:
            raise ValueError("fixture permanent failure")
        payload = payloads[url]
        assert len(payload) <= maximum_bytes
        budget.consume(len(payload))
        return study.DownloadedObject(payload=payload, final_url=url)

    return fetch, calls


def _acquire_fixture(
    tmp_path: pathlib.Path,
    *,
    count: int = 8,
    missing_reports: frozenset[str] = frozenset(),
    flip_labels: bool = False,
    instance_ids_override: list[str] | None = None,
) -> pathlib.Path:
    _, payloads = _frame(
        count,
        missing_reports=missing_reports,
        flip_labels=flip_labels,
        instance_ids_override=instance_ids_override,
    )
    fetch, _ = _fake_fetcher(payloads)
    root = tmp_path / "acquisition"
    study.acquire_corpus(
        root,
        expected_count=count,
        workers=4,
        retries=2,
        fetch_once=fetch,
        sleep=lambda _: None,
    )
    return root


def test_exact_listing_enumeration_is_complete_confined_and_unique() -> None:
    instance_ids, _ = _frame(3)
    assert study.enumerate_instance_ids(
        _listing(instance_ids), expected_count=3
    ) == tuple(instance_ids)

    with pytest.raises(ValueError, match="truncated"):
        study.enumerate_instance_ids(
            _listing(instance_ids, truncated=True), expected_count=3
        )
    with pytest.raises(ValueError, match="duplicate"):
        study.enumerate_instance_ids(
            _listing([instance_ids[0], instance_ids[0]]), expected_count=2
        )
    with pytest.raises(ValueError, match="unconfined|unsupported"):
        study.enumerate_instance_ids(
            _listing(["../escape__repo-1"]), expected_count=1
        )
    with pytest.raises(ValueError, match="DTD/entity"):
        study.enumerate_instance_ids(
            b'<!DOCTYPE x [<!ENTITY e "x">]><x>&e;</x>', expected_count=1
        )


def test_acquisition_uses_only_allowlisted_artifacts_retries_and_publishes_atomically(
    tmp_path: pathlib.Path,
) -> None:
    instance_ids, payloads = _frame(3)
    transient_url = study._artifact_url(instance_ids[0], "patch.diff")
    fetch, calls = _fake_fetcher(payloads, transient_url=transient_url)
    root = tmp_path / "corpus"

    manifest = study.acquire_corpus(
        root,
        expected_count=3,
        workers=3,
        retries=2,
        fetch_once=fetch,
        sleep=lambda _: None,
    )

    assert calls[transient_url] == 2
    assert set(calls) == {
        study._frame_listing_url(),
        study._object_listing_url(),
        *(
            study._artifact_url(instance_id, name)
            for instance_id in instance_ids
            for name in study.ARTIFACT_NAMES
        ),
    }
    assert manifest["totals"]["object_count"] == 6
    assert manifest["source"]["submission_checked"] is False
    assert not list(root.rglob("trajectory.json"))
    assert (root / "source_manifest.json").is_file()
    assert not (tmp_path / ".corpus.lock").exists()
    assert not list(tmp_path.glob(".corpus.staging.*"))


def test_failed_acquisition_leaves_no_partial_published_tree(
    tmp_path: pathlib.Path,
) -> None:
    instance_ids, payloads = _frame(2)
    failed_url = study._artifact_url(instance_ids[-1], "report.json")
    fetch, _ = _fake_fetcher(payloads, permanent_url=failed_url)
    root = tmp_path / "corpus"

    with pytest.raises(RuntimeError, match="acquisition failed"):
        study.acquire_corpus(
            root,
            expected_count=2,
            workers=2,
            retries=1,
            fetch_once=fetch,
            sleep=lambda _: None,
        )

    assert not root.exists()
    assert not (tmp_path / ".corpus.lock").exists()
    assert not list(tmp_path.glob(".corpus.staging.*"))


def test_source_url_and_instance_defenses_are_exact() -> None:
    study._validate_source_url(study._frame_listing_url(), listing=True)
    study._validate_source_url(study._object_listing_url(), listing=True)
    study._validate_source_url(
        study._artifact_url("owner__repo-1", "patch.diff")
    )
    for url in (
        "http://swe-bench-submissions.s3.amazonaws.com/x",
        "https://example.com/verified/x/patch.diff",
        (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/"
            f"{study.SUBMISSION_ID}/trajs/owner__repo-1/trajectory.json"
        ),
        study._artifact_url("owner__repo-1", "patch.diff") + "?version=other",
    ):
        with pytest.raises(ValueError):
            study._validate_source_url(url)
    for instance_id in ("../owner__repo-1", "owner/repo__repo-1", "owner__repo"):
        with pytest.raises(ValueError):
            study.infer_repository(instance_id)


def test_analysis_uses_reference_free_router_risk_then_separate_hosted_labels(
    tmp_path: pathlib.Path,
) -> None:
    root = _acquire_fixture(tmp_path)
    report = study.analyze_study(
        root,
        expected_count=8,
        budget_fractions=(0.5,),
    )

    assert report["sampling_frame"]["candidate_count"] == 8
    assert report["sampling_frame"]["analyzable_candidate_count"] == 8
    assert report["sampling_frame"]["repository_count"] == 8
    assert report["sampling_frame"]["hosted_harness_resolved_count"] == 4
    assert report["sampling_frame"]["hosted_harness_failure_count"] == 4
    assert report["sampling_frame"]["budget_counts"] == [4]
    assert report["patch_only_feature_freeze"][
        "completed_before_any_outcome_decode"
    ] is True
    freeze = report["patch_only_feature_freeze"]
    assert len(freeze["rows"]) == 8
    assert freeze["base_policy_order_count"] == 4
    assert freeze["tie_seed_policy_order_count"] == 48
    assert set(freeze["base_full_policy_orders"]) == set(study.TRIAGE_POLICIES)
    assert set(freeze["tie_seed_full_policy_orders"]) == set(
        study.TIE_SENSITIVE_POLICIES
    )
    for policy, order in freeze["base_full_policy_orders"].items():
        assert order["policy"] == policy
        assert order["seed"] == study.DEFAULT_RANDOM_SEED
        assert order["candidate_count"] == 8
        assert len(order["ordered_candidates"]) == 8
        assert len({item["instance_id"] for item in order["ordered_candidates"]}) == 8
        assert len(order["sha256"]) == 64
    for policy, orders in freeze["tie_seed_full_policy_orders"].items():
        assert len(orders) == 16
        assert [item["seed"] for item in orders] == list(
            range(study.DEFAULT_RANDOM_SEED, study.DEFAULT_RANDOM_SEED + 16)
        )
        assert all(item["policy"] == policy for item in orders)
        assert all(item["candidate_count"] == 8 for item in orders)
    assert report["scientific_status"]["independent_truth"] is False
    assert report["scientific_status"]["supports_hypotheses_h1_to_h6"] is False
    assert report["scientific_status"]["retrospective_development_evidence"] is True
    diagnostic = report["post_hoc_discrimination_diagnostic"]
    assert diagnostic["computed_only_after_outcome_reveal"] is True
    assert diagnostic["selection_or_policy_input"] is False
    assert diagnostic["signals"]["candidate_risk"]["finite_frame_roc_auc"] is not None

    first = report["candidates"][0]
    patch = (root / first["instance_id"] / "patch.diff").read_text()
    manifest = build_candidate_manifest(
        instance_id=first["instance_id"],
        candidate_patch=patch,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        provenance={
            "repository": first["repository"],
            "candidate_generator": study.SUBMISSION_ID,
            "source_bucket": study.BUCKET_NAME,
            "source_prefix": study.ROOT_PREFIX,
        },
    )
    expected_risk = ConservativeRouter().route(manifest).candidate_risk
    assert first["reference_free"]["candidate_risk"] == expected_risk
    assert first["reference_free"]["initial_route_action"] == "run_static"
    assert "hosted_outcome" not in first["reference_free"]
    assert set(first["hosted_outcome"]) >= {
        "hosted_harness_resolved",
        "fail_to_pass_success",
        "fail_to_pass_failure",
        "pass_to_pass_success",
        "pass_to_pass_failure",
    }

    results = {
        (item["policy"], item["requested_budget_count"]): item
        for item in report["policies"]
    }
    assert results[("accept_all", 0)]["metrics"]["false_accept_count"] == 4
    assert results[("accept_all", 0)]["metrics"][
        "false_accept_fraction_among_accepted"
    ] == 0.5
    assert results[("execute_all", 8)]["metrics"]["false_accept_count"] == 0
    assert results[("execute_all", 8)]["metrics"]["false_reject_count"] == 0
    for policy in (
        "risk_top_budget",
        "patch_size_top_budget",
        "touches_tests_first",
        "seeded_random",
    ):
        item = results[(policy, 4)]
        assert item["metrics"]["execution_count"] == 4
        assert item["execution_cost_proxy"]["execution_units"] == 4
        assert item["execution_cost_proxy"][
            "actual_repository_or_test_execution_performed"
        ] is False
        assert item["selection_semantics"] == (
            "retrospective_hosted_label_reveal_no_reexecution"
        )
        assert len(item["executed_instance_ids"]) == 4
        assert len(item["by_repository"]) == 8
        assert item["by_subgroup"]
        assert item["uniform_random_matched_budget_reference"]["status"].startswith(
            "exact_finite"
        )
        assert item[
            "repository_stratified_random_matched_budget_reference"
        ]["status"].startswith("exact_repository_stratified_three_category")
        assert "descriptive_delta_vs_uniform_random_expectation" in item
        assert "paired_delta_vs_uniform_random_expectation" not in item
        assert item["sampling_uncertainty"]["cluster_bootstrap_reported"] is False


def test_missing_report_is_quarantined_but_selected_without_backfill(
    tmp_path: pathlib.Path,
) -> None:
    instance_ids, _ = _frame(8)
    missing_id = instance_ids[-1]
    root = _acquire_fixture(
        tmp_path,
        count=8,
        missing_reports=frozenset({missing_id}),
    )

    report = study.analyze_study(
        root,
        expected_count=8,
        budget_fractions=(0.5,),
    )

    assert report["sampling_frame"]["candidate_count"] == 8
    assert report["sampling_frame"]["analyzable_candidate_count"] == 7
    assert report["sampling_frame"]["missing_report_count"] == 1
    missing_row = next(
        item for item in report["candidates"] if item["instance_id"] == missing_id
    )
    assert missing_row["analysis_status"] == "mandatory_quarantine"
    assert missing_row["reference_free"] is not None
    assert missing_row["hosted_outcome"] is None

    results = {
        (item["policy"], item["requested_budget_count"]): item
        for item in report["policies"]
    }
    execute_all = results[("execute_all", 8)]
    assert execute_all["realized_execution_count"] == 8
    assert execute_all["metrics"]["selected_unknown_hosted_outcome_count"] == 1
    assert missing_id in execute_all["executed_instance_ids"]

    risk = results[("risk_top_budget", 4)]
    frozen_order = [
        item["instance_id"]
        for item in report["patch_only_feature_freeze"][
            "base_full_policy_orders"
        ]["risk_top_budget"]["ordered_candidates"]
    ]
    assert risk["executed_instance_ids"] == sorted(frozen_order[:4])
    if missing_id in frozen_order[:4]:
        assert risk["metrics"]["selected_unknown_hosted_outcome_count"] == 1
        assert missing_id in risk["executed_instance_ids"]


def test_hosted_report_schema_is_exact_and_application_requires_patch() -> None:
    instance_id = "owner__repo-1"
    valid = _report(instance_id, resolved=True)
    decoded = study.strict_json_loads(valid.decode())
    decoded[instance_id]["unexpected"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        study._parse_hosted_report(
            (strict_json_dumps(decoded) + "\n").encode(), instance_id
        )

    decoded = study.strict_json_loads(valid.decode())
    decoded[instance_id]["patch_exists"] = False
    decoded[instance_id]["patch_is_None"] = True
    with pytest.raises(ValueError, match="absent patch"):
        study._parse_hosted_report(
            (strict_json_dumps(decoded) + "\n").encode(), instance_id
        )

    decoded = study.strict_json_loads(valid.decode())
    decoded[instance_id]["tests_status"]["UNKNOWN_GROUP"] = {
        "success": [],
        "failure": [],
    }
    with pytest.raises(ValueError, match="unknown fields"):
        study._parse_hosted_report(
            (strict_json_dumps(decoded) + "\n").encode(), instance_id
        )

    decoded = study.strict_json_loads(valid.decode())
    decoded[instance_id]["tests_status"]["PASS_TO_PASS"]["success"] = ["target"]
    with pytest.raises(ValueError, match="repeats a test ID"):
        study._parse_hosted_report(
            (strict_json_dumps(decoded) + "\n").encode(), instance_id
        )

    decoded = study.strict_json_loads(valid.decode())
    decoded[instance_id]["resolved"] = False
    with pytest.raises(ValueError, match="contradicts"):
        study._parse_hosted_report(
            (strict_json_dumps(decoded) + "\n").encode(), instance_id
        )


def test_report_labels_digests_and_availability_cannot_change_frozen_policy(
    tmp_path: pathlib.Path,
) -> None:
    instance_ids, _ = _frame(8)
    baseline_root = _acquire_fixture(tmp_path / "baseline")
    flipped_root = _acquire_fixture(tmp_path / "flipped", flip_labels=True)
    missing_root = _acquire_fixture(
        tmp_path / "missing",
        missing_reports=frozenset({instance_ids[-1]}),
    )
    reports = [
        study.analyze_study(root, expected_count=8, budget_fractions=(0.5,))
        for root in (baseline_root, flipped_root, missing_root)
    ]

    freezes = [report["patch_only_feature_freeze"] for report in reports]
    assert len({freeze["sha256"] for freeze in freezes}) == 1
    assert freezes[0]["rows"] == freezes[1]["rows"] == freezes[2]["rows"]
    assert (
        freezes[0]["base_full_policy_orders"]
        == freezes[1]["base_full_policy_orders"]
        == freezes[2]["base_full_policy_orders"]
    )
    assert (
        freezes[0]["tie_seed_full_policy_orders"]
        == freezes[1]["tie_seed_full_policy_orders"]
        == freezes[2]["tie_seed_full_policy_orders"]
    )

    def selections(report: Mapping[str, Any]) -> dict[tuple[str, int], list[str]]:
        return {
            (item["policy"], item["requested_budget_count"]): item[
                "executed_instance_ids"
            ]
            for item in report["policies"]
        }

    assert selections(reports[0]) == selections(reports[1]) == selections(reports[2])
    baseline_report_digests = {
        item["instance_id"]: item["artifacts"]["report.json"]["sha256"]
        for item in reports[0]["candidates"]
    }
    flipped_report_digests = {
        item["instance_id"]: item["artifacts"]["report.json"]["sha256"]
        for item in reports[1]["candidates"]
    }
    assert baseline_report_digests != flipped_report_digests


def test_all_orders_freeze_before_report_decode_and_are_only_consumed(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _acquire_fixture(tmp_path)
    real_freeze_order = study._freeze_policy_order
    real_parse_report = study._parse_hosted_report
    frozen_order_calls: list[tuple[str, int]] = []
    report_parse_count = 0

    def tracked_freeze_order(candidates, policy, *, seed):
        frozen_order_calls.append((policy, seed))
        return real_freeze_order(candidates, policy, seed=seed)

    def forbidden_recompute(*args, **kwargs):
        pytest.fail("policy order was recomputed after hosted labels were revealed")

    def tracked_parse_report(payload, instance_id):
        nonlocal report_parse_count
        assert len(frozen_order_calls) == 4 + 3 * 16
        monkeypatch.setattr(study, "_policy_order", forbidden_recompute)
        report_parse_count += 1
        return real_parse_report(payload, instance_id)

    monkeypatch.setattr(study, "_freeze_policy_order", tracked_freeze_order)
    monkeypatch.setattr(study, "_parse_hosted_report", tracked_parse_report)
    report = study.analyze_study(
        root,
        expected_count=8,
        budget_fractions=(0.5,),
    )

    assert report_parse_count == 8
    assert report["patch_only_feature_freeze"][
        "completed_before_any_outcome_decode"
    ] is True


def test_patch_freeze_accepts_only_sanitized_patch_identities(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(TypeError, match="only PatchArtifactIdentity"):
        study._build_patch_only_freeze(
            tmp_path,
            [{"instance_id": "owner__repo-1", "resolved": True}],
            policy_seed=7,
        )


def test_pinned_results_stay_opaque_until_explicit_post_freeze_reveal(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = (
        "tags:\n"
        "  checked: false\n"
        "  system:\n"
        "    attempts: 1\n"
        "assets:\n"
        f"  logs: s3://{study.BUCKET_NAME}/{study.ROOT_PREFIX.removesuffix('/')}\n"
        f"  trajs: s3://{study.BUCKET_NAME}/verified/{study.SUBMISSION_ID}/trajs\n"
    ).encode()
    opaque_results = b"not-json-and-must-not-be-decoded-during-acquisition"
    monkeypatch.setattr(
        study,
        "PINNED_SUBMISSION_SOURCES",
        {
            "metadata.yml": ("https://example.test/metadata", hashlib.sha256(metadata).hexdigest()),
            "results.json": (
                "https://example.test/results",
                hashlib.sha256(opaque_results).hexdigest(),
            ),
        },
    )
    semantics = study._validate_pinned_submission_sources_without_outcomes({
        "metadata.yml": metadata,
        "results.json": opaque_results,
    })
    assert semantics["official_results_decode"].startswith("deferred_until")

    results_payload = strict_json_dumps({
        "no_generation": [],
        "no_logs": ["owner__repo-1"],
        "resolved": [],
    }).encode()
    (tmp_path / "submission-results.json").write_bytes(results_payload)
    monkeypatch.setattr(study, "EXPECTED_INSTANCE_COUNT", 1)
    monkeypatch.setattr(
        study,
        "SUBMISSION_RESULTS_SHA256",
        hashlib.sha256(results_payload).hexdigest(),
    )
    with pytest.raises(ValueError, match="before feature freeze"):
        study._reveal_pinned_official_results(
            tmp_path,
            expected_count=1,
            feature_freeze={"completed_before_any_outcome_decode": False},
        )
    revealed = study._reveal_pinned_official_results(
        tmp_path,
        expected_count=1,
        feature_freeze={
            "completed_before_any_outcome_decode": True,
            "sha256": "a" * 64,
        },
    )
    assert revealed == {
        "no_generation": [],
        "no_logs": ["owner__repo-1"],
        "resolved": [],
    }


def test_micro_macro_and_fixed_decision_loo_use_imbalanced_repository_rows(
    tmp_path: pathlib.Path,
) -> None:
    instance_ids = [
        "big__repo-1",
        "big__repo-2",
        "big__repo-3",
        "big__repo-4",
        "small__repo-1",
        "small__repo-2",
    ]
    root = _acquire_fixture(
        tmp_path,
        count=6,
        instance_ids_override=instance_ids,
    )
    report = study.analyze_study(
        root,
        expected_count=6,
        budget_fractions=(0.5,),
    )
    accept_all = next(item for item in report["policies"] if item["policy"] == "accept_all")

    assert accept_all["metrics"]["frame_candidate_count"] == 6
    assert accept_all["metrics"]["hosted_harness_failure_count"] == 3
    by_repository = {
        item["repository"]: item for item in accept_all["by_repository"]
    }
    assert by_repository["big/repo"]["frame_candidate_count"] == 4
    assert by_repository["big/repo"]["hosted_harness_failure_count"] == 2
    assert by_repository["small/repo"]["frame_candidate_count"] == 2
    assert by_repository["small/repo"]["hosted_harness_failure_count"] == 1
    assert accept_all["macro_repository_summary"][
        "macro_false_accept_fraction_among_accepted"
    ] == 0.5
    loo = {
        item["excluded_repository"]: item
        for item in accept_all[
            "leave_one_repository_out_fixed_decision_deletion_sensitivity"
        ]
    }
    assert loo["big/repo"]["frame_candidate_count"] == 2
    assert loo["big/repo"]["hosted_harness_failure_count"] == 1
    assert loo["small/repo"]["frame_candidate_count"] == 4
    assert loo["small/repo"]["hosted_harness_failure_count"] == 2


def test_outcome_blind_ties_and_exact_randomization_are_deterministic() -> None:
    assert study._finite_frame_roc_auc([(1.0, True), (0.0, False)]) == 1.0
    assert study._finite_frame_roc_auc([(0.5, True), (0.5, False)]) == 0.5

    def candidate(instance_id: str, risk: float, lines: int) -> Any:
        return study.PolicyCandidate(
            instance_id=instance_id,
            repository=study.infer_repository(instance_id),
            candidate_id=f"sha256:{'a' if instance_id.endswith('1') else 'b'}" * 1,
            manifest_sha256="c" * 64,
            candidate_risk=risk,
            router_policy_version="fixture",
            initial_route_action="run_static",
            risk_profile={
                "touches_tests": True,
                "lines_changed": lines,
                "files_changed": 1,
            },
            patch_bytes=10,
            patch_sha256="d" * 64,
        )

    candidates = [
        candidate("owner__repo-1", 0.0, 1),
        candidate("owner__repo-2", 1.0, 1_000),
    ]
    expected = sorted(
        candidates,
        key=lambda item: study._outcome_blind_tie_key(item, 7),
    )
    assert study._policy_order(
        candidates, "touches_tests_first", seed=7
    ) == expected
    assert study._policy_order(
        candidates, "touches_tests_first", seed=7
    ) == study._policy_order(candidates, "touches_tests_first", seed=7)

    distribution = study._hypergeometric_randomization_distribution(
        population=4,
        hosted_failures=2,
        unknown_outcomes=1,
        execution_count=2,
    )
    assert sum(item["probability"] for item in distribution["support"]) == pytest.approx(1.0)
    quantiles = distribution["false_accept_fraction_quantiles"]
    assert quantiles["q025"] <= quantiles["q50"] <= quantiles["q975"]


def test_policy_hash_collisions_fail_instead_of_using_instance_id_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def candidate(instance_id: str) -> Any:
        return study.PolicyCandidate(
            instance_id=instance_id,
            repository=study.infer_repository(instance_id),
            candidate_id="sha256:" + instance_id.encode().hex().ljust(64, "0")[:64],
            manifest_sha256="c" * 64,
            candidate_risk=0.5,
            router_policy_version="fixture",
            initial_route_action="run_static",
            risk_profile={
                "touches_tests": True,
                "lines_changed": 1,
                "files_changed": 1,
            },
            patch_bytes=10,
            patch_sha256="d" * 64,
        )

    candidates = [candidate("owner__repo-1"), candidate("owner__repo-2")]
    monkeypatch.setattr(
        study,
        "_deterministic_random_key",
        lambda instance_id, seed: "0" * 64,
    )
    with pytest.raises(ValueError, match="collision.*refusing"):
        study._policy_order(candidates, "seeded_random", seed=7)

    monkeypatch.setattr(
        study,
        "_outcome_blind_tie_key",
        lambda candidate, seed: "1" * 64,
    )
    with pytest.raises(ValueError, match="collision.*refusing"):
        study._policy_order(candidates, "risk_top_budget", seed=7)


def test_rebound_frozen_order_must_still_be_a_full_candidate_permutation() -> None:
    candidates = [
        study.PolicyCandidate(
            instance_id=f"owner__repo-{index}",
            repository="owner/repo",
            candidate_id="sha256:" + str(index) * 64,
            manifest_sha256="c" * 64,
            candidate_risk=0.5,
            router_policy_version="fixture",
            initial_route_action="run_static",
            risk_profile={
                "touches_tests": True,
                "lines_changed": 1,
                "files_changed": 1,
            },
            patch_bytes=10,
            patch_sha256="d" * 64,
        )
        for index in (1, 2)
    ]
    record = study._freeze_policy_order(
        candidates,
        "risk_top_budget",
        seed=7,
    )
    tampered = study.strict_json_loads(strict_json_dumps(record))
    tampered["ordered_candidates"][1] = dict(tampered["ordered_candidates"][0])
    tampered_payload = {
        key: value for key, value in tampered.items() if key != "sha256"
    }
    tampered["sha256"] = hashlib.sha256(
        strict_json_dumps(tampered_payload).encode()
    ).hexdigest()

    with pytest.raises(ValueError, match="repeats|not a full"):
        study._consume_frozen_policy_order(
            candidates,
            tampered,
            policy="risk_top_budget",
            seed=7,
        )


def test_repository_stratified_reference_convolves_three_terminal_categories(
    tmp_path: pathlib.Path,
) -> None:
    instance_ids = [f"owner__repo-{index}" for index in range(1, 5)]
    missing_id = instance_ids[-1]
    root = _acquire_fixture(
        tmp_path,
        count=4,
        missing_reports=frozenset({missing_id}),
        instance_ids_override=instance_ids,
    )
    manifest = study._validate_acquisition_manifest(root, expected_count=4)
    patch_rows, freeze = study._build_patch_only_freeze(
        root,
        study._sanitized_patch_identities(manifest),
        policy_seed=7,
    )
    rows = study._reveal_frame_rows(
        root,
        manifest,
        patch_rows,
        feature_freeze=freeze,
    )
    distribution = study._repository_stratified_randomization_distribution(
        rows,
        execution_count=2,
    )

    assert distribution["hosted_unresolved_count"] == 2
    assert distribution["hosted_resolved_count"] == 1
    assert distribution["unknown_quarantine_count"] == 1
    assert distribution["expected_caught_hosted_unresolved"] == pytest.approx(1.0)
    assert distribution["expected_selected_unknown_outcomes"] == pytest.approx(0.5)
    support = {
        (item["caught_hosted_unresolved"], item["selected_unknown_outcomes"]): item
        for item in distribution["support"]
    }
    assert support[(2, 0)]["probability"] == pytest.approx(1 / 6)
    assert support[(1, 0)]["probability"] == pytest.approx(2 / 6)
    assert support[(1, 1)]["probability"] == pytest.approx(2 / 6)
    assert support[(0, 1)]["probability"] == pytest.approx(1 / 6)
    assert support[(1, 0)]["accepted_known_outcome_count"] == 2
    assert support[(1, 1)]["accepted_known_outcome_count"] == 2
    assert support[(1, 0)]["false_accept_fraction_among_accepted"] == 0.5
    assert support[(1, 1)]["false_accept_fraction_among_accepted"] == 0.5
    assert all(
        item["quarantined_unknown_outcome_count"] == 1
        for item in distribution["support"]
    )


def test_analysis_rejects_tampering_symlinks_and_report_contradictions(
    tmp_path: pathlib.Path,
) -> None:
    root = _acquire_fixture(tmp_path / "tamper", count=2)
    patch_path = next(root.glob("*/patch.diff"))
    patch_path.write_bytes(patch_path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="bytes or digest drift"):
        study.analyze_study(
            root,
            expected_count=2,
            budget_fractions=(0.5,),
        )

    root = _acquire_fixture(tmp_path / "contradiction", count=2)
    report_path = next(root.glob("*/report.json"))
    instance_id = report_path.parent.name
    with pytest.raises(ValueError, match="contradicts|repeats"):
        study._parse_hosted_report(
            _report(instance_id, resolved=True).replace(
                b'"failure": []', b'"failure": ["target"]', 1
            ),
            instance_id,
        )

    root = _acquire_fixture(tmp_path / "symlink", count=2)
    patch_path = next(root.glob("*/patch.diff"))
    original = patch_path.read_bytes()
    patch_path.unlink()
    target = tmp_path / "external.diff"
    target.write_bytes(original)
    patch_path.symlink_to(target)
    with pytest.raises(ValueError, match="non-symlink"):
        study.analyze_study(
            root,
            expected_count=2,
            budget_fractions=(0.5,),
        )


def test_canonical_dataset_projection_accepts_legitimate_shared_base_commit() -> None:
    shared_commit = "c" * 40
    payload = _canonical_parquet(
        [
            _dataset_row("owner__repo-1", base_commit=shared_commit),
            _dataset_row("owner__repo-2", base_commit=shared_commit),
        ]
    )

    identities, summary = study._parse_canonical_dataset_projection(
        payload,
        expected_count=2,
    )

    assert [item.instance_id for item in identities] == [
        "owner__repo-1",
        "owner__repo-2",
    ]
    assert summary["unique_repository_base_commit_pair_count"] == 1
    assert summary["duplicate_repository_base_commit_pairs"] == [
        {
            "repository": "owner/repo",
            "base_commit": shared_commit,
            "instance_ids": ["owner__repo-1", "owner__repo-2"],
        }
    ]
    assert summary["cross_repository_base_commit_collision_count"] == 0
    projection_text = strict_json_dumps(
        [item.to_dict() for item in identities],
        indent=2,
    )
    assert "privileged gold patch" not in projection_text
    assert "privileged oracle patch" not in projection_text


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [_dataset_row("owner__repo-1"), _dataset_row("owner__repo-1")],
            "duplicate instance",
        ),
        (
            [_dataset_row("owner__repo-1", base_commit="A" * 40)],
            "base_commit is not lowercase 40-hex",
        ),
        (
            [_dataset_row("owner__repo-1", repository="other/repo")],
            "repository mismatch",
        ),
        (
            [
                _dataset_row("owner__repo-1", base_commit="d" * 40),
                _dataset_row("other__repo-2", base_commit="d" * 40),
            ],
            "reuses a base commit across repositories",
        ),
    ],
)
def test_canonical_dataset_projection_rejects_identity_drift(
    rows: list[dict[str, str]],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        study._parse_canonical_dataset_projection(
            _canonical_parquet(rows),
            expected_count=len(rows),
        )


def test_canonical_dataset_frame_crosscheck_rejects_set_mismatch() -> None:
    identities, _ = study._parse_canonical_dataset_projection(
        _canonical_parquet([_dataset_row("owner__repo-1")]),
        expected_count=1,
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        study._crosscheck_canonical_dataset_frame(
            identities,
            ["owner__repo-2"],
        )


def test_pinned_canonical_dataset_digest_drift_fails_before_parquet_decode() -> None:
    with pytest.raises(ValueError, match="parquet bytes drifted"):
        study._validate_pinned_canonical_dataset(b"not the pinned parquet")


def test_feature_freeze_binds_sanitized_canonical_task_identity(
    tmp_path: pathlib.Path,
) -> None:
    instance_id = "owner__repo-1"
    patch = _patch(instance_id, 1)
    patch_path = tmp_path / instance_id / "patch.diff"
    patch_path.parent.mkdir()
    patch_path.write_bytes(patch)
    task_identity = study.CanonicalTaskIdentity(
        instance_id=instance_id,
        repository="owner/repo",
        base_commit="a" * 40,
        environment_setup_commit="b" * 40,
    )
    patch_rows, freeze = study._build_patch_only_freeze(
        tmp_path,
        (
            study.PatchArtifactIdentity(
                instance_id=instance_id,
                repository="owner/repo",
                availability="downloaded",
                byte_count=len(patch),
                sha256=hashlib.sha256(patch).hexdigest(),
                error_code=None,
                base_commit=task_identity.base_commit,
                environment_setup_commit=task_identity.environment_setup_commit,
                canonical_task_identity_sha256=task_identity.canonical_digest(),
            ),
        ),
        policy_seed=7,
    )

    expected = {
        "base_commit": "a" * 40,
        "environment_setup_commit": "b" * 40,
        "sha256": task_identity.canonical_digest(),
    }
    assert freeze["rows"][0]["canonical_task_identity"] == expected
    assert patch_rows[0].reference_free is not None
    assert patch_rows[0].reference_free["canonical_task_identity"] == expected

    with pytest.raises(ValueError, match="identity is incomplete"):
        study._build_patch_only_freeze(
            tmp_path,
            (
                study.PatchArtifactIdentity(
                    instance_id=instance_id,
                    repository="owner/repo",
                    availability="downloaded",
                    byte_count=len(patch),
                    sha256=hashlib.sha256(patch).hexdigest(),
                    error_code=None,
                    base_commit="a" * 40,
                ),
            ),
            policy_seed=7,
        )
