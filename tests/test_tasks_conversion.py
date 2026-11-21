"""The conversion tasks: test-plan-sizing, funnel-dropoff and ab-test-readout (version 4).

What is pinned here, for every task:

- the committed fixtures are byte for byte what the task's generator
  (`eval_runner/fixtures/<folder>/generate.py`) writes;
- every banded target in the task file equals the figure the oracle
  (`eval_runner/task_facts_conversion.py`) computes, and the figure this file
  recomputes from the committed fixtures with code of its own;
- a reference reply written out by hand passes every program check, and a
  blank reply earns nothing;
- the reply the task is built to catch (the tempting wrong reading) scores
  zero on each check it touches, and only there;
- the rules the candidate reads state the numbers the oracle applies, and the
  prompt asks for the work without pointing at the traps.
"""
import collections
import csv
import datetime as dt
import importlib.util
import io
import json
import math
import re
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from eval_runner import bench, task_facts_conversion, task_references

FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"
FOLDERS = {
    "test-plan-sizing": "test-plan-sizing",
    "funnel-dropoff": "funnel-dropoff",
    "ab-test-readout": "ab-test",
}


def _generator(folder: str):
    path = FIXTURES / folder / "generate.py"
    spec = importlib.util.spec_from_file_location(f"generate_{folder.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _task(task_id: str) -> dict:
    return bench.load_tasks()[task_id]


def _table(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((FIXTURES / name).read_text())))


def _sources(task_id: str) -> dict[str, str]:
    return {Path(path).name: (bench.REPO_ROOT / path).read_text() for path in _task(task_id)["fixtures"]}


def _by_id(task: dict) -> dict[str, dict]:
    return {c["id"]: c for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section]}


def _targets(task: dict) -> dict[int, float]:
    """Answer number -> the target its banded condition carries, over every criterion."""
    targets = {}
    for criterion in _by_id(task).values():
        conditions = criterion.get("programmatic") or []
        for condition in conditions if isinstance(conditions, list) else [conditions]:
            if condition["fact"].startswith("answer_q") and "near" in condition:
                index = int(condition["fact"][len("answer_q"):])
                assert index not in targets, (task["id"], index)
                targets[index] = condition["near"]
    return dict(sorted(targets.items()))


def _results(task_id: str, response: str) -> dict:
    task = _task(task_id)
    return bench.programmatic_results(task, bench.measured_facts(task, response))


def _block(values: list) -> str:
    return "Plan.\n\n" + "\n".join(f"A{index}: {value}" for index, value in enumerate(values, 1)) + "\n"


def _failed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if not result["pass"]}


def _zeroed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if result["score"] == 0}


# ------------------------------------------------------------------ every task

@pytest.mark.parametrize("task_id", sorted(FOLDERS))
def test_the_fixtures_on_disk_are_what_the_generator_writes(task_id):
    folder = FIXTURES / FOLDERS[task_id]
    built = _generator(FOLDERS[task_id]).build()
    assert built == {name: (folder / name).read_text() for name in built}
    assert built == _generator(FOLDERS[task_id]).build()            # deterministic
    # Every supplied source is generated, and nothing else in the folder is supplied.
    supplied = {Path(path).name for path in _task(task_id)["fixtures"]}
    assert supplied == set(built)
    assert {path.name for path in folder.iterdir() if path.name != "__pycache__"} == supplied | {"generate.py"}
    assert sum(len(text.encode()) for text in built.values()) < 60_000


@pytest.mark.parametrize("task_id", sorted(FOLDERS))
def test_the_task_is_shaped_as_the_board_needs(task_id):
    task = _task(task_id)
    criteria = _by_id(task)
    programmatic = [c for c in criteria.values() if c.get("programmatic")]
    assert task["split"] == "development"
    assert 10 <= len(criteria) <= 18
    assert len(programmatic) / len(criteria) >= 0.7
    assert bench.free_credit_scores(task) == {}                     # nothing is already true of an empty reply
    sources = sum(len((bench.REPO_ROOT / path).read_bytes()) for path in task["fixtures"])
    assert 30_000 <= sources <= 60_000, sources
    if "answers" not in task:                                         # a file in the reply, checked row by row
        assert task_id == "test-plan-sizing"
        return
    assert task["answers"]["single_number"] is True
    assert list(_targets(task)) == list(range(1, task["answers"]["count"] + 1))
    assert "Use a comma as the thousands separator" in task["prompt"]
    for label in range(1, task["answers"]["count"] + 1):
        assert re.search(rf"(?m)^A{label}: <[^>]+>$", task["prompt"]), label


@pytest.mark.parametrize("task_id", sorted(FOLDERS))
def test_the_targets_are_the_oracles_and_reach_the_judge(task_id):
    task = _task(task_id)
    reference = task_facts_conversion.REFERENCES[task_id](_sources(task_id))
    assert _targets(task) == {int(label[1:]): value for label, value in reference.get("answers", {}).items()}
    for include_skills in (True, False):
        judged = bench.judge_source_reference(task, bench.assemble_prompt(task, include_skills))
        assert judged == {"version": task_references.VERSION, **json.loads(json.dumps(reference))}


@pytest.mark.parametrize("text", [
    "", "\x00", "A1: 1,,2\nA2: ٣\nA3: .\nA4: -\nA5: 1e9999", "A1:\nA2:\nA3:", "A1: " + "9" * 5000,
    "A" + "9" * 5000 + ": 5", "A1: −\nA2: –\nA3: -$", "\n" * 5000 + "A1: 7", "A1: 7\n" * 3000,
])
def test_no_odd_input_makes_a_check_raise(text):
    for task_id in FOLDERS:
        task = _task(task_id)
        bench.programmatic_results(task, bench.measured_facts(task, text))
        with pytest.warns(RuntimeWarning):
            assert bench.judge_source_reference(task, text) == {}


# ------------------------------------------------------------------ test-plan-sizing

def _sizing(points_as_relative: bool = False, sessions_as_users: bool = False, outages_in: bool = False,
            whole_traffic: bool = False, ignore_freeze: bool = False, ignore_limit: bool = False,
            by_test_number: bool = False, nearest_week: bool = False) -> dict[str, dict]:
    """Every test of the backlog recomputed from the fixtures; the flags are the careless readings."""
    rules = (FIXTURES / "test-plan-sizing/testing_rules.md").read_text()
    outage = re.search(r"leaving out every week whose `note` is `([^`]+)`", rules).group(1)
    sites = {row["site"]: row for row in _table("test-plan-sizing/sites.csv")}
    weeks_of = collections.defaultdict(list)
    for row in _table("test-plan-sizing/traffic_by_page.csv"):
        weeks_of[row["site"], row["page"]].append(row)
    users = {}
    for page, rows in weeks_of.items():
        kept = [int(row["traffic"]) for row in rows if outages_in or row["note"] != outage]
        mean = Decimal(sum(kept)) / len(kept)
        if rows[0]["unit"] == "sessions" and not sessions_as_users:
            mean *= Decimal(sites[page[0]]["users_per_session"])
        users[page] = mean
    tests = {}
    for row in _table("test-plan-sizing/test_backlog.csv"):
        p1 = Decimal(row["baseline_rate_pct"]) / 100
        lift = Decimal(row["expected_lift"]) / 100
        p2 = p1 + lift if row["lift_unit"] == "percentage points" and not points_as_relative else p1 * (1 + lift)
        n = int((Decimal("2.8") ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2).to_integral_value(ROUND_CEILING))
        share = Decimal(100 if whole_traffic else row["traffic_share_pct"]) / 100
        span = 2 * n / (users[row["site"], row["page"]] * share)
        weeks = int(span.to_integral_value()) if nearest_week else int(span.to_integral_value(ROUND_CEILING))
        tests[row["test_id"]] = {"site": row["site"], "page": row["page"], "users": users[row["site"], row["page"]],
                                 "n": n, "weeks": max(weeks, 1), "priority": users[row["site"], row["page"]] * share * (p2 - p1),
                                 "start": 0, "status": "too long"}
    queue = [test_id for test_id, test in tests.items() if test["weeks"] <= 4]
    queue.sort(key=lambda test_id: int(test_id[1:]) if by_test_number else (-tests[test_id]["priority"], int(test_id[1:])))
    pages = collections.defaultdict(set)
    load = collections.defaultdict(collections.Counter)
    for test_id in queue:
        test = tests[test_id]
        site = sites[test["site"]]
        test["status"] = "no slot"
        for first in range(1, 13 - test["weeks"] + 1):
            span = set(range(first, first + test["weeks"]))
            if ((ignore_freeze or int(site["freeze_week"]) not in span) and not span & pages[test["site"], test["page"]]
                    and (ignore_limit or all(load[test["site"]][week] < int(site["max_tests_at_once"]) for week in span))):
                pages[test["site"], test["page"]] |= span
                load[test["site"]].update(span)
                test["start"], test["status"] = first, "run"
                break
    return tests


def _calendar(tests: dict[str, dict]) -> str:
    """A reply carrying the calendar file, users rounded to whole users as the prompt asks."""
    lines = ["test_id,page_weekly_users,sample_size_per_variant,weeks_needed,start_week,status"]
    for test_id, test in tests.items():
        users = int(test["users"].to_integral_value(rounding=ROUND_HALF_UP))
        lines.append(f"{test_id},{users},{test['n']},{test['weeks']},{test['start']},{test['status']}")
    statuses = collections.Counter(test["status"] for test in tests.values())
    return (f"Note for the growth lead: {statuses['run']} tests run, {statuses['too long']} are too long (make them "
            f"smaller or drop them) and {statuses['no slot']} have no slot (they wait for the next calendar).\n\n"
            "### test_calendar.csv\n```csv\n" + "\n".join(lines) + "\n```\n")


def test_sizing_plan_is_recomputed_from_the_fixtures():
    plan = {test["test_id"]: test for test in task_facts_conversion.sizing_plan(_sources("test-plan-sizing"))}
    again = _sizing()
    assert list(plan) == list(again) and len(plan) == 150
    for test_id, test in again.items():
        mine = plan[test_id]
        assert (mine["n"], mine["weeks"], mine["start"], mine["status"]) == (
            test["n"], test["weeks"], test["start"], test["status"]), test_id
        assert abs(Decimal(mine["page_weekly_users"].numerator) / mine["page_weekly_users"].denominator - test["users"]) < Decimal("1e-9")
    assert collections.Counter(test["status"] for test in again.values()) == {"run": 101, "too long": 33, "no slot": 16}
    assert collections.Counter(test["category"] for test in plan.values()) == {
        "plain": 42, "sessions site": 40, "points lift": 26, "part traffic": 22, "outage page": 20}


def test_the_sizing_counts_the_rubric_quotes_are_the_data():
    plan = task_facts_conversion.sizing_plan(_sources("test-plan-sizing"))
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(_task("test-plan-sizing")).items()}
    kinds = collections.Counter(test["category"] for test in plan)
    assert f"the backlog's {len(plan)} tests" in wording["calendar_rows"]
    for criterion_id, kind in (("sized_plain", "plain"), ("sized_sessions_sites", "sessions site"),
                               ("sized_outage_pages", "outage page"), ("sized_points_lifts", "points lift"),
                               ("sized_part_traffic", "part traffic")):
        assert f"Each of the {kinds[kind]} tests" in wording[criterion_id], criterion_id
    # Each test carries one kind of trap at most, so a trap is charged to one count.
    assert all(test["traps"] <= 1 for test in plan)


def test_the_sizing_reference_reply_passes_and_a_blank_earns_nothing():
    reply = _calendar(_sizing())
    assert not _failed(_results("test-plan-sizing", reply))
    facts = bench.measured_facts(_task("test-plan-sizing"), reply)
    assert (facts["sizing_file_run_count"], facts["sizing_file_too_long_count"], facts["sizing_file_no_slot_count"]) == (
        101, 33, 16)
    blank = _results("test-plan-sizing", "")
    assert _zeroed(blank) == set(blank)
    # The file as a Markdown table, and with thousands separators in quoted cells, reads the same.
    table = reply.replace("```csv\n", "").replace("```\n", "")
    table = "\n".join(("| " + " | ".join(line.split(",")) + " |") if line[:1] == "T" or line.startswith("test_id")
                      else line for line in table.splitlines())
    assert not _failed(_results("test-plan-sizing", table))


def test_the_sizing_traps_score_zero_on_the_checks_they_touch():
    def zeroed(**careless):
        results = _results("test-plan-sizing", _calendar(_sizing(**careless)))
        assert _failed(results) == _zeroed(results), careless          # no partial credit anywhere
        return _zeroed(results)

    cascade = {"status_every_test", "start_every_test"}
    assert zeroed(points_as_relative=True) == {"sized_points_lifts"} | cascade
    assert zeroed(sessions_as_users=True) == {"sized_sessions_sites"} | cascade
    assert zeroed(outages_in=True) == {"sized_outage_pages"} | cascade
    assert zeroed(whole_traffic=True) == {"sized_part_traffic"} | cascade
    # The calendar's own rules: the freeze weeks, the limit on tests at once, the priority order.
    assert zeroed(ignore_freeze=True) == cascade
    assert zeroed(ignore_limit=True) == cascade
    assert zeroed(by_test_number=True) == cascade
    # Weeks rounded to the nearest week instead of up: wrong in every kind of test, at least 5 of each.
    assert zeroed(nearest_week=True) == {"sized_plain", "sized_sessions_sites", "sized_outage_pages",
                                         "sized_points_lifts", "sized_part_traffic"} | cascade


def test_one_wrong_row_costs_its_own_count_and_the_strict_ones():
    tests = _sizing()
    plain = next(test_id for test_id, test in task_facts_conversion_plan_by_id().items() if test["category"] == "plain")
    tests[plain]["n"] += 500
    results = _results("test-plan-sizing", _calendar(tests))
    assert _failed(results) == {"sized_plain"} and results["sized_plain"]["score"] == pytest.approx(0.8)
    tests = _sizing()
    tests[plain]["start"] += 1
    assert _failed(_results("test-plan-sizing", _calendar(tests))) == {"start_every_test"}


def task_facts_conversion_plan_by_id() -> dict[str, dict]:
    return {test["test_id"]: test for test in task_facts_conversion.sizing_plan(_sources("test-plan-sizing"))}


def test_the_sizing_rules_state_what_the_oracle_applies():
    rules = (FIXTURES / "test-plan-sizing/testing_rules.md").read_text()
    for phrase in (
        "n = (1.96 + 0.84)² × (p1 × (1 − p1) + p2 × (1 − p2)) ÷ (p2 − p1)², rounded up to the next whole user",
        "p2 = p1 × (1 + `expected_lift` ÷ 100)", "p2 = p1 + `expected_lift` ÷ 100",
        "leaving out every week whose `note` is `tracking outage`",
        "its pages' weekly users are that figure × the mean of their weekly sessions",
        "Weeks needed = 2 × n ÷ (the page's weekly users × `traffic_share_pct` ÷ 100), rounded up to a whole week",
        "more than 4 weeks is rejected as too long", "One test at a time on each page of a site",
        "at most its `max_tests_at_once` tests in any one week", "No test may be running in its site's `freeze_week`",
        "must end by week 12", "weekly users × `traffic_share_pct` ÷ 100 × (p2 − p1)",
        "a tie goes to the lower test number", "from every site at once, in priority order",
    ):
        assert phrase in rules, phrase
    sites = _table("test-plan-sizing/sites.csv")
    assert {row["site"] for row in sites if row["unit"] == "sessions"} == {"de", "au", "fr"}
    assert {row["unit"] for row in _table("test-plan-sizing/traffic_by_page.csv") if row["site"] in ("de", "au", "fr")} == {"sessions"}
    assert sum(row["note"] == "tracking outage" for row in _table("test-plan-sizing/traffic_by_page.csv")) == 11


def test_the_sizing_prompt_asks_for_the_work_without_pointing_at_the_traps():
    prompt = _task("test-plan-sizing")["prompt"]
    for hint in ("point", "session", "outage", "freeze", "half", "share", "round up", "at once"):
        assert hint not in prompt.lower(), hint
    assert "Follow the rules exactly" in prompt
    assert "test_id,page_weekly_users,sample_size_per_variant,weeks_needed,start_week,status" in prompt
    assert "what the team should do about each kind of rejection" in prompt     # summary_for_the_lead


# -------------------------------------------------------------------- funnel-dropoff

FUNNEL_REPLY = """\
Diagnosis: checkout conversion, March 2026

What broke: the order step (payment to order) on mobile Safari, from 16 March, the day release
5.8.0 shipped the new payment form. Mobile Safari's payment-to-order rate was 70.0% before the
break and 41.0% after it; its normal range is about 65% to 75%, and it has been below that range
every day since 16 March. Every other segment and step stayed inside its range, apart from desktop
Chrome's order step on 24 March and desktop Edge's payment step on 20-23 March, which both recovered.

Data handling: the crawler's rows are left out; the order rows of 10-12 March and the Safari
payment rows of 27-29 March are halved, as the release log records both double-firings.

Conversion (orders / cart sessions, every segment): 33.22% before the break, 29.54% after it.

Orders lost: 3,795 mobile Safari payment sessions after the break x 70.00% = 2,656.6 expected
orders, against 1,556 recorded: 1,101 orders, or $79,272 at $72.00 each.

Suspected causes:
- C1 autocomplete: ruled out; no shipping step broke on 10 March.
- C2 CDN: ruled out; the break began on 16 March, not 14 March.
- C3 payment form on iPhone Safari: consistent; this is the break.
- C4 payment form on iPad Safari: ruled out; tablet Safari dipped but stayed inside its range.
- C5 sale email: ruled out; no shipping step broke on 21 March.
- C6 hotfix on desktop Chrome: ruled out; one day below the range, then back inside it.
- C7 Edge 136: ruled out; four days below the range, then back inside it.
- C8 analytics SDK on Safari: ruled out; with the doubled payment rows halved, nothing broke.
- C9 express wallets on Android: ruled out; small dips inside the range.
- C10 shipping rates and Firefox: ruled out; no Firefox shipping step broke.

First: switch the new payment form off for mobile Safari (or roll 5.8.0 back there).

A1: 33.22%
A2: 29.54%
A3: 16
A4: 70.0%
A5: 41.0%
A6: 1,101
A7: $79,272
A8: 1
A9: 1
A10: 0
A11: 1
A12: 1
A13: 1
A14: 1
A15: 1
A16: 1
A17: 1
"""


def _funnel(halve_orders: bool = True, halve_payments: bool = True, bots: bool = False,
            baseline: str = "before") -> dict:
    """The diagnosis recomputed from the fixtures; the flags are the careless readings."""
    rules = (FIXTURES / "funnel-dropoff/analysis_rules.md").read_text()
    log = (FIXTURES / "funnel-dropoff/release_log.md").read_text()

    def span(match) -> set[str]:
        first, last = (dt.date.fromisoformat(match.group(index)) for index in (1, 2))
        return {(first + dt.timedelta(days=offset)).isoformat() for offset in range((last - first).days + 1)}

    orders_twice = span(re.search(r"From (\S+) to (\S+) the order-confirmation tag fired twice for every order, on every browser", log))
    payments = re.search(r"From (\S+) to (\S+) the event fired twice on (\w+)\.", log)
    assert "the payment-step event fires twice" in log
    payments_twice, payment_browser = span(payments), payments.group(3)
    crawler = re.search(r"rows whose browser is `([^`]+)`", rules).group(1)
    data = collections.defaultdict(lambda: collections.defaultdict(dict))
    carts_by_day = collections.Counter()
    orders_by_day = collections.Counter()
    for row in _table("funnel-dropoff/funnel_daily.csv"):
        count = int(row["count"])
        if halve_orders and row["step"] == "order" and row["date"] in orders_twice:
            count //= 2
        if (halve_payments and row["step"] == "payment" and row["browser"] == payment_browser
                and row["date"] in payments_twice):
            count //= 2
        if row["browser"] == crawler and not bots:
            continue
        if row["step"] == "cart":
            carts_by_day[row["date"]] += count
        if row["step"] == "order":
            orders_by_day[row["date"]] += count
        if row["browser"] != crawler:
            data[row["device"] + " / " + row["browser"]][row["date"]][row["step"]] = count
    days = sorted(carts_by_day)
    week = days[:7]
    steps = ["cart", "shipping", "payment", "order"]

    def rate(segment, period, step, start=None):
        start = start or steps[steps.index(step) - 1]
        return (Decimal(sum(data[segment][day][step] for day in period))
                / Decimal(sum(data[segment][day][start] for day in period)))

    breaks, dips = [], []
    for segment in data:
        for step in steps[1:]:
            low = rate(segment, week, step) - Decimal("0.05")
            under = [day for day in days if rate(segment, [day], step) < low]
            if under:
                dips.append((segment, step))
            # The break begins on the first day from which every day is under the range.
            begins = next((day for day in days if all(later in under for later in days if later >= day)), None)
            if begins:
                breaks.append((segment, step, begins))
    segment, step, begins = min(breaks, key=lambda item: item[2])
    before = [day for day in days if day < begins]
    after = [day for day in days if day >= begins]
    previous = steps[steps.index(step) - 1]
    to_order = rate(segment, before if baseline == "before" else week, "order", start=previous)
    lost = int((sum(data[segment][day][previous] for day in after) * to_order
                - sum(data[segment][day]["order"] for day in after)).to_integral_value())
    causes = {}
    for line in (FIXTURES / "funnel-dropoff/suspected_causes.md").read_text().splitlines():
        match = re.match(r"\| (C\d+) \| [^|]+ \| (\S+) \| ([^|]+) \| (\w+) \|$", line)
        if match:
            named = list(data) if match.group(3).strip() == "every segment" else [
                item.strip() for item in match.group(3).split(",")]
            causes[match.group(1)] = 0 if any(
                (name, match.group(4), match.group(2)) in breaks for name in named) else 1
    return {
        "answers": [
            round(100 * sum(orders_by_day[day] for day in before) / sum(carts_by_day[day] for day in before), 2),
            round(100 * sum(orders_by_day[day] for day in after) / sum(carts_by_day[day] for day in after), 2),
            int(begins[-2:]),
            round(float(rate(segment, before, step)) * 100, 1),
            round(float(rate(segment, after, step)) * 100, 1),
            lost, lost * 72.0,
        ] + [causes[f"C{index}"] for index in range(1, 11)],
        "break": (segment, step, begins), "breaks": breaks, "dips": dips,
    }


def test_funnel_targets_are_recomputed_from_the_fixtures():
    funnel = _funnel()
    assert list(_targets(_task("funnel-dropoff")).values()) == funnel["answers"]
    assert funnel["answers"] == [33.22, 29.54, 16, 70.0, 41.0, 1101, 79272.0, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1]
    assert funnel["breaks"] == [("mobile / Safari", "order", "2026-03-16")]


def test_funnel_data_holds_the_traps_it_was_built_with():
    funnel = _funnel()
    rows = _table("funnel-dropoff/funnel_daily.csv")
    # Two steps fell below their range for a while and came back; every other dip stayed inside.
    assert sorted(funnel["dips"]) == [("desktop / Chrome", "order"), ("desktop / Edge", "payment"),
                                      ("mobile / Safari", "order")]
    reference = task_facts_conversion.funnel_reference(_sources("funnel-dropoff"))
    assert reference["days_below_normal_range"]["desktop / Chrome order"] == ["2026-03-24"]
    assert reference["days_below_normal_range"]["desktop / Edge payment"] == [
        "2026-03-20", "2026-03-21", "2026-03-22", "2026-03-23"]
    # Tablet Safari's order step fell after the release, by less than its range allows.
    tablet = reference["step_rates_before_and_after_percent"]["tablet / Safari"]["order"]
    assert tablet[0] - tablet[1] > 2
    # Left doubled, the Safari payment rows make desktop and tablet Safari seem to break from 27 March.
    assert sorted(_funnel(halve_payments=False)["breaks"]) == [
        ("desktop / Safari", "order", "2026-03-27"), ("mobile / Safari", "order", "2026-03-16"),
        ("tablet / Safari", "order", "2026-03-27")]
    # The crawler adds carts and nothing else, only after the break; every doubled row is even.
    crawler = [row for row in rows if row["browser"] == "HeadlessChrome"]
    assert {row["step"] for row in crawler} == {"cart"} and min(row["date"] for row in crawler) == "2026-03-19"
    assert all(int(row["count"]) % 2 == 0 for row in rows if task_facts_conversion.funnel_double_fired(row))
    assert len(rows) > 1000 and len({(row["device"], row["browser"]) for row in rows}) == 11


def test_the_funnel_reference_reply_passes_and_a_blank_earns_nothing():
    assert not _failed(_results("funnel-dropoff", FUNNEL_REPLY))
    assert _zeroed(_results("funnel-dropoff", "")) == set(_results("funnel-dropoff", ""))


def test_the_funnel_traps_score_zero_on_the_checks_they_touch():
    right = _funnel()["answers"]

    def zeroed(answers):
        results = _results("funnel-dropoff", _block([f"{value:,}" for value in answers]))
        assert _failed(results) == _zeroed(results)               # no partial credit anywhere
        return _zeroed(results)

    # Neither double-firing halved: the period before the break, the broken step's rate before and
    # after it, the loss built on them, and a cause the doubled Safari rows seem to confirm.
    doubled = _funnel(halve_orders=False, halve_payments=False)["answers"]
    assert doubled[0] - right[0] > 5 and doubled[3] - right[3] > 10
    assert zeroed(doubled) == {"q1_rate_before", "q4_step_rate_before", "q5_step_rate_after", "loss_size",
                               "cause_c8"}
    # The order rows halved and the Safari payment rows not: the second double-firing alone.
    assert zeroed(_funnel(halve_payments=False)["answers"]) == {"q5_step_rate_after", "loss_size", "cause_c8"}
    # The crawler's carts left in: only the period after the break.
    assert zeroed(_funnel(bots=True)["answers"]) == {"q2_rate_after"}
    # The loss counted from the reference week's rate instead of the rate before the break.
    assert zeroed(_funnel(baseline="reference week")["answers"]) == {"loss_size"}
    # The look-alikes taken for causes: a change two days before the break (C2), a dip inside the
    # range (C4), a day below the range that recovered (C6) and four days that did (C7).
    for label, criterion in ((9, "cause_c2"), (11, "cause_c4"), (13, "cause_c6"), (14, "cause_c7")):
        wrong = list(right)
        wrong[label - 1] = 0
        assert zeroed(wrong) == {criterion}


def test_the_funnel_rules_state_what_the_oracle_applies():
    rules = (FIXTURES / "funnel-dropoff/analysis_rules.md").read_text()
    log = (FIXTURES / "funnel-dropoff/release_log.md").read_text()
    for phrase in (
        "On those days that step's rows, for those browsers, count two events per session. Halve them",
        "rows whose browser is `HeadlessChrome` come from a price-monitoring crawler. Leave them out of every figure",
        "Conversion rate = orders ÷ cart sessions, over every segment",
        "The reference week is 2026-03-02 to 2026-03-08",
        "plus or minus 5 percentage points",
        "below its normal range on day D and on every later day in the export",
        "Revenue lost = orders lost × $72.00",
        "only when one of those segments has that step break, beginning on that date",
    ):
        assert phrase in rules, phrase
    assert "From 2026-03-10 to 2026-03-12 the order-confirmation tag fired twice for every order, on every browser" in log
    assert "From 2026-03-27 to 2026-03-29 the event fired twice on Safari." in log
    assert "| 2026-03-16 | 5.8.0: new payment form" in log
    assert task_facts_conversion.FUNNEL_DOUBLE_FIRED == (
        ("order", None, ("2026-03-10", "2026-03-11", "2026-03-12")),
        ("payment", "Safari", ("2026-03-27", "2026-03-28", "2026-03-29")))
    # The judged action names the segment and the release the data points at.
    action = _by_id(_task("funnel-dropoff"))["first_action_on_the_cause"]["check"]
    assert "release 5.8.0's payment form on mobile Safari" in action
    assert task_facts_conversion.funnel_reference(_sources("funnel-dropoff"))["break"] == {
        "segment": "mobile / Safari", "step": "order", "first_day": "2026-03-16"}


def test_the_funnel_prompt_asks_for_the_work_without_pointing_at_the_traps():
    prompt = _task("funnel-dropoff")["prompt"]
    for hint in ("headless", "crawler", "bot", "double", "safari", "tablet", "16 march", "5.8", "range", "edge"):
        assert hint not in prompt.lower(), hint
    assert "for each suspected cause, whether the data rules it out and why" in prompt
    assert "what to do first" in prompt                              # first_action_on_the_cause


# ------------------------------------------------------------------- ab-test-readout

AB_REPLY = """\
Readout: pricing-page test, variant B (annual pricing first)

Recommendation: do not ship variant B. The plan's rule 3 decides: the billing-ticket guardrail is
breached.

Analysis window (days 8-28; the burn-in week and the QA visits are left out as the plan says):
- Visitors: control 16,996, variant B 10,716; both clear the 10,000 minimum.
- The split holds: desktop chi-square 0.0 against 50/50, mobile 0.3 against the planned 70/30.
  The burn-in week did not hold it (a cache problem in days 1-3), which is why it is left out.
- Signup rate: desktop 8.12% control, 7.98% B (-1.7%); mobile 4.03% control, 3.75% B (-6.9%).
  Device-weighted lift: -3.8%. Variant B is lower on both devices.
- The dashboard's pooled +11.7% is not the result: B got a larger share of desktop visitors, who
  sign up about twice as often as mobile visitors, because mobile was split 70/30 by design.
- The first week's +15.7% (device-weighted, days 1-7) did not last.
- Guardrail: 3.83 billing tickets per 1,000 visitors on B against 3.00 on control, +27.5%, above
  the 20% limit.

Next step: keep control, and look at why annual-first pricing sends people to billing support
before any new version is tested.

A1: 16,996
A2: 10,716
A3: 11.7%
A4: -1.7%
A5: -6.9%
A6: -3.8%
A7: 15.7%
A8: 0.0
A9: 0.3
A10: 27.5%
A11: 3
"""


def _ab(days: range = range(8, 29), planned_mobile: Decimal = Decimal("0.7"), weighting: str = "plan",
        guardrail_days: range | None = None, qa: bool = False) -> list:
    """The 11 answers, recomputed from the fixture; the arguments are the careless readings."""
    plan = (FIXTURES / "ab-test/test_plan.md").read_text()
    split = re.search(r"Mobile visitors are split (\d+)/(\d+)", plan)
    assert Decimal(split.group(1)) / 100 == Decimal("0.7")
    internal = re.search(r"recorded with source `([^`]+)`", plan).group(1)
    rows = [row for row in _table("ab-test/experiment_results.csv") if qa or row["source"] != internal]

    def cells(period: range) -> dict:
        found = collections.defaultdict(collections.Counter)
        for row in rows:
            if int(row["day"]) in period:
                for field in ("visitors", "signups", "billing_tickets"):
                    found[row["variant"], row["device"]][field] += int(row[field])
                    found[row["variant"], "both"][field] += int(row[field])
        return found

    def lifts(period: range) -> dict:
        found = cells(period)
        rate = {key: Decimal(value["signups"]) / value["visitors"] for key, value in found.items()}
        visitors = {device: found["control", device]["visitors"] + found["variant_b", device]["visitors"]
                    for device in ("desktop", "mobile")}
        share = {device: Decimal(visitors[device]) / sum(visitors.values()) for device in visitors}
        device = {where: rate["variant_b", where] / rate["control", where] - 1 for where in ("desktop", "mobile")}
        if weighting == "plan":
            weighted = (sum(rate["variant_b", d] * share[d] for d in share)
                        / sum(rate["control", d] * share[d] for d in share) - 1)
        elif weighting == "pooled":
            weighted = rate["variant_b", "both"] / rate["control", "both"] - 1
        else:   # the visitor-weighted average of the two device lifts
            weighted = sum(device[d] * share[d] for d in share)
        return {"found": found, "pooled": rate["variant_b", "both"] / rate["control", "both"] - 1,
                "device": device, "weighted": weighted}

    window, burn_in = lifts(days), lifts(range(1, 8))
    found = window["found"]
    chi = {}
    for device, part in (("desktop", Decimal("0.5")), ("mobile", planned_mobile)):
        total = found["control", device]["visitors"] + found["variant_b", device]["visitors"]
        chi[device] = sum((Decimal(found[variant, device]["visitors"]) - total * share) ** 2 / (total * share)
                          for variant, share in (("control", part), ("variant_b", 1 - part)))
    tickets = cells(guardrail_days or days)
    per_1000 = {variant: Decimal(tickets[variant, "both"]["billing_tickets"]) * 1000 / tickets[variant, "both"]["visitors"]
                for variant in ("control", "variant_b")}
    guardrail = per_1000["variant_b"] / per_1000["control"] - 1
    visitors = [found["control", "both"]["visitors"], found["variant_b", "both"]["visitors"]]
    if min(visitors) < 10000:
        rule = 1
    elif max(chi.values()) > Decimal("3.841"):
        rule = 2
    elif guardrail > Decimal("0.2"):
        rule = 3
    elif window["weighted"] >= Decimal("0.03") and min(window["device"].values()) > 0:
        rule = 4
    else:
        rule = 5
    percent = lambda value: round(float(value) * 100, 1)  # noqa: E731
    return visitors + [percent(window["pooled"]), percent(window["device"]["desktop"]),
                       percent(window["device"]["mobile"]), percent(window["weighted"]),
                       percent(burn_in["weighted"]), round(float(chi["desktop"]), 1),
                       round(float(chi["mobile"]), 1), percent(guardrail), rule]


def test_ab_targets_are_recomputed_from_the_fixtures():
    answers = _ab()
    assert list(_targets(_task("ab-test-readout")).values()) == answers
    assert answers == [16996, 10716, 11.7, -1.7, -6.9, -3.8, 15.7, 0.0, 0.3, 27.5, 3]


def test_ab_data_holds_the_traps_it_was_built_with():
    reference = task_facts_conversion.ab_test_reference(_sources("ab-test-readout"))
    window = reference["analysis_window_days_8_to_28"]
    whole = reference["all_28_days_not_the_plans_reading"]
    # The reversal: pooled up, both devices down, from a mix the plan set.
    assert window["pooled_lift_percent"] > 10 and max(window["device_lift_percent"].values()) < -1
    rates = window["signup_rates_percent"]
    assert rates["control desktop"] > 1.9 * rates["control mobile"]
    # The first week's lift fades; over all 28 days the split fails and the guardrail does not.
    assert reference["burn_in_week_days_1_to_7"]["device_weighted_lift_percent"] > 10
    assert min(whole["sample_ratio_chi_square"].values()) > 3.841 > max(window["sample_ratio_chi_square"].values())
    assert whole["guardrail_increase_percent"] < 20 < window["guardrail_increase_percent"]
    assert whole["decision_rule_it_would_give"] == 2 and reference["decision"]["rule"] == 3
    # Against 50/50, mobile fails the check by far.
    assert _ab(planned_mobile=Decimal("0.5"))[8] > 1000


def test_the_ab_reference_reply_passes_and_a_blank_earns_nothing():
    assert not _failed(_results("ab-test-readout", AB_REPLY))
    assert _zeroed(_results("ab-test-readout", "")) == set(_results("ab-test-readout", ""))
    # Computed from rounded inputs (rates to two decimals, shares to two), the weighted lift is still exact enough.
    control = Decimal("8.12") * Decimal("0.43") + Decimal("4.03") * Decimal("0.57")
    variant = Decimal("7.98") * Decimal("0.43") + Decimal("3.75") * Decimal("0.57")
    assert abs(float(variant / control - 1) * 100 - (-3.8)) <= 0.15
    control = Decimal("8.07") * Decimal("0.43") + Decimal("3.97") * Decimal("0.57")    # the burn-in week
    variant = Decimal("9.66") * Decimal("0.43") + Decimal("4.35") * Decimal("0.57")
    assert abs(float(variant / control - 1) * 100 - 15.7) <= 0.15


def test_the_ab_traps_score_zero_on_the_checks_they_touch():
    right = _ab()

    def zeroed(answers):
        results = _results("ab-test-readout", _block([f"{value:,}" for value in answers]))
        assert _failed(results) == _zeroed(results)               # no partial credit anywhere
        return _zeroed(results)

    # The burn-in week read in: every window figure moves, and the 28-day split fails the check.
    whole = _ab(days=range(1, 29))
    assert whole[10] == 2
    assert zeroed(whole) == {"q1_control_visitors", "q2_variant_visitors", "q3_pooled_lift", "q4_desktop_lift",
                             "q5_mobile_lift", "q6_weighted_lift", "q8_desktop_srm", "q9_mobile_srm",
                             "q10_guardrail", "q11_decision_rule"}
    # The planned 70/30 mobile split taken for a sample-ratio mismatch.
    assert zeroed(_ab(planned_mobile=Decimal("0.5"))) == {"q9_mobile_srm", "q11_decision_rule"}
    # The dashboard's pooled lift, or an average of the device lifts, as the primary estimate.
    # Read that way in the burn-in week too, A7 is off as well.
    assert zeroed(_ab(weighting="pooled")) == {"q6_weighted_lift", "q7_burn_in_lift"}
    assert zeroed(_ab(weighting="average of lifts")) == {"q6_weighted_lift", "q7_burn_in_lift"}
    # The guardrail over all 28 days: not breached, so rule 5 (keep control) instead of rule 3.
    guardrail = _ab(guardrail_days=range(1, 29))
    assert guardrail[9] < 20 and guardrail[10] == 5
    assert zeroed(guardrail) == {"q10_guardrail", "q11_decision_rule"}
    # The QA visits counted in: variant B's visitors, every lift, the mobile split and the guardrail
    # move, and the split then fails the check.
    with_qa = _ab(qa=True)
    assert with_qa[10] == 2 and with_qa[1] > 1.1 * right[1]
    assert zeroed(with_qa) == {"q2_variant_visitors", "q3_pooled_lift", "q4_desktop_lift", "q5_mobile_lift",
                               "q6_weighted_lift", "q7_burn_in_lift", "q8_desktop_srm", "q9_mobile_srm",
                               "q10_guardrail", "q11_decision_rule"}
    # The burn-in week's lift with both devices pooled.
    reference = task_facts_conversion.ab_test_reference(_sources("ab-test-readout"))
    burn_in_pooled = round(reference["burn_in_week_days_1_to_7"]["pooled_lift_percent"], 1)
    assert zeroed(right[:6] + [burn_in_pooled] + right[7:]) == {"q7_burn_in_lift"}


def test_the_ab_plan_states_what_the_oracle_applies():
    plan = (FIXTURES / "ab-test/test_plan.md").read_text()
    for phrase in (
        "recorded with source `internal`", "are left out of every metric, check and decision rule below",
        "Desktop visitors are split 50/50", "Mobile visitors are split 70/30: 70% to control and 30% to variant B",
        "the burn-in week is left out of every metric, check and decision rule below",
        "The analysis window is days 8 to 28",
        "where a device's share counts the visitors of both variants",
        "Device-weighted lift = variant B's device-weighted rate ÷ control's − 1",
        "expected visitors = the device's visitors × the variant's planned share on that device",
        "when its chi-square is above 3.841", "more than 20% above control's",
        "1. Either variant has fewer than 10,000 visitors: keep the test running.",
        "2. The sample-ratio check fails on either device",
        "3. The guardrail is breached: do not ship variant B.",
        "4. The device-weighted lift is +3.0% or more and variant B's signup rate is higher than control's on both devices",
        "5. Otherwise: keep control.",
    ):
        assert phrase in plan, phrase
    # The judged checks name the split the plan set and the devices the data shows.
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(_task("ab-test-readout")).items()}
    assert "because mobile was split 70/30 by design" in wording["reversal_explained"]
    assert "lower than control's on desktop and on mobile" in wording["reversal_explained"]


def test_the_ab_prompt_asks_for_the_work_without_pointing_at_the_traps():
    prompt = _task("ab-test-readout")["prompt"]
    for hint in ("mix", "70/30", "cache", "simpson", "revers", "fade", "28 days", "breach", "qa visit", "office", "source `internal`"):
        assert hint not in prompt.lower(), hint
    assert "Follow the plan exactly" in prompt
    assert "which of the plan's decision rules decides and what it decides" in prompt   # recommendation_stated
    assert "with both devices pooled" in prompt                                         # what the manager saw


def test_the_parser_tests_keep_the_version_3_task_they_were_written_against():
    frozen = json.loads((bench.REPO_ROOT / "tests/data/ab-test-readout-v3.json").read_text())
    assert (frozen["id"], frozen["prompt_version"], frozen["rubric_version"]) == ("ab-test-readout", 3, 4)
    assert frozen["answers"] == {"count": 7, "single_number": True}
    task = _task("ab-test-readout")
    assert (task["prompt_version"], task["rubric_version"]) == (4, 5)
