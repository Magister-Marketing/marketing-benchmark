# Larkfield Goods: email sending policy

Larkfield Goods sends email for two brands, Ostrel and Tamsin, in four regions
(US, UK, EU, CA). Before the move to the new email platform, every scheduled
email in `emails.csv` is checked against this policy, using the other files
exported with it.

## Verdicts

An email that breaks no rule passes. An email that breaks a rule gets that
rule's code together with the id of the row that proves it, written
`CODE:ROW_ID` (for example `PRICE:R99`). An email can break several rules;
it gets each code once. The codes, and the file whose row each one names:

| code | rule | the row it names |
|---|---|---|
| `DOMAIN` | 1 | the failing record in `dns_records.csv` |
| `SENDER` | 2 | the row of `senders.csv` for the email's brand, region and stream |
| `ADDRESS` | 3 | the row of `addresses.csv` for the email's brand and region |
| `CONSENT` | 4 | the email's audience in `audiences.csv` |
| `PROMO` | 5 | the row of `promotions.csv` for the email's code, brand and region |
| `PRICE` | 6 | the row of `prices.csv` in effect for the email's product and region on its send date |
| `FREQUENCY` | 7 | an earlier email in `emails.csv`, as rule 7 says |

Dates are calendar days. "Between" two dates includes both. Every rule is
applied to each email on its own `send_date`.

## 1. Sending domain (`DOMAIN`)

The domain of the email's `from_address` must meet all three of these in
`dns_records.csv`:

1. **SPF**: the domain has exactly one TXT record named after the domain that
   starts with `v=spf1`. That record contains `include:spf.sendloop.example` and ends with
   `-all` or `~all`.
2. **DKIM**: the record named `sl1._domainkey.<domain>` contains `v=DKIM1` and a
   `p=` value that is not empty.
3. **DMARC**: the record named `_dmarc.<domain>` has a `p=` tag of
   `quarantine` or `reject`.

An email from a domain that fails gets `DOMAIN` with the id of the record
that fails: the SPF record, the `sl1._domainkey` record, or the DMARC record. No
domain in this export fails more than one of the three.

## 2. Sender (`SENDER`)

`senders.csv` has one row for each brand, region and stream. An email's
`from_address` must be one of the addresses in the row for its own brand,
region and stream. Otherwise it gets `SENDER` with that row's id.

## 3. Postal address (`ADDRESS`)

A marketing email's `footer_address` is the registered address in
`addresses.csv` for its brand and region, as written there (only commas,
spaces and capital letters may differ). Otherwise it gets `ADDRESS` with
that row's id. Transactional emails are not checked under this rule.

## 4. Consent (`CONSENT`)

A marketing email may go to its audience only when, on its send date, both
hold:

- the audience's `consent_date` is the send date or earlier;
- the send date is no more than the window below after the audience's
  `last_activity_date`: a window of 365 days allows a send 365 days after it
  and not 366.

The window depends on the audience's region and consent type and on the
email's message type. Purposes `promotion`, `launch`, `win-back`, `welcome offer` are
`promotional`; purposes `newsletter`, `survey`, `event invitation` are `newsletter`.

| region | consent | promotional (days) | newsletter (days) |
|---|---|---|---|
| US | `express` | 730 | 1095 |
| US | `customer` | 365 | 730 |
| UK | `express` | 540 | 730 |
| UK | `customer` | 180 | 365 |
| EU | `express` | 365 | 540 |
| EU | `customer` | never | never |
| CA | `express` | 730 | 730 |
| CA | `customer` | 730 | 730 |

`never` means no marketing email may go to such an audience. An email that
may not go gets `CONSENT` with its audience's id. Transactional emails need
no consent.

## 5. Promotions (`PROMO`)

A marketing email with a `promo_code` is checked against the row of
`promotions.csv` for that code, its brand and its region. The email must be
sent between the row's `start_date` and `end_date`, its `discount_shown`
must be the row's `discount`, and its `offer_ends_shown` must be the row's
`end_date`. Otherwise it gets `PROMO` with that row's id. A code runs on
different dates and discounts in different regions.

## 6. Prices (`PRICE`)

A marketing email that shows a product (`sku`) shows, as `price_shown`, the
price of that product for its region in effect on its send date: the row of
`prices.csv` for that sku and region whose dates, `effective_from` to
`effective_to`, include the send date. Otherwise it gets `PRICE` with the
id of that row.

## 7. Frequency within a series (`FREQUENCY`)

Emails with the same `series` and `audience_id` are one series to one
audience; no two of them share a send date. An email gets `FREQUENCY` when
2 or more emails of its series to its audience were sent in the 6 days before
its send date, and it names the earliest of those emails. An email sent 7
days after another is outside them. Every email in `emails.csv` counts,
whatever its own verdict. Transactional emails have no series.
