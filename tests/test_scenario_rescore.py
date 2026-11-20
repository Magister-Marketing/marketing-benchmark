"""Re-scoring saved records: what is left out is said, never folded into a pass rate."""
import json

from evals import scenario_rescore as rs


def record(scenario_id, repetition, *, reply="Done.", **extra):
    return {"scenario_id": scenario_id, "repetition": repetition, "nonce": "ab12cd", "stop_reason": "turn_end",
            "harvest_gaps": [], "notes": [], "outcome": {"passed": True, "summary": "old"},
            "rows": {"transcript_tool_calls": [], "approvals": [], "state": {}, "chat_messages": [
                {"role": "user", "content": "Ask.", "created_at": "2026-11-20T06:00:00Z"},
                {"role": "assistant", "content": reply, "created_at": "2026-11-20T06:01:00Z"}]}, **extra}


def scenario(text="Say done."):
    return {"schema_version": 1, "id": "s", "version": 1, "turns": [{"id": "t1", "kind": "message", "text": text}],
            "outcome": {"kind": "product_checks", "checks": [{"id": "said_done", "type": "reply", "pattern": "done"}]}}


def run_dir(tmp_path, monkeypatch, records, *, saved_text="Say done.", current_text="Say done."):
    repo = tmp_path / "repo"
    (repo / "evals" / "scenarios").mkdir(parents=True)
    (repo / "evals" / "scenarios" / "s.json").write_text(json.dumps(scenario(current_text)))
    monkeypatch.setattr(rs, "REPO_ROOT", repo)
    run = tmp_path / "run"
    (run / "s").mkdir(parents=True)
    (run / "s" / "scenario.json").write_text(json.dumps(scenario(saved_text)))
    for item in records:
        path = run / "s" / f"rep-{item['repetition']}"
        path.mkdir()
        (path / "record.json").write_text(json.dumps(item))
    return run


def test_errored_and_unread_records_are_named_and_not_counted_as_passes(tmp_path, monkeypatch, capsys):
    run = run_dir(tmp_path, monkeypatch, [
        record("s", 1), record("s", 2, reply="No."),
        record("s", 3, stop_reason="error", notes=["error: the machine refused the turn"]),
        record("s", 4, harvest_gaps=["transcript"])])
    rows = {row["repetition"]: row for row in rs.rescore(run)}
    assert [rows[n]["status"] for n in (1, 2, 3, 4)] == ["passed", "failed", "unscored", "unscored"]
    assert rows[2]["changed"] is True and "machine refused" in rows[3]["why"] and "transcript" in rows[4]["why"]
    assert rs.main([str(run)]) == 1
    out = capsys.readouterr().out
    assert "total: 1/2 scored attempts passed" in out and "2 of 4 record(s) NOT SCORED" in out
    assert "0/1 scenarios passed every attempt" in out


def test_a_record_asked_a_question_the_scenario_no_longer_asks_is_not_scored(tmp_path, monkeypatch, capsys):
    run = run_dir(tmp_path, monkeypatch, [record("s", 1)], saved_text="Say done.", current_text="Say done, twice.")
    assert rs.rescore(run)[0]["status"] == "unscored" and "different question" in rs.rescore(run)[0]["why"]
    assert rs.rescore(run, saved=True)[0]["status"] == "passed"  # against the scenario it was run with
    assert rs.main([str(run)]) == 1
    capsys.readouterr()


def test_a_clean_run_exits_zero_and_a_malformed_check_exits_two(tmp_path, monkeypatch, capsys):
    run = run_dir(tmp_path, monkeypatch, [record("s", 1)])
    assert rs.main([str(run)]) == 0
    broken = scenario()
    broken["outcome"]["checks"][0]["type"] = "nope"
    (tmp_path / "repo" / "evals" / "scenarios" / "s.json").write_text(json.dumps(broken))
    assert rs.main([str(run)]) == 2
    capsys.readouterr()


def test_the_total_of_an_earlier_outcome_kind_is_not_printed_as_a_pass_rate(tmp_path, monkeypatch, capsys):
    """The five earlier scenarios' scorers have open defects: a total over one of them says so."""
    run = run_dir(tmp_path, monkeypatch, [record("s", 1, outcome={"published": True})])
    assert rs.main([str(run)]) == 0
    assert "not a pass rate" not in capsys.readouterr().out  # product_checks: a plain total
    earlier = scenario()
    earlier["outcome"] = {"kind": "social_post_published"}
    for path in (tmp_path / "repo" / "evals" / "scenarios" / "s.json", run / "s" / "scenario.json"):
        path.write_text(json.dumps(earlier))
    assert rs.main([str(run)]) == 0
    out = capsys.readouterr().out
    assert "total: 1/1 scored attempts passed" in out and "not a pass rate for s:" in out and "pull/27" in out
