"""Direct provider API calls for the eval runner's direct-API harness.

Stdlib only. Credentials come exclusively from the operator environment
(ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY); they are never read
from manifests, flags, or files, and never written to evidence.

Default API settings: temperature is always omitted so each provider uses
its own default. The only knobs are an output-token ceiling, uniform
across models and recorded in run evidence, and an optional provider-
hosted web-search tool (the `--tools` arm).

Request building and response parsing are pure functions so the exact
wire shapes are covered by offline tests.
"""

from __future__ import annotations

import http.client
import json
import math
import os
import time
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Every OpenRouter benchmark request pins this zero-data-retention posture:
# deny data collection and route only to explicitly approved ZDR endpoints.
# Provider slugs and flex eligibility are API request-policy values; reasoning
# capability keeps non-reasoning rows from receiving an ignored setting. No row
# opts into flex: that tier never falls back on a capacity error, so a run would
# fail outright instead of being served at the default rate.
OPENROUTER_MODEL_POLICIES = {
    "google/gemini-3.8-flash": {
        "providers": ["google-vertex"],
        "flex": False,
        "supports_reasoning": True,
    },
    "z-ai/glm-5.3": {
        "providers": ["fireworks", "together", "parasail", "novita"],
        "flex": False,
        "supports_reasoning": False,
    },
    "google/gemini-3.1-pro-preview": {
        "providers": ["google-vertex"],
        "flex": False,
        "supports_reasoning": True,
    },
    "google/gemini-2.5-pro": {
        "providers": ["google-vertex"],
        "flex": False,
        "supports_reasoning": False,
    },
    "google/gemini-2.5-flash": {
        "providers": ["google-vertex"],
        "flex": False,
        "supports_reasoning": False,
    },
}

# Response provider labels differ from routing slugs. Unknown labels fail the
# strict comparison; aliases here never widen the request's provider allowlist.
OPENROUTER_PROVIDER_LABELS = {
    "google-vertex": {"Google", "Google Vertex"},
    "fireworks": {"Fireworks"},
    "together": {"Together"},
    "parasail": {"Parasail"},
    "novita": {"Novita"},
}

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

    def __init__(self, message: str, *, receipt: dict | None = None):
        super().__init__(message)
        self.receipt = receipt or {}


def required_env_key(provider: str) -> str:
    return {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }[provider]


def split_model_spec(model_spec: str) -> tuple[str, str]:
    """Split a provider/model spec on its first slash."""
    provider, separator, model = model_spec.partition("/")
    direct_spec = provider in ("anthropic", "openai") and "/" not in model
    openrouter_parts = model.split("/") if provider == "openrouter" else []
    openrouter_spec = len(openrouter_parts) == 2 and all(openrouter_parts)
    if not separator or not model or not (direct_spec or openrouter_spec):
        raise ProviderError(
            f"unsupported model spec {model_spec!r}; expected "
            "'anthropic/<model>', 'openai/<model>', or "
            "'openrouter/<vendor>/<model>'"
        )
    return provider, model


REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Anthropic's effort scale has no xhigh; a candidate must name a level the
# provider actually accepts rather than being silently clamped into one.
ANTHROPIC_EFFORTS = ("low", "medium", "high", "max")
ALLOWED_SETTINGS = ("reasoning_effort", "text_verbosity", "max_output_tokens")
OPENAI_ONLY_SETTINGS = ("text_verbosity",)
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
    `max_output_tokens` argument is the Anthropic/OpenRouter ceiling; OpenAI
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

    if provider in ("anthropic", "openrouter"):
        openai_only = set(settings) & set(OPENAI_ONLY_SETTINGS)
        if openai_only:
            raise ProviderError(
                f"{'/'.join(OPENAI_ONLY_SETTINGS)} settings are OpenAI-only; "
                f"got {sorted(openai_only)} for {model_spec}"
            )
    if provider == "anthropic":
        if effort is not None and effort not in ANTHROPIC_EFFORTS:
            raise ProviderError(
                f"Anthropic effort vocabulary is {'/'.join(ANTHROPIC_EFFORTS)}; "
                f"got {effort!r} for {model_spec}"
            )
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        # The Messages API requires max_tokens. With no effort set it is a
        # pure ceiling on the visible answer; with one, adaptive thinking
        # shares the same budget, so an effort-carrying candidate should set
        # its own roomier max_output_tokens.
        body: dict = {
            "model": model,
            "max_tokens": cap_override or max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if effort is not None:
            # Current shape for Claude 5: adaptive thinking plus the effort
            # level, exactly what the Magister gateway sends, so the direct
            # and harness arms of a comparison ask for the same work.
            body["thinking"] = {"type": "adaptive"}
            body["output_config"] = {"effort": effort}
        if web_search:
            body["tools"] = [anthropic_web_search_tool(model)]
        return ANTHROPIC_URL, headers, body

    if provider == "openrouter":
        policy = OPENROUTER_MODEL_POLICIES.get(model)
        if policy is None:
            raise ProviderError(
                f"OpenRouter model {model!r} has no zero-data-retention policy"
            )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": cap_override or max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "provider": {
                "zdr": True,
                "data_collection": "deny",
                "only": list(policy["providers"]),
                "allow_fallbacks": True,
            },
        }
        if policy["flex"]:
            body["service_tier"] = "flex"
        if effort is not None:
            if not policy["supports_reasoning"]:
                raise ProviderError(
                    f"{model} does not take a reasoning effort; got {effort!r} "
                    f"for {model_spec}"
                )
            # OpenRouter accepts the full low..max vocabulary and maps it to
            # each vendor's own scale (Gemini caps at high), so the candidate's
            # named level goes on the wire unchanged, as for the other providers.
            body["reasoning"] = {"effort": effort}
        if web_search:
            # The OpenRouter web plugin preserves the other providers' tier
            # semantics: search is provider-hosted only in the --tools arm.
            body["plugins"] = [{"id": "web"}]
        return OPENROUTER_URL, headers, body

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

    if provider == "openrouter":
        choices = payload.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") in (None, "text")
            )
        else:
            text = ""
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            name = function.get("name") or call.get("type") or "unknown_tool"
            tool_calls[name] = tool_calls.get(name, 0) + 1
        usage = payload.get("usage") or {}
        finish = choice.get("finish_reason")
        if finish == "length":
            finish = "incomplete:max_output_tokens"
        # The web plugin never surfaces as a tool call: it runs one search
        # before the model turn and reports the results as url_citation
        # annotations on the message, so a request either searched once or
        # not at all.
        annotations = message.get("annotations") or []
        searched = any(
            isinstance(item, dict) and item.get("type") == "url_citation"
            for item in annotations
        )
        result = {
            "text": text,
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "tool_calls": tool_calls,
            "web_search_calls": 1 if searched else 0,
            "finish_reason": finish,
        }
        if usage.get("cost") is not None:
            result["provider_cost_usd"] = usage["cost"]
        # Keep provider-returned identity separate from the requested catalog id.
        for source, target in (("id", "response_id"), ("model", "resolved_model"),
                               ("provider", "resolved_provider")):
            if isinstance(payload.get(source), str):
                result[target] = payload[source]
        return result

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
    *,
    retry_empty_completion: bool = True,
    retry_transport: bool = True,
    request_timeout_seconds: float | None = None,
) -> dict:
    """One prompt in, one text completion out.

    Returns {text, input_tokens, output_tokens, web_search_calls,
    finish_reason, latency_seconds, provider, model}. Raises
    ProviderError on missing keys or exhausted retries. With retry_empty_completion
    disabled, return even an empty billed completion and its usage without a
    ceiling retry; callers can retain the receipt before classifying the error.
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
    request_options = {} if retry_transport else {"max_retries": 0}
    if request_timeout_seconds is not None:
        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ProviderError("request timeout must be positive and finite")
        request_options["timeout_seconds"] = request_timeout_seconds
    payload = _post_json_with_retries(url, headers, body, provider, **request_options)
    result = parse_response(provider, payload)

    # A reasoning model can spend an explicit output cap thinking and emit no
    # text. That is a runner ceiling, not a model answer: retry once with a
    # doubled cap so the attempt records an answer or a real failure. With no
    # explicit cap the request was already bounded only by the model's own
    # maximum — doubling cannot help, so the truncation is recorded honestly.
    # Anthropic and OpenRouter requests always carry a cap, so truncation
    # qualifies even when the candidate set no cap of its own; OpenAI requests
    # are capped only when the candidate set one.
    finish = result["finish_reason"] or ""
    explicit_cap = (settings or {}).get("max_output_tokens")
    effective_cap = explicit_cap or (
        max_output_tokens if provider in ("anthropic", "openrouter") else None
    )
    truncated = "incomplete" in finish or finish == "max_tokens"
    if retry_empty_completion and not result["text"].strip() and truncated and effective_cap:
        ceiling_retried = True
        raised = dict(settings or {})
        raised["max_output_tokens"] = effective_cap * CEILING_RETRY_MULTIPLIER
        url, headers, body = build_request(
            model_spec, prompt, max_output_tokens, web_search, api_key, raised
        )
        payload = _post_json_with_retries(url, headers, body, provider, **request_options)
        result = parse_response(provider, payload)
    latency = time.monotonic() - started

    result["ceiling_retried"] = ceiling_retried
    if retry_empty_completion and not result["text"].strip():
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


def _post_json_with_retries(url: str, headers: dict, body: dict, provider: str, *, max_retries: int | None = None, timeout_seconds: float | None = None) -> dict:
    retries = MAX_RETRIES if max_retries is None else max_retries
    data = json.dumps(body).encode("utf-8")
    last_error = "unknown error"
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            embedded = _embedded_error(provider, payload)
            if embedded is None:
                return payload
            # OpenRouter reports some provider failures as HTTP 200 with an
            # error object (top-level, or on the choice next to partial
            # text). Treat the embedded code like the HTTP status it stands
            # in for: retry the transient ones, fail the rest loudly rather
            # than grading partial text as the model's answer.
            code, message = embedded
            last_error = f"embedded {code}: {message}"
            if code not in RETRYABLE_STATUSES or attempt == retries:
                receipt = parse_response(provider, payload)
                receipt.pop("text", None)
                raise ProviderError(f"{provider} call failed ({last_error})", receipt=receipt)
        except urllib.error.HTTPError as exc:
            snippet = _safe_error_snippet(exc)
            last_error = f"HTTP {exc.code}: {snippet}"
            if exc.code not in RETRYABLE_STATUSES or attempt == retries:
                raise ProviderError(f"{provider} call failed ({last_error})") from None
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            # A dropped connection mid-body surfaces as IncompleteRead, an
            # HTTPException that is not an OSError; it is as transient as a
            # refused connection and gets the same retry.
            http.client.HTTPException,
        ) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt == retries:
                raise ProviderError(f"{provider} call failed ({last_error})") from None
        time.sleep(RETRY_BASE_DELAY_SECONDS * (attempt + 1))
    raise ProviderError(f"{provider} call failed ({last_error})")


def _embedded_error(provider: str, payload: dict) -> tuple[int, str] | None:
    """Return (code, message) for an error carried inside a 200 body."""
    if provider != "openrouter" or not isinstance(payload, dict):
        return None
    candidates = [payload.get("error")]
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        candidates.append(choices[0].get("error"))
    for error in candidates:
        if isinstance(error, dict):
            try:
                code = int(error.get("code") or 0)
            except (TypeError, ValueError):
                code = 0
            message = str(error.get("message") or "no message")[:300]
            return code, message.replace("\n", " ")
    return None


def _safe_error_snippet(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")[:300]
    except Exception:
        return "unreadable error body"
    return raw.replace("\n", " ")
