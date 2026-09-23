An attribution sensitivity analysis was performed on the materialized journey dataset (`inbox/order-journeys.csv`).

### Data Cleaning & Integrity Gate
- **Raw records:** 14 rows.
- **Deduplication:** Order `O-009` was present twice with identical values (`$170`, `Meta` → `Paid Search` → `Email`). One instance was removed, leaving **13 unique orders**.
- **Net Revenue:** Retaining the negative refund for `O-013` (`-$120`), total unique-order net revenue is **$1,430.00**.
- **Direct-only:** Order `O-012` (`$100`, `Direct`) contains no marketing touches and is maintained as unattributed Direct revenue.

---

### 1. Reconciliation Under Each Model

Reconciling all unique-order net revenue against total dataset revenue ($1,430.00):

| Component | First-Touch (FT) Revenue | FT Share (%) | Last-Touch (LT) Revenue | LT Share (%) |
|---|---|---|---|---|
| **Meta** | $450.00 | 31.47% | $400.00 | 27.97% |
| **Paid Search** | $380.00 | 26.57% | $300.00 | 20.98% |
| **Email** | $290.00 | 20.28% | $630.00 | 44.06% |
| **Paid Channel Subtotal** | **$1,120.00** | **78.32%** | **$1,330.00** | **93.01%** |
| **Organic** | $210.00 | 14.69% | $0.00 | 0.00% |
| **Direct-only (Unattributed)** | $100.00 | 6.99% | $100.00 | 6.99% |
| **Total Net Revenue** | **$1,430.00** | **100.00%** | **$1,430.00** | **100.00%** |

#### Audit Arithmetic:
- **First-Touch:**
  - Meta: $120 (`O-001`) + $80 (`O-002`) + $200 (`O-005`) + $170 (`O-009`) - $120 (`O-013`) = **$450.00**
  - Paid Search: $150 (`O-003`) + $90 (`O-006`) + $140 (`O-010`) = **$380.00**
  - Email: $130 (`O-007`) + $160 (`O-011`) = **$290.00**
  - Paid Subtotal: $450.00 + $380.00 + $290.00 = **$1,120.00**
  - Organic: $100 (`O-004`) + $110 (`O-008`) = **$210.00**
  - Direct-only: $100 (`O-012`) = **$100.00**
  - Total: $1,120.00 + $210.00 + $100.00 = **$1,430.00**
- **Last-Touch:**
  - Meta: $100 (`O-004`) + $140 (`O-010`) + $160 (`O-011`) = **$400.00**
  - Paid Search: $80 (`O-002`) + $90 (`O-006`) + $130 (`O-007`) = **$300.00**
  - Email: $120 (`O-001`) + $150 (`O-003`) + $200 (`O-005`) + $110 (`O-008`) + $170 (`O-009`) - $120 (`O-013`) = **$630.00**
  - Paid Subtotal: $400.00 + $300.00 + $630.00 = **$1,330.00**
  - Organic: **$0.00** (no customer journey concluded on Organic)
  - Direct-only: $100 (`O-012`) = **$100.00**
  - Total: $1,330.00 + $0.00 + $100.00 = **$1,430.00**

---

### 2. Paid Channel Performance & ROAS Comparison

Each channel had **$600.00** of spend:

| Channel | Spend | FT Net Revenue | FT ROAS | LT Net Revenue | LT ROAS | Net Revenue Delta (LT − FT) |
|---|---|---|---|---|---|---|
| **Meta** | $600.00 | $450.00 | **0.75x** ($450/$600) | $400.00 | **0.67x** ($400/$600) | -$50.00 |
| **Paid Search** | $600.00 | $380.00 | **0.63x** ($380/$600) | $300.00 | **0.50x** ($300/$600) | -$80.00 |
| **Email** | $600.00 | $290.00 | **0.48x** ($290/$600) | $630.00 | **1.05x** ($630/$600) | +$340.00 |
| **Total Paid** | **$1,800.00** | **$1,120.00** | **0.62x** | **$1,330.00** | **0.74x** | **+$210.00** |

---

### 3. Winning Paid Channel Under Each Model

- **First-Touch Winner:** **Meta**
  - **$450.00** net revenue | **0.75x ROAS**
  - Initiates the largest volume of eventually converting journeys (5 of 13 unique journeys).
- **Last-Touch Winner:** **Email**
  - **$630.00** net revenue | **1.05x ROAS**
  - Closes the highest volume of orders (6 of 13 unique journeys), capturing 44.06% of all revenue.

---

### 4. Budget Recommendations

#### A. Conclusions Robust to the Attribution Model
1. **The Paid Media Program is Operating at an Overall Loss:** Blended ROAS is **0.62x** (FT) and **0.74x** (LT). Across all $1,800 in spend, the business is failing to break even on gross revenue, before considering COGS or fulfillment.
2. **Paid Search Underperforms in Both Models:** Paid Search fails to deliver acceptable efficiency regardless of lens—generating **0.63x ROAS** as an opener and dropping to **0.50x ROAS** as a closer.
3. **High Channel Interdependence:** Journeys show strong handoffs (e.g., Meta initiating into Email closers on `O-001`, `O-005`, `O-009`, `O-013`). Neither channel functions independently.

#### B. Conclusions Sensitive to the Attribution Model
1. **Email’s Apparent Profitability:** Email appears profitable under Last-Touch (**1.05x ROAS**), but is deeply underwater under First-Touch (**0.48x ROAS**). It relies heavily on top-of-funnel discovery funded by Meta and Organic (`O-008`).
2. **Meta’s Relative Role:** Under First-Touch, Meta is the top-performing acquisition engine; under Last-Touch, it loses revenue share to mid- and bottom-funnel touchpoints.

#### C. Budget Allocations
- **Cut Paid Search Immediately:** Reduce Paid Search spend by 50% ($300) or pause non-brand keyword groups. It consistently ties for worst efficiency and bleeds capital.
- **Do Not Scale Email Budget Based on Last-Touch ROAS:** Email’s 1.05x LT ROAS is an artifact of harvesting leads brought in by other channels. Pumping more paid budget into Email software or sponsored blasts will not generate proportional returns if upstream acquisition shrinks.
- **Fix Funnel Handoff and Reinvest in Meta:** Meta demonstrates top-of-funnel demand capture (0.75x FT ROAS), but suffers from post-click drop-offs and a full refund (`O-013` -$120). Audit Meta ad creative, product-fit messaging, and email welcome sequences before scaling.

---

### 5. Assumptions & Critical Data Limitation

#### Explicit Assumptions:
1. **Equal Attribution Weights:** Single-touch models assign 100% credit to the boundary interaction and 0% to intermediate assist touches (e.g., Paid Search in `O-009` receives zero credit under both FT and LT).
2. **Direct Discounting:** `Direct` interactions represent navigational or brand-recall behavior by an already engaged buyer, rather than a distinct acquisition driver.
3. **Uniform Attribution Window:** All logged touches are assumed to fall within an active, relevant conversion window.

#### Critical Limitation: Lack of Incrementality & Search Query Intent (Brand vs. Non-Brand)
- **The Causation Gap:** Attribution is accounting, not causation. We do not know what fraction of orders would have converted via Organic or Direct in the absence of Paid Search or Email. Specifically:
  - If Paid Search is bidding on **branded navigational keywords**, its true incremental lift is likely near-zero (cannibalizing Organic search `O-004`/`O-008`).
  - Similarly, Email may merely be capturing existing customers who would have purchased anyway.
- **How Resolving It Changes the Recommendation:**
  - **Holdout Test Outcome A (Search is Brand Cannibalization):** If a geo/audience holdout confirms zero incremental lift for Paid Search, the recommendation is to **cut Paid Search spend to $0**, eliminating $600 in waste.
  - **Holdout Test Outcome B (Meta has Low Incrementality, Search is Incremental Non-Brand):** If Meta impressions merely overlap with Organic traffic while Search drives genuinely new customer acquisition, budget should be redirected to non-brand Search and away from broad Meta prospecting.

---
*A copy of this evaluation and the audit ledger has also been saved to:*  
`drafts/report.md`