"""Frozen fallible-sensor proposal policy for the prospective pilot.

The package router remains the first source of an acquisition preference.  This
study-local layer only resolves two protocol-specific gaps:

* an unavailable requested modality is skipped through a frozen, auditable
  fallback order instead of collapsing immediately to abstention; and
* repeated full execution is treated as a *fallible proposal sensor*, never as
  ground truth.  Concordant independent primary/repeat observations can expose
  accept or reject to the randomized behavior policy.  The eventual scientific
  label remains independent and is not read here.

The policy never turns infrastructure errors, unavailable execution, or
inconclusive evidence into candidate rejection.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from bench_cleanser.verification._io import strict_json_dumps
from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceStatus,
    RouteAction,
)
from bench_cleanser.verification.policy_log import ActionOffer, RouterStateView

PROPOSAL_POLICY_VERSION = "verification-gap-proposal-v1"
PROPOSAL_POLICY_SCHEMA_VERSION = "prospective-pilot-terminal-proposal-0.1.0"

SEMANTIC_ACTION_ID = "semantic_primary"
TARGETED_ACTION_ID = "targeted_primary"
FULL_PRIMARY_ACTION_ID = "full_primary"
FULL_REPEAT_ACTION_ID = "full_repeat"
ACCEPT_ACTION_ID = "accept"
REJECT_ACTION_ID = "reject"
ABSTAIN_ACTION_ID = "abstain"

FALLBACK_ACTION_IDS = (
    SEMANTIC_ACTION_ID,
    TARGETED_ACTION_ID,
    FULL_PRIMARY_ACTION_ID,
    FULL_REPEAT_ACTION_ID,
)
_REQUIRED_ACTION_IDS = {
    *FALLBACK_ACTION_IDS,
    ACCEPT_ACTION_ID,
    REJECT_ACTION_ID,
    ABSTAIN_ACTION_ID,
}

PROPOSAL_POLICY_CONFIG = {
    "version": PROPOSAL_POLICY_VERSION,
    "fallback_action_ids": list(FALLBACK_ACTION_IDS),
    "terminal_sensor": {
        "required_action_ids": [FULL_PRIMARY_ACTION_ID, FULL_REPEAT_ACTION_ID],
        "required_full_execution_observations": 2,
        "supports_correct_action": ACCEPT_ACTION_ID,
        "supports_incorrect_action": REJECT_ACTION_ID,
        "error_or_unavailable_action": None,
        "inconclusive_or_disagreement_action": None,
    },
    "interpretation": "fallible_sensor_proposal_not_candidate_truth",
}
PROPOSAL_POLICY_CONFIG_SHA256 = hashlib.sha256(
    strict_json_dumps(PROPOSAL_POLICY_CONFIG).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class TerminalProposal:
    """One truth-free terminal proposal derived from paired full execution."""

    action_id: str | None
    reason_code: str
    schema_version: str = PROPOSAL_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROPOSAL_POLICY_SCHEMA_VERSION:
            raise ValueError("unsupported terminal-proposal schema version")
        if self.action_id not in {None, ACCEPT_ACTION_ID, REJECT_ACTION_ID}:
            raise ValueError("terminal proposal action must be accept, reject, or null")
        if self.reason_code not in {
            "paired_full_not_complete",
            "paired_full_accept_proposal",
            "paired_full_reject_proposal",
            "paired_full_nonconclusive",
            "paired_full_disagreement",
        }:
            raise ValueError("terminal proposal uses an unknown reason code")


def _catalog_by_id(action_catalog: Sequence[ActionOffer]) -> dict[str, ActionOffer]:
    if not isinstance(action_catalog, (list, tuple)) or any(
        not isinstance(item, ActionOffer) for item in action_catalog
    ):
        raise ValueError("proposal action catalog must contain ActionOffer values")
    result = {item.action_id: item for item in action_catalog}
    if len(result) != len(action_catalog):
        raise ValueError("proposal action catalog cannot repeat action IDs")
    missing = sorted(_REQUIRED_ACTION_IDS - set(result))
    if missing:
        raise ValueError(f"proposal action catalog is incomplete: missing={missing}")
    return result


def terminal_proposal(
    router_state: RouterStateView,
    *,
    completed_nonterminal_action_ids: Sequence[str],
) -> TerminalProposal:
    """Expose a terminal proposal only after two concordant full executions.

    Independence is established outside this pure policy function by the frozen
    action identities: ``full_primary`` and ``full_repeat`` have distinct action
    specifications, and the repeat is required to use a fresh worktree.  This
    function verifies the paired action/result shape and never consumes curator
    truth or hosted outcomes.
    """

    if not isinstance(router_state, RouterStateView):
        raise ValueError("terminal proposal requires a RouterStateView")
    if len(router_state.bootstrap_history) != 1:
        raise ValueError("terminal proposal requires one deterministic bootstrap")
    if not isinstance(completed_nonterminal_action_ids, (list, tuple)):
        raise ValueError("completed action IDs must be a sequence")
    completed = tuple(completed_nonterminal_action_ids)
    required = {FULL_PRIMARY_ACTION_ID, FULL_REPEAT_ACTION_ID}
    if not required.issubset(completed):
        return TerminalProposal(None, "paired_full_not_complete")

    full_observations = tuple(
        observation
        for observation in router_state.evidence_history
        if observation.kind == EvidenceKind.FULL_EXECUTION
    )
    if len(full_observations) != 2:
        return TerminalProposal(None, "paired_full_nonconclusive")
    if full_observations[0].acquisition_id == full_observations[1].acquisition_id:
        raise ValueError("paired full executions must have distinct acquisition IDs")

    statuses = tuple(item.status for item in full_observations)
    if any(
        status
        in {
            EvidenceStatus.ERROR,
            EvidenceStatus.UNAVAILABLE,
            EvidenceStatus.INCONCLUSIVE,
        }
        for status in statuses
    ):
        return TerminalProposal(None, "paired_full_nonconclusive")
    if statuses[0] != statuses[1]:
        return TerminalProposal(None, "paired_full_disagreement")
    if statuses[0] == EvidenceStatus.SUPPORTS_CORRECT:
        return TerminalProposal(ACCEPT_ACTION_ID, "paired_full_accept_proposal")
    if statuses[0] == EvidenceStatus.SUPPORTS_INCORRECT:
        return TerminalProposal(REJECT_ACTION_ID, "paired_full_reject_proposal")
    return TerminalProposal(None, "paired_full_nonconclusive")


def preferred_action_id(
    *,
    router_action: RouteAction,
    action_catalog: Sequence[ActionOffer],
    proposal: TerminalProposal,
) -> str:
    """Choose the frozen preferred offer without changing behavior support."""

    if not isinstance(router_action, RouteAction):
        raise ValueError("proposal router action must be a RouteAction")
    if not isinstance(proposal, TerminalProposal):
        raise ValueError("proposal must be a TerminalProposal")
    catalog = _catalog_by_id(action_catalog)

    if proposal.action_id is not None:
        proposed = catalog[proposal.action_id]
        if not proposed.available:
            raise ValueError("terminal proposal is not available in the canonical catalog")
        return proposed.action_id

    matching = sorted(
        item.action_id
        for item in catalog.values()
        if item.available and item.route_action == router_action
    )
    if matching:
        return matching[0]

    for action_id in FALLBACK_ACTION_IDS:
        if catalog[action_id].available:
            return action_id
    if not catalog[ABSTAIN_ACTION_ID].available:
        raise ValueError("proposal policy requires abstention support")
    return ABSTAIN_ACTION_ID
