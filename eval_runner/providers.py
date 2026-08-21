"""Direct provider API calls for the eval runner's direct-API harness.

Stdlib only. Credentials come exclusively from the operator environment
(ANTHROPIC_API_KEY, OPENAI_API_KEY); they are never read from manifests,
flags, or files, and never written to evidence.

Default API settings: temperature is always omitted so each provider uses
its own default. The only knobs are an output-token ceiling, uniform
across models and recorded in run evidence, and an optional provider-
hosted web-search tool (the `--tools` arm).

Request building and response parsing are pure functions so the exact
wire shapes are covered by offline tests.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/responses"

# Server-side web search tool versions. Newer Anthropic models take the
# dated 2026-02-09 tool; every other model keeps the basic variant.
ANTHROPIC_WEB_SEARCH_CURRENT = "web_search_20260209"
ANTHROPIC_WEB_SEARCH_BASIC = "web_search_20250305"
ANTHROPIC_CURRENT_TOOL_MODELS = (
    "opus-5", "opus-4-8", "opus-4-7", "opus-4-6", "sonnet-5", "sonnet-4-6",
    "fable-5", "mythos-5",
)
WEB_SEARCH_MAX_USES = 8

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


REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")
ALLOWED_SETTINGS = ("reasoning_effort", "text_verbosity", "max_output_tokens")
OPENAI_ONLY_SETTINGS = ("reasoning_effort", "text_verbosity")
CEILING_RETRY_MULTIPLIER = 2  # one retry with a doubled cap on empty+incomplete


def anthropic_web_search_tool(model: str) -> dict:
    current = any(marker in model for marker in ANTHROPIC_CURRENT_TOOL_MODELS)
    tool_type = ANTHROPIC_WEB_SEARCH_CURRENT if current else ANTHROPIC_WEB_SEARCH_BASIC
    return {"type": tool_type, "name": "web_search", "max_uses": WEB_SEARCH_MAX_USES}


def build_request(
    model_spec: str,
    prompt: str,
    max_output_tokens: int,
    web_search: bool,
    api_key: str,
    settings: dict | None = None,
) -> tuple[str, dict, dict]:
    """Return (url, headers, body) for one generation request.

    `settings` are optional per-candidate knobs from models.json
    (reasoning_effort, text_verbosity, max_output_tokens). Absent settings
    are omitted from the request so the provider default applies. The
    `max_output_tokens` argument is the Anthropic-required ceiling; OpenAI
    requests carry no cap unless the candidate sets one explicitly.
    """
    provider, model = split_model_spec(model_spec)
    settings = settings or {}
    unknown = set(settings) - set(ALLOWED_SETTINGS)
    if unknown:
        raise ProviderError(f"unknown candidate settings: {sorted(unknown)}")
    effort = settings.get("reasoning_effort")
    if effort is not None and effort not in REASONING_EFFORTS:
        raise ProviderError(f"invalid reasoning_effort {effort!r}")
    cap_override = settings.get("max_output_tokens")
    if cap_override is not None and (not isinstance(cap_override, int) or cap_override <= 0):
        raise ProviderError(f"invalid max_output_tokens {cap_override!r}")

    if provider == "anthropic":
        openai_only = set(settings) & set(OPENAI_ONLY_SETTINGS)
        if openai_only:
            raise ProviderError(
                "reasoning_effort/text_verbosity settings are OpenAI-only for now; "
                f"got {sorted(openai_only)} for {model_spec}"
            )
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        # The Messages API requires max_tokens; it is a pure ceiling (unused
        # headroom costs nothing, and no extended thinking is enabled here).
        body: dict = {
            "model": model,
            "max_tokens": cap_override or max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if web_search:
            body["tools"] = [anthropic_web_search_tool(model)]
        return ANTHROPIC_URL, headers, body

    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }
    # The Responses API's max_output_tokens is optional, and reasoning tokens
    # count against it — an artificial cap can starve the visible answer
    # (observed: max-effort attempts spent the whole budget thinking and
    # returned empty). Benchmark policy is "let the model work": omit the cap
    # unless the candidate explicitly sets one, so the only ceiling is the
    # model's own maximum.
    body = {
        "model": model,
        "input": prompt,
    }
    if cap_override is not None:
        body["max_output_tokens"] = cap_override
    if effort is not None:
        body["reasoning"] = {"effort": effort}
    if settings.get("text_verbosity") is not None:
        body["text"] = {"verbosity": settings["text_verbosity"]}
    if web_search:
        body["tools"] = [{"type": "web_search"}]
    return OPENAI_URL, headers, body


def parse_response(provider: str, payload: dict) -> dict:
    """Extract {text, input_tokens, output_tokens, tool_calls,
    web_search_calls, finish_reason}.

    `tool_calls` is a {tool_name: count} breakdown of every tool the model
    invoked, not just web search — Anthropic server tools appear as
    server_tool_use blocks named by tool, OpenAI Responses tools as output
    items whose type ends in `_call`. `web_search_calls` stays as a
    convenience view of the one tool the --tools arm currently enables.
    """
    tool_calls: dict[str, int] = {}
    if provider == "anthropic":
        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        for block in payload.get("content", []):
            if block.get("type") in ("server_tool_use", "tool_use"):
                name = block.get("name") or "unknown_tool"
                tool_calls[name] = tool_calls.get(name, 0) + 1
        usage = payload.get("usage", {})
        # web_search_calls keeps the billing-accurate usage counter (one
        # tool_use block can bill several search requests); tool_calls
        # counts invocations per tool.
        searches = (usage.get("server_tool_use") or {}).get(
            "web_search_requests", tool_calls.get("web_search", 0)
        )
        return {
            "text": text,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "tool_calls": tool_calls,
            "web_search_calls": searches,
            "finish_reason": payload.get("stop_reason"),
        }

    text_parts = []
    for item in payload.get("output", []):
        item_type = item.get("type") or ""
        if item_type == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
        elif item_type.endswith("_call"):
            name = item.get("name") if item_type == "function_call" else item_type[: -len("_call")]
            name = name or "unknown_tool"
            tool_calls[name] = tool_calls.get(name, 0) + 1
    usage = payload.get("usage", {})
    finish = payload.get("status")
    incomplete = (payload.get("incomplete_details") or {}).get("reason")
    if incomplete:
        finish = f"{finish}:{incomplete}"
    return {
        "text": "".join(text_parts),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "tool_calls": tool_calls,
        "web_search_calls": tool_calls.get("web_search", 0),
        "finish_reason": finish,
    }


def generate(
    model_spec: str,
    prompt: str,
    max_output_tokens: int,
    web_search: bool = False,
    settings: dict | None = None,
) -> dict:
    """One prompt in, one text completion out.

    Returns {text, input_tokens, output_tokens, web_search_calls,
    finish_reason, latency_seconds, provider, model}. Raises
    ProviderError on missing keys or exhausted retries.
    """
    provider, model = split_model_spec(model_spec)
    api_key = os.environ.get(required_env_key(provider), "")
    if not api_key:
        raise ProviderError(
            f"{required_env_key(provider)} is not set; refusing to call {provider}"
        )

    started = time.monotonic()
    ceiling_retried = False
    url, headers, body = build_request(
        model_spec, prompt, max_output_tokens, web_search, api_key, settings
    )
    payload = _post_json_with_retries(url, headers, body, provider)
    result = parse_response(provider, payload)

    # A reasoning model can spend an explicit output cap thinking and emit no
    # text. That is a runner ceiling, not a model answer: retry once with a
    # doubled cap so the attempt records an answer or a real failure. With no
    # explicit cap the request was already bounded only by the model's own
    # maximum — doubling cannot help, so the truncation is recorded honestly.
    finish = result["finish_reason"] or ""
    explicit_cap = (settings or {}).get("max_output_tokens")
    if not result["text"].strip() and "incomplete" in finish and explicit_cap:
        ceiling_retried = True
        raised = dict(settings or {})
        raised["max_output_tokens"] = explicit_cap * CEILING_RETRY_MULTIPLIER
        url, headers, body = build_request(
            model_spec, prompt, max_output_tokens, web_search, api_key, raised
        )
        payload = _post_json_with_retries(url, headers, body, provider)
        result = parse_response(provider, payload)
    latency = time.monotonic() - started

    result["ceiling_retried"] = ceiling_retried
    if not result["text"].strip():
        raise ProviderError(
            f"{provider} returned an empty completion for {model} "
            f"(finish_reason={result['finish_reason']!r}, "
            f"ceiling_retried={ceiling_retried})"
        )
    result.update(
        {
            "provider": provider,
            "model": model,
            "latency_seconds": round(latency, 2),
        }
    )
    return result


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
