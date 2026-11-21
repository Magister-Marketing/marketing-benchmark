#!/usr/bin/env python3
"""Write, or check, the sources of the brief-amendment task.

The task is two messages. The earlier one is the signed-off launch brief
(`original_brief()`, the task file's `decoy.message`) with its product sheet
(`original/product_sheet.csv`, the `decoy.fixture`), sent "for reference, the
request follows". The task prompt then supplies the client's amendment
(`amendment.md`). Both texts are rendered from the constants in
`eval_runner/task_facts_experiments.py` that its oracle applies, and
`build()` refuses data in which a planted consequence did not come out as
designed (see `_check`).

    python3 eval_runner/fixtures/brief-amendment/generate.py --write
    python3 eval_runner/fixtures/brief-amendment/generate.py --check

All brands, people and figures here are invented.
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

# item_id, item_name, ad_name, kind, bundle_items, markets, usd, gbp, eur, claim_1, claim_2
SHEET = [
    ("P01", "Brightwell Kettle BK-17", "Brightwell Kettle", "product", "", "US;UK;IE", "89", "79", "85",
     "Boils a full jug in three minutes", "Keeps water hot for half an hour"),
    ("P02", "Brightwell Stand Mixer SM-500", "Brightwell Stand Mixer", "product", "", "US;UK", "249", "219", "",
     "Ten speeds and a pulse setting", "Five-litre steel bowl"),
    ("P03", "Brightwell Toaster BT-4", "Brightwell Toaster", "product", "", "US;UK;IE", "79", "69", "75",
     "Browns evenly on both sides", "Extra-wide slots for bagels"),
    ("P04", "Brightwell Hand Blender HB-2", "Brightwell Hand Blender", "product", "", "US;UK;IE", "59", "49", "55",
     "Dishwasher-safe blending shaft", "Five speeds plus turbo"),
    ("P05", "Brightwell Juicer CJ-1", "Brightwell Juicer", "product", "", "US;UK", "129", "109", "",
     "Dishwasher-safe parts", "Cold-press keeps the pulp out"),
    ("P06", "Brightwell Coffee Machine CM-15", "Brightwell Coffee Machine", "product", "", "US;UK", "239", "209", "",
     "Barista pressure at 15 bar", "Steam wand for silky milk"),
    ("P07", "Brightwell Coffee Grinder CG-40", "Brightwell Coffee Grinder", "product", "", "US;UK;IE", "99", "85", "95",
     "Forty grind settings", "Dishwasher-safe hopper"),
    ("P08", "Brightwell Milk Frother MF-3", "Brightwell Milk Frother", "product", "", "US;IE", "49", "", "45",
     "Hot or cold foam in 90 seconds", "Non-stick jug"),
    ("B01", "Brightwell Breakfast Set BS-3", "Brightwell Breakfast Set", "bundle", "P01;P03;P07", "US;UK", "229", "199", "",
     "Three matching appliances in one box", "Brushed-steel finish throughout"),
]


def _csv(header: tuple[str, ...], rows: list[tuple]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _day(iso: str, weekday: bool = True) -> str:
    day = facts._iso(iso)
    return (day.strftime("%A ") if weekday else "") + f"{day.day} {day.strftime('%B %Y')}"


def _holiday_lines() -> str:
    lines = []
    for market, days in facts.AMEND_HOLIDAYS.items():
        names = ", ".join(f"{facts._iso(day).day} {facts._iso(day).strftime('%B')}" for day in days)
        lines.append(f"- {market}: {names}.")
    return "\n".join(lines)


def original_brief() -> str:
    """The earlier message: the brief as signed off, sent for reference."""
    brief = facts.AMEND_BRIEF
    us, uk = brief["budget"]["US"], brief["budget"]["UK"]
    total = us + uk
    signs = facts.AMEND_SIGNS
    teaser, launch, reminder = facts.AMEND_EMAILS
    return f"""Here is the Brightwell launch brief we signed off on {_day(brief["signed_off"], False)}, with the product sheet attached. This is for reference only, so no work on it yet: the request follows in my next message.

# Pellmore Kitchen: Brightwell range launch brief

Signed off {_day(brief["signed_off"], False)}.

## The launch

Pellmore Kitchen launches its Brightwell range of small kitchen appliances on {_day(brief["launch"])} in two markets, the US and the UK (market codes US and UK). Launch day is the same in every market.

## What runs where

- Every item on the product sheet, product or bundle, runs in each launch market its `markets` column lists, and nowhere else.
- A bundle is sold only while every item in it (its `bundle_items`) is in the launch. If any of its items is withdrawn, the bundle is withdrawn in every market, with its ads, and nothing takes its place.

## Ads

- One ad per item for each market it runs in. Its ad_id is the market code, a hyphen and the item_id (for example US-P02).
- Headline: the item's ad_name, exactly.
- Claim: the item's claim_1, word for word. If claim_1 may not be used, the ad uses claim_2 instead.
- Price: the item's price in the market's currency, as a whole number after its sign: {signs["US"][0]} from {signs["US"][1]} in the US, {signs["UK"][0]} from {signs["UK"][1]} in the UK, {signs["IE"][0]} from {signs["IE"][1]} in any euro market. Every price in the plan is the price in effect on the launch date: a price change counts only if it is already in effect on launch day.
- Paid ads run in every market for {facts.AMEND_FLIGHT_DAYS} days from the launch date: ads_start is the launch date and ads_end is the {facts.AMEND_FLIGHT_DAYS}th day (the launch date plus {facts.AMEND_FLIGHT_DAYS - 1} days).

## Emails

Each market gets three emails: a teaser {-teaser[1]} days before the launch date, a launch email on the launch date and a reminder {reminder[1]} days after it. An email whose date falls on a Saturday, a Sunday or a holiday of its own market goes out on the closest earlier day that is none of those.

- Teaser subject: {facts.AMEND_SUBJECTS["teaser"].format(date="<launch date>")}, with the launch date written as the day without a leading zero and the month in full (for example {_day(brief["launch"], False).rsplit(" ", 1)[0]}).
- Launch email subject: {facts.AMEND_SUBJECTS["launch"].format(featured="<featured item's ad_name>")}
- Reminder subject: {facts.AMEND_SUBJECTS["reminder"].format(featured="<featured item's ad_name>")}
- The featured item is the market's bundle. A market with no bundle features its highest-priced product, at the price in effect on launch day (a tie goes to the lower item_id).

## Holidays in 2027 in Pellmore's markets

Only these count:

{_holiday_lines()}

## Budget

The paid media budget is ${total:,}, held in US dollars: ${us:,} for the US and ${uk:,} for the UK. A market's budget pays for its paid ads only.

## What we need from you

When the request comes: the launch plan for each market, the email schedule and the ad sheet, ready to build."""


def amendment() -> str:
    changes = facts.AMEND_CHANGES
    sheet = {row[0]: row for row in SHEET}
    rise, later = changes["prices"]
    banned = changes["banned_claim"]
    return f"""From: Ines Calloway, Marketing Lead, Pellmore Kitchen
Sent: {_day(changes["sent"])}
Subject: Brightwell launch: changes to the signed-off brief

Hi both,

Some changes to the Brightwell brief we signed off on {_day(facts.AMEND_BRIEF["signed_off"], False)}. Anything not listed here stays exactly as signed off.

1. Launch date. Our retail partner's stock is arriving late, so the launch moves from {_day(facts.AMEND_BRIEF["launch"])} to {_day(changes["launch"])}.
2. Kettle. The {sheet[changes["withdrawn"]][2]} ({changes["withdrawn"]}) has not cleared its electrical certification in time and is withdrawn from the launch in every market.
3. Coffee machine price. From {_day(rise[3], False)} the US price of the {sheet[rise[0]][2]} ({rise[0]}) is ${rise[2]}; it was ${sheet[rise[0]][6]}.
4. Toaster price. From {_day(later[3], False)} the UK price of the {sheet[later[0]][2]} ({later[0]}) goes up to £{later[2]}; it is £{sheet[later[0]][7]} until then.
5. Ireland. Please add Ireland (market code {changes["added_market"]}) to the launch, at the EUR prices on the product sheet and with the items the sheet lists for {changes["added_market"]}. Fund it with ${changes["added_budget"]:,} moved from the {changes["budget_from"]} budget.
6. Claims. Legal has asked us to stop using the claim "{banned}", in any wording, until the new test reports are in.

Thanks,
Ines
"""


def build() -> dict[str, str]:
    files = {
        facts.AMEND_FIXTURE: amendment(),
        facts.AMEND_SHEET: _csv(
            ("item_id", "item_name", "ad_name", "kind", "bundle_items", "markets", "price_usd", "price_gbp",
             "price_eur", "claim_1", "claim_2"),
            SHEET,
        ),
    }
    _check(files)
    return files


def _check(files: dict[str, str]) -> None:
    reference = facts.amend_reference(files[facts.AMEND_SHEET])
    final, original = reference["final"], reference["original"]
    assert reference["bundles_lost"] == ["B01"]
    assert reference["claim_ads"] == [("IE", "P04"), ("UK", "P04"), ("UK", "P05"), ("US", "P04"), ("US", "P05")]
    assert reference["price_rises"] == [("US", "P06")] and reference["prices_not_yet"] == [("UK", "P03")]
    # The launch date breaks one dependency the amendment does not mention: the
    # UK teaser lands on Good Friday, which only the UK keeps as a holiday.
    assert reference["holiday_moves"] == [("UK", "teaser")]
    assert final["emails"][("UK", "teaser")]["send_date"].isoformat() == "2027-03-25"
    assert all(email["send_date"] == facts._iso(facts.AMEND_BRIEF["launch"]) + facts.dt.timedelta(days=dict(facts.AMEND_EMAILS)[key[1]])
               for key, email in original["emails"].items())
    # Without the bundle, each market features a different product, and in the
    # US only the price rise makes it the coffee machine.
    assert {m: final["emails"][(m, "launch")]["featured"] for m in final["markets"]} == {"US": "P06", "UK": "P02", "IE": "P07"}
    assert {m: original["emails"][(m, "launch")]["featured"] for m in original["markets"]} == {"US": "B01", "UK": "B01"}
    without_rise = facts.amend_plan(reference["sheet"], dict(facts.AMEND_CHANGES, prices=()))
    assert without_rise["emails"][("US", "launch")]["featured"] == "P02"
    # The May price is a look-alike: it does not reach the plan.
    assert final["ads"][("UK", "P03")]["price"] == "£69"
    assert len(final["ads"]) == 17 and len(reference["kept_fields"]) == 13
    # Every ad the amendment reaches differs from the signed-off one, so the
    # signed-off plan scores nothing on what the amendment changes.
    for key in reference["claim_ads"] + reference["price_rises"]:
        assert original["ads"].get(key) != final["ads"][key], key


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
            (HERE / name).parent.mkdir(parents=True, exist_ok=True)
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
