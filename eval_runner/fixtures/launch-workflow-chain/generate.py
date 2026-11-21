#!/usr/bin/env python3
"""Write, or check, the sources of the launch-workflow-chain task.

Deterministic: every row is written out below, and the brief's rules are
rendered from the constants in `eval_runner/task_facts_experiments.py`, the
same ones its oracle applies. `build()` refuses data in which a planted
property did not come out as designed (see `_check`): eight segments and
thirty ad groups, every selection rule deciding at least one segment, no tie
in the budget's remainders, and no product fact that is a substring of
another product's.

    python3 eval_runner/fixtures/launch-workflow-chain/generate.py --write
    python3 eval_runner/fixtures/launch-workflow-chain/generate.py --check

All brands and figures here are invented.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eval_runner import task_facts_experiments as facts  # noqa: E402

# segment_id, segment_code, segment_name, market, type, interest, source, consent, est_size
SEGMENTS = [
    ("S01", "HKR", "US weekend hikers", "US", "prospecting", "tents", "first-party", "opt-in", 182400),
    ("S02", "HKX", "US hikers (partner audience)", "US", "prospecting", "tents", "partner", "", 241000),
    ("S03", "PKR", "US day packers", "US", "prospecting", "packs", "first-party", "opt-in", 133250),
    ("S04", "CKR", "US camp kitchen page visitors", "US", "retargeting", "cook", "first-party", "opt-in", 14820),
    ("S05", "SLP", "US sleep shoppers (bought list)", "US", "prospecting", "sleep", "purchased", "", 310000),
    ("S06", "TRL", "US trail runners", "US", "prospecting", "packs", "first-party", "not recorded", 96000),
    ("S07", "CKP", "US camp cooks (partner audience)", "US", "prospecting", "cook", "partner", "", 54300),
    ("S08", "TNV", "US tent page visitors", "US", "retargeting", "tents", "first-party", "opt-in", 7950),
    ("S09", "HKU", "UK fell walkers", "UK", "prospecting", "tents", "first-party", "opt-in", 98600),
    ("S10", "SLU", "UK cold sleepers (partner audience)", "UK", "prospecting", "sleep", "partner", "", 72400),
    ("S11", "PKU", "UK pack page visitors", "UK", "retargeting", "packs", "first-party", "opt-in", 9310),
    ("S12", "CKU", "UK campsite cooks", "UK", "prospecting", "cook", "first-party", "opt-in", 49800),
    ("S13", "HKW", "UK walkers (partner audience)", "UK", "prospecting", "tents", "partner", "", 98600),
    ("S14", "SLV", "UK sleep page visitors", "UK", "retargeting", "sleep", "first-party", "not recorded", 12000),
    ("S15", "SLD", "DE hut sleepers", "DE", "prospecting", "sleep", "first-party", "opt-in", 88100),
    ("S16", "TND", "DE tent page visitors", "DE", "retargeting", "tents", "first-party", "opt-in", 11640),
    ("S17", "PKD", "DE alpine packers (bought list)", "DE", "prospecting", "packs", "purchased", "", 150000),
    ("S18", "HKA", "AT trekkers (partner audience)", "AT", "prospecting", "tents", "partner", "", 61900),
    ("S19", "HKC", "CA backcountry campers", "CA", "prospecting", "tents", "first-party", "opt-in", 120000),
    ("S20", "PKA", "AU bushwalkers (partner audience)", "AU", "prospecting", "packs", "partner", "", 140000),
    ("S21", "CKD", "DE camp kitchen page visitors", "DE", "retargeting", "cook", "first-party", "opt-in", 10200),
    ("S22", "SLX", "DE sleepers (partner audience)", "DE", "prospecting", "sleep", "partner", "", 79500),
]

# sku, product_name, ad_name, category, status, markets, usd, gbp, eur, proof_1, proof_2, slug
PRODUCTS = [
    ("TN-204", "Ridgeway 2P Tent", "Ridgeway 2P", "tents", "launch", "US;UK;DE", "389", "339", "369",
     "1.9 kg trail weight", "Pitches in 4 minutes", "ridgeway-2p-tent"),
    ("TN-206", "Ridgeway 3P Tent", "Ridgeway 3P", "tents", "launch", "US;UK;DE", "459", "399", "429",
     "Room for three plus packs", "Two doors and two porches", "ridgeway-3p-tent"),
    ("TN-310", "Saltmarsh Tarp Shelter", "Saltmarsh Tarp", "tents", "launch", "US;UK;DE", "179", "155", "169",
     "Packs down to 610 g", "Pitches with trekking poles", "saltmarsh-tarp-shelter"),
    ("TN-412", "Kittiwake Bivy", "Kittiwake Bivy", "tents", "launch", "UK;DE", "", "189", "209",
     "Seam-taped waterproof shell", "Weighs 540 g", "kittiwake-bivy"),
    ("TN-118", "Hollin Dome 2 Tent", "Hollin Dome 2", "tents", "carryover", "US;UK;DE", "249", "219", "239",
     "Freestanding dome design", "Colour-coded pole clips", "hollin-dome-2-tent"),
    ("PK-120", "Corrie 28 Daypack", "Corrie 28", "packs", "launch", "US;UK;DE", "129", "109", "119",
     "Fits a 15-inch laptop", "Rain cover included", "corrie-28-daypack"),
    ("PK-140", "Corrie 40 Pack", "Corrie 40", "packs", "launch", "US;UK;DE", "189", "165", "179",
     "Adjustable back length", "Weighs 1.3 kg", "corrie-40-pack"),
    ("PK-165", "Tarn 65 Trekking Pack", "Tarn 65", "packs", "launch", "US;DE", "279", "", "259",
     "Carries 20 kg in comfort", "Twin hip-belt pockets", "tarn-65-trekking-pack"),
    ("PK-090", "Scree Hip Pack", "Scree Hip Pack", "packs", "launch", "US;UK", "49", "42", "",
     "Holds two 500 ml flasks", "Reflective trim all round", "scree-hip-pack"),
    ("PK-075", "Bracken 22 Daypack", "Bracken 22", "packs", "discontinued", "US;UK", "89", "79", "",
     "Ventilated mesh back", "Stretch side bottle pockets", "bracken-22-daypack"),
    ("SL-301", "Lowfell Down Quilt", "Lowfell Quilt", "sleep", "launch", "US;UK;DE", "319", "279", "299",
     "650-fill responsible down", "Packs into a 6 litre sack", "lowfell-down-quilt"),
    ("SL-305", "Lowfell Synthetic Bag", "Lowfell Synthetic", "sleep", "launch", "US;UK;DE", "189", "159", "175",
     "Stays warm when damp", "Full-length two-way zip", "lowfell-synthetic-bag"),
    ("SL-320", "Gorse Air Mat", "Gorse Air Mat", "sleep", "launch", "US;UK;DE", "149", "129", "139",
     "R-value of 4.2", "Inflates in 12 breaths", "gorse-air-mat"),
    ("SL-330", "Gorse Camp Pillow", "Gorse Pillow", "sleep", "launch", "UK;DE", "", "29", "32",
     "Packs smaller than a fist", "Weighs 85 g", "gorse-camp-pillow"),
    ("SL-210", "Moorland Sleeping Bag", "Moorland Bag", "sleep", "carryover", "US;UK;DE", "149", "125", "135",
     "Insulated draught collar", "Comes with a compression sack", "moorland-sleeping-bag"),
    ("CK-501", "Emberline Stove", "Emberline Stove", "cook", "launch", "US;UK;DE", "89", "79", "85",
     "Boils a litre in 3.5 minutes", "Folds to fit inside its pot", "emberline-stove"),
    ("CK-505", "Emberline Pot Set", "Emberline Pot Set", "cook", "launch", "US;UK;DE", "69", "59", "65",
     "Hard-anodised aluminium", "Two pots and a lid-pan", "emberline-pot-set"),
    ("CK-520", "Brook Filter Bottle", "Brook Bottle", "cook", "launch", "US;UK", "45", "39", "",
     "Filter lasts 1500 litres", "Fits standard bottle cages", "brook-filter-bottle"),
    ("CK-530", "Cinder Titanium Mug", "Cinder Mug", "cook", "launch", "US;DE", "25", "", "23",
     "Double-wall titanium", "Holds 450 ml", "cinder-titanium-mug"),
    ("CK-480", "Spark Gas Lighter", "Spark Lighter", "cook", "discontinued", "US;UK;DE", "15", "12", "14",
     "Lights in gusty wind", "Refills from a gas can", "spark-gas-lighter"),
]


def _csv(header: tuple[str, ...], rows: list[tuple]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _money(value: int) -> str:
    return f"${value:,}"


def brief() -> str:
    markets = ", ".join(facts.CHAIN_MARKETS[:-1]) + " and " + facts.CHAIN_MARKETS[-1]
    pro, rtg = facts.CHAIN_MIN_SIZE["prospecting"], facts.CHAIN_MIN_SIZE["retargeting"]
    stores = facts.CHAIN_STORES
    signs = facts.CHAIN_CURRENCY
    return f"""# Fennick Trailworks: Fellside collection launch, paid social build brief

Fennick Trailworks launches its new Fellside collection on paid social on
2 March 2027. This brief is the build standard for the launch account. The
build has six steps, and each one uses what the steps before it produced:
the segments chosen in step 1 become the campaigns of step 2, the ad groups
of step 2 get the ads of step 3, the URLs of step 4 and the budgets of step
5, and step 6 counts what was built. Two files come with this brief:
`audience_segments.csv` (every audience the team could target) and
`product_catalogue.csv` (every product in the range). Build exactly what the
steps produce. Names are case-sensitive.

## Step 1. Choose the audience segments

Apply these rules to `audience_segments.csv`, in this order:

1. Launch markets only: {markets}. A segment in any other market is out.
2. No purchased lists: a segment whose source is `purchased` is out.
3. Consent: a `first-party` segment needs consent `opt-in`; with any other
   value it is out. A `partner` segment carries the partner's consent and
   needs nothing in our consent column.
4. Minimum size: a prospecting segment needs an est_size of at least
   {pro:,}; a retargeting segment at least {rtg:,}.
5. Duplicates: when two segments still in have the same market, type and
   interest, keep the one with the larger est_size; if they are the same
   size, keep the one with the lower segment_id.
6. Caps per market: each market runs at most
   {facts.CHAIN_CAP["prospecting"]} prospecting segments and
   {facts.CHAIN_CAP["retargeting"]} retargeting segment. If more are still
   in, keep the largest by est_size (same size: the lower segment_id).

Each segment chosen becomes one campaign.

## Step 2. Build the campaigns and ad groups

- One campaign per chosen segment, named
  `{facts.CHAIN_PREFIX}_<market>_<segment_code>_<type code>`, where the type
  code is `{facts.CHAIN_TYPE_CODE["prospecting"]}` for prospecting and
  `{facts.CHAIN_TYPE_CODE["retargeting"]}` for retargeting. Example:
  `{facts.CHAIN_PREFIX}_US_ABC_{facts.CHAIN_TYPE_CODE["prospecting"]}`.
- In each campaign, one ad group for every product in the catalogue whose
  status is `launch`, whose category is the segment's interest, and whose
  markets include the segment's market. Nothing else gets an ad group:
  carryover and discontinued products, and products not sold in the
  campaign's market, are left out.
- Ad group name: the campaign name, an underscore, and the product's sku
  exactly as the catalogue writes it. Example:
  `{facts.CHAIN_PREFIX}_US_ABC_{facts.CHAIN_TYPE_CODE["prospecting"]}_XX-000`.

## Step 3. Write one ad per ad group

- Three fields: headline_1 (at most {facts.CHAIN_LIMITS["headline_1"]}
  characters), headline_2 (at most {facts.CHAIN_LIMITS["headline_2"]}) and
  description (at most {facts.CHAIN_LIMITS["description"]}). Spaces and
  punctuation count as characters.
- headline_1 contains the product's ad_name, word for word.
- headline_2 contains one of the product's two proof points (proof_1 or
  proof_2), word for word.
- description contains the product's price in the campaign's market with its
  currency sign, written as the catalogue gives it: {signs["US"][0]} and
  {signs["US"][1]} for US, {signs["UK"][0]} and {signs["UK"][1]} for UK,
  {signs["DE"][0]} and {signs["DE"][1]} for DE (for example
  {signs["UK"][0]}129).
- Retargeting ads only: the description also carries the returning-visitor
  code {facts.CHAIN_CODE}. Prospecting ads carry no code.
- Only the ad group's own product: an ad names no other product of the
  catalogue (by its ad_name or product_name), uses no other product's proof
  point, and contains no figure except those in its own product's ad_name,
  proof points and price in the campaign's market (and, in a retargeting
  ad, the code). No dates, no percentages, no other market's price.

## Step 4. Build the trafficking sheet

- One final URL per ad group.
- Landing page: `{facts.CHAIN_DOMAIN}/<store>/<slug>`, where the store is
  `{stores["US"]}` for US, `{stores["UK"]}` for UK and `{stores["DE"]}` for
  DE, and the slug is the product's slug from the catalogue.
- Exactly four tracking parameters: `utm_source={facts.CHAIN_UTM_SOURCE}`,
  `utm_medium={facts.CHAIN_UTM_MEDIUM}`, `utm_campaign=` the campaign name in
  lower case, and `utm_content=` the ad group name in lower case.

## Step 5. Set the daily budgets

- The launch's total daily budget is {_money(facts.CHAIN_TOTAL_BUDGET)}, in
  US dollars for every market (the account bills in dollars), split across
  the campaigns and nothing else.
- Every campaign first gets {_money(facts.CHAIN_FLOOR)}.
- The rest ({_money(facts.CHAIN_TOTAL_BUDGET)} less
  {_money(facts.CHAIN_FLOOR)} for each campaign) is shared in proportion to
  each campaign's segment est_size, in whole dollars: each campaign gets the
  whole-dollar part of its share, and the dollars left over go one each to
  the campaigns with the largest fractional parts (a tie goes to the
  campaign whose name sorts first).
- The amounts add up to {_money(facts.CHAIN_TOTAL_BUDGET)} exactly.

## Step 6. Pre-launch check

Before anything goes live, count from the files you built: the campaigns,
the ad groups, the ads carrying the returning-visitor code, the distinct
products advertised, and the total of the daily budgets.
"""


def build() -> dict[str, str]:
    segments = _csv(
        ("segment_id", "segment_code", "segment_name", "market", "type", "interest", "source", "consent", "est_size"),
        SEGMENTS,
    )
    products = _csv(
        ("sku", "product_name", "ad_name", "category", "status", "markets", "price_usd", "price_gbp",
         "price_eur", "proof_1", "proof_2", "slug"),
        PRODUCTS,
    )
    files = {
        "campaign_brief.md": brief(),
        "audience_segments.csv": segments,
        "product_catalogue.csv": products,
    }
    _check(files)
    return files


def _check(files: dict[str, str]) -> None:
    table = facts.chain_segments_table(files["audience_segments.csv"])
    catalogue = facts.chain_catalogue(files["product_catalogue.csv"])
    reference = facts.chain_reference(files)
    chosen = [row["segment_id"] for row in reference["segments"]]
    assert chosen == ["S02", "S03", "S04", "S09", "S10", "S11", "S15", "S16"], chosen
    assert len(reference["structure"]) == 30, len(reference["structure"])
    assert reference["answers"] == {1: 8, 2: 30, 3: 11, 4: 16, 5: facts.CHAIN_TOTAL_BUDGET}
    # Every rule of step 1 keeps out a segment that the rules before it let in.
    out_by = {
        "market": {"S18", "S19", "S20"}, "purchased": {"S05", "S17"}, "consent": {"S06", "S14"},
        "size": {"S08", "S12"}, "duplicate": {"S01", "S13", "S22"}, "cap": {"S07", "S21"},
    }
    before = {row["segment_id"] for row in table}
    for rule, left in facts.chain_selection_stages(table):
        after = {row["segment_id"] for row in left}
        assert before - after == out_by[rule], (rule, before - after)
        before = after
    # The budget's remainders never tie, so the largest-remainder order is unique.
    remainders = [share - int(share) for _name, share in facts.chain_budget_shares(reference["segments"])]
    assert len(set(remainders)) == len(remainders)
    assert sum(reference["budget"].values()) == facts.CHAIN_TOTAL_BUDGET
    # No product fact is inside another product's, so "another product's fact" is unambiguous,
    # and every ad's required parts fit the limits with room to spare.
    texts = {
        sku: [facts._fold(p[key]) for key in ("ad_name", "product_name", "proof_1", "proof_2")]
        for sku, p in catalogue.items()
    }
    for sku, own in texts.items():
        for other_sku, other in texts.items():
            if sku != other_sku:
                assert not any(a in b for a in other for b in own), (sku, other_sku)
    for row in reference["structure"]:
        product = catalogue[row["sku"]]
        assert len(product["ad_name"]) <= 20 and max(len(product["proof_1"]), len(product["proof_2"])) <= 28
        market = next(s["market"] for s in table if s["segment_id"] == row["segment_id"])
        assert product[facts.CHAIN_CURRENCY[market][1]], row
    for sku, product in catalogue.items():  # a product's three prices are three different figures
        prices = [product[column] for _sign, column in facts.CHAIN_CURRENCY.values() if product[column]]
        assert len(set(prices)) == len(prices), sku


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    built = build()
    stale = [name for name, text in built.items() if not (HERE / name).exists() or (HERE / name).read_text() != text]
    if args.write:
        for name, text in built.items():
            (HERE / name).write_text(text)
        print(f"wrote {len(built)} files")
        return 0
    if stale:
        print("out of date: " + ", ".join(stale))
        return 1
    print("up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
