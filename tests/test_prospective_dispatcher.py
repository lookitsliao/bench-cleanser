"""Adversarial tests for the typed prospective dispatcher boundary."""

from __future__ import annotations

import hashlib
import importlib
import multiprocessing
import pathlib
import shutil
import sys
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

import pytest

from bench_cleanser.verification._io import strict_json_dumps
from bench_cleanser.verification.acquire import AcquisitionRequest
from bench_cleanser.verification.models import (
    EvidenceCost,
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RiskProfile,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)
from bench_cleanser.verification.orchestrate import (
    WORKSPACE_IDENTITY_SCHEMA_VERSION,
    RouteAcquisitionPlan,
    execute_route_acquisition,
)
from bench_cleanser.verification.policy_log import (
    ActionOffer,
    BootstrapHistoryStep,
    RouterRouteStep,
    RouterStateView,
)
from experiments.prospective_pilot.dispatcher import (
    ProspectiveDispatcher,
    WorkerExitReceipt,
)
from experiments.prospective_pilot.ledger import (
    ArtifactRetention,
    ExecutableActionSpec,
    LedgerError,
    ProspectiveLedger,
    ProvisioningReceipt,
    ReservationRequest,
)
from experiments.prospective_pilot.scheduler import (
    COLLECTION_ACTION_IDS,
    COLLECTION_ACTION_ROUTE,
    SCHEDULER_GENESIS_SHA256,
    BoundRouterDecision,
    CandidateActivity,
    CandidateRoundInput,
    SchedulerBindings,
    TaskRoundDecision,
    build_task_round_decision,
    load_study_bindings,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
_DUMMY_ACQUISITION_ID = "acq-" + "0" * 32
_ACTION_KIND = {
    RouteAction.RUN_STATIC: EvidenceKind.STATIC,
    RouteAction.RUN_SEMANTIC: EvidenceKind.SEMANTIC,
    RouteAction.RUN_TARGETED: EvidenceKind.TARGETED_EXECUTION,
    RouteAction.RUN_FULL: EvidenceKind.FULL_EXECUTION,
    RouteAction.HARDEN_ORACLE: EvidenceKind.ORACLE_HARDENING,
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _timestamp(second: int) -> str:
    return f"2026-07-14T00:00:{second:02d}.000000Z"


@pytest.fixture
def bindings(monkeypatch: pytest.MonkeyPatch) -> SchedulerBindings:
    """Load real bindings while isolating this source-under-edit hash cycle."""

    validator = importlib.import_module(
        "experiments.prospective_pilot.validate_protocol"
    )
    protocol_path = ROOT / "experiments/prospective_pilot/preregistration.json"
    configuration = {
        "collection_policy": hashlib.sha256(
            (ROOT / "experiments/prospective_pilot/collection_policy.json").read_bytes()
        ).hexdigest(),
        "scheduler_contract": hashlib.sha256(
            (ROOT / "experiments/prospective_pilot/scheduler_contract.json").read_bytes()
        ).hexdigest(),
        "frame_manifest": hashlib.sha256(
            (ROOT / "experiments/prospective_pilot/frame_manifest.json").read_bytes()
        ).hexdigest(),
    }
    fake = SimpleNamespace(
        protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        configuration_sha256=configuration,
    )
    monkeypatch.setattr(validator, "validate_protocol", lambda _root: fake)
    return load_study_bindings(ROOT)


def _generic_spec(action_id: str) -> bytes:
    return strict_json_dumps({
        "schema_version": "prospective-dispatcher-test-generic-v1",
        "action_id": action_id,
    }).encode()


def _catalog() -> tuple[ActionOffer, ...]:
    offers: list[ActionOffer] = []
    for action_id in COLLECTION_ACTION_IDS:
        action = COLLECTION_ACTION_ROUTE[action_id]
        terminal = action in {
            RouteAction.ACCEPT,
            RouteAction.REJECT,
            RouteAction.ABSTAIN,
        }
        if terminal:
            available, reason = False, "terminal_governed"
        elif action_id == "static_bootstrap":
            available, reason = False, "deterministic_bootstrap_completed"
        elif action_id == "hardening_curator":
            available, reason = False, "curator_only_not_policy_available"
        elif action_id == "semantic_primary":
            available, reason = True, "semantic_binding_available"
        else:
            available, reason = True, "execution_binding_available"
        offers.append(ActionOffer(
            action_id=action_id,
            route_action=action,
            evidence_kind=None if terminal else _ACTION_KIND[action],
            adapter_id=(
                "adapter-oracle-hardening"
                if action_id == "hardening_curator"
                else f"adapter-{action_id}"
            ),
            adapter_version="v1",
            action_spec_sha256=hashlib.sha256(
                _generic_spec(action_id)
            ).hexdigest(),
            available=available,
            availability_reason=reason,
            expected_cost=(
                EvidenceCost() if terminal else EvidenceCost(wall_seconds=1.0)
            ),
        ))
    return tuple(offers)


def _initial_manifest(task_id: str, candidate_id: str) -> ValidityManifest:
    route = RouteDecision(
        action=RouteAction.RUN_STATIC,
        policy_version="dispatcher-static-bootstrap-v1",
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.35,
        estimated_relative_cost=0.01,
        reasons=("deterministic static bootstrap",),
        terminal=False,
    )
    observation = EvidenceObservation(
        kind=EvidenceKind.STATIC,
        status=EvidenceStatus.INCONCLUSIVE,
        source="prospective-static-bootstrap",
        source_version="v1",
        acquisition_id="acq-" + _sha(f"bootstrap:{task_id}:{candidate_id}")[:32],
        cost=EvidenceCost(wall_seconds=1.0),
    )
    return ValidityManifest(
        instance_id=task_id,
        candidate_id=candidate_id,
        lifecycle_stage=LifecycleStage.ROLLOUT,
        risk_profile=RiskProfile(
            language="python",
            files_changed=2,
            lines_changed=20,
            targeted_execution_available=True,
            full_execution_available=True,
        ),
        provenance={
            "repository": "opaque/repository",
            "dataset_revision": "dispatcher-fixture-v1",
            "base_commit": "a" * 40,
            "candidate_patch_sha256": candidate_id.removeprefix("sha256:"),
        },
        evidence=[observation],
        route_history=[route],
    )


def _candidate_input(
    manifest: ValidityManifest,
    catalog: tuple[ActionOffer, ...],
) -> CandidateRoundInput:
    bootstrap = BootstrapHistoryStep(
        receipt_sha256=_sha(
            f"bootstrap-receipt:{manifest.instance_id}:{manifest.candidate_id}"
        ),
        route=RouterRouteStep.from_route_decision(manifest.route_history[0]),
        observation=manifest.evidence[0],
    )
    state = RouterStateView.from_manifest(
        manifest,
        bootstrap_history=(bootstrap,),
    )
    return CandidateRoundInput(
        candidate_id=manifest.candidate_id,
        activity=CandidateActivity.ACTIVE,
        decision_count=0,
        nonterminal_acquisition_count=0,
        completed_nonterminal_action_ids=(),
        router_state_sha256=state.canonical_digest(),
        history_sha256=state.history_sha256(),
        policy_trajectory_head_sha256=SCHEDULER_GENESIS_SHA256,
        bound_router_decision=BoundRouterDecision.from_router_state(state),
        action_catalog=catalog,
    )


def _provisioning_receipt(
    *,
    candidate_id: str,
    workspace_id: str,
    workspace_identity_sha256: str,
    fresh_worktree: bool,
) -> ProvisioningReceipt:
    payload = {
        "schema_version": "prospective-pilot-provisioning-receipt-0.1.0",
        "provisioner_id": "dispatcher-fixture-provisioner",
        "provisioner_version": "v1",
        "workspace_id": workspace_id,
        "workspace_identity_sha256": workspace_identity_sha256,
        "base_commit": "a" * 40,
        "candidate_id": candidate_id,
        "architecture": "test-architecture",
        "substrate": "local-fixture",
        "harness_sha256": _sha("harness"),
        "image_digest": "sha256:" + _sha("image"),
        "dependency_lock_sha256": _sha("dependency-lock"),
        "execution_spec_sha256": _sha("execution-spec"),
        "test_spec_sha256": _sha("test-spec"),
        "clean_start": True,
        "fresh_worktree": fresh_worktree,
        "credential_names": [],
    }
    return ProvisioningReceipt(
        provisioner_id="dispatcher-fixture-provisioner",
        provisioner_version="v1",
        receipt_sha256=hashlib.sha256(
            strict_json_dumps(payload).encode()
        ).hexdigest(),
        workspace_id=workspace_id,
        workspace_identity_sha256=workspace_identity_sha256,
        base_commit="a" * 40,
        candidate_id=candidate_id,
        architecture="test-architecture",
        substrate="local-fixture",
        harness_sha256=_sha("harness"),
        image_digest="sha256:" + _sha("image"),
        dependency_lock_sha256=_sha("dependency-lock"),
        execution_spec_sha256=_sha("execution-spec"),
        test_spec_sha256=_sha("test-spec"),
        clean_start=True,
        fresh_worktree=fresh_worktree,
        credential_names=(),
    )


def _make_spec(
    root: pathlib.Path,
    *,
    action_id: str,
    offer: ActionOffer,
    initial: ValidityManifest,
    launch_marker: pathlib.Path,
    salt: str,
    repeat_of: str | None = None,
) -> ExecutableActionSpec:
    workspace = (root / f"workspace-{salt}").resolve()
    state = (root / f"state-{salt}").resolve()
    workspace.mkdir(parents=True)
    state.mkdir(parents=True)
    workspace_id = "sha256:" + _sha(f"workspace:{salt}")
    marker_payload = strict_json_dumps(
        {
            "schema_version": WORKSPACE_IDENTITY_SCHEMA_VERSION,
            "instance_id": initial.instance_id,
            "candidate_id": initial.candidate_id,
            "base_commit": "a" * 40,
            "workspace_id": workspace_id,
        },
        indent=2,
    ) + "\n"
    marker = workspace / ".bench-cleanser-workspace.json"
    marker.write_text(marker_payload, encoding="utf-8")
    marker_sha = hashlib.sha256(marker_payload.encode()).hexdigest()
    route = RouteDecision(
        action=offer.route_action,
        policy_version="dispatcher-fixture-v1",
        candidate_risk=0.2,
        verifier_risk=0.3,
        expected_information_gain=0.4,
        estimated_relative_cost=0.2,
        reasons=("sampled typed dispatcher action",),
        terminal=False,
    )
    routed = ValidityManifest.from_dict(initial.to_dict())
    routed.add_decision(route)
    assert offer.evidence_kind is not None
    request = AcquisitionRequest(
        kind=offer.evidence_kind,
        source="prospective-dispatcher-fixture",
        source_version="v1",
        workspace_root=str(workspace),
        argv=(
            sys.executable,
            "-c",
            (
                "import pathlib,sys;"
                "p=pathlib.Path(sys.argv[1]);"
                "p.open('a',encoding='utf-8').write('launch\\n')"
            ),
            str(launch_marker),
        ),
        timeout_seconds=5.0,
        max_capture_bytes=4096,
        supports_incorrect_exit_codes=(
            () if offer.evidence_kind == EvidenceKind.SEMANTIC else (1,)
        ),
    )
    plan = RouteAcquisitionPlan(
        instance_id=initial.instance_id,
        candidate_id=initial.candidate_id,
        manifest_sha256=routed.canonical_digest(),
        base_commit="a" * 40,
        workspace_root=str(workspace),
        workspace_id=workspace_id,
        workspace_identity_path=".bench-cleanser-workspace.json",
        workspace_identity_sha256=marker_sha,
        acquisition_id=_DUMMY_ACQUISITION_ID,
        coordination_directory=str(state),
        artifact_directory=str(state / "artifacts"),
        output_path=str(state / "completed.json"),
        requests={offer.route_action: request},
    )
    fresh = action_id == "full_repeat"
    receipt = _provisioning_receipt(
        candidate_id=initial.candidate_id,
        workspace_id=workspace_id,
        workspace_identity_sha256=marker_sha,
        fresh_worktree=fresh,
    )
    return ExecutableActionSpec.from_plan(
        action_id=action_id,
        route_action=offer.route_action,
        evidence_kind=offer.evidence_kind,
        adapter_id=offer.adapter_id,
        adapter_version=offer.adapter_version,
        manifest_before=routed,
        plan=plan,
        resource_kind="fresh_worktree" if fresh else "exclusive_bundle",
        resource_key=f"fixture-resource:{salt}",
        provisioning_receipt=receipt,
        artifact_retention=ArtifactRetention(
            store_id=f"fixture-store-{salt}",
            artifact_directory=plan.artifact_directory,
        ),
        repeat_of_action_spec_sha256=repeat_of,
    )


@dataclass(frozen=True)
class DispatchFixture:
    round_decision: TaskRoundDecision
    preimages: dict[str, bytes]
    reservations: tuple[ReservationRequest, ...]
    target_acquisition_id: str
    launch_marker: pathlib.Path
    specs: dict[str, ExecutableActionSpec]


def _dispatch_fixture(
    root: pathlib.Path,
    bindings: SchedulerBindings,
) -> DispatchFixture:
    task_id = "django__django-11299"
    manifests = {
        candidate_id: _initial_manifest(task_id, candidate_id)
        for candidate_id in bindings.frame.candidate_ids_for(task_id)
    }
    inputs = tuple(
        _candidate_input(manifests[candidate_id], _catalog())
        for candidate_id in bindings.frame.candidate_ids_for(task_id)
    )
    preliminary = build_task_round_decision(
        bindings=bindings,
        task_id=task_id,
        scheduled_at=_timestamp(0),
        candidates=inputs,
    )
    selected = {
        item.candidate_id: item
        for item in preliminary.scheduled_decisions
        if not item.logged_policy_decision.terminal
    }
    assert selected
    launch_marker = (root / "launches.txt").resolve()
    specs: dict[str, ExecutableActionSpec] = {}
    updated: list[CandidateRoundInput] = []
    for candidate in inputs:
        scheduled = selected.get(candidate.candidate_id)
        if scheduled is None:
            updated.append(candidate)
            continue
        offer = scheduled.logged_policy_decision.chosen_offer
        spec = _make_spec(
            root,
            action_id=offer.action_id,
            offer=offer,
            initial=manifests[candidate.candidate_id],
            launch_marker=launch_marker,
            salt=candidate.candidate_id[-10:],
        )
        specs[candidate.candidate_id] = spec
        catalog = tuple(
            replace(item, action_spec_sha256=spec.canonical_digest())
            if item.action_id == offer.action_id
            else item
            for item in candidate.action_catalog
        )
        updated.append(replace(candidate, action_catalog=catalog))
    round_decision = build_task_round_decision(
        bindings=bindings,
        task_id=task_id,
        scheduled_at=_timestamp(0),
        candidates=tuple(updated),
    )
    preimages = {
        hashlib.sha256(_generic_spec(action_id)).hexdigest(): _generic_spec(action_id)
        for action_id in COLLECTION_ACTION_IDS
    }
    reservations: list[ReservationRequest] = []
    target: str | None = None
    for scheduled in round_decision.scheduled_decisions:
        logged = scheduled.logged_policy_decision
        if logged.terminal:
            continue
        assert logged.acquisition_id is not None
        spec = specs[logged.candidate_id]
        assert logged.chosen_offer.action_spec_sha256 == spec.canonical_digest()
        preimages[spec.canonical_digest()] = spec.canonical_preimage()
        reservations.append(ReservationRequest(
            acquisition_id=logged.acquisition_id,
            resource_kind=spec.resource_kind,
            resource_key=spec.resource_key,
            details=spec.reservation_details(),
        ))
        target = target or logged.acquisition_id
    assert target is not None
    used_digests = {
        offer.action_spec_sha256
        for candidate in round_decision.candidates
        for offer in candidate.action_catalog
    }
    return DispatchFixture(
        round_decision=round_decision,
        preimages={digest: preimages[digest] for digest in used_digests},
        reservations=tuple(reservations),
        target_acquisition_id=target,
        launch_marker=launch_marker,
        specs=specs,
    )


def _commit(
    database: pathlib.Path,
    bindings: SchedulerBindings,
    fixture: DispatchFixture,
) -> ProspectiveLedger:
    ledger = ProspectiveLedger(database, bindings=bindings)
    ProspectiveDispatcher(ledger, claimant="commit-worker").commit_round(
        fixture.round_decision,
        committed_at=_timestamp(1),
        action_spec_preimages=fixture.preimages,
        reservations=fixture.reservations,
    )
    return ledger


def _dispatch_worker(
    database: str,
    acquisition_id: str,
    worker_index: int,
    start: Any,
    output: Any,
) -> None:
    try:
        ledger = ProspectiveLedger(pathlib.Path(database))
        dispatcher = ProspectiveDispatcher(
            ledger,
            claimant=f"contending-worker-{worker_index}",
        )
        start.wait()
        result = dispatcher.dispatch_committed(
            acquisition_id=acquisition_id,
            claimed_at=_timestamp(2),
            completed_at=_timestamp(3),
        )
        output.put(("ok", result.state, result.claim_id))
    except BaseException as exc:  # pragma: no cover - asserted by parent.
        output.put(("error", type(exc).__name__, str(exc)))


def test_commit_claim_launch_and_strict_ingest(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "single", bindings)
    ledger = _commit(tmp_path / "single.sqlite3", bindings, fixture)
    outcome = ProspectiveDispatcher(
        ledger,
        claimant="single-worker",
    ).dispatch_committed(
        acquisition_id=fixture.target_acquisition_id,
        claimed_at=_timestamp(2),
        completed_at=_timestamp(3),
    )
    assert outcome.state == "completed"
    assert outcome.result is not None and outcome.result.inserted is True
    assert fixture.launch_marker.read_text(encoding="utf-8") == "launch\n"
    assert ledger.table_counts()["claims"] == 1
    assert ledger.table_counts()["results"] == 1
    assert ledger.audit().protocol_result_count == 1


def test_two_workers_only_winning_claim_launches(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "race", bindings)
    ledger = _commit(tmp_path / "race.sqlite3", bindings, fixture)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    output = context.Queue()
    workers = [
        context.Process(
            target=_dispatch_worker,
            args=(
                str(ledger.path),
                fixture.target_acquisition_id,
                index,
                start,
                output,
            ),
        )
        for index in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    results = [output.get(timeout=30) for _ in workers]
    for worker in workers:
        worker.join(timeout=30)
        assert worker.exitcode == 0
    assert [item[0] for item in results] == ["ok", "ok"]
    assert sorted(item[1] for item in results) == ["already_claimed", "completed"]
    assert fixture.launch_marker.read_text(encoding="utf-8") == "launch\n"
    assert ledger.table_counts()["claims"] == 1
    assert ledger.table_counts()["results"] == 1


def test_manifest_route_plan_request_and_reservation_tamper_precedes_claim(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "tamper", bindings)
    ledger = _commit(tmp_path / "tamper.sqlite3", bindings, fixture)
    envelope = ledger.load_dispatch_envelope(fixture.target_acquisition_id)
    manifest, route, plan = envelope.action_spec.execution_inputs(
        fixture.target_acquisition_id
    )

    manifest_value = manifest.to_dict()
    manifest_value["provenance"]["dataset_revision"] = "tampered"
    with pytest.raises(LedgerError):
        envelope.validate_execution_inputs(
            manifest_before=ValidityManifest.from_dict(manifest_value),
            route_decision=route,
            plan=plan,
        )
    with pytest.raises(LedgerError):
        envelope.validate_execution_inputs(
            manifest_before=manifest,
            route_decision=replace(route, reasons=("tampered",)),
            plan=plan,
        )
    plan_value = plan.to_dict()
    plan_value["output_path"] = str((tmp_path / "substituted.json").resolve())
    with pytest.raises(LedgerError):
        envelope.validate_execution_inputs(
            manifest_before=manifest,
            route_decision=route,
            plan=RouteAcquisitionPlan.from_dict(plan_value),
        )
    request_value = plan.to_dict()
    request_value["requests"][route.action.value]["argv"].append("tampered")
    with pytest.raises(LedgerError):
        envelope.validate_execution_inputs(
            manifest_before=manifest,
            route_decision=route,
            plan=RouteAcquisitionPlan.from_dict(request_value),
        )
    assert ledger.table_counts()["claims"] == 0

    other = _dispatch_fixture(tmp_path / "reservation", bindings)
    reservation = next(
        item
        for item in other.reservations
        if item.acquisition_id == other.target_acquisition_id
    )
    wrong = replace(reservation, resource_key=reservation.resource_key + "-tampered")
    reservations = tuple(
        wrong if item.acquisition_id == wrong.acquisition_id else item
        for item in other.reservations
    )
    # The wrong reservation belongs to a different round/acquisition and must fail
    # atomically before any claim or launch.
    with pytest.raises(LedgerError):
        tamper_ledger = ProspectiveLedger(
            tmp_path / "reservation.sqlite3",
            bindings=bindings,
        )
        ProspectiveDispatcher(
            tamper_ledger,
            claimant="reservation-tamper-worker",
        ).commit_round(
            other.round_decision,
            committed_at=_timestamp(1),
            action_spec_preimages=other.preimages,
            reservations=reservations,
        )


def test_result_ack_loss_recovers_exact_committed_result(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "ack", bindings)
    ledger = _commit(tmp_path / "ack.sqlite3", bindings, fixture)
    original = ledger.ingest_completed_route_acquisition

    def lose_ack(**kwargs: Any) -> Any:
        original(**kwargs)
        raise OSError("synthetic acknowledgement loss")

    monkeypatch.setattr(ledger, "ingest_completed_route_acquisition", lose_ack)
    outcome = ProspectiveDispatcher(
        ledger,
        claimant="ack-worker",
    ).dispatch_committed(
        acquisition_id=fixture.target_acquisition_id,
        claimed_at=_timestamp(2),
        completed_at=_timestamp(3),
    )
    assert outcome.state == "recovered"
    assert outcome.result is not None and outcome.result.inserted is False
    assert ledger.table_counts()["results"] == 1
    assert ledger.table_counts()["incidents"] == 0


def test_live_claim_recovery_never_halts_and_operator_halt_is_explicit(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "recovery", bindings)
    ledger = _commit(tmp_path / "recovery.sqlite3", bindings, fixture)
    envelope = ledger.load_dispatch_envelope(fixture.target_acquisition_id)
    manifest, route, plan = envelope.action_spec.execution_inputs(
        fixture.target_acquisition_id
    )
    claimed = ledger.claim_executable_dispatch(
        fixture.target_acquisition_id,
        claimant="live-owner",
        claimed_at=_timestamp(2),
        manifest_before=manifest,
        route_decision=route,
        plan=plan,
    )
    assert claimed is not None
    dispatcher = ProspectiveDispatcher(ledger, claimant="recovery-worker")
    with pytest.raises(FileNotFoundError):
        dispatcher.recover_completed_claim(claim_id=claimed.claim.claim_id)
    assert ledger.table_counts()["incidents"] == 0
    losing = dispatcher.dispatch_committed(
        acquisition_id=fixture.target_acquisition_id,
        claimed_at=_timestamp(3),
    )
    assert losing.state == "already_claimed"
    assert not fixture.launch_marker.exists()
    incident = dispatcher.halt_abandoned_claim(
        claim_id=claimed.claim.claim_id,
        worker_exit=WorkerExitReceipt(
            operator_id="fixture-supervisor",
            claimant="live-owner",
            worker_exit_receipt_sha256=_sha("observed-worker-exit"),
            observed_at=_timestamp(4),
            exit_code=23,
        ),
        halted_at=_timestamp(5),
    )
    assert incident.inserted is True
    assert ledger.table_counts()["incidents"] == 1
    assert ledger.claim_dispatch(
        fixture.target_acquisition_id,
        claimant="late-worker",
        claimed_at=_timestamp(6),
    ) is None


def test_full_repeat_equivalence_and_distinct_fresh_identities(
    tmp_path: pathlib.Path,
) -> None:
    candidate_id = "sha256:" + _sha("repeat-candidate")
    initial = _initial_manifest("django__django-11299", candidate_id)
    full_offer = next(
        offer for offer in _catalog() if offer.action_id == "full_primary"
    )
    launch = (tmp_path / "repeat-launches.txt").resolve()
    primary = _make_spec(
        tmp_path,
        action_id="full_primary",
        offer=full_offer,
        initial=initial,
        launch_marker=launch,
        salt="primary",
    )
    repeat_offer = replace(full_offer, action_id="full_repeat")
    repeated = _make_spec(
        tmp_path,
        action_id="full_repeat",
        offer=repeat_offer,
        initial=initial,
        launch_marker=launch,
        salt="repeat",
        repeat_of=primary.canonical_digest(),
    )
    repeated.validate_repeat_of(primary)

    plan = repeated.realized_plan(_DUMMY_ACQUISITION_ID).to_dict()
    plan["requests"][RouteAction.RUN_FULL.value]["argv"].append("changed")
    changed_plan = RouteAcquisitionPlan.from_dict(plan)
    changed = ExecutableActionSpec.from_plan(
        action_id="full_repeat",
        route_action=RouteAction.RUN_FULL,
        evidence_kind=EvidenceKind.FULL_EXECUTION,
        adapter_id=repeated.adapter_id,
        adapter_version=repeated.adapter_version,
        manifest_before=repeated.manifest_before(),
        plan=changed_plan,
        resource_kind=repeated.resource_kind,
        resource_key=repeated.resource_key,
        provisioning_receipt=repeated.provisioning_receipt,
        artifact_retention=repeated.artifact_retention,
        repeat_of_action_spec_sha256=primary.canonical_digest(),
    )
    with pytest.raises(LedgerError, match="execution/test/request"):
        changed.validate_repeat_of(primary)


def test_symlinked_raw_artifact_is_never_recovered_or_auto_halted(
    tmp_path: pathlib.Path,
    bindings: SchedulerBindings,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "symlink", bindings)
    ledger = _commit(tmp_path / "symlink.sqlite3", bindings, fixture)
    envelope = ledger.load_dispatch_envelope(fixture.target_acquisition_id)
    manifest, route, plan = envelope.action_spec.execution_inputs(
        fixture.target_acquisition_id
    )
    claimed = ledger.claim_executable_dispatch(
        fixture.target_acquisition_id,
        claimant="symlink-owner",
        claimed_at=_timestamp(2),
        manifest_before=manifest,
        route_decision=route,
        plan=plan,
    )
    assert claimed is not None
    execute_route_acquisition(manifest, route, plan)
    artifact = pathlib.Path(plan.artifact_directory) / (
        f"{fixture.target_acquisition_id}.json"
    )
    retained_copy = artifact.with_name("retained-copy.json")
    shutil.copyfile(artifact, retained_copy)
    artifact.unlink()
    artifact.symlink_to(retained_copy)
    with pytest.raises(ValueError, match="symbolic link"):
        ProspectiveDispatcher(
            ledger,
            claimant="recovery-worker",
        ).recover_completed_claim(
            claim_id=claimed.claim.claim_id,
            completed_at=_timestamp(3),
        )
    assert ledger.table_counts()["incidents"] == 0
    assert ledger.table_counts()["results"] == 0
