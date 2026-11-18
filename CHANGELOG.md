# Changelog

## Unreleased

- Tasks: six closed-book tasks in kinds of marketing work the set lacked.
  Development: `seo-technical-triage`, `search-terms-negatives`,
  `ab-test-readout`. Holdout: `seo-content-brief`, `lifecycle-reengagement`,
  `monthly-report-reconcile`. Each ends in a labeled answer block of banded
  figures and has one critical no-invention criterion backed by an oracle
  that lists only plain aggregates: a plain sum, count or rate under an
  explicit filter, with a zero band at least a tenth of its value. A planted
  trap therefore costs its own criterion. A listed figure beyond its zero
  band still scores the whole attempt zero, as for every oracle-backed
  critical; a figure on an unparsed answer line is absence and does not.
  `eval_runner/task_references.py` computes the tasks' figures from the
  recorded prompt and gives them to the judge as reference totals; its
  version is recorded in `grading.json` as `task_reference_version`, and a
  prompt whose sources cannot be read grades without a reference and warns.
  `scripts/gen_more_tasks.py` writes the fixtures from seeded generators and
  pins, in the task files, every programmatic condition, tolerance, oracle
  list and definition line, and the wording of every check that states a
  band or a figure from the data (`--write`, `--sync`, `--check`).
  `tests/test_more_tasks.py` recomputes every target and every reference
  figure independently, writes out the bands and oracle lists a second time,
  and proves that the careless answer each task is built to catch scores zero
  on the criterion meant to catch it. All brands and data are invented.
  Version 1 was a local draft, run once by one agent and discarded after
  review; the versions here are not calibrated and have not been run. Two
  more drafts, `social-calendar-limits` and `positioning-from-competitors`,
  read free text by pattern and are not in the set.
- Answers: a task may set `"single_number": true` in `answers`. Its answer
  block is then the run of answer lines with the most answers (the later run
  when two are alike), so a labelled line in a note cannot override it; a
  line is an answer only when it carries exactly one number, so a line with
  working on it (`A1: 749 / 12,480 = 6.00%`) is left unparsed instead of
  being read as its first number; a label with nothing after it stays blank;
  and a minus sign is read whether typed as a hyphen, U+2212 or a leading en
  dash. `eval_runner/README.md` lists what is left unparsed on purpose. The
  21 earlier tasks do not set it and parse exactly as before.
- Judge: `judge_source_reference` now also returns reference totals for the
  six new tasks, computed from the sources in the recorded prompt.
- Judges: `grade --judge` now sends the judge entry's `reasoning_effort` and
  `text_verbosity` with every judge request; before, a judge picked from
  models.json was called at the provider default effort whatever its entry
  said, so only the effort-less Anthropic ids graded as named. New
  `gpt-5.6-luna-high` catalog entry (Luna at high effort) as a cheap judge;
  a run's `judge_model` records the id, so scores graded by different
  judges stay distinguishable.
- Tasks: `ads-ledger-analysis-decoy`, the ledger review with a look-alike
  "preliminary" export (same name, header, 784 rows, and dates; every number
  moved) shared one turn earlier for reference only. All five oracle answers
  from the decoy fall outside the zero-credit band (A1 +40%, A2 +56%, A3
  five weeks early, A4 -50%, A5 -39%), so computing from the wrong file
  scores 0 through the existing oracle-backed `no_invented_data`; the rubric
  is otherwise the parent's, because the prompt is byte-identical and never
  asks the review to name its source file (the harness records which saved
  file the review named as unscored evidence). Harness-only: the task lists `harnesses: [magister-agent]`,
  and `run`/`--split`/`--tasks` skip or refuse it on `direct-api`, whose
  inlined prompt could not carry a prior turn. New task fields `harnesses`,
  `decoy` (fixture, message, answers — each validated to score 0 against the
  real target), and `derived_from` (prompt, answers, sources, and every
  parent criterion must match the parent; `load_tasks` enforces).
  `scripts/gen_ads_ledger.py` writes the decoy deterministically from the
  real ledger.
- Scoring: a critical criterion fails on oracle evidence. `fails_if_zero`
  names the banded programmatic checks that prove a must-not; when one
  scores 0 the criterion fails regardless of the judge and the attempt
  scores 0 instead of the 40 cap. Every `critical` criterion must carry it
  (`bench validate` enforces). `ads-ledger-analysis` rubric v2 backs
  `no_invented_data` with A1/A2/A4/A5; run `20260902-003921` (five
  estimated figures, 8-46% off, judged "match the ground truth") drops from
  75.5 to 0.0 on the next report.
- Scoring: an honest abstention keeps its negatives. The judge now returns
  `self_report` (`complete` / `partial` / `blocked`); a `blocked` reply is
  not content-free, so "negatives need a positive" no longer strips it.
  Re-graded, run `20260902-031311` (could not read the file, refused to
  invent the figures) scores 8.3 on ads-ledger instead of 0.0, above the
  confident wrong answer it previously trailed by 75 points. Pass/fail is
  unchanged.
- Scoring: `critical` is read from the current task file at report time,
  as `negative` already was, so demoting a judge-only critical lifts its 40
  cap from recorded runs on the next report (run `20260902-044014`,
  tracking-audit r2: 40.0 -> 82.4).
- Report: run marks gain `A` (failed, said it was blocked) and a Behavior
  table with tool calls per attempt, tool errors, guardrail events (from the
  bridge's new `guardrail_events` field), false confidence (failed attempts
  presented as complete) and abstentions; `report.json` carries them under
  `models.<id>.behavior`. The bridge's `session_isolation` /
  `session_protocol` now appear in the header, configuration, and JSON so a
  per-task board is never read as a per-round one.
- Tasks: `tracking-audit` rubric v2 splits the three-link uppercase-medium
  finding into search (x2) and Performance Max so a 2-of-3 hit scores half,
  and `no_false_positives` stays negative but is no longer critical: one
  interpretive judge call on it moved the task 42 points between two runs.
- Answer block: a bracketed placeholder (`A5: [blocked — ...]`) is not an
  answer; the parser no longer reads `-28` out of it.
- Scoring: free credit is discounted. A programmatic check that already
  scores on an empty response (`html_parse_error_count equals 0`,
  `over_limit_field_count equals 0`, ...) has that portion removed; a check
  that is fully free is a guard, excluded from the diagnostic score while it
  holds and counted as a failure when a deliverable breaks it. Measured from
  the task itself at report time, so it applies to every recorded run.
- Scoring: 23 absence criteria (`no_invented_proof`, `no_false_positives`,
  `*_removed`, ...) carry `negative: true` and count only once at least one
  positive criterion passed, so a content-free reply cannot collect them.
  Pass/fail is unchanged; only the diagnostic score and the report's
  criteria tally move. A blank-deliverable probe (`20260901-blank-baseline`)
  now scores 0.0 / 0.3 instead of up to 17.5 per task.
- Judge: a criterion that forbids something passes when the forbidden
  content is absent from a response that otherwise engages the task; the
  "fail when silent" rule stays for everything else.

## 0.1.0a1 — private staging

- Extract the provider-neutral runner from Magister through an allowlisted,
  clean-room boundary.
- Add versioned manifests and normalized tool traces.
- Add deterministic GA4 and cross-source replay environments.
- Add synthetic ads, lifecycle email, blog/SEO, and website benchmark packs.
- Add Claude Code and subprocess/JSONL reference adapters.
- Add a direct OpenAI Responses API adapter with isolated read, write, and
  structured-UI tools and environment-only credentials.
- Add a quick 11-profile Luna, Terra, and Sol reasoning-effort experiment.
- Add deterministic grading, blinded pairwise judging, and routing/capability
  reports.
- Add a plain-language public report alongside the technical evidence report.
- Add standalone packaging, repository scaffolding, tests, and CI.

No package or open-source license has been published.
