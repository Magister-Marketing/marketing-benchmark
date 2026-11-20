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
