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
        grades.append(
            {
                "schema_version": 1,
                "attempt_id": attempt_id,
                "scenario_id": scenario.id,
                "candidate_id": attempt["candidate_id"],
                "task_family": scenario.task_family,
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
