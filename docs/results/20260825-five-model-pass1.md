# Five-model pass@1 run: first cross-provider board, 18 tasks

Run `20260825-170012-9154f22d`: gpt-5.6-luna/terra/sol medium plus
claude-sonnet-5 and claude-opus-5, 18 tasks (14 development + 4 fresh
holdout), one attempt per task (pass@1 — the published-run protocol as of
this run), skills on, tools off. Judge claude-sonnet-5, second judge
gpt-5.6-terra-medium. 90/90 attempts and 90/90 judgments complete.

Live: https://marketingbenchmark.ai (featured run).

## Scores

| Model | Pass@1 | Candidate cost | Avg task time |
|---|---:|---:|---:|
| **claude-opus-5** | **18/18 (100%)** | $2.98 | 92.4s |
| gpt-5.6-terra-medium | 15/18 (83%) | $0.67 | 34.9s |
| gpt-5.6-sol-medium | 14/18 (78%) | $1.69 | 42.9s |
| claude-sonnet-5 | 12/18 (67%) | $0.85 | 55.4s |
| gpt-5.6-luna-medium | 12/18 (67%) | $0.06 | 24.0s |

Claude Opus 5 posted the first perfect score in this benchmark's history —
every task, every criterion, including all four untouched holdouts. It spent
the most time (92s/task), the most tokens (114k output, 2× Sol's), and the
most money doing it. Terra remains the value pick: second place at a fifth
of Opus's cost. Sonnet 5 is the surprise of the board — see below.

## Two runner-fairness fixes, disclosed

Both were harness artifacts corrected and regraded before this report;
neither judges model content.

1. **Anthropic ceiling retry.** Both Claude models spent the entire 16k
   output-token ceiling *thinking* on `launch-capacity-trap` and returned
   empty completions. The runner's empty-completion retry only recognized
   OpenAI's `incomplete` finish shape, so these were recorded as provider
   errors (E) instead of being retried with a doubled cap. Fixed; the two
   attempts were re-executed via the new `bench.py retry` command
   (`retried: true` in the evidence; both needed >16k tokens and finished
   cleanly at the 32k retry ceiling). Opus converted the retry into a 9/9
   pass; Sonnet completed but failed one criterion honestly.
2. **CTA terminal period.** All five models failed
   `platform-limits-gauntlet`'s programmatic `approved_cta_exact` with
   `approved_cta_count=0` — because all five wrote 'Review consultation
   availability.' with a period, exactly as the brand facts print it at the
   end of a sentence. A uniform 5/5 failure of an exact-match check is an
   extraction-bug signature, not a model finding; the check now accepts a
   single terminal period (rubric_version 2) and the task was regraded.

Without these fixes the published board would have read opus 16/18 and
"every model failed the gauntlet" — both artifacts of the harness, not the
models.

## New holdout report card (first exposure, now inspected)

- `launch-capacity-trap`: **discriminates** — luna F (arithmetic drift,
  incomplete options), sol F and sonnet F (presented options without
  committing to a grounded recommendation), terra P, opus P. The
  infeasibility thesis holds for a second batch: this is the same failure
  surface budget-reconciliation-trap exposed, now in hours instead of
  dollars. Notably both Claude models needed >16k thinking tokens on it.
- `unsupportable-claims-brief`: **discriminates, on one criterion** — the
  OpenAI trio all failed only `evidence_unlock` (declining claims without
  saying what evidence would unlock them later); both Claude models
  volunteered it. The criterion is strict-but-deliberate (the actionable-
  pushback bar); it is also the run's most judge-contested criterion (2/5
  cross-judge disagreement), so it goes on the calibration list now that
  the task rotates to development.
- `platform-limits-gauntlet`: **saturated after the CTA fix** — every model
  met every character limit. The hypothesis that hard char limits are a
  model weakness did not survive contact at these limits (30/40/90/125/150/
  160). Tighter limits or more interacting fields would be needed to make
  this task bite.
- `rate-card-reconciliation`: **saturated on arrival** — 5/5 passed 10/10,
  including choosing the negotiated rate among four candidates and
  quantifying all three planted errors. Careful cross-fixture invoice
  arithmetic is now table stakes at the frontier.

Running tally across both holdout batches: infeasibility traps discriminate
(2/2), facts-in-prompt detection saturates (2/3), and now precise
arithmetic/limits compliance saturates too (2/2). The discriminating axis is
judgment under conflicting commitments, not precision.

## The Sonnet 5 surprise

Sonnet 5 tied luna at 12/18 despite costing 14× more. Its failures are not
reasoning failures: malformed single-file HTML on both landing-page tasks
(`complete_html`, clean end_turn finishes well under the ceiling), missing
plan structure on marketing-plan (5/8: three_channels,
sequenced_90_days, mature_activation_denominator), and small arithmetic
slips (budget-trap `auditable_arithmetic`, ad-performance denominators). At
pass@1 with no retry, Sonnet under-delivers on long structured deliverables
while acing the judgment-heavy holdouts it shares with Opus (2/4 → after
fixes, unsupportable-claims and rate-card passed; capacity-trap failed only
on the recommendation criterion). A pass³ run would tell whether this is
variance or a stable shape.

## Family patterns

- The KPI-less-hypothesis gap (`hypothesis_prediction`,
  `operational_hypothesis`) is now visibly a **family** trait: all three
  OpenAI models failed both; both Claude models passed both.
- Anthropic models grounded declines with unlock evidence unprompted;
  OpenAI models did not.
- OpenAI models failed `ad-creatives` on hypothesis/product-name criteria;
  both Claude models passed it.

## Judge health

Primary judge $2.77 (90 calls); judge-b $1.49; cross-family agreement
**96.4%** on 855 judge-scored criteria. Hotspots are the usual interpretive
criteria (`conversion_clarity` 3/5, `single_ask` 2/5, `bounded_test_decision`,
`conditional_recommendation`, `evidence_unlock` 2/5 each). One caveat this
run introduces: the primary judge (Sonnet 5) now grades its own family,
including the leader. The 96.4% cross-family agreement — and the fact that
Opus's perfect score survives under the OpenAI second judge's criteria too —
is the check on that conflict; a non-Anthropic primary judge for Anthropic
candidates is worth considering if the gap ever matters.

Total spend: $6.24 candidates + $4.26 judges ≈ $10.50.

## Protocol notes

- Published runs are pass@1 as of this run (was pass³). Scores are not
  comparable across metrics; the site never mixes them in one table.
- All four new holdouts are now inspected and rotate to development.
- A perfect score means the development set no longer measures Opus-class
  models; the next holdout batch is now load-bearing for the top of the
  board. Bias it toward compound infeasibility (multiple interacting
  conflicts), adversarial pushback, and judgment under ambiguity — not
  precision, limits, or detection.
