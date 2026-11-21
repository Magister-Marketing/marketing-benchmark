"""Reference totals for the judge on the six data tasks added in November 2026.

A judge cannot count 260 rows, so without these it would have to take a
response's word for every figure. Each function below recomputes, from the
sources embedded in the exact prompt a run recorded, the figures its task's
rubric names: the banded answers and the lists and totals the judged
criteria refer to. Like `reference_facts.ledger_reference`, nothing is read
from today's fixture files and nothing comes from the response.

`scripts/gen_more_tasks.py` computes the task files' `near` targets with the
same functions, so the judge's reference and the oracle cannot disagree.
`tests/test_more_tasks.py` recomputes every answer and every other figure
returned here with separate code.

`task_reference` never raises: a prompt it cannot read yields no reference,
which is what every task had before this module existed, and a warning that
says so, because a judge without totals grades these tasks blind.
"""
import collections
import csv
import datetime as dt
import io
import math
import re
import warnings
from decimal import ROUND_HALF_UP, Decimal

VERSION = 4

_SOURCE_HEADING = re.compile(r"(?m)^---\n\n## (?:Supplied source: (?P<name>[^\n]+)|[^\n]*)\n\n")


def supplied_sources(exact_prompt: str) -> dict[str, str]:
    """The fixture blocks `bench.assemble_prompt` appended, by file name."""
    sources: dict[str, str] = {}
    headings = list(_SOURCE_HEADING.finditer(exact_prompt))
    for index, heading in enumerate(headings):
        name = heading.group("name")
        if not name:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(exact_prompt)
        if name.strip() in sources:
            raise ValueError(f"source {name.strip()!r} is supplied twice")
        sources[name.strip()] = exact_prompt[heading.end():end].strip() + "\n"
    return sources


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


# ------------------------------------------------------------------ seo-content-brief

# The prompt's expected click-through rate by rank: (first rank, last rank, rate). A
# keyword with no rank, or one worse than 20, has none. A new article aims for third.
SEO_CTR = (
    (1, 1, Decimal("0.30")), (2, 2, Decimal("0.16")), (3, 3, Decimal("0.11")), (4, 4, Decimal("0.08")),
    (5, 5, Decimal("0.06")), (6, 10, Decimal("0.03")), (11, 20, Decimal("0.01")),
)
SEO_TARGET_CTR = Decimal("0.11")
SEO_WON_RANK = 3
SEO_SECONDARY_COUNT = 4


def seo_ctr(rank: str) -> Decimal:
    """The expected click-through rate at a `current_rank` cell."""
    if rank == "":
        return Decimal(0)
    return next((rate for low, high, rate in SEO_CTR if low <= int(rank) <= high), Decimal(0))


def seo_already_won(row: dict) -> bool:
    """Whether the site already ranks third or better for the keyword."""
    return row["current_rank"] != "" and int(row["current_rank"]) <= SEO_WON_RANK


def seo_eligible(row: dict) -> bool:
    """Informational, difficulty at or under 45, and not already won."""
    return row["intent"] == "informational" and int(row["difficulty"]) <= 45 and not seo_already_won(row)


def seo_winnable(row: dict) -> Decimal:
    """The clicks a new article could add by ranking third: searches x (11% - the rate at its rank)."""
    return int(row["monthly_searches"]) * (SEO_TARGET_CTR - seo_ctr(row["current_rank"]))


def _whole(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


_SEO_FILLER_WORDS = frozenset("how to can you vs does is what a the of for do with and".split())


def seo_topic_outlines(outlines: str, topic: str) -> str:
    """The part of competitor_outlines.md under `## Topic: <topic>`, lowercased."""
    for block in re.split(r"(?m)^## Topic: ", outlines)[1:]:
        heading, _, body = block.partition("\n")
        if heading.strip().lower() == topic.lower():
            return body.lower()
    return ""


def seo_uncovered(keyword: str, topic: str, outlines: str) -> bool:
    """Whether no word of the topic's competing outlines touches the keyword.

    A keyword is touched when one of its own words (not the topic's words, not
    filler) is a word of an outline, plain or with -s, -es or -ing: "brew" is in
    "brewing", "da" is not in "today".
    """
    own = [word for word in re.findall(r"[a-z]+", keyword.lower())
           if word not in _SEO_FILLER_WORDS and word not in topic.lower().split()]
    return bool(own) and not any(re.search(r"\b" + re.escape(word) + r"(?:s|es|ing)?\b", outlines) for word in own)


def seo_brief_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["keyword_export.csv"])
    won = sorted((row for row in rows if seo_already_won(row)), key=lambda row: (int(row["current_rank"]), row["keyword"]))
    totals: dict[str, Decimal] = collections.defaultdict(Decimal)
    for row in rows:
        if seo_eligible(row):
            totals[row["topic"]] += seo_winnable(row)
    by_winnable = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    target, runner_up = by_winnable[0][0], by_winnable[1][0]
    eligible = sorted((row for row in rows if row["topic"] == target and seo_eligible(row)),
                      key=lambda row: (-seo_winnable(row), -int(row["monthly_searches"]), row["keyword"]))
    outlines = seo_topic_outlines(sources.get("competitor_outlines.md", ""), target)
    return {
        "answers": {
            "q1_already_won": len(won),
            "q2_eligible_count": len(eligible),
            "q3_topic_winnable": _whole(totals[target]),
            "q4_runner_up_winnable": _whole(totals[runner_up]),
            "q5_primary_winnable": _whole(seo_winnable(eligible[0])),
            "q6_won_volume": sum(int(row["monthly_searches"]) for row in won),
        },
        "target_topic": target,
        "runner_up_topic": runner_up,
        "primary_keyword": eligible[0]["keyword"],
        "secondary_keywords": [row["keyword"] for row in eligible[1:1 + SEO_SECONDARY_COUNT]],
        "eligible_keywords_in_target_topic": [
            {"keyword": row["keyword"], "monthly_searches": int(row["monthly_searches"]),
             "difficulty": int(row["difficulty"]), "current_rank": int(row["current_rank"]) if row["current_rank"] else None,
             "winnable_clicks": float(seo_winnable(row))} for row in eligible
        ],
        "eligible_keywords_neither_competing_outline_covers": [
            row["keyword"] for row in eligible if outlines and seo_uncovered(row["keyword"], target, outlines)
        ],
        "winnable_clicks_by_topic": {topic: float(value) for topic, value in by_winnable},
        "keywords_already_won": [
            {"keyword": row["keyword"], "rank": int(row["current_rank"]), "url": row["ranking_url"]} for row in won
        ],
        "existing_page_urls": sorted(set(re.findall(r"(?m)^\| (/[^ |]+) \|", sources.get("existing_pages.md", "")))),
        "interpretation": (
            "Winnable clicks are computed per keyword exactly as the prompt defines them and summed per topic; "
            "the answers A3 to A5 round those sums to whole clicks. Keywords ranking 4 to 20 are eligible, with "
            "the clicks they already get taken off."
        ),
    }


# --------------------------------------------------------------- seo-technical-triage

CRAWL_ISSUE_NAMES = {
    "noindex_in_sitemap": "noindex pages in the sitemap",
    "duplicate_titles": "duplicate titles",
    "bad_canonicals": "bad canonicals",
    "broken_linked_pages": "broken linked pages",
    "redirect_chains": "redirect chains",
}


def seo_crawl_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["crawl_export.csv"])
    by_url = {row["url"]: row for row in rows}

    def redirects(row: dict | None) -> bool:
        return row is not None and 300 <= int(row["status_code"]) < 400

    def indexable(row: dict) -> bool:
        return (int(row["status_code"]) == 200 and "noindex" not in row["meta_robots"]
                and row["canonical"] in ("", row["url"]))

    titles: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        if indexable(row):
            titles[row["title"]].append(row)
    duplicate_groups = {title: group for title, group in titles.items() if len(group) > 1}
    chain_starts = [row for row in rows if redirects(row) and redirects(by_url.get(row["redirect_target"]))]
    # Every redirecting URL of a chain: its first URL and each URL it passes through.
    chain_urls: dict[str, dict] = {}
    for row in chain_starts:
        hop: dict | None = row
        while redirects(hop) and hop["url"] not in chain_urls:
            chain_urls[hop["url"]] = hop
            hop = by_url.get(hop["redirect_target"])
    affected = {
        "broken_linked_pages": [row for row in rows if int(row["status_code"]) == 404 and int(row["inlinks"]) > 0],
        "redirect_chains": list(chain_urls.values()),
        "noindex_in_sitemap": [row for row in rows if "noindex" in row["meta_robots"] and row["in_sitemap"] == "yes"],
        "bad_canonicals": [row for row in rows if int(row["status_code"]) == 200
                           and row["canonical"] not in ("", row["url"])
                           and int(by_url.get(row["canonical"], {"status_code": 0})["status_code"]) != 200],
        "duplicate_titles": [row for group in duplicate_groups.values() for row in group],
    }
    counts = {name: len(urls) for name, urls in affected.items()}
    counts["redirect_chains"] = len(chain_starts)            # a chain is counted once, at its first URL
    counts["duplicate_titles"] = len(duplicate_groups)       # groups, not pages
    issues = {
        name: {
            "count_as_the_prompt_counts_it": counts[name],
            "affected_urls": sorted(row["url"] for row in urls),
            "organic_sessions_30d": sum(int(row["organic_sessions_30d"]) for row in urls),
            "inlinks": sum(int(row["inlinks"]) for row in urls),
        }
        for name, urls in affected.items()
    }
    top = max(rows, key=lambda row: int(row["organic_sessions_30d"]))
    return {
        "answers": {
            "q1_broken_linked": counts["broken_linked_pages"],
            "q2_redirect_chains": counts["redirect_chains"],
            "q3_noindex_in_sitemap": counts["noindex_in_sitemap"],
            "q4_bad_canonicals": counts["bad_canonicals"],
            "q5_duplicate_title_groups": counts["duplicate_titles"],
            "q6_sessions_at_risk": issues["noindex_in_sitemap"]["organic_sessions_30d"],
        },
        "issues": issues,
        "issue_order_by_sessions_then_inlinks": sorted(
            issues, key=lambda name: (-issues[name]["organic_sessions_30d"], -issues[name]["inlinks"])),
        "duplicate_title_groups": {title: sorted(row["url"] for row in group)
                                   for title, group in duplicate_groups.items()},
        "url_with_most_organic_sessions": {"url": top["url"], "organic_sessions_30d": int(top["organic_sessions_30d"])},
        "dead_pages_with_no_inlinks": sorted(
            row["url"] for row in rows if int(row["status_code"]) == 404 and int(row["inlinks"]) == 0),
        "interpretation": (
            "Counts and affected URLs follow the prompt's definitions; a redirect chain's affected URLs are "
            "every redirecting URL in it. dead_pages_with_no_inlinks are real 404s that the definition of a "
            "broken linked page leaves out: reporting them is not an error, and counting them in A1 is. "
            "Every other URL in the export is correctly configured."
        ),
    }


# -------------------------------------------------------------- search-terms-negatives

SEARCH_TARGET_CPA = Decimal("45")
# What the business facts rule out: repairs and parts, curtains, shutters,
# trade buyers, job seekers, and making your own.
SEARCH_RULED_OUT = re.compile(
    r"\b(repair|restring|fix|curtains?|drapes|shutters|wholesale|trade|jobs|careers|diy|how to make)\b"
)
SEARCH_BRAND = re.compile(r"\bsablewood\b")


def search_promote_candidate(row: dict) -> bool:
    conversions = int(row["conversions"])
    return (row["added_as_keyword"] == "no" and conversions >= 3
            and Decimal(row["cost_usd"]) / conversions <= SEARCH_TARGET_CPA)


def search_terms_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["search_terms_report.csv"])
    irrelevant = [row for row in rows if SEARCH_RULED_OUT.search(row["search_term"])]
    promote = [row for row in rows if search_promote_candidate(row)]

    def line(row: dict) -> dict:
        conversions = int(row["conversions"])
        return {
            "search_term": row["search_term"], "campaign": row["campaign"], "clicks": int(row["clicks"]),
            "cost_usd": float(row["cost_usd"]), "conversions": conversions,
            "cost_per_conversion_usd": _money(Decimal(row["cost_usd"]) / conversions) if conversions else None,
        }

    return {
        "answers": {
            "q1_zero_conversion_spend": _money(sum(Decimal(row["cost_usd"]) for row in rows if int(row["conversions"]) == 0)),
            "q2_promote_count": len(promote),
            "q3_irrelevant_spend": _money(sum(Decimal(row["cost_usd"]) for row in irrelevant)),
            "q4_promote_conversions": sum(int(row["conversions"]) for row in promote),
        },
        "irrelevant_search_terms": [line(row) for row in sorted(irrelevant, key=lambda row: row["search_term"])],
        "promote_candidates": [line(row) for row in sorted(promote, key=lambda row: -int(row["conversions"]))],
        "brand_search_terms": [line(row) for row in sorted(rows, key=lambda row: row["search_term"])
                               if SEARCH_BRAND.search(row["search_term"]) and row not in irrelevant],
        "not_yet_keywords_with_3_or_more_conversions_above_target": [
            line(row) for row in rows
            if row["added_as_keyword"] == "no" and int(row["conversions"]) >= 3 and not search_promote_candidate(row)
        ],
        "most_clicks_on_a_product_search_with_no_conversion": max(
            (int(row["clicks"]) for row in rows
             if int(row["conversions"]) == 0 and row not in irrelevant and not SEARCH_BRAND.search(row["search_term"])),
            default=0,
        ),
        "interpretation": "Every other search term in the report is a search for the brand or for a product Sablewood sells.",
    }


# -------------------------------------------------------------- lifecycle-reengagement

LIFECYCLE_LAPSED_BEFORE = dt.date(2026, 3, 3)    # 90 days before the prompt's "today"
LIFECYCLE_DORMANT_BEFORE = dt.date(2025, 6, 1)   # 12 months before it


def lifecycle_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["subscribers.csv"])

    def opened_before(row: dict, cutoff: dt.date) -> bool:
        return row["last_open_date"] == "" or dt.date.fromisoformat(row["last_open_date"]) < cutoff

    subscribed = [row for row in rows if row["consent_status"] == "subscribed"]
    mailable = [row for row in subscribed if row["hard_bounce"] == "no" and row["spam_complaint"] == "no"]
    lapsed = [row for row in mailable if opened_before(row, LIFECYCLE_LAPSED_BEFORE)]
    consent = collections.Counter(row["consent_status"] for row in rows)
    return {
        "answers": {
            "q1_mailable": len(mailable),
            "q2_lapsed": len(lapsed),
            "q3_lapsed_buyers": sum(1 for row in lapsed if int(row["orders_count"]) >= 1),
            "q4_lapsed_non_buyers": sum(1 for row in lapsed if int(row["orders_count"]) == 0),
            "q5_long_dormant": sum(1 for row in lapsed if opened_before(row, LIFECYCLE_DORMANT_BEFORE)),
        },
        "rows": len(rows),
        "three_email_audience": {
            "total": sum(1 for row in lapsed if not opened_before(row, LIFECYCLE_DORMANT_BEFORE)),
            "buyers": sum(1 for row in lapsed if not opened_before(row, LIFECYCLE_DORMANT_BEFORE)
                          and int(row["orders_count"]) >= 1),
            "non_buyers": sum(1 for row in lapsed if not opened_before(row, LIFECYCLE_DORMANT_BEFORE)
                              and int(row["orders_count"]) == 0),
        },
        "long_dormant_one_email_audience": {
            "total": sum(1 for row in lapsed if opened_before(row, LIFECYCLE_DORMANT_BEFORE)),
            "buyers": sum(1 for row in lapsed if opened_before(row, LIFECYCLE_DORMANT_BEFORE)
                          and int(row["orders_count"]) >= 1),
            "non_buyers": sum(1 for row in lapsed if opened_before(row, LIFECYCLE_DORMANT_BEFORE)
                              and int(row["orders_count"]) == 0),
        },
        "not_mailable": {
            "unsubscribed": consent["unsubscribed"],
            "never_consented": consent["never_consented"],
            "pending_confirmation": consent["pending_confirmation"],
            "subscribed_with_hard_bounce": sum(1 for row in subscribed if row["hard_bounce"] == "yes"),
            "subscribed_with_spam_complaint": sum(
                1 for row in subscribed if row["hard_bounce"] == "no" and row["spam_complaint"] == "yes"),
        },
        "without_consent_but_with_orders": sum(
            1 for row in rows
            if row["consent_status"] in ("unsubscribed", "never_consented") and int(row["orders_count"]) >= 1
        ),
    }


# -------------------------------------------------------------------- ab-test-readout

def two_proportion_p_value(x1: int, n1: int, x2: int, n2: int) -> float:
    """Two-sided p-value of a pooled two-proportion z-test."""
    pooled = (x1 + x2) / (n1 + n2)
    z = (x2 / n2 - x1 / n1) / math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    return math.erfc(abs(z) / math.sqrt(2))


def ab_test_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["experiment_results.csv"])
    fields = ("visitors", "signups", "paid_conversions")

    def totals(variant: str, device: str | None = None) -> dict:
        return {field: sum(int(row[field]) for row in rows
                           if row["variant"] == variant and device in (None, row["device"]))
                for field in fields}

    control, variant = totals("control"), totals("variant_b")
    rate_control = control["signups"] / control["visitors"]
    rate_variant = variant["signups"] / variant["visitors"]
    expected = (control["visitors"] + variant["visitors"]) / 2
    return {
        "answers": {
            "q1_control_visitors": control["visitors"],
            "q2_variant_visitors": variant["visitors"],
            "q3_control_rate": round(rate_control * 100, 2),
            "q4_variant_rate": round(rate_variant * 100, 2),
            "q5_relative_lift": round((rate_variant / rate_control - 1) * 100, 1),
            "q6_srm_chi_square": round(
                ((control["visitors"] - expected) ** 2 + (variant["visitors"] - expected) ** 2) / expected, 1),
            "q7_p_value": round(two_proportion_p_value(
                control["signups"], control["visitors"], variant["signups"], variant["visitors"]), 3),
        },
        "totals": {"control": control, "variant_b": variant},
        "by_device": {
            device: {"control": totals("control", device), "variant_b": totals("variant_b", device)}
            for device in sorted({row["device"] for row in rows})
        },
        "weeks": len({row["week"] for row in rows}),
        # What the sample-ratio check compares each variant with: half of the visitors the test received.
        "expected_visitors_per_variant_under_the_planned_50_50_split": int(expected) if expected == int(expected) else expected,
        "secondary_metric_p_value": round(two_proportion_p_value(
            control["paid_conversions"], control["visitors"],
            variant["paid_conversions"], variant["visitors"]), 3),
        "interpretation": (
            "The plan's sample size, split and decision rule are in test_plan.md in the prompt. "
            "expected_visitors_per_variant_under_the_planned_50_50_split is half of the visitors the two variants "
            "received. A readout may state it, also as the count the planned split called for: it is derived from "
            "the results. It is not the sample size the plan required of each variant."
        ),
    }


# ------------------------------------------------------------- monthly-report-reconcile

def monthly_reference(sources: dict[str, str]) -> dict:
    ads = _rows(sources["ads_platforms.csv"])
    events = _rows(sources["analytics_purchases.csv"])
    orders = _rows(sources["order_system.csv"])
    in_may = [row for row in orders if row["order_date"].startswith("2026-05")]
    real = [row for row in in_may if row["status"] not in ("cancelled", "test")]
    spend = sum(Decimal(row["spend_usd"]) for row in ads)
    gross = sum(Decimal(row["gross_usd"]) for row in real)
    refunds = sum(Decimal(row["refund_usd"]) for row in real)
    status = collections.Counter(row["status"] for row in in_may)
    first_event: dict[str, Decimal] = {}
    for row in events:
        first_event.setdefault(row["order_id"], Decimal(row["revenue_usd"]))
    by_platform: dict[str, int] = collections.defaultdict(int)
    for row in ads:
        by_platform[row["platform"]] += int(row["platform_conversions"])
    return {
        "answers": {
            "q1_ad_spend": _money(spend),
            "q2_real_orders": len(real),
            "q3_net_revenue": _money(gross - refunds),
            "q4_duplicate_rows": len(events) - len({row["order_id"] for row in events}),
            "q5_blended_roas": round(float((gross - refunds) / spend), 2),
            "q6_platform_conversions": sum(by_platform.values()),
        },
        "order_system": {
            "rows": len(orders),
            "rows_dated_outside_may": len(orders) - len(in_may),
            "may_rows_by_status": dict(status),
            "gross_of_real_orders_usd": _money(gross),
            "refunds_on_real_orders_usd": _money(refunds),
        },
        "analytics": {
            "purchase_rows": len(events),
            "distinct_order_ids": len(first_event),
            "revenue_all_rows_usd": _money(sum(Decimal(row["revenue_usd"]) for row in events)),
            "revenue_counting_each_order_once_usd": _money(sum(first_event.values())),
            "real_orders_with_no_purchase_event": sum(1 for row in real if row["order_id"] not in first_event),
        },
        "ad_platforms": {
            "reported_conversions_by_platform": dict(by_platform),
            "reported_revenue_usd": _money(sum(Decimal(row["platform_revenue_usd"]) for row in ads)),
        },
        "interpretation": "Analytics and platform figures are each tool's own report; the answers use the prompt's definitions.",
    }


REFERENCES = {
    "seo-content-brief": seo_brief_reference,
    "seo-technical-triage": seo_crawl_reference,
    "search-terms-negatives": search_terms_reference,
    "lifecycle-reengagement": lifecycle_reference,
    "ab-test-readout": ab_test_reference,
    "monthly-report-reconcile": monthly_reference,
}


def task_reference(task_id: str | None, exact_prompt: str) -> dict:
    """The judge's reference for one recorded prompt, or {} when there is none."""
    build = REFERENCES.get(task_id)
    if build is None:
        return {}
    try:
        return {"version": VERSION, **build(supplied_sources(exact_prompt))}
    except Exception as error:  # noqa: BLE001 - an unreadable prompt means no reference, never a failed grading run
        warnings.warn(
            f"no judge reference for {task_id}: its sources could not be read from the recorded prompt "
            f"({type(error).__name__}: {error}); the judge will grade this task without reference totals",
            RuntimeWarning, stacklevel=2,
        )
        return {}
