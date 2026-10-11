"""Offline receipts for both calls of an empty-completion ceiling retry."""

import pytest

from eval_runner import bench, providers


def payload(provider, *, text, input_tokens, output_tokens, capped, cost):
    if provider == "anthropic":
        return {
            "content": [{"type": "server_tool_use", "name": "web_search"},
                        {"type": "text", "text": text}],
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "stop_reason": "max_tokens" if capped else "end_turn",
        }
    if provider == "openai":
        return {
            "output": [{"type": "web_search_call"},
                       {"type": "message", "content": [
                           {"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "status": "incomplete" if capped else "completed",
            "incomplete_details": {"reason": "max_output_tokens"} if capped else None,
        }
    return {
        "id": f"call-{output_tokens}",
        "choices": [{"message": {"content": text,
                                  "tool_calls": [{"function": {"name": "web_search"}}],
                                  "annotations": [{"type": "url_citation"}]},
                     "finish_reason": "length" if capped else "stop"}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens,
                  "cost": cost},
    }


MODELS = ["anthropic/claude-sonnet-5", "openai/gpt-5.6-luna",
          "openrouter/google/gemini-3.8-flash"]


def run_retry(monkeypatch, model, replies):
    provider = model.split("/")[0]
    monkeypatch.setenv(providers.required_env_key(provider), "test-only")
    responses = iter(replies)

    def post(*args, **kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(providers, "_post_json_with_retries", post)
    return providers.generate(model, "synthetic prompt", 32000,
                              settings={"max_output_tokens": 32000})


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("answer", ["recovered answer", ""])
def test_ceiling_retry_accounts_for_both_calls_on_success_or_empty(monkeypatch, model, answer):
    provider = model.split("/")[0]
    replies = [payload(provider, text="", input_tokens=100, output_tokens=32000,
                       capped=True, cost=.03),
               payload(provider, text=answer, input_tokens=110, output_tokens=64000,
                       capped=not answer, cost=.07)]
    if answer:
        result = run_retry(monkeypatch, model, replies)
    else:
        with pytest.raises(providers.ProviderError) as caught:
            run_retry(monkeypatch, model, replies)
        assert caught.value.failure_kind == "empty_completion"
        result = caught.value.receipt

    assert result["text"] == answer
    assert result["ceiling_retried"] is True
    assert result["input_tokens"] == 210
    assert result["output_tokens"] == 96000
    assert result["tool_calls"] == {"web_search": 2}
    assert result["web_search_calls"] == 2
    assert [call["output_tokens"] for call in result["provider_calls"]] == [32000, 64000]
    assert all("text" not in call for call in result["provider_calls"])
    spec = {"pricing": {"input_per_mtok": 1, "output_per_mtok": 1}}
    expected = .10 if provider == "openrouter" else .09621
    assert bench.attempt_cost_usd(result, spec) == pytest.approx(expected)


def test_ceiling_retry_transport_failure_keeps_first_receipt_without_claiming_total(monkeypatch):
    first = payload("anthropic", text="", input_tokens=100, output_tokens=32000,
                    capped=True, cost=None)
    error = providers.ProviderError("synthetic timeout", failure_kind="transport_error")
    with pytest.raises(providers.ProviderError) as caught:
        run_retry(monkeypatch, MODELS[0], [first, error])
    assert caught.value.failure_kind == "transport_error"
    receipt = caught.value.receipt
    assert receipt["ceiling_retried"] is True
    assert receipt["provider_calls"][0]["output_tokens"] == 32000
    assert receipt["input_tokens"] is None
    assert receipt["output_tokens"] is None
    assert bench.attempt_cost_usd(receipt, {"pricing": {
        "input_per_mtok": 1, "output_per_mtok": 1}}) is None


def test_ceiling_retry_partial_provider_cost_falls_back_to_all_call_tokens(monkeypatch):
    replies = [payload("openrouter", text="", input_tokens=100, output_tokens=32000,
                       capped=True, cost=None),
               payload("openrouter", text="answer", input_tokens=110, output_tokens=64000,
                       capped=False, cost=.07)]
    result = run_retry(monkeypatch, MODELS[2], replies)
    assert "provider_cost_usd" not in result
    assert result["provider_calls"][1]["provider_cost_usd"] == .07
    assert bench.attempt_cost_usd(result, {"pricing": {
        "input_per_mtok": 1, "output_per_mtok": 1}}) == pytest.approx(.09621)


def test_ceiling_retry_missing_first_usage_is_unknown_not_final_call_only(monkeypatch):
    replies = [payload("anthropic", text="", input_tokens=None, output_tokens=None,
                       capped=True, cost=None),
               payload("anthropic", text="answer", input_tokens=110, output_tokens=64000,
                       capped=False, cost=None)]
    result = run_retry(monkeypatch, MODELS[0], replies)
    assert result["input_tokens"] is None
    assert result["output_tokens"] is None
    assert result["provider_calls"][1]["output_tokens"] == 64000
