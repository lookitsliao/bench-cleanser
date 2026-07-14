"""Adversarial durability tests for the prospective SQLite ledger."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import pathlib
import sqlite3
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from bench_cleanser.verification._io import strict_json_dumps
from bench_cleanser.verification.acquire import AcquisitionRequest
from bench_cleanser.verification.models import (
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RiskProfile,
    RouteDecision,
    ValidityManifest,
)
from bench_cleanser.verification.orchestrate import (
    WORKSPACE_IDENTITY_SCHEMA_VERSION,
    RouteAcquisitionPlan,
    execute_route_acquisition,
    load_route_acquisition_record,
)
from bench_cleanser.verification.policy_log import canonical_action_spec_sha256
from experiments.prospective_pilot.ledger import (
    LEDGER_SCHEMA_VERSION,
    LedgerConflict,
    LedgerError,
    ProspectiveLedger,
    ReservationRequest,
    RoundNotReady,
    TaskHalted,
    audit_jsonl_export,
)
from experiments.prospective_pilot.scheduler import (
    COLLECTION_ACTION_IDS,
    SchedulerBindings,
    TaskRoundDecision,
    build_task_round_decision,
    build_task_selection_decision,
    load_study_bindings,
)
from tests.test_prospective_scheduler import (
    _initial_inputs,
    _successor_inputs,
    _timestamp,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
_SYNTHETIC_RESULT_CONTRACT = "test_only_synthetic_result"


@pytest.fixture(scope="module")
def bindings() -> SchedulerBindings:
    return load_study_bindings(ROOT)


def _ledger_time(offset: int) -> str:
    value = datetime(2026, 7, 14, tzinfo=UTC) + timedelta(seconds=offset)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _spec_value(action_id: str) -> dict[str, Any]:
    return {
        "schema_version": "prospective-ledger-test-action-spec-v1",
        "action_id": action_id,
        "adapter_contract": f"fixture-adapter-{action_id}",
        "credential_names": [],
    }


def _spec_values() -> dict[str, dict[str, Any]]:
    return {action_id: _spec_value(action_id) for action_id in COLLECTION_ACTION_IDS}


def _preimages(
    specs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, bytes]:
    values = _spec_values() if specs is None else specs
    return {
        canonical_action_spec_sha256(value): strict_json_dumps(value).encode()
        for value in values.values()
    }


def _canonical_inputs(
    inputs: tuple[Any, ...],
    *,
    specs: dict[str, dict[str, Any]] | None = None,
) -> tuple[Any, ...]:
    values = _spec_values() if specs is None else specs
    result: list[Any] = []
    for candidate in inputs:
        catalog = tuple(
            replace(
                offer,
                action_spec_sha256=canonical_action_spec_sha256(
                    values[offer.action_id]
                ),
            )
            for offer in candidate.action_catalog
        )
        result.append(replace(candidate, action_catalog=catalog))
    return tuple(result)


def _round_zero(
    bindings: SchedulerBindings,
    task_id: str,
    *,
    specs: dict[str, dict[str, Any]] | None = None,
    terminal_only: bool = False,
) -> TaskRoundDecision:
    inputs = _canonical_inputs(_initial_inputs(bindings, task_id), specs=specs)
    if terminal_only:
        inputs = tuple(
            replace(
                candidate,
                action_catalog=tuple(
                    replace(
                        offer,
                        available=False,
                        availability_reason=(
                            "semantic_binding_unavailable"
                            if offer.action_id == "semantic_primary"
                            else "execution_binding_unavailable"
                        ),
                    )
                    if offer.action_id
                    in {
                        "semantic_primary",
                        "targeted_primary",
                        "full_primary",
                        "full_repeat",
                    }
                    else offer
                    for offer in candidate.action_catalog
                ),
            )
            for candidate in inputs
        )
    return build_task_round_decision(
        bindings=bindings,
        task_id=task_id,
        scheduled_at=_timestamp(0),
        candidates=inputs,
    )


def _next_round(
    bindings: SchedulerBindings,
    prior: tuple[TaskRoundDecision, ...],
) -> TaskRoundDecision:
    previous = prior[-1]
    return build_task_round_decision(
        bindings=bindings,
        task_id=previous.task_id,
        scheduled_at=_timestamp(len(prior)),
        candidates=_canonical_inputs(_successor_inputs(previous)),
        prior_rounds=prior,
    )


def _reservations(
    round_decision: TaskRoundDecision,
    *,
    namespace: str = "",
    shared_resource_key: str | None = None,
) -> tuple[ReservationRequest, ...]:
    result: list[ReservationRequest] = []
    for scheduled in round_decision.scheduled_decisions:
        logged = scheduled.logged_policy_decision
        if logged.terminal:
            continue
        assert logged.acquisition_id is not None
        resource_kind = (
            "fresh_worktree"
            if scheduled.chosen_action_id == "full_repeat"
            else "exclusive_bundle"
        )
        result.append(ReservationRequest(
            acquisition_id=logged.acquisition_id,
            resource_kind=resource_kind,
            resource_key=(
                shared_resource_key
                if shared_resource_key is not None
                else f"fixture-bundle:{namespace}:{logged.acquisition_id}"
            ),
            details={
                "action_id": scheduled.chosen_action_id,
                "credential_names": [],
            },
        ))
    return tuple(result)


def _round_commit_worker(
    database: str,
    round_payload: dict[str, Any],
    preimages: dict[str, bytes],
    reservation_payloads: list[dict[str, Any]],
    start: Any,
    output: Any,
) -> None:
    try:
        worker_bindings = load_study_bindings(ROOT)
        ledger = ProspectiveLedger(pathlib.Path(database), bindings=worker_bindings)
        round_decision = TaskRoundDecision.from_dict(round_payload)
        reservations = tuple(
            ReservationRequest(
                acquisition_id=item["acquisition_id"],
                resource_kind=item["resource_kind"],
                resource_key=item["resource_key"],
                details=item["details"],
            )
            for item in reservation_payloads
        )
        start.wait()
        receipt = ledger.commit_round(
            round_decision,
            committed_at=_ledger_time(0),
            action_spec_preimages=preimages,
            reservations=reservations,
        )
        output.put(("ok", receipt.inserted))
    except BaseException as exc:  # pragma: no cover - asserted in parent process
        output.put(("error", repr(exc)))


def _claim_worker(
    database: str,
    acquisition_id: str,
    launch_marker: str,
    worker_index: int,
    start: Any,
    output: Any,
) -> None:
    try:
        ledger = ProspectiveLedger(pathlib.Path(database))
        start.wait()
        receipt = ledger.claim_dispatch(
            acquisition_id,
            claimant=f"process-worker-{worker_index}",
            claimed_at=_ledger_time(10),
        )
        if receipt is not None:
            subprocess.run(
                (
                    sys.executable,
                    "-c",
                    (
                        "import pathlib,sys;"
                        "pathlib.Path(sys.argv[1]).write_text(sys.argv[2])"
                    ),
                    launch_marker,
                    receipt.claim_id,
                ),
                check=True,
            )
        output.put(("ok", None if receipt is None else receipt.claim_id))
    except BaseException as exc:  # pragma: no cover - asserted in parent process
        output.put(("error", repr(exc)))


def _crash_after_claim_worker(
    database: str,
    acquisition_id: str,
    marker: str,
) -> None:
    ledger = ProspectiveLedger(pathlib.Path(database))
    receipt = ledger.claim_dispatch(
        acquisition_id,
        claimant="crashing-process",
        claimed_at=_ledger_time(10),
    )
    if receipt is None:
        os._exit(31)
    with pathlib.Path(marker).open("w", encoding="utf-8") as stream:
        stream.write(receipt.claim_id)
        stream.flush()
        os.fsync(stream.fileno())
    os._exit(23)


def _crash_before_sqlite_commit_worker(database: str) -> None:
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    value = {
        "schema_version": "crash-before-commit-action-spec-v1",
        "action_id": "crash_probe",
        "credential_names": [],
    }
    preimage = strict_json_dumps(value).encode()
    digest = hashlib.sha256(preimage).hexdigest()
    record = {
        "action_spec_sha256": digest,
        "preimage_base64": "not-exported-because-the-transaction-rolls-back",
    }
    record_json = strict_json_dumps(record)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        """
        INSERT INTO action_specs(
            action_spec_sha256, preimage, record_json, record_sha256
        ) VALUES (?, ?, ?, ?)
        """,
        (
            digest,
            preimage,
            record_json,
            hashlib.sha256(record_json.encode()).hexdigest(),
        ),
    )
    os._exit(29)


def _process_results(
    context: Any,
    target: Any,
    args: tuple[Any, ...],
    *,
    count: int = 2,
) -> list[tuple[str, Any]]:
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(target=target, args=(*args, index, start, output))
        for index in range(count)
    ]
    for process in processes:
        process.start()
    start.set()
    results = [output.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    return results


def _synthetic_result(
    ledger: ProspectiveLedger,
    claim_id: str,
    observation: EvidenceObservation,
    *,
    index: int,
    payload: dict[str, Any] | None = None,
) -> Any:
    artifact_sha256 = hashlib.sha256(f"artifact-{index}".encode()).hexdigest()
    completed = replace(
        observation,
        metadata={"artifact_sha256": artifact_sha256},
    )
    result_payload = {"fixture_result": index} if payload is None else payload
    completed_output_sha256 = hashlib.sha256(
        strict_json_dumps(result_payload).encode()
    ).hexdigest()
    return ledger._append_validated_result(
        claim_id=claim_id,
        observation=completed,
        completed_at=_ledger_time(20 + index),
        artifact_sha256=artifact_sha256,
        completed_output_sha256=completed_output_sha256,
        payload=result_payload,
        validation_contract=_SYNTHETIC_RESULT_CONTRACT,
    )


def _resolve_round_for_successor(
    ledger: ProspectiveLedger,
    current: TaskRoundDecision,
    successor: TaskRoundDecision,
    *,
    index_offset: int,
) -> None:
    successor_states = {item.candidate_id: item for item in successor.candidates}
    acquisition_index = 0
    for scheduled in current.scheduled_decisions:
        logged = scheduled.logged_policy_decision
        if logged.terminal:
            continue
        assert logged.acquisition_id is not None
        index = index_offset + acquisition_index
        claim = ledger.claim_dispatch(
            logged.acquisition_id,
            claimant=f"chain-worker-{index}",
            claimed_at=_ledger_time(10 + index),
        )
        assert claim is not None
        state = successor_states[logged.candidate_id]
        assert state.bound_router_decision is not None
        observation = state.bound_router_decision.router_state.evidence_history[-1]
        _synthetic_result(
            ledger,
            claim.claim_id,
            observation,
            index=index,
        )
        acquisition_index += 1


def test_sqlite_pragmas_immutable_triggers_and_credential_safe_specs(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    ledger = ProspectiveLedger(tmp_path / "ledger.sqlite3", bindings=bindings)
    assert ledger.sqlite_settings() == {
        "journal_mode": "delete",
        "synchronous": 2,
        "foreign_keys": 1,
    }

    task_id = "django__django-11299"
    round_decision = _round_zero(bindings, task_id)
    receipt = ledger.commit_round(
        round_decision,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=_reservations(round_decision),
    )
    assert receipt.inserted is True

    connection = sqlite3.connect(ledger.path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable table rounds"):
            connection.execute(
                "UPDATE rounds SET task_id = 'mutated' WHERE round_sha256 = ?",
                (round_decision.decision_sha256,),
            )
        connection.rollback()
        with pytest.raises(
            sqlite3.IntegrityError, match="immutable table action_specs"
        ):
            connection.execute("DELETE FROM action_specs")
        connection.rollback()
        trigger_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        for table in (
            "rounds",
            "action_specs",
            "policy_decisions",
            "dispatch_intents",
            "resource_reservations",
            "claims",
            "results",
            "incidents",
            "selections",
            "events",
        ):
            assert f"{table}_deny_update" in trigger_names
            assert f"{table}_deny_delete" in trigger_names
    finally:
        connection.close()

    # Preserve the runtime credential-rejection test without shipping a
    # credential-shaped literal that archive scanners must reject.
    synthetic_credential = "-".join(("sk", "synthetic-fixture-value"))

    secret_specs = _spec_values()
    secret_specs["semantic_primary"] = {
        **secret_specs["semantic_primary"],
        "api_key": synthetic_credential,
    }
    secret_round = _round_zero(
        bindings,
        "django__django-11133",
        specs=secret_specs,
    )
    with pytest.raises(LedgerError, match="secret-bearing key"):
        ProspectiveLedger(
            tmp_path / "secret.sqlite3", bindings=bindings
        ).commit_round(
            secret_round,
            committed_at=_ledger_time(1),
            action_spec_preimages=_preimages(secret_specs),
            reservations=_reservations(secret_round, namespace="secret"),
        )

    value_specs = _spec_values()
    value_specs["semantic_primary"] = {
        **value_specs["semantic_primary"],
        "provider_handle": synthetic_credential,
    }
    value_round = _round_zero(
        bindings,
        "django__django-13417",
        specs=value_specs,
    )
    with pytest.raises(LedgerError, match="credential material"):
        ProspectiveLedger(
            tmp_path / "secret-value.sqlite3", bindings=bindings
        ).commit_round(
            value_round,
            committed_at=_ledger_time(2),
            action_spec_preimages=_preimages(value_specs),
            reservations=_reservations(value_round, namespace="secret-value"),
        )


def test_atomic_round_rollback_and_cross_process_exactly_once_commit(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    round_decision = _round_zero(bindings, "django__django-13741")
    nonterminal_count = sum(
        not item.logged_policy_decision.terminal
        for item in round_decision.scheduled_decisions
    )
    assert nonterminal_count >= 2
    rollback = ProspectiveLedger(
        tmp_path / "rollback.sqlite3", bindings=bindings
    )
    with pytest.raises(LedgerConflict, match="atomic round commit rejected"):
        rollback.commit_round(
            round_decision,
            committed_at=_ledger_time(0),
            action_spec_preimages=_preimages(),
            reservations=_reservations(
                round_decision,
                shared_resource_key="same-exclusive-workspace",
            ),
        )
    counts = rollback.table_counts()
    assert counts["rounds"] == 0
    assert counts["action_specs"] == 0
    assert counts["policy_decisions"] == 0
    assert counts["dispatch_intents"] == 0
    assert counts["resource_reservations"] == 0
    assert counts["events"] == 0

    database = tmp_path / "contended.sqlite3"
    contended = ProspectiveLedger(database, bindings=bindings)
    reservation_payloads = [
        {
            "acquisition_id": item.acquisition_id,
            "resource_kind": item.resource_kind,
            "resource_key": item.resource_key,
            "details": item.details_object(),
        }
        for item in _reservations(round_decision, namespace="contended")
    ]
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(
            target=_round_commit_worker,
            args=(
                str(database),
                round_decision.to_dict(),
                _preimages(),
                reservation_payloads,
                start,
                output,
            ),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    results = [output.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    assert [item[0] for item in results] == ["ok", "ok"]
    assert sorted(item[1] for item in results) == [False, True]
    assert contended.table_counts()["rounds"] == 1
    assert contended.table_counts()["events"] == 1


def test_cross_process_permanent_claim_is_exactly_once(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    database = tmp_path / "claims.sqlite3"
    ledger = ProspectiveLedger(database, bindings=bindings)
    round_decision = _round_zero(bindings, "django__django-11299")
    nonterminal_decisions = tuple(
        item
        for item in round_decision.scheduled_decisions
        if not item.logged_policy_decision.terminal
    )
    ledger.commit_round(
        round_decision,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=_reservations(round_decision),
    )
    acquisition_id = nonterminal_decisions[0].logged_policy_decision.acquisition_id
    assert acquisition_id is not None
    context = multiprocessing.get_context("spawn")
    launch_marker = tmp_path / "actual-launch.txt"
    results = _process_results(
        context,
        _claim_worker,
        (str(database), acquisition_id, str(launch_marker)),
    )
    assert [item[0] for item in results] == ["ok", "ok"]
    claims = [item[1] for item in results]
    assert claims.count(None) == 1
    assert sum(isinstance(item, str) for item in claims) == 1
    launched_claim_id = launch_marker.read_text(encoding="utf-8")
    assert launched_claim_id in claims
    assert ledger.table_counts()["claims"] == 1
    assert ledger.claim_dispatch(
        acquisition_id,
        claimant="late-worker",
        claimed_at=_ledger_time(11),
    ) is None


def test_os_exit_before_commit_rolls_back_uncommitted_sqlite_page(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    database = tmp_path / "precommit-crash.sqlite3"
    ledger = ProspectiveLedger(database, bindings=bindings)
    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_crash_before_sqlite_commit_worker,
        args=(str(database),),
    )
    process.start()
    process.join(timeout=30)
    assert process.exitcode == 29
    reopened = ProspectiveLedger(database, bindings=bindings)
    assert reopened.table_counts()["action_specs"] == 0
    assert reopened.table_counts()["events"] == 0
    assert reopened.audit().record_count == 1


def test_claimed_process_crash_never_redispatches_and_halts_task(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    database = tmp_path / "crash.sqlite3"
    ledger = ProspectiveLedger(database, bindings=bindings)
    round_decision = _round_zero(bindings, "django__django-11299")
    nonterminal_decisions = tuple(
        item
        for item in round_decision.scheduled_decisions
        if not item.logged_policy_decision.terminal
    )
    ledger.commit_round(
        round_decision,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=_reservations(round_decision),
    )
    acquisition_id = nonterminal_decisions[0].logged_policy_decision.acquisition_id
    assert acquisition_id is not None
    marker = tmp_path / "claimed.txt"
    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_crash_after_claim_worker,
        args=(str(database), acquisition_id, str(marker)),
    )
    process.start()
    process.join(timeout=30)
    assert process.exitcode == 23
    claim_id = marker.read_text(encoding="utf-8")
    assert ledger.claim_dispatch(
        acquisition_id,
        claimant="replacement-worker",
        claimed_at=_ledger_time(11),
    ) is None

    incident = ledger.record_claimed_crash(
        claim_id=claim_id,
        occurred_at=_ledger_time(12),
        reason_code="ambiguous_claimed_crash",
        details={"operator_action": "halt_without_replay"},
    )
    assert incident.inserted is True
    assert ledger.record_claimed_crash(
        claim_id=claim_id,
        occurred_at=_ledger_time(12),
        reason_code="ambiguous_claimed_crash",
        details={"operator_action": "halt_without_replay"},
    ).inserted is False
    with pytest.raises(LedgerConflict, match="incident retry differs"):
        ledger.record_claimed_crash(
            claim_id=claim_id,
            occurred_at=_ledger_time(12),
            reason_code="ambiguous_claimed_crash",
            details={"operator_action": "changed"},
        )
    successor = _next_round(bindings, (round_decision,))
    with pytest.raises(TaskHalted, match="permanent halt incident"):
        ledger.commit_round(
            successor,
            committed_at=_ledger_time(13),
            action_spec_preimages=_preimages(),
            reservations=_reservations(successor, namespace="after-crash"),
        )
    audit = ledger.audit()
    assert audit.halted_task_count == 1
    assert audit.pending_dispatch_count == len(nonterminal_decisions) - 1
    assert audit.complete is False


def test_idempotent_result_tamper_rejection_and_sibling_gate(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    ledger = ProspectiveLedger(tmp_path / "siblings.sqlite3", bindings=bindings)
    first = _round_zero(bindings, "django__django-13741")
    second = _next_round(bindings, (first,))
    ledger.commit_round(
        first,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=_reservations(first),
    )
    with pytest.raises(RoundNotReady, match="every nonterminal sibling"):
        ledger.commit_round(
            second,
            committed_at=_ledger_time(1),
            action_spec_preimages=_preimages(),
            reservations=_reservations(second, namespace="second"),
        )

    successor_states = {item.candidate_id: item for item in second.candidates}
    acquisitions = [
        item
        for item in first.scheduled_decisions
        if not item.logged_policy_decision.terminal
    ]
    assert len(acquisitions) >= 2
    for index, scheduled in enumerate(acquisitions):
        logged = scheduled.logged_policy_decision
        assert logged.acquisition_id is not None
        claim = ledger.claim_dispatch(
            logged.acquisition_id,
            claimant=f"sibling-worker-{index}",
            claimed_at=_ledger_time(2 + index),
        )
        assert claim is not None
        successor = successor_states[logged.candidate_id]
        assert successor.bound_router_decision is not None
        observation = (
            successor.bound_router_decision.router_state.evidence_history[-1]
        )
        receipt = _synthetic_result(
            ledger, claim.claim_id, observation, index=index
        )
        assert receipt.inserted is True
        assert _synthetic_result(
            ledger, claim.claim_id, observation, index=index
        ).inserted is False
        with pytest.raises(LedgerConflict, match="result retry differs"):
            _synthetic_result(
                ledger,
                claim.claim_id,
                observation,
                index=index,
                payload={"fixture_result": index, "tampered": True},
            )
        if index == 0:
            with pytest.raises(RoundNotReady, match="every nonterminal sibling"):
                ledger.commit_round(
                    second,
                    committed_at=_ledger_time(5),
                    action_spec_preimages=_preimages(),
                    reservations=_reservations(second, namespace="second"),
                )

    assert ledger.commit_round(
        second,
        committed_at=_ledger_time(5),
        action_spec_preimages=_preimages(),
        reservations=_reservations(second, namespace="second"),
    ).inserted is True
    assert ledger.table_counts()["results"] == len(acquisitions)
    audit = ledger.audit()
    assert audit.complete is False
    assert audit.protocol_result_count == 0


def test_full_repeat_requires_and_cannot_reuse_a_worktree_bundle(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    first = _round_zero(bindings, "django__django-14580")
    second = _next_round(bindings, (first,))
    third = _next_round(bindings, (first, second))
    repeat = next(
        item
        for item in third.scheduled_decisions
        if item.chosen_action_id == "full_repeat"
    )
    assert repeat.logged_policy_decision.acquisition_id is not None
    wrong_kind = ReservationRequest(
        acquisition_id=repeat.logged_policy_decision.acquisition_id,
        resource_kind="exclusive_bundle",
        resource_key="not-a-fresh-worktree",
    )
    wrong_kind_reservations = tuple(
        wrong_kind
        if item.acquisition_id == wrong_kind.acquisition_id
        else item
        for item in _reservations(third, namespace="wrong-kind")
    )
    with pytest.raises(LedgerError, match="fresh_worktree"):
        ProspectiveLedger(
            tmp_path / "wrong-kind.sqlite3", bindings=bindings
        ).commit_round(
            third,
            committed_at=_ledger_time(5),
            action_spec_preimages=_preimages(),
            reservations=wrong_kind_reservations,
        )

    ledger = ProspectiveLedger(tmp_path / "repeat.sqlite3", bindings=bindings)
    first_reservations = _reservations(first, namespace="repeat-first")
    ledger.commit_round(
        first,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=first_reservations,
    )
    _resolve_round_for_successor(ledger, first, second, index_offset=0)
    second_reservations = _reservations(second, namespace="repeat-second")
    ledger.commit_round(
        second,
        committed_at=_ledger_time(22),
        action_spec_preimages=_preimages(),
        reservations=second_reservations,
    )
    primary_acquisition = next(
        item.logged_policy_decision.acquisition_id
        for round_decision in (first, second)
        for item in round_decision.scheduled_decisions
        if item.candidate_id == repeat.candidate_id
        and item.chosen_action_id == "full_primary"
    )
    primary_resource_key = next(
        item.resource_key
        for item in (*first_reservations, *second_reservations)
        if item.acquisition_id == primary_acquisition
    )
    _resolve_round_for_successor(ledger, second, third, index_offset=20)
    reused = ReservationRequest(
        acquisition_id=repeat.logged_policy_decision.acquisition_id,
        resource_kind="fresh_worktree",
        resource_key=primary_resource_key,
        details={"attempted_reuse": True},
    )
    reused_reservations = tuple(
        reused
        if item.acquisition_id == reused.acquisition_id
        else item
        for item in _reservations(third, namespace="repeat-third")
    )
    with pytest.raises(LedgerConflict, match="atomic round commit rejected"):
        ledger.commit_round(
            third,
            committed_at=_ledger_time(41),
            action_spec_preimages=_preimages(),
            reservations=reused_reservations,
        )
    assert ledger.table_counts()["rounds"] == 2


def _strict_orchestration_fixture(
    root: pathlib.Path,
    round_decision: TaskRoundDecision,
) -> tuple[
    Any,
    dict[str, Any],
    ValidityManifest,
    RouteDecision,
    RouteAcquisitionPlan,
]:
    scheduled = next(
        item
        for item in round_decision.scheduled_decisions
        if not item.logged_policy_decision.terminal
    )
    logged = scheduled.logged_policy_decision
    assert logged.acquisition_id is not None
    assert logged.chosen_offer.evidence_kind is not None
    workspace = (root / "workspace").resolve()
    state = (root / "state").resolve()
    workspace.mkdir(parents=True)
    state.mkdir(parents=True)
    base_commit = "a" * 40
    workspace_id = "sha256:" + "d" * 64
    marker_payload = strict_json_dumps(
        {
            "schema_version": WORKSPACE_IDENTITY_SCHEMA_VERSION,
            "instance_id": logged.instance_id,
            "candidate_id": logged.candidate_id,
            "base_commit": base_commit,
            "workspace_id": workspace_id,
        },
        indent=2,
    ) + "\n"
    marker = workspace / ".bench-cleanser-workspace.json"
    marker.write_text(marker_payload, encoding="utf-8")
    route = RouteDecision(
        action=logged.chosen_offer.route_action,
        policy_version="prospective-ledger-fixture-v1",
        candidate_risk=0.2,
        verifier_risk=0.3,
        expected_information_gain=0.4,
        estimated_relative_cost=0.2,
        reasons=("sampled prospective ledger action",),
        terminal=False,
    )
    manifest = ValidityManifest(
        instance_id=logged.instance_id,
        candidate_id=logged.candidate_id,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(language="python"),
        provenance={
            "dataset_revision": "prospective-ledger-fixture-v1",
            "base_commit": base_commit,
            "candidate_patch_sha256": logged.candidate_id.removeprefix("sha256:"),
        },
    )
    manifest.add_decision(route)
    request = AcquisitionRequest(
        kind=logged.chosen_offer.evidence_kind,
        source="prospective-ledger-fixture",
        source_version="v1",
        workspace_root=str(workspace),
        working_directory=".",
        argv=(sys.executable, "-c", "print('ledger orchestration fixture')"),
        timeout_seconds=3.0,
        max_capture_bytes=2048,
        supports_incorrect_exit_codes=(1,),
    )
    plan = RouteAcquisitionPlan(
        instance_id=logged.instance_id,
        candidate_id=logged.candidate_id,
        manifest_sha256=manifest.canonical_digest(),
        base_commit=base_commit,
        workspace_root=str(workspace),
        workspace_id=workspace_id,
        workspace_identity_path=".bench-cleanser-workspace.json",
        workspace_identity_sha256=hashlib.sha256(
            marker_payload.encode()
        ).hexdigest(),
        acquisition_id=logged.acquisition_id,
        coordination_directory=str(state),
        artifact_directory=str(state / "artifacts"),
        output_path=str(state / "completed.json"),
        requests={logged.chosen_offer.route_action: request},
    )
    result = execute_route_acquisition(manifest, route, plan)
    with pathlib.Path(plan.output_path).open(encoding="utf-8") as stream:
        record = load_route_acquisition_record(stream)
    assert record["observation"] == result.observation.to_dict()
    return scheduled, record, manifest, route, plan


def test_strict_completed_output_ingestion_is_idempotent_and_tamper_safe(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    round_decision = _round_zero(bindings, "django__django-11299")
    scheduled, record, manifest, route, plan = _strict_orchestration_fixture(
        tmp_path / "orchestration", round_decision
    )
    logged = scheduled.logged_policy_decision
    assert logged.acquisition_id is not None
    ledger = ProspectiveLedger(tmp_path / "strict.sqlite3", bindings=bindings)
    ledger.commit_round(
        round_decision,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=_reservations(round_decision),
    )
    claim = ledger.claim_dispatch(
        logged.acquisition_id,
        claimant="strict-result-worker",
        claimed_at=_ledger_time(1),
    )
    assert claim is not None
    first = ledger._ingest_completed_route_acquisition_for_test_only(
        claim_id=claim.claim_id,
        record=record,
        manifest_before=manifest,
        decision=route,
        plan=plan,
        completed_at=_ledger_time(2),
    )
    assert first.inserted is True
    assert ledger._ingest_completed_route_acquisition_for_test_only(
        claim_id=claim.claim_id,
        record=record,
        manifest_before=manifest,
        decision=route,
        plan=plan,
        completed_at=_ledger_time(2),
    ).inserted is False

    tampered = dict(record)
    tampered["manifest_sha256_after"] = "0" * 64
    with pytest.raises(ValueError):
        ledger._ingest_completed_route_acquisition_for_test_only(
            claim_id=claim.claim_id,
            record=tampered,
            manifest_before=manifest,
            decision=route,
            plan=plan,
            completed_at=_ledger_time(2),
        )
    with pytest.raises(LedgerConflict, match="result retry differs"):
        ledger._ingest_completed_route_acquisition_for_test_only(
            claim_id=claim.claim_id,
            record=record,
            manifest_before=manifest,
            decision=route,
            plan=plan,
            completed_at=_ledger_time(3),
        )
    audit = ledger.audit()
    assert audit.protocol_result_count == 0
    assert audit.pending_dispatch_count == (
        sum(
            not item.logged_policy_decision.terminal
            for item in round_decision.scheduled_decisions
        )
        - 1
    )


def test_export_is_deterministic_padded_past_ten_and_marks_partial_state(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    ledger = ProspectiveLedger(tmp_path / "events.sqlite3", bindings=bindings)
    task_ids = (
        "django__django-11133",
        "django__django-11299",
        "django__django-13417",
        "django__django-13741",
        "django__django-14580",
    )
    claim_index = 0
    for task_index, task_id in enumerate(task_ids):
        round_decision = _round_zero(bindings, task_id)
        ledger.commit_round(
            round_decision,
            committed_at=_ledger_time(task_index),
            action_spec_preimages=_preimages(),
            reservations=_reservations(
                round_decision, namespace=f"events-{task_index}"
            ),
        )
        for scheduled in round_decision.scheduled_decisions:
            logged = scheduled.logged_policy_decision
            if logged.terminal:
                continue
            assert logged.acquisition_id is not None
            assert ledger.claim_dispatch(
                logged.acquisition_id,
                claimant=f"event-worker-{claim_index}",
                claimed_at=_ledger_time(20 + claim_index),
            ) is not None
            claim_index += 1
    assert ledger.table_counts()["events"] >= 11
    exported = ledger.export_jsonl()
    assert '"record_key":"00000000000000000010"' in exported
    assert ledger.export_jsonl() == exported
    reopened = ProspectiveLedger(ledger.path, bindings=bindings)
    assert reopened.export_jsonl() == exported
    audit = audit_jsonl_export(exported, bindings=bindings)
    assert audit.complete is False
    assert audit.analysis_ready is False
    assert audit.pending_dispatch_count == claim_index
    with pytest.raises(RoundNotReady, match="not complete"):
        audit_jsonl_export(exported, bindings=bindings, require_complete=True)
    tampered = exported.replace(LEDGER_SCHEMA_VERSION, "tampered-ledger-v0", 1)
    with pytest.raises(LedgerError):
        audit_jsonl_export(tampered, bindings=bindings)


def test_complete_terminal_task_is_not_exact_frame_analysis_ready(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    round_decision = _round_zero(
        bindings,
        "django__django-11555",
        terminal_only=True,
    )
    assert round_decision.completes_candidate_chains is True
    assert all(
        item.logged_policy_decision.terminal
        for item in round_decision.scheduled_decisions
    )
    ledger = ProspectiveLedger(tmp_path / "complete.sqlite3", bindings=bindings)
    ledger.commit_round(
        round_decision,
        committed_at=_ledger_time(0),
        action_spec_preimages=_preimages(),
        reservations=(),
    )
    selection = build_task_selection_decision(
        (round_decision,),
        bindings=bindings,
        scheduled_at=_ledger_time(1),
    )
    assert ledger.commit_selection(
        selection, committed_at=_ledger_time(2)
    ).inserted is True
    assert ledger.commit_selection(
        selection, committed_at=_ledger_time(3)
    ).inserted is False
    audit = ledger.audit(require_complete=True)
    assert audit.complete is True
    assert audit.analysis_ready is False
    assert audit.pending_dispatch_count == 0
    assert audit.selected_task_count == 1
    with pytest.raises(RoundNotReady, match="exact frozen task frame"):
        ledger.assert_analysis_ready()
