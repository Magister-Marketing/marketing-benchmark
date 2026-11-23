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
every judge verdict, criterion by criterion. The board of November 23, 2026:
three models at medium reasoning effort, the same 35 tasks (`--split board`),
one attempt each, in three setups. The number is tasks fully right: a task
counts only when the answer met every requirement in its brief. The judge is
Claude Sonnet 5.5 (`claude-sonnet-5-5`). The only percentage shown beside a
score is that count as a share of the 35 tasks: 32 of 35 is 91%.

| Model | Model only | + Marketing Skills | Inside Magister |
|---|---:|---:|---:|
| GPT-6.2 Sol | 19/35 | 24/35 | 32/35 |
| Claude Opus 5.5 | 20/35 | 26/35 | 32/35 |
| Gemini 4 Neon | 25/35 | 25/35 | 33/35 |

What to hold in mind when reading it:

- "Model only" and "+ Marketing Skills" are one API call with no tools. The
  Magister agent works a full multi-step turn with tools (it runs code and
  opens skills), so that column is the model, the skills and the harness
  together, not the model alone.
- One attempt per task. Single tasks flip between attempts, so read a gap of
  a few tasks as within noise. The stricter figure, right on every one of
  three attempts, has not been run for this board.
- The Magister runs were made on test lanes, not production, with a harness
  that starts every attempt from a clean brand: an attempt that saw anything
  from an earlier attempt is recorded as an error, never a score.
- On two tasks Gemini 4 Neon spent its whole output allowance before
  answering, in both direct setups. Those attempts count as failed.
- These judge verdicts have not been human-verified. How an answer becomes a
  pass or a fail is in [How it is scored](docs/SCORING.md).

### The skills arm uses Magister's real skill pack

When skills are on (the default), each task's prompt carries the relevant
**verbatim SKILL.md files from
[marketingskills](https://github.com/coreyhaines31/marketingskills)**, the
open marketing skill pack by Corey Haines, co-founder of Magister: copied
unchanged at the commit Magister's agent machines ran on 2026-11-20.
`--no-skills` drops those blocks and changes nothing else, which is what
makes the skills-vs-no-skills comparison a clean ablation. Provenance and
the exact pin: [`evals/fixtures/public/skills/README.md`](evals/fixtures/public/skills/README.md).

## Start here

| Guide | What it explains |
|---|---|
| **1. [Tasks](docs/TASKS.md)** | The board's 35 tasks in seven areas: what each asks for and what makes it hard, and the tasks held back or left out. |
| **2. [How it is scored](docs/SCORING.md)** | How an answer is checked, what makes it right, the score and its percentage, how errors and cut-off answers count, and the three setups. |
| **3. [Simulated companies](docs/SIMULATED_COMPANIES.md)** | A newer kind of task, not on the board yet: a model works inside an invented company, and code checks the company afterwards. |
| **4. [Magister integration](docs/MAGISTER_INTEGRATION.md)** | How the Magister setup is run: on a test lane, every attempt from a clean brand. |
| **5. [Scored examples](docs/SCORED_EXAMPLES.md)** | Three answers from a development run of August 20, 2026, and why each passed or failed. |

## What this benchmark does

For every task, the runner:

1. gives each model the same assignment, source material, and optional
   marketing guidance;
2. checks exact requirements locally and uses an independent AI judge for
   requirements that need interpretation; and
3. creates an HTML report where every score can be traced back to the task,
   answer, and judge explanation.

The score is simple: **the number of tasks fully right**. Its percentage is
that number as a share of the tasks.

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

The direct harness supports Anthropic, OpenAI, and OpenRouter candidates.
Every OpenRouter request pins zero-data-retention, denies data collection, and
restricts routing to the candidate's allowlisted endpoints.

The runner shows the number of paid API calls before it starts. When it
finishes, it prints the location of the results. Open `report.html` for the
shareable report.

To run one model's two direct setups as the board of November 23, 2026 ran
them (the 35 board tasks, medium effort, provider tools off, one attempt,
judged by `claude-sonnet-5-5`):

```bash
# + Marketing Skills, then model only: each runs, grades and writes its report
./eval.py gpt-6.2-sol-medium --split board --judge claude-sonnet-5-5 --env-file .env.local
./eval.py gpt-6.2-sol-medium --split board --no-skills --judge claude-sonnet-5-5 --env-file .env.local
```

The board's other two models are `claude-opus-5-5-medium` and
`gemini-4-neon-medium`. The same steps one at a time, for a run you want to
grade later or again: `python -m eval_runner.bench run --models <id> --split
board`, then `grade --run <run folder> --judge claude-sonnet-5-5`, then
`report --run <run folder>`.

The Magister setup runs the same tasks through Magister's agent on a test
lane (an isolated copy of the product, not production), from Magister's own
private repository, so it cannot be reproduced from this repository alone.
Its prompts, answers and verdicts are published on the board like every
other setup's. How it is run:
[Magister integration](docs/MAGISTER_INTEGRATION.md).

### Agent arms

`eval.py` asks a model one question. To give the same tasks to an agent with
a shell, files and web search, run them through Claude Code
(`python -m eval_runner.claude_code run`), with or without a skills plugin or
MCP servers attached. Setup, what each attempt is given, and how to compare
runs are in the [runner reference](eval_runner/README.md#the-claude-code-harness).

### Benchmark a new model and put it on the site

When a model comes out, one command runs it on the board at
https://marketingbenchmark.ai, grades it with the board's judge, adds it to
the site's data, and drafts a post for X. It needs a checkout of the site
([marketing-benchmark-web](https://github.com/Magister-Marketing/marketing-benchmark-web))
and Python 3.11 or newer (`PYTHON=.venv/bin/python`).

The board is the one the site's home page charts: `src/lib/current-meta.ts`
in the site's checkout names it, today `20261120-first-board`, and its
`data/experiments/<board>/meta.json` sets every setting. A run is made as the
board of November 23, 2026 was: its 35 tasks (`--split board`, which must
list the same tasks as the site), provider tools off, the board's judge
(`claude-sonnet-5-5`), and one attempt per task unless `reps=` says
otherwise. The model must be at the board's effort: its id ends in
`-medium`.

Which setups one invocation makes:

| Switches | Setups | What runs |
|---|---|---|
| (none) | + Marketing Skills | `./eval.py <model> --split board --repetitions 1 --judge claude-sonnet-5-5 -y` |
| `plain=1` | Model only, then + Marketing Skills | the same, first with `--no-skills` |
| `inside=1 magister=<checkout> [lane=bench]` | Inside Magister | that checkout's `make lane-bench lane=<lane> deploy=0 candidate=<model> tasks=<the board's 35> repetitions=1 judge=claude-sonnet-5-5` |

`inside=1` runs the Magister setup alone and refuses `plain=1`; run the
direct setups as a second invocation.

```bash
# 1. See the plan and the cost estimate; spends nothing
make bench-model model=gpt-6-luna-medium web=../marketing-benchmark-web dry_run=1

# 2. Run it with the Marketing Skills: one call per task (two for a task that sends an earlier message first)
make bench-model model=gpt-6-luna-medium web=../marketing-benchmark-web \
    env_file=.env.local confirm=SPEND

# also as the model only, or three attempts per task
make bench-model model=gpt-6-luna-medium web=... plain=1 reps=3 env_file=... confirm=SPEND

# 3. Check every claim on the site against the new data, then commit it there
cd ../marketing-benchmark-web && pnpm build
```

What it does:

- **Refuses before spending** a model that is not in
  `eval_runner/models.json` (and says what an entry needs: `model`,
  `pricing`, and `reasoning_effort` for an effort variant; add it, run
  `python -m eval_runner.bench validate`, then rerun), a model not at the
  board's effort, a model the board already has in a setup it would run (take
  the old run out first if the new one replaces it), and a runner whose
  `eval_runner/board.json` lists other tasks than the site's board.
- **Prints an estimate before spending**: the last comparable run's recorded
  cost (the newest run on the board in the same setup that is on disk, or
  `like=<run folder>`), scaled by how the model's list prices compare with
  that run's model's over the same tokens, plus that run's judge cost. Nothing
  runs without `confirm=SPEND`.
- **Runs, grades and reports** each setup with the commands above.
- **Exports each graded run to the site**: `report.json` copied unchanged to
  `data/runs/<run id>.json`; the run added to the board's `meta.json` `runs`
  in the shape the site reads (`run_id`, `setup`, `judge_model`,
  `judge_protocol_version`, and for a Magister run `ran_on`, the test lane
  and Gateway revision it ran on); and the model added to its `models`, so
  the board gives it a row. A run the site would refuse is refused first,
  with the reason, and no file changes: one graded by another judge, one made
  with the provider's tools on, one missing a board task or titling one
  otherwise than the site's `data/task-blurbs.json`, one with an attempt lost
  to a run error (run `python -m eval_runner.bench retry --run <run folder>`,
  grade the tasks it names, report, then export), one from a harness that is
  none of the board's setups, a Magister run not made on a test lane, and a
  second run of a model in one setup. An attempt that ran out of output is
  not refused: the board counts it failed.
- **Writes `tweet.txt` next to the run**: under 280 characters, every number
  read from the site's data as the board reads it. It leads with tasks fully
  right, never the checklist average: "Claude Opus 5.5 (medium effort) got 26
  of 35 marketing tasks fully right on the Marketing Benchmark with the
  Marketing Skills, 20 without, 32 inside Magister." Then the rank by tasks
  fully right among the board's runs in that setup, ties said as ties ("Tied
  #2 of 3 models inside Magister"), the attempts per task ("One attempt per
  task."), the other models in the setup as they fit, and the run's page,
  `/runs/<run id>` (a model on this board has no `/models/` page). A draft
  that runs long drops the words "on the Marketing Benchmark", then the
  effort, then the rank. Every other run on the board that is on disk gets
  its draft rewritten too, since a new run moves their ranks; it finds them
  in this checkout's results, sibling checkouts' and any folder in
  `BENCH_RESULTS_DIRS`, and lists the runs it could not find.

`make bench-model export=<run folder> web=...` does the export and the draft
alone, for a run already graded; it spends nothing.

**Inside Magister.** `inside=1` hands the run to Magister's private
repository, as the board's Magister runs were made: that checkout's
`make lane-bench` runs the board's tasks through the Magister agent on a test
lane, every attempt in a fresh session, grades the run with this runner and
the board's judge, and leaves the run folder here; `bench-model` then exports
it with the test lane and Gateway revision it ran on. It passes `deploy=0`,
so `lane-bench` measures the lane as it runs now: bring the lane up on the
Magister build to publish first. The model must be in Magister's own model
catalog on that build: `lane-bench` enables it in the lane's catalog and
stops if the lane's Gateway does not know it.

## Eval options

The options of `./eval.py` (`./eval.py --help` lists them):

| Option | Meaning |
|---|---|
| `--tasks headline,blog-post` | Run only the named tasks. Without this, every task is selected. |
| `--split development` | Run tasks used for improving and checking the benchmark. |
| `--split holdout` | Run the tasks kept out of tuning. [docs/TASKS.md](docs/TASKS.md) records which of them have had results read. |
| `--split board` | Run the open board: seven areas of marketing, five tasks each, as listed in [eval_runner/board.json](eval_runner/board.json) with the tasks held back and left out. |
| `--repetitions 3` | Ask for three answers per model and task. All three must be right for the task to count. The default is one. |
| `--no-skills` | Leave the marketingskills guidance out of the prompt (see the skills provenance note above). |
| `--tools` | Allow the answering model to use provider-hosted web search. The board's direct setups ran without it. |
| `--judge MODEL` | Choose the judge, the model that grades the requirements a program cannot check. The default is `claude-sonnet-5`; the board used `claude-sonnet-5-5`. |
| `--judge-b MODEL` | Also grade with a second judge and report how often the two agree (paid). |
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
