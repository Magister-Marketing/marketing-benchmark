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
appears exactly once with literal JSON booleans and string evidence.

Every task also has independent `prompt_version` and `rubric_version` fields.
A rubric may be hardened against the same recorded prompt. A compatible prompt
clarification may retain the task id only when the exact older prompt is
archived with a reason and the new rubric intentionally supports both; a
change to graded behavior or fixture contract requires a new task id.

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
in `models.json`; its OpenRouter entries are `gemini-3.7-flash-high` and
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
| Coding agents | Claude Code, Codex CLI | planned; adapt from `evals/runner/adapters/` |
| Magister | Real product path | planned |

Rules that keep the ladder honest:

- Task prompts, fixtures, and rubrics are never forked per harness. A harness that
  needs a different prompt gets a new task id instead. Each run snapshots its
  task definitions and exact assembled prompts.
- The judge, rubric, and configured run count are identical for every harness.
- Every run records its harness and arms (`run.json`), so any two runs can
  be compared attempt-for-attempt.

## Deliberately deferred

- **Prime Intellect / verifiers** — task JSONs are self-contained
  (prompt + fixtures + binary rubric), so porting to a `verifiers`
  Environment later is mechanical.
- **More providers** — `providers.py` keeps the three direct HTTP adapters
  small and isolated, so another provider can be added without changing task
  or report contracts.
