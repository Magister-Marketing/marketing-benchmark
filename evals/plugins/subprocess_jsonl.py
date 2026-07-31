"""Reference adapter for any local agent that speaks a small JSONL contract."""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from evals.runner.adapters.base import (
    AttemptRequest,
    AttemptResult,
    SettingsCapabilities,
    TargetInfo,
)
from evals.runner.evidence import prepare_owned_directory, redact
from evals.runner.events import AgentEvent


class SubprocessJsonlAdapter:
    """Execute an operator-configured command without invoking a shell.

    The command receives one JSON request on stdin. It writes zero or more
    ``{"type":"event","event":...}`` lines followed by exactly one
    ``{"type":"result",...}`` line. This makes custom agents portable without
    granting manifests arbitrary code-import or command execution.
    """

    name = "subprocess-jsonl"
    version = "1"

    def supported_binding_kinds(self) -> tuple[str, ...]:
        return ("mcp_http", "mcp_stdio", "subprocess_jsonl")

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        repo_root: Path,
        run_id: str,
        deadline_seconds: int,
        workspace_root: Path | None = None,
        skill_roots: tuple[Path, ...] | None = None,
    ) -> None:
        if not command:
            raise ValueError("subprocess JSONL adapter command cannot be empty")
        self.command = command
        self.repo_root = repo_root.resolve()
        self.run_id = run_id
        self.deadline = time.monotonic() + deadline_seconds
        self.workspace_root = prepare_owned_directory(
            workspace_root
            if workspace_root
            else Path(tempfile.mkdtemp(prefix=f"agent-eval-subprocess-{run_id}-")),
            protected=(self.repo_root,),
        )
        self.skill_roots = skill_roots or (
            self.repo_root / "evals" / "fixtures" / "public" / "skills",
            self.repo_root / "skills",
        )
        self._closed = False

    def settings_capabilities(self) -> SettingsCapabilities:
        return SettingsCapabilities(
            adapter=self.name,
            settings={
                "reasoning_effort": {
                    "modes": ["set", "omit", "provider_default"],
                    "observable": False,
                    "translation": "request.settings",
                },
                "text_verbosity": {
                    "modes": ["set", "omit", "provider_default"],
                    "observable": False,
                    "translation": "request.settings",
                },
                "temperature": {
                    "modes": ["set", "omit", "provider_default"],
                    "observable": False,
                    "translation": "request.settings",
                },
                "max_output_tokens": {
                    "modes": ["set"],
                    "observable": False,
                    "translation": "request.settings",
                },
            },
        )

    def preflight(self, candidates: list[Any]) -> TargetInfo:
        executable = shutil.which(self.command[0])
        if not executable:
            raise RuntimeError(f"subprocess agent executable not found: {self.command[0]}")
        return TargetInfo(
            adapter=self.name,
            target_id=" ".join((executable, *self.command[1:])),
            dimensions={
                "executable": executable,
                "candidate_count": len(candidates),
                "protocol": "agent-eval-jsonl-v1",
            },
        )

    def _stage(self, request: AttemptRequest) -> Path:
        workspace = self.workspace_root / request.trial.attempt_id
        (workspace / "fixture").mkdir(parents=True)
        (workspace / "deliverables").mkdir()
        fixture_dirs = request.scenario.fixture_dirs or (
            (request.scenario.fixture_dir,) if request.scenario.fixture_dir else ()
        )
        for index, fixture_dir in enumerate(fixture_dirs):
            source = self.repo_root / fixture_dir
            target = workspace / "fixture"
            if len(fixture_dirs) > 1:
                target = target / f"{index + 1}-{source.name}"
            self._copy_regular_files(source, target)
        for skill in request.scenario.required_skill_reads:
            source = next(
                (
                    root / skill
                    for root in self.skill_roots
                    if (root / skill / "SKILL.md").is_file()
                    and not (root / skill / "SKILL.md").is_symlink()
                ),
                None,
            )
            if source is None:
                raise RuntimeError(f"required skill not found: {skill}")
            self._copy_regular_files(source, workspace / "skills" / skill)
        return workspace

    @staticmethod
    def _copy_regular_files(source: Path, target: Path) -> None:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)

    @staticmethod
    def _bindings(request: AttemptRequest) -> list[dict[str, Any]]:
        if request.environment is None:
            return []
        return [
            {
                "kind": binding.kind,
                "name": binding.name,
                "config": binding.config,
                "operations": binding.operations,
            }
            for binding in request.environment.bindings
        ]

    def _collect_artifacts(
        self, request: AttemptRequest, workspace: Path
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        root = workspace / "deliverables"
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(workspace).as_posix()
            media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            row: dict[str, Any] = {
                "path": relative,
                "bytes": path.stat().st_size,
                "media_type": media_type,
                "content_captured": False,
            }
            if path.stat().st_size <= 2_000_000 and not media_type.startswith(
                ("image/", "video/", "audio/")
            ):
                content = redact(path.read_text(errors="replace"))
                local = request.output_dir / "artifacts" / relative
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_text(str(content))
                row.update(
                    {
                        "bytes": len(str(content).encode()),
                        "local_path": str(local.resolve()),
                        "content_captured": True,
                    }
                )
            rows.append(row)
        return rows

    def run_attempt(self, request: AttemptRequest) -> AttemptResult:
        workspace = self.workspace_root / request.trial.attempt_id
        result = AttemptResult(
            status="infrastructure_error",
            events=[],
            dimensions={
                "adapter": self.name,
                "remote_root": str(workspace),
                "write_root": str(workspace / "deliverables"),
                "provider_cost_usd": 0.0,
            },
            error="subprocess attempt did not produce a result",
        )
        try:
            workspace = self._stage(request)
            payload = {
                "protocol": "agent-eval-jsonl-v1",
                "run_id": request.run_id,
                "attempt_id": request.trial.attempt_id,
                "candidate": {
                    "id": request.candidate.id,
                    "model": request.candidate.model,
                    "settings": request.candidate.requested_settings(),
                },
                "scenario": {
                    "id": request.scenario.id,
                    "prompt": request.scenario.prompt,
                    "required_skill_reads": list(request.scenario.required_skill_reads),
                    "allowed_tools": list(request.scenario.allowed_tools),
                    "allowed_operations": list(request.scenario.allowed_operations),
                    "forbidden_side_effects": list(
                        request.scenario.forbidden_side_effects
                    ),
                },
                "workspace": str(workspace),
                "tool_bindings": self._bindings(request),
            }
            timeout = min(
                request.scenario.timeout_seconds,
                max(1.0, self.deadline - time.monotonic()),
            )
            started = time.monotonic()
            process = subprocess.run(
                list(self.command),
                input=json.dumps(payload) + "\n",
                text=True,
                capture_output=True,
                cwd=workspace,
                env={**os.environ, "AGENT_EVAL_PROTOCOL": "agent-eval-jsonl-v1"},
                timeout=timeout,
                check=False,
            )
            events: list[AgentEvent] = []
            final: dict[str, Any] | None = None
            raw: list[dict[str, Any]] = []
            for line in process.stdout.splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    raw.append({"unparsed": line[:2000]})
                    continue
                if not isinstance(value, dict):
                    continue
                raw.append(value)
                if value.get("type") == "event" and isinstance(value.get("event"), dict):
                    events.append(AgentEvent(**value["event"]))
                elif value.get("type") == "result":
                    if final is not None:
                        raise RuntimeError("subprocess agent emitted more than one result")
                    final = value
            if final is None:
                raise RuntimeError(
                    f"subprocess agent emitted no result (exit={process.returncode}): "
                    + process.stderr.strip()[:500]
                )
            actual_model = final.get("actual_model")
            contaminated = not (
                isinstance(actual_model, str)
                and actual_model == request.candidate.model
            )
            status = str(final.get("status") or "completed")
            if status not in {
                "completed",
                "contaminated",
                "infrastructure_error",
            }:
                raise RuntimeError(f"subprocess agent returned invalid status: {status}")
            if contaminated:
                status = "contaminated"
            error = str(final.get("error")) if final.get("error") else None
            if process.returncode != 0:
                status = "infrastructure_error"
                detail = process.stderr.strip()[:500]
                error = f"subprocess agent exited {process.returncode}: {detail}"
            result = AttemptResult(
                status=status,
                events=events,
                response=str(final.get("response") or ""),
                messages=list(final.get("messages") or []),
                usage=list(final.get("usage") or []),
                artifacts=self._collect_artifacts(request, workspace),
                timings={
                    "completion_seconds": round(time.monotonic() - started, 3),
                    **dict(final.get("timings") or {}),
                },
                dimensions={
                    "adapter": self.name,
                    "remote_root": str(workspace),
                    "write_root": str(workspace / "deliverables"),
                    "provider_cost_usd": float(final.get("provider_cost_usd") or 0),
                    "actual_model": actual_model,
                    "contaminated": contaminated,
                    "exit_code": process.returncode,
                    "raw_events": raw,
                },
                settings={
                    "requested": request.candidate.requested_settings(),
                    "translated": dict(final.get("translated_settings") or {}),
                    "applied": dict(final.get("applied_settings") or {}),
                    "unobservable": list(final.get("unobservable_settings") or []),
                },
                error=error,
            )
        except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as exc:
            result.error = str(exc)
        finally:
            try:
                if workspace.exists():
                    shutil.rmtree(workspace)
                result.cleanup.append(
                    {
                        "name": "delete subprocess workspace",
                        "status": "pass",
                        "resource": {"path": str(workspace)},
                    }
                )
            except OSError as exc:
                result.cleanup.append(
                    {
                        "name": "delete subprocess workspace",
                        "status": "fail",
                        "resource": {"path": str(workspace)},
                        "error": str(exc),
                    }
                )
                result.status = "infrastructure_error"
                result.error = f"workspace cleanup failed: {exc}"
        return result

    def close(self) -> list[dict[str, Any]]:
        if self._closed:
            return []
        self._closed = True
        try:
            if self.workspace_root.exists():
                shutil.rmtree(self.workspace_root)
            return [{"name": "delete subprocess run root", "status": "pass"}]
        except OSError as exc:
            return [
                {
                    "name": "delete subprocess run root",
                    "status": "fail",
                    "error": str(exc),
                }
            ]
