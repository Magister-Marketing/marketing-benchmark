"""Workflow task: roll a price change through 14 pieces of existing copy.

A booking-software company raises its prices, renames one plan and lengthens
its free trial. The brief says exactly what changes, how a price is written,
which assets carry a notice, and which sentence existing customers get in
place of their price. The work is applying it to fourteen assets without one
slip: every old price, name and trial length gone, every new figure written
as the brief writes it, every look-alike left alone, every ad within its
limit, and nothing else touched.

Everything here is derived from the constants below. Each asset is written
once, as a template whose marks (``[[m:solo:a]]``, ``[[name]]``,
``[[trial:days]]``) are the things the brief changes: rendered with the old
values it is the copy the candidate reads, rendered with the new ones it is
the reference. The brief quotes the same constants, so the copy, the brief
and the grader cannot disagree.

All brands, people, addresses and figures are invented.
"""
from __future__ import annotations

import csv
import io
import re
import string
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

TASK_ID = "price-change-rollout"
FIXTURE_DIR = Path("eval_runner") / "fixtures" / "price-change-rollout"
CHANGE_LOG = "change_log.csv"

BRAND = "Kestrelwick"
DOMAIN = "kestrelwick.example"
OLD_NAME, NEW_NAME = "Studio", "Growth"
EFFECTIVE = "March 1, 2027"
LAST_OLD_DAY = "February 28, 2027"
KEEP_UNTIL = "August 31, 2027"
EXISTING_PAY_NEW_FROM = "September 1, 2027"
OLD_TRIAL_DAYS, NEW_TRIAL_DAYS = 14, 30
YEARLY_MONTHS = 10      # a yearly plan costs ten times the monthly price, before and after
SAVING_MONTHS = 12      # what paying yearly saves: twelve monthly prices, minus the yearly one

# key: (name before, name after, monthly price before, monthly price after)
PLANS: dict[str, tuple[str, str, int, int]] = {
    "solo": ("Solo", "Solo", 19, 24),
    "studio": (OLD_NAME, NEW_NAME, 49, 59),
    "multi": ("Multi-site", "Multi-site", 99, 119),
}
RENAMED = "studio"

NOTICE = (f"Prices are in US dollars and apply to new subscriptions from {EFFECTIVE}; "
          f"current subscribers keep their price until {KEEP_UNTIL}.")
NOTICE_TYPES = ("pricing page section", "FAQ", "sales one-pager", "help article")
EXISTING_CUSTOMER_ASSET = "asset-05"
GRANDFATHER = (f"Because you subscribed before {EFFECTIVE}, your price stays at "
               f"${PLANS[RENAMED][2]}/month until {KEEP_UNTIL}.")
# The sentence of asset-05 that tells an existing customer what they pay.
_PRICE_SENTENCE = "Your [[name]] plan renews at [[m:studio:a]] on the first of each month."
_GRANDFATHER_ANCHOR = "because you subscribed before"

# Fields with a limit: (label, characters after the label and its space).
LIMITS: dict[str, list[tuple[str, int]]] = {
    "ad": [("Headline", 40), ("Body", 125)],
    "in-app banner": [("Text", 90)],
}
SHORT_UNITS = {"/mo": "/month", "/yr": "/year"}   # allowed in ads and the banner only

PLAN_URL = f"{DOMAIN}/plans/studio"
INTEGRATIONS = "49 integrations"
FEATURE = "StudioSync"
CARD_RATE = "2.9% plus 25 cents"
# The brief's example of a saving written as an amount alone: no figure of the
# change, so the example gives none of the answers away.
FORMAT_EXAMPLE_AMOUNT = "$40"

# How the old copy writes a price, by the mark's style.
_MONTH_UNITS = {"a": " a month", "per": " per month", "slash": "/month", "mo": "/mo"}
_YEAR_UNITS = {"a": " a year", "per": " per year", "slash": "/year", "yr": "/yr"}
_OLD_TRIAL = {"day": "14-day", "days": "14 days", "weeks": "two weeks", "Weeks": "Two weeks", "week": "two-week"}
_NEW_TRIAL = {"day": "30-day", "days": "30 days", "weeks": "30 days", "Weeks": "30 days", "week": "30-day"}


# ── The prices, before and after ─────────────────────────────────────────────

def monthly(plan: str, new: bool) -> int:
    return PLANS[plan][3 if new else 2]


def yearly(plan: str, new: bool) -> int:
    return YEARLY_MONTHS * monthly(plan, new)


def saving(plan: str, new: bool) -> int:
    return SAVING_MONTHS * monthly(plan, new) - yearly(plan, new)


def money(amount: int) -> str:
    return f"${amount:,}"


def new_price(plan: str, period: str, short: bool = False) -> str:
    """A new price exactly as the brief writes it: "$59/month", "$1,190/year"."""
    if period == "month":
        return money(monthly(plan, True)) + ("/mo" if short else "/month")
    return money(yearly(plan, True)) + ("/yr" if short else "/year")


# ── The assets ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    template: str

    @property
    def file(self) -> str:
        return f"{self.id}.md"


ASSETS: list[Asset] = [
    Asset("asset-01", "pricing page section", """\
## Simple plans for every studio

Every plan includes online booking, card payments, automated class reminders and a [[trial:day]] free trial. No setup fees, and you can cancel anytime.

### Solo

[[m:solo:slash]], or [[y:solo:slash]] when you pay yearly. For one instructor running their own classes, with unlimited bookings, payments and reminders.

### [[name]]

[[m:studio:slash]], or [[y:studio:slash]] when you pay yearly. For a studio with a team: everything in Solo, plus up to 10 staff logins, waitlists, memberships and StudioSync calendar sync.

### Multi-site

[[m:multi:slash]], or [[y:multi:slash]] when you pay yearly. For businesses with more than one location: everything in [[name]], plus unlimited locations, combined reporting and priority support.

Paying yearly saves [[save:solo]] on Solo, [[save:studio]] on [[name]] and [[save:multi]] on Multi-site, compared with paying month by month.

Not sure which plan fits? See everything [[name]] includes at kestrelwick.example/plans/studio, or book a call with our team."""),
    Asset("asset-02", "FAQ", """\
## Pricing questions

**How long is the free trial?**
Every new account gets [[trial:weeks]] free, with every feature of the [[name]] plan switched on. We don't ask for a card until the trial ends.

**What does the [[name]] plan cost?**
[[name]] is [[m:studio:a]], or [[y:studio:a]] if you pay for the year up front, and it connects to all 49 integrations. Your booking page, newsletter tool and accounting software stay in step.

**Can I switch plans later?**
Yes. Move between Solo, [[name]] and Multi-site from Settings at any time. When you move up, we charge only the difference for the rest of your billing period.

**Is there a discount for paying yearly?**
Yes: a year costs the same as ten months. On Solo that is [[y:solo:a]] instead of [[m:solo:a]] twelve times.

**Do you charge transaction fees?**
Card payments cost 2.9% plus 25 cents per booking, the same on every plan. Kestrelwick adds nothing on top."""),
    Asset("asset-03", "email", """\
Subject: Welcome to Kestrelwick: your [[trial:day]] trial starts now

Hi [First name],

Thanks for starting your free trial. For the next [[trial:days]] you can use everything Kestrelwick does, with no card on file.

Three things to try this week:

1. Publish your class schedule and share your booking link.
2. Turn on reminders, so clients get a text the day before class.
3. Connect your calendars with StudioSync, so no instructor double-books a room.

When your trial ends, pick the plan that fits. Most studios with a small team choose [[name]] at [[m:studio:per]]. If you teach on your own, Solo at [[m:solo:mo]] covers everything you need.

Questions? Reply to this email and a real person on our team will answer.

Marisol Okafor
Customer success, Kestrelwick"""),
    Asset("asset-04", "email", """\
Subject: Five ways to fill your January classes

Hi [First name],

January is the busiest month of the year for most studios, and the easiest to waste. Here are five things the fullest studios on Kestrelwick do before the rush.

1. Open bookings four weeks out. Clients who plan ahead book more classes.
2. Turn on waitlists for every class that sold out last January.
3. Sell a five-class intro pack, and put it at the top of your booking page.
4. Use StudioSync, so every instructor's calendar shows the new schedule.
5. Send a reminder the evening before each class. No-shows drop by about a third.

Want more ideas like these? Our guide to January is at kestrelwick.example/guides/january.

See you in class,
The Kestrelwick team"""),
    Asset("asset-05", "email to existing customers", """\
Subject: Your [[name]] plan: three features you may have missed

Hi [First name],

[[grandfather]] Here are three things your plan already includes that many studios never switch on.

Waitlists. When a class fills, clients can join a waitlist and get a spot automatically if someone cancels.

StudioSync. Connect each instructor's calendar, and every change to the schedule appears everywhere at once.

Memberships. Sell monthly memberships that renew automatically, and let members book without paying each time.

Opening a second location? Multi-site, at [[m:multi:a]], adds unlimited locations and combined reporting. You can move up from Settings at any time, and your team keeps everything it has set up.

Know another studio owner? Send them your invite link and they get a [[trial:day]] free trial.

Thanks for teaching with Kestrelwick,
Tomas Brevik
Head of customer success"""),
    Asset("asset-06", "ad", """\
Headline: Kestrelwick Solo, from [[m:solo:a]]
Body: Booking, payments and reminders for instructors who teach on their own. Try it free for [[trial:days]]."""),
    Asset("asset-07", "ad", """\
Headline: Run your studio on [[name]]
Body: Staff logins, waitlists and StudioSync for studios with a team. [[m:studio:mo]] after your [[trial:day]] free trial."""),
    Asset("asset-08", "ad", """\
Headline: Multi-site for every location: [[m:multi:slash]]
Body: One account for every location you run, with combined reporting and priority support. Free for [[trial:days]]."""),
    Asset("asset-09", "ad", """\
Headline: Fill every class, every week
Body: Online booking your clients can use on any phone, with reminders that cut no-shows. Built for yoga and fitness studios."""),
    Asset("asset-10", "ad", """\
Headline: [[trial:Weeks]] free. No card needed.
Body: Set up your schedule, take bookings and get paid. Kestrelwick plans start at [[m:solo:a]] when your trial ends."""),
    Asset("asset-11", "ad", """\
Headline: Your schedule, synced everywhere
Body: StudioSync puts every class on every instructor's calendar, and moves it when you change the timetable."""),
    Asset("asset-12", "sales one-pager", """\
# Kestrelwick for growing studios

Kestrelwick runs bookings, payments and reminders for more than 3,000 yoga and fitness studios. This page is for owners comparing booking software before they sign up.

## Why studios switch

- Clients book and pay in under a minute, from any phone.
- Automated reminders cut no-shows by about a third.
- StudioSync keeps every instructor's calendar up to date.

## Which plan

Solo is [[m:solo:a]], less than a single drop-in class at most studios. [[name]] adds staff logins, waitlists, memberships, StudioSync and all 49 integrations for [[diff:studio:solo]] more a month than Solo. Multi-site, at [[m:multi:a]] or [[y:multi:a]], is for owners with more than one location.

Every plan starts with a [[trial:day]] free trial, and every plan has the same card rate: 2.9% plus 25 cents per booking.

## Next step

Book a 20-minute walkthrough at kestrelwick.example/demo, or start a trial and import your schedule in an afternoon."""),
    Asset("asset-13", "help article", """\
# Changing your plan

You can move between Solo, [[name]] and Multi-site at any time from Settings, under Billing. This article explains what happens to your bill when you do.

## Moving up

When you move from Solo to [[name]], you pay the difference for the rest of your current billing period, and [[m:studio:per]] from your next bill.

## Moving down

A move down takes effect at the end of your billing period, and nothing is refunded for time already paid. If you move from [[name]] to Solo, [[name]]'s staff logins and waitlists are switched off, and StudioSync keeps working for the account owner only.

## Paying yearly

Yearly plans cost the same as ten months: [[y:solo:per]] for Solo, [[y:studio:per]] for [[name]] and [[y:multi:per]] for Multi-site. You can switch to yearly billing at any time, and we credit what is left of your current month.

## Still in your trial?

Changing plans during your [[trial:day]] trial is free, and your trial's end date stays the same.

If anything on your bill looks wrong, write to billing@kestrelwick.example and we will answer within one working day."""),
    Asset("asset-14", "in-app banner", """\
Text: Need staff logins? Move up to [[name]] for [[m:studio:slash]] and add your whole team.
Link: kestrelwick.example/plans/studio"""),
]
FILE_NAMES = [asset.file for asset in ASSETS]
_BY_ID = {asset.id: asset for asset in ASSETS}


# ── Rendering a template, before and after ───────────────────────────────────

_MARK = re.compile(r"\[\[([A-Za-z]{1,12}(?::[A-Za-z]{1,12}){0,2})\]\]")
_PRICE_KINDS = ("m", "y", "save", "diff")


def _mark(spec: str, new: bool, short: bool) -> str:
    kind, *args = spec.split(":")
    if kind == "m":
        plan, style = args
        return new_price(plan, "month", short) if new else money(monthly(plan, False)) + _MONTH_UNITS[style]
    if kind == "y":
        plan, style = args
        return new_price(plan, "year", short) if new else money(yearly(plan, False)) + _YEAR_UNITS[style]
    if kind == "save":
        return money(saving(args[0], new))
    if kind == "diff":
        return money(monthly(args[0], new) - monthly(args[1], new))
    if kind == "name":
        return NEW_NAME if new else OLD_NAME
    if kind == "trial":
        return (_NEW_TRIAL if new else _OLD_TRIAL)[args[0]]
    if kind == "grandfather":
        return GRANDFATHER if new else render(_PRICE_SENTENCE, False)
    raise ValueError(f"unknown mark {spec!r}")


def render(template: str, new: bool, short: bool = False) -> str:
    return _MARK.sub(lambda match: _mark(match.group(1), new, short), template)


def _marks(template: str) -> list[str]:
    return [match.group(1) for match in _MARK.finditer(template)]


def _reference_lines(asset: Asset) -> list[str]:
    """The asset's lines after the change, the notice not yet added. In a field
    with a limit, a price takes the short unit only when the long one would
    put the field over."""
    lines = []
    for line in asset.template.split("\n"):
        new = render(line, True)
        for label, limit in LIMITS.get(asset.kind, []):
            if new.startswith(f"{label}: ") and len(new) - len(label) - 2 > limit:
                new = render(line, True, short=True)
        lines.append(new)
    return lines


@lru_cache(maxsize=None)
def original(asset_id: str) -> str:
    return render(_BY_ID[asset_id].template, False)


@lru_cache(maxsize=None)
def expected(asset_id: str) -> str:
    asset = _BY_ID[asset_id]
    lines = _reference_lines(asset)
    if asset.kind in NOTICE_TYPES:
        lines += ["", NOTICE]
    return "\n".join(lines)


def changes(asset_id: str) -> bool:
    return original(asset_id) != expected(asset_id)


def changed_ids() -> list[str]:
    return [asset.id for asset in ASSETS if changes(asset.id)]


def price_mentions_changed() -> int:
    """Amounts of money that show a different figure after the change. The
    sentence for existing customers keeps its amount and is not a mark here."""
    count = 0
    for asset in ASSETS:
        for spec in _marks(asset.template):
            if spec.split(":")[0] in _PRICE_KINDS and render(f"[[{spec}]]", False) != render(f"[[{spec}]]", True):
                count += 1
    return count


def answers() -> dict[int, float]:
    """A1 assets changed, A2 amounts of money changed, A3 the renamed plan's new yearly price."""
    return {1: len(changed_ids()), 2: price_mentions_changed(), 3: float(yearly(RENAMED, True))}


def _old_amounts() -> frozenset[Decimal]:
    """Every figure the change replaces: the old prices, yearly prices,
    savings and differences."""
    figures = set()
    for plan in PLANS:
        figures |= {monthly(plan, False), yearly(plan, False), saving(plan, False)}
    for asset in ASSETS:
        for spec in _marks(asset.template):
            if spec.startswith("diff:"):
                _kind, high, low = spec.split(":")
                figures.add(monthly(high, False) - monthly(low, False))
    return frozenset(Decimal(figure) for figure in figures)


OLD_AMOUNTS = _old_amounts()


# ── The documents the candidate reads ────────────────────────────────────────

def change_brief_md() -> str:
    rows = "\n".join(
        f"| {old_name if old_name == new_name else f'{old_name}, renamed {new_name}'} "
        f"| {money(monthly(plan, False))}/month | {new_price(plan, 'month')} "
        f"| {money(yearly(plan, False))}/year | {new_price(plan, 'year')} |"
        for plan, (old_name, new_name, _before, _after) in PLANS.items())
    ad_limits = " and ".join(f"`{label}:` at most {limit} characters" for label, limit in LIMITS["ad"])
    [(banner_label, banner_limit)] = LIMITS["in-app banner"]
    named = [f"the {asset.kind} ({asset.id})" for asset in ASSETS if asset.kind in NOTICE_TYPES]
    notice_assets = ", ".join(named[:-1]) + " and " + named[-1]
    return f"""# {BRAND} price change: the brief

{BRAND} sells online booking, card payments and class reminders to yoga and fitness studios. On {EFFECTIVE} its prices go up, one plan gets a new name and the free trial gets longer. All 14 assets in assets.md go live on {EFFECTIVE}, so each must read as it should from that day. Update every asset to this brief: change everything it changes, and nothing else.

## 1. Prices

| Plan | Monthly until {LAST_OLD_DAY} | Monthly from {EFFECTIVE} | Yearly until {LAST_OLD_DAY} | Yearly from {EFFECTIVE} |
|---|---|---|---|---|
{rows}

A yearly plan costs {YEARLY_MONTHS} times the monthly price, before and after the change. The copy also states two figures worked out from the prices. Work each one out again from the new prices:

- **What paying yearly saves** on a plan: {SAVING_MONTHS} times its monthly price, minus its yearly price.
- **The difference between two plans**: the higher monthly price minus the lower.

Every price, yearly price, saving and difference in the copy changes to its new figure, however the old copy words it, with one exception: the sentence for existing customers in section 4.

## 2. The plan's new name

The {OLD_NAME} plan is now called {NEW_NAME}. Change the name wherever it names the plan: in a heading, a subject line, a list, the middle of a sentence, and a possessive ({OLD_NAME}'s becomes {NEW_NAME}'s). As the plan's name, {OLD_NAME} always starts with a capital S. Leave these alone, though they contain the same letters:

- `studio` and `studios` in lower case. They mean a customer's business, not the plan.
- `{FEATURE}`, the calendar sync feature. It keeps its name.
- `{PLAN_URL}`. The address keeps working after the change and stays exactly as it is.

## 3. The free trial

The free trial is now {NEW_TRIAL_DAYS} days. It was {OLD_TRIAL_DAYS} days. Change every statement of its length, however the old copy writes it (`14 days`, `14-day`, `two weeks`, `two-week`, `Two weeks` at the start of a sentence), to the same thing in days: `30 days` where the copy says how long (`free for 30 days`, `30 days free`), and `30-day` where the length describes the trial (`a 30-day free trial`).

## 4. Existing customers keep their price until {KEEP_UNTIL}

Customers who subscribed before {EFFECTIVE} keep the price they pay today until {KEEP_UNTIL}, and pay the new price from {EXISTING_PAY_NEW_FROM}. One asset is written to existing customers: {EXISTING_CUSTOMER_ASSET}, sent to customers on the plan being renamed. In it, the sentence that tells the reader what they pay becomes this sentence, word for word:

{GRANDFATHER}

That is the only place an old price may appear once the change is made, and it is not a price you changed. Every other price in {EXISTING_CUSTOMER_ASSET} is the price of a plan change or a new subscription, and takes its new figure.

## 5. The notice

Four assets end with this sentence, word for word, as a paragraph of its own after everything else in the asset: {notice_assets}.

{NOTICE}

It appears once in each of those four and in no other asset: no email, no ad, not the banner.

## 6. How a price is written

Write every price you change as `{new_price(RENAMED, 'month')}` or `{new_price(RENAMED, 'year')}`: a dollar sign, whole dollars with a comma for thousands (`{new_price('multi', 'year')}`), no cents, then `/month` or `/year` with no space before it. This replaces every way the old copy writes a price (`$49 a month`, `$49 per month`, `$49/mo`, `$490 a year`, `$490 per year`), and the words that wrote it (`a month`, `per year`) go with it. A saving or a difference is a dollar amount alone (`{FORMAT_EXAMPLE_AMOUNT}`), and the words around it stay as they are.

In the six ads and the in-app banner, and only there, `/mo` may stand for `/month` and `/yr` for `/year`. It is the only shortening allowed.

## 7. Limits

An ad has two fields, each on a line of its own: {ad_limits}. The in-app banner has `{banner_label}:`, at most {banner_limit} characters, and `Link:`, which has no limit. A limit counts every character after the label and the one space that follows it, spaces and punctuation included. Keep the labels as they are.

## 8. What does not change

- Only the prices, yearly prices, savings and differences of section 1, the plan's name and the trial's length change. A number that is not one of those stays as it is, even when it equals an old price: {BRAND} connects to {INTEGRATIONS}, before and after. The card rate, {CARD_RATE} per booking, does not change.
- Every other word stays exactly as it is: no rewording, no new sentences, no tidying, and no shortening but the one in section 6.
- An asset with nothing in it that this brief changes comes back exactly as it is, character for character.

## 9. The answer block

- A1 is the number of assets whose text you changed.
- A2 is the number of amounts of money in the 14 assets that now show a different figure. Count each written amount once. The price in the sentence of section 4 is the same figure as before, so it does not count.
- A3 is the new yearly price of the renamed plan, in dollars.
"""


def assets_md() -> str:
    parts = [
        f"# {BRAND} customer-facing copy: 14 assets",
        "",
        "Each asset is under a heading with its id and its type. Its text is what is inside the fence below the heading; the fence is not part of it.",
    ]
    for asset in ASSETS:
        parts += ["", f"## {asset.id} ({asset.kind})", "", "```", original(asset.id), "```"]
    return "\n".join(parts) + "\n"


def fixtures() -> dict[str, str]:
    return {"change_brief.md": change_brief_md(), "assets.md": assets_md()}


# ── The reference reply ──────────────────────────────────────────────────────

def _what(asset_id: str) -> str:
    asset = _BY_ID[asset_id]
    kinds = {spec.split(":")[0] for spec in _marks(asset.template)}
    what = []
    if kinds & set(_PRICE_KINDS):
        what.append("prices")
    if "name" in kinds:
        what.append("plan name")
    if "trial" in kinds:
        what.append("trial length")
    if "grandfather" in kinds:
        what.append("existing-customer price sentence")
    if asset.kind in NOTICE_TYPES:
        what.append("notice added")
    return "; ".join(what)


def reference_answer() -> str:
    """A reply that follows the brief to the letter: what a checker must pass."""
    out = [f"The 14 {BRAND} assets, updated to the {EFFECTIVE} price change.", ""]
    for asset in ASSETS:
        out += [f"### {asset.file}", "```", expected(asset.id), "```", ""]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["asset_id", "changed", "what"])
    for asset in ASSETS:
        changed = changes(asset.id)
        writer.writerow([asset.id, "yes" if changed else "no", _what(asset.id) if changed else ""])
    out += [f"### {CHANGE_LOG}", "```csv", buffer.getvalue().rstrip("\n"), "```", ""]
    figures = answers()
    out += [f"A1: {int(figures[1])}", f"A2: {int(figures[2])}", f"A3: {int(figures[3])}", ""]
    return "\n".join(out)


# ── Reading copy: prices, names, trials, sentences ───────────────────────────
# Every pattern is bounded and runs on an asset already cut to
# MAX_ASSET_CHARS, so no reply can make one backtrack for long.

MAX_ASSET_CHARS = 8000
_PRICE = re.compile(
    r"\$ ?(\d{1,9}(?:,\d{3}){0,3})(?:\.(\d{1,2}))?(/month|/mo|/year|/yr| a month| per month| a year| per year)?",
    re.IGNORECASE)
_OLD_NAME = re.compile(r"(?<![A-Za-z])" + OLD_NAME + r"(?![A-Za-z])")
_NEW_NAME = re.compile(r"(?<![A-Za-z])" + NEW_NAME + r"(?![A-Za-z])")
_OLD_TRIAL_RE = re.compile(r"(?<![\w-])(?:14|fourteen)[- ]days?(?![\w-])|(?<![\w-])two[- ]weeks?(?![\w-])", re.IGNORECASE)
_NEW_TRIAL_RE = re.compile(r"(?<![\w-])30[- ]days?(?![\w-])", re.IGNORECASE)
_ANY_TRIAL = re.compile(
    r"(?<![\w-])(?:14|30|fourteen|thirty)[- ]days?(?![\w-])|(?<![\w-])two[- ]weeks?(?![\w-])", re.IGNORECASE)
_NAMEISH = re.compile(r"(?<![A-Za-z])(?:Studio|Growth|studio|growth)")
_INTEGRATION_COUNT = re.compile(r"\d{1,4} integrations")
_LOWER_STUDIO = re.compile(r"(?<![A-Za-z/])studios?(?![A-Za-z])")
_STOP = frozenset("a an and are at for from in is it of on the their to your you we our".split())
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
# What looks like the change and is not: each a literal, counted where it
# appears, or a pattern, counted by its matches.
_LOOKALIKES = (INTEGRATIONS, FEATURE, PLAN_URL, _LOWER_STUDIO)
# A sentence carries the notice in other words when it holds this share of
# the notice's words (two sentences together, a higher share).
NOTICE_LIKE_ONE, NOTICE_LIKE_TWO = 0.6, 0.7


def normalise(text: str) -> str:
    """Line endings as "\\n", no trailing space on a line, no blank lines at either end."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _collapse(text: str) -> str:
    return " ".join(text.split())


def sentences(line: str) -> list[str]:
    """A line split after a full stop, question or exclamation mark that a space follows."""
    text = line.strip()
    out, start = [], 0
    for index, char in enumerate(text):
        if char in ".!?" and text[index + 1:index + 2] == " ":
            out.append(text[start:index + 1].strip())
            start = index + 1
    out.append(text[start:].strip())
    return [sentence for sentence in out if sentence]


def _without_grandfather(text: str) -> str:
    """The text with each sentence for existing customers taken out, from its
    opening words to the end of its sentence (300 characters at most): that
    sentence is checked on its own, and the old price it keeps is not a price
    left behind."""
    lowered = text.translate(_ASCII_LOWER)
    out, start = [], 0
    while True:
        index = lowered.find(_GRANDFATHER_ANCHOR, start)
        if index < 0:
            break
        end = lowered.find(". ", index)
        end = len(text) if end < 0 else end + 1
        out += [text[start:index], " "]
        start = min(end, index + 300)
    out.append(text[start:])
    return "".join(out)


def _price_key(written: str, short_ok: bool) -> str:
    if short_ok:
        for short, long in SHORT_UNITS.items():
            if written.endswith(short):
                return written[:-len(short)] + long
    return written


def _prices(text: str, short_ok: bool) -> Counter:
    """Each written amount of money as written, outside the sentence for
    existing customers. In a field where the brief allows /mo and /yr, they
    read as /month and /year."""
    return Counter(_price_key(match.group(0), short_ok) for match in _PRICE.finditer(_without_grandfather(_collapse(text))))


def _amount(written: str) -> Decimal:
    match = _PRICE.match(written)
    if not match:
        return Decimal(0)
    whole = match.group(1).replace(",", "")
    return Decimal(f"{whole}.{match.group(2)}" if match.group(2) else whole)


def skeleton(text: str) -> str:
    """A sentence with what the brief may change taken out: each amount of
    money with its unit words, each trial length, the plan's names (and the
    letters they share with studio and StudioSync), each count of
    integrations. Two sentences with the same skeleton differ only there."""
    text = _PRICE.sub("§", text)
    text = _ANY_TRIAL.sub("†", text)
    text = _NAMEISH.sub("¤", text)
    return _INTEGRATION_COUNT.sub("# integrations", text)


def _content_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]{1,40}", text.translate(_ASCII_LOWER)) if word not in _STOP}


_NOTICE_WORDS = frozenset(_content_words(NOTICE))


def _notice_share(text: str) -> float:
    return len(_content_words(text) & _NOTICE_WORDS) / len(_NOTICE_WORDS)


# The notice word for word, wherever a line break falls inside it.
_NOTICE_RE = re.compile(r"\s+".join(re.escape(word) for word in NOTICE.split(" ")))


def _notice_count(text: str) -> tuple[int, int]:
    """(times the notice is there word for word, sentences that carry it in other words)."""
    exact = len(_NOTICE_RE.findall(text))
    rest = [sentence for line in _NOTICE_RE.sub(" ", text).split("\n") for sentence in sentences(line)]
    variants = 0
    index = 0
    while index < len(rest):
        if _notice_share(rest[index]) >= NOTICE_LIKE_ONE:
            variants += 1
            index += 1
        elif index + 1 < len(rest) and _notice_share(rest[index] + " " + rest[index + 1]) >= NOTICE_LIKE_TWO:
            variants += 1
            index += 2
        else:
            index += 1
    return exact, variants


def field(text: str, label: str) -> str | None:
    """The value of a field line ("Headline: ...", "**Body:** ..."), or None."""
    want = label.lower() + ":"
    for line in text.split("\n"):
        core = line[:1000].strip().lstrip("-*>#").strip().lstrip("*_").strip()
        if core[:len(want)].lower() == want:
            return core[len(want):].lstrip("*_").strip()
    return None


# ── What each asset puts at stake ────────────────────────────────────────────

def _lookalike_count(text: str, item: str | re.Pattern[str]) -> int:
    return text.count(item) if isinstance(item, str) else len(item.findall(text))


@lru_cache(maxsize=None)
def _plan(asset_id: str) -> dict:
    """What the checker holds a reply's asset to, all from the reference."""
    asset = _BY_ID[asset_id]
    survivable: Counter = Counter()
    changed: Counter = Counter()
    for old_line, new_line in zip(original(asset_id).split("\n"), _reference_lines(asset)):
        old_parts, new_parts = sentences(old_line), sentences(new_line)
        if len(old_parts) != len(new_parts):
            raise ValueError(f"{asset_id}: a change splits or joins sentences: {old_line!r}")
        for old, new in zip(old_parts, new_parts):
            if old == new:
                survivable[old] += 1
            elif new != GRANDFATHER:
                changed[skeleton(new)] += 1
    text = expected(asset_id)
    short_ok = asset.kind in LIMITS
    return {
        "original": normalise(original(asset_id)),
        "short_ok": short_ok,
        "prices": _prices(text, short_ok),
        "new_names": len(_NEW_NAME.findall(text)),
        "new_trials": len(_NEW_TRIAL_RE.findall(text)),
        "lookalikes": [_lookalike_count(original(asset_id), item) for item in _LOOKALIKES],
        "survivable": survivable,
        "changed": changed,
        "fields": LIMITS.get(asset.kind, []),
    }


def _old_left(text: str, plan: dict) -> int:
    """Old figures in the reply that are not the reference's."""
    extra = _prices(text, plan["short_ok"]) - plan["prices"]
    return sum(count for written, count in extra.items() if _amount(written) in OLD_AMOUNTS)


def _price_errors(text: str, plan: dict) -> int:
    """New figures written wrongly or not at all: an amount the reference does
    not have that is not an old figure, and an amount the reference has that
    nothing in the reply stands in for."""
    found = _prices(text, plan["short_ok"])
    extra, short = found - plan["prices"], plan["prices"] - found
    wrong = sum(count for written, count in extra.items() if _amount(written) not in OLD_AMOUNTS)
    return wrong + max(0, sum(short.values()) - sum(extra.values()))


def _name_errors(text: str, plan: dict) -> int:
    return max(len(_OLD_NAME.findall(text)), plan["new_names"] - len(_NEW_NAME.findall(text)))


def _trial_errors(text: str, plan: dict) -> int:
    return max(len(_OLD_TRIAL_RE.findall(text)), plan["new_trials"] - len(_NEW_TRIAL_RE.findall(text)))


def _collateral(text: str, plan: dict) -> int:
    collapsed = _collapse(text)
    bare = skeleton(collapsed)
    return (sum(max(0, need - collapsed.count(sentence)) for sentence, need in plan["survivable"].items())
            + sum(max(0, need - bare.count(sentence)) for sentence, need in plan["changed"].items()))


def _limit_errors(text: str, plan: dict) -> int:
    errors = 0
    for label, limit in plan["fields"]:
        value = field(text, label)
        errors += value is None or len(value) > limit
    return errors


_YES, _NO = {"yes", "y", "true", "changed"}, {"no", "n", "false", "unchanged"}


def _log_errors(text: str, replies: dict[str, str | None]) -> int:
    rows = common.tables(text, [CHANGE_LOG])[CHANGE_LOG] or []
    flags: dict[str, list[str]] = {}
    stray = 0
    for row in rows:
        key = common.norm(common.cell(row, "asset_id", "asset", "id"))
        key = key.removesuffix(".md")
        if key in _BY_ID:
            flags.setdefault(key, []).append(common.norm(common.cell(row, "changed")))
        else:
            stray += 1
    errors = stray
    for asset in ASSETS:
        given = flags.get(asset.id)
        if not given:
            errors += 1
            continue
        errors += len(given) - 1
        flag = given[-1]
        if flag not in _YES | _NO:
            errors += 1
            continue
        said = flag in _YES
        errors += said != changes(asset.id)
        reply = replies[asset.id]
        if reply is not None:
            errors += said != (reply != _plan(asset.id)["original"])
    return errors


FACTS = (
    "workflow_missing_asset_count",
    "workflow_change_log_error_count",
    "workflow_old_price_left_count",
    "workflow_new_price_error_count",
    "workflow_plan_name_error_count",
    "workflow_trial_error_count",
    "workflow_grandfather_error_count",
    "workflow_lookalike_changed_count",
    "workflow_unchanged_asset_altered_count",
    "workflow_notice_missing_count",
    "workflow_notice_not_verbatim_count",
    "workflow_notice_misplaced_count",
    "workflow_limit_error_count",
    "workflow_collateral_change_count",
)


def facts(response_text: str, workflow: str = TASK_ID) -> dict[str, int]:
    """Counts of what a reply got wrong, each against the reference.

    An asset the brief changes that is missing, or that comes back exactly as
    it was, is not done: it counts against every check of that asset as all
    of its work left undone, so leaving an asset out, or handing it back
    untouched, never earns credit for what was not attempted. An asset the
    brief leaves alone is held to one check: that it comes back as it was."""
    text = response_text if isinstance(response_text, str) else ""
    found = common.sections(text, FILE_NAMES)
    replies = {
        asset.id: (normalise(found[asset.file][:MAX_ASSET_CHARS]) if found[asset.file] is not None else None)
        for asset in ASSETS
    }
    out = dict.fromkeys(FACTS, 0)
    out["workflow_missing_asset_count"] = sum(reply is None for reply in replies.values())
    out["workflow_change_log_error_count"] = _log_errors(text, replies)
    for asset in ASSETS:
        plan = _plan(asset.id)
        reply = replies[asset.id]
        if not changes(asset.id):
            out["workflow_unchanged_asset_altered_count"] += reply != plan["original"]
            continue
        done = reply is not None and reply != plan["original"]
        copy = reply if done else plan["original"]
        out["workflow_old_price_left_count"] += _old_left(copy, plan)
        out["workflow_plan_name_error_count"] += _name_errors(copy, plan)
        out["workflow_trial_error_count"] += _trial_errors(copy, plan)
        notice = asset.kind in NOTICE_TYPES
        if not done:
            out["workflow_new_price_error_count"] += sum(plan["prices"].values())
            out["workflow_lookalike_changed_count"] += sum(plan["lookalikes"])
            out["workflow_grandfather_error_count"] += asset.id == EXISTING_CUSTOMER_ASSET
            out["workflow_notice_missing_count"] += notice
            out["workflow_notice_not_verbatim_count"] += notice
            out["workflow_notice_misplaced_count"] += not notice
            out["workflow_limit_error_count"] += len(plan["fields"])
            out["workflow_collateral_change_count"] += sum(plan["survivable"].values()) + sum(plan["changed"].values())
            continue
        out["workflow_new_price_error_count"] += _price_errors(copy, plan)
        out["workflow_lookalike_changed_count"] += sum(
            max(0, need - _lookalike_count(copy, item)) for need, item in zip(plan["lookalikes"], _LOOKALIKES))
        collapsed = _collapse(copy)
        if asset.id == EXISTING_CUSTOMER_ASSET:
            out["workflow_grandfather_error_count"] += collapsed.count(GRANDFATHER) != 1
        else:
            out["workflow_grandfather_error_count"] += _GRANDFATHER_ANCHOR in collapsed.translate(_ASCII_LOWER)
        exact, variants = _notice_count(copy)
        if notice:
            out["workflow_notice_missing_count"] += exact == 0 and variants == 0
            out["workflow_notice_not_verbatim_count"] += exact > 1 or variants > 0
        else:
            out["workflow_notice_misplaced_count"] += exact + variants > 0
        out["workflow_limit_error_count"] += _limit_errors(copy, plan)
        out["workflow_collateral_change_count"] += _collateral(copy, plan)
    return {name: int(value) for name, value in out.items()}
