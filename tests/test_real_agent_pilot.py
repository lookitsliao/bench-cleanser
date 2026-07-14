"""Offline regression tests for the source-locked real-agent pilot runner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys

import pytest

from bench_cleanser.verification._io import strict_json_dumps

SCRIPT = (
    pathlib.Path(__file__).parents[1]
    / "experiments"
    / "real_agent_pilot"
    / "run_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("real_agent_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pilot
SPEC.loader.exec_module(pilot)


def _bytes(value: object) -> bytes:
    return (strict_json_dumps(value, indent=2) + "\n").encode()


def _patch(name: str) -> bytes:
    return (
        f"diff --git a/{name}.py b/{name}.py\n"
        f"--- a/{name}.py\n"
        f"+++ b/{name}.py\n"
        "@@ -1 +1 @@\n"
        "-old = 1\n"
        "+old = 2\n"
    ).encode()


def _report(instance_id: str, resolved: bool) -> bytes:
    return _bytes({
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
            },
        }
    })


def _trajectory() -> bytes:
    return _bytes([{
        "action": "finish",
        "args": {
            "task_completed": "true",
            "final_thought": "I successfully fixed and resolved the issue.",
        },
    }])


def _artifact(url_name: str, payload: bytes) -> dict[str, object]:
    return {
        "url": (
            "https://swe-bench-submissions.s3.amazonaws.com/verified/fixture/"
            + url_name
        ),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _fixture(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    artifacts = tmp_path / "artifacts"
    candidates = []
    for index, resolved in enumerate((True, False), start=1):
        instance_id = f"owner__repo-{index}"
        patch = _patch(f"module_{index}")
        report = _report(instance_id, resolved)
        trajectory = _trajectory()
        directory = artifacts / instance_id
        directory.mkdir(parents=True)
        (directory / "patch.diff").write_bytes(patch)
        (directory / "report.json").write_bytes(report)
        (directory / "trajectory.json").write_bytes(trajectory)
        candidates.append({
            "instance_id": instance_id,
            "repository": "owner/repo",
            "base_commit": str(index) * 40,
            "official_resolved": resolved,
            "artifacts": {
                "patch.diff": _artifact(f"{instance_id}/patch.diff", patch),
                "report.json": _artifact(f"{instance_id}/report.json", report),
                "trajectory.json": _artifact(
                    f"{instance_id}/trajectory.json",
                    trajectory,
                ),
            },
        })
    cohort = {
        "schema_version": pilot.PILOT_SCHEMA_VERSION,
        "study_id": "fixture-study",
        "source": {
            "repository": "SWE-bench/experiments",
            "revision": "a" * 40,
            "submission_id": "fixture-agent",
            "submission_checked": False,
            "submission_metadata_url": "https://github.com/fixture",
            "selection": "offline fixture",
        },
        "candidates": candidates,
    }
    cohort_path = tmp_path / "cohort.json"
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")
    return cohort_path, artifacts


def test_real_agent_pilot_reports_counts_without_claiming_validity(
    tmp_path: pathlib.Path,
) -> None:
    cohort, artifacts = _fixture(tmp_path)

    result = pilot.analyze_cohort(cohort, artifacts)

    assert result["metrics"] == {
        "candidate_count": 2,
        "official_resolved_count": 1,
        "official_unresolved_count": 1,
        "optimistic_claim_accept_count": 2,
        "optimistic_claim_false_accept_count": 1,
        "optimistic_claim_false_accept_rate": 0.5,
    }
    assert result["scientific_status"]["supports_hypotheses_h1_to_h6"] is False
    assert result["candidates"][0]["candidate_id"].startswith("sha256:")
    assert result["candidates"][1]["optimistic_claim_false_accept"] is True


def test_pilot_rejects_tampered_bytes_and_result_drift(tmp_path: pathlib.Path) -> None:
    cohort, artifacts = _fixture(tmp_path)
    tampered = artifacts / "owner__repo-1" / "patch.diff"
    tampered.write_bytes(tampered.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="size mismatch"):
        pilot.analyze_cohort(cohort, artifacts)

    cohort, artifacts = _fixture(tmp_path / "drift")
    report_path = artifacts / "owner__repo-1" / "report.json"
    changed = _report("owner__repo-1", False)
    report_path.write_bytes(changed)
    decoded = json.loads(cohort.read_text(encoding="utf-8"))
    decoded["candidates"][0]["artifacts"]["report.json"] = _artifact(
        "owner__repo-1/report.json",
        changed,
    )
    cohort.write_text(json.dumps(decoded), encoding="utf-8")
    with pytest.raises(ValueError, match="official result drift"):
        pilot.analyze_cohort(cohort, artifacts)


def test_pilot_rejects_unallowlisted_sources_and_duplicate_finish(
    tmp_path: pathlib.Path,
) -> None:
    cohort, artifacts = _fixture(tmp_path)
    decoded = json.loads(cohort.read_text(encoding="utf-8"))
    decoded["candidates"][0]["artifacts"]["patch.diff"]["url"] = (
        "https://example.com/patch.diff"
    )
    cohort.write_text(json.dumps(decoded), encoding="utf-8")
    with pytest.raises(ValueError, match="not allowlisted"):
        pilot.analyze_cohort(cohort, artifacts)

    cohort, artifacts = _fixture(tmp_path / "finish")
    trajectory_path = artifacts / "owner__repo-1" / "trajectory.json"
    duplicate = _bytes([
        {"action": "finish", "args": {"task_completed": True, "final_thought": "fixed"}},
        {"action": "finish", "args": {"task_completed": True, "final_thought": "fixed"}},
    ])
    trajectory_path.write_bytes(duplicate)
    decoded = json.loads(cohort.read_text(encoding="utf-8"))
    decoded["candidates"][0]["artifacts"]["trajectory.json"] = _artifact(
        "owner__repo-1/trajectory.json",
        duplicate,
    )
    cohort.write_text(json.dumps(decoded), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one finish"):
        pilot.analyze_cohort(cohort, artifacts)
