from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from evals.plugins.replay_mcp.server import load_service
from evals.runner.adapters.base import AttemptRequest
from evals.runner.adapters.claude_code import ClaudeCodeAdapter
from evals.runner.adapters.codex_cli import CodexCliAdapter
from evals.runner.adapters.openai_responses import OpenAIResponsesAdapter
from evals.runner.comparison import (
    build_agent_system_comparison,
    import_comparison_judging,
    prepare_comparison_judging,
)
from evals.runner.engine import plan_experiment
from evals.runner.environments.base import AttemptEnvironment, ToolBinding
from evals.runner.events import AgentEvent, upgrade_tool_trace, validate_tool_trace
from evals.runner.evidence import contained_path, prepare_owned_directory, redact
from evals.runner.grading import _category_results
from evals.runner.plugins import PluginRegistry
from evals.runner.public_report import build_public_report
from evals.runner.report import build_scorecards
from evals.runner.schema import Catalog, ManifestError, Trial
from evals.runner.scorers.base import ScorerContext
from evals.runner.scorers.integration import grade_ga4_grounding, grade_tool_contract
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
    treatment_schema = json.loads(
        (REPO_ROOT / "evals/schema/treatment-declaration.schema.json").read_text()
    )
    Draft202012Validator.check_schema(treatment_schema)
    Draft202012Validator(treatment_schema).validate(
        json.loads(
            (
                REPO_ROOT
                / "evals/treatments/magister-vs-vanilla.example.json"
            ).read_text()
        )
    )

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

    assert len(catalog.candidates) == 16
    assert len(catalog.scenarios) == 17
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


def test_scorecards_use_planned_attempts_and_macro_average_scenarios() -> None:
    manifest = {
        "scenarios": [
            {
                "id": "skill-a",
                "evaluation_types": ["skill_use"],
                "environment": {"mode": "none"},
            },
            {
                "id": "skill-b",
                "evaluation_types": ["skill_use"],
                "environment": {"mode": "none"},
            },
        ],
        "trials": [
            {
                "attempt_id": "a-1",
                "candidate_id": "candidate-a",
                "scenario_id": "skill-a",
                "repetition": 1,
            },
            {
                "attempt_id": "a-2",
                "candidate_id": "candidate-a",
                "scenario_id": "skill-a",
                "repetition": 2,
            },
            {
                "attempt_id": "b-1",
                "candidate_id": "candidate-a",
                "scenario_id": "skill-b",
                "repetition": 1,
            },
        ],
    }
    attempts = [
        {
            "attempt_id": "a-1",
            "candidate_id": "candidate-a",
            "status": "completed",
            "timings": {"completion_seconds": 10},
            "provider_cost_usd": 0.1,
        },
        {
            "attempt_id": "a-2",
            "candidate_id": "candidate-a",
            "status": "infrastructure_error",
            "provider_cost_usd": 0,
        },
    ]
    grades = [
        {
            "attempt_id": "a-1",
            "scenario_id": "skill-a",
            "hard_gate_passed": True,
            "complete_passed": True,
            "category_results": {"skill_use": {"passed": True}},
            "scores": {"programmatic": []},
        }
    ]

    scorecards = build_scorecards(manifest, attempts, grades)
    row = scorecards["rows"][0]
    assert row["planned_attempts"] == 3
    assert row["execution_rate"] == pytest.approx(1 / 3)
    assert row["end_to_end_rate"] == pytest.approx(1 / 3)
    skill = row["categories"]["skill_use"]
    assert skill["passes"] == 1
    assert skill["planned"] == 3
    # skill-a is 1/2 and skill-b is 0/1, so the scenario macro-average is 25%.
    assert skill["score"] == pytest.approx(0.25)


def test_category_grades_fail_closed_when_required_gates_are_missing() -> None:
    results = _category_results(
        ("skill_use", "ui_rendering", "integration"),
        [],
        programmatic_pass_rate=None,
    )

    assert results["skill_use"]["passed"] is False
    assert results["ui_rendering"]["passed"] is False
    assert results["integration"]["passed"] is False


def test_agent_system_comparison_pairs_runs_and_reports_uplift(
    tmp_path: Path,
) -> None:
    def write_run(name: str, *, complete: bool) -> Path:
        run_dir = tmp_path / "artifacts" / "evals" / name
        (run_dir / "grades").mkdir(parents=True)
        manifest = {
            "comparison_mode": "agent_system",
            "random_seed": 7,
            "candidates": [
                {
                    "id": f"{name}-candidate",
                    "model": "anthropic/claude-sonnet-5",
                    "settings": {
                        "reasoning_effort": {"mode": "set", "value": "high"},
                        "text_verbosity": {"mode": "omit"},
                        "temperature": {"mode": "omit"},
                        "max_output_tokens": {"mode": "set", "value": 12000},
                    },
                }
            ],
            "scenarios": [
                {
                    "id": "skill-ui",
                    "manifest_hash": "scenario-hash",
                    "prompt_hash": "prompt-hash",
                    "fixture_hash": "fixture-hash",
                    "rubric_hash": "rubric-hash",
                    "evaluation_types": ["skill_use", "ui_rendering"],
                    "ui_contracts": ["json-object@1"],
                    "environment": {"plugin": "none", "mode": "none"},
                },
                {
                    "id": "integration-replay",
                    "manifest_hash": "integration-scenario-hash",
                    "prompt_hash": "integration-prompt-hash",
                    "fixture_hash": "integration-fixture-hash",
                    "rubric_hash": "integration-rubric-hash",
                    "evaluation_types": ["integration"],
                    "ui_contracts": [],
                    "environment": {
                        "plugin": "replay-mcp",
                        "mode": "replay",
                        "fixture": "fixture-v1",
                        "clock": "2026-01-01T00:00:00Z",
                    },
                },
            ],
            "trials": [
                {
                    "attempt_id": f"{name}-attempt",
                    "candidate_id": f"{name}-candidate",
                    "scenario_id": "skill-ui",
                    "repetition": 1,
                    "ordinal": 1,
                },
                {
                    "attempt_id": f"{name}-integration-attempt",
                    "candidate_id": f"{name}-candidate",
                    "scenario_id": "integration-replay",
                    "repetition": 1,
                    "ordinal": 2,
                },
            ],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        (run_dir / "attempts.jsonl").write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    {
                        "attempt_id": f"{name}-attempt",
                        "candidate_id": f"{name}-candidate",
                        "scenario_id": "skill-ui",
                        "status": "completed",
                        "settings": {"comparison_eligible": True},
                        "provider_cost_usd": 0.1 if complete else 0.08,
                        "timings": {"completion_seconds": 10 if complete else 12},
                    },
                    {
                        "attempt_id": f"{name}-integration-attempt",
                        "candidate_id": f"{name}-candidate",
                        "scenario_id": "integration-replay",
                        "status": "completed",
                        "settings": {"comparison_eligible": True},
                        "provider_cost_usd": 0.2 if complete else 0.16,
                        "timings": {"completion_seconds": 20 if complete else 24},
                    },
                )
            )
            + "\n"
        )
        (run_dir / "grades" / "deterministic-v1.jsonl").write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    {
                        "attempt_id": f"{name}-attempt",
                        "scenario_id": "skill-ui",
                        "hard_gate_passed": complete,
                        "complete_passed": complete,
                        "evaluation_types": ["skill_use", "ui_rendering"],
                        "category_results": {
                            "skill_use": {"passed": complete},
                            "ui_rendering": {"passed": complete},
                        },
                        "scores": {"programmatic": []},
                    },
                    {
                        "attempt_id": f"{name}-integration-attempt",
                        "scenario_id": "integration-replay",
                        "hard_gate_passed": complete,
                        "complete_passed": complete,
                        "evaluation_types": ["integration"],
                        "category_results": {
                            "integration": {"passed": complete}
                        },
                        "scores": {"programmatic": []},
                    },
                )
            )
            + "\n"
        )
        return run_dir

    baseline = write_run("baseline", complete=False)
    treatment = write_run("treatment", complete=True)
    declaration = tmp_path / "declaration.json"
    declaration.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "test-comparison",
                "baseline": {
                    "id": "baseline",
                    "label": "Vanilla",
                    "runtime": "Claude Code",
                    "prompt_layer": "benchmark only",
                    "skills": "staged files",
                    "ui": "file bridge",
                    "integrations": "replay MCP",
                },
                "treatment": {
                    "id": "treatment",
                    "label": "Harness",
                    "runtime": "product agent",
                    "prompt_layer": "product orchestration",
                    "skills": "native loader",
                    "ui": "native renderer",
                    "integrations": "native tool router",
                },
                "intended_differences": ["agent harness"],
            }
        )
    )

    output = build_agent_system_comparison(
        repo_root=tmp_path,
        baseline_run_dir=baseline,
        treatment_run_dir=treatment,
        declaration_path=declaration,
    )
    payload = json.loads((output / "comparison.json").read_text())
    assert payload["valid"] is True
    assert payload["metrics"] == {}
    assert payload["reliability_record"] is None
    blocks = {row["environment_mode"]: row for row in payload["score_blocks"]}
    assert blocks["none"]["metrics"]["end_to_end"]["delta"] == 1.0
    assert blocks["none"]["metrics"]["skill_use"]["delta"] == 1.0
    assert blocks["replay"]["metrics"]["integration"]["delta"] == 1.0
    assert blocks["replay"]["reliability_record"] == {
        "wins": 1,
        "ties": 0,
        "losses": 0,
    }
    assert "not blind creative preference" in (output / "public-report.md").read_text()

    treatment_attempt_path = treatment / "attempts.jsonl"
    treatment_attempts = [
        json.loads(line)
        for line in treatment_attempt_path.read_text().splitlines()
        if line
    ]
    treatment_attempts[0]["settings"] = {
        "comparison_eligible": False,
        "mismatches": [],
        "unobservable": ["max_output_tokens"],
    }
    treatment_attempt_path.write_text(
        "\n".join(json.dumps(row) for row in treatment_attempts) + "\n"
    )
    invalid_output = build_agent_system_comparison(
        repo_root=tmp_path,
        baseline_run_dir=baseline,
        treatment_run_dir=treatment,
        declaration_path=declaration,
    )
    invalid_payload = json.loads((invalid_output / "comparison.json").read_text())
    assert invalid_payload["valid"] is False
    assert invalid_payload["metrics"] == {}
    assert any(
        "treatment.attempt" in mismatch["field"]
        for mismatch in invalid_payload["parity_mismatches"]
    )

    treatment_attempts[0]["settings"] = {"comparison_eligible": True}
    treatment_attempt_path.write_text(
        "\n".join(json.dumps(row) for row in treatment_attempts) + "\n"
    )
    treatment_manifest_path = treatment / "manifest.json"
    treatment_manifest = json.loads(treatment_manifest_path.read_text())
    treatment_manifest["trials"][1]["repetition"] = 2
    treatment_manifest_path.write_text(json.dumps(treatment_manifest))
    unmatched_output = build_agent_system_comparison(
        repo_root=tmp_path,
        baseline_run_dir=baseline,
        treatment_run_dir=treatment,
        declaration_path=declaration,
    )
    unmatched = json.loads((unmatched_output / "comparison.json").read_text())
    assert unmatched["valid"] is False
    assert any(
        mismatch["field"] == "trial.keys"
        for mismatch in unmatched["parity_mismatches"]
    )
    assert unmatched["pairing"]["missing_baseline"]
    assert unmatched["pairing"]["missing_treatment"]


def test_comparison_blind_judging_uses_only_passing_cross_run_pairs(
    tmp_path: Path,
) -> None:
    (tmp_path / "evals/candidates").mkdir(parents=True)
    (tmp_path / "evals/suites/general-chat").mkdir(parents=True)
    (tmp_path / "evals/rubrics").mkdir(parents=True)
    for source, destination in (
        (
            REPO_ROOT / "evals/candidates/claude-sonnet-5-high.json",
            tmp_path / "evals/candidates/claude-sonnet-5-high.json",
        ),
        (
            REPO_ROOT / "evals/suites/general-chat/channel-prioritization.json",
            tmp_path / "evals/suites/general-chat/channel-prioritization.json",
        ),
        (
            REPO_ROOT / "evals/rubrics/general-chat.json",
            tmp_path / "evals/rubrics/general-chat.json",
        ),
    ):
        destination.write_text(source.read_text())

    settings = {
        "reasoning_effort": {"mode": "set", "value": "high"},
        "text_verbosity": {"mode": "omit"},
        "temperature": {"mode": "omit"},
        "max_output_tokens": {"mode": "set", "value": 12000},
    }

    def write_run(name: str, system: str, response: str) -> Path:
        run_dir = tmp_path / "artifacts/evals" / name
        attempt_id = f"{system}-chat-r01"
        (run_dir / "grades").mkdir(parents=True)
        (run_dir / "raw" / attempt_id).mkdir(parents=True)
        manifest = {
            "comparison_mode": "agent_system",
            "random_seed": 42,
            "candidates": [
                {
                    "id": f"{system}-candidate",
                    "model": "anthropic/claude-sonnet-5",
                    "settings": settings,
                }
            ],
            "scenarios": [
                {
                    "id": "chat-channel-prioritization",
                    "manifest_hash": "scenario-hash",
                    "prompt_hash": "prompt-hash",
                    "fixture_hash": "fixture-hash",
                    "rubric_hash": "rubric-hash",
                    "evaluation_types": ["general_chat"],
                    "ui_contracts": [],
                    "environment": {"plugin": "none", "mode": "none"},
                }
            ],
            "trials": [
                {
                    "attempt_id": attempt_id,
                    "candidate_id": f"{system}-candidate",
                    "scenario_id": "chat-channel-prioritization",
                    "repetition": 1,
                    "ordinal": 1,
                }
            ],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        (run_dir / "attempts.jsonl").write_text(
            json.dumps(
                {
                    "attempt_id": attempt_id,
                    "candidate_id": f"{system}-candidate",
                    "scenario_id": "chat-channel-prioritization",
                    "repetition": 1,
                    "status": "completed",
                    "settings": {"comparison_eligible": True},
                    "provider_cost_usd": 0.1,
                    "timings": {"completion_seconds": 10},
                }
            )
            + "\n"
        )
        (run_dir / "grades/deterministic-v1.jsonl").write_text(
            json.dumps(
                {
                    "attempt_id": attempt_id,
                    "scenario_id": "chat-channel-prioritization",
                    "hard_gate_passed": True,
                    "complete_passed": True,
                    "evaluation_types": ["general_chat"],
                    "category_results": {"general_chat": {"passed": True}},
                    "scores": {"programmatic": []},
                }
            )
            + "\n"
        )
        (run_dir / "raw" / attempt_id / "response.json").write_text(
            json.dumps({"response": response})
        )
        return run_dir

    baseline = write_run("chat-baseline", "baseline", "A serviceable answer.")
    treatment = write_run("chat-treatment", "treatment", "A clearer answer.")
    declaration = tmp_path / "declaration.json"
    declaration.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chat-comparison",
                "baseline": {
                    "id": "baseline",
                    "label": "Vanilla",
                    "runtime": "Reference CLI",
                    "prompt_layer": "portable",
                    "skills": "portable",
                    "ui": "portable",
                    "integrations": "replay",
                },
                "treatment": {
                    "id": "treatment",
                    "label": "Harness",
                    "runtime": "product",
                    "prompt_layer": "product",
                    "skills": "native",
                    "ui": "native",
                    "integrations": "native",
                },
                "intended_differences": ["agent harness"],
            }
        )
    )
    comparison = build_agent_system_comparison(
        repo_root=tmp_path,
        baseline_run_dir=baseline,
        treatment_run_dir=treatment,
        declaration_path=declaration,
    )
    packet_path = prepare_comparison_judging(
        repo_root=tmp_path,
        comparison_dir=comparison,
        baseline_run_dir=baseline,
        treatment_run_dir=treatment,
    )
    packet = json.loads(packet_path.read_text())
    assert packet["sources"] == []
    mapping = json.loads((comparison / "judge/pair-map.json").read_text())["pairs"]
    pair_map = mapping[packet["pair_id"]]
    treatment_side = (
        "A" if pair_map["A"]["candidate_id"] == "treatment-system" else "B"
    )
    results = tmp_path / "judge-results.jsonl"
    results.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pair_id": packet["pair_id"],
                "winner": treatment_side,
                "dimension_decisions": [
                    {
                        "dimension_id": dimension["id"],
                        "winner": treatment_side,
                        "evidence": "The treatment is more specific and actionable.",
                    }
                    for dimension in packet["rubric"]["subjective_dimensions"]
                ],
                "overall_rationale": "The treatment is clearer.",
            }
        )
        + "\n"
    )
    import_comparison_judging(
        comparison_dir=comparison,
        results_path=results,
        judge_id="judge-config-1",
    )
    payload = json.loads((comparison / "comparison.json").read_text())
    blind = payload["blind_quality"]["by_environment"][0]
    assert blind["treatment_preference_rate"] == 1.0
    assert blind["wins"] == 1
    assert "Blind quality review" in (comparison / "public-report.md").read_text()
    with pytest.raises(ManifestError, match="already exist"):
        import_comparison_judging(
            comparison_dir=comparison,
            results_path=results,
            judge_id="judge-config-1",
        )


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


def test_claude_adapter_stages_fixture_manifest_and_hides_tool_discovery(
    tmp_path: Path,
) -> None:
    catalog = Catalog.load(REPO_ROOT)
    candidate = catalog.candidates["claude-sonnet-5-high"]
    scenario = catalog.scenarios["ads-creative-angle-review"]
    adapter = ClaudeCodeAdapter(
        repo_root=REPO_ROOT,
        run_id="claude-unit",
        deadline_seconds=60,
        workspace_root=tmp_path / "workspaces",
    )
    request = AttemptRequest(
        run_id="claude-unit",
        trial=Trial(
            attempt_id="claude-manifest-r01",
            scenario_id=scenario.id,
            candidate_id=candidate.id,
            repetition=1,
            ordinal=1,
        ),
        candidate=candidate,
        scenario=scenario,
        repo_root=REPO_ROOT,
        output_dir=tmp_path / "evidence",
    )

    workspace = adapter._stage_workspace(request)
    manifest = (workspace / "fixture" / "MANIFEST.md").read_text()
    prompt = adapter._prompt(request)
    assert "fixture/product-marketing.md" in manifest
    assert "fixture/sources/facts.md" in manifest
    assert "fixture/MANIFEST.md" in prompt
    assert "deliverables/ui.json" in prompt

    (workspace / "deliverables" / "ui.json").write_text(
        json.dumps({"type": "review", "title": "Arc Lamp concepts"})
    )
    ui_events = adapter._collect_ui_events(
        request,
        workspace,
        starting_sequence=4,
    )
    assert len(ui_events) == 1
    assert ui_events[0].type == "ui.emitted"
    assert ui_events[0].data["contract_id"] == "json-object@1"

    raw_lines = [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "search-1",
                            "name": "ToolSearch",
                            "input": {"query": "select:Write"},
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "search-1",
                            "content": [{"tool_name": "Write"}],
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "type": "result",
                "is_error": False,
                "result": "done",
                "usage": {},
            }
        ),
    ]
    events, _, summary = adapter._normalize(raw_lines, workspace)
    assert summary["result_seen"] is True
    assert [event.type for event in events] == [
        "backend.event",
        "backend.event",
        "turn.completed",
    ]
    assert [event.data["subtype"] for event in events[:2]] == [
        "tool_discovery",
        "tool_discovery_result",
    ]
    adapter.close()


def test_codex_adapter_uses_clean_exec_and_normalizes_skill_reads(
    tmp_path: Path,
) -> None:
    catalog = Catalog.load(REPO_ROOT)
    candidate = catalog.candidates["codex-terra-xhigh"]
    scenario = catalog.scenarios["ads-creative-angle-review"]
    adapter = CodexCliAdapter(
        repo_root=REPO_ROOT,
        run_id="codex-unit",
        deadline_seconds=60,
        workspace_root=tmp_path / "workspaces",
    )
    request = AttemptRequest(
        run_id="codex-unit",
        trial=Trial(
            attempt_id="codex-skill-r01",
            scenario_id=scenario.id,
            candidate_id=candidate.id,
            repetition=1,
            ordinal=1,
        ),
        candidate=candidate,
        scenario=scenario,
        repo_root=REPO_ROOT,
        output_dir=tmp_path / "evidence",
        environment=AttemptEnvironment(
            plugin="test-replay",
            version="1",
            attempt_id="codex-skill-r01",
            mode="replay",
            bindings=(
                ToolBinding(
                    kind="mcp_stdio",
                    name="eval_integrations",
                    config={
                        "command": "/usr/bin/env",
                        "args": ["python3", "server.py"],
                        "env": {"EVAL_ATTEMPT_ID": "codex-skill-r01"},
                    },
                ),
            ),
        ),
    )
    workspace = adapter._stage_workspace(request)
    command = adapter._command(request, adapter._prompt(request))
    joined = " ".join(command)
    assert "exec" in command
    assert "--json" in command
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert 'web_search="disabled"' in command
    assert 'shell_environment_policy.inherit="core"' in command
    assert "shell_environment_policy.ignore_default_excludes=false" in command
    assert "gpt-5.6-terra" in command
    assert "skills/ad-creative/SKILL.md" in joined
    assert "mcp_servers.eval_integrations.command" in joined
    assert 'mcp_servers."eval_integrations"' not in joined
    assert 'mcp_servers.eval_integrations.default_tools_approval_mode="approve"' in joined

    assert adapter._command_tool("node -e 'console.log(1 + 1)'") == "backend"
    assert adapter._command_tool("curl https://example.com") == "bash"
    assert adapter._command_tool("curl https://example.com | jq .") == "bash"
    assert adapter._command_tool("rm deliverables/draft.md") == "bash"
    assert adapter._command_tool("ls deliverables 2>/dev/null") == "read"
    shell_command = (
        "bash -lc 'sed -n 1,120p skills/ad-creative/SKILL.md && "
        "sed -n 1,120p fixture/MANIFEST.md'"
    )
    raw_lines = [
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "id": "command-1",
                    "type": "command_execution",
                    "command": shell_command,
                    "status": "in_progress",
                },
            }
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "command-1",
                    "type": "command_execution",
                    "command": shell_command,
                    "status": "completed",
                    "exit_code": 0,
                    "output": "skill contents",
                },
            }
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "message-1",
                    "type": "agent_message",
                    "text": "Draft ready.",
                },
            }
        ),
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 20,
                    "output_tokens": 30,
                },
            }
        ),
    ]
    events, _, summary = adapter._normalize_codex(
        raw_lines, workspace, "gpt-5.6-terra"
    )
    assert summary["result_seen"] is True
    assert summary["response"] == "Draft ready."
    skill_event = next(event for event in events if event.type == "skill.read")
    assert skill_event.data["skill"] == "ad-creative"
    assert any(
        event.type == "tool.started"
        and event.data.get("args", {}).get("path") == "fixture/MANIFEST.md"
        for event in events
    )
    assert any(event.type == "tool.completed" for event in events)
    assert events[-1].type == "turn.completed"
    adapter.close()


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


def test_public_report_keeps_fully_missing_planned_profiles(tmp_path: Path) -> None:
    run_dir = tmp_path / "missing-run"
    (run_dir / "grades").mkdir(parents=True)
    manifest = {
        "experiment_id": "missing-evidence",
        "comparison_mode": "model",
        "candidates": [
            {
                "id": "candidate-a",
                "model": "openai/gpt-5.6-terra",
                "effort": "high",
                "settings": {},
            }
        ],
        "scenarios": [
            {
                "id": "chat-a",
                "task_family": "general-chat",
                "evaluation_types": ["general_chat"],
                "environment": {"mode": "none"},
            }
        ],
        "trials": [
            {
                "attempt_id": "missing-attempt",
                "candidate_id": "candidate-a",
                "scenario_id": "chat-a",
                "repetition": 1,
            }
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    (run_dir / "attempts.jsonl").write_text("")
    (run_dir / "grades/deterministic-v1.jsonl").write_text("")
    (run_dir / "report.md").write_text("# Technical report\n")
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "aggregates": [],
                "scorecards": build_scorecards(manifest, [], []),
            }
        )
    )

    build_public_report(run_dir)
    payload = json.loads((run_dir / "public-report.json").read_text())
    row = payload["rows"][0]
    assert payload["profiles"] == 1
    assert payload["task"] == ["chat-a"]
    assert row["attempts"] == 1
    assert row["execution_rate"] == 0.0
    assert row["complete_pass_rate"] == 0.0
    assert row["estimated_cost_usd"] is None


def test_character_limits_accept_common_markdown_label_annotations() -> None:
    artifact = """\
## Angle 1
**Primary text (12/125):** Short copy.
**Headline** *(8/40)*: A header (8 chars)
**Description (9/30):** Tiny text (9 characters)

| Primary text (12/125) | Table copy. |
| **Headline** (8/40) | A table header (14/40 characters) |
| **Description** (9/30) | Table text |
| Headline | 40 characters | Every option is within the limit |

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
    assert all("2 labeled value" in result.detail for result in results)

    label_on_own_line = grade_programmatic(
        "**Primary text** *(11/125 characters)*\nCopy below.\n",
        [
            {
                "id": "primary",
                "kind": "labeled_character_limit",
                "label": "Primary text",
                "maximum": 125,
            }
        ],
    )
    assert label_on_own_line[0].passed is True

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


def test_ga4_grounding_allows_explicitly_negated_causal_language(
    tmp_path: Path,
) -> None:
    scenario = Catalog.load(REPO_ROOT).scenarios["ga4-baseline-diagnosis"]
    oracle = json.loads(
        (
            REPO_ROOT
            / "evals/fixtures/public/integrations/ga4/conversion-drop-v1/oracle.json"
        ).read_text()
    )["default"]
    evidence = (
        "Paid Search sessions landing on /pricing declined from 500 purchases "
        "to 395 while sessions moved from 10,000 to 10,100 and conversion fell "
        "from 5.0% to 3.91%. This is a hypothesis to test; the data do not "
        "establish which mechanism caused the decline."
    )

    def grounded(text: str) -> bool:
        gates = grade_ga4_grounding(
            ScorerContext(
                repo_root=REPO_ROOT,
                attempt_dir=tmp_path,
                attempt={},
                scenario=scenario,
                events=[],
                files=[],
                response=text,
                artifact_text="",
                environment={},
                oracle=oracle,
            )
        )
        return next(gate for gate in gates if gate.id == "ga4_grounded_output").passed

    assert grounded(evidence) is True
    assert grounded(evidence + " Paid Search caused the decline.") is False


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
