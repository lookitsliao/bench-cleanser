#!/usr/bin/env python3
"""Build or verify a deterministic, fail-closed release evidence dossier.

The dossier is an offline verifier.  It hashes every supplied byte, inspects
Git and archive metadata directly, cross-checks report identities, and records
explicit blockers.  It never treats generated policy output as legal review or
a self-declared status field as proof that a command, CI job, or signature ran.
"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import tomllib
import urllib.parse
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.parser import BytesParser
from typing import Any, NoReturn

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion

DOSSIER_SCHEMA_VERSION = "bench-cleanser-release-dossier-0.1.0"
GATE_EVIDENCE_SCHEMA_VERSION = "bench-cleanser-release-gate-evidence-0.1.0"
LINUX_CI_SCHEMA_VERSION = "bench-cleanser-linux-ci-evidence-0.2.0"
ENVIRONMENT_LOCK_SCHEMA_VERSION = "bench-cleanser-environment-lock-0.1.0"
ATTESTATION_SCHEMA_VERSION = "bench-cleanser-human-release-attestation-0.1.0"
CLAIM_LEDGER_SCHEMA_VERSION = "literature-claim-ledger-0.1.0"
CLAIM_LEDGER_STATUS = "partial_machine_assisted_requires_human_confirmation"
RELEASE_PROFILE = "public-engineering-alpha"
PROJECT_NAME = "bench-cleanser"
PACKAGE_DIRECTORY = "bench_cleanser"
MAX_JSON_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20_000
MAX_ARCHIVE_MEMBER_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 1024 * 1024 * 1024
MIN_COVERAGE_PERCENT = 70.0
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40,64}")
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}(?:(?:a|b|rc)[0-9]+)?")
_NAME_RE = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_REQUIREMENT_NAME_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)")
_GITHUB_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_EXTRA_ONLY_MARKER_RE = re.compile(r"\s*extra\s*==\s*['\"]([A-Za-z0-9_.-]+)['\"]\s*")
_ARXIV_VERSIONED_RE = re.compile(r"[0-9]{4}\.[0-9]{4,5}v[1-9][0-9]*")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class DossierError(ValueError):
    """An input is malformed, unsafe, or cannot be inspected."""


@dataclass(frozen=True)
class FileIdentity:
    logical_name: str
    byte_count: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_name": self.logical_name,
            "bytes": self.byte_count,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class GitIdentity:
    commit: str
    tree: str
    branch: str
    dirty_entries: tuple[str, ...]
    diff_check_passed: bool
    tag: str | None
    tag_object: str | None
    tag_object_type: str | None
    tag_target: str | None
    tag_message: str | None
    tag_signature_verified: bool

    def to_dict(self) -> dict[str, Any]:
        status_payload = "\n".join(self.dirty_entries).encode("utf-8")
        return {
            "commit": self.commit,
            "tree": self.tree,
            "worktree_clean": not self.dirty_entries,
            "dirty_entry_count": len(self.dirty_entries),
            "status_sha256": _sha256(status_payload),
            "diff_check_passed": self.diff_check_passed,
            "tag": self.tag,
            "tag_object": self.tag_object,
            "tag_object_type": self.tag_object_type,
            "tag_target": self.tag_target,
            "tag_message_sha256": (
                _sha256(self.tag_message.encode("utf-8")) if self.tag_message is not None else None
            ),
            "tag_signature_verified": self.tag_signature_verified,
        }


@dataclass(frozen=True)
class DossierInputs:
    repo_root: pathlib.Path
    wheel: pathlib.Path
    sdist: pathlib.Path
    artifact_report: pathlib.Path
    sbom: pathlib.Path
    license_inventory: pathlib.Path
    license_report: pathlib.Path
    test_evidence: pathlib.Path
    coverage_evidence: pathlib.Path
    lint_evidence: pathlib.Path
    type_evidence: pathlib.Path
    linux_ci_evidence: pathlib.Path
    literature_lock: pathlib.Path
    literature_claims: pathlib.Path
    environment_lock: pathlib.Path
    study_artifacts: tuple[tuple[str, pathlib.Path], ...]
    attestation: pathlib.Path | None = None


def _die(message: str) -> NoReturn:
    raise DossierError(message)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: Any, *, indent: int | None = 2) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":") if indent is None else None,
            indent=indent,
        )
    except (TypeError, ValueError) as exc:
        raise DossierError(f"value is not canonical JSON: {exc}") from exc
    return (text + ("\n" if indent is not None else "")).encode("utf-8")


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DossierError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _regular_file(
    path: pathlib.Path,
    field: str,
    *,
    maximum: int,
    minimum: int = 1,
) -> pathlib.Path:
    if path.is_symlink() or not path.is_file():
        raise DossierError(f"{field} must be a regular non-symlink file")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DossierError(f"cannot stat {field}: {exc}") from exc
    if size < minimum or size > maximum:
        raise DossierError(f"{field} size is outside [{minimum}, {maximum}]")
    return path


def _read_bytes(
    path: pathlib.Path,
    field: str,
    *,
    maximum: int,
    minimum: int = 1,
) -> bytes:
    checked = _regular_file(path, field, maximum=maximum, minimum=minimum)
    try:
        return checked.read_bytes()
    except OSError as exc:
        raise DossierError(f"cannot read {field}: {exc}") from exc


def _file_identity(path: pathlib.Path, logical_name: str) -> FileIdentity:
    payload = _read_bytes(path, logical_name, maximum=MAX_ARCHIVE_BYTES)
    return FileIdentity(logical_name=logical_name, byte_count=len(payload), sha256=_sha256(payload))


def _read_json(path: pathlib.Path, field: str) -> tuple[dict[str, Any] | list[Any], bytes]:
    payload = _read_bytes(path, field, maximum=MAX_JSON_BYTES)
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_strict_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, DossierError) as exc:
        raise DossierError(f"invalid strict JSON in {field}: {exc}") from exc
    if not isinstance(decoded, (dict, list)):
        raise DossierError(f"{field} must contain a JSON object or array")
    return decoded, payload


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DossierError(f"{field} must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise DossierError(f"{field} keys must be strings")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise DossierError(f"{field} must be a JSON array")
    return value


def _exact_fields(value: Mapping[str, Any], fields: set[str], field: str) -> None:
    missing = sorted(fields - set(value))
    unknown = sorted(set(value) - fields)
    if missing:
        raise DossierError(f"{field} is missing fields: {missing}")
    if unknown:
        raise DossierError(f"{field} has unknown fields: {unknown}")


def _string(value: Any, field: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise DossierError(f"{field} must be a trimmed non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise DossierError(f"{field} has an invalid format")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DossierError(f"{field} must be an integer >= {minimum}")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise DossierError(f"{field} must be a boolean")
    return value


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _package_set_sha256(identities: set[tuple[str, str]]) -> str:
    projection = [{"name": name, "version": version} for name, version in sorted(identities)]
    return _sha256(_canonical_json_bytes(projection, indent=None))


def _requirement_identity(
    value: str,
    field: str,
) -> tuple[str, tuple[str, ...], str, str | None, str | None]:
    try:
        requirement = Requirement(value)
    except InvalidRequirement as exc:
        raise DossierError(f"{field} is not a valid Python requirement: {exc}") from exc
    return (
        _normalized_name(requirement.name),
        tuple(sorted(requirement.extras)),
        str(requirement.specifier),
        requirement.url,
        str(requirement.marker) if requirement.marker is not None else None,
    )


def _runtime_requirement_versions_match(
    requirements: Sequence[str],
    identities: set[tuple[str, str]],
) -> bool:
    by_name: dict[str, list[str]] = {}
    for name, version in identities:
        by_name.setdefault(name, []).append(version)
    if any(len(versions) != 1 for versions in by_name.values()):
        return False
    for index, raw_requirement in enumerate(requirements):
        requirement = Requirement(_string(raw_requirement, f"runtime requirement {index}"))
        versions = by_name.get(_normalized_name(requirement.name), [])
        if len(versions) != 1:
            return False
        try:
            if requirement.specifier and not requirement.specifier.contains(
                versions[0],
                prereleases=True,
            ):
                return False
        except (InvalidRequirement, InvalidVersion):
            return False
    return True


def _safe_relative(value: Any, field: str) -> pathlib.PurePosixPath:
    text = _string(value, field)
    path = pathlib.PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DossierError(f"{field} is not a confined relative path")
    return path


def _git_run(
    root: pathlib.Path,
    args: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(root), *args]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DossierError(f"cannot inspect Git with {args!r}: {exc}") from exc
    if check and completed.returncode != 0:
        raise DossierError(f"Git inspection failed for {args!r}: {completed.stderr.strip()}")
    return completed


def _git_run_bytes(
    root: pathlib.Path,
    args: Sequence[str],
) -> bytes:
    command = ["git", "-C", str(root), *args]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DossierError(f"cannot inspect Git with {args!r}: {exc}") from exc
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise DossierError(f"Git inspection failed for {args!r}: {error}")
    return completed.stdout


def _assert_head_bound_files(
    repo_root: pathlib.Path,
    files: Mapping[str, bytes],
    field: str,
) -> None:
    """Require every supplied worktree byte projection to be a regular HEAD blob."""

    object_format = _git_run(repo_root, ["rev-parse", "--show-object-format"]).stdout.strip()
    if object_format not in {"sha1", "sha256"}:
        raise DossierError(f"unsupported Git object format {object_format!r}")
    for relative, payload in sorted(files.items()):
        logical_path = _safe_relative(relative, f"{field} path")
        revision = f"HEAD:{logical_path.as_posix()}"
        resolved = _git_run(
            repo_root,
            ["rev-parse", "--verify", revision],
            check=False,
        )
        observed = resolved.stdout.strip()
        if resolved.returncode != 0 or _GIT_OID_RE.fullmatch(observed) is None:
            raise DossierError(
                f"{field} contains a file that is not a regular tracked HEAD blob: "
                f"{logical_path.as_posix()}"
            )
        digest = hashlib.new(object_format)
        digest.update(f"blob {len(payload)}\0".encode("ascii"))
        digest.update(payload)
        if digest.hexdigest() != observed:
            raise DossierError(f"{field} bytes do not match HEAD: {logical_path.as_posix()}")


def _expected_sdist_paths(repo_root: pathlib.Path) -> set[str]:
    raw = _git_run_bytes(
        repo_root,
        ["ls-tree", "-r", "-z", "--full-tree", "HEAD"],
    )
    expected: set[str] = set()
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, _object_id = metadata.decode("ascii").split(" ", 2)
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise DossierError("cannot parse the HEAD source manifest") from exc
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise DossierError(f"release source manifest contains a special entry: {path}")
        if (
            path == "copilot-codex-claude-bootstrap.sh"
            or path == "scripts/codex"
            or path.startswith("scripts/codex/")
            or path == "tmp"
            or path.startswith("tmp/")
        ):
            continue
        expected.add(path)
    if not expected:
        raise DossierError("release source manifest is empty")
    return expected


def _require_canonical_repo_evidence(
    supplied_path: pathlib.Path,
    repo_root: pathlib.Path,
    logical_path: str,
    field: str,
) -> None:
    canonical = _read_bytes(
        repo_root / logical_path,
        f"canonical {field}",
        maximum=MAX_JSON_BYTES,
    )
    _assert_head_bound_files(
        repo_root,
        {logical_path: canonical},
        f"canonical {field}",
    )
    supplied = _read_bytes(supplied_path, field, maximum=MAX_JSON_BYTES)
    if supplied != canonical:
        raise DossierError(f"{field} bytes differ from tracked {logical_path}")


def inspect_git_identity(repo_root: pathlib.Path, version: str) -> GitIdentity:
    root = repo_root.resolve()
    top = pathlib.Path(_git_run(root, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top != root:
        raise DossierError("repo_root must be the exact Git top-level directory")
    commit = _string(
        _git_run(root, ["rev-parse", "HEAD"]).stdout.strip(),
        "git commit",
        pattern=_GIT_OID_RE,
    )
    tree = _string(
        _git_run(root, ["rev-parse", "HEAD^{tree}"]).stdout.strip(),
        "git tree",
        pattern=_GIT_OID_RE,
    )
    branch = _git_run(root, ["branch", "--show-current"]).stdout.strip() or "DETACHED"
    status_text = _git_run(
        root,
        ["status", "--porcelain=v1", "--untracked-files=all"],
    ).stdout
    dirty_entries = tuple(sorted(line for line in status_text.splitlines() if line))
    diff_check = _git_run(root, ["diff", "--check"], check=False).returncode == 0

    exact_names = {version, f"v{version}"}
    points_at = {
        name
        for name in _git_run(root, ["tag", "--points-at", "HEAD"]).stdout.splitlines()
        if name in exact_names
    }
    if len(points_at) > 1:
        raise DossierError("multiple exact release tags point at HEAD")
    tag = next(iter(points_at), None)
    tag_object: str | None = None
    tag_type: str | None = None
    tag_target: str | None = None
    tag_message: str | None = None
    signature_verified = False
    if tag is not None:
        tag_object = _string(
            _git_run(root, ["rev-parse", f"refs/tags/{tag}"]).stdout.strip(),
            "tag object",
            pattern=_GIT_OID_RE,
        )
        tag_type = _git_run(root, ["cat-file", "-t", f"refs/tags/{tag}"]).stdout.strip()
        tag_target = _git_run(root, ["rev-list", "-n", "1", tag]).stdout.strip()
        tag_message = _git_run(
            root, ["for-each-ref", "--format=%(contents)", f"refs/tags/{tag}"]
        ).stdout
        signature_verified = _git_run(root, ["verify-tag", tag], check=False).returncode == 0
    return GitIdentity(
        commit=commit,
        tree=tree,
        branch=branch,
        dirty_entries=dirty_entries,
        diff_check_passed=diff_check,
        tag=tag,
        tag_object=tag_object,
        tag_object_type=tag_type,
        tag_target=tag_target,
        tag_message=tag_message,
        tag_signature_verified=signature_verified,
    )


def _project_identity(repo_root: pathlib.Path) -> dict[str, Any]:
    pyproject_path = repo_root / "pyproject.toml"
    payload = _read_bytes(pyproject_path, "pyproject.toml", maximum=2 * 1024 * 1024)
    try:
        parsed = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise DossierError(f"invalid pyproject.toml: {exc}") from exc
    project = _object(parsed.get("project"), "pyproject.project")
    name = _string(project.get("name"), "pyproject.project.name")
    version = _string(project.get("version"), "pyproject.project.version", pattern=_VERSION_RE)
    requires_python_raw = _string(
        project.get("requires-python"),
        "pyproject.project.requires-python",
    )
    try:
        requires_python = str(SpecifierSet(requires_python_raw))
    except InvalidSpecifier as exc:
        raise DossierError(f"invalid pyproject Requires-Python: {exc}") from exc
    raw_dependencies = _array(
        project.get("dependencies"),
        "pyproject.project.dependencies",
    )
    dependency_names: list[str] = []
    runtime_requirements: list[str] = []
    for index, raw_dependency in enumerate(raw_dependencies):
        dependency = _string(
            raw_dependency,
            f"pyproject.project.dependencies[{index}]",
        )
        match = _REQUIREMENT_NAME_RE.match(dependency)
        if match is None:
            raise DossierError(f"cannot identify dependency name in {dependency!r}")
        _requirement_identity(dependency, f"pyproject.project.dependencies[{index}]")
        dependency_names.append(_normalized_name(match.group(1)))
        runtime_requirements.append(dependency)
    if len(dependency_names) != len(set(dependency_names)):
        raise DossierError("project runtime dependency names must be unique")
    dependency_names.sort()

    optional_dependencies = _object(
        project.get("optional-dependencies", {}),
        "pyproject.project.optional-dependencies",
    )
    optional_dependency_names: dict[str, list[str]] = {}
    optional_requirements: dict[str, list[str]] = {}
    for extra, raw_requirements in sorted(optional_dependencies.items()):
        extra_name = _string(extra, "pyproject optional dependency group", pattern=_NAME_RE)
        requirements = _array(
            raw_requirements,
            f"pyproject.project.optional-dependencies.{extra_name}",
        )
        names: list[str] = []
        validated_requirements: list[str] = []
        for index, raw_requirement in enumerate(requirements):
            requirement = _string(
                raw_requirement,
                f"pyproject optional dependency {extra_name}[{index}]",
            )
            match = _REQUIREMENT_NAME_RE.match(requirement)
            if match is None:
                raise DossierError(f"cannot identify optional dependency in {requirement!r}")
            identity = _requirement_identity(
                requirement,
                f"pyproject optional dependency {extra_name}[{index}]",
            )
            if identity[-1] is not None:
                raise DossierError(
                    "optional project dependencies with environment markers are unsupported "
                    "by the release metadata verifier"
                )
            names.append(_normalized_name(match.group(1)))
            validated_requirements.append(requirement)
        if len(names) != len(set(names)):
            raise DossierError(f"optional dependency names are duplicated for {extra_name}")
        optional_dependency_names[extra_name] = sorted(names)
        optional_requirements[extra_name] = validated_requirements

    raw_scripts = _object(project.get("scripts", {}), "pyproject.project.scripts")
    project_scripts = {
        _string(key, "pyproject script name"): _string(
            value,
            f"pyproject.project.scripts.{key}",
        )
        for key, value in sorted(raw_scripts.items())
    }

    urls = _object(project.get("urls"), "pyproject.project.urls")
    repository_url = _string(urls.get("Repository"), "pyproject.project.urls.Repository")
    parsed_repository = urllib.parse.urlsplit(repository_url)
    repository_parts = [part for part in parsed_repository.path.split("/") if part]
    if (
        parsed_repository.scheme != "https"
        or parsed_repository.hostname != "github.com"
        or parsed_repository.username is not None
        or parsed_repository.password is not None
        or parsed_repository.port is not None
        or parsed_repository.query
        or parsed_repository.fragment
        or len(repository_parts) != 2
        or any(_NAME_RE.fullmatch(part.lower()) is None for part in repository_parts)
    ):
        raise DossierError("project Repository URL must name one canonical GitHub repository")
    github_repository = "/".join(repository_parts)

    init_payload = _read_bytes(
        repo_root / PACKAGE_DIRECTORY / "__init__.py",
        "package __init__.py",
        maximum=1024 * 1024,
    )
    try:
        tree = ast.parse(init_payload.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise DossierError(f"cannot parse package version: {exc}") from exc
    init_versions: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                init_versions.append(node.value.value)
    if len(init_versions) != 1:
        raise DossierError("package __init__.py must declare __version__ exactly once")

    changelog = _read_bytes(
        repo_root / "CHANGELOG.md",
        "CHANGELOG.md",
        maximum=8 * 1024 * 1024,
    ).decode("utf-8")
    released_heading = re.search(
        rf"(?m)^## \[{re.escape(version)}\]\s+(?:—|-|–)\s+[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}\s*$",
        changelog,
    )
    unreleased_candidate = re.search(
        rf"(?mi)^## \[Unreleased\].*\b{re.escape(version)}\b",
        changelog,
    )
    readme = _read_bytes(repo_root / "README.md", "README.md", maximum=16 * 1024 * 1024).decode(
        "utf-8"
    )
    citation_versions = re.findall(r"(?m)^\s*version\s*=\s*\{([^}]+)\}\s*$", readme)
    return {
        "name": name,
        "version": version,
        "requires_python": requires_python,
        "github_repository": github_repository,
        "runtime_dependencies": dependency_names,
        "runtime_requirements": runtime_requirements,
        "optional_dependencies": optional_dependency_names,
        "optional_requirements": optional_requirements,
        "console_scripts": project_scripts,
        "package_version": init_versions[0],
        "changelog_released": released_heading is not None,
        "changelog_unreleased_candidate": unreleased_candidate is not None,
        "readme_citation_versions": citation_versions,
        "version_parity": (
            name == PROJECT_NAME and init_versions[0] == version and citation_versions == [version]
        ),
    }


def _archive_name(name: str, field: str) -> pathlib.PurePosixPath:
    path = pathlib.PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise DossierError(f"{field} contains an unsafe archive member {name!r}")
    return path


def _expected_package_files(repo_root: pathlib.Path) -> dict[str, bytes]:
    package_root = repo_root / PACKAGE_DIRECTORY
    if package_root.is_symlink() or not package_root.is_dir():
        raise DossierError("package directory is absent or a symlink")
    result: dict[str, bytes] = {}
    for path in sorted(package_root.rglob("*")):
        if path.is_symlink():
            raise DossierError(f"package source contains a symlink: {path}")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(repo_root).as_posix()
        result[relative] = _read_bytes(
            path,
            relative,
            maximum=MAX_ARCHIVE_MEMBER_BYTES,
            minimum=0,
        )
    if not result:
        raise DossierError("package source projection is empty")
    _assert_head_bound_files(repo_root, result, "package source projection")
    return result


def _authoritative_license_policy(
    repo_root: pathlib.Path,
) -> tuple[FileIdentity, dict[str, Any]]:
    relative = "supply-chain/license-policy.toml"
    payload = _read_bytes(
        repo_root / relative,
        "authoritative license policy",
        maximum=2 * 1024 * 1024,
    )
    _assert_head_bound_files(
        repo_root,
        {relative: payload},
        "authoritative license policy",
    )
    try:
        policy = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise DossierError(f"invalid authoritative license policy: {exc}") from exc
    policy_name = _string(policy.get("policy_name"), "license policy.policy_name")
    policy_version = _string(policy.get("policy_version"), "license policy.policy_version")
    legal_review_complete = _boolean(
        policy.get("legal_review_complete"),
        "license policy.legal_review_complete",
    )
    if legal_review_complete:
        raise DossierError("automated license policy cannot claim completed legal review")
    identity = FileIdentity("license-policy", len(payload), _sha256(payload))
    return identity, {
        "logical_path": relative,
        "policy_name": policy_name,
        "policy_version": policy_version,
        "legal_review_complete": legal_review_complete,
        "passed": True,
    }


def _metadata_identity(payload: bytes, field: str) -> tuple[str, str]:
    try:
        message = BytesParser().parsebytes(payload)
    except (TypeError, ValueError) as exc:
        raise DossierError(f"invalid package metadata in {field}: {exc}") from exc
    name = message.get("Name")
    version = message.get("Version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise DossierError(f"{field} lacks Name or Version metadata")
    return name, version


def _metadata_requires_python(payload: bytes, field: str) -> str:
    try:
        message = BytesParser().parsebytes(payload)
    except (TypeError, ValueError) as exc:
        raise DossierError(f"invalid package metadata in {field}: {exc}") from exc
    requires_python = _string(message.get("Requires-Python"), f"{field} Requires-Python")
    try:
        return str(SpecifierSet(requires_python))
    except InvalidSpecifier as exc:
        raise DossierError(f"invalid Requires-Python in {field}: {exc}") from exc


def _validate_wheel_record(files: Mapping[str, bytes], record_name: str) -> None:
    try:
        rows = list(csv.reader(io.StringIO(files[record_name].decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DossierError(f"invalid wheel RECORD: {exc}") from exc
    by_name: dict[str, tuple[str, str]] = {}
    for row in rows:
        if len(row) != 3:
            raise DossierError("wheel RECORD rows must have exactly three fields")
        name, digest, size = row
        _archive_name(name, "wheel RECORD")
        if name in by_name:
            raise DossierError("wheel RECORD contains duplicate paths")
        by_name[name] = (digest, size)
    if set(by_name) != set(files):
        raise DossierError("wheel RECORD member set does not match the archive")
    for name, payload in files.items():
        digest, size = by_name[name]
        if name == record_name:
            if digest or size:
                raise DossierError("wheel RECORD must leave its own digest and size empty")
            continue
        encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        if digest != f"sha256={encoded}" or size != str(len(payload)):
            raise DossierError(f"wheel RECORD identity drifted for {name}")


def _inspect_wheel(
    path: pathlib.Path,
    repo_root: pathlib.Path,
    project: Mapping[str, Any],
) -> tuple[FileIdentity, dict[str, Any]]:
    payload = _read_bytes(path, "wheel", maximum=MAX_ARCHIVE_BYTES)
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, OSError) as exc:
        raise DossierError(f"invalid wheel archive: {exc}") from exc
    files: dict[str, bytes] = {}
    total = 0
    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ARCHIVE_MEMBERS:
            raise DossierError("wheel member count is outside the safety bound")
        for info in infos:
            member = _archive_name(info.filename, "wheel")
            name = member.as_posix()
            if name in files:
                raise DossierError("wheel contains duplicate members")
            if info.flag_bits & 0x1:
                raise DossierError("wheel contains an encrypted member")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise DossierError("wheel contains a symlink")
            if info.is_dir():
                continue
            if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise DossierError("wheel member exceeds the byte bound")
            total += info.file_size
            if total > MAX_ARCHIVE_TOTAL_BYTES:
                raise DossierError("wheel uncompressed bytes exceed the bound")
            files[name] = archive.read(info)
    metadata_names = [name for name in files if name.endswith(".dist-info/METADATA")]
    record_names = [name for name in files if name.endswith(".dist-info/RECORD")]
    if len(metadata_names) != 1 or len(record_names) != 1:
        raise DossierError("wheel must contain exactly one METADATA and RECORD")
    package_name, version = _metadata_identity(files[metadata_names[0]], "wheel METADATA")
    requires_python = _metadata_requires_python(files[metadata_names[0]], "wheel METADATA")
    requires_python_matches = requires_python == project["requires_python"]
    if not requires_python_matches:
        raise DossierError("wheel Requires-Python differs from pyproject.toml")
    canonical_distribution = re.sub(r"[-_.]+", "_", package_name)
    canonical_version = version.replace("-", "_")
    expected_dist_info = f"{canonical_distribution}-{canonical_version}.dist-info"
    metadata_root = metadata_names[0].rsplit("/", 1)[0]
    record_root = record_names[0].rsplit("/", 1)[0]
    if metadata_root != expected_dist_info or record_root != expected_dist_info:
        raise DossierError("wheel metadata directories are noncanonical or inconsistent")
    expected_filename = f"{canonical_distribution}-{canonical_version}-py3-none-any.whl"
    if path.name != expected_filename:
        raise DossierError(f"wheel filename must be {expected_filename!r}")
    unexpected = sorted(
        name
        for name in files
        if not name.startswith(f"{PACKAGE_DIRECTORY}/")
        and not name.startswith(f"{expected_dist_info}/")
    )
    if unexpected:
        raise DossierError(f"wheel contains unexpected installable payloads: {unexpected}")
    dist_info_members = {
        name[len(expected_dist_info) + 1 :]
        for name in files
        if name.startswith(f"{expected_dist_info}/")
    }
    expected_dist_info_members = {
        "METADATA",
        "RECORD",
        "WHEEL",
        "licenses/LICENSE",
    }
    project_scripts = _object(project["console_scripts"], "project console scripts")
    if project_scripts:
        expected_dist_info_members.add("entry_points.txt")
    if dist_info_members != expected_dist_info_members:
        raise DossierError(
            "wheel dist-info member set drifted: "
            f"expected={sorted(expected_dist_info_members)}, "
            f"observed={sorted(dist_info_members)}"
        )

    license_payload = _read_bytes(
        repo_root / "LICENSE",
        "repository LICENSE",
        maximum=MAX_ARCHIVE_MEMBER_BYTES,
    )
    _assert_head_bound_files(repo_root, {"LICENSE": license_payload}, "repository license")
    if files[f"{expected_dist_info}/licenses/LICENSE"] != license_payload:
        raise DossierError("wheel license bytes differ from the repository LICENSE")

    wheel_message = BytesParser().parsebytes(files[f"{expected_dist_info}/WHEEL"])
    wheel_contract_matches = wheel_message.get(
        "Root-Is-Purelib"
    ) == "true" and wheel_message.get_all("Tag", []) == ["py3-none-any"]
    if not wheel_contract_matches:
        raise DossierError("wheel must be a pure Python py3-none-any artifact")

    entry_points_match = True
    if project_scripts:
        expected_entry_points = (
            "[console_scripts]\n"
            + "".join(f"{name} = {target}\n" for name, target in sorted(project_scripts.items()))
        ).encode("utf-8")
        entry_points_match = (
            files[f"{expected_dist_info}/entry_points.txt"] == expected_entry_points
        )
        if not entry_points_match:
            raise DossierError("wheel entry points differ from pyproject.toml")

    metadata_message = BytesParser().parsebytes(files[metadata_names[0]])
    runtime_requirement_contracts: set[tuple[str, tuple[str, ...], str, str | None, str | None]] = (
        set()
    )
    optional_requirement_contracts: dict[
        str,
        set[tuple[str, tuple[str, ...], str, str | None, str | None]],
    ] = {}
    for index, requirement in enumerate(metadata_message.get_all("Requires-Dist", [])):
        requirement_text = _string(requirement, f"wheel Requires-Dist[{index}]")
        requirement_parts = requirement_text.split(";", 1)
        extra_match = (
            _EXTRA_ONLY_MARKER_RE.fullmatch(requirement_parts[1])
            if len(requirement_parts) == 2
            else None
        )
        if extra_match is None:
            identity = _requirement_identity(
                requirement_text,
                f"wheel Requires-Dist[{index}]",
            )
            if identity in runtime_requirement_contracts:
                raise DossierError("wheel metadata duplicates a runtime dependency")
            runtime_requirement_contracts.add(identity)
        else:
            extra = extra_match.group(1)
            identity = _requirement_identity(
                requirement_parts[0].strip(),
                f"wheel optional Requires-Dist[{index}]",
            )
            group = optional_requirement_contracts.setdefault(extra, set())
            if identity in group:
                raise DossierError("wheel metadata duplicates an optional dependency")
            group.add(identity)
    declared_runtime_contracts = {
        _requirement_identity(value, f"project runtime requirement {index}")
        for index, value in enumerate(
            _array(project["runtime_requirements"], "project runtime requirements")
        )
    }
    declared_optional_contracts = {
        key: {
            _requirement_identity(value, f"project optional requirement {key}[{index}]")
            for index, value in enumerate(
                _array(raw_values, f"project optional requirements {key}")
            )
        }
        for key, raw_values in _object(
            project["optional_requirements"],
            "project optional requirements",
        ).items()
    }
    provided_extras = metadata_message.get_all("Provides-Extra", [])
    metadata_dependencies_match = (
        runtime_requirement_contracts == declared_runtime_contracts
        and optional_requirement_contracts == declared_optional_contracts
        and sorted(provided_extras) == sorted(declared_optional_contracts)
    )
    if not metadata_dependencies_match:
        raise DossierError("wheel dependency metadata differs from pyproject.toml")
    _validate_wheel_record(files, record_names[0])
    expected = _expected_package_files(repo_root)
    package_files = {
        name: content for name, content in files.items() if name.startswith(f"{PACKAGE_DIRECTORY}/")
    }
    if set(package_files) != set(expected):
        raise DossierError("wheel package member set does not match the source tree")
    mismatched = [name for name in expected if package_files[name] != expected[name]]
    if mismatched:
        raise DossierError(f"wheel package bytes differ from source: {mismatched}")
    projection = [
        {"path": name, "bytes": len(content), "sha256": _sha256(content)}
        for name, content in sorted(package_files.items())
    ]
    return (
        FileIdentity("wheel", len(payload), _sha256(payload)),
        {
            "filename": path.name,
            "name": package_name,
            "version": version,
            "requires_python": requires_python,
            "requires_python_matches": requires_python_matches,
            "metadata_sha256": _sha256(files[metadata_names[0]]),
            "member_count": len(files),
            "dist_info_member_count": len(dist_info_members),
            "entry_points_match": entry_points_match,
            "metadata_dependencies_match": metadata_dependencies_match,
            "wheel_contract_matches": wheel_contract_matches,
            "package_source_projection_sha256": _sha256(
                _canonical_json_bytes(projection, indent=None)
            ),
            "project_identity_matches": (
                _normalized_name(package_name) == _normalized_name(str(project["name"]))
                and version == project["version"]
            ),
        },
    )


def _inspect_sdist(
    path: pathlib.Path,
    repo_root: pathlib.Path,
    project: Mapping[str, Any],
) -> tuple[FileIdentity, dict[str, Any]]:
    payload = _read_bytes(path, "sdist", maximum=MAX_ARCHIVE_BYTES)
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise DossierError(f"invalid sdist archive: {exc}") from exc
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    total = 0
    with archive:
        members = archive.getmembers()
        if not members or len(members) > MAX_ARCHIVE_MEMBERS:
            raise DossierError("sdist member count is outside the safety bound")
        for info in members:
            member = _archive_name(info.name, "sdist")
            roots.add(member.parts[0])
            if info.isdir():
                continue
            if not info.isfile():
                raise DossierError("sdist contains a link or special member")
            if info.size > MAX_ARCHIVE_MEMBER_BYTES:
                raise DossierError("sdist member exceeds the byte bound")
            total += info.size
            if total > MAX_ARCHIVE_TOTAL_BYTES:
                raise DossierError("sdist uncompressed bytes exceed the bound")
            extracted = archive.extractfile(info)
            if extracted is None:
                raise DossierError("cannot read a regular sdist member")
            name = member.as_posix()
            if name in files:
                raise DossierError("sdist contains duplicate members")
            files[name] = extracted.read()
    if len(roots) != 1:
        raise DossierError("sdist must contain one top-level directory")
    root_name = next(iter(roots))
    canonical_distribution = re.sub(r"[-_.]+", "_", str(project["name"]))
    canonical_version = str(project["version"]).replace("-", "_")
    expected_root = f"{canonical_distribution}-{canonical_version}"
    expected_filename = f"{expected_root}.tar.gz"
    if root_name != expected_root or path.name != expected_filename:
        raise DossierError(
            f"sdist root and filename must be {expected_root!r} and {expected_filename!r}"
        )
    prefix = f"{root_name}/"
    metadata_name = f"{root_name}/PKG-INFO"
    if metadata_name not in files:
        raise DossierError("sdist lacks PKG-INFO")
    package_name, version = _metadata_identity(files[metadata_name], "sdist PKG-INFO")
    requires_python = _metadata_requires_python(files[metadata_name], "sdist PKG-INFO")
    requires_python_matches = requires_python == project["requires_python"]
    if not requires_python_matches:
        raise DossierError("sdist Requires-Python differs from pyproject.toml")
    expected_package = _expected_package_files(repo_root)
    critical = {relative: content for relative, content in expected_package.items()}
    for relative in (
        "pyproject.toml",
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "supply-chain/license-policy.toml",
        "scripts/build_release_dossier.py",
        "docs/RELEASE_DOSSIER.md",
    ):
        source = repo_root / relative
        if source.is_file() and not source.is_symlink():
            critical[relative] = _read_bytes(
                source,
                f"source {relative}",
                maximum=MAX_ARCHIVE_MEMBER_BYTES,
                minimum=0,
            )
    missing = [relative for relative in critical if f"{prefix}{relative}" not in files]
    if missing:
        raise DossierError(f"sdist omits release-critical source files: {missing}")
    mismatched = [
        relative
        for relative, content in critical.items()
        if files[f"{prefix}{relative}"] != content
    ]
    if mismatched:
        raise DossierError(f"sdist source bytes differ from the worktree: {mismatched}")
    complete_source: dict[str, bytes] = {}
    for archive_path, content in sorted(files.items()):
        if not archive_path.startswith(prefix):
            raise DossierError("sdist file lies outside its top-level directory")
        relative = archive_path[len(prefix) :]
        if relative == "PKG-INFO":
            continue
        logical_path = _archive_name(relative, "sdist source projection")
        source = repo_root.joinpath(*logical_path.parts)
        if source.is_symlink() or not source.is_file():
            raise DossierError(f"sdist contains a file absent from the source tree: {relative}")
        source_payload = _read_bytes(
            source,
            f"sdist source {relative}",
            maximum=MAX_ARCHIVE_MEMBER_BYTES,
            minimum=0,
        )
        if source_payload != content:
            raise DossierError(f"sdist source bytes differ from the worktree: {relative}")
        complete_source[relative] = content
    _assert_head_bound_files(
        repo_root,
        complete_source,
        "complete sdist source projection",
    )
    expected_source_paths = _expected_sdist_paths(repo_root)
    if set(complete_source) != expected_source_paths:
        missing_source = sorted(expected_source_paths - set(complete_source))
        unexpected_source = sorted(set(complete_source) - expected_source_paths)
        raise DossierError(
            "sdist source manifest differs from the committed packaging projection: "
            f"missing={missing_source}, unexpected={unexpected_source}"
        )
    projection = [
        {"path": relative, "bytes": len(content), "sha256": _sha256(content)}
        for relative, content in sorted(critical.items())
    ]
    return (
        FileIdentity("sdist", len(payload), _sha256(payload)),
        {
            "filename": path.name,
            "archive_root": root_name,
            "name": package_name,
            "version": version,
            "requires_python": requires_python,
            "requires_python_matches": requires_python_matches,
            "metadata_sha256": _sha256(files[metadata_name]),
            "member_count": len(files),
            "source_file_count": len(complete_source),
            "critical_source_projection_sha256": _sha256(
                _canonical_json_bytes(projection, indent=None)
            ),
            "complete_source_projection_sha256": _sha256(
                _canonical_json_bytes(
                    [
                        {"path": name, "bytes": len(content), "sha256": _sha256(content)}
                        for name, content in sorted(complete_source.items())
                    ],
                    indent=None,
                )
            ),
            "project_identity_matches": (
                _normalized_name(package_name) == _normalized_name(str(project["name"]))
                and version == project["version"]
            ),
        },
    )


def _validate_artifact_report(
    path: pathlib.Path,
    wheel: FileIdentity,
    sdist: FileIdentity,
    authoritative_policy: FileIdentity,
    wheel_name: str,
    sdist_name: str,
) -> tuple[FileIdentity, dict[str, Any]]:
    decoded, payload = _read_json(path, "artifact audit report")
    report = _object(decoded, "artifact audit report")
    _exact_fields(
        report,
        {"artifacts", "automation_result", "custom_findings", "detect_secrets", "policy_sha256"},
        "artifact audit report",
    )
    raw_artifacts = _array(report["artifacts"], "artifact audit report.artifacts")
    by_name: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_artifacts):
        item = _object(raw, f"artifact audit report.artifacts[{index}]")
        _exact_fields(
            item,
            {"members", "name", "sha256", "uncompressed_regular_bytes"},
            f"artifact audit report.artifacts[{index}]",
        )
        name = _string(item["name"], f"artifact[{index}].name")
        if name in by_name:
            raise DossierError("artifact report contains duplicate artifact names")
        _string(item["sha256"], f"artifact[{index}].sha256", pattern=_SHA256_RE)
        _integer(item["members"], f"artifact[{index}].members", minimum=1)
        _integer(
            item["uncompressed_regular_bytes"],
            f"artifact[{index}].uncompressed_regular_bytes",
            minimum=1,
        )
        by_name[name] = item
    expected = {wheel_name: wheel.sha256, sdist_name: sdist.sha256}
    artifact_identities_match = set(by_name) == set(expected) and all(
        by_name[name]["sha256"] == digest for name, digest in expected.items()
    )
    custom_findings = _array(report["custom_findings"], "artifact report.custom_findings")
    detect = _object(report["detect_secrets"], "artifact report.detect_secrets")
    _exact_fields(
        detect,
        {"declared_provenance_hashes", "findings", "network_verification", "version"},
        "artifact report.detect_secrets",
    )
    findings = _array(detect["findings"], "artifact report.detect_secrets.findings")
    declared = _array(
        detect["declared_provenance_hashes"],
        "artifact report.detect_secrets.declared_provenance_hashes",
    )
    policy_sha256 = _string(
        report["policy_sha256"], "artifact report.policy_sha256", pattern=_SHA256_RE
    )
    policy_matches_authoritative = policy_sha256 == authoritative_policy.sha256
    return (
        FileIdentity("artifact-audit-report", len(payload), _sha256(payload)),
        {
            "automation_result": report["automation_result"],
            "artifact_identities_match": artifact_identities_match,
            "custom_finding_count": len(custom_findings),
            "secret_finding_count": len(findings),
            "declared_provenance_count": len(declared),
            "policy_sha256": policy_sha256,
            "policy_matches_authoritative": policy_matches_authoritative,
            "passed": (
                report["automation_result"] == "pass"
                and artifact_identities_match
                and not custom_findings
                and not findings
                and policy_matches_authoritative
            ),
        },
    )


def _validate_sbom(
    path: pathlib.Path,
    project: Mapping[str, Any],
) -> tuple[FileIdentity, dict[str, Any], set[tuple[str, str]]]:
    decoded, payload = _read_json(path, "CycloneDX SBOM")
    sbom = _object(decoded, "CycloneDX SBOM")
    metadata = _object(sbom.get("metadata"), "SBOM.metadata")
    component = _object(metadata.get("component"), "SBOM.metadata.component")
    components = _array(sbom.get("components"), "SBOM.components")
    dependencies = _array(sbom.get("dependencies"), "SBOM.dependencies")
    root_name = _string(component.get("name"), "SBOM.metadata.component.name")
    root_version = _string(component.get("version"), "SBOM.metadata.component.version")
    root_matches = (
        _normalized_name(root_name) == _normalized_name(str(project["name"]))
        and root_version == project["version"]
    )
    package_identities = {(_normalized_name(root_name), root_version)}
    component_identities: set[tuple[str, str]] = set()
    for index, raw in enumerate(components):
        item = _object(raw, f"SBOM.components[{index}]")
        name = _string(item.get("name"), f"SBOM.components[{index}].name")
        version = _string(item.get("version"), f"SBOM.components[{index}].version")
        identity = (_normalized_name(name), version)
        if identity in component_identities:
            raise DossierError("SBOM contains duplicate component identities")
        component_identities.add(identity)
        package_identities.add(identity)
    required_names = set(_array(project["runtime_dependencies"], "project dependencies"))
    runtime_requirements = _array(
        project["runtime_requirements"],
        "project runtime requirements",
    )
    observed_names = {name for name, _version in package_identities}
    direct_dependencies_present = required_names <= observed_names
    runtime_requirement_versions_match = _runtime_requirement_versions_match(
        runtime_requirements,
        package_identities,
    )
    passed = (
        sbom.get("bomFormat") == "CycloneDX"
        and sbom.get("specVersion") == "1.6"
        and isinstance(sbom.get("version"), int)
        and not isinstance(sbom.get("version"), bool)
        and root_matches
        and bool(components)
        and bool(dependencies)
        and direct_dependencies_present
        and runtime_requirement_versions_match
    )
    return (
        FileIdentity("cyclonedx-sbom", len(payload), _sha256(payload)),
        {
            "bom_format": sbom.get("bomFormat"),
            "spec_version": sbom.get("specVersion"),
            "component_count": len(components),
            "dependency_count": len(dependencies),
            "package_count": len(package_identities),
            "package_set_sha256": _package_set_sha256(package_identities),
            "root_component_matches": root_matches,
            "direct_dependencies_present": direct_dependencies_present,
            "runtime_requirement_versions_match": runtime_requirement_versions_match,
            "passed": passed,
        },
        package_identities,
    )


def _validate_license_inventory(
    path: pathlib.Path,
    project: Mapping[str, Any],
) -> tuple[FileIdentity, dict[str, Any], set[tuple[str, str]]]:
    decoded, payload = _read_json(path, "license inventory")
    entries = _array(decoded, "license inventory")
    identities: set[tuple[str, str]] = set()
    root_matches = False
    for index, raw in enumerate(entries):
        item = _object(raw, f"license inventory[{index}]")
        name = _string(item.get("Name"), f"license inventory[{index}].Name")
        version = _string(item.get("Version"), f"license inventory[{index}].Version")
        identity = (_normalized_name(name), version)
        if identity in identities:
            raise DossierError("license inventory contains duplicate name/version identities")
        identities.add(identity)
        license_text = item.get("LicenseText")
        if not isinstance(license_text, str) or not license_text.strip():
            raise DossierError("license inventory contains an empty license text")
        if identity == (_normalized_name(str(project["name"])), str(project["version"])):
            root_matches = True
    required_names = set(_array(project["runtime_dependencies"], "project dependencies"))
    runtime_requirements = _array(
        project["runtime_requirements"],
        "project runtime requirements",
    )
    observed_names = {name for name, _version in identities}
    direct_dependencies_present = required_names <= observed_names
    runtime_requirement_versions_match = _runtime_requirement_versions_match(
        runtime_requirements,
        identities,
    )
    return (
        FileIdentity("python-license-inventory", len(payload), _sha256(payload)),
        {
            "package_count": len(entries),
            "package_set_sha256": _package_set_sha256(identities),
            "root_package_matches": root_matches,
            "direct_dependencies_present": direct_dependencies_present,
            "runtime_requirement_versions_match": runtime_requirement_versions_match,
            "passed": (
                bool(entries)
                and root_matches
                and direct_dependencies_present
                and runtime_requirement_versions_match
            ),
        },
        identities,
    )


def _validate_license_report(
    path: pathlib.Path,
    *,
    sbom: FileIdentity,
    sbom_packages: set[tuple[str, str]],
    inventory: FileIdentity,
    inventory_packages: set[tuple[str, str]],
    required_dependency_names: set[str],
    runtime_requirements: Sequence[str],
    artifact_policy_sha256: str,
    authoritative_policy: FileIdentity,
    authoritative_policy_summary: Mapping[str, Any],
) -> tuple[FileIdentity, dict[str, Any]]:
    decoded, payload = _read_json(path, "license policy report")
    report = _object(decoded, "license policy report")
    _exact_fields(
        report,
        {
            "automation_result",
            "legal_review_complete",
            "limitations",
            "packages",
            "policy",
            "sbom_coverage_errors",
            "scope_profiles",
            "source_artifacts",
            "summary",
        },
        "license policy report",
    )
    summary = _object(report["summary"], "license report.summary")
    _exact_fields(summary, {"allow", "deny", "review", "total"}, "license report.summary")
    allow = _integer(summary["allow"], "license report.summary.allow")
    deny = _integer(summary["deny"], "license report.summary.deny")
    review = _integer(summary["review"], "license report.summary.review")
    total = _integer(summary["total"], "license report.summary.total", minimum=1)
    packages = _array(report["packages"], "license report.packages")
    report_packages: set[tuple[str, str]] = set()
    observed_decisions = {"allow": 0, "deny": 0, "review": 0}
    for index, raw in enumerate(packages):
        package = _object(raw, f"license report.packages[{index}]")
        name = _string(package.get("name"), f"license report.packages[{index}].name")
        version = _string(
            package.get("version"),
            f"license report.packages[{index}].version",
        )
        decision = _string(
            package.get("decision"),
            f"license report.packages[{index}].decision",
        )
        if decision not in observed_decisions:
            raise DossierError("license report contains an unknown package decision")
        identity = (_normalized_name(name), version)
        if identity in report_packages:
            raise DossierError("license report contains duplicate package identities")
        report_packages.add(identity)
        observed_decisions[decision] += 1
    counts_match = (
        observed_decisions["allow"] == allow
        and observed_decisions["deny"] == deny
        and observed_decisions["review"] == review
        and len(report_packages) == total
    )
    package_sets_match = report_packages == inventory_packages == sbom_packages
    direct_dependencies_present = required_dependency_names <= {
        name for name, _version in report_packages
    }
    runtime_requirement_versions_match = _runtime_requirement_versions_match(
        runtime_requirements,
        report_packages,
    )
    source = _object(report["source_artifacts"], "license report.source_artifacts")
    _exact_fields(source, {"inventory_sha256", "sbom_sha256"}, "license report.source_artifacts")
    source_matches = (
        source["inventory_sha256"] == inventory.sha256 and source["sbom_sha256"] == sbom.sha256
    )
    policy = _object(report["policy"], "license report.policy")
    _exact_fields(policy, {"name", "sha256", "version"}, "license report.policy")
    policy_name = _string(policy["name"], "license report.policy.name")
    policy_version = _string(policy["version"], "license report.policy.version")
    policy_sha256 = _string(policy["sha256"], "license report.policy.sha256", pattern=_SHA256_RE)
    coverage_errors = _array(report["sbom_coverage_errors"], "license report.sbom_coverage_errors")
    limitations = _array(report["limitations"], "license report.limitations")
    if not limitations or any(
        not isinstance(item, str) or not item.strip() for item in limitations
    ):
        raise DossierError("license report limitations must be a non-empty string array")
    scope_profiles = _array(report["scope_profiles"], "license report.scope_profiles")
    scopes_match = scope_profiles == ["default", "structural"]
    legal_review_complete = _boolean(
        report["legal_review_complete"],
        "license report.legal_review_complete",
    )
    automation_scope_honest = not legal_review_complete
    policy_matches_authoritative = policy_sha256 == authoritative_policy.sha256
    policy_identity_matches = (
        policy_name == authoritative_policy_summary["policy_name"]
        and policy_version == authoritative_policy_summary["policy_version"]
    )
    automation_passed = (
        report["automation_result"] == "pass"
        and deny == 0
        and review == 0
        and allow == total == len(packages)
        and counts_match
        and package_sets_match
        and direct_dependencies_present
        and runtime_requirement_versions_match
        and not coverage_errors
        and scopes_match
        and source_matches
        and policy_sha256 == artifact_policy_sha256
        and policy_matches_authoritative
        and policy_identity_matches
        and automation_scope_honest
    )
    return (
        FileIdentity("license-policy-report", len(payload), _sha256(payload)),
        {
            "automation_result": report["automation_result"],
            "summary": {"allow": allow, "deny": deny, "review": review, "total": total},
            "summary_matches_packages": counts_match,
            "package_set_sha256": _package_set_sha256(report_packages),
            "package_sets_match": package_sets_match,
            "direct_dependencies_present": direct_dependencies_present,
            "runtime_requirement_versions_match": runtime_requirement_versions_match,
            "scope_profiles_match": scopes_match,
            "source_artifacts_match": source_matches,
            "policy_sha256": policy_sha256,
            "policy_matches_artifact_audit": policy_sha256 == artifact_policy_sha256,
            "policy_matches_authoritative": policy_matches_authoritative,
            "policy_identity_matches": policy_identity_matches,
            "legal_review_complete": legal_review_complete,
            "automation_scope_honest": automation_scope_honest,
            "automation_passed": automation_passed,
            "passed": automation_passed,
        },
    )


def _validate_platform(value: Any, field: str) -> dict[str, str]:
    platform = _object(value, field)
    _exact_fields(platform, {"architecture", "os", "python_version"}, field)
    return {
        "os": _string(platform["os"], f"{field}.os"),
        "architecture": _string(platform["architecture"], f"{field}.architecture"),
        "python_version": _string(platform["python_version"], f"{field}.python_version"),
    }


def _validate_gate_summary(kind: str, value: Any) -> tuple[dict[str, Any], bool]:
    summary = _object(value, f"{kind} evidence.result.summary")
    if kind == "test":
        _exact_fields(
            summary,
            {"collected", "errors", "failed", "passed", "skipped"},
            "test evidence.result.summary",
        )
        collected = _integer(summary["collected"], "test summary.collected", minimum=1)
        passed = _integer(summary["passed"], "test summary.passed")
        failed = _integer(summary["failed"], "test summary.failed")
        errors = _integer(summary["errors"], "test summary.errors")
        skipped = _integer(summary["skipped"], "test summary.skipped")
        return dict(summary), failed == 0 and errors == 0 and passed + skipped == collected
    if kind == "coverage":
        _exact_fields(
            summary,
            {"measured_files", "minimum_percent", "percent"},
            "coverage evidence.result.summary",
        )
        measured = _integer(summary["measured_files"], "coverage summary.measured_files", minimum=1)
        percent = summary["percent"]
        minimum = summary["minimum_percent"]
        if (
            isinstance(percent, bool)
            or not isinstance(percent, (int, float))
            or isinstance(minimum, bool)
            or not isinstance(minimum, (int, float))
            or not 0 <= float(percent) <= 100
            or not 0 <= float(minimum) <= 100
        ):
            raise DossierError("coverage percentages must be finite values in [0, 100]")
        return (
            dict(summary),
            measured > 0
            and float(minimum) >= MIN_COVERAGE_PERCENT
            and float(percent) >= float(minimum),
        )
    if kind in {"lint", "type"}:
        required = {"checked_files", "errors", "tool"}
        _exact_fields(summary, required, f"{kind} evidence.result.summary")
        checked = _integer(summary["checked_files"], f"{kind} summary.checked_files", minimum=1)
        errors = _integer(summary["errors"], f"{kind} summary.errors")
        tool = _string(summary["tool"], f"{kind} summary.tool")
        expected_tool = "ruff" if kind == "lint" else "mypy"
        return dict(summary), checked > 0 and errors == 0 and tool == expected_tool
    raise DossierError(f"unsupported gate evidence kind {kind!r}")


def _gate_command_matches(kind: str, command: Sequence[str]) -> bool:
    pytest_command = (
        "pytest",
        "tests/",
        "-q",
        "--tb=short",
        "--cov=bench_cleanser",
        "--cov-report=term",
        "--cov-fail-under=70",
    )
    expected = {
        "test": pytest_command,
        "coverage": pytest_command,
        "lint": ("ruff", "check", "."),
        "type": ("mypy", "bench_cleanser"),
    }
    return tuple(command) == expected.get(kind)


def _validate_gate_evidence(
    path: pathlib.Path,
    kind: str,
    git: GitIdentity,
) -> tuple[list[FileIdentity], dict[str, Any]]:
    decoded, payload = _read_json(path, f"{kind} gate evidence")
    evidence = _object(decoded, f"{kind} gate evidence")
    _exact_fields(
        evidence,
        {
            "command",
            "completed_at",
            "kind",
            "log",
            "platform",
            "result",
            "schema_version",
            "source",
            "started_at",
        },
        f"{kind} gate evidence",
    )
    if evidence["schema_version"] != GATE_EVIDENCE_SCHEMA_VERSION or evidence["kind"] != kind:
        raise DossierError(f"{kind} gate evidence schema/kind drifted")
    source = _object(evidence["source"], f"{kind} evidence.source")
    _exact_fields(source, {"commit", "tree"}, f"{kind} evidence.source")
    source_current = source["commit"] == git.commit and source["tree"] == git.tree
    command = _array(evidence["command"], f"{kind} evidence.command")
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise DossierError(f"{kind} evidence.command must be a non-empty argv array")
    command_policy_passed = _gate_command_matches(kind, command)
    platform = _validate_platform(evidence["platform"], f"{kind} evidence.platform")
    started = _string(evidence["started_at"], f"{kind} evidence.started_at", pattern=_UTC_RE)
    completed = _string(evidence["completed_at"], f"{kind} evidence.completed_at", pattern=_UTC_RE)
    if completed < started:
        raise DossierError(f"{kind} evidence completion precedes its start")
    result = _object(evidence["result"], f"{kind} evidence.result")
    _exact_fields(result, {"exit_code", "status", "summary"}, f"{kind} evidence.result")
    exit_code = _integer(result["exit_code"], f"{kind} evidence.result.exit_code")
    summary, summary_passed = _validate_gate_summary(kind, result["summary"])
    log = _object(evidence["log"], f"{kind} evidence.log")
    _exact_fields(log, {"bytes", "relative_path", "sha256"}, f"{kind} evidence.log")
    relative = _safe_relative(log["relative_path"], f"{kind} evidence.log.relative_path")
    log_path = path.parent.joinpath(*relative.parts)
    try:
        log_path.resolve().relative_to(path.parent.resolve())
    except ValueError as exc:
        raise DossierError(f"{kind} evidence log escapes its evidence directory") from exc
    log_payload = _read_bytes(log_path, f"{kind} evidence log", maximum=MAX_JSON_BYTES)
    expected_bytes = _integer(log["bytes"], f"{kind} evidence.log.bytes", minimum=1)
    expected_sha = _string(log["sha256"], f"{kind} evidence.log.sha256", pattern=_SHA256_RE)
    log_matches = len(log_payload) == expected_bytes and _sha256(log_payload) == expected_sha
    passed = (
        source_current
        and command_policy_passed
        and evidence["result"]["status"] == "pass"
        and exit_code == 0
        and summary_passed
        and log_matches
    )
    record_identity = FileIdentity(f"{kind}-evidence", len(payload), _sha256(payload))
    log_identity = FileIdentity(f"{kind}-evidence-log", len(log_payload), _sha256(log_payload))
    return (
        [record_identity, log_identity],
        {
            "source_current": source_current,
            "command": command,
            "command_policy_passed": command_policy_passed,
            "platform": platform,
            "started_at": started,
            "completed_at": completed,
            "status": evidence["result"]["status"],
            "exit_code": exit_code,
            "summary": summary,
            "log_identity_matches": log_matches,
            "passed": passed,
        },
    )


def _validate_linux_ci_evidence(
    path: pathlib.Path,
    git: GitIdentity,
    project: Mapping[str, Any],
    wheel: FileIdentity,
    sdist: FileIdentity,
    artifact_report: FileIdentity,
) -> tuple[FileIdentity, dict[str, Any]]:
    decoded, payload = _read_json(path, "Linux CI evidence")
    evidence = _object(decoded, "Linux CI evidence")
    _exact_fields(
        evidence,
        {
            "completed_at",
            "conclusion",
            "github_context",
            "matrix_evidence",
            "provider",
            "release_artifacts",
            "repository",
            "run_attempt",
            "run_id",
            "run_url",
            "runner",
            "schema_version",
            "source",
            "workflow",
        },
        "Linux CI evidence",
    )
    if evidence["schema_version"] != LINUX_CI_SCHEMA_VERSION:
        raise DossierError("Linux CI evidence schema drifted")
    source = _object(evidence["source"], "Linux CI evidence.source")
    _exact_fields(source, {"commit", "tree"}, "Linux CI evidence.source")
    source_current = source["commit"] == git.commit and source["tree"] == git.tree
    github_context = _object(evidence["github_context"], "Linux CI GitHub context")
    _exact_fields(
        github_context,
        {
            "event_name",
            "job",
            "ref",
            "runner_arch",
            "runner_os",
            "sha",
            "workflow",
            "workflow_ref",
            "workflow_sha",
        },
        "Linux CI GitHub context",
    )
    for key in github_context:
        _string(github_context[key], f"Linux CI GitHub context.{key}")
    github_context_valid = (
        github_context["sha"] == git.commit
        and github_context["workflow"] == "CI"
        and github_context["job"] == "release-evidence"
        and github_context["runner_os"].lower() == "linux"
        and github_context["ref"].startswith("refs/")
        and _GIT_OID_RE.fullmatch(github_context["workflow_sha"]) is not None
    )
    runner = _object(evidence["runner"], "Linux CI evidence.runner")
    _exact_fields(runner, {"architecture", "os", "python_versions"}, "Linux CI evidence.runner")
    python_versions = _array(runner["python_versions"], "Linux CI evidence.runner.python_versions")
    if (
        not python_versions
        or any(not isinstance(value, str) or not value for value in python_versions)
        or python_versions != sorted(set(python_versions))
    ):
        raise DossierError("Linux CI Python versions must be a non-empty string array")
    runner_os = _string(runner["os"], "Linux CI evidence.runner.os")
    runner_architecture = _string(
        runner["architecture"],
        "Linux CI evidence.runner.architecture",
    )
    supported_python_present = {"3.11", "3.12"} <= set(python_versions)
    matrix_raw = _array(evidence["matrix_evidence"], "Linux CI matrix evidence")
    matrix_evidence: list[dict[str, Any]] = []
    expected_matrix_files = {
        "coverage.json",
        "lint.json",
        "lint.log",
        "pytest.log",
        "test.json",
        "type.json",
        "type.log",
    }
    for index, raw in enumerate(matrix_raw):
        field = f"Linux CI matrix evidence[{index}]"
        item = _object(raw, field)
        _exact_fields(item, {"files", "platform", "python_version"}, field)
        matrix_platform = _object(item["platform"], f"{field}.platform")
        _exact_fields(
            matrix_platform,
            {"architecture", "os", "python_full_version"},
            f"{field}.platform",
        )
        python_version = _string(item["python_version"], f"{field}.python_version")
        full_version = _string(
            matrix_platform["python_full_version"],
            f"{field}.platform.python_full_version",
        )
        files_raw = _array(item["files"], f"{field}.files")
        files: list[dict[str, Any]] = []
        for file_index, raw_file in enumerate(files_raw):
            file_field = f"{field}.files[{file_index}]"
            file_item = _object(raw_file, file_field)
            _exact_fields(file_item, {"bytes", "logical_path", "sha256"}, file_field)
            files.append({
                "bytes": _integer(file_item["bytes"], f"{file_field}.bytes", minimum=1),
                "logical_path": _safe_relative(
                    file_item["logical_path"], f"{file_field}.logical_path"
                ).as_posix(),
                "sha256": _string(
                    file_item["sha256"], f"{file_field}.sha256", pattern=_SHA256_RE
                ),
            })
        if files != sorted(files, key=lambda value: value["logical_path"]):
            raise DossierError("Linux CI matrix files must be canonically sorted")
        if (
            len(files) != len(expected_matrix_files)
            or {value["logical_path"] for value in files} != expected_matrix_files
        ):
            raise DossierError("Linux CI matrix evidence file set differs")
        matrix_evidence.append({
            "files": files,
            "platform": {
                "architecture": _string(
                    matrix_platform["architecture"], f"{field}.platform.architecture"
                ),
                "os": _string(matrix_platform["os"], f"{field}.platform.os"),
                "python_full_version": full_version,
            },
            "python_version": python_version,
        })
    matrix_versions = [value["python_version"] for value in matrix_evidence]
    matrix_valid = (
        matrix_versions == ["3.11", "3.12"]
        and matrix_versions == python_versions
        and all(
            value["platform"]["os"].lower() == "linux"
            and value["platform"]["architecture"] == runner_architecture
            and value["platform"]["python_full_version"].startswith(
                value["python_version"] + "."
            )
            for value in matrix_evidence
        )
    )
    artifacts = _object(evidence["release_artifacts"], "Linux CI evidence.release_artifacts")
    _exact_fields(
        artifacts,
        {"artifact_report_sha256", "sdist_sha256", "wheel_sha256"},
        "Linux CI evidence.release_artifacts",
    )
    artifact_match = (
        artifacts["wheel_sha256"] == wheel.sha256
        and artifacts["sdist_sha256"] == sdist.sha256
        and artifacts["artifact_report_sha256"] == artifact_report.sha256
    )
    repository = _string(
        evidence["repository"],
        "Linux CI evidence.repository",
        pattern=_GITHUB_REPOSITORY_RE,
    )
    repository_matches = repository == project["github_repository"]
    workflow = _string(evidence["workflow"], "Linux CI evidence.workflow")
    workflow_matches = workflow == ".github/workflows/ci.yml"
    github_context_valid = github_context_valid and github_context[
        "workflow_ref"
    ].startswith(f"{repository}/{workflow}@")
    run_id = _integer(evidence["run_id"], "Linux CI evidence.run_id", minimum=1)
    run_attempt = _integer(
        evidence["run_attempt"],
        "Linux CI evidence.run_attempt",
        minimum=1,
    )
    run_url = _string(evidence["run_url"], "Linux CI evidence.run_url")
    parsed_url = urllib.parse.urlsplit(run_url)
    url_valid = (
        parsed_url.scheme == "https"
        and parsed_url.hostname == "github.com"
        and parsed_url.username is None
        and parsed_url.password is None
        and parsed_url.port is None
        and not parsed_url.query
        and not parsed_url.fragment
        and parsed_url.path == f"/{repository}/actions/runs/{run_id}"
    )
    completed_at = _string(
        evidence["completed_at"],
        "Linux CI evidence.completed_at",
        pattern=_UTC_RE,
    )
    passed = (
        evidence["provider"] == "github-actions"
        and evidence["conclusion"] == "success"
        and runner_os.lower() == "linux"
        and supported_python_present
        and matrix_valid
        and github_context_valid
        and repository_matches
        and workflow_matches
        and source_current
        and artifact_match
        and url_valid
    )
    return (
        FileIdentity("linux-ci-evidence", len(payload), _sha256(payload)),
        {
            "provider": evidence["provider"],
            "repository": repository,
            "repository_matches": repository_matches,
            "workflow": workflow,
            "workflow_matches": workflow_matches,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "run_url": run_url,
            "completed_at": completed_at,
            "runner": {
                "os": runner_os,
                "architecture": runner_architecture,
                "python_versions": python_versions,
            },
            "github_context": dict(github_context),
            "github_context_valid": github_context_valid,
            "matrix_evidence": matrix_evidence,
            "matrix_evidence_valid": matrix_valid,
            "supported_python_present": supported_python_present,
            "source_current": source_current,
            "release_artifacts_match": artifact_match,
            "url_valid": url_valid,
            "conclusion": evidence["conclusion"],
            "passed": passed,
        },
    )


def _validate_environment_lock(
    path: pathlib.Path,
    git: GitIdentity,
    wheel: FileIdentity,
    sdist: FileIdentity,
    project: Mapping[str, Any],
    expected_packages: set[tuple[str, str]],
) -> tuple[FileIdentity, dict[str, Any]]:
    decoded, payload = _read_json(path, "environment lock")
    lock = _object(decoded, "environment lock")
    _exact_fields(
        lock,
        {"packages", "platform", "python", "schema_version", "source"},
        "environment lock",
    )
    if lock["schema_version"] != ENVIRONMENT_LOCK_SCHEMA_VERSION:
        raise DossierError("environment lock schema drifted")
    source = _object(lock["source"], "environment lock.source")
    _exact_fields(
        source,
        {"commit", "sdist_sha256", "tree", "wheel_sha256"},
        "environment lock.source",
    )
    source_current = source["commit"] == git.commit and source["tree"] == git.tree
    artifacts_match = (
        source["wheel_sha256"] == wheel.sha256 and source["sdist_sha256"] == sdist.sha256
    )
    platform = _object(lock["platform"], "environment lock.platform")
    _exact_fields(platform, {"architecture", "os"}, "environment lock.platform")
    python = _object(lock["python"], "environment lock.python")
    _exact_fields(python, {"implementation", "version"}, "environment lock.python")
    platform_os = _string(platform["os"], "environment lock.platform.os")
    platform_architecture = _string(
        platform["architecture"],
        "environment lock.platform.architecture",
    )
    python_implementation = _string(
        python["implementation"],
        "environment lock.python.implementation",
    )
    python_version = _string(python["version"], "environment lock.python.version")
    try:
        python_version_supported = SpecifierSet(str(project["requires_python"])).contains(
            python_version, prereleases=True
        )
    except (InvalidSpecifier, InvalidVersion):
        python_version_supported = False
    platform_supported = platform_os.lower() == "linux"
    python_runtime_supported = python_implementation == "CPython" and python_version_supported
    packages = _array(lock["packages"], "environment lock.packages")
    identities: list[tuple[str, str]] = []
    root_matches = False
    root_wheel_hash_matches = False
    for index, raw in enumerate(packages):
        package = _object(raw, f"environment lock.packages[{index}]")
        _exact_fields(package, {"hashes", "name", "version"}, f"environment lock.packages[{index}]")
        name = _string(package["name"], f"environment lock.packages[{index}].name")
        version = _string(package["version"], f"environment lock.packages[{index}].version")
        hashes = _array(package["hashes"], f"environment lock.packages[{index}].hashes")
        if not hashes or any(
            not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None for value in hashes
        ):
            raise DossierError("every environment package must have one or more SHA-256 hashes")
        if hashes != sorted(set(hashes)):
            raise DossierError("environment package hashes must be unique and sorted")
        identity = (_normalized_name(name), version)
        identities.append(identity)
        if identity == (_normalized_name(str(project["name"])), str(project["version"])):
            root_matches = True
            root_wheel_hash_matches = wheel.sha256 in hashes
    if identities != sorted(set(identities)):
        raise DossierError("environment packages must be unique and canonically sorted")
    identity_set = set(identities)
    package_sets_match = identity_set == expected_packages
    required_names = set(_array(project["runtime_dependencies"], "project dependencies"))
    direct_dependencies_present = required_names <= {name for name, _version in identity_set}
    runtime_requirement_versions_match = _runtime_requirement_versions_match(
        _array(project["runtime_requirements"], "project runtime requirements"),
        identity_set,
    )
    passed = (
        bool(packages)
        and source_current
        and artifacts_match
        and root_matches
        and root_wheel_hash_matches
        and package_sets_match
        and direct_dependencies_present
        and runtime_requirement_versions_match
        and platform_supported
        and python_runtime_supported
    )
    return (
        FileIdentity("environment-lock", len(payload), _sha256(payload)),
        {
            "platform": {
                "os": platform_os,
                "architecture": platform_architecture,
            },
            "python": {
                "implementation": python_implementation,
                "version": python_version,
            },
            "platform_supported": platform_supported,
            "python_runtime_supported": python_runtime_supported,
            "package_count": len(packages),
            "package_set_sha256": _package_set_sha256(identity_set),
            "package_sets_match": package_sets_match,
            "direct_dependencies_present": direct_dependencies_present,
            "runtime_requirement_versions_match": runtime_requirement_versions_match,
            "source_current": source_current,
            "release_artifacts_match": artifacts_match,
            "root_package_matches": root_matches,
            "root_wheel_hash_matches": root_wheel_hash_matches,
            "passed": passed,
        },
    )


def _validate_literature_lock(path: pathlib.Path) -> tuple[FileIdentity, dict[str, Any]]:
    decoded, payload = _read_json(path, "literature lock")
    lock = _object(decoded, "literature lock")
    _exact_fields(lock, {"entries", "schema_version", "source"}, "literature lock")
    entries = _array(lock["entries"], "literature lock.entries")
    versioned_ids: list[str] = []
    for index, raw in enumerate(entries):
        entry = _object(raw, f"literature lock.entries[{index}]")
        versioned_id = _string(
            entry.get("versioned_id"),
            f"literature lock.entries[{index}].versioned_id",
            pattern=_ARXIV_VERSIONED_RE,
        )
        pdf_url = _string(entry.get("pdf_url"), f"literature lock.entries[{index}].pdf_url")
        _string(
            entry.get("canonical_title"),
            f"literature lock.entries[{index}].canonical_title",
        )
        parsed = urllib.parse.urlsplit(pdf_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "arxiv.org"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
            or parsed.path != f"/pdf/{versioned_id}"
        ):
            raise DossierError("literature PDF URLs must use canonical arxiv.org HTTPS")
        versioned_ids.append(versioned_id)
    if not entries or versioned_ids != sorted(set(versioned_ids)):
        raise DossierError("literature entries must be non-empty, unique, and sorted")
    source = _object(lock["source"], "literature lock.source")
    responses = _array(source.get("responses"), "literature lock.source.responses")
    if not responses:
        raise DossierError("literature lock must preserve at least one source response")
    for index, raw in enumerate(responses):
        response = _object(raw, f"literature lock.source.responses[{index}]")
        _string(
            response.get("raw_atom_sha256"),
            f"literature lock.source.responses[{index}].raw_atom_sha256",
            pattern=_SHA256_RE,
        )
    return (
        FileIdentity("literature-lock", len(payload), _sha256(payload)),
        {
            "schema_version": lock["schema_version"],
            "entry_count": len(entries),
            "metadata_identity_passed": lock["schema_version"] == "0.1.0",
            "passed": lock["schema_version"] == "0.1.0",
        },
    )


def _validate_literature_claims(
    path: pathlib.Path,
    literature_lock_path: pathlib.Path,
) -> tuple[FileIdentity, dict[str, Any]]:
    decoded, payload = _read_json(path, "literature claim ledger")
    ledger = _object(decoded, "literature claim ledger")
    _exact_fields(
        ledger,
        {"schema_version", "status", "reviewed_at", "coverage", "entries"},
        "literature claim ledger",
    )
    if (
        ledger["schema_version"] != CLAIM_LEDGER_SCHEMA_VERSION
        or ledger["status"] != CLAIM_LEDGER_STATUS
    ):
        raise DossierError("literature claim ledger schema/status drifted")
    _string(ledger["reviewed_at"], "claim ledger.reviewed_at", pattern=_DATE_RE)

    raw_lock, _lock_payload = _read_json(literature_lock_path, "literature lock")
    lock = _object(raw_lock, "literature lock")
    locked_entries = _array(lock.get("entries"), "literature lock.entries")
    locked: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(locked_entries):
        entry = _object(raw, f"literature lock.entries[{index}]")
        versioned_id = _string(
            entry.get("versioned_id"),
            f"literature lock.entries[{index}].versioned_id",
            pattern=_ARXIV_VERSIONED_RE,
        )
        if versioned_id in locked:
            raise DossierError("literature lock contains duplicate versioned IDs")
        locked[versioned_id] = entry

    coverage = _object(ledger["coverage"], "claim ledger.coverage")
    _exact_fields(
        coverage,
        {"locked_paper_count", "reviewed_pdf_count", "complete"},
        "claim ledger.coverage",
    )
    locked_count = _integer(
        coverage["locked_paper_count"],
        "claim ledger.coverage.locked_paper_count",
        minimum=1,
    )
    reviewed_count = _integer(
        coverage["reviewed_pdf_count"],
        "claim ledger.coverage.reviewed_pdf_count",
        minimum=1,
    )
    if locked_count != len(locked) or coverage["complete"] is not False:
        raise DossierError("claim ledger coverage does not match its partial literature lock")

    entries = _array(ledger["entries"], "claim ledger.entries")
    if reviewed_count != len(entries) or reviewed_count >= locked_count:
        raise DossierError("claim ledger reviewed-PDF count is inconsistent or not partial")
    seen_ids: list[str] = []
    seen_claims: set[str] = set()
    for index, raw in enumerate(entries):
        field = f"claim ledger.entries[{index}]"
        entry = _object(raw, field)
        _exact_fields(
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
        versioned_id = _string(
            entry["versioned_id"],
            f"{field}.versioned_id",
            pattern=_ARXIV_VERSIONED_RE,
        )
        seen_ids.append(versioned_id)
        source = locked.get(versioned_id)
        if source is None:
            raise DossierError(f"claim ledger entry {versioned_id} is absent from the lock")
        canonical_title = _string(entry["canonical_title"], f"{field}.canonical_title")
        if canonical_title != source.get("canonical_title") or entry["pdf_url"] != source.get(
            "pdf_url"
        ):
            raise DossierError(f"claim ledger entry {versioned_id} drifted from the lock")
        _string(entry["pdf_sha256"], f"{field}.pdf_sha256", pattern=_SHA256_RE)
        pdf_bytes = _integer(entry["pdf_bytes"], f"{field}.pdf_bytes", minimum=1)
        if pdf_bytes > MAX_ARCHIVE_MEMBER_BYTES:
            raise DossierError("claim ledger PDF byte count exceeds the safety bound")
        if entry["artifact_name"] != f"{versioned_id}.pdf":
            raise DossierError("claim ledger PDF artifact name is noncanonical")
        review = _object(entry["review"], f"{field}.review")
        _exact_fields(review, {"method", "human_confirmed"}, f"{field}.review")
        if (
            review["method"] != "machine_assisted_primary_pdf_review"
            or review["human_confirmed"] is not False
        ):
            raise DossierError("claim ledger cannot claim unsupported or human review")
        claims = _array(entry["claims"], f"{field}.claims")
        if not claims:
            raise DossierError(f"claim ledger entry {versioned_id} has no claims")
        for claim_index, raw_claim in enumerate(claims):
            claim_field = f"{field}.claims[{claim_index}]"
            claim = _object(raw_claim, claim_field)
            _exact_fields(
                claim,
                {
                    "claim_id",
                    "claim_type",
                    "paraphrase",
                    "pdf_pages",
                    "section",
                    "project_use",
                },
                claim_field,
            )
            claim_id = _string(claim["claim_id"], f"{claim_field}.claim_id")
            if claim_id in seen_claims:
                raise DossierError("claim ledger contains duplicate claim IDs")
            seen_claims.add(claim_id)
            if claim["claim_type"] not in {
                "author_reported_method",
                "author_reported_result",
                "author_reported_limitation",
            }:
                raise DossierError("claim ledger contains an unsupported claim type")
            _string(claim["paraphrase"], f"{claim_field}.paraphrase")
            _string(claim["section"], f"{claim_field}.section")
            _string(claim["project_use"], f"{claim_field}.project_use")
            pages = [
                _integer(page, f"{claim_field}.pdf_pages", minimum=1)
                for page in _array(claim["pdf_pages"], f"{claim_field}.pdf_pages")
            ]
            if not pages or pages != sorted(set(pages)):
                raise DossierError("claim ledger PDF pages must be non-empty, unique, and sorted")
    if seen_ids != sorted(set(seen_ids)):
        raise DossierError("claim ledger entries must be unique and sorted")
    return (
        FileIdentity("literature-claim-ledger", len(payload), _sha256(payload)),
        {
            "schema_version": ledger["schema_version"],
            "locked_paper_count": locked_count,
            "reviewed_pdf_count": reviewed_count,
            "verified_pdf_count": 0,
            "claim_count": len(seen_claims),
            "coverage_complete": False,
            "human_confirmation_complete": False,
            "scientific_release_ready": False,
            "passed": True,
        },
    )


def _study_code_identities(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    identities: list[Mapping[str, Any]] = []
    for key in (
        "study_code",
        "study_code_identity",
        "acquisition_study_code_identity",
        "analysis_code_identity",
        "acquisition_code_identity",
    ):
        candidate = value.get(key)
        if isinstance(candidate, dict):
            identities.append(candidate)
    feature_freeze = value.get("feature_freeze")
    if isinstance(feature_freeze, dict):
        for key in ("analysis_code_identity", "acquisition_code_identity"):
            candidate = feature_freeze.get(key)
            if isinstance(candidate, dict):
                identities.append(candidate)
    return identities


def _validate_study_artifacts(
    artifacts: Sequence[tuple[str, pathlib.Path]],
    repo_root: pathlib.Path,
) -> tuple[list[FileIdentity], list[dict[str, Any]], bool]:
    if not artifacts:
        return [], [], False
    seen: set[str] = set()
    identities: list[FileIdentity] = []
    summaries: list[dict[str, Any]] = []
    all_bound = True
    for name, path in sorted(artifacts):
        if _NAME_RE.fullmatch(name) is None or name in seen:
            raise DossierError("study artifact names must be unique lowercase identifiers")
        seen.add(name)
        decoded, payload = _read_json(path, f"study artifact {name}")
        study = _object(decoded, f"study artifact {name}")
        schema_version = study.get("schema_version")
        study_id = study.get("study_id")
        if not isinstance(schema_version, str) or not schema_version:
            raise DossierError(f"study artifact {name} lacks schema_version")
        if not isinstance(study_id, str) or not study_id:
            raise DossierError(f"study artifact {name} lacks study_id")
        code_checks: list[dict[str, Any]] = []
        for index, raw_identity in enumerate(_study_code_identities(study)):
            identity = _object(raw_identity, f"study artifact {name} code identity {index}")
            logical_path = _safe_relative(
                identity.get("logical_path"),
                f"study artifact {name} code logical_path",
            )
            if logical_path.parts[0] != "experiments" or logical_path.suffix != ".py":
                raise DossierError("study code identities must name Python code under experiments/")
            digest = _string(
                identity.get("sha256"),
                f"study artifact {name} code sha256",
                pattern=_SHA256_RE,
            )
            source = repo_root.joinpath(*logical_path.parts)
            try:
                source.resolve().relative_to(repo_root.resolve())
            except ValueError as exc:
                raise DossierError("study code identity escapes the repository") from exc
            source_payload = _read_bytes(
                source,
                f"study code {logical_path.as_posix()}",
                maximum=MAX_ARCHIVE_MEMBER_BYTES,
            )
            _assert_head_bound_files(
                repo_root,
                {logical_path.as_posix(): source_payload},
                f"study artifact {name} code projection",
            )
            matches = _sha256(source_payload) == digest
            if "bytes" in identity:
                matches = matches and identity["bytes"] == len(source_payload)
            code_checks.append(
                {
                    "logical_path": logical_path.as_posix(),
                    "sha256": digest,
                    "matches_current_source": matches,
                }
            )
            all_bound = all_bound and matches
        if not code_checks:
            all_bound = False
        file_identity = FileIdentity(f"study-{name}", len(payload), _sha256(payload))
        identities.append(file_identity)
        summaries.append(
            {
                "name": name,
                "schema_version": schema_version,
                "study_id": study_id,
                "identity": file_identity.to_dict(),
                "code_identities": code_checks,
                "code_bound": bool(code_checks)
                and all(item["matches_current_source"] for item in code_checks),
            }
        )
    return identities, summaries, all_bound


def _attestation_template(
    *,
    project: Mapping[str, Any],
    git: GitIdentity,
    subjects_sha256: str,
    sbom: FileIdentity,
    inventory: FileIdentity,
) -> dict[str, Any]:
    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "release_version": project["version"],
        "source_commit": git.commit,
        "source_tree": git.tree,
        "tag": git.tag,
        "release_subjects_sha256": subjects_sha256,
        "maintainer": {"identifier": None, "name": None},
        "legal_review": {
            "completed": False,
            "reviewed_at": None,
            "reviewed_inventory_sha256": inventory.sha256,
            "reviewed_sbom_sha256": sbom.sha256,
            "reviewer": None,
            "scope_profiles": ["default", "structural"],
        },
        "approval": {
            "approved_at": None,
            "decision": "blocked",
            "statement": (
                "I inspected the exact release subjects and source binding; quality-gate and "
                "Linux CI evidence; dependency inventory, license texts, and native/vendored "
                "scope; automated limitations; and known research limitations."
            ),
        },
    }


def _validate_attestation(
    path: pathlib.Path | None,
    template: Mapping[str, Any],
    git: GitIdentity,
) -> tuple[FileIdentity | None, dict[str, Any]]:
    if path is None:
        return None, {
            "provided": False,
            "canonical_json": False,
            "content_valid": False,
            "legal_review_completed": False,
            "tag_digest_binding_present": False,
            "passed": False,
        }
    decoded, payload = _read_json(path, "human release attestation")
    attestation = _object(decoded, "human release attestation")
    _exact_fields(
        attestation,
        {
            "approval",
            "legal_review",
            "maintainer",
            "release_subjects_sha256",
            "release_version",
            "schema_version",
            "source_commit",
            "source_tree",
            "tag",
        },
        "human release attestation",
    )
    maintainer = _object(attestation["maintainer"], "attestation.maintainer")
    _exact_fields(maintainer, {"identifier", "name"}, "attestation.maintainer")
    legal = _object(attestation["legal_review"], "attestation.legal_review")
    _exact_fields(
        legal,
        {
            "completed",
            "reviewed_at",
            "reviewed_inventory_sha256",
            "reviewed_sbom_sha256",
            "reviewer",
            "scope_profiles",
        },
        "attestation.legal_review",
    )
    approval = _object(attestation["approval"], "attestation.approval")
    _exact_fields(
        approval,
        {"approved_at", "decision", "statement"},
        "attestation.approval",
    )
    canonical_json = payload == _canonical_json_bytes(attestation)
    template_legal = _object(
        template["legal_review"],
        "attestation template legal review",
    )
    template_approval = _object(
        template["approval"],
        "attestation template approval",
    )
    content_valid = (
        canonical_json
        and attestation["schema_version"] == ATTESTATION_SCHEMA_VERSION
        and attestation["release_version"] == template["release_version"]
        and attestation["source_commit"] == template["source_commit"]
        and attestation["source_tree"] == template["source_tree"]
        and attestation["tag"] == template["tag"]
        and attestation["release_subjects_sha256"] == template["release_subjects_sha256"]
        and legal["reviewed_inventory_sha256"] == template_legal["reviewed_inventory_sha256"]
        and legal["reviewed_sbom_sha256"] == template_legal["reviewed_sbom_sha256"]
        and legal["completed"] is True
        and approval["decision"] == "approve"
        and approval["statement"] == template_approval["statement"]
    )
    try:
        _string(maintainer.get("name"), "attestation.maintainer.name")
        _string(maintainer.get("identifier"), "attestation.maintainer.identifier")
        _string(legal.get("reviewer"), "attestation.legal_review.reviewer")
        reviewed_at = _string(
            legal.get("reviewed_at"),
            "attestation.legal_review.reviewed_at",
            pattern=_UTC_RE,
        )
        approved_at = _string(
            approval.get("approved_at"),
            "attestation.approval.approved_at",
            pattern=_UTC_RE,
        )
        _string(approval.get("statement"), "attestation.approval.statement")
        profiles = _array(legal["scope_profiles"], "attestation.legal_review.scope_profiles")
        if profiles != ["default", "structural"] or approved_at < reviewed_at:
            content_valid = False
    except DossierError:
        content_valid = False
    digest = _sha256(payload)
    expected_line = f"Release-Attestation-SHA256: {digest}"
    tag_binding = git.tag_message is not None and expected_line in git.tag_message.splitlines()
    passed = content_valid and tag_binding and git.tag_signature_verified
    return (
        FileIdentity("human-release-attestation", len(payload), digest),
        {
            "provided": True,
            "canonical_json": canonical_json,
            "content_valid": content_valid,
            "legal_review_completed": legal["completed"] is True,
            "tag_digest_binding_present": tag_binding,
            "passed": passed,
        },
    )


def _build_dossier_with_git(
    inputs: DossierInputs,
    git: GitIdentity,
) -> dict[str, Any]:
    """Test seam for dossier construction with an already inspected Git identity."""

    repo_root = inputs.repo_root.resolve()
    if inputs.repo_root.is_symlink() or not repo_root.is_dir():
        raise DossierError("repo_root must be a regular directory")
    project = _project_identity(repo_root)
    policy_identity, policy_summary = _authoritative_license_policy(repo_root)
    _require_canonical_repo_evidence(
        inputs.literature_lock,
        repo_root,
        "docs/literature.lock.json",
        "literature lock",
    )
    _require_canonical_repo_evidence(
        inputs.literature_claims,
        repo_root,
        "docs/literature.claims.json",
        "literature claim ledger",
    )

    wheel_identity, wheel_summary = _inspect_wheel(
        inputs.wheel,
        repo_root,
        project,
    )
    sdist_identity, sdist_summary = _inspect_sdist(
        inputs.sdist,
        repo_root,
        project,
    )
    artifact_identity, artifact_summary = _validate_artifact_report(
        inputs.artifact_report,
        wheel_identity,
        sdist_identity,
        policy_identity,
        inputs.wheel.name,
        inputs.sdist.name,
    )
    sbom_identity, sbom_summary, sbom_packages = _validate_sbom(inputs.sbom, project)
    inventory_identity, inventory_summary, inventory_packages = _validate_license_inventory(
        inputs.license_inventory,
        project,
    )
    license_identity, license_summary = _validate_license_report(
        inputs.license_report,
        sbom=sbom_identity,
        sbom_packages=sbom_packages,
        inventory=inventory_identity,
        inventory_packages=inventory_packages,
        required_dependency_names=set(
            _array(project["runtime_dependencies"], "project dependencies")
        ),
        runtime_requirements=tuple(
            _array(project["runtime_requirements"], "project runtime requirements")
        ),
        artifact_policy_sha256=str(artifact_summary["policy_sha256"]),
        authoritative_policy=policy_identity,
        authoritative_policy_summary=policy_summary,
    )

    gate_paths = {
        "test": inputs.test_evidence,
        "coverage": inputs.coverage_evidence,
        "lint": inputs.lint_evidence,
        "type": inputs.type_evidence,
    }
    gate_identities: list[FileIdentity] = []
    gate_summaries: dict[str, dict[str, Any]] = {}
    for kind in ("test", "coverage", "lint", "type"):
        identities, summary = _validate_gate_evidence(gate_paths[kind], kind, git)
        gate_identities.extend(identities)
        gate_summaries[kind] = summary
    linux_identity, linux_summary = _validate_linux_ci_evidence(
        inputs.linux_ci_evidence,
        git,
        project,
        wheel_identity,
        sdist_identity,
        artifact_identity,
    )
    environment_identity, environment_summary = _validate_environment_lock(
        inputs.environment_lock,
        git,
        wheel_identity,
        sdist_identity,
        project,
        inventory_packages,
    )
    literature_identity, literature_summary = _validate_literature_lock(inputs.literature_lock)
    claims_identity, claims_summary = _validate_literature_claims(
        inputs.literature_claims,
        inputs.literature_lock,
    )
    study_identities, study_summaries, studies_bound = _validate_study_artifacts(
        inputs.study_artifacts,
        repo_root,
    )

    release_subjects = [
        wheel_identity,
        sdist_identity,
        artifact_identity,
        sbom_identity,
        inventory_identity,
        license_identity,
        policy_identity,
        *gate_identities,
        linux_identity,
        environment_identity,
        literature_identity,
        claims_identity,
        *study_identities,
    ]
    logical_names = [identity.logical_name for identity in release_subjects]
    if len(logical_names) != len(set(logical_names)):
        raise DossierError("release subject logical names collide")
    subject_payload = {
        "schema_version": DOSSIER_SCHEMA_VERSION,
        "source": {"commit": git.commit, "tree": git.tree},
        "subjects": [
            identity.to_dict()
            for identity in sorted(release_subjects, key=lambda item: item.logical_name)
        ],
    }
    release_subjects_sha256 = _sha256(_canonical_json_bytes(subject_payload, indent=None))
    template = _attestation_template(
        project=project,
        git=git,
        subjects_sha256=release_subjects_sha256,
        sbom=sbom_identity,
        inventory=inventory_identity,
    )
    attestation_identity, attestation_summary = _validate_attestation(
        inputs.attestation,
        template,
        git,
    )

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add_check(identifier: str, passed: bool, evidence: Mapping[str, Any]) -> None:
        if any(item["id"] == identifier for item in checks):
            raise DossierError(f"duplicate readiness check {identifier}")
        checks.append({"id": identifier, "passed": bool(passed), "evidence": dict(evidence)})
        if not passed:
            blockers.append(identifier)

    add_check(
        "git_worktree_clean",
        not git.dirty_entries,
        {"dirty_entry_count": len(git.dirty_entries)},
    )
    add_check(
        "git_diff_check",
        git.diff_check_passed,
        {"diff_check_passed": git.diff_check_passed},
    )
    add_check(
        "project_version_parity",
        bool(project["version_parity"]),
        {
            "project_version": project["version"],
            "package_version": project["package_version"],
            "readme_citation_versions": project["readme_citation_versions"],
        },
    )
    add_check(
        "changelog_released",
        bool(project["changelog_released"]) and not bool(project["changelog_unreleased_candidate"]),
        {
            "released_heading": project["changelog_released"],
            "unreleased_candidate_heading": project["changelog_unreleased_candidate"],
        },
    )
    expected_tags = [str(project["version"]), f"v{project['version']}"]
    add_check(
        "release_tag_present",
        git.tag in expected_tags,
        {"expected": expected_tags, "observed": git.tag},
    )
    add_check(
        "release_tag_annotated",
        git.tag_object_type == "tag",
        {"tag_object_type": git.tag_object_type},
    )
    add_check(
        "release_tag_signature_verified",
        git.tag_signature_verified,
        {"signature_verified": git.tag_signature_verified},
    )
    add_check(
        "release_tag_points_to_head",
        git.tag_target == git.commit,
        {"head": git.commit, "tag_target": git.tag_target},
    )
    add_check(
        "wheel_source_and_version_match",
        bool(wheel_summary["project_identity_matches"]),
        {
            "name": wheel_summary["name"],
            "version": wheel_summary["version"],
            "projection_sha256": wheel_summary["package_source_projection_sha256"],
        },
    )
    add_check(
        "sdist_source_and_version_match",
        bool(sdist_summary["project_identity_matches"]),
        {
            "name": sdist_summary["name"],
            "version": sdist_summary["version"],
            "projection_sha256": sdist_summary["critical_source_projection_sha256"],
        },
    )
    add_check(
        "wheel_sdist_metadata_match",
        wheel_summary["metadata_sha256"] == sdist_summary["metadata_sha256"],
        {
            "wheel_metadata_sha256": wheel_summary["metadata_sha256"],
            "sdist_metadata_sha256": sdist_summary["metadata_sha256"],
        },
    )
    add_check(
        "artifact_audit_passed_and_current",
        bool(artifact_summary["passed"]),
        artifact_summary,
    )
    add_check(
        "authoritative_license_policy_bound",
        bool(policy_summary["passed"]),
        {
            "identity": policy_identity.to_dict(),
            "logical_path": policy_summary["logical_path"],
        },
    )
    add_check("sbom_current", bool(sbom_summary["passed"]), sbom_summary)
    add_check(
        "license_inventory_current",
        bool(inventory_summary["passed"]),
        inventory_summary,
    )
    add_check(
        "license_automation_passed_and_current",
        bool(license_summary["automation_passed"]),
        license_summary,
    )
    add_check(
        "license_automation_scoped_as_nonlegal",
        bool(license_summary["automation_scope_honest"]),
        {
            "legal_review_complete": license_summary["legal_review_complete"],
            "automation_scope_honest": license_summary["automation_scope_honest"],
        },
    )
    for kind in ("test", "coverage", "lint", "type"):
        add_check(
            f"{kind}_evidence_passed_and_current",
            bool(gate_summaries[kind]["passed"]),
            gate_summaries[kind],
        )
    add_check(
        "linux_ci_passed_and_current",
        bool(linux_summary["passed"]),
        linux_summary,
    )
    add_check(
        "environment_lock_current",
        bool(environment_summary["passed"]),
        environment_summary,
    )
    add_check(
        "literature_metadata_lock_valid",
        bool(literature_summary["passed"]),
        literature_summary,
    )
    add_check(
        "literature_claim_ledger_valid",
        bool(claims_summary["passed"]),
        claims_summary,
    )
    add_check(
        "study_artifacts_present_and_code_bound",
        bool(study_summaries) and studies_bound,
        {
            "artifact_count": len(study_summaries),
            "all_code_bound": studies_bound,
        },
    )
    add_check(
        "human_attestation_valid_and_tag_bound",
        bool(attestation_summary["passed"]),
        attestation_summary,
    )

    release_ready = not blockers
    dossier = {
        "schema_version": DOSSIER_SCHEMA_VERSION,
        "release_profile": RELEASE_PROFILE,
        "release_version": project["version"],
        "release_ready": release_ready,
        "readiness_claim": (
            "ready_for_named_human_release_action"
            if release_ready
            else "blocked_no_public_release_claim"
        ),
        "blockers": blockers,
        "source": git.to_dict(),
        "project": project,
        "release_subjects_sha256": release_subjects_sha256,
        "release_subjects": subject_payload["subjects"],
        "artifacts": {
            "wheel": {"identity": wheel_identity.to_dict(), **wheel_summary},
            "sdist": {"identity": sdist_identity.to_dict(), **sdist_summary},
            "artifact_audit_report": {
                "identity": artifact_identity.to_dict(),
                **artifact_summary,
            },
            "sbom": {"identity": sbom_identity.to_dict(), **sbom_summary},
            "license_inventory": {
                "identity": inventory_identity.to_dict(),
                **inventory_summary,
            },
            "license_report": {
                "identity": license_identity.to_dict(),
                **license_summary,
            },
            "license_policy": {
                "identity": policy_identity.to_dict(),
                **policy_summary,
            },
            "environment_lock": {
                "identity": environment_identity.to_dict(),
                **environment_summary,
            },
        },
        "quality_gates": gate_summaries,
        "linux_ci": {
            "identity": linux_identity.to_dict(),
            **linux_summary,
        },
        "research_evidence": {
            "literature": {
                "identity": literature_identity.to_dict(),
                **literature_summary,
            },
            "claim_ledger": {
                "identity": claims_identity.to_dict(),
                **claims_summary,
            },
            "studies": study_summaries,
        },
        "human_attestation": {
            "provided_identity": (
                attestation_identity.to_dict() if attestation_identity is not None else None
            ),
            "validation": attestation_summary,
            "required_template": template,
            "tag_binding_contract": (
                "The verified annotated tag message must contain "
                "Release-Attestation-SHA256: <sha256 of canonical attestation bytes>."
            ),
        },
        "checks": checks,
        "limitations": [
            "The dossier verifies local bytes and declared CI evidence; it does not query GitHub or a transparency log.",
            "A verified tag signature authenticates the configured signing identity only to the extent of the local Git trust store.",
            "Legal review and human approval remain human claims bound by the signed tag; this tool is not legal advice.",
            "The partial claim ledger binds declared PDF hashes and page mappings, but this dossier does not receive or re-verify the PDF bytes.",
            "Engineering release readiness is not empirical validation of the router or research hypotheses.",
        ],
    }
    # Exercise canonical serialization now so no caller can receive a value that
    # later fails deterministic publication.
    _canonical_json_bytes(dossier)
    return dossier


def build_dossier(inputs: DossierInputs) -> dict[str, Any]:
    """Inspect every input and return one deterministic release dossier."""

    repo_root = inputs.repo_root.resolve()
    project = _project_identity(repo_root)
    initial_git = inspect_git_identity(repo_root, str(project["version"]))
    dossier = _build_dossier_with_git(inputs, initial_git)
    final_git = inspect_git_identity(repo_root, str(project["version"]))
    if final_git != initial_git:
        raise DossierError("Git identity changed while the release dossier was being built")
    return dossier


def dossier_bytes(dossier: Mapping[str, Any]) -> bytes:
    return _canonical_json_bytes(dict(dossier))


def write_dossier(path: pathlib.Path, dossier: Mapping[str, Any]) -> None:
    payload = dossier_bytes(dossier)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            path.unlink(missing_ok=True)
        raise


def check_dossier(path: pathlib.Path, expected: Mapping[str, Any]) -> None:
    payload = _read_bytes(path, "release dossier", maximum=MAX_JSON_BYTES)
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_strict_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, DossierError) as exc:
        raise DossierError(f"invalid existing release dossier: {exc}") from exc
    if not isinstance(decoded, dict):
        raise DossierError("existing release dossier must be a JSON object")
    canonical = dossier_bytes(decoded)
    if payload != canonical:
        raise DossierError("existing release dossier is not canonical JSON")
    if payload != dossier_bytes(expected):
        raise DossierError("existing release dossier is stale or mismatched")


def _study_argument(value: str) -> tuple[str, pathlib.Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("study artifacts must use NAME=PATH")
    name, raw_path = value.split("=", 1)
    if _NAME_RE.fullmatch(name) is None or not raw_path:
        raise argparse.ArgumentTypeError("study artifacts must use a lowercase NAME=PATH")
    return name, pathlib.Path(raw_path)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or check a deterministic fail-closed release dossier",
    )
    parser.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--wheel", type=pathlib.Path, required=True)
    parser.add_argument("--sdist", type=pathlib.Path, required=True)
    parser.add_argument("--artifact-report", type=pathlib.Path, required=True)
    parser.add_argument("--sbom", type=pathlib.Path, required=True)
    parser.add_argument("--license-inventory", type=pathlib.Path, required=True)
    parser.add_argument("--license-report", type=pathlib.Path, required=True)
    parser.add_argument("--test-evidence", type=pathlib.Path, required=True)
    parser.add_argument("--coverage-evidence", type=pathlib.Path, required=True)
    parser.add_argument("--lint-evidence", type=pathlib.Path, required=True)
    parser.add_argument("--type-evidence", type=pathlib.Path, required=True)
    parser.add_argument("--linux-ci-evidence", type=pathlib.Path, required=True)
    parser.add_argument("--literature-lock", type=pathlib.Path, required=True)
    parser.add_argument("--literature-claims", type=pathlib.Path, required=True)
    parser.add_argument("--environment-lock", type=pathlib.Path, required=True)
    parser.add_argument(
        "--study-artifact",
        action="append",
        default=[],
        type=_study_argument,
        metavar="NAME=PATH",
    )
    parser.add_argument("--attestation", type=pathlib.Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=pathlib.Path)
    mode.add_argument("--check", type=pathlib.Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    inputs = DossierInputs(
        repo_root=args.repo_root,
        wheel=args.wheel,
        sdist=args.sdist,
        artifact_report=args.artifact_report,
        sbom=args.sbom,
        license_inventory=args.license_inventory,
        license_report=args.license_report,
        test_evidence=args.test_evidence,
        coverage_evidence=args.coverage_evidence,
        lint_evidence=args.lint_evidence,
        type_evidence=args.type_evidence,
        linux_ci_evidence=args.linux_ci_evidence,
        literature_lock=args.literature_lock,
        literature_claims=args.literature_claims,
        environment_lock=args.environment_lock,
        study_artifacts=tuple(args.study_artifact),
        attestation=args.attestation,
    )
    try:
        if args.output is not None:
            try:
                args.output.resolve().relative_to(args.repo_root.resolve())
            except ValueError:
                pass
            else:
                raise DossierError("release dossier output must be outside the repository")
        dossier = build_dossier(inputs)
        if args.output is not None:
            write_dossier(args.output, dossier)
        else:
            check_dossier(args.check, dossier)
    except (DossierError, FileExistsError, OSError) as exc:
        print(f"release dossier error: {exc}", file=sys.stderr)
        return 2
    print(
        _canonical_json_bytes(
            {
                "blockers": dossier["blockers"],
                "release_ready": dossier["release_ready"],
                "release_subjects_sha256": dossier["release_subjects_sha256"],
                "schema_version": dossier["schema_version"],
            }
        ).decode("utf-8"),
        end="",
    )
    return 0 if dossier["release_ready"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
