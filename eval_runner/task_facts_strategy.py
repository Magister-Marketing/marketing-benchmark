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
BUDGET_FILES = ["allocation.csv", "constraints.csv"]


@lru_cache(maxsize=1)
def budget_inputs() -> dict:
    """The rules and the forecasts, as the three fixture files state them."""
    brief = (BUDGET_DIR / "planning_brief.md").read_text()

    def dollars(label: str) -> int:
        match = re.search(re.escape(label) + r"\*\*\s*\$([\d,]+)", brief)
        return int(match.group(1).replace(",", ""))

    budget = dollars("Quarter budget:")
    block = int(re.search(r"whole blocks of \$([\d,]+)", brief).group(1).replace(",", ""))
    capacity = int(re.search(r"at most \*\*(\d+) new leads\*\*", brief).group(1))
    channels: dict[str, dict] = {}
    for row in _read_csv(BUDGET_DIR / "channel_terms.csv"):
        channels[row["channel"]] = {
            "max": int(row["max_blocks"]),
            "min_if_used": int(row["minimum_if_used_blocks"]),
            "committed": int(row["committed_blocks"]),
            # The licence is held for each of the quarter's three months.
            "fee": int(row["fee_usd_per_month"]) * 3,
            "routed": row["routed_to_aes"] == "yes",
            "leads": [],
        }
    for row in _read_csv(BUDGET_DIR / "channel_forecasts.csv"):
        channel = channels[row["channel"]]
        assert int(row["block"]) == len(channel["leads"]) + 1
        channel["leads"].append(int(row["added_leads"]))
    constraints = re.findall(r"`([a-z_]+)`", brief.split("## Constraints, by name", 1)[1].split("\n\n")[1])
    return {"budget": budget, "block": block, "capacity": capacity, "channels": channels,
            "constraints": constraints}


def budget_split_figures(blocks: dict[str, int]) -> dict:
    """What a split costs and projects, by the brief's rules."""
    inputs = budget_inputs()
    channels = inputs["channels"]
    cost = leads = routed = 0
    for name, count in blocks.items():
        channel = channels[name]
        if count:
            got = sum(channel["leads"][:count])
            cost += count * inputs["block"] + channel["fee"]
            leads += got
            routed += got if channel["routed"] else 0
    return {"cost": cost, "leads": leads, "routed": routed}


def _budget_options(channel: dict) -> list[int]:
    low = max(1, channel["min_if_used"], channel["committed"])
    return ([] if channel["committed"] else [0]) + list(range(low, channel["max"] + 1))


def best_budget_split(*, with_capacity: bool = True) -> dict[str, int]:
    """The split with the most leads under every rule (the AE capacity
    optional), the cheaper one on a tie. Every split is tried: there are
    under a hundred thousand."""
    inputs = budget_inputs()
    names = list(inputs["channels"])
    best: tuple | None = None
    for combo in itertools.product(*(_budget_options(inputs["channels"][name]) for name in names)):
        blocks = dict(zip(names, combo))
        figures = budget_split_figures(blocks)
        if figures["cost"] > inputs["budget"]:
            continue
        if with_capacity and figures["routed"] > inputs["capacity"]:
            continue
        key = (figures["leads"], -figures["cost"])
        if best is None or key > best[0]:
            best = (key, blocks)
    return best[1]


def budget_binding(blocks: dict[str, int]) -> dict[str, str]:
    """Whether each named constraint binds in a split, by the brief's definitions."""
    inputs = budget_inputs()
    channels = inputs["channels"]
    figures = budget_split_figures(blocks)
    below_max = [name for name, channel in channels.items() if channel["routed"] and blocks[name] < channel["max"]]
    over = all(figures["routed"] + channels[name]["leads"][blocks[name]] > inputs["capacity"] for name in below_max)
    binding = {
        "budget": inputs["budget"] - figures["cost"] < inputs["block"],
        "ae_capacity": bool(below_max) and over,
    }
    for name, channel in channels.items():
        if channel["min_if_used"]:
            binding[f"{name}_min_order"] = blocks[name] == channel["min_if_used"]
        if channel["committed"]:
            binding[f"{name}_commitment"] = blocks[name] == channel["committed"]
        binding[f"{name}_max"] = blocks[name] == channel["max"]
    assert set(binding) == set(inputs["constraints"]), "the brief names the constraints the definitions cover"
    return {name: "yes" if binding[name] else "no" for name in inputs["constraints"]}


@lru_cache(maxsize=1)
def budget_reference() -> dict:
    """The one right answer, and the figures the answer block asks for."""
    inputs = budget_inputs()
    split = best_budget_split()
    figures = budget_split_figures(split)
    uncapped = budget_split_figures(best_budget_split(with_capacity=False))
    per_lead = (Decimal(figures["cost"]) / Decimal(figures["leads"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return {
        "blocks": split,
        "binding": budget_binding(split),
        "answers": {
            1: float(figures["cost"]),
            2: float(figures["leads"]),
            3: float(per_lead),
            4: float(figures["routed"]),
            5: float(uncapped["leads"] - figures["leads"]),
        },
        "left_over": inputs["budget"] - figures["cost"],
    }


def budget_facts(response_text: str) -> dict:
    inputs = budget_inputs()
    channels = inputs["channels"]
    reference = budget_reference()
    found = common.tables(response_text, BUDGET_FILES)
    rows = found["allocation.csv"] or []
    by_channel: dict[str, list[dict]] = {}
    unknown = 0
    for row in rows:
        name = common.norm(common.cell(row, "channel")).replace(" ", "_")
        if name in channels:
            by_channel.setdefault(name, []).append(row)
        elif any(str(value).strip() for value in row.values()):
            unknown += 1
    single = {name: found_rows[0] for name, found_rows in by_channel.items() if len(found_rows) == 1}
    blocks = {name: _integer(common.cell(row, "blocks")) for name, row in single.items()}

    channel_errors = unknown + sum(1 for name in channels if name not in single)
    wrong_blocks = sum(1 for name, count in reference["blocks"].items() if blocks.get(name) != count)

    # The reply's own split, held to every rule. A split that cannot be read
    # cannot be shown to keep them.
    infeasible = 0
    readable = {name: count for name, count in blocks.items() if count is not None}
    if found["allocation.csv"] is None or len(readable) != len(channels):
        infeasible += 1
    split = {name: readable.get(name, 0) for name in channels}
    for name, count in split.items():
        channel = channels[name]
        if count < 0 or count > channel["max"]:
            infeasible += 1
            split[name] = max(0, min(count, channel["max"]))
        if split[name] < channel["committed"]:
            infeasible += 1
        if 0 < split[name] < channel["min_if_used"]:
            infeasible += 1
    figures = budget_split_figures(split)
    infeasible += figures["cost"] > inputs["budget"]
    infeasible += figures["routed"] > inputs["capacity"]

    # Each row agrees with its own block count: spend, leads and fee.
    arithmetic_errors = fee_errors = 0
    for name, channel in channels.items():
        row, count = single.get(name), blocks.get(name)
        if row is None or count is None or not 0 <= count <= channel["max"]:
            arithmetic_errors += 1
            fee_errors += 1
            continue
        spend = common.money(common.cell(row, "media_spend_usd", "media_spend", "spend_usd"))
        leads = _integer(common.cell(row, "leads", "projected_leads"))
        if spend != count * inputs["block"] or leads != sum(channel["leads"][:count]):
            arithmetic_errors += 1
        fee = common.money(common.cell(row, "fee_usd", "fee"))
        if fee != (channel["fee"] if count else 0):
            fee_errors += 1

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
        "budget_channel_row_error_count": channel_errors,
        "budget_infeasible_count": infeasible,
        "budget_wrong_blocks_count": wrong_blocks,
        "budget_row_arithmetic_error_count": arithmetic_errors,
        "budget_fee_error_count": fee_errors,
        "budget_binding_error_count": binding_errors,
    }


# ───────────────────────────────────────────────────────── competitor-comparison

COMPARISON_TASK_ID = "competitor-comparison"
COMPARISON_DIR = FIXTURES / "competitor-comparison"
COMPARISON_FILES = ["comparison.csv", "claims.csv"]
COMPANIES = ["tallyhour", "brisktime", "quillhour", "ticklog", "fenwork", "larchpoint"]
US = "tallyhour"
NOT_STATED = "not stated"
# Each attribute and the kind of value its cells hold.
ATTRIBUTES = {
    "free_plan": "yes_no", "trial_days": "number", "entry_plan": "plan", "entry_price_usd": "number",
    "entry_min_users": "number", "sso_on_entry": "yes_no", "sso_cheapest_plan": "plan",
    "invoicing_on_entry": "yes_no", "api_on_entry": "yes_no", "top_plan_price_usd": "number",
    "uptime_sla_percent": "number", "eu_hosting": "yes_no",
}
PRICE_ATTRIBUTES = ("entry_price_usd", "top_plan_price_usd")
TIER_ATTRIBUTES = ("sso_on_entry", "sso_cheapest_plan", "invoicing_on_entry", "api_on_entry")

# Where each cell's value is stated on its company's page: a plan-table row, a
# sentence, an FAQ answer, or nothing at all. The value itself is read from
# the page through this, so a page that changes changes the answer, and one
# that stops saying what its source says stops the oracle.
_ENTRY, _TOP = "entry", "top"
PRICE_ROWS = {  # the row each company's prices are read from, and what one price there covers
    "tallyhour": ("Billed monthly", "month"),
    "brisktime": ("Price per user per year", "year"),
    "quillhour": ("Billed monthly, per user per month", "month"),
    "ticklog": ("Price", "month"),
    "fenwork": ("Price", "month"),
    "larchpoint": ("Per user per month, billed monthly", "month"),
}
_SLA_NOT_STATED = [r"\bSLA\b", r"service[- ]level", r"\bcommit"]
SOURCES: dict[str, dict[str, tuple]] = {
    "tallyhour": {
        "free_plan": ("quote", "The Free plan is free for as long as you use it", "yes"),
        "trial_days": ("text", r"(\d+)-day free trial"),
        "entry_min_users": ("table_number", "Users"),
        "sso_on_entry": ("table_flag", "Single sign-on (SAML)"),
        "invoicing_on_entry": ("table_flag", "Invoices from tracked time"),
        "api_on_entry": ("table_flag", "API access"),
        "uptime_sla_percent": ("text", r"(\d+(?:\.\d+)?)% uptime SLA"),
        "eu_hosting": ("any_plan_flag", "EU data hosting"),
    },
    "brisktime": {
        "free_plan": ("absent", [r"free plan", r"free forever", r"free tier", r"\$0\b"]),
        "trial_days": ("faq", "Is there a free trial?", r"free for (\d+) days"),
        "entry_min_users": ("table_number", "Minimum seats"),
        "sso_on_entry": ("table_flag", "Single sign-on (SAML) and SCIM"),
        "invoicing_on_entry": ("table_flag", "Invoicing"),
        "api_on_entry": ("table_flag", "API access"),
        "uptime_sla_percent": ("max_percent", "Uptime SLA"),
        "eu_hosting": ("quote", "EU hosting is not available", "no"),
    },
    "quillhour": {
        "free_plan": ("quote", "Quillhour has no free plan", "no"),
        "trial_days": ("text", r"(\d+)-day free trial"),
        "entry_min_users": ("faq", "What is the smallest team I can sign up?", r"start at (\d+) users"),
        "sso_on_entry": ("table_flag", "SAML single sign-on"),
        "invoicing_on_entry": ("table_flag", "Invoicing"),
        "api_on_entry": ("table_flag", "API access"),
        "uptime_sla_percent": ("absent", _SLA_NOT_STATED),
        "eu_hosting": ("any_plan_flag", "EU data residency"),
    },
    "ticklog": {
        "free_plan": ("quote", "Ticklog has no free plan", "no"),
        "trial_days": ("quote", "no free trial", 0),
        "entry_min_users": ("table_number", "Minimum users"),
        "sso_on_entry": ("table_flag", "SAML single sign-on"),
        "invoicing_on_entry": ("table_flag", "Invoicing from timesheets"),
        "api_on_entry": ("faq", "Is the REST API included on Basic?", r"^Yes\b", "yes"),
        "uptime_sla_percent": ("max_percent", "Uptime SLA"),
        "eu_hosting": ("absent", [r"\bEU\b", r"europe", r"hosting", r"hosted", r"residency", r"data cent", r"region"]),
    },
    "fenwork": {
        "free_plan": ("faq", "Is there a free plan?", r"^No\b", "no"),
        "trial_days": ("faq", "How long is the free trial?", r"(\d+)-day free trial"),
        "entry_min_users": ("absent", [r"minimum", r"\bfrom \d", r"at least", r"\bseats?\b", r"\d+ users"]),
        "sso_on_entry": ("table_flag", "Single sign-on"),
        "invoicing_on_entry": ("table_flag", "Invoicing"),
        "api_on_entry": ("table_flag", "API access"),
        "uptime_sla_percent": ("text", r"(\d+(?:\.\d+)?)% uptime SLA"),
        "eu_hosting": ("quote", "Every plan lets you choose EU or US hosting", "yes"),
    },
    "larchpoint": {
        "free_plan": ("quote", "Larchpoint has no free plan", "no"),
        "trial_days": ("text", r"(\d+)-day free trial"),
        "entry_min_users": ("table_number", "Users"),
        "sso_on_entry": ("table_flag", "Single sign-on through your identity provider"),
        "invoicing_on_entry": ("table_flag", "Client invoicing"),
        "api_on_entry": ("absent", [r"\bAPI\b", r"integrat", r"developer"]),
        "uptime_sla_percent": ("max_percent", "Uptime SLA"),
        "eu_hosting": ("quote", "We do not offer EU hosting", "no"),
    },
}
# The cells where a page's FAQ overrides what its plan table says.
FAQ_OVERRIDES = {("fenwork", "trial_days"), ("ticklog", "api_on_entry"), ("quillhour", "entry_min_users")}


def _page(company: str) -> dict:
    """A saved pricing page: its text, its plan table and its FAQ."""
    text = (COMPARISON_DIR / f"{company}.md").read_text()
    lines = text.splitlines()
    rows = [line for line in lines if line.startswith("|")]
    header = [cell.strip() for cell in rows[0].strip("|").split("|")]
    table = {}
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        table[cells[0]] = dict(zip(header[1:], cells[1:]))
    faq = dict(re.findall(r"(?m)^\*\*(.+?)\*\*\n(.+)$", text.split("## FAQ", 1)[1])) if "## FAQ" in text else {}
    return {"text": text, "plans": header[1:], "table": table, "faq": faq}


def _price(cell: str, per: str) -> float | str:
    if "contact sales" in cell.lower():
        return NOT_STATED
    value = Decimal(re.fullmatch(r"\$(\d+(?:\.\d+)?)", cell).group(1))
    if per == "year":
        value = (value / 12).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return float(value)


def _flag(cell: str) -> str:
    return {"✓": "yes", "—": "no"}[cell]


@lru_cache(maxsize=1)
def comparison_reference() -> dict:
    """The table the brief defines, read from the six pages, and the verdict
    on each draft claim."""
    table: dict[str, dict[str, object]] = {}
    for company in COMPANIES:
        page = _page(company)
        label, per = PRICE_ROWS[company]
        prices = page["table"][label]
        if per == "year":  # sold only on annual billing
            assert set(page["table"]["Billing"].values()) == {"Annual only"}
        entry = next(plan for plan in page["plans"] if prices[plan] == "Contact sales" or _price(prices[plan], per) > 0)
        top = page["plans"][-1]
        cells: dict[str, object] = {
            "entry_plan": entry,
            "entry_price_usd": _price(prices[entry], per),
            "top_plan_price_usd": _price(prices[top], per),
        }
        for attribute, source in SOURCES[company].items():
            kind = source[0]
            if kind == "quote":
                assert source[1] in page["text"], (company, attribute)
                value = source[2]
            elif kind == "text":
                value = float(re.search(source[1], page["text"]).group(1))
            elif kind == "faq":
                answer = page["faq"][source[1]]
                match = re.search(source[2], answer)
                assert match, (company, attribute)
                value = source[3] if len(source) > 3 else float(match.group(1))
            elif kind == "absent":
                assert not any(re.search(term, page["text"], re.IGNORECASE) for term in source[1]), (company, attribute)
                value = NOT_STATED
            elif kind == "table_flag":
                value = _flag(page["table"][source[1]][entry])
            elif kind == "table_number":
                value = float(re.search(r"\d+", page["table"][source[1]][entry]).group(0))
            elif kind == "any_plan_flag":
                value = "yes" if "yes" in {_flag(cell) for cell in page["table"][source[1]].values()} else "no"
            elif kind == "max_percent":
                value = max(float(cell.rstrip("%")) for cell in page["table"][source[1]].values() if cell != "—")
            else:
                raise ValueError(kind)
            cells[attribute] = value
        sso_row = SOURCES[company]["sso_on_entry"][1]
        cells["sso_cheapest_plan"] = next(
            (plan for plan in page["plans"] if page["table"][sso_row][plan] == "✓"), NOT_STATED)
        table[company] = {attribute: cells[attribute] for attribute in ATTRIBUTES}

    def numbers(attribute: str) -> list:
        return [table[company][attribute] for company in COMPANIES if company != US]

    def beats(attribute: str) -> bool:  # strictly below every competitor, every cell stated
        ours, theirs = table[US][attribute], numbers(attribute)
        return NOT_STATED not in theirs and ours != NOT_STATED and all(ours < value for value in theirs)

    def none_have(attribute: str) -> bool:
        return table[US][attribute] == "yes" and all(value == "no" for value in numbers(attribute))

    claims = {
        1: beats("entry_price_usd"),
        2: none_have("free_plan"),
        3: NOT_STATED not in numbers("trial_days") and all(table[US]["trial_days"] > v for v in numbers("trial_days")),
        4: none_have("sso_on_entry"),
        5: beats("top_plan_price_usd"),
    }
    groups: dict[str, list[tuple[str, str]]] = {"faq": [], "not_stated": [], "prices": [], "tiers": [], "other": []}
    for company in COMPANIES:
        for attribute in ATTRIBUTES:
            cell = (company, attribute)
            if cell in FAQ_OVERRIDES:
                groups["faq"].append(cell)
            elif table[company][attribute] == NOT_STATED:
                groups["not_stated"].append(cell)
            elif attribute in PRICE_ATTRIBUTES:
                groups["prices"].append(cell)
            elif attribute in TIER_ATTRIBUTES:
                groups["tiers"].append(cell)
            else:
                groups["other"].append(cell)
    return {
        "table": table,
        "claims": {number: "supportable" if holds else "not supportable" for number, holds in claims.items()},
        "groups": groups,
    }


def _company_of(text: object) -> str | None:
    key = re.sub(r"[^a-z]", "", common.norm(text))
    return next((company for company in COMPANIES if key == company or key == company + "time"), None)


def _cell_matches(kind: str, expected: object, given: object, company: str) -> bool:
    value = common.norm(given).strip("*_`. ")
    if expected == NOT_STATED or value == NOT_STATED:
        return value == expected
    if kind == "yes_no":
        return value == expected
    if kind == "number":
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
        "comparison_price_cell_error_count": errors("prices"),
        "comparison_tier_cell_error_count": errors("tiers"),
        "comparison_faq_cell_error_count": errors("faq"),
        "comparison_not_stated_cell_error_count": errors("not_stated"),
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


@lru_cache(maxsize=1)
def timeline_inputs() -> dict:
    """The plan, the calendar and the target, as the two fixture files state them."""
    brief = (TIMELINE_DIR / "launch_brief.md").read_text()
    start = _iso(re.search(r"The\nwork starts on Monday (\S+),", brief).group(1))
    target = _iso(re.search(r"the launch is on\n\*\*(\S+)\*\*", brief).group(1))
    holidays = {_iso(day) for day in re.findall(r"(?m)^- (\d{4}-\d{2}-\d{2}) \(", brief)}
    tasks = {}
    for row in _read_csv(TIMELINE_DIR / "launch_plan.csv"):
        tasks[row["task_id"]] = {
            "owner": row["owner"], "days": int(row["duration_days"]), "deps": row["depends_on"].split(),
            "optional": row["optional"] == "yes", "not_before": _iso(row["not_before"]) if row["not_before"] else None,
        }
    asked = re.findall(r"T\d{2}", brief.split("I also want the slack of", 1)[1])
    days, day = [], start
    while len(days) < 400:  # far beyond any schedule this plan can make
        if day.weekday() < 5 and day not in holidays:
            days.append(day)
        day += _dt.timedelta(days=1)
    return {"start": start, "target": target, "holidays": holidays, "tasks": tasks, "slack_asked": asked,
            "days": days, "index": {day: number for number, day in enumerate(days)}}



def _iso(text: str) -> _dt.date:
    return _dt.date.fromisoformat(text)


def timeline_schedule(cut: tuple[str, ...] = ()) -> dict:
    """Every task's first and last working day (as day numbers) under the
    brief's rules, with the given optional tasks cut, and each task's slack."""
    inputs = timeline_inputs()
    tasks, days = inputs["tasks"], inputs["days"]
    kept = [task_id for task_id in tasks if task_id not in cut]

    def depends(task_id: str) -> set[str]:
        out, stack, seen = set(), list(tasks[task_id]["deps"]), set()
        while stack:
            other = stack.pop()
            if other in seen:
                continue
            seen.add(other)
            if other in cut:
                stack.extend(tasks[other]["deps"])
            else:
                out.add(other)
        return out

    before: dict[str, list[str]] = {}
    last_of_owner: dict[str, str] = {}
    for task_id in sorted(kept):
        owner = tasks[task_id]["owner"]
        before[task_id] = sorted(depends(task_id)) + ([last_of_owner[owner]] if owner in last_of_owner else [])
        last_of_owner[owner] = task_id
    first, last = {}, {}
    for task_id in sorted(kept):
        earliest = 0
        not_before = tasks[task_id]["not_before"]
        if not_before is not None:
            earliest = next(number for number, day in enumerate(days) if day >= not_before)
        earliest = max([earliest] + [last[other] + 1 for other in before[task_id]])
        first[task_id], last[task_id] = earliest, earliest + tasks[task_id]["days"] - 1
    after: dict[str, list[str]] = {task_id: [] for task_id in kept}
    for task_id, others in before.items():
        for other in others:
            after[other].append(task_id)
    launch = max(kept)
    latest_start: dict[str, int] = {}
    for task_id in sorted(kept, reverse=True):
        latest_finish = min((latest_start[other] - 1 for other in after[task_id]), default=last[launch])
        latest_start[task_id] = latest_finish - tasks[task_id]["days"] + 1
    slack = {task_id: latest_start[task_id] - first[task_id] for task_id in kept}
    return {"first": first, "last": last, "slack": slack, "launch": first[launch]}


@lru_cache(maxsize=1)
def timeline_reference() -> dict:
    inputs = timeline_inputs()
    days, target = inputs["days"], inputs["target"]
    plan = timeline_schedule()
    critical = sorted((task_id for task_id, value in plan["slack"].items() if value == 0), key=lambda t: plan["first"][t])
    optional = [task_id for task_id, task in inputs["tasks"].items() if task["optional"]]
    best: tuple | None = None
    for size in range(len(optional) + 1):
        for cut in itertools.combinations(optional, size):
            launch = days[timeline_schedule(cut)["launch"]]
            if launch <= target and (best is None or (launch, cut) < best[1:]):
                best = (size, launch, cut)
        if best is not None:
            break
    return {
        "starts": {task_id: days[number] for task_id, number in plan["first"].items()},
        "finishes": {task_id: days[number] for task_id, number in plan["last"].items()},
        "launch_date": days[plan["launch"]],
        "critical_path": critical,
        "slack": {task_id: plan["slack"][task_id] for task_id in inputs["slack_asked"]},
        "target_met": "yes" if days[plan["launch"]] <= target else "no",
        "cut": list(best[2]) if best else [],
        "launch_date_after_cut": best[1] if best else None,
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
    # Each finish follows from its own start by the calendar: the duration in working days.
    index, days = inputs["index"], inputs["days"]
    calendar_errors = 0
    for task_id, task in inputs["tasks"].items():
        start = starts.get(task_id)
        finish = _one_date(common.cell(single[task_id], "finish")) if task_id in single else None
        if start not in index or finish != days[index[start] + task["days"] - 1]:
            calendar_errors += 1

    items: dict[str, list[str]] = {}
    extra_items = 0
    for row in found["answers.csv"] or []:
        name = common.norm(common.cell(row, "item")).strip("`").replace(" ", "_")
        if name in TIMELINE_ITEMS or name.startswith("slack_"):
            items.setdefault(name, []).append(common.cell(row, "answer"))
        elif name:
            extra_items += 1
    wanted = TIMELINE_ITEMS + [f"slack_{task_id.lower()}" for task_id in reference["slack"]]

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
        "timeline_answer_item_error_count": extra_items + sum(1 for name in wanted if answer(name) is None),
        "timeline_launch_date_wrong": int(_one_date(answer("launch_date")) != reference["launch_date"]),
        "timeline_critical_path_wrong": int(_task_ids(answer("critical_path")) != reference["critical_path"]),
        "timeline_target_met_wrong": int(_yes_no(answer("target_met")) != reference["target_met"]),
        "timeline_cut_wrong": int(cut_ids is None or len(set(cut_ids)) != len(cut_ids)
                                  or set(cut_ids) != set(reference["cut"])),
        "timeline_launch_after_cut_wrong": int(
            _one_date(answer("launch_date_after_cut")) != reference["launch_date_after_cut"]),
    }
    for task_id, value in reference["slack"].items():
        given = answer(f"slack_{task_id.lower()}")
        facts[f"timeline_slack_{task_id.lower()}_wrong"] = int(given is None or _integer(given) != value)
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
