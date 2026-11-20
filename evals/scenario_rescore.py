#!/usr/bin/env python3
"""Score saved scenario records again, with the checks as they are now.

    python -m evals.scenario_rescore <run dir> [--saved-scenario]

A run dir is a suite's (``<scenario>/rep-N/record.json``) or one scenario's
(``rep-N/record.json``). Each record is scored by ``scenario_outcomes.evaluate``
against the scenario file in this checkout (or, with ``--saved-scenario``, the
``scenario.json`` saved beside it), with the repetition's own ``{nonce}``
filled in. Nothing is written and no model is called: this is how a check is
changed and tried against the runs already paid for.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.runner import scenario_outcomes

REPO_ROOT = Path(__file__).resolve().parents[1]


def records(run_dir: Path) -> list[Path]:
    return sorted(run_dir.glob("rep-*/record.json")) + sorted(run_dir.glob("*/rep-*/record.json"))


class MissingNonce(ValueError):
    """The scenario is written around a per-run tag and the record has none:
    an empty tag would turn "hero|{nonce}" into a pattern that matches anything."""


def scenario_for(record_path: Path, record: dict, *, saved: bool) -> dict:
    path = (record_path.parents[1] / "scenario.json") if saved else (
        REPO_ROOT / "evals" / "scenarios" / f"{record['scenario_id']}.json")
    text = path.read_text()
    if "{nonce}" in text and not record.get("nonce"):
        raise MissingNonce(record["scenario_id"])
    return json.loads(text.replace("{nonce}", str(record.get("nonce") or "")))


def asked_something_else(record_path: Path, record: dict) -> bool:
    """The scenario file now asks a different question than this run was
    asked (its turns changed since): the run's answer is to the old one."""
    saved = record_path.parents[1] / "scenario.json"
    current = REPO_ROOT / "evals" / "scenarios" / f"{record['scenario_id']}.json"
    if not saved.exists() or not current.exists():
        return False
    texts = [[turn.get("text") for turn in json.loads(path.read_text()).get("turns") or []] for path in (saved, current)]
    return texts[0] != texts[1]


def rescore(run_dir: Path, *, saved: bool = False) -> list[dict]:
    """One row per record: ``status`` passed, failed, unscored or malformed,
    with ``why`` for the last two, the new ``outcome`` for the first two, and
    ``changed`` when the verdict differs from the one the run recorded."""
    rows: list[dict] = []
    for path in records(run_dir):
        record = json.loads(path.read_text())
        before = record.get("outcome") or {}
        row = {"scenario": record["scenario_id"], "repetition": record["repetition"], "path": str(path), "changed": False}
        rows.append(row)
        why = None
        if record.get("stop_reason") == "error":
            why = "the run ended in an error: " + next(
                (note for note in record.get("notes") or [] if str(note).startswith("error:")), "see its notes")
        elif record.get("harvest_gaps"):
            why = f"could not be read back: {', '.join(record['harvest_gaps'])}"
        elif not saved and asked_something_else(path, record):
            why = "the scenario's turns have changed since this run: it answered a different question"
        scenario = None
        if why is None:
            try:
                scenario = scenario_for(path, record, saved=saved)
            except FileNotFoundError:
                why = "this checkout has no such scenario"
            except MissingNonce:
                why = "the scenario uses a per-run tag and this record has none"
        if why is not None:
            row.update(status="unscored", why=why)
            continue
        try:
            after = scenario_outcomes.evaluate(scenario, record)
        except ValueError as exc:
            row.update(status="malformed", why=f"malformed check: {exc}")
            continue
        row.update(status="passed" if after.get("passed") else "failed", outcome=after,
                   changed=bool(before.get("passed")) != bool(after.get("passed")), before=before)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--saved-scenario", action="store_true", help="score against the scenario.json saved with the run")
    args = parser.parse_args(argv)
    rows = rescore(args.run_dir, saved=args.saved_scenario)
    if not rows:
        print(f"ERROR: no record.json under {args.run_dir}", file=sys.stderr)
        return 2
    for row in rows:
        name = f"{row['scenario']} rep {row['repetition']}"
        if row["status"] in ("unscored", "malformed"):
            print(f"{name}: not scored ({row['why']})")
            continue
        after, before = row["outcome"], row["before"]
        print(f"{name}: {'passed' if row['status'] == 'passed' else 'FAILED'} ({after.get('summary')})"
              + (f"  [was {'passed' if before.get('passed') else 'failed'}: {before.get('summary')}]" if row["changed"] else ""))
        for check in after.get("checks") or []:
            if not check["passed"]:
                print(f"    {'FAIL' if check['required'] else 'note'} {check['id']}: {check['detail']}")
    scored = [row for row in rows if row["status"] in ("passed", "failed")]
    left_out = [row for row in rows if row["status"] not in ("passed", "failed")]
    passed = sum(row["status"] == "passed" for row in scored)
    print(f"\n{len(rows)} record(s), {sum(row['changed'] for row in rows)} verdict(s) changed")
    by_scenario: dict[str, list[dict]] = {}
    for row in rows:
        by_scenario.setdefault(row["scenario"], []).append(row)
    if len(by_scenario) > 1:
        print(f"\n{'scenario':<34} passed  not scored")
        for scenario_id in sorted(by_scenario):
            mine = by_scenario[scenario_id]
            ran = [row for row in mine if row["status"] in ("passed", "failed")]
            print(f"{scenario_id:<34} {sum(row['status'] == 'passed' for row in ran)}/{len(ran):<5} {len(mine) - len(ran) or ''}")
    # A scenario passed every attempt only if every attempt was scored and passed: one left out is not a pass.
    every = sum(all(row["status"] == "passed" for row in mine) for mine in by_scenario.values())
    print(f"\ntotal: {passed}/{len(scored)} scored attempts passed"
          + (f" ({100 * passed / len(scored):.1f}%)" if scored else "")
          + f", {every}/{len(by_scenario)} scenarios passed every attempt"
          + (f"; {len(left_out)} of {len(rows)} record(s) NOT SCORED" if left_out else ""))
    caveated = sorted({row["scenario"] for row in scored if row["outcome"].get("caveat")})
    if caveated:
        print(f"\nnot a pass rate for {', '.join(caveated)}: {scenario_outcomes.SCORER_CAVEAT}")
    if any(row["status"] == "malformed" for row in rows):
        return 2
    return 1 if left_out or passed < len(scored) else 0


if __name__ == "__main__":
    sys.exit(main())
