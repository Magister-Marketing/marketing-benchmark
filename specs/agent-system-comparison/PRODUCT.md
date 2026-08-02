# Agent-system comparison and capability scorecards

## Summary

Marketing Benchmark will compare a product agent harness with a vanilla agent
runtime on the same marketing work, then publish scan-friendly scores for
general chat, skill use, UI rendering, and integrations. The comparison must
make the treatment explicit, preserve auditable evidence, and never let strong
writing compensate for failed safety, tool, skill, or UI requirements.

## Problem

The current runner can compare model profiles inside one runtime, but it cannot
state how much an agent system such as Magister changes outcomes relative to a
first-party Claude Code or Codex baseline. Its reports expose many technical
axes, but readers cannot quickly see a score for each product capability or a
matched Magister-versus-vanilla delta.

## Goals

- Let Magister run the portable benchmark through a private adapter while the
  open repository runs the same tasks through vanilla Claude Code and Codex.
- Produce honest, matched evidence for the value added by the agent harness.
- Give public readers understandable per-capability results, sample sizes, and
  uncertainty without inventing one opaque quality number.
- Let third parties run the same protocol in their own repositories and compare
  their own agent systems without adding product-specific code to the core.

## Non-goals

- Predicting real campaign CTR, revenue, ranking, or conversion lift from
  synthetic tasks.
- Automatically changing a production model route from a benchmark result.
- Pooling replay fixtures with live integration evidence.
- Publishing Magister credentials, identities, endpoints, deployment logic, or
  proprietary system prompts in the open repository.

## Behavior

1. A benchmark operator can produce a baseline run through a supported vanilla
   runtime and a treatment run through a product-agent adapter. Each run remains
   independently executable and keeps immutable, redacted evidence.

2. The public distribution provides first-class vanilla adapters for Claude
   Code and Codex CLI. It also supports the provider-neutral subprocess/plugin
   contract for another agent. Magister remains a private downstream plugin and
   is never required to install or run the public package.

3. A comparison labels each system and declares what differs between them. At
   minimum the declaration identifies the runtime, system prompt or instruction
   layer, skills, UI bridge or catalog, tool environment, and integration
   orchestration. Undeclared differences make the comparison invalid.

4. The runner only calls a comparison matched when the baseline and treatment
   use the same underlying model, requested model settings, scenario version,
   prompt hash, fixture hash, rubric hash, repetition number, random seed, tool
   fixture, clock, and environment mode. The report lists every mismatch instead
   of silently pooling it.

5. The runtime and agent harness are the intended treatment in an
   `agent_system` comparison. The task facts, expected outcomes, deterministic
   gates, judge rubric, limits, and synthetic tool responses are controls and
   must remain identical.

6. Baseline agents receive enough portable task infrastructure to attempt the
   same outcome: frozen skill files, synthetic replay tools, declared artifact
   paths, and a provider-neutral UI submission contract. Magister may use its
   native skill loader, renderer, and integrations because those are part of
   the treatment, but it may not receive additional task facts or hidden oracle
   data.

7. Every scenario declares one or more evaluation types from:
   `general_chat`, `skill_use`, `ui_rendering`, and `integration`. A scenario can
   contribute to multiple scorecards when it genuinely exercises each type.

8. The report shows an **execution score** for every system: the percentage of
   planned attempts that completed without infrastructure failure or model/
   settings contamination. Missing attempts remain in the denominator.

9. The report shows an **end-to-end pass score** for every system: the
   percentage of planned attempts that executed successfully, passed every
   required deterministic gate, and passed every declared objective check. An
   infrastructure failure, contamination, missing result, safety violation, or
   failed required output counts as a failed end-to-end attempt.

10. The **general-chat score** is the macro-average of scenario completion
    rates for applicable chat scenarios. A pass requires honest completion,
    instruction and format compliance, grounding, safety, and all declared
    objective checks. Subjective helpfulness and writing preference remain a
    separate blind-review result.

11. The **skill-use score** is the macro-average of applicable planned attempts
    that read every required skill before dependent work and satisfy any
    scenario-specific skill gates. Merely mentioning a skill or receiving it in
    the prompt does not count as reading it.

12. The **UI-rendering score** is the macro-average of applicable planned
    attempts that submit a non-empty UI payload, pass the declared schema, and
    successfully render when a renderer check is part of the scenario. A valid
    markdown artifact does not substitute for required UI.

13. The **integration score** is the macro-average of applicable planned
    attempts that obey the tool contract, perform required operations, recover
    from declared errors when required, reach the hidden-oracle analytical
    result, ground claims in returned data, and avoid forbidden side effects.

14. Every score is displayed as both a percentage and a count (`passes / planned
    attempts`). Scenario-level rates are macro-averaged so a category with more
    cases does not dominate. Reports include a confidence interval when the
    sample supports one and visibly label thin evidence.

15. The public scorecard never creates a weighted overall quality score.
    End-to-end pass, the four capability scores, blind preference, latency, and
    cost remain separate. The ranking policy is reliability first, then
    eligible blind quality, then objective quality, then efficiency.

16. Creative or conversational quality is compared blindly only when both
    members of a matched pair passed all requirements that make their outputs
    eligible. If exactly one member fails, the report records a deterministic
    reliability win rather than asking a judge to prefer invalid work.

17. Blind results show wins, ties, losses, preference points, number of judged
    pairs, judge configuration, and agreement when multiple judges are used.
    Candidate and runtime identities remain hidden from the judge packet.

18. A paired comparison shows the treatment-minus-baseline change for every
    score, median or mean latency, and estimated provider cost. It shows the
    number of matched pairs and uncertainty; it does not describe a positive
    point estimate as a proven improvement when the interval is inconclusive.

19. Replay and live integration rows are always separate. A public report may
    show both, but it never combines them into one integration score or one
    routing recommendation.

20. Cost rows identify whether cost was provider-reported, locally estimated,
    or unavailable. Comparisons with different accounting methods carry a
    warning and never claim exact savings.

21. Invalid, incomplete, contaminated, and infrastructure attempts remain
    visible in reports. Operators can distinguish system reliability from
    conditional model quality; rerunning a failed cell creates new evidence and
    never overwrites the original run.

22. The public report begins with a compact table containing system name,
    execution, end-to-end, general chat, skill use, UI rendering, integrations,
    blind preference, time, cost, and paired uplift. A technical report retains
    scenario, gate, error, capability, tool, settings, and evidence detail.

23. Public reports state the exact task families, repetitions, models, settings,
    runtime versions, judge configuration, and limitations. They explicitly say
    that synthetic benchmark quality is not measured campaign performance.

24. A third party can install the package in another repository, scaffold the
    public fixtures and manifests, run a vanilla baseline, implement or select a
    plugin for its agent, and generate the same comparison report without
    modifying Marketing Benchmark core.

25. Private treatment runs can be exported only through a redaction boundary
    that excludes credentials, user/project identities, private endpoints,
    service-role data, and deployment configuration. The comparison consumes
    sanitized evidence and content hashes, not private runtime access.

26. Magister treatment execution stays restricted to the dedicated canary
    account and allowlisted project until an operator explicitly approves a
    wider rollout. Benchmark reporting never mutates production model defaults.
