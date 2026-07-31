"""Dispatch scenarios to explicit, pre-constructed environment plugins."""

from __future__ import annotations

from typing import Any

from .base import (
    AttemptEnvironment,
    EnvironmentInfo,
    EnvironmentRequest,
    EnvironmentSnapshot,
    IntegrationEnvironment,
    NoopEnvironment,
)


class EnvironmentRouter:
    name = "router"
    version = "1"

    def __init__(
        self,
        environments: dict[str, IntegrationEnvironment] | None = None,
    ) -> None:
        configured = environments or {}
        if "none" in configured:
            raise ValueError("environment plugin id 'none' is reserved")
        mismatched = sorted(
            key
            for key, environment in configured.items()
            if getattr(environment, "name", None) != key
        )
        if mismatched:
            raise ValueError(
                "environment registry keys must match plugin names: "
                + ", ".join(mismatched)
            )
        self._environments: dict[str, IntegrationEnvironment] = {
            "none": NoopEnvironment(),
            **configured,
        }
        self._registration_order = list(self._environments)
        self._used: list[str] = []
        self._closed = False

    def describe(self) -> EnvironmentInfo:
        infos = [environment.describe() for environment in self._environments.values()]
        return EnvironmentInfo(
            plugin=self.name,
            version=self.version,
            modes=tuple(sorted({mode for info in infos for mode in info.modes})),
            capabilities=tuple(
                sorted({value for info in infos for value in info.capabilities})
            ),
            binding_kinds=tuple(
                sorted({value for info in infos for value in info.binding_kinds})
            ),
            dimensions={"plugins": sorted(info.plugin for info in infos)},
        )

    def _for_plugin(self, plugin: str | None) -> IntegrationEnvironment:
        key = plugin or "none"
        try:
            return self._environments[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._environments))
            raise RuntimeError(
                f"scenario requires environment {key!r}; available: {available}"
            ) from exc

    def preflight(self, scenarios: list[Any]) -> EnvironmentInfo:
        grouped: dict[str, list[Any]] = {}
        for scenario in scenarios:
            key = scenario.environment_plugin or "none"
            grouped.setdefault(key, []).append(scenario)
        infos: list[EnvironmentInfo] = []
        for key, selected in sorted(grouped.items()):
            environment = self._for_plugin(key)
            infos.append(environment.preflight(selected))
            if key not in self._used:
                self._used.append(key)
        return EnvironmentInfo(
            plugin=self.name,
            version=self.version,
            modes=tuple(sorted({mode for info in infos for mode in info.modes})),
            capabilities=tuple(
                sorted({capability for info in infos for capability in info.capabilities})
            ),
            binding_kinds=tuple(
                sorted({kind for info in infos for kind in info.binding_kinds})
            ),
            dimensions={
                "plugins": [
                    {
                        "plugin": info.plugin,
                        "version": info.version,
                        "modes": list(info.modes),
                        "capabilities": list(info.capabilities),
                        "binding_kinds": list(info.binding_kinds),
                        "dimensions": info.dimensions,
                    }
                    for info in infos
                ]
            },
        )

    def provision(self, request: EnvironmentRequest) -> AttemptEnvironment:
        environment = self._for_plugin(request.scenario.environment_plugin)
        return environment.provision(request)

    def oracle(self, handle: AttemptEnvironment) -> dict[str, Any]:
        return self._for_plugin(handle.plugin).oracle(handle)

    def snapshot(self, handle: AttemptEnvironment) -> EnvironmentSnapshot:
        return self._for_plugin(handle.plugin).snapshot(handle)

    def reset(self, handle: AttemptEnvironment) -> list[dict[str, Any]]:
        return self._for_plugin(handle.plugin).reset(handle)

    def close(self) -> list[dict[str, Any]]:
        if self._closed:
            return []
        self._closed = True
        rows: list[dict[str, Any]] = []
        order = [
            *reversed(self._used),
            *(
                key
                for key in reversed(self._registration_order)
                if key not in self._used and key != "none"
            ),
        ]
        for key in order:
            try:
                rows.extend(self._for_plugin(key).close())
            except Exception as exc:
                rows.append(
                    {
                        "name": f"close environment {key}",
                        "status": "fail",
                        "error": str(exc),
                    }
                )
        return rows
