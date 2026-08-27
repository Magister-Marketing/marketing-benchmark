# GTM container `GTM-K4WPD2` — current configuration summary

Exported from the container as of 2026-08-20. One web container serves both
`www.loamandledger.com` and `ca.loamandledger.com`.

## Tags

**1. GA4 Configuration — `G-8B21XQ4`**
- Trigger: Initialization — All Pages
- Fields: `send_page_view: true`
- Notes: none

**2. GA4 Event — `purchase` (confirmation page)**
- Trigger: Page View where Page Path matches RegEx `^/order-confirmation`
- Parameters: `value: {{DLV - order_total}}`, `currency: "USD"`,
  `items: {{DLV - items}}`
- Notes: order_total is net of tax/shipping per finance's request

**3. GA4 Event — `purchase` (checkout button)**
- Trigger: Click — All Elements, matching CSS selector `#place-order-btn`
- Parameters: `value: {{DLV - order_total}}`, `currency: "USD"`
- Notes: added 2026-06 "as a backup while debugging Safari losses" — still live

**4. GA4 Event — `Add to Cart`**
- Trigger: Custom Event `add_to_cart_clicked` (from the theme)
- Parameters: `items: {{DLV - items}}`, `value: {{DLV - line_value}}`
- Notes: renamed from `add_to_cart` during the theme migration "for readability"

**5. GA4 Event — `begin_checkout`**
- Trigger: Page View where Page Path equals `/checkout`
- Parameters: `value: {{DLV - cart_total}}`, `currency: {{DLV - currency}}`, `items: {{DLV - items}}`
- Notes: none

**6. Meta Pixel — base + purchase**
- Base code: All Pages. Purchase event: same RegEx trigger as tag 2.
- Purchase parameters: `value: {{DLV - order_total}}`, `currency: "USD"`

## Consent initialization (Consent Mode v2)

Set via a consent-initialization tag, before all others:

| Region | analytics_storage | ad_storage |
|---|---|---|
| Default (everywhere) | `granted` | `granted` |
| EEA + UK | `granted` | `denied` |

The cookie banner (Cookiebot) updates both to `granted` on accept.

## Site structure notes (from the web team)

- Order confirmation renders at `/order-confirmation` once payment settles.
- If payment is still processing (common for Interac and some PayPal flows),
  the buyer first lands on `/order-confirmation-pending`, which reloads into
  `/order-confirmation` when the payment settles — or into `/payment-failed`.
- The `ca.` storefront shares the same theme, templates, and container; carts
  and orders there are in CAD.
