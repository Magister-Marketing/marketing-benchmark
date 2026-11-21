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


# ──────────────────────────────────────────────────────────────── the hook

_HANDLERS = {
    BUDGET_TASK_ID: budget_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts a strategy task adds, or nothing for any other task."""
    handler = _HANDLERS.get((task or {}).get("id"))
    return handler(response_text) if handler else {}
