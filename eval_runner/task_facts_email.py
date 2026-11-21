"""Email tasks of the 35-task board, generated and graded here.

``email-send-calendar``: a month of campaigns placed on a calendar by a
written procedure. The work is applying a per-subscriber frequency cap over
300 subscribers whose segments overlap, together with blackout dates, send
days by campaign type, a teaser that must lead its launch, deadlines and a
priority order, without one slip.

``email-compliance-crosscheck``: 150 scheduled emails of two brands checked
against a sending policy and six exports. Most verdicts need sources joined:
an audience's consent windows on the email's own send date, the promotion
and the price in effect then for its region, the sender map, the DNS
records, and the other emails of its series. Each failing verdict names the
row that proves it.

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
AUDIT = "email-compliance-crosscheck"
TASK_IDS = (CALENDAR, AUDIT)
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path("eval_runner") / "fixtures"

# ── email-send-calendar ──────────────────────────────────────────────────────

BRAND = "Marrowfield Garden Co."
CALENDAR_FILES = ["schedule.csv", "frequency.csv"]
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
# by hand; everything else about a row is drawn from SUBSCRIBER_SEED. Four
# combinations exist only among people who unsubscribed or bounced: counting
# them would move campaigns the policy leaves where they are.
_V, _H, _P, _N, _L, _C = SEGMENTS
PROFILES: list[tuple[tuple[str, ...], int, int]] = [
    ((_V,), 160, 18), ((_H,), 113, 14), ((_V, _H), 52, 7), ((_V, _C), 46, 5), ((_H, _C), 26, 3),
    ((_C,), 32, 3), ((_V, _P), 21, 1), ((_H, _P), 16, 1), ((_P, _C), 10, 0), ((_V, _H, _P), 5, 0),
    ((_N,), 66, 7), ((_V, _N), 32, 3), ((_H, _N), 26, 3), ((_L,), 34, 7), ((_V, _L), 26, 5),
    ((_H, _L), 16, 2), ((), 16, 7), ((_L, _C), 0, 4), ((_N, _C), 5, 0), ((_H, _L, _C), 0, 2),
    ((_V, _P, _C), 0, 2), ((_V, _H, _N), 0, 4),
]
SUBSCRIBER_SEED = 20270201
# Some new subscribers join during February, on one of these days; they
# receive only what is sent on or after the day they join.
JOINABLE = {(_N,), (_V, _N), (_H, _N)}
JOIN_SHARE = 0.35
FEBRUARY_JOIN_DAYS = [3, 7, 8, 10, 11, 12, 16, 17, 18, 22, 25]
# Some subscribers paused their emails; they receive nothing sent before the
# date. The January dates are over before the month starts.
PAUSABLE = {(_V,), (_H,), (_V, _H), (_V, _C), (_H, _C), (_C,), (_N,), (_V, _N), (_H, _N), (_L,), (_V, _L)}
PAUSE_SHARE = 0.09
PAUSED_UNTIL = [date(2027, 1, 12), date(2027, 1, 25), date(2027, 2, 9), date(2027, 2, 17), date(2027, 2, 18),
                date(2027, 2, 23), date(2027, 2, 26), date(2027, 3, 1)]


def day(number: int) -> date:
    return MONTH_START + timedelta(days=number - 1)


def _random_day(rng: random.Random, first: date, last: date) -> date:
    return first + timedelta(days=rng.randrange((last - first).days + 1))


@lru_cache(maxsize=1)
def subscribers() -> list[dict]:
    """The subscriber export, one row per subscriber, the same every time."""
    rng = random.Random(SUBSCRIBER_SEED)
    entries: list[tuple[tuple[str, ...], str]] = []
    for segments, active, inactive in PROFILES:
        entries += [(segments, "active")] * active
        entries += [(segments, "unsubscribed" if rng.random() < 0.65 else "bounced") for _ in range(inactive)]
    rng.shuffle(entries)
    rows = []
    for number, (segments, status) in enumerate(entries, 1):
        if _N in segments:
            joined = _random_day(rng, date(2026, 12, 1), date(2027, 1, 31))
        else:
            joined = _random_day(rng, date(2023, 1, 1), date(2026, 11, 30))
        paused = None
        if status == "active" and segments in JOINABLE and rng.random() < JOIN_SHARE:
            joined = day(rng.choice(FEBRUARY_JOIN_DAYS))
        elif segments in PAUSABLE and rng.random() < PAUSE_SHARE:
            paused = rng.choice(PAUSED_UNTIL)
        rows.append({"subscriber_id": f"S{number:04d}", "joined": joined, "status": status, "paused_until": paused,
                     **{name: int(name in segments) for name in SEGMENTS}})
    return rows


def campaigns() -> list[dict]:
    return [
        {"campaign_id": cid, "name": name, "type": kind, "segments": list(segments),
         "requested_date": day(requested), "deadline": day(deadline), "depends_on": depends, "priority": priority}
        for cid, name, kind, segments, requested, deadline, depends, priority in CAMPAIGNS
    ]


def receives(row: dict, campaign: dict, when: date) -> bool:
    """Whether a subscriber receives a campaign sent on ``when``."""
    return (row["status"] == "active" and row["joined"] <= when
            and (row["paused_until"] is None or row["paused_until"] <= when)
            and any(row[name] for name in campaign["segments"]))


def audience(campaign: dict, when: date) -> list[str]:
    return [row["subscriber_id"] for row in subscribers() if receives(row, campaign, when)]


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
    placed: dict[str, date | None] = {}
    reasons: dict[str, str] = {}
    sizes: dict[str, int] = {}
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
        if any(_over_cap(received.get(sid, []), when) for sid in audience(campaign, when)):
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
        sizes[cid] = len(audience(campaign, chosen or campaign["requested_date"]))
        for sid in audience(campaign, chosen) if chosen else []:
            received.setdefault(sid, []).append(chosen)
    counts = {row["subscriber_id"]: len(received.get(row["subscriber_id"], [])) for row in subscribers()}
    return {"send_date": placed, "reason": reasons, "audience_size": sizes,
            "emails_per_subscriber": counts, "most": max(counts.values())}


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
    schedule = io.StringIO()
    writer = csv.writer(schedule, lineterminator="\n")
    writer.writerow(["campaign_id", "send_date", "audience_size", "reason"])
    for campaign in campaigns():
        cid = campaign["campaign_id"]
        when = ref["send_date"][cid]
        writer.writerow([cid, when.isoformat() if when else "none", ref["audience_size"][cid], ref["reason"][cid]])
    frequency = ["subscriber_id,emails"] + [f"{sid},{count}" for sid, count in ref["emails_per_subscriber"].items()]
    figures = calendar_answers()
    return "\n".join([
        f"February calendar for {BRAND}, built by the calendar policy's procedure.", "",
        "### schedule.csv", "```csv", schedule.getvalue().rstrip("\n"), "```", "",
        "### frequency.csv", "```csv", *frequency, "```", "",
        *[f"A{index}: {int(figures[index])}" for index in range(1, 6)], "",
    ])


def subscribers_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["subscriber_id", "joined", "status", "paused_until", *SEGMENTS])
    for row in subscribers():
        writer.writerow([row["subscriber_id"], row["joined"].isoformat(), row["status"],
                         row["paused_until"].isoformat() if row["paused_until"] else "", *[row[name] for name in SEGMENTS]])
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

A campaign sent on a given day goes to every subscriber who, on that day:

- has `status` `active` (subscribers who are `unsubscribed` or `bounced`
  receive nothing);
- has joined: their `joined` date is that day or earlier;
- is not paused: their `paused_until` is empty, or is that day or earlier
  (a paused subscriber receives nothing sent before that date);
- is in at least one of the campaign's segments.

A subscriber in several of a campaign's segments receives it once. Who
receives a campaign therefore depends on the day it is sent.

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


_NOT_SENT = {"", "none", "not sent", "not_sent", "unscheduled", "n/a", "-", "\u2013", "\u2014"}


def _row_id(text: object, prefix: str, width: int) -> str | None:
    """A row's id written as the export writes it ("C07", "S0001", "E001"),
    or loosely ("c7"), or None when the cell is not an id at all: a line of
    notes or an answer line that follows an unfenced file is not a row."""
    match = re.fullmatch(prefix + r"(\d{1,%d})" % width, common.norm(text), re.IGNORECASE)
    return f"{prefix}{int(match.group(1)):0{width}d}" if match else None


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
    return "" if value in ("", "none", "_", "n/a", "\u2013", "\u2014") else value


def _whole(text: object) -> int | None:
    value = common.norm(text).replace(",", "")
    return int(value) if re.fullmatch(r"\d+", value) else None


# One subscriber's line of frequency.csv, however it is written: "S0001,4",
# "S0001, 4", "S0001: 4", "S0001 4", a tab, a bullet, a Markdown table row,
# quoted cells, with or without the header. A line is read only when it holds
# an id and a count and nothing else, so a header, a note or an answer line
# below an unfenced file is not a subscriber.
_FREQUENCY_LINE = re.compile(
    r"[\s|>*`'\"+-]*(S\d{1,4})[`'\"*]*[\s|,;:=`'\"*]+(\d{1,3})[\s|`'\"*.]*", re.IGNORECASE)


def _frequency_lines(response_text: str) -> list[tuple[str, int]]:
    """Every (subscriber, count) line of the reply's frequency.csv, in order."""
    text = common.sections(response_text, ["frequency.csv"])["frequency.csv"] or ""
    out = []
    for line in text.splitlines()[:5000]:
        match = _FREQUENCY_LINE.fullmatch(line[:200])
        if match:
            out.append((f"S{int(match.group(1)[1:]):04d}", int(match.group(2))))
    return out


def calendar_facts(response_text: str) -> dict[str, int]:
    """Counts of what a reply got wrong. Every count is over the plan's
    campaigns or the export's subscribers, so a missing file is that many
    errors, never zero."""
    ref = calendar_reference()
    found = common.tables(response_text, CALENDAR_FILES)
    rows = found["schedule.csv"]
    wanted = [c["campaign_id"] for c in campaigns()]
    given: dict[str, dict] = {}
    listed: list[str] = []
    unreadable = 0
    for row in rows or []:
        cid = _row_id(common.cell(row, "campaign_id", "campaign", "id"), "C", 2)
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

    # Audience sizes and counts per subscriber are checked against the reply's
    # own calendar, so they test the counting and a wrong date is charged once,
    # to the dates. A campaign the reply leaves out, or dates unreadably,
    # counts at the policy's date.
    plan = {c["campaign_id"]: c for c in campaigns()}
    own: dict[str, date | None] = {}
    for cid in wanted:
        written = _send_date(common.cell(given[cid], "send_date", "date")) if cid in given else "unreadable"
        own[cid] = ref["send_date"][cid] if written == "unreadable" else written
    own_sizes = {cid: len(audience(plan[cid], own[cid] or plan[cid]["requested_date"])) for cid in wanted}
    own_counts = {row["subscriber_id"]: sum(1 for cid in wanted if own[cid] and receives(row, plan[cid], own[cid]))
                  for row in subscribers()}

    counts: dict[str, int | None] = {}
    seen: list[str] = []
    for sid, count in _frequency_lines(response_text):
        seen.append(sid)
        counts[sid] = count
    frequency_errors = (sum(1 for sid, count in own_counts.items() if counts.get(sid) != count)
                        + (len(seen) - len(set(seen))) + len(set(seen) - set(own_counts)))
    return {
        "calendar_missing_file_count": sum(1 for name in CALENDAR_FILES if found[name] is None),
        "calendar_row_error_count": accounting,
        "calendar_wrong_date_count": wrong(ref["send_date"], _send_date, "send_date", "date"),
        "calendar_wrong_reason_count": wrong(ref["reason"], _reason, "reason", "reason_code"),
        "calendar_wrong_audience_count": wrong(own_sizes, _whole, "audience_size", "recipients", "audience"),
        "calendar_wrong_frequency_count": frequency_errors,
    }


# ── email-compliance-crosscheck ──────────────────────────────────────────────
#
# 150 scheduled emails of two brands in four regions, checked against a
# sending policy and six exports. Most verdicts need two or three of them
# joined: an audience's consent on the email's own send date, the promotion
# and the price in effect on that date for that region, the sender map for
# the brand, region and stream, the From domain's DNS records, and the other
# emails of the same series to the same audience. Each failing verdict names
# the row that proves it.

AUDIT_BRAND = "Larkfield Goods"
AUDIT_FILES = ["findings.csv"]
CODES = ["DOMAIN", "SENDER", "ADDRESS", "CONSENT", "PROMO", "PRICE", "FREQUENCY"]
# The file whose rows are a code's evidence, and how its ids are written.
EVIDENCE = {"DOMAIN": ("dns_records.csv", "D", 2), "SENDER": ("senders.csv", "M", 2),
            "ADDRESS": ("addresses.csv", "L", 2), "CONSENT": ("audiences.csv", "A", 2),
            "PROMO": ("promotions.csv", "P", 2), "PRICE": ("prices.csv", "R", 2),
            "FREQUENCY": ("emails.csv", "E", 3)}
ESP_INCLUDE = "include:spf.sendloop.example"
DKIM_SELECTOR = "sl1"
DMARC_POLICIES = ("quarantine", "reject")
AUDIT_SEED = 20270301
BRANDS = ["Ostrel", "Tamsin"]
REGIONS = ["US", "UK", "EU", "CA"]
STREAMS = ["marketing", "transactional"]
CURRENCY = {"US": "$", "UK": "£", "EU": "€", "CA": "$"}
PROMOTIONAL_PURPOSES = ("promotion", "launch", "win-back", "welcome offer")
NEWSLETTER_PURPOSES = ("newsletter", "survey", "event invitation")
TRANSACTIONAL_PURPOSES = ("order confirmation", "shipping notice", "receipt", "password reset")
# (region, consent) -> days after last activity a (promotional, newsletter) email may still go; None: never.
CONSENT_WINDOWS = {
    ("US", "express"): (730, 1095), ("US", "customer"): (365, 730),
    ("UK", "express"): (540, 730), ("UK", "customer"): (180, 365),
    ("EU", "express"): (365, 540), ("EU", "customer"): (None, None),
    ("CA", "express"): (730, 730), ("CA", "customer"): (730, 730),
}
FREQUENCY_LIMIT = 2      # earlier emails of the series to the audience allowed within the window
FREQUENCY_DAYS = 7       # the send date and the six days before

# The sending domains' TXT records, in export order; {key} is a DKIM key drawn from AUDIT_SEED.
DNS_SPEC: dict[str, list[tuple[str, str]]] = {
    "mail.ostrel.example": [
        ("mail.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("mail.ostrel.example", "ostrel-site-verification=7Hc2kQ9pX4"),
        ("sl1._domainkey.mail.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("k1._domainkey.mail.ostrel.example", "v=DKIM1; p="),
        ("_dmarc.mail.ostrel.example", "v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example")],
    "orders.ostrel.example": [
        ("orders.ostrel.example", f"v=spf1 {ESP_INCLUDE} include:_spf.helpdeskly.example ~all"),
        ("sl1._domainkey.orders.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.orders.ostrel.example", "v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@ostrel.example")],
    "uk.ostrel.example": [
        ("uk.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.uk.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.uk.ostrel.example", "v=DMARC1; p=quarantine; pct=25; rua=mailto:dmarc@ostrel.example")],
    "ca.ostrel.example": [
        ("ca.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.ca.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.ca.ostrel.example", "v=DMARC1; p=reject; sp=none; rua=mailto:dmarc@ostrel.example")],
    "eu.ostrel.example": [
        ("eu.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.eu.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.eu.ostrel.example", "v=DMARC1; p=none; sp=quarantine; rua=mailto:dmarc@ostrel.example")],
    "news.ostrel.example": [
        ("news.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.news.ostrel.example", "v=DKIM1; p="),
        ("sl2._domainkey.news.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.news.ostrel.example", "v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example")],
    "mail.tamsin.example": [
        ("mail.tamsin.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.mail.tamsin.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.mail.tamsin.example", "v=DMARC1; p=reject; rua=mailto:dmarc@tamsin.example")],
    "shop.tamsin.example": [
        ("shop.tamsin.example", f"v=spf1 {ESP_INCLUDE} ~all"),
        ("sl1._domainkey.shop.tamsin.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.shop.tamsin.example", "v=DMARC1; p=quarantine; rua=mailto:dmarc@tamsin.example")],
    "promo.tamsin.example": [
        ("promo.tamsin.example", "v=spf1 include:mx.oldesp.example ~all"),
        ("sl1._domainkey.promo.tamsin.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.promo.tamsin.example", "v=DMARC1; p=quarantine; rua=mailto:dmarc@tamsin.example")],
}

# (brand, region, stream) -> the From addresses allowed. Ids M01.. in this order.
_SENDERS: dict[tuple[str, str, str], tuple[str, ...]] = {}
for _brand in BRANDS:
    for _region in REGIONS:
        if _brand == "Ostrel":
            _marketing = {"US": ("hello@mail.ostrel.example", "offers@mail.ostrel.example"),
                          "UK": ("hello@uk.ostrel.example",), "EU": ("hallo@eu.ostrel.example",),
                          "CA": ("hello@ca.ostrel.example", "news@news.ostrel.example")}[_region]
            _orders = ("orders@orders.ostrel.example",)
        else:
            _marketing = (("hello@mail.tamsin.example", "deals@promo.tamsin.example") if _region in ("US", "CA")
                          else ("hello@mail.tamsin.example",))
            _orders = ("orders@shop.tamsin.example",)
        _SENDERS[(_brand, _region, "marketing")] = _marketing
        _SENDERS[(_brand, _region, "transactional")] = _orders
SENDERS = [(f"M{number:02d}", *key, addresses) for number, (key, addresses) in enumerate(_SENDERS.items(), 1)]

ADDRESS_BOOK = [
    ("L01", "Ostrel", "US", "Ostrel Botanicals Inc., 418 Larch Street, Suite 200, Portland, OR 97209, USA"),
    ("L02", "Ostrel", "UK", "Ostrel Botanicals Ltd, 9 Quillan Row, London E2 7QA, UK"),
    ("L03", "Ostrel", "EU", "Ostrel Botanicals BV, Veldhuisstraat 212, 1016 DZ Amsterdam, Netherlands"),
    ("L04", "Ostrel", "CA", "Ostrel Botanicals Canada Inc., 77 Harrow Lane, Toronto, ON M5J 2S1, Canada"),
    ("L05", "Tamsin", "US", "Tamsin Home Inc., 240 Millbrook Road, Burlington, VT 05401, USA"),
    ("L06", "Tamsin", "UK", "Tamsin Home Ltd, 31 Ferrand Street, Manchester M1 3HE, UK"),
    ("L07", "Tamsin", "EU", "Tamsin Home BV, Lindengracht 18, 1015 KH Amsterdam, Netherlands"),
    ("L08", "Tamsin", "CA", "Tamsin Home Canada Inc., 9 Ashby Court, Toronto, ON M5E 1B2, Canada"),
]
OLD_ADDRESSES = {"Ostrel": "Ostrel Botanicals Inc., 22 Alder Street, Portland, OR 97205, USA",
                 "Tamsin": "Tamsin Home Inc., 12 Elm Court, Burlington, VT 05401, USA"}

SKUS = {"OS-101": ("Ostrel", "Oat Milk Cleanser"), "OS-114": ("Ostrel", "Cloudberry Barrier Cream"),
        "OS-120": ("Ostrel", "Rosehip Night Oil"), "TM-201": ("Tamsin", "Cedar and Fig Candle"),
        "TM-210": ("Tamsin", "Linen Room Spray")}
# sku -> region -> price before any change in February or March.
BASE_PRICES = {
    "OS-101": {"US": 24, "UK": 20, "EU": 22, "CA": 31}, "OS-114": {"US": 46, "UK": 38, "EU": 42, "CA": 58},
    "OS-120": {"US": 38, "UK": 32, "EU": 35, "CA": 48}, "TM-201": {"US": 34, "UK": 28, "EU": 31, "CA": 44},
    "TM-210": {"US": 22, "UK": 18, "EU": 20, "CA": 28},
}
# (sku, region) whose price rises during the period, by how much; the day is set from a series that shows it.
PRICE_RISES = {("OS-114", "US"): 4, ("OS-114", "CA"): 5, ("TM-201", "US"): 3, ("TM-210", "US"): 2,
               ("OS-120", "EU"): 3}
# code -> region -> discount, for each brand's promotions.
PROMO_DISCOUNTS = {
    ("Ostrel", "GLOW"): {"US": 15, "UK": 15, "EU": 10, "CA": 20},
    ("Ostrel", "BACK"): {"US": 25, "CA": 20},
    ("Ostrel", "WELCOME"): {"UK": 10},
    ("Tamsin", "HEARTH"): {"US": 20, "UK": 15, "EU": 15, "CA": 20},
    ("Tamsin", "WARM"): {"US": 15, "CA": 10},
}

# Audiences: (key, brand, region, name, consent, how its dates are set against the emails it gets).
AUDIENCE_PLAN = [
    ("O-US-signup", "Ostrel", "US", "US newsletter sign-ups", "express", ("inside", "promotional")),
    ("O-US-customers", "Ostrel", "US", "US customers", "customer", ("fresh",)),
    ("O-US-loyalty", "Ostrel", "US", "US loyalty members", "express", ("outside", "promotional")),
    ("O-UK-signup", "Ostrel", "UK", "UK newsletter sign-ups", "express", ("late",)),
    ("O-UK-customers", "Ostrel", "UK", "UK customers", "customer", ("outside", "promotional")),
    ("O-UK-fair", "Ostrel", "UK", "Spring fair leads", "express", ("inside", "promotional")),
    ("O-EU-signup", "Ostrel", "EU", "EU newsletter sign-ups", "express", ("fresh",)),
    ("O-EU-customers", "Ostrel", "EU", "EU customers", "customer", ("fresh",)),
    ("O-EU-loyalty", "Ostrel", "EU", "EU loyalty members", "express", ("outside", "promotional")),
    ("O-CA-signup", "Ostrel", "CA", "Canada newsletter sign-ups", "express", ("fresh",)),
    ("O-CA-customers", "Ostrel", "CA", "Canada customers", "customer", ("late",)),
    ("O-CA-lapsed", "Ostrel", "CA", "Canada lapsed customers", "customer", ("outside", "promotional")),
    ("T-US-signup", "Tamsin", "US", "US newsletter sign-ups", "express", ("inside", "promotional")),
    ("T-US-customers", "Tamsin", "US", "US customers", "customer", ("fresh",)),
    ("T-US-popup", "Tamsin", "US", "Holiday pop-up sign-ups", "express", ("late",)),
    ("T-UK-signup", "Tamsin", "UK", "UK newsletter sign-ups", "express", ("outside", "promotional")),
    ("T-UK-customers", "Tamsin", "UK", "UK customers", "customer", ("fresh",)),
    ("T-EU-signup", "Tamsin", "EU", "EU newsletter sign-ups", "express", ("inside", "promotional")),
    ("T-EU-customers", "Tamsin", "EU", "EU customers", "customer", ("fresh",)),
    ("T-CA-signup", "Tamsin", "CA", "Canada newsletter sign-ups", "express", ("fresh",)),
    ("T-CA-customers", "Tamsin", "CA", "Canada customers", "customer", ("inside", "promotional")),
]

# Step patterns: (day offset, audience slot). "tight" ones put a third email
# of the series to one audience inside seven days; "edge" ones put it on the
# seventh day after the first, one day outside.
PATTERNS = {
    "spread": [(0, 0), (4, 0), (9, 0), (14, 0)],
    "spread2": [(0, 0), (0, 1), (5, 0), (5, 1), (11, 0), (11, 1)],
    "tight3": [(0, 0), (2, 0), (5, 0), (10, 0)],
    "tight4": [(0, 0), (2, 0), (4, 0), (6, 0), (13, 0)],
    "edge7": [(0, 0), (3, 0), (7, 0), (12, 0)],
    "edge7two": [(0, 0), (0, 1), (3, 0), (3, 1), (7, 0), (7, 1)],
    "alternate": [(0, 0), (1, 1), (2, 0), (3, 1), (5, 0), (6, 1)],
}
# (brand, region, purpose, promo code, sku, first day as days after 1 February, pattern, audience keys, promo dates)
# promo dates: "" (the promotion runs from the first step to the last), "late" (it ends the day before
# the last step), "early" (it starts the day after the first step).
SERIES_PLAN = [
    ("Ostrel", "US", "promotion", "GLOW", "OS-114", 9, "tight3", ["O-US-signup"], ""),
    ("Ostrel", "US", "newsletter", "", "", 10, "spread2", ["O-US-signup", "O-US-customers"], ""),
    ("Ostrel", "US", "win-back", "BACK", "OS-120", 16, "spread", ["O-US-customers"], ""),
    ("Ostrel", "US", "launch", "", "OS-101", 22, "edge7", ["O-US-loyalty"], ""),
    ("Ostrel", "US", "survey", "", "", 12, "spread", ["O-US-loyalty"], ""),
    ("Ostrel", "UK", "promotion", "GLOW", "OS-114", 11, "spread2", ["O-UK-signup", "O-UK-customers"], "late"),
    ("Ostrel", "UK", "newsletter", "", "", 15, "edge7two", ["O-UK-signup", "O-UK-fair"], ""),
    ("Ostrel", "UK", "welcome offer", "WELCOME", "OS-101", 20, "tight4", ["O-UK-fair"], ""),
    ("Ostrel", "EU", "promotion", "GLOW", "OS-120", 13, "spread2", ["O-EU-signup", "O-EU-loyalty"], ""),
    ("Ostrel", "EU", "newsletter", "", "", 18, "alternate", ["O-EU-signup", "O-EU-customers"], ""),
    ("Ostrel", "CA", "promotion", "GLOW", "OS-114", 14, "spread", ["O-CA-signup"], "early"),
    ("Ostrel", "CA", "win-back", "BACK", "OS-120", 24, "tight3", ["O-CA-lapsed"], ""),
    ("Ostrel", "CA", "newsletter", "", "", 9, "spread2", ["O-CA-signup", "O-CA-customers"], ""),
    ("Ostrel", "CA", "event invitation", "", "", 26, "edge7", ["O-CA-customers"], ""),
    ("Tamsin", "US", "promotion", "HEARTH", "TM-201", 10, "alternate", ["T-US-signup", "T-US-customers"], ""),
    ("Tamsin", "US", "newsletter", "", "", 19, "spread", ["T-US-popup"], ""),
    ("Tamsin", "US", "launch", "", "TM-210", 12, "spread2", ["T-US-signup", "T-US-popup"], ""),
    ("Tamsin", "US", "welcome offer", "WARM", "TM-210", 27, "tight4", ["T-US-customers"], ""),
    ("Tamsin", "UK", "promotion", "HEARTH", "TM-201", 12, "spread2", ["T-UK-signup", "T-UK-customers"], "late"),
    ("Tamsin", "UK", "newsletter", "", "", 21, "edge7", ["T-UK-signup"], ""),
    ("Tamsin", "EU", "promotion", "HEARTH", "TM-210", 15, "spread2", ["T-EU-signup", "T-EU-customers"], "early"),
    ("Tamsin", "EU", "survey", "", "", 23, "spread", ["T-EU-signup"], ""),
    ("Tamsin", "CA", "promotion", "HEARTH", "TM-201", 16, "tight3", ["T-CA-customers"], ""),
    ("Tamsin", "CA", "newsletter", "", "", 11, "spread2", ["T-CA-signup", "T-CA-customers"], ""),
    ("Tamsin", "CA", "welcome offer", "WARM", "TM-210", 18, "edge7", ["T-CA-signup"], "late"),
]
TRANSACTIONAL_COUNT = 26
# Planted slips, each a count of marketing emails (or transactional ones where named).
SLIPS = {
    "sender_local_part": 4, "sender_transactional_address": 3, "sender_other_brand": 3, "sender_other_region": 3,
    "transactional_sender_marketing_address": 3,
    "address_other_region": 4, "address_other_brand": 3, "address_old": 3, "address_blank": 2,
    "discount_other_region": 4, "end_other_region": 3,
    "price_old_after_rise": 4, "price_new_before_rise": 3, "price_other_region": 3,
}


def _audit_day(offset: int) -> date:
    return date(2027, 2, 1) + timedelta(days=offset)


def _money(region: str, amount: float) -> str:
    return f"{CURRENCY[region]}{amount:.2f}"


def message_type(purpose: str) -> str:
    return "promotional" if purpose in PROMOTIONAL_PURPOSES else "newsletter"


@lru_cache(maxsize=1)
def audit_data() -> dict:
    """Every export of the crosscheck task, built once from the plans above."""
    rng = random.Random(AUDIT_SEED)
    # ── DNS records
    records = []
    for domain, entries in DNS_SPEC.items():
        for name, value in entries:
            key = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQ" + "".join(
                rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/") for _ in range(32))
            records.append({"record_id": f"D{len(records) + 1:02d}", "domain": domain, "name": name,
                            "type": "TXT", "value": value.replace("{key}", key + "IDAQAB")})
    # ── marketing emails, series by series
    keys = {plan[0]: f"A{number:02d}" for number, plan in enumerate(AUDIENCE_PLAN, 1)}
    marketing = []
    for number, (brand, region, purpose, code, sku, first, pattern, audiences, promo_dates) in enumerate(SERIES_PLAN, 1):
        series = f"S{number:02d}"
        for step, (offset, slot) in enumerate(PATTERNS[pattern]):
            marketing.append({
                "series": series, "step": step, "send_date": _audit_day(first + offset), "brand": brand, "region": region,
                "stream": "marketing", "purpose": purpose, "audience_id": keys[audiences[slot]],
                "promo_code": code, "sku": sku, "promo_dates": promo_dates,
            })
    # ── promotions: one row per code, brand and region; it runs over its series unless planted otherwise
    promotions = []
    for (brand, code), by_region in PROMO_DISCOUNTS.items():
        for region, discount in by_region.items():
            mine = [e for e in marketing if (e["brand"], e["region"], e["promo_code"]) == (brand, region, code)]
            start, end = min(e["send_date"] for e in mine), max(e["send_date"] for e in mine)
            if mine[0]["promo_dates"] == "late":
                end -= timedelta(days=1)
            elif mine[0]["promo_dates"] == "early":
                start += timedelta(days=1)
            promotions.append({"promo_id": f"P{len(promotions) + 1:02d}", "code": code, "brand": brand,
                               "region": region, "start": start, "end": end, "discount": discount})
    promo_of = {(p["brand"], p["region"], p["code"]): p for p in promotions}
    # ── prices: one row per sku and region, or two where the price rises on the date of a series' step
    prices = []
    for sku, by_region in BASE_PRICES.items():
        for region, base in by_region.items():
            rise = PRICE_RISES.get((sku, region))
            shown = sorted({e["send_date"] for e in marketing if (e["sku"], e["region"]) == (sku, region)})
            if rise and shown:
                change = shown[len(shown) // 2]
                prices.append({"price_id": "", "sku": sku, "region": region, "price": base,
                               "effective_from": date(2027, 1, 1), "effective_to": change - timedelta(days=1)})
                prices.append({"price_id": "", "sku": sku, "region": region, "price": base + rise,
                               "effective_from": change, "effective_to": date(2027, 12, 31)})
            else:
                prices.append({"price_id": "", "sku": sku, "region": region, "price": base,
                               "effective_from": date(2027, 1, 1), "effective_to": date(2027, 12, 31)})
    for number, row in enumerate(prices, 1):
        row["price_id"] = f"R{number:02d}"

    def price_on(sku: str, region: str, when: date) -> dict:
        return next(p for p in prices if p["sku"] == sku and p["region"] == region
                    and p["effective_from"] <= when <= p["effective_to"])

    # ── what each marketing email shows when nothing is planted
    address_of = {(brand, region): address for _id, brand, region, address in ADDRESS_BOOK}
    for e in marketing:
        allowed = _SENDERS[(e["brand"], e["region"], "marketing")]
        e["from_address"] = allowed[1] if len(allowed) > 1 and e["step"] % 3 == 1 else allowed[0]
        e["footer_address"] = address_of[(e["brand"], e["region"])]
        promo = promo_of.get((e["brand"], e["region"], e["promo_code"]))
        e["discount_shown"] = f"{promo['discount']}%" if promo else ""
        e["offer_ends_shown"] = promo["end"].isoformat() if promo else ""
        e["price_shown"] = _money(e["region"], price_on(e["sku"], e["region"], e["send_date"])["price"]) if e["sku"] else ""

    # ── planted slips, each on emails drawn from the ones it can apply to
    def draw(name: str, eligible: list[dict]) -> list[dict]:
        picked = rng.sample(sorted(eligible, key=lambda e: (e["series"], e["step"])), SLIPS[name])
        for e in picked:
            e.setdefault("slips", []).append(name)
        return picked

    untouched = lambda e, prefix: not any(s.startswith(prefix) for s in e.get("slips", []))  # noqa: E731
    for e in draw("sender_local_part", [e for e in marketing if e["brand"] == "Ostrel" and e["region"] in ("US", "UK")]):
        domain = e["from_address"].split("@")[1]
        e["from_address"] = f"news@{domain}"
    for e in draw("sender_transactional_address", [e for e in marketing if untouched(e, "sender")]):
        e["from_address"] = _SENDERS[(e["brand"], e["region"], "transactional")][0]
    for e in draw("sender_other_brand", [e for e in marketing if untouched(e, "sender")]):
        other = "Tamsin" if e["brand"] == "Ostrel" else "Ostrel"
        e["from_address"] = _SENDERS[(other, e["region"], "marketing")][0]
    for e in draw("sender_other_region", [e for e in marketing if e["brand"] == "Ostrel" and untouched(e, "sender")]):
        other = {"US": "UK", "UK": "US", "EU": "UK", "CA": "US"}[e["region"]]
        e["from_address"] = _SENDERS[("Ostrel", other, "marketing")][0]
    for e in draw("address_other_region", marketing):
        other = {"US": "CA", "CA": "US", "UK": "EU", "EU": "UK"}[e["region"]]
        e["footer_address"] = address_of[(e["brand"], other)]
    for e in draw("address_other_brand", [e for e in marketing if untouched(e, "address")]):
        other = "Tamsin" if e["brand"] == "Ostrel" else "Ostrel"
        e["footer_address"] = address_of[(other, e["region"])]
    for e in draw("address_old", [e for e in marketing if e["region"] == "US" and untouched(e, "address")]):
        e["footer_address"] = OLD_ADDRESSES[e["brand"]]
    for e in draw("address_blank", [e for e in marketing if untouched(e, "address")]):
        e["footer_address"] = ""

    def other_discount(e: dict) -> int | None:
        by_region = PROMO_DISCOUNTS[(e["brand"], e["promo_code"])]
        mine = by_region[e["region"]]
        return next((d for r, d in sorted(by_region.items()) if d != mine), None)

    for e in draw("discount_other_region", [e for e in marketing if e["promo_code"] and other_discount(e)]):
        e["discount_shown"] = f"{other_discount(e)}%"

    def other_end(e: dict) -> date | None:
        mine = promo_of[(e["brand"], e["region"], e["promo_code"])]["end"]
        return next((p["end"] for p in promotions if p["code"] == e["promo_code"] and p["brand"] == e["brand"]
                     and p["end"] != mine), None)

    for e in draw("end_other_region", [e for e in marketing if e["promo_code"] and other_end(e) and untouched(e, "discount")]):
        e["offer_ends_shown"] = other_end(e).isoformat()
    risen = {(p["sku"], p["region"]) for p in prices if p["effective_from"] > date(2027, 1, 1)}
    after = [e for e in marketing if (e["sku"], e["region"]) in risen and price_on(e["sku"], e["region"], e["send_date"])["effective_from"] > date(2027, 1, 1)]
    before = [e for e in marketing if (e["sku"], e["region"]) in risen and e not in after]
    for e in draw("price_old_after_rise", after):
        e["price_shown"] = _money(e["region"], BASE_PRICES[e["sku"]][e["region"]])
    for e in draw("price_new_before_rise", [e for e in before]):
        e["price_shown"] = _money(e["region"], BASE_PRICES[e["sku"]][e["region"]] + PRICE_RISES[(e["sku"], e["region"])])
    for e in draw("price_other_region", [e for e in marketing if e["sku"] and e["region"] == "CA" and untouched(e, "price")]):
        e["price_shown"] = _money("CA", price_on(e["sku"], "US", e["send_date"])["price"])
    # ── transactional emails: no series, audience, promotion or price; footers are not checked
    transactional = []
    for number in range(TRANSACTIONAL_COUNT):
        brand, region = BRANDS[number % 2], REGIONS[(number // 2) % 4]
        transactional.append({
            "series": "", "step": 0, "send_date": _audit_day(rng.randint(8, 47)), "brand": brand, "region": region,
            "stream": "transactional", "purpose": TRANSACTIONAL_PURPOSES[number % 4], "audience_id": "",
            "promo_code": "", "sku": "", "promo_dates": "", "discount_shown": "", "offer_ends_shown": "",
            "price_shown": "", "from_address": _SENDERS[(brand, region, "transactional")][0],
            "footer_address": rng.choice(["", "", address_of[(brand, rng.choice(REGIONS))]]),
        })
    for e in draw("transactional_sender_marketing_address", transactional):
        e["from_address"] = _SENDERS[(e["brand"], e["region"], "marketing")][0]
    # ── audiences: consent and activity dates set against the emails each one gets
    audiences = []
    for key, brand, region, name, consent, plan in AUDIENCE_PLAN:
        aid = keys[key]
        mine = sorted((e for e in marketing if e["audience_id"] == aid), key=lambda e: e["send_date"])
        first = mine[0]["send_date"]
        consent_date, last_activity = first - timedelta(days=rng.randint(400, 900)), first - timedelta(days=rng.randint(15, 60))
        if plan[0] in ("inside", "outside"):
            typed = [e for e in mine if message_type(e["purpose"]) == plan[1]]
            pivot = typed[len(typed) // 2]
            window = CONSENT_WINDOWS[(region, consent)][0 if plan[1] == "promotional" else 1]
            last_activity = pivot["send_date"] - timedelta(days=window + (plan[0] == "outside"))
            consent_date = min(consent_date, last_activity - timedelta(days=rng.randint(30, 300)))
        elif plan[0] == "late":
            consent_date = mine[len(mine) // 2]["send_date"]
        audiences.append({"audience_id": aid, "brand": brand, "region": region, "name": name, "consent_type": consent,
                          "consent_date": consent_date, "last_activity_date": last_activity})
    # ── ids in send-date order
    emails = sorted(marketing + transactional, key=lambda e: (e["send_date"], e["stream"], e["series"], e["step"],
                                                              e["brand"], e["region"]))
    for number, e in enumerate(emails, 1):
        e["email_id"] = f"E{number:03d}"
    return {"records": records, "senders": SENDERS, "addresses": ADDRESS_BOOK, "promotions": promotions,
            "prices": prices, "audiences": audiences, "emails": emails}


# ── The policy applied ───────────────────────────────────────────────────────

def _dns_failure(domain: str, records: list[dict]) -> str | None:
    """The id of the record by which a domain fails section 1, or None."""
    mine = [r for r in records if r["domain"] == domain]
    spf = [r for r in mine if r["name"] == domain and r["value"].startswith("v=spf1")]
    if len(spf) != 1 or ESP_INCLUDE not in spf[0]["value"].split() or spf[0]["value"].split()[-1] not in ("-all", "~all"):
        return spf[-1]["record_id"]
    dkim = [r for r in mine if r["name"] == f"{DKIM_SELECTOR}._domainkey.{domain}"]
    if not dkim or not re.search(r"\bp=[^;\s]", dkim[0]["value"]):
        return dkim[0]["record_id"]
    dmarc = [r for r in mine if r["name"] == f"_dmarc.{domain}"]
    tags = dict(part.strip().split("=", 1) for part in dmarc[0]["value"].split(";") if "=" in part)
    return None if tags.get("p") in DMARC_POLICIES else dmarc[0]["record_id"]


def _normal_address(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace(",", " ")).strip().lower()


def crosscheck_codes(email_row: dict, data: dict) -> dict[str, str]:
    """The codes the policy gives one email, each with the id of its evidence row."""
    codes: dict[str, str] = {}
    e = email_row
    domain = e["from_address"].split("@")[1]
    failing = _dns_failure(domain, data["records"])
    if failing:
        codes["DOMAIN"] = failing
    sender = next(s for s in data["senders"] if s[1:4] == (e["brand"], e["region"], e["stream"]))
    if e["from_address"] not in sender[4]:
        codes["SENDER"] = sender[0]
    if e["stream"] != "marketing":
        return codes
    address = next(a for a in data["addresses"] if a[1:3] == (e["brand"], e["region"]))
    if _normal_address(e["footer_address"]) != _normal_address(address[3]):
        codes["ADDRESS"] = address[0]
    audience = next(a for a in data["audiences"] if a["audience_id"] == e["audience_id"])
    window = CONSENT_WINDOWS[(audience["region"], audience["consent_type"])][
        0 if message_type(e["purpose"]) == "promotional" else 1]
    if (window is None or audience["consent_date"] > e["send_date"]
            or (e["send_date"] - audience["last_activity_date"]).days > window):
        codes["CONSENT"] = audience["audience_id"]
    if e["promo_code"]:
        promo = next(p for p in data["promotions"] if (p["code"], p["brand"], p["region"]) == (e["promo_code"], e["brand"], e["region"]))
        if not (promo["start"] <= e["send_date"] <= promo["end"]) or e["discount_shown"] != f"{promo['discount']}%" \
                or e["offer_ends_shown"] != promo["end"].isoformat():
            codes["PROMO"] = promo["promo_id"]
    if e["sku"]:
        price = next(p for p in data["prices"] if p["sku"] == e["sku"] and p["region"] == e["region"]
                     and p["effective_from"] <= e["send_date"] <= p["effective_to"])
        if e["price_shown"] != _money(e["region"], price["price"]):
            codes["PRICE"] = price["price_id"]
    earlier = sorted((x for x in data["emails"] if x["series"] == e["series"] and x["audience_id"] == e["audience_id"]
                      and e["send_date"] - timedelta(days=FREQUENCY_DAYS - 1) <= x["send_date"] < e["send_date"]),
                     key=lambda x: x["send_date"])
    if len(earlier) >= FREQUENCY_LIMIT:
        codes["FREQUENCY"] = earlier[0]["email_id"]
    return codes


@lru_cache(maxsize=1)
def audit_reference() -> dict[str, dict[str, str]]:
    data = audit_data()
    return {e["email_id"]: crosscheck_codes(e, data) for e in data["emails"]}


def audit_answers() -> dict[int, float]:
    """A1 emails that pass, A2 violations, A3 emails with more than one."""
    ref = audit_reference()
    return {1: sum(1 for codes in ref.values() if not codes), 2: sum(len(codes) for codes in ref.values()),
            3: sum(1 for codes in ref.values() if len(codes) > 1)}


def draft_ids() -> list[str]:
    return list(audit_reference())


def _verdict_text(codes: dict[str, str]) -> str:
    return ";".join(f"{code}:{codes[code]}" for code in CODES if code in codes) or "pass"


_FIXES = {
    "DOMAIN": "send from a domain that passes section 1, or correct the failing record",
    "SENDER": "send from an address the sender map allows for the brand, region and stream",
    "ADDRESS": "put the brand's registered address for the region in the footer",
    "CONSENT": "send only to an audience whose consent allows the email on its send date, or move the send",
    "PROMO": "show the promotion's discount and end date for the region and send while it runs",
    "PRICE": "show the price in effect for the region on the send date",
    "FREQUENCY": "move or drop the email so the audience gets at most two of the series in seven days",
}


def audit_reference_answer() -> str:
    """A reply that follows the policy to the letter: what a checker must pass."""
    ref = audit_reference()
    out = [f"Crosscheck of the {len(ref)} scheduled emails against the sending policy.", "",
           "### findings.csv", "```csv", "email_id,verdict"]
    out += [f"{email_id},{_verdict_text(codes)}" for email_id, codes in ref.items()]
    out += ["```", "", "Fixes:", ""] + [f"- {code}: {_FIXES[code]}." for code in CODES]
    figures = audit_answers()
    out += ["", *[f"A{index}: {int(figures[index])}" for index in range(1, 4)], ""]
    return "\n".join(out)


# ── The files the candidate reads ────────────────────────────────────────────

def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _iso(value) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def crosscheck_fixtures() -> dict[str, str]:
    data = audit_data()
    emails = _csv(["email_id", "send_date", "brand", "region", "stream", "purpose", "series", "audience_id",
                   "from_address", "promo_code", "discount_shown", "offer_ends_shown", "sku", "price_shown",
                   "footer_address"],
                  [[e["email_id"], _iso(e["send_date"]), e["brand"], e["region"], e["stream"], e["purpose"], e["series"],
                    e["audience_id"], e["from_address"], e["promo_code"], e["discount_shown"], e["offer_ends_shown"],
                    e["sku"], e["price_shown"], e["footer_address"]] for e in data["emails"]])
    audiences = _csv(["audience_id", "brand", "region", "name", "consent_type", "consent_date", "last_activity_date"],
                     [[a["audience_id"], a["brand"], a["region"], a["name"], a["consent_type"], _iso(a["consent_date"]),
                       _iso(a["last_activity_date"])] for a in data["audiences"]])
    senders = _csv(["sender_id", "brand", "region", "stream", "allowed_from_addresses"],
                   [[sid, brand, region, stream, ";".join(addresses)] for sid, brand, region, stream, addresses in data["senders"]])
    addresses = _csv(["address_id", "brand", "region", "registered_address"], [list(row) for row in data["addresses"]])
    promotions = _csv(["promo_id", "code", "brand", "region", "start_date", "end_date", "discount"],
                      [[p["promo_id"], p["code"], p["brand"], p["region"], _iso(p["start"]), _iso(p["end"]),
                        f"{p['discount']}%"] for p in data["promotions"]])
    prices = _csv(["price_id", "sku", "product", "region", "price", "effective_from", "effective_to"],
                  [[p["price_id"], p["sku"], SKUS[p["sku"]][1], p["region"], _money(p["region"], p["price"]),
                    _iso(p["effective_from"]), _iso(p["effective_to"])] for p in data["prices"]])
    dns = _csv(["record_id", "domain", "name", "type", "value"],
               [[r["record_id"], r["domain"], r["name"], r["type"], r["value"]] for r in data["records"]])
    return {
        f"{AUDIT}/sending_policy.md": crosscheck_policy_md(),
        f"{AUDIT}/emails.csv": emails,
        f"{AUDIT}/audiences.csv": audiences,
        f"{AUDIT}/senders.csv": senders,
        f"{AUDIT}/addresses.csv": addresses,
        f"{AUDIT}/promotions.csv": promotions,
        f"{AUDIT}/prices.csv": prices,
        f"{AUDIT}/dns_records.csv": dns,
    }


def crosscheck_policy_md() -> str:
    rows = "\n".join(
        f"| {region} | `{consent}` | {'never' if windows[0] is None else windows[0]} | "
        f"{'never' if windows[1] is None else windows[1]} |" for (region, consent), windows in CONSENT_WINDOWS.items())
    codes = ", ".join(f"`{code}`" for code in CODES)
    promotional = ", ".join(f"`{p}`" for p in PROMOTIONAL_PURPOSES)
    newsletter = ", ".join(f"`{p}`" for p in NEWSLETTER_PURPOSES)
    return f"""# {AUDIT_BRAND}: email sending policy

{AUDIT_BRAND} sends email for two brands, Ostrel and Tamsin, in four regions
(US, UK, EU, CA). Before the move to the new email platform, every scheduled
email in `emails.csv` is checked against this policy, using the other files
exported with it.

## Verdicts

An email that breaks no rule passes. An email that breaks a rule gets that
rule's code together with the id of the row that proves it, written
`CODE:ROW_ID` (for example `PRICE:R99`). An email can break several rules;
it gets each code once. The codes, and the file whose row each one names:

| code | rule | the row it names |
|---|---|---|
| `DOMAIN` | 1 | the failing record in `dns_records.csv` |
| `SENDER` | 2 | the row of `senders.csv` for the email's brand, region and stream |
| `ADDRESS` | 3 | the row of `addresses.csv` for the email's brand and region |
| `CONSENT` | 4 | the email's audience in `audiences.csv` |
| `PROMO` | 5 | the row of `promotions.csv` for the email's code, brand and region |
| `PRICE` | 6 | the row of `prices.csv` in effect for the email's product and region on its send date |
| `FREQUENCY` | 7 | an earlier email in `emails.csv`, as rule 7 says |

Dates are calendar days. "Between" two dates includes both. Every rule is
applied to each email on its own `send_date`.

## 1. Sending domain (`DOMAIN`)

The domain of the email's `from_address` must meet all three of these in
`dns_records.csv`:

1. **SPF**: the domain has exactly one TXT record named after the domain that
   starts with `v=spf1`. That record contains `{ESP_INCLUDE}` and ends with
   `-all` or `~all`.
2. **DKIM**: the record named `{DKIM_SELECTOR}._domainkey.<domain>` contains `v=DKIM1` and a
   `p=` value that is not empty.
3. **DMARC**: the record named `_dmarc.<domain>` has a `p=` tag of
   `quarantine` or `reject`.

An email from a domain that fails gets `DOMAIN` with the id of the record
that fails: the SPF record, the `{DKIM_SELECTOR}._domainkey` record, or the DMARC record. No
domain in this export fails more than one of the three.

## 2. Sender (`SENDER`)

`senders.csv` has one row for each brand, region and stream. An email's
`from_address` must be one of the addresses in the row for its own brand,
region and stream. Otherwise it gets `SENDER` with that row's id.

## 3. Postal address (`ADDRESS`)

A marketing email's `footer_address` is the registered address in
`addresses.csv` for its brand and region, as written there (only commas,
spaces and capital letters may differ). Otherwise it gets `ADDRESS` with
that row's id. Transactional emails are not checked under this rule.

## 4. Consent (`CONSENT`)

A marketing email may go to its audience only when, on its send date, both
hold:

- the audience's `consent_date` is the send date or earlier;
- the send date is no more than the window below after the audience's
  `last_activity_date`: a window of 365 days allows a send 365 days after it
  and not 366.

The window depends on the audience's region and consent type and on the
email's message type. Purposes {promotional} are
`promotional`; purposes {newsletter} are `newsletter`.

| region | consent | promotional (days) | newsletter (days) |
|---|---|---|---|
{rows}

`never` means no marketing email may go to such an audience. An email that
may not go gets `CONSENT` with its audience's id. Transactional emails need
no consent.

## 5. Promotions (`PROMO`)

A marketing email with a `promo_code` is checked against the row of
`promotions.csv` for that code, its brand and its region. The email must be
sent between the row's `start_date` and `end_date`, its `discount_shown`
must be the row's `discount`, and its `offer_ends_shown` must be the row's
`end_date`. Otherwise it gets `PROMO` with that row's id. A code runs on
different dates and discounts in different regions.

## 6. Prices (`PRICE`)

A marketing email that shows a product (`sku`) shows, as `price_shown`, the
price of that product for its region in effect on its send date: the row of
`prices.csv` for that sku and region whose dates, `effective_from` to
`effective_to`, include the send date. Otherwise it gets `PRICE` with the
id of that row.

## 7. Frequency within a series (`FREQUENCY`)

Emails with the same `series` and `audience_id` are one series to one
audience; no two of them share a send date. An email gets `FREQUENCY` when
{FREQUENCY_LIMIT} or more emails of its series to its audience were sent in the {FREQUENCY_DAYS - 1} days before
its send date, and it names the earliest of those emails. An email sent {FREQUENCY_DAYS}
days after another is outside them. Every email in `emails.csv` counts,
whatever its own verdict. Transactional emails have no series.
"""


_VERDICT_PART = re.compile(r"([A-Za-z_]+)\s*(?::|=|\(|\s)\s*([A-Za-z])0*(\d{1,3})\s*\)?")


def _crosscheck_verdict(text: object) -> tuple[dict[str, str], bool]:
    """The codes and evidence ids a verdict cell gives, and whether it is
    written as asked: `pass` alone, or `CODE:ROW_ID` parts, each code once."""
    value = str(text or "").strip().strip("`\"'").strip()
    if value.lower() == "pass":
        return {}, True
    given: dict[str, str] = {}
    written_as_asked = bool(value)
    for code, letter, digits in _VERDICT_PART.findall(value):
        code = code.upper()
        if code not in CODES or code in given:
            written_as_asked = False
            continue
        given[code] = f"{letter.upper()}{int(digits):0{EVIDENCE[code][2]}d}"
    if _VERDICT_PART.sub("", value).strip(" ;,|/&+\t"):
        written_as_asked = False
    return given, written_as_asked


def audit_facts(response_text: str) -> dict[str, int]:
    """Counts of what a reply got wrong. Every count is over the export's
    emails, so a missing file is that many errors, never zero. A code given
    with the wrong evidence row is wrong for that code."""
    ref = audit_reference()
    rows = common.tables(response_text, AUDIT_FILES)["findings.csv"]
    given: dict[str, dict[str, str]] = {}
    listed: list[str] = []
    malformed = 0
    for row in rows or []:
        email_id = _row_id(common.cell(row, "email_id", "email", "id"), "E", 3)
        if not email_id:
            continue
        listed.append(email_id)
        codes, written_as_asked = _crosscheck_verdict(common.cell(row, "verdict", "codes", "violations"))
        given[email_id] = codes
        malformed += email_id in ref and not written_as_asked
    facts = {
        "audit_missing_file_count": int(rows is None),
        "audit_row_error_count": (len(set(ref) - set(listed)) + (len(listed) - len(set(listed)))
                                  + len(set(listed) - set(ref)) + malformed),
    }
    for code in CODES:
        facts[f"audit_{code.lower()}_error_count"] = sum(
            1 for email_id, codes in ref.items() if codes.get(code) != given.get(email_id, {}).get(code))
    return facts


# ── The module's entry points ────────────────────────────────────────────────

def fixtures() -> dict[str, str]:
    """Every file the email tasks supply, by path under FIXTURE_DIR."""
    return {**calendar_fixtures(), **crosscheck_fixtures()}


def facts_for(task: dict | None, response_text: str) -> dict[str, int]:
    """The measured facts an email task adds, or nothing for any other task."""
    task_id = (task or {}).get("id")
    if task_id == CALENDAR:
        return calendar_facts(response_text)
    if task_id == AUDIT:
        return audit_facts(response_text)
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
