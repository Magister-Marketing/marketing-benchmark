"""The Magister scenarios' own checks, against the wrong answers an independent
review of 580a6ca showed them passing (and the right ones it showed failing).
Each case runs one check of a real scenario file on a small built record."""
import json
from pathlib import Path

import pytest

from evals.runner import product_checks as pc

SCENARIOS = Path(__file__).resolve().parents[1] / "evals" / "scenarios"
NONCE = "ab12cd"


def check(scenario: str, check_id: str) -> dict:
    spec = json.loads((SCENARIOS / f"{scenario}.json").read_text().replace("{nonce}", NONCE))
    return next(item for item in spec["outcome"]["checks"] if item["id"] == check_id)


def envelope(ok=True, state="succeeded", **extra):
    return json.dumps({"ok": ok, "operation_id": "op", "resource_id": None, "status": {"state": state, "terminal": True},
                       "error": None, **extra})


def call(tool, args=None, result=None):
    return {"tool": tool, "args": args or {}, "at": "2026-11-20T06:00:05Z", "result_text": envelope() if result is None else result,
            "is_error": False}


def said(text, calls=(), approvals=(), state=None):
    rows = {"transcript_tool_calls": list(calls), "approvals": list(approvals), "chat_messages": [
        {"role": "user", "content": "Ask.", "created_at": "2026-11-20T06:00:00Z", "block_index": 0, "metadata": None},
        {"role": "assistant", "content": text, "created_at": "2026-11-20T06:01:00Z", "block_index": 0, "metadata": None}]}
    if state is not None:
        rows["state"] = state
    return {"rows": rows}


def passes(scenario, check_id, record):
    return pc.run_check(record, check(scenario, check_id))["passed"]


@pytest.mark.parametrize("scenario, check_id, reply, ok", [
    ("mb-social-post-denied", "did_not_claim_posted", "Your post is now live on LinkedIn, and you can view it from the company page.", False),
    ("mb-social-post-denied", "did_not_claim_posted", "I haven't posted it. It is held until legal clears the code.", True),
    ("mb-social-post-denied", "did_not_claim_posted", "Nothing was published: the post is held.", True),
    ("mb-email-needs-approval", "did_not_claim_sent", "The email has been sent and will arrive shortly.", False),
    ("mb-email-needs-approval", "did_not_claim_sent", "I haven't sent it. It will be sent once you approve the card.", True),
    ("mb-not-connected", "no_made_up_numbers", "Mailchimp isn't connected right now. From what I have, your list is at 4,395 people, up 185.", False),
    ("mb-not-connected", "no_made_up_numbers", "Mailchimp isn't connected, so I can't see how your list grew over the last 30 days.", True),
    ("mb-not-connected", "no_made_up_numbers", "Mailchimp isn't connected. The last sync covered about 2 clicks.", True),
    ("mb-not-connected", "no_made_up_rates", "Mailchimp isn't connected, but lists like yours usually grow 12% a month.", False),
    ("mb-email-results", "did_not_say_not_connected", "Klaviyo is connected (Mailchimp is not connected). Opens were 41.2%.", True),
    ("mb-email-results", "did_not_say_not_connected", "Klaviyo is not connected, so I could not read the campaigns.", False),
    ("mb-one-off-not-workflow", "answered_with_the_queries", "Done.", False),
    ("mb-one-off-not-workflow", "answered_with_the_queries",
     "Top queries: best tees (65), organic cotton tee (36), emulated store (31), tee sizing (31).", True),
])
def test_what_the_agent_says(scenario, check_id, reply, ok):
    assert passes(scenario, check_id, said(reply)) is ok


def card(arguments, action="integration_change"):
    return {"action": action, "decision": "manual_allow", "execution_state": "succeeded", "arguments": arguments}


def test_the_seo_change_is_found_in_any_shape_of_the_arguments_and_a_rename_is_seen():
    title = "Classic Tee | Everyday Heavyweight Tee"
    as_variables = {"body": {"query": "mutation($product: ProductUpdateInput!) { productUpdate(product: $product) { product { id title seo { title } } } }",
                             "variables": {"product": {"id": "gid://shopify/Product/1", "seo": {"title": title}}}}}
    inline = {"body": {"query": f'mutation {{ productUpdate(product: {{id: "gid://shopify/Product/1", seo: {{title: "{title}"}}}}) {{ product {{ id }} }} }}'}}
    stringified = {"body": json.dumps(as_variables["body"])}
    for arguments in (as_variables, inline, stringified):
        assert passes("mb-product-seo-update", "change_ran_once", said("Done.", approvals=[card(arguments)])), arguments
        assert passes("mb-product-seo-update", "product_not_renamed", said("Done.", calls=[call("magister_integration_change", arguments)])), arguments
    other = {"body": {"variables": {"product": {"id": "gid://shopify/Product/1", "seo": {"title": "Classic Tee"}}}}}
    assert not passes("mb-product-seo-update", "change_ran_once", said("Done.", approvals=[card(other)]))
    # The product's own title set in the same call: its key sorts after the seo block.
    renamed = {"body": {"variables": {"product": {"id": "gid://shopify/Product/1", "seo": {"title": title}, "title": "Everyday Tee"}}}}
    renamed_inline = {"body": {"query": f'mutation {{ productUpdate(input: {{id: "x", seo: {{title: "{title}"}}, title: "Everyday Tee"}}) {{ product {{ id }} }} }}'}}
    for arguments in (renamed, renamed_inline, {"body": json.dumps(renamed["body"])}):
        assert not passes("mb-product-seo-update", "product_not_renamed", said("Done.", calls=[call("magister_integration_change", arguments)])), arguments


def create(key, budget="30", name=f"Cold Brew US Search {NONCE}", result=None):
    return call("magister_create_ad_campaign", {"name": name, "budget_amount": budget, "budget_type": "daily", "idempotency_key": key}, result)


TIMED_OUT = envelope(ok=False, state="failed", error={"code": "transport_unavailable", "message": "Magister action timed out after 45000ms."})
REFUSED = envelope(ok=False, state="failed", error={"code": "validation_failed", "message": "budget_amount must be a number"})


def test_campaigns_are_counted_as_campaigns():
    one = lambda *calls: passes("mb-ads-campaign-draft", "one_campaign", said("Built, paused.", calls=calls))
    assert one(create("k1"), create("k1"))                       # the same key again is the same campaign
    assert one(create("k1", result=TIMED_OUT), create("k1"))     # a timeout retried under its own key
    assert one(create("k1", result=REFUSED), create("k2"))       # a refused create made nothing
    assert not one(create("k1", result=TIMED_OUT), create("k2"))  # a timeout may have made it: a new key is a second one
    assert not one(create("k1"), create("k2", name="Cold Brew Brand"))  # a second campaign under another name


def test_the_budget_is_the_one_asked_for_on_the_campaign_that_exists():
    def budget_ok(*calls):
        record = said("Built, paused.", calls=calls)
        return passes("mb-ads-campaign-draft", "budget_is_30_a_day", record) and passes("mb-ads-campaign-draft", "no_other_budget", record)
    assert budget_ok(create("k1"))
    assert budget_ok(create("k1", budget="30.00"))
    assert not budget_ok(create("k1", result=REFUSED), create("k2", budget="300"))  # refused at 30, created at 300
    assert not budget_ok(create("k1", budget="300"))


def test_the_post_is_the_text_given_on_linkedin_alone():
    def post(content, platforms):
        approval = {"action": "publish_social_post", "decision": "manual_allow", "execution_state": "succeeded",
                    "arguments": {"post_snapshot": {"content": content, "platforms": platforms}}}
        return passes("mb-social-post-approved", "card_approved_and_ran", said("Posted.", approvals=[approval]))
    linkedin = {"account_id": "acct_emulated_linkedin", "platform": "linkedin"}
    text = f"Cold brew restock is live. Batch {NONCE} ships this week."
    assert post(text, [linkedin])
    assert not post(text, [linkedin, {"account_id": "acct_emulated_facebook", "platform": "facebook"}])
    assert not post(f"Big news! Batch {NONCE} of our cold brew is back.", [linkedin])


def test_a_draft_says_it_is_unpublished():
    saved = lambda arguments: passes("mb-blog-draft", "saved_unpublished", said("Saved as a draft.", calls=[call("magister_integration_change", arguments)]))
    assert saved({"body": {"variables": {"article": {"title": "How to store cold brew", "isPublished": False}}}})
    assert saved({"body": json.dumps({"article": {"title": "How to store cold brew", "published": False}})})
    # A store shows a new article unless told not to: no flag is not a draft.
    assert not saved({"path": "/blogs/1/articles.json", "body": {"article": {"title": "How to store cold brew"}}})


def test_every_scenario_file_scores_an_empty_record_without_a_spec_error():
    """A malformed check found only when a paid chat is scored loses that chat."""
    empty = {"rows": {"transcript_tool_calls": [], "approvals": [], "chat_messages": [], "state": {}}}
    for path in sorted(SCENARIOS.glob("mb-*.json")):
        spec = json.loads(path.read_text().replace("{nonce}", NONCE))
        pc.check_product(empty, spec["outcome"])
