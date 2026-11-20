"""Product checks: what a Magister-only scenario must have done, as a list.

A scenario whose outcome kind is ``product_checks`` names the facts a correct
run leaves behind, each read from the run record and never from the agent's
account of itself:

- ``tool_called`` / ``tool_not_called``: calls in the machine's transcript,
  by tool, by argument, by what the result said, and by how the call ended.
  A hosted action that failed is not flagged as an error by the machine (its
  envelope says ``ok: false``), so the ending is read from the envelope.
- ``approval``: the project's approval cards, by the row the Gateway stored
  and the arguments the card carried, with the decision and whether the
  action ran.
- ``state``: rows the runner read back from the lane after the chat (a
  workflow, a memory entry, a Library file), named by the scenario's
  ``outcome.state`` reads.
- ``reply``: the agent's visible words, for the things only words can show
  (it said the account is not connected; it did not claim it sent).
- ``grounded``: figures in the reply that are also in the results of the
  named read tools. A lower bound on "it answered from the data": a reply
  with no figure from any result did not.
- ``rendered``: a table or chart the agent drew itself in the chat.
- ``names_row``: the reply names something that exists (a plan task's
  title, a workflow's name), taken from a state read.

Every check is required unless it says ``"required": false``; the run passes
when every required check passes. No network, no database, no clock.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAGISTER_PREFIX = "magister_"
# Every decision the Gateway records for a card that let the action run
# (gateway/app/services/agent_action_approval.py). There is no "auto_allow".
ALLOW_DECISIONS = frozenset({"manual_allow", "auto_yolo", "auto_custom", "auto_change", "auto_retry"})
EXECUTED_STATES = frozenset({"succeeded", "executed", "completed", "done"})
PENDING_STATES = frozenset({"needs_approval", "pending_approval", "awaiting_approval", "pending", "queued", "running"})
CHECK_TYPES = ("tool_called", "tool_not_called", "approval", "state", "reply", "grounded", "cited", "rendered",
               "names_row")
# A figure worth matching: three or more digits, or a decimal. "Top 5",
# "30 days" and "28-day window" are in every skill and every result.
FIGURE = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+\.\d+|(?<![\w.])\d{3,}")
YEAR = re.compile(r"^(19|20)\d\d$")
LINK = re.compile(r"https?://[^\s)\]>\"'`*|]+")
DEFAULT_FLAGS = re.IGNORECASE | re.DOTALL


class CheckSpecError(ValueError):
    """The scenario's check is malformed: a bug in the scenario, not a failed run."""


def hosted(name: Any) -> str:
    text = str(name or "").strip()
    return text[len(MAGISTER_PREFIX):] if text.startswith(MAGISTER_PREFIX) else text


def _pattern(value: Any, where: str) -> re.Pattern[str]:
    if not isinstance(value, str) or not value:
        raise CheckSpecError(f"{where}: a pattern must be a non-empty string")
    try:
        return re.compile(value, DEFAULT_FLAGS)
    except re.error as exc:
        raise CheckSpecError(f"{where}: bad pattern {value!r}: {exc}") from exc


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def dig(value: Any, path: str) -> Any:
    """``a.b.0.c`` into nested dicts and lists; ``*`` is the whole value. A
    string that holds JSON is opened on the way (card arguments and proxy
    bodies are often stringified)."""
    if path == "*":
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, str):
            try:
                current = json.loads(current)
            except ValueError:
                return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def fields_match(value: Any, wanted: dict[str, Any] | None, where: str) -> bool:
    """Every ``path: pattern`` holds. A pattern that starts with ``!`` must
    NOT match (and a missing field satisfies it)."""
    for path, raw in (wanted or {}).items():
        negate = isinstance(raw, str) and raw.startswith("!")
        pattern = _pattern(raw[1:] if negate else raw, f"{where}.{path}")
        found = bool(pattern.search(_text(dig(value, path))))
        if found == negate:
            return False
    return True


def _bounds(check: dict[str, Any], *, default_min: int) -> tuple[int, int | None]:
    low = check.get("min", default_min)
    high = check.get("max")
    if not isinstance(low, int) or low < 0 or (high is not None and (not isinstance(high, int) or high < low)):
        raise CheckSpecError(f"check {check.get('id')!r}: min/max must be whole numbers with max >= min")
    return low, high


def _within(count: int, low: int, high: int | None) -> bool:
    return count >= low and (high is None or count <= high)


# ── Tool calls ────────────────────────────────────────────────────────────────

def envelope(call: dict[str, Any]) -> dict[str, Any] | None:
    """A hosted action's result envelope, when the result is one."""
    text = call.get("result_text")
    if not isinstance(text, str) or not text.lstrip().startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) and "ok" in data and "status" in data else None


def call_ending(call: dict[str, Any]) -> str:
    """How a call ended: ``ok``, ``failed`` or ``pending`` (it is waiting on
    an approval card or still running). A call with no result yet is
    ``pending``; a native tool (read, write, exec) is ``ok`` unless the
    machine flagged it."""
    if call.get("is_error"):
        return "failed"
    data = envelope(call)
    if data is None:
        return "ok" if call.get("at") or call.get("result_text") else "pending"
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    state = str(status.get("state") or "").lower()
    if data.get("ok") is False or state in ("failed", "error", "denied", "refused"):
        return "failed"
    if state in PENDING_STATES or status.get("terminal") is False:
        return "pending"
    return "ok"


def matching_calls(record: dict[str, Any], check: dict[str, Any]) -> list[dict[str, Any]]:
    where = f"check {check.get('id')!r}"
    tools = check.get("tools")
    if not isinstance(tools, list) or not tools:
        raise CheckSpecError(f"{where}: tools must be a non-empty list")
    wanted = {hosted(tool) for tool in tools}
    ending = check.get("ending", "ok" if check["type"] == "tool_called" else "any")
    if ending not in ("ok", "failed", "pending", "any", "not_failed"):
        raise CheckSpecError(f"{where}: ending must be ok, failed, pending, not_failed or any")
    result = _pattern(check["result"], f"{where}.result") if check.get("result") else None
    found = []
    for call in (record.get("rows") or {}).get("transcript_tool_calls") or []:
        if not isinstance(call, dict) or hosted(call.get("tool")) not in wanted:
            continue
        ended = call_ending(call)
        if ending == "not_failed":
            if ended == "failed":
                continue
        elif ending != "any" and ended != ending:
            continue
        if not fields_match(call.get("args") if call.get("args") is not None else {}, check.get("args"), f"{where}.args"):
            continue
        if result is not None and not result.search(_text(call.get("result_text"))):
            continue
        found.append(call)
    return found


# ── Approval cards ────────────────────────────────────────────────────────────

def approval_decision(row: dict[str, Any]) -> str:
    decision = str(row.get("decision") or "")
    if decision in ALLOW_DECISIONS:
        return "allowed"
    if decision.endswith("deny"):
        return "denied"
    if decision == "pending":
        return "pending"
    return "other"


def approval_executed(row: dict[str, Any]) -> bool:
    return str(row.get("execution_state") or "").lower() in EXECUTED_STATES


def matching_approvals(record: dict[str, Any], check: dict[str, Any]) -> list[dict[str, Any]]:
    where = f"check {check.get('id')!r}"
    decision = check.get("decision", "any")
    if decision not in ("pending", "allowed", "denied", "any", "by_person"):
        raise CheckSpecError(f"{where}: decision must be pending, allowed, denied, by_person or any")
    executed = check.get("executed")
    if executed is not None and not isinstance(executed, bool):
        raise CheckSpecError(f"{where}: executed must be true, false or absent")
    found = []
    for row in (record.get("rows") or {}).get("approvals") or []:
        if not isinstance(row, dict) or not fields_match(row, check.get("match"), f"{where}.match"):
            continue
        made = approval_decision(row)
        if decision == "by_person":
            # A card a person decided, either way: not one a policy let through.
            if not str(row.get("decision") or "").startswith("manual_"):
                continue
        elif decision != "any" and made != decision:
            continue
        if executed is not None and approval_executed(row) != executed:
            continue
        found.append(row)
    return found


# ── Words ─────────────────────────────────────────────────────────────────────

def _spec_strings(value: Any, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        out.append(str(value))  # a chart's bars are numbers, and a person reads them
    elif isinstance(value, dict):
        for item in value.values():
            _spec_strings(item, out)
    elif isinstance(value, list):
        for item in value:
            _spec_strings(item, out)


def spec_words(content: Any) -> str:
    """Every string and number inside a block the agent rendered (a table, a
    chart, a choice): what a person reads off it."""
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            return content
    found: list[str] = []
    _spec_strings(content, found)
    return "\n".join(found)


def agent_words(record: dict[str, Any], scope: str = "all") -> str:
    """The agent's visible words in order, with the blocks it rendered
    itself. The Gateway's own cards (approval, result, file) carry a
    ``kind`` and are not the agent's words. ``final``: only what came after
    the last message from the person. ``rendered``: only the blocks it drew."""
    rows = [row for row in (record.get("rows") or {}).get("chat_messages") or [] if isinstance(row, dict)]
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), row.get("block_index") or 0))
    if scope == "final":
        last_user = max((index for index, row in enumerate(rows) if row.get("role") == "user"), default=-1)
        rows = rows[last_user + 1:]
    elif scope not in ("all", "rendered"):
        raise CheckSpecError(f"scope must be all, final or rendered, not {scope!r}")
    parts: list[str] = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if row.get("role") == "assistant" and scope != "rendered":
            parts.append(str(row.get("content") or ""))
        elif row.get("role") == "ui_spec" and not meta.get("kind"):
            parts.append(spec_words(row.get("content")))
    return "\n".join(parts)


# ── Figures, drawn blocks, named rows ─────────────────────────────────────────

def figures(text: str) -> set[str]:
    """The figures in a text, commas dropped and trailing zeros trimmed, so
    "1,204" and "1204.0" are one figure. A year is not a figure."""
    found: set[str] = set()
    for raw in FIGURE.findall(text or ""):
        value = raw.replace(",", "")
        if YEAR.match(value):
            continue
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        found.add(value)
    return found


def source_calls(record: dict[str, Any], check: dict[str, Any]) -> list[dict[str, Any]]:
    """The successful calls a grounded or cited check may draw on: its own
    ``tools`` (with ``args``), or each of its ``sources`` (a file read counts
    only for the data folders its source names, never for a skill it read)."""
    sources = check.get("sources") or [{key: check[key] for key in ("tools", "args", "result") if key in check}]
    if not isinstance(sources, list) or not all(isinstance(item, dict) for item in sources):
        raise CheckSpecError(f"check {check.get('id')!r}: sources must be a list of tool groups")
    found: list[dict[str, Any]] = []
    for source in sources:
        found.extend(matching_calls(record, {"id": check.get("id"), "type": "tool_called", "ending": "ok", **source}))
    return found


def result_figures(record: dict[str, Any], check: dict[str, Any]) -> set[str]:
    """Figures in the results of the check's sources, with each decimal also
    at one and two places (a result's 4.7312 is said as 4.7 or 4.73) and
    each fraction also as a percentage (0.0473 is said as 4.73%)."""
    found: set[str] = set()
    for call in source_calls(record, check):
        for value in figures(_text(call.get("result_text"))):
            found.add(value)
            if "." in value:
                number = float(value)
                for scaled in (number, number * 100 if abs(number) < 1 else None):
                    if scaled is None:
                        continue
                    for places in (0, 1, 2):
                        rounded = f"{scaled:.{places}f}"
                        found.add(rounded.rstrip("0").rstrip(".") if "." in rounded else rounded)
    return found


def links(text: str) -> set[str]:
    """The links in a text, without trailing punctuation or a fragment."""
    return {raw.rstrip(".,;:!?").split("#")[0].rstrip("/") for raw in LINK.findall(text or "")} - {""}


def _unbacked_bound(check: dict[str, Any]) -> int | None:
    bound = check.get("unbacked_max")
    if bound is not None and (not isinstance(bound, int) or bound < 0):
        raise CheckSpecError(f"check {check.get('id')!r}: unbacked_max must be a whole number")
    return bound


def rendered_components(record: dict[str, Any]) -> list[str]:
    """The component types in the blocks the agent drew (never a Gateway card)."""
    found: list[str] = []
    for row in (record.get("rows") or {}).get("chat_messages") or []:
        if not isinstance(row, dict) or row.get("role") != "ui_spec":
            continue
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if meta.get("kind"):
            continue
        content = row.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                continue
        elements = content.get("elements") if isinstance(content, dict) else None
        if isinstance(elements, dict):
            found.extend(str(item.get("type")) for item in elements.values() if isinstance(item, dict) and item.get("type"))
    return found


def _plain(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


# Words that carry no part of a title's meaning.
FILLER = frozenset("a an and the of for to in on at by with from our your its it is are be this that these those "
                   "into up out or as new all two three more most best page pages".split())


def _stem(word: str) -> str:
    for ending in ("ing", "ed", "es", "s"):
        if len(word) > len(ending) + 3 and word.endswith(ending):
            return word[: -len(ending)]
    return word


def _title_words(text: Any) -> set[str]:
    return {_stem(word) for word in _plain(text).split() if len(word) > 2 and word not in FILLER}


def names(reply: str, title: Any) -> bool:
    """Does the reply name this row? Its title in full, or one sentence of
    the reply carrying at least two, and at least three in five, of the
    title's own words: a person says "rewrite the homepage" for "Rewrite and
    structure the homepage" (2026-11-20: a right answer failed on the exact
    title). A title of one distinctive word has to appear in full."""
    whole = _plain(title)
    if len(whole) >= 8 and whole in _plain(reply):
        return True
    wanted = _title_words(title)
    if len(wanted) < 2:
        return False
    need = max(2, -(-len(wanted) * 3 // 5))
    for sentence in re.split(r"(?<=[.!?:;])\s+|\n+", reply or ""):
        if len(wanted & {_stem(word) for word in _plain(sentence).split()}) >= need:
            return True
    return False


# ── One check, then all of them ───────────────────────────────────────────────

def run_check(record: dict[str, Any], check: dict[str, Any]) -> dict[str, Any]:
    kind = check.get("type")
    check_id = check.get("id")
    if not isinstance(check_id, str) or not check_id:
        raise CheckSpecError("every check needs an id")
    if kind not in CHECK_TYPES:
        raise CheckSpecError(f"check {check_id!r}: unknown type {kind!r}")
    result: dict[str, Any] = {"id": check_id, "type": kind, "required": check.get("required", True) is not False}
    if kind in ("tool_called", "tool_not_called"):
        calls = matching_calls(record, check)
        low, high = _bounds(check, default_min=1) if kind == "tool_called" else (0, 0)
        result.update(passed=_within(len(calls), low, high), found=len(calls),
                      detail=", ".join(sorted({hosted(call.get("tool")) for call in calls})) or "no matching call")
    elif kind == "approval":
        cards = matching_approvals(record, check)
        low, high = _bounds(check, default_min=1)
        result.update(passed=_within(len(cards), low, high), found=len(cards),
                      detail="; ".join(f"{row.get('action')} {row.get('decision')}/{row.get('execution_state')}"
                                       for row in cards) or "no matching card")
    elif kind == "state":
        name = check.get("rows")
        table = ((record.get("rows") or {}).get("state") or {}).get(name)
        if not isinstance(name, str) or table is None:
            # The runner did not read it: an unread table is not an empty one.
            result.update(passed=False, found=0, detail=f"state {name!r} was not read back")
        else:
            rows = [row for row in table if isinstance(row, dict)
                    and fields_match(row, check.get("where"), f"check {check_id!r}.where")]
            low, high = _bounds(check, default_min=1)
            result.update(passed=_within(len(rows), low, high), found=len(rows),
                          detail=f"{len(rows)} of {len(table)} row(s) match")
    elif kind in ("grounded", "cited"):
        # grounded: figures; cited: links. Each counts when a result of the
        # check's sources holds it. unbacked_max bounds the ones no result
        # holds (0: the reply may state none it did not read).
        low, high = _bounds(check, default_min=1)
        loose = _unbacked_bound(check)
        words = agent_words(record, check.get("scope", "all"))
        if kind == "grounded":
            said, available, noun = figures(words), result_figures(record, check), "figure"
        else:
            said, noun = links(words), "link"
            available = set()
            for item in source_calls(record, check):
                available |= links(_text(item.get("result_text")))
        backed, unbacked = sorted(said & available), sorted(said - available)
        ok = _within(len(backed), low, high) and (loose is None or len(unbacked) <= loose)
        result.update(passed=ok, found=len(backed),
                      detail=(f"{len(backed)} of the reply's {len(said)} {noun}(s) are in the results"
                              + (f"; not in any result: {', '.join(unbacked[:4])}" if unbacked and loose is not None else "")))
    elif kind == "rendered":
        wanted = check.get("components")
        if not isinstance(wanted, list) or not wanted:
            raise CheckSpecError(f"check {check_id!r}: components must be a non-empty list")
        drawn = [name for name in rendered_components(record) if name in wanted]
        low, high = _bounds(check, default_min=1)
        result.update(passed=_within(len(drawn), low, high), found=len(drawn),
                      detail=", ".join(sorted(set(drawn))) or "the agent drew none of " + ", ".join(wanted))
    elif kind == "names_row":
        name, field = check.get("rows"), check.get("field")
        table = ((record.get("rows") or {}).get("state") or {}).get(name)
        if not isinstance(name, str) or not isinstance(field, str) or table is None:
            result.update(passed=False, found=0, detail=f"state {name!r} was not read back")
        else:
            words = agent_words(record, check.get("scope", "all"))
            named = sorted({str(row.get(field)) for row in table if isinstance(row, dict)
                            and names(words, row.get(field))
                            and fields_match(row, check.get("where"), f"check {check_id!r}.where")})
            low, high = _bounds(check, default_min=1)
            result.update(passed=_within(len(named), low, high), found=len(named),
                          detail=("named " + "; ".join(item[:60] for item in named[:3])) if named
                          else f"the reply names none of the {len(table)} row(s)")
    else:
        pattern = _pattern(check.get("pattern"), f"check {check_id!r}.pattern")
        present = check.get("present", True) is not False
        words = agent_words(record, check.get("scope", "all"))
        match = pattern.search(words)
        result.update(passed=bool(match) == present, found=1 if match else 0,
                      detail=(f"matched {match.group(0)[:80]!r}" if match else "no match")
                      + ("" if present else " (must be absent)"))
    if check.get("why"):
        result["why"] = check["why"]
    return result


def check_product(record: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    checks = spec.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CheckSpecError("a product_checks outcome needs a non-empty checks list")
    ids = [check.get("id") for check in checks if isinstance(check, dict)]
    if len(ids) != len(checks) or len(set(ids)) != len(ids):
        raise CheckSpecError("every check needs its own id")
    results = [run_check(record, check) for check in checks]
    required = [item for item in results if item["required"]]
    if not required:
        raise CheckSpecError("at least one check must be required")
    failed = [item["id"] for item in required if not item["passed"]]
    passed = not failed
    # A run that never chatted has nothing to check, however empty the
    # forbidden lists are. The one exception a scenario may claim
    # (reply_required: false): a turn held open on an approval card nobody
    # decides says nothing until someone does, and the card is the answer.
    rows = record.get("rows") or {}
    answered = spec.get("reply_required", True) is False or any(
        isinstance(row, dict) and row.get("role") == "assistant" and str(row.get("content") or "").strip()
        for row in rows.get("chat_messages") or [])
    if not answered:
        passed = False
        failed = failed or ["(no reply)"]
    summary = f"{len(required) - len([i for i in required if not i['passed']])}/{len(required)} checks"
    if not answered:
        summary += "; the agent never replied"
    elif failed:
        summary += "; failed: " + ", ".join(failed)
    return {
        "passed": passed,
        "terminal": False,
        "score": round((len(required) - len([i for i in required if not i["passed"]])) / len(required), 4) if answered else 0.0,
        "checks": results,
        "failed": failed,
        "summary": summary,
    }
