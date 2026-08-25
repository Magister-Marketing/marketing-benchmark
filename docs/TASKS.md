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
| [SEO blog post](../eval_runner/tasks/blog-post.json) | A useful long-form article about furnace noises | Meeting search intent while keeping safety and emergency advice responsible | 9 |
| [Meta ad concepts](../eval_runner/tasks/ad-creatives.json) | Three feed-ad concepts with a fixed call to action | Making the concepts genuinely different and testable without inventing proof | 9 |
| [Ad performance analysis](../eval_runner/tasks/ad-performance-analysis.json) | A founder-ready analysis of four weeks of campaign data | Correct arithmetic, missing data, trends, and a bounded next test | 10 |
| [90-day marketing plan](../eval_runner/tasks/marketing-plan.json) | A focused B2B SaaS plan with three channels and a $15,000 budget | Sequencing the plan and measuring only fully observed activation cohorts | 8 |
| [Landing page](../eval_runner/tasks/landing-page.json) | A complete single-file HTML landing page | Exact visitor flow, careful claims, one action, and valid page structure | 10 |
| [Shopify to Meta tracking](../eval_runner/tasks/shopify-meta-capi.json) | A practical Pixel and Conversions API implementation guide | Correct deduplication, stable retry data, privacy, and end-to-end validation | 11 |
| [Email-flow repair](../eval_runner/tasks/email-flow-repair.json) | A corrected four-email onboarding sequence | Finding every planted defect with no defect categories named in the prompt | 14 |
| [Budget reconciliation trap](../eval_runner/tasks/budget-reconciliation-trap.json) | A Q4 allocation response to an infeasible brief | Catching that the commitments exceed the cap and saying so with exact numbers | 8 |
| [Analytics source conflict](../eval_runner/tasks/analytics-source-conflict.json) | A reconciliation of contradictory Meta and GA4 reports | Computing both sources' truths without inventing a single reconciled number or undocumented causes | 9 |

## Holdout tasks

These are the final-exam set. Their purpose is to show whether a benchmark
improvement also works on assignments that were not used to tune it. Once a
holdout answer is inspected, that task should be moved into development and
replaced before another untouched-result claim.

The August 25, 2026 runs inspected both earlier holdout batches, so all seven
of those tasks now sit in the development table above. This batch is built on
what those runs taught: detection tasks whose authoritative facts sit in the
prompt saturate quickly, while infeasibility traps and dense interacting
constraints discriminate. The current untouched set:

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
