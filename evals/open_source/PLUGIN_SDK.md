# Plugin SDK contract

The core has four extension points: agent adapters, integration environments,
deterministic scorers, and UI validators. Manifests reference registered stable
IDs; they never import code.

An agent adapter declares supported binding kinds and provider-setting
capabilities, preflights its target, executes one attempt, emits normalized
events plus requested/translated/applied setting evidence, and performs
idempotent cleanup. A tool environment describes itself without credentials,
preflights scenarios, provisions one attempt-scoped handle, exposes the hidden
oracle only after execution, snapshots a redacted ledger, and resets and closes
safely.

Trusted packages may expose factories through the reserved Python entry-point
groups `marketing_benchmark.adapters` and
`marketing_benchmark.environments`. Automatic discovery is not enabled by the
stock CLI yet; a trusted host such as Magister must call
`evals.runner.plugins.discover_entry_points` explicitly. A scenario cannot
trigger discovery.

The subprocess reference adapter uses `agent-eval-jsonl-v1`: it writes one
request object to stdin, reads zero or more
`{"type":"event","event":...}` lines, then exactly one
`{"type":"result",...}` line. The process must exit zero and the result must
include the exact `actual_model` plus a terminal status (`completed`,
`contaminated`, or `infrastructure_error`). Otherwise the attempt is
quarantined or failed. It should also report translated/applied/unobservable
settings, usage, cost, and timings. Bindings are attempt-scoped and must not be
persisted.

Use `evals.runner.conformance` to check adapter/environment surfaces, setting
and binding declarations, normalized traces, and cleanup evidence. Structural
conformance does not certify a plugin's security or semantic correctness;
fixture-specific tests remain required.
