# Symptoms we can't explain — running memo (head of growth, 2026-08-18)

Collected ahead of the Q4 scale-up. These are observations, not diagnoses.

- **Purchase counts disagree everywhere.** Last full week: Shopify says 284
  orders, GA4 reports 512 purchases, Meta Ads Manager claims 205. GA4 being
  ~80% above Shopify is new since early June.
- **GA4 shows purchases on days with payment incidents.** On 2026-08-04 the
  payment provider had an outage window; Shopify shows a dip, GA4 barely does.
  Finance also notes GA4 "revenue" ran ahead of settled revenue that week.
- **Email looks broken in GA4.** Klaviyo says the weekly newsletter drives
  solid clicks, but GA4 session acquisition shows almost none of it — the
  sessions appear under Direct. Flows (welcome, winback) attribute fine.
- **Canadian revenue looks inflated.** Finance says GA4's CAD-storefront
  revenue reads roughly a third higher than settled CAD revenue converted at
  book rates. US-storefront revenue reconciles fine.
- **Paid search splits oddly.** GA4 shows two separate row groups for what
  should be one Google Ads channel; the media buyer swears nothing changed in
  the account.
- **Add-to-cart reporting went quiet.** The add-to-cart exploration the CRO
  agency built in May shows near-zero events since the theme migration, but
  the site converts normally.
- **Legal flagged us.** Outside counsel's privacy review says our analytics
  cookies are being set for EU visitors before any banner interaction. We told
  them we run Consent Mode; they stand by the finding.
- **Cart recovery reporting is unreadable.** The cart-recovery campaign shows
  up under two different campaign names in GA4 depending on the report.

Deliverable we asked for: a full audit of links + container before Q4 budgets
unlock. Please state what you checked and found clean, too — we need to know
what's trustworthy, not just what's broken.
