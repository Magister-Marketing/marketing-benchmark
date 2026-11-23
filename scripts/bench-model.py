#!/usr/bin/env python3
"""Benchmark one model on the results site's board, in one command.

    make bench-model model=claude-opus-5-5-medium web=../marketing-benchmark-web dry_run=1
    make bench-model model=claude-opus-5-5-medium web=../marketing-benchmark-web confirm=SPEND
    make bench-model model=claude-opus-5-5-medium web=... plain=1 confirm=SPEND
    make bench-model model=claude-opus-5-5-medium web=... inside=1 magister=../magister-marketing confirm=SPEND
    make bench-model export=eval_runner/results/<run> web=...      # no spending

The board is the one the site's home page charts: its checkout's
src/lib/current-meta.ts names it, and its data/experiments/<board>/meta.json
sets the runs' settings: the board's tasks (the runner's --split board, which
must list the same ones), provider tools off, the board's effort (the model's
id ends in it, e.g. -medium), the board's judge, and one attempt per task
unless reps= says otherwise.

The setups one invocation makes:

    (default)   + Marketing Skills: ./eval.py <model> --split board --repetitions N --judge <board's> -y
    plain=1     Model only, then + Marketing Skills (the same, once with --no-skills)
    inside=1    Inside Magister only, from Magister's private repository on a
                test lane: magister=<its checkout>'s `make lane-bench lane=<lane,
                default bench> deploy=0 tasks=<the board's> repetitions=N
                judge=<the board's>`, which measures the lane as it runs now.
                Not with plain=1: run the direct setups in a second invocation.

What it does, in order:

1. Refuses, before spending: a candidate that is not in
   eval_runner/models.json (and says how to add one), one not at the board's
   effort, one the board already has in a setup it would run, and a runner
   whose board is not the site's.
2. Prints a cost estimate (the last comparable run's recorded cost, scaled
   by the candidate's list prices against that run's model's over the same
   tokens, plus that run's judge cost) and the exact commands it will run.
   Nothing is spent without confirm=SPEND.
3. Runs each setup, which grades the run and writes report.json.
4. Exports each graded run to the site: report.json copied unchanged to
   data/runs/<run id>.json, the run added to the board's meta.json `runs` (run
   id, setup, judge, and for a Magister run the test lane it ran on) and the
   model to its `models`. A run the site would refuse is refused first, with
   the reason, and nothing is changed: another judge, provider tools on, a
   board task missing or titled otherwise than the site has it, an attempt
   lost to a run error (`python -m eval_runner.bench retry` it first), a
   harness that is none of the board's setups, a Magister run not made on a
   test lane, a second run of a model in one setup.
5. Writes a draft post for X, tweet.txt, next to the run: plain text under
   280 characters, every number read from the site's data the way the board
   reads it: tasks fully right out of the board's tasks (never the checklist
   average), the model's other setups on the board, its rank by tasks fully
   right among the board's runs in the setup (ties said as ties), the
   attempts per task, and the run's page. Then rewrites the draft of every
   other run on the board that is on disk, since a new run moves their ranks.

Keys are read from --env-file (only the three provider keys eval.py reads).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_FILE = REPO_ROOT / "eval_runner" / "models.json"
RESULTS_DIR = REPO_ROOT / "eval_runner" / "results"
# The runner's open board: the tasks --split board runs.
BOARD_FILE = REPO_ROOT / "eval_runner" / "board.json"
# The one place the site names the board its home page charts
# (readCurrentMeta), and where each board's meta.json lives.
CURRENT_SOURCE = Path("src") / "lib" / "current-meta.ts"
CURRENT_NAME = re.compile(r'read<CurrentMeta>\(\s*"([^"]+)"\s*\)')
EXPERIMENTS = Path("data") / "experiments"
SITE_RUNS = Path("data") / "runs"
TASK_BLURBS = Path("data") / "task-blurbs.json"
SITE_URL = "https://marketingbenchmark.ai"
CONFIRM_WORD = "SPEND"
TWEET_LIMIT = 280
HARNESS_PREFIXES = ("magister-", "claude-code-")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# The board's setups, in its order, as the site titles them.
SETUP_TITLES = {"no-skills": "Model only", "skills": "+ Marketing Skills", "magister": "Inside Magister"}
# A setup after a count in a post ("19 as the model only"), and after a rank.
SETUP_WORDS = {"no-skills": "as the model only", "skills": "with the Marketing Skills", "magister": "inside Magister"}
RANK_WORDS = {"no-skills": "with no skills", "skills": "with the skills", "magister": "inside Magister"}


class Refusal(SystemExit):
    """A stop with a message for the person running the command."""

    def __init__(self, message: str) -> None:
        super().__init__(f"bench-model: {message}")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


# ------------------------------------------------------------ the catalog

def load_catalog() -> dict:
    return json.loads(MODELS_FILE.read_text())


def require_candidate(model: str, catalog: dict) -> dict:
    if model in catalog:
        return catalog[model]
    raise Refusal(
        f"{model!r} is not in eval_runner/models.json. Add it first: an entry "
        'with "model" (provider/model id, e.g. "openai/gpt-6.1-sol"), "pricing" '
        '({"input_per_mtok": ..., "output_per_mtok": ...}, the list prices in '
        'dollars per million tokens) and, for an effort variant, '
        '"reasoning_effort". Then run `python -m eval_runner.bench validate`. '
        "Known candidates: " + ", ".join(sorted(catalog))
    )


# ------------------------------------------------------------- the site

def board_name(web: Path) -> str:
    """The board the site's home page charts, as src/lib/current-meta.ts names it."""
    source = web / CURRENT_SOURCE
    found = CURRENT_NAME.search(source.read_text()) if source.is_file() else None
    if not found:
        raise Refusal(
            f"{web} does not look like the results site: {CURRENT_SOURCE} does not name "
            'the board its home page charts (read<CurrentMeta>("<experiment>"))'
        )
    return found.group(1)


def site_paths(web: Path) -> tuple[Path, Path]:
    meta = web / EXPERIMENTS / board_name(web) / "meta.json"
    runs = web / SITE_RUNS
    if not meta.is_file() or not runs.is_dir():
        raise Refusal(
            f"{web} does not look like the results site: {meta.relative_to(web)} or {SITE_RUNS} is missing"
        )
    return meta, runs


def read_meta(web: Path) -> dict:
    meta, _ = site_paths(web)
    return json.loads(meta.read_text())


def site_report(web: Path, run_id: str) -> dict:
    return json.loads((web / SITE_RUNS / f"{run_id}.json").read_text())


def shared_tasks(meta: dict) -> list[str]:
    """The tasks every setup can do: the board's score is over these."""
    return [t for t in meta["tasks"] if t not in meta.get("harness_only", [])]


def due_tasks(meta: dict, setup: str) -> list[str]:
    """The tasks a run in this setup must have made, as the site checks: all
    of the board's for a Magister run, the shared ones for a direct call."""
    return list(meta["tasks"]) if setup == "magister" else shared_tasks(meta)


def runner_board_tasks() -> list[str]:
    """The tasks --split board runs, area by area (eval_runner.bench.board_task_ids)."""
    return [t for area in json.loads(BOARD_FILE.read_text())["areas"] for t in area["tasks"]]


def require_same_board(meta: dict) -> None:
    ours, theirs = runner_board_tasks(), list(meta["tasks"])
    if sorted(ours) != sorted(theirs):
        raise Refusal(
            "the runner's board (eval_runner/board.json, what --split board runs) is not the "
            f"site's (meta.json `tasks`): only in the runner's: "
            f"{', '.join(t for t in ours if t not in theirs) or 'none'}; only on the site's: "
            f"{', '.join(t for t in theirs if t not in ours) or 'none'}"
        )


def plain_model(candidate: str) -> str:
    for prefix in HARNESS_PREFIXES:
        if candidate.startswith(prefix):
            return candidate[len(prefix):]
    return candidate


def model_of(report: dict) -> str:
    """The model a one-model report ran, without its harness prefix."""
    return plain_model(next(iter(report["models"])))


def setup_of(report: dict) -> str:
    """The board setup a report (or run.json) was made in, as the site reads it."""
    harness = report.get("harness") or "direct-api"
    if harness == "direct-api":
        return "skills" if report.get("skills_included") else "no-skills"
    if harness == "magister-agent":
        return "magister"
    raise Refusal(
        f"run {report.get('run_id')} was made with harness {harness!r}; the board's setups are "
        "model only and + Marketing Skills (direct-api) and inside Magister (magister-agent)"
    )


def effort_of(model: str) -> str | None:
    last = model.split("-")[-1]
    return last if last in EFFORTS else None


def base_of(model: str) -> str:
    effort = effort_of(model)
    return model[: -(len(effort) + 1)] if effort else model


def require_board_effort(model: str, meta: dict) -> None:
    effort = effort_of(model)
    if effort != meta["effort"]:
        raise Refusal(
            f"the board runs every model at {meta['effort']} effort, and {model} is "
            f"{f'at {effort} effort' if effort else 'not named with an effort'}: use its "
            f"-{meta['effort']} id (add that to eval_runner/models.json first if it is missing)"
        )


# The names label_from_id gets wrong (data.ts MODEL_LABELS).
MODEL_LABELS = {"glm-5.3": "GLM-5.3"}


def model_label(model: str) -> str:
    """The model's name as the site prints it (data.ts modelMeta: its
    MODEL_LABELS, else the same rule from the bench id), without the effort."""
    base = base_of(model)
    if base in MODEL_LABELS:
        return MODEL_LABELS[base]
    return label_from_id(base)


def label_from_id(base: str) -> str:
    """A name from a bench id: "gpt-6.1-sol" is GPT-6.1 Sol, "claude-opus-5-5"
    Claude Opus 5.5, "gemini-3.8-flash" Gemini 3.8 Flash. Runs of version
    numbers join with dots; GPT keeps its hyphen."""
    words: list[str] = []
    for token in base.split("-"):
        number = token.replace(".", "").isdigit()
        if token == "gpt":
            words.append("GPT")
        elif number and words and words[-1] == "GPT":
            words[-1] = f"GPT-{token}"
        elif number and words and words[-1].replace(".", "").isdigit():
            words[-1] = f"{words[-1]}.{token}"
        else:
            words.append(token[:1].upper() + token[1:])
    return " ".join(words)


# ------------------------------------------------------------- the post

def entry_of(report: dict, setup: str, tasks: list[str]) -> dict:
    """What the board reads from a report over its tasks: its tasks fully
    right, the tasks on which every attempt was right (fully-right.ts)."""
    (candidate, _), = report["models"].items()
    reps = report["repetitions"]
    passed = dict.fromkeys(tasks, 0)
    for sub in report.get("submissions") or []:
        if sub["model_id"] == candidate and sub["task_id"] in passed:
            passed[sub["task_id"]] += sum(1 for run in sub["runs"] if run.get("pass"))
    return {
        "run_id": report["run_id"],
        "model": plain_model(candidate),
        "setup": setup,
        "repetitions": reps,
        "right": sum(1 for n in passed.values() if n == reps),
    }


def tweet_for(web: Path, run_id: str, site_url: str = SITE_URL) -> str:
    """A draft under 280 characters about the run, from the site's data, as
    the board scores it: tasks fully right out of the board's tasks, the
    model's other setups on the board, its rank by tasks fully right among
    the board's runs in the same setup, the attempts per task, the other
    models in the setup, and the run's page."""
    meta = read_meta(web)
    tasks = shared_tasks(meta)
    entries = [entry_of(site_report(web, r["run_id"]), r["setup"], tasks) for r in meta["runs"]]
    entry = next((e for e in entries if e["run_id"] == run_id), None)
    if entry is None:
        raise Refusal(f"{run_id} is not on the site's board; export it first")
    model, setup, reps = entry["model"], entry["setup"], entry["repetitions"]
    label = model_label(model)
    name = f"{label} ({meta['effort']} effort)"
    # The model's other setups on the board, in the board's order, when they
    # made as many attempts per task.
    others = "".join(
        f", {e['right']} {'without' if setup == 'skills' and e['setup'] == 'no-skills' else SETUP_WORDS[e['setup']]}"
        for s in meta["setups"]
        for e in entries
        if e["setup"] == s != setup and e["model"] == model and e["repetitions"] == reps
    )
    # Ranked on tasks fully right alone: two runs with as many share a rank.
    peers = [e for e in entries if e["setup"] == setup]
    rank = 1 + sum(1 for e in peers if e["right"] > entry["right"])
    tied = sum(1 for e in peers if e["right"] == entry["right"]) > 1
    counts = sorted({e["repetitions"] for e in peers})
    mixed = f" (made {' or '.join(map(str, counts))} attempts per task)" if len(counts) > 1 else ""
    ranked = (
        f" {'Tied ' if tied else ''}#{rank} of {len(peers)} models {RANK_WORDS[setup]}{mixed}."
        if len(peers) > 1 else ""
    )
    attempts = " One attempt per task." if reps == 1 else f" {reps} attempts per task, all {reps} right to count."
    judge = " It is also the judge." if base_of(model) == meta["judge_model"] else ""

    def head(bench: str = " on the Marketing Benchmark", who: str = name, rank_note: str = ranked) -> str:
        return (
            f"{who} got {entry['right']} of {len(tasks)} marketing tasks fully right{bench} "
            f"{SETUP_WORDS[setup]}{others}.{rank_note}{attempts}{judge}"
        )

    url = f"{site_url}/runs/{run_id}"
    # A long name with every note can run over: the benchmark's name goes
    # first (the address names it), then the effort (every model on the board
    # is at it), then the rank. The count, the model's other setups, the
    # attempts and the judge always stay.
    for text in (head(), head(bench=""), head(bench="", who=label), head(bench="", who=label, rank_note="")):
        if len(text) + 1 + len(url) <= TWEET_LIMIT:
            break
    # The other models in the setup, most tasks fully right first, while they fit.
    compare = ""
    for e in sorted((e for e in peers if e["model"] != model), key=lambda e: -e["right"]):
        piece = f"{model_label(e['model'])} {e['right']}"
        trial = f"{compare} · {piece}" if compare else f"\nvs {piece}"
        if len(text) + len(trial) + 1 + len(url) > TWEET_LIMIT:
            break
        compare = trial
    text = f"{text}{compare}\n{url}"
    if len(text) > TWEET_LIMIT:
        raise Refusal(f"the draft is {len(text)} characters, over {TWEET_LIMIT}: {text!r}")
    return text


# ------------------------------------------------------------- the export

def lost_attempts(report: dict, tasks: list[str]) -> list[str]:
    """The attempts at these tasks lost to a run error: marked E without
    stopping at the output limit, as the site's board.ts tells them apart."""
    return [
        f"{sub['task_id']} attempt {run['repetition']}"
        for sub in report.get("submissions") or []
        if sub["task_id"] in tasks
        for run in sub["runs"]
        if run.get("mark") == "E" and run.get("finish_reason") != "max_tokens"
    ]


def mistitled(web: Path, report: dict, tasks: list[str]) -> list[str]:
    """The board's tasks this run titles otherwise than data/task-blurbs.json,
    each with both titles."""
    blurbs = json.loads((web / TASK_BLURBS).read_text())["tasks"]
    site_titles = {t: (blurbs.get(t) or {}).get("title") for t in tasks}
    return sorted({
        f"{sub['task_id']} is titled {sub.get('task_title')!r} here and {site_titles[sub['task_id']]!r} on the site"
        for sub in report.get("submissions") or []
        if sub["task_id"] in site_titles and sub.get("task_title") != site_titles[sub["task_id"]]
    })


def lane_of(run_dir: Path) -> str:
    """Where a Magister run was made, from run.json, in the site's words."""
    identity = json.loads((run_dir / "run.json").read_text()).get("eval_identity") or {}
    target = identity.get("eval_target") or ""
    if not target.startswith("lane:"):
        raise Refusal(
            f"the site charts Magister runs made on a test lane; {run_dir.name} ran on {target or 'an unrecorded target'}"
        )
    sha = (identity.get("gateway_sha") or "")[:9]
    return f"a test lane ({target[len('lane:'):]}), not production (gateway {sha})"


def export_run(run_dir: Path, web: Path, ran_on: str | None = None) -> dict:
    """Copy a graded run's report to the site and list it on the board.
    Returns the board entry it added (or found). A run the site would refuse
    is refused here first, before any file changes."""
    meta_path, runs_dir = site_paths(web)
    report_path = run_dir / "report.json"
    grading_path = run_dir / "grading.json"
    if not report_path.is_file() or not grading_path.is_file():
        raise Refusal(f"{run_dir} has no report.json or grading.json: grade and report it first")
    report = json.loads(report_path.read_text())
    grading = json.loads(grading_path.read_text())
    meta = json.loads(meta_path.read_text())
    run_id = report["run_id"]
    if len(report["models"]) != 1:
        raise Refusal(f"{run_id} holds {len(report['models'])} models; the board takes one per run")
    if (grading.get("judge_model"), grading.get("judge_protocol_version")) != (
        meta["judge_model"], meta["judge_protocol_version"]
    ):
        raise Refusal(
            f"{run_id} was graded by {grading.get('judge_model')} (protocol "
            f"{grading.get('judge_protocol_version')}); the board's runs by "
            f"{meta['judge_model']} (protocol {meta['judge_protocol_version']}). "
            "Grade it with the board's judge first."
        )
    setup = setup_of(report)
    model = model_of(report)
    require_board_effort(model, meta)
    if setup != "magister" and report.get("tools_enabled") is not False:
        raise Refusal(f"{run_id} was made with the provider's tools on; the board's direct calls are made with them off")
    due = due_tasks(meta, setup)
    missing = [t for t in due if t not in report["tasks"]]
    if missing:
        raise Refusal(f"{run_id} lacks the board's tasks {', '.join(missing)}")
    titles = mistitled(web, report, meta["tasks"])
    if titles:
        raise Refusal(
            f"{run_id} titles a board task otherwise than the site: {'; '.join(titles)}. "
            "The site's data/task-blurbs.json has to match the runner's tasks first."
        )
    lost = lost_attempts(report, due)
    if lost:
        raise Refusal(
            f"{run_id} has attempts lost to a run error: {', '.join(lost)}. The board takes no run "
            f"with a lost attempt: run them again with `python -m eval_runner.bench retry --run {run_dir}`, "
            "grade the tasks it names, report, then export."
        )
    listed = next((r for r in meta["runs"] if r["run_id"] == run_id), None)
    for other in meta["runs"]:
        if other is not listed and other["setup"] == setup and model_of(site_report(web, other["run_id"])) == model:
            raise Refusal(
                f"the board already has {other['run_id']} for {model} ({setup}). If {run_id} "
                "replaces it, take the old run out of meta.json and data/runs first."
            )
    entry: dict = listed or {
        "run_id": run_id,
        "setup": setup,
        "judge_model": grading["judge_model"],
        "judge_protocol_version": grading["judge_protocol_version"],
    }
    if listed is None and setup == "magister":
        entry["ran_on"] = ran_on or lane_of(run_dir)
    target = runs_dir / f"{run_id}.json"
    if target.exists() and target.read_bytes() != report_path.read_bytes():
        raise Refusal(f"{target} exists and differs from {report_path}; the site's copies are never edited")

    if not target.exists():
        shutil.copyfile(report_path, target)
    if listed is None:
        meta["runs"].append(entry)
        if model not in meta["models"]:
            meta["models"].append(model)
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return entry


# ------------------------------------------------------------- the estimate

def search_dirs() -> list[Path]:
    """Where to look for earlier run folders: this checkout's results, any
    listed in BENCH_RESULTS_DIRS, and sibling checkouts' results."""
    dirs = [RESULTS_DIR]
    dirs += [Path(p) for p in os.environ.get("BENCH_RESULTS_DIRS", "").split(os.pathsep) if p]
    dirs += sorted(REPO_ROOT.parent.glob("*/eval_runner/results"))
    seen, out = set(), []
    for d in dirs:
        key = d.resolve()
        if d.is_dir() and key not in seen:
            seen.add(key)
            out.append(d)
    return out


def find_runs(run_id: str) -> list[Path]:
    """Every folder of this run on disk, in search_dirs() order."""
    return [d / run_id for d in search_dirs() if (d / run_id / "attempts.jsonl").is_file()]


def find_run(run_id: str) -> Path | None:
    found = find_runs(run_id)
    return found[0] if found else None


def comparable_run(meta: dict, setup: str, like: Path | None) -> Path | None:
    """The run whose recorded cost prices the estimate: --like if given, else
    the newest run on the site's board in the same setup that is on disk."""
    if like:
        return like
    for r in sorted(meta["runs"], key=lambda r: r["run_id"], reverse=True):
        if r["setup"] == setup:
            found = find_run(r["run_id"])
            if found:
                return found
    return None


def estimate(run_dir: Path, pricing: dict, tasks: list[str], reps: int) -> dict:
    """What `reps` attempts at every task should cost: the comparable run's
    recorded model cost per attempt on each task, scaled by how the
    candidate's list prices compare with that run's model's over the same
    tokens, plus that run's judge cost per attempt. Scaling the recorded cost
    keeps what a harness saves (an agent's prompts are mostly read from cache)."""
    tokens: dict[str, list[tuple[int, int]]] = {}
    for a in read_jsonl(run_dir / "attempts.jsonl"):
        if a.get("task_id") in tasks and a.get("input_tokens") is not None and a.get("output_tokens") is not None:
            # The report's cost of a decoy task's attempt is both turns, so
            # its tokens are too.
            tokens.setdefault(a["task_id"], []).append((
                a["input_tokens"] + (a.get("decoy_input_tokens") or 0),
                a["output_tokens"] + (a.get("decoy_output_tokens") or 0),
            ))
    report = json.loads((run_dir / "report.json").read_text())
    costs: dict[str, list[float]] = {}
    for sub in report.get("submissions") or []:
        if sub["task_id"] in tasks:
            costs.setdefault(sub["task_id"], []).extend(
                r["cost_usd"] for r in sub["runs"] if r.get("cost_usd") is not None
            )
    absent = [t for t in tasks if not tokens.get(t) or not costs.get(t)]
    if absent:
        raise Refusal(f"{run_dir.name} has no tokens or cost for {', '.join(absent)}: pass like=<another run>")
    tokens_in = sum(mean([i for i, _ in v]) for v in tokens.values()) * reps
    tokens_out = sum(mean([o for _, o in v]) for v in tokens.values()) * reps
    recorded = sum(mean(v) for v in costs.values()) * reps
    run = json.loads((run_dir / "run.json").read_text())
    (basis_model, basis_spec), = (run.get("models") or {}).items()
    old = basis_spec["pricing"]
    ratio = (
        tokens_in * pricing["input_per_mtok"] + tokens_out * pricing["output_per_mtok"]
    ) / (tokens_in * old["input_per_mtok"] + tokens_out * old["output_per_mtok"])
    grading = json.loads((run_dir / "grading.json").read_text())
    usage = grading.get("judge_usage") or {}
    judge_cost = (usage.get("cost_usd") or 0.0) / max(usage.get("calls") or 1, 1) * len(tasks) * reps
    model_cost = recorded * ratio
    return {
        "basis": run_dir.name,
        "basis_model": basis_model,
        "attempts": len(tasks) * reps,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "ratio": ratio,
        "model_usd": model_cost,
        "judge_usd": judge_cost,
        "total_usd": model_cost + judge_cost,
    }


# ------------------------------------------------------------- running

def newest_run_since(marker: float, model: str, setup: str) -> Path:
    """The newest run folder made since `marker` for this model and setup.
    Another run going at the same time in this checkout (another model, or
    the same model in another setup) makes folders too; those are not it."""
    fresh = []
    if RESULTS_DIR.is_dir():
        for d in RESULTS_DIR.iterdir():
            if not (d.is_dir() and d.stat().st_mtime >= marker and (d / "run.json").is_file()):
                continue
            try:
                run = json.loads((d / "run.json").read_text())
                ours = [plain_model(m) for m in run.get("models") or {}] == [model] and setup_of(run) == setup
            except (ValueError, Refusal):  # still being written, or a harness the board does not chart
                continue
            if ours:
                fresh.append(d)
    if not fresh:
        raise Refusal(f"no new run folder for {model} ({setup}) appeared under {RESULTS_DIR}")
    return max(fresh, key=lambda d: d.name)


def eval_command(args: argparse.Namespace, judge: str, plain: bool) -> list[str]:
    """A direct setup as the board ran it: its tasks, provider tools off."""
    cmd = [sys.executable, str(REPO_ROOT / "eval.py"), args.model, "--split", "board"]
    if plain:
        cmd.append("--no-skills")
    cmd += ["--repetitions", str(args.reps), "--judge", judge, "-y"]
    if args.env_file:
        cmd += ["--env-file", str(args.env_file)]
    return cmd


def lane_command(args: argparse.Namespace, tasks: list[str], judge: str) -> list[str]:
    cmd = [
        "make", "-C", str(args.magister), "lane-bench",
        f"lane={args.lane}", f"bench_repo={REPO_ROOT}", "confirm=RUN_LANE_BENCH", "deploy=0",
        f"candidate={args.model}", f"tasks={','.join(tasks)}", f"repetitions={args.reps}",
        f"judge={judge}", f"bench_python={sys.executable}",
    ]
    if args.env_file:
        cmd.append(f"bench_env_file={args.env_file.resolve()}")
    return cmd


def run_and_export(
    cmd: list[str], model: str, setup: str, web: Path, ran_on: str | None, site_url: str
) -> None:
    marker = time.time() - 1
    print(f"\n$ {shlex.join(cmd)}", flush=True)
    code = subprocess.call(cmd, cwd=REPO_ROOT)
    run_dir = newest_run_since(marker, model, setup)
    if code != 0:
        print(
            f"bench-model: the run exited {code}; exporting {run_dir.name} as it stands "
            "(the board refuses a run with an attempt lost to a run error: retry those first)",
            file=sys.stderr,
        )
    export_and_draft(run_dir, web, ran_on, site_url)


def export_and_draft(run_dir: Path, web: Path, ran_on: str | None, site_url: str) -> None:
    entry = export_run(run_dir, web, ran_on)
    tweet = tweet_for(web, entry["run_id"], site_url)
    (run_dir / "tweet.txt").write_text(tweet + "\n")
    print(f"\nExported {entry['run_id']} to {web}'s board {board_name(web)} ({SETUP_TITLES[entry['setup']]}).")
    print(f"Tweet draft ({len(tweet)} characters), saved to {run_dir / 'tweet.txt'}:\n")
    print(tweet)
    refresh_drafts(web, site_url)


def refresh_drafts(web: Path, site_url: str) -> list[Path]:
    """Rewrite the tweet draft of every run on the board. A new run moves the
    others' ranks ("#2 of 4"), so a draft written at an earlier export goes
    stale; each is rewritten from the site's data as it stands, in every
    folder of that run on disk. Returns the drafts changed."""
    meta = read_meta(web)
    changed, missing = [], []
    for r in meta["runs"]:
        folders = find_runs(r["run_id"])
        if not folders:
            missing.append(r["run_id"])
            continue
        try:
            text = tweet_for(web, r["run_id"], site_url) + "\n"
        except Refusal as refusal:
            print(f"  {r['run_id']}: no draft: {refusal}", file=sys.stderr)
            continue
        for folder in folders:
            draft = folder / "tweet.txt"
            if not draft.is_file() or draft.read_text() != text:
                draft.write_text(text)
                changed.append(draft)
    print(f"\nRefreshed every run's draft against the board: {len(changed)} changed.")
    for draft in changed:
        print(f"  {draft}")
    if missing:
        print(
            f"  Not on disk here, so not refreshed ({len(missing)}): {', '.join(missing)}. "
            "Point BENCH_RESULTS_DIRS at their results folders to refresh them too."
        )
    return changed


def setups_of(args: argparse.Namespace) -> list[str]:
    """The board setups a run of this command makes, in the board's order."""
    if args.inside:
        return ["magister"]
    return ["no-skills", "skills"] if args.plain else ["skills"]


def already_listed(web: Path, meta: dict, model: str, setups: list[str]) -> list[tuple[str, str]]:
    """The board's runs of this model in these setups, as (run id, setup):
    a new run of either would be refused at export."""
    return [
        (r["run_id"], r["setup"])
        for r in meta["runs"]
        if r["setup"] in setups and model_of(site_report(web, r["run_id"])) == model
    ]


def print_plan(
    args: argparse.Namespace, web: Path, meta: dict, spec: dict, judge: str, setups: list[str]
) -> list[list[str]]:
    """Print the estimate and the commands a run would make; return those commands."""
    meta_path, _ = site_paths(web)
    print(f"bench-model: {args.model} ({spec['model']}) on the site's board {board_name(web)}: "
          f"{len(meta['tasks'])} tasks (--split board), {args.reps} attempt{'' if args.reps == 1 else 's'} "
          f"per task, provider tools off, {meta['effort']} effort, judge {judge}")
    print(f"  setups: {', '.join(SETUP_TITLES[s] for s in setups)}")
    print(f"  list prices: ${spec['pricing']['input_per_mtok']}/M input, ${spec['pricing']['output_per_mtok']}/M output")
    total = 0.0
    commands = []
    for setup in setups:
        basis = comparable_run(meta, setup, args.like)
        if basis is None:
            print(f"  {SETUP_TITLES[setup]}: no comparable run on disk to price an estimate from; pass like=<run folder>")
        else:
            est = estimate(basis, spec["pricing"], due_tasks(meta, setup), args.reps)
            total += est["total_usd"]
            print(
                f"  {SETUP_TITLES[setup]}: about ${est['model_usd']:.2f} in model calls + ${est['judge_usd']:.2f} judge "
                f"= ${est['total_usd']:.2f}: the recorded cost of {est['basis']} ({est['basis_model']}), "
                f"{est['input_tokens'] / est['attempts']:,.0f} input and "
                f"{est['output_tokens'] / est['attempts']:,.0f} output tokens an attempt, "
                f"times {est['ratio']:.2f} for this model's list prices, over {est['attempts']} attempts"
            )
        if setup == "magister":
            commands.append(lane_command(args, meta["tasks"], judge))
        else:
            commands.append(eval_command(args, judge, plain=setup == "no-skills"))
    print(f"  estimate in all: about ${total:.2f}. Answer length moves the real cost either way.")
    if args.inside:
        lanes = sorted({r["ran_on"] for r in meta["runs"] if r["setup"] == "magister" and r.get("ran_on")})
        print(
            "  inside=1: lane-bench measures the lane as it runs now (deploy=0), so bring it up first on "
            "the Magister build to publish; the model must be in Magister's model catalog on that build "
            "(lane-bench enables it in the lane's catalog and stops if the Gateway does not know it)."
            + (f" The board's Magister runs ran on {'; '.join(lanes)}." if lanes else "")
        )
    print("\nIt will run, then export each graded run to the site and draft a tweet:")
    for cmd in commands:
        print(f"  $ {shlex.join(cmd)}")
    print(f"  export to {web / SITE_RUNS} and {meta_path}")
    return commands


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="candidate id from eval_runner/models.json, at the board's effort")
    parser.add_argument("--web", type=Path, help="the results site's checkout (marketing-benchmark-web)")
    parser.add_argument("--plain", action="store_true",
                        help="also the Model only setup (--no-skills), beside + Marketing Skills")
    parser.add_argument("--reps", type=int, default=1, help="attempts per task (default 1, as the board ran)")
    parser.add_argument("--inside", action="store_true",
                        help="the Inside Magister setup alone, on a test lane (not with --plain)")
    parser.add_argument("--magister", type=Path, help="Magister monorepo checkout (inside only)")
    parser.add_argument("--lane", default="bench", help="test lane for inside (default bench)")
    parser.add_argument("--env-file", type=Path, help="KEY=value file with the provider keys")
    parser.add_argument("--like", type=Path, help="run folder whose recorded cost prices the estimate")
    parser.add_argument("--confirm", default="", help=f"type {CONFIRM_WORD} to spend")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and estimate only")
    parser.add_argument("--export", type=Path, help="export this graded run folder and draft its tweet; spends nothing")
    parser.add_argument("--ran-on", help="where a Magister run was made, in the site's words (default from run.json)")
    parser.add_argument("--site-url", default=SITE_URL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # keep stdout and stderr in order

    if args.web is None:
        raise Refusal("web=<marketing-benchmark-web checkout> is required: the site's board sets the tasks and the judge")
    web = args.web.resolve()
    meta = read_meta(web)

    if args.export:
        export_and_draft(args.export.resolve(), web, args.ran_on, args.site_url)
        return 0

    if not args.model:
        raise Refusal("model=<candidate id> is required")
    catalog = load_catalog()
    spec = require_candidate(args.model, catalog)
    require_board_effort(args.model, meta)
    judge = meta["judge_model"]
    if judge not in catalog:
        raise Refusal(f"the site's judge {judge!r} is not in eval_runner/models.json")
    require_same_board(meta)
    if args.inside and args.plain:
        raise Refusal("inside=1 runs the Inside Magister setup alone; run plain=1 (the direct setups) as a second invocation")
    if args.inside and not args.magister:
        raise Refusal("inside=1 needs magister=<Magister monorepo checkout>, where `make lane-bench` lives")

    setups = setups_of(args)
    commands = print_plan(args, web, meta, spec, judge, setups)
    listed = already_listed(web, meta, args.model, setups)
    if listed:
        message = (
            "the board already has "
            + ", ".join(f"{run_id} for {args.model} ({setup})" for run_id, setup in listed)
            + ", so a new run would be refused at export. If it is to replace that run, take the "
            "old one out of meta.json and data/runs first."
        )
        if not args.dry_run:
            raise Refusal(message + " Nothing was spent.")
        print(f"\nNote: {message}")
    if args.dry_run:
        print("\nDry run: nothing was spent.")
        return 0
    if args.confirm != CONFIRM_WORD:
        print(f"\nNothing was spent. To run it, pass confirm={CONFIRM_WORD}.", file=sys.stderr)
        return 2

    for cmd, setup in zip(commands, setups):
        run_and_export(cmd, args.model, setup, web, args.ran_on, args.site_url)
    print(
        f"\nNext: cd {web} && pnpm build (checks every claim on the page against the new data), "
        "then commit data/runs and the board's meta.json."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
