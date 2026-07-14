#!/usr/bin/env python3
"""Capture canonical local and GitHub Actions release-evidence records.

The tool has three fail-closed modes:

* ``quality`` runs the exact commands accepted by the release dossier and
  preserves their combined logs plus test/coverage/lint/type records;
* ``environment`` converts a complete pip installation report into a
  wheel/sdist/source-bound Linux environment lock; and
* ``linux-ci`` emits the cross-job GitHub Actions receipt only after callers
  have arranged for all required jobs to succeed.

It creates new outputs exclusively.  It does not sign, upload, or authenticate
GitHub state; the signed release attestation remains the accountability boundary.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

GATE_SCHEMA_VERSION = "bench-cleanser-release-gate-evidence-0.1.0"
ENVIRONMENT_SCHEMA_VERSION = "bench-cleanser-environment-lock-0.1.0"
LINUX_CI_SCHEMA_VERSION = "bench-cleanser-linux-ci-evidence-0.2.0"

QUALITY_COMMANDS: Mapping[str, tuple[str, ...]] = {
    "lint": ("ruff", "check", "."),
    "type": ("mypy", "bench_cleanser"),
    "pytest": (
        "pytest",
        "tests/",
        "-q",
        "--tb=short",
        "--cov=bench_cleanser",
        "--cov-report=term",
        "--cov-fail-under=70",
    ),
}

MINIMUM_COVERAGE = 70.0
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_LOG_BYTES = 64 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_PYTEST_TOKEN_RE = re.compile(
    r"(?P<count>[0-9]+) (?P<kind>passed|failed|skipped|errors?|xfailed|xpassed|deselected)"
)
_COVERAGE_TOTAL_RE = re.compile(
    r"^TOTAL\s+(?P<statements>[0-9]+)(?:\s+[0-9]+){1,4}\s+"
    r"(?P<percent>[0-9]+(?:\.[0-9]+)?)%\s*$",
    re.MULTILINE,
)


class CaptureError(ValueError):
    """Requested evidence cannot be captured without ambiguity."""


@dataclasses.dataclass(frozen=True)
class SourceIdentity:
    commit: str
    tree: str


@dataclasses.dataclass(frozen=True)
class CapturedCommand:
    argv: tuple[str, ...]
    started_at: str
    completed_at: str
    return_code: int
    raw_output: bytes
    log_output: bytes


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _load_json(path: pathlib.Path, field: str) -> tuple[Any, bytes]:
    if path.is_symlink() or not path.is_file():
        raise CaptureError(f"{field} must be a regular non-symlink file")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_JSON_BYTES:
        raise CaptureError(f"{field} has an invalid byte count")

    def reject_constant(value: str) -> None:
        raise CaptureError(f"{field} contains non-standard constant {value!r}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CaptureError(f"{field} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureError(f"{field} is not strict UTF-8 JSON") from exc
    return decoded, payload


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CaptureError(f"{field} must be a JSON object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CaptureError(f"{field} must be a JSON array")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        raise CaptureError(
            f"{field} fields differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: Any, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CaptureError(f"{field} must be a trimmed non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise CaptureError(f"{field} has an invalid format")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CaptureError(f"{field} must be an integer at least {minimum}")
    return value


def _run_git(root: pathlib.Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CaptureError(f"git {' '.join(args)} failed") from exc
    return completed.stdout.strip()


def inspect_source(root: pathlib.Path) -> SourceIdentity:
    top = pathlib.Path(_run_git(root, "rev-parse", "--show-toplevel")).resolve()
    if top != root.resolve():
        raise CaptureError("repo root must be the exact Git top level")
    dirty = _run_git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise CaptureError("release evidence requires a clean worktree")
    try:
        subprocess.run(
            ["git", "-C", str(root), "diff", "--check"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CaptureError("git diff --check failed") from exc
    commit = _run_git(root, "rev-parse", "HEAD")
    tree = _run_git(root, "rev-parse", "HEAD^{tree}")
    if _GIT_OID_RE.fullmatch(commit) is None or _GIT_OID_RE.fullmatch(tree) is None:
        raise CaptureError("Git returned a non-canonical object identity")
    return SourceIdentity(commit=commit, tree=tree)


def _platform_record() -> dict[str, str]:
    return {
        "architecture": platform.machine(),
        "os": platform.system(),
        "python_version": platform.python_version(),
    }


def _run_command(argv: tuple[str, ...], root: pathlib.Path) -> CapturedCommand:
    started = _utc_now()
    path_value = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    executable = shutil.which(argv[0], path=path_value)
    if executable is None:
        completed_at = _utc_now()
        raw = f"unable to resolve executable {argv[0]!r}\n".encode()
        log = _command_log(argv, raw, 127, started, completed_at)
        return CapturedCommand(argv, started, completed_at, 127, raw, log)
    executable_path = pathlib.Path(executable).resolve()
    if not executable_path.is_file():
        raise CaptureError(f"quality executable is not a regular file: {executable_path}")
    executable_identity = {
        "bytes": str(executable_path.stat().st_size),
        "path": str(executable_path),
        "sha256": _sha256(executable_path.read_bytes()),
    }
    temporary_home = pathlib.Path(tempfile.mkdtemp(prefix="bench-cleanser-quality-home."))
    environment = {
        "CI": "1",
        "HOME": str(temporary_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "PATH": path_value,
        "PYTHONHASHSEED": "0",
        "PYTHONUNBUFFERED": "1",
        "TERM": "dumb",
        "XDG_CACHE_HOME": str(temporary_home / "cache"),
        "XDG_CONFIG_HOME": str(temporary_home / "config"),
    }
    try:
        try:
            completed = subprocess.run(
                [str(executable_path), *argv[1:]],
                cwd=root,
                env=environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            completed_at = _utc_now()
            raw = f"unable to execute {argv[0]}: {exc}\n".encode()
            log = _command_log(
                argv,
                raw,
                127,
                started,
                completed_at,
                executable_identity=executable_identity,
            )
            return CapturedCommand(argv, started, completed_at, 127, raw, log)
    finally:
        shutil.rmtree(temporary_home, ignore_errors=True)
    completed_at = _utc_now()
    raw_output = completed.stdout
    if len(raw_output) > MAX_LOG_BYTES:
        raise CaptureError(f"{' '.join(argv)} output exceeds the log limit")
    log_output = _command_log(
        argv,
        raw_output,
        completed.returncode,
        started,
        completed_at,
        executable_identity=executable_identity,
    )
    return CapturedCommand(
        argv=argv,
        started_at=started,
        completed_at=completed_at,
        return_code=completed.returncode,
        raw_output=raw_output,
        log_output=log_output,
    )


def _command_log(
    argv: Sequence[str],
    raw: bytes,
    return_code: int,
    started_at: str,
    completed_at: str,
    *,
    executable_identity: Mapping[str, str] | None = None,
) -> bytes:
    identity = {} if executable_identity is None else dict(executable_identity)
    header = (
        f"capture_started_at={started_at}\n"
        f"command_argv_json={json.dumps(list(argv), separators=(',', ':'))}\n"
        f"executable_identity_json={json.dumps(identity, separators=(',', ':'), sort_keys=True)}\n"
        "command_output_begin\n"
    ).encode()
    separator = b"" if not raw or raw.endswith(b"\n") else b"\n"
    footer = (
        "command_output_end\n"
        f"return_code={return_code}\n"
        f"capture_completed_at={completed_at}\n"
    ).encode()
    return header + raw + separator + footer


def _tracked_python_count(root: pathlib.Path, prefix: str | None = None) -> int:
    paths = _run_git(root, "ls-files", "*.py").splitlines()
    if prefix is not None:
        paths = [path for path in paths if path.startswith(prefix)]
    return max(len(paths), 1)


def parse_pytest_summary(output: bytes) -> tuple[dict[str, int], bool]:
    text = output.decode("utf-8", errors="replace")
    summary_lines = [
        line
        for line in text.splitlines()
        if _PYTEST_TOKEN_RE.search(line) is not None and " in " in line
    ]
    if not summary_lines:
        return {"collected": 1, "errors": 1, "failed": 0, "passed": 0, "skipped": 0}, False
    counts: dict[str, int] = {}
    for match in _PYTEST_TOKEN_RE.finditer(summary_lines[-1]):
        key = match.group("kind")
        if key == "error":
            key = "errors"
        counts[key] = counts.get(key, 0) + int(match.group("count"))
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    skipped = counts.get("skipped", 0)
    errors = counts.get("errors", 0)
    unsupported = sum(counts.get(key, 0) for key in ("xfailed", "xpassed", "deselected"))
    collected = passed + failed + skipped + errors + unsupported
    if collected < 1:
        return {"collected": 1, "errors": 1, "failed": 0, "passed": 0, "skipped": 0}, False
    if unsupported:
        errors += unsupported
    valid = failed == 0 and errors == 0 and passed > 0 and passed + skipped == collected
    return {
        "collected": collected,
        "errors": errors,
        "failed": failed,
        "passed": passed,
        "skipped": skipped,
    }, valid


def parse_coverage_summary(output: bytes) -> tuple[dict[str, int | float], bool]:
    text = output.decode("utf-8", errors="replace")
    matches = list(_COVERAGE_TOTAL_RE.finditer(text))
    measured_files = sum(
        1
        for line in text.splitlines()
        if line.startswith("bench_cleanser/") and re.search(r"[0-9]+(?:\.[0-9]+)?%\s*$", line)
    )
    if len(matches) != 1 or measured_files < 1:
        return {
            "measured_files": max(measured_files, 1),
            "minimum_percent": MINIMUM_COVERAGE,
            "percent": 0.0,
        }, False
    percent = float(matches[0].group("percent"))
    return {
        "measured_files": measured_files,
        "minimum_percent": MINIMUM_COVERAGE,
        "percent": percent,
    }, percent >= MINIMUM_COVERAGE


def parse_lint_summary(
    output: bytes,
    return_code: int,
    checked_files: int,
) -> tuple[dict[str, int | str], bool]:
    text = output.decode("utf-8", errors="replace")
    match = re.search(r"Found ([0-9]+) errors?", text)
    errors = 0 if return_code == 0 else int(match.group(1)) if match else 1
    valid = return_code == 0 and "All checks passed!" in text
    return {"checked_files": checked_files, "errors": errors, "tool": "ruff"}, valid


def parse_type_summary(
    output: bytes,
    return_code: int,
    fallback_checked_files: int,
) -> tuple[dict[str, int | str], bool]:
    text = output.decode("utf-8", errors="replace")
    success = re.search(r"Success: no issues found in ([0-9]+) source files?", text)
    failure = re.search(r"Found ([0-9]+) errors? in ([0-9]+) files?", text)
    checked = int(success.group(1)) if success else int(failure.group(2)) if failure else fallback_checked_files
    errors = 0 if success and return_code == 0 else int(failure.group(1)) if failure else 1
    valid = return_code == 0 and success is not None
    return {"checked_files": max(checked, 1), "errors": errors, "tool": "mypy"}, valid


def _gate_record(
    *,
    kind: str,
    source: SourceIdentity,
    capture: CapturedCommand,
    summary: Mapping[str, Any],
    summary_valid: bool,
    log_name: str,
) -> dict[str, Any]:
    return {
        "command": list(capture.argv),
        "completed_at": capture.completed_at,
        "kind": kind,
        "log": {
            "bytes": len(capture.log_output),
            "relative_path": log_name,
            "sha256": _sha256(capture.log_output),
        },
        "platform": _platform_record(),
        "result": {
            "exit_code": capture.return_code,
            "status": "pass" if capture.return_code == 0 and summary_valid else "fail",
            "summary": dict(summary),
        },
        "schema_version": GATE_SCHEMA_VERSION,
        "source": dataclasses.asdict(source),
        "started_at": capture.started_at,
    }


def _write_new(path: pathlib.Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CaptureError(f"output already exists: {path}") from exc


def capture_quality(root: pathlib.Path, output: pathlib.Path) -> bool:
    source = inspect_source(root)
    if output.exists() or output.is_symlink():
        raise CaptureError("quality output directory already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = pathlib.Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    all_passed = True
    try:
        lint = _run_command(QUALITY_COMMANDS["lint"], root)
        type_check = _run_command(QUALITY_COMMANDS["type"], root)
        pytest_capture = _run_command(QUALITY_COMMANDS["pytest"], root)
        for name, capture in (
            ("lint.log", lint),
            ("type.log", type_check),
            ("pytest.log", pytest_capture),
        ):
            _write_new(temporary / name, capture.log_output)
            sys.stdout.buffer.write(capture.log_output)
            sys.stdout.buffer.flush()

        lint_summary, lint_valid = parse_lint_summary(
            lint.raw_output,
            lint.return_code,
            _tracked_python_count(root),
        )
        type_summary, type_valid = parse_type_summary(
            type_check.raw_output,
            type_check.return_code,
            _tracked_python_count(root, "bench_cleanser/"),
        )
        test_summary, test_valid = parse_pytest_summary(pytest_capture.raw_output)
        coverage_summary, coverage_valid = parse_coverage_summary(pytest_capture.raw_output)
        records = {
            "coverage": _gate_record(
                kind="coverage",
                source=source,
                capture=pytest_capture,
                summary=coverage_summary,
                summary_valid=coverage_valid,
                log_name="pytest.log",
            ),
            "lint": _gate_record(
                kind="lint",
                source=source,
                capture=lint,
                summary=lint_summary,
                summary_valid=lint_valid,
                log_name="lint.log",
            ),
            "test": _gate_record(
                kind="test",
                source=source,
                capture=pytest_capture,
                summary=test_summary,
                summary_valid=test_valid,
                log_name="pytest.log",
            ),
            "type": _gate_record(
                kind="type",
                source=source,
                capture=type_check,
                summary=type_summary,
                summary_valid=type_valid,
                log_name="type.log",
            ),
        }
        for kind, record in records.items():
            _write_new(temporary / f"{kind}.json", _canonical_json_bytes(record))
            all_passed = all_passed and record["result"]["status"] == "pass"
        if inspect_source(root) != source:
            raise CaptureError("source identity or worktree changed during quality capture")
        os.rename(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return all_passed


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _report_hashes(item: Mapping[str, Any], field: str) -> list[str]:
    download = _object(item.get("download_info"), f"{field}.download_info")
    archive = _object(download.get("archive_info"), f"{field}.archive_info")
    hashes_value = archive.get("hashes")
    hashes: list[str] = []
    if hashes_value is not None:
        hashes_object = _object(hashes_value, f"{field}.archive_info.hashes")
        sha = hashes_object.get("sha256")
        if sha is not None:
            hashes.append(_string(sha, f"{field}.archive_info.hashes.sha256", _SHA256_RE))
    legacy = archive.get("hash")
    if legacy is not None:
        legacy_value = _string(legacy, f"{field}.archive_info.hash")
        if legacy_value.startswith("sha256="):
            hashes.append(_string(legacy_value[7:], f"{field}.archive_info.hash", _SHA256_RE))
    result = sorted(set(hashes))
    if len(result) != 1:
        raise CaptureError(f"{field} must have exactly one consistent SHA-256 archive identity")
    return result


def _target_python_identity(python: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    if python.is_symlink():
        # Venv interpreter symlinks are normal; the resolved target still has
        # to be executable and the subprocess supplies the authoritative data.
        python = python.resolve()
    try:
        completed = subprocess.run(
            [
                str(python),
                "-c",
                (
                    "import json,platform; "
                    "print(json.dumps({'platform':{'os':platform.system(),"
                    "'architecture':platform.machine()},'python':{"
                    "'implementation':platform.python_implementation(),"
                    "'version':platform.python_version()}},sort_keys=True))"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        decoded = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise CaptureError("target Python identity query failed") from exc
    identity = _object(decoded, "target Python identity")
    platform_value = _object(identity.get("platform"), "target platform")
    python_value = _object(identity.get("python"), "target Python")
    return (
        {
            "architecture": _string(platform_value.get("architecture"), "target architecture"),
            "os": _string(platform_value.get("os"), "target OS"),
        },
        {
            "implementation": _string(
                python_value.get("implementation"), "target implementation"
            ),
            "version": _string(python_value.get("version"), "target Python version"),
        },
    )


def _target_package_identities(python: pathlib.Path) -> set[tuple[str, str]]:
    query = (
        "import importlib.metadata,json; "
        "print(json.dumps(sorted([[d.metadata['Name'],d.version] "
        "for d in importlib.metadata.distributions()])))"
    )
    try:
        completed = subprocess.run(
            [str(python), "-c", query],
            check=True,
            capture_output=True,
            text=True,
        )
        decoded = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise CaptureError("target installed-package query failed") from exc
    rows = _array(decoded, "target installed packages")
    identities: set[tuple[str, str]] = set()
    for index, raw in enumerate(rows):
        row = _array(raw, f"target installed packages[{index}]")
        if len(row) != 2:
            raise CaptureError("target installed package row must contain name and version")
        identity = (
            _normalized_name(_string(row[0], f"target package {index} name")),
            _string(row[1], f"target package {index} version"),
        )
        if identity in identities:
            raise CaptureError("target installed packages contain duplicate identities")
        identities.add(identity)
    return identities


def capture_environment(
    *,
    root: pathlib.Path,
    pip_report: pathlib.Path,
    inventory: pathlib.Path,
    wheel: pathlib.Path,
    sdist: pathlib.Path,
    target_python: pathlib.Path,
    output: pathlib.Path,
) -> dict[str, Any]:
    source = inspect_source(root)
    report_value, _ = _load_json(pip_report, "pip installation report")
    report = _object(report_value, "pip installation report")
    _exact_fields(
        report,
        {"environment", "install", "pip_version", "version"},
        "pip installation report",
    )
    if report["version"] != "1":
        raise CaptureError("unsupported pip installation-report version")
    _string(report["pip_version"], "pip installation report.pip_version")
    report_environment = _object(
        report["environment"],
        "pip installation report.environment",
    )
    installs = _array(report.get("install"), "pip installation report.install")
    packages: dict[tuple[str, str], list[str]] = {}
    display_names: dict[tuple[str, str], str] = {}
    for index, raw in enumerate(installs):
        field = f"pip installation report.install[{index}]"
        item = _object(raw, field)
        metadata = _object(item.get("metadata"), f"{field}.metadata")
        name = _string(metadata.get("name"), f"{field}.metadata.name")
        version = _string(metadata.get("version"), f"{field}.metadata.version")
        identity = (_normalized_name(name), version)
        if identity in packages:
            raise CaptureError("pip installation report contains duplicate packages")
        packages[identity] = _report_hashes(item, field)
        display_names[identity] = name

    inventory_value, _ = _load_json(inventory, "license inventory")
    inventory_rows = _array(inventory_value, "license inventory")
    inventory_identities: set[tuple[str, str]] = set()
    for index, raw in enumerate(inventory_rows):
        item = _object(raw, f"license inventory[{index}]")
        name = _string(item.get("Name"), f"license inventory[{index}].Name")
        version = _string(item.get("Version"), f"license inventory[{index}].Version")
        identity = (_normalized_name(name), version)
        if identity in inventory_identities:
            raise CaptureError("license inventory contains duplicate packages")
        inventory_identities.add(identity)
        if identity in display_names:
            display_names[identity] = name
    if set(packages) != inventory_identities:
        missing = sorted(inventory_identities - set(packages))
        unknown = sorted(set(packages) - inventory_identities)
        raise CaptureError(
            f"pip report and inventory package sets differ: missing={missing}, unknown={unknown}"
        )

    if any(path.is_symlink() or not path.is_file() for path in (wheel, sdist)):
        raise CaptureError("wheel and sdist must be regular non-symlink files")
    wheel_payload = wheel.read_bytes()
    sdist_payload = sdist.read_bytes()
    wheel_sha = _sha256(wheel_payload)
    root_rows = [identity for identity in packages if identity[0] == "bench-cleanser"]
    if len(root_rows) != 1 or wheel_sha not in packages[root_rows[0]]:
        raise CaptureError("pip report does not bind the exact bench-cleanser wheel")
    target_platform, target_runtime = _target_python_identity(target_python)
    if target_platform["os"].lower() != "linux":
        raise CaptureError("release environment lock must describe Linux")
    if target_runtime["implementation"] != "CPython":
        raise CaptureError("release environment lock must describe CPython")
    expected_report_environment = {
        "implementation_name": "cpython",
        "platform_machine": target_platform["architecture"],
        "platform_python_implementation": target_runtime["implementation"],
        "platform_system": target_platform["os"],
        "python_full_version": target_runtime["version"],
    }
    for field, expected in expected_report_environment.items():
        if report_environment.get(field) != expected:
            raise CaptureError(
                f"pip report environment {field!r} differs from target Python"
            )
    installed_identities = _target_package_identities(target_python)
    if installed_identities != set(packages):
        raise CaptureError("target installed package set differs from pip report")
    lock = {
        "packages": [
            {
                "hashes": packages[identity],
                "name": display_names[identity],
                "version": identity[1],
            }
            for identity in sorted(packages)
        ],
        "platform": target_platform,
        "python": target_runtime,
        "schema_version": ENVIRONMENT_SCHEMA_VERSION,
        "source": {
            "commit": source.commit,
            "sdist_sha256": _sha256(sdist_payload),
            "tree": source.tree,
            "wheel_sha256": wheel_sha,
        },
    }
    _write_new(output, _canonical_json_bytes(lock))
    return lock


def _quality_matrix_evidence(
    directory: pathlib.Path,
    source: SourceIdentity,
) -> dict[str, Any]:
    expected_files = {
        "coverage.json",
        "lint.json",
        "lint.log",
        "pytest.log",
        "test.json",
        "type.json",
        "type.log",
    }
    if directory.is_symlink() or not directory.is_dir():
        raise CaptureError("quality evidence must be a non-symlink directory")
    actual_files = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }
    if any(path.is_symlink() for path in directory.rglob("*")):
        raise CaptureError("quality evidence cannot contain symlinks")
    if actual_files != expected_files:
        raise CaptureError("quality evidence file set differs")
    identities = []
    platform_identity: tuple[str, str, str] | None = None
    expected_commands = {
        "coverage": QUALITY_COMMANDS["pytest"],
        "lint": QUALITY_COMMANDS["lint"],
        "test": QUALITY_COMMANDS["pytest"],
        "type": QUALITY_COMMANDS["type"],
    }
    for kind in ("coverage", "lint", "test", "type"):
        record_value, record_payload = _load_json(
            directory / f"{kind}.json",
            f"{kind} quality evidence",
        )
        if record_payload != _canonical_json_bytes(record_value):
            raise CaptureError(f"{kind} quality evidence is not canonical JSON")
        record = _object(record_value, f"{kind} quality evidence")
        _exact_fields(
            record,
            {
                "command",
                "completed_at",
                "kind",
                "log",
                "platform",
                "result",
                "schema_version",
                "source",
                "started_at",
            },
            f"{kind} quality evidence",
        )
        if record["schema_version"] != GATE_SCHEMA_VERSION or record["kind"] != kind:
            raise CaptureError(f"{kind} quality evidence identity differs")
        source_value = _object(record["source"], f"{kind} quality source")
        if source_value != dataclasses.asdict(source):
            raise CaptureError(f"{kind} quality evidence source differs")
        command = _array(record["command"], f"{kind} quality command")
        if tuple(command) != expected_commands[kind]:
            raise CaptureError(f"{kind} quality command differs")
        platform_value = _object(record["platform"], f"{kind} quality platform")
        _exact_fields(
            platform_value,
            {"architecture", "os", "python_version"},
            f"{kind} quality platform",
        )
        current_platform = (
            _string(platform_value["os"], f"{kind} quality OS"),
            _string(platform_value["architecture"], f"{kind} quality architecture"),
            _string(platform_value["python_version"], f"{kind} quality Python"),
        )
        if current_platform[0].lower() != "linux":
            raise CaptureError("quality matrix evidence must come from Linux")
        if platform_identity is None:
            platform_identity = current_platform
        elif platform_identity != current_platform:
            raise CaptureError("quality records disagree on platform identity")
        result = _object(record["result"], f"{kind} quality result")
        if result.get("exit_code") != 0 or result.get("status") != "pass":
            raise CaptureError(f"{kind} quality evidence did not pass")
        log = _object(record["log"], f"{kind} quality log")
        _exact_fields(log, {"bytes", "relative_path", "sha256"}, f"{kind} quality log")
        log_name = _string(log["relative_path"], f"{kind} quality log path")
        if "/" in log_name or "\\" in log_name or log_name not in expected_files:
            raise CaptureError(f"{kind} quality log path is not confined")
        log_path = directory / log_name
        log_payload = log_path.read_bytes()
        if (
            len(log_payload) != _integer(log["bytes"], f"{kind} quality log bytes", minimum=1)
            or _sha256(log_payload)
            != _string(log["sha256"], f"{kind} quality log digest", _SHA256_RE)
        ):
            raise CaptureError(f"{kind} quality log identity differs")
    assert platform_identity is not None
    for relative in sorted(expected_files):
        payload = (directory / relative).read_bytes()
        identities.append({
            "bytes": len(payload),
            "logical_path": relative,
            "sha256": _sha256(payload),
        })
    full_version = platform_identity[2]
    components = full_version.split(".")
    if len(components) < 2 or not all(part.isdigit() for part in components):
        raise CaptureError("quality Python version is not canonical")
    return {
        "files": identities,
        "platform": {
            "architecture": platform_identity[1],
            "os": platform_identity[0],
            "python_full_version": full_version,
        },
        "python_version": ".".join(components[:2]),
    }


def _artifact_report_digest(
    path: pathlib.Path,
    wheel: pathlib.Path,
    sdist: pathlib.Path,
) -> str:
    value, payload = _load_json(path, "artifact audit report")
    report = _object(value, "artifact audit report")
    _exact_fields(
        report,
        {
            "artifacts",
            "automation_result",
            "custom_findings",
            "detect_secrets",
            "policy_sha256",
        },
        "artifact audit report",
    )
    if report["automation_result"] != "pass" or report["custom_findings"] != []:
        raise CaptureError("artifact audit report did not pass")
    detect_secrets = _object(report["detect_secrets"], "artifact detect-secrets report")
    if detect_secrets.get("findings") != []:
        raise CaptureError("artifact audit report contains secret findings")
    expected = {
        wheel.name: _sha256(wheel.read_bytes()),
        sdist.name: _sha256(sdist.read_bytes()),
    }
    observed: dict[str, str] = {}
    for index, raw in enumerate(_array(report["artifacts"], "artifact report artifacts")):
        artifact = _object(raw, f"artifact report artifacts[{index}]")
        name = _string(artifact.get("name"), f"artifact report artifact {index} name")
        digest = _string(
            artifact.get("sha256"),
            f"artifact report artifact {index} digest",
            _SHA256_RE,
        )
        if name in observed:
            raise CaptureError("artifact audit report contains duplicate artifacts")
        observed[name] = digest
    if observed != expected:
        raise CaptureError("artifact audit report does not bind the supplied wheel and sdist")
    return _sha256(payload)


def capture_linux_ci(
    *,
    root: pathlib.Path,
    artifact_directory: pathlib.Path,
    artifact_report: pathlib.Path,
    repository: str,
    run_id: int,
    run_attempt: int,
    quality_evidence_directories: Sequence[pathlib.Path],
    output: pathlib.Path,
) -> dict[str, Any]:
    source = inspect_source(root)
    if platform.system().lower() != "linux":
        raise CaptureError("Linux CI evidence can only be emitted on a Linux runner")
    repository = _string(repository, "repository", _REPOSITORY_RE)
    run_id = _integer(run_id, "run_id", minimum=1)
    run_attempt = _integer(run_attempt, "run_attempt", minimum=1)
    if len(quality_evidence_directories) != 2:
        raise CaptureError("Linux CI evidence requires exactly two quality-matrix receipts")
    matrix_evidence = sorted(
        (_quality_matrix_evidence(path, source) for path in quality_evidence_directories),
        key=lambda item: item["python_version"],
    )
    versions = [item["python_version"] for item in matrix_evidence]
    if versions != ["3.11", "3.12"]:
        raise CaptureError("quality evidence must cover exactly Python 3.11 and 3.12")
    matrix_architectures = {item["platform"]["architecture"] for item in matrix_evidence}
    if len(matrix_architectures) != 1 or platform.machine() not in matrix_architectures:
        raise CaptureError("quality and aggregation runner architectures differ")
    github_context = {
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "job": os.environ.get("GITHUB_JOB"),
        "ref": os.environ.get("GITHUB_REF"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "runner_os": os.environ.get("RUNNER_OS"),
        "sha": os.environ.get("GITHUB_SHA"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
        "workflow_sha": os.environ.get("GITHUB_WORKFLOW_SHA"),
    }
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CaptureError("Linux CI evidence requires the GitHub Actions environment")
    if os.environ.get("GITHUB_REPOSITORY") != repository:
        raise CaptureError("GITHUB_REPOSITORY differs from requested repository")
    if os.environ.get("GITHUB_RUN_ID") != str(run_id):
        raise CaptureError("GITHUB_RUN_ID differs from requested run")
    if os.environ.get("GITHUB_RUN_ATTEMPT") != str(run_attempt):
        raise CaptureError("GITHUB_RUN_ATTEMPT differs from requested attempt")
    if github_context["sha"] != source.commit:
        raise CaptureError("GITHUB_SHA differs from checked-out source")
    workflow_prefix = f"{repository}/.github/workflows/ci.yml@"
    if not isinstance(github_context["workflow_ref"], str) or not github_context[
        "workflow_ref"
    ].startswith(workflow_prefix):
        raise CaptureError("GITHUB_WORKFLOW_REF does not name this CI workflow")
    if not isinstance(github_context["workflow_sha"], str) or _GIT_OID_RE.fullmatch(
        github_context["workflow_sha"]
    ) is None:
        raise CaptureError("GITHUB_WORKFLOW_SHA is not a full Git identity")
    for field in ("event_name", "job", "ref", "runner_arch", "runner_os", "workflow"):
        _string(github_context[field], f"GitHub {field}")
    if os.environ.get("RUNNER_OS", "").lower() != "linux":
        raise CaptureError("RUNNER_OS is not Linux")
    wheels = sorted(artifact_directory.glob("*.whl"))
    sdists = sorted(artifact_directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise CaptureError("artifact directory must contain exactly one wheel and one sdist")
    wheel = wheels[0]
    sdist = sdists[0]
    if any(path.is_symlink() or not path.is_file() for path in (wheel, sdist, artifact_report)):
        raise CaptureError("release artifacts must be regular non-symlink files")
    artifact_report_sha256 = _artifact_report_digest(artifact_report, wheel, sdist)
    record = {
        "completed_at": _utc_now(),
        "conclusion": "success",
        "provider": "github-actions",
        "github_context": github_context,
        "matrix_evidence": matrix_evidence,
        "release_artifacts": {
            "artifact_report_sha256": artifact_report_sha256,
            "sdist_sha256": _sha256(sdist.read_bytes()),
            "wheel_sha256": _sha256(wheel.read_bytes()),
        },
        "repository": repository,
        "run_attempt": run_attempt,
        "run_id": run_id,
        "run_url": f"https://github.com/{repository}/actions/runs/{run_id}",
        "runner": {
            "architecture": platform.machine(),
            "os": platform.system(),
            "python_versions": versions,
        },
        "schema_version": LINUX_CI_SCHEMA_VERSION,
        "source": dataclasses.asdict(source),
        "workflow": ".github/workflows/ci.yml",
    }
    _write_new(output, _canonical_json_bytes(record))
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    quality = subparsers.add_parser("quality")
    quality.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    quality.add_argument("--output", type=pathlib.Path, required=True)

    environment = subparsers.add_parser("environment")
    environment.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    environment.add_argument("--pip-report", type=pathlib.Path, required=True)
    environment.add_argument("--inventory", type=pathlib.Path, required=True)
    environment.add_argument("--wheel", type=pathlib.Path, required=True)
    environment.add_argument("--sdist", type=pathlib.Path, required=True)
    environment.add_argument("--target-python", type=pathlib.Path, required=True)
    environment.add_argument("--output", type=pathlib.Path, required=True)

    linux = subparsers.add_parser("linux-ci")
    linux.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    linux.add_argument("--artifact-directory", type=pathlib.Path, required=True)
    linux.add_argument("--artifact-report", type=pathlib.Path, required=True)
    linux.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    linux.add_argument("--run-id", type=int, default=os.environ.get("GITHUB_RUN_ID"))
    linux.add_argument("--run-attempt", type=int, default=os.environ.get("GITHUB_RUN_ATTEMPT"))
    linux.add_argument("--quality-evidence", type=pathlib.Path, action="append", required=True)
    linux.add_argument("--output", type=pathlib.Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "quality":
            passed = capture_quality(args.repo_root, args.output)
            result = {"all_quality_gates_passed": passed, "output": str(args.output)}
            exit_code = 0 if passed else 1
        elif args.command == "environment":
            lock = capture_environment(
                root=args.repo_root,
                pip_report=args.pip_report,
                inventory=args.inventory,
                wheel=args.wheel,
                sdist=args.sdist,
                target_python=args.target_python,
                output=args.output,
            )
            result = {"package_count": len(lock["packages"]), "output": str(args.output)}
            exit_code = 0
        else:
            if args.repository is None or args.run_id is None or args.run_attempt is None:
                raise CaptureError("GitHub repository, run ID, and run attempt are required")
            record = capture_linux_ci(
                root=args.repo_root,
                artifact_directory=args.artifact_directory,
                artifact_report=args.artifact_report,
                repository=args.repository,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                quality_evidence_directories=args.quality_evidence,
                output=args.output,
            )
            result = {"run_url": record["run_url"], "output": str(args.output)}
            exit_code = 0
    except (CaptureError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
