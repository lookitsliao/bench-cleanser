"""Strict, corpus-joined evaluation 0.4.0 tests."""

from __future__ import annotations

import io
import json
from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

import bench_cleanser.verification.evaluate as verification_evaluate
from bench_cleanser.verification.corpus import (
    CandidateCorrectness,
    EvidenceValidity,
    TaskValidity,
    VerificationGapRecord,
    corpus_digest,
)
from bench_cleanser.verification.evaluate import (
    build_evaluation_report,
    load_outcomes,
    main,
)
from tests.test_verification_corpus import _record


def _records() -> list[VerificationGapRecord]:
    return [
        _record(),
        _record(
            instance_id="owner__repo-2",
            candidate_id="sha256:" + "f" * 64,
            candidate_correctness=CandidateCorrectness.INCORRECT,
        ),
        _record(
            instance_id="owner__repo-3",
            candidate_id="sha256:" + "1" * 64,
            task_validity=TaskValidity.INVALID,
            candidate_correctness=CandidateCorrectness.NOT_APPLICABLE,
        ),
        _record(
            instance_id="owner__repo-4",
            candidate_id="sha256:" + "2" * 64,
            task_validity=TaskValidity.INDETERMINATE,
            candidate_correctness=CandidateCorrectness.INDETERMINATE,
        ),
    ]


def _row(
    record: VerificationGapRecord,
    records: list[VerificationGapRecord],
    *,
    action: str | None = None,
    policy_id: str = "router",
    policy_version: str = "1",
    run_id: str = "run-1",
    seed: int = 11,
    calibration_id: str = "calibration-1",
    subgroup: str = "python",
) -> dict[str, Any]:
    task_validity = record.task_adjudication.task_validity
    correctness = record.candidate_adjudication.candidate_correctness
    default_action = {
        CandidateCorrectness.CORRECT: "accept",
        CandidateCorrectness.INCORRECT: "reject",
        CandidateCorrectness.NOT_APPLICABLE: "abstain",
        CandidateCorrectness.INDETERMINATE: "abstain",
    }[correctness]
    probability_task_valid = {
        TaskValidity.VALID: 0.9,
        TaskValidity.INVALID: 0.1,
        TaskValidity.INDETERMINATE: 0.5,
    }[task_validity]
    probability_correct = {
        CandidateCorrectness.CORRECT: 0.9,
        CandidateCorrectness.INCORRECT: 0.1,
        CandidateCorrectness.NOT_APPLICABLE: 0.5,
        CandidateCorrectness.INDETERMINATE: 0.5,
    }[correctness]
    return {
        "instance_id": record.manifest.instance_id,
        "candidate_id": record.manifest.candidate_id,
        "probability_task_valid": probability_task_valid,
        "probability_correct_given_valid_task": probability_correct,
        "action": action or default_action,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "run_id": run_id,
        "seed": seed,
        "calibration_id": calibration_id,
        "corpus_id": "verification-gap",
        "corpus_revision": "sha256:corpus-v2",
        "corpus_digest": corpus_digest(records),
        "corpus_record_sha256": record.canonical_digest(),
        "acquisition_trajectory_digest": record.acquisition_trajectory_digest(),
        "execution_count": 0,
        "cost": 1.0,
        "subgroup": subgroup,
    }


def _rows(records: list[VerificationGapRecord] | None = None) -> list[dict[str, Any]]:
    resolved = records or _records()
    rows = [_row(record, resolved) for record in resolved]
    if len(rows) > 1:
        rows[1]["subgroup"] = "rust"
        rows[1]["execution_count"] = 1
        rows[1]["cost"] = 10.0
    return rows


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(row) for row in rows)


def _corpus_jsonl(records: list[VerificationGapRecord]) -> str:
    return "\n".join(json.dumps(record.to_dict()) for record in records) + "\n"


def _report(
    records: list[VerificationGapRecord] | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_records = records or _records()
    resolved_rows = rows or _rows(resolved_records)
    return build_evaluation_report(
        load_outcomes(io.StringIO(_jsonl(resolved_rows))),
        resolved_records,
        calibration_bins=2,
    )


def test_report_joins_truth_and_separates_task_candidate_and_verifier_metrics() -> None:
    records = _records()
    report = _report(records)

    assert report["schema_version"] == "0.4.0"
    assert report["input"]["truth_source"] == (
        "exact_corpus_0.5.0_record_and_corpus_digest_join"
    )
    assert report["input"]["corpus_digest"] == corpus_digest(records)
    assert report["input"]["corpus_record_count"] == 4
    assert report["input"]["joined_unique_corpus_records"] == 4
    assert report["input"]["corpus_record_coverage"] == 1.0
    assert report["known_blockers"]["task_aware_routing"]["implemented"] is False

    evaluation = report["evaluations"][0]
    assert evaluation["raw_totals"] == {
        "records": 4,
        "actions": {"abstain": 2, "accept": 1, "reject": 1},
        "records_with_execution": 1,
        "execution_count": 1,
        "total_cost": 13.0,
        "mean_cost": 3.25,
        "scope": "all joined rows before truth-conditional metric exclusions",
    }
    task = evaluation["task_validity"]
    assert task["scored_count"] == 3
    assert task["positive_count"] == 2
    assert task["negative_count"] == 1
    assert task["excluded_indeterminate"] == 1
    assert task["truth_counts"] == {"indeterminate": 1, "invalid": 1, "valid": 2}

    candidate = evaluation["candidate_correctness"]
    assert candidate["eligible_count"] == 2
    assert candidate["excluded_count"] == 2
    assert candidate["exclusions"] == {"indeterminate_task": 1, "invalid_task": 1}
    assert candidate["summary"]["total"] == 2
    assert candidate["summary"]["decision_errors"] == 0
    assert set(candidate["subgroups"]) == {"python", "rust"}

    disposition = evaluation["dispositions"]
    assert disposition["quarantine"] == {
        "eligible": 2,
        "correct_abstentions": 2,
        "incorrect_non_abstentions": 0,
        "accuracy": 1.0,
        "rule": (
            "abstain is the only correct disposition for invalid tasks, "
            "indeterminate tasks, or indeterminate candidate truth"
        ),
    }

    static = report["verifier_validity"]["modalities"]["static"]
    assert static["scored_count"] == 4
    assert static["positive_count"] == 4
    assert static["adjudication_source_counts"] == {
        "blinded-evidence-panel": 4,
    }
    assert static["adjudication_protocol_counts"] == {"v1": 4}
    assert static["excluded_indeterminate_label"] == 0
    assert static["excluded_inadequate_adjudication"] == 0
    assert static["excluded_missing_probability"] == 0
    assert static["brier_score"] == pytest.approx(0.01)


def test_verifier_calibration_excludes_indeterminate_provenance_bearing_labels() -> None:
    records = _records()
    events = list(records[0].observations)
    events[0] = replace(
        events[0],
        validity_adjudication=replace(
            events[0].validity_adjudication,
            validity=EvidenceValidity.INDETERMINATE,
            source="blinded-disagreement-panel",
            protocol_version="v2",
            agreement=None,
        ),
    )
    records[0] = replace(records[0], observations=tuple(events))

    static = _report(records)["verifier_validity"]["modalities"]["static"]

    assert static["event_count"] == 4
    assert static["label_counts"] == {"indeterminate": 1, "valid": 3}
    assert static["adjudication_source_counts"] == {
        "blinded-disagreement-panel": 1,
        "blinded-evidence-panel": 3,
    }
    assert static["adjudication_protocol_counts"] == {"v1": 3, "v2": 1}
    assert static["excluded_indeterminate_label"] == 1
    assert static["excluded_inadequate_adjudication"] == 0
    assert static["excluded_missing_probability"] == 0
    assert static["scored_count"] == 3


def test_invalid_and_indeterminate_non_abstentions_are_disposition_errors_only() -> None:
    records = _records()
    rows = _rows(records)
    rows[2]["action"] = "accept"
    rows[3]["action"] = "reject"

    evaluation = _report(records, rows)["evaluations"][0]

    assert evaluation["candidate_correctness"]["summary"]["decision_errors"] == 0
    assert evaluation["dispositions"]["quarantine"]["correct_abstentions"] == 0
    assert evaluation["dispositions"]["quarantine"]["incorrect_non_abstentions"] == 2
    assert evaluation["dispositions"]["quarantine"]["accuracy"] == 0.0


def test_all_non_candidate_truth_yields_no_candidate_calibration_or_error_metrics() -> None:
    records = [_records()[2]]
    evaluation = _report(records)["evaluations"][0]

    candidate = evaluation["candidate_correctness"]
    assert candidate["eligible_count"] == 0
    assert candidate["summary"] is None
    assert candidate["calibration"] is None
    assert candidate["risk_coverage"] is None
    assert evaluation["dispositions"]["quarantine"]["accuracy"] == 1.0


def test_loader_rejects_malformed_rows_instead_of_silently_dropping_them() -> None:
    records = _records()
    with pytest.raises(ValueError, match="line 5: invalid JSON"):
        load_outcomes(io.StringIO(_jsonl(_rows(records)) + "\n{broken"))


def test_loader_rejects_duplicate_json_keys() -> None:
    records = _records()
    line = _jsonl([_rows(records)[0]]).replace(
        '"action": "accept"',
        '"action": "accept", "action": "reject"',
    )
    with pytest.raises(ValueError, match="duplicate JSON object key 'action'"):
        load_outcomes(io.StringIO(line))


def test_legacy_truth_and_probability_fields_fail_with_migration_error() -> None:
    records = _records()
    row = _rows(records)[0]
    row["truth_correct"] = True
    row["probability_correct"] = 0.9
    with pytest.raises(ValueError, match="legacy evaluation truth fields.*truth_correct"):
        load_outcomes(io.StringIO(_jsonl([row])))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("corpus_digest", "sha256:" + "a" * 64, "64 lowercase hexadecimal"),
        ("corpus_record_sha256", "A" * 64, "64 lowercase hexadecimal"),
        ("acquisition_trajectory_digest", "a" * 63, "64 lowercase hexadecimal"),
        ("probability_task_valid", True, "JSON number"),
        ("probability_correct_given_valid_task", "0.9", "JSON number"),
    ],
)
def test_loader_requires_strict_join_digests_and_probabilities(
    field: str,
    value: object,
    message: str,
) -> None:
    records = _records()
    row = _rows(records)[0]
    row[field] = value
    with pytest.raises(ValueError, match=message):
        load_outcomes(io.StringIO(_jsonl([row])))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.__setitem__("corpus_digest", "a" * 64), "corpus_digest"),
        (
            lambda row: row.__setitem__("corpus_record_sha256", "a" * 64),
            "corpus_record_sha256",
        ),
        (
            lambda row: row.__setitem__("acquisition_trajectory_digest", "a" * 64),
            "acquisition trajectory",
        ),
        (lambda row: row.__setitem__("instance_id", "missing-task"), "no exact corpus"),
    ],
)
def test_exact_corpus_join_rejects_every_identity_mismatch(mutation, message: str) -> None:
    records = _records()
    row = deepcopy(_rows(records)[0])
    mutation(row)
    outcomes = load_outcomes(io.StringIO(_jsonl([row])))
    with pytest.raises(ValueError, match=message):
        build_evaluation_report(outcomes, records)


def test_loader_and_builder_reject_duplicate_observation_identity() -> None:
    records = _records()
    line = _jsonl([_rows(records)[0]])
    with pytest.raises(ValueError, match="duplicate observation identity"):
        load_outcomes(io.StringIO(f"{line}\n{line}\n"))

    outcome = load_outcomes(io.StringIO(line))[0]
    with pytest.raises(ValueError, match="duplicate observation identity"):
        build_evaluation_report([outcome, outcome], records)


def test_same_candidate_across_policies_is_preserved_for_pairing() -> None:
    records = [_records()[0]]
    baseline = _row(records[0], records, policy_id="baseline")
    routed = _row(
        records[0],
        records,
        policy_id="router",
        run_id="run-2",
        seed=12,
        calibration_id="calibration-2",
    )
    report = _report(records, [baseline, routed])

    assert len(report["evaluations"]) == 2
    assert report["pairing"] == {
        "evaluation_unit_count": 2,
        "unique_candidate_count": 1,
        "candidates_shared_by_all_units": 1,
        "fully_paired": True,
        "per_unit_candidate_counts": [1, 1],
    }


def test_loader_rejects_run_that_changes_seed_or_calibration() -> None:
    records = _records()[:2]
    rows = _rows(records)
    rows[1]["seed"] = 99
    with pytest.raises(ValueError, match="changes seed or calibration_id"):
        load_outcomes(io.StringIO(_jsonl(rows)))


def test_input_digest_is_order_independent_but_prediction_preserving() -> None:
    records = _records()
    rows = _rows(records)
    forward = _report(records, rows)
    reverse = _report(records, list(reversed(rows)))
    changed_rows = deepcopy(rows)
    changed_rows[0]["probability_correct_given_valid_task"] = 0.8
    changed = _report(records, changed_rows)

    assert forward["input"]["outcome_set_sha256"] == reverse["input"][
        "outcome_set_sha256"
    ]
    assert forward["input"]["outcome_set_sha256"] != changed["input"][
        "outcome_set_sha256"
    ]


def test_main_requires_and_joins_exact_corpus(tmp_path, capsys) -> None:
    records = _records()
    outcome_path = tmp_path / "outcomes.jsonl"
    corpus_path = tmp_path / "corpus.jsonl"
    outcome_path.write_text(_jsonl(_rows(records)), encoding="utf-8")
    corpus_path.write_text(_corpus_jsonl(records), encoding="utf-8")

    main([
        str(outcome_path),
        "--corpus",
        str(corpus_path),
        "--calibration-bins",
        "2",
    ])

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "0.4.0"
    assert output["input"]["corpus_digest"] == corpus_digest(records)


def test_main_reports_output_write_failure_cleanly(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = _records()
    outcome_path = tmp_path / "outcomes.jsonl"
    corpus_path = tmp_path / "corpus.jsonl"
    outcome_path.write_text(_jsonl(_rows(records)), encoding="utf-8")
    corpus_path.write_text(_corpus_jsonl(records), encoding="utf-8")

    def fail_write(path, content) -> None:
        raise OSError("fixture output failure")

    monkeypatch.setattr(verification_evaluate, "atomic_write", fail_write)
    with pytest.raises(
        SystemExit,
        match="verification evaluation failed: fixture output failure",
    ):
        main([
            str(outcome_path),
            "--corpus",
            str(corpus_path),
            "--output",
            str(tmp_path / "report.json"),
        ])
