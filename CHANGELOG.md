# Changelog

## Unreleased

- Tasks: workflow task `catalog-descriptions` (development split): a 60-row
  product table in twelve families of near-identical variants, a certificate
  register, a warranty policy by category and last season's descriptions in;
  60 descriptions out, each with a fixed spec line, the warranty its row or
  its category gives, only the standards whose certificates count on the
  publish date, nothing for a blank weight or country, and no fact borrowed
  from a sibling or kept from stale copy. 11 of its 12 checks are a
  program's.
- Tasks: workflow task `launch-copy-pack` (development split): a launch
  brief, a 133-row claims register, an engineering spec sheet, last year's
  launch copy, voice rules and a placements table in; 72 assets for four
  products out. Every figure and claim phrase must come from a register row
  usable for the asset's product and channel, prices carry the product's own
  offer date, an SMS limit counts the opt-out line and falls to 70
  characters for one non-plain character, and no two of a product's
  headlines open alike. 14 of its 15 checks are a program's. The copy
  tasks share `eval_runner/task_facts_copy.py` (documents, reference replies
  and checkers); each has a thin interface module in `eval_runner/workflows/`.
- Runner: the direct setups now run `ads-ledger-analysis-decoy`, so all 30
  development tasks are shared by the model alone, the model with the skills
  and Magister. A decoy task is one conversation of two calls to the same
  model with the same settings: call 1 sends only the look-alike message
  (`assemble_decoy_prompt`), call 2 sends that message, the model's own reply
  as plain text, and the task prompt as a single call has it (skills only on
  the "with skills" arm). Only call 2 is graded. A call 1 that fails, is
  empty, refused or cut off fails the attempt; the task is never sent alone.
  Call 1's tokens, cost and time are recorded under `decoy_*` and, as for
  the Magister bridge's decoy turn, are not in the report's cost, tokens or
  time, so the published cost of this task leaves the earlier turn out in
  every setup; `--stop-after-cost-usd` does count them. `retry` replays both
  calls. Validation now names the harnesses that can send a prior turn
  (`PRIOR_TURN_HARNESSES`: `direct-api`, `magister-agent`), and the task lists
  both. Its prompt, rubric, fixtures and versions are unchanged. Providers
  accept a text conversation (Anthropic and OpenRouter `messages`, OpenAI
  Responses `input`); a single prompt goes on the wire as before.
- Runner: `retry` refuses a run another harness made (`claude-code`,
  `magister-agent`). It calls the model directly, so it filled an agent
  run's errored attempts with direct-API answers.
- Runner: `retry` sends each model the output ceiling its run recorded
  (`max_output_tokens_by_model`). A run whose models have different ceilings
  records no single `max_output_tokens`, and its retries sent Anthropic and
  OpenRouter models without a cap of their own `max_tokens: null`.
- Runner: `retry` checks every errored attempt's recorded prompt before it
  asks to proceed or makes a call. It checked each one just before its own
  call, so a changed prompt on a later attempt stopped the retry after the
  earlier ones were paid for again, and their new results were not saved.
- Skills: the six skill files the "with skills" arm pastes into a prompt are
  refreshed, unchanged, to marketingskills 2.8.23 (commit `2c38021`,
  2026-11-20). They were copies from 2026-08-31 (2.8.16), three months behind
  the pack Magister's machines run, so a "with skills" run and a Magister run
  were not using the same skills. `copywriting`, `analytics`, `emails` and
  `ad-creative` changed; `cro` and `site-architecture` did not. Runs made
  before this used the older copies (each run folder keeps the prompts it
  sent).
- Runner: the ceiling retry (one call with the output cap doubled, after an
  empty reply cut off at the cap) never asks for more than a candidate's new
  optional `model_max_output_tokens`, and makes no call when the cap is
  already there. `claude-opus-5-5-medium` (65,536, doubled to 131,072 past
  the model's 128,000, so the retry was rejected) now retries at 128,000;
  `gemini-3.8-flash-high` is at its 65,536 maximum and records the
  truncation in one call. Entries without the field double as before.
- Tasks: workflow task `price-change-rollout` (development split): a price
  change, a plan rename and a longer trial rolled through 14 assets, where
  everything the brief changes must change and nothing else may. Adds a
  reader for named non-CSV files to the workflow tools.
- Tasks: workflow task `outbound-sequence` (development split): a 200-lead
  list, an outbound standard and a facts sheet in; exclusions with reasons,
  assignments by segment and country group, and 30 emails across 10
  sequences out, with merge fields allowed only where every lead has a
  value.
- Tasks: workflow task `launch-trafficking` (development split): a launch
  brief, platform specs, a tracking standard and a landing-page list in; a
  budget by channel and week, 114 text fields across 36 assets and a tracked
  URL for each asset out.
- Tasks: workflow task `lifecycle-program` (development split): a 300-customer
  export and a written policy in; suppression with reasons, segments, the
  holdout, 24 emails and a send-time schedule out. A program counts every
  customer, flow step, send time and copy rule against the reference its
  module computes.
- Tasks: two **forecast tasks**, `headline-forecast` and
  `headline-forecast-unpublished` (development split). Each is 100 pairs of
  headlines from real tests in the Upworthy Research Archive (CC BY 4.0;
  `eval_runner/fixtures/headline-forecast/NOTICE.md`,
  `scripts/build_headline_pairs.py`): pick the headline that got the higher
  click rate and say how sure. A program counts the picks that match the
  record (a coin flip scores nothing, nine in ten passes) and scores the
  stated confidence by its Brier score. The second set holds only
  headlines that were not the ones published, as a control for a model
  recognising a headline that spread.
- Tasks: the first **workflow task**, `search-account-build` (development
  split). A workflow task asks for several dependent deliverables as small
  CSV files inside one reply and is graded by program against a reference its
  own module computes (`eval_runner/workflows/`); a task file names its
  module with `"workflow"`. The files it supplies are generated by that
  module (`scripts/gen_workflow_tasks.py --write|--check`), so the standard
  the candidate reads and the rules the checker applies are the same
  constants. Every count measures work against the reference: a file left
  out is that many errors, and a blank reply earns nothing.
- Tasks: six closed-book tasks in kinds of marketing work the set lacked,
  all in the development split: `seo-technical-triage`,
  `search-terms-negatives`, `ab-test-readout`, `seo-content-brief`,
  `lifecycle-reengagement`, `monthly-report-reconcile`. The last three were
  drafted as holdout tasks; their recorded answers were read and one rubric
  was changed because of them, so they are development tasks and no
  held-out claim rests on them. The holdout split is the four tasks it held
  before. Each of the six ends in a labeled answer block of banded
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
  review. In the versions here the program-checked figures are verified by
  that independent recomputation; the judged criteria are not calibrated (no
  judge has been tested on them against responses with known errors). Two
  more drafts, `social-calendar-limits` and `positioning-from-competitors`,
  read free text by pattern and are not in the set.
- Tasks: rubric version 4 of `ab-test-readout`, `search-terms-negatives` and
  `seo-content-brief`, after a review of recorded answers; prompts and
  fixtures are unchanged, so recorded responses stay valid and can be
  regraded. A/B test: the critical criterion now says that the expected
  count per variant under the planned 50/50 split (half of the visitors
  received, 11,750) is derived from the results and is not an invented or
  misquoted plan figure; a judge had failed one readout and passed two on
  the same sentence. The judge's reference carries that count
  (`task_references.VERSION` 3). Search terms: the band on A3, the cost of
  the irrelevant search terms, is now absolute, full credit within $0.50
  and none from $400 off, in place of 2% to 25%. At 2% (about $33) full
  credit went to an answer that left out the cheapest irrelevant search
  term ($26.80), and to one that counted any one of 94 relevant terms; the
  cheapest row in the report costs $1.03, so no single-row error now earns
  full credit. Content
  brief: a URL the brief proposes for the new article itself is exempt from
  the rule that every internal URL must be in the page list.
- Answers: a task may set `"single_number": true` in `answers`. Its answer
  block is then the run of answer lines with the most answers; between runs
  of the same length, a run most of whose lines are the number alone over
  one that is not, then the one with more lines that read as a number, then
  the later one. So a labelled line in a note, or a notes list that repeats
  every label, cannot override a block written as asked, and a final block
  that marks its corrected line still replaces the draft before it. A line
  is an answer only when it carries exactly one number, so a line with
  working on it (`A1: 749 / 12,480 = 6.00%`) is left unparsed instead of
  being read as its first number; a label with nothing after it stays blank;
  and a minus sign is read whether typed as a hyphen, U+2212 or a leading en
  dash. `eval_runner/README.md` lists what is left unparsed on purpose, and
  the one shape the block rule still misreads. The 21 earlier tasks do not
  set it and parse exactly as before.
- Judge: `judge_source_reference` now also returns reference totals for the
  six new tasks, computed from the sources in the recorded prompt.
- Grade: `grade --current-rubric` can apply a rubric fix to a run made
  through an agent harness (`claude-code`, `magister-agent`), whose recorded
  prompt wraps the task in a preamble and so never hashes to the direct
  assembly. The saved prompt, tied to the attempts by its hash, is accepted
  when it ends with `Task:` and then the whole direct assembly of the
  current task, text and every source, with nothing after it. A task that
  has since been changed or cut down, and every other harness, is refused as
  before.
- Report: a run graded with the current task files is reported with each
  task's current split, so a task moved out of holdout since the run is not
  shown as held out. The report, `README.md` and `eval.py` now say of the
  holdout split what is true: it is kept out of tuning, and `docs/TASKS.md`
  records which holdout tasks have had results read.
- Harness: `claude-code` runs the tasks through headless Claude Code and
  writes the same run directory as `direct-api`, so the judge and the report
  are unchanged (`python -m eval_runner.claude_code run`). Two arms: the
  stock agent, and with a skills plugin installed (`--plugin-dir`, the model
  decides what to open). `--mcp-config` attaches MCP
  servers. Each attempt gets its own working, configuration and home folder,
  the supplied sources as files, and Claude Code's shell sandbox (writes
  inside the attempt, network to the package registries only). Two things
  the first runs taught, both now handled: with nobody to approve it Claude
  Code held a script written to `$TMPDIR` and the agent computed by hand, so
  the sandboxed shell is allowed outright; and an agent that knows the real
  date called the dated fixtures stale and was marked down for an
  unsupported date, so the shared preamble says to treat the sources as
  current. `scripts/compare-arms.py` puts graded runs side by side per task
  with a paired sign-flip test over tasks.
- Harness: `claude-code` attempts are isolated from each other. Claude Code
  gives sandboxed shell commands a temp folder every session on the machine
  shares whenever the one it is handed has a long path, so parallel attempts
  were writing their scripts into one folder, and the shell could read other
  attempts' folders and the API key. Each attempt now has short private
  folders under `/tmp` (the run checks afterwards that the shell used them
  and records an error if it did not), a sandbox that cannot read the
  operator's home, the shared temp folders or another attempt, its own copy
  of any plugin, and no API key in the shell's environment.
- Harness: `claude-code` fixes from an independent review, none of which
  changes a recorded score. Stopping a run (Ctrl-C, `kill`, a closed
  terminal) now ends its sessions, removes the attempts' folders and writes
  the records; before, sessions ran on for up to the timeout each and
  nothing was recorded. An exception in one job is that attempt's error
  instead of the loss of every attempt. An attempt whose MCP server was not
  connected at session start is an error. The model check accepts the
  requested id or its dated name only (`claude-opus-5-5` passed as
  `claude-opus-5`). The shell is denied what the run keeps outside the home
  folder (the checkout, the tasks, an MCP config, given files), and MCP
  credentials are redacted like the API key, in the reply file too. Sessions
  load their own (empty) user settings only (`--setting-sources user`): a
  `CLAUDE.md` in a folder above an attempt was loaded and obeyed, and the
  attempts sit under a temp folder anyone on the machine can write to; the
  plugins, skills, tools and sandbox a session reports are the same either
  way. A given file that would replace a supplied source, in any case, stops
  the run before the first session. A run started with `nohup` survives its
  terminal closing, and a stop also ends the shell commands a session
  started (each runs in a process group of its own and outlived it). Files
  the agent wrote are kept with credentials taken out; a folder it locked
  no longer fails the attempt or stays behind in `/tmp`. A server still
  connecting when a session started counts once one of its tools answers. A
  retried attempt's cost is marked a lower bound. Plugin arms record
  `skills_included: false` (the report printed "Skills in prompt: yes" for
  an installed plugin). `compare-arms.py` averages as the grader does.
- Harness: `claude-code --files-dir DIR` saves a folder's files into every
  attempt's working folder and names them in the prompt: the arm where a
  person hands the agent their own exports. `MARKETING_BENCH_TASKS_DIR`
  points `load_tasks` at a task set kept outside the repository, for tasks
  whose answers are a brand's real numbers.
- Harness: `claude-code --name-skills` is gone. It named in the prompt the
  skills each task was written against, but choosing the right skill is
  part of the task, so the benchmark no longer offers an arm that does it
  for the agent. The stock arm and the plugin arm (`--plugin-dir`, the
  model decides what to open) send the same prompts and record the same arm
  names as before. New runs no longer write `agent.skills_named_in_prompt`;
  runs that have it still grade and report as before.
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
