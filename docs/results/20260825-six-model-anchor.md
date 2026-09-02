# Six-model anchor run: Haiku 4.5 sets the floor, pass@1 shows its variance

> **Re-graded 2026-09-02** under the scoring shipped in
> [PR #11](https://github.com/Magister-Marketing/marketing-benchmark/pull/11)
> (oracle-backed critical criteria, judge `self_report`, `critical` read live,
> free-credit discount, negatives gated on a positive). Same judge, same
> recorded rubric snapshot, fresh judge sample. Tables carry the re-graded
> numbers; the original grading is shown where a figure moved. Per-task
> commentary describes the original sample unless it says otherwise —
> single-criterion flips between the two samples are judge variance on
> interpretive criteria, not a scoring-rule effect.

Run `20260825-205808-a4d07885`: the same 18 tasks and pass@1 protocol as the
five-model run a few hours earlier (`20260825-170012`), plus
**claude-haiku-4-5** as a deliberate capability anchor. Skills on, tools off.
Judge claude-sonnet-5, second judge gpt-5.6-terra-medium. 108/108 attempts
and 108/108 judgments complete.

Live: https://marketingbenchmark.ai (featured run).

## Scores

| Model | Pass@1 | Score (0–100) | Candidate cost | Avg task time |
|---|---:|---:|---:|---:|
| **claude-opus-5** | **15/18 (83%)** | **98.6** | $3.02 | 93.5s |
| gpt-5.6-sol-medium | 13/18 (72%) | 96.5 | $1.81 | 48.4s |
| gpt-5.6-terra-medium | 13/18 (72%) | 95.7 | $0.66 | 35.0s |
| gpt-5.6-luna-medium | 11/18 (61%) — was 12/18 | 95.6 | $0.06 | 22.3s |
| claude-sonnet-5 | 9/18 (50%) | 90.8 | $1.03 | 66.9s |
| claude-haiku-4-5 | 4/18 (22%) | 85.8 | $0.26 | 24.5s |

Re-grade movement: 15 of 1,026 judge-scored criteria changed verdict (7
down, 8 up). Luna lost `launch-capacity-trap` (`grounded_recommendation`);
Opus lost `ad-performance-analysis` (`partial_metric_denominators` — the
judge now penalises the extra full-spend CPA presented beside the correct
comparable-basis one) and gained `budget-reconciliation-trap`
(`no_invented_funds`); Haiku swapped `headline` and `launch-capacity-trap`
for `analytics-source-conflict` and `email-flow-repair`, staying at 4/18.

The board now spans 22%–83%: the suite has a real floor, and frontier scores
are not saturation artifacts.

## The headline finding is the variance

This run is a same-day, identical-input repeat of the five-model run — same
tasks, same prompts, same settings, same judges. Pass@1 deltas, purely from
sampling:

| Model | Run 170012 | Run 205808 | Δ |
|---|---:|---:|---:|
| claude-opus-5 | 18 | 15 | −3 |
| gpt-5.6-terra-medium | 14 (was 15) | 13 | −1 (was −2) |
| gpt-5.6-sol-medium | 14 | 13 | −1 |
| gpt-5.6-luna-medium | 12 | 11 (was 12) | −1 (was 0) |
| claude-sonnet-5 | 11 (was 12) | 9 | −2 (was −3) |

(Both runs re-graded 2026-09-02; the original values are in parentheses.)

Rank order held (opus > terra ≥ sol ≥ luna > sonnet), but single scores moved
by up to 3 tasks on an 18-task suite. Treat any single pass@1 board as ±3;
differences of 1–2 tasks between adjacent models are noise. This is the
strongest internal evidence yet for returning to repeated attempts (pass³ or
paired runs) once the published protocol revisits it.

## One extraction fix, disclosed

Opus appended a voluntary self-audit to its `platform-limits-gauntlet`
answer ("Character audit: RSA-H1: 28/30 …"). The programmatic extractor
counted those audit lines as *duplicate labels* and failed the attempt with
`missing_or_duplicate_label_count=5` — a harness artifact, not a model
error. The extractor now grades the **first line bearing each label** and
treats later restatements as commentary (rubric_version 3); the task was
regraded under both judges. Opus's gauntlet flipped to a clean 8/8 pass.
Haiku's gauntlet failure was inspected and stands: real character-limit
violations (~130-character values against 90-character caps), not an
extraction quirk.

## Sonnet 5's overthinking pathology, now reproduced

On `launch-capacity-trap`, Sonnet burned the entire output budget thinking —
twice, in two independent samples. Sample 1 spent 16k, was retried at the
doubled 32k ceiling per protocol, and still returned an empty completion
(recorded as an honest provider error). The re-execution (`bench.py retry`,
`retried: true` in evidence) spent 529 seconds, hit the 32k cap again, and
truncated 1.3KB into the answer table; the judge graded it incomplete.
Opus needed >16k on the same task in the previous run but finished at 32k —
Sonnet appears to sit past the task's thinking-budget cliff. At 50%, Sonnet's
board score also reflects the same long-deliverable weaknesses as last run
(malformed single-file HTML on both landing-page tasks, thin marketing-plan
structure).

Notably, **Haiku finished the task Sonnet couldn't** — a 9/9 on
launch-capacity-trap in 24 seconds in the original sample (the re-grade
judge failed it on `explicit_constraint_changes`: no option states that the
go-live date itself is being moved). Small model, no thinking spiral.

## What the anchor reveals

Haiku's four passes in the original sample: blog-post, headline,
launch-capacity-trap, and rate-card-reconciliation — the short-deliverable
and arithmetic tasks (on the re-grade it holds blog-post and rate-card,
drops headline on an unqualified "eight hours of light" claim, and picks up
analytics-source-conflict and email-flow-repair). Its fourteen failures
cluster exactly where the suite is supposed to bite: multi-constraint
deliverables, infeasibility traps, and cross-fixture conflicts.
`budget-reconciliation-trap` failed 5 of 6 models this run (luna was the
only pass; the re-grade judge also passed Opus, whose contingent tooling
reclassification it read as flagged rather than invented); the judge
evidence shows genuine hedging ("pick one
lane" without picking) and one invented budget line — real failures, not
rubric artifacts.

## Judge health

Cross-family agreement **93.1%** (955/1,026 judge-scored criteria across
108 attempts; 93.2% against the original sample — was 96% on the smaller
board: Haiku's messier outputs add
interpretive load). Hotspots remain the interpretive criteria:
`grounded_claims`, `conversion_clarity`, `no_invented_proof`,
`grounded_recommendation`. The primary judge still grades its own family;
the cross-family second judge remains the check.

Approximate spend: $6.84 candidates + $5.63 judges ≈ $12.50 at
publication, plus $3.71 for the re-grade.

## Runner fixes shipped alongside this run

- `bench.py retry` re-executes only errored attempts in place (prompt-sha
  guarded, `retried: true` provenance) and prints the regrade command.
- Anthropic's `max_tokens` finish now qualifies for the empty-completion
  ceiling retry (was OpenAI-only).
- Provider calls dropped mid-response body (`http.client.IncompleteRead`)
  now retry like any transient network failure instead of killing the run.
