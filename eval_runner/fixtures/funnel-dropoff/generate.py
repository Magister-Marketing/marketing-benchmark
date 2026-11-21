#!/usr/bin/env python3
"""Write, or check, the sources of the funnel-dropoff task.

Deterministic: the daily counts come from a seeded generator and everything
else is written out below, so running it twice writes the same bytes. The
rules are rendered from the constants in `eval_runner/task_facts_conversion.py`,
the same ones its oracle applies, and `build()` refuses data in which a planted
effect did not come out as designed (see `_check`).

    python3 eval_runner/fixtures/funnel-dropoff/generate.py --write
    python3 eval_runner/fixtures/funnel-dropoff/generate.py --check

All brands and figures here are invented.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import random
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eval_runner import task_facts_conversion as facts  # noqa: E402

SEED = 6203
FIRST_DAY = dt.date(2026, 3, 2)
DAYS = 28
WEEKDAY = (1.00, 0.97, 0.98, 1.02, 1.06, 1.18, 1.12)  # Monday first
# segment -> daily carts, and the step rates (%) of shipping, payment and order
SEGMENTS = {
    ("desktop", "Chrome"): (420, (64.0, 80.0, 74.0)),
    ("desktop", "Safari"): (200, (63.0, 81.0, 75.0)),
    ("desktop", "Edge"): (180, (62.0, 79.0, 73.0)),
    ("desktop", "Firefox"): (170, (61.0, 78.0, 72.0)),
    ("mobile", "Safari"): (540, (60.0, 76.0, 70.0)),
    ("mobile", "Chrome"): (390, (58.0, 75.0, 68.0)),
    ("mobile", "Samsung Internet"): (190, (56.0, 74.0, 67.0)),
    ("mobile", "Firefox"): (170, (57.0, 74.0, 66.0)),
    ("tablet", "Safari"): (260, (63.0, 79.0, 71.0)),
    ("tablet", "Chrome"): (180, (61.0, 77.0, 69.0)),
}
NOISE_POINTS = 0.8
BREAK_DAY = dt.date(2026, 3, 16)          # release 5.8.0
BROKEN = (("mobile", "Safari"), 41.0)     # its order step from the release on
# Effects inside the normal range: segment(s), step index (0 shipping, 1 payment, 2 order), first day, last day, points.
INSIDE = [
    ([("mobile", "Chrome")], 0, dt.date(2026, 3, 10), None, 2.0),                       # after 5.7.0
    ([("tablet", "Safari")], 2, BREAK_DAY, None, 2.8),                                  # after 5.8.0
    ([("mobile", "Chrome"), ("mobile", "Samsung Internet")], 2, BREAK_DAY, None, 1.2),  # after 5.8.0
    ([("desktop", "Firefox"), ("mobile", "Firefox")], 0, dt.date(2026, 3, 18), None, 1.5),
    (list(SEGMENTS), 0, dt.date(2026, 3, 21), dt.date(2026, 3, 24), 1.0),              # the sale email
]
SALE_DAYS = (dt.date(2026, 3, 21), dt.date(2026, 3, 24))
SALE_CARTS = 1.2
# Below the range for a while, then back inside it.
OUTAGES = [
    (("desktop", "Chrome"), 2, dt.date(2026, 3, 24), dt.date(2026, 3, 24), 31.0),
    (("desktop", "Edge"), 1, dt.date(2026, 3, 20), dt.date(2026, 3, 23), 66.0),
]
BOT_FIRST_DAY = dt.date(2026, 3, 19)
BOT_CARTS = (240, 330)
_ORDER_DAYS = facts.FUNNEL_DOUBLE_FIRED[0][2]
_PAYMENT_DAYS = facts.FUNNEL_DOUBLE_FIRED[1][2]

RELEASE_LOG_MD = f"""\
# Bramblecote Home: release and change log, March 2026

| Date | Change |
|---|---|
| 2026-03-04 | 5.6.3: copy changes on the cart page. |
| 2026-03-10 | 5.7.0: address autocomplete on the shipping step, on every device. |
| 2026-03-10 | Tag manager version 41 published: a new order-confirmation tag. |
| 2026-03-13 | 5.7.1: removes the duplicate order-confirmation tag published in version 41. From {_ORDER_DAYS[0]} to {_ORDER_DAYS[-1]} the order-confirmation tag fired twice for every order, on every browser. |
| 2026-03-14 | Product images and scripts moved to a new CDN provider. |
| 2026-03-16 | 5.8.0: new payment form with saved cards and express wallets, on every device. |
| 2026-03-18 | New shipping-rate table: flat rates by region. |
| 2026-03-20 | Edge 136 starts rolling out to desktop users. |
| 2026-03-21 | Spring-sale email sent to the full list. |
| 2026-03-24 | 5.8.1: payment-form hotfix (clearer card error messages). |
| 2026-03-25 | Security team identifies a price-monitoring crawler that runs as {facts.FUNNEL_BOT_BROWSER} and adds products to a cart. |
| {_PAYMENT_DAYS[0]} | Analytics SDK 5.9.0: on {facts.FUNNEL_DOUBLE_FIRED[1][1]}, on every device, the payment-step event fires twice for every session that reaches payment. |
| 2026-03-30 | Analytics SDK 5.9.1 fixes the double payment-step event. From {_PAYMENT_DAYS[0]} to {_PAYMENT_DAYS[-1]} the event fired twice on {facts.FUNNEL_DOUBLE_FIRED[1][1]}. |
"""

RULES_MD = f"""\
# Bramblecote Home: checkout funnel analysis rules

## The export
- `funnel_daily.csv` has one row per day, device, browser and step. `count` is the number of sessions that reached the step that day: `cart` (viewed the cart), `shipping` (reached shipping details), `payment` (reached payment) and `order` (placed an order). A step with no sessions that day has no row.
- A segment is one device and browser pair.
- Double-fired events: the release log records each time an event fired twice for every session, with the step, the browsers it hit and the days. On those days that step's rows, for those browsers, count two events per session. Halve them.
- Automated traffic: rows whose browser is `{facts.FUNNEL_BOT_BROWSER}` come from a price-monitoring crawler. Leave them out of every figure.

## Rates
- Conversion rate = orders ÷ cart sessions, over every segment, for the days in question.
- A step's rate, for one segment = its sessions at the step ÷ its sessions at the step before it (shipping ÷ cart, payment ÷ shipping, order ÷ payment). Over several days, sum the sessions of those days first.

## Breaks
- The reference week is {facts.FUNNEL_REFERENCE_WEEK[0]} to {facts.FUNNEL_REFERENCE_WEEK[1]}.
- A segment's normal range for a step is the step's rate over the reference week plus or minus {facts.FUNNEL_RANGE_POINTS} percentage points.
- A segment's step has broken on day D when the step's daily rate is below its normal range on day D and on every later day in the export. The break begins on the first such day.
- Before the break means the days before the day the break begins; after the break means that day and every later day.

## The size of the loss
- Orders lost: for the broken segment, take its sessions at the step before the broken step, after the break. Multiply them by the segment's rate from that step to an order before the break (its orders ÷ its sessions at that step, both summed over the days before the break). Subtract the orders the segment recorded after the break, and round to the nearest whole order.
- Revenue lost = orders lost × ${facts.FUNNEL_ORDER_VALUE}, the store's average order value.

## Suspected causes
- A suspected cause names a date, the segments it would hit and the step it would break. The data is consistent with it only when one of those segments has that step break, beginning on that date. Otherwise the data rules it out.
"""

CAUSES_MD = """\
# Incident thread: suspected causes of the checkout drop (collected 2026-03-30)

| # | Suspected cause | Date | Segments it would hit | Step it would break |
|---|---|---|---|---|
| C1 | Address autocomplete (5.7.0) confuses shoppers | 2026-03-10 | every segment | shipping |
| C2 | The new CDN is slow on phones and the payment page times out | 2026-03-14 | mobile / Safari, mobile / Chrome | order |
| C3 | The new payment form (5.8.0) fails on iPhone Safari | 2026-03-16 | mobile / Safari | order |
| C4 | The new payment form (5.8.0) fails on iPad Safari | 2026-03-16 | tablet / Safari | order |
| C5 | The spring-sale email brought shoppers who leave before shipping | 2026-03-21 | every segment | shipping |
| C6 | The 5.8.1 hotfix broke card payments on desktop Chrome | 2026-03-24 | desktop / Chrome | order |
| C7 | Edge 136 blocks the payment page's scripts | 2026-03-20 | desktop / Edge | payment |
| C8 | Analytics SDK 5.9.0 broke Safari checkouts on desktop and iPad | 2026-03-27 | desktop / Safari, tablet / Safari | order |
| C9 | Express wallets (5.8.0) fail on Android phones | 2026-03-16 | mobile / Chrome, mobile / Samsung Internet | order |
| C10 | The new shipping-rate table puts Firefox shoppers off | 2026-03-18 | desktop / Firefox, mobile / Firefox | shipping |
"""


def _csv_text(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _active(first: dt.date, last: dt.date | None, day: dt.date) -> bool:
    return first <= day and (last is None or day <= last)


def _rates(segment: tuple[str, str], day: dt.date, base: tuple[float, ...], rng: random.Random) -> list[float]:
    rates = [rate + rng.uniform(-NOISE_POINTS, NOISE_POINTS) for rate in base]
    for segments, step, first, last, points in INSIDE:
        if segment in segments and _active(first, last, day):
            rates[step] -= points
    if segment == BROKEN[0] and day >= BREAK_DAY:
        rates[2] = BROKEN[1] + rng.uniform(-2 * NOISE_POINTS, 2 * NOISE_POINTS)
    for where, step, first, last, rate in OUTAGES:
        if segment == where and _active(first, last, day):
            rates[step] = rate + rng.uniform(-NOISE_POINTS, NOISE_POINTS)
    return rates


def build() -> dict[str, str]:
    rng = random.Random(SEED)
    rows = []
    for offset in range(DAYS):
        day = FIRST_DAY + dt.timedelta(days=offset)
        for segment, (carts, base) in SEGMENTS.items():
            volume = carts * WEEKDAY[day.weekday()] * (SALE_CARTS if _active(*SALE_DAYS, day) else 1)
            counts = [round(volume * rng.uniform(0.95, 1.05))]
            for rate in _rates(segment, day, base, rng):
                counts.append(round(counts[-1] * rate / 100))
            for step, count in zip(facts.FUNNEL_STEPS, counts):
                row = {"date": day.isoformat(), "device": segment[0], "browser": segment[1], "step": step}
                rows.append([*row.values(), count * 2 if facts.funnel_double_fired(row) else count])
        if day >= BOT_FIRST_DAY:
            rows.append([day.isoformat(), "desktop", facts.FUNNEL_BOT_BROWSER, "cart", rng.randint(*BOT_CARTS)])
    files = {
        "analysis_rules.md": RULES_MD,
        "release_log.md": RELEASE_LOG_MD,
        "suspected_causes.md": CAUSES_MD,
        "funnel_daily.csv": _csv_text(["date", "device", "browser", "step", "count"], rows),
    }
    _check(files)
    return files


def _check(files: dict[str, str]) -> None:
    """Refuse data in which a planted effect is missing or an unplanted one appeared."""
    rows = list(csv.DictReader(io.StringIO(files["funnel_daily.csv"])))
    counts = facts.funnel_counts(rows)
    assert facts.funnel_breaks(counts) == [
        {"segment": BROKEN[0], "step": "order", "first_day": BREAK_DAY.isoformat()}], facts.funnel_breaks(counts)
    steps = {name: index for index, name in enumerate(facts.FUNNEL_STEPS[1:])}
    below = {(BROKEN[0], 2, (FIRST_DAY + dt.timedelta(days=offset)).isoformat())
             for offset in range((BREAK_DAY - FIRST_DAY).days, DAYS)}
    for where, step, first, last, _rate in OUTAGES:
        below |= {(where, step, (first + dt.timedelta(days=offset)).isoformat()) for offset in range((last - first).days + 1)}
    reference = [date for date in sorted(counts[BROKEN[0]])
                 if facts.FUNNEL_REFERENCE_WEEK[0] <= date <= facts.FUNNEL_REFERENCE_WEEK[1]]
    margin = Fraction(1, 200)   # every look-alike stays at least half a point clear of its line
    for segment, days in counts.items():
        for step, index in steps.items():
            low = facts._step_rate(days, reference, step) - Fraction(facts.FUNNEL_RANGE_POINTS, 100)
            for date in sorted(days):
                rate = facts._step_rate(days, [date], step)
                if (segment, index, date) in below:
                    assert rate < low - margin, (segment, step, date)
                else:
                    assert rate >= low + margin, (segment, step, date, float(rate), float(low))
    # Left doubled, the Safari payment rows put desktop and tablet Safari below their order range
    # from the first doubled day to the end: two breaks that are not there.
    careless = facts.funnel_breaks(facts.funnel_counts(rows, halve=False))
    assert {(item["segment"], item["first_day"]) for item in careless if item["step"] == "order"} == {
        (BROKEN[0], BREAK_DAY.isoformat()), (("desktop", "Safari"), _PAYMENT_DAYS[0]),
        (("tablet", "Safari"), _PAYMENT_DAYS[0])}, careless


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
