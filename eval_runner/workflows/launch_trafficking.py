"""Workflow task: turn a launch brief into a trafficking sheet.

A product launches to three audiences on Meta, Google Search, LinkedIn and
email. The candidate reads the brief, the platform specs and the tracking
standard, and hands back what an ad ops lead would traffic: the media budget
by channel and week, every text field of every asset, and every asset's final
URL. The work is a hundred-odd short pieces of copy, each under its own hard
limit and carrying the strings its field must carry, written for its audience
and not another's, and three files that have to agree with each other and
with the standard to the character.

Everything here derives from the constants below: the documents the candidate
reads, the reference answer and the checker. A rule cannot say one thing in
the brief and another in the grader.

All brands, people, places, URLs and figures are invented.
"""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from eval_runner.workflows import common

TASK_ID = "launch-trafficking"
FIXTURE_DIR = Path("eval_runner") / "fixtures" / "launch-trafficking"
FILES = ["budget.csv", "assets.csv", "trafficking.csv"]

BRAND = "Fernhollow"
PRODUCT = "Fernhollow Shifts"
PRODUCT_CODE = "shifts"
SITE = "https://www.fernhollow.example"

PROMO_CODE = "FERN30"
EXPIRED_CODE = "FERN20"
EXPIRED_ON = "Jan 31, 2027"
OFFER = "30% off"
LEGAL_LINE = "Offer ends Mar 31, 2027. New accounts only."
EXPIRY = "Mar 31"
FLIGHT_START = date(2027, 2, 22)
FLIGHT_WEEKS = 4
# A word of FERN and digits is a promo code. Only PROMO_CODE is live, and no
# channel in NO_CODE_CHANNELS may carry any code.
_CODE_WORD = re.compile(r"fern\d{1,6}")
NO_CODE_CHANNELS = {"google"}

BANNED_CLAIMS: list[tuple[str, str]] = [
    ("best", "a superlative nobody has measured"),
    ("#1", "a ranking nobody has published"),
    ("guarantee", "Fernhollow guarantees nothing"),
    ("guaranteed", "the same"),
    ("free forever", "there is no free plan, only the launch offer"),
    ("unlimited", "every plan is priced per user"),
    ("hipaa", "Fernhollow is not a health-records product: no HIPAA claim of any kind, even for clinics"),
]


@dataclass(frozen=True)
class Audience:
    code: str
    slug: str
    name: str
    who: str
    problem: str
    problem_keywords: tuple[str, ...]
    proof: str
    proof_point: str

    @property
    def terms(self) -> tuple[str, ...]:
        """What an asset of this audience must name, one of them at least."""
        return self.problem_keywords + (self.proof_point,)


AUDIENCES: list[Audience] = [
    Audience(
        "RST", "restaurants", "Restaurants",
        "Owners and general managers of independent restaurants and small groups, 10 to 60 staff.",
        "No-shows on the busiest nights leave the floor and the line short, and the manager spends the rush on the phone.",
        ("no-shows", "no-show"),
        "Kettlewick Kitchens, a group of 4 restaurants, logged 18% less overtime in its first 8 weeks on Fernhollow.",
        "18% less overtime",
    ),
    Audience(
        "CLN", "clinics", "Clinics",
        "Practice managers at outpatient clinics (dental, physiotherapy, primary care), front desk and clinical staff.",
        "The rota lives in a spreadsheet, so staff get double-booked and sessions go uncovered.",
        ("double-booked", "double-booking"),
        "Practice managers at Northfold Physio got back 5 hours a week of scheduling admin.",
        "5 hours a week",
    ),
    Audience(
        "RTL", "retail", "Retail",
        "Managers of retail chains with 3 to 20 stores and mostly part-time staff.",
        "Covering the weekend rush in every store at once, with part-timers who change their availability every week.",
        ("weekend rush",),
        "Bramblecote Goods had 98% of shifts filled across its 6 stores last December.",
        "98% of shifts filled",
    ),
]
AUDIENCE = {audience.code: audience for audience in AUDIENCES}

# channel -> (name in the specs, utm_source, utm_medium)
CHANNELS: dict[str, tuple[str, str, str]] = {
    "meta": ("Meta", "meta", "paid_social"),
    "google": ("Google Search", "google", "cpc"),
    "linkedin": ("LinkedIn", "linkedin", "paid_social"),
    "email": ("Email", "newsletter", "email"),
}


@dataclass(frozen=True)
class Placement:
    code: str
    channel: str
    slug: str
    fields: tuple[tuple[str, int], ...]


_GOOGLE_FIELDS = tuple((f"headline_{n}", 30) for n in range(1, 6)) + (("description_1", 90), ("description_2", 90))
PLACEMENTS: list[Placement] = [
    Placement("MF", "meta", "feed", (("primary_text", 125), ("headline", 40), ("description", 30))),
    Placement("MS", "meta", "stories", (("primary_text", 80), ("headline", 25))),
    Placement("GS", "google", "search", _GOOGLE_FIELDS),
    Placement("LF", "linkedin", "feed", (("intro_text", 150), ("headline", 70), ("description", 100))),
    Placement("EL", "email", "launch", (("subject", 60), ("preheader", 90))),
    Placement("ER", "email", "reminder", (("subject", 45), ("preheader", 90))),
]
PLACEMENT = {placement.code: placement for placement in PLACEMENTS}
VARIANTS = ["A", "B"]

# (placement code, field) -> the strings that field must contain, any case.
REQUIRED: dict[tuple[str, str], list[str]] = {
    ("MF", "primary_text"): [PROMO_CODE, LEGAL_LINE],
    ("MF", "headline"): [BRAND],
    ("MS", "primary_text"): [PROMO_CODE],
    ("MS", "headline"): [BRAND],
    ("GS", "headline_1"): [BRAND],
    ("GS", "description_1"): [OFFER],
    ("LF", "intro_text"): [PROMO_CODE, LEGAL_LINE],
    ("LF", "headline"): [BRAND],
    ("EL", "subject"): [BRAND],
    ("EL", "preheader"): [PROMO_CODE],
    ("ER", "subject"): [PROMO_CODE],
    ("ER", "preheader"): [EXPIRY],
}

# Tracking: each audience's page, and where its traffic goes when it is not live.
LANDING_PAGES: dict[str, tuple[str, str, str]] = {
    "RST": (f"{SITE}/shifts/restaurants", "live", ""),
    "CLN": (f"{SITE}/shifts/clinics", "draft", "Waiting on legal review"),
    "RTL": (f"{SITE}/shifts/retail", "live", ""),
}
LIVE = "live"
FALLBACK_URL = f"{SITE}/shifts"
GOOGLE_TERM = ("utm_term", "{keyword}")
ASSET_ID_PATTERN = re.compile(
    "FH-(?:" + "|".join(a.code for a in AUDIENCES) + ")-(?:" + "|".join(p.code for p in PLACEMENTS) + ")-(?:"
    + "|".join(VARIANTS) + ")")

# Budget.
TOTAL_BUDGET = Decimal("80000.00")
PRODUCTION_FEE = Decimal("3500.00")
CHANNEL_SHARES: dict[str, Decimal] = {"google": Decimal("0.38"), "meta": Decimal("0.37"), "linkedin": Decimal("0.25")}
WEEK_WEIGHTS = [5, 4, 3, 2]
WEEKLY_MINIMUM = Decimal("4000.00")
CENT = Decimal("0.01")


# ── The reference copy: written to the specs, one audience at a time ─────────
# Per (audience, variant), per placement, the fields in the placement's order.
# Variant A leads with the audience's problem, variant B with its proof point.

COPY: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    ("RST", "A"): {
        "MF": ("Friday no-shows? Open shifts get filled by text. FERN30 takes 30% off. " + LEGAL_LINE,
               "Fernhollow fills no-show gaps fast", "Cover the dinner rush"),
        "MS": ("No-shows at 7pm? Post the shift and a cook grabs it. FERN30 = 30% off.", "Fernhollow for kitchens"),
        "GS": ("Fernhollow for Restaurants", "Cover No-Shows in Minutes", "Shift Swaps Your Crew Can Do",
               "Overtime Alerts Before Payroll", "Built for Busy Kitchens",
               "Fill no-show shifts by text in minutes. New accounts get 30% off the first 3 months.",
               "Servers and cooks swap shifts in the app. You approve with one tap from any phone."),
        "LF": ("No-shows on your busiest night? Fernhollow texts the open shift to your crew. FERN30: 30% off. "
               + LEGAL_LINE,
               "Fernhollow Shifts: scheduling for restaurant teams",
               "Templates, shift swaps and overtime alerts for front and back of house."),
        "EL": ("Fernhollow: stop scrambling over no-shows",
               "Open shifts go out by text to your crew. FERN30 takes 30% off your first 3 months."),
        "ER": ("No-shows again? FERN30 ends Mar 31",
               "Your 30% off ends Mar 31. Build next week's schedule from a template tonight."),
    },
    ("RST", "B"): {
        "MF": ("Kettlewick Kitchens saw 18% less overtime in 8 weeks. FERN30 takes 30% off. " + LEGAL_LINE,
               "Fernhollow: 18% less overtime", "Alerts before overtime hits"),
        "MS": ("4 restaurants, 18% less overtime. See how they schedule. FERN30 = 30% off.",
               "Fernhollow: less overtime"),
        "GS": ("Fernhollow Restaurant Shifts", "18% Less Overtime, Proven", "Schedules Built in Minutes",
               "Fill Open Shifts by Text", "Made for Front & Back of House",
               "A 4-restaurant group cut overtime in 8 weeks. Get 30% off your first 3 months.",
               "Overtime alerts land before you approve a shift, not after payroll runs."),
        "LF": ("Kettlewick Kitchens logged 18% less overtime in 8 weeks on Fernhollow. FERN30: 30% off. "
               + LEGAL_LINE,
               "How 4 restaurants got 18% less overtime with Fernhollow",
               "Overtime alerts before you approve a shift, for restaurant groups of 10 to 60 staff."),
        "EL": ("18% less overtime: the Fernhollow kitchen playbook",
               "See the overtime alerts Kettlewick Kitchens runs on. FERN30 gets you 30% off 3 months."),
        "ER": ("18% less overtime, and FERN30 ends soon",
               "Kettlewick's overtime alerts can be yours by Mar 31, at 30% off for 3 months."),
    },
    ("CLN", "A"): {
        "MF": ("Front desk double-booked again? Swaps need your one-tap OK. FERN30 takes 30% off. " + LEGAL_LINE,
               "Fernhollow: no more double-booked staff", "Every session covered"),
        "MS": ("Hygienists double-booked, 4pm uncovered? Fix the rota. FERN30 = 30% off.", "Fernhollow for clinics"),
        "GS": ("Fernhollow for Clinics", "Stop Double-Booked Shifts", "Schedules Off the Spreadsheet",
               "Only Qualified Staff Notified", "Built for Practice Managers",
               "No more double-booked shifts: swaps wait for your OK. 30% off for 3 months.",
               "Open shifts go by text only to staff qualified for the session, in minutes."),
        "LF": ("Spreadsheet rotas get staff double-booked. Fernhollow routes every swap to you. FERN30: 30% off. "
               + LEGAL_LINE,
               "Fernhollow Shifts: clinic scheduling without the spreadsheet",
               "Swap approvals and open shifts sent only to qualified staff, for dental and physio teams."),
        "EL": ("Fernhollow: no more double-booked mornings",
               "Swaps wait for your approval, so nobody is double-booked. FERN30: 30% off 3 months."),
        "ER": ("FERN30 ends Mar 31: no double-booked staff",
               "Move this month's rota out of the spreadsheet before Mar 31 and keep 30% off."),
    },
    ("CLN", "B"): {
        "MF": ("Practice managers got 5 hours a week back from scheduling. FERN30 takes 30% off. " + LEGAL_LINE,
               "Fernhollow: 5 hours a week back", "Less admin, more patients"),
        "MS": ("5 hours a week back for practice managers. FERN30 takes 30% off.", "Fernhollow: admin, done"),
        "GS": ("Fernhollow Clinic Scheduling", "Get 5 Hours a Week Back", "Rotas Your Front Desk Trusts",
               "Approve Swaps in One Tap", "For Dental & Physio Teams",
               "Practice managers got 5 hours a week back. New accounts get 30% off for 3 months.",
               "Templates for recurring clinic sessions, plus overtime alerts before you approve."),
        "LF": ("Northfold Physio's managers got back 5 hours a week of scheduling admin. FERN30: 30% off. "
               + LEGAL_LINE,
               "5 hours a week back: how Northfold Physio schedules with Fernhollow",
               "Recurring session templates and overtime alerts for outpatient clinics."),
        "EL": ("How Fernhollow gave Northfold 5 hours a week back",
               "The clinic template they use is yours to copy. FERN30 takes 30% off your first 3 months."),
        "ER": ("5 hours a week back. FERN30 ends soon",
               "Northfold's clinic template takes an afternoon. The 30% off ends Mar 31."),
    },
    ("RTL", "A"): {
        "MF": ("Weekend rush, short-staffed? Share shifts across stores. FERN30 takes 30% off. " + LEGAL_LINE,
               "Fernhollow covers the weekend rush", "One schedule, every store"),
        "MS": ("Weekend rush, two staff down? Offer the shift to every store. FERN30 = 30% off.",
               "Fernhollow for retail"),
        "GS": ("Fernhollow for Retail Stores", "Staff the Weekend Rush", "Share Staff Across Stores",
               "Part-Timers Pick Up Shifts", "Labor Forecast by Store",
               "Cover the weekend rush with staff from nearby stores. 30% off your first 3 months.",
               "Part-time staff see open shifts on their phone and claim them. You approve once."),
        "LF": ("The weekend rush hits every store at once. Fernhollow shares open shifts across them. "
               "FERN30: 30% off. " + LEGAL_LINE,
               "Fernhollow Shifts: multi-store scheduling for retail managers",
               "Cross-store open shifts, part-timer availability and weekly labor forecasts."),
        "EL": ("Fernhollow: staff the weekend rush in every store",
               "Offer open shifts to staff at nearby stores. FERN30 takes 30% off your first 3 months."),
        "ER": ("Before the weekend rush: FERN30 ends soon",
               "Share open shifts across stores before your next big weekend. Offer ends Mar 31."),
    },
    ("RTL", "B"): {
        "MF": ("Bramblecote Goods had 98% of shifts filled across 6 stores. FERN30 takes 30% off. " + LEGAL_LINE,
               "Fernhollow: 98% of shifts filled", "Six stores, one schedule"),
        "MS": ("98% of shifts filled across 6 stores. See how. FERN30 = 30% off.", "Fernhollow: 98% filled"),
        "GS": ("Fernhollow Retail Scheduling", "98% of Shifts Filled", "One Schedule, Six Stores",
               "Availability From Part-Timers", "Forecast Labor Cost by Week",
               "Bramblecote Goods had 98% of shifts filled in December. 30% off your first 3 months.",
               "Shared open shifts, part-timer availability and labor cost forecasts by store."),
        "LF": ("Bramblecote Goods had 98% of shifts filled across 6 stores in December. FERN30: 30% off. "
               + LEGAL_LINE,
               "How Bramblecote Goods kept 98% of shifts filled with Fernhollow",
               "Shared shifts across stores and a labor cost forecast for each location, by week."),
        "EL": ("98% of shifts filled: a Fernhollow retail story",
               "See how 6 stores share part-time staff. Use FERN30 for 30% off your first 3 months."),
        "ER": ("98% of shifts filled. FERN30 is ending",
               "Copy Bramblecote's shared-shift setup in an afternoon. 30% off ends Mar 31."),
    },
}


# ── The rules, applied ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Asset:
    audience: Audience
    placement: Placement
    variant: str

    @property
    def id(self) -> str:
        return asset_id(self.audience.code, self.placement.code, self.variant)


def asset_id(audience_code: str, placement_code: str, variant: str) -> str:
    return f"FH-{audience_code}-{placement_code}-{variant}"


@lru_cache(maxsize=1)
def assets() -> tuple[Asset, ...]:
    """Every asset of the launch: each audience, in each placement, in each variant."""
    return tuple(Asset(audience, placement, variant)
                 for audience in AUDIENCES for placement in PLACEMENTS for variant in VARIANTS)


def landing_page(audience: Audience) -> str:
    url, status, _notes = LANDING_PAGES[audience.code]
    return url if status == LIVE else FALLBACK_URL


def utm_parameters(asset: Asset) -> list[tuple[str, str]]:
    _name, source, medium = CHANNELS[asset.placement.channel]
    params = [
        ("utm_source", source),
        ("utm_medium", medium),
        ("utm_campaign", f"{PRODUCT_CODE}_{asset.audience.code.lower()}_{FLIGHT_START:%Y%m}"),
        ("utm_content", f"{asset.placement.slug}_{asset.variant.lower()}"),
    ]
    if asset.placement.channel == "google":
        params.append(GOOGLE_TERM)
    return params


def final_url(asset: Asset) -> str:
    return landing_page(asset.audience) + "?" + "&".join(f"{key}={value}" for key, value in utm_parameters(asset))


def budget() -> dict[tuple[str, int], Decimal]:
    """(channel, week) -> amount, by the brief's four steps in order."""
    media = TOTAL_BUDGET - PRODUCTION_FEE
    total_weight = sum(WEEK_WEIGHTS)
    rows: dict[tuple[str, int], Decimal] = {}
    for channel, share in CHANNEL_SHARES.items():
        channel_budget = (media * share).quantize(CENT)
        weeks = [(channel_budget * weight / total_weight).quantize(CENT, rounding=ROUND_DOWN) for weight in WEEK_WEIGHTS]
        weeks[0] += channel_budget - sum(weeks)
        for index in range(1, len(weeks)):
            if weeks[index] < WEEKLY_MINIMUM:
                weeks[0] -= WEEKLY_MINIMUM - weeks[index]
                weeks[index] = WEEKLY_MINIMUM
        for week, amount in enumerate(weeks, 1):
            rows[(channel, week)] = amount
    return rows


def _phrase_in(text: str, term: str) -> bool:
    return common.has_phrase(common.words(text), common.words(term))


def banned_in(text: str) -> list[str]:
    """The banned claims a text makes, each as a whole word or phrase, any case."""
    return [claim for claim, _why in BANNED_CLAIMS if _phrase_in(text, claim)]


def promo_errors(text: str, channel: str) -> int:
    """Promo codes a text may not carry: an expired or invented code anywhere,
    and any code at all on a channel that carries none."""
    return sum(
        1 for word in common.words(text)
        if _CODE_WORD.fullmatch(word) and (word != PROMO_CODE.lower() or channel in NO_CODE_CHANNELS)
    )


def names_audience(text: str, audience: Audience) -> bool:
    return any(_phrase_in(text, term) for term in audience.terms)


def missing_required(text: str, required: list[str]) -> int:
    flat = common.norm(text)
    return sum(1 for string in required if common.norm(string) not in flat)


# ── The reference: what the standard produces ───────────────────────────────

@lru_cache(maxsize=1)
def reference() -> dict:
    texts = {}
    for asset in assets():
        values = COPY[(asset.audience.code, asset.variant)][asset.placement.code]
        assert len(values) == len(asset.placement.fields), asset.id
        for (field, _limit), text in zip(asset.placement.fields, values):
            texts[(asset.id, field)] = text
    return {
        "assets": assets(),
        "texts": texts,
        "urls": {asset.id: final_url(asset) for asset in assets()},
        "budget": budget(),
    }


def answers() -> dict[int, float]:
    """A1 assets, A2 text fields, A3 total of budget.csv."""
    ref = reference()
    return {1: len(ref["assets"]), 2: len(ref["texts"]), 3: float(sum(ref["budget"].values(), Decimal(0)))}


def reference_answer() -> str:
    """A reply that follows the brief, the specs and the standard to the letter."""
    ref = reference()
    out = [f"Launch package for {PRODUCT}, from the launch brief, the platform specs and the tracking standard.", ""]

    def block(name: str, header: list[str], rows: list[list]) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        out.extend([f"### {name}", "```csv", buffer.getvalue().rstrip("\n"), "```", ""])

    block("budget.csv", ["channel", "week", "amount"],
          [[channel, week, f"{amount:.2f}"] for (channel, week), amount in ref["budget"].items()])
    block("assets.csv", ["asset_id", "channel", "placement", "audience", "variant", "field", "text"], [
        [asset.id, asset.placement.channel, asset.placement.slug, asset.audience.slug, asset.variant, field,
         ref["texts"][(asset.id, field)]]
        for asset in ref["assets"] for field, _limit in asset.placement.fields
    ])
    block("trafficking.csv", ["asset_id", "final_url"], [[asset.id, ref["urls"][asset.id]] for asset in ref["assets"]])
    figures = answers()
    out += [f"A1: {int(figures[1])}", f"A2: {int(figures[2])}", f"A3: {figures[3]:.2f}", ""]
    return "\n".join(out)


# ── The documents the candidate reads ────────────────────────────────────────

def _quoted(terms: tuple[str, ...]) -> str:
    return ", ".join(f"`{term}`" for term in terms)


def _money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def launch_brief_md() -> str:
    audiences = []
    for audience in AUDIENCES:
        audiences.append(f"""### {audience.name} (audience code {audience.code})

{audience.who}

- **Problem:** {audience.problem}
- **Problem keywords:** {_quoted(audience.problem_keywords)}
- **Proof point:** {audience.proof} Copy quotes it as `{audience.proof_point}`.""")
    flight_end = FLIGHT_START + timedelta(weeks=FLIGHT_WEEKS, days=-1)
    weeks = ", ".join(str(weight) for weight in WEEK_WEIGHTS)
    shares = ", ".join(f"{CHANNELS[channel][0]} {share * 100:.0f}%" for channel, share in CHANNEL_SHARES.items())
    return f"""# {PRODUCT}: launch brief

{BRAND} is launching {PRODUCT}, a scheduling app for teams paid by the hour,
to three audiences at once. This brief is the source of every fact the copy
may state: do not add others.

## The product

- Build a week's schedule from a saved template.
- Staff swap shifts and pick up open shifts in the app; the manager approves
  each change with one tap.
- Open shifts go out by text, only to staff who are qualified for them and not
  close to overtime.
- Overtime alerts reach the manager before a shift is approved, not after
  payroll runs.
- A labor cost forecast for each location, by week.
- Runs on any phone or browser. No hardware to buy.

## The audiences

Each audience has its own problem and its own proof point, and its copy is
written for that audience alone.

{chr(10).join(chr(10) + text for text in audiences).strip()}

## The offer

- {OFFER} the first 3 months for new accounts, with the code `{PROMO_CODE}`.
- The offer ends {EXPIRY}, 2027.
- `{EXPIRED_CODE}`, the code from the private beta, expired on {EXPIRED_ON}. It
  must never appear in launch copy, and no other code may be invented.

## Flight

- {FLIGHT_WEEKS} weeks: Monday {FLIGHT_START:%b} {FLIGHT_START.day}, {FLIGHT_START.year} to Sunday {flight_end:%b} {flight_end.day}, {flight_end.year}.
  Week 1 starts {FLIGHT_START:%b} {FLIGHT_START.day}.
- The launch email goes out in week 1 and the reminder email in week 3.

## Budget

The total launch budget is {_money(TOTAL_BUDGET)}. Of it, {_money(PRODUCTION_FEE)} pays for
creative production. That is not media and gets no rows in the budget. Media
is the rest, split by these four steps, in this order:

1. **Channels.** {shares} of media. Email goes to our own
   newsletter list and has no media budget: it gets no rows.
2. **Weeks.** The weights of weeks 1 to 4 are {weeks}. A week's amount is
   the channel's budget times the week's weight, divided by {sum(WEEK_WEIGHTS)}, rounded
   down to the cent. Round only at this step.
3. **Remainder.** The cents a channel lost to rounding go to its week 1, so
   its weeks add up to its budget exactly.
4. **Minimum.** No channel-week may be under {_money(WEEKLY_MINIMUM)}. One that is
   gets raised to {_money(WEEKLY_MINIMUM)}, and the difference is taken from the
   same channel's week 1.
"""


def platform_specs_md() -> str:
    rows = []
    for placement in PLACEMENTS:
        for field, limit in placement.fields:
            required = REQUIRED.get((placement.code, field), [])
            must = " and ".join("the legal line" if text == LEGAL_LINE else f"`{text}`" for text in required) or "-"
            rows.append(f"| {placement.channel} | {placement.slug} | `{field}` | {limit} | {must} |")
    banned = "\n".join(f"- `{claim}`: {why}." for claim, why in BANNED_CLAIMS)
    terms = "\n".join(
        f"| {audience.slug} | {_quoted(audience.problem_keywords)} | `{audience.proof_point}` |" for audience in AUDIENCES)
    count = len(AUDIENCES) * len(PLACEMENTS) * len(VARIANTS)
    return f"""# Platform specs: {PRODUCT} launch

## Assets

An asset is one ad, or one email, for one audience, in one placement, in one
variant. Every audience gets two variants, `A` and `B`, in each of the six
placements below: {len(AUDIENCES)} audiences x {len(PLACEMENTS)} placements x {len(VARIANTS)} variants, {count} assets. An asset
has every field its placement lists, each once, and no other field.

## Placements and fields

The limit is the most characters the field may hold, spaces and punctuation
included. "Must contain" means the exact characters shown, in any case.

| channel | placement | field | limit | must contain |
|---|---|---|---:|---|
{chr(10).join(rows)}

The legal line, exactly: `{LEGAL_LINE}`

Only the two fields marked above require it.

## Promo codes

- A {BRAND} promo code is `FERN` followed by digits. `{PROMO_CODE}` is the only
  code any copy may carry: `{EXPIRED_CODE}` has expired, and no other code may appear.
- Google Search ads carry no promo code at all: a code in a search ad draws
  coupon sites. A Google ad states the offer as `{OFFER}` instead.

## Claims copy never makes

Any case, as a whole word or phrase:

{banned}

## Copy written for its audience

Every asset names its own audience's problem or proof point: at least one of
its fields contains one of that audience's problem keywords or its proof
point, worded as the brief words them (any case; a hyphen may be a space).
Another audience's words do not count.

| audience | problem keywords | proof point |
|---|---|---|
{terms}

No field may hold the same text as the same field of the same placement for
another audience, in either variant. Case, spacing and punctuation do not make
two texts different.
"""


def tracking_standard_md() -> str:
    sources = "\n".join(f"| {channel} | `{source}` | `{medium}` |" for channel, (_n, source, medium) in CHANNELS.items())
    placements = "\n".join(
        f"| `{placement.code}` | {placement.channel} | {placement.slug} | `{placement.slug}` |" for placement in PLACEMENTS)
    audiences = "\n".join(f"| `{audience.code}` | {audience.slug} |" for audience in AUDIENCES)
    example = Asset(AUDIENCE["RTL"], PLACEMENT["LF"], "B")
    return f"""# Tracking standard

## Asset ids

An asset id is `FH-<audience code>-<placement code>-<variant>`, in capitals,
joined by hyphens: `FH-RST-MF-A` is the Restaurants Meta feed ad, variant A.

| audience code | audience |
|---|---|
{audiences}

| placement code | channel | placement | utm_content stem |
|---|---|---|---|
{placements}

## Final URLs

A final URL is the audience's landing page, then `?`, then these parameters
joined by `&`, in any order: their order has no effect on tracking. Every
value is lower case, words joined by underscores, no spaces. No other
parameters, and no `#` fragment.

1. `utm_source` and 2. `utm_medium`, by channel:

| channel | utm_source | utm_medium |
|---|---|---|
{sources}

3. `utm_campaign`: `{PRODUCT_CODE}_<audience code in lower case>_<launch month>`. The launch
   month is the year and month in which the flight starts, as six digits
   (`yyyymm`), for every asset of the launch: it stays the start month even
   when most of the flight, or the asset's own send, falls in a later month.
4. `utm_content`: the placement's stem, an underscore and the variant in lower
   case: `feed_a`, `search_b`, `reminder_a`.
5. Google Search only: `{GOOGLE_TERM[0]}={GOOGLE_TERM[1]}`, written exactly so, braces included. Google
   fills in the keyword. No other channel has a `{GOOGLE_TERM[0]}`.

For example, `{example.id}` links to:

`{final_url(example)}`

## Landing pages

Each audience's page is in `landing_pages.csv`. Link an audience's page only
when its status is `{LIVE}`. When it has any other status, every asset of that
audience links to the fallback page, `{FALLBACK_URL}`, with the same
parameters. A page that is not live is never linked.
"""


def landing_pages_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["audience", "url", "status", "notes"])
    for audience in AUDIENCES:
        url, status, notes = LANDING_PAGES[audience.code]
        writer.writerow([audience.slug, url, status, notes])
    return out.getvalue()


def fixtures() -> dict[str, str]:
    return {
        "launch_brief.md": launch_brief_md(),
        "platform_specs.md": platform_specs_md(),
        "tracking_standard.md": tracking_standard_md(),
        "landing_pages.csv": landing_pages_csv(),
    }


# ── The checker ───────────────────────────────────────────────────────────────

_MAX_ID = 60
_MAX_URL = 2000
_ID_STRIP = " \t`'\"*_<>"
# What a row's columns may say, read loosely: the specs' own words and codes.
_CHANNEL_KEYS = {key: channel for channel, (name, _s, _m) in CHANNELS.items() for key in (channel, common.norm(name))}
_AUDIENCE_KEYS = {key: a.code for a in AUDIENCES for key in (a.slug, a.code.lower(), common.norm(a.name))}


def _raw_id(text: str) -> str:
    return str(text or "")[:_MAX_ID].strip(_ID_STRIP)


def _canon_id(raw: str) -> str:
    """An id as a join key: case, spaces and underscores aside."""
    return "-".join(part for part in re.split(r"[-_\s]+", raw.upper()) if part)


def _field_key(text: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", common.norm(str(text or "")[:60])).strip("_")
    return re.sub(r"(?<=[a-z])(?=\d$)", "_", key)


def _id_from_columns(row: dict[str, str]) -> str | None:
    """The id the standard gives the asset a row's own columns describe."""
    channel = _CHANNEL_KEYS.get(common.norm(common.cell(row, "channel")[:60]))
    slug = common.norm(common.cell(row, "placement")[:60])
    placement = next((p for p in PLACEMENTS if p.channel == channel and slug in (p.slug, p.code.lower())), None)
    audience = _AUDIENCE_KEYS.get(common.norm(common.cell(row, "audience")[:60]))
    variant = common.norm(common.cell(row, "variant")[:10]).upper()
    if placement is None or audience is None or variant not in VARIANTS:
        return None
    return asset_id(audience, placement.code, variant)


def _same_text(text: str) -> str:
    return " ".join(common.words(text))


def _url_parts(text: str) -> tuple | None:
    """(scheme, host, path), the sorted parameters and the fragment of a URL, or None."""
    text = str(text or "")[:_MAX_URL].strip(_ID_STRIP)
    try:
        parts = urlsplit(text)
        params = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError:
        return None
    base = (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"))
    return base, tuple(sorted(params)), parts.fragment


def _week(text: str) -> int | None:
    match = re.search(r"\d{1,3}", str(text or "")[:40])
    return int(match.group(0)) if match else None


def facts(response_text: str, workflow: str = TASK_ID) -> dict:
    """Counts of what a reply got wrong. Every count measures work against the
    reference, so a missing file is that many errors, never zero: a reply that
    leaves a deliverable out earns nothing on its checks."""
    ref = reference()
    expected = {asset.id: asset for asset in ref["assets"]}
    found = common.tables(response_text, FILES)

    # budget.csv
    wanted_budget = ref["budget"]
    given_budget: dict[tuple[str, int], Decimal | None] = {}
    budget_errors = 0
    for row in found["budget.csv"] or []:
        key = (_CHANNEL_KEYS.get(common.norm(common.cell(row, "channel")[:60])), _week(common.cell(row, "week")))
        if key not in wanted_budget or key in given_budget:
            budget_errors += 1
            continue
        given_budget[key] = common.money(common.cell(row, "amount", "budget")[:60])
    budget_errors += sum(
        1 for key, amount in wanted_budget.items()
        if given_budget.get(key) is None or abs(given_budget[key] - amount) >= Decimal("0.005"))

    # assets.csv
    texts: dict[tuple[str, str], str] = {}
    present: set[str] = set()
    unknown_ids: set[str] = set()
    bad_asset_ids: set[str] = set()
    seen_fields: set[tuple[str, str]] = set()
    repeated_fields = extra_fields = 0
    for row in found["assets.csv"] or []:
        raw = _raw_id(common.cell(row, "asset_id", "id"))
        key = _canon_id(raw)
        if not key:
            continue
        field = _field_key(common.cell(row, "field", "field_name"))
        if (key, field) in seen_fields:
            repeated_fields += 1
        seen_fields.add((key, field))
        if raw != _id_from_columns(row):
            bad_asset_ids.add(key)
        if key not in expected:
            unknown_ids.add(key)
            continue
        present.add(key)
        if field not in dict(expected[key].placement.fields):
            extra_fields += 1
            continue
        text = common.cell(row, "text", "copy").strip()
        if text and (key, field) not in texts:
            texts[(key, field)] = text

    field_errors = extra_fields
    limit_errors = required_errors = copy_violations = audience_errors = 0
    for asset in ref["assets"]:
        own = []
        for field, limit in asset.placement.fields:
            text = texts.get((asset.id, field))
            required = REQUIRED.get((asset.placement.code, field), [])
            if not text:
                field_errors += 1
                limit_errors += 1
                required_errors += len(required)
                continue
            own.append(text)
            limit_errors += len(text) > limit
            required_errors += missing_required(text, required)
            copy_violations += len(banned_in(text)) + promo_errors(text, asset.placement.channel)
        copy_violations += not own
        audience_errors += not any(names_audience(text, asset.audience) for text in own)

    reused = 0
    for placement in PLACEMENTS:
        for field, _limit in placement.fields:
            audiences_by_text: dict[str, set[str]] = defaultdict(set)
            for asset in ref["assets"]:
                if asset.placement is not placement:
                    continue
                text = texts.get((asset.id, field))
                if not text:
                    reused += 1
                else:
                    audiences_by_text[_same_text(text)].add(asset.audience.code)
            reused += sum(len(codes) - 1 for codes in audiences_by_text.values())

    # trafficking.csv
    urls: dict[str, str] = {}
    traffic_seen: set[str] = set()
    unknown_traffic: set[str] = set()
    bad_traffic_ids: set[str] = set()
    repeated_traffic = 0
    for row in found["trafficking.csv"] or []:
        raw = _raw_id(common.cell(row, "asset_id", "id"))
        key = _canon_id(raw)
        if not key:
            continue
        if key in traffic_seen:
            repeated_traffic += 1
            continue
        traffic_seen.add(key)
        if not ASSET_ID_PATTERN.fullmatch(raw):
            bad_traffic_ids.add(key)
        if key not in expected:
            unknown_traffic.add(key)
            continue
        urls[key] = common.cell(row, "final_url", "url")

    url_errors = fallback_errors = 0
    for asset in ref["assets"]:
        falls_back = LANDING_PAGES[asset.audience.code][1] != LIVE
        given = _url_parts(urls[asset.id]) if asset.id in urls else None
        want = _url_parts(ref["urls"][asset.id])
        if given is None:
            url_errors += 1
            fallback_errors += falls_back
            continue
        base_ok = given[0] == want[0]
        params_ok = given[1] == want[1] and not given[2]
        if falls_back:
            fallback_errors += not base_ok
            url_errors += not params_ok
        else:
            url_errors += not (base_ok and params_ok)

    # Every asset missing from a file (a missing file is all of them) is an
    # error in both id checks, so neither is passed by leaving rows out.
    missing_ids = len(set(expected) - present) + len(set(expected) - set(urls))
    return {
        "workflow_missing_file_count": sum(1 for name in FILES if found[name] is None),
        "workflow_budget_row_error_count": budget_errors,
        "workflow_asset_coverage_error_count": len(set(expected) - present) + len(unknown_ids),
        "workflow_field_coverage_error_count": field_errors,
        "workflow_field_over_limit_count": limit_errors,
        "workflow_required_string_missing_count": required_errors,
        "workflow_copy_violation_count": copy_violations,
        "workflow_audience_message_missing_count": audience_errors,
        "workflow_reused_copy_count": reused,
        "workflow_duplicate_asset_id_count": repeated_fields + repeated_traffic + missing_ids,
        "workflow_asset_id_format_error_count": len(bad_asset_ids) + len(bad_traffic_ids) + missing_ids,
        "workflow_trafficking_row_error_count": len(set(expected) - set(urls)) + len(unknown_traffic),
        "workflow_url_error_count": url_errors,
        "workflow_fallback_page_error_count": fallback_errors,
    }
