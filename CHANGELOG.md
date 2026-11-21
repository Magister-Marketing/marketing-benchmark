# Changelog

## Unreleased

- Tasks: `brief-amendment` (development split, experimental area): the
  signed-off launch brief and its product sheet arrive one turn earlier,
  "for reference, the request follows", through the existing `decoy`
  mechanism (the brief is the earlier message, the sheet its fixture); the
  request is the client's amendment of six changes (launch date, a withdrawn
  product, two price changes, a new market with its budget, a withdrawn
  claim). The reply is a note and three files (plan, emails, ads) for three
  markets. It isolates applying a change everywhere it reaches and nowhere
  else: three knock-ons the amendment does not mention (the bundle the
  withdrawn kettle belongs to, the item each launch email features, a teaser
  moved off a UK holiday) and a look-alike (a price that starts after
  launch). `decoy.answers` holds what the brief-alone plan scores on each of
  the 12 banded checks; no change to the mechanism or its validation was
  needed. 16 of its 17 checks are a program's. Lists `harnesses`
  (`direct-api`, `magister-agent`).
- Tasks: `launch-workflow-chain` (development split, experimental area): a
  paid social launch built as six dependent deliverables in one reply, from a
  build brief, a 22-segment audience table and a 20-product catalogue: the
  segments six ordered rules choose (8), the campaigns and ad groups a naming
  convention builds (8 and 30), one ad per ad group under character limits
  with only its own product's facts, a tracked URL per ad group built from
  the names, daily budgets shared by segment size, and a pre-launch count.
  It isolates consistency along the chain: the files after the structure are
  checked against the reply's own structure (a name, product or count that
  drifts between files fails that file's agreement check, and only that),
  and the structure and segments against the oracle. 13 of its 14 checks are
  a program's. Oracle and reader in the new `eval_runner/task_facts_experiments.py`,
  hooked into `bench.measured_facts`; generator beside the fixtures; tests in
  `tests/test_tasks_experiments.py`.
- Report: a decoy task's cost and time include its earlier turn, for every
  harness, since the task as given is both messages. They were the task
  turn's alone, so the published cost and time of `ads-ledger-analysis-decoy`
  understated what it took (in three Magister runs of 2026-11-20/21 the
  earlier turn was a third to a half of the cost). `attempt_cost_usd` and the
  new `attempt_latency_seconds` add the `decoy_*` cost and latency (the
  bridge's `latency_seconds` has the turn subtracted, so the sum is the whole
  attempt), and everything published reads them: each run, the metrics, the
  per-model totals, `compare-arms` (which now reads the report's per-run
  figures, not the attempts') and `bench-model`'s estimate (which also weighs
  both turns' tokens). The share is shown as `decoy_cost_usd` and
  `decoy_latency_seconds`. A turn with no recorded cost or time makes the
  total unknown, never lower. Other tasks are unchanged.
- Tasks: `launch-timeline` (development split, strategy area): schedule a
  24-task product launch under written rules (working days, three holidays,
  dependencies, owners who take their tasks one at a time in ID order, two
  not-before dates), then give the launch date, the critical path, the slack
  of three named tasks, whether the promised date holds and the smallest set
  of optional tasks to cut to make it. The oracle schedules the plan as a
  longest path and tries every set of optional tasks; the test schedules it
  again day by day and measures slack by delaying each task. 13 of its 14
  checks are a program's. The `launch` skill is vendored unchanged at
  `2c38021`.
- Tasks: `competitor-comparison` (development split, strategy area): a
  comparison table of 12 attributes for Tallyhour and five fictional
  competitors, read from six saved pricing pages under a brief's rules, and a
  verdict on five draft claims. Every cell is checked: the oracle reads each
  one out of its page through a declared source (a plan-table cell, a
  sentence, an FAQ answer that overrides the table, or a term the page never
  uses) and applies the monthly-basis and `not stated` rules. 13 of its 14
  checks are a program's, one per trap group and one per claim. The
  `competitor-profiling` skill is vendored unchanged at `2c38021`.
- Tasks: `channel-budget-allocation` (development split, strategy area): split
  a $128,000 quarter across six channels in whole $5,000 blocks from
  diminishing-returns forecasts, under a lead cap the account executives set
  on two channels, a monthly licence held all quarter, a 4-block minimum
  order and a contracted commitment. Two CSV files and five labeled figures;
  13 of its 14 checks are a program's, against the one best split the oracle
  finds by trying every split (`eval_runner/task_facts_strategy.py`, hooked
  into `measured_facts`). Its fixtures are written by
  `scripts/gen_tasks_strategy.py`. The `ads` skill is vendored unchanged at
  the same marketingskills pin (`2c38021`) for its "with skills" arm.
- Tasks: `seo-content-brief` hardened (prompt 4, rubric 5; same id). Every
  setup passed all 15 checks of rubric 4. The choice of topic is now a
  computation across a 455-keyword export: winnable clicks are a keyword's
  searches times the click-through rate of third place less the rate at its
  current rank (a table in the prompt), keywords already ranking third or
  better and keywords of the wrong intent or above the difficulty limit are
  removed, and the topic with the most winnable clicks wins. The topic with
  the most searches, the most eligible searches, and the most clicks when the
  clicks a ranking keyword already gets are left in is matcha every time; the
  target is oolong tea, whose biggest keyword ranks fifth and so is not the
  primary. Six labeled figures (A1-A6) and six labeled lines (topic, primary
  and four secondary keywords, working title, meta description, internal
  links) are checked by program: 12 of the 16 checks. Skills are now
  `content-strategy` (vendored unchanged from `2c38021`) and
  `site-architecture`. `task_references.VERSION` is 4, since the judge's
  reference for this task changed; its data tests moved from
  `tests/test_more_tasks.py` to `tests/test_tasks_seo.py`.
- Tasks: `blog-post` hardened (prompt 3, rubric 4; same id). Every direct
  setup passed all nine checks of rubric 3. The facts now come from a dated
  `sources.md` in which later sources replace four figures of earlier ones,
  each earlier source listed after the one that replaces it: the service
  menu's price ($89 to $95, and the prompt no longer states it), the 2024 tip
  sheet's filter interval, and the interim call summary's count and shares.
  The post must use at least three figures from the sources and state no
  price, percentage, number of calls or span of time or distance that is not
  a current one, link exactly the eight pages a written rule picks from a
  139-page `site_map.csv` (live, tagged furnace, most sessions, a tie at
  eighth place broken by URL; redirects, noindex pages, a dead page, a page
  tagged furnace-parts and furnace URLs tagged otherwise all have more
  sessions), with each page's keyword as the link text, and link its call to
  action to the booking page with the current price in the link text. 11 of
  the 14 checks are a program's (`eval_runner/task_facts_seo.py`). The Brightline brand fixtures
  stay for the tasks that still use them; the archived version 1 prompt is
  dropped, since rubric 4 cannot grade it.
- Tasks: `seo-titles-meta` (development split): a title and a meta
  description for each of the 99 indexed pages of a 113-page inventory, under
  written rules, as `titles_meta.csv`, with three labeled counts. All 16
  checks are a program's: limits, suffixes, keywords, prices, attributes,
  counts and duplicates, page by page. The trap is the keyword rule: when
  pages share a primary keyword the one with the most clicks keeps it (ties
  by page type, then id) and the others target their secondary keyword
  without the one they gave up: 14 pages concede, among size variants, a
  three-way tie and a guide that out-clicks its category; four noindex pages
  with more clicks take no part, and "dog bed" is not "dog beds".
  Out-of-stock products carry a price in the inventory that may not be shown.
- Tasks: `seo-redirect-map` (development split): a shop moving platform on the
  same domain. A 327-URL crawl of the old site, the new site's URL list and
  ten migration rules in order in; a `redirects.csv` of 301s and 410s and four
  labeled counts out. All 15 checks are a program's, counted row by row
  against an oracle that reads only the fixtures
  (`eval_runner/task_facts_seo.py`, hooked into `bench.measured_facts`; the
  fixtures come from `scripts/gen_tasks_seo.py`). The traps: retired products
  whose slug a successor with another SKU took, colour and size pages the
  new site folds into one product page, old redirects and the new site's own
  redirects to follow to a live page, parameter URLs with
  backlinks, 404s with inlinks but no backlinks, slugs with a number in front
  that is not a `YYYY-MM-` date, and retired products with no signal at all.
  Vendors `seo-audit` unchanged from marketingskills `2c38021` for its "with
  skills" arm.
- Tasks: `ab-test-readout` hardened (prompt version 4, rubric version 5; the
  id is kept, as the 35-task board plan asks). Every setup passed all 17
  checks of version 3. The fixtures are now 616 daily rows by device and
  traffic source over 28 days (32 KB) and a plan with written decision rules:
  mobile is split 70/30 by design, so the pooled lift (+11.7%) is up while
  variant B is down on desktop (-1.7%) and mobile (-6.9%); the first week's
  lift (+15.7%) fades, and the plan leaves that week out of every figure; a
  cache problem in days 1-3 fails the sample-ratio check over 28 days but not
  over the window; QA visits forced into variant B (source `internal`, one
  row a day per device) must come out, or the split fails and every lift
  moves; the billing-ticket guardrail is breached over the window (+27.5%,
  limit 20%) and not over 28 days. Eleven banded figures, the last the number of the decision rule that
  decides (rule 3, do not ship). 12 of its 15 checks are a program's.
  `no_invented_data` is no longer critical: every figure it guarded is a
  banded check now, and the visitor counts it named carry the burn-in trap.
  The skills are `ab-testing` and `analytics`. Runs of version 3 cannot be
  regraded against this rubric (`--current-rubric` refuses a changed
  prompt). The task moved out of `scripts/gen_more_tasks.py` and
  `task_references.py` (whose `VERSION` is now 4) into
  `task_facts_conversion.py` and `fixtures/ab-test/generate.py`; the parser
  tests in `tests/test_more_tasks.py` read the version-3 task from
  `tests/data/ab-test-readout-v3.json`, the block they were written against.
- Tasks: `funnel-dropoff` (development split): a four-week checkout funnel
  by day, device, browser and step over ten segments (1,131 rows, 47 KB of
  sources), the analytics team's rules, a release log and ten suspected
  causes in; the day and place of the break, the conversion rate before and
  after, the orders and revenue lost and a ruling on each cause out, as 17
  labeled figures. Two double-firings must be halved first (every order row
  on 10-12 March; the Safari payment rows on the last three days, which left
  doubled make desktop and tablet Safari seem to break at the end of the
  export) and a crawler left out. Look-alikes: dips inside the normal range
  in four segments, a day and a four-day run below it that recover, and a
  change two days before the break. 14 of its 16 checks are a program's.
  Same layout as `test-plan-sizing`.
- Tasks: `test-plan-sizing` (development split): a 150-test backlog across
  twelve country storefronts, their settings, eight weeks of traffic for 72
  pages (576 rows, 36 KB of sources in all) and the team's experimentation
  rules in; a calendar file out, `test_calendar.csv`, with each test's page
  weekly users, sample size per variant, weeks, start week and status (run,
  too long, no slot), every row checked by program, and a short note for the
  growth lead. Traps spread through the data, one kind per test: 40 tests on
  storefronts that count sessions (each with its own users per session), 20
  on pages with a tracking-outage week to leave out, 26 lifts in percentage
  points, 22 tests on half their page's traffic; weeks round up; each
  storefront has its own freeze week and limit on tests at once, and one
  priority order runs over all of them (101 run, 33 too long, 16 no slot).
  Wrong rows are counted by kind of test (zero credit at 5), status and start
  week over every test (zero credit at 1), so each careless reading zeroes
  its own count and the two it cascades into. 8 of its 10 checks are a
  program's; `task_facts_conversion.facts_for` reads the file and is called
  from `bench.measured_facts`. The fixtures' generator sits beside them
  (`eval_runner/fixtures/test-plan-sizing/generate.py`), the oracle is in
  `eval_runner/task_facts_conversion.py`, which `task_references` now
  consults for the judge's reference, and `tests/test_tasks_conversion.py`
  recomputes every target. Vendors `ab-testing/SKILL.md` unchanged from
  marketingskills `2c38021` (2.0.2) for the "with skills" arm.
- Tasks: `email-compliance-audit` (development split): the 150 live emails
  of a skincare brand before a platform move (110 marketing, 40
  transactional), a sending policy with six violation codes, a consent table
  of 17 audiences and the DNS records of seven sending domains in; a verdict
  per email, a fix per code and three labeled counts out. 116 violations sit
  in 87 emails, and every rule has look-alikes that pass. 12 of its 13
  checks are a program's: one per code over all 150 rows (zero credit at 3
  wrong) and exact counts. It lives in `eval_runner/task_facts_email.py`
  beside `email-send-calendar`, generated from counted features so that
  every trap occurs at least three times; `tests/test_tasks_email.py` reads
  the four fixture files with its own parser, recomputes every verdict and
  figure, and shows that each of 22 tempting misreadings of the policy
  changes at least three emails and scores zero on its code's check, with
  no check left at part credit.
- Tasks: `email-send-calendar` (development split): a 12-campaign plan, an
  800-subscriber export (six overlapping segments, join dates, pauses) and a
  calendar policy in; each campaign's send date, audience size and reason,
  every subscriber's February email count, and five labeled figures out. 12
  of its 13 checks are a program's, and every one of the 800 subscriber rows
  is checked. Audience sizes and counts are checked against the reply's own
  calendar, so a wrong date is charged once, to the dates. Its fixtures,
  oracle and checker live in `eval_runner/task_facts_email.py`
  (`python3 -m eval_runner.task_facts_email --check`), which
  `bench.measured_facts` calls; `tests/test_tasks_email.py` recomputes every
  pinned figure from the fixture files with its own scheduler and shows that
  a reply built from each of ten tempting wrong readings (campaigns taken by
  date, calendar weeks, only the days before, the cap per segment,
  unsubscribed people counted, clear days between teaser and launch, join
  dates or pauses ignored, a pause read as the whole month, a moved
  campaign's audience taken on its requested date) scores zero on every
  check it touches and full on the rest.
- Runner: the direct setups now run `ads-ledger-analysis-decoy`, so all 30
  development tasks are shared by the model alone, the model with the skills
  and Magister. A decoy task is one conversation of two calls to the same
  model with the same settings: call 1 sends only the look-alike message
  (`assemble_decoy_prompt`), call 2 sends that message, the model's own reply
  as plain text, and the task prompt as a single call has it (skills only on
  the "with skills" arm). Only call 2 is graded. A call 1 that fails, is
  empty, refused or cut off fails the attempt; the task is never sent alone.
  Call 1's tokens, cost and time are recorded under `decoy_*`, like the
  Magister bridge's decoy turn, and count in the task's cost and time (see
  the Report entry above). `retry` replays both calls. Validation now names the harnesses that can send a prior turn
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
