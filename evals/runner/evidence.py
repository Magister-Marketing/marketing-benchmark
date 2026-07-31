"""Safe evidence serialization, hashing, and artifact containment."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


_SECRET_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "credential",
    "jwt",
    "password",
    "secret",
    "api_key",
    "service_role",
)
_INLINE_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
)
_MAX_EVIDENCE_STRING = 200_000


def _secret_key(value: Any) -> bool:
    normalized = str(value).lower().replace("-", "_")
    return (
        normalized in {"key", "apikey", "token"}
        or normalized.endswith(("_key", "_token"))
        or "_token_" in normalized
        or any(fragment in normalized for fragment in _SECRET_KEY_FRAGMENTS)
    )


def _safe_string(value: str) -> str:
    result = value
    for pattern in _INLINE_SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    if len(result) > _MAX_EVIDENCE_STRING:
        omitted = len(result) - _MAX_EVIDENCE_STRING
        result = result[:_MAX_EVIDENCE_STRING] + f"\n[TRUNCATED {omitted} CHARACTERS]"
    return result


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _secret_key(key)
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _safe_string(value)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def contained_path(root: Path, relative: str) -> Path:
    """Resolve a relative artifact path and reject traversal/symlink escape."""
    if not relative or Path(relative).is_absolute():
        raise ValueError("artifact path must be non-empty and relative")
    root_resolved = root.resolve()
    target = (root_resolved / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes attempt directory: {relative}") from exc
    return target


def prepare_owned_directory(path: Path, *, protected: Iterable[Path] = ()) -> Path:
    """Claim one empty directory that a runner may later remove recursively."""

    if path.is_symlink():
        raise ValueError(f"owned directory cannot be a symlink: {path}")
    resolved = path.expanduser().resolve()
    protected_paths = {
        Path(resolved.anchor).resolve(),
        Path.home().resolve(),
        *(value.expanduser().resolve() for value in protected),
    }
    if resolved in protected_paths:
        raise ValueError(f"refusing broad owned directory: {resolved}")
    if resolved.exists():
        if not resolved.is_dir():
            raise ValueError(f"owned directory path is not a directory: {resolved}")
        if any(resolved.iterdir()):
            raise ValueError(f"owned directory must be empty: {resolved}")
    else:
        resolved.mkdir(parents=True)
    return resolved


def inventory_files(root: Path) -> list[dict[str, Any]]:
    """Inventory regular files without following symlinks out of the root."""
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for directory, dir_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        dir_names[:] = [
            name for name in dir_names if not (directory_path / name).is_symlink()
        ]
        for name in sorted(file_names):
            path = directory_path / name
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root.resolve()).as_posix()
            except ValueError as exc:
                raise ValueError(f"artifact escaped attempt directory: {path}") from exc
            rows.append(
                {
                    "path": relative,
                    "bytes": resolved.stat().st_size,
                    "sha256": sha256_file(resolved),
                }
            )
    return sorted(rows, key=lambda row: row["path"])


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(value), indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(redact(row), sort_keys=True) + "\n")


def append_jsonl(path: Path, row: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(redact(row), sort_keys=True) + "\n")
