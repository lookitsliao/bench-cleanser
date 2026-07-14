"""Paired verification-gap corpus contract tests."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace

import pytest

import bench_cleanser.verification.corpus as verification_corpus
from bench_cleanser.verification.corpus import (
    CORPUS_SCHEMA_VERSION,
    MIN_ADJUDICATOR_AGREEMENT,
    AcquisitionDecision,
    ActionPropensity,
    CandidateAdjudication,
    CandidateCorrectness,
    CandidateType,
    CorpusSplit,
    EvidenceValidity,
    EvidenceValidityAdjudication,
    PairedEvidence,
    TaskAdjudication,
    TaskValidity,
    VerificationGapRecord,
    bridge_logged_policy_observation,
    build_acquisition_decision,
    build_corpus_report,
    load_corpus,
    main,
    normalize_repository_identity,
    validate_corpus,
)
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
from bench_cleanser.verification.policy_log import (
    GENESIS_TRAJECTORY_HEAD_SHA256,
    ActionOffer,
    BehaviorProbability,
    LoggedPolicyDecision,
    RouterStateView,
    canonical_action_spec_sha256,
)

_DEFAULT_CANDIDATE_SHA256 = "e" * 64


def _validity_adjudication(
    validity: EvidenceValidity = EvidenceValidity.VALID,
    *,
    source: str = "blinded-evidence-panel",
    protocol_version: str = "v1",
    blinded: bool = True,
    annotator_count: int = 2,
    agreement: float | None = 1.0,
    notes: str = "",
) -> EvidenceValidityAdjudication:
    return EvidenceValidityAdjudication(
        validity=validity,
        source=source,
        protocol_version=protocol_version,
        blinded=blinded,
        annotator_count=annotator_count,
        agreement=agreement,
        notes=notes,
    )


def _manifest(
    *,
    instance_id: str = "owner__repo-1",
    candidate_id: str = f"sha256:{_DEFAULT_CANDIDATE_SHA256}",
    repository: str = "owner/repo",
) -> ValidityManifest:
    return ValidityManifest(
        instance_id=instance_id,
        candidate_id=candidate_id,
        lifecycle_stage=LifecycleStage.TRAINING,
        risk_profile=RiskProfile(
            language="python",
            files_changed=1,
            lines_changed=2,
            oracle_hardening_available=True,
        ),
        provenance={
            "dataset_revision": "fixture-v1",
            "repository": repository,
            "base_commit": "a" * 40,
            "candidate_generator": "fixture-agent-v1",
            "candidate_patch_sha256": candidate_id.removeprefix("sha256:"),
            "scaffold_version": "fixture-scaffold-v1",
            "prompt_version": "fixture-prompt-v1",
            "environment_image_digest": "sha256:" + "b" * 64,
            "dependency_lock_digest": "sha256:" + "c" * 64,
        },
    )


def _live_policy_decision(
    manifest: ValidityManifest,
    *,
    prior_head: str = GENESIS_TRAJECTORY_HEAD_SHA256,
    decided_at: str = "2026-01-02T12:00:00.000000Z",
    identity_index: int | None = None,
    trajectory_id: str = "trajectory-corpus-bridge",
) -> LoggedPolicyDecision:
    action_kind = {
        RouteAction.RUN_STATIC: EvidenceKind.STATIC,
        RouteAction.RUN_SEMANTIC: EvidenceKind.SEMANTIC,
        RouteAction.RUN_TARGETED: EvidenceKind.TARGETED_EXECUTION,
        RouteAction.RUN_FULL: EvidenceKind.FULL_EXECUTION,
        RouteAction.HARDEN_ORACLE: EvidenceKind.ORACLE_HARDENING,
    }
    terminal = {RouteAction.ACCEPT, RouteAction.REJECT, RouteAction.ABSTAIN}
    offers = [
        ActionOffer(
            action_id=f"route-{action.value}",
            route_action=action,
            evidence_kind=None if action in terminal else action_kind[action],
            adapter_id=(
                "terminal-disposition"
                if action in terminal
                else f"adapter-{action.value}"
            ),
            adapter_version="v1",
            action_spec_sha256=canonical_action_spec_sha256({
                "action": action.value,
                "variant": "default",
            }),
            available=True,
            availability_reason="fixture available",
            expected_cost=(
                EvidenceCost()
                if action in terminal
                else EvidenceCost(wall_seconds=1.0, usd=0.01)
            ),
        )
        for action in RouteAction
    ]
    offers.append(ActionOffer(
        action_id="semantic-second-adapter",
        route_action=RouteAction.RUN_SEMANTIC,
        evidence_kind=EvidenceKind.SEMANTIC,
        adapter_id="adapter-semantic-second",
        adapter_version="v2",
        action_spec_sha256=canonical_action_spec_sha256({
            "action": RouteAction.RUN_SEMANTIC.value,
            "variant": "second",
        }),
        available=True,
        availability_reason="fixture available",
        expected_cost=EvidenceCost(wall_seconds=0.5, usd=0.005),
    ))
    catalog = tuple(sorted(offers, key=lambda item: item.action_id))
    propensity = 1.0 / len(catalog)
    distribution = tuple(
        BehaviorProbability(item.action_id, propensity) for item in catalog
    )
    chosen_action_id = f"route-{RouteAction.RUN_STATIC.value}"
    lower = sum(
        item.propensity
        for item in distribution
        if item.action_id < chosen_action_id
    )
    state = RouterStateView.from_manifest(manifest)
    step = len(state.evidence_history)
    identity = step + 1 if identity_index is None else identity_index
    return LoggedPolicyDecision(
        trajectory_id=trajectory_id,
        decision_id=f"dec-{identity:032x}",
        acquisition_id=f"acq-{identity:032x}",
        decision_step=step,
        decided_at=decided_at,
        instance_id=state.instance_id,
        candidate_id=state.candidate_id,
        manifest_sha256=state.source_manifest_sha256,
        history_sha256=state.history_sha256(),
        router_state_sha256=state.canonical_digest(),
        prior_trajectory_head_sha256=prior_head,
        policy_id="paired-all-modalities",
        policy_version="v1",
        policy_code_config_sha256=hashlib.sha256(b"fixture-policy").hexdigest(),
        action_catalog=catalog,
        behavior_distribution=distribution,
        chosen_action_id=chosen_action_id,
        chosen_propensity=propensity,
        selection_reason_code="fixture-sampled-action",
        sampler_id="inverse-cdf",
        sampler_version="v1",
        sampler_draw=lower + propensity / 2.0,
        router_state=state,
    )


def _event(
    kind: EvidenceKind,
    *,
    event_id: str | None = None,
    replicate: int = 0,
    status: EvidenceStatus = EvidenceStatus.SUPPORTS_CORRECT,
    authoritative: bool = False,
    validity: EvidenceValidity = EvidenceValidity.VALID,
    verifier_validity: float | None = 0.9,
    subject_candidate_id: str = f"sha256:{_DEFAULT_CANDIDATE_SHA256}",
    manifest: ValidityManifest | None = None,
    prior_observations: tuple[PairedEvidence, ...] = (),
    available_actions: dict[EvidenceKind, float] | None = None,
    privileged_inputs: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
) -> PairedEvidence:
    resolved_manifest = manifest or _manifest(candidate_id=subject_candidate_id)
    identity_digest = hashlib.sha256(
        (
            f"{resolved_manifest.instance_id}\0{resolved_manifest.candidate_id}\0"
            f"{kind.value}\0{replicate}"
        ).encode()
    ).hexdigest()[:32]
    resolved_event_id = event_id or f"evt-{identity_digest}"
    decision_id = f"cur-{identity_digest}"
    acquisition_id = f"acq-{identity_digest}"
    decision = build_acquisition_decision(
        decision_id=decision_id,
        manifest=resolved_manifest,
        collection_policy="paired-all-modalities",
        collection_policy_version="v1",
        prior_observations=prior_observations,
        available_actions=available_actions or {kind: 1.0},
        chosen_action=kind,
        selection_reason="paired_collection",
    )
    return PairedEvidence(
        event_id=resolved_event_id,
        observation=EvidenceObservation(
            kind=kind,
            status=status,
            source=f"fixture-{kind.value}",
            source_version="v1",
            acquisition_id=acquisition_id,
            authoritative=authoritative,
            verifier_validity=verifier_validity,
            privileged_inputs=privileged_inputs,
            cost=EvidenceCost(
                wall_seconds=1.0,
                cpu_seconds=0.5,
                input_tokens=10,
                output_tokens=2,
                storage_bytes=100,
                usd=0.01,
            ),
            metadata=metadata or {},
        ),
        decision=decision,
        validity_adjudication=_validity_adjudication(validity),
        subject_candidate_id=subject_candidate_id,
        replicate=replicate,
        artifact_sha256="d" * 64,
        artifact_locator=f"artifact://fixture/{kind.value}/{replicate}",
        collected_at="2026-01-03T00:00:00Z",
    )


def _record(
    *,
    instance_id: str = "owner__repo-1",
    candidate_id: str = f"sha256:{_DEFAULT_CANDIDATE_SHA256}",
    repository: str = "owner/repo",
    split: CorpusSplit = CorpusSplit.DEVELOPMENT,
    task_validity: TaskValidity = TaskValidity.VALID,
    candidate_correctness: CandidateCorrectness = CandidateCorrectness.CORRECT,
) -> VerificationGapRecord:
    manifest = _manifest(
        instance_id=instance_id,
        candidate_id=candidate_id,
        repository=repository,
    )
    events: list[PairedEvidence] = []
    human_status = {
        CandidateCorrectness.CORRECT: EvidenceStatus.SUPPORTS_CORRECT,
        CandidateCorrectness.INCORRECT: EvidenceStatus.SUPPORTS_INCORRECT,
        CandidateCorrectness.NOT_APPLICABLE: EvidenceStatus.INCONCLUSIVE,
        CandidateCorrectness.INDETERMINATE: EvidenceStatus.INCONCLUSIVE,
    }[candidate_correctness]
    for kind, replicate, authoritative in (
        (EvidenceKind.STATIC, 0, False),
        (EvidenceKind.SEMANTIC, 0, False),
        (EvidenceKind.TARGETED_EXECUTION, 0, False),
        (EvidenceKind.FULL_EXECUTION, 0, False),
        (EvidenceKind.FULL_EXECUTION, 1, False),
        (EvidenceKind.ORACLE_HARDENING, 0, False),
        (EvidenceKind.HUMAN_ADJUDICATION, 0, True),
    ):
        events.append(_event(
            kind,
            replicate=replicate,
            status=(
                human_status
                if kind == EvidenceKind.HUMAN_ADJUDICATION
                else EvidenceStatus.SUPPORTS_CORRECT
            ),
            authoritative=authoritative,
            subject_candidate_id=candidate_id,
            manifest=manifest,
            prior_observations=tuple(events),
        ))
    return VerificationGapRecord(
        manifest=manifest,
        split=split,
        repository=repository,
        base_commit="a" * 40,
        task_created_at="2026-01-01T00:00:00Z",
        candidate_generated_at="2026-01-02T00:00:00Z",
        candidate_artifact_locator=f"artifact://candidates/{candidate_id}",
        candidate_type=CandidateType.AGENT,
        collection_policy="paired-all-modalities",
        collection_policy_version="v1",
        observations=tuple(events),
        task_adjudication=TaskAdjudication(
            task_validity=task_validity,
            source="blinded-expert-panel",
            protocol_version="v1",
            blinded=True,
            annotator_count=2,
            agreement=1.0,
        ),
        candidate_adjudication=CandidateAdjudication(
            candidate_correctness=candidate_correctness,
            source="blinded-expert-panel",
            protocol_version="v1",
            blinded=True,
            annotator_count=2,
            agreement=1.0,
        ),
    )


def _resequence(
    record: VerificationGapRecord,
    observations: tuple[PairedEvidence, ...],
    *,
    manifest: ValidityManifest | None = None,
    action_overrides: dict[int, dict[EvidenceKind, float]] | None = None,
) -> VerificationGapRecord:
    resolved_manifest = manifest or record.manifest
    rebuilt: list[PairedEvidence] = []
    for index, item in enumerate(observations):
        available_actions: (
            dict[EvidenceKind, float] | tuple[ActionPropensity, ...]
        ) = item.decision.available_actions
        if action_overrides and index in action_overrides:
            available_actions = action_overrides[index]
        decision = build_acquisition_decision(
            decision_id=item.decision.decision_id,
            manifest=resolved_manifest,
            collection_policy=record.collection_policy,
            collection_policy_version=record.collection_policy_version,
            prior_observations=tuple(rebuilt),
            available_actions=available_actions,
            chosen_action=item.observation.kind,
            selection_reason=item.decision.selection_reason,
        )
        rebuilt.append(replace(item, decision=decision))
    return replace(record, manifest=resolved_manifest, observations=tuple(rebuilt))


def test_complete_record_round_trips_and_validates() -> None:
    record = _record()

    restored = VerificationGapRecord.from_dict(record.to_dict())

    assert restored.to_dict() == record.to_dict()
    assert restored.canonical_digest() == record.canonical_digest()
    assert restored.schema_version == CORPUS_SCHEMA_VERSION
    validate_corpus([restored], require_paired=True)


def test_evidence_validity_adjudication_round_trips_with_provenance() -> None:
    adjudication = _validity_adjudication(
        EvidenceValidity.INVALID,
        source="blinded-evidence-panel-b",
        protocol_version="2026-07",
        blinded=True,
        annotator_count=3,
        agreement=0.875,
        notes="artifact digest mismatch confirmed independently",
    )

    restored = EvidenceValidityAdjudication.from_dict(adjudication.to_dict())

    assert restored == adjudication
    assert restored.to_dict() == {
        "validity": "invalid",
        "source": "blinded-evidence-panel-b",
        "protocol_version": "2026-07",
        "blinded": True,
        "annotator_count": 3,
        "agreement": 0.875,
        "notes": "artifact digest mismatch confirmed independently",
    }
    assert restored.determinate_paired_ready is True


def test_task_validity_and_conditional_candidate_truth_are_not_collapsed() -> None:
    with pytest.raises(ValueError, match="invalid task validity requires"):
        _record(
            task_validity=TaskValidity.INVALID,
            candidate_correctness=CandidateCorrectness.CORRECT,
        )
    with pytest.raises(ValueError, match="indeterminate task validity requires"):
        _record(
            task_validity=TaskValidity.INDETERMINATE,
            candidate_correctness=CandidateCorrectness.NOT_APPLICABLE,
        )
    with pytest.raises(ValueError, match="valid task validity cannot"):
        _record(
            task_validity=TaskValidity.VALID,
            candidate_correctness=CandidateCorrectness.NOT_APPLICABLE,
        )

    invalid = _record(
        task_validity=TaskValidity.INVALID,
        candidate_correctness=CandidateCorrectness.NOT_APPLICABLE,
    )
    indeterminate = _record(
        instance_id="owner__repo-2",
        candidate_id="sha256:" + "f" * 64,
        task_validity=TaskValidity.INDETERMINATE,
        candidate_correctness=CandidateCorrectness.INDETERMINATE,
    )
    validate_corpus([invalid], require_paired=True)
    validate_corpus([indeterminate], require_paired=True)

    unresolved_candidate = _record(
        task_validity=TaskValidity.VALID,
        candidate_correctness=CandidateCorrectness.INDETERMINATE,
    )
    with pytest.raises(ValueError, match="valid task has indeterminate"):
        validate_corpus([unresolved_candidate], require_paired=True)


def test_task_adjudication_is_identical_across_candidates() -> None:
    first = _record()
    second = _record(candidate_id="sha256:" + "f" * 64)
    validate_corpus([first, second])

    changed = replace(
        second,
        task_adjudication=replace(second.task_adjudication, notes="changed"),
    )
    with pytest.raises(ValueError, match="task adjudication changes across candidates"):
        validate_corpus([first, changed])


def test_legacy_boolean_truth_fields_fail_with_migration_errors() -> None:
    payload = _record().to_dict()
    candidate = payload["candidate_adjudication"]
    candidate["candidate_correct"] = True
    del candidate["candidate_correctness"]
    with pytest.raises(ValueError, match="legacy boolean candidate correctness"):
        VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    payload["candidate_adjudication"]["candidate_correctness"] = True
    with pytest.raises(ValueError, match="legacy boolean candidate correctness"):
        VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    task = payload["task_adjudication"]
    task["task_valid"] = True
    del task["task_validity"]
    with pytest.raises(ValueError, match="legacy boolean task validity"):
        VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    payload["task_adjudication"]["task_validity"] = True
    with pytest.raises(ValueError, match="legacy boolean task validity"):
        VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    payload["adjudication"] = payload.pop("candidate_adjudication")
    with pytest.raises(ValueError, match="legacy record.adjudication"):
        VerificationGapRecord.from_dict(payload)


def test_legacy_scalar_evidence_validity_fails_with_migration_error() -> None:
    payload = _record().to_dict()
    observation = payload["observations"][0]
    del observation["validity_adjudication"]
    observation["validity_label"] = "valid"

    with pytest.raises(
        ValueError,
        match=(
            r"legacy observations\[0\]\.validity_label is unsupported in corpus "
            r"0\.5\.0; provide provenance-bearing validity_adjudication"
        ),
    ):
        VerificationGapRecord.from_dict(payload)


def test_live_policy_bridge_is_lossless_and_keeps_all_three_identities() -> None:
    manifest = _manifest()
    policy_decision = _live_policy_decision(manifest)
    observation = replace(
        _event(EvidenceKind.STATIC, manifest=manifest).observation,
        acquisition_id=policy_decision.acquisition_id or "",
    )
    event = bridge_logged_policy_observation(
        event_id="evt-live-policy-static-1",
        policy_decision=policy_decision,
        observation=observation,
        validity_adjudication=_validity_adjudication(),
        artifact_sha256="d" * 64,
        artifact_locator="artifact://fixture/live-policy/static/1",
        collected_at="2026-01-03T00:00:00Z",
    )

    restored = PairedEvidence.from_dict(event.to_dict())

    assert restored.to_dict() == event.to_dict()
    assert restored.to_dict()["decision_contract"] == "logged_policy"
    assert isinstance(restored.decision, LoggedPolicyDecision)
    assert restored.decision.to_dict() == policy_decision.to_dict()
    assert restored.decision.decision_sha256 == policy_decision.decision_sha256
    assert (
        restored.decision.trajectory_head_sha256
        == policy_decision.trajectory_head_sha256
    )
    assert len([
        offer
        for offer in restored.decision.action_catalog
        if offer.evidence_kind == EvidenceKind.SEMANTIC
    ]) == 2
    assert {
        offer.route_action
        for offer in restored.decision.action_catalog
        if offer.evidence_kind is None
    } == {RouteAction.ACCEPT, RouteAction.REJECT, RouteAction.ABSTAIN}
    assert {
        event.event_id,
        restored.decision.decision_id,
        restored.observation.acquisition_id,
    } == {
        "evt-live-policy-static-1",
        "dec-" + f"{1:032x}",
        "acq-" + f"{1:032x}",
    }

    record = replace(_record(), observations=(restored,))
    validate_corpus([record])
    report = build_corpus_report([record])
    exact = report["propensity_diagnostics"]["overall"][
        "action_level_behavior"
    ]
    assert exact["logged_policy_decisions"] == 1
    assert len([
        offer for offer in exact["offers"]
        if offer["evidence_kind"] == EvidenceKind.SEMANTIC.value
    ]) == 2
    assert {
        offer["route_action"]
        for offer in exact["offers"]
        if offer["evidence_kind"] is None
    } == {
        RouteAction.ACCEPT.value,
        RouteAction.REJECT.value,
        RouteAction.ABSTAIN.value,
    }


def test_live_policy_bridge_fails_closed_on_mismatched_or_posthoc_inputs() -> None:
    manifest = _manifest()
    decision = _live_policy_decision(manifest)
    observation = replace(
        _event(EvidenceKind.STATIC, manifest=manifest).observation,
        acquisition_id="acq-" + "9" * 32,
    )
    with pytest.raises(ValueError, match="acquisition_id must equal"):
        bridge_logged_policy_observation(
            event_id="evt-live-policy-static-1",
            policy_decision=decision,
            observation=observation,
            validity_adjudication=_validity_adjudication(),
            collected_at="2026-01-03T00:00:00Z",
        )

    terminal_offer = next(
        offer
        for offer in decision.action_catalog
        if offer.route_action == RouteAction.ABSTAIN
    )
    terminal_catalog = tuple(
        replace(
            offer,
            available=offer.action_id == terminal_offer.action_id,
            availability_reason=(
                "fixture available"
                if offer.action_id == terminal_offer.action_id
                else "fixture unavailable"
            ),
        )
        for offer in decision.action_catalog
    )
    terminal_distribution = (
        BehaviorProbability(terminal_offer.action_id, 1.0),
    )
    terminal = replace(
        decision,
        acquisition_id=None,
        action_catalog=terminal_catalog,
        behavior_distribution=terminal_distribution,
        chosen_action_id=terminal_offer.action_id,
        chosen_propensity=1.0,
        sampler_draw=0.5,
        decision_sha256="",
        trajectory_head_sha256="",
    )
    with pytest.raises(ValueError, match="terminal policy decisions"):
        bridge_logged_policy_observation(
            event_id="evt-terminal-has-no-observation",
            policy_decision=terminal,
            observation=replace(
                observation,
                acquisition_id="",
            ),
            validity_adjudication=_validity_adjudication(
                EvidenceValidity.INDETERMINATE
            ),
            collected_at="2026-01-03T00:00:00Z",
        )

    payload = bridge_logged_policy_observation(
        event_id="evt-live-policy-static-1",
        policy_decision=decision,
        observation=replace(
            observation,
            acquisition_id=decision.acquisition_id or "",
        ),
        validity_adjudication=_validity_adjudication(),
        collected_at="2026-01-03T00:00:00Z",
    ).to_dict()
    payload["decision"]["behavior_distribution"][0]["propensity"] = 0.9
    with pytest.raises(ValueError, match="propensities must sum to 1"):
        PairedEvidence.from_dict(payload)

    other_manifest = _manifest()
    other_manifest.provenance["dataset_revision"] = "different-fixture"
    other_decision = _live_policy_decision(other_manifest)
    foreign_event = bridge_logged_policy_observation(
        event_id="evt-foreign-manifest",
        policy_decision=other_decision,
        observation=replace(
            observation,
            acquisition_id=other_decision.acquisition_id or "",
        ),
        validity_adjudication=_validity_adjudication(),
        collected_at="2026-01-03T00:00:00Z",
    )
    with pytest.raises(ValueError, match="contradicts the pre-execution manifest"):
        replace(_record(), observations=(foreign_event,))


def test_live_policy_bridge_rejects_missing_and_future_observation_times() -> None:
    manifest = _manifest()
    first_decision = _live_policy_decision(manifest)
    first_observation = replace(
        _event(EvidenceKind.STATIC, manifest=manifest).observation,
        acquisition_id=first_decision.acquisition_id or "",
    )
    first_event = bridge_logged_policy_observation(
        event_id="evt-temporal-first",
        policy_decision=first_decision,
        observation=first_observation,
        validity_adjudication=_validity_adjudication(),
        collected_at="2026-01-03T00:00:00Z",
    )
    with pytest.raises(ValueError, match="requires collected_at"):
        replace(first_event, collected_at="")

    successor_manifest = ValidityManifest.from_dict(manifest.to_dict())
    successor_manifest.add_evidence(first_observation)
    successor_manifest.add_decision(RouteDecision(
        action=RouteAction.RUN_STATIC,
        policy_version="fixture-route-v1",
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.6,
        estimated_relative_cost=0.2,
        reasons=("fixture prior route",),
    ))
    future_observing_decision = _live_policy_decision(
        successor_manifest,
        prior_head=first_decision.trajectory_head_sha256,
        decided_at="2026-01-02T18:00:00.000000Z",
    )
    second_observation = replace(
        first_observation,
        acquisition_id=future_observing_decision.acquisition_id or "",
    )
    with pytest.raises(ValueError, match="cannot precede its latest observed evidence"):
        bridge_logged_policy_observation(
            event_id="evt-temporal-second",
            policy_decision=future_observing_decision,
            observation=second_observation,
            validity_adjudication=_validity_adjudication(),
            collected_at="2026-01-04T00:00:00Z",
            prior_observations=(first_event,),
        )

    invalid_second_event = PairedEvidence(
        event_id="evt-temporal-second",
        observation=second_observation,
        decision=future_observing_decision,
        validity_adjudication=_validity_adjudication(),
        subject_candidate_id=manifest.candidate_id,
        collected_at="2026-01-04T00:00:00Z",
    )
    with pytest.raises(ValueError, match="cannot precede its latest observed evidence"):
        replace(_record(), observations=(first_event, invalid_second_event))


def test_live_policy_decisions_cannot_follow_curated_collection() -> None:
    record = _record()
    curated = record.observations[0]
    successor_manifest = ValidityManifest.from_dict(record.manifest.to_dict())
    successor_manifest.add_evidence(curated.observation)
    successor_manifest.add_decision(RouteDecision(
        action=RouteAction.RUN_STATIC,
        policy_version="fixture-route-v1",
        candidate_risk=0.4,
        verifier_risk=0.3,
        expected_information_gain=0.6,
        estimated_relative_cost=0.2,
        reasons=("fixture prior route",),
    ))
    live_decision = _live_policy_decision(
        successor_manifest,
        prior_head="f" * 64,
        decided_at="2026-01-03T12:00:00.000000Z",
    )
    live_event = PairedEvidence(
        event_id="evt-live-after-curated",
        observation=replace(
            curated.observation,
            acquisition_id=live_decision.acquisition_id or "",
        ),
        decision=live_decision,
        validity_adjudication=_validity_adjudication(),
        subject_candidate_id=record.manifest.candidate_id,
        collected_at="2026-01-04T00:00:00Z",
    )

    with pytest.raises(ValueError, match="contiguous trajectory prefix"):
        replace(record, observations=(curated, live_event))


def test_report_exposes_denominators_completeness_validity_and_cost() -> None:
    report = build_corpus_report([_record()])

    assert report["records"] == 1
    assert report["repositories"] == 1
    assert report["paired_complete_records"] == 1
    assert report["task_validity_counts"] == {"valid": 1}
    assert report["candidate_correctness_counts"] == {"correct": 1}
    assert report["record_digests"] == [{
        "instance_id": "owner__repo-1",
        "candidate_id": f"sha256:{_DEFAULT_CANDIDATE_SHA256}",
        "record_sha256": _record().canonical_digest(),
    }]
    assert report["evidence_event_counts"]["full_execution"] == 2
    assert report["evidence_validity_counts"]["semantic"] == {"valid": 1}
    assert report["evidence_validity_adjudication_status_counts"]["semantic"] == {
        "paired_ready_determinate": 1,
    }
    assert report["evidence_validity_adjudication_protocol_counts"]["semantic"] == {
        "blinded-evidence-panel@v1": 1,
    }
    assert report["cost_totals"]["input_tokens"] == 70
    assert report["corpus_digest"]
    assert report["acquisition_trajectories"] == [{
        "instance_id": "owner__repo-1",
        "candidate_id": f"sha256:{_DEFAULT_CANDIDATE_SHA256}",
        "collection_policy": "paired-all-modalities",
        "collection_policy_version": "v1",
        "acquisition_trajectory_digest": _record().acquisition_trajectory_digest(),
    }]
    assert report["completeness_scope"] == "schema_and_collection_protocol_only"
    assert report["scientific_adequacy"]["assessed"] is False
    assert report["minimum_adjudicator_agreement"] == MIN_ADJUDICATOR_AGREEMENT
    propensity = report["propensity_diagnostics"]
    assert propensity["scope"] == "descriptive_logged_behavior_policy_only"
    assert propensity["overall"]["decisions"] == 7
    assert propensity["overall"]["deterministic_decisions"] == 7
    assert propensity["overall"]["randomized_decisions"] == 0
    assert propensity["contextual_overlap"]["assessed"] is False
    assert propensity["causal_validity"]["assessed"] is False
    assert propensity["causal_validity"]["off_policy_estimates_computed"] is False


def test_loader_rejects_malformed_rows_without_changing_denominator() -> None:
    valid = json.dumps(_record().to_dict())
    with pytest.raises(ValueError, match="line 2: invalid JSON"):
        load_corpus(io.StringIO(valid + "\n{broken\n"))


def test_loader_rejects_duplicate_json_keys() -> None:
    line = json.dumps(_record().to_dict()).replace(
        '"split": "development"',
        '"split": "development", "split": "test"',
    )
    with pytest.raises(ValueError, match="duplicate JSON object key 'split'"):
        load_corpus(io.StringIO(line))


def test_legacy_schemas_and_scalar_propensity_rows_fail_closed() -> None:
    payload = _record().to_dict()
    for legacy_version in ("0.2.0", "0.3.0", "0.4.0"):
        payload["schema_version"] = legacy_version
        with pytest.raises(
            ValueError,
            match=f"unsupported corpus schema_version '{legacy_version}'",
        ):
            VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    first = payload["observations"][0]
    del first["decision"]
    first["acquisition_probability"] = 1.0
    first["selection_reason"] = "legacy"
    with pytest.raises(ValueError, match="unknown fields"):
        VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    del payload["observations"][0]["decision_contract"]
    with pytest.raises(ValueError, match="decision_contract must be a string"):
        VerificationGapRecord.from_dict(payload)

    payload = _record().to_dict()
    payload["observations"][0]["decision_contract"] = "inferred-from-shape"
    with pytest.raises(ValueError, match="decision_contract has unknown value"):
        VerificationGapRecord.from_dict(payload)


def test_record_rejects_unknown_fields_and_privileged_manifest_provenance() -> None:
    payload = _record().to_dict()
    payload["unknown"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        VerificationGapRecord.from_dict(payload)

    manifest = _manifest()
    manifest.provenance["gold_patch_digest"] = "leak"
    with pytest.raises(ValueError, match="privileged truth or outcome"):
        replace(_record(), manifest=manifest)


def test_manifest_must_remain_preexecution() -> None:
    manifest = _manifest()
    manifest.add_evidence(_event(EvidenceKind.STATIC).observation)

    with pytest.raises(ValueError, match="pre-execution"):
        replace(_record(), manifest=manifest)


def test_repository_groups_cannot_cross_splits() -> None:
    development = _record()
    test = _record(
        instance_id="owner__repo-2",
        candidate_id="sha256:" + "f" * 64,
        split=CorpusSplit.TEST,
    )

    with pytest.raises(ValueError, match="cross corpus splits"):
        validate_corpus([development, test])


def test_repository_aliases_normalize_before_split_isolation() -> None:
    assert normalize_repository_identity(
        "https://github.com/Owner/Repo.git/"
    ) == "owner/repo"
    assert normalize_repository_identity(
        "git@github.com:owner/repo.git"
    ) == "owner/repo"

    development = _record(repository="https://github.com/Owner/Repo.git")
    test = _record(
        instance_id="owner__repo-2",
        candidate_id="sha256:" + "f" * 64,
        repository="git@github.com:owner/repo.git",
        split=CorpusSplit.TEST,
    )
    with pytest.raises(ValueError, match="cross corpus splits"):
        validate_corpus([development, test])


def test_unknown_repository_hosts_are_rejected_instead_of_guessed() -> None:
    with pytest.raises(ValueError, match="must use github.com"):
        normalize_repository_identity("https://gitlab.example/owner/repo")


def test_task_timestamp_requires_timezone_and_strict_splits_are_temporal() -> None:
    with pytest.raises(ValueError, match="include a timezone"):
        replace(_record(), task_created_at="2026-01-01T00:00:00")

    development = _record(
        instance_id="dev-1",
        candidate_id="sha256:" + "1" * 64,
        repository="owner/dev",
    )
    development = replace(
        development,
        task_created_at="2026-06-01T00:00:00Z",
        candidate_generated_at="2026-06-02T00:00:00Z",
        observations=tuple(
            replace(item, collected_at="2026-06-03T00:00:00Z")
            for item in development.observations
        ),
    )
    test = _record(
        instance_id="test-1",
        candidate_id="sha256:" + "2" * 64,
        repository="owner/test",
        split=CorpusSplit.TEST,
    )
    test = replace(
        test,
        task_created_at="2026-05-01T00:00:00Z",
        candidate_generated_at="2026-05-02T00:00:00Z",
        observations=tuple(
            replace(item, collected_at="2026-05-03T00:00:00Z")
            for item in test.observations
        ),
    )

    with pytest.raises(ValueError, match="time splits overlap"):
        validate_corpus([development, test], require_paired=True)


def test_strict_pairing_requires_every_modality_and_repeated_full_runs() -> None:
    record = _record()
    no_semantic = _resequence(
        record,
        tuple(
            item for item in record.observations
            if item.observation.kind != EvidenceKind.SEMANTIC
        ),
    )
    with pytest.raises(ValueError, match="missing evidence kinds"):
        validate_corpus([no_semantic], require_paired=True)

    one_full = _resequence(
        record,
        tuple(
            item for item in record.observations
            if not (
                item.observation.kind == EvidenceKind.FULL_EXECUTION
                and item.replicate == 1
            )
        ),
    )
    with pytest.raises(ValueError, match="fewer than two conclusive full-execution"):
        validate_corpus([one_full], require_paired=True)

    unavailable_full = _resequence(
        record,
        tuple(
            replace(
                item,
                observation=replace(
                    item.observation,
                    status=EvidenceStatus.UNAVAILABLE,
                    authoritative=False,
                ),
                validity_adjudication=_validity_adjudication(
                    EvidenceValidity.INVALID
                ),
                artifact_sha256="",
                artifact_locator="",
            )
            if item.observation.kind == EvidenceKind.FULL_EXECUTION
            else item
            for item in record.observations
        ),
    )
    with pytest.raises(ValueError, match="fewer than two conclusive full-execution"):
        validate_corpus([unavailable_full], require_paired=True)


def test_strict_pairing_rejects_selectively_logged_or_unblinded_truth() -> None:
    record = _record()
    selected = _resequence(
        record,
        record.observations,
        action_overrides={
            1: {EvidenceKind.SEMANTIC: 0.5, EvidenceKind.STATIC: 0.5},
        },
    )
    with pytest.raises(ValueError, match="probability-1"):
        validate_corpus([selected], require_paired=True)

    unblinded = replace(
        _record(),
        candidate_adjudication=replace(
            _record().candidate_adjudication, blinded=False
        ),
    )
    with pytest.raises(ValueError, match="not blinded"):
        validate_corpus([unblinded], require_paired=True)


@pytest.mark.parametrize(
    "adjudication_changes",
    [
        {"blinded": False},
        {"annotator_count": 1},
        {"agreement": None},
        {"agreement": MIN_ADJUDICATOR_AGREEMENT - 0.01},
    ],
    ids=["unblinded", "single-reviewer", "missing-agreement", "weak-agreement"],
)
def test_determinate_evidence_adjudication_quality_is_a_paired_requirement(
    adjudication_changes: dict[str, object],
) -> None:
    record = _record()
    events = list(record.observations)
    events[0] = replace(
        events[0],
        validity_adjudication=replace(
            events[0].validity_adjudication,
            **adjudication_changes,
        ),
    )
    incomplete = replace(record, observations=tuple(events))

    validate_corpus([incomplete])
    with pytest.raises(
        ValueError,
        match="determinate evidence-validity adjudication is not blinded",
    ):
        validate_corpus([incomplete], require_paired=True)


def test_indeterminate_evidence_adjudication_is_paired_but_excluded() -> None:
    record = _record()
    events = list(record.observations)
    events[0] = replace(
        events[0],
        validity_adjudication=_validity_adjudication(
            EvidenceValidity.INDETERMINATE,
            source="blinded-disagreement-panel",
            protocol_version="v2",
            agreement=None,
            notes="reviewers could not establish evidence validity",
        ),
    )
    record = replace(record, observations=tuple(events))

    validate_corpus([record], require_paired=True)
    report = build_corpus_report([record])

    assert report["paired_complete_records"] == 1
    assert report["incomplete_records"] == []
    assert report["evidence_validity_counts"]["static"] == {"indeterminate": 1}
    assert report["evidence_validity_adjudication_status_counts"]["static"] == {
        "indeterminate_excluded": 1,
    }
    assert report["evidence_validity_adjudication_protocol_counts"]["static"] == {
        "blinded-disagreement-panel@v2": 1,
    }


def test_strict_pairing_checks_declared_evidence_availability() -> None:
    manifest = _manifest()
    manifest.risk_profile = replace(
        manifest.risk_profile,
        oracle_hardening_available=False,
    )
    record = _record()
    contradictory = _resequence(record, record.observations, manifest=manifest)

    with pytest.raises(ValueError, match="availability contradicts"):
        validate_corpus([contradictory], require_paired=True)


def test_strict_pairing_requires_candidate_and_evidence_artifact_identity() -> None:
    missing_provenance_manifest = _manifest()
    del missing_provenance_manifest.provenance["candidate_patch_sha256"]
    record = _record()
    missing_provenance = _resequence(
        record,
        record.observations,
        manifest=missing_provenance_manifest,
    )
    with pytest.raises(ValueError, match="candidate_patch_sha256"):
        validate_corpus([missing_provenance], require_paired=True)

    mismatch_manifest = _manifest()
    mismatch_manifest.provenance["candidate_patch_sha256"] = "a" * 64
    mismatch = _resequence(record, record.observations, manifest=mismatch_manifest)
    with pytest.raises(ValueError, match="candidate_id does not match"):
        validate_corpus([mismatch], require_paired=True)

    events = list(_record().observations)
    events[0] = replace(events[0], artifact_locator="")
    missing_locator = replace(_record(), observations=tuple(events))
    with pytest.raises(ValueError, match="digest or locator is missing"):
        validate_corpus([missing_locator], require_paired=True)

    events = list(_record().observations)
    events[1] = replace(events[1], artifact_locator=events[0].artifact_locator)
    duplicate_locator = replace(_record(), observations=tuple(events))
    with pytest.raises(ValueError, match="locators are not unique"):
        validate_corpus([duplicate_locator], require_paired=True)

    with pytest.raises(ValueError, match="candidate_id must equal subject_candidate_id"):
        replace(
            record.observations[0],
            subject_candidate_id="sha256:" + "0" * 64,
        )

    with pytest.raises(ValueError, match="credential-free"):
        replace(_record(), candidate_artifact_locator="https://token@example.com/patch")


def test_event_identity_and_collection_times_are_bound() -> None:
    event = _event(EvidenceKind.STATIC)
    with pytest.raises(ValueError, match="must be distinct"):
        replace(event, event_id=event.observation.acquisition_id)
    with pytest.raises(ValueError, match="must be distinct"):
        replace(
            event,
            decision=replace(
                event.decision,
                decision_id=event.observation.acquisition_id,
            ),
        )

    missing_time = replace(event, collected_at="")
    record = replace(
        _record(),
        observations=(missing_time, *_record().observations[1:]),
    )
    with pytest.raises(ValueError, match="collection timestamp is missing"):
        validate_corpus([record], require_paired=True)

    with pytest.raises(ValueError, match="cannot precede candidate_generated_at"):
        replace(_record(), candidate_generated_at="2026-01-04T00:00:00Z")

    record = _record()
    events = list(record.observations)
    events[1] = replace(
        events[1],
        decision=replace(
            events[1].decision,
            decision_id=events[0].event_id,
        ),
    )
    with pytest.raises(ValueError, match="namespaces must be disjoint"):
        replace(record, observations=tuple(events))


@pytest.mark.parametrize("identity_namespace", ["event", "decision", "acquisition"])
def test_corpus_identity_namespaces_are_globally_disjoint(
    identity_namespace: str,
) -> None:
    first = _record()
    second = _record(
        instance_id="other__repo-1",
        candidate_id="sha256:" + "7" * 64,
        repository="other/repo",
    )
    first_event = first.observations[0]
    reused_identity = {
        "event": first_event.event_id,
        "decision": first_event.decision.decision_id,
        "acquisition": first_event.observation.acquisition_id,
    }[identity_namespace]
    second_events = list(second.observations)
    second_events[0] = replace(second_events[0], event_id=reused_identity)
    second = _resequence(second, tuple(second_events))

    with pytest.raises(ValueError, match="corpus identity .* is reused"):
        validate_corpus([first, second])


def test_live_trajectory_and_policy_action_identity_are_corpus_stable() -> None:
    first_record = _record()
    first_decision = _live_policy_decision(first_record.manifest)
    first_event = bridge_logged_policy_observation(
        event_id="evt-global-live-first",
        policy_decision=first_decision,
        observation=replace(
            first_record.observations[0].observation,
            acquisition_id=first_decision.acquisition_id or "",
        ),
        validity_adjudication=_validity_adjudication(),
        collected_at="2026-01-03T00:00:00Z",
    )
    first_record = replace(first_record, observations=(first_event,))

    second_record = _record(
        instance_id="other__repo-2",
        candidate_id="sha256:" + "8" * 64,
        repository="other/repo",
    )
    second_decision = _live_policy_decision(
        second_record.manifest,
        identity_index=9,
        trajectory_id="trajectory-corpus-bridge-second",
    )
    second_event = bridge_logged_policy_observation(
        event_id="evt-global-live-second",
        policy_decision=second_decision,
        observation=replace(
            second_record.observations[0].observation,
            acquisition_id=second_decision.acquisition_id or "",
        ),
        validity_adjudication=_validity_adjudication(),
        collected_at="2026-01-03T00:00:00Z",
    )
    second_record = replace(second_record, observations=(second_event,))

    reused_trajectory_decision = replace(
        second_decision,
        trajectory_id=first_decision.trajectory_id,
        decision_sha256="",
        trajectory_head_sha256="",
    )
    reused_trajectory_event = replace(
        second_event,
        decision=reused_trajectory_decision,
    )
    with pytest.raises(ValueError, match="trajectory_id .* crosses corpus records"):
        validate_corpus([
            first_record,
            replace(second_record, observations=(reused_trajectory_event,)),
        ])

    redefined_implementation = replace(
        second_decision,
        policy_code_config_sha256=hashlib.sha256(
            b"different fixture policy implementation"
        ).hexdigest(),
        decision_sha256="",
        trajectory_head_sha256="",
    )
    redefined_implementation_event = replace(
        second_event,
        decision=redefined_implementation,
    )
    with pytest.raises(ValueError, match="changes code/config identity"):
        validate_corpus([
            first_record,
            replace(
                second_record,
                observations=(redefined_implementation_event,),
            ),
        ])

    changed_catalog = tuple(
        replace(offer, adapter_id="adapter-semantic-redefined")
        if offer.action_id == "semantic-second-adapter"
        else offer
        for offer in second_decision.action_catalog
    )
    redefined_decision = replace(
        second_decision,
        action_catalog=changed_catalog,
        decision_sha256="",
        trajectory_head_sha256="",
    )
    redefined_event = replace(second_event, decision=redefined_decision)
    with pytest.raises(ValueError, match="changes intervention identity"):
        validate_corpus([
            first_record,
            replace(second_record, observations=(redefined_event,)),
        ])


def test_randomized_decision_logs_full_distribution_and_descriptive_support() -> None:
    record = _record()
    randomized = _resequence(
        record,
        record.observations,
        action_overrides={
            1: {EvidenceKind.SEMANTIC: 0.25, EvidenceKind.STATIC: 0.75},
        },
    )
    decision = randomized.observations[1].decision

    assert decision.history_event_ids == (
        randomized.observations[0].event_id,
    )
    assert decision.chosen_action == EvidenceKind.SEMANTIC
    assert decision.history_conditioned_propensity == 0.25
    assert [item.to_dict() for item in decision.available_actions] == [
        {"action": "semantic", "propensity": 0.25},
        {"action": "static", "propensity": 0.75},
    ]

    diagnostics = build_corpus_report([randomized])["propensity_diagnostics"]
    overall = diagnostics["overall"]
    assert overall["randomized_decisions"] == 1
    assert overall["minimum_chosen_propensity"] == 0.25
    assert overall["per_action"]["static"]["available_decisions"] == 2
    assert overall["per_action"]["static"]["chosen_decisions"] == 1
    assert diagnostics["by_collection_policy"][0]["randomized_decisions"] == 1


def test_action_distribution_requires_order_uniqueness_normalization_and_match() -> None:
    decision = _record().observations[0].decision
    semantic = ActionPropensity(EvidenceKind.SEMANTIC, 0.5)
    static = ActionPropensity(EvidenceKind.STATIC, 0.5)

    with pytest.raises(ValueError, match="ordered by action name"):
        replace(
            decision,
            available_actions=(static, semantic),
            chosen_action=EvidenceKind.STATIC,
            history_conditioned_propensity=0.5,
        )
    with pytest.raises(ValueError, match="duplicate actions"):
        replace(
            decision,
            available_actions=(semantic, semantic),
            chosen_action=EvidenceKind.SEMANTIC,
            history_conditioned_propensity=0.5,
        )
    with pytest.raises(ValueError, match="sum to 1"):
        replace(
            decision,
            available_actions=(
                ActionPropensity(EvidenceKind.SEMANTIC, 0.4),
                ActionPropensity(EvidenceKind.STATIC, 0.5),
            ),
            chosen_action=EvidenceKind.SEMANTIC,
            history_conditioned_propensity=0.4,
        )
    with pytest.raises(ValueError, match="must equal the chosen action propensity"):
        replace(
            decision,
            available_actions=(semantic, static),
            chosen_action=EvidenceKind.SEMANTIC,
            history_conditioned_propensity=0.25,
        )
    with pytest.raises(ValueError, match=r"finite and in \(0, 1\]"):
        ActionPropensity(EvidenceKind.SEMANTIC, 0.0)


def test_sequence_rejects_order_history_and_digest_tampering() -> None:
    record = _record()
    with pytest.raises(ValueError, match="unique, contiguous, and ordered"):
        replace(
            record,
            observations=(
                record.observations[1],
                record.observations[0],
                *record.observations[2:],
            ),
        )

    events = list(record.observations)
    events[2] = replace(
        events[2],
        decision=replace(
            events[2].decision,
            history_event_ids=(
                record.observations[0].event_id,
                "fabricated-prior-event",
            ),
        ),
    )
    with pytest.raises(ValueError, match="exact prior event prefix"):
        replace(record, observations=tuple(events))

    events = list(record.observations)
    events[1] = replace(
        events[1],
        decision=replace(events[1].decision, history_sha256="0" * 64),
    )
    with pytest.raises(ValueError, match="history_sha256 does not match"):
        replace(record, observations=tuple(events))

    events = list(record.observations)
    events[0] = replace(
        events[0],
        decision=replace(events[0].decision, router_state_sha256="0" * 64),
    )
    with pytest.raises(ValueError, match="router_state_sha256 does not match"):
        replace(record, observations=tuple(events))


def test_decisions_bind_candidate_and_collection_policy() -> None:
    record = _record()
    with pytest.raises(ValueError, match="candidate_id must equal subject_candidate_id"):
        replace(
            record.observations[0],
            decision=replace(
                record.observations[0].decision,
                candidate_id="sha256:" + "0" * 64,
            ),
        )

    events = list(record.observations)
    events[0] = replace(
        events[0],
        decision=replace(events[0].decision, collection_policy="different-policy"),
    )
    with pytest.raises(ValueError, match="contradicts the corpus record"):
        replace(record, observations=tuple(events))


def test_privileged_and_human_evidence_cannot_enter_history() -> None:
    record = _record()
    events = list(record.observations)
    events[0] = replace(
        events[0],
        observation=replace(
            events[0].observation,
            privileged_inputs=("gold_patch",),
        ),
    )
    with pytest.raises(ValueError, match="privileged evidence cannot enter"):
        replace(record, observations=tuple(events))

    with pytest.raises(ValueError, match="human adjudication cannot enter"):
        build_acquisition_decision(
            decision_id="after-human",
            manifest=record.manifest,
            collection_policy=record.collection_policy,
            collection_policy_version=record.collection_policy_version,
            prior_observations=(record.observations[-1],),
            available_actions={EvidenceKind.STATIC: 1.0},
            chosen_action=EvidenceKind.STATIC,
            selection_reason="invalid_post_truth_decision",
        )


def test_unstructured_metadata_is_audited_but_excluded_from_router_history() -> None:
    record = _record()
    events = list(record.observations)
    original_history_digest = events[1].decision.history_sha256
    original_trajectory_digest = record.acquisition_trajectory_digest()
    events[0] = replace(
        events[0],
        observation=replace(
            events[0].observation,
            metadata={
                "artifact_sha256": "f" * 64,
                "runner": "bench-cleanser-acquire",
            },
        ),
    )

    with_metadata = replace(record, observations=tuple(events))

    assert with_metadata.observations[1].decision.history_sha256 == original_history_digest
    assert with_metadata.acquisition_trajectory_digest() != original_trajectory_digest


def test_curator_labels_are_excluded_from_declared_router_history() -> None:
    record = _record()
    events = list(record.observations)
    original_history_digest = events[1].decision.history_sha256
    original_trajectory_digest = record.acquisition_trajectory_digest()
    events[0] = replace(
        events[0],
        validity_adjudication=_validity_adjudication(EvidenceValidity.INVALID),
    )

    relabeled = replace(record, observations=tuple(events))

    assert relabeled.observations[1].decision.history_sha256 == original_history_digest
    assert relabeled.acquisition_trajectory_digest() == original_trajectory_digest
    assert relabeled.canonical_digest() != record.canonical_digest()

    artifact_changed = list(record.observations)
    artifact_changed[0] = replace(
        artifact_changed[0],
        artifact_locator="artifact://fixture/static/recollected",
    )
    changed = replace(record, observations=tuple(artifact_changed))
    assert changed.acquisition_trajectory_digest() != original_trajectory_digest


def test_collection_times_follow_decision_order() -> None:
    record = _record()
    events = list(record.observations)
    events[1] = replace(events[1], collected_at="2026-01-02T23:59:59Z")
    with pytest.raises(ValueError, match="timestamps must follow decision_step order"):
        replace(record, observations=tuple(events))


def test_blank_required_provenance_is_rejected_before_claiming_completeness() -> None:
    manifest = _manifest()
    manifest.provenance["dataset_revision"] = " "

    with pytest.raises(ValueError, match="non-empty string"):
        replace(_record(), manifest=manifest)


def test_human_event_must_match_privileged_candidate_truth() -> None:
    record = _record()
    events = list(record.observations)
    events[-1] = replace(
        events[-1],
        observation=replace(
            events[-1].observation,
            status=EvidenceStatus.SUPPORTS_INCORRECT,
        ),
    )
    contradictory = replace(record, observations=tuple(events))

    with pytest.raises(ValueError, match="contradicts authoritative truth"):
        validate_corpus([contradictory], require_paired=True)


def test_strict_pairing_requires_meaningful_adjudicator_agreement() -> None:
    weak_agreement = replace(
        _record(),
        candidate_adjudication=replace(
            _record().candidate_adjudication,
            agreement=MIN_ADJUDICATOR_AGREEMENT - 0.01,
        ),
    )
    with pytest.raises(ValueError, match="below the schema threshold"):
        validate_corpus([weak_agreement], require_paired=True)


def test_lifecycle_stage_cannot_bypass_candidate_duplicate_detection() -> None:
    record = _record()
    second_manifest = ValidityManifest.from_dict(record.manifest.to_dict())
    second_manifest.lifecycle_stage = LifecycleStage.EVALUATION
    second = _resequence(record, record.observations, manifest=second_manifest)

    with pytest.raises(ValueError, match="duplicate instance/candidate"):
        validate_corpus([record, second])


def test_failed_evidence_cannot_be_labeled_valid() -> None:
    with pytest.raises(ValueError, match="cannot have a valid label"):
        _event(
            EvidenceKind.FULL_EXECUTION,
            status=EvidenceStatus.ERROR,
            validity=EvidenceValidity.VALID,
        )


def test_corpus_cli_writes_a_strict_machine_readable_report(tmp_path) -> None:
    corpus_path = tmp_path / "corpus.jsonl"
    output_path = tmp_path / "report.json"
    corpus_path.write_text(json.dumps(_record().to_dict()) + "\n", encoding="utf-8")

    main([str(corpus_path), "--require-paired", "--output", str(output_path)])

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["paired_complete_records"] == 1
    assert report["schema_version"] == CORPUS_SCHEMA_VERSION


def test_corpus_canonical_digest_rejects_nonstandard_nan() -> None:
    with pytest.raises(ValueError, match="notes must be a string"):
        replace(_record().candidate_adjudication, notes=float("nan"))


def test_corpus_cli_reports_output_write_failure_cleanly(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(json.dumps(_record().to_dict()) + "\n", encoding="utf-8")

    def fail_write(path, content) -> None:
        raise OSError("fixture output failure")

    monkeypatch.setattr(verification_corpus, "atomic_write", fail_write)
    with pytest.raises(
        SystemExit,
        match="verification corpus validation failed: fixture output failure",
    ):
        verification_corpus.main([
            str(corpus_path),
            "--output",
            str(tmp_path / "report.json"),
        ])
