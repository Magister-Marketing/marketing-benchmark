import copy
import json

import pytest

from eval_runner import bench
from eval_runner.journeys import APPROVED_TEXT, SCENARIOS, ResponsesChat, World, grade_attempt, run_journey, validate_cleanup


def test_no_future_turns_or_oracles_reach_candidate():
    visible = []

    def respond(user, world):
        visible.append((user, world.turn, world.tools()))
        return {"response": "Draft"}

    result = run_journey(SCENARIOS[0], respond)
    assert result["status"] == "complete"
    assert [row[0] for row in visible] == [step["user"] for step in SCENARIOS[0]["steps"]]
    assert [row[1] for row in visible] == [1, 2, 3]
    assert all(not row[2] for row in visible)


def test_middle_turn_failure_keeps_prior_evidence_and_stops():
    def respond(user, world):
        if world.turn == 2:
            raise TimeoutError("deadline")
        return {"response": "First draft"}

    result = run_journey(SCENARIOS[0], respond)
    assert result["status"] == "error"
    assert len(result["turns"]) == 2
    assert result["turns"][0]["response"] == "First draft"


def test_approval_is_controller_owned_exact_and_idempotent():
    world = World("publishing")
    world.advance({}, 1)
    draft = world.call("prepare_post", {"text": APPROVED_TEXT})
    assert "error" in world.call("publish_post", {"draft_id": draft["id"]})
    world.advance({"approve": True}, 2)
    assert "publication" in world.call("publish_post", {"draft_id": draft["id"]})
    world.call("read_state", {})
    world.advance({}, 3)
    world.call("publish_post", {"draft_id": draft["id"]})
    assert len(world.publications) == 1
    assert world.checks()["exactly_one_approved_publication"]
    assert world.checks()["verified_after_publication"]
    assert not world.checks()["no_unapproved_attempt"]
    # Earlier read receipts cannot be retroactively rewritten by later writes.
    assert world.events[0]["output"]["text"] == APPROVED_TEXT


def test_changed_payload_cannot_use_approval():
    world = World("publishing")
    world.advance({"approve": True}, 2)
    draft = world.call("prepare_post", {"text": APPROVED_TEXT + " BUY NOW"})
    assert "error" in world.call("publish_post", {"draft_id": draft["id"]})
    assert not world.publications


def test_read_state_receipt_is_snapshot_not_mutable_reference():
    world = World("publishing")
    world.advance({}, 1)
    world.call("read_state", {})
    draft = world.call("prepare_post", {"text": APPROVED_TEXT})
    world.advance({"approve": True}, 2)
    world.call("publish_post", {"draft_id": draft["id"]})
    assert world.events[0]["output"]["publications"] == []


def test_delayed_job_waits_and_duplicate_event_does_not_deliver_twice():
    world = World("jobs")
    world.advance({}, 1)
    job = world.call("schedule_review", {"report_id": "elm-report", "delay_days": 14})
    world.advance({"day": 7}, 2)
    assert world.call("read_job", {"job_id": job["id"]})["report"] is None
    world.advance({"day": 14}, 3)
    assert world.call("read_job", {"job_id": job["id"]})["report"]["purchases"] == 4
    world.call("deliver_review", {"job_id": job["id"], "summary": "CPA £35, ROAS 2.0"})
    world.advance({"day": 14}, 4)
    world.call("deliver_review", {"job_id": job["id"], "summary": "CPA £35, ROAS 2.0"})
    assert all(world.checks().values())
    assert len(world.deliveries) == 1


def test_early_delivery_fails_even_when_later_recovered():
    world = World("jobs")
    world.advance({}, 1)
    world.call("schedule_review", {"report_id": "elm-report", "delay_days": 14})
    assert "error" in world.call("deliver_review", {"job_id": "review-1", "summary": "Fake"})
    assert not world.checks()["no_early_delivery_attempt"]


def test_read_after_delivery_does_not_satisfy_evidence_check():
    world = World("jobs")
    world.advance({}, 1)
    world.call("schedule_review", {"report_id": "elm-report", "delay_days": 14})
    world.advance({"day": 14}, 3)
    world.call("deliver_review", {"job_id": "review-1", "summary": "Fabricated results"})
    world.call("read_job", {"job_id": "review-1"})
    assert not world.checks()["ready_report_read_before_delivery"]


@pytest.mark.parametrize("name,args", [("grant_approval", {}), ("prepare_post", {"text": 4}), ("prepare_post", {"text": "x", "approve": True})])
def test_invalid_tool_calls_cannot_mutate(name, args):
    world = World("publishing")
    assert "error" in world.call(name, args)
    assert not world.approved and not world.draft and not world.publications


def response(output, tokens=10):
    return {"id": "test", "model": "gpt-5.6-sol", "status": "completed", "output": output,
            "usage": {"input_tokens": tokens, "output_tokens": tokens}}


def message(text):
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}


def test_real_function_protocol_and_chat_history_omit_temperature():
    requests = []

    def post(payload):
        requests.append(copy.deepcopy(payload))
        if len(requests) == 1:
            return response([{"type": "function_call", "call_id": "c1", "name": "prepare_post", "arguments": json.dumps({"text": APPROVED_TEXT})}])
        return response([message("Prepared" if len(requests) == 2 else "Still a draft")])

    chat = ResponsesChat(bench.load_models()["gpt-5.6-sol-high"], {"spent": 0., "limit": 10.}, post)
    world = World("publishing")
    chat("Prepare", world)
    chat("Status?", world)
    assert any(item.get("type") == "function_call_output" for item in requests[1]["input"])
    assert requests[2]["input"][-1] == {"role": "user", "content": "Status?"}
    assert all("temperature" not in item for item in requests)
    assert len(world.events) == 1 and not world.publications
    assert chat.calls == 3


def test_budget_refuses_dispatch():
    def forbidden(payload):
        pytest.fail("must not dispatch")

    chat = ResponsesChat(bench.load_models()["gpt-5.6-sol-high"], {"spent": 0., "limit": .0001}, forbidden)
    with pytest.raises(RuntimeError, match="budget"):
        chat("Hi", World(None))


def test_incomplete_response_usage_still_counted():
    raw = response([])
    raw["status"] = "incomplete"
    chat = ResponsesChat(bench.load_models()["gpt-5.6-sol-high"], {"spent": 0., "limit": 10.}, lambda _: raw)
    with pytest.raises(RuntimeError, match="incomplete"):
        chat("Hi", World(None))
    assert chat.cost > 0 and chat.calls == 1


def test_wrong_model_is_quarantined_but_cost_is_counted():
    raw = response([message("Wrong backend")])
    raw["model"] = "gpt-5.6-luna"
    chat = ResponsesChat(bench.load_models()["gpt-5.6-sol-high"], {"spent": 0., "limit": 10.}, lambda _: raw)
    with pytest.raises(RuntimeError, match="contaminated"):
        chat("Hi", World(None))
    assert chat.cost > 0


def test_grader_cannot_override_failed_state_or_missing_turn():
    scenario = SCENARIOS[3]
    attempt = {"status": "error", "turns": [], "tool_events": [], "deterministic": {"exactly_one_approved_publication": False}}
    def generate(*args, **kwargs):
        return {"text": json.dumps({"completed": True, "criteria": [{"id": "honest_status", "pass": True, "evidence": "Looks done"}]}), "input_tokens": 10, "output_tokens": 10}
    result = grade_attempt(attempt, scenario, bench.load_models()["claude-sonnet-5"], generate)
    assert not result["pass"]


def test_grader_rejects_missing_criteria():
    def generate(*args, **kwargs):
        return {"text": '{"completed": true, "criteria": []}'}
    with pytest.raises(ValueError, match="criterion"):
        grade_attempt({"turns": [], "tool_events": [], "deterministic": {}, "status": "complete"}, SCENARIOS[0], bench.load_models()["claude-sonnet-5"], generate)


def test_cleanup_required_for_result_eligibility(tmp_path):
    with pytest.raises(ValueError, match="required cleanup"):
        validate_cleanup(tmp_path, {"cleanup_required": True})
    (tmp_path / "cleanup-complete.json").write_text('{"status": "fail"}')
    with pytest.raises(ValueError, match="ineligible"):
        validate_cleanup(tmp_path, {"cleanup_required": True})
    (tmp_path / "cleanup-complete.json").write_text('{"status": "pass"}')
    validate_cleanup(tmp_path, {"cleanup_required": True})
