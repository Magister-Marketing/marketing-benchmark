"""Workflow tasks: which headline won?

Every other task grades work against a brief. These two grade a judgment
against what happened. Each holds 100 pairs of headlines from real tests on
Upworthy's site (the same story, image and excerpt, a different headline,
visitors assigned at random), where the two headlines' click rates differed
at p < 0.001. The candidate picks the one that got the higher click rate and
says how sure it is. A program counts the picks that match the record and
scores the stated confidence; no judge decides who is right.

Two sets, never pooled:

- ``headline-forecast``: the best and the worst headline of a test.
- ``headline-forecast-unpublished``: the same, among headlines that were
  neither the test's top performer nor flagged as its winner. Upworthy did
  not go on to publish these, so a model cannot score by recognising a
  headline that spread on the web.

The pairs and their outcomes come from the Upworthy Research Archive (Matias,
Munger, Le Quere and Ebersole, 2021; CC BY 4.0). See
eval_runner/fixtures/headline-forecast/NOTICE.md for the source, the licence
and how the pairs were chosen.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path("eval_runner") / "fixtures" / "headline-forecast"
SETS = {
    "headline-forecast": "clear",
    "headline-forecast-unpublished": "unpublished",
}
# Both bars are one reference forecaster: right nine times in ten on pairs
# with a wide gap, and saying 90. Credit runs in a straight line from what a
# coin flip with no opinion earns (nothing) up to that forecaster.
# On 2026-11-20 a first bar of 70% was met by GPT-6.2 Sol, Claude Opus 5.5
# and Gemini 4 Neon alike on both sets (28 to 35 right of 40), so it told
# them apart no better than the tasks it was written to add to.
PASS_SHARE = 0.90
CHANCE_SHARE = 0.50
# Brier scores times 1,000: saying "50" to everything, and the reference
# forecaster's (0.9 x 0.1^2 + 0.1 x 0.9^2).
BRIER_OF_NO_OPINION = 250
BRIER_TO_PASS = round(1000 * PASS_SHARE * (1 - PASS_SHARE))

_MAX_LINE = 200
# "P007: A 65", "**P7** - B (80%)", "P007. A, 0.7". One bounded pattern on a
# line already cut to _MAX_LINE characters.
_ANSWER = re.compile(
    r"^[\s>*_`#-]{0,12}P(\d{1,3})[\s*_`]{0,6}[:.\-)][\s*_`]{0,6}([AB])(?![A-Za-z])"
    r"(?:[^0-9\n]{0,24}?(\d{1,3}(?:\.\d{1,4})?))?",
    re.IGNORECASE,
)


@lru_cache(maxsize=None)
def pairs(workflow: str) -> tuple[dict, ...]:
    path = REPO_ROOT / FIXTURE_DIR / f"pairs_{SETS[workflow]}.jsonl"
    return tuple(json.loads(line) for line in path.read_text().splitlines() if line.strip())


def candidate_file(workflow: str) -> str:
    """The pairs as the candidate reads them: an id and two headlines, nothing about the outcome."""
    lines = ["# Headline pairs", ""]
    for pair in pairs(workflow):
        lines += [f"## {pair['id']}", "", f"A: {pair['a']}", f"B: {pair['b']}", ""]
    return "\n".join(lines)


def fixtures() -> dict[str, str]:
    return {f"headline_pairs_{name}.md": candidate_file(workflow) for workflow, name in SETS.items()}


def bars(workflow: str) -> dict[str, int]:
    """The numbers the task file pins: how many picks pass and how many are a coin flip."""
    total = len(pairs(workflow))
    return {"pairs": total, "to_pass": round(total * PASS_SHARE), "chance": round(total * CHANCE_SHARE)}


def reference_answer(workflow: str) -> str:
    """Every pick right, at a confidence the record supports: what a checker must pass."""
    return "\n".join(f"{pair['id']}: {pair['answer']} 90" for pair in pairs(workflow)) + "\n"


def picks(response_text: str) -> dict[int, tuple[str, float]]:
    """{pair number: (side, confidence 50-100)} from a reply's answer lines.
    The last line for a pair is its answer: a draft earlier in the reply does
    not count. A confidence below 50, above 100 or missing reads as 50: no
    opinion beyond the pick."""
    found: dict[int, tuple[str, float]] = {}
    for line in response_text.splitlines():
        match = _ANSWER.match(line[:_MAX_LINE])
        if not match:
            continue
        confidence = 50.0
        if match.group(3) is not None:
            value = float(match.group(3))
            if 0 < value <= 1:
                value *= 100
            if 50 <= value <= 100:
                confidence = value
        found[int(match.group(1))] = (match.group(2).upper(), confidence)
    return found


def facts(response_text: str, workflow: str = "headline-forecast") -> dict:
    """Counts of the reply's picks against what happened. A pair with no pick
    is a wrong pick held with full confidence, so leaving pairs out never
    beats answering them."""
    answered = correct = 0
    squared = 0.0
    given = picks(response_text)
    for pair in pairs(workflow):
        pick = given.get(int(pair["id"][1:]))
        if pick is None:
            squared += 1.0
            continue
        answered += 1
        side, confidence = pick
        right = side == pair["answer"]
        correct += right
        on_the_winner = confidence / 100 if right else 1 - confidence / 100
        squared += (1 - on_the_winner) ** 2
    total = len(pairs(workflow))
    return {
        "workflow_forecast_answered_count": answered,
        "workflow_forecast_correct_count": correct,
        "workflow_forecast_brier_x1000": round(1000 * squared / total),
    }
