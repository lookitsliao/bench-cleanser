"""Run a reproducible synthetic integration study across evidence modalities.

This is deliberately a plumbing/oracle-strength pilot, not research validation.
It uses hand-authored candidates with known labels to exercise real static,
targeted, inherited-suite, repeated full, and hardened-oracle acquisitions.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import subprocess
from datetime import UTC, datetime
from typing import Any

from bench_cleanser.verification._io import atomic_write, strict_json_dumps, strict_json_loads
from bench_cleanser.verification.acquire import AcquisitionRequest, acquire_evidence
from bench_cleanser.verification.models import EvidenceKind, EvidenceObservation, EvidenceStatus

REPORT_SCHEMA_VERSION = "seed-study-report-1"
FIXTURE_DIRECTORY = pathlib.Path(__file__).parent / "fixtures" / "normalize_username"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the synthetic verification-acquisition integration pilot; "
            "results are not research-valid performance evidence"
        )
    )
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument("--runtime", choices=("local", "docker"), default="local")
    parser.add_argument("--node", default="node", help="Local Node executable")
    parser.add_argument("--docker", default="docker", help="Docker CLI executable")
    parser.add_argument(
        "--docker-host",
        help="Explicit Docker daemon URI; required because acquisitions discard ambient HOME",
    )
    parser.add_argument("--image", default="node:18")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def _fixture_digest(root: pathlib.Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _run_identity(args: argparse.Namespace) -> tuple[str, str]:
    if args.runtime == "local":
        executable = shutil.which(args.node)
        if executable is None:
            raise RuntimeError(f"Node executable not found: {args.node!r}")
        result = subprocess.run(
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return executable, result.stdout.strip()

    if not args.docker_host:
        raise ValueError("--docker-host is required for the docker runtime")
    executable = shutil.which(args.docker)
    if executable is None:
        raise RuntimeError(f"Docker executable not found: {args.docker!r}")
    result = subprocess.run(
        [
            executable,
            "--host",
            args.docker_host,
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            args.image,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    image_id = result.stdout.strip()
    if not image_id.startswith("sha256:"):
        raise RuntimeError("Docker image inspect did not return an immutable image ID")
    return executable, image_id


def _command(
    args: argparse.Namespace,
    executable: str,
    workspace: pathlib.Path,
    node_arguments: tuple[str, ...],
) -> tuple[str, ...]:
    if args.runtime == "local":
        return (executable, *node_arguments)
    assert args.docker_host is not None
    return (
        executable,
        "--host",
        args.docker_host,
        "run",
        "--rm",
        "--pull",
        "never",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--user",
        "65534:65534",
        "--mount",
        f"type=bind,src={workspace},dst=/work,readonly",
        "--workdir",
        "/work",
        args.image,
        "node",
        *node_arguments,
    )


def _prepare_workspace(candidate: pathlib.Path, destination: pathlib.Path) -> None:
    destination.mkdir(parents=True)
    shutil.copyfile(candidate, destination / "solution.js")
    for test_name in ("visible.test.js", "inherited.test.js", "hardened.test.js"):
        shutil.copyfile(FIXTURE_DIRECTORY / test_name, destination / test_name)


def _acquire(
    *,
    args: argparse.Namespace,
    executable: str,
    runtime_version: str,
    workspace: pathlib.Path,
    artifact_directory: pathlib.Path,
    kind: EvidenceKind,
    node_arguments: tuple[str, ...],
) -> EvidenceObservation:
    source = "seed-study-node-local" if args.runtime == "local" else "seed-study-node-docker"
    request = AcquisitionRequest(
        kind=kind,
        source=source,
        source_version=runtime_version,
        workspace_root=str(workspace),
        argv=_command(args, executable, workspace, node_arguments),
        timeout_seconds=args.timeout_seconds,
        max_capture_bytes=32 * 1024,
    )
    return acquire_evidence(request, artifact_directory=artifact_directory)


def _consensus(observations: list[EvidenceObservation]) -> bool | None:
    statuses = {observation.status for observation in observations}
    if statuses == {EvidenceStatus.SUPPORTS_CORRECT}:
        return True
    if statuses == {EvidenceStatus.SUPPORTS_INCORRECT}:
        return False
    return None


def _metrics(
    labels: dict[str, bool],
    by_candidate: dict[str, dict[str, list[EvidenceObservation]]],
    modality: str,
) -> dict[str, Any]:
    counts = {
        "true_accept": 0,
        "false_accept": 0,
        "true_reject": 0,
        "false_reject": 0,
        "inconclusive": 0,
    }
    wall_seconds = 0.0
    storage_bytes = 0
    acquisitions = 0
    for candidate_name, truth in labels.items():
        observations = by_candidate[candidate_name][modality]
        acquisitions += len(observations)
        wall_seconds += sum(item.cost.wall_seconds for item in observations)
        storage_bytes += sum(item.cost.storage_bytes for item in observations)
        prediction = _consensus(observations)
        if prediction is None:
            counts["inconclusive"] += 1
        elif prediction and truth:
            counts["true_accept"] += 1
        elif prediction and not truth:
            counts["false_accept"] += 1
        elif not prediction and truth:
            counts["false_reject"] += 1
        else:
            counts["true_reject"] += 1
    conclusive = len(labels) - counts["inconclusive"]
    accepted = counts["true_accept"] + counts["false_accept"]
    return {
        "counts": counts,
        "candidates": len(labels),
        "acquisitions": acquisitions,
        "coverage": conclusive / len(labels),
        "false_accept_risk_among_accepted": (
            counts["false_accept"] / accepted if accepted else None
        ),
        "total_wall_seconds": wall_seconds,
        "total_storage_bytes": storage_bytes,
    }


def run(args: argparse.Namespace) -> pathlib.Path:
    output_value = args.output_dir
    if not isinstance(output_value, pathlib.Path):
        raise TypeError("output_dir must be a pathlib.Path")
    output = output_value.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    workspace_root = output / "workspaces"
    artifact_root = output / "artifacts"
    labels_value = strict_json_loads((FIXTURE_DIRECTORY / "labels.json").read_text())
    labels = labels_value.get("labels") if isinstance(labels_value, dict) else None
    if not isinstance(labels, dict) or not labels or any(
        not isinstance(name, str) or not isinstance(truth, bool)
        for name, truth in labels.items()
    ):
        raise ValueError("fixture labels must be a non-empty string-to-boolean object")

    executable, runtime_version = _run_identity(args)
    by_candidate: dict[str, dict[str, list[EvidenceObservation]]] = {}
    plan = {
        "static": (EvidenceKind.STATIC, ("--check", "solution.js"), 1),
        "targeted": (
            EvidenceKind.TARGETED_EXECUTION,
            ("--test", "visible.test.js"),
            1,
        ),
        "full": (
            EvidenceKind.FULL_EXECUTION,
            ("--test", "inherited.test.js"),
            2,
        ),
        "hardened": (
            EvidenceKind.ORACLE_HARDENING,
            ("--test", "hardened.test.js"),
            1,
        ),
    }
    for candidate_name in sorted(labels):
        candidate_path = FIXTURE_DIRECTORY / "candidates" / candidate_name
        if not candidate_path.is_file():
            raise ValueError(f"missing candidate fixture: {candidate_name}")
        workspace = workspace_root / candidate_path.stem
        _prepare_workspace(candidate_path, workspace)
        candidate_events: dict[str, list[EvidenceObservation]] = {}
        for modality, (kind, arguments, replicates) in plan.items():
            candidate_events[modality] = [
                _acquire(
                    args=args,
                    executable=executable,
                    runtime_version=runtime_version,
                    workspace=workspace,
                    artifact_directory=artifact_root / candidate_path.stem,
                    kind=kind,
                    node_arguments=arguments,
                )
                for _ in range(replicates)
            ]
        by_candidate[candidate_name] = candidate_events

    modality_metrics = {
        modality: _metrics(labels, by_candidate, modality) for modality in plan
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "study_status": "synthetic_integration_pilot_not_research_validation",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "fixture": {
            "task_id": labels_value.get("task_id"),
            "sha256": _fixture_digest(FIXTURE_DIRECTORY),
            "candidate_count": len(labels),
            "correct_candidates": sum(labels.values()),
            "incorrect_candidates": len(labels) - sum(labels.values()),
            "labels": dict(sorted(labels.items())),
        },
        "runtime": {
            "kind": args.runtime,
            "version": runtime_version,
            "image": args.image if args.runtime == "docker" else None,
            "network_during_acquisitions": "disabled" if args.runtime == "docker" else "not_restricted",
        },
        "modality_metrics": modality_metrics,
        "observations": {
            candidate: {
                modality: [observation.to_dict() for observation in observations]
                for modality, observations in events.items()
            }
            for candidate, events in by_candidate.items()
        },
        "limitations": [
            "Candidates and ground truth are hand-authored rather than sampled from agents.",
            "The task is a single JavaScript micro-repository and cannot support transfer claims.",
            "Ground truth is specification-derived, not blinded multi-annotator adjudication.",
            "No learned router, randomized collection policy, or downstream SFT/RL model is evaluated.",
            "Wall time is an integration measurement on one machine, not a general cost estimate.",
        ],
    }
    report_path = output / "report.json"
    atomic_write(report_path, strict_json_dumps(report, indent=2) + "\n")
    return report_path


def main() -> None:
    try:
        report = run(_parse_args())
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        raise SystemExit(f"seed study failed: {exc}") from exc
    print(report)


if __name__ == "__main__":
    main()
