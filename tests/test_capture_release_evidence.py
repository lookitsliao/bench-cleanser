"""Canonical CI/release evidence capture contracts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
from typing import Any

import pytest

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "capture_release_evidence.py"
SPEC = importlib.util.spec_from_file_location("capture_release_evidence", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
capture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture
SPEC.loader.exec_module(capture)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: pathlib.Path, value: Any) -> None:
    path.write_bytes(capture._canonical_json_bytes(value))


def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "repo"
    (root / "bench_cleanser").mkdir(parents=True)
    (root / "bench_cleanser" / "__init__.py").write_text("VALUE = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Evidence Fixture"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "config",
            "user.email",
            "evidence@example.invalid",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "commit.gpgSign=false",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )
    return root


def _captured(argv: tuple[str, ...], raw: bytes, return_code: int = 0) -> Any:
    started = "2026-07-13T00:00:00Z"
    completed = "2026-07-13T00:00:01Z"
    return capture.CapturedCommand(
        argv=argv,
        started_at=started,
        completed_at=completed,
        return_code=return_code,
        raw_output=raw,
        log_output=capture._command_log(argv, raw, return_code, started, completed),
    )


def test_quality_capture_emits_dossier_compatible_records(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _git_repo(tmp_path)
    pytest_output = b"""Name                         Stmts   Miss  Cover
------------------------------------------------
bench_cleanser/__init__.py       10      1    90%
------------------------------------------------
TOTAL                            10      1    90%
9 passed, 1 skipped in 0.10s
"""
    captures = {
        capture.QUALITY_COMMANDS["lint"]: _captured(
            capture.QUALITY_COMMANDS["lint"], b"All checks passed!\n"
        ),
        capture.QUALITY_COMMANDS["type"]: _captured(
            capture.QUALITY_COMMANDS["type"],
            b"Success: no issues found in 1 source file\n",
        ),
        capture.QUALITY_COMMANDS["pytest"]: _captured(
            capture.QUALITY_COMMANDS["pytest"], pytest_output
        ),
    }

    def fake_run(argv: tuple[str, ...], _root: pathlib.Path) -> Any:
        return captures[argv]

    monkeypatch.setattr(capture, "_run_command", fake_run)
    output = tmp_path / "quality"
    assert capture.capture_quality(root, output) is True

    records = {
        kind: json.loads((output / f"{kind}.json").read_text())
        for kind in ("coverage", "lint", "test", "type")
    }
    assert records["test"]["command"] == list(capture.QUALITY_COMMANDS["pytest"])
    assert records["test"]["result"]["summary"] == {
        "collected": 10,
        "errors": 0,
        "failed": 0,
        "passed": 9,
        "skipped": 1,
    }
    assert records["coverage"]["result"]["summary"] == {
        "measured_files": 1,
        "minimum_percent": 70.0,
        "percent": 90.0,
    }
    assert all(record["result"]["status"] == "pass" for record in records.values())
    for name in ("coverage.json", "lint.json", "test.json", "type.json"):
        payload = (output / name).read_bytes()
        assert payload.endswith(b"\n")
        assert payload == capture._canonical_json_bytes(json.loads(payload))


@pytest.mark.parametrize(
    ("output", "expected_valid"),
    [
        (b"724 passed in 3.1s\n", True),
        (b"723 passed, 1 skipped in 3.1s\n", True),
        (b"722 passed, 1 failed, 1 skipped in 3.1s\n", False),
        (b"722 passed, 1 xfailed in 3.1s\n", False),
        (b"not a pytest summary\n", False),
    ],
)
def test_pytest_parser_is_conservative(output: bytes, expected_valid: bool) -> None:
    summary, valid = capture.parse_pytest_summary(output)
    assert valid is expected_valid
    assert summary["collected"] >= 1
    if valid:
        assert summary["passed"] + summary["skipped"] == summary["collected"]
    else:
        assert summary["failed"] > 0 or summary["errors"] > 0


def test_coverage_parser_rejects_multiple_total_lines() -> None:
    output = b"""bench_cleanser/a.py 10 0 100%
TOTAL 10 0 100%
bench_cleanser/a.py 10 4 60%
TOTAL 10 4 60%
"""
    summary, valid = capture.parse_coverage_summary(output)
    assert valid is False
    assert summary["percent"] == 0.0


def _install_item(name: str, version: str, digest: str) -> dict[str, Any]:
    return {
        "download_info": {
            "archive_info": {"hashes": {"sha256": digest}},
            "url": f"https://packages.example.invalid/{name}-{version}.whl",
        },
        "is_direct": False,
        "is_yanked": False,
        "metadata": {"name": name, "version": version},
        "requested": True,
    }


def test_environment_lock_requires_complete_archive_hash_set(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _git_repo(tmp_path)
    wheel = tmp_path / "bench_cleanser-0.1.0-py3-none-any.whl"
    sdist = tmp_path / "bench_cleanser-0.1.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    wheel_sha = _sha256(wheel.read_bytes())
    dependency_sha = "d" * 64
    report = tmp_path / "pip-report.json"
    _write_json(
        report,
        {
            "environment": {
                "implementation_name": "cpython",
                "platform_machine": "x86_64",
                "platform_python_implementation": "CPython",
                "platform_system": "Linux",
                "python_full_version": "3.11.15",
            },
            "install": [
                _install_item("bench-cleanser", "0.1.0", wheel_sha),
                _install_item("dependency", "2.0", dependency_sha),
            ],
            "pip_version": "26.1",
            "version": "1",
        },
    )
    inventory = tmp_path / "inventory.json"
    _write_json(
        inventory,
        [
            {"Name": "bench-cleanser", "Version": "0.1.0"},
            {"Name": "Dependency", "Version": "2.0"},
        ],
    )
    monkeypatch.setattr(
        capture,
        "_target_python_identity",
        lambda _python: (
            {"architecture": "x86_64", "os": "Linux"},
            {"implementation": "CPython", "version": "3.11.15"},
        ),
    )
    monkeypatch.setattr(
        capture,
        "_target_package_identities",
        lambda _python: {("bench-cleanser", "0.1.0"), ("dependency", "2.0")},
    )
    output = tmp_path / "environment-lock.json"
    lock = capture.capture_environment(
        root=root,
        pip_report=report,
        inventory=inventory,
        wheel=wheel,
        sdist=sdist,
        target_python=pathlib.Path(sys.executable),
        output=output,
    )
    assert lock["schema_version"] == capture.ENVIRONMENT_SCHEMA_VERSION
    assert lock["source"]["wheel_sha256"] == wheel_sha
    assert [(item["name"], item["version"]) for item in lock["packages"]] == [
        ("bench-cleanser", "0.1.0"),
        ("Dependency", "2.0"),
    ]

    altered = json.loads(report.read_text())
    altered["install"].pop()
    second_report = tmp_path / "pip-report-incomplete.json"
    _write_json(second_report, altered)
    with pytest.raises(capture.CaptureError, match="package sets differ"):
        capture.capture_environment(
            root=root,
            pip_report=second_report,
            inventory=inventory,
            wheel=wheel,
            sdist=sdist,
            target_python=pathlib.Path(sys.executable),
            output=tmp_path / "second-environment.json",
        )

    mismatched = json.loads(report.read_text())
    mismatched["environment"]["platform_system"] = "Darwin"
    mismatch_report = tmp_path / "pip-report-wrong-platform.json"
    _write_json(mismatch_report, mismatched)
    with pytest.raises(capture.CaptureError, match="differs from target Python"):
        capture.capture_environment(
            root=root,
            pip_report=mismatch_report,
            inventory=inventory,
            wheel=wheel,
            sdist=sdist,
            target_python=pathlib.Path(sys.executable),
            output=tmp_path / "third-environment.json",
        )


def _quality_directory(
    path: pathlib.Path,
    root: pathlib.Path,
    python_version: str,
) -> pathlib.Path:
    path.mkdir()
    source = capture.inspect_source(root)
    log_payloads = {
        "lint.log": b"lint passed\n",
        "pytest.log": b"tests passed\n",
        "type.log": b"type passed\n",
    }
    for name, payload in log_payloads.items():
        (path / name).write_bytes(payload)
    summaries = {
        "coverage": {"measured_files": 1, "minimum_percent": 70.0, "percent": 90.0},
        "lint": {"checked_files": 2, "errors": 0, "tool": "ruff"},
        "test": {"collected": 2, "errors": 0, "failed": 0, "passed": 2, "skipped": 0},
        "type": {"checked_files": 1, "errors": 0, "tool": "mypy"},
    }
    log_names = {
        "coverage": "pytest.log",
        "lint": "lint.log",
        "test": "pytest.log",
        "type": "type.log",
    }
    commands = {
        "coverage": capture.QUALITY_COMMANDS["pytest"],
        "lint": capture.QUALITY_COMMANDS["lint"],
        "test": capture.QUALITY_COMMANDS["pytest"],
        "type": capture.QUALITY_COMMANDS["type"],
    }
    for kind in ("coverage", "lint", "test", "type"):
        log_name = log_names[kind]
        log = log_payloads[log_name]
        _write_json(
            path / f"{kind}.json",
            {
                "command": list(commands[kind]),
                "completed_at": "2026-07-13T00:00:01Z",
                "kind": kind,
                "log": {
                    "bytes": len(log),
                    "relative_path": log_name,
                    "sha256": _sha256(log),
                },
                "platform": {
                    "architecture": "x86_64",
                    "os": "Linux",
                    "python_version": python_version,
                },
                "result": {"exit_code": 0, "status": "pass", "summary": summaries[kind]},
                "schema_version": capture.GATE_SCHEMA_VERSION,
                "source": {"commit": source.commit, "tree": source.tree},
                "started_at": "2026-07-13T00:00:00Z",
            },
        )
    return path


def test_linux_ci_receipt_is_source_and_artifact_bound(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _git_repo(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    wheel = artifacts / "bench_cleanser-0.1.0-py3-none-any.whl"
    sdist = artifacts / "bench_cleanser-0.1.0.tar.gz"
    report = artifacts / "artifact-audit-report.json"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    _write_json(
        report,
        {
            "artifacts": [
                {
                    "members": 2,
                    "name": wheel.name,
                    "sha256": _sha256(wheel.read_bytes()),
                    "uncompressed_regular_bytes": 10,
                },
                {
                    "members": 2,
                    "name": sdist.name,
                    "sha256": _sha256(sdist.read_bytes()),
                    "uncompressed_regular_bytes": 10,
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
            "policy_sha256": "a" * 64,
        },
    )
    quality_311 = _quality_directory(tmp_path / "quality-311", root, "3.11.15")
    quality_312 = _quality_directory(tmp_path / "quality-312", root, "3.12.11")
    monkeypatch.setattr(capture.platform, "system", lambda: "Linux")
    monkeypatch.setattr(capture.platform, "machine", lambda: "x86_64")
    github_environment = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_JOB": "release-evidence",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "example/bench-cleanser",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_RUN_ID": "123",
        "GITHUB_SHA": capture.inspect_source(root).commit,
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_WORKFLOW_REF": (
            "example/bench-cleanser/.github/workflows/ci.yml@refs/heads/main"
        ),
        "GITHUB_WORKFLOW_SHA": capture.inspect_source(root).commit,
        "RUNNER_ARCH": "X64",
        "RUNNER_OS": "Linux",
    }
    for key, value in github_environment.items():
        monkeypatch.setenv(key, value)

    output = tmp_path / "linux-ci.json"
    record = capture.capture_linux_ci(
        root=root,
        artifact_directory=artifacts,
        artifact_report=report,
        repository="example/bench-cleanser",
        run_id=123,
        run_attempt=2,
        quality_evidence_directories=[quality_312, quality_311],
        output=output,
    )
    assert record["schema_version"] == capture.LINUX_CI_SCHEMA_VERSION
    assert record["run_url"] == (
        "https://github.com/example/bench-cleanser/actions/runs/123"
    )
    assert record["runner"]["python_versions"] == ["3.11", "3.12"]
    assert [item["python_version"] for item in record["matrix_evidence"]] == [
        "3.11",
        "3.12",
    ]
    assert record["release_artifacts"]["wheel_sha256"] == _sha256(
        wheel.read_bytes()
    )
    with pytest.raises(capture.CaptureError, match="already exists"):
        capture.capture_linux_ci(
            root=root,
            artifact_directory=artifacts,
            artifact_report=report,
            repository="example/bench-cleanser",
            run_id=123,
            run_attempt=2,
            quality_evidence_directories=[quality_311, quality_312],
            output=output,
        )


def test_source_capture_refuses_dirty_tree(tmp_path: pathlib.Path) -> None:
    root = _git_repo(tmp_path)
    (root / "untracked.txt").write_text("dirty")
    with pytest.raises(capture.CaptureError, match="clean worktree"):
        capture.inspect_source(root)
