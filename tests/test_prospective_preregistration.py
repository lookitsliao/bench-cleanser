"""Contracts for the prospective independent-evidence pilot protocol."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from bench_cleanser.verification.policy_log import (
    CANONICAL_SAMPLER_ID,
    CANONICAL_SAMPLER_VERSION,
)
from experiments.prospective_pilot.proposal_policy import (
    PROPOSAL_POLICY_CONFIG_SHA256,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "experiments" / "prospective_pilot" / "preregistration.json"
PROSE_PATH = ROOT / "experiments" / "prospective_pilot" / "PREREGISTRATION.md"
PREHISTORY_PATH = ROOT / "experiments" / "prospective_pilot" / "prehistory.json"
VALIDATOR_PATH = ROOT / "experiments" / "prospective_pilot" / "validate_protocol.py"
SPHINX_MANIFEST_PATH = ROOT / "experiments" / "sphinx_execution_smoke" / "evidence-manifest.json"
INDEPENDENT_MANIFEST_PATH = (
    ROOT / "experiments" / "independent_execution_smoke" / "evidence-manifest.json"
)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "prospective_protocol_validator",
    VALIDATOR_PATH,
)
assert VALIDATOR_SPEC is not None and VALIDATOR_SPEC.loader is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
sys.modules[VALIDATOR_SPEC.name] = validator
VALIDATOR_SPEC.loader.exec_module(validator)


def _protocol() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(PROTOCOL_PATH.read_text(encoding="utf-8")),
    )


def _copy_protocol_tree(tmp_path: Path) -> Path:
    relative_paths = {
        validator.EVIDENCE_RELATIVE,
        validator.SPHINX_EVIDENCE_RELATIVE,
        *validator.FREEZE_OBJECT_PATHS.values(),
    }
    for relative in sorted(relative_paths, key=lambda value: value.as_posix()):
        source = ROOT.joinpath(*relative.parts)
        target = tmp_path.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path


def test_protocol_is_explicitly_post_feasibility_and_not_confirmatory() -> None:
    protocol = _protocol()

    assert protocol["schema_version"] == "prospective-evidence-routing-protocol-0.3.0"
    assert protocol["status"] == "draft_post_feasibility_execution_not_registered"
    scope = protocol["claim_scope"]
    assert isinstance(scope, dict)
    assert scope["confirmatory"] is False
    assert scope["measurement_design"] == validator.MEASUREMENT_DESIGN
    assert scope["hypotheses_supported"] == []
    assert "evidence for hypotheses H1 through H6" in scope["cannot_support"]
    knowledge = protocol["knowledge_boundary"]
    assert isinstance(knowledge, dict)
    assert knowledge["existing_hosted_outcomes_known_to_developers"] is True
    assert knowledge["outcome_naive"] is False
    assert knowledge["hosted_outcomes_allowed_in_live_policy_state"] is False
    assert knowledge["hosted_outcomes_allowed_in_new_adjudication"] is False
    assert knowledge["independent_execution_outcomes_known_to_developers"] is True
    assert knowledge["pre_freeze_feasibility_task_ids"] == [
        "sympy__sympy-15976",
        "sphinx-doc__sphinx-8475",
    ]
    assert knowledge["pre_freeze_evidence_allowed_in_prospective_or_ope_estimands"] is False
    assert knowledge["protocol_committed_before_pre_freeze_execution"] is False


def test_protocol_binds_the_complete_matched_cohort_without_outcome_values() -> None:
    protocol = _protocol()
    frozen = protocol["frozen_inputs"]
    assert isinstance(frozen, dict)
    assert frozen["task_count"] == 24
    assert frozen["candidates_per_task"] == 3
    assert frozen["candidate_count"] == 72
    for field in (
        "acquisition_manifest_sha256",
        "cohort_identity_sha256",
        "selected_task_identities_sha256",
        "matched_study_code_sha256",
    ):
        value = frozen[field]
        assert isinstance(value, str)
        assert len(value) == 64
        int(value, 16)

    raw = PROTOCOL_PATH.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "hosted_resolved_count",
        "selected_hosted_resolved",
        "gpt-5",
        "kimi k2",
        "claude 4 sonnet",
    ):
        assert forbidden not in raw


def test_behavior_policy_has_declared_positive_support() -> None:
    protocol = _protocol()
    behavior = protocol["behavior_policy"]
    assert isinstance(behavior, dict)
    exploration = behavior["exploration_mass"]
    action_count = behavior["maximum_available_actions"]
    minimum = behavior["minimum_history_conditioned_propensity"]
    assert isinstance(exploration, float)
    assert isinstance(action_count, int)
    assert isinstance(minimum, float)
    assert action_count == 7
    assert exploration / action_count == minimum
    assert behavior["write_ahead_required"] is True
    assert behavior["full_action_catalog_required"] is True
    assert behavior["disclosed_action_count"] == 9
    assert behavior["positive_support_required"] is True
    sampler = behavior["sampler"]
    assert isinstance(sampler, dict)
    assert sampler == {
        "id": CANONICAL_SAMPLER_ID,
        "version": CANONICAL_SAMPLER_VERSION,
        "implementation": ("bench_cleanser.verification.policy_log.sample_behavior_action"),
    }

    actions = protocol["evidence_actions"]
    assert isinstance(actions, dict)
    randomized = actions["randomized_catalog"]
    assert isinstance(randomized, list)
    assert len(randomized) == action_count
    assert {"accept", "reject", "abstain"}.issubset(randomized)
    assert actions["disclosed_nonpolicy_action_ids"] == [
        "hardening_curator",
        "static_bootstrap",
    ]

    go_no_go = protocol["go_no_go"]
    assert isinstance(go_no_go, dict)
    requirements = go_no_go["requirements"]
    assert isinstance(requirements, dict)
    assert requirements["minimum_observed_propensity"] == minimum


def test_power_limit_is_exact_and_prevents_a_low_risk_claim() -> None:
    protocol = _protocol()
    power = protocol["stopping_and_power"]
    assert isinstance(power, dict)
    bound = 1.0 - math.pow(0.05, 1.0 / 24.0)
    future_bound = 1.0 - math.pow(0.05, 1.0 / 22.0)
    assert power["zero_error_one_sided_95_upper_bound_at_24"] == bound
    assert power["zero_error_one_sided_95_upper_bound_at_22"] == future_bound
    assert power["zero_error_bound_interpretation"] == validator.BOUND_INTERPRETATION
    assert power["remaining_future_task_count"] == 22
    assert power["minimum_accepts_for_zero_error_95_upper_bound_below_0_02"] == 149
    assert power["minimum_accepts_for_zero_error_95_upper_bound_below_0_01"] == 299
    estimand = protocol["primary_estimand"]
    assert isinstance(estimand, dict)
    assert estimand["target_is_certifiable_at_n_24"] is False
    assert bound > estimand["pilot_target"]


def test_protocol_requires_independent_truth_cost_and_deviation_artifacts() -> None:
    protocol = _protocol()
    execution = protocol["execution_protocol"]
    adjudication = protocol["adjudication_protocol"]
    costs = protocol["cost_ledger"]
    deviations = protocol["deviation_policy"]
    assert isinstance(execution, dict)
    assert isinstance(adjudication, dict)
    assert isinstance(costs, dict)
    assert isinstance(deviations, dict)
    assert execution["replicates"] == 2
    assert execution["disagreement_replicate"] == 3
    assert execution["network_during_tests"] is False
    assert adjudication["reviewers"] == 3
    assert adjudication["execution_is_adjudication"] is False
    assert adjudication["minimum_paired_ready_agreement"] == 0.8
    assert "human_minutes" in costs["required_extended_fields"]
    assert deviations["silent_changes_forbidden"] is True
    assert deviations["material_change_requires_new_protocol_version"] is True


def test_prose_and_json_share_the_safety_critical_contract() -> None:
    text = PROSE_PATH.read_text(encoding="utf-8")
    protocol_digest = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
    assert "not\nexternally registered and not confirmatory" in text
    assert "post-draft,\npre-freeze feasibility evidence" in text
    assert "22 future task clusters" in text
    assert "72 candidates" in text and "66 candidates" in text
    assert "12.73%" in text and "11.73%" in text
    assert "propensity at least `1/14`" in text
    assert "Execution is evidence, not adjudication" in text
    assert "outcome-exposed development cohort, not prospective policy validation" in text
    assert "not cluster-valid inference under adaptive acceptance" in text
    assert "cannot supply evidence for H1-H6" in text
    assert "149" in text and "299" in text
    assert len(protocol_digest) == 64


def test_chained_prehistory_is_present_bound_and_draft_is_not_activatable() -> None:
    result = validator.validate_protocol(ROOT)

    assert PREHISTORY_PATH.is_file()
    assert result.prehistory_event_count == 2
    prehistory = json.loads(PREHISTORY_PATH.read_text(encoding="utf-8"))
    assert result.prehistory_chain_head_sha256 == prehistory["chain_head_sha256"]
    sphinx_manifest = json.loads(SPHINX_MANIFEST_PATH.read_text(encoding="utf-8"))
    sphinx_bundle = sphinx_manifest["evidence_bundle"]
    sphinx_event = prehistory["events"][1]
    assert sphinx_event["task_id"] == "sphinx-doc__sphinx-8475"
    assert sphinx_event["acquisition_window"] == {
        "first_started_at": "2026-07-13T13:45:11.324927Z",
        "last_finished_at": "2026-07-13T13:46:34.783239Z",
        "receipt": "raw_execution_artifact_timestamps_not_authenticated_protocol_time",
    }
    sphinx_record = sphinx_event["evidence_record"]
    assert sphinx_record["external_bundle_bytes"] == sphinx_bundle["bytes"]
    assert sphinx_record["external_bundle_sha256"] == sphinx_bundle["sha256"]
    assert sphinx_record["external_bundle_index"]["sha256"] == sphinx_bundle["index"]["sha256"]
    assert (
        sphinx_record["external_bundle_environment"]["sha256"]
        == sphinx_manifest["runtime"]["environment_record"]["sha256"]
    )
    assert sphinx_record["external_bundle_runner"]["sha256"] == sphinx_bundle["runner"]["sha256"]
    assert result.activation_ready is False
    assert set(result.blockers) == {
        *validator.REQUIRED_ACTIVATION_BLOCKERS,
        validator.FREEZE_RECEIPT_BLOCKER,
    }
    assert set(result.configuration_sha256) == set(validator.CONFIG_PATHS)

    protocol = _protocol()
    binding = protocol["prehistory"]
    assert isinstance(binding, dict)
    prehistory_bytes = PREHISTORY_PATH.read_bytes()
    assert binding["bytes"] == len(prehistory_bytes)
    assert binding["sha256"] == hashlib.sha256(prehistory_bytes).hexdigest()


def test_prehistory_tampering_and_missing_authority_fail_closed(tmp_path: Path) -> None:
    root = _copy_protocol_tree(tmp_path)
    prehistory_path = root.joinpath(*validator.PREHISTORY_RELATIVE.parts)
    prehistory = json.loads(prehistory_path.read_text(encoding="utf-8"))
    prehistory["events"][0]["knowledge_boundary"]["hosted_labels_accessible_before_execution"] = (
        False
    )
    prehistory_path.write_text(json.dumps(prehistory), encoding="utf-8")
    with pytest.raises(validator.ProtocolError, match="event_sha256"):
        validator.validate_protocol(root)

    root = _copy_protocol_tree(tmp_path / "missing")
    root.joinpath(*validator.PREHISTORY_RELATIVE.parts).unlink()
    with pytest.raises(validator.ProtocolError, match="prehistory.json"):
        validator.validate_protocol(root)


def test_claim_boundary_deletion_and_activation_attempt_fail_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _copy_protocol_tree(tmp_path)
    protocol_path = root.joinpath(*validator.PROTOCOL_RELATIVE.parts)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["claim_scope"]["hypotheses_supported"] = ["H1"]
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(validator.ProtocolError, match="no H1-H6"):
        validator.validate_protocol(root)

    assert validator.main(["--root", str(ROOT), "--require-activation-ready"]) == 2
    assert "not activation-ready" in capsys.readouterr().err


def test_activation_configs_are_exact_and_keep_real_unknowns_blocking() -> None:
    resource = json.loads(
        (ROOT / "experiments/prospective_pilot/resource_ceiling.json").read_text()
    )
    policy = json.loads((ROOT / "experiments/prospective_pilot/collection_policy.json").read_text())
    scheduler = json.loads(
        (ROOT / "experiments/prospective_pilot/scheduler_contract.json").read_text()
    )
    frame = json.loads((ROOT / "experiments/prospective_pilot/frame_manifest.json").read_text())
    execution = json.loads(
        (ROOT / "experiments/prospective_pilot/execution_freeze.json").read_text()
    )
    adjudication = json.loads(
        (ROOT / "experiments/prospective_pilot/adjudication_plan.json").read_text()
    )
    analysis = json.loads((ROOT / "experiments/prospective_pilot/analysis_plan.json").read_text())

    assert resource["status"] == ("specified_numeric_ceiling_pending_clean_commit_freeze")
    assert resource["decision_limits"]["maximum_total_acquisition_events"] == 732
    assert resource["compute_limits"]["maximum_concurrent_workers"] == 4
    assert resource["enforcement"]["outcome_dependent_extension_allowed"] is False
    assert policy["rng"]["action_draws"]["seed_sha256"]
    assert policy["semantic_producer"]["availability"] == "unavailable"
    assert policy["semantic_producer"]["blocking"] is True
    catalog = policy["behavior_policy"]["action_catalog"]
    assert len(catalog) == 9
    assert policy["behavior_policy"]["disclosed_action_count"] == 9
    assert policy["behavior_policy"]["maximum_available_actions"] == 7
    assert [item["action_id"] for item in catalog] == sorted(item["action_id"] for item in catalog)
    assert [item["action_id"] for item in catalog if item["evidence_kind"] == "full_execution"] == [
        "full_primary",
        "full_repeat",
    ]
    assert all(
        item["evidence_kind"] is None
        for item in catalog
        if item["route_action"] in {"accept", "reject", "abstain"}
    )
    assert {
        item["action_id"]: (item["evidence_kind"], item["route_action"])
        for item in catalog
        if item["action_id"] in {"hardening_curator", "static_bootstrap"}
    } == {
        "hardening_curator": ("oracle_hardening", "harden_oracle"),
        "static_bootstrap": ("static", "run_static"),
    }
    scheduler_source = ROOT / "experiments/prospective_pilot/scheduler.py"
    proposal_source = ROOT / "experiments/prospective_pilot/proposal_policy.py"
    ledger_source = ROOT / "experiments/prospective_pilot/ledger.py"
    scientific_ledger_source = ROOT / "experiments/prospective_pilot/scientific_ledger.py"
    corpus_source = ROOT / "bench_cleanser/verification/corpus.py"
    evaluation_source = ROOT / "bench_cleanser/verification/evaluate.py"
    metrics_source = ROOT / "bench_cleanser/verification/metrics.py"
    dispatcher_source = ROOT / "experiments/prospective_pilot/dispatcher.py"
    release_bundle_source = ROOT / "experiments/prospective_pilot/release_bundle.py"
    orchestrator_source = ROOT / "bench_cleanser/verification/orchestrate.py"
    assert scheduler["schema_version"] == "prospective-pilot-scheduler-contract-0.6.0"
    assert scheduler["status"] == (
        "scheduler_bootstrap_proposal_ledger_dispatcher_scientific_export_audit_"
        "and_split_corpus_evaluation_contracts_implemented_operationally_blocked"
    )
    assert (
        scheduler["candidate_chain"]["nonterminal_acquisition_id_preallocated_in_policy_decision"]
        is True
    )
    assert scheduler["policy_log_crosswalk"]["embedded_record"] == (
        "scheduled_decisions[].logged_policy_decision"
    )
    assert scheduler["implementation"] == {
        "blocking": True,
        "scheduler": {
            "logical_path": "experiments/prospective_pilot/scheduler.py",
            "sha256": hashlib.sha256(scheduler_source.read_bytes()).hexdigest(),
        },
        "proposal_policy": {
            "config_sha256": PROPOSAL_POLICY_CONFIG_SHA256,
            "logical_path": "experiments/prospective_pilot/proposal_policy.py",
            "schema_version": "prospective-pilot-terminal-proposal-0.1.0",
            "sha256": hashlib.sha256(proposal_source.read_bytes()).hexdigest(),
            "version": "verification-gap-proposal-v1",
        },
        "ledger": {
            "logical_path": "experiments/prospective_pilot/ledger.py",
            "schema_version": "prospective-pilot-ledger-0.1.0",
            "scope": "single_host_local_durable_filesystem",
            "sha256": hashlib.sha256(ledger_source.read_bytes()).hexdigest(),
        },
        "scientific_ledger": {
            "logical_path": "experiments/prospective_pilot/scientific_ledger.py",
            "profile": "SIGNED_BOOTSTRAP_CURATOR_RESOURCE_EXPORT_AUDIT_CORE",
            "schema_version": "prospective-pilot-scientific-ledger-0.2.0",
            "scope": "single_host_local_sqlite_digest_pinned_export_unanchored",
            "sha256": hashlib.sha256(scientific_ledger_source.read_bytes()).hexdigest(),
        },
        "corpus_contract": {
            "logical_path": "bench_cleanser/verification/corpus.py",
            "profile": "DETERMINISTIC_LABEL_EVIDENCE_PLUS_SEPARATE_RANDOMIZED_BEHAVIOR",
            "schema_version": "0.6.0",
            "sha256": hashlib.sha256(corpus_source.read_bytes()).hexdigest(),
        },
        "evaluation_contract": {
            "logical_path": "bench_cleanser/verification/evaluate.py",
            "profile": "TARGET_POLICY_JOINED_TO_DISTINCT_BEHAVIOR_LOGGER",
            "schema_version": "0.5.0",
            "sha256": hashlib.sha256(evaluation_source.read_bytes()).hexdigest(),
        },
        "metrics_source": {
            "logical_path": "bench_cleanser/verification/metrics.py",
            "sha256": hashlib.sha256(metrics_source.read_bytes()).hexdigest(),
        },
        "dispatcher": {
            "logical_path": "experiments/prospective_pilot/dispatcher.py",
            "sha256": hashlib.sha256(dispatcher_source.read_bytes()).hexdigest(),
        },
        "structural_release_bundle_compiler": {
            "logical_path": "experiments/prospective_pilot/release_bundle.py",
            "profile": "STRUCTURAL",
            "schema_version": "verification-gap-study-bundle-0.2.0",
            "sha256": hashlib.sha256(release_bundle_source.read_bytes()).hexdigest(),
            "trust_model": "out_of_band_sha256_v1",
        },
        "completed_acquisition_validator": {
            "entrypoint": "validate_completed_route_acquisition",
            "logical_path": "bench_cleanser/verification/orchestrate.py",
            "sha256": hashlib.sha256(orchestrator_source.read_bytes()).hexdigest(),
        },
        "status": (
            "scheduler_bootstrap_proposal_ledger_dispatcher_structural_bundle_"
            "scientific_export_audit_and_split_corpus_evaluation_contracts_"
            "available_external_scientific_activation_inputs_missing"
        ),
    }
    assert frame["task_count"] == 22
    assert frame["candidate_count"] == 66
    assert len(frame["tasks"]) == 22
    assert len({candidate for task in frame["tasks"] for candidate in task["candidate_ids"]}) == 66
    assert scheduler["operational_requirements"] == {
        "aggregate_resource_and_partial_frame_runtime": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "signed_resource_reservation_and_settlement_core_preserves_overruns_"
                "and_reports_local_committed_usage_bootstrap_coverage_deviations_and_"
                "halt_state_but_no_populated_records_activation_calendar_acquisition_"
                "cost_join_or_trusted_partial_frame_compiler_exists"
            ),
        },
        "bootstrap_and_terminal_proposal_policy": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "typed_bootstrap_prefix_terminal_proposals_and_signed_bootstrap_"
                "receipt_core_are_source_bound_but_no_populated_receipts_frozen_"
                "signer_profiles_behavior_genesis_join_or_external_checkpoint_"
                "exists"
            ),
        },
        "durable_exclusive_counter_and_head_ledger": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "claim_gated_single_host_dispatch_core_exists_but_no_validated_"
                "activation_context_or_populated_action_registry_exists"
            ),
        },
        "nonpolicy_evidence_and_truth_ledgers": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "signed_bootstrap_curator_and_resource_record_core_plus_digest_pinned_"
                "semantic_export_reaudit_exists_but_no_human_adjudication_records_"
                "populated_stream_frozen_production_roles_external_checkpoint_or_"
                "cross_ledger_join_exists"
            ),
        },
        "trusted_study_bundle_compiler": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "behavior_and_label_trajectories_are_separated_and_the_scientific_"
                "export_is_digest_pinned_and_semantically_reauditable_but_the_"
                "structural_compiler_does_not_join_the_unpopulated_scientific_ledger_"
                "or_authenticate_scientific_inputs"
            ),
        },
        "typed_acquisition_persistence": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "strict_spec_and_result_core_exists_but_provisioner_and_retention_"
                "identities_are_declarative_and_no_external_immutable_store_exists"
            ),
        },
    }
    independent_manifest = json.loads(INDEPENDENT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert execution["harness"]["commit"] == independent_manifest["harness"]["commit"]
    assert execution["platform"]["architecture"] == {
        "blocking": True,
        "status": "unavailable",
        "value": None,
    }
    assert all(
        binding["status"] == "unavailable" and binding["blocking"] is True
        for binding in execution["unavailable_bindings"].values()
    )
    assert all(
        reviewer["identifier"] is None
        for reviewer in adjudication["unavailable_bindings"]["reviewers"]
    )
    review_source = ROOT / "experiments/prospective_pilot/review_packets.py"
    assert adjudication["packet_contract"]["packet_manifest_schema_version"] == (
        "prospective-pilot-review-packet-manifest-0.2.0"
    )
    assert adjudication["packet_contract"]["directional_evidence_status_omitted"] is True
    assert adjudication["available_bindings"]["packet_generator"] == {
        "bytes": len(review_source.read_bytes()),
        "logical_path": "experiments/prospective_pilot/review_packets.py",
        "sha256": hashlib.sha256(review_source.read_bytes()).hexdigest(),
        "status": "available",
    }
    assert adjudication["aggregation"]["disagreement"] == (
        "retain_every_initial_label_and_emit_indeterminate_without_tie_breaking"
    )
    assert analysis["analysis_population"]["cluster_unit"] == "task"
    assert analysis["off_policy_evaluation"]["support_unit"] == (
        "complete_task_cluster_history_across_all_three_candidate_chains"
    )
    assert analysis["implemented_estimators"]["doubly_robust"] == {
        "availability": "not_implemented_not_claimed",
        "nuisance_model": None,
        "cross_fitting": None,
    }
    for name in ("analysis_implementation", "target_policy_implementation_manifest"):
        assert analysis["available_bindings"][name]["status"] == "available"
    validation = validator.validate_protocol(ROOT)
    assert validation.activation_ready is False
    assert "durable exclusive scheduler ledger and write-ahead dispatcher" in (validation.blockers)
    assert "typed acquisition-result persistence and action-spec preimages" in (validation.blockers)
    assert "signed deterministic bootstrap receipt acquisition" in (validation.blockers)
    assert "durable bootstrap curator adjudication substrate and resource ledgers" in (
        validation.blockers
    )
    assert "trusted ledger-to-corpus terminal-outcome and cost compiler" in (validation.blockers)
    assert "aggregate resource reservation settlement and partial-frame reporting" in (
        validation.blockers
    )
    assert "review-packet generator identity" not in validation.blockers
    assert "analysis implementation identity" not in validation.blockers
    assert "target-policy implementation manifest" not in validation.blockers


@pytest.mark.parametrize(
    ("relative", "mutation", "message"),
    [
        (
            validator.RESOURCE_RELATIVE,
            lambda value: value["enforcement"].update(outcome_dependent_extension_allowed=True),
            "enforcement",
        ),
        (
            validator.POLICY_RELATIVE,
            lambda value: value["semantic_producer"].update(model="fabricated-model"),
            "partial identity",
        ),
        (
            validator.POLICY_RELATIVE,
            lambda value: value["rng"]["action_draws"].update(domain="different-domain"),
            "literal binding differs",
        ),
        (
            validator.POLICY_RELATIVE,
            lambda value: value["preferred_action_rule"]["router"].update(
                policy_config_sha256="a" * 64
            ),
            "source binding differs",
        ),
        (
            validator.SCHEDULER_RELATIVE,
            lambda value: value["implementation"]["scheduler"].update(
                logical_path="experiments/prospective_pilot/fake.py"
            ),
            "source bindings differ",
        ),
        (
            validator.SCHEDULER_RELATIVE,
            lambda value: value["implementation"]["ledger"].update(sha256="a" * 64),
            "source bindings differ",
        ),
        (
            validator.SCHEDULER_RELATIVE,
            lambda value: value["implementation"]["dispatcher"].update(sha256="a" * 64),
            "source bindings differ",
        ),
        (
            validator.SCHEDULER_RELATIVE,
            lambda value: value["implementation"]["structural_release_bundle_compiler"].update(
                sha256="a" * 64
            ),
            "source bindings differ",
        ),
        (
            validator.SCHEDULER_RELATIVE,
            lambda value: value["logical_order"].update(candidate_order="garbage"),
            "logical-order contract differs",
        ),
        (
            validator.SCHEDULER_RELATIVE,
            lambda value: value["joint_propensity"].update(computation="garbage"),
            "joint-propensity contract",
        ),
        (
            validator.FRAME_RELATIVE,
            lambda value: value["tasks"][0]["candidate_ids"].__setitem__(0, "sha256:" + "f" * 64),
            "frame-manifest binding differs",
        ),
        (
            validator.EXECUTION_RELATIVE,
            lambda value: value["unavailable_bindings"]["per_task_image_digest_manifest"].update(
                sha256="a" * 64
            ),
            "partial identity",
        ),
        (
            validator.ADJUDICATION_RELATIVE,
            lambda value: value["unavailable_bindings"]["reviewers"][0].update(
                identifier="invented-reviewer"
            ),
            "explicitly unavailable",
        ),
        (
            validator.ADJUDICATION_RELATIVE,
            lambda value: value["packet_contract"].update(
                directional_evidence_status_omitted=False
            ),
            "packet identity/binding differs",
        ),
        (
            validator.ADJUDICATION_RELATIVE,
            lambda value: value["available_bindings"]["packet_generator"].update(sha256="a" * 64),
            "available packet_generator binding differs",
        ),
        (
            validator.ANALYSIS_RELATIVE,
            lambda value: value["analysis_population"].update(cluster_unit="candidate"),
            "cluster-respecting",
        ),
        (
            validator.ANALYSIS_RELATIVE,
            lambda value: value["implemented_estimators"]["doubly_robust"].update(
                availability="implemented"
            ),
            "implemented-estimator boundary differs",
        ),
        (
            validator.ANALYSIS_RELATIVE,
            lambda value: value["available_bindings"]["analysis_implementation"].update(
                logical_path="experiments/prospective_pilot/fake-analysis.py"
            ),
            "available analysis_implementation binding differs",
        ),
    ],
)
def test_activation_config_tampering_fails_closed(
    tmp_path: Path,
    relative: object,
    mutation: object,
    message: str,
) -> None:
    root = _copy_protocol_tree(tmp_path)
    assert hasattr(relative, "parts")
    path = root.joinpath(*relative.parts)
    value = json.loads(path.read_text())
    assert callable(mutation)
    mutation(value)
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(validator.ProtocolError, match=message):
        validator.validate_protocol(root)


def test_refreshed_frame_bindings_cannot_legitimize_mapping_substitution(
    tmp_path: Path,
) -> None:
    root = _copy_protocol_tree(tmp_path)
    frame_path = root.joinpath(*validator.FRAME_RELATIVE.parts)
    frame = json.loads(frame_path.read_text())
    frame["tasks"][0]["candidate_ids"][0] = "sha256:" + "0" * 64
    frame_path.write_text(json.dumps(frame), encoding="utf-8")
    frame_sha256 = hashlib.sha256(frame_path.read_bytes()).hexdigest()

    policy_path = root.joinpath(*validator.POLICY_RELATIVE.parts)
    policy = json.loads(policy_path.read_text())
    policy["implementation_bindings"]["frame_manifest"]["sha256"] = frame_sha256
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    scheduler_path = root.joinpath(*validator.SCHEDULER_RELATIVE.parts)
    scheduler = json.loads(scheduler_path.read_text())
    scheduler["frame_manifest"]["sha256"] = frame_sha256
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")

    with pytest.raises(
        validator.ProtocolError,
        match=(
            "adjudication available frame_manifest binding differs|"
            "task_ids_sha256|candidate_ids_sha256|tasks_sha256"
        ),
    ):
        validator.validate_protocol(root)


def _init_clean_protocol_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "protocol@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Protocol Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "freeze fixture"], cwd=root, check=True)


def test_freeze_receipt_cli_binds_clean_commit_tree_and_rejects_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _copy_protocol_tree(tmp_path / "repo")
    _init_clean_protocol_repo(root)
    receipt_path = tmp_path / "freeze-receipt.json"

    assert (
        validator.main(
            [
                "--root",
                str(root),
                "--write-freeze-receipt",
                str(receipt_path),
            ]
        )
        == 0
    )
    written = json.loads(receipt_path.read_text())
    assert set(written["source"]) == {"commit", "tree"}
    assert set(item["role"] for item in written["objects"]) == set(validator.FREEZE_OBJECT_PATHS)
    assert all(item["git_blob_oid"] for item in written["objects"])
    output = json.loads(capsys.readouterr().out)
    assert output["activation_ready"] is False
    assert validator.FREEZE_RECEIPT_BLOCKER not in output["blockers"]
    assert set(output["blockers"]) == validator.REQUIRED_ACTIVATION_BLOCKERS

    with pytest.raises(validator.ProtocolError, match="overwrite is forbidden"):
        validator.write_freeze_receipt(root, receipt_path)
    assert (
        validator.main(
            [
                "--root",
                str(root),
                "--check-freeze-receipt",
                str(receipt_path),
            ]
        )
        == 0
    )
    checked = json.loads(capsys.readouterr().out)
    assert checked["checked_freeze_receipt"] is True
    assert checked["activation_ready"] is False

    tampered_receipt = tmp_path / "tampered-freeze-receipt.json"
    tampered = json.loads(receipt_path.read_text())
    tampered["source"]["tree"] = "0" * 40
    tampered_receipt.write_text(
        validator.strict_json_dumps(tampered) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(validator.ProtocolError, match="commit/tree differs"):
        validator.validate_protocol(root, freeze_receipt=tampered_receipt)

    resource_path = root.joinpath(*validator.RESOURCE_RELATIVE.parts)
    resource_path.write_text(resource_path.read_text() + "\n")
    with pytest.raises(
        validator.ProtocolError,
        match="activation configuration binding differs|clean Git worktree",
    ):
        validator.validate_protocol(root, freeze_receipt=receipt_path)


def test_freeze_receipt_generation_refuses_repository_output_and_dirty_source(
    tmp_path: Path,
) -> None:
    root = _copy_protocol_tree(tmp_path / "repo")
    _init_clean_protocol_repo(root)
    with pytest.raises(validator.ProtocolError, match="outside"):
        validator.write_freeze_receipt(root, root / "receipt.json")

    protocol_path = root.joinpath(*validator.PROTOCOL_RELATIVE.parts)
    protocol_path.write_text(protocol_path.read_text() + "\n")
    with pytest.raises(validator.ProtocolError, match="clean Git worktree"):
        validator.write_freeze_receipt(root, tmp_path / "dirty-receipt.json")
