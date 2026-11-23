"""`./eval.py`, the one-line entry point, takes every task set the runner has."""
import importlib.util
import sys
from pathlib import Path

import pytest

from eval_runner import bench

EVAL_PY = Path(__file__).resolve().parents[1] / "eval.py"


def _entry():
    spec = importlib.util.spec_from_file_location("eval_entry", EVAL_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("task_set", bench.TASK_SETS)
def test_eval_py_accepts_every_task_set(monkeypatch, task_set):
    """The board is the published benchmark, so the one-line command must be
    able to run it: `--split board` reached `bench.run` and `bench.eval` but
    was refused here."""
    seen = {}
    entry = _entry()
    monkeypatch.setattr(entry.bench, "cmd_eval", lambda args: seen.update(vars(args)) or 0)
    monkeypatch.setattr(sys, "argv", ["eval.py", "gpt-6.2-sol-medium", "--split", task_set, "-y"])
    assert entry.main() == 0
    assert seen["split"] == task_set
    assert seen["models"] == "gpt-6.2-sol-medium"
