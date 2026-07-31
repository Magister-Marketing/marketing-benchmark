"""Dependency-free conformance checks for third-party eval-runner plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .adapters.base import SettingsCapabilities
from .environments import BINDING_KINDS, EnvironmentInfo
from .events import AgentEvent, validate_tool_trace


@dataclass(frozen=True)
class ConformanceFinding:
    check: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "passed": self.passed,
            "detail": self.detail,
        }


def _surface_findings(value: Any, methods: tuple[str, ...]) -> list[ConformanceFinding]:
    return [
        ConformanceFinding(
            check=f"surface.{method}",
            passed=callable(getattr(value, method, None)),
            detail=(
                f"{method} is callable"
                if callable(getattr(value, method, None))
                else f"missing callable {method}"
            ),
        )
        for method in methods
    ]


def check_agent_adapter(adapter: Any) -> tuple[ConformanceFinding, ...]:
    findings = _surface_findings(
        adapter,
        (
            "supported_binding_kinds",
            "settings_capabilities",
            "preflight",
            "run_attempt",
            "close",
        ),
    )
    name = getattr(adapter, "name", None)
    findings.append(
        ConformanceFinding(
            check="identity.name",
            passed=isinstance(name, str) and bool(name.strip()),
            detail=f"adapter name={name!r}",
        )
    )
    binding_method = getattr(adapter, "supported_binding_kinds", None)
    if callable(binding_method):
        try:
            kinds = tuple(binding_method())
            unknown = sorted(set(kinds) - BINDING_KINDS)
            valid = len(kinds) == len(set(kinds)) and not unknown
            detail = (
                f"binding kinds={sorted(kinds)}"
                if valid
                else f"duplicate or unknown binding kinds={unknown or list(kinds)}"
            )
        except Exception as exc:
            valid = False
            detail = f"binding declaration raised {type(exc).__name__}: {exc}"
        findings.append(ConformanceFinding("bindings.declaration", valid, detail))
    capability_method = getattr(adapter, "settings_capabilities", None)
    if callable(capability_method):
        try:
            capabilities = capability_method()
            valid = isinstance(capabilities, SettingsCapabilities) and (
                capabilities.adapter == name
            )
            detail = (
                f"settings={sorted(capabilities.settings)}"
                if isinstance(capabilities, SettingsCapabilities)
                else f"unexpected type={type(capabilities).__name__}"
            )
        except Exception as exc:
            valid = False
            detail = f"settings declaration raised {type(exc).__name__}: {exc}"
        findings.append(ConformanceFinding("settings.declaration", valid, detail))
    return tuple(findings)


def check_environment(environment: Any) -> tuple[ConformanceFinding, ...]:
    findings = _surface_findings(
        environment,
        ("describe", "preflight", "provision", "oracle", "snapshot", "reset", "close"),
    )
    describe = getattr(environment, "describe", None)
    if callable(describe):
        try:
            info = describe()
            unknown = (
                sorted(set(info.binding_kinds) - BINDING_KINDS)
                if isinstance(info, EnvironmentInfo)
                else []
            )
            valid = (
                isinstance(info, EnvironmentInfo)
                and info.plugin == getattr(environment, "name", None)
                and info.version == getattr(environment, "version", None)
                and not unknown
            )
            detail = (
                f"plugin={info.plugin}, modes={list(info.modes)}, bindings={list(info.binding_kinds)}"
                if isinstance(info, EnvironmentInfo)
                else f"unexpected type={type(info).__name__}"
            )
        except Exception as exc:
            valid = False
            detail = f"describe raised {type(exc).__name__}: {exc}"
        findings.append(ConformanceFinding("environment.describe", valid, detail))
    return tuple(findings)


def check_tool_trace(events: list[AgentEvent]) -> tuple[ConformanceFinding, ...]:
    errors = validate_tool_trace(events)
    return (
        ConformanceFinding(
            check="tool_trace.v2",
            passed=not errors,
            detail="trace conforms" if not errors else "; ".join(errors),
        ),
    )


def check_cleanup(rows: Iterable[dict[str, Any]]) -> tuple[ConformanceFinding, ...]:
    values = list(rows)
    malformed = [
        index
        for index, row in enumerate(values)
        if not isinstance(row, dict)
        or not isinstance(row.get("name"), str)
        or row.get("status") not in {"pass", "fail"}
    ]
    return (
        ConformanceFinding(
            check="cleanup.evidence",
            passed=bool(values) and not malformed,
            detail=(
                f"captured {len(values)} cleanup result(s)"
                if values and not malformed
                else f"missing or malformed cleanup entries={malformed}"
            ),
        ),
    )


def assert_conformant(findings: Iterable[ConformanceFinding]) -> None:
    failures = [finding.detail for finding in findings if not finding.passed]
    if failures:
        raise ValueError("plugin conformance failed: " + "; ".join(failures))
