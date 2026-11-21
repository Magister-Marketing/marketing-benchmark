# Tallyhour: competitor comparison, brief

From Priya Raman, product marketing. Tallyhour sells time tracking and invoicing to agencies. Sales
wants one comparison table of us and our five closest competitors, and I want to know which of our
draft claims the table can back. The six pricing pages were saved from the sites today: `tallyhour.md`, `brisktime.md`, `quillhour.md`, `ticklog.md`, `fenwork.md`, `larchpoint.md`.

## The attributes

One row per company, one column per attribute:

- `free_plan`: whether the company offers a plan that is free with no time limit. A free trial is
  not a free plan.
- `trial_days`: the length of the free trial in days, and 0 when the page says there is no free
  trial. A money-back guarantee is not a free trial.
- `entry_plan`: the name of the entry plan, the cheapest plan with a price above $0, as the page
  names it.
- `entry_price_usd`: the entry plan's price per user per month, on a monthly basis (below).
- `entry_min_users`: the fewest users the entry plan can be bought for.
- `sso_on_entry`: whether the entry plan includes single sign-on.
- `sso_cheapest_plan`: the name of the cheapest plan that includes single sign-on.
- `invoicing_on_entry`: whether the entry plan includes invoicing.
- `api_on_entry`: whether the entry plan includes API access.
- `top_plan_price_usd`: the price per user per month, on a monthly basis, of the top plan: the
  plan listed last in the company's plan table.
- `uptime_sla_percent`: the highest uptime the company commits to in a service-level agreement,
  on any plan, as a percentage.
- `eu_hosting`: whether customer data can be hosted in the EU, on any plan.

## Rules for every cell

1. A cell holds the value the company's own page states, or exactly `not stated` when the page
   does not state it. Do not infer a value from what a page leaves out: a feature or a plan the
   page does not mention is `not stated`, not `no`.
2. In a plan table a check mark (✓) means the plan includes it and a dash (—) means it does not.
3. A price the page replaces with "Contact sales", "custom" or a quote is `not stated`.
4. Monthly basis: when a plan has a price billed monthly, that is its price, even if the page
   also gives a lower price for annual billing. When a plan is sold only on annual billing, its
   price is its price per user per year divided by 12, rounded to the cent.
5. Each page's FAQ was updated after its plan table. Where a page's FAQ and its plan table
   disagree, the FAQ is right.
6. Write yes or no as `yes` or `no`, a price in US dollars with two decimals and no currency sign,
   a percentage without the % sign, a number of days or users as a whole number, and a plan by
   its name alone.

## The draft claims

1. Tallyhour's entry plan costs less per user per month than any competitor's entry plan.
2. Tallyhour is the only one of the six with a free plan.
3. Tallyhour's 21-day free trial is the longest of the six.
4. Tallyhour includes single sign-on on its entry plan, and no competitor includes it on theirs.
5. Tallyhour's top plan costs less per user per month than any competitor's top plan.

A claim is `supportable` when the table's cells prove it and `not supportable` otherwise. A claim
that something holds for every competitor, or that no competitor has something, needs every
competitor's cell: a `not stated` cell cannot support it. "Less" and "longest" are strict: a tie
does not support them.
