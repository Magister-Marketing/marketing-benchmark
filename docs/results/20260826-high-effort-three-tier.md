# 2026-08-26 — High effort, three states: the harness stops adding score

> **Re-graded 2026-09-02** under the scoring shipped in
> [PR #11](https://github.com/Magister-Marketing/marketing-benchmark/pull/11)
> (oracle-backed critical criteria, judge `self_report`, `critical` read live,
> free-credit discount, negatives gated on a positive). Same judge, same
> recorded rubric snapshots, fresh judge sample for all three arms. Tables
> carry the re-graded numbers; the original grading is shown where a figure
> moved. Single-criterion flips between the two samples are judge variance
> on interpretive criteria, not a scoring-rule effect.

**Runs (18 tasks, pass@1, judge `claude-sonnet-5`, judge-b `gpt-5.6-terra-medium`):**

| Configuration | Run | GPT-5.6 Sol (high) | Score (0–100) | Claude Opus 5 (high) | Score (0–100) |
|---|---|---:|---:|---:|---:|
| Plain model + web search | `20260826-212341-34f65925` | 14/18 (was 13) | 96.7 | 12/18 | 95.6 |
| + marketingskills in the prompt | `20260826-212336-e68672f4` | 13/18 | 96.7 | 14/18 (was 13) | 97.1 |
| Magister harness (production agent) | `20260826-212643-62e39f5c` | 13/18 | 93.9 | 12/18 (was 13) | 94.2 |

108 attempts, **zero attempt errors and zero judge failures**. Judge agreement
97.1% (plain), 95.0% (skills), 95.3% (harness), all on 342 judge-scored
criteria per run (98.2% / 94.4% / 95.0% against the original sample).

Re-grade movement, all single judge criteria: plain Sol gained
`budget-reconciliation-trap`; skills Opus gained `factorial-ad-test`; the
harness Opus lost `launch-capacity-trap` (`auditable_arithmetic`, 8/9). 15
of 1,026 judge-scored criteria changed verdict across the three arms.

**The headline is parity — at best.** Where the first harness arm (terra at
medium effort, 2026-08-26 earlier) went 11 → 12 → 14 as published (10 → 12 →
12 on re-grade), both frontier models at high effort sit flat or slightly
behind through the harness: 14 / 13 / 13 for Sol and 12 / 14 / 12 for Opus
across plain / skills / harness, every gap inside the ±3 pass@1 noise. The
harness wins and loses different tasks rather than more of them, and its
0–100 score trails both direct arms by 2–3 points. Cost is the honest
separator — the harness bills every LLM call of
the agent's working turn, so the same 18 tasks cost **$13.23 vs $3.60 (Sol,
3.7×)** and **$24.89 vs $4.73 (Opus 5, 3.9×)**, at 98s and 128s per task
against 76s and 87s direct.

## What actually moved

Per-task flips against the plain arm (`<` lost, `>` gained):

| Model | + Skills | Magister |
|---|---|---|
| Sol high | < launch-capacity-trap | < shopify-meta-capi |
| Opus 5 high | > attribution-sensitivity, factorial-ad-test, landing-page-repair · < email-flow-repair | > attribution-sensitivity, factorial-ad-test · < landing-page, launch-capacity-trap |

(Re-graded flips. As published: Sol +Skills `> ad-performance-analysis,
budget-reconciliation-trap · < email-flow-repair, launch-capacity-trap`,
Magister `> budget-reconciliation-trap · < ad-performance-analysis,
shopify-meta-capi`; Opus +Skills `> attribution-sensitivity,
landing-page-repair · < factorial-ad-test`, Magister `> attribution-sensitivity,
email-flow-repair · < landing-page, landing-page-repair`.)

Two observations the score hides:

- **The harness passes `email-flow-repair` with Opus 5** (14/14; the skills
  arm misses one criterion, and on the re-grade the plain arm passes it
  too) — a task where the failure is a missed defect in supplied material,
  exactly what tool-assisted rework should catch.
- **`shopify-meta-capi` is where the harness loses Sol a task**, and not on
  correctness: the agent delivered a 2.4 KB draft guide where the direct arms
  wrote the full implementation spec (3/11 criteria, all of them "is this
  section present"). Agents summarize; the benchmark asks for the artifact.
  That is a real product finding, not a harness bug — the answer arrived in
  chat, well-formed, and short.

Most remaining failures are single-criterion misses (9/10, 13/14, 18/19), so
a ±1 movement here is one requirement, not a category difference. Run-to-run
variance on this suite is roughly ±3 at pass@1.

## Changes this run required

- **Claude candidates can carry an effort level.** `providers.py` sends
  Anthropic effort as `thinking: {type: adaptive}` + `output_config.effort` —
  the shape the Magister gateway sends — so a model can be asked for the same
  work in the direct and harness arms. `text_verbosity` stays OpenAI-only and
  `xhigh` is rejected rather than clamped (Anthropic's scale has no xhigh).
- **`claude-opus-5-high` raises its output ceiling to 32,000.** Anthropic
  requires `max_tokens` and adaptive thinking shares that budget; the model's
  longest answer here was 18,194 tokens, so the uniform 16,000 would have
  truncated real work. The manifest test now enforces the rule that was
  actually meant: a candidate may raise the ceiling, never lower it.
- **`cmd_eval` graded the wrong directory under concurrency.** It re-derived
  its run by diffing `results/` before and after, so a run started in
  parallel — a second `eval.py`, or the Magister bridge — was picked up
  instead, and grading died on a stranger's missing `attempts.jsonl`.
  `cmd_run` now records the directory it created.

Bridge-side (magister repo): `--candidate <bench model id>` reads the model,
effort, verbosity, ceiling **and pricing** out of `models.json`, so the
harness arm can never be priced with another model's rate card; `--into`
accepts a candidate the run has not seen, which is how both models landed in
one harness run with byte-identical prompts.

## Caveats / next

- One attempt per task. The parity finding deserves pass³ before it is
  treated as settled.
- Re-grade judge spend: $1.20 (plain), $1.79 (skills), $1.24 (harness).
- All verdicts judge-scored, 0 human-verified.
- The harness arm runs on one internal fixture project; machine-side
  variability (cold starts, mid-run recycles) is not modelled.
