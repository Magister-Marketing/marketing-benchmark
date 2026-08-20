#!/usr/bin/env python3
"""Kick off a full eval in one line: run every model, grade, write the report.

    ./eval.py gpt-5.6-luna-medium gpt-5.6-terra-medium gpt-5.6-sol-medium
    ./eval.py claude-sonnet-5 --tools                # with web search
    ./eval.py claude-haiku-4-5 --no-skills -y        # baseline arm, no prompt
    ./eval.py gpt-5.6-sol --tasks headline,blog-post # a task subset
    ./eval.py claude-sonnet-5 --split holdout         # untouched-task check

Model ids come from mvp/models.json; tasks from mvp/tasks/. The run
directory (prompts, raw submissions, judgments, report.md, report.json)
lands under mvp/results/ and its path is printed at the end.

Keys: ANTHROPIC_API_KEY / OPENAI_API_KEY must be in the environment, or
pass --env-file pointing at a KEY=value file. Only those two keys are
read from it, and values are never printed.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mvp import bench  # noqa: E402

API_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def load_env_file(path: str) -> None:
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in API_KEYS and not os.environ.get(key):
            os.environ[key] = value.strip().strip('"').strip("'")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("models", nargs="+", help="model ids from mvp/models.json")
    parser.add_argument("--tasks", help="comma-separated task ids (default: all)")
    parser.add_argument(
        "--split", choices=("all",) + bench.TASK_SPLITS, default="all",
        help="run all tasks or one task split (ignored when --tasks is set)",
    )
    parser.add_argument("--repetitions", type=int, default=bench.REPETITIONS_DEFAULT)
    parser.add_argument("--no-skills", action="store_true",
                        help="omit skill guidance from prompts (baseline arm)")
    parser.add_argument("--tools", action="store_true",
                        help="enable provider-hosted web search (tools arm)")
    parser.add_argument("--judge", default=bench.JUDGE_DEFAULT)
    parser.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    parser.add_argument("--env-file", help="KEY=value file to load API keys from")
    args = parser.parse_args()

    if args.env_file:
        load_env_file(args.env_file)

    return bench.cmd_eval(argparse.Namespace(
        models=",".join(args.models),
        tasks=args.tasks,
        split=args.split,
        repetitions=args.repetitions,
        no_skills=args.no_skills,
        tools=args.tools,
        judge=args.judge,
        yes=args.yes,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
