# Scoring v2 pilot — two hard tasks, three tiers, gpt-5.6-sol-medium

**Date:** 2026-08-27 · **Runs:** plain `20260827-014657-a656de1b` /
`20260827-015441-c29e75ca`, skills `20260827-014659-45db0d35` /
`20260827-015442-c4d7464f`, magister `20260827-014910-b4ef29d0`

First live test of 0–100 task scoring (mean criterion score, critical-gate cap
at 40, banded `near` credit on numeric answers) on the two new
headroom-seeking tasks, run pass@1 on one mid-tier model across all three
configurations.

## Scores

| task | plain | + skills | Magister |
|---|---:|---:|---:|
| ads-ledger-analysis | 91.7 | 100.0 | **0.0** |
| tracking-audit (fixed fixture) | 100.0 | 100.0 | 100.0 |
| **composite** | **95.9** | **100.0** | **50.0** |

Answer cost for the two tasks: ~$1.29 per direct arm; **$15.16** for the
Magister arm (all-in agent-turn token bill).

## What the pilot proved

1. **The 0–100 scale expresses real differences pass@1 could not.** A single
   task now spans 0 → 91.7 → 100 across configurations, and each gap is
   attributable to a concrete behavior, not judge noise.
2. **The Magister ledger 0.0 is a real product finding, third sighting of the
   under-delivery class.** The agent worked 462s / 5,716 output tokens —
   almost certainly computing the right numbers in its sandbox — then ended
   its turn (`end_turn`, healthy stream) with a 169-byte status line: *"I'm
   running a deterministic ledger pass now…"* and never posted the review.
   The same product delivered an 18KB audit report on the other task, so
   this is turn-ending behavior, not a transport or pipeline defect.
   (Predecessors: `shopify-meta-capi` 2.4KB draft in the 2026-08-26 run.)
3. **The critical gate works — it caught a fixture bug on its first outing.**
   Both direct arms flagged the ca-storefront links' `-ca` campaign suffix as
   nonconforming, and they were right: the standards doc never documented the
   market suffix the rubric declared clean. Fixed in the standards doc
   (`f0dd2cb`); on the corrected fixture both direct arms score 100 with zero
   false accusations.
4. **sol-medium is stronger than the tasks' core mechanics.** It summed the
   784-row CSV to the cent by pure reasoning (no code tool: Q2/Q4/Q5 exact,
   Q1 off 0.32%) and recalled 12/12 seeded audit defects. Frontier-tier
   discrimination on these tasks currently comes from deliverable
   completeness, adset-level depth (`pb_video_flagged` is what separates
   91.7 from 100), and false-positive discipline — not from the arithmetic
   or the defect recall.

## Calibration verdict and next steps

- Keep both tasks; they will spread the full model ladder (weaker models will
  miss defects and mangle sums) even though sol-tier aces the mechanics.
- To discriminate *among* frontier models, the data must defeat in-context
  arithmetic: 10–50× more rows (attached file rather than inlined), required
  dedup/joins across tables, or messier semantics. Subtler audit defects
  (cross-file-only) for recall spread.
- pass@1 caveat: every number here is n=1. The ledger 0.0 needs repetition
  before quoting a rate; the artifact evidence is unambiguous for this
  attempt.
- Bridge fix shipped en route (magister-marketing PR #1552, `a7345bedf`):
  the committed bridge passed a stale `idle_timeout` kwarg that main's
  `e2e_support.run_agent_trace` no longer accepts; every attempt errored
  instantly. Also: standalone bridge launches must export the
  Makefile-owned `CANARY_EMAILS` cohort or the Team+Test doctor fails
  `canary_membership`.
