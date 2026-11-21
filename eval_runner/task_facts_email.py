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


# ── email-compliance-audit ───────────────────────────────────────────────────

AUDIT_BRAND = "Ostrel Botanicals"
AUDIT_FILES = ["findings.csv"]
# The policy's codes, in the order its sections give them.
CODES = ["DOMAIN", "ADDRESS", "UNSUBSCRIBE", "SUBJECT", "TRANSACTIONAL_PROMO", "CONSENT"]
ESP_INCLUDE = "include:spf.sendloop.example"
DKIM_SELECTOR = "sl1"
DMARC_POLICIES = ("quarantine", "reject")
SENDING_DOMAINS = ["mail.ostrel.example", "orders.ostrel.example", "eu.ostrel.example"]
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
DNS_SEED = 20270212

# (id, name, region, consent, double_opt_in, max_months_since_purchase)
AUDIENCES: list[tuple[str, str, str, str, str, str]] = [
    ("A01", "US newsletter sign-ups", "US", "express", "no", ""),
    ("A02", "US customers", "US", "customer", "", "22"),
    ("A03", "UK newsletter sign-ups", "UK", "express", "no", ""),
    ("A04", "UK customers", "UK", "customer", "", "30"),
    ("A05", "EU newsletter, confirmed", "EU", "express", "yes", ""),
    ("A06", "EU newsletter, unconfirmed", "EU", "express", "no", ""),
    ("A07", "EU customers", "EU", "customer", "", "14"),
    ("A08", "Canada customers", "CA", "customer", "", "24"),
    ("A09", "Canada customers, lapsed", "CA", "customer", "", "38"),
    ("A10", "Clean Beauty Expo badge scans", "US", "event", "", ""),
    ("A11", "Partner giveaway entrants", "US", "imported", "", ""),
    ("A12", "Order and account notifications", "all", "none", "", ""),
]

# Each sending domain's TXT records: (name, value). A DKIM key is drawn from
# DNS_SEED where the value says {key}.
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
    "eu.ostrel.example": [
        ("eu.ostrel.example", f"v=spf1 {ESP_INCLUDE} -all"),
        ("sl1._domainkey.eu.ostrel.example", "v=DKIM1; k=rsa; p={key}"),
        ("_dmarc.eu.ostrel.example", "v=DMARC1; p=none; sp=quarantine; rua=mailto:dmarc@ostrel.example"),
    ],
}

_STREET = ["Ostrel Botanicals Inc.", "418 Larch Street, Suite 200", "Portland, OR 97209, USA"]
_UNSUBSCRIBE = "You get this email because you signed up at ostrel.example. Unsubscribe: {{ unsubscribe_link }}"
_TRANSACTIONAL_FOOTER = ["Ostrel Botanicals Inc. · ostrel.example"]
_MAIL = "Ostrel Botanicals <hello@mail.ostrel.example>"
_EU = "Ostrel Botanicals <hallo@eu.ostrel.example>"
_ORDERS = "Ostrel Botanicals <orders@orders.ostrel.example>"


def _draft(stream, purpose, audiences, sender, subject, preheader, blocks, footer, *,
           claims=None, offer=None, reply_to="care@ostrel.example") -> dict:
    """One draft. ``claims`` is what its subject and preheader promise and
    ``offer`` what its body gives, written out for the SUBJECT rule:
    pct, up_to, scope (says sitewide/everything/all products), end (weekday),
    free_shipping_no_minimum; and pcts, limited, end, shipping_minimum."""
    return {"stream": stream, "purpose": purpose, "audiences": audiences, "from": sender, "reply_to": reply_to,
            "subject": subject, "preheader": preheader, "blocks": blocks, "footer": footer,
            "claims": claims or {}, "offer": offer or {}}


# The review queue, in order: E01 first. The planted violations and the look-alikes
# are pinned in tests/test_tasks_email.py.
DRAFTS: list[dict] = [
    _draft("marketing", "newsletter", ["A01", "A02"], _MAIL,
           "Your winter skin reset starts here", "Three routines for cold, dry days",
           [("message", "Cold air outside and dry heat inside pull moisture from skin. We asked our formulators for three "
                        "simple routines that hold up through February."),
            ("product", "Each routine uses products you may already own: Oat Milk Cleanser, Cloudberry Barrier Cream and "
                        "Rosehip Night Oil."),
            ("message", "Read the three routines on our journal.")],
           _STREET + [_UNSUBSCRIBE]),
    _draft("marketing", "promotion", ["A01", "A02"], _MAIL,
           "20% off every serum, ends Monday", "All six serums, while stocks last",
           [("offer", "Take 20% off all six of our serums until Sunday 21 February at 11:59 pm PT. No code needed."),
            ("product", "Vitamin C Brightening Serum, Niacinamide Pore Serum, Peptide Firming Serum and three more.")],
           _STREET + [_UNSUBSCRIBE],
           claims={"pct": 20, "end": "Monday"}, offer={"pcts": [20], "end": "Sunday"}),
    _draft("transactional", "order confirmation", ["A12"], _ORDERS,
           "Order 48213 confirmed", "Thanks for your order, Jamie",
           [("order", "Order 48213: Cloudberry Barrier Cream 50 ml, $46.00. Shipping $5.95. Total $51.95."),
            ("shipping", "Shipping to 22 Wren Court, Bend, OR 97701. Expected 18 to 20 February."),
            ("recommendations", "Pairs well with your cream: Oat Milk Cleanser."),
            ("support", "Questions about your order? Reply to this email.")],
           _TRANSACTIONAL_FOOTER),
    _draft("marketing", "promotion", ["A03", "A04"], _MAIL,
           "Up to 40% off selected gift sets", "Six sets, three prices, until Friday",
           [("offer", "Save 20%, 30% or 40% on selected gift sets until Friday 26 February."),
            ("product", "The Morning Set, the Night Set, the Travel Set and three more.")],
           ["Ostrel Botanicals Inc., PO Box 7721, Portland, OR 97207, USA",
            "Choose what you get from us, or unsubscribe: {{unsubscribe_link}}"],
           claims={"pct": 40, "up_to": True, "end": "Friday"}, offer={"pcts": [20, 30, 40], "limited": True, "end": "Friday"}),
    _draft("marketing", "promotion", ["A05"], _EU,
           "15% off everything until Sunday", "Our first sale of the year",
           [("offer", "15% off everything in the shop until Sunday 21 February. Excludes gift cards and the Advent "
                      "calendar."),
            ("product", "Start with our bestsellers: Oat Milk Cleanser and Rosehip Night Oil.")],
           _STREET + [_UNSUBSCRIBE], reply_to="hallo@ostrel.example",
           claims={"pct": 15, "scope": True, "end": "Sunday"}, offer={"pcts": [15], "limited": True, "end": "Sunday"}),
    _draft("transactional", "shipping notice", ["A12"], _ORDERS,
           "Your order 48190 is on its way", "Track your parcel",
           [("promo", "Spring preview: take 20% off your next order with code SPRING20."),
            ("shipping", "Order 48190 left our warehouse today. Follow it with your tracking link."),
            ("order", "Oat Milk Cleanser 150 ml, Rosehip Night Oil 30 ml.")],
           _TRANSACTIONAL_FOOTER),
    _draft("marketing", "newsletter", ["A05", "A06"], _EU,
           "What's new at Ostrel this February", "Two new products and a routine for travel",
           [("message", "Two products arrive this month, and our team shares the routine they pack for long flights."),
            ("product", "New: Cloudberry Barrier Cream and the Travel Set.")],
           _STREET + [_UNSUBSCRIBE], reply_to="hallo@ostrel.example"),
    _draft("marketing", "promotion", ["A01", "A02"], _MAIL,
           "Free shipping over $40 this weekend", "No code needed",
           [("offer", "Free standard shipping on US orders over $40, from Friday 19 to Sunday 21 February."),
            ("product", "Stock up on cleansers, creams and oils.")],
           ["Ostrel Botanicals Inc.", "418 Larch Street, Suite 120", "Portland, OR 97209, USA", _UNSUBSCRIBE],
           claims={"free_shipping_no_minimum": False}, offer={"shipping_minimum": 40, "end": "Sunday"}),
    _draft("marketing", "promotion", ["A08"], _MAIL,
           "A thank-you from Ostrel", "10% off your next order, until Sunday 28 February",
           [("message", "Thank you for shopping with us over the last two years."),
            ("offer", "Use code MERCI10 for 10% off your next order until Sunday 28 February.")],
           _STREET + [_UNSUBSCRIBE],
           claims={"pct": 10, "end": "Sunday"}, offer={"pcts": [10], "end": "Sunday"}),
    _draft("marketing", "promotion", ["A08", "A09"], _MAIL,
           "We miss you: 25% off your next order", "Your favourites are waiting",
           [("offer", "25% off your next order with code BACK25 until Sunday 28 February."),
            ("product", "Your past orders are saved in your account for quick reordering.")],
           _STREET + ["To stop receiving these emails, log in to your account at ostrel.example and change your email "
                      "settings."],
           claims={"pct": 25}, offer={"pcts": [25], "end": "Sunday"}),
    _draft("transactional", "password reset", ["A12"], _ORDERS,
           "Reset your Ostrel password", "This link works for 30 minutes",
           [("account", "Someone asked to reset the password for your account. Use the link within 30 minutes. If it "
                        "was not you, ignore this email."),
            ("recommendations", "While you are here: our three bestsellers this week.")],
           _TRANSACTIONAL_FOOTER),
    _draft("marketing", "promotion", ["A10"], _MAIL,
           "Great to meet you at the Clean Beauty Expo", "15% off your first order, until Friday",
           [("message", "Thanks for stopping by our stand in Denver."),
            ("offer", "Take 15% off your first order with code EXPO15 until Friday 26 February.")],
           _STREET + [_UNSUBSCRIBE],
           claims={"pct": 15, "end": "Friday"}, offer={"pcts": [15], "end": "Friday"}),
    _draft("marketing", "launch", ["A01"], "Ostrel Botanicals <launches@ostrel-news.example>",
           "Meet Cloudberry Barrier Cream", "Our richest moisturiser yet, in two sizes",
           [("product", "Cloudberry Barrier Cream comes in 50 ml and 100 ml, for dry and very dry skin."),
            ("message", "See how it fits into a morning and a night routine.")],
           _STREET + [_UNSUBSCRIBE]),
    _draft("marketing", "promotion", ["A02"], _MAIL,
           "30% off cleansers", "Ends Wednesday at midnight",
           [("offer", "30% off all cleansers from Monday 15 to Wednesday 17 February, ending at midnight."),
            ("product", "Oat Milk Cleanser, Green Clay Cleanser and Rose Cleansing Balm.")],
           ["Ostrel Botanicals Inc., Portland, Oregon", "Unsubscribe: {{ unsubscribe_link }}"],
           claims={"pct": 30, "end": "Wednesday"}, offer={"pcts": [30], "end": "Wednesday"}),
    _draft("transactional", "delivery confirmation", ["A12"], _ORDERS,
           "Your order 48177 was delivered", "How did we do?",
           [("shipping", "Order 48177 was delivered on 16 February."),
            ("review_request", "How did we do? Rate your order in one click."),
            ("recommendations", "Running low soon? A bottle of Rosehip Night Oil lasts about eight weeks.")],
           _TRANSACTIONAL_FOOTER),
    _draft("marketing", "promotion", ["A01", "A02"], _MAIL,
           "Double points on everything this weekend", "Every order, Friday to Sunday",
           [("offer", "Earn double loyalty points on every order from Friday 19 to Sunday 21 February."),
            ("message", "Points show in your account the day after you order.")],
           _STREET + [_UNSUBSCRIBE],
           claims={"scope": True, "end": "Sunday"}, offer={"limited": False, "end": "Sunday"}),
    _draft("marketing", "survey", ["A04"], _MAIL,
           "Two minutes to tell us about your routine?", "Five questions, no sign-in",
           [("message", "We are planning next year's products and would like to hear how you use ours."),
            ("message", "Answer five questions on one page.")],
           _STREET + ["Unsubscribe: {{ unsubscribe_url }}"]),
    _draft("marketing", "preferences", ["A03"], _MAIL,
           "Choose what you hear from us", "Pick topics, or take a break",
           [("message", "You can now choose which emails you get from us: new products, routines, or offers only.")],
           _STREET + ["Choose your emails or unsubscribe: {{ preferences_link }}"]),
]


def draft_ids() -> list[str]:
    return [f"E{number:02d}" for number in range(1, len(DRAFTS) + 1)]


def drafts() -> dict[str, dict]:
    return dict(zip(draft_ids(), DRAFTS))


def _address(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(",", " ")).strip()


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
        if not claims.get("up_to") and claims["pct"] not in pcts:
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
    """The codes the policy gives one draft."""
    codes = set()
    domain = _domain_of(draft["from"])
    if domain not in SENDING_DOMAINS or domain_failures()[domain]:
        codes.add("DOMAIN")
    marketing = draft["stream"] == "marketing"
    footer = _address(" ".join(draft["footer"]))
    if marketing and not any(_address(address) in footer for address in REGISTERED_ADDRESSES):
        codes.add("ADDRESS")
    tags = re.findall(r"\{\{\s*([a-z_]+)\s*\}\}", " ".join(draft["footer"]))
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
    """A1 drafts that pass, A2 violations, A3 drafts with more than one."""
    ref = audit_reference()
    return {
        1: sum(1 for codes in ref.values() if not codes),
        2: sum(len(codes) for codes in ref.values()),
        3: sum(1 for codes in ref.values() if len(codes) > 1),
    }


_FIXES = {
    "DOMAIN": "send it from mail.ostrel.example, which passes section 1, or fix the domain's records first",
    "ADDRESS": "put a registered postal address from section 2 in the footer",
    "UNSUBSCRIBE": "put {{ unsubscribe_link }} in the footer",
    "SUBJECT": "make the subject and preheader state the body's offer as the body states it",
    "TRANSACTIONAL_PROMO": "remove the promotional block, or keep one, without a code, after the order and shipping details",
    "CONSENT": "remove the audience whose consent does not allow marketing",
}


def audit_reference_answer() -> str:
    """A reply that follows the policy to the letter: what a checker must pass."""
    ref = audit_reference()
    out = [f"Review of the {len(ref)} drafts in the queue against the sending policy.", "",
           "### findings.csv", "```csv", "draft_id,verdict"]
    out += [f"{draft_id},{';'.join(sorted(codes)) if codes else 'pass'}" for draft_id, codes in ref.items()]
    out += ["```", "", "Fixes:", ""]
    out += [f"{draft_id} {code}: {_FIXES[code]}." for draft_id, codes in ref.items() for code in sorted(codes)]
    figures = audit_answers()
    out += ["", *[f"A{index}: {int(figures[index])}" for index in range(1, 4)], ""]
    return "\n".join(out)


def _dkim_key(rng: random.Random) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    return "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQ" + "".join(rng.choice(alphabet) for _ in range(150)) + "IDAQAB"


def dns_records_md() -> str:
    rng = random.Random(DNS_SEED)
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
    parts = [f"# {AUDIT_BRAND}: email drafts in the review queue", "",
             "Each draft as the email platform exports it. Body blocks are listed in the order they appear, each "
             "with its block type in brackets. The footer is shown line by line.", ""]
    for draft_id, draft in drafts().items():
        parts += [
            f"## {draft_id}", "",
            f"- Stream: {draft['stream']}",
            f"- Purpose: {draft['purpose']}",
            f"- Audiences: {', '.join(draft['audiences'])}",
            f"- From: {draft['from']}",
            f"- Reply-To: {draft['reply_to']}",
            f"- Subject: {draft['subject']}",
            f"- Preheader: {draft['preheader']}", "",
            "Body blocks:", "",
            *[f"{index}. [{kind}] {text}" for index, (kind, text) in enumerate(draft["blocks"], 1)], "",
            "Footer:", "",
            *[f"    {line}" for line in draft["footer"]], "",
        ]
    return "\n".join(parts)


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

Every draft is checked against this policy before it is scheduled. A draft
that breaks a rule gets that rule's code; a draft can get several codes. The
codes are {codes}.

Each draft's `Stream` is `marketing` or `transactional`, as set in the email
platform. Each rule below says which stream it applies to; a rule that names
no stream applies to both.

## 1. Sending domain (`DOMAIN`)

A draft is sent from the domain of its From address. That domain must be one
of our three sending domains, {domains}, and it must meet all three of these
in its published DNS records:

1. **SPF**: the domain has exactly one TXT record that starts with `v=spf1`.
   That record contains `{ESP_INCLUDE}` and ends with `-all` or `~all`.
2. **DKIM**: there is a TXT record at `{DKIM_SELECTOR}._domainkey.<domain>` that contains
   `v=DKIM1` and a `p=` value that is not empty.
3. **DMARC**: there is one TXT record at `_dmarc.<domain>`, and its `p=` tag is
   `quarantine` or `reject`.

A draft from any other domain, or from a domain that does not meet all three,
gets `DOMAIN`. The Reply-To address is not checked.

## 2. Postal address (`ADDRESS`)

The footer of every marketing draft contains one of our two registered postal
addresses, exactly as written here (line breaks and commas may differ):

{addresses}

A marketing draft without one gets `ADDRESS`. Transactional drafts need no
address.

## 3. Unsubscribe (`UNSUBSCRIBE`)

The footer of every marketing draft contains a working unsubscribe link: the
merge tag {tags} (the preferences page has a one-click
unsubscribe). The email platform ignores spaces inside the braces; any other
tag does not render and is not a working link. A marketing draft without a
working link gets `UNSUBSCRIBE`. Transactional drafts need no link.

## 4. Subject line and preheader (`SUBJECT`)

The subject line and the preheader state the body's offer as the body
states it. A draft gets `SUBJECT` when its subject or its preheader:

1. states a percentage off that is not the body's percentage; after "up to",
   the percentage must be the highest one the body offers;
2. says {scope} while the body limits the offer to some
   products or excludes any;
3. names a day or date the offer ends that is not the day the body's offer
   ends;
4. promises free shipping without a minimum order when the body sets one.

A subject or preheader may leave out any part of the offer.

## 5. Promotion in transactional drafts (`TRANSACTIONAL_PROMO`)

Body blocks of type {promotional} are promotional; no other
block type is.

- A transactional draft whose `Purpose` is {no_promo} has
  no promotional block.
- Any other transactional draft has at most one promotional block. It comes
  after every {after} block, and it contains no discount code.

A transactional draft that breaks either rule gets `TRANSACTIONAL_PROMO`.

## 6. Consent (`CONSENT`)

A marketing draft goes only to audiences whose consent allows marketing in
their region (`audiences.csv`):

| consent | US | UK | EU | CA |
|---|---|---|---|---|
| `express` | yes | yes | only if `double_opt_in` is `yes` | yes |
| `customer` | yes | yes | no | only if `max_months_since_purchase` is {CA_CUSTOMER_MONTHS} or less |
| `event` | no | no | no | no |
| `imported` | no | no | no | no |

A marketing draft with any audience the table does not allow gets `CONSENT`.
Transactional drafts go only to the person whose own action triggered them
and need no marketing consent.
"""


def audit_fixtures() -> dict[str, str]:
    return {
        f"{AUDIT}/sending_policy.md": sending_policy_md(),
        f"{AUDIT}/audiences.csv": audiences_csv(),
        f"{AUDIT}/dns_records.md": dns_records_md(),
        f"{AUDIT}/drafts.md": drafts_md(),
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
    """Counts of what a reply got wrong. Every count is over the queue's
    drafts, so a missing file is that many errors, never zero."""
    ref = audit_reference()
    rows = common.tables(response_text, AUDIT_FILES)["findings.csv"]
    given: dict[str, set[str]] = {}
    listed: list[str] = []
    malformed = 0
    for row in rows or []:
        draft_id = common.norm(common.cell(row, "draft_id", "draft", "id", "email_id")).upper()
        if not draft_id:
            continue
        listed.append(draft_id)
        codes, written_as_asked = _verdict(common.cell(row, "verdict", "codes", "violations"))
        given[draft_id] = codes
        malformed += draft_id in ref and not written_as_asked
    facts = {
        "audit_missing_file_count": int(rows is None),
        "audit_row_error_count": (len(set(ref) - set(listed)) + (len(listed) - len(set(listed)))
                                  + len(set(listed) - set(ref)) + malformed),
    }
    for code in CODES:
        facts[f"audit_{code.lower()}_error_count"] = sum(
            1 for draft_id, codes in ref.items() if (code in codes) != (code in given.get(draft_id, set())))
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
