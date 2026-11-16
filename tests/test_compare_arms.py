"""Offline tests for scripts/compare-arms.py: graded runs side by side."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare-arms.py"


@pytest.fixture(scope="module")
def compare():
    spec = importlib.util.spec_from_file_location("compare_arms", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(tmp_path, name, scores, *, passes, judge="judge-a", repetitions=2, cost_key="provider_cost_usd"):
    """A graded run directory: `scores` is task -> score, `passes` is task -> runs passed."""
    run_dir = tmp_path / name
    run_dir.mkdir()
    attempts = [
        {"task_id": task, "repetition": rep, "latency_seconds": 10.0 * rep, "llm_calls": 2,
         "tool_calls": {"Bash": 1}, "skill_reads": ["analytics"] if task == "ledger" else [], cost_key: 0.25}
        for task in scores for rep in range(1, repetitions + 1)
    ]
    (run_dir / "attempts.jsonl").write_text("".join(json.dumps(attempt) + "\n" for attempt in attempts))
    (run_dir / "grading.json").write_text(json.dumps({"judge_model": judge}))
    (run_dir / "report.json").write_text(json.dumps({
        "run_id": name, "harness": "test", "repetitions": repetitions, "tasks": list(scores),
        "models": {"m": {
            "composite_score": round(sum(scores.values()) / len(scores), 1),
            "tasks_passed": sum(1 for task in scores if passes[task] == repetitions),
            "tasks_total": len(scores), "runs_passed": sum(passes.values()),
            "runs_total": repetitions * len(scores), "task_scores": scores,
            "candidate_cost_usd": 9.99, "candidate_cost_complete": True,
        }},
        "submissions": [
            {"task_id": task, "model_id": "m",
             "runs": [{"pass": rep <= passes[task]} for rep in range(1, repetitions + 1)]}
            for task in scores
        ],
    }))
    return run_dir


def test_a_whole_run_is_reported_as_its_report_has_it(compare, tmp_path):
    arm = compare.load_arm("A", _run(tmp_path, "a", {"ledger": 80.0, "headline": 100.0},
                                     passes={"ledger": 1, "headline": 2}))
    assert (arm["composite"], arm["tasks_passed"], arm["tasks_total"]) == (90.0, 1, 2)
    assert (arm["runs_passed"], arm["runs_total"], arm["errors"]) == (3, 4, 0)
    assert arm["cost_usd"] == 9.99  # the report's own price for the run
    assert arm["seconds_per_attempt"] == 15.0 and arm["attempts_reading_a_skill"] == 2


def test_shared_tasks_work_every_figure_out_again_over_those_tasks(compare, tmp_path, capsys):
    ours = _run(tmp_path, "ours", {"ledger": 60.0, "headline": 100.0, "decoy": 0.0},
                passes={"ledger": 1, "headline": 2, "decoy": 0}, cost_key="gateway_provider_cost_usd")
    theirs = _run(tmp_path, "theirs", {"ledger": 80.0, "headline": 90.0}, passes={"ledger": 2, "headline": 1})

    with pytest.raises(SystemExit, match="ran different tasks: decoy"):
        compare.main(["--arm", f"Theirs={theirs}", "--arm", f"Ours={ours}"])

    assert compare.main(["--arm", f"Theirs={theirs}", "--arm", f"Ours={ours}", "--shared-tasks"]) == 0
    out = capsys.readouterr().out
    assert "| Score (0-100) | **85.0** | **80.0** |" in out       # ours without the task only it ran
    assert "| Tasks passed on all 2 runs | 1/2 | 1/2 |" in out
    assert "| Cost, whole run | $1.00 | $1.00 |" in out            # four attempts' own costs, not the run's
    assert "| decoy |" not in out
    assert "Not every arm ran, so left out: decoy." in out
    assert "| Theirs | -5.0 | 1 / 0 / 1 |" in out


def test_runs_graded_differently_are_refused(compare, tmp_path):
    first = _run(tmp_path, "first", {"ledger": 80.0}, passes={"ledger": 2})
    other_judge = _run(tmp_path, "other-judge", {"ledger": 80.0}, passes={"ledger": 2}, judge="judge-b")
    with pytest.raises(SystemExit, match="differ in judge"):
        compare.main(["--arm", f"A={first}", "--arm", f"B={other_judge}"])
    ungraded = tmp_path / "ungraded"
    ungraded.mkdir()
    with pytest.raises(SystemExit, match="report.json is missing"):
        compare.main(["--arm", f"A={first}", "--arm", f"B={ungraded}"])


def test_the_difference_is_tested_over_tasks(compare):
    # Four tasks all one point ahead: 2 of the 16 sign patterns are as extreme.
    assert compare.paired_permutation([1.0, 1.0, 1.0, 1.0]) == pytest.approx(2 / 16)
    assert compare.paired_permutation([0.0, 0.0]) == 1.0
    # More tasks than the exact test enumerates: seeded, so the same every time.
    many = [1.0] * 20
    assert compare.paired_permutation(many) == compare.paired_permutation(many) < 0.001
    result = compare.versus(
        {"label": "Ours", "tasks": ["a", "b", "c"], "task_scores": {"a": 100.0, "b": 90.0, "c": 50.0}},
        {"label": "Theirs", "tasks": ["a", "b", "c"], "task_scores": {"a": 90.0, "b": 90.0, "c": 60.0}},
    )
    assert (result["tasks_ahead"], result["tasks_level"], result["tasks_behind"]) == (1, 1, 1)
    assert result["mean_difference"] == 0.0 and result["p_value"] == 1.0
