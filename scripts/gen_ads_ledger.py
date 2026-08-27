#!/usr/bin/env python3
"""Generate the ads-ledger-analysis fixture CSV and its ground truth.

Deterministic (seeded): re-running always reproduces the identical CSV, so the
task JSON's `near` targets stay verifiable. A unit test recomputes every
ground-truth value from the shipped CSV and asserts the task JSON matches —
regenerate with a different seed or shape and that test names the drift.

The data plants four findings a competent analyst should surface:
  - prospecting-broad decays: its weekly net ROAS crosses below 1.0 mid-window
  - pb-video stops converting entirely for the final 28 days (wasted spend)
  - rt-lookalike refunds ~22% of conversions (the refund drag)
  - brand-search stays healthy throughout (the control nobody should touch)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = REPO_ROOT / "eval_runner" / "fixtures" / "ads-ledger" / "ads_daily.csv"

START = dt.date(2026, 3, 2)  # a Monday; 14 exact Monday-start weeks
DAYS = 98
FINAL_WINDOW_START = DAYS - 28  # day index 70 => last 28 dates

# adset -> (campaign, daily spend base, cvr base, aov, refund_rate)
ADSETS = {
    "bs-exact":     ("brand-search",      120.0, 0.055, 92.0, 0.02),
    "bs-phrase":    ("brand-search",       95.0, 0.048, 88.0, 0.02),
    "pb-interest":  ("prospecting-broad", 110.0, 0.021, 84.0, 0.04),
    "pb-video":     ("prospecting-broad",  62.0, 0.016, 80.0, 0.04),
    "pb-lookalike": ("prospecting-broad",  88.0, 0.019, 86.0, 0.04),
    "rt-visitors":  ("retargeting",        58.0, 0.062, 90.0, 0.03),
    "rt-lookalike": ("retargeting",        74.0, 0.051, 95.0, 0.22),
    "rt-cart":      ("retargeting",        49.0, 0.078, 97.0, 0.04),
}


def generate_rows() -> list[dict]:
    rng = random.Random(7)
    rows = []
    for day in range(DAYS):
        date = START + dt.timedelta(days=day)
        week = day // 7  # 0-based
        for adset, (campaign, spend_base, cvr, aov, refund_rate) in ADSETS.items():
            spend = round(spend_base * rng.uniform(0.82, 1.18), 2)
            impressions = int(spend * rng.uniform(55, 80))
            clicks = int(impressions * rng.uniform(0.010, 0.022))

            eff_cvr = cvr
            # prospecting-broad decays: strong early, underwater late.
            if campaign == "prospecting-broad":
                eff_cvr = cvr * (1.55 - 0.115 * week)
            conversions = sum(
                1 for _ in range(clicks) if rng.random() < max(eff_cvr, 0.0)
            )
            # pb-video dies completely for the final 28 days while spend keeps
            # running — the classic unwatched always-on adset.
            if adset == "pb-video" and day >= FINAL_WINDOW_START:
                conversions = 0

            revenue = round(conversions * aov * rng.uniform(0.86, 1.14), 2)
            refunded = sum(1 for _ in range(conversions) if rng.random() < refund_rate)
            refunded_revenue = (
                round(revenue / conversions * refunded, 2) if conversions else 0.0
            )
            rows.append({
                "date": date.isoformat(),
                "campaign": campaign,
                "adset": adset,
                "spend_usd": f"{spend:.2f}",
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "revenue_usd": f"{revenue:.2f}",
                "refunded_conversions": refunded,
                "refunded_revenue_usd": f"{refunded_revenue:.2f}",
            })
    return rows


def ground_truth(rows: list[dict]) -> dict:
    spend = sum(float(r["spend_usd"]) for r in rows)
    conv = sum(int(r["conversions"]) for r in rows)
    refunded = sum(int(r["refunded_conversions"]) for r in rows)

    q1 = spend / (conv - refunded)
    q2 = sum(float(r["spend_usd"]) for r in rows if int(r["conversions"]) == 0)

    q3 = None
    for week in range(14):
        lo = START + dt.timedelta(days=week * 7)
        hi = lo + dt.timedelta(days=7)
        wk = [r for r in rows
              if r["campaign"] == "prospecting-broad"
              and lo.isoformat() <= r["date"] < hi.isoformat()]
        net = sum(float(r["revenue_usd"]) - float(r["refunded_revenue_usd"]) for r in wk)
        wspend = sum(float(r["spend_usd"]) for r in wk)
        if net / wspend < 1.0:
            q3 = week + 1
            break

    by_adset: dict[str, float] = {}
    for r in rows:
        by_adset[r["adset"]] = by_adset.get(r["adset"], 0.0) + float(
            r["refunded_revenue_usd"]
        )
    worst = max(by_adset, key=by_adset.get)
    ranked = sorted(by_adset.values(), reverse=True)

    final_lo = (START + dt.timedelta(days=FINAL_WINDOW_START)).isoformat()
    final = [r for r in rows if r["date"] >= final_lo]
    q5 = (
        sum(float(r["revenue_usd"]) - float(r["refunded_revenue_usd"]) for r in final)
        / sum(float(r["spend_usd"]) for r in final)
    )

    return {
        "q1_blended_cpa": round(q1, 2),
        "q2_wasted_spend": round(q2, 2),
        "q3_first_underwater_week": q3,
        "q4_worst_refund_adset": worst,
        "q4_worst_refund_amount": round(by_adset[worst], 2),
        "q4_margin_over_runner_up": round(ranked[0] - ranked[1], 2),
        "q5_final_28d_net_roas": round(q5, 2),
        "final_window_start": final_lo,
        "total_rows": len(rows),
    }


def main() -> None:
    rows = generate_rows()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    truth = ground_truth(rows)
    print(f"wrote {OUT_CSV} ({OUT_CSV.stat().st_size:,} bytes, {len(rows)} rows)")
    print(json.dumps(truth, indent=2))


if __name__ == "__main__":
    main()
