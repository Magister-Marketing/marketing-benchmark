"""Workflow task launch-copy-pack: a launch brief, a claims register and the rules in; 72 assets for four products out.

The task's documents, reference reply and checker live in
eval_runner.task_facts_copy with the other copy tasks; this module is the
workflow interface the runner and gen_workflow_tasks.py read.
"""
from __future__ import annotations

from eval_runner import task_facts_copy as _copy

TASK_ID = _copy.LAUNCH_ID
FIXTURE_DIR = _copy.LAUNCH_DIR


def fixtures() -> dict[str, str]:
    return _copy.launch_fixtures()


def reference_answer() -> str:
    return _copy.launch_reference_answer()


def facts(response_text: str, workflow: str = TASK_ID) -> dict[str, int]:
    return _copy.facts(response_text, TASK_ID)
