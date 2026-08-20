# MVP eval report — 20260819-233057-6e21f87b

> Historical rubric-v1 report. See the
> [rubric-v2 calibration](20260820-rubric-v2-calibration.md) for the
> non-destructive regrade of these same submissions.

- Skills in prompt: yes
- Tools: none
- Repetitions per task: 3 (all must pass)
- Max output tokens: 16000 Anthropic ceiling (required by the API); OpenAI uncapped unless a candidate sets one; per-candidate overrides: gpt-5.6-luna-xhigh=32000, gpt-5.6-luna-max=64000; temperature omitted
- Human-verified verdicts: 0 of 42

## Scoreboard

The score is the task pass rate under the all-repetitions-pass
protocol. Cost and latency sit beside it and are never blended in.

| Model | Score | Criterion pass rate | Cost (USD) | Mean latency |
|---|---|---|---|---|
| gpt-5.6-luna-xhigh | **6/7 (86%)** | 0.993 | $0.33 | 104.4s |
| gpt-5.6-luna-max | **6/7 (86%)** | 0.993 | $0.63 | 198.4s |

## Task grid (pass = all repetitions passed every rubric criterion)

| Task | gpt-5.6-luna-xhigh | gpt-5.6-luna-max |
|---|---|---|
| ad-creatives | FAIL (PPF) | FAIL (PFP) |
| ad-performance-analysis | PASS (PPP) | PASS (PPP) |
| blog-post | PASS (PPP) | PASS (PPP) |
| headline | PASS (PPP) | PASS (PPP) |
| landing-page | PASS (PPP) | PASS (PPP) |
| marketing-plan | PASS (PPP) | PASS (PPP) |
| shopify-meta-capi | PASS (PPP) | PASS (PPP) |
| **Tasks passed** | **6/7** | **6/7** |

Per-repetition marks: P pass, F fail, T truncated/abnormal finish
(counts as a failure; not quality evidence), E provider error.

## Criterion failures (quality evidence only: judge verdicts on
normally-finished attempts, human overrides applied)

| Task | Criterion | Failures |
|---|---|---|
| ad-creatives | falsifiable_hypotheses | 2 |

## Task prompts and model submissions

Every cell links to the exact text: the full prompt sent (fixtures
and skills included) and each repetition's raw submission.

| Task | Prompt | gpt-5.6-luna-xhigh | gpt-5.6-luna-max |
|---|---|---|---|
| ad-creatives | — | [r1 P](responses/ad-creatives--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/ad-creatives--gpt-5.6-luna-xhigh--r2.md) · [r3 F](responses/ad-creatives--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/ad-creatives--gpt-5.6-luna-max--r1.md) · [r2 F](responses/ad-creatives--gpt-5.6-luna-max--r2.md) · [r3 P](responses/ad-creatives--gpt-5.6-luna-max--r3.md) |
| ad-performance-analysis | — | [r1 P](responses/ad-performance-analysis--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/ad-performance-analysis--gpt-5.6-luna-xhigh--r2.md) · [r3 P](responses/ad-performance-analysis--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/ad-performance-analysis--gpt-5.6-luna-max--r1.md) · [r2 P](responses/ad-performance-analysis--gpt-5.6-luna-max--r2.md) · [r3 P](responses/ad-performance-analysis--gpt-5.6-luna-max--r3.md) |
| blog-post | — | [r1 P](responses/blog-post--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/blog-post--gpt-5.6-luna-xhigh--r2.md) · [r3 P](responses/blog-post--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/blog-post--gpt-5.6-luna-max--r1.md) · [r2 P](responses/blog-post--gpt-5.6-luna-max--r2.md) · [r3 P](responses/blog-post--gpt-5.6-luna-max--r3.md) |
| headline | — | [r1 P](responses/headline--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/headline--gpt-5.6-luna-xhigh--r2.md) · [r3 P](responses/headline--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/headline--gpt-5.6-luna-max--r1.md) · [r2 P](responses/headline--gpt-5.6-luna-max--r2.md) · [r3 P](responses/headline--gpt-5.6-luna-max--r3.md) |
| landing-page | — | [r1 P](responses/landing-page--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/landing-page--gpt-5.6-luna-xhigh--r2.md) · [r3 P](responses/landing-page--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/landing-page--gpt-5.6-luna-max--r1.md) · [r2 P](responses/landing-page--gpt-5.6-luna-max--r2.md) · [r3 P](responses/landing-page--gpt-5.6-luna-max--r3.md) |
| marketing-plan | — | [r1 P](responses/marketing-plan--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/marketing-plan--gpt-5.6-luna-xhigh--r2.md) · [r3 P](responses/marketing-plan--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/marketing-plan--gpt-5.6-luna-max--r1.md) · [r2 P](responses/marketing-plan--gpt-5.6-luna-max--r2.md) · [r3 P](responses/marketing-plan--gpt-5.6-luna-max--r3.md) |
| shopify-meta-capi | — | [r1 P](responses/shopify-meta-capi--gpt-5.6-luna-xhigh--r1.md) · [r2 P](responses/shopify-meta-capi--gpt-5.6-luna-xhigh--r2.md) · [r3 P](responses/shopify-meta-capi--gpt-5.6-luna-xhigh--r3.md) | [r1 P](responses/shopify-meta-capi--gpt-5.6-luna-max--r1.md) · [r2 P](responses/shopify-meta-capi--gpt-5.6-luna-max--r2.md) · [r3 P](responses/shopify-meta-capi--gpt-5.6-luna-max--r3.md) |

## Model efficiency and criterion resolution

| Model | Completed | Mean latency | Output tokens | Cost (USD) | Criteria passed | Criterion pass rate |
|---|---|---|---|---|---|---|
| gpt-5.6-luna-xhigh | 21/21 | 104.4s | 274165 | $0.33 | 152/153 | 0.993 |
| gpt-5.6-luna-max | 21/21 | 198.4s | 526257 | $0.63 | 152/153 | 0.993 |

Pass rate by rubric section (normally-finished attempts only):

| Model | completion | skill_adherence | best_practices |
|---|---|---|---|
| gpt-5.6-luna-xhigh | 1.0 | 1.0 | 0.978 |
| gpt-5.6-luna-max | 1.0 | 1.0 | 0.978 |

## Run health

- Attempts: 42 planned, 0 provider errors (count as failures)
- Judge failures (ungraded, count as failures): 0
- Total output tokens: 800422
- Tool calls (all tools, by name): none
- Attempts with abnormal finish (truncation/refusal; check finish_reason): 0
- Attempts that needed a doubled output ceiling (reasoning overflow): 0

Generated by `mvp/bench.py report`. Judge verdicts are advisory until
human-verified; the grid above already applies any human overrides.
