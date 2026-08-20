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


def test_build_request_anthropic_tool_versions():
    url, headers, body = providers.build_request(
        "anthropic/claude-sonnet-5", "hi", 100, web_search=True, api_key="k")
    assert url == providers.ANTHROPIC_URL
    assert headers["x-api-key"] == "k"
    assert body["tools"] == [{"type": "web_search_20260209", "name": "web_search",
                              "max_uses": providers.WEB_SEARCH_MAX_USES}]
    _, _, body = providers.build_request(
        "anthropic/claude-haiku-4-5", "hi", 100, web_search=True, api_key="k")
    assert body["tools"][0]["type"] == "web_search_20250305"
    _, _, body = providers.build_request(
        "anthropic/claude-sonnet-5", "hi", 100, web_search=False, api_key="k")
    assert "tools" not in body
    assert "temperature" not in body
    assert body["max_tokens"] == 100


def test_build_request_openai_responses_api():
    url, headers, body = providers.build_request(
        "openai/gpt-5.6-sol", "hi", 100, web_search=True, api_key="k")
    assert url == providers.OPENAI_URL and url.endswith("/v1/responses")
    assert headers["Authorization"] == "Bearer k"
    assert body == {"model": "gpt-5.6-sol",
                    "input": "hi", "tools": [{"type": "web_search"}]}
    _, _, body = providers.build_request(
        "openai/gpt-5.6-sol", "hi", 100, web_search=False, api_key="k")
    assert "tools" not in body and "temperature" not in body
    # No artificial output cap unless the candidate sets one: reasoning
    # tokens count against max_output_tokens, so a default cap can starve
    # the visible answer. The Anthropic default still applies (required).
    assert "max_output_tokens" not in body


def test_parse_response_anthropic_with_web_search():
    payload = {
        "content": [
            {"type": "server_tool_use", "id": "x", "name": "web_search"},
            {"type": "web_search_tool_result", "tool_use_id": "x", "content": []},
            {"type": "text", "text": "part one "},
            {"type": "text", "text": "part two"},
        ],
        "usage": {"input_tokens": 10, "output_tokens": 20,
                  "server_tool_use": {"web_search_requests": 3}},
    }
    result = providers.parse_response("anthropic", payload)
    assert result == {"text": "part one part two", "input_tokens": 10,
                      "output_tokens": 20, "web_search_calls": 3,
                      "tool_calls": {"web_search": 1},
                      "finish_reason": None}


def test_parse_response_openai_with_web_search():
    payload = {
        "output": [
            {"type": "web_search_call", "id": "ws1", "status": "completed"},
            {"type": "web_search_call", "id": "ws2", "status": "completed"},
            {"type": "message", "content": [
                {"type": "output_text", "text": "answer"},
            ]},
        ],
        "usage": {"input_tokens": 5, "output_tokens": 7},
    }
    result = providers.parse_response("openai", payload)
    assert result == {"text": "answer", "input_tokens": 5,
                      "output_tokens": 7, "web_search_calls": 2,
                      "tool_calls": {"web_search": 2},
                      "finish_reason": None}


def test_parse_response_captures_all_tool_kinds():
    # Tool use is not only web search: every invoked tool is counted by name.
    openai_payload = {
        "output": [
            {"type": "web_search_call", "id": "ws1"},
            {"type": "code_interpreter_call", "id": "ci1"},
            {"type": "code_interpreter_call", "id": "ci2"},
            {"type": "function_call", "name": "lookup_prices", "id": "f1"},
            {"type": "message", "content": [{"type": "output_text", "text": "ok"}]},
        ],
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }
    result = providers.parse_response("openai", openai_payload)
    assert result["tool_calls"] == {"web_search": 1, "code_interpreter": 2,
                                    "lookup_prices": 1}
    assert result["web_search_calls"] == 1
    anthropic_payload = {
        "content": [
            {"type": "server_tool_use", "id": "a", "name": "web_search"},
            {"type": "server_tool_use", "id": "b", "name": "code_execution"},
            {"type": "text", "text": "ok"},
        ],
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }
    result = providers.parse_response("anthropic", anthropic_payload)
    assert result["tool_calls"] == {"web_search": 1, "code_execution": 1}
    assert result["web_search_calls"] == 1  # falls back to invocation count


def test_candidate_settings_reach_openai_request():
    _, _, body = providers.build_request(
        "openai/gpt-5.6-luna", "hi", 16000, web_search=False, api_key="k",
        settings={"reasoning_effort": "xhigh", "text_verbosity": "medium"})
    assert body["reasoning"] == {"effort": "xhigh"}
    assert body["text"] == {"verbosity": "medium"}
    _, _, body = providers.build_request(
        "openai/gpt-5.6-luna", "hi", 16000, web_search=False, api_key="k",
        settings={"reasoning_effort": "max"})
    assert body["reasoning"] == {"effort": "max"}
    assert "text" not in body


def test_candidate_settings_validated():
    with pytest.raises(providers.ProviderError, match="invalid reasoning_effort"):
        providers.build_request("openai/gpt-5.6-luna", "hi", 1, False, "k",
                                settings={"reasoning_effort": "ultra"})
    with pytest.raises(providers.ProviderError, match="unknown candidate settings"):
        providers.build_request("openai/gpt-5.6-luna", "hi", 1, False, "k",
                                settings={"temperature": 0})
    with pytest.raises(providers.ProviderError, match="OpenAI-only"):
        providers.build_request("anthropic/claude-sonnet-5", "hi", 1, False, "k",
                                settings={"reasoning_effort": "high"})


def test_finish_reason_surfaces_truncation():
    anthropic_payload = {"content": [{"type": "text", "text": "cut off"}],
                         "usage": {"input_tokens": 1, "output_tokens": 2},
                         "stop_reason": "max_tokens"}
    assert providers.parse_response("anthropic", anthropic_payload)["finish_reason"] == "max_tokens"
    openai_payload = {"output": [{"type": "message", "content": [
                          {"type": "output_text", "text": "cut off"}]}],
                      "usage": {"input_tokens": 1, "output_tokens": 2},
                      "status": "incomplete",
                      "incomplete_details": {"reason": "max_output_tokens"}}
    assert providers.parse_response("openai", openai_payload)["finish_reason"] == \
        "incomplete:max_output_tokens"


def test_candidate_manifest_shape():
    models = bench.load_models()
    for candidate_id, model_spec, effort in (
        ("gpt-5.6-luna-medium", "openai/gpt-5.6-luna", "medium"),
        ("gpt-5.6-luna-xhigh", "openai/gpt-5.6-luna", "xhigh"),
        ("gpt-5.6-luna-max", "openai/gpt-5.6-luna", "max"),
        ("gpt-5.6-terra-medium", "openai/gpt-5.6-terra", "medium"),
        ("gpt-5.6-sol-medium", "openai/gpt-5.6-sol", "medium"),
    ):
        assert models[candidate_id]["model"] == model_spec
        assert models[candidate_id]["reasoning_effort"] == effort
    for candidate_id, spec in models.items():
        # Every candidate must carry real pricing so cost never silently
        # reports n/a, and none may cap output ("let the model work").
        assert spec["pricing"]["input_per_mtok"] > 0, candidate_id
        assert spec["pricing"]["output_per_mtok"] > 0, candidate_id
        assert "max_output_tokens" not in spec, candidate_id


def test_max_output_tokens_override_and_validation():
    _, _, body = providers.build_request(
        "openai/gpt-5.6-luna", "hi", 16000, web_search=False, api_key="k",
        settings={"max_output_tokens": 64000})
    assert body["max_output_tokens"] == 64000
    _, _, body = providers.build_request(
        "anthropic/claude-sonnet-5", "hi", 16000, web_search=False, api_key="k",
        settings={"max_output_tokens": 32000})
    assert body["max_tokens"] == 32000  # allowed on anthropic, unlike effort
    with pytest.raises(providers.ProviderError, match="invalid max_output_tokens"):
        providers.build_request("openai/gpt-5.6-luna", "hi", 1, False, "k",
                                settings={"max_output_tokens": "lots"})


def test_ceiling_retry_doubles_cap_once(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def fake_post(url, headers, body, provider):
        calls.append(body)
        if len(calls) == 1:
            return {"output": [], "usage": {}, "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"}}
        return {"output": [{"type": "message", "content": [
                    {"type": "output_text", "text": "recovered"}]}],
                "usage": {"input_tokens": 1, "output_tokens": 2},
                "status": "completed"}

    monkeypatch.setattr(providers, "_post_json_with_retries", fake_post)
    result = providers.generate("openai/gpt-5.6-luna", "hi", 16000,
                                settings={"reasoning_effort": "max",
                                          "max_output_tokens": 32000})
    assert [c["max_output_tokens"] for c in calls] == [32000, 64000]
    assert result["text"] == "recovered"
    assert result["ceiling_retried"] is True
    assert calls[1]["reasoning"] == {"effort": "max"}  # other settings preserved


def test_ceiling_retry_gives_up_after_one_doubling(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    incomplete = {"output": [], "usage": {}, "status": "incomplete",
                  "incomplete_details": {"reason": "max_output_tokens"}}
    monkeypatch.setattr(providers, "_post_json_with_retries",
                        lambda *args: dict(incomplete))
    with pytest.raises(providers.ProviderError, match="ceiling_retried=True"):
        providers.generate("openai/gpt-5.6-luna", "hi", 16000,
                           settings={"max_output_tokens": 16000})


def test_uncapped_truncation_never_retries(monkeypatch):
    # With no explicit cap the request is bounded only by the model's own
    # maximum; doubling cannot help, so the failure is recorded honestly
    # in a single call.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def fake_post(url, headers, body, provider):
        calls.append(body)
        return {"output": [], "usage": {}, "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"}}

    monkeypatch.setattr(providers, "_post_json_with_retries", fake_post)
    with pytest.raises(providers.ProviderError, match="ceiling_retried=False"):
        providers.generate("openai/gpt-5.6-luna", "hi", 16000)
    assert len(calls) == 1
    assert "max_output_tokens" not in calls[0]


def test_attempt_mark_letters():
    assert bench.attempt_mark({"error": "boom"}, None) == "E"
    assert bench.attempt_mark({"finish_reason": "incomplete:max_output_tokens"}, {"pass": False}) == "T"
    assert bench.attempt_mark({"finish_reason": "completed"}, {"pass": True}) == "P"
    assert bench.attempt_mark({"finish_reason": "end_turn"}, {"pass": False}) == "F"
    assert bench.attempt_mark(None, None) == "F"  # never attempted


def test_model_efficiency_pools_criteria_on_normal_finishes_only():
    attempts = [
        {"task_id": "t", "model_id": "m", "repetition": 1,
         "finish_reason": "completed", "latency_seconds": 10.0, "output_tokens": 100},
        {"task_id": "t", "model_id": "m", "repetition": 2,
         "finish_reason": "incomplete:max_output_tokens", "latency_seconds": 30.0,
         "output_tokens": 900},
    ]
    judgments = [
        {"task_id": "t", "model_id": "m", "repetition": 1, "completed": True,
         "criteria": [{"id": "a", "pass": True, "evidence": ""},
                      {"id": "b", "pass": False, "evidence": ""}]},
        {"task_id": "t", "model_id": "m", "repetition": 2, "completed": True,
         "criteria": [{"id": "a", "pass": False, "evidence": ""}]},  # truncated: excluded
    ]
    models_meta = {"m": {"model": "anthropic/x",
                         "pricing": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}}
    for a in attempts:
        a["input_tokens"] = 1000
    section_of = {("t", "a"): "completion", ("t", "b"): "best_practices"}
    stats = bench.model_efficiency(["m"], attempts, judgments, models_meta, section_of)["m"]
    assert stats["completed_attempts"] == 2
    assert stats["mean_latency_seconds"] == 20.0
    assert stats["total_output_tokens"] == 1000
    assert (stats["criteria_passed"], stats["criteria_judged"]) == (1, 2)
    assert stats["criterion_pass_rate"] == 0.5
    # 2 attempts x (1000 in x $1/M + (100|900) out x $5/M)
    assert stats["cost_usd"] == round((1000 * 1 + 100 * 5 + 1000 * 1 + 900 * 5) / 1e6, 4)
    assert stats["section_pass_rates"] == {
        "completion": 1.0, "skill_adherence": None, "best_practices": 0.0}


def test_attempt_cost_requires_pricing():
    attempt = {"input_tokens": 1000, "output_tokens": 1000}
    assert bench.attempt_cost_usd(attempt, {"model": "openai/x"}) is None
    spec = {"pricing": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}}
    assert bench.attempt_cost_usd(attempt, spec) == 0.018
    assert bench.attempt_cost_usd({"error": "boom"}, spec) is None


def test_criterion_tally_excludes_truncated_attempts():
    judgments = [
        _judgment("t", "m", 1, False),  # normal finish: counts
        _judgment("t", "m", 2, False),  # truncated: excluded
    ]
    attempts_by_key = {
        ("t", "m", 1): {"finish_reason": "completed"},
        ("t", "m", 2): {"finish_reason": "incomplete:max_output_tokens"},
    }
    verdicts = {("t", "m", 1): {"pass": False, "source": "judge"},
                ("t", "m", 2): {"pass": False, "source": "judge"}}
    counts = bench.criterion_failure_counts(judgments, verdicts, attempts_by_key)
    assert counts == {("t", "c1"): 1}


def test_report_scoreboard_and_json(tmp_path, capsys):
    """End-to-end cmd_report on a synthetic 1-task, 1-model, 2-rep run."""
    run_dir = tmp_path / "run1"
    (run_dir / "responses").mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "run1", "created_at": "x",
        "models": {"claude-haiku-4-5": {
            "model": "anthropic/claude-haiku-4-5",
            "pricing": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}},
        "tasks": ["headline"], "repetitions": 2, "skills_included": True,
        "tools_enabled": False, "max_output_tokens": 16000,
        "temperature": "omitted", "protocol": "all-pass",
    }))
    attempts = [
        {"run_id": "run1", "task_id": "headline", "model_id": "claude-haiku-4-5",
         "repetition": r, "skills_included": True, "tools_enabled": False,
         "prompt_sha256": "h", "finish_reason": "end_turn",
         "latency_seconds": 5.0, "input_tokens": 1000, "output_tokens": 1000,
         "web_search_calls": 0, "response_path": "responses/x.md"}
        for r in (1, 2)
    ]
    judgments = [
        {"task_id": "headline", "model_id": "claude-haiku-4-5", "repetition": r,
         "judge_model": "claude-sonnet-5", "completed": True,
         "criteria": [{"id": "five_options", "pass": True, "evidence": ""}]}
        for r in (1, 2)
    ]
    (run_dir / "attempts.jsonl").write_text(
        "".join(json.dumps(a) + "\n" for a in attempts))
    (run_dir / "judgments.jsonl").write_text(
        "".join(json.dumps(j) + "\n" for j in judgments))

    (run_dir / "prompts").mkdir()
    (run_dir / "prompts" / "headline.md").write_text("the prompt")
    (run_dir / "responses" / "headline--claude-haiku-4-5--r1.md").write_text("answer")

    import argparse
    assert bench.cmd_report(argparse.Namespace(run=str(run_dir))) == 0
    report = (run_dir / "report.md").read_text()
    assert "## Scoreboard" in report
    assert "**1/1 (100%)**" in report
    assert "[prompt](prompts/headline.md)" in report
    assert "[r1 P](responses/headline--claude-haiku-4-5--r1.md)" in report
    assert "r2 P" in report  # response file absent -> plain mark, no dead link
    assert "$0.01" in report  # 2 x (1000x$1 + 1000x$5)/1M = $0.012
    summary = json.loads((run_dir / "report.json").read_text())
    model = summary["models"]["claude-haiku-4-5"]
    assert model["tasks_passed"] == 1
    assert model["task_passes"] == {"headline": True}
    assert model["cost_usd"] == 0.012
    assert summary["run_health"]["provider_errors"] == 0


def test_provider_refuses_without_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(providers.ProviderError, match="ANTHROPIC_API_KEY"):
        providers.generate("anthropic/claude-sonnet-5", "hi", 100)


def test_provider_rejects_unknown_spec():
    with pytest.raises(providers.ProviderError, match="unsupported model spec"):
        providers.split_model_spec("gemini/some-model")


def test_run_writes_prompts_and_responses(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(
        bench.providers, "generate",
        lambda *args, **kwargs: {
            "provider": "anthropic", "model": "claude-haiku-4-5",
            "text": "the submission", "input_tokens": 10, "output_tokens": 20,
            "web_search_calls": 0, "finish_reason": "end_turn",
            "ceiling_retried": False, "latency_seconds": 0.1,
        },
    )
    import argparse
    args = argparse.Namespace(models="claude-haiku-4-5", tasks="headline",
                              repetitions=2, no_skills=False, tools=False, yes=True)
    assert bench.cmd_run(args) == 0
    run_dir = next(tmp_path.iterdir())
    assert (run_dir / "prompts" / "headline.md").read_text().startswith(
        "You are the copywriter for Cedar & Coil")
    for rep in (1, 2):
        path = run_dir / "responses" / f"headline--claude-haiku-4-5--r{rep}.md"
        assert path.read_text() == "the submission"
    attempts = [json.loads(l) for l in (run_dir / "attempts.jsonl").read_text().splitlines()]
    assert len(attempts) == 2 and all("error" not in a for a in attempts)
