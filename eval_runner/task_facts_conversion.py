"""The figures of the conversion tasks, computed from the text of their sources.

Tasks: test-plan-sizing, funnel-dropoff.

Each `*_reference` function takes a task's supplied sources (file name ->
text, as `task_references.supplied_sources` reads them from a recorded
prompt) and returns the figures its rubric checks, under `answers` by answer
label, beside the intermediate figures a judge needs to read a reply. The
task files' `near` targets are these answers; `tests/test_tasks_conversion.py`
recomputes every one of them from the committed fixtures with code of its own.

The constants below are the numbers the sources state. Each fixture's
generator (`eval_runner/fixtures/<folder>/generate.py`) renders its rules from
the same constants, so a rule the candidate reads and the rule applied here
cannot drift apart.

These references reach the judge through `task_references.task_reference`
and are versioned with `task_references.VERSION`.

All brands, people, URLs and figures here are invented.
"""
from __future__ import annotations

import csv
import io
import math
from decimal import Decimal
from fractions import Fraction


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _ceil(value: Fraction) -> int:
    return math.ceil(value)


# ------------------------------------------------------------------ test-plan-sizing

# Decimals, so the rules render them as written; the arithmetic below is exact (Fraction).
SIZING_Z_ALPHA = Decimal("1.96")       # two-sided 5% significance
SIZING_Z_BETA = Decimal("0.84")        # 80% power
SIZING_USERS_PER_SESSION = Decimal("0.8")
SIZING_MAX_WEEKS = 4
SIZING_FREEZE_WEEK = 5
SIZING_CALENDAR_WEEKS = 10
SIZING_TRAFFIC_WEEKS = 8


def sizing_rates(test: dict) -> tuple[Fraction, Fraction]:
    """(p1, p2): the baseline rate and the rate the expected lift would give."""
    p1 = Fraction(test["baseline_rate_pct"]) / 100
    lift = Fraction(test["expected_lift"])
    if test["lift_unit"] == "percentage points":
        return p1, p1 + lift / 100
    if test["lift_unit"] == "relative %":
        return p1, p1 * (1 + lift / 100)
    raise ValueError(f"unknown lift_unit {test['lift_unit']!r}")


def sizing_sample_size(p1: Fraction, p2: Fraction) -> int:
    """Users per variant, rounded up: (z_a + z_b)^2 (p1 q1 + p2 q2) / (p2 - p1)^2."""
    z = Fraction(SIZING_Z_ALPHA + SIZING_Z_BETA) ** 2
    return _ceil(z * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2)


def sizing_weekly_users(traffic: list[dict]) -> dict[str, Fraction]:
    """Each page's weekly users: the mean of its weeks, sessions turned into users."""
    by_page: dict[str, list[dict]] = {}
    for row in traffic:
        by_page.setdefault(row["page"], []).append(row)
    users = {}
    for page, rows in by_page.items():
        if len(rows) != SIZING_TRAFFIC_WEEKS or len({row["unit"] for row in rows}) != 1:
            raise ValueError(f"{page}: expected {SIZING_TRAFFIC_WEEKS} weeks in one unit")
        mean = Fraction(sum(int(row["traffic"]) for row in rows), len(rows))
        users[page] = mean * Fraction(SIZING_USERS_PER_SESSION) if rows[0]["unit"] == "sessions" else mean
    return users


def sizing_schedule(tests: list[dict]) -> dict[str, int]:
    """Start week of each test, 0 when it does not run, by the rules' greedy order.

    Each test is a dict with `test_id`, `page`, `weeks` and `priority`.
    """
    start = {test["test_id"]: 0 for test in tests}
    runnable = [test for test in tests if test["weeks"] <= SIZING_MAX_WEEKS]
    order = sorted(runnable, key=lambda test: (-test["priority"], int(test["test_id"][1:])))
    busy: dict[str, set[int]] = {}
    for test in order:
        taken = busy.setdefault(test["page"], set())
        for first in range(1, SIZING_CALENDAR_WEEKS - test["weeks"] + 2):
            weeks = set(range(first, first + test["weeks"]))
            if SIZING_FREEZE_WEEK not in weeks and not weeks & taken:
                start[test["test_id"]] = first
                taken |= weeks
                break
    return start


def sizing_reference(sources: dict[str, str]) -> dict:
    tests = _rows(sources["test_backlog.csv"])
    users = sizing_weekly_users(_rows(sources["traffic_by_page.csv"]))
    sized = []
    for test in tests:
        p1, p2 = sizing_rates(test)
        n = sizing_sample_size(p1, p2)
        page_users = users[test["page"]]
        sized.append({
            "test_id": test["test_id"], "page": test["page"], "p1": p1, "p2": p2, "n": n,
            "weeks": _ceil(2 * n / page_users), "priority": page_users * (p2 - p1),
        })
    start = sizing_schedule(sized)
    # A1-A6 sample sizes, A7-A12 weeks, A13-A18 start weeks, each in test order.
    values = [test["n"] for test in sized] + [test["weeks"] for test in sized] + [
        start[test["test_id"]] for test in sized]
    return {
        "answers": {f"A{index}": value for index, value in enumerate(values, 1)},
        "weekly_users_by_page": {page: round(float(value), 2) for page, value in users.items()},
        "tests": [
            {
                "test_id": test["test_id"], "page": test["page"],
                "baseline_rate": float(test["p1"]), "rate_with_expected_lift": round(float(test["p2"]), 6),
                "sample_size_per_variant": test["n"], "weeks_needed": test["weeks"],
                "priority_extra_conversions_per_week": round(float(test["priority"]), 2),
                "start_week": start[test["test_id"]],
                "end_week": start[test["test_id"]] + test["weeks"] - 1 if start[test["test_id"]] else None,
                "rejected_because": (
                    f"needs {test['weeks']} weeks, more than {SIZING_MAX_WEEKS}"
                    if test["weeks"] > SIZING_MAX_WEEKS else
                    "cannot be placed in the calendar" if not start[test["test_id"]] else None
                ),
            }
            for test in sized
        ],
        "interpretation": (
            "Answers A1-A6 are sample sizes per variant, A7-A12 weeks needed and A13-A18 start weeks "
            "(0 = not run), each in test order T1-T6, under testing_rules.md."
        ),
    }


# -------------------------------------------------------------------- funnel-dropoff

FUNNEL_STEPS = ("cart", "shipping", "payment", "order")
FUNNEL_BOT_BROWSER = "HeadlessChrome"
FUNNEL_REFERENCE_WEEK = ("2026-03-02", "2026-03-08")
FUNNEL_RANGE_POINTS = 5
FUNNEL_DOUBLE_FIRED_DAYS = ("2026-03-10", "2026-03-11", "2026-03-12")
FUNNEL_ORDER_VALUE = Decimal("72.00")


def funnel_counts(rows: list[dict]) -> dict[tuple[str, str], dict[str, dict[str, int]]]:
    """(device, browser) -> day -> step -> sessions: automated rows out, double-fired orders halved."""
    counts: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    for row in rows:
        if row["browser"] == FUNNEL_BOT_BROWSER:
            continue
        value = int(row["count"])
        if row["step"] == "order" and row["date"] in FUNNEL_DOUBLE_FIRED_DAYS:
            if value % 2:
                raise ValueError(f"an odd double-fired order count on {row['date']}")
            value //= 2
        day = counts.setdefault((row["device"], row["browser"]), {}).setdefault(row["date"], {})
        if row["step"] in day:
            raise ValueError(f"{row['date']} {row['device']} / {row['browser']} {row['step']} appears twice")
        day[row["step"]] = value
    return counts


def _step_rate(days: dict[str, dict[str, int]], dates: list[str], step: str, start: str | None = None) -> Fraction:
    """A step's rate over some days: sessions at it ÷ sessions at `start` (the step before it)."""
    start = start or FUNNEL_STEPS[FUNNEL_STEPS.index(step) - 1]
    return Fraction(sum(days[date][step] for date in dates), sum(days[date][start] for date in dates))


def funnel_breaks(counts: dict) -> list[dict]:
    """Every segment step that broke: below its normal range on a day and every day after it."""
    found = []
    for segment, days in sorted(counts.items()):
        dates = sorted(days)
        reference = [date for date in dates if FUNNEL_REFERENCE_WEEK[0] <= date <= FUNNEL_REFERENCE_WEEK[1]]
        for step in FUNNEL_STEPS[1:]:
            low = _step_rate(days, reference, step) - Fraction(FUNNEL_RANGE_POINTS, 100)
            below = [_step_rate(days, [date], step) < low for date in dates]
            first = None
            for index in range(len(dates) - 1, -1, -1):
                if not below[index]:
                    break
                first = dates[index]
            if first:
                found.append({"segment": segment, "step": step, "first_day": first})
    return found


def funnel_causes(text: str) -> list[dict]:
    """The suspected causes table: id, date, segments ('every segment' or a list) and step."""
    causes = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0].startswith("C") and cells[0][1:].isdigit():
            segments = None if cells[3] == "every segment" else [
                tuple(part.strip() for part in item.split("/")) for item in cells[3].split(",")]
            causes.append({"id": cells[0], "date": cells[2], "segments": segments, "step": cells[4]})
    return causes


def funnel_reference(sources: dict[str, str]) -> dict:
    counts = funnel_counts(_rows(sources["funnel_daily.csv"]))
    breaks = funnel_breaks(counts)
    if len(breaks) != 1:
        raise ValueError(f"expected one break, found {len(breaks)}")
    (broken,) = breaks
    dates = sorted({date for days in counts.values() for date in days})
    before = [date for date in dates if date < broken["first_day"]]
    after = [date for date in dates if date >= broken["first_day"]]

    def conversion(period: list[str]) -> Fraction:
        return Fraction(
            sum(days[date]["order"] for days in counts.values() for date in period),
            sum(days[date]["cart"] for days in counts.values() for date in period))

    days = counts[broken["segment"]]
    previous = FUNNEL_STEPS[FUNNEL_STEPS.index(broken["step"]) - 1]
    to_order = _step_rate(days, before, "order", start=previous)
    expected = sum(days[date][previous] for date in after) * to_order
    lost = round(expected - sum(days[date]["order"] for date in after))
    causes = funnel_causes(sources["suspected_causes.md"])
    segments = sorted(counts)

    def consistent(cause: dict) -> bool:
        return any(item["segment"] in (cause["segments"] or segments) and item["step"] == cause["step"]
                   and item["first_day"] == cause["date"] for item in breaks)

    answers = [
        round(float(conversion(before)) * 100, 2),
        round(float(conversion(after)) * 100, 2),
        int(broken["first_day"][-2:]),
        round(float(_step_rate(days, before, broken["step"])) * 100, 1),
        round(float(_step_rate(days, after, broken["step"])) * 100, 1),
        lost,
        float(lost * FUNNEL_ORDER_VALUE),
    ] + [0 if consistent(cause) else 1 for cause in causes]
    reference_week = [date for date in dates if FUNNEL_REFERENCE_WEEK[0] <= date <= FUNNEL_REFERENCE_WEEK[1]]
    return {
        "answers": {f"A{index}": value for index, value in enumerate(answers, 1)},
        "break": {"segment": " / ".join(broken["segment"]), "step": broken["step"],
                  "first_day": broken["first_day"]},
        "before_days": [before[0], before[-1]],
        "after_days": [after[0], after[-1]],
        "normal_ranges_percent": {
            " / ".join(segment): {
                step: [round(float(_step_rate(counts[segment], reference_week, step)) * 100 - FUNNEL_RANGE_POINTS, 2),
                       round(float(_step_rate(counts[segment], reference_week, step)) * 100 + FUNNEL_RANGE_POINTS, 2)]
                for step in FUNNEL_STEPS[1:]
            }
            for segment in segments
        },
        "step_rates_before_and_after_percent": {
            " / ".join(segment): {
                step: [round(float(_step_rate(counts[segment], before, step)) * 100, 2),
                       round(float(_step_rate(counts[segment], after, step)) * 100, 2)]
                for step in FUNNEL_STEPS[1:]
            }
            for segment in segments
        },
        "days_below_normal_range": {
            f"{' / '.join(segment)} {step}": [
                date for date in sorted(counts[segment])
                if _step_rate(counts[segment], [date], step)
                < _step_rate(counts[segment], reference_week, step) - Fraction(FUNNEL_RANGE_POINTS, 100)
            ]
            for segment in segments for step in FUNNEL_STEPS[1:]
            if any(_step_rate(counts[segment], [date], step)
                   < _step_rate(counts[segment], reference_week, step) - Fraction(FUNNEL_RANGE_POINTS, 100)
                   for date in counts[segment])
        },
        "orders_lost_working": {
            "sessions_at_the_step_before_after_the_break": sum(days[date][previous] for date in after),
            "rate_from_that_step_to_an_order_before_the_break_percent": round(float(to_order) * 100, 4),
            "expected_orders_after_the_break": round(float(expected), 2),
            "recorded_orders_after_the_break": sum(days[date]["order"] for date in after),
        },
        "causes_ruled_out": {cause["id"]: not consistent(cause) for cause in causes},
        "interpretation": (
            "Figures follow analysis_rules.md: automated rows left out, double-fired order rows halved. "
            "A7 is A6 orders times the stated average order value. A8-A13 are 1 for a cause the data rules out."
        ),
    }


REFERENCES = {
    "test-plan-sizing": sizing_reference,
    "funnel-dropoff": funnel_reference,
}
