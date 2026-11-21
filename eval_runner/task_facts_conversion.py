"""The figures of the conversion tasks, computed from the text of their sources.

Tasks: test-plan-sizing.

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


REFERENCES = {
    "test-plan-sizing": sizing_reference,
}
