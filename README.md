# Marketing Benchmark

Marketing Benchmark is an evidence-first evaluation runner for marketing models
and tool-using agents. It measures whether an agent follows required skills,
uses tools correctly, produces valid UI and artifacts, grounds conclusions in
returned data, and creates strong marketing work across repeated trials.

> **Private staging project.** This repository is not currently open source and
> does not grant a redistribution license. It is being prepared for a reviewed
> public release.

## Start here: the MVP eval

For model-level marketing quality without agents, tools, or sandboxes, use
the small direct-API runner in [`mvp/`](mvp/README.md). It calls models with
default API settings, applies deterministic hard checks plus a binary judge
rubric (completion, skill adherence, best practices), supports human
verification, and defaults to one run per task (pass@1). A larger run count is
an explicit `--repetitions N` choice. Seven development tasks support rubric
calibration; four untouched holdout tasks test whether that calibration
generalizes. Each run produces a detailed Markdown report plus a polished,
self-contained HTML leaderboard for viewing, printing, or capturing.

```bash
python3 -m mvp.bench validate
python3 -m mvp.bench run --models claude-haiku-4-5,claude-sonnet-5
python3 -m mvp.bench grade  --run mvp/results/<run-id>
python3 -m mvp.bench verify --run mvp/results/<run-id>
python3 -m mvp.bench report --run mvp/results/<run-id>
```

The full evidence-first runner below remains the path for tool-using agent
comparisons.

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
- Claude Code, Codex CLI, direct OpenAI Responses API, and provider-neutral
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

Run the same frozen general-chat, skill/UI, and GA4 replay protocol through a
clean, locally authenticated Codex CLI:

```bash
.venv/bin/marketing-benchmark run \
  --experiment evals/experiments/codex-agent-system-repeated.json \
  --adapter codex-cli \
  --confirm RUN_LOCAL_CODEX_EVALS \
  --max-provider-cost-usd 7.20 \
  --candidate codex-terra-xhigh
```

The Codex adapter uses non-interactive, ephemeral execution, ignores ambient
user configuration and repository rules, disables web search, and attaches
only the experiment-owned replay MCP. Model-generated shell commands inherit a
trimmed environment with Codex's default KEY/SECRET/TOKEN exclusions. Its
output-token setting is explicitly recorded as the Codex/provider default
because the CLI does not expose a documented override.

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

## Grade, compare, judge, and report

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

For a harness comparison, generate the baseline and treatment as separate runs
with `comparison_mode: agent_system`, the same model settings, scenario hashes,
repetition keys, seed, and replay environment. Then join the sanitized evidence
offline:

```bash
marketing-benchmark compare \
  --baseline-run <vanilla-run-id-or-path> \
  --treatment-run <harness-run-id-or-path> \
  --declaration evals/treatments/magister-vs-vanilla.example.json

marketing-benchmark compare-judge-plan \
  --comparison <comparison-id> \
  --baseline-run <vanilla-run-id-or-path> \
  --treatment-run <harness-run-id-or-path>

# Give only artifacts/comparisons/<comparison-id>/judge/pairs.jsonl to a judge.
marketing-benchmark compare-judge-import \
  --comparison <comparison-id> \
  --results <blinded-results.jsonl> \
  --judge-id <stable-lowercase-id>
```

The comparison fails closed and withholds uplift scores when a control differs
or a completed attempt cannot prove that its requested settings were applied.
The treatment declaration makes the intended harness differences visible.
Only matched pairs where both systems passed end-to-end enter blind quality
review; one-sided failures remain deterministic reliability wins or losses.

Reports include:

- `report.md` and `report.json`
- `public-report.md` and `public-report.json`, a plain-language leaderboard
- `routing.json`
- `capability-matrix.json`
- `error-matrix.json`
- `scorecards.json`, with planned-attempt scores for general chat, skill use,
  UI rendering, and integrations

The public report puts pass/fail validity, blind preference, elapsed time, and
estimated provider cost in one table, then states the sample size and limits in
plain language. It is a scan-friendly companion to the auditable technical
report, not a replacement for its traces and gate-level evidence.

Scores are intentionally separate instead of being collapsed into an opaque
overall number:

- **Execution** is the share of planned attempts that completed with gradeable
  evidence.
- **End-to-end** is the share of planned attempts that passed all required
  gates and objective checks.
- **General chat**, **skill use**, **UI rendering**, and **integrations** use the
  deterministic gates assigned to that evaluation type. Missing,
  infrastructure-error, and contaminated attempts count as failures.
- Category scores are macro-averaged across scenarios so a large scenario does
  not dominate a smaller one. Reports show passes/planned counts, 95% Wilson
  intervals in technical evidence, and a thin-evidence warning below ten
  attempts.

Dogfood results:

- [Repeated general-chat, skill/UI, and integration baselines](docs/results/2026-08-01-repeated-agent-baselines.md)
- [GPT-5.6 marketing quick screen](docs/results/2026-07-31-openai-marketing-quick.md)

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
