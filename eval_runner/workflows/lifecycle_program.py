"""Workflow task: build a lifecycle email programme from a customer export.

The brief is the policy a lifecycle lead would hand over: who may not be
emailed and why, which segment everyone else is in, who is held out to measure
the programme, the flow each segment gets, when each step lands by the
customer's own clock, and what a subject line may say. The work is applying it
to every customer of an export without one slip, writing some fifty short
lines of copy inside hard limits, and keeping five files in agreement: the same
people, the same segments, the same counts.

Everything here is derived from the constants below: the policy the candidate
reads, the customer export, the reference answer and the checker. A rule
cannot say one thing in the brief and another in the grader.

All brands, people and figures are invented. Customers are ids only.
"""
from __future__ import annotations

import csv
import io
import random
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

TASK_ID = "lifecycle-program"
FIXTURE_DIR = Path("eval_runner") / "fixtures" / "lifecycle-program"
FILES = ["suppressed.csv", "segments.csv", "holdout.csv", "flow.csv", "schedule.csv"]

BRAND = "Wrenlow Tea Club"
# The day the policy calls today. Nothing here reads the real date.
TODAY = date(2026, 10, 1)

# ── Suppression: reasons in the order they apply; the first is the reason ────
STALE_CONSENT_COUNTRIES = ("DE", "FR", "NL")
STALE_CONSENT_DAYS = 730
DORMANT_SIGNUP_DAYS = 365
REASONS = ["complaint", "unsubscribed", "hard_bounce", "no_consent", "stale_consent", "dormant_signup"]

# ── Segments: in the order they claim a customer who is not suppressed ───────
NEW_DAYS = 30
LAPSED_DAYS = 180
AT_RISK_DAYS = 90
VIP_ORDERS = 8
VIP_VALUE = 600
SEGMENTS = ["new", "prospect", "lapsed", "vip", "at_risk", "active"]

# ── Holdout ──────────────────────────────────────────────────────────────────
HOLDOUT_SEGMENTS = ("lapsed", "at_risk", "prospect")
HOLDOUT_DIVISOR = 7

# ── Flows: segment -> (emails, day of the first, day of the last) ────────────
FLOWS: dict[str, tuple[int, int, int]] = {
    "new": (5, 0, 21),
    "prospect": (4, 1, 14),
    "lapsed": (5, 0, 30),
    "vip": (3, 0, 10),
    "at_risk": (4, 0, 12),
    "active": (3, 3, 17),
}
MIN_GAP_DAYS = 4
# The only offers, each on the last email of its segment's flow:
# segment -> (code, the words the email states it in, the percentage).
OFFERS: dict[str, tuple[str, str, int]] = {
    "prospect": ("FIRST10", "10% off your first order", 10),
    "lapsed": ("BACK15", "15% off your next order", 15),
}
GIFT_PLAN = "G"
GIFT_CAP = 2
PLANS = {"M": "monthly", "Q": "quarterly", GIFT_PLAN: "a gift plan someone else pays for"}

# ── Send times ───────────────────────────────────────────────────────────────
RELEASE_UTC = {"new": "14:30", "prospect": "16:00", "lapsed": "18:30", "vip": "12:00", "at_risk": "17:00", "active": "13:30"}
OFFER_RELEASE_UTC = "20:00"
UTC_OFFSET_MINUTES = {"PT": -480, "MT": -420, "CT": -360, "ET": -300, "GMT": 0, "CET": 60, "IST": 330, "AEST": 600}
QUIET_FROM = "21:00"
QUIET_UNTIL = "07:59"
QUIET_RESUME = "08:00"

# ── Copy ─────────────────────────────────────────────────────────────────────
SUBJECT_MAX = 50
PREHEADER_MAX = 90
SEGMENT_PHRASE = {
    "new": "welcome",
    "prospect": "first tin",
    "lapsed": "come back",
    "vip": "Reserve List",
    "at_risk": "next tin",
    "active": "this month",
}
FORBIDDEN_WORDS = ["free", "guarantee", "guaranteed", "urgent", "last chance", "act now", "cheap"]
FORBIDDEN_MARK = "!"

# The flows of the reference answer: segment -> [(day, subject, preheader)].
REFERENCE_FLOW: dict[str, list[tuple[int, str, str]]] = {
    "new": [
        (0, "Welcome to Wrenlow Tea Club",
         "Your first tin is being packed. Here is what happens between now and your doorstep."),
        (4, "How to brew your first tin properly",
         "A welcome guide: water temperature, leaf to cup, and the timer most people skip."),
        (9, "Meet the growers behind your tea",
         "Part of your welcome: the three estates we buy from, and why we visit every spring."),
        (15, "Make the club yours: set a taste profile",
         "Welcome aboard. Say black, green or herbal and the tin after this one follows suit."),
        (21, "Three weeks in: how is the tea?",
         "Your welcome weeks are nearly done. Swap, skip or pause a tin from your account."),
    ],
    "prospect": [
        (1, "Your first tin is one choice away",
         "You joined the list and have not picked a tea yet. Start with the taster of three."),
        (5, "Not sure which tea? Take the two-minute quiz",
         "Answer five questions and we suggest a first tin that fits how you drink tea."),
        (9, "What members said after their opening order",
         "Short notes from people who began where you are, on how their first tin surprised them."),
        (14, "10% off your first order, when you are ready",
         "Enter the code at checkout and your first tin is in the post within two days."),
    ],
    "lapsed": [
        (0, "It has been a while. Come back for a cup?",
         "Much has changed since your last order: new estates, lighter tins, flexible dates."),
        (7, "What is new at Wrenlow since you left",
         "Six teas you have not tried, and three reasons members come back after a break."),
        (14, "Order one tin, with no subscription",
         "Come back on your own terms: a single tin whenever the shelf runs low, nothing monthly."),
        (22, "The autumn harvest is in",
         "If you were waiting for a reason to come back, the second-flush Assam is a good one."),
        (30, "A thank-you for returning: 15% off",
         "Come back with 15% off your next order. The code works on any tin, once."),
    ],
    "vip": [
        (0, "You are on the Reserve List",
         "Our thanks for years of orders: first pick of small lots before the shop sees them."),
        (5, "Reserve List preview: 40 tins of Silver Needle",
         "A lot too small for the shop. Reserve List members can claim a tin for two days."),
        (10, "Help choose the teas we buy in spring",
         "Reserve List members vote on the three estates we visit. Voting takes a minute."),
    ],
    "at_risk": [
        (0, "Your next tin is on hold. Still want it?",
         "We noticed a gap in your orders, so nothing ships until you tell us to carry on."),
        (4, "Change what comes in your next tin",
         "If the last teas missed, switch your taste profile and the selection follows it."),
        (8, "Skip a month without leaving the club",
         "Delay your next tin by four or eight weeks from your account. Nothing is charged."),
        (12, "Should we keep your place in the club?",
         "One tap keeps your next tin scheduled. No reply, and we pause deliveries, never cancel."),
    ],
    "active": [
        (3, "This month in your tin: smoked Lapsang",
         "Brewing notes and a food pairing for the tea on its way to you. Best at 95 degrees."),
        (10, "Add a second tea to your parcel",
         "Members can add any tin to this month's post and pay for delivery only once."),
        (17, "Tell us how the Lapsang went",
         "Rate this month's tin in two taps and the one after leans toward what you liked."),
    ],
}


# ── The rules, applied ────────────────────────────────────────────────────────

def days_before_today(day: date) -> int:
    return (TODAY - day).days


def suppression_reason(customer: dict) -> str | None:
    """The first reason that applies, or None for a customer who may be emailed."""
    if customer["complained"]:
        return "complaint"
    if customer["unsubscribed"]:
        return "unsubscribed"
    if customer["hard_bounced"]:
        return "hard_bounce"
    if not customer["consent"]:
        return "no_consent"
    if (customer["country"] in STALE_CONSENT_COUNTRIES
            and days_before_today(customer["consent_date"]) > STALE_CONSENT_DAYS):
        return "stale_consent"
    if customer["orders"] == 0 and days_before_today(customer["signup_date"]) > DORMANT_SIGNUP_DAYS:
        return "dormant_signup"
    return None


def segment_of(customer: dict) -> str:
    """The segment of a customer who is not suppressed: the first whose test they meet."""
    if days_before_today(customer["signup_date"]) <= NEW_DAYS:
        return "new"
    if customer["orders"] == 0:
        return "prospect"
    since_order = days_before_today(customer["last_order_date"])
    if since_order > LAPSED_DAYS:
        return "lapsed"
    if customer["orders"] >= VIP_ORDERS and customer["lifetime_value"] >= VIP_VALUE:
        return "vip"
    if since_order > AT_RISK_DAYS:
        return "at_risk"
    return "active"


def id_number(customer_id: str) -> int:
    return int(customer_id[1:])


def held_out(customer_id: str, segment: str) -> bool:
    return segment in HOLDOUT_SEGMENTS and id_number(customer_id) % HOLDOUT_DIVISOR == 0


def steps_received(segment: str, plan: str) -> int:
    emails = FLOWS[segment][0]
    return min(emails, GIFT_CAP) if plan == GIFT_PLAN else emails


def offer_code(segment: str, step: int) -> str:
    """The code a step carries: its segment's, on the last email, else none."""
    return OFFERS[segment][0] if segment in OFFERS and step == FLOWS[segment][0] else ""


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def local_send_time(segment: str, step: int, timezone: str) -> str:
    released = OFFER_RELEASE_UTC if offer_code(segment, step) else RELEASE_UTC[segment]
    local = (_minutes(released) + UTC_OFFSET_MINUTES[timezone]) % (24 * 60)
    if local >= _minutes(QUIET_FROM) or local <= _minutes(QUIET_UNTIL):
        return QUIET_RESUME
    return f"{local // 60:02d}:{local % 60:02d}"


# ── The customer export ───────────────────────────────────────────────────────

_COLUMNS = ["customer_id", "country", "timezone", "consent", "consent_date", "unsubscribed", "hard_bounced",
            "complained", "signup_date", "last_order_date", "orders", "lifetime_value", "plan"]
_CUSTOMER_COUNT = 300


def _customer(number: int, country: str, timezone: str, signup: int, orders: int = 0, value: int = 0,
              last: int | None = None, consent: int | bool | None = None, flags: str = "", plan: str = "M") -> dict:
    """A customer, with every date given as days before today. `consent` is the
    age of the consent in days, None for "given at signup", False for none.
    `flags`: c complained, u unsubscribed, b hard bounced."""
    return {
        "customer_id": f"C{number}",
        "country": country,
        "timezone": timezone,
        "consent": consent is not False,
        "consent_date": None if consent is False else TODAY - timedelta(days=signup if consent is None else consent),
        "unsubscribed": "u" in flags,
        "hard_bounced": "b" in flags,
        "complained": "c" in flags,
        "signup_date": TODAY - timedelta(days=signup),
        "last_order_date": None if last is None else TODAY - timedelta(days=last),
        "orders": orders,
        "lifetime_value": value,
        "plan": plan,
    }


# Customers written by hand because a rule's edge is the point of them. Each is
# pinned in tests/test_workflow_lifecycle_program.py. Everyone in IST and AEST
# is here, so which steps those two timezones receive is decided on purpose.
def _planted() -> list[dict]:
    c = _customer
    return [
        # Suppression: the first reason that applies, and where each stops.
        c(118, "US", "ET", 700, 4, 180, 60, flags="cu"),                 # two reasons: complaint comes first
        c(203, "US", "CT", 900, 3, 120, 300, consent=False, flags="b"),  # two reasons: hard_bounce; 203 = 7 x 29
        c(326, "DE", "CET", 900, 5, 240, 30, flags="u"),                 # unsubscribed before stale consent
        c(431, "FR", "CET", 800, 6, 310, 25, consent=731),               # consent one day too old
        c(432, "NL", "CET", 800, 6, 305, 25, consent=730),               # exactly 730 days: still good
        c(519, "US", "PT", 1600, 20, 1480, 35),                          # old consent, a country it never stales in
        c(523, "GB", "GMT", 1200, 4, 170, 120),                          # the same in GB
        c(644, "DE", "CET", 1000),                                       # stale consent before dormant signup
        c(707, "US", "MT", 366),                                         # never ordered, 366 days: dormant_signup
        c(708, "US", "MT", 365),                                         # 365 days exactly: a prospect
        c(812, "CA", "ET", 364),                                         # a prospect, and 812 = 7 x 116: held out
        c(255, "US", "CT", 500, consent=False),                          # no consent before dormant signup
        c(377, "GB", "GMT", 640, 2, 75, 400, consent=False, flags="cb"),  # three reasons: complaint
        # Segments: the order decides, and each boundary day.
        c(140, "US", "ET", 30),                                          # 30 days: new, not prospect; 140 = 7 x 20
        c(146, "US", "ET", 31),                                          # 31 days, no orders: prospect
        c(149, "CA", "PT", 31, 1, 36, 20),                               # 31 days, one order: active
        c(152, "GB", "GMT", 12, 2, 80, 2),                               # new, with orders
        c(560, "US", "CT", 1500, 14, 1250, 200),                         # VIP numbers, lapsed; 560 = 7 x 80: held out
        c(571, "US", "ET", 1300, 11, 940, 150),                          # VIP numbers at at-risk dates: vip
        c(577, "GB", "GMT", 420, 8, 600, 40),                            # 8 orders and $600 exactly: vip
        c(583, "US", "PT", 430, 8, 599, 40),                             # $599: not vip
        c(589, "US", "CT", 800, 7, 1100, 120),                           # 7 orders: not vip, at_risk
        c(593, "CA", "ET", 700, 3, 130, 180),                            # last order 180 days: at_risk
        c(596, "US", "ET", 700, 3, 128, 181),                            # 181 days: lapsed
        c(602, "US", "PT", 300, 2, 96, 90),                              # 90 days: active; 602 = 7 x 86, not held out
        c(605, "US", "MT", 300, 2, 92, 91),                              # 91 days: at_risk
        c(611, "DE", "CET", 1400, 16, 1320, 180, consent=100),           # VIP numbers, 180 days: vip
        c(617, "FR", "CET", 1400, 16, 1290, 181, consent=90),            # VIP numbers, 181 days: lapsed
        # Holdout: only three segments, only ids divisible by 7.
        c(630, "US", "ET", 900, 12, 1010, 100),                          # vip and 630 = 7 x 90: not held out
        c(735, "US", "CT", 500, 3, 140, 130),                            # at_risk and 735 = 7 x 105: held out
        c(917, "GB", "GMT", 1000, 5, 220, 400),                          # lapsed and 917 = 7 x 131: held out
        c(923, "GB", "GMT", 1000, 5, 215, 410),                          # lapsed, 923 is not divisible by 7
        c(791, "NL", "CET", 200),                                        # prospect and 791 = 7 x 113: held out
        # IST: a half-hour offset, and segments with one member each.
        c(154, "IN", "IST", 600, 4, 190, 140),                           # the only at_risk; 154 = 7 x 22: held out
        c(158, "IN", "IST", 18, 1, 34, 10),                              # new: 14:30 UTC is 20:00, not quiet
        c(272, "IN", "IST", 1100, 15, 1120, 22, plan="G"),               # the only vip, on a gift plan: steps 1-2
        c(344, "IN", "IST", 900, 6, 260, 320, plan="Q"),                 # lapsed: every step lands in quiet hours
        c(415, "IN", "IST", 250, 3, 118, 14),                            # active
        c(473, "IN", "IST", 700, 2, 77, 500, flags="u"),                 # unsubscribed
        c(586, "IN", "IST", 120),                                        # prospect
        # AEST: ten hours ahead, so every release lands in quiet hours.
        c(161, "AU", "AEST", 90),                                        # the only prospect; 161 = 7 x 23: held out
        c(226, "AU", "AEST", 9, 1, 31, 5, plan="G"),                     # the only new, on a gift plan: steps 1-2
        c(298, "AU", "AEST", 400, 5, 230, 30, plan="Q"),                 # active
        c(364, "AU", "AEST", 1200, 4, 160, 250),                         # lapsed; 364 = 7 x 52: held out
        c(369, "AU", "AEST", 1250, 7, 330, 330, plan="G"),               # lapsed, gift: steps 1-2, never the offer
        c(452, "AU", "AEST", 1500, 22, 1640, 60),                        # vip
        c(537, "AU", "AEST", 640, 2, 88, 100),                           # at_risk
        c(612, "AU", "AEST", 300, 1, 40, 200, consent=False),            # no consent
    ]


_COUNTRIES = [("US", 50), ("CA", 10), ("GB", 16), ("DE", 11), ("FR", 8), ("NL", 5)]
_TIMEZONES = {
    "US": [("PT", 22), ("MT", 10), ("CT", 26), ("ET", 42)],
    "CA": [("PT", 25), ("MT", 15), ("CT", 10), ("ET", 50)],
    "GB": [("GMT", 1)], "DE": [("CET", 1)], "FR": [("CET", 1)], "NL": [("CET", 1)],
}
_KINDS = [("new", 9), ("prospect", 12), ("lapsed", 17), ("vip", 10), ("near_vip", 5), ("at_risk", 15), ("active", 32)]


def _pick(rng: random.Random, weighted: list[tuple[str, int]]) -> str:
    return rng.choices([name for name, _weight in weighted], weights=[weight for _name, weight in weighted])[0]


def _drawn(rng: random.Random, number: int) -> dict:
    """A customer drawn at random. The kind only shapes the figures: the rules
    above decide what the customer is."""
    country = _pick(rng, _COUNTRIES)
    kind = _pick(rng, _KINDS)
    orders = value = 0
    last: int | None = None
    if kind == "new":
        signup = rng.randint(0, NEW_DAYS)
        orders = rng.choice([0, 0, 1, 1, 1, 2])
        last = rng.randint(0, signup) if orders else None
        value = orders * rng.randint(22, 48)
    elif kind == "prospect":
        signup = rng.randint(NEW_DAYS + 1, DORMANT_SIGNUP_DAYS) if rng.random() < 0.8 else rng.randint(
            DORMANT_SIGNUP_DAYS + 1, 720)
    else:
        if kind == "lapsed":
            last, orders = rng.randint(LAPSED_DAYS + 1, 900), rng.randint(1, 12)
        elif kind == "vip":
            last, orders = rng.randint(0, LAPSED_DAYS), rng.randint(VIP_ORDERS, 30)
        elif kind == "near_vip":
            last, orders = rng.randint(0, LAPSED_DAYS), rng.randint(5, 14)
        elif kind == "at_risk":
            last, orders = rng.randint(AT_RISK_DAYS + 1, LAPSED_DAYS), rng.randint(1, 7)
        else:
            last, orders = rng.randint(0, AT_RISK_DAYS), rng.randint(1, 7)
        value = orders * rng.randint(24, 68)
        if kind == "vip":
            value = max(VIP_VALUE + rng.randint(0, 40), orders * rng.randint(40, 85))
        elif kind == "near_vip":
            # One of the two tests met and the other just missed.
            value = rng.randint(420, VIP_VALUE - 1) if orders >= VIP_ORDERS else rng.randint(VIP_VALUE, 980)
        signup = min(2500, last + orders * 30 + rng.randint(5, 700))
    renewed = rng.random() < (0.6 if country in STALE_CONSENT_COUNTRIES and signup > STALE_CONSENT_DAYS else 0.3)
    consent: int | bool | None = False if rng.random() < 0.05 else rng.randint(0, signup) if renewed else None
    flags = "".join(flag for flag, chance in (("c", 0.03), ("u", 0.15 if kind == "lapsed" else 0.08), ("b", 0.045))
                    if rng.random() < chance)
    return _customer(number, country, _pick(rng, _TIMEZONES[country]), signup, orders, value, last, consent, flags,
                     _pick(rng, [("M", 60), ("Q", 28), (GIFT_PLAN, 12)]))


@lru_cache(maxsize=1)
def customers() -> list[dict]:
    """The export, the same every time: every customer once, in id order."""
    rng = random.Random(20261001)
    planted = _planted()
    taken = {id_number(customer["customer_id"]) for customer in planted}
    numbers = rng.sample([number for number in range(100, 1000) if number not in taken], _CUSTOMER_COUNT - len(planted))
    return sorted(planted + [_drawn(rng, number) for number in numbers],
                  key=lambda customer: id_number(customer["customer_id"]))


def _flag(value: bool) -> str:
    return "y" if value else "n"


def export_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(_COLUMNS)
    for customer in customers():
        writer.writerow([
            customer["customer_id"], customer["country"], customer["timezone"], _flag(customer["consent"]),
            customer["consent_date"].isoformat() if customer["consent_date"] else "",
            _flag(customer["unsubscribed"]), _flag(customer["hard_bounced"]), _flag(customer["complained"]),
            customer["signup_date"].isoformat(),
            customer["last_order_date"].isoformat() if customer["last_order_date"] else "",
            customer["orders"], customer["lifetime_value"], customer["plan"],
        ])
    return out.getvalue()


# ── The reference: what the policy produces from the export ──────────────────

@lru_cache(maxsize=1)
def reference() -> dict:
    suppressed: dict[str, str] = {}
    segments: dict[str, str] = {}
    holdout: list[str] = []
    schedule: dict[tuple[str, int, str], str] = {}
    emails = 0
    for customer in customers():
        customer_id = customer["customer_id"]
        reason = suppression_reason(customer)
        if reason:
            suppressed[customer_id] = reason
            continue
        segment = segments[customer_id] = segment_of(customer)
        if held_out(customer_id, segment):
            holdout.append(customer_id)
            continue
        received = steps_received(segment, customer["plan"])
        emails += received
        for step in range(1, received + 1):
            schedule[(segment, step, customer["timezone"])] = local_send_time(segment, step, customer["timezone"])
    return {"suppressed": suppressed, "segments": segments, "holdout": holdout, "schedule": schedule, "emails": emails}


def flow_keys() -> list[tuple[str, int]]:
    """Every email of the programme: (segment, step)."""
    return [(segment, step) for segment in SEGMENTS for step in range(1, FLOWS[segment][0] + 1)]


def answers() -> dict[int, float]:
    """A1 customers suppressed, A2 customers in the holdout, A3 emails in the first full run."""
    ref = reference()
    return {1: len(ref["suppressed"]), 2: len(ref["holdout"]), 3: ref["emails"]}


def reference_answer() -> str:
    """A reply that follows the policy to the letter: what a checker must pass."""
    ref = reference()
    out = [f"Lifecycle email programme for {BRAND}, from the customer export and the lifecycle policy.", ""]

    def block(name: str, header: list[str], rows: list[list]) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        out.extend([f"### {name}", "```csv", buffer.getvalue().rstrip("\n"), "```", ""])

    block("suppressed.csv", ["customer_id", "reason"], [[k, reason] for k, reason in ref["suppressed"].items()])
    block("segments.csv", ["customer_id", "segment"], [[k, segment] for k, segment in ref["segments"].items()])
    block("holdout.csv", ["customer_id"], [[k] for k in ref["holdout"]])
    block("flow.csv", ["segment", "step", "day", "subject", "preheader", "offer_code"], [
        [segment, step, day, subject, preheader, offer_code(segment, step)]
        for segment in SEGMENTS for step, (day, subject, preheader) in enumerate(REFERENCE_FLOW[segment], 1)])
    order = {segment: index for index, segment in enumerate(SEGMENTS)}
    zones = {timezone: index for index, timezone in enumerate(UTC_OFFSET_MINUTES)}
    block("schedule.csv", ["segment", "step", "timezone", "local_send_time"], [
        [segment, step, timezone, clock] for (segment, step, timezone), clock in sorted(
            ref["schedule"].items(), key=lambda item: (order[item[0][0]], item[0][1], zones[item[0][2]]))])
    figures = answers()
    out += [f"A1: {int(figures[1])}", f"A2: {int(figures[2])}", f"A3: {int(figures[3])}", ""]
    return "\n".join(out)


# ── The documents the candidate reads ────────────────────────────────────────

def _quoted(terms) -> str:
    return ", ".join(f"`{term}`" for term in terms)


def _offset(minutes: int) -> str:
    sign = "-" if minutes < 0 else "+" if minutes > 0 else ""
    return f"{sign}{abs(minutes) // 60}:{abs(minutes) % 60:02d}"


def lifecycle_policy_md() -> str:
    plans = ", ".join(f"`{code}` ({meaning})" for code, meaning in PLANS.items())
    stale = " or ".join([", ".join(STALE_CONSENT_COUNTRIES[:-1]), STALE_CONSENT_COUNTRIES[-1]])
    held = " and ".join([", ".join(f"`{name}`" for name in HOLDOUT_SEGMENTS[:-1]), f"`{HOLDOUT_SEGMENTS[-1]}`"])
    never_held = [name for name in SEGMENTS if name not in HOLDOUT_SEGMENTS]
    not_held = " or ".join([", ".join(f"`{name}`" for name in never_held[:-1]), f"`{never_held[-1]}`"])
    flows = "\n".join(
        f"| `{segment}` | {emails} | day {first} | day {last} | "
        + (f"`{OFFERS[segment][0]}` on the last email" if segment in OFFERS else "none") + " |"
        for segment, (emails, first, last) in FLOWS.items())
    releases = "\n".join(f"| `{segment}` | {RELEASE_UTC[segment]} |" for segment in SEGMENTS)
    zones = list(UTC_OFFSET_MINUTES)
    phrases = "\n".join(f"  - `{segment}`: `{SEGMENT_PHRASE[segment]}`" for segment in SEGMENTS)
    wordings = "\n".join(f"  - `{code}`: `{wording}`" for code, wording, _percent in OFFERS.values())
    with_offer = " and ".join(f"`{segment}`" for segment in OFFERS)
    return f"""# {BRAND}: lifecycle email policy

{BRAND} posts a tin of loose-leaf tea to its members each month. This is the
standard for its lifecycle email programme. Apply it to `customers.csv` as
written: do not improve on it, and do not skip a customer.

**Today is {TODAY.isoformat()}.** "Days before today" counts calendar days back from
today: {(TODAY - timedelta(days=1)).isoformat()} is 1 day before today, and today itself is 0.

## The export

One row per customer. `consent`, `unsubscribed`, `hard_bounced` and `complained`
are `y` or `n`. `consent_date` is blank where there is no consent, and
`last_order_date` where there are no orders. `lifetime_value` is in whole
dollars. `plan` is {plans}. `timezone` is where the customer reads email.

## 1. Suppression

A suppressed customer receives nothing and belongs to no segment. Check these
reasons in this order. The first that applies is the customer's reason, and
they are listed with that one only.

1. `complaint`: `complained` is `y`.
2. `unsubscribed`: `unsubscribed` is `y`.
3. `hard_bounce`: `hard_bounced` is `y`.
4. `no_consent`: `consent` is `n`.
5. `stale_consent`: `country` is {stale}, and `consent_date` is more than
   {STALE_CONSENT_DAYS} days before today. Exactly {STALE_CONSENT_DAYS} days is still good. Consent never goes
   stale in any other country.
6. `dormant_signup`: `orders` is 0 and `signup_date` is more than {DORMANT_SIGNUP_DAYS} days
   before today. Exactly {DORMANT_SIGNUP_DAYS} days does not count.

## 2. Segments

Every customer who is not suppressed is in one segment: the first in this
order whose test they meet.

1. `new`: `signup_date` is {NEW_DAYS} days before today or fewer. Exactly {NEW_DAYS} days is new.
2. `prospect`: `orders` is 0.
3. `lapsed`: `last_order_date` is more than {LAPSED_DAYS} days before today. Exactly {LAPSED_DAYS}
   days is not lapsed.
4. `vip`: `orders` is {VIP_ORDERS} or more and `lifetime_value` is {VIP_VALUE} or more. Both are needed.
5. `at_risk`: `last_order_date` is more than {AT_RISK_DAYS} days before today. Exactly {AT_RISK_DAYS}
   days is not at risk.
6. `active`: everyone else.

The order decides. A customer with VIP numbers whose last order was 200 days
before today is `lapsed`.

## 3. Holdout

Some customers are held out, so the programme can be measured against them.
In {held}, a customer is in the holdout when
the number in their id is divisible by {HOLDOUT_DIVISOR} (`C105` is 105, which is). Nobody in
{not_held} is held out, and a suppressed customer is never in the
holdout. A held-out customer keeps their segment and receives no email.

## 4. Flows

Each segment has one flow. A customer enters it on day 0.

| segment | emails | first email | last email | offer |
|---|---|---|---|---|
{flows}

- Steps are numbered from 1, in the order they are sent.
- You choose the days of the emails between the first and the last: whole
  days, with at least {MIN_GAP_DAYS} days between one email and the next. Day 0 then day {MIN_GAP_DAYS}
  is allowed; day 0 then day {MIN_GAP_DAYS - 1} is not.
- Only the {with_offer} flows carry an offer. Its code goes on the last email
  of that flow and on no other email.
- Cap: a customer on a gift plan (`{GIFT_PLAN}`) receives steps 1 and {GIFT_CAP} of their flow and
  no later step. Everyone else receives every step.

The programme's first full run is every email it sends when each customer who
is neither suppressed nor held out receives every step they are due.

## 5. Send times

Each step is released once, to everyone at the same moment:

| segment | released at (UTC) |
|---|---|
{releases}

A step that carries an offer code is released at {OFFER_RELEASE_UTC} UTC instead of its
segment's time.

A customer receives it at that moment by their own clock. Use these fixed
offsets from UTC, with no daylight saving:

| timezone | {' | '.join(zones)} |
|{'---|' * (len(zones) + 1)}
| offset | {' | '.join(_offset(UTC_OFFSET_MINUTES[zone]) for zone in zones)} |

Quiet hours are {QUIET_FROM} to {QUIET_UNTIL} by the customer's clock, both ends included. An
email that would arrive in quiet hours is held and arrives at {QUIET_RESUME} instead;
{QUIET_RESUME} itself is not quiet. Holding an email does not change its day in the flow.

The schedule has one row for each segment, step and timezone in which at
least one customer receives that step, and no other rows. A local time is
written as HH:MM on the 24-hour clock.

## 6. Copy

Each email has a subject and a preheader. A term below is found as whole
words, in any case: `free` is in "caffeine-free" (a hyphen separates words)
and is not in "freedom".

- A subject is at most {SUBJECT_MAX} characters and a preheader at most {PREHEADER_MAX}, spaces and
  punctuation included. Neither is empty.
- Every email has its segment's phrase in its subject or in its preheader:
{phrases}
- The offer email of a flow has its offer, in these exact words, in its
  subject or in its preheader. It states no other percentage and names no
  other code.
{wordings}
- An email without an offer has no `%` sign and names no offer code.
- Never: {_quoted(FORBIDDEN_WORDS)}.
- No exclamation marks.
- No two emails in the programme have the same subject, whatever the case.
"""


def fixtures() -> dict[str, str]:
    return {"customers.csv": export_csv(), "lifecycle_policy.md": lifecycle_policy_md()}


# ── The checker ───────────────────────────────────────────────────────────────

# A reply is a model's output. A cell that is read as a code, a number or a
# time is cut to this first; a line of copy is cut to _COPY before it is searched.
_CELL = 40
_COPY = 400
_NO_OFFER = {"", "-", "–", "—", "none", "n/a", "na", "null", "no"}


def _code(text: object) -> str:
    """A reason, a segment or a column value written loosely: `At-Risk` is `at_risk`."""
    return re.sub(r"[^a-z0-9]+", "_", common.norm(str(text or "")[:_CELL])).strip("_")


def _customer_id(text: object) -> str:
    core = str(text or "")[:_CELL].strip().strip("\"'`").strip().upper()
    return f"C{core}" if core.isdigit() else core


def _whole(text: object) -> int | None:
    """The whole number in a cell such as "3", "Step 3" or "day 14"."""
    match = re.search(r"-?\d{1,4}", str(text or "")[:_CELL])
    return int(match.group(0)) if match and not match.group(0).startswith("-") else None


def _clock(text: object) -> str | None:
    """The time in a cell, as HH:MM: "8:00", "08:00:00" and "8.00 am" are 08:00."""
    core = str(text or "")[:_CELL].lower()
    match = re.search(r"(\d{1,2})[:.h](\d{2})", core)
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    after = core[match.end():].lstrip(": 0123456789")[:4].replace(".", "")
    if after.startswith("pm") and hours < 12:
        hours += 12
    elif after.startswith("am") and hours == 12:
        hours = 0
    return f"{hours:02d}:{minutes:02d}" if hours < 24 and minutes < 60 else None


def _offer_cell(text: object) -> str:
    core = common.norm(str(text or "")[:_CELL])
    return "" if core in _NO_OFFER else core.upper()


def _has_term(flat: str, term: str) -> bool:
    """Whether a term is in a line as whole words: `free` is in "caffeine-free"
    and not in "freedom"."""
    return re.search(r"(?<![a-z0-9])" + re.escape(common.norm(term)) + r"(?![a-z0-9])", flat) is not None


def _copy_violations(parts: list[str], segment: str, step: int) -> int:
    """What a subject and preheader say that they may not. `parts` are the two,
    each already cut and normalised; a term cannot run from one into the other."""
    flat = " | ".join(parts)
    count = sum(1 for term in FORBIDDEN_WORDS if _has_term(flat, term)) + (FORBIDDEN_MARK in flat)
    codes = {code for code, _wording, _percent in OFFERS.values()}
    if offer_code(segment, step):
        own, _wording, percent = OFFERS[segment]
        count += any(int(number) != percent for number in re.findall(r"(\d{1,3}) ?%", flat))
        count += any(_has_term(flat, code) for code in codes - {own})
    else:
        count += "%" in flat or any(_has_term(flat, code) for code in codes)
    return count


def facts(response_text: str, workflow: str = TASK_ID) -> dict[str, int]:
    """Counts of what a reply got wrong. Every count measures work against the
    reference, so a missing file or a missing row is that many errors, never
    zero: a reply that leaves a deliverable out earns nothing on its checks."""
    ref = reference()
    found = common.tables(response_text, FILES)

    def ids(name: str) -> list[str]:
        listed = [_customer_id(common.cell(row, "customer_id", "id", "customer")) for row in (found[name] or [])]
        return [customer_id for customer_id in listed if customer_id]

    export = {customer["customer_id"] for customer in customers()}
    suppressed = {_customer_id(common.cell(row, "customer_id", "id", "customer")): row for row in (found["suppressed.csv"] or [])}
    segments = {_customer_id(common.cell(row, "customer_id", "id", "customer")): row for row in (found["segments.csv"] or [])}
    listed = ids("suppressed.csv") + ids("segments.csv")
    said_suppressed = set(ids("suppressed.csv")) & export
    holdout = set(ids("holdout.csv"))

    # flow.csv: one row per email, the last one given for a step being the one read.
    flow_rows = [(_code(common.cell(row, "segment")), _whole(common.cell(row, "step")), row) for row in (found["flow.csv"] or [])]
    wanted_flow = flow_keys()
    wanted = set(wanted_flow)
    flow = {(segment, step): row for segment, step, row in flow_rows if (segment, step) in wanted}
    step_errors = sum(1 for key in wanted_flow if key not in flow)
    step_errors += len(flow_rows) - len(flow)   # a step given twice, a step the flow has not, another segment
    day_errors = 0
    for segment, (emails, first, last) in FLOWS.items():
        days = [_whole(common.cell(flow[(segment, step)], "day")) if (segment, step) in flow else None
                for step in range(1, emails + 1)]
        day_errors += (days[0] != first) + (days[-1] != last)
        day_errors += sum(1 for before, after in zip(days, days[1:])
                          if before is None or after is None or after - before < MIN_GAP_DAYS)
    offer_errors = limit_errors = required_errors = copy_violations = 0
    subjects: list[str] = []
    for segment, step in wanted_flow:
        code = offer_code(segment, step)
        row = flow.get((segment, step))
        if row is None:
            offer_errors += 1
            limit_errors += 2
            required_errors += 1 + bool(code)
            copy_violations += 1
            continue
        subject, preheader = common.cell(row, "subject", "subject_line"), common.cell(row, "preheader", "preview_text")
        offer_errors += _offer_cell(common.cell(row, "offer_code", "offer", "code")) != code
        limit_errors += (not subject or len(subject) > SUBJECT_MAX) + (not preheader or len(preheader) > PREHEADER_MAX)
        parts = [common.norm(subject[:_COPY]), common.norm(preheader[:_COPY])]
        required_errors += not any(_has_term(part, SEGMENT_PHRASE[segment]) for part in parts)
        if code:
            required_errors += not any(_has_term(part, OFFERS[segment][1]) for part in parts)
        copy_violations += _copy_violations(parts, segment, step)
        if subject:
            subjects.append(parts[0])
    repeated = len(subjects) - len(set(subjects)) + sum(1 for key in wanted_flow if key not in flow)

    # schedule.csv: the rows that should be there, and the time on each.
    schedule_rows = [
        ((_code(common.cell(row, "segment")), _whole(common.cell(row, "step")),
          str(common.cell(row, "timezone", "time_zone", "tz"))[:_CELL].strip().upper()),
         _clock(common.cell(row, "local_send_time", "local_time", "send_time", "time")))
        for row in (found["schedule.csv"] or [])
    ]
    schedule = {key: clock for key, clock in schedule_rows if key in ref["schedule"]}
    schedule_row_errors = sum(1 for key in ref["schedule"] if key not in schedule) + len(schedule_rows) - len(schedule)

    return {
        "workflow_missing_file_count": sum(1 for name in FILES if found[name] is None),
        # Customers of the export in neither list, listed twice, or not in the export at all.
        "workflow_customer_accounting_error_count": (
            len(export - set(listed)) + (len(listed) - len(set(listed))) + len(set(listed) - export)),
        "workflow_suppression_error_count": len(set(ref["suppressed"]) ^ said_suppressed),
        "workflow_wrong_reason_count": sum(
            1 for customer_id, reason in ref["suppressed"].items()
            if customer_id not in suppressed or _code(common.cell(suppressed[customer_id], "reason", "reason_code")) != reason),
        "workflow_wrong_segment_count": sum(
            1 for customer_id, segment in ref["segments"].items()
            if customer_id not in segments or _code(common.cell(segments[customer_id], "segment")) != segment),
        "workflow_holdout_error_count": len(set(ref["holdout"]) ^ holdout),
        "workflow_flow_step_error_count": step_errors,
        "workflow_flow_day_error_count": day_errors,
        "workflow_offer_error_count": offer_errors,
        "workflow_schedule_row_error_count": schedule_row_errors,
        "workflow_schedule_time_error_count": sum(1 for key, clock in ref["schedule"].items() if schedule.get(key) != clock),
        "workflow_copy_limit_error_count": limit_errors,
        "workflow_copy_required_error_count": required_errors,
        "workflow_copy_violation_count": copy_violations,
        "workflow_repeated_subject_count": repeated,
    }
