# Tallyhour: competitor comparison, brief

From Priya Raman, product marketing. Tallyhour sells time tracking and invoicing to agencies. Sales
wants one comparison table of us and our nine closest competitors, and I want to know which of our
draft claims the table can back. The ten pricing pages were saved from the sites today: `tallyhour.md`, `brisktime.md`, `quillhour.md`, `ticklog.md`, `fenwork.md`, `larchpoint.md`, `clockwell.md`, `pacemark.md`, `hourglen.md`, `ledgerline.md`.

## The attributes

One row per company, one column per attribute:

- `free_plan`: whether the company offers a plan that is free with no time limit. A free trial is not a free plan.
- `trial_days`: the length of the free trial in days, and 0 when the page says there is none.
- `entry_plan`: the entry plan's name: the cheapest plan with a price above $0, on a monthly basis.
- `entry_price_usd`: the entry plan's price per user per month, on a monthly basis.
- `entry_min_users`: the fewest users the entry plan can be bought for.
- `entry_projects`: the active projects the entry plan allows, or `unlimited`.
- `top_plan_price_usd`: the price per user per month, on a monthly basis, of the top plan: the plan listed last in the plan table.
- `sso_on_entry`: whether the entry plan includes single sign-on.
- `sso_cheapest_plan`: the cheapest plan that includes single sign-on, or `none` when no plan does.
- `audit_log_cheapest_plan`: the cheapest plan that includes an audit log, or `none` when no plan does.
- `invoicing_on_entry`: whether the entry plan includes invoicing.
- `api_on_entry`: whether the entry plan includes API access.
- `approvals_on_entry`: whether the entry plan includes timesheet approvals.
- `budgets_on_entry`: whether the entry plan includes project budgets.
- `phone_support_on_entry`: whether the entry plan includes phone support.
- `mobile_app`: whether the company offers a mobile app, on any plan.
- `uptime_sla_percent`: the highest uptime the company commits to in a service-level agreement, on any plan.
- `eu_hosting`: whether customer data can be hosted in the EU, on any plan.
- `soc2_type2`: whether the company holds a SOC 2 Type II report.
- `dpa`: whether the company signs a data processing agreement with customers.

## Rules for every cell

1. A cell holds the value the company's own page states, or exactly `not stated` when the page
   does not state it. Do not infer a value from what a page leaves out: a feature, a plan or a
   report the page does not mention is `not stated`, not `no`.
2. In a plan table a check mark (✓) means the plan includes it and a dash (—) means it does not.
3. Where parts of one page disagree, the newest wins. Each changelog entry is dated and overrides
   everything else on the page; the FAQ was updated after the plan table and overrides it; the plan
   table and its footnotes override the introduction, the feature list and the other sections.
4. A footnote that makes a feature a paid add-on means the plan does not include it. A footnote
   that only limits a feature (a cap or a quota) leaves it included.
5. A feature, hosting option or report the page calls in beta, coming, planned or in progress is
   not included or held: `no`. Only a SOC 2 Type II report counts for `soc2_type2`: a Type I
   report is `no`.
6. An uptime figure the page gives as a target, an aim or a status-page history is not a
   service-level agreement. A money-back guarantee is not a free trial.
7. Monthly basis: when a plan has a price billed monthly, that is its price, even if the page
   also gives a lower price for annual billing. When a plan is sold only on annual billing, its
   price is its price per user per year divided by 12, rounded to the cent. A price the page
   replaces with "Contact sales" is `not stated`.
8. Write yes or no as `yes` or `no`, a price in US dollars with two decimals and no currency sign,
   a percentage without the % sign, days, users and projects as whole numbers, unlimited projects
   as `unlimited`, a plan by its name alone, and `none` when no plan includes the feature.

## The draft claims

1. Tallyhour's entry plan costs less per user per month than every competitor's entry plan.
2. Tallyhour is one of only two of the ten with a free plan.
3. No competitor includes single sign-on on its entry plan; Tallyhour does.
4. Tallyhour's free trial is longer than the free trial of every competitor that offers one.
5. Tallyhour is the only one of the ten whose entry plan includes both timesheet approvals and project budgets.
6. Tallyhour is one of only three of the ten with both a SOC 2 Type II report and EU hosting.
7. Tallyhour's top plan costs less per user per month than the top plan of every competitor that offers EU hosting.
8. Every competitor's entry plan needs at least two users; Tallyhour's can be bought for one.
9. Tallyhour is the only one of the ten with phone support on its entry plan.

A claim is `supportable` when the table proves it: it must hold whatever value any `not stated`
cell might really have. Otherwise it is `not supportable`. "Less", "longer" and "only" are strict:
a tie does not support them.
