#!/usr/bin/env python3
"""Print and save the metric table of a scenario run, beside an earlier one.

    python -m evals.scenario_report <run dir> [--before <run dir>] [--json]

A run dir is what the monorepo's ``evals/magister/scenario_bridge.py`` writes:
``scenario.json`` (the scenario as run), and one ``rep-N/record.json`` per
repetition (``rep-0/`` holds the origin chat harvested from its own database
when the run recorded one). This computes ``metrics.json`` next to every
record, writes ``summary.json`` and ``summary.md`` into the run dir, and
prints the Markdown table: one column per repetition plus the mean. With
``--before`` the earlier run's columns and a delta-of-means table follow, so
a harness, skill or model change is read run by run and on average.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evals.runner.scenario_metrics import (
    compare,
    compute_metrics,
    render_comparison,
    render_table,
    summarize,
)


def _records(run_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    if (run_dir / "record.json").exists():
        return [(run_dir, json.loads((run_dir / "record.json").read_text()))]
    found = sorted(
        (path for path in run_dir.glob("rep-*/record.json")),
        key=lambda path: int(path.parent.name.split("-")[-1]) if path.parent.name.split("-")[-1].isdigit() else 99,
    )
    if not found:
        raise SystemExit(f"ERROR: no record.json under {run_dir}")
    return [(path.parent, json.loads(path.read_text())) for path in found]


def load_run(run_dir: Path, *, write: bool = True) -> dict[str, Any]:
    scenario_path = run_dir / "scenario.json"
    scenario = json.loads(scenario_path.read_text()) if scenario_path.exists() else {}
    metric_ids = list(scenario.get("metrics") or []) or None
    columns: list[tuple[str, dict[str, Any]]] = []
    replays: list[dict[str, Any]] = []
    origin: dict[str, Any] | None = None
    for rep_dir, record in _records(run_dir):
        metrics = compute_metrics(record)
        if write:
            (rep_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
        label = str(record.get("label") or rep_dir.name)
        if record.get("repetition") == 0 or label == "origin":
            origin = metrics
            columns.append(("run 0 (origin)", metrics))
        else:
            replays.append(metrics)
            columns.append((f"run {record.get('repetition') or len(replays)}", metrics))
    summary = summarize(replays)
    if replays:
        columns.append((f"mean of {len(replays)}", _mean_column(summary, replays)))
    return {
        "dir": run_dir, "scenario": scenario, "metric_ids": metric_ids, "columns": columns,
        "replays": replays, "origin": origin, "summary": summary,
    }


def _mean_column(summary: dict[str, Any], replays: list[dict[str, Any]]) -> dict[str, Any]:
    """The mean column renders through the same row formatters as a run; the
    publish row shows how many runs published instead of yes/no."""
    column = {
        key: (round(value["mean"], 1) if isinstance(value, dict) else value) for key, value in summary.items()
    }
    column.update({
        "published": summary["published"] > 0,
        "has_media": all(run.get("has_media") for run in replays),
        "_published_text": f"{summary['published']}/{summary['runs']}",
        "wall_seconds_per_turn": [],
        "experience": {"status": "not_run"},
    })
    return column


def render_run(run: dict[str, Any]) -> str:
    return render_table(run["columns"], run["metric_ids"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--before", type=Path, default=None, help="an earlier run of the same scenario")
    parser.add_argument("--json", action="store_true", help="print summary.json instead of the table")
    args = parser.parse_args(argv)

    after = load_run(args.run)
    before = load_run(args.before, write=False) if args.before else None
    scenario = after["scenario"]
    title = scenario.get("title") or scenario.get("id") or args.run.name
    shas = sorted({str(m.get("gateway_sha") or "")[:9] for m in after["replays"]} - {""})
    models = sorted({str(m.get("model") or "") for m in after["replays"]} - {""})
    out = [f"## {title}", "", f"run: {args.run}  gateway: {', '.join(shas) or '—'}  model: {', '.join(models) or '—'}", ""]
    out.append(render_run(after))
    comparison = None
    if before is not None:
        b_shas = sorted({str(m.get("gateway_sha") or "")[:9] for m in before["replays"]} - {""})
        out += ["", f"before: {args.before}  gateway: {', '.join(b_shas) or '—'}", "", render_run(before)]
        comparison = compare(before["replays"], after["replays"])
        out += ["", "### Before → after (means)", "", render_comparison(comparison, after["metric_ids"])]
    text = "\n".join(out) + "\n"
    payload = {
        "scenario_id": scenario.get("id"),
        "run_dir": str(args.run),
        "before_dir": str(args.before) if args.before else None,
        "summary": after["summary"],
        "origin": after["origin"],
        "runs": after["replays"],
        "comparison": comparison,
    }
    (args.run / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    (args.run / "summary.md").write_text(text)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str) if args.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
