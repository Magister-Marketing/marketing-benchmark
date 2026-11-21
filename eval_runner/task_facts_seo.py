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


# ------------------------------------------------------------------------- dispatch

FACTS = {
    REDIRECT_TASK: redirect_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts one of these tasks adds, or nothing for any other task."""
    build = FACTS.get((task or {}).get("id"))
    return build(response_text) if build else {}
