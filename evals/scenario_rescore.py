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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--saved-scenario", action="store_true", help="score against the scenario.json saved with the run")
    args = parser.parse_args(argv)
    found = records(args.run_dir)
    if not found:
        print(f"ERROR: no record.json under {args.run_dir}", file=sys.stderr)
        return 2
    changed = 0
    totals: dict[str, list[bool]] = {}
    for path in found:
        record = json.loads(path.read_text())
        before = record.get("outcome") or {}
        try:
            scenario = scenario_for(path, record, saved=args.saved_scenario)
        except FileNotFoundError:
            print(f"{record['scenario_id']} rep {record['repetition']}: not scored (this checkout has no such scenario)")
            continue
        except MissingNonce:
            print(f"{record['scenario_id']} rep {record['repetition']}: not scored (the scenario uses a per-run tag and "
                  "this record has none)")
            continue
        if record.get("harvest_gaps"):
            print(f"{record['scenario_id']} rep {record['repetition']}: not scored (could not be read back: "
                  f"{', '.join(record['harvest_gaps'])})")
            continue
        try:
            after = scenario_outcomes.evaluate(scenario, record)
        except ValueError as exc:
            print(f"{record['scenario_id']} rep {record['repetition']}: not scored (malformed check: {exc})")
            continue
        totals.setdefault(record["scenario_id"], []).append(bool(after.get("passed")))
        flipped = bool(before.get("passed")) != bool(after.get("passed"))
        changed += flipped
        print(f"{record['scenario_id']} rep {record['repetition']}: "
              f"{'passed' if after.get('passed') else 'FAILED'} ({after.get('summary')})"
              + (f"  [was {'passed' if before.get('passed') else 'failed'}: {before.get('summary')}]" if flipped else ""))
        for check in after.get("checks") or []:
            if not check["passed"]:
                print(f"    {'FAIL' if check['required'] else 'note'} {check['id']}: {check['detail']}")
    print(f"\n{len(found)} record(s), {changed} verdict(s) changed")
    if len(totals) > 1:
        scored = sum(len(passes) for passes in totals.values())
        passed = sum(sum(passes) for passes in totals.values())
        every = sum(all(passes) for passes in totals.values())
        print(f"\n{'scenario':<34} passed")
        for scenario_id in sorted(totals):
            print(f"{scenario_id:<34} {sum(totals[scenario_id])}/{len(totals[scenario_id])}")
        print(f"\ntotal: {every}/{len(totals)} scenarios passed every attempt, {passed}/{scored} attempts passed "
              f"({100 * passed / scored:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
