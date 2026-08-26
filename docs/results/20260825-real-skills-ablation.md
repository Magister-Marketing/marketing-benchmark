# Real-skills ablation: the production skill pack, three arms, six models

Runs `20260825-222810-a1437fef` (baseline: skills on, tools off),
`20260825-230519-539e42f9` (tools: skills + provider web search), and
`20260825-234438-8373ba31` (no skills, no tools). 18 tasks, pass@1, six
models, judge claude-sonnet-5 with second judge gpt-5.6-terra-medium.
324/324 attempts completed with zero candidate errors; judge agreement
94.4% / 94.7% / 94.8% per arm on the full 1,026-criteria samples.

This is the first ablation where the skills arm carries the **verbatim
production skill pack** — unmodified SKILL.md files from
[marketingskills](https://github.com/coreyhaines31/marketingskills) by Corey
Haines, at the pin every Magister machine ships
(`evals/fixtures/public/skills/README.md` has the provenance). Earlier runs
used ~500-byte benchmark-written distillations; scores are not comparable
across that boundary.

Live: https://marketingbenchmark.ai (baseline is the featured run; the
skills/tools section shows all three arms).

## Scores

| Model | Baseline | Tools on | No skills |
|---|---:|---:|---:|
| gpt-5.6-sol-medium | 13/18 | **15/18** | 12/18 |
| claude-opus-5 | 13/18 | 13/18 | 12/18 |
| gpt-5.6-terra-medium | 12/18 | 12/18 | 10/18 |
| gpt-5.6-luna-medium | 12/18 | 10/18 | 10/18 |
| claude-sonnet-5 | 9/18 | 9/18 | 10/18 |
| claude-haiku-4-5 | 4/18 | 5/18 | 5/18 |

Read per-model deltas against the measured pass@1 noise (±3 on this suite;
see the six-model anchor doc). The signals that survive that caution:

- **Sol converts web search into wins — again.** +2 with tools here, +2 in
  the 14-task pass³ ablation. Two independent experiments, same direction,
  largest tools delta on the board both times. Luna moved −2 with tools,
  also matching its earlier −1: search seems to actively cost the smallest
  GPT model accuracy.
- **The pooled skills effect is positive but modest**: 63 tasks passed with
  skills vs 59 without, concentrated in the four frontier models (sol,
  opus, terra, luna are +1 to +2 each; sonnet and haiku are flat-to-negative).
  The production pack helps models that can follow it.

## The headline finding: our old skill file was an answer key

`ad-performance-analysis` went from mixed results to **0/6** in the
baseline arm, on the same fixtures and rubric. The judge evidence shows all
six models making the identical error: the fixture withholds week-4
conversions for one campaign, and every model computed the headline CPA as
$1,000 of four-week spend ÷ 7 conversions from three known weeks
($142.86), failing `partial_metric_denominators`. Five of six also failed
`bounded_test_decision` (next test proposed without a numeric win rule or
sample floor).

In the previous run — old distilled skills — terra, sol, and opus passed
that criterion by matching $750 of spend to the same three complete weeks.
The distilled analytics skill literally said "Use complete, comparable date
ranges", "Preserve missing values as missing", and "End with … a bounded
next test." It was an unintentional answer key for exactly these criteria.
Corey's real analytics skill is production workflow guidance and contains
no denominator or missing-data discipline, so every model reverted to the
natural error.

Two conclusions, both worth keeping:

1. **The criteria are fair and now genuinely discriminative.** Catching a
   missing week before dividing is table-stakes analyst hygiene; the judge
   evidence is precise and unanimous. Frontier models silently mix
   measurement windows unless told not to.
2. **A single sentence of skill guidance was worth the criterion.** That is
   the sharpest evidence yet that skill files measurably change analytical
   competence — and a warning for benchmark design: bespoke per-benchmark
   "skills" drift into teaching-to-the-test. Verbatim production skills
   keep the skills arm honest.

## Judge reliability fix, disclosed

Terra-as-judge emits malformed verdict JSON in correlated streaks — the
same parse failure at the same character offset, twice in a row on the same
response (worst on `blog-post`). The single in-run retry regularly
exhausted, leaving holes in the judge-b sample. Judgments now get four
tries, and a final failure records the raw emission prefix
(`error_raw_prefix`) for diagnosis. Arms 1 and 2 were patched to 108/108
with targeted regrades; arm 3 ran the fix natively and finished with zero
failures on both judges.

## Cost

Roughly $13–15 per arm (candidates + both judges), ≈ $42 for the
experiment. The tools arm's candidate spend runs higher (opus $5.94 with
web search vs $3.23 baseline) because search results inflate input tokens.

## Protocol notes

- The baseline arm (`20260825-222810`) is the site's featured run going
  forward; the pre-swap six-model anchor (`20260825-205808`) remains
  published for the variance record but is not comparable task-by-task on
  skill-sensitive criteria.
- Next: human verification pass (still 0 verified), a pass³ replication of
  the skills effect, and the next holdout batch (bias toward compound
  infeasibility and judgment under ambiguity — precision and limits
  saturate).
