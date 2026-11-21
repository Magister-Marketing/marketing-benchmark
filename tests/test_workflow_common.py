"""The reply reader every workflow task shares: how a reply's files are found.
A reply written the way models write (a blank line between a file's name and
its fence, a closing list of the files delivered) reads exactly as the
reference does, for every workflow task."""
import json
import re
from pathlib import Path

import pytest

from eval_runner import bench, workflows
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


def scores_as_the_reference(workflow: str, text: str) -> None:
    """The reply's facts are the reference's, and every programmatic check is at 1.0."""
    module, _reference, clean = reference_and_facts(workflow)
    assert module.facts(text) == clean
    task = next(task for task in TASKS if task.get("workflow") == workflow)
    results = bench.programmatic_results(task, bench.measured_facts(task, text))
    assert results and all(item["pass"] and item["score"] == 1.0 for item in results.values())


def as_list(names: list[str], marker: str) -> str:
    """The names as list items: "- ", "* ", "+ ", or numbered as "1." or "1)"."""
    if marker in ("1.", "1)"):
        return "\n".join(f"{number}{marker[1]} {name}" for number, name in enumerate(names, 1))
    return "\n".join(f"{marker}{name}" for name in names)


MARKERS = ["- ", "* ", "+ ", "1.", "1)"]
SIGN_OFFS = ["Let me know if you want any changes.", "Happy to adjust any of these, just say which one."]


def test_every_file_task_is_covered():
    assert FILE_TASKS == ["launch-copy-pack", "launch-trafficking",
                          "lifecycle-program", "outbound-sequence", "price-change-rollout", "search-account-build"]


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
    # A file named only with nothing under it is present but empty, not missing; a
    # name in a list is a mention, not a file.
    assert common.tables("### a.csv\n### b.csv\n", ["a.csv", "b.csv", "c.csv"]) == {
        "a.csv": [], "b.csv": [], "c.csv": None}
    assert common.tables("Files:\n- a.csv\n- b.csv\n", ["a.csv", "b.csv"]) == {"a.csv": None, "b.csv": None}


def test_the_document_reader_keeps_the_last_document_with_text():
    text = "### a.md\n```\nfirst\n```\n### a.md\n\n```\nfinal\n```\n"
    assert common.sections(text, ["a.md"]) == {"a.md": "final"}
    for closing in ("- a.md\n", "### a.md\n\n\n", "**a.md**\n```\n```\n", "### a.md\n### b.md\n"):
        assert common.sections(text + "\nFiles:\n" + closing, ["a.md", "b.md"])["a.md"] == "final", closing
    assert common.sections("### a.md\n### b.md\n", ["a.md", "b.md", "c.md"]) == {
        "a.md": "", "b.md": "", "c.md": None}
    assert common.sections("Files:\n- a.md\n- b.md\n", ["a.md", "b.md"]) == {"a.md": None, "b.md": None}


@pytest.mark.parametrize("marker", MARKERS)
@pytest.mark.parametrize("workflow", FILE_TASKS)
def test_a_list_of_the_files_with_a_sentence_after_it_changes_nothing(workflow, marker):
    """A model often ends with "Files delivered:", a list of the names and a
    sign-off, or opens with the list before the files. A name in a list is a
    mention: it neither replaces a file nor starts one."""
    _module, reference, _clean = reference_and_facts(workflow)
    listing = as_list(NAME_LINE.findall(reference), marker)
    for sign_off in SIGN_OFFS:
        scores_as_the_reference(workflow, f"{reference}\n\nFiles delivered:\n{listing}\n\n{sign_off}\n")
        scores_as_the_reference(workflow, f"{reference}\n\nFiles delivered:\n\n{listing}\n{sign_off}\n")
        scores_as_the_reference(workflow, f"I will deliver:\n{listing}\n\n{sign_off}\n\n{reference}")


@pytest.mark.parametrize("marker", MARKERS)
@pytest.mark.parametrize("workflow", FILE_TASKS)
def test_files_named_as_list_items_are_still_read(workflow, marker):
    """A list item followed by a code fence, or by a table row, starts a file."""
    _module, reference, _clean = reference_and_facts(workflow)
    names = NAME_LINE.findall(reference)
    listed = reference
    for name in names:
        listed = listed.replace(f"### {name}\n", as_list([name], marker) + "\n", 1)
    assert not NAME_LINE.search(listed)
    scores_as_the_reference(workflow, listed)
    spaced = re.sub(r"^((?:[-*+]|\d[.)]) [^\n]+)\n(```|~~~)", r"\1\n\n\2", listed, flags=re.MULTILINE)
    assert spaced != listed
    scores_as_the_reference(workflow, spaced)
    # Unfenced, the first line must read as a table row (a comma or a pipe), so a
    # one-column file keeps its fence: a lone word could as well be a sign-off.
    unfenced = re.sub(r"^((?:[-*+]|\d[.)]) [^\n]+\.csv)\n```[a-z]*\n([^\n]*[,|].*?)\n```$", r"\1\n\2", listed,
                      flags=re.MULTILINE | re.DOTALL)
    assert unfenced != listed
    scores_as_the_reference(workflow, unfenced)
    assert common.tables("- a.csv\nid\nC1\n", ["a.csv"]) == {"a.csv": None}
    assert common.tables("- a.csv\n```csv\nid\nC1\n```\n", ["a.csv"]) == {"a.csv": [{"id": "C1"}]}


def test_list_item_names_and_their_lookahead_are_fast():
    import time

    started = time.perf_counter()
    for text in (
        "- keywords.csv\n" * 100_000,
        "- keywords.csv\n\n" * 60_000 + "x,y\n",
        "1. keywords.csv\n" + "\n" * 200_000 + "a,b\n" * 10,
        "* asset-01.md\n" * 100_000 + "```\nx\n```\n",
        ("- keywords.csv\n" + " " * 150 + "\n") * 50_000,
        "+ " + "a" * 150_000 + ".csv\n```\n",
    ):
        common.tables(text, ["keywords.csv", "ads.csv"])
        common.sections(text, ["asset-01.md", "keywords.csv"])
    for workflow in FILE_TASKS:
        module, reference, _clean = reference_and_facts(workflow)
        names = NAME_LINE.findall(reference)
        module.facts(as_list(names, "- ") * 1 + "\n" + ("\n".join(f"- {names[0]}" for _ in range(50_000))) + "\n" + reference)
    assert time.perf_counter() - started < 5
