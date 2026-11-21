"""The email tasks: the files on disk are what the module generates, every
figure a task file pins is recomputed here from those files by separate code,
the reference reply passes every program check, a blank reply earns nothing,
a reply built from each tempting wrong reading scores zero on the checks it
touches, and each single slip is counted where it went wrong."""
import csv
import io
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from eval_runner import bench
from eval_runner import task_facts_email as email

REPO_ROOT = Path(__file__).resolve().parents[1]


def _task(task_id: str) -> dict:
    return json.loads((REPO_ROOT / f"eval_runner/tasks/{task_id}.json").read_text())


def _by_id(task: dict) -> dict:
    return {c["id"]: c for section in task["rubric"].values() for c in section}


def _results(task: dict, text: str) -> dict:
    return bench.programmatic_results(task, bench.measured_facts(task, text))


def _swap(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"{old!r} appears {text.count(old)} times"
    return text.replace(old, new)


def test_the_files_on_disk_are_what_the_module_generates():
    assert email.drift() == []
    for name, text in email.fixtures().items():
        assert (REPO_ROOT / email.FIXTURE_DIR / name).read_text() == text, name
    # Generated again from nothing cached, the same bytes: nothing depends on
    # the clock or the machine.
    email.subscribers.cache_clear()
    email.calendar_reference.cache_clear()
    assert email.fixtures() == {name: (REPO_ROOT / email.FIXTURE_DIR / name).read_text() for name in email.fixtures()}
    assert email.main(["--check"]) == 0
    # Every fixture a task names is a file this module writes.
    for task_id in email.TASK_IDS:
        for fixture in _task(task_id)["fixtures"]:
            assert Path(fixture).relative_to(email.FIXTURE_DIR).as_posix() in email.fixtures(), fixture


def test_the_runner_measures_the_email_facts_for_these_tasks_only():
    tasks = bench.load_tasks()
    for task_id in email.TASK_IDS:
        facts = bench.measured_facts(tasks[task_id], "")
        assert set(email.facts_for(tasks[task_id], "")) <= set(facts)
        assert not tasks[task_id].get("workflow")
    assert email.facts_for(tasks["search-account-build"], "") == {}
    assert not any(name.startswith("calendar_") for name in bench.measured_facts(tasks["headline"], "x"))


# ══ email-send-calendar ═══════════════════════════════════════════════════════

CALENDAR = _task("email-send-calendar")
CALENDAR_DIR = REPO_ROOT / "eval_runner/fixtures/email-send-calendar"
CALENDAR_REFERENCE = email.calendar_reference_answer()
# What the policy states, written out again here: the cap, its window and the
# teaser gap. The test below checks the policy text says exactly these.
CAP, WINDOW, GAP = 3, 7, 3
CALENDAR_BANDS = {
    "every_campaign_once": (0, 1), "a1_moved": (0, 1), "a2_not_sent": (0, 1), "a3_emails_sent": (0, 20),
    "a4_most_emails": (0, 1), "a5_subscribers_at_most": (0, 3), "send_dates_right": (0, 2),
    "reasons_right": (0, 2), "audiences_right": (0, 2),
}


def _calendar_files():
    subscribers = list(csv.DictReader((CALENDAR_DIR / "subscribers.csv").open()))
    plan = list(csv.DictReader((CALENDAR_DIR / "campaigns.csv").open()))
    policy = (CALENDAR_DIR / "calendar_policy.md").read_text()
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    blackouts = {date(2027, 2, int(n)) for n in re.findall(r"^\s*- \w+day (\d+) February \(", policy, re.M)}
    send_days = {}
    for kind, text in re.findall(r"^\s*- `(\w+)`: (.+)$", policy, re.M):
        span = re.fullmatch(r"(\w+) to (\w+)", text)
        send_days[kind] = (set(range(names.index(span.group(1)), names.index(span.group(2)) + 1)) if span
                           else {names.index(word) for word in re.findall(r"\w+day", text)})
    return subscribers, plan, policy, blackouts, send_days


def build_calendar(order="priority", window="rolling", counting="subscriber", everyone=False, gap=GAP):
    """The policy's procedure, read from the files, with a switch for each
    tempting wrong reading: campaigns taken by date instead of priority; the
    cap counted per calendar week or only over the days before; the cap
    counted per segment instead of per subscriber; unsubscribed and bounced
    subscribers counted; and the teaser gap read as clear days between."""
    subscribers, plan, _policy, blackouts, send_days = _calendar_files()
    segments = {c["campaign_id"]: c["segments"].split(";") for c in plan}
    audience = {cid: [s["subscriber_id"] for s in subscribers
                      if (everyone or s["status"] == "active") and any(s[g] == "1" for g in segs)]
                for cid, segs in segments.items()}
    key = (lambda c: int(c["priority"])) if order == "priority" else (lambda c: (c["requested_date"], int(c["priority"])))
    placed, reasons, got, by_segment = {}, {}, {}, {}

    def full(dates, when):
        if window == "rolling":
            starts = [when - timedelta(days=k) for k in range(WINDOW)]
        elif window == "backward":
            starts = [when - timedelta(days=WINDOW - 1)]
        else:
            starts = [when - timedelta(days=when.weekday())]
        return any(sum(start <= sent <= start + timedelta(days=WINDOW - 1) for sent in dates) >= CAP for start in starts)

    def blocked(campaign, when):
        out = []
        if when in blackouts:
            out.append("blackout")
        if when.weekday() not in send_days[campaign["type"]]:
            out.append("send_day")
        if campaign["depends_on"]:
            before = placed.get(campaign["depends_on"])
            if before is None or (when - before).days < gap:
                out.append("dependency")
        cid = campaign["campaign_id"]
        if counting == "segment":
            capped = any(full(by_segment.get(g, []), when) for g in segments[cid])
        else:
            capped = any(full(got.get(s, []), when) for s in audience[cid])
        if capped:
            out.append("frequency_cap")
        return out

    for campaign in sorted(plan, key=key):
        cid = campaign["campaign_id"]
        requested, deadline = date.fromisoformat(campaign["requested_date"]), date.fromisoformat(campaign["deadline"])
        first = blocked(campaign, requested)
        reasons[cid] = first[0] if first else ""
        when, placed[cid] = requested, None
        while when <= deadline:
            if not blocked(campaign, when):
                placed[cid] = when
                break
            when += timedelta(days=1)
        if placed[cid]:
            for s in audience[cid]:
                got.setdefault(s, []).append(placed[cid])
            for g in segments[cid]:
                by_segment.setdefault(g, []).append(placed[cid])
    sizes = {cid: len(ids) for cid, ids in audience.items()}
    received: dict[str, int] = {}
    for cid, when in placed.items():
        for s in audience[cid] if when else []:
            received[s] = received.get(s, 0) + 1
    most = max(received.values())
    requested = {c["campaign_id"]: date.fromisoformat(c["requested_date"]) for c in plan}
    figures = [
        sum(1 for cid, when in placed.items() if when and when != requested[cid]),
        sum(1 for when in placed.values() if when is None),
        sum(sizes[cid] for cid, when in placed.items() if when),
        most,
        sum(1 for count in received.values() if count == most),
    ]
    return {"send_date": placed, "reason": reasons, "audience_size": sizes, "figures": figures}


def summed_segment_sizes() -> dict[str, int]:
    """Audience sizes as the sum of each segment's active count: a subscriber in
    two of a campaign's segments counted twice."""
    subscribers, plan, *_ = _calendar_files()
    return {c["campaign_id"]: sum(sum(1 for s in subscribers if s["status"] == "active" and s[g] == "1")
                                  for g in c["segments"].split(";")) for c in plan}


def calendar_reply(calendar: dict, sizes: dict | None = None, figures: list | None = None) -> str:
    sizes = sizes or calendar["audience_size"]
    figures = figures or calendar["figures"]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["campaign_id", "send_date", "audience_size", "reason"])
    for cid in sorted(calendar["send_date"]):
        when = calendar["send_date"][cid]
        writer.writerow([cid, when.isoformat() if when else "none", sizes[cid], calendar["reason"][cid]])
    return ("The calendar.\n\n### schedule.csv\n```csv\n" + out.getvalue() + "```\n\n"
            + "\n".join(f"A{index}: {value}" for index, value in enumerate(figures, 1)) + "\n")


def test_the_calendar_task_pins_what_the_files_give():
    calendar = build_calendar()
    figures = calendar["figures"]
    assert figures == [5, 1, 1247, 8, 8]
    criteria = _by_id(CALENDAR)
    for index, criterion_id in enumerate(
            ["a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails", "a5_subscribers_at_most"]):
        assert criteria[criterion_id]["programmatic"] == {
            "fact": f"answer_q{index + 1}", "near": figures[index],
            "tolerance": {"kind": "absolute", "full": CALENDAR_BANDS[criterion_id][0], "zero": CALENDAR_BANDS[criterion_id][1]}}
    for criterion_id, (full, zero) in CALENDAR_BANDS.items():
        tolerance = criteria[criterion_id]["programmatic"]["tolerance"]
        assert (tolerance["full"], tolerance["zero"]) == (full, zero), criterion_id
        assert f"zero credit {zero:g} or more off." in criteria[criterion_id]["check"] or (
            f"zero credit at {zero:g}" in criteria[criterion_id]["check"]), criterion_id
    # The module's oracle and this file's agree on every campaign.
    reference = email.calendar_reference()
    for field in ("send_date", "reason", "audience_size"):
        assert reference[field] == calendar[field], field
    assert email.calendar_answers() == dict(enumerate(figures, 1))
    assert f"plan's {len(calendar['send_date'])} campaigns" in criteria["every_campaign_once"]["check"]
    assert CALENDAR["answers"] == {"count": 5, "single_number": True}
    judged = [c for c in criteria.values() if "programmatic" not in c]
    assert [c["id"] for c in judged] == ["no_invented_data"] and judged[0]["negative"]
    assert not bench.critical_criterion_ids(CALENDAR)
    named = {c["programmatic"]["fact"] for c in criteria.values() if "programmatic" in c}
    assert {fact for fact in named if fact.startswith("calendar_")} == set(email.calendar_facts(""))
    assert 10 <= len(criteria) <= 18 and (len(criteria) - len(judged)) / len(criteria) >= 0.7
    assert sum((CALENDAR_DIR / name).stat().st_size for name in ("calendar_policy.md", "campaigns.csv", "subscribers.csv")) < 60_000


def test_the_calendar_policy_states_the_rules_the_checker_applies():
    subscribers, plan, policy, blackouts, send_days = _calendar_files()
    assert f"more than {CAP} emails in any\n   {WINDOW} consecutive days" in policy
    assert f"at least\n   {GAP} days after" in policy
    assert blackouts == set(email.BLACKOUTS)
    assert send_days == {kind: set(days) for kind, days in email.SEND_DAYS.items()}
    assert ", ".join(f"`{code}`" for code in email.REASONS) in policy
    assert (CAP, WINDOW, GAP) == (email.CAP_EMAILS, email.CAP_WINDOW_DAYS, email.DEPENDENCY_GAP_DAYS)
    assert date(2027, 2, 1).weekday() == 0 and "February 2027 starts on a Monday" in policy
    assert len(subscribers) == 300 and len(plan) == 12
    assert sorted(int(c["priority"]) for c in plan) == list(range(1, 13))
    # A launch is processed after its teaser, so the procedure always knows the teaser's date.
    by_id = {c["campaign_id"]: c for c in plan}
    for c in plan:
        if c["depends_on"]:
            assert int(by_id[c["depends_on"]]["priority"]) < int(c["priority"])


def test_the_calendar_exercises_every_rule_and_the_look_alikes_are_planted():
    calendar = build_calendar()
    moved_or_dropped = [r for r in calendar["reason"].values() if r]
    assert sorted(set(moved_or_dropped)) == sorted(email.REASONS)
    assert moved_or_dropped.count("frequency_cap") == 3
    # The campaign that is not sent is stopped by the cap: later campaigns of
    # higher priority are already on the calendar.
    assert [cid for cid, when in calendar["send_date"].items() if when is None] == ["C04"]
    assert calendar["reason"]["C04"] == "frequency_cap"
    # C10 is asked for on a blackout Monday that is not a newsletter day either: the first rule is the reason.
    assert calendar["reason"]["C10"] == "blackout"
    # C02 moved off a Saturday, so its launch C03 moves by the teaser gap.
    assert calendar["reason"]["C02"] == "send_day" and calendar["reason"]["C03"] == "dependency"
    subscribers, *_ = _calendar_files()
    combos = {}
    for s in subscribers:
        combo = tuple(g for g in email.SEGMENTS if s[g] == "1")
        combos.setdefault(combo, set()).add(s["status"])
    only_inactive = [combo for combo, statuses in combos.items() if "active" not in statuses]
    assert len(only_inactive) == 4
    assert {s["status"] for s in subscribers} == set(email.STATUSES)


TRAPS = {
    # name: (switches, the checks it must score zero on)
    "by requested date": ({"order": "requested"},
                          {"send_dates_right", "reasons_right", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "calendar weeks": ({"window": "calendar"},
                       {"send_dates_right", "reasons_right", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "only the days before": ({"window": "backward"},
                             {"send_dates_right", "reasons_right", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "per segment": ({"counting": "segment"},
                    {"send_dates_right", "reasons_right", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "unsubscribed counted": ({"everyone": True},
                             {"send_dates_right", "reasons_right", "audiences_right", "a1_moved", "a2_not_sent",
                              "a3_emails_sent", "a4_most_emails", "a5_subscribers_at_most"}),
    "clear days between": ({"gap": GAP + 1},
                           {"send_dates_right", "reasons_right", "a1_moved", "a3_emails_sent", "a5_subscribers_at_most"}),
}


def test_the_reference_passes_every_program_check_and_a_blank_reply_none():
    passed = _results(CALENDAR, CALENDAR_REFERENCE)
    assert passed and all(item["pass"] and item["score"] == 1.0 for item in passed.values()), {
        name: item["evidence"] for name, item in passed.items() if not item["pass"]}
    assert all(value == 0 for value in email.calendar_facts(CALENDAR_REFERENCE).values())
    # The reply this file builds from its own reading of the files passes too.
    assert all(item["pass"] for item in _results(CALENDAR, calendar_reply(build_calendar())).values())
    blank = _results(CALENDAR, "")
    assert not any(item["pass"] for item in blank.values())
    assert bench.free_credit_scores(CALENDAR) == {}
    # The answer block alone earns its own checks and nothing of the file's.
    answer_checks = {"answer_block", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails", "a5_subscribers_at_most"}
    only_answers = CALENDAR_REFERENCE[CALENDAR_REFERENCE.index("A1:"):]
    for name, item in _results(CALENDAR, only_answers).items():
        assert item["score"] == (1.0 if name in answer_checks else 0.0), name


@pytest.mark.parametrize("trap", sorted(TRAPS))
def test_each_tempting_wrong_reading_scores_zero_on_what_it_touches(trap):
    switches, touched = TRAPS[trap]
    reply = calendar_reply(build_calendar(**switches))
    scores = {name: item["score"] for name, item in _results(CALENDAR, reply).items()}
    assert {name for name, score in scores.items() if score == 0.0} == touched, scores
    assert all(scores[name] == 1.0 for name in scores if name not in touched), scores


def test_an_audience_added_up_by_segment_scores_zero_on_audiences_and_a3():
    calendar = build_calendar()
    summed = summed_segment_sizes()
    figures = list(calendar["figures"])
    figures[2] = sum(summed[cid] for cid, when in calendar["send_date"].items() if when)
    scores = {name: item["score"] for name, item in _results(CALENDAR, calendar_reply(calendar, summed, figures)).items()}
    assert {name for name, score in scores.items() if score == 0.0} == {"audiences_right", "a3_emails_sent"}


def test_a_slip_is_counted_where_it_went_wrong():
    def changed(text: str) -> dict:
        return {name: value for name, value in email.calendar_facts(text).items() if value}

    line = "C07,2027-02-18,94,frequency_cap"
    assert changed(_swap(CALENDAR_REFERENCE, line, "C07,2027-02-16,94,")) == {
        "calendar_wrong_date_count": 1, "calendar_wrong_reason_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, "C07,2027-02-18,95,frequency_cap")) == {"calendar_wrong_audience_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, "C07,2027-02-18,94,dependency")) == {"calendar_wrong_reason_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, "C07,18/02/2027,94,frequency_cap")) == {
        "calendar_row_error_count": 1, "calendar_wrong_date_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line + "\n", "")) == {
        "calendar_row_error_count": 1, "calendar_wrong_date_count": 1, "calendar_wrong_reason_count": 1,
        "calendar_wrong_audience_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, line + "\nC13,2027-02-26,40,")) == {"calendar_row_error_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, line + "\n" + line)) == {"calendar_row_error_count": 1}
    # Written loosely, still the same answer: the reason in words, the campaign
    # in lower case, "Not sent" for none, a thousands separator.
    assert changed(_swap(CALENDAR_REFERENCE, line, "c07,2027-02-18,94,Frequency cap")) == {}
    assert changed(_swap(CALENDAR_REFERENCE, "C04,none,130,frequency_cap", "C04,Not sent,130,frequency_cap")) == {}
    assert changed(_swap(CALENDAR_REFERENCE, "C11,2027-02-23,218,", 'C11,2027-02-23,"218",none')) == {}
    # A Markdown table in place of the CSV is read the same way.
    rows = CALENDAR_REFERENCE[CALENDAR_REFERENCE.index("campaign_id,"):CALENDAR_REFERENCE.index("```\n\nA1")].strip().splitlines()
    table = "\n".join(["| " + " | ".join(next(csv.reader([rows[0]]))) + " |", "|---|---|---|---|"]
                      + ["| " + " | ".join(next(csv.reader([row]))) + " |" for row in rows[1:]])
    markdown = CALENDAR_REFERENCE.replace("```csv\n" + "\n".join(rows) + "\n```", table)
    assert markdown != CALENDAR_REFERENCE and changed(markdown) == {}
