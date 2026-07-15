"""Focused regressions for the fail-closed release supply-chain gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_auditor() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "audit_supply_chain.py"
    spec = importlib.util.spec_from_file_location("audit_supply_chain", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = _load_auditor()
ROOT = Path(__file__).parents[1]
POLICY = ROOT / "supply-chain" / "license-policy.toml"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _rebind_exact_record(
    monkeypatch: pytest.MonkeyPatch,
    *,
    prefix: str,
    path: Path,
) -> None:
    payload = path.read_bytes()
    monkeypatch.setattr(AUDITOR, f"{prefix}_BYTES", len(payload))
    monkeypatch.setattr(AUDITOR, f"{prefix}_DIGEST", hashlib.sha256(payload).digest())


def _inventory(
    *,
    package_name: str = "bench-cleanser",
    license_name: str = "MIT",
) -> list[dict[str, str]]:
    return [
        {
            "License": license_name,
            "LicenseText": "permission is hereby granted",
            "Name": package_name,
            "URL": "https://example.invalid/source",
            "Version": "0.1.0",
        },
        {
            "License": "MIT License",
            "LicenseText": "permission is hereby granted",
            "Name": "pip",
            "URL": "https://pip.pypa.io/",
            "Version": "26.1",
        },
    ]


def _sbom(*, package_name: str = "bench-cleanser") -> dict[str, Any]:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"name": "pip", "type": "library", "version": "26.1"}],
        "metadata": {"component": {"name": package_name, "type": "library", "version": "0.1.0"}},
    }


def test_ci_actions_are_commit_pinned_and_release_evidence_is_retained() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    uses = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", workflow, flags=re.MULTILINE)

    assert uses == [
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
        "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
        "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ]
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", use) for use in uses)
    assert (
        "name: bench-cleanser-release-gate-${{ github.sha }}-attempt-"
        "${{ github.run_attempt }}" in workflow
    )
    assert "path: ${{ runner.temp }}/bench-cleanser-dist" in workflow
    assert "if-no-files-found: error" in workflow
    assert "retention-days: 90" in workflow
    assert "Strict type check release and study scripts" in workflow
    assert "mypy --strict scripts/audit_supply_chain.py scripts/lock_literature.py" in workflow
    for script in (
        "experiments/hosted_outcome_study/run_study.py",
        "experiments/matched_rollout_study/run_study.py",
        "experiments/real_agent_pilot/run_pilot.py",
        "experiments/seed_study/run_seed_study.py",
        "experiments/independent_execution_smoke/run_smoke.py",
        "experiments/paired_execution_smoke/verify_evidence.py",
        "experiments/sphinx_execution_smoke/verify_evidence.py",
    ):
        assert f"mypy --strict {script}" in workflow
    for script in (
        "experiments/independent_execution_smoke/run_smoke.py",
        "experiments/paired_execution_smoke/verify_evidence.py",
        "experiments/sphinx_execution_smoke/verify_evidence.py",
    ):
        assert f"python {script}" in workflow
    assert "mypy --strict scripts/capture_release_evidence.py" in workflow
    assert (
        "mypy --strict --explicit-package-bases "
        "experiments/prospective_pilot/review_packets.py "
        "tests/test_prospective_review_packets.py" in workflow
    )
    assert (
        "mypy --strict --explicit-package-bases "
        "experiments/prospective_pilot/scheduler.py "
        "experiments/prospective_pilot/proposal_policy.py "
        "experiments/prospective_pilot/target_policies.py "
        "experiments/prospective_pilot/analysis.py "
        "tests/test_prospective_scheduler.py "
        "tests/test_prospective_proposal_policy.py "
        "tests/test_prospective_target_policies.py "
        "tests/test_prospective_analysis.py" in workflow
    )
    assert (
        "mypy --strict --explicit-package-bases "
        "experiments/prospective_pilot/ledger.py "
        "experiments/prospective_pilot/dispatcher.py "
        "experiments/prospective_pilot/release_bundle.py "
        "tests/test_prospective_ledger.py "
        "tests/test_prospective_dispatcher.py "
        "tests/test_prospective_release_bundle.py" in workflow
    )
    assert (
        "mypy --strict --explicit-package-bases "
        "experiments/prospective_pilot/validate_protocol.py" in workflow
    )
    assert (
        "mypy --strict --explicit-package-bases "
        "experiments/prospective_pilot/scientific_ledger.py "
        "tests/test_prospective_scientific_ledger.py" in workflow
    )
    assert "tests/test_capture_release_evidence.py" in workflow
    assert "tests/test_prospective_review_packets.py" in workflow
    assert "tests/test_prospective_proposal_policy.py" in workflow
    assert "tests/test_prospective_release_bundle.py" in workflow
    assert "tests/test_prospective_scientific_ledger.py" in workflow


def test_license_gate_passes_complete_allowed_inventory(tmp_path: Path) -> None:
    inventory = tmp_path / "licenses.json"
    sbom = tmp_path / "sbom.json"
    _write_json(inventory, _inventory())
    _write_json(sbom, _sbom())

    report = AUDITOR.audit_licenses(inventory, sbom, POLICY)

    assert report["automation_result"] == "pass"
    assert report["legal_review_complete"] is False
    assert report["summary"] == {"allow": 2, "deny": 0, "review": 0, "total": 2}
    assert report["sbom_coverage_errors"] == []


def test_human_readable_license_parentheses_are_not_truncated(tmp_path: Path) -> None:
    inventory = tmp_path / "licenses.json"
    sbom = tmp_path / "sbom.json"
    _write_json(
        inventory,
        _inventory(license_name="Mozilla Public License 2.0 (MPL 2.0)"),
    )
    _write_json(sbom, _sbom())

    report = AUDITOR.audit_licenses(inventory, sbom, POLICY)

    assert report["automation_result"] == "pass"
    assert report["packages"][0]["normalized_licenses"] == ["MPL-2.0"]


@pytest.mark.parametrize(
    ("package_name", "license_name", "expected"),
    [
        ("bench-cleanser", "Mystery Research Terms", "review"),
        ("azure-identity", "MIT", "deny"),
        ("docent-python", "MIT", "deny"),
        ("bench-cleanser", "GNU General Public License v3", "deny"),
    ],
)
def test_license_gate_fails_unknown_denied_and_out_of_scope_packages(
    tmp_path: Path,
    package_name: str,
    license_name: str,
    expected: str,
) -> None:
    inventory = tmp_path / "licenses.json"
    sbom = tmp_path / "sbom.json"
    _write_json(inventory, _inventory(package_name=package_name, license_name=license_name))
    _write_json(sbom, _sbom(package_name=package_name))

    report = AUDITOR.audit_licenses(inventory, sbom, POLICY)

    assert report["automation_result"] == "fail"
    assert report["packages"][0]["decision"] == expected


def test_license_gate_fails_missing_license_file_and_sbom_component(tmp_path: Path) -> None:
    inventory_value = _inventory()
    inventory_value[0]["LicenseText"] = ""
    inventory = tmp_path / "licenses.json"
    sbom = tmp_path / "sbom.json"
    _write_json(inventory, inventory_value)
    value = _sbom()
    value["components"] = []
    _write_json(sbom, value)

    report = AUDITOR.audit_licenses(inventory, sbom, POLICY)

    assert report["automation_result"] == "fail"
    assert report["summary"]["review"] == 1
    assert "absent from SBOM" in report["sbom_coverage_errors"][0]


def _wheel(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def _pilot_cohort() -> dict[str, Any]:
    digests = {
        "patch.diff": "c" * 64,
        "report.json": "d" * 64,
        "trajectory.json": "e" * 64,
    }
    return {
        "schema_version": "0.1.0",
        "study_id": "pilot",
        "source": {
            "repository": "SWE-bench/experiments",
            "revision": "a" * 40,
            "submission_id": "submission",
            "submission_checked": False,
            "submission_metadata_url": "https://example.invalid/metadata",
            "selection": "contrastive",
        },
        "candidates": [
            {
                "instance_id": "repo__repo-1",
                "repository": "owner/repo",
                "base_commit": "b" * 40,
                "official_resolved": False,
                "artifacts": {
                    name: {
                        "url": f"https://example.invalid/{name}",
                        "sha256": digest,
                        "bytes": 1,
                    }
                    for name, digest in digests.items()
                },
            }
        ],
    }


def _write_pretty_pilot_cohort(root: Path) -> tuple[Path, str, int]:
    path = root / "artifact-0" / "experiments" / "real_agent_pilot" / "cohort.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(_pilot_cohort(), indent=2) + "\n",
        encoding="utf-8",
    )
    declared = AUDITOR._declared_pilot_provenance_hashes(path)
    revision = next(
        (identity, line)
        for (identity, line), field in declared.items()
        if field == "source.revision"
    )
    return path, revision[0], revision[1]


def _write_hosted_study_source(root: Path) -> Path:
    path = root / "experiments" / "hosted_outcome_study" / "run_study.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    revision = "a1b2c3d4" * 5
    dataset_revision = "d1e2f3a4" * 5
    mirror_revision = "e1f2a3b4" * 5
    path.write_text(
        "\n".join(
            [
                'SUBMISSION_ID = "20250805-openhands-Qwen"',
                'SUBMISSION_METADATA_URL = ("https://raw.githubusercontent.com/"',
                '    "SWE-bench/experiments/"',
                f'    "{revision}/evaluation/verified/"',
                '    "20250805_openhands-Qwen/metadata.yml")',
                'SUBMISSION_METADATA_SHA256 = ("' + "b" * 64 + '")',
                'SUBMISSION_RESULTS_URL = ("https://raw.githubusercontent.com/"',
                '    "SWE-bench/experiments/"',
                f'    "{revision}/evaluation/verified/"',
                '    "20250805_openhands-Qwen/results/results.json")',
                'SUBMISSION_RESULTS_SHA256 = ("' + "c" * 64 + '")',
                'CANONICAL_DATASET_ID = "princeton-nlp/SWE-bench_Verified"',
                f'CANONICAL_DATASET_REVISION = "{dataset_revision}"',
                "CANONICAL_DATASET_AUTHORITATIVE_URL = (",
                '    "https://huggingface.co/datasets/princeton-nlp/"',
                '    "SWE-bench_Verified/resolve/"',
                '    f"{CANONICAL_DATASET_REVISION}/data/test-00000-of-00001.parquet"',
                ")",
                f'CANONICAL_DATASET_MIRROR_REVISION = "{mirror_revision}"',
                "CANONICAL_DATASET_RETRIEVAL_URL = (",
                '    "https://raw.githubusercontent.com/justin-napolitano/"',
                '    "SWE-bench_Verified/"',
                '    f"{CANONICAL_DATASET_MIRROR_REVISION}/"',
                '    "data/test-00000-of-00001.parquet"',
                ")",
                'CANONICAL_DATASET_SHA256 = "' + "d" * 64 + '"',
                'CANONICAL_DATASET_PROJECTION_SHA256 = "' + "e" * 64 + '"',
                'CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT = "' + "f" * 40 + '"',
                "PINNED_SUBMISSION_SOURCES = {",
                '    "metadata.yml": (SUBMISSION_METADATA_URL, SUBMISSION_METADATA_SHA256),',
                '    "results.json": (SUBMISSION_RESULTS_URL, SUBMISSION_RESULTS_SHA256),',
                "}",
                "EXPECTED_DUPLICATE = {",
                '    "base_commit": CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT,',
                '    "instance_ids": ["django__django-15268", "django__django-15278"],',
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _mock_detect_secrets(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
) -> None:
    monkeypatch.setattr(AUDITOR.importlib.metadata, "version", lambda _name: "1.5.0")
    completed = AUDITOR.subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=stdout,
        stderr="",
    )
    monkeypatch.setattr(
        AUDITOR.subprocess,
        "run",
        lambda *_args, **_kwargs: completed,
    )


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "C:/windows", "./relative", "a//b", "a/./b", "a\\b"],
)
def test_archive_member_names_fail_closed(name: str) -> None:
    assert AUDITOR._safe_member_name(name) is None


def test_artifact_gate_accepts_clean_archive_without_external_scanner(tmp_path: Path) -> None:
    wheel = tmp_path / "clean.whl"
    _wheel(
        wheel,
        {
            "clean/__init__.py": b"VALUE = 1\n",
            "clean-0.1.dist-info/METADATA": (
                b"Name: clean\nVersion: 0.1\nRequires-Dist: pydantic>=2\n"
            ),
        },
    )

    report = AUDITOR.audit_artifacts([wheel], POLICY, run_detect_secrets=False)

    assert report["automation_result"] == "pass"
    assert report["custom_findings"] == []
    assert report["detect_secrets"]["version"] == "not-run"


def test_only_typed_real_agent_provenance_hashes_are_narrowly_allowlisted(
    tmp_path: Path,
) -> None:
    cohort_path = tmp_path / "experiments" / "real_agent_pilot" / "cohort.json"
    cohort_path.parent.mkdir(parents=True)
    revision = "a" * 40
    base_commit = "b" * 40
    digests = {
        "patch.diff": "c" * 64,
        "report.json": "d" * 64,
        "trajectory.json": "e" * 64,
    }
    cohort = _pilot_cohort()
    cohort_path.write_text(
        json.dumps(cohort, indent=2) + "\n",
        encoding="utf-8",
    )

    allowed = AUDITOR._declared_pilot_provenance_hashes(cohort_path)

    expected_values = {revision, base_commit, *digests.values()}
    assert {identity for identity, _line in allowed} == {
        hashlib.sha1(value.encode("utf-8")).hexdigest() for value in expected_values
    }
    assert set(allowed.values()) == {
        "source.revision",
        "candidates[0].base_commit",
        "candidates[0].artifacts['patch.diff'].sha256",
        "candidates[0].artifacts['report.json'].sha256",
        "candidates[0].artifacts['trajectory.json'].sha256",
    }

    malformed = json.loads(cohort_path.read_text(encoding="utf-8"))
    malformed["source"]["unexpected"] = "f" * 64
    _write_json(cohort_path, malformed)
    assert AUDITOR._declared_pilot_provenance_hashes(cohort_path) == {}

    _write_json(cohort_path, cohort)
    assert AUDITOR._declared_pilot_provenance_hashes(cohort_path) == {}


def test_only_typed_hosted_study_source_hashes_are_narrowly_allowlisted(
    tmp_path: Path,
) -> None:
    path = _write_hosted_study_source(tmp_path)

    allowed = AUDITOR._declared_hosted_study_provenance_hashes(path)

    expected_values = {
        "b" * 64,
        "c" * 64,
        "d1e2f3a4" * 5,
        "e1f2a3b4" * 5,
        "d" * 64,
        "e" * 64,
        "f" * 40,
    }
    assert {identity for identity, _line in allowed} == {
        hashlib.sha1(value.encode("utf-8")).hexdigest() for value in expected_values
    }
    assert set(allowed.values()) == {
        "SUBMISSION_METADATA_SHA256",
        "SUBMISSION_RESULTS_SHA256",
        "CANONICAL_DATASET_REVISION",
        "CANONICAL_DATASET_MIRROR_REVISION",
        "CANONICAL_DATASET_SHA256",
        "CANONICAL_DATASET_PROJECTION_SHA256",
        "CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT",
    }

    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("raw.githubusercontent.com", "example.invalid"),
        encoding="utf-8",
    )
    assert AUDITOR._declared_hosted_study_provenance_hashes(path) == {}


def test_only_typed_matched_study_source_hashes_are_narrowly_allowlisted(
    tmp_path: Path,
) -> None:
    source = Path(__file__).parents[1] / "experiments" / "matched_rollout_study" / "run_study.py"
    path = tmp_path / "experiments" / "matched_rollout_study" / "run_study.py"
    path.parent.mkdir(parents=True)
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    allowed = AUDITOR._declared_matched_study_provenance_hashes(path)

    assert set(allowed.values()) == {
        "SOURCE_REVISION",
        "SUBMISSIONS[gpt5].metadata_sha256",
        "SUBMISSIONS[gpt5].results_sha256",
        "SUBMISSIONS[kimi_k2].metadata_sha256",
        "SUBMISSIONS[kimi_k2].results_sha256",
        "SUBMISSIONS[claude_4_sonnet].metadata_sha256",
        "SUBMISSIONS[claude_4_sonnet].results_sha256",
        "CANONICAL_DATASET_REVISION",
        "CANONICAL_DATASET_MIRROR_REVISION",
        "CANONICAL_DATASET_SHA256",
        "CANONICAL_DATASET_PROJECTION_SHA256",
        "CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT",
    }
    assert len(allowed) == 12

    text = path.read_text(encoding="utf-8")
    tampered, replacement_count = re.subn(
        r'(metadata_sha256=\(\s*\n\s*")[0-9a-f]{64}',
        r"\1not-a-digest",
        text,
        count=1,
    )
    assert replacement_count == 1
    path.write_text(
        tampered,
        encoding="utf-8",
    )
    assert AUDITOR._declared_matched_study_provenance_hashes(path) == {}

    path.write_text(
        text.replace("raw.githubusercontent.com", "example.invalid"),
        encoding="utf-8",
    )
    assert AUDITOR._declared_matched_study_provenance_hashes(path) == {}


def test_only_schema_bound_literature_api_hashes_are_narrowly_allowlisted(
    tmp_path: Path,
) -> None:
    source_path = Path(__file__).parents[1] / "docs" / "literature.lock.json"
    lock = json.loads(source_path.read_text(encoding="utf-8"))
    path = tmp_path / "docs" / "literature.lock.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    allowed = AUDITOR._declared_literature_lock_hashes(path)

    expected_fields = {
        "source.versioned_ids_sha256",
        "source.responses[0].raw_atom_sha256",
    }
    assert set(allowed.values()) == expected_fields
    expected_values = {
        lock["source"]["versioned_ids_sha256"],
        lock["source"]["responses"][0]["raw_atom_sha256"],
    }
    assert {identity for identity, _line in allowed} == {
        hashlib.sha1(value.encode("utf-8")).hexdigest() for value in expected_values
    }

    malformed = json.loads(path.read_text(encoding="utf-8"))
    malformed["entries"][0]["version"] += 1
    path.write_text(
        json.dumps(malformed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert AUDITOR._declared_literature_lock_hashes(path) == {}

    malformed = lock
    malformed["source"]["responses"][0]["request_url"] = (
        "https://example.invalid/api/query?id_list=1003.3967v5&start=0&max_results=1"
    )
    path.write_text(
        json.dumps(malformed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert AUDITOR._declared_literature_lock_hashes(path) == {}

    path = _write_hosted_study_source(tmp_path)
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            "(SUBMISSION_RESULTS_URL, SUBMISSION_RESULTS_SHA256)",
            "(SUBMISSION_METADATA_URL, SUBMISSION_RESULTS_SHA256)",
        ),
        encoding="utf-8",
    )
    assert AUDITOR._declared_hosted_study_provenance_hashes(path) == {}


def test_execution_smoke_and_prospective_hashes_are_schema_and_chain_bound(
    tmp_path: Path,
) -> None:
    relatives = (
        Path("experiments/independent_execution_smoke/evidence-manifest.json"),
        Path("experiments/independent_execution_smoke/run_smoke.py"),
        Path("experiments/independent_execution_smoke/README.md"),
        Path("experiments/independent_execution_smoke/RESULTS.md"),
        Path("experiments/sphinx_execution_smoke/evidence-manifest.json"),
        Path("experiments/sphinx_execution_smoke/verify_evidence.py"),
        Path("experiments/prospective_pilot/prehistory.json"),
        Path("experiments/prospective_pilot/preregistration.json"),
        Path("experiments/prospective_pilot/validate_protocol.py"),
        Path("experiments/prospective_pilot/adjudication_plan.json"),
        Path("experiments/prospective_pilot/analysis.py"),
        Path("experiments/prospective_pilot/analysis_plan.json"),
        Path("experiments/prospective_pilot/collection_policy.json"),
        Path("experiments/prospective_pilot/execution_freeze.json"),
        Path("experiments/prospective_pilot/frame_manifest.json"),
        Path("experiments/prospective_pilot/resource_ceiling.json"),
        Path("experiments/prospective_pilot/review_packets.py"),
        Path("experiments/prospective_pilot/proposal_policy.py"),
        Path("experiments/prospective_pilot/release_bundle.py"),
        Path("experiments/prospective_pilot/scheduler_contract.json"),
        Path("experiments/prospective_pilot/scheduler.py"),
        Path("experiments/prospective_pilot/ledger.py"),
        Path("experiments/prospective_pilot/scientific_ledger.py"),
        Path("experiments/prospective_pilot/dispatcher.py"),
        Path("experiments/prospective_pilot/target_policies.py"),
        Path("experiments/prospective_pilot/target_policy_manifest.json"),
        Path("bench_cleanser/verification/orchestrate.py"),
        Path("bench_cleanser/verification/policy_log.py"),
        Path("bench_cleanser/verification/router.py"),
        Path("bench_cleanser/verification/corpus.py"),
        Path("bench_cleanser/verification/evaluate.py"),
        Path("bench_cleanser/verification/metrics.py"),
    )
    for relative in relatives:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())

    manifest_path = tmp_path / relatives[0]
    source_path = tmp_path / relatives[1]
    prehistory_path = tmp_path / Path("experiments/prospective_pilot/prehistory.json")
    protocol_path = tmp_path / Path("experiments/prospective_pilot/preregistration.json")
    validator_path = tmp_path / Path("experiments/prospective_pilot/validate_protocol.py")
    collection_path = tmp_path / Path("experiments/prospective_pilot/collection_policy.json")
    frame_path = tmp_path / Path("experiments/prospective_pilot/frame_manifest.json")
    scheduler_contract_path = tmp_path / Path(
        "experiments/prospective_pilot/scheduler_contract.json"
    )
    scheduler_path = tmp_path / Path("experiments/prospective_pilot/scheduler.py")
    proposal_path = tmp_path / Path("experiments/prospective_pilot/proposal_policy.py")
    release_bundle_path = tmp_path / Path("experiments/prospective_pilot/release_bundle.py")
    ledger_path = tmp_path / Path("experiments/prospective_pilot/ledger.py")
    scientific_ledger_path = tmp_path / Path("experiments/prospective_pilot/scientific_ledger.py")
    dispatcher_path = tmp_path / Path("experiments/prospective_pilot/dispatcher.py")
    orchestrator_path = tmp_path / Path("bench_cleanser/verification/orchestrate.py")
    policy_log_path = tmp_path / Path("bench_cleanser/verification/policy_log.py")
    router_path = tmp_path / Path("bench_cleanser/verification/router.py")
    corpus_path = tmp_path / Path("bench_cleanser/verification/corpus.py")
    evaluation_path = tmp_path / Path("bench_cleanser/verification/evaluate.py")
    metrics_path = tmp_path / Path("bench_cleanser/verification/metrics.py")
    assert len(AUDITOR._declared_independent_smoke_manifest_hashes(manifest_path)) == 107
    assert len(AUDITOR._declared_independent_smoke_source_hashes(source_path)) == 30
    prehistory_fields = set(
        AUDITOR._declared_prospective_prehistory_hashes(prehistory_path).values()
    )
    assert {
        "events[0].evidence_record.sha256",
        "events[0].prior_chain_head_sha256",
        "events[0].event_sha256",
        "events[0].chain_head_sha256",
        "events[1].evidence_record.sha256",
        "events[1].prior_chain_head_sha256",
        "events[1].event_sha256",
        "events[1].chain_head_sha256",
        "chain_head_sha256",
    }.issubset(prehistory_fields)
    assert {
        "declared_unverified:events[0].draft_artifacts[0].sha256",
        "declared_unverified:events[0].evidence_record.external_bundle_sha256",
        "declared_unverified:events[1].evidence_record.external_bundle_runner.sha256",
    }.issubset(prehistory_fields)
    protocol_fields = set(AUDITOR._declared_prospective_protocol_hashes(protocol_path).values())
    assert {
        "prehistory.sha256",
        "prehistory.chain_head_sha256",
        *(f"activation_configuration.objects[{index}].sha256" for index in range(7)),
    }.issubset(protocol_fields)
    assert {
        "declared_unverified:frozen_inputs.acquisition_manifest_sha256",
        "declared_unverified:frozen_inputs.cohort_identity_sha256",
        "declared_unverified:frozen_inputs.selected_task_identities_sha256",
        "declared_unverified:frozen_inputs.matched_study_code_sha256",
    }.issubset(protocol_fields)
    collection_fields = set(
        AUDITOR._declared_prospective_collection_policy_hashes(collection_path).values()
    )
    assert {
        "preferred_action_rule.router.policy_config_sha256",
        "preferred_action_rule.router.sha256",
        "preferred_action_rule.proposal_policy.config_sha256",
        "preferred_action_rule.proposal_policy.sha256",
        "implementation_bindings.frame_manifest.sha256",
        "implementation_bindings.policy_log.sha256",
        "implementation_bindings.proposal_policy.sha256",
        "implementation_bindings.task_scheduler.sha256",
    }.issubset(collection_fields)
    assert {
        "declared_unverified:rng.action_draws.seed_sha256",
        "declared_unverified:rng.candidate_order.seed_sha256",
        "declared_unverified:rng.task_order.seed_sha256",
    }.issubset(collection_fields)
    frame_fields = set(AUDITOR._declared_prospective_frame_hashes(frame_path).values())
    assert {
        "task_ids_sha256",
        "candidate_ids_sha256",
        "tasks_sha256",
    }.issubset(frame_fields)
    assert {
        "declared_unverified:source_feature_freeze.sha256",
        "declared_unverified:source_feature_freeze.selected_instance_ids_sha256",
        "declared_unverified:source_feature_freeze.selected_task_identities_sha256",
    }.issubset(frame_fields)
    assert set(
        AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path).values()
    ) == {
        "frame_manifest.sha256",
        "implementation.scheduler.sha256",
        "implementation.proposal_policy.config_sha256",
        "implementation.proposal_policy.sha256",
        "implementation.ledger.sha256",
        "implementation.scientific_ledger.sha256",
        "implementation.corpus_contract.sha256",
        "implementation.evaluation_contract.sha256",
        "implementation.metrics_source.sha256",
        "implementation.dispatcher.sha256",
        "implementation.structural_release_bundle_compiler.sha256",
        "implementation.completed_acquisition_validator.sha256",
    }
    scheduler_source_fields = set(
        AUDITOR._declared_prospective_scheduler_source_hashes(scheduler_path).values()
    )
    assert "ROUTER_SOURCE_SHA256" in scheduler_source_fields
    assert len(scheduler_source_fields) == 7
    assert all(
        field == "ROUTER_SOURCE_SHA256"
        or field.startswith("declared_unverified:source_constant_line_")
        for field in scheduler_source_fields
    )
    review_source_path = tmp_path / "experiments/prospective_pilot/review_packets.py"
    review_source_fields = set(
        AUDITOR._declared_prospective_review_packet_source_hashes(review_source_path).values()
    )
    assert len(review_source_fields) == 3
    assert all(
        field.startswith("declared_unverified:source_constant_line_")
        for field in review_source_fields
    )
    validator_source_fields = set(
        AUDITOR._declared_prospective_validator_source_hashes(validator_path).values()
    )
    assert len(validator_source_fields) == 1
    assert all(
        field.startswith("declared_unverified:validator_constant_line_")
        for field in validator_source_fields
    )
    analysis_path = tmp_path / "experiments/prospective_pilot/analysis_plan.json"
    assert set(AUDITOR._declared_prospective_analysis_plan_hashes(analysis_path).values()) == {
        "declared_unverified:uncertainty.sensitivity.bootstrap_seed_sha256",
        "available_bindings.analysis_implementation.sha256",
        "available_bindings.target_policy_implementation_manifest.sha256",
    }
    adjudication_path = tmp_path / "experiments/prospective_pilot/adjudication_plan.json"
    assert set(
        AUDITOR._declared_prospective_adjudication_plan_hashes(adjudication_path).values()
    ) == {
        "available_bindings.frame_manifest.sha256",
        "available_bindings.packet_generator.sha256",
    }
    execution_path = tmp_path / "experiments/prospective_pilot/execution_freeze.json"
    assert set(AUDITOR._declared_prospective_execution_freeze_hashes(execution_path).values()) == {
        "declared_unverified:canonical_dataset.parquet_sha256",
        "declared_unverified:canonical_dataset.revision",
        "declared_unverified:harness.commit",
        "declared_unverified:harness.tree",
    }
    target_policy_path = tmp_path / "experiments/prospective_pilot/target_policy_manifest.json"
    assert set(
        AUDITOR._declared_prospective_target_policy_manifest_hashes(target_policy_path).values()
    ) == {"implementation.sha256"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["task"]["api_key"] = "1a2b3c4d" * 8
    _write_json(manifest_path, manifest)
    assert AUDITOR._declared_independent_smoke_manifest_hashes(manifest_path) == {}
    assert AUDITOR._declared_independent_smoke_source_hashes(source_path) == {}

    manifest_path.write_bytes((ROOT / relatives[0]).read_bytes())
    source_path.write_text(
        source_path.read_text(encoding="utf-8")
        + '\nUNDECLARED_SECRET = "1a2b3c4d'
        + "5e6f7a8b" * 7
        + '"\n',
        encoding="utf-8",
    )
    assert AUDITOR._declared_independent_smoke_source_hashes(source_path) == {}

    source_path.write_bytes((ROOT / relatives[1]).read_bytes())
    source_path.write_bytes(b"\n" + source_path.read_bytes())
    assert AUDITOR._declared_independent_smoke_manifest_hashes(manifest_path) == {}
    assert AUDITOR._declared_independent_smoke_source_hashes(source_path) == {}

    source_path.write_bytes((ROOT / relatives[1]).read_bytes())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["task"]["base_commit"] = "1a2b3c4d" * 5
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    assert AUDITOR._declared_independent_smoke_manifest_hashes(manifest_path) == {}

    manifest_path.write_bytes((ROOT / relatives[0]).read_bytes())
    wrong_path = manifest_path.with_name("evidence_manifest.json")
    wrong_path.write_bytes(manifest_path.read_bytes())
    assert AUDITOR._declared_independent_smoke_manifest_hashes(wrong_path) == {}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "independent-execution-smoke-0.1.1"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert AUDITOR._declared_independent_smoke_manifest_hashes(manifest_path) == {}

    manifest_path.write_bytes((ROOT / relatives[0]).read_bytes())
    prehistory = json.loads(prehistory_path.read_text(encoding="utf-8"))
    prehistory["events"][0]["knowledge_boundary"]["hosted_labels_accessible_before_execution"] = (
        False
    )
    _write_json(prehistory_path, prehistory)
    assert AUDITOR._declared_prospective_prehistory_hashes(prehistory_path) == {}
    assert AUDITOR._declared_prospective_protocol_hashes(protocol_path) == {}

    prehistory_path.write_bytes(
        (ROOT / "experiments/prospective_pilot/prehistory.json").read_bytes()
    )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["claim_scope"]["hypotheses_supported"] = ["H1"]
    _write_json(protocol_path, protocol)
    assert AUDITOR._declared_prospective_protocol_hashes(protocol_path) == {}

    protocol_path.write_bytes(
        (ROOT / "experiments/prospective_pilot/preregistration.json").read_bytes()
    )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["activation_readiness"]["missing"].remove(
        "signed deterministic bootstrap receipt acquisition"
    )
    _write_json(protocol_path, protocol)
    assert AUDITOR._declared_prospective_protocol_hashes(protocol_path) == {}

    protocol_path.write_bytes(
        (ROOT / "experiments/prospective_pilot/preregistration.json").read_bytes()
    )
    validator_path.write_bytes(b"\n" + validator_path.read_bytes())
    assert AUDITOR._declared_prospective_prehistory_hashes(prehistory_path) == {}
    assert AUDITOR._declared_prospective_protocol_hashes(protocol_path) == {}

    validator_path.write_bytes(
        (ROOT / "experiments/prospective_pilot/validate_protocol.py").read_bytes()
    )
    original_router = router_path.read_bytes()
    router_path.write_bytes(original_router + b"\n")
    assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}
    assert AUDITOR._declared_prospective_scheduler_source_hashes(scheduler_path) == {}

    router_path.write_bytes(original_router)
    original_proposal = proposal_path.read_bytes()
    proposal_path.write_bytes(original_proposal + b"\n")
    assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}
    assert AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path) == {}

    proposal_path.write_bytes(original_proposal)
    original_policy_log = policy_log_path.read_bytes()
    policy_log_path.write_bytes(original_policy_log + b"\n")
    assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}

    policy_log_path.write_bytes(original_policy_log)
    original_release_bundle = release_bundle_path.read_bytes()
    release_bundle_path.write_bytes(original_release_bundle + b"\n")
    assert AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path) == {}

    release_bundle_path.write_bytes(original_release_bundle)
    activation_path = tmp_path / "experiments/prospective_pilot/analysis_plan.json"
    original_activation = activation_path.read_bytes()
    activation_path.write_bytes(original_activation + b"\n")
    assert AUDITOR._declared_prospective_protocol_hashes(protocol_path) == {}

    activation_path.write_bytes(original_activation)
    original_scheduler = scheduler_path.read_bytes()
    scheduler_path.write_bytes(original_scheduler + b"\n")
    assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}
    assert AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path) == {}
    assert AUDITOR._declared_prospective_scheduler_source_hashes(scheduler_path) == {}

    scheduler_path.write_bytes(original_scheduler)
    original_scheduler_contract = scheduler_contract_path.read_bytes()
    scheduler_contract = json.loads(original_scheduler_contract)
    scheduler_contract["policy_log_crosswalk"]["bootstrap_history"] = "unsigned_bootstrap_receipt"
    _write_json(scheduler_contract_path, scheduler_contract)
    assert AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path) == {}

    scheduler_contract_path.write_bytes(original_scheduler_contract)
    scheduler_contract = json.loads(original_scheduler_contract)
    scheduler_contract["operational_requirements"]["trusted_study_bundle_compiler"]["blocking"] = (
        False
    )
    _write_json(scheduler_contract_path, scheduler_contract)
    assert AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path) == {}

    scheduler_contract_path.write_bytes(original_scheduler_contract)
    for dependency_path in (
        ledger_path,
        scientific_ledger_path,
        dispatcher_path,
        orchestrator_path,
        corpus_path,
        evaluation_path,
        metrics_path,
    ):
        original_dependency = dependency_path.read_bytes()
        dependency_path.write_bytes(original_dependency + b"\n")
        assert (
            AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path) == {}
        )
        dependency_path.write_bytes(original_dependency)

    assert (
        len(AUDITOR._declared_prospective_scheduler_contract_hashes(scheduler_contract_path)) == 12
    )


def test_prospective_semantic_guards_survive_exact_record_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relatives = (
        "bench_cleanser/verification/orchestrate.py",
        "bench_cleanser/verification/policy_log.py",
        "bench_cleanser/verification/router.py",
        "bench_cleanser/verification/corpus.py",
        "bench_cleanser/verification/evaluate.py",
        "bench_cleanser/verification/metrics.py",
        "experiments/prospective_pilot/collection_policy.json",
        "experiments/prospective_pilot/dispatcher.py",
        "experiments/prospective_pilot/frame_manifest.json",
        "experiments/prospective_pilot/ledger.py",
        "experiments/prospective_pilot/scientific_ledger.py",
        "experiments/prospective_pilot/proposal_policy.py",
        "experiments/prospective_pilot/release_bundle.py",
        "experiments/prospective_pilot/scheduler.py",
        "experiments/prospective_pilot/scheduler_contract.json",
    )
    for relative in relatives:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())

    collection_path = tmp_path / "experiments/prospective_pilot/collection_policy.json"
    contract_path = tmp_path / "experiments/prospective_pilot/scheduler_contract.json"
    policy_log_path = tmp_path / "bench_cleanser/verification/policy_log.py"
    proposal_path = tmp_path / "experiments/prospective_pilot/proposal_policy.py"
    release_path = tmp_path / "experiments/prospective_pilot/release_bundle.py"
    scientific_ledger_path = tmp_path / "experiments/prospective_pilot/scientific_ledger.py"
    original_collection = collection_path.read_bytes()
    original_contract = contract_path.read_bytes()
    original_policy_log = policy_log_path.read_bytes()
    original_proposal = proposal_path.read_bytes()
    original_release = release_path.read_bytes()
    original_scientific_ledger = scientific_ledger_path.read_bytes()

    collection = json.loads(original_collection)
    collection["terminal_admissibility"]["error_unavailable_inconclusive_or_disagreement"] = (
        "enables_reject"
    )
    _write_json(collection_path, collection)
    with monkeypatch.context() as scoped:
        _rebind_exact_record(
            scoped,
            prefix="_PROSPECTIVE_COLLECTION_POLICY",
            path=collection_path,
        )
        assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}
    collection_path.write_bytes(original_collection)

    tampered_proposal = original_proposal.replace(
        b'PROPOSAL_POLICY_VERSION = "verification-gap-proposal-v1"',
        b'PROPOSAL_POLICY_VERSION = "verification-gap-proposal-v2"',
    )
    assert tampered_proposal != original_proposal
    proposal_path.write_bytes(tampered_proposal)
    collection = json.loads(original_collection)
    proposal_digest = hashlib.sha256(tampered_proposal).hexdigest()
    collection["preferred_action_rule"]["proposal_policy"]["sha256"] = proposal_digest
    collection["implementation_bindings"]["proposal_policy"]["sha256"] = proposal_digest
    _write_json(collection_path, collection)
    with monkeypatch.context() as scoped:
        _rebind_exact_record(
            scoped,
            prefix="_PROSPECTIVE_COLLECTION_POLICY",
            path=collection_path,
        )
        assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}
    proposal_path.write_bytes(original_proposal)
    collection_path.write_bytes(original_collection)

    tampered_policy_log = original_policy_log.replace(
        b"class BootstrapHistoryStep:",
        b"class UnsignedBootstrapStep:",
    )
    assert tampered_policy_log != original_policy_log
    policy_log_path.write_bytes(tampered_policy_log)
    collection = json.loads(original_collection)
    collection["implementation_bindings"]["policy_log"]["sha256"] = hashlib.sha256(
        tampered_policy_log
    ).hexdigest()
    _write_json(collection_path, collection)
    with monkeypatch.context() as scoped:
        _rebind_exact_record(
            scoped,
            prefix="_PROSPECTIVE_COLLECTION_POLICY",
            path=collection_path,
        )
        assert AUDITOR._declared_prospective_collection_policy_hashes(collection_path) == {}
    policy_log_path.write_bytes(original_policy_log)
    collection_path.write_bytes(original_collection)

    contract = json.loads(original_contract)
    contract["policy_log_crosswalk"]["bootstrap_history"] = "counted_as_policy_history"
    contract["operational_requirements"]["trusted_study_bundle_compiler"]["blocking"] = False
    _write_json(contract_path, contract)
    with monkeypatch.context() as scoped:
        _rebind_exact_record(
            scoped,
            prefix="_PROSPECTIVE_SCHEDULER_CONTRACT",
            path=contract_path,
        )
        assert AUDITOR._declared_prospective_scheduler_contract_hashes(contract_path) == {}
    contract_path.write_bytes(original_contract)

    for field_name, invalid_value in (
        ("logical_path", "experiments/prospective_pilot/ledger.py"),
        ("profile", "TRUSTED_SCIENTIFIC_LEDGER"),
        ("schema_version", "prospective-pilot-scientific-ledger-0.3.0"),
        ("scope", "multi_host_externally_anchored"),
    ):
        contract = json.loads(original_contract)
        contract["implementation"]["scientific_ledger"][field_name] = invalid_value
        _write_json(contract_path, contract)
        with monkeypatch.context() as scoped:
            _rebind_exact_record(
                scoped,
                prefix="_PROSPECTIVE_SCHEDULER_CONTRACT",
                path=contract_path,
            )
            assert AUDITOR._declared_prospective_scheduler_contract_hashes(contract_path) == {}
    contract_path.write_bytes(original_contract)

    for original_symbol, tampered_symbol in (
        (
            b'SCIENTIFIC_LEDGER_SCHEMA_VERSION = "prospective-pilot-scientific-ledger-0.2.0"',
            b'SCIENTIFIC_LEDGER_SCHEMA_VERSION = "prospective-pilot-scientific-ledger-0.3.0"',
        ),
        (b"class ScientificLedger:", b"class UnboundScientificLedger:"),
        (b"def signed_envelope_bytes(", b"def unsigned_envelope_bytes("),
    ):
        tampered_scientific_ledger = original_scientific_ledger.replace(
            original_symbol,
            tampered_symbol,
        )
        assert tampered_scientific_ledger != original_scientific_ledger
        scientific_ledger_path.write_bytes(tampered_scientific_ledger)
        contract = json.loads(original_contract)
        contract["implementation"]["scientific_ledger"]["sha256"] = hashlib.sha256(
            tampered_scientific_ledger
        ).hexdigest()
        _write_json(contract_path, contract)
        with monkeypatch.context() as scoped:
            _rebind_exact_record(
                scoped,
                prefix="_PROSPECTIVE_SCHEDULER_CONTRACT",
                path=contract_path,
            )
            assert AUDITOR._declared_prospective_scheduler_contract_hashes(contract_path) == {}
    scientific_ledger_path.write_bytes(original_scientific_ledger)
    contract_path.write_bytes(original_contract)

    tampered_release = original_release.replace(
        b'TRUST_MODEL = "out_of_band_sha256_v1"',
        b'TRUST_MODEL = "self_asserted_v1"',
    )
    assert tampered_release != original_release
    release_path.write_bytes(tampered_release)
    contract = json.loads(original_contract)
    contract["implementation"]["structural_release_bundle_compiler"]["sha256"] = hashlib.sha256(
        tampered_release
    ).hexdigest()
    _write_json(contract_path, contract)
    with monkeypatch.context() as scoped:
        _rebind_exact_record(
            scoped,
            prefix="_PROSPECTIVE_SCHEDULER_CONTRACT",
            path=contract_path,
        )
        assert AUDITOR._declared_prospective_scheduler_contract_hashes(contract_path) == {}


def test_paired_and_sphinx_evidence_hashes_are_exact_record_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = (
        (
            "experiments/paired_execution_smoke/evidence-manifest.json",
            AUDITOR._declared_paired_smoke_manifest_hashes,
            38,
        ),
        (
            "experiments/paired_execution_smoke/verify_evidence.py",
            AUDITOR._declared_paired_smoke_source_hashes,
            37,
        ),
        (
            "experiments/sphinx_execution_smoke/evidence-manifest.json",
            AUDITOR._declared_sphinx_smoke_manifest_hashes,
            31,
        ),
        (
            "experiments/sphinx_execution_smoke/verify_evidence.py",
            AUDITOR._declared_sphinx_smoke_source_hashes,
            37,
        ),
    )
    scanner_results: dict[str, list[dict[str, Any]]] = {}
    for relative, _classifier, _expected_count in records:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes())
    for relative, classifier, expected_count in records:
        path = tmp_path / relative
        declared = classifier(path)
        assert len(declared) == expected_count
        (identity, line), _field = next(iter(declared.items()))
        scanner_results[relative] = [
            {
                "type": "Hex High Entropy String",
                "line_number": line,
                "hashed_secret": identity,
            }
        ]

    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": scanner_results}),
    )
    _version, findings, declared = AUDITOR._run_detect_secrets(tmp_path)
    assert findings == []
    assert len(declared) == 4

    paired_manifest = tmp_path / records[0][0]
    paired_manifest.write_bytes(b"\n" + paired_manifest.read_bytes())
    assert AUDITOR._declared_paired_smoke_manifest_hashes(paired_manifest) == {}
    assert AUDITOR._declared_paired_smoke_source_hashes(tmp_path / records[1][0]) == {}

    sphinx_source = tmp_path / records[3][0]
    sphinx_source.write_bytes(sphinx_source.read_bytes() + b"\n")
    assert AUDITOR._declared_sphinx_smoke_manifest_hashes(tmp_path / records[2][0]) == {}
    assert AUDITOR._declared_sphinx_smoke_source_hashes(sphinx_source) == {}


def test_prospective_classifiers_label_external_and_seed_hashes_unverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relatives = (
        "bench_cleanser/verification/policy_log.py",
        "bench_cleanser/verification/router.py",
        "bench_cleanser/verification/corpus.py",
        "bench_cleanser/verification/evaluate.py",
        "bench_cleanser/verification/metrics.py",
        "experiments/independent_execution_smoke/evidence-manifest.json",
        "experiments/independent_execution_smoke/run_smoke.py",
        "experiments/sphinx_execution_smoke/evidence-manifest.json",
        "experiments/sphinx_execution_smoke/verify_evidence.py",
        "experiments/prospective_pilot/adjudication_plan.json",
        "experiments/prospective_pilot/analysis.py",
        "experiments/prospective_pilot/analysis_plan.json",
        "experiments/prospective_pilot/collection_policy.json",
        "experiments/prospective_pilot/execution_freeze.json",
        "experiments/prospective_pilot/frame_manifest.json",
        "experiments/prospective_pilot/prehistory.json",
        "experiments/prospective_pilot/preregistration.json",
        "experiments/prospective_pilot/resource_ceiling.json",
        "experiments/prospective_pilot/review_packets.py",
        "experiments/prospective_pilot/proposal_policy.py",
        "experiments/prospective_pilot/release_bundle.py",
        "experiments/prospective_pilot/scheduler.py",
        "experiments/prospective_pilot/scheduler_contract.json",
        "experiments/prospective_pilot/target_policies.py",
        "experiments/prospective_pilot/target_policy_manifest.json",
        "experiments/prospective_pilot/validate_protocol.py",
    )
    for relative in relatives:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())

    cases = (
        (
            "experiments/prospective_pilot/collection_policy.json",
            AUDITOR._declared_prospective_collection_policy_hashes,
            "preferred_action_rule.router.policy_config_sha256",
            "rng.action_draws.seed_sha256",
        ),
        (
            "experiments/prospective_pilot/prehistory.json",
            AUDITOR._declared_prospective_prehistory_hashes,
            "events[0].evidence_record.sha256",
            "events[0].evidence_record.external_bundle_sha256",
        ),
        (
            "experiments/prospective_pilot/preregistration.json",
            AUDITOR._declared_prospective_protocol_hashes,
            "activation_configuration.objects[0].sha256",
            "frozen_inputs.acquisition_manifest_sha256",
        ),
    )
    scanner_results: dict[str, list[dict[str, Any]]] = {}
    expected_fields: set[str] = set()
    for relative, classifier, classified_field, visible_field in cases:
        path = tmp_path / relative
        classified = classifier(path)
        (classified_identity, classified_line), _name = next(
            item for item in classified.items() if item[1] == classified_field
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        visible = next(item for item in AUDITOR._json_hex_fields(value) if item[1] == visible_field)
        visible_rendered = AUDITOR._render_json_provenance_identities(
            path.read_text(encoding="utf-8"),
            [visible],
        )
        (visible_identity, visible_line), _visible_name = next(iter(visible_rendered.items()))
        scanner_results[relative] = [
            {
                "type": "Hex High Entropy String",
                "line_number": classified_line,
                "hashed_secret": classified_identity,
            },
            {
                "type": "Hex High Entropy String",
                "line_number": visible_line,
                "hashed_secret": visible_identity,
            },
        ]
        expected_fields.update(
            {
                classified_field,
                f"declared_unverified:{visible_field}",
            }
        )

    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": scanner_results}),
    )
    _version, findings, declared = AUDITOR._run_detect_secrets(tmp_path)

    assert findings == []
    assert {item["field"] for item in declared} == expected_fields


@pytest.mark.parametrize(
    "relative",
    [
        "experiments/independent_execution_smoke/README.md",
        "experiments/independent_execution_smoke/RESULTS.md",
        "experiments/prospective_pilot/validate_protocol.py",
        "docs/EVIDENCE_AVAILABILITY.md",
    ],
)
def test_new_evidence_docs_and_validator_receive_no_hash_waiver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    raw_value = "1a2b3c4d" * 8
    path.write_text(f"untrusted = {raw_value}\n", encoding="utf-8")
    finding = {
        "type": "Hex High Entropy String",
        "line_number": 1,
        "hashed_secret": hashlib.sha1(raw_value.encode("utf-8")).hexdigest(),
    }
    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": {relative: [finding]}}),
    )

    _version, findings, declared = AUDITOR._run_detect_secrets(tmp_path)

    assert findings == [
        {
            "line": 1,
            "path": relative,
            "rule": "Hex High Entropy String",
        }
    ]
    assert declared == []


def test_literature_claim_pdf_hashes_are_exact_record_and_validator_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relatives = (
        Path("docs/literature.claims.json"),
        Path("docs/literature.lock.json"),
        Path("scripts/verify_claim_ledger.py"),
    )
    for relative in relatives:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    ledger_path = tmp_path / relatives[0]
    validator_path = tmp_path / relatives[2]

    allowed = AUDITOR._declared_literature_claim_hashes(ledger_path)

    assert len(allowed) == 26
    assert set(allowed.values()) == {f"entries[{index}].pdf_sha256" for index in range(26)}
    (identity, line), field = next(iter(allowed.items()))
    finding = {
        "type": "Hex High Entropy String",
        "line_number": line,
        "hashed_secret": identity,
    }
    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": {relatives[0].as_posix(): [finding]}}),
    )
    _version, findings, declared = AUDITOR._run_detect_secrets(tmp_path)
    assert findings == []
    assert declared == [
        {
            "field": field,
            "line": line,
            "path": relatives[0].as_posix(),
            "rule": "Hex High Entropy String",
        }
    ]

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["entries"][0]["pdf_sha256"] = "1a2b3c4d" * 8
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    assert AUDITOR._declared_literature_claim_hashes(ledger_path) == {}

    ledger_path.write_bytes((ROOT / relatives[0]).read_bytes())
    ledger_path.write_bytes(b"\n" + ledger_path.read_bytes())
    assert AUDITOR._declared_literature_claim_hashes(ledger_path) == {}

    ledger_path.write_bytes((ROOT / relatives[0]).read_bytes())
    validator_path.write_bytes(validator_path.read_bytes() + b"\n")
    assert AUDITOR._declared_literature_claim_hashes(ledger_path) == {}

    wrong_path = ledger_path.with_name("literature-claims.json")
    wrong_path.write_bytes((ROOT / relatives[0]).read_bytes())
    assert AUDITOR._declared_literature_claim_hashes(wrong_path) == {}

    validator_path.write_bytes((ROOT / relatives[2]).read_bytes())
    wrong_line = {**finding, "line_number": line + 1}
    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": {relatives[0].as_posix(): [wrong_line]}}),
    )
    _version, findings, declared = AUDITOR._run_detect_secrets(tmp_path)
    assert findings == [
        {
            "line": line + 1,
            "path": relatives[0].as_posix(),
            "rule": "Hex High Entropy String",
        }
    ]
    assert declared == []


@pytest.mark.parametrize(
    ("field", "malformed_value"),
    [
        ("submission_checked", 0),
        ("official_resolved", 0),
        ("bytes", True),
    ],
)
def test_provenance_waiver_rejects_malformed_typed_schema(
    tmp_path: Path,
    field: str,
    malformed_value: object,
) -> None:
    cohort = _pilot_cohort()
    if field == "submission_checked":
        cohort["source"][field] = malformed_value
    elif field == "official_resolved":
        cohort["candidates"][0][field] = malformed_value
    else:
        cohort["candidates"][0]["artifacts"]["patch.diff"][field] = malformed_value
    path = tmp_path / "experiments" / "real_agent_pilot" / "cohort.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(cohort, indent=2) + "\n", encoding="utf-8")

    assert AUDITOR._declared_pilot_provenance_hashes(path) == {}


def test_detect_secrets_waiver_is_exact_and_malformed_output_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, revision_identity, revision_line = _write_pretty_pilot_cohort(tmp_path)
    relative_path = path.relative_to(tmp_path).as_posix()
    finding = {
        "type": "Hex High Entropy String",
        "line_number": revision_line,
        "hashed_secret": revision_identity,
    }
    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": {relative_path: [finding]}}),
    )

    version, findings, declared = AUDITOR._run_detect_secrets(tmp_path)

    assert version == "1.5.0"
    assert findings == []
    assert declared == [
        {
            "field": "source.revision",
            "line": revision_line,
            "path": relative_path,
            "rule": "Hex High Entropy String",
        }
    ]

    unsafe_path = f"../{relative_path}"
    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": {unsafe_path: [finding]}}),
    )
    with pytest.raises(AUDITOR.AuditInputError, match="result path is unsafe"):
        AUDITOR._run_detect_secrets(tmp_path)

    boolean_line = {**finding, "line_number": True}
    _mock_detect_secrets(
        monkeypatch,
        json.dumps({"results": {relative_path: [boolean_line]}}),
    )
    with pytest.raises(AUDITOR.AuditInputError, match="fields are malformed"):
        AUDITOR._run_detect_secrets(tmp_path)

    duplicate_results = (
        '{"results": {'
        + json.dumps(relative_path)
        + ": [], "
        + json.dumps(relative_path)
        + ": ["
        + json.dumps(finding)
        + "]}}"
    )
    _mock_detect_secrets(monkeypatch, duplicate_results)
    with pytest.raises(AUDITOR.AuditInputError, match="emitted invalid JSON"):
        AUDITOR._run_detect_secrets(tmp_path)


def test_artifact_gate_finds_secret_retired_import_dependency_and_escape(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "bad.whl"
    retired_import = ("from " + "azure.identity import DefaultAzureCredential\n").encode()
    credential = b"TOKEN = '" + b"sk-" + (b"A" * 30) + b"'\n"
    excluded_dependency = ("Requires-Dist: " + "docent-python>=0.1\n").encode()
    _wheel(
        wheel,
        {
            "../escape.py": b"pass\n",
            "bad/provider.py": retired_import,
            "bad/token.py": credential,
            "bad-0.1.dist-info/METADATA": excluded_dependency,
        },
    )

    report = AUDITOR.audit_artifacts([wheel], POLICY, run_detect_secrets=False)

    assert report["automation_result"] == "fail"
    kinds = {finding["kind"] for finding in report["custom_findings"]}
    assert kinds == {
        "credential",
        "forbidden-dependency",
        "proprietary-import",
        "unsafe-archive-path",
    }
    serialized = json.dumps(report)
    assert ("sk-" + "A" * 30) not in serialized


def test_cli_writes_machine_readable_failure_report(tmp_path: Path) -> None:
    inventory = tmp_path / "licenses.json"
    sbom = tmp_path / "sbom.json"
    output = tmp_path / "report.json"
    _write_json(inventory, _inventory(license_name="UNKNOWN"))
    _write_json(sbom, _sbom())

    code = AUDITOR.main(
        [
            "licenses",
            "--inventory",
            str(inventory),
            "--sbom",
            str(sbom),
            "--policy",
            str(POLICY),
            "--output",
            str(output),
        ]
    )

    assert code == 1
    assert json.loads(output.read_text(encoding="utf-8"))["automation_result"] == "fail"
