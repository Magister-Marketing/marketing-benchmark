"""The SEO tasks of the 35-task board: fixtures, oracles, traps and parsing.

For each task:

- the committed fixtures are exactly what `scripts/gen_tasks_seo.py` writes;
- every value a program checks, and every count a check's wording quotes, is
  recomputed here from the committed fixtures by code that shares nothing
  with `eval_runner/task_facts_seo.py`;
- a reference reply built from that recomputation passes every program check,
  and an empty reply passes none;
- the careless reading each trap is built for scores zero on the check written
  for it.
"""
import collections
import csv
import importlib.util
import io
import json
import re

import pytest

from eval_runner import bench, task_facts_seo

FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("gen_tasks_seo", bench.REPO_ROOT / "scripts" / "gen_tasks_seo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((FIXTURES / name).read_text())))


def _task(task_id: str) -> dict:
    return bench.load_tasks()[task_id]


def _by_id(task: dict) -> dict[str, dict]:
    return {c["id"]: c for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section]}


def _results(task_id: str, response: str) -> dict:
    task = _task(task_id)
    return bench.programmatic_results(task, bench.measured_facts(task, response))


def _failed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, item in results.items() if not item["pass"]}


def _zeroed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, item in results.items() if item["score"] == 0}


def _all_pass(results: dict) -> bool:
    return bool(results) and all(item["pass"] and item["score"] == 1.0 for item in results.values())


def _csv_block(name: str, header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows([header, *rows])
    return f"### {name}\n```csv\n{out.getvalue().rstrip()}\n```\n"


def _answer_block(values: list) -> str:
    return "\n".join(f"A{index}: {value}" for index, value in enumerate(values, 1)) + "\n"


def test_the_fixtures_are_what_the_generator_writes(generator):
    assert generator.drift() == []
    for task_id in ("seo-redirect-map", "seo-titles-meta", "blog-post"):
        task = _task(task_id)
        assert task["split"] == "development"
        assert all((bench.REPO_ROOT / path).is_file() for path in task["fixtures"])
        size = sum((bench.REPO_ROOT / path).stat().st_size for path in task["fixtures"])
        assert size < 60_000, (task_id, size)
        assert bench.free_credit_scores(task) == {}, task_id  # an empty reply earns nothing


# ------------------------------------------------------------------ seo-redirect-map

REDIRECT_DIR = "seo-redirect-map/"


def _redirect_oracle():
    """Each old URL's row under the migration rules, recomputed from the fixtures."""
    old = _table(REDIRECT_DIR + "old_site_urls.csv")
    new = _table(REDIRECT_DIR + "new_site_urls.csv")
    rules = (FIXTURES / REDIRECT_DIR / "migration_rules.md").read_text()
    table = dict(re.findall(r"(?m)^\| `(/[^`]*)` \| `(/[^`]*)` \|$", rules))
    status_of = {row["url"]: row["status"] for row in new}
    hop = {row["url"]: row["redirect_to"] for row in new if row["status"] == "301"}
    sku_at = {row["sku"]: row["url"] for row in new if row["sku"]}
    old_at = {row["url"]: row for row in old}

    def land(address):
        return hop.get(address, address)

    def row_for(item):
        url = item["url"]
        if "?" in url:
            return None
        if item["status"] == "404" and item["backlinks"] == "0":
            return None
        if status_of.get(url) == "200":
            return None
        if url.split("/")[1] == "wholesale":
            return ("410", "")
        if item["status"] == "301":
            return row_for(old_at[item["redirect_target"]])
        if url.startswith("/products/"):
            if item["sku"] in sku_at:
                return ("301", land(sku_at[item["sku"]]))
            if (item["inlinks"], item["backlinks"], item["sessions_90d"]) == ("0", "0", "0"):
                return ("410", "")
            return ("301", land(table["/collections/" + item["category"]]))
        if url in table:
            return ("301", land(table[url]))
        if url.startswith("/blogs/kitchen-notes/"):
            slug = url.split("/")[-1]
            if re.match(r"\d\d\d\d-\d\d-", slug):
                slug = slug[8:]
            address = "/journal/" + slug
            return ("301", land(address if address in status_of else "/journal"))
        return ("410", "")

    rows = {item["url"]: row_for(item) for item in old}
    return old, new, table, rows


def _redirect_reply(rows: dict, answers: list | None = None) -> str:
    listed = [[url, status, target] for url, value in sorted(rows.items()) if value for status, target in [value]]
    if answers is None:
        answers = [sum(1 for _u, s, _t in listed if s == "301"), sum(1 for _u, s, _t in listed if s == "410"),
                   sum(1 for value in rows.values() if value is None)]
        old = {row["url"]: row for row in _table(REDIRECT_DIR + "old_site_urls.csv")}
        answers.append(sum(int(old[u]["backlinks"]) for u, s, _t in listed if s == "410"))
    return ("Redirect map for the Bramblewood Kitchen migration.\n\n"
            + _csv_block("redirects.csv", ["old_url", "status", "target"], listed)
            + "\n" + _answer_block(answers))


def test_redirect_oracle_matches_the_task_file_and_an_independent_recomputation():
    task = _task("seo-redirect-map")
    old, new, table, rows = _redirect_oracle()
    ref = task_facts_seo.redirect_oracle()
    assert {url: (item["status"], item.get("target", "")) if item["row"] else None
            for url, item in ref["decisions"].items()} == rows
    redirects = {url: value[1] for url, value in rows.items() if value and value[0] == "301"}
    gone = sorted(url for url, value in rows.items() if value and value[0] == "410")
    no_row = sorted(url for url, value in rows.items() if value is None)
    backlinks = {row["url"]: int(row["backlinks"]) for row in old}
    answers = [len(redirects), len(gone), len(no_row), sum(backlinks[url] for url in gone)]
    assert answers == [170, 16, 28, 28] == list(ref["answers"].values())
    by_id = _by_id(task)
    assert [by_id[name]["programmatic"]["near"] for name in ("q1_redirects", "q2_gone", "q3_no_row", "q4_gone_backlinks")] == answers
    # Every 301 lands on a live page of the new site, and none on an old URL that redirects.
    live = {row["url"] for row in new if row["status"] == "200"}
    assert set(redirects.values()) <= live
    assert not set(redirects.values()) & {url for url, value in rows.items() if value}
    # The counts the checks quote are the oracle's.
    assert len(old) == 214 and "(186 of the 214)" in by_id["every_row_accounted"]["check"]
    assert f"None of the {len(no_row)} old URLs" in by_id["no_row_urls_left_out"]["check"]
    assert f"Each of the {len(gone)} old URLs" in by_id["gone_urls_right"]["check"]
    quoted = {"product": "products_matched_by_sku", "retired": "retired_products_to_category", "renamed": "renames_applied",
              "journal": "journal_slugs_right", "old_redirect": "old_redirects_flattened",
              "new_site_redirect": "no_chains_on_the_new_site"}
    assert sum(len(urls) for urls in ref["buckets"].values()) == len(redirects)  # each 301 in exactly one bucket
    for bucket, criterion_id in quoted.items():
        assert f"Each of the {len(ref['buckets'][bucket])} " in by_id[criterion_id]["check"], bucket
    assert sum("programmatic" in c for c in by_id.values()) == len(by_id) == 15


def test_redirect_traps_are_in_the_data():
    old, new, table, rows = _redirect_oracle()
    old_at = {row["url"]: row for row in old}
    new_by_slug = collections.defaultdict(list)
    for row in new:
        new_by_slug[row["url"].rsplit("/", 1)[1]].append(row)
    # Retired products whose slug the new site gave a successor with another SKU.
    reused = [row for row in old if row["url"].startswith("/products/") and row["status"] == "200"
              and row["sku"] not in {item["sku"] for item in new}
              and any(item["sku"] for item in new_by_slug[row["url"].rsplit("/", 1)[1]])]
    assert len(reused) == 5
    assert all(rows[row["url"]][1].count("/") == 2 for row in reused)  # a category, not the successor
    # Retired products with exactly one signal above zero still redirect; the silent ones are gone.
    retired = [row for row in old if row["url"].startswith("/products/") and row["status"] == "200"
               and row["sku"] not in {item["sku"] for item in new}]
    signals = collections.Counter(sum(row[key] != "0" for key in ("inlinks", "backlinks", "sessions_90d")) for row in retired)
    assert signals[0] == 6 and signals[1] == 3
    # Slugs with a number in front that is not a YYYY-MM- date keep it.
    for slug in ("10-knife-skills-every-cook-needs", "2024-gift-guide", "2025-kitchen-trends"):
        assert rows["/blogs/kitchen-notes/" + slug] == ("301", "/journal/" + slug)
    assert rows["/blogs/kitchen-notes/2023-11-holiday-baking-timeline"] == ("301", "/journal/holiday-baking-timeline")
    assert rows["/blogs/kitchen-notes/2021-06-summer-grilling-tools"] == ("301", "/journal")
    # The trade portal's old redirect is gone, not followed; a 404 with inlinks but no backlinks gets no row.
    assert old_at["/wholesale/login"]["status"] == "301" and rows["/wholesale/login"] == ("410", "")
    assert old_at["/products/knife-roll-canvas"]["inlinks"] != "0" and rows["/products/knife-roll-canvas"] is None
    # Parameter URLs get no row even with backlinks.
    assert int(old_at["/blogs/kitchen-notes/how-to-season-cast-iron?utm_source=pinterest"]["backlinks"]) > 10
    # The rename table points at addresses the new site redirects again.
    assert {address for address in table.values() if any(row["url"] == address and row["status"] == "301" for row in new)} == {
        "/shop/cast-iron", "/shop/food-storage", "/pages/visit-us"}


def test_redirect_reference_reply_passes_every_check_and_a_blank_reply_none():
    _old, _new, _table_rows, rows = _redirect_oracle()
    reference = _redirect_reply(rows)
    assert _all_pass(_results("seo-redirect-map", reference)), {
        name: item["evidence"] for name, item in _results("seo-redirect-map", reference).items() if not item["pass"]}
    assert not any(item["pass"] for item in _results("seo-redirect-map", "").values())
    # Written with full URLs, as a Markdown table, or with a trailing slash: read the same.
    domain = "https://www.bramblewoodkitchen.example"
    full = re.sub(r"(?m)^(/[^,\n]*),(\d{3}),(/[^,\n]*)?$",
                  lambda m: f"{domain}{m.group(1)},{m.group(2)},{domain + m.group(3) if m.group(3) else ''}", reference)
    assert full != reference and _all_pass(_results("seo-redirect-map", full))
    lines = reference.split("```csv\n")[1].split("\n```")[0].splitlines()
    markdown = "| " + " | ".join(lines[0].split(",")) + " |\n|---|---|---|\n" + "\n".join(
        "| " + " | ".join(line.split(",")) + " |" for line in lines[1:])
    as_table = reference.split("```csv\n")[0] + markdown + "\n\n" + reference.split("\n```\n")[1]
    assert _all_pass(_results("seo-redirect-map", as_table))


def _with(rows: dict, changes: dict) -> dict:
    out = dict(rows)
    out.update(changes)
    return out


def test_each_careless_reading_scores_zero_on_its_own_check():
    old, new, table, rows = _redirect_oracle()
    old_at = {row["url"]: row for row in old}
    new_by_slug = {row["url"].rsplit("/", 1)[1]: row["url"] for row in new}
    hop = {row["url"]: row["redirect_to"] for row in new if row["status"] == "301"}
    ref = task_facts_seo.redirect_oracle()

    def zeroed(variant: dict, answers=None) -> set[str]:
        return _zeroed(_results("seo-redirect-map", _redirect_reply(variant, answers)))

    # Matching products by slug: the successor that took a retired product's slug.
    by_slug = {url: ("301", hop.get(new_by_slug[url.rsplit("/", 1)[1]], new_by_slug[url.rsplit("/", 1)[1]]))
               for url in ref["buckets"]["retired"] if url.rsplit("/", 1)[1] in new_by_slug}
    assert len(by_slug) == 4 and "retired_products_to_category" in zeroed(_with(rows, by_slug))
    # Stopping at the address a rule gives when the new site redirects it again.
    unfollowed = {}
    for url in ref["buckets"]["new_site_redirect"]:
        target = rows[url][1]
        unfollowed[url] = ("301", next(source for source, end in hop.items() if end == target and (
            source in table.values() or source.startswith(("/shop/", "/journal/")))))
    assert "no_chains_on_the_new_site" in zeroed(_with(rows, unfollowed))
    # Pointing an old redirect at the old address it pointed to.
    stale = {url: ("301", old_at[url]["redirect_target"]) for url in ref["buckets"]["old_redirect"]}
    assert "old_redirects_flattened" in zeroed(_with(rows, stale))
    # Redirecting parameter URLs to the page without the query string, or every URL to itself.
    stripped = {row["url"]: ("301", rows.get(row["url"].split("?")[0]) and rows[row["url"].split("?")[0]][1]
                             or row["url"].split("?")[0]) for row in old if "?" in row["url"]}
    assert "no_row_urls_left_out" in zeroed(_with(rows, stripped))
    unchanged = {url: ("301", url) for url, value in rows.items() if value is None and "?" not in url
                 and old_at[url]["status"] == "200"}
    assert len(unchanged) == 10 and "no_row_urls_left_out" in zeroed(_with(rows, unchanged))
    # Sending every retired product to its category, or the trade portal to the home page.
    silent = {url: ("301", table["/collections/" + old_at[url]["category"]]) for url in ref["gone"]
              if url.startswith("/products/")}
    assert len(silent) == 6 and {"gone_urls_right", "q2_gone"} <= zeroed(_with(rows, silent))
    portal = {url: ("301", "/") for url in ref["gone"] if url.startswith("/wholesale")}
    assert {"gone_urls_right", "q2_gone", "q4_gone_backlinks"} <= zeroed(_with(rows, portal))
    # Stripping any number from the front of a slug, and mapping every post to /journal/<slug>.
    numbered = {url: ("301", "/journal/" + re.sub(r"^\d+-", "", url.rsplit("/", 1)[1])) for url in ref["buckets"]["journal"]
                if re.match(r"\d+-", url.rsplit("/", 1)[1]) and not re.match(r"\d{4}-\d{2}-", url.rsplit("/", 1)[1])}
    assert len(numbered) == 3 and "journal_slugs_right" in zeroed(_with(rows, numbered))
    blind = {url: ("301", "/journal/" + re.sub(r"^\d{4}-\d{2}-", "", url.rsplit("/", 1)[1]))
             for url in ref["buckets"]["journal"] if rows[url][1] == "/journal"}
    assert len(blind) >= 3 and "journal_slugs_right" in zeroed(_with(rows, blind))
    # Reading the rename table by pattern instead: /collections/<slug> to /shop/<slug>.
    patterned = {url: ("301", "/shop/" + url.rsplit("/", 1)[1]) for url in ref["buckets"]["renamed"]
                 if url.startswith("/collections/") and "/shop/" + url.rsplit("/", 1)[1] != rows[url][1]}
    assert len(patterned) >= 4 and "renames_applied" in zeroed(_with(rows, patterned))
    # Leaving out the URLs that already redirect, or dead pages that still have backlinks.
    dropped = {url: None for url in ref["buckets"]["old_redirect"]}
    assert {"every_row_accounted", "old_redirects_flattened"} <= zeroed(_with(rows, dropped))


# ------------------------------------------------------------------ seo-titles-meta

META_SUFFIX = {"category": " | Shop Quillon Pets", "product": " | Quillon Pets", "guide": " | Quillon Pets Guides"}


def _meta_oracle():
    """Each indexed page's target keyword, recomputed from the inventory."""
    rows = _table("seo-titles-meta/page_inventory.csv")
    indexed = [row for row in rows if row["index"] == "index"]
    rank = {"category": 0, "product": 1, "guide": 2}
    targets, gave_up = {}, {}
    for keyword in {row["primary_keyword"] for row in indexed}:
        group = sorted((row for row in indexed if row["primary_keyword"] == keyword),
                       key=lambda row: (-int(row["clicks_28d"]), rank[row["page_type"]], row["page_id"]))
        targets[group[0]["page_id"]] = keyword
        for row in group[1:]:
            targets[row["page_id"]] = row["secondary_keyword"]
            gave_up[row["page_id"]] = keyword
    return rows, {row["page_id"]: row for row in indexed}, targets, gave_up


def _meta_row(row: dict, target: str, keeps: bool, price=True) -> list[str]:
    title = target[:1].upper() + target[1:] + META_SUFFIX[row["page_type"]]
    extra = f" and {row['secondary_keyword']}" if keeps else ""
    if row["page_type"] == "product":
        shown = f" Now ${row['price']}." if price and row["in_stock"] == "yes" else ""
        text = f"{target[:1].upper() + target[1:]}{extra} from Quillon Pet Supply, with {row['attributes'].split(';')[0]}.{shown}"
    elif row["page_type"] == "category":
        text = f"Browse {row['product_count']} {target}{extra} at Quillon Pet Supply, each one picked by our team."
    else:
        text = f"Our guide to {target}{extra}, with practical steps for pet owners: {row['name'].lower()}."
    for pad in (" Shop with care at Quillon.", " Delivered to your door.", " Read more online."):
        if len(text) < 100:
            text += pad
    return [row["page_id"], title, text]


def _meta_reply(rows: list[list[str]], answers: list) -> str:
    return "Titles and meta descriptions.\n\n" + _csv_block("titles_meta.csv", ["page_id", "title", "meta_description"], rows) + (
        "\n" + _answer_block(answers))


def test_titles_meta_oracle_matches_the_task_file_and_an_independent_recomputation():
    task = _task("seo-titles-meta")
    rows, indexed, targets, gave_up = _meta_oracle()
    ref = task_facts_seo.meta_oracle()
    assert {page_id: page["target"] for page_id, page in ref["pages"].items()} == targets
    assert ref["conceded"] == gave_up
    priced = [page_id for page_id, row in indexed.items() if row["page_type"] == "product" and row["in_stock"] == "yes"]
    answers = [len(indexed), len(gave_up), len(priced)]
    assert answers == [41, 6, 13] == list(ref["answers"].values())
    by_id = _by_id(task)
    assert [by_id[name]["programmatic"]["near"] for name in ("q1_rows", "q2_conceded", "q3_priced")] == answers
    assert f"Each of the {len(indexed)} indexed pages" in by_id["every_page_once"]["check"]
    noindex = [row for row in rows if row["index"] == "noindex"]
    assert f"None of the {len(noindex)} noindex pages" in by_id["noindex_left_out"]["check"]
    assert f"None of the {len(gave_up)} pages" in by_id["keyword_given_up"]["check"]
    assert f"Each of the {len(priced)} in-stock" in by_id["price_only_in_stock"]["check"]
    # The rules the candidate reads state the constants the checker applies.
    rules = (FIXTURES / "seo-titles-meta/title_rules.md").read_text()
    assert all(f"`{suffix}`" in rules for suffix in META_SUFFIX.values()) and META_SUFFIX == task_facts_seo.META_SUFFIXES
    assert "At most 60 characters" in rules and "100 to 155 characters" in rules
    assert "this order: category, product, guide" in rules
    # Every target keyword fits with its suffix; the tightest leaves one character.
    room = {page_id: 60 - len(keyword) - len(META_SUFFIX[indexed[page_id]["page_type"]]) for page_id, keyword in targets.items()}
    assert min(room.values()) == 1
    assert sum("programmatic" in c for c in by_id.values()) == len(by_id) == 16


def test_titles_meta_traps_are_in_the_data():
    rows, indexed, targets, gave_up = _meta_oracle()
    by_id = {row["page_id"]: row for row in rows}
    # A guide out-clicks the category that shares its keyword; a tie goes to the category, then the lower id.
    assert (int(by_id["G-201"]["clicks_28d"]) > int(by_id["C-02"]["clicks_28d"])) and "C-02" in gave_up
    assert by_id["C-03"]["clicks_28d"] == by_id["P-107"]["clicks_28d"] and "P-107" in gave_up
    assert by_id["P-110"]["clicks_28d"] == by_id["P-113"]["clicks_28d"] and "P-113" in gave_up
    assert {"C-05", "G-202"} <= set(gave_up) and "P-116" not in gave_up        # three pages, one keeps
    # A noindex page with more clicks takes no part: the indexed page keeps the keyword.
    assert int(by_id["G-209"]["clicks_28d"]) > int(by_id["P-122"]["clicks_28d"]) and targets["P-122"] == "catnip toys"
    # "dog bed" and "dog beds" are different keywords.
    assert targets["P-101"] == "dog bed" and targets["C-01"] == "dog beds"
    # Out-of-stock products carry a price in the inventory that must not be shown.
    assert sum(1 for row in indexed.values() if row["in_stock"] == "no" and row["price"]) == 7


def _meta_reference_rows(**overrides) -> list[list[str]]:
    _rows_all, indexed, targets, gave_up = _meta_oracle()
    return [_meta_row(row, overrides.get(page_id, targets[page_id]), page_id not in gave_up)
            for page_id, row in sorted(indexed.items())]


def test_titles_meta_reference_reply_passes_every_check_and_a_blank_reply_none():
    rows = _meta_reference_rows()
    assert all(len(title) <= 60 and 100 <= len(meta) <= 155 for _id, title, meta in rows)
    reference = _meta_reply(rows, [41, 6, 13])
    results = _results("seo-titles-meta", reference)
    assert _all_pass(results), {name: item["evidence"] for name, item in results.items() if not item["pass"]}
    assert not any(item["pass"] for item in _results("seo-titles-meta", "").values())
    # Capital letters and a hyphen for a space do not matter; a plural is another keyword.
    hyphened = reference.replace("No pull harness for dogs", "No-Pull Harness for Dogs")
    assert hyphened != reference and _all_pass(_results("seo-titles-meta", hyphened))
    assert not task_facts_seo._contains("Orthopedic dog beds for every size", "dog bed")
    assert task_facts_seo._contains("CloudRest dog-bed, washable", "dog bed")


def test_titles_meta_careless_readings_score_zero_on_their_checks():
    raw, indexed, targets, gave_up = _meta_oracle()
    by_id = {row["page_id"]: row for row in raw}

    def zeroed(rows, answers) -> set[str]:
        return _zeroed(_results("seo-titles-meta", _meta_reply(rows, answers)))

    reference = _meta_reference_rows()
    # Writing every page in the inventory, noindex pages too.
    every = reference + [_meta_row(row, row["primary_keyword"], True) for row in raw if row["index"] == "noindex"]
    assert {"noindex_left_out", "q1_rows"} <= zeroed(every, [46, 6, 13])
    # Letting every page keep its primary keyword.
    kept = [_meta_row(row, row["primary_keyword"], True) for _id, row in sorted(indexed.items())]
    assert {"keyword_given_up", "title_keyword", "q2_conceded"} <= zeroed(kept, [41, 0, 13])
    # Giving a shared keyword to the category whatever the clicks.
    rank = {"category": 0, "product": 1, "guide": 2}
    category_first = {}
    for keyword in {row["primary_keyword"] for row in indexed.values()}:
        group = sorted((row for row in indexed.values() if row["primary_keyword"] == keyword),
                       key=lambda row: (rank[row["page_type"]], row["page_id"]))
        category_first.update({row["page_id"]: row["secondary_keyword"] for row in group[1:]})
        category_first[group[0]["page_id"]] = keyword
    careless = [_meta_row(row, category_first[page_id], category_first[page_id] == row["primary_keyword"])
                for page_id, row in sorted(indexed.items())]
    assert {"keyword_given_up", "title_keyword"} <= zeroed(careless, [41, 6, 13])
    # Counting the noindex page in the keyword rule, or "dog bed" as "dog beds": one more page gives up.
    assert "q2_conceded" in zeroed(_meta_reference_rows(**{"P-122": by_id["P-122"]["secondary_keyword"]}), [41, 7, 13])
    # Showing the price of an out-of-stock product, or a price written another way.
    out_of_stock = [row for row in reference]
    for index, (page_id, title, meta) in enumerate(out_of_stock):
        row = indexed[page_id]
        if row["page_type"] == "product" and row["in_stock"] == "no":
            out_of_stock[index] = [page_id, title, meta[:140] + f" ${row['price']}."]
    assert {"price_only_in_stock", "q3_priced"} <= zeroed(out_of_stock, [41, 6, 20])
    rounded = [[page_id, title, meta.replace(".00.", ".")] for page_id, title, meta in reference]
    assert "price_only_in_stock" in zeroed(rounded, [41, 6, 13])


# --------------------------------------------------------------------- blog-post

BLOG_POST = """\
SEO title: Why Is My Furnace Making Noise? A Homeowner's Guide
Meta description: Whistling, rattling, banging or grinding? Learn which furnace noises you can safely watch and which need a licensed Brightline technician.

# Why Is My Furnace Making Noise?

A furnace is never silent. You hear the burner light, the blower start and the air move through the ducts, and most of the time those sounds fade into the background of a North Valley winter. When a new sound appears, or a familiar one gets louder, it is worth paying attention. Some noises point to something you can check yourself in a few calm minutes. Others are a sign that a licensed technician should look at the system, and a few mean you should leave the house and call for help from outside.

This guide walks through the noises Brightline Heating hears about most often, what you can safely observe on your own, and when it is time to stop and call a professional. In 2025 Brightline answered 1,412 furnace calls about a noise, so you are far from alone if your furnace has started to sound different.

## What to check before you worry

Before you try to name a noise, take a few simple, safe observations. None of them involves opening the furnace or touching any part inside it.

- **Look at the thermostat.** Make sure it is set to heat and that the set point is above the temperature of the room. A thermostat set too low can make the system start and stop in a way that sounds odd.
- **Check the air filter.** A 1-inch filter is due for replacement every 90 days. If yours looks grey and clogged, airflow through the system drops, and that alone changes how the furnace sounds.
- **Walk the house and look at the registers.** Supply registers should be open and not blocked by furniture, rugs or curtains. A room full of closed registers forces air through a smaller path.
- **Give the furnace room to breathe.** Keep 3 feet clear around the furnace. Boxes, laundry and storage pushed against the cabinet are a safety problem as well as an airflow one.
- **Notice when the noise happens.** Does it start when the burner lights, when the blower comes on, or does it run the whole time the furnace is working? That one detail helps a technician more than any description of the sound itself.

Write down what you notice. A short note on when the sound starts and how long it lasts is the most useful thing you can bring to a service visit.

## Whistling and howling: usually airflow

Whistling or howling was the most common complaint in Brightline's 2025 service calls, at 31% of noise calls. It is usually about air rather than anything mechanical. A clogged filter, closed registers or a blocked return grille all make the blower work harder to move the same air, and the air whistles as it squeezes through.

This is the noise you are most likely to be able to influence yourself. Replace an overdue filter, open the registers and clear anything blocking the returns, then listen again over the next day or two. If the whistle is gone, airflow was the cause. If it stays, or it comes with weak airflow from the vents, a technician should check the ducts and the blower.

## Rattling: something is loose

Rattling made up 22% of the noise calls. It is often a loose panel or a loose section of duct that vibrates when the blower runs. You can safely look for anything obvious from the outside: a register cover that buzzes, something stored on top of the furnace, or a duct you can see that shakes when the air comes on.

Do not take panels off the furnace to look for the source. Panels are there to keep you away from electrical and gas parts. If the rattle is coming from the cabinet itself, or it gets worse over time, book an inspection so a technician can secure what is loose without putting you near those parts.

## Banging or a boom when the burner lights

A bang or a small boom right as the burner lights accounted for 18% of the calls. This one deserves more caution than a whistle or a rattle. A bang at ignition can mean the burner is not lighting the way it should, and that is a gas-side problem, not something to investigate yourself.

Note when it happens and how often, and leave the furnace alone. Banging when the burner lights is on the list of signs that need a licensed technician, so this is the moment to call a professional rather than wait to see whether it settles down.

## Squealing, clicking and grinding

**Squealing or screeching** was 14% of the calls and often comes from the blower. You may hear it when the fan starts or while it runs. It is not an emergency on its own, but it rarely fixes itself, and a blower that keeps working under strain can fail.

**Clicking that repeats without the burner lighting** was 9% of the calls. A single click as the system starts is normal. Clicking that goes on and on while the burner never lights is not, and repeated clicking without ignition needs a licensed technician.

**Grinding or scraping** was the least common at 6%, but it is one of the most important to act on. Grinding usually means metal is wearing against metal somewhere in a moving part. Turn the system off at the thermostat and book an inspection.

If you want a quick reference for other heating questions, our guide to the [furnace filter guide](/blog/furnace-filter-guide) covers filters in detail, [furnace blowing cold air](/blog/why-is-my-furnace-blowing-cold-air) explains a different common complaint, and [thermostat troubleshooting](/blog/thermostat-troubleshooting) helps when the problem starts at the wall.

## When to call a professional

Some sounds are worth watching for a day or two. Others are not. Call a licensed technician when you notice any of these:

- Banging or a boom when the burner lights.
- Grinding or scraping from the furnace.
- Clicking that repeats without the burner lighting.
- An electrical burning smell.
- A furnace that keeps shutting down on its own. If that is what you are seeing, our article on why a [furnace keeps turning off](/blog/furnace-keeps-turning-off) explains what a technician will look for.

Whatever the noise, never open, bypass or repair gas or electrical parts yourself. That includes removing panels to get a better look, resetting parts inside the cabinet, or taping over anything that seems loose. Brightline's [furnace repair](/services/furnace-repair) team can diagnose the source safely. Booking times vary, so book as soon as you notice one of the signs above rather than waiting for the noise to get worse.

## When it is an emergency

If you smell gas, do not stop to listen to the furnace. Leave the building right away. Do not use light switches, phones or anything with a flame on your way out. Once you are outside and at a safe distance, call the gas emergency line. Stay out until you are told it is safe to go back in.

A gas smell is different from the slightly dusty smell some furnaces give off the first time they run in the autumn. If you are ever unsure which one you are smelling, treat it as gas and leave.

## A simple way to think about furnace noises

It can help to sort what you hear into three groups:

1. **Safe to observe and adjust:** whistling or howling that may be airflow. Check the filter, the registers and the space around the furnace, then listen again.
2. **Book an inspection:** rattling from the cabinet, squealing from the blower, and anything that keeps coming back after you have checked the basics.
3. **Call a professional now, or leave:** banging when the burner lights, grinding, repeated clicking without ignition, an electrical burning smell, a furnace that keeps shutting down, and above all a gas smell, which means leaving the house first.

Most furnace noises are a message rather than a crisis. Listening carefully, noting when the sound happens and keeping your hands off the inside of the furnace will get you to the right fix faster and keep your household safe.

## Book a furnace diagnostic

If your furnace is making a noise you cannot explain, or one of the signs above sounds familiar, a Brightline technician can find the cause. Brightline serves homeowners across North Valley, and a diagnostic visit means someone with the right training looks at the system before any repair is discussed.

[Book a $95 furnace diagnostic visit](/book/furnace-diagnostic)
"""


def _blog_oracle():
    """The figures and the links the rules give, recomputed from the two fixtures."""
    sources = (FIXTURES / "blog-post/sources.md").read_text()
    sections = re.split(r"(?m)^## ", sources)[1:]
    by_date = sorted((re.search(r"published (\d{4}-\d{2}-\d{2})", section).group(1), section) for section in sections)
    prices = [(date, re.findall(r"Furnace diagnostic visit: \$(\d+)", section)) for date, section in by_date]
    prices = [(date, found[0]) for date, found in prices if found]
    site = _table("blog-post/site_map.csv")
    live = [row for row in site if "furnace" in row["tags"].split(";") and row["status"] == "200" and row["noindex"] == "no"]
    live.sort(key=lambda row: row["url"])
    live.sort(key=lambda row: int(row["sessions_28d"]), reverse=True)
    return sources, prices, site, {row["url"]: row["primary_keyword"] for row in live[:5]}


def test_blog_post_oracle_matches_an_independent_recomputation():
    task = _task("blog-post")
    sources, prices, site, links = _blog_oracle()
    ref = task_facts_seo.blog_oracle()
    # The later source is first in the file, and its price is the current one.
    assert prices == [("2025-02-10", "89"), ("2026-01-05", "95")]
    assert sources.index("$95") < sources.index("$89")
    assert ref["price"] == 95.0 and ref["superseded_figures"] == [("$", 89.0)]
    percentages = sorted(float(value) for value in re.findall(r": (\d+)%\.", sources))
    assert percentages == [6.0, 9.0, 14.0, 18.0, 22.0, 31.0] and sum(percentages) == 100
    assert sorted(tuple(item) for item in ref["current_figures"]) == sorted(
        [("$", 95.0), ("calls", 1412.0), ("day", 90.0), ("foot", 3.0), ("inch", 1.0)] + [("%", value) for value in percentages])
    assert ref["links"] == links
    by_id = _by_id(task)
    assert all(url in by_id["links_chosen"]["check"] for url in links)
    # The fifth place is a tie the URL order breaks, and the page that loses it comes first in the file.
    sessions = {row["url"]: int(row["sessions_28d"]) for row in site}
    assert sessions["/blog/furnace-keeps-turning-off"] == sessions["/services/furnace-maintenance"]
    urls = [row["url"] for row in site]
    assert urls.index("/services/furnace-maintenance") < urls.index("/blog/furnace-keeps-turning-off")
    # Pages with more sessions that the rule leaves out: a redirect, a noindex page, a furnace URL
    # not tagged furnace, and another noise.
    for url in ("/blog/furnace-short-cycling", "/blog/carbon-monoxide-safety", "/blog/heat-pump-vs-furnace", "/blog/ac-making-noise"):
        assert sessions[url] > min(sessions[link] for link in links) and url not in links
    # The prompt no longer gives the price, and the brand fixture that did is not supplied.
    assert "$" not in task["prompt"] and "95" not in task["prompt"]
    assert task["fixtures"] == ["eval_runner/fixtures/blog-post/sources.md", "eval_runner/fixtures/blog-post/site_map.csv"]
    assert (task["prompt_version"], task["rubric_version"]) == (3, 4) and "rubric_compatible_prompts" not in task
    code = sum("programmatic" in c for c in by_id.values())
    assert (code, len(by_id)) == (10, 13)


def test_blog_post_reference_passes_every_check_and_a_blank_reply_none():
    results = _results("blog-post", BLOG_POST)
    assert _all_pass(results), {name: item["evidence"] for name, item in results.items() if not item["pass"]}
    assert len(BLOG_POST.split()) >= 1200
    assert not any(item["pass"] for item in _results("blog-post", "").values())
    # Links written as HTML or as full URLs on the brand's domain read the same.
    as_html = BLOG_POST.replace("[furnace repair](/services/furnace-repair)",
                                '<a href="https://www.brightlineheating.example/services/furnace-repair/">Furnace Repair</a>')
    assert as_html != BLOG_POST and _all_pass(_results("blog-post", as_html))


def test_blog_post_careless_readings_score_zero_on_their_checks():
    def failed(text: str) -> set[str]:
        return _failed(_results("blog-post", text))

    def zeroed(text: str) -> set[str]:
        return _zeroed(_results("blog-post", text))

    # The price from the older menu, which comes later in the file.
    old_price = BLOG_POST.replace("$95", "$89")
    assert {"price_current", "booking_cta"} <= failed(old_price)
    # A figure the sources do not give: a sum of two shares and a filter interval in months.
    invented = BLOG_POST.replace("at 31% of noise calls", "at 31% of noise calls (with rattling, 53%)").replace(
        "every 90 days", "every 3 months")
    assert "figures_from_sources" in zeroed(invented)
    # Links picked by a furnace URL, or by sessions without the live test, or a tie broken by file order.
    by_url = BLOG_POST.replace("(/blog/thermostat-troubleshooting)", "(/blog/heat-pump-vs-furnace)")
    assert "links_chosen" in zeroed(by_url)
    redirect = BLOG_POST.replace("(/blog/furnace-keeps-turning-off)", "(/blog/furnace-short-cycling)")
    assert "links_chosen" in zeroed(redirect)
    tie = BLOG_POST.replace("[furnace keeps turning off](/blog/furnace-keeps-turning-off)",
                            "[furnace maintenance](/services/furnace-maintenance)")
    assert "links_chosen" in zeroed(tie)
    # The page title as the link text, instead of the keyword.
    titles = BLOG_POST
    for keyword, title in (("furnace filter guide", "The Furnace Filter Guide"),
                           ("furnace blowing cold air", "Why Is My Furnace Blowing Cold Air?"),
                           ("thermostat troubleshooting", "Thermostat Troubleshooting Tips")):
        titles = titles.replace(f"[{keyword}]", f"[{title}]")
    assert "anchors_exact" in zeroed(titles)
    # A link to another website, and a post with no call to action link.
    assert "links_chosen" in failed(BLOG_POST.replace("[furnace repair](/services/furnace-repair)",
                                                      "[furnace repair](https://example.org/furnaces)"))
    assert "booking_cta" in failed(BLOG_POST.replace("(/book/furnace-diagnostic)", "(/contact)"))


def test_the_figures_a_post_states_are_read_as_the_prompt_defines_them():
    read = task_facts_seo.figures
    assert read("Brightline answered 1,412 furnace calls.") == {("calls", 1412.0)}
    assert read("In Brightline's 2025 service calls, 31% were whistling.") == {("%", 31.0)}   # a year is not a count
    assert read("A 1-inch filter every 90 days; keep 3 feet clear.") == {("inch", 1.0), ("day", 90.0), ("foot", 3.0)}
    assert read("every 3 months, or 31 percent, for $95.00") == {("month", 3.0), ("%", 31.0), ("$", 95.0)}
    # What the prompt does not call a figure: a temperature, a phone number, a count of noises, a list number.
    assert read("Set it to 68°F, call 911, and listen for these 6 noises.\n1. Whistling") == set()
    # A singular "call" after a number is not a number of calls.
    assert read("Raise it 2 degrees and call a technician.") == set()
