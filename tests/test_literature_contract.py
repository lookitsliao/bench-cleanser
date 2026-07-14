from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
ARXIV_NAMESPACE = "http://arxiv.org/schemas/atom"
ARXIV_LINK = re.compile(
    r"https://arxiv\.org/abs/(?P<id>\d{4}\.(?:\d{5}|\d{4}))v(?P<version>\d+)"
)
UNVERSIONED_ARXIV_LINK = re.compile(
    r"https://arxiv\.org/abs/\d{4}\.(?:\d{5}|\d{4})(?!\d|v\d)"
)


def _load_locker() -> ModuleType:
    path = ROOT / "scripts" / "lock_literature.py"
    spec = importlib.util.spec_from_file_location("literature_contract_locker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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
            f" Canonical\n title {index} "
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


def _mini_program(path: Path, versioned_id: str) -> None:
    path.write_text(
        "# Program\n\n"
        f"Body [paper](https://arxiv.org/abs/{versioned_id}).\n\n"
        "## Contemporary references\n\n"
        f"- [Paper](https://arxiv.org/abs/{versioned_id}).\n",
        encoding="utf-8",
    )


class _FakeResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        final_url: str,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.final_url = final_url
        self.status = status
        self.headers = headers or {"Content-Type": "application/atom+xml"}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def geturl(self) -> str:
        return self.final_url

    def read(self, maximum_bytes: int) -> bytes:
        return self.payload[:maximum_bytes]


def test_research_program_literature_boundary_is_versioned_and_integrated() -> None:
    text = (ROOT / "docs" / "RESEARCH_PROGRAM.md").read_text(encoding="utf-8")
    body, bibliography = text.split("## Contemporary references", maxsplit=1)

    assert UNVERSIONED_ARXIV_LINK.findall(text) == []

    body_ids = {match.group("id") for match in ARXIV_LINK.finditer(body)}
    bibliography_matches = list(ARXIV_LINK.finditer(bibliography))
    bibliography_ids = {match.group("id") for match in bibliography_matches}

    assert body_ids == bibliography_ids
    assert len(bibliography_matches) == len(bibliography_ids)


def test_checked_in_lock_strictly_matches_all_70_current_citations() -> None:
    lock = LOCKER.load_and_validate_lock(
        ROOT / "docs" / "literature.lock.json",
        ROOT / "docs" / "RESEARCH_PROGRAM.md",
    )

    expected_ids = LOCKER.cited_versioned_ids(ROOT / "docs" / "RESEARCH_PROGRAM.md")
    assert len(expected_ids) == 70
    assert [entry["versioned_id"] for entry in lock["entries"]] == list(expected_ids)
    assert len(lock["source"]["responses"]) == 1
    response = lock["source"]["responses"][0]
    assert response["entry_count"] == 70
    assert LOCKER.SHA256_RE.fullmatch(response["raw_atom_sha256"])
    assert response["request_url"] == LOCKER._request_url(expected_ids)


def test_checked_in_lock_loader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    original = (ROOT / "docs" / "literature.lock.json").read_text(encoding="utf-8")
    duplicate = original.replace(
        '  "schema_version": "0.1.0",',
        '  "schema_version": "0.1.0",\n  "schema_version": "0.1.0",',
        1,
    )
    path = tmp_path / "duplicate.json"
    path.write_text(duplicate, encoding="utf-8")

    with pytest.raises(LOCKER.LiteratureLockError, match="duplicate JSON object key"):
        LOCKER.load_and_validate_lock(
            path,
            ROOT / "docs" / "RESEARCH_PROGRAM.md",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda entry: entry.update(abs_url="http://arxiv.org/abs/bad"), "abs_url"),
        (lambda entry: entry.update(published_at="2026-99-99T00:00:00Z"), "real UTC"),
        (lambda entry: entry.update(canonical_title=" title "), "trimmed|canonical"),
        (lambda entry: entry.update(authors=["Ada", "Ada"]), "duplicates"),
        (lambda entry: entry.update(primary_category="cs SE"), "primary_category"),
    ],
)
def test_lock_validator_rejects_noncanonical_metadata(
    mutation: Any,
    message: str,
) -> None:
    expected_ids = LOCKER.cited_versioned_ids(ROOT / "docs" / "RESEARCH_PROGRAM.md")
    decoded = LOCKER.strict_json_loads(
        (ROOT / "docs" / "literature.lock.json").read_text(encoding="utf-8")
    )
    tampered = copy.deepcopy(decoded)
    mutation(tampered["entries"][0])

    with pytest.raises(LOCKER.LiteratureLockError, match=message):
        LOCKER.validate_lock_payload(
            tampered,
            expected_ids,
            require_primary_response=True,
            expected_entry_count=70,
        )


def test_atom_parser_rejects_duplicates_missing_fields_dtd_and_size() -> None:
    versioned_id = "2504.07164v1"
    with pytest.raises(LOCKER.LiteratureLockError, match="duplicate arXiv entry"):
        LOCKER.parse_atom_response(_atom_feed(versioned_id, versioned_id))

    root = ET.fromstring(_atom_feed(versioned_id))
    entry = root.find(f"{{{ATOM_NAMESPACE}}}entry")
    assert entry is not None
    title = entry.find(f"{{{ATOM_NAMESPACE}}}title")
    assert title is not None
    entry.remove(title)
    with pytest.raises(LOCKER.LiteratureLockError, match="title"):
        LOCKER.parse_atom_response(
            ET.tostring(root, encoding="utf-8", xml_declaration=True)
        )

    dtd = (
        b'<!DOCTYPE feed [<!ENTITY x "expanded">]>'
        + _atom_feed(versioned_id)
    )
    with pytest.raises(LOCKER.LiteratureLockError, match="DTD/entity"):
        LOCKER.parse_atom_response(dtd)
    with pytest.raises(LOCKER.LiteratureLockError, match="size bound"):
        LOCKER.parse_atom_response(b"x" * (LOCKER.MAX_RESPONSE_BYTES + 1))


def test_lock_builder_rejects_missing_unexpected_and_cross_response_duplicates() -> None:
    first = "2504.07164v1"
    second = "2606.28436v1"
    first_response = _atom_feed(first)
    second_response = _atom_feed(second)

    with pytest.raises(LOCKER.LiteratureLockError, match="missing"):
        LOCKER.build_lock(
            (first, second),
            ((first_response, "saved-response:first.xml"),),
            retrieved_at="2026-07-13T00:00:00Z",
        )
    with pytest.raises(LOCKER.LiteratureLockError, match="unexpected"):
        LOCKER.build_lock(
            (first,),
            ((second_response, "saved-response:second.xml"),),
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


def test_fetch_rejects_invalid_timeout_redirect_and_oversized_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versioned_ids = ("2504.07164v1",)
    url = LOCKER._request_url(versioned_ids)
    for invalid in (True, 0, float("inf"), LOCKER.MAX_TIMEOUT_SECONDS + 1):
        with pytest.raises(LOCKER.LiteratureLockError, match="timeout_seconds"):
            LOCKER.fetch_atom_response(versioned_ids, timeout_seconds=invalid)

    monkeypatch.setattr(
        LOCKER.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            _atom_feed(*versioned_ids),
            final_url="https://evil.example/redirect",
        ),
    )
    with pytest.raises(LOCKER.LiteratureLockError, match="redirected"):
        LOCKER.fetch_atom_response(versioned_ids, timeout_seconds=5)

    monkeypatch.setattr(
        LOCKER.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            _atom_feed(*versioned_ids),
            final_url=url,
            headers={
                "Content-Type": "application/atom+xml",
                "Content-Length": str(LOCKER.MAX_RESPONSE_BYTES + 1),
            },
        ),
    )
    with pytest.raises(LOCKER.LiteratureLockError, match="declared.*byte bound"):
        LOCKER.fetch_atom_response(versioned_ids, timeout_seconds=5)


def test_fetch_success_binds_exact_final_url_and_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versioned_ids = ("2504.07164v1",)
    url = LOCKER._request_url(versioned_ids)
    payload = _atom_feed(*versioned_ids)
    observed: dict[str, Any] = {}

    def urlopen(request: Any, *, timeout: float) -> _FakeResponse:
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        return _FakeResponse(
            payload,
            final_url=url,
            headers={
                "Content-Type": "application/atom+xml; charset=utf-8",
                "Content-Length": str(len(payload)),
            },
        )

    monkeypatch.setattr(LOCKER.urllib.request, "urlopen", urlopen)
    fetched, request_url = LOCKER.fetch_atom_response(
        versioned_ids,
        timeout_seconds=5,
    )
    assert fetched == payload
    assert request_url == url
    assert observed == {"url": url, "timeout": 5}


def test_atomic_and_network_failures_preserve_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lock.json"
    output.write_text("sentinel\n", encoding="utf-8")
    monkeypatch.setattr(
        LOCKER.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("replace failed")),
    )
    with pytest.raises(OSError, match="replace failed"):
        LOCKER._atomic_write_json(output, {"replacement": True})
    assert output.read_text(encoding="utf-8") == "sentinel\n"
    assert not list(tmp_path.glob(".lock.json.*"))

    monkeypatch.undo()
    program = tmp_path / "program.md"
    _mini_program(program, "2504.07164v1")
    monkeypatch.setattr(
        LOCKER,
        "fetch_atom_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            LOCKER.LiteratureLockError("network failed")
        ),
    )
    assert LOCKER.main(
        [
            "--research-program",
            str(program),
            "--output",
            str(output),
        ]
    ) == 1
    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_offline_regeneration_is_atomic_and_self_validating(tmp_path: Path) -> None:
    versioned_id = "2504.07164v1"
    program = tmp_path / "program.md"
    response = tmp_path / "response.xml"
    output = tmp_path / "lock.json"
    _mini_program(program, versioned_id)
    response.write_bytes(_atom_feed(versioned_id))

    assert LOCKER.main(
        [
            "--research-program",
            str(program),
            "--response",
            str(response),
            "--retrieved-at",
            "2026-07-13T00:00:00Z",
            "--output",
            str(output),
        ]
    ) == 0
    payload = LOCKER.strict_json_loads(output.read_text(encoding="utf-8"))
    validated = LOCKER.validate_lock_payload(
        payload,
        (versioned_id,),
        require_primary_response=False,
        expected_entry_count=1,
    )
    assert validated["entries"][0]["canonical_title"] == "Canonical title 0"
    assert json.loads(output.read_text(encoding="utf-8")) == payload
