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
    # Each task's folder holds exactly the files the module writes: nothing left from an older version.
    on_disk = {path.relative_to(REPO_ROOT / email.FIXTURE_DIR).as_posix()
               for task_id in email.TASK_IDS for path in (REPO_ROOT / email.FIXTURE_DIR / task_id).iterdir()}
    assert on_disk == set(email.fixtures())
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
CALENDAR_FIGURES = [5, 1, 3200, 8, 21]
CALENDAR_BANDS = {
    "every_campaign_once": (0, 1), "a1_moved": (0, 1), "a2_not_sent": (0, 1), "a3_emails_sent": (0, 10),
    "a4_most_emails": (0, 1), "a5_subscribers_at_most": (0, 3), "send_dates_right": (0, 2),
    "reasons_right": (0, 2), "audiences_right": (0, 2), "frequency_right": (0, 8),
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


def build_calendar(order="priority", window="rolling", counting="subscriber", everyone=False, gap=GAP,
                   joined_ignored=False, pause_ignored=False, pause_all_month=False, audience_on_request=False):
    """The policy's procedure, read from the files, with a switch for each
    tempting wrong reading: campaigns taken by date instead of priority; the
    cap counted per calendar week or only over the days before; the cap
    counted per segment instead of per subscriber; unsubscribed and bounced
    subscribers counted; the teaser gap read as clear days between; the join
    date ignored; the pause ignored, or read as a pause for the whole month
    whatever its date; and a moved campaign's audience taken on its requested
    date."""
    subscribers, plan, _policy, blackouts, send_days = _calendar_files()
    segments = {c["campaign_id"]: c["segments"].split(";") for c in plan}
    requested = {c["campaign_id"]: date.fromisoformat(c["requested_date"]) for c in plan}

    def audience(cid, when):
        out = []
        for s in subscribers:
            if not (everyone or s["status"] == "active") or not any(s[g] == "1" for g in segments[cid]):
                continue
            if not joined_ignored and date.fromisoformat(s["joined"]) > when:
                continue
            if s["paused_until"] and not pause_ignored and (pause_all_month or date.fromisoformat(s["paused_until"]) > when):
                continue
            out.append(s["subscriber_id"])
        return out

    key = (lambda c: int(c["priority"])) if order == "priority" else (lambda c: (c["requested_date"], int(c["priority"])))
    placed, reasons, sizes, got, by_segment = {}, {}, {}, {}, {}

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
            capped = any(full(got.get(s, []), when) for s in audience(cid, requested[cid] if audience_on_request else when))
        if capped:
            out.append("frequency_cap")
        return out

    for campaign in sorted(plan, key=key):
        cid = campaign["campaign_id"]
        deadline = date.fromisoformat(campaign["deadline"])
        first = blocked(campaign, requested[cid])
        reasons[cid] = first[0] if first else ""
        when, placed[cid] = requested[cid], None
        while when <= deadline:
            if not blocked(campaign, when):
                placed[cid] = when
                break
            when += timedelta(days=1)
        on = requested[cid] if audience_on_request or not placed[cid] else placed[cid]
        sizes[cid] = len(audience(cid, on))
        if placed[cid]:
            for s in audience(cid, on):
                got.setdefault(s, []).append(placed[cid])
            for g in segments[cid]:
                by_segment.setdefault(g, []).append(placed[cid])
    received = {s["subscriber_id"]: len(got.get(s["subscriber_id"], [])) for s in subscribers}
    most = max(received.values())
    figures = [
        sum(1 for cid, when in placed.items() if when and when != requested[cid]),
        sum(1 for when in placed.values() if when is None),
        sum(sizes[cid] for cid, when in placed.items() if when),
        most,
        sum(1 for count in received.values() if count == most),
    ]
    return {"send_date": placed, "reason": reasons, "audience_size": sizes, "received": received, "figures": figures}


def summed_segment_sizes(calendar: dict) -> dict[str, int]:
    """Audience sizes as the sum of each segment's count on the same day: a
    subscriber in two of a campaign's segments counted twice."""
    subscribers, plan, *_ = _calendar_files()
    out = {}
    for c in plan:
        on = calendar["send_date"][c["campaign_id"]] or date.fromisoformat(c["requested_date"])
        out[c["campaign_id"]] = sum(
            sum(1 for s in subscribers if s["status"] == "active" and s[g] == "1" and date.fromisoformat(s["joined"]) <= on
                and (not s["paused_until"] or date.fromisoformat(s["paused_until"]) <= on))
            for g in c["segments"].split(";"))
    return out


def calendar_reply(calendar: dict, sizes: dict | None = None, figures: list | None = None) -> str:
    sizes = sizes or calendar["audience_size"]
    figures = figures or calendar["figures"]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["campaign_id", "send_date", "audience_size", "reason"])
    for cid in sorted(calendar["send_date"]):
        when = calendar["send_date"][cid]
        writer.writerow([cid, when.isoformat() if when else "none", sizes[cid], calendar["reason"][cid]])
    frequency = "\n".join(f"{sid},{count}" for sid, count in calendar["received"].items())
    return ("The calendar.\n\n### schedule.csv\n```csv\n" + out.getvalue() + "```\n\n"
            + "### frequency.csv\n```csv\nsubscriber_id,emails\n" + frequency + "\n```\n\n"
            + "\n".join(f"A{index}: {value}" for index, value in enumerate(figures, 1)) + "\n")


def test_the_calendar_task_pins_what_the_files_give():
    calendar = build_calendar()
    figures = calendar["figures"]
    assert figures == CALENDAR_FIGURES
    criteria = _by_id(CALENDAR)
    for index, criterion_id in enumerate(
            ["a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails", "a5_subscribers_at_most"]):
        full, zero = CALENDAR_BANDS[criterion_id]
        assert criteria[criterion_id]["programmatic"] == {
            "fact": f"answer_q{index + 1}", "near": figures[index], "tolerance": {"kind": "absolute", "full": full, "zero": zero}}
    for criterion_id, (full, zero) in CALENDAR_BANDS.items():
        tolerance = criteria[criterion_id]["programmatic"]["tolerance"]
        assert (tolerance["full"], tolerance["zero"]) == (full, zero), criterion_id
        assert f"zero credit {zero:g} or more off." in criteria[criterion_id]["check"] or (
            f"zero credit at {zero:g}" in criteria[criterion_id]["check"]), criterion_id
    # The module's oracle and this file's agree on every campaign and every subscriber.
    reference = email.calendar_reference()
    for field in ("send_date", "reason", "audience_size"):
        assert reference[field] == calendar[field], field
    assert reference["emails_per_subscriber"] == calendar["received"]
    assert email.calendar_answers() == dict(enumerate(figures, 1))
    assert f"plan's {len(calendar['send_date'])} campaigns" in criteria["every_campaign_once"]["check"]
    assert CALENDAR["answers"] == {"count": 5, "single_number": True}
    judged = [c for c in criteria.values() if "programmatic" not in c]
    assert [c["id"] for c in judged] == ["no_invented_data"] and judged[0]["negative"]
    assert not bench.critical_criterion_ids(CALENDAR)
    named = {c["programmatic"]["fact"] for c in criteria.values() if "programmatic" in c}
    assert {fact for fact in named if fact.startswith("calendar_")} == set(email.calendar_facts(""))
    assert 10 <= len(criteria) <= 18 and (len(criteria) - len(judged)) / len(criteria) >= 0.7
    size = sum((CALENDAR_DIR / name).stat().st_size for name in ("calendar_policy.md", "campaigns.csv", "subscribers.csv"))
    assert 30_000 <= size < 60_000
    # Every subscriber is a row the reply must get right: 800 of them.
    assert len(calendar["received"]) == 800


def test_the_calendar_policy_states_the_rules_the_checker_applies():
    subscribers, plan, policy, blackouts, send_days = _calendar_files()
    assert f"more than {CAP} emails in any\n   {WINDOW} consecutive days" in policy
    assert f"at least\n   {GAP} days after" in policy
    assert "their `joined` date is that day or earlier" in policy
    assert "a paused subscriber receives nothing sent before that date" in policy
    assert blackouts == set(email.BLACKOUTS)
    assert send_days == {kind: set(days) for kind, days in email.SEND_DAYS.items()}
    assert ", ".join(f"`{code}`" for code in email.REASONS) in policy
    assert (CAP, WINDOW, GAP) == (email.CAP_EMAILS, email.CAP_WINDOW_DAYS, email.DEPENDENCY_GAP_DAYS)
    assert date(2027, 2, 1).weekday() == 0 and "February 2027 starts on a Monday" in policy
    assert len(plan) == 12 and sorted(int(c["priority"]) for c in plan) == list(range(1, 13))
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
    assert len([combo for combo, statuses in combos.items() if "active" not in statuses]) == 4
    assert {s["status"] for s in subscribers} == set(email.STATUSES)
    active = [s for s in subscribers if s["status"] == "active"]
    joined_in_february = [s for s in active if s["joined"] >= "2027-02-01"]
    paused = [s for s in active if s["paused_until"]]
    assert len(joined_in_february) >= 30 and len(paused) >= 30
    # Some pauses ended in January: those subscribers receive everything.
    assert any(s["paused_until"] < "2027-02-01" for s in paused)
    # Four of the five campaigns that move reach people their requested date would not.
    on_request = build_calendar(audience_on_request=True)["audience_size"]
    changed = [cid for cid in calendar["audience_size"] if on_request[cid] != calendar["audience_size"][cid]]
    assert sorted(changed) == ["C02", "C03", "C07", "C10"]


TRAPS = {
    # name: (switches, the checks it must score zero on). Audience sizes and
    # counts per subscriber are checked against the reply's own calendar, so a
    # reading that only gets dates wrong costs the dates, and one that only
    # counts wrongly costs the counts.
    "by requested date": ({"order": "requested"},
                          {"send_dates_right", "reasons_right", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "calendar weeks": ({"window": "calendar"},
                       {"send_dates_right", "reasons_right", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "only the days before": ({"window": "backward"},
                             {"send_dates_right", "reasons_right", "a1_moved", "a2_not_sent", "a3_emails_sent",
                              "a4_most_emails"}),
    "per segment": ({"counting": "segment"},
                    {"send_dates_right", "reasons_right", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails"}),
    "unsubscribed counted": ({"everyone": True},
                             {"send_dates_right", "reasons_right", "audiences_right", "frequency_right", "a1_moved",
                              "a2_not_sent", "a3_emails_sent", "a4_most_emails", "a5_subscribers_at_most"}),
    "clear days between": ({"gap": GAP + 1},
                           {"send_dates_right", "reasons_right", "a1_moved", "a3_emails_sent", "a5_subscribers_at_most"}),
    "join dates ignored": ({"joined_ignored": True}, {"audiences_right", "frequency_right", "a3_emails_sent"}),
    "pauses ignored": ({"pause_ignored": True}, {"audiences_right", "frequency_right", "a3_emails_sent"}),
    "a pause is the whole month": ({"pause_all_month": True},
                                   {"audiences_right", "frequency_right", "a3_emails_sent"}),
    "audience on the requested date": ({"audience_on_request": True},
                                       {"audiences_right", "frequency_right", "a3_emails_sent"}),
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
    # The answer block alone earns its own checks and nothing of the files'.
    answer_checks = {"answer_block", "a1_moved", "a2_not_sent", "a3_emails_sent", "a4_most_emails", "a5_subscribers_at_most"}
    only_answers = CALENDAR_REFERENCE[CALENDAR_REFERENCE.index("A1:"):]
    for name, item in _results(CALENDAR, only_answers).items():
        assert item["score"] == (1.0 if name in answer_checks else 0.0), name
    # The schedule without the frequency file scores nothing on the frequency check.
    no_frequency = CALENDAR_REFERENCE[:CALENDAR_REFERENCE.index("### frequency.csv")] + only_answers
    assert {name for name, item in _results(CALENDAR, no_frequency).items() if not item["pass"]} == {
        "files_present", "frequency_right"}


@pytest.mark.parametrize("trap", sorted(TRAPS))
def test_each_tempting_wrong_reading_scores_zero_on_what_it_touches(trap):
    switches, touched = TRAPS[trap]
    reply = calendar_reply(build_calendar(**switches))
    scores = {name: item["score"] for name, item in _results(CALENDAR, reply).items()}
    assert {name for name, score in scores.items() if score == 0.0} == touched, scores
    assert all(scores[name] == 1.0 for name in scores if name not in touched), scores


def test_an_audience_added_up_by_segment_scores_zero_on_audiences_and_a3():
    calendar = build_calendar()
    summed = summed_segment_sizes(calendar)
    figures = list(calendar["figures"])
    figures[2] = sum(summed[cid] for cid, when in calendar["send_date"].items() if when)
    scores = {name: item["score"] for name, item in _results(CALENDAR, calendar_reply(calendar, summed, figures)).items()}
    assert {name for name, score in scores.items() if score == 0.0} == {"audiences_right", "a3_emails_sent"}


def test_a_slip_is_counted_where_it_went_wrong():
    def changed(text: str) -> dict:
        return {name: value for name, value in email.calendar_facts(text).items() if value}

    line = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("C07,"))
    cid, when, size, reason = line.split(",")
    assert (when, reason) == ("2027-02-18", "frequency_cap")
    # Moved back to its requested date with everything else as it was: the date
    # and the reason are wrong, and on the 16th fewer people receive C07 than
    # the size and the counts say (some join or end a pause on the 17th or 18th).
    on_16 = len(email.audience(next(c for c in email.campaigns() if c["campaign_id"] == "C07"), date(2027, 2, 16)))
    assert on_16 < int(size)
    assert changed(_swap(CALENDAR_REFERENCE, line, f"C07,2027-02-16,{size},")) == {
        "calendar_wrong_date_count": 1, "calendar_wrong_reason_count": 1, "calendar_wrong_audience_count": 1,
        "calendar_wrong_frequency_count": int(size) - on_16}
    assert changed(_swap(CALENDAR_REFERENCE, line, f"C07,2027-02-16,{on_16},")) == {
        "calendar_wrong_date_count": 1, "calendar_wrong_reason_count": 1, "calendar_wrong_frequency_count": int(size) - on_16}
    assert changed(_swap(CALENDAR_REFERENCE, line, f"C07,{when},{int(size) + 1},{reason}")) == {"calendar_wrong_audience_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, f"C07,{when},{size},dependency")) == {"calendar_wrong_reason_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, f"C07,18/02/2027,{size},{reason}")) == {
        "calendar_row_error_count": 1, "calendar_wrong_date_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line + "\n", "")) == {
        "calendar_row_error_count": 1, "calendar_wrong_date_count": 1, "calendar_wrong_reason_count": 1,
        "calendar_wrong_audience_count": 1}
    # The counts are read against the reply's own calendar: correct counts for
    # a calendar the reply does not give are wrong.
    wrong_calendar = build_calendar(window="calendar")
    mixed = CALENDAR_REFERENCE[:CALENDAR_REFERENCE.index("### frequency.csv")] + calendar_reply(wrong_calendar)[
        calendar_reply(wrong_calendar).index("### frequency.csv"):]
    assert changed(mixed)["calendar_wrong_frequency_count"] >= 8
    assert changed(_swap(CALENDAR_REFERENCE, line, line + "\nC13,2027-02-26,40,")) == {"calendar_row_error_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, line, line + "\n" + line)) == {"calendar_row_error_count": 1}
    # Written loosely, still the same answer: the reason in words, the campaign
    # in lower case, "Not sent" for none, a quoted number.
    assert changed(_swap(CALENDAR_REFERENCE, line, f"c07,{when},{size},Frequency cap")) == {}
    c04 = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("C04,"))
    assert changed(_swap(CALENDAR_REFERENCE, c04, c04.replace(",none,", ",Not sent,"))) == {}
    c11 = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("C11,"))
    assert changed(_swap(CALENDAR_REFERENCE, c11, c11.replace(",2027-02-23,", ',2027-02-23,"').rstrip(",") + '",none')) == {}
    # A subscriber's count wrong, missing, repeated or invented.
    first = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("S0001,"))
    count = int(first.split(",")[1])
    assert changed(_swap(CALENDAR_REFERENCE, first + "\n", f"S0001,{count + 1}\n")) == {"calendar_wrong_frequency_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, first + "\n", "")) == {"calendar_wrong_frequency_count": 1}
    assert changed(_swap(CALENDAR_REFERENCE, first + "\n", first + "\n" + first + "\nS9999,0\n")) == {
        "calendar_wrong_frequency_count": 2}
    assert changed(_swap(CALENDAR_REFERENCE, first + "\n", f"s0001,{count}\n")) == {}
    # A Markdown table in place of the CSV is read the same way.
    start = CALENDAR_REFERENCE.index("campaign_id,")
    rows = CALENDAR_REFERENCE[start:CALENDAR_REFERENCE.index("```", start)].strip().splitlines()
    table = "\n".join(["| " + " | ".join(next(csv.reader([rows[0]]))) + " |", "|---|---|---|---|"]
                      + ["| " + " | ".join(next(csv.reader([row]))) + " |" for row in rows[1:]])
    markdown = CALENDAR_REFERENCE.replace("```csv\n" + "\n".join(rows) + "\n```", table)
    assert markdown != CALENDAR_REFERENCE and changed(markdown) == {}


# ══ email-compliance-crosscheck ═══════════════════════════════════════════════

CROSS = _task("email-compliance-crosscheck")
CROSS_DIR = REPO_ROOT / "eval_runner/fixtures/email-compliance-crosscheck"
CROSS_REFERENCE = email.audit_reference_answer()
CROSS_CHECKS = {code: f"{code.lower()}_right" for code in email.CODES}
# Written out by hand: how many emails get each code, and the three figures.
CROSS_COUNTS = {"CONSENT": 33, "DOMAIN": 25, "SENDER": 16, "PROMO": 14, "ADDRESS": 12, "FREQUENCY": 11, "PRICE": 10}
CROSS_FIGURES = [69, 121, 34]


def _cross_files():
    read = lambda name: list(csv.DictReader((CROSS_DIR / name).open()))  # noqa: E731
    files = {name: read(f"{name}.csv") for name in
             ("emails", "audiences", "senders", "addresses", "promotions", "prices", "dns_records")}
    policy = (CROSS_DIR / "sending_policy.md").read_text()
    windows = {}
    for region, consent, promotional, newsletter in re.findall(
            r"^\| (US|UK|EU|CA) \| `(\w+)` \| (\w+) \| (\w+) \|$", policy, re.M):
        windows[(region, consent)] = tuple(None if w == "never" else int(w) for w in (promotional, newsletter))
    promotional = re.findall(r"`([a-z -]+)`", policy.split("Purposes ")[1].split(" are\n`promotional`")[0])
    return files, policy, windows, promotional


def crosscheck(dmarc_sp_counts=False, other_selector_counts=False, softfail_fails=False, partial_pct_fails=False,
               sp_none_fails=False, any_empty_key_fails=False, sender_domain_only=False, sender_ignores_stream=False,
               sender_any_region=False, address_any_of_brand=False, address_on_transactional=False,
               consent_date_ignored=False, window_exclusive=False, one_window=False, promo_first_region=False,
               promo_end_exclusive=False, promo_dates_ignored=False, price_latest_row=False, price_us_for_ca=False,
               price_cites_matching_row=False, frequency_eight_days=False, frequency_across_audiences=False,
               frequency_cites_latest=False) -> dict[str, dict[str, str]]:
    """The policy applied to the exports as the files state it, with a switch
    for each tempting misreading."""
    files, _policy, windows, promotional = _cross_files()
    D = date.fromisoformat
    norm = lambda text: re.sub(r"\s+", " ", text.replace(",", " ")).strip().lower()  # noqa: E731
    emails = files["emails"]
    out = {}
    for e in emails:
        codes = {}
        domain = e["from_address"].split("@")[1]
        records = [r for r in files["dns_records"] if r["domain"] == domain]
        spf = [r for r in records if r["name"] == domain and r["value"].startswith("v=spf1")]
        ends = ("-all",) if softfail_fails else ("-all", "~all")
        keys = [r for r in records if "._domainkey." in r["name"]]
        dmarc = next(r for r in records if r["name"] == f"_dmarc.{domain}")
        tags = dict(part.strip().split("=", 1) for part in dmarc["value"].split(";"))
        if len(spf) != 1 or "include:spf.sendloop.example" not in spf[0]["value"].split() \
                or not spf[0]["value"].endswith(ends):
            codes["DOMAIN"] = spf[-1]["record_id"]
        elif any_empty_key_fails and any(re.search(r"p=\s*$", r["value"]) for r in keys):
            codes["DOMAIN"] = next(r for r in keys if re.search(r"p=\s*$", r["value"]))["record_id"]
        elif not any(re.search(r"p=[A-Za-z0-9+/]", r["value"]) for r in keys
                     if other_selector_counts or r["name"] == f"sl1._domainkey.{domain}"):
            codes["DOMAIN"] = next(r for r in keys if r["name"] == f"sl1._domainkey.{domain}")["record_id"]
        elif not (tags.get("p") in ("quarantine", "reject") or (dmarc_sp_counts and tags.get("sp") in ("quarantine", "reject"))) \
                or (partial_pct_fails and tags.get("pct", "100") != "100") or (sp_none_fails and tags.get("sp") == "none"):
            codes["DOMAIN"] = dmarc["record_id"]
        rows = [s for s in files["senders"] if s["brand"] == e["brand"]
                and (sender_any_region or s["region"] == e["region"])
                and (sender_ignores_stream or s["stream"] == e["stream"])]
        allowed = {a for s in rows for a in s["allowed_from_addresses"].split(";")}
        if sender_domain_only:
            allowed_ok = domain in {a.split("@")[1] for a in allowed}
        else:
            allowed_ok = e["from_address"] in allowed
        if not allowed_ok:
            codes["SENDER"] = next(s for s in files["senders"] if (s["brand"], s["region"], s["stream"]) ==
                                   (e["brand"], e["region"], e["stream"]))["sender_id"]
        marketing = e["stream"] == "marketing"
        book = [a for a in files["addresses"] if a["brand"] == e["brand"]]
        own = next(a for a in book if a["region"] == e["region"])
        if marketing or address_on_transactional:
            ok = norm(e["footer_address"]) in ({norm(a["registered_address"]) for a in book} if address_any_of_brand
                                                else {norm(own["registered_address"])})
            if not ok:
                codes["ADDRESS"] = own["address_id"]
        if not marketing:
            out[e["email_id"]] = codes
            continue
        send = D(e["send_date"])
        audience = next(a for a in files["audiences"] if a["audience_id"] == e["audience_id"])
        kind = 0 if one_window or e["purpose"] in promotional else 1
        window = windows[(audience["region"], audience["consent_type"])][kind]
        days = (send - D(audience["last_activity_date"])).days
        if window is None or (not consent_date_ignored and D(audience["consent_date"]) > send) \
                or (days >= window if window_exclusive else days > window):
            codes["CONSENT"] = audience["audience_id"]
        if e["promo_code"]:
            same_code = [p for p in files["promotions"] if p["code"] == e["promo_code"] and p["brand"] == e["brand"]]
            promo = same_code[0] if promo_first_region else next(p for p in same_code if p["region"] == e["region"])
            last_ok = send < D(promo["end_date"]) if promo_end_exclusive else send <= D(promo["end_date"])
            running = promo_dates_ignored or (D(promo["start_date"]) <= send and last_ok)
            if not running or e["discount_shown"] != promo["discount"] or e["offer_ends_shown"] != promo["end_date"]:
                codes["PROMO"] = promo["promo_id"]
        if e["sku"]:
            region = "US" if price_us_for_ca and e["region"] == "CA" else e["region"]
            sheet = [p for p in files["prices"] if p["sku"] == e["sku"] and p["region"] == region]
            row = sheet[-1] if price_latest_row else next(
                p for p in sheet if D(p["effective_from"]) <= send <= D(p["effective_to"]))
            shown = e["price_shown"].lstrip("$£€")
            if shown != row["price"].lstrip("$£€"):
                matching = [p for p in sheet if p["price"].lstrip("$£€") == shown]
                codes["PRICE"] = (matching[0] if price_cites_matching_row and matching else row)["price_id"]
        back = 7 if frequency_eight_days else 6
        earlier = sorted((x for x in emails if x["series"] == e["series"]
                          and (frequency_across_audiences or x["audience_id"] == e["audience_id"])
                          and send - timedelta(days=back) <= D(x["send_date"]) < send), key=lambda x: x["send_date"])
        if len(earlier) >= 2:
            codes["FREQUENCY"] = (earlier[-1] if frequency_cites_latest else earlier[0])["email_id"]
        out[e["email_id"]] = codes
    return out


def cross_reply(verdicts: dict[str, dict[str, str]]) -> str:
    rows = [f"{email_id},{';'.join(f'{c}:{v}' for c, v in sorted(codes.items())) or 'pass'}"
            for email_id, codes in sorted(verdicts.items())]
    figures = [sum(1 for c in verdicts.values() if not c), sum(len(c) for c in verdicts.values()),
               sum(1 for c in verdicts.values() if len(c) > 1)]
    return ("The crosscheck.\n\n### findings.csv\n```csv\nemail_id,verdict\n" + "\n".join(rows) + "\n```\n\n"
            + "\n".join(f"A{index}: {value}" for index, value in enumerate(figures, 1)) + "\n")


def test_the_crosscheck_task_pins_what_the_files_give():
    verdicts = crosscheck()
    assert len(verdicts) == 150
    assert email.audit_reference() == verdicts
    assert {code: sum(code in codes for codes in verdicts.values()) for code in email.CODES} == CROSS_COUNTS
    figures = [sum(1 for c in verdicts.values() if not c), sum(len(c) for c in verdicts.values()),
               sum(1 for c in verdicts.values() if len(c) > 1)]
    assert figures == CROSS_FIGURES == [email.audit_answers()[index] for index in (1, 2, 3)]
    criteria = _by_id(CROSS)
    for index, criterion_id in enumerate(["a1_passing", "a2_violations", "a3_multiple"]):
        assert criteria[criterion_id]["programmatic"] == {
            "fact": f"answer_q{index + 1}", "near": figures[index], "tolerance": {"kind": "absolute", "full": 0, "zero": 1}}
        assert criteria[criterion_id]["check"].endswith("zero credit 1 or more off.")
    for code, criterion_id in CROSS_CHECKS.items():
        assert criteria[criterion_id]["programmatic"] == {
            "fact": f"audit_{code.lower()}_error_count", "near": 0, "tolerance": {"kind": "absolute", "full": 0, "zero": 3}}
        assert code in criteria[criterion_id]["check"] and criteria[criterion_id]["check"].endswith("zero credit at 3 or more.")
    assert criteria["every_email_once"]["programmatic"]["tolerance"] == {"kind": "absolute", "full": 0, "zero": 3}
    assert f"export's {len(verdicts)} emails" in criteria["every_email_once"]["check"]
    assert CROSS["answers"] == {"count": 3, "single_number": True}
    assert (CROSS["prompt_version"], CROSS["rubric_version"]) == (1, 1)
    judged = [c for c in criteria.values() if "programmatic" not in c]
    assert [c["id"] for c in judged] == ["fixes_given"]
    assert not bench.critical_criterion_ids(CROSS)
    named = {c["programmatic"]["fact"] for c in criteria.values() if "programmatic" in c}
    assert {fact for fact in named if fact.startswith("audit_")} == set(email.audit_facts(""))
    assert 10 <= len(criteria) <= 18 and (len(criteria) - len(judged)) / len(criteria) >= 0.7
    assert 30_000 <= sum(path.stat().st_size for path in CROSS_DIR.iterdir()) < 60_000
    # The retired single-source audit is gone; its id is not reused.
    assert not (REPO_ROOT / "eval_runner/tasks/email-compliance-audit.json").exists()


def test_the_crosscheck_policy_states_the_rules_the_checker_applies():
    files, policy, windows, promotional = _cross_files()
    assert windows == email.CONSENT_WINDOWS
    assert tuple(promotional) == email.PROMOTIONAL_PURPOSES
    for code in email.CODES:
        assert f"| `{code}` |" in policy
    assert "a window of 365 days allows a send 365 days after it\n  and not 366" in policy
    assert "were sent in the 6 days before\nits send date" in policy and "2 or more emails" in policy
    assert "No\ndomain in this export fails more than one of the three." in policy
    # Every evidence id a verdict can name is a row of the file the policy says.
    ids = {name: {row[next(iter(row))] for row in rows} for name, rows in files.items()}
    for codes in crosscheck().values():
        for code, row_id in codes.items():
            assert row_id in ids[email.EVIDENCE[code][0].split(".")[0]], (code, row_id)
    # Each lookup the policy names has exactly one row.
    keys = [(s["brand"], s["region"], s["stream"]) for s in files["senders"]]
    assert len(keys) == len(set(keys)) == 16
    assert len({(p["code"], p["brand"], p["region"]) for p in files["promotions"]}) == len(files["promotions"])
    for e in files["emails"]:
        if e["sku"]:
            send = date.fromisoformat(e["send_date"])
            assert sum(1 for p in files["prices"] if p["sku"] == e["sku"] and p["region"] == e["region"]
                       and date.fromisoformat(p["effective_from"]) <= send <= date.fromisoformat(p["effective_to"])) == 1
    pairs = [(e["series"], e["audience_id"], e["send_date"]) for e in files["emails"] if e["series"]]
    assert len(pairs) == len(set(pairs))


def test_the_crosscheck_needs_its_sources_joined_and_plants_look_alikes_on_every_boundary():
    files, _policy, windows, promotional = _cross_files()
    D = date.fromisoformat
    audiences = {a["audience_id"]: a for a in files["audiences"]}
    marketing = [e for e in files["emails"] if e["stream"] == "marketing"]
    on_edge, past_edge, on_consent_day = [], [], []
    for e in marketing:
        a = audiences[e["audience_id"]]
        w = windows[(a["region"], a["consent_type"])][0 if e["purpose"] in promotional else 1]
        days = (D(e["send_date"]) - D(a["last_activity_date"])).days
        on_edge += [e] if w is not None and days == w else []
        past_edge += [e] if w is not None and days == w + 1 else []
        on_consent_day += [e] if e["send_date"] == a["consent_date"] else []
    assert len(on_edge) >= 3 and len(past_edge) >= 3 and len(on_consent_day) >= 3
    ref = email.audit_reference()
    assert all("CONSENT" not in ref[e["email_id"]] for e in on_edge + on_consent_day)
    assert all(ref[e["email_id"]].get("CONSENT") for e in past_edge)
    promos = {(p["code"], p["brand"], p["region"]): p for p in files["promotions"]}
    on_promo_edge = [e for e in marketing if e["promo_code"] and e["send_date"] in (
        promos[(e["promo_code"], e["brand"], e["region"])]["start_date"], promos[(e["promo_code"], e["brand"], e["region"])]["end_date"])]
    assert len(on_promo_edge) >= 6
    # A code runs on different discounts in different regions.
    assert any(len({p["discount"] for p in files["promotions"] if p["code"] == code}) > 1 for code in ("GLOW", "HEARTH"))
    rises = [p for p in files["prices"] if p["effective_from"] != "2027-01-01"]
    assert len(rises) >= 4
    on_rise_day = [e for e in marketing if any(e["sku"] == p["sku"] and e["region"] == p["region"]
                                               and e["send_date"] == p["effective_from"] for p in rises)]
    assert len(on_rise_day) >= 3
    seventh_day = [e for e in marketing if any(
        x["series"] == e["series"] and x["audience_id"] == e["audience_id"]
        and (D(e["send_date"]) - D(x["send_date"])).days == 7 for x in marketing)]
    assert len(seventh_day) >= 6
    # A large share of the verdicts turns on a join: a date window, a region's row, or another email.
    joined = sum(1 for codes in ref.values() for code in codes if code in ("CONSENT", "PROMO", "PRICE", "FREQUENCY"))
    assert joined >= 60


CROSS_TRAPS = {
    "DMARC sp= read as p=": ("dmarc_sp_counts", "DOMAIN"),
    "a key at another selector counted": ("other_selector_counts", "DOMAIN"),
    "SPF ~all read as a fail": ("softfail_fails", "DOMAIN"),
    "DMARC pct below 100 read as a fail": ("partial_pct_fails", "DOMAIN"),
    "DMARC sp=none read as a fail": ("sp_none_fails", "DOMAIN"),
    "an empty key at an unused selector read as a fail": ("any_empty_key_fails", "DOMAIN"),
    "any address on an allowed domain": ("sender_domain_only", "SENDER"),
    "the stream of the sender row ignored": ("sender_ignores_stream", "SENDER"),
    "any region's sender row": ("sender_any_region", "SENDER"),
    "any registered address of the brand": ("address_any_of_brand", "ADDRESS"),
    "transactional footers checked": ("address_on_transactional", "ADDRESS"),
    "the consent date ignored": ("consent_date_ignored", "CONSENT"),
    "the window's last day excluded": ("window_exclusive", "CONSENT"),
    "one window for every message type": ("one_window", "CONSENT"),
    "the first region's promotion row": ("promo_first_region", "PROMO"),
    "a promotion's last day excluded": ("promo_end_exclusive", "PROMO"),
    "a promotion's dates ignored": ("promo_dates_ignored", "PROMO"),
    "the latest price row whatever the date": ("price_latest_row", "PRICE"),
    "the US price for Canada": ("price_us_for_ca", "PRICE"),
    "the price row the shown price matches cited": ("price_cites_matching_row", "PRICE"),
    "seven days back instead of six": ("frequency_eight_days", "FREQUENCY"),
    "a series counted across audiences": ("frequency_across_audiences", "FREQUENCY"),
    "the latest earlier email cited": ("frequency_cites_latest", "FREQUENCY"),
}


def test_the_crosscheck_reference_passes_every_program_check_and_a_blank_reply_none():
    passed = _results(CROSS, CROSS_REFERENCE)
    assert passed and all(item["pass"] and item["score"] == 1.0 for item in passed.values()), {
        name: item["evidence"] for name, item in passed.items() if not item["pass"]}
    assert all(value == 0 for value in email.audit_facts(CROSS_REFERENCE).values())
    assert all(item["pass"] for item in _results(CROSS, cross_reply(crosscheck())).values())
    assert not any(item["pass"] for item in _results(CROSS, "").values())
    assert bench.free_credit_scores(CROSS) == {}
    # The right codes with no evidence ids: every code check scores nothing.
    bare = CROSS_REFERENCE
    for code in email.CODES:
        bare = re.sub(rf"{code}:[A-Z]\d+", code, bare)
    scores = {name: item["score"] for name, item in _results(CROSS, bare).items()}
    assert all(scores[check] == 0.0 for check in CROSS_CHECKS.values()) and scores["every_email_once"] == 0.0


@pytest.mark.parametrize("trap", sorted(CROSS_TRAPS))
def test_each_tempting_misreading_of_the_crosscheck_scores_zero_on_what_it_touches(trap):
    switch, code = CROSS_TRAPS[trap]
    verdicts = crosscheck(**{switch: True})
    changed = sum(1 for email_id, codes in verdicts.items() if codes.get(code) != email.audit_reference()[email_id].get(code))
    assert changed >= 3, (trap, changed)
    scores = {name: item["score"] for name, item in _results(CROSS, cross_reply(verdicts)).items()}
    assert scores[CROSS_CHECKS[code]] == 0.0, scores
    assert all(score in (0.0, 1.0) for score in scores.values()), scores
    assert scores["every_email_once"] == 1.0


def test_a_crosscheck_slip_is_counted_where_it_went_wrong():
    def changed(text: str) -> dict:
        return {name: value for name, value in email.audit_facts(text).items() if value}

    ref = email.audit_reference()
    target = next(email_id for email_id, codes in ref.items() if set(codes) == {"CONSENT", "PRICE"} or len(codes) == 2)
    codes = ref[target]
    line = f"{target},{';'.join(f'{c}:{codes[c]}' for c in email.CODES if c in codes)}"
    assert line in CROSS_REFERENCE
    first, second = [c for c in email.CODES if c in codes]
    clean = next(email_id for email_id, c in ref.items() if not c)
    # The right code with another row's id is wrong for that code.
    wrong_row = codes[first][0] + "99"
    assert changed(_swap(CROSS_REFERENCE, line, line.replace(f"{first}:{codes[first]}", f"{first}:{wrong_row}"))) == {
        f"audit_{first.lower()}_error_count": 1}
    assert changed(_swap(CROSS_REFERENCE, line, f"{target},{second}:{codes[second]}")) == {f"audit_{first.lower()}_error_count": 1}
    assert changed(_swap(CROSS_REFERENCE, f"{clean},pass", f"{clean},SENDER:M01")) == {"audit_sender_error_count": 1}
    # Written loosely, still the same verdict: spaces, lower case, brackets, ids without the leading zero.
    loose = f'{target},"{second.lower()} ({codes[second][0]}{int(codes[second][1:])}); {first}: {codes[first]}"'
    assert changed(_swap(CROSS_REFERENCE, line, loose)) == {}
    # Not written as asked: a code without its row, a code twice, a code the policy does not have.
    assert changed(_swap(CROSS_REFERENCE, line, f"{target},{first};{second}:{codes[second]}")) == {
        "audit_row_error_count": 1, f"audit_{first.lower()}_error_count": 1}
    assert changed(_swap(CROSS_REFERENCE, f"{clean},pass", f"{clean},SPAM:X01")) == {"audit_row_error_count": 1}
    assert changed(_swap(CROSS_REFERENCE, line, line + f";{first}:{codes[first]}")) == {"audit_row_error_count": 1}
    # An email missing, listed twice, or invented; the fix lines after the file are not rows.
    assert changed(_swap(CROSS_REFERENCE, f"{clean},pass\n", "")) == {"audit_row_error_count": 1}
    assert changed(_swap(CROSS_REFERENCE, f"{clean},pass\n", f"{clean},pass\nE151,pass\n")) == {"audit_row_error_count": 1}
    unfenced = CROSS_REFERENCE.replace("```csv\n", "").replace("```\n\nFixes:\n\n", "")
    assert email.audit_facts(unfenced) == email.audit_facts(CROSS_REFERENCE)


def test_replies_written_the_way_models_write_them_read_as_the_reference():
    """An unfenced file followed at once by notes or the answer block, an em
    dash for an empty reason, and ids written loosely all read as written."""
    calendar_clean = email.calendar_facts(CALENDAR_REFERENCE)
    unfenced = CALENDAR_REFERENCE.replace("```csv\n", "").replace("```\n\nA1:", "A1:").replace("```\n", "")
    assert "```" not in unfenced and "\nA1:" in unfenced
    assert email.calendar_facts(unfenced) == calendar_clean
    on_time = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("C01,"))
    for dash in ("—", "–", "-"):
        assert email.calendar_facts(_swap(CALENDAR_REFERENCE, on_time, on_time + dash)) == calendar_clean
    first = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("S0001,"))
    assert email.calendar_facts(_swap(CALENDAR_REFERENCE, first, first.replace("S0001", "s1"))) == calendar_clean
    assert email.calendar_facts(_swap(CALENDAR_REFERENCE, on_time, on_time.replace("C01", "C1"))) == calendar_clean

    audit_clean = email.audit_facts(CROSS_REFERENCE)
    unfenced = CROSS_REFERENCE.replace("```csv\n", "").replace("```\n\nFixes:\n\n", "")
    assert "```" not in unfenced and "\n- DOMAIN:" in unfenced
    assert email.audit_facts(unfenced) == audit_clean
    assert all(value == 0 for value in audit_clean.values())
    clean = next(email_id for email_id, codes in email.audit_reference().items() if not codes)
    assert email.audit_facts(_swap(CROSS_REFERENCE, f"{clean},pass", f"E{int(clean[1:])},pass")) == audit_clean


@pytest.mark.parametrize("style", ["colon", "space", "tab", "comma space", "bullets", "table", "no header",
                                   "other header", "quoted", "loose ids", "unfenced then answers"])
def test_frequency_rows_read_however_a_model_writes_them(style):
    """800 short lines, one per subscriber: every plain way of writing an id
    and a count reads as the reference, and only such lines are read."""
    head, rest = CALENDAR_REFERENCE.split("### frequency.csv\n```csv\nsubscriber_id,emails\n")
    body, tail = rest.split("\n```\n", 1)
    rows = [line.split(",") for line in body.splitlines()]
    assert len(rows) == 800
    header = "subscriber_id,emails\n"
    fence = ("```csv\n", "\n```\n")
    if style == "colon":
        lines = [f"{sid}: {n}" for sid, n in rows]
    elif style == "space":
        lines = [f"{sid} {n}" for sid, n in rows]
    elif style == "tab":
        lines = [f"{sid}\t{n}" for sid, n in rows]
    elif style == "comma space":
        lines = [f"{sid}, {n}" for sid, n in rows]
    elif style == "bullets":
        lines, header, fence = [f"- {sid}: {n}" for sid, n in rows], "", ("", "\n\n")
    elif style == "table":
        lines, header, fence = ["| subscriber_id | emails |", "|---|---|"] + [f"| {sid} | {n} |" for sid, n in rows], "", ("", "\n\n")
    elif style == "no header":
        lines, header = [f"{sid},{n}" for sid, n in rows], ""
    elif style == "other header":
        lines, header = [f"{sid},{n}" for sid, n in rows], "subscriber,emails_received\n"
    elif style == "quoted":
        lines = [f'"{sid}","{n}"' for sid, n in rows]
    elif style == "loose ids":
        lines = [f"{sid.lower().replace('s0', 's', 1)},{n}" for sid, n in rows]
    else:
        lines, fence = [f"{sid},{n}" for sid, n in rows], ("", "\n")
    reply = head + "### frequency.csv\n" + fence[0] + header + "\n".join(lines) + fence[1] + tail
    assert email.calendar_facts(reply) == email.calendar_facts(CALENDAR_REFERENCE)
    assert email.calendar_facts(reply)["calendar_wrong_frequency_count"] == 0


def test_a_frequency_line_with_more_than_an_id_and_a_count_is_not_read():
    first = next(row for row in CALENDAR_REFERENCE.splitlines() if row.startswith("S0001,"))
    count = int(first.split(",")[1])
    for written in (f"S0001,{count},{count}", f"S0001 gets {count}", f"S0001,{count} emails"):
        facts = email.calendar_facts(_swap(CALENDAR_REFERENCE, first + "\n", written + "\n"))
        assert facts["calendar_wrong_frequency_count"] == 1, written
