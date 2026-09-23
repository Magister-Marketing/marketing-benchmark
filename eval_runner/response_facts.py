"""Conservative, non-executing checks of worked examples in candidate text.

These are evidence for the judge, never automatic rubric verdicts: a response
can quote a wrong example to reject it. Unrecognized formats imply no coverage.
"""
import hashlib
import json
import re


def _cell(text):
    text = text.strip()
    if text.startswith("**") and text.endswith("**"):
        text = text[2:-2].strip()
    if text.startswith("`") and text.endswith("`"):
        # Preserve code-span contents exactly, including literal Markdown and
        # spaces. Unsupported multi-backtick spans are skipped by _literal.
        return text[1:-1]
    return text


def _literal(text):
    value = text
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except ValueError:
            return None
        return decoded if isinstance(decoded, str) and not re.fullmatch(r"\s*<[^>]+>\s*", decoded) else None
    # Quotes and placeholders are ambiguous; do not guess their intended bytes.
    if any(c in value for c in "<>`\\{}[]\"'") or not value:
        return None
    return value


def sha256_examples(response):
    """Check simple Markdown tables with explicit bytes or normalized emails.

    Support explicitly UTF-8 normalized-value/SHA-256 columns, or raw email examples in a
    SHA-256 table that explicitly documents trim/lowercase normalization. Never
    execute candidate code or infer normalization for other raw PII fields.
    """
    checks = []
    headers = None
    for line_number, line in enumerate(response.splitlines(), 1):
        if not line.strip().startswith("|") or r"\|" in line:
            headers = None
            continue
        cells = [_cell(c) for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        names = [c.lower() for c in cells]
        if any(name in names for name in ("normalized value", "normalized utf-8 value", "raw example")):
            headers = names if len(names) == len(set(names)) else None
            continue
        if not headers or len(headers) != len(cells):
            continue
        row = dict(zip(headers, cells))
        claimed = row.get("sha-256", row.get("sha256", row.get("processed value", "")))
        # A too-short/long hex digest is still a checkable claim, not a placeholder.
        if not re.fullmatch(r"[0-9a-fA-F]{32,128}", claimed):
            continue
        value = None
        basis = None
        utf8_value = row.get("normalized utf-8 value")
        if utf8_value is None and row.get("encoding", "").lower() in {"utf-8", "utf8"}:
            utf8_value = row.get("normalized value")
        if utf8_value is not None and ("sha-256" in row or "sha256" in row):
            value = _literal(utf8_value)
            basis = "explicit normalized UTF-8 value"
        elif (row.get("parameter", "").lower() == "email"
              and row.get("capi key") == "em"
              and "sha-256" in row.get("hashing algorithm", "").lower()
              and "trim" in row.get("normalization standard", "").lower()
              and "lowercase" in row.get("normalization standard", "").lower()):
            raw = _literal(row.get("raw example", ""))
            if raw and re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", raw.strip()):
                value = raw.strip().lower()
                basis = "email trimmed and lowercased as documented in the table"
        if value is None:
            continue
        try:
            actual = hashlib.sha256(value.encode("utf-8")).hexdigest()
        except UnicodeError:
            continue
        checks.append({"line": line_number, "basis": basis, "normalized_value": value,
                       "claimed_sha256": claimed, "computed_sha256": actual,
                       "matches": claimed.lower() == actual})
    return checks
