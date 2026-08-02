# Agent-system comparison validation

## Status

The portable benchmark implementation is complete and validated locally. The
first vanilla Claude Code and Codex CLI baseline runs have been dogfooded
against synthetic fixtures. The Magister treatment remains intentionally
pending until PR #890 is deployed only to the Team+Test canary; no production
user or model default was changed by this work.

## Requirements coverage

| Product behavior | Implementation | Validation |
|---|---|---|
| Explicit eval types and per-type scores | Scenario v2 `evaluation_types`, category grades, and planned-denominator scorecards | Schema/catalog validation and `test_scorecards_use_planned_attempts_and_macro_average_scenarios` |
| Honest execution and end-to-end denominators | Expected-attempt left join counts missing, infrastructure, and contaminated attempts as failures | Scorecard unit test and generated dogfood scorecards |
| Matched baseline/treatment comparison | `marketing-benchmark compare` validates settings, observed model, content hashes, seed, fixture, clock, and environment parity | `test_agent_system_comparison_pairs_runs_and_reports_uplift` |
| Separate replay and live integration evidence | Comparison blocks are partitioned by environment mode | Comparison unit test and GA4 replay dogfood run |
| Cross-run blind judging | `compare-judge-plan` includes only matched pairs where both sides passed end to end; `compare-judge-import` retains the hidden identity map and rejects duplicate judges | `test_comparison_blind_judging_uses_only_passing_cross_run_pairs` |
| Vanilla Claude Code adapter | Exact fixture manifest, deferred tool-discovery normalization, portable file-backed UI bridge | `test_claude_adapter_stages_fixture_manifest_and_hides_tool_discovery` plus paid dogfood |
| Vanilla Codex CLI adapter | Ephemeral clean execution, explicit model/effort/verbosity, synthetic replay MCP, normalized command/file/MCP events, fail-closed command classification | `test_codex_adapter_uses_clean_exec_and_normalizes_skill_reads` plus paid dogfood |
| Provider-neutral open-core boundary | No Magister credentials, identities, endpoints, or private adapter code in the package | `test_clean_room_boundary_contains_no_private_magister_code` and `marketing-benchmark boundary-check` |
| Scan-friendly public evidence | Public Markdown/JSON begins with execution, end-to-end, category, blind-preference, time, and cost rows; no weighted overall score | `test_public_report_is_plain_language_and_keeps_audit_link` and generated reports |

## Local verification

The provider-free verification gate is:

```sh
make PYTHON=.venv/bin/python check
```

It compiles the package, validates the bundled catalog and JSON schemas, runs
the offline conformance and clean-room boundary checks, executes the test
suite, and builds both source and wheel distributions. Paid provider runs are
opt-in and never execute in CI.

## Dogfood protocol

Each vanilla runtime is run three times on the same compact protocol:

1. general chat: channel prioritization without skills or tools;
2. skill and UI: Meta creative review requiring a skill read, artifact, and
   structured review UI; and
3. integration replay: GA4 diagnosis requiring a skill read and synthetic,
   read-only MCP tool calls.

The frozen scenarios, rubrics, fixtures, environment clocks, and repetition
numbers are controls. Results are reported as thin baseline evidence, not as a
production routing decision. Adapter defects found during dogfooding are kept
in raw artifacts but excluded from model scores and disclosed in the curated
results report.

## Remaining canary validation

After Magister PR #890 and its migration are available only to the Team+Test
canary, run the identical protocol through the private Magister adapter with
the same underlying model and requested settings. Export only sanitized
evidence, run the offline parity check and comparison, then create and import
identity-blinded judge packets for pairs where both systems passed end to end.
This is required before making any Magister uplift claim or widening rollout.

This feature is a CLI and Markdown/JSON reporting workflow, so cloud browser
visual validation is not applicable. The pull request had no review comments
requiring additional validation at the time this document was written.
