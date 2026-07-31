"""Backend-neutral event vocabulary for agent attempts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .evidence import redact


EVENT_TYPES = frozenset(
    {
        "message.delta",
        "thinking.delta",
        "tool.started",
        "tool.completed",
        "skill.read",
        "ui.emitted",
        "approval.requested",
        "approval.resolved",
        "artifact.created",
        "usage.recorded",
        "turn.error",
        "turn.completed",
        "backend.event",
    }
)
TOOL_TRACE_VERSION = 2
_SIDE_EFFECTS = frozenset(
    {
        "none",
        "internal_write",
        "draft",
        "external_write",
        "send",
        "publish",
        "spend",
        "delete",
    }
)

_READ_TOOL_NAMES = frozenset({"read", "glob", "grep"})
_WEB_READ_TOOL_NAMES = frozenset({"webfetch", "websearch"})
_INTERNAL_WRITE_NAMES = frozenset({"write", "edit", "notebookedit"})


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _duration_ms(started_at: Any, completed_at: Any) -> float | None:
    try:
        started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        completed = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
        return round(max(0.0, (completed - started).total_seconds() * 1000), 3)
    except (TypeError, ValueError):
        return None


def _bounded_preview(value: Any, *, maximum_bytes: int = 2_000) -> Any:
    safe = redact(value)
    encoded = json.dumps(safe, default=str, ensure_ascii=False).encode()
    if len(encoded) <= maximum_bytes:
        return safe
    text = encoded[:maximum_bytes].decode(errors="replace")
    return {
        "preview": text,
        "truncated": True,
        "original_bytes": len(encoded),
    }


def _legacy_call_id(data: dict[str, Any]) -> str:
    return str(
        data.get("call_id")
        or data.get("toolCallId")
        or data.get("tool_call_id")
        or data.get("id")
        or ""
    )


def _default_tool_metadata(name: str) -> dict[str, str]:
    normalized = name.casefold()
    if normalized in _READ_TOOL_NAMES:
        return {
            "operation": f"files.{normalized}",
            "integration": "filesystem",
            "capability": "files.read",
            "side_effect": "none",
        }
    if normalized in _WEB_READ_TOOL_NAMES:
        return {
            "operation": f"browser.{normalized}",
            "integration": "web",
            "capability": "browser.read",
            "side_effect": "none",
        }
    if normalized in _INTERNAL_WRITE_NAMES:
        return {
            "operation": f"files.{normalized}",
            "integration": "filesystem",
            "capability": "files.write",
            "side_effect": "internal_write",
        }
    return {
        "operation": normalized or "unknown",
        "integration": "unknown",
        "capability": "unknown",
        "side_effect": "external_write",
    }


def upgrade_tool_trace(
    events: list["AgentEvent"],
    *,
    operation_maps: tuple[dict[str, dict[str, str]], ...] = (),
    operation_resolvers: tuple[
        Callable[[str, dict[str, Any]], dict[str, str] | None], ...
    ] = (),
    adapter: str = "unknown",
    adapter_version: str = "unknown",
    environment: str = "none",
    environment_version: str = "unknown",
) -> list["AgentEvent"]:
    """Add the v2 tool envelope and bound normalized argument/result evidence.

    Adapters may emit the v2 fields themselves. This function fills only absent
    values and pairs completion events with their observed starts. Unknown tools
    fail closed to an external-write side effect. Unbounded native payloads stay
    in the separately redacted raw trace, not the normalized event stream.
    """

    operations: dict[str, dict[str, str]] = {}
    for operation_map in operation_maps:
        operations.update(operation_map)
        operations.update({key.casefold(): value for key, value in operation_map.items()})
    starts: dict[str, dict[str, Any]] = {}
    upgraded: list[AgentEvent] = []
    for event in events:
        if event.type not in {"tool.started", "tool.completed", "skill.read"}:
            upgraded.append(event)
            continue
        data = dict(event.data)
        call_id = _legacy_call_id(data)
        if event.type in {"tool.started", "skill.read"}:
            name = str(data.get("tool_name") or data.get("name") or "")
            metadata = operations.get(name) or operations.get(name.casefold())
            raw_arguments = data.get("args") if isinstance(data.get("args"), dict) else {}
            for resolver in operation_resolvers:
                try:
                    resolved = resolver(name, raw_arguments)
                except Exception:
                    resolved = {
                        "operation": "unknown",
                        "integration": "unknown",
                        "capability": "unknown",
                        "side_effect": "external_write",
                    }
                if resolved is not None:
                    metadata = resolved
                    break
            metadata = dict(metadata or _default_tool_metadata(name))
            args = data.get("arguments_redacted")
            if args is None:
                args = redact(raw_arguments)
            data.pop("args", None)
            data.update(
                {
                    "trace_version": TOOL_TRACE_VERSION,
                    "call_id": call_id,
                    "tool_name": name,
                    "operation": data.get("operation") or metadata["operation"],
                    "integration": data.get("integration") or metadata["integration"],
                    "capability": data.get("capability") or metadata["capability"],
                    "side_effect": data.get("side_effect") or metadata["side_effect"],
                    "arguments_redacted": args,
                    "arguments_sha256": data.get("arguments_sha256")
                    or _canonical_hash(raw_arguments),
                    "started_at": data.get("started_at") or event.timestamp,
                    "retry_ordinal": int(data.get("retry_ordinal") or 0),
                    "adapter": data.get("adapter") or adapter,
                    "adapter_version": data.get("adapter_version") or adapter_version,
                    "environment": data.get("environment") or environment,
                    "environment_version": data.get("environment_version")
                    or environment_version,
                    "raw_event_schema_version": data.get("raw_event_schema_version")
                    or "unversioned",
                }
            )
            if call_id:
                starts[call_id] = data
        else:
            start = starts.get(call_id, {})
            is_error = bool(
                data.get("isError")
                or data.get("is_error")
                or data.get("status") == "error"
            )
            result = data.get("result")
            preview = _bounded_preview(
                data.get("result_preview", result)
                if data.get("result_preview") is not None
                else result
            )
            result_bytes = (
                len(json.dumps(result, default=str).encode())
                if result is not None
                else 0
            )
            result_rows = data.get("result_rows")
            if result_rows is None and isinstance(result, dict):
                result_rows = result.get("rowCount")
            if (
                result_rows is None
                and isinstance(result, dict)
                and isinstance(result.get("rows"), list)
            ):
                result_rows = len(result["rows"])
            completed_at = data.get("completed_at") or event.timestamp
            raw_status = data.get("status")
            status = (
                raw_status
                if raw_status in {"completed", "error"}
                else ("error" if is_error else "completed")
            )
            data.pop("result", None)
            data.update(
                {
                    "trace_version": TOOL_TRACE_VERSION,
                    "call_id": call_id,
                    "tool_name": data.get("tool_name")
                    or data.get("name")
                    or start.get("tool_name")
                    or "",
                    "operation": data.get("operation")
                    or start.get("operation")
                    or "unknown",
                    "integration": data.get("integration")
                    or start.get("integration")
                    or "unknown",
                    "capability": data.get("capability")
                    or start.get("capability")
                    or "unknown",
                    "side_effect": data.get("side_effect")
                    or start.get("side_effect")
                    or "external_write",
                    "status": status,
                    "error_kind": data.get("error_kind")
                    or ("tool_error" if is_error else None),
                    "recovered": bool(data.get("recovered", False)),
                    "retry_ordinal": int(
                        data.get("retry_ordinal") or start.get("retry_ordinal") or 0
                    ),
                    "completed_at": completed_at,
                    "duration_ms": data.get("duration_ms")
                    if data.get("duration_ms") is not None
                    else _duration_ms(start.get("started_at"), completed_at),
                    "result_preview": preview,
                    "result_sha256": data.get("result_sha256")
                    or (_canonical_hash(result) if result is not None else None),
                    "result_bytes": data.get("result_bytes") or result_bytes,
                    "result_rows": result_rows,
                    "result_truncated": bool(
                        data.get("result_truncated", False)
                        or (
                            isinstance(preview, dict)
                            and preview.get("truncated") is True
                        )
                    ),
                    "pagination_present": bool(
                        data.get("pagination_present", False)
                        or (
                            isinstance(result, dict)
                            and any(
                                key in result
                                for key in (
                                    "next_page_token",
                                    "nextPageToken",
                                    "next_offset",
                                    "nextOffset",
                                    "cursor",
                                )
                            )
                        )
                    ),
                    "adapter": data.get("adapter") or start.get("adapter") or adapter,
                    "adapter_version": data.get("adapter_version")
                    or start.get("adapter_version")
                    or adapter_version,
                    "environment": data.get("environment")
                    or start.get("environment")
                    or environment,
                    "environment_version": data.get("environment_version")
                    or start.get("environment_version")
                    or environment_version,
                    "raw_event_schema_version": data.get("raw_event_schema_version")
                    or start.get("raw_event_schema_version")
                    or "unversioned",
                }
            )
        upgraded.append(
            AgentEvent(
                sequence=event.sequence,
                type=event.type,
                timestamp=event.timestamp,
                data=data,
                raw_type=event.raw_type,
            )
        )
    return upgraded


def validate_tool_trace(events: list["AgentEvent"]) -> tuple[str, ...]:
    """Return conformance errors for a normalized v2 tool trace."""

    errors: list[str] = []
    starts: dict[str, AgentEvent] = {}
    completions: set[str] = set()
    last_sequence = 0
    for event in events:
        if event.sequence <= last_sequence:
            errors.append(f"non-monotonic sequence at {event.sequence}")
        last_sequence = event.sequence
        if event.type not in {"tool.started", "tool.completed", "skill.read"}:
            continue
        data = event.data
        call_id = str(data.get("call_id") or "")
        if data.get("trace_version") != TOOL_TRACE_VERSION:
            errors.append(f"{event.sequence}: missing tool trace version")
        if not call_id:
            errors.append(f"{event.sequence}: missing call_id")
        if data.get("side_effect") not in _SIDE_EFFECTS:
            errors.append(f"{event.sequence}: invalid side_effect")
        if event.type in {"tool.started", "skill.read"}:
            if call_id and call_id in starts:
                errors.append(f"{event.sequence}: duplicate start {call_id!r}")
            if call_id:
                starts[call_id] = event
            for field_name in (
                "tool_name",
                "operation",
                "integration",
                "capability",
                "side_effect",
                "arguments_sha256",
                "adapter",
                "adapter_version",
                "environment",
                "environment_version",
                "raw_event_schema_version",
            ):
                if not data.get(field_name):
                    errors.append(f"{event.sequence}: missing {field_name}")
            if "arguments_redacted" not in data:
                errors.append(f"{event.sequence}: missing arguments_redacted")
        elif call_id not in starts:
            errors.append(f"{event.sequence}: completion without start {call_id!r}")
        else:
            if call_id in completions:
                errors.append(f"{event.sequence}: duplicate completion {call_id!r}")
            completions.add(call_id)
            for field_name in (
                "tool_name",
                "operation",
                "integration",
                "capability",
                "side_effect",
                "status",
                "adapter",
                "adapter_version",
                "environment",
                "environment_version",
                "raw_event_schema_version",
            ):
                if not data.get(field_name):
                    errors.append(f"{event.sequence}: missing completion {field_name}")
            if data.get("duration_ms") is None:
                errors.append(f"{event.sequence}: missing completion duration_ms")
            elif (
                isinstance(data.get("duration_ms"), bool)
                or not isinstance(data.get("duration_ms"), (int, float))
                or data["duration_ms"] < 0
            ):
                errors.append(f"{event.sequence}: invalid completion duration_ms")
            if "result_bytes" not in data:
                errors.append(f"{event.sequence}: missing completion result_bytes")
            elif (
                isinstance(data.get("result_bytes"), bool)
                or not isinstance(data.get("result_bytes"), int)
                or data["result_bytes"] < 0
            ):
                errors.append(f"{event.sequence}: invalid completion result_bytes")
            if data.get("status") not in {"completed", "error"}:
                errors.append(f"{event.sequence}: invalid completion status")
    for call_id, event in starts.items():
        if call_id not in completions:
            errors.append(f"{event.sequence}: start without completion {call_id!r}")
    return tuple(errors)


def tool_ledger_from_events(events: list["AgentEvent"]) -> tuple[dict[str, Any], ...]:
    """Collapse normalized start/completion events into a redacted call ledger."""

    starts: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    completed: set[str] = set()
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.type in {"tool.started", "skill.read"}:
            call_id = str(event.data.get("call_id") or "")
            if not call_id:
                continue
            starts[call_id] = dict(event.data)
            order.append(call_id)
        elif event.type == "tool.completed":
            call_id = str(event.data.get("call_id") or "")
            start = starts.get(call_id, {})
            completed.add(call_id)
            rows.append(
                {
                    "trace_version": TOOL_TRACE_VERSION,
                    "sequence": event.sequence,
                    "call_id": call_id,
                    "tool_name": event.data.get("tool_name")
                    or start.get("tool_name"),
                    "operation": event.data.get("operation")
                    or start.get("operation"),
                    "integration": event.data.get("integration")
                    or start.get("integration"),
                    "capability": event.data.get("capability")
                    or start.get("capability"),
                    "side_effect": event.data.get("side_effect")
                    or start.get("side_effect"),
                    "arguments": start.get("arguments_redacted") or {},
                    "arguments_sha256": start.get("arguments_sha256"),
                    "status": event.data.get("status"),
                    "error_kind": event.data.get("error_kind"),
                    "result": event.data.get("result_preview"),
                    "result_sha256": event.data.get("result_sha256"),
                    "retry_ordinal": event.data.get("retry_ordinal", 0),
                    "timestamp": event.timestamp,
                }
            )
    for call_id in order:
        if call_id in completed:
            continue
        start = starts[call_id]
        rows.append(
            {
                "trace_version": TOOL_TRACE_VERSION,
                "sequence": 0,
                "call_id": call_id,
                "tool_name": start.get("tool_name"),
                "operation": start.get("operation"),
                "integration": start.get("integration"),
                "capability": start.get("capability"),
                "side_effect": start.get("side_effect"),
                "arguments": start.get("arguments_redacted") or {},
                "arguments_sha256": start.get("arguments_sha256"),
                "status": "incomplete",
                "error_kind": "missing_completion",
                "retry_ordinal": start.get("retry_ordinal", 0),
                "timestamp": start.get("started_at"),
            }
        )
    return tuple(sorted(rows, key=lambda row: int(row.get("sequence") or 0)))


@dataclass(frozen=True)
class AgentEvent:
    sequence: int
    type: str
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)
    raw_type: str | None = None

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown normalized event type: {self.type}")
        if self.sequence < 1:
            raise ValueError("event sequence must be positive")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
