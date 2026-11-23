"""Workflow task claims-check: six product pages with 150 claims and their sources in; verdicts and the rewritten pages out.

The task's documents, reference reply and checker live in
eval_runner.task_facts_copy with the other copy tasks; this module is the
workflow interface the runner and gen_workflow_tasks.py read.
"""
from __future__ import annotations

from eval_runner import task_facts_copy as _copy

TASK_ID = _copy.CLAIMS_ID
FIXTURE_DIR = _copy.CLAIMS_DIR


def fixtures() -> dict[str, str]:
    return _copy.claims_fixtures()


def reference_answer() -> str:
    return _copy.claims_reference_answer()


def facts(response_text: str, workflow: str = TASK_ID) -> dict[str, int]:
    return _copy.facts(response_text, TASK_ID)
