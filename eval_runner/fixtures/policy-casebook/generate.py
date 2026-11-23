#!/usr/bin/env python3
"""Write, or check, the sources of the policy-casebook task.

Deterministic: the policy is written out below, with every number rendered
from `POLICY` in `eval_runner/task_facts_experiments.py`, and the forty cases
are rendered from `CASEBOOK_CASES` there, beside the attributes the oracle
reads. `build()` refuses a casebook in which a case is not decided as
designed (`EXPECTED` below), or is decided by more than one clause at the
last step of the policy's procedure (see `_check`).

    python3 eval_runner/fixtures/policy-casebook/generate.py --write
    python3 eval_runner/fixtures/policy-casebook/generate.py --check

All brands, people and figures here are invented. The policy is a company's
own rulebook: none of it states what any law requires.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eval_runner import task_facts_experiments as facts  # noqa: E402

P = facts.POLICY
A, C, N = facts.ALLOWED, facts.CONDITIONAL, facts.NOT_ALLOWED

# What each case was written to test: its ruling, condition and deciding clause.
EXPECTED = {
    "C01": (C, "study-on-file", "CL-3"), "C02": (C, "price-record", "3.7"), "C03": (C, "legal-signoff", "4.1"),
    "C04": (A, None, "3.2"), "C05": (N, None, "2.6"), "C06": (C, "ad-label", "2.5"), "C07": (N, None, "7.5"),
    "C08": (N, None, "CL-4"), "C09": (N, None, "3.1"), "C10": (C, "ad-label", "2.5"), "C11": (A, None, "4.2"),
    "C12": (N, None, "3.4"), "C13": (C, "gift-note", "6.2"), "C14": (N, None, "CL-3"), "C15": (C, "partner-approval", "7.1"),
    "C16": (N, None, "2.1"), "C17": (N, None, "3.4"), "C18": (N, None, "2.6"), "C19": (C, "ad-label", "2.5"),
    "C20": (A, None, "7.3"), "C21": (N, None, "2.4"), "C22": (N, None, "3.1"), "C23": (A, None, "1.6"),
    "C24": (A, None, "6.5"), "C25": (N, None, "2.4"), "C26": (N, None, "2.2"), "C27": (N, None, "CL-7"),
    "C28": (A, None, "5.3"), "C29": (A, None, "1.6"), "C30": (A, None, "1.6"), "C31": (C, "skill-question", "2.3"),
    "C32": (C, "legal-signoff", "4.1"), "C33": (A, None, "2.4(a)"), "C34": (C, "employee-tag", "6.3"),
    "C35": (C, "terms-link", "CL-2"), "C36": (N, None, "6.1"), "C37": (N, None, "4.6"), "C38": (N, None, "4.3"),
    "C39": (C, "ad-label", "2.5"), "C40": (N, None, "3.1"),
}


def _day(iso: str) -> str:
    day = facts._iso(iso)
    return f"{day.day} {day.strftime('%B %Y')}"


def _ruling(text: str) -> str:
    return f"**Ruling: {text}.**"


def policy() -> str:
    quiet, quiet_cl = P["quiet"], P["quiet_cl"]
    events = "\n".join(f"| {name} | {_day(start)} | {_day(end)} |" for name, start, end in facts.CLEARANCE_EVENTS)
    conditions = {
        "ad-label": "\"#ad\" (or the market's own word for advertising) in the first line of the post, before any other text",
        "gift-note": "the post says plainly that the product was a gift from Northvane",
        "employee-tag": "the post says plainly that the person works for Northvane",
        "skill-question": "every winner correctly answers a skill-testing question before the prize is awarded",
        "terms-link": "the message links to the offer's full terms",
        "price-record": "the price history behind the reference price is saved to the pricing file before launch",
        "legal-signoff": "Legal approves the claim, in writing, before publication",
        "study-on-file": "the study behind the claim is attached to the claim in the claims register",
        "partner-approval": "the partner approves the final communication, in writing, before it goes out",
    }
    assert tuple(conditions) == facts.CONDITIONS
    condition_rows = "\n".join(f"| `{name}` | {text} |" for name, text in conditions.items())
    return f"""# Northvane Nutrition: Brand and Promotions Policy

Version 7. Issued 15 January 2027 by Brand and Legal. This version replaces
version 6 (March 2025) and every regional addendum issued before it. Read
Part 1 first: it says what the words mean and how a case is decided, and
every other Part depends on it.

## Contents

- Part 1: How this policy works (1.1 to 1.11)
- Part 2: Legal minimums (2.1 to 2.8)
- Part 3: Price promotions (3.1 to 3.10)
- Part 4: Product claims (4.1 to 4.9)
- Part 5: Prize promotions (5.1 to 5.6)
- Part 6: People who speak for us (6.1 to 6.8)
- Part 7: Partners and channels (7.1 to 7.8)
- Part 8: Change log (CL-1 to CL-8)
- Annex: Channels
- Schedule A: Clearance events
- Schedule B: Approved health claims
- Schedule C: Studies held for "clinically proven"

## Part 1: How this policy works

### 1.1 Purpose

Northvane Nutrition sells sports nutrition to people who train: athletes,
gym members, runners, cyclists and swimmers. They buy from us because they
trust what we tell them about our products and our prices. This policy keeps
that trust. It sets out what our marketing may say and do, in every market
and channel, so that a proposal can be ruled on quickly and the same way
whoever reviews it. It is also the record we show a retailer, a platform or a
regulator when they ask how we decide.

The policy is written for the brand team, the regional marketing leads, our
agencies and anyone else who plans or approves a marketing action for us.
When this policy and an agency's own guidelines disagree, this policy
applies.

### 1.2 Scope

This policy covers every marketing action that Northvane Nutrition, its
agencies or its partners take for our products in the markets where we sell:
the United States (US), Canada (CA), the United Kingdom (UK), Ireland (IE),
Germany (DE) and Australia (AU).

It covers our three ranges:

- the core range: Northvane Whey Isolate and the Oat Protein Bar, in every
  flavour and size;
- the hydration range: Hydra+ Electrolyte Mix, in every flavour;
- the Surge range: Surge Pre-Workout, which contains caffeine.

It covers these channels: our website, email, SMS, paid social, organic
social, influencer posts, in-store material, podcasts and out-of-home
advertising.

It does not cover customer-service replies to one person, investor or
recruitment communications, or packaging, which the packaging standard
governs. A marketing action that falls outside this scope is not reviewed
under it.

### 1.3 Definitions

The words below have these meanings wherever they appear in this policy.
Other clauses depend on them: a clause covers an action only if the action
is what the clause describes, as defined here.

(a) **Price reduction.** A percentage or fixed-amount discount, a sale or
markdown price (including a "was" and "now" price), a promotional code, or a
loyalty member discount. Free shipping, a gift with purchase and extra
product ("buy two, get a shaker") are not price reductions.

(b) **Stack.** Two or more price reductions applied to one order. A price
reduction together with free shipping or a gift is not a stack.

(c) **Clearance event.** One of the sale periods listed in Schedule A, its
first and last days included. Nothing else is a clearance event, however it
is advertised: flash sales, launch offers and seasonal sales outside those
dates are not.

(d) **New product.** A product, or a flavour or size of one, first sold in
the market less than {P["new_days"]} days before the action's date.

(e) **Comparative claim.** A claim that names, shows or clearly identifies a
competitor or a competitor's product, including "the leading brand" and
"other brands". A comparison with our own earlier product or formula is not
a comparative claim: it is an improvement claim.

(f) **Improvement claim.** A claim that a product is new, improved or
changed compared with our own earlier version of it ("new formula", "now
with more protein").

(g) **Superlative claim.** A claim that our product is the best, the first,
number one, the strongest, the fastest or the most of anything.

(h) **Influencer.** A person, other than an employee, whom we pay in any
amount (a fee, a commission or an affiliate share) to post about our
products, or to whom we give products worth more than ${P["gift_value"]} in
total for a post. Freelancers and contractors, including those who work for
us on other things, are influencers when they post for us on these terms.

(i) **Gifted creator.** A person, other than an employee, to whom we give
products worth ${P["gift_value"]} or less in total, with no payment of any
kind, and who posts about them.

(j) **Employee.** Anyone on Northvane's payroll, full-time or part-time.
Contractors, freelancers and agency staff are not employees.

(k) **Minor-directed.** A communication is minor-directed if any one of
these is true: (1) its targeting includes anyone under 18; (2) it runs in a
placement whose audience the platform reports as more than {P["minor_share"]}% under
18; (3) it shows a person under 18, including the person who posts it.

(l) **Giveaway and contest.** A giveaway picks its winners by chance, in a
draw. A contest picks its winners by skill, judged against published
criteria. A promotion that does both is a giveaway.

(m) **Marketing message.** An email or SMS that promotes a product, an offer
or the brand. An order confirmation, delivery notice or receipt is a
transactional message; but one that also carries a promotion (a code, an
offer, a product recommendation) is a marketing message.

(n) **Co-branded communication.** A communication that carries another
organisation's name or logo as a joint offerer, a sponsor or the beneficiary
of a promotion. A retailer named only as a place to buy ("available at") is
not co-branding.

(o) **Opted in.** A person who has given us marketing consent for that
channel and has not withdrawn it.

(p) **Action's date.** The date on which the action is first published,
sent or goes live.

### 1.4 Rulings and conditions

Every action reviewed under this policy gets one of three rulings:

- **allowed**: it may go ahead as proposed;
- **allowed with condition**: it may go ahead only once the named condition
  is met;
- **not allowed**: it may not go ahead in this form.

A ruling with a condition names exactly one of these conditions:

| Condition | What must be done |
|---|---|
{condition_rows}

A clause that sets a condition gives that ruling whether or not the
proposal says the condition will be met, or already is: the reviewer names
the condition, and the person who meets it records how (1.8).

Every ruling cites the one clause that decides it, by its number as this
policy numbers it (for example 3.4, 2.4(a) or CL-2).

### 1.5 How to decide a case

Take these steps in this order. Only clauses that state a ruling decide
cases; clauses about process (records, approvals, roles, training) never do.

**Step A. The policy in force.** Use the policy as the change log (Part 8)
has amended it on the action's date. An entry takes effect on its effective
date and changes the clause it names from that date on: it replaces that
clause's text, or deletes the clause. An entry whose effective date is after
the action's date does not apply to the action, even if it was approved
before. A replaced clause keeps its place in the policy: the clauses it is
an exception to, and the exceptions to it, stay as they are. When a clause
that an entry has replaced decides a case, cite the entry (for example
CL-3), not the clause it replaced.

**Step B. What each clause covers.** Read each clause with the definitions
in 1.3. A clause covers an action only if the action is what the clause
describes, as defined.

**Step C. Exceptions.** An exception applies only to an action that a clause
it names covers. When it applies, it displaces that clause: the clause no
longer counts for the action, and the exception counts in its place with its
own ruling. An exception to an exception, when it applies, displaces that
exception and decides nothing itself, so the clause the first exception
named counts again. No clause outside Part 2 displaces a Part 2 clause,
whatever it says; only an exception in Part 2 can.

**Step D. The strictest ruling.** Of the clauses that still count, the
strictest ruling decides: not allowed over allowed with condition, and
allowed with condition over allowed.

**Step E. Ties.** If more than one clause with that ruling still counts, the
one in Part 2 decides; otherwise the one with the lowest number.

**Step F. The default.** If no clause counts, clause 1.6 decides.

### 1.6 The default

An action that no clause of this policy covers may go ahead.
{_ruling("allowed")}

### 1.7 Who reviews

Regional marketing leads review the actions of their own markets. The brand
team reviews every action that runs in more than one market, every
influencer contract and every co-branded communication. Legal reviews any
action a reviewer is unsure about, and every action that needs `legal-signoff`.
A reviewer who planned or wrote an action does not review it. Reviews are
due within three working days of a complete proposal; a proposal that lacks
its date, market, channel or the facts a clause turns on is returned, not
ruled on.

### 1.8 Records

Every ruling is logged in the review tracker with the proposal, the ruling,
the condition (if any), the deciding clause and the reviewer's name. Logs are
kept for six years. When a condition is met, the person who met it records
how (the label added, the approval received, the study attached) before the
action goes live. An action that goes live without its condition met is a
breach of this policy, reported to the brand director the same day.

### 1.9 Training and questions

Everyone who plans or approves marketing for Northvane completes this
policy's training within a month of starting and again after each new
version. Questions about how to read a clause go to the brand team's policy
channel; answers that change how a clause is read are added to the change
log, never sent only by message.

### 1.10 What a proposal contains

A proposal is ruled on only when it gives everything a clause could turn on.
It states the action's date, the market (one proposal per market when the
facts differ between markets), the channel and placement, the products and
ranges it features, every price reduction and how they combine on an order,
any free shipping or gift, every claim in the words it will use with the
evidence behind it, every person who appears in it or posts it (with their
age and what we pay or give them), any other organisation named in it, the
audience and its targeting, the list it is sent to and the send time. A
reviewer rules on the proposal as written and does not assume facts it does
not state.

### 1.11 Urgent reviews

A proposal that must go live within three working days is marked urgent in
the review tracker and reviewed the same day by the brand team's on-call
reviewer. Urgency changes who reviews and how fast, never the ruling: an
urgent proposal is decided by exactly the same clauses as any other. Nothing
goes live while a review is open.

## Part 2: Legal minimums

The clauses in this Part set out the minimum our markets' rules require of
us, as Legal has written them for our business. The brand rules in Parts 3
to 7 add to them; under 1.5 step C nothing outside this Part displaces them,
and under step E a Part 2 clause decides a tie.

### 2.1 Disease claims

No communication may claim, or imply, that a product prevents, treats or
cures a disease or its symptoms, in any market or channel. This includes
claims about colds, infections, joint conditions and heart health.
{_ruling("not allowed")}

### 2.2 No purchase necessary

A giveaway must be open to enter without buying anything. A giveaway that
requires a purchase to enter, or that gives buyers a better chance to win,
may not run. A contest may require a purchase (Part 5 still applies to it).
{_ruling("not allowed")}

### 2.3 Canada: skill-testing question

A giveaway that runs in Canada may award a prize only to a winner who has
correctly answered a skill-testing question.
{_ruling("allowed with condition `skill-question`")}

### 2.4 Consent for marketing messages

A marketing message may be sent only to people who have opted in to that
channel. A marketing message to anyone who has not opted in may not be sent.
{_ruling("not allowed")}

### 2.4(a) Exception to 2.4: existing customers in the UK and Ireland

In the UK and Ireland, a marketing email (not an SMS) may be sent to
customers who ordered from us in the last {P["soft_months"]} months, were
given the chance to opt out when they ordered, and have not opted out.
{_ruling("allowed")}

### 2.5 Disclosure of influencer content

Every post by an influencer about our products must be identified as
advertising.
{_ruling("allowed with condition `ad-label`")}

### 2.6 The Surge range and minors

No minor-directed communication may promote the Surge range, in any market
or channel.
{_ruling("not allowed")}

### 2.7 Contact with regulators

Only Legal answers a regulator, a platform's policy team or a consumer body
about our marketing. Anyone who is contacted passes the contact to Legal on
the same day and says nothing about the substance. Legal records every
contact and its outcome in the review tracker.

### 2.8 Notes for Legal by market

Legal keeps a short note for each market listing the regulators, platforms
and industry codes that apply there, and the contacts at our outside counsel.
The notes are reviewed every six months and whenever a change-log entry
touches Part 2. They explain where the clauses in this Part come from; they
are not clauses, and a reviewer decides a case by the clauses above, not by
the notes.

## Part 3: Price promotions

Price promotions are the most common actions we review, and the ones
customers notice first when they are wrong. A discount that is too deep, or
discounts that pile up on one order, teach customers to wait for the next
sale and make our regular prices look false; a reference price that was
never really charged misleads them outright. The clauses below set the
limits, and the exceptions say where we have decided a deeper or combined
offer is fair. A "regular price" in this Part is the price a product sells
at when no price reduction applies.

### 3.1 Depth of a price reduction

No single price reduction may take more than {P["depth"]}% off a product's
regular price. A reduction deeper than that may not run.
{_ruling("not allowed")}

### 3.2 Exception to 3.1: clearance events

During a clearance event, a single price reduction of up to {P["clearance_depth"]}%
may run.
{_ruling("allowed")}

### 3.3 Exception to 3.2: new products

Clause 3.2 does not apply to a new product: a clearance event does not allow
a reduction of a new product beyond the limit in 3.1. This exception decides
nothing itself; clause 3.1 counts again.

### 3.4 Stacking

An order may receive only one price reduction. A stack may not be offered.
{_ruling("not allowed")}

### 3.5 Exception to 3.4: loyalty members

A loyalty member's discount may be stacked with one promotional code, and
with nothing else.
{_ruling("allowed with condition `terms-link`")}

### 3.6 Exception to 3.5: clearance events

Clause 3.5 does not apply during a clearance event. This exception decides
nothing itself; clause 3.4 counts again.

### 3.7 Reference prices

A "was" or "regular" price shown beside a lower price must have been the
price charged for at least {P["reference_days"]} days in the six months
before the reduction starts. When it was, the reference price may be shown.
{_ruling("allowed with condition `price-record`")} When it was not, it may
not. {_ruling("not allowed")}

### 3.8 Promotion calendar

Every price promotion is entered in the promotion calendar at least ten
working days before it starts, with its dates, markets, products and depth.
Regional leads check the calendar for overlaps every Monday and tell the
brand team about any two promotions that would run on the same product at
once.

### 3.9 Pricing errors

When a price is shown wrongly (a missing digit, the wrong market's price), the
web team corrects it as soon as it is found and the regional lead decides,
with Legal, whether orders already placed are honoured. A pricing error is
not a price reduction and is not reviewed under 3.1 to 3.7.

### 3.10 Retailers and marketplaces

Retailers that stock our products set their own prices, and this Part does
not review them. It does apply to every price we set ourselves, on our
website, in our own marketplace stores and in promotions we fund at a
retailer. When we fund a retailer's promotion, the retailer's price is
treated as our price reduction and is reviewed under 3.1 to 3.7 like any
other.

## Part 4: Product claims

A claim is anything a communication says or shows about what a product is,
does or is worth. Every claim we make must be one we can prove on the day it
is made, with evidence that is ours to show. Sports nutrition attracts
claims that sound scientific and are not; we would rather make fewer claims
and stand behind each of them. Comparisons with competitors need more care
than any other claim, because the competitor can challenge them.

### 4.1 Comparative claims

A comparative claim needs Legal's written approval before it is published.
{_ruling("allowed with condition `legal-signoff`")}

### 4.2 Exception to 4.1: price comparisons

A comparative claim that is only about price, made against a competitor's
published price checked no more than {P["price_check_days"]} days before
the action's date, needs no approval beyond this policy.
{_ruling("allowed")}

### 4.3 Superlatives

A superlative claim needs independent data (a panel, a test or a survey that
we did not run) less than {P["superlative_months"]} months old on the
action's date. With such data, the claim may be made.
{_ruling("allowed with condition `study-on-file`")} Without it, it may not.
{_ruling("not allowed")}

### 4.4 Health claims

A claim that a product supports or affects a body function may be made only
in the exact words of an approved claim in Schedule B, for the range it is
listed for. {_ruling("allowed")} Any other health claim may not be made.
{_ruling("not allowed")} Nutrition facts, such as "20 g of protein per scoop",
are not health claims.

### 4.5 "Clinically proven"

No communication may describe a product, or anything about it, as
"clinically proven" or "clinically tested".
{_ruling("not allowed")}

### 4.6 Improvement claims

An improvement claim may be made for {P["improvement_months"]} months after
the change it describes. Made later than that, it may not.
{_ruling("not allowed")}

### 4.7 Claims register

Legal keeps the claims register: every claim we use, the evidence behind it,
the date the evidence was produced and the date it next needs checking. A
claim not in the register is added, with its evidence, before the action
that uses it is ruled on. The register is checked in full every January.

### 4.8 Writing claims well

Say what the evidence shows, in plain words, and no more. Give nutrition
facts per serving and name the serving ("per 30 g scoop"). Avoid "up to"
unless the evidence gives a range and the top of it is common. Do not round
a figure in our favour. Keep a claim and the words that limit it ("in a
two-week trial", "for adults") in the same sentence and the same size of
type. These are writing guidance for the brand team and agencies; they do
not change which clause decides a case.

### 4.9 Translations

A claim translated for another market keeps the meaning of the approved
English claim. Legal checks every German translation of a claim before it is
used, and the regional lead checks the others. A translation is a new claim
for the claims register only when its meaning differs from the English.

## Part 5: Prize promotions

Giveaways and contests build our audience quickly, and they go wrong in
public when the rules are unclear, the prize is out of proportion or the
promotion runs where we cannot run it properly. Part 2 sets the minimums
that apply to every giveaway; this Part adds our own.

### 5.1 Official rules

Every giveaway and contest needs official rules (who may enter, how, until
when, the prize, how winners are picked and told) published before it opens.
One without published rules may not open.
{_ruling("not allowed")}

### 5.2 Prize value

No single prize may be worth more than ${P["prize_cap"]:,} (or the same in
the market's currency on the day the promotion opens).
{_ruling("not allowed")}

### 5.3 Exception to 5.2: contests

A contest may offer a single prize worth up to ${P["contest_cap"]:,}.
{_ruling("allowed")}

### 5.4 Markets where we do not run giveaways

We do not run giveaways in Germany (DE). Contests may run there.
{_ruling("not allowed")}

### 5.5 Winners and records

Winners are picked within ten working days of the closing date, by a person
who did not plan the promotion, and told within five working days after
that. The entries, the draw or the judges' scores, and proof that each prize
was delivered are kept for two years.

### 5.6 Prize fulfilment and taxes

Prizes are sent by tracked delivery within thirty days of a winner
accepting. A prize that cannot be delivered is offered to the next eligible
entrant in the order of the draw or the judges' scores. Where a market taxes
prizes, the official rules say who pays the tax, and Finance files any
return that is due. A cash alternative is offered only when the official
rules say so.

## Part 6: People who speak for us

People trust a person more than an advertisement, which is why we work with
creators, athletes and our own staff, and why the audience must always know
when someone speaks for us. Who a person is under the definitions in 1.3
(an influencer, a gifted creator, an employee) decides which of these
clauses apply to their post, and Part 2 applies to them as well.

### 6.1 Influencers' age

Every influencer must be at least 18 years old on the action's date. An
influencer under 18 may not post for us.
{_ruling("not allowed")}

### 6.2 Gifted creators

A gifted creator's post about our products must say that the product was a
gift.
{_ruling("allowed with condition `gift-note`")}

### 6.3 Employees

An employee who posts about our products on their own accounts must say that
they work for Northvane.
{_ruling("allowed with condition `employee-tag`")}

### 6.4 Reviews in advertising

A customer review may be quoted in advertising only if the reviewer is a
verified buyer of the product reviewed. A review from anyone not verified as
a buyer may not be used.
{_ruling("not allowed")}

### 6.5 Exception to 6.2 and 2.5: platform labels

A post that has the platform's own paid-partnership label switched on needs
no other label or note.
{_ruling("allowed")}

### 6.6 Contracts and briefs

Every influencer works under a written contract that sets the fee or the
value of the products, the posts, their dates and the right to ask for
changes, and that requires the influencer to follow this policy. Every post
is briefed in writing. The brand team keeps the contracts and the briefs for
three years after the last post.

### 6.7 The ambassador programme

Ambassadors are athletes under a contract of at least a year who post about
our products and appear at our events. We pay them, so under 1.3(h) they are
influencers whenever they post for us, and every clause about influencers
applies to their posts. The brand team renews or ends each contract at its
anniversary, after reviewing the ambassador's posts against this policy.

### 6.8 Ending a relationship

When we end a contract with an influencer, a gifted creator or an
ambassador, the brand team asks them in writing to keep any disclosure on
past posts and to stop using our codes. Their past posts are not reviewed
again unless we pay to promote them, in which case each promotion is a new
action, ruled on as of its own date.

## Part 7: Partners and channels

Working with another organisation puts both names on the line, so we agree
every co-branded communication with the partner and choose partners who fit
a brand for people who train. The channel clauses here protect the people
we message, beyond the consent rules in Part 2.

### 7.1 Co-branded communications

A co-branded communication needs the partner's written approval of the
final version.
{_ruling("allowed with condition `partner-approval`")}

### 7.2 Restricted partners

We do not co-brand with alcohol, gambling or tobacco brands.
{_ruling("not allowed")}

### 7.3 Exception to 7.1: charity beneficiaries

A co-branded communication whose only other organisation is a registered
charity, named as the beneficiary of a donation we make, needs no partner
approval.
{_ruling("allowed")}

### 7.4 Partner lists

A co-branded email goes only to our own list. One sent to a partner's list
may not be sent.
{_ruling("not allowed")}

### 7.5 Quiet hours for SMS

No marketing SMS may be sent between {quiet[0]} and {quiet[1]} in the
recipient's local time. One timed inside those hours may not be sent.
{_ruling("not allowed")}

### 7.6 Frequency

We send no more than three marketing emails and two marketing SMS a week to
any one person, across all campaigns. The CRM team checks the plan against
this every Friday and moves sends that break it; this is a planning rule and
does not change a ruling.

### 7.7 In-store and out-of-home

Shelf talkers, posters, sampling stands and billboards follow the same
clauses as any other channel. Their action's date is the first day they are
on display. Material for a retailer's store is sent to the retailer for its
own checks after our ruling, and their changes come back to us for a new
ruling if they alter a price, a claim or a person shown.

### 7.8 Podcasts

A host-read advertisement is scripted by us and read as written. The script
is ruled on like any other communication, and the host is an influencer if
we pay them to read it on their own show. Ad-free mentions a host makes
unprompted are not our communications and are not reviewed.

## Part 8: Change log

Each entry takes effect on its effective date and changes the clause it
names from that date on (1.5 step A). Entries are listed in the order they
take effect.

### CL-1 (effective {_day("2026-05-01")}): replaces 7.5

No marketing SMS may be sent between {quiet_cl[0]} and {quiet_cl[1]} in the
recipient's local time. One timed inside those hours may not be sent.
{_ruling("not allowed")}

### CL-2 (effective {_day("2026-06-01")}): replaces 3.5, the exception to 3.4

In the US and Canada only, a loyalty member's discount may be stacked with
one promotional code, and with nothing else.
{_ruling("allowed with condition `terms-link`")}

### CL-3 (effective {_day("2026-07-01")}): replaces 4.5

A product may be described as "clinically proven" only for the property a
study listed for it in Schedule C supports.
{_ruling("allowed with condition `study-on-file`")} Any other product, or any
other property, may not be. {_ruling("not allowed")}

### CL-4 (effective {_day("2026-09-01")}): replaces 5.4

We do not run giveaways in Germany (DE) or Australia (AU). Contests may run
there. {_ruling("not allowed")}

### CL-5 (effective {_day("2026-10-15")}): replaces 3.1, the clause 3.2 is an exception to

No single price reduction may take more than {P["depth_cl"]}% off a
product's regular price. A reduction deeper than that may not run.
{_ruling("not allowed")}

### CL-6 (effective {_day("2026-12-01")}): process only

The promotion calendar in 3.8 moves to the shared planning board. No clause
that states a ruling changes.

### CL-7 (effective {_day("2027-01-01")}): replaces 6.1

Every influencer must be at least 18 years old on the action's date, and at
least {P["surge_age_cl"]} for a post about the Surge range. An influencer
younger than that may not post for us.
{_ruling("not allowed")}

### CL-8 (effective {_day("2027-06-01")}, approved 10 January 2027): deletes 4.3

Clause 4.3 is deleted. Superlative claims will be handled by the claims
register (4.7) from then on.

## Annex: Channels

These descriptions say what each channel name in this policy refers to.
They are not definitions in the sense of 1.3, and they never change which
clause covers an action.

- **Website**: our own online stores in each market, including product
  pages, banners and the checkout.
- **Email** and **SMS**: messages we send to a person's inbox or phone,
  from any system we use. Whether one is a marketing message is decided by
  1.3(m).
- **Paid social**: advertisements we pay a social platform to show,
  targeted by the platform's tools.
- **Organic social**: posts on our own social accounts that we do not pay to
  promote. A post we pay to promote becomes paid social from the moment we
  pay.
- **Influencer post**: a post about our products on a person's own account.
  Who the person is (1.3(h) to (j)) decides which clauses of Part 6 and
  Part 2 apply to it.
- **In-store**, **out-of-home** and **podcast**: as described in 7.7 and
  7.8.

## Schedule A: Clearance events

| Event | First day | Last day |
|---|---|---|
{events}

## Schedule B: Approved health claims

Use these words exactly, only for the range given.

| Range | Approved claim |
|---|---|
| core | Protein contributes to the growth of muscle mass. |
| core | Protein contributes to the maintenance of muscle mass. |
| hydration | Potassium contributes to normal muscle function. |
| hydration | Magnesium contributes to a reduction of tiredness and fatigue. |
| Surge | Caffeine contributes to increased alertness (adults only). |

## Schedule C: Studies held for "clinically proven"

| Product | Property the study supports | Study |
|---|---|---|
| {facts.SCHEDULE_C[0]} | dissolves fully in 10 seconds | laboratory study, March 2026 |
| {facts.SCHEDULE_C[1]} | caffeine content per scoop as labelled | laboratory study, May 2026 |
"""


def cases() -> str:
    blocks = []
    for case in facts.CASEBOOK_CASES:
        blocks.append(
            f"## {case['id']}: {case['title']}\n\n"
            f"- Date: {_day(case['date'])}\n- Market: {case['market']}\n- Channel: {case['channel']}\n\n"
            f"{case['text']}\n"
        )
    return (
        "# Proposed marketing actions for review\n\n"
        "Forty actions the regional teams have proposed. Each gives the action's date (the day it is first "
        "published, sent or goes live), its market and its channel, then what the team wants to do. "
        "Nothing beyond what each case says is known about it.\n\n" + "\n".join(blocks)
    )


def build() -> dict[str, str]:
    files = {"policy.md": policy(), "cases.md": cases()}
    _check(files)
    return files


def _check(files: dict[str, str]) -> None:
    rulings = facts.casebook_rulings(facts.CASEBOOK_CASES)
    assert [case["id"] for case in facts.CASEBOOK_CASES] == [f"C{i:02d}" for i in range(1, 41)]
    for case in facts.CASEBOOK_CASES:
        decided = rulings[case["id"]]
        assert (decided["ruling"], decided["condition"], decided["clause"]) == EXPECTED[case["id"]], (case["id"], decided)
        # Exactly one deciding clause at the last step: one clause of the
        # strictest ruling, or a tie that one Part 2 clause breaks.
        top = decided.get("top", [])
        assert len(top) <= 1 or len(decided["part_two_in_top"]) == 1, (case["id"], top)
        if decided["ruling"] == C:   # never two conditions owed at once
            assert len(top) == 1, (case["id"], top)
    groups = {}
    for case in facts.CASEBOOK_CASES:
        groups.setdefault(case["group"], []).append(case["id"])
    assert set(groups) == set(facts.CASEBOOK_GROUPS)
    assert {len(ids) for ids in groups.values()} <= {3, 4, 5, 6}
    rulings_by_kind = [decided["ruling"] for decided in rulings.values()]
    assert min(rulings_by_kind.count(kind) for kind in (A, C, N)) >= 9
    # Every clause the cases cite is a clause of the policy, written as a heading.
    for decided in rulings.values():
        assert f"### {decided['clause']} " in files["policy.md"] or f"### {decided['clause']}\n" in files["policy.md"], decided["clause"]
    assert len(files["policy.md"].encode()) >= 30_000, len(files["policy.md"].encode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    built = build()
    stale = [name for name, text in built.items() if not (HERE / name).exists() or (HERE / name).read_text() != text]
    if args.write:
        for name, text in built.items():
            (HERE / name).write_text(text)
        print(f"wrote {len(built)} files")
        return 0
    if stale:
        print("out of date: " + ", ".join(stale))
        return 1
    print("up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
