from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "evals.cli", *arguments],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_validate_loads_the_bundled_catalog() -> None:
    result = run_cli("validate")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["candidate_count"] == 16
    assert payload["scenario_count"] == 17
    assert {row["id"] for row in payload["experiments"]} == {
        "ga4-replay",
        "cross-tool-replay",
        "claude-agent-system-repeated",
        "codex-agent-system-repeated",
        "general-chat-repeated",
        "marketing-creative",
        "openai-marketing-quick",
    }


def test_plan_can_select_a_reviewed_cost_reducing_subset() -> None:
    result = run_cli(
        "plan",
        "--experiment",
        "evals/experiments/ga4-replay.json",
        "--candidate",
        "claude-sonnet-5-high",
        "--scenario",
        "ga4-baseline-diagnosis",
        "--repetitions",
        "1",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["generation_attempts"] == 1
    assert payload["candidates"][0]["id"] == "claude-sonnet-5-high"
    assert payload["scenarios"][0]["id"] == "ga4-baseline-diagnosis"


def test_init_scaffolds_an_independent_repository(tmp_path: Path) -> None:
    target = tmp_path / "customer-repository"

    initialized = run_cli("init", str(target))
    assert initialized.returncode == 0, initialized.stderr
    assert (target / "evals" / "experiments" / "ga4-replay.json").is_file()
    assert (target / "evals" / "fixtures" / "public").is_dir()
    assert not (target / "evals" / "runner").exists()

    validated = run_cli("--repo-root", str(target), "validate")
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["scenario_count"] == 17

    repeated = run_cli("init", str(target))
    assert repeated.returncode == 2
    assert "refusing to overwrite existing catalog" in repeated.stderr


def test_init_refuses_a_home_root() -> None:
    result = run_cli("init", str(Path.home()))

    assert result.returncode == 2
    assert "refusing to initialize a filesystem or home root" in result.stderr


def test_conformance_is_offline_and_structurally_complete() -> None:
    result = run_cli("conformance")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["findings"]
    assert all(row["passed"] for row in payload["findings"])


def test_cli_exposes_the_complete_offline_workflow() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    for command in (
        "init",
        "validate",
        "conformance",
        "plan",
        "run",
        "grade",
        "compare",
        "compare-judge-plan",
        "compare-judge-import",
        "judge-plan",
        "judge-import",
        "report",
        "public-report",
    ):
        assert command in result.stdout


def test_openai_quick_plan_has_all_requested_profiles() -> None:
    result = run_cli(
        "plan",
        "--experiment",
        "evals/experiments/openai-marketing-quick.json",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["generation_attempts"] == 11
    assert payload["warnings"] == []
    assert {row["model"] for row in payload["candidates"]} == {
        "openai/gpt-5.6-luna",
        "openai/gpt-5.6-terra",
        "openai/gpt-5.6-sol",
    }
    assert {row["verbosity"] for row in payload["candidates"]} == {"medium"}
    assert {
        row["settings"]["temperature"]["mode"] for row in payload["candidates"]
    } == {"omit"}
