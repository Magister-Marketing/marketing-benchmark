# Full 11-task run: Luna, Terra, Sol at medium — first holdout results

Run `20260825-040844-5ddf2d2c` · direct-api harness · 11 tasks (7 development +
4 holdout) · pass³ (3 attempts per task) · skills on · tools off · judge
claude-sonnet-5. 99/99 attempts completed normally, 99/99 judged, 0 judge
failures, 0 truncations. This is the first run over the rubric-v2/v3 task set
where all four holdout tasks were exercised; per the protocol, they are now
inspected and rotate into development.

Live report: https://marketingbenchmark.ai/runs/20260825-040844-5ddf2d2c

## Headline

| Configuration | Tasks passed | Development | Holdout | Attempts passed | Cost | Avg task time | Output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-5.6-sol-medium | **8/11 (73%)** | 6/7 | 2/4 | 26/33 | $3.88 | 55.0s | 125.5k |
| gpt-5.6-terra-medium | **5/11 (45%)** | 4/7 | 1/4 | 23/33 | $1.34 | 33.8s | 107.9k |
| gpt-5.6-luna-medium | **4/11 (36%)** | 4/7 | 0/4 | 17/33 | $0.12 | 38.9s | 94.9k |

The ordering is monotonic with model tier on both splits, and the holdout
tasks — never used to tune rubric v2 — separate hardest. The saturation that
motivated the rubric hardening is gone: the same three configurations scored
6/7, 7/7, 6/7 under rubric v1 five days ago.

## Where the separation came from

- **Oracle math (attribution-sensitivity):** Luna mis-assigned order O-002's
  last touch and reported Meta $480/0.80 ROAS where the oracle is $400/0.67 —
  a checkable, unambiguous fail. Terra and Sol reconciled both models
  correctly on all three attempts, including the duplicate order and the
  refund retention.
- **Constraint density (factorial-ad-test):** Luna and Terra each broke factor
  isolation (changing visual format across appeals instead of holding it
  constant); Sol held all constants on all three attempts.
- **Reliability, not ability (source-conflict-repair):** every model caught
  all 12 planted claims in every attempt — grounding is a solved behavior at
  this tier. But 7 of 9 attempts wrote a test hypothesis without an observable
  KPI (`operational_hypothesis`), and Terra and Sol each passed it only once.
  Under pass³ the task fails for everyone; the per-attempt grid shows it is a
  consistency failure, which is exactly what pass³ is for.
- **The universal skill gap is hypothesis operationalization.** The two
  biggest criterion failures — `hypothesis_prediction` on ad-creatives (9/9
  attempts) and `operational_hypothesis` on source-conflict-repair (7/9) —
  are the same behavior: predictions phrased as "will resonate more" with no
  metric, direction, or comparator. This is consistent with the v2
  calibration and reads as a true model limitation at medium effort, not
  judge noise.

## What saturated (rotation candidates)

- **landing-page-repair: 57/57 criteria for every model.** All planted
  factual/safety/proof/action/structure defects were repaired by all models on
  all attempts. Repair with an explicit defect taxonomy appears easier than
  fresh generation for frontier models. Retire or harden (subtler defects, no
  defect-category hints in the prompt).
- **blog-post, headline, landing-page** remain near-ceiling as in
  calibration (one Terra headline attempt failed `distinct_appeals`).

## Instrument health

- 0 provider errors, 0 truncations (OpenAI requests uncapped), 0 judge JSON
  failures across 99 gradings.
- Criterion evidence on failures is quotable and specific in every sampled
  case; no judge flip-flops of the rubric-v1 kind were observed on the
  checkable criteria.
- Still missing: judge token/cost accounting, second cross-family judge
  agreement rate, human verification (0/99 verified).

## Protocol consequence

The four holdout tasks are now inspected and move to the development split.
Before the next untouched-generalization claim, author replacement holdouts
(candidates: a subtler repair task without defect-category hints, a
budget-reconciliation trap with an infeasible constraint to catch, a
multi-source analytics conflict).
