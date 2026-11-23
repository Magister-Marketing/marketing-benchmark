"""An attempt whose model spent its whole output allowance is a failed
attempt by the model, not a run error: offline, with recorded receipts."""
import argparse
import hashlib
import json

import pytest

from eval_runner import bench, providers

LIMIT = "incomplete:max_output_tokens"
# What 05dcffe recorded for Gemini 4 Neon on test-plan-sizing (2026-11-23):
# both calls of a ceiling retry spent their allowance and returned no text.
EMPTY_AT_LIMIT = {
    "error": "openrouter returned an empty completion for google/gemini-4-neon "
             f"(finish_reason='{LIMIT}', ceiling_retried=True)",
    "finish_reason": LIMIT, "ceiling_retried": True, "cost_unknown": True,
    "dispatched": True, "input_tokens": 39376, "output_tokens": 131072,
    "provider_cost_usd": 2.084208, "resolved_model": "google/gemini-4-neon",
    "resolved_provider": "Google", "response_id": "gen-2",
}
TRANSPORT = {"error": "openrouter request failed after 3 retries: timed out",
             "cost_unknown": True, "dispatched": True}


def _run(tmp_path, attempts, judgments=()):
    run_dir = tmp_path / "run"
    (run_dir / "responses").mkdir(parents=True)
    (run_dir / "prompts").mkdir()
    (run_dir / "prompts" / "headline.md").write_text("the prompt")
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "run", "created_at": "x",
        "models": {"m": {"model": "openrouter/google/gemini-4-neon",
                         "pricing": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}}},
        "tasks": ["headline"], "repetitions": len(attempts), "skills_included": False,
        "tools_enabled": False, "max_output_tokens": 65536,
    }))
    rows = []
    for repetition, attempt in enumerate(attempts, start=1):
        row = {"run_id": "run", "task_id": "headline", "model_id": "m",
               "repetition": repetition, "prompt_sha256": "h", **attempt}
        if "text" in row:
            path = f"responses/headline--m--r{repetition}.md"
            (run_dir / path).write_text(row.pop("text"))
            row["response_path"] = path
        rows.append(row)
    (run_dir / "attempts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (run_dir / "judgments.jsonl").write_text("".join(json.dumps(j) + "\n" for j in judgments))
    return run_dir


def _judgment(repetition, passed):
    return {"task_id": "headline", "model_id": "m", "repetition": repetition,
            "judge_model": "claude-sonnet-5", "completed": True,
            "criteria": [{"id": "five_options", "pass": passed, "evidence": "x"}]}


def test_an_attempt_that_spent_its_output_allowance_is_a_failed_attempt_not_a_run_error(tmp_path):
    cut_off = {"text": "A partial answer that stopped", "finish_reason": LIMIT,
               "output_tokens": 131091, "provider_cost_usd": 2.203461,
               "latency_seconds": 637.0}
    run_dir = _run(tmp_path, [EMPTY_AT_LIMIT, cut_off, TRANSPORT],
                   # A judge never makes an answer that ran out of output right.
                   judgments=[_judgment(2, True)])
    assert bench.cmd_report(argparse.Namespace(run=str(run_dir))) == 0
    report = json.loads((run_dir / "report.json").read_text())
    (submission,) = report["submissions"]
    empty, partial, lost = submission["runs"]

    assert empty["mark"] == "T"
    assert empty["pass"] is False
    assert empty["provider_error"] is False
    assert empty["verdict_source"] == "output-limit"
    assert empty["finish_reason"] == LIMIT
    assert empty["output_limit_reached"] is True
    assert empty["cost_usd"] == 2.084208
    assert empty["cost_unknown"] is False

    assert partial["mark"] == "T"
    assert partial["pass"] is False
    assert partial["output_limit_reached"] is True
    assert partial["cost_unknown"] is False

    assert lost["mark"] == "E"
    assert lost["provider_error"] is True
    assert lost["verdict_source"] == "run-error"
    assert lost["output_limit_reached"] is False

    stats = report["models"]["m"]
    assert stats["candidate_cost_usd"] == round(2.084208 + 2.203461, 4)
    # Only the transport failure's cost is unknown.
    assert stats["cost_unknown_attempts"] == 1
    assert stats["runs_passed"] == 0
    assert stats["completed_responses"] == 2
    markdown = (run_dir / "report.md").read_text()
    assert "spent its whole output allowance" in markdown
    assert "spent its whole output allowance" in (run_dir / "report.html").read_text()


def test_the_classification_reads_old_and_new_records_and_keeps_real_errors():
    assert bench.output_limit_reached(EMPTY_AT_LIMIT)
    assert not bench.run_error(EMPTY_AT_LIMIT)
    assert bench.output_limit_reached({"finish_reason": "max_tokens"})
    assert bench.output_limit_reached({"finish_reason": "max_tokens", "error":
                                       "provider returned an empty completion; no retry dispatched"})
    # A decoy task whose earlier turn ran out: the task prompt was never sent.
    assert bench.output_limit_reached({
        "decoy_finish_reason": LIMIT,
        "error": "decoy turn: the reply did not finish normally "
                 f"(finish_reason='{LIMIT}'); the task prompt was not sent"})
    assert not bench.output_limit_reached(TRANSPORT)
    assert bench.run_error(TRANSPORT)
    # Any other error stays a run error, whatever the finish reason says.
    route = {"finish_reason": LIMIT,
             "error": "provider-returned route is outside the allowed policy"}
    assert bench.run_error(route) and not bench.output_limit_reached(route)
    # An empty reply that finished normally is still a run error.
    assert bench.run_error({"finish_reason": "stop", "error":
                            "provider returned an empty completion; no retry dispatched"})
    assert bench.attempt_mark(EMPTY_AT_LIMIT, {"pass": False}) == "T"
    assert bench.attempt_mark(TRANSPORT, {"pass": False}) == "E"


def _retry_run(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "prompts").mkdir(parents=True)
    (run_dir / "responses").mkdir()
    (run_dir / "prompts" / "t.md").write_text("hello prompt")
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "run", "tasks": ["t"], "skills_included": True, "tools_enabled": False,
        "models": {"m": {"model": "openrouter/google/gemini-4-neon"}},
        "max_output_tokens": 65536,
    }))
    sha = hashlib.sha256(b"hello prompt").hexdigest()
    rows = [{"task_id": "t", "model_id": "m", "repetition": 1, "prompt_sha256": sha, **EMPTY_AT_LIMIT},
            {"task_id": "t", "model_id": "m", "repetition": 2, "prompt_sha256": sha, **TRANSPORT}]
    (run_dir / "attempts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return run_dir


def test_retry_never_selects_an_attempt_that_spent_its_output_allowance(tmp_path, monkeypatch):
    run_dir = _retry_run(tmp_path)
    calls = []

    def fake_generate(model_spec, prompt, max_output_tokens, web_search=False, settings=None):
        calls.append(prompt)
        return {"text": "an answer", "input_tokens": 10, "output_tokens": 20,
                "provider_cost_usd": .01, "finish_reason": "stop",
                "ceiling_retried": False, "latency_seconds": 1.0}

    monkeypatch.setattr(bench.providers, "generate", fake_generate)
    assert bench.cmd_retry(argparse.Namespace(run=str(run_dir), yes=True)) == 0
    assert calls == ["hello prompt"]  # the transport failure only
    limited, recovered = bench._read_jsonl(run_dir / "attempts.jsonl")
    assert limited == {"task_id": "t", "model_id": "m", "repetition": 1,
                       "prompt_sha256": limited["prompt_sha256"], **EMPTY_AT_LIMIT}
    assert "error" not in recovered and recovered["retried"] is True
    # The failed call's flag does not outlive the answer that replaced it.
    assert "cost_unknown" not in recovered


def test_a_retry_that_runs_out_of_output_keeps_its_receipt(tmp_path, monkeypatch):
    run_dir = _retry_run(tmp_path)
    receipt = {k: v for k, v in EMPTY_AT_LIMIT.items() if k not in ("error", "cost_unknown", "dispatched")}

    def fake_generate(*args, **kwargs):
        raise providers.ProviderError("openrouter returned an empty completion for google/x "
                                      f"(finish_reason='{LIMIT}', ceiling_retried=True)",
                                      receipt={**receipt, "latency_seconds": 600.0},
                                      failure_kind="empty_completion")

    monkeypatch.setattr(bench.providers, "generate", fake_generate)
    # Nothing is left to retry: the model's own miss is an outcome, not an error.
    assert bench.cmd_retry(argparse.Namespace(run=str(run_dir), yes=True)) == 0
    _limited, retried = bench._read_jsonl(run_dir / "attempts.jsonl")
    assert retried["latency_seconds"] == 600.0
    assert bench.output_limit_reached(retried) and not bench.run_error(retried)


def _run_args(**changes):
    values = dict(models="gemini-4-neon-medium", tasks="headline,ad-creatives",
                  repetitions=1, no_skills=True, tools=False, yes=True)
    return argparse.Namespace(**{**values, **changes})


def test_a_new_run_records_the_miss_with_its_cost_and_time(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    receipt = {"text": "", "input_tokens": 100, "output_tokens": 131072,
               "provider_cost_usd": 2.0, "finish_reason": LIMIT, "ceiling_retried": True,
               "latency_seconds": 640.0}

    def fake_generate(*args, **kwargs):
        raise providers.ProviderError("openrouter returned an empty completion for google/x "
                                      f"(finish_reason='{LIMIT}', ceiling_retried=True)",
                                      receipt=dict(receipt), failure_kind="empty_completion")

    monkeypatch.setattr(bench.providers, "generate", fake_generate)
    # The run did not fail: both attempts are the model's.
    assert bench.cmd_run(_run_args()) == 0
    run = next(tmp_path.iterdir())
    rows = bench._read_jsonl(run / "attempts.jsonl")
    assert len(rows) == 2
    for row in rows:
        assert row["latency_seconds"] == 640.0
        assert row["cost_unknown"] is False
        assert bench.output_limit_reached(row) and not bench.run_error(row)


def test_a_strict_run_carries_on_past_a_model_that_ran_out_of_output(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs)
        return {"text": "", "provider": "openrouter", "model": "google/gemini-4-neon",
                "resolved_model": "google/gemini-4-neon", "resolved_provider": "Google",
                "response_id": "gen-x", "input_tokens": 10, "output_tokens": 65536,
                "provider_cost_usd": 1.0, "finish_reason": LIMIT, "latency_seconds": 300.0}

    monkeypatch.setattr(bench.providers, "generate", fake_generate)
    assert bench.cmd_run(_run_args(strict_attempts=True, request_timeout_seconds=900.,
                                   stop_after_cost_usd=50.)) == 0
    assert len(calls) == 2  # the first miss did not halt the run
    rows = bench._read_jsonl(next(tmp_path.iterdir()) / "attempts.jsonl")
    assert all(bench.output_limit_reached(row) and row["cost_unknown"] is False for row in rows)


def test_a_strict_untrusted_route_stays_a_run_error_even_when_the_reply_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(bench.providers, "generate", lambda *a, **kw: {
        "text": "", "provider": "openrouter", "model": "google/gemini-4-neon",
        "resolved_model": "another-model", "resolved_provider": "Google",
        "response_id": "gen-x", "input_tokens": 10, "output_tokens": 65536,
        "provider_cost_usd": 1.0, "finish_reason": LIMIT, "latency_seconds": 300.0})
    assert bench.cmd_run(_run_args(strict_attempts=True, request_timeout_seconds=900.,
                                   stop_after_cost_usd=50.)) == 1
    first = bench._read_jsonl(next(tmp_path.iterdir()) / "attempts.jsonl")[0]
    assert first["error"] == "provider-returned model does not match the requested model"
    assert bench.run_error(first)


def test_the_empty_completion_receipt_carries_the_calls_time(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    payload = {"id": "gen-1", "model": "google/gemini-4-neon", "provider": "Google",
               "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
               "usage": {"prompt_tokens": 5, "completion_tokens": 65536, "cost": 1.0}}
    monkeypatch.setattr(providers, "_post_json_with_retries", lambda *a, **kw: payload)
    with pytest.raises(providers.ProviderError) as raised:
        providers.generate("openrouter/google/gemini-4-neon", "task", 65536,
                           settings={"model_max_output_tokens": 65536})
    assert raised.value.failure_kind == "empty_completion"
    assert raised.value.receipt["finish_reason"] == LIMIT
    assert isinstance(raised.value.receipt["latency_seconds"], float)
