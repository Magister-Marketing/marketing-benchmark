"""The experimental tasks: launch-workflow-chain, brief-amendment and policy-casebook.

What is pinned here, for every task:

- the committed fixtures are byte for byte what the task's generator
  (`eval_runner/fixtures/<task>/generate.py`) writes, and writing is deterministic;
- every figure a check expects is what the oracle
  (`eval_runner/task_facts_experiments.py`) computes, and what this file
  recomputes from the committed fixtures with code of its own;
- a reference reply written out by hand passes every program check, and a
  blank reply earns nothing;
- the reply the task is built to catch scores zero on each check it touches,
  and only there.
"""
import csv
import importlib.util
import io
import json
import re
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

from eval_runner import bench, task_facts_experiments

FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"
TASKS = ("launch-workflow-chain",)


def _generator(folder: str):
    path = FIXTURES / folder / "generate.py"
    spec = importlib.util.spec_from_file_location(f"generate_{folder.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _task(task_id: str) -> dict:
    return bench.load_tasks()[task_id]


def _table(folder: str, name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((FIXTURES / folder / name).read_text())))


def _by_id(task: dict) -> dict[str, dict]:
    return {c["id"]: c for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section]}


def _results(task_id: str, response: str) -> dict:
    task = _task(task_id)
    return bench.programmatic_results(task, bench.measured_facts(task, response))


def _failed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if not result["pass"]}


def _zeroed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if result["score"] == 0}


def _csv_file(name: str, header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return f"### {name}\n\n```csv\n{out.getvalue()}```\n"


# ------------------------------------------------------------------ every task

@pytest.mark.parametrize("task_id", TASKS)
def test_the_fixtures_on_disk_are_what_the_generator_writes(task_id):
    folder = FIXTURES / task_id
    built = _generator(task_id).build()
    on_disk = {name: (folder / name).read_text() for name in built}
    assert built == on_disk
    assert built == _generator(task_id).build()                        # deterministic
    task = _task(task_id)
    supplied = {str(Path(path).relative_to(f"eval_runner/fixtures/{task_id}")) for path in task["fixtures"]}
    if task.get("decoy"):
        supplied.add(str(Path(task["decoy"]["fixture"]).relative_to(f"eval_runner/fixtures/{task_id}")))
    assert supplied == set(built)
    written = {str(path.relative_to(folder)) for path in folder.rglob("*") if path.is_file() and "__pycache__" not in path.parts}
    assert written == supplied | {"generate.py"}
    assert sum(len(text.encode()) for text in built.values()) < 60_000


@pytest.mark.parametrize("task_id", TASKS)
def test_the_task_is_shaped_as_the_board_needs(task_id):
    task = _task(task_id)
    criteria = _by_id(task)
    programmatic = [c for c in criteria.values() if c.get("programmatic")]
    assert task["split"] == "development"
    assert 10 <= len(criteria) <= 18
    assert len(programmatic) / len(criteria) >= 0.7
    assert bench.free_credit_scores(task) == {}                        # nothing is already true of an empty reply
    for path in task["skills"]:
        assert (bench.REPO_ROOT / path).is_file()


# ══════════════════════════════════════════════════════════ launch-workflow-chain

CHAIN = "launch-workflow-chain"


def _chain_recomputed() -> dict:
    """Step 1, 2 and 5 of the brief, written again from the brief's words."""
    segments = _table(CHAIN, "audience_segments.csv")
    products = _table(CHAIN, "product_catalogue.csv")
    for row in segments:
        row["est_size"] = int(row["est_size"])
    keep = []
    for row in segments:
        if row["market"] not in ("US", "UK", "DE") or row["source"] == "purchased":
            continue
        if row["source"] == "first-party" and row["consent"] != "opt-in":
            continue
        if row["est_size"] < (50000 if row["type"] == "prospecting" else 8000):
            continue
        keep.append(row)
    deduped = []
    for row in keep:
        rivals = [r for r in keep if (r["market"], r["type"], r["interest"]) == (row["market"], row["type"], row["interest"])]
        best = max(rivals, key=lambda r: (r["est_size"], -int(r["segment_id"][1:])))
        if best is row:
            deduped.append(row)
    chosen = []
    for row in deduped:
        rivals = sorted(
            (r for r in deduped if r["market"] == row["market"] and r["type"] == row["type"]),
            key=lambda r: (-r["est_size"], r["segment_id"]),
        )
        if row in rivals[: (2 if row["type"] == "prospecting" else 1)]:
            chosen.append(row)
    code = {"prospecting": "PRO", "retargeting": "RTG"}
    campaigns = {row["segment_id"]: f"FTW_FS27_{row['market']}_{row['segment_code']}_{code[row['type']]}" for row in chosen}
    groups = []
    for row in chosen:
        for product in products:
            if product["status"] == "launch" and product["category"] == row["interest"] and row["market"] in product["markets"].split(";"):
                groups.append((row, product, campaigns[row["segment_id"]], f"{campaigns[row['segment_id']]}_{product['sku']}"))
    rest = 3600 - 180 * len(chosen)
    total = sum(row["est_size"] for row in chosen)
    exact = {campaigns[row["segment_id"]]: Fraction(rest * row["est_size"], total) for row in chosen}
    budget = {name: 180 + int(share) for name, share in exact.items()}
    for name in sorted(exact, key=lambda n: (-(exact[n] - int(exact[n])), n))[: 3600 - sum(budget.values())]:
        budget[name] += 1
    return {"chosen": chosen, "campaigns": campaigns, "groups": groups, "budget": budget, "products": products}


def test_chain_oracle_matches_a_recomputation_and_the_task_file():
    mine = _chain_recomputed()
    reference = task_facts_experiments._chain_on_disk()[0]
    assert [row["segment_id"] for row in mine["chosen"]] == [row["segment_id"] for row in reference["segments"]]
    assert sorted((g[0]["segment_id"], g[2], g[3], g[1]["sku"]) for g in mine["groups"]) == sorted(
        (row["segment_id"], row["campaign_name"], row["ad_group_name"], row["sku"]) for row in reference["structure"]
    )
    assert mine["budget"] == reference["budget"]
    assert sum(mine["budget"].values()) == 3600
    assert len(mine["chosen"]) == 8 and len(mine["groups"]) == 30
    # The figures the checks name are the computed ones.
    criteria = _by_id(_task(CHAIN))
    ids = ", ".join(row["segment_id"] for row in mine["chosen"])
    assert f"({ids})" in criteria["segments_chosen"]["check"]
    budget_text = ", ".join(f"{name} ${amount:,}" for name, amount in mine["budget"].items())
    assert budget_text in criteria["budget_amounts_right"]["check"]
    assert f"remaining ${3600 - 180 * 8:,}" in criteria["budget_amounts_right"]["check"]
    retargeting = sum(g[0]["type"] == "retargeting" for g in mine["groups"])
    assert reference["answers"] == {1: 8, 2: 30, 3: retargeting, 4: len({g[1]["sku"] for g in mine["groups"]}), 5: 3600}


def test_chain_brief_states_the_rules_the_oracle_applies():
    brief = (FIXTURES / CHAIN / "campaign_brief.md").read_text()
    for phrase in (
        "Launch markets only: US, UK and DE", "a segment whose source is `purchased` is out",
        "needs consent `opt-in`", "at least\n   50,000", "at least 8,000", "keep the one with the lower segment_id",
        "at most\n   2 prospecting segments and\n   1 retargeting segment", "`FTW_FS27_<market>_<segment_code>_<type code>`",
        "`gb` for UK", "utm_source=social", "utm_medium=paid", "FELL10", "Every campaign first gets $180",
        "total daily budget is $3,600", "(a tie goes to the\n  campaign whose name sorts first)",
    ):
        assert phrase in brief, phrase
    prompt = _task(CHAIN)["prompt"]
    for header in ("segment_id,market,type,est_size", "segment_id,campaign_name,ad_group_name,sku",
                   "ad_group_name,headline_1,headline_2,description", "ad_group_name,final_url",
                   "campaign_name,daily_budget"):
        assert header in prompt
    # The prompt asks for the work without pointing at a trap.
    for word in ("duplicate", "drift", "partner", "gb", "trap"):
        assert word not in prompt.lower()


def _chain_reply(mutate=None) -> str:
    """A reply written from the recomputation: every file, then the check.
    `mutate(files)` may change the rows before they are written."""
    mine = _chain_recomputed()
    signs = {"US": ("$", "price_usd"), "UK": ("£", "price_gbp"), "DE": ("€", "price_eur")}
    stores = {"US": "us", "UK": "gb", "DE": "de"}
    files = {
        "segments.csv": [[r["segment_id"], r["market"], r["type"], r["est_size"]] for r in mine["chosen"]],
        "structure.csv": [[g[0]["segment_id"], g[2], g[3], g[1]["sku"]] for g in mine["groups"]],
        "ads.csv": [],
        "trafficking.csv": [],
        "budget.csv": [[name, amount] for name, amount in mine["budget"].items()],
    }
    for segment, product, campaign, group in mine["groups"]:
        sign, column = signs[segment["market"]]
        price = f"{sign}{product[column]}"
        if segment["type"] == "retargeting":
            description = f"Back for the {product['ad_name']}? {price} with code FELL10."
        else:
            description = f"Meet the {product['ad_name']} from Fennick Trailworks. {price}."
        files["ads.csv"].append([group, f"New: {product['ad_name']}", product["proof_1"], description])
        url = (f"https://www.fennicktrail.example/{stores[segment['market']]}/{product['slug']}"
               f"?utm_source=social&utm_medium=paid&utm_campaign={campaign.lower()}&utm_content={group.lower()}")
        files["trafficking.csv"].append([group, url])
    answers = [len(mine["campaigns"]), len(mine["groups"]),
               sum(g[0]["type"] == "retargeting" for g in mine["groups"]),
               len({g[1]["sku"] for g in mine["groups"]}), sum(mine["budget"].values())]
    if mutate:
        answers = mutate(files, answers) or answers
    headers = task_facts_experiments.CHAIN_COLUMNS
    body = "Here is the launch build.\n\n" + "\n".join(
        _csv_file(name, list(headers[name]), rows) for name, rows in files.items()
    )
    return body + "\nPre-launch check:\n\n" + "\n".join(f"A{i}: {v}" for i, v in enumerate(answers, 1)) + "\n"


def test_chain_reference_reply_passes_every_program_check_and_a_blank_reply_none():
    results = _results(CHAIN, _chain_reply())
    assert _failed(results) == set(), {k: v["evidence"] for k, v in results.items() if not v["pass"]}
    assert len(results) == 13
    blank = _results(CHAIN, "")
    assert all(result["score"] == 0 for result in blank.values())
    # Each ad sits inside its limits with the required parts: the reference is a real one.
    reply = _chain_reply()
    assert "FELL10" in reply and "£339" in reply and "€369" in reply


def test_a_name_that_drifts_in_one_later_file_fails_that_files_agreement_check():
    """Every step right in isolation, one name written differently downstream:
    the cross-file check of that file fails, and nothing that is still right."""
    def drift_trafficking(files, answers):
        row = files["trafficking.csv"][7]
        row[0] = row[0].replace("FTW_FS27_", "FTW-FS27_")
    assert _failed(_results(CHAIN, _chain_reply(drift_trafficking))) == {"tracking_rows_match_structure"}

    def drift_ads(files, answers):
        row = files["ads.csv"][12]
        row[0] = row[0].lower()
    assert _failed(_results(CHAIN, _chain_reply(drift_ads))) == {"one_ad_per_ad_group"}

    def drift_budget(files, answers):
        files["budget.csv"][2][0] = files["budget.csv"][2][0].replace("_RTG", "_RET")
    failed = _failed(_results(CHAIN, _chain_reply(drift_budget)))
    assert failed == {"budget_rows_match_campaigns", "budget_amounts_right"}

    def drift_utm(files, answers):            # the parameter built from a name other than the structure's
        row = files["trafficking.csv"][20]
        row[1] = row[1].replace("utm_content=ftw_fs27_", "utm_content=")
    assert _failed(_results(CHAIN, _chain_reply(drift_utm))) == {"urls_built_from_names"}

    def drift_product(files, answers):        # an ad written for the product of the ad group beside it
        files["ads.csv"][0][1:] = list(files["ads.csv"][1][1:])
    failed = _failed(_results(CHAIN, _chain_reply(drift_product)))
    assert failed == {"ads_carry_required_facts", "ads_use_own_product_only"}

    def drift_count(files, answers):          # the check reports the plan, not the files built
        del files["structure.csv"][5]
        del files["ads.csv"][5]
        del files["trafficking.csv"][5]
        return answers                        # still says 30 ad groups
    failed = _failed(_results(CHAIN, _chain_reply(drift_count)))
    assert failed == {"ad_groups_built", "prelaunch_check_matches_package"}


def test_a_consistent_but_wrong_early_choice_fails_only_the_checks_against_the_brief():
    """The tempting reading of step 1: keep the first-party duplicate over the
    larger partner one. Every later file follows the reply's own choice, so
    the agreement checks pass and the checks against the brief score zero."""
    def first_party_duplicate(files, answers):
        for name in ("structure.csv", "ads.csv", "trafficking.csv", "budget.csv"):
            for row in files[name]:
                for index, value in enumerate(row):
                    if isinstance(value, str):
                        row[index] = value.replace("US_HKX", "US_HKR").replace("us_hkx", "us_hkr")
        for row in files["structure.csv"]:
            if row[0] == "S02":
                row[0] = "S01"
        for row in files["segments.csv"]:
            if row[0] == "S02":
                row[:] = ["S01", "US", "prospecting", 182400]
        files["budget.csv"][:] = [[name, amount] for name, amount in _budget_with("S01", "S02").items()]
        answers[4] = sum(amount for _name, amount in files["budget.csv"])
        return answers
    results = _results(CHAIN, _chain_reply(first_party_duplicate))
    assert _zeroed(results) == {"segments_chosen", "campaigns_named", "ad_groups_built", "budget_amounts_right"}
    assert _failed(results) == _zeroed(results)


def _budget_with(new_id: str, old_id: str) -> dict[str, int]:
    """Step 5 over the chosen segments with one swapped for another."""
    mine = _chain_recomputed()
    table = {row["segment_id"]: row for row in _table(CHAIN, "audience_segments.csv")}
    chosen = [table[new_id] if row["segment_id"] == old_id else table[row["segment_id"]] for row in mine["chosen"]]
    code = {"prospecting": "PRO", "retargeting": "RTG"}
    names = [f"FTW_FS27_{r['market']}_{r['segment_code']}_{code[r['type']]}" for r in chosen]
    sizes = [int(r["est_size"]) for r in chosen]
    exact = [Fraction(2160 * size, sum(sizes)) for size in sizes]
    budget = {name: 180 + int(share) for name, share in zip(names, exact)}
    order = sorted(range(len(names)), key=lambda i: (-(exact[i] - int(exact[i])), names[i]))
    for i in order[: 3600 - sum(budget.values())]:
        budget[names[i]] += 1
    return budget


def test_chain_ad_rules_catch_each_kind_of_wrong_ad():
    def uk_store(files, answers):             # the UK store written as "uk"
        for row in files["trafficking.csv"]:
            row[1] = row[1].replace("/gb/", "/uk/")
    assert _zeroed(_results(CHAIN, _chain_reply(uk_store))) == {"urls_built_from_names"}

    def code_everywhere(files, answers):      # the code on prospecting ads too
        for row in files["ads.csv"]:
            if "FELL10" not in row[3]:
                row[3] = row[3].rstrip(".") + " Code FELL10."
        answers[2] = 30
        return answers
    assert _zeroed(_results(CHAIN, _chain_reply(code_everywhere))) == {"ads_carry_required_facts"}

    def dollar_everywhere(files, answers):    # the US price in every market
        mine = _chain_recomputed()
        for row, (segment, product, _c, _g) in zip(files["ads.csv"], mine["groups"]):
            if segment["market"] != "US" and product["price_usd"]:
                row[3] = row[3].replace(f"£{product['price_gbp']}", f"${product['price_usd']}").replace(
                    f"€{product['price_eur']}", f"${product['price_usd']}")
    assert _zeroed(_results(CHAIN, _chain_reply(dollar_everywhere))) == {
        "ads_carry_required_facts", "ads_use_own_product_only"}

    def a_season(files, answers):             # an invented figure in the copy
        for row in files["ads.csv"][:3]:
            row[1] = row[1] + " 2027"
    assert _failed(_results(CHAIN, _chain_reply(a_season))) == {"ads_use_own_product_only"}

    def long_headlines(files, answers):
        for row in files["ads.csv"][:3]:
            row[1] = row[1] + " for the long trail ahead"
    assert _zeroed(_results(CHAIN, _chain_reply(long_headlines))) == {"ads_within_limits"}
