# Real-skills ablation: the production skill pack, three arms, six models

> **Re-graded 2026-09-02** under the scoring shipped in
> [PR #11](https://github.com/Magister-Marketing/marketing-benchmark/pull/11)
> (oracle-backed critical criteria, judge `self_report`, `critical` read live,
> free-credit discount, negatives gated on a positive). Same judge, same
> recorded rubric snapshots, fresh judge sample for all three arms. Tables
> carry the re-graded numbers; the original grading is shown where a figure
> moved. Per-task commentary describes the original sample unless it says
> otherwise — single-criterion flips between the two samples are judge
> variance on interpretive criteria, not a scoring-rule effect.

Runs `20260825-222810-a1437fef` (baseline: skills on, tools off),
`20260825-230519-539e42f9` (tools: skills + provider web search), and
`20260825-234438-8373ba31` (no skills, no tools). 18 tasks, pass@1, six
models, judge claude-sonnet-5 with second judge gpt-5.6-terra-medium.
324/324 attempts completed with zero candidate errors; judge agreement
94.1% / 94.4% / 95.1% per arm on the full 1,026-criteria samples (94.4% /
94.7% / 94.8% against the original judge sample).

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
| gpt-5.6-sol-medium | 13/18 | **15/18** | 13/18 (was 12) |
| gpt-5.6-terra-medium | 13/18 (was 12) | 12/18 | 11/18 (was 10) |
| claude-opus-5 | 11/18 (was 13) | 13/18 | 10/18 (was 12) |
| gpt-5.6-luna-medium | 11/18 (was 12) | 10/18 | 10/18 |
| claude-sonnet-5 | 7/18 (was 9) | 9/18 | 11/18 (was 10) |
| claude-haiku-4-5 | 5/18 (was 4) | 5/18 | 6/18 (was 5) |

Score (0–100), re-graded:

| Model | Baseline | Tools on | No skills |
|---|---:|---:|---:|
| gpt-5.6-sol-medium | 95.1 | **97.8** | 95.9 |
| gpt-5.6-terra-medium | 96.3 | 95.2 | 94.7 |
| claude-opus-5 | 94.4 | 95.2 | 92.4 |
| gpt-5.6-luna-medium | 94.2 | 94.5 | 91.3 |
| claude-sonnet-5 | 89.5 | 94.1 | 92.6 |
| claude-haiku-4-5 | 85.9 | 84.1 | 86.8 |

The re-grade moved 24 / 11 / 21 of the 1,026 judge-scored criteria per arm
(baseline: 10 down, 14 up; tools: 10 down, 1 up; no skills: 9 down, 12 up).
The baseline arm lost the most tasks — Sonnet −2, Opus −2, Luna −1 — and the
no-skills arm gained — Sol, Terra, Sonnet and Haiku +1 each, Opus −2 — so
the pooled comparison below reads differently from the original.

Read per-model deltas against the measured pass@1 noise (±3 on this suite;
see the six-model anchor doc). The signals that survive that caution:

- **Sol converts web search into wins — again.** +2 with tools here, +2 in
  the 14-task pass³ ablation. Two independent experiments, same direction,
  largest tools delta on the board both times. Luna moved −1 with tools
  (−2 in the original sample), matching its earlier −1: search seems to
  actively cost the smallest GPT model accuracy.
- **The pooled skills effect is inside the noise on the re-grade**: 60
  tasks passed with skills vs 61 without (63 vs 59 in the original sample).
  Terra is +2, Opus and Luna +1, Sol flat, Haiku −1 and Sonnet −4 — Sonnet's
  baseline arm lost `ad-creatives`, `email-flow-repair` and
  `factorial-ad-test` to single-criterion judge flips. The production pack
  still helps the models that can follow it; a pass³ replication is what
  would separate that from sampling.

## The headline finding: our old skill file was an answer key

`ad-performance-analysis` went from mixed results to **0/6** in the
baseline arm, on the same fixtures and rubric. The judge evidence shows all
six models making the identical error: the fixture withholds week-4
conversions for one campaign, and every model computed the headline CPA as
$1,000 of four-week spend ÷ 7 conversions from three known weeks
($142.86), failing `partial_metric_denominators` (6/6 still fail it on the
re-grade; the task stays 0/6). Five of six also failed
`bounded_test_decision` (next test proposed without a numeric win rule or
sample floor; 3/6 on the re-grade).

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
experiment, plus $14.50 of judge spend for the 2026-09-02 re-grade ($5.34 /
$5.47 / $3.69). The tools arm's candidate spend runs higher (opus $5.94 with
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
