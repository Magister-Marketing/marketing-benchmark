"""Offline tests for scripts/bench-model.py: nothing here calls a model."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bench-model.py"
spec = importlib.util.spec_from_file_location("bench_model", SCRIPT)
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)

TASKS = ["alpha", "beta"]
JUDGE = "claude-sonnet-5-5"


def report(run_id, candidate, *, harness="direct-api", skills=True, reps=1,
           scores=None, passes=None, cost=0.05, lost=()):
    """A report.json shaped like the runner's, for two tasks."""
    scores = scores or {t: 90.0 for t in TASKS}
    passes = passes or {}
    subs = []
    for task in TASKS:
        runs = []
        for rep in range(1, reps + 1):
            gone = (task, rep) in lost
            runs.append({
                "repetition": rep,
                "mark": "E" if gone else ("P" if passes.get(task, True) else "F"),
                "pass": (not gone) and passes.get(task, True),
                "finish_reason": None if gone else "stop",
                "cost_usd": None if gone else cost,
                "latency_seconds": None if gone else 10.0,
            })
        subs.append({"task_id": task, "model_id": candidate, "runs": runs})
    return {
        "run_id": run_id,
        "harness": harness,
        "skills_included": skills,
        "tools_enabled": True,
        "repetitions": reps,
        "tasks": list(TASKS),
        "models": {candidate: {"task_scores": scores, "composite_score": sum(scores.values()) / 2}},
        "submissions": subs,
    }


def write_run(root: Path, rep: dict, *, judge=JUDGE, errors=None, identity=None,
              pricing=None, tokens=(1000, 200)) -> Path:
    run_dir = root / rep["run_id"]
    run_dir.mkdir(parents=True)
    (run_dir / "report.json").write_text(json.dumps(rep, indent=2) + "\n")
    (run_dir / "grading.json").write_text(json.dumps({
        "judge_model": judge, "judge_protocol_version": 4,
        "judge_usage": {"calls": 4, "cost_usd": 0.4},
    }))
    candidate = next(iter(rep["models"]))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": rep["run_id"],
        "models": {candidate: {"pricing": pricing or {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}},
        **({"eval_identity": identity} if identity else {}),
    }))
    lines = []
    for sub in rep["submissions"]:
        for run in sub["runs"]:
            lines.append(json.dumps({
                "task_id": sub["task_id"], "repetition": run["repetition"],
                "input_tokens": tokens[0], "output_tokens": tokens[1],
                "error": (errors or {}).get((sub["task_id"], run["repetition"])),
            }))
    (run_dir / "attempts.jsonl").write_text("\n".join(lines) + "\n")
    return run_dir


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A results site with one model on its board."""
    web = tmp_path / "web"
    (web / "data" / "runs").mkdir(parents=True)
    meta = web / bm.BOARD_META
    meta.parent.mkdir(parents=True)
    old = report("20260101-000000-aaaaaaaa", "gpt-6.2-sol-high", scores={"alpha": 98.0, "beta": 96.0}, cost=0.08)
    (web / "data" / "runs" / f"{old['run_id']}.json").write_text(json.dumps(old))
    meta.write_text(json.dumps({
        "judge": "Claude Sonnet 5.5", "judge_model": JUDGE, "judge_protocol_version": 4,
        "earlier_judge": "Claude Sonnet 5", "references": ["gpt-6.2-sol-high", "claude-opus-5-5-high"],
        "runs": [{"run_id": old["run_id"], "setup": "skills", "judge_model": JUDGE, "judge_protocol_version": 4}],
    }, indent=2) + "\n")
    return web


def test_unknown_candidate_is_refused_with_how_to_add_it(site):
    with pytest.raises(SystemExit) as stop:
        bm.main(["--web", str(site), "--model", "gpt-9-nova", "--dry-run"])
    assert "not in eval_runner/models.json" in str(stop.value)
    assert '"pricing"' in str(stop.value)


def test_dry_run_prints_the_estimate_and_spends_nothing(site, tmp_path, monkeypatch, capsys):
    like = write_run(tmp_path / "results", report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-high", cost=0.10),
                     pricing={"input_per_mtok": 2.0, "output_per_mtok": 10.0})
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("a dry run must not run anything"))
    code = bm.main(["--web", str(site), "--model", "gpt-6.1-sol-high", "--like", str(like), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Dry run: nothing was spent." in out
    # gpt-6.1-sol-high has the same list prices: two tasks, three attempts each
    # at $0.10, plus the judge's $0.10 a call for six calls.
    assert "about $0.60 in model calls + $0.60 judge = $1.20" in out
    assert "eval.py gpt-6.1-sol-high --tools --tasks alpha,beta --repetitions 3 --judge claude-sonnet-5-5 -y" in out


def test_without_the_confirmation_word_nothing_runs(site, tmp_path, monkeypatch):
    like = write_run(tmp_path / "results", report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-high"))
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("ran without confirm=SPEND"))
    assert bm.main(["--web", str(site), "--model", "gpt-6.1-sol-high", "--like", str(like), "--confirm", "yes"]) == 2


def test_a_model_already_on_the_board_is_refused_before_spending(site, tmp_path, monkeypatch):
    like = write_run(tmp_path / "results", report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-high"))
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("spent on a run that export would refuse"))
    with pytest.raises(SystemExit, match="already has 20260101-000000-aaaaaaaa for gpt-6.2-sol-high"):
        bm.main(["--web", str(site), "--model", "gpt-6.2-sol-high", "--like", str(like), "--confirm", "SPEND"])
    # Without the skills it has no run yet, so plain alone would go ahead; and
    # inside Magister the model has no run either.
    assert bm.already_listed(site, json.loads((site / bm.BOARD_META).read_text()),
                             "gpt-6.2-sol-high", ["no-skills", "magister"]) == []


def test_export_copies_the_report_unchanged_and_lists_the_run(site, tmp_path):
    rep = report("20260103-000000-cccccccc", "gpt-6-astra-high", reps=3, cost=0.2,
                 scores={"alpha": 100.0, "beta": 33.3}, lost={("beta", 1), ("beta", 2)})
    run = write_run(tmp_path / "results", rep,
                    errors={("beta", 1): "openai call failed (TimeoutError: The read operation timed out)",
                            ("beta", 2): "openai call failed (TimeoutError: The read operation timed out)"})
    entry = bm.export_run(run, site)
    copied = site / "data" / "runs" / "20260103-000000-cccccccc.json"
    assert copied.read_bytes() == (run / "report.json").read_bytes()
    meta = json.loads((site / bm.BOARD_META).read_text())
    assert meta["runs"][-1] == entry
    assert entry["setup"] == "skills" and entry["judge_model"] == JUDGE
    assert [(e["task"], e["repetition"]) for e in entry["run_errors"]] == [("beta", 1), ("beta", 2)]
    assert entry["run_errors"][0]["record"].startswith("openai call failed")
    assert "timed out" in entry["run_errors"][0]["cause"]
    # Exporting again changes nothing.
    before = (site / bm.BOARD_META).read_text()
    bm.export_run(run, site)
    assert (site / bm.BOARD_META).read_text() == before


def test_export_refuses_another_judge(site, tmp_path):
    run = write_run(tmp_path / "results", report("20260103-000000-dddddddd", "gpt-6-astra-high"), judge="claude-sonnet-5")
    with pytest.raises(SystemExit, match="graded by claude-sonnet-5"):
        bm.export_run(run, site)


def test_export_refuses_a_second_run_of_a_model_in_one_setup(site, tmp_path):
    run = write_run(tmp_path / "results", report("20260103-000000-eeeeeeee", "gpt-6.2-sol-high"))
    with pytest.raises(SystemExit, match="already has 20260101-000000-aaaaaaaa"):
        bm.export_run(run, site)


def test_export_of_a_magister_run_says_which_test_lane(site, tmp_path):
    rep = report("20260103-000000-ffffffff", "magister-gpt-6.2-sol-high", harness="magister-agent", skills=False)
    run = write_run(tmp_path / "results", rep, identity={"eval_target": "lane:bench", "gateway_sha": "d0afdad5034d895a"})
    entry = bm.export_run(run, site)
    assert entry["setup"] == "magister"
    assert entry["ran_on"] == "a test lane (bench), not production (gateway d0afdad50)"


def test_export_refuses_a_magister_run_not_made_on_a_test_lane(site, tmp_path):
    rep = report("20260103-000000-abababab", "magister-gpt-6.2-sol-high", harness="magister-agent", skills=False)
    run = write_run(tmp_path / "results", rep, identity={"eval_target": "canary"})
    with pytest.raises(SystemExit, match="test lane"):
        bm.export_run(run, site)


def test_tweet_reads_the_site_and_stays_under_280(site, tmp_path):
    rep = report("20260103-000000-12121212", "gpt-6.1-sol-high", reps=3, cost=0.10133,
                 scores={"alpha": 99.0, "beta": 96.8}, passes={"beta": False})
    run = write_run(tmp_path / "results", rep)
    bm.export_run(run, site)
    text = bm.tweet_for(site, rep["run_id"])
    assert len(text) <= 280
    assert text.startswith("GPT-6.1 Sol (high effort) scored 97.9/100 on the Marketing Benchmark, #1 of 2 models: ")
    assert "3/6 attempts met every requirement, at 10¢ an attempt." in text
    assert "vs GPT-6.2 Sol 97.0" in text  # the reference with a run; Opus 5.5 has none
    assert "Opus" not in text
    assert text.endswith("https://marketingbenchmark.ai/models/gpt-6.1-sol-high")


def test_an_export_refreshes_every_runs_draft(site, tmp_path, monkeypatch, capsys):
    results, copy = tmp_path / "results", tmp_path / "other-checkout"
    monkeypatch.setattr(bm, "search_dirs", lambda: [results, copy])
    # The board's run has a folder in two checkouts, each with the draft
    # written when it was the only model: "#1 of 1".
    old_id = "20260101-000000-aaaaaaaa"
    old = json.loads((site / "data" / "runs" / f"{old_id}.json").read_text())
    stale = [write_run(results, old) / "tweet.txt", write_run(copy, old) / "tweet.txt"]
    for draft in stale:
        draft.write_text("GPT-6.2 Sol (high effort) scored 97.0/100 ..., #1 of 1 models: ...\n")
    new = report("20260103-000000-78787878", "gpt-6-luna-xhigh", scores={"alpha": 99.0, "beta": 99.0})
    run = write_run(results, new)
    bm.main(["--web", str(site), "--export", str(run)])
    assert "#1 of 2 models" in (run / "tweet.txt").read_text()
    assert (run / "tweet.txt").read_text().startswith("GPT-6 Luna (xhigh effort) scored 99.0/100")
    for draft in stale:
        assert draft.read_text() == bm.tweet_for(site, old_id) + "\n"
        assert "#2 of 2 models" in draft.read_text()
    assert "2 changed" in capsys.readouterr().out
    # A second export of the same run finds nothing stale.
    bm.main(["--web", str(site), "--export", str(run)])
    assert "0 changed" in capsys.readouterr().out


def test_a_run_going_at_the_same_time_is_not_taken_for_this_one(tmp_path, monkeypatch):
    results = tmp_path / "results"
    monkeypatch.setattr(bm, "RESULTS_DIR", results)
    marker = time.time() - 1

    def fresh(run_id, cand, skills=True):
        d = write_run(results, report(run_id, cand, skills=skills))
        (d / "run.json").write_text(json.dumps(
            {"models": {cand: {}}, "harness": "direct-api", "skills_included": skills}))
        return d

    ours = fresh("20260103-000000-90909090", "gpt-6-luna-high")
    # Started later in the same checkout: another model, and the same model
    # without the skills.
    fresh("20260103-000001-91919191", "gpt-6.2-sol-low")
    plain = fresh("20260103-000002-92929292", "gpt-6-luna-high", skills=False)
    assert bm.newest_run_since(marker, "gpt-6-luna-high", "skills") == ours
    assert bm.newest_run_since(marker, "gpt-6-luna-high", "no-skills") == plain
    with pytest.raises(SystemExit, match="no new run folder for gpt-6-luna-xhigh"):
        bm.newest_run_since(marker, "gpt-6-luna-xhigh", "skills")


def test_a_claude_code_run_exports_and_gets_a_draft(site, tmp_path):
    rep = report("20260103-000000-cdcdcdcd", "claude-code-claude-haiku-5-5-high", harness="claude-code", skills=False)
    run = write_run(tmp_path / "results", rep)
    assert bm.export_run(run, site)["setup"] == "claude-code"
    text = bm.tweet_for(site, rep["run_id"])
    assert "#1 of 1 models inside Claude Code" in text and "Run inside Claude Code." in text


def test_runs_that_print_the_same_score_share_a_rank(site, tmp_path):
    # 96.98 prints as 97.0, the board run's score, so the two share first place.
    rep = report("20260103-000000-34343434", "gpt-6.1-sol-high", scores={"alpha": 98.0, "beta": 95.96})
    run = write_run(tmp_path / "results", rep)
    bm.export_run(run, site)
    assert "tied #1 of 2 models" in bm.tweet_for(site, rep["run_id"])


def test_the_draft_says_when_the_model_is_also_the_judge(site, tmp_path):
    rep = report("20260103-000000-56565656", "claude-sonnet-5-5-high")
    run = write_run(tmp_path / "results", rep)
    bm.export_run(run, site)
    text = bm.tweet_for(site, rep["run_id"])
    assert text.startswith("Claude Sonnet 5.5 (high effort) scored")
    assert "It is also the judge." in text and len(text) <= 280


def test_numbers_round_as_the_page_does():
    assert bm.fmt_score(96.25) == "96.3"  # JavaScript's toFixed rounds this tie up
    assert bm.fmt_score(97.866) == "97.9"
    assert bm.fmt_cents(0.0186) == "1.9¢"
    assert bm.fmt_cents(0.4415) == "44¢"


@pytest.mark.parametrize("bench_id, label", [
    ("gpt-6.1-sol-high", "GPT-6.1 Sol"),
    ("gpt-6-astra-high", "GPT-6 Astra"),
    ("claude-opus-5-5-high", "Claude Opus 5.5"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
    ("gemini-3.8-flash-high", "Gemini 3.8 Flash"),
    ("glm-5.3", "GLM-5.3"),
])
def test_model_names_match_the_site(bench_id, label):
    assert bm.model_label(bench_id) == label
