#!/usr/bin/env python3
"""Benchmark one model and put it on the results site, in one command.

    make bench-model model=gpt-6.1-sol-high web=../marketing-benchmark-web dry_run=1
    make bench-model model=gpt-6.1-sol-high web=../marketing-benchmark-web confirm=SPEND
    make bench-model model=gpt-6.1-sol-high web=... plain=1 reps=3 confirm=SPEND
    make bench-model model=gpt-6.1-sol-high web=... inside=1 magister=../magister-marketing confirm=SPEND
    make bench-model export=eval_runner/results/<run> web=...      # no spending

What it does, in order:

1. Refuses a candidate that is not in eval_runner/models.json, and says how to
   add one.
2. Prints a cost estimate (the last comparable run's recorded cost, scaled
   by the candidate's list prices against that run's model's over the same
   tokens, plus that run's judge cost) and the exact commands it will run. Nothing is spent without `confirm=SPEND`.
3. Runs the one-call benchmark on the site's tasks: with the skills in the
   prompt, and also without them when `plain=1` (`./eval.py <model> --tools
   [--no-skills] --tasks ... --repetitions N --judge <site judge> -y`), which
   grades the run and writes report.json. With `inside=1` it runs the same
   tasks through the Magister agent on a test lane instead, through the
   Magister monorepo's `make lane-bench`.
4. Exports each graded run to the site: report.json copied unchanged to
   data/runs/<run id>.json, and one entry added to the board's meta.json
   (the setup, the judge from grading.json, any attempt lost to a run error
   with the runner's record of it, and for a Magister run the test lane it ran
   on). The site's build checks every number and claim against these files.
5. Writes a tweet draft, tweet.txt, next to the run: plain text under 280
   characters, every number read from the site's data the same way the
   model's page reads it, with the page's URL. Then rewrites the draft of
   every other run on the board that is on disk, since a new run moves their
   ranks and counts.

Keys are read from --env-file (only the three provider keys eval.py reads).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_FILE = REPO_ROOT / "eval_runner" / "models.json"
RESULTS_DIR = REPO_ROOT / "eval_runner" / "results"
# The site's board: which runs it charts and who graded them.
BOARD_META = Path("data") / "experiments" / "20261118-model-board" / "meta.json"
SITE_RUNS = Path("data") / "runs"
SITE_URL = "https://marketingbenchmark.ai"
CONFIRM_WORD = "SPEND"
TWEET_LIMIT = 280
HARNESS_PREFIXES = ("magister-", "claude-code-")
EFFORTS = ("low", "medium", "high", "xhigh", "max")


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

def site_paths(web: Path) -> tuple[Path, Path]:
    meta = web / BOARD_META
    runs = web / SITE_RUNS
    if not meta.is_file() or not runs.is_dir():
        raise Refusal(
            f"{web} does not look like the results site: {BOARD_META} or {SITE_RUNS} is missing"
        )
    return meta, runs


def read_meta(web: Path) -> dict:
    meta, _ = site_paths(web)
    return json.loads(meta.read_text())


def site_report(web: Path, run_id: str) -> dict:
    return json.loads((web / SITE_RUNS / f"{run_id}.json").read_text())


def board_tasks(web: Path, meta: dict) -> list[str]:
    """The tasks every run on the board has, in the first run's order: the
    tasks the site scores every run over."""
    reports = [site_report(web, r["run_id"]) for r in meta["runs"]]
    if not reports:
        raise Refusal("the site's board lists no runs")
    return [t for t in reports[0]["tasks"] if all(t in r["tasks"] for r in reports)]


def plain_model(candidate: str) -> str:
    for prefix in HARNESS_PREFIXES:
        if candidate.startswith(prefix):
            return candidate[len(prefix):]
    return candidate


def model_of(report: dict) -> str:
    """The model a one-model report ran, without its harness prefix."""
    return plain_model(next(iter(report["models"])))


def setup_of(report: dict) -> str:
    harness = report.get("harness") or "direct-api"
    if harness.startswith("direct-api"):
        return "skills" if report.get("skills_included") else "no-skills"
    if harness.startswith("magister-agent"):
        return "magister"
    if harness.startswith("claude-code"):
        return "claude-code"
    raise Refusal(f"run {report.get('run_id')} has harness {harness!r}, which the site does not chart")


# ---------------------------------------------- numbers, as the site reads them

def js_fixed(value: float, digits: int) -> str:
    """JavaScript's toFixed: the exact value rounded half up, so the draft
    prints what the page prints."""
    quantum = Decimal(1).scaleb(-digits)
    return str(Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP))


def fmt_score(score: float) -> str:
    return js_fixed(score, 1)


def fmt_cents(dollars: float) -> str:
    value = dollars * 100
    return f"{js_fixed(value, 1 if value < 10 else 0)}¢"


def entry_of(report: dict, tasks: list[str]) -> dict:
    """What the site's board.ts entryOf reads from a report, over the board's
    tasks: score, attempts, passes, cost per priced attempt, time."""
    (candidate, stats), = report["models"].items()
    scores = stats.get("task_scores") or {}
    attempts = [
        dict(task=s["task_id"], **run)
        for s in report.get("submissions") or []
        if s["model_id"] == candidate and s["task_id"] in tasks
        for run in s["runs"]
    ]
    priced = [a for a in attempts if a.get("cost_usd") is not None]
    timed = [a["latency_seconds"] for a in attempts if a.get("latency_seconds") is not None]
    cost = sum(a["cost_usd"] for a in priced)
    return {
        "run_id": report["run_id"],
        "candidate": candidate,
        "model": plain_model(candidate),
        "setup": setup_of(report),
        "repetitions": report["repetitions"],
        "score": sum(scores[t] for t in tasks) / len(tasks),
        "attempts": len(attempts),
        "passed": sum(1 for a in attempts if a.get("pass")),
        "tasks_passed": sum(
            1 for t in tasks if all(a.get("pass") for a in attempts if a["task"] == t)
        ),
        "cost_usd": cost,
        "cost_missing": len(attempts) - len(priced),
        "cost_per_attempt": cost / len(priced) if priced else 0.0,
        "seconds": sum(timed) / len(timed) if timed else 0.0,
    }


def effort_of(model: str) -> str | None:
    last = model.split("-")[-1]
    return last if last in EFFORTS else None


# The names label_from_id gets wrong (data.ts MODEL_LABELS).
MODEL_LABELS = {"glm-5.3": "GLM-5.3"}


def model_label(model: str) -> str:
    """The model's name as the site prints it (data.ts modelMeta: its
    MODEL_LABELS, else the same rule from the bench id), without the effort."""
    effort = effort_of(model)
    base = model[: -(len(effort) + 1)] if effort else model
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


# ------------------------------------------------------------- the tweet

def tweet_for(web: Path, run_id: str, site_url: str = SITE_URL) -> str:
    """A draft under 280 characters about the run, from the site's data: its
    score, attempts passed, cost per attempt, rank among the board's runs of
    the same setup, the reference models that have a run in that setup, and,
    when the model is also the judge, that it is."""
    meta = read_meta(web)
    tasks = board_tasks(web, meta)
    entries = [entry_of(site_report(web, r["run_id"]), tasks) for r in meta["runs"]]
    entry = next((e for e in entries if e["run_id"] == run_id), None)
    if entry is None:
        raise Refusal(f"{run_id} is not on the site's board; export it first")
    peers = [e for e in entries if e["setup"] == entry["setup"]]
    # Ranked on the score as printed, as the site ranks (board.ts rankIn): two
    # runs that print the same score share a rank.
    shown = lambda e: Decimal(fmt_score(e["score"]))  # noqa: E731
    rank = 1 + sum(1 for e in peers if shown(e) > shown(entry))
    tied = sum(1 for e in peers if shown(e) == shown(entry)) > 1
    label = model_label(entry["model"])
    effort = effort_of(entry["model"])
    name = f"{label} ({effort} effort)" if effort else label
    url = f"{site_url}/models/{entry['model']}"
    how = {
        "skills": "One call per task, skills in the prompt.",
        "no-skills": "One call per task, no skills.",
        "magister": "Run inside Magister's agent.",
        "claude-code": "Run inside Claude Code.",
    }[entry["setup"]]
    # As the model's page says it (src/lib/models.ts peersWord).
    peers_word = {
        "magister": "models inside Magister",
        "claude-code": "models inside Claude Code",
    }.get(entry["setup"], "models")
    lost = entry["cost_missing"]
    lost_note = f" ({lost} lost to a run error)" if lost else ""
    head = (
        f"{name} scored {fmt_score(entry['score'])}/100 on the Marketing Benchmark, "
        f"{'tied ' if tied else ''}#{rank} of {len(peers)} {peers_word}: "
        f"{entry['passed']}/{entry['attempts']} attempts met every requirement"
        f"{lost_note}, at {fmt_cents(entry['cost_per_attempt'])} an attempt. {how}"
    )
    # As the model's page and card say it (board.ts gradesItself).
    effortless = entry["model"][: -len(effort) - 1] if effort else entry["model"]
    if effortless == meta["judge_model"]:
        head += " It is also the judge."
    # A long name with every note can run over: the effort goes first.
    if len(head) + 1 + len(url) > TWEET_LIMIT and effort:
        head = head.replace(name, label, 1)
    # The reference models that have a run in the same setup, best first,
    # as many as fit.
    refs = sorted(
        (
            e for e in peers
            if e["model"] in meta.get("references", []) and e["model"] != entry["model"]
        ),
        key=lambda e: e["score"],
        reverse=True,
    )
    compare = ""
    for e in refs:
        piece = f"{model_label(e['model'])} {fmt_score(e['score'])}"
        trial = f"{compare} · {piece}" if compare else f"\nvs {piece}"
        if len(head) + len(trial) + 1 + len(url) <= TWEET_LIMIT:
            compare = trial
    text = f"{head}{compare}\n{url}"
    if len(text) > TWEET_LIMIT:
        raise Refusal(f"the draft is {len(text)} characters, over {TWEET_LIMIT}: {text!r}")
    return text


# ------------------------------------------------------------- the export

def run_errors(run_dir: Path, report: dict, setup: str) -> list[dict]:
    """The attempts lost to a run error (marked E, not stopped at the output
    limit), each with the runner's record of it and what that was."""
    records = {}
    attempts_file = run_dir / "attempts.jsonl"
    if attempts_file.is_file():
        records = {
            (a.get("task_id"), a.get("repetition")): a.get("error")
            for a in read_jsonl(attempts_file)
        }
    lost = []
    for sub in report.get("submissions") or []:
        for run in sub["runs"]:
            if run.get("mark") != "E" or run.get("finish_reason") == "max_tokens":
                continue
            record = records.get((sub["task_id"], run["repetition"]))
            if not record:
                raise Refusal(
                    f"{sub['task_id']} attempt {run['repetition']} was lost and "
                    "attempts.jsonl has no error for it: the site needs the record"
                )
            timed_out = "timed out" in record.lower()
            if setup == "magister":
                cause = (
                    "the test machine's connection to the test lane timed out; "
                    "the record does not say which side failed"
                    if timed_out
                    else "the agent's stream failed before any answer came back"
                )
            else:
                cause = (
                    "the call to the provider timed out before any answer came back; "
                    "the record does not say which side failed"
                    if timed_out
                    else "the call to the provider failed before any answer came back"
                )
            lost.append({
                "task": sub["task_id"],
                "repetition": run["repetition"],
                "record": record,
                "cause": cause,
            })
    return lost


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
    Returns the board entry it added (or found)."""
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
    tasks = board_tasks(web, meta)
    missing = [t for t in tasks if t not in report["tasks"]]
    if missing:
        raise Refusal(f"{run_id} lacks the board's tasks {', '.join(missing)}")
    setup = setup_of(report)
    model = model_of(report)
    listed = next((r for r in meta["runs"] if r["run_id"] == run_id), None)
    for other in meta["runs"]:
        if other is listed:
            continue
        if other["setup"] == setup and model_of(site_report(web, other["run_id"])) == model:
            raise Refusal(
                f"the board already has {other['run_id']} for {model} ({setup}). If {run_id} "
                "replaces it, take the old run out of meta.json and data/runs first."
            )

    target = runs_dir / f"{run_id}.json"
    if target.exists() and target.read_bytes() != report_path.read_bytes():
        raise Refusal(f"{target} exists and differs from {report_path}; the site's copies are never edited")
    if not target.exists():
        shutil.copyfile(report_path, target)

    if listed is None:
        entry: dict = {
            "run_id": run_id,
            "setup": setup,
            "judge_model": grading["judge_model"],
            "judge_protocol_version": grading["judge_protocol_version"],
        }
        if setup == "magister":
            entry["ran_on"] = ran_on or lane_of(run_dir)
        errors = run_errors(run_dir, report, setup)
        if errors:
            entry["run_errors"] = errors
        meta["runs"].append(entry)
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
        listed = entry
    return listed


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
            tokens.setdefault(a["task_id"], []).append((a["input_tokens"], a["output_tokens"]))
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
            except (ValueError, Refusal):  # still being written, or a harness the site does not chart
                continue
            if ours:
                fresh.append(d)
    if not fresh:
        raise Refusal(f"no new run folder for {model} ({setup}) appeared under {RESULTS_DIR}")
    return max(fresh, key=lambda d: d.name)


def eval_command(args: argparse.Namespace, tasks: list[str], judge: str, plain: bool) -> list[str]:
    cmd = [sys.executable, str(REPO_ROOT / "eval.py"), args.model, "--tools"]
    if plain:
        cmd.append("--no-skills")
    cmd += [
        "--tasks", ",".join(tasks), "--repetitions", str(args.reps),
        "--judge", judge, "-y",
    ]
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
            "(an attempt lost to a run error is listed with the runner's record of it)",
            file=sys.stderr,
        )
    export_and_draft(run_dir, web, ran_on, site_url)


def export_and_draft(run_dir: Path, web: Path, ran_on: str | None, site_url: str) -> None:
    entry = export_run(run_dir, web, ran_on)
    tweet = tweet_for(web, entry["run_id"], site_url)
    (run_dir / "tweet.txt").write_text(tweet + "\n")
    print(f"\nExported {entry['run_id']} to {web} ({entry['setup']}).")
    print(f"Tweet draft ({len(tweet)} characters), saved to {run_dir / 'tweet.txt'}:\n")
    print(tweet)
    refresh_drafts(web, site_url)


def refresh_drafts(web: Path, site_url: str) -> list[Path]:
    """Rewrite the tweet draft of every run on the board. A new run moves the
    others' ranks and counts ("#4 of 6"), so a draft written at an earlier
    export goes stale; each is rewritten from the site's data as it stands,
    in every folder of that run on disk. Returns the drafts changed."""
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
    """The board setups a run of this command makes."""
    if args.inside:
        return ["magister"]
    return ["skills", "no-skills"] if args.plain else ["skills"]


def already_listed(web: Path, meta: dict, model: str, setups: list[str]) -> list[tuple[str, str]]:
    """The board's runs of this model in these setups, as (run id, setup):
    a new run of either would be refused at export."""
    return [
        (r["run_id"], r["setup"])
        for r in meta["runs"]
        if r["setup"] in setups and model_of(site_report(web, r["run_id"])) == model
    ]


def print_plan(
    args: argparse.Namespace, web: Path, meta: dict, spec: dict, tasks: list[str], judge: str
) -> list[list[str]]:
    """Print the estimate and the commands a run would make; return those commands."""
    setups = setups_of(args)
    print(f"bench-model: {args.model} ({spec['model']}), {len(tasks)} tasks from the site's board, "
          f"{args.reps} attempts per task, judge {judge}")
    print(f"  list prices: ${spec['pricing']['input_per_mtok']}/M input, ${spec['pricing']['output_per_mtok']}/M output")
    total = 0.0
    commands = []
    for setup in setups:
        basis = comparable_run(meta, setup, args.like)
        if basis is None:
            print(f"  {setup}: no comparable run on disk to price an estimate from; pass like=<run folder>")
        else:
            est = estimate(basis, spec["pricing"], tasks, args.reps)
            total += est["total_usd"]
            print(
                f"  {setup}: about ${est['model_usd']:.2f} in model calls + ${est['judge_usd']:.2f} judge "
                f"= ${est['total_usd']:.2f}: the recorded cost of {est['basis']} ({est['basis_model']}), "
                f"{est['input_tokens'] / est['attempts']:,.0f} input and "
                f"{est['output_tokens'] / est['attempts']:,.0f} output tokens an attempt, "
                f"times {est['ratio']:.2f} for this model's list prices, over {est['attempts']} attempts"
            )
        if setup == "magister":
            commands.append(lane_command(args, tasks, judge))
        else:
            commands.append(eval_command(args, tasks, judge, plain=setup == "no-skills"))
    print(f"  estimate in all: about ${total:.2f}. Reasoning effort, answer length and web "
          "search move the real cost either way.")
    if args.inside:
        print(
            "  inside=1: the model must be in Magister's own model catalog on the lane's build "
            "(lane-bench enables it in the lane's catalog and stops if the Gateway does not know it)."
        )
    print("\nIt will run, then export each graded run to the site and draft a tweet:")
    for cmd in commands:
        print(f"  $ {shlex.join(cmd)}")
    print(f"  export to {web / SITE_RUNS} and {web / BOARD_META}")
    return commands


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="candidate id from eval_runner/models.json")
    parser.add_argument("--web", type=Path, help="the results site's checkout (marketing-benchmark-web)")
    parser.add_argument("--plain", action="store_true", help="also run without the skills")
    parser.add_argument("--reps", type=int, default=3, help="attempts per task (default 3)")
    parser.add_argument("--inside", action="store_true", help="run through Magister on a test lane instead")
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
    judge = meta["judge_model"]
    if judge not in catalog:
        raise Refusal(f"the site's judge {judge!r} is not in eval_runner/models.json")
    tasks = board_tasks(web, meta)
    if args.inside and not args.magister:
        raise Refusal("inside=1 needs magister=<Magister monorepo checkout>, where `make lane-bench` lives")

    commands = print_plan(args, web, meta, spec, tasks, judge)
    listed = already_listed(web, meta, args.model, setups_of(args))
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

    for cmd, setup in zip(commands, setups_of(args)):
        run_and_export(cmd, args.model, setup, web, args.ran_on, args.site_url)
    print(
        f"\nNext: cd {web} && pnpm build (checks every claim on the page against the new data), "
        "then commit data/runs and the board's meta.json."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
