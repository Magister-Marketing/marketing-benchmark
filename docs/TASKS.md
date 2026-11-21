# Tasks

[Back to the overview](../README.md) · [How scoring works](SCORING.md) ·
[See scored examples](SCORED_EXAMPLES.md)

A task is a realistic marketing assignment with its own source material and
pass/fail checklist. Every model in a comparison receives the same task
package.

- **The assignment** says what to produce.
- **The source material** supplies the facts the model may use.
- **The skill guidance** is the relevant verbatim SKILL.md from
  [marketingskills](https://github.com/coreyhaines31/marketingskills), Corey
  Haines's open skill pack that ships on every Magister agent machine
  (provenance: `evals/fixtures/public/skills/README.md`).
- **The checklist** defines every requirement the answer must pass.

The task files linked below are the source of truth.

## Development tasks

These are the practice and calibration set. We can inspect their answers and
use what we learn to make unclear requirements clearer. Because we have seen
the results, these tasks are useful for development—not as a claim about
performance on an untouched test.

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Hero headlines](../eval_runner/tasks/headline.json) | Five grounded launch headlines with distinct angles and rationales | Staying punchy while using only supported product facts | 6 |
| [Conflicting brief repair](../eval_runner/tasks/source-conflict-repair.json) | A 12-item conflict audit and one corrected Meta concept | Separating atomic claims and following the authoritative sources | 18 |
| [Attribution sensitivity](../eval_runner/tasks/attribution-sensitivity.json) | First-touch and last-touch revenue comparisons | Deduplicating orders, retaining refunds, and separating robust from model-dependent conclusions | 10 |
| [Factorial ad test](../eval_runner/tasks/factorial-ad-test.json) | A four-cell 2×2 creative experiment | Holding variables constant while obeying exact budget, stop, win, and inconclusive rules | 13 |
| [Landing-page repair](../eval_runner/tasks/landing-page-repair.json) | A corrected single-file HTML page | Removing planted factual, safety, proof, action, and structural defects | 19 |
| [SEO blog post](../eval_runner/tasks/blog-post.json) | A useful long-form article about furnace noises, with an SEO title and meta description, from a dated sources file and a site map | Using only current figures when a later source has replaced four (the price, a filter interval, and an interim call summary's count and shares, each listed after the source that replaces it); linking exactly the eight pages a written rule picks from a 139-page site map (live, tagged furnace, most sessions, a tie broken by URL, with redirects, noindex pages, a dead page and pages tagged otherwise above the cutoff) with each page's keyword as the link text; and keeping safety and emergency advice responsible. Prompt 3, rubric 4 (hardened 2026-11-20: every direct setup passed all nine checks of rubric 3); 11 of the 14 checks are a program's | 14 |
| [Meta ad concepts](../eval_runner/tasks/ad-creatives.json) | Three feed-ad concepts with a fixed call to action | Making the concepts genuinely different and testable without inventing proof | 9 |
| [Ad performance analysis](../eval_runner/tasks/ad-performance-analysis.json) | A founder-ready analysis of four weeks of campaign data | Correct arithmetic, missing data, trends, and a bounded next test | 10 |
| [90-day marketing plan](../eval_runner/tasks/marketing-plan.json) | A focused B2B SaaS plan with three channels and a $15,000 budget | Sequencing the plan and measuring only fully observed activation cohorts | 8 |
| [Landing page](../eval_runner/tasks/landing-page.json) | A complete single-file HTML landing page | Exact visitor flow, careful claims, one action, and valid page structure | 10 |
| [Shopify to Meta tracking](../eval_runner/tasks/shopify-meta-capi.json) | A practical Pixel and Conversions API implementation guide | Correct deduplication, stable retry data, privacy, and end-to-end validation | 11 |
| [Email-flow repair](../eval_runner/tasks/email-flow-repair.json) | A corrected four-email onboarding sequence | Finding every planted defect with no defect categories named in the prompt | 14 |
| [Budget reconciliation trap](../eval_runner/tasks/budget-reconciliation-trap.json) | A Q4 allocation response to an infeasible brief | Catching that the commitments exceed the cap and saying so with exact numbers | 8 |
| [Analytics source conflict](../eval_runner/tasks/analytics-source-conflict.json) | A reconciliation of contradictory Meta and GA4 reports | Computing both sources' truths without inventing a single reconciled number or undocumented causes | 9 |
| [Quarterly paid-media review](../eval_runner/tasks/ads-ledger-analysis.json) | A CMO-ready review of a 784-row daily ads export with five labeled figures | Computing refund-adjusted CPA, wasted spend, and ROAS exactly; `no_invented_data` is backed by the oracle, so estimated figures score 0 | 12 |
| [Quarterly paid-media review, decoy file](../eval_runner/tasks/ads-ledger-analysis-decoy.json) | The same review, after a look-alike "preliminary" export with the same name, shape, and dates but different numbers was shared one turn earlier for reference | Computing from the file this request supplied, not the one already sitting in the workspace; every figure from the wrong file is outside the zero-credit band, so the oracle scores it 0. Runs wherever a prior turn can be sent: the direct setups (the look-alike message, the model's reply, then the request, as one conversation of two calls) and Magister; not Claude Code | 13 |
| [Tracking audit](../eval_runner/tasks/tracking-audit.json) | A prioritized defect list across UTM links, GTM/GA4 tags, and consent defaults | Finding all twelve planted defects (Performance Max counts separately from search) without flagging the conforming decoys | 18 |

Added on 2026-11-17 (the first draft was run once and discarded; the judged checks of these versions are not calibrated yet):

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Technical SEO triage](../eval_runner/tasks/seo-technical-triage.json) | A prioritised fix list from a 165-URL site crawl, with six labeled figures | Counting five issue types exactly while leaving correctly configured look-alikes (canonicalised filter pages, noindex cart and search pages, one-hop redirects) unflagged, and ordering the issue types by the traffic of the pages each affects | 14 |
| [Search terms review](../eval_runner/tasks/search-terms-negatives.json) | Negative keywords by theme, terms to keep, and terms to promote, from a month of search terms | Blocking what the business does not sell without blocking its own brand name, two converting terms, or product searches with too few clicks to judge | 12 |
| [A/B test readout](../eval_runner/tasks/ab-test-readout.json) | A readout and recommendation for a pricing-page test, with seven labeled figures | Seeing that the test was read early and that the visitor split is not the planned 50/50, and not shipping on a secondary metric | 17 |
| [Content brief](../eval_runner/tasks/seo-content-brief.json) | A content brief for one new article, from a 455-keyword export, the site's pages and competitor outlines for three candidate topics, opening with six labeled lines (topic, primary and secondary keywords, title, meta description, internal links) and closing with six labeled figures | Computing winnable clicks from a click-through table for every eligible keyword, with those the site already wins removed: the topic with the most searches, the most eligible searches, and the most clicks when the clicks a ranking keyword already gets are left in is a different one, and the target topic's biggest keyword ranks fifth, so it is not the primary. Prompt 4, rubric 5 (hardened 2026-11-20: every setup passed all 15 checks of rubric 4); 12 of the 16 checks are a program's | 16 |
| [A/B test readout](../eval_runner/tasks/ab-test-readout.json) | A readout and decision for a pricing-page test from 616 daily rows by device and traffic source and a plan with written decision rules, with eleven labeled figures (hardened on 2026-11-20) | The dashboard's pooled lift is up while variant B is down on both devices, because the plan split mobile 70/30; the first week's lift fades and the plan leaves that week out of every figure; QA visits forced into variant B must come out; the 70/30 split is not a mismatch, and the billing-ticket guardrail is breached only over the window the plan reads | 15 |
| [Content brief](../eval_runner/tasks/seo-content-brief.json) | A content brief for one new article, from a keyword export, the site's pages and competitor outlines for three candidate topics | Picking the topic the numbers support when the highest-volume keyword has buying intent and already ranks on another page | 15 |
| [Re-engagement programme](../eval_runner/tasks/lifecycle-reengagement.json) | An audience with counts, segments and a three-email flow, from a 260-row subscriber export and an email policy | Leaving out everyone without consent, including past buyers, and following the policy's offer, cadence and sunset rules | 15 |
| [Monthly report](../eval_runner/tasks/monthly-report-reconcile.json) | A founder-ready report with six labeled figures, from ad, analytics and order exports that disagree | Reconciling double-fired events, refunds, test orders and platform over-claiming into one set of real results | 15 |
| [Search account build](../eval_runner/tasks/search-account-build.json) | Five files for a new Google Ads account: keywords by campaign and ad group, exclusions with reasons, negatives, daily budgets and one ad per ad group, from a 208-keyword export and an account standard | Applying seven steps of rules to every keyword without one slip: the first matching rule wins, an exclusion beats the brand name, budgets are scaled to a cap and then floored, and each ad has limits, required words and banned ones | 19 |
| [Lifecycle programme](../eval_runner/tasks/lifecycle-program.json) | Five files for a tea club's lifecycle email programme, from a 300-customer export and a written policy: who is suppressed and why, everyone else's segment, the holdout, 24 emails with days, subjects, preheaders and offer codes, and the local send time of every step in every timezone | Rules that interact across 300 people (the first suppression reason that applies, the first segment that fits, a holdout by id, a cap for gift plans), send times that move out of quiet hours, and two dozen short pieces of copy with a required phrase each, hard limits and no repeats, all agreeing with each other | 20 |
| [Launch brief to trafficking sheet](../eval_runner/tasks/launch-trafficking.json) | Three files for a product launch to three audiences on Meta, Google Search, LinkedIn and email: a budget by channel and week, 114 text fields across 36 assets, and a tracked final URL for each asset | Many short pieces of copy under hard, differing character limits, each with strings it must and must not carry, written for its own audience and never reused across audiences; a budget with a rounding rule and a weekly minimum; URLs built exactly to a tracking standard, with one landing page not live | 19 |
| [Cold outbound sequences](../eval_runner/tasks/outbound-sequence.json) | Three files for a B2B cold outbound programme, from a 200-lead list, a written standard and a facts sheet: who is excluded and why, everyone else's segment and country group, and 30 emails across 10 sequences with send days, subjects and bodies | Seven exclusion reasons and four segments decided in order over 200 leads, country rules that change which steps are sent and which exact sentence an email must carry, 30 emails under a subject limit and a word limit with a required footer, forbidden phrases and no repeated subject, merge fields that are allowed only where every lead in the sequence has a value, and no figure that is not in the facts | 22 |
| [Price change rollout](../eval_runner/tasks/price-change-rollout.json) | All 14 customer-facing assets of a subscription product returned after a price change, a plan rename and a longer trial: pricing page, FAQ, emails, six ads, a one-pager, a help article and a banner, with a change log | Changing everything the brief changes and nothing else: prices however the old copy wrote them, savings that must be worked out again, a plan name that is also an ordinary word and part of a feature's name, a number that equals an old price and is not one, an ad already at its character limit, one sentence that keeps the old price, and three assets that must come back character for character | 19 |
| [Which headline won?](../eval_runner/tasks/headline-forecast.json) | A pick and a confidence for each of 100 pairs of headlines from real tests, where one beat the other by a wide margin | Telling which headline people really clicked more, and knowing how sure to be: a coin flip scores nothing, nine right in ten passes | 4 |
| [Which headline won? Never published](../eval_runner/tasks/headline-forecast-unpublished.json) | The same for 100 pairs of headlines the publisher did not go on to use | The same, where no headline can be recognised from having spread on the web | 4 |

The three tasks from Content brief down were drafted as holdout tasks. Their
recorded answers have been read and one rubric was changed because of what
they showed, so by the rule under "Holdout tasks" they are development
tasks, and no held-out result is claimed from them. In these six tasks every
figure a program checks is recomputed by separate code in the tests; the
checks a judge makes are not calibrated yet.

Known limits of those six tasks:

- To fix in their next prompt version: an answer written with a full stop as
  the thousands separator (`12.480`) is read as 12.48, because a full stop is
  always the decimal point. The prompts say thousands separators are fine
  without saying which; they should say "a comma as thousands separator".
  The content brief's prompt 4 says "Write thousands with a comma".
- To fix in the next rubric version of the A/B test readout: the critical
  criterion says a readout may state the expected count per variant under the
  planned 50/50 split (11,750). That a readout fails when it gives that count
  as the sample size the plan required of each variant (18,000) is said only
  in the judge's reference, not in the criterion's own text.
  The A/B test readout's version 4 says so.

Conversion tasks added on 2026-11-20 for the 35-task board. No setup has run
them yet and their judged checks are not calibrated. Every figure a program
checks is recomputed from the fixtures by separate code in
`tests/test_tasks_conversion.py`. The A/B test readout above was hardened the
same day (prompt version 4, rubric version 5), with its tests in the same file.

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Test plan sizing](../eval_runner/tasks/test-plan-sizing.json) | A 150-row calendar file for a backlog of A/B tests across twelve storefronts: each test's page weekly users, sample size, weeks, start week and status, every row checked by program, and a note for the growth lead | Traps spread through the backlog: storefronts that count sessions at their own users per session, outage weeks to leave out of a page's mean, lifts in percentage points, tests on half their page's traffic, and weeks that round up; then one priority order over every storefront, each with its own freeze week and limit on tests at once, decides which of the tests that fit in four weeks get a slot | 10 |
| [Funnel drop-off](../eval_runner/tasks/funnel-dropoff.json) | A diagnosis of a checkout drop from a 1,131-row daily funnel export over ten segments, a release log and ten suspected causes: what broke, where and since when, the conversion rate before and after, the orders and revenue lost, and which causes the data rules out, with 17 labeled figures | Halving two double-firings the release log records (one of them on the last three days, where left doubled it fakes two more breaks) and leaving out a crawler before any rate; finding the one segment and step that broke by a written normal-range rule, past dips that stay inside their range, a day and a four-day run below it that recover, and a change made two days before the break | 16 |

Strategy tasks added on 2026-11-20 for the 35-task board (not run yet; the judged checks are not calibrated). Every figure a program checks is computed from the fixtures by `eval_runner/task_facts_strategy.py` and recomputed by separate code in `tests/test_tasks_strategy.py`:

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Channel budget allocation](../eval_runner/tasks/channel-budget-allocation.json) | A quarterly budget split across six channels in whole $5,000 blocks, from diminishing-returns forecasts and channel terms: blocks, spend, fee and leads per channel, which of ten named constraints bind, and five labeled figures | Finding the one best split when the rules interact: the account executives can take only 520 leads from two of the channels, one channel's fee is monthly and held all quarter, one has a 4-block minimum order and one a contracted commitment. Buying the best blocks as if the AEs could take every lead projects 85 more leads and breaks the cap, and scores zero on every check it touches | 14 |
| [Competitor comparison](../eval_runner/tasks/competitor-comparison.json) | A 72-cell table of 12 attributes for us and five competitors, read from six saved pricing pages under a brief's rules, and a verdict on five draft claims about us | Every cell is the value its page states or exactly `not stated`: monthly prices beside lower annual ones, annual-only plans put on a monthly basis, single sign-on listed in an introduction but sold on a higher plan only, three FAQs that contradict their plan tables (the FAQ wins), a price withheld behind "Contact sales" and a gap that is not a no. Each trap costs its own check and the one claim it decides | 14 |
| [Launch timeline](../eval_runner/tasks/launch-timeline.json) | The start and finish of each of 24 launch tasks under written scheduling rules, the launch date, the critical path, the slack of three tasks, whether the promised date holds, and the smallest set of optional tasks to cut to make it | Owners do one task at a time in ID order, so the critical path runs through the designer's queue, not the dependencies; two outside start dates and three holidays move the dates. A dependency-only critical path says the date holds (9 April against 16) and scores zero on every check it touches; the longest task and the longest optional task both have slack, and the first useful cut alone falls a day short | 14 |
SEO tasks added on 2026-11-20 for the 35-task board. A program checks every row and figure against an oracle
that reads only the fixtures (`eval_runner/task_facts_seo.py`), and the tests compute each one again with
separate code. No model has been run on them yet:

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Redirect map](../eval_runner/tasks/seo-redirect-map.json) | A redirect file for a shop moving platform, from a 327-URL crawl of the old site, the new site's URL list and ten migration rules in order, with four labeled counts | Applying the first rule that fits to every URL: products matched by SKU when a successor took a retired product's slug, colour pages the new site folds into one product page, old redirects and the new site's own redirects followed to a live page, parameter URLs and unchanged pages left out, a date stripped only when it is a date, and retired products with no signal at all gone instead of redirected | 15 |
| [Titles and meta descriptions](../eval_runner/tasks/seo-titles-meta.json) | A title and a meta description for each of the 99 indexed pages of a 113-page inventory, with three labeled counts | Hard length limits, a suffix per page type, the exact keyword in each, prices only on in-stock products, a product's attribute and a category's count, and pages that share a keyword: the one with the most clicks keeps it (ties by page type, then id), the rest switch to their secondary keyword and may not use the one they gave up; size variants share a keyword, three pages tie, four noindex pages out-click the page that keeps it and take no part, and a singular is not a plural | 16 |

Email tasks added on 2026-11-20 for the 35-task board (not run yet; the one judged check of each is not calibrated):

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Email send calendar](../eval_runner/tasks/email-send-calendar.json) | February's calendar for 12 campaigns to six overlapping segments of an 800-subscriber list: each campaign's send date (or none), audience size and the reason it moved; every subscriber's email count for the month; five labeled figures | A per-subscriber cap of 3 emails in any 7 consecutive days, applied in priority order and counting campaigns already placed on later dates, together with blackout dates, send days by type, a teaser gap that moves a launch, and deadlines; audiences that depend on the send date, because subscribers join during the month and pauses end on given days (and some pauses ended in January); collisions that exist only for people in two segments, one campaign that cannot go out, and unsubscribed people whose segment overlaps would move campaigns if they were counted. Every one of the 800 subscriber rows is checked | 13 |
| [Email compliance audit](../eval_runner/tasks/email-compliance-audit.json) | A verdict for each of the 150 live emails before a platform move (pass, or the codes of the sending policy it breaks), a fix for each code, and three labeled counts, from the policy, a consent table of 17 audiences and the DNS records of seven sending domains | 116 violations under six codes across 87 emails, and look-alikes in every rule: DMARC `p=none` beside `sp=quarantine`, a revoked key at the required selector with a live one at another, a second SPF record, the brand's own root domain, against `~all`, `pct=25`, `sp=none` and an empty key at an unused selector that all pass; a registered PO box and a `·`-separated address against a wrong suite, ZIP or street; tags without spaces or for preferences against `{{ unsubscribe_url }}` and capital letters; "up to" the highest discount, "sitewide" with no exclusions and a stated shipping minimum; a review request, a promotion followed by a support block; an unconfirmed EU audience listed second, a Canadian audience at exactly 24 months. Every one of the 150 rows is checked | 13 |

Experimental tasks added on 2026-11-20 for the 35-task board, each built to isolate one way of being hard so the ways can be compared (not run yet; the judged checks are not calibrated). Every figure a program checks is computed from the fixtures by `eval_runner/task_facts_experiments.py` and recomputed by separate code in `tests/test_tasks_experiments.py`:

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Launch build as a chain](../eval_runner/tasks/launch-workflow-chain.json) | Six dependent deliverables for a paid social launch: the audience segments six written rules choose, 8 campaigns and 30 ad groups named by a convention, one ad per ad group, a tracked URL per ad group, daily budgets by segment size, and a pre-launch count of what was built | Consistency along the chain, not the size of any one step: every later file is checked against the reply's own earlier files, so one ad group name, campaign name, product or count that drifts between files fails that file's agreement check even when each file is right on its own. The rules choose a partner duplicate over a smaller first-party one, keep the UK store at `gb`, put the returning-visitor code on retargeting ads only and allow no figure outside the ad's own product row | 14 |
| [Brief, then the client's amendment](../eval_runner/tasks/brief-amendment.json) | The final launch plan, email schedule and ad sheet for three markets after the client amends a signed-off brief, with a note on what changed. The brief and its product sheet arrive one turn earlier, "for reference, the request follows"; the amendment is the request | Applying six changes everywhere they reach and leaving everything else as signed off. Three knock-ons the amendment never mentions: the withdrawn kettle takes the bundle it belongs to with it, which changes the product every launch email features (and in the US only the price rise makes it the coffee machine); the new launch date puts the UK teaser on a UK holiday. One change looks like it applies and does not: a UK price that starts after launch. The plan built from the brief alone scores zero on every check the amendment touches, and the amendment applied literally scores zero on the four knock-ons. Runs where a prior turn can be sent: the direct setups and Magister, not Claude Code | 17 |

### Forecast tasks

The two "Which headline won?" tasks grade a judgment against what happened,
not work against a brief. Each pair is two headlines from one real test on
Upworthy's site, with the same story, image and excerpt and visitors assigned
at random, where the click rates differed at p < 0.001. A program counts the
picks that match the record and scores the stated confidence; the one judged
check is that the reply did not claim to look the tests up. Both bars are one
reference forecaster, right nine times in ten and saying 90, with credit in a
straight line up from a coin flip with no opinion. Count one model's result on
a set as good to about four points either way: that is what 100 pairs give.
The pairs come
from the Upworthy Research Archive (Matias, Munger, Le Quere and Ebersole,
2021; CC BY 4.0): `eval_runner/fixtures/headline-forecast/NOTICE.md` has the
source, the licence and how the pairs were chosen. The archive is public, so
a model may have seen it; the second task holds only headlines that were not
the ones published. A forecast task carries `"forecast": true`, which keeps
it out of a report's false-confidence figure: a reply with every pick made is
complete, and a pick that turned out wrong is a miss, not unfinished work.

### Workflow tasks

Search account build is the first workflow task. A workflow task hands over a
few files and asks for several deliverables that depend on each other, each
as a small CSV file inside the reply. Its checks are a program's, counted
against a reference the task's own module computes
(`eval_runner/workflows/`): how many keywords are in the wrong ad group, how
many budgets are off, how many headlines run over. One judged check is left
for what a program cannot see. A count is banded, so a near miss earns part of
the score, and the task is still passed only when every check is. Every count
measures work against the reference, so a file left out is that many errors,
never zero.

The files a workflow task supplies are generated by the module that grades
it (`python3 scripts/gen_workflow_tasks.py --check`): the standard the
candidate reads and the rules the checker applies are the same constants.

## Holdout tasks

These are the final-exam set. Their purpose is to show whether a benchmark
improvement also works on assignments that were not used to tune it. Once a
holdout answer is inspected, that task should be moved into development and
replaced before another untouched-result claim.

The August 25, 2026 runs inspected both earlier holdout batches, so all seven
of those tasks now sit in the development table above. The batch below was
built on what those runs taught: detection tasks whose authoritative facts
sit in the prompt saturate quickly, while infeasibility traps and dense
interacting constraints discriminate.

These four are not untouched: the 2026-11-16 runs graded them and their
results were read. They remain the holdout split for now, so a
`--split holdout` result is a result on tasks whose answers have been seen.
The holdout split:

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Launch capacity trap](../eval_runner/tasks/launch-capacity-trap.json) | A four-week production schedule response to an over-committed launch brief | Spotting that designer hours are infeasible while copywriter hours fit, plus an independent freeze-date conflict | 9 |
| [Platform limits gauntlet](../eval_runner/tasks/platform-limits-gauntlet.json) | One coordinated promotion in eleven labeled fields across Google, Meta, LinkedIn, and SMS | Hard character limits and exact required strings, enforced programmatically | 10 |
| [Rate-card reconciliation](../eval_runner/tasks/rate-card-reconciliation.json) | An invoice audit against a signed agreement, rate card, and delivery log | Choosing the one correct rate among four candidates and quantifying three planted billing errors without disputing the clean line | 10 |
| [Unsupportable claims brief](../eval_runner/tasks/unsupportable-claims-brief.json) | A landing section and promo email that fulfill a franchise brief minus its unsupportable claims | Declining exactly the four unsupported demands without fabricating them or silently dropping them | 10 |

## How tasks stay comparable

Every task records a prompt version and a rubric version. A run also saves a
snapshot of the exact task, prompt, and source material it used. That means a
later wording change cannot quietly rewrite the evidence from an older run.

For the full file format and versioning rules, see the
[direct-model runner reference](../eval_runner/README.md).
