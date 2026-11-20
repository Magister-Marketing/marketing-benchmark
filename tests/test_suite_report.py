"""The suite summary: settings side by side, nothing unscored counted, nothing private written."""
import json
import re

import pytest

from evals import scenario_rescore as rs
from evals import suite_report

PRIVATE = "the customer's own words, which no summary may carry"


def record(scenario_id, repetition, *, reply="Done.", **extra):
    return {"scenario_id": scenario_id, "repetition": repetition, "nonce": "ab12cd", "stop_reason": "turn_end",
            "harvest_gaps": [], "notes": [], "outcome": {"passed": True, "summary": "old"},
            "rows": {"transcript_tool_calls": [], "approvals": [], "state": {}, "chat_messages": [
                {"role": "user", "content": PRIVATE, "created_at": "2026-11-20T06:00:00Z"},
                {"role": "assistant", "content": reply, "created_at": "2026-11-20T06:01:00Z"}]}, **extra}


def scenario(scenario_id):
    return {"schema_version": 1, "id": scenario_id, "version": 1, "title": f"Title of {scenario_id}",
            "description": f"What {scenario_id} asks.", "tags": ["magister-benchmark", "read"],
            "turns": [{"id": "t1", "kind": "message", "text": "Say done."}],
            "outcome": {"kind": "product_checks", "checks": [{"id": "said_done", "type": "reply", "pattern": "done"}]}}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "evals" / "scenarios").mkdir(parents=True)
    for scenario_id in ("a", "b"):
        (root / "evals" / "scenarios" / f"{scenario_id}.json").write_text(json.dumps(scenario(scenario_id)))
    monkeypatch.setattr(rs, "REPO_ROOT", root)
    return tmp_path


def suite_run(repo, name, records, *, effort="low", seconds=40.0, cost=0.05):
    run = repo / name
    rows = []
    for item in records:
        path = run / item["scenario_id"] / f"rep-{item['repetition']}"
        path.mkdir(parents=True)
        (path / "record.json").write_text(json.dumps(item))
        (run / item["scenario_id"] / "scenario.json").write_text(json.dumps(scenario(item["scenario_id"])))
        rows.append({"scenario": item["scenario_id"], "repetition": item["repetition"], "seconds": seconds,
                     "llm_seconds": seconds / 4, "llm_calls": 3, "tool_calls": 5, "provider_cost_usd": cost,
                     "session_id": "5e55-10n", "notes": ["fixture is someone@example.com's brand"]})
        seconds += 10
    (run / "suite.json").write_text(json.dumps({
        "suite": "magister", "lane": "a-lane", "model": "openai/gpt-6.2-sol", "effort": effort,
        "gateway_sha": "abc123", "rows": rows}))
    return run


def test_a_setting_counts_scored_attempts_only_and_a_top_up_fills_what_was_lost(repo):
    first = suite_run(repo, "first", [
        record("a", 1), record("a", 2, reply="No."),
        record("b", 1, stop_reason="error", notes=["error: the machine refused the turn"]),
        record("b", 2, harvest_gaps=["transcript"])])
    top_up = suite_run(repo, "top-up", [record("b", 1), record("b", 2)], seconds=100.0, cost=0.15)
    summary = suite_report.summarize({"low": [first, top_up]})
    low = summary["settings"][0]
    assert (low["attempts"], low["passed"], low["not_scored"]) == (4, 3, 2)
    # a: one of two passed, so it did not pass every attempt; b: both scored attempts passed.
    assert (low["scenarios"], low["scenarios_passed_every_attempt"]) == (2, 1)
    assert low["by_scenario"]["a"] == {"attempts": 2, "passed": 1, "not_scored": 0, "median_seconds": 45.0}
    assert low["by_scenario"]["b"] == {"attempts": 2, "passed": 2, "not_scored": 2, "median_seconds": 105.0}
    assert low["failures"] == [{"scenario": "a", "repetition": 2, "run": "first", "checks": ["said_done"]}]
    # Measurements are over the scored attempts: 40, 50, 100, 110 seconds; the errored 60 and 70 are left out.
    assert low["median_seconds"] == 75.0 and low["mean_cost_usd"] == 0.1 and low["cost_known_for"] == 4
    assert low["runs"] == ["first", "top-up"] and low["efforts"] == ["low"]
    assert summary["scenarios"] == [
        {"id": "a", "title": "Title of a", "description": "What a asks.", "tags": ["read"]},
        {"id": "b", "title": "Title of b", "description": "What b asks.", "tags": ["read"]}]


def test_a_scenario_with_no_scored_attempt_did_not_pass_every_attempt(repo):
    run = suite_run(repo, "run", [record("a", 1), record("b", 1, harvest_gaps=["rows"])])
    block = suite_report.summarize({"x": [run]})["settings"][0]
    assert (block["attempts"], block["scenarios"], block["scenarios_passed_every_attempt"]) == (1, 2, 1)
    assert block["by_scenario"]["b"]["median_seconds"] is None


def test_the_file_and_the_table_hold_no_message_text_session_or_lane(repo, capsys):
    low = suite_run(repo, "low-run", [record("a", 1), record("a", 2, reply="No.")])
    high = suite_run(repo, "high-run", [record("a", 1), record("b", 1)], effort="high")
    out = repo / "summary.json"
    assert suite_report.main([f"low={low}", f"high={high}", "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    written = out.read_text()
    for text in (printed, written):
        for private in (PRIVATE, "5e55-10n", "someone@example.com", "a-lane"):
            assert private not in text
    assert re.search(r"^low\s+1/2\s+0/1\b", printed, re.M) and re.search(r"^high\s+2/2\s+2/2\b", printed, re.M)
    assert "low a rep 2: said_done" in printed
    assert [block["label"] for block in json.loads(written)["settings"]] == ["low", "high"]


@pytest.mark.parametrize("args", [["low"], ["low=a", "low=b"], ["=a"]])
def test_a_malformed_setting_is_refused(repo, args):
    with pytest.raises(SystemExit):
        suite_report.main(args)


def test_a_folder_that_is_not_a_suite_run_is_refused(repo):
    (repo / "empty").mkdir()
    with pytest.raises(SystemExit):
        suite_report.main([f"low={repo / 'empty'}"])


def test_a_scenario_of_an_earlier_outcome_kind_carries_its_caveat_into_the_table_and_the_file(repo, capsys):
    earlier = scenario("a")
    earlier["outcome"] = {"kind": "social_post_published"}
    (repo / "repo" / "evals" / "scenarios" / "a.json").write_text(json.dumps(earlier))
    run = suite_run(repo, "run", [record("a", 1, outcome={"published": True}), record("b", 1)])
    summary = suite_report.summarize({"low": [run]})
    assert summary["settings"][0]["caveated_scenarios"] == ["a"]
    assert summary["caveat"].startswith("a: ") and "pull/27" in summary["caveat"]
    assert "not a pass rate for a:" in suite_report.render(summary)
    # The suite's own kind: no caveat anywhere.
    plain = suite_report.summarize({"low": [suite_run(repo, "plain", [record("b", 1)])]})
    assert plain["caveat"] is None and "not a pass rate" not in suite_report.render(plain)
