"""Paid generation policies tested entirely with synthetic provider receipts."""
import argparse
import json

import pytest

from eval_runner import bench, providers


def args(**changes):
    values = dict(models="gemini-3.8-flash-high", tasks="headline,ad-creatives",
                  repetitions=1, no_skills=True, tools=True, yes=True,
                  strict_attempts=True, request_timeout_seconds=75., stop_after_cost_usd=5.)
    return argparse.Namespace(**{**values, **changes})


def result(**changes):
    return {**dict(text="A synthetic answer", provider="openrouter",
                   model="google/gemini-3.8-flash", resolved_model="google/gemini-3.8-flash",
                   resolved_provider="Google Vertex", response_id="gen-test",
                   input_tokens=10, output_tokens=20, provider_cost_usd=.01,
                   finish_reason="stop", latency_seconds=.1), **changes}


@pytest.mark.parametrize("failure", ["empty", "wrong-model", "wrong-provider", "missing-id", "transport", "malformed"])
def test_strict_failure_preserves_cost_and_stops_remaining_dispatches(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    calls = []

    def generate(*values, **options):
        calls.append(options)
        if failure == "transport":
            raise providers.ProviderError("synthetic failure", receipt={"provider_cost_usd": .01})
        if failure == "malformed":
            raise json.JSONDecodeError("bad payload", "", 0)
        changes = {"empty": {"text": ""}, "wrong-model": {"resolved_model": "another-model"},
                   "wrong-provider": {"resolved_provider": "unexpected"}, "missing-id": {"response_id": None}}
        return result(**changes[failure])

    monkeypatch.setattr(providers, "generate", generate)
    assert bench.cmd_run(args()) == 1
    assert len(calls) == 1
    assert calls[0]["retry_transport"] is False
    assert calls[0]["retry_empty_completion"] is False
    assert calls[0]["request_timeout_seconds"] == 75.
    run = next(tmp_path.iterdir())
    records = [json.loads(line) for line in (run / "attempts.jsonl").read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["dispatched"] is True and records[0]["error"]
    if failure != "malformed":
        assert records[0]["provider_cost_usd"] == .01
        assert bench.attempt_cost_usd(records[0], {}) == .01
    assert records[0]["cost_unknown"] is (failure in {"transport", "malformed"})
    assert records[1]["dispatched"] is False
    assert bench.attempt_cost_usd(records[1], {}) == 0.
    assert len((run / "dispatch-events.jsonl").read_text().splitlines()) == 1


def test_strict_budget_stop_retains_the_planned_denominator(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(providers, "generate", lambda *a, **kw: calls.append(kw) or result())
    assert bench.cmd_run(args(stop_after_cost_usd=.005)) == 1
    assert len(calls) == 1
    run = next(tmp_path.iterdir())
    meta = json.loads((run / "run.json").read_text())
    assert len(meta["tasks"]) == 2
    assert meta["max_output_tokens"] == 65536
    assert meta["max_output_tokens_by_model"]["gemini-3.8-flash-high"] == 65536
    assert meta["generation_policy"]["transport_retries"] == 0
    rows = [json.loads(line) for line in (run / "attempts.jsonl").read_text().splitlines()]
    assert "error" not in rows[0]
    assert rows[1]["error"] == "not dispatched: observed spend threshold reached"


def test_no_retry_retains_empty_billed_completion_and_returned_identity(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    calls = []
    payload = {"id": "gen-proof", "model": "google/gemini-3.8-flash", "provider": "Google Vertex",
               "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
               "usage": {"prompt_tokens": 5, "completion_tokens": 65536, "cost": .25}}
    monkeypatch.setattr(providers, "_post_json_with_retries", lambda *a, **kw: calls.append(kw) or payload)
    receipt = providers.generate("openrouter/google/gemini-3.8-flash", "task", 65536,
                                 retry_empty_completion=False, retry_transport=False,
                                 request_timeout_seconds=75.)
    assert calls == [{"max_retries": 0, "timeout_seconds": 75.}]
    assert receipt["text"] == "" and receipt["provider_cost_usd"] == .25
    assert receipt["resolved_model"] == payload["model"]
    assert receipt["resolved_provider"] == "Google Vertex"
    assert receipt["response_id"] == "gen-proof"
    assert receipt["ceiling_retried"] is False


@pytest.mark.parametrize('kind', ['http','transport'])
def test_provider_failure_diagnosis_is_structured_without_parsing_error_text(monkeypatch,kind):
    import io
    import urllib.error
    def fail(*a,**kw):
        if kind=='http':
            raise urllib.error.HTTPError('https://example.invalid',429,'rate limited',{},
                                         io.BytesIO(b'PRIVATE provider body'))
        raise TimeoutError('PRIVATE transport detail')
    monkeypatch.setattr(providers.urllib.request,'urlopen',fail)
    with pytest.raises(providers.ProviderError) as caught:
        providers._post_json_with_retries('https://example.invalid',{}, {},'openrouter',max_retries=0)
    assert caught.value.failure_kind == ('http_error' if kind=='http' else 'transport_error')
    assert caught.value.status_code == (429 if kind=='http' else None)
    assert caught.value.receipt == {}


def test_empty_completion_error_keeps_its_billed_receipt(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-only')
    payload={'id':'gen-empty','model':'google/example','provider':'Example Provider',
             'choices':[{'message':{'content':''},'finish_reason':'stop'}],
             'usage':{'prompt_tokens':100,'completion_tokens':20,'cost':.007}}
    monkeypatch.setattr(providers,'_post_json_with_retries',lambda *a,**kw: payload)
    with pytest.raises(providers.ProviderError) as caught:
        providers.generate('openrouter/google/gemini-3.8-flash','prompt',1000)
    assert caught.value.failure_kind=='empty_completion'
    assert caught.value.receipt['response_id']=='gen-empty'
    assert caught.value.receipt['provider_cost_usd']==.007


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_refused_before_generation(timeout):
    with pytest.raises(SystemExit, match="positive and finite"):
        bench.cmd_run(args(request_timeout_seconds=timeout))


def test_failed_call_spend_is_included_and_unknown_billing_is_labelled():
    rows = [{"provider_cost_usd": .01, "output_tokens": 2, "latency_seconds": 1},
            {"error": "failed", "provider_cost_usd": .02, "cost_unknown": True,
             "output_tokens": 3, "latency_seconds": 2},
            {"error": "not dispatched", "dispatched": False}]
    efficiency = bench.attempt_efficiency(rows)
    assert efficiency["cost_usd"] == .03
    assert efficiency["cost_unknown_attempts"] == 1
    assert efficiency["total_output_tokens"] == 5
    assert efficiency["completed_attempts"] == 1
    table = bench._report_summary_rows(["m"], 3, 1, {"m": 1}, {"m": 1},
                                       {"m": efficiency}, {"m": 33.3})
    assert "lower bound; billing incomplete" in table[0]["total_cost"]


def test_model_report_counts_failed_spend_without_counting_failed_quality():
    rows = [
        {"model_id": "m", "task_id": "success", "repetition": 1,
         "finish_reason": "stop", "provider_cost_usd": .10, "latency_seconds": 10},
        {"model_id": "m", "task_id": "failed", "repetition": 1,
         "error": "upstream failure", "dispatched": True, "cost_unknown": True,
         "provider_cost_usd": .03, "latency_seconds": 2},
        {"model_id": "m", "task_id": "unstarted", "repetition": 1,
         "error": "not dispatched", "dispatched": False},
        {"model_id": "other", "task_id": "success", "repetition": 1,
         "finish_reason": "stop", "provider_cost_usd": 8, "latency_seconds": 100},
    ]
    judgments = [
        {"model_id": "m", "task_id": task, "repetition": 1,
         "criteria": [{"id": "criterion", "pass": passed}]}
        for task, passed in (("success", True), ("failed", False))
    ]
    stats = bench.model_efficiency(["m"], rows, judgments)["m"]
    assert stats["cost_usd"] == .13
    assert stats["cost_unknown_attempts"] == 1
    assert stats["completed_attempts"] == 1
    assert stats["latency_observations"] == 2
    assert stats["mean_latency_seconds"] == 6
    assert stats["criteria_passed"] == stats["criteria_judged"] == 1
    table = bench._report_summary_rows(["m"], 3, 1, {"m": 1}, {"m": 1},
                                       {"m": stats}, {"m": 33.3})
    assert "$0.1300" in table[0]["total_cost"]
    assert "lower bound; billing incomplete" in table[0]["total_cost"]
