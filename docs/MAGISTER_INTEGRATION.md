# Magister integration

Marketing Benchmark and Magister should use one portable engine with a private
downstream host, not two independently evolving copies.

## Ownership boundary

Marketing Benchmark owns:

- schemas, planning, evidence, normalized traces, grading, judging, and reports;
- public candidates, rubrics, synthetic fixtures, and replay environments;
- Claude Code, Codex CLI, and subprocess/JSONL reference adapters;
- plugin contracts and conformance checks.

Magister owns:

- Team+Test identity and exact project/property allowlists;
- gateway transport, service-role session overrides, Supabase, and usage
  reconciliation;
- native Magister tool traces and the private JSON-render validator;
- internal model candidates, proprietary fixtures, deployment, and live
  acceptance commands.

## Transition

During private staging, Magister remains the canonical implementation while
this extracted repository is independently hardened. The cutover should be one
reviewed Magister change that:

1. Pins an exact Marketing Benchmark version or Git commit as an eval-only
   dependency.
2. Moves Magister-only adapters/environments into a private plugin package.
3. Registers the private plugins in `scripts/run-canary-agent-evals.py`.
4. Adds catalog layering so public replay packs and private candidates/live
   scenarios can be selected without copying either tree.
5. Records core, plugin, fixture, adapter, and runtime versions in every run.
6. Runs the public conformance suite against the private plugins.
7. Deletes the duplicate portable implementation only after parity tests pass.

## Matched public comparison

The public claim is a controlled comparison between two agent systems, not a
comparison between different models:

1. Freeze one agent-system experiment with the model, requested setting modes,
   scenario/fixture/rubric hashes, repetition keys, seed, replay clock, and tool
   responses held constant.
2. Run the baseline through `claude-code` or `codex-cli` in this repository.
3. Run the treatment through the Magister canary plugin on Team+Test. Keep the
   feature dark and allowlisted; do not send ordinary users through it.
4. Export only sanitized, normalized run evidence from Magister. Private
   identity, credentials, URLs, and live-property identifiers stay downstream.
5. Run `marketing-benchmark compare` with the two run directories and a
   reviewed treatment declaration.

The comparator rejects model, setting, hash, seed, or environment mismatches
and rejects completed attempts with unverified setting application. Its public
report shows baseline and treatment scores plus paired uplift separately for
execution, end-to-end completion, general chat, skill use, UI rendering, and
integrations. Reliability W–T–L is deterministic task completion; creative
blind preference remains a separate judging step.

Replay results should establish repeatable behavior first. Any later live GA4
acceptance must use the exact Team+Test property, read-only capabilities, a
second explicit operator confirmation, and a separate report. Live and replay
scores are never pooled.

After that cutover, portable changes land here first. Magister updates its pin
and private compatibility tests in a normal dependency-update pull request.

## Internal execution policy

- Run validation, conformance, and deterministic replay on relevant changes.
- Use three repetitions for screening and at least ten on discriminating cases
  before making a routing recommendation.
- Keep Team+Test live checks opt-in, low-cost, read-only, and outside ordinary
  CI.
- Never automatically change production defaults from a benchmark report.
- Keep private run evidence in Magister-controlled storage; do not commit it to
  this repository.
