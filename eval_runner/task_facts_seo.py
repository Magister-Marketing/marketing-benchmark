"""Measured facts for the SEO tasks of the 35-task board.

`facts_for(task, response_text)` is the one entry point: `bench.measured_facts`
calls it for every task, and it returns facts only for the tasks below.

Each task's oracle computes the answer from the fixture text alone (the files
`scripts/gen_tasks_seo.py` writes), never from the response, and the facts
are counts of what a reply got wrong against it. Every count measures work
against the oracle, so a file left out is that many errors, never zero: an
empty reply earns nothing. tests/test_tasks_seo.py computes every answer again
with separate code.

Nothing here judges prose. A reply is untrusted text; it is only parsed.
"""
from __future__ import annotations

import csv
import io
import re
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "eval_runner" / "fixtures"


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _markdown_pairs(text: str) -> list[tuple[str, str]]:
    """The two-column rows of the Markdown tables in a document, backticks removed."""
    pairs = []
    for line in text.splitlines():
        cells = [cell.strip().strip("`").strip() for cell in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and len(cells) == 2 and not set(cells[0]) <= set("-: "):
            pairs.append((cells[0], cells[1]))
    return pairs


# ------------------------------------------------------------------ seo-redirect-map

REDIRECT_TASK = "seo-redirect-map"
REDIRECT_FILE = "redirects.csv"
REDIRECT_DOMAIN = "www.bramblewoodkitchen.example"
REDIRECT_DATED_SLUG = re.compile(r"^\d{4}-\d{2}-")
# What decides a 301's target, for the check that counts its errors. A row
# belongs to the first bucket that fits: an old redirect, then a target the new
# site's own list redirects, then the rule that gave it.
REDIRECT_BUCKETS = ("old_redirect", "new_site_redirect", "product", "retired", "renamed", "journal")


def redirect_reference(old_csv: str, new_csv: str, rules_md: str) -> dict:
    """Every old URL's row (or none) under migration_rules.md, from the three files' text."""
    old = _rows(old_csv)
    new = {row["url"]: row for row in _rows(new_csv)}
    by_old = {row["url"]: row for row in old}
    sku_url = {row["sku"]: row["url"] for row in new.values() if row["sku"]}
    pairs = _markdown_pairs(rules_md)
    renames = {old_url: new_url for old_url, new_url in pairs if old_url.startswith("/")}

    def live(address: str) -> tuple[str, bool]:
        """The live target for an address a rule gives, and whether the new list redirected it."""
        row = new.get(address)
        if row is not None and row["status"] == "301":
            return row["redirect_to"], True
        return address, False

    def decide(row: dict, depth: int = 0) -> dict:
        url, status = row["url"], row["status"]
        if "?" in url:
            return {"row": False, "reason": "parameter"}
        if status == "404" and int(row["backlinks"]) == 0:
            return {"row": False, "reason": "dead_unlinked"}
        if url in new and new[url]["status"] == "200":
            return {"row": False, "reason": "unchanged"}
        if url == "/wholesale" or url.startswith("/wholesale/"):
            return {"row": True, "status": "410", "rule": "trade_portal"}
        if status == "301" and depth == 0:
            decided = dict(decide(by_old[row["redirect_target"]], depth + 1))
            decided["via"] = row["redirect_target"]
            if decided.get("status") == "301":
                decided["bucket"] = "old_redirect"
            return decided
        if url.startswith("/products/"):
            if row["sku"] in sku_url:
                return _target(sku_url[row["sku"]], "product")
            if int(row["inlinks"]) == int(row["backlinks"]) == int(row["sessions_90d"]) == 0:
                return {"row": True, "status": "410", "rule": "retired_silent"}
            return _target(renames[f"/collections/{row['category']}"], "retired")
        if url in renames:
            return _target(renames[url], "renamed")
        if url.startswith("/blogs/kitchen-notes/"):
            moved = "/journal/" + REDIRECT_DATED_SLUG.sub("", url.rsplit("/", 1)[1])
            return _target(moved if moved in new else "/journal", "journal")
        return {"row": True, "status": "410", "rule": "everything_else"}

    def _target(address: str, rule: str) -> dict:
        target, followed = live(address)
        return {"row": True, "status": "301", "target": target, "rule": rule,
                "bucket": "new_site_redirect" if followed else rule}

    decisions = {row["url"]: decide(row) for row in old}
    redirects = {url: item for url, item in decisions.items() if item["row"] and item["status"] == "301"}
    gone = {url: item for url, item in decisions.items() if item["row"] and item["status"] == "410"}
    no_row = {url: item for url, item in decisions.items() if not item["row"]}
    return {
        "decisions": decisions,
        "redirects": {url: item["target"] for url, item in redirects.items()},
        "buckets": {bucket: sorted(url for url, item in redirects.items() if item["bucket"] == bucket)
                    for bucket in REDIRECT_BUCKETS},
        "gone": sorted(gone),
        "no_row": sorted(no_row),
        "answers": {
            "q1_redirects": len(redirects),
            "q2_gone": len(gone),
            "q3_no_row": len(no_row),
            "q4_gone_backlinks": sum(int(by_old[url]["backlinks"]) for url in gone),
        },
        "live_urls": sorted(url for url, row in new.items() if row["status"] == "200"),
    }


@lru_cache(maxsize=1)
def redirect_oracle() -> dict:
    folder = "seo-redirect-map/"
    return redirect_reference(_fixture(folder + "old_site_urls.csv"), _fixture(folder + "new_site_urls.csv"),
                              _fixture(folder + "migration_rules.md"))


def _path(text: str, domain: str) -> str:
    """A URL cell as the path the files write: the site's own domain and a trailing slash dropped."""
    value = str(text or "").strip().strip("\"'`<>").strip()
    value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    if value.lower().startswith(domain):
        value = value[len(domain):] or "/"
    if len(value) > 1 and value.endswith("/") and "?" not in value:
        value = value[:-1]
    return value


def _status(text: str) -> str:
    match = re.match(r"\s*(\d{3})", str(text or ""))
    return match.group(1) if match else ""


def redirect_facts(response_text: str) -> dict:
    ref = redirect_oracle()
    found = common.tables(response_text, [REDIRECT_FILE])[REDIRECT_FILE]
    missing_file = found is None
    rows = []
    for row in found or []:
        old_url = _path(common.cell(row, "old_url", "old", "source", "from", "url"), REDIRECT_DOMAIN)
        if not old_url:
            continue
        rows.append((old_url, _status(common.cell(row, "status", "status_code", "type", "code")),
                     _path(common.cell(row, "target", "new_url", "destination", "to", "redirect_to"), REDIRECT_DOMAIN)))
    given: dict[str, tuple[str, str]] = {}
    for old_url, status, target in rows:
        given.setdefault(old_url, (status, target))
    export = set(ref["decisions"])
    wanted_rows = set(ref["redirects"]) | set(ref["gone"])
    listed = [old_url for old_url, _status_code, _target in rows]

    def redirect_errors(urls: list[str]) -> int:
        return sum(1 for url in urls if given.get(url) != ("301", ref["redirects"][url]))

    return {
        "seo_redirect_missing_file_count": int(missing_file),
        # Rows the rules give that are missing, rows for URLs not in the export, and an old URL listed twice.
        "seo_redirect_accounting_error_count": (
            len(wanted_rows - set(listed)) + len(set(listed) - export) + (len(listed) - len(set(listed)))),
        # URLs that must get no row: each has one, or the file the claim rests on is missing.
        "seo_redirect_no_row_error_count": (
            len(ref["no_row"]) if missing_file else sum(1 for url in ref["no_row"] if url in given)),
        "seo_redirect_gone_error_count": sum(1 for url in ref["gone"] if given.get(url, ("", ""))[0] != "410"),
        **{f"seo_redirect_{bucket}_error_count": redirect_errors(urls) for bucket, urls in ref["buckets"].items()},
    }


# ------------------------------------------------------------------ seo-titles-meta

META_TASK = "seo-titles-meta"
META_FILE = "titles_meta.csv"
META_BRAND = "Quillon"
# The suffix every title ends with, by page type, in the order a keyword tie is broken.
META_SUFFIXES = {
    "category": " | Shop Quillon Pets",
    "product": " | Quillon Pets",
    "guide": " | Quillon Pets Guides",
}
META_TITLE_MAX = 60
META_DESCRIPTION_RANGE = (100, 155)


def _phrase(text: object) -> str:
    """Lower case, a hyphen read as a space, one space between words."""
    return " " + re.sub(r"\s+", " ", str(text or "").lower().replace("-", " ")).strip() + " "


def _contains(text: object, keyword: object) -> bool:
    """Whether the keyword is in the text as whole words, capitals and hyphens aside."""
    wanted = _phrase(keyword).strip()
    return bool(wanted) and bool(re.search(r"(?<![a-z0-9])" + re.escape(wanted) + r"(?![a-z0-9])", _phrase(text)))


def _numeral(text: str, number: str) -> bool:
    """Whether the number is written in the text as a whole numeral."""
    return bool(re.search(r"(?<![\d.,$])" + re.escape(number) + r"(?![\d]|[.,]\d)", text))


def meta_reference(inventory_csv: str) -> dict:
    """The target keyword of every indexed page and what its title and description must carry."""
    rows = _rows(inventory_csv)
    indexed = [row for row in rows if row["index"] == "index"]
    order = list(META_SUFFIXES)
    groups: dict[str, list[dict]] = {}
    for row in indexed:
        groups.setdefault(_phrase(row["primary_keyword"]), []).append(row)
    pages, conceded = {}, {}
    for group in groups.values():
        keeper = min(group, key=lambda row: (-int(row["clicks_28d"]), order.index(row["page_type"]), row["page_id"]))
        for row in group:
            keeps = row is keeper
            if not keeps:
                conceded[row["page_id"]] = row["primary_keyword"]
            pages[row["page_id"]] = {
                "page_type": row["page_type"],
                "target": row["primary_keyword"] if keeps else row["secondary_keyword"],
                "also_in_description": [row["secondary_keyword"]] if keeps else [],
                "price": f"${row['price']}" if row["page_type"] == "product" and row["in_stock"] == "yes" else None,
                "own_price": row["price"],
                "attribute": row["attributes"].split(";")[0].strip() if row["page_type"] == "product" else None,
                "count": row["product_count"] if row["page_type"] == "category" else None,
            }
    return {
        "pages": pages,
        "conceded": conceded,
        "noindex": sorted(row["page_id"] for row in rows if row["index"] != "index"),
        "answers": {
            "q1_rows": len(pages),
            "q2_conceded": len(conceded),
            "q3_priced": sum(1 for page in pages.values() if page["price"]),
        },
    }


@lru_cache(maxsize=1)
def meta_oracle() -> dict:
    return meta_reference(_fixture("seo-titles-meta/page_inventory.csv"))


def meta_facts(response_text: str) -> dict:
    ref = meta_oracle()
    pages = ref["pages"]
    found = common.tables(response_text, [META_FILE])[META_FILE]
    missing_file = found is None
    rows = [(common.cell(row, "page_id", "id", "page").strip().strip("`*").upper(),
             common.cell(row, "title", "title_tag", "seo_title").strip(),
             common.cell(row, "meta_description", "meta", "description").strip())
            for row in found or []]
    rows = [row for row in rows if row[0]]
    given: dict[str, tuple[str, str]] = {}
    for page_id, title, description in rows:
        given.setdefault(page_id, (title, description))
    known = set(pages) | set(ref["noindex"])
    listed = [page_id for page_id, _title, _description in rows]

    def errors(test) -> int:
        """Pages of the oracle whose row is missing or fails the test."""
        return sum(1 for page_id, page in pages.items() if page_id not in given or not test(page, *given[page_id]))

    def suffix_right(page, title, _description):
        suffix = META_SUFFIXES[page["page_type"]]
        return title.endswith(suffix) and META_BRAND.lower() not in title[:-len(suffix)].lower()

    def price_right(page, title, description):
        if "$" in title:
            return False
        if page["price"]:
            return page["price"] in description
        return "$" not in description and not (page["own_price"] and _numeral(description, page["own_price"]))

    def facts_right(page, _title, description):
        if page["attribute"] is not None:
            return _contains(description, page["attribute"])
        if page["count"] is not None:
            return _numeral(description, page["count"])
        return True

    titles = [_phrase(title) for _page_id, title, _description in rows]
    descriptions = [_phrase(description) for _page_id, _title, description in rows]
    low, high = META_DESCRIPTION_RANGE
    return {
        "seo_meta_missing_file_count": int(missing_file),
        "seo_meta_accounting_error_count": (
            len(set(pages) - set(listed)) + len(set(listed) - known) + (len(listed) - len(set(listed)))),
        "seo_meta_noindex_error_count": (
            len(ref["noindex"]) if missing_file else sum(1 for page_id in ref["noindex"] if page_id in given)),
        "seo_meta_title_length_error_count": errors(lambda _p, title, _d: 0 < len(title) <= META_TITLE_MAX),
        "seo_meta_suffix_error_count": errors(suffix_right),
        "seo_meta_title_keyword_error_count": errors(lambda page, title, _d: _contains(title, page["target"])),
        "seo_meta_conceded_keyword_error_count": sum(
            1 for page_id, keyword in ref["conceded"].items()
            if page_id not in given or any(_contains(text, keyword) for text in given[page_id])),
        "seo_meta_description_length_error_count": errors(lambda _p, _t, description: low <= len(description) <= high),
        "seo_meta_description_keyword_error_count": errors(lambda page, _t, description: all(
            _contains(description, keyword) for keyword in [page["target"], *page["also_in_description"]])),
        "seo_meta_price_error_count": errors(price_right),
        "seo_meta_page_fact_error_count": errors(facts_right),
        "seo_meta_duplicate_count": (
            len(pages) if missing_file else
            (len(titles) - len(set(titles))) + (len(descriptions) - len(set(descriptions)))),
    }


# --------------------------------------------------------------------- blog-post

BLOG_TASK = "blog-post"
BLOG_BOOKING = "/book/furnace-diagnostic"
BLOG_LINKS = 5
BLOG_TITLE_PHRASE = "furnace making noise"
BLOG_TITLE_MAX, BLOG_DESCRIPTION_MAX = 60, 155
BLOG_MIN_WORDS_FOR_A_POST = 300
_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# What the prompt calls a figure: a price, a percentage, a number of calls, a span of time or distance.
_FIGURES = (
    ("$", re.compile(r"\$\s?(" + _NUMBER + r")")),
    ("%", re.compile(r"(?<![\d.,$])(" + _NUMBER + r")\s?(?:%|percent\b)", re.IGNORECASE)),
    ("calls", re.compile(r"(?<![\d.,$])(" + _NUMBER + r")(?:[ \t]+[a-z'-]+){0,3}?[ \t]+calls\b", re.IGNORECASE)),
    ("span", re.compile(r"(?<![\d.,$])(" + _NUMBER + r")[ \t-]?(second|minute|hour|day|week|month|year|inch|inche|foot|feet|ft|mile)s?\b",
                        re.IGNORECASE)),
)
_UNITS = {"inche": "inch", "feet": "foot", "ft": "foot"}


def figures(text: str) -> set[tuple[str, float]]:
    """The figures a text states, as (kind, value): ("$", 95.0), ("%", 31.0), ("day", 90.0).

    A year is not a count: "Brightline's 2025 service calls" states no number of calls.
    """
    found = set()
    for kind, pattern in _FIGURES:
        for match in pattern.finditer(text):
            value = float(match.group(1).replace(",", ""))
            if kind == "calls" and re.fullmatch(r"(?:19|20)\d\d", match.group(1)):
                continue
            if kind == "span":
                unit = match.group(2).lower()
                found.add((_UNITS.get(unit, unit), value))
            else:
                found.add((kind, value))
    return found


def blog_reference(sources_md: str, site_map_csv: str) -> dict:
    """The current and the superseded figures of sources.md, and the five pages the link rule picks."""
    dated: list[tuple[str, str, str]] = []   # (published, label, line)
    published = ""
    for line in sources_md.splitlines():
        heading = re.match(r"^## .*\(published (\d{4}-\d{2}-\d{2})\)", line)
        if heading:
            published = heading.group(1)
        elif line.startswith("- "):
            label = line[2:].split(": ", 1)[0].strip().lower() if ": " in line else line
            dated.append((published, label, line))
    latest: dict[str, str] = {}
    for when, label, _line in dated:
        latest[label] = max(latest.get(label, ""), when)
    current = set().union(*(figures(line) for when, label, line in dated if when == latest[label]))
    superseded = set().union(*(figures(line) for when, label, line in dated if when != latest[label])) - current
    pages = _rows(site_map_csv)
    live = [row for row in pages if "furnace" in row["tags"].split(";") and row["status"] == "200" and row["noindex"] == "no"]
    chosen = sorted(live, key=lambda row: (-int(row["sessions_28d"]), row["url"]))[:BLOG_LINKS]
    price = sorted(value for kind, value in current if kind == "$")
    return {
        "current_figures": sorted(current),
        "superseded_figures": sorted(superseded),
        "price": price[0] if len(price) == 1 else None,
        "links": {row["url"]: row["primary_keyword"] for row in chosen},
    }


@lru_cache(maxsize=1)
def blog_oracle() -> dict:
    return blog_reference(_fixture("blog-post/sources.md"), _fixture("blog-post/site_map.csv"))


_MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]\n]{1,300})\]\(\s*<?([^)\s>]{1,500})>?(?:\s+\"[^\"\n]*\")?\s*\)")
_HTML_LINK = re.compile(r"<a\s[^>]{0,500}?href=[\"']([^\"']{1,500})[\"'][^>]{0,500}>(.{0,300}?)</a>", re.IGNORECASE | re.DOTALL)


def _links(text: str) -> list[tuple[str, str]]:
    """(link text, target) for every Markdown or HTML link, images aside."""
    found = [(match.group(1), match.group(2)) for match in _MARKDOWN_LINK.finditer(text)]
    found += [(re.sub(r"<[^>]+>", "", match.group(2)), match.group(1)) for match in _HTML_LINK.finditer(text)]
    return found


def _site_path(target: str) -> str | None:
    """The path of a link on Brightline's own site, or None for any other site."""
    value = target.strip()
    if re.match(r"^(?:https?:)?//", value, re.IGNORECASE):
        host_and_path = re.sub(r"^(?:https?:)?//", "", value, flags=re.IGNORECASE)
        host, _, path = host_and_path.partition("/")
        if not re.fullmatch(r"(?:www\.)?brightlineheating\.[a-z.]+", host.lower()):
            return None
        value = "/" + path
    value = value.split("#", 1)[0]
    return value[:-1] if len(value) > 1 and value.endswith("/") else value


def _labelled(text: str, names: str) -> str | None:
    match = re.search(r"(?im)^[ \t>#*_-]*(?:" + names + r")[ \t*_]*[:：][ \t*_]*(.+?)[ \t]*$", text)
    return match.group(1).strip().strip("*_`\"'“”").strip() if match else None


def blog_facts(response_text: str) -> dict:
    ref = blog_oracle()
    text = response_text
    is_post = len(text.split()) >= BLOG_MIN_WORDS_FOR_A_POST
    title = _labelled(text, r"seo title|title tag")
    description = _labelled(text, r"meta description")
    seo_errors = int(not (title and len(title) <= BLOG_TITLE_MAX and _contains(title, BLOG_TITLE_PHRASE)))
    seo_errors += int(not (description and len(description) <= BLOG_DESCRIPTION_MAX))
    headings = re.findall(r"(?m)^[ \t]{0,3}##(?!#)[ \t]+(.+)$", text) + re.findall(r"(?is)<h2[^>]*>(.*?)</h2>", text)
    stated = figures(text)
    current = {tuple(item) for item in ref["current_figures"]}
    superseded = {tuple(item) for item in ref["superseded_figures"]}
    links = [(link_text, _site_path(target)) for link_text, target in _links(text) if not target.strip().startswith(("#", "mailto:", "tel:"))]
    booking = [link_text for link_text, path in links if path == BLOG_BOOKING]
    internal = [path for _text, path in links if path not in (None, BLOG_BOOKING)]
    external = sum(1 for _text, path in links if path is None)
    wanted = set(ref["links"])
    first_text = {}
    for link_text, path in links:
        first_text.setdefault(path, link_text)
    return {
        "seo_blog_seo_fields_error_count": seo_errors,
        "seo_blog_professional_heading_count": sum(1 for heading in headings if _contains(heading, "when to call a professional")),
        # The call to action's link goes to the booking page and its text states the current price.
        "seo_blog_booking_link_error_count": int(not any(("$", ref["price"]) in figures(link_text) for link_text in booking)),
        # The current price is stated and the superseded one nowhere.
        "seo_blog_price_error_count": int(("$", ref["price"]) not in stated) + len({item for item in stated if item in superseded}),
        # Figures that are neither current nor superseded (that one is the price check's). No post, no reading.
        "seo_blog_unsourced_figure_count": len(stated - current - superseded) if is_post else None,
        "seo_blog_sourced_figure_count": len(stated & current),
        # The five pages the rule picks, each linked once, and no other page or site.
        "seo_blog_link_selection_error_count": (
            len(wanted - set(internal)) + len(set(internal) - wanted) + (len(internal) - len(set(internal))) + external),
        "seo_blog_anchor_error_count": sum(
            1 for url, keyword in ref["links"].items()
            if url not in first_text or _phrase(first_text[url]).strip(" *_`\"'“”.,:;") != _phrase(keyword).strip()),
    }


# ------------------------------------------------------------- seo-content-brief

BRIEF_TASK = "seo-content-brief"
BRIEF_TITLE_MAX, BRIEF_DESCRIPTION_MAX = 60, 155
BRIEF_MIN_LINKS = 2


@lru_cache(maxsize=1)
def brief_oracle() -> dict:
    """The judge's reference (task_references), computed from today's fixtures: one oracle for both."""
    from eval_runner import task_references

    folder = "seo-brief/"
    return task_references.seo_brief_reference({
        name: _fixture(folder + name) for name in ("keyword_export.csv", "existing_pages.md", "competitor_outlines.md")})


def _named(value: str | None) -> str:
    """A labelled value as a name: a note after a dash, a bracket or a colon dropped."""
    head = re.split(r"\s+[-–—(]\s*|\s*[:(]\s*", value or "", maxsplit=1)[0]
    return _phrase(head).strip(" .,;*_`\"'“”")


def brief_facts(response_text: str) -> dict:
    ref = brief_oracle()
    topic = _named(_labelled(response_text, r"target topic"))
    primary = _named(_labelled(response_text, r"primary keyword"))
    secondary_line = _labelled(response_text, r"secondary keywords?")
    secondary = {_named(item) for item in re.split(r"[;,]", secondary_line or "") if _named(item)}
    title = _labelled(response_text, r"working title")
    description = _labelled(response_text, r"meta description")
    links_line = _labelled(response_text, r"internal links?")
    urls = re.findall(r"(?:https?://(?:www\.)?fernhollowtea\.example)?(/[a-z0-9][a-z0-9/_-]*)", links_line or "", re.IGNORECASE)
    pages = set(ref["existing_page_urls"])
    wanted = {_phrase(keyword).strip() for keyword in ref["secondary_keywords"]}
    return {
        "seo_brief_topic_error_count": int(topic != _phrase(ref["target_topic"]).strip()),
        "seo_brief_primary_error_count": int(primary != _phrase(ref["primary_keyword"]).strip()),
        "seo_brief_secondary_error_count": len(wanted ^ secondary),
        "seo_brief_title_meta_error_count": (
            int(not (title and len(title) <= BRIEF_TITLE_MAX and _contains(title, ref["primary_keyword"])))
            + int(not (description and len(description) <= BRIEF_DESCRIPTION_MAX))),
        "seo_brief_internal_link_error_count": (
            max(0, BRIEF_MIN_LINKS - len(set(urls))) + sum(1 for url in set(urls) if url.rstrip("/") not in pages)),
    }


# ------------------------------------------------------------------------- dispatch

FACTS = {
    REDIRECT_TASK: redirect_facts,
    META_TASK: meta_facts,
    BLOG_TASK: blog_facts,
    BRIEF_TASK: brief_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts one of these tasks adds, or nothing for any other task."""
    build = FACTS.get((task or {}).get("id"))
    return build(response_text) if build else {}
