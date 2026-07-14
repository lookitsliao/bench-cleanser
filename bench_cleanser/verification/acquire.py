"""Bounded local acquisition of raw verification evidence.

This module is an execution adapter, not a sandbox.  It starts an operator-
supplied argv without a shell, confines the *initial* working directory to a
declared workspace root, excludes arbitrary ambient variables from the child
environment, and records a bounded, digest-bound artifact.  The child
still has the filesystem, network, and operating-system permissions of the
calling user.

Process-tree cleanup is best effort. Deliberately detached descendants are not
contained, and ordinary descendant containment is also not guaranteed on
backends without a process-group or job-object boundary.

Every successful call represents one acquisition.  A preallocated identifier
plus a shared artifact directory provides at-most-once exclusion only for
callers that coordinate on that same path and identifier; it is not a global
CAS or recovery protocol.  Repeated full execution must therefore use separate
calls and separate acquisition identifiers.
The resulting observation is deliberately non-authoritative; source trust and
replicate requirements remain policy decisions in :mod:`router`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import math
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, BinaryIO, TextIO, cast

from bench_cleanser import __version__
from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_load,
    strict_json_loads,
)
from bench_cleanser.verification.models import (
    EvidenceCost,
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
)

ACQUISITION_SCHEMA_VERSION = "0.2.0"
SEMANTIC_OUTPUT_SCHEMA_VERSION = "0.1.0"
SEMANTIC_PRODUCER_DECLARED_FIELDS = (
    "status",
    "candidate_probability",
    "calibrated_risk_upper_bound",
    "calibration_id",
    "verifier_validity",
    "privileged_inputs",
)
DEFAULT_TIMEOUT_SECONDS = 300.0
MAX_TIMEOUT_SECONDS = 3600.0
DEFAULT_CAPTURE_BYTES = 64 * 1024
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
_TERMINATION_GRACE_SECONDS = 0.25
_READ_CHUNK_BYTES = 64 * 1024
_ACQUISITION_ID_RE = re.compile(r"acq-[0-9a-f]{32}")
_RUNNABLE_KINDS = frozenset({
    EvidenceKind.STATIC,
    EvidenceKind.SEMANTIC,
    EvidenceKind.TARGETED_EXECUTION,
    EvidenceKind.FULL_EXECUTION,
    EvidenceKind.ORACLE_HARDENING,
})


def _plain_string(value: Any, field_name: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a JSON string")
    if "\x00" in value:
        raise ValueError(f"{field_name} cannot contain NUL bytes")
    if nonempty and (not value.strip() or value != value.strip()):
        raise ValueError(
            f"{field_name} must be non-empty and have no surrounding whitespace"
        )
    return value


def _positive_number(value: Any, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be a finite positive number")
    return float(value)


def _exit_codes(value: Any, field_name: str, *, required: bool) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array of integers")
    codes: list[int] = []
    for index, item in enumerate(value):
        if (
            isinstance(item, bool)
            or not isinstance(item, int)
            or item < 0
            or item > 2**31 - 1
        ):
            raise ValueError(
                f"{field_name}[{index}] must be an integer between 0 and 2147483647"
            )
        codes.append(item)
    if required and not codes:
        raise ValueError(f"{field_name} cannot be empty")
    if len(codes) != len(set(codes)):
        raise ValueError(f"{field_name} cannot contain duplicate exit codes")
    return tuple(sorted(codes))


@dataclass(frozen=True)
class AcquisitionRequest:
    """Strict operator contract for one local evidence acquisition."""

    kind: EvidenceKind
    source: str
    source_version: str
    workspace_root: str
    argv: tuple[str, ...]
    schema_version: str = ACQUISITION_SCHEMA_VERSION
    working_directory: str = "."
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_capture_bytes: int = DEFAULT_CAPTURE_BYTES
    supports_correct_exit_codes: tuple[int, ...] = (0,)
    supports_incorrect_exit_codes: tuple[int, ...] = (1,)

    def __post_init__(self) -> None:
        if self.schema_version != ACQUISITION_SCHEMA_VERSION:
            raise ValueError(
                "unsupported acquisition schema version "
                f"{self.schema_version!r}; expected {ACQUISITION_SCHEMA_VERSION!r}"
            )
        if not isinstance(self.kind, EvidenceKind) or self.kind not in _RUNNABLE_KINDS:
            allowed = ", ".join(sorted(kind.value for kind in _RUNNABLE_KINDS))
            raise ValueError(f"evidence kind must be one of: {allowed}")
        _plain_string(self.source, "source", nonempty=True)
        _plain_string(self.source_version, "source_version", nonempty=True)
        _plain_string(self.workspace_root, "workspace_root", nonempty=True)
        _plain_string(self.working_directory, "working_directory", nonempty=True)

        if not isinstance(self.argv, (list, tuple)) or not self.argv:
            raise ValueError("argv must be a non-empty sequence of strings")
        normalized_argv = tuple(self.argv)
        for index, item in enumerate(normalized_argv):
            _plain_string(item, f"argv[{index}]", nonempty=index == 0)
        object.__setattr__(self, "argv", normalized_argv)

        timeout = _positive_number(self.timeout_seconds, "timeout_seconds")
        if timeout > MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds cannot exceed {MAX_TIMEOUT_SECONDS:g} seconds"
            )
        object.__setattr__(self, "timeout_seconds", timeout)

        if (
            isinstance(self.max_capture_bytes, bool)
            or not isinstance(self.max_capture_bytes, int)
            or not 1 <= self.max_capture_bytes <= MAX_CAPTURE_BYTES
        ):
            raise ValueError(
                f"max_capture_bytes must be an integer in [1, {MAX_CAPTURE_BYTES}]"
            )

        correct = _exit_codes(
            list(self.supports_correct_exit_codes),
            "supports_correct_exit_codes",
            required=True,
        )
        incorrect = _exit_codes(
            list(self.supports_incorrect_exit_codes),
            "supports_incorrect_exit_codes",
            required=False,
        )
        overlap = set(correct).intersection(incorrect)
        if overlap:
            raise ValueError(
                "supports_correct_exit_codes and supports_incorrect_exit_codes "
                f"must be disjoint; overlap={sorted(overlap)}"
            )
        object.__setattr__(self, "supports_correct_exit_codes", correct)
        object.__setattr__(self, "supports_incorrect_exit_codes", incorrect)
        if self.kind == EvidenceKind.SEMANTIC and (
            correct != (0,) or incorrect
        ):
            raise ValueError(
                "semantic acquisition requires supports_correct_exit_codes=[0] and "
                "supports_incorrect_exit_codes=[]; exit 0 means transport success only"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-native request representation."""

        return {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "source": self.source,
            "source_version": self.source_version,
            "workspace_root": self.workspace_root,
            "working_directory": self.working_directory,
            "argv": list(self.argv),
            "timeout_seconds": self.timeout_seconds,
            "max_capture_bytes": self.max_capture_bytes,
            "supports_correct_exit_codes": list(self.supports_correct_exit_codes),
            "supports_incorrect_exit_codes": list(
                self.supports_incorrect_exit_codes
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> AcquisitionRequest:
        """Build a request while rejecting missing, unknown, or coerced fields."""

        if not isinstance(value, dict):
            raise ValueError("acquisition request must be a JSON object")
        allowed = {
            "schema_version",
            "kind",
            "source",
            "source_version",
            "workspace_root",
            "working_directory",
            "argv",
            "timeout_seconds",
            "max_capture_bytes",
            "supports_correct_exit_codes",
            "supports_incorrect_exit_codes",
        }
        unknown = sorted(set(value).difference(allowed))
        if unknown:
            raise ValueError(f"acquisition request contains unknown fields: {unknown}")
        required = {
            "schema_version",
            "kind",
            "source",
            "source_version",
            "workspace_root",
            "argv",
        }
        missing = sorted(required.difference(value))
        if missing:
            raise ValueError(f"acquisition request is missing required fields: {missing}")

        try:
            kind = EvidenceKind(_plain_string(value["kind"], "kind", nonempty=True))
        except ValueError as exc:
            raise ValueError(f"unknown evidence kind: {value.get('kind')!r}") from exc
        argv = value["argv"]
        if not isinstance(argv, list):
            raise ValueError("argv must be a JSON array of strings")
        max_capture = value.get("max_capture_bytes", DEFAULT_CAPTURE_BYTES)
        if isinstance(max_capture, bool) or not isinstance(max_capture, int):
            raise ValueError("max_capture_bytes must be a JSON integer")
        return cls(
            schema_version=_plain_string(
                value["schema_version"], "schema_version", nonempty=True
            ),
            kind=kind,
            source=_plain_string(value["source"], "source", nonempty=True),
            source_version=_plain_string(
                value["source_version"], "source_version", nonempty=True
            ),
            workspace_root=_plain_string(
                value["workspace_root"], "workspace_root", nonempty=True
            ),
            working_directory=_plain_string(
                value.get("working_directory", "."),
                "working_directory",
                nonempty=True,
            ),
            argv=tuple(
                _plain_string(item, f"argv[{index}]", nonempty=index == 0)
                for index, item in enumerate(argv)
            ),
            timeout_seconds=_positive_number(
                value.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
                "timeout_seconds",
            ),
            max_capture_bytes=max_capture,
            supports_correct_exit_codes=_exit_codes(
                value.get("supports_correct_exit_codes", [0]),
                "supports_correct_exit_codes",
                required=True,
            ),
            supports_incorrect_exit_codes=_exit_codes(
                value.get("supports_incorrect_exit_codes", [1]),
                "supports_incorrect_exit_codes",
                required=False,
            ),
        )


def _optional_probability(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(f"{field_name} must be null or a finite number in [0, 1]")
    return float(value)


def _optional_token_count(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be null or a non-negative integer")
    return value


def _optional_usd(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{field_name} must be null or a finite non-negative number")
    return float(value)


@dataclass(frozen=True)
class SemanticOutput:
    """Strict execution-free verifier output emitted as one stdout JSON object."""

    status: EvidenceStatus
    candidate_probability: float | None
    calibrated_risk_upper_bound: float | None
    calibration_id: str
    verifier_validity: float | None
    privileged_inputs: tuple[str, ...]
    input_tokens: int | None
    output_tokens: int | None
    usd: float | None
    schema_version: str = SEMANTIC_OUTPUT_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Any) -> SemanticOutput:
        if not isinstance(value, dict):
            raise ValueError("semantic output must be a JSON object")
        expected = {
            "schema_version",
            "status",
            "candidate_probability",
            "calibrated_risk_upper_bound",
            "calibration_id",
            "verifier_validity",
            "privileged_inputs",
            "cost",
        }
        unknown = sorted(set(value).difference(expected))
        missing = sorted(expected.difference(value))
        if unknown:
            raise ValueError(f"semantic output contains unknown fields: {unknown}")
        if missing:
            raise ValueError(f"semantic output is missing fields: {missing}")
        schema_version = _plain_string(
            value["schema_version"],
            "semantic output schema_version",
            nonempty=True,
        )
        if schema_version != SEMANTIC_OUTPUT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported semantic output schema version "
                f"{schema_version!r}; expected {SEMANTIC_OUTPUT_SCHEMA_VERSION!r}"
            )
        status_text = _plain_string(
            value["status"],
            "semantic output status",
            nonempty=True,
        )
        try:
            status = EvidenceStatus(status_text)
        except ValueError as exc:
            raise ValueError(f"unknown semantic output status {status_text!r}") from exc
        if status not in {
            EvidenceStatus.SUPPORTS_CORRECT,
            EvidenceStatus.SUPPORTS_INCORRECT,
            EvidenceStatus.INCONCLUSIVE,
        }:
            raise ValueError(
                "semantic output status must be supports_correct, "
                "supports_incorrect, or inconclusive"
            )
        candidate_probability = _optional_probability(
            value["candidate_probability"],
            "semantic output candidate_probability",
        )
        risk_bound = _optional_probability(
            value["calibrated_risk_upper_bound"],
            "semantic output calibrated_risk_upper_bound",
        )
        calibration_id = _plain_string(
            value["calibration_id"],
            "semantic output calibration_id",
        )
        if calibration_id != calibration_id.strip():
            raise ValueError(
                "semantic output calibration_id cannot have surrounding whitespace"
            )
        if risk_bound is not None and not calibration_id:
            raise ValueError(
                "semantic output calibrated risk bound requires calibration_id"
            )
        if risk_bound is None and calibration_id:
            raise ValueError(
                "semantic output calibration_id requires calibrated_risk_upper_bound"
            )
        verifier_validity = _optional_probability(
            value["verifier_validity"],
            "semantic output verifier_validity",
        )
        raw_privileged = value["privileged_inputs"]
        if not isinstance(raw_privileged, list):
            raise ValueError("semantic output privileged_inputs must be a JSON array")
        privileged: list[str] = []
        for index, item in enumerate(raw_privileged):
            normalized = _plain_string(
                item,
                f"semantic output privileged_inputs[{index}]",
                nonempty=True,
            )
            if any(ord(character) < 32 for character in normalized):
                raise ValueError(
                    "semantic output privileged_inputs cannot contain control characters"
                )
            privileged.append(normalized)
        if len(privileged) != len(set(privileged)):
            raise ValueError("semantic output privileged_inputs cannot contain duplicates")
        cost = value["cost"]
        if not isinstance(cost, dict) or set(cost) != {
            "input_tokens",
            "output_tokens",
            "usd",
        }:
            raise ValueError(
                "semantic output cost must contain exactly input_tokens, output_tokens, usd"
            )
        if status == EvidenceStatus.INCONCLUSIVE and (
            candidate_probability is not None or risk_bound is not None
        ):
            raise ValueError(
                "inconclusive semantic output cannot carry candidate probability or risk bound"
            )
        if (
            candidate_probability is not None
            and status == EvidenceStatus.SUPPORTS_CORRECT
            and candidate_probability < 0.5
        ):
            raise ValueError(
                "supports_correct semantic output cannot have candidate_probability < 0.5"
            )
        if (
            candidate_probability is not None
            and status == EvidenceStatus.SUPPORTS_INCORRECT
            and candidate_probability > 0.5
        ):
            raise ValueError(
                "supports_incorrect semantic output cannot have candidate_probability > 0.5"
            )
        return cls(
            schema_version=schema_version,
            status=status,
            candidate_probability=candidate_probability,
            calibrated_risk_upper_bound=risk_bound,
            calibration_id=calibration_id,
            verifier_validity=verifier_validity,
            privileged_inputs=tuple(privileged),
            input_tokens=_optional_token_count(
                cost["input_tokens"],
                "semantic output cost.input_tokens",
            ),
            output_tokens=_optional_token_count(
                cost["output_tokens"],
                "semantic output cost.output_tokens",
            ),
            usd=_optional_usd(cost["usd"], "semantic output cost.usd"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "candidate_probability": self.candidate_probability,
            "calibrated_risk_upper_bound": self.calibrated_risk_upper_bound,
            "calibration_id": self.calibration_id,
            "verifier_validity": self.verifier_validity,
            "privileged_inputs": list(self.privileged_inputs),
            "cost": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "usd": self.usd,
            },
        }


def decode_semantic_output(payload: bytes) -> tuple[SemanticOutput | None, str | None]:
    """Decode strict semantic stdout into a typed result and stable error code."""

    if not isinstance(payload, bytes):
        raise TypeError("semantic output payload must be bytes")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None, "invalid_utf8"
    try:
        value = strict_json_loads(text)
    except ValueError:
        return None, "invalid_json"
    try:
        return SemanticOutput.from_dict(value), None
    except ValueError:
        return None, "invalid_schema"


def load_acquisition_request(stream: TextIO) -> AcquisitionRequest:
    """Load one strict JSON acquisition request from *stream*."""

    try:
        value = strict_json_load(stream)
    except ValueError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    return AcquisitionRequest.from_dict(value)


class _BoundedCapture:
    """Drain a byte stream completely while retaining at most *limit* bytes."""

    def __init__(self, stream: BinaryIO | None, limit: int, name: str) -> None:
        self.stream = stream
        self.limit = limit
        self.name = name
        self.total_bytes = 0
        self._head = bytearray()
        self._tail = bytearray()
        self._truncated = False
        self._digest = hashlib.sha256()
        self.error = ""
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.stream is None:
            return
        self.thread = threading.Thread(
            target=self._drain,
            name=f"bench-cleanser-{self.name}-capture",
            daemon=True,
        )
        self.thread.start()

    def _append(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        self._digest.update(chunk)
        if not self._truncated and len(self._head) + len(chunk) <= self.limit:
            self._head.extend(chunk)
            return

        head_limit = (self.limit + 1) // 2
        tail_limit = self.limit - head_limit
        if not self._truncated:
            combined = bytes(self._head) + chunk
            self._head = bytearray(combined[:head_limit])
            self._tail = (
                bytearray(combined[-tail_limit:]) if tail_limit else bytearray()
            )
            self._truncated = True
            return
        if tail_limit:
            self._tail = bytearray((bytes(self._tail) + chunk)[-tail_limit:])

    def _drain(self) -> None:
        assert self.stream is not None
        try:
            while True:
                chunk = self.stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                self._append(chunk)
        except (OSError, ValueError) as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                self.stream.close()
            except OSError:
                pass

    def join(self, timeout: float) -> None:
        if self.thread is not None:
            self.thread.join(max(0.0, timeout))

    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def close(self) -> None:
        if self.stream is not None:
            try:
                self.stream.close()
            except OSError:
                pass

    def captured_raw_bytes(self) -> bytes:
        """Return the exact retained bytes without the human truncation marker."""

        return bytes(self._head) + bytes(self._tail)

    def to_dict(self) -> dict[str, Any]:
        raw = bytes(self._head)
        if self._truncated:
            raw += b"\n[... bounded capture truncated ...]\n" + bytes(self._tail)
        return {
            "text": raw.decode("utf-8", errors="replace"),
            "encoding": "utf-8-replace",
            "captured_bytes": len(self._head) + len(self._tail),
            "total_bytes": self.total_bytes,
            "truncated": self._truncated,
            "sha256": self._digest.hexdigest(),
            "read_error": self.error or None,
        }


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolve_working_directory(request: AcquisitionRequest) -> tuple[pathlib.Path, pathlib.Path]:
    root = pathlib.Path(request.workspace_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace_root must resolve to a directory")
    relative = pathlib.Path(request.working_directory)
    if relative.is_absolute():
        raise ValueError("working_directory must be relative to workspace_root")
    working = (root / relative).resolve(strict=True)
    try:
        working.relative_to(root)
    except ValueError as exc:
        raise ValueError("working_directory escapes workspace_root") from exc
    if not working.is_dir():
        raise ValueError("working_directory must resolve to a directory")
    return root, working


def _artifact_directory(path: pathlib.Path) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("artifact_directory must resolve to a directory")
    return resolved


def _minimal_environment(home: pathlib.Path) -> dict[str, str]:
    """Return an allowlisted environment without ambient credential variables."""

    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "TMPDIR": str(home),
        "TMP": str(home),
        "TEMP": str(home),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "TERM": "dumb",
        "NO_COLOR": "1",
        "PYTHONUNBUFFERED": "1",
    }
    if os.name == "nt":
        for key in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT"):
            if key in os.environ:
                environment[key] = os.environ[key]
        environment["USERPROFILE"] = str(home)
    return environment


def _group_exists(process_group_id: int) -> bool:
    if os.name != "posix":
        return False
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_process_group(
    process: subprocess.Popen[bytes],
    environment: dict[str, str],
) -> list[str]:
    """Terminate the acquisition's process group/tree and return cleanup errors."""

    errors: list[str] = []
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exc:
            errors.append(f"SIGTERM process group failed: {exc}")

        deadline = time.monotonic() + _TERMINATION_GRACE_SECONDS
        while _group_exists(process.pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        if _group_exists(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exc:
                errors.append(f"SIGKILL process group failed: {exc}")
    else:  # pragma: no cover - exercised by Windows CI/users
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=1.0,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"process-tree cleanup failed: {exc}")
        if process.poll() is None:
            try:
                process.kill()
            except OSError as exc:
                errors.append(f"process kill failed: {exc}")

    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        errors.append("process leader did not exit after group termination")
    return errors


def _join_captures(captures: tuple[_BoundedCapture, ...], deadline: float) -> bool:
    for capture in captures:
        capture.join(max(0.0, deadline - time.monotonic()))
    return not any(capture.alive for capture in captures)


def _request_digest(request: AcquisitionRequest) -> str:
    encoded = strict_json_dumps(request.to_dict()).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class _ArtifactReservation:
    path: pathlib.Path
    device: int
    inode: int

    def release(self) -> None:
        try:
            current = self.path.stat(follow_symlinks=False)
        except FileNotFoundError as exc:
            raise OSError("acquisition reservation disappeared before release") from exc
        if (current.st_dev, current.st_ino) != (self.device, self.inode):
            raise OSError("acquisition reservation identity changed before release")
        self.path.unlink()
        if os.name != "nt":
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)


def _new_artifact_path(
    directory: pathlib.Path,
    acquisition_id: str | None = None,
) -> tuple[str, pathlib.Path, _ArtifactReservation]:
    def reserve(identifier: str) -> tuple[str, pathlib.Path, _ArtifactReservation]:
        path = directory / f"{identifier}.json"
        lock_path = directory / f".{identifier}.lock"
        if path.exists():
            raise FileExistsError(
                f"acquisition artifact already exists for {identifier!r}"
            )
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise FileExistsError(
                f"acquisition {identifier!r} is already reserved"
            ) from exc
        reservation_stat = os.fstat(descriptor)
        try:
            payload = (identifier + "\n").encode("ascii")
            os.write(descriptor, payload)
            os.fsync(descriptor)
        except BaseException:
            os.close(descriptor)
            reservation = _ArtifactReservation(
                path=lock_path,
                device=reservation_stat.st_dev,
                inode=reservation_stat.st_ino,
            )
            reservation.release()
            raise
        else:
            os.close(descriptor)
        reservation = _ArtifactReservation(
            path=lock_path,
            device=reservation_stat.st_dev,
            inode=reservation_stat.st_ino,
        )
        try:
            if os.name != "nt":
                directory_fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except BaseException:
            reservation.release()
            raise
        if path.exists():
            reservation.release()
            raise FileExistsError(
                f"acquisition artifact appeared while reserving {identifier!r}"
            )
        return identifier, path, reservation

    if acquisition_id is not None:
        if (
            not isinstance(acquisition_id, str)
            or not _ACQUISITION_ID_RE.fullmatch(acquisition_id)
        ):
            raise ValueError(
                "acquisition_id must have the form 'acq-' followed by "
                "32 lowercase hexadecimal characters"
            )
        return reserve(acquisition_id)
    for _ in range(8):
        generated_id = f"acq-{uuid.uuid4().hex}"
        try:
            return reserve(generated_id)
        except FileExistsError:
            continue
    raise OSError("could not allocate a unique acquisition artifact name")


def _atomic_create_artifact(path: pathlib.Path, content: str) -> None:
    """Atomically publish a complete artifact without replacing another writer."""

    if not isinstance(content, str):
        raise TypeError("artifact content must be text")
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
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(
                f"acquisition artifact appeared before publication: {path}"
            ) from exc
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def acquire_evidence(
    request: AcquisitionRequest,
    *,
    artifact_directory: pathlib.Path,
    acquisition_id: str | None = None,
) -> EvidenceObservation:
    """Run one bounded acquisition and atomically persist its artifact.

    Exit codes are interpreted only through the request's explicit maps.  A
    completed mapped failure supports candidate incorrectness; a timeout,
    launch/capture failure, signal, leaked process group, or unmapped exit is
    inconclusive.  No observation returned here is authoritative.
    """

    if not isinstance(request, AcquisitionRequest):
        raise ValueError("request must be an AcquisitionRequest")
    root, working = _resolve_working_directory(request)
    artifacts = _artifact_directory(pathlib.Path(artifact_directory))
    acquisition_id, artifact_path, reservation = _new_artifact_path(
        artifacts,
        acquisition_id,
    )

    try:
        started_at = _timestamp()
        started = time.monotonic()
        deadline = started + request.timeout_seconds
        process: subprocess.Popen[bytes] | None = None
        stdout_capture = _BoundedCapture(None, request.max_capture_bytes, "stdout")
        stderr_capture = _BoundedCapture(None, request.max_capture_bytes, "stderr")
        timed_out = False
        residual_process_group = False
        setup_error: str | None = None
        cleanup_errors: list[str] = []
        environment: dict[str, str] = {}
        temporary_home: tempfile.TemporaryDirectory[str] | None = None
    except BaseException:
        reservation.release()
        raise

    try:
        try:
            temporary_home = tempfile.TemporaryDirectory(
                prefix="bench-cleanser-acquire-"
            )
            environment = _minimal_environment(pathlib.Path(temporary_home.name))
        except OSError as exc:
            setup_error = f"{type(exc).__name__}: {exc}"
        except BaseException:
            try:
                if temporary_home is not None:
                    temporary_home.cleanup()
                    temporary_home = None
            finally:
                reservation.release()
            raise

        if setup_error is None:
            popen_options: dict[str, Any] = {
                "cwd": working,
                "env": environment,
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "shell": False,
                "close_fds": True,
            }
            if os.name == "posix":
                popen_options["start_new_session"] = True
            else:  # pragma: no cover - platform-specific
                popen_options["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
            try:
                process = subprocess.Popen(list(request.argv), **popen_options)
            except (OSError, subprocess.SubprocessError) as exc:
                setup_error = f"{type(exc).__name__}: {exc}"
            except BaseException:
                try:
                    if temporary_home is not None:
                        temporary_home.cleanup()
                        temporary_home = None
                finally:
                    reservation.release()
                raise

        if process is not None:
            stdout_capture = _BoundedCapture(
                cast(BinaryIO | None, process.stdout),
                request.max_capture_bytes,
                "stdout",
            )
            stderr_capture = _BoundedCapture(
                cast(BinaryIO | None, process.stderr),
                request.max_capture_bytes,
                "stderr",
            )
            captures = (stdout_capture, stderr_capture)
            for capture in captures:
                capture.start()

            remaining = deadline - time.monotonic()
            if remaining <= 0 and process.poll() is None:
                timed_out = True
            else:
                try:
                    process.wait(timeout=max(0.0, remaining))
                except subprocess.TimeoutExpired:
                    timed_out = True

            if not timed_out and not _join_captures(captures, deadline):
                # A descendant can keep an inherited pipe open after the
                # process leader exits.  The acquisition still owns that
                # process group and the wall deadline still applies.
                timed_out = True

            if timed_out:
                cleanup_errors.extend(_terminate_process_group(process, environment))

            reader_deadline = time.monotonic() + 1.0
            if not _join_captures(captures, reader_deadline):
                for capture in captures:
                    capture.close()
                _join_captures(captures, time.monotonic() + 0.1)

            if not timed_out and os.name == "posix" and _group_exists(process.pid):
                # Verification commands are not permitted to leak background
                # work into later acquisitions.  Clean it up and fail closed.
                residual_process_group = True
                cleanup_errors.extend(_terminate_process_group(process, environment))
    except BaseException:
        if process is not None:
            try:
                _terminate_process_group(process, environment)
            except BaseException:
                pass
            for capture in (stdout_capture, stderr_capture):
                capture.close()
            try:
                _join_captures(
                    (stdout_capture, stderr_capture),
                    time.monotonic() + 1.0,
                )
            except (RuntimeError, TypeError):
                pass
        raise
    finally:
        if temporary_home is not None:
            try:
                temporary_home.cleanup()
            except OSError as exc:
                cleanup_errors.append(f"temporary environment cleanup failed: {exc}")

    capture_incomplete = any(
        capture.alive for capture in (stdout_capture, stderr_capture)
    )
    capture_failed = capture_incomplete or any(
        capture.error for capture in (stdout_capture, stderr_capture)
    )
    return_code = process.returncode if process is not None else None
    semantic_output: SemanticOutput | None = None
    semantic_error: str | None = None
    if setup_error is not None:
        outcome = "setup_failure"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = "setup_failure" if request.kind == EvidenceKind.SEMANTIC else None
    elif timed_out:
        outcome = "timeout"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = "timeout" if request.kind == EvidenceKind.SEMANTIC else None
    elif capture_failed or cleanup_errors:
        outcome = "capture_or_cleanup_failure"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = (
            "capture_or_cleanup_failure"
            if request.kind == EvidenceKind.SEMANTIC
            else None
        )
    elif residual_process_group:
        outcome = "residual_process_group"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = (
            "residual_process_group"
            if request.kind == EvidenceKind.SEMANTIC
            else None
        )
    elif return_code is None or return_code < 0:
        outcome = "signaled"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = "signaled" if request.kind == EvidenceKind.SEMANTIC else None
    elif request.kind == EvidenceKind.SEMANTIC and (
        stdout_capture.to_dict()["truncated"]
        or stderr_capture.to_dict()["truncated"]
    ):
        outcome = "semantic_truncated_output"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = "capture_truncated"
    elif request.kind == EvidenceKind.SEMANTIC and return_code != 0:
        outcome = "semantic_nonzero_exit"
        status = EvidenceStatus.INCONCLUSIVE
        semantic_error = "nonzero_exit"
    elif request.kind == EvidenceKind.SEMANTIC:
        semantic_output, semantic_error = decode_semantic_output(
            stdout_capture.captured_raw_bytes()
        )
        if semantic_output is None:
            outcome = "semantic_invalid_output"
            status = EvidenceStatus.INCONCLUSIVE
        else:
            outcome = "semantic_result"
            status = semantic_output.status
    elif return_code in request.supports_correct_exit_codes:
        outcome = "supports_correct"
        status = EvidenceStatus.SUPPORTS_CORRECT
    elif return_code in request.supports_incorrect_exit_codes:
        outcome = "supports_incorrect"
        status = EvidenceStatus.SUPPORTS_INCORRECT
    else:
        outcome = "unmapped_exit"
        status = EvidenceStatus.INCONCLUSIVE

    finished_at = _timestamp()
    wall_seconds = max(0.0, time.monotonic() - started)
    stdout_data = stdout_capture.to_dict()
    stderr_data = stderr_capture.to_dict()
    semantic_artifact: dict[str, Any] | None = None
    if request.kind == EvidenceKind.SEMANTIC:
        retained_stdout = stdout_capture.captured_raw_bytes()
        semantic_artifact = {
            "output_schema_version": SEMANTIC_OUTPUT_SCHEMA_VERSION,
            "raw_stdout": {
                "encoding": "base64",
                "data": base64.b64encode(retained_stdout).decode("ascii"),
                "captured_bytes": len(retained_stdout),
                "total_bytes": stdout_data["total_bytes"],
                "truncated": stdout_data["truncated"],
                "sha256": stdout_data["sha256"],
            },
            "parsed": (
                semantic_output.to_dict() if semantic_output is not None else None
            ),
            "error_code": semantic_error,
        }
    artifact = {
        "schema_version": ACQUISITION_SCHEMA_VERSION,
        "runner": {
            "name": "bench-cleanser-acquire",
            "version": __version__,
        },
        "acquisition_id": acquisition_id,
        "request_sha256": _request_digest(request),
        "kind": request.kind.value,
        "source": request.source,
        "source_version": request.source_version,
        "argv": list(request.argv),
        "workspace_root": str(root),
        "working_directory": str(working.relative_to(root)) or ".",
        "execution": {
            "started_at": started_at,
            "finished_at": finished_at,
            "wall_seconds": wall_seconds,
            "timeout_seconds": request.timeout_seconds,
            "outcome": outcome,
            "return_code": return_code,
            "timed_out": timed_out,
            "residual_process_group": residual_process_group,
            "capture_incomplete": capture_incomplete,
            "setup_error": setup_error,
            "cleanup_errors": cleanup_errors,
            "supports_correct_exit_codes": list(
                request.supports_correct_exit_codes
            ),
            "supports_incorrect_exit_codes": list(
                request.supports_incorrect_exit_codes
            ),
            "shell": False,
            "sandbox": "not_provided",
            "environment_policy": "minimal-allowlist-v1",
            "supplied_environment_keys": sorted(environment),
        },
        "stdout": stdout_data,
        "stderr": stderr_data,
    }
    if semantic_artifact is not None:
        artifact["semantic"] = semantic_artifact
    try:
        artifact_text = strict_json_dumps(artifact, indent=2) + "\n"
        artifact_bytes = artifact_text.encode("utf-8")
        artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        _atomic_create_artifact(artifact_path, artifact_text)
    except BaseException:
        if process is None:
            reservation.release()
        raise
    reservation.release()

    verifier_validity = (
        semantic_output.verifier_validity
        if semantic_output is not None
        else (0.0 if status == EvidenceStatus.INCONCLUSIVE else None)
    )
    measured_cost_dimensions = ["wall_seconds", "storage_bytes"]
    producer_declared_cost_dimensions: list[str] = []
    producer_declared_semantic_fields: list[str] = []
    if semantic_output is not None:
        producer_declared_semantic_fields.extend(
            SEMANTIC_PRODUCER_DECLARED_FIELDS
        )
        for name in ("input_tokens", "output_tokens", "usd"):
            if getattr(semantic_output, name) is not None:
                producer_declared_cost_dimensions.append(name)
    observation_metadata: dict[str, Any] = {
        "acquisition_schema_version": ACQUISITION_SCHEMA_VERSION,
        "runner": "bench-cleanser-acquire",
        "runner_version": __version__,
        "outcome": outcome,
        "return_code": return_code,
        "capture_incomplete": capture_incomplete,
        "artifact_sha256": artifact_sha256,
        "artifact_locator": artifact_path.as_uri(),
        "capture_bindings": {
            "stdout": {
                "captured_bytes": stdout_data["captured_bytes"],
                "total_bytes": stdout_data["total_bytes"],
                "truncated": stdout_data["truncated"],
                "sha256": stdout_data["sha256"],
                "read_error": stdout_data["read_error"],
            },
            "stderr": {
                "captured_bytes": stderr_data["captured_bytes"],
                "total_bytes": stderr_data["total_bytes"],
                "truncated": stderr_data["truncated"],
                "sha256": stderr_data["sha256"],
                "read_error": stderr_data["read_error"],
            },
        },
        "stdout_truncated": stdout_data["truncated"],
        "stderr_truncated": stderr_data["truncated"],
        "measured_cost_dimensions": measured_cost_dimensions,
    }
    if request.kind == EvidenceKind.SEMANTIC:
        observation_metadata.update({
            "semantic_output_schema_version": SEMANTIC_OUTPUT_SCHEMA_VERSION,
            "semantic_output_sha256": stdout_data["sha256"],
            "semantic_output_error": semantic_error,
            "semantic_output_valid": semantic_output is not None,
            "producer_declared_semantic_fields": (
                producer_declared_semantic_fields
            ),
            "producer_declared_cost_dimensions": producer_declared_cost_dimensions,
        })
    return EvidenceObservation(
        kind=request.kind,
        status=status,
        source=request.source,
        source_version=request.source_version,
        acquisition_id=acquisition_id,
        candidate_probability=(
            semantic_output.candidate_probability
            if semantic_output is not None
            else None
        ),
        verifier_validity=verifier_validity,
        calibrated_risk_upper_bound=(
            semantic_output.calibrated_risk_upper_bound
            if semantic_output is not None
            else None
        ),
        calibration_id=(
            semantic_output.calibration_id if semantic_output is not None else ""
        ),
        authoritative=False,
        privileged_inputs=(
            semantic_output.privileged_inputs if semantic_output is not None else ()
        ),
        cost=EvidenceCost(
            wall_seconds=wall_seconds,
            input_tokens=(
                semantic_output.input_tokens
                if semantic_output is not None
                and semantic_output.input_tokens is not None
                else 0
            ),
            output_tokens=(
                semantic_output.output_tokens
                if semantic_output is not None
                and semantic_output.output_tokens is not None
                else 0
            ),
            storage_bytes=len(artifact_bytes),
            usd=(
                semantic_output.usd
                if semantic_output is not None and semantic_output.usd is not None
                else 0.0
            ),
        ),
        metadata=observation_metadata,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench-cleanser-acquire",
        description=(
            "Run one bounded, argv-only local evidence acquisition and emit a "
            "non-authoritative EvidenceObservation as strict JSON"
        ),
        epilog=(
            "This confines the initial working directory and child environment; "
            "it does not provide a filesystem, network, container, or OS sandbox."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("request", help="Acquisition-request JSON file, or '-' for stdin")
    parser.add_argument(
        "--artifact-dir",
        required=True,
        help="Directory for the atomically written, digest-bound run artifact",
    )
    parser.add_argument("--output", help="Write the observation here instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if args.request == "-":
            request = load_acquisition_request(sys.stdin)
        else:
            with pathlib.Path(args.request).open(encoding="utf-8") as stream:
                request = load_acquisition_request(stream)
        observation = acquire_evidence(
            request,
            artifact_directory=pathlib.Path(args.artifact_dir),
        )
        rendered = strict_json_dumps(observation.to_dict(), indent=2) + "\n"
        if args.output:
            atomic_write(pathlib.Path(args.output), rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"evidence acquisition failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - console entry point
    main()
