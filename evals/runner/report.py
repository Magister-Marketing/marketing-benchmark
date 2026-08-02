"""Human-readable report helpers."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .engine import RunPlan
from .evidence import write_json
from .stats import mean, percentile, wilson_interval


def render_plan_markdown(plan: RunPlan) -> str:
    temperature_requests = {
        candidate["id"]: candidate["settings"]["temperature"]
        for candidate in plan.candidates
    }
    temperature_summary = ", ".join(
        f"{candidate_id}={request['mode']}"
        + (f"({request['value']})" if request.get("mode") == "set" else "")
        for candidate_id, request in temperature_requests.items()
    )
    lines = [
        f"# Eval plan: {plan.experiment_id}",
        "",
        f"- Generation attempts: {plan.generation_attempts}",
        f"- Maximum model calls declared by scenarios: {plan.maximum_model_calls}",
        f"- Estimated subjective judge calls: {plan.estimated_judge_calls}",
        f"- Configured provider-cost cap: ${plan.configured_cost_cap_usd:.2f}",
        f"- Sum of per-attempt safety ceilings: ${plan.conservative_cost_ceiling_usd:.2f}",
        f"- Deadline: {plan.deadline_seconds} seconds",
        f"- Requested concurrency: {plan.concurrency}",
        f"- Temperature requests: {temperature_summary}",
        "",
        "## Candidates",
        "",
        "| Candidate | Model | Effort | Verbosity | Temperature | Adapter |",
        "|---|---|---|---|---|---|",
    ]
    for candidate in plan.candidates:
        lines.append(
            "| {id} | {model} | {effort} | {verbosity} | {temperature} | {adapter} |".format(
                id=candidate["id"],
                model=candidate["model"],
                effort=candidate["effort"] or "provider default",
                verbosity=candidate["verbosity"] or "not supported",
                temperature=(
                    str(candidate["settings"]["temperature"].get("value"))
                    if candidate["settings"]["temperature"]["mode"] == "set"
                    else candidate["settings"]["temperature"]["mode"]
                ),
                adapter=candidate["agent_adapter"] or "selected at run time",
            )
        )
    lines.extend(["", "## Scenarios", ""])
    for scenario in plan.scenarios:
        lines.append(
            f"- `{scenario['id']}` ({scenario['task_family']}): "
            f"evals={', '.join(scenario.get('evaluation_types') or []) or 'legacy'}, "
            f"skills={', '.join(scenario['required_skill_reads']) or 'none'}, "
            f"UI={'required' if scenario['require_ui_spec'] else 'optional'}"
        )
    lines.extend(["", "## Forbidden side effects", ""])
    lines.extend(f"- `{item}`" for item in plan.forbidden_side_effects)
    if plan.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in plan.warnings)
    return "\n".join(lines) + "\n"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def aggregate_run_results(
    attempts: list[dict[str, Any]],
    grades: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate valid model outputs while retaining excluded-run diagnostics."""
    grade_by_attempt = {grade["attempt_id"]: grade for grade in grades}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        grade = grade_by_attempt.get(attempt["attempt_id"])
        if not grade:
            continue
        mode = str(
            grade.get("environment_mode")
            or (attempt.get("dimensions", {}).get("environment") or {}).get("mode")
            or "none"
        )
        grouped[(attempt["candidate_id"], grade["task_family"], mode)].append(
            {"attempt": attempt, "grade": grade}
        )

    aggregates: list[dict[str, Any]] = []
    for (candidate_id, task_family, environment_mode), rows in sorted(grouped.items()):
        eligible = [row for row in rows if row["attempt"].get("status") == "completed"]
        contaminated = [
            row for row in rows if row["attempt"].get("status") == "contaminated"
        ]
        infrastructure = [
            row
            for row in rows
            if row["attempt"].get("status") not in {"completed", "contaminated"}
        ]
        hard_passes = sum(
            1 for row in eligible if row["grade"]["hard_gate_passed"]
        )
        interval = (
            wilson_interval(hard_passes, len(eligible)) if eligible else None
        )
        programmatic = [
            float(value)
            for row in eligible
            if (value := row["grade"]["scores"].get("programmatic_pass_rate"))
            is not None
        ]
        costs = [float(row["attempt"].get("provider_cost_usd") or 0) for row in rows]
        durations = [
            float(row["attempt"].get("timings", {}).get("completion_seconds") or 0)
            for row in eligible
        ]
        def metric_values(name: str) -> list[float]:
            return [
                float(row["attempt"].get("metrics", {}).get(name) or 0)
                for row in eligible
            ]

        aggregates.append(
            {
                "candidate_id": candidate_id,
                "task_family": task_family,
                "environment_mode": environment_mode,
                "attempts": len(rows),
                "quality_attempts": len(eligible),
                "contaminated_attempts": len(contaminated),
                "infrastructure_failures": len(infrastructure),
                "attempt_statuses": {
                    status: sum(
                        1 for row in rows if row["attempt"].get("status") == status
                    )
                    for status in sorted(
                        {str(row["attempt"].get("status")) for row in rows}
                    )
                },
                "hard_gate_pass_rate": (
                    hard_passes / len(eligible) if eligible else None
                ),
                "hard_gate_wilson_95": list(interval) if interval else None,
                "programmatic_pass_rate": mean(programmatic),
                "provider_cost_usd": round(sum(costs), 6),
                "cost_per_hard_gate_pass_usd": (
                    round(sum(costs) / hard_passes, 6) if hard_passes else None
                ),
                "mean_completion_seconds": mean(durations),
                "p95_completion_seconds": percentile(durations, 0.95),
                "mean_input_tokens": mean(metric_values("input_tokens")),
                "mean_output_tokens": mean(metric_values("output_tokens")),
                "mean_cache_read_tokens": mean(metric_values("cache_read_tokens")),
                "mean_cache_write_tokens": mean(metric_values("cache_write_tokens")),
                "mean_tool_calls": mean(metric_values("tool_calls")),
                "mean_tool_errors": mean(metric_values("tool_errors")),
                "subjective_score": None,
            }
        )
    return aggregates


_EVALUATION_TYPE_ORDER = (
    "general_chat",
    "skill_use",
    "ui_rendering",
    "integration",
)


def build_scorecards(
    manifest: dict[str, Any],
    attempts: list[dict[str, Any]],
    grades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate product-facing scores over every planned attempt.

    Unlike conditional model-quality aggregates, missing, contaminated, and
    infrastructure-failed cells stay in the denominator. Category scores are
    macro-averaged by scenario so a larger suite cannot dominate a capability.
    """

    attempt_by_id = {str(row["attempt_id"]): row for row in attempts}
    grade_by_id = {str(row["attempt_id"]): row for row in grades}
    scenario_by_id = {
        str(row["id"]): row for row in manifest.get("scenarios") or []
    }
    evaluation_types_by_scenario: dict[str, list[str]] = {
        scenario_id: list(row.get("evaluation_types") or [])
        for scenario_id, row in scenario_by_id.items()
    }
    for grade in grades:
        scenario_id = str(grade.get("scenario_id") or "")
        if scenario_id and not evaluation_types_by_scenario.get(scenario_id):
            evaluation_types_by_scenario[scenario_id] = list(
                grade.get("evaluation_types") or []
            )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trial in manifest.get("trials") or []:
        attempt_id = str(trial.get("attempt_id") or "")
        candidate_id = str(trial.get("candidate_id") or "")
        scenario_id = str(trial.get("scenario_id") or "")
        scenario = scenario_by_id.get(scenario_id, {})
        attempt = attempt_by_id.get(attempt_id)
        grade = grade_by_id.get(attempt_id)
        mode = str(
            (scenario.get("environment") or {}).get("mode")
            or (grade or {}).get("environment_mode")
            or "none"
        )
        status = str((attempt or {}).get("status") or "missing")
        executed = status == "completed" and grade is not None
        complete = executed and bool(
            (grade or {}).get(
                "complete_passed",
                bool((grade or {}).get("hard_gate_passed"))
                and all(
                    bool(check.get("passed"))
                    for check in ((grade or {}).get("scores") or {}).get(
                        "programmatic", []
                    )
                ),
            )
        )
        category_results = (grade or {}).get("category_results") or {}
        category_passes = {
            evaluation_type: (
                executed
                and bool((category_results.get(evaluation_type) or {}).get("passed"))
            )
            for evaluation_type in evaluation_types_by_scenario.get(scenario_id, [])
        }
        grouped[(candidate_id, mode)].append(
            {
                "attempt_id": attempt_id,
                "scenario_id": scenario_id,
                "status": status,
                "executed": executed,
                "complete": complete,
                "category_passes": category_passes,
                "attempt": attempt,
            }
        )

    rows: list[dict[str, Any]] = []
    for (candidate_id, mode), cells in sorted(grouped.items()):
        planned = len(cells)
        execution_passes = sum(1 for cell in cells if cell["executed"])
        complete_passes = sum(1 for cell in cells if cell["complete"])

        def binary_interval(passes: int, total: int) -> list[float] | None:
            if total == 0:
                return None
            return list(wilson_interval(passes, total))

        categories: dict[str, Any] = {}
        for evaluation_type in _EVALUATION_TYPE_ORDER:
            applicable = [
                cell
                for cell in cells
                if evaluation_type in cell["category_passes"]
            ]
            if not applicable:
                categories[evaluation_type] = None
                continue
            scenario_cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for cell in applicable:
                scenario_cells[cell["scenario_id"]].append(cell)
            scenario_rates = {
                scenario_id: (
                    sum(
                        1
                        for cell in values
                        if cell["category_passes"][evaluation_type]
                    )
                    / len(values)
                )
                for scenario_id, values in sorted(scenario_cells.items())
            }
            passes = sum(
                1 for cell in applicable if cell["category_passes"][evaluation_type]
            )
            categories[evaluation_type] = {
                "score": mean(list(scenario_rates.values())),
                "passes": passes,
                "planned": len(applicable),
                "wilson_95": binary_interval(passes, len(applicable)),
                "scenario_rates": scenario_rates,
                "thin_evidence": len(applicable) < 10,
            }

        completed_attempts = [
            cell["attempt"]
            for cell in cells
            if cell["executed"] and cell["attempt"] is not None
        ]
        durations = [
            float(attempt.get("timings", {}).get("completion_seconds") or 0)
            for attempt in completed_attempts
        ]
        costs = [
            float(cell["attempt"].get("provider_cost_usd") or 0)
            for cell in cells
            if cell["attempt"] is not None
        ]
        statuses = sorted({str(cell["status"]) for cell in cells})
        rows.append(
            {
                "candidate_id": candidate_id,
                "environment_mode": mode,
                "planned_attempts": planned,
                "execution_passes": execution_passes,
                "execution_rate": execution_passes / planned if planned else None,
                "execution_wilson_95": binary_interval(execution_passes, planned),
                "end_to_end_passes": complete_passes,
                "end_to_end_rate": complete_passes / planned if planned else None,
                "end_to_end_wilson_95": binary_interval(complete_passes, planned),
                "categories": categories,
                "attempt_statuses": {
                    status: sum(1 for cell in cells if cell["status"] == status)
                    for status in statuses
                },
                "mean_completion_seconds": mean(durations),
                "provider_cost_usd": round(sum(costs), 6),
                "thin_evidence": planned < 10,
            }
        )
    return {
        "schema_version": 1,
        "denominator": "planned_attempts",
        "category_aggregation": "macro_average_of_scenario_pass_rates",
        "rows": rows,
    }


_CAPABILITY_GATE_AXES: dict[str, tuple[str, ...]] = {
    "tool_contract": ("integration_", "cross_tool_completed_reads"),
    "analytical_correctness": (
        "ga4_property_discovery",
        "ga4_comparison_ranges",
        "ga4_useful_drilldown",
        "ga4_pagination",
        "ga4_error_recovery",
        "ga4_live_discovery",
        "ga4_live_property_allowlist",
        "ga4_live_read_only",
        "cross_tool_quantitative_grounding",
    ),
    "grounded_output": (
        "ga4_grounded_output",
        "ga4_hostile_data",
        "ga4_live_grounded_output",
        "cross_tool_source_attribution",
        "cross_tool_definition_safety",
        "cross_tool_claim_safety",
    ),
    "artifact": ("artifact_contract",),
    "ui": ("ui_contract",),
    "skill_use": ("required_skill_reads",),
}


def _axis_pass(grade: dict[str, Any], axis: str) -> bool | None:
    if axis == "ui" and not grade.get("ui_contracts"):
        return None
    if axis == "artifact" and not grade.get("artifact_contracts"):
        return None
    selectors = _CAPABILITY_GATE_AXES[axis]
    selected = [
        gate
        for gate in grade.get("gates") or []
        if any(str(gate.get("id") or "").startswith(value) for value in selectors)
    ]
    if not selected:
        return None
    return all(bool(gate.get("passed")) for gate in selected)


def build_capability_matrix(
    attempts: list[dict[str, Any]],
    grades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report each reliability axis by capability without blending a leaderboard."""

    attempt_by_id = {row["attempt_id"]: row for row in attempts}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for grade in grades:
        attempt = attempt_by_id.get(grade["attempt_id"])
        if attempt is None:
            continue
        mode = str(
            grade.get("environment_mode")
            or (attempt.get("dimensions", {}).get("environment") or {}).get("mode")
            or "none"
        )
        for capability in grade.get("capabilities") or []:
            grouped[(attempt["candidate_id"], str(capability), mode)].append(
                {"attempt": attempt, "grade": grade}
            )

    rows: list[dict[str, Any]] = []
    for (candidate_id, capability, mode), values in sorted(grouped.items()):
        eligible = [
            value
            for value in values
            if value["attempt"].get("status") == "completed"
        ]
        hard_passes = sum(
            1 for value in eligible if value["grade"].get("hard_gate_passed")
        )
        axes: dict[str, float | None] = {}
        for axis in _CAPABILITY_GATE_AXES:
            results = [
                result
                for value in eligible
                if (result := _axis_pass(value["grade"], axis)) is not None
            ]
            axes[axis] = (
                sum(1 for result in results if result) / len(results)
                if results
                else None
            )
        unobservable = sum(
            1
            for value in values
            if (value["attempt"].get("settings") or {}).get("unobservable")
        )
        gate_failures: dict[str, int] = defaultdict(int)
        for value in eligible:
            for gate in value["grade"].get("gates") or []:
                if not gate.get("passed"):
                    gate_failures[str(gate.get("id") or "unknown")] += 1
        rows.append(
            {
                "candidate_id": candidate_id,
                "capability": capability,
                "environment_mode": mode,
                "attempts": len(values),
                "quality_attempts": len(eligible),
                "contaminated_attempts": sum(
                    1
                    for value in values
                    if value["attempt"].get("status") == "contaminated"
                ),
                "infrastructure_failures": sum(
                    1
                    for value in values
                    if value["attempt"].get("status")
                    not in {"completed", "contaminated"}
                ),
                "hard_gate_pass_rate": (
                    hard_passes / len(eligible) if eligible else None
                ),
                "hard_gate_wilson_95": (
                    list(wilson_interval(hard_passes, len(eligible)))
                    if eligible
                    else None
                ),
                "axes": axes,
                "settings_unobservable_attempts": unobservable,
                "mean_tool_calls": mean(
                    [
                        float(value["attempt"].get("metrics", {}).get("tool_calls") or 0)
                        for value in eligible
                    ]
                ),
                "mean_tool_errors": mean(
                    [
                        float(value["attempt"].get("metrics", {}).get("tool_errors") or 0)
                        for value in eligible
                    ]
                ),
                "gate_failures": dict(sorted(gate_failures.items())),
            }
        )

    recommendations: list[dict[str, Any]] = []
    by_capability: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_capability[(row["capability"], row["environment_mode"])].append(row)
    for (capability, environment_mode), candidates in sorted(by_capability.items()):
        rankable = [row for row in candidates if row["quality_attempts"] > 0]

        def rank_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
            axes = row["axes"]
            return (
                row["hard_gate_pass_rate"] or 0.0,
                axes["tool_contract"] or 0.0,
                axes["analytical_correctness"] or 0.0,
                axes["grounded_output"] or 0.0,
            )

        ranked = sorted(rankable, key=rank_key, reverse=True)
        winner = ranked[0] if ranked else None
        caveats: list[str] = []
        if winner is None:
            caveats.append("no quality attempts")
        elif winner["quality_attempts"] < ROUTING_MIN_QUALITY_ATTEMPTS:
            caveats.append(
                f"only {winner['quality_attempts']} quality attempt(s); repeat before routing"
            )
        recommendations.append(
            {
                "capability": capability,
                "recommended_candidate": winner["candidate_id"] if winner else None,
                "environment_mode": environment_mode,
                "caveats": caveats,
                "candidates": [row["candidate_id"] for row in ranked],
            }
        )
    return {
        "schema_version": 1,
        "axes": sorted(_CAPABILITY_GATE_AXES),
        "rows": rows,
        "recommendations": recommendations,
    }


def attach_subjective_results(
    aggregates: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach transparent pairwise W/T/L metrics without creating one score."""
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "wins": 0,
            "ties": 0,
            "losses": 0,
            "judge_ids": set(),
        }
    )
    pair_winners: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        candidate_a = str(row["candidate_a_id"])
        candidate_b = str(row["candidate_b_id"])
        family = str(row["task_family"])
        mode = str(row.get("environment_mode") or "none")
        winner = row.get("winner_candidate_id")
        judge_id = str(row["judge_id"])
        pair_winners[str(row["pair_id"])].append(str(winner or "tie"))
        for candidate, opponent in ((candidate_a, candidate_b), (candidate_b, candidate_a)):
            record = grouped[(candidate, family, mode)]
            record["judge_ids"].add(judge_id)
            if winner is None:
                record["ties"] += 1
            elif winner == candidate:
                record["wins"] += 1
            elif winner == opponent:
                record["losses"] += 1

    for aggregate in aggregates:
        result = grouped.get(
            (
                aggregate["candidate_id"],
                aggregate["task_family"],
                str(aggregate.get("environment_mode") or "none"),
            )
        )
        if not result:
            continue
        total = result["wins"] + result["ties"] + result["losses"]
        aggregate["subjective_score"] = {
            "pairs": total,
            "wins": result["wins"],
            "ties": result["ties"],
            "losses": result["losses"],
            "pairwise_points_rate": (
                (result["wins"] + 0.5 * result["ties"]) / total if total else None
            ),
            "judge_ids": sorted(result["judge_ids"]),
        }

    comparable = [values for values in pair_winners.values() if len(values) > 1]
    agreements = sum(1 for values in comparable if len(set(values)) == 1)
    return {
        "judge_ids": sorted({str(row["judge_id"]) for row in rows}),
        "decisions": len(rows),
        "multiply_judged_pairs": len(comparable),
        "exact_agreement_rate": agreements / len(comparable) if comparable else None,
    }


ROUTING_MIN_QUALITY_ATTEMPTS = 3


def build_routing_recommendations(
    aggregates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rank candidates per task family for a future task-aware model router.

    The ranking is transparent and lexicographic, never one blended score:
    hard-gate pass rate first (a reliability floor creative quality cannot
    offset), then blinded pairwise points, then objective checks, then lower
    cost per hard-gate pass. The output is decision support for choosing a
    default plus per-family specialist routes; thin evidence is stated as a
    caveat rather than hidden.
    """
    families: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in aggregates:
        families[
            (
                row["task_family"],
                str(row.get("environment_mode") or "none"),
            )
        ].append(row)

    def sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
        subjective = row.get("subjective_score") or {}
        points = subjective.get("pairwise_points_rate")
        cost_per_pass = row.get("cost_per_hard_gate_pass_usd")
        return (
            -1.0 if row["hard_gate_pass_rate"] is None else row["hard_gate_pass_rate"],
            -1.0 if points is None else points,
            -1.0
            if row["programmatic_pass_rate"] is None
            else row["programmatic_pass_rate"],
            float("-inf") if cost_per_pass is None else -cost_per_pass,
        )

    def evidence(row: dict[str, Any]) -> dict[str, Any]:
        subjective = row.get("subjective_score") or {}
        return {
            "candidate_id": row["candidate_id"],
            "quality_attempts": row["quality_attempts"],
            "hard_gate_pass_rate": row["hard_gate_pass_rate"],
            "hard_gate_wilson_95": row["hard_gate_wilson_95"],
            "pairwise_points_rate": subjective.get("pairwise_points_rate"),
            "programmatic_pass_rate": row["programmatic_pass_rate"],
            "cost_per_hard_gate_pass_usd": row["cost_per_hard_gate_pass_usd"],
            "mean_completion_seconds": row["mean_completion_seconds"],
        }

    result_families: list[dict[str, Any]] = []
    for (task_family, environment_mode), rows in sorted(families.items()):
        rankable = [row for row in rows if row["quality_attempts"] > 0]
        ranked = sorted(rankable, key=sort_key, reverse=True)
        caveats: list[str] = []
        recommended = ranked[0] if ranked else None
        if not ranked:
            caveats.append("no candidate produced a quality attempt")
        else:
            if all(
                (row.get("subjective_score") or {}).get("pairwise_points_rate")
                is None
                for row in ranked
            ):
                caveats.append(
                    "no blinded subjective judging was imported; ranking uses "
                    "hard gates, objective checks, and cost only"
                )
            if recommended["quality_attempts"] < ROUTING_MIN_QUALITY_ATTEMPTS:
                caveats.append(
                    f"only {recommended['quality_attempts']} quality attempt(s); "
                    f"rerun with at least {ROUTING_MIN_QUALITY_ATTEMPTS} "
                    "repetitions before acting"
                )
            interval = recommended.get("hard_gate_wilson_95")
            if interval and interval[1] - interval[0] > 0.5:
                caveats.append(
                    "hard-gate confidence interval is wider than 50 points"
                )
            if len(ranked) > 1 and sort_key(ranked[0]) == sort_key(ranked[1]):
                caveats.append(
                    "top candidates are exactly tied on every ranking axis"
                )
            excluded = [row for row in rows if row["quality_attempts"] == 0]
            if excluded:
                caveats.append(
                    "unrankable (zero quality attempts): "
                    + ", ".join(sorted(row["candidate_id"] for row in excluded))
                )
        result_families.append(
            {
                "task_family": task_family,
                "environment_mode": environment_mode,
                "recommended_candidate": (
                    recommended["candidate_id"] if recommended else None
                ),
                "runner_up": ranked[1]["candidate_id"] if len(ranked) > 1 else None,
                "caveats": caveats,
                "candidates": [evidence(row) for row in ranked],
            }
        )
    return {
        "schema_version": 1,
        "method": (
            "lexicographic per task family: hard-gate pass rate, then blinded "
            "pairwise points rate, then objective check pass rate, then lower "
            "cost per hard-gate pass; no blended score"
        ),
        "families": result_families,
    }


def build_run_report(run_dir: Path) -> Path:
    attempts = _read_jsonl(run_dir / "attempts.jsonl")
    grades_path = run_dir / "grades" / "deterministic-v1.jsonl"
    if not grades_path.is_file():
        raise FileNotFoundError("run must be graded before reporting")
    grades = _read_jsonl(grades_path)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    comparison_mode = str(manifest.get("comparison_mode") or "model")
    aggregates = aggregate_run_results(attempts, grades)
    scorecards = build_scorecards(manifest, attempts, grades)
    capability_matrix = build_capability_matrix(attempts, grades)
    subjective_rows = [
        row
        for path in sorted((run_dir / "grades").glob("subjective-*.jsonl"))
        for row in _read_jsonl(path)
    ]
    subjective_summary = attach_subjective_results(aggregates, subjective_rows)

    lines = [
        f"# Eval report: {run_dir.name}",
        "",
        f"Comparison mode: `{comparison_mode}`.",
        "",
        "Reliability, objective marketing checks, cost, and latency are shown separately. "
        "Subjective creative judging has not been run when its column is blank.",
        "",
        "Contaminated and infrastructure attempts are shown but excluded from quality denominators.",
    ]
    if scorecards["rows"]:
        lines.extend(
            [
                "",
                "## Product scorecards",
                "",
                "Execution and end-to-end rates use every planned attempt. Capability scores are macro-averaged by scenario; missing, contaminated, and infrastructure attempts do not pass.",
                "",
                "| Candidate | Mode | Planned | Execution | End-to-end | General chat | Skill use | UI rendering | Integrations |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )

        def scorecard_cell(value: dict[str, Any] | None) -> str:
            if value is None or value.get("score") is None:
                return "—"
            return (
                f"{float(value['score']):.0%} "
                f"({int(value['passes'])}/{int(value['planned'])})"
            )

        for row in scorecards["rows"]:
            categories = row["categories"]
            lines.append(
                "| {candidate} | {mode} | {planned} | {execution:.0%} ({execution_passes}/{planned}) | "
                "{end_to_end:.0%} ({end_to_end_passes}/{planned}) | {chat} | {skills} | {ui} | {integration} |".format(
                    candidate=row["candidate_id"],
                    mode=row["environment_mode"],
                    planned=row["planned_attempts"],
                    execution=row["execution_rate"] or 0,
                    execution_passes=row["execution_passes"],
                    end_to_end=row["end_to_end_rate"] or 0,
                    end_to_end_passes=row["end_to_end_passes"],
                    chat=scorecard_cell(categories["general_chat"]),
                    skills=scorecard_cell(categories["skill_use"]),
                    ui=scorecard_cell(categories["ui_rendering"]),
                    integration=scorecard_cell(categories["integration"]),
                )
            )
    lines.extend(
        [
        "",
        "## Conditional model-quality results",
        "",
        "| Candidate | Domain | Mode | All | Quality | Contam. | Infra | Hard gates (95% CI) | Objective checks | Cost | Cost/pass | Mean sec | p95 sec | Subjective |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in aggregates:
        interval = row["hard_gate_wilson_95"]
        objective = row["programmatic_pass_rate"]
        hard_gate_rate = row["hard_gate_pass_rate"]
        subjective = row["subjective_score"]
        lines.append(
            "| {candidate} | {family} | {mode} | {attempts} | {quality} | {contaminated} | {infra} | "
            "{hard_gates} | {objective} | ${cost:.4f} | {cost_pass} | {mean_sec:.1f} | {p95:.1f} | {subjective} |".format(
                candidate=row["candidate_id"],
                family=row["task_family"],
                mode=row["environment_mode"],
                attempts=row["attempts"],
                quality=row["quality_attempts"],
                contaminated=row["contaminated_attempts"],
                infra=row["infrastructure_failures"],
                hard_gates=(
                    "—"
                    if hard_gate_rate is None or interval is None
                    else f"{hard_gate_rate:.0%} ({interval[0]:.0%}–{interval[1]:.0%})"
                ),
                objective="—" if objective is None else f"{objective:.0%}",
                cost=row["provider_cost_usd"],
                cost_pass=(
                    "—"
                    if row["cost_per_hard_gate_pass_usd"] is None
                    else f"${row['cost_per_hard_gate_pass_usd']:.4f}"
                ),
                mean_sec=row["mean_completion_seconds"] or 0,
                p95=row["p95_completion_seconds"] or 0,
                subjective=(
                    "—"
                    if subjective is None
                    else (
                        f"{subjective['wins']}/{subjective['ties']}/"
                        f"{subjective['losses']} "
                        f"({subjective['pairwise_points_rate']:.0%})"
                    )
                ),
            )
        )
    if capability_matrix["rows"]:
        lines.extend(
            [
                "",
                "## Capability matrix",
                "",
                "Tool protocol, analytical correctness, grounded output, artifact, and UI remain separate axes. Live and replay evidence are never pooled.",
                "",
                "| Candidate | Capability | Mode | Quality | Hard gates | Tool contract | Analysis | Grounding | Artifact | UI | Skill use | Setting gaps | Tool errors |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )

        def rate(value: float | None) -> str:
            return "—" if value is None else f"{value:.0%}"

        for row in capability_matrix["rows"]:
            axes = row["axes"]
            lines.append(
                "| {candidate} | {capability} | {mode} | {quality} | {hard} | "
                "{tool} | {analysis} | {grounding} | {artifact} | {ui} | {skills} | {gaps} | "
                "{errors} |".format(
                    candidate=row["candidate_id"],
                    capability=row["capability"],
                    mode=row["environment_mode"],
                    quality=row["quality_attempts"],
                    hard=rate(row["hard_gate_pass_rate"]),
                    tool=rate(axes["tool_contract"]),
                    analysis=rate(axes["analytical_correctness"]),
                    grounding=rate(axes["grounded_output"]),
                    artifact=rate(axes["artifact"]),
                    ui=rate(axes["ui"]),
                    skills=rate(axes["skill_use"]),
                    gaps=row["settings_unobservable_attempts"],
                    errors=(
                        "—"
                        if row["mean_tool_errors"] is None
                        else f"{row['mean_tool_errors']:.1f}"
                    ),
                )
            )
    if subjective_summary["judge_ids"]:
        agreement = subjective_summary["exact_agreement_rate"]
        lines.extend(
            [
                "",
                "## Subjective judging",
                "",
                f"- Judges: {', '.join(subjective_summary['judge_ids'])}",
                f"- Pair decisions: {subjective_summary['decisions']}",
                (
                    "- Cross-judge exact agreement: not available"
                    if agreement is None
                    else f"- Cross-judge exact agreement: {agreement:.0%}"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Efficiency and agent behavior",
            "",
            "Means below use only uncontaminated, infrastructure-successful attempts.",
            "",
            "| Candidate | Domain | Mode | Input tokens | Output tokens | Cache read | Cache write | Tool calls | Tool errors |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in aggregates:
        def display(value: float | None) -> str:
            return "—" if value is None else f"{value:.1f}"

        lines.append(
            "| {candidate} | {family} | {mode} | {input_tokens} | {output_tokens} | "
            "{cache_read} | {cache_write} | {tool_calls} | {tool_errors} |".format(
                candidate=row["candidate_id"],
                family=row["task_family"],
                mode=row["environment_mode"],
                input_tokens=display(row["mean_input_tokens"]),
                output_tokens=display(row["mean_output_tokens"]),
                cache_read=display(row["mean_cache_read_tokens"]),
                cache_write=display(row["mean_cache_write_tokens"]),
                tool_calls=display(row["mean_tool_calls"]),
                tool_errors=display(row["mean_tool_errors"]),
            )
        )
    routing = build_routing_recommendations(aggregates)
    lines.extend(
        [
            "",
            "## Routing recommendations",
            "",
            "Best-evidenced candidate per task family, for choosing a default plus "
            "specialist routes. Ranking is lexicographic (hard gates, then blinded "
            "pairwise points, then objective checks, then cost per pass) — read the "
            "caveats before acting; `routing.json` holds the machine-readable form.",
            "",
            "| Task family | Mode | Route to | Runner-up | Evidence | Caveats |",
            "|---|---|---|---|---|---|",
        ]
    )
    for family in routing["families"]:
        top = family["candidates"][0] if family["candidates"] else None
        if top:
            interval = top["hard_gate_wilson_95"]
            points = top["pairwise_points_rate"]
            cost_per_pass = top["cost_per_hard_gate_pass_usd"]
            evidence_text = (
                f"gates {top['hard_gate_pass_rate']:.0%}"
                + (
                    f" ({interval[0]:.0%}–{interval[1]:.0%})"
                    if interval
                    else ""
                )
                + (f", pairwise {points:.0%}" if points is not None else "")
                + (
                    f", objective {top['programmatic_pass_rate']:.0%}"
                    if top["programmatic_pass_rate"] is not None
                    else ""
                )
                + (
                    f", ${cost_per_pass:.4f}/pass"
                    if cost_per_pass is not None
                    else ""
                )
            )
        else:
            evidence_text = "—"
        lines.append(
            "| {family} | {mode} | {candidate} | {runner_up} | {evidence} | {caveats} |".format(
                family=family["task_family"],
                mode=family["environment_mode"],
                candidate=family["recommended_candidate"] or "—",
                runner_up=family["runner_up"] or "—",
                evidence=evidence_text,
                caveats="; ".join(family["caveats"]) or "—",
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- A hard-gate failure is never offset by creative quality.",
            "- Infrastructure and contaminated attempts remain visible and are not model passes.",
            "- Offline quality is not evidence of CTR, revenue, rank, or conversion lift.",
            "- Compare only runs with the same fixture, prompt, runtime, skill, UI-catalog, and rubric hashes.",
            "- Routing recommendations are decision support from this run only; do not "
            "change a production default or router without repeated, calibrated evidence.",
        ]
    )
    output = run_dir / "report.md"
    output.write_text("\n".join(lines) + "\n")
    write_json(run_dir / "routing.json", routing)
    write_json(run_dir / "capability-matrix.json", capability_matrix)
    write_json(run_dir / "scorecards.json", scorecards)
    write_json(
        run_dir / "error-matrix.json",
        {
            "schema_version": 1,
            "rows": [
                {
                    "candidate_id": row["candidate_id"],
                    "capability": row["capability"],
                    "environment_mode": row["environment_mode"],
                    "attempts": row["attempts"],
                    "contaminated_attempts": row["contaminated_attempts"],
                    "infrastructure_failures": row["infrastructure_failures"],
                    "settings_unobservable_attempts": row[
                        "settings_unobservable_attempts"
                    ],
                    "gate_failures": row["gate_failures"],
                }
                for row in capability_matrix["rows"]
            ],
        },
    )
    write_json(
        run_dir / "report.json",
        {
            "schema_version": 1,
            "aggregates": aggregates,
            "subjective": subjective_summary,
            "routing": routing,
            "comparison_mode": comparison_mode,
            "capabilities": capability_matrix,
            "scorecards": scorecards,
        },
    )
    return output
