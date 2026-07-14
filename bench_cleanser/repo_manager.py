"""Repository cloning and caching for code visitation.

Manages shallow git clones of SWE-bench source repos, cached on disk
so that repeated pipeline runs reuse existing checkouts.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import shutil
import subprocess
import threading
from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Per-repo lock to prevent concurrent clone of the same repo+commit.
_clone_locks: dict[str, threading.Lock] = {}
_lock_guard = threading.Lock()

_REPO_IDENTIFIER_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}"
)
_FULL_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}")


def _get_lock(key: str) -> threading.Lock:
    with _lock_guard:
        if key not in _clone_locks:
            _clone_locks[key] = threading.Lock()
        return _clone_locks[key]


def validate_repo_identifier(repo: str) -> str:
    """Validate and return a GitHub ``owner/name`` repository identifier.

    Dataset fields are untrusted input.  Accepting URL-like values or path
    components here would let them influence both the clone URL and cache
    layout, so the accepted grammar is intentionally narrow.
    """
    if not isinstance(repo, str) or not _REPO_IDENTIFIER_RE.fullmatch(repo):
        raise ValueError(f"Invalid repository identifier: {repo!r}")
    return repo


def validate_full_commit_hash(base_commit: str) -> str:
    """Validate and normalize a full 40-character Git commit hash."""
    if not isinstance(base_commit, str) or not _FULL_COMMIT_RE.fullmatch(base_commit):
        raise ValueError(
            "base_commit must be a full 40-character hexadecimal Git commit hash"
        )
    return base_commit.lower()


def validate_relative_file_path(file_path: str) -> str:
    """Validate a repository-relative POSIX file path.

    Unified diffs use POSIX paths on every supported host.  Backslashes,
    absolute paths, empty components and dot traversal are rejected instead
    of being normalized, keeping security decisions explicit and auditable.
    """
    if not isinstance(file_path, str) or not file_path or "\x00" in file_path:
        raise ValueError(f"Invalid repository file path: {file_path!r}")
    if "\\" in file_path or file_path.startswith("/") or re.match(r"^[A-Za-z]:", file_path):
        raise ValueError(f"Repository file path must be relative: {file_path!r}")
    components = file_path.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise ValueError(f"Repository file path contains traversal: {file_path!r}")
    return file_path


def _repo_slug(repo: str) -> str:
    """Convert ``owner/name`` to ``owner__name`` for filesystem use."""
    return validate_repo_identifier(repo).replace("/", "__")


def _confined_path(root: pathlib.Path, *parts: str) -> pathlib.Path:
    """Resolve a child path and require it to remain below *root*."""
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts).resolve(strict=False)
    if not candidate.is_relative_to(resolved_root) or candidate == resolved_root:
        raise ValueError(f"Path escapes configured root {resolved_root}: {candidate}")
    return candidate


def resolve_confined_repo_path(
    repo_path: pathlib.Path,
    file_path: str,
) -> pathlib.Path:
    """Resolve a repository-relative path without allowing checkout escape.

    Resolving the candidate (rather than only checking its lexical form) is
    important because a valid-looking path can traverse a symlink whose
    target is outside the checkout.  The returned path may not exist; callers
    can then distinguish missing files and directories in the usual way.
    """
    relative_path = validate_relative_file_path(file_path)
    try:
        repo_root = pathlib.Path(repo_path).resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Repository checkout does not exist: {repo_path}") from exc

    candidate = (repo_root / relative_path).resolve(strict=False)
    if not candidate.is_relative_to(repo_root) or candidate == repo_root:
        raise ValueError(f"Repository path escapes checkout: {file_path!r}")
    return candidate


def resolve_confined_repo_file(
    repo_path: pathlib.Path,
    file_path: str,
) -> pathlib.Path:
    """Resolve a repository-relative file path beneath *repo_path*.

    This named file helper is the common boundary for every source read.  It
    intentionally does not require the file to exist so callers can preserve
    their existing missing-file behavior without weakening confinement.
    """
    return resolve_confined_repo_path(repo_path, file_path)


class RepoManager:
    """Clone and cache git repositories for code visitation.

    Cloned repos are stored under ``cache_dir/<repo_slug>/<commit[:12]>/``.
    A marker file ``.clone_complete`` indicates that the clone succeeded and
    can be reused.
    """

    def __init__(
        self,
        cache_dir: str = ".cache/repos",
        clone_timeout: int = 300,
    ) -> None:
        self._cache_dir = pathlib.Path(cache_dir).expanduser()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = self._cache_dir.resolve()
        self._timeout = clone_timeout

    # Public API

    def get_repo_path(self, repo: str, base_commit: str) -> pathlib.Path | None:
        """Return the local path for *repo* at *base_commit*, cloning if needed.

        Returns ``None`` if cloning fails.
        """
        repo = validate_repo_identifier(repo)
        base_commit = validate_full_commit_hash(base_commit)
        slug = _repo_slug(repo)
        dest = _confined_path(self._cache_dir, slug, base_commit[:12])
        if dest.is_symlink():
            raise ValueError(f"Refusing symlinked repository cache path: {dest}")
        marker = dest / ".clone_complete"

        if marker.exists():
            logger.debug("Reusing cached clone: %s", dest)
            return dest

        lock = _get_lock(f"{slug}/{base_commit}")
        with lock:
            # Double-check after acquiring lock
            if marker.exists():
                return dest

            return self._clone(repo, base_commit, dest, marker)

    def get_file(self, repo_path: pathlib.Path, file_path: str) -> str | None:
        """Read a file from a cloned repo.  Returns ``None`` if not found."""
        try:
            repo_root = pathlib.Path(repo_path).resolve(strict=True)
        except OSError:
            return None
        if not repo_root.is_relative_to(self._cache_dir):
            raise ValueError(f"Repository path is outside configured cache root: {repo_root}")
        full = resolve_confined_repo_file(repo_root, file_path)
        if not full.is_file():
            return None
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", full, exc)
            return None

    def get_files_for_task(
        self,
        repo_path: pathlib.Path,
        file_paths: Sequence[str],
    ) -> dict[str, str]:
        """Read multiple files from a cloned repo.  Skips missing files."""
        result: dict[str, str] = {}
        for fp in file_paths:
            content = self.get_file(repo_path, fp)
            if content is not None:
                result[fp] = content
        return result

    # Batch pre-clone — call before pipeline processing.

    def pre_clone_repos(
        self,
        tasks: list,
    ) -> dict[str, pathlib.Path | None]:
        """Clone all unique repos needed by *tasks*.

        *tasks* may be a list of ``TaskRecord`` objects (with ``.repo`` and
        ``.base_commit`` attributes) or a list of ``(repo, base_commit)``
        tuples.

        Returns a mapping from ``repo/commit`` to local path (or ``None``).
        """
        unique: dict[str, tuple[str, str]] = {}
        for item in tasks:
            if isinstance(item, tuple):
                repo, commit = item
            else:
                repo, commit = item.repo, item.base_commit
            try:
                repo = validate_repo_identifier(repo)
                commit = validate_full_commit_hash(commit)
            except ValueError as exc:
                logger.error("Skipping invalid repository checkout metadata: %s", exc)
                continue
            key = f"{repo}/{commit}"
            if key not in unique:
                unique[key] = (repo, commit)

        logger.info(
            "Pre-cloning %d unique repo checkouts for %d tasks",
            len(unique),
            len(tasks),
        )

        results: dict[str, pathlib.Path | None] = {}
        for key, (repo, commit) in unique.items():
            path = self.get_repo_path(repo, commit)
            results[key] = path
            if path is None:
                logger.warning("Failed to clone %s @ %s", repo, commit[:12])
            else:
                logger.info("Ready: %s @ %s -> %s", repo, commit[:12], path)

        return results

    # Internal

    def _clone(
        self,
        repo: str,
        base_commit: str,
        dest: pathlib.Path,
        marker: pathlib.Path,
    ) -> pathlib.Path | None:
        """Perform the actual shallow clone + checkout."""
        repo = validate_repo_identifier(repo)
        base_commit = validate_full_commit_hash(base_commit)
        dest = dest.resolve(strict=False)
        if not dest.is_relative_to(self._cache_dir) or dest == self._cache_dir:
            raise ValueError(f"Clone destination escapes configured cache root: {dest}")
        url = f"https://github.com/{repo}.git"
        dest.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: init + configure remote idempotently
            self._run_git(["git", "init"], cwd=dest)
            remotes = self._run_git(["git", "remote"], cwd=dest).stdout.split()
            if "origin" in remotes:
                self._run_git(["git", "remote", "set-url", "origin", url], cwd=dest)
            else:
                self._run_git(["git", "remote", "add", "origin", url], cwd=dest)

            # Step 2: fetch the specific commit (shallow)
            self._run_git(
                ["git", "fetch", "--depth=1", "origin", base_commit],
                cwd=dest,
                timeout=self._timeout,
            )

            # Step 3: checkout
            self._run_git(
                ["git", "checkout", "FETCH_HEAD"],
                cwd=dest,
            )

            # Mark success
            marker.write_text("ok", encoding="utf-8")
            logger.info("Cloned %s @ %s -> %s", repo, base_commit[:12], dest)
            return dest

        except (subprocess.SubprocessError, OSError) as exc:
            logger.error("Clone failed for %s @ %s: %s", repo, base_commit[:12], exc)
            try:
                if dest.exists():
                    shutil.rmtree(dest)
            except OSError as cleanup_exc:
                logger.warning("Failed to clean partial clone at %s: %s", dest, cleanup_exc)
            return None

    def _run_git(
        self,
        cmd: list[str],
        cwd: pathlib.Path,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command with logging."""
        effective_timeout = timeout or self._timeout
        resolved_cwd = cwd.resolve(strict=False)
        if not resolved_cwd.is_relative_to(self._cache_dir) or resolved_cwd == self._cache_dir:
            raise ValueError(f"Git working directory escapes configured cache root: {cwd}")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"  # never prompt for credentials

        logger.debug("Running: %s (cwd=%s)", " ".join(cmd), cwd)
        return subprocess.run(
            cmd,
            cwd=str(resolved_cwd),
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=True,
            env=env,
        )
