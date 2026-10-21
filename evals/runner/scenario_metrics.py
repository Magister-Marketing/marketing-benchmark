"""Metrics for one product scenario run, read back from the lane's database.

A scenario run (``evals/schema/scenario-task.v1.schema.json``) is one real
chat replayed on a Magister test lane. The runner (the monorepo's
``evals/magister/scenario_bridge.py``) saves what the lane recorded as a
*run record*: the user turns it sent, the rows the chat left behind
(``usage_events``, ``chat_messages``, ``agent_turns``, the project's
``agent_action_approvals`` and the social posts read back from the
provider), and the outcome it verified. This module turns a record into the
metric table the scenario names, and lays two or more runs side by side.

Everything here is pure: no network, no database, no clock. The same
functions read run 0 (the original chat, harvested from its own database)
and every replay, so a before/after comparison is one table.

Timing comes from rows that carry real timestamps (the person's messages,
every usage event, the agent turns' queued/started/finished, approvals). The
agent's own ``chat_messages`` rows (thinking, tool_use, assistant) are
stamped at the turn's start and ordered by ``block_index``, so they give the
sequence of tool calls but never their timing.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Callable

SCHEMA_VERSION = 1

# Tools that only read. A repeated call with identical arguments to one of
# these is a duplicate read: the answer was already in the context.
READ_TOOLS = frozenset({
    "read", "web_search", "web_fetch", "search_project_corpus", "tool_describe",
    "pdf", "image", "ls", "glob", "grep", "memory_search", "memory_get",
})
READ_TOOL_PATTERN = re.compile(
    r"^magister_(list|get|read|search|describe|preview|fetch|query|check|lookup)_|^magister_integration_read$"
)

USD_PER_MICROCENT = 1 / 10_000  # the Gateway's unit, as the bench bridge reads it


def is_read_tool(name: str) -> bool:
    return name in READ_TOOLS or bool(READ_TOOL_PATTERN.match(name))


def parse_ts(value: Any) -> float | None:
    """ISO 8601 (Postgres `timestamptz` text included) to epoch seconds."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace(" ", "T", 1)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # Postgres prints "+00" for UTC; fromisoformat wants "+00:00".
    if re.search(r"[+-]\d{2}$", text):
        text += ":00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def canonical_args(args: Any) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _sorted_messages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (parse_ts(row.get("created_at")) or 0.0, int(row.get("block_index") or 0)),
    )


def tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per tool call, in chat order: ``{tool, args, key, is_error,
    turn_id}``. A call persisted twice (a start and a result phase) counts
    once, by its ``toolCallId``."""
    calls: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    for row in _sorted_messages(messages):
        if row.get("role") != "tool_use":
            continue
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        tool = str(row.get("content") or meta.get("tool") or "").strip() or "unknown"
        args = meta.get("args") if isinstance(meta.get("args"), (dict, list)) else {}
        entry = {
            "tool": tool,
            "args": args,
            "key": f"{tool}:{canonical_args(args)}",
            "is_error": meta.get("isError") is True,
            "turn_id": row.get("turn_id"),
        }
        call_id = str(meta.get("toolCallId") or "")
        if call_id and call_id in seen_ids:
            calls[seen_ids[call_id]] = entry  # the later phase carries the result
            continue
        if call_id:
            seen_ids[call_id] = len(calls)
        calls.append(entry)
    return calls


def _within(ts: float | None, start: float, end: float) -> bool:
    return ts is not None and start - 1.0 <= ts <= end + 1.0


def user_turns(record: dict[str, Any], start: float, end: float) -> list[dict[str, Any]]:
    """The person's turns inside the window, each with the agent turns it
    started and its wall time: from the message to the end of the last of
    those agent turns (or the window's end while one still runs).

    An agent turn names its message through ``source_message_id`` when the
    product dispatched it (a kickoff, a Continue, a detached send); a streamed
    turn carries none and is matched by order: queued after this message and
    before the next one."""
    rows = record.get("rows") or {}
    messages = [
        row for row in _sorted_messages(rows.get("chat_messages") or [])
        if row.get("role") == "user" and _within(parse_ts(row.get("created_at")), start, end)
    ]
    agent_turns = sorted(
        (row for row in rows.get("agent_turns") or [] if parse_ts(row.get("queued_at")) is not None),
        key=lambda row: parse_ts(row.get("queued_at")) or 0.0,
    )
    scripted = {str(turn.get("message_id")): turn for turn in record.get("turns") or [] if turn.get("message_id")}
    claimed: set[str] = set()
    turns: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        sent = parse_ts(message.get("created_at")) or start
        next_sent = parse_ts(messages[index + 1].get("created_at")) if index + 1 < len(messages) else None
        mine = [
            turn for turn in agent_turns
            if str(turn.get("source_message_id") or "") == str(message.get("id"))
        ]
        if not mine:
            mine = [
                turn for turn in agent_turns
                if str(turn.get("id")) not in claimed
                and not turn.get("source_message_id")
                and (parse_ts(turn.get("queued_at")) or 0.0) >= sent - 2.0
                and (next_sent is None or (parse_ts(turn.get("queued_at")) or 0.0) < next_sent)
            ]
        claimed.update(str(turn.get("id")) for turn in mine)
        finished = [parse_ts(turn.get("finished_at")) for turn in mine]
        settled = max((value for value in finished if value is not None), default=None)
        still_running = any(value is None for value in finished) or not mine
        wall_end = end if still_running else min(settled or end, end)
        meta = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
        kind = {"kickoff": "task_brief", "plan_dispatch": "continue"}.get(str(meta.get("kind") or ""), "message")
        script = scripted.get(str(message.get("id")))
        turns.append({
            "index": index + 1,
            "message_id": message.get("id"),
            "kind": script.get("kind") if script else kind,
            "source": script.get("source") if script else "chat",
            "sent_at": message.get("created_at"),
            "text_chars": len(str(message.get("content") or "")),
            "agent_turn_ids": [turn.get("id") for turn in mine],
            "agent_turn_states": [turn.get("state") for turn in mine],
            "wall_seconds": round(max(0.0, wall_end - sent), 1),
        })
    return turns


def timeline(record: dict[str, Any], start: float, end: float) -> list[tuple[float, str]]:
    """Every timestamp the lane recorded inside the window, labelled."""
    rows = record.get("rows") or {}
    points: list[tuple[float, str]] = []

    def add(value: Any, label: str) -> None:
        ts = parse_ts(value)
        if _within(ts, start, end):
            points.append((ts, label))  # type: ignore[arg-type]

    for row in rows.get("chat_messages") or []:
        if row.get("role") == "user":
            add(row.get("created_at"), "user message")
    for row in rows.get("usage_events") or []:
        event = str(row.get("event_type") or "usage")
        label = f"{event} ({row.get('model')})" if event == "llm_request" else event
        add(row.get("created_at"), label)
    for row in rows.get("agent_turns") or []:
        add(row.get("queued_at"), "agent turn queued")
        add(row.get("started_at"), "agent turn started")
        add(row.get("finished_at"), f"agent turn {row.get('state') or 'finished'}")
    for row in rows.get("approvals") or []:
        add(row.get("created_at"), f"approval requested ({row.get('action')})")
        add(row.get("decided_at"), f"approval {row.get('decision')}")
    for turn in record.get("turns") or []:
        add(turn.get("sent_at"), f"turn sent ({turn.get('id')})")
        add(turn.get("settled_at"), f"turn settled ({turn.get('id')})")
    for reply in (record.get("responder") or {}).get("replies") or []:
        add(reply.get("at"), "responder reply")
    points.append((start, "run start"))
    points.append((end, "run end"))
    return sorted(points)


def longest_gap(points: list[tuple[float, str]]) -> dict[str, Any]:
    best = {"seconds": 0.0, "after": None, "before": None}
    for (earlier, label_a), (later, label_b) in zip(points, points[1:]):
        gap = later - earlier
        if gap > best["seconds"]:
            best = {"seconds": round(gap, 1), "after": label_a, "before": label_b}
    return best


def window(record: dict[str, Any]) -> tuple[float, float]:
    """The run's [start, end]: the record's own bounds, else the first user
    message to the last recorded event."""
    rows = record.get("rows") or {}
    start = parse_ts(record.get("started_at"))
    end = parse_ts(record.get("ended_at"))
    if start is None:
        users = [parse_ts(r.get("created_at")) for r in rows.get("chat_messages") or [] if r.get("role") == "user"]
        start = min((value for value in users if value is not None), default=None)
    if start is None:
        raise ValueError("run record has no started_at and no user message")
    if end is None:
        stamps = [parse_ts(r.get("created_at")) for r in rows.get("usage_events") or []]
        stamps += [parse_ts(r.get("finished_at")) for r in rows.get("agent_turns") or []]
        end = max((value for value in stamps if value is not None), default=start)
    return start, max(start, end)


def compute_metrics(record: dict[str, Any]) -> dict[str, Any]:
    """The metric table for one run record. Every value is derived from the
    rows; a value the rows cannot give is ``None``, never a guess."""
    rows = record.get("rows") or {}
    start, end = window(record)
    usage = sorted(
        (row for row in rows.get("usage_events") or [] if _within(parse_ts(row.get("created_at")), start, end)),
        key=lambda row: parse_ts(row.get("created_at")) or 0.0,
    )
    llm = [row for row in usage if row.get("event_type") == "llm_request"]
    messages = [
        row for row in rows.get("chat_messages") or []
        if _within(parse_ts(row.get("created_at")), start, end)
    ]
    calls = tool_calls(messages)
    seen_calls: set[str] = set()
    seen_reads: set[str] = set()
    duplicate_calls = duplicate_reads = 0
    for call in calls:
        if call["key"] in seen_calls:
            duplicate_calls += 1
            if is_read_tool(call["tool"]):
                duplicate_reads += 1
        seen_calls.add(call["key"])
        if is_read_tool(call["tool"]):
            seen_reads.add(call["key"])
    histogram: dict[str, int] = {}
    for call in calls:
        histogram[call["tool"]] = histogram.get(call["tool"], 0) + 1

    def meta_sum(key: str) -> int | None:
        values = [(row.get("metadata") or {}).get(key) for row in llm]
        numbers = [_number(value) for value in values]
        return int(sum(value for value in numbers if value is not None)) if llm else 0

    def cached(row: dict[str, Any]) -> float:
        meta = row.get("metadata") or {}
        return max(_number(meta.get("cached_tokens")) or 0.0, _number(meta.get("cache_read_tokens")) or 0.0)

    turns = user_turns(record, start, end)
    approvals = [
        row for row in rows.get("approvals") or []
        if _within(parse_ts(row.get("created_at")), start, end)
    ]
    approval_cards = sorted(
        (
            parse_ts(row.get("created_at")) for row in messages
            if row.get("role") == "ui_spec"
            and isinstance(row.get("metadata"), dict)
            and row["metadata"].get("kind") == "approval"
        ),
        key=lambda value: value or 0.0,
    )
    first_approval = min(
        [value for value in approval_cards if value is not None]
        + [value for value in (parse_ts(row.get("created_at")) for row in approvals) if value is not None],
        default=None,
    )
    turns_until_first_approval = (
        sum(1 for turn in turns if (parse_ts(turn["sent_at"]) or 0.0) <= first_approval)
        if first_approval is not None else None
    )
    outcome = record.get("outcome") if isinstance(record.get("outcome"), dict) else {}
    responder = record.get("responder") if isinstance(record.get("responder"), dict) else {}
    gap = longest_gap(timeline(record, start, end))
    durations = [_number(row.get("duration_ms")) for row in llm]
    longest_call = max((value for value in durations if value is not None), default=None)
    models = sorted({str(row.get("model")) for row in llm if row.get("model")})
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": record.get("scenario_id"),
        "repetition": record.get("repetition"),
        "label": record.get("label"),
        "lane": record.get("lane"),
        "gateway_sha": record.get("gateway_sha"),
        # The model the rows show, never the one the run asked for: a
        # preference the Gateway resolves differently is exactly what a
        # comparison must not hide.
        "model": models[0] if len(models) == 1 else (", ".join(models) if models else None),
        "model_requested": record.get("model"),
        "models_seen": models,
        "session_id": record.get("session_id"),
        "stop_reason": record.get("stop_reason"),
        "published": bool(outcome.get("published")),
        "has_media": bool(outcome.get("has_media")) if outcome.get("published") else False,
        "live_url": outcome.get("live_url"),
        "wall_seconds_total": round(end - start, 1),
        "wall_seconds_per_turn": [turn["wall_seconds"] for turn in turns],
        "turns": turns,
        "user_turns": len(turns),
        "scripted_replies": len(responder.get("replies") or []),
        "llm_calls": len(llm),
        "input_tokens": int(sum(_number(row.get("input_tokens")) or 0 for row in llm)),
        "cached_tokens": int(sum(cached(row) for row in llm)),
        "output_tokens": int(sum(_number(row.get("output_tokens")) or 0 for row in llm)),
        "reasoning_tokens": meta_sum("reasoning_tokens"),
        "cost_usd": round(sum(_number(row.get("cost_microcents")) or 0 for row in usage) * USD_PER_MICROCENT, 4),
        "provider_cost_usd": round(
            sum(_number(row.get("provider_cost_microcents")) or 0 for row in usage) * USD_PER_MICROCENT, 4
        ),
        "longest_llm_call_seconds": round(longest_call / 1000, 1) if longest_call is not None else None,
        "tool_calls": len(calls),
        "distinct_tools": len(histogram),
        "tool_histogram": dict(sorted(histogram.items(), key=lambda item: (-item[1], item[0]))),
        "duplicate_reads": duplicate_reads,
        "duplicate_calls": duplicate_calls,
        "dead_end_calls": sum(1 for call in calls if call["is_error"]),
        "dead_end_tools": sorted({call["tool"] for call in calls if call["is_error"]}),
        "longest_silent_gap_seconds": gap["seconds"],
        "longest_silent_gap": gap,
        "turns_until_first_approval": turns_until_first_approval,
        "approvals_requested": len(approvals),
        # Decisions are recorded as manual_allow / auto_allow / manual_deny / ...
        "approvals_allowed": sum(1 for row in approvals if str(row.get("decision") or "").endswith("allow")),
        "approvals_executed": sum(
            1 for row in approvals
            if str(row.get("execution_state") or "") in {"succeeded", "executed", "completed", "done"}
        ),
        "experience": record.get("experience") or {"status": "not_run"},
    }


# ── Tables ────────────────────────────────────────────────────────────────────

METRIC_ROWS: list[tuple[str, str, Callable[[dict[str, Any]], str]]] = [
    ("published", "Published (with media)", lambda m: m.get("_published_text") or (("yes" if m["published"] else "no") + (" ✓media" if m["has_media"] else ""))),
    ("wall_seconds_total", "Wall time, total", lambda m: _fmt_seconds(m["wall_seconds_total"])),
    ("wall_seconds_per_turn", "Wall time per turn", lambda m: " / ".join(_fmt_seconds(v) for v in m["wall_seconds_per_turn"]) or "—"),
    ("user_turns", "User turns", lambda m: str(m["user_turns"])),
    ("scripted_replies", "Scripted replies", lambda m: str(m["scripted_replies"])),
    ("llm_calls", "LLM calls", lambda m: str(m["llm_calls"])),
    ("longest_llm_call_seconds", "Longest LLM call", lambda m: _fmt_seconds(m["longest_llm_call_seconds"])),
    ("input_tokens", "Input tokens", lambda m: _fmt_int(m["input_tokens"])),
    ("cached_tokens", "  of which cached", lambda m: _fmt_int(m["cached_tokens"])),
    ("output_tokens", "Output tokens", lambda m: _fmt_int(m["output_tokens"])),
    ("reasoning_tokens", "  of which reasoning", lambda m: _fmt_int(m["reasoning_tokens"])),
    ("cost_usd", "Cost (billed)", lambda m: f"${m['cost_usd']:.3f}"),
    ("provider_cost_usd", "Cost (provider)", lambda m: f"${m['provider_cost_usd']:.3f}"),
    ("tool_calls", "Tool calls", lambda m: str(m["tool_calls"])),
    ("distinct_tools", "Distinct tools", lambda m: str(m["distinct_tools"])),
    ("duplicate_reads", "Duplicate reads", lambda m: str(m["duplicate_reads"])),
    ("dead_end_calls", "Dead-end calls", lambda m: str(m["dead_end_calls"])),
    ("longest_silent_gap_seconds", "Longest silent gap", lambda m: _fmt_seconds(m["longest_silent_gap_seconds"])),
    ("turns_until_first_approval", "Turns until first approval", lambda m: "—" if m["turns_until_first_approval"] is None else str(m["turns_until_first_approval"])),
    ("approvals_requested", "Approvals requested", lambda m: str(m["approvals_requested"])),
    ("approvals_allowed", "Approvals allowed", lambda m: str(m["approvals_allowed"])),
    ("experience", "Experience (judge)", lambda m: str((m.get("experience") or {}).get("status") or "not_run")),
]

NUMERIC_METRICS = [
    "wall_seconds_total", "llm_calls", "longest_llm_call_seconds", "input_tokens", "cached_tokens",
    "output_tokens", "reasoning_tokens", "cost_usd", "provider_cost_usd", "tool_calls", "distinct_tools",
    "duplicate_reads", "dead_end_calls", "longest_silent_gap_seconds", "turns_until_first_approval",
    "approvals_requested", "approvals_allowed", "user_turns", "scripted_replies",
]


def _fmt_seconds(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "—"
    whole = int(round(number))
    if whole >= 60:
        return f"{whole // 60}m {whole % 60:02d}s"
    return f"{whole}s"


def _fmt_int(value: Any) -> str:
    number = _number(value)
    return "—" if number is None else f"{int(number):,}"


def select_rows(metric_ids: list[str] | None) -> list[tuple[str, str, Callable[[dict[str, Any]], str]]]:
    if not metric_ids:
        return METRIC_ROWS
    wanted = set(metric_ids)
    return [row for row in METRIC_ROWS if row[0] in wanted]


def render_table(columns: list[tuple[str, dict[str, Any]]], metric_ids: list[str] | None = None) -> str:
    """A Markdown table: one column per run, one row per metric."""
    header = "| Metric | " + " | ".join(label for label, _ in columns) + " |"
    rule = "|---|" + "|".join("---:" for _ in columns) + "|"
    lines = [header, rule]
    for _, label, render in select_rows(metric_ids):
        lines.append(f"| {label} | " + " | ".join(render(metrics) for _, metrics in columns) + " |")
    return "\n".join(lines)


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean, median, min and max of every numeric metric across runs, and the
    publish rate."""
    summary: dict[str, Any] = {
        "runs": len(runs),
        "published": sum(1 for run in runs if run.get("published")),
        "published_rate": (sum(1 for run in runs if run.get("published")) / len(runs)) if runs else None,
    }
    for key in NUMERIC_METRICS:
        values = [_number(run.get(key)) for run in runs]
        numbers = [value for value in values if value is not None]
        summary[key] = (
            {"mean": mean(numbers), "median": median(numbers), "min": min(numbers), "max": max(numbers), "n": len(numbers)}
            if numbers else None
        )
    return summary


def compare(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    """Before/after over two sets of runs: the two summaries and the delta of
    means per metric. With three runs a side there is no confidence interval
    worth printing; the per-run table beside it shows the spread."""
    b, a = summarize(before), summarize(after)
    deltas: dict[str, Any] = {}
    for key in NUMERIC_METRICS:
        if b.get(key) and a.get(key):
            deltas[key] = {
                "before_mean": b[key]["mean"], "after_mean": a[key]["mean"],
                "delta": a[key]["mean"] - b[key]["mean"],
                "delta_pct": ((a[key]["mean"] - b[key]["mean"]) / b[key]["mean"] * 100) if b[key]["mean"] else None,
            }
    deltas["published_rate"] = {
        "before": b["published_rate"], "after": a["published_rate"],
        "delta": (a["published_rate"] - b["published_rate"])
        if a["published_rate"] is not None and b["published_rate"] is not None else None,
    }
    return {"before": b, "after": a, "deltas": deltas}


def render_comparison(comparison: dict[str, Any], metric_ids: list[str] | None = None) -> str:
    rows = ["| Metric | before (mean) | after (mean) | Δ |", "|---|---:|---:|---:|"]
    pub = comparison["deltas"]["published_rate"]
    pub_delta = "—" if pub["delta"] is None else f"{pub['delta'] * 100:+.0f} pts"
    rows.append(f"| Published | {_fmt_rate(pub['before'])} | {_fmt_rate(pub['after'])} | {pub_delta} |")
    wanted = set(metric_ids or NUMERIC_METRICS)
    labels = {key: label for key, label, _ in METRIC_ROWS}
    for key in NUMERIC_METRICS:
        if key not in wanted:
            continue
        delta = comparison["deltas"].get(key)
        if not delta:
            continue
        fmt = _fmt_seconds if key.endswith("seconds") else (lambda v: f"${v:.3f}") if key.endswith("usd") else lambda v: f"{v:,.1f}"
        pct = "" if delta["delta_pct"] is None else f" ({delta['delta_pct']:+.0f}%)"
        rows.append(
            f"| {labels.get(key, key).strip()} | {fmt(delta['before_mean'])} | {fmt(delta['after_mean'])} | "
            f"{fmt(delta['delta']) if not key.endswith('seconds') else _fmt_signed_seconds(delta['delta'])}{pct} |"
        )
    return "\n".join(rows)


def _fmt_rate(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _fmt_signed_seconds(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return sign + _fmt_seconds(abs(value))
