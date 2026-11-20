# Wrenlow Tea Club: lifecycle email policy

Wrenlow Tea Club posts a tin of loose-leaf tea to its members each month. This is the
standard for its lifecycle email programme. Apply it to `customers.csv` as
written: do not improve on it, and do not skip a customer.

**Today is 2026-10-01.** "Days before today" counts calendar days back from
today: 2026-09-30 is 1 day before today, and today itself is 0.

## The export

One row per customer. `consent`, `unsubscribed`, `hard_bounced` and `complained`
are `y` or `n`. `consent_date` is blank where there is no consent, and
`last_order_date` where there are no orders. `lifetime_value` is in whole
dollars. `plan` is `M` (monthly), `Q` (quarterly), `G` (a gift plan someone else pays for). `timezone` is where the customer reads email.

## 1. Suppression

A suppressed customer receives nothing and belongs to no segment. Check these
reasons in this order. The first that applies is the customer's reason, and
they are listed with that one only.

1. `complaint`: `complained` is `y`.
2. `unsubscribed`: `unsubscribed` is `y`.
3. `hard_bounce`: `hard_bounced` is `y`.
4. `no_consent`: `consent` is `n`.
5. `stale_consent`: `country` is DE, FR or NL, and `consent_date` is more than
   730 days before today. Exactly 730 days is still good. Consent never goes
   stale in any other country.
6. `dormant_signup`: `orders` is 0 and `signup_date` is more than 365 days
   before today. Exactly 365 days does not count.

## 2. Segments

Every customer who is not suppressed is in one segment: the first in this
order whose test they meet.

1. `new`: `signup_date` is 30 days before today or fewer. Exactly 30 days is new.
2. `prospect`: `orders` is 0.
3. `lapsed`: `last_order_date` is more than 180 days before today. Exactly 180
   days is not lapsed.
4. `vip`: `orders` is 8 or more and `lifetime_value` is 600 or more. Both are needed.
5. `at_risk`: `last_order_date` is more than 90 days before today. Exactly 90
   days is not at risk.
6. `active`: everyone else.

The order decides. A customer with VIP numbers whose last order was 200 days
before today is `lapsed`.

## 3. Holdout

Some customers are held out, so the programme can be measured against them.
In `lapsed`, `at_risk` and `prospect`, a customer is in the holdout when
the number in their id is divisible by 7 (`C105` is 105, which is). Nobody in
`new`, `vip` or `active` is held out, and a suppressed customer is never in the
holdout. A held-out customer keeps their segment and receives no email.

## 4. Flows

Each segment has one flow. A customer enters it on day 0.

| segment | emails | first email | last email | offer |
|---|---|---|---|---|
| `new` | 5 | day 0 | day 21 | none |
| `prospect` | 4 | day 1 | day 14 | `FIRST10` on the last email |
| `lapsed` | 5 | day 0 | day 30 | `BACK15` on the last email |
| `vip` | 3 | day 0 | day 10 | none |
| `at_risk` | 4 | day 0 | day 12 | none |
| `active` | 3 | day 3 | day 17 | none |

- Steps are numbered from 1, in the order they are sent.
- You choose the days of the emails between the first and the last: whole
  days, with at least 4 days between one email and the next. Day 0 then day 4
  is allowed; day 0 then day 3 is not.
- Only the `prospect` and `lapsed` flows carry an offer. Its code goes on the last email
  of that flow and on no other email.
- Cap: a customer on a gift plan (`G`) receives steps 1 and 2 of their flow and
  no later step. Everyone else receives every step.

The programme's first full run is every email it sends when each customer who
is neither suppressed nor held out receives every step they are due.

## 5. Send times

Each step is released once, to everyone at the same moment:

| segment | released at (UTC) |
|---|---|
| `new` | 14:30 |
| `prospect` | 16:00 |
| `lapsed` | 18:30 |
| `vip` | 12:00 |
| `at_risk` | 17:00 |
| `active` | 13:30 |

A step that carries an offer code is released at 20:00 UTC instead of its
segment's time.

A customer receives it at that moment by their own clock. Use these fixed
offsets from UTC, with no daylight saving:

| timezone | PT | MT | CT | ET | GMT | CET | IST | AEST |
|---|---|---|---|---|---|---|---|---|
| offset | -8:00 | -7:00 | -6:00 | -5:00 | 0:00 | +1:00 | +5:30 | +10:00 |

Quiet hours are 21:00 to 07:59 by the customer's clock, both ends included. An
email that would arrive in quiet hours is held and arrives at 08:00 instead;
08:00 itself is not quiet. Holding an email does not change its day in the flow.

The schedule has one row for each segment, step and timezone in which at
least one customer receives that step, and no other rows. A local time is
written as HH:MM on the 24-hour clock.

## 6. Copy

Each email has a subject and a preheader. A term below is found as whole
words, in any case: `free` is in "caffeine-free" (a hyphen separates words)
and is not in "freedom".

- A subject is at most 50 characters and a preheader at most 90, spaces and
  punctuation included. Neither is empty.
- Every email has its segment's phrase in its subject or in its preheader:
  - `new`: `welcome`
  - `prospect`: `first tin`
  - `lapsed`: `come back`
  - `vip`: `Reserve List`
  - `at_risk`: `next tin`
  - `active`: `this month`
- The offer email of a flow has its offer, in these exact words, in its
  subject or in its preheader. It states no other percentage and names no
  other code.
  - `FIRST10`: `10% off your first order`
  - `BACK15`: `15% off your next order`
- An email without an offer has no `%` sign and names no offer code.
- Never: `free`, `guarantee`, `guaranteed`, `urgent`, `last chance`, `act now`, `cheap`.
- No exclamation marks.
- No two emails in the programme have the same subject, whatever the case.
