"""Offline tests for the scenario tier: the manifest schema and the metrics
read back from a run record. No provider or database calls."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from evals.runner.scenario_metrics import (
    compare,
    compute_metrics,
    is_read_tool,
    parse_ts,
    render_comparison,
    render_table,
    summarize,
    tool_calls,
)
from evals.scenario_report import load_run, main as report_main

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scenario_manifests_match_schema() -> None:
    schema = json.loads((REPO_ROOT / "evals/schema/scenario-task.v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted(REPO_ROOT.glob("evals/scenarios/*.json"))
    assert paths, "at least one scenario manifest"
    for path in paths:
        manifest = json.loads(path.read_text())
        validator.validate(manifest)
        assert manifest["id"] == path.stem
        # Every metric the scenario prints is one the module computes.
        from evals.runner.scenario_metrics import METRIC_ROWS

        known = {key for key, _, _ in METRIC_ROWS}
        assert set(manifest["metrics"]) <= known, set(manifest["metrics"]) - known


def test_parse_ts_reads_postgres_and_iso_forms() -> None:
    epoch = datetime(2026, 10, 20, 23, 54, 30, tzinfo=timezone.utc).timestamp()
    assert parse_ts("2026-10-20 23:54:30.682931+00") == pytest.approx(epoch + 0.682931)
    assert parse_ts("2026-10-20T23:54:30Z") == pytest.approx(epoch)
    assert parse_ts("2026-10-20T23:54:30+00:00") == pytest.approx(epoch)
    assert parse_ts("2026-10-21 01:54:30+02") == pytest.approx(epoch)
    assert parse_ts(None) is None
    assert parse_ts("not a time") is None


def test_read_tool_classification() -> None:
    assert is_read_tool("read")
    assert is_read_tool("magister_list_social_accounts")
    assert is_read_tool("magister_integration_read")
    assert is_read_tool("web_search")
    assert not is_read_tool("write")
    assert not is_read_tool("magister_update_plan_item_status")
    assert not is_read_tool("exec")


def _msg(role: str, at: str, content: str = "", block: int = 0, **meta):
    return {"id": meta.pop("id", f"{role}-{at}-{block}"), "role": role, "created_at": at, "content": content,
            "block_index": block, "turn_id": meta.pop("turn_id", None), "metadata": meta or None}


def _tool(at: str, block: int, tool: str, args: dict, *, error: bool = False, call_id: str | None = None, turn_id: str = "t1"):
    meta = {"args": args, "phase": "result", "toolCallId": call_id or f"call-{turn_id}-{block}", "durationMs": 1}
    if error:
        meta["isError"] = True
        meta["errorContent"] = "{\"status\": \"error\"}"
    return _msg("tool_use", at, tool, block, turn_id=turn_id, **meta)


def _llm(at: str, turn: str, inp: int, out: int, *, cached: int = 0, reasoning: int = 0, cost: int = 10, provider: int = 8, ms: int = 1000):
    return {"created_at": at, "event_type": "llm_request", "model": "openai/gpt-6-luna", "input_tokens": inp,
            "output_tokens": out, "duration_ms": ms, "cost_microcents": cost, "provider_cost_microcents": provider,
            "agent_turn_id": turn, "metadata": {"cached_tokens": cached, "reasoning_tokens": reasoning}}


@pytest.fixture
def record() -> dict:
    """Two user turns. Turn 1 is a dispatched kickoff (source_message_id);
    turn 2 is streamed (matched by order). Three tool calls repeat a read,
    one errors, one approval card is raised and allowed, and a post is live."""
    t0 = "2026-10-21T10:00:00+00:00"
    return {
        "schema_version": 1, "scenario_id": "share-flood-guide-instagram", "repetition": 1, "label": "before",
        "lane": "hbench", "gateway_sha": "2c0920ec7c", "model": "openai/gpt-6-luna", "session_id": "s1",
        "started_at": t0, "ended_at": "2026-10-21T10:10:00+00:00", "stop_reason": "published",
        "turns": [
            {"index": 1, "id": "brief", "kind": "task_brief", "source": "gateway_brief", "message_id": "m1", "sent_at": t0, "settled_at": "2026-10-21T10:04:00+00:00"},
            {"index": 2, "id": "continue", "kind": "continue", "source": "continue_route", "message_id": "m2", "sent_at": "2026-10-21T10:05:00+00:00", "settled_at": "2026-10-21T10:09:00+00:00"},
        ],
        "responder": {"replies": [{"at": "2026-10-21T10:09:30+00:00", "reply": "Yes, go ahead.", "trigger": "default"}],
                      "approvals": [{"id": "ap1", "at": "2026-10-21T10:08:00+00:00", "result": "allowed"}]},
        "rows": {
            "chat_messages": [
                _msg("user", t0, "# Work on: brief", id="m1", kind="kickoff"),
                _tool("2026-10-21T10:00:01+00:00", 1, "read", {"path": "/data/BRAND.md"}),
                _tool("2026-10-21T10:00:01+00:00", 2, "magister_list_social_accounts", {}),
                _tool("2026-10-21T10:00:01+00:00", 3, "magister_list_social_accounts", {}),
                _tool("2026-10-21T10:00:01+00:00", 4, "read", {"path": "/data/BRAND.md"}),
                _tool("2026-10-21T10:00:01+00:00", 5, "pdf", {"path": "x.pdf"}, error=True),
                _tool("2026-10-21T10:00:01+00:00", 6, "write", {"path": "draft.md"}),
                _tool("2026-10-21T10:00:01+00:00", 7, "write", {"path": "draft.md"}),  # duplicate, not a read
                _msg("assistant", "2026-10-21T10:00:01+00:00", "Blocked.", 8, turn_id="t1"),
                _msg("user", "2026-10-21T10:05:00+00:00", "Continue: Share the flood guide on Instagram.", id="m2", kind="plan_dispatch"),
                _tool("2026-10-21T10:05:01+00:00", 1, "magister_publish_social_post", {"post_id": "p1"}, turn_id="t2"),
                _msg("ui_spec", "2026-10-21T10:07:30+00:00", "{\"kind\":\"approval\",\"approval_id\":\"ap1\"}", 2, turn_id="t2", kind="approval", approval_id="ap1"),
            ],
            "usage_events": [
                _llm("2026-10-21T10:00:20+00:00", "t1", 40000, 1000, reasoning=800, cost=70, provider=56, ms=13000),
                _llm("2026-10-21T10:01:00+00:00", "t1", 48000, 900, cached=40000, reasoning=500, cost=24, provider=19, ms=9000),
                {"created_at": "2026-10-21T10:01:10+00:00", "event_type": "mcp_tool", "duration_ms": 900, "cost_microcents": 0, "provider_cost_microcents": 0, "metadata": {"service": "firecrawl"}},
                _llm("2026-10-21T10:03:50+00:00", "t1", 60000, 300, cached=48000, cost=20, provider=15, ms=160000),
                _llm("2026-10-21T10:06:00+00:00", "t2", 61000, 400, cached=60000, cost=12, provider=10, ms=5000),
            ],
            "agent_turns": [
                {"id": "t1", "source_message_id": "m1", "state": "completed", "queued_at": "2026-10-21T10:00:00.5+00:00", "started_at": "2026-10-21T10:00:01+00:00", "finished_at": "2026-10-21T10:04:00+00:00"},
                {"id": "t2", "source_message_id": None, "state": "completed", "queued_at": "2026-10-21T10:05:01+00:00", "started_at": "2026-10-21T10:05:02+00:00", "finished_at": "2026-10-21T10:07:40+00:00"},
                {"id": "t3", "source_message_id": None, "state": "completed", "queued_at": "2026-10-21T10:08:05+00:00", "started_at": "2026-10-21T10:08:06+00:00", "finished_at": "2026-10-21T10:09:00+00:00", "approval_continuation_id": "ap1"},
            ],
            "approvals": [
                {"id": "ap1", "action": "publish_social_post", "decision": "manual_allow", "execution_state": "succeeded",
                 "created_at": "2026-10-21T10:07:30+00:00", "decided_at": "2026-10-21T10:08:00+00:00"},
            ],
            "posts": [{"id": "p1", "status": "published", "mediaUrls": ["https://x/y.jpg"], "createdAt": "2026-10-21T10:07:00Z"}],
        },
        "outcome": {"published": True, "has_media": True, "post_id": "p1", "live_url": "https://instagram.com/p/x"},
    }


def test_tool_calls_dedupe_by_call_id(record: dict) -> None:
    calls = tool_calls(record["rows"]["chat_messages"])
    assert [c["tool"] for c in calls] == [
        "read", "magister_list_social_accounts", "magister_list_social_accounts", "read", "pdf", "write", "write",
        "magister_publish_social_post",
    ]
    twice = record["rows"]["chat_messages"][1]
    again = dict(twice, metadata={**twice["metadata"], "phase": "start"})
    assert len(tool_calls(record["rows"]["chat_messages"] + [again])) == len(calls)


def test_compute_metrics_counts_everything(record: dict) -> None:
    m = compute_metrics(record)
    assert m["published"] is True and m["has_media"] is True
    assert m["model"] == "openai/gpt-6-luna" and m["model_requested"] == "openai/gpt-6-luna"
    assert m["wall_seconds_total"] == 600.0
    assert m["user_turns"] == 2
    # Turn 1 is matched by source_message_id; turn 2 by order and includes the
    # approval continuation queued before the window's end.
    assert m["turns"][0]["agent_turn_ids"] == ["t1"]
    assert m["turns"][1]["agent_turn_ids"] == ["t2", "t3"]
    assert m["wall_seconds_per_turn"] == [240.0, 240.0]
    assert m["scripted_replies"] == 1
    assert m["llm_calls"] == 4
    assert m["input_tokens"] == 40000 + 48000 + 60000 + 61000
    assert m["cached_tokens"] == 40000 + 48000 + 60000
    assert m["output_tokens"] == 2600
    assert m["reasoning_tokens"] == 1300
    assert m["cost_usd"] == pytest.approx((70 + 24 + 20 + 12) / 10_000)
    assert m["provider_cost_usd"] == pytest.approx((56 + 19 + 15 + 10) / 10_000)
    assert m["longest_llm_call_seconds"] == 160.0
    assert m["tool_calls"] == 8
    assert m["distinct_tools"] == 5
    assert m["duplicate_reads"] == 2  # the second list_social_accounts and the second BRAND.md read
    assert m["duplicate_calls"] == 3  # plus the repeated write
    assert m["dead_end_calls"] == 1 and m["dead_end_tools"] == ["pdf"]
    # The quiet stretch is the 160 s LLM call: from the mcp_tool event at
    # 10:01:10 to that call's usage row at 10:03:50.
    assert m["longest_silent_gap_seconds"] == 160.0
    assert m["longest_silent_gap"]["before"].startswith("llm_request")
    assert m["turns_until_first_approval"] == 2
    assert m["approvals_requested"] == 1 and m["approvals_allowed"] == 1 and m["approvals_executed"] == 1
    assert m["experience"]["status"] == "not_run"


def test_compute_metrics_without_outcome_or_bounds(record: dict) -> None:
    bare = {"rows": record["rows"]}
    m = compute_metrics(bare)
    assert m["published"] is False and m["has_media"] is False
    # From the first user message to the last recorded event (t3 finished).
    assert m["wall_seconds_total"] == 540.0
    assert m["turns_until_first_approval"] == 2


def test_window_cuts_rows_outside_it(record: dict) -> None:
    short = dict(record, ended_at="2026-10-21T10:04:30+00:00")
    m = compute_metrics(short)
    assert m["user_turns"] == 1
    assert m["llm_calls"] == 3
    assert m["approvals_requested"] == 0
    assert m["turns_until_first_approval"] is None
    assert m["wall_seconds_per_turn"] == [240.0]


def test_summary_compare_and_tables(record: dict) -> None:
    a = compute_metrics(record)
    slower = compute_metrics(dict(record, ended_at="2026-10-21T10:12:00+00:00", outcome={"published": False}))
    summary = summarize([a, slower])
    assert summary["runs"] == 2 and summary["published"] == 1 and summary["published_rate"] == 0.5
    assert summary["wall_seconds_total"]["mean"] == 660.0
    comparison = compare([slower, slower], [a, a])
    assert comparison["deltas"]["wall_seconds_total"]["delta"] == -120.0
    assert comparison["deltas"]["published_rate"]["delta"] == 1.0
    table = render_table([("run 1", a), ("run 2", slower)], ["published", "wall_seconds_total", "duplicate_reads"])
    assert table.splitlines()[0] == "| Metric | run 1 | run 2 |"
    assert "| Published (with media) | yes ✓media | no |" in table
    assert "| Wall time, total | 10m 00s | 12m 00s |" in table
    assert render_table([("x", dict(a, wall_seconds_total=719.6))], ["wall_seconds_total"]).endswith("| 12m 00s |")
    text = render_comparison(comparison, ["wall_seconds_total", "llm_calls"])
    assert "| Published | 0% | 100% | +100 pts |" in text
    assert "Wall time, total" in text and "LLM calls" in text


def test_report_cli_writes_summary(tmp_path: Path, record: dict, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    scenario = json.loads((REPO_ROOT / "evals/scenarios/share-flood-guide-instagram.json").read_text())
    run.mkdir()
    (run / "scenario.json").write_text(json.dumps(scenario))
    origin = dict(record, repetition=0, label="origin")
    for rep, rec in ((0, origin), (1, record), (2, dict(record, repetition=2))):
        (run / f"rep-{rep}").mkdir()
        (run / f"rep-{rep}" / "record.json").write_text(json.dumps(rec))
    before = tmp_path / "before"
    before.mkdir()
    (before / "scenario.json").write_text(json.dumps(scenario))
    (before / "rep-1").mkdir()
    (before / "rep-1" / "record.json").write_text(json.dumps(dict(record, outcome={"published": False})))
    assert report_main([str(run), "--before", str(before)]) == 0
    out = capsys.readouterr().out
    assert "| Metric | run 0 (origin) | run 1 | run 2 | mean of 2 |" in out
    assert "| Published (with media) | yes ✓media | yes ✓media | yes ✓media | 2/2 |" in out
    assert "### Before → after (means)" in out
    assert (run / "summary.json").exists() and (run / "summary.md").exists()
    assert (run / "rep-1" / "metrics.json").exists()
    loaded = load_run(run, write=False)
    assert loaded["origin"] is not None and len(loaded["replays"]) == 2
