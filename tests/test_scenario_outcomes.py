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


def test_entities_in_reads_nested_keys_and_non_json_results() -> None:
    calls = [_call("magister_read_analytics_breakdown", {"source": "gsc"}, GSC_PAGES), _call("x", {}, '"query": "art storage san diego" and more')]
    found = entities_in(calls, ["keys", "page", "query"])
    assert "https://www.artworkssandiego.com/flood-response-guide" in found and "/services/art-storage" in found
    assert "art storage san diego" in found


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
