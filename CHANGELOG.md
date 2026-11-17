# Changelog

## Unreleased

- Harness: `claude-code` runs the tasks through headless Claude Code and
  writes the same run directory as `direct-api`, so the judge and the report
  are unchanged (`python -m eval_runner.claude_code run`). Three arms: the
  stock agent; with a skills plugin installed (`--plugin-dir`, the model
  decides what to open); and with the task's own skills named in the prompt
  (`--name-skills`, the best case for skills). `--mcp-config` attaches MCP
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
  credentials are redacted like the API key, in the reply file too. A given
  file that would replace a supplied source, in any case, and a `CLAUDE.md`
  above the attempts' folders stop the run before the first session. A
  retried attempt's cost is marked a lower bound. Plugin arms record
  `skills_included: false` (the report printed "Skills in prompt: yes" for
  an installed plugin). `compare-arms.py` averages as the grader does.
- Harness: `claude-code --files-dir DIR` saves a folder's files into every
  attempt's working folder and names them in the prompt: the arm where a
  person hands the agent their own exports. `MARKETING_BENCH_TASKS_DIR`
  points `load_tasks` at a task set kept outside the repository, for tasks
  whose answers are a brand's real numbers.
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
