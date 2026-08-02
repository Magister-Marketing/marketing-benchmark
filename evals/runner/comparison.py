"""Offline, matched comparisons between two agent-system benchmark runs."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from .evidence import write_json, write_jsonl
from .judging import (
    _attempt_output,
    _scenario_sources,
    build_blinded_pairs,
    import_pairwise_results,
)
from .schema import Catalog, ManifestError
from .stats import mean


EVALUATION_TYPES = (
    "general_chat",
    "skill_use",
    "ui_rendering",
    "integration",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _load_run(run_dir: Path) -> dict[str, Any]:
    required = (
        run_dir / "manifest.json",
        run_dir / "attempts.jsonl",
        run_dir / "grades" / "deterministic-v1.jsonl",
    )
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise ValueError(
            f"comparison run is incomplete ({run_dir}): missing {', '.join(missing)}"
        )
    return {
        "path": run_dir,
        "manifest": _read_json(required[0]),
        "attempts": _read_jsonl(required[1]),
        "grades": _read_jsonl(required[2]),
    }


def _select_candidate(run: dict[str, Any], requested: str | None) -> dict[str, Any]:
    candidates = list(run["manifest"].get("candidates") or [])
    if requested is not None:
        matches = [row for row in candidates if str(row.get("id")) == requested]
        if len(matches) != 1:
            raise ValueError(
                f"candidate {requested!r} is not uniquely present in {run['path']}"
            )
        return matches[0]
    if len(candidates) != 1:
        raise ValueError(
            f"run {run['path']} has {len(candidates)} candidates; select one explicitly"
        )
    return candidates[0]


def _load_declaration(path: Path) -> dict[str, Any]:
    declaration = _read_json(path)
    if not isinstance(declaration, dict) or declaration.get("schema_version") != 1:
        raise ValueError("treatment declaration must be a schema-version-1 object")
    for side in ("baseline", "treatment"):
        value = declaration.get(side)
        if not isinstance(value, dict):
            raise ValueError(f"treatment declaration requires {side}")
        missing = [
            field
            for field in ("id", "label", "runtime", "prompt_layer", "skills", "ui", "integrations")
            if not isinstance(value.get(field), str) or not value[field].strip()
        ]
        if missing:
            raise ValueError(
                f"treatment declaration {side} is missing: {', '.join(missing)}"
            )
    differences = declaration.get("intended_differences")
    if (
        not isinstance(differences, list)
        or not differences
        or not all(isinstance(value, str) and value.strip() for value in differences)
    ):
        raise ValueError("treatment declaration needs intended_differences")
    return declaration


def _scenario_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in manifest.get("scenarios") or []}


def _runtime_summary(run: dict[str, Any]) -> dict[str, Any]:
    target = run["manifest"].get("target") or {}
    dimensions = target.get("dimensions") or {}
    version = (
        dimensions.get("cli_version")
        or dimensions.get("runtime_version")
        or dimensions.get("version")
        or "unavailable"
    )
    return {
        "adapter": target.get("adapter") or "unavailable",
        "version": version,
    }


def _parity_mismatches(
    baseline: dict[str, Any],
    treatment: dict[str, Any],
    baseline_candidate: dict[str, Any],
    treatment_candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []

    def compare(field: str, left: Any, right: Any) -> None:
        if _canonical(left) != _canonical(right):
            mismatches.append(
                {"field": field, "baseline": left, "treatment": right}
            )

    compare("comparison_mode.baseline", baseline["manifest"].get("comparison_mode"), "agent_system")
    compare("comparison_mode.treatment", treatment["manifest"].get("comparison_mode"), "agent_system")
    compare("candidate.model", baseline_candidate.get("model"), treatment_candidate.get("model"))
    compare("candidate.settings", baseline_candidate.get("settings"), treatment_candidate.get("settings"))
    compare("random_seed", baseline["manifest"].get("random_seed"), treatment["manifest"].get("random_seed"))

    baseline_scenarios = _scenario_map(baseline["manifest"])
    treatment_scenarios = _scenario_map(treatment["manifest"])
    compare("scenario.ids", sorted(baseline_scenarios), sorted(treatment_scenarios))
    for scenario_id in sorted(set(baseline_scenarios) & set(treatment_scenarios)):
        left = baseline_scenarios[scenario_id]
        right = treatment_scenarios[scenario_id]
        for field in (
            "manifest_hash",
            "prompt_hash",
            "fixture_hash",
            "rubric_hash",
            "evaluation_types",
            "ui_contracts",
            "environment",
        ):
            compare(f"scenario.{scenario_id}.{field}", left.get(field), right.get(field))

    def trial_keys(manifest: dict[str, Any], candidate_id: str) -> list[list[Any]]:
        return sorted(
            [
                [
                    str(trial.get("scenario_id") or ""),
                    int(trial.get("repetition") or 0),
                ]
                for trial in manifest.get("trials") or []
                if str(trial.get("candidate_id") or "") == candidate_id
            ]
        )

    compare(
        "trial.keys",
        trial_keys(baseline["manifest"], str(baseline_candidate["id"])),
        trial_keys(treatment["manifest"], str(treatment_candidate["id"])),
    )

    def observed_models(run: dict[str, Any], candidate_id: str) -> list[str]:
        return sorted(
            {
                str((attempt.get("dimensions") or {}).get("actual_model"))
                for attempt in run["attempts"]
                if str(attempt.get("candidate_id")) == candidate_id
                and str(attempt.get("status")) == "completed"
                and (attempt.get("dimensions") or {}).get("actual_model")
            }
        )

    baseline_models = observed_models(baseline, str(baseline_candidate["id"]))
    treatment_models = observed_models(treatment, str(treatment_candidate["id"]))
    if baseline_models or treatment_models:
        compare("candidate.observed_models", baseline_models, treatment_models)
    for side, models, candidate in (
        ("baseline", baseline_models, baseline_candidate),
        ("treatment", treatment_models, treatment_candidate),
    ):
        expected_model = str(candidate.get("model") or "").split("/", 1)[-1]
        if models and models != [expected_model]:
            mismatches.append(
                {
                    "field": f"candidate.observed_model.{side}",
                    "baseline": expected_model,
                    "treatment": models,
                }
            )
    return mismatches


def _completed_setting_gaps(
    run: dict[str, Any], candidate_id: str, side: str
) -> list[dict[str, Any]]:
    """Reject completed cells whose adapter could not prove requested settings."""

    gaps: list[dict[str, Any]] = []
    for attempt in run["attempts"]:
        if (
            str(attempt.get("candidate_id")) != candidate_id
            or str(attempt.get("status")) != "completed"
        ):
            continue
        settings = attempt.get("settings")
        if isinstance(settings, dict) and settings.get("comparison_eligible") is True:
            continue
        attempt_id = str(attempt.get("attempt_id") or "unknown")
        observed = {
            "comparison_eligible": False,
            "mismatches": (
                list(settings.get("mismatches") or [])
                if isinstance(settings, dict)
                else ["settings evidence missing"]
            ),
            "unobservable": (
                list(settings.get("unobservable") or [])
                if isinstance(settings, dict)
                else []
            ),
        }
        gaps.append(
            {
                "field": f"{side}.attempt.{attempt_id}.settings",
                "baseline": observed if side == "baseline" else "comparison_eligible=true",
                "treatment": observed if side == "treatment" else "comparison_eligible=true",
            }
        )
    return gaps


def _candidate_cells(
    run: dict[str, Any],
    candidate_id: str,
) -> dict[tuple[str, int], dict[str, Any]]:
    attempts = {str(row["attempt_id"]): row for row in run["attempts"]}
    grades = {str(row["attempt_id"]): row for row in run["grades"]}
    scenarios = _scenario_map(run["manifest"])
    cells: dict[tuple[str, int], dict[str, Any]] = {}
    for trial in run["manifest"].get("trials") or []:
        if str(trial.get("candidate_id")) != candidate_id:
            continue
        scenario_id = str(trial.get("scenario_id") or "")
        repetition = int(trial.get("repetition") or 0)
        attempt_id = str(trial.get("attempt_id") or "")
        attempt = attempts.get(attempt_id)
        grade = grades.get(attempt_id)
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
        evaluation_types = list(
            scenarios.get(scenario_id, {}).get("evaluation_types")
            or (grade or {}).get("evaluation_types")
            or []
        )
        environment_mode = str(
            (scenarios.get(scenario_id, {}).get("environment") or {}).get("mode")
            or (grade or {}).get("environment_mode")
            or "none"
        )
        dimensions = (attempt or {}).get("dimensions") or {}
        if attempt is None or attempt.get("provider_cost_usd") is None:
            cost_method = "unavailable"
        elif dimensions.get("provider_cost_estimated"):
            cost_method = "locally_estimated"
        else:
            cost_method = "provider_reported"
        cells[(scenario_id, repetition)] = {
            "attempt_id": attempt_id,
            "scenario_id": scenario_id,
            "repetition": repetition,
            "environment_mode": environment_mode,
            "status": status,
            "executed": executed,
            "complete": complete,
            "categories": {
                evaluation_type: (
                    executed
                    and bool(
                        (category_results.get(evaluation_type) or {}).get("passed")
                    )
                )
                for evaluation_type in evaluation_types
            },
            "completion_seconds": (
                float((attempt or {}).get("timings", {}).get("completion_seconds") or 0)
                if executed
                else None
            ),
            "provider_cost_usd": (
                float((attempt or {}).get("provider_cost_usd") or 0)
                if attempt is not None
                else 0.0
            ),
            "cost_method": cost_method,
        }
    return cells


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _paired_bootstrap_delta(
    pairs: list[tuple[float, float]],
    *,
    seed: int,
    samples: int = 10_000,
) -> list[float] | None:
    if not pairs:
        return None
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(samples):
        selected = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        deltas.append(
            sum(treatment - baseline for baseline, treatment in selected)
            / len(selected)
        )
    return [_percentile(deltas, 0.025), _percentile(deltas, 0.975)]


def _binary_metric(
    pairs: list[dict[str, Any]],
    getter: Callable[[dict[str, Any]], bool],
    *,
    seed: int,
) -> dict[str, Any]:
    values = [
        (float(getter(pair["baseline"])), float(getter(pair["treatment"])))
        for pair in pairs
    ]
    baseline_passes = int(sum(value[0] for value in values))
    treatment_passes = int(sum(value[1] for value in values))
    total = len(values)
    baseline_rate = baseline_passes / total if total else None
    treatment_rate = treatment_passes / total if total else None
    return {
        "baseline_rate": baseline_rate,
        "treatment_rate": treatment_rate,
        "delta": (
            treatment_rate - baseline_rate
            if baseline_rate is not None and treatment_rate is not None
            else None
        ),
        "delta_bootstrap_95": _paired_bootstrap_delta(values, seed=seed),
        "baseline_passes": baseline_passes,
        "treatment_passes": treatment_passes,
        "pairs": total,
        "method": "paired_bootstrap_percentile_10000",
    }


def _continuous_metric(
    pairs: list[dict[str, Any]],
    field: str,
    *,
    seed: int,
) -> dict[str, Any] | None:
    values = [
        (float(pair["baseline"][field]), float(pair["treatment"][field]))
        for pair in pairs
        if pair["baseline"].get(field) is not None
        and pair["treatment"].get(field) is not None
    ]
    if not values:
        return None
    baseline_value = mean([value[0] for value in values])
    treatment_value = mean([value[1] for value in values])
    return {
        "baseline_mean": baseline_value,
        "treatment_mean": treatment_value,
        "delta": treatment_value - baseline_value,
        "delta_bootstrap_95": _paired_bootstrap_delta(values, seed=seed),
        "pairs": len(values),
        "method": "paired_bootstrap_percentile_10000",
    }


def _format_rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _format_delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.0%}"


def _reliability_record(pairs: list[dict[str, Any]]) -> dict[str, int]:
    record = {"wins": 0, "ties": 0, "losses": 0}
    for pair in pairs:
        baseline_pass = bool(pair["baseline"]["complete"])
        treatment_pass = bool(pair["treatment"]["complete"])
        if treatment_pass and not baseline_pass:
            record["wins"] += 1
        elif baseline_pass and not treatment_pass:
            record["losses"] += 1
        else:
            record["ties"] += 1
    return record


def _metric_block(
    pairs: list[dict[str, Any]],
    *,
    environment_mode: str,
    seed: int,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "execution": _binary_metric(
            pairs, lambda value: bool(value["executed"]), seed=seed + 1
        ),
        "end_to_end": _binary_metric(
            pairs, lambda value: bool(value["complete"]), seed=seed + 2
        ),
    }
    for index, evaluation_type in enumerate(EVALUATION_TYPES, start=3):
        applicable = [
            pair
            for pair in pairs
            if evaluation_type in pair["baseline"]["categories"]
            and evaluation_type in pair["treatment"]["categories"]
        ]
        metrics[evaluation_type] = (
            _binary_metric(
                applicable,
                lambda value, category=evaluation_type: bool(
                    value["categories"].get(category)
                ),
                seed=seed + index,
            )
            if applicable
            else None
        )
    metrics["completion_seconds"] = _continuous_metric(
        pairs, "completion_seconds", seed=seed + 10
    )
    metrics["provider_cost_usd"] = _continuous_metric(
        pairs, "provider_cost_usd", seed=seed + 11
    )
    baseline_cost_methods = sorted(
        {
            str(pair["baseline"].get("cost_method") or "unavailable")
            for pair in pairs
        }
    )
    treatment_cost_methods = sorted(
        {
            str(pair["treatment"].get("cost_method") or "unavailable")
            for pair in pairs
        }
    )
    cost_warning = None
    if baseline_cost_methods != treatment_cost_methods:
        cost_warning = (
            "Cost accounting methods differ; the cost delta is directional and "
            "must not be described as exact savings."
        )
    return {
        "environment_mode": environment_mode,
        "matched_pairs": len(pairs),
        "metrics": metrics,
        "reliability_record": _reliability_record(pairs),
        "cost_methods": {
            "baseline": baseline_cost_methods,
            "treatment": treatment_cost_methods,
        },
        "cost_warning": cost_warning,
    }


def _format_interval(value: Any, *, percent: bool = True) -> str:
    if not isinstance(value, list) or len(value) != 2:
        return "—"
    if percent:
        return f"{float(value[0]):+.0%} to {float(value[1]):+.0%}"
    return f"{float(value[0]):+.3f} to {float(value[1]):+.3f}"


def _blind_cell(blind: dict[str, Any] | None, field: str) -> str:
    if not blind or blind.get("status") not in {"partial", "ready"}:
        return "—"
    if field == "baseline":
        value = blind.get("baseline_preference_rate")
    elif field == "treatment":
        value = blind.get("treatment_preference_rate")
    else:
        value = blind.get("preference_delta")
    return _format_delta(value) if field == "delta" else _format_rate(value)


def _write_public_comparison_report(output_dir: Path, payload: dict[str, Any]) -> Path:
    declaration = payload["declaration"]
    mismatches = list(payload.get("parity_mismatches") or [])
    blind_by_mode = {
        str(row.get("environment_mode") or "none"): row
        for row in (payload.get("blind_quality") or {}).get("by_environment") or []
    }
    lines = [
        "# Marketing Benchmark: agent-system comparison",
        "",
        f"Comparison `{payload['comparison_id']}` is **{'valid' if payload['valid'] else 'invalid'}**.",
        "",
        f"- Baseline: **{declaration['baseline']['label']}** (`{payload['baseline_run_id']}`)",
        f"- Treatment: **{declaration['treatment']['label']}** (`{payload['treatment_run_id']}`)",
        f"- Model: `{payload.get('model')}`",
        f"- Requested settings: `{_canonical(payload.get('settings'))}`",
        f"- Baseline runtime: `{_canonical(payload.get('runtimes', {}).get('baseline'))}`",
        f"- Treatment runtime: `{_canonical(payload.get('runtimes', {}).get('treatment'))}`",
        f"- Task families: {', '.join(payload.get('task_families') or []) or 'none'}",
        f"- Scenarios: {', '.join(payload.get('scenarios') or []) or 'none'}",
        f"- Repetitions: {', '.join(str(value) for value in payload.get('repetitions') or []) or 'none'}",
        f"- Matched planned pairs: {payload['matched_pairs']}",
    ]
    if mismatches:
        lines.extend(
            [
                "",
                "## Parity failures",
                "",
                "Scores are withheld because controls do not match.",
                "",
            ]
        )
        lines.extend(f"- `{row['field']}`" for row in mismatches)
    else:
        for block in payload.get("score_blocks") or []:
            mode = str(block["environment_mode"])
            metrics = block["metrics"]
            blind = blind_by_mode.get(mode)
            labels = {
                "execution": "Execution",
                "end_to_end": "End-to-end",
                "general_chat": "General chat",
                "skill_use": "Skill use",
                "ui_rendering": "UI rendering",
                "integration": "Integrations",
            }

            def rate(metric_id: str, side: str) -> str:
                metric = metrics.get(metric_id)
                if metric is None:
                    return "—"
                field = "delta" if side == "delta" else f"{side}_rate"
                return (
                    _format_delta(metric.get(field))
                    if side == "delta"
                    else _format_rate(metric.get(field))
                )

            time_metric = metrics.get("completion_seconds")
            cost_metric = metrics.get("provider_cost_usd")
            lines.extend(
                [
                    "",
                    f"## {mode.title()} scores and treatment uplift",
                    "",
                    "| System | Execution | End-to-end | General chat | Skill use | UI rendering | Integrations | Blind preference | Mean time | Cost / attempt |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                    f"| Baseline | {rate('execution', 'baseline')} | {rate('end_to_end', 'baseline')} | {rate('general_chat', 'baseline')} | {rate('skill_use', 'baseline')} | {rate('ui_rendering', 'baseline')} | {rate('integration', 'baseline')} | {_blind_cell(blind, 'baseline')} | "
                    + (
                        f"{time_metric['baseline_mean']:.1f}s"
                        if time_metric is not None
                        else "—"
                    )
                    + " | "
                    + (
                        f"${cost_metric['baseline_mean']:.4f}"
                        if cost_metric is not None
                        else "—"
                    )
                    + " |",
                    f"| Treatment | {rate('execution', 'treatment')} | {rate('end_to_end', 'treatment')} | {rate('general_chat', 'treatment')} | {rate('skill_use', 'treatment')} | {rate('ui_rendering', 'treatment')} | {rate('integration', 'treatment')} | {_blind_cell(blind, 'treatment')} | "
                    + (
                        f"{time_metric['treatment_mean']:.1f}s"
                        if time_metric is not None
                        else "—"
                    )
                    + " | "
                    + (
                        f"${cost_metric['treatment_mean']:.4f}"
                        if cost_metric is not None
                        else "—"
                    )
                    + " |",
                    f"| Treatment − baseline | {rate('execution', 'delta')} | {rate('end_to_end', 'delta')} | {rate('general_chat', 'delta')} | {rate('skill_use', 'delta')} | {rate('ui_rendering', 'delta')} | {rate('integration', 'delta')} | {_blind_cell(blind, 'delta')} | "
                    + (
                        f"{time_metric['delta']:+.1f}s"
                        if time_metric is not None
                        else "—"
                    )
                    + " | "
                    + (
                        f"${cost_metric['delta']:+.4f}"
                        if cost_metric is not None
                        else "—"
                    )
                    + " |",
                    "",
                    "| Evaluation | Baseline | Treatment | Treatment uplift | 95% delta interval | Pairs |",
                    "|---|---:|---:|---:|---:|---:|",
                ]
            )
            for metric_id in ("execution", "end_to_end", *EVALUATION_TYPES):
                metric = metrics.get(metric_id)
                if metric is None:
                    continue
                lines.append(
                    f"| {labels[metric_id]} | {_format_rate(metric['baseline_rate'])} "
                    f"({metric['baseline_passes']}/{metric['pairs']}) | "
                    f"{_format_rate(metric['treatment_rate'])} "
                    f"({metric['treatment_passes']}/{metric['pairs']}) | "
                    f"{_format_delta(metric['delta'])} | "
                    f"{_format_interval(metric['delta_bootstrap_95'])} | {metric['pairs']} |"
                )
            lines.append(
                f"| Blind preference | {_blind_cell(blind, 'baseline')} | "
                f"{_blind_cell(blind, 'treatment')} | {_blind_cell(blind, 'delta')} | — | "
                f"{int((blind or {}).get('judged_decisions') or 0)} |"
            )
            record = block["reliability_record"]
            lines.extend(
                [
                    "",
                    "Reliability W–T–L for the treatment: "
                    f"**{record['wins']}–{record['ties']}–{record['losses']}**. "
                    "This is deterministic end-to-end reliability, not blind creative preference.",
                    "",
                    "| Efficiency | Baseline | Treatment | Difference | 95% delta interval | Pairs |",
                    "|---|---:|---:|---:|---:|---:|",
                ]
            )
            if time_metric is not None:
                lines.append(
                    f"| Mean time | {time_metric['baseline_mean']:.1f}s | "
                    f"{time_metric['treatment_mean']:.1f}s | {time_metric['delta']:+.1f}s | "
                    f"{_format_interval(time_metric['delta_bootstrap_95'], percent=False)}s | "
                    f"{time_metric['pairs']} |"
                )
            if cost_metric is not None:
                lines.append(
                    f"| Cost / attempt | ${cost_metric['baseline_mean']:.4f} | "
                    f"${cost_metric['treatment_mean']:.4f} | ${cost_metric['delta']:+.4f} | "
                    f"{_format_interval(cost_metric['delta_bootstrap_95'], percent=False)} | "
                    f"{cost_metric['pairs']} |"
                )
            if block.get("cost_warning"):
                lines.extend(["", f"> {block['cost_warning']}"])
            if int(block.get("matched_pairs") or 0) < 10:
                lines.extend(
                    [
                        "",
                        "> Thin evidence: this block has fewer than 10 matched pairs; read the counts and interval before treating the point estimate as stable.",
                    ]
                )
            if blind and blind.get("status") in {"ready", "partial"}:
                lines.extend(
                    [
                        "",
                        "Blind quality W–T–L for the treatment: "
                        f"**{blind['wins']}–{blind['ties']}–{blind['losses']}** "
                        f"across {blind['judged_decisions']} judge decision(s).",
                    ]
                )
                dimensions = blind.get("dimensions") or {}
                if dimensions:
                    lines.extend(
                        [
                            "",
                            "| Blind dimension | Treatment W–T–L | Treatment preference | Decisions |",
                            "|---|---:|---:|---:|",
                        ]
                    )
                    for dimension_id, dimension in sorted(dimensions.items()):
                        lines.append(
                            f"| {dimension_id} | {dimension['wins']}–{dimension['ties']}–{dimension['losses']} | "
                            f"{_format_rate(dimension['treatment_preference_rate'])} | {dimension['decisions']} |"
                        )
        blind_quality = payload.get("blind_quality") or {}
        if blind_quality.get("status") in {"ready", "partial"}:
            judge_ids = ", ".join(blind_quality.get("judge_ids") or []) or "unknown"
            lines.extend(
                [
                    "",
                    "## Blind quality review",
                    "",
                    f"Judge configurations: `{judge_ids}`. Only matched outputs that both passed end-to-end were judged.",
                ]
            )
            if blind_quality.get("agreement") is not None:
                lines.append(
                    f"Overall winner agreement across multiply judged pairs: {float(blind_quality['agreement']):.0%}."
                )
        else:
            lines.extend(
                [
                    "",
                    "Cross-run blind quality judging has not been run. Use `compare-judge-plan` and `compare-judge-import` after both runs are graded.",
                ]
            )
    lines.extend(
        [
            "",
            "## Intended treatment",
            "",
        ]
    )
    lines.extend(f"- {value}" for value in declaration["intended_differences"])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The treatment is the declared agent-system difference; task facts, model settings, fixtures, and rubrics must match.",
            "- Synthetic benchmark scores are not campaign-performance lift.",
            "- Read counts and uncertainty before treating a positive point estimate as a stable improvement.",
            "- Positive score deltas favor the treatment; negative time and cost deltas are faster and cheaper.",
            "- Replay and live evidence are reported in separate score blocks.",
            "",
        ]
    )
    output = output_dir / "public-report.md"
    output.write_text("\n".join(lines))
    return output


def build_agent_system_comparison(
    *,
    repo_root: Path,
    baseline_run_dir: Path,
    treatment_run_dir: Path,
    declaration_path: Path,
    baseline_candidate_id: str | None = None,
    treatment_candidate_id: str | None = None,
) -> Path:
    baseline = _load_run(baseline_run_dir)
    treatment = _load_run(treatment_run_dir)
    declaration = _load_declaration(declaration_path)
    baseline_candidate = _select_candidate(baseline, baseline_candidate_id)
    treatment_candidate = _select_candidate(treatment, treatment_candidate_id)
    mismatches = _parity_mismatches(
        baseline,
        treatment,
        baseline_candidate,
        treatment_candidate,
    )
    mismatches.extend(
        _completed_setting_gaps(
            baseline, str(baseline_candidate["id"]), "baseline"
        )
    )
    mismatches.extend(
        _completed_setting_gaps(
            treatment, str(treatment_candidate["id"]), "treatment"
        )
    )

    baseline_cells = _candidate_cells(baseline, str(baseline_candidate["id"]))
    treatment_cells = _candidate_cells(treatment, str(treatment_candidate["id"]))
    pair_keys = sorted(set(baseline_cells) | set(treatment_cells))
    baseline_scenarios = _scenario_map(baseline["manifest"])

    def missing_cell(key: tuple[str, int]) -> dict[str, Any]:
        scenario = baseline_scenarios.get(key[0], {})
        evaluation_types = list(scenario.get("evaluation_types") or [])
        return {
            "status": "missing",
            "executed": False,
            "complete": False,
            "categories": {value: False for value in evaluation_types},
            "environment_mode": str(
                (scenario.get("environment") or {}).get("mode") or "none"
            ),
            "completion_seconds": None,
            "provider_cost_usd": 0.0,
            "cost_method": "unavailable",
        }

    pairs: list[dict[str, Any]] = []
    for key in pair_keys:
        baseline_present = key in baseline_cells
        treatment_present = key in treatment_cells
        baseline_cell = baseline_cells.get(key, missing_cell(key))
        treatment_cell = treatment_cells.get(key, missing_cell(key))
        pairs.append(
            {
                "scenario_id": key[0],
                "repetition": key[1],
                "environment_mode": str(
                    baseline_cell.get("environment_mode")
                    or treatment_cell.get("environment_mode")
                    or "none"
                ),
                "baseline_present": baseline_present,
                "treatment_present": treatment_present,
                "baseline": baseline_cell,
                "treatment": treatment_cell,
            }
        )

    seed_material = (
        f"{baseline_run_dir.name}:{treatment_run_dir.name}:"
        f"{baseline_candidate['id']}:{treatment_candidate['id']}"
    )
    seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:8], 16)
    score_blocks: list[dict[str, Any]] = []
    if not mismatches:
        grouped_pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pair in pairs:
            grouped_pairs[pair["environment_mode"]].append(pair)
        for index, (mode, mode_pairs) in enumerate(sorted(grouped_pairs.items())):
            score_blocks.append(
                _metric_block(
                    mode_pairs,
                    environment_mode=mode,
                    seed=seed + (index * 100),
                )
            )

    compatibility_metrics = (
        score_blocks[0]["metrics"] if len(score_blocks) == 1 else {}
    )
    compatibility_record = (
        score_blocks[0]["reliability_record"] if len(score_blocks) == 1 else None
    )

    comparison_id = (
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    output_root = repo_root / "artifacts" / "comparisons"
    output_root.mkdir(parents=True, exist_ok=True)
    output_dir = output_root / comparison_id
    output_dir.mkdir()
    payload = {
        "schema_version": 1,
        "comparison_id": comparison_id,
        "valid": not mismatches,
        "baseline_run_id": baseline_run_dir.name,
        "treatment_run_id": treatment_run_dir.name,
        "baseline_candidate_id": baseline_candidate["id"],
        "treatment_candidate_id": treatment_candidate["id"],
        "model": baseline_candidate.get("model"),
        "settings": baseline_candidate.get("settings"),
        "runtimes": {
            "baseline": _runtime_summary(baseline),
            "treatment": _runtime_summary(treatment),
        },
        "scenarios": sorted({pair["scenario_id"] for pair in pairs}),
        "task_families": sorted(
            {
                str(row.get("task_family") or "unknown")
                for row in baseline_scenarios.values()
            }
        ),
        "repetitions": sorted({pair["repetition"] for pair in pairs}),
        "declaration": declaration,
        "parity_mismatches": mismatches,
        "matched_pairs": sum(
            1
            for pair in pairs
            if pair["baseline_present"] and pair["treatment_present"]
        ),
        "planned_pair_slots": len(pairs),
        "pairing": {
            "matched": [
                {
                    "scenario_id": pair["scenario_id"],
                    "repetition": pair["repetition"],
                }
                for pair in pairs
                if pair["baseline_present"] and pair["treatment_present"]
            ],
            "missing_baseline": [
                {
                    "scenario_id": pair["scenario_id"],
                    "repetition": pair["repetition"],
                }
                for pair in pairs
                if not pair["baseline_present"]
            ],
            "missing_treatment": [
                {
                    "scenario_id": pair["scenario_id"],
                    "repetition": pair["repetition"],
                }
                for pair in pairs
                if not pair["treatment_present"]
            ],
        },
        "score_blocks": score_blocks,
        "metrics": compatibility_metrics,
        "reliability_record": compatibility_record,
        "blind_quality": {
            "status": "not_run",
            "detail": "Cross-run identity-blinded preference judging is a separate step.",
        },
        "bootstrap_seed": seed,
    }
    write_json(output_dir / "comparison.json", payload)
    _write_public_comparison_report(output_dir, payload)
    return output_dir


def _assert_comparison_runs(
    payload: dict[str, Any],
    baseline_run_dir: Path,
    treatment_run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not payload.get("valid"):
        raise ManifestError("cannot judge an invalid agent-system comparison")
    if baseline_run_dir.name != payload.get("baseline_run_id"):
        raise ManifestError("baseline run does not match the comparison")
    if treatment_run_dir.name != payload.get("treatment_run_id"):
        raise ManifestError("treatment run does not match the comparison")
    return _load_run(baseline_run_dir), _load_run(treatment_run_dir)


def prepare_comparison_judging(
    *,
    repo_root: Path,
    comparison_dir: Path,
    baseline_run_dir: Path,
    treatment_run_dir: Path,
) -> Path:
    """Build identity-blinded packets only where both systems passed end-to-end."""

    comparison_path = comparison_dir / "comparison.json"
    payload = _read_json(comparison_path)
    baseline, treatment = _assert_comparison_runs(
        payload, baseline_run_dir, treatment_run_dir
    )
    catalog = Catalog.load(repo_root)
    baseline_cells = _candidate_cells(
        baseline, str(payload["baseline_candidate_id"])
    )
    treatment_cells = _candidate_cells(
        treatment, str(payload["treatment_candidate_id"])
    )
    judge_dir = comparison_dir / "judge"
    if judge_dir.exists():
        raise ManifestError("comparison judge plan already exists")
    judge_dir.mkdir(parents=True)

    eligible_outputs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    fixture_cache: dict[str, list[dict[str, str]]] = {}
    rubric_cache: dict[str, dict[str, Any]] = {}
    for key in sorted(set(baseline_cells) & set(treatment_cells)):
        baseline_cell = baseline_cells[key]
        treatment_cell = treatment_cells[key]
        if not baseline_cell["complete"] or not treatment_cell["complete"]:
            skipped.append(
                {
                    "scenario_id": key[0],
                    "repetition": key[1],
                    "reason": "both systems must pass end-to-end before blind quality judging",
                    "baseline_passed": bool(baseline_cell["complete"]),
                    "treatment_passed": bool(treatment_cell["complete"]),
                }
            )
            continue
        scenario = catalog.scenarios.get(key[0])
        if scenario is None:
            raise ManifestError(f"comparison scenario is not in the catalog: {key[0]}")
        rubric = rubric_cache.setdefault(
            scenario.rubric,
            _read_json(repo_root / scenario.rubric),
        )
        dimensions = rubric.get("subjective_dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            skipped.append(
                {
                    "scenario_id": key[0],
                    "repetition": key[1],
                    "reason": "rubric has no subjective dimensions",
                }
            )
            continue
        baseline_output = _attempt_output(
            baseline_run_dir,
            str(baseline_cell["attempt_id"]),
            scenario.artifact.relative_path,
        )
        treatment_output = _attempt_output(
            treatment_run_dir,
            str(treatment_cell["attempt_id"]),
            scenario.artifact.relative_path,
        )
        if not baseline_output.strip() or not treatment_output.strip():
            skipped.append(
                {
                    "scenario_id": key[0],
                    "repetition": key[1],
                    "reason": "one or both eligible outputs are empty",
                }
            )
            continue
        sources = _scenario_sources(
            repo_root,
            scenario.fixture_dirs,
            fixture_cache,
        )
        shared = {
            "scenario_id": scenario.id,
            "task_family": scenario.task_family,
            "environment_mode": scenario.environment_mode,
            "repetition": key[1],
            "brief": scenario.prompt,
            "sources": sources,
            "rubric": {
                "id": rubric.get("id"),
                "subjective_dimensions": dimensions,
            },
        }
        eligible_outputs.extend(
            [
                {
                    **shared,
                    "attempt_id": str(baseline_cell["attempt_id"]),
                    "candidate_id": "baseline-system",
                    "output": baseline_output,
                },
                {
                    **shared,
                    "attempt_id": str(treatment_cell["attempt_id"]),
                    "candidate_id": "treatment-system",
                    "output": treatment_output,
                },
            ]
        )

    packets, identity_map = build_blinded_pairs(
        run_id=str(payload["comparison_id"]),
        random_seed=int(payload["bootstrap_seed"]),
        eligible_outputs=eligible_outputs,
    )
    packet_path = judge_dir / "pairs.jsonl"
    write_jsonl(packet_path, packets)
    write_json(
        judge_dir / "pair-map.json",
        {
            "schema_version": 1,
            "warning": "Do not expose this identity map to a judge.",
            "systems": {
                "baseline-system": payload["baseline_candidate_id"],
                "treatment-system": payload["treatment_candidate_id"],
            },
            "pairs": identity_map,
        },
    )
    write_json(judge_dir / "skipped.json", {"schema_version": 1, "pairs": skipped})
    write_json(
        judge_dir / "summary.json",
        {
            "schema_version": 1,
            "eligible_outputs": len(eligible_outputs),
            "pairs": len(packets),
            "skipped_pairs": len(skipped),
            "identity_blinded": True,
            "tools_allowed": False,
        },
    )
    payload["blind_quality"] = {
        "status": "planned",
        "eligible_pairs": len(packets),
        "skipped_pairs": len(skipped),
        "detail": "Identity-blinded packets are ready; judge results are not imported.",
    }
    write_json(comparison_path, payload)
    _write_public_comparison_report(comparison_dir, payload)
    return packet_path


def _blind_mode_summary(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if str(row.get("environment_mode") or "none") == mode
    ]
    wins = sum(
        1 for row in selected if row.get("winner_candidate_id") == "treatment-system"
    )
    losses = sum(
        1 for row in selected if row.get("winner_candidate_id") == "baseline-system"
    )
    ties = sum(1 for row in selected if row.get("winner") == "tie")
    total = wins + ties + losses
    dimension_records: dict[str, dict[str, int]] = defaultdict(
        lambda: {"wins": 0, "ties": 0, "losses": 0}
    )
    for row in selected:
        for decision in row.get("dimension_decisions") or []:
            dimension_id = str(decision.get("dimension_id") or "unknown")
            winner = decision.get("winner")
            if winner == "tie":
                dimension_records[dimension_id]["ties"] += 1
                continue
            winner_candidate = (
                row.get("candidate_a_id")
                if winner == "A"
                else row.get("candidate_b_id")
            )
            if winner_candidate == "treatment-system":
                dimension_records[dimension_id]["wins"] += 1
            else:
                dimension_records[dimension_id]["losses"] += 1
    dimensions: dict[str, Any] = {}
    for dimension_id, record in sorted(dimension_records.items()):
        decisions = record["wins"] + record["ties"] + record["losses"]
        dimensions[dimension_id] = {
            **record,
            "decisions": decisions,
            "treatment_preference_rate": (
                (record["wins"] + 0.5 * record["ties"]) / decisions
                if decisions
                else None
            ),
        }
    return {
        "status": "ready" if selected else "not_run",
        "environment_mode": mode,
        "judged_decisions": total,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "baseline_preference_rate": (
            (losses + 0.5 * ties) / total if total else None
        ),
        "treatment_preference_rate": (
            (wins + 0.5 * ties) / total if total else None
        ),
        "preference_delta": (
            (wins - losses) / total if total else None
        ),
        "dimensions": dimensions,
    }


def import_comparison_judging(
    *,
    comparison_dir: Path,
    results_path: Path,
    judge_id: str,
) -> Path:
    """Import one blinded judge result set and refresh comparison quality rows."""

    comparison_path = comparison_dir / "comparison.json"
    payload = _read_json(comparison_path)
    if not payload.get("valid"):
        raise ManifestError("cannot import judging for an invalid comparison")
    output = import_pairwise_results(
        comparison_dir,
        results_path,
        judge_id=judge_id,
    )
    rows: list[dict[str, Any]] = []
    for path in sorted((comparison_dir / "grades").glob("subjective-*.jsonl")):
        rows.extend(_read_jsonl(path))
    modes = sorted(
        {
            str(block.get("environment_mode") or "none")
            for block in payload.get("score_blocks") or []
        }
    )
    by_environment = [_blind_mode_summary(rows, mode) for mode in modes]
    grouped_winners: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        winner = str(row.get("winner_candidate_id") or "tie")
        grouped_winners[
            (str(row.get("environment_mode") or "none"), str(row["pair_id"]))
        ].append(winner)
    agreements = 0
    comparisons = 0
    for winners in grouped_winners.values():
        for left_index in range(len(winners)):
            for right_index in range(left_index + 1, len(winners)):
                comparisons += 1
                agreements += int(winners[left_index] == winners[right_index])
    judge_ids = sorted({str(row.get("judge_id")) for row in rows})
    import_summaries = [
        _read_json(path)
        for path in sorted((comparison_dir / "judge").glob("import-*.json"))
    ]
    partial = any(summary.get("missing_pairs") for summary in import_summaries)
    payload["blind_quality"] = {
        "status": "partial" if partial else "ready",
        "judge_ids": judge_ids,
        "judged_decisions": len(rows),
        "agreement": agreements / comparisons if comparisons else None,
        "agreement_comparisons": comparisons,
        "by_environment": by_environment,
    }
    write_json(comparison_path, payload)
    _write_public_comparison_report(comparison_dir, payload)
    return output
