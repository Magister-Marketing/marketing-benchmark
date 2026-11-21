"""The strategy tasks: channel-budget-allocation, competitor-comparison, launch-timeline.

What is pinned here, for every task:

- the committed fixtures are exactly what `scripts/gen_tasks_strategy.py`
  writes, byte for byte;
- every value the task file asks a program to check is recomputed here from
  the committed fixtures, by code that shares nothing with the oracle in
  `eval_runner/task_facts_strategy.py`;
- a reference reply written by hand from those values passes every
  programmatic check, and the reply a careless but plausible reading gives
  scores zero on each check that reading touches;
- an empty reply earns nothing, and no odd reply makes a check raise.
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import io
import itertools
import math
import random
import re

import pytest

from eval_runner import bench, task_facts_strategy

FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"
STRATEGY_TASKS = ["channel-budget-allocation", "competitor-comparison", "launch-timeline"]
# Version 1 of each was run once (2026-11-20) and found too small; version 2 is the larger task.
VERSIONS = {"channel-budget-allocation": (2, 2), "competitor-comparison": (1, 1), "launch-timeline": (1, 1)}


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location(
        "gen_tasks_strategy", bench.REPO_ROOT / "scripts" / "gen_tasks_strategy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((FIXTURES / name).read_text())))


def _task(task_id: str) -> dict:
    return bench.load_tasks()[task_id]


def _by_id(task: dict) -> dict[str, dict]:
    return {c["id"]: c for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section]}


def _results(task_id: str, response: str) -> dict:
    task = _task(task_id)
    return bench.programmatic_results(task, bench.measured_facts(task, response))


def _failed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if not result["pass"]}


def _zeroed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if result["score"] == 0}


def _near(task_id: str) -> dict[str, float]:
    return {criterion_id: criterion["programmatic"]["near"] for criterion_id, criterion in _by_id(_task(task_id)).items()
            if "near" in (criterion.get("programmatic") or {})}


# ─────────────────────────────────────────────────────────── the set as a whole

def test_the_fixtures_are_what_the_generator_writes(generator, tmp_path):
    planned = generator.planned()
    assert planned and all(path.read_text() == text for path, text in planned.items())
    assert generator.drift() == []
    again = generator.planned()
    assert again == planned                                       # deterministic
    for task_id in STRATEGY_TASKS:
        fixtures = {bench.REPO_ROOT / path for path in _task(task_id)["fixtures"]}
        assert fixtures <= set(planned), task_id                  # every fixture is generated
        assert sum(path.stat().st_size for path in fixtures) < 60_000, task_id


def test_the_tasks_load_as_development_tasks_with_most_checks_by_program():
    for task_id in STRATEGY_TASKS:
        task = _task(task_id)
        assert task["split"] == "development" and (task["prompt_version"], task["rubric_version"]) == VERSIONS[task_id]
        criteria = list(_by_id(task).values())
        programmatic = [c for c in criteria if c.get("programmatic")]
        assert 10 <= len(criteria) <= 18, task_id
        assert len(programmatic) / len(criteria) >= 0.7, task_id
        assert bench.free_credit_scores(task) == {}, task_id     # an empty reply earns nothing
        assert bench.task_supports_harness(task, bench.HARNESS_ID)
        for skill in task["skills"]:
            assert (bench.REPO_ROOT / skill).is_file()


@pytest.mark.parametrize("text", [
    "", "\x00", "### allocation.csv\n```csv\nchannel,blocks\nsearch,1e999\nmeta,-3\nwebinars,99\n```\n",
    "### constraints.csv\nconstraint,binds\nbudget,yes\nbudget,no\n,\n", "A1: " + "9" * 5000,
    "### allocation.csv\n" + "search,1,5000,0,142\n" * 3000, " " * 20000,
])
def test_no_odd_reply_makes_a_check_raise(text):
    for task_id in STRATEGY_TASKS:
        task = _task(task_id)
        results = bench.programmatic_results(task, bench.measured_facts(task, text))
        assert results and not any(result["pass"] for result in results.values()), task_id


def test_other_tasks_get_no_strategy_facts():
    assert task_facts_strategy.facts_for(_task("headline"), "anything") == {}
    assert task_facts_strategy.facts_for(None, "anything") == {}


# ─────────────────────────────────────────────────── channel-budget-allocation

BUDGET = "channel-budget-allocation"
B_MONTHS = ["apr", "may", "jun"]
B_REGIONS = ["na", "emea", "apac"]
BLOCK = 10_000


def _budget_world() -> dict:
    """The rules and every block's leads, read again from the fixtures with code of this file's own."""
    brief = (FIXTURES / "channel-budget/planning_brief.md").read_text()
    flat = " ".join(brief.split())
    assert "**Quarter budget:** $1,400,000." in flat and "whole blocks of $10,000" in flat
    assert "| webinars | $3,200 for each month it is live |" in brief
    assert "| abm | $8,000 if it is live in one month, $13,000 if live in two, $17,000 if live in all three |" in brief
    assert ("| podcasts | $5,000 one-off agency setup if it is live in any month, plus $2,000 for each month it is "
            "live |") in brief
    assert "buys at least one block in that month in any region" in flat and "charged per channel, not per region" in flat
    licences = {"webinars": lambda months: 3_200 * months, "abm": lambda months: (0, 8_000, 13_000, 17_000)[months],
                "podcasts": lambda months: 5_000 + 2_000 * months if months else 0}
    regions = {}
    for line in brief.splitlines():
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) == 5 and parts[0] in B_REGIONS:
            low, high, month = (int(part.strip("$").replace(",", "")) // BLOCK for part in parts[1:4])
            regions[parts[0]] = {"min": low, "max": high, "month": month, "field": int(parts[4])}
    assert set(regions) == set(B_REGIONS)
    terms = {row["channel"]: row for row in _table("channel-budget/channel_terms.csv")}
    field = {channel for channel, row in terms.items() if row["field_channel"] == "yes"}
    assert field == {"webinars", "events", "abm"} and {c for c, r in terms.items() if r["licence"] == "yes"} == set(licences)
    cells = {(row["channel"], row["region"], row["month"]): {"max": int(row["max_blocks"]),
                                                              "committed": int(row["committed_blocks"]), "leads": []}
             for row in _table("channel-budget/cell_limits.csv")}
    for row in _table("channel-budget/forecasts.csv"):
        cells[(row["channel"], row["region"], row["month"])]["leads"].append(int(row["added_leads"]))
    before = {}
    for row in _table("channel-budget/syndication_vendor_forecast.csv"):
        key = ("syndication", row["region"], row["month"])
        cells[key]["leads"].append(int(row["cumulative_leads"]) - before.get(key, 0))
        before[key] = int(row["cumulative_leads"])
    assert all(len(cell["leads"]) == cell["max"] for cell in cells.values())
    return {"budget": 1_400_000, "regions": regions, "field": field, "licences": licences, "cells": cells}


def _budget_live(blocks: dict, world: dict) -> dict[str, list[str]]:
    return {channel: [month for month in B_MONTHS if any(n for (c, _r, m), n in blocks.items() if c == channel and m == month)]
            for channel in world["licences"]}


def _budget_numbers(blocks: dict, world: dict, licences: dict | None = None) -> dict:
    licences = licences or world["licences"]
    cells = world["cells"]
    leads = {key: sum(cells[key]["leads"][:count]) for key, count in blocks.items()}
    live = _budget_live(blocks, world)
    fees = {channel: licences[channel](len(months)) for channel, months in live.items()}
    cost = BLOCK * sum(blocks.values()) + sum(fees.values())
    total = sum(leads.values())
    return {"cost": cost, "leads": total, "per_lead": round(cost / total, 2), "live": live, "fees": fees,
            "regions": {region: sum(v for k, v in leads.items() if k[1] == region) for region in B_REGIONS},
            "field": sum(v for k, v in leads.items() if k[0] in world["field"])}


def _budget_breaks(blocks: dict, world: dict) -> list[str]:
    """Every rule of the brief a split breaks, by name."""
    cells, regions = world["cells"], world["regions"]
    broken = [f"cell {key}" for key, n in blocks.items() if not cells[key]["committed"] <= n <= cells[key]["max"]]
    if _budget_numbers(blocks, world)["cost"] > world["budget"]:
        broken.append("budget")
    for region, limit in regions.items():
        mine = {key: n for key, n in blocks.items() if key[1] == region}
        if not limit["min"] <= sum(mine.values()) <= limit["max"]:
            broken.append(f"{region} total")
        for month in B_MONTHS:
            if sum(n for key, n in mine.items() if key[2] == month) > limit["month"]:
                broken.append(f"{region} {month} pacing")
            if sum(n for key, n in mine.items() if key[2] == month and key[0] in world["field"]) > limit["field"]:
                broken.append(f"{region} {month} field")
    return broken


def _top(weights: list[int], forced: list[int]) -> dict[int, tuple[int, int]]:
    """The best total of exactly b blocks from a pool with only cell limits, and the number of ways."""
    rest = sorted(weights, reverse=True)
    out, total = {len(forced): (sum(forced), 1)}, sum(forced)
    for index, weight in enumerate(rest):
        total += weight
        ways = sum(1 for other in rest if other == weight)
        chosen = sum(1 for other in rest[:index + 1] if other == weight)
        out[len(forced) + index + 1] = (total, math.comb(ways, chosen))
    return out


def _combine(left: dict, right: dict, cap: int | None = None) -> dict:
    out: dict[int, tuple[int, int]] = {}
    for a, (va, wa) in left.items():
        for b, (vb, wb) in right.items():
            if cap is not None and a + b > cap:
                continue
            value, ways = va + vb, wa * wb
            if a + b not in out or value > out[a + b][0]:
                out[a + b] = (value, ways)
            elif value == out[a + b][0]:
                out[a + b] = (value, out[a + b][1] + ways)
    return out


def _budget_exact(world: dict, live: dict, *, field_capacity: bool = True) -> tuple[int, int]:
    """The most leads any split with these live months can project, and how many splits do.

    Exact by decomposition, with no greedy step: within one region and month, the field
    blocks and the other blocks are each a pool limited only by their cells, whose best b
    blocks are its b largest; the month combines the two pools under its pacing and field
    limits, the region combines its months under its maximum and minimum, and the quarter
    combines the regions under the budget left after the licences."""
    fees = sum(world["licences"][channel](len(months)) for channel, months in live.items())
    blocks = (world["budget"] - fees) // BLOCK
    totals = None
    for region, limit in world["regions"].items():
        quarter = {0: (0, 1)}
        for month in B_MONTHS:
            pools = {}
            for group in (True, False):
                weights, forced = [], []
                for (channel, r, m), cell in world["cells"].items():
                    if r == region and m == month and (channel in world["field"]) == group \
                            and (channel not in live or month in live[channel]):
                        forced += cell["leads"][:cell["committed"]]
                        weights += cell["leads"][cell["committed"]:]
                pool = _top(weights, forced)
                if group and field_capacity:
                    pool = {n: value for n, value in pool.items() if n <= limit["field"]}
                pools[group] = pool
            quarter = _combine(quarter, _combine(pools[True], pools[False], limit["month"]), limit["max"])
        quarter = {n: value for n, value in quarter.items() if n >= limit["min"]}
        totals = quarter if totals is None else _combine(totals, quarter, blocks)
    best = max(value for value, _ways in totals.values())
    return best, sum(ways for value, ways in totals.values() if value == best)


def _budget_patterns(world: dict):
    for flags in itertools.product(*(list(itertools.product((False, True), repeat=3)) for _ in world["licences"])):
        yield {channel: [month for month, on in zip(B_MONTHS, flag) if on] for channel, flag in zip(world["licences"], flags)}


def test_budget_oracle_is_the_one_best_split_by_an_exact_search():
    world = _budget_world()
    reference = task_facts_strategy.budget_reference()
    blocks = reference["blocks"]
    numbers = _budget_numbers(blocks, world)
    assert _budget_breaks(blocks, world) == []
    assert (sum(blocks.values()), sum(1 for n in blocks.values() if n)) == (137, 68)
    live = _budget_live(blocks, world)
    assert live == {"webinars": ["apr", "may"], "abm": ["may", "jun"], "podcasts": ["apr", "may"]} == reference["live"]
    # Exactly one split reaches the most leads for these live months, and it is the oracle's.
    assert _budget_exact(world, live) == (numbers["leads"], 1)
    # No other choice of live months comes close; the cheapest pattern with that value is this one.
    by_pattern = sorted(((_budget_exact(world, pattern)[0], pattern) for pattern in _budget_patterns(world)),
                        key=lambda item: -item[0])
    assert by_pattern[0] == (numbers["leads"], live) and by_pattern[0][0] - by_pattern[1][0] >= 50
    uncapped = max(_budget_exact(world, pattern, field_capacity=False)[0] for pattern in _budget_patterns(world))
    assert uncapped == 34_707
    assert _near(BUDGET) == {
        "a1_total_cost": numbers["cost"], "a2_total_leads": numbers["leads"], "a3_cost_per_lead": numbers["per_lead"],
        "a4_na_leads": numbers["regions"]["na"], "a5_emea_leads": numbers["regions"]["emea"],
        "a6_apac_leads": numbers["regions"]["apac"], "a7_field_leads": numbers["field"],
        "a8_field_capacity_cost": uncapped - numbers["leads"],
        "best_split": 0,
    }
    assert (numbers["cost"], numbers["leads"], numbers["fees"]) == (
        1_398_400, 33_728, {"webinars": 6_400, "abm": 13_000, "podcasts": 9_000})
    # Binding, from the brief's definitions applied by hand to the best split.
    binding = {"budget": world["budget"] - numbers["cost"] < BLOCK}
    for region, limit in world["regions"].items():
        spend = sum(n for key, n in blocks.items() if key[1] == region)
        binding[f"{region}_min"], binding[f"{region}_max"] = spend == limit["min"], spend == limit["max"]
        for month in B_MONTHS:
            binding[f"pacing_{region}_{month}"] = sum(
                n for key, n in blocks.items() if key[1:] == (region, month)) == limit["month"]
            binding[f"field_{region}_{month}"] = sum(
                n for key, n in blocks.items() if key[1:] == (region, month) and key[0] in world["field"]) == limit["field"]
    assert reference["binding"] == {name: "yes" if value else "no" for name, value in binding.items()}
    said = sorted(name for name, value in binding.items() if value)
    assert said == sorted(["budget", "na_max", "apac_min", "pacing_na_apr", "pacing_na_may", "pacing_na_jun",
                           "pacing_apac_may"] + [f"field_{r}_{m}" for r in B_REGIONS for m in B_MONTHS
                                                 if (r, m) != ("emea", "apr")])
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(_task(BUDGET)).items()}
    assert "(137 blocks across 68 cells)" in wording["best_split"]
    assert "the best split without the limits on field blocks (34,707 leads)" in wording["a8_field_capacity_cost"]
    assert "every field_<region>_<month> except field_emea_apr" in wording["binding_named"]
    sizes = sum(path.stat().st_size for path in (FIXTURES / "channel-budget").iterdir())
    assert 30_000 < sizes < 60_000 and sum(len(cell["leads"]) for cell in world["cells"].values()) == 416


def test_budget_the_oracles_procedure_is_optimal_on_every_small_instance_tried():
    """Why taking blocks by most added leads is exact here: for a fixed set of live months,
    the limits (budget, region maximum, region-month pacing, region-month field blocks, cell
    maximum) are caps on a nested family of sets of blocks, and a cell's blocks add ever
    fewer leads. Blocks under nested caps form a laminar matroid, on which the greedy choice
    of the heaviest blocks is optimal; committed blocks contract the matroid, and a region
    minimum is met first by the region's own heaviest blocks, which is the best way to meet
    it because the regions meet only in the budget. The licence months are not concave, so
    the oracle tries all of them. Here that claim is checked against brute force on small
    random instances of the same shape."""
    rng = random.Random(7)
    months = ["m1", "m2"]
    for _trial in range(40):
        regions = {"r1": None, "r2": None}
        cells = {}
        for channel in ("c1", "c2", "c3"):
            for region in regions:
                for month in months:
                    most = rng.randint(0, 2)
                    leads = sorted(rng.sample(range(5, 60), most), reverse=True)
                    cells[(channel, region, month)] = {"max": most, "committed": 0, "leads": leads}
        cells[("c1", "r1", "m1")]["committed"] = min(1, cells[("c1", "r1", "m1")]["max"])
        limits = {region: {"min": BLOCK * rng.randint(0, 2), "max": BLOCK * rng.randint(2, 5),
                           "month": BLOCK * rng.randint(1, 3), "field": rng.randint(0, 2)} for region in regions}
        inputs = {"budget": BLOCK * rng.randint(3, 7) + rng.choice([0, 3_000, 6_000]), "block": BLOCK,
                  "regions": limits, "months": months, "field": {"c2"},
                  "licences": {"c3": lambda live_months: 4_000 * live_months}, "cells": cells}
        keys = list(cells)
        best = None
        for counts in itertools.product(*(range(cells[key]["max"] + 1) for key in keys)):
            split = dict(zip(keys, counts))
            if any(split[key] < cells[key]["committed"] for key in keys):
                continue
            live = [m for m in months if any(split[("c3", r, m)] for r in regions)]
            cost = BLOCK * sum(counts) + 4_000 * len(live)
            ok = cost <= inputs["budget"]
            for region, limit in limits.items():
                mine = [(key, n) for key, n in split.items() if key[1] == region]
                ok = ok and limit["min"] <= BLOCK * sum(n for _k, n in mine) <= limit["max"]
                for month in months:
                    ok = ok and BLOCK * sum(n for key, n in mine if key[2] == month) <= limit["month"]
                    ok = ok and sum(n for key, n in mine if key[2] == month and key[0] == "c2") <= limit["field"]
            if ok:
                rank = (sum(sum(cells[key]["leads"][:n]) for key, n in split.items()), -cost)
                best = rank if best is None or rank > best else best
        if best is None:
            continue
        solved = task_facts_strategy.budget_solve(inputs)
        assert (solved["leads"], -solved["cost"]) == best


def test_budget_each_rule_moves_the_best_split():
    """Read any rule wrongly and the best split changes in at least four cells."""
    inputs = task_facts_strategy.budget_inputs()
    reference = task_facts_strategy.budget_reference()["blocks"]

    def moved(changed: dict, **options) -> int:
        solved = task_facts_strategy.budget_solve(changed, **options)["blocks"]
        return sum(solved[key] != reference[key] for key in reference)

    import copy
    assert moved(inputs, field_capacity=False) >= 30
    no_minimum = copy.deepcopy(inputs)
    for limit in no_minimum["regions"].values():
        limit["min"] = 0
    assert moved(no_minimum) >= 20
    no_pacing = copy.deepcopy(inputs)
    for limit in no_pacing["regions"].values():
        limit["month"] = 10**9
    assert moved(no_pacing) >= 4
    for channel, misread in (("abm", lambda months: 8_000 * months), ("podcasts", lambda months: 7_000 * months)):
        assert moved({**inputs, "licences": {**inputs["licences"], channel: misread}}) >= 4, channel
    assert moved({**inputs, "licences": {channel: (lambda months: 0) for channel in inputs["licences"]}}) >= 10


def _budget_reply(blocks: dict, *, lead_table: dict | None = None, fees: dict | None = None,
                  binding: dict | None = None, answers: list | None = None) -> str:
    """A reply built from a split, its rows computed from a table of leads (the right one unless given)."""
    world = _budget_world()
    table = lead_table or {key: cell["leads"] for key, cell in world["cells"].items()}
    lines = ["Recommendation for Ines.", "", "### allocation.csv", "```csv", "channel,region,month,blocks,media_spend_usd,leads"]
    for (channel, region, month), count in blocks.items():
        lines.append(f"{channel},{region},{month},{count},{BLOCK * count},{sum(table[(channel, region, month)][:count])}")
    live = _budget_live(blocks, world)
    fees = fees or {channel: world["licences"][channel](len(months)) for channel, months in live.items()}
    lines += ["```", "", "### fees.csv", "```csv", "channel,live_months,fee_usd"]
    lines += [f"{channel},{' '.join(live[channel]) or 'none'},{fees[channel]}" for channel in world["licences"]]
    lines += ["```", "", "### constraints.csv", "```csv", "constraint,binds"]
    lines += [f"{name},{value}" for name, value in (binding or {}).items()]
    lines += ["```", ""] + [f"A{index}: {value}" for index, value in enumerate(answers or [], 1)]
    return "\n".join(lines) + "\n"


def _budget_reference_reply() -> str:
    reference = task_facts_strategy.budget_reference()
    numbers = _budget_numbers(reference["blocks"], _budget_world())
    return _budget_reply(reference["blocks"], binding=reference["binding"], answers=[
        f"${numbers['cost']:,}", f"{numbers['leads']:,}", f"${numbers['per_lead']:.2f}", numbers["regions"]["na"],
        numbers["regions"]["emea"], numbers["regions"]["apac"], numbers["field"], 979])


def test_budget_reference_reply_passes_every_programmatic_check():
    reply = _budget_reference_reply()
    results = _results(BUDGET, reply)
    assert len(results) == 16 and not _failed(results)
    table = re.sub(r"```csv\n(.*?)\n```", lambda m: "\n".join(
        "| " + " | ".join(line.split(",")) + " |" + ("\n|" + "---|" * len(line.split(",")) if i == 0 else "")
        for i, line in enumerate(m.group(1).splitlines())), reply, flags=re.DOTALL)
    for variant in (table, reply.replace("```csv\n", "").replace("```\n", "\n"),
                    reply.replace(",apac,", ",APAC,").replace("budget,yes", "Budget,Yes"),
                    reply.replace("abm,may jun,", "abm,\"may, jun\",").replace("$1,398,400", "1398400")):
        assert not _failed(_results(BUDGET, variant)), variant[:300]


def test_budget_ignoring_the_field_capacity_scores_zero_where_it_should():
    """The tempting reading: buy the best blocks wherever they are, as if each region's field
    team could run any number of webinars, events and mailings."""
    world = _budget_world()
    inputs = task_facts_strategy.budget_inputs()
    blocks = task_facts_strategy.budget_solve(inputs, field_capacity=False)["blocks"]
    numbers = _budget_numbers(blocks, world)
    assert numbers["leads"] == 34_707 and any("field" in rule for rule in _budget_breaks(blocks, world))
    reply = _budget_reply(blocks, binding=task_facts_strategy.budget_binding(blocks), answers=[
        numbers["cost"], numbers["leads"], f"{numbers['per_lead']:.2f}", numbers["regions"]["na"],
        numbers["regions"]["emea"], numbers["regions"]["apac"], numbers["field"], 0])
    results = _results(BUDGET, reply)
    assert _zeroed(results) == _failed(results) == {
        "split_keeps_every_rule", "best_split", "a1_total_cost", "a2_total_leads", "a3_cost_per_lead", "a4_na_leads",
        "a5_emea_leads", "a6_apac_leads", "a7_field_leads", "a8_field_capacity_cost", "binding_named"}


@pytest.mark.parametrize("reading", ["no_minimum", "no_pacing", "abm_per_month", "podcast_setup_monthly", "no_licences"])
def test_budget_each_wrong_reading_of_a_rule_scores_zero_where_it_should(reading):
    import copy
    world = _budget_world()
    inputs = copy.deepcopy(task_facts_strategy.budget_inputs())
    believed = dict(world["licences"])
    if reading == "no_minimum":
        for limit in inputs["regions"].values():
            limit["min"] = 0
    elif reading == "no_pacing":
        for limit in inputs["regions"].values():
            limit["month"] = 10**9
    else:
        misread = {"abm_per_month": {"abm": lambda months: 8_000 * months},
                   "podcast_setup_monthly": {"podcasts": lambda months: 7_000 * months},
                   "no_licences": {channel: (lambda months: 0) for channel in believed}}[reading]
        believed.update(misread)
        inputs["licences"] = {**inputs["licences"], **misread}
    blocks = task_facts_strategy.budget_solve(inputs)["blocks"]
    numbers = _budget_numbers(blocks, world, believed)            # the figures as that reading believes them
    fees = {channel: believed[channel](len(months)) for channel, months in numbers["live"].items()}
    reply = _budget_reply(blocks, fees=fees, binding=task_facts_strategy.budget_binding(blocks), answers=[
        numbers["cost"], numbers["leads"], f"{numbers['per_lead']:.2f}", numbers["regions"]["na"],
        numbers["regions"]["emea"], numbers["regions"]["apac"], numbers["field"], 979])
    results = _results(BUDGET, reply)
    touched = {"best_split", "a2_total_leads", "a3_cost_per_lead"}
    touched |= {name for name, region in (("a4_na_leads", "na"), ("a5_emea_leads", "emea"), ("a6_apac_leads", "apac"))
                if numbers["regions"][region] != _near(BUDGET)[name]}
    if numbers["cost"] != 1_398_400:
        touched.add("a1_total_cost")
    if numbers["field"] != 8_301:
        touched.add("a7_field_leads")
    if reading in ("no_minimum", "no_pacing"):
        touched.add("split_keeps_every_rule")
    if reading not in ("no_minimum", "no_pacing"):
        touched.add("licences_right")
    assert touched <= _zeroed(results), reading
    assert results["rows_add_up"]["pass"]                        # its rows are honest arithmetic


def test_budget_the_vendors_cumulative_figures_read_as_added_leads_score_zero_where_they_should():
    reference = task_facts_strategy.budget_reference()
    world = _budget_world()
    misread = {key: ([sum(cell["leads"][:i + 1]) for i in range(len(cell["leads"]))] if key[0] == "syndication"
                     else cell["leads"]) for key, cell in world["cells"].items()}
    blocks = reference["blocks"]
    leads = {key: sum(misread[key][:n]) for key, n in blocks.items()}
    regions = {region: sum(v for k, v in leads.items() if k[1] == region) for region in B_REGIONS}
    total = sum(leads.values())
    reply = _budget_reply(blocks, lead_table=misread, binding=reference["binding"], answers=[
        1_398_400, total, f"{1_398_400 / total:.2f}", regions["na"], regions["emea"], regions["apac"], 8_301, 979])
    results = _results(BUDGET, reply)
    assert _failed(results) == _zeroed(results) == {
        "rows_add_up", "a2_total_leads", "a3_cost_per_lead", "a4_na_leads", "a5_emea_leads", "a6_apac_leads"}


def test_budget_missing_rows_and_files_are_counted_not_excused():
    reply = _budget_reference_reply()
    no_row = "\n".join(line for line in reply.splitlines() if not line.startswith("search,na,apr,")) + "\n"
    assert {"every_cell_once", "best_split", "rows_add_up", "split_keeps_every_rule"} <= _failed(_results(BUDGET, no_row))
    no_fees = re.sub(r"### fees\.csv\n```csv\n.*?```\n", "", reply, flags=re.DOTALL)
    assert _failed(_results(BUDGET, no_fees)) == {"three_files", "licences_right"}
    wrong_fee = reply.replace("abm,may jun,13000", "abm,may jun,16000")
    assert _failed(_results(BUDGET, wrong_fee)) == {"licences_right"}
    flipped = reply.replace("field_emea_apr,no", "field_emea_apr,yes")
    assert _failed(_results(BUDGET, flipped)) == {"binding_named"}


# ───────────────────────────────────────────────────────── competitor-comparison

COMPARISON = "competitor-comparison"
COLUMNS = ["free_plan", "trial_days", "entry_plan", "entry_price_usd", "entry_min_users", "sso_on_entry",
           "sso_cheapest_plan", "invoicing_on_entry", "api_on_entry", "top_plan_price_usd", "uptime_sla_percent",
           "eu_hosting"]
NS = "not stated"
# The table the brief defines, written out by hand from the six pages.
COMPARISON_TABLE = {
    "Tallyhour": ["yes", 21, "Studio", 21.00, 1, "yes", "Studio", "yes", "yes", 34.00, 99.9, "yes"],
    "Brisktime": [NS, 7, "Starter", 23.00, 3, "no", "Business", "yes", "no", 35.00, 99.5, "no"],
    "Quillhour": ["no", 14, "Team", 23.00, 3, "no", "Enterprise", "yes", "yes", NS, NS, "yes"],
    "Ticklog": ["no", 0, "Basic", 24.00, 5, "no", "Enterprise", "no", "yes", 45.00, 99.95, NS],
    "Fenwork": ["no", 30, "Essentials", 22.00, NS, "no", "Growth", "yes", "yes", 39.00, 99.9, "yes"],
    "Larchpoint": ["no", 14, "Core", 29.00, 1, "no", "Scale", "yes", NS, 48.00, 99.9, "no"],
}


def _page_text(company: str) -> str:
    return (FIXTURES / f"competitor-comparison/{company.lower()}.md").read_text()


def _claims(table: dict) -> dict[int, str]:
    """The five draft claims, judged from a table by the brief's verdict rules."""
    rows = {company: dict(zip(COLUMNS, values)) for company, values in table.items()}
    ours, theirs = rows["Tallyhour"], [row for company, row in rows.items() if company != "Tallyhour"]

    def below(column: str) -> bool:
        # A price written as words ("contact sales") reads, to a careless reader, as dearer than any number.
        def amount(value):
            return float("inf") if isinstance(value, str) else value
        return all(row[column] != NS for row in theirs) and all(ours[column] < amount(row[column]) for row in theirs)

    held = {
        1: below("entry_price_usd"),
        2: ours["free_plan"] == "yes" and all(row["free_plan"] == "no" for row in theirs),
        3: all(row["trial_days"] != NS for row in theirs) and all(ours["trial_days"] > row["trial_days"] for row in theirs),
        4: ours["sso_on_entry"] == "yes" and all(row["sso_on_entry"] == "no" for row in theirs),
        5: below("top_plan_price_usd"),
    }
    return {number: "supportable" if holds else "not supportable" for number, holds in held.items()}


def _comparison_reply(table: dict, verdicts: dict | None = None, *, reasons: bool = True) -> str:
    verdicts = verdicts or _claims(table)
    lines = ["Comparison of Tallyhour and five competitors, from the saved pages.", "", "### comparison.csv", "```csv",
             "company," + ",".join(COLUMNS)]
    for company, values in table.items():
        cells = [f"{value:.2f}" if isinstance(value, float) and value < 90 else str(value) for value in values]
        lines.append(",".join([company] + cells))
    lines += ["```", "", "### claims.csv", "```csv", "claim,verdict"]
    lines += [f"{number},{verdict}" for number, verdict in verdicts.items()]
    lines += ["```", ""]
    if reasons:
        lines += ["Claim 2: Brisktime's free_plan is not stated.", "Claim 3: Fenwork's trial_days is 30.",
                  "Claim 5: Quillhour's top_plan_price_usd is not stated."]
    return "\n".join(lines) + "\n"


def _with(table: dict, company: str, column: str, value) -> dict:
    changed = {name: list(values) for name, values in table.items()}
    changed[company][COLUMNS.index(column)] = value
    return changed


def test_comparison_oracle_reads_the_table_the_pages_state():
    reference = task_facts_strategy.comparison_reference()
    names = {"tallyhour": "Tallyhour", "brisktime": "Brisktime", "quillhour": "Quillhour", "ticklog": "Ticklog",
             "fenwork": "Fenwork", "larchpoint": "Larchpoint"}
    assert {names[company]: [row[column] for column in COLUMNS] for company, row in reference["table"].items()} \
        == COMPARISON_TABLE
    assert reference["claims"] == _claims(COMPARISON_TABLE) == {
        1: "supportable", 2: "not supportable", 3: "not supportable", 4: "supportable", 5: "not supportable"}
    assert {group: len(cells) for group, cells in reference["groups"].items()} == {
        "faq": 3, "not_stated": 6, "prices": 11, "tiers": 22, "other": 30}
    assert sorted(reference["groups"]["not_stated"]) == sorted(
        (company.lower(), column) for company, values in COMPARISON_TABLE.items()
        for column, value in zip(COLUMNS, values) if value == NS)


def test_comparison_every_trap_is_in_the_pages_as_described():
    """Each look-alike the checks name is there, so a careful reader can see it
    and a careless one is led past it."""
    pages = {company: _page_text(company) for company in COMPARISON_TABLE}
    brief = (FIXTURES / "competitor-comparison/comparison_brief.md").read_text()
    # Monthly basis: a monthly price beside a lower annual one, and annual-only plans.
    assert "| Billed annually, per user per month | $19 |" in pages["Quillhour"]
    assert "| Billed monthly, per user per month | $23 |" in pages["Quillhour"]
    assert "| Price per user per year | $276 | $420 |" in pages["Brisktime"] and "| Billing | Annual only | Annual only |" in pages["Brisktime"]
    assert (276 / 12, 420 / 12) == (23.0, 35.0)
    assert "| Per user per year, billed yearly | $290 | $480 |" in pages["Larchpoint"] and round(290 / 12, 2) == 24.17
    # A feature in a page's introduction that its table puts on a higher plan only.
    assert "single sign-on, SCIM provisioning and audit logs" in pages["Brisktime"]
    assert "| Single sign-on (SAML) and SCIM | — | ✓ |" in pages["Brisktime"]
    assert "| Invoicing from timesheets | — | ✓ | ✓ |" in pages["Ticklog"]
    # FAQ against table, three times.
    assert "| Free trial | 14 days | 14 days | 14 days |" in pages["Fenwork"] and "30-day free trial" in pages["Fenwork"]
    assert "| REST API | — | ✓ | ✓ |" in pages["Ticklog"] and "every Ticklog plan includes the REST API" in pages["Ticklog"]
    assert "| Minimum users | 2 | 2 | 25 |" in pages["Quillhour"] and "now start at 3 users" in pages["Quillhour"]
    assert "the FAQ is right" in brief
    # Not stated: never said, a price withheld, a status page that is not an SLA.
    assert not re.search(r"free plan|free forever|free tier|\$0", pages["Brisktime"], re.I)
    assert "Try either plan free for 7 days" in pages["Brisktime"]                 # a trial, not a free plan
    assert "| Contact sales |" in pages["Quillhour"] and "Contact sales" in brief
    assert "status page" in pages["Quillhour"] and not re.search(r"\bSLA\b", pages["Quillhour"])
    assert not re.search(r"\bEU\b|hosting|hosted|region|residency", pages["Ticklog"])
    assert not re.search(r"minimum|seats|at least|\d+ users|from \d", pages["Fenwork"], re.I)
    assert not re.search(r"\bAPI\b", pages["Larchpoint"])
    # Look-alike numbers next to the real ones.
    assert "30-day money-back guarantee" in pages["Larchpoint"] and "14-day free trial" in pages["Larchpoint"]
    assert "30-minute demo" in pages["Ticklog"] and "no free plan and no free trial" in pages["Ticklog"]
    assert "| Uptime SLA | 99.5% | 99.9% |" in pages["Larchpoint"]
    # The claims the brief lists are the ones the checks speak of.
    assert brief.count("Tallyhour") >= 6 and "a `not stated` cell cannot support it" in brief
    sizes = sum(path.stat().st_size for path in (FIXTURES / "competitor-comparison").iterdir())
    assert sizes < 60_000


def test_comparison_reference_reply_passes_every_programmatic_check():
    reply = _comparison_reply(COMPARISON_TABLE)
    results = _results(COMPARISON, reply)
    assert len(results) == 13 and not _failed(results)
    # Written other ways a model writes them, it reads the same.
    variants = [
        reply.replace("Larchpoint,", "Larchpoint Time,").replace(",Business,", ",Brisktime Business,"),
        reply.replace("not stated", "Not stated").replace(",Growth,", ",Growth plan,"),
        reply.replace(",21.00,", ",$21.00,").replace(",99.95,", ",99.95%,").replace(",yes,", ",Yes,"),
        reply.replace("not supportable", "Not supportable"),
    ]
    table = re.sub(r"```csv\n(.*?)\n```", lambda m: "\n".join(
        "| " + " | ".join(line.split(",")) + " |" + ("\n|" + "---|" * len(line.split(",")) if i == 0 else "")
        for i, line in enumerate(m.group(1).splitlines())), reply, flags=re.DOTALL)
    for variant in variants + [table]:
        assert not _failed(_results(COMPARISON, variant)), variant[:200]


def test_comparison_the_careless_reading_scores_zero_on_every_check_it_touches():
    """Read the way a hurried researcher reads: the price in large type
    (annual billing), a feature in the introduction taken for every plan, the
    table over the FAQ, a gap in a page read as a no, and "Contact sales" left
    as written. Every trap group and every claim scores zero; the cells with
    no trap in them still pass."""
    careless = COMPARISON_TABLE
    for company, column, value in (
        ("Quillhour", "entry_price_usd", 19.00),
        ("Brisktime", "sso_on_entry", "yes"), ("Brisktime", "sso_cheapest_plan", "Starter"),
        ("Fenwork", "trial_days", 14), ("Ticklog", "api_on_entry", "no"), ("Quillhour", "entry_min_users", 2),
        ("Brisktime", "free_plan", "no"), ("Quillhour", "top_plan_price_usd", "Contact sales"),
        ("Quillhour", "uptime_sla_percent", "no"), ("Ticklog", "eu_hosting", "no"),
        ("Fenwork", "entry_min_users", 1), ("Larchpoint", "api_on_entry", "no"),
    ):
        careless = _with(careless, company, column, value)
    verdicts = {1: "not supportable", 2: "supportable", 3: "supportable", 4: "not supportable", 5: "supportable"}
    results = _results(COMPARISON, _comparison_reply(careless, verdicts))
    assert _zeroed(results) == _failed(results) == {
        "prices_on_a_monthly_basis", "features_read_per_plan", "faq_beats_the_table", "not_stated_kept",
        "claim_1_verdict", "claim_2_verdict", "claim_3_verdict", "claim_4_verdict", "claim_5_verdict"}


@pytest.mark.parametrize("company,column,value,group,claim", [
    ("Quillhour", "entry_price_usd", 19.00, "prices_on_a_monthly_basis", 1),     # the annual-billing price
    ("Larchpoint", "entry_price_usd", 24.17, "prices_on_a_monthly_basis", None),  # a twelfth of the yearly price
    ("Brisktime", "top_plan_price_usd", 420.00, "prices_on_a_monthly_basis", None),
    ("Brisktime", "free_plan", "no", "not_stated_kept", 2),                      # a gap read as a no
    ("Fenwork", "trial_days", 14, "faq_beats_the_table", 3),                      # the table over the FAQ
    ("Brisktime", "sso_on_entry", "yes", "features_read_per_plan", 4),            # the introduction's list
    ("Quillhour", "top_plan_price_usd", "contact sales", "not_stated_kept", 5),
    ("Larchpoint", "trial_days", 30, "other_cells_right", None),                 # the money-back guarantee
    ("Larchpoint", "uptime_sla_percent", 99.5, "other_cells_right", None),       # the entry plan's SLA, not the highest
])
def test_comparison_each_trap_costs_its_own_check_and_its_own_claim(company, column, value, group, claim):
    table = _with(COMPARISON_TABLE, company, column, value)
    verdicts = _claims(table)
    expected = {group} | ({f"claim_{claim}_verdict"} if claim else set())
    assert {number for number, verdict in verdicts.items() if verdict != _claims(COMPARISON_TABLE)[number]} == (
        {claim} if claim else set())
    results = _results(COMPARISON, _comparison_reply(table, verdicts))
    assert _failed(results) == _zeroed(results) == expected


def test_comparison_a_missing_file_or_row_is_counted_not_excused():
    reply = _comparison_reply(COMPARISON_TABLE)
    no_fenwork = "\n".join(line for line in reply.splitlines() if not line.startswith("Fenwork,")) + "\n"
    failed = _failed(_results(COMPARISON, no_fenwork))
    assert {"six_companies_twelve_columns", "faq_beats_the_table", "not_stated_kept", "prices_on_a_monthly_basis",
            "features_read_per_plan", "other_cells_right"} == failed
    no_claims = reply.split("### claims.csv")[0]
    assert {"both_files", "five_claims_once", "claim_1_verdict", "claim_5_verdict"} <= _failed(_results(COMPARISON, no_claims))
    dropped_column = reply.replace(",eu_hosting\n", "\n")
    assert "six_companies_twelve_columns" in _failed(_results(COMPARISON, dropped_column))


# ─────────────────────────────────────────────────────────────── launch-timeline

TIMELINE = "launch-timeline"


def _launch_plan() -> tuple[dict, list, dt.date, dt.date]:
    """The tasks, the working days and the dates, read again from the fixtures."""
    brief = (FIXTURES / "launch-timeline/launch_brief.md").read_text()
    holidays = {dt.date.fromisoformat(day) for day in re.findall(r"(?m)^- (\d{4}-\d{2}-\d{2}) \(", brief)}
    assert holidays == {dt.date(2027, 3, 12), dt.date(2027, 3, 26), dt.date(2027, 3, 29)}
    assert "work starts on Monday 2027-03-01" in brief.replace("\n", " ")
    assert "the launch is on **2027-04-13**" in brief.replace("\n", " ")
    tasks = {row["task_id"]: {"owner": row["owner"], "days": int(row["duration_days"]), "deps": row["depends_on"].split(),
                              "optional": row["optional"] == "yes",
                              "not_before": dt.date.fromisoformat(row["not_before"]) if row["not_before"] else None}
             for row in _table("launch-timeline/launch_plan.csv")}
    calendar, day = [], dt.date(2027, 3, 1)
    while day < dt.date(2027, 12, 31):
        if day.weekday() < 5 and day not in holidays:
            calendar.append(day)
        day += dt.timedelta(days=1)
    return tasks, calendar, dt.date(2027, 3, 1), dt.date(2027, 4, 13)


def _simulate(tasks: dict, *, owners: bool = True, cut: frozenset = frozenset(), longer: dict | None = None) -> dict:
    """Walk the calendar a working day at a time and start each task on the first
    day the brief's rules let it: a different method from the oracle's."""
    _tasks, calendar, _start, _target = _launch_plan()
    longer = longer or {}

    def needs(task_id: str) -> set:
        out = set()
        for other in tasks[task_id]["deps"]:
            out |= needs(other) if other in cut else {other}
        return out

    kept = [task_id for task_id in sorted(tasks) if task_id not in cut]
    waits = {task_id: needs(task_id) for task_id in kept}
    if owners:
        for task_id in kept:
            earlier = [other for other in kept if other < task_id and tasks[other]["owner"] == tasks[task_id]["owner"]]
            if earlier:
                waits[task_id] = waits[task_id] | {max(earlier)}
    start, finish = {}, {}
    for number, day in enumerate(calendar):
        for task_id in kept:
            if task_id in start:
                continue
            nb = tasks[task_id]["not_before"]
            if nb and day < nb:
                continue
            if all(other in finish and finish[other] < number for other in waits[task_id]):
                start[task_id] = number
                finish[task_id] = number + tasks[task_id]["days"] + longer.get(task_id, 0) - 1
        if len(start) == len(kept):
            break
    return {task_id: (calendar[start[task_id]], calendar[finish[task_id]]) for task_id in kept}


def _slack(tasks: dict, task_id: str, *, owners: bool = True) -> int:
    """How many working days later the task can finish before the launch moves.
    The launch is measured by the day T24 ends, so T24 itself has none."""
    launch = _simulate(tasks, owners=owners)["T24"][1]
    days = 0
    while _simulate(tasks, owners=owners, longer={task_id: days + 1})["T24"][1] == launch:
        days += 1
    return days


def test_timeline_oracle_matches_a_day_by_day_simulation():
    tasks, calendar, _start, target = _launch_plan()
    schedule = _simulate(tasks)
    reference = task_facts_strategy.timeline_reference()
    assert {task_id: (reference["starts"][task_id], reference["finishes"][task_id]) for task_id in tasks} == schedule
    assert schedule["T24"][0] == reference["launch_date"] == dt.date(2027, 4, 16) > target
    slack = {task_id: _slack(tasks, task_id) for task_id in tasks}
    critical = sorted((task_id for task_id, value in slack.items() if value == 0), key=lambda t: schedule[t][0])
    assert critical == reference["critical_path"] == ["T02", "T04", "T05", "T07", "T08", "T17", "T19", "T22", "T23", "T24"]
    assert {task_id: slack[task_id] for task_id in ("T06", "T11", "T16")} == reference["slack"] == {
        "T06": 2, "T11": 1, "T16": 18}
    # The critical path is one chain: each task starts the working day after the one before it finishes.
    for earlier, later in zip(critical, critical[1:]):
        assert calendar.index(schedule[later][0]) == calendar.index(schedule[earlier][1]) + 1
    # Three of its links are the designer's queue, not a dependency.
    assert all(earlier not in tasks[later]["deps"] for earlier, later in (("T02", "T04"), ("T04", "T05"), ("T05", "T07")))
    # Every set of optional tasks, cut: one smallest set brings the launch to the target.
    optional = [task_id for task_id, task in tasks.items() if task["optional"]]
    assert optional == ["T05", "T13", "T16", "T21"]
    launches = {cut: _simulate(tasks, cut=frozenset(cut))["T24"][0]
                for size in range(len(optional) + 1) for cut in itertools.combinations(optional, size)}
    hits = sorted((len(cut), cut) for cut, launch in launches.items() if launch <= target)
    assert hits[0] == (2, ("T05", "T13")) and hits[1][0] == 3                    # the only pair; no single task
    assert launches[("T05",)] == dt.date(2027, 4, 14) and launches[("T16",)] == dt.date(2027, 4, 16)
    assert launches[("T05", "T13")] == reference["launch_date_after_cut"] == dt.date(2027, 4, 13)
    assert reference["cut"] == ["T05", "T13"] and reference["target_met"] == "no"


def test_timeline_the_traps_are_real():
    tasks, calendar, _start, target = _launch_plan()
    # Without the owners' one-task-at-a-time rule the plan looks as if it makes the date.
    loose = _simulate(tasks, owners=False)
    assert loose["T24"][0] == dt.date(2027, 4, 9) <= target
    assert sum(loose[task_id][0] != start for task_id, (start, _finish) in _simulate(tasks).items()) >= 10
    # The longest task and the longest optional task look critical and are not.
    longest = max(tasks, key=lambda task_id: tasks[task_id]["days"])
    assert longest == "T06" and _slack(tasks, "T06") == 2
    assert max((task for task in tasks if tasks[task]["optional"]), key=lambda t: tasks[t]["days"]) == "T16"
    # Both not_before dates bind, and every holiday falls inside a task that runs across it.
    schedule = _simulate(tasks)
    assert schedule["T02"][0] == dt.date(2027, 3, 9) > dt.date(2027, 3, 4)          # T01 ends on 03-03
    assert schedule["T15"][0] == dt.date(2027, 4, 8) and tasks["T15"]["not_before"] == dt.date(2027, 4, 5)
    for holiday in (dt.date(2027, 3, 12), dt.date(2027, 3, 26), dt.date(2027, 3, 29)):
        assert any(start < holiday < finish for start, finish in schedule.values()), holiday
    assert sum(path.stat().st_size for path in (FIXTURES / "launch-timeline").iterdir()) < 60_000


TIMELINE_REFERENCE_REPLY = """\
Mara, the plan as it stands launches on Friday 2027-04-16, three working days after the date you
gave the retail partners. The designer's queue drives it: Cleo cannot start the landing page design
until the photography, the packaging artwork and the retail lookbook are done, in that order.

### schedule.csv
```csv
task_id,start,finish
T01,2027-03-01,2027-03-03
T02,2027-03-09,2027-03-10
T03,2027-03-04,2027-03-09
T04,2027-03-11,2027-03-17
T05,2027-03-18,2027-03-22
T06,2027-03-18,2027-04-02
T07,2027-03-23,2027-03-25
T08,2027-03-30,2027-04-05
T09,2027-03-10,2027-03-15
T10,2027-03-16,2027-03-17
T11,2027-03-30,2027-04-02
T12,2027-03-04,2027-03-10
T13,2027-04-05,2027-04-07
T14,2027-03-16,2027-03-17
T15,2027-04-08,2027-04-12
T16,2027-03-10,2027-03-17
T17,2027-04-06,2027-04-08
T18,2027-04-09,2027-04-12
T19,2027-04-09,2027-04-12
T20,2027-03-18,2027-03-19
T21,2027-03-18,2027-03-19
T22,2027-04-13,2027-04-14
T23,2027-04-15,2027-04-15
T24,2027-04-16,2027-04-16
```

### answers.csv
```csv
item,answer
launch_date,2027-04-16
critical_path,T02 T04 T05 T07 T08 T17 T19 T22 T23 T24
slack_T06,2
slack_T11,1
slack_T16,18
target_met,no
cut,T05 T13
launch_date_after_cut,2027-04-13
```

Cutting the retail lookbook (T05) frees Cleo three days earlier and brings the launch to 04-14; the
seeding kits (T13) then hold Esme's press outreach back, so cutting them too brings it to 04-13. No
single cut does it, and no other pair: the retail partner deck (T16) has 18 days of slack.
"""


def _timeline_reply(schedule: dict, answers: dict) -> str:
    lines = ["Launch plan.", "", "### schedule.csv", "```csv", "task_id,start,finish"]
    lines += [f"{task_id},{start},{finish}" for task_id, (start, finish) in sorted(schedule.items())]
    lines += ["```", "", "### answers.csv", "```csv", "item,answer"]
    lines += [f"{item},{value}" for item, value in answers.items()]
    return "\n".join(lines + ["```", ""]) + "\n"


def test_timeline_reference_reply_passes_every_programmatic_check():
    results = _results(TIMELINE, TIMELINE_REFERENCE_REPLY)
    assert len(results) == 13 and not _failed(results)
    for variant in (
        TIMELINE_REFERENCE_REPLY.replace("T02 T04 T05 T07 T08 T17 T19 T22 T23 T24", '"T02, T04, T05, T07, T08, T17, T19, T22, T23, T24"'),
        TIMELINE_REFERENCE_REPLY.replace("cut,T05 T13", "cut,T13 T05").replace("target_met,no", "target_met,No"),
        TIMELINE_REFERENCE_REPLY.replace("```csv\n", "").replace("```\n", "\n"),
        TIMELINE_REFERENCE_REPLY.replace("slack_T06,2", "slack_T06,2 days"),
    ):
        assert not _failed(_results(TIMELINE, variant)), variant[-600:]


def test_timeline_scheduling_without_the_owner_rule_scores_zero_where_it_should():
    """The tempting reading: a dependency-only critical path, as if every owner
    could run tasks side by side. It says the date holds."""
    tasks, _calendar, _start, _target = _launch_plan()
    loose = _simulate(tasks, owners=False)
    slack = {task_id: _slack(tasks, task_id, owners=False) for task_id in tasks}
    critical = sorted((task_id for task_id, value in slack.items() if value == 0), key=lambda t: loose[t][0])
    careless = _timeline_reply(loose, {
        "launch_date": loose["T24"][0], "critical_path": " ".join(critical), "slack_T06": slack["T06"],
        "slack_T11": slack["T11"], "slack_T16": slack["T16"], "target_met": "yes", "cut": "none",
        "launch_date_after_cut": loose["T24"][0]})
    results = _results(TIMELINE, careless)
    # Its critical path is the press embargo alone, and every slack it gives is wrong.
    assert critical == ["T15", "T23", "T24"] and {task_id: slack[task_id] for task_id in ("T06", "T11", "T16")} == {
        "T06": 5, "T11": 6, "T16": 13}
    assert _zeroed(results) == _failed(results) == {
        "starts_follow_the_rules", "launch_date_right", "critical_path_right", "slack_t06_right", "slack_t11_right",
        "slack_t16_right", "target_missed_said", "smallest_cut", "launch_after_cut_right"}
    assert results["finishes_follow_the_calendar"]["pass"]       # its calendar arithmetic is sound


def test_timeline_other_wrong_readings_fail_their_own_checks():
    tasks, calendar, _start, _target = _launch_plan()
    # Holidays forgotten: the finishes no longer follow the calendar, and the starts slide.
    reply = TIMELINE_REFERENCE_REPLY.replace("T04,2027-03-11,2027-03-17", "T04,2027-03-11,2027-03-16")
    assert _failed(_results(TIMELINE, reply)) == {"finishes_follow_the_calendar"}
    # The obvious single cut, the longest optional task, or the first cut alone.
    for cut, after in (("T16", "2027-04-16"), ("T05", "2027-04-14"), ("T05 T13 T16", "2027-04-13")):
        reply = TIMELINE_REFERENCE_REPLY.replace("cut,T05 T13", f"cut,{cut}").replace(
            "launch_date_after_cut,2027-04-13", f"launch_date_after_cut,{after}")
        assert "smallest_cut" in _zeroed(_results(TIMELINE, reply)), cut
    # The critical path with the queue's links left out, as a dependency-only reading writes it.
    reply = TIMELINE_REFERENCE_REPLY.replace("T02 T04 T05 T07", "T02 T07")
    assert _failed(_results(TIMELINE, reply)) == {"critical_path_right"}
    # One start a day late costs the start check part of its credit, not all of it.
    reply = TIMELINE_REFERENCE_REPLY.replace("T21,2027-03-18,2027-03-19", "T21,2027-03-19,2027-03-22")
    results = _results(TIMELINE, reply)
    assert _failed(results) == {"starts_follow_the_rules"} and 0 < results["starts_follow_the_rules"]["score"] < 1
    # A missing row, a missing item, a missing file.
    assert {"every_task_once", "starts_follow_the_rules", "finishes_follow_the_calendar"} == _failed(
        _results(TIMELINE, TIMELINE_REFERENCE_REPLY.replace("T13,2027-04-05,2027-04-07\n", "")))
    assert {"every_item_answered", "slack_t11_right"} == _failed(
        _results(TIMELINE, TIMELINE_REFERENCE_REPLY.replace("slack_T11,1\n", "")))
    assert {"both_files", "every_item_answered", "launch_date_right", "smallest_cut"} <= _failed(
        _results(TIMELINE, TIMELINE_REFERENCE_REPLY.split("### answers.csv")[0]))
