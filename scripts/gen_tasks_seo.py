#!/usr/bin/env python3
"""Generate the fixtures of the SEO tasks added for the 35-task board.

Tasks: seo-redirect-map, seo-titles-meta, and the sources of the hardened
blog-post. (The hardened seo-content-brief keeps its generator,
scripts/gen_more_tasks.py.)

Deterministic: every table is written out below or drawn from a seeded
generator, so a rerun writes the same bytes. The answers are not computed
here: `eval_runner/task_facts_seo.py` computes them from the fixture text,
and tests/test_tasks_seo.py computes them again with separate code.

All brands, people, URLs and figures are invented.

Usage:
    python3 scripts/gen_tasks_seo.py --write   # (re)write the fixtures
    python3 scripts/gen_tasks_seo.py --check   # report drift, change nothing
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
FIXTURES = REPO_ROOT / "eval_runner" / "fixtures"


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ------------------------------------------------------------------ seo-redirect-map

# Old category slug, the new address the rename table gives it.
REDIRECT_CATEGORIES = [
    ("frying-pans", "/shop/frying-pans"),
    ("saucepans", "/shop/saucepans"),
    ("dutch-ovens", "/shop/dutch-ovens"),
    ("cast-iron", "/shop/cast-iron"),                    # stale: the new site moved it again
    ("stainless-steel", "/shop/stainless-steel-cookware"),
    ("nonstick", "/shop/frying-pans"),                   # merged into frying pans
    ("knives", "/shop/kitchen-knives"),
    ("knife-sets", "/shop/kitchen-knives"),              # merged
    ("cutting-boards", "/shop/cutting-boards"),
    ("bakeware", "/shop/bakeware"),
    ("baking-tools", "/shop/bakeware"),                  # merged
    ("utensils", "/shop/kitchen-tools"),
    ("gadgets", "/shop/kitchen-tools"),                  # merged
    ("storage", "/shop/food-storage"),                   # stale: the new site moved it again
    ("kitchen-linens", "/shop/linens"),
    ("coffee-tea", "/shop/coffee-and-tea"),
    ("gifts", "/shop/gifts"),
    ("sale", "/shop/sale"),
    ("new-arrivals", "/shop/new"),
    ("bar-tools", "/shop/bar-tools"),                    # stale: the new site moved it again
]
# The rename table's addresses that the new site's own list redirects again.
REDIRECT_NEW_SITE_MOVES = {
    "/shop/cast-iron": "/shop/cast-iron-cookware",
    "/shop/food-storage": "/shop/pantry-storage",
    "/pages/visit-us": "/pages/contact",
    "/shop/bar-tools": "/shop/barware",
}
REDIRECT_PAGE_RENAMES = [
    ("/pages/shipping", "/pages/shipping-and-returns"),
    ("/pages/returns", "/pages/shipping-and-returns"),
    ("/pages/our-story", "/pages/about"),
    ("/pages/care-guides", "/journal/care-and-cleaning"),
    ("/pages/store-locations", "/pages/visit-us"),       # stale: the new site redirects it
    ("/blogs/kitchen-notes", "/journal"),
    ("/pages/gift-cards", "/pages/gift-card"),
    ("/pages/recipes", "/journal"),
]
REDIRECT_UNCHANGED = [
    "/", "/cart", "/search", "/account/login", "/account/register",
    "/pages/about", "/pages/contact", "/pages/faq", "/pages/privacy-policy", "/pages/terms",
]
# Products by old category: the name, and the new slug where the new site renamed it.
REDIRECT_PRODUCTS = {
    "frying-pans": ["Classic Fry Pan 8 Inch", "Classic Fry Pan 10 Inch", "Classic Fry Pan 12 Inch", "Everyday Skillet 10",
                    "Carbon Steel Pan 11", "Crepe Pan 10", "Grill Pan Square", "Paella Pan 14", "Egg Pan Mini",
                    "Stainless Fry Pan 8", "Wok 14 Inch", "Grill Press"],
    "saucepans": ["Saucepan 1.5 Quart", "Saucepan 3 Quart", "Saucier 2 Quart", "Butter Warmer", "Milk Pan Small",
                  "Stockpot 8 Quart", "Pasta Pot 6 Quart", "Saucepan 2 Quart",
                  "Saute Pan 4 Quart"],
    "dutch-ovens": ["Round Dutch Oven 5.5 Quart", "Oval Dutch Oven 7 Quart", "Braiser 3.5 Quart", "Mini Cocotte Pair",
                    "Bread Oven Cloche", "Dutch Oven Lid Knob", "Cast Iron Bread Pan"],
    "cast-iron": ["Cast Iron Skillet 10", "Cast Iron Skillet 12", "Cast Iron Griddle", "Cast Iron Wok",
                  "Chainmail Scrubber", "Skillet Handle Sleeve", "Cast Iron Dutch Oven 6", "Pan Scraper Set"],
    "stainless-steel": ["Tri Ply Skillet 10", "Tri Ply Saute Pan", "Tri Ply Stockpot", "Steamer Insert", "Roasting Pan Rack", "Tri Ply Saucepan 2",
                        "Stainless Roaster"],
    "nonstick": ["Ceramic Nonstick Pan 10", "Ceramic Nonstick Pan 12", "Nonstick Omelette Pan", "Nonstick Wok", "Nonstick Grill Pan",
                 "Ceramic Saute Pan"],
    "knives": ["Chef Knife 8 Inch", "Santoku 7 Inch", "Paring Knife 3.5", "Bread Knife 9", "Utility Knife 6",
               "Boning Knife", "Nakiri 6.5", "Honing Steel", "Carving Knife 10", "Serrated Utility 5"],
    "knife-sets": ["Essential Knife Trio", "Block Set 7 Piece", "Steak Knife Set 4", "Magnetic Knife Strip", "Knife Block Bamboo"],
    "cutting-boards": ["Walnut End Grain Board", "Maple Board Large", "Bamboo Prep Board", "Board Oil Bottle",
                       "Cherry Serving Board", "Bread Board Oak"],
    "bakeware": ["Half Sheet Pan", "Quarter Sheet Pan", "Loaf Pan", "Round Cake Pan 9", "Muffin Tin 12",
                 "Pie Dish Ceramic", "Bundt Pan", "Springform Pan 9", "Baking Dish Large"],
    "baking-tools": ["Bench Scraper", "French Rolling Pin", "Pastry Brush", "Cooling Rack", "Proofing Basket",
                     "Dough Whisk", "Pastry Blender", "Piping Bag Set"],
    "utensils": ["Fish Spatula", "Silicone Spatula", "Wooden Spoon Set", "Kitchen Tongs 12", "Ladle Stainless",
                 "Slotted Spoon", "Potato Masher", "Spider Strainer"],
    "gadgets": ["Garlic Press", "Microplane Zester", "Salad Spinner", "Mandoline Slicer", "Herb Stripper", "Smooth Edge Can Opener",
                "Citrus Juicer"],
    "storage": ["Glass Container Set", "Spice Jar Set", "Bread Box Bamboo", "Produce Saver", "Flour Canister", "Bento Box Steel"],
    "kitchen-linens": ["Linen Tea Towel Pair", "Waffle Dish Towel", "Canvas Apron", "Oven Mitt Pair", "Linen Napkin Set", "Pot Holder Pair"],
    "coffee-tea": ["Pour Over Kettle", "French Press 8 Cup", "Tea Infuser Mug", "Coffee Canister", "Milk Frother", "Hand Burr Grinder", "Enamel Tea Kettle"],
    "gifts": ["Starter Kitchen Gift Set", "Baker Gift Set", "Knife Care Gift Set", "Pasta Night Gift Set"],
    "bar-tools": ["Cocktail Shaker", "Jigger Set", "Bar Spoon", "Muddler"],
}
# New slugs where the new site renamed the product page (the rest keep theirs).
REDIRECT_NEW_SLUGS = {
    "Classic Fry Pan 8 Inch": "classic-fry-pan-8in", "Classic Fry Pan 10 Inch": "classic-fry-pan",
    "Classic Fry Pan 12 Inch": "classic-fry-pan-12in", "Carbon Steel Pan 11": "carbon-steel-skillet-11",
    "Saucepan 1.5 Quart": "saucepan-1-5-qt", "Saucepan 3 Quart": "saucepan-3-qt", "Saucier 2 Quart": "saucier",
    "Stockpot 8 Quart": "stockpot-8-qt", "Round Dutch Oven 5.5 Quart": "round-dutch-oven",
    "Oval Dutch Oven 7 Quart": "oval-dutch-oven", "Braiser 3.5 Quart": "braiser",
    "Cast Iron Skillet 10": "cast-iron-skillet", "Cast Iron Skillet 12": "cast-iron-skillet-12in",
    "Tri Ply Skillet 10": "tri-ply-fry-pan-10", "Tri Ply Stockpot": "tri-ply-stockpot-12-qt",
    "Ceramic Nonstick Pan 10": "ceramic-pan-10", "Ceramic Nonstick Pan 12": "ceramic-pan-12",
    "Chef Knife 8 Inch": "chefs-knife-8in", "Paring Knife 3.5": "paring-knife", "Bread Knife 9": "bread-knife",
    "Block Set 7 Piece": "knife-block-set", "Walnut End Grain Board": "walnut-end-grain-cutting-board",
    "Maple Board Large": "maple-cutting-board", "Round Cake Pan 9": "cake-pan-9in", "Muffin Tin 12": "muffin-pan",
    "French Rolling Pin": "rolling-pin", "Kitchen Tongs 12": "tongs", "Microplane Zester": "rasp-zester",
    "Linen Tea Towel Pair": "linen-tea-towels", "French Press 8 Cup": "french-press",
}
# Retired: not on the new site. With every signal at zero they get 410.
REDIRECT_RETIRED_SILENT = ["Milk Pan Small", "Butter Warmer", "Nonstick Wok", "Board Oil Bottle", "Produce Saver",
                           "Steak Knife Set 4", "Grill Press", "Pastry Blender", "Pot Holder Pair", "Muddler"]
# Retired with exactly one signal above zero: (inlinks, backlinks, sessions).
REDIRECT_RETIRED_ONE_SIGNAL = {"Chainmail Scrubber": (0, 0, 1), "Proofing Basket": (1, 0, 0), "Coffee Canister": (0, 1, 0),
                               "Potato Masher": (0, 0, 2), "Bread Board Oak": (0, 1, 0)}
REDIRECT_RETIRED = ["Crepe Pan 10", "Mini Cocotte Pair", "Steamer Insert", "Waffle Dish Towel", "Tea Infuser Mug",
                    "Cast Iron Wok", "Spice Jar Set", "Egg Pan Mini", "Herb Stripper", "Stainless Roaster", "Citrus Juicer",
                    "Cast Iron Dutch Oven 6", "Bento Box Steel"]
# Retired, and the new site reuses the slug for a successor with a new SKU.
REDIRECT_SLUG_REUSED = ["Everyday Skillet 10", "Santoku 7 Inch", "Half Sheet Pan", "Pour Over Kettle",
                        "Glass Container Set", "Wok 14 Inch", "Hand Burr Grinder", "Springform Pan 9"]
# New-site product pages that are merged into another (status 301 in the new list).
REDIRECT_MERGED_PRODUCTS = {
    "Classic Fry Pan 8 Inch": "Classic Fry Pan 10 Inch", "Classic Fry Pan 12 Inch": "Classic Fry Pan 10 Inch",
    "Cast Iron Skillet 12": "Cast Iron Skillet 10", "Tri Ply Stockpot": "Stockpot 8 Quart",
    "Saucepan 2 Quart": "Saucepan 3 Quart", "Serrated Utility 5": "Utility Knife 6",
}
# Colourways and sizes the old site sold as separate product pages, each with its own SKU.
# The new site keeps every SKU but folds the pages into one: the first is the product page,
# the others redirect to it. The last of some groups is retired.
REDIRECT_VARIANTS = [
    ("kitchen-linens", "Chef Apron", ["navy", "rust", "olive", "charcoal"]),
    ("kitchen-linens", "Striped Tea Towel", ["blue", "red", "green"]),
    ("cutting-boards", "Acacia Board", ["small", "medium", "large"]),
    ("dutch-ovens", "Enamel Dutch Oven", ["red", "blue", "black", "white"]),
    ("utensils", "Silicone Spoon", ["grey", "sage", "blush"]),
    ("bakeware", "Ceramic Ramekin Set", ["white", "speckled"]),
    ("coffee-tea", "Stoneware Mug", ["cream", "slate", "terracotta"]),
    ("storage", "Glass Jar", ["small", "medium", "large"]),
    ("bar-tools", "Cocktail Glass Pair", ["coupe", "rocks"]),
]
# Variant pages not on the new site: (inlinks, backlinks, sessions); all zero is gone.
REDIRECT_RETIRED_VARIANTS = {("Enamel Dutch Oven", "white"): (3, 0, 40), ("Stoneware Mug", "terracotta"): (0, 0, 0),
                             ("Glass Jar", "large"): (1, 2, 75)}
REDIRECT_NEW_ONLY_PRODUCTS = [("frying-pans", "induction-fry-pan-11"), ("kitchen-knives", "cleaver-7in"),
                              ("bakeware", "baguette-tray"), ("pantry-storage", "rice-bin"), ("linens", "bar-towels"),
                              ("barware", "ice-mold-set"), ("kitchen-tools", "bench-knife"), ("coffee-and-tea", "matcha-whisk")]

REDIRECT_POSTS = [
    "how-to-season-cast-iron", "cleaning-stainless-steel-pans", "choosing-a-dutch-oven", "knife-sharpening-basics",
    "end-grain-vs-edge-grain", "caring-for-wooden-boards", "sheet-pan-dinners", "perfect-pan-sauce", "braising-101",
    "bread-baking-in-a-dutch-oven", "how-to-hone-a-knife", "nonstick-pan-care", "oils-for-seasoning",
    "stocking-a-first-kitchen", "pantry-organization-ideas", "how-to-use-a-bench-scraper", "cooling-racks-explained",
    "whipping-cream-by-hand", "kitchen-tools-under-25", "making-cold-brew-at-home", "pour-over-coffee-guide",
    "tea-towel-care", "how-to-clean-a-cast-iron-griddle", "carbon-steel-vs-cast-iron", "induction-cookware-guide",
    "oven-safe-pans", "saute-vs-fry", "how-to-store-knives", "choosing-a-cutting-board", "linen-vs-cotton-towels",
    "how-to-braise-short-ribs", "chef-knife-vs-santoku", "storing-fresh-herbs", "making-stock-at-home",
    "how-to-dice-an-onion", "pie-crust-basics", "sourdough-starter-guide", "cast-iron-myths", "kitchen-towel-guide",
    "how-to-sharpen-scissors", "coffee-grind-sizes", "tea-steeping-guide", "cleaning-a-dutch-oven", "mixing-a-classic-sour",
    # A number at the front that is not a YYYY-MM- date: the slug stays as it is.
    "10-knife-skills-every-cook-needs", "2024-gift-guide", "2025-kitchen-trends", "5-pans-every-kitchen-needs",
    "2023-holiday-gift-guide", "30-minute-weeknight-dinners", "2024-1-year-of-sourdough",
    # Dated slugs: the date goes. The last two have no page on the new site.
    "2022-03-spring-baking-checklist", "2023-11-holiday-baking-timeline", "2024-02-valentines-dinner-for-two",
    "2023-05-mothers-day-brunch", "2021-10-soup-season-staples", "2024-08-tomato-season-recipes",
    "2022-12-holiday-cookie-swap", "2023-04-spring-pasta-recipes", "2021-01-new-year-pantry-reset",
    "2024-06-grilling-season-guide",
    "2021-06-summer-grilling-tools", "2022-09-back-to-school-lunches", "2023-09-apple-pie-season", "2022-07-picnic-essentials",
    # Not carried over.
    "our-new-warehouse", "meet-the-team-2022", "warehouse-sale-recap",
]
REDIRECT_POSTS_NOT_MOVED = {"summer-grilling-tools", "back-to-school-lunches", "our-new-warehouse", "meet-the-team-2022",
                            "apple-pie-season", "picnic-essentials", "warehouse-sale-recap"}
REDIRECT_MERGED_POSTS = {"saute-vs-fry": "pan-frying-guide", "linen-vs-cotton-towels": "tea-towel-care",
                         "kitchen-towel-guide": "tea-towel-care", "cast-iron-myths": "how-to-season-cast-iron",
                         "cleaning-a-dutch-oven": "choosing-a-dutch-oven"}

REDIRECT_RULES_MD = """\
# Bramblewood Kitchen: redirect rules for the platform move

Bramblewood Kitchen sells cookware, knives and kitchen tools online at www.bramblewoodkitchen.example. The shop moves to a new platform, on the same domain, on 2027-01-18. `old_site_urls.csv` is the crawl of the old site; `new_site_urls.csv` is the final crawl of the new site on staging. Both write URLs as paths.

## The file to deliver

`redirects.csv`, with the header `old_url,status,target`: one row for every old URL that gets a redirect (`301`) or is retired as gone (`410`), and no row for any other old URL. A 410 row has an empty `target`. Write every URL as a path, exactly as the files write it.

## The rules, in order

Take each URL in `old_site_urls.csv` and apply these rules in order. The first rule that applies decides its row.

1. **Parameter URLs.** A URL with a `?` in it gets no row. The new platform drops query strings.
2. **Dead URLs nobody links to.** A URL whose `status` is 404 and whose `backlinks` is 0 gets no row.
3. **Unchanged URLs.** A URL that appears in `new_site_urls.csv`, exactly as written, with status 200 gets no row.
4. **The trade portal.** `/wholesale` and every URL under `/wholesale/` get 410. The trade programme has closed.
5. **Old redirects.** A URL whose `status` is 301 gets the same status and target as its `redirect_target` gets under these rules, so that no visitor passes through an old address.
6. **Products on the new site.** A `/products/` URL whose `sku` appears in `new_site_urls.csv` redirects to the new URL of that SKU. Products are matched by SKU only; a product page with the same slug but another SKU is a different product.
7. **Retired products.** A `/products/` URL whose `sku` does not appear in `new_site_urls.csv` is retired. If its `inlinks`, `backlinks` and `sessions_90d` are all 0 it gets 410. Otherwise it redirects to the new address the rename table gives `/collections/<its category>`.
8. **Renamed categories and pages.** A URL in the rename table below redirects to its new address.
9. **Journal posts.** A URL under `/blogs/kitchen-notes/` moves to `/journal/` with the same slug, except that a slug that starts with a date written `YYYY-MM-` (four digits, a hyphen, two digits, a hyphen) loses that date. If the address this gives is not in `new_site_urls.csv`, the post redirects to `/journal` instead.
10. **Everything else** gets 410.

## Every redirect lands on a live page

The target of a 301 must have status 200 in `new_site_urls.csv`. Where a rule above gives an address that has status 301 in `new_site_urls.csv`, the target is that row's `redirect_to` instead. Every redirect in the new list is a single hop to a live page.

## The rename table

| Old URL | New address |
|---|---|
{rename_rows}
"""


def _redirect_leaf(category: str) -> str:
    """The last part of the live new address of an old category."""
    path = dict(REDIRECT_CATEGORIES)[category]
    return REDIRECT_NEW_SITE_MOVES.get(path, path).rsplit("/", 1)[1]


def redirect_product_rows() -> list[dict]:
    """Every product page of the old site with its SKU, signals and new URL (None when retired).

    A variant page carries `folds_into`: the new product page its new URL redirects to.
    """
    rng = random.Random(4471)
    retired = set(REDIRECT_RETIRED_SILENT) | set(REDIRECT_RETIRED_ONE_SIGNAL) | set(REDIRECT_RETIRED) | set(REDIRECT_SLUG_REUSED)
    products, sku = [], 1001

    def busy() -> tuple[int, int, int]:
        return rng.randint(2, 38), rng.choice([0, 0, 0, 1, 1, 2, 3, 5, 8, 12]), rng.randint(15, 2400)

    for category, names in REDIRECT_PRODUCTS.items():
        for name in names:
            slug = _slug(name)
            if name in REDIRECT_RETIRED_SILENT:
                signals = (0, 0, 0)
            else:
                signals = REDIRECT_RETIRED_ONE_SIGNAL.get(name) or busy()
            products.append({
                "name": name, "category": category, "slug": slug, "sku": f"BW-{sku}",
                "inlinks": signals[0], "backlinks": signals[1], "sessions": signals[2],
                "new_url": None if name in retired else f"/shop/{_redirect_leaf(category)}/{REDIRECT_NEW_SLUGS.get(name, slug)}",
            })
            sku += 1 + rng.randint(0, 3)
    sku = 2401
    for category, base, options in REDIRECT_VARIANTS:
        main = f"/shop/{_redirect_leaf(category)}/{_slug(base)}"
        for index, option in enumerate(options):
            gone = (base, option) in REDIRECT_RETIRED_VARIANTS
            signals = REDIRECT_RETIRED_VARIANTS[(base, option)] if gone else busy()
            products.append({
                "name": f"{base} {option}", "category": category, "slug": f"{_slug(base)}-{option}", "sku": f"BW-{sku}",
                "inlinks": signals[0], "backlinks": signals[1], "sessions": signals[2],
                "new_url": None if gone else (main if index == 0 else f"{main}-{option}"),
                "folds_into": main if index and not gone else None,
            })
            sku += 3
    return products


def build_redirect_map() -> dict[str, str]:
    rng = random.Random(9083)
    products = redirect_product_rows()
    by_name = {item["name"]: item for item in products}
    old: list[list] = []   # url, status, redirect_target, sku, category, inlinks, backlinks, sessions_90d
    new: list[list] = []   # url, status, redirect_to, sku

    def signals(low: int, high: int, backlinks: list[int], sessions: tuple[int, int]) -> list[int]:
        return [rng.randint(low, high), rng.choice(backlinks), rng.randint(*sessions)]

    # The old site.
    for path in REDIRECT_UNCHANGED:
        old.append([path, 200, "", "", "", *signals(40, 220, [0, 4, 9, 21, 40], (300, 9000))])
    for slug, _new in REDIRECT_CATEGORIES:
        old.append([f"/collections/{slug}", 200, "", "", "", *signals(30, 150, [0, 1, 3, 6, 14], (200, 5200))])
    for path, _new in REDIRECT_PAGE_RENAMES:
        old.append([path, 200, "", "", "", *signals(10, 120, [0, 1, 2, 5], (40, 1800))])
    for path in ("/collections/holiday-2023", "/collections/black-friday-2024", "/pages/press-2019",
                 "/collections/outdoor-dining", "/pages/careers"):
        old.append([path, 200, "", "", "", *signals(1, 12, [0, 2, 7], (5, 300))])
    for item in products:
        old.append([f"/products/{item['slug']}", 200, "", item["sku"], item["category"],
                    item["inlinks"], item["backlinks"], item["sessions"]])
    for slug in REDIRECT_POSTS:
        old.append([f"/blogs/kitchen-notes/{slug}", 200, "", "", "", *signals(1, 25, [0, 0, 1, 2, 4, 9], (20, 3100))])
    # Already redirecting on the old site, each to an old URL that is itself in the export.
    for path, target in (
        ("/products/chefs-knife", "/products/chef-knife-8-inch"),
        ("/products/dutch-oven-round", "/products/round-dutch-oven-5-5-quart"),
        ("/products/skillet-everyday", "/products/everyday-skillet-10"),
        ("/products/maple-board", "/products/maple-board-large"),
        ("/products/apron-navy", "/products/chef-apron-navy"),
        ("/products/apron-rust", "/products/chef-apron-rust"),
        ("/products/wok", "/products/wok-14-inch"),
        ("/products/santoku-knife", "/products/santoku-7-inch"),
        ("/collections/pans", "/collections/frying-pans"),
        ("/collections/food-storage", "/collections/storage"),
        ("/collections/knife-blocks", "/collections/knife-sets"),
        ("/blogs/kitchen-notes/seasoning-cast-iron", "/blogs/kitchen-notes/how-to-season-cast-iron"),
        ("/blogs/kitchen-notes/dutch-oven-bread", "/blogs/kitchen-notes/bread-baking-in-a-dutch-oven"),
        ("/pages/shipping-policy", "/pages/shipping"),
        ("/pages/returns-policy", "/pages/returns"),
    ):
        old.append([path, 301, target, "", "", *signals(0, 9, [0, 1, 3, 6, 11], (0, 0))])
    # Already dead on the old site.
    sku = 1900
    for slug, category, inlinks, backlinks, on_new_site in (
        ("linen-napkin-roll", "kitchen-linens", 3, 3, False), ("copper-saucepan", "saucepans", 0, 5, False),
        ("knife-roll-canvas", "knives", 4, 0, False), ("pizza-stone", "bakeware", 2, 0, False),
        ("enamel-roaster", "dutch-ovens", 1, 2, True), ("bamboo-steamer", "saucepans", 2, 1, False),
        ("knife-guard-set", "knives", 3, 0, False), ("oven-thermometer", "gadgets", 0, 4, True),
    ):
        old.append([f"/products/{slug}", 404, "", f"BW-{sku}", category, inlinks, backlinks, 0])
        if on_new_site:
            new.append([f"/shop/{_redirect_leaf(category)}/{slug}", 200, "", f"BW-{sku}"])
        sku += 7
    for path, inlinks, backlinks in (
        ("/blogs/kitchen-notes/2020-01-new-year-kitchen-reset", 0, 2), ("/blogs/kitchen-notes/old-recipe-index", 6, 0),
        ("/blogs/kitchen-notes/2019-11-thanksgiving-prep", 0, 3), ("/pages/holiday-hours", 2, 1),
        ("/pages/gift-registry", 4, 0), ("/wholesale/catalog-2024", 3, 0),
    ):
        old.append([path, 404, "", "", "", inlinks, backlinks, 0])
    # The trade portal.
    old.append(["/wholesale", 200, "", "", "", 12, 4, 260])
    old.append(["/wholesale/login", 301, "/wholesale/portal", "", "", 5, 2, 0])
    for path, backlinks in (("/wholesale/portal", 1), ("/wholesale/price-list", 6), ("/wholesale/apply", 0),
                            ("/wholesale/terms", 0), ("/wholesale/order-form", 2)):
        old.append([path, 200, "", "", "", rng.randint(2, 9), backlinks, rng.randint(10, 140)])
    # Parameter URLs, some with links worth keeping that the new platform cannot keep.
    for path, backlinks in (
        ("/collections/frying-pans?sort=price-ascending", 0), ("/collections/knives?page=2", 0),
        ("/collections/bakeware?filter.v.availability=1", 0), ("/products/chef-knife-8-inch?variant=40112233", 9),
        ("/products/half-sheet-pan?variant=40110001", 2), ("/?utm_source=newsletter&utm_medium=email", 0),
        ("/search?q=dutch+oven", 0), ("/search?q=cast+iron", 1),
        ("/blogs/kitchen-notes/how-to-season-cast-iron?utm_source=pinterest", 14), ("/collections/sale?page=3", 0),
        ("/collections/gifts?sort=best-selling", 1), ("/products/walnut-end-grain-board?ref=gift-guide", 3),
        ("/pages/contact?subject=wholesale", 0), ("/cart?discount=WELCOME10", 0),
        ("/collections/dutch-ovens?color=red", 0), ("/collections/cutting-boards?sort=price-descending", 0),
        ("/products/enamel-dutch-oven-red?variant=40220011", 4), ("/collections/kitchen-linens?page=2", 0),
        ("/blogs/kitchen-notes?page=3", 0), ("/blogs/kitchen-notes/knife-sharpening-basics?utm_source=video", 6),
        ("/products/chef-apron-navy?utm_campaign=spring", 1), ("/search?q=apron", 0),
        ("/collections/new-arrivals?sort=created-descending", 0), ("/pages/faq?section=shipping", 0),
    ):
        old.append([path, 200, "", "", "", rng.randint(0, 6), backlinks, rng.randint(0, 90)])

    # The new site.
    for path in REDIRECT_UNCHANGED + ["/pages/shipping-and-returns", "/pages/gift-card", "/journal"]:
        new.append([path, 200, "", ""])
    for path in sorted({new_path for _slug, new_path in REDIRECT_CATEGORIES}):
        if path in REDIRECT_NEW_SITE_MOVES:
            new.append([path, 301, REDIRECT_NEW_SITE_MOVES[path], ""])
        else:
            new.append([path, 200, "", ""])
    for path in sorted(set(REDIRECT_NEW_SITE_MOVES.values()) - {"/pages/contact"}):
        new.append([path, 200, "", ""])
    new.append(["/pages/visit-us", 301, REDIRECT_NEW_SITE_MOVES["/pages/visit-us"], ""])
    for item in products:
        if item["new_url"] is None:
            continue
        merged = REDIRECT_MERGED_PRODUCTS.get(item["name"])
        folds = by_name[merged]["new_url"] if merged else item.get("folds_into")
        new.append([item["new_url"], 301, folds, item["sku"]] if folds else [item["new_url"], 200, "", item["sku"]])
    successor = 3001
    for name in REDIRECT_SLUG_REUSED:
        item = by_name[name]
        new.append([f"/shop/{_redirect_leaf(item['category'])}/{item['slug']}", 200, "", f"BW-{successor}"])
        successor += 11
    for leaf, slug in REDIRECT_NEW_ONLY_PRODUCTS:
        new.append([f"/shop/{leaf}/{slug}", 200, "", f"BW-{successor}"])
        successor += 11
    new.append(["/journal/care-and-cleaning", 200, "", ""])
    for slug in REDIRECT_POSTS:
        moved = re.sub(r"^\d{4}-\d{2}-", "", slug)
        if moved in REDIRECT_POSTS_NOT_MOVED:
            continue
        if moved in REDIRECT_MERGED_POSTS:
            new.append([f"/journal/{moved}", 301, f"/journal/{REDIRECT_MERGED_POSTS[moved]}", ""])
        else:
            new.append([f"/journal/{moved}", 200, "", ""])
    new.append(["/journal/pan-frying-guide", 200, "", ""])

    rng.shuffle(old)
    new.sort(key=lambda row: row[0])
    rename_rows = "\n".join(f"| `/collections/{slug}` | `{path}` |" for slug, path in REDIRECT_CATEGORIES)
    rename_rows += "\n" + "\n".join(f"| `{old_path}` | `{path}` |" for old_path, path in REDIRECT_PAGE_RENAMES)
    return {
        "seo-redirect-map/old_site_urls.csv": _csv_text(
            ["url", "status", "redirect_target", "sku", "category", "inlinks", "backlinks", "sessions_90d"], old),
        "seo-redirect-map/new_site_urls.csv": _csv_text(["url", "status", "redirect_to", "sku"], new),
        "seo-redirect-map/migration_rules.md": REDIRECT_RULES_MD.replace("{rename_rows}", rename_rows),
    }


# ------------------------------------------------------------------ seo-titles-meta

META_HEADER = ["page_id", "url", "page_type", "name", "primary_keyword", "secondary_keyword", "attributes",
               "price", "in_stock", "product_count", "index", "clicks_28d"]
# page_id, url, type, name, primary, secondary, attributes, price, in stock, product count, index, clicks.
# Six groups share a primary keyword among indexed pages; two more share one only with a noindex page.
META_PAGES = [
    ("C-01", "/collections/dog-beds", "category", "Dog Beds", "dog beds", "orthopedic dog beds", "", "", "", 38, "index", 1840),
    ("C-02", "/collections/cat-trees", "category", "Cat Trees", "cat trees", "cat towers", "", "", "", 24, "index", 880),
    ("C-03", "/collections/dog-harnesses", "category", "Dog Harnesses", "dog harness", "harnesses for dogs", "", "", "", 31, "index", 540),
    ("C-04", "/collections/dog-bowls", "category", "Dog Bowls", "dog bowls", "dog food bowls", "", "", "", 19, "index", 310),
    ("C-05", "/collections/puppy-training", "category", "Puppy Training", "puppy training pads", "puppy pads", "", "", "", 12, "index", 410),
    ("C-06", "/collections/aquarium-filters", "category", "Aquarium Filters", "aquarium filter", "fish tank filters", "", "", "", 15, "index", 300),
    ("C-07", "/collections/cat-litter", "category", "Cat Litter", "cat litter", "clumping cat litter", "", "", "", 22, "index", 1210),
    ("C-08", "/collections/bird-cages", "category", "Bird Cages", "bird cages", "large bird cage", "", "", "", 9, "index", 140),
    ("C-09", "/collections/small-animal-bedding", "category", "Small Animal Bedding", "small animal bedding", "hamster bedding", "", "", "", 14, "index", 95),
    ("C-10", "/collections/dog-toys", "category", "Dog Toys", "dog toys", "durable dog toys", "", "", "", 46, "index", 1500),
    ("C-11", "/collections/cat-toys", "category", "Cat Toys", "cat toys", "interactive cat toys", "", "", "", 33, "index", 620),
    ("C-12", "/collections/dog-beds?size=large", "category", "Dog Beds: Large", "dog beds", "large dog beds", "", "", "", 11, "noindex", 210),
    ("C-13", "/collections/clearance", "category", "Clearance", "pet supplies clearance", "discount pet supplies", "", "", "", 57, "noindex", 640),
    ("P-101", "/products/cloudrest-orthopedic-dog-bed", "product", "CloudRest Orthopedic Dog Bed", "dog bed", "washable dog bed", "memory foam base; washable cover", "89.00", "yes", "", "index", 420),
    ("P-104", "/products/summit-cat-tree", "product", "Summit Cat Tree", "cat tree with hammock", "multi level cat tree", "sisal scratching posts; two hammocks", "129.00", "no", "", "index", 260),
    ("P-107", "/products/trailmate-no-pull-harness", "product", "TrailMate No-Pull Harness", "dog harness", "no pull harness for dogs", "front clip; reflective stitching", "34.00", "yes", "", "index", 540),
    ("P-110", "/products/steel-dog-bowl-small", "product", "Steel Dog Bowl, Small", "stainless steel dog bowl", "dog water bowl", "non-slip rubber base; dishwasher safe", "12.00", "yes", "", "index", 75),
    ("P-113", "/products/steel-dog-bowl-large", "product", "Steel Dog Bowl, Large", "stainless steel dog bowl", "elevated dog bowl", "raised bamboo stand; dishwasher safe", "18.00", "yes", "", "index", 75),
    ("P-116", "/products/leakguard-training-pads", "product", "LeakGuard Training Pads, 50 Pack", "puppy training pads", "absorbent puppy pads", "five-layer core; scented attractant", "24.00", "yes", "", "index", 655),
    ("P-119", "/products/clearflow-aquarium-filter", "product", "ClearFlow Aquarium Filter", "aquarium filter", "hang on back filter", "three-stage filtration; quiet motor", "46.00", "yes", "", "index", 420),
    ("P-122", "/products/catnip-mouse-trio", "product", "Catnip Mouse Trio", "catnip toys", "catnip mice", "organic catnip; set of three", "9.00", "yes", "", "index", 90),
    ("P-125", "/products/chew-ring-xl", "product", "Chew Ring XL", "tough dog chew toy", "dog chew ring", "natural rubber; floats in water", "15.00", "no", "", "index", 130),
    ("P-128", "/products/feather-wand", "product", "Feather Wand", "cat feather wand", "wand toy for cats", "telescoping rod; refill feathers", "11.00", "yes", "", "index", 210),
    ("P-131", "/products/pine-litter-20lb", "product", "Pine Litter, 20 lb", "pine cat litter", "natural cat litter", "compostable pine pellets; low dust", "27.00", "no", "", "index", 340),
    ("P-134", "/products/flight-cage-xl", "product", "Flight Cage XL", "flight cage for birds", "large parakeet cage", "rolling stand; seed guard", "189.00", "yes", "", "index", 60),
    ("P-137", "/products/paper-bedding-30l", "product", "Paper Bedding, 30 L", "paper small animal bedding", "dust free hamster bedding", "unbleached paper; odour control", "19.00", "no", "", "index", 115),
    ("P-140", "/products/slow-feeder-bowl", "product", "Slow Feeder Bowl", "slow feeder dog bowl", "puzzle feeder bowl", "maze pattern; non-slip base", "16.00", "yes", "", "index", 380),
    ("P-143", "/products/travel-water-bottle", "product", "Travel Water Bottle", "dog travel water bottle", "portable dog water bottle", "leak-proof lock; fold-out bowl", "21.00", "no", "", "index", 170),
    ("P-146", "/products/heated-cat-bed", "product", "Heated Cat Bed", "heated cat bed", "self warming cat bed", "low-voltage pad; removable cover", "49.00", "yes", "", "index", 290),
    ("P-149", "/products/automatic-litter-box", "product", "Automatic Litter Box", "self cleaning litter box", "automatic litter box", "sealed waste drawer; app alerts", "249.00", "no", "", "index", 510),
    ("P-152", "/products/rope-tug-toy", "product", "Rope Tug Toy", "rope dog toy", "tug toy for dogs", "cotton rope; two handles", "13.00", "yes", "", "index", 150),
    ("P-155", "/products/hamster-wheel-silent", "product", "Silent Hamster Wheel", "silent hamster wheel", "quiet exercise wheel", "ball-bearing spin; solid running track", "22.00", "no", "", "index", 140),
    ("P-158", "/products/aquarium-heater-100w", "product", "Aquarium Heater, 100 W", "aquarium heater", "fish tank heater", "adjustable thermostat; shatterproof glass", "29.00", "yes", "", "index", 230),
    ("P-161", "/products/cloudrest-orthopedic-dog-bed-copy", "product", "CloudRest Orthopedic Dog Bed (copy)", "dog bed", "orthopedic dog bed", "memory foam base; washable cover", "89.00", "yes", "", "noindex", 30),
    ("G-201", "/guides/cat-tree-buying-guide", "guide", "How to Choose a Cat Tree", "cat trees", "how to choose a cat tree", "", "", "", "", "index", 1320),
    ("G-202", "/guides/puppy-potty-training", "guide", "Potty Training a Puppy", "puppy training pads", "potty training a puppy", "", "", "", "", "index", 120),
    ("G-203", "/guides/introduce-dog-to-cat", "guide", "Introducing a Dog to a Cat", "how to introduce a dog to a new cat", "dogs and cats living together", "", "", "", "", "index", 260),
    ("G-204", "/guides/aquarium-cycling", "guide", "Cycling a New Aquarium", "how to cycle a fish tank", "nitrogen cycle aquarium", "", "", "", "", "index", 340),
    ("G-205", "/guides/dog-bed-sizes", "guide", "Dog Bed Sizes", "dog bed size chart", "what size dog bed", "", "", "", "", "index", 510),
    ("G-206", "/guides/litter-box-placement", "guide", "Litter Box Placement", "where to put a litter box", "litter box placement", "", "", "", "", "index", 190),
    ("G-207", "/guides/harness-fitting", "guide", "Fitting a Dog Harness", "how to fit a dog harness", "dog harness sizing", "", "", "", "", "index", 230),
    ("G-208", "/guides/hamster-cage-setup", "guide", "Setting Up a Hamster Cage", "hamster cage setup", "hamster habitat ideas", "", "", "", "", "index", 80),
    ("G-209", "/guides/catnip-guide-old", "guide", "Catnip Guide (old)", "catnip toys", "what is catnip", "", "", "", "", "noindex", 300),
    ("G-210", "/guides/senior-dog-care", "guide", "Caring for a Senior Dog", "senior dog care", "caring for an older dog", "", "", "", "", "index", 450),
    ("G-211", "/guides/2023-gift-guide", "guide", "Gift Guide 2023", "gifts for dog lovers", "dog lover gift ideas", "", "", "", "", "noindex", 150),
    ("G-212", "/guides/hot-weather-dogs", "guide", "Keeping Dogs Cool", "how to keep a dog cool in hot weather", "dog heatstroke signs", "", "", "", "", "index", 390),
    # More categories.
    ("C-14", "/collections/dog-crates", "category", "Dog Crates", "dog crates", "wire dog crates", "", "", "", 17, "index", 760),
    ("C-15", "/collections/cat-carriers", "category", "Cat Carriers", "cat carrier", "carriers for cats", "", "", "", 11, "index", 260),
    ("C-16", "/collections/dog-leashes", "category", "Dog Leashes", "dog leashes", "leads for dogs", "", "", "", 27, "index", 690),
    ("C-17", "/collections/dog-collars", "category", "Dog Collars", "dog collars", "personalized dog collars", "", "", "", 35, "index", 980),
    ("C-18", "/collections/dog-grooming", "category", "Dog Grooming", "dog grooming supplies", "dog grooming tools", "", "", "", 29, "index", 450),
    ("C-19", "/collections/cat-scratchers", "category", "Cat Scratchers", "cat scratchers", "scratching posts", "", "", "", 16, "index", 370),
    ("C-20", "/collections/fish-food", "category", "Fish Food", "fish food", "tropical fish food", "", "", "", 13, "index", 180),
    ("C-21", "/collections/aquarium-heaters", "category", "Aquarium Heaters", "aquarium heaters", "tank heaters", "", "", "", 8, "index", 120),
    ("C-22", "/collections/hamster-cages", "category", "Hamster Cages", "hamster cages", "small animal cages", "", "", "", 10, "index", 210),
    ("C-23", "/collections/dog-treats", "category", "Dog Treats", "dog treats", "training treats for dogs", "", "", "", 41, "index", 1320),
    ("C-24", "/collections/senior-dogs", "category", "Senior Dog Supplies", "senior dog supplies", "supplies for older dogs", "", "", "", 18, "index", 230),
    ("C-25", "/collections/new-arrivals", "category", "New Arrivals", "new pet supplies", "latest pet products", "", "", "", 64, "noindex", 400),
    ("C-26", "/collections/dog-toys?sort=price", "category", "Dog Toys by Price", "dog toys", "cheap dog toys", "", "", "", 46, "noindex", 160),
    ("C-27", "/collections/dog-beds?page=2", "category", "Dog Beds, Page 2", "dog beds", "dog bed sale", "", "", "", 38, "noindex", 90),
    # More products: size variants that share a keyword, ties, and pages a noindex page out-clicks.
    ("P-164", "/products/cloudrest-bed-small", "product", "CloudRest Orthopedic Bed, Small", "orthopedic dog bed", "orthopedic bed for small dogs", "memory foam base; washable cover", "69.00", "yes", "", "index", 210),
    ("P-167", "/products/cloudrest-bed-medium", "product", "CloudRest Orthopedic Bed, Medium", "orthopedic dog bed", "orthopedic bed for medium dogs", "memory foam base; washable cover", "79.00", "yes", "", "index", 480),
    ("P-170", "/products/cloudrest-bed-large", "product", "CloudRest Orthopedic Bed, Large", "orthopedic dog bed", "orthopedic bed for large dogs", "memory foam base; washable cover", "99.00", "no", "", "index", 480),
    ("P-173", "/products/folding-crate-36", "product", "Folding Dog Crate, 36 in", "folding dog crate", "36 inch dog crate", "double doors; divider panel", "129.00", "yes", "", "index", 300),
    ("P-176", "/products/folding-crate-42", "product", "Folding Dog Crate, 42 in", "folding dog crate", "42 inch dog crate", "double doors; leak-proof tray", "149.00", "yes", "", "index", 150),
    ("P-179", "/products/softside-cat-carrier", "product", "Softside Cat Carrier", "cat carrier", "softside carrier for cats", "mesh windows; shoulder strap", "39.00", "yes", "", "index", 260),
    ("P-182", "/products/oatmeal-dog-shampoo", "product", "Oatmeal Dog Shampoo", "dog shampoo", "oatmeal shampoo for dogs", "soap-free formula; 500 ml bottle", "14.00", "yes", "", "index", 120),
    ("P-185", "/products/puppy-shampoo", "product", "Tearless Puppy Shampoo", "dog shampoo", "tearless puppy shampoo", "tear-free formula; 250 ml bottle", "12.00", "no", "", "index", 95),
    ("P-188", "/products/senior-dog-food-5lb", "product", "Senior Dog Food, 5 lb", "senior dog food", "food for older dogs", "chicken and brown rice; joint support blend", "32.00", "yes", "", "index", 330),
    ("P-191", "/products/reflective-leash", "product", "Reflective Dog Leash", "reflective dog leash", "night walking leash", "reflective stitching; padded handle", "22.00", "yes", "", "index", 140),
    ("P-194", "/products/martingale-collar", "product", "Martingale Collar", "martingale collar", "no slip dog collar", "nylon webbing; chain loop", "18.00", "no", "", "index", 160),
    ("P-197", "/products/deshedding-brush", "product", "Deshedding Brush", "deshedding brush", "dog undercoat brush", "stainless teeth; release button", "26.00", "yes", "", "index", 390),
    ("P-200", "/products/nail-clippers", "product", "Dog Nail Clippers", "dog nail clippers", "nail trimmer for dogs", "safety guard; non-slip grip", "15.00", "yes", "", "index", 280),
    ("P-203", "/products/sisal-scratching-post", "product", "Sisal Scratching Post", "cat scratcher", "sisal scratching post", "natural sisal rope; weighted base", "29.00", "yes", "", "index", 220),
    ("P-206", "/products/cardboard-scratcher", "product", "Cardboard Scratcher", "cardboard cat scratcher", "corrugated scratch pad", "recycled cardboard; catnip included", "12.00", "no", "", "index", 90),
    ("P-209", "/products/tropical-flakes", "product", "Tropical Flakes", "tropical fish flakes", "fish flake food", "colour-enhancing formula; 100 g tub", "8.00", "yes", "", "index", 110),
    ("P-212", "/products/betta-pellets", "product", "Betta Pellets", "betta fish food", "betta pellets", "floating pellets; 50 g jar", "6.00", "yes", "", "index", 75),
    ("P-215", "/products/hamster-cage-deluxe", "product", "Deluxe Hamster Cage", "large hamster cage", "hamster habitat", "deep base; two levels", "89.00", "no", "", "index", 130),
    ("P-218", "/products/finch-seed-mix", "product", "Finch Seed Mix", "finch food", "finch seed mix", "millet and canary seed; 2 kg bag", "11.00", "yes", "", "index", 60),
    ("P-221", "/products/treat-pouch", "product", "Training Treat Pouch", "dog treat pouch", "training treat bag", "magnetic closure; belt clip", "16.00", "yes", "", "index", 105),
    ("P-224", "/products/chicken-jerky-treats", "product", "Chicken Jerky Treats", "chicken jerky dog treats", "single ingredient dog treats", "single ingredient; 200 g pouch", "13.00", "yes", "", "index", 340),
    ("P-227", "/products/dental-chews", "product", "Dental Chews, 30 Pack", "dental chews for dogs", "dog teeth cleaning chews", "vet-formulated texture; 30 chews", "24.00", "no", "", "index", 410),
    ("P-230", "/products/top-entry-litter-box", "product", "Top Entry Litter Box", "top entry litter box", "covered litter box", "grated lid; low-tracking design", "45.00", "yes", "", "index", 200),
    ("P-233", "/products/litter-mat", "product", "Litter Mat", "cat litter mat", "litter trapping mat", "honeycomb layers; waterproof base", "19.00", "yes", "", "index", 150),
    ("P-236", "/products/indoor-cat-food-6lb", "product", "Indoor Cat Food, 6 lb", "indoor cat food", "dry food for indoor cats", "salmon recipe; hairball control", "28.00", "yes", "", "index", 310),
    ("P-239", "/products/wet-cat-food-variety", "product", "Wet Cat Food Variety Pack", "wet cat food", "cat food variety pack", "pate texture; 12 cans", "18.00", "no", "", "index", 260),
    ("P-242", "/products/laser-pointer", "product", "Laser Pointer Toy", "cat laser toy", "laser pointer for cats", "USB charging; auto shut-off", "10.00", "yes", "", "index", 230),
    ("P-245", "/products/crinkle-tunnel", "product", "Crinkle Cat Tunnel", "cat tunnel", "crinkle tunnel", "collapsible; three openings", "17.00", "yes", "", "index", 140),
    ("P-248", "/products/squeaky-ball-set", "product", "Squeaky Ball Set", "squeaky dog balls", "dog ball toys", "natural rubber; set of four", "9.00", "no", "", "index", 115),
    ("P-251", "/products/elevated-bowl-stand", "product", "Elevated Bowl Stand", "raised dog bowl stand", "elevated feeder", "adjustable height; bamboo top", "34.00", "yes", "", "index", 190),
    ("P-254", "/products/aquarium-gravel", "product", "Natural Aquarium Gravel", "aquarium gravel", "fish tank gravel", "rinsed river stone; 5 kg bag", "15.00", "yes", "", "index", 85),
    ("P-257", "/products/bird-perch-set", "product", "Bird Perch Set", "bird perches", "natural wood perch", "manzanita wood; three sizes", "14.00", "yes", "", "index", 55),
    ("P-260", "/products/dog-shampoo-old-listing", "product", "Dog Shampoo (old listing)", "dog shampoo", "dog wash", "soap-free formula; 500 ml bottle", "14.00", "no", "", "noindex", 900),
    ("P-263", "/products/car-seat-cover", "product", "Dog Car Seat Cover", "dog car seat cover", "back seat cover for dogs", "waterproof fabric; side flaps", "49.00", "yes", "", "index", 270),
    ("P-266", "/products/dog-raincoat", "product", "Dog Raincoat", "dog raincoat", "waterproof dog coat", "reflective trim; hood", "29.00", "no", "", "index", 180),
    ("P-269", "/products/cooling-mat", "product", "Dog Cooling Mat", "dog cooling mat", "pressure activated cooling pad", "gel-filled; no water needed", "39.00", "yes", "", "index", 360),
    ("P-272", "/products/cat-water-fountain", "product", "Cat Water Fountain", "cat water fountain", "pet drinking fountain", "carbon filter; quiet pump", "35.00", "yes", "", "index", 440),
    ("P-275", "/products/cat-water-fountain-v1", "product", "Cat Water Fountain (first version)", "cat water fountain", "pet water fountain", "carbon filter; quiet pump", "29.00", "no", "", "noindex", 50),
    ("P-278", "/products/cloudrest-bed-xl", "product", "CloudRest Orthopedic Bed, XL", "orthopedic dog bed", "orthopedic bed for giant dogs", "memory foam base; washable cover", "119.00", "no", "", "noindex", 600),
    # More guides.
    ("G-213", "/guides/clean-fish-tank", "guide", "How to Clean a Fish Tank (2022)", "how to clean a fish tank", "aquarium cleaning steps", "", "", "", "", "index", 220),
    ("G-214", "/guides/fish-tank-cleaning", "guide", "Fish Tank Cleaning, Step by Step", "how to clean a fish tank", "fish tank maintenance", "", "", "", "", "index", 400),
    ("G-215", "/guides/cat-carrier-training", "guide", "Getting a Cat Used to a Carrier", "cat carrier", "carrier training for cats", "", "", "", "", "index", 260),
    ("G-216", "/guides/senior-dog-nutrition", "guide", "Feeding a Senior Dog", "senior dog food", "what to feed an older dog", "", "", "", "", "index", 330),
    ("G-217", "/guides/crate-training", "guide", "Crate Training a Puppy", "crate training", "how to crate train a puppy", "", "", "", "", "index", 520),
    ("G-218", "/guides/leash-training", "guide", "Leash Training Basics", "leash training a puppy", "loose leash walking", "", "", "", "", "index", 300),
    ("G-219", "/guides/grooming-at-home", "guide", "Grooming Your Dog at Home", "how to groom a dog at home", "home dog grooming", "", "", "", "", "index", 270),
    ("G-220", "/guides/bird-cage-setup", "guide", "Setting Up a Bird Cage", "bird cage setup", "where to put a bird cage", "", "", "", "", "index", 90),
    ("G-221", "/guides/cat-dental-care", "guide", "Cat Dental Care", "cat dental care", "how to clean cat teeth", "", "", "", "", "index", 140),
    ("G-222", "/guides/aquarium-heater-guide", "guide", "Choosing an Aquarium Heater", "what size aquarium heater", "aquarium heater wattage", "", "", "", "", "index", 150),
    ("G-223", "/guides/crate-training-old", "guide", "Crate Training (old)", "crate training", "crate training schedule", "", "", "", "", "noindex", 700),
    ("G-224", "/guides/dog-treat-guide", "guide", "Choosing Dog Treats", "healthy dog treats", "low calorie dog treats", "", "", "", "", "index", 410),
    ("G-225", "/guides/summer-sale-2024", "guide", "Summer Sale 2024", "pet supplies sale", "summer pet deals", "", "", "", "", "noindex", 260),
    ("G-226", "/guides/print/senior-dog-care", "guide", "Caring for a Senior Dog (print)", "senior dog care", "caring for an older dog", "", "", "", "", "noindex", 40),
]


def meta_rules_md() -> str:
    from eval_runner import task_facts_seo as facts  # the checker's own constants

    low, high = facts.META_DESCRIPTION_RANGE
    order = ", ".join(facts.META_SUFFIXES)
    suffixes = "\n".join(f"  - {kind}: `{suffix}`" for kind, suffix in facts.META_SUFFIXES.items())
    return f"""\
# Quillon Pet Supply: rules for titles and meta descriptions

Quillon Pet Supply sells pet food, beds, toys and supplies online at www.quillonpets.example. Write a title and a meta description for every page in `page_inventory.csv` that is indexed, following these rules.

## Which pages
- A page whose `index` is `noindex` gets no row, and it takes no part in the keyword rule below.

## The target keyword
- Each page targets its `primary_keyword`.
- When two or more indexed pages have the same `primary_keyword`, only one of them keeps it: the page with the most `clicks_28d`; on a tie, the page whose type comes first in this order: {order}; on a further tie, the page whose `page_id` comes first. Every other page of the group targets its `secondary_keyword` instead, and neither its title nor its meta description may contain the primary keyword it gave up.
- Keywords are matched as whole words. Capital letters may differ, and a hyphen may stand for a space; nothing else may.

## Titles
- At most {facts.META_TITLE_MAX} characters, counting spaces and the suffix.
- Contain the page's target keyword.
- End with the suffix for the page type, exactly:
{suffixes}
- The brand name "{facts.META_BRAND}" appears in a title only in its suffix.
- No price and no `$`.

## Meta descriptions
- {low} to {high} characters, counting spaces.
- Contain the page's target keyword. A page that keeps its primary keyword also contains its `secondary_keyword`.
- A product page contains the first of its `attributes` (they are separated by semicolons), word for word.
- A category page contains its `product_count`, written in digits.
- An in-stock product page (`in_stock` is yes) contains its price, written as `$` and the `price` value exactly as the inventory gives it (`$34.00`). No other meta description contains a price or a `$`: an out-of-stock product's price is not shown anywhere.

## No duplicates
- No two titles are the same, and no two meta descriptions are the same.
"""


def build_titles_meta() -> dict[str, str]:
    rows = sorted((list(page) for page in META_PAGES), key=lambda row: row[1])
    return {
        "seo-titles-meta/page_inventory.csv": _csv_text(META_HEADER, rows),
        "seo-titles-meta/title_rules.md": meta_rules_md(),
    }


# --------------------------------------------------------------------- blog-post

# The price source comes first in the file and is the later one; the older menu,
# with the superseded price, comes last.
BLOG_SOURCES_MD = """\
# Brightline Heating: sources for the furnace-noise article

Brightline Heating is a local heating service for homeowners in North Valley. Each source gives the date it was published.

## Office note: diagnostic visit price (published 2026-01-05)
- Furnace diagnostic visit: $95.

## Approved homeowner checks (published 2025-09-03)
- Thermostat: set to heat, with the set point above the room temperature.
- Air filter: a 1-inch filter is due for replacement every 90 days.
- Clearance: keep 3 feet clear around the furnace.
- Registers: supply registers open and not blocked by furniture.
- When a noise happens: note whether it starts with the burner, with the blower, or runs all the time.

## 2025 service-call summary (published 2026-01-14)
- Brightline answered 1,412 furnace calls about a noise in 2025. By the noise the homeowner described:
- Whistling or howling, usually airflow (a clogged filter, closed registers): 31%.
- Rattling, often a loose panel or duct: 22%.
- Banging or a boom when the burner lights: 18%.
- Squealing or screeching, often the blower: 14%.
- Clicking that repeats without the burner lighting: 9%.
- Grinding or scraping: 6%.

## Safety (published 2025-09-03)
- If you smell gas: leave the building, do not use switches or flames, and call the gas emergency line from outside.
- Banging when the burner lights, grinding, repeated clicking without ignition, an electrical burning smell, or a furnace that keeps shutting down need a licensed technician.
- Never open, bypass or repair gas or electrical parts yourself.

## Service menu (published 2025-02-10)
- Service area: North Valley.
- Furnace diagnostic visit: $89.
- Booking: times vary, and Brightline makes no promise about response times.
"""
BLOG_SITE_HEADER = ["url", "title", "tags", "status", "noindex", "primary_keyword", "sessions_28d"]
# The five live furnace pages with the most sessions are the links; the fifth place is a tie
# the URL order breaks. Above them sit a redirect, a noindex page, a furnace URL that is not
# tagged furnace, and two other noises.
BLOG_SITE_MAP = [
    ("/", "Brightline Heating", "home", 200, "no", "brightline heating", 5400),
    ("/services/furnace-maintenance", "Furnace Maintenance", "furnace;services", 200, "no", "furnace maintenance", 1320),
    ("/blog/heat-pump-vs-furnace", "Heat Pump or Furnace?", "heat-pump", 200, "no", "heat pump vs furnace", 2600),
    ("/blog/furnace-short-cycling", "Why Your Furnace Short Cycles", "furnace", 301, "no", "furnace short cycling", 1650),
    ("/blog/carbon-monoxide-safety", "Carbon Monoxide Safety at Home", "furnace;safety", 200, "yes", "carbon monoxide safety", 1540),
    ("/book/furnace-diagnostic", "Book a Furnace Diagnostic", "booking", 200, "no", "book a furnace diagnostic", 1900),
    ("/blog/furnace-filter-guide", "The Furnace Filter Guide", "furnace;maintenance", 200, "no", "furnace filter guide", 2140),
    ("/blog/ac-making-noise", "Why Is My AC Making Noise?", "cooling", 200, "no", "ac making noise", 2300),
    ("/services/furnace-repair", "Furnace Repair", "furnace;services", 200, "no", "furnace repair", 1760),
    ("/blog/why-is-my-furnace-blowing-cold-air", "Why Is My Furnace Blowing Cold Air?", "furnace", 200, "no", "furnace blowing cold air", 1980),
    ("/blog/water-heater-noises", "Water Heater Noises Explained", "water-heater", 200, "no", "water heater noises", 1210),
    ("/blog/thermostat-troubleshooting", "Thermostat Troubleshooting", "furnace;thermostat", 200, "no", "thermostat troubleshooting", 1450),
    ("/blog/pilot-light-out", "Pilot Light Out?", "furnace", 404, "no", "pilot light out", 900),
    ("/blog/furnace-keeps-turning-off", "My Furnace Keeps Turning Off", "furnace", 200, "no", "furnace keeps turning off", 1320),
    ("/blog/winter-furnace-checklist", "A Winter Furnace Checklist", "furnace;seasonal", 200, "no", "winter furnace checklist", 1100),
    ("/blog/furnace-smells", "Furnace Smells and What They Mean", "furnace", 200, "no", "furnace smells", 870),
    ("/services/furnace-installation", "Furnace Installation", "furnace;services", 200, "no", "furnace installation", 760),
    ("/services/heat-pump-repair", "Heat Pump Repair", "heat-pump;services", 200, "no", "heat pump repair", 980),
    ("/services/ac-repair", "AC Repair", "cooling;services", 200, "no", "ac repair", 1450),
    ("/blog/how-old-is-my-furnace", "How Old Is My Furnace?", "furnace", 200, "no", "how old is my furnace", 610),
    ("/blog/furnace-efficiency-ratings", "Furnace Efficiency Ratings", "furnace", 200, "no", "furnace efficiency ratings", 540),
    ("/blog/space-heater-safety", "Space Heater Safety", "safety", 200, "no", "space heater safety", 700),
    ("/about", "About Brightline", "about", 200, "no", "about brightline", 400),
    ("/contact", "Contact Brightline", "contact", 200, "no", "contact brightline", 820),
    ("/reviews", "What Customers Say", "about", 200, "yes", "brightline reviews", 300),
]


def build_blog_post() -> dict[str, str]:
    return {
        "blog-post/sources.md": BLOG_SOURCES_MD,
        "blog-post/site_map.csv": _csv_text(BLOG_SITE_HEADER, [list(row) for row in BLOG_SITE_MAP]),
    }


# ------------------------------------------------------------------------- driver

BUILDERS = (build_redirect_map, build_titles_meta, build_blog_post)


def build_all() -> dict[str, str]:
    files: dict[str, str] = {}
    for builder in BUILDERS:
        files.update(builder())
    return files


def drift() -> list[str]:
    problems = []
    for name, text in build_all().items():
        path = FIXTURES / name
        if not path.exists():
            problems.append(f"missing fixture {name}")
        elif path.read_text() != text:
            problems.append(f"fixture {name} differs from the generator's output")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="write the fixtures")
    group.add_argument("--check", action="store_true", help="report drift, change nothing")
    args = parser.parse_args(argv)
    if args.write:
        files = build_all()
        for name, text in files.items():
            path = FIXTURES / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        print(f"wrote {len(files)} fixture files under {FIXTURES.relative_to(REPO_ROOT)}")
        return 0
    problems = drift()
    for problem in problems:
        print("DRIFT: " + problem, file=sys.stderr)
    if not problems:
        print("OK: the fixtures are what this script writes")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
