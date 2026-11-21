#!/usr/bin/env python3
"""Write, or check, the fixtures of the strategy tasks.

Tasks: channel-budget-allocation, competitor-comparison, launch-timeline.

Deterministic: every table and page is written out below from constants, so
re-running reproduces identical bytes. The answers are not here: the oracle in
`eval_runner/task_facts_strategy.py` computes them from the files this writes,
and `tests/test_tasks_strategy.py` recomputes them again with separate code.

All brands, people, prices and figures are invented.

    python3 scripts/gen_tasks_strategy.py --write   # (re)write the fixtures
    python3 scripts/gen_tasks_strategy.py --check   # report drift, change nothing
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "eval_runner" / "fixtures"


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


# ─────────────────────────────────────────────── channel-budget-allocation

BUDGET_DIR = "channel-budget"
QUARTER_BUDGET = 128_000
BLOCK_USD = 5_000
AE_CAPACITY = 520

# (id, description, max blocks, minimum blocks if used, committed blocks,
#  fee per month in dollars, routed to the account executives)
CHANNELS = [
    ("search", "Google Ads search, non-brand keywords", 10, 0, 0, 0, "no"),
    ("linkedin", "LinkedIn Ads sponsored content to the target-account list", 8, 0, 0, 0, "yes"),
    ("webinars", "Monthly webinar series promoted to the house list and partner lists", 5, 0, 0, 1400, "yes"),
    ("syndication", "Content syndication of the clinic benchmark report through a B2B publisher network", 8, 4, 0, 0, "no"),
    ("review_sites", "Paid profile and lead program on software review marketplaces", 4, 0, 2, 0, "no"),
    ("meta", "Meta retargeting of site visitors and trial drop-offs", 6, 0, 0, 0, "no"),
]

# Leads each successive $5,000 block adds, strictly decreasing within a channel.
ADDED_LEADS = {
    "search": [142, 129, 117, 106, 96, 87, 79, 72, 66, 58],
    "linkedin": [101, 91, 84, 77, 70, 62, 55, 49],
    "webinars": [153, 124, 97, 73, 51],
    "syndication": [89, 80, 46, 37, 31, 26, 22, 19],
    "review_sites": [41, 33, 25, 19],
    "meta": [118, 99, 83, 68, 53, 41],
}


def budget_terms_csv() -> str:
    return _csv_text(
        ["channel", "description", "max_blocks", "minimum_if_used_blocks", "committed_blocks",
         "fee_usd_per_month", "routed_to_aes"],
        [list(channel) for channel in CHANNELS],
    )


def budget_forecasts_csv() -> str:
    rows = []
    for channel, *_rest in CHANNELS:
        for block, leads in enumerate(ADDED_LEADS[channel], 1):
            rows.append([channel, block, block * BLOCK_USD, leads])
    return _csv_text(["channel", "block", "spend_through_block_usd", "added_leads"], rows)


def budget_constraint_names() -> list[str]:
    names = ["budget", "ae_capacity"]
    for channel, _description, _max, minimum, committed, _fee, _routed in CHANNELS:
        if minimum:
            names.append(f"{channel}_min_order")
        if committed:
            names.append(f"{channel}_commitment")
        names.append(f"{channel}_max")
    return names


def budget_brief_md() -> str:
    routed = [channel for channel, *_rest, flag in CHANNELS if flag == "yes"]
    maxima = ", ".join(f"`{channel}_max`" for channel, *_rest in CHANNELS)
    syndication_min = next(minimum for channel, _d, _m, minimum, *_r in CHANNELS if channel == "syndication")
    review_committed = next(committed for channel, _d, _m, _n, committed, *_r in CHANNELS if channel == "review_sites")
    names = ", ".join(f"`{name}`" for name in budget_constraint_names())
    return f"""# Fernmoor: Q2 2027 demand budget, planning brief

From Ines Varga, Head of Demand Generation. Fernmoor sells practice-management
software to physiotherapy clinics. This brief sets the rules for splitting next
quarter's demand budget across our six paid channels. The two files beside it
are `channel_terms.csv` (each channel's limits and fees) and
`channel_forecasts.csv` (the leads each block of spend is projected to bring).

## The money

- **Quarter budget:** ${QUARTER_BUDGET:,}. Everything the plan buys comes out of it: media blocks
  and channel fees. The plan may not go over it. Money left over stays unspent.
- **Blocks:** spend is bought in whole blocks of ${BLOCK_USD:,}. A channel's blocks are bought in
  order: block 1, then block 2, and so on.
- **Forecasts:** `added_leads` in `channel_forecasts.csv` is the number of qualified leads that
  block adds on top of the channel's earlier blocks. A channel's projected leads for n blocks are
  the sum of its first n rows. `spend_through_block_usd` is the media spend once that block is
  bought.
- **Fees:** `fee_usd_per_month` is a licence the channel needs for every month of the quarter in
  which it runs. A channel that buys any block runs for the whole quarter, so it pays three months
  of its fee. A channel that buys no block pays nothing.

## Channel terms

- `max_blocks`: the most blocks the channel can take this quarter.
- `minimum_if_used_blocks`: if the channel is used at all, it must buy at least this many blocks.
  0 means there is no minimum.
- `committed_blocks`: blocks already contracted for this quarter. The plan must buy at least this
  many.
- `routed_to_aes`: whether the channel's leads go to the account executives.

## Account executive capacity

Leads from the channels routed to the AEs ({" and ".join(routed)}) ask for a demo and go to our
four account executives, who can take at most **{AE_CAPACITY} new leads** this quarter in total. The
projected leads of the routed channels together may not exceed {AE_CAPACITY}. Leads from the other
channels go to the self-serve trial and do not count against it.

## What I need

The split of the budget that projects the most leads while keeping every rule above. If two splits
project the same number of leads, take the one that costs less.

## Constraints, by name

For each of these constraints, say whether it binds in your split: {names}.

- `budget` binds when less than ${BLOCK_USD:,} of the quarter budget is left unspent.
- `ae_capacity` binds when at least one routed channel is below its maximum and, for every routed
  channel that is below its maximum, buying its next block would take the routed leads above
  {AE_CAPACITY}.
- {maxima}: each binds when that channel buys exactly its `max_blocks`.
- `syndication_min_order` binds when syndication buys exactly its minimum order ({syndication_min} blocks).
- `review_sites_commitment` binds when review sites buy exactly their committed blocks ({review_committed}).
"""


def budget_fixtures() -> dict[str, str]:
    return {
        f"{BUDGET_DIR}/planning_brief.md": budget_brief_md(),
        f"{BUDGET_DIR}/channel_terms.csv": budget_terms_csv(),
        f"{BUDGET_DIR}/channel_forecasts.csv": budget_forecasts_csv(),
    }


# ───────────────────────────────────────────────────────────────── all of them

def planned() -> dict[Path, str]:
    """Every generated file, by its path in the repository."""
    files: dict[str, str] = {}
    files.update(budget_fixtures())
    return {FIXTURES / name: text for name, text in files.items()}


def drift() -> list[str]:
    return [
        f"{path.relative_to(REPO_ROOT)}: {'missing' if not path.exists() else 'differs from what the generator writes'}"
        for path, text in planned().items()
        if not path.exists() or path.read_text() != text
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        for path, text in planned().items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        print(f"wrote {len(planned())} file(s)")
        return 0
    problems = drift()
    for problem in problems:
        print(problem)
    print("ok" if not problems else f"{len(problems)} file(s) out of date: run with --write")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
