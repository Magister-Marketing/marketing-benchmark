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
import re

import pytest

from eval_runner import bench, task_facts_strategy

FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"
STRATEGY_TASKS = ["channel-budget-allocation", "competitor-comparison", "launch-timeline"]


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
        assert task["split"] == "development" and (task["prompt_version"], task["rubric_version"]) == (1, 1)
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


def _budget_inputs() -> dict:
    """The rules, read again from the fixtures with code of this file's own."""
    brief = (FIXTURES / "channel-budget/planning_brief.md").read_text()
    channels = {}
    for row in _table("channel-budget/channel_terms.csv"):
        channels[row["channel"]] = {
            "max": int(row["max_blocks"]), "minimum": int(row["minimum_if_used_blocks"]),
            "committed": int(row["committed_blocks"]), "fee": 3 * int(row["fee_usd_per_month"]),
            "routed": row["routed_to_aes"] == "yes", "added": []}
    for row in _table("channel-budget/channel_forecasts.csv"):
        channels[row["channel"]]["added"].append(int(row["added_leads"]))
    assert "**Quarter budget:** $128,000" in brief and "whole blocks of $5,000" in brief
    assert "at most **520 new leads**" in brief and "pays three months\n  of its fee" in brief
    return {"budget": 128_000, "block": 5_000, "capacity": 520, "channels": channels}


def _budget_search(capacity: int | None, inputs: dict | None = None) -> list[tuple[int, int, dict]]:
    """Every split that keeps the rules, as (leads, cost, blocks), best first."""
    inputs = inputs or _budget_inputs()
    names = list(inputs["channels"])
    found = []

    def walk(index: int, blocks: dict, cost: int, leads: int, routed: int) -> None:
        if cost > inputs["budget"] or (capacity is not None and routed > capacity):
            return
        if index == len(names):
            found.append((leads, cost, dict(blocks)))
            return
        name = names[index]
        channel = inputs["channels"][name]
        for count in range(channel["max"] + 1):
            if count < channel["committed"] or 0 < count < channel["minimum"]:
                continue
            got = sum(channel["added"][:count])
            blocks[name] = count
            walk(index + 1, blocks, cost + count * inputs["block"] + (channel["fee"] if count else 0),
                 leads + got, routed + (got if channel["routed"] else 0))
        del blocks[name]

    walk(0, {}, 0, 0, 0)
    return sorted(found, key=lambda item: (-item[0], item[1]))


def _budget_figures(blocks: dict) -> dict:
    inputs = _budget_inputs()
    cost = leads = routed = 0
    for name, count in blocks.items():
        channel = inputs["channels"][name]
        got = sum(channel["added"][:count])
        cost += count * inputs["block"] + (channel["fee"] if count else 0)
        leads += got
        routed += got if channel["routed"] else 0
    return {"cost": cost, "leads": leads, "routed": routed}


def test_budget_oracle_matches_a_recomputation_from_the_fixtures():
    splits = _budget_search(520)
    (leads, cost, best), second = splits[0], splits[1]
    assert best == {"search": 10, "linkedin": 1, "webinars": 3, "syndication": 4, "review_sites": 2, "meta": 4}
    assert (leads, cost) == (2121, 124_200)
    assert leads - second[0] >= 5                               # one best split, not a near-tie on a rounding
    uncapped = _budget_search(None)
    assert uncapped[0][0] - uncapped[1][0] >= 4 and uncapped[0][0] == 2206
    routed = _budget_figures(best)["routed"]
    per_lead = round(cost / leads, 2)
    assert _near(BUDGET) == {
        "a1_total_cost": cost, "a2_total_leads": leads, "a3_cost_per_lead": per_lead,
        "a4_routed_leads": routed, "a5_capacity_cost": uncapped[0][0] - leads,
    } == {"a1_total_cost": 124_200, "a2_total_leads": 2121, "a3_cost_per_lead": 58.56,
          "a4_routed_leads": 475, "a5_capacity_cost": 85}
    # The oracle the checker uses says the same.
    reference = task_facts_strategy.budget_reference()
    assert reference["blocks"] == best
    assert reference["answers"] == {1: 124_200.0, 2: 2121.0, 3: 58.56, 4: 475.0, 5: 85.0}
    # Binding, from the brief's definitions applied by hand to the best split.
    inputs = _budget_inputs()
    ae = [name for name, channel in inputs["channels"].items() if channel["routed"]]
    assert all(routed + inputs["channels"][name]["added"][best[name]] > 520 for name in ae)
    assert 128_000 - cost == 3_800 < 5_000
    assert reference["binding"] == {
        "budget": "yes", "ae_capacity": "yes", "search_max": "yes", "linkedin_max": "no", "webinars_max": "no",
        "syndication_min_order": "yes", "syndication_max": "no", "review_sites_commitment": "yes",
        "review_sites_max": "no", "meta_max": "no"}
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(_task(BUDGET)).items()}
    assert "search 10, linkedin 1, webinars 3, syndication 4, review_sites 2, meta 4" in wording["best_split"]
    assert ("yes exactly for budget, ae_capacity, search_max, syndication_min_order and review_sites_commitment"
            in wording["binding_named"])
    assert "the best split without it (2,206 leads)" in wording["a5_capacity_cost"]


def test_budget_each_rule_changes_the_answer():
    """Every rule the brief states moves the best split when it is read wrongly,
    and the choices it forces (open webinars, open syndication) win clearly."""
    splits = _budget_search(520)
    best = splits[0]
    without_webinars = next(item for item in splits if item[2]["webinars"] == 0)
    without_syndication = next(item for item in splits if item[2]["syndication"] == 0)
    assert best[0] - without_webinars[0] >= 40 and best[0] - without_syndication[0] >= 100
    # The licence read as one month's fee frees a block: the best split changes.
    one_month = _budget_inputs()
    one_month["channels"]["webinars"]["fee"] = 1_400
    assert _budget_search(520, one_month)[0][2] == {**best[2], "meta": 5}
    # The commitment or the minimum order ignored: a split that looks better and breaks a rule.
    loose = _budget_inputs()
    loose["channels"]["review_sites"]["committed"] = 0
    assert _budget_search(520, loose)[0][0] > best[0]
    loose = _budget_inputs()
    loose["channels"]["syndication"]["minimum"] = 0
    assert _budget_search(520, loose)[0][0] > best[0]


BUDGET_REFERENCE_REPLY = """\
Ines, here is the split that projects the most leads under every rule in the brief.

Review sites take their 2 committed blocks. Search gets all 10 of its blocks: every one of them
adds more leads than the next-best use of the money. Webinars are worth their $4,200 licence for
the quarter: their first three blocks add 153, 124 and 97 leads. The account executives can take
520 leads, so the routed channels stop at 475 (webinars 374, LinkedIn 101): the next webinar block
(73) or LinkedIn block (91) would take them past 520. Syndication's 4-block minimum order is worth
buying (252 leads), and Meta takes 4 blocks. $3,800 is left, less than a block.

### allocation.csv
```csv
channel,blocks,media_spend_usd,fee_usd,leads
search,10,50000,0,952
linkedin,1,5000,0,101
webinars,3,15000,4200,374
syndication,4,20000,0,252
review_sites,2,10000,0,74
meta,4,20000,0,368
```

### constraints.csv
```csv
constraint,binds
budget,yes
ae_capacity,yes
search_max,yes
linkedin_max,no
webinars_max,no
syndication_min_order,yes
syndication_max,no
review_sites_commitment,yes
review_sites_max,no
meta_max,no
```

Without the AE capacity the best split would project 2,206 leads, so the capacity costs 85.

A1: $124,200
A2: 2,121
A3: $58.56
A4: 475
A5: 85
"""


def _budget_reply(blocks: dict, *, fee_months: int = 3, binding: dict | None = None, answers: list | None = None) -> str:
    """A reply built from a split, with its rows computed honestly from the tables."""
    inputs = _budget_inputs()
    lines = ["Recommendation.", "", "### allocation.csv", "```csv", "channel,blocks,media_spend_usd,fee_usd,leads"]
    for name, count in blocks.items():
        channel = inputs["channels"][name]
        fee = channel["fee"] // 3 * fee_months if count else 0
        lines.append(f"{name},{count},{count * 5000},{fee},{sum(channel['added'][:count])}")
    lines += ["```", "", "### constraints.csv", "```csv", "constraint,binds"]
    lines += [f"{name},{value}" for name, value in (binding or {}).items()]
    lines += ["```", ""]
    lines += [f"A{index}: {value}" for index, value in enumerate(answers or [], 1)]
    return "\n".join(lines) + "\n"


def test_budget_reference_reply_passes_every_programmatic_check():
    results = _results(BUDGET, BUDGET_REFERENCE_REPLY)
    assert len(results) == 13 and not _failed(results)
    facts = bench.measured_facts(_task(BUDGET), BUDGET_REFERENCE_REPLY)
    assert {key: value for key, value in facts.items() if key.startswith("budget_")} == {
        "budget_missing_file_count": 0, "budget_channel_row_error_count": 0, "budget_infeasible_count": 0,
        "budget_wrong_blocks_count": 0, "budget_row_arithmetic_error_count": 0, "budget_fee_error_count": 0,
        "budget_binding_error_count": 0}
    # The same reply as Markdown tables, unfenced, or with names in other cases, reads the same.
    table = re.sub(r"```csv\n(.*?)\n```", lambda m: "\n".join(
        "| " + " | ".join(line.split(",")) + " |" + ("\n|---|---|---|---|---|" if i == 0 else "")
        for i, line in enumerate(m.group(1).splitlines())), BUDGET_REFERENCE_REPLY, flags=re.DOTALL)
    assert not _failed(_results(BUDGET, table))
    assert not _failed(_results(BUDGET, BUDGET_REFERENCE_REPLY.replace("```csv\n", "").replace("```\n", "\n")))
    assert not _failed(_results(BUDGET, BUDGET_REFERENCE_REPLY.replace("review_sites,2", "Review_Sites,2")
                                .replace("$124,200", "124200")))


def test_budget_ignoring_the_ae_capacity_scores_zero_where_it_should():
    """The tempting reading: buy the best blocks wherever they are, as if the
    AEs could take every lead. It is infeasible, and every figure it changes is
    outside its zero band."""
    leads, cost, uncapped = _budget_search(None)[0]
    figures = _budget_figures(uncapped)
    assert figures["routed"] == 870 > 520
    binding = dict(task_facts_strategy.budget_binding(uncapped))
    careless = _budget_reply(uncapped, binding=binding, answers=[
        f"${cost:,}", f"{leads:,}", f"${cost / leads:.2f}", figures["routed"], 0])
    results = _results(BUDGET, careless)
    assert {"split_keeps_every_rule", "best_split", "a2_total_leads", "a3_cost_per_lead", "a4_routed_leads",
            "a5_capacity_cost", "binding_named"} == _zeroed(results) == _failed(results)
    # Its rows are honest arithmetic, its fees right, and it spends the same: those checks pass.
    assert results["rows_add_up"]["pass"] and results["fees_for_the_quarter"]["pass"] and results["a1_total_cost"]["pass"]


def test_budget_reading_the_fee_as_one_month_scores_zero_where_it_should():
    """The licence is per month and held all quarter. Read once, it frees a
    block; the split, its fee and its total cost are then wrong."""
    split = {"search": 10, "linkedin": 1, "webinars": 3, "syndication": 4, "review_sites": 2, "meta": 5}
    figures = _budget_figures(split)
    cost = figures["cost"] - 2 * 1_400                         # the fee counted once
    assert cost == 126_400 <= 128_000 < figures["cost"]
    careless = _budget_reply(split, fee_months=1, binding=task_facts_strategy.budget_binding(split),
                             answers=[f"${cost:,}", figures["leads"], f"{cost / figures['leads']:.2f}", 475, 32])
    results = _results(BUDGET, careless)
    assert {"split_keeps_every_rule", "best_split", "fees_for_the_quarter", "a1_total_cost", "a2_total_leads",
            "a3_cost_per_lead", "a5_capacity_cost"} <= _zeroed(results)
    assert results["a4_routed_leads"]["pass"] and results["rows_add_up"]["pass"]


def test_budget_dropping_a_commitment_or_a_minimum_order_is_infeasible():
    for split in ({"search": 10, "linkedin": 1, "webinars": 3, "syndication": 4, "review_sites": 0, "meta": 6},
                  {"search": 10, "linkedin": 1, "webinars": 3, "syndication": 3, "review_sites": 2, "meta": 5}):
        figures = _budget_figures(split)
        assert figures["leads"] > 2121 and figures["cost"] <= 128_000 and figures["routed"] <= 520
        reply = _budget_reply(split, answers=[figures["cost"], figures["leads"], 58, 475, 85])
        results = _results(BUDGET, reply)
        assert {"split_keeps_every_rule", "best_split", "a2_total_leads"} <= _zeroed(results)
        assert results["rows_add_up"]["pass"] and results["fees_for_the_quarter"]["pass"]


def test_budget_rows_that_do_not_add_up_are_caught_one_by_one():
    wrong_leads = BUDGET_REFERENCE_REPLY.replace("meta,4,20000,0,368", "meta,4,20000,0,350")
    assert _failed(_results(BUDGET, wrong_leads)) == {"rows_add_up"}
    cumulative = BUDGET_REFERENCE_REPLY.replace("search,10,50000,0,952", "search,10,50000,0,58")
    assert "rows_add_up" in _failed(_results(BUDGET, cumulative))
    missing_row = BUDGET_REFERENCE_REPLY.replace("syndication,4,20000,0,252\n", "")
    assert {"six_channels_once", "best_split", "split_keeps_every_rule", "rows_add_up",
            "fees_for_the_quarter"} <= _failed(_results(BUDGET, missing_row))
    extra = BUDGET_REFERENCE_REPLY.replace("meta,4,20000,0,368\n", "meta,4,20000,0,368\ntotal,24,120000,4200,2121\n")
    assert _failed(_results(BUDGET, extra)) == {"six_channels_once"}
    assert not _failed(_results(BUDGET, BUDGET_REFERENCE_REPLY.replace("ae_capacity,yes", "AE capacity,Yes")))
    flipped = BUDGET_REFERENCE_REPLY.replace("meta_max,no", "meta_max,yes")
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
