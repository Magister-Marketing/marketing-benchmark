# Ostrel Botanicals: email sending policy

Before we move to the new email platform, every live email is checked
against this policy. An email that breaks a rule gets that rule's code; an
email can get several codes. The codes are `DOMAIN`, `ADDRESS`, `UNSUBSCRIBE`, `SUBJECT`, `TRANSACTIONAL_PROMO`, `CONSENT`.

Each email's stream is `marketing` or `transactional`, as set in the email
platform. Each rule below says which stream it applies to; a rule that names
no stream applies to both.

## 1. Sending domain (`DOMAIN`)

An email is sent from the domain of its From address. That domain must be
one of our sending domains, `mail.ostrel.example`, `orders.ostrel.example`, `uk.ostrel.example`, `ca.ostrel.example`, `eu.ostrel.example`, `news.ostrel.example`, `promo.ostrel.example`, and it must meet all three of these in
its published DNS records:

1. **SPF**: the domain has exactly one TXT record that starts with `v=spf1`.
   That record contains `include:spf.sendloop.example` and ends with `-all` or `~all`.
2. **DKIM**: there is a TXT record at `sl1._domainkey.<domain>` that contains
   `v=DKIM1` and a `p=` value that is not empty.
3. **DMARC**: there is one TXT record at `_dmarc.<domain>`, and its `p=` tag is
   `quarantine` or `reject`.

An email from any other domain, or from a domain that does not meet all
three, gets `DOMAIN`.

## 2. Postal address (`ADDRESS`)

The footer of every marketing email contains one of our two registered postal
addresses, exactly as written here; only line breaks, commas and the `·`
separator may differ:

- Ostrel Botanicals Inc., 418 Larch Street, Suite 200, Portland, OR 97209, USA
- Ostrel Botanicals Inc., PO Box 7721, Portland, OR 97207, USA

A marketing email without one gets `ADDRESS`. Transactional emails need no
address.

## 3. Unsubscribe (`UNSUBSCRIBE`)

The footer of every marketing email contains a working unsubscribe link: the
merge tag `{{ unsubscribe_link }}` or `{{ preferences_link }}` (the preferences page has a one-click
unsubscribe). The email platform ignores spaces inside the braces. Any other
difference, capital letters included, is a tag that does not render and is
not a working link. A marketing email without a working link gets
`UNSUBSCRIBE`. Transactional emails need no link.

## 4. Subject line and preheader (`SUBJECT`)

The subject line and the preheader state the body's offer as the body
states it. An email gets `SUBJECT` when its subject or its preheader:

1. states a percentage off that is not the body's percentage; after "up to",
   the percentage must be the highest one the body offers;
2. says "sitewide", "everything" or "all products" while the body limits the offer to some
   products or excludes any;
3. names a day or date the offer ends that is not the day the body's offer
   ends;
4. promises free shipping without a minimum order when the body sets one.

A subject or preheader may leave out any part of the offer.

## 5. Promotion in transactional emails (`TRANSACTIONAL_PROMO`)

Body blocks of type `promo` and `recommendations` are promotional; no other
block type is.

- A transactional email whose purpose is `password reset` or `account security` has
  no promotional block.
- Any other transactional email has at most one promotional block. It comes
  after every `order`, `shipping` and `account` block, and it contains no discount code.

A transactional email that breaks either rule gets `TRANSACTIONAL_PROMO`.

## 6. Consent (`CONSENT`)

A marketing email goes only to audiences whose consent allows marketing in
their region (`audiences.csv`):

| consent | US | UK | EU | CA |
|---|---|---|---|---|
| `express` | yes | yes | only if `double_opt_in` is `yes` | yes |
| `customer` | yes | yes | no | only if `max_months_since_purchase` is 24 or less |
| `event` | no | no | no | no |
| `imported` | no | no | no | no |

A marketing email with any audience the table does not allow gets `CONSENT`.
Transactional emails go only to the person whose own action triggered them
and need no marketing consent.
