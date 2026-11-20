"""The suite summary: settings side by side, nothing unscored counted, nothing private written."""
import json
import re

import pytest

from evals import scenario_rescore as rs
from evals import suite_report

PRIVATE = "the customer's own words, which no summary may carry"


def record(scenario_id, repetition, *, reply="Done.", **extra):
    return {"scenario_id": scenario_id, "repetition": repetition, "nonce": "ab12cd", "stop_reason": "turn_end",
            "session_id": "5e55-10n", "harvest_gaps": [], "notes": [], "outcome": {"passed": True, "summary": "old"},
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


def suite_run(repo, name, records, *, effort="low", seconds=40.0, cost=0.05, rows=None, listed=None, extra_rows=()):
    """A suite run folder. ``rows`` overrides fields of a record's row by
    (scenario, repetition); ``extra_rows`` are rows with no record (attempts
    never made); ``listed`` is the order the run lists its scenarios in."""
    run = repo / name
    out = []
    for item in records:
        path = run / item["scenario_id"] / f"rep-{item['repetition']}"
        path.mkdir(parents=True)
        (path / "record.json").write_text(json.dumps(item))
        (run / item["scenario_id"] / "scenario.json").write_text(json.dumps(scenario(item["scenario_id"])))
        row = {"scenario": item["scenario_id"], "repetition": item["repetition"], "seconds": seconds,
               "llm_seconds": seconds / 4, "llm_calls": 3, "tool_calls": 5, "provider_cost_usd": cost,
               "models": ["openai/gpt-6.2-sol"], "session_id": item.get("session_id"),
               "notes": ["fixture is someone@example.com's brand"]}
        row.update((rows or {}).get((item["scenario_id"], item["repetition"]), {}))
        out.append(row)
        seconds += 10
    out += list(extra_rows)
    (run / "suite.json").write_text(json.dumps({
        "suite": "magister", "lane": "a-lane", "model": "openai/gpt-6.2-sol", "effort": effort,
        "gateway_sha": "abc123", "scenarios": [{"scenario": name_} for name_ in (listed or [])], "rows": out}))
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
    low = suite_run(repo, "low-run", [
        record("a", 1), record("a", 2, reply="No."),
        record("b", 1, stop_reason="error", notes=[f"error: the chat with someone@example.com said: {PRIVATE}"])])
    high = suite_run(repo, "high-run", [record("a", 1), record("b", 1)], effort="high")
    out = repo / "summary.json"
    assert suite_report.main([f"low={low}", f"high={high}", "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    written = out.read_text()
    for text in (printed, written):
        for private in (PRIVATE, "5e55-10n", "someone@example.com", "a-lane"):
            assert private not in text
    assert re.search(r"^low\s+1/2\s+0/2\b", printed, re.M) and re.search(r"^high\s+2/2\s+2/2\b", printed, re.M)
    assert "low a rep 2: said_done" in printed
    assert [block["label"] for block in json.loads(written)["settings"]] == ["low", "high"]


def test_a_malformed_setting_is_refused_for_its_own_reason(repo, capsys):
    run = suite_run(repo, "run", [record("a", 1)])
    other = suite_run(repo, "other", [record("a", 1)])
    assert suite_report.main([f"low={run}", f"high={other}"]) == 0  # the same shapes, well formed
    capsys.readouterr()
    for args, reason in (
        (["low"], "expected LABEL=RUN_DIR"),
        ([f"low={run}", f"low={other}"], "each label once"),
        ([f"={run}"], "expected LABEL=RUN_DIR"),
        (["low=,"], "names no run folder"),
        ([f"low={run}", f"high={run}"], "listed twice"),
        ([f"low={run},{run}"], "listed twice"),
    ):
        with pytest.raises(SystemExit):
            suite_report.main(args)
        assert reason in capsys.readouterr().err, args


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
    assert summary["caveat"].startswith("a: ") and "not a pass rate" in summary["caveat"]
    assert "not a pass rate for a:" in suite_report.render(summary) and "pull/27" in suite_report.render(summary)
    # The suite's own kind: no caveat anywhere.
    plain = suite_report.summarize({"low": [suite_run(repo, "plain", [record("b", 1)])]})
    assert plain["caveat"] is None and "not a pass rate" not in suite_report.render(plain)


def test_an_attempt_another_model_served_is_not_scored(repo):
    """An organization out of credits is served a cheaper model and the chat does not say so."""
    run = suite_run(repo, "run", [record("a", 1), record("a", 2), record("a", 3, reply="No.")], rows={
        ("a", 2): {"models": ["openai/gpt-6-luna"]},
        ("a", 3): {"models": ["openai/gpt-6-luna", "openai/gpt-6.2-sol"]}})
    block = suite_report.summarize({"low": [run]})["settings"][0]
    assert (block["attempts"], block["passed"], block["not_scored"]) == (1, 1, 2)
    assert block["models"] == ["openai/gpt-6.2-sol"] and block["failures"] == []


def test_a_row_for_another_chat_is_not_the_records_measurement(repo):
    """A record harvested again later no longer matches its suite.json row: its time and cost are unknown, and said so."""
    run = suite_run(repo, "run", [record("a", 1), record("a", 2)], rows={("a", 2): {"session_id": "another-chat", "tool_calls": 0}})
    summary = suite_report.summarize({"low": [run]})
    block = summary["settings"][0]
    assert (block["attempts"], block["measured_for"], block["cost_known_for"]) == (2, 1, 1)
    assert block["median_tool_calls"] == 5 and block["median_seconds"] == 40.0
    assert "low 1" in suite_report.render(summary).split("not in the medians")[1]


def test_an_attempt_the_run_never_made_is_counted_and_its_scenario_is_listed(repo):
    never = {"scenario": "b", "repetition": 1, "status": "not_run"}
    run = suite_run(repo, "run", [record("a", 1)], extra_rows=[never], listed=["b", "a"])
    summary = suite_report.summarize({"low": [run]})
    block = summary["settings"][0]
    assert [item["id"] for item in summary["scenarios"]] == ["b", "a"]  # the run's order, not the alphabet's
    assert (block["attempts"], block["not_scored"], block["scenarios"], block["scenarios_passed_every_attempt"]) == (1, 1, 2, 1)
    assert block["by_scenario"]["b"] == {"attempts": 0, "passed": 0, "not_scored": 1, "median_seconds": None}


def test_the_file_carries_the_caveat_without_the_link(repo):
    earlier = scenario("a")
    earlier["outcome"] = {"kind": "social_post_published"}
    (repo / "repo" / "evals" / "scenarios" / "a.json").write_text(json.dumps(earlier))
    summary = suite_report.summarize({"low": [suite_run(repo, "run", [record("a", 1, outcome={"published": True})])]})
    assert "not a pass rate" in summary["caveat"] and "http" not in json.dumps(summary)
    assert "pull/27" in suite_report.render(summary)
