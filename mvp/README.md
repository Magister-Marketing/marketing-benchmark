# MVP eval — direct-API marketing benchmark

The smallest useful version of this benchmark: call models directly over
HTTP with default API settings, grade each response with an LLM judge
against a binary rubric, let a human verify or override every judgment,
and only count a task as passed when **all repetitions pass**.

No agents, no tools, no sandboxes, no pairwise judging. The heavyweight
runner in `evals/` remains the path for tool-using agent comparisons;
this directory is the current entry point for model-level marketing
quality.

## Protocol

- Every (model, task) pair runs **3 repetitions** by default.
- A repetition passes only if the judge (or a human override) passes
  **every** rubric criterion and marks the task completed.
- A task passes for a model only if **all repetitions pass** (pass^3).
- Provider errors and judge failures count as failed repetitions.
- Temperature is never sent; the only setting is a uniform
  `max_output_tokens` recorded in `run.json`.
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

## Tasks

| Task | Brand fixture | Skill graded |
|---|---|---|
| `headline` | cedar-and-coil | copywriting |
| `blog-post` | brightline-heating | copywriting |
| `ad-creatives` | cedar-and-coil | ad-creative |
| `ad-performance-analysis` | cedar-and-coil + `mvp/fixtures/ad-performance/campaigns.csv` | analytics |
| `marketing-plan` | northstar-ops | copywriting + analytics |
| `landing-page` | harborline-sleep | cro + site-architecture |
| `shopify-meta-capi` | cedar-and-coil | analytics |

The ad-performance CSV has planted, exactly computable findings
(creative fatigue on Broad, frequency saturation on Retargeting, a
stable winner, and one week of missing conversions that must be treated
as missing, not zero), so the analysis task is graded against oracle
numbers, not vibes.

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
```

The individual stages, when you need them separately:

```bash
# offline sanity check (also run in CI)
python3 -m mvp.bench validate

# 1) generate (paid) — asks for confirmation unless --yes
python3 -m mvp.bench run --models claude-haiku-4-5,claude-sonnet-5

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
```

Each run writes immutable evidence under `mvp/results/<run-id>/`:
`run.json` (config), `attempts.jsonl`, `responses/*.md`,
`judgments.jsonl`, `human_verdicts.jsonl`, `report.md`. Results are
gitignored; commit a `report.md` into `docs/results/` when publishing.

## The ladder: same tasks, rising tiers

The tasks in `tasks/*.json` are the constant. Each tier changes only
what generates the response, so results stay comparable up the stack:

| Tier | Generator | Status |
|---|---|---|
| 0 | Raw model, direct API call (`skills` x `tools` arms) | **this directory** |
| 1 | Coding-agent harnesses: Claude Code, Codex CLI | planned; adapt from `evals/runner/adapters/` |
| 2 | The Magister harness (real product path) | planned |

Rules that keep the ladder honest:

- Task prompts, fixtures, and rubrics are never forked per tier. A tier
  that needs a different prompt gets a new task id instead.
- The judge, rubric, and pass^3 protocol are identical at every tier.
- Every run records its tier and arms (`run.json`), so any two runs can
  be compared attempt-for-attempt.

## Deliberately deferred

- **Prime Intellect / verifiers** — task JSONs are self-contained
  (prompt + fixtures + binary rubric), so porting to a `verifiers`
  Environment later is mechanical.
- **More providers** — `providers.py` is a registry of two small HTTP
  functions; Gemini is a ~15-line addition when needed.
