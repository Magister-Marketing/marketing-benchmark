"""Attempt-scoped replay MCP environment backed only by synthetic fixtures."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from evals.runner.environments import (
    AttemptEnvironment,
    EnvironmentInfo,
    EnvironmentRequest,
    EnvironmentSnapshot,
    ToolBinding,
)
from evals.runner.evidence import contained_path, prepare_owned_directory
from evals.runner.schema import KNOWN_CAPABILITIES


class ReplayMcpEnvironment:
    name = "replay-mcp"
    version = "1"

    def __init__(
        self,
        *,
        repo_root: Path,
        run_id: str,
        fixture_root: Path | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.run_id = run_id
        self.fixture_root = (
            fixture_root.resolve()
            if fixture_root
            else self.repo_root / "evals" / "fixtures" / "public" / "integrations"
        )
        self.workspace_root = prepare_owned_directory(
            workspace_root
            if workspace_root
            else Path(tempfile.mkdtemp(prefix=f"agent-eval-replay-{run_id}-")),
            protected=(self.repo_root,),
        )
        self._fixtures: dict[str, tuple[Path, dict[str, Any]]] = {}
        self._oracles: dict[str, dict[str, Any]] = {}
        self._closed = False

    def describe(self) -> EnvironmentInfo:
        return EnvironmentInfo(
            plugin=self.name,
            version=self.version,
            modes=("replay",),
            capabilities=(
                "ads.read",
                "analytics.read",
                "commerce.read",
                "crm.read",
                "search.read",
            ),
            binding_kinds=("mcp_stdio",),
            dimensions={"network": "disabled", "credentials": "none"},
        )

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise RuntimeError(f"replay fixture JSON cannot be a symlink: {path}")
        try:
            value = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid replay fixture JSON {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"replay fixture must be an object: {path}")
        return value

    def _load_fixtures(self) -> None:
        fixtures: dict[str, tuple[Path, dict[str, Any]]] = {}
        if not self.fixture_root.is_dir():
            raise RuntimeError(f"replay fixture root does not exist: {self.fixture_root}")
        for path in sorted(self.fixture_root.glob("**/manifest.json")):
            if path.is_symlink():
                continue
            manifest = self._read_object(path)
            fixture_id = manifest.get("id")
            if not isinstance(fixture_id, str) or not fixture_id:
                raise RuntimeError(f"replay fixture has no id: {path}")
            if fixture_id in fixtures:
                raise RuntimeError(f"duplicate replay fixture id: {fixture_id}")
            if manifest.get("fixture_version") != 1:
                raise RuntimeError(f"unsupported replay fixture version in {path}")
            fixtures[fixture_id] = (path.parent.resolve(), manifest)
        if not fixtures:
            raise RuntimeError(f"no replay fixtures found under {self.fixture_root}")
        self._fixtures = fixtures

    def preflight(self, scenarios: list[Any]) -> EnvironmentInfo:
        self._load_fixtures()
        selected: set[str] = set()
        capabilities: set[str] = set()
        for scenario in scenarios:
            if scenario.environment_plugin != self.name:
                raise RuntimeError(
                    f"replay MCP received incompatible scenario {scenario.id}: "
                    f"{scenario.environment_plugin!r}"
                )
            if scenario.environment_mode != "replay":
                raise RuntimeError(
                    f"replay MCP scenario {scenario.id} must use replay mode"
                )
            fixture_id = scenario.environment_fixture
            if not fixture_id or fixture_id not in self._fixtures:
                raise RuntimeError(
                    f"scenario {scenario.id} references unknown replay fixture "
                    f"{fixture_id!r}"
                )
            _, manifest = self._fixtures[fixture_id]
            fixture_capabilities = set(manifest.get("capabilities") or [])
            unknown = sorted(fixture_capabilities - KNOWN_CAPABILITIES)
            if unknown:
                raise RuntimeError(
                    f"replay fixture {fixture_id} declares unknown capabilities: "
                    + ", ".join(unknown)
                )
            missing = sorted(set(scenario.capabilities) - fixture_capabilities)
            if missing:
                raise RuntimeError(
                    f"replay fixture {fixture_id} lacks capabilities for "
                    f"{scenario.id}: {', '.join(missing)}"
                )
            scripts = manifest.get("scripts") or {}
            if scenario.id not in scripts and "default" not in scripts:
                raise RuntimeError(
                    f"replay fixture {fixture_id} has no script for {scenario.id}"
                )
            selected.add(fixture_id)
            capabilities.update(fixture_capabilities)
        return EnvironmentInfo(
            plugin=self.name,
            version=self.version,
            modes=("replay",),
            capabilities=tuple(sorted(capabilities)),
            binding_kinds=("mcp_stdio",),
            dimensions={
                "fixture_ids": sorted(selected),
                "network": "disabled",
                "credentials": "none",
            },
        )

    def _fixture(self, fixture_id: str) -> tuple[Path, dict[str, Any]]:
        if not self._fixtures:
            self._load_fixtures()
        try:
            return self._fixtures[fixture_id]
        except KeyError as exc:
            raise RuntimeError(f"unknown replay fixture: {fixture_id}") from exc

    def provision(self, request: EnvironmentRequest) -> AttemptEnvironment:
        if self._closed:
            raise RuntimeError("replay MCP environment is closed")
        fixture_id = request.scenario.environment_fixture
        if not fixture_id:
            raise RuntimeError(f"scenario {request.scenario.id} has no replay fixture")
        fixture_dir, manifest = self._fixture(fixture_id)
        state_dir = contained_path(self.workspace_root, request.trial.attempt_id)
        if state_dir.exists():
            raise RuntimeError(f"replay attempt state already exists: {state_dir}")
        public_dir = state_dir / "public"
        public_dir.mkdir(parents=True)
        for name in ("manifest.json", "tools.json", "dataset.json", "script.json"):
            source = fixture_dir / name
            if source.is_file() and not source.is_symlink():
                shutil.copyfile(source, public_dir / name)
        oracle = self._read_object(fixture_dir / "oracle.json")
        selected_oracle = dict(oracle.get("default") or {})
        scenario_oracles = oracle.get("scenarios") or {}
        if isinstance(scenario_oracles.get(request.scenario.id), dict):
            selected_oracle.update(scenario_oracles[request.scenario.id])
        self._oracles[request.trial.attempt_id] = selected_oracle
        ledger = state_dir / "ledger.jsonl"
        server_name = "eval_integrations"
        tools = self._read_object(fixture_dir / "tools.json").get("tools") or []
        operations: dict[str, dict[str, str]] = {}
        allowed_tools: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
                continue
            tool_name = tool["name"]
            metadata = {
                "operation": str(tool.get("operation") or tool_name),
                "integration": str(
                    tool.get("integration") or manifest.get("integration") or "unknown"
                ),
                "capability": str(tool.get("capability") or "unknown"),
                "side_effect": str(tool.get("side_effect") or "external_write"),
            }
            native_name = f"mcp__{server_name}__{tool_name}"
            operations[tool_name] = metadata
            operations[native_name] = metadata
            allowed_tools.append(native_name)
        config = {
            "command": sys.executable,
            "args": [
                "-m",
                "evals.plugins.replay_mcp.server",
                "--fixture",
                str(public_dir),
                "--scenario",
                request.scenario.id,
                "--attempt-id",
                request.trial.attempt_id,
                "--ledger",
                str(ledger),
            ],
            "env": {
                "PYTHONPATH": str(self.repo_root),
                "AGENT_EVAL_REPLAY_NETWORK": "disabled",
            },
            "allowed_tools": allowed_tools,
        }
        binding = ToolBinding(
            kind="mcp_stdio",
            name=server_name,
            config=config,
            evidence={
                "fixture_id": fixture_id,
                "scenario": request.scenario.id,
                "transport": "stdio",
                "network": "disabled",
                "credentials": "none",
                "allowed_tools": allowed_tools,
            },
            operations=operations,
        )
        return AttemptEnvironment(
            plugin=self.name,
            version=self.version,
            attempt_id=request.trial.attempt_id,
            mode="replay",
            fixed_clock=request.scenario.fixed_clock
            or str(manifest.get("fixed_clock") or ""),
            bindings=(binding,),
            public_metadata={
                "fixture_id": fixture_id,
                "integration": manifest.get("integration"),
                "capabilities": manifest.get("capabilities") or [],
                "scenario": request.scenario.id,
            },
            opaque_ref=str(state_dir),
        )

    def oracle(self, handle: AttemptEnvironment) -> dict[str, Any]:
        return dict(self._oracles.get(handle.attempt_id) or {})

    def snapshot(self, handle: AttemptEnvironment) -> EnvironmentSnapshot:
        state_dir = Path(handle.opaque_ref or "")
        ledger_path = state_dir / "ledger.jsonl"
        rows: list[dict[str, Any]] = []
        if ledger_path.is_file():
            for line in ledger_path.read_text().splitlines():
                if not line.strip():
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
        return EnvironmentSnapshot(
            ledger=tuple(rows),
            state={"call_count": len(rows)},
            dimensions={"fixture_id": handle.public_metadata.get("fixture_id")},
        )

    def reset(self, handle: AttemptEnvironment) -> list[dict[str, Any]]:
        state_dir = Path(handle.opaque_ref or "")
        resource = {"type": "replay_attempt", "attempt_id": handle.attempt_id}
        try:
            if state_dir.exists():
                shutil.rmtree(state_dir)
            self._oracles.pop(handle.attempt_id, None)
            return [{"name": "delete replay attempt", "status": "pass", "resource": resource}]
        except OSError as exc:
            return [
                {
                    "name": "delete replay attempt",
                    "status": "fail",
                    "resource": resource,
                    "error": str(exc),
                }
            ]

    def close(self) -> list[dict[str, Any]]:
        if self._closed:
            return []
        self._closed = True
        try:
            if self.workspace_root.exists():
                shutil.rmtree(self.workspace_root)
            self._oracles.clear()
            return [
                {
                    "name": "delete replay workspace root",
                    "status": "pass",
                    "resource": {"type": "replay_run", "run_id": self.run_id},
                }
            ]
        except OSError as exc:
            return [
                {
                    "name": "delete replay workspace root",
                    "status": "fail",
                    "resource": {"type": "replay_run", "run_id": self.run_id},
                    "error": str(exc),
                }
            ]
