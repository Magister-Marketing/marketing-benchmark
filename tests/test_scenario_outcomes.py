"""Offline tests for the scenario outcome checks: pure functions over fixture
rows shaped like what the lane runner harvests. No provider or database."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.runner.scenario_metrics import compute_metrics, render_table, summarize
from evals.runner.scenario_outcomes import (
    card_facts,
    check_ad_campaign_draft,
    check_answer_grounded,
    check_shopify_page_section,
    deny_rule_for,
    draft_parts,
    entities_in,
    evaluate,
    html_text,
    number_supported,
    numbers_in,
    post_approval_reply,
    questions_in,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = "2026-10-21T10:00:00+00:00"


def _scenario(name: str) -> dict:
    return json.loads((REPO_ROOT / "evals/scenarios" / f"{name}.json").read_text())


def _call(tool: str, args: dict, result, *, error: bool = False, call_id: str = "c1") -> dict:
    return {"tool_call_id": call_id, "tool": tool, "args": args, "is_error": error,
            "result_text": result if isinstance(result, str) else json.dumps(result), "at": T0}


def _assistant(text: str, *, at: str = "2026-10-21T10:03:00+00:00", turn: str = "t1", block: int = 5) -> dict:
    return {"id": f"a-{turn}-{block}", "role": "assistant", "content": text, "created_at": at,
            "turn_id": turn, "block_index": block, "metadata": None}


# ── Numbers ───────────────────────────────────────────────────────────────────

def test_numbers_in_skips_dates_periods_and_small_counts() -> None:
    text = ("Last week (Oct 14–20, 2026) organic clicks were 1,234 (+12.5% vs the 7 days before), "
            "impressions 45,678, CTR 2.7%, 3 pages lost rank; revenue $1,050.40 on 2026-10-18 at 10:30.")
    found = {n["text"]: n for n in numbers_in(text)}
    assert set(found) == {"1,234", "12.5%", "45,678", "2.7%", "$1,050.40"}
    assert found["1,234"]["value"] == 1234 and found["1,234"]["kind"] == "number"
    assert found["12.5%"]["kind"] == "percent" and found["12.5%"]["decimals"] == 1
    assert found["$1,050.40"]["kind"] == "currency" and found["$1,050.40"]["value"] == 1050.4


def test_number_supported_exact_fraction_and_derived() -> None:
    values = [1234.0, 1100.0, 0.027, 45678.0]
    assert number_supported({"value": 1234, "decimals": 0, "kind": "number"}, values, derived_percentages=False) == "exact"
    assert number_supported({"value": 1234.4, "decimals": 1, "kind": "number"}, values, derived_percentages=False) is None
    assert number_supported({"value": 2.7, "decimals": 1, "kind": "percent"}, values, derived_percentages=False) == "fraction"
    # 1234 vs 1100 is +12.2%: derivable only when the scenario allows it.
    assert number_supported({"value": 12.2, "decimals": 1, "kind": "percent"}, values, derived_percentages=False) is None
    assert number_supported({"value": 12.2, "decimals": 1, "kind": "percent"}, values, derived_percentages=True) == "derived"


# ── answer_grounded ───────────────────────────────────────────────────────────

GSC_RESULT = {
    "selection": {"source": "gsc", "metric": "clicks", "from_date": "2026-10-13", "to_date": "2026-10-19"},
    "rows": [
        {"date": "2026-10-13", "clicks": 180, "impressions": 6500, "ctr": 0.0277},
        {"date": "2026-10-19", "clicks": 1234, "impressions": 45678, "ctr": 0.027},
    ],
}
GSC_PAGES = {"rows": [
    {"keys": ["https://www.artworkssandiego.com/flood-response-guide"], "clicks": 410, "position": 8.4},
    {"page": "/services/art-storage", "clicks": 96, "position": 3.1},
]}


def _grounded_record(reply: str, *, calls=None) -> dict:
    calls = calls if calls is not None else [
        _call("magister_read_analytics_snapshots", {"source": "gsc", "external_id": "sc-domain:x", "metric": "clicks"}, GSC_RESULT, call_id="c1"),
        _call("magister_read_analytics_breakdown", {"source": "gsc", "external_id": "sc-domain:x", "kind": "top_pages"}, GSC_PAGES, call_id="c2"),
        _call("read", {"path": "/data/BRAND.md"}, "ArtWorks San Diego brand: 99 reasons", call_id="c3"),
    ]
    return {
        "started_at": T0, "ended_at": "2026-10-21T10:10:00+00:00",
        "rows": {"chat_messages": [_assistant(reply)], "transcript_tool_calls": calls, "approvals": []},
    }


def test_answer_grounded_passes_when_numbers_and_entity_come_from_the_rows() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    reply = ("Organic search last week: 1,234 clicks on 45,678 impressions (CTR 2.7%), up 586% on the week before. "
             "The flood-response guide (/flood-response-guide) took 410 clicks at position 8.4; move it into the top 5.")
    result = check_answer_grounded(_grounded_record(reply), spec)
    assert result["passed"] is True
    assert result["unsupported_numbers"] == []
    assert result["read_calls_ok"] == 2 and result["tools_read"] == ["read_analytics_breakdown", "read_analytics_snapshots"]
    assert any("flood-response-guide" in e for e in result["entities_named"])
    # The brand file's "99" is not an analytics result and must not support a claim.
    assert "99" not in [n["text"] for n in result["numbers"]]


def test_answer_grounded_fails_on_an_invented_number_or_a_generic_recommendation() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    invented = check_answer_grounded(_grounded_record("Clicks were 1,234 and bounce rate 61%; refresh old posts."), spec)
    assert invented["passed"] is False and invented["unsupported_numbers"] == ["61%"]
    assert invented["entities_named"] == []
    nothing_read = check_answer_grounded(_grounded_record("Clicks were 1,234.", calls=[]), spec)
    assert nothing_read["passed"] is False and nothing_read["read_calls"] == 0


def test_answer_grounded_filters_calls_by_source_for_the_ads_review() -> None:
    spec = _scenario("google-ads-performance-review")["outcome"]
    ads = {"rows": [
        {"campaign": {"id": "22334455", "name": "Emergency Removal - Search"}, "metrics": {"cost_micros": 412500000, "conversions": 0, "clicks": 310}},
        {"campaign": {"id": "99887766", "name": "Storage - Brand"}, "metrics": {"cost_micros": 150000000, "conversions": 6, "clicks": 120}},
    ]}
    calls = [
        _call("magister_integration_read", {"service": "google_ads", "path": "v24/customers/1/googleAds:search"}, ads, call_id="g1"),
        _call("magister_read_analytics_snapshots", {"source": "ga4", "external_id": "p1", "metric": "sessions"}, {"rows": [{"sessions": 777}]}, call_id="g2"),
    ]
    reply = "Pause 'Emergency Removal - Search': 310 clicks, $412.50 spent and 0 conversions in 30 days, while Storage - Brand converted 6 times for $150."
    result = check_answer_grounded(_grounded_record(reply, calls=calls), spec)
    assert result["read_calls_ok"] == 1  # the ga4 read does not count for a google_ads outcome
    assert result["unsupported_numbers"] == ["$412.50", "$150"]  # micros are not dollars in the rows
    assert "Emergency Removal - Search" in result["entities_named"]
    assert result["passed"] is False
    grounded = check_answer_grounded(_grounded_record(reply.replace("$412.50", "412500000 micros").replace("$150", "150000000 micros"), calls=calls), spec)
    assert grounded["passed"] is True


def test_check_in_fails_when_no_page_or_query_rows_were_read() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    totals_only = [_call("magister_read_analytics_snapshots", {"source": "gsc", "external_id": "x"}, GSC_RESULT, call_id="c1")]
    result = check_answer_grounded(_grounded_record("Clicks were 1,234 last week; refresh the top pages.", calls=totals_only), spec)
    assert result["passed"] is False and result["entities_in_results"] == 0 and "no page or query rows read" in result["summary"]


def test_answer_grounded_on_an_empty_account_passes_only_an_honest_reply() -> None:
    spec = _scenario("google-ads-performance-review")["outcome"]
    empty = [_call("magister_integration_read", {"service": "google_ads", "path": "v24/customers/1/googleAds:search"},
                   {"body": {"fieldMask": "campaign.id,campaign.name", "queryResourceConsumption": "1395"}}, call_id="g1")]
    honest = check_answer_grounded(_grounded_record("The account ran no campaigns in the last 30 days, so there is nothing to pause.", calls=empty), spec)
    assert honest["passed"] is True and honest["entities_in_results"] == 0 and "no entities" in honest["summary"]
    invented = check_answer_grounded(_grounded_record("Pause 'Brand - Search': $412.50 spent, 0 conversions.", calls=empty), spec)
    assert invented["passed"] is False and invented["unsupported_numbers"] == ["$412.50"]
    unread = check_answer_grounded(_grounded_record("There are no campaigns.", calls=[]), spec)
    assert unread["passed"] is False


def test_window_sums_back_weekly_totals_the_agent_adds_up() -> None:
    from evals.runner.scenario_outcomes import table_rows, window_sums

    daily = "date,clicks,impressions\n" + "\n".join(f"2026-10-{d:02d},{c},{i}" for d, c, i in [
        (5, 10, 300), (6, 9, 280), (7, 8, 290), (8, 9, 310), (9, 10, 270), (10, 9, 260), (11, 9, 289),
        (12, 5, 220), (13, 4, 230), (14, 5, 221), (15, 4, 224), (16, 5, 226), (17, 4, 228), (18, 5, 225),
    ])
    rows = table_rows(daily, path="data/gsc/x/daily.csv")
    sums = window_sums(rows)
    assert 64.0 in sums and 1999.0 in sums and 32.0 in sums and 1574.0 in sums  # the two weeks' totals
    by_page = "date,page,impressions\n2026-10-12,/extension,500\n2026-10-13,/extension,438\n2026-10-12,/,300\n2026-10-13,/,341\n"
    page_sums = window_sums(table_rows(by_page, path="daily-by-page.csv"))
    assert 938.0 in page_sums and 641.0 in page_sums and 800.0 not in page_sums  # series never mix
    json_rows = json.dumps({"rows": [{"date": "2026-10-12", "sessions": 500}, {"date": "2026-10-13", "sessions": 515}]})
    assert 1015.0 in window_sums(table_rows(json_rows))
    # A hosted read answers in an action envelope with long-format rows under receipt.
    envelope = json.dumps({"ok": True, "receipt": {"selection": {"source": "gsc"}, "rows": [
        {"date": "2026-10-12", "metric": "clicks", "dimension": None, "value": 5.0},
        {"date": "2026-10-13", "metric": "clicks", "dimension": None, "value": 4.0},
        {"date": "2026-10-12", "metric": "impressions", "dimension": None, "value": 220.0},
        {"date": "2026-10-13", "metric": "impressions", "dimension": None, "value": 230.0},
    ]}})
    long_sums = window_sums(table_rows(envelope))
    assert 9.0 in long_sums and 450.0 in long_sums and 225.0 not in long_sums
    assert number_supported({"value": 1999, "decimals": 0, "kind": "number"}, [10.0], derived_percentages=False, sums=sums) == "sum"
    assert number_supported({"value": 1999, "decimals": 0, "kind": "number"}, [10.0], derived_percentages=False) is None


def test_file_reads_count_only_on_analytics_paths() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    csv = "date,clicks,impressions\n2026-10-13,180,6500\n2026-10-19,1234,45678\n"
    pages = "page,clicks\n/flood-response-guide,410\n"
    calls = [
        _call("read", {"path": "/data/.openclaw/skills/seo-audit/SKILL.md"}, "a skill: 99 steps", call_id="r1"),
        _call("read", {"path": "/data/.openclaw/workspace/data/gsc/sc-domain-x/daily.csv"}, csv, call_id="r2"),
        _call("exec", {"command": "head -5 data/gsc/sc-domain-x/daily-by-page.csv", "workdir": "/data/.openclaw/workspace"}, pages, call_id="r3"),
        _call("exec", {"command": "find audits -type f"}, "audits/2026-10-21-light-audit.md", call_id="r4"),
    ]
    result = check_answer_grounded(_grounded_record("Clicks 1,234 last week; /flood-response-guide took 410 of them.", calls=calls), spec)
    assert result["read_calls"] == 2 and result["tools_read"] == ["exec", "read"]
    # A script that builds its paths from a quoted 'data' directory reads the pulls too.
    script = _call("exec", {"command": "python3 - <<'PY'\nimport os\nbase='data'\nprint(open(os.path.join(base,'gsc','x','daily.csv')).read())"}, csv, call_id="r5")
    assert check_answer_grounded(_grounded_record("Clicks 1,234.", calls=[script]), spec)["read_calls"] == 1
    assert result["passed"] is True and result["unsupported_numbers"] == []
    ads = _scenario("google-ads-performance-review")["outcome"]
    assert check_answer_grounded(_grounded_record("Clicks 1,234.", calls=calls), ads)["read_calls"] == 0  # gsc files are not google_ads


def test_entities_in_reads_nested_keys_and_non_json_results() -> None:
    calls = [_call("magister_read_analytics_breakdown", {"source": "gsc"}, GSC_PAGES), _call("x", {}, '"query": "art storage san diego" and more')]
    found = entities_in(calls, ["keys", "page", "query"])
    assert "https://www.artworkssandiego.com/flood-response-guide" in found and "/services/art-storage" in found
    assert "art storage san diego" in found
    # Long-format rows: a by-page series holds pages under `dimension`, a by-channel one holds channel names.
    long_rows = {"receipt": {"rows": [
        {"date": "2026-10-13", "metric": "sessions", "dimension": "/signup", "value": 12.0},
        {"date": "2026-10-13", "metric": "sessions", "dimension": "Organic Search", "value": 40.0},
    ]}}
    found = entities_in([_call("magister_read_analytics_snapshots", {"source": "ga4"}, long_rows)], ["query"], ["dimension"])
    assert found == ["/signup"]
    assert entities_in([_call("x", {"source": "google_ads"}, long_rows)], ["dimension"]) == ["/signup", "Organic Search"]


GA4_SYNC, ADS_SYNC = "4d5af515-19af-43c7-a40e-29717d3553b2", "9bdd8673-c59e-478e-8b1f-86aff2ebeb4f"


def _syncs_call() -> dict:
    return _call("magister_list_data_syncs", {}, {"ok": True, "receipt": {"syncs": [
        {"id": GA4_SYNC, "source": "ga4", "display_name": "Magister Website"},
        {"id": ADS_SYNC, "source": "google_ads", "display_name": "Magister Marketing"},
    ]}}, call_id="s0")


def _asset_call(sync: str, name: str, content: str, *, folder: str = "Google Analytics › Magister Website",
                call_id: str = "a1", offset: int = 0) -> dict:
    return _call("magister_read_asset", {"asset_id": f"generated:data:{sync}:{name.removesuffix('.csv')}"}, {
        "ok": True, "receipt": {"asset": {"id": f"generated:data:{sync}:{name}", "name": name, "contentType": "text/csv",
                                          "folder": folder}, "content": content, "offset": offset}}, call_id=call_id)


def test_library_csv_reads_count_by_their_sync_source() -> None:
    daily = "date,sessions,users\n2026-10-12,153,120\n2026-10-13,149,118\n2026-10-14,122,101\n"
    pages = "page,sessions\n/signup,41\n/pricing,18\n"
    calls = [_syncs_call(), _asset_call(GA4_SYNC, "daily.csv", daily, call_id="a1"),
             _asset_call(GA4_SYNC, "top-pages-30d.csv", pages, call_id="a2"),
             _call("magister_read_asset", {"asset_id": "resources/draft.md"}, {"receipt": {"content": "999 visitors"}}, call_id="a3")]
    reply = "Sessions totalled 424 over Oct 12–14 (153 on the first day); /signup drew 41 of them, so start there."
    check_in = check_answer_grounded(_grounded_record(reply, calls=calls), _scenario("analytics-weekly-check-in")["outcome"])
    assert check_in["read_calls"] == 2  # the draft is not an analytics result
    assert check_in["unsupported_numbers"] == [] and check_in["window_sums"] > 0  # 424 is a sum of the CSV's rows
    assert check_in["entities_named"] == ["/signup"] and check_in["passed"] is True
    ads = check_answer_grounded(_grounded_record(reply, calls=calls), _scenario("google-ads-performance-review")["outcome"])
    assert ads["read_calls"] == 0  # ga4 files never count for the google_ads outcome
    # Without a list_data_syncs result the asset's Library folder names its source.
    by_folder = [_asset_call(ADS_SYNC, "daily.csv", "date,cost\n2026-10-12,0\n", folder="Google Ads › Magister Marketing")]
    assert check_answer_grounded(_grounded_record("Nothing ran.", calls=by_folder), _scenario("google-ads-performance-review")["outcome"])["read_calls"] == 1
    # A later page of a CSV has no header row and yields no rows.
    from evals.runner.scenario_outcomes import table_rows
    assert table_rows(_asset_call(GA4_SYNC, "daily.csv", "2026-10-15,117,99\n", offset=4000)["result_text"]) == []


def test_stated_gaps_and_weekly_means_are_supported_and_a_late_value_still_counts() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    filler = {"rows": [{"date": f"2026-09-{d:02d}", "metric": "x", "dimension": None, "value": 1000.0 + i}
                       for i, d in enumerate(range(1, 31))] * 1}
    noise = _call("magister_read_analytics_snapshots", {"source": "ga4"}, {"blob": list(range(2000, 4000))}, call_id="n1")
    last = _call("magister_integration_read", {"service": "search_console", "path": "sites/x/searchAnalytics/query"},
                 {"rows": [{"clicks": 32, "position": 8.659466}, {"clicks": 64, "position": 7.237618}],
                  "ctr": [0.0203303, 0.0320160]}, call_id="n2")
    daily = "date,position\n" + "\n".join(f"2026-10-{d:02d},{p}" for d, p in zip(range(5, 12), [7.1, 7.4, 7.9, 7.6, 7.5, 7.8, 7.76]))
    calls = [noise, _call("magister_read_analytics_snapshots", {"source": "gsc"}, filler, call_id="n0"), last,
             _call("read", {"path": "/data/.openclaw/workspace/data/gsc/x/daily.csv"}, daily, call_id="n3")]
    reply = ("Position went from 7.2 to 8.7, weaker by 1.4 positions; CTR fell from 3.2% to 2.0%, "
             "down 1.2 percentage points. The daily average for Oct 5–11 was 7.58.")
    result = check_answer_grounded(_grounded_record(reply, calls=calls), spec)
    how = {n["text"]: n["supported"] for n in result["numbers"]}
    assert how["7.2"] == "exact"  # read after 2,000 other values
    assert how["1.4"] == "difference" and how["1.2 percentage points"] in ("difference", "derived")
    assert how["7.58"] == "sum"  # the 7-day mean of the daily rows
    assert result["unsupported_numbers"] == []
    # A gap between values the reply never stated is not supported.
    assert check_answer_grounded(_grounded_record("Weaker by 1.4 positions.", calls=calls), spec)["unsupported_numbers"] == ["1.4"]


def test_rows_of_a_cut_off_result_still_back_the_sums() -> None:
    from evals.runner.scenario_outcomes import table_rows, window_sums

    rows = [{"date": f"2026-10-{d}", "metric": "impressions", "dimension": None, "value": v}
            for d, v in zip(range(12, 19), [220, 230, 221, 224, 226, 228, 225])]
    full = json.dumps({"ok": True, "receipt": {"rows": rows + [{"date": "2026-10-18", "metric": "page_clicks", "dimension": "page:/x", "value": 3}]}}, indent=2)
    cut = full[: full.rindex('"page_clicks"')]  # stops inside the last object
    assert len(table_rows(cut)) == 7
    assert 1574.0 in window_sums(table_rows(cut))
    assert table_rows('{"rows": [') == [] and table_rows("no rows here") == []


def test_series_dimensions_name_pages_and_queries_and_the_brand_never_counts() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    series = {"receipt": {"rows": [
        {"date": "2026-10-12", "metric": "page_sessions", "dimension": "page:/", "value": 294.0},
        {"date": "2026-10-12", "metric": "page_clicks", "dimension": "page:/tools/llms-txt-checker", "value": 3.0},
        {"date": "2026-10-12", "metric": "query_clicks", "dimension": "query:ai marketing agent", "value": 4.0},
    ]}}
    queries = {"rows": [{"keys": ["magister"], "clicks": 12}, {"keys": ["magiste"], "clicks": 2}]}
    calls = [_call("magister_read_analytics_snapshots", {"source": "ga4"}, series, call_id="s1"),
             _call("magister_read_analytics_breakdown", {"source": "gsc", "kind": "top_queries"}, queries, call_id="s2")]
    found = entities_in(calls, spec["entity"]["keys"], spec["entity"]["path_keys"])
    assert {"/", "/tools/llms-txt-checker", "ai marketing agent", "magister"} <= set(found)
    brand_only = check_answer_grounded(_grounded_record("Magister drew 12 clicks; keep going.", calls=calls), spec)
    assert brand_only["entities_named"] == [] and brand_only["passed"] is False
    homepage = check_answer_grounded(_grounded_record("The homepage held 294 sessions; fix its hero first.", calls=calls), spec)
    assert homepage["entities_named"] == ["/"] and homepage["passed"] is True


def test_homepage_names_the_site_root_and_a_bare_slash_does_not() -> None:
    from evals.runner.scenario_outcomes import entities_named

    entities = ["/", "https://magistermarketing.com/", "/extension"]
    assert entities_named("Fix the homepage hero first.", entities) == ["/", "https://magistermarketing.com/"]
    assert entities_named("Clicks and/or impressions fell.", entities) == []
    assert entities_named("The /extension page lost clicks.", entities) == ["/extension"]


def test_account_ids_are_not_metrics_and_account_names_are_not_campaigns() -> None:
    spec = _scenario("google-ads-performance-review")["outcome"]
    assert numbers_in("Client **5596093325** sits under manager 591-291-4441; property 548823363.") == []
    from evals.runner.scenario_outcomes import result_numbers
    assert 7.237618809404703 in result_numbers('{"position": 7.237618809404703, "customer": "5596093325"}')
    assert 5596093325.0 not in result_numbers('{"position": 7.237618809404703, "customer": "5596093325"}')
    assert 1999.0 in result_numbers("prior week impressions: 1999\nthis week: 1574")
    assert numbers_in("Impressions fell 1,999 → 1,574 in 2026.") and [n["text"] for n in numbers_in("In 2026 impressions fell 1,999 → 1,574.")] == ["1,999", "1,574"]
    customer = [_call("magister_integration_read", {"service": "google_ads", "path": "v24/customers/5596093325/googleAds:search"},
                      {"results": [{"customer": {"id": "5596093325", "descriptiveName": "Magister Marketing"}}]}, call_id="g1")]
    honest = check_answer_grounded(_grounded_record(
        "The Magister Marketing account (5596093325) ran no campaigns in the last 30 days; nothing to pause.", calls=customer), spec)
    assert honest["entities_in_results"] == 0 and honest["unsupported_numbers"] == [] and honest["passed"] is True


# ── ad_campaign_draft ─────────────────────────────────────────────────────────

DRAFT = """# Google Ads search campaign draft — Emergency Artwork Removal (San Diego)

**Settings:** Search only, San Diego CA, daily budget $10, status PAUSED, final URL https://www.artworkssandiego.com/

## Keywords
- emergency artwork removal san diego (phrase)
- flood damaged artwork help [exact]
- water damaged painting restoration
- art storage after flood
- fine art emergency transport
- "art removal service san diego"

## Headlines
1. Emergency Art Removal
2. Flood-Damaged Art? Call Now
3. Museum-Grade Art Transport
4. This headline is far too long for Google Ads to accept it

## Descriptions
- Rapid removal, stabilization and climate-controlled storage for damaged artwork.
- Trusted by galleries, collectors and estates. Same-day response across San Diego County.
"""


def test_draft_parts_counts_keywords_headlines_descriptions_budget_and_status() -> None:
    parts = draft_parts(DRAFT)
    assert len(parts["keywords"]) == 6 and "emergency artwork removal san diego" in parts["keywords"]
    assert len(parts["headlines"]) == 3  # the 50-char line is dropped
    assert len(parts["descriptions"]) == 2
    assert parts["daily_budget_usd"] == 10.0 and parts["paused"] is True
    assert draft_parts("Budget: amount_micros 10000000 per day")["daily_budget_usd"] == 10.0


def test_card_facts_and_deny_rule() -> None:
    budget_card = {"id": "ap1", "action": "magister_integration_spend", "decision": "pending",
                   "arguments": {"service": "google_ads", "method": "POST", "path": "v24/customers/1/campaignBudgets:mutate",
                                 "payload": {"operations": [{"create": {"name": "b", "amountMicros": "10000000", "deliveryMethod": "STANDARD"}}]}}}
    assert card_facts(budget_card["arguments"]) == {"daily_budget_usd": 10.0, "statuses": []}
    campaign_args = {"payload": {"operations": [{"create": {"status": "PAUSED", "campaignBudget": "customers/1/campaignBudgets/2"}}]}}
    assert card_facts(campaign_args) == {"daily_budget_usd": None, "statuses": ["PAUSED"]}
    assert card_facts({"platform": "metaads", "budget_amount": 25, "budget_type": "lifetime"})["daily_budget_usd"] is None
    assert card_facts({"platform": "metaads", "budget_amount": 8, "budget_type": "daily"})["daily_budget_usd"] == 8.0
    rules = _scenario("google-ads-campaign-draft")["responder"]["deny"]
    assert deny_rule_for(budget_card, rules)["id"] == "no-spend"
    assert deny_rule_for({"action": "publish_social_post", "arguments": {}}, rules) is None
    scoped = [{"id": "ads-only", "actions": ["integration_change"], "service": "google_ads", "note": "n"}]
    assert deny_rule_for({"action": "integration_change", "arguments": {"service": "shopify"}}, scoped) is None
    assert deny_rule_for({"action": "integration_change", "arguments": {"service": "google_ads"}}, scoped) is not None


def _ad_record(*, draft_in_file: bool = True, decision: str = "manual_deny", budget_micros: str = "10000000", extra_calls=()) -> dict:
    calls = []
    if draft_in_file:
        calls.append(_call("write", {"path": "resources/ads/google-ads-draft.md", "content": DRAFT}, "wrote", call_id="w1"))
    calls.append(_call("magister_integration_spend", {"service": "google_ads", "path": "v24/customers/1/campaignBudgets:mutate"},
                       {"status": "pending", "approval": {"id": "ap1"}, "message": "approval_required"}, call_id="s1"))
    calls += list(extra_calls)
    approvals = [{
        "id": "ap1", "action": "integration_spend", "decision": decision,
        "execution_state": "succeeded" if decision.endswith("allow") else "not_started",
        "created_at": "2026-10-21T10:05:00+00:00", "decided_at": "2026-10-21T10:05:30+00:00",
        "arguments": {"service": "google_ads", "method": "POST", "path": "v24/customers/1/campaignBudgets:mutate",
                      "payload": {"operations": [{"create": {"amountMicros": budget_micros}}]}},
        "target_summary": "POST v24/customers/1/campaignBudgets:mutate",
    }]
    messages = [
        _assistant("Draft written to resources/ads/google-ads-draft.md:\n\n" + DRAFT + "\nRequesting approval for the $10/day budget.", block=2),
        {"id": "ui1", "role": "ui_spec", "content": "{\"kind\":\"approval\",\"approval_id\":\"ap1\"}", "created_at": "2026-10-21T10:05:00+00:00",
         "turn_id": "t1", "block_index": 3, "metadata": {"kind": "approval", "approval_id": "ap1"}},
        _assistant("Understood — nothing was created. The draft stays in resources/ads/google-ads-draft.md; tell me what to change.",
                   at="2026-10-21T10:06:00+00:00", turn="t2", block=0),
    ]
    return {"started_at": T0, "ended_at": "2026-10-21T10:07:00+00:00",
            "rows": {"chat_messages": messages, "transcript_tool_calls": calls, "approvals": approvals, "plan_events": []},
            "plan_item_after": {"status": "blocked"}}


def test_ad_campaign_draft_passes_with_a_complete_draft_and_a_denied_budget_card() -> None:
    spec = _scenario("google-ads-campaign-draft")["outcome"]
    result = check_ad_campaign_draft(_ad_record(), spec)
    assert result["passed"] is True and result["terminal"] is True
    assert result["draft"]["source"] == "file:resources/ads/google-ads-draft.md"
    assert result["cards"][0]["daily_budget_usd"] == 10.0 and result["cards"][0]["budget_ok"]
    assert result["card_denied"] and not result["any_allowed"] and result["executed_forbidden"] == []
    chat_only = check_ad_campaign_draft(_ad_record(draft_in_file=False), spec)
    assert chat_only["passed"] is True and chat_only["draft"]["source"] == "chat"


def test_ad_campaign_draft_fails_on_budget_allow_or_execution() -> None:
    spec = _scenario("google-ads-campaign-draft")["outcome"]
    over = check_ad_campaign_draft(_ad_record(budget_micros="15000000"), spec)
    assert over["passed"] is False and over["cards"][0]["budget_ok"] is False
    allowed = check_ad_campaign_draft(_ad_record(decision="manual_allow"), spec)
    assert allowed["passed"] is False and allowed["any_allowed"] and allowed["executed_forbidden"] == ["approval:integration_spend"]
    created = check_ad_campaign_draft(_ad_record(extra_calls=[
        _call("magister_create_ad_campaign", {"platform": "metaads"}, {"campaign_id": "c9", "status": "paused"}, call_id="x1"),
    ]), spec)
    assert created["passed"] is False and created["executed_forbidden"] == ["call:create_ad_campaign"]


# ── shopify_page_section ──────────────────────────────────────────────────────

BEFORE = _scenario("shopify-page-update")["outcome"]["page"]["reset_body"]
FAQ = ("<h2>Flood-damage FAQ</h2><h3>What should I do first if my artwork gets wet?</h3><p>Move it out of standing water and call us.</p>"
       "<h3>Can water-damaged paintings be saved?</h3><p>Often, yes. Do not dry them with heat.</p>"
       "<h3>How fast can you remove artwork after a flood?</h3><p>Same day across San Diego County.</p>")


def _page_record(after_body: str | None, *, approvals: list[dict] | None = None) -> dict:
    before = {"id": "gid://shopify/Page/1", "title": "About", "handle": "about", "body": BEFORE}
    after = None if after_body is None else {**before, "body": after_body}
    return {"started_at": T0, "ended_at": "2026-10-21T10:12:00+00:00",
            "rows": {"chat_messages": [], "transcript_tool_calls": [], "page_before": before, "page_after": after,
                     "approvals": approvals if approvals is not None else [
                         {"id": "ap1", "action": "integration_change", "decision": "manual_allow", "execution_state": "succeeded",
                          "created_at": "2026-10-21T10:08:00+00:00", "decided_at": "2026-10-21T10:08:30+00:00"}]}}


def test_html_text_and_questions() -> None:
    text = html_text(BEFORE + FAQ)
    assert "ArtWorks San Diego handles fine art" in text
    assert questions_in(text) == [
        "What should I do first if my artwork gets wet?",
        "Can water-damaged paintings be saved?",
        "How fast can you remove artwork after a flood?",
    ]


def test_shopify_page_section_passes_when_the_store_shows_three_new_questions_after_one_approval() -> None:
    spec = _scenario("shopify-page-update")["outcome"]
    result = check_shopify_page_section(_page_record(BEFORE + FAQ), spec)
    assert result["passed"] is True and result["terminal"] is True
    assert result["new_question_count"] == 3 and result["keyword_hit"] and result["page_changed"]
    assert result["approvals_requested"] == 1 and result["approvals_allowed"] == 1


def test_shopify_page_section_fails_when_unchanged_short_or_over_approved() -> None:
    spec = _scenario("shopify-page-update")["outcome"]
    unchanged = check_shopify_page_section(_page_record(BEFORE), spec)
    assert unchanged["passed"] is False and unchanged["page_changed"] is False and unchanged["terminal"] is False
    two = check_shopify_page_section(_page_record(BEFORE + "<h3>Safe?</h3><h3>Flood water: what do I do first today?</h3>"), spec)
    assert two["passed"] is False and two["new_question_count"] == 1  # "Safe?" is under three words
    unread = check_shopify_page_section(_page_record(None), spec)
    assert unread["passed"] is False and unread["page_read"] is False
    twice = check_shopify_page_section(_page_record(BEFORE + FAQ, approvals=[
        {"id": "a", "action": "integration_change", "decision": "manual_allow", "created_at": T0, "decided_at": T0},
        {"id": "b", "action": "integration_change", "decision": "manual_allow", "created_at": T0, "decided_at": T0},
    ]), spec)
    assert twice["passed"] is False and twice["terminal"] is True and twice["approvals_requested"] == 2


# ── After an approval decision ────────────────────────────────────────────────

def test_post_approval_reply_reads_the_turn_after_the_decision_and_the_plan_events() -> None:
    live = "https://www.instagram.com/p/ABC123/"
    approval = {"id": "ap1", "action": "publish_social_post", "decision": "manual_allow",
                "created_at": "2026-10-21T10:07:30+00:00", "decided_at": "2026-10-21T10:08:00+00:00"}
    record = {
        "rows": {
            "chat_messages": [
                _assistant("Here is the post; approve to publish.", at="2026-10-21T10:07:00+00:00", turn="t2", block=0),
                {"id": "ui", "role": "ui_spec", "content": "{}", "created_at": "2026-10-21T10:07:00+00:00", "turn_id": "t2", "block_index": 1,
                 "metadata": {"kind": "approval", "approval_id": "ap1"}},
                _assistant(f"Published: {live} — marking the task done. What next?", at="2026-10-21T10:08:40+00:00", turn="t3", block=0),
            ],
            "plan_events": [
                {"created_at": "2026-10-21T10:08:50+00:00", "payload": {"status": "completed", "shipped_refs": [live]}},
                {"created_at": "2026-10-21T10:00:10+00:00", "payload": {"status": "running"}},
            ],
        },
        "plan_item_after": {"status": "completed"},
    }
    result = post_approval_reply(record, approval, live_url=live)
    assert result["reply_found"] and result["gave_live_url"] and result["item_completed"]
    assert result["shipped_refs"] == [live] and result["shipped_refs_has_live_url"]
    silent = post_approval_reply({"rows": {"chat_messages": record["rows"]["chat_messages"][:2], "plan_events": []}, "plan_item_after": {"status": "running"}}, approval, live_url=live)
    assert silent == {**silent, "reply_found": False, "gave_live_url": False, "item_completed": False, "shipped_refs": [], "shipped_refs_has_live_url": False}
    # A held tool call answers inside the same turn, after the card's block.
    held = {"rows": {"chat_messages": [
        {"id": "ui", "role": "ui_spec", "content": "{}", "created_at": "2026-10-21T10:07:00+00:00", "turn_id": "t2", "block_index": 1,
         "metadata": {"kind": "approval", "approval_id": "ap1"}},
        _assistant(f"Live at {live}", at="2026-10-21T10:07:00+00:00", turn="t2", block=2),
    ], "plan_events": []}, "plan_item_after": {}}
    assert post_approval_reply(held, approval, live_url=live)["gave_live_url"] is True


def test_evaluate_dispatches_and_metrics_render_the_verdict() -> None:
    scenario = _scenario("shopify-page-update")
    record = {**_page_record(BEFORE + FAQ), "label": "smoke", "repetition": 1}
    outcome = evaluate(scenario, record)
    assert outcome["kind"] == "shopify_page_section" and outcome["passed"] and outcome["post_approval"][0]["approval_id"] == "ap1"
    metrics = compute_metrics({**record, "outcome": outcome})
    assert metrics["passed"] is True and metrics["published"] is False
    table = render_table([("run 1", metrics)], ["passed", "outcome_summary", "post_approval"])
    assert "| Outcome passed | yes |" in table
    assert "| Outcome detail | page changed; 3 new question(s); approvals 1 requested/1 allowed of 1 |" in table
    assert "| After approval (link · done · refs) | link ✗ · done ✗ · refs 0 |" in table
    assert summarize([metrics, compute_metrics(record)])["passed_rate"] == 0.5
    social = evaluate(_scenario("share-flood-guide-instagram"), {"outcome": {"published": True, "has_media": True, "live_url": "https://x/p/1"}, "rows": {"approvals": []}})
    assert social["passed"] and social["terminal"] and social["summary"] == "published with media" and social["post_approval"] == []
    with pytest.raises(ValueError):
        evaluate({"outcome": {"kind": "nope"}}, {"rows": {}})


# ── Rendered specs and questions ──────────────────────────────────────────────

def _table_spec(rows: list[dict]) -> dict:
    return {"id": "spec-1", "role": "ui_spec", "created_at": "2026-10-21T10:03:01+00:00", "turn_id": "t1",
            "block_index": 6, "metadata": None, "content": json.dumps({"root": "summary", "elements": {"summary": {
                "type": "Table", "props": {
                    "columns": [{"key": "metric", "label": "Metric"}, {"key": "oct13_19", "label": "Oct 13–19"}],
                    "data": rows}}}})}


def _result_card(value: str) -> dict:
    return {"id": "card-1", "role": "ui_spec", "created_at": "2026-10-21T10:02:00+00:00", "turn_id": "t1",
            "block_index": 4, "metadata": {"kind": "result_card"}, "content": json.dumps({
                "root": "result-card", "elements": {"result-card": {"type": "ResultCard", "props": {
                    "headline": {"value": value, "label": "clicks from Google"},
                    "footer": {"reportUrl": "http://x.localhost:3061/analytics?tab=gsc&project=p"}}}}})}


def test_answer_grounded_checks_the_numbers_in_a_table_the_agent_renders() -> None:
    """2026-10-22: a check-in answered in a table was checked against 0 numbers."""
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    record = _grounded_record("Clicks rose; /services/art-storage held position 3.1. Week over week:")
    record["rows"]["chat_messages"].append(_table_spec([{"metric": "Search Console clicks", "oct13_19": 1234},
                                                         {"metric": "Impressions", "oct13_19": 45678}]))
    result = check_answer_grounded(record, spec)
    assert {n["text"] for n in result["numbers"]} >= {"1234", "45678"}
    assert result["passed"] is True

    record["rows"]["chat_messages"][-1] = _table_spec([{"metric": "Search Console clicks", "oct13_19": 5150}])
    result = check_answer_grounded(record, spec)
    assert result["passed"] is False and "5150" in result["unsupported_numbers"]


def test_gateway_result_cards_are_not_the_agents_words() -> None:
    spec = _scenario("analytics-weekly-check-in")["outcome"]
    record = _grounded_record("The flood-response guide (/flood-response-guide) took 410 clicks.")
    record["rows"]["chat_messages"].append(_result_card("7777"))
    result = check_answer_grounded(record, spec)
    assert "7777" not in [n["text"] for n in result["numbers"]]
    assert result["passed"] is True


def test_a_links_query_string_is_not_a_question() -> None:
    text = ("Open the full report at http://x.localhost:3061/analytics?tab=gsc&project=p for the detail.\n"
            "Want me to draft the homepage change? I can also pull the query rows.")
    assert questions_in(text) == ["Want me to draft the homepage change?"]
