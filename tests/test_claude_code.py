"""Offline tests for the Claude Code harness. No sessions are started."""

import fcntl
import json
import os
from pathlib import Path
import pty
import signal
import subprocess
import sys
import termios
import time

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


def test_given_files_are_staged_named_in_the_prompt_and_never_kept(tmp_path):
    files_dir = tmp_path / "exports"
    files_dir.mkdir()
    (files_dir / "queries.csv").write_text("query,clicks\nlamp,3\n")
    (files_dir / "pages.csv").write_text("page,clicks\n/,9\n")
    (files_dir / ".DS_Store").write_text("")
    (files_dir / "nested").mkdir()
    files = claude_code.given_files(files_dir)
    assert [path.name for path in files] == ["pages.csv", "queries.csv"]
    assert claude_code.given_files(None) == []

    task = dict(bench.load_tasks()["headline"], fixtures=[])
    prompt = claude_code.build_prompt(task, files=files)
    assert "These files are saved in the working folder: pages.csv, queries.csv.\n" in prompt
    assert "These files" not in claude_code.build_prompt(task)

    workspace = tmp_path / "work"
    staged = claude_code.stage_workspace(task, workspace, files)
    assert staged == ["pages.csv", "queries.csv"]
    assert (workspace / "queries.csv").read_text() == "query,clicks\nlamp,3\n"
    (workspace / "answer.md").write_text("mine")
    # What the run gave is not what the agent wrote.
    assert claude_code.keep_written_files(workspace, staged, tmp_path / "kept") == ["answer.md"]

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit, match="no files to give"):
        claude_code.given_files(empty)


def test_a_private_task_folder_replaces_the_repositorys(tmp_path):
    criterion = {"check": "The reply greets the reader."}
    task = {
        "id": "private-task", "title": "A task kept elsewhere", "split": "development",
        "prompt_version": 1, "rubric_version": 1, "fixtures": [], "skills": [], "prompt": "Say hello.",
        "rubric": {section: [dict(criterion, id=section)] for section in bench.RUBRIC_SECTIONS},
    }
    (tmp_path / "private-task.json").write_text(json.dumps(task))
    script = "from eval_runner import bench; print(sorted(bench.load_tasks()))"
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True, cwd=bench.REPO_ROOT,
        env={**os.environ, "MARKETING_BENCH_TASKS_DIR": str(tmp_path)},
    ).stdout
    assert out.strip() == "['private-task']"


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
        "claude", model="claude-haiku-5-5", effort="high", attempt_root=tmp_path,
        home_dir=tmp_path / "home", tmp_dir=tmp_path / "tmp", operator_home=Path("/Users/someone"),
        plugin_dirs=[], mcp_config=None, mcp_servers=[], max_budget_usd=3.0,
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
    # The shell reads its own attempt and the system, not the operator's home,
    # the shared temp folders, or (under them) another attempt.
    assert sandbox["filesystem"] == {
        "denyRead": ["/Users/someone", "/tmp", "/private/tmp"],
        "allowRead": [str(tmp_path)],
        "allowWrite": [str(tmp_path / "home")],
    }
    assert sandbox["credentials"] == {"envVars": [{"name": "ANTHROPIC_API_KEY", "mode": "deny"}]}
    assert "pypi.org" in sandbox["network"]["allowedDomains"]
    assert sandbox["network"]["strictAllowlist"] is True


def test_command_installs_plugins_and_attaches_mcp_servers(tmp_path):
    plugin = tmp_path / "plugin"
    config = tmp_path / "mcp.json"
    command = claude_code.build_command(
        "claude", model="claude-haiku-5-5", effort=None, attempt_root=tmp_path, home_dir=tmp_path,
        tmp_dir=tmp_path / "tmp", operator_home=tmp_path, plugin_dirs=[plugin], mcp_config=config,
        mcp_servers=["magister"], max_budget_usd=1.0,
    )
    assert "--effort" not in command
    assert command[command.index("--plugin-dir") + 1] == str(plugin)
    assert command[command.index("--plugin-dir") + 2:command.index("--plugin-dir") + 4] == ["--add-dir", str(plugin)]
    assert command[command.index("--mcp-config") + 1] == str(config)
    assert "mcp__magister" in command


def test_attempt_folders_are_private_short_and_checked(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_code, "ATTEMPT_ROOT_PARENT", str(tmp_path))
    run_root = claude_code.make_run_root()
    assert run_root.parent == tmp_path.resolve() and run_root.stat().st_mode & 0o777 == 0o700
    first, retry, other = (claude_code.attempt_folders(run_root, *key) for key in ((59, 1), (59, 2), (60, 1)))
    assert {first["root"].name, retry["root"].name, other["root"].name} == {"59a", "59b", "60a"}
    for name in ("work", "config", "home", "tmp", "plugins"):
        assert first[name].parent == first["root"]
    # Claude Code falls back to a temp folder every session shares when the one
    # it is given has a long path; a 28-character one was measured to be used.
    assert len(f"/private/tmp/{retry['tmp'].relative_to(run_root.parent)}") <= 28

    first["tmp"].mkdir(parents=True)
    assert not claude_code.sandbox_used_own_temp(first["tmp"])
    (first["tmp"] / f"claude-{os.getuid()}").mkdir()
    assert claude_code.sandbox_used_own_temp(first["tmp"])


def test_child_environment_passes_nothing_of_the_operators(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = claude_code.child_environment(
        "key", config_dir=tmp_path / "c", home_dir=tmp_path / "h", tmp_dir=tmp_path / "t",
    )
    assert set(env) == {
        "PATH", "HOME", "TMPDIR", "CLAUDE_CODE_TMPDIR", "LANG", "ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_AUTOUPDATER",
    }
    assert env["HOME"] == str(tmp_path / "h")
    # Sandboxed commands get their $TMPDIR under this one, not the shared default.
    assert env["CLAUDE_CODE_TMPDIR"] == env["TMPDIR"] == str(tmp_path / "t")
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


def test_plugin_is_described_once_and_copied_per_attempt(tmp_path):
    source = tmp_path / "pack"
    (source / ".claude-plugin").mkdir(parents=True)
    (source / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "pack", "version": "1.2.3"}))
    for name in ("emails", "analytics"):
        (source / "skills" / name).mkdir(parents=True)
        (source / "skills" / name / "SKILL.md").write_text("---\nname: x\n---\n")
    (source / ".git").mkdir()

    described = claude_code.describe_plugin(source)
    assert described["name"] == "pack" and described["version"] == "1.2.3"
    assert described["skills"] == ["analytics", "emails"]

    # Each attempt gets its own copy: what one session does to a skill reaches
    # neither the checkout nor the next attempt.
    first, second = tmp_path / "a1" / "0-pack", tmp_path / "a2" / "0-pack"
    for destination in (first, second):
        destination.parent.mkdir()
        claude_code.copy_plugin(source, destination)
        assert not (destination / ".git").exists()
    (first / "skills" / "emails" / "SKILL.md").write_text("poisoned")
    assert (second / "skills" / "emails" / "SKILL.md").read_text() == "---\nname: x\n---\n"
    assert (source / "skills" / "emails" / "SKILL.md").read_text() == "---\nname: x\n---\n"

    with pytest.raises(SystemExit, match="not a Claude Code plugin"):
        claude_code.describe_plugin(tmp_path)


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
# the retry of job DIES_TWICE_JOB (attempt folders are named by the job's place
# in the run, then `a` or `b` for the attempt). Its stderr puts the key across
# the cut the error message makes.
FAKE_CLI = """#!{python}
import json, pathlib, sys
if sys.argv[1:] == ["--version"]:
    print("0.0.0 (fake)")
    raise SystemExit(0)
sys.stdin.read()
attempt = pathlib.Path.cwd().parent.name
print(json.dumps({{"type": "system", "subtype": "init", "model": "claude-haiku-5-5"}}))
if attempt.endswith("a") or attempt == "{dies_twice_job}b":
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
    # `dies_twice` is the second task named below, so the run's second job.
    cli.write_text(FAKE_CLI.format(python=sys.executable, dies_twice_job=1, key=key))
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
    # The first session's spend left no receipt, so the attempt's cost is a lower bound.
    assert answered["cost_unknown"] is True
    assert (run_dir / answered["response_path"]).read_text() == "answer"
    # The run directory shows the recorded attempt only, not the first one's draft.
    assert answered["files_written"] == ["final.md"]
    assert [path.name for path in (run_dir / "artifacts" / f"{answers}--claude-code-claude-haiku-5-5--r1").iterdir()] \
        == ["final.md"]
    failed = records[dies_twice]
    assert failed["retried"] is True and "response_path" not in failed
    assert failed["error"].startswith("Claude Code ended without a result event (exit 9): xxx")
    assert "sk-test" not in failed["error"]


# ------------------------------------------------- review of adc4e2e (2026-11-16)

# A second stand-in for the CLI, steered by files beside it (the session's
# environment carries nothing of the test's): `mode` is what it does, and
# `servers.json` what its first event says about MCP servers.
FAKE_AGENT = """#!{python}
import json, os, pathlib, sys, time
here = pathlib.Path(__file__).parent
if sys.argv[1:] == ["--version"]:
    print("0.0.0 (fake)")
    raise SystemExit(0)
sys.stdin.read()
mode = (here / "mode").read_text().strip()
attempt = pathlib.Path.cwd().parent.name
servers = json.loads((here / "servers.json").read_text()) if (here / "servers.json").exists() else []
print(json.dumps({{"type": "system", "subtype": "init", "model": "claude-haiku-5-5", "mcp_servers": servers}}), flush=True)
(here / ("started-" + attempt)).write_text(json.dumps({{"pid": os.getpid(), "cwd": os.getcwd()}}))
if mode == "sleep":
    time.sleep(120)
text = "answer"
if mode == "leak":
    config = json.loads(pathlib.Path(sys.argv[sys.argv.index("--mcp-config") + 1]).read_text())
    text = "key " + os.environ["ANTHROPIC_API_KEY"] + " token " + config["mcpServers"]["magister"]["headers"]["Authorization"]
print(json.dumps({{"type": "assistant", "message": {{"id": "m1", "content": [{{"type": "text", "text": text}}]}}}}))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "usage": {{}}}}))
"""
KEY = "sk-test-0123456789"


def _fake_agent(tmp_path, mode):
    folder = tmp_path / "cli"
    folder.mkdir()
    cli = folder / "claude"
    cli.write_text(FAKE_AGENT.format(python=sys.executable))
    cli.chmod(0o755)
    (folder / "mode").write_text(mode)
    return cli


def _two_tasks():
    tasks = bench.load_tasks()
    return bench._select_tasks(None, "all", tasks, harness=claude_code.HARNESS_ID)[:2]


def _records(results):
    (run_dir,) = results.iterdir()
    rows = [json.loads(line) for line in (run_dir / "attempts.jsonl").read_text().splitlines()]
    return run_dir, {row["task_id"]: row for row in rows}


DRIVER = """
import sys
from pathlib import Path
from eval_runner import bench, claude_code
bench.RESULTS_DIR = Path(sys.argv[1])
raise SystemExit(claude_code.main(sys.argv[2:]))
"""


@pytest.mark.parametrize(("signum", "exit_code"), [(signal.SIGINT, 130), (signal.SIGTERM, 143), (signal.SIGHUP, 129)])
def test_a_stopped_run_ends_its_sessions_and_records_what_happened(tmp_path, signum, exit_code):
    """Each session leads its own process group, so nothing the terminal sends
    reaches it. Stopping the run left sessions running on the key for up to
    half an hour each, wrote no record, and (on a closed terminal) left the
    attempts' folders, sources included, in /tmp."""
    cli = _fake_agent(tmp_path, "sleep")
    first, second = _two_tasks()
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    process = subprocess.Popen(
        [sys.executable, str(driver), str(tmp_path / "results"), "run", "--candidate", "claude-haiku-5-5",
         "--tasks", f"{first},{second}", "--parallel", "1", "--cli", str(cli), "--yes"],
        env={**os.environ, "ANTHROPIC_API_KEY": KEY, "PYTHONPATH": str(bench.REPO_ROOT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        started = cli.parent / "started-0a"
        deadline = time.monotonic() + 30
        while not started.exists():
            assert process.poll() is None and time.monotonic() < deadline, "the first session never started"
            time.sleep(0.05)
        session = json.loads(started.read_text())
        process.send_signal(signum)
        assert process.wait(timeout=30) == exit_code
    finally:
        process.kill()

    _assert_stopped(tmp_path, cli, session, first, second)


def _assert_stopped(tmp_path, cli, session, first, second):
    with pytest.raises(ProcessLookupError):
        os.kill(session["pid"], 0)  # the session went with the run
    assert not Path(session["cwd"]).exists()  # and so did the attempt's folders
    assert not (cli.parent / "started-1a").exists()  # the queued attempt never began
    run_dir, records = _records(tmp_path / "results")
    assert (run_dir / "run.json").exists()
    assert records[first]["error"] == "the run was stopped during this attempt"
    assert (records[first]["dispatched"], records[first]["cost_unknown"]) == (True, True)
    assert records[second]["error"] == "not dispatched: the run was stopped"
    assert (records[second]["dispatched"], records[second]["cost_unknown"]) == (False, False)


def test_a_closed_terminal_stops_the_run_and_still_records_it(tmp_path):
    """After a terminal closes, every write to it fails. The line that announced
    the stop was printed before the sessions were ended, so it raised instead:
    the session in flight ran on, the queued attempt started, and no record was
    written. A hangup sent to a run whose output went elsewhere hid all of it."""
    cli = _fake_agent(tmp_path, "sleep")
    first, second = _two_tasks()
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    terminal, child_end = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, str(driver), str(tmp_path / "results"), "run", "--candidate", "claude-haiku-5-5",
         "--tasks", f"{first},{second}", "--parallel", "1", "--cli", str(cli), "--yes"],
        env={**os.environ, "ANTHROPIC_API_KEY": KEY, "PYTHONPATH": str(bench.REPO_ROOT)},
        stdin=child_end, stdout=child_end, stderr=child_end, start_new_session=True,
        preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),  # the run's own terminal
    )
    os.close(child_end)
    try:
        started = cli.parent / "started-0a"
        deadline = time.monotonic() + 30
        while not started.exists():
            assert process.poll() is None and time.monotonic() < deadline, "the first session never started"
            time.sleep(0.05)
        session = json.loads(started.read_text())
        os.close(terminal)  # the terminal closes: a hangup, and nowhere left to print
        assert process.wait(timeout=30) == 128 + signal.SIGHUP
    finally:
        process.kill()
    _assert_stopped(tmp_path, cli, session, first, second)


def test_a_session_that_has_just_exited_does_not_break_the_stop():
    """On macOS, signalling a group whose only member has exited and not yet
    been reaped is refused as not permitted, not as gone. Raised inside the
    stop, it left the sessions after it running."""
    class Gone:
        pid = 2 ** 22 + 12345  # no such group

    claude_code._kill_group(Gone())  # ProcessLookupError: already tolerated

    def refused(pid, signum):
        raise PermissionError(1, "Operation not permitted")

    original, claude_code.os.killpg = claude_code.os.killpg, refused
    try:
        claude_code._kill_group(Gone())
    finally:
        claude_code.os.killpg = original


def test_two_given_files_that_differ_only_in_case_are_refused(tmp_path):
    """One would overwrite the other in the working folder while the prompt named both."""
    for folder, name in (("a", "Brief.md"), ("b", "brief.md")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / name).write_text("x")

    class Folder:  # a case-sensitive volume holding both
        def iterdir(self):
            return [tmp_path / "a" / "Brief.md", tmp_path / "b" / "brief.md"]

        def __str__(self):
            return "/exports"

    with pytest.raises(SystemExit, match="/exports: two files share a name"):
        claude_code.given_files(Folder())


def test_one_attempts_exception_is_its_own_error_not_the_runs(tmp_path, monkeypatch):
    """An exception in one job ended the run with no run.json and no
    attempts.jsonl, discarding every attempt that had already been paid for."""
    cli = _fake_agent(tmp_path, "answer")
    first, second = _two_tasks()
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    keep = claude_code.keep_written_files

    def keep_or_fail(workspace, staged, destination):
        if second in str(destination):
            raise RuntimeError(f"disk on fire {KEY}")
        return keep(workspace, staged, destination)

    monkeypatch.setattr(claude_code, "keep_written_files", keep_or_fail)

    code = claude_code.main(["run", "--candidate", "claude-haiku-5-5", "--tasks", f"{first},{second}",
                             "--parallel", "1", "--cli", str(cli), "--yes"])

    run_dir, records = _records(tmp_path / "results")
    assert code == 1
    assert "error" not in records[first] and (run_dir / records[first]["response_path"]).read_text() == "answer"
    assert records[second]["error"] == "RuntimeError: disk on fire <api-key>"
    # A session was paid for and its receipt is gone: never recorded as free.
    assert (records[second]["dispatched"], records[second]["cost_unknown"]) == (True, True)
    assert "cost_unknown" not in records[first] and "dispatched" not in records[first]


def test_a_given_file_that_would_replace_a_source_is_refused_before_any_session(tmp_path, monkeypatch):
    """Found mid-run it cost five sessions; and a name differing only in case
    silently replaced the staged source on a volume that does not tell them apart."""
    cli = _fake_agent(tmp_path, "answer")
    tasks = bench.load_tasks()
    source = Path(tasks["ads-ledger-analysis"]["fixtures"][0]).name
    given = tmp_path / "given"
    given.mkdir()
    (given / source.upper()).write_text("not the ledger")
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)

    with pytest.raises(SystemExit, match=f"ads-ledger-analysis: {source.upper()} "):
        claude_code.main(["run", "--candidate", "claude-haiku-5-5", "--tasks", "headline,ads-ledger-analysis",
                          "--files-dir", str(given), "--cli", str(cli), "--yes"])
    assert not (tmp_path / "results").exists() and not list(cli.parent.glob("started-*"))

    with pytest.raises(ValueError, match="share a file name"):
        claude_code.fixture_names({"id": "t", "fixtures": ["a/Ledger.csv", "b/ledger.csv"]})


def test_only_the_requested_model_or_its_dated_name_passes():
    """`claude-opus-5` is a prefix of `claude-opus-5-5`: a prefix test took the
    newer model for the one asked for."""
    def error(requested, actual):
        lines = _events(dict(INIT, model=actual), _assistant("m1", {"type": "text", "text": "x"}), _result())
        return claude_code.attempt_fields(claude_code.parse_stream(lines), requested).get("error")

    assert error("claude-opus-5", "claude-opus-5") is None
    assert error("claude-opus-5", "claude-opus-5-20260801") is None
    assert "not the requested" in error("claude-opus-5", "claude-opus-5-5")
    assert "not the requested" in error("claude-opus-5", "claude-opus-5-5-20261001")


def test_the_shell_is_denied_what_the_run_keeps_outside_the_home(tmp_path):
    """The tasks (with their expected answers), the checkout, an MCP config and
    given files are denied wherever they live. Under the home folder or /tmp
    they already are, and the settings stay exactly as they were."""
    home = Path("/Users/someone")
    inside = [home / "bench", home / "bench" / "eval_runner" / "tasks", Path("/private/tmp/x/mcp.json")]
    def denied(paths):
        return claude_code.sandbox_settings(tmp_path, tmp_path / "home", home, paths)["sandbox"]["filesystem"]["denyRead"]

    assert denied(inside) == denied([]) == ["/Users/someone", "/tmp", "/private/tmp"]
    assert denied([*inside, Path("/srv/tasks"), Path("/var/folders/zz/T/mcp-1.json"), Path("/srv/tasks")]) == [
        "/Users/someone", "/tmp", "/private/tmp", "/srv/tasks", "/var/folders/zz/T/mcp-1.json",
    ]


def test_mcp_secrets_are_the_credential_values_only(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {
        "magister": {"type": "http", "url": "https://example.test/mcp",
                     "headers": {"Authorization": "Bearer tok-0123456789", "Accept": "application/json"}},
        "local": {"command": "server", "env": {"SERVICE_API_KEY": "key-abcdefgh", "LOG_LEVEL": "debug-verbose"},
                  "args": ["--port", "8123456789", "--token", "arg-token-1", "--api-key=arg-key-22", "--verbose"]},
        "remote": {"type": "http", "url": "https://example.test/mcp?api_key=url-key-333&region=us-east-1-long"},
    }}))
    assert claude_code.mcp_secrets(config) == [
        "Bearer tok-0123456789", "tok-0123456789", "key-abcdefgh", "arg-token-1", "url-key-333", "arg-key-22",
    ]


def test_a_reply_that_carries_a_credential_is_redacted_everywhere(tmp_path, monkeypatch):
    """The transcript was redacted and the reply file was built from the stream
    before redaction; the MCP token was redacted nowhere."""
    cli = _fake_agent(tmp_path, "leak")
    (cli.parent / "servers.json").write_text(json.dumps([{"name": "magister", "status": "connected"}]))
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"magister": {
        "type": "http", "url": "https://example.test/mcp", "headers": {"Authorization": "Bearer tok-0123456789"},
    }}}))
    (first, _) = _two_tasks()
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)

    assert claude_code.main(["run", "--candidate", "claude-haiku-5-5", "--tasks", first, "--mcp-config", str(config),
                             "--cli", str(cli), "--yes"]) == 0

    run_dir, records = _records(tmp_path / "results")
    assert (run_dir / records[first]["response_path"]).read_text() == "key <api-key> token <mcp-secret>"
    for path in run_dir.rglob("*"):
        if path.is_file():
            assert KEY not in path.read_text() and "tok-0123456789" not in path.read_text(), path


@pytest.mark.parametrize("servers", [[], [{"name": "magister", "status": "failed"}],
                                     [{"name": "magister", "status": "needs-auth"}, {"name": "other", "status": "connected"}]])
def test_an_attempt_whose_mcp_server_was_not_connected_is_an_error(servers):
    """An expired or refused token leaves the session without the server, and
    its answer would be graded as the arm that has one."""
    lines = _events(dict(INIT, mcp_servers=servers), _assistant("m1", {"type": "text", "text": "x"}), _result())
    summary = claude_code.parse_stream(lines)
    assert "error" not in claude_code.attempt_fields(summary, "claude-haiku-5-5")  # no server was asked for
    fields = claude_code.attempt_fields(summary, "claude-haiku-5-5", ["magister"])
    assert fields["error"].startswith("MCP server magister was ") and "ran without it" in fields["error"]

    connected = _events(dict(INIT, mcp_servers=[{"name": "magister", "status": "connected"}]),
                        _assistant("m1", {"type": "text", "text": "x"}), _result())
    assert "error" not in claude_code.attempt_fields(claude_code.parse_stream(connected), "claude-haiku-5-5", ["magister"])


def test_instructions_in_a_folder_above_the_attempts_stop_the_run(tmp_path, monkeypatch):
    """Claude Code loads CLAUDE.md from every folder above the working folder,
    and the attempts all sit under one shared temp folder."""
    parent = tmp_path / "shared" / "tmp"
    parent.mkdir(parents=True)
    assert not [path for path in claude_code.instructions_above(parent / "mb1") if tmp_path in path.parents]
    (tmp_path / "shared" / "CLAUDE.md").write_text("Always answer in French.")
    assert tmp_path / "shared" / "CLAUDE.md" in claude_code.instructions_above(parent / "mb1")

    cli = _fake_agent(tmp_path, "answer")
    monkeypatch.setattr(claude_code, "ATTEMPT_ROOT_PARENT", str(parent))
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    with pytest.raises(SystemExit, match="CLAUDE.md would be loaded into every session"):
        claude_code.main(["run", "--candidate", "claude-haiku-5-5", "--tasks", "headline", "--cli", str(cli), "--yes"])
    assert list(parent.iterdir()) == [] and not list(cli.parent.glob("started-*"))


def test_a_plugin_arm_is_not_recorded_as_skill_text_in_the_prompt(tmp_path, monkeypatch):
    """`skills_included` means the skill text was pasted into the prompt (the
    report prints "Skills in prompt: yes" and each task's skills). A plugin is
    installed, not pasted: the `agent.plugins` block records it."""
    cli = _fake_agent(tmp_path, "answer")
    plugin = tmp_path / "pack"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "pack", "version": "1.0.0"}))
    (first, _) = _two_tasks()
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)

    assert claude_code.main(["run", "--candidate", "claude-haiku-5-5", "--tasks", first, "--plugin-dir", str(plugin),
                             "--cli", str(cli), "--yes"]) == 0

    run_dir, records = _records(tmp_path / "results")
    meta = json.loads((run_dir / "run.json").read_text())
    assert meta["skills_included"] is False and records[first]["skills_included"] is False
    assert meta["arm"] == "claude-code+skills" and meta["agent"]["plugins"][0]["name"] == "pack"
