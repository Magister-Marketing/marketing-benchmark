"""Deterministic judge context computed from the recorded source, never the answer."""
import csv
import datetime as dt
import hashlib
import io
import re
from decimal import Decimal, InvalidOperation

VERSION = 1
HEADER = "date,campaign,adset,spend_usd,impressions,clicks,conversions,revenue_usd,refunded_conversions,refunded_revenue_usd"
AMOUNTS = ("spend_usd", "revenue_usd", "refunded_revenue_usd")
COUNTS = ("impressions", "clicks", "conversions", "refunded_conversions")


def ledger_reference(exact_prompt: str) -> dict:
    """Summarize the one ledger embedded in an immutable generation prompt.

    Never reload today's fixture: historical prompts can contain different data.
    Refuse ambiguous/malformed sources and incomplete adset coverage, rather than an oracle
    from the wrong export. Daily averages are observed spend, not configured caps.
    """
    lines = exact_prompt.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == HEADER]
    if len(starts) != 1:
        raise ValueError("judge reference needs exactly one recorded ledger CSV")
    source = [HEADER]
    for index in range(starts[0] + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue  # A blank CSV line is not the end of the recorded source.
        if line.strip().startswith(("```", "---", "##")):
            if any(re.match(r"\s*\d{4}-\d{2}-\d{2},", rest) for rest in lines[index + 1:]):
                raise ValueError("ledger rows continue after source boundary")
            break
        source.append(line)
    rows = []
    seen = set()
    for raw in csv.DictReader(io.StringIO("\n".join(source))):
        if set(raw) != set(HEADER.split(",")) or any(v is None for v in raw.values()):
            raise ValueError("malformed recorded ledger row")
        row = dict(raw)
        row["date"] = dt.date.fromisoformat(raw["date"])
        key = (row["date"], row["adset"])
        if key in seen:
            raise ValueError("duplicate recorded ledger adset-day")
        seen.add(key)
        for field in AMOUNTS:
            try:
                row[field] = Decimal(raw[field])
            except InvalidOperation as exc:
                raise ValueError("invalid recorded ledger amount") from exc
            if not row[field].is_finite() or row[field] < 0:
                raise ValueError("invalid recorded ledger amount")
        for field in COUNTS:
            row[field] = int(raw[field])
            if row[field] < 0:
                raise ValueError("invalid recorded ledger count")
        if (row["refunded_conversions"] > row["conversions"]
                or row["refunded_revenue_usd"] > row["revenue_usd"]):
            raise ValueError("recorded ledger refunds exceed gross outcomes")
        rows.append(row)
    if not rows:
        raise ValueError("empty recorded ledger")
    first, last = min(r["date"] for r in rows), max(r["date"] for r in rows)
    # This export is complete daily data. Do not silently call a truncated export
    # the full window or divide sparse observations by an arbitrary calendar span.
    for adset in {r["adset"] for r in rows}:
        subset = [r for r in rows if r["adset"] == adset]
        if (len(subset) != (last - first).days + 1
                or len({r["campaign"] for r in subset}) != 1):
            raise ValueError("incomplete or inconsistent recorded ledger adset")

    def summary(items, start, end):
        totals = {field: sum(r[field] for r in items) for field in AMOUNTS + COUNTS}
        spend = totals["spend_usd"]
        net_revenue = totals["revenue_usd"] - totals["refunded_revenue_usd"]
        net_conversions = totals["conversions"] - totals["refunded_conversions"]
        return {
            "start": start.isoformat(), "end": end.isoformat(),
            **{k: str(v) if isinstance(v, Decimal) else v for k, v in totals.items()},
            "net_revenue_usd": str(net_revenue), "net_conversions": net_conversions,
            "observed_spend_per_calendar_day_usd": str(round(spend / ((end - start).days + 1), 2)),
            "net_cpa_usd": str(round(spend / net_conversions, 2)) if net_conversions else None,
            "net_roas": str(round(net_revenue / spend, 4)) if spend else None,
            "zero_conversion_spend_usd": str(sum(r["spend_usd"] for r in items if r["conversions"] == 0)),
        }

    windows = {}
    for name, start in (("full", first), ("last_calendar_week", max(first, last - dt.timedelta(days=last.weekday()))),
                        ("final_28_days", max(first, last - dt.timedelta(days=27)))):
        subset = [r for r in rows if r["date"] >= start]
        windows[name] = {
            "account": summary(subset, start, last),
            "adsets": {adset: summary([r for r in subset if r["adset"] == adset], start, last)
                       for adset in sorted({r["adset"] for r in subset})},
        }
    return {
        "version": VERSION, "csv_sha256": hashlib.sha256("\n".join(source).encode()).hexdigest(),
        "rows": len(rows),
        "interpretation": "These are observed spend and outcomes, not configured budgets, available capacity, costs or proof of causation. Net revenue here means revenue minus refunds, not profit. Proposed future budgets may differ if labeled proposals with their funding and assumptions reconciled.",
        "windows": windows,
    }
