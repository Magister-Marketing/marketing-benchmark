#!/usr/bin/env python3
"""Marketing Benchmark CLI for plans, replay runs, grading, and reports."""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import shlex
import sys
from pathlib import Path

from .plugins.replay_mcp import ReplayMcpEnvironment
from .plugins.subprocess_jsonl import SubprocessJsonlAdapter
from .runner.adapters.claude_code import ClaudeCodeAdapter
from .runner.adapters.codex_cli import CodexCliAdapter
from .runner.adapters.openai_responses import OpenAIResponsesAdapter
from .runner.conformance import assert_conformant, check_agent_adapter, check_environment
from .runner.comparison import (
    build_agent_system_comparison,
    import_comparison_judging,
    prepare_comparison_judging,
)
from .runner.engine import execute_experiment, generate_run_id, plan_experiment
from .runner.environments import EnvironmentRouter
from .runner.grading import grade_run
from .runner.judging import import_pairwise_results, prepare_pairwise_judging
from .runner.plugins import PluginRegistry
from .runner.public_report import build_public_report
from .runner.report import build_run_report, render_plan_markdown
from .runner.schema import Catalog, Experiment, ManifestError
from .runner.validators import (
    JsonObjectValidator,
    PlaywrightHtmlValidator,
    StaticHtmlValidator,
    UiValidatorRegistry,
)


def _default_repo_root() -> Path:
    working_root = Path.cwd().resolve()
    if (working_root / "evals").is_dir():
        return working_root
    source_root = Path(__file__).resolve().parents[1]
    return source_root if (source_root / "evals").is_dir() else Path.cwd().resolve()


def _path(root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _run_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        direct = root / candidate
        candidate = direct if direct.exists() else root / "artifacts" / "evals" / value
    resolved = candidate.resolve()
    eval_root = (root / "artifacts" / "evals").resolve()
    try:
        resolved.relative_to(eval_root)
    except ValueError as exc:
        raise ManifestError("run path must be inside artifacts/evals") from exc
    if not resolved.is_dir():
        raise ManifestError(f"run directory not found: {resolved}")
    return resolved


def _comparison_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        direct = root / candidate
        candidate = (
            direct if direct.exists() else root / "artifacts" / "comparisons" / value
        )
    resolved = candidate.resolve()
    comparison_root = (root / "artifacts" / "comparisons").resolve()
    try:
        resolved.relative_to(comparison_root)
    except ValueError as exc:
        raise ManifestError("comparison path must be inside artifacts/comparisons") from exc
    if not resolved.is_dir():
        raise ManifestError(f"comparison directory not found: {resolved}")
    return resolved


_CATALOG_DIRECTORIES = (
    "candidates",
    "experiments",
    "fixtures",
    "rubrics",
    "schema",
    "suites",
    "treatments",
)


def command_init(args: argparse.Namespace) -> int:
    """Copy the bundled benchmark catalog into an operator-owned repository."""
    target_root = args.path.expanduser().resolve()
    filesystem_root = Path(target_root.anchor).resolve()
    if target_root in {filesystem_root, Path.home().resolve()}:
        raise ManifestError("refusing to initialize a filesystem or home root")
    if target_root.exists() and not target_root.is_dir():
        raise ManifestError(f"initialization target is not a directory: {target_root}")
    if not target_root.exists():
        if not target_root.parent.is_dir():
            raise ManifestError(
                f"initialization target parent does not exist: {target_root.parent}"
            )
        target_root.mkdir()

    source_root = Path(__file__).resolve().parent
    target_catalog = target_root / "evals"
    if target_catalog.exists():
        raise ManifestError(f"refusing to overwrite existing catalog: {target_catalog}")
    target_catalog.mkdir()
    try:
        for directory in _CATALOG_DIRECTORIES:
            source = source_root / directory
            if not source.is_dir() or source.is_symlink():
                raise ManifestError(f"bundled catalog directory is missing: {source}")
            shutil.copytree(source, target_catalog / directory)
    except Exception:
        shutil.rmtree(target_catalog, ignore_errors=True)
        raise
    print(
        json.dumps(
            {
                "status": "initialized",
                "path": str(target_catalog),
                "directories": list(_CATALOG_DIRECTORIES),
            },
            sort_keys=True,
        )
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    catalog = Catalog.load(args.repo_root)
    experiments: list[dict[str, object]] = []
    for path in sorted((args.repo_root / "evals" / "experiments").glob("*.json")):
        experiment = Experiment.load(path)
        catalog.resolve(experiment)
        plan_experiment(args.repo_root, path)
        experiments.append(
            {
                "id": experiment.id,
                "comparison_mode": experiment.comparison_mode,
                "candidates": len(experiment.candidates),
                "scenarios": len(experiment.scenarios),
                "repetitions": experiment.repetitions,
            }
        )
    print(
        json.dumps(
            {
                "status": "ok",
                "candidate_count": len(catalog.candidates),
                "scenario_count": len(catalog.scenarios),
                "experiments": experiments,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_plan(args: argparse.Namespace) -> int:
    plan = plan_experiment(
        args.repo_root,
        _path(args.repo_root, args.experiment),
        candidate_ids=tuple(args.candidate),
        scenario_ids=tuple(args.scenario),
        repetitions=args.repetitions,
    )
    print(
        json.dumps(plan.as_dict(), indent=2, sort_keys=True)
        if args.json
        else render_plan_markdown(plan),
        end="\n" if args.json else "",
    )
    return 0


def _adapter_registry() -> PluginRegistry[object]:
    registry: PluginRegistry[object] = PluginRegistry("agent_adapter")
    registry.register(
        "claude-code",
        lambda **kwargs: ClaudeCodeAdapter(**kwargs),
        implementation_version="1",
    )
    registry.register(
        "subprocess-jsonl",
        lambda **kwargs: SubprocessJsonlAdapter(**kwargs),
        implementation_version="1",
    )
    registry.register(
        "openai-responses",
        lambda **kwargs: OpenAIResponsesAdapter(**kwargs),
        implementation_version="1",
    )
    registry.register(
        "codex-cli",
        lambda **kwargs: CodexCliAdapter(**kwargs),
        implementation_version="1",
    )
    return registry


def _environment_registry() -> PluginRegistry[object]:
    registry: PluginRegistry[object] = PluginRegistry("integration_environment")
    registry.register(
        "replay-mcp",
        lambda **kwargs: ReplayMcpEnvironment(**kwargs),
        implementation_version="1",
    )
    return registry


def _skill_roots(root: Path) -> tuple[Path, ...]:
    return (
        root / "evals" / "fixtures" / "public" / "skills",
        root / "skills",
    )


def command_run(args: argparse.Namespace) -> int:
    confirmation = {
        "claude-code": "RUN_LOCAL_CLAUDE_CODE_EVALS",
        "subprocess-jsonl": "RUN_LOCAL_SUBPROCESS_EVALS",
        "openai-responses": "RUN_LOCAL_OPENAI_EVALS",
        "codex-cli": "RUN_LOCAL_CODEX_EVALS",
    }[args.adapter]
    if args.confirm != confirmation:
        raise ManifestError(
            f"paid {args.adapter} execution requires --confirm {confirmation}"
        )
    experiment_path = _path(args.repo_root, args.experiment)
    experiment = Experiment.load(experiment_path)
    if (
        args.max_provider_cost_usd <= 0
        or args.max_provider_cost_usd > experiment.budget.max_provider_cost_usd
    ):
        raise ManifestError(
            "operator cost cap must be positive and cannot exceed the reviewed "
            f"experiment cap ${experiment.budget.max_provider_cost_usd:.2f}"
        )
    plan_experiment(
        args.repo_root,
        experiment_path,
        candidate_ids=tuple(args.candidate),
        scenario_ids=tuple(args.scenario),
        repetitions=args.repetitions,
    )
    run_id = generate_run_id()
    common = {
        "repo_root": args.repo_root,
        "run_id": run_id,
        "deadline_seconds": experiment.budget.deadline_seconds,
        "skill_roots": _skill_roots(args.repo_root),
    }
    if args.adapter == "subprocess-jsonl":
        if not args.subprocess_command:
            raise ManifestError("subprocess-jsonl requires --subprocess-command")
        adapter = _adapter_registry().create(
            args.adapter,
            command=tuple(shlex.split(args.subprocess_command)),
            **common,
        )
    else:
        adapter = _adapter_registry().create(args.adapter, **common)
    replay = _environment_registry().create(
        "replay-mcp", repo_root=args.repo_root, run_id=run_id
    )
    environment = EnvironmentRouter({"replay-mcp": replay})
    try:
        run_dir = execute_experiment(
            repo_root=args.repo_root,
            experiment_path=experiment_path,
            adapter=adapter,
            environment=environment,
            run_id=run_id,
            output_root=args.repo_root / "artifacts" / "evals",
            max_provider_cost_usd=args.max_provider_cost_usd,
            candidate_ids=tuple(args.candidate),
            scenario_ids=tuple(args.scenario),
            repetitions=args.repetitions,
        )
    except Exception:
        with contextlib.suppress(Exception):
            adapter.close()
        with contextlib.suppress(Exception):
            environment.close()
        raise
    print(json.dumps({"status": "finished", "run_id": run_id, "path": str(run_dir)}))
    return 0


def command_grade(args: argparse.Namespace) -> int:
    validators = UiValidatorRegistry()
    validators.register("json-object@1", JsonObjectValidator())
    validators.register("static-html@1", StaticHtmlValidator())
    validators.register("playwright-html@1", PlaywrightHtmlValidator())
    output = grade_run(
        args.repo_root,
        _run_path(args.repo_root, args.run),
        ui_validators=validators,
    )
    print(json.dumps({"status": "graded", "path": str(output)}))
    return 0


def command_report(args: argparse.Namespace) -> int:
    output = build_run_report(_run_path(args.repo_root, args.run))
    print(json.dumps({"status": "reported", "path": str(output)}))
    return 0


def command_public_report(args: argparse.Namespace) -> int:
    output = build_public_report(_run_path(args.repo_root, args.run))
    print(json.dumps({"status": "public-report-ready", "path": str(output)}))
    return 0


def command_compare(args: argparse.Namespace) -> int:
    output = build_agent_system_comparison(
        repo_root=args.repo_root,
        baseline_run_dir=_run_path(args.repo_root, args.baseline_run),
        treatment_run_dir=_run_path(args.repo_root, args.treatment_run),
        declaration_path=_path(args.repo_root, args.declaration),
        baseline_candidate_id=args.baseline_candidate,
        treatment_candidate_id=args.treatment_candidate,
    )
    payload = json.loads((output / "comparison.json").read_text())
    print(
        json.dumps(
            {
                "status": "comparison-ready" if payload["valid"] else "comparison-invalid",
                "valid": payload["valid"],
                "path": str(output),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["valid"] else 2


def command_compare_judge_plan(args: argparse.Namespace) -> int:
    output = prepare_comparison_judging(
        repo_root=args.repo_root,
        comparison_dir=_comparison_path(args.repo_root, args.comparison),
        baseline_run_dir=_run_path(args.repo_root, args.baseline_run),
        treatment_run_dir=_run_path(args.repo_root, args.treatment_run),
    )
    print(json.dumps({"status": "comparison-judge-plan-ready", "path": str(output)}))
    return 0


def command_compare_judge_import(args: argparse.Namespace) -> int:
    output = import_comparison_judging(
        comparison_dir=_comparison_path(args.repo_root, args.comparison),
        results_path=_path(args.repo_root, args.results),
        judge_id=args.judge_id,
    )
    print(
        json.dumps(
            {"status": "comparison-judge-results-imported", "path": str(output)}
        )
    )
    return 0


def command_judge_plan(args: argparse.Namespace) -> int:
    output = prepare_pairwise_judging(
        args.repo_root,
        _run_path(args.repo_root, args.run),
    )
    print(json.dumps({"status": "judge-plan-ready", "path": str(output)}))
    return 0


def command_judge_import(args: argparse.Namespace) -> int:
    output = import_pairwise_results(
        _run_path(args.repo_root, args.run),
        _path(args.repo_root, args.results),
        judge_id=args.judge_id,
    )
    print(json.dumps({"status": "judge-results-imported", "path": str(output)}))
    return 0


def command_conformance(args: argparse.Namespace) -> int:
    run_id = "structural-conformance"
    claude_adapter = ClaudeCodeAdapter(
        repo_root=args.repo_root,
        run_id=run_id,
        deadline_seconds=60,
        workspace_root=args.repo_root / "artifacts" / "evals-conformance-workspace",
        skill_roots=_skill_roots(args.repo_root),
    )
    openai_adapter = OpenAIResponsesAdapter(
        repo_root=args.repo_root,
        run_id=run_id,
        deadline_seconds=60,
        workspace_root=args.repo_root / "artifacts" / "evals-conformance-openai",
        skill_roots=_skill_roots(args.repo_root),
        api_key="offline-structural-placeholder",
    )
    codex_adapter = CodexCliAdapter(
        repo_root=args.repo_root,
        run_id=run_id,
        deadline_seconds=60,
        workspace_root=args.repo_root / "artifacts" / "evals-conformance-codex",
        skill_roots=_skill_roots(args.repo_root),
    )
    environment = ReplayMcpEnvironment(
        repo_root=args.repo_root,
        run_id=run_id,
        workspace_root=args.repo_root / "artifacts" / "evals-conformance-replay",
    )
    findings = [
        *check_agent_adapter(claude_adapter),
        *check_agent_adapter(openai_adapter),
        *check_agent_adapter(codex_adapter),
        *check_environment(environment),
    ]
    try:
        assert_conformant(findings)
    finally:
        claude_adapter.close()
        openai_adapter.close()
        codex_adapter.close()
        environment.close()
    print(
        json.dumps(
            {"status": "ok", "findings": [value.as_dict() for value in findings]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="copy the bundled catalog into a repository")
    init.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    init.set_defaults(func=command_init)
    validate = commands.add_parser("validate")
    validate.set_defaults(func=command_validate)
    conformance = commands.add_parser("conformance")
    conformance.set_defaults(func=command_conformance)
    plan = commands.add_parser("plan")
    plan.add_argument("--experiment", required=True)
    plan.add_argument("--candidate", action="append", default=[])
    plan.add_argument("--scenario", action="append", default=[])
    plan.add_argument("--repetitions", type=int)
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)
    run = commands.add_parser("run")
    run.add_argument("--experiment", required=True)
    run.add_argument(
        "--adapter",
        choices=("claude-code", "codex-cli", "openai-responses", "subprocess-jsonl"),
        required=True,
    )
    run.add_argument("--confirm", required=True)
    run.add_argument("--max-provider-cost-usd", required=True, type=float)
    run.add_argument("--subprocess-command")
    run.add_argument("--candidate", action="append", default=[])
    run.add_argument("--scenario", action="append", default=[])
    run.add_argument("--repetitions", type=int)
    run.set_defaults(func=command_run)
    grade = commands.add_parser("grade")
    grade.add_argument("--run", required=True)
    grade.set_defaults(func=command_grade)
    report = commands.add_parser("report")
    report.add_argument("--run", required=True)
    report.set_defaults(func=command_report)
    public_report = commands.add_parser(
        "public-report", help="write a plain-language benchmark leaderboard"
    )
    public_report.add_argument("--run", required=True)
    public_report.set_defaults(func=command_public_report)
    compare = commands.add_parser(
        "compare", help="compare matched baseline and treatment agent-system runs"
    )
    compare.add_argument("--baseline-run", required=True)
    compare.add_argument("--treatment-run", required=True)
    compare.add_argument("--baseline-candidate")
    compare.add_argument("--treatment-candidate")
    compare.add_argument("--declaration", required=True)
    compare.set_defaults(func=command_compare)
    compare_judge_plan = commands.add_parser(
        "compare-judge-plan",
        help="prepare identity-blinded quality packets for a valid comparison",
    )
    compare_judge_plan.add_argument("--comparison", required=True)
    compare_judge_plan.add_argument("--baseline-run", required=True)
    compare_judge_plan.add_argument("--treatment-run", required=True)
    compare_judge_plan.set_defaults(func=command_compare_judge_plan)
    compare_judge_import = commands.add_parser(
        "compare-judge-import",
        help="import blinded quality decisions into a comparison",
    )
    compare_judge_import.add_argument("--comparison", required=True)
    compare_judge_import.add_argument("--results", required=True)
    compare_judge_import.add_argument("--judge-id", required=True)
    compare_judge_import.set_defaults(func=command_compare_judge_import)
    judge_plan = commands.add_parser("judge-plan")
    judge_plan.add_argument("--run", required=True)
    judge_plan.set_defaults(func=command_judge_plan)
    judge_import = commands.add_parser("judge-import")
    judge_import.add_argument("--run", required=True)
    judge_import.add_argument("--results", required=True)
    judge_import.add_argument("--judge-id", required=True)
    judge_import.set_defaults(func=command_judge_import)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.repo_root = args.repo_root.expanduser().resolve()
    try:
        return int(args.func(args))
    except (FileNotFoundError, ManifestError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
