# Cedar & Coil: Shopify to Meta Conversion Tracking & CAPI Implementation Guide

**Brand & Product:** Cedar & Coil — Arc Clip Lamp ($68 USD)  
**Deliverable Context:** Technical Implementation Guide for Server-Side & Browser Event Measurement  
**Target Architecture:** Redundant Dual-Layer Setup (Meta Pixel + Conversions API with Exact Deduplication)

---

### 1. Recommended Architecture: Browser Meta Pixel + Conversions API (CAPI)

For Cedar & Coil’s Shopify storefront selling the Arc Clip Lamp, the recommended tracking architecture is a **redundant dual-layer setup**: the client-side Meta Pixel running concurrently with server-side Meta Conversions API (CAPI), synchronized by deterministic event deduplication.

#### Why Both Layers Are Necessary
* **Client-Side Vulnerabilities:** Relying exclusively on browser-side tracking leaves measurement exposed to ad blockers, browser privacy restrictions (such as Safari’s Intelligent Tracking Prevention / ITP capping cookie lifespans), browser crashes upon purchase confirmation, and script-blocking extensions. These factors routinely drop browser hits before they reach Meta.
* **Server-Side Resilience:** CAPI dispatches events directly from a secure server environment (Shopify’s backend or a dedicated intermediate container) to Meta’s Graph API. Because this connection is server-to-server, it is completely immune to client-side ad blockers, browser extension interference, and device network interruptions occurring right after checkout.
* **Why CAPI Alone Is Insufficient:** The browser Pixel remains essential because it natively captures immediate, rich client context: first-party cookies (`_fbp` and `_fbc`), exact client screen properties, and real-time millisecond timestamps. Discarding the Pixel in favor of pure server tracking degrades Event Match Quality (EMQ) and weakens Meta's real-time attribution signals.
* **The Dual-Layer Advantage:** Running both systems in tandem provides maximum data fidelity. When both channels capture an interaction, Meta fuses the client context with the server data, creating a single robust record. If the browser event is blocked or lost, the CAPI event ensures the conversion is still recorded.

---

### 2. Standard Funnel Events & Core Parameters

To enable full-funnel optimization and bidding intelligence for the Arc Clip Lamp, four standard events must be captured across the buyer journey.

#### Standard Funnel Events Matrix

| Event Name | Trigger Location / User Action | Required & Recommended Custom Parameters | Cedar & Coil Context |
| :--- | :--- | :--- | :--- |
| **`ViewContent`** | Arc Clip Lamp product detail page load (`/products/arc-clip-lamp`). | `content_type`: `'product'`<br>`content_ids`: `['shopify_US_arc_clip_lamp_default']`<br>`content_name`: `'Arc Clip Lamp'`<br>`content_category`: `'Lighting'`<br>`value`: `68.00`<br>`currency`: `'USD'` | Captures prospect engagement with the core product page. |
| **`AddToCart`** | User clicks the "Add to Cart" button or drawer checkout trigger. | `content_type`: `'product'`<br>`content_ids`: `['shopify_US_arc_clip_lamp_default']`<br>`content_name`: `'Arc Clip Lamp'`<br>`value`: `68.00` (or `68.00 * quantity`)<br>`currency`: `'USD'` | Signals purchase intent prior to checkout initiation. |
| **`InitiateCheckout`** | User proceeds to the Shopify checkout flow (`/checkout`). | `content_type`: `'product'`<br>`content_ids`: `['shopify_US_arc_clip_lamp_default']`<br>`num_items`: `1` (or total quantity)<br>`value`: `68.00`<br>`currency`: `'USD'` | Measures funnel progression into payment/shipping entry. |
| **`Purchase`** | Customer completes payment; order confirmation page loads or `orders/paid` webhook fires. | `content_type`: `'product'`<br>`content_ids`: `['shopify_US_arc_clip_lamp_default']`<br>`content_name`: `'Arc Clip Lamp'`<br>`num_items`: `1`<br>`value`: `68.00` (order subtotal or total excluding shipping/tax per reporting policy)<br>`currency`: `'USD'`<br>`order_id`: `'1001'` | Primary optimization event for ROAS, CPA, and conversion bidding. |

#### Critical Purchase Parameters Deep Dive
1. **`value` & `currency`:** Must be passed as a valid floating-point number and an ISO 4217 standard currency code (e.g., `value: 68.00`, `currency: 'USD'`). Inconsistent formatting breaks ROAS calculations in Meta Ads Manager.
2. **`content_ids` Alignment:** The ID structure passed in `content_ids` (e.g., the Shopify variant/product ID `shopify_US_{product_id}_{variant_id}` or SKU) **must exactly match** the identifier scheme in Cedar & Coil's Meta Product Catalog. A mismatch prevents Meta from connecting dynamic product ads (DPA) to catalog items.

---

### 3. Exactly How Deduplication Works Between Pixel and CAPI

When both the browser Pixel and server CAPI dispatch data for the same user interaction, Meta must evaluate incoming payloads to count a single conversion while enriching attribution data.

```
       User Action (e.g., Purchase of Arc Clip Lamp: Order #1001)
                                  |
            +---------------------+---------------------+
            |                                           |
      [Browser Pixel]                             [Server CAPI]
            |                                           |
    event_name: 'Purchase'                      event_name: 'Purchase'
    event_id:   'CC-1001'                       event_id:   'CC-1001'
            |                                           |
            +----------------->   <---------------------+
                                  |
                        [Meta Processing Engine]
                                  |
                    Match: event_name + event_id
                    (Within 48-Hour Matching Window)
                                  |
                   Single Deduplicated Conversion
                 (Merged signals maximize match quality)
```

#### Deduplication Keys
Deduplication requires two identical payload keys across both client and server dispatches:
1. **`event_name`**: Must match identically and case-sensitively (e.g., `Purchase` in the browser, `Purchase` on the server).
2. **`event_id`**: A unique, deterministic identifier assigned at the time of the event and passed identically in both `fbq('track', 'Purchase', {...}, {eventID: 'XYZ'})` and CAPI's `data[].event_id: 'XYZ'`.

#### Generating Deterministic Identifiers
* **For `Purchase`:** The canonical deduplication key is the Shopify Order ID or Order Confirmation Number (e.g., `shopify_order_1001` or `CC-1001`). Because this order ID exists in both the Liquid checkout/thank-you context and backend order webhooks, it guarantees a 1:1 deterministic match.
* **For Up-Funnel Events (`ViewContent`, `AddToCart`, `InitiateCheckout`):** Generate a unique UUID or a deterministic session-based hash (e.g., `fbp_timestamp_eventname`). This token must be stored in browser `sessionStorage` or state so both the client script and the server relay dispatch the identical string.

#### Processing Window and Data Fusion
* **48-Hour Deduplication Window:** Meta evaluates incoming events over a rolling 48-hour window. If an event is received via the browser first, Meta logs it and waits; when the corresponding CAPI event arrives with the identical `(event_name, event_id)` combination, Meta merges them.
* **Signal Merging:** The resulting deduplicated conversion retains the client-side browser fingerprints and timestamps alongside the server-side verified customer match parameters (hashed email, phone, billing address), maximizing match quality without inflating conversion counts.

---

### 4. Customer Information Preparation (Normalization & Hashing)

Meta relies on customer information parameters (`user_data`) to map events back to specific Meta user accounts. All personally identifiable information (PII) must be normalized and hashed prior to CAPI transmission.

#### Normalization and Hashing Standards

| Parameter | CAPI Key | Normalization Standard | Hashing Algorithm | Raw Example | Processed Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Email** | `em` | Trim whitespace; convert all characters to lowercase. | SHA-256 (hex) | `" Customer@CedarCoil.com "` | `cbcacbe91844c2b30bfb0cdd11449d42d70deed2cbeeca742cab43e3f6f41b1b` |
| **Phone** | `ph` | Strip non-numeric characters (spaces, dashes, parentheses); include country code; drop leading zeros. | SHA-256 (hex) | `"+1 (619) 555-0142"` | `a03cd95bbc0a29bc3ec884e286a84a6f78ccfe88d3bfbec9fae2efbf392bf51f` |
| **First Name**| `fn` | Trim whitespace; lowercase; remove punctuation. | SHA-256 (hex) | `" Jane "` | `81f8f6dde88365f3928796ec7aa53f72820b06db8664f5fe76a7eb13e24546a2` |
| **Last Name** | `ln` | Trim whitespace; lowercase; remove punctuation. | SHA-256 (hex) | `"Doe"` | `799ef92a11af918e3fb741df42934f3b568ed2d93ac1df74f1b8d41a27932a6f` |
| **City** | `ct` | Trim whitespace; lowercase; remove spaces and special characters. | SHA-256 (hex) | `"San Diego"` | `4fb5ca3b980f7bc3ec7a71345c4e025aa55c604e8faca407614ca648e8a35331` |
| **State** | `st` | Two-letter state/province abbreviation; lowercase. | SHA-256 (hex) | `"CA"` | `6959097001d10501ac7d54c0bdb8db61420f658f2922cc26e46d536119a31126` |
| **Postal Code**| `zp` | Lowercase; remove spaces/dashes; standard format (e.g., first 5 digits in US). | SHA-256 (hex) | `"92101-1234"` | `0c63ebeb401cc071ed9d6c0bddff77ecc458a92cbf5b9994fe9d729b97ff1e3e` |
| **Country** | `country`| Two-letter ISO 3166-1 alpha-2 code; lowercase. | SHA-256 (hex) | `"US"` | `79adb2a2fce5c6ba215fe5f27f532d4e7edbac4b6a5e09e1ef3a08084a904621` |

#### Unhashed Contextual & Browser Parameters
Do **not** SHA-256 hash these parameters:
* **`client_ip_address` (`ip`)**: Raw IPv4 or IPv6 address extracted from request headers (e.g., `X-Forwarded-For`).
* **`client_user_agent` (`user_agent`)**: Raw browser `User-Agent` string.
* **`fbp` (Browser Cookie)**: First-party `_fbp` cookie created by the Meta Pixel in the visitor’s browser (e.g., `fb.1.1727050000.1234567890`).
* **`fbc` (Click Identifier)**: First-party `_fbc` cookie containing the Meta Click ID (`fbclid`) from an ad visit (e.g., `fb.1.1727050000.IwAR0_AbCdEfGhIjKlMnOpQrStUvWxYz`).

Passing unhashed `_fbp` and `_fbc` values significantly boosts match rates even when personal identifiers like email or phone are absent in upper-funnel events.

---

### 5. Concrete Shopify Setup Path & Implementation

#### Comparison: Native Meta Sales Channel App vs. Custom CAPI Implementation

| Evaluation Dimension | Option A: Native Meta Sales Channel App (Shopify) | Option B: Custom Implementation (Server GTM / Custom Cloud Worker) |
| :--- | :--- | :--- |
| **Architecture** | Turnkey managed integration built jointly by Shopify and Meta. | Custom backend service (AWS Lambda, Cloudflare Worker, or sGTM) receiving Shopify webhooks. |
| **Setup & Engineering Effort** | **Minimal (15–30 minutes):** Installed via Shopify App Store; authenticated via Meta OAuth. | **High (20–40+ engineering hours):** Requires custom cloud hosting, API token rotation, schema maintenance, and monitoring. |
| **Data Sharing Configuration** | Built-in toggle set to **"Maximum"** (enables Pixel + server CAPI automatically). | Custom scripts deployed across Shopify Customer Events (Web Pixels API) and backend webhook listeners. |
| **Deduplication Handling** | **Automated:** Shopify internally syncs `event_id` between client scripts and backend server dispatches. | **Manual:** Developers must architect, store, and pair `event_id` tokens across client and server environments. |
| **Ongoing Maintenance** | Zero infrastructure overhead; automatic updates for Meta Graph API version migrations. | Ongoing maintenance burden; requires uptime monitoring, log rotation, rate limit handling, and API deprecation updates. |

#### Concrete Recommendation for Cedar & Coil
**Deploy Option A: Native Meta Sales Channel App.**  
For a lean direct-to-consumer store launching a single product ($68 Arc Clip Lamp), the native Meta Sales Channel app set to **"Maximum" data sharing** is the optimal path. It provides native out-of-the-box CAPI synchronization, automated deduplication, and zero server infrastructure maintenance, fully respecting Shopify's modern checkout sandbox (Web Pixels API) without requiring custom code maintenance.

#### Technical Code Sketch: CAPI Server-Side Purchase Payload
If Cedar & Coil requires a custom server-side relay (e.g., via a cloud worker listening to the Shopify `orders/paid` webhook), the following payload demonstrates the exact Graph API call structure.

**Request Endpoint:**  
`POST https://graph.facebook.com/v19.0/{PIXEL_OR_DATASET_ID}/events?access_token={META_CAPI_SYSTEM_USER_TOKEN}`

**JSON Payload (`Purchase` Event):**
```json
{
  "data": [
    {
      "event_name": "Purchase",
      "event_time": 1727053200,
      "event_id": "shopify_order_1001",
      "event_source_url": "https://cedarandcoil.com/checkouts/c/1a2b3c4d/thank_you",
      "action_source": "website",
      "user_data": {
        "em": [
          "cbcacbe91844c2b30bfb0cdd11449d42d70deed2cbeeca742cab43e3f6f41b1b"
        ],
        "ph": [
          "a03cd95bbc0a29bc3ec884e286a84a6f78ccfe88d3bfbec9fae2efbf392bf51f"
        ],
        "fn": [
          "81f8f6dde88365f3928796ec7aa53f72820b06db8664f5fe76a7eb13e24546a2"
        ],
        "ln": [
          "799ef92a11af918e3fb741df42934f3b568ed2d93ac1df74f1b8d41a27932a6f"
        ],
        "ct": [
          "4fb5ca3b980f7bc3ec7a71345c4e025aa55c604e8faca407614ca648e8a35331"
        ],
        "st": [
          "6959097001d10501ac7d54c0bdb8db61420f658f2922cc26e46d536119a31126"
        ],
        "zp": [
          "0c63ebeb401cc071ed9d6c0bddff77ecc458a92cbf5b9994fe9d729b97ff1e3e"
        ],
        "country": [
          "79adb2a2fce5c6ba215fe5f27f532d4e7edbac4b6a5e09e1ef3a08084a904621"
        ],
        "client_ip_address": "198.51.100.42",
        "client_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "fbp": "fb.1.1727050000.1234567890",
        "fbc": "fb.1.1727050000.IwAR0_AbCdEfGhIjKlMnOpQrStUvWxYz"
      },
      "custom_data": {
        "currency": "USD",
        "value": 68.00,
        "content_type": "product",
        "content_ids": [
          "shopify_US_arc_clip_lamp_default"
        ],
        "content_name": "Arc Clip Lamp",
        "num_items": 1,
        "order_id": "1001"
      }
    }
  ],
  "test_event_code": "TEST12345"
}
```

---

### 6. End-to-End Validation Protocol (Before Scaling Spend)

Before scaling ad budgets on the Arc Clip Lamp, execute this step-by-step verification protocol to confirm both layers are healthy and deduplicating accurately.

#### Step 1: Real-Time Diagnostic via Meta Test Events
1. In Meta Events Manager, go to **Data Sources** → Select the Cedar & Coil Pixel/Dataset → Click the **Test Events** tab.
2. If testing via the browser with the native Shopify app, enter the store URL (`https://cedarandcoil.com`) to open a live test session. If testing custom CAPI calls, append the `"test_event_code": "TEST12345"` parameter to your server requests.
3. Complete the entire checkout journey on the storefront:
   - Load the Arc Clip Lamp page (`ViewContent`).
   - Add the lamp to cart (`AddToCart`).
   - Click checkout (`InitiateCheckout`).
   - Complete an order using Shopify’s Bogus Gateway or a test payment (`Purchase`).
4. **Validation Checklist in Test Events Feed:**
   - [ ] Verify that each event displays two entries: one labeled **Browser** and one labeled **Server**.
   - [ ] Confirm that both entries share the exact same **Event ID**.
   - [ ] Confirm that the status column updates to **"Deduplicated"**, confirming Meta successfully merged the two events without double-counting.

#### Step 2: Browser Verification with Meta Pixel Helper
1. Open Google Chrome with the **Meta Pixel Helper** extension installed.
2. Walk through the storefront and inspect the extension popup on each page.
3. Confirm that:
   - Standard event names appear with green checkmarks.
   - Core parameters (`content_ids`, `value: 68.00`, `currency: 'USD'`) are present and uncorrupted.
   - No red error flags (such as missing currencies or duplicate unkeyed pixel triggers) are reported.

#### Step 3: Event Match Quality (EMQ) Audit
1. Allow test transactions and organic traffic to populate Events Manager over a 24–48 hour window.
2. In the **Overview** tab of Events Manager, check the **Event Match Quality** score for `Purchase` (scored from 1.0 to 10.0).
3. **Target Standard:** For a direct-to-consumer store with full checkout data, aim for **Good (6.0+) or Great (8.0+)**.
4. If the score is below acceptable thresholds:
   - Ensure all available customer fields (`em`, `ph`, `fn`, `ln`, `ct`, `st`, `zp`, `country`) are properly captured and normalized.
   - Verify that client-side `_fbp` and `_fbc` parameters are properly extracted and forwarded in server-side payloads.

---

### 7. Consent, Privacy & Regulatory Compliance

A robust tracking architecture must strictly adhere to regional privacy legislation (e.g., GDPR, ePrivacy Directive, and US state privacy regulations such as CCPA/CPRA).

1. **Consent Gate Prior to Event Dispatch:**
   * Under GDPR and ePrivacy rules, neither the browser Pixel nor the server-side CAPI event stream may fire for visitors in covered jurisdictions until explicit, affirmative opt-in consent has been granted for marketing cookies and tracking.
   * Integrating with Shopify's native Customer Privacy API or a recognized Consent Management Platform (CMP) ensures that:
     * When marketing consent is **declined**, both client-side pixel scripts and server-side CAPI relays are suppressed.
     * Server-side tracking does not bypass consent mandates: transmitting personal data (including hashed emails, IP addresses, or phone numbers) over CAPI without user consent represents a regulatory violation.
2. **Meta Limited Data Use (LDU) for California (CPRA/CCPA):**
   * For visitors identified in California, enable Meta’s Limited Data Use mode.
   * Under LDU, Meta acts as a data processor/service provider, restricting the use of event data for cross-context behavioral advertising.
   * In CAPI payloads, LDU mode is enforced by passing explicit data processing parameters:
     ```json
     "data_processing_options": ["LDU"],
     "data_processing_options_country": 1,
     "data_processing_options_state": 1000
     ```
     *(Setting `country: 0` and `state: 0` directs Meta to geolocate the user's IP to determine applicability automatically).*
3. **Storefront Privacy Policy Disclosure:**
   * The Cedar & Coil privacy policy must clearly state that customer data, browsing patterns, and order details are shared with third-party advertising partners (Meta Platforms, Inc.) for conversion measurement and targeted advertising.
   * Provide a straightforward, accessible mechanism for visitors to opt out of data sharing or submit California consumer privacy requests.

---
*The implementation guide has also been preserved in the project workspace at:*  
`drafts/guide.md`