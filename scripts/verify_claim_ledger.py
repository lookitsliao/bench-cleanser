#!/usr/bin/env python3
"""Validate the partial claim-level primary-PDF literature ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "literature-claim-ledger-0.1.0"
STATUS = "partial_machine_assisted_requires_human_confirmation"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
VERSIONED_ID_RE = re.compile(r"[0-9]{4}\.[0-9]{4,5}v[1-9][0-9]*")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_PDF_BYTES = 128 * 1024 * 1024


class ClaimLedgerError(ValueError):
    """The claim ledger, literature lock, or supplied PDF is invalid."""


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ClaimLedgerError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: pathlib.Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ClaimLedgerError(f"{field} must be a regular non-symlink file")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_JSON_BYTES:
        raise ClaimLedgerError(f"{field} is empty or exceeds the size bound")
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ClaimLedgerError(f"non-standard JSON constant {value!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClaimLedgerError(f"invalid JSON in {field}: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ClaimLedgerError(f"{field} must be a JSON object")
    return decoded


def _exact(value: Mapping[str, Any], fields: set[str], field: str) -> None:
    missing = sorted(fields - set(value))
    unknown = sorted(set(value) - fields)
    if missing or unknown:
        raise ClaimLedgerError(f"{field} field mismatch: missing={missing}, unknown={unknown}")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ClaimLedgerError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ClaimLedgerError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ClaimLedgerError(f"{field} must be a trimmed non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ClaimLedgerError(f"{field} has an invalid format")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ClaimLedgerError(f"{field} must be a positive integer")
    return value


def _literature_index(lock: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = _array(lock.get("entries"), "literature_lock.entries")
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(entries):
        entry = _object(raw, f"literature_lock.entries[{index}]")
        versioned_id = _string(
            entry.get("versioned_id"),
            f"literature_lock.entries[{index}].versioned_id",
            pattern=VERSIONED_ID_RE,
        )
        if versioned_id in result:
            raise ClaimLedgerError("literature lock contains duplicate versioned IDs")
        result[versioned_id] = entry
    if not result:
        raise ClaimLedgerError("literature lock has no entries")
    return result


def validate_ledger(
    ledger: Mapping[str, Any],
    literature_lock: Mapping[str, Any],
    *,
    pdf_files: Mapping[str, pathlib.Path] | None = None,
    require_all_pdfs: bool = False,
) -> dict[str, Any]:
    """Validate metadata and optionally exact PDF bytes."""

    _exact(ledger, {"schema_version", "status", "reviewed_at", "coverage", "entries"}, "ledger")
    if ledger["schema_version"] != SCHEMA_VERSION or ledger["status"] != STATUS:
        raise ClaimLedgerError("unsupported ledger schema or status")
    _string(ledger["reviewed_at"], "ledger.reviewed_at", pattern=DATE_RE)
    locked = _literature_index(literature_lock)

    coverage = _object(ledger["coverage"], "ledger.coverage")
    _exact(coverage, {"locked_paper_count", "reviewed_pdf_count", "complete"}, "ledger.coverage")
    if _positive_int(coverage["locked_paper_count"], "coverage.locked_paper_count") != len(locked):
        raise ClaimLedgerError("locked-paper count does not match literature lock")
    if coverage["complete"] is not False:
        raise ClaimLedgerError("the checked-in partial ledger cannot claim complete coverage")

    entries = _array(ledger["entries"], "ledger.entries")
    reviewed_count = _positive_int(coverage["reviewed_pdf_count"], "coverage.reviewed_pdf_count")
    if reviewed_count != len(entries) or reviewed_count >= len(locked):
        raise ClaimLedgerError("reviewed-PDF count is inconsistent or not partial")

    seen_ids: set[str] = set()
    seen_claims: set[str] = set()
    verified_pdfs: list[str] = []
    previous_versioned_id: str | None = None
    for index, raw in enumerate(entries):
        field = f"ledger.entries[{index}]"
        entry = _object(raw, field)
        _exact(
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
            field,
        )
        versioned_id = _string(entry["versioned_id"], f"{field}.versioned_id", pattern=VERSIONED_ID_RE)
        if versioned_id in seen_ids:
            raise ClaimLedgerError(f"duplicate ledger entry {versioned_id}")
        if previous_versioned_id is not None and versioned_id <= previous_versioned_id:
            raise ClaimLedgerError("ledger entries must be sorted by versioned ID")
        seen_ids.add(versioned_id)
        previous_versioned_id = versioned_id
        source = locked.get(versioned_id)
        if source is None:
            raise ClaimLedgerError(f"ledger entry {versioned_id} is absent from literature lock")
        if entry["canonical_title"] != source.get("canonical_title"):
            raise ClaimLedgerError(f"{versioned_id} title does not match literature lock")
        if entry["pdf_url"] != source.get("pdf_url"):
            raise ClaimLedgerError(f"{versioned_id} PDF URL does not match literature lock")
        digest = _string(entry["pdf_sha256"], f"{field}.pdf_sha256", pattern=SHA256_RE)
        byte_count = _positive_int(entry["pdf_bytes"], f"{field}.pdf_bytes")
        if byte_count > MAX_PDF_BYTES:
            raise ClaimLedgerError(f"{versioned_id} PDF exceeds the size bound")
        if entry["artifact_name"] != f"{versioned_id}.pdf":
            raise ClaimLedgerError(f"{versioned_id} artifact name is not canonical")

        review = _object(entry["review"], f"{field}.review")
        _exact(review, {"method", "human_confirmed"}, f"{field}.review")
        if review["method"] != "machine_assisted_primary_pdf_review":
            raise ClaimLedgerError(f"{versioned_id} has an unsupported review method")
        if review["human_confirmed"] is not False:
            raise ClaimLedgerError("checked-in machine-assisted reviews cannot claim human confirmation")

        claims = _array(entry["claims"], f"{field}.claims")
        if not claims:
            raise ClaimLedgerError(f"{versioned_id} has no claim mapping")
        for claim_index, raw_claim in enumerate(claims):
            claim_field = f"{field}.claims[{claim_index}]"
            claim = _object(raw_claim, claim_field)
            _exact(
                claim,
                {"claim_id", "claim_type", "paraphrase", "pdf_pages", "section", "project_use"},
                claim_field,
            )
            claim_id = _string(claim["claim_id"], f"{claim_field}.claim_id")
            if claim_id in seen_claims:
                raise ClaimLedgerError(f"duplicate claim ID {claim_id!r}")
            seen_claims.add(claim_id)
            if claim["claim_type"] not in {
                "author_reported_method",
                "author_reported_result",
                "author_reported_limitation",
            }:
                raise ClaimLedgerError(f"{claim_id} has an unsupported claim type")
            _string(claim["paraphrase"], f"{claim_field}.paraphrase")
            _string(claim["section"], f"{claim_field}.section")
            _string(claim["project_use"], f"{claim_field}.project_use")
            pages = [_positive_int(page, f"{claim_field}.pdf_pages") for page in _array(claim["pdf_pages"], f"{claim_field}.pdf_pages")]
            if not pages or pages != sorted(set(pages)):
                raise ClaimLedgerError(f"{claim_id} pages must be non-empty, unique, and sorted")

        supplied = None if pdf_files is None else pdf_files.get(versioned_id)
        if supplied is not None:
            if supplied.is_symlink() or not supplied.is_file():
                raise ClaimLedgerError(f"PDF for {versioned_id} is not a regular file")
            payload = supplied.read_bytes()
            if len(payload) != byte_count or hashlib.sha256(payload).hexdigest() != digest:
                raise ClaimLedgerError(f"PDF bytes for {versioned_id} do not match the ledger")
            if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-4096:]:
                raise ClaimLedgerError(f"PDF for {versioned_id} is structurally truncated")
            verified_pdfs.append(versioned_id)

    extras = set(pdf_files or {}) - seen_ids
    if extras:
        raise ClaimLedgerError(f"PDF mappings contain unknown ledger IDs: {sorted(extras)}")
    if require_all_pdfs and set(verified_pdfs) != seen_ids:
        raise ClaimLedgerError("not every ledger PDF was supplied and byte-verified")
    return {
        "locked_paper_count": len(locked),
        "reviewed_pdf_count": len(entries),
        "verified_pdf_count": len(verified_pdfs),
        "claim_count": len(seen_claims),
        "coverage_complete": False,
        "human_confirmation_complete": False,
    }


def _pdf_mapping(values: Sequence[str]) -> dict[str, pathlib.Path]:
    result: dict[str, pathlib.Path] = {}
    for value in values:
        versioned_id, separator, raw_path = value.partition("=")
        if not separator or VERSIONED_ID_RE.fullmatch(versioned_id) is None or not raw_path:
            raise ClaimLedgerError("--pdf values must be VERSIONED_ID=/path/to/file.pdf")
        if versioned_id in result:
            raise ClaimLedgerError(f"duplicate --pdf mapping for {versioned_id}")
        result[versioned_id] = pathlib.Path(raw_path)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=pathlib.Path, default=pathlib.Path("docs/literature.claims.json"))
    parser.add_argument("--literature-lock", type=pathlib.Path, default=pathlib.Path("docs/literature.lock.json"))
    parser.add_argument("--pdf", action="append", default=[], help="VERSIONED_ID=/path/to/exact.pdf; repeatable")
    parser.add_argument("--require-all-pdfs", action="store_true")
    args = parser.parse_args(argv)
    try:
        ledger = _load_json(args.ledger, "claim ledger")
        lock = _load_json(args.literature_lock, "literature lock")
        result = validate_ledger(
            ledger,
            lock,
            pdf_files=_pdf_mapping(args.pdf),
            require_all_pdfs=args.require_all_pdfs,
        )
    except (ClaimLedgerError, OSError) as exc:
        print(f"claim ledger validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    if result["verified_pdf_count"] < result["reviewed_pdf_count"]:
        print("metadata-only partial validation: reviewed PDF bytes were not all supplied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
