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


# Questions and release notes every page also carries, about nothing the table records.
EVERYDAY_FAQ = [
    ("Which payment methods do you accept?", "Cards and bank transfer."),
    ("Can I import time entries from a spreadsheet?", "Yes, from a CSV file in the workspace settings."),
    ("Do you offer onboarding sessions?", "Yes, a one-hour onboarding call for new workspaces."),
    ("Can I rename my workspace?", "Yes, owners can rename it at any time."),
    ("Is there a desktop timer?", "Yes, for Windows and macOS."),
    ("How do I close my account?", "Owners can close it from the account page; data is deleted after 30 days."),
    ("Can clients see their own reports?", "Yes, through a read-only link."),
    ("Do you have a referral scheme?", "Yes, a month's credit for every referral."),
    ("Can I set different hourly rates?", "Yes, by person, client or task."),
    ("Which languages is the app in?", "English, German, French and Spanish."),
    ("Do you offer a discount for non-profits?", "Yes, 25% off."),
    ("Can I keep my data when I change plans?", "Yes; nothing is deleted when you move between plans."),
]
EVERYDAY_CHANGES = ["Dark mode.", "Keyboard shortcuts for timers.", "Weekly summary emails.", "Faster search.",
                    "CSV export of every report.", "A new onboarding checklist.", "Bulk edit for time entries.",
                    "Calendar view of time entries.", "Custom fields on clients.", "Smarter rounding rules for timesheets."]
QUOTES = [
    ("We closed our month-end in half the time.", "Head of operations, design studio"),
    ("The team actually fills in timesheets now.", "Managing partner, consultancy"),
    ("Our clients love the read-only reports.", "Account director, creative agency"),
    ("Setup took one afternoon.", "Founder, architecture practice"),
    ("Rates by client saved us hours every week.", "Finance lead, PR firm"),
    ("We finally know which clients are profitable.", "Chief executive, digital agency"),
    ("Support answered within the hour, every time.", "Office manager, engineering consultancy"),
]
ADD_ONS = {
    "Brisktime": ["Extra file storage: $2 per user per month", "Payroll export pack: $49 a month"],
    "Quillhour": ["Premium onboarding: $500 one-off", "Dedicated success manager on Pro: $300 a month"],
    "Ticklog": ["Sandbox workspace: $99 a month", "Custom report design: $750 one-off"],
    "Pacemark": ["Forecasting on Plus: $6 per user per month", "Extra file storage: $3 per user per month"],
    "Ledgerline": ["Accounting connector pack: $29 a month"],
}
_PAGES_MADE: list[str] = []


def _page(name: str, intro: str, plans: list[str], rows: list[tuple], footnotes: list[str], after_table: list[str],
          features: list[str], security: list[str], faq: list[tuple[str, str]], changelog: list[tuple[str, str]]) -> str:
    """A saved pricing page: introduction, plan table, footnotes, then its sections, each page with
    four everyday questions and four release notes of its own as well."""
    turn = len(_PAGES_MADE)
    _PAGES_MADE.append(name)
    faq = faq + [EVERYDAY_FAQ[(5 * turn + k) % len(EVERYDAY_FAQ)] for k in range(8)]
    changelog = sorted(changelog + [(f"2027-01-{1 + 3 * k + turn % 3:02d}", EVERYDAY_CHANGES[(turn + 3 * k) % len(EVERYDAY_CHANGES)])
                                    for k in range(8)])
    quotes = [QUOTES[(2 * turn + k) % len(QUOTES)] for k in range(2)]
    lines = [f"# {name} pricing", "", intro, "", "| | " + " | ".join(plans) + " |",
             "|---|" + "---|" * len(plans)]
    lines += ["| " + label + " | " + " | ".join(cells) + " |" for label, *cells in rows]
    if footnotes:
        lines += [""] + footnotes
    if after_table:
        lines += [""] + after_table
    lines += ["", "## Features", ""] + [f"- {item}" for item in features]
    if security:
        lines += ["", "## Security and compliance", ""] + security
    if faq:
        lines += ["", "## FAQ"]
        for question, answer in faq:
            lines += ["", f"**{question}**", answer]
    if name in ADD_ONS:
        lines += ["", "## Add-ons", ""] + [f"- {item}" for item in ADD_ONS[name]]
    lines += ["", "## What customers say", ""] + [f"> “{quote}” {who}" for quote, who in quotes]
    if changelog:
        lines += ["", "## Changelog", ""] + [f"- {day}: {entry}" for day, entry in changelog]
    return "\n".join(lines) + "\n"


Y, N = "✓", "—"
MONTHLY, ANNUAL, YEARLY = ("Price per user per month, billed monthly", "Price per user per month, billed annually",
                           "Price per user per year")
COMPANY_PAGES = {
    "tallyhour": _page(
        "Tallyhour", "Time tracking, approvals and invoicing for agencies and studios. Every price is per user.",
        ["Free", "Studio", "Agency"],
        [(MONTHLY, "$0", "$21", "$34"), (ANNUAL, "$0", "$17.50", "$28"), ("Users", "1", "From 1", "From 5"),
         ("Active projects", "3", "Unlimited", "Unlimited"), ("Time tracking and timesheets", Y, Y, Y),
         ("Timesheet approvals", N, Y, Y), ("Project budgets", N, Y, Y), ("Invoices from tracked time", N, Y, Y),
         ("API access", N, Y, Y), ("Single sign-on (SAML)", N, Y, Y), ("Audit log", N, N, Y),
         ("Phone support", N, Y, Y), ("Mobile app", Y, Y, Y), ("Uptime SLA", N, "99.9%", "99.9%")],
        [], ["The Free plan is free for as long as you use it: one person, three projects.",
             "Every paid plan starts with a 21-day free trial. No card needed."],
        ["Timers, timesheets and approvals in one place", "Budgets that warn you before a project runs over",
         "Invoices drafted from approved time"],
        ["Customer data can be hosted in the EU on Studio and Agency.", "We hold a SOC 2 Type II report.",
         "We sign a data processing agreement with every customer."],
        [("Can I switch between monthly and annual billing?", "Yes, at any time from the billing page."),
         ("Do you offer discounts for charities?", "Yes, 30% off any paid plan.")],
        [("2027-01-14", "Budgets now warn at 80% as well as 100%."), ("2027-02-02", "New invoice templates.")]),
    "brisktime": _page(
        "Brisktime", "Brisktime keeps timesheets, approvals and invoices in one place, and it is built for teams that "
        "take security seriously: single sign-on, SCIM provisioning and audit logs.",
        ["Starter", "Business"],
        [(YEARLY, "$276", "$420"), ("Billing", "Annual only", "Annual only"), ("Minimum seats", "3", "10"),
         ("Active projects", "20", "Unlimited"), ("Timesheets", Y, Y), ("Timesheet approvals", Y, Y),
         ("Project budgets", N, Y), ("Invoicing", Y, Y), ("Expense tracking", N, Y), ("API access", N, Y),
         ("Single sign-on (SAML) and SCIM", N, Y), ("Audit log", N, Y), ("Phone support", N, Y),
         ("Uptime SLA", "99.5%", "99.5%")],
        [], [],
        ["Approvals that route to the right manager", "Expense tracking on Business", "Exports to every major payroll tool"],
        ["All Brisktime data is hosted in our US data centres. EU hosting is not available.",
         "Our SOC 2 Type II audit is in progress; we expect the report this summer."],
        [("Is there a free trial?", "Yes. Try either plan free for 7 days."),
         ("Can I pay monthly?", "No. Brisktime plans are billed once a year."),
         ("Can I export my data?", "Yes, as CSV or through the API on Business.")],
        [("2027-01-09", "Approval reminders by email."), ("2027-02-11", "Faster timesheet loading on large teams.")]),
    "quillhour": _page(
        "Quillhour", "Plan, track and bill client work. Save 17% with annual billing.",
        ["Team", "Pro", "Enterprise"],
        [(ANNUAL, "$19", "$27", "Contact sales"), (MONTHLY, "$23", "$32", "Contact sales"),
         ("Minimum users", "2", "2", "25"), ("Active projects", "Unlimited", "Unlimited", "Unlimited"),
         ("Time tracking", Y, Y, Y), ("Timesheet approvals", Y, Y, Y), ("Project budgets", N, Y, Y),
         ("Invoicing", Y, Y, Y), ("API access", Y, Y, Y), ("SAML single sign-on", N, N, Y), ("Audit log", N, Y, Y),
         ("Phone support", N, N, Y), ("Mobile app", Y, Y, Y)],
        [], ["Quillhour has no free plan. Team and Pro come with a 14-day free trial."],
        ["Resource planning across every project", "Budgets and forecasts on Pro", "Client portal for approvals"],
        ["EU data residency is available on every plan.", "We hold a SOC 2 Type II report.",
         "We sign a data processing agreement with every customer."],
        [("What is the smallest team I can sign up?", "Team and Pro now start at 3 users. We raised the minimum in September."),
         ("Do you publish uptime?", "Our status page shows the last 90 days of uptime for every service."),
         ("Can I cancel at any time?", "Yes. Monthly plans end at the close of the month.")],
        [("2027-01-21", "Capacity view for resource planning."), ("2027-02-16", "Client portal in four more languages.")]),
    "ticklog": _page(
        "Ticklog", "Timesheets for professional-services firms.",
        ["Basic", "Pro", "Enterprise"],
        [(MONTHLY, "$24", "$33", "$45"), ("Minimum users", "5", "5", "20"), ("Active projects", "10", "Unlimited", "Unlimited"),
         ("Time tracking", Y, Y, Y), ("Timesheet approvals", N, Y, Y), ("Project budgets", N, Y, Y),
         ("Invoicing from timesheets", N, Y, Y), ("REST API", N, Y, Y), ("SAML single sign-on", N, N, Y),
         ("Audit trail", N, N, Y), ("Phone support", N, Y, Y), ("Uptime SLA", N, N, "99.95%")],
        [], ["Ticklog has no free plan and no free trial. Book a 30-minute demo and we will set up a sandbox with "
             "your own projects."],
        ["Utilisation reports by person and client", "Approvals and budgets on Pro and Enterprise",
         "Our mobile app is in beta for Pro customers."],
        ["Data is hosted in the US only.", "Ticklog holds a SOC 2 Type II report, available under NDA.",
         "We sign a data processing agreement with every customer."],
        [("Is the REST API included on Basic?", "Yes. Since October every Ticklog plan includes the REST API."),
         ("Can I get a discount for paying yearly?", "Yes, ask your account manager.")],
        [("2027-01-18", "Timesheet approvals are now included on Basic."), ("2027-02-04", "New utilisation dashboard.")]),
    "fenwork": _page(
        "Fenwork", "Time tracking, budgets and invoicing for agencies. Pay yearly and get two months free.",
        ["Essentials", "Growth", "Scale"],
        [(MONTHLY, "$22", "$30", "$39"), ("Minimum users", "2", "2", "5"), ("Free trial", "14 days", "14 days", "14 days"),
         ("Time tracking", Y, Y, Y), ("Timesheet approvals", Y, Y, Y), ("Project budgets", N, Y, Y),
         ("Invoicing", Y, Y, Y), ("API access", Y, Y, Y), ("Single sign-on", N, Y, Y), ("Audit log", N, Y, Y),
         ("Phone support", N, N, Y), ("Mobile app", Y, Y, Y), ("Uptime SLA", N, "99.9%", "99.9%")],
        [], [],
        ["Budgets with burn-down charts", "Invoices in 30 currencies", "Mobile timers that work offline"],
        ["Every plan lets you choose EU or US hosting for your workspace.",
         "We hold a SOC 2 Type I report; Type II is planned for next year."],
        [("How long is the free trial?", "Since March every plan comes with a 30-day free trial."),
         ("Is there a free plan?", "No. The trial gives you every feature of Scale instead."),
         ("Which currencies can I invoice in?", "Thirty, including euro, pound and yen.")],
        [("2027-02-08", "Essentials is now $24 per user per month, billed monthly."),
         ("2027-02-19", "Burn-down charts on every budget.")]),
    "larchpoint": _page(
        "Larchpoint Time", "Timesheets, approvals and client invoicing.",
        ["Core", "Scale"],
        [(MONTHLY, "$29", "$48"), ("Price per user per year, billed yearly", "$290", "$480"), ("Users", "From 2", "From 10"),
         ("Timesheets and approvals", Y, Y), ("Project budgets", "✓¹", Y), ("Client invoicing", Y, Y),
         ("Single sign-on through your identity provider", N, Y), ("Audit log", N, Y), ("Phone support", N, Y),
         ("Uptime SLA", "99.5%", "99.9%")],
        ["¹ Budgets on Core are a paid add-on at $3 per user per month."],
        ["Larchpoint has no free plan. Start with a 14-day free trial; every paid subscription also carries a "
         "30-day money-back guarantee."],
        ["Approvals in two clicks", "Apps for iOS and Android are included on every plan.", "Invoices synced to your accounting tool"],
        ["All Larchpoint data is stored in our US region. We do not offer EU hosting.",
         "We sign a data processing agreement with every customer."],
        [("Can I move from Core to Scale mid-month?", "Yes; we prorate the difference.")],
        [("2027-01-27", "Accounting sync for two more tools.")]),
    "clockwell": _page(
        "Clockwell", "Simple time tracking for growing teams.",
        ["Free", "Team", "Company"],
        [(MONTHLY, "$0", "$22", "$36"), (ANNUAL, "$0", "$18", "$30"), ("Users", "1", "From 2", "From 10"),
         ("Active projects", "2", "Unlimited", "Unlimited"), ("Time tracking", Y, Y, Y), ("Timesheet approvals", N, Y, Y),
         ("Project budgets", N, N, Y), ("Invoicing", N, Y, Y), ("API access", N, Y, Y), ("Single sign-on", N, N, Y),
         ("Audit log", N, N, Y), ("Phone support", N, N, Y), ("Uptime SLA", N, "99.9%", "99.95%")],
        [], ["The Free plan is free forever for one person.", "Paid plans come with a 14-day free trial."],
        ["Approvals and budgets on every paid plan", "Phone and chat support for every customer",
         "Mobile apps on every plan."],
        ["Customer data can be hosted in the EU on Team and Company.", "We hold a SOC 2 Type II report.",
         "We sign a data processing agreement with every customer."],
        [("Can I add guests for free?", "Yes, guests who only view reports are free on every plan.")],
        [("2027-01-30", "Reports load twice as fast.")]),
    "pacemark": _page(
        "Pacemark", "Project time and profitability for agencies.",
        ["Plus", "Pro", "Enterprise"],
        [(MONTHLY, "$26", "$38", "Contact sales"), (ANNUAL, "$22", "$32", "Contact sales"),
         ("Minimum users", "3", "3", "50"), ("Active projects", "Unlimited", "Unlimited", "Unlimited"),
         ("Time tracking", Y, Y, Y), ("Timesheet approvals", Y, Y, Y), ("Project budgets", N, Y, Y),
         ("Invoicing", Y, Y, Y), ("API access", "✓²", Y, Y), ("Single sign-on", N, Y, Y), ("Audit log", N, Y, Y),
         ("Phone support", N, N, Y), ("Uptime SLA", "99.9%", "99.9%", "99.99%")],
        ["² API access on Plus is a paid add-on."],
        ["There is no free plan. Plus and Pro come with a 14-day free trial."],
        ["Profitability by client and project", "Approvals on every plan", "Forecasts on Pro and Enterprise"],
        ["EU hosting is coming in the second half of the year.", "We hold a SOC 2 Type II report."],
        [("Do you offer phone support on Plus?", "Plus customers get email and chat support; phone support starts on Enterprise."),
         ("Can I pay by invoice?", "Yes, on annual plans.")],
        [("2027-02-15", "Single sign-on is now included on Plus."), ("2027-02-22", "Profitability alerts.")]),
    "hourglen": _page(
        "Hourglen", "Time tracking and approvals for consultancies.",
        ["Standard", "Premium"],
        [(MONTHLY, "$25", "$35"), ("Free trial", "10 days", "10 days"), ("Minimum users", "2", "5"),
         ("Time tracking", Y, Y), ("Timesheet approvals", Y, Y), ("Project budgets", N, Y), ("Invoicing", Y, Y),
         ("API access", Y, Y), ("Single sign-on", N, Y), ("Audit log", N, N), ("Phone support", N, Y),
         ("Mobile app", Y, Y)],
        [], ["There is no free plan."],
        ["Approvals by client, project or person", "Budgets on Premium", "We aim for 99.9% uptime."],
        ["Customer data is hosted in the EU (Frankfurt) or the US (Virginia), as you choose.",
         "We completed our SOC 2 Type I audit in 2026.", "We sign a data processing agreement with every customer."],
        [("How long is the free trial?", "Since February, trials last 14 days on both plans."),
         ("Do you support single sign-on?", "Yes, on Premium.")],
        [("2027-01-11", "Approvals by client.")]),
    "ledgerline": _page(
        "Ledgerline", "Timesheets that flow straight into billing.",
        ["Starter", "Team", "Business"],
        [(MONTHLY, N, "$28", "$36"), (YEARLY, "$264", "$300", "$384"),
         ("Billing", "Annual only", "Monthly or annual", "Monthly or annual"), ("Minimum users", "1", "3", "10"),
         ("Active projects", "5", "Unlimited", "Unlimited"), ("Time tracking", Y, Y, Y), ("Timesheet approvals", Y, Y, Y),
         ("Project budgets", "✓³", Y, Y), ("Invoicing", Y, Y, Y), ("API access", N, Y, Y),
         ("Single sign-on", N, N, Y), ("Audit log", N, Y, Y), ("Phone support", N, N, N)],
        ["³ Budgets on Starter cover up to five projects."],
        ["Ledgerline has no free plan and no free trial; every plan carries a 30-day money-back guarantee."],
        ["Billing rates by person and client", "Mobile app coming later this year.", "Budgets on every plan"],
        ["EU hosting is not available.", "A SOC 2 Type II report is available to customers."],
        [("Can I change plans?", "Yes, upgrades take effect at once.")],
        [("2027-01-25", "Audit log is now included from Team."), ("2027-02-12", "Starter now starts at 2 users."),
         ("2027-02-20", "Single sign-on moved to Team and above.")]),
}

COMPARISON_ATTRIBUTES = [
    ("free_plan", "whether the company offers a plan that is free with no time limit. A free trial is not a free plan."),
    ("trial_days", "the length of the free trial in days, and 0 when the page says there is none."),
    ("entry_plan", "the entry plan's name: the cheapest plan with a price above $0, on a monthly basis."),
    ("entry_price_usd", "the entry plan's price per user per month, on a monthly basis."),
    ("entry_min_users", "the fewest users the entry plan can be bought for."),
    ("entry_projects", "the active projects the entry plan allows, or `unlimited`."),
    ("top_plan_price_usd", "the price per user per month, on a monthly basis, of the top plan: the plan listed "
                           "last in the plan table."),
    ("sso_on_entry", "whether the entry plan includes single sign-on."),
    ("sso_cheapest_plan", "the cheapest plan that includes single sign-on, or `none` when no plan does."),
    ("audit_log_cheapest_plan", "the cheapest plan that includes an audit log, or `none` when no plan does."),
    ("invoicing_on_entry", "whether the entry plan includes invoicing."),
    ("api_on_entry", "whether the entry plan includes API access."),
    ("approvals_on_entry", "whether the entry plan includes timesheet approvals."),
    ("budgets_on_entry", "whether the entry plan includes project budgets."),
    ("phone_support_on_entry", "whether the entry plan includes phone support."),
    ("mobile_app", "whether the company offers a mobile app, on any plan."),
    ("uptime_sla_percent", "the highest uptime the company commits to in a service-level agreement, on any plan."),
    ("eu_hosting", "whether customer data can be hosted in the EU, on any plan."),
    ("soc2_type2", "whether the company holds a SOC 2 Type II report."),
    ("dpa", "whether the company signs a data processing agreement with customers."),
]
COMPARISON_CLAIMS = [
    "Tallyhour's entry plan costs less per user per month than every competitor's entry plan.",
    "Tallyhour is one of only two of the ten with a free plan.",
    "No competitor includes single sign-on on its entry plan; Tallyhour does.",
    "Tallyhour's free trial is longer than the free trial of every competitor that offers one.",
    "Tallyhour is the only one of the ten whose entry plan includes both timesheet approvals and project budgets.",
    "Tallyhour is one of only three of the ten with both a SOC 2 Type II report and EU hosting.",
    "Tallyhour's top plan costs less per user per month than the top plan of every competitor that offers EU hosting.",
    "Every competitor's entry plan needs at least two users; Tallyhour's can be bought for one.",
    "Tallyhour is the only one of the ten with phone support on its entry plan.",
]


def comparison_brief_md() -> str:
    pages = ", ".join(f"`{name}.md`" for name in COMPANY_PAGES)
    attributes = "\n".join(f"- `{name}`: {text}" for name, text in COMPARISON_ATTRIBUTES)
    claims = "\n".join(f"{number}. {claim}" for number, claim in enumerate(COMPARISON_CLAIMS, 1))
    return f"""# Tallyhour: competitor comparison, brief

From Priya Raman, product marketing. Tallyhour sells time tracking and invoicing to agencies. Sales
wants one comparison table of us and our nine closest competitors, and I want to know which of our
draft claims the table can back. The ten pricing pages were saved from the sites today: {pages}.

## The attributes

One row per company, one column per attribute:

{attributes}

## Rules for every cell

1. A cell holds the value the company's own page states, or exactly `not stated` when the page
   does not state it. Do not infer a value from what a page leaves out: a feature, a plan or a
   report the page does not mention is `not stated`, not `no`.
2. In a plan table a check mark (✓) means the plan includes it and a dash (—) means it does not.
3. Where parts of one page disagree, the newest wins. Each changelog entry is dated and overrides
   everything else on the page; the FAQ was updated after the plan table and overrides it; the plan
   table and its footnotes override the introduction, the feature list and the other sections.
4. A footnote that makes a feature a paid add-on means the plan does not include it. A footnote
   that only limits a feature (a cap or a quota) leaves it included.
5. A feature, hosting option or report the page calls in beta, coming, planned or in progress is
   not included or held: `no`. Only a SOC 2 Type II report counts for `soc2_type2`: a Type I
   report is `no`.
6. An uptime figure the page gives as a target, an aim or a status-page history is not a
   service-level agreement. A money-back guarantee is not a free trial.
7. Monthly basis: when a plan has a price billed monthly, that is its price, even if the page
   also gives a lower price for annual billing. When a plan is sold only on annual billing, its
   price is its price per user per year divided by 12, rounded to the cent. A price the page
   replaces with "Contact sales" is `not stated`.
8. Write yes or no as `yes` or `no`, a price in US dollars with two decimals and no currency sign,
   a percentage without the % sign, days, users and projects as whole numbers, unlimited projects
   as `unlimited`, a plan by its name alone, and `none` when no plan includes the feature.

## The draft claims

{claims}

A claim is `supportable` when the table proves it: it must hold whatever value any `not stated`
cell might really have. Otherwise it is `not supportable`. "Less", "longer" and "only" are strict:
a tie does not support them.
"""


def comparison_fixtures() -> dict[str, str]:
    files = {f"{COMPARISON_DIR}/comparison_brief.md": comparison_brief_md()}
    files.update({f"{COMPARISON_DIR}/{name}.md": page for name, page in COMPANY_PAGES.items()})
    return files


# ─────────────────────────────────────────────────────────────── launch-timeline

TIMELINE_DIR = "launch-timeline"
TIMELINE_START = "2027-03-01"
TIMELINE_TARGET = "2027-05-26"
OFFICES = {
    "London": [("2027-03-26", "Good Friday"), ("2027-03-29", "Easter Monday"),
               ("2027-05-03", "Early May bank holiday"), ("2027-05-31", "Spring bank holiday")],
    "Boston": [("2027-04-19", "Patriots' Day"), ("2027-05-31", "Memorial Day")],
}
# (owner, role, office, days worked, away)
PEOPLE = [
    ("Ana", "brand lead", "London", "Monday to Friday", ""),
    ("Ben", "copywriter", "London", "Monday to Friday", ""),
    ("Cleo", "designer", "London", "Monday to Friday", "2027-04-19 to 2027-04-23"),
    ("Esme", "PR and influencers", "London", "Monday to Friday", ""),
    ("Gia", "lifecycle and customer service", "London", "Monday, Tuesday and Wednesday", ""),
    ("Jules", "PR and influencer coordinator", "London", "Monday, Tuesday, Wednesday and Thursday", ""),
    ("Dev", "web developer", "Boston", "Monday to Friday", ""),
    ("Finn", "paid media", "Boston", "Monday to Friday", "2027-04-26 to 2027-04-28"),
    ("Hana", "partner and retail marketing", "Boston", "Monday to Friday", ""),
    ("Ivo", "sales enablement and operations", "Boston", "Monday to Friday", ""),
]
SUPPLIERS = [
    ("Printer", "packaging, sell sheets and booth graphics"),
    ("Freight", "carrier from the printer to the warehouse"),
    ("Lingua", "translation agency"),
]
W, C = "working days", "calendar days"
# (id, task, owner, duration, unit, depends on, optional, not before, deliverable)
LAUNCH_TASKS_V2 = [
    ("T01", "Launch brief and positioning", "Ana", 4, W, [], "no", "", "One-page brief: audience, promise, price band, launch goals"),
    ("T02", "Pricing and margin sign-off", "Ana", 2, W, ["T01"], "no", "", "Retail and online prices signed off with finance"),
    ("T03", "Messaging framework", "Ben", 4, W, ["T01"], "no", "", "Headline promise, three proof points, tone notes"),
    ("T04", "Product photography shoot", "Cleo", 2, W, ["T01"], "no", "2027-03-10", "Studio shoot: hero, lifestyle and detail shots"),
    ("T05", "Packaging artwork", "Cleo", 5, W, ["T03"], "no", "", "Front, back and side panels for the box"),
    ("T06", "Packaging copy and legal lines", "Ben", 2, W, ["T03"], "no", "", "Panel copy, care instructions, compliance lines"),
    ("T07", "Brand film script", "Ben", 3, W, ["T03"], "yes", "", "Script and shot list for a 60-second brand film"),
    ("T08", "Landing page wireframes", "Dev", 3, W, ["T03"], "no", "", "Wireframes for the waitlist and product pages"),
    ("T09", "Key visuals for ads", "Cleo", 4, W, ["T03", "T04"], "no", "", "Three key visuals that every ad and page builds on"),
    ("T10", "Customer research readout", "Hana", 3, W, ["T01"], "no", "", "Findings from twelve customer interviews"),
    ("T11", "Sales deck outline", "Ivo", 2, W, ["T03"], "no", "", "Storyline and slide list for the retail sales deck"),
    ("T12", "Media list and outreach plan", "Esme", 3, W, ["T03"], "no", "", "Forty target titles and the outreach order"),
    ("T13", "Waitlist page copy", "Ben", 2, W, ["T03"], "no", "", "Copy for the waitlist page and its form"),
    ("T14", "Waitlist page build", "Dev", 3, W, ["T08", "T13"], "no", "", "Live waitlist page with the signup form"),
    ("T15", "Waitlist email sequence", "Gia", 3, W, ["T13"], "no", "", "Three nurture emails for waitlist signups"),
    ("T16", "Search keyword plan", "Finn", 3, W, ["T03"], "no", "", "Keyword list, match types and negatives"),
    ("T17", "Audience build for paid social", "Finn", 2, W, ["T10"], "no", "", "Lookalike and interest audiences"),
    ("T18", "Influencer shortlist", "Esme", 4, W, ["T10"], "no", "", "Twenty creators with reach and fit notes"),
    ("T19", "Packaging dielines and print files", "Cleo", 3, W, ["T05", "T06"], "no", "", "Print-ready files on the printer's dielines"),
    ("T20", "Creative review: packaging and key visuals", "Ana", 1, W, ["T09", "T19"], "no", "", "Sign-off that releases the print files"),
    ("T21", "Packaging print run", "Printer", 12, C, ["T20"], "no", "", "Printed and folded boxes"),
    ("T22", "Freight to the warehouse", "Freight", 9, C, ["T21"], "no", "", "Boxes delivered to the warehouse"),
    ("T23", "Product page copy", "Ben", 3, W, ["T02", "T03"], "no", "", "Product page copy with prices"),
    ("T24", "Product page design", "Cleo", 3, W, ["T09", "T23"], "no", "", "Desktop and mobile designs of the product page"),
    ("T25", "Product page build", "Dev", 5, W, ["T14", "T24"], "no", "", "Built product page on staging"),
    ("T26", "Checkout and pricing configuration", "Dev", 2, W, ["T02", "T25"], "no", "", "Prices, bundles and discount rules in checkout"),
    ("T27", "Product page translation", "Lingua", 8, C, ["T23"], "no", "", "German and French product page copy"),
    ("T28", "EU site localisation", "Dev", 3, W, ["T25", "T27"], "no", "", "Translated product pages live on the EU store"),
    ("T29", "Press release", "Ben", 2, W, ["T23"], "no", "", "Release text with quotes and price"),
    ("T30", "Retail sell sheet", "Cleo", 2, W, ["T23"], "no", "", "Two-page sell sheet for buyers"),
    ("T31", "Sell sheet print", "Printer", 4, C, ["T30"], "no", "", "Printed sell sheets for the trade show"),
    ("T32", "Press kit", "Esme", 3, W, ["T04", "T29"], "no", "", "Release, photos and fact sheet in one kit"),
    ("T33", "Retail partner list and terms", "Hana", 4, W, ["T02"], "no", "", "Target retailers and trade terms"),
    ("T34", "Partner co-marketing agreements", "Hana", 5, W, ["T33"], "no", "", "Signed co-marketing terms with three retailers"),
    ("T35", "Partner training webinar", "Hana", 1, W, ["T30", "T34"], "no", "2027-05-12", "Live product training for retail staff"),
    ("T36", "Ad creative: static set", "Cleo", 4, W, ["T09", "T23"], "no", "", "Twelve static ads in four sizes"),
    ("T37", "Ad creative: video cutdowns", "Cleo", 6, W, ["T36"], "no", "", "Six, fifteen and thirty-second cutdowns"),
    ("T38", "Launch lookbook", "Cleo", 4, W, ["T24"], "yes", "", "Twenty-page lookbook for press and partners"),
    ("T39", "Email templates", "Cleo", 2, W, ["T36"], "no", "", "Launch email templates in the brand system"),
    ("T40", "Launch email copy", "Ben", 3, W, ["T23"], "no", "", "Copy for the three launch emails"),
    ("T41", "Launch email build", "Gia", 3, W, ["T39", "T40"], "no", "", "Launch emails built and tested in the email platform"),
    ("T42", "SMS launch flow", "Gia", 2, W, ["T40"], "yes", "", "Two SMS messages for opted-in subscribers"),
    ("T43", "Customer service FAQ", "Gia", 2, W, ["T23"], "no", "", "Answers to the twenty likeliest questions"),
    ("T44", "Help centre articles", "Ben", 3, W, ["T23"], "no", "", "Set-up, care and returns articles"),
    ("T45", "Trade show booth graphics", "Cleo", 3, W, ["T36"], "no", "", "Back wall, counter and banner artwork"),
    ("T46", "Booth graphics print", "Printer", 5, C, ["T45"], "no", "", "Printed booth graphics"),
    ("T47", "Trade show", "Hana", 2, W, ["T31", "T46+3"], "no", "2027-05-18", "Two days on the stand at the housewares show"),
    ("T48", "Search campaigns build", "Finn", 3, W, ["T16", "T25"], "no", "", "Search campaigns built, paused"),
    ("T49", "Paid social campaigns build", "Finn", 4, W, ["T17", "T25", "T36"], "no", "", "Paid social campaigns built, paused"),
    ("T50", "Video campaigns build", "Finn", 2, W, ["T37"], "yes", "", "Video campaigns built, paused"),
    ("T51", "Tracking plan and tags", "Dev", 3, W, ["T25"], "no", "", "Events, tags and conversion goals"),
    ("T52", "Product quiz", "Dev", 4, W, ["T25"], "yes", "", "Five-question quiz that recommends a size"),
    ("T53", "Influencer outreach", "Esme", 4, W, ["T18", "T32"], "no", "", "Offers sent and confirmed with creators"),
    ("T54", "Influencer seeding kits", "Esme", 2, W, ["T22+3", "T53"], "no", "", "Kits packed and sent from warehouse stock"),
    ("T55", "Analytics QA", "Dev", 2, W, ["T48", "T49", "T51"], "no", "", "Every conversion event checked end to end"),
    ("T56", "Review program setup", "Esme", 2, W, ["T26"], "no", "", "Post-purchase review requests switched on"),
    ("T57", "Launch blog post", "Ben", 2, W, ["T29"], "yes", "", "Founder's post on why the product exists"),
    ("T58", "Sales battlecards", "Ivo", 3, W, ["T11", "T23"], "yes", "", "Battlecards against the three closest rivals"),
    ("T59", "Sales deck", "Ivo", 4, W, ["T11", "T36"], "no", "", "Finished retail sales deck"),
    ("T60", "Sales team training", "Ivo", 1, W, ["T26", "T59"], "no", "", "Training session for the sales team"),
    ("T61", "Press outreach under embargo", "Esme", 4, W, ["T32"], "no", "2027-05-10", "Embargoed briefings with target titles"),
    ("T62", "Retail partner deck", "Ana", 4, W, ["T30", "T33"], "yes", "", "Deck for retail partners' buying teams"),
    ("T63", "Launch plan sign-off", "Ana", 1, W, ["T26", "T34"], "no", "", "Final launch plan agreed with retail partners"),
    ("T64", "Marketplace listing", "Ivo", 3, W, ["T04", "T23"], "no", "", "Listing copy and images for the marketplace"),
    ("T65", "Marketplace listing translation", "Lingua", 6, C, ["T64"], "no", "", "German and French marketplace listings"),
    ("T66", "Partner newsletter feature", "Hana", 2, W, ["T35"], "no", "", "Feature in the retail partners' newsletter"),
    ("T67", "Warehouse stock check", "Ivo", 1, W, ["T22+3"], "no", "", "Received boxes counted and released for sale"),
    ("T68", "Social launch posts", "Cleo", 2, W, ["T36"], "no", "", "Launch-week posts for every channel"),
    ("T69", "Social posts scheduling", "Finn", 1, W, ["T29", "T68"], "no", "", "Posts scheduled in the social tool"),
    ("T70", "Site performance pass", "Dev", 3, W, ["T55"], "no", "", "Page speed fixes on the product pages"),
    ("T71", "Site QA and checkout test", "Dev", 2, W, ["T26", "T28", "T70"], "no", "", "Full purchase tested on every store"),
    ("T72", "Launch email QA", "Gia", 1, W, ["T41", "T71"], "no", "", "Launch emails checked against the live site"),
    ("T73", "Paid media launch QA", "Finn", 1, W, ["T48", "T49", "T55"], "no", "", "Campaigns checked, budgets loaded"),
    ("T74", "Unboxing video", "Cleo", 3, W, ["T67"], "yes", "", "Unboxing video shot with warehouse stock"),
    ("T75", "Customer service training", "Gia", 1, W, ["T43", "T44"], "no", "", "Support team trained on the FAQ and articles"),
    ("T76", "Press day coordination", "Esme", 1, W, ["T61"], "no", "", "Interview slots and samples for launch day"),
    ("T77", "Final creative review", "Ana", 1, W, ["T37", "T45", "T68"], "no", "", "Last look at every launch asset"),
    ("T78", "EU press release adaptation", "Ben", 2, W, ["T29"], "no", "", "Release adapted for EU titles: prices in euros, EU stockists"),
    ("T79", "EU media list", "Jules", 2, W, ["T12"], "no", "", "Twenty EU titles and their embargo contacts"),
    ("T80", "Influencer content approvals", "Jules", 2, W, ["T53"], "no", "", "Creator drafts checked against the brief"),
    ("T81", "Retail staff incentive scheme", "Ivo", 2, W, ["T34"], "no", "", "Sales incentive for retail floor staff"),
    ("T82", "Retail order forecast", "Ivo", 2, W, ["T34", "T67"], "no", "", "First-month order forecast by retailer"),
    ("T83", "Retail replenishment plan", "Ivo", 2, W, ["T82"], "no", "", "Reorder points and weekly replenishment"),
    ("T84", "Search ad copy variants", "Finn", 2, W, ["T23", "T48"], "no", "", "Four headline sets for each ad group"),
    ("T85", "Remarketing audiences", "Dev", 1, W, ["T51"], "no", "", "Site-visitor audiences from the new tags"),
    ("T86", "Launch budget pacing sheet", "Finn", 1, W, ["T84", "T85"], "no", "", "Daily budgets and pacing alerts"),
    ("T87", "Customer review seeding", "Jules", 2, W, ["T54"], "yes", "", "Early reviews from seeded creators"),
    ("T88", "Packaging insert card", "Ben", 1, W, ["T06"], "no", "", "Welcome card copy for inside the box"),
    ("T89", "Partner FAQ for retail staff", "Ben", 2, W, ["T44"], "no", "", "Short FAQ for retail floor staff"),
    ("T90", "Launch-day social monitoring", "Ben", 1, W, ["T69"], "no", "", "Listening streams and escalation rota"),
    ("T91", "EU press briefings", "Jules", 3, W, ["T78", "T79"], "no", "2027-05-17", "Briefings with EU titles under the same embargo"),
    ("T92", "Investor update", "Ana", 1, W, ["T63"], "yes", "", "Launch note for investors"),
    ("T93", "Launch-day press call list", "Jules", 1, W, ["T61", "T91"], "no", "", "Who calls which title on launch morning"),
    ("T94", "Go/no-go review", "Ana", 1, W, ["T07", "T38", "T42", "T47", "T50", "T52", "T54", "T56", "T57", "T58", "T60",
                                               "T62", "T63", "T65", "T66", "T67", "T69", "T71", "T72", "T73", "T74", "T75",
                                               "T76", "T77", "T80", "T81", "T83", "T86", "T87", "T88", "T89", "T90",
                                               "T92", "T93"], "no", "", "Launch decision with every owner"),
    ("T95", "Launch-day war room setup", "Dev", 1, W, ["T94"], "no", "", "Dashboards, alerts and rota for launch day"),
    ("T96", "Launch day", "Ana", 1, W, ["T94", "T95"], "no", "", "The product goes on sale"),
]
# Older estimates kept in the plan's history: what the plan file now says replaces them.
SUPERSEDED = [
    ("2027-02-08", "T04", "The studio was first booked for 2027-03-08; the studio moved the booking to 2027-03-10."),
    ("2027-02-09", "T05", "Packaging artwork was scoped at 4 working days before the side panels were added; it is 5."),
    ("2027-02-10", "T09", "Key visuals were planned at 3 working days; Cleo now plans 4."),
    ("2027-02-11", "T21", "Printer quoted 10 calendar days for the print run; the confirmed quote is 12."),
    ("2027-02-11", "T22", "Freight was quoted at 7 calendar days by road; the confirmed sea and road route takes 9."),
    ("2027-02-12", "T27", "The translation agency first quoted 6 calendar days; it now quotes 8 for two languages."),
    ("2027-02-15", "T25", "Product page build estimated at 4 working days; Dev re-estimated it at 5 after the wireframes."),
    ("2027-02-16", "T35", "The partner training webinar was pencilled in for 2027-05-05; partners asked for 2027-05-12."),
    ("2027-02-17", "T41", "Launch email build was planned for Ben; it moved to Gia, who builds every email."),
    ("2027-02-18", "T47", "The housewares show was first listed for 2027-05-11; the organisers moved it to 2027-05-18."),
    ("2027-02-18", "T46", "Booth graphics print was quoted at 3 calendar days; the printer now quotes 5."),
    ("2027-02-19", "T61", "Embargoed briefings were planned from 2027-05-03; the embargo now lifts for briefings on 2027-05-10."),
    ("2027-02-19", "T91", "EU briefings were planned to start with the UK ones; EU titles asked for 2027-05-17."),
    ("2027-02-22", "T37", "Video cutdowns were scoped at 3 working days; adding the thirty-second cut made them 6."),
    ("2027-02-22", "T38", "The lookbook was scoped at 6 working days with a printed edition; the digital-only edition is 4."),
    ("2027-02-23", "T54", "Seeding kits were to ship straight from the printer; they now ship from the warehouse, after T22+3."),
    ("2027-02-24", "T65", "Marketplace translation was quoted at 4 calendar days for one language; two languages take 6."),
    ("2027-02-25", "T59", "The sales deck was planned at 3 working days; adding the retailer case studies made it 4."),
    ("2027-02-25", "T70", "The performance pass was scoped at 2 working days; Dev added image work and it is 3."),
    ("2027-02-26", "Calendar", "Cleo's leave was first planned for 2027-04-12 to 2027-04-16; it is now 2027-04-19 to 2027-04-23."),
]


def launch_plan_v2_csv() -> str:
    return _csv_text(
        ["task_id", "task", "owner", "duration", "duration_unit", "depends_on", "optional", "not_before", "deliverable"],
        [[task_id, name, owner, duration, unit, " ".join(deps), optional, not_before, deliverable]
         for task_id, name, owner, duration, unit, deps, optional, not_before, deliverable in LAUNCH_TASKS_V2],
    )


def team_calendar_md() -> str:
    offices = "\n".join(
        f"| {office} | Monday to Friday | {', '.join(f'{day} ({why})' for day, why in days)} |"
        for office, days in OFFICES.items())
    people = "\n".join(f"| {name} | {role} | {office} | {days} | {away or 'none'} |"
                       for name, role, office, days, away in PEOPLE)
    suppliers = "\n".join(f"| {name} | {what} | every calendar day |" for name, what in SUPPLIERS)
    history = "\n".join(f"- {day}, {task}: {text}" for day, task, text in SUPERSEDED)
    return f"""# Orlo Fold launch: team calendar

## Offices

| office | working days | holidays |
|---|---|---|
{offices}

## People

Each person works on the days below in their office's calendar: not on its holidays, not on days
they do not work, and not on days they are away.

| owner | role | office | works | away |
|---|---|---|---|---|
{people}

## Outside suppliers

Suppliers work every calendar day, weekends and holidays included, and each takes one job at a time.

| owner | what | works |
|---|---|---|
{suppliers}

## Plan history

Earlier estimates, kept for the record. The plan file is current; where it differs from these, the
plan file is right.

{history}
"""


def launch_brief_v2_md() -> str:
    return f"""# Orlo Fold launch: plan and scheduling rules

From Mara Quill, Head of Marketing. Orlo sells reusable food containers online and through
retailers, and the Orlo Fold collapsible lunch box launches this spring. `launch_plan.csv` lists
every task of the launch and `team_calendar.md` says who works when. The work starts on Monday
{TIMELINE_START}, and I have told retail partners the launch is on **{TIMELINE_TARGET}**. I need to know
whether that holds.

## The plan file

- `duration` and `duration_unit`: how long the task takes. A task measured in working days counts
  only its owner's working days; one measured in calendar days counts every day.
- `depends_on`: the tasks that must be finished before it can start, separated by spaces. A task
  depends only on tasks with lower IDs. An entry
  such as `T22+3` adds a lead time in calendar days: the task cannot start before the third
  calendar day after T22's finish date (if T22 finishes on a Monday, on the Thursday at the
  earliest). A plain entry such as `T22` means the day after its finish date at the earliest.
- `owner`: the one person or supplier who does it.
- `optional`: `yes` for a task we could cut.
- `not_before`: the earliest date the task can start, set from outside. Blank means none.
- `deliverable`: what the task produces. It does not change the schedule.

## Scheduling rules

1. A task starts at the start of one of its owner's working days and runs on its owner's working
   days only, for its duration: a task of 3 working days that starts on a Monday, for someone who
   works Monday to Friday, finishes at the end of Wednesday. Its finish date is the last day it
   runs. Time off, holidays and days an owner does not work pause a task; they do not count.
2. A task can start on its owner's first working day that every entry in `depends_on` allows.
3. Every owner, person or supplier, does one task at a time and takes their tasks in task ID
   order: a task cannot start before the day after the same owner's previous task (the one with
   the closest lower ID) has finished, even if it could otherwise start sooner. Nobody starts a
   later task early.
4. A task with a `not_before` date cannot start before that date.
5. No task starts before {TIMELINE_START}. Every task starts on the earliest day rules 1 to 5 allow.
6. The launch date is the day T96 runs.

## Definitions

- A task's **slack** is the number of its owner's working days (calendar days for a supplier) its
  finish could move later without moving the launch date, if every task that waits for it
  (because it depends on it, or because its owner takes it next) moved later as needed and nothing
  else changed.
- The **critical path** is the tasks whose slack is 0, in the order they run.

## Cutting tasks

Only optional tasks can be cut. A cut task is removed from the plan: a task that depended on it
depends instead on the tasks the cut task depended on, and its owner's next task follows the
owner's task before it. Everything else, including every duration, owner, lead time and
`not_before` date, stays as it is.

If the launch misses {TIMELINE_TARGET}, I need the smallest set of optional tasks to cut that
brings it to {TIMELINE_TARGET} or earlier: the fewest tasks; if two sets of that size both do it,
the one with the earlier launch date; if they are still tied, the one whose task IDs come first.

For the review I also want every task's slack.
"""


def timeline_fixtures() -> dict[str, str]:
    return {
        f"{TIMELINE_DIR}/launch_brief.md": launch_brief_v2_md(),
        f"{TIMELINE_DIR}/team_calendar.md": team_calendar_md(),
        f"{TIMELINE_DIR}/launch_plan.csv": launch_plan_v2_csv(),
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
