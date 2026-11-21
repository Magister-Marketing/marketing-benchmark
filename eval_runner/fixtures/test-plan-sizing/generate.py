#!/usr/bin/env python3
"""Write, or check, the sources of the test-plan-sizing task.

Deterministic: the traffic comes from a seeded generator and everything else
is written out below, so running it twice writes the same bytes. The rules
are rendered from the constants in `eval_runner/task_facts_conversion.py`,
the same ones its oracle applies.

    python3 eval_runner/fixtures/test-plan-sizing/generate.py --write
    python3 eval_runner/fixtures/test-plan-sizing/generate.py --check

All brands and figures here are invented.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eval_runner import task_facts_conversion as facts  # noqa: E402

SEED = 4417
FIRST_WEEK = dt.date(2027, 1, 4)

# test id, page, change, primary metric, baseline rate (%), expected lift, unit
BACKLOG = [
    ("T1", "homepage", "Hero leads with the subscription offer", "orders per homepage user", "3.0", "10", "relative %"),
    ("T2", "product page", "Tasting notes moved above the price", "orders per product-page user", "5.0", "12", "relative %"),
    ("T3", "product page", "Grind selector shown before add-to-cart", "orders per product-page user", "5.0", "1.2", "percentage points"),
    ("T4", "subscribe page", "Delivery-frequency picker replaces the dropdown", "subscriptions started per subscribe-page user", "6.0", "10", "relative %"),
    ("T5", "subscribe page", "Plan comparison table", "subscriptions started per subscribe-page user", "6.0", "16", "relative %"),
    ("T6", "homepage", "Free-shipping threshold in the announcement bar", "orders per homepage user", "3.0", "14", "relative %"),
]
# page, unit, the weekly level the eight weeks scatter around
TRAFFIC = [
    ("homepage", "users", 29400),
    ("product page", "users", 19000),
    ("subscribe page", "sessions", 14125),
    ("cart", "users", 6100),
    ("blog", "users", 11800),
    ("checkout", "users", 3900),
]

RULES_MD = f"""\
# Quillfeather Coffee Roasters: experimentation rules

These rules decide which proposed tests run in the next testing calendar, when each one starts, and which are rejected. They apply to every test in `test_backlog.csv`.

## Sizing a test
- Every test is an A/B test: control and one variant, each shown to half of the page's users. A running test takes all of its page's traffic.
- p1 is the test's baseline rate (`baseline_rate_pct` ÷ 100). p2 is the rate the expected lift would give. A lift whose `lift_unit` is `relative %` multiplies the baseline: p2 = p1 × (1 + `expected_lift` ÷ 100). A lift whose `lift_unit` is `percentage points` adds to it: p2 = p1 + `expected_lift` ÷ 100.
- Sample size per variant: n = ({facts.SIZING_Z_ALPHA} + {facts.SIZING_Z_BETA})² × (p1 × (1 − p1) + p2 × (1 − p2)) ÷ (p2 − p1)², rounded up to the next whole user. {facts.SIZING_Z_ALPHA} is the z-value of a two-sided 5% significance level and {facts.SIZING_Z_BETA} the z-value of 80% power.
- A page's weekly users are the mean of its {facts.SIZING_TRAFFIC_WEEKS} weeks in `traffic_by_page.csv`. A page measured in sessions (`unit` is `sessions`) has {facts.SIZING_USERS_PER_SESSION} users per session: its weekly users are {facts.SIZING_USERS_PER_SESSION} × the mean of its weekly sessions.
- Weeks needed = 2 × n ÷ the page's weekly users, rounded up to a whole week.

## Limits
- A test that needs more than {facts.SIZING_MAX_WEEKS} weeks is rejected.
- One test at a time on each page. Tests on different pages may run in the same weeks.
- The calendar runs from week 1 to week {facts.SIZING_CALENDAR_WEEKS}. Week {facts.SIZING_FREEZE_WEEK} is the spring-sale code freeze: no test may be running in week {facts.SIZING_FREEZE_WEEK}. A test runs whole, consecutive weeks and must end by week {facts.SIZING_CALENDAR_WEEKS}.

## Priority and the calendar
- A test's priority is its page's weekly users × (p2 − p1): the extra conversions a week its expected lift would bring. Higher priority goes first; a tie goes to the lower test number.
- Take the tests that are not rejected in priority order. Give each one the earliest start week at which every week it runs is free of the tests already placed on its page, none of its weeks is week {facts.SIZING_FREEZE_WEEK}, and it ends by week {facts.SIZING_CALENDAR_WEEKS}. A test that cannot be placed is rejected.
"""


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def build() -> dict[str, str]:
    rng = random.Random(SEED)
    traffic = []
    for page, unit, level in TRAFFIC:
        for week in range(facts.SIZING_TRAFFIC_WEEKS):
            start = FIRST_WEEK + dt.timedelta(weeks=week - facts.SIZING_TRAFFIC_WEEKS)
            traffic.append([start.isoformat(), page, unit, round(level * rng.uniform(0.94, 1.06))])
    traffic.sort(key=lambda row: (row[0], row[1]))
    return {
        "testing_rules.md": RULES_MD,
        "test_backlog.csv": _csv_text(
            ["test_id", "page", "change", "primary_metric", "baseline_rate_pct", "expected_lift", "lift_unit"],
            [list(row) for row in BACKLOG]),
        "traffic_by_page.csv": _csv_text(["week_start", "page", "unit", "traffic"], traffic),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    drift = []
    for name, text in build().items():
        path = HERE / name
        if args.write:
            path.write_text(text)
        elif not path.exists() or path.read_text() != text:
            drift.append(name)
    for name in drift:
        print(f"DRIFT: {name} differs from the generator's output", file=sys.stderr)
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
