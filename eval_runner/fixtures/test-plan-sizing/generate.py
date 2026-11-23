#!/usr/bin/env python3
"""Write, or check, the sources of the test-plan-sizing task.

Deterministic: the traffic and the backlog come from a seeded generator and
everything else is written out below, so running it twice writes the same
bytes. The rules are rendered from the constants in
`eval_runner/task_facts_conversion.py`, the same ones its oracle applies, and
`build()` refuses a backlog in which a figure sits so close to a rounding or
ordering edge that two careful computations could disagree (see `_check`).

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
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eval_runner import task_facts_conversion as facts  # noqa: E402

SEED = 4417
FIRST_WEEK = dt.date(2026, 11, 9)
# site, traffic unit, users per session, freeze week, tests at once, size, tests proposed
SITES = [
    ("us", "users", "", 5, 3, 1.00, 22),
    ("uk", "users", "", 6, 2, 0.74, 16),
    ("de", "sessions", "0.80", 7, 2, 0.70, 16),
    ("ca", "users", "", 5, 2, 0.52, 12),
    ("au", "sessions", "0.85", 3, 2, 0.48, 12),
    ("fr", "sessions", "0.75", 8, 2, 0.46, 12),
    ("nl", "users", "", 6, 1, 0.42, 12),
    ("se", "users", "", 7, 1, 0.38, 10),
    ("ch", "users", "", 7, 1, 0.36, 10),
    ("at", "users", "", 7, 1, 0.33, 10),
    ("ie", "users", "", 6, 1, 0.31, 9),
    ("nz", "users", "", 3, 1, 0.30, 9),
]
# page, weekly users on the largest site, baseline rates (%), changes
PAGES = {
    "homepage": (62000, (2.6, 3.4), [
        "Hero leads with the subscription offer", "Free-shipping threshold in the announcement bar",
        "Customer photos replace the studio hero", "Coffee quiz above the fold", "Shorter top navigation",
        "Roaster's story moved below the products"]),
    "collection page": (41000, (4.2, 5.6), [
        "Roast-level filter shown first", "Best-seller badges on the grid", "Two-column grid on phones",
        "Tasting-note chips under each bag", "Sort by roast date by default"]),
    "product page": (46000, (5.0, 6.8), [
        "Tasting notes above the price", "Grind selector before add-to-cart", "Subscribe-and-save selected by default",
        "Brew-guide video in the gallery", "Reviews summary next to the price", "Bag size as buttons, not a dropdown"]),
    "subscribe page": (16000, (5.5, 8.0), [
        "Plan comparison table", "Delivery-frequency picker replaces the dropdown", "First-bag discount in the plan cards",
        "Pause-anytime promise above the button", "Fewer plan options"]),
    "cart": (12500, (26.0, 34.0), [
        "Free-shipping progress bar", "Express wallets at the top", "Filter-paper cross-sell removed",
        "Delivery date estimate under the total", "Subscription upsell for one-off bags"]),
    "checkout": (8200, (56.0, 68.0), [
        "One-page checkout", "Address autocomplete", "Order summary collapsed on phones",
        "Guest checkout first", "Trust badges next to the card fields"]),
}
TRAFFIC_SCALE = 0.8
POINTS_TESTS = 26          # lifts in percentage points
HALF_TRAFFIC_TESTS = 22    # tests that run on half of their page's users
OUTAGE_ROWS = 11           # page-weeks with a tracking outage, on user-measured sites

RULES_MD = f"""\
# Quillfeather Coffee Roasters: experimentation rules, next testing calendar

These rules decide which proposed tests in `test_backlog.csv` run in the next calendar, when each starts, and which are rejected. They apply to every storefront in `sites.csv`.

## Sizing a test
- Every test is an A/B test: control and one variant. A test runs on the share of its page's users in `traffic_share_pct`, split half and half between control and the variant.
- p1 is the test's baseline rate (`baseline_rate_pct` ÷ 100). p2 is the rate the expected lift would give. A lift whose `lift_unit` is `relative %` multiplies the baseline: p2 = p1 × (1 + `expected_lift` ÷ 100). A lift whose `lift_unit` is `percentage points` adds to it: p2 = p1 + `expected_lift` ÷ 100.
- Sample size per variant: n = ({facts.SIZING_Z_ALPHA} + {facts.SIZING_Z_BETA})² × (p1 × (1 − p1) + p2 × (1 − p2)) ÷ (p2 − p1)², rounded up to the next whole user. {facts.SIZING_Z_ALPHA} is the z-value of a two-sided 5% significance level and {facts.SIZING_Z_BETA} the z-value of 80% power.
- A page's weekly users are the mean of its weeks in `traffic_by_page.csv`, leaving out every week whose `note` is `{facts.SIZING_OUTAGE_NOTE}`. A site whose analytics counts sessions (`unit` is `sessions`) has the users per session given in `sites.csv`: its pages' weekly users are that figure × the mean of their weekly sessions.
- Weeks needed = 2 × n ÷ (the page's weekly users × `traffic_share_pct` ÷ 100), rounded up to a whole week.

## Limits
- A test that needs more than {facts.SIZING_MAX_WEEKS} weeks is rejected as too long.
- One test at a time on each page of a site.
- A site runs at most its `max_tests_at_once` tests in any one week.
- No test may be running in its site's `freeze_week`.
- The calendar runs from week 1 to week {facts.SIZING_CALENDAR_WEEKS}. A test runs whole, consecutive weeks and must end by week {facts.SIZING_CALENDAR_WEEKS}.

## Priority and the calendar
- A test's priority is its page's weekly users × `traffic_share_pct` ÷ 100 × (p2 − p1): the extra conversions a week its expected lift would bring. Higher priority goes first; a tie goes to the lower test number.
- Take every test not rejected as too long, from every site at once, in priority order. Give each one the earliest start week at which none of its weeks is its site's freeze week, none of its weeks overlaps a test already placed on the same page of the same site, in none of its weeks would its site be running more than `max_tests_at_once` tests (counting the tests already placed), and it ends by week {facts.SIZING_CALENDAR_WEEKS}. A test that cannot be placed has no slot and is rejected.
"""


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def build() -> dict[str, str]:
    rng = random.Random(SEED)
    sites_csv = [[site, unit, ratio, freeze, most] for site, unit, ratio, freeze, most, _size, _tests in SITES]
    traffic = []
    for week in range(facts.SIZING_TRAFFIC_WEEKS):
        start = FIRST_WEEK + dt.timedelta(weeks=week)
        for site, unit, ratio, _freeze, _most, size, _tests in SITES:
            for page, (level, _rates, _changes) in PAGES.items():
                users = level * size * TRAFFIC_SCALE * rng.uniform(0.93, 1.07)
                value = users / float(ratio) if unit == "sessions" else users
                traffic.append([start.isoformat(), site, page, unit, round(value), ""])
    # Tracking outages: a week of a page on a user-measured site that recorded a fraction of its traffic.
    candidates = [index for index, row in enumerate(traffic) if row[3] == "users"]
    for index in rng.sample(candidates, OUTAGE_ROWS):
        traffic[index][4] = round(traffic[index][4] * rng.uniform(0.18, 0.4))
        traffic[index][5] = facts.SIZING_OUTAGE_NOTE
    sites = facts.sizing_sites(_csv_text(["site", "unit", "users_per_session", "freeze_week", "max_tests_at_once"],
                                         sites_csv))
    traffic_rows = [dict(zip(["week_start", "site", "page", "unit", "traffic", "note"], map(str, row)))
                    for row in traffic]
    users = facts.sizing_weekly_users(traffic_rows, sites)

    backlog: list[list] = []
    priorities: list[Fraction] = []
    placed = []
    for site, *_rest, tests in SITES:
        pages = [page for page in PAGES for _ in range(4)]
        rng.shuffle(pages)
        placed.extend((site, page) for page in pages[:tests])
    # A points lift or a part-traffic test only where no other trap is: a site counting users,
    # a page without an outage week. Each test then carries one kind of trap at most.
    outages = {(row[1], row[2]) for row in traffic if row[5]}
    eligible = [index for index, (site, page) in enumerate(placed)
                if sites[site]["users_per_session"] is None and (site, page) not in outages]
    chosen = rng.sample(eligible, POINTS_TESTS + HALF_TRAFFIC_TESTS)
    kinds = ["plain"] * len(placed)
    for position, index in enumerate(chosen):
        kinds[index] = "points" if position < POINTS_TESTS else "half"
    for number, ((site, page), kind) in enumerate(zip(placed, kinds), 1):
        low, high = PAGES[page][1]
        change = rng.choice(PAGES[page][2])
        while True:
            baseline = round(rng.uniform(low, high), 1)
            if kind == "points":
                lift, unit = round(rng.uniform(0.08, 0.2) * baseline, 1), "percentage points"
            else:
                lift, unit = rng.choice([5, 6, 8, 10, 12, 14, 15, 18, 20, 22, 25, 30]), "relative %"
            share = 50 if kind == "half" else 100
            test = {"baseline_rate_pct": str(baseline), "expected_lift": str(lift), "lift_unit": unit}
            p1, p2 = facts.sizing_rates(test)
            exact = facts.sizing_sample_size_exact(p1, p2)
            weeks = 2 * facts.sizing_sample_size(p1, p2) / (users[site, page] * Fraction(share, 100))
            priority = users[site, page] * Fraction(share, 100) * (p2 - p1)
            if (Fraction(1, 1000) < exact - int(exact) < Fraction(999, 1000)
                    and abs(weeks - round(weeks)) > Fraction(3, 100)
                    and all(abs(priority - other) > Fraction(1, 20) for other in priorities)):
                break
        priorities.append(priority)
        backlog.append([f"T{number:03d}", site, page, change, baseline, lift, unit, share])
    files = {
        "testing_rules.md": RULES_MD,
        "sites.csv": _csv_text(["site", "unit", "users_per_session", "freeze_week", "max_tests_at_once"], sites_csv),
        "test_backlog.csv": _csv_text(
            ["test_id", "site", "page", "change", "baseline_rate_pct", "expected_lift", "lift_unit", "traffic_share_pct"],
            backlog),
        "traffic_by_page.csv": _csv_text(["week_start", "site", "page", "unit", "traffic", "note"], traffic),
    }
    _check(files)
    return files


def _check(files: dict[str, str]) -> None:
    """Refuse a backlog whose calendar does not exercise every rule."""
    plan = facts.sizing_plan(files)
    assert all(test["traps"] <= 1 for test in plan)
    kinds = [test["category"] for test in plan]
    assert kinds.count("sessions site") >= 20 and kinds.count("outage page") >= 6, (
        {name: kinds.count(name) for name in facts.SIZING_CATEGORIES})
    assert kinds.count("points lift") == POINTS_TESTS and kinds.count("part traffic") == HALF_TRAFFIC_TESTS
    status = [test["status"] for test in plan]
    assert status.count("too long") >= 20 and status.count("no slot") >= 8 and status.count("run") >= 70, (
        {name: status.count(name) for name in facts.SIZING_STATUSES})


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
