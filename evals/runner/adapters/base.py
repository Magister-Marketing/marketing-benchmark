"""Public adapter contract for running an arbitrary agent backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..events import AgentEvent
from ..environments import AttemptEnvironment
from ..schema import Candidate, Scenario, Trial


@dataclass(frozen=True)
class TargetInfo:
    adapter: str
    target_id: str
    dimensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AttemptRequest:
    run_id: str
    trial: Trial
    candidate: Candidate
    scenario: Scenario
    repo_root: Path
    output_dir: Path
    environment: AttemptEnvironment | None = None


@dataclass
class AttemptResult:
    status: str
    events: list[AgentEvent]
    response: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    usage: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    dimensions: dict[str, Any] = field(default_factory=dict)
    cleanup: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SettingsCapabilities:
    """Adapter-declared setting support used to fail before paid execution."""

    adapter: str
    settings: dict[str, dict[str, Any]]
    model_overrides: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def for_candidate(self, candidate: Candidate) -> dict[str, dict[str, Any]]:
        result = dict(self.settings)
        result.update(self.model_overrides.get(candidate.model, {}))
        return result


class AgentAdapter(Protocol):
    """Backend contract intentionally free of Magister implementation types."""

    name: str

    def supported_binding_kinds(self) -> tuple[str, ...]:
        """Return environment binding kinds this adapter can attach."""

    def settings_capabilities(self) -> SettingsCapabilities:
        """Describe supported setting modes and observable applied values."""

    def preflight(self, candidates: list[Candidate]) -> TargetInfo:
        """Resolve and validate the exact target without mutating it."""

    def run_attempt(self, request: AttemptRequest) -> AttemptResult:
        """Execute one isolated attempt and return complete evidence."""

    def close(self) -> list[dict[str, Any]]:
        """Release run-scoped resources; safe to call more than once."""
