"""The experimental tasks of the 35-task board, each built to test one way of
being hard, so the three ways can be compared:

- ``launch-workflow-chain``: a chain of six deliverables in one reply, each
  built from the one before; the difficulty is that a name, a count or a
  product chosen early must match exactly in every later file.
- ``brief-amendment``: the original brief arrives one turn earlier, then the
  client's amendment; the difficulty is applying every change everywhere it
  bites, and nowhere else.
- ``policy-casebook``: forty proposed actions ruled against a long rulebook;
  the difficulty is judgement across clauses, with no arithmetic.

Each task has an oracle here that computes what its checks expect from the
task's supplied sources (file name -> text), and a reader that turns a reply
into measured facts: counts of what the reply got wrong. ``facts_for`` (called
from ``bench.measured_facts``) is the one entry point the runner calls. The
constants below are the numbers and names the sources state; each fixture's
generator (``eval_runner/fixtures/<task>/generate.py``) renders its text from
the same constants, so a rule the candidate reads and the rule applied here
cannot drift apart. ``tests/test_tasks_experiments.py`` recomputes every
figure with code of its own.

All brands, people, URLs and figures here are invented.
"""
from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .workflows import common

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _fold(text: object) -> str:
    """Lower case, one space between words: how copy is compared word for word."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _decimal(text: object) -> Decimal | None:
    try:
        return Decimal(str(text))
    except (InvalidOperation, ValueError):
        return None


def _sources_on_disk(folder: str, names: tuple[str, ...]) -> dict[str, str]:
    return {name: (FIXTURES / folder / name).read_text() for name in names}


# ══════════════════════════════════════════════════════════ launch-workflow-chain

CHAIN_FOLDER = "launch-workflow-chain"
CHAIN_SOURCES = ("campaign_brief.md", "audience_segments.csv", "product_catalogue.csv")
CHAIN_FILES = ("segments.csv", "structure.csv", "ads.csv", "trafficking.csv", "budget.csv")
CHAIN_COLUMNS = {
    "segments.csv": ("segment_id", "market", "type", "est_size"),
    "structure.csv": ("segment_id", "campaign_name", "ad_group_name", "sku"),
    "ads.csv": ("ad_group_name", "headline_1", "headline_2", "description"),
    "trafficking.csv": ("ad_group_name", "final_url"),
    "budget.csv": ("campaign_name", "daily_budget"),
}
CHAIN_MARKETS = ("US", "UK", "DE")
CHAIN_STORES = {"US": "us", "UK": "gb", "DE": "de"}
CHAIN_CURRENCY = {"US": ("$", "price_usd"), "UK": ("£", "price_gbp"), "DE": ("€", "price_eur")}
CHAIN_MIN_SIZE = {"prospecting": 50_000, "retargeting": 8_000}
CHAIN_CAP = {"prospecting": 2, "retargeting": 1}
CHAIN_TYPE_CODE = {"prospecting": "PRO", "retargeting": "RTG"}
CHAIN_PREFIX = "FTW_FS27"
CHAIN_DOMAIN = "https://www.fennicktrail.example"
CHAIN_UTM_SOURCE = "social"
CHAIN_UTM_MEDIUM = "paid"
CHAIN_CODE = "FELL10"
CHAIN_LIMITS = {"headline_1": 30, "headline_2": 30, "description": 90}
CHAIN_TOTAL_BUDGET = 3600
CHAIN_FLOOR = 180
CHAIN_ANSWERS = 5


def chain_segments_table(text: str) -> list[dict]:
    rows = _rows(text)
    for row in rows:
        row["est_size"] = int(row["est_size"])
    return rows


def chain_catalogue(text: str) -> dict[str, dict]:
    return {row["sku"]: row for row in _rows(text)}


def chain_selection_stages(table: list[dict]) -> list[tuple[str, list[dict]]]:
    """Step 1 of the brief, rule by rule, in its order: (rule, segments still in after it)."""
    stages = []
    left = [row for row in table if row["market"] in CHAIN_MARKETS]
    stages.append(("market", left))
    left = [row for row in left if row["source"] != "purchased"]
    stages.append(("purchased", left))
    left = [row for row in left if row["source"] != "first-party" or row["consent"] == "opt-in"]
    stages.append(("consent", left))
    left = [row for row in left if row["est_size"] >= CHAIN_MIN_SIZE[row["type"]]]
    stages.append(("size", left))
    # Duplicates: same market, type and interest; the larger stays, a tie keeps the lower id.
    kept: dict[tuple[str, str, str], dict] = {}
    for row in sorted(left, key=lambda r: (-r["est_size"], r["segment_id"])):
        kept.setdefault((row["market"], row["type"], row["interest"]), row)
    left = sorted(kept.values(), key=lambda r: r["segment_id"])
    stages.append(("duplicate", left))
    chosen = []
    for market in CHAIN_MARKETS:
        for kind, cap in CHAIN_CAP.items():
            group = sorted(
                (row for row in left if row["market"] == market and row["type"] == kind),
                key=lambda r: (-r["est_size"], r["segment_id"]),
            )
            chosen.extend(group[:cap])
    stages.append(("cap", sorted(chosen, key=lambda r: r["segment_id"])))
    return stages


def chain_chosen_segments(table: list[dict]) -> list[dict]:
    return chain_selection_stages(table)[-1][1]


def chain_campaign_name(segment: dict) -> str:
    return f"{CHAIN_PREFIX}_{segment['market']}_{segment['segment_code']}_{CHAIN_TYPE_CODE[segment['type']]}"


def chain_structure(segments: list[dict], catalogue: dict[str, dict]) -> list[dict]:
    """Step 2: one campaign per segment, one ad group per launch product of the
    segment's interest sold in its market."""
    rows = []
    for segment in segments:
        campaign = chain_campaign_name(segment)
        for sku, product in sorted(catalogue.items()):
            if (
                product["status"] == "launch"
                and product["category"] == segment["interest"]
                and segment["market"] in product["markets"].split(";")
            ):
                rows.append({
                    "segment_id": segment["segment_id"],
                    "campaign_name": campaign,
                    "ad_group_name": f"{campaign}_{sku}",
                    "sku": sku,
                })
    return rows


def chain_budget_shares(segments: list[dict]) -> list[tuple[str, Fraction]]:
    """(campaign name, exact share of the rest of the budget) per campaign."""
    rest = CHAIN_TOTAL_BUDGET - CHAIN_FLOOR * len(segments)
    total = sum(segment["est_size"] for segment in segments)
    return [(chain_campaign_name(s), Fraction(rest * s["est_size"], total)) for s in segments]


def chain_budget(segments: list[dict]) -> dict[str, int]:
    """Step 5: the floor, then the rest in proportion to size by largest remainder."""
    shares = chain_budget_shares(segments)
    amounts = {name: CHAIN_FLOOR + int(share) for name, share in shares}
    left = CHAIN_TOTAL_BUDGET - sum(amounts.values())
    by_remainder = sorted(shares, key=lambda item: (-(item[1] - int(item[1])), item[0]))
    for name, _share in by_remainder[:left]:
        amounts[name] += 1
    return amounts


def chain_landing_page(market: str, product: dict) -> str:
    return f"{CHAIN_DOMAIN}/{CHAIN_STORES[market]}/{product['slug']}"


def chain_price_text(market: str, product: dict) -> str:
    sign, column = CHAIN_CURRENCY[market]
    return f"{sign}{product[column]}"


def chain_reference(sources: dict[str, str]) -> dict:
    """Everything the checks of launch-workflow-chain expect, from its sources."""
    table = chain_segments_table(sources["audience_segments.csv"])
    catalogue = chain_catalogue(sources["product_catalogue.csv"])
    segments = chain_chosen_segments(table)
    structure = chain_structure(segments, catalogue)
    budget = chain_budget(segments)
    by_id = {row["segment_id"]: row for row in table}
    retargeting = sum(by_id[row["segment_id"]]["type"] == "retargeting" for row in structure)
    return {
        "segments": segments,
        "structure": structure,
        "budget": budget,
        "answers": {
            1: len(segments),
            2: len(structure),
            3: retargeting,
            4: len({row["sku"] for row in structure}),
            5: sum(budget.values()),
        },
    }


@lru_cache(maxsize=1)
def _chain_on_disk() -> tuple[dict, dict, dict]:
    sources = _sources_on_disk(CHAIN_FOLDER, CHAIN_SOURCES)
    return (
        chain_reference(sources),
        {row["segment_id"]: row for row in chain_segments_table(sources["audience_segments.csv"])},
        chain_catalogue(sources["product_catalogue.csv"]),
    )


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def chain_ad_numbers(product: dict, market: str) -> set[Decimal]:
    """The figures an ad for this product in this market may carry."""
    text = " ".join([product["ad_name"], product["proof_1"], product["proof_2"], product[CHAIN_CURRENCY[market][1]]])
    return {Decimal(token) for token in _NUMBER.findall(text)}


def chain_ad_problems(ad: dict, product: dict, market: str, kind: str, catalogue: dict[str, dict]) -> dict[str, bool]:
    """What is wrong with one ad, by check: over a limit or empty, a required
    part missing, another product's fact or a figure not its product's own."""
    fields = {name: (ad.get(name) or "").strip() for name in CHAIN_LIMITS}
    over = any(not value or len(value) > CHAIN_LIMITS[name] for name, value in fields.items())
    h1, h2, description = (_fold(fields[name]) for name in CHAIN_LIMITS)
    code = CHAIN_CODE.lower()
    code_right = code in description if kind == "retargeting" else code not in _fold(" ".join(fields.values()))
    required_missing = (
        _fold(product["ad_name"]) not in h1
        or not any(_fold(product[proof]) in h2 for proof in ("proof_1", "proof_2"))
        or chain_price_text(market, product) not in fields["description"]
        or not code_right
    )
    text = _fold(" ".join(fields.values()))
    foreign = False
    for sku, other in catalogue.items():
        if sku == product["sku"]:
            continue
        names = (other["ad_name"], other["product_name"], other["proof_1"], other["proof_2"])
        if any(_fold(name) in text for name in names):
            foreign = True
    allowed = chain_ad_numbers(product, market)
    stripped = re.sub(re.escape(CHAIN_CODE), " ", " ".join(fields.values()), flags=re.IGNORECASE)
    if any(Decimal(token) not in allowed for token in _NUMBER.findall(stripped)):
        foreign = True
    return {"over_limit": over, "required_missing": required_missing, "foreign": foreign}


def _url(text: str) -> str:
    match = re.search(r"https?://[^\s<>()`\"']+", text or "")
    return match.group(0) if match else ""


def chain_url_right(url: str, expected_page: str, expected_params: dict[str, str]) -> bool:
    parts = urlsplit(_url(url))
    page = f"{parts.scheme}://{parts.netloc.lower()}{parts.path.rstrip('/')}"
    if page != expected_page or parts.fragment:
        return False
    params = parse_qsl(parts.query, keep_blank_values=True)
    return len(params) == len(expected_params) and dict(params) == expected_params


def _keyed(rows: list[dict] | None, column: str) -> dict[str, list[dict]]:
    keyed: dict[str, list[dict]] = {}
    for row in rows or []:
        keyed.setdefault((row.get(column) or "").strip(), []).append(row)
    return keyed


def _key_errors(expected: set[str], rows: list[dict] | None, column: str, empty: int) -> int:
    """Rows of a later file keyed by the names an earlier file gave: each name
    needs exactly one row, and a row naming anything else is an error."""
    if not expected:
        return empty
    keyed = _keyed(rows, column)
    missing_or_repeated = sum(len(keyed.get(name, [])) != 1 for name in expected)
    unknown = sum(len(found) for name, found in keyed.items() if name not in expected)
    return missing_or_repeated + unknown


def chain_facts(response_text: str, task: dict | None = None) -> dict:
    reference, segment_table, catalogue = _chain_on_disk()
    files = common.tables(response_text, list(CHAIN_FILES))
    groups_expected = len(reference["structure"])
    campaigns_expected = len(reference["segments"])
    facts = {"chain_missing_file_count": sum(files[name] is None for name in CHAIN_FILES)}

    # Step 1, against the reference: the right segments, each as the table gives it.
    oracle_segments = {row["segment_id"]: row for row in reference["segments"]}
    reply_segments = _keyed(files["segments.csv"], "segment_id")
    errors = sum(1 for name in reply_segments if name not in oracle_segments)
    for segment_id, segment in oracle_segments.items():
        found = reply_segments.get(segment_id, [])
        if len(found) != 1 or any(
            _fold(found[0].get(column)) != _fold(segment[column]) for column in ("market", "type")
        ) or _decimal((found[0].get("est_size") or "").replace(",", "")) != segment["est_size"]:
            errors += 1
    facts["chain_segment_error_count"] = errors

    # Step 2, against the reference: each campaign's name, then each ad group.
    structure = files["structure.csv"] or []
    names_by_segment: dict[str, set[str]] = {}
    for row in structure:
        names_by_segment.setdefault((row.get("segment_id") or "").strip(), set()).add((row.get("campaign_name") or "").strip())
    errors = sum(1 for name in names_by_segment if name not in oracle_segments)
    for segment_id, segment in oracle_segments.items():
        if names_by_segment.get(segment_id) != {chain_campaign_name(segment)}:
            errors += 1
    facts["chain_campaign_error_count"] = errors
    oracle_groups = {row["ad_group_name"]: row for row in reference["structure"]}
    reply_groups = _keyed(structure, "ad_group_name")
    errors = sum(len(found) for name, found in reply_groups.items() if name not in oracle_groups)
    for name, group in oracle_groups.items():
        found = reply_groups.get(name, [])
        if len(found) != 1 or any((found[0].get(column) or "").strip() != group[column] for column in ("segment_id", "campaign_name", "sku")):
            errors += 1
    facts["chain_ad_group_error_count"] = errors

    # Steps 3 to 6, against the reply's own structure: every later file must
    # agree with the names, products and counts the reply itself chose.
    own_groups = {}
    for row in structure:
        name = (row.get("ad_group_name") or "").strip()
        if name:
            own_groups.setdefault(name, row)
    own_campaigns = {(row.get("campaign_name") or "").strip() for row in structure} - {""}

    facts["chain_ad_key_error_count"] = _key_errors(set(own_groups), files["ads.csv"], "ad_group_name", groups_expected)
    over = required = foreign = 0
    evaluated = 0
    for ad in files["ads.csv"] or []:
        group = own_groups.get((ad.get("ad_group_name") or "").strip())
        product = catalogue.get((group or {}).get("sku", "").strip())
        segment = segment_table.get((group or {}).get("segment_id", "").strip())
        if not product or not segment or segment["market"] not in CHAIN_MARKETS:
            continue
        evaluated += 1
        problems = chain_ad_problems(ad, product, segment["market"], segment["type"], catalogue)
        over += problems["over_limit"]
        required += problems["required_missing"]
        foreign += problems["foreign"]
    if not evaluated:
        over = required = foreign = groups_expected
    facts["chain_ad_limit_error_count"] = over
    facts["chain_ad_required_error_count"] = required
    facts["chain_ad_foreign_fact_count"] = foreign

    facts["chain_tracking_key_error_count"] = _key_errors(set(own_groups), files["trafficking.csv"], "ad_group_name", groups_expected)
    errors = evaluated = 0
    for row in files["trafficking.csv"] or []:
        group = own_groups.get((row.get("ad_group_name") or "").strip())
        product = catalogue.get((group or {}).get("sku", "").strip())
        segment = segment_table.get((group or {}).get("segment_id", "").strip())
        if not group:
            continue
        evaluated += 1
        if not product or not segment or segment["market"] not in CHAIN_MARKETS:
            errors += 1
            continue
        expected = {
            "utm_source": CHAIN_UTM_SOURCE,
            "utm_medium": CHAIN_UTM_MEDIUM,
            "utm_campaign": group["campaign_name"].strip().lower(),
            "utm_content": group["ad_group_name"].strip().lower(),
        }
        if not chain_url_right(row.get("final_url") or "", chain_landing_page(segment["market"], product), expected):
            errors += 1
    facts["chain_url_error_count"] = errors if evaluated else groups_expected

    facts["chain_budget_key_error_count"] = _key_errors(own_campaigns, files["budget.csv"], "campaign_name", campaigns_expected)
    reply_budget = _keyed(files["budget.csv"], "campaign_name")
    errors = 0
    for name, amount in reference["budget"].items():
        found = reply_budget.get(name, [])
        if len(found) != 1 or common.money(found[0].get("daily_budget")) != Decimal(amount):
            errors += 1
    facts["chain_budget_amount_error_count"] = errors

    # Step 6: the pre-launch check reports the reply's own files.
    from . import bench  # the answer-block reader; bench imports this module first

    answers = bench._single_number_answers(response_text, CHAIN_ANSWERS)
    if not structure or files["ads.csv"] is None or files["budget.csv"] is None:
        facts["chain_prelaunch_error_count"] = CHAIN_ANSWERS
    else:
        amounts = [common.money(row.get("daily_budget")) for row in files["budget.csv"]]
        own = {
            1: len(own_campaigns),
            2: len(own_groups),
            3: sum(CHAIN_CODE.lower() in _fold(row.get("description")) for row in files["ads.csv"]),
            4: len({(row.get("sku") or "").strip() for row in structure} - {""}),
            5: sum((amount for amount in amounts if amount is not None), Decimal(0)),
        }
        facts["chain_prelaunch_error_count"] = sum(
            index not in answers or abs(Decimal(str(answers[index])) - Decimal(value)) > Decimal("0.005")
            for index, value in own.items()
        )
    return facts


# ══════════════════════════════════════════════════════════════════ entry point

FACTS = {
    "launch-workflow-chain": chain_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts one of these tasks adds, or nothing for any other task."""
    build = FACTS.get((task or {}).get("id"))
    return build(response_text, task) if build else {}
