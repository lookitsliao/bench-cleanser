"""Contract tests for bounded local evidence acquisition."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote, urlparse

import pytest

import bench_cleanser.verification.acquire as verification_acquire
from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_loads,
)
from bench_cleanser.verification.acquire import (
    ACQUISITION_SCHEMA_VERSION,
    SEMANTIC_OUTPUT_SCHEMA_VERSION,
    AcquisitionRequest,
    SemanticOutput,
    acquire_evidence,
    decode_semantic_output,
    load_acquisition_request,
    main,
)
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
)


def _request(
    workspace: pathlib.Path,
    argv: tuple[str, ...],
    *,
    kind: EvidenceKind = EvidenceKind.STATIC,
    working_directory: str = ".",
    timeout_seconds: float = 2.0,
    max_capture_bytes: int = 8192,
) -> AcquisitionRequest:
    return AcquisitionRequest(
        kind=kind,
        source="fixture-runner",
        source_version="1.2.3",
        workspace_root=str(workspace),
        working_directory=working_directory,
        argv=argv,
        timeout_seconds=timeout_seconds,
        max_capture_bytes=max_capture_bytes,
        supports_incorrect_exit_codes=(
            () if kind == EvidenceKind.SEMANTIC else (1,)
        ),
    )


def _artifact_path(observation: EvidenceObservation) -> pathlib.Path:
    locator = observation.metadata["artifact_locator"]
    assert isinstance(locator, str)
    parsed = urlparse(locator)
    assert parsed.scheme == "file"
    return pathlib.Path(unquote(parsed.path))


def _load_artifact(observation: EvidenceObservation) -> tuple[pathlib.Path, dict]:
    path = _artifact_path(observation)
    artifact_bytes = path.read_bytes()
    assert hashlib.sha256(artifact_bytes).hexdigest() == observation.metadata[
        "artifact_sha256"
    ]
    assert len(artifact_bytes) == observation.cost.storage_bytes
    return path, json.loads(artifact_bytes)


def _semantic_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SEMANTIC_OUTPUT_SCHEMA_VERSION,
        "status": "supports_correct",
        "candidate_probability": 0.82,
        "calibrated_risk_upper_bound": 0.18,
        "calibration_id": "fixture-calibration-v1",
        "verifier_validity": 0.91,
        "privileged_inputs": ["issue_text"],
        "cost": {
            "input_tokens": 120,
            "output_tokens": 15,
            "usd": 0.004,
        },
    }
    payload.update(updates)
    return payload


def _semantic_argv(
    stdout: bytes,
    *,
    stderr: bytes = b"",
    exit_code: int = 0,
) -> tuple[str, ...]:
    script = (
        "import base64,sys; "
        "sys.stdout.buffer.write(base64.b64decode(sys.argv[1])); "
        "sys.stderr.buffer.write(base64.b64decode(sys.argv[2])); "
        "raise SystemExit(int(sys.argv[3]))"
    )
    return (
        sys.executable,
        "-c",
        script,
        base64.b64encode(stdout).decode("ascii"),
        base64.b64encode(stderr).decode("ascii"),
        str(exit_code),
    )


def test_atomic_write_preserves_exact_utf8_bytes(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "exact.txt"
    content = "alpha\n雪\nomega\n"

    atomic_write(output, content)

    assert output.read_bytes() == content.encode("utf-8")


def test_success_is_non_authoritative_bounded_and_does_not_inherit_secrets(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "should-never-reach-the-acquisition-child"
    monkeypatch.setenv("BENCH_CLEANSER_TEST_SECRET", secret)
    script = (
        "import json, os, sys; "
        "print(json.dumps(dict(os.environ), sort_keys=True)); "
        "sys.stderr.write('diagnostic\\n')"
    )

    observation = acquire_evidence(
        _request(tmp_path, (sys.executable, "-c", script)),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.SUPPORTS_CORRECT
    assert observation.kind == EvidenceKind.STATIC
    assert observation.source == "fixture-runner"
    assert observation.source_version == "1.2.3"
    assert observation.acquisition_id.startswith("acq-")
    assert observation.authoritative is False
    assert observation.cost.wall_seconds > 0
    assert observation.cost.cpu_seconds == 0
    assert observation.metadata["measured_cost_dimensions"] == (
        "wall_seconds",
        "storage_bytes",
    )

    path, artifact = _load_artifact(observation)
    assert path.name == f"{observation.acquisition_id}.json"
    assert artifact["acquisition_id"] == observation.acquisition_id
    assert artifact["runner"] == {
        "name": "bench-cleanser-acquire",
        "version": observation.metadata["runner_version"],
    }
    assert artifact["execution"]["outcome"] == "supports_correct"
    assert artifact["execution"]["return_code"] == 0
    assert artifact["execution"]["shell"] is False
    assert artifact["execution"]["sandbox"] == "not_provided"
    assert "BENCH_CLEANSER_TEST_SECRET" not in artifact["execution"][
        "supplied_environment_keys"
    ]
    assert secret not in artifact["stdout"]["text"]
    child_environment = json.loads(artifact["stdout"]["text"])
    assert "BENCH_CLEANSER_TEST_SECRET" not in child_environment
    assert artifact["stderr"]["text"] == "diagnostic\n"


@pytest.mark.parametrize(
    ("exit_code", "expected_status", "expected_outcome"),
    [
        (1, EvidenceStatus.SUPPORTS_INCORRECT, "supports_incorrect"),
        (2, EvidenceStatus.INCONCLUSIVE, "unmapped_exit"),
    ],
)
def test_exit_mapping_distinguishes_candidate_failure_from_verifier_failure(
    tmp_path: pathlib.Path,
    exit_code: int,
    expected_status: EvidenceStatus,
    expected_outcome: str,
) -> None:
    observation = acquire_evidence(
        _request(
            tmp_path,
            (sys.executable, "-c", f"raise SystemExit({exit_code})"),
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == expected_status
    assert observation.authoritative is False
    _, artifact = _load_artifact(observation)
    assert artifact["execution"]["outcome"] == expected_outcome
    assert artifact["execution"]["return_code"] == exit_code
    if expected_status == EvidenceStatus.INCONCLUSIVE:
        assert observation.verifier_validity == 0.0
        assert observation.candidate_probability is None


def test_missing_executable_is_an_auditable_inconclusive_setup_failure(
    tmp_path: pathlib.Path,
) -> None:
    observation = acquire_evidence(
        _request(tmp_path, ("__bench_cleanser_missing_executable__",)),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.INCONCLUSIVE
    assert observation.verifier_validity == 0.0
    assert observation.candidate_probability is None
    _, artifact = _load_artifact(observation)
    assert artifact["execution"]["outcome"] == "setup_failure"
    assert artifact["execution"]["return_code"] is None
    assert "FileNotFoundError" in artifact["execution"]["setup_error"]


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    state = result.stdout.strip()
    return result.returncode == 0 and bool(state) and not state.startswith("Z")


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group assertion")
def test_wall_timeout_kills_descendant_process_group(tmp_path: pathlib.Path) -> None:
    pid_path = tmp_path / "child.pid"
    child_script = "import time; time.sleep(30)"
    parent_script = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', sys.argv[1]]); "
        "pathlib.Path(sys.argv[2]).write_text(str(child.pid)); "
        "time.sleep(30)"
    )
    observation = acquire_evidence(
        _request(
            tmp_path,
            (
                sys.executable,
                "-c",
                parent_script,
                child_script,
                str(pid_path),
            ),
            timeout_seconds=0.4,
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.INCONCLUSIVE
    _, artifact = _load_artifact(observation)
    assert artifact["execution"]["outcome"] == "timeout"
    assert artifact["execution"]["timed_out"] is True
    assert observation.cost.wall_seconds < 2.5

    child_pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 1.0
    while _pid_is_running(child_pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    try:
        assert not _pid_is_running(child_pid)
    finally:
        if _pid_is_running(child_pid):
            os.kill(child_pid, signal.SIGKILL)


def test_stdout_and_stderr_are_drained_but_storage_is_truncated(
    tmp_path: pathlib.Path,
) -> None:
    script = (
        "import sys; "
        "sys.stdout.write('A' * 200000); "
        "sys.stderr.write('B' * 180000)"
    )
    observation = acquire_evidence(
        _request(
            tmp_path,
            (sys.executable, "-c", script),
            max_capture_bytes=32,
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.SUPPORTS_CORRECT
    assert observation.metadata["stdout_truncated"] is True
    assert observation.metadata["stderr_truncated"] is True
    _, artifact = _load_artifact(observation)
    for stream_name, expected_total, character in (
        ("stdout", 200000, "A"),
        ("stderr", 180000, "B"),
    ):
        capture = artifact[stream_name]
        assert capture["total_bytes"] == expected_total
        assert capture["captured_bytes"] == 32
        assert capture["truncated"] is True
        assert capture["text"].startswith(character * 16)
        assert capture["text"].endswith(character * 16)


@pytest.mark.parametrize("working_directory", ["../outside", "/tmp"])
def test_working_directory_cannot_escape_declared_workspace(
    tmp_path: pathlib.Path,
    working_directory: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / "outside").mkdir()
    marker = tmp_path / "ran"
    request = _request(
        workspace,
        (sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"),
        working_directory=working_directory,
    )

    with pytest.raises(ValueError, match="working_directory"):
        acquire_evidence(request, artifact_directory=tmp_path / "artifacts")
    assert not marker.exists()


def test_symlinked_working_directory_cannot_escape_workspace(
    tmp_path: pathlib.Path,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    try:
        (workspace / "escape").symlink_to(outside, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - depends on Windows policy
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="escapes workspace_root"):
        acquire_evidence(
            _request(workspace, (sys.executable, "-c", "pass"), working_directory="escape"),
            artifact_directory=tmp_path / "artifacts",
        )


def test_semantic_request_requires_transport_only_exit_contract(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(ValueError, match="transport success only"):
        AcquisitionRequest(
            kind=EvidenceKind.SEMANTIC,
            source="semantic-fixture",
            source_version="1",
            workspace_root=str(tmp_path),
            argv=(sys.executable, "-c", "pass"),
        )
    request = _request(
        tmp_path,
        (sys.executable, "-c", "pass"),
        kind=EvidenceKind.SEMANTIC,
    )
    assert request.supports_correct_exit_codes == (0,)
    assert request.supports_incorrect_exit_codes == ()


def test_semantic_exit_zero_maps_strict_payload_not_exit_code(
    tmp_path: pathlib.Path,
) -> None:
    payload = _semantic_payload(
        status="supports_incorrect",
        candidate_probability=0.12,
        calibrated_risk_upper_bound=0.95,
        privileged_inputs=["issue_text", "reference_patch"],
    )
    raw = (strict_json_dumps(payload) + "\n").encode()
    observation = acquire_evidence(
        _request(
            tmp_path,
            _semantic_argv(raw),
            kind=EvidenceKind.SEMANTIC,
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.kind == EvidenceKind.SEMANTIC
    assert observation.status == EvidenceStatus.SUPPORTS_INCORRECT
    assert observation.authoritative is False
    assert observation.candidate_probability == 0.12
    assert observation.calibrated_risk_upper_bound == 0.95
    assert observation.calibration_id == "fixture-calibration-v1"
    assert observation.verifier_validity == 0.91
    assert observation.privileged_inputs == ("issue_text", "reference_patch")
    assert observation.cost.input_tokens == 120
    assert observation.cost.output_tokens == 15
    assert observation.cost.usd == 0.004
    assert observation.metadata["outcome"] == "semantic_result"
    assert observation.metadata["measured_cost_dimensions"] == (
        "wall_seconds",
        "storage_bytes",
    )
    assert observation.metadata["producer_declared_cost_dimensions"] == (
        "input_tokens",
        "output_tokens",
        "usd",
    )
    assert observation.metadata["producer_declared_semantic_fields"] == (
        "status",
        "candidate_probability",
        "calibrated_risk_upper_bound",
        "calibration_id",
        "verifier_validity",
        "privileged_inputs",
    )

    _, artifact = _load_artifact(observation)
    assert artifact["execution"]["return_code"] == 0
    assert artifact["execution"]["outcome"] == "semantic_result"
    assert artifact["semantic"]["parsed"] == payload
    retained = base64.b64decode(
        artifact["semantic"]["raw_stdout"]["data"],
        validate=True,
    )
    assert retained == raw
    assert hashlib.sha256(retained).hexdigest() == artifact["semantic"][
        "raw_stdout"
    ]["sha256"]


def test_semantic_nonzero_exit_ignores_correctness_payload(
    tmp_path: pathlib.Path,
) -> None:
    raw = (strict_json_dumps(_semantic_payload()) + "\n").encode()
    observation = acquire_evidence(
        _request(
            tmp_path,
            _semantic_argv(raw, exit_code=7),
            kind=EvidenceKind.SEMANTIC,
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.INCONCLUSIVE
    assert observation.candidate_probability is None
    assert observation.calibrated_risk_upper_bound is None
    assert observation.calibration_id == ""
    assert observation.privileged_inputs == ()
    assert observation.verifier_validity == 0.0
    assert observation.cost.input_tokens == 0
    assert observation.metadata["outcome"] == "semantic_nonzero_exit"
    assert observation.metadata["semantic_output_error"] == "nonzero_exit"
    assert observation.metadata["producer_declared_semantic_fields"] == ()
    _, artifact = _load_artifact(observation)
    assert artifact["semantic"]["parsed"] is None
    assert artifact["semantic"]["error_code"] == "nonzero_exit"


@pytest.mark.parametrize(
    ("raw", "expected_error"),
    [
        (b"\xff", "invalid_utf8"),
        (b"not-json", "invalid_json"),
        (
            b'{"schema_version":"0.1.0","schema_version":"0.1.0"}',
            "invalid_json",
        ),
        (
            (strict_json_dumps({**_semantic_payload(), "unknown": True}) + "\n").encode(),
            "invalid_schema",
        ),
    ],
)
def test_invalid_semantic_output_fails_closed_and_preserves_raw(
    tmp_path: pathlib.Path,
    raw: bytes,
    expected_error: str,
) -> None:
    observation = acquire_evidence(
        _request(
            tmp_path,
            _semantic_argv(raw),
            kind=EvidenceKind.SEMANTIC,
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.INCONCLUSIVE
    assert observation.verifier_validity == 0.0
    assert observation.candidate_probability is None
    assert observation.metadata["outcome"] == "semantic_invalid_output"
    assert observation.metadata["semantic_output_error"] == expected_error
    _, artifact = _load_artifact(observation)
    assert base64.b64decode(
        artifact["semantic"]["raw_stdout"]["data"],
        validate=True,
    ) == raw
    assert artifact["semantic"]["parsed"] is None


@pytest.mark.parametrize("truncate_stderr", [False, True])
def test_semantic_stdout_or_stderr_truncation_is_inconclusive(
    tmp_path: pathlib.Path,
    truncate_stderr: bool,
) -> None:
    raw = (strict_json_dumps(_semantic_payload()) + "\n").encode()
    observation = acquire_evidence(
        _request(
            tmp_path,
            _semantic_argv(
                raw,
                stderr=b"diagnostic-that-exceeds-bound" if truncate_stderr else b"",
            ),
            kind=EvidenceKind.SEMANTIC,
            max_capture_bytes=(8 if truncate_stderr else len(raw) - 1),
        ),
        artifact_directory=tmp_path / "artifacts",
    )

    assert observation.status == EvidenceStatus.INCONCLUSIVE
    assert observation.metadata["outcome"] == "semantic_truncated_output"
    assert observation.metadata["semantic_output_error"] == "capture_truncated"
    assert observation.candidate_probability is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.__setitem__("candidate_probability", True),
        lambda value: value.__setitem__("candidate_probability", 1.1),
        lambda value: value.__setitem__("candidate_probability", 0.49),
        lambda value: value.update({
            "status": "supports_incorrect",
            "candidate_probability": 0.51,
        }),
        lambda value: value.__setitem__("calibration_id", ""),
        lambda value: value.__setitem__("privileged_inputs", ["issue", "issue"]),
        lambda value: value.__setitem__("status", "error"),
        lambda value: value["cost"].__setitem__("input_tokens", -1),
        lambda value: value.__setitem__("unknown", True),
    ],
)
def test_semantic_output_schema_rejects_ambiguous_values(
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    payload = _semantic_payload()
    mutation(payload)
    with pytest.raises(ValueError):
        SemanticOutput.from_dict(payload)


def test_semantic_inconclusive_cannot_carry_candidate_scores() -> None:
    payload = _semantic_payload(
        status="inconclusive",
        candidate_probability=0.5,
        calibrated_risk_upper_bound=None,
        calibration_id="",
    )
    with pytest.raises(ValueError, match="inconclusive"):
        SemanticOutput.from_dict(payload)
    decoded, error = decode_semantic_output(
        b'{"schema_version":"0.1.0","schema_version":"0.1.0"}'
    )
    assert decoded is None
    assert error == "invalid_json"


def test_full_execution_replication_is_separate_unique_acquisitions(
    tmp_path: pathlib.Path,
) -> None:
    request = _request(
        tmp_path,
        (sys.executable, "-c", "pass"),
        kind=EvidenceKind.FULL_EXECUTION,
    )

    first = acquire_evidence(request, artifact_directory=tmp_path / "artifacts")
    second = acquire_evidence(request, artifact_directory=tmp_path / "artifacts")

    assert first.acquisition_id != second.acquisition_id
    assert first.metadata["artifact_locator"] != second.metadata["artifact_locator"]
    assert _artifact_path(first).exists()
    assert _artifact_path(second).exists()


def test_preallocated_acquisition_id_is_preserved_and_cannot_be_rerun(
    tmp_path: pathlib.Path,
) -> None:
    acquisition_id = "acq-" + "7" * 32
    calls = tmp_path / "calls"
    script = (
        "import pathlib, sys; "
        "path = pathlib.Path(sys.argv[1]); "
        "path.write_text((path.read_text() if path.exists() else '') + 'x')"
    )
    request = _request(
        tmp_path,
        (sys.executable, "-c", script, str(calls)),
    )

    observation = acquire_evidence(
        request,
        artifact_directory=tmp_path / "artifacts",
        acquisition_id=acquisition_id,
    )
    assert observation.acquisition_id == acquisition_id
    assert calls.read_text(encoding="utf-8") == "x"

    with pytest.raises(FileExistsError, match="artifact already exists"):
        acquire_evidence(
            request,
            artifact_directory=tmp_path / "artifacts",
            acquisition_id=acquisition_id,
        )
    assert calls.read_text(encoding="utf-8") == "x"

    with pytest.raises(ValueError, match="acquisition_id must have the form"):
        acquire_evidence(
            request,
            artifact_directory=tmp_path / "other-artifacts",
            acquisition_id="../../unsafe",
        )


def test_preallocated_id_reservation_prevents_concurrent_execution(
    tmp_path: pathlib.Path,
) -> None:
    acquisition_id = "acq-" + "8" * 32
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / f".{acquisition_id}.lock").write_text(
        acquisition_id + "\n",
        encoding="utf-8",
    )
    marker = tmp_path / "ran"
    request = _request(
        tmp_path,
        (
            sys.executable,
            "-c",
            f"open({str(marker)!r}, 'w').close()",
        ),
    )

    with pytest.raises(FileExistsError, match="already reserved"):
        acquire_evidence(
            request,
            artifact_directory=artifacts,
            acquisition_id=acquisition_id,
        )
    assert not marker.exists()


def test_post_launch_unexpected_exception_terminates_process_leader(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquisition_id = "acq-" + "b" * 32
    artifacts = tmp_path / "artifacts"
    marker = tmp_path / "leaked-process"
    script = (
        "import pathlib, sys, time; "
        "time.sleep(0.3); "
        "pathlib.Path(sys.argv[1]).write_text('leaked')"
    )

    def fail_capture_start(self) -> None:
        raise RuntimeError("fixture post-launch failure")

    monkeypatch.setattr(
        verification_acquire._BoundedCapture,
        "start",
        fail_capture_start,
    )
    with pytest.raises(RuntimeError, match="fixture post-launch failure"):
        acquire_evidence(
            _request(tmp_path, (sys.executable, "-c", script, str(marker))),
            artifact_directory=artifacts,
            acquisition_id=acquisition_id,
        )

    time.sleep(0.5)
    assert not marker.exists()
    assert (artifacts / f".{acquisition_id}.lock").exists()
    assert not (artifacts / f"{acquisition_id}.json").exists()


def test_post_execution_artifact_appearance_is_not_overwritten(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquisition_id = "acq-" + "c" * 32
    artifacts = tmp_path / "artifacts"
    marker = tmp_path / "ran"
    artifact = artifacts / f"{acquisition_id}.json"
    real_link = verification_acquire.os.link

    def racing_link(source, destination, *args, **kwargs):
        pathlib.Path(destination).write_text("contender-owned\n", encoding="utf-8")
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(verification_acquire.os, "link", racing_link)
    with pytest.raises(FileExistsError, match="appeared before publication"):
        acquire_evidence(
            _request(
                tmp_path,
                (
                    sys.executable,
                    "-c",
                    f"open({str(marker)!r}, 'w').close()",
                ),
            ),
            artifact_directory=artifacts,
            acquisition_id=acquisition_id,
        )

    assert marker.exists()
    assert artifact.read_text(encoding="utf-8") == "contender-owned\n"
    assert (artifacts / f".{acquisition_id}.lock").exists()
    assert not list(artifacts.glob(f".{artifact.name}.*.tmp"))


def test_artifact_appearance_race_releases_only_the_owned_reservation(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquisition_id = "acq-" + "9" * 32
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    artifact = artifacts / f"{acquisition_id}.json"
    reservation = artifacts / f".{acquisition_id}.lock"
    real_fsync = verification_acquire.os.fsync
    injected = False

    def create_artifact_after_lock(fd: int) -> None:
        nonlocal injected
        real_fsync(fd)
        if not injected and reservation.exists():
            artifact.write_text("{}\n", encoding="utf-8")
            injected = True

    monkeypatch.setattr(verification_acquire.os, "fsync", create_artifact_after_lock)
    with pytest.raises(FileExistsError, match="appeared while reserving"):
        acquire_evidence(
            _request(tmp_path, (sys.executable, "-c", "pass")),
            artifact_directory=artifacts,
            acquisition_id=acquisition_id,
        )

    assert artifact.read_text(encoding="utf-8") == "{}\n"
    assert not reservation.exists()


def test_unexpected_prelaunch_failure_releases_acquisition_reservation(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquisition_id = "acq-" + "a" * 32
    artifacts = tmp_path / "artifacts"
    marker = tmp_path / "ran"
    request = _request(
        tmp_path,
        (sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"),
    )

    def fail_before_launch() -> str:
        raise RuntimeError("fixture prelaunch failure")

    monkeypatch.setattr(verification_acquire, "_timestamp", fail_before_launch)
    with pytest.raises(RuntimeError, match="fixture prelaunch failure"):
        acquire_evidence(
            request,
            artifact_directory=artifacts,
            acquisition_id=acquisition_id,
        )

    assert not marker.exists()
    assert not (artifacts / f"{acquisition_id}.json").exists()
    assert not (artifacts / f".{acquisition_id}.lock").exists()


def test_strict_request_loader_rejects_duplicate_keys_unknown_fields_and_nan(
    tmp_path: pathlib.Path,
) -> None:
    base = {
        "schema_version": ACQUISITION_SCHEMA_VERSION,
        "kind": "static",
        "source": "fixture",
        "source_version": "1",
        "workspace_root": str(tmp_path),
        "argv": [sys.executable, "-c", "pass"],
    }
    duplicate = json.dumps(base).replace(
        '"kind": "static"',
        '"kind": "static", "kind": "full_execution"',
    )
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        load_acquisition_request(io.StringIO(duplicate))

    with pytest.raises(ValueError, match="unknown fields"):
        AcquisitionRequest.from_dict({**base, "shell": True})

    with pytest.raises(ValueError, match="non-standard JSON constant"):
        load_acquisition_request(
            io.StringIO(json.dumps({**base, "timeout_seconds": float("nan")}))
        )


def test_cli_emits_strict_observation_and_reports_output_failure_cleanly(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            _request(tmp_path, (sys.executable, "-c", "pass")).to_dict()
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "observation.json"
    real_atomic_write = verification_acquire.atomic_write
    calls = 0

    def fail_result_write(path: pathlib.Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("fixture output failure")
        real_atomic_write(path, content)

    monkeypatch.setattr(verification_acquire, "atomic_write", fail_result_write)
    with pytest.raises(
        SystemExit,
        match="evidence acquisition failed: fixture output failure",
    ):
        main([
            str(request_path),
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--output",
            str(output_path),
        ])

    assert calls == 1
    assert not output_path.exists()
    artifact_paths = list((tmp_path / "artifacts").glob("*.json"))
    assert len(artifact_paths) == 1

    monkeypatch.setattr(verification_acquire, "atomic_write", real_atomic_write)
    main([
        str(request_path),
        "--artifact-dir",
        str(tmp_path / "artifacts"),
        "--output",
        str(output_path),
    ])
    decoded = strict_json_loads(output_path.read_text(encoding="utf-8"))
    restored = EvidenceObservation.from_dict(decoded)
    assert restored.status == EvidenceStatus.SUPPORTS_CORRECT


def test_cli_rejects_malformed_request_with_clean_nonzero_failure(
    tmp_path: pathlib.Path,
) -> None:
    request_path = tmp_path / "bad.json"
    request_path.write_text('{"kind":"static","kind":"semantic"}', encoding="utf-8")

    with pytest.raises(SystemExit, match="evidence acquisition failed: invalid JSON"):
        main([
            str(request_path),
            "--artifact-dir",
            str(tmp_path / "artifacts"),
        ])
    assert not (tmp_path / "artifacts").exists()
