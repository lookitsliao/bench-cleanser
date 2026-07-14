"""Contract tests for the digest-pinned Docker acquisition builder."""

from __future__ import annotations

import os
import pathlib
from typing import Any

import pytest

from bench_cleanser.verification import (
    PINNED_CONTAINER_ADAPTER_VERSION,
    PinnedContainerLimits,
    build_pinned_container_acquisition_request,
)
from bench_cleanser.verification.models import EvidenceKind

_DIGEST = "d" * 64
_IMAGE = f"registry.example/research/verifier@sha256:{_DIGEST}"


def _paths(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    docker.chmod(0o755)
    return workspace, docker


def _build(
    tmp_path: pathlib.Path,
    **overrides: Any,
):
    workspace, docker = _paths(tmp_path)
    values: dict[str, Any] = {
        "kind": EvidenceKind.FULL_EXECUTION,
        "source": "fixture-pinned-container",
        "source_version": "fixture-v1",
        "workspace_root": workspace,
        "docker_executable": docker,
        "docker_host": "unix:///var/run/docker.sock",
        "image": _IMAGE,
        "container_argv": ("python", "-m", "pytest", "-q"),
        "timeout_seconds": 30.0,
        "max_capture_bytes": 4096,
    }
    values.update(overrides)
    return build_pinned_container_acquisition_request(**values)


def test_builder_emits_exact_hardened_argv_without_executing_docker(
    tmp_path: pathlib.Path,
) -> None:
    workspace, docker = _paths(tmp_path)
    marker = tmp_path / "executed"
    docker.write_text(
        f"#!/bin/sh\ntouch {marker}\nexit 99\n",
        encoding="utf-8",
    )
    request = build_pinned_container_acquisition_request(
        kind=EvidenceKind.FULL_EXECUTION,
        source="fixture-pinned-container",
        source_version="fixture-v1",
        workspace_root=workspace,
        docker_executable=docker,
        docker_host="unix:///var/run/docker.sock",
        image=_IMAGE,
        container_argv=("python", "-m", "pytest", "-q"),
        timeout_seconds=30.0,
        max_capture_bytes=4096,
    )

    assert PINNED_CONTAINER_ADAPTER_VERSION == "0.1.0"
    assert request.argv == (
        str(docker),
        "--host",
        "unix:///var/run/docker.sock",
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
        "/tmp:rw,noexec,nosuid,nodev,size=67108864",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "268435456",
        "--memory-swap",
        "268435456",
        "--cpus",
        "1",
        "--user",
        "65534:65534",
        "--log-driver",
        "none",
        "--mount",
        f"type=bind,src={workspace},dst=/workspace,readonly",
        "--workdir",
        "/workspace",
        "--entrypoint",
        "",
        _IMAGE,
        "python",
        "-m",
        "pytest",
        "-q",
    )
    assert request.workspace_root == str(workspace)
    assert request.working_directory == "."
    assert request.kind == EvidenceKind.FULL_EXECUTION
    assert request.source == "fixture-pinned-container"
    assert request.source_version == "fixture-v1"
    assert "authoritative" not in request.to_dict()
    assert not marker.exists()


def test_custom_limits_are_canonicalized_to_numeric_docker_arguments(
    tmp_path: pathlib.Path,
) -> None:
    request = _build(
        tmp_path,
        image=f"sha256:{_DIGEST}",
        limits=PinnedContainerLimits(
            tmpfs_size_bytes=32 * 1024 * 1024,
            pids_limit=64,
            memory_limit_bytes=512 * 1024 * 1024,
            cpu_limit_millis=1250,
        ),
    )

    assert request.argv[1:3] == ("--host", "unix:///var/run/docker.sock")
    assert request.argv[request.argv.index("--tmpfs") + 1].endswith(
        "size=33554432"
    )
    assert request.argv[request.argv.index("--pids-limit") + 1] == "64"
    assert request.argv[request.argv.index("--memory") + 1] == "536870912"
    assert request.argv[request.argv.index("--memory-swap") + 1] == "536870912"
    assert request.argv[request.argv.index("--cpus") + 1] == "1.25"


@pytest.mark.parametrize(
    "image",
    [
        "node:18",
        "latest",
        "sha256:short",
        "sha512:" + "d" * 128,
        "registry.example/repo@sha256:" + "D" * 64,
        "--evil@sha256:" + "d" * 64,
        "registry.example//repo@sha256:" + "d" * 64,
        "registry.example/../repo@sha256:" + "d" * 64,
        "registry.example/repo,@sha256:" + "d" * 64,
        "registry.example/repo:latest@sha256:" + "d" * 64,
        "registry.example:99999/repo@sha256:" + "d" * 64,
        "bad-.example/repo@sha256:" + "d" * 64,
        "registry.example/repo..name@sha256:" + "d" * 64,
        "Registry.example/repo@sha256:" + "d" * 64,
    ],
)
def test_mutable_or_noncanonical_image_references_are_rejected(
    tmp_path: pathlib.Path,
    image: str,
) -> None:
    with pytest.raises(ValueError, match="image"):
        _build(tmp_path, image=image)


@pytest.mark.parametrize(
    "docker_host",
    [
        "",
        "docker-context-name",
        "tcp://127.0.0.1:2375",
        "ssh://builder.example",
        "http://127.0.0.1",
        "unix://relative.sock",
        "unix://localhost/var/run/docker.sock",
        "unix:///var/run/../docker.sock",
        "unix:///var//run/docker.sock",
        "unix:///var/run/docker.sock/",
        "unix:///var/run/docker%2Esock",
        "unix:///var/run/docker.sock?unsafe=true",
        "npipe:////./pipe/../docker_engine",
        "npipe:////./pipe/docker_engine/",
    ],
)
def test_nonlocal_or_ambiguous_daemon_endpoints_are_rejected(
    tmp_path: pathlib.Path,
    docker_host: str,
) -> None:
    with pytest.raises(ValueError, match="docker_host"):
        _build(tmp_path, docker_host=docker_host)


@pytest.mark.parametrize(
    "container_argv",
    [
        [],
        "python",
        ("",),
        ("--entrypoint",),
        ("sh", "-c", "pytest"),
        ("/bin/bash", "-lc", "pytest"),
        ("cmd.exe", "/c", "pytest"),
        ("busybox", "sh", "-c", "pytest"),
        ("/usr/bin/env", "bash", "-lc", "pytest"),
        ("python", "line\nbreak"),
        ("python", object()),
        ("python", "x" * 4097),
        tuple(["python", *("x" for _ in range(256))]),
    ],
)
def test_non_explicit_or_unbounded_container_argv_is_rejected(
    tmp_path: pathlib.Path,
    container_argv: Any,
) -> None:
    with pytest.raises(ValueError, match="container_argv"):
        _build(tmp_path, container_argv=container_argv)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tmpfs_size_bytes": True},
        {"tmpfs_size_bytes": 1024},
        {"tmpfs_size_bytes": 1024 * 1024 * 1024 + 1},
        {"pids_limit": 0},
        {"pids_limit": 1025},
        {"memory_limit_bytes": 1024},
        {"memory_limit_bytes": 16 * 1024 * 1024 * 1024 + 1},
        {"cpu_limit_millis": 99},
        {"cpu_limit_millis": 16_001},
        {
            "tmpfs_size_bytes": 512 * 1024 * 1024,
            "memory_limit_bytes": 256 * 1024 * 1024,
        },
    ],
)
def test_resource_limits_are_typed_bounded_and_internally_consistent(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        PinnedContainerLimits(**kwargs)


def test_builder_rejects_untyped_limits_and_nonrunnable_evidence_kind(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(ValueError, match="PinnedContainerLimits"):
        _build(tmp_path, limits={})

    other = tmp_path / "other"
    with pytest.raises(ValueError, match="evidence kind must be one of"):
        _build(other, kind=EvidenceKind.HUMAN_ADJUDICATION)


def test_noncanonical_host_paths_are_rejected(
    tmp_path: pathlib.Path,
) -> None:
    workspace, docker = _paths(tmp_path)
    with pytest.raises(ValueError, match="docker_executable must be an absolute"):
        build_pinned_container_acquisition_request(
            kind=EvidenceKind.STATIC,
            source="fixture",
            source_version="v1",
            workspace_root=workspace,
            docker_executable="docker",
            docker_host="unix:///var/run/docker.sock",
            image=_IMAGE,
            container_argv=("python", "-m", "compileall", "."),
        )

    docker_link = tmp_path / "docker-link"
    workspace_link = tmp_path / "workspace-link"
    try:
        docker_link.symlink_to(docker)
        workspace_link.symlink_to(workspace, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - depends on Windows policy
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError, match="docker_executable.*canonical"):
        _build(tmp_path / "linked-docker", docker_executable=docker_link)
    with pytest.raises(ValueError, match="workspace_root.*canonical"):
        _build(tmp_path / "linked-workspace", workspace_root=workspace_link)


def test_mount_delimiter_and_filesystem_root_are_rejected(
    tmp_path: pathlib.Path,
) -> None:
    workspace, docker = _paths(tmp_path)
    comma_workspace = tmp_path / "unsafe,workspace"
    comma_workspace.mkdir()
    with pytest.raises(ValueError, match="unsafe for Docker --mount"):
        build_pinned_container_acquisition_request(
            kind=EvidenceKind.STATIC,
            source="fixture",
            source_version="v1",
            workspace_root=comma_workspace,
            docker_executable=docker,
            docker_host="unix:///var/run/docker.sock",
            image=_IMAGE,
            container_argv=("python", "-m", "compileall", "."),
        )
    with pytest.raises(ValueError, match="filesystem root"):
        build_pinned_container_acquisition_request(
            kind=EvidenceKind.STATIC,
            source="fixture",
            source_version="v1",
            workspace_root=pathlib.Path(pathlib.Path.cwd().anchor),
            docker_executable=docker,
            docker_host="unix:///var/run/docker.sock",
            image=_IMAGE,
            container_argv=("python", "-m", "compileall", "."),
        )


def test_docker_cli_and_socket_cannot_be_sourced_from_untrusted_workspace(
    tmp_path: pathlib.Path,
) -> None:
    workspace, docker = _paths(tmp_path)
    workspace_docker = workspace / "docker"
    workspace_docker.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    workspace_docker.chmod(0o755)
    common: dict[str, Any] = {
        "kind": EvidenceKind.STATIC,
        "source": "fixture",
        "source_version": "v1",
        "workspace_root": workspace,
        "docker_host": "unix:///var/run/docker.sock",
        "image": _IMAGE,
        "container_argv": ("python", "-m", "compileall", "."),
    }

    with pytest.raises(ValueError, match="cannot be inside workspace_root"):
        build_pinned_container_acquisition_request(
            **common,
            docker_executable=workspace_docker,
        )

    workspace_socket = f"unix://{workspace}/docker.sock"
    with pytest.raises(ValueError, match="socket cannot be inside workspace_root"):
        build_pinned_container_acquisition_request(
            **{**common, "docker_host": workspace_socket},
            docker_executable=docker,
        )

    podman = tmp_path / "podman"
    podman.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    podman.chmod(0o755)
    with pytest.raises(ValueError, match="must name the Docker CLI"):
        build_pinned_container_acquisition_request(
            **common,
            docker_executable=podman,
        )


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable permission contract")
def test_docker_cli_must_be_executable(tmp_path: pathlib.Path) -> None:
    workspace, docker = _paths(tmp_path)
    docker.chmod(0o644)
    with pytest.raises(ValueError, match="must be executable"):
        build_pinned_container_acquisition_request(
            kind=EvidenceKind.STATIC,
            source="fixture",
            source_version="v1",
            workspace_root=workspace,
            docker_executable=docker,
            docker_host="unix:///var/run/docker.sock",
            image=_IMAGE,
            container_argv=("python", "-m", "compileall", "."),
        )
