"""Explicit plugin registries for the open-core evaluation runner.

Manifests refer only to pre-registered IDs.  They can never supply an arbitrary
Python module or import path, which keeps untrusted fixture loading from turning
into code execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any, Callable, Generic, TypeVar

from .schema import ManifestError


T = TypeVar("T")


@dataclass(frozen=True)
class PluginDescriptor:
    id: str
    kind: str
    api_version: int
    implementation_version: str


@dataclass(frozen=True)
class _Registration(Generic[T]):
    descriptor: PluginDescriptor
    factory: Callable[..., T]


class PluginRegistry(Generic[T]):
    def __init__(self, kind: str, *, api_version: int = 1) -> None:
        self.kind = kind
        self.api_version = api_version
        self._plugins: dict[str, _Registration[T]] = {}

    def register(
        self,
        plugin_id: str,
        factory: Callable[..., T],
        *,
        implementation_version: str,
        api_version: int | None = None,
    ) -> None:
        if plugin_id in self._plugins:
            raise ValueError(f"duplicate {self.kind} plugin id: {plugin_id}")
        declared_api = self.api_version if api_version is None else api_version
        if declared_api != self.api_version:
            raise ValueError(
                f"{self.kind} plugin {plugin_id} uses API {declared_api}; "
                f"runner requires {self.api_version}"
            )
        self._plugins[plugin_id] = _Registration(
            descriptor=PluginDescriptor(
                id=plugin_id,
                kind=self.kind,
                api_version=declared_api,
                implementation_version=implementation_version,
            ),
            factory=factory,
        )

    def create(self, plugin_id: str, **kwargs: Any) -> T:
        try:
            registration = self._plugins[plugin_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._plugins)) or "none"
            raise ManifestError(
                f"unknown {self.kind} plugin {plugin_id!r}; registered: {available}"
            ) from exc
        return registration.factory(**kwargs)

    def describe(self) -> tuple[PluginDescriptor, ...]:
        return tuple(
            self._plugins[plugin_id].descriptor for plugin_id in sorted(self._plugins)
        )

    def __contains__(self, plugin_id: object) -> bool:
        return plugin_id in self._plugins


def discover_entry_points(
    registry: PluginRegistry[Any],
    *,
    group: str,
) -> tuple[PluginDescriptor, ...]:
    """Load operator-installed plugins; manifests can never invoke discovery.

    Discovery is deliberately explicit. A trusted CLI or host calls this after
    installing a package, while untrusted scenario files may reference only IDs
    already present in the registry.
    """

    discovered = metadata.entry_points()
    selected = (
        discovered.select(group=group)
        if hasattr(discovered, "select")
        else discovered.get(group, ())
    )
    for entry_point in selected:
        factory = entry_point.load()
        api_version = int(getattr(factory, "agent_eval_api_version", 1))
        implementation_version = str(
            getattr(factory, "agent_eval_version", "unknown")
        )
        registry.register(
            entry_point.name,
            factory,
            api_version=api_version,
            implementation_version=implementation_version,
        )
    return registry.describe()


agent_adapters: PluginRegistry[Any] = PluginRegistry("agent_adapter")
integration_environments: PluginRegistry[Any] = PluginRegistry(
    "integration_environment"
)
scorers: PluginRegistry[Any] = PluginRegistry("scorer")
ui_validators: PluginRegistry[Any] = PluginRegistry("ui_validator")
