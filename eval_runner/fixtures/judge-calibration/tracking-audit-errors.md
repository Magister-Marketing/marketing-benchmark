# Tracking & Measurement Audit Report: Loam & Ledger
**Prepared for:** Head of Growth, Web Engineering, and Finance  
**Scope:** Active Campaign URLs (`active_links.csv`), GTM Container (`GTM-K4WPD2`), GA4 Property (`G-8B21XQ4`), and Measurement Standards (v3)  
**Deliverable File:** `/workspace/drafts/deliverable.md`

---

### Executive Summary

Ahead of unlocking Q4 performance budgets, we audited Loam & Ledger's tracking setup across active campaign links, GTM container tags, triggers, Consent Mode settings, and event parameters against your agreed measurement standards.

Our findings explain every unexplained symptom reported in the growth memo:
1. **Purchase Count Explosion & Phantom Orders:** GA4 purchase overcounting (512 in GA4 vs. 284 in Shopify) and purchases recorded during payment outages stem from **two compounding defects**: a rogue click-triggered purchase tag firing on button tap (Tag 3) and an overbroad regex trigger (Tag 2 / Tag 6) firing prematurely on `/order-confirmation-pending`.
2. **CAD Revenue Inflation:** Hardcoded `"USD"` currency parameters on Tag 2 and Tag 6 force GA4 to treat CAD order values as USD, inflating Canadian revenue by ~35% after platform currency conversion.
3. **Email Attribution Failure:** Newsletter links deployed with unencrypted `http://` cause server-side 301 redirects that strip UTM query strings and referrers, dumping newsletter sessions into Direct.
4. **Channel & Campaign Fragmentation:** Casing errors (`CPC`), legacy source naming (`facebook`), duplicate query parameters, and unencoded spaces fragment Paid Search, Meta, and Cart Recovery across separate GA4 report lines.
5. **Add-to-Cart Funnel Blindspot:** Renaming the event to PascalCase `Add to Cart` broke standard GA4 ecommerce funnels and CRO exploration reports.
6. **EU/UK Consent Mode Non-Compliance:** `analytics_storage` is defaulting to `granted` for EEA/UK visitors, exposing the business to GDPR/PECR regulatory enforcement.

---

### Prioritized Audit Findings (Ordered by Impact)

```
Impact Hierarchy:
[CRITICAL] P0: Flawed Conversion & Revenue Measurement (Purchases, Currency, Legal)
[HIGH]     P1: Broken Channel Attribution & Funnel Visibility (Email, Add-to-Cart)
[MEDIUM]   P2: Taxonomy Inconsistencies & Reporting Fragmentation (UTM Casing, Syntax)
```

---

#### 1. Speculative Click-Based Purchase Tag Firing on Unsettled Checkouts (CRITICAL — P0)
- **Exact Location:** GTM Tag 3 (`GA4 Event — purchase (checkout button)`), Trigger: Click — All Elements matching CSS selector `#place-order-btn`.
- **Why It Is Wrong:** Directly violates Measurement Standards: *"Exactly one purchase event fires per order, on the order confirmation page only, carrying transaction_id, value, currency, and items."* Firing a purchase event on a button click records user intent rather than a completed transaction. Furthermore, Tag 3 completely omits `transaction_id`, making transaction deduplication in GA4 impossible.
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of the 80% purchase count inflation:** GA4 logged 512 purchases while Shopify logged only 284. Every validation error (e.g., expired card, invalid address), accidental double-click, or abandoned payment attempt fired a complete purchase event.
  - **Explains purchases during payment outages:** On 2026-08-04, users clicking `#place-order-btn` triggered purchases in GA4 even when the payment processor was down and transactions were rejected.
  - **Explains revenue outpacing settled book revenue:** Phantom orders with uncollected revenue inflated GA4's top-line revenue figures.
- **Concrete Fix:** Immediately pause and delete GTM Tag 3. Purchase events must never fire on button clicks.

---

#### 2. Overbroad Regex Trigger Firing on Pending & Failed Orders (CRITICAL — P0)
- **Exact Location:** GTM Trigger for Tag 2 (`GA4 Event — purchase`) and Tag 6 (`Meta Pixel — purchase`): Page View where Page Path matches RegEx `^/order-confirmation`.
- **Why It Is Wrong:** RegEx `^/order-confirmation` is an unanchored prefix match. As documented in site structure notes, asynchronous payment methods (Interac, PayPal) first route users to `/order-confirmation-pending` while payment processes. Because `/order-confirmation-pending` begins with `/order-confirmation`, Tag 2 and Tag 6 fire immediately.
- **Measurement Impact & Connected Symptoms:**
  - **Double Counting:** If the payment succeeds, the page reloads to `/order-confirmation`, firing Tag 2 and Tag 6 a second time.
  - **False Positives on Payment Failure:** If the payment fails and routes to `/payment-failed`, the purchase has already been logged in both GA4 and Meta.
  - **Drives discrepancy:** Contributes heavily to GA4's 512 orders and Meta's 205 reported conversions during gateway downtime.
- **Concrete Fix:** Modify the trigger condition for Tag 2 and Tag 6 from RegEx match to exact string match: **Page Path equals `/order-confirmation`** (or regex `^/order-confirmation$`). Ensure the Data Layer also pushes `transaction_id` so any accidental page refresh is deduplicated.

---

#### 3. Hardcoded USD Currency on Multi-Currency Storefront (CRITICAL — P0)
- **Exact Location:** GTM Tag 2 (`GA4 Event — purchase`), Tag 3, and Tag 6 (`Meta Pixel — purchase`): Parameter `currency: "USD"`.
- **Why It Is Wrong:** Violates Measurement Standards: *"currency reflects the order's actual currency. The ca. storefront transacts in CAD."* Both storefronts share one GTM container, but Tag 2 hardcodes static `"USD"` rather than referencing dynamic Data Layer values (unlike Tag 5, which correctly uses `{{DLV - currency}}`).
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of Canadian revenue inflation:** When a Canadian buyer completes a 100 CAD order on `ca.loamandledger.com`, GA4 records 100 USD. GA4 then converts that 100 "USD" into the reporting currency at prevailing exchange rates (~1.35 CAD per USD), causing finance to observe that CAD-storefront revenue in GA4 reads ~35% higher than actual settled CAD book revenue.
- **Concrete Fix:** In GTM Tag 2 and Tag 6, change parameter `currency` from hardcoded `"USD"` to the Data Layer Variable: `{{DLV - currency}}`.

---

#### 4. Non-Compliant Consent Mode v2 Default in EEA & UK (CRITICAL — P0 / Compliance)
- **Exact Location:** GTM Consent Initialization Tag: EEA + UK regional default set to `analytics_storage: "granted"`, `ad_storage: "denied"`.
- **Why It Is Wrong:** Violates Measurement Standards: *"Defaults for visitors in the EEA/UK: analytics_storage: denied and ad_storage: denied until the banner grants them."* Setting analytics storage to `granted` prior to user consent violates the EU ePrivacy Directive, GDPR, and UK PECR regulations.
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of legal compliance flag:** Outside legal counsel correctly noted that analytics cookies (`_ga`, `_ga_*`) were written upon initial page load before the visitor interacted with Cookiebot.
  - Exposes the business to regulatory sanctions and invalidates European consent signals.
- **Concrete Fix:** In GTM Consent Initialization, update the EEA + UK regional setting to:
  `analytics_storage: "denied"` and `ad_storage: "denied"`.

---

#### 5. Insecure HTTP Protocol on Klaviyo Newsletter Links (HIGH — P1)
- **Exact Location:** `active_links.csv`, Rows 12 & 13:
  - Row 12: `http://www.loamandledger.com/collections/new?utm_source=klaviyo&utm_medium=email&utm_campaign=2026q3-weekly-newsletter`
  - Row 13: `http://www.loamandledger.com/collections/bestsellers?utm_source=klaviyo&utm_medium=email&utm_campaign=2026q3-weekly-newsletter`
- **Why It Is Wrong:** Violates Measurement Standards: *"All destination URLs are https:// on www.loamandledger.com"*.
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of broken email acquisition:** Cloudflare/Shopify 301-redirects `http://` traffic to `https://`. HTTP-to-HTTPS redirects frequently strip UTM query parameters and drop browser referrers.
  - Explains why Klaviyo reported high click volume while GA4 session acquisition recorded almost no newsletter traffic, misclassifying visitors under `(direct) / (none)`. Flows (Rows 14 & 15) were built with `https://`, which is why flow attribution remained intact.
- **Concrete Fix:** Update Klaviyo master newsletter templates so all links explicitly use `https://`. Audit redirect rules on the web server to ensure existing query strings are preserved (`$is_args$args`).

---

#### 6. Non-Standard Event Name Breaking Add-to-Cart Tracking (HIGH — P1)
- **Exact Location:** GTM Tag 4: Event Name set to `Add to Cart` (Trigger: Custom Event `add_to_cart_clicked`).
- **Why It Is Wrong:** Violates Measurement Standards: *"GA4 event names are snake_case (begin_checkout, add_to_cart)"*. Renamed during the theme migration "for readability."
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of empty add-to-cart reports:** GA4 standard ecommerce reports, monetization dashboards, and funnel explorations natively expect the reserved standard event `add_to_cart`. Custom PascalCase names like `Add to Cart` are treated as generic custom events and completely ignored by standard ecommerce metrics.
  - Explains why the CRO agency's exploration funnel showed near-zero add-to-cart events post-migration despite healthy conversion rates.
- **Concrete Fix:** In GTM Tag 4, rename the GA4 Event Name field from `Add to Cart` to `add_to_cart`.

---

#### 7. Uppercase Medium Splitting Google Paid Search Channel Group (MEDIUM — P2)
- **Exact Location:** `active_links.csv`, Rows 1, 2, & 3:
  - Row 1: `https://www.loamandledger.com/collections/linen?utm_source=google&utm_medium=CPC&utm_campaign=2026q3-linen-prospecting`
  - Row 2: `https://www.loamandledger.com/collections/ceramics?utm_source=google&utm_medium=CPC&utm_campaign=2026q3-ceramics-prospecting`
  - Row 3: `https://www.loamandledger.com/collections/new?utm_source=google&utm_medium=CPC&utm_campaign=2026q3-newin-pmax`
- **Why It Is Wrong:** Violates Measurement Standards: *"All UTM parameter values are lowercase, always"* and `utm_medium` must be exact lowercase `cpc`.
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of Google Ads splitting into two row groups:** GA4's default channel group rules are case-sensitive. While `utm_medium=cpc` (used in Row 4 brand defense and Row 19 Canadian search) classifies into `Paid Search`, uppercase `utm_medium=CPC` falls into `Unassigned` or a separate channel bucket.
  - The media buyer saw two rows because the campaigns literally carried conflicting mediums (`cpc` vs `CPC`).
- **Concrete Fix:** Update the tracking templates in Google Ads for Linen Prospecting, Ceramics Prospecting, and New In PMax to use lowercase `utm_medium=cpc`.

---

#### 8. Deprecated Source Parameter Splitting Meta Acquisition (MEDIUM — P2)
- **Exact Location:** `active_links.csv`, Rows 5 & 7:
  - Row 5: `https://www.loamandledger.com/collections/linen?utm_source=facebook&utm_medium=paidsocial&utm_campaign=2026q3-linen-prospecting`
  - Row 7: `https://www.loamandledger.com/collections/bestsellers?utm_source=facebook&utm_medium=paidsocial&utm_campaign=2026q3-bestsellers-retargeting`
- **Why It Is Wrong:** Violates Measurement Standards: *"utm_source is the platform: google, meta, klaviyo... Historical note: we standardized on meta — not facebook — in v2."*
- **Measurement Impact & Connected Symptoms:**
  - Fragments Meta acquisition data across two disparate sources: `facebook / paidsocial` and `meta / paidsocial` (used in Rows 6, 8, 9, and 20). Prevents unified performance evaluation and blended ROAS reporting across Meta prospecting and retargeting.
- **Concrete Fix:** Update ad destination URLs in Meta Ads Manager for these two campaigns to use `utm_source=meta`.

---

#### 9. Duplicate Campaign Parameter Breaking Cart Recovery Reporting (MEDIUM — P2)
- **Exact Location:** `active_links.csv`, Row 8:
  - `https://www.loamandledger.com/cart?utm_source=meta&utm_medium=paidsocial&utm_campaign=2026q3-cart-recovery&utm_campaign=cart_recovery`
- **Why It Is Wrong:** Violates Measurement Standards: *"Every parameter appears at most once per URL"* and campaign naming syntax. The URL appends two conflicting `utm_campaign` keys.
- **Measurement Impact & Connected Symptoms:**
  - **Direct cause of unreadable cart-recovery reporting:** Different analytics parsers, session engines, and attribution models handle duplicate URL keys differently (some read the first instance `2026q3-cart-recovery`, others parse the last instance `cart_recovery`). As a result, the same ad spend appears split under two distinct campaign names in GA4.
- **Concrete Fix:** Clean the URL in Meta Ads Manager to:  
  `https://www.loamandledger.com/cart?utm_source=meta&utm_medium=paidsocial&utm_campaign=2026q3-cart-recovery`

---

#### 10. Unencoded Spaces in Summer Sale Campaign Name (MEDIUM — P2)
- **Exact Location:** `active_links.csv`, Row 9:
  - `https://www.loamandledger.com/collections/summer?utm_source=meta&utm_medium=paidsocial&utm_campaign=2026q3 summer sale`
- **Why It Is Wrong:** Violates Measurement Standards: *"format: <year>q<quarter>-<line>-<goal>, hyphen-separated, no spaces"*.
- **Measurement Impact & Connected Symptoms:**
  - Raw spaces are unpredictably encoded by ad networks and browsers into `%20` or `+`, creating fractured campaign dimension rows (`2026q3 summer sale`, `2026q3%20summer%20sale`, and `2026q3+summer+sale`) and breaking automated reporting filters.
- **Concrete Fix:** Update the ad URL in Meta Ads Manager to hyphenated syntax:  
  `https://www.loamandledger.com/collections/summer?utm_source=meta&utm_medium=paidsocial&utm_campaign=2026q3-summer-sale`

---

#### 11. Missing Source Parameter on Welcome Flow (MEDIUM — P2)
- **Exact Location:** `active_links.csv`, Row 14:
  - `https://www.loamandledger.com/collections/starter?utm_medium=email&utm_campaign=2026q3-welcome-flow`
- **Why It Is Wrong:** Violates Measurement Standards: `utm_source` is a required tracking parameter and must be `klaviyo`.
- **Measurement Impact & Connected Symptoms:**
  - In GA4 source/medium reporting, traffic arriving with `utm_medium=email` but no `utm_source` is assigned to `(not set) / email`.
- **Concrete Fix:** Update the link in Klaviyo Welcome Flow (Step 2) to include `utm_source=klaviyo`:  
  `https://www.loamandledger.com/collections/starter?utm_source=klaviyo&utm_medium=email&utm_campaign=2026q3-welcome-flow`

---

#### 12. Missing Transaction ID on Confirmation Page Purchase Tag (MEDIUM — P2)
- **Exact Location:** GTM Tag 2 (`GA4 Event — purchase (confirmation page)`).
- **Why It Is Wrong:** Violates Measurement Standards: *"carrying transaction_id, value, currency, and items."*
- **Measurement Impact & Connected Symptoms:**
  - Without `transaction_id`, GA4 cannot deduplicate purchases if a user reloads the confirmation page, returns to view their order status, or navigates back in browser history. This further inflates GA4 purchase counts.
- **Concrete Fix:** Add `transaction_id: {{DLV - transaction_id}}` to the parameter list of GTM Tag 2.

---

### What Was Checked and Found Clean (Trustworthy Systems)

To give the team full confidence in what can be trusted right now, we verified the following items and found them fully compliant:

1. **Active Campaign Links (12 of 22 fully compliant):**
   - **Row 4 (Google Brand Defense):** Perfectly formed (`https://`, lowercase `google`, lowercase `cpc`, hyphenated campaign `2026q3-brand-defense`).
   - **Row 6 (Meta Prospecting Table):** Fully conforming (`utm_source=meta`, `utm_medium=paidsocial`, standard campaign format).
   - **Rows 10 & 11 (TikTok Prospecting Linen & Ceramics):** Compliant Spark Ad links (`utm_source=tiktok`, `utm_medium=paidsocial`, standard taxonomy).
   - **Row 15 (Klaviyo Winback Flow):** Correct HTTPS scheme, standard `klaviyo` source, `email` medium, valid campaign taxonomy.
   - **Row 16 (Pinterest Prospecting Table):** Compliant pins link (`utm_source=pinterest`, `utm_medium=paidsocial`).
   - **Rows 17 & 18 (Affiliate Placements):** `domesticnotes.com` and `hearthreview.com` strictly follow affiliate standards (partner domain as source, `affiliate` as medium).
   - **Rows 19 & 20 (Canadian Storefront Search & Meta):** Fully conforming HTTPS links targeting `ca.loamandledger.com`, valid sources/mediums, and correct `-ca` market suffix.
   - **Rows 21 & 22 (Organic Social):** Instagram bio and Pinterest board links correctly use `organicsocial` medium and valid syntax.

2. **GA4 Configuration Tag (Tag 1):**
   - Measurement ID `G-8B21XQ4` is correctly placed on `Initialization — All Pages` with `send_page_view: true`. No duplicate or rogue config tags exist.

3. **Checkout Progression Tracking (Tag 5 — `begin_checkout`):**
   - Tag 5 strictly follows standards: valid `snake_case` event name, exact Page Path trigger (`/checkout`), and dynamic Data Layer parameter mappings (`cart_total`, `items`, and `{{DLV - currency}}`).

4. **Ecommerce Order Net Value Basis:**
   - Tag 2 correctly maps `value` to `{{DLV - order_total}}`, which is verified net of tax and shipping per finance's policy.

5. **Consent Mode v2 Rest-of-World Defaults:**
   - Non-EEA/UK visitor defaults in the Consent Initialization Tag are properly set to `granted` for both `analytics_storage` and `ad_storage`, exactly matching policy.

---

### Recommended Remediation Checklist (Pre-Q4 Launch)

1. **GTM Container:**
   - [ ] Delete Tag 3 (`purchase` on `#place-order-btn`).
   - [ ] Update Trigger for Tag 2 & Tag 6 to Page Path equals `/order-confirmation`.
   - [ ] Update Tag 2: Add `transaction_id: {{DLV - transaction_id}}`, set `currency: {{DLV - currency}}`.
   - [ ] Update Tag 6 (Meta Pixel): Set `currency: {{DLV - currency}}`.
   - [ ] Update Tag 4: Rename event to `add_to_cart`.
   - [ ] Update Consent Initialization Tag: Set EEA/UK `analytics_storage` to `denied`.
   - [ ] Preview, test via Tag Assistant / GA4 DebugView, and publish container version.

2. **Campaign URLs:**
   - [ ] Klaviyo: Update newsletter URLs to `https://` (Rows 12 & 13); add `utm_source=klaviyo` to Welcome Flow (Row 14).
   - [ ] Google Ads: Change `utm_medium=CPC` to lowercase `cpc` (Rows 1, 2, & 3).
   - [ ] Meta Ads: Update `utm_source=facebook` to `meta` (Rows 5 & 7); remove duplicate campaign parameter (Row 8); replace spaces with hyphens in summer sale (Row 9).