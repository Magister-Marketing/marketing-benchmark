# 2026-08-26 — First Magister-harness arm: Terra beats its own plain and skills arms

**Runs (18 tasks, pass@1, judge claude-sonnet-5 with gpt-5.6-terra-medium as judge-b):**

| Configuration | Run | GPT-5.6 Terra (medium) | Claude Sonnet 5 |
|---|---|---:|---:|
| Plain model + web search (no skills) | `20260826-052545-86a467c8` | 11/18 | 8/18 |
| Plain model + marketingskills + web search | `20260825-230519-539e42f9` | 12/18 | 9/18 |
| **Magister harness (production agent)** | `20260826-053858-0af06e7c` | **14/18** | — |

The Magister arm ran the identical 18 tasks through the production Magister
agent on the internal Team+Test canary project: same task prompts and source
fixtures, no inlined skill text — the machine brings its own marketingskills
pack, hosted tools, and web research, exactly as it does for customers.
Result: **+2 tasks over the same model with skills in the prompt, +3 over the
plain model**, and the second-highest score recorded on this suite (Sol with
web search holds 15/18). Run-to-run variance on this suite is roughly ±3 at
pass@1, so treat the deltas as directional until replicated.

Versus the same model's skills arm, the harness **gained**
`budget-reconciliation-trap`, `factorial-ad-test`, `launch-capacity-trap`,
and `unsupportable-claims-brief`, and **lost** `marketing-plan` (6/8
criteria) and `platform-limits-gauntlet` (9/10). `ad-creatives` and
`ad-performance-analysis` fail in both (the latter by one criterion in the
Magister arm).

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
  `unsupportable-claims-brief :: evidence_unlock`).

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
