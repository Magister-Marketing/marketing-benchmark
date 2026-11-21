"""Workflow task catalog-descriptions: a 60-row spec table, a certificate register and a warranty policy in; 60 descriptions out.

The task's documents, reference reply and checker live in
eval_runner.task_facts_copy with the other copy tasks; this module is the
workflow interface the runner and gen_workflow_tasks.py read.
"""
from __future__ import annotations

from eval_runner import task_facts_copy as _copy

TASK_ID = _copy.CATALOG_ID
FIXTURE_DIR = _copy.CATALOG_DIR


def fixtures() -> dict[str, str]:
    return _copy.catalog_fixtures()


def reference_answer() -> str:
    return _copy.catalog_reference_answer()


def facts(response_text: str, workflow: str = TASK_ID) -> dict[str, int]:
    return _copy.facts(response_text, TASK_ID)
