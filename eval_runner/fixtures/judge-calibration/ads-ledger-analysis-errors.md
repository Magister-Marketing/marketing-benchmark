### Quarterly Paid-Media Performance Review: Verra Threads (Q1–Q2 2026)
**Evaluation Window:** 14 Weeks (2026-03-02 through 2026-06-07)  
**Dataset Analyzed:** `ads_daily.csv` (784 adset-day observations across 8 active adsets)

---

### Executive Summary

Across the 14-week period, Verra Threads deployed **$64,460.44** in paid media spend across three campaigns (`brand-search`, `retargeting`, and `prospecting-broad`), generating **$244,515.01** in gross revenue and **$230,109.60** in net revenue across **2,541 net conversions** (2,697 gross conversions minus 156 refunded orders). 

Account-wide, blended performance appears healthy on the surface:
- **Blended Net ROAS:** **3.57x** ($230,109.60 net revenue / $64,460.44 spend)
- **Blended Net CPA:** **$25.37** ($64,460.44 spend / 2,541 net conversions)
- **Final 28-Day Net ROAS:** **3.09x** ($57,268.95 net revenue / $18,538.28 spend)

However, top-line performance masks severe operational inefficiencies:
1. **Prospecting Funnel Collapse:** `prospecting-broad` was profitable in Weeks 1–9 (1.78x Net ROAS, $46.81 Net CPA), but experienced severe fatigue starting in Week 10 (Net ROAS dropped below 1.0x to 0.82x), culminating in a complete collapse by Week 14 (0 conversions, $0 revenue on $1,873.93 spend). Total wasted spend on zero-conversion adset-days reached **$10,228.41**, with **$9,326.66 (91.2%)** concentrated in prospecting.
2. **Abnormal Return Rates in `rt-lookalike`:** While bottom-funnel retargeting generated **5.49x Net ROAS**, `rt-lookalike` suffered an alarming **21.55% refund rate on revenue** ($8,470.84 refunded out of $39,305.30 gross revenue across 90 refunded orders), representing **58.8% of all refunded revenue** across the brand.

---

### Full 14-Week Performance by Campaign & Adset

```
Campaign / Adset         Spend ($)     Gross Rev ($)   Ref Rev ($)    Net Rev ($)   Gross Conv  Ref Conv  Net Conv  Net ROAS  Net CPA ($)  Wasted Spend ($)
brand-search             $21,048.77     $101,413.75     $1,702.38     $99,711.37        1,126        19     1,107     4.74x      $19.01           $278.52
 ├─ bs-exact             $11,650.09      $59,835.38       $973.16     $58,862.22          654        11       643     5.05x      $18.12             $0.00
 └─ bs-phrase             $9,398.68      $41,578.37       $729.22     $40,849.15          472         8       464     4.35x      $20.26           $278.52
retargeting              $17,706.30     $108,514.88    $11,291.45     $97,223.43        1,158       120     1,038     5.49x      $17.06           $623.23
 ├─ rt-cart               $4,796.95      $36,413.29     $1,719.76     $34,693.53          380        18       362     7.23x      $13.25           $346.61
 ├─ rt-visitors           $5,620.05      $32,796.29     $1,100.85     $31,695.44          364        12       352     5.64x      $15.97           $212.65
 └─ rt-lookalike          $7,289.30      $39,305.30     $8,470.84     $30,834.46          414        90       324     4.23x      $22.50            $63.97
prospecting-broad        $25,705.37      $34,586.38     $1,411.58     $33,174.80          413        17       396     1.29x      $64.91         $9,326.66
 ├─ pb-interest          $10,855.88      $16,486.68       $483.42     $16,003.26          197         6       191     1.47x      $56.84         $3,145.10
 ├─ pb-lookalike          $8,698.22      $12,643.72       $610.24     $12,033.48          148         7       141     1.38x      $61.69         $2,707.40
 └─ pb-video              $6,151.27       $5,455.98       $317.92      $5,138.06           68         4        64     0.84x      $96.11         $3,474.16
Total Account            $64,460.44     $244,515.01    $14,405.41    $230,109.60        2,697       156     2,541     3.57x      $25.37        $10,228.41
```

---

### What Is Working

1. **High-Efficiency Conversion Harvesting (`brand-search` & Site Retargeting):**
   - **`rt-cart`** is the top-performing asset in the portfolio, generating **7.23x Net ROAS** at a **$13.25 Net CPA**, converting high-intent cart abandoners with low post-purchase refund rates (4.72% on revenue).
   - **`rt-visitors`** delivers consistent, profitable remarketing with **5.64x Net ROAS** and a **$15.97 Net CPA**, with refund rates sitting at a baseline of 3.36%.
   - **`brand-search`** captures intent efficiently, yielding **$99,711.37 in net revenue** at **4.74x Net ROAS** and **$19.01 Net CPA**. Notably, `bs-exact` delivered zero wasted spend across all 98 days with a 1.63% refund rate.
2. **Resilience of Account-Wide Returns Over the Final 28 Days:**
   - From May 11 to June 7 (Weeks 11–14), account Net ROAS held at **3.09x** ($57,268.95 net revenue on $18,538.28 spend) solely because brand search ($26,897.66 net revenue; 4.88x ROAS) and retargeting ($28,137.97 net revenue; 5.28x ROAS) sustained cash flow while prospecting faltered.

---

### What Is Broken

1. **Prospecting Fatigue & Funnel Collapse (Weeks 10–14):**
   - **The Week 10 Inflexion:** Through Weeks 1–9, `prospecting-broad` averaged **1.78x Net ROAS** and **$46.81 Net CPA**. In Week 10, weekly Net ROAS fell below 1.0x for the first time to **0.82x** ($1,486.99 net revenue on $1,821.35 spend).
   - **The Collapse:** Weekly Net ROAS degraded continuously:
     - Week 10: 0.82x ($1,486.99 net revenue, 17 net conversions)
     - Week 11: 0.24x ($434.88 net revenue, 5 net conversions)
     - Week 12: 0.67x ($1,213.32 net revenue, 14 net conversions)
     - Week 13: 0.31x ($583.09 net revenue, 7 net conversions)
     - Week 14: **0.00x ($0.00 net revenue, 0 net conversions on $1,873.93 spend)**
   - **Diagnostic Breakdown (CTR vs. CVR):** Comparing W1–9 against W10–14 shows that outbound CTR remained steady (1.59% in W1–9 vs. 1.58% in W10–14) and CPC held flat ($0.93 vs. $0.94). However, on-site conversion rate collapsed from **2.06% down to 0.47%** in W10–14 (and 0.00% in W14). Users continue to click, but landing page traffic is no longer converting due to audience saturation and unrefreshed creative/offers.
   - **`pb-video` Underperformance:** `pb-video` was unprofitable over the full quarter (**0.84x Net ROAS**, **$96.11 Net CPA**), generating 56 zero-conversion days out of 98 (57.1% failure rate) and driving **$3,474.16 in wasted spend**.
2. **Wasted Spend Concentration:**
   - Account-wide wasted spend on adset-days with 0 conversions totaled **$10,228.41** (15.87% of total budget).
   - **$9,326.66 (91.18%)** of all wasted spend came from `prospecting-broad` ($3,474.16 in `pb-video`, $3,145.10 in `pb-interest`, and $2,707.40 in `pb-lookalike`). In Week 14 alone, 100% of prospecting spend ($1,873.93) was wasted.
3. **The `rt-lookalike` Refund Anomaly:**
   - `rt-lookalike` generated **$8,470.84 in refunds** across 90 refunded orders (21.55% of its gross revenue; 21.74% of its conversions).
   - In comparison, `rt-visitors` had a 3.36% refund rate ($1,100.85) and `rt-cart` had 4.72% ($1,719.76).
   - Buyers acquired through `rt-lookalike` return apparel at **5x to 6x the rate** of actual site visitors and cart abandoners, indicating either aggressive discount-seeking behavior, misleading creative sizing expectations, or lower purchase qualification.

---

### Action Plan for Next Week

1. **Restructure Prospecting Immediately:**
   - **Pause `pb-video`:** Immediately pause `pb-video` to stop the weekly bleeding of ~$440 in zero-ROAS spend.
   - **Throttle Daily Prospecting Spend:** Reduce `pb-interest` and `pb-lookalike` daily budgets by 60% (from ~$267/day combined down to ~$100/day) as a defensive holding action while new creative is produced.
   - **Deploy Creative & Offer Reset:** Launch 3 net-new creative angles (fit/fabric quality breakdown, lifestyle UGC, seasonal layering) to overcome audience ad fatigue.
2. **Audit and Fix `rt-lookalike`:**
   - Cross-reference Shopify return data for `rt-lookalike` purchases to identify if specific SKUs or sizes drive the 21.6% return rate.
   - Introduce prominent sizing charts and fit guides into `rt-lookalike` landing pages and ad copy.
   - Shift $250/day from `rt-lookalike` into `rt-cart` and `rt-visitors`, which produce superior net returns with low refunds.
3. **Reallocate Capital to High-Margin Channels:**
   - Reallocate ~$1,200/week from depleted prospecting into `rt-cart` (7.23x ROAS) and `bs-exact` (5.05x ROAS), where conversion intent and post-purchase retention are strongest.

---

A1: 25.37
A2: 10228.41
A3: 10
A4: 8470.84
A5: 3.09