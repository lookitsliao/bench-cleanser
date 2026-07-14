"""Small shared I/O helpers for verification command-line tools."""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
from typing import Any, TextIO


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r} is not allowed")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build an object while rejecting ambiguous duplicate member names."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def strict_json_load(stream: TextIO) -> Any:
    """Decode unambiguous standard JSON from a text stream."""

    return json.load(
        stream,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )


def strict_json_loads(value: str) -> Any:
    """Decode unambiguous standard JSON text."""

    return json.loads(
        value,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )


def strict_json_dumps(value: Any, *, indent: int | None = None) -> str:
    """Encode interoperable JSON with deterministic keys and no NaN extensions."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        separators=None if indent is not None else (",", ":"),
        sort_keys=True,
    )


def atomic_write(path: pathlib.Path, content: str) -> None:
    """Atomically and durably replace *path* with UTF-8 text.

    The temporary file is flushed before replacement and the containing
    directory is flushed afterwards.  The latter makes the rename durable
    across a crash on filesystems that implement directory ``fsync``.
    """

    if not isinstance(content, str):
        raise TypeError("atomic_write content must be text")
    temporary: pathlib.Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = pathlib.Path(handle.name)
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Preserve the original write/replace failure. A cleanup
                # failure must not hide the reason the requested output failed.
                pass
        raise
