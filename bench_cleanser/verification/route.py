"""CLI for making one auditable verification-routing decision."""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import asdict
from typing import Any, TextIO

from bench_cleanser import __version__
from bench_cleanser.verification._io import (
    atomic_write,
    strict_json_dumps,
    strict_json_load,
)
from bench_cleanser.verification.models import ValidityManifest
from bench_cleanser.verification.router import ConservativeRouter, RoutingPolicy


def load_manifest(stream: TextIO) -> ValidityManifest:
    """Load exactly one strict JSON manifest from *stream*."""

    try:
        value = strict_json_load(stream)
    except ValueError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    return ValidityManifest.from_dict(value)


def _policy_dict(policy: RoutingPolicy) -> dict[str, Any]:
    """Return the complete non-secret runtime policy used for this decision."""

    return {
        "version": policy.version,
        "maximum_false_accept_risk": policy.maximum_false_accept_risk,
        "minimum_authoritative_verifier_validity": (
            policy.minimum_authoritative_verifier_validity
        ),
        "high_candidate_risk": policy.high_candidate_risk,
        "high_verifier_risk": policy.high_verifier_risk,
        "allow_semantic_accept_in_evaluation": (
            policy.allow_semantic_accept_in_evaluation
        ),
        "relative_costs": {
            "static": policy.static_relative_cost,
            "semantic": policy.semantic_relative_cost,
            "targeted": policy.targeted_relative_cost,
            "full": policy.full_relative_cost,
            "hardening": policy.hardening_relative_cost,
        },
        "minimum_full_execution_replicates": (
            policy.minimum_full_execution_replicates
        ),
        "maximum_full_execution_attempts": policy.maximum_full_execution_attempts,
        "maximum_hardening_attempts": policy.maximum_hardening_attempts,
        "trusted_authoritative_bindings": [
            [kind.value, source, source_version]
            for kind, source, source_version in sorted(
                policy.trusted_authoritative_bindings,
                key=lambda item: (item[0].value, item[1], item[2]),
            )
        ],
        "trusted_calibration_bindings": [
            list(binding) for binding in sorted(policy.trusted_calibration_bindings)
        ],
    }


def build_route_result(
    manifest: ValidityManifest,
    *,
    policy: RoutingPolicy | None = None,
) -> dict[str, Any]:
    """Append and return the next conservative routing decision."""

    if manifest.route_history and manifest.route_history[-1].terminal:
        raise ValueError("manifest already has a terminal routing decision")
    if policy is not None and not isinstance(policy, RoutingPolicy):
        raise ValueError("policy must be a RoutingPolicy")
    effective_policy = policy if policy is not None else RoutingPolicy()
    digest_before = manifest.canonical_digest()
    decision = ConservativeRouter(effective_policy).route(manifest)
    if manifest.route_history and manifest.route_history[-1] == decision:
        raise ValueError(
            "routing state is unchanged; acquire and append the requested "
            "evidence before routing again"
        )
    manifest.add_decision(decision)
    return {
        "manifest_digest_before": digest_before,
        "manifest_digest_after": manifest.canonical_digest(),
        "policy": _policy_dict(effective_policy),
        "decision": asdict(decision),
        "manifest": manifest.to_dict(),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench-cleanser-route",
        description=(
            "Read a validity manifest, append the next conservative evidence "
            "action, and emit an auditable JSON result"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("manifest", help="Validity-manifest JSON file, or '-' for stdin")
    parser.add_argument("--output", help="Write the result here instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if args.manifest == "-":
            manifest = load_manifest(sys.stdin)
        else:
            with pathlib.Path(args.manifest).open(encoding="utf-8") as stream:
                manifest = load_manifest(stream)
        result = build_route_result(manifest)
        rendered = strict_json_dumps(result, indent=2) + "\n"
        if args.output:
            atomic_write(pathlib.Path(args.output), rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, ValueError) as exc:
        raise SystemExit(f"verification routing failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - console entry point
    main()
