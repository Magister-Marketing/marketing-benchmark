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
| [SEO blog post](../eval_runner/tasks/blog-post.json) | A useful long-form article about furnace noises, with an SEO title and meta description, from a dated sources file and a site map | Using only current figures when the price in the older source, listed last, has been superseded; linking exactly the five pages a written rule picks from the site map (live, tagged furnace, most sessions, a tie broken by URL) with each page's keyword as the link text; and keeping safety and emergency advice responsible. Prompt 3, rubric 4 (hardened 2026-11-20: every direct setup passed all nine checks of rubric 3); 10 of the 13 checks are a program's | 13 |
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
| [Content brief](../eval_runner/tasks/seo-content-brief.json) | A content brief for one new article, from a 149-keyword export, the site's pages and competitor outlines for three candidate topics, opening with six labeled lines (topic, primary and secondary keywords, title, meta description, internal links) and closing with six labeled figures | Computing winnable clicks from a click-through table for every eligible keyword, with those the site already wins removed: the topic with the most searches, the most eligible searches, and the most clicks when the clicks a ranking keyword already gets are left in is a different one, and the target topic's biggest keyword ranks fifth, so it is not the primary. Prompt 4, rubric 5 (hardened 2026-11-20: every setup passed all 15 checks of rubric 4); 12 of the 16 checks are a program's | 16 |
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

SEO tasks added on 2026-11-20 for the 35-task board. A program checks every row and figure against an oracle
that reads only the fixtures (`eval_runner/task_facts_seo.py`), and the tests compute each one again with
separate code. No model has been run on them yet:

| Task | What the model must produce | What makes it challenging | Checks |
|---|---|---|---:|
| [Redirect map](../eval_runner/tasks/seo-redirect-map.json) | A redirect file for a shop moving platform, from a 327-URL crawl of the old site, the new site's URL list and ten migration rules in order, with four labeled counts | Applying the first rule that fits to every URL: products matched by SKU when a successor took a retired product's slug, colour pages the new site folds into one product page, old redirects and the new site's own redirects followed to a live page, parameter URLs and unchanged pages left out, a date stripped only when it is a date, and retired products with no signal at all gone instead of redirected | 15 |
| [Titles and meta descriptions](../eval_runner/tasks/seo-titles-meta.json) | A title and a meta description for each of the 41 indexed pages of a 46-page inventory, with three labeled counts | Hard length limits, a suffix per page type, the exact keyword in each, prices only on in-stock products, a product's attribute and a category's count, and pages that share a keyword: the one with the most clicks keeps it (ties by page type, then id), the rest switch to their secondary keyword and may not use the one they gave up, while a noindex page takes no part and a singular is not a plural | 16 |

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
