"""What every workflow task's checker shares: reading the tables an answer
carries, and comparing keywords the way a search platform does.

A workflow task asks for several deliverables in one reply, each a small CSV
table under a line that names its file (``### keywords.csv``). Nothing here
judges the work: these functions only turn the reply into rows, tolerantly,
so a checker can count what is right and wrong in them. Facts a checker
returns are counts and flags only; no text the candidate wrote may reach the
block the judge is told to trust.
"""
from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation

# A reply is a model's output: untrusted, and as long and as odd as the model
# made it. Lines are recognised by stripping and comparing, with one
# single-class pattern for the name, so no line can make a pattern backtrack.
_FILE_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*\.csv", re.IGNORECASE)
_MAX_MARKER_LINE = 200
_FENCES = ("```", "~~~")


def file_named(line: str) -> str | None:
    """The file a line names, or None: "### keywords.csv", "**keywords.csv**",
    "- `keywords.csv`:", "File: keywords.csv"."""
    if len(line) > _MAX_MARKER_LINE:
        return None
    core = line.strip().lstrip("#").strip()
    if core[:2] in ("- ", "* "):
        core = core[2:]
    core = core.strip("*_` \t")
    if core[:4].lower() == "file" and core[4:].lstrip()[:1] in (":", "="):
        core = core[4:].lstrip()[1:]
    core = core.strip("*_` \t:")
    return core.lower() if _FILE_NAME.fullmatch(core) else None


def _is_heading(line: str) -> bool:
    core = line.lstrip()
    marks = len(core) - len(core.lstrip("#"))
    return 1 <= marks <= 6 and core[marks:marks + 1] in (" ", "\t") and bool(core[marks:].strip())


def _is_fence(line: str) -> bool:
    return line.lstrip().startswith(_FENCES)


def _is_table_rule(line: str) -> bool:
    """The line under a Markdown table's header: only pipes, colons, dashes."""
    core = line.strip()
    return "--" in core and not core.strip("|:- \t")


def norm(text: object) -> str:
    """Lower case, one space between words, no surrounding quotes or space."""
    return re.sub(r"\s+", " ", str(text or "").strip().strip("\"'`").strip()).lower()


def words(text: object) -> list[str]:
    """The words of a keyword or a term, as a search platform splits them."""
    return re.findall(r"[a-z0-9$#%']+", norm(text).replace("-", " "))


def has_phrase(keyword_words: list[str], term_words: list[str]) -> bool:
    """Whether the term's words appear in the keyword, whole and in order,
    next to each other: "mat" is in "desk mat" and not in "matte desk"."""
    n = len(term_words)
    return n > 0 and any(keyword_words[i:i + n] == term_words for i in range(len(keyword_words) - n + 1))


def money(text: object) -> Decimal | None:
    """The amount in a cell such as "$1,204.50", "1204.5" or "USD 1,204.50"."""
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(text or ""))
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


# No cell of a deliverable needs more than this; a longer line is cut, so a
# runaway line cannot trip the csv module's field limit or fill a row.
_MAX_ROW_CHARS = 4000


def _csv_row(line: str) -> list[str]:
    """One line as CSV, on its own: a stray quote spoils that row and cannot
    swallow the rows after it."""
    try:
        return next(csv.reader([line]), [])
    except csv.Error:
        return [line]


def _split(lines: list[str]) -> list[list[str]]:
    kept = [line[:_MAX_ROW_CHARS] for line in lines if line.strip()]
    if kept and sum(line.strip().startswith("|") for line in kept) >= max(1, len(kept) - 1):
        # A Markdown table in place of the CSV that was asked for: read it anyway.
        return [
            [cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in kept if not _is_table_rule(line)
        ]
    return [[cell.strip() for cell in _csv_row(line)] for line in kept]


def _rows(lines: list[str]) -> list[dict[str, str]]:
    table = [row for row in _split(lines) if any(cell for cell in row)]
    if not table:
        return []
    header = [re.sub(r"[^a-z0-9]+", "_", norm(cell)).strip("_") for cell in table[0]]
    return [
        {name: (row[index] if index < len(row) else "") for index, name in enumerate(header) if name}
        for row in table[1:]
    ]


def tables(text: str, names: list[str]) -> dict[str, list[dict[str, str]] | None]:
    """The named CSV files of a reply, each as a list of rows keyed by its own
    header (lower case, underscores). None for a file the reply does not
    carry. A file is the lines under the line that names it, inside a code
    fence when there is one, else up to the first blank line after its rows,
    the next heading or the next file. A file given twice is read where it
    was given last: a draft earlier in the reply does not shadow the final
    one."""
    wanted = {name.lower() for name in names}
    lines = text.splitlines()
    found: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        name = file_named(lines[index])
        if name not in wanted:
            index += 1
            continue
        index += 1
        body: list[str] = []
        fenced = False
        while index < len(lines):
            line = lines[index]
            if _is_fence(line):
                index += 1
                if fenced or body:
                    break
                fenced = True
                continue
            if not fenced:
                if file_named(line) or _is_heading(line):
                    break
                if not line.strip() and body:
                    break
            body.append(line)
            index += 1
        found[name] = body
    return {name: (_rows(found[name.lower()]) if name.lower() in found else None) for name in names}


def cell(row: dict[str, str], *names: str) -> str:
    """A row's value under the first of these column names it has."""
    for name in names:
        if name in row:
            return row[name]
    return ""
