"""Contracts for the partial claim-level primary-PDF ledger."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_validator() -> ModuleType:
    path = ROOT / "scripts" / "verify_claim_ledger.py"
    spec = importlib.util.spec_from_file_location("verify_claim_ledger", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _inputs() -> tuple[dict[str, object], dict[str, object]]:
    ledger = json.loads((ROOT / "docs" / "literature.claims.json").read_text())
    lock = json.loads((ROOT / "docs" / "literature.lock.json").read_text())
    return ledger, lock


def test_checked_in_claim_ledger_is_partial_and_lock_bound() -> None:
    ledger, lock = _inputs()
    report = VALIDATOR.validate_ledger(ledger, lock)

    assert report == {
        "locked_paper_count": 66,
        "reviewed_pdf_count": 22,
        "verified_pdf_count": 0,
        "claim_count": 31,
        "coverage_complete": False,
        "human_confirmation_complete": False,
    }
    assert all(entry["review"]["human_confirmed"] is False for entry in ledger["entries"])


def test_every_claim_mapping_is_cited_by_the_research_boundary() -> None:
    ledger, _ = _inputs()
    narrative = (ROOT / "docs" / "RESEARCH_PROGRAM.md").read_text(encoding="utf-8")

    claim_ids = {
        claim["claim_id"]
        for entry in ledger["entries"]
        for claim in entry["claims"]
    }
    assert len(claim_ids) == 31
    assert all(f"`{claim_id}`" in narrative for claim_id in claim_ids)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["entries"][0].update(pdf_url="https://evil.example/x"), "PDF URL"),
        (lambda value: value["entries"][0].update(canonical_title="drift"), "title"),
        (lambda value: value["entries"][0]["claims"][0].update(pdf_pages=[]), "pages"),
        (lambda value: value["entries"][1]["claims"][0].update(claim_id="r2e-fixed-topn-hybrid"), "duplicate claim"),
        (lambda value: value["coverage"].update(complete=True), "cannot claim complete"),
        (lambda value: value["entries"][0]["review"].update(human_confirmed=True), "cannot claim human"),
        (lambda value: value["entries"].reverse(), "sorted by versioned ID"),
    ],
)
def test_claim_ledger_rejects_claim_and_provenance_drift(mutation: object, message: str) -> None:
    ledger, lock = _inputs()
    tampered = copy.deepcopy(ledger)
    mutation(tampered)
    with pytest.raises(VALIDATOR.ClaimLedgerError, match=message):
        VALIDATOR.validate_ledger(tampered, lock)


def test_optional_pdf_verification_binds_exact_bytes(tmp_path: Path) -> None:
    ledger, lock = _inputs()
    adjusted = copy.deepcopy(ledger)
    payload = b"%PDF-1.7\nclaim-ledger-fixture\n%%EOF\n"
    first = adjusted["entries"][0]
    first["pdf_bytes"] = len(payload)
    first["pdf_sha256"] = hashlib.sha256(payload).hexdigest()
    path = tmp_path / first["artifact_name"]
    path.write_bytes(payload)

    report = VALIDATOR.validate_ledger(
        adjusted,
        lock,
        pdf_files={first["versioned_id"]: path},
    )
    assert report["verified_pdf_count"] == 1

    path.write_bytes(payload + b"tamper")
    with pytest.raises(VALIDATOR.ClaimLedgerError, match="do not match"):
        VALIDATOR.validate_ledger(
            adjusted,
            lock,
            pdf_files={first["versioned_id"]: path},
        )


def test_require_all_pdfs_cannot_pass_metadata_only() -> None:
    ledger, lock = _inputs()
    with pytest.raises(VALIDATOR.ClaimLedgerError, match="not every ledger PDF"):
        VALIDATOR.validate_ledger(ledger, lock, require_all_pdfs=True)
