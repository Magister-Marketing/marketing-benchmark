# MVP eval report — 20260820-004238-72d18331

> Historical rubric-v1 report. See the
> [rubric-v2 calibration](20260820-rubric-v2-calibration.md) for the
> non-destructive regrade of these same submissions.

- Skills in prompt: yes
- Tools: none
- Repetitions per task: 3 (all must pass)
- Max output tokens: 16000 Anthropic ceiling (required by the API); OpenAI uncapped unless a candidate sets one; temperature omitted
- Human-verified verdicts: 0 of 63

## Scoreboard

The score is the task pass rate under the all-repetitions-pass
protocol. Cost and latency sit beside it and are never blended in.

| Model | Score | Criterion pass rate | Cost (USD) | Mean latency |
|---|---|---|---|---|
| gpt-5.6-luna-medium | **6/7 (86%)** | 0.993 | $0.08 | 28.8s |
| gpt-5.6-terra-medium | **7/7 (100%)** | 1.0 | $0.87 | 33.4s |
| gpt-5.6-sol-medium | **6/7 (86%)** | 0.993 | $2.47 | 59.2s |

## Task grid (pass = all repetitions passed every rubric criterion)

| Task | gpt-5.6-luna-medium | gpt-5.6-terra-medium | gpt-5.6-sol-medium |
|---|---|---|---|
| ad-creatives | FAIL (PFP) | PASS (PPP) | FAIL (FPP) |
| ad-performance-analysis | PASS (PPP) | PASS (PPP) | PASS (PPP) |
| blog-post | PASS (PPP) | PASS (PPP) | PASS (PPP) |
| headline | PASS (PPP) | PASS (PPP) | PASS (PPP) |
| landing-page | PASS (PPP) | PASS (PPP) | PASS (PPP) |
| marketing-plan | PASS (PPP) | PASS (PPP) | PASS (PPP) |
| shopify-meta-capi | PASS (PPP) | PASS (PPP) | PASS (PPP) |
| **Tasks passed** | **6/7** | **7/7** | **6/7** |

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

| Task | Prompt | gpt-5.6-luna-medium | gpt-5.6-terra-medium | gpt-5.6-sol-medium |
|---|---|---|---|---|
| ad-creatives | [prompt](prompts/ad-creatives.md) | [r1 P](responses/ad-creatives--gpt-5.6-luna-medium--r1.md) · [r2 F](responses/ad-creatives--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/ad-creatives--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/ad-creatives--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/ad-creatives--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/ad-creatives--gpt-5.6-terra-medium--r3.md) | [r1 F](responses/ad-creatives--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/ad-creatives--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/ad-creatives--gpt-5.6-sol-medium--r3.md) |
| ad-performance-analysis | [prompt](prompts/ad-performance-analysis.md) | [r1 P](responses/ad-performance-analysis--gpt-5.6-luna-medium--r1.md) · [r2 P](responses/ad-performance-analysis--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/ad-performance-analysis--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/ad-performance-analysis--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/ad-performance-analysis--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/ad-performance-analysis--gpt-5.6-terra-medium--r3.md) | [r1 P](responses/ad-performance-analysis--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/ad-performance-analysis--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/ad-performance-analysis--gpt-5.6-sol-medium--r3.md) |
| blog-post | [prompt](prompts/blog-post.md) | [r1 P](responses/blog-post--gpt-5.6-luna-medium--r1.md) · [r2 P](responses/blog-post--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/blog-post--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/blog-post--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/blog-post--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/blog-post--gpt-5.6-terra-medium--r3.md) | [r1 P](responses/blog-post--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/blog-post--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/blog-post--gpt-5.6-sol-medium--r3.md) |
| headline | [prompt](prompts/headline.md) | [r1 P](responses/headline--gpt-5.6-luna-medium--r1.md) · [r2 P](responses/headline--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/headline--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/headline--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/headline--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/headline--gpt-5.6-terra-medium--r3.md) | [r1 P](responses/headline--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/headline--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/headline--gpt-5.6-sol-medium--r3.md) |
| landing-page | [prompt](prompts/landing-page.md) | [r1 P](responses/landing-page--gpt-5.6-luna-medium--r1.md) · [r2 P](responses/landing-page--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/landing-page--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/landing-page--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/landing-page--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/landing-page--gpt-5.6-terra-medium--r3.md) | [r1 P](responses/landing-page--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/landing-page--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/landing-page--gpt-5.6-sol-medium--r3.md) |
| marketing-plan | [prompt](prompts/marketing-plan.md) | [r1 P](responses/marketing-plan--gpt-5.6-luna-medium--r1.md) · [r2 P](responses/marketing-plan--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/marketing-plan--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/marketing-plan--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/marketing-plan--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/marketing-plan--gpt-5.6-terra-medium--r3.md) | [r1 P](responses/marketing-plan--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/marketing-plan--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/marketing-plan--gpt-5.6-sol-medium--r3.md) |
| shopify-meta-capi | [prompt](prompts/shopify-meta-capi.md) | [r1 P](responses/shopify-meta-capi--gpt-5.6-luna-medium--r1.md) · [r2 P](responses/shopify-meta-capi--gpt-5.6-luna-medium--r2.md) · [r3 P](responses/shopify-meta-capi--gpt-5.6-luna-medium--r3.md) | [r1 P](responses/shopify-meta-capi--gpt-5.6-terra-medium--r1.md) · [r2 P](responses/shopify-meta-capi--gpt-5.6-terra-medium--r2.md) · [r3 P](responses/shopify-meta-capi--gpt-5.6-terra-medium--r3.md) | [r1 P](responses/shopify-meta-capi--gpt-5.6-sol-medium--r1.md) · [r2 P](responses/shopify-meta-capi--gpt-5.6-sol-medium--r2.md) · [r3 P](responses/shopify-meta-capi--gpt-5.6-sol-medium--r3.md) |

## Model efficiency and criterion resolution

| Model | Completed | Mean latency | Output tokens | Cost (USD) | Criteria passed | Criterion pass rate |
|---|---|---|---|---|---|---|
| gpt-5.6-luna-medium | 21/21 | 28.8s | 64585 | $0.08 | 152/153 | 0.993 |
| gpt-5.6-terra-medium | 21/21 | 33.4s | 70639 | $0.87 | 153/153 | 1.0 |
| gpt-5.6-sol-medium | 21/21 | 59.2s | 80260 | $2.47 | 152/153 | 0.993 |

Pass rate by rubric section (normally-finished attempts only):

| Model | completion | skill_adherence | best_practices |
|---|---|---|---|
| gpt-5.6-luna-medium | 1.0 | 1.0 | 0.978 |
| gpt-5.6-terra-medium | 1.0 | 1.0 | 1.0 |
| gpt-5.6-sol-medium | 1.0 | 1.0 | 0.978 |

## Run health

- Attempts: 63 planned, 0 provider errors (count as failures)
- Judge failures (ungraded, count as failures): 0
- Total output tokens: 215484
- Tool calls (all tools, by name): none
- Attempts with abnormal finish (truncation/refusal; check finish_reason): 0
- Attempts that needed a doubled output ceiling (reasoning overflow): 0

Generated by `mvp/bench.py report`. Judge verdicts are advisory until
human-verified; the grid above already applies any human overrides.
