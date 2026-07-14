"""Reference-free candidate manifest construction and command-line interface."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from bench_cleanser import __version__
from bench_cleanser.repo_manager import validate_relative_file_path
from bench_cleanser.verification._io import atomic_write, strict_json_dumps
from bench_cleanser.verification.models import (
    LifecycleStage,
    RiskProfile,
    ValidityManifest,
)

RISK_PROFILE_VERSION = "reference-free-v1"

_DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_HUNK_HEADER_RE = re.compile(
    r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@(?: .*)?$"
)
_GIT_FILE_MODE_RE = re.compile(r"[0-7]{6}")
_GIT_INDEX_RE = re.compile(
    r"^index (?P<old>[0-9a-f]{7,64})\.\.(?P<new>[0-9a-f]{7,64})"
    r"(?: (?P<mode>[0-7]{6}))?$"
)
# Git object IDs hash the object header together with the content.  Derive this
# public protocol constant rather than embedding a secret-shaped hex literal in
# release artifacts.
_EMPTY_GIT_BLOB_SHA1 = hashlib.sha1(
    b"blob 0\0", usedforsecurity=False
).hexdigest()
_LANGUAGE_BY_SUFFIX = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".cxx": "cpp",
    ".go": "go",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".m": "objective-c",
    ".mm": "objective-cpp",
    ".php": "php",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".sql": "sql",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "typescript",
}
_COMPILED_LANGUAGES = {
    "c",
    "cpp",
    "csharp",
    "go",
    "java",
    "kotlin",
    "objective-c",
    "objective-cpp",
    "rust",
    "scala",
    "swift",
}
_NATIVE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".m", ".mm", ".rs"}
_DEPENDENCY_OR_BUILD_FILES = {
    "build.gradle",
    "build.gradle.kts",
    "cargo.lock",
    "cargo.toml",
    "cmakelists.txt",
    "composer.json",
    "composer.lock",
    "dockerfile",
    "gemfile",
    "gemfile.lock",
    "go.mod",
    "go.sum",
    "gradle.properties",
    "makefile",
    "meson.build",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "yarn.lock",
}
_SECURITY_RE = re.compile(
    r"\b(auth(?:entication|orization)?|credential|crypto|jwt|oauth|password|"
    r"permission|secret|security|token)\b",
    re.IGNORECASE,
)
_CONCURRENCY_RE = re.compile(
    r"\b(async|await|atomic|concurren\w*|deadlock|mutex|race|semaphore|thread\w*)\b",
    re.IGNORECASE,
)

_GENERATED_PROVENANCE_KEYS = {
    "candidate_patch_sha256",
    "changed_files_sha256",
    "risk_profile_version",
}
_PRIVILEGED_PROVENANCE_FRAGMENTS = {
    "adjudicat",
    "annotation",
    "answerkey",
    "executionresult",
    "failed",
    "futurecommit",
    "gold",
    "groundtruth",
    "hidden",
    "human",
    "label",
    "outcome",
    "passed",
    "refpatch",
    "refsolution",
    "reference",
    "result",
    "resolved",
    "resolution",
    "reward",
    "score",
    "success",
    "testresult",
    "truth",
    "verdict",
}


def _provenance_key_fingerprint(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", key.casefold())


def validate_deployable_provenance(
    provenance: Mapping[str, str],
    *,
    reject_reserved: bool = False,
) -> dict[str, str]:
    """Validate provenance that may accompany deployable router inputs.

    This intentionally rejects a broad family of answer-, outcome-, and
    reference-derived key names. Values are not interpreted, so callers must
    still avoid hiding privileged payloads behind misleading safe-looking keys.
    """

    if not provenance:
        raise ValueError("at least one provenance field is required")
    normalized: dict[str, str] = {}
    seen_fingerprints: set[str] = set()
    for key, value in provenance.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("provenance keys must be non-empty strings")
        if key != key.strip():
            raise ValueError(f"provenance key {key!r} has surrounding whitespace")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"provenance value for {key!r} must be a non-empty string")
        fingerprint = _provenance_key_fingerprint(key)
        if fingerprint in seen_fingerprints:
            raise ValueError(f"duplicate normalized provenance key {key!r}")
        seen_fingerprints.add(fingerprint)
        if reject_reserved and key.casefold() in _GENERATED_PROVENANCE_KEYS:
            raise ValueError(f"provenance key {key!r} is reserved")
        if key.casefold() not in _GENERATED_PROVENANCE_KEYS and any(
            fragment in fingerprint for fragment in _PRIVILEGED_PROVENANCE_FRAGMENTS
        ):
            raise ValueError(
                f"deployable provenance key {key!r} may encode privileged truth or outcome data"
            )
        normalized[key] = value
    return normalized


def _normalize_header_path(raw_path: str) -> str | None:
    path = raw_path.split("\t", 1)[0]
    if path == "/dev/null":
        return None
    if path.startswith('"') or path.endswith('"'):
        raise ValueError("quoted diff paths are not supported")
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return validate_relative_file_path(path)


@dataclass
class _DiffSection:
    diff_paths: tuple[str | None, str | None] | None = None
    old_path: str | None = None
    new_path: str | None = None
    old_header_seen: bool = False
    new_header_seen: bool = False
    hunk_seen: bool = False
    in_hunk: bool = False
    new_file_mode: str | None = None
    deleted_file_mode: str | None = None
    index_old: str | None = None
    index_new: str | None = None
    index_mode: str | None = None
    unknown_metadata_seen: bool = False


def _empty_file_metadata_path(section: _DiffSection) -> str | None:
    """Return a path only for an exact empty-file add/delete Git section."""

    if (
        section.diff_paths is None
        or section.old_header_seen
        or section.new_header_seen
        or section.hunk_seen
        or section.unknown_metadata_seen
        or section.index_old is None
        or section.index_new is None
        or section.index_mode is not None
        or (section.new_file_mode is None) == (section.deleted_file_mode is None)
    ):
        return None
    old_path, new_path = section.diff_paths
    if section.new_file_mode is not None:
        if (
            old_path is None
            or new_path is None
            or set(section.index_old) != {"0"}
            or not _EMPTY_GIT_BLOB_SHA1.startswith(section.index_new)
        ):
            return None
        return new_path
    if (
        old_path is None
        or new_path is None
        or not _EMPTY_GIT_BLOB_SHA1.startswith(section.index_old)
        or set(section.index_new) != {"0"}
    ):
        return None
    return old_path


def _finish_diff_section(
    section: _DiffSection,
    files: list[str],
    seen: set[str],
) -> None:
    empty_file_path = _empty_file_metadata_path(section)
    if empty_file_path is not None:
        if empty_file_path not in seen:
            seen.add(empty_file_path)
            files.append(empty_file_path)
        return
    if not section.old_header_seen or not section.new_header_seen:
        raise ValueError("unified diff section is missing ---/+++ file headers")
    if not section.hunk_seen:
        raise ValueError("unified diff section contains no hunks")
    if section.old_path is None and section.new_path is None:
        raise ValueError("unified diff section cannot map /dev/null to /dev/null")
    if section.diff_paths is not None:
        diff_old, diff_new = section.diff_paths
        if section.old_path is not None and section.old_path != diff_old:
            raise ValueError("--- header path contradicts diff --git path")
        if section.new_path is not None and section.new_path != diff_new:
            raise ValueError("+++ header path contradicts diff --git path")
    for path in (section.old_path, section.new_path):
        if path is not None and path not in seen:
            seen.add(path)
            files.append(path)


def _parse_unified_diff(patch: str) -> tuple[list[str], str, int]:
    """Parse file headers and changed lines with explicit section/hunk state."""

    files: list[str] = []
    seen: set[str] = set()
    changed: list[str] = []
    section: _DiffSection | None = None

    for line_number, raw_line in enumerate(patch.splitlines(), 1):
        if raw_line.startswith("diff --git"):
            match = _DIFF_GIT_RE.fullmatch(raw_line)
            if match is None:
                raise ValueError(f"line {line_number}: unsupported diff --git header")
            if section is not None:
                _finish_diff_section(section, files, seen)
            section = _DiffSection(
                diff_paths=(
                    _normalize_header_path(f"a/{match.group(1)}"),
                    _normalize_header_path(f"b/{match.group(2)}"),
                )
            )
            continue

        if section is None:
            if raw_line.startswith("--- "):
                section = _DiffSection(
                    old_path=_normalize_header_path(raw_line[4:]),
                    old_header_seen=True,
                )
            # Mail headers and other preamble are ignored until the first
            # unambiguous diff section begins.
            continue

        if not section.in_hunk:
            if raw_line.startswith("new file mode "):
                mode = raw_line.removeprefix("new file mode ")
                if (
                    section.new_file_mode is not None
                    or section.deleted_file_mode is not None
                    or _GIT_FILE_MODE_RE.fullmatch(mode) is None
                ):
                    raise ValueError(f"line {line_number}: malformed new file mode")
                section.new_file_mode = mode
                continue
            if raw_line.startswith("deleted file mode "):
                mode = raw_line.removeprefix("deleted file mode ")
                if (
                    section.deleted_file_mode is not None
                    or section.new_file_mode is not None
                    or _GIT_FILE_MODE_RE.fullmatch(mode) is None
                ):
                    raise ValueError(f"line {line_number}: malformed deleted file mode")
                section.deleted_file_mode = mode
                continue
            if raw_line.startswith("index "):
                index_match = _GIT_INDEX_RE.fullmatch(raw_line)
                if (
                    index_match is None
                    or section.index_old is not None
                    or section.index_new is not None
                ):
                    raise ValueError(f"line {line_number}: malformed or duplicate index")
                section.index_old = index_match.group("old")
                section.index_new = index_match.group("new")
                section.index_mode = index_match.group("mode")
                continue
            if raw_line.startswith("--- "):
                if section.old_header_seen:
                    raise ValueError(f"line {line_number}: duplicate --- header")
                section.old_path = _normalize_header_path(raw_line[4:])
                section.old_header_seen = True
                continue
            if raw_line.startswith("+++ "):
                if not section.old_header_seen or section.new_header_seen:
                    raise ValueError(f"line {line_number}: misplaced +++ header")
                section.new_path = _normalize_header_path(raw_line[4:])
                section.new_header_seen = True
                continue
            if raw_line.startswith("@@"):
                if not section.old_header_seen or not section.new_header_seen:
                    raise ValueError(f"line {line_number}: hunk appears before file headers")
                if _HUNK_HEADER_RE.fullmatch(raw_line) is None:
                    raise ValueError(f"line {line_number}: malformed unified-diff hunk header")
                section.hunk_seen = True
                section.in_hunk = True
                continue
            if section.old_header_seen:
                raise ValueError(f"line {line_number}: expected +++ header or hunk")
            # Git metadata (index, modes, rename markers) is allowed before
            # the paired file headers.
            if raw_line:
                section.unknown_metadata_seen = True
            continue

        if raw_line.startswith("@@"):
            if _HUNK_HEADER_RE.fullmatch(raw_line) is None:
                raise ValueError(f"line {line_number}: malformed unified-diff hunk header")
            section.hunk_seen = True
            continue
        if raw_line == r"\ No newline at end of file":
            continue
        if raw_line.startswith(("+", "-")):
            changed.append(raw_line[1:])
            continue
        if raw_line.startswith(" "):
            continue
        raise ValueError(f"line {line_number}: malformed unified-diff hunk line")

    if section is not None:
        _finish_diff_section(section, files, seen)
    return files, "\n".join(changed), len(changed)


def _infer_language(files: list[str]) -> str:
    languages = {
        language
        for path in files
        if (language := _LANGUAGE_BY_SUFFIX.get(pathlib.PurePosixPath(path).suffix.lower()))
    }
    if not languages:
        return "unknown"
    if len(languages) > 1:
        return "mixed"
    return next(iter(languages))


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    parts = pathlib.PurePosixPath(lowered).parts
    name = parts[-1]
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith(("_test.py", "_test.go"))
        or ".test." in name
        or ".spec." in name
    )


def _touches_dependency_or_build(path: str) -> bool:
    lowered = path.lower()
    name = pathlib.PurePosixPath(lowered).name
    return (
        name in _DEPENDENCY_OR_BUILD_FILES
        or name.endswith((".lock", ".gradle", ".gradle.kts"))
        or lowered.startswith(".github/workflows/")
        or "/.github/workflows/" in lowered
    )


def _touches_schema_or_migration(path: str) -> bool:
    lowered = path.lower()
    parts = pathlib.PurePosixPath(lowered).parts
    name = parts[-1]
    return (
        name.endswith(".sql")
        or any(part in {"migration", "migrations", "schema", "schemas"} for part in parts)
        or "alembic" in parts
        or name.startswith("schema.")
    )


def build_candidate_manifest(
    *,
    instance_id: str,
    candidate_patch: str,
    lifecycle_stage: LifecycleStage,
    provenance: Mapping[str, str],
    language: str | None = None,
    generated_tests: bool = False,
    targeted_execution_available: bool = True,
    full_execution_available: bool = True,
    oracle_hardening_available: bool = False,
) -> ValidityManifest:
    """Build a deployable pre-execution manifest from a candidate patch only.

    No reference patch, hidden test, future commit, execution result, or model
    verdict is accepted by this interface. Such curator-only information must
    be added later as explicitly privileged evidence, never as router features.
    """

    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("instance_id is required")
    if not isinstance(candidate_patch, str):
        raise ValueError("candidate_patch must be text")
    if not isinstance(lifecycle_stage, LifecycleStage):
        raise ValueError("lifecycle_stage must be a LifecycleStage")
    normalized_provenance = validate_deployable_provenance(
        provenance,
        reject_reserved=True,
    )

    files, changed_source, lines_changed = _parse_unified_diff(candidate_patch)
    if candidate_patch.strip() and not files:
        raise ValueError("non-empty candidate patch has no supported diff file headers")
    inferred_language = _infer_language(files)
    if language is not None and not isinstance(language, str):
        raise ValueError("language override must be a string")
    selected_language = language.strip().lower() if language is not None else inferred_language
    if not selected_language:
        raise ValueError("language override cannot be empty")

    suffixes = {
        pathlib.PurePosixPath(path).suffix.lower()
        for path in files
    }
    path_text = "\n".join(files)
    patch_sha256 = hashlib.sha256(candidate_patch.encode("utf-8")).hexdigest()
    changed_files_sha256 = hashlib.sha256(
        "\n".join(sorted(files)).encode("utf-8")
    ).hexdigest()
    normalized_provenance.update({
        "candidate_patch_sha256": patch_sha256,
        "changed_files_sha256": changed_files_sha256,
        "risk_profile_version": RISK_PROFILE_VERSION,
    })

    return ValidityManifest(
        instance_id=instance_id,
        candidate_id=f"sha256:{patch_sha256}",
        lifecycle_stage=lifecycle_stage,
        risk_profile=RiskProfile(
            language=selected_language,
            files_changed=len(files),
            lines_changed=lines_changed,
            compiled_language=(
                selected_language in _COMPILED_LANGUAGES
                or any(
                    language_name in _COMPILED_LANGUAGES
                    for path in files
                    if (
                        language_name := _LANGUAGE_BY_SUFFIX.get(
                            pathlib.PurePosixPath(path).suffix.lower()
                        )
                    )
                )
            ),
            native_dependencies=(
                bool(suffixes & _NATIVE_SUFFIXES)
                or any(token in path_text.lower() for token in ("/ffi/", "/native/"))
            ),
            touches_dependency_or_build_files=any(
                _touches_dependency_or_build(path) for path in files
            ),
            touches_schema_or_migration=any(
                _touches_schema_or_migration(path) for path in files
            ),
            touches_security_or_auth=bool(
                _SECURITY_RE.search(path_text) or _SECURITY_RE.search(changed_source)
            ),
            touches_concurrency=bool(
                _CONCURRENCY_RE.search(path_text) or _CONCURRENCY_RE.search(changed_source)
            ),
            touches_tests=any(_is_test_path(path) for path in files),
            generated_tests=generated_tests,
            targeted_execution_available=targeted_execution_available,
            full_execution_available=full_execution_available,
            oracle_hardening_available=oracle_hardening_available,
        ),
        provenance=normalized_provenance,
    )


def _provenance(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"invalid provenance {item!r}; expected KEY=VALUE")
        key, value = item.split("=", 1)
        if not key.strip() or not value:
            raise ValueError(f"invalid provenance {item!r}; expected non-empty KEY=VALUE")
        if key in result:
            raise ValueError(f"duplicate provenance key {key!r}")
        result[key] = value
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench-cleanser-manifest",
        description="Build a reference-free pre-execution validity manifest from a patch",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("instance_id")
    parser.add_argument("patch", help="Candidate unified-diff file, or '-' for stdin")
    parser.add_argument(
        "--stage",
        required=True,
        choices=[stage.value for stage in LifecycleStage],
    )
    parser.add_argument(
        "--provenance",
        action="append",
        required=True,
        metavar="KEY=VALUE",
        help="Immutable provenance field; repeat for multiple fields",
    )
    parser.add_argument("--language", help="Override inferred candidate language")
    parser.add_argument("--generated-tests", action="store_true")
    parser.add_argument("--no-targeted-execution", action="store_true")
    parser.add_argument("--no-full-execution", action="store_true")
    parser.add_argument("--oracle-hardening-available", action="store_true")
    parser.add_argument("--output", help="Write manifest JSON here instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if args.patch == "-":
            candidate_patch = sys.stdin.read()
        else:
            candidate_patch = pathlib.Path(args.patch).read_text(encoding="utf-8")
        manifest = build_candidate_manifest(
            instance_id=args.instance_id,
            candidate_patch=candidate_patch,
            lifecycle_stage=LifecycleStage(args.stage),
            provenance=_provenance(args.provenance),
            language=args.language,
            generated_tests=args.generated_tests,
            targeted_execution_available=not args.no_targeted_execution,
            full_execution_available=not args.no_full_execution,
            oracle_hardening_available=args.oracle_hardening_available,
        )
        rendered = strict_json_dumps(manifest.to_dict(), indent=2) + "\n"
        if args.output:
            atomic_write(pathlib.Path(args.output), rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, TypeError, ValueError) as exc:
        raise SystemExit(f"manifest construction failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - console entry point
    main()
