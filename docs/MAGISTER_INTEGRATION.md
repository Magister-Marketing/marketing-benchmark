# Magister integration

[Back to the overview](../README.md) · [How scoring works](SCORING.md) ·
[Architecture](ARCHITECTURE.md)

How the "Inside Magister" setup on the board is run today, what makes one of
its attempts invalid, and what lives in this repository and what in
Magister's.

## How the Magister setup is run

The Magister setup is run from Magister's own repository, which is private,
not from this one. A bridge there gives this repository's tasks to Magister's
agent and writes the results as a run folder in this runner's format. This
runner's own `grade` and `report` commands then score that folder with the
same rubrics and the same judge as the direct setups.

- **On a test lane, not production.** A test lane is an isolated copy of the
  product (its own database, server and agent machines) for one branch of
  Magister's code. The board's three Magister runs were made on test lanes,
  and the site records which lane and which server revision each ran on.
- **The candidate model.** The brand on the lane is set to the candidate
  model and effort, and the usage of every model call is checked against
  them.
- **What the agent receives.** The task's prompt and its source files, after
  a short preamble that marks the turn as an internal evaluation and forbids
  any outside change. No skill files are put in the prompt: the agent's
  machine has the marketing skills pack installed, and the agent decides
  which to open. The exact prompt is saved in the run folder, so the site
  shows what the agent received.
- **What it does.** One chat turn per attempt, worked the way the product
  works it: many model calls, Magister's own tools and skills. Its tokens and
  cost are added up over every model call in the turn.
- **A task with an earlier message** gets that message as an earlier chat
  turn in the same session, before the request. That turn is not graded,
  but its cost and time are counted with the task's.

## Every attempt starts from a clean brand

A new chat is not enough on its own. Magister remembers: it summarises earlier
chats and carries the newest summaries into new ones, and it learns lessons
from a brand's chats into the brand's memory. Left alone, an attempt could
see what earlier attempts did. So every attempt starts from the brand's clean
state:

- Each attempt gets a fresh chat session. Attempts run in waves of up to four
  started together.
- Before each wave, every chat is deleted (after its pending summary is
  written), the learning jobs are waited out, and what was learned since the
  clean state is removed. The machine's chat summaries, the folder where
  pasted files land, and the files earlier attempts wrote are emptied.
- A check that uses no model then refuses to start the wave while the brand
  still holds any of it.
- Attempts whose prompt pastes data files run one at a time, so no attempt
  sees another's files.

## What makes an attempt invalid

Every model call records a fingerprint of the context it was given. Each call
of an attempt must carry the clean brand's fingerprint. An attempt whose
calls saw any other context (an earlier chat's summary, a learned lesson) is
recorded as an error, never as a score. The run's `report.json` states this
protocol in its `session_protocol` field.

Run errors count as failed attempts in the score
([how errors count](SCORING.md#run-errors-and-truncated-answers)). The board's
three Magister runs have none.

## Reading the Magister column

- The column measures Magister's agent on that model, with its tools, its
  skills and its harness, against the same tasks and the same judge. It is
  not a measure of the model alone, and it is not an equal-compute
  comparison with the one-call setups.
- It cannot be reproduced from this repository alone. Its prompts, answers
  and verdicts are published on the board like every other setup's.

## What lives where

This repository holds:

- the tasks, rubrics and invented fixtures;
- the runner that runs the direct setups and grades and reports every setup,
  the Magister setup included;
- the Claude Code harness (`python -m eval_runner.claude_code`);
- the agent-system engine in `evals/` and its reference adapters.

Magister's private repository holds the bridge, the test lanes, the product
itself, and the harness for the [simulated-company tasks](SIMULATED_COMPANIES.md).

Keep it that way: this repository stays free of Magister's production
identities, endpoints, credentials and deployment code (`AGENTS.md`).

## The agent-system comparison in `evals/`

The `evals/` engine has its own way to compare two agent systems:
`marketing-benchmark compare` joins two run folders, checks that they match
(model, settings, tasks and environment) and withholds scores where they do
not. A Magister adapter for that engine would live downstream; none is in this
repository. The board's Magister column was not made this way: it was made by
the bridge described above. See [Architecture](ARCHITECTURE.md).

## Internal execution policy

- Run validation, conformance, and deterministic replay on relevant changes.
- Use three repetitions for screening and at least ten on discriminating cases
  before making a routing recommendation.
- Never automatically change production defaults from a benchmark report.
- Keep private run evidence in Magister-controlled storage; do not commit it to
  this repository.
