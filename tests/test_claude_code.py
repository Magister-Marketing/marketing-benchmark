"""Offline tests for the Claude Code harness. No sessions are started."""

import json
import os
import stat
import sys

import pytest

from eval_runner import bench, claude_code


def _events(*events):
    return [json.dumps(event) for event in events]


def _assistant(message_id, *blocks, parent=None):
    return {
        "type": "assistant",
        "parent_tool_use_id": parent,
        "message": {"id": message_id, "content": list(blocks)},
    }


def _result(**overrides):
    event = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "stop_reason": "end_turn",
        "num_turns": 3,
        "total_cost_usd": 0.0421,
        "result": "final answer",
        "permission_denials": [],
        "usage": {
            "input_tokens": 10,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": 30000,
            "output_tokens": 900,
            "server_tool_use": {"web_search_requests": 2},
        },
    }
    event.update(overrides)
    return event


INIT = {"type": "system", "subtype": "init", "model": "claude-haiku-5-5", "tools": ["Bash"],
        "mcp_servers": [], "skills": [], "plugins": [], "claude_code_version": "2.1.325",
        "permissionMode": "acceptEdits", "apiKeySource": "ANTHROPIC_API_KEY", "agents": []}


def test_prompt_is_the_task_in_the_shared_preamble():
    tasks = bench.load_tasks()
    with_sources = next(task for task in tasks.values() if task.get("fixtures"))
    prompt = claude_code.build_prompt(with_sources)
    assert prompt.endswith(bench.assemble_prompt(with_sources, include_skills=False))
    assert "also saved under its own name" in prompt
    assert "Skill guidance you should follow" not in prompt
    assert "Deliver the complete final deliverable in your chat reply" in prompt
    assert "assume today is just after the latest date it mentions" in prompt

    without = dict(with_sources, fixtures=[])
    assert "also saved under its own name" not in claude_code.build_prompt(without)


def test_named_skills_are_the_tasks_own_and_only_installed_ones():
    tasks = bench.load_tasks()
    task = tasks["email-flow-repair"]
    assert claude_code.task_skill_names(task, {"emails", "copywriting", "seo-audit"}) == ["emails", "copywriting"]
    assert claude_code.task_skill_names(task, {"copywriting"}) == ["copywriting"]

    named = claude_code.build_prompt(task, ["emails", "copywriting"])
    plain = claude_code.build_prompt(task)
    assert "open these installed skills with the Skill tool and\nfollow them: emails, copywriting." in named
    assert "installed skills" not in plain
    # Naming a skill never pastes it: the model still has to open it.
    assert named.endswith(bench.assemble_prompt(task, include_skills=False))


def test_every_runnable_task_stages_its_sources_under_distinct_names(tmp_path):
    tasks = bench.load_tasks()
    for task_id in bench._select_tasks(None, "all", tasks, harness=claude_code.HARNESS_ID):
        task = tasks[task_id]
        workspace = tmp_path / task_id
        names = claude_code.stage_workspace(task, workspace)
        assert sorted(names) == sorted(path.name for path in workspace.iterdir())
        for fixture, name in zip(task.get("fixtures", []), names):
            assert (workspace / name).read_bytes() == (bench.REPO_ROOT / fixture).read_bytes()


def test_tasks_that_need_a_prior_turn_are_left_out():
    tasks = bench.load_tasks()
    selected = bench._select_tasks(None, "all", tasks, harness=claude_code.HARNESS_ID)
    assert "ads-ledger-analysis" in selected
    assert all(not tasks[task_id].get("decoy") for task_id in selected)


def test_command_confines_the_session(tmp_path):
    command = claude_code.build_command(
        "claude", model="claude-haiku-5-5", effort="high", deny_read=["/Users/someone"],
        home_dir=tmp_path / "home", tmp_dir=tmp_path / "tmp", plugin_dirs=[], mcp_config=None,
        mcp_servers=[], max_budget_usd=3.0,
    )
    assert command[:2] == ["claude", "-p"]
    for flag in ("--strict-mcp-config", "--no-session-persistence"):
        assert flag in command
    assert command[command.index("--permission-prompts") + 1] == "none"
    assert command[command.index("--effort") + 1] == "high"
    assert "--plugin-dir" not in command and "--mcp-config" not in command
    assert "--dangerously-skip-permissions" not in command
    # The shell runs unprompted because the sandbox confines it. The file
    # tools get no blanket allow: the working folders decide those.
    allowed = command[command.index("--allowedTools") + 1:command.index("--effort")]
    assert allowed == ["Bash", "WebSearch", "WebFetch", "Skill"]
    assert command[command.index("--add-dir") + 1] == str(tmp_path / "tmp")
    sandbox = json.loads(command[command.index("--settings") + 1])["sandbox"]
    assert sandbox["enabled"] and sandbox["failIfUnavailable"]
    assert sandbox["allowUnsandboxedCommands"] is False
    assert sandbox["filesystem"] == {"denyRead": ["/Users/someone"], "allowWrite": [str(tmp_path / "home")]}
    assert "pypi.org" in sandbox["network"]["allowedDomains"]
    assert sandbox["network"]["strictAllowlist"] is True


def test_command_installs_plugins_and_attaches_mcp_servers(tmp_path):
    plugin = tmp_path / "plugin"
    config = tmp_path / "mcp.json"
    command = claude_code.build_command(
        "claude", model="claude-haiku-5-5", effort=None, deny_read=[], home_dir=tmp_path,
        tmp_dir=tmp_path / "tmp", plugin_dirs=[plugin], mcp_config=config, mcp_servers=["magister"], max_budget_usd=1.0,
    )
    assert "--effort" not in command
    assert command[command.index("--plugin-dir") + 1] == str(plugin)
    assert command[command.index("--plugin-dir") + 2:command.index("--plugin-dir") + 4] == ["--add-dir", str(plugin)]
    assert command[command.index("--mcp-config") + 1] == str(config)
    assert "mcp__magister" in command


def test_child_environment_passes_nothing_of_the_operators(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = claude_code.child_environment(
        "key", config_dir=tmp_path / "c", home_dir=tmp_path / "h", tmp_dir=tmp_path / "t",
    )
    assert set(env) == {
        "PATH", "HOME", "TMPDIR", "LANG", "ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_AUTOUPDATER",
    }
    assert env["HOME"] == str(tmp_path / "h")
    assert os.path.expanduser("~") not in env["PATH"]


def test_stream_is_reduced_to_an_attempt_record():
    lines = _events(
        INIT,
        _assistant("m1", {"type": "text", "text": "Reading the export."},
                   {"type": "tool_use", "name": "Skill", "input": {"skill": "marketing-skills:analytics"}}),
        # One model call can arrive as several events; it is still one call.
        _assistant("m1", {"type": "tool_use", "name": "Bash", "input": {"command": "python3 x.py"}}),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "is_error": True,
             "content": "Exit code 56\n<sandbox_violations>\ndeny network-outbound example.com:443\n</sandbox_violations>"},
        ]}},
        _assistant("sub1", {"type": "text", "text": "subagent chatter"}, parent="toolu_1"),
        _assistant("m2", {"type": "tool_use", "name": "Read",
                          "input": {"file_path": "/x/plugin/skills/copywriting/SKILL.md"}}),
        _assistant("m3", {"type": "text", "text": "A1: $10,228.41"}),
        _result(permission_denials=[{"tool_name": "Read"}]),
    )
    summary = claude_code.parse_stream(lines + ["not json", ""])
    fields = claude_code.attempt_fields(summary, "claude-haiku-5-5")

    assert "error" not in fields
    assert claude_code.response_text(summary) == "Reading the export.\n\nA1: $10,228.41"
    assert fields["tool_calls"] == {"Skill": 1, "Bash": 1, "Read": 1}
    assert fields["tool_call_count"] == 3
    assert fields["skill_reads"] == ["analytics", "copywriting"]
    assert fields["tool_errors"] == 1
    assert fields["guardrail_kinds"] == {"permission_denied": 1, "sandbox_denied": 1}
    assert fields["guardrail_events"] == 2
    assert fields["llm_calls"] == 3
    assert fields["input_tokens"] == 32010
    assert fields["cached_tokens"] == 30000
    assert fields["output_tokens"] == 900
    assert fields["web_search_calls"] == 2
    assert fields["provider_cost_usd"] == pytest.approx(0.0421)
    assert fields["finish_reason"] == "end_turn"
    assert fields["short_reply"] is True
    assert summary["inventory"]["claude_code_version"] == "2.1.325"


def test_reply_falls_back_to_the_result_text():
    summary = claude_code.parse_stream(_events(INIT, _result()))
    assert claude_code.response_text(summary) == "final answer"


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (_events(INIT, _assistant("m1", {"type": "text", "text": "partial"})), "without a result event"),
        (_events(dict(INIT, model="claude-sonnet-5-5"), _assistant("m1", {"type": "text", "text": "x"}), _result()),
         "not the requested"),
        (_events(INIT, _assistant("m1", {"type": "text", "text": "x"}),
                 _result(subtype="error_max_budget_usd", is_error=True)), "error_max_budget_usd"),
        (_events(INIT, _result(result="")), "no reply"),
    ],
)
def test_unfinished_sessions_are_errors_not_answers(lines, message):
    fields = claude_code.attempt_fields(claude_code.parse_stream(lines), "claude-haiku-5-5")
    assert message in fields["error"]


def test_a_dated_model_name_is_the_requested_model():
    lines = _events(dict(INIT, model="claude-haiku-5-5-20261001"),
                    _assistant("m1", {"type": "text", "text": "x"}), _result())
    assert "error" not in claude_code.attempt_fields(claude_code.parse_stream(lines), "claude-haiku-5-5")


def test_plugin_is_copied_read_only_and_described(tmp_path):
    source = tmp_path / "pack"
    (source / ".claude-plugin").mkdir(parents=True)
    (source / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "pack", "version": "1.2.3"}))
    for name in ("emails", "analytics"):
        (source / "skills" / name).mkdir(parents=True)
        (source / "skills" / name / "SKILL.md").write_text("---\nname: x\n---\n")
    (source / ".git").mkdir()

    destination = tmp_path / "run" / "0-pack"
    destination.parent.mkdir()
    described = claude_code.stage_plugin(source, destination)

    assert described["name"] == "pack" and described["version"] == "1.2.3"
    assert described["skills"] == ["analytics", "emails"]
    assert not (destination / ".git").exists()
    skill = destination / "skills" / "emails" / "SKILL.md"
    assert not stat.S_IMODE(skill.stat().st_mode) & 0o222
    assert (source / "skills" / "emails" / "SKILL.md").stat().st_mode & 0o200  # the checkout is untouched

    with pytest.raises(SystemExit, match="not a Claude Code plugin"):
        claude_code.stage_plugin(tmp_path, tmp_path / "other")


def test_mcp_config_gives_up_names_only(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {
        "magister": {"type": "http", "url": "https://example.test/mcp",
                     "headers": {"Authorization": "Bearer secret"}},
    }}))
    assert claude_code.mcp_server_names(config) == ["magister"]
    config.write_text("{}")
    with pytest.raises(SystemExit, match="mcpServers"):
        claude_code.mcp_server_names(config)


def test_written_files_are_kept_without_the_staged_sources(tmp_path):
    workspace = tmp_path / "work"
    (workspace / ".claude").mkdir(parents=True)
    (workspace / ".claude" / "x.json").write_text("{}")
    (workspace / "ads_daily.csv").write_text("staged")
    (workspace / "out").mkdir()
    (workspace / "out" / "review.md").write_text("written")
    (workspace / "big.bin").write_bytes(b"0" * (claude_code.KEPT_FILE_BYTES + 1))

    kept = claude_code.keep_written_files(workspace, ["ads_daily.csv"], tmp_path / "kept")

    assert kept == ["out/review.md"]
    assert (tmp_path / "kept" / "out" / "review.md").read_text() == "written"


# A stand-in for the CLI, so `run` can be driven offline. Every first attempt
# dies before its result event, after writing a draft; a retry answers, except
# for the task named in DIES_TWICE. Its stderr puts the key across the cut the
# error message makes.
FAKE_CLI = """#!{python}
import json, pathlib, sys
if sys.argv[1:] == ["--version"]:
    print("0.0.0 (fake)")
    raise SystemExit(0)
sys.stdin.read()
attempt = pathlib.Path.cwd().parent.name
print(json.dumps({{"type": "system", "subtype": "init", "model": "claude-haiku-5-5"}}))
if attempt.endswith("-1") or attempt.startswith("{dies_twice}--"):
    pathlib.Path("draft.md").write_text("abandoned")
    print("x" * 290 + " {key}", file=sys.stderr)
    raise SystemExit(9)
pathlib.Path("final.md").write_text("kept")
print(json.dumps({{"type": "assistant", "message": {{"id": "m1", "content": [{{"type": "text", "text": "answer"}}]}}}}))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "usage": {{}}}}))
"""


def test_only_a_session_that_never_finished_runs_again(tmp_path, monkeypatch):
    tasks = bench.load_tasks()
    answers, dies_twice = bench._select_tasks(None, "all", tasks, harness=claude_code.HARNESS_ID)[:2]
    key = "sk-test-0123456789"
    cli = tmp_path / "claude"
    cli.write_text(FAKE_CLI.format(python=sys.executable, dies_twice=dies_twice, key=key))
    cli.chmod(0o755)
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)

    code = claude_code.main(["run", "--candidate", "claude-haiku-5-5", "--tasks", f"{answers},{dies_twice}",
                             "--parallel", "1", "--cli", str(cli), "--yes"])

    (run_dir,) = (tmp_path / "results").iterdir()
    records = {row["task_id"]: row for row in map(json.loads, (run_dir / "attempts.jsonl").read_text().splitlines())}
    assert code == 1
    answered = records[answers]
    assert answered["retried"] is True and "error" not in answered
    assert (run_dir / answered["response_path"]).read_text() == "answer"
    # The run directory shows the recorded attempt only, not the first one's draft.
    assert answered["files_written"] == ["final.md"]
    assert [path.name for path in (run_dir / "artifacts" / f"{answers}--claude-code-claude-haiku-5-5--r1").iterdir()] \
        == ["final.md"]
    failed = records[dies_twice]
    assert failed["retried"] is True and "response_path" not in failed
    assert failed["error"].startswith("Claude Code ended without a result event (exit 9): xxx")
    assert "sk-test" not in failed["error"]
