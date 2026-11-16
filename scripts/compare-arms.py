#!/usr/bin/env python3
"""Put several graded runs side by side: one column per arm, one row per task.

Each arm is a run directory that `bench report` has already written
`report.json` into. The runs must share their tasks, repetitions and judge, or
the comparison is refused: a number from another judge or another task set is
not the same number.

    python scripts/compare-arms.py \\
        --arm "Claude Code=eval_runner/results/<run>" \\
        --arm "Claude Code + skills=eval_runner/results/<run>" \\
        --arm "Magister=eval_runner/results/<run>" [--json out.json]

The last arm is the one the others are measured against. The difference is
tested per task, not per attempt: the tasks are the sample, and three attempts
at one task are not three tasks. The test is a paired sign-flip permutation
over the per-task score differences.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import statistics
import sys
from pathlib import Path

EXACT_LIMIT = 16
MONTE_CARLO_DRAWS = 200_000
# A per-task score difference within this margin, either way, counts as level.
LEVEL_MARGIN = 0.05


def _mean(values: list) -> float | None:
    """The mean to one decimal, or None when no attempt recorded the value."""
    return round(statistics.mean(values), 1) if values else None


def load_arm(label: str, run_dir: Path) -> dict:
    report_path = run_dir / "report.json"
    if not report_path.is_file():
        raise SystemExit(f"{label}: {report_path} is missing; run `bench grade` and `bench report` first")
    report = json.loads(report_path.read_text())
    if len(report["models"]) != 1:
        raise SystemExit(f"{label}: expected one model in the run, found {len(report['models'])}")
    model_id, stats = next(iter(report["models"].items()))
    attempts = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines() if line.strip()]
    grading_path = run_dir / "grading.json"
    grading = json.loads(grading_path.read_text()) if grading_path.is_file() else {}
    runs = {
        submission["task_id"]: submission["runs"]
        for submission in report["submissions"]
        if submission["model_id"] == model_id
    }
    answered = [attempt for attempt in attempts if "error" not in attempt]
    return {
        "label": label,
        "run_id": report["run_id"],
        "harness": report.get("harness"),
        "model_id": model_id,
        "tasks": list(report["tasks"]),
        "repetitions": report["repetitions"],
        "judge": grading.get("judge_model") or grading.get("judge"),
        "composite": stats["composite_score"],
        "tasks_passed": stats["tasks_passed"],
        "tasks_total": stats["tasks_total"],
        "runs_passed": stats["runs_passed"],
        "runs_total": stats["runs_total"],
        "task_scores": stats["task_scores"],
        "task_runs_passed": {
            task_id: sum(1 for run in task_runs if run.get("pass")) for task_id, task_runs in runs.items()
        },
        "errors": len(attempts) - len(answered),
        # The report prices every attempt the same way for every harness: the
        # recorded provider cost when there is one, the rate card otherwise.
        "cost_usd": stats.get("candidate_cost_usd"),
        "cost_complete": bool(stats.get("candidate_cost_complete", True)),
        "seconds_per_attempt": _mean(
            [a["latency_seconds"] for a in answered if a.get("latency_seconds") is not None]
        ),
        "llm_calls_per_attempt": _mean([a["llm_calls"] for a in answered if a.get("llm_calls") is not None]),
        "tool_calls_per_attempt": _mean(
            [a.get("tool_call_count") or sum((a.get("tool_calls") or {}).values()) for a in answered]
        ),
        "attempts_reading_a_skill": (
            sum(1 for a in answered if a.get("skill_reads"))
            if any(a.get("skill_reads") is not None for a in answered) else None
        ),
        "attempts": len(attempts),
    }


def check_comparable(arms: list[dict]) -> None:
    first = arms[0]
    for arm in arms[1:]:
        for key in ("repetitions", "judge"):
            if arm[key] != first[key]:
                raise SystemExit(
                    f"{arm['label']} and {first['label']} differ in {key}: {arm[key]!r} vs {first[key]!r}"
                )
        if sorted(arm["tasks"]) != sorted(first["tasks"]):
            only = sorted(set(arm["tasks"]) ^ set(first["tasks"]))
            raise SystemExit(f"{arm['label']} and {first['label']} ran different tasks: {', '.join(only)}")


def paired_permutation(differences: list[float]) -> float:
    """Two-sided p for the mean difference under random sign flips of each task's difference."""
    observed = abs(sum(differences))
    if observed == 0:
        return 1.0
    count = len(differences)
    if count <= EXACT_LIMIT:
        hits = sum(
            1
            for signs in itertools.product((1, -1), repeat=count)
            if abs(sum(sign * diff for sign, diff in zip(signs, differences))) >= observed - 1e-9
        )
        return hits / 2 ** count
    rng = random.Random(20261116)
    hits = sum(
        1
        for _ in range(MONTE_CARLO_DRAWS)
        if abs(sum(diff if rng.random() < 0.5 else -diff for diff in differences)) >= observed - 1e-9
    )
    return (hits + 1) / (MONTE_CARLO_DRAWS + 1)


def versus(reference: dict, other: dict) -> dict:
    tasks = reference["tasks"]
    differences = [reference["task_scores"][task] - other["task_scores"][task] for task in tasks]
    return {
        "against": other["label"],
        "mean_difference": round(statistics.mean(differences), 2),
        "tasks_ahead": sum(1 for diff in differences if diff > LEVEL_MARGIN),
        "tasks_level": sum(1 for diff in differences if abs(diff) <= LEVEL_MARGIN),
        "tasks_behind": sum(1 for diff in differences if diff < -LEVEL_MARGIN),
        "p_value": round(paired_permutation(differences), 4),
    }


def render(arms: list[dict], comparisons: list[dict]) -> str:
    def row(cells: list[str]) -> str:
        return "| " + " | ".join(cells) + " |"

    labels = [arm["label"] for arm in arms]
    divider = row(["---", *["---:" for _ in arms]])
    reps = arms[0]["repetitions"]
    lines = [row(["", *labels]), divider]
    lines.append(row(["Score (0-100)", *[f"**{arm['composite']:.1f}**" for arm in arms]]))
    lines.append(row([f"Tasks passed on all {reps} runs", *[f"{arm['tasks_passed']}/{arm['tasks_total']}" for arm in arms]]))
    lines.append(row(["Attempts passed", *[f"{arm['runs_passed']}/{arm['runs_total']}" for arm in arms]]))
    lines.append(row(["Attempts with no answer", *[str(arm["errors"]) for arm in arms]]))
    lines.append(row(["Cost, whole run", *[
        "n/a" if arm["cost_usd"] is None
        else f"${arm['cost_usd']:.2f}" + ("" if arm["cost_complete"] else " (incomplete)")
        for arm in arms
    ]]))
    for title, key in (
        ("Seconds per attempt", "seconds_per_attempt"),
        ("Model calls per attempt", "llm_calls_per_attempt"),
        ("Tool calls per attempt", "tool_calls_per_attempt"),
        ("Attempts that opened a skill", "attempts_reading_a_skill"),
    ):
        lines.append(row([title, *["n/a" if arm[key] is None else str(arm[key]) for arm in arms]]))

    lines += ["", row(["Task", *labels]), divider]
    for task in arms[0]["tasks"]:
        lines.append(row([task, *[
            f"{arm['task_scores'][task]:.1f} ({arm['task_runs_passed'].get(task, 0)}/{reps})" for arm in arms
        ]]))

    if comparisons:
        reference = arms[-1]["label"]
        lines += ["", f"{reference} against each other arm, per task ({len(arms[0]['tasks'])} tasks):", ""]
        lines += [row(["Against", "Mean difference", "Ahead / level / behind", "p (paired sign-flip)"]),
                  row(["---", "---:", "---:", "---:"])]
        for item in comparisons:
            lines.append(row([
                item["against"], f"{item['mean_difference']:+.1f}",
                f"{item['tasks_ahead']} / {item['tasks_level']} / {item['tasks_behind']}", f"{item['p_value']:.3f}",
            ]))
    lines += ["", "Runs: " + "; ".join(f"{arm['label']} `{arm['run_id']}` ({arm['harness']})" for arm in arms)
              + f". Judge: {arms[0]['judge']}. Repetitions: {reps}."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--arm", action="append", required=True, metavar="LABEL=RUN_DIR")
    parser.add_argument("--json", help="also write the comparison as JSON")
    args = parser.parse_args(argv)
    arms = []
    for spec in args.arm:
        label, separator, path = spec.partition("=")
        if not separator or not label or not path:
            raise SystemExit(f"--arm takes LABEL=RUN_DIR, got {spec!r}")
        arms.append(load_arm(label, Path(path)))
    check_comparable(arms)
    comparisons = [versus(arms[-1], other) for other in arms[:-1]]
    sys.stdout.write(render(arms, comparisons))
    if args.json:
        Path(args.json).write_text(json.dumps({"arms": arms, "comparisons": comparisons}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
