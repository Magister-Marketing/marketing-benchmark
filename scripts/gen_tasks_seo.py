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
]
# The rename table's addresses that the new site's own list redirects again.
REDIRECT_NEW_SITE_MOVES = {
    "/shop/cast-iron": "/shop/cast-iron-cookware",
    "/shop/food-storage": "/shop/pantry-storage",
    "/pages/visit-us": "/pages/contact",
}
REDIRECT_PAGE_RENAMES = [
    ("/pages/shipping", "/pages/shipping-and-returns"),
    ("/pages/returns", "/pages/shipping-and-returns"),
    ("/pages/our-story", "/pages/about"),
    ("/pages/care-guides", "/journal/care-and-cleaning"),
    ("/pages/store-locations", "/pages/visit-us"),       # stale: the new site redirects it
    ("/blogs/kitchen-notes", "/journal"),
]
REDIRECT_UNCHANGED = [
    "/", "/cart", "/search", "/account/login", "/account/register",
    "/pages/about", "/pages/contact", "/pages/faq", "/pages/privacy-policy", "/pages/terms",
]
# Products by old category: the name, and the new slug where the new site renamed it.
REDIRECT_PRODUCTS = {
    "frying-pans": ["Classic Fry Pan 8 Inch", "Classic Fry Pan 10 Inch", "Classic Fry Pan 12 Inch", "Everyday Skillet 10",
                    "Carbon Steel Pan 11", "Crepe Pan 10", "Grill Pan Square", "Paella Pan 14", "Egg Pan Mini"],
    "saucepans": ["Saucepan 1.5 Quart", "Saucepan 3 Quart", "Saucier 2 Quart", "Butter Warmer", "Milk Pan Small",
                  "Stockpot 8 Quart", "Pasta Pot 6 Quart"],
    "dutch-ovens": ["Round Dutch Oven 5.5 Quart", "Oval Dutch Oven 7 Quart", "Braiser 3.5 Quart", "Mini Cocotte Pair",
                    "Bread Oven Cloche", "Dutch Oven Lid Knob"],
    "cast-iron": ["Cast Iron Skillet 10", "Cast Iron Skillet 12", "Cast Iron Griddle", "Cast Iron Wok",
                  "Chainmail Scrubber", "Skillet Handle Sleeve"],
    "stainless-steel": ["Tri Ply Skillet 10", "Tri Ply Saute Pan", "Tri Ply Stockpot", "Steamer Insert", "Roasting Pan Rack"],
    "nonstick": ["Ceramic Nonstick Pan 10", "Ceramic Nonstick Pan 12", "Nonstick Omelette Pan", "Nonstick Wok"],
    "knives": ["Chef Knife 8 Inch", "Santoku 7 Inch", "Paring Knife 3.5", "Bread Knife 9", "Utility Knife 6",
               "Boning Knife", "Nakiri 6.5", "Honing Steel"],
    "knife-sets": ["Essential Knife Trio", "Block Set 7 Piece", "Steak Knife Set 4", "Magnetic Knife Strip"],
    "cutting-boards": ["Walnut End Grain Board", "Maple Board Large", "Bamboo Prep Board", "Board Oil Bottle",
                       "Cherry Serving Board"],
    "bakeware": ["Half Sheet Pan", "Quarter Sheet Pan", "Loaf Pan", "Round Cake Pan 9", "Muffin Tin 12",
                 "Pie Dish Ceramic", "Bundt Pan"],
    "baking-tools": ["Bench Scraper", "French Rolling Pin", "Pastry Brush", "Cooling Rack", "Proofing Basket",
                     "Dough Whisk"],
    "utensils": ["Fish Spatula", "Silicone Spatula", "Wooden Spoon Set", "Kitchen Tongs 12", "Ladle Stainless",
                 "Slotted Spoon"],
    "gadgets": ["Garlic Press", "Microplane Zester", "Salad Spinner", "Mandoline Slicer", "Herb Stripper"],
    "storage": ["Glass Container Set", "Spice Jar Set", "Bread Box Bamboo", "Produce Saver", "Flour Canister"],
    "kitchen-linens": ["Linen Tea Towel Pair", "Waffle Dish Towel", "Canvas Apron", "Oven Mitt Pair", "Linen Napkin Set"],
    "coffee-tea": ["Pour Over Kettle", "French Press 8 Cup", "Tea Infuser Mug", "Coffee Canister", "Milk Frother"],
    "gifts": ["Starter Kitchen Gift Set", "Baker Gift Set", "Knife Care Gift Set"],
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
                           "Steak Knife Set 4"]
# Retired with exactly one signal above zero: (inlinks, backlinks, sessions).
REDIRECT_RETIRED_ONE_SIGNAL = {"Chainmail Scrubber": (0, 0, 1), "Proofing Basket": (1, 0, 0), "Coffee Canister": (0, 1, 0)}
REDIRECT_RETIRED = ["Crepe Pan 10", "Mini Cocotte Pair", "Steamer Insert", "Waffle Dish Towel", "Tea Infuser Mug",
                    "Cast Iron Wok", "Spice Jar Set", "Egg Pan Mini", "Herb Stripper"]
# Retired, and the new site reuses the slug for a successor with a new SKU.
REDIRECT_SLUG_REUSED = ["Everyday Skillet 10", "Santoku 7 Inch", "Half Sheet Pan", "Pour Over Kettle",
                        "Glass Container Set"]
# New-site product pages that are merged into another (status 301 in the new list).
REDIRECT_MERGED_PRODUCTS = {
    "Classic Fry Pan 8 Inch": "Classic Fry Pan 10 Inch", "Classic Fry Pan 12 Inch": "Classic Fry Pan 10 Inch",
    "Cast Iron Skillet 12": "Cast Iron Skillet 10", "Tri Ply Stockpot": "Stockpot 8 Quart",
}
REDIRECT_NEW_ONLY_PRODUCTS = [("frying-pans", "induction-fry-pan-11"), ("kitchen-knives", "cleaver-7in"),
                              ("bakeware", "baguette-tray"), ("pantry-storage", "rice-bin"), ("linens", "bar-towels")]

REDIRECT_POSTS = [
    "how-to-season-cast-iron", "cleaning-stainless-steel-pans", "choosing-a-dutch-oven", "knife-sharpening-basics",
    "end-grain-vs-edge-grain", "caring-for-wooden-boards", "sheet-pan-dinners", "perfect-pan-sauce", "braising-101",
    "bread-baking-in-a-dutch-oven", "how-to-hone-a-knife", "nonstick-pan-care", "oils-for-seasoning",
    "stocking-a-first-kitchen", "pantry-organization-ideas", "how-to-use-a-bench-scraper", "cooling-racks-explained",
    "whipping-cream-by-hand", "kitchen-tools-under-25", "making-cold-brew-at-home", "pour-over-coffee-guide",
    "tea-towel-care", "how-to-clean-a-cast-iron-griddle", "carbon-steel-vs-cast-iron", "induction-cookware-guide",
    "oven-safe-pans", "saute-vs-fry", "how-to-store-knives", "choosing-a-cutting-board", "linen-vs-cotton-towels",
    # A number at the front that is not a YYYY-MM- date: the slug stays as it is.
    "10-knife-skills-every-cook-needs", "2024-gift-guide", "2025-kitchen-trends",
    # Dated slugs: the date goes. The last two have no page on the new site.
    "2022-03-spring-baking-checklist", "2023-11-holiday-baking-timeline", "2024-02-valentines-dinner-for-two",
    "2023-05-mothers-day-brunch", "2021-10-soup-season-staples", "2024-08-tomato-season-recipes",
    "2021-06-summer-grilling-tools", "2022-09-back-to-school-lunches",
    # Not carried over.
    "our-new-warehouse", "meet-the-team-2022",
]
REDIRECT_POSTS_NOT_MOVED = {"summer-grilling-tools", "back-to-school-lunches", "our-new-warehouse", "meet-the-team-2022"}
REDIRECT_MERGED_POSTS = {"saute-vs-fry": "pan-frying-guide", "linen-vs-cotton-towels": "tea-towel-care"}

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


def redirect_product_rows() -> list[dict]:
    """Every product of the old site with its SKU, signals and new URL (or None when retired)."""
    rng = random.Random(4471)
    new_leaf = {slug: new.rsplit("/", 1)[1] for slug, new in REDIRECT_CATEGORIES}
    new_leaf.update({"cast-iron": "cast-iron-cookware", "storage": "pantry-storage"})
    retired = set(REDIRECT_RETIRED_SILENT) | set(REDIRECT_RETIRED_ONE_SIGNAL) | set(REDIRECT_RETIRED) | set(REDIRECT_SLUG_REUSED)
    products, sku = [], 1001
    for category, names in REDIRECT_PRODUCTS.items():
        for name in names:
            slug = _slug(name)
            if name in REDIRECT_RETIRED_SILENT:
                signals = (0, 0, 0)
            elif name in REDIRECT_RETIRED_ONE_SIGNAL:
                signals = REDIRECT_RETIRED_ONE_SIGNAL[name]
            else:
                signals = (rng.randint(2, 38), rng.choice([0, 0, 0, 1, 1, 2, 3, 5, 8, 12]), rng.randint(15, 2400))
            products.append({
                "name": name, "category": category, "slug": slug, "sku": f"BW-{sku}",
                "inlinks": signals[0], "backlinks": signals[1], "sessions": signals[2],
                "new_url": None if name in retired else f"/shop/{new_leaf[category]}/{REDIRECT_NEW_SLUGS.get(name, slug)}",
            })
            sku += 1 + rng.randint(0, 3)
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
    for path in ("/collections/holiday-2023", "/collections/black-friday-2024", "/pages/press-2019"):
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
        ("/collections/pans", "/collections/frying-pans"),
        ("/collections/food-storage", "/collections/storage"),
        ("/blogs/kitchen-notes/seasoning-cast-iron", "/blogs/kitchen-notes/how-to-season-cast-iron"),
        ("/pages/shipping-policy", "/pages/shipping"),
    ):
        old.append([path, 301, target, "", "", *signals(0, 9, [0, 1, 3, 6, 11], (0, 0))])
    # Already dead on the old site.
    sku = 1900
    for slug, category, inlinks, backlinks, on_new_site in (
        ("linen-napkin-roll", "kitchen-linens", 3, 3, False), ("copper-saucepan", "saucepans", 0, 5, False),
        ("knife-roll-canvas", "knives", 4, 0, False), ("pizza-stone", "bakeware", 2, 0, False),
        ("enamel-roaster", "dutch-ovens", 1, 2, True),
    ):
        old.append([f"/products/{slug}", 404, "", f"BW-{sku}", category, inlinks, backlinks, 0])
        if on_new_site:
            new.append([f"/shop/dutch-ovens/{slug}", 200, "", f"BW-{sku}"])
        sku += 7
    for path, inlinks, backlinks in (
        ("/blogs/kitchen-notes/2020-01-new-year-kitchen-reset", 0, 2), ("/blogs/kitchen-notes/old-recipe-index", 6, 0),
        ("/pages/holiday-hours", 2, 1), ("/wholesale/catalog-2024", 3, 0),
    ):
        old.append([path, 404, "", "", "", inlinks, backlinks, 0])
    # The trade portal.
    old.append(["/wholesale", 200, "", "", "", 12, 4, 260])
    old.append(["/wholesale/login", 301, "/wholesale/portal", "", "", 5, 2, 0])
    for path, backlinks in (("/wholesale/portal", 1), ("/wholesale/price-list", 6), ("/wholesale/apply", 0), ("/wholesale/terms", 0)):
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
    ):
        old.append([path, 200, "", "", "", rng.randint(0, 6), backlinks, rng.randint(0, 90)])

    # The new site.
    for path in REDIRECT_UNCHANGED + ["/pages/shipping-and-returns", "/journal"]:
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
        if merged:
            new.append([item["new_url"], 301, by_name[merged]["new_url"], item["sku"]])
        else:
            new.append([item["new_url"], 200, "", item["sku"]])
    successor = 3001
    for name in REDIRECT_SLUG_REUSED:
        item = by_name[name]
        leaf = "pantry-storage" if item["category"] == "storage" else dict(REDIRECT_CATEGORIES)[item["category"]].rsplit("/", 1)[1]
        new.append([f"/shop/{leaf}/{item['slug']}", 200, "", f"BW-{successor}"])
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


# ------------------------------------------------------------------------- driver

BUILDERS = (build_redirect_map,)


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
