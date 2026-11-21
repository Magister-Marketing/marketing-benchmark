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


# ───────────────────────────────────────────────────────────── competitor-comparison

COMPARISON_DIR = "competitor-comparison"

# The pages, as a product marketer saved them from each site on the same day.
# Ours is first. Each is written out in full: what a page states, and what it
# leaves out, is the task.
COMPANY_PAGES = {
    "tallyhour": """\
# Tallyhour pricing

Time tracking and invoicing for agencies and studios. Prices are per user per month.

| | Free | Studio | Agency |
|---|---|---|---|
| Billed monthly | $0 | $21 | $34 |
| Billed annually | $0 | $17.50 | $28 |
| Users | 1 | From 1 | From 5 |
| Time tracking and timesheets | ✓ | ✓ | ✓ |
| Invoices from tracked time | — | ✓ | ✓ |
| API access | — | ✓ | ✓ |
| Single sign-on (SAML) | — | ✓ | ✓ |
| EU data hosting | — | ✓ | ✓ |

The Free plan is free for as long as you use it: one person, unlimited projects.

Every paid plan starts with a 21-day free trial. No card needed.

## Reliability

Studio and Agency come with a 99.9% uptime SLA.

## FAQ

**Can I switch between monthly and annual billing?**
Yes, at any time from the billing page.
""",
    "brisktime": """\
# Brisktime plans and pricing

Brisktime keeps timesheets, approvals and invoices in one place, and it is built for teams that
take security seriously: single sign-on, SCIM provisioning and audit logs.

| | Starter | Business |
|---|---|---|
| Price per user per year | $276 | $420 |
| Billing | Annual only | Annual only |
| Minimum seats | 3 | 10 |
| Timesheets and approvals | ✓ | ✓ |
| Invoicing | ✓ | ✓ |
| Expense tracking | — | ✓ |
| API access | — | ✓ |
| Single sign-on (SAML) and SCIM | — | ✓ |
| Audit logs | — | ✓ |
| Uptime SLA | 99.5% | 99.5% |

## Where your data lives

All Brisktime data is hosted in our US data centres. EU hosting is not available.

## FAQ

**Is there a free trial?**
Yes. Try either plan free for 7 days.

**Can I pay monthly?**
No. Brisktime plans are billed once a year.
""",
    "quillhour": """\
# Quillhour pricing

Plan, track and bill client work. Save 17% with annual billing.

| | Team | Pro | Enterprise |
|---|---|---|---|
| Billed annually, per user per month | $19 | $27 | Contact sales |
| Billed monthly, per user per month | $23 | $32 | Contact sales |
| Minimum users | 2 | 2 | 25 |
| Time tracking | ✓ | ✓ | ✓ |
| Invoicing | ✓ | ✓ | ✓ |
| API access | ✓ | ✓ | ✓ |
| SAML single sign-on | — | — | ✓ |
| EU data residency | ✓ | ✓ | ✓ |

Quillhour has no free plan. Team and Pro come with a 14-day free trial.

## FAQ

**What is the smallest team I can sign up?**
Team and Pro now start at 3 users. We raised the minimum in September.

**Do you publish uptime?**
Our status page shows the last 90 days of uptime for every service.
""",
    "ticklog": """\
# Ticklog pricing

Timesheets for professional-services firms. All prices are per user per month, billed monthly.

| Plan | Basic | Pro | Enterprise |
|---|---|---|---|
| Price | $24 | $33 | $45 |
| Minimum users | 5 | 5 | 20 |
| Time tracking | ✓ | ✓ | ✓ |
| Invoicing from timesheets | — | ✓ | ✓ |
| REST API | — | ✓ | ✓ |
| SAML single sign-on | — | — | ✓ |
| Uptime SLA | — | — | 99.95% |

Ticklog has no free plan and no free trial. Book a 30-minute demo and we will set up a sandbox
with your own projects.

## FAQ

**Is the REST API included on Basic?**
Yes. Since October every Ticklog plan includes the REST API.

**Can I get a discount for paying yearly?**
Yes, ask your account manager.
""",
    "fenwork": """\
# Fenwork pricing

Time tracking, budgets and invoicing for agencies. Prices are per user per month, billed monthly.
Pay yearly and get two months free.

| | Essentials | Growth | Scale |
|---|---|---|---|
| Price | $22 | $30 | $39 |
| Free trial | 14 days | 14 days | 14 days |
| Time tracking | ✓ | ✓ | ✓ |
| Invoicing | ✓ | ✓ | ✓ |
| API access | ✓ | ✓ | ✓ |
| Single sign-on | — | ✓ | ✓ |
| 99.9% uptime SLA | — | ✓ | ✓ |

Every plan lets you choose EU or US hosting for your workspace.

## FAQ

**How long is the free trial?**
Since March every plan comes with a 30-day free trial.

**Is there a free plan?**
No. The trial gives you every feature of Scale instead.
""",
    "larchpoint": """\
# Larchpoint Time pricing

Timesheets, approvals and client invoicing.

| | Core | Scale |
|---|---|---|
| Per user per month, billed monthly | $29 | $48 |
| Per user per year, billed yearly | $290 | $480 |
| Users | From 1 | From 10 |
| Timesheets and approvals | ✓ | ✓ |
| Client invoicing | ✓ | ✓ |
| Single sign-on through your identity provider | — | ✓ |
| Uptime SLA | 99.5% | 99.9% |

Larchpoint has no free plan. Start with a 14-day free trial; every paid subscription also carries
a 30-day money-back guarantee.

All Larchpoint data is stored in our US region. We do not offer EU hosting.
""",
}

COMPARISON_CLAIMS = [
    "Tallyhour's entry plan costs less per user per month than any competitor's entry plan.",
    "Tallyhour is the only one of the six with a free plan.",
    "Tallyhour's 21-day free trial is the longest of the six.",
    "Tallyhour includes single sign-on on its entry plan, and no competitor includes it on theirs.",
    "Tallyhour's top plan costs less per user per month than any competitor's top plan.",
]


def comparison_brief_md() -> str:
    pages = ", ".join(f"`{name}.md`" for name in COMPANY_PAGES)
    claims = "\n".join(f"{number}. {claim}" for number, claim in enumerate(COMPARISON_CLAIMS, 1))
    return f"""# Tallyhour: competitor comparison, brief

From Priya Raman, product marketing. Tallyhour sells time tracking and invoicing to agencies. Sales
wants one comparison table of us and our five closest competitors, and I want to know which of our
draft claims the table can back. The six pricing pages were saved from the sites today: {pages}.

## The attributes

One row per company, one column per attribute:

- `free_plan`: whether the company offers a plan that is free with no time limit. A free trial is
  not a free plan.
- `trial_days`: the length of the free trial in days, and 0 when the page says there is no free
  trial. A money-back guarantee is not a free trial.
- `entry_plan`: the name of the entry plan, the cheapest plan with a price above $0, as the page
  names it.
- `entry_price_usd`: the entry plan's price per user per month, on a monthly basis (below).
- `entry_min_users`: the fewest users the entry plan can be bought for.
- `sso_on_entry`: whether the entry plan includes single sign-on.
- `sso_cheapest_plan`: the name of the cheapest plan that includes single sign-on.
- `invoicing_on_entry`: whether the entry plan includes invoicing.
- `api_on_entry`: whether the entry plan includes API access.
- `top_plan_price_usd`: the price per user per month, on a monthly basis, of the top plan: the
  plan listed last in the company's plan table.
- `uptime_sla_percent`: the highest uptime the company commits to in a service-level agreement,
  on any plan, as a percentage.
- `eu_hosting`: whether customer data can be hosted in the EU, on any plan.

## Rules for every cell

1. A cell holds the value the company's own page states, or exactly `not stated` when the page
   does not state it. Do not infer a value from what a page leaves out: a feature or a plan the
   page does not mention is `not stated`, not `no`.
2. In a plan table a check mark (✓) means the plan includes it and a dash (—) means it does not.
3. A price the page replaces with "Contact sales", "custom" or a quote is `not stated`.
4. Monthly basis: when a plan has a price billed monthly, that is its price, even if the page
   also gives a lower price for annual billing. When a plan is sold only on annual billing, its
   price is its price per user per year divided by 12, rounded to the cent.
5. Each page's FAQ was updated after its plan table. Where a page's FAQ and its plan table
   disagree, the FAQ is right.
6. Write yes or no as `yes` or `no`, a price in US dollars with two decimals and no currency sign,
   a percentage without the % sign, a number of days or users as a whole number, and a plan by
   its name alone.

## The draft claims

{claims}

A claim is `supportable` when the table's cells prove it and `not supportable` otherwise. A claim
that something holds for every competitor, or that no competitor has something, needs every
competitor's cell: a `not stated` cell cannot support it. "Less" and "longest" are strict: a tie
does not support them.
"""


def comparison_fixtures() -> dict[str, str]:
    files = {f"{COMPARISON_DIR}/comparison_brief.md": comparison_brief_md()}
    files.update({f"{COMPARISON_DIR}/{name}.md": page for name, page in COMPANY_PAGES.items()})
    return files


# ───────────────────────────────────────────────────────────────── all of them

def planned() -> dict[Path, str]:
    """Every generated file, by its path in the repository."""
    files: dict[str, str] = {}
    files.update(budget_fixtures())
    files.update(comparison_fixtures())
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
