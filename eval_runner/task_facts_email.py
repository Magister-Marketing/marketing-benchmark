"""Email tasks of the 35-task board, generated and graded here.

``email-send-calendar``: a month of campaigns placed on a calendar by a
written procedure. The work is applying a per-subscriber frequency cap over
300 subscribers whose segments overlap, together with blackout dates, send
days by campaign type, a teaser that must lead its launch, deadlines and a
priority order, without one slip.

``email-compliance-audit``: 18 drafts in a review queue checked against a
written sending policy, a consent table by audience and the DNS records of
the sending domains. The work is finding every planted violation, from a
fixed list of codes, without flagging the drafts that only look wrong.

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
AUDIT = "email-compliance-audit"
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
    for row in found["frequency.csv"] or []:
        sid = common.norm(common.cell(row, "subscriber_id", "subscriber", "id")).upper()
        if sid:
            seen.append(sid)
            counts[sid] = _whole(common.cell(row, "emails", "email_count", "count"))
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


# ── email-compliance-audit ───────────────────────────────────────────────────

AUDIT_BRAND = "Ostrel Botanicals"
AUDIT_FILES = ["findings.csv"]
# The policy's codes, in the order its sections give them.
CODES = ["DOMAIN", "ADDRESS", "UNSUBSCRIBE", "SUBJECT", "TRANSACTIONAL_PROMO", "CONSENT"]
ESP_INCLUDE = "include:spf.sendloop.example"
DKIM_SELECTOR = "sl1"
DMARC_POLICIES = ("quarantine", "reject")
SENDING_DOMAINS = ["mail.ostrel.example", "orders.ostrel.example", "uk.ostrel.example", "ca.ostrel.example",
                   "eu.ostrel.example", "news.ostrel.example", "promo.ostrel.example"]
REGISTERED_ADDRESSES = [
    "Ostrel Botanicals Inc., 418 Larch Street, Suite 200, Portland, OR 97209, USA",
    "Ostrel Botanicals Inc., PO Box 7721, Portland, OR 97207, USA",
]
UNSUBSCRIBE_TAGS = ("unsubscribe_link", "preferences_link")
PROMOTIONAL_BLOCKS = ("promo", "recommendations")
PLACED_AFTER = ("order", "shipping", "account")
NO_PROMOTION_PURPOSES = ("password reset", "account security")
SCOPE_WORDS = ("sitewide", "everything", "all products")
CA_CUSTOMER_MONTHS = 24
AUDIT_SEED = 20270213

# (id, name, region, consent, double_opt_in, max_months_since_purchase)
AUDIENCES: list[tuple[str, str, str, str, str, str]] = [
    ("A01", "US newsletter sign-ups", "US", "express", "no", ""),
    ("A02", "US customers", "US", "customer", "", "22"),
    ("A03", "US loyalty members", "US", "express", "yes", ""),
    ("A04", "UK newsletter sign-ups", "UK", "express", "no", ""),
    ("A05", "UK customers", "UK", "customer", "", "30"),
    ("A06", "EU newsletter, confirmed", "EU", "express", "yes", ""),
    ("A07", "EU newsletter, unconfirmed", "EU", "express", "no", ""),
    ("A08", "EU customers", "EU", "customer", "", "14"),
    ("A09", "EU loyalty members", "EU", "express", "yes", ""),
    ("A10", "Canada newsletter sign-ups", "CA", "express", "no", ""),
    ("A11", "Canada customers", "CA", "customer", "", "24"),
    ("A12", "Canada customers, lapsed", "CA", "customer", "", "38"),
    ("A13", "Canada recent customers", "CA", "customer", "", "11"),
    ("A14", "Clean Beauty Expo badge scans", "US", "event", "", ""),
    ("A15", "Partner giveaway entrants", "US", "imported", "", ""),
    ("A16", "Spa partner list", "UK", "imported", "", ""),
    ("A17", "Order and account notifications", "all", "none", "", ""),
]
TRANSACTIONAL_AUDIENCE = "A17"
# Marketing audiences by region: the ones the consent table allows, and the ones it does not.
REGION_AUDIENCES = {
    "US": (["A01", "A02", "A03"], ["A14", "A15"]),
    "UK": (["A04", "A05"], ["A16"]),
    "EU": (["A06", "A09"], ["A07", "A08"]),
    "CA": (["A10", "A11", "A13"], ["A12"]),
}

# Each sending domain's TXT records: (name, value). {key} is a DKIM key drawn from AUDIT_SEED.
DNS: dict[str, list[tuple[str, str]]] = {
    "mail.ostrel.example": [
        ("mail.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("mail.ostrel.example", "ostrel-site-verification=7Hc2kQ9pX4"),
        ("sl1._domainkey.mail.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("k1._domainkey.mail.ostrel.example", "v=DKIM1; p="),
        ("_dmarc.mail.ostrel.example", "v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example"),
    ],
    "orders.ostrel.example": [
        ("orders.ostrel.example", f"v=spf1 {ESP_INCLUDE} include:_spf.helpdeskly.example ~all"),
        ("sl1._domainkey.orders.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.orders.ostrel.example", "v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@ostrel.example"),
    ],
    "uk.ostrel.example": [
        ("uk.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.uk.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.uk.ostrel.example", "v=DMARC1; p=quarantine; pct=25; rua=mailto:dmarc@ostrel.example"),
    ],
    "ca.ostrel.example": [
        ("ca.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.ca.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.ca.ostrel.example", "v=DMARC1; p=reject; sp=none; rua=mailto:dmarc@ostrel.example"),
    ],
    "eu.ostrel.example": [
        ("eu.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.eu.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.eu.ostrel.example", "v=DMARC1; p=none; sp=quarantine; rua=mailto:dmarc@ostrel.example"),
    ],
    "news.ostrel.example": [
        ("news.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.news.ostrel.example", "v=DKIM1; p="),
        ("sl2._domainkey.news.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.news.ostrel.example", "v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example"),
    ],
    "promo.ostrel.example": [
        ("promo.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("promo.ostrel.example", "v=spf1 include:mx.oldesp.example ~all"),
        ("sl1._domainkey.promo.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.promo.ostrel.example", "v=DMARC1; p=quarantine; rua=mailto:dmarc@ostrel.example"),
    ],
}

_STREET = "Ostrel Botanicals Inc., 418 Larch Street, Suite 200, Portland, OR 97209, USA"
# Footer address -> how many marketing emails carry it. The first three are registered.
MARKETING_ADDRESSES = [
    (_STREET, 52),
    ("Ostrel Botanicals Inc. · 418 Larch Street, Suite 200 · Portland, OR 97209 · USA", 24),
    ("Ostrel Botanicals Inc., PO Box 7721, Portland, OR 97207, USA", 18),
    ("Ostrel Botanicals Inc., 418 Larch Street, Suite 120, Portland, OR 97209, USA", 4),
    ("Ostrel Botanicals Inc., 418 Larch Street, Suite 200, Portland, OR 97210, USA", 4),
    ("Ostrel Botanicals Inc., 22 Alder Street, Portland, OR 97205, USA", 3),
    ("Ostrel Botanicals Inc., Portland, Oregon", 3),
    ("", 2),
]
MARKETING_UNSUBSCRIBES = [
    ("Unsubscribe: {{ unsubscribe_link }}", 60),
    ("Unsubscribe: {{unsubscribe_link}}", 15),
    ("Choose your emails or unsubscribe: {{ preferences_link }}", 15),
    ("Unsubscribe: {{ unsubscribe_url }}", 5),
    ("Unsubscribe: {{ Unsubscribe_Link }}", 4),
    ("To unsubscribe, log in to your account at ostrel.example.", 4),
    ("To unsubscribe, reply STOP to this email.", 3),
    ("", 4),
]
# From domain -> how many emails of each stream are sent from it.
MARKETING_DOMAINS = [("mail.ostrel.example", 52), ("uk.ostrel.example", 14), ("ca.ostrel.example", 14),
                     ("eu.ostrel.example", 10), ("news.ostrel.example", 8), ("promo.ostrel.example", 4),
                     ("ostrel.example", 4), ("ostrel-mail.example", 4)]
TRANSACTIONAL_DOMAINS = [("orders.ostrel.example", 34), ("mail.ostrel.example", 3), ("ostrel.example", 3)]
DOMAIN_REGION = {"uk.ostrel.example": "UK", "ca.ostrel.example": "CA", "eu.ostrel.example": "EU"}
REGION_COUNTS = {"US": 50, "UK": 18, "EU": 22, "CA": 20}
# How many of each region's marketing emails include one audience the consent table does not allow.
REGION_BAD = {"US": 6, "UK": 3, "EU": 6, "CA": 5}
NON_OFFER_PURPOSES = [("newsletter", 22), ("survey", 8), ("event invitation", 6), ("preferences", 4), ("launch", 10)]
OFFER_PURPOSES = ["welcome offer", "abandoned cart", "win-back", "birthday", "seasonal sale"]
SHIPPING_PURPOSES = ["free shipping", "abandoned cart", "welcome offer"]
# Offer pattern -> how many promotional emails get it. The ones marked x break section 4.
OFFER_PATTERNS = [("match", 17), ("match_everything", 4), ("pct_higher", 3), ("everything_excluded", 3),
                  ("end_later", 3), ("up_to_max", 7), ("up_to_more", 3), ("shipping_minimum_stated", 8),
                  ("shipping_minimum_hidden", 4), ("shipping_free", 8)]
TRANSACTIONAL_PURPOSES = [("order confirmation", 10), ("shipping notice", 8), ("delivery confirmation", 6),
                          ("receipt", 4), ("refund confirmation", 3), ("password reset", 5), ("account security", 4)]
# Promotional-block pattern -> count, for transactional emails that are not security emails.
TRANSACTIONAL_PATTERNS = [("none", 9), ("recommendation_after", 8), ("review_then_recommendation", 4),
                          ("promo_then_support", 3), ("promo_before", 3), ("two_promotional", 2), ("promo_with_code", 2)]
SECURITY_PATTERNS = [("none", 5), ("recommendation_after", 4)]
TRANSACTIONAL_FOOTERS = [("Ostrel Botanicals Inc. · ostrel.example", 28), (_STREET, 8),
                         ("Manage your emails: {{ preferences_link }}", 4)]

_PRODUCTS = ["Oat Milk Cleanser", "Green Clay Cleanser", "Rose Cleansing Balm", "Cloudberry Barrier Cream",
             "Rosehip Night Oil", "Vitamin C Brightening Serum", "Niacinamide Pore Serum", "Peptide Firming Serum",
             "Calendula Hand Cream", "Sea Buckthorn Lip Balm", "Bamboo Exfoliating Mitt", "Mineral Day Fluid"]
_CATEGORIES = ["cleansers", "serums", "moisturisers", "body care", "gift sets", "travel sizes"]
_NEWSLETTER = [("What's new at Ostrel this month", "Two new products and a routine for travel"),
               ("Your winter skin reset starts here", "Three routines for cold, dry days"),
               ("Inside our formulation lab", "How a cream goes from idea to shelf"),
               ("Five minutes to a better routine", "Small changes our customers swear by"),
               ("The ingredient guide you asked for", "Ceramides, niacinamide and oats, explained")]
_LAUNCH = ["Our newest product, in two sizes", "Made for dry, cold days", "Now in our shop"]
_OTHER_SUBJECTS = {
    "survey": [("Two minutes to tell us about your routine?", "Five questions, no sign-in")],
    "event invitation": [("You're invited to our skincare evening", "Meet our formulators in Portland")],
    "preferences": [("Choose what you hear from us", "Pick topics, or take a break")],
}
_PREHEADERS = ["Stock up for spring", "Your favourites are waiting", "A little thank-you", "Made in small batches",
               "Picked by our team", "For dry, cold days"]


def _expand(counted: list[tuple[object, int]], rng: random.Random) -> list:
    items = [item for item, count in counted for _ in range(count)]
    rng.shuffle(items)
    return items


def _weekday(day_of_february: int) -> str:
    return WEEKDAYS[day(day_of_february).weekday()]


def _offer_email(pattern: str, rng: random.Random) -> dict:
    """The subject, preheader and offer block of a promotional email, and the
    facts the SUBJECT rule reads, for one offer pattern."""
    end = rng.randint(14, 27)
    until = f"until {_weekday(end)} {end} February"
    category = rng.choice(_CATEGORIES)
    pct = rng.choice([10, 15, 20, 25, 30])
    claims: dict = {}
    offer: dict = {"end": _weekday(end)}
    with_end = rng.random() < 0.5
    if pattern in ("match", "pct_higher", "end_later"):
        body = f"{pct}% off all {category} {until}."
        offer.update(pcts=[pct], limited=False)
        said = pct + 5 if pattern == "pct_higher" else pct
        claim = f"{said}% off {category}"
        claims["pct"] = said
        if pattern == "end_later":
            claim += f", ends {_weekday(end + 1)}"
            claims["end"] = _weekday(end + 1)
        elif with_end:
            claim += f" until {_weekday(end)}"
            claims["end"] = _weekday(end)
    elif pattern in ("match_everything", "everything_excluded"):
        word = rng.choice(["everything", "sitewide"])
        body = f"{pct}% off everything in the shop {until}."
        excluded = pattern == "everything_excluded"
        if excluded:
            body += " Excludes gift sets and gift cards."
        offer.update(pcts=[pct], limited=excluded)
        claim = f"{pct}% off {word}"
        claims.update(pct=pct, scope=True)
    elif pattern in ("up_to_max", "up_to_more"):
        low = rng.choice([10, 15, 20])
        pcts = [low, low + 10, low + 20]
        body = f"Save {pcts[0]}%, {pcts[1]}% or {pcts[2]}% on selected {category} {until}."
        offer.update(pcts=pcts, limited=True)
        said = pcts[2] + (10 if pattern == "up_to_more" else 0)
        claim = f"Up to {said}% off {category}"
        claims.update(pct=said, up_to=True)
    else:
        minimum = None if pattern == "shipping_free" else rng.choice([35, 40, 50, 60])
        offer["shipping_minimum"] = minimum
        if minimum:
            body = f"Free shipping on orders over ${minimum} {until}."
            claim = f"Free shipping over ${minimum}" if pattern == "shipping_minimum_stated" else "Free shipping this week"
        else:
            body = f"Free shipping on every order {until}."
            claim = "Free shipping on every order"
        claims["free_shipping_no_minimum"] = pattern == "shipping_minimum_hidden"
    in_preheader = rng.random() < 0.3
    neutral = rng.choice(_PREHEADERS)
    subject, preheader = (rng.choice(["A note from Ostrel", "Something for you", "This week at Ostrel"]), claim) \
        if in_preheader else (claim, neutral)
    return {"subject": subject, "preheader": preheader, "claims": claims, "offer": offer, "blocks": [("offer", body)]}


def _non_offer_email(purpose: str, rng: random.Random) -> dict:
    if purpose == "newsletter":
        subject, preheader = rng.choice(_NEWSLETTER)
        blocks = [("message", f"A routine for cold days, featuring {rng.choice(_PRODUCTS)}.")]
    elif purpose == "launch":
        product = rng.choice(_PRODUCTS)
        subject, preheader = f"New: {product}", rng.choice(_LAUNCH)
        blocks = [("product", f"Meet {product}, made for dry skin.")]
    elif purpose == "event invitation":
        subject, preheader = rng.choice(_OTHER_SUBJECTS[purpose])
        blocks = [("message", f"Join us at our Portland studio on {_weekday(25)} 25 February at 6 pm.")]
    else:
        subject, preheader = rng.choice(_OTHER_SUBJECTS[purpose])
        text = ("Five questions on how you use our products." if purpose == "survey"
                else "Choose which emails you get: products, routines or offers.")
        blocks = [("message", text)]
    return {"subject": subject, "preheader": preheader, "claims": {}, "offer": {}, "blocks": blocks}


def _transactional_blocks(purpose: str, pattern: str, rng: random.Random) -> list[tuple[str, str]]:
    order = rng.randint(48100, 48999)
    product, paired = rng.sample(_PRODUCTS, 2)
    base = {
        "order confirmation": [("order", f"Order {order}: {product}, ${rng.randint(18, 64)}.00."),
                               ("shipping", f"Expected {rng.randint(16, 20)} to {rng.randint(21, 24)} February.")],
        "shipping notice": [("shipping", f"Order {order} is on its way. Follow it with your tracking link."),
                            ("order", f"In the parcel: {product}.")],
        "delivery confirmation": [("shipping", f"Order {order} was delivered on {rng.randint(10, 20)} February.")],
        "receipt": [("order", f"Receipt for order {order}: ${rng.randint(18, 64)}.00 paid by card.")],
        "refund confirmation": [("order", f"We refunded ${rng.randint(18, 64)}.00 for order {order}.")],
        "password reset": [("account", "Use the link within 30 minutes to reset your password.")],
        "account security": [("account", f"A new device signed in to your account on {rng.randint(10, 20)} February.")],
    }[purpose]
    recommendation = ("recommendations", f"Pairs well: {paired}.")
    promo = ("promo", f"Take {rng.choice([10, 15, 20])}% off your next order.")
    support = ("support", "Questions? Reply here.")
    if pattern == "none":
        return base + [support]
    if pattern == "recommendation_after":
        return base + [recommendation]
    if pattern == "review_then_recommendation":
        return base + [("review_request", "How did we do? Rate your order in one click."), recommendation]
    if pattern == "promo_then_support":
        return base + [promo, support]
    if pattern == "promo_before":
        return [promo] + base
    if pattern == "two_promotional":
        return base + [recommendation, promo]
    code = f"{rng.choice(['SPRING', 'THANKS', 'NEXT'])}{rng.choice([10, 15, 20])}"
    return base + [("promo", f"Take 15% off your next order with code {code}.")]


def _sender(domain: str, local: str) -> str:
    return f"Ostrel Botanicals <{local}@{domain}>"


@lru_cache(maxsize=1)
def drafts() -> dict[str, dict]:
    """Every live email, by id: 110 marketing emails and 40 transactional ones,
    each built from counted features so that every trap appears several times."""
    rng = random.Random(AUDIT_SEED)
    emails: list[dict] = []
    # Marketing: a domain, then the region it implies, then audiences.
    domains = _expand(MARKETING_DOMAINS, rng)
    left = dict(REGION_COUNTS)
    for domain in DOMAIN_REGION:
        left[DOMAIN_REGION[domain]] -= sum(1 for d in domains if d == domain)
    others = _expand([(region, count) for region, count in left.items()], rng)
    regions = [DOMAIN_REGION.get(domain) or others.pop() for domain in domains]
    bad_slots: dict[str, list[bool]] = {}
    for region, count in REGION_COUNTS.items():
        slots = [True] * REGION_BAD[region] + [False] * (count - REGION_BAD[region])
        rng.shuffle(slots)
        bad_slots[region] = slots
    purposes = _expand(NON_OFFER_PURPOSES, rng) + [None] * sum(count for _p, count in OFFER_PATTERNS)
    rng.shuffle(purposes)
    offers = _expand(OFFER_PATTERNS, rng)
    addresses = _expand(MARKETING_ADDRESSES, rng)
    unsubscribes = _expand(MARKETING_UNSUBSCRIBES, rng)
    bad_first = True
    for domain, region, purpose, address, unsubscribe in zip(domains, regions, purposes, addresses, unsubscribes):
        good, bad = REGION_AUDIENCES[region]
        audiences = sorted(rng.sample(good, rng.randint(1, len(good))))
        if bad_slots[region].pop():
            # The audience the table does not allow comes first in half of these, last in the rest.
            audiences = [rng.choice(bad)] + audiences if bad_first else audiences + [rng.choice(bad)]
            bad_first = not bad_first
        if purpose is None:
            pattern = offers.pop()
            content = _offer_email(pattern, rng)
            purpose = rng.choice(SHIPPING_PURPOSES if pattern.startswith("shipping") else OFFER_PURPOSES)
        else:
            content = _non_offer_email(purpose, rng)
        local = {"newsletter": "news", "launch": "hello"}.get(purpose, "offers" if content["offer"] else "hello")
        emails.append({"stream": "marketing", "purpose": purpose, "audiences": audiences,
                       "from": _sender(domain, local), "footer": " · ".join(part for part in (address, unsubscribe) if part),
                       **content})
    # Transactional: a purpose, its promotional pattern, a domain and a footer.
    t_domains = _expand(TRANSACTIONAL_DOMAINS, rng)
    t_footers = _expand(TRANSACTIONAL_FOOTERS, rng)
    t_purposes = [p for p, count in TRANSACTIONAL_PURPOSES for _ in range(count)]
    security = [p for p in t_purposes if p in NO_PROMOTION_PURPOSES]
    deliveries = [p for p in t_purposes if p == "delivery confirmation"]
    rest = [p for p in t_purposes if p not in NO_PROMOTION_PURPOSES and p != "delivery confirmation"]
    patterns = _expand([(p, c) for p, c in TRANSACTIONAL_PATTERNS if p != "review_then_recommendation"], rng)
    review_count = dict(TRANSACTIONAL_PATTERNS)["review_then_recommendation"]
    paired = [(p, "review_then_recommendation" if index < review_count else patterns.pop())
              for index, p in enumerate(deliveries)]
    paired += [(p, patterns.pop()) for p in rest]
    paired += list(zip(security, _expand(SECURITY_PATTERNS, rng)))
    rng.shuffle(paired)
    for (purpose, pattern), domain, footer in zip(paired, t_domains, t_footers):
        subject = {"order confirmation": "Your order is confirmed", "shipping notice": "Your order is on its way",
                   "delivery confirmation": "Your order was delivered", "receipt": "Your receipt from Ostrel",
                   "refund confirmation": "Your refund is on its way", "password reset": "Reset your Ostrel password",
                   "account security": "A new sign-in to your Ostrel account"}[purpose]
        emails.append({"stream": "transactional", "purpose": purpose, "audiences": [TRANSACTIONAL_AUDIENCE],
                       "from": _sender(domain, "orders"), "subject": subject, "preheader": "Details inside",
                       "claims": {}, "offer": {}, "blocks": _transactional_blocks(purpose, pattern, rng),
                       "footer": footer})
    rng.shuffle(emails)
    return {f"E{number:03d}": email for number, email in enumerate(emails, 1)}


def draft_ids() -> list[str]:
    return list(drafts())


def _address(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(",", " ").replace("·", " ")).strip()


def _domain_of(sender: str) -> str:
    return sender.rsplit("@", 1)[-1].strip(" >").lower()


def domain_failures() -> dict[str, list[str]]:
    """Each sending domain's failed requirements under section 1 of the policy."""
    failures = {}
    for domain, records in DNS.items():
        at = lambda name: [value for record_name, value in records if record_name == name]  # noqa: E731
        failed = []
        spf = [value for value in at(domain) if value.startswith("v=spf1")]
        if len(spf) != 1 or ESP_INCLUDE not in spf[0].split() or spf[0].split()[-1] not in ("-all", "~all"):
            failed.append("spf")
        dkim = at(f"{DKIM_SELECTOR}._domainkey.{domain}")
        if not any("v=DKIM1" in value and re.search(r"\bp=[^;\s]", value) for value in dkim):
            failed.append("dkim")
        dmarc = at(f"_dmarc.{domain}")
        tags = [dict(part.strip().split("=", 1) for part in value.split(";") if "=" in part) for value in dmarc]
        if len(tags) != 1 or tags[0].get("p") not in DMARC_POLICIES:
            failed.append("dmarc")
        failures[domain] = failed
    return failures


def _subject_broken(claims: dict, offer: dict) -> bool:
    if "pct" in claims:
        pcts = offer.get("pcts", [])
        if claims.get("up_to") and claims["pct"] != max(pcts, default=None):
            return True
        if not claims.get("up_to") and pcts != [claims["pct"]]:
            return True
    if claims.get("scope") and offer.get("limited"):
        return True
    if "end" in claims and claims["end"] != offer.get("end"):
        return True
    return bool(claims.get("free_shipping_no_minimum") and offer.get("shipping_minimum"))


def _transactional_promo_broken(draft: dict) -> bool:
    kinds = [kind for kind, _text in draft["blocks"]]
    promotional = [index for index, kind in enumerate(kinds) if kind in PROMOTIONAL_BLOCKS]
    if not promotional:
        return False
    if draft["purpose"] in NO_PROMOTION_PURPOSES or len(promotional) > 1:
        return True
    last_required = max((index for index, kind in enumerate(kinds) if kind in PLACED_AFTER), default=-1)
    coded = re.search(r"\bcode [A-Z0-9]{4,}\b", draft["blocks"][promotional[0]][1])
    return promotional[0] < last_required or bool(coded)


def _consent_allows(audience_id: str) -> bool:
    _id, _name, region, consent, double_opt_in, months = next(a for a in AUDIENCES if a[0] == audience_id)
    if consent == "express":
        return region != "EU" or double_opt_in == "yes"
    if consent == "customer":
        if region == "EU":
            return False
        return region != "CA" or int(months) <= CA_CUSTOMER_MONTHS
    return False


def draft_codes(draft: dict) -> set[str]:
    """The codes the policy gives one email."""
    codes = set()
    domain = _domain_of(draft["from"])
    if domain not in SENDING_DOMAINS or domain_failures()[domain]:
        codes.add("DOMAIN")
    marketing = draft["stream"] == "marketing"
    if marketing and not any(_address(address) in _address(draft["footer"]) for address in REGISTERED_ADDRESSES):
        codes.add("ADDRESS")
    tags = re.findall(r"\{\{\s*([A-Za-z_]+)\s*\}\}", draft["footer"])
    if marketing and not set(tags) & set(UNSUBSCRIBE_TAGS):
        codes.add("UNSUBSCRIBE")
    if _subject_broken(draft["claims"], draft["offer"]):
        codes.add("SUBJECT")
    if not marketing and _transactional_promo_broken(draft):
        codes.add("TRANSACTIONAL_PROMO")
    if marketing and not all(_consent_allows(audience) for audience in draft["audiences"]):
        codes.add("CONSENT")
    return codes


@lru_cache(maxsize=1)
def audit_reference() -> dict[str, frozenset[str]]:
    return {draft_id: frozenset(draft_codes(draft)) for draft_id, draft in drafts().items()}


def audit_answers() -> dict[int, float]:
    """A1 emails that pass, A2 violations, A3 emails with more than one."""
    ref = audit_reference()
    return {
        1: sum(1 for codes in ref.values() if not codes),
        2: sum(len(codes) for codes in ref.values()),
        3: sum(1 for codes in ref.values() if len(codes) > 1),
    }


_FIXES = {
    "DOMAIN": "send from a sending domain that passes section 1, or correct the failing domain's DNS records",
    "ADDRESS": "put a registered postal address from section 2 in the footer",
    "UNSUBSCRIBE": "put {{ unsubscribe_link }} in the footer",
    "SUBJECT": "make the subject and preheader state the body's offer as the body states it",
    "TRANSACTIONAL_PROMO": "remove the promotion, or keep one block without a code after the order, shipping and account blocks",
    "CONSENT": "take the audience whose consent does not allow marketing off the email",
}


def audit_reference_answer() -> str:
    """A reply that follows the policy to the letter: what a checker must pass."""
    ref = audit_reference()
    out = [f"Audit of the {len(ref)} live emails against the sending policy.", "",
           "### findings.csv", "```csv", "email_id,verdict"]
    out += [f"{email_id},{';'.join(sorted(codes)) if codes else 'pass'}" for email_id, codes in ref.items()]
    out += ["```", "", "Fixes:", ""]
    out += [f"- {code}: {_FIXES[code]}." for code in CODES]
    figures = audit_answers()
    out += ["", *[f"A{index}: {int(figures[index])}" for index in range(1, 4)], ""]
    return "\n".join(out)


def _dkim_key(rng: random.Random) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    return "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQ" + "".join(rng.choice(alphabet) for _ in range(40)) + "IDAQAB"


def dns_records_md() -> str:
    rng = random.Random(AUDIT_SEED)
    parts = [f"# {AUDIT_BRAND}: DNS records of the sending domains", "",
             "Exported from the DNS host on 12 February 2027. Every TXT record at or under each sending domain is "
             "listed.", ""]
    for domain, records in DNS.items():
        parts += [f"## {domain}", "", "| Name | Type | Value |", "|---|---|---|"]
        parts += [f"| {name} | TXT | {value.replace('{key}', _dkim_key(rng))} |" for name, value in records]
        parts.append("")
    return "\n".join(parts)


def audiences_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["audience_id", "name", "region", "consent", "double_opt_in", "max_months_since_purchase"])
    writer.writerows(AUDIENCES)
    return out.getvalue()


def drafts_md() -> str:
    parts = [f"# {AUDIT_BRAND}: every live email", "",
             "Exported from the email platform before the move: every step of every automated flow and every "
             "scheduled campaign. The first line of each email gives its stream, its purpose, its audiences and its "
             "From address, in that order. Body blocks are listed in order, each with its block type in brackets and separated by "
             "` | `. The footer is shown on one line, its parts separated by ` · `.", ""]
    for email_id, draft in drafts().items():
        parts += [
            f"## {email_id}",
            f"{draft['stream']} · {draft['purpose']} · {', '.join(draft['audiences'])} · {_domain_address(draft['from'])}",
            f"Subject: {draft['subject']}",
            f"Preheader: {draft['preheader']}",
            "Body: " + " | ".join(f"[{kind}] {text}" for kind, text in draft["blocks"]),
            f"Footer: {draft['footer']}", "",
        ]
    return "\n".join(parts)


def _domain_address(sender: str) -> str:
    return sender.rsplit("<", 1)[-1].rstrip(">")


def sending_policy_md() -> str:
    domains = ", ".join(f"`{domain}`" for domain in SENDING_DOMAINS)
    addresses = "\n".join(f"- {address}" for address in REGISTERED_ADDRESSES)
    tags = " or ".join(f"`{{{{ {tag} }}}}`" for tag in UNSUBSCRIBE_TAGS)
    promotional = " and ".join(f"`{kind}`" for kind in PROMOTIONAL_BLOCKS)
    after = ", ".join(f"`{kind}`" for kind in PLACED_AFTER[:-1]) + f" and `{PLACED_AFTER[-1]}`"
    no_promo = " or ".join(f"`{purpose}`" for purpose in NO_PROMOTION_PURPOSES)
    scope = ", ".join(f"\"{word}\"" for word in SCOPE_WORDS[:-1]) + f" or \"{SCOPE_WORDS[-1]}\""
    codes = ", ".join(f"`{code}`" for code in CODES)
    return f"""# {AUDIT_BRAND}: email sending policy

Before we move to the new email platform, every live email is checked
against this policy. An email that breaks a rule gets that rule's code; an
email can get several codes. The codes are {codes}.

Each email's stream is `marketing` or `transactional`, as set in the email
platform. Each rule below says which stream it applies to; a rule that names
no stream applies to both.

## 1. Sending domain (`DOMAIN`)

An email is sent from the domain of its From address. That domain must be
one of our sending domains, {domains}, and it must meet all three of these in
its published DNS records:

1. **SPF**: the domain has exactly one TXT record that starts with `v=spf1`.
   That record contains `{ESP_INCLUDE}` and ends with `-all` or `~all`.
2. **DKIM**: there is a TXT record at `{DKIM_SELECTOR}._domainkey.<domain>` that contains
   `v=DKIM1` and a `p=` value that is not empty.
3. **DMARC**: there is one TXT record at `_dmarc.<domain>`, and its `p=` tag is
   `quarantine` or `reject`.

An email from any other domain, or from a domain that does not meet all
three, gets `DOMAIN`.

## 2. Postal address (`ADDRESS`)

The footer of every marketing email contains one of our two registered postal
addresses, exactly as written here; only line breaks, commas and the `·`
separator may differ:

{addresses}

A marketing email without one gets `ADDRESS`. Transactional emails need no
address.

## 3. Unsubscribe (`UNSUBSCRIBE`)

The footer of every marketing email contains a working unsubscribe link: the
merge tag {tags} (the preferences page has a one-click
unsubscribe). The email platform ignores spaces inside the braces. Any other
difference, capital letters included, is a tag that does not render and is
not a working link. A marketing email without a working link gets
`UNSUBSCRIBE`. Transactional emails need no link.

## 4. Subject line and preheader (`SUBJECT`)

The subject line and the preheader state the body's offer as the body
states it. An email gets `SUBJECT` when its subject or its preheader:

1. states a percentage off that is not the body's percentage; after "up to",
   the percentage must be the highest one the body offers;
2. says {scope} while the body limits the offer to some
   products or excludes any;
3. names a day or date the offer ends that is not the day the body's offer
   ends;
4. promises free shipping without a minimum order when the body sets one.

A subject or preheader may leave out any part of the offer.

## 5. Promotion in transactional emails (`TRANSACTIONAL_PROMO`)

Body blocks of type {promotional} are promotional; no other
block type is.

- A transactional email whose purpose is {no_promo} has
  no promotional block.
- Any other transactional email has at most one promotional block. It comes
  after every {after} block, and it contains no discount code.

A transactional email that breaks either rule gets `TRANSACTIONAL_PROMO`.

## 6. Consent (`CONSENT`)

A marketing email goes only to audiences whose consent allows marketing in
their region (`audiences.csv`):

| consent | US | UK | EU | CA |
|---|---|---|---|---|
| `express` | yes | yes | only if `double_opt_in` is `yes` | yes |
| `customer` | yes | yes | no | only if `max_months_since_purchase` is {CA_CUSTOMER_MONTHS} or less |
| `event` | no | no | no | no |
| `imported` | no | no | no | no |

A marketing email with any audience the table does not allow gets `CONSENT`.
Transactional emails go only to the person whose own action triggered them
and need no marketing consent.
"""


def audit_fixtures() -> dict[str, str]:
    return {
        f"{AUDIT}/sending_policy.md": sending_policy_md(),
        f"{AUDIT}/audiences.csv": audiences_csv(),
        f"{AUDIT}/dns_records.md": dns_records_md(),
        f"{AUDIT}/emails.md": drafts_md(),
    }


def _verdict(text: object) -> tuple[set[str], bool]:
    """The codes a verdict cell gives, and whether it is written as asked:
    `pass` alone, or one or more of the policy's codes."""
    value = re.sub(r"TRANSACTIONAL[\s-]+PROMO", "TRANSACTIONAL_PROMO", str(text or "").strip().strip("`\"'").upper())
    tokens = [token for token in re.split(r"[\s;,/|+&]+", value) if token]
    codes = {token for token in tokens if token in CODES}
    if tokens == ["PASS"]:
        return set(), True
    return codes, bool(tokens) and all(token in CODES for token in tokens)


def audit_facts(response_text: str) -> dict[str, int]:
    """Counts of what a reply got wrong. Every count is over the export's
    emails, so a missing file is that many errors, never zero."""
    ref = audit_reference()
    rows = common.tables(response_text, AUDIT_FILES)["findings.csv"]
    given: dict[str, set[str]] = {}
    listed: list[str] = []
    malformed = 0
    for row in rows or []:
        email_id = common.norm(common.cell(row, "email_id", "email", "id", "draft_id")).upper()
        if not email_id:
            continue
        listed.append(email_id)
        codes, written_as_asked = _verdict(common.cell(row, "verdict", "codes", "violations"))
        given[email_id] = codes
        malformed += email_id in ref and not written_as_asked
    facts = {
        "audit_missing_file_count": int(rows is None),
        "audit_row_error_count": (len(set(ref) - set(listed)) + (len(listed) - len(set(listed)))
                                  + len(set(listed) - set(ref)) + malformed),
    }
    for code in CODES:
        facts[f"audit_{code.lower()}_error_count"] = sum(
            1 for email_id, codes in ref.items() if (code in codes) != (code in given.get(email_id, set())))
    return facts


# ── The module's entry points ────────────────────────────────────────────────

def fixtures() -> dict[str, str]:
    """Every file the email tasks supply, by path under FIXTURE_DIR."""
    return {**calendar_fixtures(), **audit_fixtures()}


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
