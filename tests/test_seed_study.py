"""Regression coverage for the synthetic acquisition integration pilot."""

from __future__ import annotations

import argparse
import pathlib
import shutil

import pytest

from bench_cleanser.verification._io import strict_json_loads
from experiments.seed_study.run_seed_study import FIXTURE_DIRECTORY, _fixture_digest, run


def test_seed_fixture_is_complete_and_digest_bound() -> None:
    labels = strict_json_loads((FIXTURE_DIRECTORY / "labels.json").read_text())["labels"]

    assert len(labels) == 8
    assert sum(labels.values()) == 2
    assert set(labels) == {
        path.name for path in (FIXTURE_DIRECTORY / "candidates").glob("*.js")
    }
    assert _fixture_digest(FIXTURE_DIRECTORY) == (
        # Pinned public fixture SHA-256, not a credential.
        "69dee7dbd276f073f3b84870750f594035c245737ebdf3699e74299384fa24ce"  # pragma: allowlist secret
    )


def test_local_seed_study_exposes_weak_oracle_and_hardening(
    tmp_path: pathlib.Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the seed-study integration smoke")
    output = tmp_path / "study"
    report_path = run(
        argparse.Namespace(
            output_dir=output,
            runtime="local",
            node=node,
            docker="docker",
            docker_host=None,
            image="node:18",
            timeout_seconds=10.0,
        )
    )

    report = strict_json_loads(report_path.read_text())
    assert report["study_status"] == "synthetic_integration_pilot_not_research_validation"
    metrics = report["modality_metrics"]
    assert metrics["static"]["counts"]["false_accept"] == 5
    assert metrics["targeted"]["counts"]["false_accept"] == 3
    assert metrics["full"]["counts"]["false_accept"] == 2
    assert metrics["hardened"]["counts"]["false_accept"] == 0
    assert metrics["full"]["acquisitions"] == 16
    assert len(list((output / "artifacts").glob("*/*.json"))) == 40
