#!/usr/bin/env python3
"""Validate prospective-pilot chronology and fail-closed activation state.

The current protocol is intentionally a draft.  A successful default check
means its chronology, source bindings, claim limits, and declared blockers are
internally consistent.  It does *not* mean evidence collection may start.
``--require-activation-ready`` additionally requires an external receipt for a
completely clean committed tree and fails while any activation blocker remains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bench_cleanser.verification._io import strict_json_dumps, strict_json_loads
from bench_cleanser.verification.corpus import CORPUS_SCHEMA_VERSION
from bench_cleanser.verification.evaluate import EVALUATION_SCHEMA_VERSION
from bench_cleanser.verification.policy_log import (
    CANONICAL_SAMPLER_ID,
    CANONICAL_SAMPLER_VERSION,
)
from experiments.prospective_pilot.ledger import (
    LEDGER_SCHEMA_VERSION,
    PROTOCOL_RESULT_VALIDATION_CONTRACT,
)
from experiments.prospective_pilot.proposal_policy import (
    PROPOSAL_POLICY_CONFIG,
    PROPOSAL_POLICY_CONFIG_SHA256,
    PROPOSAL_POLICY_SCHEMA_VERSION,
    PROPOSAL_POLICY_VERSION,
)
from experiments.prospective_pilot.review_packets import (
    EXPECTED_SOURCE_FEATURE_FREEZE,
)
from experiments.prospective_pilot.scheduler import (
    ACTION_DRAW_DOMAIN,
    ACTION_DRAW_SEED_SHA256,
    CANDIDATE_ORDER_DOMAIN,
    CANDIDATE_ORDER_SEED_SHA256,
    TASK_ORDER_DOMAIN,
    TASK_ORDER_SEED_SHA256,
)
from experiments.prospective_pilot.scientific_ledger import (
    SCIENTIFIC_LEDGER_SCHEMA_VERSION,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROTOCOL_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/preregistration.json")
PROSE_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/PREREGISTRATION.md")
PREHISTORY_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/prehistory.json")
EVIDENCE_RELATIVE = pathlib.PurePosixPath(
    "experiments/independent_execution_smoke/evidence-manifest.json"
)
SPHINX_EVIDENCE_RELATIVE = pathlib.PurePosixPath(
    "experiments/sphinx_execution_smoke/evidence-manifest.json"
)
RESOURCE_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/resource_ceiling.json")
POLICY_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/collection_policy.json")
SCHEDULER_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/scheduler_contract.json")
SCHEDULER_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/scheduler.py"
)
LEDGER_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/ledger.py")
SCIENTIFIC_LEDGER_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/scientific_ledger.py"
)
DISPATCHER_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/dispatcher.py"
)
PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/proposal_policy.py"
)
RELEASE_BUNDLE_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/release_bundle.py"
)
ACQUISITION_ORCHESTRATOR_RELATIVE = pathlib.PurePosixPath(
    "bench_cleanser/verification/orchestrate.py"
)
FRAME_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/frame_manifest.json")
EXECUTION_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/execution_freeze.json")
ADJUDICATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/adjudication_plan.json"
)
ANALYSIS_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/analysis_plan.json")
ANALYSIS_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/analysis.py"
)
TARGET_POLICY_MANIFEST_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/target_policy_manifest.json"
)
TARGET_POLICY_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "experiments/prospective_pilot/target_policies.py"
)
REVIEW_PACKET_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/review_packets.py")
VALIDATOR_RELATIVE = pathlib.PurePosixPath("experiments/prospective_pilot/validate_protocol.py")
ROUTER_RELATIVE = pathlib.PurePosixPath("bench_cleanser/verification/router.py")
POLICY_LOG_RELATIVE = pathlib.PurePosixPath("bench_cleanser/verification/policy_log.py")
CORPUS_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath("bench_cleanser/verification/corpus.py")
EVALUATION_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath(
    "bench_cleanser/verification/evaluate.py"
)
METRICS_IMPLEMENTATION_RELATIVE = pathlib.PurePosixPath("bench_cleanser/verification/metrics.py")

PROTOCOL_SCHEMA_VERSION = "prospective-evidence-routing-protocol-0.3.0"
PREHISTORY_SCHEMA_VERSION = "prospective-pilot-prehistory-0.1.0"
FREEZE_RECEIPT_SCHEMA_VERSION = "prospective-pilot-freeze-receipt-0.1.0"
RESOURCE_SCHEMA_VERSION = "prospective-pilot-resource-ceiling-0.1.0"
POLICY_SCHEMA_VERSION = "prospective-pilot-collection-policy-0.3.0"
SCHEDULER_SCHEMA_VERSION = "prospective-pilot-scheduler-contract-0.6.0"
FRAME_SCHEMA_VERSION = "prospective-pilot-frame-manifest-0.1.0"
EXECUTION_SCHEMA_VERSION = "prospective-pilot-execution-freeze-0.1.0"
ADJUDICATION_SCHEMA_VERSION = "prospective-pilot-adjudication-plan-0.1.0"
ANALYSIS_SCHEMA_VERSION = "prospective-pilot-analysis-plan-0.1.0"
STUDY_ID = "matched-24-independent-evidence-development-pilot-v2"
PREHISTORY_CHAIN_CONTRACT = "bench-cleanser-prospective-pilot-prehistory-chain-v1"
GENESIS_CHAIN_HEAD_SHA256 = "0" * 64
MAX_JSON_BYTES = 2 * 1024 * 1024
PRE_FREEZE_TASK_IDS = ["sympy__sympy-15976", "sphinx-doc__sphinx-8475"]

MEASUREMENT_DESIGN = (
    "prospective measurement collection on an outcome-exposed development "
    "cohort; not prospective policy validation"
)
BOUND_INTERPRETATION = (
    "optimistic full-coverage iid reference only; not cluster-valid inference "
    "under adaptive acceptance"
)
FREEZE_RECEIPT_BLOCKER = "clean-commit freeze receipt"
REQUIRED_ACTIVATION_BLOCKERS = {
    "Docker daemon and provisioner attestation",
    "execution target architecture",
    "opaque-map custodian identity",
    "per-task dependency-lock manifest",
    "per-task execution-spec manifest",
    "per-task image-digest manifest",
    "reviewer identities and independence attestations",
    "semantic model prompt endpoint calibration and cost identity",
    "aggregate resource reservation settlement and partial-frame reporting",
    "signed deterministic bootstrap receipt acquisition",
    "durable exclusive scheduler ledger and write-ahead dispatcher",
    "durable bootstrap curator adjudication substrate and resource ledgers",
    "trusted ledger-to-corpus terminal-outcome and cost compiler",
    "typed acquisition-result persistence and action-spec preimages",
}
FREEZE_OBJECT_PATHS = {
    "adjudication_config": ADJUDICATION_RELATIVE,
    "analysis_plan": ANALYSIS_RELATIVE,
    "analysis_source": ANALYSIS_IMPLEMENTATION_RELATIVE,
    "collection_policy": POLICY_RELATIVE,
    "execution_config": EXECUTION_RELATIVE,
    "frame_manifest": FRAME_RELATIVE,
    "policy_log_source": POLICY_LOG_RELATIVE,
    "proposal_policy_source": PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE,
    "preferred_router_source": ROUTER_RELATIVE,
    "prehistory": PREHISTORY_RELATIVE,
    "protocol_json": PROTOCOL_RELATIVE,
    "protocol_prose": PROSE_RELATIVE,
    "resource_ceiling": RESOURCE_RELATIVE,
    "scheduler_contract": SCHEDULER_RELATIVE,
    "scheduler_source": SCHEDULER_IMPLEMENTATION_RELATIVE,
    "ledger_source": LEDGER_IMPLEMENTATION_RELATIVE,
    "scientific_ledger_source": SCIENTIFIC_LEDGER_IMPLEMENTATION_RELATIVE,
    "corpus_source": CORPUS_IMPLEMENTATION_RELATIVE,
    "evaluation_source": EVALUATION_IMPLEMENTATION_RELATIVE,
    "metrics_source": METRICS_IMPLEMENTATION_RELATIVE,
    "dispatcher_source": DISPATCHER_IMPLEMENTATION_RELATIVE,
    "release_bundle_source": RELEASE_BUNDLE_IMPLEMENTATION_RELATIVE,
    "acquisition_orchestrator_source": ACQUISITION_ORCHESTRATOR_RELATIVE,
    "target_policy_manifest": TARGET_POLICY_MANIFEST_RELATIVE,
    "target_policy_source": TARGET_POLICY_IMPLEMENTATION_RELATIVE,
    "validator": VALIDATOR_RELATIVE,
    "review_packet_generator": REVIEW_PACKET_RELATIVE,
}
REQUIRED_FREEZE_ROLES = set(FREEZE_OBJECT_PATHS)
CONFIG_PATHS = {
    "resource_ceiling": RESOURCE_RELATIVE,
    "collection_policy": POLICY_RELATIVE,
    "scheduler_contract": SCHEDULER_RELATIVE,
    "execution_config": EXECUTION_RELATIVE,
    "adjudication_config": ADJUDICATION_RELATIVE,
    "analysis_plan": ANALYSIS_RELATIVE,
    "frame_manifest": FRAME_RELATIVE,
}

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}\Z")


class ProtocolError(ValueError):
    """A protocol, prehistory, or activation receipt is invalid."""


@dataclass(frozen=True)
class ValidationResult:
    activation_ready: bool
    blockers: tuple[str, ...]
    prehistory_event_count: int
    prehistory_chain_head_sha256: str
    protocol_sha256: str
    prehistory_sha256: str
    configuration_sha256: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "activation_ready": self.activation_ready,
            "blockers": list(self.blockers),
            "prehistory_event_count": self.prehistory_event_count,
            "prehistory_chain_head_sha256": self.prehistory_chain_head_sha256,
            "protocol_sha256": self.protocol_sha256,
            "prehistory_sha256": self.prehistory_sha256,
            "configuration_sha256": dict(sorted(self.configuration_sha256.items())),
            "protocol_valid": True,
        }


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProtocolError(f"{path} must be a JSON object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProtocolError(f"{path} must be a JSON array")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ProtocolError(
            f"{path} keys differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _sha256_value(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ProtocolError(f"{path} must be a lowercase SHA-256")
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProtocolError(f"{path} must be a positive integer")
    return value


def _nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolError(f"{path} must be a non-negative integer")
    return value


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError(f"{path} must be numeric")
    result = float(value)
    if not (-float("inf") < result < float("inf")):
        raise ProtocolError(f"{path} must be finite")
    return result


def _string(value: Any, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ProtocolError(f"{path} must be a trimmed non-empty string")
    return value


def _validate_scope(value: Any, path: str = "scope") -> None:
    scope = _object(value, path)
    _exact_keys(
        scope,
        {
            "candidate_count",
            "candidates_per_task",
            "excluded_task_clusters",
            "future_task_clusters",
            "replacement_allowed",
        },
        path,
    )
    if (
        scope["candidate_count"] != 66
        or scope["candidates_per_task"] != 3
        or scope["future_task_clusters"] != 22
        or scope["candidate_count"] != scope["candidates_per_task"] * scope["future_task_clusters"]
    ):
        raise ProtocolError(f"{path} does not describe the 22-task/66-candidate frame")
    if scope["excluded_task_clusters"] != PRE_FREEZE_TASK_IDS:
        raise ProtocolError(f"{path} must exclude exactly both pre-freeze tasks")
    if scope["replacement_allowed"] is not False:
        raise ProtocolError(f"{path} cannot allow replacement")


def _validate_unavailable_binding(
    value: Any,
    path: str,
    *,
    expected_keys: set[str],
) -> None:
    binding = _object(value, path)
    _exact_keys(binding, expected_keys | {"blocking", "status"}, path)
    if binding["status"] != "unavailable" or binding["blocking"] is not True:
        raise ProtocolError(f"{path} must remain explicitly unavailable and blocking")


def _confined_relative(value: Any, path: str) -> pathlib.PurePosixPath:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProtocolError(f"{path} must be a non-empty relative path")
    relative = pathlib.PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != value:
        raise ProtocolError(f"{path} must be a confined canonical relative path")
    return relative


def _regular_file(root: pathlib.Path, relative: pathlib.PurePosixPath) -> pathlib.Path:
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file():
        raise ProtocolError(f"required regular file is missing: {relative.as_posix()}")
    return path


def _read_bytes(root: pathlib.Path, relative: pathlib.PurePosixPath) -> bytes:
    path = _regular_file(root, relative)
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_JSON_BYTES:
        raise ProtocolError(f"file is empty or exceeds byte bound: {relative.as_posix()}")
    return payload


def _read_json(root: pathlib.Path, relative: pathlib.PurePosixPath) -> dict[str, Any]:
    try:
        value = strict_json_loads(_read_bytes(root, relative).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolError(f"invalid strict JSON at {relative.as_posix()}: {exc}") from exc
    return _object(value, relative.as_posix())


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_digest(value: Any) -> str:
    return _digest(strict_json_dumps(value).encode("utf-8"))


def _validate_pre_history_chain(prehistory: dict[str, Any]) -> tuple[int, str]:
    _exact_keys(
        prehistory,
        {
            "schema_version",
            "study_id",
            "append_only_contract",
            "events",
            "chain_head_sha256",
        },
        "prehistory",
    )
    if prehistory["schema_version"] != PREHISTORY_SCHEMA_VERSION:
        raise ProtocolError("unsupported prehistory schema_version")
    if prehistory["study_id"] != STUDY_ID:
        raise ProtocolError("prehistory study_id differs")
    if prehistory["append_only_contract"] != PREHISTORY_CHAIN_CONTRACT:
        raise ProtocolError("prehistory append-only contract differs")
    events = _array(prehistory["events"], "prehistory.events")
    if not events:
        raise ProtocolError("prehistory must contain at least one event")

    prior_head = GENESIS_CHAIN_HEAD_SHA256
    for index, raw_event in enumerate(events, start=1):
        event = _object(raw_event, f"prehistory.events[{index - 1}]")
        _exact_keys(
            event,
            {
                "sequence",
                "event_id",
                "classification",
                "task_id",
                "acquisition_window",
                "draft_artifacts",
                "evidence_record",
                "knowledge_boundary",
                "protocol_timing",
                "analysis_exclusion",
                "prior_chain_head_sha256",
                "event_sha256",
                "chain_head_sha256",
            },
            f"prehistory.events[{index - 1}]",
        )
        if event["sequence"] != index:
            raise ProtocolError("prehistory event sequence must be contiguous from one")
        if event["prior_chain_head_sha256"] != prior_head:
            raise ProtocolError("prehistory prior chain head differs")
        payload = dict(event)
        supplied_event_digest = _sha256_value(
            payload.pop("event_sha256"), f"prehistory.events[{index - 1}].event_sha256"
        )
        supplied_chain_head = _sha256_value(
            payload.pop("chain_head_sha256"),
            f"prehistory.events[{index - 1}].chain_head_sha256",
        )
        computed_event_digest = _canonical_digest(payload)
        if supplied_event_digest != computed_event_digest:
            raise ProtocolError("prehistory event_sha256 does not match event content")
        computed_chain_head = _canonical_digest(
            {
                "contract": PREHISTORY_CHAIN_CONTRACT,
                "prior_chain_head_sha256": prior_head,
                "event_sha256": computed_event_digest,
            }
        )
        if supplied_chain_head != computed_chain_head:
            raise ProtocolError("prehistory chain_head_sha256 does not match event link")
        prior_head = computed_chain_head

    if prehistory["chain_head_sha256"] != prior_head:
        raise ProtocolError("top-level prehistory chain head differs from final event")
    return len(events), prior_head


def _validate_feasibility_limits(event: dict[str, Any]) -> None:
    knowledge = _object(event["knowledge_boundary"], "event.knowledge_boundary")
    if knowledge != {
        "candidate_patches_accessible_before_execution": True,
        "hosted_labels_accessible_before_execution": True,
        "selection_blinded": False,
        "execution_blinded": False,
    }:
        raise ProtocolError("prehistory knowledge boundary differs")
    timing = _object(event["protocol_timing"], "event.protocol_timing")
    if timing != {
        "draft_bytes_existed_before_execution": True,
        "clean_commit_before_execution": None,
        "external_registration_before_execution": False,
        "recorded_after_execution": True,
        "recorded_at": None,
        "record_time_receipt": "not_recorded",
    }:
        raise ProtocolError("prehistory protocol timing must preserve the missing receipts")
    exclusion = _object(event["analysis_exclusion"], "event.analysis_exclusion")
    if exclusion != {
        "prospective_estimands": True,
        "off_policy_estimands": True,
        "hypotheses_h1_through_h6": True,
        "replacement_allowed": False,
        "descriptive_development_stratum_only": True,
    }:
        raise ProtocolError("prehistory analysis exclusion differs")


def _validate_sympy_feasibility_event(
    event: dict[str, Any],
    evidence: dict[str, Any],
    evidence_digest: str,
) -> None:
    if event["classification"] != "post_draft_pre_freeze_feasibility_execution":
        raise ProtocolError("feasibility event classification differs")
    if event["task_id"] != "sympy__sympy-15976":
        raise ProtocolError("feasibility event task differs")
    if event["event_id"] != "prehistory-0001-sympy-15976-feasibility":
        raise ProtocolError("SymPy feasibility event identity differs")

    evidence_record = _object(event["evidence_record"], "event.evidence_record")
    _exact_keys(
        evidence_record,
        {
            "logical_path",
            "schema_version",
            "study_id",
            "sha256",
            "external_bundle_bytes",
            "external_bundle_sha256",
        },
        "event.evidence_record",
    )
    if evidence_record["logical_path"] != EVIDENCE_RELATIVE.as_posix():
        raise ProtocolError("event evidence logical path differs")
    if evidence_record["sha256"] != evidence_digest:
        raise ProtocolError("event evidence digest differs from current source-locked record")
    if evidence_record["schema_version"] != evidence.get("schema_version"):
        raise ProtocolError("event evidence schema differs")
    if evidence_record["study_id"] != evidence.get("study_id"):
        raise ProtocolError("event evidence study_id differs")
    bundle = _object(evidence.get("evidence_bundle"), "evidence.evidence_bundle")
    if evidence_record["external_bundle_bytes"] != bundle.get("bytes"):
        raise ProtocolError("event external bundle byte count differs")
    if evidence_record["external_bundle_sha256"] != bundle.get("sha256"):
        raise ProtocolError("event external bundle digest differs")

    classification = _object(evidence.get("classification"), "evidence.classification")
    if classification.get("stage") != event["classification"]:
        raise ProtocolError("event classification contradicts evidence manifest")
    if classification.get("prospective") is not False or classification.get("blinded") is not False:
        raise ProtocolError("feasibility evidence must remain non-prospective and non-blinded")
    task = _object(evidence.get("task"), "evidence.task")
    if task.get("instance_id") != event["task_id"]:
        raise ProtocolError("event task contradicts evidence manifest")

    expected_drafts = {
        item["logical_path"]: item
        for item in _array(
            _object(evidence.get("protocol_state"), "evidence.protocol_state").get(
                "draft_artifacts"
            ),
            "evidence.protocol_state.draft_artifacts",
        )
        if isinstance(item, dict) and isinstance(item.get("logical_path"), str)
    }
    event_drafts = {
        item["logical_path"]: item
        for item in _array(event["draft_artifacts"], "event.draft_artifacts")
        if isinstance(item, dict) and isinstance(item.get("logical_path"), str)
    }
    if event_drafts != expected_drafts:
        raise ProtocolError("prehistory old-draft bindings differ from evidence manifest")
    _validate_feasibility_limits(event)


def _validate_sphinx_feasibility_event(
    event: dict[str, Any],
    evidence: dict[str, Any],
    evidence_digest: str,
    inherited_draft_artifacts: Any,
) -> None:
    if event["event_id"] != "prehistory-0002-sphinx-8475-feasibility":
        raise ProtocolError("Sphinx feasibility event identity differs")
    if event["classification"] != "post_draft_pre_freeze_feasibility_execution":
        raise ProtocolError("Sphinx feasibility event classification differs")
    if event["task_id"] != "sphinx-doc__sphinx-8475":
        raise ProtocolError("Sphinx feasibility event task differs")
    if event["acquisition_window"] != {
        "first_started_at": "2026-07-13T13:45:11.324927Z",
        "last_finished_at": "2026-07-13T13:46:34.783239Z",
        "receipt": "raw_execution_artifact_timestamps_not_authenticated_protocol_time",
    }:
        raise ProtocolError("Sphinx raw acquisition window differs")

    evidence_record = _object(event["evidence_record"], "Sphinx event.evidence_record")
    _exact_keys(
        evidence_record,
        {
            "logical_path",
            "schema_version",
            "study_id",
            "sha256",
            "external_bundle_bytes",
            "external_bundle_sha256",
            "external_bundle_index",
            "external_bundle_environment",
            "external_bundle_runner",
        },
        "Sphinx event.evidence_record",
    )
    if evidence_record["logical_path"] != SPHINX_EVIDENCE_RELATIVE.as_posix():
        raise ProtocolError("Sphinx evidence logical path differs")
    if evidence_record["sha256"] != evidence_digest:
        raise ProtocolError("Sphinx evidence digest differs from source-locked record")
    if evidence_record["schema_version"] != evidence.get("schema_version"):
        raise ProtocolError("Sphinx evidence schema differs")
    if evidence_record["study_id"] != evidence.get("study_id"):
        raise ProtocolError("Sphinx evidence study_id differs")

    bundle = _object(evidence.get("evidence_bundle"), "Sphinx evidence.evidence_bundle")
    _exact_keys(
        bundle,
        {
            "logical_filename",
            "media_type",
            "bytes",
            "sha256",
            "root_directory",
            "file_member_count",
            "directory_member_count",
            "maximum_file_member_bytes",
            "index",
            "runner",
            "location_contract",
        },
        "Sphinx evidence.evidence_bundle",
    )
    bundle_bytes = _positive_int(bundle["bytes"], "Sphinx bundle bytes")
    bundle_sha256 = _sha256_value(bundle["sha256"], "Sphinx bundle sha256")
    if (
        evidence_record["external_bundle_bytes"] != bundle_bytes
        or evidence_record["external_bundle_sha256"] != bundle_sha256
    ):
        raise ProtocolError("Sphinx external bundle identity differs")

    runtime = _object(evidence.get("runtime"), "Sphinx evidence.runtime")
    environment = _object(
        runtime.get("environment_record"),
        "Sphinx evidence.runtime.environment_record",
    )
    _exact_keys(environment, {"bytes", "sha256"}, "Sphinx environment record")
    _positive_int(environment["bytes"], "Sphinx environment bytes")
    _sha256_value(environment["sha256"], "Sphinx environment sha256")
    expected_members = {
        "external_bundle_index": bundle.get("index"),
        "external_bundle_environment": {
            "path": "environment.json",
            **environment,
        },
        "external_bundle_runner": bundle.get("runner"),
    }
    for key, expected in expected_members.items():
        expected_member = _object(expected, f"Sphinx evidence source {key}")
        _exact_keys(expected_member, {"path", "bytes", "sha256"}, key)
        _positive_int(expected_member["bytes"], f"Sphinx {key} bytes")
        _sha256_value(expected_member["sha256"], f"Sphinx {key} sha256")
        member = _object(evidence_record[key], f"Sphinx event.evidence_record.{key}")
        _exact_keys(member, {"path", "bytes", "sha256"}, key)
        if member != expected_member:
            raise ProtocolError(f"Sphinx {key} identity differs")
    if bundle.get("index") != expected_members["external_bundle_index"]:
        raise ProtocolError("Sphinx bundle index contradicts the evidence manifest")
    if bundle.get("runner") != expected_members["external_bundle_runner"]:
        raise ProtocolError("Sphinx bundle runner contradicts the evidence manifest")
    expected_environment = dict(
        _object(
            expected_members["external_bundle_environment"],
            "Sphinx event environment member",
        )
    )
    expected_environment.pop("path")
    if environment != expected_environment:
        raise ProtocolError("Sphinx environment contradicts the evidence manifest")

    classification = _object(
        evidence.get("classification"),
        "Sphinx evidence.classification",
    )
    if (
        classification.get("stage") != event["classification"]
        or classification.get("prospective") is not False
        or classification.get("blinded") is not False
    ):
        raise ProtocolError("Sphinx evidence must remain pre-freeze and non-blinded")
    task = _object(evidence.get("task"), "Sphinx evidence.task")
    if task.get("instance_id") != event["task_id"]:
        raise ProtocolError("Sphinx task contradicts the evidence manifest")
    protocol_state = _object(
        evidence.get("protocol_state"),
        "Sphinx evidence.protocol_state",
    )
    if (
        protocol_state.get("registration_freeze") is not None
        or protocol_state.get("clean_commit_freeze") is not None
    ):
        raise ProtocolError("Sphinx evidence cannot claim a pre-execution freeze")
    if event["draft_artifacts"] != inherited_draft_artifacts:
        raise ProtocolError("Sphinx event must inherit the recorded pre-existing draft bytes")
    _validate_feasibility_limits(event)


def _validate_resource_ceiling(resource: dict[str, Any]) -> set[str]:
    _exact_keys(
        resource,
        {
            "schema_version",
            "study_id",
            "status",
            "scope",
            "decision_limits",
            "compute_limits",
            "semantic_limits",
            "human_limits",
            "calendar_limits",
            "enforcement",
        },
        "resource_ceiling",
    )
    if (
        resource["schema_version"] != RESOURCE_SCHEMA_VERSION
        or resource["study_id"] != STUDY_ID
        or resource["status"] != "specified_numeric_ceiling_pending_clean_commit_freeze"
    ):
        raise ProtocolError("resource ceiling identity or status differs")
    _validate_scope(resource["scope"], "resource_ceiling.scope")

    decisions = _object(resource["decision_limits"], "resource_ceiling.decision_limits")
    _exact_keys(
        decisions,
        {
            "maximum_candidate_chain_decisions",
            "maximum_candidate_terminal_decisions",
            "maximum_curator_hardening_attempts",
            "maximum_curator_primary_execution_attempts",
            "maximum_deterministic_static_acquisitions",
            "maximum_nonterminal_policy_acquisitions",
            "maximum_nonterminal_policy_acquisitions_per_candidate",
            "maximum_secondary_container_free_attempts",
            "maximum_task_selection_decisions",
            "maximum_total_acquisition_events",
            "maximum_total_policy_decisions",
        },
        "resource_ceiling.decision_limits",
    )
    for key, value in decisions.items():
        _positive_int(value, f"resource_ceiling.decision_limits.{key}")
    if (
        decisions["maximum_nonterminal_policy_acquisitions"] != 66 * 4
        or decisions["maximum_candidate_terminal_decisions"] != 66
        or decisions["maximum_task_selection_decisions"] != 22
        or decisions["maximum_total_policy_decisions"] != 66 * 4 + 66 + 22
        or decisions["maximum_curator_primary_execution_attempts"] != 66 * 3
        or decisions["maximum_secondary_container_free_attempts"] != 8 * 3 * 3
        or decisions["maximum_curator_hardening_attempts"] != 22 * 6
        or decisions["maximum_total_acquisition_events"]
        != 66 + 66 * 4 + 66 * 3 + 8 * 3 * 3 + 22 * 6
    ):
        raise ProtocolError("resource ceiling decision arithmetic differs")

    compute = _object(resource["compute_limits"], "resource_ceiling.compute_limits")
    _exact_keys(
        compute,
        {
            "maximum_concurrent_workers",
            "maximum_cumulative_cpu_seconds",
            "maximum_cumulative_worker_wall_seconds",
            "maximum_peak_rss_bytes_per_process",
            "maximum_total_process_launches",
            "maximum_total_storage_bytes",
        },
        "resource_ceiling.compute_limits",
    )
    for key, value in compute.items():
        _positive_int(value, f"resource_ceiling.compute_limits.{key}")
    if (
        compute["maximum_concurrent_workers"] != 4
        or compute["maximum_cumulative_cpu_seconds"]
        != compute["maximum_cumulative_worker_wall_seconds"] * 4
        or compute["maximum_total_process_launches"]
        != decisions["maximum_total_acquisition_events"]
    ):
        raise ProtocolError("resource ceiling compute limits are internally inconsistent")

    semantic = _object(resource["semantic_limits"], "resource_ceiling.semantic_limits")
    _exact_keys(
        semantic,
        {
            "maximum_calls",
            "maximum_input_tokens",
            "maximum_output_tokens",
            "maximum_usd_micros",
        },
        "resource_ceiling.semantic_limits",
    )
    for key, value in semantic.items():
        _positive_int(value, f"resource_ceiling.semantic_limits.{key}")
    if (
        semantic["maximum_calls"] != 66
        or semantic["maximum_input_tokens"] != 66 * 131072
        or semantic["maximum_output_tokens"] != 66 * 32768
    ):
        raise ProtocolError("semantic resource ceilings differ from the per-candidate cap")

    human = _object(resource["human_limits"], "resource_ceiling.human_limits")
    _exact_keys(human, {"maximum_human_minutes", "maximum_reviewers"}, "human_limits")
    if human["maximum_reviewers"] != 3:
        raise ProtocolError("resource ceiling must retain exactly three reviewer slots")
    _positive_int(human["maximum_human_minutes"], "human_limits.maximum_human_minutes")
    calendar = _object(resource["calendar_limits"], "resource_ceiling.calendar_limits")
    _exact_keys(
        calendar,
        {"maximum_seconds_from_activation_to_last_acquisition"},
        "resource_ceiling.calendar_limits",
    )
    _positive_int(
        calendar["maximum_seconds_from_activation_to_last_acquisition"],
        "calendar limit",
    )
    enforcement = _object(resource["enforcement"], "resource_ceiling.enforcement")
    _exact_keys(
        enforcement,
        {
            "budget_increase_requires_new_protocol_version",
            "counters_committed_before_next_action",
            "outcome_dependent_extension_allowed",
            "on_any_limit",
            "units",
        },
        "resource_ceiling.enforcement",
    )
    if (
        enforcement["budget_increase_requires_new_protocol_version"] is not True
        or enforcement["counters_committed_before_next_action"] is not True
        or enforcement["outcome_dependent_extension_allowed"] is not False
        or enforcement["on_any_limit"] != "halt_without_replacement_and_preserve_the_partial_frame"
    ):
        raise ProtocolError("resource-ceiling enforcement must fail closed")
    units = _object(enforcement["units"], "resource_ceiling.enforcement.units")
    _exact_keys(units, {"cpu", "currency", "human_time", "storage", "wall_time"}, "units")
    return set()


def _validate_frame_manifest(frame: dict[str, Any]) -> set[str]:
    _exact_keys(
        frame,
        {
            "schema_version",
            "study_id",
            "status",
            "source_feature_freeze",
            "excluded_task_clusters",
            "task_count",
            "candidates_per_task",
            "candidate_count",
            "task_ids_sha256",
            "candidate_ids_sha256",
            "tasks_sha256",
            "tasks",
        },
        "frame_manifest",
    )
    if (
        frame["schema_version"] != FRAME_SCHEMA_VERSION
        or frame["study_id"] != STUDY_ID
        or frame["status"] != "frozen_uncommitted"
        or frame["excluded_task_clusters"] != PRE_FREEZE_TASK_IDS
        or frame["task_count"] != 22
        or frame["candidates_per_task"] != 3
        or frame["candidate_count"] != 66
    ):
        raise ProtocolError("frame manifest identity, exclusions, or counts differ")
    source = _object(frame["source_feature_freeze"], "frame source_feature_freeze")
    _exact_keys(
        source,
        {
            "logical_name",
            "bytes",
            "sha256",
            "selected_instance_ids_sha256",
            "selected_task_identities_sha256",
        },
        "frame source_feature_freeze",
    )
    if source != dict(EXPECTED_SOURCE_FEATURE_FREEZE):
        raise ProtocolError("frame source feature-freeze identity differs")
    tasks = _array(frame["tasks"], "frame_manifest.tasks")
    normalized: list[dict[str, Any]] = []
    task_ids: list[str] = []
    candidate_ids: list[str] = []
    for index, raw in enumerate(tasks):
        item = _object(raw, f"frame_manifest.tasks[{index}]")
        _exact_keys(item, {"task_id", "candidate_ids"}, f"frame task {index}")
        task_id = _string(item["task_id"], f"frame task {index} task_id")
        raw_candidates = _array(item["candidate_ids"], f"frame task {index} candidates")
        if (
            len(raw_candidates) != 3
            or any(
                not isinstance(candidate, str) or _CANDIDATE_RE.fullmatch(candidate) is None
                for candidate in raw_candidates
            )
            or raw_candidates != sorted(raw_candidates)
            or len(raw_candidates) != len(set(raw_candidates))
        ):
            raise ProtocolError("frame task candidate IDs must be three sorted opaque hashes")
        task_ids.append(task_id)
        candidate_ids.extend(raw_candidates)
        normalized.append({"task_id": task_id, "candidate_ids": raw_candidates})
    if (
        len(tasks) != 22
        or task_ids != sorted(task_ids)
        or len(task_ids) != len(set(task_ids))
        or len(candidate_ids) != 66
        or len(candidate_ids) != len(set(candidate_ids))
    ):
        raise ProtocolError("frame task/candidate mapping is not exact and unique")
    expected = {
        "task_ids_sha256": _canonical_digest(task_ids),
        "candidate_ids_sha256": _canonical_digest(sorted(candidate_ids)),
        "tasks_sha256": _canonical_digest(normalized),
    }
    for key, digest in expected.items():
        if frame[key] != digest:
            raise ProtocolError(f"frame manifest {key} differs")
    return set()


def _validate_collection_policy(root: pathlib.Path, policy: dict[str, Any]) -> set[str]:
    _exact_keys(
        policy,
        {
            "schema_version",
            "study_id",
            "status",
            "scope",
            "rng",
            "behavior_policy",
            "preferred_action_rule",
            "terminal_admissibility",
            "semantic_producer",
            "implementation_bindings",
        },
        "collection_policy",
    )
    if (
        policy["schema_version"] != POLICY_SCHEMA_VERSION
        or policy["study_id"] != STUDY_ID
        or policy["status"] != "core_implemented_operationally_blocked"
    ):
        raise ProtocolError("collection policy identity or status differs")
    _validate_scope(policy["scope"], "collection_policy.scope")

    rng = _object(policy["rng"], "collection_policy.rng")
    _exact_keys(
        rng,
        {
            "action_draws",
            "candidate_order",
            "counter_contract",
            "generator_contract",
            "selection_timing",
            "task_order",
        },
        "rng",
    )
    if rng["counter_contract"] != (
        "task_order_index_times_15_plus_round_index_times_3_plus_"
        "candidate_position_with_terminal_candidate_slots_reserved_and_never_reused"
    ):
        raise ProtocolError("collection RNG counter contract differs")
    if rng["selection_timing"] != (
        "post_hosted_outcome_exposure_pre_future_measurement_not_outcome_naive"
    ):
        raise ProtocolError("collection RNG timing boundary differs")
    if rng["generator_contract"] != (
        "sha256(hex_decode(seed_sha256) || 0x00 || utf8(domain) || 0x00 || "
        "uint64_be(counter)); unsigned_big_endian_first_53_bits_divided_by_2_pow_53"
    ):
        raise ProtocolError("collection RNG contract differs")
    for field in ("action_draws", "candidate_order", "task_order"):
        binding = _object(rng[field], f"collection_policy.rng.{field}")
        _exact_keys(binding, {"domain", "seed_sha256"}, f"rng.{field}")
        _string(binding["domain"], f"rng.{field}.domain")
        _sha256_value(binding["seed_sha256"], f"rng.{field}.seed_sha256")
    if (
        len(
            {
                rng[field]["seed_sha256"]
                for field in ("action_draws", "candidate_order", "task_order")
            }
        )
        != 3
    ):
        raise ProtocolError("collection RNG seeds must be domain-separated")
    expected_rng = {
        "action_draws": {
            "domain": ACTION_DRAW_DOMAIN,
            "seed_sha256": ACTION_DRAW_SEED_SHA256,
        },
        "candidate_order": {
            "domain": CANDIDATE_ORDER_DOMAIN,
            "seed_sha256": CANDIDATE_ORDER_SEED_SHA256,
        },
        "task_order": {
            "domain": TASK_ORDER_DOMAIN,
            "seed_sha256": TASK_ORDER_SEED_SHA256,
        },
    }
    for name, expected in expected_rng.items():
        if rng[name] != expected:
            raise ProtocolError(f"collection RNG {name} literal binding differs")

    behavior = _object(policy["behavior_policy"], "collection_policy.behavior_policy")
    _exact_keys(
        behavior,
        {
            "action_catalog",
            "availability_reason_allowlist",
            "action_probability",
            "availability_rules",
            "disclosed_action_count",
            "exploration_mass",
            "maximum_available_actions",
            "minimum_history_conditioned_propensity",
            "preferred_mass",
            "sampler",
            "unavailable_actions_receive_zero_probability",
        },
        "collection_policy.behavior_policy",
    )
    expected_catalog = [
        {"action_id": "abstain", "evidence_kind": None, "route_action": "abstain"},
        {"action_id": "accept", "evidence_kind": None, "route_action": "accept"},
        {
            "action_id": "full_primary",
            "evidence_kind": "full_execution",
            "route_action": "run_full_execution",
        },
        {
            "action_id": "full_repeat",
            "evidence_kind": "full_execution",
            "route_action": "run_full_execution",
        },
        {
            "action_id": "hardening_curator",
            "evidence_kind": "oracle_hardening",
            "route_action": "harden_oracle",
        },
        {"action_id": "reject", "evidence_kind": None, "route_action": "reject"},
        {
            "action_id": "semantic_primary",
            "evidence_kind": "semantic",
            "route_action": "run_semantic",
        },
        {
            "action_id": "static_bootstrap",
            "evidence_kind": "static",
            "route_action": "run_static",
        },
        {
            "action_id": "targeted_primary",
            "evidence_kind": "targeted_execution",
            "route_action": "run_targeted_execution",
        },
    ]
    if (
        behavior["action_catalog"] != expected_catalog
        or behavior["action_probability"]
        != "0.5 * indicator(action_is_preferred) + 0.5 / available_action_count"
        or behavior["exploration_mass"] != 0.5
        or behavior["preferred_mass"] != 0.5
        or behavior["disclosed_action_count"] != len(expected_catalog)
        or behavior["maximum_available_actions"] != 7
        or behavior["minimum_history_conditioned_propensity"] != 0.5 / 7
        or behavior["unavailable_actions_receive_zero_probability"] is not True
    ):
        raise ProtocolError("collection behavior-policy distribution differs")
    if behavior["availability_reason_allowlist"] != [
        "acquisition_ceiling",
        "action_already_completed",
        "always_available",
        "candidate_terminal",
        "curator_only_not_policy_available",
        "deterministic_bootstrap_completed",
        "execution_binding_available",
        "execution_binding_unavailable",
        "primary_full_required",
        "proposal_terminal_available",
        "proposal_terminal_unavailable",
        "semantic_binding_available",
        "semantic_binding_unavailable",
        "terminal_governed",
    ]:
        raise ProtocolError("collection availability-reason allowlist differs")
    availability = _object(
        behavior["availability_rules"],
        "collection_policy.behavior_policy.availability_rules",
    )
    if availability != {
        "full_primary": "available_once_after_the_per_task_execution_bindings_are_complete",
        "full_repeat": ("available_once_only_after_full_primary_returns_and_uses_a_fresh_worktree"),
        "hardening_curator": (
            "disclosed_for_route_enum_completeness_but_permanently_unavailable_to_"
            "the_behavior_policy_and_reserved_for_the_post_policy_curator_stream"
        ),
        "semantic_primary": (
            "available_once_only_when_the_complete_semantic_producer_identity_is_frozen"
        ),
        "static_bootstrap": (
            "collected_deterministically_before_the_first_randomized_decision_and_"
            "therefore_disclosed_but_permanently_unavailable_to_the_behavior_policy"
        ),
        "targeted_primary": "available_once_after_the_per_task_execution_spec_is_frozen",
        "terminals": "governed_by_terminal_admissibility",
    }:
        raise ProtocolError("collection action-availability rules differ")
    sampler = _object(behavior["sampler"], "collection_policy.behavior_policy.sampler")
    if sampler != {
        "id": CANONICAL_SAMPLER_ID,
        "implementation": "bench_cleanser.verification.policy_log.sample_behavior_action",
        "version": CANONICAL_SAMPLER_VERSION,
    }:
        raise ProtocolError("collection behavior sampler differs from package implementation")

    preferred = _object(policy["preferred_action_rule"], "collection_policy.preferred_action_rule")
    _exact_keys(
        preferred,
        {
            "fallback_when_router_action_is_unavailable",
            "multiple_concrete_offers_for_one_kind",
            "proposal_policy",
            "router",
            "rule",
        },
        "preferred_action_rule",
    )
    if (
        preferred["fallback_when_router_action_is_unavailable"]
        != (
            "semantic_primary_then_targeted_primary_then_full_primary_then_full_repeat_then_abstain"
        )
        or preferred["multiple_concrete_offers_for_one_kind"] != "lowest_lexicographic_action_id"
        or preferred["rule"]
        != ("use_fallible_terminal_proposal_else_router_match_else_frozen_available_fallback")
    ):
        raise ProtocolError("preferred-action fallback or tie rule differs")
    router = _object(preferred["router"], "preferred_action_rule.router")
    _exact_keys(
        router,
        {
            "logical_path",
            "policy_config",
            "policy_config_sha256",
            "policy_version",
            "sha256",
            "status",
            "symbol",
        },
        "router",
    )
    expected_policy_config = {
        "allow_semantic_accept_in_evaluation": False,
        "full_relative_cost": 0.7,
        "hardening_relative_cost": 1.0,
        "high_candidate_risk": 0.55,
        "high_verifier_risk": 0.4,
        "maximum_false_accept_risk": 0.02,
        "maximum_full_execution_attempts": 3,
        "maximum_hardening_attempts": 2,
        "minimum_authoritative_verifier_validity": 0.95,
        "minimum_full_execution_replicates": 2,
        "semantic_relative_cost": 0.05,
        "static_relative_cost": 0.01,
        "targeted_relative_cost": 0.2,
        "trusted_authoritative_bindings": [],
        "trusted_calibration_bindings": [],
        "version": "conservative-v1",
    }
    if (
        router["logical_path"] != ROUTER_RELATIVE.as_posix()
        or router["policy_version"] != "conservative-v1"
        or router["status"] != "available_uncommitted"
        or router["sha256"] != _digest(_read_bytes(root, ROUTER_RELATIVE))
        or router["symbol"] != "bench_cleanser.verification.router.ConservativeRouter"
        or router["policy_config"] != expected_policy_config
        or router["policy_config_sha256"] != _canonical_digest(expected_policy_config)
    ):
        raise ProtocolError("preferred router source binding differs")
    proposal = _object(
        preferred["proposal_policy"],
        "preferred_action_rule.proposal_policy",
    )
    _exact_keys(
        proposal,
        {"config_sha256", "logical_path", "sha256", "version"},
        "preferred_action_rule.proposal_policy",
    )
    if proposal != {
        "config_sha256": PROPOSAL_POLICY_CONFIG_SHA256,
        "logical_path": PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE.as_posix(),
        "sha256": _digest(_read_bytes(root, PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE)),
        "version": PROPOSAL_POLICY_VERSION,
    }:
        raise ProtocolError("proposal-policy source/config binding differs")
    if _canonical_digest(PROPOSAL_POLICY_CONFIG) != PROPOSAL_POLICY_CONFIG_SHA256:
        raise ProtocolError("runtime proposal-policy config identity differs")

    terminal = _object(policy["terminal_admissibility"], "collection_policy.terminal_admissibility")
    _exact_keys(
        terminal,
        {
            "abstain",
            "accept",
            "error_unavailable_inconclusive_or_disagreement",
            "interpretation",
            "reject",
            "terminal_decisions_are_sampled_and_propensity_logged",
        },
        "terminal_admissibility",
    )
    if (
        terminal["abstain"] != "always_available"
        or terminal["accept"]
        != (
            "available_only_after_full_primary_and_fresh_full_repeat_are_"
            "concordant_supports_correct"
        )
        or terminal["reject"]
        != (
            "available_only_after_full_primary_and_fresh_full_repeat_are_"
            "concordant_supports_incorrect"
        )
        or terminal["error_unavailable_inconclusive_or_disagreement"]
        != "never_enables_accept_or_reject"
        or terminal["interpretation"] != "fallible_sensor_proposal_not_candidate_truth"
        or terminal["terminal_decisions_are_sampled_and_propensity_logged"] is not True
    ):
        raise ProtocolError("terminal admissibility must be exact and propensity logged")

    semantic = _object(policy["semantic_producer"], "collection_policy.semantic_producer")
    _exact_keys(
        semantic,
        {
            "availability",
            "base_url_class",
            "blocking",
            "calibration_id",
            "cost_policy_sha256",
            "model",
            "prompt_logical_path",
            "prompt_sha256",
            "provider",
            "reason",
        },
        "semantic_producer",
    )
    if semantic["availability"] != "unavailable" or semantic["blocking"] is not True:
        raise ProtocolError("semantic producer must remain unavailable and blocking")
    for field in (
        "base_url_class",
        "calibration_id",
        "cost_policy_sha256",
        "model",
        "prompt_logical_path",
        "prompt_sha256",
        "provider",
    ):
        if semantic[field] is not None:
            raise ProtocolError("unavailable semantic producer cannot contain partial identity")

    implementations = _object(policy["implementation_bindings"], "implementation_bindings")
    _exact_keys(
        implementations,
        {"frame_manifest", "policy_log", "proposal_policy", "task_scheduler"},
        "implementation_bindings",
    )
    frame = _object(implementations["frame_manifest"], "implementation_bindings.frame_manifest")
    _exact_keys(frame, {"logical_path", "sha256", "status"}, "frame_manifest binding")
    if (
        frame["logical_path"] != FRAME_RELATIVE.as_posix()
        or frame["sha256"] != _digest(_read_bytes(root, FRAME_RELATIVE))
        or frame["status"] != "frozen_uncommitted"
    ):
        raise ProtocolError("collection frame-manifest binding differs")
    policy_log = _object(implementations["policy_log"], "implementation_bindings.policy_log")
    _exact_keys(policy_log, {"logical_path", "sha256", "status"}, "policy_log")
    if (
        policy_log["logical_path"] != POLICY_LOG_RELATIVE.as_posix()
        or policy_log["sha256"] != _digest(_read_bytes(root, POLICY_LOG_RELATIVE))
        or policy_log["status"] != "available_uncommitted"
    ):
        raise ProtocolError("policy-log source binding differs")
    proposal_binding = _object(
        implementations["proposal_policy"],
        "implementation_bindings.proposal_policy",
    )
    _exact_keys(
        proposal_binding,
        {"logical_path", "sha256", "status"},
        "proposal_policy",
    )
    if proposal_binding != {
        "logical_path": PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE.as_posix(),
        "sha256": _digest(_read_bytes(root, PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE)),
        "status": "available_uncommitted",
    }:
        raise ProtocolError("proposal-policy implementation binding differs")
    scheduler = _object(implementations["task_scheduler"], "implementation_bindings.task_scheduler")
    _exact_keys(
        scheduler,
        {"blocking", "logical_path", "sha256", "status"},
        "implementation_bindings.task_scheduler",
    )
    if (
        scheduler["blocking"] is not True
        or scheduler["logical_path"] != SCHEDULER_IMPLEMENTATION_RELATIVE.as_posix()
        or scheduler["sha256"] != _digest(_read_bytes(root, SCHEDULER_IMPLEMENTATION_RELATIVE))
        or scheduler["status"] != "core_available_operationally_blocked"
    ):
        raise ProtocolError("task scheduler source binding differs")
    return {"semantic model prompt endpoint calibration and cost identity"}


def _validate_scheduler_contract(
    root: pathlib.Path,
    scheduler: dict[str, Any],
) -> set[str]:
    _exact_keys(
        scheduler,
        {
            "schema_version",
            "study_id",
            "status",
            "scope",
            "logical_order",
            "frame_manifest",
            "candidate_chain",
            "policy_log_crosswalk",
            "task_disposition",
            "joint_propensity",
            "failure_handling",
            "operational_requirements",
            "implementation",
        },
        "scheduler_contract",
    )
    if (
        scheduler["schema_version"] != SCHEDULER_SCHEMA_VERSION
        or scheduler["study_id"] != STUDY_ID
        or scheduler["status"]
        != (
            "scheduler_bootstrap_proposal_ledger_dispatcher_scientific_export_"
            "audit_and_split_corpus_evaluation_contracts_implemented_"
            "operationally_blocked"
        )
    ):
        raise ProtocolError("scheduler contract identity or status differs")
    _validate_scope(scheduler["scope"], "scheduler_contract.scope")
    logical = _object(scheduler["logical_order"], "scheduler_contract.logical_order")
    _exact_keys(
        logical,
        {
            "action_draw_counter",
            "candidate_order",
            "candidate_rounds",
            "parallel_execution",
            "task_batches",
            "task_order",
        },
        "scheduler_contract.logical_order",
    )
    if logical != {
        "action_draw_counter": (
            "task_order_index_times_15_plus_round_index_times_3_plus_"
            "candidate_position_with_terminal_candidate_slots_reserved_and_never_reused"
        ),
        "candidate_order": (
            "ascending_sha256(hex_decode(candidate_order_seed_sha256) || 0x00 || "
            "utf8(candidate_order_domain) || 0x00 || utf8(opaque_candidate_id))"
        ),
        "candidate_rounds": (
            "one_decision_per_nonterminal_candidate_in_frozen_candidate_order_before_the_next_round"
        ),
        "parallel_execution": (
            "actions_in_one_committed_round_may_execute_concurrently_but_no_result_"
            "changes_another_action_in_that_round"
        ),
        "task_batches": (
            "ascending_task_order_partitioned_into_contiguous_batches_of_at_most_four"
        ),
        "task_order": (
            "ascending_sha256(hex_decode(task_order_seed_sha256) || 0x00 || "
            "utf8(task_order_domain) || 0x00 || utf8(opaque_task_id))"
        ),
    }:
        raise ProtocolError("scheduler logical-order contract differs")
    frame = _object(scheduler["frame_manifest"], "scheduler_contract.frame_manifest")
    _exact_keys(frame, {"logical_path", "sha256", "status"}, "scheduler frame binding")
    if frame != {
        "logical_path": FRAME_RELATIVE.as_posix(),
        "sha256": _digest(_read_bytes(root, FRAME_RELATIVE)),
        "status": "frozen_uncommitted",
    }:
        raise ProtocolError("scheduler frame-manifest binding differs")
    chain = _object(scheduler["candidate_chain"], "scheduler_contract.candidate_chain")
    _exact_keys(
        chain,
        {
            "each_nonterminal_action_id_at_most_once",
            "fresh_worktree_preimage_required_for_full_repeat",
            "maximum_decisions",
            "maximum_nonterminal_acquisitions",
            "nonterminal_acquisition_id_preallocated_in_policy_decision",
            "repeat_action_spec_must_differ_from_primary",
            "terminal_actions",
            "typed_successor_must_append_one_route_and_observation",
            "write_ahead_before_dispatch",
        },
        "scheduler_contract.candidate_chain",
    )
    if (
        chain["maximum_decisions"] != 5
        or chain["maximum_nonterminal_acquisitions"] != 4
        or chain["each_nonterminal_action_id_at_most_once"] is not True
        or chain["fresh_worktree_preimage_required_for_full_repeat"] is not True
        or chain["nonterminal_acquisition_id_preallocated_in_policy_decision"] is not True
        or chain["repeat_action_spec_must_differ_from_primary"] is not True
        or chain["typed_successor_must_append_one_route_and_observation"] is not True
        or chain["terminal_actions"] != ["accept", "reject", "abstain"]
        or chain["write_ahead_before_dispatch"] is not True
    ):
        raise ProtocolError("scheduler candidate-chain limit or terminal contract differs")
    policy_crosswalk = _object(
        scheduler["policy_log_crosswalk"],
        "scheduler_contract.policy_log_crosswalk",
    )
    expected_policy_crosswalk = {
        "bootstrap_history": (
            "one_candidate_bound_static_receipt_is_required_before_round_zero_and_"
            "is_hash_bound_as_an_immutable_prefix_but_never_counted_as_a_"
            "randomized_policy_decision_propensity_or_trajectory_step"
        ),
        "candidate_chain_validation": (
            "group_embedded_policy_decisions_by_candidate_in_canonical_round_order_"
            "and_validate_each_with_validate_policy_decision_chain"
        ),
        "candidate_head": (
            "the_scheduler_candidate_head_is_exactly_the_embedded_logged_policy_"
            "decision_trajectory_head_not_a_scheduler_parallel_chain"
        ),
        "decision_identity": (
            "candidate_selection_identity_sha256_equals_embedded_logged_policy_"
            "decision_decision_sha256"
        ),
        "embedded_record": "scheduled_decisions[].logged_policy_decision",
        "nonterminal_result_join": (
            "the_successor_evidence_observation_acquisition_id_equals_the_"
            "preallocated_logged_policy_decision_acquisition_id"
        ),
        "terminal_result_join": (
            "terminal_logged_policy_decisions_have_no_acquisition_id_and_append_no_"
            "evidence_observation"
        ),
    }
    if policy_crosswalk != expected_policy_crosswalk:
        raise ProtocolError("scheduler/package policy-log crosswalk differs")
    disposition = _object(scheduler["task_disposition"], "scheduler_contract.task_disposition")
    _exact_keys(
        disposition,
        {
            "all_candidate_chains_are_observed_before_selection",
            "if_multiple_candidates_accept",
            "if_no_candidate_accepts",
            "one_selected_candidate_or_abstention_per_task",
            "selection_must_bind_the_complete_genesis_rooted_chain",
            "selection_timestamp_not_before_final_round",
            "task_selection_is_committed_as_a_separate_decision",
        },
        "scheduler_contract.task_disposition",
    )
    if not all(
        disposition[key] is True
        for key in (
            "all_candidate_chains_are_observed_before_selection",
            "one_selected_candidate_or_abstention_per_task",
            "selection_must_bind_the_complete_genesis_rooted_chain",
            "selection_timestamp_not_before_final_round",
            "task_selection_is_committed_as_a_separate_decision",
        )
    ):
        raise ProtocolError("scheduler must observe all candidates and commit task selection")
    if (
        disposition["if_multiple_candidates_accept"]
        != "select_the_first_accepted_candidate_in_frozen_candidate_order"
        or disposition["if_no_candidate_accepts"] != "abstain"
    ):
        raise ProtocolError("scheduler task-selection rule differs")
    joint = _object(scheduler["joint_propensity"], "scheduler_contract.joint_propensity")
    _exact_keys(
        joint,
        {
            "action_probability_source",
            "candidate_scheduler_probability",
            "computation",
            "history",
            "task_trajectory_probability",
            "zero_or_missing_probability",
        },
        "scheduler_contract.joint_propensity",
    )
    if joint != {
        "action_probability_source": ("the_full_logged_history_conditioned_behavior_distribution"),
        "candidate_scheduler_probability": 1.0,
        "computation": (
            "retain_every_action_log_probability_in_canonical_task_decision_order_"
            "apply_one_global_fsum_then_exponentiate_only_for_reporting"
        ),
        "history": (
            "complete_task_cluster_history_including_all_three_candidate_chains_"
            "and_prior_round_results"
        ),
        "task_trajectory_probability": (
            "product_of_every_realized_action_probability_in_the_task_cluster"
        ),
        "zero_or_missing_probability": "support_violation_and_no_ope_estimate",
    }:
        raise ProtocolError("scheduler joint-propensity contract must fail on missing support")
    failure = _object(scheduler["failure_handling"], "scheduler_contract.failure_handling")
    _exact_keys(
        failure,
        {
            "crash_or_digest_mismatch",
            "infrastructure_failure",
            "replacement_or_backfill",
            "resource_ceiling",
        },
        "scheduler_contract.failure_handling",
    )
    if failure != {
        "crash_or_digest_mismatch": ("halt_the_task_cluster_and_preserve_all_committed_history"),
        "infrastructure_failure": (
            "record_the_typed_observation_and_continue_only_if_the_frozen_policy_"
            "offers_a_next_action"
        ),
        "replacement_or_backfill": False,
        "resource_ceiling": ("halt_without_replacement_and_preserve_the_partial_frame"),
    }:
        raise ProtocolError("scheduler cannot replace or backfill failed tasks")
    operational = _object(
        scheduler["operational_requirements"],
        "scheduler_contract.operational_requirements",
    )
    expected_operational = {
        "aggregate_resource_and_partial_frame_runtime": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "signed_resource_reservation_and_settlement_core_preserves_"
                "overruns_and_reports_local_committed_usage_bootstrap_coverage_"
                "deviations_and_halt_state_but_no_populated_records_activation_"
                "calendar_acquisition_cost_join_or_trusted_partial_frame_compiler_"
                "exists"
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
                "signed_bootstrap_curator_and_resource_record_core_plus_digest_"
                "pinned_semantic_export_reaudit_exists_but_no_human_adjudication_"
                "records_populated_stream_frozen_production_roles_external_"
                "checkpoint_or_cross_ledger_join_exists"
            ),
        },
        "trusted_study_bundle_compiler": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "behavior_and_label_trajectories_are_separated_and_the_scientific_"
                "export_is_digest_pinned_and_semantically_reauditable_but_the_"
                "structural_compiler_does_not_join_the_unpopulated_scientific_"
                "ledger_or_authenticate_scientific_inputs"
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
    if operational != expected_operational:
        raise ProtocolError("scheduler operational blockers differ")
    implementation = _object(scheduler["implementation"], "scheduler_contract.implementation")
    _exact_keys(
        implementation,
        {
            "blocking",
            "scheduler",
            "proposal_policy",
            "ledger",
            "scientific_ledger",
            "corpus_contract",
            "evaluation_contract",
            "metrics_source",
            "dispatcher",
            "structural_release_bundle_compiler",
            "completed_acquisition_validator",
            "status",
        },
        "scheduler_contract.implementation",
    )
    scheduler_source = _object(
        implementation["scheduler"],
        "scheduler_contract.implementation.scheduler",
    )
    _exact_keys(
        scheduler_source,
        {"logical_path", "sha256"},
        "scheduler_contract.implementation.scheduler",
    )
    proposal_source = _object(
        implementation["proposal_policy"],
        "scheduler_contract.implementation.proposal_policy",
    )
    _exact_keys(
        proposal_source,
        {
            "config_sha256",
            "logical_path",
            "schema_version",
            "sha256",
            "version",
        },
        "scheduler_contract.implementation.proposal_policy",
    )
    ledger_source = _object(
        implementation["ledger"],
        "scheduler_contract.implementation.ledger",
    )
    _exact_keys(
        ledger_source,
        {"logical_path", "schema_version", "scope", "sha256"},
        "scheduler_contract.implementation.ledger",
    )
    scientific_ledger_source = _object(
        implementation["scientific_ledger"],
        "scheduler_contract.implementation.scientific_ledger",
    )
    _exact_keys(
        scientific_ledger_source,
        {"logical_path", "profile", "schema_version", "scope", "sha256"},
        "scheduler_contract.implementation.scientific_ledger",
    )
    corpus_source = _object(
        implementation["corpus_contract"],
        "scheduler_contract.implementation.corpus_contract",
    )
    _exact_keys(
        corpus_source,
        {"logical_path", "profile", "schema_version", "sha256"},
        "scheduler_contract.implementation.corpus_contract",
    )
    evaluation_source = _object(
        implementation["evaluation_contract"],
        "scheduler_contract.implementation.evaluation_contract",
    )
    _exact_keys(
        evaluation_source,
        {"logical_path", "profile", "schema_version", "sha256"},
        "scheduler_contract.implementation.evaluation_contract",
    )
    metrics_source = _object(
        implementation["metrics_source"],
        "scheduler_contract.implementation.metrics_source",
    )
    _exact_keys(
        metrics_source,
        {"logical_path", "sha256"},
        "scheduler_contract.implementation.metrics_source",
    )
    dispatcher_source = _object(
        implementation["dispatcher"],
        "scheduler_contract.implementation.dispatcher",
    )
    _exact_keys(
        dispatcher_source,
        {"logical_path", "sha256"},
        "scheduler_contract.implementation.dispatcher",
    )
    release_bundle_source = _object(
        implementation["structural_release_bundle_compiler"],
        "scheduler_contract.implementation.structural_release_bundle_compiler",
    )
    _exact_keys(
        release_bundle_source,
        {"logical_path", "profile", "schema_version", "sha256", "trust_model"},
        "scheduler_contract.implementation.structural_release_bundle_compiler",
    )
    completed_validator = _object(
        implementation["completed_acquisition_validator"],
        "scheduler_contract.implementation.completed_acquisition_validator",
    )
    _exact_keys(
        completed_validator,
        {"entrypoint", "logical_path", "sha256"},
        "scheduler_contract.implementation.completed_acquisition_validator",
    )
    if (
        implementation["blocking"] is not True
        or scheduler_source
        != {
            "logical_path": SCHEDULER_IMPLEMENTATION_RELATIVE.as_posix(),
            "sha256": _digest(_read_bytes(root, SCHEDULER_IMPLEMENTATION_RELATIVE)),
        }
        or proposal_source
        != {
            "config_sha256": PROPOSAL_POLICY_CONFIG_SHA256,
            "logical_path": PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE.as_posix(),
            "schema_version": PROPOSAL_POLICY_SCHEMA_VERSION,
            "sha256": _digest(_read_bytes(root, PROPOSAL_POLICY_IMPLEMENTATION_RELATIVE)),
            "version": PROPOSAL_POLICY_VERSION,
        }
        or ledger_source
        != {
            "logical_path": LEDGER_IMPLEMENTATION_RELATIVE.as_posix(),
            "schema_version": LEDGER_SCHEMA_VERSION,
            "scope": "single_host_local_durable_filesystem",
            "sha256": _digest(_read_bytes(root, LEDGER_IMPLEMENTATION_RELATIVE)),
        }
        or scientific_ledger_source
        != {
            "logical_path": SCIENTIFIC_LEDGER_IMPLEMENTATION_RELATIVE.as_posix(),
            "profile": "SIGNED_BOOTSTRAP_CURATOR_RESOURCE_EXPORT_AUDIT_CORE",
            "schema_version": SCIENTIFIC_LEDGER_SCHEMA_VERSION,
            "scope": "single_host_local_sqlite_digest_pinned_export_unanchored",
            "sha256": _digest(_read_bytes(root, SCIENTIFIC_LEDGER_IMPLEMENTATION_RELATIVE)),
        }
        or corpus_source
        != {
            "logical_path": CORPUS_IMPLEMENTATION_RELATIVE.as_posix(),
            "profile": "DETERMINISTIC_LABEL_EVIDENCE_PLUS_SEPARATE_RANDOMIZED_BEHAVIOR",
            "schema_version": CORPUS_SCHEMA_VERSION,
            "sha256": _digest(_read_bytes(root, CORPUS_IMPLEMENTATION_RELATIVE)),
        }
        or evaluation_source
        != {
            "logical_path": EVALUATION_IMPLEMENTATION_RELATIVE.as_posix(),
            "profile": "TARGET_POLICY_JOINED_TO_DISTINCT_BEHAVIOR_LOGGER",
            "schema_version": EVALUATION_SCHEMA_VERSION,
            "sha256": _digest(_read_bytes(root, EVALUATION_IMPLEMENTATION_RELATIVE)),
        }
        or metrics_source
        != {
            "logical_path": METRICS_IMPLEMENTATION_RELATIVE.as_posix(),
            "sha256": _digest(_read_bytes(root, METRICS_IMPLEMENTATION_RELATIVE)),
        }
        or dispatcher_source
        != {
            "logical_path": DISPATCHER_IMPLEMENTATION_RELATIVE.as_posix(),
            "sha256": _digest(_read_bytes(root, DISPATCHER_IMPLEMENTATION_RELATIVE)),
        }
        or release_bundle_source
        != {
            "logical_path": RELEASE_BUNDLE_IMPLEMENTATION_RELATIVE.as_posix(),
            "profile": "STRUCTURAL",
            "schema_version": "verification-gap-study-bundle-0.2.0",
            "sha256": _digest(_read_bytes(root, RELEASE_BUNDLE_IMPLEMENTATION_RELATIVE)),
            "trust_model": "out_of_band_sha256_v1",
        }
        or completed_validator
        != {
            "entrypoint": PROTOCOL_RESULT_VALIDATION_CONTRACT.rsplit(".", 1)[1],
            "logical_path": ACQUISITION_ORCHESTRATOR_RELATIVE.as_posix(),
            "sha256": _digest(_read_bytes(root, ACQUISITION_ORCHESTRATOR_RELATIVE)),
        }
        or implementation["status"]
        != (
            "scheduler_bootstrap_proposal_ledger_dispatcher_structural_bundle_"
            "scientific_export_audit_and_split_corpus_evaluation_contracts_"
            "available_external_scientific_activation_inputs_missing"
        )
    ):
        raise ProtocolError("scheduler and durable-ledger source bindings differ")
    return {
        "aggregate resource reservation settlement and partial-frame reporting",
        "signed deterministic bootstrap receipt acquisition",
        "durable exclusive scheduler ledger and write-ahead dispatcher",
        "durable bootstrap curator adjudication substrate and resource ledgers",
        "trusted ledger-to-corpus terminal-outcome and cost compiler",
        "typed acquisition-result persistence and action-spec preimages",
    }


def _validate_execution_freeze(
    root: pathlib.Path,
    execution: dict[str, Any],
) -> set[str]:
    _exact_keys(
        execution,
        {
            "schema_version",
            "study_id",
            "status",
            "scope",
            "canonical_dataset",
            "harness",
            "platform",
            "timeouts_seconds",
            "container_limits",
            "replication",
            "cache_accounting",
            "unavailable_bindings",
        },
        "execution_freeze",
    )
    if (
        execution["schema_version"] != EXECUTION_SCHEMA_VERSION
        or execution["study_id"] != STUDY_ID
        or execution["status"] != "blocked_missing_external_execution_identities"
    ):
        raise ProtocolError("execution freeze identity or status differs")
    _validate_scope(execution["scope"], "execution_freeze.scope")
    dataset = _object(execution["canonical_dataset"], "execution_freeze.canonical_dataset")
    _exact_keys(
        dataset, {"parquet_bytes", "parquet_sha256", "provider", "revision"}, "canonical_dataset"
    )
    independent_evidence = _read_json(root, EVIDENCE_RELATIVE)
    sources = _object(independent_evidence["sources"], "independent evidence sources")
    canonical_source = _object(
        sources["canonical_dataset"],
        "independent evidence canonical dataset",
    )
    if dataset != {
        "provider": canonical_source.get("dataset_id"),
        "revision": canonical_source.get("revision"),
        "parquet_bytes": canonical_source.get("bytes"),
        "parquet_sha256": canonical_source.get("sha256"),
    }:
        raise ProtocolError("execution canonical-dataset identity differs")
    harness = _object(execution["harness"], "execution_freeze.harness")
    _exact_keys(harness, {"commit", "repository", "tree"}, "execution harness")
    independent_harness = _object(
        independent_evidence["harness"],
        "independent evidence harness",
    )
    if harness != {
        "commit": independent_harness.get("commit"),
        "repository": f"https://github.com/{independent_harness.get('repository')}",
        "tree": "81083caddb04c76896805b38eaa4e43ca3ce2d63",
    }:
        raise ProtocolError("execution harness identity differs")
    platform = _object(execution["platform"], "execution_freeze.platform")
    _exact_keys(
        platform,
        {
            "architecture",
            "container_runtime",
            "operating_system",
            "primary_substrate",
            "secondary_substrate",
        },
        "execution platform",
    )
    architecture = _object(platform["architecture"], "execution target architecture")
    _validate_unavailable_binding(
        architecture,
        "execution target architecture",
        expected_keys={"value"},
    )
    if architecture["value"] is not None:
        raise ProtocolError("unavailable execution architecture cannot claim a value")
    expected_platform = {
        "architecture": architecture,
        "container_runtime": "docker",
        "operating_system": "linux",
        "primary_substrate": "official_per_task_container",
        "secondary_substrate": "container_free_same_architecture",
    }
    if platform != expected_platform:
        raise ProtocolError("execution target platform differs")
    timeouts = _object(execution["timeouts_seconds"], "execution_freeze.timeouts_seconds")
    expected_timeouts = {
        "environment_build": 3600,
        "full_execution": 1800,
        "full_execution_repeat": 1800,
        "image_pull": 1800,
        "oracle_hardening": 1800,
        "patch_application": 300,
        "process_cleanup": 120,
        "signal_grace": 15,
        "targeted_execution": 900,
    }
    if timeouts != expected_timeouts:
        raise ProtocolError("execution timeout freeze differs")
    container = _object(execution["container_limits"], "execution_freeze.container_limits")
    _exact_keys(
        container,
        {
            "capabilities",
            "cpu_count",
            "log_driver",
            "memory_bytes",
            "network",
            "no_new_privileges",
            "output_capture_bytes_per_stream",
            "pids",
            "pull_policy",
            "read_only_root",
            "tmpfs_bytes",
            "workspace_mount",
        },
        "execution container limits",
    )
    if (
        container["capabilities"] != []
        or container["cpu_count"] != 4
        or container["memory_bytes"] != 8589934592
        or container["network"] != "none"
        or container["no_new_privileges"] is not True
        or container["pids"] != 1024
        or container["read_only_root"] is not True
    ):
        raise ProtocolError("execution isolation/resource limits differ")
    replication = _object(execution["replication"], "execution_freeze.replication")
    _exact_keys(
        replication,
        {
            "disagreement_attempt",
            "fresh_worktree_per_attempt",
            "required_attempts",
            "same_image_dependency_test_and_argv_across_attempts",
        },
        "execution replication",
    )
    if replication != {
        "disagreement_attempt": 3,
        "fresh_worktree_per_attempt": True,
        "required_attempts": 2,
        "same_image_dependency_test_and_argv_across_attempts": True,
    }:
        raise ProtocolError("execution replication contract differs")
    cache = _object(execution["cache_accounting"], "execution_freeze.cache_accounting")
    _exact_keys(
        cache,
        {
            "cold_image_build_and_pull_reported_separately",
            "dependency_cache_state_recorded_per_attempt",
            "warm_execution_never_includes_unreported_setup",
        },
        "execution cache accounting",
    )
    if not all(value is True for value in cache.values()):
        raise ProtocolError("execution cache accounting must be complete")

    unavailable = _object(
        execution["unavailable_bindings"], "execution_freeze.unavailable_bindings"
    )
    _exact_keys(
        unavailable,
        {
            "docker_daemon_and_provisioner",
            "per_task_dependency_lock_manifest",
            "per_task_execution_spec_manifest",
            "per_task_image_digest_manifest",
        },
        "execution unavailable bindings",
    )
    docker = _object(unavailable["docker_daemon_and_provisioner"], "docker binding")
    _validate_unavailable_binding(
        docker,
        "docker binding",
        expected_keys={"attestation_sha256", "identity"},
    )
    if docker["attestation_sha256"] is not None or docker["identity"] is not None:
        raise ProtocolError("unavailable Docker binding cannot contain partial identity")
    for name in (
        "per_task_dependency_lock_manifest",
        "per_task_execution_spec_manifest",
        "per_task_image_digest_manifest",
    ):
        binding = _object(unavailable[name], f"execution unavailable {name}")
        _validate_unavailable_binding(
            binding,
            f"execution unavailable {name}",
            expected_keys={"bytes", "logical_path", "sha256"},
        )
        if any(binding[field] is not None for field in ("bytes", "logical_path", "sha256")):
            raise ProtocolError(f"unavailable {name} cannot contain partial identity")
    return {
        "Docker daemon and provisioner attestation",
        "execution target architecture",
        "per-task dependency-lock manifest",
        "per-task execution-spec manifest",
        "per-task image-digest manifest",
    }


def _validate_adjudication_plan(
    root: pathlib.Path,
    adjudication: dict[str, Any],
) -> set[str]:
    _exact_keys(
        adjudication,
        {
            "schema_version",
            "study_id",
            "status",
            "scope",
            "packet_contract",
            "blinding",
            "label_contract",
            "aggregation",
            "available_bindings",
            "unavailable_bindings",
        },
        "adjudication_plan",
    )
    if (
        adjudication["schema_version"] != ADJUDICATION_SCHEMA_VERSION
        or adjudication["study_id"] != STUDY_ID
        or adjudication["status"] != "packet_generator_available_custodian_and_reviewers_blocking"
    ):
        raise ProtocolError("adjudication plan identity or status differs")
    _validate_scope(adjudication["scope"], "adjudication_plan.scope")
    packet = _object(adjudication["packet_contract"], "adjudication_plan.packet_contract")
    _exact_keys(
        packet,
        {
            "directional_evidence_status_omitted",
            "included",
            "packet_manifest_schema_version",
            "packet_schema_version",
            "prohibited",
            "raw_packet_sha256_required",
            "same_task_context_across_its_three_candidate_packets",
        },
        "adjudication packet contract",
    )
    if (
        packet["packet_schema_version"] != "prospective-pilot-review-packet-0.1.0"
        or packet["packet_manifest_schema_version"]
        != "prospective-pilot-review-packet-manifest-0.2.0"
        or packet["directional_evidence_status_omitted"] is not True
        or packet["raw_packet_sha256_required"] is not True
        or packet["same_task_context_across_its_three_candidate_packets"] is not True
    ):
        raise ProtocolError("adjudication packet identity/binding differs")
    prohibited = _array(packet["prohibited"], "adjudication packet prohibited fields")
    required_prohibited = {
        "submission_name",
        "model_name",
        "hosted_outcome",
        "gold_patch",
        "official_resolved_label",
        "router_terminal_decision",
        "other_reviewer_labels",
        "candidate_priority_order",
        "prospective_analysis_outputs",
    }
    if set(prohibited) != required_prohibited or len(prohibited) != len(required_prohibited):
        raise ProtocolError("adjudication packet prohibited-field set differs")
    blinding = _object(adjudication["blinding"], "adjudication_plan.blinding")
    _exact_keys(
        blinding,
        {
            "blind_reviewers_to_each_other_until_all_initial_labels_are_committed",
            "breach_action",
            "candidate_and_model_masking_required",
            "opaque_map_access",
            "reviewer_conflict_attestation_required",
        },
        "adjudication blinding",
    )
    if (
        blinding["blind_reviewers_to_each_other_until_all_initial_labels_are_committed"] is not True
        or blinding["candidate_and_model_masking_required"] is not True
        or blinding["opaque_map_access"] != "custodian_only"
        or blinding["reviewer_conflict_attestation_required"] is not True
    ):
        raise ProtocolError("adjudication blinding contract differs")
    labels = _object(adjudication["label_contract"], "adjudication_plan.label_contract")
    _exact_keys(
        labels,
        {
            "candidate_correctness",
            "candidate_is_conditional_on_task_validity",
            "evidence_validity",
            "evidence_validity_is_per_event",
            "execution_is_adjudication",
            "task_validity",
        },
        "adjudication label contract",
    )
    if (
        labels["task_validity"] != ["valid", "invalid", "indeterminate"]
        or labels["candidate_correctness"]
        != ["correct", "incorrect", "indeterminate", "not_applicable"]
        or labels["evidence_validity"] != ["valid", "invalid", "indeterminate"]
        or labels["candidate_is_conditional_on_task_validity"] is not True
        or labels["evidence_validity_is_per_event"] is not True
        or labels["execution_is_adjudication"] is not False
    ):
        raise ProtocolError("adjudication label contract differs")
    aggregation = _object(adjudication["aggregation"], "adjudication_plan.aggregation")
    _exact_keys(
        aggregation,
        {
            "agreement",
            "candidate_when_task_indeterminate",
            "candidate_when_task_invalid",
            "determinate_label",
            "disagreement",
            "minimum_agreement",
            "minimum_paired_ready_reviewers",
            "requested_independent_initial_reviewers",
            "reviewer_identity_is_never_a_correctness_feature",
        },
        "adjudication aggregation",
    )
    if (
        aggregation["minimum_agreement"] != 0.8
        or aggregation["minimum_paired_ready_reviewers"] != 2
        or aggregation["requested_independent_initial_reviewers"] != 3
        or aggregation["candidate_when_task_invalid"] != "not_applicable"
        or aggregation["candidate_when_task_indeterminate"] != "indeterminate"
        or aggregation["reviewer_identity_is_never_a_correctness_feature"] is not True
        or aggregation["disagreement"]
        != "retain_every_initial_label_and_emit_indeterminate_without_tie_breaking"
    ):
        raise ProtocolError("adjudication aggregation rule differs")

    available = _object(
        adjudication["available_bindings"],
        "adjudication available bindings",
    )
    _exact_keys(
        available,
        {"frame_manifest", "packet_generator"},
        "adjudication available bindings",
    )
    for name, relative in (
        ("frame_manifest", FRAME_RELATIVE),
        ("packet_generator", REVIEW_PACKET_RELATIVE),
    ):
        binding = _object(available[name], f"adjudication available {name}")
        _exact_keys(
            binding,
            {"bytes", "logical_path", "sha256", "status"},
            f"adjudication available {name}",
        )
        payload = _read_bytes(root, relative)
        if binding != {
            "bytes": len(payload),
            "logical_path": relative.as_posix(),
            "sha256": _digest(payload),
            "status": "available",
        }:
            raise ProtocolError(f"adjudication available {name} binding differs")

    unavailable = _object(adjudication["unavailable_bindings"], "adjudication unavailable bindings")
    _exact_keys(
        unavailable, {"opaque_map_custodian", "reviewers"}, "adjudication unavailable bindings"
    )
    custodian = _object(unavailable["opaque_map_custodian"], "opaque-map custodian")
    _validate_unavailable_binding(custodian, "opaque-map custodian", expected_keys={"identifier"})
    if custodian["identifier"] is not None:
        raise ProtocolError("unavailable opaque-map custodian cannot have an identity")
    reviewers = _array(unavailable["reviewers"], "adjudication reviewers")
    if len(reviewers) != 3:
        raise ProtocolError("adjudication plan must preserve exactly three reviewer slots")
    for index, raw in enumerate(reviewers, start=1):
        reviewer = _object(raw, f"adjudication reviewer {index}")
        _exact_keys(
            reviewer,
            {
                "conflict_attestation_sha256",
                "identifier",
                "independence_attestation_sha256",
                "slot",
                "status",
            },
            f"adjudication reviewer {index}",
        )
        if reviewer != {
            "conflict_attestation_sha256": None,
            "identifier": None,
            "independence_attestation_sha256": None,
            "slot": index,
            "status": "unavailable",
        }:
            raise ProtocolError(
                "reviewer identities/attestations must remain explicitly unavailable"
            )
    return {
        "opaque-map custodian identity",
        "reviewer identities and independence attestations",
    }


def _validate_target_policy_manifest(
    root: pathlib.Path,
    manifest: dict[str, Any],
    expected_policies: Mapping[str, tuple[str, bool]],
) -> None:
    _exact_keys(
        manifest,
        {
            "schema_version",
            "study_id",
            "status",
            "implementation",
            "input_contract",
            "policies",
            "weight_contract",
            "claim_boundary",
        },
        "target_policy_manifest",
    )
    if (
        manifest["schema_version"] != "prospective-pilot-target-policy-manifest-0.1.0"
        or manifest["study_id"] != STUDY_ID
        or manifest["status"] != "fixed_descriptive_ope_implementation_no_performance_claim"
        or manifest["claim_boundary"]
        != (
            "fixed likelihood and diagnostic implementation only; no learned "
            "policy, calibration, causal validity, or positive performance claim"
        )
    ):
        raise ProtocolError("target-policy manifest identity or claim boundary differs")
    implementation = _object(
        manifest["implementation"],
        "target-policy manifest implementation",
    )
    _exact_keys(
        implementation,
        {"bytes", "logical_path", "sha256", "status"},
        "target-policy manifest implementation",
    )
    source = _read_bytes(root, TARGET_POLICY_IMPLEMENTATION_RELATIVE)
    if implementation != {
        "bytes": len(source),
        "logical_path": TARGET_POLICY_IMPLEMENTATION_RELATIVE.as_posix(),
        "sha256": _digest(source),
        "status": "available",
    }:
        raise ProtocolError("target-policy implementation source binding differs")
    inputs = _object(manifest["input_contract"], "target-policy input contract")
    _exact_keys(
        inputs,
        {"allowed", "prohibited", "scheduler_validation_required"},
        "target-policy input contract",
    )
    if (
        set(_array(inputs["allowed"], "target-policy allowed inputs"))
        != {
            "validated_pre_action_candidate_round_state",
            "complete_available_action_catalog",
            "logged_behavior_distribution_and_chosen_action",
            "opaque_candidate_position_and_fixed_task_chain",
        }
        or set(_array(inputs["prohibited"], "target-policy prohibited inputs"))
        != {
            "adjudication",
            "hosted_outcome",
            "reward",
            "future_evidence",
            "model_or_submission_identity",
        }
        or inputs["scheduler_validation_required"] is not True
    ):
        raise ProtocolError("target-policy deployable input boundary differs")
    policies = _array(manifest["policies"], "target-policy manifest policies")
    decoded: dict[str, tuple[str, bool]] = {}
    for index, raw in enumerate(policies):
        policy = _object(raw, f"target-policy manifest policy {index}")
        _exact_keys(
            policy,
            {"id", "rule", "semantic_required"},
            f"target-policy manifest policy {index}",
        )
        policy_id = _string(policy["id"], f"target-policy manifest policy {index}.id")
        if policy_id in decoded or not isinstance(policy["semantic_required"], bool):
            raise ProtocolError("target-policy manifest policies are invalid or duplicated")
        decoded[policy_id] = (
            _string(policy["rule"], f"target-policy manifest policy {index}.rule"),
            policy["semantic_required"],
        )
    if decoded != dict(expected_policies):
        raise ProtocolError("target-policy manifest differs from analysis-plan policies")
    weights = _object(manifest["weight_contract"], "target-policy weight contract")
    if weights != {
        "joint_unit": "complete_task_cluster_history_across_all_three_candidate_chains",
        "support_violation": (
            "positive_target_probability_for_an_action_absent_from_logged_behavior_support"
        ),
        "support_violating_weight": None,
        "zero_target_probability_weight": 0.0,
        "clipping_or_trimming": False,
    }:
        raise ProtocolError("target-policy weight contract differs")


def _validate_analysis_plan(
    root: pathlib.Path,
    analysis: dict[str, Any],
) -> set[str]:
    _exact_keys(
        analysis,
        {
            "schema_version",
            "study_id",
            "status",
            "claim_scope",
            "analysis_population",
            "target_policies",
            "estimands",
            "off_policy_evaluation",
            "implemented_estimators",
            "uncertainty",
            "mandatory_outputs",
            "available_bindings",
        },
        "analysis_plan",
    )
    if (
        analysis["schema_version"] != ANALYSIS_SCHEMA_VERSION
        or analysis["study_id"] != STUDY_ID
        or analysis["status"] != "fixed_descriptive_implementations_available"
        or analysis["claim_scope"] != "descriptive_development_analysis_only_no_h1_through_h6"
    ):
        raise ProtocolError("analysis plan identity, status, or claim scope differs")
    population = _object(analysis["analysis_population"], "analysis_plan.analysis_population")
    _exact_keys(
        population,
        {
            "candidate_count",
            "cluster_unit",
            "candidates_per_task",
            "excluded_task_clusters",
            "future_task_clusters",
            "repository_count",
            "repository_stratum_rule",
            "replacement_allowed",
            "repository_generalization",
        },
        "analysis population",
    )
    if (
        population["candidate_count"] != 66
        or population["cluster_unit"] != "task"
        or population["candidates_per_task"] != 3
        or population["excluded_task_clusters"] != PRE_FREEZE_TASK_IDS
        or population["future_task_clusters"] != 22
        or population["repository_count"] != 4
        or population["repository_stratum_rule"] != "task_id_prefix_before_double_underscore"
        or population["replacement_allowed"] is not False
        or population["repository_generalization"] != "forbidden"
    ):
        raise ProtocolError("analysis population is not the cluster-respecting 22-task frame")
    target_policies = _array(analysis["target_policies"], "analysis_plan.target_policies")
    expected_policy_contract = {
        "behavior-mixture-v1": (
            "the_exact_logged_0.5_preferred_plus_0.5_uniform_behavior_policy",
            True,
        ),
        "always-full-repeat-v1": (
            "full_execution_then_fresh_worktree_repeat_then_frozen_terminal_rule_for_every_candidate",
            False,
        ),
        "static-targeted-full-v1": (
            "deterministic_static_then_targeted_then_full_then_repeat_then_frozen_terminal_rule",
            False,
        ),
        "conservative-v1-preferred-v1": (
            "follow_the_bound_conservative_v1_preferred_action_with_no_exploration",
            True,
        ),
        "semantic-only-v1": (
            "semantic_once_then_the_frozen_terminal_rule_without_runtime_evidence",
            True,
        ),
        "hash-priority-no-runtime-v1": (
            "select_the_first_candidate_in_frozen_opaque_candidate_order_without_runtime_evidence",
            False,
        ),
    }
    decoded_policy_contract: dict[str, tuple[str, bool]] = {}
    for index, raw in enumerate(target_policies):
        policy = _object(raw, f"analysis target policy {index}")
        _exact_keys(
            policy,
            {"id", "rule", "semantic_required", "status"},
            f"analysis target policy {index}",
        )
        policy_id = _string(policy["id"], f"analysis target policy {index}.id")
        if policy_id in decoded_policy_contract:
            raise ProtocolError("target-policy IDs cannot be duplicated")
        rule = _string(policy["rule"], f"analysis target policy {index}.rule")
        if not isinstance(policy["semantic_required"], bool):
            raise ProtocolError("target-policy semantic_required must be boolean")
        if policy["status"] != "implemented_fixed_descriptive":
            raise ProtocolError("target-policy implementation status differs")
        decoded_policy_contract[policy_id] = (
            rule,
            policy["semantic_required"],
        )
    if decoded_policy_contract != expected_policy_contract:
        raise ProtocolError("frozen target-policy set differs")
    estimands = _object(analysis["estimands"], "analysis_plan.estimands")
    _exact_keys(estimands, {"primary", "secondary", "unsafe_accept"}, "analysis estimands")
    if estimands["primary"] != (
        "accepted_set_false_accept_risk_with_coverage_and_cost_reported_separately"
    ):
        raise ProtocolError("analysis primary estimand differs")
    _array(estimands["secondary"], "analysis secondary estimands")
    _string(estimands["unsafe_accept"], "analysis unsafe-accept definition")
    ope = _object(analysis["off_policy_evaluation"], "analysis_plan.off_policy_evaluation")
    _exact_keys(
        ope,
        {
            "effective_sample_size",
            "estimate_release_rule",
            "joint_weight",
            "minimum_logged_action_probability",
            "primary_weight_handling",
            "ratio_estimator",
            "scheduler_probability",
            "support_unit",
        },
        "analysis OPE",
    )
    if (
        ope["minimum_logged_action_probability"] != 0.5 / 7
        or ope["scheduler_probability"] != 1.0
        or ope["primary_weight_handling"] != "no_clipping_no_trimming"
        or ope["support_unit"] != "complete_task_cluster_history_across_all_three_candidate_chains"
        or ope["estimate_release_rule"]
        != "omit_when_any_support_violation_or_effective_sample_size_below_10"
        or ope["ratio_estimator"]
        != (
            "sum_task_weight_times_accept_times_unsafe_indicator_divided_by_"
            "sum_task_weight_times_accept"
        )
    ):
        raise ProtocolError("analysis OPE support/weight contract differs")
    estimators = _object(
        analysis["implemented_estimators"],
        "analysis implemented estimators",
    )
    if estimators != {
        "sequential_importance_sampling": {
            "availability": "implemented",
            "confidence_interval": "not_implemented",
            "cross_fitting": "not_applicable_no_nuisance_model",
            "point_estimate": "self_normalized_accepted_set_ratio",
            "suppression": (
                "any_support_violation_or_effective_sample_size_below_10_or_"
                "empty_weighted_accepted_set"
            ),
            "weight_handling": "no_clipping_no_trimming",
        },
        "doubly_robust": {
            "availability": "not_implemented_not_claimed",
            "nuisance_model": None,
            "cross_fitting": None,
        },
        "learned_or_calibrated_policy": False,
    }:
        raise ProtocolError("analysis implemented-estimator boundary differs")
    uncertainty = _object(analysis["uncertainty"], "analysis_plan.uncertainty")
    _exact_keys(
        uncertainty,
        {
            "confidence_level",
            "exact_binomial_bound",
            "hypothesis_tests",
            "primary_interval",
            "repository_cluster_asymptotics",
            "sensitivity",
        },
        "analysis uncertainty",
    )
    if (
        uncertainty["confidence_level"] != 0.95
        or uncertainty["exact_binomial_bound"] != "full_coverage_iid_reference_only"
        or uncertainty["hypothesis_tests"] != "none"
        or uncertainty["repository_cluster_asymptotics"] != "forbidden_with_four_repositories"
    ):
        raise ProtocolError("analysis uncertainty limitations differ")
    sensitivity = _object(uncertainty["sensitivity"], "analysis uncertainty sensitivity")
    _exact_keys(
        sensitivity,
        {"bootstrap_replicates", "bootstrap_seed_sha256", "method"},
        "analysis sensitivity",
    )
    if (
        sensitivity["bootstrap_replicates"] != 10000
        or sensitivity["method"] != "resample_tasks_within_each_fixed_repository_stratum"
    ):
        raise ProtocolError("analysis sensitivity plan differs")
    _sha256_value(sensitivity["bootstrap_seed_sha256"], "analysis bootstrap seed")
    outputs = _array(analysis["mandatory_outputs"], "analysis mandatory outputs")
    if len(outputs) != len(set(outputs)) or not {
        "raw_task_cluster_rows",
        "all_abstentions_and_failures",
        "support_and_overlap_diagnostics",
        "task_weights_and_effective_sample_size",
        "risk_coverage_cost_frontier",
        "deviation_log",
    }.issubset(set(outputs)):
        raise ProtocolError("analysis mandatory outputs are incomplete or duplicated")
    available = _object(analysis["available_bindings"], "analysis available bindings")
    _exact_keys(
        available,
        {"analysis_implementation", "target_policy_implementation_manifest"},
        "analysis available bindings",
    )
    for name, relative in (
        ("analysis_implementation", ANALYSIS_IMPLEMENTATION_RELATIVE),
        (
            "target_policy_implementation_manifest",
            TARGET_POLICY_MANIFEST_RELATIVE,
        ),
    ):
        binding = _object(available[name], f"analysis available {name}")
        _exact_keys(
            binding,
            {"bytes", "logical_path", "sha256", "status"},
            f"analysis available {name}",
        )
        payload = _read_bytes(root, relative)
        if binding != {
            "bytes": len(payload),
            "logical_path": relative.as_posix(),
            "sha256": _digest(payload),
            "status": "available",
        }:
            raise ProtocolError(f"analysis available {name} binding differs")
    target_manifest_bytes = _read_bytes(root, TARGET_POLICY_MANIFEST_RELATIVE)
    try:
        target_manifest = _object(
            strict_json_loads(target_manifest_bytes.decode("utf-8")),
            "target-policy implementation manifest",
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolError(f"invalid target-policy implementation manifest: {exc}") from exc
    _validate_target_policy_manifest(
        root,
        target_manifest,
        expected_policy_contract,
    )
    return set()


def _validate_configuration_bundle(
    root: pathlib.Path,
    protocol: dict[str, Any],
) -> tuple[dict[str, str], set[str]]:
    payloads = {role: _read_bytes(root, relative) for role, relative in CONFIG_PATHS.items()}
    configs = {
        role: _object(strict_json_loads(payload.decode("utf-8")), role)
        for role, payload in payloads.items()
    }
    blockers: set[str] = set()
    blockers.update(_validate_resource_ceiling(configs["resource_ceiling"]))
    blockers.update(_validate_collection_policy(root, configs["collection_policy"]))
    blockers.update(_validate_scheduler_contract(root, configs["scheduler_contract"]))
    blockers.update(_validate_execution_freeze(root, configs["execution_config"]))
    blockers.update(_validate_adjudication_plan(root, configs["adjudication_config"]))
    blockers.update(_validate_analysis_plan(root, configs["analysis_plan"]))
    blockers.update(_validate_frame_manifest(configs["frame_manifest"]))
    if blockers != REQUIRED_ACTIVATION_BLOCKERS:
        raise ProtocolError(
            "configuration-derived activation blockers differ: "
            f"missing={sorted(REQUIRED_ACTIVATION_BLOCKERS - blockers)}, "
            f"unknown={sorted(blockers - REQUIRED_ACTIVATION_BLOCKERS)}"
        )

    binding = _object(protocol.get("activation_configuration"), "protocol.activation_configuration")
    _exact_keys(binding, {"schema_version", "objects"}, "protocol.activation_configuration")
    if binding["schema_version"] != "prospective-pilot-activation-configuration-0.1.0":
        raise ProtocolError("activation-configuration binding schema differs")
    objects = _array(binding["objects"], "protocol.activation_configuration.objects")
    seen: set[str] = set()
    for index, raw in enumerate(objects):
        item = _object(raw, f"activation configuration object {index}")
        _exact_keys(
            item, {"role", "logical_path", "bytes", "sha256"}, "activation configuration object"
        )
        role = _string(item["role"], f"activation configuration object {index}.role")
        if role in seen or role not in CONFIG_PATHS:
            raise ProtocolError("activation configuration roles must be exact and unique")
        seen.add(role)
        relative = CONFIG_PATHS[role]
        payload = payloads[role]
        if (
            item["logical_path"] != relative.as_posix()
            or item["bytes"] != len(payload)
            or item["sha256"] != _digest(payload)
        ):
            raise ProtocolError(f"activation configuration binding differs for {role}")
    if seen != set(CONFIG_PATHS):
        raise ProtocolError("activation configuration bundle is incomplete")

    resource = configs["resource_ceiling"]
    scheduler = configs["scheduler_contract"]
    analysis = configs["analysis_plan"]
    decisions = _object(resource["decision_limits"], "resource decision limits")
    chain = _object(scheduler["candidate_chain"], "scheduler candidate chain")
    if (
        decisions["maximum_candidate_chain_decisions"] != chain["maximum_decisions"]
        or decisions["maximum_nonterminal_policy_acquisitions_per_candidate"]
        != chain["maximum_nonterminal_acquisitions"]
    ):
        raise ProtocolError("resource and scheduler decision ceilings differ")
    ope = _object(analysis["off_policy_evaluation"], "analysis OPE")
    behavior = _object(configs["collection_policy"]["behavior_policy"], "collection behavior")
    if (
        ope["minimum_logged_action_probability"]
        != behavior["minimum_history_conditioned_propensity"]
    ):
        raise ProtocolError("analysis and collection propensity floors differ")
    return ({role: _digest(payload) for role, payload in payloads.items()}, blockers)


def _validate_protocol_claims(
    protocol: dict[str, Any],
    configuration_blockers: set[str],
) -> tuple[bool, tuple[str, ...]]:
    if protocol.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise ProtocolError("unsupported protocol schema_version")
    if protocol.get("study_id") != STUDY_ID:
        raise ProtocolError("protocol study_id differs")
    claim_scope = _object(protocol.get("claim_scope"), "protocol.claim_scope")
    if claim_scope.get("confirmatory") is not False:
        raise ProtocolError("development protocol cannot be confirmatory")
    if claim_scope.get("measurement_design") != MEASUREMENT_DESIGN:
        raise ProtocolError("protocol measurement-design boundary differs")
    if claim_scope.get("hypotheses_supported") != []:
        raise ProtocolError("development protocol must support no H1-H6 hypothesis claim")
    cannot_support = _array(claim_scope.get("cannot_support"), "claim_scope.cannot_support")
    if "evidence for hypotheses H1 through H6" not in cannot_support:
        raise ProtocolError("claim scope must explicitly reject H1-H6 evidence")
    frozen = _object(protocol.get("frozen_inputs"), "protocol.frozen_inputs")
    if (
        frozen.get("task_count") != 24
        or frozen.get("candidates_per_task") != 3
        or frozen.get("candidate_count") != 72
    ):
        raise ProtocolError("the 24-task/72-candidate descriptive frame must remain fixed")
    knowledge = _object(protocol.get("knowledge_boundary"), "protocol.knowledge_boundary")
    if (
        knowledge.get("pre_freeze_feasibility_task_ids") != PRE_FREEZE_TASK_IDS
        or knowledge.get("pre_freeze_evidence_allowed_in_prospective_or_ope_estimands") is not False
    ):
        raise ProtocolError("both feasibility tasks must remain excluded from prospective/OPE")

    behavior = _object(protocol.get("behavior_policy"), "protocol.behavior_policy")
    sampler = _object(behavior.get("sampler"), "behavior_policy.sampler")
    if sampler != {
        "id": CANONICAL_SAMPLER_ID,
        "version": CANONICAL_SAMPLER_VERSION,
        "implementation": "bench_cleanser.verification.policy_log.sample_behavior_action",
    }:
        raise ProtocolError("protocol sampler identity differs from the implementation")
    action_count = behavior.get("maximum_available_actions")
    if isinstance(action_count, bool) or not isinstance(action_count, int) or action_count <= 0:
        raise ProtocolError("maximum_available_actions must be a positive integer")
    exploration = behavior.get("exploration_mass")
    if isinstance(exploration, bool) or not isinstance(exploration, (int, float)):
        raise ProtocolError("exploration_mass must be numeric")
    expected_floor = float(exploration) / action_count
    if behavior.get("minimum_history_conditioned_propensity") != expected_floor:
        raise ProtocolError("declared propensity floor does not match behavior mixture")
    if behavior.get("disclosed_action_count") != 9:
        raise ProtocolError("the protocol must disclose the complete nine-action catalog")
    actions = _object(protocol.get("evidence_actions"), "protocol.evidence_actions")
    randomized = _array(actions.get("randomized_catalog"), "evidence_actions.randomized_catalog")
    if len(randomized) != action_count or not {"accept", "reject", "abstain"}.issubset(
        set(randomized)
    ):
        raise ProtocolError("randomized action catalog contradicts its declared size/terminals")
    if actions.get("disclosed_nonpolicy_action_ids") != [
        "hardening_curator",
        "static_bootstrap",
    ]:
        raise ProtocolError(
            "static bootstrap and curator hardening must remain disclosed outside randomization"
        )
    go_no_go = _object(protocol.get("go_no_go"), "protocol.go_no_go")
    requirements = _object(go_no_go.get("requirements"), "go_no_go.requirements")
    if requirements.get("minimum_observed_propensity") != expected_floor:
        raise ProtocolError("go/no-go propensity threshold contradicts policy support")

    power = _object(protocol.get("stopping_and_power"), "protocol.stopping_and_power")
    if power.get("zero_error_bound_interpretation") != BOUND_INTERPRETATION:
        raise ProtocolError("zero-error reference bound lacks its iid/full-coverage limitation")
    if (
        power.get("fixed_task_count") != 24
        or power.get("prehistory_excluded_task_count") != 2
        or power.get("remaining_future_task_count") != 22
        or power.get("zero_error_one_sided_95_upper_bound_at_24") != 0.11734615615494881
        or power.get("zero_error_one_sided_95_upper_bound_at_22") != 0.12730543165483876
        or "zero_error_one_sided_95_upper_bound_at_23" in power
    ):
        raise ProtocolError("stopping/power counts do not preserve the 24/22 frame split")

    readiness = _object(protocol.get("activation_readiness"), "protocol.activation_readiness")
    _exact_keys(
        readiness,
        {
            "ready",
            "missing",
            "external_freeze_receipt_required",
            "activation_command_policy",
        },
        "protocol.activation_readiness",
    )
    if not isinstance(readiness["ready"], bool):
        raise ProtocolError("activation_readiness.ready must be a boolean")
    missing_raw = _array(readiness["missing"], "activation_readiness.missing")
    if any(not isinstance(item, str) or not item for item in missing_raw):
        raise ProtocolError("activation blockers must be non-empty strings")
    if len(missing_raw) != len(set(missing_raw)):
        raise ProtocolError("activation blockers cannot contain duplicates")
    missing = tuple(sorted(missing_raw))
    if readiness["external_freeze_receipt_required"] is not True:
        raise ProtocolError("activation must require a clean-commit freeze receipt")
    if readiness["ready"] and missing:
        raise ProtocolError("activation cannot be ready while blockers remain")
    if not readiness["ready"] and set(missing) != configuration_blockers:
        raise ProtocolError("declared activation blockers differ from strict config state")
    if readiness["ready"] and configuration_blockers:
        raise ProtocolError("activation cannot be ready while a config remains unavailable")
    return readiness["ready"], missing


def _validate_protocol_prehistory_binding(
    protocol: dict[str, Any],
    prehistory_bytes: bytes,
    event_count: int,
    chain_head: str,
) -> None:
    binding = _object(protocol.get("prehistory"), "protocol.prehistory")
    _exact_keys(
        binding,
        {
            "required_record",
            "schema_version",
            "bytes",
            "sha256",
            "event_count",
            "chain_head_sha256",
            "excluded_task_clusters_for_prospective_or_ope_estimands",
            "replacement",
            "remaining_future_task_count",
            "all_24_tasks_may_be_reported_only_as_a_descriptive_development_frame",
        },
        "protocol.prehistory",
    )
    if binding["required_record"] != PREHISTORY_RELATIVE.as_posix():
        raise ProtocolError("protocol prehistory path differs")
    if binding["schema_version"] != PREHISTORY_SCHEMA_VERSION:
        raise ProtocolError("protocol prehistory schema binding differs")
    if binding["bytes"] != len(prehistory_bytes):
        raise ProtocolError("protocol prehistory byte binding differs")
    if binding["sha256"] != _digest(prehistory_bytes):
        raise ProtocolError("protocol prehistory digest binding differs")
    if binding["event_count"] != event_count or binding["chain_head_sha256"] != chain_head:
        raise ProtocolError("protocol prehistory chain summary differs")
    if binding["excluded_task_clusters_for_prospective_or_ope_estimands"] != PRE_FREEZE_TASK_IDS:
        raise ProtocolError("protocol must exclude both feasibility task clusters")
    if binding["replacement"] is not False or binding["remaining_future_task_count"] != 22:
        raise ProtocolError("protocol prehistory replacement/count differs")


def _git_text(root: pathlib.Path, args: Sequence[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProtocolError(f"Git command failed: {' '.join(args)}") from exc


def _git_bytes(root: pathlib.Path, args: Sequence[str]) -> bytes:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProtocolError(f"Git command failed: {' '.join(args)}") from exc


def _git_snapshot(
    root: pathlib.Path,
    object_paths: Mapping[str, pathlib.PurePosixPath],
) -> tuple[str, str, dict[str, str]]:
    top_level = pathlib.Path(_git_text(root, ["rev-parse", "--show-toplevel"]).strip()).resolve()
    if top_level != root.resolve():
        raise ProtocolError("protocol root must be the exact Git top-level directory")
    status = _git_text(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if status:
        raise ProtocolError("freeze receipt requires a completely clean Git worktree")
    commit = _git_text(root, ["rev-parse", "HEAD"]).strip()
    tree = _git_text(root, ["rev-parse", "HEAD^{tree}"]).strip()
    if _COMMIT_RE.fullmatch(commit) is None or _COMMIT_RE.fullmatch(tree) is None:
        raise ProtocolError("Git commit/tree identities must be full object IDs")
    blob_oids: dict[str, str] = {}
    for role, relative in object_paths.items():
        logical_path = relative.as_posix()
        _git_text(root, ["ls-files", "--error-unmatch", "--", logical_path])
        head_payload = _git_bytes(root, ["show", f"HEAD:{logical_path}"])
        current_payload = _read_bytes(root, relative)
        if head_payload != current_payload:
            raise ProtocolError(f"freeze object {role} differs from its HEAD blob")
        blob_oid = _git_text(root, ["rev-parse", f"HEAD:{logical_path}"]).strip()
        if _COMMIT_RE.fullmatch(blob_oid) is None:
            raise ProtocolError(f"freeze object {role} has an invalid Git blob identity")
        blob_oids[role] = blob_oid
    return commit, tree, blob_oids


def build_freeze_receipt(root: pathlib.Path = ROOT) -> dict[str, Any]:
    """Build, but do not write, a receipt for one clean committed source tree."""

    validate_protocol(root)
    commit, tree, blob_oids = _git_snapshot(root, FREEZE_OBJECT_PATHS)
    objects: list[dict[str, Any]] = []
    for role in sorted(FREEZE_OBJECT_PATHS):
        relative = FREEZE_OBJECT_PATHS[role]
        payload = _read_bytes(root, relative)
        objects.append(
            {
                "role": role,
                "logical_path": relative.as_posix(),
                "bytes": len(payload),
                "sha256": _digest(payload),
                "git_blob_oid": blob_oids[role],
            }
        )
    return {
        "schema_version": FREEZE_RECEIPT_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "claim_scope": MEASUREMENT_DESIGN,
        "source": {"commit": commit, "tree": tree},
        "objects": objects,
    }


def write_freeze_receipt(
    root: pathlib.Path,
    output_path: pathlib.Path,
) -> tuple[dict[str, Any], bytes]:
    """Exclusively write a clean-tree receipt outside the governed repository."""

    root = root.resolve()
    raw_output_path = output_path.expanduser()
    if not raw_output_path.is_absolute():
        raw_output_path = pathlib.Path.cwd() / raw_output_path
    if raw_output_path.is_symlink() or raw_output_path.exists():
        raise ProtocolError("freeze receipt output already exists; overwrite is forbidden")
    if raw_output_path.parent.is_symlink() or not raw_output_path.parent.is_dir():
        raise ProtocolError("freeze receipt output parent must be an existing regular directory")
    output_path = raw_output_path.resolve()
    try:
        inside_root = output_path.is_relative_to(root)
    except AttributeError:  # pragma: no cover - Python 3.11+ is required
        inside_root = root == output_path or root in output_path.parents
    if inside_root:
        raise ProtocolError("freeze receipt output must be outside the governed repository")
    receipt = build_freeze_receipt(root)
    payload = (strict_json_dumps(receipt) + "\n").encode("utf-8")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            output_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        output_path.unlink(missing_ok=True)
        raise
    return receipt, payload


def _validate_freeze_receipt(
    root: pathlib.Path,
    receipt_path: pathlib.Path,
) -> None:
    if not receipt_path.is_absolute():
        receipt_path = pathlib.Path.cwd() / receipt_path
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ProtocolError("activation freeze receipt must be a regular file")
    payload = receipt_path.read_bytes()
    if not payload or len(payload) > MAX_JSON_BYTES:
        raise ProtocolError("activation freeze receipt is empty or exceeds the size bound")
    try:
        receipt = _object(
            strict_json_loads(payload.decode("utf-8")),
            "freeze_receipt",
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolError(f"invalid freeze receipt: {exc}") from exc
    if payload != (strict_json_dumps(receipt) + "\n").encode("utf-8"):
        raise ProtocolError("freeze receipt must use canonical JSON bytes")
    _exact_keys(
        receipt,
        {"schema_version", "study_id", "claim_scope", "source", "objects"},
        "freeze_receipt",
    )
    if receipt["schema_version"] != FREEZE_RECEIPT_SCHEMA_VERSION:
        raise ProtocolError("unsupported freeze receipt schema")
    if receipt["study_id"] != STUDY_ID or receipt["claim_scope"] != MEASUREMENT_DESIGN:
        raise ProtocolError("freeze receipt study/claim scope differs")
    source = _object(receipt["source"], "freeze_receipt.source")
    _exact_keys(source, {"commit", "tree"}, "freeze_receipt.source")
    commit = source["commit"]
    tree = source["tree"]
    if (
        not isinstance(commit, str)
        or _COMMIT_RE.fullmatch(commit) is None
        or not isinstance(tree, str)
        or _COMMIT_RE.fullmatch(tree) is None
    ):
        raise ProtocolError("freeze receipt source must contain full commit/tree IDs")

    objects = _array(receipt["objects"], "freeze_receipt.objects")
    by_role: dict[str, dict[str, Any]] = {}
    for index, raw_object in enumerate(objects):
        item = _object(raw_object, f"freeze_receipt.objects[{index}]")
        _exact_keys(
            item,
            {"role", "logical_path", "bytes", "sha256", "git_blob_oid"},
            "freeze object",
        )
        role = _string(item["role"], f"freeze_receipt.objects[{index}].role")
        if role in by_role:
            raise ProtocolError("freeze object roles must be unique")
        by_role[role] = item
    if set(by_role) != REQUIRED_FREEZE_ROLES:
        raise ProtocolError(
            f"freeze receipt roles differ: missing={sorted(REQUIRED_FREEZE_ROLES - set(by_role))}, "
            f"unknown={sorted(set(by_role) - REQUIRED_FREEZE_ROLES)}"
        )
    current_commit, current_tree, blob_oids = _git_snapshot(root, FREEZE_OBJECT_PATHS)
    if current_commit != commit or current_tree != tree:
        raise ProtocolError("freeze receipt commit/tree differs from clean Git HEAD")
    for role, relative in FREEZE_OBJECT_PATHS.items():
        item = by_role[role]
        if item["logical_path"] != relative.as_posix():
            raise ProtocolError(f"freeze object path differs for role {role}")
        object_payload = _read_bytes(root, relative)
        if (
            item["bytes"] != len(object_payload)
            or item["sha256"] != _digest(object_payload)
            or item["git_blob_oid"] != blob_oids[role]
        ):
            raise ProtocolError(f"freeze object identity differs for role {role}")


def validate_protocol(
    root: pathlib.Path = ROOT,
    *,
    freeze_receipt: pathlib.Path | None = None,
) -> ValidationResult:
    """Validate the draft record and optionally its activation freeze."""

    protocol_bytes = _read_bytes(root, PROTOCOL_RELATIVE)
    prehistory_bytes = _read_bytes(root, PREHISTORY_RELATIVE)
    evidence_bytes = _read_bytes(root, EVIDENCE_RELATIVE)
    sphinx_evidence_bytes = _read_bytes(root, SPHINX_EVIDENCE_RELATIVE)
    protocol = _object(strict_json_loads(protocol_bytes.decode("utf-8")), "protocol")
    prehistory = _object(
        strict_json_loads(prehistory_bytes.decode("utf-8")),
        "prehistory",
    )
    evidence = _object(
        strict_json_loads(evidence_bytes.decode("utf-8")),
        "independent evidence",
    )
    sphinx_evidence = _object(
        strict_json_loads(sphinx_evidence_bytes.decode("utf-8")),
        "Sphinx independent evidence",
    )

    event_count, chain_head = _validate_pre_history_chain(prehistory)
    events = _array(prehistory["events"], "prehistory.events")
    if event_count != 2:
        raise ProtocolError("prehistory must disclose exactly both feasibility events")
    sympy_event = _object(events[0], "prehistory.events[0]")
    _validate_sympy_feasibility_event(
        sympy_event,
        evidence,
        _digest(evidence_bytes),
    )
    _validate_sphinx_feasibility_event(
        _object(events[1], "prehistory.events[1]"),
        sphinx_evidence,
        _digest(sphinx_evidence_bytes),
        sympy_event["draft_artifacts"],
    )
    _validate_protocol_prehistory_binding(
        protocol,
        prehistory_bytes,
        event_count,
        chain_head,
    )
    configuration_sha256, configuration_blockers = _validate_configuration_bundle(
        root,
        protocol,
    )
    declared_ready, declared_blockers = _validate_protocol_claims(
        protocol,
        configuration_blockers,
    )

    blockers = list(declared_blockers)
    if freeze_receipt is None:
        blockers.append(FREEZE_RECEIPT_BLOCKER)
    else:
        _validate_freeze_receipt(root, freeze_receipt)
    activation_ready = declared_ready and freeze_receipt is not None and not blockers
    if declared_ready and not activation_ready:
        raise ProtocolError("protocol declares activation-ready without a valid complete freeze")

    return ValidationResult(
        activation_ready=activation_ready,
        blockers=tuple(sorted(set(blockers))),
        prehistory_event_count=event_count,
        prehistory_chain_head_sha256=chain_head,
        protocol_sha256=_digest(protocol_bytes),
        prehistory_sha256=_digest(prehistory_bytes),
        configuration_sha256=configuration_sha256,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=ROOT)
    receipt_group = parser.add_mutually_exclusive_group()
    receipt_group.add_argument(
        "--check-freeze-receipt",
        "--freeze-receipt",
        dest="check_freeze_receipt",
        type=pathlib.Path,
        help="validate an existing external clean-tree receipt",
    )
    receipt_group.add_argument(
        "--write-freeze-receipt",
        type=pathlib.Path,
        help="exclusively write a new receipt outside a completely clean repository",
    )
    parser.add_argument("--require-activation-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.write_freeze_receipt is not None and args.require_activation_ready:
            raise ProtocolError(
                "--write-freeze-receipt cannot be combined with --require-activation-ready"
            )
        receipt_path = args.check_freeze_receipt
        receipt_identity: dict[str, Any] | None = None
        if args.write_freeze_receipt is not None:
            receipt_path = args.write_freeze_receipt
            _, receipt_payload = write_freeze_receipt(
                args.root.resolve(),
                receipt_path,
            )
            receipt_identity = {
                "bytes": len(receipt_payload),
                "sha256": _digest(receipt_payload),
            }
        result = validate_protocol(
            args.root.resolve(),
            freeze_receipt=receipt_path,
        )
        if args.require_activation_ready and not result.activation_ready:
            raise ProtocolError(
                "protocol is valid as a draft but not activation-ready: "
                + "; ".join(result.blockers)
            )
    except (OSError, ProtocolError, ValueError) as exc:
        print(f"prospective protocol validation failed: {exc}", file=sys.stderr)
        return 2
    output = result.to_dict()
    if receipt_identity is not None:
        output["written_freeze_receipt"] = receipt_identity
    elif receipt_path is not None:
        output["checked_freeze_receipt"] = True
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
