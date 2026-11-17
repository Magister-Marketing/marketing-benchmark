# 2026-11-16: the tasks through real agents, and what a connection is worth

Two experiments on one day. Same model throughout (Claude Haiku 5.5, high
effort), same judge (Claude Sonnet 5.5), three attempts per task, zero judge
failures and zero attempts without an answer in every run reported here.

Until today the board compared the Magister agent with a model called once
over the API. That call has no shell, no files and no search, so it was a
floor, not a comparison with an agent a person can use. These runs replace it
with Claude Code.

## 1. The 20 closed-book tasks, four agents

| | Claude Code | + skills installed | + skills named | Magister |
|---|---:|---:|---:|---:|
| Score (0-100) | 93.8 | 94.0 | 94.5 | **97.0** |
| Tasks passed on all 3 runs | 8/20 | 10/20 | 10/20 | 9/20 |
| Attempts passed | 37/60 | 38/60 | 39/60 | 42/60 |
| Attempts that opened a skill | 0 | 2 | 60 | 60 |
| Cost, 60 attempts | $0.53 | $0.62 | $0.70 | $1.12 |
| Seconds per attempt | 60 | 70 | 69 | 104 |
| Model calls per attempt | 1.6 | 1.6 | 2.6 | 3.6 |

- **Claude Code**: headless Claude Code as shipped (shell in its sandbox, file
  tools, web search), nothing installed.
- **+ skills installed**: the same, with the marketingskills plugin (47
  skills, pin `4270283`) installed the way a user installs it. The model
  decides what to open.
- **+ skills named**: the same, and the prompt names the skills each task was
  written against. The best case for skills.
- **Magister**: the Magister agent on a test stack built from its `main`
  (`7f6aa08`), one fresh chat per attempt.

Magister against each other arm, per task (the tasks are the sample; three
attempts at one task are not three tasks):

| Against | Mean difference | Ahead / level / behind | p (paired sign-flip) |
|---|---:|---:|---:|
| Claude Code | +3.2 | 9 / 6 / 5 | 0.10 |
| + skills installed | +3.1 | 9 / 5 / 6 | 0.23 |
| + skills named | +2.6 | 6 / 9 / 5 | 0.36 |

What this shows, and what it does not:

- **Magister has the highest score, and 20 tasks do not settle it.** The
  lead over stock Claude Code is 3.2 points with nine tasks ahead and five
  behind; a difference that size would turn up by chance about one time in
  ten. On tasks passed in all three runs the four arms are level (8 to 10).
- **Where Magister is ahead**: `ad-performance-analysis` (+26.6),
  `ads-ledger-analysis` (+20.0, the only arm with no invented figure in any
  attempt), `launch-capacity-trap` and `unsupportable-claims-brief` (+7.4
  each), both landing-page tasks (+6.7 and +5.3: Claude Code wrapped the HTML
  in a Markdown fence in all 18 attempts, which the task forbids),
  `tracking-audit` (+6.6).
- **Where it is behind**: `analytics-source-conflict` and `blog-post` (-7.4
  each), `source-conflict-repair` (-3.7), `shopify-meta-capi` (-3.0, 0 of 3
  attempts passed), `factorial-ad-test` (-2.6).
- **Installing skills did nothing by itself.** With the plugin installed and
  nothing said, Claude Code opened a skill in 2 of 60 attempts. Named in the
  prompt it opened one in 60 of 60, and the score did not move (94.5 against
  93.8, p = 0.72). Magister's agent opened a skill in 60 of 60 without being
  told which.
- **Magister costs about twice as much and takes 1.7 times as long** per
  attempt as stock Claude Code on these tasks.
- **The agent, not the skills, is most of the old gap.** On 2026-10-08 the
  same model called once over the API scored 87.2, and 91.7 with skill text
  pasted into the prompt (different day, no agent preamble, so read these as
  context, not as a fifth arm). The largest single change is
  `ads-ledger-analysis`: 0.0 and 13.3 over the API, where the model ran out
  of output reading 784 pasted rows; 80.0 in stock Claude Code, which wrote a
  script and got all five figures exactly in every attempt.

`ads-ledger-analysis-decoy` needs a prior chat turn, so only Magister ran it
(100.0, 3 of 3); it is left out of every figure above.

## 2. Connected-data tasks: what the connection is worth

Every closed-book task hands over its facts, so a connector to a brand's
accounts cannot help with them. Eight new tasks ask about a brand's own
Search Console and Analytics instead: three exact figures over fixed past
dates, and one recommendation. The figures are graded against the product's
own numbers; a figure the agent could not get must be written `unavailable`,
and a guess presented as the brand's number fails the attempt. The brand is
Magister's own site, so the task files and answers are not in this
repository.

| | Claude Code, no access | + hand exports | + Magister MCP | Magister |
|---|---:|---:|---:|---:|
| Figures exactly right | 0/72 | 72/72 | 72/72 | 72/72 |
| Figures written `unavailable` | 72 | 0 | 0 | 0 |
| Guesses presented as figures | 0 | 0 | 0 | 0 |
| Recommendation met its criterion | 24/24 | 15/24 | 9/24 | 8/24 |
| Score (0-100) | 33.3 | 93.7 | 89.6 | 88.9 |
| Seconds per attempt | 15 | 23 | 23 | 126 |
| Cost, 24 attempts | $0.09 | $0.12 | $0.14 | $0.49 |

- **No access**: Claude Code alone. It looked for the data, found none, and
  said so in all 24 attempts. It never guessed.
- **+ hand exports**: the same data exported by hand as nine CSV files (one
  per report and date range) and put in its working folder. What a person
  without a connector does.
- **+ Magister MCP**: Claude Code with Magister's MCP server attached, read
  scope only. It found the tools, picked the brand and made the reads itself.
- **Magister**: the Magister agent on the same brand.

What this shows:

- **With the connector, Claude Code answered every figure exactly, from the
  live accounts, in about 23 seconds and half a cent a question.** Without
  it, it could answer none.
- **Hand exports do as well on the figures.** The connector's gain over them
  is the nine exports nobody had to make, not accuracy.
- **The recommendations are where the arms differ.** The criterion fails a
  recommendation that names nothing specific or states a cause the figures
  cannot show. The arms that could pull more data said more and were marked
  down more (9, 15 and 16 of 24 failed). The no-access arm passes it by
  recommending nothing, which is also why its score is 33 and not 0.
- **The Magister agent got the same figures five times slower** than Claude
  Code with the connector, at three and a half times the cost.

## Method

- `eval_runner/claude_code.py` runs each attempt in its own working,
  configuration, home and temp folder with nothing of the operator's loaded,
  the task's sources saved as files, and Claude Code's shell sandbox on
  (network to the package registries only). Both agent harnesses wrap the
  task in the same preamble: draft only, treat the sources as current,
  deliver the answer in the reply.
- Three instrument faults were found and fixed before these runs, and the
  runs made before each fix were thrown away: a shell command held for an
  approval nobody could give; the judge failing an agent for knowing the real
  date; and parallel attempts sharing one temp folder.
- The Magister arm ran on a test stack at `7f6aa08`. Another evaluation used
  the same fixture between these runs; a lease keeps runs on a fixture from
  overlapping, and the stack's code did not change.
- `scripts/compare-arms.py` produced the tables and the paired test.
- An independent review of the runner afterwards read all 535 saved Claude
  Code sessions. Nothing it found changes a figure here: no attempt was
  retried, every session ran the requested model, all 24 attempts of the MCP
  arm reported the server connected when the session started, and no key or
  token is in any run file. Its findings are fixed in the runner.

Limits: one model; 20 tasks and 8 tasks; a judge from the candidate's own
family; the connected tasks cover one brand and grade the figures more firmly
than the advice.

## Runs

| Arm | Run |
|---|---|
| Claude Code | `20261116-220214-091c8677` |
| + skills installed | `20261116-220216-579f1c95` |
| + skills named | `20261116-220218-8dc8daa4` |
| Magister | `20261116-215702-cdbd380f` |
| Connected, no access | `20261116-232947-6f53802a` |
| Connected, hand exports | `20261116-232949-06dd77c0` |
| Connected, Magister MCP | `20261116-232952-bc8416ac` |
| Connected, Magister | `20261116-233303-f7127c27` |
