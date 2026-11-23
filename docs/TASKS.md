# Tasks

[Back to the overview](../README.md) · [How scoring works](SCORING.md) ·
[See scored examples](SCORED_EXAMPLES.md) ·
[Simulated companies](SIMULATED_COMPANIES.md)

A task is a realistic marketing assignment with its own source material and a
pass/fail checklist. Every model and setup on a board receives the same task.

- **The assignment** (the task's `prompt`) says what to produce and in what
  form.
- **The source material** (its `fixtures`) supplies the facts the model may
  use. Brands, people and figures are invented, except the headline pairs of
  the two forecast tasks, which come from real tests.
- **The skill guidance** is the task's listed SKILL.md files from
  [marketingskills](https://github.com/coreyhaines31/marketingskills). Only the
  "+ Marketing Skills" setup gets them in the prompt
  ([provenance](../evals/fixtures/public/skills/README.md)).
- **The checklist** (its `rubric`) lists every requirement the answer must
  meet. Some are checked by a program, the rest by the judge
  ([how](SCORING.md#how-an-answer-is-checked)).

The task files in `eval_runner/tasks/` are the source of truth. There are 49.
`eval_runner/board.json` places every one of them in exactly one of three
lists, and `tests/test_board.py` fails the build otherwise:

- **the board**: 35 tasks, five in each of seven areas of marketing;
- **held back**: the 4 tasks of the holdout split;
- **left out**: 10 open tasks that stay in the repository and run by id, but
  are not on the board, each with the reason.

`--split board` runs the board's 35 in the file's order (on
`python -m eval_runner.bench run` and `python -m eval_runner.bench eval`).

The descriptions below say what each task asks for and what makes it hard,
as its prompt and files set it out. They do not give the answers. "Checks"
is the number of requirements in the task's current rubric, and how many of
them a program decides.

This page covers the tasks where a model writes an answer from supplied files.
A second, newer kind, where a model works inside a simulated company, is
described in [Simulated companies](SIMULATED_COMPANIES.md). It is not on the
board.

## The board: 35 tasks in seven areas

### Copywriting

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [Hero headlines](../eval_runner/tasks/headline.json) | Five launch headline options for a product's website hero, each with a one-line rationale | Staying punchy while every product fact comes from the supplied sources | 6 (1) |
| [Conflicting brief repair](../eval_runner/tasks/source-conflict-repair.json) | A 12-row register of the agency brief's unsupported or contradictory claims, and one corrected Meta ad concept | Splitting the brief into separate claims and following the authoritative sources wherever they disagree with it | 18 (0) |
| [Price change rollout](../eval_runner/tasks/price-change-rollout.json) | All 14 customer-facing assets of a subscription product, returned after a price change, with a change log and labelled figures | Changing everything the change brief changes and nothing else, with every ad and the banner inside its limit and the brief's notices exactly where it says | 19 (18) |
| [Launch copy pack](../eval_runner/tasks/launch-copy-pack.json) | Every asset a placements table calls for, for four air purifiers, as one file of copy | Every figure and claim must come from a claims-register row usable for that product and channel on the launch day, within each placement's limit and the voice rules; a spec sheet and last year's launch copy are supplied for reference only | 15 (14) |
| [Claims check](../eval_runner/tasks/claims-check.json) | A verdict on each of 150 numbered claims across six product pages (supported, contradicted or unsupported), and the pages rewritten | Deciding each claim by the prompt's rules: final lab results only, figures for the same product, measure and group of people, and prices and offers in force on the day the pages go live | 14 (13) |

### Paid ads

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [Meta ad concepts](../eval_runner/tasks/ad-creatives.json) | Three Meta feed ad concepts with labelled fields and a fixed call to action | Concepts aimed at genuinely different audience motivations, each testable, without inventing proof | 9 (2) |
| [Search account build](../eval_runner/tasks/search-account-build.json) | Five files for a new Google Ads account (keywords by campaign and ad group, exclusions with reasons, negatives, daily budgets, one ad per ad group) from a keyword export and an account standard | Applying the standard's ordered steps to every keyword in the export without a slip, with every ad inside its limits and wording rules | 19 (18) |
| [Search terms review](../eval_runner/tasks/search-terms-negatives.json) | Negative keywords by theme, terms to promote and terms kept, from a month's search terms report, with labelled figures | Blocking what the business does not sell or do without blocking searches it wants, and promoting only the terms the definitions allow | 12 (5) |
| [Launch brief to trafficking sheet](../eval_runner/tasks/launch-trafficking.json) | Three files for a launch on Meta, Google Search, LinkedIn and email: a budget by channel and week, every asset's text fields, and a tracked final URL per asset | Many short pieces of copy under differing hard limits, each written for its own audience, with ids and URLs built exactly to a tracking standard | 19 (18) |
| [Channel budget allocation](../eval_runner/tasks/channel-budget-allocation.json) | A quarter's demand budget split across twelve channels, three regions and three months in $10,000 blocks: every cell, the licence fees, which named constraints bind, and labelled figures | Finding the one split that projects the most leads while every rule in the planning brief holds at once; last quarter's results are supplied too | 17 (16) |

### SEO and content

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [SEO blog post](../eval_runner/tasks/blog-post.json) | A long-form article answering "Why is my furnace making noise?", with an SEO title, a meta description and a booking link | Using only the current figure where a later source replaced an earlier one, linking exactly the pages a written rule picks from a site map, and keeping safety and emergency advice responsible | 14 (11) |
| [Content brief](../eval_runner/tasks/seo-content-brief.json) | A content brief for one new article, from a keyword export, the site's pages and competitors' outlines for three candidate topics | Choosing the topic and its keywords by the brief's own definitions of winnable clicks, not by search volume alone | 16 (12) |
| [Technical SEO triage](../eval_runner/tasks/seo-technical-triage.json) | A prioritised fix list from a site crawl, with labelled figures | Counting each issue type exactly under the given definitions, leaving correctly configured URLs alone, and ordering the issues by the traffic of the pages they affect | 14 (7) |
| [Redirect map](../eval_runner/tasks/seo-redirect-map.json) | A file of 301 and 410 redirects for a shop moving platform, with labelled counts | Applying the agreed migration rules to every old URL, in order, against the old crawl and the new site's staging crawl | 15 (15) |
| [Titles and meta descriptions](../eval_runner/tasks/seo-titles-meta.json) | A title and a meta description for every page the SEO lead's rules cover, with labelled counts | Hard rules on every page (lengths, suffixes, keywords, prices) and pages that share a keyword, which the rules settle | 16 (16) |

### Email and lifecycle

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [Email-flow repair](../eval_runner/tasks/email-flow-repair.json) | A corrected four-email onboarding sequence | Finding every defect in an agency draft against the supplied facts and guidance, with no kinds of defect named, while keeping what is accurate | 14 (0) |
| [Re-engagement programme](../eval_runner/tasks/lifecycle-reengagement.json) | An audience with counts and exclusions, a three-email flow in two versions, and what happens next, from a subscriber export | Applying the given definitions and the email policy (consent, offers, cadence, sunset) exactly | 15 (6) |
| [Cold outbound sequences](../eval_runner/tasks/outbound-sequence.json) | Three files for a cold outbound programme: exclusions with reasons, every other lead's segment and country group, and every email of every sequence | Deciding exclusions, segments and country rules in order over every lead, then writing each email within the standard's limits and required wording, using only the facts sheet | 22 (21) |
| [Email compliance crosscheck](../eval_runner/tasks/email-compliance-crosscheck.json) | A verdict on each scheduled email of two brands in four regions (pass, or each broken rule's code with the row that proves it), a fix for each code, and labelled counts | Joining each email, on its own send date, with the sending policy and six other exports: audiences and consent, the sender map, registered addresses, promotions, prices and DNS records | 14 (13) |
| [Email send calendar](../eval_runner/tasks/email-send-calendar.json) | A month's send calendar for a campaign plan, every subscriber's email count for the month, and labelled figures | Following the calendar policy and its frequency cap exactly, with each campaign's audience counted on its own send date | 13 (12) |

### Landing pages and conversion

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [Landing page](../eval_runner/tasks/landing-page.json) | A complete single-file HTML landing page for a paid consultation | The section order a cautious first-time visitor needs, careful claims and limitations, one primary action, and valid page structure | 10 (4) |
| [Landing-page repair](../eval_runner/tasks/landing-page-repair.json) | A corrected single-file HTML page | Fixing every planted factual, safety, proof, urgency, action, structure and implementation defect while keeping the required section order and call to action | 19 (4) |
| [A/B test readout](../eval_runner/tasks/ab-test-readout.json) | A readout and recommendation for a pricing-page test, from daily results by device and traffic source and the test plan, with labelled figures | Reading the test as the plan written before launch says (its window, the visits it counts, its decision rules) rather than by the dashboard's pooled headline | 15 (12) |
| [Funnel drop-off](../eval_runner/tasks/funnel-dropoff.json) | A diagnosis of a checkout conversion drop: each segment's step rates and verdict, a ruling on each suspected cause, and store figures | Following the analysts' rules on four weeks of daily funnel data by device, browser and step, beside a release log and a list of suspected causes | 14 (12) |
| [Test plan sizing](../eval_runner/tasks/test-plan-sizing.json) | A calendar for a backlog of 150 A/B tests (each test's traffic, sample size, weeks, start week and status) and a note for the growth lead | Applying the experimentation rules and each storefront's settings to every test, then fitting what runs into a four-week calendar | 10 (8) |

### Analytics and measurement

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [Ad performance analysis](../eval_runner/tasks/ad-performance-analysis.json) | A founder-ready analysis of four weeks of Meta campaign data | Correct arithmetic over gaps in the data, the trend that matters, and a bounded next test | 10 (0) |
| [Quarterly paid-media review](../eval_runner/tasks/ads-ledger-analysis.json) | A CMO-ready review of a raw daily ads export, with five labelled figures | Computing refund-adjusted figures exactly from the rows by the given definitions; a figure presented as computed that the data cannot give fails on the oracle's evidence | 12 (6) |
| [Attribution sensitivity](../eval_runner/tasks/attribution-sensitivity.json) | First-touch and last-touch revenue and ROAS by channel, and a budget recommendation | Removing duplicate orders, keeping refunds, and separating conclusions that hold under both models from those that depend on the choice | 10 (0) |
| [Tracking audit](../eval_runner/tasks/tracking-audit.json) | A prioritised defect list across campaign links, GTM and GA4 tags and consent settings, and what was checked and found clean | Finding every real defect against the documented standards without flagging items that conform | 20 (0) |
| [Shopify to Meta tracking](../eval_runner/tasks/shopify-meta-capi.json) | An implementation guide for Pixel and Conversions API tracking from Shopify to Meta | Correct deduplication, stable retry data, careful handling of customer data, and end-to-end validation | 11 (0) |

### Strategy and planning

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [90-day marketing plan](../eval_runner/tasks/marketing-plan.json) | A 90-day plan for a B2B SaaS with three channels and a $15,000 budget | Sequencing the plan and measuring activation by the documented event, without inventing customers or figures | 8 (0) |
| [Budget reconciliation](../eval_runner/tasks/budget-reconciliation-trap.json) | A Q4 allocation in reply to a CMO's budget brief | Checking whether the brief's commitments can all be honoured at once, saying so with exact numbers if not, and offering complete revised allocations | 8 (0) |
| [Launch timeline](../eval_runner/tasks/launch-timeline.json) | The start, finish and slack of each of 96 launch tasks, the launch date, the critical path, whether the promised date holds, and the smallest cut that makes it | Scheduling exactly by the brief's rules with every person's own calendar: offices, working days, time off and outside suppliers | 12 (11) |
| [Policy casebook](../eval_runner/tasks/policy-casebook.json) | A ruling on each of 40 proposed marketing actions, with the one clause that decides it | Judgement across a long policy with no sums: definitions, exceptions, dated changes, and the policy's own procedure for choosing the deciding clause | 10 (10) |
| [Brief, then the client's amendment](../eval_runner/tasks/brief-amendment.json) | The final launch plan, email schedule and ad sheet for three markets after the client amends a signed-off brief, with a note on what changed | Applying each change everywhere it reaches and nothing else, including effects the amendment does not spell out; the signed-off brief arrives as an earlier message in the same conversation | 17 (16) |

## Held back: the holdout split

The four tasks of the holdout split are kept off the board and out of tuning.
They are not untouched: the agent-setup runs of 2026-11-16 graded them and
their results were read. So a `--split holdout` result is a result on tasks
whose answers have been seen.

| Task | What is produced | What makes it hard | Checks (by program) |
|---|---|---|---:|
| [Launch capacity](../eval_runner/tasks/launch-capacity-trap.json) | A reply to an over-committed four-week launch production schedule | Checking every commitment against the team's capacity and dates before agreeing to any of it | 9 (0) |
| [Platform limits](../eval_runner/tasks/platform-limits-gauntlet.json) | One promotion in eleven labelled fields across Google, Meta, LinkedIn and SMS | Hard character limits and exact required strings, checked by program | 10 (6) |
| [Rate-card reconciliation](../eval_runner/tasks/rate-card-reconciliation.json) | An invoice audit against a signed agreement, a rate card and a delivery log | Choosing the right rate from several candidates and quantifying the billing errors without disputing what is correct | 10 (0) |
| [Unsupportable claims](../eval_runner/tasks/unsupportable-claims-brief.json) | A landing section and a promotional email that deliver a franchise brief without its unsupportable claims | Declining what the facts cannot support, openly, without inventing support or silently dropping it | 10 (3) |

## Left out

These ten tasks stay in the repository and run by id (`--tasks <id>`), but
are not on the board. The reasons are those `eval_runner/board.json` records.

| Task | Why it is not on the board |
|---|---|
| [Which headline won?](../eval_runner/tasks/headline-forecast.json) | A forecast of real tests. It cannot be scored like the rest until the results are known, so it belongs to a forecast track of its own. |
| [Which headline won? Never published](../eval_runner/tasks/headline-forecast-unpublished.json) | The same. |
| [Catalog descriptions](../eval_runner/tasks/catalog-descriptions.json) | Fully right on every recorded attempt (GPT-6.2 Sol three times with and without skills, Gemini 4 Neon, Claude Opus 5.5), 2026-11-21: it separates nobody. |
| [Competitor comparison](../eval_runner/tasks/competitor-comparison.json) | The same, 2026-11-21. |
| [Factorial ad test](../eval_runner/tasks/factorial-ad-test.json) | Fully right in all nine cells of the first-attempt pilot (three models, three setups), 2026-11-20: it separates nobody. |
| [Lifecycle programme](../eval_runner/tasks/lifecycle-program.json) | The same, 2026-11-20. |
| [Monthly report](../eval_runner/tasks/monthly-report-reconcile.json) | Fully right in eight of the nine cells of that pilot; three harder analytics tasks cover the same ground. |
| [Analytics source conflict](../eval_runner/tasks/analytics-source-conflict.json) | Fully right in seven of the nine cells of that pilot; attribution sensitivity and the tracking audit cover source conflicts harder. |
| [Quarterly paid-media review, decoy file](../eval_runner/tasks/ads-ledger-analysis-decoy.json) | A variant of the quarterly paid-media review that only two harnesses can deliver, so not every setup shares it; the plain version is on the board. |
| [Launch build as a chain](../eval_runner/tasks/launch-workflow-chain.json) | A third launch build of its kind: the trafficking sheet and the search account build are on the board, and each area holds five. |

## How some tasks are built

### Tasks that return files

Most of the tasks added in November 2026 ask for one or more small CSV files
inside the reply, under fixed headers, often with a labelled answer block at
the end. A program reads every row and figure and compares it with a
reference computed from the task's own files, by code in
`eval_runner/task_facts_*.py` or `eval_runner/workflows/`, and the tests in
`tests/test_tasks_*.py` and `tests/test_workflow_*.py` check those
references. What a program cannot see is left to the judge: one or two
checks on most of these tasks, none on some. A count can be banded, so a near
miss earns part of the checklist score, but the task is right only when every
check passes.

For the tasks built by `eval_runner/workflows/`, every count measures the
work against the reference, so a file left out is that many errors, never
zero. The files the model reads are generated by the same module that grades
them, so the standard the model reads and the rules the checker applies are
the same constants (`python3 scripts/gen_workflow_tasks.py --check` confirms
the files match).

### Tasks with an earlier message

A task with a `decoy` block sends a message one turn before the request. On
the board this is the client-amendment task: the signed-off brief comes
first, the amendment second. The direct setups send it as one conversation of
two calls, and the Magister setup as an earlier chat turn in the same
session. Claude Code takes a single prompt, so these tasks list the
harnesses that can run them (`harnesses` in the task file). The earlier
turn's cost and time are counted with the task's.

### Forecast tasks

The two "Which headline won?" tasks grade a judgement against what happened,
not work against a brief. Each pair is two headlines from one real test on
Upworthy's site, from the Upworthy Research Archive (Matias, Munger, Le Quere
and Ebersole, 2021; CC BY 4.0). `eval_runner/fixtures/headline-forecast/NOTICE.md`
has the source, the licence and how the pairs were chosen. The archive is
public, so a model may have seen it; the second task holds only headlines the
publisher did not go on to use. A forecast task carries `"forecast": true`,
which keeps it out of a report's false-confidence figure.

## Known limits

- An answer block reads a full stop as the decimal point, so a figure
  written with a full stop as the thousands separator (`12.480`) is read as
  12.48. Most prompts that allow separators say to use a comma. Three board
  prompts say only that thousands separators are fine: the search terms
  review, the re-engagement programme and the technical SEO triage (and,
  off the board, the monthly report). Their next prompt versions should say
  "a comma as thousands separator".

## How tasks stay comparable

Every task records a prompt version and a rubric version. A run saves a
snapshot of the exact task, prompt and source material it used, so a later
wording change cannot quietly rewrite the evidence of an older run.

For the full file format and versioning rules, see the
[direct-model runner reference](../eval_runner/README.md).
