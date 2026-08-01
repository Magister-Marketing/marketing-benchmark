from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from evals.plugins.replay_mcp.server import load_service
from evals.runner.adapters.base import AttemptRequest
from evals.runner.adapters.openai_responses import OpenAIResponsesAdapter
from evals.runner.engine import plan_experiment
from evals.runner.events import AgentEvent, upgrade_tool_trace, validate_tool_trace
from evals.runner.evidence import contained_path, prepare_owned_directory, redact
from evals.runner.plugins import PluginRegistry
from evals.runner.public_report import build_public_report
from evals.runner.schema import Catalog, ManifestError, Trial
from evals.runner.scorers.base import ScorerContext
from evals.runner.scorers.integration import grade_tool_contract
from evals.runner.scorers.programmatic import grade_programmatic


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

    assert len(catalog.candidates) == 13
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

    openai = plan_experiment(
        REPO_ROOT,
        REPO_ROOT / "evals/experiments/openai-marketing-quick.json",
    )
    assert openai.generation_attempts == 11
    assert openai.conservative_cost_ceiling_usd == 10.8
    assert openai.warnings == ()


def test_openai_adapter_records_real_tool_artifact_and_ui_evidence(
    tmp_path: Path,
) -> None:
    catalog = Catalog.load(REPO_ROOT)
    candidate = catalog.candidates["openai-luna-high"]
    scenario = catalog.scenarios["ads-creative-angle-review"]
    adapter = OpenAIResponsesAdapter(
        repo_root=REPO_ROOT,
        run_id="openai-unit",
        deadline_seconds=60,
        api_key="example-not-a-secret",
        workspace_root=tmp_path / "workspaces",
    )
    responses = [
        {
            "id": "resp-1",
            "model": "gpt-5.6-luna",
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "output": [
                {
                    "type": "function_call",
                    "call_id": "skill-1",
                    "name": "read",
                    "arguments": json.dumps(
                        {"path": "skills/ad-creative/SKILL.md"}
                    ),
                },
                {
                    "type": "function_call",
                    "call_id": "fixture-1",
                    "name": "read",
                    "arguments": json.dumps(
                        {"path": "fixture/product-marketing.md"}
                    ),
                },
                {
                    "type": "function_call",
                    "call_id": "fixture-2",
                    "name": "read",
                    "arguments": json.dumps({"path": "fixture/sources/facts.md"}),
                },
            ],
        },
        {
            "id": "resp-2",
            "model": "gpt-5.6-luna",
            "status": "completed",
            "usage": {"input_tokens": 300, "output_tokens": 200},
            "output": [
                {
                    "type": "function_call",
                    "call_id": "write-1",
                    "name": "write",
                    "arguments": json.dumps(
                        {
                            "path": "deliverables/arc-lamp-ad-review.md",
                            "content": "# Angle 1\n" + "Grounded draft copy.\n" * 40,
                        }
                    ),
                },
                {
                    "type": "function_call",
                    "call_id": "ui-1",
                    "name": "emit_ui",
                    "arguments": json.dumps(
                        {"spec": {"type": "review", "title": "Arc Lamp ads"}}
                    ),
                },
            ],
        },
        {
            "id": "resp-3",
            "model": "gpt-5.6-luna",
            "status": "completed",
            "usage": {
                "input_tokens": 350,
                "output_tokens": 50,
                "output_tokens_details": {"reasoning_tokens": 10},
            },
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Draft and review UI ready."}
                    ],
                }
            ],
        },
    ]
    payloads: list[dict[str, object]] = []

    def fake_post(payload: dict[str, object], timeout: float) -> dict[str, object]:
        payloads.append(payload)
        return responses.pop(0)

    adapter._post = fake_post  # type: ignore[method-assign]
    output_dir = tmp_path / "evidence"
    output_dir.mkdir()
    try:
        result = adapter.run_attempt(
            AttemptRequest(
                run_id="openai-unit",
                trial=Trial(
                    attempt_id="ads--luna--r01",
                    scenario_id=scenario.id,
                    candidate_id=candidate.id,
                    repetition=1,
                    ordinal=1,
                ),
                candidate=candidate,
                scenario=scenario,
                repo_root=REPO_ROOT,
                output_dir=output_dir,
            )
        )
    finally:
        adapter.close()

    assert result.status == "completed"
    assert result.response == "Draft and review UI ready."
    assert result.settings["applied"]["reasoning_effort"] == "high"
    assert result.settings["applied"]["text_verbosity"] == "medium"
    assert result.settings["applied"]["temperature"] == "omitted"
    assert all("temperature" not in payload for payload in payloads)
    assert all(payload["reasoning"] == {"effort": "high"} for payload in payloads)
    assert all(payload["text"] == {"verbosity": "medium"} for payload in payloads)
    assert any(event.type == "skill.read" for event in result.events)
    assert any(event.type == "ui.emitted" for event in result.events)
    assert result.artifacts[0]["path"] == "deliverables/arc-lamp-ad-review.md"
    assert (output_dir / "artifacts/deliverables/arc-lamp-ad-review.md").is_file()
    assert adapter._cost("gpt-5.6-luna", 1_000, 400, 500) == pytest.approx(
        0.000728
    )


def test_public_report_is_plain_language_and_keeps_audit_link(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-123"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "experiment_id": "openai-marketing-quick",
                "comparison_mode": "model",
                "candidates": [
                    {
                        "id": "openai-terra-high",
                        "model": "openai/gpt-5.6-terra",
                        "effort": "high",
                        "verbosity": "medium",
                        "settings": {"temperature": {"mode": "omit"}},
                    }
                ],
            }
        )
    )
    (run_dir / "attempts.jsonl").write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {
                    "attempt_id": "attempt-1",
                    "candidate_id": "openai-terra-high",
                    "scenario_id": "ads-creative-angle-review",
                    "repetition": 1,
                    "status": "completed",
                },
                {
                    "attempt_id": "attempt-2",
                    "candidate_id": "openai-terra-high",
                    "scenario_id": "email-trial-activation-sequence",
                    "repetition": 1,
                    "status": "completed",
                },
            )
        )
        + "\n"
    )
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "aggregates": [
                    {
                        "candidate_id": "openai-terra-high",
                        "task_family": "ads",
                        "quality_attempts": 1,
                        "hard_gate_pass_rate": 1.0,
                        "programmatic_pass_rate": 1.0,
                        "subjective_score": {
                            "pairwise_points_rate": 0.75,
                            "wins": 1,
                            "ties": 0,
                            "losses": 0,
                            "pairs": 1,
                        },
                        "mean_completion_seconds": 12.3,
                        "provider_cost_usd": 0.041,
                        "mean_input_tokens": 1000,
                        "mean_output_tokens": 700,
                        "attempts": 1,
                        "infrastructure_failures": 0,
                        "mean_tool_errors": 0,
                    },
                    {
                        "candidate_id": "openai-terra-high",
                        "task_family": "email",
                        "quality_attempts": 1,
                        "hard_gate_pass_rate": 1.0,
                        "programmatic_pass_rate": 1.0,
                        "subjective_score": {
                            "pairwise_points_rate": 0.5,
                            "wins": 0,
                            "ties": 1,
                            "losses": 0,
                            "pairs": 1,
                        },
                        "mean_completion_seconds": 17.7,
                        "provider_cost_usd": 0.009,
                        "mean_input_tokens": 1200,
                        "mean_output_tokens": 900,
                        "attempts": 1,
                        "infrastructure_failures": 0,
                        "mean_tool_errors": 0,
                    }
                ],
                "subjective": {
                    "judge_ids": ["test-judge"],
                    "decisions": 2,
                    "multiply_judged_pairs": 0,
                    "exact_agreement_rate": None,
                },
            }
        )
    )
    (run_dir / "report.md").write_text("# Technical report\n")
    grade_dir = run_dir / "grades"
    grade_dir.mkdir()
    (grade_dir / "deterministic-v1.jsonl").write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {
                    "attempt_id": "attempt-1",
                    "hard_gate_passed": True,
                    "scores": {"programmatic": [{"id": "copy-limit", "passed": True}]},
                },
                {
                    "attempt_id": "attempt-2",
                    "hard_gate_passed": True,
                    "scores": {"programmatic": [{"id": "email-count", "passed": True}]},
                },
            )
        )
        + "\n"
    )

    output = build_public_report(run_dir)
    content = output.read_text()

    assert "Creative quality leader" in content
    assert "gpt-5.6-terra · high" in content
    assert "Blind preference" in content
    assert "[technical report](report.md)" in content
    payload = json.loads((run_dir / "public-report.json").read_text())
    assert payload["leader"] == "openai-terra-high"
    assert payload["blind_judging_imported"] is True
    assert payload["rows"][0]["complete_pass_rate"] == 1.0
    assert payload["judge_ids"] == ["test-judge"]
    assert payload["profiles"] == 1
    assert payload["rows"][0]["estimated_cost_usd"] == pytest.approx(0.05)
    assert payload["rows"][0]["task_families"] == ["ads", "email"]


def test_character_limits_accept_common_markdown_label_annotations() -> None:
    artifact = """\
## Angle 1
**Primary text (12/125):** Short copy.
**Headline** *(8/40)*: A header
**Description (9/30):** “Tiny text”

## Review checklist
- Primary text: each option is within the 125-character limit.
- Headline: each option is within the 40-character limit.
- Description: each option is within the 30-character limit.
"""
    results = grade_programmatic(
        artifact,
        [
            {"id": "primary", "kind": "labeled_character_limit", "label": "Primary text", "maximum": 125},
            {"id": "headline", "kind": "labeled_character_limit", "label": "Headline", "maximum": 40},
            {"id": "description", "kind": "labeled_character_limit", "label": "Description", "maximum": 30},
        ],
    )

    assert all(result.passed for result in results)
    assert all("1 labeled value" in result.detail for result in results)

    missing_value = grade_programmatic(
        "**Primary text:**\n**Headline:** A real headline\n",
        [
            {
                "id": "primary",
                "kind": "labeled_character_limit",
                "label": "Primary text",
                "maximum": 125,
            }
        ],
    )
    assert missing_value[0].passed is False


def test_non_integration_scenario_does_not_require_environment_capability_ledger(
    tmp_path: Path,
) -> None:
    scenario = Catalog.load(REPO_ROOT).scenarios["ads-creative-angle-review"]
    gates = grade_tool_contract(
        ScorerContext(
            repo_root=REPO_ROOT,
            attempt_dir=tmp_path,
            attempt={},
            scenario=scenario,
            events=[],
            files=[],
            response="",
            artifact_text="",
            environment={},
            oracle={},
        )
    )
    capability_gate = next(
        gate for gate in gates if gate.id == "integration_capabilities"
    )

    assert capability_gate.passed is True
    assert "no integration environment" in capability_gate.detail


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
