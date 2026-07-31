#!/usr/bin/env python3
"""Validate or copy the standalone eval-runner release-candidate boundary."""

from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "evals" / "open_source" / "PACKAGE_MANIFEST.json"


def _manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST_PATH.read_text())
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("open-source package manifest must use schema_version 1")
    return value


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def public_files(manifest: dict[str, Any]) -> tuple[Path, ...]:
    includes = manifest.get("include") or []
    excludes = manifest.get("exclude") or []
    if not all(isinstance(value, str) for value in [*includes, *excludes]):
        raise ValueError("package include/exclude entries must be strings")
    selected: set[Path] = set()
    empty_patterns: list[str] = []
    for pattern in includes:
        matches = [path for path in REPO_ROOT.glob(pattern) if path.is_file()]
        if not matches:
            empty_patterns.append(pattern)
        selected.update(matches)
    if empty_patterns:
        raise ValueError("package patterns matched no files: " + ", ".join(empty_patterns))
    files = tuple(
        sorted(
            path
            for path in selected
            if not _matches(path.relative_to(REPO_ROOT).as_posix(), excludes)
        )
    )
    if not files:
        raise ValueError("package boundary contains no files")
    return files


def validate_boundary(
    manifest: dict[str, Any], files: tuple[Path, ...]
) -> dict[str, Any]:
    forbidden = [str(value).casefold() for value in manifest.get("forbidden_path_fragments") or []]
    forbidden_content = [
        str(value).casefold()
        for value in manifest.get("forbidden_content_fragments") or []
    ]
    violations: list[str] = []
    content_violations: list[str] = []
    for path in files:
        relative = path.relative_to(REPO_ROOT).as_posix()
        lowered = relative.casefold()
        if any(fragment in lowered for fragment in forbidden):
            violations.append(relative)
        if relative != "evals/open_source/PACKAGE_MANIFEST.json":
            try:
                content = path.read_text(errors="replace").casefold()
            except OSError:
                content = ""
            matched = [value for value in forbidden_content if value in content]
            if matched:
                content_violations.append(f"{relative}: {matched}")
    required = {
        "evals/cli.py",
        "evals/runner/engine.py",
        "evals/runner/conformance.py",
        "evals/plugins/replay_mcp/server.py",
        "evals/plugins/subprocess_jsonl.py",
        "evals/fixtures/public/integrations/ga4/conversion-drop-v1/oracle.json",
    }
    relative_files = {path.relative_to(REPO_ROOT).as_posix() for path in files}
    missing = sorted(required - relative_files)
    if violations or content_violations or missing:
        raise ValueError(
            "invalid public boundary; "
            f"forbidden_paths={violations}, forbidden_content={content_violations}, "
            f"missing={missing}"
        )
    return {
        "status": "ok",
        "schema_version": manifest["schema_version"],
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "private_paths_included": violations,
        "private_content_included": content_violations,
    }


def export(files: tuple[Path, ...], output: Path) -> None:
    resolved = output.expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError("export output must be outside the source repository")
    if resolved.exists() and any(resolved.iterdir()):
        raise ValueError("export output must not exist or must be empty")
    resolved.mkdir(parents=True, exist_ok=True)
    for source in files:
        relative = source.relative_to(REPO_ROOT)
        destination = resolved / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    template = resolved / "evals" / "open_source" / "pyproject.toml.template"
    if template.is_file():
        shutil.copy2(template, resolved / "pyproject.toml")
    readme = resolved / "evals" / "open_source" / "README.md"
    if readme.is_file():
        shutil.copy2(readme, resolved / "README.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        manifest = _manifest()
        files = public_files(manifest)
        summary = validate_boundary(manifest, files)
        if args.output is not None:
            export(files, args.output)
            summary["output"] = str(args.output.expanduser().resolve())
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
