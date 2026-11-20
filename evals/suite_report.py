#!/usr/bin/env python3
"""A suite's results side by side, scored with the checks as they are now.

    python -m evals.suite_report low=<run dir>[,<run dir>...] medium=<run dir> ... [--json FILE]

Each argument is a setting (an effort, a model) and the suite run folders
that make it up: a top-up run adds the attempts an earlier run lost to an
error. Every saved record is scored again by ``scenario_rescore`` against
this checkout's scenario files, with no model call, so every setting is read
by the same checks whatever the checks were when it ran. An attempt that
errored, could not be read back, or answered a question the scenario no
longer asks is not scored: it is counted apart, never as a pass or a fail.

Times, calls and cost are the run's own measurements (``suite.json``), over
the scored attempts only. ``--json`` writes what a page may publish: counts,
times, costs and the ids of failed checks. It holds no message text, chat or
session id, lane name or address; the records themselves stay private.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from evals import scenario_rescore
from evals.runner import scenario_outcomes


def attempts(run_dir: Path) -> list[dict[str, Any]]:
    """One row per saved record of a suite run: its new verdict, the ids of
    the required checks it failed, and what the run measured for it."""
    suite = json.loads((run_dir / "suite.json").read_text())
    measured = {(row["scenario"], row["repetition"]): row for row in suite.get("rows") or []}
    out = []
    for row in scenario_rescore.rescore(run_dir):
        if row["status"] == "malformed":
            raise SystemExit(f"ERROR: {row['scenario']}: {row['why']}")
        mine = measured.get((row["scenario"], row["repetition"])) or {}
        out.append({
            "scenario": row["scenario"],
            "repetition": row["repetition"],
            "run": run_dir.name,
            "status": row["status"],
            "why": row.get("why"),
            "caveat": (row.get("outcome") or {}).get("caveat"),
            "failed_checks": [
                check["id"] for check in (row.get("outcome") or {}).get("checks") or []
                if check["required"] and not check["passed"]
            ],
            "seconds": mine.get("seconds"),
            "model_seconds": mine.get("llm_seconds"),
            "model_calls": mine.get("llm_calls"),
            "tool_calls": mine.get("tool_calls"),
            "cost_usd": mine.get("provider_cost_usd"),
        })
    return out


def _median(values: list[Any]) -> float | None:
    values = [value for value in values if value is not None]
    return round(statistics.median(values), 2) if values else None


def _setting(label: str, run_dirs: list[Path]) -> dict[str, Any]:
    rows = [row for run_dir in run_dirs for row in attempts(run_dir)]
    scored = [row for row in rows if row["status"] in ("passed", "failed")]
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_scenario.setdefault(row["scenario"], []).append(row)
    costs = [row["cost_usd"] for row in scored if row["cost_usd"] is not None]
    meta = [json.loads((run_dir / "suite.json").read_text()) for run_dir in run_dirs]
    return {
        "label": label,
        "runs": [run_dir.name for run_dir in run_dirs],
        "models": sorted({m["model"] for m in meta if m.get("model")}),
        "efforts": sorted({m["effort"] for m in meta if m.get("effort")}),
        "gateway_shas": sorted({m["gateway_sha"] for m in meta if m.get("gateway_sha")}),
        "attempts": len(scored),
        "passed": sum(row["status"] == "passed" for row in scored),
        "not_scored": len(rows) - len(scored),
        "scenarios": len(by_scenario),
        # Passed every attempt: at least one scored attempt, and every scored one passed.
        "scenarios_passed_every_attempt": sum(
            bool(ran) and all(row["status"] == "passed" for row in ran)
            for ran in ([row for row in mine if row["status"] in ("passed", "failed")] for mine in by_scenario.values())
        ),
        "median_seconds": _median([row["seconds"] for row in scored]),
        "median_model_seconds": _median([row["model_seconds"] for row in scored]),
        "median_model_calls": _median([row["model_calls"] for row in scored]),
        "median_tool_calls": _median([row["tool_calls"] for row in scored]),
        "mean_cost_usd": round(statistics.mean(costs), 4) if costs else None,
        "cost_known_for": len(costs),
        "by_scenario": {
            scenario_id: {
                "attempts": sum(row["status"] in ("passed", "failed") for row in mine),
                "passed": sum(row["status"] == "passed" for row in mine),
                "not_scored": sum(row["status"] not in ("passed", "failed") for row in mine),
                "median_seconds": _median([row["seconds"] for row in mine if row["status"] in ("passed", "failed")]),
            }
            for scenario_id, mine in by_scenario.items()
        },
        "failures": [
            {"scenario": row["scenario"], "repetition": row["repetition"], "run": row["run"], "checks": row["failed_checks"]}
            for row in scored if row["status"] == "failed"
        ],
        # Scenarios scored by an earlier outcome kind: their counts are not a pass rate.
        "caveated_scenarios": sorted({row["scenario"] for row in scored if row["caveat"]}),
    }


def summarize(settings: dict[str, list[Path]]) -> dict[str, Any]:
    """What the table and ``--json`` hold: the scenarios in the order the
    first setting ran them, with each one's title, description and tags from
    this checkout, then one block per setting."""
    blocks = [_setting(label, run_dirs) for label, run_dirs in settings.items()]
    order = list(dict.fromkeys(scenario_id for block in blocks for scenario_id in block["by_scenario"]))
    scenarios = []
    for scenario_id in order:
        path = scenario_rescore.REPO_ROOT / "evals" / "scenarios" / f"{scenario_id}.json"
        spec = json.loads(path.read_text()) if path.exists() else {}
        scenarios.append({
            "id": scenario_id,
            "title": spec.get("title") or scenario_id,
            "description": spec.get("description") or "",
            "tags": [tag for tag in spec.get("tags") or [] if tag != "magister-benchmark"],
        })
    caveated = sorted({scenario_id for block in blocks for scenario_id in block["caveated_scenarios"]})
    return {
        "schema_version": 1,
        "caveat": f"{', '.join(caveated)}: {scenario_outcomes.SCORER_CAVEAT}" if caveated else None,
        "scenarios": scenarios,
        "settings": blocks,
    }


def render(summary: dict[str, Any]) -> str:
    def cell(value: Any, digits: int = 0) -> str:
        return "—" if value is None else f"{value:.{digits}f}"

    lines = [f"{'setting':<10} {'passed':>9} {'every attempt':>14} {'median s':>9} {'model s':>8} {'tools':>6} {'cents':>6} {'not scored':>11}"]
    for block in summary["settings"]:
        cents = None if block["mean_cost_usd"] is None else 100 * block["mean_cost_usd"]
        lines.append(
            f"{block['label']:<10} {str(block['passed']) + '/' + str(block['attempts']):>9} "
            f"{str(block['scenarios_passed_every_attempt']) + '/' + str(block['scenarios']):>14} "
            f"{cell(block['median_seconds']):>9} {cell(block['median_model_seconds']):>8} "
            f"{cell(block['median_tool_calls']):>6} {cell(cents, 1):>6} {block['not_scored'] or '':>11}"
        )
    lines += ["", f"{'scenario':<28} " + " ".join(f"{block['label']:>9}" for block in summary["settings"])]
    for scenario in summary["scenarios"]:
        cells = []
        for block in summary["settings"]:
            mine = block["by_scenario"].get(scenario["id"])
            cells.append("—" if not mine else f"{mine['passed']}/{mine['attempts']}")
        lines.append(f"{scenario['id']:<28} " + " ".join(f"{c:>9}" for c in cells))
    failures = [(block["label"], failure) for block in summary["settings"] for failure in block["failures"]]
    if failures:
        lines += ["", "failed attempts (the required checks each one failed)"]
        lines += [f"  {label} {f['scenario']} rep {f['repetition']}: {', '.join(f['checks']) or 'no required check named'}" for label, f in failures]
    if summary["caveat"]:
        lines += ["", f"not a pass rate for {summary['caveat']}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("settings", nargs="+", metavar="LABEL=RUN_DIR[,RUN_DIR...]")
    parser.add_argument("--json", type=Path, default=None, help="also write the summary to this file")
    args = parser.parse_args(argv)
    settings: dict[str, list[Path]] = {}
    for arg in args.settings:
        label, sep, dirs = arg.partition("=")
        if not sep or not label or not dirs or label in settings:
            parser.error(f"expected LABEL=RUN_DIR[,RUN_DIR...] with each label once, got {arg!r}")
        settings[label] = [Path(d) for d in dirs.split(",") if d]
        for run_dir in settings[label]:
            if not (run_dir / "suite.json").exists():
                parser.error(f"{run_dir} is not a suite run folder (no suite.json)")
    summary = summarize(settings)
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2) + "\n")
    print(render(summary), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
