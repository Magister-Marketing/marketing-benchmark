# MVP eval — direct-API marketing benchmark

The smallest useful version of this benchmark: call models directly over
HTTP with default API settings, grade each response with deterministic hard
checks plus an LLM judge against a binary rubric, let a human verify or
override every judgment, and only count a task as passed when **all
repetitions pass**.

No agents, no tools, no sandboxes, no pairwise judging. The heavyweight
runner in `evals/` remains the path for tool-using agent comparisons;
this directory is the current entry point for model-level marketing
quality.

## Protocol

- Every (model, task) pair runs **3 repetitions** by default.
- A repetition passes only if every programmatic check and judge criterion
  passes and the judge marks the task completed (or a human overrides it).
- A task passes for a model only if **all repetitions pass** (pass^3).
- Provider errors and judge failures count as failed repetitions.
- Temperature is never sent. Anthropic gets its required output ceiling;
  OpenAI is uncapped unless a candidate explicitly opts into a ceiling.
- Two independent arm toggles, both recorded in evidence:
  - **Skills**: guidance from `evals/fixtures/public/skills/` is in the
    prompt by default; `--no-skills` is the baseline arm, so skill
    uplift is measurable with the same tasks and rubric.
  - **Tools**: off by default; `--tools` enables provider-hosted web
    search on the same API call (Anthropic server web-search tool,
    OpenAI Responses `web_search`). Tasks and rubrics do not change, so
    on fixture-grounded tasks the tools arm also measures tool
    discipline — staying inside supplied sources when search is
    available. The judge is always tool-less and blind to the arm.

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
| holdout | `source-conflict-repair` | contradiction detection and grounded repair |
| holdout | `attribution-sensitivity` | deduplication, refunds, two attribution oracles, conditional judgment |
| holdout | `factorial-ad-test` | dense interacting constraints in a 2x2 experiment |
| holdout | `landing-page-repair` | correction of planted factual, safety, proof, action, and HTML defects |

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

Keys come only from the environment: `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY` (or `--env-file <KEY=value file>` on `eval.py`, which
reads only those two names and never prints values). Candidates live in
`models.json`.

**The one-liner** — run, grade, and report in a single command from the
repo root:

```bash
./eval.py gpt-5.6-luna-medium gpt-5.6-terra-medium gpt-5.6-sol-medium
./eval.py claude-sonnet-5 --tools          # web-search arm
./eval.py claude-haiku-4-5 --no-skills -y  # baseline arm, no prompt
./eval.py claude-sonnet-5 --split holdout  # untouched-task check
```

The individual stages, when you need them separately:

```bash
# offline sanity check (also run in CI)
python3 -m mvp.bench validate

# 1) generate (paid) — asks for confirmation unless --yes
python3 -m mvp.bench run --models claude-haiku-4-5,claude-sonnet-5

# run just one split; explicit --tasks takes precedence
python3 -m mvp.bench run --models claude-sonnet-5 --split holdout

# optional baseline arm without skill guidance in the prompt
python3 -m mvp.bench run --models claude-haiku-4-5 --no-skills

# optional tools arm: same tasks, provider-hosted web search enabled
python3 -m mvp.bench run --models claude-haiku-4-5 --tools

# 2) judge every attempt (paid; default judge claude-sonnet-5)
python3 -m mvp.bench grade --run mvp/results/<run-id>

# 3) human verification — agree/override each judgment
python3 -m mvp.bench verify --run mvp/results/<run-id> --failures-only

# 4) report (offline; applies human overrides)
python3 -m mvp.bench report --run mvp/results/<run-id>

# Calibrate a new rubric against old prompts without overwriting v1 evidence.
# --current-rubric accepts only the current prompt or an explicitly archived,
# rubric-compatible historical prompt.
python3 -m mvp.bench grade --run mvp/results/<run-id> \
  --current-rubric --label candidate-rubric
python3 -m mvp.bench report --run mvp/results/<run-id> --label candidate-rubric

# Regrade selected tasks into an existing label without touching its other rows.
python3 -m mvp.bench grade --run mvp/results/<run-id> \
  --current-rubric --label candidate-rubric --tasks landing-page,blog-post
```

Each run writes immutable evidence under `mvp/results/<run-id>/`:
`run.json` (config), `tasks/*.json` (exact task snapshots), `prompts/*.md`,
`attempts.jsonl`, `responses/*.md`, `judgments.jsonl`,
`human_verdicts.jsonl`, `grading.json`, `report.md`, and `report.json`.
Labeled regrades add the label before each grading/report extension. Results
are gitignored; commit a reviewed `report.md` into `docs/results/` when
publishing.

## The ladder: same tasks, rising tiers

The tasks in `tasks/*.json` are the constant. Each tier changes only
what generates the response, so results stay comparable up the stack:

| Tier | Generator | Status |
|---|---|---|
| 0 | Raw model, direct API call (`skills` x `tools` arms) | **this directory** |
| 1 | Coding-agent harnesses: Claude Code, Codex CLI | planned; adapt from `evals/runner/adapters/` |
| 2 | The Magister harness (real product path) | planned |

Rules that keep the ladder honest:

- Task prompts, fixtures, and rubrics are never forked per tier. A tier that
  needs a different prompt gets a new task id instead. Each run snapshots its
  task definitions and exact assembled prompts.
- The judge, rubric, and pass^3 protocol are identical at every tier.
- Every run records its tier and arms (`run.json`), so any two runs can
  be compared attempt-for-attempt.

## Deliberately deferred

- **Prime Intellect / verifiers** — task JSONs are self-contained
  (prompt + fixtures + binary rubric), so porting to a `verifiers`
  Environment later is mechanical.
- **More providers** — `providers.py` is a registry of two small HTTP
  functions; Gemini is a ~15-line addition when needed.
