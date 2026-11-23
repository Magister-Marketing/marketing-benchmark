"""Measured facts for the strategy tasks: what a reply got wrong, counted by program.

Tasks: ``channel-budget-allocation``, ``competitor-comparison`` and
``launch-timeline``. Each task's oracle reads only that task's fixture files
(written by ``scripts/gen_tasks_strategy.py``) and computes the one right
answer from them; the checker turns a reply's files into rows with the reader
every workflow task uses (``workflows.common.tables``) and counts its
differences from that answer. ``facts_for`` is the one entry point the runner
calls, and it returns nothing for any other task.

Facts are counts and flags only: no text the candidate wrote reaches the block
the judge is told to trust. Every count measures work against the oracle, so a
file left out is that many errors, never zero, and an empty reply earns
nothing.

All brands, people and figures are invented.
"""
from __future__ import annotations

import bisect
import csv
import datetime as _dt
import io
import itertools
import re
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from eval_runner.workflows import common

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "eval_runner" / "fixtures"


def _read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


def _integer(text: object) -> int | None:
    """The whole number a cell holds ("4", "4.0", "4 blocks"), or None."""
    found = re.findall(r"-?\d[\d,]*(?:\.\d+)?", str(text or ""))
    if len(found) != 1:
        return None
    value = Decimal(found[0].replace(",", ""))
    return int(value) if value == value.to_integral_value() else None


def _yes_no(text: object) -> str | None:
    value = common.norm(text).strip("*_.` ")
    return value if value in ("yes", "no") else None


# ─────────────────────────────────────────────── channel-budget-allocation

BUDGET_TASK_ID = "channel-budget-allocation"
BUDGET_DIR = FIXTURES / "channel-budget"
BUDGET_FILES = ["allocation.csv", "fees.csv", "constraints.csv"]


def _licence_fee(text: str):
    """A licence as the brief words it, as a function of the months a channel is live."""
    per_month = re.fullmatch(r"\$([\d,]+) for each month it is live", text)
    tiers = re.fullmatch(r"\$([\d,]+) if it is live in one month, \$([\d,]+) if live in two, "
                         r"\$([\d,]+) if live in all three", text)
    setup = re.fullmatch(r"\$([\d,]+) one-off agency setup if it is live in any month, plus \$([\d,]+) "
                         r"for each month it is live", text)
    amounts = [int(value.replace(",", "")) for value in (per_month or tiers or setup).groups()]
    if per_month:
        return lambda months: amounts[0] * months
    if tiers:
        return lambda months: ([0] + amounts)[months]
    return lambda months: (amounts[0] + amounts[1] * months) if months else 0


@lru_cache(maxsize=1)
def budget_inputs() -> dict:
    """The rules, the limits and every block's leads, as the fixture files state them."""
    brief = (BUDGET_DIR / "planning_brief.md").read_text()
    regions: dict[str, dict] = {}
    for region, low, high, month, field in re.findall(
            r"(?m)^\| ([a-z]+) \| \$([\d,]+) \| \$([\d,]+) \| \$([\d,]+) \| (\d+) \|$", brief):
        regions[region] = {"min": int(low.replace(",", "")), "max": int(high.replace(",", "")),
                           "month": int(month.replace(",", "")), "field": int(field)}
    licences = {channel: _licence_fee(text) for channel, text in re.findall(
        r"(?m)^\| ([a-z_]+) \| (\$[^|]+?) \|$", brief.split("## Licences", 1)[1].split("## ", 1)[0])}
    terms = {row["channel"]: row for row in _read_csv(BUDGET_DIR / "channel_terms.csv")}
    cells: dict[tuple[str, str, str], dict] = {}
    for row in _read_csv(BUDGET_DIR / "cell_limits.csv"):
        cells[(row["channel"], row["region"], row["month"])] = {
            "max": int(row["max_blocks"]), "committed": int(row["committed_blocks"]), "leads": []}
    for row in _read_csv(BUDGET_DIR / "forecasts.csv"):
        cell = cells[(row["channel"], row["region"], row["month"])]
        assert int(row["block"]) == len(cell["leads"]) + 1
        cell["leads"].append(int(row["added_leads"]))
    block = int(re.search(r"whole blocks of \$([\d,]+)", brief).group(1).replace(",", ""))
    for row in _read_csv(BUDGET_DIR / "syndication_vendor_forecast.csv"):
        cell = cells[("syndication", row["region"], row["month"])]
        assert int(row["spend_usd"]) == block * (len(cell["leads"]) + 1)
        cell["leads"].append(int(row["cumulative_leads"]) - sum(cell["leads"]))
    for key, cell in cells.items():
        assert len(cell["leads"]) == cell["max"], key
        assert all(a > b for a, b in zip(cell["leads"], cell["leads"][1:])), key
    names = brief.split("## Constraints, by name", 1)[1].split("\n\n")[1]
    return {
        "budget": int(re.search(r"\*\*Quarter budget:\*\* \$([\d,]+)", brief).group(1).replace(",", "")),
        "block": block, "regions": regions, "months": list(dict.fromkeys(key[2] for key in cells)),
        "field": {channel for channel, row in terms.items() if row["field_channel"] == "yes"},
        "licences": licences, "cells": cells,
        "constraints": re.findall(r"`([a-z_]+)`", names),
    }


def budget_solve(inputs: dict, *, field_capacity: bool = True) -> dict:
    """The split with the most leads under every rule (the field capacity
    optional), the cheaper on a tie.

    Which licence months to pay for is tried every way (8 for each licensed
    channel). For a given set of live months every other limit is a cap on a
    nested family of block sets (the budget's blocks, a region's, a region's
    month, its field blocks, a cell), and a cell's blocks add ever fewer
    leads, so the blocks form a laminar matroid: taking blocks by most added
    leads first, skipping any a cap forbids, is optimal. Committed blocks are
    bought first, and a region below its minimum then takes its own best
    blocks before the rest are taken in order. tests/test_tasks_strategy.py
    proves the result with an exact search that assumes none of this."""
    cells, regions, months, block = inputs["cells"], inputs["regions"], inputs["months"], inputs["block"]
    licensed = list(inputs["licences"])
    ranked = sorted(((leads, key, index) for key, cell in cells.items() for index, leads in enumerate(cell["leads"])),
                    key=lambda item: (-item[0], item[1], item[2]))
    best: tuple | None = None
    for pattern in itertools.product(*(list(itertools.product((False, True), repeat=len(months))) for _ in licensed)):
        live = {channel: [month for month, on in zip(months, flags) if on] for channel, flags in zip(licensed, pattern)}
        fees = sum(inputs["licences"][channel](len(live[channel])) for channel in licensed)
        if fees > inputs["budget"]:
            continue
        allowed = inputs["budget"] - fees
        taken = {key: 0 for key in cells}
        spend = {"all": 0, **{region: 0 for region in regions}}
        monthly = {(region, month): 0 for region in regions for month in months}
        field = {(region, month): 0 for region in regions for month in months}

        def fits(key: tuple) -> bool:
            channel, region, month = key
            cell = cells[key]
            if taken[key] >= cell["max"] or (channel in live and month not in live[channel]):
                return False
            if spend["all"] + block > allowed or spend[region] + block > regions[region]["max"]:
                return False
            if monthly[(region, month)] + block > regions[region]["month"]:
                return False
            return not (field_capacity and channel in inputs["field"]
                        and field[(region, month)] + 1 > regions[region]["field"])

        def buy(key: tuple) -> None:
            channel, region, month = key
            taken[key] += 1
            spend["all"] += block
            spend[region] += block
            monthly[(region, month)] += block
            field[(region, month)] += channel in inputs["field"]

        feasible = True
        for key, cell in cells.items():
            for _ in range(cell["committed"]):
                feasible = feasible and fits(key)
                buy(key)
        for region in regions:
            for _leads, key, index in ranked:
                if spend[region] >= regions[region]["min"]:
                    break
                if key[1] == region and index == taken[key] and fits(key):
                    buy(key)
            feasible = feasible and spend[region] >= regions[region]["min"]
        for _leads, key, index in ranked:
            if index == taken[key] and fits(key):
                buy(key)
        if not feasible:
            continue
        leads = sum(sum(cells[key]["leads"][:count]) for key, count in taken.items())
        rank = (leads, -(spend["all"] + fees))
        if best is None or rank > best[0]:
            best = (rank, dict(taken), fees)
    (leads, negative_cost), taken, fees = best
    return {"blocks": taken, "leads": leads, "cost": -negative_cost, "fees": fees}


def budget_live_months(blocks: dict) -> dict[str, list[str]]:
    inputs = budget_inputs()
    return {channel: [month for month in inputs["months"]
                      if any(count for (c, _region, m), count in blocks.items() if c == channel and m == month)]
            for channel in inputs["licences"]}


def budget_figures(blocks: dict) -> dict:
    """What a split costs and projects, by the brief's rules."""
    inputs = budget_inputs()
    cells, block = inputs["cells"], inputs["block"]
    live = budget_live_months(blocks)
    fees = {channel: inputs["licences"][channel](len(months)) for channel, months in live.items()}
    leads = {key: sum(cells[key]["leads"][:count]) for key, count in blocks.items()}
    by_region = {region: sum(value for key, value in leads.items() if key[1] == region) for region in inputs["regions"]}
    media = sum(blocks.values()) * block
    return {
        "media": media, "fees": fees, "cost": media + sum(fees.values()), "leads": sum(leads.values()),
        "by_region": by_region, "field_leads": sum(value for key, value in leads.items() if key[0] in inputs["field"]),
        "region_spend": {region: block * sum(n for key, n in blocks.items() if key[1] == region) for region in inputs["regions"]},
        "month_spend": {(region, month): block * sum(n for key, n in blocks.items() if key[1] == region and key[2] == month)
                        for region in inputs["regions"] for month in inputs["months"]},
        "field_blocks": {(region, month): sum(n for key, n in blocks.items()
                                              if key[0] in inputs["field"] and key[1] == region and key[2] == month)
                         for region in inputs["regions"] for month in inputs["months"]},
        "live": live,
    }


def budget_binding(blocks: dict) -> dict[str, str]:
    """Whether each named constraint binds in a split, by the brief's definitions."""
    inputs = budget_inputs()
    figures = budget_figures(blocks)
    binding = {"budget": inputs["budget"] - figures["cost"] < inputs["block"]}
    for region, limits in inputs["regions"].items():
        binding[f"{region}_min"] = figures["region_spend"][region] == limits["min"]
        binding[f"{region}_max"] = figures["region_spend"][region] == limits["max"]
        for month in inputs["months"]:
            binding[f"pacing_{region}_{month}"] = figures["month_spend"][(region, month)] == limits["month"]
            binding[f"field_{region}_{month}"] = figures["field_blocks"][(region, month)] == limits["field"]
    assert set(binding) == set(inputs["constraints"]), "the brief names the constraints the definitions cover"
    return {name: "yes" if binding[name] else "no" for name in inputs["constraints"]}


def budget_violations(blocks: dict) -> int:
    """How many of the brief's rules a split breaks."""
    inputs = budget_inputs()
    figures = budget_figures(blocks)
    broken = sum(1 for key, count in blocks.items()
                 if not inputs["cells"][key]["committed"] <= count <= inputs["cells"][key]["max"])
    broken += figures["cost"] > inputs["budget"]
    for region, limits in inputs["regions"].items():
        broken += not limits["min"] <= figures["region_spend"][region] <= limits["max"]
        for month in inputs["months"]:
            broken += figures["month_spend"][(region, month)] > limits["month"]
            broken += figures["field_blocks"][(region, month)] > limits["field"]
    return broken


@lru_cache(maxsize=1)
def budget_reference() -> dict:
    """The one right answer, and the figures the answer block asks for."""
    inputs = budget_inputs()
    best = budget_solve(inputs)
    blocks = best["blocks"]
    figures = budget_figures(blocks)
    assert (figures["cost"], figures["leads"]) == (best["cost"], best["leads"])
    uncapped = budget_solve(inputs, field_capacity=False)
    per_lead = (Decimal(figures["cost"]) / Decimal(figures["leads"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return {
        "blocks": blocks,
        "live": figures["live"],
        "fees": figures["fees"],
        "binding": budget_binding(blocks),
        "answers": {
            1: float(figures["cost"]), 2: float(figures["leads"]), 3: float(per_lead),
            4: float(figures["by_region"]["na"]), 5: float(figures["by_region"]["emea"]),
            6: float(figures["by_region"]["apac"]), 7: float(figures["field_leads"]),
            8: float(uncapped["leads"] - figures["leads"]),
        },
    }


def budget_facts(response_text: str) -> dict:
    inputs = budget_inputs()
    cells = inputs["cells"]
    reference = budget_reference()
    found = common.tables(response_text, BUDGET_FILES)
    by_cell: dict[tuple, list[dict]] = {}
    unknown = 0
    for row in found["allocation.csv"] or []:
        key = tuple(common.norm(common.cell(row, name)).replace(" ", "_") for name in ("channel", "region", "month"))
        if key in cells:
            by_cell.setdefault(key, []).append(row)
        elif any(str(value).strip() for value in row.values()):
            unknown += 1
    single = {key: rows[0] for key, rows in by_cell.items() if len(rows) == 1}
    blocks = {key: _integer(common.cell(row, "blocks")) for key, row in single.items()}

    readable = {key: count for key, count in blocks.items() if count is not None and 0 <= count <= cells[key]["max"]}
    split = {key: readable.get(key, 0) for key in cells}
    infeasible = budget_violations(split) + (found["allocation.csv"] is None)
    infeasible += sum(1 for key in cells if key not in readable)          # a cell that cannot be read keeps no rule

    arithmetic = 0
    for key, cell in cells.items():
        row, count = single.get(key), readable.get(key)
        if row is None or count is None:
            arithmetic += 1
            continue
        spend = common.money(common.cell(row, "media_spend_usd", "media_spend", "spend_usd"))
        leads = _integer(common.cell(row, "leads", "projected_leads"))
        arithmetic += spend != count * inputs["block"] or leads != sum(cell["leads"][:count])

    live = budget_live_months(split)
    fee_rows: dict[str, list[dict]] = {}
    extra_fees = 0
    for row in found["fees.csv"] or []:
        channel = common.norm(common.cell(row, "channel")).replace(" ", "_")
        if channel in inputs["licences"]:
            fee_rows.setdefault(channel, []).append(row)
        elif any(str(value).strip() for value in row.values()):
            extra_fees += 1
    fee_errors = extra_fees
    for channel, months in live.items():
        rows = fee_rows.get(channel, [])
        if len(rows) != 1 or found["allocation.csv"] is None:
            fee_errors += 1
            continue
        stated = [month for month in inputs["months"]
                  if re.search(rf"\b{month}\b", common.norm(common.cell(rows[0], "live_months", "months_live")))]
        fee = common.money(common.cell(rows[0], "fee_usd", "fee"))
        fee_errors += stated != months or fee != inputs["licences"][channel](len(months))

    stated: dict[str, list[str | None]] = {}
    extra_constraints = 0
    for row in found["constraints.csv"] or []:
        name = common.norm(common.cell(row, "constraint")).strip("`").replace(" ", "_")
        if name in reference["binding"]:
            stated.setdefault(name, []).append(_yes_no(common.cell(row, "binds")))
        elif name:
            extra_constraints += 1
    binding_errors = extra_constraints + sum(
        1 for name, value in reference["binding"].items() if stated.get(name) != [value])

    return {
        "budget_missing_file_count": sum(1 for name in BUDGET_FILES if found[name] is None),
        "budget_cell_row_error_count": unknown + sum(1 for key in cells if key not in single),
        "budget_infeasible_count": infeasible,
        "budget_wrong_cell_count": sum(1 for key, count in reference["blocks"].items() if blocks.get(key) != count),
        "budget_row_arithmetic_error_count": arithmetic,
        "budget_fee_error_count": fee_errors,
        "budget_binding_error_count": binding_errors,
    }


# ───────────────────────────────────────────────────────── competitor-comparison

COMPARISON_TASK_ID = "competitor-comparison"
COMPARISON_DIR = FIXTURES / "competitor-comparison"
COMPARISON_FILES = ["comparison.csv", "claims.csv"]
COMPANIES = ["tallyhour", "brisktime", "quillhour", "ticklog", "fenwork", "larchpoint", "clockwell", "pacemark",
             "hourglen", "ledgerline"]
US = "tallyhour"
NOT_STATED = "not stated"
ATTRIBUTES = {
    "free_plan": "yes_no", "trial_days": "number", "entry_plan": "plan", "entry_price_usd": "number",
    "entry_min_users": "number", "entry_projects": "projects", "top_plan_price_usd": "number",
    "sso_on_entry": "yes_no", "sso_cheapest_plan": "plan", "audit_log_cheapest_plan": "plan",
    "invoicing_on_entry": "yes_no", "api_on_entry": "yes_no", "approvals_on_entry": "yes_no",
    "budgets_on_entry": "yes_no", "phone_support_on_entry": "yes_no", "mobile_app": "yes_no",
    "uptime_sla_percent": "number", "eu_hosting": "yes_no", "soc2_type2": "yes_no", "dpa": "yes_no",
}
PRICE_ATTRIBUTES = ("entry_price_usd", "top_plan_price_usd")
# A plan table row, by what its label says. The plan-level features of the table.
FEATURE_ROWS = {"approvals": r"approval", "budgets": r"budget", "invoicing": r"invoic", "api": r"\bAPI\b",
                "sso": r"single sign-on|\bSSO\b", "audit": r"\baudit\b", "phone": r"phone support"}
# Cells whose value is decided against a statement nearby that reads otherwise: a feature list
# or an introduction the plan table overrides, a footnote, a beta, a plan, a Type I report, a
# money-back guarantee, an entry plan's SLA below the highest.
LOOK_ALIKES = {
    ("brisktime", "sso_on_entry"), ("brisktime", "soc2_type2"), ("ticklog", "mobile_app"), ("ticklog", "trial_days"),
    ("ticklog", "uptime_sla_percent"), ("fenwork", "soc2_type2"), ("larchpoint", "budgets_on_entry"),
    ("larchpoint", "trial_days"), ("larchpoint", "uptime_sla_percent"), ("clockwell", "budgets_on_entry"),
    ("clockwell", "phone_support_on_entry"), ("clockwell", "uptime_sla_percent"), ("pacemark", "api_on_entry"),
    ("pacemark", "eu_hosting"), ("pacemark", "uptime_sla_percent"), ("hourglen", "soc2_type2"),
    ("ledgerline", "budgets_on_entry"), ("ledgerline", "mobile_app"), ("ledgerline", "trial_days"),
}
# Company-wide statements, wherever the page makes them outside its table, FAQ and changelog.
PROSE = {
    "free_plan": [(r"free for as long as you use it|free forever", "yes"), (r"\bno free plan\b", "no")],
    "trial_days": [(r"\bno free trial\b", 0), (r"(\d+)-day free trial", None)],
    "mobile_app": [(r"mobile app is in beta|mobile app coming", "no"),
                   (r"apps for iOS and Android are included on every plan|mobile apps on every plan", "yes")],
    "eu_hosting": [(r"EU hosting is not available|do not offer EU hosting|hosted in the US only|EU hosting is coming", "no"),
                   (r"can be hosted in the EU|choose EU or US hosting|EU data residency is available|hosted in the EU \(", "yes")],
    "soc2_type2": [(r"SOC 2 Type II audit is in progress|SOC 2 Type I (?:report|audit)", "no"),
                   (r"hold a SOC 2 Type II report|holds a SOC 2 Type II report|SOC 2 Type II report is available", "yes")],
    "dpa": [(r"sign a data processing agreement with every customer", "yes")],
}


def _comparison_page(company: str) -> dict:
    """A saved pricing page, read into its parts."""
    text = (COMPARISON_DIR / f"{company}.md").read_text()
    head, _, rest = text.partition("\n## ")
    rest = "## " + rest
    rows = [line for line in head.splitlines() if line.startswith("|")]
    plans = [cell.strip() for cell in rows[0].strip("|").split("|")][1:]
    table = {}
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        table[cells[0]] = dict(zip(plans, cells[1:]))
    footnotes = dict(re.findall(r"(?m)^([¹²³⁴])\s+(.+)$", head))
    prose = [line for line in head.splitlines()[1:] if line and not line.startswith("|") and line[0] not in "¹²³⁴#"]
    sections = dict((name, body) for name, body in re.findall(r"(?ms)^## (.+?)\n(.*?)(?=^## |\Z)", rest))
    faq = re.findall(r"(?m)^\*\*(.+?)\*\*\n(.+)$", sections.get("FAQ", ""))
    changelog = re.findall(r"(?m)^- (\d{4}-\d{2}-\d{2}): (.+)$", sections.get("Changelog", ""))
    other = prose + [line for name in ("Features", "Security and compliance") for line in sections.get(name, "").splitlines()]
    return {"plans": plans, "table": table, "footnotes": footnotes, "prose": " ".join(other), "faq": faq,
            "changelog": sorted(changelog)}


def _row(page: dict, pattern: str) -> dict | None:
    found = [cells for label, cells in page["table"].items() if re.search(pattern, label, re.IGNORECASE)]
    return found[0] if found else None


def _flag(page: dict, cell: str) -> str:
    """A plan-table cell as included or not, its footnote read by rule 4."""
    mark = cell[1:] if cell[:1] == "✓" else ""
    if cell[:1] == "✓":
        return "no" if mark and "paid add-on" in page["footnotes"][mark] else "yes"
    assert cell == "—", cell
    return "no"


def _plan_after(plans: list[str], plan: str) -> list[str]:
    return plans[plans.index(plan):]


def _company_cells(company: str) -> tuple[dict, dict]:
    """The twenty cells of one company, and the value each had before an FAQ or a changelog entry overrode it."""
    page = _comparison_page(company)
    plans, table = page["plans"], page["table"]

    # Prices on a monthly basis, plan by plan (rule 7), then the changelog's price changes.
    prices: dict[str, object] = {}
    monthly = _row(page, r"billed monthly")
    yearly = _row(page, r"per year")
    billing = table.get("Billing", {})
    for plan in plans:
        cell = (monthly or {}).get(plan, "—")
        if cell == "Contact sales":
            prices[plan] = NOT_STATED
        elif cell.startswith("$"):
            prices[plan] = float(cell[1:])
        elif yearly and billing.get(plan) == "Annual only":
            prices[plan] = float((Decimal(yearly[plan][1:]) / 12).quantize(Decimal("0.01"), ROUND_HALF_UP))
        else:
            raise ValueError((company, plan))
    base_prices = dict(prices)
    for _day, entry in page["changelog"]:
        match = re.fullmatch(r"(\w+) is now \$([\d.]+) per user per month, billed monthly\.", entry)
        if match:
            prices[match.group(1)] = float(match.group(2))

    # Plan-level features: the table, then the FAQ, then the changelog (rule 3).
    features = {name: ({plan: _flag(page, cell) for plan, cell in row.items()} if (row := _row(page, pattern)) else None)
                for name, pattern in FEATURE_ROWS.items()}
    base_features = {name: dict(value) if value else None for name, value in features.items()}

    def feature_of(phrase: str) -> str:
        return next(name for name, pattern in FEATURE_ROWS.items() if re.search(pattern, phrase, re.IGNORECASE))

    for question, answer in page["faq"]:
        if re.search(r"every \w+ ?plan includes the (?:REST )?API", answer):
            features["api"] = {plan: "yes" for plan in plans}
    for _day, entry in page["changelog"]:
        if match := re.fullmatch(r"(.+?) (?:is|are) now included on (\w+)\.", entry):
            features[feature_of(match.group(1))][match.group(2)] = "yes"
        elif match := re.fullmatch(r"(.+?) is now included from (\w+)\.", entry):
            for plan in _plan_after(plans, match.group(2)):
                features[feature_of(match.group(1))][plan] = "yes"
        elif match := re.fullmatch(r"(.+?) moved to (\w+) and above\.", entry):
            name = feature_of(match.group(1))
            features[name] = {plan: "yes" if plan in _plan_after(plans, match.group(2)) else "no" for plan in plans}

    # Minimum users: the table, then the FAQ and the changelog.
    users_row = _row(page, r"^(?:users|minimum users|minimum seats)$")
    users = {plan: float(re.search(r"\d+", cell).group(0)) for plan, cell in users_row.items()} if users_row else None
    base_users = dict(users) if users else None
    for _question, answer in page["faq"]:
        if match := re.search(r"((?:\w+ and )?\w+) now start at (\d+) users", answer):
            for plan in match.group(1).split(" and "):
                users[plan] = float(match.group(2))
    for _day, entry in page["changelog"]:
        if match := re.fullmatch(r"(\w+) now starts at (\d+) users\.", entry):
            users[match.group(1)] = float(match.group(2))

    paid = [plan for plan in plans if prices[plan] != NOT_STATED and prices[plan] > 0]
    entry = min(paid, key=lambda plan: (prices[plan], plans.index(plan)))
    base_entry = min((p for p in plans if base_prices[p] != NOT_STATED and base_prices[p] > 0),
                     key=lambda plan: (base_prices[plan], plans.index(plan)))

    def cheapest(values: dict | None) -> str:
        if values is None:
            return NOT_STATED
        return next((plan for plan in plans if values[plan] == "yes"), "none")

    def on_entry(values: dict | None, plan: str) -> str:
        return NOT_STATED if values is None else values[plan]

    projects_row = _row(page, r"^active projects$")
    sla_row = _row(page, r"uptime sla")
    trial_row = _row(page, r"free trial")
    prose = page["prose"]

    def company_wide(attribute: str) -> object:
        for pattern, value in PROSE.get(attribute, []):
            if match := re.search(pattern, prose, re.IGNORECASE):
                return float(match.group(1)) if value is None else value
        return NOT_STATED

    trial = float(re.search(r"\d+", next(iter(trial_row.values()))).group(0)) if trial_row else company_wide("trial_days")
    base_trial = trial
    for question, answer in page["faq"]:
        if "free trial" in question.lower():
            if match := re.search(r"(\d+)-day free trial|trials last (\d+) days|free for (\d+) days", answer):
                trial = float(next(group for group in match.groups() if group))
    sla = [float(cell.rstrip("%")) for cell in (sla_row or {}).values() if cell != "—"]
    mobile_row = _row(page, r"mobile app")
    free_plan = company_wide("free_plan")
    for question, answer in page["faq"]:
        if "free plan" in question.lower() and re.match(r"(Yes|No)\b", answer):
            free_plan = answer[:2].strip(".").lower() if answer.startswith("No") else "yes"
    cells = {
        "free_plan": free_plan,
        "trial_days": trial,
        "entry_plan": entry,
        "entry_price_usd": prices[entry],
        "entry_min_users": users[entry] if users else NOT_STATED,
        "entry_projects": NOT_STATED if not projects_row else (
            "unlimited" if projects_row[entry] == "Unlimited" else float(projects_row[entry])),
        "top_plan_price_usd": prices[plans[-1]],
        "sso_on_entry": on_entry(features["sso"], entry),
        "sso_cheapest_plan": cheapest(features["sso"]),
        "audit_log_cheapest_plan": cheapest(features["audit"]),
        "invoicing_on_entry": on_entry(features["invoicing"], entry),
        "api_on_entry": on_entry(features["api"], entry),
        "approvals_on_entry": on_entry(features["approvals"], entry),
        "budgets_on_entry": on_entry(features["budgets"], entry),
        "phone_support_on_entry": on_entry(features["phone"], entry),
        "mobile_app": ("yes" if "yes" in {_flag(page, c) for c in mobile_row.values()} else "no") if mobile_row
        else company_wide("mobile_app"),
        "uptime_sla_percent": max(sla) if sla else NOT_STATED,
        "eu_hosting": company_wide("eu_hosting"),
        "soc2_type2": company_wide("soc2_type2"),
        "dpa": company_wide("dpa"),
    }
    before = dict(cells)
    before.update({
        "trial_days": base_trial, "entry_price_usd": base_prices[base_entry],
        "entry_min_users": base_users[base_entry] if base_users else NOT_STATED,
        "sso_on_entry": on_entry(base_features["sso"], base_entry),
        "sso_cheapest_plan": cheapest(base_features["sso"]),
        "audit_log_cheapest_plan": cheapest(base_features["audit"]),
        "api_on_entry": on_entry(base_features["api"], base_entry),
        "approvals_on_entry": on_entry(base_features["approvals"], base_entry),
    })
    return cells, before


def _claim_holds(table: dict, number: int) -> bool:
    """Whether a draft claim holds for every value its `not stated` cells might really have."""
    others = [company for company in COMPANIES if company != US]
    ours = table[US]

    def worlds(attributes: list[str]):
        """Every way the not-stated cells of these attributes could really be."""
        open_cells = [(company, attribute) for company in COMPANIES for attribute in attributes
                      if table[company][attribute] == NOT_STATED]
        choices = {"yes_no": ["yes", "no"], "number": [-1e9, 1e9], "plan": ["?"], "projects": [0.0]}
        for picked in itertools.product(*(choices[ATTRIBUTES[attribute]] for _company, attribute in open_cells)):
            world = {company: dict(row) for company, row in table.items()}
            for (company, attribute), value in zip(open_cells, picked):
                world[company][attribute] = value
            yield world

    tests = {
        1: (["entry_price_usd"], lambda w: all(w[US]["entry_price_usd"] < w[c]["entry_price_usd"] for c in others)),
        2: (["free_plan"], lambda w: w[US]["free_plan"] == "yes" and sum(w[c]["free_plan"] == "yes" for c in COMPANIES) == 2),
        3: (["sso_on_entry"], lambda w: w[US]["sso_on_entry"] == "yes" and all(w[c]["sso_on_entry"] == "no" for c in others)),
        4: (["trial_days"], lambda w: all(w[c]["trial_days"] <= 0 or w[US]["trial_days"] > w[c]["trial_days"] for c in others)),
        5: (["approvals_on_entry", "budgets_on_entry"], lambda w: all(
            (w[c]["approvals_on_entry"], w[c]["budgets_on_entry"]) == ("yes", "yes") for c in [US])
            and not any((w[c]["approvals_on_entry"], w[c]["budgets_on_entry"]) == ("yes", "yes") for c in others)),
        6: (["soc2_type2", "eu_hosting"], lambda w: (w[US]["soc2_type2"], w[US]["eu_hosting"]) == ("yes", "yes") and sum(
            (w[c]["soc2_type2"], w[c]["eu_hosting"]) == ("yes", "yes") for c in COMPANIES) == 3),
        7: (["eu_hosting", "top_plan_price_usd"], lambda w: all(
            w[c]["eu_hosting"] == "no" or w[US]["top_plan_price_usd"] < w[c]["top_plan_price_usd"] for c in others)),
        8: (["entry_min_users"], lambda w: w[US]["entry_min_users"] == 1 and all(w[c]["entry_min_users"] >= 2 for c in others)),
        9: (["phone_support_on_entry"], lambda w: w[US]["phone_support_on_entry"] == "yes"
            and all(w[c]["phone_support_on_entry"] == "no" for c in others)),
    }
    attributes, test = tests[number]
    assert all(ours[attribute] != NOT_STATED for attribute in attributes)
    return all(test(world) for world in worlds(attributes))


@lru_cache(maxsize=1)
def comparison_reference() -> dict:
    """The table the brief defines, read from the ten pages, and the verdict on each draft claim."""
    table, before = {}, {}
    for company in COMPANIES:
        table[company], before[company] = _company_cells(company)
    groups: dict[str, list[tuple[str, str]]] = {"overrides": [], "not_stated": [], "prices": [], "look_alikes": [], "other": []}
    for company in COMPANIES:
        for attribute in ATTRIBUTES:
            cell, value, earlier = (company, attribute), table[company][attribute], before[company][attribute]
            if earlier != value and earlier != NOT_STATED:
                groups["overrides"].append(cell)
            elif value == NOT_STATED:
                groups["not_stated"].append(cell)
            elif attribute in PRICE_ATTRIBUTES:
                groups["prices"].append(cell)
            elif cell in LOOK_ALIKES:
                groups["look_alikes"].append(cell)
            else:
                groups["other"].append(cell)
    claims = {number: "supportable" if _claim_holds(table, number) else "not supportable" for number in range(1, 10)}
    return {"table": table, "claims": claims, "groups": groups}


def _company_of(text: object) -> str | None:
    key = re.sub(r"[^a-z]", "", common.norm(text))
    return next((company for company in COMPANIES if key == company or key == company + "time"), None)


def _cell_matches(kind: str, expected: object, given: object, company: str) -> bool:
    value = common.norm(given).strip("*_`. ")
    if expected in (NOT_STATED, "none", "unlimited") or value in (NOT_STATED, "none", "unlimited"):
        return value == expected
    if kind == "yes_no":
        return value == expected
    if kind in ("number", "projects"):
        found = re.findall(r"\d[\d,]*(?:\.\d+)?", value)
        return len(found) == 1 and abs(float(found[0].replace(",", "")) - float(expected)) <= 0.005
    words = value.replace("-", " ").split()
    for name in (company, "time", "plan"):  # "Brisktime Business", "Business plan"
        if words and words[0] == name:
            words = words[1:]
        if words and words[-1] == name:
            words = words[:-1]
    return " ".join(words) == common.norm(expected)


def _verdict(text: object) -> str | None:
    value = common.norm(text).strip("*_`. ").replace("_", " ").replace("-", " ")
    return value if value in ("supportable", "not supportable") else None


def comparison_facts(response_text: str) -> dict:
    reference = comparison_reference()
    found = common.tables(response_text, COMPARISON_FILES)
    rows = found["comparison.csv"] or []
    by_company: dict[str, list[dict]] = {}
    unknown = 0
    for row in rows:
        company = _company_of(common.cell(row, "company"))
        if company:
            by_company.setdefault(company, []).append(row)
        elif any(str(value).strip() for value in row.values()):
            unknown += 1
    single = {company: found_rows[0] for company, found_rows in by_company.items() if len(found_rows) == 1}
    header = set(rows[0]) if rows else set()
    structure = unknown + sum(1 for company in COMPANIES if company not in single)
    structure += sum(1 for attribute in ATTRIBUTES if attribute not in header)

    def errors(group: str) -> int:
        return sum(
            1 for company, attribute in reference["groups"][group]
            if company not in single or attribute not in single[company]
            or not _cell_matches(ATTRIBUTES[attribute], reference["table"][company][attribute],
                                 single[company][attribute], company))

    stated: dict[int, list[str | None]] = {}
    claim_structure = 0
    for row in found["claims.csv"] or []:
        number = _integer(common.cell(row, "claim"))
        if number in reference["claims"]:
            stated.setdefault(number, []).append(_verdict(common.cell(row, "verdict")))
        elif any(str(value).strip() for value in row.values()):
            claim_structure += 1
    claim_structure += sum(1 for number in reference["claims"] if len(stated.get(number, [])) != 1
                           or stated[number][0] is None)
    facts = {
        "comparison_missing_file_count": sum(1 for name in COMPARISON_FILES if found[name] is None),
        "comparison_structure_error_count": structure,
        "comparison_override_cell_error_count": errors("overrides"),
        "comparison_not_stated_cell_error_count": errors("not_stated"),
        "comparison_price_cell_error_count": errors("prices"),
        "comparison_look_alike_cell_error_count": errors("look_alikes"),
        "comparison_other_cell_error_count": errors("other"),
        "comparison_claim_structure_error_count": claim_structure,
    }
    for number, verdict in reference["claims"].items():
        facts[f"comparison_claim_{number}_wrong"] = int(stated.get(number) != [verdict])
    return facts


# ─────────────────────────────────────────────────────────────── launch-timeline

TIMELINE_TASK_ID = "launch-timeline"
TIMELINE_DIR = FIXTURES / "launch-timeline"
TIMELINE_FILES = ["schedule.csv", "answers.csv"]
TIMELINE_ITEMS = ["launch_date", "critical_path", "target_met", "cut", "launch_date_after_cut"]
_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_TASK_ID = re.compile(r"\bT(\d{2})\b", re.IGNORECASE)
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _iso(text: str) -> _dt.date:
    return _dt.date.fromisoformat(text)


def _table_rows(markdown: str, heading: str) -> list[list[str]]:
    """The body rows of the first table under a heading."""
    section = markdown.split(heading, 1)[1].split("\n## ", 1)[0]
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in section.splitlines() if line.startswith("|")]
    return rows[2:]


def _weekdays(text: str) -> set[int]:
    if text == "Monday to Friday":
        return {0, 1, 2, 3, 4}
    if text == "every calendar day":
        return set(range(7))
    return {_WEEKDAYS.index(day) for day in re.findall(r"[A-Z][a-z]+day", text)}


@lru_cache(maxsize=1)
def timeline_inputs() -> dict:
    """The plan, every owner's working days and the target, as the fixture files state them."""
    brief = (TIMELINE_DIR / "launch_brief.md").read_text()
    calendar = (TIMELINE_DIR / "team_calendar.md").read_text()
    flat = " ".join(brief.split())
    start = _iso(re.search(r"The work starts on Monday (\S+),", flat).group(1))
    target = _iso(re.search(r"the launch is on \*\*(\S+)\*\*", flat).group(1))
    holidays = {office: {_iso(day) for day in re.findall(r"(\d{4}-\d{2}-\d{2}) \(", days)}
                for office, _working, days in _table_rows(calendar, "## Offices")}
    owners: dict[str, dict] = {}
    for name, _role, office, works, away in _table_rows(calendar, "## People"):
        absent: set[_dt.date] = set()
        if away != "none":
            first, last = (_iso(day) for day in away.split(" to "))
            absent = {first + _dt.timedelta(days=n) for n in range((last - first).days + 1)}
        owners[name] = {"weekdays": _weekdays(works), "off": holidays[office] | absent}
    for name, _what, works in _table_rows(calendar, "## Outside suppliers"):
        owners[name] = {"weekdays": _weekdays(works), "off": set()}
    tasks = {}
    for row in _read_csv(TIMELINE_DIR / "launch_plan.csv"):
        deps = []
        for entry in row["depends_on"].split():
            other, _plus, lead = entry.partition("+")
            deps.append((other, int(lead) if lead else 1))
        assert row["duration_unit"] == ("calendar days" if owners[row["owner"]]["weekdays"] == set(range(7))
                                        else "working days"), row["task_id"]
        tasks[row["task_id"]] = {"owner": row["owner"], "days": int(row["duration"]), "deps": deps,
                                 "optional": row["optional"] == "yes",
                                 "not_before": _iso(row["not_before"]) if row["not_before"] else None}
    working = {}
    for name, owner in owners.items():
        days, day = [], start
        while day < start + _dt.timedelta(days=500):
            if day.weekday() in owner["weekdays"] and day not in owner["off"]:
                days.append(day)
            day += _dt.timedelta(days=1)
        working[name] = days
    return {"start": start, "target": target, "tasks": tasks, "working": working,
            "index": {name: {day: n for n, day in enumerate(days)} for name, days in working.items()},
            "launch": max(tasks)}


def _on_or_after(inputs: dict, owner: str, day: _dt.date) -> int:
    """The index of the owner's first working day on or after a date."""
    return bisect.bisect_left(inputs["working"][owner], day)


def timeline_schedule(cut: tuple[str, ...] = ()) -> dict:
    """Every task's first and last day under the brief's rules, with the given
    optional tasks cut, and each task's slack in its owner's days."""
    inputs = timeline_inputs()
    tasks, working = inputs["tasks"], inputs["working"]
    kept = [task_id for task_id in sorted(tasks) if task_id not in cut]

    def waits_for(task_id: str) -> dict[str, int]:
        """What a task waits for once the cut tasks are gone: task -> lead time in days."""
        out: dict[str, int] = {}
        stack = list(tasks[task_id]["deps"])
        while stack:
            other, lead = stack.pop()
            if other in cut:
                stack.extend(tasks[other]["deps"])
            else:
                out[other] = max(out.get(other, 0), lead)
        return out

    before: dict[str, dict[str, int]] = {}
    previous: dict[str, str] = {}
    for task_id in kept:
        owner = tasks[task_id]["owner"]
        before[task_id] = waits_for(task_id)
        if owner in previous:
            before[task_id][previous[owner]] = max(before[task_id].get(previous[owner], 0), 1)
        previous[owner] = task_id
    first: dict[str, _dt.date] = {}
    last: dict[str, _dt.date] = {}
    for task_id in kept:
        task = tasks[task_id]
        earliest = max([inputs["start"], task["not_before"] or inputs["start"]]
                       + [last[other] + _dt.timedelta(days=lead) for other, lead in before[task_id].items()])
        number = _on_or_after(inputs, task["owner"], earliest)
        first[task_id] = working[task["owner"]][number]
        last[task_id] = working[task["owner"]][number + task["days"] - 1]
    after: dict[str, list[tuple[str, int]]] = {task_id: [] for task_id in kept}
    for task_id, others in before.items():
        for other, lead in others.items():
            after[other].append((task_id, lead))
    launch = kept[-1]
    latest_start: dict[str, _dt.date] = {}
    slack: dict[str, int] = {}
    for task_id in reversed(kept):
        owner = tasks[task_id]["owner"]
        bound = min((latest_start[other] - _dt.timedelta(days=lead) for other, lead in after[task_id]),
                    default=last[launch])
        latest_finish = bisect.bisect_right(working[owner], bound) - 1        # its last working day on or before
        latest_start[task_id] = working[owner][latest_finish - tasks[task_id]["days"] + 1]
        slack[task_id] = latest_finish - inputs["index"][owner][last[task_id]]
    return {"first": first, "last": last, "slack": slack, "launch": first[launch]}


@lru_cache(maxsize=1)
def timeline_reference() -> dict:
    inputs = timeline_inputs()
    plan = timeline_schedule()
    critical = sorted((task_id for task_id, value in plan["slack"].items() if value == 0), key=lambda t: (plan["first"][t], t))
    optional = [task_id for task_id, task in inputs["tasks"].items() if task["optional"]]
    best: tuple | None = None
    for size in range(len(optional) + 1):
        for cut in itertools.combinations(optional, size):
            launch = timeline_schedule(cut)["launch"]
            if launch <= inputs["target"] and (best is None or (launch, cut) < best[1:]):
                best = (size, launch, cut)
        if best is not None:
            break
    return {
        "starts": plan["first"], "finishes": plan["last"], "launch_date": plan["launch"],
        "critical_path": critical, "slack": plan["slack"],
        "target_met": "yes" if plan["launch"] <= inputs["target"] else "no",
        "cut": list(best[2]) if best else [], "launch_date_after_cut": best[1] if best else None,
    }


def _one_date(text: object) -> _dt.date | None:
    found = _DATE.findall(str(text or ""))
    if len(found) != 1:
        return None
    try:
        return _dt.date(*(int(part) for part in found[0]))
    except ValueError:
        return None


def _task_ids(text: object) -> list[str]:
    return [f"T{number}" for number in _TASK_ID.findall(str(text or ""))]


def timeline_facts(response_text: str) -> dict:
    inputs = timeline_inputs()
    reference = timeline_reference()
    found = common.tables(response_text, TIMELINE_FILES)
    rows: dict[str, list[dict]] = {}
    unknown = 0
    for row in found["schedule.csv"] or []:
        ids = _task_ids(common.cell(row, "task_id", "task"))
        if len(ids) == 1 and ids[0] in inputs["tasks"]:
            rows.setdefault(ids[0], []).append(row)
        elif any(str(value).strip() for value in row.values()):
            unknown += 1
    single = {task_id: found_rows[0] for task_id, found_rows in rows.items() if len(found_rows) == 1}
    starts = {task_id: _one_date(common.cell(row, "start")) for task_id, row in single.items()}
    wrong_starts = sum(1 for task_id, day in reference["starts"].items() if starts.get(task_id) != day)
    wrong_slack = sum(1 for task_id, value in reference["slack"].items()
                      if task_id not in single or _integer(common.cell(single[task_id], "slack")) != value)
    # Each finish follows from its own start by its owner's calendar, whatever start the reply gives.
    calendar_errors = 0
    for task_id, task in inputs["tasks"].items():
        start = starts.get(task_id)
        finish = _one_date(common.cell(single[task_id], "finish")) if task_id in single else None
        index = inputs["index"][task["owner"]]
        if start not in index or finish != inputs["working"][task["owner"]][index[start] + task["days"] - 1]:
            calendar_errors += 1

    items: dict[str, list[str]] = {}
    extra_items = 0
    for row in found["answers.csv"] or []:
        name = common.norm(common.cell(row, "item")).strip("`").replace(" ", "_")
        if name in TIMELINE_ITEMS:
            items.setdefault(name, []).append(common.cell(row, "answer"))
        elif name:
            extra_items += 1

    def answer(name: str) -> str | None:
        given = items.get(name)
        return given[0] if given and len(given) == 1 else None

    cut = answer("cut")
    cut_ids = _task_ids(cut) if cut is not None else None
    facts = {
        "timeline_missing_file_count": sum(1 for name in TIMELINE_FILES if found[name] is None),
        "timeline_task_row_error_count": unknown + sum(1 for task_id in inputs["tasks"] if task_id not in single),
        "timeline_wrong_start_count": wrong_starts,
        "timeline_calendar_error_count": calendar_errors,
        "timeline_wrong_slack_count": wrong_slack,
        "timeline_answer_item_error_count": extra_items + sum(1 for name in TIMELINE_ITEMS if answer(name) is None),
        "timeline_launch_date_wrong": int(_one_date(answer("launch_date")) != reference["launch_date"]),
        "timeline_critical_path_wrong": int(_task_ids(answer("critical_path")) != reference["critical_path"]),
        "timeline_target_met_wrong": int(_yes_no(answer("target_met")) != reference["target_met"]),
        "timeline_cut_wrong": int(cut_ids is None or len(set(cut_ids)) != len(cut_ids)
                                  or set(cut_ids) != set(reference["cut"])),
        "timeline_launch_after_cut_wrong": int(
            _one_date(answer("launch_date_after_cut")) != reference["launch_date_after_cut"]),
    }
    return facts


# ──────────────────────────────────────────────────────────────── the hook

_HANDLERS = {
    BUDGET_TASK_ID: budget_facts,
    COMPARISON_TASK_ID: comparison_facts,
    TIMELINE_TASK_ID: timeline_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts a strategy task adds, or nothing for any other task."""
    handler = _HANDLERS.get((task or {}).get("id"))
    return handler(response_text) if handler else {}
