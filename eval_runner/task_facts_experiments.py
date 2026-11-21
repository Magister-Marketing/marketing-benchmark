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


# ══════════════════════════════════════════════════════════════════ entry point

FACTS = {
    "launch-workflow-chain": chain_facts,
    "brief-amendment": amend_facts,
}


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts one of these tasks adds, or nothing for any other task."""
    build = FACTS.get((task or {}).get("id"))
    return build(response_text, task) if build else {}
