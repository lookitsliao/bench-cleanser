#!/usr/bin/env python3
"""Fail-closed release SBOM, license-policy, and artifact checks.

The license result is deliberately described as automated metadata triage. It
does not assert that counsel has reviewed a dependency or that package metadata
correctly describes every bundled/native component.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.parse
import zipfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

_MAX_MEMBER_BYTES = 16 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 256 * 1024 * 1024

_REAL_AGENT_COHORT_SUFFIX = (
    "experiments",
    "real_agent_pilot",
    "cohort.json",
)
_HOSTED_STUDY_SOURCE_SUFFIX = (
    "experiments",
    "hosted_outcome_study",
    "run_study.py",
)
_MATCHED_STUDY_SOURCE_SUFFIX = (
    "experiments",
    "matched_rollout_study",
    "run_study.py",
)
_LITERATURE_LOCK_SUFFIX = ("docs", "literature.lock.json")
_LITERATURE_CLAIMS_SUFFIX = ("docs", "literature.claims.json")
_INDEPENDENT_SMOKE_MANIFEST_SUFFIX = (
    "experiments",
    "independent_execution_smoke",
    "evidence-manifest.json",
)
_INDEPENDENT_SMOKE_SOURCE_SUFFIX = (
    "experiments",
    "independent_execution_smoke",
    "run_smoke.py",
)
_PAIRED_SMOKE_MANIFEST_SUFFIX = (
    "experiments",
    "paired_execution_smoke",
    "evidence-manifest.json",
)
_PAIRED_SMOKE_SOURCE_SUFFIX = (
    "experiments",
    "paired_execution_smoke",
    "verify_evidence.py",
)
_SPHINX_SMOKE_MANIFEST_SUFFIX = (
    "experiments",
    "sphinx_execution_smoke",
    "evidence-manifest.json",
)
_SPHINX_SMOKE_SOURCE_SUFFIX = (
    "experiments",
    "sphinx_execution_smoke",
    "verify_evidence.py",
)
_PROSPECTIVE_PROTOCOL_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "preregistration.json",
)
_PROSPECTIVE_PREHISTORY_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "prehistory.json",
)
_PROSPECTIVE_COLLECTION_POLICY_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "collection_policy.json",
)
_PROSPECTIVE_FRAME_MANIFEST_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "frame_manifest.json",
)
_PROSPECTIVE_SCHEDULER_CONTRACT_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "scheduler_contract.json",
)
_PROSPECTIVE_SCHEDULER_SOURCE_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "scheduler.py",
)
_PROSPECTIVE_ANALYSIS_PLAN_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "analysis_plan.json",
)
_PROSPECTIVE_EXECUTION_FREEZE_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "execution_freeze.json",
)
_PROSPECTIVE_TARGET_POLICY_MANIFEST_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "target_policy_manifest.json",
)
_PROSPECTIVE_ADJUDICATION_PLAN_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "adjudication_plan.json",
)
_PROSPECTIVE_REVIEW_PACKET_SOURCE_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "review_packets.py",
)
_PROSPECTIVE_VALIDATOR_SUFFIX = (
    "experiments",
    "prospective_pilot",
    "validate_protocol.py",
)
# These records are immutable, checked-in public evidence.  Store their binary
# SHA-256 values rather than high-entropy hexadecimal strings so the scanner
# does not need a recursive waiver for its own provenance policy.  Exact byte
# bindings deliberately make whitespace, source-line, and same-shape digest
# substitutions fail closed.
_INDEPENDENT_SMOKE_MANIFEST_BYTES = 35_718
_INDEPENDENT_SMOKE_MANIFEST_DIGEST = bytes(
    (
        176,
        188,
        236,
        66,
        74,
        87,
        13,
        128,
        168,
        141,
        6,
        88,
        75,
        235,
        127,
        173,
        18,
        89,
        254,
        159,
        164,
        254,
        103,
        219,
        31,
        77,
        48,
        106,
        194,
        81,
        226,
        28,
    )
)
_INDEPENDENT_SMOKE_SOURCE_BYTES = 54_596
_INDEPENDENT_SMOKE_SOURCE_DIGEST = bytes(
    (
        163,
        218,
        163,
        81,
        139,
        19,
        241,
        129,
        72,
        25,
        173,
        178,
        161,
        152,
        39,
        132,
        188,
        200,
        60,
        197,
        225,
        24,
        75,
        85,
        248,
        167,
        41,
        106,
        174,
        221,
        103,
        28,
    )
)
_PAIRED_SMOKE_MANIFEST_BYTES = 18_559
_PAIRED_SMOKE_MANIFEST_DIGEST = bytes(
    (
        23,
        204,
        202,
        88,
        47,
        63,
        77,
        175,
        184,
        232,
        171,
        46,
        53,
        234,
        154,
        137,
        147,
        36,
        146,
        44,
        12,
        60,
        223,
        116,
        74,
        137,
        43,
        224,
        161,
        184,
        125,
        28,
    )
)
_PAIRED_SMOKE_SOURCE_BYTES = 44_375
_PAIRED_SMOKE_SOURCE_DIGEST = bytes(
    (
        194,
        96,
        22,
        167,
        82,
        170,
        156,
        173,
        231,
        133,
        7,
        217,
        230,
        177,
        17,
        234,
        29,
        107,
        107,
        211,
        202,
        188,
        207,
        70,
        204,
        94,
        186,
        207,
        115,
        25,
        132,
        114,
    )
)
_SPHINX_SMOKE_MANIFEST_BYTES = 15_215
_SPHINX_SMOKE_MANIFEST_DIGEST = bytes(
    (
        64,
        105,
        152,
        166,
        10,
        122,
        7,
        80,
        1,
        158,
        132,
        6,
        160,
        54,
        82,
        197,
        174,
        206,
        5,
        250,
        231,
        235,
        110,
        74,
        229,
        217,
        119,
        232,
        162,
        171,
        109,
        179,
    )
)
_SPHINX_SMOKE_SOURCE_BYTES = 49_421
_SPHINX_SMOKE_SOURCE_DIGEST = bytes(
    (
        82,
        53,
        108,
        22,
        161,
        161,
        173,
        83,
        149,
        22,
        43,
        252,
        240,
        174,
        176,
        101,
        251,
        199,
        118,
        231,
        94,
        61,
        247,
        156,
        219,
        233,
        163,
        60,
        149,
        251,
        101,
        81,
    )
)
_PROSPECTIVE_PREHISTORY_BYTES = 6_328
_PROSPECTIVE_PREHISTORY_DIGEST = bytes(
    (
        236,
        51,
        179,
        158,
        189,
        246,
        230,
        145,
        251,
        91,
        143,
        21,
        171,
        119,
        220,
        207,
        26,
        193,
        23,
        81,
        29,
        66,
        178,
        241,
        143,
        255,
        14,
        184,
        172,
        99,
        125,
        99,
    )
)
_PROSPECTIVE_PROTOCOL_BYTES = 14_922
_PROSPECTIVE_PROTOCOL_DIGEST = bytes(
    (
        65,
        162,
        225,
        21,
        79,
        63,
        4,
        245,
        195,
        167,
        99,
        52,
        3,
        71,
        54,
        49,
        227,
        117,
        2,
        160,
        251,
        77,
        39,
        89,
        250,
        248,
        163,
        223,
        122,
        91,
        249,
        172,
    )
)
_PROSPECTIVE_VALIDATOR_BYTES = 123_699
_PROSPECTIVE_VALIDATOR_DIGEST = bytes(
    (
        78,
        64,
        210,
        202,
        160,
        135,
        138,
        144,
        255,
        134,
        87,
        22,
        53,
        164,
        183,
        14,
        206,
        205,
        237,
        48,
        162,
        102,
        184,
        89,
        203,
        177,
        37,
        167,
        143,
        199,
        93,
        162,
    )
)
_PROSPECTIVE_COLLECTION_POLICY_BYTES = 8_168
_PROSPECTIVE_COLLECTION_POLICY_DIGEST = bytes(
    (
        197,
        210,
        118,
        237,
        228,
        97,
        27,
        182,
        45,
        38,
        71,
        103,
        193,
        78,
        243,
        137,
        9,
        172,
        244,
        214,
        176,
        37,
        211,
        216,
        152,
        104,
        218,
        208,
        56,
        156,
        191,
        138,
    )
)
_PROSPECTIVE_FRAME_MANIFEST_BYTES = 8_455
_PROSPECTIVE_FRAME_MANIFEST_DIGEST = bytes(
    (
        75,
        43,
        228,
        247,
        123,
        198,
        112,
        104,
        86,
        151,
        149,
        131,
        1,
        220,
        64,
        50,
        119,
        123,
        139,
        165,
        49,
        233,
        114,
        49,
        21,
        45,
        200,
        71,
        230,
        187,
        179,
        25,
    )
)
_PROSPECTIVE_SCHEDULER_CONTRACT_BYTES = 7_915
_PROSPECTIVE_SCHEDULER_CONTRACT_DIGEST = bytes(
    (
        99,
        121,
        146,
        193,
        74,
        96,
        104,
        76,
        90,
        84,
        231,
        64,
        191,
        153,
        109,
        5,
        31,
        81,
        96,
        110,
        202,
        21,
        16,
        32,
        222,
        164,
        251,
        205,
        143,
        124,
        220,
        141,
    )
)
_PROSPECTIVE_SCHEDULER_SOURCE_BYTES = 155_935
_PROSPECTIVE_SCHEDULER_SOURCE_DIGEST = bytes(
    (
        253,
        203,
        126,
        220,
        31,
        79,
        13,
        79,
        78,
        132,
        21,
        58,
        144,
        204,
        9,
        74,
        128,
        61,
        97,
        106,
        250,
        103,
        88,
        39,
        187,
        97,
        175,
        217,
        20,
        77,
        121,
        225,
    )
)
_LITERATURE_CLAIMS_BYTES = 29_139
_LITERATURE_CLAIMS_DIGEST = bytes(
    (
        152,
        178,
        199,
        163,
        227,
        99,
        47,
        185,
        254,
        125,
        132,
        124,
        45,
        229,
        4,
        175,
        57,
        19,
        57,
        53,
        73,
        186,
        56,
        196,
        196,
        44,
        215,
        106,
        94,
        65,
        0,
        157,
    )
)
_LITERATURE_CLAIMS_VALIDATOR_BYTES = 12_489
_LITERATURE_CLAIMS_VALIDATOR_DIGEST = bytes(
    (
        35,
        159,
        48,
        88,
        8,
        126,
        159,
        29,
        215,
        173,
        206,
        204,
        197,
        178,
        186,
        254,
        236,
        224,
        130,
        38,
        40,
        208,
        29,
        113,
        130,
        118,
        238,
        174,
        113,
        22,
        100,
        23,
    )
)
_PILOT_ARTIFACT_NAMES = {"patch.diff", "report.json", "trajectory.json"}
_COMMIT_HEX_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")
_ARXIV_VERSIONED_ID_RE = re.compile(
    r"(?P<arxiv_id>[0-9]{4}\.(?:[0-9]{5}|[0-9]{4}))v(?P<version>[1-9][0-9]*)"
)
_UTC_TIMESTAMP_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

_PROSPECTIVE_ACTIVATION_BLOCKERS = (
    "Docker daemon and provisioner attestation",
    "aggregate resource reservation settlement and partial-frame reporting",
    "signed deterministic bootstrap receipt acquisition",
    "durable exclusive scheduler ledger and write-ahead dispatcher",
    "durable bootstrap curator adjudication substrate and resource ledgers",
    "execution target architecture",
    "opaque-map custodian identity",
    "per-task dependency-lock manifest",
    "per-task execution-spec manifest",
    "per-task image-digest manifest",
    "reviewer identities and independence attestations",
    "semantic model prompt endpoint calibration and cost identity",
    "trusted ledger-to-corpus terminal-outcome and cost compiler",
    "typed acquisition-result persistence and action-spec preimages",
)
_PROSPECTIVE_PROPOSAL_POLICY_PATH = "experiments/prospective_pilot/proposal_policy.py"
_PROSPECTIVE_RELEASE_BUNDLE_PATH = "experiments/prospective_pilot/release_bundle.py"
_PROSPECTIVE_PROPOSAL_POLICY_CONFIG: Mapping[str, Any] = {
    "version": "verification-gap-proposal-v1",
    "fallback_action_ids": [
        "semantic_primary",
        "targeted_primary",
        "full_primary",
        "full_repeat",
    ],
    "terminal_sensor": {
        "required_action_ids": ["full_primary", "full_repeat"],
        "required_full_execution_observations": 2,
        "supports_correct_action": "accept",
        "supports_incorrect_action": "reject",
        "error_or_unavailable_action": None,
        "inconclusive_or_disagreement_action": None,
    },
    "interpretation": "fallible_sensor_proposal_not_candidate_truth",
}

_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "private-key",
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    ("openai-compatible-key", re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}")),
    ("github-token", re.compile(rb"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(rb"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("google-api-key", re.compile(rb"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{30,}")),
    ("slack-token", re.compile(rb"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{20,}")),
    (
        "literal-api-key-assignment",
        re.compile(
            rb"(?i)(?:OPENAI|ANTHROPIC|DOCENT|LB)_API_KEY\s*[:=]\s*[\"']?"
            rb"[A-Za-z0-9_-]{20,}"
        ),
    ),
)

_PROPRIETARY_IMPORT = re.compile(
    r"(?m)^[ \t]*(?:from|import)[ \t]+"
    r"(?:azure(?:\.[A-Za-z0-9_.]+)?|msal(?:_extensions)?|cloudgpt|astred(?:_core)?)\b"
)


class AuditInputError(ValueError):
    """Raised when an audit input is malformed or internally inconsistent."""


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditInputError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle, object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError(f"cannot read strict JSON {path}: {exc}") from exc


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            policy = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AuditInputError(f"cannot read policy {path}: {exc}") from exc

    if policy.get("legal_review_complete") is not False:
        raise AuditInputError(
            "policy must keep legal_review_complete=false; this gate cannot establish legal review"
        )
    for section in ("licenses", "packages"):
        if not isinstance(policy.get(section), dict):
            raise AuditInputError(f"policy is missing [{section}]")
    return policy


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _compile_patterns(values: Any, field: str) -> list[re.Pattern[str]]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise AuditInputError(f"{field} must be a list of regex strings")
    try:
        return [re.compile(value) for value in values]
    except re.error as exc:
        raise AuditInputError(f"invalid regex in {field}: {exc}") from exc


def _split_license_expression(raw: str) -> list[str]:
    # pip-licenses may return SPDX expressions, classifier labels separated by
    # semicolons, or a single human-readable label. Requiring every leaf to be
    # allowed is intentionally conservative, including for OR expressions.
    pieces = re.split(r"\s+(?:AND|OR)\s+|;", raw, flags=re.IGNORECASE)
    leaves: list[str] = []
    for piece in pieces:
        leaf = piece.strip()
        if leaf.startswith("(") and leaf.endswith(")"):
            leaf = leaf[1:-1].strip()
        if leaf:
            leaves.append(leaf)
    return leaves


def _normalized_alias_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _sbom_packages(sbom: Any) -> tuple[set[tuple[str, str]], list[str]]:
    errors: list[str] = []
    if not isinstance(sbom, dict) or sbom.get("bomFormat") != "CycloneDX":
        return set(), ["SBOM is not a CycloneDX JSON object"]
    if sbom.get("specVersion") not in {"1.6", "1.7"}:
        errors.append("SBOM must use CycloneDX specification 1.6 or 1.7")

    components = sbom.get("components", [])
    if not isinstance(components, list):
        return set(), errors + ["SBOM components must be a list"]
    metadata = sbom.get("metadata", {})
    if not isinstance(metadata, dict):
        return set(), errors + ["SBOM metadata must be an object"]

    values: list[Any] = list(components)
    root = metadata.get("component")
    if root is not None:
        values.append(root)

    packages: set[tuple[str, str]] = set()
    for index, component in enumerate(values):
        if not isinstance(component, dict):
            errors.append(f"SBOM component {index} is not an object")
            continue
        name = component.get("name")
        version = component.get("version")
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            errors.append(f"SBOM component {index} lacks a non-empty name/version")
            continue
        identity = (_canonical_name(name), version)
        if identity in packages:
            errors.append(f"duplicate SBOM package identity: {name}=={version}")
        packages.add(identity)
    return packages, errors


def audit_licenses(
    inventory_path: Path,
    sbom_path: Path,
    policy_path: Path,
) -> dict[str, Any]:
    """Evaluate installed-distribution metadata against the alpha policy."""

    inventory = _load_json(inventory_path)
    sbom = _load_json(sbom_path)
    policy = _load_policy(policy_path)
    if not isinstance(inventory, list):
        raise AuditInputError("pip-licenses inventory must be a JSON list")

    licenses = policy["licenses"]
    aliases_value = licenses.get("aliases")
    if not isinstance(aliases_value, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in aliases_value.items()
    ):
        raise AuditInputError("[licenses.aliases] must map strings to strings")
    aliases = {_normalized_alias_key(key): value for key, value in aliases_value.items()}
    allowed_value = licenses.get("allowed")
    if not isinstance(allowed_value, list) or not all(
        isinstance(value, str) for value in allowed_value
    ):
        raise AuditInputError("licenses.allowed must be a list of strings")
    allowed = set(allowed_value)
    denied = _compile_patterns(licenses.get("denied_patterns"), "licenses.denied_patterns")
    review = _compile_patterns(licenses.get("review_patterns"), "licenses.review_patterns")
    unknown_values = {
        _normalized_alias_key(value)
        for value in licenses.get("unknown_values", [])
        if isinstance(value, str)
    }

    package_policy = policy["packages"]
    forbidden = {
        _canonical_name(value)
        for value in package_policy.get("forbidden", [])
        if isinstance(value, str)
    }
    excluded = {
        _canonical_name(value)
        for value in package_policy.get("excluded_integrations", [])
        if isinstance(value, str)
    }

    package_records: list[dict[str, Any]] = []
    inventory_identities: set[tuple[str, str]] = set()
    seen_names: set[str] = set()
    for index, item in enumerate(inventory):
        if not isinstance(item, dict):
            raise AuditInputError(f"inventory item {index} is not an object")
        name = item.get("Name")
        version = item.get("Version")
        raw_license = item.get("License")
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise AuditInputError(f"inventory item {index} lacks Name/Version")
        if not isinstance(raw_license, str):
            raise AuditInputError(f"inventory item {index} lacks a string License")

        canonical_name = _canonical_name(name)
        if canonical_name in seen_names:
            raise AuditInputError(f"duplicate installed distribution: {name}")
        seen_names.add(canonical_name)
        inventory_identities.add((canonical_name, version))

        decision = "allow"
        reasons: list[str] = []
        normalized_licenses: list[str] = []
        if canonical_name in forbidden:
            decision = "deny"
            reasons.append("package is forbidden/retired by release policy")
        if canonical_name in excluded:
            decision = "deny"
            reasons.append("external integration entered the audited release environment")

        license_text = item.get("LicenseText")
        if not isinstance(license_text, str) or not license_text.strip():
            if decision != "deny":
                decision = "review"
            reasons.append("no non-empty installed license file was captured")

        normalized_raw = _normalized_alias_key(raw_license)
        if normalized_raw in unknown_values:
            if decision != "deny":
                decision = "review"
            reasons.append("license metadata is unknown or empty")
        elif any(pattern.search(raw_license) for pattern in denied):
            decision = "deny"
            reasons.append("license metadata matches a deny pattern")
        elif any(pattern.search(raw_license) for pattern in review):
            if decision != "deny":
                decision = "review"
            reasons.append("license metadata requires explicit human review")
        else:
            for leaf in _split_license_expression(raw_license):
                canonical_license = aliases.get(_normalized_alias_key(leaf))
                if canonical_license is None:
                    if decision != "deny":
                        decision = "review"
                    reasons.append(f"unrecognized license term: {leaf}")
                    continue
                normalized_licenses.append(canonical_license)
                if canonical_license not in allowed:
                    if decision != "deny":
                        decision = "review"
                    reasons.append(f"license is not policy-allowed: {canonical_license}")

        package_records.append(
            {
                "decision": decision,
                "license_file_captured": isinstance(license_text, str)
                and bool(license_text.strip()),
                "name": name,
                "normalized_licenses": sorted(set(normalized_licenses)),
                "reasons": reasons,
                "reported_license": raw_license,
                "url": item.get("URL") if isinstance(item.get("URL"), str) else "",
                "version": version,
            }
        )

    sbom_identities, sbom_errors = _sbom_packages(sbom)
    missing_from_sbom = sorted(inventory_identities - sbom_identities)
    missing_from_inventory = sorted(sbom_identities - inventory_identities)
    coverage_errors = list(sbom_errors)
    if missing_from_sbom:
        coverage_errors.append(f"installed packages absent from SBOM: {missing_from_sbom}")
    if missing_from_inventory:
        coverage_errors.append(
            f"SBOM packages absent from license inventory: {missing_from_inventory}"
        )

    summary = {
        "allow": sum(record["decision"] == "allow" for record in package_records),
        "deny": sum(record["decision"] == "deny" for record in package_records),
        "review": sum(record["decision"] == "review" for record in package_records),
        "total": len(package_records),
    }
    passed = summary["deny"] == 0 and summary["review"] == 0 and not coverage_errors
    return {
        "automation_result": "pass" if passed else "fail",
        "legal_review_complete": False,
        "limitations": [
            "Decisions use installed distribution metadata and captured license files; metadata may be wrong or incomplete.",
            "The snapshot covers one resolved Python environment, not every platform, dependency version, native library, or external integration.",
            "A passing result is automated policy triage and is not legal advice or a completed legal review.",
        ],
        "packages": sorted(package_records, key=lambda item: _canonical_name(item["name"])),
        "policy": {
            "name": policy.get("policy_name"),
            "sha256": _sha256(policy_path),
            "version": policy.get("policy_version"),
        },
        "sbom_coverage_errors": coverage_errors,
        "scope_profiles": policy.get("scope_profiles", []),
        "source_artifacts": {
            "inventory_sha256": _sha256(inventory_path),
            "sbom_sha256": _sha256(sbom_path),
        },
        "summary": summary,
    }


def _safe_member_name(name: str) -> str | None:
    if (
        not name
        or "\\" in name
        or "//" in name
        or name.startswith("./")
        or "/./" in name
        or re.match(r"^[A-Za-z]:", name)
    ):
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def _iter_archive(path: Path) -> Iterator[tuple[str, bytes | None, str]]:
    """Yield member path, bytes, and kind without trusting archive paths."""

    if path.suffix == ".whl" or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for zip_member in archive.infolist():
                if zip_member.is_dir():
                    continue
                kind = "file"
                # UNIX symlink mode in the high permission bits.
                if (zip_member.external_attr >> 16) & 0o170000 == 0o120000:
                    kind = "link"
                if zip_member.file_size > _MAX_MEMBER_BYTES:
                    kind = "oversize"
                data = archive.read(zip_member) if kind == "file" else None
                yield zip_member.filename, data, kind
        return

    if path.name.endswith((".tar.gz", ".tgz", ".tar")):
        with tarfile.open(path, "r:*") as archive:
            for tar_member in archive.getmembers():
                if tar_member.isdir():
                    continue
                if not tar_member.isfile():
                    yield tar_member.name, None, "link-or-special"
                    continue
                if tar_member.size > _MAX_MEMBER_BYTES:
                    yield tar_member.name, None, "oversize"
                    continue
                handle = archive.extractfile(tar_member)
                if handle is None:
                    yield tar_member.name, None, "unreadable"
                else:
                    yield tar_member.name, handle.read(), "file"
        return

    raise AuditInputError(f"unsupported release artifact format: {path}")


def _line_number(data: bytes, offset: int) -> int:
    return data.count(b"\n", 0, offset) + 1


def _dependency_files(member_path: str) -> bool:
    name = PurePosixPath(member_path).name.lower()
    return (
        name == "pyproject.toml"
        or name == "setup.cfg"
        or (name.startswith("requirements") and name.endswith(".txt"))
    )


def _scan_member(
    member_path: str,
    data: bytes,
    dependency_names: set[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for finding_type, credential_pattern in _CREDENTIAL_PATTERNS:
        for credential_match in credential_pattern.finditer(data):
            findings.append(
                {
                    "kind": "credential",
                    "line": _line_number(data, credential_match.start()),
                    "path": member_path,
                    "rule": finding_type,
                }
            )

    if b"\x00" in data:
        return findings
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return findings

    if member_path.endswith(".py"):
        for import_match in _PROPRIETARY_IMPORT.finditer(text):
            findings.append(
                {
                    "kind": "proprietary-import",
                    "line": text.count("\n", 0, import_match.start()) + 1,
                    "path": member_path,
                    "rule": "retired-provider-import",
                }
            )

    dependency_lines: list[tuple[int, str]] = []
    if member_path.endswith(".dist-info/METADATA"):
        dependency_lines = [
            (line_number, line)
            for line_number, line in enumerate(text.splitlines(), 1)
            if line.lower().startswith("requires-dist:")
        ]
    elif _dependency_files(member_path):
        dependency_lines = [
            (line_number, line)
            for line_number, line in enumerate(text.splitlines(), 1)
            if line.strip() and not line.lstrip().startswith("#")
        ]

    if dependency_lines:
        for dependency in sorted(dependency_names):
            spelling = re.escape(dependency).replace(r"\-", "[-_.]")
            dependency_pattern = re.compile(rf"(?i)(?<![A-Za-z0-9_.-]){spelling}(?![A-Za-z0-9_.-])")
            for line_number, line in dependency_lines:
                if dependency_pattern.search(line):
                    findings.append(
                        {
                            "kind": "forbidden-dependency",
                            "line": line_number,
                            "path": member_path,
                            "rule": dependency,
                        }
                    )
    return findings


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def _json_hex_fields(
    value: Any,
    *,
    path: str = "",
) -> list[tuple[str, str, str]]:
    """Return full commit/SHA strings with their canonical JSON field paths."""

    result: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            item_path = f"{path}.{key}" if path else key
            if isinstance(item, str) and (
                _COMMIT_HEX_RE.fullmatch(item) or _SHA256_HEX_RE.fullmatch(item)
            ):
                result.append((item, item_path, key))
            else:
                result.extend(_json_hex_fields(item, path=item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(_json_hex_fields(item, path=f"{path}[{index}]"))
    return result


def _render_json_provenance_identities(
    text: str,
    declared: Sequence[tuple[str, str, str]],
) -> dict[tuple[str, int], str]:
    """Bind declared JSON values to one unambiguous pretty-printed source line."""

    grouped: dict[tuple[str, str], list[str]] = {}
    for raw_value, field, json_key in declared:
        grouped.setdefault((json_key, raw_value), []).append(field)
    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    used_lines: set[int] = set()
    for (json_key, raw_value), fields in grouped.items():
        encoded_pair = re.compile(
            rf"{re.escape(json.dumps(json_key))}\s*:\s*"
            rf"{re.escape(json.dumps(raw_value))}"
        )
        matching_lines = [
            line_number for line_number, line in enumerate(lines, 1) if encoded_pair.search(line)
        ]
        if len(matching_lines) != len(fields):
            return {}
        for field, line_number in zip(fields, matching_lines, strict=True):
            if line_number in used_lines:
                # Minified or multi-value lines do not receive a waiver.
                return {}
            used_lines.add(line_number)
            identity = hashlib.sha1(  # noqa: S324 - scanner identity, not security
                raw_value.encode("utf-8")
            ).hexdigest()
            key = (identity, line_number)
            if key in result:
                return {}
            result[key] = field
    return result


def _label_unverified_provenance(
    rendered: Mapping[tuple[str, int], str],
    unverified_fields: set[str],
) -> dict[tuple[str, int], str]:
    """Keep declared external/seed identities visible as explicitly unverified."""

    return {
        key: (f"declared_unverified:{field}" if field in unverified_fields else field)
        for key, field in rendered.items()
    }


def _matches_any_path(path: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.fullmatch(path) for pattern in patterns)


def _matches_exact_public_record(
    path: Path,
    *,
    expected_bytes: int,
    expected_digest: bytes,
) -> bool:
    """Require the exact immutable public record without exposing hex text."""

    try:
        payload = path.read_bytes()
    except OSError:
        return False
    return len(payload) == expected_bytes and hashlib.sha256(payload).digest() == expected_digest


def _declared_independent_smoke_manifest_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify only typed hashes in the strict one-task execution record."""

    if tuple(path.parts[-len(_INDEPENDENT_SMOKE_MANIFEST_SUFFIX) :]) != (
        _INDEPENDENT_SMOKE_MANIFEST_SUFFIX
    ):
        return {}
    if not _matches_exact_public_record(
        path,
        expected_bytes=_INDEPENDENT_SMOKE_MANIFEST_BYTES,
        expected_digest=_INDEPENDENT_SMOKE_MANIFEST_DIGEST,
    ) or not _matches_exact_public_record(
        path.with_name("run_smoke.py"),
        expected_bytes=_INDEPENDENT_SMOKE_SOURCE_BYTES,
        expected_digest=_INDEPENDENT_SMOKE_SOURCE_DIGEST,
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
        {
            "schema_version",
            "study_id",
            "classification",
            "protocol_state",
            "task",
            "sources",
            "harness",
            "preparation",
            "runtime",
            "evidence_bundle",
            "execution_groups",
            "hosted_prior_measurements",
            "aggregate",
            "limitations",
        },
    ):
        return {}
    classification = value["classification"]
    groups = value["execution_groups"]
    if (
        value["schema_version"] != "independent-execution-smoke-0.1.0"
        or value["study_id"] != "sympy-15976-container-free-post-draft-pre-freeze-feasibility-v1"
        or not isinstance(classification, dict)
        or classification.get("stage") != "post_draft_pre_freeze_feasibility_execution"
        or classification.get("prospective") is not False
        or classification.get("blinded") is not False
        or classification.get("execution_count") != 15
        or not isinstance(groups, list)
        or len(groups) != 5
        or any(
            not isinstance(group, dict)
            or not isinstance(group.get("repeats"), list)
            or len(group["repeats"]) != 3
            for group in groups
        )
    ):
        return {}

    patterns = tuple(
        re.compile(pattern)
        for pattern in (
            r"protocol_state\.draft_artifacts\[[0-9]+\]\.sha256",
            r"task\.(?:base_commit|base_tree|environment_setup_commit)",
            r"task\.canonical_row\.sha256",
            r"task\.oracle_tests\.test_patch_sha256",
            r"task\.patches\[[0-9]+\]\.sha256",
            r"sources\.canonical_dataset\.(?:revision|retrieval_revision|sha256)",
            r"sources\.matched_acquisition_manifest\.sha256",
            r"sources\.base_source_archive\.(?:sha256|commit|tree)",
            r"harness\.commit",
            r"harness\.files\[[0-9]+\]\.sha256",
            r"runtime\.python\.(?:archive_sha256|binary_sha256)",
            r"evidence_bundle\.sha256",
            r"execution_groups\[[0-9]+\]\.input_patch_sha256",
            r"execution_groups\[[0-9]+\]\.repeats\[[0-9]+\]\."
            r"(?:observation\.sha256|artifact\.sha256|request_sha256|"
            r"stdout\.sha256|stderr\.sha256)",
            r"hosted_prior_measurements\[[0-9]+\]\.report_sha256",
        )
    )
    declared = _json_hex_fields(value)
    if not declared or any(
        not _matches_any_path(field, patterns) for _raw, field, _key in declared
    ):
        return {}
    return _render_json_provenance_identities(text, declared)


def _canonical_json_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _declared_prospective_prehistory_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify only recomputable chain and checked-in evidence identities."""

    if tuple(path.parts[-len(_PROSPECTIVE_PREHISTORY_SUFFIX) :]) != (
        _PROSPECTIVE_PREHISTORY_SUFFIX
    ):
        return {}
    if not _matches_exact_public_record(
        path,
        expected_bytes=_PROSPECTIVE_PREHISTORY_BYTES,
        expected_digest=_PROSPECTIVE_PREHISTORY_DIGEST,
    ) or not _matches_exact_public_record(
        path.with_name("validate_protocol.py"),
        expected_bytes=_PROSPECTIVE_VALIDATOR_BYTES,
        expected_digest=_PROSPECTIVE_VALIDATOR_DIGEST,
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
        {
            "schema_version",
            "study_id",
            "append_only_contract",
            "events",
            "chain_head_sha256",
        },
    ):
        return {}
    contract = "bench-cleanser-prospective-pilot-prehistory-chain-v1"
    events = value["events"]
    if (
        value["schema_version"] != "prospective-pilot-prehistory-0.1.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["append_only_contract"] != contract
        or not isinstance(events, list)
        or len(events) != 2
    ):
        return {}

    prior_head = "0" * 64
    classified_paths: set[str] = {"chain_head_sha256"}
    for index, event in enumerate(events, 1):
        if not _exact_keys(
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
        ):
            return {}
        if event["sequence"] != index or event["prior_chain_head_sha256"] != prior_head:
            return {}
        payload = dict(event)
        supplied_event = payload.pop("event_sha256")
        supplied_head = payload.pop("chain_head_sha256")
        if (
            not isinstance(supplied_event, str)
            or not _SHA256_HEX_RE.fullmatch(supplied_event)
            or not isinstance(supplied_head, str)
            or not _SHA256_HEX_RE.fullmatch(supplied_head)
            or supplied_event != _canonical_json_sha256(payload)
            or supplied_head
            != _canonical_json_sha256(
                {
                    "contract": contract,
                    "prior_chain_head_sha256": prior_head,
                    "event_sha256": supplied_event,
                }
            )
        ):
            return {}
        classified_paths.update(
            {
                f"events[{index - 1}].prior_chain_head_sha256",
                f"events[{index - 1}].event_sha256",
                f"events[{index - 1}].chain_head_sha256",
            }
        )
        prior_head = supplied_head
    if value["chain_head_sha256"] != prior_head:
        return {}

    record_contracts = (
        (
            "sympy__sympy-15976",
            "experiments/independent_execution_smoke/evidence-manifest.json",
            "independent-execution-smoke-0.1.0",
            "sympy-15976-container-free-post-draft-pre-freeze-feasibility-v1",
        ),
        (
            "sphinx-doc__sphinx-8475",
            "experiments/sphinx_execution_smoke/evidence-manifest.json",
            "sphinx-execution-smoke-0.1.0",
            "sphinx-8475-container-free-post-draft-pre-freeze-feasibility-v2",
        ),
    )
    root = path.parents[2]
    for index, contract_fields in enumerate(record_contracts):
        task_id, logical_path, schema_version, study_id = contract_fields
        event = events[index]
        evidence_record = event.get("evidence_record")
        evidence_path = root.joinpath(*PurePosixPath(logical_path).parts)
        try:
            evidence = _load_json(evidence_path)
            evidence_bytes = evidence_path.read_bytes()
        except (AuditInputError, OSError):
            return {}
        expected_record_keys = {
            "logical_path",
            "schema_version",
            "study_id",
            "sha256",
            "external_bundle_bytes",
            "external_bundle_sha256",
        }
        if index == 1:
            expected_record_keys.update(
                {
                    "external_bundle_index",
                    "external_bundle_environment",
                    "external_bundle_runner",
                }
            )
        manifest_declared = (
            _declared_independent_smoke_manifest_hashes(evidence_path)
            if index == 0
            else _declared_sphinx_smoke_manifest_hashes(evidence_path)
        )
        bundle = evidence.get("evidence_bundle") if isinstance(evidence, dict) else None
        if (
            event.get("classification") != "post_draft_pre_freeze_feasibility_execution"
            or event.get("task_id") != task_id
            or not _exact_keys(evidence_record, expected_record_keys)
            or evidence_record["logical_path"] != logical_path
            or evidence_record["schema_version"] != schema_version
            or evidence_record["study_id"] != study_id
            or evidence_record["sha256"] != hashlib.sha256(evidence_bytes).hexdigest()
            or not isinstance(bundle, dict)
            or evidence_record["external_bundle_bytes"] != bundle.get("bytes")
            or evidence_record["external_bundle_sha256"] != bundle.get("sha256")
            or not manifest_declared
        ):
            return {}
        classified_paths.add(f"events[{index}].evidence_record.sha256")

    patterns = tuple(
        re.compile(pattern)
        for pattern in (
            r"events\[[0-9]+\]\.draft_artifacts\[[0-9]+\]\.sha256",
            r"events\[[0-9]+\]\.evidence_record\."
            r"(?:sha256|external_bundle_sha256|"
            r"external_bundle_(?:index|environment|runner)\.sha256)",
            r"events\[[0-9]+\]\.(?:prior_chain_head_sha256|event_sha256|chain_head_sha256)",
            r"chain_head_sha256",
        )
    )
    declared = _json_hex_fields(value)
    if not declared or any(
        not _matches_any_path(field, patterns) for _raw, field, _key in declared
    ):
        return {}
    if not classified_paths.issubset({field for _raw, field, _key in declared}):
        return {}
    unverified_fields = {field for _raw, field, _key in declared if field not in classified_paths}
    rendered = _render_json_provenance_identities(text, declared)
    return _label_unverified_provenance(rendered, unverified_fields)


def _declared_prospective_protocol_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify only source- and prehistory-bound protocol identities."""

    if tuple(path.parts[-len(_PROSPECTIVE_PROTOCOL_SUFFIX) :]) != (_PROSPECTIVE_PROTOCOL_SUFFIX):
        return {}
    if not _matches_exact_public_record(
        path,
        expected_bytes=_PROSPECTIVE_PROTOCOL_BYTES,
        expected_digest=_PROSPECTIVE_PROTOCOL_DIGEST,
    ) or not _matches_exact_public_record(
        path.with_name("validate_protocol.py"),
        expected_bytes=_PROSPECTIVE_VALIDATOR_BYTES,
        expected_digest=_PROSPECTIVE_VALIDATOR_DIGEST,
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
        {
            "schema_version",
            "study_id",
            "status",
            "claim_scope",
            "frozen_inputs",
            "knowledge_boundary",
            "prehistory",
            "activation_configuration",
            "unit_of_analysis",
            "primary_estimand",
            "secondary_estimands",
            "evidence_actions",
            "behavior_policy",
            "execution_protocol",
            "adjudication_protocol",
            "cost_ledger",
            "baselines",
            "stopping_and_power",
            "go_no_go",
            "activation_readiness",
            "required_release_objects",
            "deviation_policy",
        },
    ):
        return {}
    scope = value["claim_scope"]
    if (
        value["schema_version"] != "prospective-evidence-routing-protocol-0.3.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "draft_post_feasibility_execution_not_registered"
        or not isinstance(scope, dict)
        or scope.get("confirmatory") is not False
        or scope.get("hypotheses_supported") != []
    ):
        return {}
    readiness = value["activation_readiness"]
    evidence_actions = value["evidence_actions"]
    if (
        not _exact_keys(
            readiness,
            {
                "ready",
                "missing",
                "external_freeze_receipt_required",
                "activation_command_policy",
            },
        )
        or readiness["ready"] is not False
        or readiness["missing"] != list(_PROSPECTIVE_ACTIVATION_BLOCKERS)
        or readiness["external_freeze_receipt_required"] is not True
        or readiness["activation_command_policy"]
        != (
            "validation must fail closed while ready is false, any configured "
            "binding is unavailable, or the external clean-commit freeze receipt "
            "is absent"
        )
        or not isinstance(evidence_actions, dict)
        or evidence_actions.get("deterministic_initial") != ["static patch and repository features"]
        or evidence_actions.get("disclosed_nonpolicy_action_ids")
        != ["hardening_curator", "static_bootstrap"]
    ):
        return {}
    binding = value["prehistory"]
    prehistory_path = path.with_name("prehistory.json")
    try:
        prehistory_bytes = prehistory_path.read_bytes()
        prehistory = _load_json(prehistory_path)
    except (AuditInputError, OSError):
        return {}
    if (
        not isinstance(binding, dict)
        or binding.get("required_record") != "experiments/prospective_pilot/prehistory.json"
        or binding.get("bytes") != len(prehistory_bytes)
        or binding.get("sha256") != hashlib.sha256(prehistory_bytes).hexdigest()
        or binding.get("chain_head_sha256") != prehistory.get("chain_head_sha256")
        or not _declared_prospective_prehistory_hashes(prehistory_path)
    ):
        return {}

    activation = value["activation_configuration"]
    if not _exact_keys(activation, {"schema_version", "objects"}) or (
        activation["schema_version"] != "prospective-pilot-activation-configuration-0.1.0"
    ):
        return {}
    objects = activation["objects"]
    object_contracts = (
        ("adjudication_config", "experiments/prospective_pilot/adjudication_plan.json"),
        ("analysis_plan", "experiments/prospective_pilot/analysis_plan.json"),
        ("collection_policy", "experiments/prospective_pilot/collection_policy.json"),
        ("execution_config", "experiments/prospective_pilot/execution_freeze.json"),
        ("frame_manifest", "experiments/prospective_pilot/frame_manifest.json"),
        ("resource_ceiling", "experiments/prospective_pilot/resource_ceiling.json"),
        ("scheduler_contract", "experiments/prospective_pilot/scheduler_contract.json"),
    )
    if not isinstance(objects, list) or len(objects) != len(object_contracts):
        return {}
    root = path.parents[2]
    classified_paths = {"prehistory.sha256", "prehistory.chain_head_sha256"}
    for index, (role, logical_path) in enumerate(object_contracts):
        binding = objects[index]
        local_path = root.joinpath(*PurePosixPath(logical_path).parts)
        try:
            payload = local_path.read_bytes()
        except OSError:
            return {}
        if (
            not _exact_keys(binding, {"role", "logical_path", "bytes", "sha256"})
            or binding["role"] != role
            or binding["logical_path"] != logical_path
            or local_path.is_symlink()
            or not local_path.is_file()
            or not payload
            or len(payload) > _MAX_MEMBER_BYTES
            or binding["bytes"] != len(payload)
            or binding["sha256"] != hashlib.sha256(payload).hexdigest()
        ):
            return {}
        classified_paths.add(f"activation_configuration.objects[{index}].sha256")

    patterns = tuple(
        re.compile(pattern)
        for pattern in (
            r"frozen_inputs\."
            r"(?:acquisition_manifest_sha256|cohort_identity_sha256|"
            r"selected_task_identities_sha256|matched_study_code_sha256)",
            r"prehistory\.(?:sha256|chain_head_sha256)",
            r"activation_configuration\.objects\[[0-9]+\]\.sha256",
        )
    )
    declared = _json_hex_fields(value)
    if not declared or any(
        not _matches_any_path(field, patterns) for _raw, field, _key in declared
    ):
        return {}
    if not classified_paths.issubset({field for _raw, field, _key in declared}):
        return {}
    unverified_fields = {field for _raw, field, _key in declared if field not in classified_paths}
    rendered = _render_json_provenance_identities(text, declared)
    return _label_unverified_provenance(rendered, unverified_fields)


def _prospective_root(path: Path, suffix: tuple[str, ...]) -> Path | None:
    if tuple(path.parts[-len(suffix) :]) != suffix:
        return None
    try:
        root = path.parents[2]
    except IndexError:
        return None
    expected = root.joinpath(*suffix)
    return root if expected == path else None


def _read_regular_bounded(path: Path) -> bytes | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if path.is_symlink() or not path.is_file() or not payload or len(payload) > _MAX_MEMBER_BYTES:
        return None
    return payload


def _python_source_contract_matches(
    payload: bytes,
    *,
    string_assignments: Mapping[str, str],
    required_classes: Iterable[str] = (),
    required_functions: Iterable[str] = (),
) -> bool:
    """Check public source symbols without importing or executing the module."""

    try:
        module = ast.parse(payload.decode("utf-8"))
    except (SyntaxError, UnicodeError):
        return False
    assignments = {
        target.id: node.value.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    classes = {node.name for node in module.body if isinstance(node, ast.ClassDef)}
    functions = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return (
        all(assignments.get(name) == expected for name, expected in string_assignments.items())
        and set(required_classes).issubset(classes)
        and set(required_functions).issubset(functions)
    )


def _protocol_activation_binds(
    root: Path,
    *,
    role: str,
    logical_path: str,
    payload: bytes,
) -> bool:
    protocol_path = root / "experiments" / "prospective_pilot" / "preregistration.json"
    if not _declared_prospective_protocol_hashes(protocol_path):
        return False
    try:
        protocol = _load_json(protocol_path)
    except AuditInputError:
        return False
    activation = protocol.get("activation_configuration")
    objects = activation.get("objects") if isinstance(activation, dict) else None
    if not isinstance(objects, list):
        return False
    matches = [
        binding
        for binding in objects
        if isinstance(binding, dict)
        and binding.get("role") == role
        and binding.get("logical_path") == logical_path
    ]
    return (
        len(matches) == 1
        and matches[0].get("bytes") == len(payload)
        and (matches[0].get("sha256") == hashlib.sha256(payload).hexdigest())
    )


def _declared_prospective_analysis_plan_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify a protocol-bound analysis seed and local implementation hashes."""

    root = _prospective_root(path, _PROSPECTIVE_ANALYSIS_PLAN_SUFFIX)
    payload = _read_regular_bounded(path)
    if (
        root is None
        or payload is None
        or not _protocol_activation_binds(
            root,
            role="analysis_plan",
            logical_path="experiments/prospective_pilot/analysis_plan.json",
            payload=payload,
        )
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
        {
            "schema_version",
            "study_id",
            "status",
            "claim_scope",
            "analysis_population",
            "estimands",
            "target_policies",
            "implemented_estimators",
            "off_policy_evaluation",
            "uncertainty",
            "mandatory_outputs",
            "available_bindings",
        },
    ) or (
        value["schema_version"] != "prospective-pilot-analysis-plan-0.1.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "fixed_descriptive_implementations_available"
    ):
        return {}
    bindings = value["available_bindings"]
    binding_contracts = (
        (
            "analysis_implementation",
            "experiments/prospective_pilot/analysis.py",
        ),
        (
            "target_policy_implementation_manifest",
            "experiments/prospective_pilot/target_policy_manifest.json",
        ),
    )
    if not _exact_keys(bindings, {name for name, _logical_path in binding_contracts}):
        return {}
    for name, logical_path in binding_contracts:
        binding = bindings[name]
        local_payload = _read_regular_bounded(root.joinpath(*PurePosixPath(logical_path).parts))
        if (
            not _exact_keys(binding, {"bytes", "logical_path", "sha256", "status"})
            or binding["logical_path"] != logical_path
            or binding["status"] != "available"
            or local_payload is None
            or binding["bytes"] != len(local_payload)
            or binding["sha256"] != hashlib.sha256(local_payload).hexdigest()
        ):
            return {}
    declared = _json_hex_fields(value)
    expected_fields = {
        "uncertainty.sensitivity.bootstrap_seed_sha256",
        "available_bindings.analysis_implementation.sha256",
        "available_bindings.target_policy_implementation_manifest.sha256",
    }
    if {field for _raw, field, _key in declared} != expected_fields:
        return {}
    rendered = _render_json_provenance_identities(text, declared)
    return _label_unverified_provenance(
        rendered,
        {"uncertainty.sensitivity.bootstrap_seed_sha256"},
    )


def _declared_prospective_adjudication_plan_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify protocol-bound local frame and review-packet source identities."""

    root = _prospective_root(path, _PROSPECTIVE_ADJUDICATION_PLAN_SUFFIX)
    payload = _read_regular_bounded(path)
    if (
        root is None
        or payload is None
        or not _protocol_activation_binds(
            root,
            role="adjudication_config",
            logical_path="experiments/prospective_pilot/adjudication_plan.json",
            payload=payload,
        )
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
        {
            "schema_version",
            "study_id",
            "status",
            "scope",
            "blinding",
            "packet_contract",
            "label_contract",
            "aggregation",
            "unavailable_bindings",
            "available_bindings",
        },
    ) or (
        value["schema_version"] != "prospective-pilot-adjudication-plan-0.1.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "packet_generator_available_custodian_and_reviewers_blocking"
    ):
        return {}
    bindings = value["available_bindings"]
    contracts = (
        (
            "frame_manifest",
            "experiments/prospective_pilot/frame_manifest.json",
        ),
        (
            "packet_generator",
            "experiments/prospective_pilot/review_packets.py",
        ),
    )
    if not _exact_keys(bindings, {name for name, _logical_path in contracts}):
        return {}
    for name, logical_path in contracts:
        binding = bindings[name]
        local_payload = _read_regular_bounded(root.joinpath(*PurePosixPath(logical_path).parts))
        if (
            not _exact_keys(binding, {"bytes", "logical_path", "sha256", "status"})
            or binding["logical_path"] != logical_path
            or binding["status"] != "available"
            or local_payload is None
            or binding["bytes"] != len(local_payload)
            or binding["sha256"] != hashlib.sha256(local_payload).hexdigest()
        ):
            return {}
    declared = _json_hex_fields(value)
    expected_fields = {
        "available_bindings.frame_manifest.sha256",
        "available_bindings.packet_generator.sha256",
    }
    if {field for _raw, field, _key in declared} != expected_fields:
        return {}
    return _render_json_provenance_identities(text, declared)


def _declared_prospective_execution_freeze_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify exact protocol-bound external execution identities as unverified."""

    root = _prospective_root(path, _PROSPECTIVE_EXECUTION_FREEZE_SUFFIX)
    payload = _read_regular_bounded(path)
    if (
        root is None
        or payload is None
        or not _protocol_activation_binds(
            root,
            role="execution_config",
            logical_path="experiments/prospective_pilot/execution_freeze.json",
            payload=payload,
        )
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
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
    ) or (
        value["schema_version"] != "prospective-pilot-execution-freeze-0.1.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "blocked_missing_external_execution_identities"
    ):
        return {}
    dataset = value["canonical_dataset"]
    harness = value["harness"]
    if (
        not _exact_keys(dataset, {"parquet_bytes", "parquet_sha256", "provider", "revision"})
        or dataset["provider"] != "princeton-nlp/SWE-bench_Verified"
        or type(dataset["parquet_bytes"]) is not int
        or dataset["parquet_bytes"] < 1
        or not _exact_keys(harness, {"commit", "repository", "tree"})
        or harness["repository"] != "https://github.com/SWE-bench/SWE-bench"
    ):
        return {}
    declared = _json_hex_fields(value)
    expected_fields = {
        "canonical_dataset.parquet_sha256",
        "canonical_dataset.revision",
        "harness.commit",
        "harness.tree",
    }
    if {field for _raw, field, _key in declared} != expected_fields:
        return {}
    rendered = _render_json_provenance_identities(text, declared)
    return _label_unverified_provenance(rendered, expected_fields)


def _declared_prospective_target_policy_manifest_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify the analysis-plan-bound target-policy implementation digest."""

    root = _prospective_root(path, _PROSPECTIVE_TARGET_POLICY_MANIFEST_SUFFIX)
    payload = _read_regular_bounded(path)
    if root is None or payload is None:
        return {}
    analysis_path = root / "experiments" / "prospective_pilot" / "analysis_plan.json"
    if not _declared_prospective_analysis_plan_hashes(analysis_path):
        return {}
    try:
        analysis = _load_json(analysis_path)
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    binding = analysis.get("available_bindings", {}).get("target_policy_implementation_manifest")
    implementation = value.get("implementation") if isinstance(value, dict) else None
    source_path = root / "experiments" / "prospective_pilot" / "target_policies.py"
    source_payload = _read_regular_bounded(source_path)
    if (
        not isinstance(binding, dict)
        or binding.get("bytes") != len(payload)
        or binding.get("sha256") != hashlib.sha256(payload).hexdigest()
        or not _exact_keys(
            value,
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
        )
        or value["schema_version"] != "prospective-pilot-target-policy-manifest-0.1.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "fixed_descriptive_ope_implementation_no_performance_claim"
        or not isinstance(implementation, dict)
        or not _exact_keys(
            implementation,
            {"bytes", "logical_path", "sha256", "status"},
        )
        or implementation["logical_path"] != "experiments/prospective_pilot/target_policies.py"
        or implementation["status"] != "available"
        or source_payload is None
        or implementation["bytes"] != len(source_payload)
        or implementation["sha256"] != hashlib.sha256(source_payload).hexdigest()
    ):
        return {}
    declared = _json_hex_fields(value)
    if [field for _raw, field, _key in declared] != ["implementation.sha256"]:
        return {}
    return _render_json_provenance_identities(text, declared)


def _declared_prospective_collection_policy_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify only embedded or checked-in local implementation bindings."""

    root = _prospective_root(path, _PROSPECTIVE_COLLECTION_POLICY_SUFFIX)
    if root is None or not _matches_exact_public_record(
        path,
        expected_bytes=_PROSPECTIVE_COLLECTION_POLICY_BYTES,
        expected_digest=_PROSPECTIVE_COLLECTION_POLICY_DIGEST,
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
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
    ) or (
        value["schema_version"] != "prospective-pilot-collection-policy-0.3.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "core_implemented_operationally_blocked"
    ):
        return {}
    preferred = value["preferred_action_rule"]
    router = preferred.get("router") if isinstance(preferred, dict) else None
    proposal = preferred.get("proposal_policy") if isinstance(preferred, dict) else None
    if (
        not _exact_keys(
            preferred,
            {
                "fallback_when_router_action_is_unavailable",
                "multiple_concrete_offers_for_one_kind",
                "router",
                "proposal_policy",
                "rule",
            },
        )
        or preferred["fallback_when_router_action_is_unavailable"]
        != (
            "semantic_primary_then_targeted_primary_then_full_primary_then_full_repeat_then_abstain"
        )
        or preferred["multiple_concrete_offers_for_one_kind"] != "lowest_lexicographic_action_id"
        or preferred["rule"]
        != ("use_fallible_terminal_proposal_else_router_match_else_frozen_available_fallback")
        or not isinstance(router, dict)
        or not _exact_keys(
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
        )
        or not isinstance(proposal, dict)
        or not _exact_keys(
            proposal,
            {"config_sha256", "logical_path", "sha256", "version"},
        )
    ):
        return {}
    router_path = root / "bench_cleanser" / "verification" / "router.py"
    router_bytes = _read_regular_bounded(router_path)
    proposal_path = root.joinpath(*PurePosixPath(_PROSPECTIVE_PROPOSAL_POLICY_PATH).parts)
    proposal_bytes = _read_regular_bounded(proposal_path)
    if (
        router["logical_path"] != "bench_cleanser/verification/router.py"
        or not isinstance(router["policy_config"], dict)
        or router["policy_config_sha256"] != _canonical_json_sha256(router["policy_config"])
        or router_bytes is None
        or router["sha256"] != hashlib.sha256(router_bytes).hexdigest()
        or router["policy_version"] != router["policy_config"].get("version")
        or proposal["logical_path"] != _PROSPECTIVE_PROPOSAL_POLICY_PATH
        or proposal["version"] != "verification-gap-proposal-v1"
        or proposal["config_sha256"] != _canonical_json_sha256(_PROSPECTIVE_PROPOSAL_POLICY_CONFIG)
        or proposal_bytes is None
        or proposal["sha256"] != hashlib.sha256(proposal_bytes).hexdigest()
        or not _python_source_contract_matches(
            proposal_bytes,
            string_assignments={
                "PROPOSAL_POLICY_VERSION": "verification-gap-proposal-v1",
                "PROPOSAL_POLICY_SCHEMA_VERSION": ("prospective-pilot-terminal-proposal-0.1.0"),
            },
            required_classes={"TerminalProposal"},
            required_functions={"preferred_action_id", "terminal_proposal"},
        )
    ):
        return {}
    behavior = value["behavior_policy"]
    terminal = value["terminal_admissibility"]
    availability_reasons = (
        behavior.get("availability_reason_allowlist") if isinstance(behavior, dict) else None
    )
    availability_rules = behavior.get("availability_rules") if isinstance(behavior, dict) else None
    if (
        not isinstance(behavior, dict)
        or behavior.get("disclosed_action_count") != 9
        or behavior.get("maximum_available_actions") != 7
        or behavior.get("unavailable_actions_receive_zero_probability") is not True
        or not isinstance(availability_reasons, list)
        or "deterministic_bootstrap_completed" not in availability_reasons
        or not isinstance(availability_rules, dict)
        or availability_rules.get("static_bootstrap")
        != (
            "collected_deterministically_before_the_first_randomized_decision_"
            "and_therefore_disclosed_but_permanently_unavailable_to_the_behavior_"
            "policy"
        )
        or not _exact_keys(
            terminal,
            {
                "abstain",
                "accept",
                "error_unavailable_inconclusive_or_disagreement",
                "interpretation",
                "reject",
                "terminal_decisions_are_sampled_and_propensity_logged",
            },
        )
        or terminal["abstain"] != "always_available"
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
        return {}
    bindings = value["implementation_bindings"]
    if not _exact_keys(
        bindings,
        {"frame_manifest", "policy_log", "proposal_policy", "task_scheduler"},
    ):
        return {}
    binding_contracts = (
        (
            "frame_manifest",
            "experiments/prospective_pilot/frame_manifest.json",
            "frozen_uncommitted",
        ),
        (
            "policy_log",
            "bench_cleanser/verification/policy_log.py",
            "available_uncommitted",
        ),
        (
            "proposal_policy",
            _PROSPECTIVE_PROPOSAL_POLICY_PATH,
            "available_uncommitted",
        ),
        (
            "task_scheduler",
            "experiments/prospective_pilot/scheduler.py",
            "core_available_operationally_blocked",
        ),
    )
    for name, logical_path, status in binding_contracts:
        binding = bindings[name]
        expected_keys = {"logical_path", "sha256", "status"}
        if name == "task_scheduler":
            expected_keys.add("blocking")
        local_path = root.joinpath(*PurePosixPath(logical_path).parts)
        payload = _read_regular_bounded(local_path)
        if (
            not _exact_keys(binding, expected_keys)
            or binding["logical_path"] != logical_path
            or binding["status"] != status
            or (name == "task_scheduler" and binding["blocking"] is not True)
            or payload is None
            or binding["sha256"] != hashlib.sha256(payload).hexdigest()
            or (
                name == "policy_log"
                and not _python_source_contract_matches(
                    payload,
                    string_assignments={},
                    required_classes={"BootstrapHistoryStep", "RouterStateView"},
                    required_functions={
                        "sample_behavior_action",
                        "validate_policy_decision_chain",
                    },
                )
            )
            or (name == "proposal_policy" and payload != proposal_bytes)
        ):
            return {}

    declared = _json_hex_fields(value)
    allowed_patterns = tuple(
        re.compile(pattern)
        for pattern in (
            r"rng\.(?:action_draws|candidate_order|task_order)\.seed_sha256",
            r"preferred_action_rule\.router\.(?:policy_config_sha256|sha256)",
            r"preferred_action_rule\.proposal_policy\.(?:config_sha256|sha256)",
            r"implementation_bindings\."
            r"(?:frame_manifest|policy_log|proposal_policy|task_scheduler)\.sha256",
        )
    )
    classified_paths = {
        "preferred_action_rule.router.policy_config_sha256",
        "preferred_action_rule.router.sha256",
        "preferred_action_rule.proposal_policy.config_sha256",
        "preferred_action_rule.proposal_policy.sha256",
        "implementation_bindings.frame_manifest.sha256",
        "implementation_bindings.policy_log.sha256",
        "implementation_bindings.proposal_policy.sha256",
        "implementation_bindings.task_scheduler.sha256",
    }
    if not declared or any(
        not _matches_any_path(field, allowed_patterns) for _raw, field, _key in declared
    ):
        return {}
    if not classified_paths.issubset({field for _raw, field, _key in declared}):
        return {}
    unverified_fields = {field for _raw, field, _key in declared if field.startswith("rng.")}
    rendered = _render_json_provenance_identities(text, declared)
    return _label_unverified_provenance(rendered, unverified_fields)


def _declared_prospective_frame_hashes(path: Path) -> dict[tuple[str, int], str]:
    """Classify the three projections recomputed from the exact inline frame."""

    if _prospective_root(path, _PROSPECTIVE_FRAME_MANIFEST_SUFFIX) is None or not (
        _matches_exact_public_record(
            path,
            expected_bytes=_PROSPECTIVE_FRAME_MANIFEST_BYTES,
            expected_digest=_PROSPECTIVE_FRAME_MANIFEST_DIGEST,
        )
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
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
    ) or (
        value["schema_version"] != "prospective-pilot-frame-manifest-0.1.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"] != "frozen_uncommitted"
        or value["excluded_task_clusters"] != ["sympy__sympy-15976", "sphinx-doc__sphinx-8475"]
        or value["task_count"] != 22
        or value["candidates_per_task"] != 3
        or value["candidate_count"] != 66
    ):
        return {}
    tasks = value["tasks"]
    if not isinstance(tasks, list) or len(tasks) != 22:
        return {}
    normalized: list[dict[str, Any]] = []
    task_ids: list[str] = []
    candidate_ids: list[str] = []
    for item in tasks:
        if not _exact_keys(item, {"task_id", "candidate_ids"}):
            return {}
        task_id = item["task_id"]
        candidates = item["candidate_ids"]
        if (
            not isinstance(task_id, str)
            or not isinstance(candidates, list)
            or len(candidates) != 3
            or candidates != sorted(candidates)
            or len(set(candidates)) != 3
            or any(
                not isinstance(candidate, str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", candidate) is None
                for candidate in candidates
            )
        ):
            return {}
        task_ids.append(task_id)
        candidate_ids.extend(candidates)
        normalized.append({"task_id": task_id, "candidate_ids": candidates})
    expected = {
        "task_ids_sha256": _canonical_json_sha256(task_ids),
        "candidate_ids_sha256": _canonical_json_sha256(sorted(candidate_ids)),
        "tasks_sha256": _canonical_json_sha256(normalized),
    }
    if (
        task_ids != sorted(set(task_ids))
        or len(candidate_ids) != len(set(candidate_ids))
        or any(value[key] != digest for key, digest in expected.items())
    ):
        return {}
    declared = _json_hex_fields(value)
    allowed_patterns = tuple(
        re.compile(pattern)
        for pattern in (
            r"source_feature_freeze\.(?:sha256|selected_instance_ids_sha256|selected_task_identities_sha256)",
            r"(?:task_ids_sha256|candidate_ids_sha256|tasks_sha256)",
        )
    )
    if not declared or any(
        not _matches_any_path(field, allowed_patterns) for _raw, field, _key in declared
    ):
        return {}
    if not set(expected).issubset({field for _raw, field, _key in declared}):
        return {}
    unverified_fields = {
        field for _raw, field, _key in declared if field.startswith("source_feature_freeze.")
    }
    rendered = _render_json_provenance_identities(text, declared)
    return _label_unverified_provenance(rendered, unverified_fields)


def _declared_prospective_scheduler_contract_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify the scheduler's exact local code and structural bindings."""

    root = _prospective_root(path, _PROSPECTIVE_SCHEDULER_CONTRACT_SUFFIX)
    if root is None or not _matches_exact_public_record(
        path,
        expected_bytes=_PROSPECTIVE_SCHEDULER_CONTRACT_BYTES,
        expected_digest=_PROSPECTIVE_SCHEDULER_CONTRACT_DIGEST,
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(
        value,
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
    ) or (
        value["schema_version"] != "prospective-pilot-scheduler-contract-0.4.0"
        or value["study_id"] != "matched-24-independent-evidence-development-pilot-v2"
        or value["status"]
        != (
            "scheduler_bootstrap_proposal_ledger_and_dispatcher_core_implemented_"
            "operationally_blocked"
        )
    ):
        return {}
    policy_crosswalk = value["policy_log_crosswalk"]
    candidate_chain = value["candidate_chain"]
    if (
        not isinstance(policy_crosswalk, dict)
        or policy_crosswalk.get("bootstrap_history")
        != (
            "one_candidate_bound_static_receipt_is_required_before_round_zero_and_"
            "is_hash_bound_as_an_immutable_prefix_but_never_counted_as_a_"
            "randomized_policy_decision_propensity_or_trajectory_step"
        )
        or not isinstance(candidate_chain, dict)
        or candidate_chain.get("fresh_worktree_preimage_required_for_full_repeat") is not True
        or candidate_chain.get("repeat_action_spec_must_differ_from_primary") is not True
        or candidate_chain.get("terminal_actions") != ["accept", "reject", "abstain"]
    ):
        return {}
    operational = value["operational_requirements"]
    if operational != {
        "aggregate_resource_and_partial_frame_runtime": {
            "availability": "unavailable",
            "blocking": True,
            "reason": (
                "validated_resource_ceiling_has_no_runtime_reservation_settlement_"
                "or_partial_frame_report_path"
            ),
        },
        "bootstrap_and_terminal_proposal_policy": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "typed_bootstrap_prefix_and_fallible_paired_full_terminal_"
                "proposals_are_source_bound_but_no_signed_durable_bootstrap_"
                "acquisition_substrate_or_populated_receipts_exist"
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
            "availability": "unavailable",
            "blocking": True,
            "reason": (
                "bootstrap_curator_adjudication_substrate_and_resource_events_"
                "have_no_durable_ledger"
            ),
        },
        "trusted_study_bundle_compiler": {
            "availability": "partial",
            "blocking": True,
            "reason": (
                "externally_anchored_structural_compiler_derives_policy_terminal_"
                "selection_and_cost_declarations_but_typed_signed_nonpolicy_"
                "scientific_inputs_are_missing"
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
    }:
        return {}

    frame = value["frame_manifest"]
    frame_path = "experiments/prospective_pilot/frame_manifest.json"
    frame_payload = _read_regular_bounded(root.joinpath(*PurePosixPath(frame_path).parts))
    if (
        not _exact_keys(frame, {"logical_path", "sha256", "status"})
        or frame["logical_path"] != frame_path
        or frame["status"] != "frozen_uncommitted"
        or frame_payload is None
        or frame["sha256"] != hashlib.sha256(frame_payload).hexdigest()
    ):
        return {}

    implementation = value["implementation"]
    if (
        not _exact_keys(
            implementation,
            {
                "blocking",
                "scheduler",
                "proposal_policy",
                "ledger",
                "dispatcher",
                "structural_release_bundle_compiler",
                "completed_acquisition_validator",
                "status",
            },
        )
        or implementation["blocking"] is not True
        or implementation["status"]
        != (
            "scheduler_bootstrap_proposal_ledger_dispatcher_and_structural_bundle_"
            "core_available_scientific_activation_inputs_missing"
        )
    ):
        return {}

    scheduler = implementation["scheduler"]
    proposal = implementation["proposal_policy"]
    ledger = implementation["ledger"]
    dispatcher = implementation["dispatcher"]
    release_bundle = implementation["structural_release_bundle_compiler"]
    completed_validator = implementation["completed_acquisition_validator"]
    binding_contracts = (
        (
            scheduler,
            {"logical_path", "sha256"},
            "experiments/prospective_pilot/scheduler.py",
        ),
        (
            proposal,
            {"config_sha256", "logical_path", "schema_version", "sha256", "version"},
            _PROSPECTIVE_PROPOSAL_POLICY_PATH,
        ),
        (
            ledger,
            {"logical_path", "schema_version", "scope", "sha256"},
            "experiments/prospective_pilot/ledger.py",
        ),
        (
            dispatcher,
            {"logical_path", "sha256"},
            "experiments/prospective_pilot/dispatcher.py",
        ),
        (
            release_bundle,
            {"logical_path", "profile", "schema_version", "sha256", "trust_model"},
            _PROSPECTIVE_RELEASE_BUNDLE_PATH,
        ),
        (
            completed_validator,
            {"entrypoint", "logical_path", "sha256"},
            "bench_cleanser/verification/orchestrate.py",
        ),
    )
    for binding, expected_keys, logical_path in binding_contracts:
        payload = _read_regular_bounded(root.joinpath(*PurePosixPath(logical_path).parts))
        if (
            not _exact_keys(binding, expected_keys)
            or binding["logical_path"] != logical_path
            or payload is None
            or binding["sha256"] != hashlib.sha256(payload).hexdigest()
        ):
            return {}
    if (
        proposal["config_sha256"] != _canonical_json_sha256(_PROSPECTIVE_PROPOSAL_POLICY_CONFIG)
        or proposal["schema_version"] != "prospective-pilot-terminal-proposal-0.1.0"
        or proposal["version"] != "verification-gap-proposal-v1"
        or ledger["schema_version"] != "prospective-pilot-ledger-0.1.0"
        or ledger["scope"] != "single_host_local_durable_filesystem"
        or release_bundle["profile"] != "STRUCTURAL"
        or release_bundle["schema_version"] != "verification-gap-study-bundle-0.1.0"
        or release_bundle["trust_model"] != "out_of_band_sha256_v1"
        or completed_validator["entrypoint"] != "validate_completed_route_acquisition"
    ):
        return {}
    proposal_payload = _read_regular_bounded(
        root.joinpath(*PurePosixPath(_PROSPECTIVE_PROPOSAL_POLICY_PATH).parts)
    )
    release_payload = _read_regular_bounded(
        root.joinpath(*PurePosixPath(_PROSPECTIVE_RELEASE_BUNDLE_PATH).parts)
    )
    if (
        proposal_payload is None
        or release_payload is None
        or not _python_source_contract_matches(
            proposal_payload,
            string_assignments={
                "PROPOSAL_POLICY_VERSION": "verification-gap-proposal-v1",
                "PROPOSAL_POLICY_SCHEMA_VERSION": ("prospective-pilot-terminal-proposal-0.1.0"),
            },
            required_classes={"TerminalProposal"},
            required_functions={"preferred_action_id", "terminal_proposal"},
        )
        or not _python_source_contract_matches(
            release_payload,
            string_assignments={
                "STRUCTURAL_BUNDLE_SCHEMA_VERSION": ("verification-gap-study-bundle-0.1.0"),
                "TRUST_MODEL": "out_of_band_sha256_v1",
            },
            required_classes={"AuditedLedgerSnapshot", "ProspectiveReleaseBundle"},
            required_functions={
                "compile_prospective_release",
                "write_prospective_release_bundle",
            },
        )
    ):
        return {}

    declared = _json_hex_fields(value)
    classified_paths = {
        "frame_manifest.sha256",
        "implementation.scheduler.sha256",
        "implementation.proposal_policy.config_sha256",
        "implementation.proposal_policy.sha256",
        "implementation.ledger.sha256",
        "implementation.dispatcher.sha256",
        "implementation.structural_release_bundle_compiler.sha256",
        "implementation.completed_acquisition_validator.sha256",
    }
    if {field for _raw, field, _key in declared} != classified_paths:
        return {}
    return _render_json_provenance_identities(text, declared)


def _declared_prospective_scheduler_source_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify exact scheduler SHA/RNG constants against validated records."""

    root = _prospective_root(path, _PROSPECTIVE_SCHEDULER_SOURCE_SUFFIX)
    if root is None or not _matches_exact_public_record(
        path,
        expected_bytes=_PROSPECTIVE_SCHEDULER_SOURCE_BYTES,
        expected_digest=_PROSPECTIVE_SCHEDULER_SOURCE_DIGEST,
    ):
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
        policy_path = root.joinpath(*_PROSPECTIVE_COLLECTION_POLICY_SUFFIX)
        frame_path = root.joinpath(*_PROSPECTIVE_FRAME_MANIFEST_SUFFIX)
        policy = _load_json(policy_path)
        frame = _load_json(frame_path)
    except (AuditInputError, OSError, UnicodeError, SyntaxError):
        return {}
    if (
        not _declared_prospective_protocol_hashes(
            root / "experiments" / "prospective_pilot" / "preregistration.json"
        )
        or not _declared_prospective_collection_policy_hashes(policy_path)
        or not _declared_prospective_frame_hashes(frame_path)
    ):
        return {}
    router_bytes = _read_regular_bounded(root / "bench_cleanser" / "verification" / "router.py")
    if router_bytes is None:
        return {}
    router_digest = hashlib.sha256(router_bytes).hexdigest()
    assignments: dict[str, ast.Assign] = {
        target.id: node
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assignment = assignments.get("ROUTER_SOURCE_SHA256")
    rng = policy.get("rng") if isinstance(policy, dict) else None
    source_freeze = frame.get("source_feature_freeze") if isinstance(frame, dict) else None
    if (
        assignment is None
        or not isinstance(assignment.value, ast.Constant)
        or assignment.value.value != router_digest
        or not isinstance(rng, dict)
        or not isinstance(source_freeze, dict)
        or policy.get("implementation_bindings", {}).get("task_scheduler", {}).get("sha256")
        != hashlib.sha256(path.read_bytes()).hexdigest()
        or policy.get("preferred_action_rule", {}).get("router", {}).get("sha256") != router_digest
    ):
        return {}
    allowed_values = {
        router_digest,
        *(
            binding.get("seed_sha256")
            for name in ("action_draws", "candidate_order", "task_order")
            for binding in [rng.get(name)]
            if isinstance(binding, dict)
        ),
        source_freeze.get("sha256"),
        source_freeze.get("selected_instance_ids_sha256"),
        source_freeze.get("selected_task_identities_sha256"),
    }
    if any(
        not isinstance(value, str) or _SHA256_HEX_RE.fullmatch(value) is None
        for value in allowed_values
    ):
        return {}
    constants = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _SHA256_HEX_RE.fullmatch(node.value)
    ]
    if not constants or any(node.value not in allowed_values for node in constants):
        return {}
    lines = text.splitlines()
    router_line = assignment.value.lineno
    result: dict[tuple[str, int], str] = {}
    for node in constants:
        raw_value = node.value
        if not isinstance(raw_value, str) or raw_value not in lines[node.lineno - 1]:
            return {}
        identity = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()  # noqa: S324
        label = (
            "ROUTER_SOURCE_SHA256"
            if node.lineno == router_line
            else f"declared_unverified:source_constant_line_{node.lineno}"
        )
        result[(identity, node.lineno)] = label
    return result


def _declared_prospective_review_packet_source_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify exact review-source frame anchors as declared and unverified."""

    root = _prospective_root(path, _PROSPECTIVE_REVIEW_PACKET_SOURCE_SUFFIX)
    if root is None:
        return {}
    adjudication_path = root.joinpath(*_PROSPECTIVE_ADJUDICATION_PLAN_SUFFIX)
    frame_path = root.joinpath(*_PROSPECTIVE_FRAME_MANIFEST_SUFFIX)
    if not _declared_prospective_adjudication_plan_hashes(
        adjudication_path
    ) or not _declared_prospective_frame_hashes(frame_path):
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
        frame = _load_json(frame_path)
    except (AuditInputError, OSError, UnicodeError, SyntaxError):
        return {}
    source_freeze = frame.get("source_feature_freeze") if isinstance(frame, dict) else None
    if not isinstance(source_freeze, dict):
        return {}
    allowed_values = {
        source_freeze.get("sha256"),
        source_freeze.get("selected_instance_ids_sha256"),
        source_freeze.get("selected_task_identities_sha256"),
    }
    if any(
        not isinstance(value, str) or _SHA256_HEX_RE.fullmatch(value) is None
        for value in allowed_values
    ):
        return {}
    constants = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _SHA256_HEX_RE.fullmatch(node.value)
    ]
    if len(constants) != 3 or {node.value for node in constants} != allowed_values:
        return {}
    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    for node in constants:
        raw_value = node.value
        if not isinstance(raw_value, str) or raw_value not in lines[node.lineno - 1]:
            return {}
        identity = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()  # noqa: S324
        result[(identity, node.lineno)] = f"declared_unverified:source_constant_line_{node.lineno}"
    return result


def _declared_prospective_validator_source_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify the remaining exact validator anchor with an external preimage."""

    root = _prospective_root(path, _PROSPECTIVE_VALIDATOR_SUFFIX)
    if root is None or not _matches_exact_public_record(
        path,
        expected_bytes=_PROSPECTIVE_VALIDATOR_BYTES,
        expected_digest=_PROSPECTIVE_VALIDATOR_DIGEST,
    ):
        return {}
    protocol_path = root.joinpath(*_PROSPECTIVE_PROTOCOL_SUFFIX)
    execution_path = root.joinpath(*_PROSPECTIVE_EXECUTION_FREEZE_SUFFIX)
    if not _declared_prospective_protocol_hashes(
        protocol_path
    ) or not _declared_prospective_execution_freeze_hashes(execution_path):
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
        execution = _load_json(execution_path)
    except (AuditInputError, OSError, UnicodeError, SyntaxError):
        return {}
    harness = execution.get("harness") if isinstance(execution, dict) else None
    if not isinstance(harness, dict):
        return {}
    allowed_values = {harness.get("tree")}
    if any(
        not isinstance(value, str)
        or (_SHA256_HEX_RE.fullmatch(value) is None and _COMMIT_HEX_RE.fullmatch(value) is None)
        for value in allowed_values
    ):
        return {}
    constants = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (_SHA256_HEX_RE.fullmatch(node.value) or _COMMIT_HEX_RE.fullmatch(node.value))
    ]
    if (
        len(constants) != len(allowed_values)
        or {node.value for node in constants} != allowed_values
    ):
        return {}
    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    for node in constants:
        raw_value = node.value
        if not isinstance(raw_value, str) or raw_value not in lines[node.lineno - 1]:
            return {}
        identity = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()  # noqa: S324
        result[(identity, node.lineno)] = (
            f"declared_unverified:validator_constant_line_{node.lineno}"
        )
    return result


def _declared_independent_smoke_source_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify verifier constants only when they are bound by its manifest."""

    if tuple(path.parts[-len(_INDEPENDENT_SMOKE_SOURCE_SUFFIX) :]) != (
        _INDEPENDENT_SMOKE_SOURCE_SUFFIX
    ):
        return {}
    if not _matches_exact_public_record(
        path,
        expected_bytes=_INDEPENDENT_SMOKE_SOURCE_BYTES,
        expected_digest=_INDEPENDENT_SMOKE_SOURCE_DIGEST,
    ):
        return {}
    manifest_path = path.with_name("evidence-manifest.json")
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
        manifest = _load_json(manifest_path)
    except (AuditInputError, OSError, UnicodeError, SyntaxError):
        return {}
    if not _declared_independent_smoke_manifest_hashes(manifest_path):
        return {}
    assignments = {
        target.id: node
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    schema = assignments.get("SCHEMA_VERSION")
    study = assignments.get("STUDY_ID")
    if (
        schema is None
        or study is None
        or not isinstance(schema.value, ast.Constant)
        or schema.value.value != manifest.get("schema_version")
        or not isinstance(study.value, ast.Constant)
        or study.value.value != manifest.get("study_id")
    ):
        return {}
    function_names = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if not {"verify_manifest", "verify_external_bundle", "main"}.issubset(function_names):
        return {}

    manifest_values = {raw for raw, _field, _key in _json_hex_fields(manifest)}
    constants = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (_COMMIT_HEX_RE.fullmatch(node.value) or _SHA256_HEX_RE.fullmatch(node.value))
    ]
    if not constants or any(node.value not in manifest_values for node in constants):
        return {}
    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    for node in constants:
        raw_value = node.value
        if not isinstance(raw_value, str) or raw_value not in lines[node.lineno - 1]:
            return {}
        identity = hashlib.sha1(  # noqa: S324 - scanner identity, not security
            raw_value.encode("utf-8")
        ).hexdigest()
        key = (identity, node.lineno)
        if key in result:
            return {}
        result[key] = f"source_constant_line_{node.lineno}"
    return result


def _declared_exact_smoke_manifest_hashes(
    path: Path,
    *,
    suffix: tuple[str, ...],
    manifest_bytes: int,
    manifest_digest: bytes,
    source_bytes: int,
    source_digest: bytes,
    schema_version: str,
    study_id: str,
    top_level_fields: set[str],
    classification_contract: Mapping[str, Any],
    collection_lengths: Mapping[str, int],
    allowed_paths: Sequence[str],
) -> dict[tuple[str, int], str]:
    """Classify an exact immutable feasibility manifest without a file-wide waiver."""

    if tuple(path.parts[-len(suffix) :]) != suffix:
        return {}
    if not _matches_exact_public_record(
        path,
        expected_bytes=manifest_bytes,
        expected_digest=manifest_digest,
    ) or not _matches_exact_public_record(
        path.with_name("verify_evidence.py"),
        expected_bytes=source_bytes,
        expected_digest=source_digest,
    ):
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    classification = value.get("classification") if isinstance(value, dict) else None
    if (
        not _exact_keys(value, top_level_fields)
        or value["schema_version"] != schema_version
        or value["study_id"] != study_id
        or not isinstance(classification, dict)
        or any(
            classification.get(key) != expected for key, expected in classification_contract.items()
        )
        or any(
            not isinstance(value.get(key), list) or len(value[key]) != expected
            for key, expected in collection_lengths.items()
        )
    ):
        return {}
    patterns = tuple(re.compile(pattern) for pattern in allowed_paths)
    declared = _json_hex_fields(value)
    if not declared or any(
        not _matches_any_path(field, patterns) for _raw, field, _key in declared
    ):
        return {}
    return _render_json_provenance_identities(text, declared)


def _declared_exact_smoke_source_hashes(
    path: Path,
    *,
    suffix: tuple[str, ...],
    source_bytes: int,
    source_digest: bytes,
    manifest_bytes: int,
    manifest_digest: bytes,
    schema_version: str,
    study_id: str,
    required_functions: set[str],
) -> dict[tuple[str, int], str]:
    """Classify verifier constants only when exact source and manifest bytes agree."""

    if tuple(path.parts[-len(suffix) :]) != suffix:
        return {}
    if not _matches_exact_public_record(
        path,
        expected_bytes=source_bytes,
        expected_digest=source_digest,
    ) or not _matches_exact_public_record(
        path.with_name("evidence-manifest.json"),
        expected_bytes=manifest_bytes,
        expected_digest=manifest_digest,
    ):
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
        manifest = _load_json(path.with_name("evidence-manifest.json"))
    except (AuditInputError, OSError, UnicodeError, SyntaxError):
        return {}
    assignments = {
        target.id: node
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    schema = assignments.get("SCHEMA_VERSION")
    study = assignments.get("STUDY_ID")
    function_names = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if (
        schema is None
        or study is None
        or not isinstance(schema.value, ast.Constant)
        or schema.value.value != schema_version
        or not isinstance(study.value, ast.Constant)
        or study.value.value != study_id
        or not required_functions.issubset(function_names)
        or manifest.get("schema_version") != schema_version
        or manifest.get("study_id") != study_id
    ):
        return {}
    manifest_values = {raw for raw, _field, _key in _json_hex_fields(manifest)}
    constants = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (_COMMIT_HEX_RE.fullmatch(node.value) or _SHA256_HEX_RE.fullmatch(node.value))
    ]
    if not constants or any(node.value not in manifest_values for node in constants):
        return {}
    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    for node in constants:
        raw_value = node.value
        if not isinstance(raw_value, str) or raw_value not in lines[node.lineno - 1]:
            return {}
        identity = hashlib.sha1(  # noqa: S324 - scanner identity, not security
            raw_value.encode("utf-8")
        ).hexdigest()
        key = (identity, node.lineno)
        if key in result:
            return {}
        result[key] = f"source_constant_line_{node.lineno}"
    return result


def _declared_paired_smoke_manifest_hashes(path: Path) -> dict[tuple[str, int], str]:
    return _declared_exact_smoke_manifest_hashes(
        path,
        suffix=_PAIRED_SMOKE_MANIFEST_SUFFIX,
        manifest_bytes=_PAIRED_SMOKE_MANIFEST_BYTES,
        manifest_digest=_PAIRED_SMOKE_MANIFEST_DIGEST,
        source_bytes=_PAIRED_SMOKE_SOURCE_BYTES,
        source_digest=_PAIRED_SMOKE_SOURCE_DIGEST,
        schema_version="paired-execution-smoke-0.1.0",
        study_id="sympy-15976-locally-constructed-container-paired-retrospective-v1",
        top_level_fields={
            "aggregate",
            "classification",
            "evidence_bundle",
            "limitations",
            "relation_to_independent_smoke",
            "roles",
            "runs",
            "runtime",
            "schema_version",
            "study_id",
            "task",
        },
        classification_contract={
            "stage": "retrospective_post_draft_locally_constructed_paired_container_feasibility",
            "prospective": False,
            "blinded": False,
            "task_count": 1,
            "candidate_count": 3,
            "execution_count": 15,
            "supports_routing_claims": False,
            "supports_hypotheses_h1_h6": False,
        },
        collection_lengths={"roles": 5, "runs": 15},
        allowed_paths=(
            r"evidence_bundle\.sha256",
            r"evidence_bundle\.supporting_members\[[0-9]+\]\.sha256",
            r"relation_to_independent_smoke\.manifest\.sha256",
            r"roles\[[0-9]+\]\.input_patch_sha256",
            r"runs\[[0-9]+\]\.log\.sha256",
            r"runtime\.dockerfile\.sha256",
            r"runtime\.execution_contract\.runner_sha256",
            r"runtime\.mpmath\.(?:metadata_sha256|mounted_tree_manifest_sha256)",
            r"runtime\.python\.archive_sha256",
            r"task\.(?:base_commit|base_tree|environment_setup_commit)",
        ),
    )


def _declared_paired_smoke_source_hashes(path: Path) -> dict[tuple[str, int], str]:
    return _declared_exact_smoke_source_hashes(
        path,
        suffix=_PAIRED_SMOKE_SOURCE_SUFFIX,
        source_bytes=_PAIRED_SMOKE_SOURCE_BYTES,
        source_digest=_PAIRED_SMOKE_SOURCE_DIGEST,
        manifest_bytes=_PAIRED_SMOKE_MANIFEST_BYTES,
        manifest_digest=_PAIRED_SMOKE_MANIFEST_DIGEST,
        schema_version="paired-execution-smoke-0.1.0",
        study_id="sympy-15976-locally-constructed-container-paired-retrospective-v1",
        required_functions={"verify_manifest", "verify_external_bundle", "main"},
    )


def _declared_sphinx_smoke_manifest_hashes(path: Path) -> dict[tuple[str, int], str]:
    return _declared_exact_smoke_manifest_hashes(
        path,
        suffix=_SPHINX_SMOKE_MANIFEST_SUFFIX,
        manifest_bytes=_SPHINX_SMOKE_MANIFEST_BYTES,
        manifest_digest=_SPHINX_SMOKE_MANIFEST_DIGEST,
        source_bytes=_SPHINX_SMOKE_SOURCE_BYTES,
        source_digest=_SPHINX_SMOKE_SOURCE_DIGEST,
        schema_version="sphinx-execution-smoke-0.1.0",
        study_id="sphinx-8475-container-free-post-draft-pre-freeze-feasibility-v2",
        top_level_fields={
            "aggregate",
            "classification",
            "evidence_bundle",
            "execution_contract",
            "limitations",
            "preparation",
            "protocol_state",
            "results",
            "runtime",
            "schema_version",
            "sources",
            "study_id",
            "task",
        },
        classification_contract={
            "stage": "post_draft_pre_freeze_feasibility_execution",
            "prospective": False,
            "blinded": False,
            "task_count": 1,
            "candidate_count": 3,
            "observation_count": 15,
            "supports_routing_claims": False,
            "supports_hypotheses_h1_h6": False,
        },
        collection_lengths={"results": 5},
        allowed_paths=(
            r"evidence_bundle\.(?:sha256|index\.sha256|runner\.sha256)",
            r"preparation\.source_trees\.[A-Za-z0-9_]+",
            r"protocol_state\.bench_cleanser_commit",
            r"results\[[0-9]+\]\.input_patch_sha256",
            r"runtime\.environment_record\.sha256",
            r"runtime\.python\.(?:archive_sha256|binary_sha256)",
            r"sources\.base_source_archive\.(?:commit|sha256|tree)",
            r"sources\.canonical_dataset\.(?:retrieval_revision|revision|sha256)",
            r"task\.(?:base_commit|base_tree|environment_setup_commit)",
            r"task\.canonical_row\.sha256",
            r"task\.oracle_tests\.test_patch_sha256",
            r"task\.patches\[[0-9]+\]\.sha256",
        ),
    )


def _declared_sphinx_smoke_source_hashes(path: Path) -> dict[tuple[str, int], str]:
    return _declared_exact_smoke_source_hashes(
        path,
        suffix=_SPHINX_SMOKE_SOURCE_SUFFIX,
        source_bytes=_SPHINX_SMOKE_SOURCE_BYTES,
        source_digest=_SPHINX_SMOKE_SOURCE_DIGEST,
        manifest_bytes=_SPHINX_SMOKE_MANIFEST_BYTES,
        manifest_digest=_SPHINX_SMOKE_MANIFEST_DIGEST,
        schema_version="sphinx-execution-smoke-0.1.0",
        study_id="sphinx-8475-container-free-post-draft-pre-freeze-feasibility-v2",
        required_functions={"validate_manifest", "validate_bundle", "main"},
    )


def _declared_pilot_provenance_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Return detect-secrets identities for schema-bound public provenance.

    Git commits and SHA-256 artifact bindings are intentionally high-entropy.
    They are allowlisted only when the exact real-agent cohort schema, field,
    value shape, file suffix, and source line all agree.  This is deliberately
    narrower than suppressing HexHighEntropyString for a file or extension.
    """

    if tuple(path.parts[-len(_REAL_AGENT_COHORT_SUFFIX) :]) != _REAL_AGENT_COHORT_SUFFIX:
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(value, {"schema_version", "study_id", "source", "candidates"}):
        return {}
    if (
        value["schema_version"] != "0.1.0"
        or not isinstance(value["study_id"], str)
        or not value["study_id"]
    ):
        return {}

    source = value["source"]
    if not _exact_keys(
        source,
        {
            "repository",
            "revision",
            "submission_id",
            "submission_checked",
            "submission_metadata_url",
            "selection",
        },
    ):
        return {}
    revision = source["revision"]
    if (
        not all(
            isinstance(source[field], str) and bool(source[field])
            for field in (
                "repository",
                "submission_id",
                "submission_metadata_url",
                "selection",
            )
        )
        or not isinstance(source["submission_checked"], bool)
        or not isinstance(revision, str)
        or not _COMMIT_HEX_RE.fullmatch(revision)
    ):
        return {}

    candidates = value["candidates"]
    if not isinstance(candidates, list) or not candidates:
        return {}
    declared: list[tuple[str, str, str]] = [(revision, "source.revision", "revision")]
    instance_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not _exact_keys(
            candidate,
            {
                "instance_id",
                "repository",
                "base_commit",
                "official_resolved",
                "artifacts",
            },
        ):
            return {}
        base_commit = candidate["base_commit"]
        artifacts = candidate["artifacts"]
        if (
            not isinstance(candidate["instance_id"], str)
            or not candidate["instance_id"]
            or candidate["instance_id"] in instance_ids
            or not isinstance(candidate["repository"], str)
            or not candidate["repository"]
            or not isinstance(candidate["official_resolved"], bool)
            or not isinstance(base_commit, str)
            or not _COMMIT_HEX_RE.fullmatch(base_commit)
            or not _exact_keys(artifacts, _PILOT_ARTIFACT_NAMES)
        ):
            return {}
        instance_ids.add(candidate["instance_id"])
        declared.append((base_commit, f"candidates[{index}].base_commit", "base_commit"))
        for artifact_name in sorted(_PILOT_ARTIFACT_NAMES):
            artifact = artifacts[artifact_name]
            if not _exact_keys(artifact, {"url", "sha256", "bytes"}):
                return {}
            digest = artifact["sha256"]
            byte_count = artifact["bytes"]
            if (
                not isinstance(artifact["url"], str)
                or not artifact["url"]
                or type(byte_count) is not int
                or byte_count < 0
                or not isinstance(digest, str)
                or not _SHA256_HEX_RE.fullmatch(digest)
            ):
                return {}
            declared.append(
                (
                    digest,
                    f"candidates[{index}].artifacts[{artifact_name!r}].sha256",
                    "sha256",
                )
            )

    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    used_lines: set[int] = set()
    for raw_value, field, json_key in declared:
        encoded = json.dumps(raw_value)
        encoded_pair = re.compile(rf"{re.escape(json.dumps(json_key))}\s*:\s*{re.escape(encoded)}")
        matching_lines = [
            line_number for line_number, line in enumerate(lines, 1) if encoded_pair.search(line)
        ]
        if text.count(encoded) != 1 or len(matching_lines) != 1 or matching_lines[0] in used_lines:
            # Ambiguous/minified/duplicated encodings do not receive a waiver.
            return {}
        used_lines.add(matching_lines[0])
        detect_secrets_identity = hashlib.sha1(  # noqa: S324 - scanner identity, not security
            raw_value.encode("utf-8")
        ).hexdigest()
        key = (detect_secrets_identity, matching_lines[0])
        if key in result:
            return {}
        result[key] = field
    return result


def _resolve_static_string(node: ast.AST, values: Mapping[str, str]) -> str | None:
    """Resolve only literal/name/concatenated top-level strings, never execute code."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_static_string(node.left, values)
        right = _resolve_static_string(node.right, values)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                resolved = _resolve_static_string(value.value, values)
                if resolved is None or value.conversion != -1 or value.format_spec is not None:
                    return None
                parts.append(resolved)
            else:
                return None
        return "".join(parts)
    return None


def _ast_constant(node: ast.AST, expected_type: type[Any]) -> Any | None:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, expected_type):
        return None
    return node.value


def _provenance_identity(
    value: str,
    line_number: int,
    *,
    text: str,
    lines: Sequence[str],
) -> tuple[str, int] | None:
    if (
        text.count(value) != 1
        or not 1 <= line_number <= len(lines)
        or value not in lines[line_number - 1]
    ):
        return None
    identity = hashlib.sha1(  # noqa: S324 - detect-secrets scanner identity
        value.encode("utf-8")
    ).hexdigest()
    return identity, line_number


def _declared_canonical_dataset_provenance_hashes(
    assignments: Mapping[str, ast.Assign],
    *,
    text: str,
    lines: Sequence[str],
) -> dict[tuple[str, int], str] | None:
    """Validate and classify the shared canonical SWE-bench task identity.

    Both public outcome studies bind the same authoritative dataset, immutable
    mirror, byte digest, four-field projection, and sole duplicate base-commit
    pair.  Keeping that contract in one fail-closed helper prevents one study
    from receiving a broader provenance waiver than the other.
    """

    canonical_names = {
        "CANONICAL_DATASET_ID",
        "CANONICAL_DATASET_REVISION",
        "CANONICAL_DATASET_AUTHORITATIVE_URL",
        "CANONICAL_DATASET_MIRROR_REVISION",
        "CANONICAL_DATASET_RETRIEVAL_URL",
        "CANONICAL_DATASET_SHA256",
        "CANONICAL_DATASET_PROJECTION_SHA256",
        "CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT",
    }
    static_values: dict[str, str] = {}
    unresolved = set(canonical_names)
    while unresolved:
        progress = False
        for name in sorted(unresolved):
            assignment = assignments.get(name)
            if assignment is None:
                return None
            resolved = _resolve_static_string(assignment.value, static_values)
            if resolved is None:
                continue
            static_values[name] = resolved
            unresolved.remove(name)
            progress = True
        if not progress:
            return None

    dataset_id = static_values["CANONICAL_DATASET_ID"]
    dataset_revision = static_values["CANONICAL_DATASET_REVISION"]
    mirror_revision = static_values["CANONICAL_DATASET_MIRROR_REVISION"]
    if (
        dataset_id != "princeton-nlp/SWE-bench_Verified"
        or _COMMIT_HEX_RE.fullmatch(dataset_revision) is None
        or _COMMIT_HEX_RE.fullmatch(mirror_revision) is None
        or static_values["CANONICAL_DATASET_AUTHORITATIVE_URL"]
        != (
            "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/"
            f"{dataset_revision}/data/test-00000-of-00001.parquet"
        )
        or static_values["CANONICAL_DATASET_RETRIEVAL_URL"]
        != (
            "https://raw.githubusercontent.com/justin-napolitano/"
            f"SWE-bench_Verified/{mirror_revision}/data/test-00000-of-00001.parquet"
        )
        or _SHA256_HEX_RE.fullmatch(static_values["CANONICAL_DATASET_SHA256"]) is None
        or _SHA256_HEX_RE.fullmatch(static_values["CANONICAL_DATASET_PROJECTION_SHA256"]) is None
        or _COMMIT_HEX_RE.fullmatch(
            static_values["CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT"]
        )
        is None
        or text.count("CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT") != 2
        or text.count('"django__django-15268"') != 1
        or text.count('"django__django-15278"') != 1
    ):
        return None

    result: dict[tuple[str, int], str] = {}
    for name in (
        "CANONICAL_DATASET_REVISION",
        "CANONICAL_DATASET_MIRROR_REVISION",
        "CANONICAL_DATASET_SHA256",
        "CANONICAL_DATASET_PROJECTION_SHA256",
        "CANONICAL_DATASET_EXPECTED_DUPLICATE_BASE_COMMIT",
    ):
        assignment = assignments[name]
        value = static_values[name]
        canonical_key = _provenance_identity(
            value,
            assignment.value.lineno,
            text=text,
            lines=lines,
        )
        if canonical_key is None or canonical_key in result:
            return None
        result[canonical_key] = name
    return result


def _declared_hosted_study_provenance_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Return exact public-source digests from the hosted-outcome study.

    The study intentionally pins two public GitHub payloads by SHA-256.  Treat
    those values as provenance only when the file path, top-level symbols,
    public URL shapes, shared commit/submission identity, mapping structure,
    digest shapes, source lines, and scanner identities all agree.  Any nearby
    or malformed high-entropy literal remains an actionable finding.
    """

    if tuple(path.parts[-len(_HOSTED_STUDY_SOURCE_SUFFIX) :]) != (_HOSTED_STUDY_SOURCE_SUFFIX):
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return {}

    assignments: dict[str, ast.Assign] = {}
    for statement in module.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            name = statement.targets[0].id
            if name in assignments:
                return {}
            assignments[name] = statement

    required_literals = {
        "SUBMISSION_ID",
        "SUBMISSION_METADATA_URL",
        "SUBMISSION_METADATA_SHA256",
        "SUBMISSION_RESULTS_URL",
        "SUBMISSION_RESULTS_SHA256",
    }
    literals: dict[str, tuple[str, int]] = {}
    for name in required_literals:
        assignment = assignments.get(name)
        if assignment is None or not isinstance(assignment.value, ast.Constant):
            return {}
        value = assignment.value.value
        if not isinstance(value, str):
            return {}
        literals[name] = (value, assignment.value.lineno)

    submission_id = literals["SUBMISSION_ID"][0]
    metadata_url = literals["SUBMISSION_METADATA_URL"][0]
    results_url = literals["SUBMISSION_RESULTS_URL"][0]
    url_pattern = re.compile(
        r"https://raw\.githubusercontent\.com/SWE-bench/experiments/"
        r"(?P<revision>[0-9a-f]{40})/evaluation/verified/"
        r"(?P<submission>[A-Za-z0-9_.-]+)/(?P<artifact>metadata\.yml|results/results\.json)"
    )
    metadata_match = url_pattern.fullmatch(metadata_url)
    results_match = url_pattern.fullmatch(results_url)
    if (
        metadata_match is None
        or results_match is None
        or metadata_match.group("artifact") != "metadata.yml"
        or results_match.group("artifact") != "results/results.json"
        or metadata_match.group("revision") != results_match.group("revision")
        or metadata_match.group("submission") != results_match.group("submission")
        or metadata_match.group("submission") != submission_id.replace("-", "_", 1)
    ):
        return {}

    pinned = assignments.get("PINNED_SUBMISSION_SOURCES")
    if pinned is None or not isinstance(pinned.value, ast.Dict):
        return {}
    expected_mapping = {
        "metadata.yml": ("SUBMISSION_METADATA_URL", "SUBMISSION_METADATA_SHA256"),
        "results.json": ("SUBMISSION_RESULTS_URL", "SUBMISSION_RESULTS_SHA256"),
    }
    observed_mapping: dict[str, tuple[str, str]] = {}
    for key_node, value_node in zip(pinned.value.keys, pinned.value.values, strict=True):
        if (
            not isinstance(key_node, ast.Constant)
            or not isinstance(key_node.value, str)
            or not isinstance(value_node, ast.Tuple)
            or len(value_node.elts) != 2
        ):
            return {}
        first_name, second_name = value_node.elts
        if not isinstance(first_name, ast.Name) or not isinstance(second_name, ast.Name):
            return {}
        mapping_key = key_node.value
        if mapping_key in observed_mapping:
            return {}
        observed_mapping[mapping_key] = (
            first_name.id,
            second_name.id,
        )
    if observed_mapping != expected_mapping:
        return {}

    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    for name in ("SUBMISSION_METADATA_SHA256", "SUBMISSION_RESULTS_SHA256"):
        digest, line_number = literals[name]
        if (
            not _SHA256_HEX_RE.fullmatch(digest)
            or text.count(digest) != 1
            or line_number > len(lines)
            or digest not in lines[line_number - 1]
        ):
            return {}
        identity = hashlib.sha1(  # noqa: S324 - detect-secrets identity
            digest.encode("utf-8")
        ).hexdigest()
        provenance_key = (identity, line_number)
        if provenance_key in result:
            return {}
        result[provenance_key] = name

    canonical = _declared_canonical_dataset_provenance_hashes(
        assignments,
        text=text,
        lines=lines,
    )
    if canonical is None or set(result).intersection(canonical):
        return {}
    result.update(canonical)
    return result


def _declared_matched_study_provenance_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Narrowly classify immutable public source identities in the matched study."""

    if tuple(path.parts[-len(_MATCHED_STUDY_SOURCE_SUFFIX) :]) != (_MATCHED_STUDY_SOURCE_SUFFIX):
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        module = ast.parse(text, filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return {}
    assignments: dict[str, ast.Assign] = {}
    for statement in module.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            name = statement.targets[0].id
            if name in assignments:
                return {}
            assignments[name] = statement
    revision_assignment = assignments.get("SOURCE_REVISION")
    submissions_assignment = assignments.get("SUBMISSIONS")
    if (
        revision_assignment is None
        or not isinstance(revision_assignment.value, ast.Constant)
        or not isinstance(revision_assignment.value.value, str)
        or _COMMIT_HEX_RE.fullmatch(revision_assignment.value.value) is None
        or submissions_assignment is None
        or not isinstance(submissions_assignment.value, ast.Tuple)
        or len(submissions_assignment.value.elts) != 3
    ):
        return {}
    expected_sources = {
        "gpt5": ("20250807_openhands_gpt5", 499),
        "kimi_k2": ("20250716_openhands_kimi_k2", 500),
        "claude_4_sonnet": ("20250524_openhands_claude_4_sonnet", 500),
    }
    hash_values: list[tuple[str, int, str]] = []
    observed: dict[str, tuple[str, int]] = {}
    required_keywords = {
        "key",
        "model_label",
        "submission_id",
        "expected_instance_count",
        "metadata_bytes",
        "metadata_sha256",
        "results_bytes",
        "results_sha256",
    }
    for call_node in submissions_assignment.value.elts:
        if (
            not isinstance(call_node, ast.Call)
            or not isinstance(call_node.func, ast.Name)
            or call_node.func.id != "SubmissionSpec"
            or call_node.args
            or any(keyword.arg is None for keyword in call_node.keywords)
        ):
            return {}
        keywords = {str(keyword.arg): keyword.value for keyword in call_node.keywords}
        if set(keywords) != required_keywords:
            return {}

        key = _ast_constant(keywords["key"], str)
        submission_id = _ast_constant(keywords["submission_id"], str)
        expected_count = _ast_constant(keywords["expected_instance_count"], int)
        metadata_bytes = _ast_constant(keywords["metadata_bytes"], int)
        results_bytes = _ast_constant(keywords["results_bytes"], int)
        metadata_digest = _ast_constant(keywords["metadata_sha256"], str)
        results_digest = _ast_constant(keywords["results_sha256"], str)
        if (
            not isinstance(key, str)
            or not isinstance(submission_id, str)
            or not isinstance(expected_count, int)
            or not isinstance(metadata_bytes, int)
            or not isinstance(results_bytes, int)
            or metadata_bytes < 1
            or results_bytes < 1
            or not isinstance(metadata_digest, str)
            or not isinstance(results_digest, str)
            or _SHA256_HEX_RE.fullmatch(metadata_digest) is None
            or _SHA256_HEX_RE.fullmatch(results_digest) is None
            or key in observed
        ):
            return {}
        observed[key] = (submission_id, expected_count)
        hash_values.extend(
            [
                (
                    metadata_digest,
                    keywords["metadata_sha256"].lineno,
                    f"SUBMISSIONS[{key}].metadata_sha256",
                ),
                (
                    results_digest,
                    keywords["results_sha256"].lineno,
                    f"SUBMISSIONS[{key}].results_sha256",
                ),
            ]
        )
    if (
        observed != expected_sources
        or "metadata.yaml" not in text
        or "results/results.json" not in text
        or "spec.metadata_sha256" not in text
        or "spec.results_sha256" not in text
    ):
        return {}
    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    revision = revision_assignment.value.value
    revision_key = _provenance_identity(
        revision,
        revision_assignment.value.lineno,
        text=text,
        lines=lines,
    )
    if revision_key is None:
        return {}
    result[revision_key] = "SOURCE_REVISION"
    for value, line_number, field in hash_values:
        provenance_key = _provenance_identity(
            value,
            line_number,
            text=text,
            lines=lines,
        )
        if provenance_key is None or provenance_key in result:
            return {}
        result[provenance_key] = field
    canonical = _declared_canonical_dataset_provenance_hashes(
        assignments,
        text=text,
        lines=lines,
    )
    if canonical is None or set(result).intersection(canonical):
        return {}
    result.update(canonical)
    return result


def _declared_literature_lock_hashes(path: Path) -> dict[tuple[str, int], str]:
    """Return exact public API digests from a schema-valid literature lock."""

    if tuple(path.parts[-len(_LITERATURE_LOCK_SUFFIX) :]) != _LITERATURE_LOCK_SUFFIX:
        return {}
    try:
        value = _load_json(path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if not _exact_keys(value, {"schema_version", "source", "entries"}):
        return {}
    if value["schema_version"] != "0.1.0":
        return {}

    source = value["source"]
    if not _exact_keys(
        source,
        {
            "provider",
            "api_endpoint",
            "retrieved_at",
            "versioned_ids_sha256",
            "responses",
        },
    ):
        return {}
    if (
        source["provider"] != "arXiv"
        or source["api_endpoint"] != "https://export.arxiv.org/api/query"
        or not isinstance(source["retrieved_at"], str)
        or not _UTC_TIMESTAMP_RE.fullmatch(source["retrieved_at"])
    ):
        return {}

    entries = value["entries"]
    if not isinstance(entries, list) or not entries:
        return {}
    versioned_ids: list[str] = []
    for entry in entries:
        if not _exact_keys(
            entry,
            {
                "abs_url",
                "arxiv_id",
                "authors",
                "canonical_title",
                "pdf_url",
                "primary_category",
                "published_at",
                "updated_at",
                "version",
                "versioned_id",
            },
        ):
            return {}
        arxiv_id = entry["arxiv_id"]
        version = entry["version"]
        versioned_id = entry["versioned_id"]
        authors = entry["authors"]
        if (
            not isinstance(arxiv_id, str)
            or type(version) is not int
            or version < 1
            or not isinstance(versioned_id, str)
            or _ARXIV_VERSIONED_ID_RE.fullmatch(versioned_id) is None
            or versioned_id != f"{arxiv_id}v{version}"
            or entry["abs_url"] != f"https://arxiv.org/abs/{versioned_id}"
            or entry["pdf_url"] != f"https://arxiv.org/pdf/{versioned_id}"
            or not isinstance(entry["canonical_title"], str)
            or not entry["canonical_title"].strip()
            or entry["canonical_title"] != entry["canonical_title"].strip()
            or not isinstance(authors, list)
            or not authors
            or any(
                not isinstance(author, str) or not author.strip() or author != author.strip()
                for author in authors
            )
            or not isinstance(entry["primary_category"], str)
            or not entry["primary_category"].strip()
            or not isinstance(entry["published_at"], str)
            or not _UTC_TIMESTAMP_RE.fullmatch(entry["published_at"])
            or not isinstance(entry["updated_at"], str)
            or not _UTC_TIMESTAMP_RE.fullmatch(entry["updated_at"])
            or entry["published_at"] > entry["updated_at"]
        ):
            return {}
        versioned_ids.append(versioned_id)
    if versioned_ids != sorted(set(versioned_ids)):
        return {}

    ids_digest = source["versioned_ids_sha256"]
    canonical_ids = ("\n".join(versioned_ids) + "\n").encode("utf-8")
    if (
        not isinstance(ids_digest, str)
        or not _SHA256_HEX_RE.fullmatch(ids_digest)
        or ids_digest != hashlib.sha256(canonical_ids).hexdigest()
    ):
        return {}

    responses = source["responses"]
    if not isinstance(responses, list) or not responses:
        return {}
    queried_ids: set[str] = set()
    declared: list[tuple[str, str, str]] = [
        (ids_digest, "source.versioned_ids_sha256", "versioned_ids_sha256")
    ]
    response_entry_total = 0
    for index, response in enumerate(responses):
        if not _exact_keys(
            response,
            {"request_url", "raw_atom_sha256", "entry_count"},
        ):
            return {}
        request_url = response["request_url"]
        digest = response["raw_atom_sha256"]
        entry_count = response["entry_count"]
        if (
            not isinstance(request_url, str)
            or not isinstance(digest, str)
            or not _SHA256_HEX_RE.fullmatch(digest)
            or type(entry_count) is not int
            or entry_count < 1
        ):
            return {}
        parsed = urllib.parse.urlsplit(request_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "export.arxiv.org"
            or parsed.path != "/api/query"
            or parsed.fragment
        ):
            return {}
        try:
            query = urllib.parse.parse_qs(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
            )
        except ValueError:
            return {}
        if set(query) != {"id_list", "start", "max_results"}:
            return {}
        if query["start"] != ["0"] or query["max_results"] != [str(entry_count)]:
            return {}
        response_ids = query["id_list"][0].split(",")
        if (
            len(response_ids) != entry_count
            or len(set(response_ids)) != entry_count
            or any(_ARXIV_VERSIONED_ID_RE.fullmatch(item) is None for item in response_ids)
            or queried_ids.intersection(response_ids)
        ):
            return {}
        queried_ids.update(response_ids)
        response_entry_total += entry_count
        declared.append(
            (
                digest,
                f"source.responses[{index}].raw_atom_sha256",
                "raw_atom_sha256",
            )
        )
    if queried_ids != set(versioned_ids) or response_entry_total != len(versioned_ids):
        return {}

    lines = text.splitlines()
    result: dict[tuple[str, int], str] = {}
    used_lines: set[int] = set()
    for raw_value, field, json_key in declared:
        encoded = json.dumps(raw_value)
        encoded_pair = re.compile(rf"{re.escape(json.dumps(json_key))}\s*:\s*{re.escape(encoded)}")
        matching_lines = [
            line_number for line_number, line in enumerate(lines, 1) if encoded_pair.search(line)
        ]
        if text.count(encoded) != 1 or len(matching_lines) != 1 or matching_lines[0] in used_lines:
            return {}
        used_lines.add(matching_lines[0])
        identity = hashlib.sha1(  # noqa: S324 - detect-secrets identity
            raw_value.encode("utf-8")
        ).hexdigest()
        key = (identity, matching_lines[0])
        if key in result:
            return {}
        result[key] = field
    return result


def _declared_literature_claim_hashes(
    path: Path,
) -> dict[tuple[str, int], str]:
    """Classify only PDF digests in the immutable, lock-bound claim ledger."""

    if tuple(path.parts[-len(_LITERATURE_CLAIMS_SUFFIX) :]) != (_LITERATURE_CLAIMS_SUFFIX):
        return {}
    validator_path = path.parent.parent / "scripts" / "verify_claim_ledger.py"
    if not _matches_exact_public_record(
        path,
        expected_bytes=_LITERATURE_CLAIMS_BYTES,
        expected_digest=_LITERATURE_CLAIMS_DIGEST,
    ) or not _matches_exact_public_record(
        validator_path,
        expected_bytes=_LITERATURE_CLAIMS_VALIDATOR_BYTES,
        expected_digest=_LITERATURE_CLAIMS_VALIDATOR_DIGEST,
    ):
        return {}
    lock_path = path.with_name("literature.lock.json")
    try:
        value = _load_json(path)
        lock = _load_json(lock_path)
        text = path.read_text(encoding="utf-8")
    except (AuditInputError, OSError, UnicodeError):
        return {}
    if (
        not _declared_literature_lock_hashes(lock_path)
        or not _exact_keys(
            value,
            {"schema_version", "status", "reviewed_at", "coverage", "entries"},
        )
        or value["schema_version"] != "literature-claim-ledger-0.1.0"
        or value["status"] != "partial_machine_assisted_requires_human_confirmation"
        or value["reviewed_at"] != "2026-07-14"
    ):
        return {}
    coverage = value["coverage"]
    entries = value["entries"]
    lock_entries = lock.get("entries")
    if (
        not _exact_keys(
            coverage,
            {"locked_paper_count", "reviewed_pdf_count", "complete"},
        )
        or coverage != {"locked_paper_count": 66, "reviewed_pdf_count": 22, "complete": False}
        or not isinstance(entries, list)
        or len(entries) != 22
        or not isinstance(lock_entries, list)
        or len(lock_entries) != 66
    ):
        return {}
    locked = {
        entry.get("versioned_id"): entry
        for entry in lock_entries
        if isinstance(entry, dict) and isinstance(entry.get("versioned_id"), str)
    }
    if len(locked) != len(lock_entries):
        return {}

    declared: list[tuple[str, str, str]] = []
    versioned_ids: list[str] = []
    for index, entry in enumerate(entries):
        if not _exact_keys(
            entry,
            {
                "versioned_id",
                "canonical_title",
                "pdf_url",
                "pdf_sha256",
                "pdf_bytes",
                "artifact_name",
                "review",
                "claims",
            },
        ):
            return {}
        versioned_id = entry["versioned_id"]
        digest = entry["pdf_sha256"]
        source = locked.get(versioned_id) if isinstance(versioned_id, str) else None
        review = entry["review"]
        claims = entry["claims"]
        if (
            not isinstance(versioned_id, str)
            or _ARXIV_VERSIONED_ID_RE.fullmatch(versioned_id) is None
            or not isinstance(source, dict)
            or entry["canonical_title"] != source.get("canonical_title")
            or entry["pdf_url"] != source.get("pdf_url")
            or entry["artifact_name"] != f"{versioned_id}.pdf"
            or type(entry["pdf_bytes"]) is not int
            or entry["pdf_bytes"] < 1
            or not isinstance(digest, str)
            or _SHA256_HEX_RE.fullmatch(digest) is None
            or not _exact_keys(review, {"method", "human_confirmed"})
            or review
            != {
                "method": "machine_assisted_primary_pdf_review",
                "human_confirmed": False,
            }
            or not isinstance(claims, list)
            or not claims
            or any(
                not _exact_keys(
                    claim,
                    {
                        "claim_id",
                        "claim_type",
                        "paraphrase",
                        "pdf_pages",
                        "section",
                        "project_use",
                    },
                )
                for claim in claims
            )
        ):
            return {}
        versioned_ids.append(versioned_id)
        declared.append((digest, f"entries[{index}].pdf_sha256", "pdf_sha256"))
    if versioned_ids != sorted(set(versioned_ids)):
        return {}
    return _render_json_provenance_identities(text, declared)


def _run_detect_secrets(
    extraction_root: Path,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        version = importlib.metadata.version("detect-secrets")
    except importlib.metadata.PackageNotFoundError as exc:
        raise AuditInputError("detect-secrets is required for artifact auditing") from exc

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "detect_secrets",
                "scan",
                "--all-files",
                "--no-verify",
                "--disable-plugin",
                "KeywordDetector",
                ".",
            ],
            cwd=extraction_root,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuditInputError(f"detect-secrets could not run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip()[:500]
        raise AuditInputError(f"detect-secrets exited {result.returncode}: {detail}")
    try:
        baseline = json.loads(result.stdout, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, AuditInputError) as exc:
        raise AuditInputError("detect-secrets emitted invalid JSON") from exc

    findings: list[dict[str, Any]] = []
    declared_provenance: list[dict[str, Any]] = []
    results = baseline.get("results", {}) if isinstance(baseline, dict) else {}
    if not isinstance(results, dict):
        raise AuditInputError("detect-secrets JSON has no results object")
    for path, path_findings in results.items():
        if not isinstance(path, str) or not isinstance(path_findings, list):
            raise AuditInputError("detect-secrets result entry is malformed")
        normalized_path = path.removeprefix("./")
        safe_path = _safe_member_name(normalized_path)
        if safe_path is None or safe_path != normalized_path:
            raise AuditInputError("detect-secrets result path is unsafe")
        for finding in path_findings:
            if not isinstance(finding, dict):
                raise AuditInputError("detect-secrets finding is malformed")
            line_number = finding.get("line_number")
            hashed_secret = finding.get("hashed_secret")
            finding_type = finding.get("type", "unknown")
            if (
                type(line_number) is not int
                or line_number < 1
                or not isinstance(hashed_secret, str)
                or not hashed_secret
                or not isinstance(finding_type, str)
                or not finding_type
            ):
                raise AuditInputError("detect-secrets finding fields are malformed")
            finding_path = extraction_root.joinpath(*PurePosixPath(safe_path).parts)
            declared_fields = _declared_pilot_provenance_hashes(finding_path)
            hosted_fields = _declared_hosted_study_provenance_hashes(finding_path)
            matched_fields = _declared_matched_study_provenance_hashes(finding_path)
            literature_fields = _declared_literature_lock_hashes(finding_path)
            literature_claim_fields = _declared_literature_claim_hashes(finding_path)
            independent_manifest_fields = _declared_independent_smoke_manifest_hashes(finding_path)
            independent_source_fields = _declared_independent_smoke_source_hashes(finding_path)
            paired_manifest_fields = _declared_paired_smoke_manifest_hashes(finding_path)
            paired_source_fields = _declared_paired_smoke_source_hashes(finding_path)
            sphinx_manifest_fields = _declared_sphinx_smoke_manifest_hashes(finding_path)
            sphinx_source_fields = _declared_sphinx_smoke_source_hashes(finding_path)
            prospective_protocol_fields = _declared_prospective_protocol_hashes(finding_path)
            prospective_prehistory_fields = _declared_prospective_prehistory_hashes(finding_path)
            prospective_collection_fields = _declared_prospective_collection_policy_hashes(
                finding_path
            )
            prospective_frame_fields = _declared_prospective_frame_hashes(finding_path)
            prospective_scheduler_contract_fields = _declared_prospective_scheduler_contract_hashes(
                finding_path
            )
            prospective_scheduler_source_fields = _declared_prospective_scheduler_source_hashes(
                finding_path
            )
            prospective_review_source_fields = _declared_prospective_review_packet_source_hashes(
                finding_path
            )
            prospective_validator_source_fields = _declared_prospective_validator_source_hashes(
                finding_path
            )
            prospective_analysis_fields = _declared_prospective_analysis_plan_hashes(finding_path)
            prospective_adjudication_fields = _declared_prospective_adjudication_plan_hashes(
                finding_path
            )
            prospective_execution_fields = _declared_prospective_execution_freeze_hashes(
                finding_path
            )
            prospective_target_policy_fields = _declared_prospective_target_policy_manifest_hashes(
                finding_path
            )
            provenance_groups = (
                declared_fields,
                hosted_fields,
                matched_fields,
                literature_fields,
                literature_claim_fields,
                independent_manifest_fields,
                independent_source_fields,
                paired_manifest_fields,
                paired_source_fields,
                sphinx_manifest_fields,
                sphinx_source_fields,
                prospective_protocol_fields,
                prospective_prehistory_fields,
                prospective_collection_fields,
                prospective_frame_fields,
                prospective_scheduler_contract_fields,
                prospective_scheduler_source_fields,
                prospective_review_source_fields,
                prospective_validator_source_fields,
                prospective_analysis_fields,
                prospective_adjudication_fields,
                prospective_execution_fields,
                prospective_target_policy_fields,
            )
            if any(
                set(left).intersection(right)
                for left_index, left in enumerate(provenance_groups)
                for right in provenance_groups[left_index + 1 :]
            ):
                raise AuditInputError("declared provenance identities collide")
            for provenance_group in provenance_groups[1:]:
                declared_fields.update(provenance_group)
            declared_field = declared_fields.get((hashed_secret, line_number))
            if finding_type == "Hex High Entropy String" and declared_field is not None:
                declared_provenance.append(
                    {
                        "field": declared_field,
                        "line": line_number,
                        "path": safe_path,
                        "rule": finding_type,
                    }
                )
                continue
            findings.append(
                {
                    "line": line_number,
                    "path": safe_path,
                    "rule": finding_type,
                }
            )
    sort_key = lambda item: (item["path"], item["line"] or 0)
    return (
        version,
        sorted(findings, key=sort_key),
        sorted(declared_provenance, key=sort_key),
    )


def audit_artifacts(
    artifact_paths: Iterable[Path],
    policy_path: Path,
    *,
    run_detect_secrets: bool = True,
) -> dict[str, Any]:
    """Inspect exact wheel/sdist bytes, then run detect-secrets on safe copies."""

    policy = _load_policy(policy_path)
    package_policy = policy["packages"]
    forbidden = {
        _canonical_name(value)
        for field in ("forbidden", "excluded_integrations")
        for value in package_policy.get(field, [])
        if isinstance(value, str)
    }

    artifact_records: list[dict[str, Any]] = []
    custom_findings: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="bench-cleanser-artifact-audit-") as temporary:
        root = Path(temporary)
        for index, artifact_path in enumerate(artifact_paths):
            if not artifact_path.is_file():
                raise AuditInputError(f"release artifact is not a regular file: {artifact_path}")
            extraction = root / f"artifact-{index}"
            extraction.mkdir()
            member_count = 0
            total_bytes = 0
            for raw_name, data, kind in _iter_archive(artifact_path):
                member_count += 1
                safe_name = _safe_member_name(raw_name)
                if safe_name is None:
                    custom_findings.append(
                        {
                            "kind": "unsafe-archive-path",
                            "line": None,
                            "path": raw_name,
                            "rule": "path-confinement",
                        }
                    )
                    continue
                display_path = f"{artifact_path.name}:{safe_name}"
                if kind == "oversize":
                    custom_findings.append(
                        {
                            "kind": "archive-size-limit",
                            "line": None,
                            "path": display_path,
                            "rule": "release-artifact-size",
                        }
                    )
                    continue
                if kind != "file" or data is None:
                    custom_findings.append(
                        {
                            "kind": "link-or-special-member",
                            "line": None,
                            "path": display_path,
                            "rule": kind,
                        }
                    )
                    continue
                total_bytes += len(data)
                if len(data) > _MAX_MEMBER_BYTES or total_bytes > _MAX_ARCHIVE_BYTES:
                    custom_findings.append(
                        {
                            "kind": "archive-size-limit",
                            "line": None,
                            "path": display_path,
                            "rule": "release-artifact-size",
                        }
                    )
                    continue

                custom_findings.extend(_scan_member(display_path, data, forbidden))
                destination = extraction.joinpath(*PurePosixPath(safe_name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)

            artifact_records.append(
                {
                    "members": member_count,
                    "name": artifact_path.name,
                    "sha256": _sha256(artifact_path),
                    "uncompressed_regular_bytes": total_bytes,
                }
            )

        scanner_version = "not-run"
        scanner_findings: list[dict[str, Any]] = []
        declared_provenance: list[dict[str, Any]] = []
        if run_detect_secrets:
            (
                scanner_version,
                scanner_findings,
                declared_provenance,
            ) = _run_detect_secrets(root)

    passed = not custom_findings and not scanner_findings
    return {
        "artifacts": artifact_records,
        "automation_result": "pass" if passed else "fail",
        "custom_findings": sorted(
            custom_findings,
            key=lambda item: (item["path"], item["line"] or 0, item["kind"]),
        ),
        "detect_secrets": {
            "declared_provenance_hashes": declared_provenance,
            "findings": scanner_findings,
            "network_verification": False,
            "version": scanner_version,
        },
        "policy_sha256": _sha256(policy_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    licenses = subparsers.add_parser(
        "licenses", help="enforce the license policy and SBOM/inventory agreement"
    )
    licenses.add_argument("--inventory", type=Path, required=True)
    licenses.add_argument("--sbom", type=Path, required=True)
    licenses.add_argument("--policy", type=Path, required=True)
    licenses.add_argument("--output", type=Path, required=True)

    artifacts = subparsers.add_parser(
        "artifacts", help="scan exact wheel/sdist members and safely run detect-secrets"
    )
    artifacts.add_argument("--policy", type=Path, required=True)
    artifacts.add_argument("--output", type=Path, required=True)
    artifacts.add_argument("artifact", type=Path, nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "licenses":
            report = audit_licenses(args.inventory, args.sbom, args.policy)
        else:
            report = audit_artifacts(args.artifact, args.policy)
        _write_json(args.output, report)
    except (AuditInputError, OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"supply-chain audit error: {exc}", file=sys.stderr)
        return 2

    if report["automation_result"] != "pass":
        print(f"supply-chain policy failed; inspect {args.output}", file=sys.stderr)
        return 1
    print(f"supply-chain policy passed; report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
