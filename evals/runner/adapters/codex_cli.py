"""Portable reference adapter for clean, non-interactive Codex CLI runs.

The adapter uses ``codex exec --json --ephemeral`` in an attempt-owned
workspace. User configuration, project rules, web search, interactive
approvals, and ambient MCP servers are disabled; only an attempt-scoped replay
MCP binding may be attached. Codex JSONL events are normalized into the same
evidence vocabulary used by the other adapters.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..evidence import redact
from ..events import AgentEvent
from ..schema import Candidate
from .base import AttemptRequest, AttemptResult, SettingsCapabilities, TargetInfo
from .claude_code import ClaudeCodeAdapter


_MODEL_PRICES_PER_MILLION = {
    "gpt-5.6-luna": {"input": 0.2, "cached_input": 0.02, "output": 1.2},
    "gpt-5.6-terra": {"input": 2.0, "cached_input": 0.2, "output": 12.0},
    "gpt-5.6-sol": {"input": 5.0, "cached_input": 0.5, "output": 30.0},
}
_READ_COMMAND = re.compile(
    r"\b(?:pwd|ls|find|fd|rg|grep|sed|cat|head|tail|wc|jq|stat|file|readFileSync)\b|\bgit\s+(?:diff|status|show)\b",
    re.IGNORECASE,
)
_WRITE_MARKERS = re.compile(
    r"(?:\s(?:>>?|2>>?)\s*['\"]?[A-Za-z_./]|\b(?:rm|mv|cp|mkdir|touch|tee|chmod|chown|writeFileSync|write_text|write_bytes|git\s+(?:add|commit|checkout|switch|reset|clean))\b)",
    re.IGNORECASE,
)
_DELETE_COMMAND = re.compile(
    r"\b(?:rm|rmdir)\b|\bgit\s+clean\b|\bgit\s+reset\s+--hard\b",
    re.IGNORECASE,
)
_WORKSPACE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:skills|fixture|deliverables)(?:/[A-Za-z0-9_.?@%+=:,/-]+)?)"
)
_PURE_COMPUTE_COMMAND = re.compile(r"\b(?:node|python3?|ruby|perl)\b", re.IGNORECASE)
_EXTERNAL_COMMAND = re.compile(
    r"\b(?:curl|wget|ssh|scp|sftp|nc|netcat|gh|brew|pip|uv|npm|pnpm|yarn)\b|"
    r"\bgit\s+(?:push|pull|fetch|clone)\b|https?://",
    re.IGNORECASE,
)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _model_id(candidate: Candidate) -> str:
    if not candidate.model.startswith("openai/"):
        raise ValueError(f"Codex CLI adapter cannot execute {candidate.model!r}")
    return candidate.model.removeprefix("openai/")


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_array(values: list[str]) -> str:
    return "[" + ",".join(_toml_string(value) for value in values) + "]"


def _toml_inline_string_table(values: dict[str, str]) -> str:
    return "{" + ",".join(
        f"{json.dumps(key)}={_toml_string(value)}"
        for key, value in sorted(values.items())
    ) + "}"


class CodexCliAdapter(ClaudeCodeAdapter):
    """Execute OpenAI candidates through the locally authenticated Codex CLI."""

    name = "codex-cli"
    version = "1"

    def __init__(self, *args: Any, cli: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            *args,
            cli=cli or os.environ.get("CODEX_EVAL_CLI") or "codex",
            **kwargs,
        )

    def supported_binding_kinds(self) -> tuple[str, ...]:
        return ("mcp_stdio",)

    def settings_capabilities(self) -> SettingsCapabilities:
        return SettingsCapabilities(
            adapter=self.name,
            settings={
                "reasoning_effort": {
                    "modes": ["set", "omit", "provider_default"],
                    "values": ["low", "medium", "high", "xhigh"],
                    "observable": True,
                    "translation": "model_reasoning_effort",
                },
                "text_verbosity": {
                    "modes": ["set", "omit", "provider_default"],
                    "values": ["low", "medium", "high"],
                    "observable": True,
                    "translation": "model_verbosity",
                },
                "temperature": {
                    "modes": ["omit", "provider_default"],
                    "observable": True,
                    "translation": "not sent",
                },
                "max_output_tokens": {
                    "modes": ["provider_default"],
                    "observable": True,
                    "translation": "not overridden; Codex CLI/provider default",
                },
            },
        )

    def preflight(self, candidates: list[Candidate]) -> TargetInfo:
        executable = shutil.which(self.cli)
        if not executable:
            raise RuntimeError(
                f"Codex CLI {self.cli!r} was not found on PATH; install it or set CODEX_EVAL_CLI"
            )
        version = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout.strip()
        models = sorted({_model_id(candidate) for candidate in candidates})
        unsupported_models = sorted(set(models) - set(_MODEL_PRICES_PER_MILLION))
        if unsupported_models:
            raise RuntimeError(
                "Codex CLI adapter has no reviewed pricing boundary for: "
                + ", ".join(unsupported_models)
            )
        max_effort = [
            candidate.id for candidate in candidates if candidate.effort == "max"
        ]
        if max_effort:
            raise RuntimeError(
                "codex exec does not document reasoning effort 'max'; use xhigh or lower: "
                + ", ".join(max_effort)
            )
        return TargetInfo(
            adapter=self.name,
            target_id=f"{executable} ({version or 'unknown version'})",
            dimensions={
                "cli": executable,
                "cli_version": version,
                "models": models,
                "ephemeral": True,
                "user_config": "ignored",
                "rules": "ignored",
                "web_search": "disabled",
            },
        )

    def _command(self, request: AttemptRequest, prompt: str) -> list[str]:
        model = _model_id(request.candidate)
        command = [
            self.cli,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--model",
            model,
            "--color",
            "never",
            "-c",
            'approval_policy="never"',
            "-c",
            'web_search="disabled"',
            "-c",
            'shell_environment_policy.inherit="core"',
            "-c",
            "shell_environment_policy.ignore_default_excludes=false",
        ]
        if request.candidate.effort is not None:
            command.extend(
                [
                    "-c",
                    f"model_reasoning_effort={_toml_string(request.candidate.effort)}",
                ]
            )
        if request.candidate.verbosity is not None:
            command.extend(
                [
                    "-c",
                    f"model_verbosity={_toml_string(request.candidate.verbosity)}",
                ]
            )
        if request.environment is not None:
            for binding in request.environment.bindings:
                if binding.kind != "mcp_stdio":
                    raise RuntimeError(
                        f"Codex CLI cannot attach {binding.kind} binding {binding.name}"
                    )
                config = binding.config
                command_value = config.get("command")
                args_value = config.get("args") or []
                env_value = config.get("env") or {}
                if (
                    not isinstance(command_value, str)
                    or not isinstance(args_value, list)
                    or not all(isinstance(value, str) for value in args_value)
                    or not isinstance(env_value, dict)
                    or not all(
                        isinstance(key, str) and isinstance(value, str)
                        for key, value in env_value.items()
                    )
                ):
                    raise RuntimeError(f"invalid MCP stdio binding: {binding.name}")
                prefix = f"mcp_servers.{binding.name}"
                enabled_tools = sorted(
                    {
                        name
                        for name in binding.operations
                        if "__" not in name
                    }
                )
                command.extend(
                    [
                        "-c",
                        f"{prefix}.command={_toml_string(command_value)}",
                        "-c",
                        f"{prefix}.args={_toml_array(args_value)}",
                        "-c",
                        f"{prefix}.env={_toml_inline_string_table(env_value)}",
                        "-c",
                        f"{prefix}.required=true",
                        "-c",
                        f'{prefix}.default_tools_approval_mode="approve"',
                    ]
                )
                if enabled_tools:
                    command.extend(
                        [
                            "-c",
                            f"{prefix}.enabled_tools={_toml_array(enabled_tools)}",
                        ]
                    )
        command.extend(["--cd", ".", prompt])
        return command

    @staticmethod
    def _command_text(item: dict[str, Any]) -> str:
        command = item.get("command")
        if isinstance(command, list):
            return " ".join(str(value) for value in command)
        return str(command or "")

    @staticmethod
    def _command_tool(command: str) -> str:
        effect_text = re.sub(r"\b\d?>\s*/dev/null\b", "", command)
        if _EXTERNAL_COMMAND.search(effect_text) or _DELETE_COMMAND.search(
            effect_text
        ):
            return "bash"
        if _WRITE_MARKERS.search(effect_text):
            return "edit"
        if _READ_COMMAND.search(command):
            return "read"
        if _PURE_COMPUTE_COMMAND.search(command) and not _EXTERNAL_COMMAND.search(command):
            return "backend"
        return "bash"

    @staticmethod
    def _command_paths(command: str, workspace: Path) -> list[str]:
        normalized = command.replace(str(workspace), ".")
        paths: list[str] = []
        for match in _WORKSPACE_PATH.finditer(normalized):
            value = match.group(1).rstrip(".,:;")
            if value not in paths:
                paths.append(value)
        return paths

    @staticmethod
    def _skill_from_path(path: str) -> str | None:
        match = re.fullmatch(r"skills/([^/]+)/SKILL\.md", path)
        return match.group(1) if match else None

    def _skill_from_command(self, command: str, workspace: Path) -> str | None:
        if self._command_tool(command) != "read":
            return None
        normalized = command.replace(str(workspace), ".")
        for skill_dir in sorted((workspace / "skills").glob("*")):
            if not skill_dir.is_dir():
                continue
            relative = f"skills/{skill_dir.name}/SKILL.md"
            if relative in normalized:
                return skill_dir.name
        return None

    @staticmethod
    def _item_error(item: dict[str, Any]) -> bool:
        status = str(item.get("status") or "").casefold()
        exit_code = item.get("exit_code")
        return status in {"failed", "error"} or (
            isinstance(exit_code, int) and exit_code != 0
        )

    def _normalize_codex(
        self,
        raw_lines: list[str],
        workspace: Path,
        requested_model: str,
    ) -> tuple[list[AgentEvent], list[dict[str, Any]], dict[str, Any]]:
        events: list[AgentEvent] = []
        raw_events: list[dict[str, Any]] = []
        summary: dict[str, Any] = {
            "actual_model": requested_model,
            "response": "",
            "usage": {},
            "result_seen": False,
            "is_error": False,
        }
        sequence = 0
        started_items: dict[str, list[str]] = {}

        def emit(event_type: str, data: dict[str, Any], raw_type: str) -> None:
            nonlocal sequence
            sequence += 1
            events.append(
                AgentEvent(
                    sequence=sequence,
                    type=event_type,
                    timestamp=_now(),
                    data=data,
                    raw_type=raw_type,
                )
            )

        def start_item(item: dict[str, Any]) -> None:
            item_id = str(item.get("id") or f"item-{len(started_items) + 1}")
            if item_id in started_items:
                return
            item_type = str(item.get("type") or "")
            if item_type == "command_execution":
                command = self._command_text(item)
                tool_name = self._command_tool(command)
                if tool_name == "backend":
                    emit(
                        "backend.event",
                        {"subtype": "local_compute"},
                        "codex.item.started",
                    )
                    started_items[item_id] = []
                    return
                paths = self._command_paths(command, workspace) or ["."]
                call_ids: list[str] = []
                for index, path in enumerate(paths, start=1):
                    call_id = item_id if len(paths) == 1 else f"{item_id}:{index}"
                    call_ids.append(call_id)
                    payload = {
                        "name": tool_name,
                        "toolCallId": call_id,
                        "args": {"command": command, "path": path},
                    }
                    skill = self._skill_from_path(path)
                    if tool_name == "read" and skill:
                        payload.update({"name": "read", "skill": skill})
                        emit("skill.read", payload, "codex.item.started")
                    else:
                        emit("tool.started", payload, "codex.item.started")
                started_items[item_id] = call_ids
            elif item_type == "mcp_tool_call":
                server = str(item.get("server") or item.get("server_name") or "")
                tool = str(item.get("tool") or item.get("tool_name") or item.get("name") or "")
                name = f"mcp__{server}__{tool}" if server and tool else tool
                emit(
                    "tool.started",
                    {
                        "name": name,
                        "toolCallId": item_id,
                        "args": item.get("arguments") or item.get("input") or {},
                    },
                    "codex.item.started",
                )
                started_items[item_id] = [item_id]
            elif item_type == "web_search":
                emit(
                    "tool.started",
                    {
                        "name": "websearch",
                        "toolCallId": item_id,
                        "args": {"query": item.get("query")},
                    },
                    "codex.item.started",
                )
                started_items[item_id] = [item_id]

        def complete_item(item: dict[str, Any]) -> None:
            item_id = str(item.get("id") or f"item-{len(started_items) + 1}")
            item_type = str(item.get("type") or "")
            if item_type == "agent_message":
                text = str(item.get("text") or item.get("message") or "")
                if text:
                    summary["response"] = text
                    emit("message.delta", {"text": text}, "codex.item.completed")
                return
            if item_type in {"reasoning", "plan_update"}:
                emit("thinking.delta", {}, "codex.item.completed")
                return
            if item_type == "file_change":
                changes = item.get("changes") or []
                for index, change in enumerate(changes, start=1):
                    if not isinstance(change, dict):
                        continue
                    call_id = item_id if len(changes) == 1 else f"{item_id}:{index}"
                    path = str(change.get("path") or "")
                    emit(
                        "tool.started",
                        {
                            "name": "edit",
                            "toolCallId": call_id,
                            "args": {"path": path, "kind": change.get("kind")},
                        },
                        "codex.item.completed",
                    )
                    emit(
                        "tool.completed",
                        {
                            "toolCallId": call_id,
                            "isError": self._item_error(item),
                            "result": {
                                "status": item.get("status"),
                                "change": change,
                            },
                        },
                        "codex.item.completed",
                    )
                return
            if item_type not in {"command_execution", "mcp_tool_call", "web_search"}:
                return
            if item_id not in started_items:
                start_item(item)
            for call_id in started_items.get(item_id, []):
                emit(
                    "tool.completed",
                    {
                        "toolCallId": call_id,
                        "isError": self._item_error(item),
                        "result": item.get("result") or item.get("output") or {
                            "status": item.get("status"),
                            "exit_code": item.get("exit_code"),
                        },
                    },
                    "codex.item.completed",
                )

        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                raw_events.append({"unparsed": line[:2000]})
                continue
            if not isinstance(value, dict):
                continue
            safe = redact(value)
            raw_events.append(safe if isinstance(safe, dict) else {"redacted": True})
            kind = str(value.get("type") or "")
            if kind in {"thread.started", "turn.started"}:
                emit("backend.event", {"subtype": kind}, kind)
            elif kind == "item.started":
                item = value.get("item")
                if isinstance(item, dict):
                    start_item(item)
            elif kind == "item.completed":
                item = value.get("item")
                if isinstance(item, dict):
                    complete_item(item)
            elif kind == "turn.completed":
                summary["result_seen"] = True
                usage = value.get("usage")
                summary["usage"] = dict(usage) if isinstance(usage, dict) else {}
                emit("turn.completed", {}, kind)
            elif kind in {"turn.failed", "error"}:
                summary["result_seen"] = kind == "turn.failed"
                summary["is_error"] = True
                emit("turn.error", {"subtype": kind}, kind)
            else:
                emit("backend.event", {"subtype": kind or "unknown"}, kind or "unknown")
        return events, raw_events, summary

    @staticmethod
    def _estimated_cost(model: str, usage: dict[str, Any]) -> float:
        prices = _MODEL_PRICES_PER_MILLION[model]
        input_tokens = int(usage.get("input_tokens") or 0)
        cached_tokens = int(
            usage.get("cached_input_tokens")
            or usage.get("cache_read_input_tokens")
            or 0
        )
        uncached_tokens = max(0, input_tokens - cached_tokens)
        output_tokens = int(usage.get("output_tokens") or 0)
        return (
            uncached_tokens * prices["input"]
            + cached_tokens * prices["cached_input"]
            + output_tokens * prices["output"]
        ) / 1_000_000

    def run_attempt(self, request: AttemptRequest) -> AttemptResult:
        if self._closed:
            raise RuntimeError("adapter is closed")
        workspace = self._workspace_root / request.trial.attempt_id
        result = AttemptResult(
            status="infrastructure_error",
            events=[],
            dimensions={
                "adapter": self.name,
                "remote_root": str(workspace),
                "write_root": str(workspace / "deliverables"),
                "provider_cost_usd": 0.0,
            },
            error="attempt interrupted before a result was available",
        )
        try:
            workspace = self._stage_workspace(request)
            prompt = self._prompt(request)
            command = self._command(request, prompt)
            timeout = min(
                request.scenario.timeout_seconds,
                max(1.0, self._deadline - time.monotonic()),
            )
            started = time.monotonic()
            returncode, stdout, stderr = self._run_cli(
                command,
                cwd=workspace,
                env=dict(os.environ),
                timeout=timeout,
            )
            completion_seconds = time.monotonic() - started
            model = _model_id(request.candidate)
            events, raw_events, summary = self._normalize_codex(
                stdout.splitlines(), workspace, model
            )
            artifacts = self._collect_artifacts(request, workspace)
            events.extend(
                self._collect_ui_events(
                    request,
                    workspace,
                    starting_sequence=len(events) + 1,
                )
            )
            usage = summary.get("usage") or {}
            cost = self._estimated_cost(model, usage)
            usage_rows = []
            if summary["result_seen"]:
                usage_rows.append(
                    {
                        "model": model,
                        "input_tokens": int(usage.get("input_tokens") or 0),
                        "output_tokens": int(usage.get("output_tokens") or 0),
                        "provider_cost_microcents": int(round(cost * 10_000)),
                        "metadata": {
                            "cache_read_tokens": int(
                                usage.get("cached_input_tokens") or 0
                            ),
                            "cache_write_tokens": 0,
                            "cost_method": "estimated_from_public_rates",
                        },
                    }
                )
            infrastructure_failure = (
                returncode is None
                or returncode != 0
                or not summary["result_seen"]
                or summary["is_error"]
            )
            status = "infrastructure_error" if infrastructure_failure else "completed"
            error = (
                f"Codex CLI failed (exit={returncode!r}): {stderr.strip()[:500]}"
                if infrastructure_failure
                else None
            )
            result = AttemptResult(
                status=status,
                events=events,
                response=str(summary.get("response") or ""),
                usage=usage_rows,
                artifacts=artifacts,
                timings={"completion_seconds": round(completion_seconds, 3)},
                dimensions={
                    "adapter": self.name,
                    "remote_root": str(workspace),
                    "write_root": str(workspace / "deliverables"),
                    "provider_cost_usd": cost,
                    "provider_cost_estimated": True,
                    "actual_model": model,
                    "requested_effort": request.candidate.effort,
                    "cli_exit_code": returncode,
                    "raw_events": raw_events,
                },
                settings={
                    "requested": request.candidate.requested_settings(),
                    "translated": {
                        "reasoning_effort": {
                            "model_reasoning_effort": request.candidate.effort
                        },
                        "text_verbosity": {
                            "model_verbosity": request.candidate.verbosity
                        },
                        "temperature": {"mode": "omit"},
                        "max_output_tokens": {"mode": "provider_default"},
                    },
                    "applied": {
                        "model": model,
                        "reasoning_effort": request.candidate.effort,
                        "text_verbosity": request.candidate.verbosity,
                        "temperature": "omitted",
                        "max_output_tokens": "provider_default",
                    },
                    "unobservable": [],
                },
                error=error,
            )
        except Exception as exc:
            result.error = str(exc)
        finally:
            cleanup = self._cleanup_workspace(workspace)
            self._cleanup_results.extend(cleanup)
            result.cleanup = cleanup
            if any(row.get("status") != "pass" for row in cleanup) and result.status == "completed":
                result.status = "infrastructure_error"
                result.error = "attempt cleanup failed"
        return result
