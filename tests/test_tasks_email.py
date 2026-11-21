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


# ══ email-compliance-audit ════════════════════════════════════════════════════

AUDIT = _task("email-compliance-audit")
AUDIT_DIR = REPO_ROOT / "eval_runner/fixtures/email-compliance-audit"
AUDIT_REFERENCE = email.audit_reference_answer()
CODE_CHECKS = {
    "DOMAIN": "domain_right", "ADDRESS": "address_right", "UNSUBSCRIBE": "unsubscribe_right",
    "SUBJECT": "subject_right", "TRANSACTIONAL_PROMO": "transactional_promo_right", "CONSENT": "consent_right",
}
# Written out by hand: how many emails get each code, and the three figures.
CODE_COUNTS = {"DOMAIN": 33, "UNSUBSCRIBE": 20, "CONSENT": 20, "ADDRESS": 16, "SUBJECT": 16, "TRANSACTIONAL_PROMO": 11}
AUDIT_FIGURES = [63, 116, 23]
DAYS = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"


def _audit_files():
    policy = (AUDIT_DIR / "sending_policy.md").read_text()
    audiences = {row["audience_id"]: row for row in csv.DictReader((AUDIT_DIR / "audiences.csv").open())}
    records: dict[str, list[tuple[str, str]]] = {}
    domain = None
    for line in (AUDIT_DIR / "dns_records.md").read_text().splitlines():
        if line.startswith("## "):
            domain = line[3:].strip()
            records[domain] = []
        elif domain and line.startswith("| ") and "| TXT |" in line:
            name, _kind, value = [cell.strip() for cell in line.strip("| ").split(" | ")]
            records[domain].append((name, value))
    emails = {}
    text = (AUDIT_DIR / "emails.md").read_text()
    for match in re.finditer(r"^## (E\d{3})\n(.*?)(?=^## E\d{3}\n|\Z)", text, re.M | re.S):
        lines = match.group(2).splitlines()
        stream, purpose, listed, sender = lines[0].split(" · ")
        field = lambda name: next(re.match(rf"^{name}: ?(.*)$", line).group(1) for line in lines  # noqa: E731
                                  if line.startswith(name + ":"))
        emails[match.group(1)] = {
            "stream": stream, "purpose": purpose, "audiences": [a.strip() for a in listed.split(",")],
            "domain": sender.split("@")[1], "subject": field("Subject"), "preheader": field("Preheader"),
            "blocks": [re.match(r"\[(\w+)\] (.*)", part).groups() for part in field("Body").split(" | ")],
            "footer": field("Footer"),
        }
    return policy, audiences, records, emails


def audit_queue(dmarc_sp_counts=False, softfail_fails=False, any_empty_key_fails=False, partial_pct_fails=False,
                sp_none_fails=False, other_selector_counts=False, first_spf_only=False, root_domain_ours=False,
                po_box_invalid=False, transactional_like_marketing=False, spaces_matter=False, capitals_ok=False,
                url_tag_works=False, up_to_strict=False, everything_always=False, minimum_always=False,
                review_is_promo=False, promo_must_be_last=False, first_audience_only=False,
                consent_on_transactional=False, months_strict=False, double_opt_in_everywhere=False) -> dict[str, set[str]]:
    """The policy applied to the emails as the files state it, with a switch
    for each tempting misreading."""
    policy, audiences, records, emails = _audit_files()
    sending = re.findall(r"`([a-z.]+\.example)`", policy.split("## 1.")[1].split("1. **SPF**")[0])
    addresses = re.findall(r"^- (Ostrel Botanicals Inc\..*)$", policy, re.M)
    if po_box_invalid:
        addresses = [a for a in addresses if "PO Box" not in a]
    flat = lambda text: re.sub(r"\s+", " ", text.replace(",", " ").replace("·", " ")).strip()  # noqa: E731

    def domain_passes(name):
        if name == "ostrel.example" and root_domain_ours:
            return True
        if name not in sending:
            return False
        txt = records[name]
        spf = [v for n, v in txt if n == name and v.startswith("v=spf1")]
        if first_spf_only:
            spf = spf[:1]
        ends = ("-all",) if softfail_fails else ("-all", "~all")
        if len(spf) != 1 or "include:spf.sendloop.example" not in spf[0].split() or not spf[0].endswith(ends):
            return False
        keys = [(n, v) for n, v in txt if "._domainkey." in n]
        if any_empty_key_fails and any(re.search(r"p=\s*$", v) for _n, v in keys):
            return False
        usable = [n for n, v in keys if re.search(r"p=[A-Za-z0-9+/]", v)]
        if not (usable if other_selector_counts else f"sl1._domainkey.{name}" in usable):
            return False
        dmarc = [dict(p.strip().split("=", 1) for p in v.split(";")) for n, v in txt if n == f"_dmarc.{name}"]
        if len(dmarc) != 1:
            return False
        tags = dmarc[0]
        if partial_pct_fails and tags.get("pct", "100") != "100":
            return False
        if sp_none_fails and tags.get("sp") == "none":
            return False
        return any(tags.get(tag) in ("quarantine", "reject") for tag in (("p", "sp") if dmarc_sp_counts else ("p",)))

    def allowed(audience_id):
        row = audiences[audience_id]
        if row["consent"] == "express":
            return not (double_opt_in_everywhere or row["region"] == "EU") or row["double_opt_in"] == "yes"
        if row["consent"] == "customer":
            if row["region"] == "CA":
                months = int(row["max_months_since_purchase"])
                return months < 24 if months_strict else months <= 24
            return row["region"] in ("US", "UK")
        return False

    names = "unsubscribe_link|preferences_link" + ("|unsubscribe_url" if url_tag_works else "")
    tag = re.compile(r"\{\{ (?:%s) \}\}" % names if spaces_matter else r"\{\{\s*(?:%s)\s*\}\}" % names,
                     re.I if capitals_ok else 0)
    out = {}
    for email_id, mail in emails.items():
        marketing = mail["stream"] == "marketing"
        footer = mail["footer"]
        codes = set()
        if not domain_passes(mail["domain"]):
            codes.add("DOMAIN")
        footer_rules = marketing or transactional_like_marketing
        if footer_rules and not any(flat(a) in flat(footer) for a in addresses):
            codes.add("ADDRESS")
        if footer_rules and not tag.search(footer):
            codes.add("UNSUBSCRIBE")
        claim = mail["subject"] + " / " + mail["preheader"]
        body = " ".join(text for _kind, text in mail["blocks"])
        broken = False
        percent = re.search(r"(up to )?(\d+)%", claim, re.I)
        offered = [int(n) for n in re.findall(r"(\d+)%", body)]
        if percent:
            up_to = bool(percent.group(1)) and not up_to_strict
            broken |= int(percent.group(2)) != max(offered) if up_to else offered != [int(percent.group(2))]
        scoped = re.search(r"\b(sitewide|everything|all products)\b", claim, re.I)
        broken |= bool(scoped and (everything_always or re.search(r"\b(Excludes|selected)\b", body)))
        claimed_end = re.search(r"\b(?:ends?|until) " + DAYS, claim, re.I)
        body_end = re.findall(r"\buntil " + DAYS, body)
        broken |= bool(claimed_end and body_end and claimed_end.group(1).capitalize() != body_end[-1])
        free = re.search(r"free shipping", claim, re.I)
        broken |= bool(free and re.search(r"over \$\d+", body) and (minimum_always or not re.search(r"over \$\d+", claim)))
        if broken:
            codes.add("SUBJECT")
        if not marketing:
            kinds = ("promo", "recommendations", "review_request") if review_is_promo else ("promo", "recommendations")
            blocks = mail["blocks"]
            promos = [i for i, (kind, _t) in enumerate(blocks) if kind in kinds]
            last = max([i for i, (kind, _t) in enumerate(blocks) if kind in ("order", "shipping", "account")], default=-1)
            if promos and (mail["purpose"] in ("password reset", "account security") or len(promos) > 1
                           or promos[0] < last or re.search(r"code [A-Z0-9]{4,}", blocks[promos[0]][1])
                           or (promo_must_be_last and promos[-1] != len(blocks) - 1)):
                codes.add("TRANSACTIONAL_PROMO")
        if marketing or consent_on_transactional:
            listed = mail["audiences"][:1] if first_audience_only else mail["audiences"]
            if not all(allowed(a) for a in listed):
                codes.add("CONSENT")
        out[email_id] = codes
    return out


def audit_reply(verdicts: dict[str, set[str]]) -> str:
    rows = [f"{email_id},{';'.join(sorted(codes)) or 'pass'}" for email_id, codes in sorted(verdicts.items())]
    figures = [sum(1 for c in verdicts.values() if not c), sum(len(c) for c in verdicts.values()),
               sum(1 for c in verdicts.values() if len(c) > 1)]
    return ("The audit.\n\n### findings.csv\n```csv\nemail_id,verdict\n" + "\n".join(rows) + "\n```\n\n"
            + "\n".join(f"A{index}: {value}" for index, value in enumerate(figures, 1)) + "\n")


def test_the_audit_task_pins_what_the_files_give():
    verdicts = audit_queue()
    assert len(verdicts) == 150
    assert {draft_id: set(codes) for draft_id, codes in email.audit_reference().items()} == verdicts
    assert {code: sum(code in codes for codes in verdicts.values()) for code in email.CODES} == CODE_COUNTS
    figures = [sum(1 for c in verdicts.values() if not c), sum(len(c) for c in verdicts.values()),
               sum(1 for c in verdicts.values() if len(c) > 1)]
    assert figures == AUDIT_FIGURES == [email.audit_answers()[index] for index in (1, 2, 3)]
    criteria = _by_id(AUDIT)
    for index, criterion_id in enumerate(["a1_passing", "a2_violations", "a3_multiple"]):
        assert criteria[criterion_id]["programmatic"] == {
            "fact": f"answer_q{index + 1}", "near": figures[index], "tolerance": {"kind": "absolute", "full": 0, "zero": 1}}
        assert criteria[criterion_id]["check"].endswith("zero credit 1 or more off.")
    for code, criterion_id in CODE_CHECKS.items():
        assert criteria[criterion_id]["programmatic"] == {
            "fact": f"audit_{code.lower()}_error_count", "near": 0, "tolerance": {"kind": "absolute", "full": 0, "zero": 3}}
        assert code in criteria[criterion_id]["check"] and criteria[criterion_id]["check"].endswith("zero credit at 3 or more.")
    assert criteria["every_email_once"]["programmatic"]["tolerance"] == {"kind": "absolute", "full": 0, "zero": 3}
    assert f"export's {len(verdicts)} emails" in criteria["every_email_once"]["check"]
    assert AUDIT["answers"] == {"count": 3, "single_number": True}
    judged = [c for c in criteria.values() if "programmatic" not in c]
    assert [c["id"] for c in judged] == ["fixes_given"]
    assert not bench.critical_criterion_ids(AUDIT)
    named = {c["programmatic"]["fact"] for c in criteria.values() if "programmatic" in c}
    assert {fact for fact in named if fact.startswith("audit_")} == set(email.audit_facts(""))
    assert 10 <= len(criteria) <= 18 and (len(criteria) - len(judged)) / len(criteria) >= 0.7
    assert 30_000 <= sum(path.stat().st_size for path in AUDIT_DIR.iterdir()) < 60_000


def test_the_sending_policy_states_the_rules_the_checker_applies():
    policy, audiences, records, emails = _audit_files()
    assert ", ".join(f"`{code}`" for code in email.CODES) in policy
    for address in email.REGISTERED_ADDRESSES:
        assert f"- {address}\n" in policy
    assert f"`{email.ESP_INCLUDE}`" in policy and "`-all` or `~all`" in policy
    assert "`sl1._domainkey.<domain>`" in policy and "`quarantine` or `reject`" in policy
    assert "`{{ unsubscribe_link }}` or `{{ preferences_link }}`" in policy and "capital letters included" in policy
    assert "`promo` and `recommendations` are promotional" in policy
    assert f"is {email.CA_CUSTOMER_MONTHS} or less" in policy
    assert set(records) == set(email.SENDING_DOMAINS) == set(email.DNS)
    assert len(audiences) == len(email.AUDIENCES) and set(emails) == set(email.draft_ids())
    assert email.domain_failures() == {
        "mail.ostrel.example": [], "orders.ostrel.example": [], "uk.ostrel.example": [], "ca.ostrel.example": [],
        "eu.ostrel.example": ["dmarc"], "news.ostrel.example": ["dkim"], "promo.ostrel.example": ["spf"]}
    # Two From domains are not sending domains at all; one of them is the brand's own.
    assert {mail["domain"] for mail in emails.values()} - set(records) == {"ostrel.example", "ostrel-mail.example"}


AUDIT_TRAPS = {
    # name: (switch, the code check it must zero)
    "DMARC sp= read as p=": ("dmarc_sp_counts", "domain_right"),
    "SPF ~all read as a fail": ("softfail_fails", "domain_right"),
    "an empty key at another selector": ("any_empty_key_fails", "domain_right"),
    "DMARC pct below 100 read as a fail": ("partial_pct_fails", "domain_right"),
    "DMARC sp=none read as a fail": ("sp_none_fails", "domain_right"),
    "a key at another selector counted": ("other_selector_counts", "domain_right"),
    "only the first SPF record read": ("first_spf_only", "domain_right"),
    "the brand's own domain taken as a sending domain": ("root_domain_ours", "domain_right"),
    "a PO box is not an address": ("po_box_invalid", "address_right"),
    "transactional emails held to the footer rules": ("transactional_like_marketing", "address_right"),
    "spaces in the tag matter": ("spaces_matter", "unsubscribe_right"),
    "capital letters in the tag are fine": ("capitals_ok", "unsubscribe_right"),
    "unsubscribe_url works": ("url_tag_works", "unsubscribe_right"),
    "up to read as exactly": ("up_to_strict", "subject_right"),
    "everything is always a promise": ("everything_always", "subject_right"),
    "free shipping with a minimum always flagged": ("minimum_always", "subject_right"),
    "a review request is promotional": ("review_is_promo", "transactional_promo_right"),
    "the promotion must be the last block": ("promo_must_be_last", "transactional_promo_right"),
    "only the first audience checked": ("first_audience_only", "consent_right"),
    "consent asked of transactional emails": ("consent_on_transactional", "consent_right"),
    "24 months read as under 24": ("months_strict", "consent_right"),
    "double opt-in everywhere": ("double_opt_in_everywhere", "consent_right"),
}


def test_the_audit_reference_passes_every_program_check_and_a_blank_reply_none():
    passed = _results(AUDIT, AUDIT_REFERENCE)
    assert passed and all(item["pass"] and item["score"] == 1.0 for item in passed.values()), {
        name: item["evidence"] for name, item in passed.items() if not item["pass"]}
    assert all(value == 0 for value in email.audit_facts(AUDIT_REFERENCE).values())
    assert all(item["pass"] for item in _results(AUDIT, audit_reply(audit_queue())).values())
    assert not any(item["pass"] for item in _results(AUDIT, "").values())
    assert bench.free_credit_scores(AUDIT) == {}
    # Every email passed: each code check and the counts score nothing.
    everything_passes = audit_reply({email_id: set() for email_id in email.draft_ids()})
    scores = {name: item["score"] for name, item in _results(AUDIT, everything_passes).items()}
    assert {name for name, score in scores.items() if score == 0.0} == (
        set(CODE_CHECKS.values()) | {"a1_passing", "a2_violations", "a3_multiple"})


@pytest.mark.parametrize("trap", sorted(AUDIT_TRAPS))
def test_each_tempting_misreading_of_the_policy_scores_zero_on_what_it_touches(trap):
    """A reply built from the misreading scores zero on its code's check, and
    every check it touches is zero, never part credit."""
    switch, target = AUDIT_TRAPS[trap]
    verdicts = audit_queue(**{switch: True})
    changed = sum(1 for email_id, codes in verdicts.items() if codes != email.audit_reference()[email_id])
    assert changed >= 3, (trap, changed)
    scores = {name: item["score"] for name, item in _results(AUDIT, audit_reply(verdicts)).items()}
    assert scores[target] == 0.0, scores
    assert all(score in (0.0, 1.0) for score in scores.values()), scores
    assert scores["a2_violations"] == 0.0 and scores["every_email_once"] == 1.0


def test_an_audit_slip_is_counted_where_it_went_wrong():
    def changed(text: str) -> dict:
        return {name: value for name, value in email.audit_facts(text).items() if value}

    ref = email.audit_reference()
    two = next(email_id for email_id, codes in ref.items() if codes == {"DOMAIN", "SUBJECT"})
    clean = next(email_id for email_id, codes in ref.items() if not codes)
    consent = next(email_id for email_id, codes in ref.items() if codes == {"CONSENT"})
    promo = next(email_id for email_id, codes in ref.items() if codes == {"TRANSACTIONAL_PROMO"})
    assert changed(_swap(AUDIT_REFERENCE, f"{two},DOMAIN;SUBJECT", f"{two},SUBJECT")) == {"audit_domain_error_count": 1}
    assert changed(_swap(AUDIT_REFERENCE, f"{clean},pass", f"{clean},ADDRESS")) == {"audit_address_error_count": 1}
    assert changed(_swap(AUDIT_REFERENCE, f"{two},DOMAIN;SUBJECT", f"{two},pass")) == {
        "audit_domain_error_count": 1, "audit_subject_error_count": 1}
    # One slip costs a third of its code's check; three cost all of it.
    one_slip = _results(AUDIT, _swap(AUDIT_REFERENCE, f"{clean},pass", f"{clean},ADDRESS"))
    assert one_slip["address_right"]["score"] == pytest.approx(2 / 3, abs=1e-3)
    # Written loosely, still the same verdict.
    assert changed(_swap(AUDIT_REFERENCE, f"{two},DOMAIN;SUBJECT", f'{two},"subject, domain"')) == {}
    assert changed(_swap(AUDIT_REFERENCE, f"{promo},TRANSACTIONAL_PROMO", f"{promo.lower()},Transactional promo")) == {}
    assert changed(_swap(AUDIT_REFERENCE, f"{clean},pass", f"{clean},PASS")) == {}
    # Not written as asked: a verdict that is both, a code the policy does not have, an empty one.
    assert changed(_swap(AUDIT_REFERENCE, f"{two},DOMAIN;SUBJECT", f"{two},pass;DOMAIN;SUBJECT")) == {"audit_row_error_count": 1}
    assert changed(_swap(AUDIT_REFERENCE, f"{clean},pass", f"{clean},SPAM_WORDS")) == {"audit_row_error_count": 1}
    assert changed(_swap(AUDIT_REFERENCE, f"{clean},pass", f"{clean},")) == {"audit_row_error_count": 1}
    # An email missing, listed twice, or invented.
    assert changed(_swap(AUDIT_REFERENCE, f"{consent},CONSENT\n", "")) == {
        "audit_row_error_count": 1, "audit_consent_error_count": 1}
    assert changed(_swap(AUDIT_REFERENCE, f"{clean},pass\n", f"{clean},pass\n{clean},pass\n")) == {"audit_row_error_count": 1}
    assert changed(_swap(AUDIT_REFERENCE, f"{clean},pass\n", f"{clean},pass\nE151,pass\n")) == {"audit_row_error_count": 1}
    # The fix lines after the file are not rows of it.
    assert "- DOMAIN:" in AUDIT_REFERENCE and email.audit_facts(AUDIT_REFERENCE)["audit_row_error_count"] == 0


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

    audit_clean = email.audit_facts(AUDIT_REFERENCE)
    unfenced = AUDIT_REFERENCE.replace("```csv\n", "").replace("```\n\nFixes:\n\n", "")
    assert "```" not in unfenced and "pass\n- DOMAIN:" in unfenced
    assert email.audit_facts(unfenced) == audit_clean
    assert all(value == 0 for value in audit_clean.values())
    clean = next(email_id for email_id, codes in email.audit_reference().items() if not codes)
    assert email.audit_facts(_swap(AUDIT_REFERENCE, f"{clean},pass", f"E{int(clean[1:])},pass")) == audit_clean


def test_free_shipping_claims_are_unambiguous_under_section_4():
    """Every free-shipping claim over a body with a minimum either states that
    minimum or says the offer is on every order: no claim leaves the minimum
    out, which section 4 would allow."""
    _policy, _audiences, _records, emails = _audit_files()
    for email_id, mail in emails.items():
        claim = mail["subject"] + " / " + mail["preheader"]
        body = " ".join(text for _kind, text in mail["blocks"])
        if re.search(r"free shipping", claim, re.I) and re.search(r"over \$\d+", body):
            stated = re.search(r"over \$\d+", claim)
            assert stated or "on every order" in claim, email_id
            assert ("SUBJECT" in email.audit_reference()[email_id]) == (not stated), email_id


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
