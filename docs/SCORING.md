# How scoring works

[Back to the overview](../README.md) · [See all tasks](TASKS.md) ·
[See scored examples](SCORED_EXAMPLES.md) ·
[Simulated companies](SIMULATED_COMPANIES.md)

This page is the method behind the board at https://marketingbenchmark.ai and
behind every report the runner writes (`eval_runner/bench.py`). It describes
what the code does today.

## The score: tasks fully right

An attempt is **right** when it met every requirement in its task's brief. A
task **counts** for a run only when every attempt at it was right. The score
is the number of tasks that count.

The board of November 23, 2026 made one attempt per task on 35 tasks, so its
score is the number of the 35 tasks whose one answer met every requirement.
GPT-6.2 Sol inside Magister, for example, scored 32 of 35.

```text
answer -> program checks -> judge -> right or not -> tasks fully right
```

Every task weighs the same, whatever the number of requirements in its brief.

### The percentage

The only percentage shown beside a score is that count as a share of the
tasks: 32 of 35 is 91%. The runner's `report.md` prints it the same way, as
`32/35 (91%)`; `report.html` shows the count, `32/35`.

### Right on average

With more than one attempt per task there is a second, softer figure: per
task, the share of its attempts that were right, added up over the tasks. A
task right on two of three attempts adds two thirds. It is never below the
score, and with one attempt per task it equals the score. The runner's report
gives the count it rests on (`N/M individual runs passed`) whenever a run has
more than one attempt per task; the site prints right on average.

## How an answer is checked

Each task has a checklist of requirements (its rubric, in three sections:
completion, skill adherence and best practices). Each requirement is pass or
fail.

1. **Program checks come first.** A requirement with a `programmatic`
   condition is settled by code: facts are measured in the answer (counts,
   totals, character lengths, HTML structure, the figures in its answer block,
   the rows of a CSV file it returns) and compared with values computed from
   the task's own files. A figure can be checked inside a band: within the
   first tolerance it passes; between the two tolerances it fails and earns
   part credit for the checklist score below; past the second it scores zero.
2. **Then the judge, with evidence.** Every other requirement goes to a judge
   model. The judge receives the exact prompt the setup sent, the answer, the
   facts the program measured (with the instruction to trust them over its
   own counting) and, for data tasks, reference totals computed from the
   recorded input files, never from the answer. It is told to audit the whole
   answer, to fail a requirement the answer is silent or unclear about
   (except one that forbids something, which passes when the thing is
   absent), and that one counterexample fails any requirement about every
   claim. For each
   requirement it returns pass or fail and one sentence of evidence. It also
   says whether the answer delivered the task end to end (`completed`) and
   how the answer describes its own work (`complete`, `partial` or
   `blocked`).
3. **The oracle can overrule the judge.** A requirement marked critical names
   the banded program checks that prove it (`fails_if_zero`). When one of them
   scores zero, the figure is outside any plausible reading of the data, so
   the requirement fails whatever the judge said. A figure the answer never
   gave is an absence, not an invention, and does not trigger this.

An attempt is right when the judge says it was completed and every
requirement, program or judged, passed.

What the judge does not get: it is not told which model wrote the answer, and
it has no web search. It does see the exact prompt the setup sent, so for the
Magister setup it also sees the short preamble that setup adds.

Its reply is checked before it is used: every requirement exactly once and
nothing else. A malformed or incomplete reply is asked for again, up to four
tries in all. After the fourth, the attempt's grading is an error and the
attempt is not right.

The board was graded by `claude-sonnet-5-5` under judge protocol 4. The
runner's default judge is `claude-sonnet-5`; `--judge` picks another. How the
judge protocol grew: [whole-answer factual grading](judge-factuality.md).

## Run errors and truncated answers

Every attempt gets one mark in the report's grid:

| Mark | Meaning | Counts as |
|---|---|---|
| `P` | Right | Right |
| `F` | Not right | Failed |
| `A` | Not right, and the answer said plainly, with a reason, that it could not or would not deliver (`blocked`) | Failed |
| `T` | The model spent its whole output allowance (also shown for any other abnormal finish) | Failed, when the allowance ran out |
| `E` | Run error: the call itself failed (a transport failure, a provider error, a refused request, or in strict mode an untrusted route) | Failed |

- **Out of output (`T`).** When the provider reports that the call ended at
  the output allowance (`max_tokens` or `incomplete:max_output_tokens`), with
  or without partial text, the attempt failed, and no judgment can make it
  right. Its cost and time count like any other attempt's. In an ordinary
  run (not `--strict-attempts`), when the reply came back empty and cut off
  and the request carried a cap below the model's maximum, the runner first
  asks once more inside the same attempt with the cap doubled (never past the
  maximum `eval_runner/models.json` names for the model); only if that also
  runs out is the attempt marked `T`. `retry` never runs a `T` attempt
  again: it is the model's miss, not a fault of the run. The rule is applied whenever a report
  is written, so older run folders report the same way.
- **Run errors (`E`).** The attempt is not graded and counts as failed.
  `python -m eval_runner.bench retry --run <run folder>` runs only the errored
  attempts again, in place, with the run's recorded prompts and settings, and
  prints the command that grades the affected tasks again.
- **On the board:** four attempts were `T`, all Gemini 4 Neon's, two in each
  direct setup. There were no run errors.

## The checklist score: a diagnostic, not the score

The runner also computes a 0 to 100 average of each attempt's requirements,
`composite_score` in `report.json`. This page calls it the **checklist score**.
The runner's `report.md` heads that column "Score (0–100)" and puts it before
the task count; `report.html` prints it as "score N/100" under the task
count; the site calls it "requirements met". Whatever the label, it is not the
score and not the percentage.

It is a diagnostic because it gives part credit, and a benchmark of
marketing work should not. A task that misses one requirement of fourteen
still has a checklist score in the nineties, and it is still wrong work: the
task fails. Use the checklist score to see how near an answer came, never to
rank.

How it is computed:

- **Per attempt:** the mean of its requirement scores (1 or 0, or part credit
  on a banded figure), then these rules:
  - **Free credit is removed.** A program check that an empty answer would
    already pass is discounted by what the empty answer earns; one that an
    empty answer passes in full counts only when the answer breaks it.
  - **Negatives need a positive.** A requirement that forbids something ("no
    invented data") counts only once at least one positive requirement
    passed, or when the answer said it was blocked. A blank reply earns
    nothing.
  - **Capped at 40** when a critical requirement fails, or when the judge says
    the task was not delivered end to end.
  - **Zero** when a critical requirement fails on the oracle's evidence.
  - **Zero** when the attempt has no grading: a run error, a judge that failed
    four times, or an empty reply that ran out of output.
- **Per task:** the mean over its attempts. **Per run:** the mean over its
  tasks.

Why the two honesty rules: on 2026-09-02 the same model, on the same ledger
task, had a checklist score of 75.5 when it estimated all five figures wrong
and presented them as computed, and 0.0 when it said plainly that it could not
read the file and would not invent the numbers. Under these rules the invented
figures score 0, and the honest refusal keeps the one requirement it met (no
invented data, one of twelve). Neither changes whether the task is right: both
attempts failed.

Each task cell in the report also shows a fraction such as `7/8 checks`: the
requirements passed and judged over the attempts that finished normally.
Attempts that ran out of output are left out of that fraction, because their
failures measure a missing tail, not the work.

## False confidence

The report's Behavior table shows **false confidence**: the share of failed
attempts that the answer presented as complete. A failed attempt that said it
was blocked is marked `A` instead of `F`. Neither changes the score. Forecast
tasks (`"forecast": true`) are left out of this figure: a forecast with every
pick made is complete, and a pick that turned out wrong is a miss, not
unfinished work.

## More than one attempt

The default is one attempt per task, which the report heads `Pass@1`.
`--repetitions 3` asks for three independent attempts. They are not averaged
for the score: a task counts only when all three are right, so repeats test
reliability. The report then heads the column `Tasks passed (all 3 runs)` and
keeps every attempt, so the spread can be read.

## The three setups

The board runs each model three ways. The tasks, the files and the judge are
the same in all three.

| | Model only | + Marketing Skills | Inside Magister |
|---|---|---|---|
| What answers | The model, in one API call | The same call | Magister's agent on that model |
| Prompt | The task and its source files | The same, plus the task's listed SKILL.md files under `## Skill guidance you should follow` | The task and its source files, after a short preamble that marks the turn as an internal evaluation and forbids outside changes |
| Skills | None | In the prompt | Installed on the agent's machine; the agent decides what to open |
| Tools | None (the provider's tools are off) | None | Magister's own tools, over a multi-step turn |
| Calls | One (two for a task that sends an earlier message first) | The same | As many as the turn takes; tokens and cost are added up over all of them |
| Runner harness id | `direct-api` | `direct-api` | `magister-agent` |

The direct setups are run with this runner (`--no-skills` for model only). The
Magister setup is run from Magister's own repository on a test lane, an
isolated copy of the product, and its run folder is graded by this runner's
own `grade` and `report` commands with the same judge. How it is run, and
what makes a Magister attempt invalid:
[Magister integration](MAGISTER_INTEGRATION.md).

So the Magister column is the model, the skills and Magister's harness
together, not the model alone. Differences between the columns measure the
setups as wholes; this is not an equal-compute comparison.

Where the skill files come from: [skill provenance](../evals/fixtures/public/skills/README.md).

## Not human-verified

Every verdict on the board is the judge's, or the output-limit rule's. No
person has reviewed them. A judge can pass an answer that should fail and fail
one that should pass. The runner has a human review step
(`python -m eval_runner.bench verify --run <run folder>`) whose verdict, once
recorded, takes precedence over the judge's, and every report shows where
each verdict came from. It has not been used for this board. The judge's
calibration checks ([judge factuality](judge-factuality.md)) are development
checks, not proof that it catches every error.

## What a gap of a few tasks means with one attempt

A single task can come out right on one attempt and wrong on the next, for the
same model in the same setup. In a stored three-attempt development run of
August 25, 2026 (`20260825-040844-5ddf2d2c`), 10 of its 33 task-and-model
cells had both a right and a failed attempt.

So, with one attempt per task:

- The score says how many of these 35 tasks this model, in this setup, got
  fully right on this attempt, graded by this judge.
- A gap of a few tasks between two cells may not repeat on another attempt.
  Read it as within noise, not as a measured difference.
- A large gap that holds across all three models is stronger evidence, but it
  is still one attempt each, on 35 tasks.
- The stricter figure, every one of three attempts right, has not been run
  for this board.

## Development, holdout and the board

- **Development** tasks are open, and their answers are read to improve
  prompts and rubrics. They are useful evidence, not untouched test results.
- **Holdout** tasks are kept out of tuning. Once their answers have been read
  they are no longer untouched; [Tasks](TASKS.md) records which have been.
- **The board** (`--split board` on `python -m eval_runner.bench run` and
  `eval`) is 35 development tasks, five in each of seven areas, listed in
  `eval_runner/board.json` with the tasks held back and left out.

## Tokens, time and cost

The report keeps quality and efficiency apart:

| Measure | What it means |
|---|---|
| Output tokens (total) | Tokens the answering model produced across the run's tasks |
| Candidate cost (total) | Estimated cost of the answering model, from recorded usage and `eval_runner/models.json` prices |
| Avg task time | Mean time per attempt; attempts may run in parallel |

Judge tokens, cost and time are left out of these figures and reported
separately. Some reasoning models count hidden reasoning tokens as output. A
task that sends an earlier message first counts both turns' cost and time.
For the Magister setup, tokens and cost are summed over every model call in
the turn.

For exact data fields, retry behaviour and the file formats, see the
[direct-model runner reference](../eval_runner/README.md).
