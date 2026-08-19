"""Offline tests for the MVP eval runner. No provider calls."""

import json

import pytest

from mvp import bench, providers


def test_models_load_and_specs_are_supported():
    models = bench.load_models()
    assert models, "models.json must not be empty"
    for spec in models.values():
        provider, model = providers.split_model_spec(spec["model"])
        assert provider in ("anthropic", "openai")
        assert model


def test_judge_default_exists_in_models():
    assert bench.JUDGE_DEFAULT in bench.load_models()


def test_tasks_load_and_validate():
    tasks = bench.load_tasks()
    assert len(tasks) == 7
    for task in tasks.values():
        for section in bench.RUBRIC_SECTIONS:
            assert task["rubric"][section]


def test_prompt_assembly_includes_fixtures_and_skills():
    tasks = bench.load_tasks()
    task = tasks["headline"]
    with_skills = bench.assemble_prompt(task, include_skills=True)
    without_skills = bench.assemble_prompt(task, include_skills=False)
    assert "Arc Clip Lamp" in with_skills
    assert "Skill guidance you should follow" in with_skills
    assert "Skill guidance you should follow" not in without_skills
    assert task["prompt"].strip() in with_skills


def test_bad_task_rejected(tmp_path):
    path = tmp_path / "broken.json"
    task = {"id": "broken", "title": "x", "prompt": "y",
            "rubric": {"completion": [], "skill_adherence": [], "best_practices": []}}
    path.write_text(json.dumps(task))
    with pytest.raises(ValueError, match="non-empty"):
        bench._validate_task(task, path)


def test_parse_judge_json_variants():
    verdict = {"completed": True, "criteria": [{"id": "a", "pass": True, "evidence": "e"}]}
    raw = json.dumps(verdict)
    assert bench.parse_judge_json(raw) == verdict
    assert bench.parse_judge_json(f"Here you go:\n```json\n{raw}\n```") == verdict
    assert bench.parse_judge_json(f"prefix {raw} suffix") == verdict
    with pytest.raises((ValueError, json.JSONDecodeError)):
        bench.parse_judge_json("not json at all")
    with pytest.raises(ValueError):
        bench.parse_judge_json('{"criteria": "wrong shape"}')


def _judgment(task, model, rep, passes, completed=True):
    return {
        "task_id": task, "model_id": model, "repetition": rep,
        "completed": completed,
        "criteria": [{"id": "c1", "pass": passes, "evidence": ""}],
    }


def test_all_pass_requires_every_repetition():
    attempts = [{"task_id": "t", "model_id": "m", "repetition": r} for r in (1, 2, 3)]
    judgments = [_judgment("t", "m", 1, True), _judgment("t", "m", 2, True),
                 _judgment("t", "m", 3, False)]
    verdicts = bench.attempt_verdicts(attempts, judgments, human=[])
    assert not bench.all_pass("t", "m", 3, verdicts)
    judgments[2] = _judgment("t", "m", 3, True)
    verdicts = bench.attempt_verdicts(attempts, judgments, human=[])
    assert bench.all_pass("t", "m", 3, verdicts)


def test_incomplete_response_fails_even_if_criteria_pass():
    judgment = _judgment("t", "m", 1, True, completed=False)
    assert not bench._judgment_passes(judgment)


def test_run_error_and_missing_judgment_count_as_failures():
    attempts = [
        {"task_id": "t", "model_id": "m", "repetition": 1, "error": "boom"},
        {"task_id": "t", "model_id": "m", "repetition": 2},
        {"task_id": "t", "model_id": "m", "repetition": 3},
    ]
    judgments = [_judgment("t", "m", 2, True)]  # rep 3 never judged
    verdicts = bench.attempt_verdicts(attempts, judgments, human=[])
    assert verdicts[("t", "m", 1)] == {"pass": False, "source": "run-error"}
    assert not bench.all_pass("t", "m", 3, verdicts)


def test_human_override_beats_judge():
    attempts = [{"task_id": "t", "model_id": "m", "repetition": 1}]
    judgments = [_judgment("t", "m", 1, False)]
    human = [{"task_id": "t", "model_id": "m", "repetition": 1,
              "human_pass": True, "agreed_with_judge": False, "note": ""}]
    verdicts = bench.attempt_verdicts(attempts, judgments, human)
    assert verdicts[("t", "m", 1)] == {"pass": True, "source": "human"}
    assert bench.all_pass("t", "m", 1, verdicts)


def test_judge_prompt_contains_rubric_and_measurements():
    task = bench.load_tasks()["ad-performance-analysis"]
    prompt = bench.build_judge_prompt(task, "some response", {"word_count": 42})
    assert "totals_correct" in prompt
    assert "word_count: 42" in prompt
    assert "<response>" in prompt
    # oracle numbers reach the judge through the rubric criteria
    assert "$17.39" in prompt


def test_ad_performance_csv_oracle_totals():
    """The planted findings in the CSV must match the rubric's oracle numbers."""
    import csv as _csv
    path = bench.REPO_ROOT / "mvp/fixtures/ad-performance/campaigns.csv"
    rows = list(_csv.DictReader(path.read_text().splitlines()))
    assert len(rows) == 16
    totals: dict[str, dict[str, float]] = {}
    missing = 0
    for row in rows:
        bucket = totals.setdefault(row["campaign"], {"spend": 0.0, "conv": 0.0})
        bucket["spend"] += float(row["spend_usd"])
        if row["conversions"] == "":
            missing += 1
        else:
            bucket["conv"] += float(row["conversions"])
            # revenue is priced at the fixture's $68 everywhere it exists
            assert float(row["revenue_usd"]) == float(row["conversions"]) * 68
    assert missing == 1
    broad = totals["Prospecting - Broad"]
    interest = totals["Prospecting - Small-Space Interest"]
    retargeting = totals["Retargeting - 30d Engagers"]
    assert (broad["spend"], broad["conv"]) == (4800, 169)
    assert round(broad["spend"] / broad["conv"], 2) == 28.40
    assert (interest["spend"], interest["conv"]) == (2400, 138)
    assert round(interest["spend"] / interest["conv"], 2) == 17.39
    assert (retargeting["spend"], retargeting["conv"]) == (1600, 83)
    assert round(retargeting["spend"] / retargeting["conv"], 2) == 19.28


def test_provider_refuses_without_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(providers.ProviderError, match="ANTHROPIC_API_KEY"):
        providers.generate("anthropic/claude-sonnet-5", "hi", 100)


def test_provider_rejects_unknown_spec():
    with pytest.raises(providers.ProviderError, match="unsupported model spec"):
        providers.split_model_spec("gemini/some-model")
