# Magister Marketing Evals — direct-model runner

The current `direct-api` harness calls models over HTTP with default API
settings, grades each response with deterministic hard checks plus an LLM
judge against a binary rubric, lets a human verify or override every judgment,
and only counts a task as passed when every configured run passes. The default
is one run per task: **pass@1**.

No coding-agent runtime, sandbox, or pairwise judge is involved. Provider web
search is an optional arm and remains off by default. The engine in `evals/`
supports tool-using agent comparisons; this directory is the current entry
point for direct-model marketing quality.

## Protocol

- Every (model, task) pair runs **once** by default. `--repetitions N` opts into
  any larger run count without changing tasks, rubrics, or report structure.
- A run passes only if every programmatic check and judge criterion
  passes and the judge marks the task completed (or a human overrides it).
- A task passes for a model only if **every configured run passes**. At the
  default this is pass@1; if `--repetitions 3` is requested, all three must pass.
- The headline model score is the share of selected tasks that pass. Per-task
  passed/total criterion counts explain near misses without becoming partial
  credit; macro and pooled criterion rates remain structured diagnostics.
- Provider errors and judge failures count as failed runs.
- Temperature is never sent. Anthropic and OpenRouter get an output ceiling;
  OpenAI is uncapped unless a candidate explicitly opts into a ceiling.
- Two independent arm toggles, both recorded in evidence:
  - **Skills**: guidance from `evals/fixtures/public/skills/` is in the
    prompt by default. Each task explicitly lists its skill files, whose full
    raw text is appended to the user prompt; there is no native skill loader or
    model-side discovery. `--no-skills` is the baseline arm, so skill uplift is
    measurable with the same tasks and rubric.
  - **Tools**: off by default; `--tools` enables provider-hosted web
    search on the same API call (Anthropic server web-search tool,
    OpenAI Responses `web_search`, or the OpenRouter `web` plugin). Tasks and
    rubrics do not change, so
    on fixture-grounded tasks the tools arm also measures tool
    discipline — staying inside supplied sources when search is available. The
    judge is always tool-less and receives no explicit arm flag or candidate
    identity. It grades the exact recorded prompt, so it sees skill text when
    that text was part of the candidate prompt but does not see tools metadata.

Reports open with one compact task matrix: overall task score, a binary result
and passed/total criterion count for every task, total candidate output tokens,
total candidate cost, and average task time. The binary result is the score;
criterion counts only explain near misses. The Magister-branded `report.html`
embeds the real logo and typography and keeps every task/model submission on
the main page. Its header links to the repository and includes a copyable
command reconstructed from the recorded models, tasks, repetition count,
skills arm, tools arm, and judge; clicking anywhere on the command copies it.
The adjacent **Copy results for LLM** action copies the exact generated
`report.md`, embedded into the HTML so it works locally and when hosted without
a network fetch. Selecting a matrix cell jumps into a
filterable Tasks & Submissions view grouped by task: the exact assignment and
complete assembled prompt appear once, followed by a task-level model results
table and a collapsed response-and-score panel for every model. Opening a
model reveals its candidate response and judge evidence; complete prompts and
raw responses remain expandable, with raw Markdown links as secondary actions.
It has no remote runtime dependencies
and is formatted for screenshots and printing. `report.md` keeps the same
all-in-one table at the top followed by a text-first audit trail. `report.json`
contains the compact leaderboard plus the self-contained submission records.
Costs use recorded input/output usage and the current price catalog and do not
include LLM-judge spend.

## Rubric shape

Every task in `tasks/*.json` carries three sections of binary criteria:

1. `completion` — did it even do the task (structure, counts, limits,
   required content)? The judge also returns a top-level `completed`.
2. `skill_adherence` — did it follow the supplied marketing skill's
   recommendations (grounding, no invented proof, preserved safety and
   disclosures, missing data kept missing)?
3. `best_practices` — does it reflect how a strong marketer would do the
   work (positioning fit, distinct angles, prioritized actions,
   technically correct tracking)?

Criteria whose answer is mechanically knowable carry a `programmatic`
condition. Counts, exact CTA values, word minimums, HTML document shape,
active/embedded assets, and heading order are computed locally and never
delegated to the judge. Semantic criteria remain binary judge calls with
one-sentence evidence. Judge output is accepted only when every requested id
appears exactly once with literal JSON booleans and string evidence, plus a
top-level `self_report` (`complete`, `partial`, or `blocked`) describing how
the response presents its own deliverable.

A criterion marked `critical` caps the attempt's diagnostic score at 40 when
it fails, and must name, in `fails_if_zero`, the banded programmatic checks
that prove it; when one of those scores 0 the criterion fails on oracle
evidence and the attempt scores 0. A judge-only critical is rejected by
`bench validate`: one interpretive call must not swing a task by 40 points,
and a judge without an oracle passed invented figures on 2026-09-02. See
`docs/SCORING.md` for the honesty rules.

Every task also has independent `prompt_version` and `rubric_version` fields.
A rubric may be hardened against the same recorded prompt. A compatible prompt
clarification may retain the task id only when the exact older prompt is
archived with a reason and the new rubric intentionally supports both; a
change to graded behavior or fixture contract requires a new task id.

Three optional fields cover a task whose input a harness must *deliver*
rather than inline:

- `harnesses` — the harness ids that can run the task (`magister-agent` is
  the bridge in the Magister monorepo). Absent means every harness. This
  runner's `run`, `--split`, and `--tasks` selection skips a task that does
  not list `direct-api`, and refuses it by name rather than running a
  degraded version.
- `decoy` — `{fixture, message, answers}`: a look-alike source the harness
  sends as its own chat turn *before* the task prompt (`assemble_decoy_prompt`
  builds that turn: the message, then the export under the same
  `## Supplied source: <name>` heading the real fixture gets, so a harness
  that saves pastes to files names both alike). `assemble_prompt` ignores it,
  which is why a decoy task must list `harnesses` and never `direct-api`:
  inlined into one prompt, the decoy would change the task. `answers` maps
  every banded check to the value the decoy yields; `bench validate` proves
  each scores 0 against the real target, so computing from the wrong file
  fails on oracle evidence.
- `derived_from` — the parent task this one duplicates. Prompt, answers,
  fixtures, and skills must be identical and every parent criterion must
  appear unchanged; the derived task may only add (a decoy, a criterion).
  `load_tasks` enforces it, so a parent edit that forgets the child fails
  instead of shipping two versions of one task.

## Tasks

| Split | Task | What it probes |
|---|---|---|
| development | `headline` | grounded, distinct launch positioning |
| development | `blog-post` | long-form search intent and safety triage |
| development | `ad-creatives` | operational creative hypotheses |
| development | `ad-performance-analysis` | oracle math, missing-data denominator integrity, bounded decisions |
| development | `marketing-plan` | budget, sequencing, and mature activation cohorts |
| development | `landing-page` | single-file conversion page and deterministic HTML gates |
| development | `shopify-meta-capi` | retry-stable browser/server deduplication |
| development | `source-conflict-repair` | contradiction detection and grounded repair (holdout until 2026-08-25) |
| development | `attribution-sensitivity` | deduplication, refunds, two attribution oracles, conditional judgment (holdout until 2026-08-25) |
| development | `factorial-ad-test` | dense interacting constraints in a 2x2 experiment (holdout until 2026-08-25) |
| development | `landing-page-repair` | correction of planted factual, safety, proof, action, and HTML defects (holdout until 2026-08-25) |
| development | `email-flow-repair` | unprompted defect detection in a lifecycle sequence (holdout until 2026-08-25) |
| development | `budget-reconciliation-trap` | catching an infeasible brief instead of papering over it (holdout until 2026-08-25) |
| development | `analytics-source-conflict` | reconciling contradictory platform/GA4 numbers without inventing a single truth (holdout until 2026-08-25) |
| holdout | `launch-capacity-trap` | one resource infeasible while the other fits, plus a freeze-date conflict |
| holdout | `platform-limits-gauntlet` | eleven labeled fields under hard character limits and exact required strings |
| holdout | `rate-card-reconciliation` | cross-fixture invoice audit with distractor rates and three planted errors |
| holdout | `unsupportable-claims-brief` | partial refusal: deliver the brief, decline the four unsupportable claims |
| development | `ads-ledger-analysis` | 784-row daily ledger: five oracle figures, refund-adjusted method, planted wasted spend, oracle-backed `no_invented_data` |
| development | `ads-ledger-analysis-decoy` | the same ledger with a look-alike preliminary export planted one turn earlier; harness-only (`harnesses`), `derived_from` the ledger task |
| development | `tracking-audit` | 12 planted UTM/GTM/consent defects across four artifacts, with conforming decoys that must not be flagged |

The ad-performance CSV has planted, exactly computable findings
(creative fatigue on Broad, frequency saturation on Retargeting, a
stable winner, and one week of missing conversions that must be treated
as missing, not zero), so the analysis task is graded against oracle
numbers, not vibes.

### Calibration discipline

The development split is allowed to inform rubric design; its scores are
post-hoc calibration evidence, not an untouched model ranking. The holdout
split must not be used to tune criteria after reading responses. After a
holdout is inspected, move it into development and replace it before claiming
another held-out comparison. Criteria are written from prompt and domain
contracts, not chosen to force an arbitrary failure rate.

## Usage

Keys come only from the environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
and `OPENROUTER_API_KEY` (or `--env-file <KEY=value file>` on `eval.py`,
which reads only those three names and never prints values). Candidates live
in `models.json`; its OpenRouter entries are `gemini-3.8-flash-high` and
`glm-5.3`.

OpenRouter requests always pin zero-data-retention, deny data collection, and
restrict routing to each candidate's explicit provider allowlist. Every request
runs on the provider's default service tier; the discounted flex tier is not
used because it never falls back on a capacity error.

**The one-liner** — run, grade, and report in a single command from the
repo root:

```bash
./eval.py gpt-5.6-luna-medium gpt-5.6-terra-medium gpt-5.6-sol-medium
./eval.py claude-sonnet-5 --tools          # web-search arm
./eval.py claude-haiku-4-5 --no-skills -y  # baseline arm, no prompt
./eval.py claude-sonnet-5 --split holdout  # untouched-task check
./eval.py claude-sonnet-5 --repetitions 3  # explicitly request three runs/task
```

The individual stages, when you need them separately:

```bash
# offline sanity check (also run in CI)
python3 -m eval_runner.bench validate

# 1) generate (paid) — asks for confirmation unless --yes
python3 -m eval_runner.bench run --models claude-haiku-4-5,claude-sonnet-5

# run just one split; explicit --tasks takes precedence
python3 -m eval_runner.bench run --models claude-sonnet-5 --split holdout

# optional baseline arm without skill guidance in the prompt
python3 -m eval_runner.bench run --models claude-haiku-4-5 --no-skills

# optional tools arm: same tasks, provider-hosted web search enabled
python3 -m eval_runner.bench run --models claude-haiku-4-5 --tools

# 2) judge every attempt (paid; default judge claude-sonnet-5)
python3 -m eval_runner.bench grade --run eval_runner/results/<run-id>

# 3) human verification — agree/override each judgment
python3 -m eval_runner.bench verify --run eval_runner/results/<run-id> --failures-only

# 4) report (offline; applies human overrides)
python3 -m eval_runner.bench report --run eval_runner/results/<run-id>

# Calibrate a new rubric against old prompts without overwriting v1 evidence.
# --current-rubric accepts only the current prompt or an explicitly archived,
# rubric-compatible historical prompt.
python3 -m eval_runner.bench grade --run eval_runner/results/<run-id> \
  --current-rubric --label candidate-rubric
python3 -m eval_runner.bench report --run eval_runner/results/<run-id> --label candidate-rubric

# Regrade selected tasks into an existing label without touching its other rows.
python3 -m eval_runner.bench grade --run eval_runner/results/<run-id> \
  --current-rubric --label candidate-rubric --tasks landing-page,blog-post
```

Each run writes immutable evidence under `eval_runner/results/<run-id>/`:
`run.json` (config), `tasks/*.json` (exact task snapshots), `prompts/*.md`,
`attempts.jsonl`, `responses/*.md`, `judgments.jsonl`,
`human_verdicts.jsonl`, `grading.json`, `report.md`, `report.html`, and
`report.json`.
Labeled regrades add the label before each grading/report extension. Results
are gitignored; commit reviewed report artifacts into `docs/results/` when
publishing.

## Harness roadmap: same tasks, different execution paths

The tasks in `tasks/*.json` are the constant. A harness changes only what
generates the response, so results remain comparable:

| Harness | Generator | Status |
|---|---|---|
| `direct-api` | Raw model API call (`skills` x `tools` arms) | available |
| `claude-code` | Headless Claude Code: stock tools, optionally a skills plugin and MCP servers (`eval_runner/claude_code.py`) | available |
| Other coding agents | Codex CLI | planned; adapt from `evals/runner/adapters/` |
| `magister-agent` | Real product path (the bridge in the Magister monorepo) | available; the only harness that runs `decoy` tasks |

Rules that keep the ladder honest:

- Task prompts, fixtures, and rubrics are never forked per harness. A harness that
  needs a different prompt gets a new task id instead. Each run snapshots its
  task definitions and exact assembled prompts.
- The judge, rubric, and configured run count are identical for every harness.
- Every run records its harness and arms (`run.json`), so any two runs can
  be compared attempt-for-attempt.

## The Claude Code harness

`direct-api` asks a model one question. `claude-code` gives the same task to
the Claude Code agent as a person would use it, and writes the same run
directory, so `grade` and `report` read it unchanged.

```sh
# the stock agent: a shell, file tools, web search
python -m eval_runner.claude_code run --candidate claude-haiku-5-5-high \
    --repetitions 3 --env-file ~/keys.env --yes

# with a skills plugin installed, as a user installs one; the model decides what to open
python -m eval_runner.claude_code run --candidate claude-haiku-5-5-high --repetitions 3 \
    --plugin-dir ~/src/marketingskills --env-file ~/keys.env --yes

# the best case for skills: installed, and the prompt names the ones the task was written against
python -m eval_runner.claude_code run ... --plugin-dir ~/src/marketingskills --name-skills

# with MCP servers attached (Claude Code's own mcpServers JSON; its contents stay out of the run)
python -m eval_runner.claude_code run ... --mcp-config ~/magister-mcp.json

# with the person's own files (exports, a brief) saved into the working folder and named in the prompt
python -m eval_runner.claude_code run ... --files-dir ~/exports

# a task set kept outside this repository (its answers are someone's real numbers)
MARKETING_BENCH_TASKS_DIR=~/private-tasks python -m eval_runner.claude_code run ...

python -m eval_runner.bench grade --run eval_runner/results/<run> --env-file ~/keys.env
python -m eval_runner.bench report --run eval_runner/results/<run>
python scripts/compare-arms.py --arm "Claude Code=eval_runner/results/<run>" \
    --arm "Claude Code + skills=eval_runner/results/<run>" --arm "Magister=<run>"
```

What every attempt gets:

- **Its own folders and nothing of yours.** A fresh working, configuration,
  home and temp folder per attempt, and its own copy of any plugin; no
  CLAUDE.md, memory, settings, plugins, hooks or MCP servers from the machine
  it runs on. The session's own list of what it loaded is kept as
  `agent_inventory` in `run.json`. Attempts cannot see each other: the
  folders live under a short private path in `/tmp`, because Claude Code
  falls back to a temp folder every session shares when the one it is given
  has a long path, and an attempt whose shell did not use its own is recorded
  as an error.
- **The sources as files.** Each supplied source is inline in the prompt, as
  for every harness, and also saved in the working folder, with one sentence
  saying so.
- **Claude Code's shell sandbox, on.** Every shell command runs without
  asking, may write only inside the attempt's folders, may reach the package
  registries and nothing else, cannot read your home folder, the shared temp
  folders or another attempt, and has no API key in its environment. Web
  search and web fetch stay on. A file-tool call outside the attempt's folders is
  refused; refusals are counted per attempt (`guardrail_kinds`).
- **The same preamble as the Magister agent harness:** draft only, treat the
  sources as current, deliver the answer in the reply.

Per attempt the run records the model calls, the tools called, the skills
opened (`skill_reads`), tokens, the cost Claude Code reports, the raw event
stream (`transcripts/`) and any files the agent wrote (`artifacts/`, never
graded). The reply that is graded is everything the agent said to the person,
in order, as the Magister harness records its agent's reply.

It needs the `claude` CLI on the PATH and an `ANTHROPIC_API_KEY`; sessions
are billed to that key, about one to three cents a task on Haiku 5.5. Tasks
that need a prior turn (`decoy`) are left out, as on `direct-api`.

## Deliberately deferred

- **Prime Intellect / verifiers** — task JSONs are self-contained
  (prompt + fixtures + binary rubric), so porting to a `verifiers`
  Environment later is mechanical.
- **More providers** — `providers.py` keeps the three direct HTTP adapters
  small and isolated, so another provider can be added without changing task
  or report contracts.
