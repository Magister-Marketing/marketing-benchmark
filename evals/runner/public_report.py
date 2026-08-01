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

    rows: list[dict[str, Any]] = []
    for candidate_id, candidate_aggregates in sorted(aggregates_by_candidate.items()):
        candidate = candidate_by_id.get(candidate_id, {"id": candidate_id})
        candidate_complete = complete_results.get(candidate_id, [])
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

        rows.append(
            {
                "candidate_id": candidate_id,
                "label": _candidate_label(candidate),
                "model": candidate.get("model"),
                "effort": candidate.get("effort"),
                "verbosity": candidate.get("verbosity"),
                "temperature": (candidate.get("settings") or {}).get("temperature"),
                "complete_pass_rate": (
                    sum(1 for value in candidate_complete if value)
                    / len(candidate_complete)
                    if candidate_complete
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
                "estimated_cost_usd": round(
                    sum(
                        float(aggregate.get("provider_cost_usd") or 0)
                        for aggregate in candidate_aggregates
                    ),
                    8,
                ),
                "input_tokens": weighted("mean_input_tokens"),
                "output_tokens": weighted("mean_output_tokens"),
                "attempts": sum(
                    int(aggregate.get("attempts") or 0)
                    for aggregate in candidate_aggregates
                ),
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
            }
        )

    ranked = sorted(
        [row for row in rows if int(row.get("attempts") or 0) > 0],
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
        passing,
        key=lambda row: float(row.get("completion_seconds") or float("inf")),
        default=None,
    )
    best_value = min(
        passing,
        key=lambda row: float(row.get("estimated_cost_usd") or float("inf")),
        default=None,
    )
    judged = any(row.get("blind_preference_rate") is not None for row in rows)
    subjective_summary = report.get("subjective") or {}
    judge_ids = list(subjective_summary.get("judge_ids") or [])
    repetitions = sorted(
        {
            int(attempt.get("repetition") or 0)
            for attempt in attempts
            if int(attempt.get("repetition") or 0) > 0
        }
    )
    scenario_ids = sorted({str(attempt["scenario_id"]) for attempt in attempts})
    caveats = [
        "This is a synthetic benchmark; it does not measure real ad delivery, CTR, revenue, or conversion lift.",
        "One task cannot establish a universal model ranking.",
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
        "total_candidate_cost_usd": round(
            sum(float(row.get("estimated_cost_usd") or 0) for row in rows), 6
        ),
        "rows": rows,
        "caveats": caveats,
        "technical_report": "report.md",
    }
    write_json(run_dir / "public-report.json", public_payload)

    labels = {row["candidate_id"]: row["label"] for row in rows}
    row_by_id = {row["candidate_id"]: row for row in rows}
    lines = [
        f"# Marketing Benchmark: quick results",
        "",
        f"Run `{run_dir.name}` compared **{len(rows)} model profiles** on "
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
        f"- **Fastest complete pass:** {fastest['label'] if fastest else 'None'}"
        + (f" ({_seconds(fastest['completion_seconds'])})." if fastest else "."),
        f"- **Lowest-cost complete pass:** {best_value['label'] if best_value else 'None'}"
        + (f" ({_cost(best_value['estimated_cost_usd'])})." if best_value else "."),
        "",
        "## Leaderboard",
        "",
        "| Profile | Complete pass | Required gates | Objective checks | Blind preference | W–T–L | Time | Est. cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
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
            f"| {row['label']} | {_percent(row['complete_pass_rate'])} | "
            f"{_percent(row['required_gate_rate'])} | "
            f"{_percent(row['objective_check_rate'])} | "
            f"{_percent(row['blind_preference_rate'])} | "
            f"{record_text} | "
            f"{_seconds(row['completion_seconds'])} | "
            f"{_cost(row['estimated_cost_usd'])} |"
        )
    lines.extend(
        [
            "",
            "## What was tested",
            "",
            "Each profile received the same synthetic brand facts, required skill, task, tools, output limits, and UI contract. Text verbosity stayed fixed and temperature was omitted; only model tier and reasoning effort changed.",
            "",
            "- **Complete pass** means both every required gate and every objective marketing check passed.",
            "- **Required gates** cover skill use, allowed-tool and safety boundaries, artifact delivery, structured UI validation, grounding, cleanup, and terminal-state honesty.",
            "- **Objective checks** cover machine-verifiable marketing constraints such as concept count and Meta copy limits.",
            "- **Blind preference** is the share of pairwise judge points after candidate identities were hidden. A tie contributes half a point.",
            "- **W–T–L** is the blind judge's win–tie–loss record against the other profiles.",
            "- **Time** is end-to-end completion time for the task. **Cost** is estimated candidate-generation cost from reported token usage and public model rates; judging cost is excluded.",
            "",
            "The run used one generation per profile. "
            + (
                f"The blind review contained {int(subjective_summary.get('decisions') or 0)} pairwise decisions from {len(judge_ids)} judge configuration."
                if judged
                else "Blind review has not been imported."
            )
            + f" Total estimated candidate-generation cost was {_cost(sum(float(row.get('estimated_cost_usd') or 0) for row in rows))}.",
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
