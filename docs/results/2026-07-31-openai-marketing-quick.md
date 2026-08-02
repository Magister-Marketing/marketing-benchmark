# GPT-5.6 marketing quick screen

On July 31, 2026, Marketing Benchmark compared 11 GPT-5.6 model/effort
profiles on one synthetic Meta ad-review task. All 11 read the required skill,
used only the allowed files and tools, produced the required artifact and JSON
review UI, stayed grounded in the supplied facts, and passed every objective
copy check.

## Results at a glance

- **Creative quality leader:** Sol xhigh, with a 10–0–0 blind win/tie/loss
  record.
- **Fastest complete pass:** Terra high at 29.5 seconds.
- **Lowest-cost complete pass:** Luna high at an estimated $0.0063.
- **Total candidate-generation cost:** an estimated $1.1456. Judge cost is not
  included.

| Profile | Complete pass | Blind preference | W–T–L | Time | Est. cost |
|---|---:|---:|---:|---:|---:|
| Sol xhigh | 100% | 100% | 10–0–0 | 86.3s | $0.2099 |
| Sol max | 100% | 85% | 8–1–1 | 90.0s | $0.2266 |
| Sol medium | 100% | 75% | 7–1–2 | 60.3s | $0.1647 |
| Terra xhigh | 100% | 65% | 6–1–3 | 58.2s | $0.0871 |
| Luna xhigh | 100% | 45% | 4–1–5 | 44.5s | $0.0072 |
| Sol high | 100% | 45% | 3–3–4 | 75.9s | $0.2047 |
| Terra max | 100% | 40% | 3–2–5 | 82.5s | $0.1346 |
| Terra high | 100% | 30% | 2–2–6 | 29.5s | $0.0425 |
| Terra medium | 100% | 25% | 2–1–7 | 40.8s | $0.0512 |
| Luna max | 100% | 25% | 2–1–7 | 69.1s | $0.0110 |
| Luna high | 100% | 15% | 1–1–8 | 36.3s | $0.0063 |

Blind preference is the share of pairwise judge points; a tie contributes half
a point. Candidate identities were hidden during 55 head-to-head reviews by
one Claude Sonnet 5/high judge configuration with no tools. The Claude Code CLI
did not expose a temperature control. Candidate generation used the OpenAI
Responses API with medium text verbosity and temperature omitted; only model
tier and reasoning effort changed.

## What this suggests

For a paid-plan shortlist, **Terra xhigh** is the strongest value candidate in
this screen: it beat Sol high on creative quality while completing faster and
at less than half the estimated cost. **Sol medium** is the quality-leaning
alternative: it beat Terra xhigh directly, finished only about two seconds
slower, and cost about 1.9 times as much. Terra high is compelling for latency,
but this run does not support choosing it when creative quality is the primary
goal.

For the Luna tier, xhigh outperformed max in blind preference while also
finishing faster and costing less. That is a useful signal, not enough evidence
by itself to change a production default.

## What was tested

The task used the fictional Cedar & Coil Arc Clip Lamp fixture. Every profile
had to:

- read the `ad-creative` skill and all authoritative fixture files;
- write three genuinely different Meta concepts within copy limits;
- use the approved CTA and avoid unsupported claims;
- save a review artifact and emit structured JSON review UI; and
- remain draft-only, with no publishing, spending, or external writes.

Run ID: `20260731-232826-f63a21ca`. The experiment manifest is
[`evals/experiments/openai-marketing-quick.json`](../../evals/experiments/openai-marketing-quick.json),
and the scenario is
[`ads-creative-angle-review.json`](../../evals/suites/marketing/ads/creative-angle-review.json).

## Limits

This is an exploratory screen, not a production-routing decision:

- each profile ran once;
- only one synthetic ad task was tested;
- one judge made one decision per pair; and
- the benchmark did not measure live CTR, conversion, revenue, or tool-backed
  integration work.

Before changing a default, repeat the finalists at least three times across
ads, email, blog/SEO, website, and tool-backed analytics scenarios, then add a
second independent judge. Raw evidence should be published only after the
repository's privacy and provenance review is complete.
