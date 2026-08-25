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

This small development run gave each model one chance at the same three tasks.
It was run on August 20, 2026, with Magister's marketing skills included and
web search turned off.

| Model | Overall score | Marketing plan | Shopify tracking | Ad analysis | Output tokens | Answer cost | Avg. task time |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Luna medium | **1/3 (33%)** | FAIL · 7/8 checks | PASS · 11/11 checks | FAIL · 8/10 checks | 12,102 | $0.0150 | 38.6s |
| GPT-5.6 Luna x-high | **2/3 (67%)** | PASS · 8/8 checks | PASS · 11/11 checks | FAIL · 9/10 checks | 57,900 | $0.0699 | 163.4s |

Each task is worth one point. An answer that passes 7 of 8 checks still fails
that task; the fraction simply shows how close it came. Tokens and cost cover
the model answering the tasks, not the judge. These judge verdicts have not
been human-verified, so this is a development check rather than a public model
ranking.

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
| `--no-skills` | Leave Magister's marketing guidance out of the prompt. |
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
phase3 acceptance 0825a
