# 2026-08-31 — High-effort three-tier rerun: the harness separates

**Runs (20 tasks, one attempt each, judge `claude-sonnet-5`, zero judge
failures in all three arms):**

| Configuration | Run | Score (0–100) | Tasks passed |
|---|---|---:|---:|
| Magister harness (production agent) | `20260831-212016-af4c8df1` | **97.4** | **16/20** |
| Plain model + web search | `20260831-212031-c6d4636d` | 96.8 | 14/20 |
| + marketingskills in the prompt | `20260831-212036-e234131f` | 96.6 | 14/20 |

Same model everywhere: GPT-5.6 Sol, high reasoning effort, medium verbosity.
This is the first run where the harness beats both direct configurations —
the 08-26 high-effort board was parity (13/13/13 on the then-18 tasks). It is
also the first featured board on the 0–100 composite score (one decimal),
which replaced tasks-passed as the headline number; passing stays
all-or-nothing per task.

## What changed since the parity run

- **The 20-task set** now includes `ads-ledger-analysis` and
  `tracking-audit` (scoring v2's hard tasks).
- **The under-delivery class is gone.** `shopify-meta-capi` — which the
  08-26 harness lost by delivering a 2.4 KB draft where the direct arms wrote
  the full spec — passed 11/11 through the harness (the direct+skills arm
  failed it 10/11). The subagent foreground-delivery fix (#1559) closed it,
  and the earlier 8-repetition ledger run measured non-delivery at 0/8.
- **The machines run the session-stable skill-hints image** (openclaw
  `7e26abcd`): the `<available_skills>` block no longer flaps per turn, so
  agent turns rode a warm prompt cache throughout (97.6% of input tokens
  cached within warm sessions during this run).

## Where the harness won and lost

Wins against both direct arms: `ad-performance-analysis` (90.0 → 100),
`source-conflict-repair` (94.4 → 100), plus `shopify-meta-capi` against the
skills arm. Losses: `ads-ledger-analysis` (91.7 — the known one-dropped-row
arithmetic slip: the agent sums the 784-row CSV by pure reasoning instead of
using its exec tool, `web_search_calls=0`, byte-identical across reruns) and
`launch-capacity-trap` (88.9, shared with the skills arm). `ad-creatives`
(77.8) and `unsupportable-claims-brief` (90.0) fail identically in all three
arms — task-side difficulty, not configuration signal.

## Skills-in-prompt is a wash at high effort (second replication)

Both direct arms landed 14/20, and only 6 of 222 shared criteria flipped —
three each way. The wins are practitioner-structure criteria (test design,
adset isolation, factor isolation); the losses are attention slips (shortened
product name, feasibility-framed recommendation, `event_time` defaulting to
send time). At high reasoning effort the model already practices most of what
the skill text teaches; at medium effort (08-25) skills were worth +2 to +3
per model. Skills raise the floor of cheaper configurations, not the ceiling
of a frontier model thinking hard — the delta that matters is
harness-over-skills, not skills-over-plain.

## Cost

| Arm | List-price answer cost | Avg task time |
|---|---:|---:|
| Plain | $5.11 | 123.3s |
| + skills | $5.71 | 95.4s |
| Magister | $23.10 | 104.8s |

Judges: $2.40 across the three arms. The harness's list-price figure values
every token at the rate card; the provider actually billed ~$15.72 for the
arm because ~5 calls/task × ~75k-token prompts are almost entirely cached
reads (the run-level cache read rate, 59.6%, understates warm-session
behavior only because the bridge creates and deletes a fresh session per
task). The harness is ~3× the direct arms per task, structural to
multi-step agency.

## Caveats / next

- One attempt per task; historical same-day repeats have moved pass counts
  by up to 3 tasks. The +2 margin deserves a pass³ replication before being
  treated as settled.
- All verdicts judge-scored; zero human-verified.
- Two transient stream errors during the harness pass (`ad-creatives`,
  `launch-capacity-trap`) were re-run cleanly with `--into`; both then
  completed (one passed, one failed on its merits).
- Open lever: push the agent toward exec-tool arithmetic for row-level data
  — it is the only harness-specific loss left on the board.
