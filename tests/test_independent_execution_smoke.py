"""Offline checks for the source-locked SymPy feasibility-execution record."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any

import pytest

SCRIPT = (
    pathlib.Path(__file__).parents[1]
    / "experiments"
    / "independent_execution_smoke"
    / "run_smoke.py"
)
SPEC = importlib.util.spec_from_file_location("independent_execution_smoke", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)


def _encoded(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _stream(text: str) -> dict[str, Any]:
    payload = text.encode()
    return {
        "captured_bytes": len(payload),
        "encoding": "utf-8-replace",
        "read_error": None,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "text": text,
        "total_bytes": len(payload),
        "truncated": False,
    }


def _raw_pair(
    run: dict[str, Any],
    *,
    variant: str,
    stdout_text: str,
) -> tuple[bytes, bytes]:
    stdout = _stream(stdout_text)
    stderr = _stream("")
    run["stdout"] = {
        "captured_bytes": stdout["captured_bytes"],
        "sha256": stdout["sha256"],
        "truncated": False,
    }
    run["stderr"] = {
        "captured_bytes": 0,
        "sha256": stderr["sha256"],
        "truncated": False,
    }
    artifact = {
        "acquisition_id": run["acquisition_id"],
        "argv": [
            "/tmp/bench-cleanser-sympy-15976-py39/bin/python",
            *smoke.EXPECTED_ARGV_TAIL,
        ],
        "execution": {
            "environment_policy": "minimal-allowlist-v1",
            "finished_at": run["finished_at"],
            "outcome": run["outcome"],
            "return_code": run["return_code"],
            "sandbox": "not_provided",
            "setup_error": None,
            "shell": False,
            "started_at": run["started_at"],
            "supplied_environment_keys": list(smoke.EXPECTED_ENVIRONMENT_KEYS),
            "supports_correct_exit_codes": [0],
            "supports_incorrect_exit_codes": [1],
            "timed_out": False,
            "timeout_seconds": 120.0,
            "wall_seconds": run["wall_seconds"],
        },
        "kind": "targeted_execution",
        "request_sha256": run["request_sha256"],
        "source": "sympy-15976-container-free-pilot",
        "stderr": stderr,
        "stdout": stdout,
        "working_directory": ".",
        "workspace_root": f"/tmp/{smoke.EXPECTED_VARIANTS[variant]['workspace_suffix']}",
    }
    artifact_bytes = _encoded(artifact)
    run["storage_bytes"] = len(artifact_bytes)
    run["artifact"]["sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    observation = {
        "acquisition_id": run["acquisition_id"],
        "authoritative": False,
        "cost": {
            "storage_bytes": len(artifact_bytes),
            "wall_seconds": run["wall_seconds"],
        },
        "kind": "targeted_execution",
        "metadata": {
            "artifact_locator": f"file:///tmp/{pathlib.PurePosixPath(run['artifact']['path']).name}",
            "artifact_sha256": run["artifact"]["sha256"],
            "capture_incomplete": False,
            "outcome": run["outcome"],
            "return_code": run["return_code"],
        },
        "privileged_inputs": [],
        "source": "sympy-15976-container-free-pilot",
        "status": run["outcome"],
    }
    observation_bytes = _encoded(observation)
    run["observation"]["sha256"] = hashlib.sha256(observation_bytes).hexdigest()
    return observation_bytes, artifact_bytes


def test_checked_in_manifest_is_strict_and_path_independent() -> None:
    manifest = smoke.load_manifest()
    smoke.verify_manifest(manifest)

    assert manifest["classification"]["stage"] == (
        "post_draft_pre_freeze_feasibility_execution"
    )
    assert manifest["classification"]["prospective"] is False
    assert manifest["classification"]["blinded"] is False
    assert "/private/tmp/" not in SCRIPT.with_name("evidence-manifest.json").read_text()


def test_strict_json_and_schema_reject_duplicate_or_unknown_fields() -> None:
    with pytest.raises(smoke.EvidenceError, match="duplicate JSON key"):
        smoke.strict_json_loads('{"key": 1, "key": 2}')

    manifest = smoke.load_manifest()
    manifest["unreviewed_claim"] = True
    with pytest.raises(smoke.EvidenceError, match="unknown"):
        smoke.verify_manifest(manifest)


def test_critical_input_tampering_is_rejected() -> None:
    manifest = smoke.load_manifest()
    manifest["task"]["patches"][1]["sha256"] = "0" * 64
    with pytest.raises(smoke.EvidenceError, match="patch gpt5 differs"):
        smoke.verify_manifest(manifest)


def test_hosted_prior_cannot_impute_or_replace_an_executed_outcome() -> None:
    manifest = smoke.load_manifest()
    kimi = next(
        group for group in manifest["execution_groups"] if group["variant"] == "kimi_k2"
    )
    kimi["repeats"][0]["provenance"] = "hosted_prior_measurement"
    with pytest.raises(smoke.EvidenceError, match="provenance differs"):
        smoke.verify_manifest(manifest)

    manifest = smoke.load_manifest()
    manifest["execution_groups"] = [
        group for group in manifest["execution_groups"] if group["variant"] != "kimi_k2"
    ]
    with pytest.raises(smoke.EvidenceError, match="five distinct roles"):
        smoke.verify_manifest(manifest)


def test_raw_stream_tampering_and_outcome_relabeling_are_rejected() -> None:
    manifest = smoke.load_manifest()
    group = next(group for group in manifest["execution_groups"] if group["variant"] == "gpt5")
    run = copy.deepcopy(group["repeats"][0])
    passing_output = (
        "sympy/printing/tests/test_mathml.py[39]\n"
        "test_presentation_symbol ok\n"
        "tests finished: 39 passed, in 0.01 seconds\n"
    )
    observation_bytes, artifact_bytes = _raw_pair(
        run, variant="gpt5", stdout_text=passing_output
    )
    smoke._validate_run_evidence(
        run,
        "gpt5",
        observation_bytes,
        artifact_bytes,
        manifest["runtime"],
    )

    tampered = artifact_bytes.replace(b"39 passed", b"38 passed")
    with pytest.raises(smoke.EvidenceError, match="artifact file digest"):
        smoke._validate_run_evidence(
            run,
            "gpt5",
            observation_bytes,
            tampered,
            manifest["runtime"],
        )

    relabeled_run = copy.deepcopy(group["repeats"][0])
    failing_output = (
        "sympy/printing/tests/test_mathml.py[39]\n"
        "test_presentation_symbol F\n"
        "tests finished: 38 passed, 1 failed, in 0.01 seconds\n"
    )
    observation_bytes, artifact_bytes = _raw_pair(
        relabeled_run,
        variant="gpt5",
        stdout_text=failing_output,
    )
    with pytest.raises(smoke.EvidenceError, match="parsed test summary differs"):
        smoke._validate_run_evidence(
            relabeled_run,
            "gpt5",
            observation_bytes,
            artifact_bytes,
            manifest["runtime"],
        )


def test_aggregate_must_be_derived_from_independent_runs() -> None:
    manifest = smoke.load_manifest()
    manifest["aggregate"]["total_storage_bytes"] += 1
    with pytest.raises(smoke.EvidenceError, match="not derived|differs"):
        smoke.verify_manifest(manifest)
