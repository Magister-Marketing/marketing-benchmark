# Changelog

## Unreleased

- Results: re-graded the published runs under the PR #11 scoring
  (2026-09-02) so `docs/results/` and the leaderboard no longer mix the two
  regimes. 15 runs, 695 judge calls, $27.64, zero judge failures — same
  judge (`claude-sonnet-5`), each run's recorded rubric snapshot, a fresh
  judge sample; `agreement.judge-b.json` refreshed offline wherever a
  second-judge label exists. No oracle override fired on any published run.
  The 08-27 pilot moved by rule (the Magister ledger reply is recorded as
  `self_report: blocked` and keeps its negatives, 0.0 → 8.3; the
  un-fixed-fixture tracking-audit attempts lift from the 40 cap to 94.1 now
  that `no_false_positives` is not critical); every other movement is a
  single-criterion judge flip on the fresh sample — 96 of ~6,500
  judge-scored criteria, 49 down and 47 up — and the docs say so where a
  figure moved. **Still on the pre-#11 grading:** the 08-31 three-tier rerun
  (`20260831-212016` / `-212031` / `-212036`, the site's featured board;
  re-grading was stopped before those ran), the 08-25 three-arm ablation
  (`20260825-040844` / `-054015` / `-061339` / `-064613`), the 08-19 / 08-20
  runs (no recorded rubric snapshot, so a default-label regrade is not
  possible), and the 07-31 / 08-01 runs (no local run directories). The
  "recomputed" column below is the old judgments under the current report
  code — it isolates the report-time rules from the re-judge.

| Run | Model | Tasks passed (before → after) | Score 0–100 (published → recomputed → re-graded) |
|---|---|---:|---:|
| `20260825-170012-9154f22d` | gpt-5.6-luna-medium | 12/18 → **12/18** | n/a → 94.2 → **95.4** |
| `20260825-170012-9154f22d` | gpt-5.6-terra-medium | 15/18 → **14/18** | n/a → 97.8 → **97.2** |
| `20260825-170012-9154f22d` | gpt-5.6-sol-medium | 14/18 → **14/18** | n/a → 97.8 → **97.8** |
| `20260825-170012-9154f22d` | claude-sonnet-5 | 12/18 → **11/18** | n/a → 94.6 → **94.7** |
| `20260825-170012-9154f22d` | claude-opus-5 | 18/18 → **18/18** | n/a → 100.0 → **100.0** |
| `20260825-205808-a4d07885` | gpt-5.6-luna-medium | 12/18 → **11/18** | n/a → 96.3 → **95.6** |
| `20260825-205808-a4d07885` | gpt-5.6-terra-medium | 13/18 → **13/18** | n/a → 95.7 → **95.7** |
| `20260825-205808-a4d07885` | gpt-5.6-sol-medium | 13/18 → **13/18** | n/a → 96.5 → **96.5** |
| `20260825-205808-a4d07885` | claude-sonnet-5 | 9/18 → **9/18** | n/a → 89.5 → **90.8** |
| `20260825-205808-a4d07885` | claude-opus-5 | 15/18 → **15/18** | n/a → 98.1 → **98.6** |
| `20260825-205808-a4d07885` | claude-haiku-4-5 | 4/18 → **4/18** | n/a → 86.0 → **85.8** |
| `20260825-222810-a1437fef` | gpt-5.6-luna-medium | 12/18 → **11/18** | n/a → 95.2 → **94.2** |
| `20260825-222810-a1437fef` | gpt-5.6-terra-medium | 12/18 → **13/18** | n/a → 94.2 → **96.3** |
| `20260825-222810-a1437fef` | gpt-5.6-sol-medium | 13/18 → **13/18** | n/a → 95.1 → **95.1** |
| `20260825-222810-a1437fef` | claude-sonnet-5 | 9/18 → **7/18** | n/a → 89.9 → **89.5** |
| `20260825-222810-a1437fef` | claude-opus-5 | 13/18 → **11/18** | n/a → 94.8 → **94.4** |
| `20260825-222810-a1437fef` | claude-haiku-4-5 | 4/18 → **5/18** | n/a → 83.3 → **85.9** |
| `20260825-230519-539e42f9` | gpt-5.6-luna-medium | 10/18 → **10/18** | n/a → 94.5 → **94.5** |
| `20260825-230519-539e42f9` | gpt-5.6-terra-medium | 12/18 → **12/18** | n/a → 95.9 → **95.2** |
| `20260825-230519-539e42f9` | gpt-5.6-sol-medium | 15/18 → **15/18** | n/a → 97.8 → **97.8** |
| `20260825-230519-539e42f9` | claude-sonnet-5 | 9/18 → **9/18** | n/a → 94.7 → **94.1** |
| `20260825-230519-539e42f9` | claude-opus-5 | 13/18 → **13/18** | n/a → 95.5 → **95.2** |
| `20260825-230519-539e42f9` | claude-haiku-4-5 | 5/18 → **5/18** | n/a → 87.9 → **84.1** |
| `20260825-234438-8373ba31` | gpt-5.6-luna-medium | 10/18 → **10/18** | n/a → 91.3 → **91.3** |
| `20260825-234438-8373ba31` | gpt-5.6-terra-medium | 10/18 → **11/18** | n/a → 94.5 → **94.7** |
| `20260825-234438-8373ba31` | gpt-5.6-sol-medium | 12/18 → **13/18** | n/a → 94.7 → **95.9** |
| `20260825-234438-8373ba31` | claude-sonnet-5 | 10/18 → **11/18** | n/a → 93.0 → **92.6** |
| `20260825-234438-8373ba31` | claude-opus-5 | 12/18 → **10/18** | n/a → 93.1 → **92.4** |
| `20260825-234438-8373ba31` | claude-haiku-4-5 | 5/18 → **6/18** | n/a → 85.3 → **86.8** |
| `20260826-052545-86a467c8` | claude-sonnet-5 | 8/18 → **8/18** | n/a → 93.4 → **92.9** |
| `20260826-052545-86a467c8` | gpt-5.6-terra-medium | 11/18 → **10/18** | n/a → 94.7 → **94.3** |
| `20260826-053858-0af06e7c` | magister-gpt-5.6-terra-medium | 14/18 → **12/18** | n/a → 96.3 → **95.3** |
| `20260826-212336-e68672f4` | gpt-5.6-sol-high | 13/18 → **13/18** | n/a → 96.2 → **96.7** |
| `20260826-212336-e68672f4` | claude-opus-5-high | 13/18 → **14/18** | n/a → 96.7 → **97.1** |
| `20260826-212341-34f65925` | gpt-5.6-sol-high | 13/18 → **14/18** | n/a → 96.0 → **96.7** |
| `20260826-212341-34f65925` | claude-opus-5-high | 12/18 → **12/18** | n/a → 95.1 → **95.6** |
| `20260826-212643-62e39f5c` | magister-gpt-5.6-sol-high | 13/18 → **13/18** | n/a → 94.4 → **93.9** |
| `20260826-212643-62e39f5c` | magister-claude-opus-5-high | 13/18 → **12/18** | n/a → 95.4 → **94.2** |
| `20260827-014657-a656de1b` | gpt-5.6-sol-medium | 0/2 → **0/2** | 65.8 → 92.9 → **92.9** |
| `20260827-014659-45db0d35` | gpt-5.6-sol-medium | 1/2 → **1/2** | 70.0 → 97.0 → **97.0** |
| `20260827-014910-b4ef29d0` | magister-gpt-5.6-sol-medium | 1/2 → **1/2** | 50.0 → 50.0 → **54.1** |
| `20260827-015441-c29e75ca` | gpt-5.6-sol-medium | 1/1 → **1/1** | 100.0 → 100.0 → **100.0** |
| `20260827-015442-c4d7464f` | gpt-5.6-sol-medium | 1/1 → **1/1** | 100.0 → 100.0 → **100.0** |

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
