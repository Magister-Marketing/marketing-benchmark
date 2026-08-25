<p align="center">
  <a href="https://magistermarketing.com">
    <img src="docs/assets/magister-mark.svg" width="64" alt="Magister logo">
  </a>
</p>

<h1 align="center">Magister Marketing Evals</h1>

<p align="center">
  A clear, inspectable way to compare how well AI models handle real marketing work.
</p>

## Latest results

Live board: **https://marketingbenchmark.ai** — every run, every answer, and
every judge verdict, criterion by criterion. The six-model run of
August 25, 2026 (18 tasks, one attempt each, skills on, web search off):

| Model | Pass@1 | Answer cost | Avg. task time |
|---|---:|---:|---:|
| Claude Opus 5 | **15/18 (83%)** | $3.02 | 93.5s |
| GPT-5.6 Terra medium | 13/18 (72%) | $0.66 | 35.0s |
| GPT-5.6 Sol medium | 13/18 (72%) | $1.81 | 48.4s |
| GPT-5.6 Luna medium | 12/18 (67%) | $0.06 | 22.3s |
| Claude Sonnet 5 | 9/18 (50%) | $1.03 | 66.9s |
| Claude Haiku 4.5 | 4/18 (22%) | $0.26 | 24.5s |

Each task is worth one point: an answer that passes 7 of 8 checks still fails
that task. Tokens and cost cover the model answering the tasks, not the
judge. A same-day identical-input repeat moved individual scores by up to 3
tasks, so read single pass@1 boards as ±3. These judge verdicts have not been
human-verified yet.

### The skills arm uses Magister's real skill pack

When skills are on (the default), each task's prompt carries the relevant
**verbatim SKILL.md files from
[marketingskills](https://github.com/coreyhaines31/marketingskills)**, the
open marketing skill pack by Corey Haines, co-founder of Magister — the same
files, at the same pinned commit, that ship on every Magister agent machine.
`--no-skills` drops those blocks and changes nothing else, which is what
makes the skills-vs-no-skills comparison a clean ablation. Provenance and
the exact pin: [`evals/fixtures/public/skills/README.md`](evals/fixtures/public/skills/README.md).

## Start here

| Guide | What it explains |
|---|---|
| **1. [Tasks](docs/TASKS.md)** | What the models are asked to do and the difference between development and holdout tasks. |
| **2. [How it is scored](docs/SCORING.md)** | How an answer becomes a pass or fail, how repeats work, and what the efficiency numbers mean. |
| **3. [Scored examples](docs/SCORED_EXAMPLES.md)** | Real answers from the run above, what the judge noticed, and why each example passed or failed. |

## What this benchmark does

For every task, the runner:

1. gives each model the same assignment, source material, and optional
   marketing guidance;
2. checks exact requirements locally and uses an independent AI judge for
   requirements that need interpretation; and
3. creates an HTML report where every score can be traced back to the task,
   answer, and judge explanation.

The main score is intentionally simple: **tasks passed ÷ tasks attempted**.

## Run it yourself

You need Python 3.11 or newer and an API key for the models you want to run.
The default judge also needs an Anthropic API key.

```bash
git clone https://github.com/Magister-Marketing/marketing-benchmark.git
cd marketing-benchmark
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env.local
```

Add your API keys to `.env.local`, then run one model on one task:

```bash
./eval.py claude-haiku-4-5 --tasks headline --env-file .env.local
```

The runner shows the number of paid API calls before it starts. When it
finishes, it prints the location of the results. Open `report.html` for the
shareable report.

To reproduce the latest run shown above:

```bash
./eval.py gpt-5.6-luna-medium gpt-5.6-luna-xhigh \
  --tasks marketing-plan,shopify-meta-capi,ad-performance-analysis \
  --repetitions 1 --judge claude-sonnet-5 \
  --env-file .env.local
```

## Eval options

| Option | Meaning |
|---|---|
| `--tasks headline,blog-post` | Run only the named tasks. Without this, every task is selected. |
| `--split development` | Run tasks used for improving and checking the benchmark. |
| `--split holdout` | Run the untouched final-test tasks. |
| `--repetitions 3` | Ask for three answers per model and task. All three must pass. The default is one. |
| `--no-skills` | Leave the marketingskills guidance out of the prompt (see the skills provenance note above). |
| `--tools` | Allow the answering model to use provider-hosted web search. |
| `--judge MODEL` | Choose the model that grades requirements needing interpretation. |
| `--env-file PATH` | Load API keys from a local file. |
| `-y` or `--yes` | Skip the paid-call confirmation. |

Every run stores its exact prompts, answers, judgments, configuration, and
HTML, Markdown, and JSON reports under `eval_runner/results/<run-id>/`. This
folder is ignored by Git unless a reviewed result is deliberately published.

## More detail

- [Direct-model runner reference](eval_runner/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Agent and tool-use runner](evals/open_source/README.md)
- [Security model](evals/open_source/SECURITY.md)

---

Built by [Magister Marketing](https://magistermarketing.com).

> **Private staging project.** This repository is not currently open source
> and does not grant a redistribution license.
