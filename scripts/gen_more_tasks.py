#!/usr/bin/env python3
"""Generate the fixtures of the eight tasks added in November 2026, and pin their targets.

Tasks: seo-content-brief, seo-technical-triage, search-terms-negatives,
lifecycle-reengagement, ab-test-readout, social-calendar-limits,
monthly-report-reconcile, positioning-from-competitors.

Deterministic: every table is either written out below or drawn from a seeded
generator, so re-running reproduces identical files. The figures come from
`eval_runner/task_references.py`, which reads only fixture text and is the same
code that gives the judge its reference totals; the limits and dates of the
social brief come from `eval_runner/task_facts.py`, which also checks them.

A task file's prose (its prompt and the wording of each check) is written by
hand. Everything a program decides is pinned here: each programmatic
condition with its target and tolerance, the `answers` field, the oracle list
of each critical criterion, and the definition and answer lines the prompt
must carry. `--sync` writes those into the task files; `--check` (and
tests/test_more_tasks.py) reports every difference and never raises on a task
file it can parse.

All brands, people, URLs and figures here are invented.

Usage:
    python3 scripts/gen_more_tasks.py --write   # (re)write the fixtures
    python3 scripts/gen_more_tasks.py --sync    # write the pinned values into the task files
    python3 scripts/gen_more_tasks.py --check   # report drift, change nothing
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import random
import re
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from eval_runner import task_facts, task_references  # noqa: E402

FIXTURES = REPO_ROOT / "eval_runner" / "fixtures"
TASKS = REPO_ROOT / "eval_runner" / "tasks"


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _money(value: Decimal | float) -> str:
    return f"{Decimal(str(value)):.2f}"


# --------------------------------------------------------------- seo-content-brief

SEO_HEADER = ["keyword", "topic", "monthly_searches", "difficulty", "intent", "current_rank", "ranking_url"]
# keyword, topic, monthly searches, difficulty (0-100), intent, current rank, ranking URL
SEO_KEYWORDS = [
    ("how to cold brew tea", "cold brew tea", 3600, 28, "informational", "", ""),
    ("cold brew tea ratio", "cold brew tea", 1900, 19, "informational", "", ""),
    ("how long to cold brew tea", "cold brew tea", 1600, 22, "informational", "", ""),
    ("best tea for cold brew", "cold brew tea", 1300, 34, "commercial", "", ""),
    ("cold brew green tea", "cold brew tea", 1000, 31, "informational", "", ""),
    ("cold brew tea caffeine", "cold brew tea", 720, 24, "informational", "", ""),
    ("can you cold brew tea bags", "cold brew tea", 590, 17, "informational", "", ""),
    ("cold brew tea vs iced tea", "cold brew tea", 880, 26, "informational", "", ""),
    ("cold brew tea maker", "cold brew tea", 2400, 48, "transactional", "", ""),
    ("cold brew tea recipe", "cold brew tea", 1300, 52, "informational", "", ""),
    ("does cold brew tea go bad", "cold brew tea", 480, 15, "informational", 9, "/blog/how-long-does-brewed-tea-last"),
    ("best green tea", "green tea", 14800, 62, "commercial", 4, "/guides/best-green-tea"),
    ("green tea benefits", "green tea", 12100, 71, "informational", "", ""),
    ("green tea caffeine", "green tea", 6600, 38, "informational", 7, "/blog/green-tea-caffeine"),
    ("how to brew green tea", "green tea", 2900, 41, "informational", "", ""),
    ("green tea temperature", "green tea", 1300, 29, "informational", "", ""),
    ("sencha vs gyokuro", "green tea", 880, 33, "informational", "", ""),
    ("japanese green tea brands", "green tea", 1000, 44, "commercial", "", ""),
    ("loose leaf green tea", "green tea", 2400, 55, "transactional", 15, "/collections/green-tea"),
    ("matcha powder", "matcha", 9900, 68, "transactional", "", ""),
    ("ceremonial grade matcha", "matcha", 4400, 57, "commercial", "", ""),
    ("how to make matcha", "matcha", 5400, 49, "informational", "", ""),
    ("matcha vs green tea", "matcha", 2400, 36, "informational", "", ""),
    ("matcha caffeine", "matcha", 1900, 40, "informational", 6, "/blog/matcha-caffeine"),
    ("how to whisk matcha", "matcha", 1000, 27, "informational", "", ""),
    ("matcha latte recipe", "matcha", 6600, 61, "informational", "", ""),
    ("best tea for sleep", "herbal tea for sleep", 8100, 58, "commercial", "", ""),
    ("chamomile tea benefits", "herbal tea for sleep", 5400, 66, "informational", "", ""),
    ("does chamomile tea make you sleepy", "herbal tea for sleep", 1600, 30, "informational", "", ""),
    ("herbal tea before bed", "herbal tea for sleep", 720, 21, "informational", "", ""),
    ("valerian root tea", "herbal tea for sleep", 2900, 47, "informational", "", ""),
    ("lavender tea", "herbal tea for sleep", 1900, 39, "informational", "", ""),
    ("how to store loose leaf tea", "tea storage", 1900, 23, "informational", 3, "/blog/how-to-store-loose-leaf-tea"),
    ("does tea expire", "tea storage", 2400, 35, "informational", 8, "/blog/does-tea-expire"),
    ("tea storage containers", "tea storage", 1300, 42, "transactional", "", ""),
    ("how long does loose leaf tea last", "tea storage", 1000, 25, "informational", "", ""),
    ("can you freeze tea leaves", "tea storage", 390, 14, "informational", "", ""),
    ("best tea tins", "tea storage", 880, 37, "commercial", "", ""),
    ("oolong tea benefits", "oolong", 6600, 64, "informational", "", ""),
    ("what is oolong tea", "oolong", 4400, 46, "informational", "", ""),
    ("oolong tea caffeine", "oolong", 1600, 33, "informational", "", ""),
    ("how to brew oolong tea", "oolong", 1300, 28, "informational", "", ""),
    ("oolong vs green tea", "oolong", 1000, 31, "informational", "", ""),
    ("milk oolong", "oolong", 880, 44, "commercial", "", ""),
    ("tea gift set", "tea gifts", 5400, 59, "transactional", "", ""),
    ("gifts for tea lovers", "tea gifts", 4400, 53, "commercial", "", ""),
    ("tea sampler", "tea gifts", 2900, 45, "transactional", 22, "/collections/samplers"),
    ("how to host a tea tasting", "tea gifts", 590, 18, "informational", "", ""),
    ("how to make iced tea", "iced tea", 8100, 51, "informational", "", ""),
    ("sweet tea recipe", "iced tea", 6600, 56, "informational", "", ""),
    ("iced tea concentrate", "iced tea", 720, 29, "informational", "", ""),
    ("is sun tea safe", "iced tea", 880, 20, "informational", "", ""),
    ("best iced tea bags", "iced tea", 1300, 40, "commercial", "", ""),
]

SEO_PAGES_MD = """\
# Fernhollow Tea: existing pages (site inventory, 2026-04)

Fernhollow Tea sells loose-leaf tea and brewing gear online. Site: https://www.fernhollowtea.example

| URL | Type | What it is |
|---|---|---|
| /guides/best-green-tea | Buying guide | Ranked picks of our green teas with prices and tasting notes |
| /blog/green-tea-caffeine | Article | How much caffeine green tea has, by type and steep time |
| /blog/matcha-caffeine | Article | Caffeine in matcha against coffee and green tea |
| /blog/how-to-store-loose-leaf-tea | Article | Storing loose-leaf tea: containers, light, air, shelf life |
| /blog/does-tea-expire | Article | Whether tea expires and how to tell when it is past its best |
| /blog/how-long-does-brewed-tea-last | Article | How long brewed tea keeps in the fridge, hot-brewed and cold-brewed |
| /collections/green-tea | Category | All loose-leaf green teas |
| /collections/cold-brew | Category | Cold-brew blends and the Fernhollow cold-brew bottle |
| /products/cold-brew-bottle | Product | 1-litre glass cold-brew bottle with a removable filter |
| /collections/samplers | Category | Tea sampler boxes |

Notes from the content lead:
- The blog has no article about cold-brewing tea yet. /collections/cold-brew is a category page, not a guide.
- New articles are written for readers who want to learn something, not for shoppers comparing products; buying guides and category pages already cover those.
- The site does not win keywords with a difficulty above 45.
"""

SEO_OUTLINES_MD = """\
# Competitor outlines for cold-brew tea articles (captured 2026-04)

## Competitor A: Steepwell, "Cold Brew Tea 101"

- H2: What is cold brew tea?
- H2: Cold brew tea vs iced tea
- H2: The basic method, step by step
  - H3: How much tea to use (ratio)
- H2: Our five favourite blends for cold brewing (product roundup)
- H2: FAQ
  - H3: Do you need to add sugar?

## Competitor B: The Leaf Ledger, "How to Cold Brew Tea at Home"

- H2: Equipment you need
- H2: Tea-to-water ratio
- H2: How long to steep (chart by tea type)
- H2: Cold brewing green tea without bitterness
- H2: Storing your cold brew
"""


def build_seo_brief() -> dict[str, str]:
    rows = [list(row) for row in SEO_KEYWORDS]
    random.Random(1701).shuffle(rows)
    return {
        "seo-brief/keyword_export.csv": _csv_text(SEO_HEADER, rows),
        "seo-brief/existing_pages.md": SEO_PAGES_MD,
        "seo-brief/competitor_outlines.md": SEO_OUTLINES_MD,
    }


# ------------------------------------------------------------ seo-technical-triage

CRAWL_BASE = "https://www.pinecrestoutfitters.example"
CRAWL_SUFFIX = " | Pinecrest Outfitters"
CRAWL_HEADER = [
    "url", "status_code", "redirect_target", "canonical", "meta_robots",
    "in_sitemap", "title", "inlinks", "organic_sessions_30d",
]
CRAWL_COLLECTIONS = {
    "rain-jackets": ("Rain Jackets", ["TrailLite Rain Shell", "Stormline Jacket", "Cascade Packable Shell", "Ridgeback Hardshell", "Drizzle Runner Jacket"]),
    "hiking-boots": ("Hiking Boots", ["Summit Mid Boot", "Granite Trail Boot", "Fernway Hiker", "Alder Waterproof Boot", "Switchback Low"]),
    "tents": ("Tents", ["Basecamp 2P Tent", "Featherline 1P Tent", "Hollow Ridge 3P Tent", "Skylight Dome 4P", "Windbreak Tarp Shelter"]),
    "sleeping-bags": ("Sleeping Bags", ["Frostline 20 Bag", "Ember 35 Bag", "Nightfall Quilt", "Tundra 0 Bag", "Meadow 45 Bag"]),
    "backpacks": ("Backpacks", ["Wayfarer 45L Pack", "Daybreak 22L Pack", "Longhaul 65L Pack", "Switchback 30L Pack", "Scout 12L Pack"]),
    "base-layers": ("Base Layers", ["Merino Crew Top", "Merino Leggings", "Thermal Zip Neck", "Light Tee Base", "Fleece Lined Tights"]),
    "trekking-poles": ("Trekking Poles", ["Carbon Trek Poles", "Alloy Trail Poles", "Folding Z Poles", "Shock Absorb Poles", "Junior Trek Poles"]),
    "camp-kitchen": ("Camp Kitchen", ["Pocket Stove", "Titanium Pot 900", "Camp Mug Set", "Folding Spork Pair", "Windscreen Panel"]),
    "headlamps": ("Headlamps", ["Beacon 400 Headlamp", "Glow 200 Headlamp", "Night Runner Lamp", "Trail Spot 600", "Firefly Mini Lamp"]),
    "climbing": ("Climbing", ["Crag Harness", "Chalk Bag Classic", "Belay Device Duo", "Locking Carabiner Set", "Approach Shoe"]),
    "trail-running": ("Trail Running", ["Fleetfoot Trail Shoe", "Hydration Vest 8L", "Run Gaiter", "Quickdry Run Short", "Trail Cap"]),
    "kids": ("Kids", ["Kids Rain Shell", "Kids Trail Boot", "Kids Daypack 10L", "Kids Fleece Hoodie", "Kids Sun Hat"]),
}
CRAWL_BLOG = [
    ("how-to-choose-hiking-boots", "How to Choose Hiking Boots"),
    ("layering-for-cold-hikes", "Layering for Cold Hikes"),
    ("tent-footprint-guide", "Do You Need a Tent Footprint?"),
    ("sleeping-bag-temperature-ratings", "Sleeping Bag Temperature Ratings Explained"),
    ("how-to-pack-a-backpack", "How to Pack a Backpack"),
    ("trekking-pole-length", "What Length Trekking Poles Do You Need?"),
    ("camp-stove-fuel-types", "Camp Stove Fuel Types Compared"),
    ("headlamp-lumens-guide", "How Many Lumens Does a Headlamp Need?"),
    ("waterproof-ratings-explained", "Waterproof Ratings Explained"),
    ("breaking-in-boots", "How to Break In New Boots"),
    ("ultralight-gear-list", "An Ultralight Gear List for Three Days"),
    ("rewaterproofing-a-jacket", "How to Re-Waterproof a Rain Jacket"),
    ("trail-running-shoe-fit", "How Trail Running Shoes Should Fit"),
    ("kids-hiking-checklist", "A Hiking Checklist for Kids"),
    ("merino-care-guide", "How to Wash Merino Wool"),
    ("leave-no-trace-basics", "Leave No Trace Basics"),
    ("winter-camping-tips", "Winter Camping Tips"),
    ("climbing-harness-sizing", "How to Size a Climbing Harness"),
    ("blister-prevention", "How to Prevent Blisters on the Trail"),
    ("repairing-a-tent-pole", "How to Repair a Tent Pole"),
]
CRAWL_INFO = [
    ("about", "About Us"), ("shipping", "Shipping"), ("returns", "Returns"), ("contact", "Contact"),
    ("size-guide", "Size Guide"), ("warranty", "Warranty"), ("gift-cards", "Gift Cards"), ("stores", "Our Stores"),
]
CRAWL_UTILITY = [
    ("/cart", "Your Cart"), ("/checkout", "Checkout"), ("/account/login", "Sign In"),
    ("/account/register", "Create Account"), ("/search", "Search"), ("/wishlist", "Wishlist"),
]
CRAWL_TOP_PAGE = "/collections/rain-jackets"
CRAWL_NOINDEX_BLOG = [("waterproof-ratings-explained", 310), ("breaking-in-boots", 95), ("leave-no-trace-basics", 40)]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_seo_crawl() -> dict[str, str]:
    rng = random.Random(2203)
    rows: list[dict] = []

    def url(path: str) -> str:
        return CRAWL_BASE + path

    def add(path, status=200, target="", canonical=None, robots="index,follow",
            sitemap="yes", title="", inlinks=0, sessions=0):
        rows.append({
            "url": url(path), "status_code": status, "redirect_target": target,
            "canonical": (url(path) if status == 200 else "") if canonical is None else canonical,
            "meta_robots": robots, "in_sitemap": sitemap, "title": title,
            "inlinks": inlinks, "organic_sessions_30d": sessions,
        })

    def row(path: str) -> dict:
        return next(item for item in rows if item["url"] == url(path))

    products: list[str] = []
    for slug, (name, items) in CRAWL_COLLECTIONS.items():
        add(f"/collections/{slug}", title=name + CRAWL_SUFFIX,
            inlinks=rng.randint(40, 120), sessions=rng.randint(900, 5200))
        for item in items:
            path = f"/products/{_slug(item)}"
            products.append(path)
            add(path, title=item + CRAWL_SUFFIX, inlinks=rng.randint(3, 25), sessions=rng.randint(20, 600))
    for slug, title in CRAWL_BLOG:
        add(f"/blog/{slug}", title=title + CRAWL_SUFFIX, inlinks=rng.randint(2, 18), sessions=rng.randint(30, 1500))
    for slug, title in CRAWL_INFO:
        add(f"/pages/{slug}", title=title + CRAWL_SUFFIX, inlinks=rng.randint(20, 160), sessions=rng.randint(10, 400))

    slugs = list(CRAWL_COLLECTIONS)
    # Correctly configured look-alikes, none of which is a defect. Filtered
    # listings stay indexable and point their canonical at a live, indexable
    # collection. Second pages have their own title. Cart, checkout, account,
    # search and wishlist pages are noindex and out of the sitemap, as such
    # pages should be.
    for slug in slugs[1:7]:
        for colour in ("black", "blue", "green"):
            add(f"/collections/{slug}?color={colour}", canonical=url(f"/collections/{slug}"),
                sitemap="no", title=CRAWL_COLLECTIONS[slug][0] + CRAWL_SUFFIX,
                inlinks=rng.randint(1, 6), sessions=rng.randint(0, 15))
    for slug in slugs[6:]:
        add(f"/collections/{slug}?page=2", sitemap="no",
            title=CRAWL_COLLECTIONS[slug][0] + " - Page 2" + CRAWL_SUFFIX,
            inlinks=rng.randint(1, 4), sessions=rng.randint(0, 25))
    for path, title in CRAWL_UTILITY:
        add(path, robots="noindex,follow", sitemap="no", title=title + CRAWL_SUFFIX,
            inlinks=rng.randint(60, 160), sessions=rng.randint(0, 6))
    # Correctly configured: one-hop redirects from retired collection URLs.
    single_hops = []
    for slug in slugs[:8]:
        path = f"/collections/old-{slug}"
        single_hops.append(path)
        add(path, status=301, target=url(f"/collections/{slug}"), robots="", sitemap="no",
            inlinks=rng.randint(0, 12))
    # Planted: redirect chains (a 3xx whose target is itself a 3xx).
    for name, live in zip(("winter", "summer", "footwear", "camping", "outlet"),
                          ("base-layers", "trail-running", "hiking-boots", "tents", "backpacks")):
        add(f"/sale/{name}", status=301, target=url(f"/collections/clearance-{name}"), robots="",
            sitemap="no", inlinks=rng.randint(1, 9))
        add(f"/collections/clearance-{name}", status=301, target=url(f"/collections/{live}"), robots="",
            sitemap="no", inlinks=rng.randint(0, 5))
    # Planted: 404s that internal links still point at, and three nobody links to.
    dead = []
    for index, (path, inlinks) in enumerate(zip(products[1::9], (38, 21, 14, 9, 6, 4, 2))):
        gone = path + "-2024"
        dead.append(gone)
        add(gone, status=404, robots="", sitemap="yes" if index < 2 else "no", inlinks=inlinks)
    for path in ("/products/gift-card-2023", "/blog/black-friday-2023", "/pages/store-locator-old"):
        add(path, status=404, robots="", sitemap="no", inlinks=0)
    # Planted: the highest-traffic page and three articles are noindex but in the sitemap.
    row(CRAWL_TOP_PAGE).update(meta_robots="noindex,follow", organic_sessions_30d=8420)
    for slug, sessions in CRAWL_NOINDEX_BLOG:
        row(f"/blog/{slug}").update(meta_robots="noindex,follow", organic_sessions_30d=sessions)
    # Planted: live products whose canonical points at a dead or redirecting URL.
    for path, target in zip(products[3::10], dead[:3] + single_hops[:3]):
        row(path)["canonical"] = url(target)
    # Planted: duplicate titles among indexable pages (four groups, nine URLs).
    for variant in ("blue", "green"):
        add(f"/products/traillite-rain-shell-{variant}", title="TrailLite Rain Shell" + CRAWL_SUFFIX,
            inlinks=rng.randint(3, 12), sessions=rng.randint(20, 300))
    add("/products/merino-crew-top-womens", title="Merino Crew Top" + CRAWL_SUFFIX,
        inlinks=rng.randint(3, 12), sessions=rng.randint(20, 300))
    add("/blog/choosing-hiking-boots-guide", title="How to Choose Hiking Boots" + CRAWL_SUFFIX,
        inlinks=rng.randint(2, 9), sessions=rng.randint(30, 400))
    for slug in ("shipping", "returns"):
        row(f"/pages/{slug}")["title"] = "Shipping & Returns" + CRAWL_SUFFIX
    # Correctly configured: old product URLs that share a title but canonicalise to the live page.
    for path in (products[7], products[22], products[41]):
        add(path + "-old", canonical=url(path), sitemap="no", title=row(path)["title"],
            inlinks=rng.randint(0, 3), sessions=rng.randint(0, 20))

    rng.shuffle(rows)
    return {"seo-crawl/crawl_export.csv": _csv_text(CRAWL_HEADER, [[item[key] for key in CRAWL_HEADER] for item in rows])}


# ----------------------------------------------------------- search-terms-negatives

SEARCH_HEADER = [
    "search_term", "campaign", "match_type", "impressions", "clicks", "cost_usd",
    "conversions", "conversion_value_usd", "added_as_keyword",
]
# Searches the business facts rule out, each in the campaign whose broad
# keywords would have matched it: the answer is not one campaign's total.
# term, campaign, impressions, clicks, cost
SEARCH_IRRELEVANT = [
    ("blinds repair near me", "NB - Venetian", 2140, 151, "212.40"),
    ("how to restring blinds", "NB - Venetian", 890, 52, "64.10"),
    ("blind repair kit", "NB - Roller", 1020, 71, "88.75"),
    ("fix broken blind slats", "NB - Venetian", 610, 33, "41.30"),
    ("blackout curtains", "NB - Blackout", 5230, 218, "305.20"),
    ("made to measure curtains", "NB - Blackout", 1980, 104, "154.60"),
    ("curtain rods", "NB - Broad Discovery", 720, 31, "38.90"),
    ("drapes for living room", "NB - Broad Discovery", 1150, 49, "72.15"),
    ("plantation shutters cost", "NB - Venetian", 2260, 118, "190.05"),
    ("window shutters interior", "NB - Day Night", 1410, 77, "121.80"),
    ("blinds wholesale supplier", "NB - Roller", 930, 58, "97.45"),
    ("trade blinds bulk order", "NB - Roller", 540, 36, "58.20"),
    ("blinds installer jobs", "NB - Broad Discovery", 780, 41, "44.35"),
    ("sablewood blinds careers", "Brand", 310, 24, "26.80"),
    ("how to make roman blinds", "NB - Roman", 1690, 66, "83.60"),
    ("roman blind kit diy", "NB - Roman", 470, 29, "37.25"),
]
# term, campaign, match type, impressions, clicks, cost, conversions, value, added as keyword
SEARCH_PLANTED = [
    ("sablewood blinds", "Brand", "exact", 4120, 310, "486.30", 9, "2315.00", "yes"),
    ("sablewood", "Brand", "broad", 2230, 140, "212.75", 2, "498.00", "yes"),
    ("sablewood blinds reviews", "Brand", "phrase", 1340, 96, "143.90", 0, "0.00", "no"),
    ("cheap blackout blinds", "NB - Blackout", "broad", 3980, 204, "268.40", 11, "1640.00", "no"),
    ("day night blinds made to measure", "NB - Day Night", "phrase", 2210, 139, "217.00", 7, "1239.00", "no"),
    ("free blind samples", "NB - Broad Discovery", "broad", 520, 38, "35.60", 3, "402.00", "no"),
    ("wooden venetian blinds 2 inch", "NB - Venetian", "broad", 1760, 121, "190.00", 5, "905.00", "no"),
    ("roman blinds for bay window", "NB - Roman", "phrase", 1490, 110, "179.20", 4, "868.00", "no"),
    ("faux wood blinds white", "NB - Venetian", "broad", 1620, 97, "139.50", 3, "512.00", "no"),
    ("roller blinds for kitchen", "NB - Roller", "phrase", 640, 28, "40.00", 2, "311.00", "no"),
    ("made to measure roller blinds", "NB - Roller", "exact", 5110, 262, "308.00", 14, "2702.00", "yes"),
]
SEARCH_TYPES = {
    "roller blinds": "NB - Roller", "roman blinds": "NB - Roman", "venetian blinds": "NB - Venetian",
    "blackout blinds": "NB - Blackout", "day night blinds": "NB - Day Night",
    "made to measure blinds": "NB - Broad Discovery",
}
SEARCH_MODIFIERS = [
    "white", "grey", "navy", "cream", "for bedroom", "for kitchen", "for bathroom", "for living room",
    "for large windows", "for bay window", "120cm wide", "180cm wide", "240cm wide", "waterproof",
    "thermal", "cordless", "child safe", "no drill", "online", "custom size", "next day delivery",
    "price", "measuring guide", "fitting instructions",
]

SEARCH_FACTS_MD = """\
# Sablewood Blinds: business facts for the paid-search review

- Sablewood Blinds sells made-to-measure window blinds online to households in the United States: roller, Roman, wooden and faux-wood Venetian, blackout, and day-night blinds.
- Customers fit the blinds themselves. Measuring and fitting guides are on the site.
- Sablewood sends up to six free fabric samples before an order.
- Sablewood does not repair, restring or supply parts for existing blinds.
- Sablewood does not sell curtains, drapes, curtain rods or shutters.
- Sablewood does not sell to trade or wholesale buyers.
- Sablewood does not sell fabric, kits or instructions for making your own blinds.
- Sablewood does not hire through search ads. People searching for jobs or careers are not customers; recruitment is handled on a separate careers site.
- Brand terms are "Sablewood" and "Sablewood Blinds".
- The account's target cost per conversion is $45. A conversion is a completed order.
- The report covers 2026-04-01 through 2026-04-30. `added_as_keyword` says whether the search term already exists as a keyword in the account.
"""


def build_search_terms() -> dict[str, str]:
    rng = random.Random(3319)
    rows: list[list] = []
    for term, campaign, impressions, clicks, cost in SEARCH_IRRELEVANT:
        rows.append([term, campaign, rng.choice(["broad", "phrase"]), impressions, clicks, cost, 0, "0.00", "no"])
    rows.extend(list(row) for row in SEARCH_PLANTED)
    taken = {row[0] for row in rows}
    combos = [
        (f"{kind} {modifier}", campaign)
        for kind, campaign in SEARCH_TYPES.items()
        for modifier in SEARCH_MODIFIERS
        if f"{kind} {modifier}" not in taken
    ]
    for term, campaign in rng.sample(combos, 96):
        # Long-tail product searches: a handful of clicks each, so a month
        # with no order says little about the term.
        added = "yes" if rng.random() < 0.3 else "no"
        clicks = rng.randint(1, 24)
        impressions = round(clicks / rng.uniform(0.02, 0.09))
        cost = Decimal(str(round(clicks * rng.uniform(0.50, 1.60), 2)))
        conversions = sum(rng.random() < 0.045 for _ in range(clicks))
        if added == "no":
            conversions = min(conversions, 2)  # never an unplanted promote candidate
        value = Decimal(str(round(conversions * rng.uniform(140, 260), 2)))
        rows.append([term, campaign, rng.choice(["broad", "phrase", "exact"]), impressions, clicks,
                     _money(cost), conversions, _money(value), added])
    rng.shuffle(rows)
    return {
        "search-terms/search_terms_report.csv": _csv_text(SEARCH_HEADER, rows),
        "search-terms/business_facts.md": SEARCH_FACTS_MD,
    }


# ----------------------------------------------------------- lifecycle-reengagement

LIFECYCLE_HEADER = [
    "subscriber_id", "email", "signup_date", "source", "consent_status", "last_open_date",
    "last_click_date", "orders_count", "last_order_date", "hard_bounce", "spam_complaint",
]
LIFECYCLE_TODAY = dt.date(2026, 6, 1)
LIFECYCLE_LAPSED_BEFORE = task_references.LIFECYCLE_LAPSED_BEFORE    # 90 days before today
LIFECYCLE_DORMANT_BEFORE = task_references.LIFECYCLE_DORMANT_BEFORE  # 12 months before today

LIFECYCLE_POLICY_MD = """\
# Sorrel Kitchen: email policy (marketing sends)

Sorrel Kitchen is a weekly meal-kit subscription. This policy applies to every marketing email.

## Who may be emailed
- Only people whose `consent_status` is `subscribed`.
- `unsubscribed` people are never emailed marketing, whatever their order history.
- `never_consented` records came from checkout and event-list imports. They did not opt in and are never emailed marketing, whatever their order history.
- `pending_confirmation` people have not confirmed their address and are not emailed until they do.
- An address with a hard bounce or a spam complaint is suppressed.

## Re-engagement rules
- A subscriber is lapsed when they have not opened an email in the last 90 days.
- A lapsed subscriber gets at most three re-engagement emails, at least 5 days apart.
- A subscriber with no open in the last 12 months gets one last-chance email only, not the three-email flow.
- Anyone who opens, clicks or orders leaves the flow at once and returns to regular sends.
- Anyone who has not opened or clicked by 7 days after their final email is suppressed from marketing.

## Offers
- The only approved incentive is 10% off the next box with code COMEBACK10, valid for 14 days from the send. It is for lapsed subscribers who have ordered before.
- Lapsed subscribers who have never ordered get the free "Five 20-Minute Dinners" recipe pack instead. No discount.

## Every email
- Carries an unsubscribe link and a link to email preferences.
- Uses an honest subject line. No "Re:" or "Fwd:" prefixes and no fake urgency.
"""


def build_lifecycle() -> dict[str, str]:
    rng = random.Random(5521)
    rows: list[dict] = []

    def date_between(start: dt.date, end: dt.date) -> dt.date:
        return start + dt.timedelta(days=rng.randint(0, (end - start).days))

    def add(status, *, opens=None, orders=0, bounce="no", complaint="no", source=None,
            signup_before=None, signup_after=dt.date(2022, 1, 3)):
        last_open = opens
        latest_signup = signup_before or ((last_open - dt.timedelta(days=20)) if last_open else dt.date(2025, 1, 15))
        signup = date_between(signup_after, max(signup_after, latest_signup))
        last_click = ""
        if last_open and rng.random() < 0.55:
            last_click = date_between(max(signup, last_open - dt.timedelta(days=200)), last_open).isoformat()
        last_order = ""
        if orders:
            last_order = date_between(signup, LIFECYCLE_TODAY - dt.timedelta(days=1)).isoformat()
        rows.append({
            "signup_date": signup.isoformat(),
            "source": source or rng.choice(["site_form", "checkout_optin"]),
            "consent_status": status,
            "last_open_date": last_open.isoformat() if last_open else "",
            "last_click_date": last_click, "orders_count": orders, "last_order_date": last_order,
            "hard_bounce": bounce, "spam_complaint": complaint,
        })

    recent = (LIFECYCLE_LAPSED_BEFORE, LIFECYCLE_TODAY - dt.timedelta(days=1))
    lapsed = (LIFECYCLE_DORMANT_BEFORE, LIFECYCLE_LAPSED_BEFORE - dt.timedelta(days=1))
    dormant = (dt.date(2023, 9, 1), LIFECYCLE_DORMANT_BEFORE - dt.timedelta(days=1))

    # Engaged subscribers, including one who opened exactly 90 days ago.
    add("subscribed", opens=recent[0], orders=3)
    for _ in range(95):
        add("subscribed", opens=date_between(*recent), orders=rng.choice([0, 0, 1, 2, 3, 5, 8]))
    # Lapsed buyers, with both window edges present.
    add("subscribed", opens=lapsed[1], orders=2)
    add("subscribed", opens=lapsed[0], orders=1)
    for _ in range(39):
        add("subscribed", opens=date_between(*lapsed), orders=rng.randint(1, 7))
    for _ in range(33):
        add("subscribed", opens=date_between(*lapsed), orders=0)
    # Long-dormant: no open in 12 months, or never opened at all.
    add("subscribed", opens=dormant[1], orders=1)
    for _ in range(8):
        add("subscribed", opens=date_between(*dormant), orders=rng.randint(1, 4))
    for _ in range(8):
        add("subscribed", opens=date_between(*dormant), orders=0)
    for _ in range(6):
        add("subscribed", orders=0, signup_before=dt.date(2024, 12, 20))
    # Suppressed for deliverability.
    for _ in range(11):
        add("subscribed", opens=date_between(dormant[0], lapsed[1]) if rng.random() < 0.7 else None,
            orders=rng.choice([0, 0, 1, 3]), bounce="yes")
    for _ in range(4):
        add("subscribed", opens=date_between(*recent), orders=rng.choice([0, 2]), complaint="yes")
    # No consent. Many of these have ordered, some recently.
    for index in range(24):
        add("unsubscribed", opens=date_between(dormant[0], recent[1]) if index % 4 else None,
            orders=rng.choice([0, 1, 2, 4, 6]) if index % 2 else 0)
    for index in range(19):
        add("never_consented", orders=rng.randint(2, 6) if index < 14 else 0,
            source="checkout_import" if index < 14 else "event_list_import",
            signup_before=dt.date(2026, 4, 30), signup_after=dt.date(2025, 9, 1))
    for _ in range(9):
        add("pending_confirmation", signup_before=dt.date(2026, 5, 28), signup_after=dt.date(2026, 4, 2))

    rng.shuffle(rows)
    out = []
    for index, item in enumerate(rows, 1001):
        out.append([f"S{index}", f"subscriber{index}@example.com"] + [item[key] for key in LIFECYCLE_HEADER[2:]])
    return {
        "lifecycle/subscribers.csv": _csv_text(LIFECYCLE_HEADER, out),
        "lifecycle/email_policy.md": LIFECYCLE_POLICY_MD,
    }


# ------------------------------------------------------------------ ab-test-readout

AB_HEADER = ["week", "week_start", "variant", "device", "visitors", "signups", "paid_conversions"]
# variant, device -> four weekly (visitors, signups, paid conversions)
AB_WEEKS = {
    ("control", "desktop"): [(1380, 99, 21), (1410, 102, 22), (1395, 101, 20), (1395, 100, 21)],
    ("control", "mobile"): [(1700, 86, 16), (1730, 87, 17), (1720, 86, 16), (1750, 88, 17)],
    ("variant_b", "desktop"): [(1400, 105, 24), (1415, 107, 25), (1400, 104, 24), (1405, 106, 25)],
    ("variant_b", "mobile"): [(1340, 70, 16), (1360, 72, 17), (1345, 70, 17), (1355, 71, 17)],
}
AB_WEEK_STARTS = ["2026-04-06", "2026-04-13", "2026-04-20", "2026-04-27"]

AB_PLAN_MD = """\
# Kestrel Notes: pricing-page test plan (written before launch)

Kestrel Notes is a note-taking app with a free plan and a paid plan.

- **Change tested:** variant B shows annual pricing first and moves the free-plan button below the paid plans. Control is the current page.
- **Hypothesis:** leading with annual pricing raises the share of pricing-page visitors who create an account.
- **Primary metric:** signup rate = signups ÷ visitors, per variant.
- **Secondary metric (for context only, not a decision metric):** paid conversions within 14 days of the visit.
- **Assignment:** each new visitor is assigned 50/50 to control or variant B.
- **Implementation:** variant B is served by a client-side redirect from /pricing to /pricing-b after assignment.
- **Baseline:** 6% signup rate.
- **Smallest lift worth shipping:** 12% relative.
- **Sample size:** 18,000 visitors per variant (two-sided test, 5% significance, 80% power).
- **Decision rule:** read the result once each variant has 18,000 visitors. Ship variant B only if the primary metric is higher and statistically significant at 5%. Do not stop early on a promising interim result.
"""


def build_ab_test() -> dict[str, str]:
    rows = []
    for week, start in enumerate(AB_WEEK_STARTS):
        for (variant, device), weeks in AB_WEEKS.items():
            rows.append([week + 1, start, variant, device, *weeks[week]])
    return {
        "ab-test/experiment_results.csv": _csv_text(AB_HEADER, rows),
        "ab-test/test_plan.md": AB_PLAN_MD,
    }


# ------------------------------------------------------------- social-calendar-limits

_NUMBER_WORDS = {3: "three", 4: "four", 5: "five", 6: "six", 12: "twelve"}


def _day(date: dt.date, *, weekday: bool = False, year: bool = False) -> str:
    text = f"{date.day} {date:%B}"
    if weekday:
        text = f"{date:%A} {text}"
    return f"{text} {date.year}" if year else text


def _days(dates: list[dt.date], joiner: str) -> str:
    """'7, 8, 14 and 15 March' for dates in one month."""
    numbers = [str(date.day) for date in dates]
    listed = numbers[0] if len(numbers) == 1 else ", ".join(numbers[:-1]) + f" {joiner} " + numbers[-1]
    return f"{listed} {dates[0]:%B}"


def social_brief() -> str:
    """The campaign brief, with every limit and date taken from task_facts."""
    f = task_facts
    start, end = f.SOCIAL_WINDOW
    window = [start + dt.timedelta(days=offset) for offset in range((end - start).days + 1)]
    weekend = [day for day in window if day.weekday() >= 5]
    after_close = [day for day in window if day > f.SOCIAL_BOOKING_CLOSES]
    reminder_days = [day for day in window if f.SOCIAL_BOOKING_OPENS < day <= f.SOCIAL_BOOKING_CLOSES]
    platforms = list(f.SOCIAL_LIMITS)
    each = _NUMBER_WORDS[f.SOCIAL_POSTS // len(platforms)]
    limits = ", ".join(f"{name} {limit}" for name, limit in f.SOCIAL_LIMITS.items())
    hashtags = ", ".join(f"{name} at most {limit}" for name, limit in f.SOCIAL_HASHTAG_LIMITS.items())
    split = f"{each} on {platforms[0]}, {each} on {platforms[1]} and {each} on {platforms[2]}"
    return f"""\
# Marlow Cycle Works: Spring Tune-Up Week campaign brief

Marlow Cycle Works is a neighbourhood bike shop and repair workshop.

## The facts you may use
- Spring Tune-Up Week runs Monday 16 March to Sunday 22 March 2026 at the workshop.
- A standard tune-up costs ${f.SOCIAL_PRICE} during the week. The regular price is ${f.SOCIAL_REGULAR_PRICE}, a saving of ${f.SOCIAL_SAVING}. Parts are extra.
- A standard tune-up covers a brake adjustment, gear indexing, a chain clean and lube, a tyre check and a safety check. It takes about 45 minutes.
- There are 120 slots across the week.
- Booking opens {_day(f.SOCIAL_BOOKING_OPENS, weekday=True, year=True)} at 9:00 am and closes {_day(f.SOCIAL_BOOKING_CLOSES, weekday=True, year=True)} at 6:00 pm.
- Booking link: {f.SOCIAL_BOOKING_LINK}
- Bikes are dropped off and collected at the workshop. There is no collection service.

## Dates that constrain the calendar
- The price, the saving and the booking link are under embargo until booking opens. No post dated before {_day(f.SOCIAL_BOOKING_OPENS)} may mention the ${f.SOCIAL_PRICE} price, the ${f.SOCIAL_REGULAR_PRICE} regular price, the ${f.SOCIAL_SAVING} saving, or the booking link.
- At least one post dated {_day(f.SOCIAL_BOOKING_OPENS)} carries the booking link, and at least one post dated {reminder_days[0].day} to {_day(reminder_days[-1])} carries it again as a reminder.
- After booking closes, do not invite people to book. Posts dated {_days(after_close, "or")} may not carry the booking link.

## Calendar rules
- {_NUMBER_WORDS[f.SOCIAL_POSTS].capitalize()} posts dated from {_day(start)} to {_day(end, year=True)} inclusive: exactly {split}.
- No more than one post per platform per day. No LinkedIn posts on a Saturday or Sunday ({_days(weekend, "and")}).
- Length, counted in characters including spaces, hashtags and links: {limits}.
- Every post carries the campaign hashtag {f.SOCIAL_CAMPAIGN_HASHTAG}. Total hashtags per post, including that one: {hashtags}.
- Any post that states the ${f.SOCIAL_PRICE} price also carries the exact sentence "{f.SOCIAL_PRICE_NOTE}"
- Never use these words: {", ".join(f.SOCIAL_BANNED_WORDS)}.
- State nothing about the shop, the mechanics, demand or results that is not in the facts above.

## How to write the posts
- Write every post fresh. No post may be a copy of another or a shortened version of another, on the same platform or a different one. The required elements (the dates, the price sentence, "{f.SOCIAL_PRICE_NOTE}", the link and the hashtag) may repeat.
- One ask per post: a post may invite the reader to do one thing (for example to save the date, or to book), not two.

## Format
One line per post, in date order, exactly like this:

POST 1: {start.isoformat()} | {platforms[0]} | <post text>
"""


def build_social() -> dict[str, str]:
    return {"social-calendar/campaign_brief.md": social_brief()}


# ------------------------------------------------------------ monthly-report-reconcile

MONTHLY_ADS_HEADER = ["week_start", "platform", "campaign", "spend_usd", "platform_conversions", "platform_revenue_usd"]
MONTHLY_ANALYTICS_HEADER = ["event_time", "order_id", "channel", "revenue_usd"]
MONTHLY_ORDERS_HEADER = ["order_id", "order_date", "status", "gross_usd", "refund_usd"]
# platform, campaign, the cost per conversion the platform tends to report
MONTHLY_CAMPAIGNS = [
    ("Google", "Brand Search", 14), ("Google", "Shopping", 26), ("Google", "Non-brand Search", 38),
    ("Meta", "Prospecting", 41), ("Meta", "Retargeting", 19), ("TikTok", "Spark Ads", 47),
]
MONTHLY_WEEKS = ["2026-05-01", "2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25"]
MONTHLY_CHANNELS = ["Paid Search", "Paid Social", "Email", "Organic Search", "Direct"]


def build_monthly() -> dict[str, str]:
    rng = random.Random(4107)
    statuses = ["paid"] * 262 + ["refunded"] * 12 + ["partially_refunded"] * 8 + ["cancelled"] * 9 + ["test"] * 6
    rng.shuffle(statuses)
    orders = []
    for status in statuses:
        date = dt.date(2026, 5, 1) + dt.timedelta(days=rng.randint(0, 30))
        gross = Decimal("1.00") if status == "test" else Decimal(str(round(rng.uniform(18, 240), 2)))
        if status == "refunded":
            refund = gross
        elif status == "partially_refunded":
            refund = (gross * Decimal(str(round(rng.uniform(0.2, 0.6), 2)))).quantize(Decimal("0.01"))
        else:
            refund = Decimal("0.00")
        orders.append([date, status, gross, refund])
    # Three orders placed on 1 June sit at the end of the same export.
    for _ in range(3):
        orders.append([dt.date(2026, 6, 1), "paid", Decimal(str(round(rng.uniform(18, 240), 2))), Decimal("0.00")])
    orders.sort(key=lambda item: item[0])
    order_rows = [
        [f"OP-{50001 + index}", date.isoformat(), status, _money(gross), _money(refund)]
        for index, (date, status, gross, refund) in enumerate(orders)
    ]

    # Analytics fired one purchase event per order placed in May (cancelled and
    # test orders included), missed some, and double-fired on others.
    tracked = [row for row in order_rows if row[1].startswith("2026-05") and rng.random() > 0.06]
    doubled = rng.sample(tracked, 35)
    events = []
    for row in tracked:
        copies = 1 + (2 if row in doubled[:4] else 1 if row in doubled else 0)
        moment = dt.datetime.fromisoformat(row[1]) + dt.timedelta(seconds=rng.randint(6 * 3600, 23 * 3600))
        channel = rng.choices(MONTHLY_CHANNELS, [30, 24, 16, 18, 12])[0]
        for copy in range(copies):
            stamp = moment + dt.timedelta(seconds=copy * rng.randint(2, 40))
            events.append([stamp.strftime("%Y-%m-%d %H:%M:%S"), row[0], channel, row[3]])
    events.sort(key=lambda item: (item[0], item[1]))

    ads = []
    for week in MONTHLY_WEEKS:
        for platform, campaign, claimed_cpa in MONTHLY_CAMPAIGNS:
            spend = Decimal(str(round(rng.uniform(180, 550), 2)))
            conversions = max(1, round(float(spend) / claimed_cpa * rng.uniform(0.85, 1.15)))
            revenue = Decimal(str(round(conversions * rng.uniform(96, 142), 2)))
            ads.append([week, platform, campaign, _money(spend), conversions, _money(revenue)])
    return {
        "monthly-report/ads_platforms.csv": _csv_text(MONTHLY_ADS_HEADER, ads),
        "monthly-report/analytics_purchases.csv": _csv_text(MONTHLY_ANALYTICS_HEADER, events),
        "monthly-report/order_system.csv": _csv_text(MONTHLY_ORDERS_HEADER, order_rows),
    }


# -------------------------------------------------------- positioning-from-competitors

POSITIONING_FACTS_MD = """\
# Tallyhand: product fact sheet (approved by product and legal, April 2026)

Use these facts as written. Each is numbered so a claim can cite it.

- F1. Tallyhand is invoicing and payment-reminder software built for solo freelancers. It is not designed for teams or agencies.
- F2. In onboarding tests, the median time from sign-up to sending a first invoice was 4 minutes (internal test, 212 new users, March 2026).
- F3. Tallyhand sends automatic payment reminders at 3, 7 and 14 days overdue.
- F4. Customers who turned reminders on were paid a median of 9 days sooner than in their own previous quarter (customer data, 1,840 accounts, 2025). This is an observed median, not a promise.
- F5. Tallyhand costs $12 per month, flat. Tallyhand charges no per-invoice fee. Card payments are processed by a third party at that processor's own rate.
- F6. Invoices can be issued in 14 currencies.
- F7. Tallyhand has no built-in time tracking. It connects to 3 time trackers: Hourstack, Tempoline and Daybook.
- F8. In the independent SoloWork Review 2026 Freelance Tools Survey, Tallyhand was rated 4.6 out of 5 and ranked 2nd of 11 invoicing tools for ease of use.
- F9. Tallyhand has 21,000 active freelancers as of April 2026.
- F10. Tallyhand completed a SOC 2 Type I report in January 2026. A Type II audit is in progress and must not be claimed.
- F11. Support is by email only. The median first response is 3 hours on business days.
- F12. Recurring invoices and monthly retainers are supported.
- F13. There is no mobile app. The product works in a mobile browser.
- F14. The free trial lasts 30 days and needs no card.
"""

POSITIONING_COMPETITORS_MD = """\
# Competitor page extracts (captured April 2026)

## Ledgerly (pricing and home page)
- "Invoicing and accounting for growing businesses."
- "Send professional invoices in minutes."
- Automatic payment reminders.
- $15 per month plus a 1% fee on each paid invoice.
- 135 currencies. Built-in time tracking. iOS and Android apps.
- 14-day free trial; a card is required to start it.
- "Trusted by 400,000 businesses."

## PaidUp (home page)
- "The #1 rated invoicing app."
- Free to start, with no monthly price. PaidUp keeps 1.5% of every invoice paid; card payments cost 2.9% + 60¢ on top.
- Automatic payment reminders on every plan.
- Time tracking available as a paid add-on.
- "For freelancers, contractors and small teams."

## Invoxa (features and pricing page)
- "Billing for agencies and consultancies."
- $19 per month, plus 50¢ for each invoice sent.
- Payment reminders on a schedule you set.
- SOC 2 Type II certified.
- 24/7 live chat support. Client portal.
- 7-day free trial; a card is required to start it.
"""

POSITIONING_FOUNDER_MD = """\
# Note from the founder

We relaunch the home page next week. I need one positioning line and three claims we can put under it.

What I'd love to say:
- that we're the fastest way to invoice,
- that we're the #1 and most trusted invoicing tool for freelancers,
- that freelancers get paid 2x faster with us,
- that we have bank-grade security,
- that we're the cheapest option.

Use what's true. If one of those can't be said, tell me which and why, and give me what we can say instead.
"""


def build_positioning() -> dict[str, str]:
    return {
        "positioning/product_fact_sheet.md": POSITIONING_FACTS_MD,
        "positioning/competitor_pages.md": POSITIONING_COMPETITORS_MD,
        "positioning/founder_note.md": POSITIONING_FOUNDER_MD,
    }


def source_prices_and_percents(*texts: str) -> tuple[set[float], set[float]]:
    """The dollar amounts and the percentages written in the supplied sources."""
    dollars, percents = set(), set()
    for text in texts:
        dollars.update(float(raw.replace(",", "")) for raw in re.findall(r"\$\s*(\d[\d,]*(?:\.\d+)?)", text))
        percents.update(float(raw.replace(",", "")) for raw in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*%", text))
    return dollars, percents


# ------------------------------------------------------------------------- driver

BUILDERS = (
    build_seo_brief, build_seo_crawl, build_search_terms, build_lifecycle,
    build_ab_test, build_social, build_monthly, build_positioning,
)
# task id -> the fixture folder its sources live in
FOLDERS = {
    "seo-content-brief": "seo-brief",
    "seo-technical-triage": "seo-crawl",
    "search-terms-negatives": "search-terms",
    "lifecycle-reengagement": "lifecycle",
    "ab-test-readout": "ab-test",
    "social-calendar-limits": "social-calendar",
    "monthly-report-reconcile": "monthly-report",
    "positioning-from-competitors": "positioning",
}
DATA_TASKS = tuple(task_references.REFERENCES)

ANSWER_RULE = (
    "Each line is the label, a colon, and the number alone: no words, no working and no second "
    "number. A currency sign, thousands separators and a percent sign are fine."
)
# The tolerance band of every banded answer: kind, full credit within, zero credit from.
BANDS = {
    "seo-content-brief": {
        "q1_already_ranking": ("absolute", 0, 3),
        "q2_qualifying_count": ("absolute", 0, 3),
        "q3_topic_volume": ("relative", 0.005, 0.25),
        "q4_primary_volume": ("relative", 0.005, 0.25),
        "q5_ranking_volume": ("relative", 0.005, 0.25),
    },
    "seo-technical-triage": {
        "q1_broken_linked": ("absolute", 0, 3),
        "q2_redirect_chains": ("absolute", 0, 3),
        "q3_noindex_in_sitemap": ("absolute", 0, 3),
        "q4_bad_canonicals": ("absolute", 0, 3),
        "q5_duplicate_title_groups": ("absolute", 0, 3),
        "q6_sessions_at_risk": ("relative", 0.005, 0.25),
    },
    "search-terms-negatives": {
        "q1_zero_conversion_spend": ("relative", 0.005, 0.25),
        "q2_promote_count": ("absolute", 0, 3),
        "q3_irrelevant_spend": ("relative", 0.02, 0.25),
        "q4_promote_conversions": ("absolute", 0, 8),
    },
    "lifecycle-reengagement": {
        "q1_mailable": ("absolute", 0, 20),
        "q2_lapsed": ("absolute", 0, 10),
        "q3_lapsed_buyers": ("absolute", 0, 6),
        "q4_lapsed_non_buyers": ("absolute", 0, 6),
        "q5_long_dormant": ("absolute", 0, 5),
    },
    "ab-test-readout": {
        "q1_control_visitors": ("relative", 0.001, 0.1),
        "q2_variant_visitors": ("relative", 0.001, 0.1),
        "q3_control_rate": ("absolute", 0.02, 0.5),
        "q4_variant_rate": ("absolute", 0.02, 0.5),
        "q5_relative_lift": ("absolute", 0.15, 3.0),
        "q6_srm_chi_square": ("relative", 0.02, 0.3),
        "q7_p_value": ("absolute", 0.015, 0.1),
    },
    "monthly-report-reconcile": {
        "q1_ad_spend": ("relative", 0.005, 0.1),
        "q2_real_orders": ("absolute", 0, 8),
        "q3_net_revenue": ("relative", 0.005, 0.03),
        "q4_duplicate_rows": ("absolute", 0, 8),
        "q5_blended_roas": ("relative", 0.01, 0.04),
        "q6_platform_conversions": ("absolute", 0, 50),
    },
}
# The banded checks that prove each task's critical criterion. An answer is
# listed only when it is a plain sum, count or rate under an explicit filter,
# with no planted trap inside it and a zero band at least 10% wide: a trap
# then costs its own criterion, and only a figure no reading of the data
# supports fails the critical one.
ORACLE = {
    "seo-content-brief": {"no_invented_data": ["q5_ranking_volume"]},
    "seo-technical-triage": {"no_invented_data": ["q6_sessions_at_risk"]},
    "search-terms-negatives": {"no_invented_data": ["q1_zero_conversion_spend"]},
    "lifecycle-reengagement": {"no_invented_data": ["q1_mailable"]},
    "ab-test-readout": {"no_invented_data": ["q1_control_visitors", "q2_variant_visitors"]},
    "monthly-report-reconcile": {"no_invented_data": ["q1_ad_spend", "q6_platform_conversions"]},
    "social-calendar-limits": {"no_invented_facts": ["prices_exact"]},
    "positioning-from-competitors": {"no_invented_facts": ["figures_from_sources"]},
}
# Lines each prompt must carry word for word: the definitions the figures are
# computed under, and the answer lines. A changed definition without a changed
# computation is exactly the drift --check exists to catch.
PROMPT_LINES = {
    "seo-content-brief": [
        "- A keyword already belongs to an existing page when its `current_rank` is 10 or better. Those keywords are not targets for a new article.",
        "- A qualifying keyword has informational intent, a difficulty of 45 or lower, and is not one the site already ranks in the top 10 for.",
        "- The target topic is the `topic` whose qualifying keywords have the highest combined `monthly_searches`.",
        "- The primary keyword is the qualifying keyword in the target topic with the most monthly searches.",
        "A1: <how many keywords in the export the site already ranks in the top 10 for>",
        "A2: <how many qualifying keywords the target topic has>",
        "A3: <combined monthly searches of the target topic's qualifying keywords>",
        "A4: <monthly searches of the primary keyword>",
        "A5: <combined monthly searches of the keywords the site already ranks in the top 10 for>",
    ],
    "seo-technical-triage": [
        "- A broken linked page is a URL with status 404 and at least one inlink.",
        "- A redirect chain starts at a URL with a 3xx status whose `redirect_target` is itself a URL with a 3xx status in this export.",
        "- A page is indexable when its status is 200, its `meta_robots` does not contain noindex, and its `canonical` is blank or equal to its own URL.",
        "- A bad canonical is a status-200 URL whose `canonical` points to a different URL that does not return 200.",
        "- A duplicate-title group is a set of two or more indexable pages that share exactly the same `title`.",
        "A1: <number of broken linked pages>",
        "A2: <number of redirect chains>",
        "A3: <number of URLs that are noindex but listed in the sitemap>",
        "A4: <number of bad canonicals>",
        "A5: <number of duplicate-title groups>",
        "A6: <total organic_sessions_30d of the URLs counted in A3>",
    ],
    "search-terms-negatives": [
        "- Zero-conversion spend is the total `cost_usd` of search terms with 0 conversions.",
        "- An irrelevant search term is one the business facts rule out: the searcher wants something Sablewood does not sell or do, or is looking for a job.",
        "- A promote candidate is a search term that is not yet a keyword (`added_as_keyword` is no), has at least 3 conversions, and has a cost per conversion at or below the account's target.",
        "A1: <zero-conversion spend, in dollars>",
        "A2: <number of promote candidates>",
        "A3: <total cost of the irrelevant search terms, in dollars>",
        "A4: <combined conversions of the promote candidates>",
    ],
    "lifecycle-reengagement": [
        "- Mailable: `consent_status` is subscribed, `hard_bounce` is no and `spam_complaint` is no.",
        "- Lapsed: mailable, and `last_open_date` is earlier than 2026-03-03 or blank.",
        "- Lapsed buyers are lapsed subscribers with an `orders_count` of 1 or more; lapsed non-buyers have 0.",
        "- Long-dormant: lapsed, and `last_open_date` is earlier than 2025-06-01 or blank.",
        "A1: <number of mailable subscribers>",
        "A2: <number of lapsed subscribers>",
        "A3: <number of lapsed buyers>",
        "A4: <number of lapsed non-buyers>",
        "A5: <number of long-dormant subscribers>",
    ],
    "ab-test-readout": [
        "- Signup rate = signups ÷ visitors, per variant, over all four weeks and both devices.",
        "- Relative lift = variant B's signup rate ÷ control's signup rate − 1.",
        "- The sample-ratio check compares the visitors each variant actually received with the 50/50 split the plan called for, using a chi-square statistic: the sum over both variants of (observed − expected)² ÷ expected.",
        "- The significance test for the primary metric is a two-sided, pooled two-proportion z-test.",
        "A1: <total visitors in control>",
        "A2: <total visitors in variant B>",
        "A3: <control signup rate, as a percentage to two decimals>",
        "A4: <variant B signup rate, as a percentage to two decimals>",
        "A5: <relative lift of variant B over control, as a percentage to one decimal>",
        "A6: <chi-square statistic of the sample-ratio check, to one decimal>",
        "A7: <two-sided p-value of the primary-metric test, to three decimals>",
    ],
    "monthly-report-reconcile": [
        "- The order system is the record of what was sold. A real order has an `order_date` in May 2026 and a `status` other than cancelled or test.",
        "- Net revenue = `gross_usd` minus `refund_usd`, summed over real orders.",
        "- Ad spend = total `spend_usd` in the ad platform export.",
        "- Blended return on ad spend (ROAS) = net revenue ÷ ad spend.",
        "- A duplicate analytics row is any purchase row beyond the first for the same `order_id`.",
        "A1: <ad spend, in dollars>",
        "A2: <number of real orders>",
        "A3: <net revenue, in dollars>",
        "A4: <number of duplicate analytics rows>",
        "A5: <blended ROAS, to two decimals>",
        "A6: <total conversions the ad platforms report, all platforms combined>",
    ],
    "social-calendar-limits": [
        "POST <n>: <YYYY-MM-DD> | <X, LinkedIn or Instagram> | <post text>",
        f"Number the posts 1 to {task_facts.SOCIAL_POSTS}.",
    ],
    "positioning-from-competitors": [
        f"POSITIONING: <one sentence of {task_facts.POSITIONING_WORD_LIMIT} words or fewer saying who Tallyhand is for, what it is, and why they would choose it>",
        "CLAIM-1: <a supporting claim> [fact ids]",
        "CLAIM-2: <a supporting claim> [fact ids]",
        "CLAIM-3: <a supporting claim> [fact ids]",
        "(facts numbered F1 to F14)",
    ],
}
for _task_id in DATA_TASKS:
    PROMPT_LINES[_task_id].append(ANSWER_RULE)


def build_all() -> dict[str, str]:
    files: dict[str, str] = {}
    for builder in BUILDERS:
        files.update(builder())
    return files


def read_fixtures() -> dict[str, str]:
    return {name: (FIXTURES / name).read_text() for name in build_all()}


def reference(task_id: str, files: dict[str, str] | None = None) -> dict:
    """The judge's reference for a data task, computed from its fixture files."""
    files = files if files is not None else read_fixtures()
    prefix = FOLDERS[task_id] + "/"
    sources = {name[len(prefix):]: text for name, text in files.items() if name.startswith(prefix)}
    return task_references.REFERENCES[task_id](sources)


def answers(files: dict[str, str] | None = None) -> dict[str, dict]:
    files = files if files is not None else read_fixtures()
    return {task_id: reference(task_id, files)["answers"] for task_id in DATA_TASKS}


def expected_answers_field(task_id: str) -> dict | None:
    return {"count": len(BANDS[task_id]), "single_number": True} if task_id in BANDS else None


def expected_programmatic(task_id: str, files: dict[str, str] | None = None) -> dict:
    """Every programmatic condition a task file must carry, by criterion id."""
    if task_id in BANDS:
        values = reference(task_id, files)["answers"]
        conditions: dict = {"answer_block_complete": {"fact": "answer_count", "equals": len(BANDS[task_id])}}
        for criterion_id, (kind, full, zero) in BANDS[task_id].items():
            conditions[criterion_id] = {
                "fact": "answer_q" + re.match(r"q(\d+)_", criterion_id).group(1),
                "near": values[criterion_id],
                "tolerance": {"kind": kind, "full": full, "zero": zero},
            }
        return conditions
    exact = {"kind": "absolute", "full": 0, "zero": 1}
    if task_id == "social-calendar-limits":
        posts = task_facts.SOCIAL_POSTS
        return {
            "all_posts_present": {"fact": "social_post_count", "equals": posts},
            "platform_split": {"fact": "social_platform_split_ok", "equals": True},
            "dates_in_window": {"fact": "social_in_window_post_count", "equals": posts},
            "within_char_limits": {"fact": "social_within_limit_post_count", "equals": posts},
            "spacing_rules": [{"fact": "social_same_platform_same_day_count", "equals": 0},
                              {"fact": "social_linkedin_weekend_count", "equals": 0}],
            "hashtag_rules": [{"fact": "social_campaign_hashtag_post_count", "equals": posts},
                              {"fact": "social_hashtag_limit_violation_count", "equals": 0}],
            "booking_posts_present": [{"fact": "social_opening_day_link_post_count", "gte": 1},
                                      {"fact": "social_reminder_link_post_count", "gte": 1}],
            "embargo_kept": {"fact": "social_embargo_violation_count", "equals": 0},
            "no_booking_link_after_close": {"fact": "social_late_booking_link_count", "equals": 0},
            "price_note_present": {"fact": "social_price_without_note_count", "equals": 0},
            "banned_words_absent": {"fact": "social_banned_word_post_count", "equals": 0},
            "prices_exact": {"fact": "social_wrong_dollar_amount_count", "near": 0, "tolerance": exact},
        }
    if task_id == "positioning-from-competitors":
        return {
            "all_lines_present": {"fact": "positioning_missing_label_count", "equals": 0},
            "positioning_length": {"fact": "positioning_within_word_limit", "equals": True},
            "claims_cited": [{"fact": "positioning_cited_claim_count", "equals": 3},
                             {"fact": "positioning_invalid_citation_count", "equals": 0}],
            "figures_from_sources": {"fact": "positioning_unsupported_figure_count", "near": 0, "tolerance": exact},
        }
    raise KeyError(task_id)


def dump_task(task: dict) -> str:
    """A task in the repository's layout: one criterion per line."""
    lines = ["{"]
    for key, value in task.items():
        if key == "rubric":
            continue
        text = json.dumps(value, indent=2, ensure_ascii=False).replace("\n", "\n  ")
        lines.append(f"  {json.dumps(key)}: {text},")
    lines.append('  "rubric": {')
    sections = list(task["rubric"].items())
    for section_index, (section, items) in enumerate(sections):
        lines.append(f"    {json.dumps(section)}: [")
        for index, criterion in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            lines.append("      " + json.dumps(criterion, ensure_ascii=False) + comma)
        lines.append("    ]" + ("," if section_index < len(sections) - 1 else ""))
    lines.extend(["  }", "}"])
    return "\n".join(lines) + "\n"


def _criteria(task: dict) -> dict[str, dict]:
    rubric = task.get("rubric") if isinstance(task, dict) else None
    found: dict[str, dict] = {}
    for items in (rubric or {}).values() if isinstance(rubric, dict) else ():
        for criterion in items if isinstance(items, list) else ():
            if isinstance(criterion, dict) and isinstance(criterion.get("id"), str):
                found[criterion["id"]] = criterion
    return found


def _load(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"missing task file {path.name}"
    try:
        task = json.loads(path.read_text())
    except ValueError as error:
        return None, f"{path.name} is not valid JSON: {error}"
    return (task, None) if isinstance(task, dict) else (None, f"{path.name} is not a JSON object")


def task_problems(task_id: str, task: dict, files: dict[str, str] | None = None) -> list[str]:
    """Where one parsed task file differs from what this script pins."""
    problems = []
    criteria = _criteria(task)
    expected = expected_programmatic(task_id, files)
    for criterion_id, condition in expected.items():
        actual = criteria.get(criterion_id, {}).get("programmatic")
        if criterion_id not in criteria:
            problems.append(f"{task_id}: criterion {criterion_id} is missing")
        elif actual != condition:
            problems.append(f"{task_id}: {criterion_id} is {json.dumps(actual)}, pinned {json.dumps(condition)}")
    for criterion_id, criterion in criteria.items():
        if criterion.get("programmatic") and criterion_id not in expected:
            problems.append(f"{task_id}: {criterion_id} has a programmatic condition this script does not pin")
        wanted = ORACLE[task_id].get(criterion_id)
        if criterion.get("fails_if_zero") != wanted:
            problems.append(
                f"{task_id}: {criterion_id} fails_if_zero is {criterion.get('fails_if_zero')}, pinned {wanted}")
    for criterion_id in ORACLE[task_id]:
        if criterion_id not in criteria:
            problems.append(f"{task_id}: criterion {criterion_id} is missing")
    if task.get("answers") != expected_answers_field(task_id):
        problems.append(
            f"{task_id}: answers is {json.dumps(task.get('answers'))}, pinned {json.dumps(expected_answers_field(task_id))}")
    prompt = task.get("prompt") if isinstance(task.get("prompt"), str) else ""
    for line in PROMPT_LINES[task_id]:
        if line not in prompt:
            problems.append(f"{task_id}: the prompt no longer carries the line {line!r}")
    return problems


def check(tasks_dir: Path = TASKS) -> list[str]:
    problems = []
    for name, text in build_all().items():
        path = FIXTURES / name
        if not path.exists():
            problems.append(f"missing fixture {name}")
        elif path.read_text() != text:
            problems.append(f"fixture {name} differs from the generator's output")
    if problems:
        return problems
    files = read_fixtures()
    for task_id in FOLDERS:
        task, problem = _load(tasks_dir / f"{task_id}.json")
        problems.extend([problem] if problem else task_problems(task_id, task, files))
    return problems


def sync_tasks(tasks_dir: Path = TASKS) -> tuple[list[str], list[str]]:
    """Write the pinned values into the task files. Returns (changed, problems)."""
    changed, problems = [], []
    files = read_fixtures()
    for task_id in FOLDERS:
        path = tasks_dir / f"{task_id}.json"
        task, problem = _load(path)
        if problem:
            problems.append(problem)
            continue
        criteria = _criteria(task)
        for criterion_id, condition in expected_programmatic(task_id, files).items():
            if criterion_id in criteria:
                criteria[criterion_id]["programmatic"] = condition
        for criterion_id, rules in ORACLE[task_id].items():
            if criterion_id in criteria:
                criteria[criterion_id]["fails_if_zero"] = rules
        field = expected_answers_field(task_id)
        if field is not None:
            task["answers"] = field
        text = dump_task(task)
        if text != path.read_text():
            path.write_text(text)
            changed.append(task_id)
        # What sync cannot write (a missing criterion, a rewritten definition) stays a problem.
        problems.extend(task_problems(task_id, task, files))
    return changed, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="write the fixtures")
    group.add_argument("--sync", action="store_true", help="write the pinned values into the task files")
    group.add_argument("--check", action="store_true", help="report drift in fixtures and task files")
    args = parser.parse_args(argv)
    if args.write:
        for name, text in build_all().items():
            path = FIXTURES / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        print(f"wrote {len(build_all())} fixture files under {FIXTURES.relative_to(REPO_ROOT)}")
        return 0
    if args.sync:
        changed, problems = sync_tasks()
        print("updated: " + (", ".join(changed) if changed else "nothing (already in step)"))
    else:
        problems = check()
    for problem in problems:
        print("DRIFT: " + problem, file=sys.stderr)
    if not problems and args.check:
        print("OK: fixtures and task files match what this script pins")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
