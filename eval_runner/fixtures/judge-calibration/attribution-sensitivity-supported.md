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
Paid Search is not the descriptive winner under either rule. It ranks second
under first-touch and third under last-touch; it does not tie for worst in both.
The paid-channel subtotal is below spend under both accounting rules. Neither
observation establishes incremental revenue, profit or a causal budget decision.

#### B. Conclusions Sensitive to the Attribution Model
Meta has the highest attributed ROAS under first-touch; Email has the highest
under last-touch. There is no universal Meta-versus-Email winner. Multi-channel
journeys show recorded handoffs, not proof that any channel caused a purchase.

#### C. Budget Allocations
Hold current budgets while obtaining evidence of incremental returns. Do not
cut Search or scale Meta/Email solely because of these accounting allocations.
Request margin data and design a randomized, funded holdout or defensible geo
experiment before proposing a decisive reallocation. Test scope and cost require
approval; this report does not allocate additional funds.

---

### 5. Assumptions & Critical Data Limitation
Single-touch rules assign all credit to one recorded touch and none to assists.
The requested rules ignore Direct touches when marketing touches are present;
this is an accounting convention, not a finding about Direct's causal role.
All supplied touches are treated as in scope; conversion-window completeness is
not independently verified.

The missing evidence is incremental revenue by channel and its uncertainty,
plus margins and capacity. If a valid holdout finds Search contributes no
incremental profit, a reduction may be warranted. If it demonstrates profitable
incremental Search demand and weaker returns elsewhere, a shift toward Search
may instead be warranted. Until then the recommended allocation is unchanged.
