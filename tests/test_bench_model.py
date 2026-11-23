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
TITLES = {"alpha": "Alpha task", "beta": "Beta task"}
JUDGE = "claude-sonnet-5-5"
# Not the live board's name: the board is the one the site's
# src/lib/current-meta.ts names, never a name kept in the script.
BOARD = "20261201-test-board"
EARLIER = "20261118-model-board"
URL = "https://marketingbenchmark.ai/runs/"


def report(run_id, candidate, *, harness="direct-api", skills=True, reps=1, tools=False,
           tasks=TASKS, scores=None, passes=None, cost=0.05, lost=(), cut=()):
    """A report.json shaped like the runner's. `passes` says per task whether
    its attempts were right; `lost` attempts are run errors, `cut` ones ran out
    of output."""
    scores = scores or {t: 90.0 for t in tasks}
    passes = passes or {}
    subs = []
    for task in tasks:
        runs = []
        for rep in range(1, reps + 1):
            gone, short = (task, rep) in lost, (task, rep) in cut
            right = passes.get(task, True) and not gone and not short
            runs.append({
                "repetition": rep,
                "mark": "E" if gone else "T" if short else "P" if right else "F",
                "pass": right,
                "finish_reason": None if gone else "max_tokens" if short else "stop",
                "cost_usd": None if gone else cost,
            })
        subs.append({"task_id": task, "task_title": TITLES[task], "model_id": candidate, "runs": runs})
    return {
        "run_id": run_id,
        "harness": harness,
        "skills_included": skills,
        "tools_enabled": tools,
        "repetitions": reps,
        "tasks": list(tasks),
        "models": {candidate: {"task_scores": scores, "composite_score": sum(scores.values()) / len(scores)}},
        "submissions": subs,
    }


def write_run(root: Path, rep: dict, *, identity=None, pricing=None) -> Path:
    run_dir = root / rep["run_id"]
    run_dir.mkdir(parents=True)
    (run_dir / "report.json").write_text(json.dumps(rep, indent=2) + "\n")
    (run_dir / "grading.json").write_text(json.dumps({
        "judge_model": JUDGE, "judge_protocol_version": 4,
        "judge_usage": {"calls": 4, "cost_usd": 0.4},
    }))
    candidate = next(iter(rep["models"]))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": rep["run_id"],
        "harness": rep["harness"],
        "skills_included": rep["skills_included"],
        "models": {candidate: {"pricing": pricing or {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}},
        **({"eval_identity": identity} if identity else {}),
    }))
    lines = []
    for sub in rep["submissions"]:
        for run in sub["runs"]:
            lines.append(json.dumps({
                "task_id": sub["task_id"], "repetition": run["repetition"],
                "input_tokens": 1000, "output_tokens": 200,
            }))
    (run_dir / "attempts.jsonl").write_text("\n".join(lines) + "\n")
    return run_dir


def board_meta(web: Path) -> Path:
    return web / "data" / "experiments" / BOARD / "meta.json"


def meta_of(web: Path) -> dict:
    return json.loads(board_meta(web).read_text())


def add_to_board(web: Path, rep: dict, setup: str) -> None:
    """Put a report on the board by hand, as the site's own data has it."""
    (web / "data" / "runs" / f"{rep['run_id']}.json").write_text(json.dumps(rep))
    meta = meta_of(web)
    model = bm.plain_model(next(iter(rep["models"])))
    if model not in meta["models"]:
        meta["models"].append(model)
    meta["runs"].append({"run_id": rep["run_id"], "setup": setup, "judge_model": JUDGE,
                         "judge_protocol_version": 4})
    board_meta(web).write_text(json.dumps(meta, indent=2) + "\n")


@pytest.fixture(autouse=True)
def runner_board(tmp_path, monkeypatch) -> Path:
    """The runner's board.json, holding the site's two tasks."""
    path = tmp_path / "board.json"
    path.write_text(json.dumps({"areas": [{"id": "one", "title": "One", "tasks": TASKS}]}))
    monkeypatch.setattr(bm, "BOARD_FILE", path)
    return path


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A results site whose home page charts BOARD, with GPT-6.2 Sol on it
    with the Marketing Skills (one of the two tasks fully right), and the
    earlier model board its earlier page still reads."""
    web = tmp_path / "web"
    (web / "data" / "runs").mkdir(parents=True)
    (web / "src" / "lib").mkdir(parents=True)
    (web / "src" / "lib" / "current-meta.ts").write_text(
        "export function readCurrentMeta(): CurrentMeta {\n"
        f'  current ??= read<CurrentMeta>("{BOARD}");\n'
        "  return current;\n}\n"
    )
    earlier = web / "data" / "experiments" / EARLIER / "meta.json"
    earlier.parent.mkdir(parents=True)
    earlier.write_text(json.dumps({"judge_model": JUDGE, "judge_protocol_version": 4, "runs": []}) + "\n")
    board_meta(web).parent.mkdir(parents=True)
    board_meta(web).write_text(json.dumps({
        "id": BOARD, "runner_commit": "05dcffe", "judge": "Claude Sonnet 5.5",
        "judge_model": JUDGE, "judge_protocol_version": 4, "effort": "medium",
        "models": [], "setups": ["no-skills", "skills", "magister"], "tasks": TASKS,
        "harness_only": [], "runs": [],
    }, indent=2) + "\n")
    (web / "data" / "task-blurbs.json").write_text(json.dumps({
        "source": "test", "tasks": {t: {"title": TITLES[t], "produce": "p", "challenge": "c"} for t in TASKS},
    }))
    add_to_board(web, report("20260101-000000-aaaaaaaa", "gpt-6.2-sol-medium", passes={"beta": False},
                             scores={"alpha": 98.0, "beta": 96.0}), "skills")
    return web


def test_unknown_candidate_is_refused_with_how_to_add_it(site):
    with pytest.raises(SystemExit) as stop:
        bm.main(["--web", str(site), "--model", "gpt-9-nova-medium", "--dry-run"])
    assert "not in eval_runner/models.json" in str(stop.value)
    assert '"pricing"' in str(stop.value)


def test_a_checkout_that_does_not_name_its_board_is_refused(site):
    (site / "src" / "lib" / "current-meta.ts").write_text("export const nothing = 1;\n")
    with pytest.raises(SystemExit, match="does not name the board its home page charts"):
        bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--dry-run"])


def test_dry_run_prints_the_boards_plan_and_estimate_and_spends_nothing(site, tmp_path, monkeypatch, capsys):
    # The basis has claude-opus-5-5-medium's list prices, so its cost carries over unscaled.
    like = write_run(tmp_path / "results", report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-medium", cost=0.10),
                     pricing={"input_per_mtok": 4.0, "output_per_mtok": 20.0})
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("a dry run must not run anything"))
    code = bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--like", str(like), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Dry run: nothing was spent." in out
    assert f"the site's board {BOARD}" in out and "1 attempt per task, provider tools off" in out
    assert "setups: + Marketing Skills\n" in out
    # One attempt at each of two tasks at $0.10, plus the judge's $0.10 a call for two calls.
    assert "about $0.20 in model calls + $0.20 judge = $0.40" in out
    assert "eval.py claude-opus-5-5-medium --split board --repetitions 1 --judge claude-sonnet-5-5 -y" in out
    assert "--tools" not in out and "web search" not in out
    assert str(board_meta(site)) in out
    # plain=1 adds the model only setup, run first, as the board orders them.
    bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--like", str(like),
             "--plain", "--reps", "3", "--dry-run"])
    out = capsys.readouterr().out
    assert "setups: Model only, + Marketing Skills\n" in out
    assert out.index("--split board --no-skills --repetitions 3") < out.index("--split board --repetitions 3")


def test_inside_hands_the_boards_tasks_to_lane_bench(site, tmp_path, capsys):
    magister = tmp_path / "magister"
    bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--inside", "--magister", str(magister),
             "--lane", "bench2", "--dry-run"])
    out = capsys.readouterr().out
    assert "setups: Inside Magister\n" in out
    assert (f"make -C {magister} lane-bench lane=bench2 bench_repo={bm.REPO_ROOT} confirm=RUN_LANE_BENCH "
            "deploy=0 candidate=claude-opus-5-5-medium tasks=alpha,beta repetitions=1 judge=claude-sonnet-5-5") in out
    assert "eval.py" not in out
    with pytest.raises(SystemExit, match="inside=1 runs the Inside Magister setup alone"):
        bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--inside", "--magister", str(magister),
                 "--plain", "--dry-run"])


def test_the_estimate_scales_a_decoy_attempts_cost_over_both_turns_tokens(tmp_path):
    """The report's cost of a decoy task's attempt is both turns, so the
    price ratio that scales it weighs both turns' tokens."""
    run = write_run(tmp_path / "results", report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-medium"))
    rows = [json.loads(line) for line in (run / "attempts.jsonl").read_text().splitlines()]
    rows[0].update(decoy_prompt_sha256="d", decoy_input_tokens=500, decoy_output_tokens=10)
    (run / "attempts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    est = bm.estimate(run, {"input_per_mtok": 1.0, "output_per_mtok": 5.0}, TASKS, 1)
    assert (est["input_tokens"], est["output_tokens"]) == (2500, 410)


def test_only_the_confirmation_word_runs_it(site, tmp_path, monkeypatch, capsys):
    results = tmp_path / "results"
    like = write_run(results, report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-medium"))
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("ran without confirm=SPEND"))
    assert bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--like", str(like), "--confirm", "yes"]) == 2
    # With it, the board's command runs, and the run it made is exported and drafted.
    ran = []

    def fake_run(cmd, cwd=None):
        ran.append(cmd)
        write_run(results, report("20260103-000000-f0f0f0f0", "claude-opus-5-5-medium"))
        return 0

    monkeypatch.setattr(bm, "RESULTS_DIR", results)
    monkeypatch.setattr(bm, "search_dirs", lambda: [results])
    monkeypatch.setattr(subprocess, "call", fake_run)
    assert bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--like", str(like), "--confirm", "SPEND"]) == 0
    assert [c[2:] for c in ran] == [["claude-opus-5-5-medium", "--split", "board", "--repetitions", "1",
                                     "--judge", JUDGE, "-y"]]
    assert meta_of(site)["runs"][-1]["run_id"] == "20260103-000000-f0f0f0f0"
    assert (results / "20260103-000000-f0f0f0f0" / "tweet.txt").read_text().startswith(
        "Claude Opus 5.5 (medium effort) got 2 of 2 marketing tasks fully right")


def test_a_model_already_on_the_board_is_refused_before_spending(site, tmp_path, monkeypatch):
    like = write_run(tmp_path / "results", report("20260102-000000-bbbbbbbb", "gpt-6.2-sol-medium"))
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("spent on a run that export would refuse"))
    with pytest.raises(SystemExit, match="already has 20260101-000000-aaaaaaaa for gpt-6.2-sol-medium"):
        bm.main(["--web", str(site), "--model", "gpt-6.2-sol-medium", "--like", str(like), "--confirm", "SPEND"])
    # As the model only it has no run yet, so plain alone would go ahead; and
    # inside Magister the model has no run either.
    assert bm.already_listed(site, meta_of(site), "gpt-6.2-sol-medium", ["no-skills", "magister"]) == []


def test_a_model_at_another_effort_is_refused_before_spending_and_at_export(site, tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("spent on a run the board refuses"))
    with pytest.raises(SystemExit, match="the board runs every model at medium effort"):
        bm.main(["--web", str(site), "--model", "gpt-6.2-sol-high", "--dry-run"])
    before = board_meta(site).read_text()
    run = write_run(tmp_path / "results", report("20260103-000000-a1a1a1a1", "gpt-6-luna-high"))
    with pytest.raises(SystemExit, match="medium effort"):
        bm.export_run(run, site)
    assert board_meta(site).read_text() == before
    assert not (site / "data" / "runs" / "20260103-000000-a1a1a1a1.json").exists()


def test_a_runner_board_that_is_not_the_sites_is_refused_before_spending(site, runner_board, monkeypatch):
    runner_board.write_text(json.dumps({"areas": [{"id": "one", "title": "One", "tasks": ["alpha", "gamma"]}]}))
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: pytest.fail("spent on the wrong tasks"))
    with pytest.raises(SystemExit, match="only in the runner's: gamma; only on the site's: beta"):
        bm.main(["--web", str(site), "--model", "claude-opus-5-5-medium", "--dry-run"])


def test_export_copies_the_report_unchanged_and_lists_the_run(site, tmp_path):
    # Three attempts per task, one of which ran out of output: the board
    # counts that attempt failed and takes the run.
    rep = report("20260103-000000-cccccccc", "claude-opus-5-5-medium", reps=3, cut={("beta", 2)})
    run = write_run(tmp_path / "results", rep)
    earlier = (site / "data" / "experiments" / EARLIER / "meta.json").read_text()
    entry = bm.export_run(run, site)
    copied = site / "data" / "runs" / "20260103-000000-cccccccc.json"
    assert copied.read_bytes() == (run / "report.json").read_bytes()
    meta = meta_of(site)
    # The shape the site's runs hold, and nothing it does not read.
    assert entry == {"run_id": "20260103-000000-cccccccc", "setup": "skills",
                     "judge_model": JUDGE, "judge_protocol_version": 4}
    assert meta["runs"][-1] == entry
    assert meta["models"] == ["gpt-6.2-sol-medium", "claude-opus-5-5-medium"]
    # The earlier board, which the site's earlier page still reads, is left alone.
    assert (site / "data" / "experiments" / EARLIER / "meta.json").read_text() == earlier
    # Exporting again changes nothing.
    before = board_meta(site).read_text()
    bm.export_run(run, site)
    assert board_meta(site).read_text() == before


def _another_judge(rep, run):
    grading = json.loads((run / "grading.json").read_text())
    (run / "grading.json").write_text(json.dumps({**grading, "judge_model": "claude-sonnet-5"}))


def _retitled(rep, run):
    rep["submissions"][1]["task_title"] = "Beta task, renamed"
    (run / "report.json").write_text(json.dumps(rep))


@pytest.mark.parametrize("change, kwargs, refusal", [
    (_another_judge, {}, "graded by claude-sonnet-5"),
    (None, {"tools": True}, "with the provider's tools on"),
    (None, {"tasks": ["alpha"]}, "lacks the board's tasks beta"),
    (_retitled, {}, "beta is titled"),
    (None, {"lost": {("beta", 1)}}, "lost to a run error: beta attempt 1. .*bench retry --run .*/results/20260103-000000-dddddddd`"),
    (None, {"harness": "claude-code", "skills": False}, "harness 'claude-code'"),
])
def test_export_refuses_what_the_site_refuses_and_changes_nothing(site, tmp_path, change, kwargs, refusal):
    rep = report("20260103-000000-dddddddd", "claude-opus-5-5-medium", **kwargs)
    run = write_run(tmp_path / "results", rep)
    if change:
        change(rep, run)
    before = board_meta(site).read_text()
    with pytest.raises(SystemExit, match=refusal):
        bm.export_run(run, site)
    assert board_meta(site).read_text() == before
    assert not (site / "data" / "runs" / "20260103-000000-dddddddd.json").exists()


def test_export_refuses_a_second_run_of_a_model_in_one_setup(site, tmp_path):
    run = write_run(tmp_path / "results", report("20260103-000000-eeeeeeee", "gpt-6.2-sol-medium"))
    with pytest.raises(SystemExit, match="already has 20260101-000000-aaaaaaaa"):
        bm.export_run(run, site)


def test_export_of_a_magister_run_says_which_test_lane(site, tmp_path):
    rep = report("20260103-000000-ffffffff", "magister-gpt-6.2-sol-medium", harness="magister-agent",
                 skills=False, tools=True)
    run = write_run(tmp_path / "results", rep, identity={"eval_target": "lane:bench", "gateway_sha": "d0afdad5034d895a"})
    entry = bm.export_run(run, site)
    assert entry == {"run_id": "20260103-000000-ffffffff", "setup": "magister", "judge_model": JUDGE,
                     "judge_protocol_version": 4,
                     "ran_on": "a test lane (bench), not production (gateway d0afdad50)"}
    assert meta_of(site)["models"] == ["gpt-6.2-sol-medium"]


def test_export_refuses_a_magister_run_not_made_on_a_test_lane(site, tmp_path):
    rep = report("20260103-000000-abababab", "magister-gpt-6.2-sol-medium", harness="magister-agent", skills=False)
    run = write_run(tmp_path / "results", rep, identity={"eval_target": "canary"})
    with pytest.raises(SystemExit, match="test lane"):
        bm.export_run(run, site)


def test_the_draft_leads_with_tasks_fully_right_never_the_checklist(site, tmp_path):
    results = tmp_path / "results"
    # Both tasks right with the skills, one without; the checklist average
    # (97.9) is not the score and never appears.
    skills = report("20260103-000000-12121212", "claude-opus-5-5-medium", scores={"alpha": 99.0, "beta": 96.8})
    plain = report("20260103-000000-13131313", "claude-opus-5-5-medium", skills=False, passes={"beta": False})
    bm.export_run(write_run(results, skills), site)
    bm.export_run(write_run(results, plain), site)
    text = bm.tweet_for(site, skills["run_id"])
    assert text == (
        "Claude Opus 5.5 (medium effort) got 2 of 2 marketing tasks fully right on the Marketing Benchmark "
        "with the Marketing Skills, 1 without. #1 of 2 models with the skills. One attempt per task.\n"
        "vs GPT-6.2 Sol 1\n"
        f"{URL}20260103-000000-12121212"
    )
    assert "/100" not in text and "97.9" not in text and "%" not in text
    # Alone in its setup, a run has no rank to give.
    assert bm.tweet_for(site, plain["run_id"]) == (
        "Claude Opus 5.5 (medium effort) got 1 of 2 marketing tasks fully right on the Marketing Benchmark "
        "as the model only, 2 with the Marketing Skills. One attempt per task.\n"
        f"{URL}20260103-000000-13131313"
    )


def test_an_export_refreshes_every_runs_draft(site, tmp_path, monkeypatch, capsys):
    results, copy = tmp_path / "results", tmp_path / "other-checkout"
    monkeypatch.setattr(bm, "search_dirs", lambda: [results, copy])
    # The board's run has a folder in two checkouts, each with the draft
    # written when it was the only model.
    old_id = "20260101-000000-aaaaaaaa"
    old = json.loads((site / "data" / "runs" / f"{old_id}.json").read_text())
    stale = [write_run(results, old) / "tweet.txt", write_run(copy, old) / "tweet.txt"]
    for draft in stale:
        draft.write_text("GPT-6.2 Sol (medium effort) got 1 of 2 marketing tasks fully right ...\n")
    new = report("20260103-000000-78787878", "gpt-6-luna-medium")
    run = write_run(results, new)
    bm.main(["--web", str(site), "--export", str(run)])
    assert (run / "tweet.txt").read_text().startswith("GPT-6 Luna (medium effort) got 2 of 2 marketing tasks")
    assert "#1 of 2 models with the skills" in (run / "tweet.txt").read_text()
    for draft in stale:
        assert draft.read_text() == bm.tweet_for(site, old_id) + "\n"
        assert "#2 of 2 models with the skills" in draft.read_text()
    assert "2 changed" in capsys.readouterr().out
    # A second export of the same run finds nothing stale.
    bm.main(["--web", str(site), "--export", str(run)])
    assert "0 changed" in capsys.readouterr().out


def test_a_run_going_at_the_same_time_is_not_taken_for_this_one(tmp_path, monkeypatch):
    results = tmp_path / "results"
    monkeypatch.setattr(bm, "RESULTS_DIR", results)
    marker = time.time() - 1

    def fresh(run_id, cand, skills=True, harness="direct-api"):
        return write_run(results, report(run_id, cand, skills=skills, harness=harness))

    ours = fresh("20260103-000000-90909090", "gpt-6-luna-medium")
    # Started later in the same checkout: another model, and the same model
    # without the skills.
    fresh("20260103-000001-91919191", "gpt-6.2-sol-medium")
    plain = fresh("20260103-000002-92929292", "gpt-6-luna-medium", skills=False)
    # A run that has only begun writing its run.json, and one in a harness
    # the board does not chart, are passed over.
    (results / "20260103-000003-93939393").mkdir()
    (results / "20260103-000003-93939393" / "run.json").write_text('{"models": {"gpt-6-lu')
    fresh("20260103-000004-94949494", "gpt-6-luna-medium", harness="journeys")
    assert bm.newest_run_since(marker, "gpt-6-luna-medium", "skills") == ours
    assert bm.newest_run_since(marker, "gpt-6-luna-medium", "no-skills") == plain
    with pytest.raises(SystemExit, match="no new run folder for gemini-4-neon-medium"):
        bm.newest_run_since(marker, "gemini-4-neon-medium", "skills")


def test_runs_with_as_many_tasks_fully_right_share_a_rank(site, tmp_path):
    # One of two tasks fully right, like the board's GPT-6.2 Sol run: a tie,
    # however far apart their checklist averages are.
    rep = report("20260103-000000-34343434", "gpt-6-luna-medium", passes={"beta": False},
                 scores={"alpha": 60.0, "beta": 40.0})
    bm.export_run(write_run(tmp_path / "results", rep), site)
    assert "Tied #1 of 2 models with the skills." in bm.tweet_for(site, rep["run_id"])
    assert "Tied #1 of 2 models with the skills." in bm.tweet_for(site, "20260101-000000-aaaaaaaa")


def test_the_draft_says_when_the_model_is_also_the_judge(site, tmp_path):
    rep = report("20260103-000000-56565656", "claude-sonnet-5-5-medium")
    bm.export_run(write_run(tmp_path / "results", rep), site)
    text = bm.tweet_for(site, rep["run_id"])
    assert text.startswith("Claude Sonnet 5.5 (medium effort) got 2 of 2 marketing tasks fully right")
    assert "It is also the judge." in text and len(text) <= 280


def test_a_run_ranked_beside_another_number_of_attempts_says_so(site, tmp_path):
    # The board's run made 3 attempts per task; this one makes 1.
    old = json.loads((site / "data" / "runs" / "20260101-000000-aaaaaaaa.json").read_text())
    old["repetitions"] = 3
    (site / "data" / "runs" / "20260101-000000-aaaaaaaa.json").write_text(json.dumps(old))
    rep = report("20260103-000000-c3c3c3c3", "gpt-6-luna-medium")
    bm.export_run(write_run(tmp_path / "results", rep), site)
    text = bm.tweet_for(site, rep["run_id"])
    assert "#1 of 2 models with the skills (made 1 or 3 attempts per task). One attempt per task." in text
    assert len(text) <= 280
    # Three attempts per task are said as what makes a task count.
    assert "3 attempts per task, all 3 right to count." in bm.tweet_for(site, "20260101-000000-aaaaaaaa")


def test_a_long_draft_shortens_its_prose_and_keeps_every_note(site, tmp_path):
    # The judge's own model in all three setups, its Magister run ranked
    # beside a three-attempt one: in full it runs to 334 characters. The
    # benchmark's name goes (307), then the effort (291), then the rank.
    for setup, skills in (("no-skills", False), ("skills", True)):
        add_to_board(site, report(f"20260103-00000{int(skills)}-b0b0b0b0", "claude-sonnet-5-5-medium",
                                  skills=skills, passes={"beta": skills}), setup)
    lane = {"eval_target": "lane:bench", "gateway_sha": "abc"}
    peer = report("20260103-000000-d4d4d4d4", "magister-gpt-6.2-sol-medium", harness="magister-agent",
                  skills=False, reps=3, passes={"beta": False})
    bm.export_run(write_run(tmp_path / "results", peer, identity=lane), site)
    rep = report("20260103-000000-e5e5e5e5", "magister-claude-sonnet-5-5-medium", harness="magister-agent",
                 skills=False)
    bm.export_run(write_run(tmp_path / "results", rep, identity=lane), site)
    text = bm.tweet_for(site, rep["run_id"])
    assert text == (
        "Claude Sonnet 5.5 got 2 of 2 marketing tasks fully right inside Magister, 1 as the model only, "
        "2 with the Marketing Skills. One attempt per task. It is also the judge.\n"
        "vs GPT-6.2 Sol 1\n"
        f"{URL}20260103-000000-e5e5e5e5"
    )
    assert len(text) <= 280


@pytest.mark.parametrize("bench_id, label", [
    ("gpt-6.1-sol-high", "GPT-6.1 Sol"),
    ("gpt-6-astra-high", "GPT-6 Astra"),
    ("claude-opus-5-5-medium", "Claude Opus 5.5"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
    ("gemini-4-neon-medium", "Gemini 4 Neon"),
    ("glm-5.3", "GLM-5.3"),
])
def test_model_names_match_the_site(bench_id, label):
    assert bm.model_label(bench_id) == label
