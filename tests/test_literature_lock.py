"""Offline contracts for the primary-arXiv literature lock."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
ARXIV_NAMESPACE = "http://arxiv.org/schemas/atom"


def _load_locker() -> ModuleType:
    path = ROOT / "scripts" / "lock_literature.py"
    spec = importlib.util.spec_from_file_location("lock_literature", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOCKER = _load_locker()


def _atom_feed(*versioned_ids: str) -> bytes:
    ET.register_namespace("", ATOM_NAMESPACE)
    ET.register_namespace("arxiv", ARXIV_NAMESPACE)
    feed = ET.Element(f"{{{ATOM_NAMESPACE}}}feed")
    for index, versioned_id in enumerate(versioned_ids):
        entry = ET.SubElement(feed, f"{{{ATOM_NAMESPACE}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NAMESPACE}}}id").text = (
            f"http://arxiv.org/abs/{versioned_id}"
        )
        ET.SubElement(entry, f"{{{ATOM_NAMESPACE}}}title").text = (
            f"  Canonical\n title {index}  "
        )
        ET.SubElement(entry, f"{{{ATOM_NAMESPACE}}}published").text = (
            "2025-01-01T00:00:00Z"
        )
        ET.SubElement(entry, f"{{{ATOM_NAMESPACE}}}updated").text = (
            "2025-02-01T00:00:00Z"
        )
        author = ET.SubElement(entry, f"{{{ATOM_NAMESPACE}}}author")
        ET.SubElement(author, f"{{{ATOM_NAMESPACE}}}name").text = "Ada Example"
        ET.SubElement(
            entry,
            f"{{{ARXIV_NAMESPACE}}}primary_category",
            {"term": "cs.SE"},
        )
    return ET.tostring(feed, encoding="utf-8", xml_declaration=True)


def _mini_research_program(path: Path, versioned_id: str) -> None:
    path.write_text(
        "# Program\n\n"
        f"Body [paper](https://arxiv.org/abs/{versioned_id}).\n\n"
        "## Contemporary references\n\n"
        f"- [Paper](https://arxiv.org/abs/{versioned_id}).\n",
        encoding="utf-8",
    )


def test_committed_lock_matches_exact_integrated_bibliography() -> None:
    expected_ids = LOCKER.cited_versioned_ids(ROOT / "docs" / "RESEARCH_PROGRAM.md")
    lock_bytes = (ROOT / "docs" / "literature.lock.json").read_bytes()
    lock = json.loads(lock_bytes)

    assert set(lock) == {"schema_version", "source", "entries"}
    assert lock["schema_version"] == "0.1.0"
    assert set(lock["source"]) == {
        "provider",
        "api_endpoint",
        "retrieved_at",
        "versioned_ids_sha256",
        "responses",
    }
    assert lock["source"]["provider"] == "arXiv"
    assert lock["source"]["api_endpoint"] == LOCKER.ARXIV_API_ENDPOINT
    assert LOCKER.UTC_TIMESTAMP_RE.fullmatch(lock["source"]["retrieved_at"])

    canonical_ids = "\n".join(expected_ids) + "\n"
    assert lock["source"]["versioned_ids_sha256"] == hashlib.sha256(
        canonical_ids.encode("utf-8")
    ).hexdigest()
    assert len(lock["source"]["responses"]) == 1
    response = lock["source"]["responses"][0]
    assert response["entry_count"] == len(expected_ids)
    assert len(response["raw_atom_sha256"]) == 64

    entries = lock["entries"]
    assert [entry["versioned_id"] for entry in entries] == list(expected_ids)
    for entry in entries:
        assert set(entry) == {
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
        }
        assert entry["canonical_title"]
        assert entry["authors"] and all(entry["authors"])
        assert LOCKER.UTC_TIMESTAMP_RE.fullmatch(entry["published_at"])
        assert LOCKER.UTC_TIMESTAMP_RE.fullmatch(entry["updated_at"])
        assert entry["abs_url"] == f"https://arxiv.org/abs/{entry['versioned_id']}"
        assert entry["pdf_url"] == f"https://arxiv.org/pdf/{entry['versioned_id']}"


def test_lock_builder_is_strict_about_response_identity_and_duplicates() -> None:
    first = "2504.07164v1"
    second = "2606.28436v1"
    first_response = _atom_feed(first)

    with pytest.raises(LOCKER.LiteratureLockError, match="missing"):
        LOCKER.build_lock(
            (first, second),
            ((first_response, "saved-response:first.xml"),),
            retrieved_at="2026-07-13T00:00:00Z",
        )

    with pytest.raises(LOCKER.LiteratureLockError, match="duplicate entries"):
        LOCKER.build_lock(
            (first,),
            (
                (first_response, "saved-response:first.xml"),
                (first_response, "saved-response:duplicate.xml"),
            ),
            retrieved_at="2026-07-13T00:00:00Z",
        )


def test_offline_cli_writes_atomic_lock_and_requires_retrieval_time(
    tmp_path: Path,
) -> None:
    versioned_id = "2504.07164v1"
    research_program = tmp_path / "program.md"
    response = tmp_path / "response.xml"
    output = tmp_path / "lock.json"
    _mini_research_program(research_program, versioned_id)
    response.write_bytes(_atom_feed(versioned_id))

    assert LOCKER.main(
        [
            "--research-program",
            str(research_program),
            "--response",
            str(response),
            "--retrieved-at",
            "2026-07-13T00:00:00Z",
            "--output",
            str(output),
        ]
    ) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["entries"][0][
        "canonical_title"
    ] == "Canonical title 0"

    output.unlink()
    assert LOCKER.main(
        [
            "--research-program",
            str(research_program),
            "--response",
            str(response),
            "--output",
            str(output),
        ]
    ) == 1
    assert not output.exists()


def test_citation_extractor_rejects_version_drift(tmp_path: Path) -> None:
    program = tmp_path / "program.md"
    program.write_text(
        "Body https://arxiv.org/abs/2504.07164v1\n\n"
        "## Contemporary references\n\n"
        "- https://arxiv.org/abs/2504.07164v2\n",
        encoding="utf-8",
    )

    with pytest.raises(LOCKER.LiteratureLockError, match="citation mismatch"):
        LOCKER.cited_versioned_ids(program)
