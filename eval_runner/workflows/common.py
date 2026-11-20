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
import io
import re
from decimal import Decimal, InvalidOperation

# A line that names a file: "### keywords.csv", "**keywords.csv**",
# "File: `keywords.csv`", "keywords.csv:".
_FILE_LINE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[-*]\s+)?[*_`]*\s*(?:file\s*[:=]\s*)?[*_`]*\s*"
    r"([a-z0-9][a-z0-9_.-]*\.csv)\s*[*_`]*\s*:?\s*[*_`]*\s*$",
    re.IGNORECASE,
)
_HEADING = re.compile(r"^\s*#{1,6}\s+\S")
_FENCE = re.compile(r"^\s*(```|~~~)")
_PIPE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


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


def _split(lines: list[str]) -> list[list[str]]:
    kept = [line for line in lines if line.strip()]
    if kept and sum(line.strip().startswith("|") for line in kept) >= max(1, len(kept) - 1):
        # A Markdown table in place of the CSV that was asked for: read it anyway.
        return [
            [cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in kept if not _PIPE_RULE.match(line)
        ]
    return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO("\n".join(kept)))]


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
        match = _FILE_LINE.match(lines[index])
        if not match or match.group(1).lower() not in wanted:
            index += 1
            continue
        name = match.group(1).lower()
        index += 1
        body: list[str] = []
        fenced = False
        while index < len(lines):
            line = lines[index]
            if _FENCE.match(line):
                index += 1
                if fenced or body:
                    break
                fenced = True
                continue
            if not fenced:
                if _FILE_LINE.match(line) or _HEADING.match(line):
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
