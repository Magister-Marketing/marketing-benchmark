"""Email tasks of the 35-task board, generated and graded here.

``email-send-calendar``: a month of campaigns placed on a calendar by a
written procedure. The work is applying a per-subscriber frequency cap over
300 subscribers whose segments overlap, together with blackout dates, send
days by campaign type, a teaser that must lead its launch, deadlines and a
priority order, without one slip.

Each task's reply carries files the way a workflow task's does (a CSV under a
line that names it), and they are read with the same reader
(``eval_runner.workflows.common``). ``bench.measured_facts`` adds what
``facts_for`` returns. For each task the constants below are the one source of
the files the candidate reads (``fixtures()``), the reference answer and the
checker, so a rule cannot say one thing in the brief and another in the
grader. The files are written by this module, deterministically:

    python3 -m eval_runner.task_facts_email --write   # (re)write the files
    python3 -m eval_runner.task_facts_email --check   # report drift, change nothing

All brands, people and figures are invented. Subscribers are ids only.
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import re
import sys
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

CALENDAR = "email-send-calendar"
TASK_IDS = (CALENDAR,)
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path("eval_runner") / "fixtures"

# ── email-send-calendar ──────────────────────────────────────────────────────

BRAND = "Marrowfield Garden Co."
CALENDAR_FILES = ["schedule.csv"]
MONTH_START = date(2027, 2, 1)  # a Monday
MONTH_END = date(2027, 2, 28)
SEGMENTS = ["veg_growers", "houseplants", "vip", "new_subscribers", "lapsed_buyers", "local"]
STATUSES = ["active", "unsubscribed", "bounced"]
BLACKOUTS = {
    date(2027, 2, 15): "Presidents' Day",
    date(2027, 2, 24): "email platform maintenance",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Campaign type -> the weekdays it may go out on (Monday = 0).
SEND_DAYS = {
    "newsletter": (1, 3),
    "promo": (2, 4, 5),
    "teaser": (0, 1, 2, 3, 4),
    "launch": (1, 2, 3),
    "event": (0, 1, 2),
    "survey": (0, 1, 2, 3),
}
DEPENDENCY_GAP_DAYS = 3
CAP_EMAILS = 3
CAP_WINDOW_DAYS = 7
# The order the rules are checked in: the first that rules out a campaign's
# requested date is its reason.
REASONS = ["blackout", "send_day", "dependency", "frequency_cap"]

# (id, name, type, segments, requested day of February, deadline day, depends on, priority)
CAMPAIGNS: list[tuple[str, str, str, tuple[str, ...], int, int, str, int]] = [
    ("C01", "February newsletter", "newsletter", ("veg_growers", "houseplants"), 4, 8, "", 9),
    ("C02", "Spring seed sale teaser", "teaser", ("veg_growers", "lapsed_buyers"), 6, 12, "", 3),
    ("C03", "Spring seed sale launch", "launch", ("veg_growers", "lapsed_buyers", "vip"), 9, 12, "C02", 5),
    ("C04", "Houseplant clearance", "promo", ("houseplants", "new_subscribers"), 6, 7, "", 10),
    ("C05", "Valentine's gift guide", "promo", ("houseplants", "new_subscribers", "vip"), 12, 13, "", 1),
    ("C06", "Pruning workshop invitation", "event", ("local",), 8, 13, "", 12),
    ("C07", "Repotting kit teaser", "teaser", ("houseplants",), 16, 19, "", 7),
    ("C08", "Repotting kit launch", "launch", ("houseplants", "vip"), 23, 27, "C07", 11),
    ("C09", "Win-back offer", "promo", ("lapsed_buyers",), 17, 23, "", 2),
    ("C10", "New grower's guide", "newsletter", ("new_subscribers",), 15, 20, "", 6),
    ("C11", "Late February newsletter", "newsletter", ("veg_growers", "houseplants", "local"), 23, 25, "", 4),
    ("C12", "Customer survey", "survey", ("vip", "local"), 23, 28, "", 8),
]

# Who is on the list: segment combination -> (active, not active). The
# combinations decide which campaigns collide under the cap, so they are set
# by hand; the shuffle that orders the rows is seeded. Four combinations exist
# only among people who unsubscribed or bounced: counting them would move
# campaigns the policy leaves where they are.
_V, _H, _P, _N, _L, _C = SEGMENTS
PROFILES: list[tuple[tuple[str, ...], int, int]] = [
    ((_V,), 58, 8), ((_H,), 40, 6), ((_V, _H), 20, 3), ((_V, _C), 18, 2), ((_H, _C), 10, 1),
    ((_C,), 12, 1), ((_V, _P), 8, 0), ((_H, _P), 6, 0), ((_P, _C), 4, 0), ((_V, _H, _P), 2, 0),
    ((_N,), 22, 3), ((_V, _N), 12, 1), ((_H, _N), 10, 1), ((_L,), 13, 3), ((_V, _L), 10, 2),
    ((_H, _L), 6, 1), ((), 6, 3), ((_L, _C), 0, 2), ((_N, _C), 2, 0), ((_H, _L, _C), 0, 1),
    ((_V, _P, _C), 0, 1), ((_V, _H, _N), 0, 2),
]
SUBSCRIBER_SEED = 20270201


def day(number: int) -> date:
    return MONTH_START + timedelta(days=number - 1)


@lru_cache(maxsize=1)
def subscribers() -> list[dict]:
    """The subscriber export: 300 rows, one per subscriber, the same every time."""
    rng = random.Random(SUBSCRIBER_SEED)
    entries: list[tuple[tuple[str, ...], str]] = []
    for segments, active, inactive in PROFILES:
        entries += [(segments, "active")] * active
        entries += [(segments, "unsubscribed" if rng.random() < 0.65 else "bounced") for _ in range(inactive)]
    rng.shuffle(entries)
    return [
        {"subscriber_id": f"S{number:03d}", "status": status, **{name: int(name in segments) for name in SEGMENTS}}
        for number, (segments, status) in enumerate(entries, 1)
    ]


def campaigns() -> list[dict]:
    return [
        {"campaign_id": cid, "name": name, "type": kind, "segments": list(segments),
         "requested_date": day(requested), "deadline": day(deadline), "depends_on": depends, "priority": priority}
        for cid, name, kind, segments, requested, deadline, depends, priority in CAMPAIGNS
    ]


def audience(campaign: dict) -> list[str]:
    """Active subscribers in at least one of the campaign's segments, each once."""
    return [row["subscriber_id"] for row in subscribers()
            if row["status"] == "active" and any(row[name] for name in campaign["segments"])]


def _over_cap(dates: list[date], candidate: date) -> bool:
    """Whether one more email on ``candidate`` gives this subscriber more than
    the cap in some run of consecutive days that contains it."""
    for offset in range(CAP_WINDOW_DAYS):
        start = candidate - timedelta(days=offset)
        end = start + timedelta(days=CAP_WINDOW_DAYS - 1)
        if sum(start <= sent <= end for sent in dates) + 1 > CAP_EMAILS:
            return True
    return False


@lru_cache(maxsize=1)
def calendar_reference() -> dict:
    """The calendar the policy's procedure builds: priority order, each
    campaign on the first allowed date from its request to its deadline."""
    plan = campaigns()
    audiences = {c["campaign_id"]: audience(c) for c in plan}
    placed: dict[str, date | None] = {}
    reasons: dict[str, str] = {}
    received: dict[str, list[date]] = {}

    def ruled_out(campaign: dict, when: date) -> list[str]:
        out = []
        if when in BLACKOUTS:
            out.append("blackout")
        if when.weekday() not in SEND_DAYS[campaign["type"]]:
            out.append("send_day")
        if campaign["depends_on"]:
            before = placed.get(campaign["depends_on"])
            if before is None or when < before + timedelta(days=DEPENDENCY_GAP_DAYS):
                out.append("dependency")
        if any(_over_cap(received.get(sid, []), when) for sid in audiences[campaign["campaign_id"]]):
            out.append("frequency_cap")
        return out

    for campaign in sorted(plan, key=lambda c: c["priority"]):
        cid = campaign["campaign_id"]
        blocked = ruled_out(campaign, campaign["requested_date"])
        reasons[cid] = blocked[0] if blocked else ""
        chosen = None
        when = campaign["requested_date"]
        while when <= campaign["deadline"]:
            if not ruled_out(campaign, when):
                chosen = when
                break
            when += timedelta(days=1)
        placed[cid] = chosen
        if chosen:
            for sid in audiences[cid]:
                received.setdefault(sid, []).append(chosen)
    counts = {sid: len(dates) for sid, dates in received.items()}
    most = max(counts.values())
    return {
        "send_date": placed, "reason": reasons,
        "audience_size": {cid: len(ids) for cid, ids in audiences.items()},
        "emails_per_subscriber": counts, "most": most,
    }


def calendar_answers() -> dict[int, float]:
    """A1 campaigns moved, A2 not sent, A3 emails sent, A4 the most one
    subscriber receives, A5 how many subscribers receive that many."""
    ref = calendar_reference()
    requested = {c["campaign_id"]: c["requested_date"] for c in campaigns()}
    sent = {cid: when for cid, when in ref["send_date"].items() if when}
    return {
        1: sum(1 for cid, when in sent.items() if when != requested[cid]),
        2: sum(1 for when in ref["send_date"].values() if when is None),
        3: sum(ref["audience_size"][cid] for cid in sent),
        4: ref["most"],
        5: sum(1 for count in ref["emails_per_subscriber"].values() if count == ref["most"]),
    }


def calendar_reference_answer() -> str:
    """A reply that follows the policy to the letter: what a checker must pass."""
    ref = calendar_reference()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["campaign_id", "send_date", "audience_size", "reason"])
    for campaign in campaigns():
        cid = campaign["campaign_id"]
        when = ref["send_date"][cid]
        writer.writerow([cid, when.isoformat() if when else "none", ref["audience_size"][cid], ref["reason"][cid]])
    figures = calendar_answers()
    return "\n".join([
        f"February calendar for {BRAND}, built by the calendar policy's procedure.", "",
        "### schedule.csv", "```csv", buffer.getvalue().rstrip("\n"), "```", "",
        *[f"A{index}: {int(figures[index])}" for index in range(1, 6)], "",
    ])


def subscribers_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["subscriber_id", "status", *SEGMENTS], lineterminator="\n")
    writer.writeheader()
    writer.writerows(subscribers())
    return out.getvalue()


def campaigns_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["campaign_id", "name", "type", "segments", "requested_date", "deadline", "depends_on", "priority"])
    for c in campaigns():
        writer.writerow([c["campaign_id"], c["name"], c["type"], ";".join(c["segments"]),
                         c["requested_date"].isoformat(), c["deadline"].isoformat(), c["depends_on"], c["priority"]])
    return out.getvalue()


def _weekday_list(days: tuple[int, ...]) -> str:
    names = [WEEKDAYS[number] for number in days]
    if len(names) > 2 and list(days) == list(range(days[0], days[-1] + 1)):
        return f"{names[0]} to {names[-1]}"
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]


def calendar_policy_md() -> str:
    blackouts = "\n".join(
        f"   - {WEEKDAYS[when.weekday()]} {when.day} February ({why})" for when, why in sorted(BLACKOUTS.items()))
    send_days = "\n".join(f"   - `{kind}`: {_weekday_list(days)}" for kind, days in SEND_DAYS.items())
    segments = ", ".join(f"`{name}`" for name in SEGMENTS)
    reasons = ", ".join(f"`{code}`" for code in REASONS)
    return f"""# {BRAND}: email calendar policy

The CRM team lists the month's campaigns in `campaigns.csv`. The calendar is
built from that list by the procedure below, so two people who follow it get
the same calendar. February 2027 starts on a Monday and has 28 days.

## Who receives a campaign

The subscriber export has one row per subscriber and one column per segment:
{segments}. A 1 means the subscriber is in that segment.

A campaign goes to every subscriber whose `status` is `active` and who is in
at least one of the campaign's segments. A subscriber in several of its
segments receives it once. Subscribers whose status is `unsubscribed` or
`bounced` receive nothing.

## The rules a send date must meet

1. **Blackout dates.** Nothing is sent on:
{blackouts}
2. **Send days.** Each type of campaign goes out only on these days:
{send_days}
3. **Teaser before launch.** A campaign with a `depends_on` is sent at least
   {DEPENDENCY_GAP_DAYS} days after the campaign it depends on: a teaser sent on the 2nd allows
   its launch on the 5th or later. If that campaign is not sent, neither is
   this one.
4. **Frequency cap.** No subscriber receives more than {CAP_EMAILS} emails in any
   {CAP_WINDOW_DAYS} consecutive days. Nothing sent before 1 February counts.

A campaign is never sent after its `deadline`.

## How to build the calendar

Take the campaigns in order of `priority`, 1 first. For each one:

1. Try its `requested_date`, then each following date up to its `deadline`.
2. A date is allowed when the campaign meets rules 1 to 4 on it, given the
   campaigns already on the calendar.
3. The campaign goes on the first allowed date and stays there. A campaign
   already on the calendar is never moved to make room for a later one.
4. If no date up to the deadline is allowed, the campaign is not sent.

## Reasons

When a campaign does not go out on its requested date (it moved, or it is not
sent), its reason is the first of these rules that rules out the requested
date, in this order: {reasons}.
"""


def calendar_fixtures() -> dict[str, str]:
    return {
        f"{CALENDAR}/calendar_policy.md": calendar_policy_md(),
        f"{CALENDAR}/campaigns.csv": campaigns_csv(),
        f"{CALENDAR}/subscribers.csv": subscribers_csv(),
    }


_NOT_SENT = {"", "none", "not sent", "not_sent", "unscheduled", "n/a", "-"}


def _send_date(text: object) -> date | None | str:
    """A cell's date, None for a campaign not sent, or "unreadable"."""
    value = common.norm(text)
    if value in _NOT_SENT:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if not match:
        return "unreadable"
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return "unreadable"


def _reason(text: object) -> str:
    value = re.sub(r"[\s-]+", "_", common.norm(text))
    return "" if value in ("", "none", "_", "n/a") else value


def _whole(text: object) -> int | None:
    value = common.norm(text).replace(",", "")
    return int(value) if re.fullmatch(r"\d+", value) else None


def calendar_facts(response_text: str) -> dict[str, int]:
    """Counts of what a reply got wrong. Every count is over the plan's
    campaigns, so a missing file is that many errors, never zero."""
    ref = calendar_reference()
    rows = common.tables(response_text, CALENDAR_FILES)["schedule.csv"]
    wanted = [c["campaign_id"] for c in campaigns()]
    given: dict[str, dict] = {}
    listed: list[str] = []
    unreadable = 0
    for row in rows or []:
        cid = common.norm(common.cell(row, "campaign_id", "campaign", "id")).upper()
        if not cid:
            continue
        listed.append(cid)
        given[cid] = row
    for cid in set(listed) & set(wanted):
        unreadable += _send_date(common.cell(given[cid], "send_date", "date")) == "unreadable"
    accounting = (len(set(wanted) - set(listed)) + (len(listed) - len(set(listed)))
                  + len(set(listed) - set(wanted)) + unreadable)

    def wrong(reference: dict, read, *names: str) -> int:
        return sum(1 for cid in wanted
                   if cid not in given or read(common.cell(given[cid], *names)) != reference[cid])

    return {
        "calendar_missing_file_count": int(rows is None),
        "calendar_row_error_count": accounting,
        "calendar_wrong_date_count": wrong(ref["send_date"], _send_date, "send_date", "date"),
        "calendar_wrong_reason_count": wrong(ref["reason"], _reason, "reason", "reason_code"),
        "calendar_wrong_audience_count": wrong(ref["audience_size"], _whole, "audience_size", "recipients", "audience"),
    }


# ── The module's entry points ────────────────────────────────────────────────

def fixtures() -> dict[str, str]:
    """Every file the email tasks supply, by path under FIXTURE_DIR."""
    return {**calendar_fixtures()}


def facts_for(task: dict | None, response_text: str) -> dict[str, int]:
    """The measured facts an email task adds, or nothing for any other task."""
    task_id = (task or {}).get("id")
    if task_id == CALENDAR:
        return calendar_facts(response_text)
    return {}


def drift() -> list[str]:
    """The generated files that are missing or differ on disk."""
    return [
        f"{FIXTURE_DIR / name}: {'missing' if not (REPO_ROOT / FIXTURE_DIR / name).exists() else 'differs from what the module generates'}"
        for name, text in fixtures().items()
        if not (REPO_ROOT / FIXTURE_DIR / name).exists() or (REPO_ROOT / FIXTURE_DIR / name).read_text() != text
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write, or check, the email tasks' files.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        for name, text in fixtures().items():
            path = REPO_ROOT / FIXTURE_DIR / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        print(f"wrote {len(fixtures())} file(s)")
        return 0
    problems = drift()
    for problem in problems:
        print(problem)
    print("ok" if not problems else f"{len(problems)} file(s) out of date: run with --write")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
