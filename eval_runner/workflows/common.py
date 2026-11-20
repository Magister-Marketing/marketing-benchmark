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


def _list_marker(core: str) -> int:
    """The length of the list marker a stripped line opens with ("- ", "* ",
    "+ ", "1. ", "12) "), or 0 when it is not a list item."""
    if core[:1] in ("-", "*", "+") and core[1:2] in (" ", "\t"):
        return 2
    head = core[:10]
    digits = len(head) - len(head.lstrip("0123456789"))
    if 1 <= digits <= 9 and core[digits:digits + 1] in (".", ")") and core[digits + 1:digits + 2] in (" ", "\t"):
        return digits + 2
    return 0


def _next_text(lines: list[str], index: int) -> str | None:
    """The first line with text after lines[index], or None."""
    for following in range(index + 1, len(lines)):
        if lines[following].strip():
            return lines[following]
    return None


def _table_row(line: str) -> bool:
    """Whether a line reads as a CSV or Markdown table row, not a sentence: it
    holds a comma or a pipe and does not end the way a sentence ends."""
    core = line.strip()
    return ("," in core or "|" in core) and core[-1:] not in (".", "!", "?")


def _starts_file(lines: list[str], index: int, tabular: bool) -> bool:
    """Whether the naming line at lines[index] starts a file. A heading, bold,
    backticks, "File: x" or the bare name always does. A list item ("- x.csv",
    "1. x.csv") does only when the next line with text opens a code fence or,
    for a table, is a table row: otherwise it is a name in a list (the files
    delivered, the files to come) and starts nothing."""
    if not _list_marker(lines[index].strip()):
        return True
    following = _next_text(lines, index)
    if following is None:
        return False
    return _is_fence(following) or (tabular and _table_row(following))


def file_named(line: str) -> str | None:
    """The file a line names, or None: "### keywords.csv", "**keywords.csv**",
    "- `keywords.csv`:", "1. keywords.csv", "File: keywords.csv"."""
    if len(line) > _MAX_MARKER_LINE:
        return None
    core = line.strip().lstrip("#").strip()
    core = core[_list_marker(core):]
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
    the next heading or the next file; blank lines between the name and the
    file are skipped. A file given twice is read where it was last given with
    something in it: a draft earlier in the reply does not shadow the final
    one, and a closing list of the file names does not empty them. A name
    given as a list item starts a file only when a code fence or a table row
    follows it (``_starts_file``); otherwise it is a mention, though like any
    naming line it still ends an unfenced file above it. A file only ever
    named with nothing under it is present but empty."""
    wanted = {name.lower() for name in names}
    lines = text.splitlines()
    found: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        name = file_named(lines[index])
        if name not in wanted or not _starts_file(lines, index, tabular=True):
            index += 1
            continue
        index += 1
        # Outside a fence, only lines with text are kept, so a non-empty body
        # has text: blank lines before the first one are skipped, not kept.
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
                if not line.strip():
                    index += 1
                    if body:
                        break
                    continue
            body.append(line)
            index += 1
        if name not in found or any(line.strip() for line in body):
            found[name] = body
    return {name: (_rows(found[name.lower()]) if name.lower() in found else None) for name in names}


def cell(row: dict[str, str], *names: str) -> str:
    """A row's value under the first of these column names it has."""
    for name in names:
        if name in row:
            return row[name]
    return ""


# ── Named documents ─────────────────────────────────────────────────────────
# Some workflow tasks ask for documents rather than tables: each a piece of
# copy under a line that names its file (``### asset-01.md``). A document's
# text is compared as written, so it is returned raw.

# A file of any kind a reply carries. Bounded, and only tried on a line of at
# most _MAX_MARKER_LINE characters.
_ANY_FILE_NAME = re.compile(
    r"[a-z0-9][a-z0-9_.-]{0,80}\.(?:md|markdown|txt|csv|json|html|yaml|yml)", re.IGNORECASE)


def named_file(line: str) -> str | None:
    """The file a line names, of any kind a reply carries, or None:
    "### asset-01.md", "**asset-01.md**", "- `asset-01.md`:", "2. asset-02.md",
    "File: notes.txt"."""
    if len(line) > _MAX_MARKER_LINE:
        return None
    core = line.strip().lstrip("#").strip()
    core = core[_list_marker(core):]
    core = core.strip("*_` \t")
    if core[:4].lower() == "file" and core[4:].lstrip()[:1] in (":", "="):
        core = core[4:].lstrip()[1:]
    core = core.strip("*_` \t:")
    return core.lower() if _ANY_FILE_NAME.fullmatch(core) else None


def _fence_mark(line: str) -> str:
    """The run of backticks or tildes a fence line opens with, or ""."""
    core = line.lstrip()
    if not core.startswith(_FENCES):
        return ""
    return core[:len(core) - len(core.lstrip(core[0]))]


def _closes(line: str, mark: str) -> bool:
    """Whether a line closes the fence ``mark`` opened: nothing but the mark's
    character, at least as many times."""
    core = line.strip()
    return len(core) >= len(mark) and not core.strip(mark[0])


def _document(lines: list[str]) -> str:
    """A document's text from the lines under its name. When the lines hold a
    code fence, the text is what is inside the first one, up to the fence line
    that closes it: a note before or after is not the document. A lone fence
    line after the text closes something the reply opened earlier, and the
    text is what comes before it."""
    first_text = next((index for index, line in enumerate(lines) if line.strip()), None)
    opening = next((index for index, line in enumerate(lines) if _fence_mark(line)), None)
    body = lines
    if opening is not None:
        mark = _fence_mark(lines[opening])
        closing = next((index for index in range(opening + 1, len(lines)) if _closes(lines[index], mark)), None)
        if closing is not None:
            body = lines[opening + 1:closing]
        elif opening == first_text:
            body = lines[opening + 1:]
        else:
            body = lines[:opening]
    start, end = 0, len(body)
    while start < end and not body[start].strip():
        start += 1
    while end > start and not body[end - 1].strip():
        end -= 1
    return "\n".join(body[start:end])


def sections(text: str, names: list[str]) -> dict[str, str | None]:
    """The named documents of a reply, each as the raw text under the line
    that names it, or None for a file the reply does not carry. A document is
    the lines after its name up to the next line that names any file, read
    through ``_document`` (inside its code fence when it has one). A file
    given twice is read where it was last given with text: a draft earlier in
    the reply does not shadow the final one, and a closing list of the file
    names does not empty them. A name given as a list item starts a document
    only when a code fence follows it (``_starts_file``); otherwise it is a
    mention, which still ends the document above it as any naming line does.
    A file only ever named with no text under it is present but empty ("").
    Nothing is matched against more than a bounded line, and each blank run is
    looked past once, so no reply can stall it."""
    wanted = {name.lower() for name in names}
    found: dict[str, str] = {}

    def keep(name: str | None, lines: list[str]) -> None:
        if name is None:
            return
        document = _document(lines)
        if name not in found or document:
            found[name] = document

    current_name: str | None = None
    current: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        name = named_file(line)
        if name is not None:
            keep(current_name, current)
            starts = name in wanted and _starts_file(lines, index, tabular=False)
            current_name, current = (name if starts else None), []
            continue
        if current_name is not None:
            current.append(line)
    keep(current_name, current)
    return {name: found.get(name.lower()) for name in names}
