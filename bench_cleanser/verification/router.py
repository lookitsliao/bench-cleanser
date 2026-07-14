"""Inspectable baseline policy for acquiring verification evidence.

This is deliberately a conservative heuristic baseline, not a learned or
calibrated verifier.  It provides a safe control contract and auditable route
history while paired counterfactual data are collected for a learned policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from bench_cleanser.verification.models import (
    EvidenceKind,
    EvidenceObservation,
    EvidenceStatus,
    LifecycleStage,
    RouteAction,
    RouteDecision,
    ValidityManifest,
)

AuthorityBinding = tuple[EvidenceKind, str, str]
CalibrationBinding = tuple[str, str, str]

_CONCLUSIVE_STATUSES = {
    EvidenceStatus.SUPPORTS_CORRECT,
    EvidenceStatus.SUPPORTS_INCORRECT,
}
_RUNTIME_ORACLE_KINDS = {
    EvidenceKind.TARGETED_EXECUTION,
    EvidenceKind.FULL_EXECUTION,
    EvidenceKind.ORACLE_HARDENING,
}


@dataclass(frozen=True)
class RoutingPolicy:
    version: str = "conservative-v1"
    maximum_false_accept_risk: float = 0.02
    minimum_authoritative_verifier_validity: float = 0.95
    high_candidate_risk: float = 0.55
    high_verifier_risk: float = 0.40
    allow_semantic_accept_in_evaluation: bool = False
    static_relative_cost: float = 0.01
    semantic_relative_cost: float = 0.05
    targeted_relative_cost: float = 0.20
    full_relative_cost: float = 0.70
    hardening_relative_cost: float = 1.00
    minimum_full_execution_replicates: int = 2
    maximum_full_execution_attempts: int = 3
    maximum_hardening_attempts: int = 2
    trusted_authoritative_bindings: frozenset[AuthorityBinding] = frozenset()
    trusted_calibration_bindings: frozenset[CalibrationBinding] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("policy version must be a non-empty string")
        for name in (
            "maximum_false_accept_risk",
            "minimum_authoritative_verifier_validity",
            "high_candidate_risk",
            "high_verifier_risk",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be between 0 and 1")
        for name in (
            "static_relative_cost",
            "semantic_relative_cost",
            "targeted_relative_cost",
            "full_relative_cost",
            "hardening_relative_cost",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if not isinstance(self.allow_semantic_accept_in_evaluation, bool):
            raise ValueError("allow_semantic_accept_in_evaluation must be a boolean")
        for name in (
            "minimum_full_execution_replicates",
            "maximum_full_execution_attempts",
            "maximum_hardening_attempts",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.maximum_full_execution_attempts < self.minimum_full_execution_replicates:
            raise ValueError(
                "maximum_full_execution_attempts cannot be smaller than "
                "minimum_full_execution_replicates"
            )

        if not isinstance(self.trusted_authoritative_bindings, (set, frozenset)):
            raise ValueError("trusted_authoritative_bindings must be a set")
        authority_bindings = frozenset(self.trusted_authoritative_bindings)
        for binding in authority_bindings:
            if (
                not isinstance(binding, tuple)
                or len(binding) != 3
                or not isinstance(binding[0], EvidenceKind)
                or not isinstance(binding[1], str)
                or not binding[1].strip()
                or not isinstance(binding[2], str)
                or not binding[2].strip()
            ):
                raise ValueError(
                    "authoritative bindings must be "
                    "(EvidenceKind, source, source_version) tuples"
                )
        object.__setattr__(
            self,
            "trusted_authoritative_bindings",
            authority_bindings,
        )

        if not isinstance(self.trusted_calibration_bindings, (set, frozenset)):
            raise ValueError("trusted_calibration_bindings must be a set")
        calibration_bindings = frozenset(self.trusted_calibration_bindings)
        for calibration_binding in calibration_bindings:
            if (
                not isinstance(calibration_binding, tuple)
                or len(calibration_binding) != 3
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in calibration_binding
                )
            ):
                raise ValueError(
                    "calibration bindings must be "
                    "(source, source_version, calibration_id) tuples"
                )
        object.__setattr__(
            self,
            "trusted_calibration_bindings",
            calibration_bindings,
        )


class ConservativeRouter:
    """Select a safe next action from an evidence manifest."""

    def __init__(self, policy: RoutingPolicy | None = None) -> None:
        if policy is not None and not isinstance(policy, RoutingPolicy):
            raise ValueError("policy must be a RoutingPolicy")
        self.policy = policy or RoutingPolicy()

    @staticmethod
    def _latest(
        manifest: ValidityManifest,
        kind: EvidenceKind,
    ) -> EvidenceObservation | None:
        return next(
            (item for item in reversed(manifest.evidence) if item.kind == kind),
            None,
        )

    def _is_trusted_authority(self, item: EvidenceObservation) -> bool:
        binding = (item.kind, item.source, item.source_version)
        return (
            item.authoritative
            and bool(item.acquisition_id)
            and binding in self.policy.trusted_authoritative_bindings
        )

    def _is_trusted_calibration(self, item: EvidenceObservation) -> bool:
        binding = (item.source, item.source_version, item.calibration_id)
        return binding in self.policy.trusted_calibration_bindings

    def _trusted_conclusive(
        self,
        manifest: ValidityManifest,
        kind: EvidenceKind,
    ) -> list[EvidenceObservation]:
        return [
            item
            for item in manifest.evidence
            if item.kind == kind
            and item.status in _CONCLUSIVE_STATUSES
            and self._is_trusted_authority(item)
        ]

    @staticmethod
    def _has_conclusive_disagreement(
        manifest: ValidityManifest,
        kind: EvidenceKind,
    ) -> bool:
        statuses = {
            item.status
            for item in manifest.evidence
            if item.kind == kind and item.status in _CONCLUSIVE_STATUSES
        }
        return len(statuses) > 1

    @staticmethod
    def _candidate_risk(manifest: ValidityManifest) -> float:
        profile = manifest.risk_profile
        score = 0.0
        score += 0.18 if profile.compiled_language else 0.0
        score += 0.14 if profile.native_dependencies else 0.0
        score += 0.14 if profile.touches_dependency_or_build_files else 0.0
        score += 0.12 if profile.touches_schema_or_migration else 0.0
        score += 0.16 if profile.touches_security_or_auth else 0.0
        score += 0.12 if profile.touches_concurrency else 0.0
        score += 0.10 if profile.touches_tests else 0.0
        score += min(profile.files_changed / 20.0, 0.10)
        score += min(profile.lines_changed / 2000.0, 0.10)
        score += profile.semantic_disagreement * 0.18
        return min(score, 1.0)

    @staticmethod
    def _verifier_risk(manifest: ValidityManifest) -> float:
        profile = manifest.risk_profile
        components: list[float] = []
        if profile.oracle_strength is not None:
            components.append(1.0 - profile.oracle_strength)
        if profile.historical_environment_error_rate is not None:
            components.append(profile.historical_environment_error_rate)
        if profile.observed_flake_rate is not None:
            components.append(profile.observed_flake_rate)
        if profile.generated_tests:
            components.append(0.25)
        elif profile.touches_tests:
            components.append(0.15)
        for item in manifest.evidence:
            if (
                item.kind in _RUNTIME_ORACLE_KINDS
                and item.verifier_validity is not None
            ):
                components.append(1.0 - item.verifier_validity)
            if (
                item.kind in _RUNTIME_ORACLE_KINDS
                and item.status in {EvidenceStatus.ERROR, EvidenceStatus.UNAVAILABLE}
            ):
                components.append(1.0)
        if ConservativeRouter._has_conclusive_disagreement(
            manifest,
            EvidenceKind.FULL_EXECUTION,
        ):
            components.append(1.0)
        return max(components, default=0.5)

    @staticmethod
    def _semantic_conflict(
        semantic: EvidenceObservation | None,
        runtime: EvidenceObservation,
    ) -> bool:
        if semantic is None:
            return False
        opposing = {
            (EvidenceStatus.SUPPORTS_CORRECT, EvidenceStatus.SUPPORTS_INCORRECT),
            (EvidenceStatus.SUPPORTS_INCORRECT, EvidenceStatus.SUPPORTS_CORRECT),
        }
        return (semantic.status, runtime.status) in opposing

    def _decision(
        self,
        action: RouteAction,
        manifest: ValidityManifest,
        *,
        information_gain: float,
        relative_cost: float,
        reasons: list[str],
        terminal: bool = False,
    ) -> RouteDecision:
        # These are inspectable heuristic scores, not learned or
        # statistically calibrated probabilities/value-of-information estimates.
        return RouteDecision(
            action=action,
            policy_version=self.policy.version,
            candidate_risk=self._candidate_risk(manifest),
            verifier_risk=self._verifier_risk(manifest),
            expected_information_gain=min(max(information_gain, 0.0), 1.0),
            estimated_relative_cost=relative_cost,
            reasons=tuple(reasons),
            terminal=terminal,
            scores_calibrated=False,
        )

    def _terminal_from_authority(
        self,
        manifest: ValidityManifest,
        item: EvidenceObservation,
        reason: str,
    ) -> RouteDecision:
        action = (
            RouteAction.ACCEPT
            if item.status == EvidenceStatus.SUPPORTS_CORRECT
            else RouteAction.REJECT
        )
        return self._decision(
            action,
            manifest,
            information_gain=0.0,
            relative_cost=0.0,
            reasons=[reason],
            terminal=True,
        )

    def route(self, manifest: ValidityManifest) -> RouteDecision:
        """Return the next evidence action or a terminal disposition.

        Callers should append the returned decision to ``route_history`` before
        acquiring the requested evidence.  In particular, this method never
        translates an execution/environment error into candidate rejection.
        """

        profile = manifest.risk_profile
        verifier_risk = self._verifier_risk(manifest)

        trusted_humans = self._trusted_conclusive(
            manifest,
            EvidenceKind.HUMAN_ADJUDICATION,
        )
        if len({item.status for item in trusted_humans}) > 1:
            return self._decision(
                RouteAction.ABSTAIN,
                manifest,
                information_gain=0.0,
                relative_cost=0.0,
                reasons=["policy-trusted human adjudications disagree"],
                terminal=True,
            )
        if trusted_humans:
            return self._terminal_from_authority(
                manifest,
                trusted_humans[-1],
                "human adjudication matches an explicit policy trust binding",
            )

        static = self._latest(manifest, EvidenceKind.STATIC)
        if static is None:
            return self._decision(
                RouteAction.RUN_STATIC,
                manifest,
                information_gain=0.35,
                relative_cost=self.policy.static_relative_cost,
                reasons=["no deterministic/static evidence has been recorded"],
            )
        trusted_static = self._trusted_conclusive(manifest, EvidenceKind.STATIC)
        if len({item.status for item in trusted_static}) > 1:
            return self._decision(
                RouteAction.ABSTAIN,
                manifest,
                information_gain=0.0,
                relative_cost=0.0,
                reasons=["policy-trusted static invariants disagree"],
                terminal=True,
            )
        trusted_static_failures = [
            item
            for item in trusted_static
            if item.status == EvidenceStatus.SUPPORTS_INCORRECT
        ]
        if trusted_static_failures:
            return self._terminal_from_authority(
                manifest,
                trusted_static_failures[-1],
                "a failed static invariant matches an explicit policy trust binding",
            )

        semantic = self._latest(manifest, EvidenceKind.SEMANTIC)
        if semantic is None:
            return self._decision(
                RouteAction.RUN_SEMANTIC,
                manifest,
                information_gain=0.50,
                relative_cost=self.policy.semantic_relative_cost,
                reasons=["no execution-free semantic evidence has been recorded"],
            )

        hardening_events = [
            item
            for item in manifest.evidence
            if item.kind == EvidenceKind.ORACLE_HARDENING
        ]
        can_harden = (
            profile.oracle_hardening_available
            and len(hardening_events) < self.policy.maximum_hardening_attempts
        )
        if hardening_events:
            trusted_hardened = [
                item
                for item in self._trusted_conclusive(
                    manifest,
                    EvidenceKind.ORACLE_HARDENING,
                )
                if (item.verifier_validity or 0.0)
                >= self.policy.minimum_authoritative_verifier_validity
            ]
            if len({item.status for item in trusted_hardened}) > 1:
                if can_harden:
                    return self._decision(
                        RouteAction.HARDEN_ORACLE,
                        manifest,
                        information_gain=0.75,
                        relative_cost=self.policy.hardening_relative_cost,
                        reasons=[
                            "policy-trusted hardening results disagree; acquire "
                            f"hardening attempt {len(hardening_events) + 1}"
                        ],
                    )
                return self._decision(
                    RouteAction.ABSTAIN,
                    manifest,
                    information_gain=0.0,
                    relative_cost=0.0,
                    reasons=["policy-trusted hardening results remain contradictory"],
                    terminal=True,
                )
            if trusted_hardened:
                return self._terminal_from_authority(
                    manifest,
                    trusted_hardened[-1],
                    "hardened oracle matches a policy trust binding and validity threshold",
                )
            if can_harden:
                return self._decision(
                    RouteAction.HARDEN_ORACLE,
                    manifest,
                    information_gain=0.70,
                    relative_cost=self.policy.hardening_relative_cost,
                    reasons=[
                        "hardening evidence is failed, inconclusive, or untrusted; "
                        f"acquire hardening attempt {len(hardening_events) + 1}"
                    ],
                )
            return self._decision(
                RouteAction.ABSTAIN,
                manifest,
                information_gain=0.0,
                relative_cost=0.0,
                reasons=[
                    "hardening attempts produced no policy-trusted conclusive result; "
                    "verifier failure is not candidate failure"
                ],
                terminal=True,
            )

        full_events = [
            item
            for item in manifest.evidence
            if item.kind == EvidenceKind.FULL_EXECUTION
        ]
        if full_events:
            full = full_events[-1]
            full_disagreement = self._has_conclusive_disagreement(
                manifest,
                EvidenceKind.FULL_EXECUTION,
            )
            semantic_conflict = self._semantic_conflict(semantic, full)
            if full_disagreement or semantic_conflict:
                if can_harden:
                    return self._decision(
                        RouteAction.HARDEN_ORACLE,
                        manifest,
                        information_gain=0.80,
                        relative_cost=self.policy.hardening_relative_cost,
                        reasons=[
                            "execution results disagree with each other or with "
                            "semantic evidence"
                        ],
                    )
                return self._decision(
                    RouteAction.ABSTAIN,
                    manifest,
                    information_gain=0.0,
                    relative_cost=0.0,
                    reasons=[
                        "execution evidence is contradictory and trustworthy "
                        "oracle hardening is unavailable"
                    ],
                    terminal=True,
                )

            if full.status in {EvidenceStatus.ERROR, EvidenceStatus.UNAVAILABLE}:
                if can_harden:
                    return self._decision(
                        RouteAction.HARDEN_ORACLE,
                        manifest,
                        information_gain=0.75,
                        relative_cost=self.policy.hardening_relative_cost,
                        reasons=["full execution failed; acquire independent oracle evidence"],
                    )
                if (
                    profile.full_execution_available
                    and len(full_events) < self.policy.maximum_full_execution_attempts
                ):
                    return self._decision(
                        RouteAction.RUN_FULL,
                        manifest,
                        information_gain=0.60,
                        relative_cost=self.policy.full_relative_cost,
                        reasons=[
                            "full execution failed without a candidate label; "
                            f"acquire attempt {len(full_events) + 1}"
                        ],
                    )
                return self._decision(
                    RouteAction.ABSTAIN,
                    manifest,
                    information_gain=0.0,
                    relative_cost=0.0,
                    reasons=[
                        "full execution attempts failed and cannot reject the candidate"
                    ],
                    terminal=True,
                )

            if verifier_risk >= self.policy.high_verifier_risk:
                if can_harden:
                    return self._decision(
                        RouteAction.HARDEN_ORACLE,
                        manifest,
                        information_gain=0.80,
                        relative_cost=self.policy.hardening_relative_cost,
                        reasons=["runtime oracle risk exceeds the terminal-decision bound"],
                    )
                return self._decision(
                    RouteAction.ABSTAIN,
                    manifest,
                    information_gain=0.0,
                    relative_cost=0.0,
                    reasons=[
                        "runtime oracle risk exceeds the terminal-decision bound and "
                        "hardening is unavailable"
                    ],
                    terminal=True,
                )

            trusted_full = [
                item
                for item in self._trusted_conclusive(
                    manifest,
                    EvidenceKind.FULL_EXECUTION,
                )
                if (item.verifier_validity or 0.0)
                >= self.policy.minimum_authoritative_verifier_validity
            ]
            if len(trusted_full) < self.policy.minimum_full_execution_replicates:
                if (
                    profile.full_execution_available
                    and len(full_events) < self.policy.maximum_full_execution_attempts
                ):
                    return self._decision(
                        RouteAction.RUN_FULL,
                        manifest,
                        information_gain=0.60,
                        relative_cost=self.policy.full_relative_cost,
                        reasons=[
                            "terminal execution evidence requires "
                            f"{self.policy.minimum_full_execution_replicates} trusted "
                            "independently identified replicates; acquire another attempt"
                        ],
                    )
                if can_harden:
                    return self._decision(
                        RouteAction.HARDEN_ORACLE,
                        manifest,
                        information_gain=0.75,
                        relative_cost=self.policy.hardening_relative_cost,
                        reasons=["full execution lacks enough policy-trusted replicates"],
                    )
                return self._decision(
                    RouteAction.ABSTAIN,
                    manifest,
                    information_gain=0.0,
                    relative_cost=0.0,
                    reasons=[
                        "full execution lacks enough policy-trusted replicates and "
                        "no further trustworthy acquisition is available"
                    ],
                    terminal=True,
                )

            return self._terminal_from_authority(
                manifest,
                trusted_full[-1],
                "repeated full executions match an explicit policy trust binding",
            )

        semantic_terminal_allowed = (
            manifest.lifecycle_stage != LifecycleStage.EVALUATION
            or self.policy.allow_semantic_accept_in_evaluation
        )
        if (
            semantic_terminal_allowed
            and semantic.status == EvidenceStatus.SUPPORTS_CORRECT
            and not semantic.privileged_inputs
            and semantic.candidate_probability is not None
            and semantic.candidate_probability >= 0.5
            and semantic.calibrated_risk_upper_bound is not None
            and semantic.calibrated_risk_upper_bound
            <= self.policy.maximum_false_accept_risk
            and self._is_trusted_calibration(semantic)
        ):
            return self._terminal_from_authority(
                manifest,
                semantic,
                "declared calibration bound from a policy-trusted binding is "
                "within the false-accept threshold",
            )

        if (
            verifier_risk >= self.policy.high_verifier_risk
            and profile.oracle_hardening_available
        ):
            return self._decision(
                RouteAction.HARDEN_ORACLE,
                manifest,
                information_gain=0.70,
                relative_cost=self.policy.hardening_relative_cost,
                reasons=["available runtime oracle has high validity uncertainty"],
            )

        candidate_risk = self._candidate_risk(manifest)
        targeted = self._latest(manifest, EvidenceKind.TARGETED_EXECUTION)
        if (
            candidate_risk < self.policy.high_candidate_risk
            and profile.targeted_execution_available
            and targeted is None
            and manifest.lifecycle_stage != LifecycleStage.EVALUATION
        ):
            return self._decision(
                RouteAction.RUN_TARGETED,
                manifest,
                information_gain=0.55,
                relative_cost=self.policy.targeted_relative_cost,
                reasons=["a cheaper targeted probe is available for a non-high-risk patch"],
            )

        if profile.full_execution_available:
            reasons = ["remaining evidence does not justify a terminal label"]
            if candidate_risk >= self.policy.high_candidate_risk:
                reasons.append("candidate features exceed the high-risk threshold")
            if manifest.lifecycle_stage == LifecycleStage.EVALUATION:
                reasons.append("evaluation uses the stricter evidence path by default")
            if targeted is not None:
                reasons.append("targeted evidence alone is non-authoritative")
            return self._decision(
                RouteAction.RUN_FULL,
                manifest,
                information_gain=0.75,
                relative_cost=self.policy.full_relative_cost,
                reasons=reasons,
            )

        return self._decision(
            RouteAction.ABSTAIN,
            manifest,
            information_gain=0.0,
            relative_cost=0.0,
            reasons=["required execution is unavailable and semantic risk is unbounded"],
            terminal=True,
        )
