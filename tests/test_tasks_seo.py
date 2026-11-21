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
    for task_id in ("seo-redirect-map",):
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
