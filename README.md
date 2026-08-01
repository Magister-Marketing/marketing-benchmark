# Marketing Benchmark

Marketing Benchmark is an evidence-first evaluation runner for marketing models
and tool-using agents. It measures whether an agent follows required skills,
uses tools correctly, produces valid UI and artifacts, grounds conclusions in
returned data, and creates strong marketing work across repeated trials.

> **Private staging project.** This repository is not currently open source and
> does not grant a redistribution license. It is being prepared for a reviewed
> public release.

## What is included

- Versioned candidate, scenario, experiment, rubric, and tool-trace schemas.
- Repeated randomized trials with immutable, redacted evidence.
- Deterministic hard gates kept separate from subjective quality judgments.
- Identity-blinded pairwise judging packets.
- Capability, error, cost, latency, and task-family routing reports.
- A credential-free replay MCP with invented GA4, Search Console, Ads,
  commerce, and CRM data.
- Synthetic creative packs for ads, lifecycle email, blog/SEO, and website
  copy/architecture work.
- Claude Code, direct OpenAI Responses API, and provider-neutral
  subprocess/JSONL adapters.
- Plugin contracts for private or third-party adapters and tool environments.

Validation, planning, grading, judging-packet generation, reporting, and
conformance checks do not call a model provider. Only `run` can create paid
model traffic, and it requires an adapter-specific confirmation token plus a
reviewed cost ceiling.

## Quick start

Marketing Benchmark requires Python 3.11 or newer.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

.venv/bin/marketing-benchmark validate
.venv/bin/marketing-benchmark conformance
.venv/bin/marketing-benchmark plan \
  --experiment evals/experiments/ga4-replay.json
```

Run one replay case through a locally authenticated Claude Code CLI:

```bash
.venv/bin/marketing-benchmark run \
  --experiment evals/experiments/ga4-replay.json \
  --adapter claude-code \
  --confirm RUN_LOCAL_CLAUDE_CODE_EVALS \
  --max-provider-cost-usd 5 \
  --candidate claude-sonnet-5-high \
  --scenario ga4-baseline-diagnosis \
  --repetitions 1
```

Claude Code generation bills the account to which the local `claude` CLI is
authenticated. Temporary workspaces and strict MCP configuration reduce
ambient access, but they are not an operating-system sandbox.

Compare the reviewed OpenAI Luna, Terra, and Sol profiles on the same compact
creative task by supplying `OPENAI_API_KEY` in the process environment:

```bash
OPENAI_API_KEY='<provider-key>' \
  .venv/bin/marketing-benchmark run \
  --experiment evals/experiments/openai-marketing-quick.json \
  --adapter openai-responses \
  --confirm RUN_LOCAL_OPENAI_EVALS \
  --max-provider-cost-usd 10.80
```

The key is never accepted as a command-line option or written to evidence.
Avoid putting it in shell history; prefer a secret manager or an already
configured, least-privilege environment. The experiment fixes text verbosity
at medium, omits temperature, and changes only model tier and reasoning effort.

The creative pack covers ads, email, blog/SEO, and website work. Start with a
single reviewed case before running its full repeated matrix:

```bash
marketing-benchmark plan \
  --experiment evals/experiments/marketing-creative.json \
  --scenario email-trial-activation-sequence \
  --candidate claude-sonnet-5-high \
  --repetitions 1

marketing-benchmark run \
  --experiment evals/experiments/marketing-creative.json \
  --adapter claude-code \
  --confirm RUN_LOCAL_CLAUDE_CODE_EVALS \
  --max-provider-cost-usd 5 \
  --scenario email-trial-activation-sequence \
  --candidate claude-sonnet-5-high \
  --repetitions 1
```

## Evaluate an agent in another repository

Install Marketing Benchmark, then scaffold its catalog into the target
repository:

```bash
marketing-benchmark init /path/to/your-repository
marketing-benchmark --repo-root /path/to/your-repository validate
```

The scaffold creates:

```text
evals/
├── candidates/
├── experiments/
├── fixtures/public/
├── rubrics/
├── schema/
└── suites/
```

Edit or add candidates, fixtures, skills, scenarios, and experiments there.
Every paid run writes immutable evidence under
`artifacts/evals/<run-id>/` in that repository.

Claude Code is available directly. Any other agent can implement the
`agent-eval-jsonl-v1` protocol and run through the generic adapter:

```bash
marketing-benchmark --repo-root /path/to/your-repository run \
  --experiment evals/experiments/ga4-replay.json \
  --adapter subprocess-jsonl \
  --subprocess-command './your-agent-adapter' \
  --confirm RUN_LOCAL_SUBPROCESS_EVALS \
  --max-provider-cost-usd 5
```

The command is operator configuration and is executed without a shell. It can
never be supplied by an experiment or scenario manifest.

## Grade, judge, and report

Generation and evaluation are separate, so the same evidence can be regraded
without another provider call:

```bash
marketing-benchmark grade --run <run-id>
marketing-benchmark judge-plan --run <run-id>

# Give only artifacts/evals/<run-id>/judge/pairs.jsonl to a judge.
marketing-benchmark judge-import \
  --run <run-id> \
  --results <blinded-results.jsonl> \
  --judge-id <stable-lowercase-id>

marketing-benchmark report --run <run-id>
marketing-benchmark public-report --run <run-id>
```

Reports include:

- `report.md` and `report.json`
- `public-report.md` and `public-report.json`, a plain-language leaderboard
- `routing.json`
- `capability-matrix.json`
- `error-matrix.json`

The public report puts pass/fail validity, blind preference, elapsed time, and
estimated provider cost in one table, then states the sample size and limits in
plain language. It is a scan-friendly companion to the auditable technical
report, not a replacement for its traces and gate-level evidence.

See the first dogfood result: [GPT-5.6 marketing quick screen](docs/results/2026-07-31-openai-marketing-quick.md).

Replay and live evidence are never pooled. Routing recommendations are decision
support; the runner does not change a production model default automatically.

## Repository commands

```bash
make validate     # manifests and plans; no provider calls
make conformance  # adapter/environment structural checks
make test         # offline unit and contract tests
make build        # wheel and source distribution
make check        # all of the above
```

## Architecture and extensions

The portable core owns schemas, planning, evidence, replay environments,
grading, judging, and reports. Product-specific identity, credentials, live
tools, and deployment controls belong in downstream plugins.

- [Architecture](docs/ARCHITECTURE.md)
- [Plugin SDK](evals/open_source/PLUGIN_SDK.md)
- [Security model](evals/open_source/SECURITY.md)
- [Using the runner from Magister](docs/MAGISTER_INTEGRATION.md)
- [Public-release checklist](evals/open_source/OPEN_SOURCE_CHECKLIST.md)

## Public-release status

The software is functional, but publication remains gated on an approved
license, security contact, provenance review, package/namespace review,
governance documents, and release approval. Do not publish this package or
change the repository visibility until those items are complete.
