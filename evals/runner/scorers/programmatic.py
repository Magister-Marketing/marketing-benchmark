"""Small, explainable programmatic checks from task rubrics."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProgrammaticResult:
    id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_labeled_value(value: str) -> str:
    value = value.strip()
    value = re.sub(
        r"\s*\((?:\d+\s*/\s*\d+|\d+\s*(?:chars?|characters?))\)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    for opening, closing in (("“", "”"), ('"', '"'), ("'", "'")):
        if len(value) >= 2 and value.startswith(opening) and value.endswith(closing):
            return value[len(opening) : -len(closing)].strip()
    return value


def _label_values(text: str, label: str) -> list[str]:
    """Extract labeled copy while ignoring Markdown presentation annotations.

    Agents commonly write ``**Headline (23/40):**`` or
    ``**Headline** *(23/40)*:``. Character limits apply to the copy, not those
    annotations or surrounding quotation marks. When emphasized labels exist,
    prefer them over unformatted prose such as a later ``Headline: each option
    is within the limit`` checklist.
    """

    lines = text.splitlines()
    matches: list[tuple[str, bool]] = []
    pattern = re.compile(
        rf"^{re.escape(label)}(?:\s*\([^)]*\))?\s*:\s*(.*)$",
        re.IGNORECASE,
    )
    emphasized_label_pattern = re.compile(
        rf"^{re.escape(label)}(?:\s*\([^)]*\))?\s*$",
        re.IGNORECASE,
    )
    table_pattern = re.compile(
        rf"^\|\s*{re.escape(label)}(?:\s*\([^)]*\))?\s*\|\s*([^|]*?)\s*\|\s*$",
        re.IGNORECASE,
    )
    for index, raw_line in enumerate(lines):
        without_bullet = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?", "", raw_line)
        prefix = without_bullet.split(":", 1)[0]
        emphasized = "**" in prefix or "__" in prefix
        normalized = re.sub(r"[*_`]", "", without_bullet).strip()
        table_match = table_pattern.match(normalized)
        if table_match is not None:
            value = _clean_labeled_value(table_match.group(1))
            if value:
                # A table row is an explicitly structured field even when the
                # label is not bold; prefer it over prose checklists.
                matches.append((value, True))
            continue
        match = pattern.match(normalized)
        label_only = emphasized and emphasized_label_pattern.match(normalized)
        if match is None and label_only is None:
            continue
        value = match.group(1).strip() if match is not None else ""
        if not value:
            for following in lines[index + 1 :]:
                value = re.sub(r"[*_`]", "", following).strip()
                if not value:
                    continue
                if value.startswith("#") or re.match(
                    r"^[A-Za-z][^:]{0,48}:\s*", value
                ):
                    value = ""
                break
        value = _clean_labeled_value(value)
        if value:
            matches.append((value, emphasized))
    emphasized_values = [value for value, emphasized in matches if emphasized]
    return emphasized_values or [value for value, _ in matches]


def grade_programmatic(
    text: str,
    checks: list[dict[str, Any]],
) -> list[ProgrammaticResult]:
    results: list[ProgrammaticResult] = []
    for check in checks:
        check_id = str(check.get("id") or "unnamed")
        kind = check.get("kind")
        passed = False
        detail = f"unsupported check kind {kind!r}"
        if kind == "minimum_heading_matches":
            pattern = str(check.get("pattern") or "")
            headings = re.findall(r"(?im)^#{1,6}\s+(.+)$", text)
            count = sum(1 for heading in headings if pattern.casefold() in heading.casefold())
            minimum = int(check.get("minimum") or 0)
            passed = count >= minimum
            detail = f"heading matches={count}, required>={minimum}"
        elif kind == "labeled_character_limit":
            label = str(check.get("label") or "")
            maximum = int(check.get("maximum") or 0)
            values = _label_values(text, label)
            violations = [len(value) for value in values if len(value) > maximum]
            passed = bool(values) and not violations
            detail = (
                f"{len(values)} labeled value(s), max={maximum}, violations={violations}"
            )
        elif kind == "numbered_section_count":
            prefix = str(check.get("prefix") or "")
            count = len(
                re.findall(rf"(?im)^#{{1,6}}\s+{re.escape(prefix)}\s+\d+\b", text)
            )
            minimum = int(check.get("minimum") or 0)
            maximum = int(check.get("maximum") or 2**31 - 1)
            passed = minimum <= count <= maximum
            detail = f"sections={count}, required={minimum}..{maximum}"
        elif kind == "required_label_per_section":
            label = str(check.get("label") or "")
            prefix = str(check.get("prefix") or "Email")
            section_count = len(
                re.findall(rf"(?im)^#{{1,6}}\s+{re.escape(prefix)}\s+\d+\b", text)
            )
            value_count = len(_label_values(text, label))
            passed = section_count > 0 and value_count >= section_count
            detail = (
                f"{prefix} sections={section_count}, {label} labels={value_count}"
            )
        elif kind == "required_heading_level":
            level = int(check.get("level") or 1)
            expected_count = int(check.get("count") or 1)
            count = len(re.findall(rf"(?m)^{'#' * level}\s+[^#].+$", text))
            passed = count == expected_count
            detail = f"level-{level} headings={count}, expected={expected_count}"
        elif kind == "required_label":
            label = str(check.get("label") or "")
            count = len(_label_values(text, label))
            passed = count > 0
            detail = f"{label} labels={count}"
        elif kind == "required_phrase":
            phrase = str(check.get("phrase") or "")
            passed = phrase.casefold() in text.casefold()
            detail = f"required phrase {'present' if passed else 'missing'}: {phrase!r}"
        elif kind == "required_headings":
            values = [str(value) for value in check.get("values", [])]
            headings = [
                value.strip().casefold()
                for value in re.findall(r"(?im)^#{1,6}\s+(.+)$", text)
            ]
            missing = [
                value
                for value in values
                if not any(value.casefold() in heading for heading in headings)
            ]
            passed = not missing
            detail = f"missing headings={missing}"
        results.append(ProgrammaticResult(check_id, passed, detail))
    return results
