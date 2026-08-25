# Three-arm ablation: baseline vs tools-on vs no-skills, 14 tasks

Runs `20260825-054015-0f00cf6a` (baseline: skills on, tools off),
`20260825-061339-10bd059b` (tools on), `20260825-064613-c5112316` (no skills).
Each: 14 tasks (11 development + 3 fresh holdout) × luna/terra/sol medium × 3
attempts, pass³, judge claude-sonnet-5, second judge gpt-5.6-terra-medium.
378/378 candidate attempts and 378/378 primary judgments clean; zero provider
errors, zero judge failures. First runs with judge cost accounting and
cross-family agreement.

Live: https://marketingbenchmark.ai (baseline featured; ablation table on the
homepage).

## Scores

| Arm | Luna medium | Terra medium | Sol medium |
|---|---:|---:|---:|
| Baseline (skills, no tools) | 8/14 · $0.14 | **10/14** · $1.59 | 10/14 · $4.34 |
| Tools on (web search) | 7/14 · $0.18 | 9/14 · $1.95 | **12/14** · $6.41 |
| No skills | 6/14 · $0.13 | 7/14 · $1.45 | 8/14 · $4.13 |

## Skills vs no skills: worth +2 to +3 tasks for every model

Removing the skill guidance cost Luna 2 tasks, Terra 3, Sol 2. The collapse
concentrates: `budget-reconciliation-trap` went from 8/9 attempts passed
across models (baseline) to 3/9 without skills — the analytics guidance is
what licenses "tell the CMO the brief is infeasible" over papering it across;
without it models allocate anyway or recommend without grounding
(`grounded_recommendation` failed 8×, only in the skills-less and baseline
arms' margins). Terra also lost `marketing-plan` and `shopify-meta-capi`
without skills. The skill prompt is not decoration; it is the difference
between a compliant intern and a colleague who pushes back.

## Tools vs no tools: direction depends on the model

Same tasks, plus provider web search. Sol searched 25 times, Luna 8, Terra 9.

- **Sol converted search into wins**: +2 net (12/14, the best score recorded
  on this benchmark), flipping `ad-performance-analysis` and
  `factorial-ad-test` to pass.
- **Luna and Terra got worse**: −1 each. Both *lost*
  `attribution-sensitivity` — the oracle-math task — with search enabled
  (`last_touch_oracle`, `first_touch_oracle`, `model_definitions` failures
  appear only in the tools and no-skills arms). Luna also lost
  `landing-page` (`cta_count`). On fixture-grounded work, search appears to
  split smaller models' attention and degrade arithmetic care, while Sol
  treats it as a supplement.

## New holdout report card (first exposure, now inspected)

- `analytics-source-conflict`: **27/27 attempts passed in every arm** —
  saturated on arrival. The oracle divisions were too easy and the
  hallucination trap didn't tempt anyone. Retire or harden.
- `email-flow-repair`: 26/27, 27/27, 26/27 — near-saturated; unprompted
  defect detection is apparently easy when the facts sheet is in-prompt.
- `budget-reconciliation-trap`: the keeper. Skills-sensitive (see above),
  and the one task where Terra failed an attempt in baseline (`FPP`).

Two of three replacements saturated where the *previous* holdout round
discriminated sharply. Pattern worth recording: repair/reconciliation tasks
with the authoritative facts in-prompt are easier than generation or
constraint-compliance tasks. The next holdout batch should bias toward
infeasibility traps and constraint density, not detection.

## Run-to-run variance is real

On the 11 shared tasks, against yesterday's `20260825-040844-5ddf2d2c`:
Luna 4→5, Terra 5→8, Sol 8→7. Terra's +3 (factorial, headline, shopify all
F→P) shows task-level pass³ from 3 attempts is noisy at the margin;
single-run deltas of ±1 task should not be read as capability change. (A
minor confound: the judge prompt's criterion-line format changed in this PR;
rubric text was unchanged.) Cross-run claims need either more repetitions or
paired-run confirmation.

## Judge health (now measured, not assumed)

| Arm | Primary judge cost | Cross-family agreement |
|---|---:|---:|
| Baseline | $3.78 (126 calls) | 98.9% (1255/1269) |
| Tools | $3.92 | 98.2% (1246/1269) |
| No skills | $3.62 | 98.6% (1251/1269) |

Sonnet 5 and Terra-medium agree on ~99% of judge-scored criteria; the
disagreement hotspots are precisely the known interpretive criteria
(`bounded_test_decision`, `conversion_clarity`, `cells_isolate_factors`),
which stays consistent with the rubric-v2 finding that checkable criteria are
stable and interpretive ones carry the noise. Second-judge grading costs
~$2/arm. Total spend for the ablation: ~$20.3 candidates + ~$17.3 judges.

## What failed most (all arms pooled)

`hypothesis_prediction` (27×) and `operational_hypothesis` (21×) — the
KPI-less-hypothesis gap survives every arm and remains the single biggest
model limitation this benchmark exposes. `canonical_product_name` (21×),
`partial_metric_denominators` (14×), `bounded_test_decision` (12×) follow.

## Protocol consequence

All three new holdouts are now inspected and rotate to development. Next
holdout batch: bias toward infeasibility and constraint density; avoid
facts-in-prompt detection tasks.
