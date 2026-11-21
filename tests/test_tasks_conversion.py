"""The conversion tasks: test-plan-sizing.

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
import importlib.util
import io
import json
import math
import re
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import pytest

from eval_runner import bench, task_facts_conversion, task_references

FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"
FOLDERS = {
    "test-plan-sizing": "test-plan-sizing",
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
    assert task["answers"]["single_number"] is True
    assert list(_targets(task)) == list(range(1, task["answers"]["count"] + 1))
    assert "Use a comma as the thousands separator" in task["prompt"]
    for label in range(1, task["answers"]["count"] + 1):
        assert re.search(rf"(?m)^A{label}: <[^>]+>$", task["prompt"]), label


@pytest.mark.parametrize("task_id", sorted(FOLDERS))
def test_the_targets_are_the_oracles_and_reach_the_judge(task_id):
    task = _task(task_id)
    reference = task_facts_conversion.REFERENCES[task_id](_sources(task_id))
    assert _targets(task) == {int(label[1:]): value for label, value in reference["answers"].items()}
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

SIZING_REPLY = """\
Testing plan for the next calendar

Sizing (users per variant; weeks at the page's mean weekly users):
- T1 homepage hero: 53,148 per variant, 3.63 weeks, so 4 weeks
- T2 tasting notes: 21,858 per variant, 2.27 weeks, so 3 weeks
- T3 grind selector (+1.2 points, 5.0% to 6.2%): 5,753 per variant, 1 week
- T4 frequency picker: 25,708 per variant; the subscribe page has 11,305 users a week (0.8 x 14,132 sessions), so 4.55 weeks, 5 weeks
- T5 comparison table: 10,307 per variant, 2 weeks
- T6 free-shipping bar: 27,614 per variant, 2 weeks

Calendar:
| Test | Page | Start | End |
|---|---|---|---|
| T3 | product page | week 1 | week 1 |
| T2 | product page | week 2 | week 4 |
| T5 | subscribe page | week 1 | week 2 |
| T6 | homepage | week 1 | week 2 |
| T1 | homepage | week 6 | week 9 |

Rejected: T4 needs 5 weeks, more than the four-week limit.

A1: 53,148
A2: 21,858
A3: 5,753
A4: 25,708
A5: 10,307
A6: 27,614
A7: 4
A8: 3
A9: 1
A10: 5
A11: 2
A12: 2
A13: 6
A14: 2
A15: 1
A16: 0
A17: 1
A18: 1
"""


def _sizing(points_as_relative: bool = False, sessions_as_users: bool = False,
            by_test_number: bool = False, ignore_freeze: bool = False) -> list[int]:
    """The 18 answers, recomputed from the fixtures; the flags are the careless readings."""
    tests = _table("test-plan-sizing/test_backlog.csv")
    weeks_of = collections.defaultdict(list)
    for row in _table("test-plan-sizing/traffic_by_page.csv"):
        weeks_of[row["page"]].append(row)
    users = {}
    for page, rows in weeks_of.items():
        mean = Decimal(sum(int(row["traffic"]) for row in rows)) / len(rows)
        users[page] = mean * Decimal("0.8") if rows[0]["unit"] == "sessions" and not sessions_as_users else mean
    sized = []
    for row in tests:
        p1 = Decimal(row["baseline_rate_pct"]) / 100
        lift = Decimal(row["expected_lift"]) / 100
        p2 = p1 + lift if row["lift_unit"] == "percentage points" and not points_as_relative else p1 * (1 + lift)
        n = int((Decimal("2.8") ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2).to_integral_value(ROUND_CEILING))
        weeks = int((2 * n / users[row["page"]]).to_integral_value(ROUND_CEILING))
        sized.append({"id": row["test_id"], "page": row["page"], "n": n, "weeks": weeks,
                      "priority": users[row["page"]] * (p2 - p1)})
    calendar = {test["id"]: 0 for test in sized}
    queue = [test for test in sized if test["weeks"] <= 4]
    queue.sort(key=lambda test: int(test["id"][1:]) if by_test_number else (-test["priority"], int(test["id"][1:])))
    occupied = collections.defaultdict(set)
    for test in queue:
        start = 1
        while start + test["weeks"] - 1 <= 10:
            span = set(range(start, start + test["weeks"]))
            if not span & occupied[test["page"]] and (ignore_freeze or 5 not in span):
                occupied[test["page"]] |= span
                calendar[test["id"]] = start
                break
            start += 1
    return [test["n"] for test in sized] + [test["weeks"] for test in sized] + [calendar[test["id"]] for test in sized]


def test_sizing_targets_are_recomputed_from_the_fixtures():
    answers = _sizing()
    assert list(_targets(_task("test-plan-sizing")).values()) == answers
    assert answers == [53148, 21858, 5753, 25708, 10307, 27614, 4, 3, 1, 5, 2, 2, 6, 2, 1, 0, 1, 1]


def test_sizing_data_holds_the_traps_it_was_built_with():
    tests = {row["test_id"]: row for row in _table("test-plan-sizing/test_backlog.csv")}
    traffic = collections.defaultdict(list)
    for row in _table("test-plan-sizing/traffic_by_page.csv"):
        traffic[row["page"]].append(int(row["traffic"]))
    mean = {page: sum(values) / len(values) for page, values in traffic.items()}
    # One lift is in points and the rest relative; one page is measured in sessions.
    assert [row["test_id"] for row in tests.values() if row["lift_unit"] == "percentage points"] == ["T3"]
    assert {row["unit"] for row in _table("test-plan-sizing/traffic_by_page.csv") if row["page"] == "subscribe page"} == {"sessions"}
    assert {row["page"] for row in _table("test-plan-sizing/traffic_by_page.csv") if row["unit"] == "sessions"} == {"subscribe page"}
    # T4 needs five weeks on users and would fit in four on sessions.
    assert 4 < 2 * 25708 / (0.8 * mean["subscribe page"]) <= 5
    assert 3 < 2 * 25708 / mean["subscribe page"] <= 4
    # T1 needs exactly the four weeks the limit allows; T2 needs rounding up, not to the nearest week.
    assert 3.5 < 2 * 53148 / mean["homepage"] <= 4
    assert 2 < 2 * 21858 / mean["product page"] < 2.5
    # On each shared page the test with the higher number has the higher priority.
    assert mean["homepage"] * 0.0042 > mean["homepage"] * 0.003
    assert mean["product page"] * 0.012 > mean["product page"] * 0.006


def test_the_sizing_reference_reply_passes_and_a_blank_earns_nothing():
    assert not _failed(_results("test-plan-sizing", SIZING_REPLY))
    assert _zeroed(_results("test-plan-sizing", "")) == set(_results("test-plan-sizing", ""))
    reference = task_facts_conversion.sizing_reference(_sources("test-plan-sizing"))
    rejected = [test["test_id"] for test in reference["tests"] if test["start_week"] == 0]
    assert rejected == ["T4"]
    assert reference["tests"][0]["end_week"] == 9


def test_the_tempting_readings_score_zero_on_the_checks_they_touch():
    right = _sizing()

    def zeroed(answers):
        results = _results("test-plan-sizing", _block([f"{value:,}" for value in answers]))
        assert _failed(results) == _zeroed(results)               # no partial credit anywhere
        return _zeroed(results)

    # The lift of T3 read as 1.2% relative: a sample no page can supply, so T3 is rejected
    # and T2 takes week 1.
    points = _sizing(points_as_relative=True)
    assert points[2] > 100 * right[2] and points[14] == 0 and points[13] == 1
    assert zeroed(points) == {"points_lift_test", "start_t2", "start_t3"}
    # The subscribe page's sessions used as users: T4 seems to fit in four weeks and is
    # given weeks 6-9.
    sessions = _sizing(sessions_as_users=True)
    assert sessions[9] == 4 and sessions[15] == 6
    assert zeroed(sessions) == {"sessions_page_weeks", "start_t4"}
    # Both at once, as a careless plan makes them.
    assert zeroed(_sizing(points_as_relative=True, sessions_as_users=True)) == {
        "points_lift_test", "sessions_page_weeks", "start_t2", "start_t3", "start_t4"}
    # The backlog's order instead of the priority rule, and a calendar that runs through the freeze.
    assert zeroed(_sizing(by_test_number=True)) == {"start_t1", "start_t2", "start_t3", "start_t6"}
    assert zeroed(_sizing(ignore_freeze=True)) == {"start_t1"}
    # Weeks rounded to the nearest week, not up.
    product = [int(row["traffic"]) for row in _table("test-plan-sizing/traffic_by_page.csv") if row["page"] == "product page"]
    nearest = right[:7] + [round(2 * right[1] / (sum(product) / len(product)))] + right[8:]
    assert nearest[7] == 2 and zeroed(nearest) == {"weeks_rounded_up"}
    # A rule-of-thumb sample size (16 p(1-p) / d^2 at the mean of p1 and p2) is an estimate,
    # not the formula: every one lands outside the band.
    thumb = list(right)
    for index, row in enumerate(_table("test-plan-sizing/test_backlog.csv")):
        if row["lift_unit"] == "relative %":
            p1 = float(row["baseline_rate_pct"]) / 100
            p2 = p1 * (1 + float(row["expected_lift"]) / 100)
            mean = (p1 + p2) / 2
            thumb[index] = math.ceil(16 * mean * (1 - mean) / (p2 - p1) ** 2)
            assert thumb[index] / right[index] > 1.015, row["test_id"]
    assert zeroed(thumb) == {"sample_sizes"}


def test_the_sizing_rules_state_what_the_oracle_applies():
    rules = (FIXTURES / "test-plan-sizing/testing_rules.md").read_text()
    for phrase in (
        "n = (1.96 + 0.84)² × (p1 × (1 − p1) + p2 × (1 − p2)) ÷ (p2 − p1)², rounded up to the next whole user",
        "p2 = p1 × (1 + `expected_lift` ÷ 100)", "p2 = p1 + `expected_lift` ÷ 100",
        "mean of its 8 weeks", "its weekly users are 0.8 × the mean of its weekly sessions",
        "Weeks needed = 2 × n ÷ the page's weekly users, rounded up to a whole week",
        "more than 4 weeks is rejected", "One test at a time on each page", "no test may be running in week 5",
        "must end by week 10", "weekly users × (p2 − p1)", "a tie goes to the lower test number",
    ):
        assert phrase in rules, phrase
    assert (task_facts_conversion.SIZING_MAX_WEEKS, task_facts_conversion.SIZING_FREEZE_WEEK,
            task_facts_conversion.SIZING_CALENDAR_WEEKS) == (4, 5, 10)


def test_the_sizing_prompt_asks_for_the_work_without_pointing_at_the_traps():
    prompt = _task("test-plan-sizing")["prompt"]
    for hint in ("point", "session", "relative", "freeze", "round"):
        assert hint not in prompt.lower(), hint
    assert "Follow the rules exactly" in prompt
    assert "the rule that rejects it" in prompt                     # rejections_explained
    assert "its page, its start week and its end week" in prompt     # calendar_presented
