"""Backend-neutral lifecycle for the tools/world used by one agent attempt.

The adapter and environment are deliberately independent.  An adapter receives
only public tool bindings.  Hidden oracle data is fetched by the engine after
the adapter has returned, so it cannot leak into the agent workspace or prompt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema import Candidate, Scenario, Trial

from ..schema import KNOWN_CAPABILITIES, SIDE_EFFECT_CLASSES


BINDING_KINDS = frozenset({"mcp_stdio", "mcp_http", "subprocess_jsonl", "native"})
OperationResolver = Callable[[str, dict[str, Any]], Optional[dict[str, str]]]


@dataclass(frozen=True)
class ToolBinding:
    """Attempt-scoped tool connection passed to an agent adapter.

    ``config`` may contain process-local connection material and must never be
    serialized. ``evidence`` is the explicit redacted representation that may
    be written to an eval artifact. ``operations`` maps native tool names onto
    stable integration/capability/side-effect metadata.
    """

    kind: str
    name: str
    config: dict[str, Any] = field(default_factory=dict, repr=False)
    evidence: dict[str, Any] = field(default_factory=dict)
    operations: dict[str, dict[str, str]] = field(default_factory=dict)
    operation_resolver: OperationResolver | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.kind not in BINDING_KINDS:
            raise ValueError(f"unsupported tool binding kind: {self.kind!r}")
        if not self.name or not self.name.strip():
            raise ValueError("tool binding name must be non-empty")
        for tool_name, metadata in self.operations.items():
            if not isinstance(tool_name, str) or not tool_name:
                raise ValueError("tool operation map names must be non-empty strings")
            missing = {
                key
                for key in ("operation", "integration", "capability", "side_effect")
                if not isinstance(metadata.get(key), str) or not metadata.get(key)
            }
            if missing:
                raise ValueError(
                    f"tool operation {tool_name!r} lacks metadata: {sorted(missing)}"
                )
            if metadata["capability"] not in KNOWN_CAPABILITIES:
                raise ValueError(
                    f"tool operation {tool_name!r} has unknown capability "
                    f"{metadata['capability']!r}"
                )
            if metadata["side_effect"] not in SIDE_EFFECT_CLASSES:
                raise ValueError(
                    f"tool operation {tool_name!r} has unknown side effect "
                    f"{metadata['side_effect']!r}"
                )

    def as_evidence(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "evidence": self.evidence,
            "operations": self.operations,
        }

    def resolve_operation(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, str] | None:
        if self.operation_resolver is None:
            return None
        return self.operation_resolver(tool_name, arguments)


@dataclass(frozen=True)
class EnvironmentInfo:
    plugin: str
    version: str
    modes: tuple[str, ...]
    capabilities: tuple[str, ...]
    binding_kinds: tuple[str, ...] = ()
    dimensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnvironmentRequest:
    run_id: str
    trial: "Trial"
    candidate: "Candidate"
    scenario: "Scenario"
    repo_root: Path
    output_dir: Path


@dataclass(frozen=True)
class AttemptEnvironment:
    plugin: str
    version: str
    attempt_id: str
    mode: str
    fixed_clock: str | None = None
    bindings: tuple[ToolBinding, ...] = ()
    public_metadata: dict[str, Any] = field(default_factory=dict)
    opaque_ref: str | None = field(default=None, repr=False)

    def as_evidence(self) -> dict[str, Any]:
        return {
            "plugin": self.plugin,
            "version": self.version,
            "attempt_id": self.attempt_id,
            "mode": self.mode,
            "fixed_clock": self.fixed_clock,
            "bindings": [binding.as_evidence() for binding in self.bindings],
            "public_metadata": self.public_metadata,
        }


@dataclass(frozen=True)
class EnvironmentSnapshot:
    ledger: tuple[dict[str, Any], ...] = ()
    state: dict[str, Any] = field(default_factory=dict)
    dimensions: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IntegrationEnvironment(Protocol):
    """World/tool lifecycle independent of the agent backend."""

    name: str
    version: str

    def describe(self) -> EnvironmentInfo:
        """Describe stable capabilities without credentials or external state."""

    def preflight(self, scenarios: list["Scenario"]) -> EnvironmentInfo:
        """Validate support without creating attempt resources."""

    def provision(self, request: EnvironmentRequest) -> AttemptEnvironment:
        """Create one isolated environment and return agent-visible bindings."""

    def oracle(self, handle: AttemptEnvironment) -> dict[str, Any]:
        """Return grader-only expected facts after agent execution."""

    def snapshot(self, handle: AttemptEnvironment) -> EnvironmentSnapshot:
        """Collect the redacted tool ledger and attempt-owned state."""

    def reset(self, handle: AttemptEnvironment) -> list[dict[str, Any]]:
        """Remove only resources belonging to this attempt; safe to retry."""

    def close(self) -> list[dict[str, Any]]:
        """Release run-scoped resources; safe to call more than once."""


class NoopEnvironment:
    """Environment used by writing and other tool-free version 1 scenarios."""

    name = "none"
    version = "1"

    def describe(self) -> EnvironmentInfo:
        return EnvironmentInfo(
            plugin=self.name,
            version=self.version,
            modes=("none",),
            capabilities=(),
            binding_kinds=(),
        )

    def preflight(self, scenarios: list["Scenario"]) -> EnvironmentInfo:
        unsupported = [
            scenario.id
            for scenario in scenarios
            if getattr(scenario, "environment_plugin", None) not in {None, "none"}
            or getattr(scenario, "environment_mode", "none") != "none"
        ]
        if unsupported:
            raise RuntimeError(
                "tool-backed scenarios require an integration environment: "
                + ", ".join(sorted(unsupported))
            )
        return EnvironmentInfo(
            plugin=self.name,
            version=self.version,
            modes=("none",),
            capabilities=(),
            binding_kinds=(),
            dimensions={"scenario_count": len(scenarios)},
        )

    def provision(self, request: EnvironmentRequest) -> AttemptEnvironment:
        return AttemptEnvironment(
            plugin=self.name,
            version=self.version,
            attempt_id=request.trial.attempt_id,
            mode="none",
        )

    def oracle(self, handle: AttemptEnvironment) -> dict[str, Any]:
        return {}

    def snapshot(self, handle: AttemptEnvironment) -> EnvironmentSnapshot:
        return EnvironmentSnapshot()

    def reset(self, handle: AttemptEnvironment) -> list[dict[str, Any]]:
        return [
            {
                "name": "reset no-op environment",
                "status": "pass",
                "resource": {"attempt_id": handle.attempt_id},
            }
        ]

    def close(self) -> list[dict[str, Any]]:
        return [{"name": "close no-op environment", "status": "pass"}]
