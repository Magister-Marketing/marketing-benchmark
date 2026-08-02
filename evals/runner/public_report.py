"""Plain-language benchmark summary backed by the technical evidence report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence import write_json


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _percent(value: Any) -> str:
    return "—" if value is None else f"{float(value):.0%}"


def _seconds(value: Any) -> str:
    return "—" if value is None else f"{float(value):.1f}s"


def _cost(value: Any) -> str:
    return "—" if value is None else f"${float(value):.4f}"


def _candidate_label(candidate: dict[str, Any]) -> str:
    model = str(candidate.get("model") or candidate.get("id") or "unknown")
    model = model.removeprefix("openai/").removeprefix("anthropic/")
    effort = candidate.get("effort") or "default"
    return f"{model} · {effort}"


def _ranking_key(row: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
    return (
        -1.0
        if row.get("complete_pass_rate") is None
        else float(row["complete_pass_rate"]),
        -1.0
        if row.get("required_gate_rate") is None
        else float(row["required_gate_rate"]),
        -1.0
        if row.get("blind_preference_rate") is None
        else float(row["blind_preference_rate"]),
        -1.0
        if row.get("objective_check_rate") is None
        else float(row["objective_check_rate"]),
        -float(row.get("completion_seconds") or float("inf")),
        -float(row.get("estimated_cost_usd") or float("inf")),
    )


def build_public_report(run_dir: Path) -> Path:
    """Write a skimmable report without replacing the audit-oriented report."""
    report_path = run_dir / "report.json"
    if not report_path.is_file():
        raise FileNotFoundError("technical report must be generated first")
    report = _read_json(report_path)
    manifest = _read_json(run_dir / "manifest.json")
    attempts = _read_jsonl(run_dir / "attempts.jsonl")
    grades = _read_jsonl(run_dir / "grades" / "deterministic-v1.jsonl")
    aggregates = list(report.get("aggregates") or [])
    scorecards = dict(report.get("scorecards") or {})
    scorecard_rows = list(scorecards.get("rows") or [])
    candidate_by_id = {
        str(candidate["id"]): candidate for candidate in manifest.get("candidates") or []
    }
    attempt_by_id = {str(attempt["attempt_id"]): attempt for attempt in attempts}
    complete_results: dict[str, list[bool]] = {}
    for grade in grades:
        attempt = attempt_by_id.get(str(grade.get("attempt_id") or ""))
        if attempt is None or attempt.get("status") != "completed":
            continue
        checks = list((grade.get("scores") or {}).get("programmatic") or [])
        complete = bool(grade.get("hard_gate_passed")) and all(
            bool(check.get("passed")) for check in checks
        )
        complete_results.setdefault(str(attempt["candidate_id"]), []).append(complete)

    aggregates_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for aggregate in aggregates:
        aggregates_by_candidate.setdefault(str(aggregate["candidate_id"]), []).append(
            aggregate
        )

    planned_candidate_ids = {
        str(trial.get("candidate_id") or "")
        for trial in manifest.get("trials") or []
        if trial.get("candidate_id")
    }
    scorecard_candidate_ids = {
        str(row.get("candidate_id") or "")
        for row in scorecard_rows
        if row.get("candidate_id")
    }
    report_candidate_ids = sorted(
        planned_candidate_ids
        | scorecard_candidate_ids
        | set(aggregates_by_candidate)
    )

    rows: list[dict[str, Any]] = []
    for candidate_id in report_candidate_ids:
        candidate_aggregates = aggregates_by_candidate.get(candidate_id, [])
        candidate = candidate_by_id.get(candidate_id, {"id": candidate_id})
        candidate_complete = complete_results.get(candidate_id, [])
        candidate_attempts = [
            attempt
            for attempt in attempts
            if str(attempt.get("candidate_id") or "") == candidate_id
        ]
        candidate_scorecards = [
            value
            for value in scorecard_rows
            if str(value.get("candidate_id")) == candidate_id
        ]
        scorecard_planned = sum(
            int(value.get("planned_attempts") or 0)
            for value in candidate_scorecards
        )
        scorecard_execution = sum(
            int(value.get("execution_passes") or 0)
            for value in candidate_scorecards
        )
        scorecard_complete = sum(
            int(value.get("end_to_end_passes") or 0)
            for value in candidate_scorecards
        )
        subjective_rows = [
            value
            for aggregate in candidate_aggregates
            if (value := aggregate.get("subjective_score"))
        ]
        wins = sum(int(value.get("wins") or 0) for value in subjective_rows)
        ties = sum(int(value.get("ties") or 0) for value in subjective_rows)
        losses = sum(int(value.get("losses") or 0) for value in subjective_rows)
        pairs = wins + ties + losses

        def weighted(field: str) -> float | None:
            values = [
                (float(aggregate[field]), int(aggregate.get("quality_attempts") or 0))
                for aggregate in candidate_aggregates
                if aggregate.get(field) is not None
                and int(aggregate.get("quality_attempts") or 0) > 0
            ]
            denominator = sum(weight for _, weight in values)
            return (
                sum(value * weight for value, weight in values) / denominator
                if denominator
                else None
            )

        observed_costs = [
            float(attempt["provider_cost_usd"])
            for attempt in candidate_attempts
            if attempt.get("provider_cost_usd") is not None
        ]
        aggregate_costs = [
            float(aggregate["provider_cost_usd"])
            for aggregate in candidate_aggregates
            if aggregate.get("provider_cost_usd") is not None
        ]
        aggregate_attempts = sum(
            int(aggregate.get("attempts") or 0)
            for aggregate in candidate_aggregates
        )
        cost_methods = {
            (
                "locally_estimated"
                if (attempt.get("dimensions") or {}).get("provider_cost_estimated")
                else "provider_reported"
            )
            for attempt in candidate_attempts
            if attempt.get("provider_cost_usd") is not None
        }
        cost_method = (
            next(iter(cost_methods))
            if len(cost_methods) == 1
            else "mixed"
            if cost_methods
            else "unavailable"
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "label": _candidate_label(candidate),
                "model": candidate.get("model"),
                "effort": candidate.get("effort"),
                "verbosity": candidate.get("verbosity"),
                "temperature": (candidate.get("settings") or {}).get("temperature"),
                "complete_pass_rate": (
                    scorecard_complete / scorecard_planned
                    if scorecard_planned
                    else (
                        sum(1 for value in candidate_complete if value)
                        / len(candidate_complete)
                        if candidate_complete
                        else None
                    )
                ),
                "execution_rate": (
                    scorecard_execution / scorecard_planned
                    if scorecard_planned
                    else None
                ),
                "required_gate_rate": weighted("hard_gate_pass_rate"),
                "objective_check_rate": weighted("programmatic_pass_rate"),
                "blind_preference_rate": (
                    (wins + 0.5 * ties) / pairs if pairs else None
                ),
                "blind_record": (
                    {
                        "wins": wins,
                        "ties": ties,
                        "losses": losses,
                        "pairs": pairs,
                    }
                    if pairs
                    else None
                ),
                "completion_seconds": weighted("mean_completion_seconds"),
                "estimated_cost_usd": (
                    round(sum(observed_costs), 8)
                    if observed_costs
                    else round(sum(aggregate_costs), 8)
                    if aggregate_costs
                    else None
                ),
                "cost_method": cost_method,
                "input_tokens": weighted("mean_input_tokens"),
                "output_tokens": weighted("mean_output_tokens"),
                "attempts": scorecard_planned or aggregate_attempts,
                "infrastructure_failures": sum(
                    int(aggregate.get("infrastructure_failures") or 0)
                    for aggregate in candidate_aggregates
                ),
                "tool_errors": weighted("mean_tool_errors"),
                "task_families": sorted(
                    {
                        str(aggregate.get("task_family") or "unknown")
                        for aggregate in candidate_aggregates
                    }
                ),
                "scorecards": candidate_scorecards,
            }
        )

    ranked = sorted(
        [
            row
            for row in rows
            if int(row.get("attempts") or 0) > 0
            and (
                row.get("execution_rate") is None
                or float(row["execution_rate"]) > 0
            )
        ],
        key=_ranking_key,
        reverse=True,
    )
    leader_id = str(ranked[0]["candidate_id"]) if ranked else None
    passing = [
        row
        for row in rows
        if row.get("complete_pass_rate") == 1.0
    ]
    fastest = min(
        [row for row in passing if row.get("completion_seconds") is not None],
        key=lambda row: float(row.get("completion_seconds") or float("inf")),
        default=None,
    )
    best_value = min(
        [row for row in passing if row.get("estimated_cost_usd") is not None],
        key=lambda row: float(row.get("estimated_cost_usd") or float("inf")),
        default=None,
    )
    judged = any(row.get("blind_preference_rate") is not None for row in rows)
    subjective_summary = report.get("subjective") or {}
    judge_ids = list(subjective_summary.get("judge_ids") or [])
    planned_trials = list(manifest.get("trials") or [])
    repetitions = sorted(
        {
            int(trial.get("repetition") or 0)
            for trial in (planned_trials or attempts)
            if int(trial.get("repetition") or 0) > 0
        }
    )
    scenario_ids = sorted(
        {
            str(scenario.get("id") or "")
            for scenario in manifest.get("scenarios") or []
            if scenario.get("id")
        }
    )
    if not scenario_ids:
        scenario_ids = sorted(
            {
                str(attempt.get("scenario_id") or "")
                for attempt in attempts
                if attempt.get("scenario_id")
            }
        )
    caveats = [
        "This is a synthetic benchmark; it does not measure real ad delivery, CTR, revenue, or conversion lift.",
        (
            "One task cannot establish a universal model ranking."
            if len(scenario_ids) == 1
            else "This small task set cannot establish a universal model ranking."
        ),
    ]
    if repetitions == [1]:
        caveats.append(
            "Each profile ran once, so the result is an exploratory screen rather than a stable production decision."
        )
    if not judged:
        caveats.append(
            "Blind creative judging has not been imported; the provisional order uses task completion, objective checks, speed, and cost."
        )
    elif len(judge_ids) == 1 and int(
        subjective_summary.get("multiply_judged_pairs") or 0
    ) == 0:
        caveats.append(
            "Blind preference comes from one judge decision per pair; repeat with an independent judge before making a production change."
        )
    if any(row.get("infrastructure_failures") for row in rows):
        caveats.append("At least one profile had an infrastructure failure and is not directly comparable.")
    if any(bool(row.get("thin_evidence")) for row in scorecard_rows):
        caveats.append(
            "At least one scorecard has fewer than 10 planned attempts; treat its percentage as directional and read the sample count."
        )
    if any(row.get("cost_method") == "locally_estimated" for row in rows):
        caveats.append(
            "At least one cost is locally estimated from token usage and configured rates rather than provider-reported."
        )

    available_costs = [
        float(row["estimated_cost_usd"])
        for row in rows
        if row.get("estimated_cost_usd") is not None
    ]

    public_payload = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "experiment_id": manifest.get("experiment_id"),
        "comparison_mode": manifest.get("comparison_mode"),
        "task": scenario_ids,
        "profiles": len(rows),
        "repetitions": repetitions,
        "leader": leader_id,
        "leader_basis": "blind creative preference" if judged else "available evidence",
        "fastest_full_pass": fastest["candidate_id"] if fastest else None,
        "lowest_cost_full_pass": best_value["candidate_id"] if best_value else None,
        "blind_judging_imported": judged,
        "judge_ids": judge_ids,
        "pairwise_decisions": subjective_summary.get("decisions"),
        "total_candidate_cost_usd": (
            round(sum(available_costs), 6) if available_costs else None
        ),
        "rows": rows,
        "scorecards": scorecards,
        "caveats": caveats,
        "technical_report": "report.md",
    }
    write_json(run_dir / "public-report.json", public_payload)

    labels = {row["candidate_id"]: row["label"] for row in rows}
    row_by_id = {row["candidate_id"]: row for row in rows}
    profile_kind = (
        "agent-system profile"
        if manifest.get("comparison_mode") == "agent_system"
        else "model profile"
    )
    if len(rows) != 1:
        profile_kind += "s"
    lines = [
        f"# Marketing Benchmark: quick results",
        "",
        f"Run `{run_dir.name}` compared **{len(rows)} "
        + profile_kind
        + "** on "
        + (", ".join(f"`{value}`" for value in scenario_ids) or "the selected task")
        + ".",
        "",
        "## At a glance",
        "",
        (
            (
                f"- **Creative quality leader:** {labels.get(leader_id, leader_id or 'No eligible result')}"
                + (
                    f" ({int((row_by_id.get(leader_id) or {}).get('blind_record', {}).get('wins') or 0)} wins, "
                    f"{int((row_by_id.get(leader_id) or {}).get('blind_record', {}).get('ties') or 0)} ties, "
                    f"{int((row_by_id.get(leader_id) or {}).get('blind_record', {}).get('losses') or 0)} losses)."
                    if judged
                    else " on the currently available evidence."
                )
            )
            if judged
            else f"- **Provisional leader:** {labels.get(leader_id, leader_id or 'No eligible result')} on the currently available evidence."
        ),
        (
            f"- **Fastest fully reliable profile:** {fastest['label']} "
            f"({_seconds(fastest['completion_seconds'])})."
            if fastest
            else "- **Fastest fully reliable profile:** none; no profile passed every planned attempt."
        ),
        (
            f"- **Lowest-cost fully reliable profile:** {best_value['label']} "
            f"({_cost(best_value['estimated_cost_usd'])})."
            if best_value
            else "- **Lowest-cost fully reliable profile:** none; no profile passed every planned attempt."
        ),
        "",
        "## Leaderboard",
        "",
        "| Profile | Execution | End-to-end | Required gates | Objective checks | Blind preference | W–T–L | Time | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    ordered_ids = [str(row["candidate_id"]) for row in ranked]
    ordered_ids.extend(sorted(set(row_by_id) - set(ordered_ids)))
    for candidate_id in ordered_ids:
        row = row_by_id[candidate_id]
        record = row.get("blind_record") or {}
        record_text = (
            f"{record.get('wins')}–{record.get('ties')}–{record.get('losses')}"
            if record
            else "—"
        )
        lines.append(
            f"| {row['label']} | {_percent(row['execution_rate'])} | "
            f"{_percent(row['complete_pass_rate'])} | "
            f"{_percent(row['required_gate_rate'])} | "
            f"{_percent(row['objective_check_rate'])} | "
            f"{_percent(row['blind_preference_rate'])} | "
            f"{record_text} | "
            f"{_seconds(row['completion_seconds'])} | "
            f"{_cost(row['estimated_cost_usd'])} ({str(row['cost_method']).replace('_', ' ')}) |"
        )
    if scorecard_rows:
        lines.extend(
            [
                "",
                "## Scores by evaluation type",
                "",
                "These scores use planned attempts as the reliability boundary. Capability scores are macro-averaged by scenario, and live and replay rows stay separate.",
                "",
                "| Profile | Mode | General chat | Skill use | UI rendering | Integrations |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )

        def category_cell(row: dict[str, Any], category: str) -> str:
            value = (row.get("categories") or {}).get(category)
            if not value or value.get("score") is None:
                return "—"
            return (
                f"{_percent(value['score'])} "
                f"({int(value['passes'])}/{int(value['planned'])})"
            )

        for scorecard in scorecard_rows:
            candidate_id = str(scorecard.get("candidate_id") or "")
            lines.append(
                f"| {labels.get(candidate_id, candidate_id)} | "
                f"{scorecard.get('environment_mode') or 'none'} | "
                f"{category_cell(scorecard, 'general_chat')} | "
                f"{category_cell(scorecard, 'skill_use')} | "
                f"{category_cell(scorecard, 'ui_rendering')} | "
                f"{category_cell(scorecard, 'integration')} |"
            )
    lines.extend(
        [
            "",
            "## What was tested",
            "",
            (
                "Each profile received the same frozen task contract. The underlying model and requested settings stay fixed while the declared agent runtime or harness changes."
                if manifest.get("comparison_mode") == "agent_system"
                else "Each profile received the same frozen task contract; the experiment changes only the declared model profile settings."
            ),
            "",
            "- **Complete pass** means both every required gate and every objective marketing check passed.",
            "- **Required gates** cover skill use, allowed-tool and safety boundaries, artifact delivery, structured UI validation, grounding, cleanup, and terminal-state honesty.",
            "- **Objective checks** cover machine-verifiable marketing constraints such as concept count and Meta copy limits.",
            "- **Blind preference** is the share of pairwise judge points after candidate identities were hidden. A tie contributes half a point.",
            "- **W–T–L** is the blind judge's win–tie–loss record against the other profiles.",
            "- **Time** is end-to-end completion time for the task. **Cost** is provider-reported where available or locally estimated from token usage and configured rates; judging cost is excluded.",
            "",
            f"The run requested up to {max(repetitions) if repetitions else 0} repetition(s) per selected profile and scenario. "
            + (
                f"The blind review contained {int(subjective_summary.get('decisions') or 0)} pairwise decisions from {len(judge_ids)} judge configuration."
                if judged
                else "Blind review has not been imported."
            )
            + f" Total recorded candidate-generation cost was {_cost(public_payload['total_candidate_cost_usd'])}.",
            "",
            "## How to interpret this",
            "",
        ]
    )
    lines.extend(f"- {caveat}" for caveat in caveats)
    lines.extend(
        [
            "",
            "For manifests, traces, gate-level evidence, token usage, and confidence intervals, see the [technical report](report.md).",
            "",
        ]
    )
    output = run_dir / "public-report.md"
    output.write_text("\n".join(lines))
    return output
