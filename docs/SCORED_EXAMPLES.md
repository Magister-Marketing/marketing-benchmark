# Scored examples

[Back to the overview](../README.md) · [See all tasks](TASKS.md) ·
[How scoring works](SCORING.md)

These shortened examples come from a development run of August 20, 2026
(`20260820-234113-2b224909`: GPT-5.6 Luna at medium and at x-high effort).
Each model answered each task once, with the skills in the prompt and web
search off. The run was graded by Claude Sonnet 5 under the first judge
protocol, with the rubric versions of that day; the ad performance rubric has
changed since (version 2 then, 5 now). The examples show how the pass/fail
rule works. They are not from the board, whose answers and verdicts are on
https://marketingbenchmark.ai. The judge verdicts have not been
human-verified.

## Example 1: one subtle detail changes the result

Both models wrote strong 90-day marketing plans. The task required activation
rates to include only trials whose full 14-day activation window had ended.

| Submission | What it said | Result | Why |
|---|---|---:|---|
| Luna medium | “Activated trial workspaces divided by trial workspaces started” | **FAIL · 7/8** | The denominator included no rule for excluding newer, still-in-progress trials. |
| Luna x-high | “Report in-flight trials separately from matured 14-day cohorts” and exclude trials without the full observation window | **PASS · 8/8** | It clearly separated eligible trials from pending trials. |

The medium answer did almost everything else correctly. It still failed the
task because this measurement mistake can make a healthy activation rate look
worse simply because recent trials have not had time to activate.

## Example 2: a caveat does not repair mismatched arithmetic

Luna x-high's ad analysis passed 9 of 10 checks. It correctly noticed that one
week of Launch Teaser conversions was missing, but then calculated:

```text
$1,000 of spend from four weeks ÷ 7 conversions from three known weeks = $142.86 CPA
```

That mixes spend from four weeks with outcomes from only three. Calling the
number incomplete does not make the denominator valid. The answer should have
used spend and conversions from the same known weeks, or reported four-week
CPA as unavailable.

**Result: FAIL · 9/10.** This is why the checklist is diagnostic but not
partial credit.

## Example 3: a complete technical answer

Luna medium passed all 11 checks on the Shopify-to-Meta tracking task. Among
other requirements, it:

- used the same event name and event ID for the browser and server events;
- said to save and reuse the event ID when a webhook retries;
- normalized and SHA-256 hashed customer data before sending it; and
- used Meta's Test Events view to confirm the two events were deduplicated.

**Result: PASS · 11/11.** The answer did not merely mention Conversions API; it
made the details specific enough for a technical marketer to implement and
verify.

## What these examples show

The benchmark rewards exact, auditable work rather than length or polish by
itself. A near-perfect answer can fail one task-critical requirement, while a
shorter answer can pass when every requirement is correct and supported.

The generated HTML report carries this same evidence for every model and task:
the exact assignment, complete response, result, and the judge's explanation
for every check.
