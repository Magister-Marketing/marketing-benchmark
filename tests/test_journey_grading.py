import json

from eval_runner import bench, providers
from eval_runner.journey_calibration import probes
from eval_runner.journey_grading import MAX_OUTPUT_TOKENS, grade_attempt, evidence_errors


def sample():
    _, scenario, attempt, _ = next(probes())
    return scenario, attempt


def verdict(scenario, attempt):
    return {"completed": True, "self_report": "complete",
            "turn_audit": [{"turn": t["turn"], "evidence": "Checked supplied facts and current surfaces"} for t in attempt["turns"]],
            "criteria": [{"id": k, "pass": True, "evidence": "Supported"} for k in scenario["checks"]]}


def test_calibration_controls_all_have_complete_real_file_evidence():
    assert len(list(probes())) == 8
    for _, scenario, attempt, _ in probes():
        assert evidence_errors(attempt, scenario) == []


def test_required_file_absent_or_hash_invalid_prevents_paid_grading():
    scenario, attempt = sample()
    def forbidden(*args, **kwargs):
        raise AssertionError("ineligible attempt dispatched a paid judge")
    attempt["turns"][-1]["artifacts"] = []
    result = grade_attempt(attempt, scenario, {}, forbidden)
    assert result["status"] == "ineligible" and result["judge_calls"] == 0
    assert result["judge_cost_estimate_usd"] == 0
    scenario, attempt = sample()
    attempt["turns"][-1]["artifacts"][0]["content"] += "tampered"
    assert grade_attempt(attempt, scenario, {}, forbidden)["status"] == "ineligible"


def test_each_turn_audit_required_and_ceiling_fixed_without_hidden_retry():
    scenario, attempt = sample()
    correct = verdict(scenario, attempt)
    calls = []
    def generate(*args, **kwargs):
        calls.append((args, kwargs))
        return {"text": json.dumps(correct), "input_tokens": 100, "output_tokens": 100, "finish_reason": "end_turn"}
    spec = bench.load_models()["claude-sonnet-5"]
    result = grade_attempt(attempt, scenario, spec, generate)
    assert result["pass"] and result["judge_protocol_version"] == 3
    assert calls[0][1]["retry_empty_completion"] is False
    assert calls[0][1]["settings"]["max_output_tokens"] == MAX_OUTPUT_TOKENS
    correct["turn_audit"].pop(0)
    result = grade_attempt(attempt, scenario, spec, generate)
    assert result["status"] == "judge_error" and "audit" in result["error"]


def test_truncated_reply_retains_cost_and_raw_evidence_once():
    scenario, attempt = sample()
    calls = []
    def generate(*args, **kwargs):
        calls.append(True)
        return {"text": '{"turn_audit":[', "input_tokens": 100, "output_tokens": 8192, "finish_reason": "max_tokens"}
    result = grade_attempt(attempt, scenario, bench.load_models()["claude-sonnet-5"], generate)
    assert len(calls) == 1 and result["status"] == "judge_error"
    assert result["judge_response"] == '{"turn_audit":['
    assert result["judge_cost_estimate_usd"] > 0 and not result["judge_cost_unknown"]


def test_provider_can_return_empty_billed_receipt_without_retry(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    calls = []
    def post(*args, **kwargs):
        calls.append(True)
        return {"content": [], "stop_reason": "max_tokens", "usage": {"input_tokens": 20, "output_tokens": 8192}}
    monkeypatch.setattr(providers, "_post_json_with_retries", post)
    result = providers.generate("anthropic/claude-sonnet-5", "synthetic", 8192, retry_empty_completion=False)
    assert len(calls) == 1 and result["output_tokens"] == 8192 and result["text"] == ""


def test_transport_timeout_is_one_attempt_with_unknown_cost(monkeypatch):
    scenario, attempt = sample()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    calls = []
    def timeout(*args, **kwargs):
        calls.append(True)
        raise TimeoutError("ambiguous completion")
    monkeypatch.setattr(providers.urllib.request, "urlopen", timeout)
    result = grade_attempt(attempt, scenario, bench.load_models()["claude-sonnet-5"])
    assert len(calls) == 1 and result["judge_calls"] == 1
    assert result["judge_cost_unknown"] and result["status"] == "judge_error"


def test_lower_budget_control_preserves_measured_source_totals():
    _, _, attempt, _ = next(p for p in probes() if p[0] == "valid-lower-budget")
    final = attempt["turns"][-1]
    for text in (final["response"], final["artifacts"][0]["content"]):
        assert "£700 spend, 21 purchases and £1400 revenue" in text
        assert "control £35, one new headline £35; £70 total" in text
