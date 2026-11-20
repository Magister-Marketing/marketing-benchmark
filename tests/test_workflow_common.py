"""The reply reader every workflow task shares: how a reply's files are found.
A reply written the way models write (a blank line between a file's name and
its fence, a closing list of the files delivered) reads exactly as the
reference does, for every workflow task."""
import json
import re
from pathlib import Path

import pytest

from eval_runner import workflows
from eval_runner.workflows import common

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS = [
    json.loads(path.read_text()) for path in sorted((REPO_ROOT / "eval_runner/tasks").glob("*.json"))
]
# Every workflow task whose reply carries named files (the headline forecasts are answer lines).
FILE_TASKS = sorted(
    task["workflow"] for task in TASKS
    if task.get("workflow") and not task["workflow"].startswith("headline-forecast"))
NAME_LINE = re.compile(r"^### ([a-z0-9][a-z0-9_.-]*\.(?:csv|md))$", re.MULTILINE)


def reference_and_facts(workflow: str) -> tuple[object, str, dict]:
    module = workflows.module_for(workflow)
    reference = module.reference_answer()
    return module, reference, module.facts(reference)


def test_every_file_task_is_covered():
    assert FILE_TASKS == ["launch-trafficking", "lifecycle-program", "outbound-sequence",
                          "price-change-rollout", "search-account-build"]


@pytest.mark.parametrize("workflow", FILE_TASKS)
def test_a_blank_line_between_a_name_and_its_fence_changes_nothing(workflow):
    module, reference, clean = reference_and_facts(workflow)
    spaced = re.sub(r"^(### [^\n]+)\n(```|~~~)", r"\1\n\n\2", reference, flags=re.MULTILINE)
    assert spaced != reference
    assert module.facts(spaced) == clean
    # Several blank lines, and blank lines before an unfenced file, are dropped the same way.
    spaced = re.sub(r"^(### [^\n]+)\n(```|~~~)", r"\1\n\n\n\2", reference, flags=re.MULTILINE)
    assert module.facts(spaced) == clean
    unfenced = re.sub(r"^(### [^\n]+\.csv)\n```[a-z]*\n(.*?)\n```$", r"\1\n\n\n\2", reference,
                      flags=re.MULTILINE | re.DOTALL)
    assert module.facts(unfenced) == clean


@pytest.mark.parametrize("workflow", FILE_TASKS)
def test_a_closing_list_of_the_files_does_not_replace_them(workflow):
    module, reference, clean = reference_and_facts(workflow)
    names = NAME_LINE.findall(reference)
    assert names
    for listing in (
        "\n\nFiles delivered:\n" + "".join(f"- {name}\n" for name in names),
        "\n\n" + "".join(f"### {name}\n\n" for name in names),
        "\n\n" + "".join(f"**{name}**\n```\n```\n" for name in names),
    ):
        assert module.facts(reference + listing) == clean, listing


def test_the_table_reader_drops_leading_blank_lines():
    for text in (
        "### a.csv\n\n```csv\nk,v\n1,2\n```\n",
        "### a.csv\n\n\n```csv\nk,v\n1,2\n```\n",
        "### a.csv\n\n\nk,v\n1,2\n\nprose\n",
        "### a.csv\n   \nk,v\n1,2\n",
    ):
        assert common.tables(text, ["a.csv"]) == {"a.csv": [{"k": "1", "v": "2"}]}, text
    # A fence after the rows still ends the file; a blank line after the rows still ends it.
    assert common.tables("### a.csv\nk,v\n1,2\n```\nk,v\n3,4\n```\n", ["a.csv"]) == {"a.csv": [{"k": "1", "v": "2"}]}
    assert common.tables("### a.csv\nk,v\n1,2\n\n3,4\n", ["a.csv"]) == {"a.csv": [{"k": "1", "v": "2"}]}


def test_the_last_mention_with_something_in_it_wins():
    draft_then_final = "### a.csv\nk,v\n1,2\n\n### a.csv\n```csv\nk,v\n3,4\n```\n"
    assert common.tables(draft_then_final, ["a.csv"]) == {"a.csv": [{"k": "3", "v": "4"}]}
    # A later mention with nothing under it does not replace the file.
    for closing in ("- a.csv\n", "### a.csv\n\n\n", "**a.csv**\n```\n```\n", "### a.csv\n### b.csv\n"):
        text = draft_then_final + "\n" + closing
        assert common.tables(text, ["a.csv", "b.csv"])["a.csv"] == [{"k": "3", "v": "4"}], closing
    # A file mentioned only with nothing under it is present but empty, not missing.
    assert common.tables("Files:\n- a.csv\n- b.csv\n", ["a.csv", "b.csv", "c.csv"]) == {
        "a.csv": [], "b.csv": [], "c.csv": None}


def test_the_document_reader_keeps_the_last_document_with_text():
    text = "### a.md\n```\nfirst\n```\n### a.md\n\n```\nfinal\n```\n"
    assert common.sections(text, ["a.md"]) == {"a.md": "final"}
    for closing in ("- a.md\n", "### a.md\n\n\n", "**a.md**\n```\n```\n", "### a.md\n### b.md\n"):
        assert common.sections(text + "\nFiles:\n" + closing, ["a.md", "b.md"])["a.md"] == "final", closing
    assert common.sections("Files:\n- a.md\n- b.md\n", ["a.md", "b.md", "c.md"]) == {
        "a.md": "", "b.md": "", "c.md": None}
