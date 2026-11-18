"""Reference totals for the judge on the six data tasks added in November 2026.

A judge cannot count 260 rows, so without these it would have to take a
response's word for every figure. Each function below recomputes, from the
sources embedded in the exact prompt a run recorded, the figures its task's
rubric names: the banded answers and the lists and totals the judged
criteria refer to. Like `reference_facts.ledger_reference`, nothing is read
from today's fixture files and nothing comes from the response.

`scripts/gen_more_tasks.py` computes the task files' `near` targets with the
same functions, so the judge's reference and the oracle cannot disagree.
`tests/test_more_tasks.py` recomputes every answer with separate code.

`task_reference` never raises: a prompt it cannot read yields no reference,
which is what every task had before this module existed.
"""
import collections
import csv
import datetime as dt
import io
import math
import re
from decimal import Decimal

VERSION = 1

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

def seo_qualifies(row: dict) -> bool:
    """Informational, difficulty at or under 45, and not already in the top 10."""
    ranked_top_ten = row["current_rank"] != "" and int(row["current_rank"]) <= 10
    return row["intent"] == "informational" and int(row["difficulty"]) <= 45 and not ranked_top_ten


def seo_brief_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["keyword_export.csv"])
    ranking = [row for row in rows if row["current_rank"] != "" and int(row["current_rank"]) <= 10]
    totals: dict[str, int] = collections.defaultdict(int)
    for row in rows:
        if seo_qualifies(row):
            totals[row["topic"]] += int(row["monthly_searches"])
    by_volume = sorted(totals.items(), key=lambda item: -item[1])
    target = by_volume[0][0]
    qualifying = sorted(
        (row for row in rows if row["topic"] == target and seo_qualifies(row)),
        key=lambda row: -int(row["monthly_searches"]),
    )
    return {
        "answers": {
            "q1_already_ranking": len(ranking),
            "q2_qualifying_count": len(qualifying),
            "q3_topic_volume": totals[target],
            "q4_primary_volume": int(qualifying[0]["monthly_searches"]),
            "q5_ranking_volume": sum(int(row["monthly_searches"]) for row in ranking),
        },
        "target_topic": target,
        "primary_keyword": qualifying[0]["keyword"],
        "qualifying_keywords_in_target_topic": [
            {"keyword": row["keyword"], "monthly_searches": int(row["monthly_searches"]),
             "difficulty": int(row["difficulty"])} for row in qualifying
        ],
        "qualifying_volume_by_topic": dict(by_volume),
        "keywords_already_ranking_top_10": [
            {"keyword": row["keyword"], "rank": int(row["current_rank"]), "url": row["ranking_url"]}
            for row in ranking
        ],
        "existing_page_urls": sorted(set(re.findall(r"(?m)^\| (/[^ |]+) \|", sources.get("existing_pages.md", "")))),
    }


# --------------------------------------------------------------- seo-technical-triage

def seo_crawl_reference(sources: dict[str, str]) -> dict:
    rows = _rows(sources["crawl_export.csv"])
    status = {row["url"]: int(row["status_code"]) for row in rows}

    def redirects(code: int | None) -> bool:
        return code is not None and 300 <= code < 400

    def indexable(row: dict) -> bool:
        return (int(row["status_code"]) == 200 and "noindex" not in row["meta_robots"]
                and row["canonical"] in ("", row["url"]))

    titles: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        if indexable(row):
            titles[row["title"]].append(row)
    duplicate_groups = {title: group for title, group in titles.items() if len(group) > 1}
    issues = {
        "broken_linked_pages": [row for row in rows if int(row["status_code"]) == 404 and int(row["inlinks"]) > 0],
        "redirect_chains": [row for row in rows if redirects(int(row["status_code"]))
                            and redirects(status.get(row["redirect_target"]))],
        "noindex_in_sitemap": [row for row in rows if "noindex" in row["meta_robots"] and row["in_sitemap"] == "yes"],
        "bad_canonicals": [row for row in rows if int(row["status_code"]) == 200
                           and row["canonical"] not in ("", row["url"]) and status.get(row["canonical"]) != 200],
        "duplicate_title_pages": [row for group in duplicate_groups.values() for row in group],
    }
    top = max(rows, key=lambda row: int(row["organic_sessions_30d"]))
    return {
        "answers": {
            "q1_broken_linked": len(issues["broken_linked_pages"]),
            "q2_redirect_chains": len(issues["redirect_chains"]),
            "q3_noindex_in_sitemap": len(issues["noindex_in_sitemap"]),
            "q4_bad_canonicals": len(issues["bad_canonicals"]),
            "q5_duplicate_title_groups": len(duplicate_groups),
            "q6_sessions_at_risk": sum(int(row["organic_sessions_30d"]) for row in issues["noindex_in_sitemap"]),
        },
        "issues": {
            name: {
                "urls": sorted(row["url"] for row in affected),
                "organic_sessions_30d": sum(int(row["organic_sessions_30d"]) for row in affected),
                "inlinks": sum(int(row["inlinks"]) for row in affected),
            }
            for name, affected in issues.items()
        },
        "duplicate_title_groups": {title: sorted(row["url"] for row in group)
                                   for title, group in duplicate_groups.items()},
        "url_with_most_organic_sessions": {"url": top["url"], "organic_sessions_30d": int(top["organic_sessions_30d"])},
        "interpretation": "Counts follow the prompt's definitions. URLs outside these lists are correctly configured in this export.",
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
        "brand_search_terms": [line(row) for row in rows
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
        "interpretation": "Every other search term in the report is for a product Sablewood sells.",
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
        "secondary_metric_p_value": round(two_proportion_p_value(
            control["paid_conversions"], control["visitors"],
            variant["paid_conversions"], variant["visitors"]), 3),
        "interpretation": "The plan's sample size, split and decision rule are in test_plan.md in the prompt.",
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
            "distinct_order_ids": len({row["order_id"] for row in events}),
            "revenue_all_rows_usd": _money(sum(Decimal(row["revenue_usd"]) for row in events)),
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
    except Exception:  # noqa: BLE001 - an unreadable prompt means no reference, never a failed grading run
        return {}
