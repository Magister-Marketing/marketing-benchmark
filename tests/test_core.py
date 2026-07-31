from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from evals.plugins.replay_mcp.server import load_service
from evals.runner.engine import plan_experiment
from evals.runner.events import AgentEvent, upgrade_tool_trace, validate_tool_trace
from evals.runner.evidence import contained_path, prepare_owned_directory, redact
from evals.runner.plugins import PluginRegistry
from evals.runner.schema import Catalog, ManifestError


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_version_two_manifests_and_tool_contracts_match_json_schema() -> None:
    schemas = {
        name: json.loads((REPO_ROOT / f"evals/schema/{name}.v2.schema.json").read_text())
        for name in ("candidate", "scenario", "experiment")
    }
    trace_schema = json.loads(
        (REPO_ROOT / "evals/schema/tool-trace.v2.schema.json").read_text()
    )
    for schema in (*schemas.values(), trace_schema):
        Draft202012Validator.check_schema(schema)

    patterns = {
        "candidate": "evals/candidates/*.json",
        "scenario": "evals/suites/**/*.json",
        "experiment": "evals/experiments/*.json",
    }
    for kind, pattern in patterns.items():
        validator = Draft202012Validator(schemas[kind])
        for path in REPO_ROOT.glob(pattern):
            manifest = json.loads(path.read_text())
            if manifest.get("schema_version") == 2:
                validator.validate(manifest)

    for path in REPO_ROOT.glob("evals/fixtures/public/integrations/**/tools.json"):
        for tool in json.loads(path.read_text())["tools"]:
            Draft202012Validator.check_schema(tool["input_schema"])


def test_catalog_and_randomized_plan_are_complete_and_deterministic() -> None:
    catalog = Catalog.load(REPO_ROOT)
    plan = plan_experiment(
        REPO_ROOT,
        REPO_ROOT / "evals/experiments/ga4-replay.json",
    )
    repeated = plan_experiment(
        REPO_ROOT,
        REPO_ROOT / "evals/experiments/ga4-replay.json",
    )

    assert len(catalog.candidates) == 2
    assert len(catalog.scenarios) == 16
    assert plan.generation_attempts == 48
    assert plan.as_dict() == repeated.as_dict()
    assert len({trial.attempt_id for trial in plan.trials}) == 48

    marketing = plan_experiment(
        REPO_ROOT,
        REPO_ROOT / "evals/experiments/marketing-creative.json",
    )
    assert marketing.generation_attempts == 24
    assert marketing.estimated_judge_calls == 12
    assert marketing.warnings == ()


def test_plugin_registry_fails_closed_for_unknown_and_duplicate_ids() -> None:
    registry: PluginRegistry[object] = PluginRegistry("test")
    registry.register("known", object, implementation_version="1")

    with pytest.raises(ValueError, match="duplicate"):
        registry.register("known", object, implementation_version="2")
    with pytest.raises(ManifestError, match="unknown test plugin"):
        registry.create("missing")


def test_evidence_redaction_removes_secret_values_and_bounds_paths(tmp_path: Path) -> None:
    value = redact(
        {
            "authorization": "Bearer should-never-survive",
            "nested": {"api_key": "example-secret-value"},
            "safe": "retained",
        }
    )

    assert value == {
        "authorization": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]"},
        "safe": "retained",
    }
    assert contained_path(tmp_path, "deliverables/report.md") == (
        tmp_path / "deliverables/report.md"
    ).resolve()
    with pytest.raises(ValueError, match="escapes"):
        contained_path(tmp_path, "../outside.txt")


def test_owned_directory_rejects_broad_or_nonempty_cleanup_roots(tmp_path: Path) -> None:
    owned = prepare_owned_directory(tmp_path / "attempt")
    assert owned.is_dir()
    (owned / "evidence.json").write_text("{}")

    with pytest.raises(ValueError, match="must be empty"):
        prepare_owned_directory(owned)
    with pytest.raises(ValueError, match="broad owned directory"):
        prepare_owned_directory(Path.home())


def test_normalized_trace_redacts_payloads_and_fails_unknown_tools_closed() -> None:
    events = upgrade_tool_trace(
        [
            AgentEvent(
                sequence=1,
                type="tool.started",
                timestamp="2026-01-01T00:00:00Z",
                data={
                    "name": "unregistered_tool",
                    "toolCallId": "call-1",
                    "args": {"authorization": "Bearer secret-token-value"},
                },
            ),
            AgentEvent(
                sequence=2,
                type="tool.completed",
                timestamp="2026-01-01T00:00:01Z",
                data={"toolCallId": "call-1", "result": {"secret": "hidden"}},
            ),
        ]
    )

    assert validate_tool_trace(events) == ()
    started, completed = (event.as_dict() for event in events)
    assert started["data"]["side_effect"] == "external_write"
    assert started["data"]["arguments_redacted"]["authorization"] == "[REDACTED]"
    assert "args" not in started["data"]
    assert "result" not in completed["data"]
    assert completed["data"]["result_sha256"]


def test_replay_ga4_and_cross_tool_services_use_only_synthetic_fixtures() -> None:
    ga4_fixture = (
        REPO_ROOT / "evals/fixtures/public/integrations/ga4/conversion-drop-v1"
    )
    ga4 = load_service(ga4_fixture, "ga4-baseline-diagnosis")
    properties = ga4.call("list_properties", {})
    assert properties["properties"]
    assert properties["fixed_clock"]

    cross_fixture = (
        REPO_ROOT
        / "evals/fixtures/public/integrations/marketing-funnel/cross-tool-v1"
    )
    cross = load_service(cross_fixture, "ga4-search-console")
    integrations = cross.call("list_integrations", {})
    assert integrations["integrations"]
    assert "credential" not in json.dumps(integrations).lower()


def test_clean_room_boundary_contains_no_private_magister_code() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export-eval-runner.py", "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["private_paths_included"] == []
    assert payload["private_content_included"] == []
