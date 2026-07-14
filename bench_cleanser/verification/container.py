"""Fail-closed construction of pinned Linux-container acquisition requests.

This module only builds an :class:`~verification.acquire.AcquisitionRequest`;
it never contacts a Docker daemon or executes a repository.  The generated
Docker CLI invocation uses a digest-only image reference, an explicit local
daemon endpoint, no network, a read-only root filesystem and workspace mount,
bounded writable tmpfs and process/resource limits, a non-root user, no Linux
capabilities, and ``no-new-privileges``.  The image entrypoint is cleared so
the supplied container argv is not silently wrapped by image metadata.

This remains a defense-in-depth adapter, not a sandbox proof.  The Docker CLI,
daemon, kernel, pinned image, and provisioned workspace are trusted inputs.
Read-only mounts expose their contents and any special files or nested mounts,
image-declared volumes or daemon policy may add writable state, daemon-managed
containers can outlive a killed client, and container/kernel escapes are
outside this contract. Only Linux-container flags are encoded; Windows
containers are unsupported. Evidence acquired from the resulting request
remains non-authoritative under :mod:`verification.acquire`.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from bench_cleanser.verification.acquire import (
    DEFAULT_CAPTURE_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    AcquisitionRequest,
)
from bench_cleanser.verification.models import EvidenceKind

PINNED_CONTAINER_ADAPTER_VERSION = "0.1.0"

DEFAULT_TMPFS_SIZE_BYTES = 64 * 1024 * 1024
DEFAULT_PIDS_LIMIT = 128
DEFAULT_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024
DEFAULT_CPU_LIMIT_MILLIS = 1000

MIN_TMPFS_SIZE_BYTES = 1024 * 1024
MAX_TMPFS_SIZE_BYTES = 1024 * 1024 * 1024
MIN_MEMORY_LIMIT_BYTES = 16 * 1024 * 1024
MAX_MEMORY_LIMIT_BYTES = 16 * 1024 * 1024 * 1024
MIN_PIDS_LIMIT = 1
MAX_PIDS_LIMIT = 1024
MIN_CPU_LIMIT_MILLIS = 100
MAX_CPU_LIMIT_MILLIS = 16_000

_RAW_IMAGE_ID_RE = re.compile(r"sha256:[0-9a-f]{64}")
_NAMED_IMAGE_DIGEST_RE = re.compile(
    r"(?P<name>[a-z0-9][a-z0-9._:/-]{0,254})@sha256:[0-9a-f]{64}"
)
_REPOSITORY_COMPONENT_RE = re.compile(
    r"[a-z0-9]+(?:(?:[._]|__|[-]+)[a-z0-9]+)*"
)
_REGISTRY_LABEL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
_NPIPE_ENDPOINT_RE = re.compile(
    r"npipe:////\./pipe/[A-Za-z0-9][A-Za-z0-9._/-]*"
)
_DIRECT_SHELL_NAMES = frozenset({
    "ash",
    "bash",
    "cmd",
    "cmd.exe",
    "csh",
    "dash",
    "fish",
    "ksh",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "sh",
    "tcsh",
    "zsh",
})
_MAX_CONTAINER_ARGV_ITEMS = 256
_MAX_CONTAINER_ARG_BYTES = 4096
_MAX_CONTAINER_ARGV_BYTES = 64 * 1024


def _integer_limit(value: Any, field_name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a JSON integer")
    if not lower <= value <= upper:
        raise ValueError(f"{field_name} must be in [{lower}, {upper}]")
    return value


@dataclass(frozen=True)
class PinnedContainerLimits:
    """Conservative Docker resource ceilings for one acquisition."""

    tmpfs_size_bytes: int = DEFAULT_TMPFS_SIZE_BYTES
    pids_limit: int = DEFAULT_PIDS_LIMIT
    memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES
    cpu_limit_millis: int = DEFAULT_CPU_LIMIT_MILLIS

    def __post_init__(self) -> None:
        _integer_limit(
            self.tmpfs_size_bytes,
            "tmpfs_size_bytes",
            MIN_TMPFS_SIZE_BYTES,
            MAX_TMPFS_SIZE_BYTES,
        )
        _integer_limit(
            self.pids_limit,
            "pids_limit",
            MIN_PIDS_LIMIT,
            MAX_PIDS_LIMIT,
        )
        _integer_limit(
            self.memory_limit_bytes,
            "memory_limit_bytes",
            MIN_MEMORY_LIMIT_BYTES,
            MAX_MEMORY_LIMIT_BYTES,
        )
        _integer_limit(
            self.cpu_limit_millis,
            "cpu_limit_millis",
            MIN_CPU_LIMIT_MILLIS,
            MAX_CPU_LIMIT_MILLIS,
        )
        if self.tmpfs_size_bytes > self.memory_limit_bytes:
            raise ValueError("tmpfs_size_bytes cannot exceed memory_limit_bytes")


DEFAULT_PINNED_CONTAINER_LIMITS = PinnedContainerLimits()


def _contains_cli_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _string(value: Any, field_name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if _contains_cli_control(value):
        raise ValueError(f"{field_name} cannot contain control characters")
    if nonempty and (not value.strip() or value != value.strip()):
        raise ValueError(
            f"{field_name} must be non-empty and have no surrounding whitespace"
        )
    return value


def _canonical_executable(value: str | os.PathLike[str]) -> pathlib.Path:
    try:
        declared = pathlib.Path(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("docker_executable must be a filesystem path") from exc
    if not declared.is_absolute():
        raise ValueError("docker_executable must be an absolute path")
    try:
        resolved = declared.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("docker_executable must exist") from exc
    if declared != resolved or declared.is_symlink():
        raise ValueError("docker_executable must be a canonical physical path")
    if not resolved.is_file():
        raise ValueError("docker_executable must resolve to a regular file")
    if _contains_cli_control(str(resolved)):
        raise ValueError("docker_executable cannot contain control characters")
    if resolved.name.casefold() not in {"docker", "docker.exe"}:
        raise ValueError("docker_executable must name the Docker CLI")
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        raise ValueError("docker_executable must be executable")
    return resolved


def _canonical_workspace(value: str | os.PathLike[str]) -> pathlib.Path:
    try:
        declared = pathlib.Path(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("workspace_root must be a filesystem path") from exc
    if not declared.is_absolute():
        raise ValueError("workspace_root must be an absolute path")
    try:
        resolved = declared.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("workspace_root must exist") from exc
    if declared != resolved or declared.is_symlink():
        raise ValueError("workspace_root must be a canonical physical path")
    if not resolved.is_dir():
        raise ValueError("workspace_root must resolve to a directory")
    if resolved.parent == resolved:
        raise ValueError("workspace_root cannot be a filesystem root")
    rendered = str(resolved)
    if _contains_cli_control(rendered) or "," in rendered:
        raise ValueError(
            "workspace_root contains characters unsafe for Docker --mount"
        )
    return resolved


def _docker_host(value: Any) -> str:
    endpoint = _string(value, "docker_host")
    if any(character.isspace() for character in endpoint):
        raise ValueError("docker_host cannot contain whitespace")
    if endpoint.startswith("unix://"):
        if os.name == "nt":  # pragma: no cover - Windows contract
            raise ValueError("docker_host must use npipe:// on a Windows host")
        parsed = urlsplit(endpoint)
        path_parts = parsed.path.split("/")[1:]
        if (
            parsed.scheme != "unix"
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/")
            or parsed.path == "/"
            or "%" in endpoint
            or any(part in {"", ".", ".."} for part in path_parts)
        ):
            raise ValueError("docker_host must be a canonical absolute unix:// socket URI")
        return endpoint
    if _NPIPE_ENDPOINT_RE.fullmatch(endpoint):
        if os.name != "nt":
            raise ValueError("docker_host must use unix:// on a POSIX host")
        suffix = endpoint.removeprefix("npipe:////./pipe/")
        if any(part in {"", ".", ".."} for part in suffix.split("/")):
            raise ValueError("docker_host named-pipe path cannot contain traversal")
        return endpoint
    raise ValueError(
        "docker_host must use an explicit local unix:// or npipe:// endpoint; "
        "remote daemon authentication is not encoded"
    )


def _immutable_image(value: Any) -> str:
    image = _string(value, "image")
    if _RAW_IMAGE_ID_RE.fullmatch(image):
        return image
    match = _NAMED_IMAGE_DIGEST_RE.fullmatch(image)
    if match is None:
        raise ValueError(
            "image must be an immutable sha256:<digest> ID or name@sha256:<digest>"
        )
    name = match.group("name")
    parts = name.split("/")
    path_parts = parts
    if len(parts) > 1 and (
        parts[0] == "localhost" or "." in parts[0] or ":" in parts[0]
    ):
        registry = parts[0]
        path_parts = parts[1:]
        host, separator, port = registry.rpartition(":")
        if not separator:
            host = registry
        elif not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError("image registry port is not canonical")
        if host != "localhost" and (
            len(host) > 253
            or any(
                _REGISTRY_LABEL_RE.fullmatch(label) is None
                for label in host.split(".")
            )
        ):
            raise ValueError("image registry host is not canonical")
    if not path_parts or any(
        _REPOSITORY_COMPONENT_RE.fullmatch(part) is None
        for part in path_parts
    ):
        raise ValueError("image repository name is not canonical")
    return image


def _container_argv(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("container_argv must be a non-empty list or tuple")
    if len(value) > _MAX_CONTAINER_ARGV_ITEMS:
        raise ValueError(
            f"container_argv cannot contain more than {_MAX_CONTAINER_ARGV_ITEMS} items"
        )
    normalized: list[str] = []
    total_bytes = 0
    for index, raw_item in enumerate(value):
        item = _string(raw_item, f"container_argv[{index}]", nonempty=index == 0)
        item_bytes = len(item.encode("utf-8"))
        if item_bytes > _MAX_CONTAINER_ARG_BYTES:
            raise ValueError(
                f"container_argv[{index}] exceeds {_MAX_CONTAINER_ARG_BYTES} UTF-8 bytes"
            )
        total_bytes += item_bytes
        normalized.append(item)
    if total_bytes > _MAX_CONTAINER_ARGV_BYTES:
        raise ValueError(
            f"container_argv exceeds {_MAX_CONTAINER_ARGV_BYTES} total UTF-8 bytes"
        )
    executable = normalized[0]
    if executable.startswith("-"):
        raise ValueError("container_argv[0] cannot be an option")
    basename = executable.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    if basename in _DIRECT_SHELL_NAMES:
        raise ValueError("container_argv cannot directly invoke a command shell")
    if basename in {"busybox", "toybox", "env", "env.exe"} and any(
        item.replace("\\", "/").rsplit("/", 1)[-1].casefold()
        in _DIRECT_SHELL_NAMES
        for item in normalized[1:]
    ):
        raise ValueError("container_argv cannot invoke a shell through a command wrapper")
    return tuple(normalized)


def _cpu_limit(value: int) -> str:
    whole, remainder = divmod(value, 1000)
    if not remainder:
        return str(whole)
    return f"{whole}.{remainder:03d}".rstrip("0")


def build_pinned_container_acquisition_request(
    *,
    kind: EvidenceKind,
    source: str,
    source_version: str,
    workspace_root: str | os.PathLike[str],
    docker_executable: str | os.PathLike[str],
    docker_host: str,
    image: str,
    container_argv: tuple[str, ...] | list[str],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_capture_bytes: int = DEFAULT_CAPTURE_BYTES,
    supports_correct_exit_codes: tuple[int, ...] = (0,),
    supports_incorrect_exit_codes: tuple[int, ...] = (1,),
    limits: PinnedContainerLimits = DEFAULT_PINNED_CONTAINER_LIMITS,
) -> AcquisitionRequest:
    """Build one digest-pinned, argv-only Docker acquisition request.

    No arbitrary Docker options are accepted.  This prevents callers from
    weakening the fixed isolation flags through an extra-options escape hatch.
    The returned request must still be executed by :func:`acquire_evidence`,
    whose observations are always non-authoritative.
    """

    if not isinstance(limits, PinnedContainerLimits):
        raise ValueError("limits must be a PinnedContainerLimits")
    executable = _canonical_executable(docker_executable)
    workspace = _canonical_workspace(workspace_root)
    endpoint = _docker_host(docker_host)
    try:
        executable.relative_to(workspace)
    except ValueError:
        pass
    else:
        raise ValueError("docker_executable cannot be inside workspace_root")
    if endpoint.startswith("unix://"):
        socket_path = pathlib.Path(urlsplit(endpoint).path).resolve(strict=False)
        try:
            socket_path.relative_to(workspace)
        except ValueError:
            pass
        else:
            raise ValueError("docker_host socket cannot be inside workspace_root")
    pinned_image = _immutable_image(image)
    command = _container_argv(container_argv)
    mount = f"type=bind,src={workspace},dst=/workspace,readonly"
    argv = (
        str(executable),
        "--host",
        endpoint,
        "run",
        "--rm",
        "--pull",
        "never",
        "--platform",
        "linux",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        (
            "/tmp:rw,noexec,nosuid,nodev,"
            f"size={limits.tmpfs_size_bytes}"
        ),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(limits.pids_limit),
        "--memory",
        str(limits.memory_limit_bytes),
        "--memory-swap",
        str(limits.memory_limit_bytes),
        "--cpus",
        _cpu_limit(limits.cpu_limit_millis),
        "--user",
        "65534:65534",
        "--log-driver",
        "none",
        "--mount",
        mount,
        "--workdir",
        "/workspace",
        "--entrypoint",
        "",
        pinned_image,
        *command,
    )
    return AcquisitionRequest(
        kind=kind,
        source=source,
        source_version=source_version,
        workspace_root=str(workspace),
        working_directory=".",
        argv=argv,
        timeout_seconds=timeout_seconds,
        max_capture_bytes=max_capture_bytes,
        supports_correct_exit_codes=supports_correct_exit_codes,
        supports_incorrect_exit_codes=supports_incorrect_exit_codes,
    )
