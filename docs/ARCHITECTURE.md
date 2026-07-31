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
 report + routing + capability/error matrices
```

## Portable core

`evals/runner/` owns manifest loading, randomized planning, lifecycle control,
setting evidence, normalized events, grading, judging, statistics, and reports.
It has no gateway, database, deployment, or product-identity dependency.

`evals/plugins/` contains reference integrations:

- `replay_mcp` provisions an attempt-owned MCP process backed by invented data
  and keeps the oracle hidden until generation finishes.
- `subprocess_jsonl` runs an operator-selected command through the
  `agent-eval-jsonl-v1` protocol without a shell.

The Claude Code adapter is a reference agent host. Product-specific hosts can
implement the same adapter contract.

## Trust boundaries

- Manifests select only registered plugin IDs; they cannot import code or name
  shell commands, credentials, users, projects, or live endpoints.
- Tool arguments/results are redacted and bounded, with hashes retained for
  correlation.
- Unknown operations fail closed as external writes.
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
