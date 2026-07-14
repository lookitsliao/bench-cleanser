"""Reference-free candidate risk-profile construction tests."""

from __future__ import annotations

import inspect
import io
import json
import sys

import pytest

import bench_cleanser.verification._io as verification_io
import bench_cleanser.verification.manifest as verification_manifest
from bench_cleanser.verification import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RouteAction,
    build_candidate_manifest,
)
from bench_cleanser.verification._io import atomic_write
from bench_cleanser.verification.manifest import main
from bench_cleanser.verification.router import ConservativeRouter

_PYTHON_PATCH = """\
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return old()
+return new()
diff --git a/tests/test_app.py b/tests/test_app.py
--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -1 +1 @@
-assert old()
+assert new()
"""

_RISKY_RUST_PATCH = """\
diff --git a/Cargo.toml b/Cargo.toml
--- a/Cargo.toml
+++ b/Cargo.toml
@@ -1 +1 @@
-version = "1"
+version = "2"
diff --git a/src/auth.rs b/src/auth.rs
--- a/src/auth.rs
+++ b/src/auth.rs
@@ -1 +1 @@
-let value = old();
+let value = Mutex::new(token);
diff --git a/migrations/001.sql b/migrations/001.sql
--- a/migrations/001.sql
+++ b/migrations/001.sql
@@ -1 +1 @@
-SELECT 1;
+ALTER TABLE users ADD secret TEXT;
"""

_HEADER_LIKE_CONTENT_PATCH = """\
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
--- /etc/passwd
+++ ../../not-a-header
-ordinary_old
+ordinary_new
"""


def _build(patch: str = _PYTHON_PATCH):
    return build_candidate_manifest(
        instance_id="owner__repo-candidate",
        candidate_patch=patch,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        provenance={"dataset_revision": "fixture-v1"},
    )


def test_python_candidate_profile_is_deterministic_and_reference_free() -> None:
    first = _build()
    second = _build()

    assert first.to_dict() == second.to_dict()
    assert first.canonical_digest() == second.canonical_digest()
    assert first.candidate_id.startswith("sha256:")
    assert first.risk_profile.language == "python"
    assert first.risk_profile.files_changed == 2
    assert first.risk_profile.lines_changed == 4
    assert first.risk_profile.touches_tests is True
    assert first.risk_profile.compiled_language is False
    assert first.evidence == []
    assert "gold_patch" not in json.dumps(first.to_dict())
    assert "hidden_tests" not in json.dumps(first.to_dict())
    parameters = inspect.signature(build_candidate_manifest).parameters
    assert "reference_patch" not in parameters
    assert "gold_patch" not in parameters


def test_risky_compiled_candidate_sets_declared_preexecution_features() -> None:
    manifest = _build(_RISKY_RUST_PATCH)
    profile = manifest.risk_profile

    assert profile.language == "mixed"
    assert profile.compiled_language is True
    assert profile.native_dependencies is True
    assert profile.touches_dependency_or_build_files is True
    assert profile.touches_schema_or_migration is True
    assert profile.touches_security_or_auth is True
    assert profile.touches_concurrency is True

    decision = ConservativeRouter().route(manifest)
    assert decision.action == RouteAction.RUN_STATIC
    assert decision.candidate_risk >= 0.5


def test_test_touching_candidate_increases_candidate_and_verifier_risk() -> None:
    manifest = _build()

    decision = ConservativeRouter().route(manifest)

    assert decision.candidate_risk >= 0.1
    assert decision.verifier_risk >= 0.15


def test_candidate_digest_changes_when_patch_changes() -> None:
    assert _build().candidate_id != _build(_PYTHON_PATCH.replace("new()", "other()", 1)).candidate_id


def test_header_like_changed_content_is_not_parsed_as_a_file_header() -> None:
    manifest = _build(_HEADER_LIKE_CONTENT_PATCH)

    assert manifest.risk_profile.files_changed == 1
    assert manifest.risk_profile.lines_changed == 4
    assert manifest.provenance["changed_files_sha256"]


def test_git_empty_file_sections_without_hunks_are_counted() -> None:
    patch = """diff --git a/empty-added.txt b/empty-added.txt
new file mode 100644
index 0000000000..e69de29bb2
diff --git a/empty-deleted.txt b/empty-deleted.txt
deleted file mode 100644
index e69de29bb2..0000000000
diff --git a/app.py b/app.py
index 7898192261..6178079822 100644
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-before = 1
+after = 2
"""

    manifest = build_candidate_manifest(
        instance_id="empty-file-metadata",
        candidate_patch=patch,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        provenance={"repository": "owner/repo"},
    )

    assert manifest.risk_profile.files_changed == 3
    assert manifest.risk_profile.lines_changed == 2


@pytest.mark.parametrize(
    "metadata",
    [
        "new file mode 100644\nindex 0000000000..deadbee123\n",
        "new file mode 100644\nindex 0000000000..e69de29bb2\nuntrusted metadata\n",
        "new file mode 100644\nindex 0000000000..e69de29bb2 100644\n",
        "new file mode 100644\ndeleted file mode 100644\n"
        "index 0000000000..e69de29bb2\n",
    ],
)
def test_no_hunk_section_requires_exact_empty_blob_metadata(metadata: str) -> None:
    patch = f"diff --git a/empty.txt b/empty.txt\n{metadata}"

    with pytest.raises(ValueError):
        build_candidate_manifest(
            instance_id="invalid-empty-file-metadata",
            candidate_patch=patch,
            lifecycle_stage=LifecycleStage.ROLLOUT,
            provenance={"repository": "owner/repo"},
        )


@pytest.mark.parametrize(
    "patch",
    [
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n",
        "diff --git a/app.py b/app.py\n--- a/app.py\n--- /etc/passwd\n+++ b/app.py\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --git a/app.py b/app.py\n--- a/other.py\n+++ b/app.py\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --git a/app.py b/app.py\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ malformed\n-a\n+b\n",
    ],
)
def test_candidate_builder_rejects_incomplete_or_contradictory_diff_state(
    patch: str,
) -> None:
    with pytest.raises(ValueError):
        _build(patch)


@pytest.mark.parametrize(
    "patch",
    [
        "diff --git a/good.py b/../../secret\n",
        "--- /etc/passwd\n+++ b/good.py\n",
        'diff --git a/"../secret" b/good.py\n',
        "this is not a unified diff",
    ],
)
def test_candidate_builder_rejects_unsafe_or_malformed_patch(patch: str) -> None:
    with pytest.raises(ValueError):
        _build(patch)


def test_candidate_builder_rejects_reserved_provenance() -> None:
    with pytest.raises(ValueError, match="reserved"):
        build_candidate_manifest(
            instance_id="i",
            candidate_patch="",
            lifecycle_stage=LifecycleStage.TRAINING,
            provenance={"candidate_patch_sha256": "forged"},
        )


@pytest.mark.parametrize(
    "key",
    [
        "gold_patch_digest",
        "referenceCommit",
        "hidden-tests-version",
        "ground_truth",
        "execution_outcome",
        "resolved",
        "human_verdict",
        "reward_score",
        "ref_patch_result",
        "future_commit",
    ],
)
def test_candidate_builder_rejects_broad_privileged_provenance_keys(key: str) -> None:
    with pytest.raises(ValueError, match="privileged truth or outcome"):
        build_candidate_manifest(
            instance_id="i",
            candidate_patch="",
            lifecycle_stage=LifecycleStage.TRAINING,
            provenance={key: "leak"},
        )


def test_candidate_builder_rejects_blank_or_normalized_duplicate_provenance() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        build_candidate_manifest(
            instance_id="i",
            candidate_patch="",
            lifecycle_stage=LifecycleStage.TRAINING,
            provenance={"dataset_revision": "  "},
        )
    with pytest.raises(ValueError, match="duplicate normalized"):
        build_candidate_manifest(
            instance_id="i",
            candidate_patch="",
            lifecycle_stage=LifecycleStage.TRAINING,
            provenance={"dataset-revision": "one", "Dataset Revision": "two"},
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"instance_id": ""},
        {"candidate_patch": None},
        {"lifecycle_stage": "rollout"},
        {"provenance": {}},
        {"provenance": {1: "value"}},
        {"provenance": {"dataset": 1}},
        {"language": 1},
        {"language": "  "},
    ],
)
def test_candidate_builder_rejects_invalid_api_types(overrides) -> None:
    values = {
        "instance_id": "i",
        "candidate_patch": "",
        "lifecycle_stage": LifecycleStage.TRAINING,
        "provenance": {"dataset": "fixture"},
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        build_candidate_manifest(**values)


def test_candidate_builder_declares_availability_without_making_evidence() -> None:
    manifest = build_candidate_manifest(
        instance_id="i",
        candidate_patch="",
        lifecycle_stage=LifecycleStage.TRAINING,
        provenance={"dataset_revision": "fixture"},
        generated_tests=True,
        targeted_execution_available=False,
        full_execution_available=False,
        oracle_hardening_available=True,
    )

    assert manifest.risk_profile.generated_tests is True
    assert manifest.risk_profile.targeted_execution_available is False
    assert manifest.risk_profile.full_execution_available is False
    assert manifest.risk_profile.oracle_hardening_available is True
    assert manifest.evidence == []


def test_manifest_cli_reads_patch_and_emits_json(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_path = tmp_path / "candidate.diff"
    patch_path.write_text(_PYTHON_PATCH, encoding="utf-8")

    main([
        "owner__repo-candidate",
        str(patch_path),
        "--stage",
        "evaluation",
        "--provenance",
        "dataset_revision=fixture-v1",
    ])

    result = json.loads(capsys.readouterr().out)
    assert result["lifecycle_stage"] == "evaluation"
    assert result["risk_profile"]["files_changed"] == 2
    assert result["evidence"] == []


def test_manifest_cli_supports_stdin_and_atomic_output(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "nested" / "manifest.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(_PYTHON_PATCH))

    main([
        "owner__repo-candidate",
        "-",
        "--stage",
        "training",
        "--provenance",
        "dataset_revision=fixture-v1",
        "--output",
        str(output_path),
    ])

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["lifecycle_stage"] == "training"
    assert list(output_path.parent.glob(f".{output_path.name}.*.tmp")) == []


@pytest.mark.parametrize(
    "provenance",
    ["missing-separator", "=missing-key", "missing-value=", "same=1"],
)
def test_manifest_cli_rejects_bad_or_duplicate_provenance(
    tmp_path,
    provenance: str,
) -> None:
    patch_path = tmp_path / "candidate.diff"
    patch_path.write_text(_PYTHON_PATCH, encoding="utf-8")
    args = [
        "i",
        str(patch_path),
        "--stage",
        "training",
        "--provenance",
        provenance,
    ]
    if provenance == "same=1":
        args.extend(["--provenance", "same=2"])

    with pytest.raises(SystemExit, match="manifest construction failed"):
        main(args)


def test_atomic_write_removes_temporary_file_when_replace_fails(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "result.json"

    def fail_replace(source, destination) -> None:
        raise OSError("fixture replace failure")

    monkeypatch.setattr(verification_io.os, "replace", fail_replace)
    with pytest.raises(OSError, match="fixture replace failure"):
        atomic_write(target, "{}")

    assert not target.exists()
    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_strict_json_writer_rejects_nonstandard_nan() -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        verification_io.strict_json_dumps({"not_json": float("nan")})


def test_manifest_cli_reports_output_write_failure_cleanly(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_path = tmp_path / "candidate.diff"
    patch_path.write_text(_PYTHON_PATCH, encoding="utf-8")

    def fail_write(path, content) -> None:
        raise OSError("fixture output failure")

    monkeypatch.setattr(verification_manifest, "atomic_write", fail_write)
    with pytest.raises(SystemExit, match="manifest construction failed: fixture output failure"):
        verification_manifest.main([
            "i",
            str(patch_path),
            "--stage",
            "training",
            "--provenance",
            "dataset_revision=fixture",
            "--output",
            str(tmp_path / "result.json"),
        ])


def test_manifest_with_evidence_still_routes_from_caller_supplied_state() -> None:
    manifest = _build()
    manifest.add_evidence(EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.SUPPORTS_CORRECT,
        source="external-static-check",
    ))

    assert ConservativeRouter().route(manifest).action == RouteAction.RUN_SEMANTIC
