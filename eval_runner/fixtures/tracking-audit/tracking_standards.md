# Loam & Ledger — Measurement Standards (v3, agreed 2026-01)

These conventions are the contract between marketing, the web team, and
finance. Every live link and every tag change is supposed to conform.

## UTM conventions

- All UTM parameter values are **lowercase**, always.
- `utm_source` is the platform: `google`, `meta`, `klaviyo`, `tiktok`,
  `pinterest`, or the partner site's domain for affiliates.
  (Historical note: we standardized on `meta` — not `facebook` — in v2.)
- `utm_medium` is one of exactly: `cpc`, `paidsocial`, `email`, `affiliate`,
  `organicsocial`.
- `utm_campaign` format: `<year>q<quarter>-<line>-<goal>`, hyphen-separated,
  no spaces, e.g. `2026q3-linen-prospecting`.
- Every parameter appears at most once per URL.
- All destination URLs are `https://` on `www.loamandledger.com` (or the
  `ca.` storefront).

## GA4 / GTM conventions

- GA4 event names are `snake_case` (`begin_checkout`, `add_to_cart`).
- Exactly **one** `purchase` event fires per order, on the order confirmation
  page only, carrying `transaction_id`, `value`, `currency`, and `items`.
- `currency` reflects the order's actual currency. The `ca.` storefront
  transacts in CAD.
- Ecommerce values are order totals net of tax and shipping.

## Consent (Consent Mode v2)

- Defaults for visitors in the EEA/UK: `analytics_storage: denied` and
  `ad_storage: denied` until the banner grants them.
- Defaults elsewhere: both granted.
- Tags must respect consent state; no consent-exempt duplicates.
