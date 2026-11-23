# Realistic journey pilot v1

[Back to the overview](../README.md) · [How scoring works](SCORING.md)

A development suite of September 2026, run by `python -m eval_runner.journeys`.
It is separate from the board: nothing here feeds the board's score.

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

## Journey grading protocol 3

Conversation grading has its own protocol version (3). Each journey judgment
also records the single-answer judge protocol it builds on
(`base_judge_protocol_version`), which is 4 today. It requires an ordered audit
of every response, checks budget pacing and full decision conditions across
current deliverables, and permits lower budgets, requested revisions and
explicitly superseded history. The native worksheet scenario requires verified
current file contents at each turn; a reused link is sufficient when the adapter
rereads the file. It is not part of the direct simulated-tool runner.

Incomplete turns, failed native capture, missing required files and mismatched
content hashes are **ineligible evidence**, not model quality failures. They
receive no paid judge call. Generation errors and costs remain in the original
attempt. Grading errors also remain distinct from valid quality failures.

The judge has an explicit 8192-token output ceiling. Empty or truncated replies
are retained with their usage, finish reason and raw output, without a hidden
ceiling retry. Do not replace old judgment files or compare grades across these
protocols as evidence of product improvement. Freeze the evaluator sources,
model settings, scenarios and runtime before a new baseline/comparison.

Eight synthetic development controls exercise an earlier budget contradiction
followed by a correct final answer, a missing minimum-count rule in a current
file, unsupported causality, mixed periods, valid lower spending, a reused
worksheet, an explicit user-requested plan revision and superseded history. Offline tests verify protocol and
evidence handling; a paid calibration tests actual judge behavior:

```sh
python -m eval_runner.journey_calibration --output /tmp/journey-v3-calibration.jsonl \
  --judge claude-sonnet-5 --env-file /path/to/private/provider.env
```

Calibration is a release check, not proof that the judge finds every error.
Review actual answers and file contents alongside scores, cost and latency.
No product deployment or migrations are required for these evaluator changes.
