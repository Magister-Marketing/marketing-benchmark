# Marketing Benchmark release candidate

Marketing Benchmark evaluates models and tool-using agents with versioned
manifests, repeated randomized trials, immutable evidence, deterministic hard
gates, blinded pairwise review packets, and capability/task-family reports.
It includes credential-free replay MCP fixtures, Claude Code and Codex CLI
adapters, direct OpenAI Responses support, and a generic subprocess/JSONL
adapter.

This describes the agent-system engine in `evals/` and the `marketing-benchmark`
command. The board at https://marketingbenchmark.ai is made by a different
runner in the same repository, `eval_runner/` (`./eval.py` and
`python -m eval_runner.bench`), which the repository's main README and
`docs/SCORING.md` describe.

No provider call occurs during validation, planning, grading, judging-packet
generation, reporting, conformance, or replay-server tests. A generation run
is paid and requires an adapter-specific confirmation plus a reviewed cost cap.

```bash
marketing-benchmark validate
marketing-benchmark conformance
marketing-benchmark plan --experiment evals/experiments/ga4-replay.json
```

Reports keep execution and end-to-end reliability separate from general chat,
skill use, UI rendering, integrations, blind preference, time, and cost. The
offline `compare` workflow can join matched vanilla and product-harness runs,
withhold scores when controls differ, and produce treatment-minus-baseline
uplift by evaluation type.

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
