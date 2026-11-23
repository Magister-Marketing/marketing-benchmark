# Architecture

[Back to the overview](../README.md) · [How scoring works](SCORING.md) ·
[Magister integration](MAGISTER_INTEGRATION.md)

Marketing Benchmark separates generation from evaluation so expensive model
output is captured once and can be graded, judged, and reported repeatedly.

The repository holds two engines:

- **The runner** in `eval_runner/`, which makes the board at
  https://marketingbenchmark.ai. Its tasks are answered from supplied files
  and graded by program checks and a judge model.
- **The agent-system engine** in `evals/`, which runs tool-using agents
  against replayed integrations and compares two agent systems. It is not
  used for the board.

## The runner (`eval_runner/`)

```text
eval_runner/tasks/*.json + fixtures + skill files      (board.json picks the board's 35)
              |
              v
  run      one answer per task and attempt              -> prompts/, responses/, attempts.jsonl, run.json, tasks/
              |
              v
  grade    program checks, then the judge, then the oracle  -> judgments.jsonl, grading.json
              |
              v
  report   tasks fully right, checklist score, cost, time    -> report.md, report.html, report.json
```

- `python -m eval_runner.bench run`, `grade` and `report` are the three steps;
  `eval` (and `./eval.py`) runs all three. Each run is a folder under
  `eval_runner/results/<run-id>/`, which Git ignores unless a reviewed result
  is published on purpose. The folder snapshots the exact tasks and prompts
  it used, so it can be graded again later without the task files changing
  under it.
- The run step calls the provider directly (`eval_runner/providers.py`):
  Anthropic, OpenAI or OpenRouter. Its harness id is `direct-api`. The two
  direct setups on the board, model only and + Marketing Skills, are this
  step with and without `--no-skills`.
- Other harnesses write a run folder in the same format, and the same `grade`
  and `report` steps score it: the Claude Code harness in this repository
  (`python -m eval_runner.claude_code run`, harness id `claude-code`) and the
  bridge in Magister's private repository (harness id `magister-agent`),
  which made the board's Magister column. How that bridge runs:
  [Magister integration](MAGISTER_INTEGRATION.md).
- The results site reads each run's `report.json`.
- How an answer is checked and how the score is counted:
  [How it is scored](SCORING.md).

## The agent-system engine (`evals/`)

```text
candidate + scenario + experiment
              |
              v
     adapter + environment
              |
              v
 immutable redacted evidence
              |
              +--> deterministic hard gates
              +--> blinded pairwise packets
              +--> UI/artifact validation
              |
              v
 report + per-evaluation scorecards + routing/error matrices
```

Two independently generated `agent_system` runs can be joined later by the
offline comparison layer. It validates model/settings/task/environment parity,
pairs the same scenario and repetition, keeps replay and live blocks separate,
and computes treatment-minus-baseline reliability, capability, time, and cost
deltas. Only pairs where both systems pass end-to-end can enter cross-run blind
quality judging.

### Portable core

`evals/runner/` owns manifest loading, randomized planning, lifecycle control,
setting evidence, normalized events, grading, judging, statistics, and reports.
It has no gateway, database, deployment, or product-identity dependency.

`evals/plugins/` contains reference integrations:

- `replay_mcp` provisions an attempt-owned MCP process backed by invented data
  and keeps the oracle hidden until generation finishes.
- `subprocess_jsonl` runs an operator-selected command through the
  `agent-eval-jsonl-v1` protocol without a shell.

Claude Code and Codex CLI are reference agent hosts. Both run in attempt-owned
workspaces and can attach only the attempt-owned replay MCP. Claude Code uses a
strict MCP configuration and disables hooks; Codex additionally ignores user
configuration and repository rules. The direct OpenAI Responses adapter stages
only declared fixtures and skills, exposes attempt-scoped read, write, and UI
functions, and keeps provider credentials out of manifests and evidence.
Product-specific hosts can implement the same adapter contract.

### Trust boundaries

- Manifests select only registered plugin IDs; they cannot import code or name
  shell commands, credentials, users, projects, or live endpoints.
- Tool arguments/results are redacted and bounded, with hashes retained for
  correlation.
- Unknown operations fail closed as external writes.
- Direct provider credentials come only from the operator environment. They
  cannot be supplied by candidates, scenarios, experiments, or CLI flags.
- The hidden oracle is not mounted into an agent workspace.
- Every adapter/environment must perform idempotent cleanup after success,
  failure, cancellation, and timeout.
- Replay and live evidence are never combined in comparative statistics.

### Extension model

Trusted hosts construct registries of agent adapters, environments, scorers,
and UI validators. Installed plugin discovery remains an explicit host action;
scenario data cannot enable it.

Structural conformance verifies method surfaces and declared capabilities. It
does not establish semantic correctness or isolation, so every plugin also
needs fixture-specific and adversarial tests.
