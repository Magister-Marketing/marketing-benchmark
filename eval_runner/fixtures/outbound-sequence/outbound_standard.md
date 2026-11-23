# Brackenfold outbound standard

Apply this to leads.csv as written: do not improve on it, and do not skip a
lead. Today is 2026-03-16. In leads.csv an empty `opted_out` or
`existing_customer` means no, and an empty `last_contacted` means never.

## How a term matches a title

Split the title into words at every character that is not a letter or a
digit, in lower case. A term matches when all its words appear in the title
as whole words, next to each other and in order. `head` matches "Head of
Logistics", not "Headcount Planner"; `coo` matches "COO", not "Coordinator".

## Step 1. Exclusions

Check every lead against these, in this order. The first that applies is the
lead's reason. An excluded lead gets no segment and no email.

1. `opted_out`: `opted_out` is `yes`.
2. `bounced`: `email_status` is `bounced` (`unknown` is not a reason).
3. `existing_customer`: `existing_customer` is `yes`.
4. `competitor`: `domain` is one of `dockhallow.example`, `slotrook.example`, `bayquell.example`, or ends
   with a dot followed by one of them (a subdomain: `eu.dockhallow.example`).
   Ending with the name alone is not enough: `mydockhallow.example` is not one.
5. `recently_contacted`: `last_contacted` is 60 calendar days or fewer before today.
   60 days before is excluded; 61 is not.
6. `not_buying_role`: the title is not a buying role. A buying role
   contains no junior term, and either contains a standalone role or
   contains both a department term and a level term.
   - Standalone roles: `coo`, `chief operating officer`
   - Department terms: `operations`, `logistics`, `warehouse`, `distribution`, `supply chain`, `fulfilment`, `fulfillment`, `site`
   - Level terms: `director`, `head`, `manager`, `vp`, `vice president`, `chief`
   - Junior terms: `assistant`, `deputy`, `intern`, `trainee`
7. `company_size`: `employees` is under 50 or over 5,000
   (50 and 5,000 are inside).

## Step 2. Segments

Every lead left belongs to the first segment whose rule it meets.

1. `executive`: the title contains any of `coo`, `chief`, `vp`, `vice president`.
2. `cold_chain`: `industry` is `food` or `pharma`.
3. `enterprise`: `employees` is 1,000 or more.
4. `site_ops`: every other lead.

## Step 3. Country groups

- `restricted`: `country` is one of `BE`, `DE`, `ES`, `FR`, `IE`, `IT`, `NL`, `SE`.
- `canada`: `country` is `CA`.
- `standard`: every other country.

## Step 4. Sequences

One sequence for each segment and country group with at least one assigned
lead, and none for any other. Each lead receives every step of its sequence.

| Segment | Steps | Send day of each step |
|---|---|---|
| `executive` | 3 | 1, 4, 10 |
| `cold_chain` | 4 | 1, 5, 9, 16 |
| `enterprise` | 4 | 1, 6, 13, 22 |
| `site_ops` | 3 | 1, 3, 8 |

`standard` and `canada` get every step on these days. `restricted` gets steps
1 and 2 only, and step 2 at least 4 days after step 1: if
the segment's step 2 day is less than 4 days after its step
1 day, step 2 moves to step 1's day plus 4.

## Step 5. Copy

- A subject is at most 45 characters as written, spaces included, a
  merge field counted as written (`{{company}}` is 11). It does not start
  with `Re:` or `Fwd:` or `Fw:`.
- No two emails of the programme share a subject. Subjects that differ only
  in case, spaces, punctuation or merge fields count as the same.
- A body is one line: a space, a slash and a space (` / `) between
  paragraphs, never a line break. At most 110 words: a word is anything
  between spaces holding a letter or a digit, so the slash is not one and a
  merge field is one. The greeting, the country sentence, the unsubscribe
  sentence and the address all count.
- A body opens with its greeting (Step 6). Its last words are the
  unsubscribe sentence followed by the postal address in product_facts.md.
  Unsubscribe sentence: `Not for you? Reply STOP and we will not email you again.`
- Every `restricted` email, and no other, contains:
  `We write under legitimate interest, as your role covers inbound dock operations.`
- Every `canada` email, and no other, contains:
  `Sent to your business address under Canadian anti-spam law.`
- Never, in any case, as whole words (a hyphen counts as a space):
  `guarantee`, `guaranteed`, `just checking in`, `quick question`, `circling back`, `touch base`, `touching base`, `following up`, `free trial`, `act now`.
- Each email cites exactly one of the three proof points: it cites one when
  its subject or body states one of that proof point's figures.
- Every figure in digits in a subject or body is a figure of a proof point or
  of the offer, as written there; work out no new figure (a difference, a
  total). The only other digits allowed are in the postal address.

## Step 6. Merge fields

A merge field is written `{{name}}` and filled from the lead's own row,
from the column of the same name. Only these exist:
`{{first_name}}`, `{{company}}`, `{{industry}}`.

A merge field may be used in a sequence's emails only if every lead assigned
to that sequence (segment and country group) has a value in its column.
Excluded leads do not count. Where one may not be used, write its fallback:
`{{company}}` -> `your team`, `{{industry}}` -> `your sector`.

Every body opens with `Hi {{first_name}},` where `{{first_name}}` may be used,
and with `Hi there,` where it may not.
