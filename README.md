# Magister Marketing Evals

An evidence-first eval runner for marketing models and agents. It runs real
marketing tasks, checks objective requirements locally, uses an LLM judge for
semantic quality, and produces shareable HTML, Markdown, and JSON reports.

> **Private staging project.** This repository is not currently open source
> and does not grant a redistribution license.

## Run your first eval

You need Python 3.11 or newer and an Anthropic API key. Add an OpenAI key when
evaluating GPT models.

### 1. Install

```bash
git clone https://github.com/Magister-Marketing/marketing-benchmark.git
cd marketing-benchmark
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env.local
```

Add your keys to `.env.local`. The file is gitignored. Keys are read only for
provider calls and are never written to run evidence.

### 2. Validate the catalog

This is offline and makes no provider calls:

```bash
python -m eval_runner.bench validate
```

### 3. Run one model on one task

```bash
./eval.py claude-haiku-4-5 --tasks headline --env-file .env.local
```

The command shows the number of candidate calls and asks for confirmation.
Grading adds one judge call for each completed candidate response. It then:

1. generates one candidate response;
2. grades it with the default judge; and
3. writes `report.html`, `report.md`, and `report.json`.

The result directory is printed when the run finishes. Open the HTML report:

```bash
open eval_runner/results/<run-id>/report.html
```

Skills are included, web tools are off, and each task runs once by default.
That default protocol is **Pass@1**.

## Compare two models

This is the three-task command used for the example below. It requires both
`OPENAI_API_KEY` for the candidates and `ANTHROPIC_API_KEY` for the default
judge.

```bash
./eval.py gpt-5.6-luna-medium gpt-5.6-luna-xhigh \
  --tasks marketing-plan,shopify-meta-capi,ad-performance-analysis \
  --env-file .env.local
```

### Example result

This development smoke run made six candidate calls: one response from each
model on each of three tasks.

| Model | Pass@1 | Output tokens | Candidate cost | Avg task time |
|---|---:|---:|---:|---:|
| Luna medium | **1/3 (33%)** | 12,102 | $0.0150 | 38.6s |
| Luna xhigh | **2/3 (67%)** | 57,900 | $0.0699 | 163.4s |

| Task | Luna medium | Luna xhigh |
|---|---:|---:|
| Marketing plan | FAIL · 7/8 | PASS · 8/8 |
| Shopify CAPI | PASS · 11/11 | PASS · 11/11 |
| Ad analysis | FAIL · 8/10 | FAIL · 9/10 |

The binary task result drives the score. Fractions such as `7/8` explain how
many rubric requirements passed; they are not partial credit. Token and cost
figures cover candidate generation only, while task time is the average
candidate-call latency. Judge usage is excluded. These verdicts have not been
human-verified, so this is implementation evidence rather than a published
model ranking.

More recorded examples:

- [Rubric-v2 calibration across 105 submissions](docs/results/20260820-rubric-v2-calibration.md)
- [GPT-5.6 marketing quick screen](docs/results/2026-07-31-openai-marketing-quick.md)
- [Repeated agent baselines](docs/results/2026-08-01-repeated-agent-baselines.md)

## How scoring works

- Every selected model receives the same task prompt, fixtures, and skill
  guidance.
- Objective requirements—counts, exact values, document structure, and other
  mechanically knowable facts—are checked locally.
- The tool-less LLM judge evaluates the remaining semantic criteria against
  the exact recorded prompt and response.
- A task passes only when every local check and judge criterion passes.
- The overall score is passed tasks divided by selected tasks.
- With `--repetitions N`, every configured response must pass for the task to
  pass. The default is one.

See the [direct-model runner reference](eval_runner/README.md) for task design,
skill injection, judging, human verification, and rubric-version rules.

## Useful commands

These examples assume keys are already exported. Append
`--env-file .env.local` to an `eval.py` command when using the template.

```bash
# Compare models across every task
./eval.py gpt-5.6-luna-medium gpt-5.6-luna-xhigh

# Run only development tasks or untouched holdouts
./eval.py claude-sonnet-5 --split development
./eval.py claude-sonnet-5 --split holdout

# Explicitly require three successful responses per model/task
./eval.py claude-sonnet-5 --tasks headline --repetitions 3

# Remove skill guidance for a baseline arm
./eval.py claude-haiku-4-5 --tasks headline --no-skills

# Enable provider-hosted web search
./eval.py claude-sonnet-5 --tasks blog-post --tools
```

Run stages separately when you want to regrade saved responses without paying
for generation again:

```bash
python -m eval_runner.bench run --models claude-haiku-4-5 --tasks headline
python -m eval_runner.bench grade --run eval_runner/results/<run-id>
python -m eval_runner.bench verify --run eval_runner/results/<run-id>
python -m eval_runner.bench report --run eval_runner/results/<run-id>
```

Each run keeps the exact prompts, task snapshots, raw responses, judgments,
configuration, and reports under `eval_runner/results/<run-id>/`. Results are
gitignored by default.

## Agent and tool-use evals

The `direct-api` harness above is the simplest path for comparing raw models.
The portable `marketing-benchmark` engine also supports Claude Code, Codex,
OpenAI Responses, replay MCP environments, blinded pairwise judging, and
third-party adapters.

Start with its offline plan:

```bash
.venv/bin/marketing-benchmark validate
.venv/bin/marketing-benchmark conformance
.venv/bin/marketing-benchmark plan \
  --experiment evals/experiments/ga4-replay.json
```

Paid agent runs require an adapter-specific confirmation and an explicit cost
ceiling. See the [agent-runner guide](evals/open_source/README.md),
[architecture](docs/ARCHITECTURE.md), and
[plugin SDK](evals/open_source/PLUGIN_SDK.md).

## Development

```bash
python -m pip install -e '.[dev]'
make validate     # catalog validation; offline
make conformance  # adapter and environment contracts
make test         # unit and contract tests
make build        # wheel and source distribution
make check        # all of the above
```

Additional references:

- [Security model](evals/open_source/SECURITY.md)
- [Using the runner from Magister](docs/MAGISTER_INTEGRATION.md)
- [Public-release checklist](evals/open_source/OPEN_SOURCE_CHECKLIST.md)

Publication remains gated on an approved license, security contact,
provenance review, package review, governance documents, and release approval.
