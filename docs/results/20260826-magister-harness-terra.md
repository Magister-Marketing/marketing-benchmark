# 2026-08-26 — First Magister-harness arm: Terra beats its own plain arm and, on re-grade, ties its skills arm

> **Re-graded 2026-09-02** under the scoring shipped in
> [PR #11](https://github.com/Magister-Marketing/marketing-benchmark/pull/11)
> (oracle-backed critical criteria, judge `self_report`, `critical` read live,
> free-credit discount, negatives gated on a positive). Same judge, same
> recorded rubric snapshots, fresh judge sample for all three arms. Tables
> carry the re-graded numbers; the original grading is shown where a figure
> moved. Single-criterion flips between the two samples are judge variance
> on interpretive criteria, not a scoring-rule effect.

**Runs (18 tasks, pass@1, judge claude-sonnet-5 with gpt-5.6-terra-medium as judge-b):**

| Configuration | Run | GPT-5.6 Terra (medium) | Score (0–100) | Claude Sonnet 5 | Score (0–100) |
|---|---|---:|---:|---:|---:|
| Plain model + web search (no skills) | `20260826-052545-86a467c8` | 10/18 (was 11) | 94.3 | 8/18 | 92.9 |
| Plain model + marketingskills + web search | `20260825-230519-539e42f9` | 12/18 | 95.2 | 9/18 | 94.1 |
| **Magister harness (production agent)** | `20260826-053858-0af06e7c` | **12/18** (was 14) | **95.3** | — | — |

Re-grade movement: the harness arm lost `email-flow-repair` (13/14,
`no_new_claims`) and `unsupportable-claims-brief` (9/10, `evidence_unlock`);
the plain arm lost `factorial-ad-test` (`cells_isolate_factors`); the skills
arm's Terra and Sonnet rows did not move. Every flip is one judge criterion.

The Magister arm ran the identical 18 tasks through the production Magister
agent on the internal Team+Test canary project: same task prompts and source
fixtures, no inlined skill text — the machine brings its own marketingskills
pack, hosted tools, and web research, exactly as it does for customers.
Result, as published: **+2 tasks over the same model with skills in the
prompt, +3 over the plain model**. On the re-grade it is **level with the
skills arm (12/18 each, 95.3 vs 95.2) and +2 over the plain model** — the
two tasks the harness lost went on single interpretive criteria. Run-to-run
variance on this suite is roughly ±3 at pass@1, so treat the deltas as
directional until replicated.

Versus the same model's skills arm, the harness **gained**
`budget-reconciliation-trap`, `factorial-ad-test`, and
`launch-capacity-trap` (and `unsupportable-claims-brief` in the original
sample), and **lost** `marketing-plan` (6/8 criteria) and
`platform-limits-gauntlet` (9/10), plus `email-flow-repair` (13/14) on the
re-grade. `ad-creatives` and `ad-performance-analysis` fail in both (the
latter by one criterion in the Magister arm).

**Honest cost accounting.** The Magister arm's tokens and cost sum every LLM
call of the agent's working turn (~114k input tokens per task just from the
machine's system prompt and context): $4.74 for the suite vs. $0.95 for the
same model over the API with skills, at 150s average per task vs. 31s. The
quality/cost/speed columns are deliberately never blended.

## Mechanics (evals/magister/public_bench_bridge.py, magister repo)

- Bridge writes a public-runner-format run dir; `grade` / `agreement` /
  `report` score it with the same pipeline as every direct-API arm.
- Candidate model pinned per chat session via `model_eval_session_overrides`
  and verified from usage metadata (contamination check); sessions isolated
  and deleted; fixture lease held and renewed per attempt; machine refreshed
  every 9 attempts.
- Judge agreement: 99.4% (1 disagreement in 171 criteria:
  `email-flow-repair :: no_new_claims` on the re-grade;
  `unsupportable-claims-brief :: evidence_unlock` in the original sample).
- Re-grade judge spend: $0.56 (harness arm) and $1.21 (plain arm); the
  skills arm is accounted in the real-skills ablation doc.

## Findings that changed the harness

- **SSE lstrip bias (fixed before this run):** `scripts/e2e_support.py`
  `stream_sse()` stripped payload whitespace, deleting inter-word spaces from
  token-sized chunks — the first smoke response came back with *no spaces at
  all*. Only the Magister arm reads SSE, so the bias was one-sided against
  Magister. Same defect as magister-marketing PR #1363; fixed on the bridge's
  branch.
- **Broken streams are not failed turns:** 4 of 18 first-pass attempts died
  with "stream ended without a 'done' event" clustered around machine
  restarts. Detached turn execution means the machine finishes and persists
  the answer anyway, so the bridge now polls persisted messages for a stable
  assistant answer before failing an attempt, and `--into <run_dir>` re-runs
  errored attempts in place (all 4 passed cleanly on retry, 42–84s each).

## Caveats / next

- One model through the harness so far; Sonnet 5 (and the rest of the board)
  need Magister arms before the comparison generalizes.
- The no-skills web-search arm has only terra + sonnet (trial scope); the
  full six-model arm is pending.
- All verdicts judge-scored, 0 human-verified.
