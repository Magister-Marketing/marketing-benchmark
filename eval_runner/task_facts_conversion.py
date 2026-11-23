"""The figures of the conversion tasks, computed from the text of their sources.

Tasks: test-plan-sizing, funnel-dropoff, ab-test-readout (from its version 4).

Each `*_reference` function takes a task's supplied sources (file name ->
text, as `task_references.supplied_sources` reads them from a recorded
prompt) and returns the figures its rubric checks, under `answers` by answer
label, beside the intermediate figures a judge needs to read a reply. The
task files' `near` targets are these answers; `tests/test_tasks_conversion.py`
recomputes every one of them from the committed fixtures with code of its own.
test-plan-sizing has no answer block: its reply carries a calendar file, which
`facts_for` (called from `bench.measured_facts`) reads and counts wrong rows in.

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
from functools import lru_cache
from pathlib import Path

from .workflows import common


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _ceil(value: Fraction) -> int:
    return math.ceil(value)


# ------------------------------------------------------------------ test-plan-sizing

# Decimals, so the rules render them as written; the arithmetic below is exact (Fraction).
SIZING_Z_ALPHA = Decimal("1.96")       # two-sided 5% significance
SIZING_Z_BETA = Decimal("0.84")        # 80% power
SIZING_MAX_WEEKS = 4
SIZING_CALENDAR_WEEKS = 12
SIZING_TRAFFIC_WEEKS = 8
SIZING_OUTAGE_NOTE = "tracking outage"
SIZING_FILE = "test_calendar.csv"
SIZING_COLUMNS = ("test_id", "page_weekly_users", "sample_size_per_variant", "weeks_needed", "start_week", "status")
SIZING_STATUSES = ("run", "too long", "no slot")
# What can go wrong in sizing a test, one kind per test (the generator keeps them apart).
SIZING_CATEGORIES = ("sessions site", "outage page", "points lift", "part traffic", "plain")
SIZING_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "test-plan-sizing"


def sizing_rates(test: dict) -> tuple[Fraction, Fraction]:
    """(p1, p2): the baseline rate and the rate the expected lift would give."""
    p1 = Fraction(test["baseline_rate_pct"]) / 100
    lift = Fraction(test["expected_lift"])
    if test["lift_unit"] == "percentage points":
        return p1, p1 + lift / 100
    if test["lift_unit"] == "relative %":
        return p1, p1 * (1 + lift / 100)
    raise ValueError(f"unknown lift_unit {test['lift_unit']!r}")


def sizing_sample_size_exact(p1: Fraction, p2: Fraction) -> Fraction:
    """(z_a + z_b)^2 (p1 q1 + p2 q2) / (p2 - p1)^2, before rounding up."""
    z = Fraction(SIZING_Z_ALPHA + SIZING_Z_BETA) ** 2
    return z * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2


def sizing_sample_size(p1: Fraction, p2: Fraction) -> int:
    """Users per variant, rounded up."""
    return _ceil(sizing_sample_size_exact(p1, p2))


def sizing_sites(text: str) -> dict[str, dict]:
    sites = {}
    for row in _rows(text):
        sites[row["site"]] = {
            "users_per_session": Fraction(row["users_per_session"]) if row["users_per_session"] else None,
            "freeze_week": int(row["freeze_week"]),
            "max_tests_at_once": int(row["max_tests_at_once"]),
        }
    return sites


def sizing_weekly_users(traffic: list[dict], sites: dict[str, dict]) -> dict[tuple[str, str], Fraction]:
    """Each page's weekly users: the mean of its weeks without a tracking outage, sessions turned into users."""
    by_page: dict[tuple[str, str], list[dict]] = {}
    for row in traffic:
        by_page.setdefault((row["site"], row["page"]), []).append(row)
    users = {}
    for (site, page), rows in by_page.items():
        if len(rows) != SIZING_TRAFFIC_WEEKS or len({row["unit"] for row in rows}) != 1:
            raise ValueError(f"{site} {page}: expected {SIZING_TRAFFIC_WEEKS} weeks in one unit")
        kept = [int(row["traffic"]) for row in rows if row["note"] != SIZING_OUTAGE_NOTE]
        mean = Fraction(sum(kept), len(kept))
        if rows[0]["unit"] == "sessions":
            mean *= sites[site]["users_per_session"]
        users[site, page] = mean
    return users


def sizing_schedule(tests: list[dict], sites: dict[str, dict]) -> dict[str, int]:
    """Start week of each test, 0 when it does not run, by the rules' greedy order.

    Each test is a dict with `test_id`, `site`, `page`, `weeks` and `priority`.
    """
    start = {test["test_id"]: 0 for test in tests}
    runnable = [test for test in tests if test["weeks"] <= SIZING_MAX_WEEKS]
    order = sorted(runnable, key=lambda test: (-test["priority"], int(test["test_id"][1:])))
    page_weeks: dict[tuple[str, str], set[int]] = {}
    site_load: dict[str, dict[int, int]] = {}
    for test in order:
        site = sites[test["site"]]
        taken = page_weeks.setdefault((test["site"], test["page"]), set())
        load = site_load.setdefault(test["site"], {})
        for first in range(1, SIZING_CALENDAR_WEEKS - test["weeks"] + 2):
            weeks = range(first, first + test["weeks"])
            if (site["freeze_week"] not in weeks and not taken.intersection(weeks)
                    and all(load.get(week, 0) < site["max_tests_at_once"] for week in weeks)):
                start[test["test_id"]] = first
                taken.update(weeks)
                for week in weeks:
                    load[week] = load.get(week, 0) + 1
                break
    return start


def sizing_plan(sources: dict[str, str]) -> list[dict]:
    """Every test of the backlog with what the rules give it, and the traps it carries."""
    sites = sizing_sites(sources["sites.csv"])
    traffic = _rows(sources["traffic_by_page.csv"])
    users = sizing_weekly_users(traffic, sites)
    outage_pages = {(row["site"], row["page"]) for row in traffic if row["note"] == SIZING_OUTAGE_NOTE}
    sized = []
    for test in _rows(sources["test_backlog.csv"]):
        p1, p2 = sizing_rates(test)
        n = sizing_sample_size(p1, p2)
        page = (test["site"], test["page"])
        share = Fraction(test["traffic_share_pct"]) / 100
        sized.append({
            "test_id": test["test_id"], "site": test["site"], "page": test["page"], "p1": p1, "p2": p2,
            "page_weekly_users": users[page], "n": n, "weeks": _ceil(2 * n / (users[page] * share)),
            "priority": users[page] * share * (p2 - p1),
            "category": ("sessions site" if sites[test["site"]]["users_per_session"] is not None else
                         "outage page" if page in outage_pages else
                         "points lift" if test["lift_unit"] == "percentage points" else
                         "part traffic" if share < 1 else "plain"),
            "traps": sum((sites[test["site"]]["users_per_session"] is not None, page in outage_pages,
                          test["lift_unit"] == "percentage points", share < 1)),
        })
    start = sizing_schedule(sized, sites)
    for test in sized:
        test["start"] = start[test["test_id"]]
        test["status"] = ("too long" if test["weeks"] > SIZING_MAX_WEEKS else
                          "run" if test["start"] else "no slot")
    return sized


def sizing_reference(sources: dict[str, str]) -> dict:
    plan = sizing_plan(sources)
    by_status = {status: [test["test_id"] for test in plan if test["status"] == status] for status in SIZING_STATUSES}
    return {
        "tests": len(plan),
        "tests_by_status": {status: len(ids) for status, ids in by_status.items()},
        "tests_by_kind": {category: sum(1 for test in plan if test["category"] == category)
                          for category in SIZING_CATEGORIES},
        "too_long": [{"test_id": test["test_id"], "weeks_needed": test["weeks"]}
                     for test in plan if test["status"] == "too long"],
        "no_slot": by_status["no slot"],
        "no_slot_by_site": {site: sum(1 for test in plan if test["status"] == "no slot" and test["site"] == site)
                            for site in sorted({test["site"] for test in plan})},
        "last_week_in_use": max(test["start"] + test["weeks"] - 1 for test in plan if test["start"]),
        "interpretation": (
            "Every row of test_calendar.csv is checked by program against the rules (page weekly users, sample "
            "size, weeks, start week, status). Statuses: run, too long (needs more than four weeks), no slot "
            "(no start week satisfies the calendar's limits)."
        ),
    }


@lru_cache(maxsize=1)
def _sizing_plan_on_disk() -> tuple[dict, ...]:
    sources = {path.name: path.read_text() for path in SIZING_FIXTURES.iterdir()
               if path.suffix in (".csv", ".md")}
    return tuple(sizing_plan(sources))


def _number(text: str) -> Fraction | None:
    value = common.money(text)
    return None if value is None else Fraction(value)


def _status(text: str) -> str:
    return common.norm(text).replace("_", " ").replace("-", " ")


def sizing_facts(response_text: str) -> dict:
    """Counts of the calendar's tests that are missing or wrong, by the kind of test.

    A test is sized wrong when its row is missing or its page weekly users, its
    sample size or its weeks are off; that is counted by kind, so each trap has
    a count of its own. Status and start week are counted over every test. A
    test with no row counts as wrong everywhere, so a file left out is that many
    errors, never zero.
    """
    plan = _sizing_plan_on_disk()
    rows = common.tables(response_text, [SIZING_FILE])[SIZING_FILE] or []
    given: dict[str, dict] = {}
    repeated = set()
    for row in rows:
        test_id = common.norm(common.cell(row, "test_id", "test")).upper()
        if test_id in given:
            repeated.add(test_id)
        given.setdefault(test_id, row)
    known = {test["test_id"] for test in plan}

    def value(test: dict, column: str) -> Fraction | None:
        row = given.get(test["test_id"])
        return None if row is None else _number(row.get(column, ""))

    def sized_wrong(test: dict) -> bool:
        users, n, weeks = (value(test, column) for column in SIZING_COLUMNS[1:4])
        return (users is None or abs(users - test["page_weekly_users"]) > Fraction(1, 2)
                or n is None or abs(n - test["n"]) > Fraction(2, 1000) * test["n"]
                or weeks != test["weeks"])

    facts = {
        "sizing_row_accounting_error_count": (
            len(known - set(given)) + len(repeated & known) + len(set(given) - known)),
    }
    for category in SIZING_CATEGORIES:
        facts[f"sizing_wrong_{category.replace(' ', '_')}_count"] = sum(
            1 for test in plan if test["category"] == category and sized_wrong(test))
    facts["sizing_status_wrong_count"] = sum(
        1 for test in plan if test["test_id"] not in given or _status(given[test["test_id"]].get("status", "")) != test["status"])
    facts["sizing_start_wrong_count"] = sum(1 for test in plan if value(test, "start_week") != test["start"])
    # What the reply's own file says, for the judge to compare the reply's summary with.
    statuses = [_status(row.get("status", "")) for row in given.values()]
    for status in SIZING_STATUSES:
        facts[f"sizing_file_{status.replace(' ', '_')}_count"] = statuses.count(status)
    return facts


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts a conversion task adds beyond its answer block, or nothing."""
    task_id = (task or {}).get("id")
    if task_id == "test-plan-sizing":
        return sizing_facts(response_text)
    if task_id == "funnel-dropoff":
        return funnel_facts(response_text)
    return {}


# -------------------------------------------------------------------- funnel-dropoff

FUNNEL_STEPS = ("cart", "shipping", "payment", "order")
FUNNEL_BOT_BROWSER = "HeadlessChrome"
FUNNEL_REFERENCE_WEEK = ("2026-03-02", "2026-03-08")
FUNNEL_RANGE_POINTS = 5
# A segment-day is automated when fewer than this share of its cart sessions reached shipping.
FUNNEL_AUTOMATED_SHIPPING_SHARE = Fraction(2, 100)
# Each double-firing the release log records: the step, the browsers it hit (None: every one) and the days.
FUNNEL_DOUBLE_FIRED = (
    ("order", None, ("2026-03-15", "2026-03-16", "2026-03-17")),
    ("shipping", ("Chrome", FUNNEL_BOT_BROWSER), ("2026-03-20", "2026-03-21", "2026-03-22")),
    ("payment", ("Safari",), ("2026-03-27", "2026-03-28", "2026-03-29")),
)
FUNNEL_ORDER_VALUE = Decimal("72.00")
FUNNEL_TABLE = "segment_diagnosis.csv"
FUNNEL_TABLE_COLUMNS = ("segment", "shipping_before", "shipping_after", "payment_before", "payment_after",
                        "order_before", "order_after", "verdict", "broken_step", "break_day", "orders_lost")
FUNNEL_CAUSES_FILE = "causes.csv"
FUNNEL_VERDICTS = ("broken", "recovered", "normal")
FUNNEL_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "funnel-dropoff"


def funnel_double_fired(row: dict) -> bool:
    return any(row["step"] == step and (browsers is None or row["browser"] in browsers) and row["date"] in days
               for step, browsers, days in FUNNEL_DOUBLE_FIRED)


def funnel_counts(rows: list[dict], halve: tuple[str, ...] = ("order", "shipping", "payment"),
                  automated_after_halving: bool = True) -> dict[tuple[str, str], dict[str, dict[str, int]]]:
    """(device, browser) -> day -> step -> sessions, under the rules: double-fired rows halved, then
    automated segment-days left out. `halve` and `automated_after_halving` exist for the careless readings."""
    counts: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    raw: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    for row in rows:
        value = int(row["count"])
        doubled = funnel_double_fired(row)
        if doubled and value % 2:
            raise ValueError(f"an odd double-fired count on {row['date']}")
        segment = (row["device"], row["browser"])
        for target, halved in ((counts, doubled and row["step"] in halve), (raw, False)):
            day = target.setdefault(segment, {}).setdefault(row["date"], {})
            if row["step"] in day:
                raise ValueError(f"{row['date']} {row['device']} / {row['browser']} {row['step']} appears twice")
            day[row["step"]] = value // 2 if halved else value
    for segment in list(counts):
        for date in list(counts[segment]):
            judged = (counts if automated_after_halving else raw)[segment][date]
            if Fraction(judged.get("shipping", 0), judged["cart"]) < FUNNEL_AUTOMATED_SHIPPING_SHARE:
                del counts[segment][date]
        if not counts[segment]:
            del counts[segment]
    return counts


def _step_rate(days: dict[str, dict[str, int]], dates: list[str], step: str,
               start: str | None = None) -> Fraction | None:
    """A step's rate over some days: sessions at it ÷ sessions at `start` (the step before it), or None
    when no session reached `start` on those days."""
    start = start or FUNNEL_STEPS[FUNNEL_STEPS.index(step) - 1]
    entered = sum(days[date].get(start, 0) for date in dates)
    return Fraction(sum(days[date].get(step, 0) for date in dates), entered) if entered else None


def _reference_days(days: dict) -> list[str]:
    return [date for date in sorted(days) if FUNNEL_REFERENCE_WEEK[0] <= date <= FUNNEL_REFERENCE_WEEK[1]]


def funnel_below(days: dict, step: str) -> list[str]:
    """The days a segment's step rate was below its normal range."""
    reference = _step_rate(days, _reference_days(days), step)
    if reference is None:       # no reference week, so no normal range (only in a careless reading)
        return []
    low = reference - Fraction(FUNNEL_RANGE_POINTS, 100)
    return [date for date in sorted(days)
            if (rate := _step_rate(days, [date], step)) is not None and rate < low]


def funnel_breaks(counts: dict) -> list[dict]:
    """Every segment step that broke: below its normal range on a day and every day after it."""
    found = []
    for segment, days in sorted(counts.items()):
        dates = sorted(days)
        for step in FUNNEL_STEPS[1:]:
            below = set(funnel_below(days, step))
            first = None
            for date in reversed(dates):
                if date not in below:
                    break
                first = date
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


def funnel_diagnosis(sources: dict[str, str], **careless) -> dict:
    """Everything the rules give: the store's figures, one row per segment, a ruling per cause."""
    counts = funnel_counts(_rows(sources["funnel_daily.csv"]), **careless)
    breaks = funnel_breaks(counts)
    dates = sorted({date for days in counts.values() for date in days})
    split = min(item["first_day"] for item in breaks)
    before = [date for date in dates if date < split]
    after = [date for date in dates if date >= split]

    def conversion(period: list[str]) -> Fraction:
        return Fraction(sum(days[date].get("order", 0) for days in counts.values() for date in period if date in days),
                        sum(days[date]["cart"] for days in counts.values() for date in period if date in days))

    table = []
    for segment, days in sorted(counts.items()):
        mine = [item for item in breaks if item["segment"] == segment]
        lost, working = 0, None
        if mine:
            (item,) = mine
            previous = FUNNEL_STEPS[FUNNEL_STEPS.index(item["step"]) - 1]
            own_before = [date for date in sorted(days) if date < item["first_day"]]
            own_after = [date for date in sorted(days) if date >= item["first_day"]]
            to_order = _step_rate(days, own_before, "order", start=previous)
            expected = sum(days[date][previous] for date in own_after) * to_order
            lost = round(expected - sum(days[date].get("order", 0) for date in own_after))
            working = {"sessions_at_the_step_before_from_the_break": sum(days[date][previous] for date in own_after),
                       "rate_from_that_step_to_an_order_before_the_break_percent": round(float(to_order) * 100, 4),
                       "expected_orders": round(float(expected), 2),
                       "recorded_orders": sum(days[date].get("order", 0) for date in own_after)}
        segment_before = [date for date in before if date in days]
        segment_after = [date for date in after if date in days]
        row = {"segment": " / ".join(segment)}
        for step in FUNNEL_STEPS[1:]:
            row[f"{step}_before"] = _step_rate(days, segment_before, step)
            row[f"{step}_after"] = _step_rate(days, segment_after, step)
        row.update({
            "verdict": "broken" if mine else "recovered" if any(funnel_below(days, step) for step in FUNNEL_STEPS[1:])
            else "normal",
            "broken_step": mine[0]["step"] if mine else "none",
            "break_day": int(mine[0]["first_day"][-2:]) if mine else 0,
            "orders_lost": lost,
            "working": working,
        })
        table.append(row)
    segments = sorted(counts)
    rulings = {}
    for cause in funnel_causes(sources["suspected_causes.md"]):
        named = cause["segments"] or segments
        rulings[cause["id"]] = not any(item["segment"] in named and item["step"] == cause["step"]
                                       and item["first_day"] == cause["date"] for item in breaks)
    total = sum(row["orders_lost"] for row in table)
    return {"breaks": breaks, "split": split, "before": before, "after": after,
            "conversion_before": conversion(before), "conversion_after": conversion(after),
            "orders_lost": total, "revenue_lost": total * FUNNEL_ORDER_VALUE, "table": table,
            "causes_ruled_out": rulings, "counts": counts}


def funnel_reference(sources: dict[str, str]) -> dict:
    found = funnel_diagnosis(sources)
    answers = [round(float(found["conversion_before"]) * 100, 2), round(float(found["conversion_after"]) * 100, 2),
               found["orders_lost"], float(found["revenue_lost"])]
    return {
        "answers": {f"A{index}": value for index, value in enumerate(answers, 1)},
        "breaks": [{"segment": " / ".join(item["segment"]), "step": item["step"], "first_day": item["first_day"]}
                   for item in found["breaks"]],
        "store_break_date": found["split"],
        "segment_diagnosis": [
            {key: (round(float(value) * 100, 2) if isinstance(value, Fraction) else value) for key, value in row.items()}
            for row in found["table"]
        ],
        "days_below_normal_range": {
            f"{' / '.join(segment)} {step}": funnel_below(days, step)
            for segment, days in sorted(found["counts"].items()) for step in FUNNEL_STEPS[1:] if funnel_below(days, step)
        },
        "causes_ruled_out": found["causes_ruled_out"],
        "interpretation": (
            "Figures follow analysis_rules.md: double-fired rows halved first, then automated segment-days left out. "
            "The table's rates split at the store's break date; each broken segment's orders lost uses its own break."
        ),
    }


@lru_cache(maxsize=1)
def _funnel_on_disk() -> dict:
    sources = {path.name: path.read_text() for path in FUNNEL_FIXTURES.iterdir() if path.suffix in (".csv", ".md")}
    return funnel_diagnosis(sources)


def _segment_key(text: str) -> str:
    return "/".join(part.strip() for part in common.norm(text).split("/"))


def _word(text: str) -> str:
    return common.norm(text).replace("_", " ").replace("-", " ")


def funnel_facts(response_text: str) -> dict:
    """Counts of what the reply's two files get wrong. A segment or a cause with no row is wrong in every
    count it belongs to; a rate is right within half a tenth of a point."""
    found = _funnel_on_disk()
    files = common.tables(response_text, [FUNNEL_TABLE, FUNNEL_CAUSES_FILE])
    given: dict[str, dict] = {}
    for row in files[FUNNEL_TABLE] or []:
        given.setdefault(_segment_key(common.cell(row, "segment")), row)
    expected = {_segment_key(row["segment"]): row for row in found["table"]}

    def wrong_rate(row: dict | None, column: str, value: Fraction) -> bool:
        number = None if row is None else _number(row.get(column, ""))
        return number is None or abs(number - value * 100) > Fraction(51, 1000)

    def wrong_number(row: dict | None, column: str, value: int, slack: int = 0) -> bool:
        number = None if row is None else _number(row.get(column, ""))
        return number is None or abs(number - value) > slack

    facts = {"funnel_segment_accounting_error_count": len(set(expected) - set(given)) + len(set(given) - set(expected))}
    for period in ("before", "after"):
        facts[f"funnel_rates_{period}_wrong_count"] = sum(
            wrong_rate(given.get(key), f"{step}_{period}", row[f"{step}_{period}"])
            for key, row in expected.items() for step in FUNNEL_STEPS[1:])
    facts["funnel_verdict_wrong_count"] = sum(
        1 for key, row in expected.items()
        if given.get(key) is None or _word(given[key].get("verdict", "")) != row["verdict"]
        or _word(given[key].get("broken_step", "")) != row["broken_step"]
        or wrong_number(given[key], "break_day", row["break_day"]))
    facts["funnel_orders_lost_wrong_count"] = sum(
        1 for key, row in expected.items() if wrong_number(given.get(key), "orders_lost", row["orders_lost"], slack=2))
    rulings: dict[str, str] = {}
    for row in files[FUNNEL_CAUSES_FILE] or []:
        rulings.setdefault(common.norm(common.cell(row, "cause", "id")).upper(), _word(common.cell(row, "ruled_out")))
    consistent = {cause for cause, out in found["causes_ruled_out"].items() if not out}
    look_alike = set(FUNNEL_LOOK_ALIKE_CAUSES)
    for group, members in (("consistent", consistent), ("look_alike", look_alike),
                           ("plain", set(found["causes_ruled_out"]) - consistent - look_alike)):
        facts[f"funnel_causes_{group}_wrong_count"] = sum(
            1 for cause in members if rulings.get(cause) != ("yes" if found["causes_ruled_out"][cause] else "no"))
    return facts


# The causes built to look like the break: a change two days early, dips inside the range, steps
# that fell below it and recovered, the double-fired rows' artefact, and the second break pinned on
# the first release. The rest are plain.
FUNNEL_LOOK_ALIKE_CAUSES = ("C2", "C4", "C6", "C7", "C8", "C9", "C11", "C12", "C13")


# ------------------------------------------------------------------- ab-test-readout

AB_DAYS = 28
AB_WINDOW_FIRST_DAY = 8                       # days 1-7 are the burn-in week
AB_PLANNED_CONTROL_SHARE = {"desktop": Decimal("0.5"), "mobile": Decimal("0.7")}
AB_MIN_VISITORS = 10_000                      # per variant, in the analysis window
AB_CHI_SQUARE_LIMIT = Decimal("3.841")
AB_GUARDRAIL_LIMIT_PERCENT = 20
AB_SHIP_LIFT_PERCENT = Decimal("3.0")
AB_INTERNAL_SOURCE = "internal"            # QA visits forced into variant B: left out
AB_DECISIONS = {
    1: "keep the test running",
    2: "fix the assignment and run the test again",
    3: "do not ship variant B",
    4: "ship variant B",
    5: "keep control",
}


def ab_totals(rows: list[dict], days: range, internal: bool = False) -> dict:
    """(variant, device) -> visitors, signups and billing tickets over some days, every source
    summed, the QA visits left out (`internal` keeps them, for the careless reading)."""
    totals: dict = {}
    for row in rows:
        if int(row["day"]) in days and (internal or row["source"] != AB_INTERNAL_SOURCE):
            cell = totals.setdefault((row["variant"], row["device"]), {"visitors": 0, "signups": 0, "billing_tickets": 0})
            for field in cell:
                cell[field] += int(row[field])
    return totals


def ab_readout(totals: dict) -> dict:
    """Every figure the plan reads from one period's totals, as exact fractions."""
    devices = sorted({device for _variant, device in totals})

    def summed(variant: str, field: str, device: str | None = None) -> int:
        return sum(cell[field] for (arm, where), cell in totals.items()
                   if arm == variant and device in (None, where))

    def rate(variant: str, device: str | None = None) -> Fraction:
        return Fraction(summed(variant, "signups", device), summed(variant, "visitors", device))

    everyone = summed("control", "visitors") + summed("variant_b", "visitors")
    share = {device: Fraction(summed("control", "visitors", device) + summed("variant_b", "visitors", device), everyone)
             for device in devices}
    weighted = {variant: sum(rate(variant, device) * share[device] for device in devices)
                for variant in ("control", "variant_b")}
    chi_square = {}
    for device in devices:
        total = summed("control", "visitors", device) + summed("variant_b", "visitors", device)
        planned = Fraction(AB_PLANNED_CONTROL_SHARE[device])
        chi_square[device] = sum(
            (summed(variant, "visitors", device) - total * part) ** 2 / (total * part)
            for variant, part in (("control", planned), ("variant_b", 1 - planned)))
    tickets = {variant: Fraction(summed(variant, "billing_tickets") * 1000, summed(variant, "visitors"))
               for variant in ("control", "variant_b")}
    return {
        "visitors": {variant: summed(variant, "visitors") for variant in ("control", "variant_b")},
        "pooled_lift": rate("variant_b") / rate("control") - 1,
        "device_lift": {device: rate("variant_b", device) / rate("control", device) - 1 for device in devices},
        "weighted_lift": weighted["variant_b"] / weighted["control"] - 1,
        "chi_square": chi_square,
        "tickets_per_1000": tickets,
        "guardrail_increase": tickets["variant_b"] / tickets["control"] - 1,
        "rates": {f"{variant} {device or 'pooled'}": rate(variant, device)
                  for variant in ("control", "variant_b") for device in (*devices, None)},
        "device_share": share,
    }


def ab_decision(readout: dict) -> int:
    """The number of the first decision rule whose condition holds."""
    if min(readout["visitors"].values()) < AB_MIN_VISITORS:
        return 1
    if max(readout["chi_square"].values()) > Fraction(AB_CHI_SQUARE_LIMIT):
        return 2
    if readout["guardrail_increase"] * 100 > AB_GUARDRAIL_LIMIT_PERCENT:
        return 3
    if readout["weighted_lift"] * 100 >= Fraction(AB_SHIP_LIFT_PERCENT) and all(
            lift > 0 for lift in readout["device_lift"].values()):
        return 4
    return 5


def _percent(value: Fraction, places: int) -> float:
    return round(float(value) * 100, places)


def ab_test_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["experiment_results.csv"])
    window = ab_readout(ab_totals(rows, range(AB_WINDOW_FIRST_DAY, AB_DAYS + 1)))
    burn_in = ab_readout(ab_totals(rows, range(1, AB_WINDOW_FIRST_DAY)))
    whole = ab_readout(ab_totals(rows, range(1, AB_DAYS + 1)))
    with_qa = ab_readout(ab_totals(rows, range(AB_WINDOW_FIRST_DAY, AB_DAYS + 1), internal=True))
    decision = ab_decision(window)
    answers = [
        window["visitors"]["control"],
        window["visitors"]["variant_b"],
        _percent(window["pooled_lift"], 1),
        _percent(window["device_lift"]["desktop"], 1),
        _percent(window["device_lift"]["mobile"], 1),
        _percent(window["weighted_lift"], 1),
        _percent(burn_in["weighted_lift"], 1),
        round(float(window["chi_square"]["desktop"]), 1),
        round(float(window["chi_square"]["mobile"]), 1),
        _percent(window["guardrail_increase"], 1),
        decision,
    ]

    def summary(readout: dict) -> dict:
        return {
            "visitors": readout["visitors"],
            "signup_rates_percent": {key: _percent(value, 2) for key, value in readout["rates"].items()},
            "device_share_of_visitors": {key: round(float(value), 4) for key, value in readout["device_share"].items()},
            "pooled_lift_percent": _percent(readout["pooled_lift"], 2),
            "device_lift_percent": {key: _percent(value, 2) for key, value in readout["device_lift"].items()},
            "device_weighted_lift_percent": _percent(readout["weighted_lift"], 2),
            "sample_ratio_chi_square": {key: round(float(value), 2) for key, value in readout["chi_square"].items()},
            "billing_tickets_per_1000_visitors": {key: round(float(value), 3)
                                                  for key, value in readout["tickets_per_1000"].items()},
            "guardrail_increase_percent": _percent(readout["guardrail_increase"], 2),
        }

    return {
        "answers": {f"A{index}": value for index, value in enumerate(answers, 1)},
        "analysis_window_days_8_to_28": summary(window),
        "burn_in_week_days_1_to_7": summary(burn_in),
        "all_28_days_not_the_plans_reading": {**summary(whole), "decision_rule_it_would_give": ab_decision(whole)},
        "analysis_window_with_the_qa_visits_not_the_plans_reading": {
            **summary(with_qa), "decision_rule_it_would_give": ab_decision(with_qa)},
        "decision": {"rule": decision, "outcome": AB_DECISIONS[decision]},
        "interpretation": (
            "The plan reads every metric, check and decision rule over the analysis window (days 8-28), every "
            "source summed except the QA visits (source internal). The all-28-days and with-QA figures are what "
            "those two misreadings give; they are not the plan's result."
        ),
    }


REFERENCES = {
    "test-plan-sizing": sizing_reference,
    "funnel-dropoff": funnel_reference,
    "ab-test-readout": ab_test_reference,
}
