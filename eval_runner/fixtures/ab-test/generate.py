#!/usr/bin/env python3
"""Write, or check, the sources of the ab-test-readout task (prompt version 4).

Deterministic: the daily results come from a seeded generator and the plan is
written out below, so running it twice writes the same bytes. The plan is
rendered from the constants in `eval_runner/task_facts_conversion.py`, the
same ones its oracle applies, and `build()` refuses data in which a planted
effect did not come out as designed (see `_check`).

    python3 eval_runner/fixtures/ab-test/generate.py --write
    python3 eval_runner/fixtures/ab-test/generate.py --check

All brands and figures here are invented.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eval_runner import task_facts_conversion as facts  # noqa: E402

SEED = 8812
FIRST_DAY = dt.date(2026, 4, 6)
WEEKDAY = (1.04, 1.06, 1.05, 1.02, 0.96, 0.90, 0.97)   # Monday first
DAILY_VISITORS = {"desktop": 560, "mobile": 760}
# Days 1-3: a cache rule served control to some visitors assigned to variant B.
CACHE_DAYS = range(1, 4)
CACHE_CONTROL_SHARE = {"desktop": 0.60, "mobile": 0.79}
# Signup rate (%) by variant, device and period.
CONTROL_RATE = {"desktop": 8.0, "mobile": 4.0}
VARIANT_RATE_BURN_IN = {"desktop": 9.4, "mobile": 4.35}
VARIANT_RATE_WINDOW = {"desktop": 7.85, "mobile": 3.72}
# Each source's share of a device's visitors and how its signup rate compares with the average.
SOURCES = {"direct": (0.30, 1.10), "organic_search": (0.34, 0.95), "paid_search": (0.18, 0.85),
           "email": (0.11, 1.35), "referral": (0.07, 0.90)}
# QA visits from the office network, forced into variant B with a URL flag: about 3 in 10 make an account.
QA_VISITS = {"desktop": (34, 46), "mobile": (12, 20)}
QA_SIGNUP_RATE = 0.30
# Billing tickets per 1,000 visitors by variant and period.
TICKETS_PER_1000 = {("control", "burn-in"): 3.0, ("variant_b", "burn-in"): 2.2,
                    ("control", "window"): 3.0, ("variant_b", "window"): 3.8}

PLAN_MD = f"""\
# Kestrel Notes: pricing-page test plan (written before launch)

Kestrel Notes is a note-taking app with a free plan and a paid plan.

- **Change tested:** variant B shows annual pricing first and moves the free-plan button below the paid plans. Control is the current page.
- **Hypothesis:** leading with annual pricing raises the share of pricing-page visitors who create an account.
- **Primary metric:** signup rate = signups ÷ visitors.
- **Guardrail metric:** billing-support tickets opened within 7 days of the visit, per 1,000 visitors.
- **Assignment:** each new visitor is assigned once. Desktop visitors are split {facts.AB_PLANNED_CONTROL_SHARE['desktop'] * 100:.0f}/{(1 - facts.AB_PLANNED_CONTROL_SHARE['desktop']) * 100:.0f} between control and variant B. Mobile visitors are split {facts.AB_PLANNED_CONTROL_SHARE['mobile'] * 100:.0f}/{(1 - facts.AB_PLANNED_CONTROL_SHARE['mobile']) * 100:.0f}: {facts.AB_PLANNED_CONTROL_SHARE['mobile'] * 100:.0f}% to control and {(1 - facts.AB_PLANNED_CONTROL_SHARE['mobile']) * 100:.0f}% to variant B, because variant B's mobile layout is new.
- **Duration:** {facts.AB_DAYS} days, {FIRST_DAY.isoformat()} to {(FIRST_DAY + dt.timedelta(days=facts.AB_DAYS - 1)).isoformat()}.
- **QA visits:** visits from the company's office network are recorded with source `{facts.AB_INTERNAL_SOURCE}`. They are the team's own checks, forced into variant B with a URL flag, and are left out of every metric, check and decision rule below; every other source counts.
- **Burn-in week:** days 1 to {facts.AB_WINDOW_FIRST_DAY - 1}. A new page draws curiosity clicks and a new test carries set-up problems, so the burn-in week is left out of every metric, check and decision rule below. The analysis window is days {facts.AB_WINDOW_FIRST_DAY} to {facts.AB_DAYS}.

## How the result is read (analysis window only)
- A variant's signup rate on a device = its signups ÷ its visitors on that device.
- Device-weighted signup rate of a variant = its desktop signup rate × desktop's share of all visitors + its mobile signup rate × mobile's share, where a device's share counts the visitors of both variants. Device-weighted lift = variant B's device-weighted rate ÷ control's − 1. This is the primary estimate, because the two devices are split differently.
- Sample-ratio check, for each device: chi-square = the sum over both variants of (observed visitors − expected visitors)² ÷ expected visitors, where expected visitors = the device's visitors × the variant's planned share on that device. The check fails on a device when its chi-square is above {facts.AB_CHI_SQUARE_LIMIT}.
- Guardrail: billing tickets ÷ visitors × 1,000, per variant, both devices together. It is breached when variant B's rate is more than {facts.AB_GUARDRAIL_LIMIT_PERCENT}% above control's.

## Decision rules
Apply them in order. The first rule whose condition holds decides.
1. Either variant has fewer than {facts.AB_MIN_VISITORS:,} visitors: {facts.AB_DECISIONS[1]}.
2. The sample-ratio check fails on either device: the split is broken; {facts.AB_DECISIONS[2]}.
3. The guardrail is breached: {facts.AB_DECISIONS[3]}.
4. The device-weighted lift is +{facts.AB_SHIP_LIFT_PERCENT}% or more and variant B's signup rate is higher than control's on both devices: {facts.AB_DECISIONS[4]}.
5. Otherwise: {facts.AB_DECISIONS[5]}.
"""

HEADER = ["day", "date", "variant", "device", "source", "visitors", "signups", "billing_tickets"]


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _period(day: int) -> str:
    return "burn-in" if day < facts.AB_WINDOW_FIRST_DAY else "window"


def build() -> dict[str, str]:
    rng = random.Random(SEED)
    cells = []   # [day, date, variant, device, source, visitors, signups]
    for day in range(1, facts.AB_DAYS + 1):
        date = FIRST_DAY + dt.timedelta(days=day - 1)
        for device, level in DAILY_VISITORS.items():
            share = CACHE_CONTROL_SHARE[device] if day in CACHE_DAYS else float(facts.AB_PLANNED_CONTROL_SHARE[device])
            for source, (part, multiplier) in SOURCES.items():
                total = round(level * part * WEEKDAY[date.weekday()] * rng.uniform(0.9, 1.1))
                control = round(total * share + rng.uniform(-0.03, 0.03) * total)
                for variant, visitors in (("control", control), ("variant_b", total - control)):
                    rate = (CONTROL_RATE if variant == "control" else
                            VARIANT_RATE_BURN_IN if _period(day) == "burn-in" else VARIANT_RATE_WINDOW)[device]
                    signups = round(visitors * rate * multiplier / 100 * rng.uniform(0.9, 1.1))
                    cells.append([day, date.isoformat(), variant, device, source, visitors, signups])
            visits = rng.randint(*QA_VISITS[device])
            cells.append([day, date.isoformat(), "variant_b", device, facts.AB_INTERNAL_SOURCE, visits,
                          round(visits * QA_SIGNUP_RATE * rng.uniform(0.8, 1.2))])
    # Billing tickets: each period's total at its rate, spread over the rows by visitors. QA files none.
    tickets = [0] * len(cells)
    for (variant, period), per_1000 in TICKETS_PER_1000.items():
        members = [index for index, cell in enumerate(cells) if cell[2] == variant and _period(cell[0]) == period
                   and cell[4] != facts.AB_INTERNAL_SOURCE]
        visitors = sum(cells[index][5] for index in members)
        for _ in range(round(visitors * per_1000 / 1000)):
            pick = rng.choices(members, weights=[cells[index][5] for index in members])[0]
            tickets[pick] += 1
    rows = [cell + [count] for cell, count in zip(cells, tickets)]
    files = {"test_plan.md": PLAN_MD, "experiment_results.csv": _csv_text(HEADER, rows)}
    _check(files)
    return files


def _check(files: dict[str, str]) -> None:
    """Refuse data in which a planted effect is missing or an unplanted one appeared."""
    rows = list(csv.DictReader(io.StringIO(files["experiment_results.csv"])))
    window = facts.ab_readout(facts.ab_totals(rows, range(facts.AB_WINDOW_FIRST_DAY, facts.AB_DAYS + 1)))
    burn_in = facts.ab_readout(facts.ab_totals(rows, range(1, facts.AB_WINDOW_FIRST_DAY)))
    whole = facts.ab_readout(facts.ab_totals(rows, range(1, facts.AB_DAYS + 1)))
    limit = float(facts.AB_CHI_SQUARE_LIMIT)
    # The reversal: pooled up, both devices down, in the window.
    assert window["pooled_lift"] > 0.05, float(window["pooled_lift"])
    assert all(-0.07 < lift < -0.015 for lift in window["device_lift"].values()), window["device_lift"]
    assert window["weighted_lift"] < -0.015
    # The first week's lift that fades.
    assert burn_in["weighted_lift"] > 0.08 and all(lift > 0.05 for lift in burn_in["device_lift"].values())
    # The planned split holds in the window; the burn-in's cache problem fails it over 28 days.
    assert all(value < limit - 1.5 for value in window["chi_square"].values()), window["chi_square"]
    assert all(value > limit + 2 for value in whole["chi_square"].values()), whole["chi_square"]
    # The guardrail breaches in the window and not over 28 days.
    limit_lift = facts.AB_GUARDRAIL_LIMIT_PERCENT / 100
    assert window["guardrail_increase"] > limit_lift + 0.04, float(window["guardrail_increase"])
    assert whole["guardrail_increase"] < limit_lift - 0.03, float(whole["guardrail_increase"])
    # Both variants clear the minimum sample in the window.
    assert min(window["visitors"].values()) > facts.AB_MIN_VISITORS
    assert facts.ab_decision(window) == 3 and facts.ab_decision(whole) == 2
    # Counted in, the QA visits fail the mobile split and lift variant B.
    with_qa = facts.ab_readout(facts.ab_totals(rows, range(facts.AB_WINDOW_FIRST_DAY, facts.AB_DAYS + 1), internal=True))
    assert with_qa["chi_square"]["mobile"] > limit + 2 and facts.ab_decision(with_qa) == 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    drift = []
    for name, text in build().items():
        path = HERE / name
        if args.write:
            path.write_text(text)
        elif not path.exists() or path.read_text() != text:
            drift.append(name)
    for name in drift:
        print(f"DRIFT: {name} differs from the generator's output", file=sys.stderr)
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
