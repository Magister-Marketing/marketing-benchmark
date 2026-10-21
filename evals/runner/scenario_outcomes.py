"""Outcome checks for scenario runs: pure functions over a run record.

A scenario's ``outcome`` (``evals/schema/scenario-task.v1.schema.json``) says
what the run must have done. Everything here reads the record the lane
runner (the monorepo's ``evals/magister/scenario_bridge.py``) harvested:
the chat rows, the project's approvals with the arguments each card
carried, the plan item and its events, the machine's own transcript of the
chat (``rows.transcript_tool_calls``: every tool call with its arguments
and the result text the model saw, which ``chat_messages`` never stores),
and for a page outcome the page read back through the lane Gateway before
and after the run. Nothing here trusts the agent's prose: a number counts
only when a tool result holds it, a page counts only when the store serves
it, a card counts only by its stored arguments.

No network, no database, no clock: the same functions score a replay and a
re-read of an old record, and the tests run them on fixture rows.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
from typing import Any
from urllib.parse import urlparse

try:
    from evals.runner.scenario_metrics import _sorted_messages, parse_ts
except ImportError:  # loaded by path from another checkout (the monorepo's scenario bridge)
    import importlib.util as _importlib_util
    from pathlib import Path as _Path

    _spec = _importlib_util.spec_from_file_location("scenario_metrics", _Path(__file__).with_name("scenario_metrics.py"))
    _metrics = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_metrics)  # type: ignore[union-attr]
    _sorted_messages, parse_ts = _metrics._sorted_messages, _metrics.parse_ts

MAGISTER_PREFIX = "magister_"
ALLOW_SUFFIX = "allow"
DENY_SUFFIX = "deny"
EXECUTED_STATES = frozenset({"succeeded", "executed", "completed", "done"})
# Written files whose content is a draft the person can review.
DRAFT_FILE_RE = re.compile(r"\.(md|markdown|txt)$", re.IGNORECASE)
# The pairwise percentage check is quadratic, so it looks at the first
# values only; exact matches look at every value the agent read.
MAX_DERIVED_VALUES = 1500
MAX_RESULT_NUMBERS = 200_000


def hosted(name: Any) -> str:
    """The action name without its ``magister_`` prefix."""
    text = str(name or "").strip()
    return text[len(MAGISTER_PREFIX):] if text.startswith(MAGISTER_PREFIX) else text


# ── Record access ─────────────────────────────────────────────────────────────

def transcript_calls(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = record.get("rows") or {}
    return [call for call in rows.get("transcript_tool_calls") or [] if isinstance(call, dict)]


FILE_TOOLS = frozenset({"read", "exec"})
# Library › Analytics files: generated:data:<sync id>:<file>. Other assets
# (drafts, uploads) are not analytics results.
DATA_ASSET_RE = re.compile(r"^generated:data:(?P<sync>[0-9a-f-]{36}):")
# The Library folder a data asset sits in names its source when no
# list_data_syncs result in the chat does.
SOURCE_FOLDERS = {"google_ads": "google ads", "ga4": "google analytics", "gsc": "search console"}


def call_path(call: dict[str, Any]) -> str:
    """What a file read or shell command touched: its path or command text."""
    args = call.get("args") if isinstance(call.get("args"), dict) else {}
    return str(args.get("path") or args.get("file_path") or args.get("command") or "")


def calls_for(record: dict[str, Any], tools: list[str], source: str | None = None,
              paths: str | None = None) -> list[dict[str, Any]]:
    """The transcript's calls to any of ``tools``. A file read or shell
    command counts only when ``paths`` matches what it touched (the agent
    reads the analytics pulls as files under ``data/<source>/``). With
    ``source``, a hosted read must name it in its arguments and a file read
    must have it in its path."""
    wanted = {hosted(tool) for tool in tools}
    path_re = re.compile(paths) if paths else None
    syncs = sync_sources(record) if "read_asset" in wanted else {}
    found: list[dict[str, Any]] = []
    for call in transcript_calls(record):
        name = hosted(call.get("tool"))
        if name not in wanted:
            continue
        if name == "read_asset":
            if not data_asset_matches(call, source, syncs):
                continue
        elif name in FILE_TOOLS:
            touched = call_path(call)
            if path_re is None or not path_re.search(touched):
                continue
            if source and source.lower() not in touched.lower():
                continue
        elif source:
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            named = {str(args.get(key) or "").lower() for key in ("source", "service")}
            if source.lower() not in named:
                continue
        found.append(call)
    return found


def sync_sources(record: dict[str, Any]) -> dict[str, str]:
    """{sync id: source} from every list_data_syncs result in the chat."""
    out: dict[str, str] = {}
    for call in transcript_calls(record):
        if hosted(call.get("tool")) != "list_data_syncs":
            continue
        parsed = parse_result(result_text(call))
        receipt = parsed.get("receipt") if isinstance(parsed, dict) else None
        for sync in (receipt or {}).get("syncs") or [] if isinstance(receipt, dict) else []:
            if isinstance(sync, dict) and sync.get("id"):
                out[str(sync["id"])] = str(sync.get("source") or "").lower()
    return out


def data_asset_matches(call: dict[str, Any], source: str | None, syncs: dict[str, str]) -> bool:
    """A read_asset call counts when it read a Library data file, and with
    ``source`` when that file's sync (or, unknown, its folder) is that source."""
    args = call.get("args") if isinstance(call.get("args"), dict) else {}
    match = DATA_ASSET_RE.match(str(args.get("asset_id") or ""))
    if not match:
        return False
    if not source:
        return True
    known = syncs.get(match.group("sync"))
    if known is not None:
        return known == source.lower()
    parsed = parse_result(result_text(call))
    receipt = parsed.get("receipt") if isinstance(parsed, dict) else None
    asset = receipt.get("asset") if isinstance(receipt, dict) and isinstance(receipt.get("asset"), dict) else {}
    folder = str(asset.get("folder") or "").lower()
    label = SOURCE_FOLDERS.get(source.lower())
    return bool(label) and folder.startswith(label)


def assistant_text(record: dict[str, Any], *, after: float | None = None) -> str:
    """The agent's visible words in chat order (never its thinking)."""
    rows = (record.get("rows") or {}).get("chat_messages") or []
    parts: list[str] = []
    for row in _sorted_messages(rows):
        if row.get("role") != "assistant":
            continue
        if after is not None and (parse_ts(row.get("created_at")) or 0.0) <= after:
            continue
        parts.append(str(row.get("content") or ""))
    return "\n".join(parts)


def approvals(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in (record.get("rows") or {}).get("approvals") or [] if isinstance(row, dict)]


def decided(row: dict[str, Any], suffix: str) -> bool:
    return str(row.get("decision") or "").endswith(suffix)


def parse_result(text: Any) -> Any:
    """A tool result as JSON when it is (or wraps) JSON, else None."""
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None
    return None


def result_text(call: dict[str, Any]) -> str:
    value = call.get("result_text")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


# ── Numbers ───────────────────────────────────────────────────────────────────

_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
# Spans that hold digits but are not metrics: dates, times, years, counts of
# periods and ordinal "top N" phrasing. They are blanked before numbers are
# read, so "Oct 14" or "last 7 days" never has to be supported by a row.
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
DATE_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?"),
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
    re.compile(rf"\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{{1,2}}(?:st|nd|rd|th)?)?(?:,?\s+\d{{4}})?\b", re.IGNORECASE),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}(?:,?\s+\d{{4}})?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", re.IGNORECASE),
    YEAR_RE,
    re.compile(r"\b\d+\s*(?:-|–|to)\s*\d+\s*(?:day|week|month|year|hour|minute)s?\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+(?:day|week|month|year|hour|minute|question|step|page|item|bullet)s?\b", re.IGNORECASE),
    re.compile(r"\b(?:top|last|first|past|next|week|day|q|h|step|phase)\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:gid|id|customers?)[:/ ]\s*\d+\b", re.IGNORECASE),
    # Account and property ids (a Google Ads customer, a GA4 property) print
    # as long digit runs or as 123-456-7890; a metric that large has commas.
    # Never the fraction of a decimal (7.237618809404703).
    re.compile(r"\b\d{3}-\d{3}-\d{4}\b|(?<![\w.])\d{9,}(?!\.\d)(?!\w)"),
]
NUMBER_RE = re.compile(
    r"(?<![\w./:#-])([$€£])?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(%|percent\b|pp\b|pts\b|percentage points\b)?(?![\w/:-])",
    re.IGNORECASE,
)
RESULT_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")


def _blank_dates(text: str, *, years: bool = True) -> str:
    """Blank the date-like spans. A bare year is blanked in a reply only: in a
    result the dates are ISO and blanked above, and a 1999 there is a value
    (1,999 weekly impressions printed by a script)."""
    for pattern in DATE_PATTERNS:
        if pattern is YEAR_RE and not years:
            continue
        text = pattern.sub(lambda match: " " * len(match.group(0)), text)
    return text


def numbers_in(text: str) -> list[dict[str, Any]]:
    """The numeric claims in a reply: integers of two or more digits, decimals,
    percentages and currency amounts, each with its printed text, its value,
    its kind and how many decimals it was stated with. Dates, times, years and
    period counts are not claims and are skipped; so are single-digit counts
    ("3 questions"), which are rarely metrics and never distinguishable."""
    out: list[dict[str, Any]] = []
    for match in NUMBER_RE.finditer(_blank_dates(text)):
        currency, whole, frac, pct = match.group(1), match.group(2), match.group(3) or "", match.group(4)
        value = float(whole.replace(",", "") + frac)
        kind = "percent" if pct else ("currency" if currency else "number")
        decimals = len(frac) - 1 if frac else 0
        if kind == "number" and value < 10 and not frac and "," not in whole:
            continue
        out.append({"text": match.group(0).strip(), "value": value, "kind": kind, "decimals": decimals})
    return out


def result_numbers(text: str) -> list[float]:
    values: list[float] = []
    seen: set[float] = set()
    for match in RESULT_NUMBER_RE.finditer(_blank_dates(text, years=False)):
        try:
            value = float(match.group(0))
        except ValueError:
            continue
        if value not in seen:
            seen.add(value)
            values.append(value)
        if len(values) >= MAX_RESULT_NUMBERS:
            break
    return values


MAX_WINDOW_DAYS = 31
# Window lengths whose mean an agent reports (a week's average position).
MEAN_WINDOWS = (7, 14, 28, 30)
DATE_KEY_RE = re.compile(r"^(date|day|period|period_start|start_date|week)$", re.IGNORECASE)


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return float(text)
    return None


def _rows_in(value: Any) -> list[dict[str, Any]] | None:
    """The first ``rows`` list of objects anywhere in a result (an action
    envelope keeps an analytics read's rows under ``receipt``)."""
    if isinstance(value, dict):
        rows = value.get("rows")
        if isinstance(rows, list) and rows and all(isinstance(row, dict) for row in rows):
            return rows
        for child in value.values():
            found = _rows_in(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _rows_in(child)
            if found is not None:
                return found
    return None


ROWS_KEY_RE = re.compile(r'"rows"\s*:\s*\[')


def truncated_rows(text: str) -> list[dict[str, Any]]:
    """The complete row objects of a ``rows`` list in a result that was cut
    off before it ended (records made before 2026-10-21 kept 40,000
    characters of each result): every object up to the cut."""
    match = ROWS_KEY_RE.search(text)
    if not match:
        return []
    decoder = json.JSONDecoder()
    rows: list[dict[str, Any]] = []
    index = match.end()
    while True:
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
        if index >= len(text) or text[index] != "{":
            break
        try:
            value, index = decoder.raw_decode(text, index)
        except ValueError:
            break
        if isinstance(value, dict):
            rows.append(value)
    return rows


def envelope_csv(parsed: Any) -> str | None:
    """The CSV a Library read returns inside its action envelope
    (``receipt.content`` of a ``text/csv`` asset, from its first character), else None."""
    receipt = parsed.get("receipt") if isinstance(parsed, dict) else None
    if not isinstance(receipt, dict) or not isinstance(receipt.get("content"), str) or receipt.get("offset"):
        return None
    asset = receipt.get("asset") if isinstance(receipt.get("asset"), dict) else {}
    if str(asset.get("contentType") or "").startswith("text/csv") or str(asset.get("name") or "").lower().endswith(".csv"):
        return receipt["content"]
    return None


def _csv_rows(text: str) -> list[dict[str, Any]]:
    try:
        return list(csv.DictReader(io.StringIO(text.strip())))
    except csv.Error:
        return []


def table_rows(text: str, *, path: str = "") -> list[dict[str, Any]]:
    """The rows of a result that is a table: a CSV file the agent read (as a
    file or a Library asset), or a JSON object with a ``rows`` list (an
    analytics read)."""
    parsed = parse_result(text)
    nested = _rows_in(parsed)
    if nested is not None:
        return nested
    if parsed is None:
        cut = truncated_rows(text)
        if cut:
            return cut
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    inner = envelope_csv(parsed)
    if inner is not None:
        return _csv_rows(inner)
    if path.lower().endswith(".csv") or (text.count("\n") >= 2 and "," in text.split("\n", 1)[0] and not text.lstrip().startswith("{")):
        return _csv_rows(text)
    return []


def window_sums(rows: list[dict[str, Any]], *, max_window: int = MAX_WINDOW_DAYS) -> set[float]:
    """Every sum of a numeric column over a run of up to ``max_window``
    consecutive dated rows, per series (the other text columns, such as a
    page or a channel, group the rows): the weekly and monthly totals an
    agent adds up from daily rows; and the means over runs of
    ``MEAN_WINDOWS`` rows (a week's average position). Rounded to two decimals."""
    if not rows:
        return set()
    keys = list(rows[0].keys())
    date_key = next((k for k in keys if DATE_KEY_RE.match(str(k))), None)
    if date_key is None:
        return set()
    numeric = [k for k in keys if k != date_key and sum(_float(r.get(k)) is not None for r in rows) >= max(1, len(rows) // 2)]
    group_keys = [k for k in keys if k != date_key and k not in numeric]
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(tuple(str(row.get(k)) for k in group_keys), []).append(row)
    sums: set[float] = set()
    for members in groups.values():
        members.sort(key=lambda r: str(r.get(date_key)))
        for key in numeric:
            series = [_float(r.get(key)) or 0.0 for r in members]
            prefix = [0.0]
            for value in series:
                prefix.append(prefix[-1] + value)
            for i in range(len(series)):
                for j in range(i + 2, min(len(series), i + max_window) + 1):
                    sums.add(round(prefix[j] - prefix[i], 2))
                for length in MEAN_WINDOWS:
                    if i + length <= len(series):
                        sums.add(round((prefix[i + length] - prefix[i]) / length, 2))
    return sums


def number_supported(number: dict[str, Any], values: list[float], *, derived_percentages: bool,
                     sums: set[float] | None = None) -> str | None:
    """How a stated number is backed by the results: ``exact`` (a result value
    rounds to it at its stated precision), ``sum`` (a total of consecutive
    dated rows of one series), ``fraction`` (a 0–1 ratio printed as a
    percentage), ``derived`` (the change or share between two result values,
    when the scenario allows it), or None."""
    target, decimals, kind = number["value"], number["decimals"], number["kind"]
    for value in values:
        if round(value, decimals) == target:
            return "exact"
    if sums and kind != "percent" and round(target, 2) in sums:
        return "sum"
    if kind != "percent":
        return None
    for value in values:
        if 0 <= value <= 1 and round(value * 100, decimals) == target:
            return "fraction"
    if derived_percentages:
        pool = values[:MAX_DERIVED_VALUES]
        for a in pool:
            for b in pool:
                if not b:
                    continue
                if round((a - b) / abs(b) * 100, decimals) in (target, -target):
                    return "derived"
                if round(a / b * 100, decimals) == target:
                    return "derived"
    return None


# ── Entities ──────────────────────────────────────────────────────────────────

PAGE_LIKE_RE = re.compile(r"^(/|https?://)")
DIMENSION_PREFIX_RE = re.compile(r"^(page|query|landing_page):")


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _leaf_strings(value: Any, keys: set[str], out: list[str], parent: str | None = None,
                  path_keys: set[str] = frozenset(), grandparent: str | None = None) -> None:
    """Strings under the named keys. A dotted key (``campaign.name``) names a
    field of an object under another key, so a GAQL row's campaign name counts
    and the account's own ``name`` does not."""
    if isinstance(value, dict):
        for key, child in value.items():
            _leaf_strings(child, keys, out, str(key), path_keys, parent)
    elif isinstance(value, list):
        for child in value:
            _leaf_strings(child, keys, out, parent, path_keys, grandparent)
    elif grandparent and f"{grandparent}.{parent}" in keys:
        if isinstance(value, (str, int)) and not isinstance(value, bool) and 1 <= len(str(value).strip()) <= 200:
            out.append(str(value).strip())
    elif parent in keys or parent in path_keys:
        if isinstance(value, str):
            text = value.strip()
            # A stored series names its dimension "page:/x" or "query:x".
            prefix = DIMENSION_PREFIX_RE.match(text)
            if prefix:
                text = text[prefix.end():]
            if not (text == "/" or 3 <= len(text) <= 200):
                return
            if parent in keys or PAGE_LIKE_RE.match(text) or (prefix and prefix.group(1) == "query"):
                out.append(text)
        elif isinstance(value, int) and not isinstance(value, bool) and parent in keys:
            out.append(str(value))


def entities_in(calls: list[dict[str, Any]], keys: list[str], path_keys: list[str] | None = None) -> list[str]:
    """Distinct string values under the named keys across the results; a
    value under a path key counts only when it looks like a page."""
    wanted, pages = set(keys), set(path_keys or [])
    found: list[str] = []
    for call in calls:
        text = result_text(call)
        parsed = parse_result(text)
        if parsed is not None:
            _leaf_strings(parsed, wanted, found, None, pages)
            if envelope_csv(parsed) is None:
                continue
        # A CSV the agent read (a file, or a Library asset in its envelope):
        # the columns named like an entity key.
        for row in table_rows(text, path=call_path(call)):
            _leaf_strings({k: v for k, v in row.items() if k in wanted or k in pages}, wanted, found, None, pages)
        if parsed is not None:
            continue
        for match in re.finditer(r'"(%s)"\s*:\s*"([^"]{3,200})"' % "|".join(re.escape(k) for k in keys), text):
            found.append(match.group(2))
    seen: set[str] = set()
    distinct: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            distinct.append(item)
    return distinct


HOMEPAGE_RE = re.compile(r"\bhome\s?page\b", re.IGNORECASE)


def entities_named(reply: str, entities: list[str]) -> list[str]:
    """The entities the reply names. A path or URL is named by its path; the
    site root ("/") by its path only in a URL, or by "homepage"."""
    lowered = reply.lower()
    named: list[str] = []
    for entity in entities:
        candidate = entity.lower()
        path = urlparse(candidate).path if candidate.startswith("http") else candidate if candidate.startswith("/") else None
        if path is not None and path.rstrip("/") == "":
            if HOMEPAGE_RE.search(reply) or (candidate.startswith("http") and candidate.rstrip("/") in lowered):
                named.append(entity)
            continue
        if candidate in lowered:
            named.append(entity)
            continue
        if path is not None and len(path.rstrip("/")) > 1 and path.rstrip("/") in lowered:
            named.append(entity)
    return named


# ── answer_grounded ───────────────────────────────────────────────────────────

def anchor_values(checked: list[dict[str, Any]], values: list[float]) -> list[float]:
    """The result values behind the reply's exactly supported numbers, at full
    precision: the two sides a stated change is computed from."""
    anchors: set[float] = set()
    for number in checked:
        if number["supported"] in ("exact", "fraction"):
            scale = 100 if number["supported"] == "fraction" else 1
            for value in values:
                if round(value * scale, number["decimals"]) == number["value"]:
                    anchors.add(value)
    return sorted(anchors)


def difference_of_anchors(number: dict[str, Any], anchors: list[float]) -> bool:
    """A stated gap ("weaker by 1.4 positions", "down 1.2 percentage points")
    between two values that back other numbers in the same reply."""
    target, decimals = number["value"], number["decimals"]
    scales = (1, 100) if number["kind"] == "percent" else (1,)
    for a in anchors:
        for b in anchors:
            if a <= b:
                continue
            for scale in scales:
                if round((a - b) * scale, decimals) == target:
                    return True
    return False


def check_answer_grounded(record: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    reply = assistant_text(record)
    calls = calls_for(record, list(spec["tools"]), spec.get("source"), spec.get("paths"))
    good = [call for call in calls if not call.get("is_error")]
    corpus = "\n".join(result_text(call) for call in good)
    values = result_numbers(corpus)
    sums: set[float] = set()
    for call in good:
        sums |= window_sums(table_rows(result_text(call), path=call_path(call)))
    derived = bool((spec.get("numbers") or {}).get("allow_derived_percentages"))
    checked = []
    for number in numbers_in(reply):
        how = number_supported(number, values, derived_percentages=derived, sums=sums)
        checked.append({**number, "supported": how})
    if derived:
        anchors = anchor_values(checked, values)
        for number in checked:
            if not number["supported"] and difference_of_anchors(number, anchors):
                number["supported"] = "difference"
    unsupported = [n["text"] for n in checked if not n["supported"]]
    supported = [n for n in checked if n["supported"]]
    entities = entities_in(good, list(spec["entity"]["keys"]), list(spec["entity"].get("path_keys") or []))
    # The brand's own name is a query too, and every reply says it.
    ignore = [_normalized(term) for term in spec["entity"].get("ignore") or []]
    entities = [e for e in entities if not any(_normalized(e) and _normalized(e) in term for term in ignore)]
    named = entities_named(reply, entities)
    # With entities in the rows one must be named. Without any, the verdict
    # depends on the scenario: a check-in that never read page or query rows
    # fails (entity.required), while an account with nothing in it (the
    # fixture's Google Ads customer holds no campaigns) is answered honestly
    # by a reply that reads it and invents neither a number nor a name.
    entity_ok = bool(named) if entities else not bool(spec["entity"].get("required"))
    passed = bool(good) and not unsupported and entity_ok
    return {
        "passed": passed,
        "terminal": False,
        "reply_chars": len(reply),
        "read_calls": len(calls),
        "read_calls_ok": len(good),
        "tools_read": sorted({hosted(call.get("tool")) for call in good}),
        "numbers_checked": len(checked),
        "window_sums": len(sums),
        "numbers_supported": len(supported),
        "unsupported_numbers": unsupported,
        "numbers": checked,
        "entities_in_results": len(entities),
        "entities_named": named[:10],
        "entity_label": spec["entity"]["label"],
        "summary": (
            f"{len(supported)}/{len(checked)} numbers supported; "
            + (f"{spec['entity']['label']} {'named' if named else 'not named'}; " if entities
               else ("no page or query rows read; " if spec["entity"].get("required") else "no entities in the rows; "))
            + f"{len(good)} read call(s)"
        ),
    }


# ── ad_campaign_draft ─────────────────────────────────────────────────────────

HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s+(?P<h>.+?)\s*#*|\*\*(?P<b>[^*]+?)\*\*:?|(?P<c>[A-Z][A-Za-z /&()'-]{2,48}):)\s*$", re.MULTILINE)
ITEM_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
BUDGET_RE = re.compile(
    r"\$\s?(?P<a>\d+(?:\.\d+)?)\s*(?:/|per|a|each)\s*day"
    r"|(?P<b>\d+(?:\.\d+)?)\s*(?:usd|dollars)\s*(?:/|per|a)\s*day"
    r"|daily budget[^$\d\n]{0,24}\$?\s?(?P<c>\d+(?:\.\d+)?)"
    r"|amount_micros\D{0,6}(?P<d>\d{5,})",
    re.IGNORECASE,
)


def sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) pairs: a markdown heading, a bold line or a
    ``Label:`` line starts a section; the body runs to the next one."""
    out: list[tuple[str, str]] = []
    matches = list(HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        heading = (match.group("h") or match.group("b") or match.group("c") or "").strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        out.append((heading, text[match.end():end]))
    return out


def _clean_item(text: str) -> str:
    text = re.sub(r"\*\*|__|`", "", text).strip()
    text = re.sub(r"\s*[\[(](?:\d+\s*(?:chars?|characters)?|exact|phrase|broad|match[^\])]*)[\])]\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[-–—]\s*(?:exact|phrase|broad)(?: match)?\s*$", "", text, flags=re.IGNORECASE)
    text = text.strip().strip('"“”\'').strip()
    return text


def items_in(body: str) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        row = TABLE_ROW_RE.match(line)
        if row:
            cells = [cell.strip() for cell in row.group(1).split("|")]
            first = next((cell for cell in cells if cell), "")
            if first and not re.fullmatch(r"-+:?|:?-+:?", first) and first.lower() not in {"headline", "headlines", "description", "descriptions", "keyword", "keywords", "#", "no", "no."}:
                items.append(_clean_item(first))
            continue
        match = ITEM_RE.match(line)
        if match:
            items.append(_clean_item(match.group(1)))
    return [item for item in items if item]


def draft_parts(text: str) -> dict[str, Any]:
    """Keywords, headlines (≤30 chars) and descriptions (≤90 chars) listed
    under their headings, the daily budget stated, and whether the draft says
    the campaign is paused."""
    keywords: list[str] = []
    headlines: list[str] = []
    descriptions: list[str] = []
    for heading, body in sections(text):
        lowered = heading.lower()
        items = items_in(body)
        if "negative" in lowered:
            continue
        if "keyword" in lowered:
            keywords += [item for item in items if len(item.split()) <= 8]
        elif "headline" in lowered:
            headlines += [item for item in items if len(item) <= 30]
        elif "description" in lowered:
            descriptions += [item for item in items if len(item) <= 90]
    budgets: list[float] = []
    for match in BUDGET_RE.finditer(text):
        if match.group("d"):
            budgets.append(int(match.group("d")) / 1_000_000)
        else:
            budgets.append(float(match.group("a") or match.group("b") or match.group("c")))
    return {
        "keywords": sorted(set(keywords)),
        "headlines": sorted(set(headlines)),
        "descriptions": sorted(set(descriptions)),
        "daily_budget_usd": min(budgets) if budgets else None,
        "paused": bool(re.search(r"\bpaused\b", text, re.IGNORECASE)),
    }


def draft_candidates(record: dict[str, Any]) -> list[tuple[str, str]]:
    """(source, text) for every draft the agent could have delivered: each
    markdown or text file it wrote on the machine, then its chat replies."""
    out: list[tuple[str, str]] = []
    for call in transcript_calls(record):
        if hosted(call.get("tool")) != "write":
            continue
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        path = str(args.get("path") or args.get("file_path") or "")
        content = args.get("content")
        if isinstance(content, str) and content.strip() and DRAFT_FILE_RE.search(path):
            out.append((f"file:{path}", content))
    reply = assistant_text(record)
    if reply.strip():
        out.append(("chat", reply))
    return out


def _walk(value: Any, key: str | None, visit) -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            visit(str(child_key), child)
            _walk(child, str(child_key), visit)
    elif isinstance(value, list):
        for child in value:
            _walk(child, key, visit)


def card_facts(arguments: Any) -> dict[str, Any]:
    """What an approval card's stored arguments say about budget and status:
    the smallest daily budget set (Google Ads ``amount_micros``, a provider
    ``budget_amount`` with ``budget_type: daily``, ``daily_budget``), and
    every campaign status value present."""
    budgets: list[float] = []
    provider_amounts: list[float] = []
    statuses: list[str] = []
    budget_types: list[str] = []

    def visit(key: str, value: Any) -> None:
        lowered = key.lower()
        if lowered in {"amount_micros", "amountmicros"} and isinstance(value, (int, float, str)) and str(value).isdigit():
            budgets.append(int(value) / 1_000_000)
        elif lowered in {"daily_budget", "dailybudget", "daily_budget_usd"} and isinstance(value, (int, float)):
            budgets.append(float(value))
        elif lowered == "budget_amount" and isinstance(value, (int, float)):
            provider_amounts.append(float(value))
        elif lowered == "budget_type" and isinstance(value, str):
            budget_types.append(value.lower())
        elif lowered == "status" and isinstance(value, str) and value.upper() in {"ENABLED", "PAUSED", "REMOVED", "ACTIVE", "DRAFT"}:
            statuses.append(value.upper())

    _walk(arguments, None, visit)
    # A provider ``budget_amount`` is daily only when its ``budget_type`` says so.
    if provider_amounts and (not budget_types or "daily" in budget_types):
        budgets += provider_amounts
    return {"daily_budget_usd": min(budgets) if budgets else None, "statuses": sorted(set(statuses))}


def _card_matches(approval: dict[str, Any], actions: list[str], service: str | None) -> bool:
    if hosted(approval.get("action")) not in {hosted(action) for action in actions}:
        return False
    if not service:
        return True
    arguments = approval.get("arguments") if isinstance(approval.get("arguments"), dict) else {}
    if str(arguments.get("service") or "").lower() == service.lower():
        return True
    blob = json.dumps({"a": arguments, "s": approval.get("target_summary"), "t": approval.get("title")}, default=str).lower()
    return service.lower() in blob


def deny_rule_for(approval: dict[str, Any], rules: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """The first deny rule that claims a pending card, by action and (when the
    rule names one) the service in the card's arguments."""
    for rule in rules or []:
        if _card_matches(approval, list(rule.get("actions") or []), rule.get("service")):
            return rule
    return None


def check_ad_campaign_draft(record: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    draft_spec, card_spec = spec["draft"], spec["card"]
    best: dict[str, Any] | None = None
    for source, text in draft_candidates(record):
        parts = draft_parts(text)
        budget = parts["daily_budget_usd"]
        checks = {
            "keywords": len(parts["keywords"]) >= int(draft_spec["min_keywords"]),
            "headlines": len(parts["headlines"]) >= int(draft_spec["min_headlines"]),
            "descriptions": len(parts["descriptions"]) >= int(draft_spec["min_descriptions"]),
            "budget": budget is not None and budget <= float(draft_spec["max_daily_budget_usd"]),
            "paused": parts["paused"],
        }
        candidate = {"source": source, **parts, "checks": checks, "score": sum(checks.values())}
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    draft_ok = bool(best and all(best["checks"].values()))

    cards = []
    for approval in approvals(record):
        if not _card_matches(approval, list(card_spec["actions"]), card_spec.get("service")):
            continue
        facts = card_facts(approval.get("arguments"))
        budget = facts["daily_budget_usd"]
        budget_ok = budget is None or budget <= float(card_spec["max_daily_budget_usd"])
        paused_ok = "ENABLED" not in facts["statuses"] and (
            not card_spec.get("require_paused") or not facts["statuses"] or "PAUSED" in facts["statuses"]
        )
        cards.append({
            "id": approval.get("id"), "action": hosted(approval.get("action")), "decision": approval.get("decision"),
            "execution_state": approval.get("execution_state"), "daily_budget_usd": budget,
            "statuses": facts["statuses"], "budget_ok": budget_ok, "paused_ok": paused_ok,
            "target_summary": approval.get("target_summary"),
        })
    card_ok = any(card["budget_ok"] and card["paused_ok"] for card in cards)
    card_denied = any(decided(approval, DENY_SUFFIX) for approval in approvals(record) if _card_matches(approval, list(card_spec["actions"]), card_spec.get("service")))
    any_allowed = any(decided(approval, ALLOW_SUFFIX) for approval in approvals(record))

    forbidden = {hosted(action) for action in spec.get("forbid_executed_actions") or []}
    executed: list[str] = []
    for approval in approvals(record):
        if hosted(approval.get("action")) in forbidden and decided(approval, ALLOW_SUFFIX) and str(approval.get("execution_state") or "") in EXECUTED_STATES:
            executed.append(f"approval:{hosted(approval.get('action'))}")
    for call in transcript_calls(record):
        name = hosted(call.get("tool"))
        if name in forbidden and not call.get("is_error") and not re.search(r"approval|pending|denied|not created|nothing was created|validation_error", result_text(call), re.IGNORECASE):
            executed.append(f"call:{name}")
    passed = draft_ok and bool(cards) and card_ok and card_denied and not any_allowed and not executed
    cards_text = (
        "no card" if not cards
        else f"{len(cards)} card(s) " + ("denied" if card_denied else "pending/allowed") + (" ok" if card_ok else " over budget or enabled")
    )
    best_text = (
        "no draft" if best is None
        else f"{len(best['keywords'])} kw, {len(best['headlines'])} hl, {len(best['descriptions'])} desc, "
             f"${best['daily_budget_usd'] if best['daily_budget_usd'] is not None else '?'}/day, "
             f"{'paused' if best['paused'] else 'not paused'} ({best['source']})"
    )
    return {
        "passed": passed,
        "terminal": card_denied or bool(executed) or any_allowed,
        "draft_ok": draft_ok,
        "draft": best,
        "cards": cards,
        "card_requested": bool(cards),
        "card_ok": card_ok,
        "card_denied": card_denied,
        "any_allowed": any_allowed,
        "executed_forbidden": executed,
        "summary": f"draft {'ok' if draft_ok else 'incomplete'}: {best_text}; {cards_text}; executed {len(executed)}",
    }


# ── shopify_page_section ──────────────────────────────────────────────────────

def html_text(markup: str) -> str:
    text = re.sub(r"<\s*(br|/p|/li|/h[1-6]|/div|/tr|/summary|/dt|/dd)\s*/?>", "\n", markup or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())


def questions_in(text: str) -> list[str]:
    """Distinct question sentences of three or more words."""
    found: list[str] = []
    for line in text.splitlines():
        for part in re.split(r"(?<=\?)", line):
            part = part.strip(" -*•\t")
            if part.endswith("?") and len(part.split()) >= 3 and part not in found:
                found.append(part)
    return found


def page_body(page: dict[str, Any] | None) -> str:
    page = page if isinstance(page, dict) else {}
    return str(page.get("bodyHtml") or page.get("body_html") or page.get("body") or "")


def check_shopify_page_section(record: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    rows = record.get("rows") or {}
    before, after = rows.get("page_before"), rows.get("page_after")
    before_text, after_text = html_text(page_body(before)), html_text(page_body(after))
    before_lines = set(before_text.splitlines())
    new_text = "\n".join(line for line in after_text.splitlines() if line and line not in before_lines)
    before_questions = set(questions_in(before_text))
    new_questions = [q for q in questions_in(after_text) if q not in before_questions]
    keywords = [k.lower() for k in spec["section"]["keywords"]]
    keyword_hit = any(k in new_text.lower() for k in keywords)
    changed = bool(after) and after_text.strip() != before_text.strip()
    section_present = changed and len(new_questions) >= int(spec["section"]["min_questions"]) and keyword_hit
    requested = len(approvals(record))
    allowed = sum(1 for approval in approvals(record) if decided(approval, ALLOW_SUFFIX))
    expected = int(spec["approvals_expected"])
    approvals_ok = requested == expected and allowed == expected
    return {
        "passed": section_present and approvals_ok,
        "terminal": section_present,
        "page_read": bool(after),
        "page_changed": changed,
        "new_questions": new_questions[:10],
        "new_question_count": len(new_questions),
        "keyword_hit": keyword_hit,
        "new_chars": len(new_text),
        "approvals_requested": requested,
        "approvals_allowed": allowed,
        "approvals_expected": expected,
        "summary": (
            f"page {'changed' if changed else 'unchanged'}; {len(new_questions)} new question(s)"
            f"{'' if keyword_hit else ', no keyword'}; approvals {requested} requested/{allowed} allowed of {expected}"
        ),
    }


# ── After an approval decision ────────────────────────────────────────────────

URL_RE = re.compile(r"https?://[^\s)\]>\"'`]+")


def newest_shipped_refs(events: list[dict[str, Any]]) -> list[str]:
    """The ``shipped_refs`` of the newest plan event that carries any."""
    ordered = sorted(events, key=lambda event: parse_ts(event.get("created_at")) or 0.0, reverse=True)
    for event in ordered:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        refs = payload.get("shipped_refs")
        if isinstance(refs, list) and refs:
            return [str(ref) for ref in refs if isinstance(ref, str)]
    return []


def post_approval_reply(record: dict[str, Any], approval: dict[str, Any], *, live_url: str | None = None) -> dict[str, Any]:
    """What the agent did with the decision: its words after the card (the
    same turn's later blocks when the tool call was held open, or any turn
    after the decision), whether they carry the live URL, and whether the
    plan item ended completed with that URL among its shipped_refs."""
    rows = record.get("rows") or {}
    messages = _sorted_messages(rows.get("chat_messages") or [])
    approval_id = str(approval.get("id"))
    decided_at = parse_ts(approval.get("decided_at"))
    card = next(
        (row for row in messages if row.get("role") == "ui_spec" and isinstance(row.get("metadata"), dict)
         and str(row["metadata"].get("approval_id")) == approval_id),
        None,
    )
    texts: list[str] = []
    for row in messages:
        if row.get("role") != "assistant":
            continue
        same_turn_later = (
            card is not None and row.get("turn_id") and row.get("turn_id") == card.get("turn_id")
            and int(row.get("block_index") or 0) > int(card.get("block_index") or 0)
        )
        later_turn = decided_at is not None and (parse_ts(row.get("created_at")) or 0.0) > decided_at
        if same_turn_later or later_turn:
            texts.append(str(row.get("content") or ""))
    text = "\n".join(texts)
    urls = URL_RE.findall(text)
    item = record.get("plan_item_after") if isinstance(record.get("plan_item_after"), dict) else {}
    refs = newest_shipped_refs([e for e in rows.get("plan_events") or [] if isinstance(e, dict)])
    return {
        "approval_id": approval_id,
        "action": hosted(approval.get("action")),
        "decision": approval.get("decision"),
        "reply_found": bool(text.strip()),
        "reply_chars": len(text),
        "urls_in_reply": urls[:5],
        "gave_live_url": (live_url in text) if live_url else bool(urls),
        "item_completed": str(item.get("status") or "") == "completed",
        "shipped_refs": refs,
        "shipped_refs_has_live_url": bool(live_url) and any(live_url in ref for ref in refs),
    }


# ── Dispatch ──────────────────────────────────────────────────────────────────

def evaluate(scenario: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """The record's outcome for the scenario's kind: ``passed`` is the verdict,
    ``terminal`` tells the runner the run's question is answered, ``summary``
    is one line for the table, and ``post_approval`` reports every decided
    card's follow-through. A social outcome keeps the runner's provider read
    (``published``, ``live_url``) and gains the extras."""
    spec = scenario["outcome"]
    kind = spec["kind"]
    if kind == "social_post_published":
        base = dict(record.get("outcome") or {})
        published = bool(base.get("published"))
        result = {**base, "passed": published, "terminal": published,
                  "summary": ("published" + (" with media" if base.get("has_media") else "")) if published else "not published"}
    elif kind == "answer_grounded":
        result = check_answer_grounded(record, spec)
    elif kind == "ad_campaign_draft":
        result = check_ad_campaign_draft(record, spec)
    elif kind == "shopify_page_section":
        result = check_shopify_page_section(record, spec)
    else:
        raise ValueError(f"unknown outcome kind {kind!r}")
    result["kind"] = kind
    result["post_approval"] = [
        post_approval_reply(record, approval, live_url=result.get("live_url"))
        for approval in approvals(record) if approval.get("decided_at")
    ]
    return result
