"""Offline deterministic grading of immutable run evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence import write_json, write_jsonl
from .schema import Catalog
from .scorers import (
    ScorerContext,
    builtin_scorers,
    grade_contracts,
    grade_programmatic,
)
from .validators import UiValidator, UiValidatorRegistry


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _category_results(
    evaluation_types: tuple[str, ...],
    gates: list[Any],
    *,
    programmatic_pass_rate: float | None,
) -> dict[str, dict[str, Any]]:
    by_id = {str(gate.id): gate for gate in gates}

    def result(
        gate_ids: list[str],
        *,
        require_objectives: bool = False,
    ) -> dict[str, Any]:
        requested_ids = list(dict.fromkeys(gate_ids))
        selected = [
            by_id[gate_id] for gate_id in requested_ids if gate_id in by_id
        ]
        objectives_passed = (
            programmatic_pass_rate is None or programmatic_pass_rate == 1.0
        )
        passed = (
            bool(requested_ids)
            and len(selected) == len(requested_ids)
            and all(gate.passed for gate in selected)
        )
        if require_objectives:
            passed = passed and objectives_passed
        return {
            "applicable": True,
            "passed": passed,
            "gate_ids": [gate.id for gate in selected],
            "objectives_required": require_objectives,
            "objectives_passed": objectives_passed if require_objectives else None,
        }

    rows: dict[str, dict[str, Any]] = {}
    if "general_chat" in evaluation_types:
        rows["general_chat"] = result(
            [
                "allowed_tools",
                "forbidden_side_effects",
                "grounded_claims",
                "honest_terminal_state",
            ],
            require_objectives=True,
        )
    if "skill_use" in evaluation_types:
        rows["skill_use"] = result(["required_skill_reads"])
    if "ui_rendering" in evaluation_types:
        rows["ui_rendering"] = result(["ui_contract"])
    if "integration" in evaluation_types:
        integration_gate_ids = [
            "integration_tool_ledger",
            "integration_allowed_operations",
            "integration_required_operations",
            "integration_capabilities",
            "integration_side_effects",
        ]
        integration_gate_ids.extend(sorted(
            gate_id
            for gate_id in by_id
            if gate_id.startswith(("ga4_", "cross_tool_"))
        ))
        integration_gate_ids.extend(
            gate_id
            for gate_id in (
                "allowed_tools",
                "read_containment",
                "write_containment",
                "forbidden_side_effects",
                "grounded_claims",
                "honest_terminal_state",
            )
        )
        rows["integration"] = result(integration_gate_ids)
    return rows


def grade_run(
    repo_root: Path,
    run_dir: Path,
    *,
    ui_validator: UiValidator | None = None,
    ui_validators: UiValidatorRegistry | None = None,
) -> Path:
    catalog = Catalog.load(repo_root)
    attempts = _read_jsonl(run_dir / "attempts.jsonl")
    scorer_registry = builtin_scorers()
    grades: list[dict[str, Any]] = []
    for attempt in attempts:
        attempt_id = attempt["attempt_id"]
        scenario = catalog.scenarios[attempt["scenario_id"]]
        attempt_dir = run_dir / "raw" / attempt_id
        events = _read_jsonl(attempt_dir / "events.jsonl")
        files = _read_json(attempt_dir / "files.json")
        response_payload = _read_json(attempt_dir / "response.json")
        response = str(response_payload.get("response") or "")
        scenario_ui_validator = ui_validator
        ui_validation_results = []
        if ui_validators is not None and scenario.ui_contracts:
            scenario_ui_validator = ui_validators.validator_for(
                scenario.ui_contracts,
                results=ui_validation_results,
            )
        gates, artifact_text = grade_contracts(
            repo_root=repo_root,
            attempt_dir=attempt_dir,
            attempt=attempt,
            scenario=scenario,
            events=events,
            files=files,
            response=response,
            ui_validator=scenario_ui_validator,
        )
        environment = (
            _read_json(attempt_dir / "environment.json")
            if (attempt_dir / "environment.json").is_file()
            else {}
        )
        oracle = (
            _read_json(attempt_dir / "oracle.json")
            if (attempt_dir / "oracle.json").is_file()
            else {}
        )
        plugin_gates = scorer_registry.run(
            scenario.scorers,
            ScorerContext(
                repo_root=repo_root,
                attempt_dir=attempt_dir,
                attempt=attempt,
                scenario=scenario,
                events=events,
                files=files,
                response=response,
                artifact_text=artifact_text,
                environment=environment,
                oracle=oracle,
            ),
        )
        gates.extend(plugin_gates)
        rubric = _read_json(repo_root / scenario.rubric) if scenario.rubric else {}
        programmatic = grade_programmatic(
            artifact_text or response,
            rubric.get("programmatic_checks", []),
        )
        hard_gate_passed = all(gate.passed for gate in gates)
        programmatic_passed = (
            sum(1 for result in programmatic if result.passed) / len(programmatic)
            if programmatic
            else None
        )
        objective_passed = (
            programmatic_passed is None or programmatic_passed == 1.0
        )
        complete_passed = hard_gate_passed and objective_passed
        category_results = _category_results(
            scenario.evaluation_types,
            gates,
            programmatic_pass_rate=programmatic_passed,
        )
        grades.append(
            {
                "schema_version": 1,
                "attempt_id": attempt_id,
                "scenario_id": scenario.id,
                "candidate_id": attempt["candidate_id"],
                "task_family": scenario.task_family,
                "evaluation_types": list(scenario.evaluation_types),
                "capabilities": list(scenario.capabilities),
                "environment_mode": scenario.environment_mode,
                "environment_plugin": scenario.environment_plugin or "none",
                "ui_contracts": list(scenario.ui_contracts),
                "ui_validation": [
                    result.as_dict() for result in ui_validation_results
                ],
                "artifact_contracts": [
                    contract.id
                    for contract in (scenario.artifacts or (scenario.artifact,))
                    if contract.required
                ],
                "hard_gate_passed": hard_gate_passed,
                "objective_passed": objective_passed,
                "complete_passed": complete_passed,
                "category_results": category_results,
                "gates": [gate.as_dict() for gate in gates],
                "scores": {
                    "programmatic_pass_rate": programmatic_passed,
                    "programmatic": [result.as_dict() for result in programmatic],
                    "subjective": None,
                },
                "rubric_version": rubric.get("id"),
                "scorer_versions": list(scenario.scorers),
                "environment": attempt.get("dimensions", {}).get("environment"),
                "judge": None,
            }
        )
    rubric_versions = sorted(
        {
            str(grade["rubric_version"])
            for grade in grades
            if grade["rubric_version"] is not None
        }
    )
    grade_dir = run_dir / "grades"
    grade_dir.mkdir(parents=True, exist_ok=True)
    output = grade_dir / "deterministic-v1.jsonl"
    write_jsonl(output, grades)
    write_json(
        grade_dir / "summary.json",
        {
            "schema_version": 1,
            "attempts": len(grades),
            "hard_gate_passes": sum(1 for grade in grades if grade["hard_gate_passed"]),
            "rubric_versions": rubric_versions,
            "subjective_grading": "not_run",
        },
    )
    return output
