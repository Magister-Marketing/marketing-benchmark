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
import datetime as dt
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


# ═════════════════════════════════════════════════════════════════ brief-amendment

AMEND_FOLDER = "brief-amendment"
AMEND_SHEET = "original/product_sheet.csv"     # sent with the original brief, one turn earlier
AMEND_FIXTURE = "amendment.md"                   # the task's own source: the client's changes
AMEND_FILES = ("launch_plan.csv", "email_schedule.csv", "ads.csv")
AMEND_COLUMNS = {
    "launch_plan.csv": ("market", "launch_date", "ads_start", "ads_end", "budget_usd"),
    "email_schedule.csv": ("market", "email", "send_date", "subject"),
    "ads.csv": ("ad_id", "market", "item_id", "headline", "claim", "price"),
}
AMEND_SIGNS = {"US": ("$", "price_usd"), "UK": ("£", "price_gbp"), "IE": ("€", "price_eur")}
AMEND_EMAILS = (("teaser", -4), ("launch", 0), ("reminder", 3))
AMEND_FLIGHT_DAYS = 28
AMEND_HOLIDAYS = {
    "US": ("2027-01-01", "2027-01-18", "2027-02-15", "2027-05-31"),
    "UK": ("2027-01-01", "2027-03-26", "2027-03-29", "2027-05-03", "2027-05-31"),
    "IE": ("2027-01-01", "2027-02-01", "2027-03-17", "2027-03-29", "2027-05-03"),
}
AMEND_SUBJECTS = {
    "teaser": "Brightwell arrives {date}",
    "launch": "Meet the {featured}",
    "reminder": "Still thinking about the {featured}?",
}
# The brief as signed off.
AMEND_BRIEF = {
    "signed_off": "2027-02-08",
    "launch": "2027-03-09",
    "markets": ("US", "UK"),
    "budget": {"US": 28_800, "UK": 19_200},
}
# The client's amendment, as the amendment fixture states it.
AMEND_CHANGES = {
    "sent": "2027-02-22",
    "launch": "2027-03-30",
    "withdrawn": "P01",
    "prices": (
        # item, market, new price, in effect from
        ("P06", "US", 259, "2027-03-01"),
        ("P03", "UK", 74, "2027-05-01"),
    ),
    "added_market": "IE",
    "added_budget": 6_000,
    "budget_from": "UK",
    "banned_claim": "dishwasher-safe",
}


def _iso(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def amend_sheet(text: str) -> dict[str, dict]:
    return {row["item_id"]: row for row in _rows(text)}


def _working_day_on_or_before(day: dt.date, market: str) -> dt.date:
    holidays = {_iso(value) for value in AMEND_HOLIDAYS[market]}
    while day.weekday() >= 5 or day in holidays:
        day -= dt.timedelta(days=1)
    return day


def _date_words(day: dt.date) -> str:
    return f"{day.day} {day.strftime('%B')}"


def amend_plan(sheet: dict[str, dict], changes: dict | None) -> dict:
    """The plan the brief gives, as signed off (changes=None) or as amended.
    Prices are those in effect on launch day; a bundle runs only while every
    item in it is in the launch."""
    launch = _iso((changes or AMEND_BRIEF)["launch"])
    markets = list(AMEND_BRIEF["markets"]) + ([changes["added_market"]] if changes else [])
    budget = dict(AMEND_BRIEF["budget"])
    if changes:
        budget[changes["budget_from"]] -= changes["added_budget"]
        budget[changes["added_market"]] = changes["added_budget"]
    withdrawn = {changes["withdrawn"]} if changes else set()
    prices: dict[tuple[str, str], int] = {}
    for item_id, row in sheet.items():
        for market, (_sign, column) in AMEND_SIGNS.items():
            if row[column]:
                prices[(market, item_id)] = int(row[column])
    for item_id, market, price, start in (changes or {}).get("prices", ()):
        if _iso(start) <= launch:
            prices[(market, item_id)] = price
    live = {item_id for item_id in sheet if item_id not in withdrawn}
    live = {
        item_id for item_id in live
        if sheet[item_id]["kind"] != "bundle" or set(sheet[item_id]["bundle_items"].split(";")) <= live
    }
    banned = (changes or {}).get("banned_claim")
    ads = {}
    for item_id in sorted(live):
        row = sheet[item_id]
        for market in markets:
            if market not in row["markets"].split(";"):
                continue
            claim = row["claim_1"]
            if banned and banned in claim.lower():
                claim = row["claim_2"]
            ads[(market, item_id)] = {
                "headline": row["ad_name"],
                "claim": claim,
                "price": f"{AMEND_SIGNS[market][0]}{prices[(market, item_id)]}",
                "amount": prices[(market, item_id)],
            }
    plan_rows = {
        market: {
            "launch_date": launch,
            "ads_start": launch,
            "ads_end": launch + dt.timedelta(days=AMEND_FLIGHT_DAYS - 1),
            "budget_usd": budget[market],
        }
        for market in markets
    }
    emails = {}
    for market in markets:
        in_market = [item_id for (m, item_id) in ads if m == market]
        bundles = [item_id for item_id in in_market if sheet[item_id]["kind"] == "bundle"]
        if bundles:
            featured = bundles[0]
        else:
            featured = sorted(in_market, key=lambda item: (-ads[(market, item)]["amount"], item))[0]
        name = sheet[featured]["ad_name"]
        for email, offset in AMEND_EMAILS:
            day = _working_day_on_or_before(launch + dt.timedelta(days=offset), market)
            subject = AMEND_SUBJECTS[email].format(date=_date_words(launch), featured=name)
            emails[(market, email)] = {"send_date": day, "subject": subject, "featured": featured}
    return {"markets": plan_rows, "emails": emails, "ads": ads}


def amend_reference(sheet_text: str) -> dict:
    """The final plan, the plan as signed off, and which ads and emails each
    change of the amendment reaches, by kind."""
    sheet = amend_sheet(sheet_text)
    original = amend_plan(sheet, None)
    final = amend_plan(sheet, AMEND_CHANGES)
    added = AMEND_CHANGES["added_market"]
    withdrawn = AMEND_CHANGES["withdrawn"]
    banned = AMEND_CHANGES["banned_claim"]
    bundles_lost = sorted(
        item_id for item_id, row in sheet.items()
        if row["kind"] == "bundle" and withdrawn in row["bundle_items"].split(";")
    )
    claim_ads = sorted(key for key in final["ads"] if banned in sheet[key[1]]["claim_1"].lower())
    rises = sorted(
        (market, item_id) for item_id, market, _price, start in AMEND_CHANGES["prices"]
        if _iso(start) <= _iso(AMEND_CHANGES["launch"])
    )
    not_yet = sorted(
        (market, item_id) for item_id, market, _price, start in AMEND_CHANGES["prices"]
        if _iso(start) > _iso(AMEND_CHANGES["launch"])
    )
    moved_emails = sorted(
        key for key, email in final["emails"].items()
        if email["send_date"] != _iso(AMEND_CHANGES["launch"]) + dt.timedelta(days=dict(AMEND_EMAILS)[key[1]])
    )
    # In the markets the brief had, each ad keeps every field no change reaches:
    # its headline always, its claim unless the claim was withdrawn, its price
    # unless a price change names it (the one not yet in effect is checked on
    # its own). Ireland's ads are new; their fields are checked together.
    kept_fields = {}
    for key in sorted(final["ads"]):
        if key[0] == added:
            continue
        fields = ["headline"]
        if key not in claim_ads:
            fields.append("claim")
        if key not in rises and key not in not_yet:
            fields.append("price")
        assert all(original["ads"][key][field] == final["ads"][key][field] for field in fields), key
        kept_fields[key] = tuple(fields)
    return {
        "final": final,
        "original": original,
        "sheet": sheet,
        "withdrawn_item": withdrawn,
        "bundles_lost": bundles_lost,
        "added_market": added,
        "claim_ads": claim_ads,
        "price_rises": rises,
        "prices_not_yet": not_yet,
        "holiday_moves": moved_emails,
        "kept_fields": kept_fields,
    }


@lru_cache(maxsize=1)
def _amend_on_disk() -> dict:
    return amend_reference((FIXTURES / AMEND_FOLDER / AMEND_SHEET).read_text())


def _date_cell(text: object) -> dt.date | None:
    value = re.sub(r"\s+", " ", str(text or "")).strip().strip("*`\"'")
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y", "%A %d %B %Y", "%A, %d %B %Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _subject(text: object) -> str:
    value = _fold(text).replace("’", "'").replace("“", "").replace("”", "").strip("\"'` ")
    return value.rstrip(".?! ")


def _claim(text: object) -> str:
    return _fold(text).replace("’", "'").strip("\"'` ").rstrip(". ")


def _market(text: object) -> str:
    return _fold(text).upper()


def _email_kind(text: object) -> str | None:
    value = _fold(text)
    found = [kind for kind, _offset in AMEND_EMAILS if kind in value]
    return found[0] if len(found) == 1 else None


def _price_right(cell: object, market: str, amount: int) -> bool:
    value = str(cell or "").strip()
    sign = AMEND_SIGNS[market][0]
    others = [s for s, _c in AMEND_SIGNS.values() if s != sign]
    return sign in value and not any(s in value for s in others) and common.money(value) == Decimal(amount)


def _reply_ads(rows: list[dict] | None) -> dict[tuple[str, str], list[dict]]:
    keyed: dict[tuple[str, str], list[dict]] = {}
    for row in rows or []:
        market = _market(row.get("market"))
        item = _fold(row.get("item_id")).upper()
        if not item:
            match = re.fullmatch(r"([A-Za-z]{2})-([A-Za-z]\d{2})", (row.get("ad_id") or "").strip())
            if match:
                market, item = match.group(1).upper(), match.group(2).upper()
        keyed.setdefault((market, item), []).append(row)
    return keyed


def amend_facts(response_text: str, task: dict | None = None) -> dict:
    reference = _amend_on_disk()
    final, sheet = reference["final"], reference["sheet"]
    files = common.tables(response_text, list(AMEND_FILES))
    facts = {"amend_missing_file_count": sum(files[name] is None for name in AMEND_FILES)}

    # The launch plan: each market's dates, and its budget.
    plan = {}
    for row in files["launch_plan.csv"] or []:
        plan.setdefault(_market(row.get("market")), []).append(row)
    date_errors = sum(len(found) for market, found in plan.items() if market not in final["markets"])
    budget_errors = 0
    for market, expected in final["markets"].items():
        found = plan.get(market, [])
        if len(found) != 1 or any(
            _date_cell(found[0].get(column)) != expected[column] for column in ("launch_date", "ads_start", "ads_end")
        ):
            date_errors += 1
        if len(found) != 1 or common.money(found[0].get("budget_usd")) != Decimal(expected["budget_usd"]):
            budget_errors += 1
    facts["amend_plan_date_error_count"] = date_errors
    facts["amend_budget_error_count"] = budget_errors

    # The ads: which exist, and each one's headline, claim and price.
    ads = _reply_ads(files["ads.csv"])
    any_rows = bool(files["ads.csv"])
    withdrawn = reference["withdrawn_item"]
    lost = set(reference["bundles_lost"])
    added = reference["added_market"]

    def ad_right(key, *, claim=True, price=True, headline=True) -> bool:
        found = ads.get(key, [])
        if len(found) != 1:
            return False
        row, expected = found[0], final["ads"][key]
        return (
            (not headline or _fold(row.get("headline")) == _fold(expected["headline"]))
            and (not claim or _claim(row.get("claim")) == _claim(expected["claim"]))
            and (not price or _price_right(row.get("price"), key[0], expected["amount"]))
        )

    facts["amend_withdrawn_ad_count"] = (
        sum(len(found) for (market, item), found in ads.items() if item == withdrawn) if any_rows else 2
    )
    facts["amend_bundle_ad_count"] = (
        sum(len(found) for (market, item), found in ads.items() if item in lost) if any_rows else 2
    )
    gone = {withdrawn} | lost
    ireland_expected = {key for key in final["ads"] if key[0] == added}
    facts["amend_ireland_ad_error_count"] = sum(len(ads.get(key, [])) != 1 for key in ireland_expected) + sum(
        len(found) for key, found in ads.items() if key[0] == added and key not in ireland_expected and key[1] not in gone
    )
    others_expected = {key for key in final["ads"] if key[0] != added}
    facts["amend_other_ad_error_count"] = sum(len(ads.get(key, [])) != 1 for key in others_expected) + sum(
        len(found) for key, found in ads.items()
        if key[0] != added and key not in others_expected and key[1] not in gone
    )
    banned = AMEND_CHANGES["banned_claim"]
    claim_errors = sum(not ad_right(key, price=False, headline=False) for key in reference["claim_ads"])
    claim_errors += sum(
        1 for key, found in ads.items() if key not in reference["claim_ads"]
        for row in found if banned.replace("-", "") in _fold(" ".join([row.get("claim") or "", row.get("headline") or ""])).replace("-", "").replace(" ", "")
    )
    facts["amend_claim_error_count"] = claim_errors
    facts["amend_price_rise_error_count"] = sum(
        not ad_right(key, claim=False, headline=False) for key in reference["price_rises"]
    )
    facts["amend_later_price_error_count"] = sum(
        not ad_right(key, claim=False, headline=False) for key in reference["prices_not_yet"]
    )
    facts["amend_ireland_ad_field_error_count"] = sum(
        not ad_right(key, claim=key not in reference["claim_ads"]) for key in sorted(ireland_expected)
    )
    facts["amend_untouched_error_count"] = sum(
        not ad_right(key, headline="headline" in fields, claim="claim" in fields, price="price" in fields)
        for key, fields in reference["kept_fields"].items()
    )

    # The emails: each one's send date and subject.
    emails: dict[tuple[str, str | None], list[dict]] = {}
    for row in files["email_schedule.csv"] or []:
        emails.setdefault((_market(row.get("market")), _email_kind(row.get("email"))), []).append(row)

    def email_right(key, column: str) -> bool:
        found = emails.get(key, [])
        if len(found) != 1:
            return False
        if column == "send_date":
            return _date_cell(found[0].get("send_date")) == final["emails"][key]["send_date"]
        return _subject(found[0].get("subject")) == _subject(final["emails"][key]["subject"])

    moved = reference["holiday_moves"]
    facts["amend_holiday_move_error_count"] = sum(not email_right(key, "send_date") for key in moved)
    facts["amend_email_date_error_count"] = sum(
        not email_right(key, "send_date") for key in final["emails"] if key not in moved
    ) + sum(len(found) for key, found in emails.items() if key not in final["emails"])
    facts["amend_teaser_subject_error_count"] = sum(
        not email_right(key, "subject") for key in final["emails"] if key[1] == "teaser"
    )
    facts["amend_featured_error_count"] = sum(
        not email_right(key, "subject") for key in final["emails"] if key[1] != "teaser"
    )
    return facts


# ═════════════════════════════════════════════════════════════════ policy-casebook
#
# The policy's deciding clauses, as a machine-readable copy of the text the
# generator writes (`fixtures/policy-casebook/policy.md`), and the forty cases
# as the attributes their prose states (`cases.md`). `casebook_decide` applies
# the policy's own decision procedure (its clause 1.5) to one case and returns
# the ruling, the condition and the deciding clause, with the clauses still
# standing at the last step, so a test can prove each case has exactly one.

CASEBOOK_FOLDER = "policy-casebook"
CASEBOOK_SOURCES = ("policy.md", "cases.md")
CASEBOOK_FILE = "rulings.csv"
CASEBOOK_COLUMNS = ("case_id", "ruling", "condition", "clause")
ALLOWED, CONDITIONAL, NOT_ALLOWED = "allowed", "allowed with condition", "not allowed"
STRICTNESS = {ALLOWED: 0, CONDITIONAL: 1, NOT_ALLOWED: 2}
CONDITIONS = (
    "ad-label", "gift-note", "employee-tag", "skill-question", "terms-link", "price-record",
    "legal-signoff", "study-on-file", "partner-approval",
)
DEFAULT_CLAUSE = "1.6"
# The policy's numbers, rendered into its text by the generator.
POLICY = {
    "depth": 40, "depth_cl": 50, "clearance_depth": 60, "new_days": 90, "reference_days": 28,
    "price_check_days": 7, "superlative_months": 12, "improvement_months": 12, "prize_cap": 5_000,
    "contest_cap": 20_000, "gift_value": 100, "minor_share": 25, "soft_months": 24,
    "quiet": ("20:00", "09:00"), "quiet_cl": ("21:00", "08:00"), "surge_age_cl": 21,
}
CLEARANCE_EVENTS = (
    ("Winter Clearance 2026", "2026-01-05", "2026-01-25"),
    ("Summer Clearance 2026", "2026-07-20", "2026-08-09"),
    ("Winter Clearance 2027", "2027-01-04", "2027-01-24"),
)
SCHEDULE_C = ("Hydra+ Electrolyte Mix", "Surge Pre-Workout")


def _clearance(case: dict) -> bool:
    day = _iso(case["date"])
    return any(_iso(start) <= day <= _iso(end) for _name, start, end in CLEARANCE_EVENTS)


def _person(case: dict) -> dict:
    return case.get("person") or {}


def _influencer(case: dict) -> bool:
    """1.3(h): paid in any amount, or given product worth more than the gift
    value, to post; never an employee."""
    person = _person(case)
    return bool(person) and person["kind"] != "employee" and (
        person.get("paid", 0) > 0 or person.get("gift", 0) > POLICY["gift_value"])


def _gifted_creator(case: dict) -> bool:
    person = _person(case)
    return bool(person) and person["kind"] != "employee" and not person.get("paid", 0) and 0 < person.get("gift", 0) <= POLICY["gift_value"]


def _minor_directed(case: dict) -> bool:
    """1.3(j): targeting that includes under-18s, a placement over the stated
    under-18 share, or a person under 18 shown in it."""
    return bool(case.get("targets_minors") or case.get("under_18_share", 0) > POLICY["minor_share"]
                or case.get("shows_minor") or (_person(case).get("age", 99) < 18))


def _marketing_message(case: dict) -> bool:
    """1.3(m): an email or SMS that promotes; a transactional one that carries a promotion counts."""
    return case.get("channel") in ("email", "sms")


def _reductions(case: dict) -> list[tuple[str, int]]:
    return case.get("reductions", [])


def _co_branded(case: dict) -> bool:
    return (case.get("co_brand") or {}).get("kind") in ("partner", "beneficiary")


def _claims(case: dict) -> dict:
    return case.get("claims", {})


def _quiet(time: str, window: tuple[str, str]) -> bool:
    start, end = window
    return time >= start or time < end


def _outcome(ruling: str, condition: str | None = None) -> tuple[str, str | None]:
    return (ruling, condition)


DISPLACE = ("displace", None)   # an exception to an exception: it puts the clause back, and decides nothing


def _rule_3_1(depth: int):
    return lambda c: _outcome(NOT_ALLOWED) if any(p > depth for _k, p in _reductions(c)) else None


def _rule_3_5(markets: tuple[str, ...] | None):
    def test(c):
        kinds = sorted(kind for kind, _p in _reductions(c))
        if kinds == ["code", "loyalty"] and (markets is None or c["market"] in markets):
            return _outcome(CONDITIONAL, "terms-link")
        return None
    return test


def _rule_4_5(with_studies: bool):
    def test(c):
        claim = _claims(c).get("clinically_proven")
        if claim is None:
            return None
        if with_studies and claim.get("product") in SCHEDULE_C:
            return _outcome(CONDITIONAL, "study-on-file")
        return _outcome(NOT_ALLOWED)
    return test


def _rule_5_4(markets: tuple[str, ...]):
    return lambda c: _outcome(NOT_ALLOWED) if c.get("promotion") == "giveaway" and c["market"] in markets else None


def _rule_6_1(surge_age: int | None):
    def test(c):
        if not _influencer(c):
            return None
        age = _person(c).get("age", 99)
        if age < 18 or (surge_age and c.get("range") == "surge" and age < surge_age):
            return _outcome(NOT_ALLOWED)
        return None
    return test


def _rule_7_5(window: tuple[str, str]):
    return lambda c: _outcome(NOT_ALLOWED) if c.get("channel") == "sms" and _quiet(c.get("send_time", "12:00"), window) else None


def _superlative(c):
    claim = _claims(c).get("superlative")
    if claim is None:
        return None
    age = claim.get("data_months")
    if age is not None and age < POLICY["superlative_months"]:
        return _outcome(CONDITIONAL, "study-on-file")
    return _outcome(NOT_ALLOWED)


def _reference_price(c):
    days = c.get("reference_days")
    if days is None:
        return None
    return _outcome(CONDITIONAL, "price-record") if days >= POLICY["reference_days"] else _outcome(NOT_ALLOWED)


# id, part, the clauses it is an exception to (empty for a rule), and its test.
CASEBOOK_CLAUSES = [
    ("2.1", 2, (), lambda c: _outcome(NOT_ALLOWED) if "disease" in _claims(c) else None),
    ("2.2", 2, (), lambda c: _outcome(NOT_ALLOWED) if c.get("promotion") == "giveaway" and c.get("purchase_required") else None),
    ("2.3", 2, (), lambda c: _outcome(CONDITIONAL, "skill-question") if c.get("promotion") == "giveaway" and c["market"] == "CA" else None),
    ("2.4", 2, (), lambda c: _outcome(NOT_ALLOWED) if _marketing_message(c) and c.get("consent") != "opted-in" else None),
    ("2.4(a)", 2, ("2.4",), lambda c: _outcome(ALLOWED) if (
        c.get("channel") == "email" and c["market"] in ("UK", "IE") and c.get("consent") == "past-customer"
        and c.get("last_order_months", 99) <= POLICY["soft_months"] and c.get("opt_out_offered")) else None),
    ("2.5", 2, (), lambda c: _outcome(CONDITIONAL, "ad-label") if _influencer(c) else None),
    ("2.6", 2, (), lambda c: _outcome(NOT_ALLOWED) if c.get("range") == "surge" and _minor_directed(c) else None),
    ("3.1", 3, (), _rule_3_1(POLICY["depth"])),
    ("3.2", 3, ("3.1",), lambda c: _outcome(ALLOWED) if _clearance(c) and all(p <= POLICY["clearance_depth"] for _k, p in _reductions(c)) else None),
    ("3.3", 3, ("3.2",), lambda c: DISPLACE if c.get("first_sold_days", 9999) < POLICY["new_days"] else None),
    ("3.4", 3, (), lambda c: _outcome(NOT_ALLOWED) if len(_reductions(c)) >= 2 else None),
    ("3.5", 3, ("3.4",), _rule_3_5(None)),
    ("3.6", 3, ("3.5",), lambda c: DISPLACE if _clearance(c) else None),
    ("3.7", 3, (), _reference_price),
    ("4.1", 4, (), lambda c: _outcome(CONDITIONAL, "legal-signoff") if "comparative" in _claims(c) else None),
    ("4.2", 4, ("4.1",), lambda c: _outcome(ALLOWED) if (
        _claims(c).get("comparative", {}).get("price_only")
        and _claims(c)["comparative"].get("checked_days", 99) <= POLICY["price_check_days"]) else None),
    ("4.3", 4, (), _superlative),
    ("4.4", 4, (), lambda c: None if "function" not in _claims(c) else (
        _outcome(ALLOWED) if _claims(c)["function"].get("listed") else _outcome(NOT_ALLOWED))),
    ("4.5", 4, (), _rule_4_5(False)),
    ("4.6", 4, (), lambda c: _outcome(NOT_ALLOWED) if _claims(c).get("improvement", {}).get("months", 0) > POLICY["improvement_months"] else None),
    ("5.1", 5, (), lambda c: _outcome(NOT_ALLOWED) if c.get("promotion") in ("giveaway", "contest") and not c.get("rules_published") else None),
    ("5.2", 5, (), lambda c: _outcome(NOT_ALLOWED) if c.get("promotion") and c.get("prize", 0) > POLICY["prize_cap"] else None),
    ("5.3", 5, ("5.2",), lambda c: _outcome(ALLOWED) if c.get("promotion") == "contest" and c.get("prize", 0) <= POLICY["contest_cap"] else None),
    ("5.4", 5, (), _rule_5_4(("DE",))),
    ("6.1", 6, (), _rule_6_1(None)),
    ("6.2", 6, (), lambda c: _outcome(CONDITIONAL, "gift-note") if _gifted_creator(c) else None),
    ("6.3", 6, (), lambda c: _outcome(CONDITIONAL, "employee-tag") if _person(c).get("kind") == "employee" else None),
    ("6.4", 6, (), lambda c: _outcome(NOT_ALLOWED) if c.get("review") == "unverified" else None),
    ("6.5", 6, ("6.2", "2.5"), lambda c: _outcome(ALLOWED) if _person(c).get("platform_label") else None),
    ("7.1", 7, (), lambda c: _outcome(CONDITIONAL, "partner-approval") if _co_branded(c) else None),
    ("7.2", 7, (), lambda c: _outcome(NOT_ALLOWED) if _co_branded(c) and c["co_brand"].get("category") in ("alcohol", "gambling", "tobacco") else None),
    ("7.3", 7, ("7.1",), lambda c: _outcome(ALLOWED) if (c.get("co_brand") or {}).get("kind") == "beneficiary" else None),
    ("7.4", 7, (), lambda c: _outcome(NOT_ALLOWED) if _co_branded(c) and c.get("channel") == "email" and c["co_brand"].get("list") == "partner" else None),
    ("7.5", 7, (), _rule_7_5(POLICY["quiet"])),
]
# The change log: id, the date it takes effect, the clause it replaces or
# deletes, and the replacement's test (None deletes the clause; an entry with
# no clause changes process only).
CHANGE_LOG = [
    ("CL-1", "2026-05-01", "7.5", _rule_7_5(POLICY["quiet_cl"])),
    ("CL-2", "2026-06-01", "3.5", _rule_3_5(("US", "CA"))),
    ("CL-3", "2026-07-01", "4.5", _rule_4_5(True)),
    ("CL-4", "2026-09-01", "5.4", _rule_5_4(("DE", "AU"))),
    ("CL-5", "2026-10-15", "3.1", _rule_3_1(POLICY["depth_cl"])),
    ("CL-6", "2026-12-01", None, None),
    ("CL-7", "2027-01-01", "6.1", _rule_6_1(POLICY["surge_age_cl"])),
    ("CL-8", "2027-06-01", "4.3", None),
]


def _clause_key(clause_id: str) -> tuple:
    """Order of clause numbers: 2.4 before 2.4(a) before 2.5, change-log entries last."""
    if clause_id.startswith("CL-"):
        return (99, int(clause_id[3:]), "")
    head, _, letter = clause_id.partition("(")
    part, number = head.split(".")
    return (int(part), int(number), letter)


def casebook_in_force(date: str) -> dict[str, dict]:
    """Step A: the policy in force on a date, each clause under the number to cite."""
    clauses = {
        cid: {"id": cid, "part": part, "targets": targets, "test": test}
        for cid, part, targets, test in CASEBOOK_CLAUSES
    }
    for entry_id, start, replaces, test in CHANGE_LOG:
        if replaces is None or _iso(start) > _iso(date):
            continue
        old = next(key for key, clause in clauses.items() if key == replaces or clause.get("replaces") == replaces)
        if test is None:
            del clauses[old]
        else:
            clauses[old] = dict(clauses[old], id=entry_id, test=test, replaces=replaces)
    return clauses


def casebook_decide(case: dict) -> dict:
    """Clause 1.5, step by step. Returns the ruling, condition and deciding
    clause, and the clauses still standing at step D (for the uniqueness proof)."""
    clauses = casebook_in_force(case["date"])
    rules = {key: c for key, c in clauses.items() if not c["targets"]}
    exceptions = {key: c for key, c in clauses.items() if c["targets"]}
    covered = {key: outcome for key, c in rules.items() if (outcome := c["test"](case)) is not None}
    # Step C. An exception applies only to an action a clause it names covers.
    applied = {}
    for depth in (1, 2):
        for key, c in exceptions.items():
            targets_here = [t for t in c["targets"] if t in covered or t in applied]
            is_second = any(t in exceptions for t in c["targets"])
            if (depth == 2) != is_second or not targets_here:
                continue
            outcome = c["test"](case)
            if outcome is not None:
                applied[key] = outcome
    standing = dict(covered)
    for key, outcome in applied.items():
        if outcome == DISPLACE:
            continue
        put_back = [x for x, o in applied.items() if o == DISPLACE and key in exceptions[x]["targets"]]
        if put_back:
            continue
        for target in exceptions[key]["targets"]:
            if target in standing and (clauses[target]["part"] != 2 or exceptions[key]["part"] == 2):
                del standing[target]
        standing[key] = outcome
    if not standing:
        return {"ruling": ALLOWED, "condition": None, "clause": DEFAULT_CLAUSE, "standing": {}}
    # Step D, then step E.
    top = max(STRICTNESS[outcome[0]] for outcome in standing.values())
    group = sorted((key for key, outcome in standing.items() if STRICTNESS[outcome[0]] == top), key=_clause_key)
    part_two = [key for key in group if clauses[key]["part"] == 2]
    chosen = part_two[0] if part_two else group[0]
    ruling, condition = standing[chosen]
    return {"ruling": ruling, "condition": condition, "clause": clauses[chosen]["id"],
            "standing": {clauses[key]["id"]: standing[key] for key in standing}, "top": [clauses[k]["id"] for k in group],
            "part_two_in_top": [clauses[k]["id"] for k in part_two]}


# The forty cases: their trap group, the attributes the prose states, and the prose.
CASEBOOK_GROUPS = {
    "plain": "one clause decides, as it reads",
    "offer_definitions": "a definition of an offer or a claim decides which clause covers it",
    "people_definitions": "a definition of a person or an audience decides which clause covers it",
    "exceptions": "an exception displaces the clause it names",
    "exception_limits": "an exception to an exception, or an exception that does not reach the case",
    "log_decides": "a change-log entry in force replaces a clause and decides",
    "log_takes_out": "a change-log entry in force takes the case out of a clause",
    "log_not_in_force": "a change-log entry dated after the action does not apply",
    "part_two": "a Part 2 clause outranks, or cannot be displaced by, a clause elsewhere",
}


def casebook_rulings(cases: list[dict]) -> dict[str, dict]:
    return {case["id"]: casebook_decide(case) for case in cases}


def _clause_cell(text: object) -> str:
    """The first clause number a cell gives: "2.4(a)", "Clause 2.4 (a)", "CL2",
    "1.6 (default)". A cell with none is returned as it is, and matches nothing."""
    value = str(text or "")
    match = re.search(r"(?i)\bCL\s*-?\s*(\d+)\b|\b(\d)\.(\d+)(?:\s*\(([a-z])\)|([a-z])\b)?", value)
    if not match:
        return value.strip()
    if match.group(1):
        return f"CL-{int(match.group(1))}"
    letter = (match.group(4) or match.group(5) or "").lower()
    return f"{match.group(2)}.{match.group(3)}" + (f"({letter})" if letter else "")


def _ruling_cell(text: object) -> str | None:
    value = _fold(text).strip("*`. ")
    if not value:
        return None
    if re.search(r"\bnot\b|\bdisallowed\b|\bprohibited\b", value):
        return NOT_ALLOWED
    if "condition" in value or value == "conditional":
        return CONDITIONAL
    if value.startswith("allowed") or value == "allow":
        return ALLOWED
    return None


def _condition_cell(text: object) -> str:
    """The condition a cell names: the one name of the policy's list it
    contains ("ad-label", "ad label (#ad first)"), else the cell itself."""
    value = re.sub(r"[\s_]+", "-", _fold(text).strip("*`.\"' "))
    named = [name for name in CONDITIONS if name in value]
    return named[0] if len(named) == 1 else value


@lru_cache(maxsize=1)
def _casebook_on_disk() -> dict[str, dict]:
    return casebook_rulings(CASEBOOK_CASES)


def casebook_facts(response_text: str, task: dict | None = None) -> dict:
    expected = _casebook_on_disk()
    rows = common.tables(response_text, [CASEBOOK_FILE])[CASEBOOK_FILE]
    found: dict[str, list[dict]] = {}
    for row in rows or []:
        found.setdefault(_fold(row.get("case_id")).upper(), []).append(row)
    coverage = sum(len(found.get(case_id, [])) != 1 for case_id in expected) + sum(
        len(items) for case_id, items in found.items() if case_id not in expected)
    facts = {"casebook_missing_file_count": int(rows is None), "casebook_coverage_error_count": coverage}
    wrong = {group: 0 for group in CASEBOOK_GROUPS}
    for case in CASEBOOK_CASES:
        want = expected[case["id"]]
        items = found.get(case["id"], [])
        right = len(items) == 1
        if right:
            row = items[0]
            right = (
                _ruling_cell(row.get("ruling")) == want["ruling"]
                and _clause_cell(row.get("clause")) == want["clause"]
                and (want["ruling"] != CONDITIONAL or _condition_cell(row.get("condition")) == want["condition"])
            )
        wrong[case["group"]] += not right
    for group, count in wrong.items():
        facts[f"casebook_wrong_{group}_count"] = count
    return facts


def _case(cid, group, title, date, market, channel, text, **attributes) -> dict:
    return {"id": cid, "group": group, "title": title, "date": date, "market": market, "channel": channel,
            "text": text, **attributes}


CASEBOOK_CASES = [
    _case("C01", "log_decides", "Clinically proven, dissolving", "2026-09-10", "US", "paid social",
          "A paid social ad for Hydra+ Electrolyte Mix with the line \"Clinically proven to dissolve fully in "
          "10 seconds\", the property the March 2026 laboratory study of the mix measured. No price, no "
          "promotion; the ad targets adults aged 25 to 54.",
          range="hydration", claims={"clinically_proven": {"product": "Hydra+ Electrolyte Mix"}}),
    _case("C02", "offer_definitions", "Spring markdown with free shipping", "2026-03-03", "US", "website",
          "The Whey Isolate product page shows \"Was $59, now $47\" (a 20% markdown) for two weeks, and every "
          "order of it ships free during those weeks. The $59 price was charged for 40 days in the six months "
          "before. No code, no loyalty discount.",
          range="core", reductions=[("markdown", 20)], free_shipping=True, reference_days=40),
    _case("C03", "plain", "Comparison with a rival's taste", "2026-05-18", "UK", "paid social",
          "A paid social ad for Whey Isolate that says \"Smoother than Maxlift Whey\", naming the rival brand. "
          "The claim is about taste and texture, not price. The ad targets adults.",
          range="core", claims={"comparative": {"price_only": False}}),
    _case("C04", "exceptions", "Summer Clearance on bars", "2026-07-28", "UK", "website",
          "During the summer sale the site takes 55% off the Oat Protein Bar (chocolate), a flavour first sold "
          "in the UK two years ago. One price reduction per order; no code.",
          range="core", reductions=[("sale", 55)], first_sold_days=730),
    _case("C05", "part_two", "A 16-year-old on Surge", "2026-10-20", "US", "influencer post",
          "A paid creator, aged 16, is offered $700 for a TikTok video in which she takes Surge Pre-Workout "
          "before a race. The video shows her throughout. The post would carry #ad in its first line, and the "
          "campaign targets viewers aged 18 and over.",
          range="surge", person={"kind": "creator", "paid": 700, "age": 16}),
    _case("C06", "people_definitions", "Freelance photographer's post", "2026-04-08", "US", "influencer post",
          "A freelance photographer who shoots our product images on contract (she is not on Northvane's "
          "payroll) is paid $400 to post a reel about the Oat Protein Bar on her own Instagram account. She is 31.",
          range="core", person={"kind": "contractor", "paid": 400, "age": 31}),
    _case("C07", "log_not_in_force", "Evening text in April", "2026-04-10", "UK", "sms",
          "A marketing SMS about the Hydra+ spring flavours to customers who opted in to texts, scheduled for "
          "20:30 UK time.",
          range="hydration", consent="opted-in", send_time="20:30"),
    _case("C08", "log_decides", "Australian giveaway", "2026-10-05", "AU", "organic social",
          "An Instagram giveaway in Australia: follow the account and comment to enter, no purchase needed, "
          "winners drawn at random. The prize is a year of Hydra+ worth $800, and the official rules are "
          "published with the post.",
          range="hydration", promotion="giveaway", purchase_required=False, rules_published=True, prize=800),
    _case("C09", "exception_limits", "Clearance on a new flavour", "2026-07-30", "US", "website",
          "In the summer sale, 55% off the Hydra+ Berry flavour, first sold in the US six weeks before the sale "
          "starts. One price reduction per order; no code.",
          range="hydration", reductions=[("sale", 55)], first_sold_days=42),
    _case("C10", "plain", "Paid creator on whey", "2026-06-02", "US", "influencer post",
          "A fitness creator aged 26 is paid $1,500 for one Instagram post about Whey Isolate. The post is on "
          "her own account; there is no giveaway and no discount code.",
          range="core", person={"kind": "creator", "paid": 1500, "age": 26}),
    _case("C11", "exceptions", "Ten dollars less than Maxlift", "2026-05-06", "US", "paid social",
          "A paid social ad: \"Whey Isolate: $10 less than Maxlift Whey\". The claim is about price only, and "
          "Maxlift's published price was checked three days before the ad goes live.",
          range="core", claims={"comparative": {"price_only": True, "checked_days": 3}}),
    _case("C12", "log_takes_out", "Loyalty and a code in the UK, August", "2026-08-24", "UK", "email",
          "An email to UK loyalty members who opted in: their 10% member discount plus a 15% code on one order "
          "of Whey Isolate, with a link to the offer's terms.",
          range="core", consent="opted-in", reductions=[("loyalty", 10), ("code", 15)]),
    _case("C13", "people_definitions", "A gifted box", "2026-03-19", "UK", "influencer post",
          "A runner aged 24 is sent a box of Hydra+ worth $60, with no payment and nothing else, and plans to "
          "post about it on her own Instagram account.",
          range="hydration", person={"kind": "creator", "gift": 60, "age": 24}),
    _case("C14", "log_decides", "Clinically proven, mixing", "2026-08-01", "US", "website",
          "The Whey Isolate page adds \"Clinically proven to mix without clumps\". The claims register holds no "
          "study for Whey Isolate.",
          range="core", claims={"clinically_proven": {"product": "Northvane Whey Isolate"}}),
    _case("C15", "plain", "Gym partnership email", "2026-09-14", "US", "email",
          "An email to our opted-in subscribers announcing a joint offer with IronHouse Gyms: a free month at "
          "IronHouse with any Whey Isolate order, under both brands' logos.",
          range="core", consent="opted-in", co_brand={"kind": "partner", "category": "fitness", "list": "own"}),
    _case("C16", "part_two", "Cure-all bar", "2026-11-09", "US", "paid social",
          "A paid social ad for the Oat Protein Bar: \"The best bar there is, and it helps prevent colds\". There "
          "is no independent data behind \"the best\".",
          range="core", claims={"disease": {}, "superlative": {"data_months": None}}),
    _case("C17", "exception_limits", "Loyalty and a code in the January sale", "2026-01-12", "US", "email",
          "During the January sale, an email to US loyalty members who opted in: their 10% member discount plus "
          "a 15% code on one order of the Oat Protein Bar.",
          range="core", consent="opted-in", reductions=[("loyalty", 10), ("code", 15)]),
    _case("C18", "people_definitions", "Surge on a teen-heavy placement", "2026-05-27", "US", "paid social",
          "A paid ad for Surge Pre-Workout, targeted at people aged 18 to 34, in a placement the platform "
          "reports as 31% under 18. The ad shows two adult athletes.",
          range="surge", under_18_share=31),
    _case("C19", "log_not_in_force", "Surge creator aged 19, December", "2026-12-01", "US", "influencer post",
          "A creator aged 19 is paid $900 to post a video about Surge Pre-Workout on her own TikTok account. "
          "The video shows only her, and targets viewers aged 18 and over.",
          range="surge", person={"kind": "creator", "paid": 900, "age": 19}),
    _case("C20", "exceptions", "Donation email", "2026-10-07", "UK", "email",
          "An email to our opted-in UK subscribers: for every order this month we donate £1 to RunFree Trust, a "
          "registered charity, named in the email with its logo. No other partner.",
          range="core", consent="opted-in", co_brand={"kind": "beneficiary", "category": "charity", "list": "own"}),
    _case("C21", "offer_definitions", "Order confirmation with a code", "2026-06-23", "US", "email",
          "The order-confirmation email adds a 10% code for the customer's next order. It goes to every US "
          "customer who orders, including those who have never opted in to marketing.",
          range="core", consent="no", transactional=True, reductions=[("code", 10)]),
    _case("C22", "plain", "Sitewide sale in April", "2026-04-10", "US", "website",
          "A sitewide sale taking 45% off every product for a weekend. One price reduction per order; no code, "
          "no loyalty discount.",
          range="core", reductions=[("sale", 45)]),
    _case("C23", "log_takes_out", "Sitewide sale in November", "2026-11-20", "US", "website",
          "A sitewide sale taking 45% off every product for a weekend. One price reduction per order; no code, "
          "no loyalty discount.",
          range="core", reductions=[("sale", 45)]),
    _case("C24", "exceptions", "Gifted box with the platform label", "2026-09-02", "UK", "influencer post",
          "A cyclist aged 29 is sent a box of the Oat Protein Bar worth $45, with no payment, and posts about it "
          "with the platform's own \"Paid partnership\" label switched on.",
          range="core", person={"kind": "creator", "gift": 45, "age": 29, "platform_label": True}),
    _case("C25", "exception_limits", "Text to past customers in Ireland", "2026-05-12", "IE", "sms",
          "A marketing SMS at 12:00 to customers in Ireland who last ordered six months ago, were offered the "
          "chance to opt out at checkout, have never opted in to marketing and have never opted out.",
          range="hydration", consent="past-customer", last_order_months=6, opt_out_offered=True, send_time="12:00"),
    _case("C26", "part_two", "Purchase-to-enter in Germany", "2026-05-05", "DE", "organic social",
          "An Instagram giveaway in Germany that needs a purchase to enter (upload your receipt), winners drawn "
          "at random, prize worth $500, official rules published.",
          range="core", promotion="giveaway", purchase_required=True, rules_published=True, prize=500),
    _case("C27", "log_decides", "Surge creator aged 19, February", "2027-02-10", "US", "influencer post",
          "A creator aged 19 is paid $900 to post a video about Surge Pre-Workout on her own TikTok account. "
          "The video shows only her, and targets viewers aged 18 and over.",
          range="surge", person={"kind": "creator", "paid": 900, "age": 19}),
    _case("C28", "exceptions", "Twelve-thousand-dollar contest", "2026-06-15", "US", "organic social",
          "A recipe contest: entrants post a recipe using Whey Isolate and a panel of chefs picks the winner. "
          "No purchase needed. The prize is a kitchen worth $12,000, and the official rules are published.",
          range="core", promotion="contest", purchase_required=False, rules_published=True, prize=12000),
    _case("C29", "log_takes_out", "Evening text in June", "2026-06-15", "UK", "sms",
          "A marketing SMS about the Hydra+ summer flavours to customers who opted in to texts, scheduled for "
          "20:30 UK time.",
          range="hydration", consent="opted-in", send_time="20:30"),
    _case("C30", "offer_definitions", "Photo contest with a receipt", "2026-08-18", "US", "organic social",
          "A photo contest judged by a panel on creativity: to enter, buy any Northvane product and post a photo "
          "with the receipt. Prize worth $2,000; official rules published.",
          range="core", promotion="contest", purchase_required=True, rules_published=True, prize=2000),
    _case("C31", "plain", "Canadian giveaway", "2026-03-24", "CA", "organic social",
          "An Instagram giveaway in Canada: follow and comment to enter, no purchase needed, winners drawn at "
          "random, prize worth $300, official rules published.",
          range="hydration", promotion="giveaway", purchase_required=False, rules_published=True, prize=300),
    _case("C32", "exception_limits", "Price comparison checked twelve days before", "2026-05-20", "US", "paid social",
          "A paid social ad: \"Whey Isolate: $10 less than Maxlift Whey\", about price only. Maxlift's published "
          "price was last checked twelve days before the ad goes live.",
          range="core", claims={"comparative": {"price_only": True, "checked_days": 12}}),
    _case("C33", "exceptions", "Email to past customers in the UK", "2026-05-20", "UK", "email",
          "A marketing email about Whey Isolate to UK customers who last ordered ten months ago, were offered "
          "the chance to opt out at checkout, have never opted in to marketing and have never opted out.",
          range="core", consent="past-customer", last_order_months=10, opt_out_offered=True),
    _case("C34", "plain", "Warehouse staff post", "2026-07-07", "UK", "organic social",
          "A part-time member of our warehouse staff, on Northvane's payroll, posts about the Oat Protein Bar on "
          "her own TikTok after we give her a box worth $40.",
          range="core", person={"kind": "employee", "gift": 40, "age": 22}),
    _case("C35", "log_decides", "Loyalty and a code in the US, August", "2026-08-24", "US", "email",
          "An email to US loyalty members who opted in: their 10% member discount plus a 15% code on one order "
          "of Whey Isolate, with a link to the offer's terms.",
          range="core", consent="opted-in", reductions=[("loyalty", 10), ("code", 15)]),
    _case("C36", "people_definitions", "A 16-year-old swimmer on whey", "2026-06-20", "US", "influencer post",
          "A swimmer aged 16 is paid $500 to post about Whey Isolate on her own Instagram account. The post shows "
          "her, carries #ad and targets adults.",
          range="core", person={"kind": "creator", "paid": 500, "age": 16}),
    _case("C37", "offer_definitions", "New formula claim", "2026-10-26", "US", "paid social",
          "A paid social ad: \"New formula: 20% more protein than our previous Whey Isolate\". The formula "
          "changed 18 months before the ad goes live. No other brand is named or shown.",
          range="core", claims={"improvement": {"months": 18}}),
    _case("C38", "log_not_in_force", "Best-tasting whey", "2027-03-01", "US", "paid social",
          "A paid social ad calling Whey Isolate \"the best-tasting whey\". The independent taste panel behind "
          "it reported 20 months before the ad goes live.",
          range="core", claims={"superlative": {"data_months": 20}}),
    _case("C39", "part_two", "Paid creator with the platform label", "2026-08-11", "US", "influencer post",
          "A creator aged 30 is paid $900 to post about Hydra+ with the platform's own \"Paid partnership\" label "
          "switched on, and no #ad in the post itself.",
          range="hydration", person={"kind": "creator", "paid": 900, "age": 30, "platform_label": True}),
    _case("C40", "exception_limits", "Clearance at sixty-five percent", "2026-08-03", "UK", "website",
          "In the summer sale, 65% off the Oat Protein Bar (vanilla), a flavour first sold in the UK three years "
          "ago. One price reduction per order.",
          range="core", reductions=[("sale", 65)], first_sold_days=1095),
]


# ══════════════════════════════════════════════════════════════════ entry point

FACTS = {
    "launch-workflow-chain": chain_facts,
    "brief-amendment": amend_facts,
    "policy-casebook": casebook_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts one of these tasks adds, or nothing for any other task."""
    build = FACTS.get((task or {}).get("id"))
    return build(response_text, task) if build else {}
