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
BUDGET_SEED = 2
QUARTER_BUDGET = 1_400_000
BLOCK_USD = 10_000
LEAD_SCALE = 2  # leads of a $10,000 block
REGIONS = ["na", "emea", "apac"]
REGION_NAMES = {"na": "North America", "emea": "Europe, Middle East and Africa", "apac": "Asia-Pacific"}
MONTHS = ["apr", "may", "jun"]
MONTH_NAMES = {"apr": "April", "may": "May", "jun": "June"}
FIELD_CHANNELS = ["webinars", "events", "abm"]
# id: (description, base leads of a first block by region, decay per block,
#      month multipliers, most blocks in a cell by region)
BUDGET_CHANNELS = {
    "search": ("Google Ads search, non-brand keywords",
               {"na": 190, "emea": 150, "apac": 95}, 0.88, (1.0, 1.04, 0.97), {"na": 7, "emea": 6, "apac": 4}),
    "linkedin": ("LinkedIn Ads sponsored content to the target-account list",
                 {"na": 150, "emea": 135, "apac": 80}, 0.86, (1.0, 1.0, 0.95), {"na": 5, "emea": 5, "apac": 4}),
    "meta": ("Meta prospecting and retargeting",
             {"na": 120, "emea": 100, "apac": 88}, 0.82, (0.95, 1.0, 1.05), {"na": 5, "emea": 4, "apac": 4}),
    "programmatic": ("Programmatic display through the demand-side platform",
                     {"na": 85, "emea": 70, "apac": 62}, 0.84, (1.0, 0.98, 1.0), {"na": 4, "emea": 4, "apac": 3}),
    "video": ("Online video and connected TV",
              {"na": 95, "emea": 75, "apac": 50}, 0.8, (0.9, 1.0, 1.08), {"na": 4, "emea": 3, "apac": 3}),
    "syndication": ("Content syndication of the clinic benchmark report through a publisher network",
                    {"na": 160, "emea": 140, "apac": 100}, 0.72, (1.0, 1.0, 1.0), {"na": 5, "emea": 5, "apac": 4}),
    "review_sites": ("Paid profiles and lead programs on software review marketplaces",
                     {"na": 70, "emea": 64, "apac": 40}, 0.8, (1.0, 1.0, 1.0), {"na": 3, "emea": 3, "apac": 2}),
    "podcasts": ("Sponsorships on physiotherapy and practice-management podcasts",
                 {"na": 150, "emea": 115, "apac": 60}, 0.8, (1.0, 1.1, 0.7), {"na": 3, "emea": 2, "apac": 2}),
    "webinars": ("Regional webinar series run with partner clinics",
                 {"na": 175, "emea": 160, "apac": 120}, 0.78, (1.0, 1.0, 0.92), {"na": 3, "emea": 3, "apac": 2}),
    "events": ("Trade-show and conference booths",
               {"na": 230, "emea": 190, "apac": 130}, 0.72, (1.0, 1.0, 1.0), {"na": 3, "emea": 3, "apac": 2}),
    "abm": ("Account-based direct mail and gifting to target clinics",
            {"na": 195, "emea": 150, "apac": 85}, 0.8, (0.75, 1.0, 1.1), {"na": 3, "emea": 2, "apac": 2}),
    "partners": ("Co-marketing with referral partners: equipment suppliers and training providers",
                 {"na": 105, "emea": 95, "apac": 75}, 0.8, (1.0, 0.95, 1.0), {"na": 3, "emea": 3, "apac": 3}),
}
# Extra blocks on top of the maxima above, by channel and region.
EXTRA_BLOCKS = {
    "search": {"na": 2, "emea": 2, "apac": 1}, "linkedin": {"na": 1, "emea": 1, "apac": 1},
    "meta": {"na": 1, "emea": 1, "apac": 1}, "programmatic": {"na": 1, "emea": 1, "apac": 1},
    "syndication": {"na": 1, "emea": 1},
}
# Trade shows run only in these region-months.
EVENT_MONTHS = {("na", "apr"), ("na", "jun"), ("emea", "may"), ("emea", "jun"), ("apac", "may")}
# Blocks already contracted: review sites in NA and EMEA every month, and the NA April show.
COMMITTED_BLOCKS = {**{("review_sites", region, month): 1 for region in ("na", "emea") for month in MONTHS},
                    ("events", "na", "apr"): 1}
# (minimum, maximum, most in one month) of media spend, and field blocks a month, by region.
REGION_LIMITS = {"na": (400_000, 600_000, 200_000, 4), "emea": (340_000, 500_000, 170_000, 3),
                 "apac": (360_000, 440_000, 130_000, 2)}
LICENCES = {
    "webinars": "$3,200 for each month it is live",
    "abm": "$8,000 if it is live in one month, $13,000 if live in two, $17,000 if live in all three",
    "podcasts": "$5,000 one-off agency setup if it is live in any month, plus $2,000 for each month it is live",
}


def budget_cells() -> dict[tuple[str, str, str], list[int]]:
    """The leads each block of each cell adds, from a seeded draw: strictly
    decreasing within a cell. The seed is one whose best split is unique."""
    import random

    rng = random.Random(BUDGET_SEED)
    cells: dict[tuple[str, str, str], list[int]] = {}
    for channel, (_description, base, decay, months, maxima) in BUDGET_CHANNELS.items():
        for region in REGIONS:
            for index, month in enumerate(MONTHS):
                most = maxima[region]
                if channel == "events" and (region, month) not in EVENT_MONTHS:
                    most = 0
                leads: list[int] = []
                value = LEAD_SCALE * base[region] * months[index] * rng.uniform(0.85, 1.15)
                for _block in range(most):
                    drawn = int(round(value * rng.uniform(0.95, 1.05)))
                    if leads and drawn >= leads[-1]:
                        drawn = leads[-1] - 1
                    leads.append(drawn)
                    value *= decay
                cells[(channel, region, month)] = leads
    # Deeper inventory in the always-on channels: more blocks, each adding fewer leads, drawn
    # from a stream of their own so the blocks above keep their values.
    tail = random.Random(BUDGET_SEED * 1000 + 7)
    for (channel, region, month), leads in cells.items():
        for _extra in range(EXTRA_BLOCKS.get(channel, {}).get(region, 0)):
            drawn = int(round(leads[-1] * BUDGET_CHANNELS[channel][2] * tail.uniform(0.95, 1.05)))
            leads.append(min(drawn, leads[-1] - 1))
    return cells


def budget_terms_csv() -> str:
    return _csv_text(
        ["channel", "description", "field_channel", "licence"],
        [[channel, spec[0], "yes" if channel in FIELD_CHANNELS else "no", "yes" if channel in LICENCES else "no"]
         for channel, spec in BUDGET_CHANNELS.items()],
    )


SHOWS = {("na", "apr"): "ClinicOps Summit, Denver", ("na", "jun"): "Physio Business Expo, Toronto",
         ("emea", "may"): "Rehab Practice Forum, Manchester", ("emea", "jun"): "PhysioTech Europe, Rotterdam",
         ("apac", "may"): "Allied Health Congress, Melbourne"}
LIMIT_SOURCES = {
    "search": "keyword inventory at target bids", "linkedin": "target-account audience size",
    "meta": "audience size", "programmatic": "demand-side platform inventory", "video": "booked inventory",
    "syndication": "publisher network inventory", "review_sites": "marketplace lead program",
    "podcasts": "available sponsorship slots", "webinars": "webinar slots", "abm": "mailing list size",
    "partners": "partner co-marketing calendar",
}


def budget_cell_limits_csv() -> str:
    rows = []
    for (channel, region, month), leads in budget_cells().items():
        committed = COMMITTED_BLOCKS.get((channel, region, month), 0)
        if channel == "events":
            note = f"booth at {SHOWS[(region, month)]}" if (region, month) in SHOWS else "no trade show this month"
        else:
            note = LIMIT_SOURCES[channel]
        if committed:
            note += "; contracted in 2026"
        rows.append([channel, region, month, len(leads), committed, note])
    return _csv_text(["channel", "region", "month", "max_blocks", "committed_blocks", "note"], rows)


def budget_forecasts_csv() -> str:
    rows = []
    for (channel, region, month), leads in budget_cells().items():
        if channel == "syndication":
            continue
        for block, added in enumerate(leads, 1):
            low, high = int(added * 0.8), int(added * 1.25 + 0.5)
            rows.append([channel, region, month, block, block * BLOCK_USD, added, low, high,
                         f"{BLOCK_USD / added:.2f}"])
    return _csv_text(["channel", "region", "month", "block", "spend_through_block_usd", "added_leads",
                      "added_leads_low", "added_leads_high", "cost_per_added_lead_usd"], rows)


def budget_syndication_csv() -> str:
    rows = []
    for (channel, region, month), leads in budget_cells().items():
        if channel != "syndication":
            continue
        for block in range(1, len(leads) + 1):
            rows.append([region, month, block * BLOCK_USD, sum(leads[:block])])
    return _csv_text(["region", "month", "spend_usd", "cumulative_leads"], rows)


def budget_q1_actuals_csv() -> str:
    """What each channel did last quarter: a distractor, drawn apart from the forecasts."""
    import random

    rng = random.Random(2027)
    rows = []
    for channel, (_description, base, _decay, _months, maxima) in BUDGET_CHANNELS.items():
        for region in REGIONS:
            for month in ("jan", "feb", "mar"):
                blocks = rng.randint(0, maxima[region])
                leads = int(sum(LEAD_SCALE * base[region] * rng.uniform(0.6, 1.0) * 0.8 ** k for k in range(blocks)))
                impressions = int(leads * rng.uniform(180, 420)) if blocks else 0
                clicks = int(leads * rng.uniform(6, 14)) if blocks else 0
                opportunities = int(leads * rng.uniform(0.04, 0.12))
                pipeline = opportunities * rng.randrange(9_000, 16_000, 100)
                rows.append([channel, region, month, blocks * BLOCK_USD, impressions, clicks, leads, opportunities,
                             pipeline])
    return _csv_text(["channel", "region", "month", "spend_usd", "impressions", "clicks", "leads", "opportunities",
                      "pipeline_usd"], rows)


def budget_constraint_names() -> list[str]:
    names = ["budget"]
    names += [f"{region}_min" for region in REGIONS] + [f"{region}_max" for region in REGIONS]
    names += [f"pacing_{region}_{month}" for region in REGIONS for month in MONTHS]
    names += [f"field_{region}_{month}" for region in REGIONS for month in MONTHS]
    return names


def budget_brief_md() -> str:
    limits = "\n".join(
        f"| {region} | ${low:,} | ${high:,} | ${month:,} | {field} |"
        for region, (low, high, month, field) in REGION_LIMITS.items())
    licences = "\n".join(f"| {channel} | {text} |" for channel, text in LICENCES.items())
    regions = ", ".join(f"{REGION_NAMES[region]} (`{region}`)" for region in REGIONS)
    months = ", ".join(f"{MONTH_NAMES[month]} (`{month}`)" for month in MONTHS)
    names = ", ".join(f"`{name}`" for name in budget_constraint_names())
    field = ", ".join(f"`{channel}`" for channel in FIELD_CHANNELS)
    return f"""# Fernmoor: Q2 2027 demand budget, planning brief

From Ines Varga, Head of Demand Generation. Fernmoor sells practice-management software to
physiotherapy clinics in three regions: {regions}. This brief sets the rules for splitting the
demand budget for Q2 2027, the months {months}, across twelve channels in the three regions.
The files beside it:

- `channel_terms.csv`: each channel, whether it is a field channel, and whether it needs a licence.
- `cell_limits.csv`: for each channel, region and month (a "cell"), the most blocks the cell can
  take and the blocks already committed in it.
- `forecasts.csv`: the leads each block is projected to add, for every channel except syndication.
- `syndication_vendor_forecast.csv`: the syndication vendor's own forecast, in its own format.
- `q1_actuals.csv`: what each channel delivered last quarter. It is context for the regional
  teams, not a forecast, and plays no part in the split.

## The money

- **Quarter budget:** ${QUARTER_BUDGET:,}. Everything the plan buys comes out of it: media blocks
  and licences. The plan may not go over it. Money left over stays unspent.
- **Blocks:** media is bought in whole blocks of ${BLOCK_USD:,}, each in one channel, one region
  and one month. A cell's blocks are bought in order: block 1, then block 2, and so on, up to its
  `max_blocks`.
- **Forecasts:** in `forecasts.csv`, `added_leads` is the number of qualified leads a block adds
  on top of the earlier blocks of its cell. A cell's projected leads for n blocks are the sum of
  its first n rows. `added_leads_low` and `added_leads_high` are the forecast's range for the same
  block; plan on `added_leads` alone. The syndication vendor states instead `cumulative_leads`, the cell's leads
  once the block at that spend is bought: the leads a syndication block adds are its cumulative
  figure minus the one before it.

## Licences

Three channels need a licence. A licence is charged per channel, not per region, for the months
the channel is live, and it comes out of the quarter budget. A channel is live in a month when it
buys at least one block in that month in any region; a channel that buys no block pays nothing.

| channel | licence for the quarter |
|---|---|
{licences}

## Regional limits

Media spend only: licences are not regional.

| region | minimum media spend in the quarter | maximum media spend in the quarter | most media spend in any one month | most field blocks in any one month |
|---|---|---|---|---|
{limits}

The field channels are {field}. Each block of a field channel needs the regional field
marketing team, so in each month a region can buy at most the number of field blocks above, the
three field channels together.

## Commitments

`committed_blocks` in `cell_limits.csv` are already contracted: the plan must buy at least that
many blocks in the cell. They count against every limit and are paid from the quarter budget like
any other block.

## What I need

The split of the budget that projects the most leads while keeping every rule above. If two
splits project the same number of leads, take the one that costs less.

## Constraints, by name

For each of these constraints, say whether it binds in your split: {names}.

- `budget` binds when less than ${BLOCK_USD:,} of the quarter budget is left unspent.
- `<region>_min` binds when the region's media spend is exactly its minimum, and `<region>_max`
  when it is exactly its maximum.
- `pacing_<region>_<month>` binds when the region's media spend in that month is exactly its
  most in any one month.
- `field_<region>_<month>` binds when the region buys exactly its most field blocks in that month.
"""


def budget_fixtures() -> dict[str, str]:
    return {
        f"{BUDGET_DIR}/planning_brief.md": budget_brief_md(),
        f"{BUDGET_DIR}/channel_terms.csv": budget_terms_csv(),
        f"{BUDGET_DIR}/cell_limits.csv": budget_cell_limits_csv(),
        f"{BUDGET_DIR}/forecasts.csv": budget_forecasts_csv(),
        f"{BUDGET_DIR}/syndication_vendor_forecast.csv": budget_syndication_csv(),
        f"{BUDGET_DIR}/q1_actuals.csv": budget_q1_actuals_csv(),
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


# ─────────────────────────────────────────────────────────────── launch-timeline

TIMELINE_DIR = "launch-timeline"
TIMELINE_START = "2027-03-01"
TIMELINE_TARGET = "2027-04-13"
HOLIDAYS = [("2027-03-12", "company offsite"), ("2027-03-26", "Good Friday"), ("2027-03-29", "Easter Monday")]
OWNERS = [
    ("Ana", "brand lead"), ("Ben", "copywriter"), ("Cleo", "designer"), ("Dev", "web developer"),
    ("Esme", "PR and partnerships"), ("Finn", "paid media"), ("Gia", "lifecycle and support"),
    ("Printer", "the outside packaging printer"),
]
# (id, task, owner, working days, depends on, optional, not before)
LAUNCH_TASKS = [
    ("T01", "Launch brief and positioning", "Ana", 3, [], "no", ""),
    ("T02", "Product photography shoot", "Cleo", 2, ["T01"], "no", "2027-03-09"),
    ("T03", "Messaging and copy deck", "Ben", 4, ["T01"], "no", ""),
    ("T04", "Packaging artwork", "Cleo", 4, ["T01"], "no", ""),
    ("T05", "Retail lookbook", "Cleo", 3, ["T02", "T03"], "yes", ""),
    ("T06", "Packaging print run", "Printer", 10, ["T04"], "no", ""),
    ("T07", "Landing page design", "Cleo", 3, ["T02", "T03"], "no", ""),
    ("T08", "Landing page build", "Dev", 5, ["T07"], "no", ""),
    ("T09", "Email sequence copy", "Ben", 3, ["T03"], "no", ""),
    ("T10", "Email build and test sends", "Gia", 2, ["T02", "T09"], "no", ""),
    ("T11", "Ad creative", "Cleo", 4, ["T02", "T03"], "no", ""),
    ("T12", "Influencer shortlist and outreach", "Esme", 5, ["T01"], "no", ""),
    ("T13", "Influencer seeding kits", "Esme", 3, ["T06", "T12"], "yes", ""),
    ("T14", "Press kit", "Ben", 2, ["T02", "T03"], "no", ""),
    ("T15", "Press outreach under embargo", "Esme", 3, ["T14"], "no", "2027-04-05"),
    ("T16", "Retail partner deck", "Ana", 5, ["T03"], "yes", ""),
    ("T17", "Paid social campaign setup", "Finn", 3, ["T08", "T11"], "no", ""),
    ("T18", "Search campaign setup", "Finn", 2, ["T03", "T08"], "no", ""),
    ("T19", "Tracking and analytics QA", "Dev", 2, ["T08", "T17"], "no", ""),
    ("T20", "Customer service FAQ and macros", "Gia", 2, ["T03"], "no", ""),
    ("T21", "Launch blog post", "Ben", 2, ["T14"], "yes", ""),
    ("T22", "Site QA and checkout test", "Dev", 2, ["T10", "T19"], "no", ""),
    ("T23", "Go/no-go review", "Ana", 1, ["T05", "T13", "T15", "T16", "T17", "T18", "T20", "T21", "T22"], "no", ""),
    ("T24", "Launch day", "Ana", 1, ["T23"], "no", ""),
]
SLACK_ASKED = ["T06", "T11", "T16"]


def launch_plan_csv() -> str:
    return _csv_text(
        ["task_id", "task", "owner", "duration_days", "depends_on", "optional", "not_before"],
        [[task_id, name, owner, days, " ".join(deps), optional, not_before]
         for task_id, name, owner, days, deps, optional, not_before in LAUNCH_TASKS],
    )


def launch_brief_md() -> str:
    holidays = "\n".join(f"- {day} ({why})" for day, why in HOLIDAYS)
    owners = "\n".join(f"- {name}: {role}" for name, role in OWNERS)
    slack = ", ".join(SLACK_ASKED)
    return f"""# Orlo Fold launch: plan, calendar and scheduling rules

From Mara Quill, Head of Marketing. Orlo sells reusable food containers online, and the Orlo Fold
collapsible lunch box launches this spring. `launch_plan.csv` lists every task of the launch. The
work starts on Monday {TIMELINE_START}, and I have told retail partners the launch is on
**{TIMELINE_TARGET}**. I need to know whether that holds.

## The plan file

- `duration_days`: working days the task takes.
- `depends_on`: the tasks that must be finished before it can start (space-separated).
- `owner`: the one person, or the printer, who does it.
- `optional`: `yes` for a task we could cut.
- `not_before`: the earliest date the task can start, set from outside (a booked studio, a press
  embargo). Blank means none.

## Owners

{owners}

## Calendar

Working days are Monday to Friday, except these company holidays:

{holidays}

## Scheduling rules

1. A task starts at the start of a working day and runs for its duration in working days: a
   3-day task that starts on a Monday finishes at the end of Wednesday. Its finish date is its
   last working day.
2. A task can start on the first working day after every task it depends on has finished.
3. An owner does one task at a time and takes their tasks in task ID order: a task cannot start
   until the same owner's previous task (the one with the closest lower ID) has finished, even if
   it could otherwise start sooner. Nobody starts a later task early.
4. A task with a `not_before` date cannot start before that date, or before the first working
   day after it when the date is not a working day.
5. No task starts before {TIMELINE_START}. Every task starts on the earliest working day that
   rules 2 to 5 allow.
6. The launch date is the day T24 runs.

## Definitions

- A task's **slack** is the number of working days its finish could move later without moving
  the launch date, if every task that waits for it (because it depends on it, or because its
  owner takes it next) moved later as needed and nothing else changed.
- The **critical path** is the tasks whose slack is 0, in the order they run.

## Cutting tasks

Only optional tasks can be cut. A cut task is removed from the plan: a task that depended on it
depends instead on the tasks the cut task depended on, and its owner's next task follows the
owner's task before it. Everything else, including every duration, owner and `not_before` date,
stays as it is.

If the launch misses {TIMELINE_TARGET}, I need the smallest set of optional tasks to cut that
brings it to {TIMELINE_TARGET} or earlier: the fewest tasks; if two sets of that size both do it,
the one with the earlier launch date; if they are still tied, the one whose task IDs come first.

For the review I also want the slack of {slack}.
"""


def timeline_fixtures() -> dict[str, str]:
    return {
        f"{TIMELINE_DIR}/launch_brief.md": launch_brief_md(),
        f"{TIMELINE_DIR}/launch_plan.csv": launch_plan_csv(),
    }


# ───────────────────────────────────────────────────────────────── all of them

def planned() -> dict[Path, str]:
    """Every generated file, by its path in the repository."""
    files: dict[str, str] = {}
    files.update(budget_fixtures())
    files.update(comparison_fixtures())
    files.update(timeline_fixtures())
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
