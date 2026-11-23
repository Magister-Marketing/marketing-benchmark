"""Workflow task: build a search account from a keyword export.

The brief is an account standard a paid-search lead would hand over: which
searches the business must not pay for, how campaigns and ad groups are cut,
which match type a keyword gets, which negatives follow, how the daily budget
is set, and what an ad may say. The work is applying it to every keyword of an
export without one slip, then writing an ad for each ad group that results.

Everything here is derived from the constants below: the rules document the
candidate reads, the keyword export, the reference answer and the checker. A
rule cannot say one thing in the brief and another in the grader.

All brands, people and figures are invented.
"""
from __future__ import annotations

import csv
import io
import random
import re
from decimal import ROUND_DOWN, Decimal
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

TASK_ID = "search-account-build"
FIXTURE_DIR = Path("eval_runner") / "fixtures" / "search-account-build"
FILES = ["keywords.csv", "excluded.csv", "negatives.csv", "budgets.csv", "ads.csv"]

BRAND = "Tidewater"
BRAND_TERM = "tidewater"

# Searches the business does not pay for, in the order the reasons apply: a
# keyword that matches two themes is excluded for the first.
EXCLUSIONS: list[tuple[str, str, list[str]]] = [
    ("competitor", "Another maker's name", [
        "liftwell", "ergovo", "perchly", "stanza desks", "oakline", "varidian", "deskmate", "uprise"]),
    ("unserved_location", "A place Tidewater does not ship to", [
        "uk", "canada", "australia", "hawaii", "alaska", "europe", "toronto", "london"]),
    ("not_sold", "Something Tidewater does not sell or do", [
        "used", "second hand", "refurbished", "rental", "rent", "repair", "replacement parts", "diy",
        "plans", "treadmill", "converter", "riser", "kids"]),
    ("informational", "Research with no purchase in it", [
        "how to", "what is", "benefits", "vs", "reddit", "ideas", "worth it", "calories"]),
]

# Campaigns in the order they claim a keyword that is not excluded. The last
# takes whatever is left.
CAMPAIGNS: list[tuple[str, list[str] | None]] = [
    ("Brand", [BRAND_TERM]),
    ("Frames", ["frame", "frames", "legs"]),
    ("Desktops", ["desktop", "desktops", "tabletop"]),
    ("Monitor Arms", ["monitor arm", "monitor arms", "monitor mount"]),
    ("Accessories", ["cable", "mat", "desk drawer", "casters", "power strip"]),
    ("Desks", None),
]

# Ad groups inside each campaign, in the order they claim a keyword. The last
# of each takes whatever is left.
AD_GROUPS: dict[str, list[tuple[str, list[str] | None]]] = {
    "Brand": [("Core", None)],
    "Desks": [
        ("L-Shaped", ["l shaped", "corner"]),
        ("Electric", ["electric", "motorized", "dual motor"]),
        ("Manual", ["manual", "crank"]),
        ("Gaming", ["gaming"]),
        ("Size", ["48 inch", "60 inch", "72 inch", "small", "large", "wide"]),
        ("Finish", ["bamboo", "walnut", "oak", "white", "black"]),
        ("Price", ["price", "cheap", "sale", "deal", "under 500"]),
        ("General", None),
    ],
    "Frames": [
        ("Motor", ["dual motor", "single motor"]),
        ("L-Shaped", ["l shaped", "corner"]),
        ("Finish", ["black", "white", "silver"]),
        ("General", None),
    ],
    "Desktops": [
        ("Bamboo", ["bamboo"]),
        ("Hardwood", ["walnut", "oak", "maple"]),
        ("Laminate", ["laminate"]),
        ("Size", ["48 inch", "60 inch", "72 inch"]),
        ("General", None),
    ],
    "Monitor Arms": [("Dual", ["dual"]), ("Single", ["single"]), ("General", None)],
    "Accessories": [
        ("Cable Management", ["cable"]),
        ("Mats", ["mat"]),
        ("Drawers", ["desk drawer"]),
        ("Other", None),
    ],
}

EXACT_FROM_SEARCHES = 1000
CLICK_RATE = {"Brand": Decimal("0.15")}
DEFAULT_CLICK_RATE = Decimal("0.04")
DAYS_PER_MONTH = Decimal("30.4")
DAILY_CAP = Decimal("100.00")
BUDGET_FLOOR = Decimal("5.00")

HEADLINE_MAX = 30
DESCRIPTION_MAX = 90
SHIPPING_LINE = "Free shipping to the lower 48"
# What the first headline of an ad must name, by campaign.
CAMPAIGN_NOUN = {
    "Brand": "Tidewater",
    "Desks": "Standing Desk",
    "Frames": "Desk Frame",
    "Desktops": "Desktop",
    "Monitor Arms": "Monitor Arm",
    "Accessories": "Desk",
}
# Ad groups whose name after the bar is not a thing a headline has to name.
UNNAMED_BUCKETS = {"Core", "General", "Other"}
BANNED_CLAIMS = ["best", "cheapest", "#1", "guarantee", "guaranteed", "lifetime", "free returns"]
# The only prices an ad may state, by campaign. Brand ads may state any of them.
PRICES = {"Desks": 449, "Frames": 289, "Desktops": 129, "Monitor Arms": 59}

_VOLUMES = [20, 30, 40, 50, 70, 90, 110, 140, 170, 210, 260, 320, 390, 480, 590, 720, 880,
            1000, 1300, 1600, 1900, 2400, 2900, 3600, 4400, 5400, 6600, 8100]


# ── The rules, applied ────────────────────────────────────────────────────────

def exclusion_reason(keyword: str) -> str | None:
    kw = common.words(keyword)
    for code, _label, terms in EXCLUSIONS:
        if any(common.has_phrase(kw, common.words(term)) for term in terms):
            return code
    return None


def placement(keyword: str) -> tuple[str, str]:
    """(campaign, "Campaign | Bucket") of a keyword that is not excluded."""
    kw = common.words(keyword)
    campaign = next(
        name for name, terms in CAMPAIGNS
        if terms is None or any(common.has_phrase(kw, common.words(term)) for term in terms)
    )
    bucket = next(
        name for name, terms in AD_GROUPS[campaign]
        if terms is None or any(common.has_phrase(kw, common.words(term)) for term in terms)
    )
    return campaign, f"{campaign} | {bucket}"


def match_type(campaign: str, searches: int) -> str:
    return "exact" if campaign == "Brand" or searches >= EXACT_FROM_SEARCHES else "phrase"


# ── The keyword export ────────────────────────────────────────────────────────

_DESK_HEADS = ["standing desk", "sit stand desk", "adjustable desk", "height adjustable desk", "stand up desk"]
_PATTERNS: list[tuple[list[str], list[str], int]] = [
    # (modifiers, heads, how many to draw)
    (["l shaped", "corner"], _DESK_HEADS, 9),
    (["electric", "motorized", "dual motor"], _DESK_HEADS, 12),
    (["manual", "crank"], _DESK_HEADS, 6),
    (["gaming"], _DESK_HEADS, 4),
    (["48 inch", "60 inch", "72 inch", "small", "large", "wide"], _DESK_HEADS, 14),
    (["bamboo", "walnut", "oak", "white", "black"], _DESK_HEADS, 12),
    (["price", "cheap", "sale", "deal", "under 500"], _DESK_HEADS, 9),
    (["", "home office", "ergonomic", "for tall people", "with storage", "with memory presets", "quiet"], _DESK_HEADS, 16),
    (["dual motor", "single motor", "l shaped", "corner", "black", "white", "silver", "", "heavy duty", "steel"],
     ["standing desk frame", "desk frame", "adjustable desk frames", "standing desk legs"], 20),
    (["bamboo", "walnut", "oak", "maple", "laminate", "48 inch", "60 inch", "72 inch", "", "solid wood", "rounded"],
     ["desktop", "standing desk desktop", "desktops", "tabletop for standing desk"], 20),
    (["dual", "single", "", "gas spring", "heavy duty", "ultrawide"], ["monitor arm", "monitor arms", "monitor mount"], 12),
    (["under desk", "standing desk", "desk"], ["cable tray", "cable management", "cable organizer"], 6),
    (["anti fatigue", "standing desk", "cushioned"], ["mat", "floor mat"], 5),
    (["under", "slide out", "clamp on"], ["desk drawer", "desk drawer organizer"], 4),
    (["locking", "standing desk", "clamp"], ["casters", "power strip"], 5),
    ([BRAND_TERM], ["standing desk", "desk frame", "desks", "desk reviews", "bamboo desktop", "discount code",
                    "monitor arm", "desk assembly", "customer service", "l shaped desk"], 10),
]
# Keywords written by hand because a rule's edge is the point of them. Each is
# pinned in tests/test_workflow_search_account_build.py.
_PLANTED = [
    "electric l shaped standing desk",            # two Desks buckets: the first in the list wins
    "white gaming standing desk 60 inch",         # three buckets
    "cheap bamboo standing desk",                 # Finish before Price
    "dual motor standing desk frame",             # Frames claims it before Desks; then Motor
    "black l shaped desk frame",                  # Frames: L-Shaped before Finish
    "bamboo desktop for standing desk",           # Desktops before Desks
    "oak desktop 60 inch",                        # Hardwood before Size
    "monitor arm for standing desk",              # Monitor Arms before Desks
    "dual monitor arm for l shaped desk",         # "l shaped" belongs to another campaign's groups
    "standing desk with drawers",                 # not "desk drawer": stays a desk
    "matte black standing desk",                  # "matte" is not "mat"; Finish
    "standing desk cable management tray",        # Accessories
    "tidewater standing desk uk",                 # an exclusion beats Brand
    "tidewater vs liftwell",                      # two reasons: competitor comes first
    "tidewater desk repair",                      # an exclusion beats Brand
    "used liftwell standing desk",                # competitor before not sold
    "how to repair a standing desk",              # not sold before informational
    "standing desk canada free shipping",         # unserved location
    "standing desk benefits",                     # informational
    "standing desk vs sitting",                   # informational
    "is a standing desk worth it",                # informational
    "standing desk ideas for small spaces",       # informational, not Size
    "standing desk converter",                    # not sold
    "desk riser for laptop",                      # not sold
    "treadmill desk",                             # not sold
    "kids standing desk",                         # not sold
    "diy standing desk plans",                    # not sold
    "standing desk rental near me",               # not sold
    "refurbished standing desk",                  # not sold
    "ergovo standing desk review",                # competitor
    "perchly desk frame",                         # competitor
    "stanza desks l shaped",                      # competitor (a two-word name)
    "stanza for standing desk",                   # "stanza" alone is not the competitor's name
    "varidian vs oakline",                        # competitor
    "standing desk london",                       # unserved location
    "standing desk australia",                    # unserved location
    "standing desk delivery hawaii",              # unserved location
    "standing desk europe plug",                  # unserved location
    "standing desk reddit",                       # informational
    "what is a sit stand desk",                   # informational
    "standing desk calories burned",              # informational
    "under 500 standing desk",                    # Price
    "standing desk sale",                         # Price
    "large corner standing desk",                 # L-Shaped before Size
    "manual crank standing desk small",           # Manual before Size
    "rent to own standing desk",                  # not sold ("rent")
]


@lru_cache(maxsize=1)
def export_rows() -> list[dict]:
    """The keyword export, the same every time: every keyword once, with its
    monthly searches and the bid range the planner shows."""
    rng = random.Random(20261120)
    keywords: list[str] = []
    for modifiers, heads, count in _PATTERNS:
        pool = sorted({
            common.norm(f"{modifier} {head}" if rng.random() < 0.7 else f"{head} {modifier}")
            for modifier in modifiers for head in heads
        })
        rng.shuffle(pool)
        keywords += pool[:count]
    keywords += _PLANTED
    rows, seen = [], set()
    for keyword in keywords:
        keyword = common.norm(keyword)
        if keyword in seen:
            continue
        seen.add(keyword)
        length = len(keyword.split())
        top = len(_VOLUMES) - 1 - min(length * 3, 18)
        searches = _VOLUMES[max(0, min(len(_VOLUMES) - 1, int(rng.triangular(0, top + 6, top))))]
        low = round(rng.uniform(0.35, 2.4), 2)
        rows.append({
            "keyword": keyword,
            "avg_monthly_searches": searches,
            "bid_low": f"{low:.2f}",
            "bid_high": f"{round(low * rng.uniform(1.5, 2.9), 2):.2f}",
        })
    rng.shuffle(rows)
    return rows


def export_csv() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["keyword", "avg_monthly_searches", "bid_low", "bid_high"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(export_rows())
    return out.getvalue()


# ── The reference: what the standard produces from the export ────────────────

@lru_cache(maxsize=1)
def reference() -> dict:
    targeted: dict[str, dict] = {}
    excluded: dict[str, str] = {}
    for row in export_rows():
        keyword = row["keyword"]
        reason = exclusion_reason(keyword)
        if reason:
            excluded[keyword] = reason
            continue
        campaign, ad_group = placement(keyword)
        targeted[keyword] = {
            "campaign": campaign, "ad_group": ad_group,
            "match_type": match_type(campaign, row["avg_monthly_searches"]),
            "searches": row["avg_monthly_searches"],
            "bid_mid": (Decimal(row["bid_low"]) + Decimal(row["bid_high"])) / 2,
        }
    every = [common.words(row["keyword"]) for row in export_rows()]
    account_negatives = sorted(
        term for _code, _label, terms in EXCLUSIONS for term in terms
        if any(common.has_phrase(kw, common.words(term)) for kw in every)
    )
    ad_groups = sorted({item["ad_group"] for item in targeted.values()})
    general_negatives: dict[str, list[str]] = {}
    for campaign, buckets in AD_GROUPS.items():
        general = f"{campaign} | General"
        if general not in ad_groups:
            continue
        mine = [common.words(k) for k, item in targeted.items() if item["campaign"] == campaign]
        general_negatives[general] = sorted(
            term for bucket, terms in buckets
            if terms and f"{campaign} | {bucket}" in ad_groups
            for term in terms if any(common.has_phrase(kw, common.words(term)) for kw in mine)
        )
    estimates = {
        campaign: sum(
            (Decimal(item["searches"]) * CLICK_RATE.get(campaign, DEFAULT_CLICK_RATE) * item["bid_mid"]
             for item in targeted.values() if item["campaign"] == campaign), Decimal(0)) / DAYS_PER_MONTH
        for campaign in sorted({item["campaign"] for item in targeted.values()})
    }
    total = sum(estimates.values(), Decimal(0))
    factor = DAILY_CAP / total if total > DAILY_CAP else Decimal(1)
    budgets = {
        campaign: max(BUDGET_FLOOR, (estimate * factor).quantize(Decimal("0.01"), rounding=ROUND_DOWN))
        for campaign, estimate in estimates.items()
    }
    return {
        "targeted": targeted, "excluded": excluded, "account_negatives": account_negatives,
        "general_negatives": general_negatives, "ad_groups": ad_groups, "budgets": budgets,
        "scaled": factor != 1, "estimate_total": total,
    }


def answers() -> dict[int, float]:
    """A1 keywords targeted, A2 keywords excluded, A3 total daily budget."""
    ref = reference()
    return {1: len(ref["targeted"]), 2: len(ref["excluded"]), 3: float(sum(ref["budgets"].values(), Decimal(0)))}


def reference_answer() -> str:
    """A reply that follows the standard to the letter: what a checker must pass."""
    ref = reference()
    out = ["Search account build for Tidewater, from the keyword export and the account standard.", ""]

    def block(name: str, header: list[str], rows: list[list]) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        out.extend([f"### {name}", "```csv", buffer.getvalue().rstrip("\n"), "```", ""])

    block("keywords.csv", ["keyword", "campaign", "ad_group", "match_type"], [
        [k, item["campaign"], item["ad_group"], item["match_type"]] for k, item in sorted(ref["targeted"].items())])
    block("excluded.csv", ["keyword", "reason"], [[k, reason] for k, reason in sorted(ref["excluded"].items())])
    block("negatives.csv", ["level", "scope", "negative", "match_type"], [
        *[["account", "account", term, "phrase"] for term in ref["account_negatives"]],
        *[["ad_group", group, term, "phrase"] for group, terms in sorted(ref["general_negatives"].items()) for term in terms],
    ])
    block("budgets.csv", ["campaign", "daily_budget"], [[c, f"{b:.2f}"] for c, b in sorted(ref["budgets"].items())])
    ads = []
    for group in ref["ad_groups"]:
        campaign, bucket = group.split(" | ")
        noun = CAMPAIGN_NOUN[campaign]
        named = "" if bucket in UNNAMED_BUCKETS else f"{bucket} "
        h1 = f"{named}{noun}"[:HEADLINE_MAX] if campaign != "Brand" else "Tidewater Standing Desks"
        price = f" From ${PRICES[campaign]}." if campaign in PRICES else ""
        ads.append([
            group, h1, "Made by Tidewater", f"Shop {bucket if bucket not in UNNAMED_BUCKETS else campaign} Options"[:HEADLINE_MAX],
            f"{SHIPPING_LINE}.{price}"[:DESCRIPTION_MAX],
            f"{named}{noun.lower()} options, sized to your room. 30-day returns."[:DESCRIPTION_MAX],
        ])
    block("ads.csv", ["ad_group", "h1", "h2", "h3", "d1", "d2"], ads)
    figures = answers()
    out += [f"A1: {int(figures[1])}", f"A2: {int(figures[2])}", f"A3: {figures[3]:.2f}", ""]
    return "\n".join(out)


# ── The documents the candidate reads ────────────────────────────────────────

def _quoted(terms: list[str]) -> str:
    return ", ".join(f"`{term}`" for term in terms)


def business_facts_md() -> str:
    prices = "\n".join(f"- {campaign}: from ${price}" for campaign, price in PRICES.items())
    return f"""# Tidewater: business facts

Tidewater makes height-adjustable standing desks and sells them online, direct.

## What it sells

- Standing desks (complete: a frame and a desktop), electric and manual
- Desk frames on their own, single and dual motor
- Desktops on their own, in bamboo, hardwood and laminate
- Monitor arms
- Accessories: cable management, anti-fatigue mats, desk drawers, casters, power strips

It does not sell used or refurbished desks, rent desks, repair desks or sell
replacement parts, publish DIY plans, or make treadmill desks, desk converters,
desk risers or children's desks.

## Where it ships

The lower 48 United States only. Not Alaska, not Hawaii, nowhere outside the US.

## Prices an ad may state

{prices}

Accessories have no advertised price.

## Offers and policies

- {SHIPPING_LINE}. Always worded exactly that way.
- 30-day returns. The buyer pays return shipping: returns are not free.
- 10-year frame warranty. It is a warranty, never a "guarantee", and never "lifetime".
"""


def account_rules_md() -> str:
    def numbered(items: list[str]) -> str:
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))

    exclusions = numbered([
        f"**{code}** ({label.lower()}): {_quoted(terms)}" for code, label, terms in EXCLUSIONS])
    campaigns = numbered([
        f"**{name}**: " + (_quoted(terms) if terms else "every keyword no earlier campaign claimed")
        for name, terms in CAMPAIGNS])
    groups = []
    for campaign, buckets in AD_GROUPS.items():
        lines = numbered([
            f"`{campaign} | {bucket}`: " + (_quoted(terms) if terms else "every keyword no earlier ad group claimed")
            for bucket, terms in buckets])
        groups.append(f"### {campaign}\n\n{lines}")
    nouns = "\n".join(f"- {campaign}: `{noun}`" for campaign, noun in CAMPAIGN_NOUN.items())
    return f"""# Tidewater search account standard

Every search account we build follows this standard. It is applied to the
keyword export as written: do not improve on it, and do not skip a keyword.

## How a term matches a keyword

A term matches a keyword when all of the term's words appear in the keyword as
whole words, next to each other and in the same order. Case does not matter.
`mat` matches "standing desk mat" and does not match "matte black desk".
`desk drawer` matches "under desk drawer" and does not match "desk with
drawers". A plural is a different word unless it is listed.

## Step 1. Exclude what we do not pay for

Check every keyword against these four themes, in this order. A keyword that
matches a theme is excluded with that theme's reason, and the first theme that
matches is the reason. An excluded keyword goes in no campaign, whatever else
it contains, the brand name included.

{exclusions}

## Step 2. Campaign

Each keyword that is left belongs to the first campaign in this list with a
term that matches it.

{campaigns}

## Step 3. Ad group

Inside its campaign, a keyword belongs to the first ad group in that
campaign's list with a term that matches it. Only that campaign's list
applies. Ad groups are named exactly as written here. An ad group exists only
if at least one keyword lands in it.

{chr(10).join(chr(10) + group for group in groups).strip()}

## Step 4. Match type

- Every keyword in the Brand campaign is `exact`.
- Elsewhere a keyword with {EXACT_FROM_SEARCHES:,} or more average monthly searches is `exact`.
- Every other keyword is `phrase`.

## Step 5. Negative keywords

Two kinds, and no others. All are `phrase` match.

- **Account level:** one negative for every term in Step 1 that matches at
  least one keyword in the export. A term that matches nothing in the export
  gets no negative.
- **In each `General` ad group:** one negative for every term of the other ad
  groups that exist in the same campaign, where that term matches at least one
  keyword targeted in that campaign. This keeps the General ad group from
  taking searches that belong to a more specific one.

## Step 6. Daily budgets

One daily budget per campaign that has keywords.

1. A keyword's expected daily cost is its average monthly searches, times the
   click rate, times the midpoint of its bid range, divided by {DAYS_PER_MONTH}.
   The click rate is {CLICK_RATE['Brand'] * 100:.0f}% in the Brand campaign and {DEFAULT_CLICK_RATE * 100:.0f}% everywhere else.
2. A campaign's estimate is the sum over its targeted keywords.
3. The account has ${DAILY_CAP} a day. If the estimates add up to more, multiply
   every estimate by ${DAILY_CAP} divided by their total.
4. Round each result down to the cent.
5. A campaign that comes out under ${BUDGET_FLOOR} gets ${BUDGET_FLOOR}. Nothing else changes when that happens.

## Step 7. One ad per ad group

Each ad has three headlines and two descriptions.

- A headline is at most {HEADLINE_MAX} characters and a description at most {DESCRIPTION_MAX}, spaces and punctuation included.
- Headline 1 names what the campaign sells, with these exact words (any case):

{nouns}

- Headline 2 contains `{BRAND}`.
- One headline contains the ad group's own name, the part after the bar
  (`L-Shaped`, `Bamboo`, `Cable Management`). A space in place of a hyphen is
  fine. This does not apply to `Core`, `General` and `Other`.
- One description contains the shipping offer exactly as the business facts word it.
- No two headlines of one ad are the same, and no two ad groups share a first headline.
- Never: {_quoted(BANNED_CLAIMS)}.
- A dollar amount in an ad is one of that campaign's advertised prices from the
  business facts. A Brand ad may state any of them. An Accessories ad states none.
"""


def fixtures() -> dict[str, str]:
    return {
        "keyword_export.csv": export_csv(),
        "account_rules.md": account_rules_md(),
        "business_facts.md": business_facts_md(),
    }


# ── The checker ───────────────────────────────────────────────────────────────

def _group_key(text: str) -> str:
    return re.sub(r"\s*\|\s*", " | ", common.norm(text).replace("-", " "))


def facts(response_text: str, workflow: str = TASK_ID) -> dict:
    """Counts of what a reply got wrong. Every count measures work against the
    reference, so a missing file is that many errors, never zero: a reply that
    leaves a deliverable out earns nothing on its checks."""
    ref = reference()
    found = common.tables(response_text, FILES)
    keywords = {common.norm(common.cell(r, "keyword")): r for r in (found["keywords.csv"] or []) if common.cell(r, "keyword")}
    excluded = {common.norm(common.cell(r, "keyword")): r for r in (found["excluded.csv"] or []) if common.cell(r, "keyword")}
    export = {row["keyword"] for row in export_rows()}
    listed = [common.norm(common.cell(r, "keyword")) for name in ("keywords.csv", "excluded.csv") for r in (found[name] or [])]
    listed = [k for k in listed if k]

    targeted = ref["targeted"]
    negatives = found["negatives.csv"] or []
    account = [(common.norm(common.cell(r, "negative", "negative_keyword", "keyword")), common.norm(common.cell(r, "match_type")))
               for r in negatives if common.norm(common.cell(r, "level")) == "account"]
    in_groups = [(_group_key(common.cell(r, "scope", "ad_group")), common.norm(common.cell(r, "negative", "negative_keyword", "keyword")),
                  common.norm(common.cell(r, "match_type")))
                 for r in negatives if common.norm(common.cell(r, "level")).replace(" ", "_") == "ad_group"]
    stray = len(negatives) - len(account) - len(in_groups)
    wanted_account = set(ref["account_negatives"])
    account_errors = stray
    account_errors += sum(1 for term in wanted_account if (term, "phrase") not in account)
    account_errors += sum(1 for term, _kind in set(account) if term not in wanted_account)
    wanted_general = {(_group_key(group), term) for group, terms in ref["general_negatives"].items() for term in terms}
    general_errors = sum(1 for group, term in wanted_general if (group, term, "phrase") not in in_groups)
    general_errors += sum(1 for group, term, _kind in set(in_groups) if (group, term) not in wanted_general)

    budgets = {common.norm(common.cell(r, "campaign")): common.money(common.cell(r, "daily_budget", "budget"))
               for r in (found["budgets.csv"] or [])}
    budget_errors = sum(1 for name in budgets if name not in {common.norm(c) for c in ref["budgets"]})
    for campaign, target in ref["budgets"].items():
        given = budgets.get(common.norm(campaign))
        if given is None or abs(given - target) > max(Decimal("0.02"), target * Decimal("0.01")):
            budget_errors += 1

    ads = {_group_key(common.cell(r, "ad_group")): r for r in (found["ads.csv"] or []) if common.cell(r, "ad_group")}
    ad_rows = [r for r in (found["ads.csv"] or []) if common.cell(r, "ad_group")]
    wanted_groups = {_group_key(group): group for group in ref["ad_groups"]}
    coverage_errors = sum(1 for key in wanted_groups if sum(_group_key(common.cell(r, "ad_group")) == key for r in ad_rows) != 1)
    coverage_errors += sum(1 for key in ads if key not in wanted_groups)
    limit_errors = required_errors = copy_violations = 0
    first_headlines: list[str] = []
    for key, group in wanted_groups.items():
        row = ads.get(key)
        campaign, bucket = group.split(" | ")
        if row is None:
            limit_errors += 5
            required_errors += 3 + (bucket not in UNNAMED_BUCKETS)
            copy_violations += 1
            continue
        headlines = [common.cell(row, name) for name in ("h1", "h2", "h3")]
        descriptions = [common.cell(row, name) for name in ("d1", "d2")]
        limit_errors += sum(1 for text in headlines if not text or len(text) > HEADLINE_MAX)
        limit_errors += sum(1 for text in descriptions if not text or len(text) > DESCRIPTION_MAX)
        flat = [common.norm(text).replace("-", " ") for text in headlines]
        required_errors += common.norm(CAMPAIGN_NOUN[campaign]) not in flat[0]
        required_errors += BRAND_TERM not in flat[1]
        if bucket not in UNNAMED_BUCKETS:
            required_errors += not any(common.norm(bucket).replace("-", " ") in text for text in flat)
        required_errors += not any(common.norm(SHIPPING_LINE) in common.norm(text) for text in descriptions)
        every = " \n ".join(headlines + descriptions)
        lowered = common.norm(every)
        copy_violations += sum(1 for claim in BANNED_CLAIMS if re.search(
            r"(?<![a-z0-9])" + re.escape(claim) + r"(?![a-z0-9])", lowered))
        allowed = set(PRICES.values()) if campaign == "Brand" else {PRICES[campaign]} if campaign in PRICES else set()
        copy_violations += sum(
            1 for amount in re.findall(r"\$\s?(\d[\d,]*(?:\.\d+)?)", every)
            if float(amount.replace(",", "")) not in allowed)
        copy_violations += len(flat) - len(set(flat))
        first_headlines.append(flat[0])
    copy_violations += len(first_headlines) - len(set(first_headlines))

    def wrong(field: str, reference_field: str, key=common.norm) -> int:
        return sum(
            1 for keyword, item in targeted.items()
            if keyword not in keywords or key(common.cell(keywords[keyword], field)) != key(item[reference_field])
        )

    return {
        "workflow_missing_file_count": sum(1 for name in FILES if found[name] is None),
        # Keywords of the export in neither file, listed twice, or not in the export at all.
        "workflow_keyword_accounting_error_count": (
            len(export - set(listed)) + (len(listed) - len(set(listed))) + len(set(listed) - export)),
        "workflow_targeting_error_count": len(set(targeted) ^ (set(keywords) & export)),
        "workflow_wrong_reason_count": sum(
            1 for keyword, reason in ref["excluded"].items()
            if keyword not in excluded or common.norm(common.cell(excluded[keyword], "reason", "reason_code")).replace(" ", "_") != reason
        ),
        "workflow_wrong_campaign_count": wrong("campaign", "campaign"),
        "workflow_wrong_ad_group_count": wrong("ad_group", "ad_group", _group_key),
        "workflow_wrong_match_type_count": wrong("match_type", "match_type"),
        "workflow_account_negative_error_count": account_errors,
        "workflow_general_negative_error_count": general_errors,
        "workflow_budget_error_count": budget_errors,
        "workflow_ad_coverage_error_count": coverage_errors,
        "workflow_ad_limit_error_count": limit_errors,
        "workflow_ad_required_error_count": required_errors,
        "workflow_ad_copy_violation_count": copy_violations,
    }
