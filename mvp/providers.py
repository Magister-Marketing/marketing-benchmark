"""Direct provider API calls for the MVP eval.

Stdlib only. Credentials come exclusively from the operator environment
(ANTHROPIC_API_KEY, OPENAI_API_KEY); they are never read from manifests,
flags, or files, and never written to evidence.

Default API settings: temperature is always omitted so each provider uses
its own default. The only knob we set is an output-token ceiling, uniform
across models and recorded in run evidence.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

REQUEST_TIMEOUT_SECONDS = 600
RETRYABLE_STATUSES = {429, 500, 502, 503, 504, 529}
MAX_RETRIES = 2
RETRY_BASE_DELAY_SECONDS = 10


class ProviderError(RuntimeError):
    """A provider call failed after retries. Never contains credentials."""


def required_env_key(provider: str) -> str:
    return {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}[provider]


def split_model_spec(model_spec: str) -> tuple[str, str]:
    """Split 'anthropic/claude-sonnet-5' into (provider, model)."""
    provider, _, model = model_spec.partition("/")
    if provider not in ("anthropic", "openai") or not model:
        raise ProviderError(
            f"unsupported model spec {model_spec!r}; expected "
            "'anthropic/<model>' or 'openai/<model>'"
        )
    return provider, model


def generate(model_spec: str, prompt: str, max_output_tokens: int) -> dict:
    """One prompt in, one text completion out.

    Returns {text, input_tokens, output_tokens, latency_seconds, provider, model}.
    Raises ProviderError on missing keys or exhausted retries.
    """
    provider, model = split_model_spec(model_spec)
    api_key = os.environ.get(required_env_key(provider), "")
    if not api_key:
        raise ProviderError(
            f"{required_env_key(provider)} is not set; refusing to call {provider}"
        )

    if provider == "anthropic":
        url = ANTHROPIC_URL
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        url = OPENAI_URL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_completion_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

    started = time.monotonic()
    payload = _post_json_with_retries(url, headers, body, provider)
    latency = time.monotonic() - started

    if provider == "anthropic":
        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        usage = payload.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        choices = payload.get("choices", [])
        text = choices[0]["message"].get("content") or "" if choices else ""
        usage = payload.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

    if not text.strip():
        raise ProviderError(f"{provider} returned an empty completion for {model}")

    return {
        "provider": provider,
        "model": model,
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_seconds": round(latency, 2),
    }


def _post_json_with_retries(url: str, headers: dict, body: dict, provider: str) -> dict:
    data = json.dumps(body).encode("utf-8")
    last_error = "unknown error"
    for attempt in range(MAX_RETRIES + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            snippet = _safe_error_snippet(exc)
            last_error = f"HTTP {exc.code}: {snippet}"
            if exc.code not in RETRYABLE_STATUSES or attempt == MAX_RETRIES:
                raise ProviderError(f"{provider} call failed ({last_error})") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt == MAX_RETRIES:
                raise ProviderError(f"{provider} call failed ({last_error})") from None
        time.sleep(RETRY_BASE_DELAY_SECONDS * (attempt + 1))
    raise ProviderError(f"{provider} call failed ({last_error})")


def _safe_error_snippet(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")[:300]
    except Exception:
        return "unreadable error body"
    return raw.replace("\n", " ")
