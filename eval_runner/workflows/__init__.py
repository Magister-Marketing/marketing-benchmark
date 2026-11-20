"""Workflow tasks: several dependent deliverables in one reply, graded by program.

A task file names its workflow (``"workflow": "search-account-build"``). The
module of that name builds the task's files, holds the reference answer, and
turns a reply into measured facts: counts of what the reply got wrong against
the reference. ``facts_for`` is the one entry point the runner calls.

Adding a workflow: a module with ``fixtures() -> {file name: text}``,
``reference_answer() -> str``, ``answers() -> {n: value}`` when the task has
an answer block, and ``facts(response_text) -> {fact: number}``; an entry in
``MODULES``; a task file; and tests that the reference passes every check and
that each kind of wrong answer fails the check written for it.
"""
from __future__ import annotations

from importlib import import_module
from types import ModuleType

MODULES = {
    "search-account-build": "eval_runner.workflows.search_account_build",
}


def module_for(workflow: str) -> ModuleType:
    if workflow not in MODULES:
        raise ValueError(f"unknown workflow {workflow!r}")
    return import_module(MODULES[workflow])


def facts_for(task: dict | None, response_text: str) -> dict:
    """The measured facts a workflow task adds, or nothing for any other task."""
    workflow = (task or {}).get("workflow")
    return module_for(workflow).facts(response_text) if workflow else {}
