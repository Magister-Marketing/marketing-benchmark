# Realistic journey pilot v1

This is a small development suite, not a production reliability estimate or a
leaderboard replacement. All names, messages, metrics and sites are invented.
The scenarios reflect common workflows: iterative drafting, correcting a site
assumption, reconciling incomplete reports, approved publishing, and delayed
follow-up. No customer conversation is copied into the suite.

The first three tasks can run through any adapter retaining chat context. The
last two require the supplied **simulated** tools. The controller, not the
candidate, grants approval and advances time. Only actual function calls change
the simulator ledger. Repeated calls use stable operation identities. There is
no network integration, live publishing, real scheduler, restart recovery or
notification transport under test. A day-14 wake-up is supplied by the runner;
passing does not prove a product will wake itself up fourteen days later.

Each attempt starts with fresh context. Future user turns and scoring criteria
are withheld. Every turn, tool receipt, failure and usage receipt is saved.
Approval/payload/exactly-once checks are deterministic; a separate judge grades
the whole transcript for factual accuracy and useful completion. Every check
and every turn must pass for a journey pass. Inspect failures manually before
turning them into product changes. Keep model/simulated-tool and product-native
scorecards separate. Compare latency and cost alongside success; two repetitions
only detect obvious instability, not small model differences.

Local commands (paid; never run in CI):

```sh
python -m eval_runner.journeys run --output /tmp/journeys-new-run \
  --models gpt-5.6-sol-high,gpt-5.6-luna-xhigh --repetitions 2 \
  --max-cost-usd 12 --env-file /path/to/private/provider.env
python -m eval_runner.journeys grade --run /tmp/journeys-new-run \
  --judge claude-sonnet-5 --env-file /path/to/private/provider.env
python -m eval_runner.calibration --output /tmp/rubric-v3-probes.jsonl \
  --judge claude-sonnet-5 --env-file /path/to/private/provider.env
```

The generation cap reserves input bytes plus maximum output tokens before each
call, using catalog prices without cache discounts. Actual invoices can differ;
reported costs are upper estimates from returned usage. Grading is separately
billed and not covered by the generation cap. Generation never retries silently.
Existing run directories and judgment files are refused, preserving history.
Journey grading retains returned usage even when the judge verdict is malformed,
marks costs unknown when a provider response is lost, and exits nonzero on
grading errors after recording the remaining attempts. A validly graded quality
failure is separate from a grading error; inspect each recorded pass result.

## Rubric corrections

Tracking-audit rubric v3 recognizes the fixture's malformed two-part organic
Pinterest campaign and unsupported Instagram source as legitimate findings.
Ad-performance rubric v3 permits objective-aware worst-campaign choices and a
multi-arm test varying one factor. The judge must check denominator claims in
all prose, including notes, while allowing examples explicitly rejected as
invalid. Task prompts and historical snapshots are unchanged. Compare old and
new responses under the same rubric; never interpret regrading alone as product
improvement. Keep this development suite separate from a future held-out set
with different synthetic brands, values, wording and correction order.

The small-budget reporting journey accepts replication/measurement pilots and
clearly labeled mathematical bounds; it does not require an underpowered A/B
test or forbid useful conditional arithmetic. Missing outcomes presented as
measured zeros, incompatible periods, unsupported causal claims and unbounded
recommendations still fail. Retain initial pilot grades when correcting these
rubric ambiguities, and report the changed grading separately from generation.

Ad-creatives rubric v4 applies evidence requirements to quantified competitor
comparisons and every field, while allowing clearly hypothetical visual staging
and test outcomes. This resolves inconsistent treatment of invented lamp-base
dimensions; it does not change the task or add a product-specific capability.

Tracking-audit rubric v6 removes a nonexistent `tiktok-retargeting` example from
the clean-item guidance and its calibration control. The supplied CSV contains
two `tiktok-prospecting` links. Previously recorded v5 calibration and grades
retain their original snapshots; this source correction has only offline
validation until a separately recorded paid run is performed.

No production deployment or migration is needed for these evaluation tools.

The follow-up [factual-grading protocol](judge-factuality.md) addresses false
passes found in the complete rerun responses. It versions all five affected
task rubrics and records judge-protocol provenance; earlier scores remain intact.
