"""Experiment planning and backend-neutral run orchestration."""

from __future__ import annotations

import datetime as dt
import math
import time
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .adapters.base import AgentAdapter, AttemptRequest, SettingsCapabilities
from .environments import (
    EnvironmentRequest,
    IntegrationEnvironment,
    NoopEnvironment,
)
from .evidence import append_jsonl, write_json, write_jsonl
from .events import tool_ledger_from_events, upgrade_tool_trace, validate_tool_trace
from .schema import Catalog, Experiment, ManifestError, Trial, build_trials, canonical_hash


@dataclass(frozen=True)
class RunPlan:
    experiment_id: str
    experiment_hash: str
    experiment_schema_version: int
    candidates: tuple[dict[str, Any], ...]
    scenarios: tuple[dict[str, Any], ...]
    trials: tuple[Trial, ...]
    generation_attempts: int
    maximum_model_calls: int
    estimated_judge_calls: int
    conservative_cost_ceiling_usd: float
    configured_cost_cap_usd: float
    deadline_seconds: int
    concurrency: int
    random_seed: int
    judge: dict[str, Any]
    comparison_mode: str
    forbidden_side_effects: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self, *, include_trials: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": 1,
            "canonical_contract_version": 2,
            "experiment_id": self.experiment_id,
            "experiment_hash": self.experiment_hash,
            "experiment_schema_version": self.experiment_schema_version,
            "candidates": list(self.candidates),
            "scenarios": list(self.scenarios),
            "generation_attempts": self.generation_attempts,
            "maximum_model_calls": self.maximum_model_calls,
            "estimated_judge_calls": self.estimated_judge_calls,
            "conservative_cost_ceiling_usd": self.conservative_cost_ceiling_usd,
            "configured_cost_cap_usd": self.configured_cost_cap_usd,
            "deadline_seconds": self.deadline_seconds,
            "concurrency": self.concurrency,
            "random_seed": self.random_seed,
            "judge": self.judge,
            "comparison_mode": self.comparison_mode,
            "forbidden_side_effects": list(self.forbidden_side_effects),
            "warnings": list(self.warnings),
        }
        if include_trials:
            result["trials"] = [asdict(trial) for trial in self.trials]
        return result


def _narrow_experiment(
    experiment: Experiment,
    *,
    candidate_ids: tuple[str, ...] = (),
    scenario_ids: tuple[str, ...] = (),
    repetitions: int | None = None,
) -> Experiment:
    """Apply only cost-reducing manifest subsets and hash the derived selection."""
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ManifestError("candidate filters contain duplicates")
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ManifestError("scenario filters contain duplicates")
    unknown_candidates = sorted(set(candidate_ids) - set(experiment.candidates))
    unknown_scenarios = sorted(set(scenario_ids) - set(experiment.scenarios))
    if unknown_candidates:
        raise ManifestError(
            "candidate filters are outside the reviewed experiment: "
            + ", ".join(unknown_candidates)
        )
    if unknown_scenarios:
        raise ManifestError(
            "scenario filters are outside the reviewed experiment: "
            + ", ".join(unknown_scenarios)
        )
    if repetitions is not None and not 1 <= repetitions <= experiment.repetitions:
        raise ManifestError(
            "repetitions override must be between 1 and the reviewed manifest value"
        )
    candidates = candidate_ids or experiment.candidates
    scenarios = scenario_ids or experiment.scenarios
    selected_repetitions = repetitions or experiment.repetitions
    derived_hash = canonical_hash(
        {
            "base_experiment_hash": experiment.manifest_hash,
            "candidates": candidates,
            "scenarios": scenarios,
            "repetitions": selected_repetitions,
        }
    )
    return replace(
        experiment,
        candidates=tuple(candidates),
        scenarios=tuple(scenarios),
        repetitions=selected_repetitions,
        manifest_hash=derived_hash,
    )


def plan_experiment(
    repo_root: Path,
    experiment_path: Path,
    *,
    candidate_ids: tuple[str, ...] = (),
    scenario_ids: tuple[str, ...] = (),
    repetitions: int | None = None,
) -> RunPlan:
    catalog = Catalog.load(repo_root)
    experiment = _narrow_experiment(
        Experiment.load(experiment_path),
        candidate_ids=candidate_ids,
        scenario_ids=scenario_ids,
        repetitions=repetitions,
    )
    candidates, scenarios = catalog.resolve(experiment)
    trials = build_trials(experiment, candidates, scenarios)
    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    scenarios_by_id = {scenario.id: scenario for scenario in scenarios}

    cost_ceiling = sum(
        candidates_by_id[trial.candidate_id].cost_ceiling_usd_per_attempt
        for trial in trials
    )
    maximum_model_calls = sum(
        scenarios_by_id[trial.scenario_id].max_model_calls for trial in trials
    )
    estimated_judge_calls = 0
    if experiment.judge.get("enabled"):
        pairs_per_scenario = len(candidates) * (len(candidates) - 1) // 2
        estimated_judge_calls = (
            pairs_per_scenario * len(scenarios) * experiment.repetitions
        )
    warnings: list[str] = []
    if cost_ceiling > experiment.budget.max_provider_cost_usd:
        warnings.append(
            "The sum of per-attempt safety ceilings exceeds the experiment cost cap; "
            "the live runner will stop before the cap and may produce a partial run."
        )
    if experiment.concurrency != 1:
        warnings.append(
            "Version 1 executes serially even when a higher concurrency is requested."
        )
    return RunPlan(
        experiment_id=experiment.id,
        experiment_hash=experiment.manifest_hash,
        experiment_schema_version=experiment.schema_version,
        candidates=tuple(
            {
                "id": candidate.id,
                "model": candidate.model,
                "effort": candidate.effort,
                "verbosity": candidate.verbosity,
                "temperature_policy": candidate.temperature_policy,
                "settings": candidate.requested_settings(),
                "agent_adapter": candidate.agent_adapter,
                "source_schema_version": candidate.schema_version,
                "max_output_tokens": candidate.max_output_tokens,
                "manifest_hash": candidate.manifest_hash,
                "cost_ceiling_usd_per_attempt": candidate.cost_ceiling_usd_per_attempt,
            }
            for candidate in candidates
        ),
        scenarios=tuple(
            {
                "id": scenario.id,
                "task_family": scenario.task_family,
                "fixture_dir": scenario.fixture_dir,
                "fixture_dirs": list(scenario.fixture_dirs),
                "required_skill_reads": list(scenario.required_skill_reads),
                "require_ui_spec": scenario.require_ui_spec,
                "ui_contracts": list(scenario.ui_contracts),
                "artifact_required": scenario.artifact.required,
                "environment": {
                    "plugin": scenario.environment_plugin or "none",
                    "fixture": scenario.environment_fixture,
                    "mode": scenario.environment_mode,
                    "clock": scenario.fixed_clock,
                },
                "capabilities": list(scenario.capabilities),
                "allowed_operations": list(scenario.allowed_operations),
                "scorers": list(scenario.scorers),
                "source_schema_version": scenario.schema_version,
                "manifest_hash": scenario.manifest_hash,
                "prompt_hash": scenario.prompt_hash,
                "fixture_hash": scenario.fixture_hash,
                "rubric_hash": scenario.rubric_hash,
            }
            for scenario in scenarios
        ),
        trials=tuple(trials),
        generation_attempts=len(trials),
        maximum_model_calls=maximum_model_calls,
        estimated_judge_calls=estimated_judge_calls,
        conservative_cost_ceiling_usd=round(cost_ceiling, 2),
        configured_cost_cap_usd=experiment.budget.max_provider_cost_usd,
        deadline_seconds=experiment.budget.deadline_seconds,
        concurrency=experiment.concurrency,
        random_seed=experiment.random_seed,
        judge=dict(experiment.judge),
        comparison_mode=experiment.comparison_mode,
        forbidden_side_effects=tuple(
            sorted(
                {
                    side_effect
                    for scenario in scenarios
                    for side_effect in scenario.forbidden_side_effects
                }
            )
        ),
        warnings=tuple(warnings),
    )


def generate_run_id() -> str:
    return f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _attempt_metrics(result: Any) -> dict[str, int]:
    usage = result.usage
    events = result.events
    return {
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in usage),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in usage),
        "provider_duration_ms": sum(int(row.get("duration_ms") or 0) for row in usage),
        "cache_read_tokens": sum(
            int((row.get("metadata") or {}).get("cache_read_tokens") or 0)
            for row in usage
            if isinstance(row.get("metadata"), dict)
        ),
        "cache_write_tokens": sum(
            int((row.get("metadata") or {}).get("cache_write_tokens") or 0)
            for row in usage
            if isinstance(row.get("metadata"), dict)
        ),
        "tool_calls": sum(
            1 for event in events if event.type in {"tool.started", "skill.read"}
        ),
        "tool_errors": sum(
            1
            for event in events
            if event.type == "tool.completed"
            and bool(
                event.data.get("isError")
                or event.data.get("is_error")
                or event.data.get("status") == "error"
            )
        ),
        "skill_reads": sum(1 for event in events if event.type == "skill.read"),
        "ui_specs": sum(1 for event in events if event.type == "ui.emitted"),
    }


def _validate_candidate_settings(
    adapter: AgentAdapter,
    candidates: list[Any],
) -> dict[str, Any]:
    capability_method = getattr(adapter, "settings_capabilities", None)
    if not callable(capability_method):
        v2 = [candidate.id for candidate in candidates if candidate.schema_version >= 2]
        if v2:
            raise RuntimeError(
                f"adapter {adapter.name} does not declare settings capabilities for "
                + ", ".join(v2)
            )
        return {"status": "undeclared", "adapter": adapter.name}
    document = capability_method()
    if not isinstance(document, SettingsCapabilities):
        raise RuntimeError(
            f"adapter {adapter.name} returned an invalid settings capability document"
        )
    if document.adapter != adapter.name:
        raise RuntimeError(
            f"adapter {adapter.name} returned settings capabilities for "
            f"{document.adapter}"
        )
    checked: dict[str, Any] = {}
    for candidate in candidates:
        supported = document.for_candidate(candidate)
        candidate_result: dict[str, Any] = {}
        for setting_name, request in candidate.requested_settings().items():
            capability = supported.get(setting_name)
            mode = request["mode"]
            if not isinstance(capability, dict):
                raise RuntimeError(
                    f"adapter {adapter.name} does not declare {setting_name} for "
                    f"candidate {candidate.id}"
                )
            if mode == "set":
                value = request.get("value")
                allowed_values = capability.get("values")
                if allowed_values is not None and value not in allowed_values:
                    raise RuntimeError(
                        f"adapter {adapter.name} rejects {setting_name}={value!r} "
                        f"for candidate {candidate.id}"
                    )
                minimum = capability.get("minimum")
                maximum = capability.get("maximum")
                if minimum is not None and value < minimum:
                    raise RuntimeError(
                        f"adapter {adapter.name} requires {setting_name}>={minimum} "
                        f"for candidate {candidate.id}"
                    )
                if maximum is not None and value > maximum:
                    raise RuntimeError(
                        f"adapter {adapter.name} requires {setting_name}<={maximum} "
                        f"for candidate {candidate.id}"
                    )
            modes = capability.get("modes")
            if not isinstance(modes, (list, tuple, set)) or mode not in modes:
                raise RuntimeError(
                    f"adapter {adapter.name} cannot apply {setting_name} mode={mode} "
                    f"for candidate {candidate.id}"
                )
            candidate_result[setting_name] = {
                "mode": mode,
                "observable": bool(capability.get("observable", False)),
                "translation": capability.get("translation"),
            }
        checked[candidate.id] = candidate_result
    return {
        "status": "validated",
        "adapter": document.adapter,
        "candidates": checked,
    }


def _validate_candidate_adapters(adapter: AgentAdapter, candidates: list[Any]) -> None:
    mismatched = [
        f"{candidate.id}={candidate.agent_adapter}"
        for candidate in candidates
        if candidate.agent_adapter is not None
        and candidate.agent_adapter != adapter.name
    ]
    if mismatched:
        raise RuntimeError(
            f"selected adapter {adapter.name} does not match candidate declarations: "
            + ", ".join(mismatched)
        )


def _validate_binding_compatibility(
    adapter: AgentAdapter,
    environment_info: Any,
) -> dict[str, Any]:
    required = set(environment_info.binding_kinds)
    capability_method = getattr(adapter, "supported_binding_kinds", None)
    if not callable(capability_method):
        if required:
            raise RuntimeError(
                f"adapter {adapter.name} does not declare environment binding support; "
                f"required: {', '.join(sorted(required))}"
            )
        supported: set[str] = set()
    else:
        supported = set(capability_method())
    unsupported = sorted(required - supported)
    if unsupported:
        raise RuntimeError(
            f"adapter {adapter.name} cannot attach required environment binding(s): "
            + ", ".join(unsupported)
        )
    return {
        "required": sorted(required),
        "supported": sorted(supported),
        "status": "validated",
    }


def _assess_attempt_settings(
    candidate: Any,
    settings: dict[str, Any],
    preflight: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Normalize requested/applied evidence and identify contaminated requests."""

    result = dict(settings or {})
    mismatches: list[str] = []
    expected = candidate.requested_settings()
    recorded = result.get("requested")
    if recorded is None:
        if candidate.schema_version >= 2:
            mismatches.append("adapter omitted requested-settings evidence")
    elif recorded != expected:
        mismatches.append("adapter requested-settings evidence differs from manifest")
    if candidate.schema_version >= 2:
        for field_name in ("translated", "applied"):
            if field_name not in result or result.get(field_name) in (None, {}, []):
                mismatches.append(
                    f"adapter omitted non-empty {field_name}-settings evidence"
                )
    unobservable = {
        str(value) for value in result.get("unobservable") or [] if str(value)
    }
    candidate_preflight = (
        preflight.get("candidates", {}).get(candidate.id, {})
        if isinstance(preflight, dict)
        else {}
    )
    for setting_name, evidence in candidate_preflight.items():
        if isinstance(evidence, dict) and not evidence.get("observable", False):
            unobservable.add(str(setting_name))
    result["unobservable"] = sorted(unobservable)
    result["mismatches"] = mismatches
    result["comparison_eligible"] = not unobservable and not mismatches
    return result, tuple(mismatches)


def execute_experiment(
    *,
    repo_root: Path,
    experiment_path: Path,
    adapter: AgentAdapter,
    environment: IntegrationEnvironment | None = None,
    run_id: str,
    output_root: Path,
    max_provider_cost_usd: float,
    candidate_ids: tuple[str, ...] = (),
    scenario_ids: tuple[str, ...] = (),
    repetitions: int | None = None,
) -> Path:
    """Execute a validated plan serially and persist regradable raw evidence."""
    catalog = Catalog.load(repo_root)
    experiment = _narrow_experiment(
        Experiment.load(experiment_path),
        candidate_ids=candidate_ids,
        scenario_ids=scenario_ids,
        repetitions=repetitions,
    )
    candidates, scenarios = catalog.resolve(experiment)
    active_environment: IntegrationEnvironment = environment or NoopEnvironment()
    plan = plan_experiment(
        repo_root,
        experiment_path,
        candidate_ids=candidate_ids,
        scenario_ids=scenario_ids,
        repetitions=repetitions,
    )
    if max_provider_cost_usd <= 0:
        raise ValueError("max_provider_cost_usd must be positive")
    if max_provider_cost_usd > experiment.budget.max_provider_cost_usd:
        raise ValueError(
            "operator cost cap cannot exceed the reviewed experiment manifest cap"
        )

    run_dir = output_root.resolve() / run_id
    if run_dir.exists():
        raise FileExistsError(f"eval run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    scenarios_by_id = {scenario.id: scenario for scenario in scenarios}
    manifest = {
        **plan.as_dict(),
        "run_id": run_id,
        "operator_cost_cap_usd": max_provider_cost_usd,
        "target": {"status": "preflight_pending", "adapter": adapter.name},
        "environment": {
            "status": "preflight_pending",
            "plugin": active_environment.name,
        },
    }
    write_json(
        run_dir / "manifest.json",
        manifest,
    )

    accumulated_cost = 0.0
    attempt_rows: list[dict[str, Any]] = []
    stopped_reason: str | None = None
    stop_status: str | None = None
    cleanup: list[dict[str, Any]] = []
    fatal_error: Exception | None = None
    interrupted = False
    started_monotonic = time.monotonic()
    try:
        environment_info = active_environment.preflight(scenarios)
        manifest["environment"] = {
            "status": "ready",
            "plugin": environment_info.plugin,
            "version": environment_info.version,
            "modes": list(environment_info.modes),
            "capabilities": list(environment_info.capabilities),
            "binding_kinds": list(environment_info.binding_kinds),
            "dimensions": environment_info.dimensions,
        }
        manifest["binding_preflight"] = _validate_binding_compatibility(
            adapter, environment_info
        )
        manifest["settings_preflight"] = _validate_candidate_settings(
            adapter, candidates
        )
        _validate_candidate_adapters(adapter, candidates)
        target = adapter.preflight(candidates)
        manifest["target"] = {
            "status": "ready",
            "adapter": target.adapter,
            "target_id": target.target_id,
            "dimensions": target.dimensions,
        }
        write_json(run_dir / "manifest.json", manifest)
        for trial in plan.trials:
            elapsed_seconds = time.monotonic() - started_monotonic
            if elapsed_seconds >= plan.deadline_seconds:
                stopped_reason = (
                    f"run deadline of {plan.deadline_seconds} seconds was reached"
                )
                stop_status = "partial_deadline_stop"
                break
            candidate = candidates_by_id[trial.candidate_id]
            scenario = scenarios_by_id[trial.scenario_id]
            remaining = max_provider_cost_usd - accumulated_cost
            if candidate.cost_ceiling_usd_per_attempt > remaining:
                stopped_reason = (
                    f"remaining cost budget ${remaining:.4f} is below candidate "
                    f"safety ceiling ${candidate.cost_ceiling_usd_per_attempt:.4f}"
                )
                stop_status = "partial_budget_stop"
                break
            attempt_dir = run_dir / "raw" / trial.attempt_id
            attempt_dir.mkdir(parents=True)
            environment_handle = active_environment.provision(
                EnvironmentRequest(
                    run_id=run_id,
                    trial=trial,
                    candidate=candidate,
                    scenario=scenario,
                    repo_root=repo_root,
                    output_dir=attempt_dir,
                )
            )
            result = None
            environment_cleanup: list[dict[str, Any]] = []
            try:
                result = adapter.run_attempt(
                    AttemptRequest(
                        run_id=run_id,
                        trial=trial,
                        candidate=candidate,
                        scenario=scenario,
                        repo_root=repo_root,
                        output_dir=attempt_dir,
                        environment=environment_handle,
                    )
                )
                result.settings, setting_mismatches = _assess_attempt_settings(
                    candidate,
                    result.settings,
                    manifest.get("settings_preflight") or {},
                )
                if setting_mismatches and result.status == "completed":
                    result.status = "contaminated"
                    result.error = "; ".join(setting_mismatches)
                operation_maps = tuple(
                    binding.operations for binding in environment_handle.bindings
                )
                operation_resolvers = tuple(
                    binding.operation_resolver
                    for binding in environment_handle.bindings
                    if binding.operation_resolver is not None
                )
                result.events = upgrade_tool_trace(
                    result.events,
                    operation_maps=operation_maps,
                    operation_resolvers=operation_resolvers,
                    adapter=adapter.name,
                    adapter_version=str(getattr(adapter, "version", "unknown")),
                    environment=environment_handle.plugin,
                    environment_version=environment_handle.version,
                )
                trace_errors = validate_tool_trace(result.events)
                snapshot = active_environment.snapshot(environment_handle)
                if not snapshot.ledger and any(
                    binding.kind == "native" for binding in environment_handle.bindings
                ):
                    snapshot = replace(
                        snapshot,
                        ledger=tool_ledger_from_events(result.events),
                    )
                oracle = active_environment.oracle(environment_handle)
                write_json(
                    attempt_dir / "environment.json",
                    {
                        "handle": environment_handle.as_evidence(),
                        "snapshot": snapshot.as_dict(),
                        "tool_trace_conformance": {
                            "passed": not trace_errors,
                            "errors": list(trace_errors),
                        },
                    },
                )
                write_json(attempt_dir / "oracle.json", oracle)
                result.dimensions["environment"] = {
                    "plugin": environment_handle.plugin,
                    "version": environment_handle.version,
                    "mode": environment_handle.mode,
                }
                result.dimensions["tool_trace_conformant"] = not trace_errors
                if trace_errors and result.status == "completed":
                    result.status = "infrastructure_error"
                    result.error = "normalized tool trace failed conformance: " + "; ".join(
                        trace_errors[:5]
                    )
            finally:
                try:
                    environment_cleanup = active_environment.reset(environment_handle)
                except Exception as exc:
                    environment_cleanup = [
                        {
                            "name": "environment reset",
                            "status": "fail",
                            "error": str(exc),
                            "resource": {"attempt_id": trial.attempt_id},
                        }
                    ]
                if result is not None:
                    result.cleanup.extend(environment_cleanup)
                    reset_failures = [
                        row
                        for row in environment_cleanup
                        if row.get("status") != "pass"
                    ]
                    if reset_failures and result.status == "completed":
                        result.status = "infrastructure_error"
                        result.error = "environment reset failed: " + ", ".join(
                            str(row.get("name") or "unknown")
                            for row in reset_failures
                        )
            if result is None:
                raise RuntimeError(
                    f"adapter {adapter.name} returned no result for {trial.attempt_id}"
                )
            raw_events = result.dimensions.pop("raw_events", [])
            write_jsonl(
                attempt_dir / "events.jsonl",
                [event.as_dict() for event in result.events],
            )
            write_jsonl(attempt_dir / "raw-events.jsonl", raw_events)
            write_json(attempt_dir / "messages.json", result.messages)
            write_json(attempt_dir / "usage.json", result.usage)
            write_json(attempt_dir / "files.json", result.artifacts)
            write_json(attempt_dir / "response.json", {"response": result.response})
            reported_provider_cost = float(
                result.dimensions.get("provider_cost_usd") or 0.0
            )
            invalid_cost = (
                not math.isfinite(reported_provider_cost)
                or reported_provider_cost < 0
            )
            cost_violation = invalid_cost or (
                reported_provider_cost > candidate.cost_ceiling_usd_per_attempt
            )
            provider_cost = 0.0 if invalid_cost else reported_provider_cost
            if invalid_cost:
                result.dimensions["reported_provider_cost_usd"] = repr(
                    reported_provider_cost
                )
                result.dimensions["provider_cost_usd"] = provider_cost
            if cost_violation:
                previous_error = f"; prior error: {result.error}" if result.error else ""
                result.status = "infrastructure_error"
                result.error = (
                    f"provider cost {reported_provider_cost!r} violated candidate ceiling "
                    f"${candidate.cost_ceiling_usd_per_attempt:.4f}{previous_error}"
                )
            accumulated_cost = round(accumulated_cost + provider_cost, 6)
            row = {
                "schema_version": 1,
                **asdict(trial),
                "status": result.status,
                "error": result.error,
                "timings": result.timings,
                "dimensions": result.dimensions,
                "artifact_count": len(result.artifacts),
                "event_count": len(result.events),
                "usage_event_count": len(result.usage),
                "metrics": _attempt_metrics(result),
                "cleanup": result.cleanup,
                "settings": result.settings,
                "provider_cost_usd": provider_cost,
                "accumulated_provider_cost_usd": accumulated_cost,
            }
            append_jsonl(run_dir / "attempts.jsonl", row)
            attempt_rows.append(row)
            if cost_violation or accumulated_cost > max_provider_cost_usd:
                stopped_reason = (
                    f"provider cost safety boundary was exceeded by {trial.attempt_id}"
                )
                stop_status = "partial_cost_ceiling_breach"
                break
    except KeyboardInterrupt:
        interrupted = True
        stopped_reason = "operator interrupted the run"
    except Exception as exc:
        fatal_error = exc
        stopped_reason = f"runner error: {exc}"
    finally:
        adapter_cleanup: list[dict[str, Any]]
        try:
            adapter_cleanup = adapter.close()
        except Exception as exc:
            adapter_cleanup = [
                {
                    "name": "adapter close",
                    "status": "fail",
                    "error": str(exc),
                }
            ]
        try:
            environment_close = active_environment.close()
        except Exception as exc:
            environment_close = [
                {
                    "name": "environment close",
                    "status": "fail",
                    "error": str(exc),
                }
            ]
        cleanup = [*adapter_cleanup, *environment_close]

    statuses = {row["status"] for row in attempt_rows}
    status = "completed"
    if interrupted:
        status = "partial_interrupted"
    elif fatal_error:
        status = "failed_preflight" if not attempt_rows else "partial_runner_error"
    elif stopped_reason:
        status = stop_status or "partial_stopped"
    elif statuses - {"completed"} or any(
        row.get("status") != "pass" for row in cleanup
    ):
        status = "completed_with_failures"
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": experiment.id,
        "status": status,
        "planned_attempts": len(plan.trials),
        "completed_attempts": len(attempt_rows),
        "attempt_statuses": {
            value: sum(1 for row in attempt_rows if row["status"] == value)
            for value in sorted(statuses)
        },
        "provider_cost_usd": accumulated_cost,
        "operator_cost_cap_usd": max_provider_cost_usd,
        "stopped_reason": stopped_reason,
        "cleanup": cleanup,
    }
    write_json(run_dir / "summary.json", summary)
    if interrupted:
        raise RuntimeError(
            f"eval run interrupted; partial evidence is available at {run_dir}"
        )
    if fatal_error:
        raise RuntimeError(
            f"eval run failed; partial evidence is available at {run_dir}: {fatal_error}"
        ) from fatal_error
    return run_dir
