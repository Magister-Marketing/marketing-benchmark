# Rubric v2 calibration on 105 recorded submissions

This is a post-hoc **development-split calibration**, not a new model run and
not untouched model-ranking evidence. Rubric v2 was written after inspecting
the rubric-v1 ceiling, then applied to the same 105 raw submissions from:

- [Luna xhigh versus max](20260819-luna-xhigh-vs-max.md) — 42 submissions.
- [Luna, Terra, and Sol at medium](20260820-luna-terra-sol-medium.md) — 63 submissions.

No candidate response was regenerated. The original rubric-v1 judgments and
published reports remain unchanged; labeled `rubric-v2` judgments/reports live
beside the ignored local run evidence. Exact structural constraints were moved
to programmatic checks, while semantic criteria remained binary Sonnet 5
judgments.

## Result

| Configuration | Rubric v1 | Rubric v2 | v2 criterion rate | Recorded generation cost | Mean latency |
|---|---:|---:|---:|---:|---:|
| gpt-5.6-luna-medium | 6/7 | **3/7** | 0.931 | $0.08 | 28.8s |
| gpt-5.6-terra-medium | 7/7 | **4/7** | 0.942 | $0.87 | 33.4s |
| gpt-5.6-sol-medium | 6/7 | **5/7** | 0.974 | $2.47 | 59.2s |
| gpt-5.6-luna-xhigh | 6/7 | **5/7** | 0.968 | $0.33 | 104.4s |
| gpt-5.6-luna-max | 6/7 | **5/7** | 0.968 | $0.63 | 198.4s |

The medium-effort configurations now order monotonically on both pass³ task
score and pooled criterion rate. Luna xhigh and max remain quality-identical,
while max still costs about twice as much and takes about twice as long. That
is the useful shape the old 6/7–7/7 ceiling could not reveal.

## What failed

Across 105 normally finished submissions, rubric v2 produced 41 failed binary
criteria:

| Criterion | Failures | Reproducible boundary |
|---|---:|---|
| `hypothesis_prediction` | 15 | Every concept needs an observable KPI and expected direction; “resonate” or “drive interest” alone fails. |
| `partial_metric_denominators` | 8 | Launch Teaser cannot divide four weeks of spend by only three known weeks of outcomes. |
| `canonical_product_name` | 6 | `Arc` and `Arc Lamp` are not the supplied product name `Arc Clip Lamp`. |
| `bounded_test_decision` | 6 | A bounded test needs a control, one variable, cap, KPI, numeric win rule, and numeric sample or explicit inconclusive rule. |
| `event_time_stable` | 3 | Purchase code cannot use wall-clock send/retry time in place of the order occurrence time. |
| `mature_activation_denominator` | 1 | A 14-day activation rate excludes trial cohorts whose window has not closed. |
| `hypothesis_test_design` | 1 | A creative hypothesis omitted its comparator/control. |
| `event_id_retry_stability` | 1 | A new random suffix on retry defeats browser/server deduplication. |

The first draft of v2 also exposed one rubric defect: `blog-post` demanded
mechanical causes that its authoritative fixture did not supply. It was
replaced with a source-grounded noise/triage check, and only the 15 affected
blog judgments were rerun. All 15 passed. This is exactly why development
calibration must remain distinct from holdout evaluation.

After calibration, `ad-creatives`, `blog-post`, and `landing-page` advanced to
rubric v3 for checker-boundary fixes only: equivalent concept labels and HTML
H2s are accepted, while the HTML checker now rejects active content, embedded
assets, multiple root documents, and missing inline CSS. A read-only replay of
all 45 affected saved submissions produced zero pass/fail changes, so the v2
table above remains the historical calibration result rather than being
silently relabeled.

## Interpretation

- The separation comes from marketing-analysis and implementation correctness,
  not arbitrary length limits or a subjective 1–5 craft scale.
- `headline`, `blog-post`, and fresh-generation `landing-page` still saturate.
  Their ease is a real result; tougher behavior lives in the new holdout tasks.
- `ad-creatives` is an absolute quality gate today: none of the 15 responses
  made every hypothesis operational. It lowers all task scores equally but its
  criterion evidence is consistent rather than judge-boundary noise.
- `ad-performance-analysis` fails pass³ for every configuration, but its
  repetition pattern and criteria separate denominator errors from incomplete
  decision rules.
- These results remain judge-advisory: 0/105 verdicts have been independently
  human-verified, and judge token/cost accounting is not implemented yet.

## Holdout next step

Rubric v2 adds four tasks that were not used to choose these criteria:
contradictory-source repair, attribution sensitivity with a duplicate and
refund, a constraint-dense 2x2 ad experiment, and repair of a landing page with
planted factual/compliance/HTML defects. Run that holdout once, inspect it only
after the report is complete, then retire and replace the tasks before another
claim of held-out generalization.
