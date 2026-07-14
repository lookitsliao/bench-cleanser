#!/usr/bin/env python3
"""Create a strict, machine-readable lock for cited arXiv literature."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
ARXIV_API_ENDPOINT = "https://export.arxiv.org/api/query"
ARXIV_LINK_RE = re.compile(
    r"https://arxiv\.org/abs/(?P<arxiv_id>\d{4}\.(?:\d{5}|\d{4}))"
    r"v(?P<version>[1-9]\d*)"
)
VERSIONED_ID_RE = re.compile(
    r"(?P<arxiv_id>\d{4}\.(?:\d{5}|\d{4}))v(?P<version>[1-9]\d*)"
)
UTC_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
CATEGORY_RE = re.compile(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*")
BIBLIOGRAPHY_MARKER = "## Contemporary references"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 120.0
EXPECTED_CHECKED_IN_ENTRY_COUNT = 70
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


class LiteratureLockError(ValueError):
    """Raised when literature inputs are missing, ambiguous, or inconsistent."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_text(value: str) -> str:
    return " ".join(value.split())


def _reject_json_constant(value: str) -> None:
    raise LiteratureLockError(f"non-standard JSON constant {value!r} is not allowed")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LiteratureLockError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def strict_json_loads(value: str) -> Any:
    """Decode standard JSON while rejecting duplicate keys and NaN extensions."""

    try:
        return json.loads(
            value,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise LiteratureLockError(f"invalid literature lock JSON: {exc}") from exc


def _validate_utc_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise LiteratureLockError(f"{field} must be an RFC 3339 UTC timestamp")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise LiteratureLockError(f"{field} is not a real UTC timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise LiteratureLockError(f"{field} is not a canonical UTC timestamp")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        raise LiteratureLockError(f"{field} is missing fields: {missing}")
    if unknown:
        raise LiteratureLockError(f"{field} has unknown fields: {unknown}")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiteratureLockError(f"{field} must be a JSON object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise LiteratureLockError(f"{field} must be a JSON array")
    return value


def _string(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise LiteratureLockError(f"{field} must be a trimmed non-empty string")
    return value


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LiteratureLockError(f"{field} must be a positive integer")
    return value


def _version_map(text: str) -> dict[str, int]:
    versions: dict[str, int] = {}
    for match in ARXIV_LINK_RE.finditer(text):
        arxiv_id = match.group("arxiv_id")
        version = int(match.group("version"))
        prior = versions.setdefault(arxiv_id, version)
        if prior != version:
            raise LiteratureLockError(
                f"arXiv identity {arxiv_id} is cited at both v{prior} and v{version}"
            )
    return versions


def cited_versioned_ids(research_program: Path) -> tuple[str, ...]:
    try:
        text = research_program.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LiteratureLockError(f"cannot read research program: {exc}") from exc
    if text.count(BIBLIOGRAPHY_MARKER) != 1:
        raise LiteratureLockError("research program must contain one bibliography marker")
    body, bibliography = text.split(BIBLIOGRAPHY_MARKER, maxsplit=1)
    body_versions = _version_map(body)
    bibliography_versions = _version_map(bibliography)
    if not bibliography_versions:
        raise LiteratureLockError("bibliography has no versioned arXiv citations")
    if body_versions != bibliography_versions:
        missing = sorted(set(bibliography_versions) - set(body_versions))
        body_only = sorted(set(body_versions) - set(bibliography_versions))
        mismatched = sorted(
            arxiv_id
            for arxiv_id in set(body_versions).intersection(bibliography_versions)
            if body_versions[arxiv_id] != bibliography_versions[arxiv_id]
        )
        raise LiteratureLockError(
            "body/bibliography citation mismatch: "
            f"missing_from_body={missing}, body_only={body_only}, "
            f"version_mismatch={mismatched}"
        )
    bibliography_matches = list(ARXIV_LINK_RE.finditer(bibliography))
    if len(bibliography_matches) != len(bibliography_versions):
        raise LiteratureLockError("bibliography must list each arXiv identity exactly once")
    return tuple(
        f"{arxiv_id}v{bibliography_versions[arxiv_id]}"
        for arxiv_id in sorted(bibliography_versions)
    )


def _required_text(entry: ET.Element, tag: str, versioned_id: str) -> str:
    elements = entry.findall(f"{ATOM}{tag}")
    if len(elements) != 1:
        raise LiteratureLockError(
            f"{versioned_id} must contain exactly one Atom {tag} element"
        )
    element = elements[0]
    value = "" if element.text is None else _canonical_text(element.text)
    if not value:
        raise LiteratureLockError(f"{versioned_id} has no {tag}")
    return value


def parse_atom_response(data: bytes) -> tuple[dict[str, dict[str, Any]], str]:
    if not data or len(data) > MAX_RESPONSE_BYTES:
        raise LiteratureLockError("arXiv response is empty or exceeds the size bound")
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise LiteratureLockError("DTD/entity declarations are forbidden in Atom XML")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise LiteratureLockError(f"arXiv returned invalid Atom XML: {exc}") from exc
    if root.tag != f"{ATOM}feed":
        raise LiteratureLockError("arXiv response root is not an Atom feed")

    records: dict[str, dict[str, Any]] = {}
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = _required_text(entry, "id", "unknown entry")
        match = re.fullmatch(
            r"https?://arxiv\.org/abs/(?P<versioned_id>"
            + VERSIONED_ID_RE.pattern
            + r")",
            entry_id,
        )
        if match is None:
            raise LiteratureLockError(f"unexpected arXiv entry identity: {entry_id!r}")
        versioned_id = match.group("versioned_id")
        if versioned_id in records:
            raise LiteratureLockError(f"duplicate arXiv entry: {versioned_id}")

        published_at = _required_text(entry, "published", versioned_id)
        updated_at = _required_text(entry, "updated", versioned_id)
        _validate_utc_timestamp(published_at, f"{versioned_id}.published")
        _validate_utc_timestamp(updated_at, f"{versioned_id}.updated")
        if updated_at < published_at:
            raise LiteratureLockError(f"{versioned_id} updated before it was published")
        authors: list[str] = []
        for author_index, author in enumerate(entry.findall(f"{ATOM}author")):
            names = author.findall(f"{ATOM}name")
            if len(names) != 1:
                raise LiteratureLockError(
                    f"{versioned_id} author {author_index} must contain exactly one name"
                )
            authors.append(_canonical_text(names[0].text or ""))
        if not authors or any(not author for author in authors):
            raise LiteratureLockError(f"{versioned_id} has no complete author list")
        if len(authors) != len(set(authors)):
            raise LiteratureLockError(f"{versioned_id} contains duplicate authors")
        primary_elements = entry.findall(f"{ARXIV}primary_category")
        if len(primary_elements) != 1:
            raise LiteratureLockError(
                f"{versioned_id} must contain exactly one primary category"
            )
        primary_category = primary_elements[0].attrib.get("term", "")
        if (
            not primary_category
            or primary_category != primary_category.strip()
            or CATEGORY_RE.fullmatch(primary_category) is None
        ):
            raise LiteratureLockError(f"{versioned_id} has no primary category")

        records[versioned_id] = {
            "arxiv_id": match.group("arxiv_id"),
            "version": int(match.group("version")),
            "versioned_id": versioned_id,
            "canonical_title": _required_text(entry, "title", versioned_id),
            "authors": authors,
            "published_at": published_at,
            "updated_at": updated_at,
            "primary_category": primary_category,
            "abs_url": f"https://arxiv.org/abs/{versioned_id}",
            "pdf_url": f"https://arxiv.org/pdf/{versioned_id}",
        }
    if not records:
        raise LiteratureLockError("arXiv response contains no entries")
    return records, _sha256_bytes(data)


def _request_url(versioned_ids: Sequence[str]) -> str:
    query = urllib.parse.urlencode(
        {
            "id_list": ",".join(versioned_ids),
            "start": 0,
            "max_results": len(versioned_ids),
        }
    )
    return f"{ARXIV_API_ENDPOINT}?{query}"


def _validated_versioned_ids(versioned_ids: Sequence[str]) -> tuple[str, ...]:
    if not versioned_ids:
        raise LiteratureLockError("at least one versioned arXiv ID is required")
    typed = tuple(versioned_ids)
    if any(not isinstance(value, str) for value in typed):
        raise LiteratureLockError("versioned arXiv IDs must be strings")
    if len(typed) != len(set(typed)):
        raise LiteratureLockError("requested versioned IDs are not unique")
    for versioned_id in typed:
        if VERSIONED_ID_RE.fullmatch(versioned_id) is None:
            raise LiteratureLockError(f"invalid versioned arXiv ID: {versioned_id!r}")
    if typed != tuple(sorted(typed)):
        raise LiteratureLockError("versioned arXiv IDs must be in canonical order")
    return typed


def _validate_response_locator(
    request_url: str,
    response_ids: Sequence[str],
) -> None:
    if not isinstance(request_url, str) or not request_url:
        raise LiteratureLockError("response request_url must be a non-empty string")
    if request_url.startswith("saved-response:"):
        name = request_url.removeprefix("saved-response:")
        if (
            not name
            or name != Path(name).name
            or name in {".", ".."}
            or any(ord(character) < 32 for character in name)
        ):
            raise LiteratureLockError("saved response locator is not a confined basename")
        return
    expected_url = _request_url(tuple(sorted(response_ids)))
    if request_url != expected_url:
        raise LiteratureLockError(
            "Atom response request URL does not match its exact versioned IDs"
        )


def fetch_atom_response(
    versioned_ids: Sequence[str], *, timeout_seconds: float
) -> tuple[bytes, str]:
    versioned_ids = _validated_versioned_ids(versioned_ids)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0 < float(timeout_seconds) <= MAX_TIMEOUT_SECONDS
    ):
        raise LiteratureLockError(
            f"timeout_seconds must be finite and in (0, {MAX_TIMEOUT_SECONDS:g}]"
        )
    url = _request_url(versioned_ids)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/atom+xml",
            "User-Agent": "bench-cleanser-literature-lock/0.1 (+https://github.com/lookitsliao/bench-cleanser)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status != 200:
                raise LiteratureLockError(f"arXiv API returned HTTP {status}")
            final_url = response.geturl()
            if final_url != url:
                raise LiteratureLockError(
                    f"arXiv API redirected outside the exact request URL: {final_url!r}"
                )
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except (TypeError, ValueError) as exc:
                    raise LiteratureLockError(
                        "arXiv API returned an invalid Content-Length"
                    ) from exc
                if not 0 <= declared_length <= MAX_RESPONSE_BYTES:
                    raise LiteratureLockError(
                        "arXiv API declared a response outside the byte bound"
                    )
            content_type = response.headers.get("Content-Type")
            if content_type is not None and content_type.split(";", 1)[0].strip() not in {
                "application/atom+xml",
                "application/xml",
                "text/xml",
            }:
                raise LiteratureLockError(
                    f"arXiv API returned an unexpected content type: {content_type!r}"
                )
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise LiteratureLockError(f"cannot fetch arXiv metadata: {exc}") from exc
    if len(data) > MAX_RESPONSE_BYTES:
        raise LiteratureLockError("arXiv response exceeds the size bound")
    return data, url


def build_lock(
    versioned_ids: Sequence[str],
    responses: Iterable[tuple[bytes, str]],
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    _validate_utc_timestamp(retrieved_at, "retrieved_at")
    versioned_ids = _validated_versioned_ids(versioned_ids)
    expected = set(versioned_ids)

    combined: dict[str, dict[str, Any]] = {}
    response_records: list[dict[str, Any]] = []
    for data, request_url in responses:
        parsed, digest = parse_atom_response(data)
        _validate_response_locator(request_url, tuple(sorted(parsed)))
        overlap = set(combined).intersection(parsed)
        if overlap:
            raise LiteratureLockError(f"duplicate entries across responses: {sorted(overlap)}")
        combined.update(parsed)
        response_records.append(
            {
                "request_url": request_url,
                "raw_atom_sha256": digest,
                "entry_count": len(parsed),
            }
        )
    if not response_records:
        raise LiteratureLockError("at least one Atom response is required")
    missing = sorted(expected - set(combined))
    unexpected = sorted(set(combined) - expected)
    if missing or unexpected:
        raise LiteratureLockError(
            f"arXiv response identity mismatch: missing={missing}, unexpected={unexpected}"
        )
    canonical_ids = "\n".join(versioned_ids) + "\n"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "provider": "arXiv",
            "api_endpoint": ARXIV_API_ENDPOINT,
            "retrieved_at": retrieved_at,
            "versioned_ids_sha256": _sha256_bytes(canonical_ids.encode("utf-8")),
            "responses": response_records,
        },
        "entries": [combined[versioned_id] for versioned_id in versioned_ids],
    }
    validate_lock_payload(
        payload,
        versioned_ids,
        require_primary_response=False,
    )
    return payload


def _primary_request_ids(url: str) -> tuple[str, ...]:
    parsed = urllib.parse.urlsplit(url)
    endpoint = urllib.parse.urlsplit(ARXIV_API_ENDPOINT)
    if (
        parsed.scheme != endpoint.scheme
        or parsed.netloc != endpoint.netloc
        or parsed.path != endpoint.path
        or parsed.fragment
    ):
        raise LiteratureLockError("response request_url is not the canonical arXiv endpoint")
    try:
        pairs = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise LiteratureLockError("response request_url query is malformed") from exc
    if len(pairs) != len({key for key, _ in pairs}):
        raise LiteratureLockError("response request_url contains duplicate query fields")
    values = dict(pairs)
    if set(values) != {"id_list", "start", "max_results"} or values["start"] != "0":
        raise LiteratureLockError("response request_url query contract drifted")
    ids = tuple(values["id_list"].split(","))
    ids = _validated_versioned_ids(ids)
    try:
        maximum = int(values["max_results"])
    except ValueError as exc:
        raise LiteratureLockError("response request_url max_results is not an integer") from exc
    if maximum != len(ids) or url != _request_url(ids):
        raise LiteratureLockError("response request_url is not canonically encoded")
    return ids


def validate_lock_payload(
    payload: Mapping[str, Any],
    versioned_ids: Sequence[str],
    *,
    require_primary_response: bool,
    expected_entry_count: int | None = None,
) -> dict[str, Any]:
    """Validate every checked-lock identity and canonical metadata field."""

    expected_ids = _validated_versioned_ids(versioned_ids)
    if expected_entry_count is not None:
        if (
            isinstance(expected_entry_count, bool)
            or not isinstance(expected_entry_count, int)
            or expected_entry_count < 1
        ):
            raise LiteratureLockError("expected_entry_count must be a positive integer")
        if len(expected_ids) != expected_entry_count:
            raise LiteratureLockError(
                "citation count drifted: "
                f"expected {expected_entry_count}, got {len(expected_ids)}"
            )
    root = _object(payload, "literature lock")
    _exact_fields(root, {"schema_version", "source", "entries"}, "literature lock")
    if root["schema_version"] != SCHEMA_VERSION:
        raise LiteratureLockError("literature lock schema_version drifted")
    source = _object(root["source"], "literature lock.source")
    _exact_fields(
        source,
        {
            "provider",
            "api_endpoint",
            "retrieved_at",
            "versioned_ids_sha256",
            "responses",
        },
        "literature lock.source",
    )
    if source["provider"] != "arXiv" or source["api_endpoint"] != ARXIV_API_ENDPOINT:
        raise LiteratureLockError("literature lock provider/API identity drifted")
    _validate_utc_timestamp(source["retrieved_at"], "source.retrieved_at")
    expected_id_digest = _sha256_bytes(
        ("\n".join(expected_ids) + "\n").encode("utf-8")
    )
    if source["versioned_ids_sha256"] != expected_id_digest:
        raise LiteratureLockError("literature lock versioned-ID-set digest drifted")

    responses = _array(source["responses"], "literature lock.source.responses")
    if not responses:
        raise LiteratureLockError("literature lock must contain response provenance")
    if require_primary_response and len(responses) != 1:
        raise LiteratureLockError("checked-in lock requires one primary arXiv response")
    response_entry_total = 0
    primary_ids: set[str] = set()
    saw_saved_response = False
    for index, raw_response in enumerate(responses):
        field = f"literature lock.source.responses[{index}]"
        response = _object(raw_response, field)
        _exact_fields(
            response,
            {"request_url", "raw_atom_sha256", "entry_count"},
            field,
        )
        request_url = _string(response["request_url"], f"{field}.request_url")
        digest = _string(response["raw_atom_sha256"], f"{field}.raw_atom_sha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise LiteratureLockError(f"{field}.raw_atom_sha256 is not lowercase SHA-256")
        entry_count = _positive_integer(response["entry_count"], f"{field}.entry_count")
        response_entry_total += entry_count
        if request_url.startswith("saved-response:"):
            saw_saved_response = True
            _validate_response_locator(request_url, ())
        else:
            response_ids = _primary_request_ids(request_url)
            if len(response_ids) != entry_count:
                raise LiteratureLockError(f"{field} count contradicts its request URL")
            if primary_ids.intersection(response_ids):
                raise LiteratureLockError("primary response request IDs overlap")
            primary_ids.update(response_ids)
    if response_entry_total != len(expected_ids):
        raise LiteratureLockError("response entry counts contradict the citation set")
    if require_primary_response:
        if saw_saved_response or primary_ids != set(expected_ids):
            raise LiteratureLockError(
                "checked-in lock must bind the exact primary arXiv request"
            )

    entries = _array(root["entries"], "literature lock.entries")
    if len(entries) != len(expected_ids):
        raise LiteratureLockError("literature lock entry count contradicts citations")
    normalized_entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_entry in enumerate(entries):
        field = f"literature lock.entries[{index}]"
        entry = _object(raw_entry, field)
        _exact_fields(
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
            field,
        )
        versioned_id = _string(entry["versioned_id"], f"{field}.versioned_id")
        match = VERSIONED_ID_RE.fullmatch(versioned_id)
        if match is None or versioned_id in seen_ids:
            raise LiteratureLockError(f"{field}.versioned_id is invalid or duplicate")
        seen_ids.add(versioned_id)
        if versioned_id != expected_ids[index]:
            raise LiteratureLockError("literature lock entries are not in exact citation order")
        version = _positive_integer(entry["version"], f"{field}.version")
        if entry["arxiv_id"] != match.group("arxiv_id") or version != int(
            match.group("version")
        ):
            raise LiteratureLockError(f"{field} arXiv ID/version fields contradict each other")
        title = _string(entry["canonical_title"], f"{field}.canonical_title")
        if title != _canonical_text(title):
            raise LiteratureLockError(f"{field}.canonical_title is not canonical text")
        authors = _array(entry["authors"], f"{field}.authors")
        if not authors:
            raise LiteratureLockError(f"{field}.authors cannot be empty")
        normalized_authors = [
            _string(author, f"{field}.authors[{author_index}]")
            for author_index, author in enumerate(authors)
        ]
        if any(author != _canonical_text(author) for author in normalized_authors):
            raise LiteratureLockError(f"{field}.authors are not canonical text")
        if len(normalized_authors) != len(set(normalized_authors)):
            raise LiteratureLockError(f"{field}.authors contains duplicates")
        published_at = _validate_utc_timestamp(
            entry["published_at"],
            f"{field}.published_at",
        )
        updated_at = _validate_utc_timestamp(
            entry["updated_at"],
            f"{field}.updated_at",
        )
        if updated_at < published_at:
            raise LiteratureLockError(f"{field} updated before publication")
        category = _string(entry["primary_category"], f"{field}.primary_category")
        if CATEGORY_RE.fullmatch(category) is None:
            raise LiteratureLockError(f"{field}.primary_category is invalid")
        if entry["abs_url"] != f"https://arxiv.org/abs/{versioned_id}":
            raise LiteratureLockError(f"{field}.abs_url is not canonical")
        if entry["pdf_url"] != f"https://arxiv.org/pdf/{versioned_id}":
            raise LiteratureLockError(f"{field}.pdf_url is not canonical")
        normalized_entries.append(dict(entry))
    if seen_ids != set(expected_ids):
        raise LiteratureLockError("literature lock does not contain the exact citation set")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": dict(source),
        "entries": normalized_entries,
    }


def load_and_validate_lock(
    lock_path: Path,
    research_program: Path,
    *,
    expected_entry_count: int = EXPECTED_CHECKED_IN_ENTRY_COUNT,
) -> dict[str, Any]:
    """Load the checked-in lock with duplicate-key and citation-parity checks."""

    versioned_ids = cited_versioned_ids(research_program)
    try:
        text = lock_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LiteratureLockError(f"cannot read literature lock: {exc}") from exc
    decoded = strict_json_loads(text)
    return validate_lock_payload(
        _object(decoded, "literature lock"),
        versioned_ids,
        require_primary_response=True,
        expected_entry_count=expected_entry_count,
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lock exact arXiv metadata for the research-program bibliography"
    )
    parser.add_argument(
        "--research-program",
        type=Path,
        default=Path("docs/RESEARCH_PROGRAM.md"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/literature.lock.json"),
    )
    parser.add_argument(
        "--response",
        type=Path,
        action="append",
        default=[],
        help="Use a saved Atom response instead of the network; repeat if needed",
    )
    parser.add_argument(
        "--retrieved-at",
        help="RFC 3339 UTC retrieval time; required with --response",
    )
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the existing output against citations without network or writes",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            if args.response or args.retrieved_at is not None:
                raise LiteratureLockError(
                    "--check cannot be combined with --response or --retrieved-at"
                )
            checked = load_and_validate_lock(
                args.output,
                args.research_program,
            )
            print(f"validated {len(checked['entries'])} entries in {args.output}")
            return 0
        versioned_ids = cited_versioned_ids(args.research_program)
        retrieved_at = args.retrieved_at or _utc_now()
        if args.response:
            if args.retrieved_at is None:
                raise LiteratureLockError("--retrieved-at is required with --response")
            responses = [
                (
                    response_path.read_bytes(),
                    f"saved-response:{response_path.name}",
                )
                for response_path in args.response
            ]
        else:
            data, request_url = fetch_atom_response(
                versioned_ids, timeout_seconds=args.timeout_seconds
            )
            responses = [(data, request_url)]
        payload = build_lock(versioned_ids, responses, retrieved_at=retrieved_at)
        _atomic_write_json(args.output, payload)
    except (LiteratureLockError, OSError) as exc:
        print(f"literature lock failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(payload['entries'])} entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
