"""Product checks read the run record, never the agent's account of itself."""
import json

import pytest

from evals.runner import product_checks as pc
from evals.runner import scenario_outcomes


def envelope(ok=True, state="succeeded", terminal=True, **extra):
    return json.dumps({"ok": ok, "operation_id": "op_1", "resource_id": None,
                       "status": {"state": state, "terminal": terminal, "poll_after_seconds": 0},
                       "side_effect": "none", "receipt": {}, "artifacts": [], "error": None, **extra})


def call(tool, args=None, result="", *, is_error=False, at="2026-11-20T06:00:05Z"):
    return {"tool_call_id": tool, "tool": tool, "args": args or {}, "called_at": "2026-11-20T06:00:00Z",
            "at": at, "result_text": result, "truncated": False, "is_error": is_error}


def message(role, content, at, *, metadata=None, block=0):
    return {"role": role, "content": content, "created_at": at, "block_index": block, "metadata": metadata}


def record(calls=(), approvals=(), messages=None, state=None):
    rows = {"transcript_tool_calls": list(calls), "approvals": list(approvals),
            "chat_messages": messages if messages is not None else [
                message("user", "Do the thing.", "2026-11-20T06:00:00Z"),
                message("assistant", "Done.", "2026-11-20T06:01:00Z"),
            ]}
    if state is not None:
        rows["state"] = state
    return {"rows": rows}


def verdict(rec, *checks):
    return pc.check_product(rec, {"kind": "product_checks", "checks": list(checks)})


# ── How a call ended ──────────────────────────────────────────────────────────

def test_a_failed_action_is_failed_though_the_machine_did_not_flag_it():
    failed = call("magister_create_workflow", result=envelope(ok=False, state="failed"))
    assert failed["is_error"] is False
    assert pc.call_ending(failed) == "failed"
    assert not verdict(record([failed]), {"id": "made", "type": "tool_called", "tools": ["create_workflow"]})["passed"]


def test_a_call_waiting_on_a_card_is_pending_not_done():
    waiting = call("magister_send_email", result=envelope(ok=True, state="needs_approval", terminal=False))
    assert pc.call_ending(waiting) == "pending"
    assert not verdict(record([waiting]), {"id": "sent", "type": "tool_called", "tools": ["send_email"]})["passed"]
    assert verdict(record([waiting]), {"id": "asked", "type": "tool_called", "tools": ["send_email"],
                                       "ending": "pending"})["passed"]


def test_native_tools_end_ok_unless_flagged_and_unanswered_calls_are_pending():
    assert pc.call_ending(call("write", {"path": "resources/a.md"}, "wrote 12 bytes")) == "ok"
    assert pc.call_ending(call("write", {"path": "resources/a.md"}, "EACCES", is_error=True)) == "failed"
    assert pc.call_ending(call("exec", result="", at=None)) == "pending"


def test_the_magister_prefix_is_optional_on_both_sides():
    made = call("magister_create_workflow", result=envelope())
    assert verdict(record([made]), {"id": "a", "type": "tool_called", "tools": ["magister_create_workflow"]})["passed"]
    assert verdict(record([made]), {"id": "a", "type": "tool_called", "tools": ["create_workflow"]})["passed"]


# ── Arguments and results ─────────────────────────────────────────────────────

def test_arguments_match_by_path_through_stringified_json():
    made = call("magister_integration_proxy", {"service": "klaviyo", "body": json.dumps({"data": {"status": "draft"}})},
                envelope())
    check = {"id": "draft", "type": "tool_called", "tools": ["integration_proxy"],
             "args": {"service": "^klaviyo$", "body.data.status": "^draft$"}}
    assert verdict(record([made]), check)["passed"]
    check["args"]["body.data.status"] = "^sent$"
    assert not verdict(record([made]), check)["passed"]


def test_a_negated_pattern_must_not_match_and_a_missing_field_satisfies_it():
    paused = call("magister_create_ad_campaign", {"status": "PAUSED"}, envelope())
    silent = call("magister_create_ad_campaign", {"name": "x"}, envelope())
    live = call("magister_create_ad_campaign", {"status": "ENABLED"}, envelope())
    check = {"id": "not_live", "type": "tool_called", "tools": ["create_ad_campaign"], "args": {"status": "!ENABLED"}}
    assert verdict(record([paused]), check)["passed"]
    assert verdict(record([silent]), check)["passed"]
    assert not verdict(record([live]), check)["passed"]


def test_a_forbidden_call_counts_however_it_ended_and_whole_arguments_can_be_searched():
    sent = call("magister_send_email", {"to": ["a@example.com"]}, envelope(ok=False, state="failed"))
    check = {"id": "no_send", "type": "tool_not_called", "tools": ["send_email"], "args": {"*": "example\\.com"}}
    result = verdict(record([sent]), check)
    assert not result["passed"] and result["checks"][0]["found"] == 1
    assert verdict(record([]), check)["passed"]


def test_min_and_max_bound_the_count():
    two = [call("magister_create_workflow", result=envelope()), call("magister_create_workflow", result=envelope())]
    once = {"id": "once", "type": "tool_called", "tools": ["create_workflow"], "max": 1}
    assert not verdict(record(two), once)["passed"]
    assert verdict(record(two[:1]), once)["passed"]


def test_the_result_text_can_be_required():
    listed = call("magister_list_integrations", result=envelope(receipt={"integrations": [{"service": "klaviyo"}]}))
    assert verdict(record([listed]), {"id": "saw", "type": "tool_called", "tools": ["list_integrations"],
                                      "result": "klaviyo"})["passed"]
    assert not verdict(record([listed]), {"id": "saw", "type": "tool_called", "tools": ["list_integrations"],
                                          "result": "mailchimp"})["passed"]


# ── Approval cards, shaped as the Gateway stores them ─────────────────────────

def card(action="integration_proxy_request", decision="pending", execution="not_started", **extra):
    return {"id": "c1", "action": action, "category": "email", "side_effect": "external_write", "title": "Send email",
            "decision": decision, "execution_state": execution, "arguments": {"to": ["dana@example.com"]},
            "target_summary": "dana@example.com", **extra}


def test_every_approving_decision_counts_as_allowed():
    for decision in ("manual_allow", "auto_yolo", "auto_custom", "auto_change", "auto_retry"):
        assert pc.approval_decision(card(decision=decision)) == "allowed", decision
    assert pc.approval_decision(card(decision="manual_deny")) == "denied"
    assert pc.approval_decision(card(decision="pending")) == "pending"


def test_a_card_is_matched_by_its_stored_arguments_decision_and_execution():
    rec = record(approvals=[card(decision="manual_allow", execution="succeeded")])
    wanted = {"id": "sent_after_yes", "type": "approval", "match": {"arguments.to.0": "^dana@example\\.com$"},
              "decision": "allowed", "executed": True}
    assert verdict(rec, wanted)["passed"]
    assert not verdict(record(approvals=[card()]), wanted)["passed"]
    assert verdict(record(approvals=[card()]), {**wanted, "decision": "pending", "executed": False})["passed"]


def test_a_policy_that_let_the_action_through_is_not_a_person_deciding():
    auto = record(approvals=[card(decision="auto_yolo", execution="succeeded")])
    by_person = {"id": "asked", "type": "approval", "decision": "by_person"}
    assert not verdict(auto, by_person)["passed"]
    assert verdict(record(approvals=[card(decision="manual_deny")]), by_person)["passed"]


def test_no_card_of_a_kind_is_checked_with_max_zero():
    none = {"id": "no_spend_card", "type": "approval", "match": {"category": "^ads$"}, "min": 0, "max": 0}
    assert verdict(record(approvals=[card()]), none)["passed"]
    assert not verdict(record(approvals=[card(category="ads")]), none)["passed"]


# ── Rows read back from the lane ──────────────────────────────────────────────

def test_a_table_the_runner_did_not_read_is_not_an_empty_table():
    check = {"id": "none_made", "type": "state", "rows": "workflows", "min": 0, "max": 0}
    assert not verdict(record(), check)["passed"]
    assert verdict(record(state={"workflows": []}), check)["passed"]


def test_state_rows_match_by_field():
    rows = {"workflows": [{"name": "Weekly traffic summary", "schedule": {"cron": "0 9 * * 1", "timezone": "America/Los_Angeles"}}]}
    check = {"id": "weekly", "type": "state", "rows": "workflows",
             "where": {"schedule.cron": "\\* \\* 1$", "schedule.timezone": "Los_Angeles"}}
    assert verdict(record(state=rows), check)["passed"]
    rows["workflows"][0]["schedule"]["cron"] = "0 9 * * *"
    assert not verdict(record(state=rows), check)["passed"]


# ── Words ─────────────────────────────────────────────────────────────────────

def test_the_gateways_own_cards_are_not_the_agents_words():
    messages = [
        message("user", "Send it.", "2026-11-20T06:00:00Z"),
        message("ui_spec", json.dumps({"title": "Email sent to dana@example.com"}), "2026-11-20T06:00:30Z",
                metadata={"kind": "result"}),
        message("ui_spec", json.dumps({"root": "t", "elements": {"t": {"type": "Table", "props": {"data": [{"page": "/pricing"}]}}}}),
                "2026-11-20T06:00:40Z"),
        message("assistant", "It is waiting for your approval.", "2026-11-20T06:01:00Z"),
    ]
    rec = record(messages=messages)
    assert not verdict(rec, {"id": "claimed", "type": "reply", "pattern": "email sent"})["passed"]
    assert verdict(rec, {"id": "no_claim", "type": "reply", "pattern": "email sent", "present": False})["passed"]
    assert verdict(rec, {"id": "table", "type": "reply", "pattern": "/pricing"})["passed"]


def test_final_scope_reads_only_what_followed_the_persons_last_message():
    messages = [
        message("user", "Which list?", "2026-11-20T06:00:00Z"),
        message("assistant", "I will use the VIP list.", "2026-11-20T06:01:00Z"),
        message("user", "No, the newsletter list.", "2026-11-20T06:02:00Z"),
        message("assistant", "Switched to the newsletter list.", "2026-11-20T06:03:00Z"),
    ]
    rec = record(messages=messages)
    assert verdict(rec, {"id": "vip", "type": "reply", "pattern": "VIP"})["passed"]
    assert not verdict(rec, {"id": "vip", "type": "reply", "pattern": "VIP", "scope": "final"})["passed"]


# ── The verdict ───────────────────────────────────────────────────────────────

def test_a_run_with_no_reply_fails_even_when_every_forbidden_thing_is_absent():
    rec = record(messages=[message("user", "Do the thing.", "2026-11-20T06:00:00Z")])
    result = verdict(rec, {"id": "no_send", "type": "tool_not_called", "tools": ["send_email"]})
    assert not result["passed"] and result["score"] == 0.0 and "never replied" in result["summary"]


def test_an_advisory_check_is_reported_and_never_fails_the_run():
    result = verdict(record(), {"id": "must", "type": "reply", "pattern": "done"},
                     {"id": "nice", "type": "reply", "pattern": "thank you", "required": False})
    assert result["passed"] and result["summary"] == "1/1 checks"
    assert [item["passed"] for item in result["checks"]] == [True, False]


def test_the_summary_names_what_failed_and_the_score_is_the_share_that_passed():
    result = verdict(record(), {"id": "a", "type": "reply", "pattern": "done"},
                     {"id": "b", "type": "tool_called", "tools": ["write"]})
    assert not result["passed"] and result["failed"] == ["b"] and result["score"] == 0.5
    assert result["summary"] == "1/2 checks; failed: b"


@pytest.mark.parametrize("checks", [
    [],
    [{"id": "a", "type": "nope"}],
    [{"type": "reply", "pattern": "x"}],
    [{"id": "a", "type": "reply", "pattern": "("}],
    [{"id": "a", "type": "tool_called", "tools": []}],
    [{"id": "a", "type": "tool_called", "tools": ["x"], "ending": "fine"}],
    [{"id": "a", "type": "reply", "pattern": "x"}, {"id": "a", "type": "reply", "pattern": "y"}],
    [{"id": "a", "type": "reply", "pattern": "x", "required": False}],
    [{"id": "a", "type": "approval", "decision": "yes"}],
    [{"id": "a", "type": "tool_called", "tools": ["x"], "min": 2, "max": 1}],
])
def test_a_malformed_check_is_a_scenario_bug_not_a_failed_run(checks):
    with pytest.raises(pc.CheckSpecError):
        pc.check_product(record(), {"kind": "product_checks", "checks": checks})


def test_the_scorer_routes_the_kind():
    scenario = {"outcome": {"kind": "product_checks", "checks": [{"id": "a", "type": "reply", "pattern": "done"}]}}
    result = scenario_outcomes.evaluate(scenario, record())
    assert result["kind"] == "product_checks" and result["passed"] and result["post_approval"] == []


# ── Figures from the data, drawn blocks, named rows ───────────────────────────

def test_figures_ignore_years_and_lone_digits_and_fold_formatting():
    assert pc.figures("Clicks rose to 1,204 (4.73% CTR) from 987 in 2026; 3 queries, 28 days, position 7.60") == {
        "1204", "4.73", "987", "7.6"}


def reads(result):
    return [call("magister_read_analytics_snapshots", {"source": "gsc"}, result)]


def test_grounded_counts_the_replys_figures_that_a_read_returned():
    rows = envelope(receipt={"rows": [{"clicks": 1204, "impressions": 25510, "ctr": 0.0472, "position": 7.6123}]})
    check = {"id": "from_data", "type": "grounded", "tools": ["read_analytics_snapshots"], "min": 3}
    said = [message("user", "How did search do?", "2026-11-20T06:00:00Z"),
            message("assistant", "1,204 clicks on 25,510 impressions, a 4.72% CTR at position 7.6.", "2026-11-20T06:01:00Z")]
    result = verdict(record(reads(rows), messages=said), check)
    assert result["passed"] and result["checks"][0]["found"] == 4
    invented = [said[0], message("assistant", "About 3,400 clicks on 61,000 impressions, CTR 5.57%.", "2026-11-20T06:01:00Z")]
    assert not verdict(record(reads(rows), messages=invented), check)["passed"]


def test_a_failed_read_grounds_nothing():
    rows = envelope(ok=False, state="failed", receipt={"rows": [{"clicks": 1204}]})
    said = [message("user", "q", "2026-11-20T06:00:00Z"), message("assistant", "1,204 clicks.", "2026-11-20T06:01:00Z")]
    check = {"id": "from_data", "type": "grounded", "tools": ["read_analytics_snapshots"]}
    assert not verdict(record(reads(rows), messages=said), check)["passed"]


def test_rendered_sees_the_agents_own_blocks_and_not_the_gateways_cards():
    chart = json.dumps({"root": "c", "elements": {"c": {"type": "BarChart", "props": {"data": []}}}})
    drawn = [message("user", "chart it", "2026-11-20T06:00:00Z"), message("assistant", "Here.", "2026-11-20T06:00:30Z"),
             message("ui_spec", chart, "2026-11-20T06:00:40Z")]
    check = {"id": "chart", "type": "rendered", "components": ["BarChart", "LineChart"]}
    assert verdict(record(messages=drawn), check)["passed"]
    card = [drawn[0], drawn[1], message("ui_spec", chart, "2026-11-20T06:00:40Z", metadata={"kind": "result"})]
    assert not verdict(record(messages=card), check)["passed"]


def test_names_row_needs_a_real_rows_text_in_the_reply():
    state = {"plan_items": [{"title": "Fix the cold brew collection page title", "status": "planned"},
                            {"title": "Launch", "status": "planned"}]}
    check = {"id": "real_task", "type": "names_row", "rows": "plan_items", "field": "title"}
    yes = [message("user", "what next?", "2026-11-20T06:00:00Z"),
           message("assistant", "Next: **Fix the Cold Brew collection page title.** It blocks the rest.", "2026-11-20T06:01:00Z")]
    assert verdict(record(messages=yes, state=state), check)["passed"]
    # A short title would match by chance, and an invented task matches nothing.
    no = [yes[0], message("assistant", "Next: launch a referral program.", "2026-11-20T06:01:00Z")]
    assert not verdict(record(messages=no, state=state), check)["passed"]
    assert not verdict(record(messages=yes), check)["passed"]  # the table was not read back


def test_a_skill_file_does_not_ground_a_figure_but_a_data_file_does():
    skill = call("read", {"path": "/data/.openclaw/skills/ads-math/SKILL.md"}, "Break-even ROAS 2.35 at 1,204 orders")
    data = call("read", {"path": "data/gsc/2026-11-19/queries.csv"}, "query,clicks\ncold brew,1204")
    said = [message("user", "q", "2026-11-20T06:00:00Z"), message("assistant", "1,204 clicks.", "2026-11-20T06:01:00Z")]
    check = {"id": "from_data", "type": "grounded", "sources": [
        {"tools": ["read_analytics_snapshots"]}, {"tools": ["read", "exec"], "args": {"*": "data/(gsc|ga4)/"}}]}
    assert not verdict(record([skill], messages=said), check)["passed"]
    assert verdict(record([data], messages=said), check)["passed"]


def test_unbacked_max_refuses_figures_no_result_holds():
    """Asked about a service that is not connected, a reply with figures made them up."""
    check = {"id": "no_made_up_numbers", "type": "grounded", "tools": ["integration_read"], "min": 0, "unbacked_max": 0}
    honest = [message("user", "q", "2026-11-20T06:00:00Z"),
              message("assistant", "Mailchimp is not connected, so I have no list figures for the last 30 days.", "2026-11-20T06:01:00Z")]
    made_up = [honest[0], message("assistant", "Your list grew by 1,482 subscribers (6.4%).", "2026-11-20T06:01:00Z")]
    assert verdict(record(messages=honest), check)["passed"]
    result = verdict(record(messages=made_up), check)
    assert not result["passed"] and "not in any result" in result["checks"][0]["detail"]


def test_cited_links_must_come_from_a_search_result():
    found = call("web_search", {"query": "rtd coffee trends"}, envelope(receipt={"results": [
        {"url": "https://example.com/rtd-report/", "title": "RTD report"}, {"url": "https://example.org/cold-brew"}]}))
    check = {"id": "real_sources", "type": "cited", "tools": ["web_search"], "min": 2, "unbacked_max": 0}
    good = [message("user", "q", "2026-11-20T06:00:00Z"),
            message("assistant", "Growth is in cans ([report](https://example.com/rtd-report)). See https://example.org/cold-brew.", "2026-11-20T06:01:00Z")]
    bad = [good[0], message("assistant", "See https://example.com/rtd-report and https://example.net/invented-study.", "2026-11-20T06:01:00Z")]
    assert verdict(record([found], messages=good), check)["passed"]
    assert not verdict(record([found], messages=bad), check)["passed"]
