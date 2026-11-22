"""The open board: seven areas of marketing, five tasks each (eval_runner/board.json)."""
from __future__ import annotations

import json

import pytest

from eval_runner import bench, claude_code

AREAS = ["copywriting", "paid-ads", "seo-content", "email-lifecycle", "conversion", "analytics", "strategy"]


def test_the_board_is_seven_areas_of_five_open_tasks():
    tasks = bench.load_tasks()
    board = bench.load_board(tasks)
    assert [area["id"] for area in board["areas"]] == AREAS
    assert all(len(area["tasks"]) == 5 for area in board["areas"])
    on = bench.board_task_ids(board)
    assert len(on) == len(set(on)) == 35
    assert all(tasks[task_id]["split"] == "development" for task_id in on)


def test_every_task_is_on_the_board_held_back_or_left_out_with_a_reason():
    tasks = bench.load_tasks()
    board = bench.load_board(tasks)
    on = set(bench.board_task_ids(board))
    held = set(board["held_back"])
    out = {row["id"]: row["why"] for row in board["left_out"]}
    assert held == {task_id for task_id, task in tasks.items() if task["split"] == "holdout"}
    assert on | held | set(out) == set(tasks)
    assert not (on & held) and not (on & set(out)) and not (held & set(out))
    assert all(len(why) >= 30 for why in out.values())


def test_split_board_runs_the_board_in_its_order():
    tasks = bench.load_tasks()
    on = bench.board_task_ids(bench.load_board(tasks))
    assert bench._select_tasks(None, "board", tasks) == on
    assert bench._select_tasks("headline", "board", tasks) == ["headline"]  # --tasks still wins
    # A harness is given only the board tasks it can deliver, in the same order.
    for_claude_code = bench._select_tasks(None, "board", tasks, harness=claude_code.HARNESS_ID)
    assert for_claude_code == [t for t in on if bench.task_supports_harness(tasks[t], claude_code.HARNESS_ID)]
    assert 30 <= len(for_claude_code) <= 35


def test_the_cli_offers_the_board():
    assert bench.TASK_SETS == ("all", "development", "holdout", "board")
    with pytest.raises(SystemExit, match="known: all, development, holdout, board"):
        bench._select_tasks(None, "mystery", bench.load_tasks())


def _damaged(change):
    board = json.loads(bench.BOARD_PATH.read_text())
    change(board)
    return board


@pytest.mark.parametrize("change, message", [
    (lambda b: b["areas"][0]["tasks"].pop(), "five tasks"),
    (lambda b: b["areas"].pop(), "seven areas"),
    (lambda b: b["areas"][1]["tasks"].__setitem__(0, b["areas"][0]["tasks"][0]), "more than once"),
    (lambda b: b["areas"][0]["tasks"].__setitem__(0, "no-such-task"), "no task file"),
    (lambda b: b["areas"][0]["tasks"].__setitem__(0, b["held_back"].pop(0)), "held back"),
    (lambda b: b["left_out"].pop(), "neither on the board"),
    (lambda b: b["left_out"][0].__setitem__("why", ""), "says why"),
])
def test_a_damaged_board_is_refused(tmp_path, change, message):
    path = tmp_path / "board.json"
    path.write_text(json.dumps(_damaged(change)))
    with pytest.raises(ValueError, match=message):
        bench.load_board(bench.load_tasks(), path)
