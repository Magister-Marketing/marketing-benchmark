# Repeated general-chat, skill/UI, and integration baselines

On August 1, 2026, Marketing Benchmark ran a compact three-cell protocol three
times through vanilla Claude Code and Codex CLI. Both systems executed all nine
attempts. Codex passed all nine end to end; Claude Code passed eight and did not
finish one GA4 artifact.

These are **separate baseline profiles**, not a causal head-to-head comparison.
They use different underlying models and settings. A Magister uplift claim
requires a later matched run with the same model, settings, fixtures, hashes,
seed, clock, and environment on both sides.

## Results at a glance

| System | Execution | End to end | General chat | Skill use | UI rendering | GA4 replay |
|---|---:|---:|---:|---:|---:|---:|
| Claude Code · Sonnet 5 high | 100% (9/9) | 89% (8/9) | 100% (3/3) | 100% (6/6) | 100% (3/3) | 67% (2/3) |
| Codex CLI · GPT-5.6 Terra xhigh | 100% (9/9) | 100% (9/9) | 100% (3/3) | 100% (6/6) | 100% (3/3) | 100% (3/3) |

All evidence is thin. The 95% Wilson intervals are 70.1–100% for 9/9,
56.5–98.0% for 8/9, 61.0–100% for 6/6, 43.8–100% for 3/3, and 20.8–93.9%
for 2/3. The table therefore describes these attempts; it does not establish a
stable provider ranking.

Each score answers a different question:

- **Execution:** did the runtime return gradeable evidence?
- **End to end:** did the attempt pass every required gate and objective check?
- **General chat:** was the answer grounded, safe, honest, and compliant with
  the requested decision format?
- **Skill use:** were all required skills actually read before dependent work?
- **UI rendering:** was a non-empty payload submitted and valid against the
  declared UI contract?
- **GA4 replay:** did the agent use the synthetic read-only tool correctly,
  reach a grounded diagnosis, and avoid forbidden side effects?

Category scores remain separate from end-to-end completion so a skill read or
valid UI cannot hide an unrelated task failure. In this run, Codex passed both
the category gates and every end-to-end requirement in all three creative
attempts.

## Time and cost by task

| System | Eval cell | End to end | Mean time | Generation cost |
|---|---|---:|---:|---:|
| Claude Code · Sonnet 5 high | General chat | 3/3 | 39.4s | $0.4731 reported |
| Claude Code · Sonnet 5 high | Skill + UI | 3/3 | 153.2s | $1.5643 reported |
| Claude Code · Sonnet 5 high | GA4 replay | 2/3 | 124.5s | $1.4240 reported |
| Codex CLI · GPT-5.6 Terra xhigh | General chat | 3/3 | 19.9s | $0.0724 estimated |
| Codex CLI · GPT-5.6 Terra xhigh | Skill + UI | 3/3 | 170.2s | $0.4998 estimated |
| Codex CLI · GPT-5.6 Terra xhigh | GA4 replay | 3/3 | 118.7s | $0.4789 estimated |

Across all nine attempts, mean completion time was 105.7 seconds for Claude
Code and 103.0 seconds for Codex CLI. Claude Code reported $3.4614 of generation
cost; Codex cost was locally estimated at $1.0512 from token usage and public
rates. Those accounting methods differ, so the cost columns are operational
context—not an exact savings claim. Judge cost is not included.

## Observed failure

- Claude Code's third GA4 attempt read the analytics skill and called the
  synthetic tools, but spent its turn budget on repeated drilldowns and never
  wrote the required diagnosis. It failed artifact, grounded-output, and honest
  terminal-state gates.

No external campaign, analytics property, or user data was touched. The GA4
tool was a deterministic, invented replay service with network access disabled.

## Settings

| System | Model | Reasoning | Text verbosity | Temperature | Output limit |
|---|---|---|---|---|---|
| Claude Code | `claude-sonnet-5` | high, translated to a 16,384-token thinking budget | not exposed; omitted | not exposed; omitted | 12,000 |
| Codex CLI | `gpt-5.6-terra` | xhigh | medium | omitted | provider default |

The Claude Code CLI and Codex CLI are part of each baseline system. This screen
does not isolate model quality from their instruction layers, skill loading,
tool interfaces, or runtime behavior.

## Grader corrections found by dogfooding

Manual audit found three general false-negative patterns in the deterministic
grader: a bold copy label and character annotation on their own line; a
two-column copy table whose annotations were counted as copy while a separate
three-column guardrail table was mistaken for copy; and a careful GA4 caveat
that contained the phrase “caused the decline” inside an explicit negation.
The parsers were corrected with regression tests, and the same corrected grader
was applied to every scored run. Only the missing Claude artifact remained a
failure.

Adapter-development runs were not counted as model results. Excluded Claude
runs `20260801-222626-3ed76334`, `20260801-223212-67e90497`, and
`20260801-223612-17fd623d` exposed fixture-manifest and portable-UI bridge
defects. Codex run `20260801-231033-8519bf10` exposed path and replay-MCP
normalization defects; single-attempt runs `20260801-230611-51228b52`,
`20260801-232337-b09a3f45`, `20260801-232735-b10ab472`, and
`20260801-232934-1e6bcbb8` were repair smokes and were not pooled.

## Auditable run IDs

- Claude general chat: `20260801-225228-f1a43795`
- Claude skill/UI: `20260801-223758-4241fd88`
- Claude GA4 replay: `20260801-225654-40f91436`
- Codex combined protocol: `20260801-233150-12b8e744`

The scored tasks were `chat-channel-prioritization`,
`ads-creative-angle-review`, and `ga4-baseline-diagnosis`. Raw artifacts,
normalized traces, settings evidence, deterministic grades, scorecards, and
technical/public reports remain under each local `artifacts/evals/<run-id>/`
directory and are excluded from source control.

## What comes next

There is no blind preference result in this baseline report. Once Magister PR
#890 is available only on Team+Test, run the same Terra xhigh profile through
the private Magister adapter, export sanitized evidence, and use
`marketing-benchmark compare` to enforce parity. Reliability deltas are scored
for every matched pair; only pairs where both systems passed end to end enter
identity-blinded quality review. Repeat across more scenarios before changing a
production default.

This benchmark measures synthetic task performance, not real CTR, conversion,
revenue, search ranking, or campaign lift.
