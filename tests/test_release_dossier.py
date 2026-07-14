"""Fail-closed release dossier contract tests."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import replace
from typing import Any

import pytest

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "build_release_dossier.py"
SPEC = importlib.util.spec_from_file_location("build_release_dossier", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
dossier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dossier
SPEC.loader.exec_module(dossier)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dossier._canonical_json_bytes(value))


def _wheel_record(files: dict[str, bytes], record_name: str) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    for name, payload in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        writer.writerow([name, f"sha256={digest}", str(len(payload))])
    writer.writerow([record_name, "", ""])
    return output.getvalue().encode()


def _package_metadata(root: pathlib.Path, version: str) -> bytes:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = "".join(
        f"Requires-Dist: {requirement}\n" for requirement in project["dependencies"]
    )
    return (
        f"Metadata-Version: 2.3\nName: bench-cleanser\nVersion: {version}\n"
        f"Requires-Python: {project['requires-python']}\n{requirements}\n"
    ).encode()


def _build_wheel(root: pathlib.Path, version: str) -> pathlib.Path:
    dist_info = f"bench_cleanser-{version}.dist-info"
    record_name = f"{dist_info}/RECORD"
    files = {
        "bench_cleanser/__init__.py": (root / "bench_cleanser" / "__init__.py").read_bytes(),
        f"{dist_info}/METADATA": _package_metadata(root, version),
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{dist_info}/licenses/LICENSE": (root / "LICENSE").read_bytes(),
    }
    files[record_name] = _wheel_record(files, record_name)
    path = root.parent / f"bench_cleanser-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            archive.writestr(name, payload)
    return path


def _add_wheel_member(path: pathlib.Path, name: str, payload: bytes) -> None:
    with zipfile.ZipFile(path) as archive:
        files = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir() and not info.filename.endswith(".dist-info/RECORD")
        }
    files[name] = payload
    record_name = next(
        f"{member.rsplit('/', 1)[0]}/RECORD"
        for member in files
        if member.endswith(".dist-info/METADATA")
    )
    files[record_name] = _wheel_record(files, record_name)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member, content in sorted(files.items()):
            archive.writestr(member, content)


def _build_sdist(root: pathlib.Path, version: str) -> pathlib.Path:
    path = root.parent / f"bench_cleanser-{version}.tar.gz"
    archive_root = f"bench_cleanser-{version}"
    files = {
        "pyproject.toml": (root / "pyproject.toml").read_bytes(),
        "README.md": (root / "README.md").read_bytes(),
        "CHANGELOG.md": (root / "CHANGELOG.md").read_bytes(),
        "LICENSE": (root / "LICENSE").read_bytes(),
        "supply-chain/license-policy.toml": (
            root / "supply-chain" / "license-policy.toml"
        ).read_bytes(),
        "experiments/fixture/study.py": (
            root / "experiments" / "fixture" / "study.py"
        ).read_bytes(),
        "tests/__init__.py": (root / "tests" / "__init__.py").read_bytes(),
        "docs/literature.lock.json": (root / "docs" / "literature.lock.json").read_bytes(),
        "docs/literature.claims.json": (root / "docs" / "literature.claims.json").read_bytes(),
        "bench_cleanser/__init__.py": (root / "bench_cleanser" / "__init__.py").read_bytes(),
        "PKG-INFO": _package_metadata(root, version),
    }
    with tarfile.open(path, "w:gz") as archive:
        for relative, payload in sorted(files.items()):
            info = tarfile.TarInfo(f"{archive_root}/{relative}")
            info.size = len(payload)
            info.mtime = 0
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))
    return path


def _gate_summary(kind: str) -> dict[str, Any]:
    if kind == "test":
        return {"collected": 10, "errors": 0, "failed": 0, "passed": 10, "skipped": 0}
    if kind == "coverage":
        return {"measured_files": 3, "minimum_percent": 70.0, "percent": 80.0}
    return {"checked_files": 3, "errors": 0, "tool": "ruff" if kind == "lint" else "mypy"}


def _literature_lock_fixture() -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "entries": [
            {
                "versioned_id": "2310.06770v3",
                "canonical_title": "Fixture Paper A",
                "pdf_url": "https://arxiv.org/pdf/2310.06770v3",
            },
            {
                "versioned_id": "2504.07164v1",
                "canonical_title": "Fixture Paper B",
                "pdf_url": "https://arxiv.org/pdf/2504.07164v1",
            },
        ],
        "source": {"responses": [{"raw_atom_sha256": "4" * 64}]},
    }


def _literature_claims_fixture() -> dict[str, Any]:
    return {
        "schema_version": dossier.CLAIM_LEDGER_SCHEMA_VERSION,
        "status": dossier.CLAIM_LEDGER_STATUS,
        "reviewed_at": "2026-07-13",
        "coverage": {
            "locked_paper_count": 2,
            "reviewed_pdf_count": 1,
            "complete": False,
        },
        "entries": [
            {
                "versioned_id": "2310.06770v3",
                "canonical_title": "Fixture Paper A",
                "pdf_url": "https://arxiv.org/pdf/2310.06770v3",
                "pdf_sha256": "6" * 64,
                "pdf_bytes": 123,
                "artifact_name": "2310.06770v3.pdf",
                "review": {
                    "method": "machine_assisted_primary_pdf_review",
                    "human_confirmed": False,
                },
                "claims": [
                    {
                        "claim_id": "fixture-claim",
                        "claim_type": "author_reported_method",
                        "paraphrase": "The fixture paper reports a method.",
                        "pdf_pages": [1],
                        "section": "Section 1",
                        "project_use": "Fixture boundary",
                    }
                ],
            }
        ],
    }


def _gate_evidence(
    directory: pathlib.Path,
    kind: str,
    *,
    commit: str,
    tree: str,
) -> pathlib.Path:
    log = f"{kind} passed\n".encode()
    log_path = directory / f"{kind}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(log)
    pytest_command = [
        "pytest",
        "tests/",
        "-q",
        "--tb=short",
        "--cov=bench_cleanser",
        "--cov-report=term",
        "--cov-fail-under=70",
    ]
    commands = {
        "test": pytest_command,
        "coverage": pytest_command,
        "lint": ["ruff", "check", "."],
        "type": ["mypy", "bench_cleanser"],
    }
    evidence = {
        "schema_version": dossier.GATE_EVIDENCE_SCHEMA_VERSION,
        "kind": kind,
        "source": {"commit": commit, "tree": tree},
        "command": commands[kind],
        "platform": {
            "os": "Linux",
            "architecture": "x86_64",
            "python_version": "3.11.15",
        },
        "started_at": "2026-07-13T01:00:00Z",
        "completed_at": "2026-07-13T01:01:00Z",
        "result": {"exit_code": 0, "status": "pass", "summary": _gate_summary(kind)},
        "log": {"relative_path": log_path.name, "bytes": len(log), "sha256": _sha256(log)},
    }
    path = directory / f"{kind}.json"
    _write_json(path, evidence)
    return path


def _fixture(
    tmp_path: pathlib.Path,
    *,
    released: bool = True,
    tagged: bool = True,
    declared_dependencies: tuple[str, ...] = (),
    resolved_dependencies: tuple[tuple[str, str], ...] = (),
) -> tuple[Any, Any]:
    version = "0.1.0"
    commit = "1" * 40
    tree = "2" * 40
    root = tmp_path / "repo"
    (root / "bench_cleanser").mkdir(parents=True)
    (root / "bench_cleanser" / "__init__.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "bench-cleanser"\nversion = "{version}"\n'
        'requires-python = ">=3.11"\n'
        f"dependencies = {json.dumps(list(declared_dependencies))}\n\n"
        "[project.urls]\n"
        'Repository = "https://github.com/example/bench-cleanser"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# fixture\n\nversion = {0.1.0}\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        (
            "# Changelog\n\n## [0.1.0] - 2026-07-13\n"
            if released
            else "# Changelog\n\n## [Unreleased] — 0.1.0 engineering-alpha candidate\n"
        ),
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("MIT fixture\n", encoding="utf-8")
    policy_path = root / "supply-chain" / "license-policy.toml"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        'policy_name = "fixture"\npolicy_version = "1.0"\nlegal_review_complete = false\n',
        encoding="utf-8",
    )
    study_code = root / "experiments" / "fixture" / "study.py"
    study_code.parent.mkdir(parents=True)
    study_code.write_text("VALUE = 1\n", encoding="utf-8")
    empty_test_package = root / "tests" / "__init__.py"
    empty_test_package.parent.mkdir(parents=True)
    empty_test_package.write_bytes(b"")
    literature = root / "docs" / "literature.lock.json"
    literature_claims = root / "docs" / "literature.claims.json"
    _write_json(literature, _literature_lock_fixture())
    _write_json(literature_claims, _literature_claims_fixture())

    subprocess.run(
        ["git", "init", "-q", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )

    def fixture_git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    fixture_git("config", "user.name", "Release Dossier Fixture")
    fixture_git("config", "user.email", "release-dossier@example.invalid")
    fixture_git("add", ".")
    fixture_git("-c", "commit.gpgSign=false", "commit", "-q", "-m", "fixture")

    wheel = _build_wheel(root, version)
    sdist = _build_sdist(root, version)
    wheel_sha = _sha256(wheel.read_bytes())
    sdist_sha = _sha256(sdist.read_bytes())
    policy_sha = _sha256(policy_path.read_bytes())
    artifact_report = tmp_path / "artifact-report.json"
    _write_json(
        artifact_report,
        {
            "artifacts": [
                {
                    "members": 4,
                    "name": wheel.name,
                    "sha256": wheel_sha,
                    "uncompressed_regular_bytes": 500,
                },
                {
                    "members": 6,
                    "name": sdist.name,
                    "sha256": sdist_sha,
                    "uncompressed_regular_bytes": 1000,
                },
            ],
            "automation_result": "pass",
            "custom_findings": [],
            "detect_secrets": {
                "declared_provenance_hashes": [],
                "findings": [],
                "network_verification": "disabled",
                "version": "1.5.0",
            },
            "policy_sha256": policy_sha,
        },
    )
    sbom = tmp_path / "sbom.json"
    resolved = sorted(resolved_dependencies)
    package_identities = sorted([("bench-cleanser", version), *resolved])
    sbom_components = [
        {"name": name, "version": package_version}
        for name, package_version in (resolved or [("bench-cleanser", version)])
    ]
    _write_json(
        sbom,
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "version": 1,
            "metadata": {"component": {"name": "bench-cleanser", "version": version}},
            "components": sbom_components,
            "dependencies": [{"ref": "root"}],
        },
    )
    inventory = tmp_path / "inventory.json"
    _write_json(
        inventory,
        [
            {
                "Name": name,
                "Version": package_version,
                "License": "MIT",
                "LicenseText": "MIT fixture",
            }
            for name, package_version in package_identities
        ],
    )
    license_report = tmp_path / "license-report.json"
    _write_json(
        license_report,
        {
            "automation_result": "pass",
            "legal_review_complete": False,
            "limitations": ["Automated fixture triage is not legal advice."],
            "packages": [
                {"name": name, "version": package_version, "decision": "allow"}
                for name, package_version in package_identities
            ],
            "policy": {"name": "fixture", "sha256": policy_sha, "version": "1.0"},
            "sbom_coverage_errors": [],
            "scope_profiles": ["default", "structural"],
            "source_artifacts": {
                "inventory_sha256": _sha256(inventory.read_bytes()),
                "sbom_sha256": _sha256(sbom.read_bytes()),
            },
            "summary": {
                "allow": len(package_identities),
                "deny": 0,
                "review": 0,
                "total": len(package_identities),
            },
        },
    )
    evidence_dir = tmp_path / "evidence"
    evidence = {
        kind: _gate_evidence(evidence_dir, kind, commit=commit, tree=tree)
        for kind in ("test", "coverage", "lint", "type")
    }
    linux = tmp_path / "linux-ci.json"
    matrix_files = [
        {"bytes": 10, "logical_path": name, "sha256": _sha256(name.encode())}
        for name in (
            "coverage.json",
            "lint.json",
            "lint.log",
            "pytest.log",
            "test.json",
            "type.json",
            "type.log",
        )
    ]
    _write_json(
        linux,
        {
            "schema_version": dossier.LINUX_CI_SCHEMA_VERSION,
            "source": {"commit": commit, "tree": tree},
            "provider": "github-actions",
            "github_context": {
                "event_name": "push",
                "job": "release-evidence",
                "ref": "refs/heads/main",
                "runner_arch": "X64",
                "runner_os": "Linux",
                "sha": commit,
                "workflow": "CI",
                "workflow_ref": "example/bench-cleanser/.github/workflows/ci.yml@refs/heads/main",
                "workflow_sha": commit,
            },
            "matrix_evidence": [
                {
                    "files": matrix_files,
                    "platform": {
                        "architecture": "x86_64",
                        "os": "Linux",
                        "python_full_version": "3.11.15",
                    },
                    "python_version": "3.11",
                },
                {
                    "files": matrix_files,
                    "platform": {
                        "architecture": "x86_64",
                        "os": "Linux",
                        "python_full_version": "3.12.11",
                    },
                    "python_version": "3.12",
                },
            ],
            "repository": "example/bench-cleanser",
            "workflow": ".github/workflows/ci.yml",
            "run_id": 123,
            "run_attempt": 1,
            "run_url": "https://github.com/example/bench-cleanser/actions/runs/123",
            "runner": {
                "os": "Linux",
                "architecture": "x86_64",
                "python_versions": ["3.11", "3.12"],
            },
            "conclusion": "success",
            "completed_at": "2026-07-13T02:00:00Z",
            "release_artifacts": {
                "wheel_sha256": wheel_sha,
                "sdist_sha256": sdist_sha,
                "artifact_report_sha256": _sha256(artifact_report.read_bytes()),
            },
        },
    )
    environment = tmp_path / "environment-lock.json"
    _write_json(
        environment,
        {
            "schema_version": dossier.ENVIRONMENT_LOCK_SCHEMA_VERSION,
            "source": {
                "commit": commit,
                "tree": tree,
                "wheel_sha256": wheel_sha,
                "sdist_sha256": sdist_sha,
            },
            "platform": {"os": "Linux", "architecture": "x86_64"},
            "python": {"implementation": "CPython", "version": "3.11.15"},
            "packages": [
                {
                    "name": name,
                    "version": package_version,
                    "hashes": [
                        wheel_sha
                        if name == "bench-cleanser"
                        else _sha256(f"{name}=={package_version}".encode())
                    ],
                }
                for name, package_version in package_identities
            ],
        },
    )
    literature = root / "docs" / "literature.lock.json"
    _write_json(
        literature,
        {
            "schema_version": "0.1.0",
            "entries": [
                {
                    "versioned_id": "2310.06770v3",
                    "canonical_title": "Fixture Paper A",
                    "pdf_url": "https://arxiv.org/pdf/2310.06770v3",
                },
                {
                    "versioned_id": "2504.07164v1",
                    "canonical_title": "Fixture Paper B",
                    "pdf_url": "https://arxiv.org/pdf/2504.07164v1",
                },
            ],
            "source": {"responses": [{"raw_atom_sha256": "4" * 64}]},
        },
    )
    literature_claims = root / "docs" / "literature.claims.json"
    _write_json(
        literature_claims,
        {
            "schema_version": dossier.CLAIM_LEDGER_SCHEMA_VERSION,
            "status": dossier.CLAIM_LEDGER_STATUS,
            "reviewed_at": "2026-07-13",
            "coverage": {
                "locked_paper_count": 2,
                "reviewed_pdf_count": 1,
                "complete": False,
            },
            "entries": [
                {
                    "versioned_id": "2310.06770v3",
                    "canonical_title": "Fixture Paper A",
                    "pdf_url": "https://arxiv.org/pdf/2310.06770v3",
                    "pdf_sha256": "6" * 64,
                    "pdf_bytes": 123,
                    "artifact_name": "2310.06770v3.pdf",
                    "review": {
                        "method": "machine_assisted_primary_pdf_review",
                        "human_confirmed": False,
                    },
                    "claims": [
                        {
                            "claim_id": "fixture-claim",
                            "claim_type": "author_reported_method",
                            "paraphrase": "The fixture paper reports a method.",
                            "pdf_pages": [1],
                            "section": "Section 1",
                            "project_use": "Fixture boundary",
                        }
                    ],
                }
            ],
        },
    )
    study = tmp_path / "study.json"
    study_payload = study_code.read_bytes()
    _write_json(
        study,
        {
            "schema_version": "fixture-study-0.1.0",
            "study_id": "fixture-study",
            "study_code_identity": {
                "logical_path": "experiments/fixture/study.py",
                "bytes": len(study_payload),
                "sha256": _sha256(study_payload),
            },
        },
    )
    git = dossier.GitIdentity(
        commit=commit,
        tree=tree,
        branch="main",
        dirty_entries=(),
        diff_check_passed=True,
        tag=f"v{version}" if tagged else None,
        tag_object="5" * 40 if tagged else None,
        tag_object_type="tag" if tagged else None,
        tag_target=commit if tagged else None,
        tag_message="fixture release\n" if tagged else None,
        tag_signature_verified=tagged,
    )
    inputs = dossier.DossierInputs(
        repo_root=root,
        wheel=wheel,
        sdist=sdist,
        artifact_report=artifact_report,
        sbom=sbom,
        license_inventory=inventory,
        license_report=license_report,
        test_evidence=evidence["test"],
        coverage_evidence=evidence["coverage"],
        lint_evidence=evidence["lint"],
        type_evidence=evidence["type"],
        linux_ci_evidence=linux,
        literature_lock=literature,
        literature_claims=literature_claims,
        environment_lock=environment,
        study_artifacts=(("fixture", study),),
        attestation=None,
    )
    if released and tagged:
        preliminary = dossier._build_dossier_with_git(inputs, git)
        attestation = preliminary["human_attestation"]["required_template"]
        attestation["maintainer"] = {
            "identifier": "mailto:maintainer@example.com",
            "name": "Release Maintainer",
        }
        attestation["legal_review"].update(
            {
                "completed": True,
                "reviewed_at": "2026-07-13T03:00:00Z",
                "reviewer": "License Reviewer",
            }
        )
        attestation["approval"].update(
            {
                "approved_at": "2026-07-13T03:01:00Z",
                "decision": "approve",
            }
        )
        attestation_path = tmp_path / "attestation.json"
        _write_json(attestation_path, attestation)
        attestation_sha = _sha256(attestation_path.read_bytes())
        git = replace(
            git,
            tag_message=(f"fixture release\n\nRelease-Attestation-SHA256: {attestation_sha}\n"),
        )
        inputs = replace(inputs, attestation=attestation_path)
    return inputs, git


def test_complete_dossier_is_deterministic_and_checkable(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    first = dossier._build_dossier_with_git(inputs, git)
    second = dossier._build_dossier_with_git(inputs, git)

    assert first == second
    assert first["release_ready"] is True
    assert first["blockers"] == []
    assert first["readiness_claim"] == "ready_for_named_human_release_action"
    output = tmp_path / "release-dossier.json"
    dossier.write_dossier(output, first)
    dossier.check_dossier(output, second)


def test_dirty_tree_can_never_claim_ready(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    dirty = replace(git, dirty_entries=(" M README.md", "?? scratch.txt"))
    result = dossier._build_dossier_with_git(inputs, dirty)

    assert result["release_ready"] is False
    assert result["readiness_claim"] == "blocked_no_public_release_claim"
    assert "git_worktree_clean" in result["blockers"]


def test_unreleased_untagged_source_is_explicitly_blocked(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path, released=False, tagged=False)
    result = dossier._build_dossier_with_git(inputs, git)

    assert result["release_ready"] is False
    assert "changelog_released" in result["blockers"]
    assert "release_tag_present" in result["blockers"]
    assert "release_tag_annotated" in result["blockers"]
    assert "release_tag_signature_verified" in result["blockers"]


def test_artifact_report_tampering_is_detected(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    report = json.loads(inputs.artifact_report.read_text(encoding="utf-8"))
    report["artifacts"][0]["sha256"] = "f" * 64
    _write_json(inputs.artifact_report, report)

    result = dossier._build_dossier_with_git(inputs, git)
    assert result["release_ready"] is False
    assert "artifact_audit_passed_and_current" in result["blockers"]
    assert "linux_ci_passed_and_current" in result["blockers"]


def test_stale_test_evidence_is_detected(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    evidence = json.loads(inputs.test_evidence.read_text(encoding="utf-8"))
    evidence["source"]["commit"] = "9" * 40
    _write_json(inputs.test_evidence, evidence)

    result = dossier._build_dossier_with_git(inputs, git)
    assert result["release_ready"] is False
    assert "test_evidence_passed_and_current" in result["blockers"]
    assert "human_attestation_valid_and_tag_bound" in result["blockers"]


def test_automated_license_report_cannot_claim_human_legal_review(
    tmp_path: pathlib.Path,
) -> None:
    inputs, git = _fixture(tmp_path)
    report = json.loads(inputs.license_report.read_text(encoding="utf-8"))
    report["legal_review_complete"] = True
    _write_json(inputs.license_report, report)

    result = dossier._build_dossier_with_git(inputs, git)
    assert result["release_ready"] is False
    assert "license_automation_passed_and_current" in result["blockers"]
    assert "license_automation_scoped_as_nonlegal" in result["blockers"]


def test_check_rejects_noncanonical_or_stale_dossier(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    result = dossier._build_dossier_with_git(inputs, git)
    output = tmp_path / "release-dossier.json"
    dossier.write_dossier(output, result)
    output.write_bytes(output.read_bytes() + b"\n")

    with pytest.raises(dossier.DossierError, match="not canonical"):
        dossier.check_dossier(output, result)


def test_check_rejects_json_bool_integer_type_confusion(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    result = dossier._build_dossier_with_git(inputs, git)
    output = tmp_path / "release-dossier.json"
    altered = dict(result)
    altered["release_ready"] = 1
    _write_json(output, altered)

    with pytest.raises(dossier.DossierError, match="stale or mismatched"):
        dossier.check_dossier(output, result)


def test_coordinated_policy_digest_substitution_is_blocked(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    substituted = "f" * 64
    artifact_report = json.loads(inputs.artifact_report.read_text(encoding="utf-8"))
    artifact_report["policy_sha256"] = substituted
    _write_json(inputs.artifact_report, artifact_report)
    license_report = json.loads(inputs.license_report.read_text(encoding="utf-8"))
    license_report["policy"]["sha256"] = substituted
    _write_json(inputs.license_report, license_report)

    result = dossier._build_dossier_with_git(inputs, git)
    assert result["release_ready"] is False
    assert "artifact_audit_passed_and_current" in result["blockers"]
    assert "license_automation_passed_and_current" in result["blockers"]
    assert result["artifacts"]["artifact_audit_report"]["policy_matches_authoritative"] is False
    assert result["artifacts"]["license_report"]["policy_matches_authoritative"] is False


def test_jointly_truncated_dependency_evidence_is_blocked(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(
        tmp_path,
        declared_dependencies=("missing-dependency>=1",),
    )
    result = dossier._build_dossier_with_git(inputs, git)

    assert result["release_ready"] is False
    assert "sbom_current" in result["blockers"]
    assert "license_inventory_current" in result["blockers"]
    assert "license_automation_passed_and_current" in result["blockers"]
    assert "environment_lock_current" in result["blockers"]


def test_resolved_dependency_version_must_satisfy_project_specifier(
    tmp_path: pathlib.Path,
) -> None:
    inputs, git = _fixture(
        tmp_path,
        declared_dependencies=("missing-dependency>=1",),
        resolved_dependencies=(("missing-dependency", "0.1"),),
    )
    result = dossier._build_dossier_with_git(inputs, git)

    assert "sbom_current" in result["blockers"]
    assert "license_inventory_current" in result["blockers"]
    assert "license_automation_passed_and_current" in result["blockers"]
    assert "environment_lock_current" in result["blockers"]
    assert result["artifacts"]["sbom"]["runtime_requirement_versions_match"] is False


def test_environment_root_hash_must_bind_supplied_wheel(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    environment = json.loads(inputs.environment_lock.read_text(encoding="utf-8"))
    environment["packages"][0]["hashes"] = ["f" * 64]
    _write_json(inputs.environment_lock, environment)

    result = dossier._build_dossier_with_git(inputs, git)
    assert "environment_lock_current" in result["blockers"]
    assert result["artifacts"]["environment_lock"]["root_wheel_hash_matches"] is False


def test_environment_python_must_satisfy_requires_python(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    environment = json.loads(inputs.environment_lock.read_text(encoding="utf-8"))
    environment["python"]["version"] = "2.7.18"
    _write_json(inputs.environment_lock, environment)

    result = dossier._build_dossier_with_git(inputs, git)
    assert "environment_lock_current" in result["blockers"]
    assert result["artifacts"]["environment_lock"]["python_runtime_supported"] is False


def test_record_valid_extra_wheel_payload_is_rejected(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    _add_wheel_member(inputs.wheel, "foreign_payload.pth", b"import foreign_payload\n")

    with pytest.raises(dossier.DossierError, match="unexpected installable payloads"):
        dossier._build_dossier_with_git(inputs, git)


def test_record_valid_dependency_specifier_drift_is_rejected(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(
        tmp_path,
        declared_dependencies=("missing-dependency>=1",),
    )
    metadata_name = "bench_cleanser-0.1.0.dist-info/METADATA"
    drifted_metadata = _package_metadata(inputs.repo_root, "0.1.0").replace(
        b"missing-dependency>=1",
        b"missing-dependency>=999",
    )
    _add_wheel_member(inputs.wheel, metadata_name, drifted_metadata)

    with pytest.raises(dossier.DossierError, match="dependency metadata differs"):
        dossier._build_dossier_with_git(inputs, git)


def test_record_valid_requires_python_drift_is_rejected(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    metadata_name = "bench_cleanser-0.1.0.dist-info/METADATA"
    drifted_metadata = _package_metadata(inputs.repo_root, "0.1.0").replace(
        b"Requires-Python: >=3.11",
        b"Requires-Python: <3",
    )
    _add_wheel_member(inputs.wheel, metadata_name, drifted_metadata)

    with pytest.raises(dossier.DossierError, match="Requires-Python differs"):
        dossier._build_dossier_with_git(inputs, git)


def test_sdist_omission_from_committed_manifest_is_rejected(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    members: dict[str, bytes] = {}
    with tarfile.open(inputs.sdist, "r:gz") as archive:
        for info in archive.getmembers():
            if (
                not info.isfile()
                or info.name == "bench_cleanser-0.1.0/experiments/fixture/study.py"
            ):
                continue
            extracted = archive.extractfile(info)
            assert extracted is not None
            members[info.name] = extracted.read()
    with tarfile.open(inputs.sdist, "w:gz") as archive:
        for name, payload in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = 0
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(dossier.DossierError, match="committed packaging projection"):
        dossier._build_dossier_with_git(inputs, git)


def test_ignored_package_source_cannot_masquerade_as_head(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    ignored = inputs.repo_root / "bench_cleanser" / "ignored_payload.py"
    ignored.write_text("VALUE = 'not in HEAD'\n", encoding="utf-8")
    exclude = inputs.repo_root / ".git" / "info" / "exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8") + "\nbench_cleanser/ignored_payload.py\n",
        encoding="utf-8",
    )

    with pytest.raises(dossier.DossierError, match="not a regular tracked HEAD blob"):
        dossier._build_dossier_with_git(inputs, git)


def test_noncanonical_attestation_is_blocked_even_when_tag_binds_raw_bytes(
    tmp_path: pathlib.Path,
) -> None:
    inputs, git = _fixture(tmp_path)
    assert inputs.attestation is not None
    decoded = json.loads(inputs.attestation.read_text(encoding="utf-8"))
    raw = json.dumps(decoded, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    inputs.attestation.write_bytes(raw)
    rebound_git = replace(
        git,
        tag_message=(f"fixture release\n\nRelease-Attestation-SHA256: {_sha256(raw)}\n"),
    )

    result = dossier._build_dossier_with_git(inputs, rebound_git)
    assert result["release_ready"] is False
    assert "human_attestation_valid_and_tag_bound" in result["blockers"]
    assert result["human_attestation"]["validation"]["canonical_json"] is False
    assert result["human_attestation"]["validation"]["tag_digest_binding_present"] is True


@pytest.mark.parametrize(
    ("kind", "command"),
    [
        ("test", ["true", "-m", "pytest", "tests/"]),
        ("test", ["pytest", "tests/", "--collect-only"]),
        (
            "coverage",
            [
                "pytest",
                "tests/",
                "--cov=bench_cleanser",
                "--cov-fail-under=70",
                "-p",
                "no:cov",
            ],
        ),
        ("type", ["mypy", "--version", "bench_cleanser"]),
    ],
)
def test_fabricated_gate_command_is_blocked(
    tmp_path: pathlib.Path,
    kind: str,
    command: list[str],
) -> None:
    inputs, git = _fixture(tmp_path)
    evidence_paths = {
        "test": inputs.test_evidence,
        "coverage": inputs.coverage_evidence,
        "type": inputs.type_evidence,
    }
    path = evidence_paths[kind]
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence["command"] = command
    _write_json(path, evidence)

    result = dossier._build_dossier_with_git(inputs, git)
    assert f"{kind}_evidence_passed_and_current" in result["blockers"]
    assert result["quality_gates"][kind]["command_policy_passed"] is False


def test_linux_run_url_must_match_repository_and_run_id(tmp_path: pathlib.Path) -> None:
    inputs, git = _fixture(tmp_path)
    evidence = json.loads(inputs.linux_ci_evidence.read_text(encoding="utf-8"))
    evidence["run_url"] = "https://github.com/other/project/actions/runs/999"
    _write_json(inputs.linux_ci_evidence, evidence)

    result = dossier._build_dossier_with_git(inputs, git)
    assert "linux_ci_passed_and_current" in result["blockers"]
    assert result["linux_ci"]["url_valid"] is False


def test_literature_claim_ledger_drift_is_rejected(tmp_path: pathlib.Path) -> None:
    inputs, _git = _fixture(tmp_path)
    claims = json.loads(inputs.literature_claims.read_text(encoding="utf-8"))
    claims["entries"][0]["canonical_title"] = "Drifted title"
    external = tmp_path / "drifted-claims.json"
    _write_json(external, claims)

    with pytest.raises(dossier.DossierError, match="drifted from the lock"):
        dossier._validate_literature_claims(external, inputs.literature_lock)


def test_external_literature_evidence_must_equal_tracked_canonical_bytes(
    tmp_path: pathlib.Path,
) -> None:
    inputs, git = _fixture(tmp_path)
    external = tmp_path / "external-claims.json"
    claims = json.loads(inputs.literature_claims.read_text(encoding="utf-8"))
    claims["reviewed_at"] = "2026-07-12"
    _write_json(external, claims)

    with pytest.raises(dossier.DossierError, match="differ from tracked"):
        dossier._build_dossier_with_git(
            replace(inputs, literature_claims=external),
            git,
        )


def test_null_canonical_titles_are_rejected_in_lock_and_ledger(
    tmp_path: pathlib.Path,
) -> None:
    inputs, _git = _fixture(tmp_path)
    lock = json.loads(inputs.literature_lock.read_text(encoding="utf-8"))
    claims = json.loads(inputs.literature_claims.read_text(encoding="utf-8"))
    lock["entries"][0]["canonical_title"] = None
    claims["entries"][0]["canonical_title"] = None
    external_lock = tmp_path / "null-title-lock.json"
    external_claims = tmp_path / "null-title-claims.json"
    _write_json(external_lock, lock)
    _write_json(external_claims, claims)

    with pytest.raises(dossier.DossierError, match="canonical_title"):
        dossier._validate_literature_lock(external_lock)
    with pytest.raises(dossier.DossierError, match="canonical_title"):
        dossier._validate_literature_claims(external_claims, external_lock)


def test_git_inspection_detects_dirty_tree_and_unsigned_annotated_tag(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "git-repo"
    subprocess.run(
        ["git", "init", "-q", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("config", "user.name", "Release Dossier Test")
    git("config", "user.email", "release-dossier@example.invalid")
    tracked = root / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    git("add", "tracked.txt")
    git("-c", "commit.gpgSign=false", "commit", "-q", "-m", "fixture")
    git("-c", "tag.gpgSign=false", "tag", "-a", "v0.1.0", "-m", "release")

    clean = dossier.inspect_git_identity(root, "0.1.0")
    assert clean.dirty_entries == ()
    assert clean.tag == "v0.1.0"
    assert clean.tag_object_type == "tag"
    assert clean.tag_target == clean.commit
    assert clean.tag_signature_verified is False

    tracked.write_text("tracked\ndirty\n", encoding="utf-8")
    dirty = dossier.inspect_git_identity(root, "0.1.0")
    assert dirty.dirty_entries == (" M tracked.txt",)
