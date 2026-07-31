# Marketing Benchmark release candidate

Marketing Benchmark evaluates models and tool-using agents with versioned
manifests, repeated randomized trials, immutable evidence, deterministic hard
gates, blinded pairwise review packets, and capability/task-family reports.
It includes credential-free replay MCP fixtures, a Claude Code adapter, and a
generic subprocess/JSONL adapter.

No provider call occurs during validation, planning, grading, judging-packet
generation, reporting, conformance, or replay-server tests. A generation run
is paid and requires an adapter-specific confirmation plus a reviewed cost cap.

```bash
marketing-benchmark validate
marketing-benchmark conformance
marketing-benchmark plan --experiment evals/experiments/ga4-replay.json
```

To run one Claude Code replay attempt, review the plan and ensure the local CLI
is authenticated:

```bash
marketing-benchmark run \
  --experiment evals/experiments/ga4-replay.json \
  --adapter claude-code \
  --confirm RUN_LOCAL_CLAUDE_CODE_EVALS \
  --max-provider-cost-usd 5 \
  --candidate claude-sonnet-5-high \
  --scenario ga4-baseline-diagnosis \
  --repetitions 1
```

Fixtures are invented and use no vendor credentials. The hidden oracle is
added to grader evidence only after the agent returns; it is never staged into
the agent workspace or MCP resources.

Temporary workspaces and strict MCP configuration are isolation layers, not an
operating-system sandbox. Follow `SECURITY.md` when testing an untrusted agent
or when strict oracle isolation is required.

This private repository is a technical release candidate, not a publication
grant. An approved license, security contact, provenance review, and release
approval are still required before changing its visibility.
