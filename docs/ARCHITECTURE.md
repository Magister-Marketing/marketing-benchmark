# Architecture

Marketing Benchmark separates generation from evaluation so expensive model
output is captured once and can be graded, judged, and reported repeatedly.

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

## Portable core

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

## Trust boundaries

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

## Extension model

Trusted hosts construct registries of agent adapters, environments, scorers,
and UI validators. Installed plugin discovery remains an explicit host action;
scenario data cannot enable it.

Structural conformance verifies method surfaces and declared capabilities. It
does not establish semantic correctness or isolation, so every plugin also
needs fixture-specific and adversarial tests.
