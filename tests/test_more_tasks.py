"""The six data tasks added in November 2026: fixtures, oracles, traps and parsing.

What is pinned here, for every task:

- the committed fixtures and every value a program decides in a task file are
  exactly what `scripts/gen_more_tasks.py` produces and pins, and the bands
  and oracle lists it pins are the ones written out in this file, so neither
  can change by one edit alone;
- every banded target, and every figure the judge's reference carries, equals
  a figure recomputed in this file from the committed fixture, by code that
  shares nothing with `task_references`;
- a careful answer passes every programmatic criterion, and the careless
  answer the task is built to catch scores zero on the criterion meant to
  catch it without failing the critical one;
- an answer block is read as the prompt asks for it to be written.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import re
import statistics
from decimal import Decimal

import pytest

from eval_runner import bench, reference_facts, task_references

NEW_TASKS = {
    "seo-technical-triage": "development",
    "search-terms-negatives": "development",
    "ab-test-readout": "development",
    # Drafted as holdout tasks. Their recorded answers were read, and one rubric was changed
    # because of them, so by the repository's rule they are development tasks.
    "seo-content-brief": "development",
    "lifecycle-reengagement": "development",
    "monthly-report-reconcile": "development",
}
# The holdout split is the four tasks it held before these six were added.
HOLDOUT = {"launch-capacity-trap", "platform-limits-gauntlet", "rate-card-reconciliation", "unsupportable-claims-brief"}
# (prompt version, rubric version). Version 1 was a local draft, run once and
# discarded. A version moves when its prompt or fixtures, or its rubric, do.
VERSIONS = {
    "seo-technical-triage": (3, 3),
    "search-terms-negatives": (3, 4),
    "ab-test-readout": (3, 4),
    "seo-content-brief": (3, 4),
    "lifecycle-reengagement": (2, 2),
    "monthly-report-reconcile": (2, 3),
}
# The second key. The generator pins these into the task files; a change to a
# band or an oracle list has to be made there and here.
BANDS = {
    "seo-content-brief": {
        "q1_already_ranking": ("absolute", 0, 3), "q2_qualifying_count": ("absolute", 0, 3),
        "q3_topic_volume": ("relative", 0.005, 0.25), "q4_primary_volume": ("relative", 0.005, 0.25),
        "q5_ranking_volume": ("relative", 0.005, 0.25),
    },
    "seo-technical-triage": {
        "q1_broken_linked": ("absolute", 0, 3), "q2_redirect_chains": ("absolute", 0, 3),
        "q3_noindex_in_sitemap": ("absolute", 0, 3), "q4_bad_canonicals": ("absolute", 0, 3),
        "q5_duplicate_title_groups": ("absolute", 0, 3), "q6_sessions_at_risk": ("relative", 0.005, 0.25),
    },
    "search-terms-negatives": {
        "q1_zero_conversion_spend": ("relative", 0.005, 0.25), "q2_promote_count": ("absolute", 0, 3),
        "q3_irrelevant_spend": ("absolute", 0.5, 400), "q4_promote_conversions": ("absolute", 0, 8),
    },
    "lifecycle-reengagement": {
        "q1_mailable": ("absolute", 0, 20), "q2_lapsed": ("absolute", 0, 10),
        "q3_lapsed_buyers": ("absolute", 0, 6), "q4_lapsed_non_buyers": ("absolute", 0, 6),
        "q5_long_dormant": ("absolute", 0, 5),
    },
    "ab-test-readout": {
        "q1_control_visitors": ("relative", 0.001, 0.1), "q2_variant_visitors": ("relative", 0.001, 0.1),
        "q3_control_rate": ("absolute", 0.02, 0.5), "q4_variant_rate": ("absolute", 0.02, 0.5),
        "q5_relative_lift": ("absolute", 0.15, 3.0), "q6_srm_chi_square": ("relative", 0.02, 0.3),
        "q7_p_value": ("absolute", 0.015, 0.1),
    },
    "monthly-report-reconcile": {
        "q1_ad_spend": ("relative", 0.005, 0.1), "q2_real_orders": ("absolute", 0, 8),
        "q3_net_revenue": ("relative", 0.005, 0.03), "q4_duplicate_rows": ("absolute", 0, 8),
        "q5_blended_roas": ("relative", 0.01, 0.04), "q6_platform_conversions": ("absolute", 0, 50),
    },
}
ORACLE = {
    "seo-content-brief": ["q5_ranking_volume"],
    "seo-technical-triage": ["q6_sessions_at_risk"],
    "search-terms-negatives": ["q1_zero_conversion_spend"],
    "lifecycle-reengagement": ["q1_mailable"],
    "ab-test-readout": ["q1_control_visitors", "q2_variant_visitors"],
    "monthly-report-reconcile": ["q1_ad_spend", "q6_platform_conversions"],
}
FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location(
        "gen_more_tasks", bench.REPO_ROOT / "scripts" / "gen_more_tasks.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((FIXTURES / name).read_text())))


def _by_id(task: dict) -> dict[str, dict]:
    return {c["id"]: c for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section]}


def _targets(task: dict) -> dict[str, float]:
    return {
        criterion_id: criterion["programmatic"]["near"]
        for criterion_id, criterion in _by_id(task).items()
        if isinstance(criterion.get("programmatic"), dict)
        and criterion["programmatic"].get("fact", "").startswith("answer_q")
    }


def _reference(task_id: str) -> dict:
    task = bench.load_tasks()[task_id]
    return bench.judge_source_reference(task, bench.assemble_prompt(task, False))


def _results(task_id: str, response: str) -> dict:
    task = bench.load_tasks()[task_id]
    return bench.programmatic_results(task, bench.measured_facts(task, response))


def _answer_block(values: list) -> str:
    return "Report text.\n\n" + "\n".join(f"A{index}: {value}" for index, value in enumerate(values, 1)) + "\n"


def _failed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if not result["pass"]}


def _zeroed(results: dict) -> set[str]:
    return {criterion_id for criterion_id, result in results.items() if result["score"] == 0}


def _critical_tripped(task_id: str, response: str) -> bool:
    """Whether the oracle alone fails the task's critical criterion."""
    task = bench.load_tasks()[task_id]
    critical = next(iter(bench.critical_criterion_ids(task)))
    programmatic = list(bench.programmatic_results(task, bench.measured_facts(task, response)).values())
    judged = [{"id": critical, "pass": True, "score": 1.0, "evidence": "the judge saw nothing wrong"}]
    after = bench.apply_oracle_overrides(programmatic + judged, bench.oracle_rules(task))
    return bool(next(item for item in after if item["id"] == critical).get("oracle_failed"))


def _money(value) -> float:
    return float(Decimal(value).quantize(Decimal("0.01")))


# ------------------------------------------------------------------ the set as a whole

def test_six_tasks_load_with_their_splits_versions_and_one_oracle_backed_critical():
    tasks = bench.load_tasks()
    assert {task_id: tasks[task_id]["split"] for task_id in NEW_TASKS} == NEW_TASKS
    assert set(NEW_TASKS.values()) == {"development"}
    assert {task_id for task_id, task in tasks.items() if task["split"] == "holdout"} == HOLDOUT
    assert set(task_references.REFERENCES) == set(NEW_TASKS)
    # The two tasks whose checks read free text by pattern are parked, not here.
    assert not {"social-calendar-limits", "positioning-from-competitors"} & set(tasks)
    for task_id in NEW_TASKS:
        task = tasks[task_id]
        assert (task["prompt_version"], task["rubric_version"]) == VERSIONS[task_id], task_id
        critical = bench.critical_criterion_ids(task)
        assert critical == {"no_invented_data"} and critical <= bench.negative_criterion_ids(task), task_id
        assert bench.task_supports_harness(task, bench.HARNESS_ID)
        assert all((bench.REPO_ROOT / path).is_file() for path in task["fixtures"])
        assert bench.free_credit_scores(task) == {}, task_id  # nothing is already true of an empty reply
        assert task["answers"] == {"count": len(BANDS[task_id]), "single_number": True}


def test_committed_fixtures_and_task_files_are_what_the_generator_pins(generator):
    assert generator.check() == []


def test_bands_and_oracle_lists_are_the_ones_written_here(generator):
    """Synced from the generator, a changed band would carry the task file and
    its wording with it and look consistent. It still has to match this file."""
    assert generator.BANDS == BANDS
    assert generator.ORACLE == {task_id: {"no_invented_data": listed} for task_id, listed in ORACLE.items()}
    tasks = bench.load_tasks()
    for task_id in NEW_TASKS:
        criteria = _by_id(tasks[task_id])
        assert bench.oracle_rules(tasks[task_id]) == {"no_invented_data": ORACLE[task_id]}, task_id
        for criterion_id, (kind, full, zero) in BANDS[task_id].items():
            condition = criteria[criterion_id]["programmatic"]
            assert condition["tolerance"] == {"kind": kind, "full": full, "zero": zero}, (task_id, criterion_id)
            # The wording describes the band that is applied.
            if kind == "relative":
                wording = f"full credit within {full * 100:g}%, zero credit beyond {zero * 100:g}% off"
            elif full == 0:
                wording = f"full credit for the exact figure, zero credit {zero:g} or more off"
            else:
                wording = f"full credit within {full:g}, zero credit {zero:g} or more off"
            assert criteria[criterion_id]["check"].endswith("; " + wording + "."), (task_id, criterion_id)
        # An oracle-listed answer is a plain aggregate with a zero band of at
        # least a tenth of its value: only a figure no reading of the data
        # supports scores the whole attempt zero.
        for listed in ORACLE[task_id]:
            kind, _full, zero = BANDS[task_id][listed]
            relative = zero if kind == "relative" else zero / criteria[listed]["programmatic"]["near"]
            assert relative >= 0.0999, (task_id, listed)


def test_check_reports_drift_in_numbers_wording_and_flags_and_survives_reformatting(generator, tmp_path):
    """A hand edit to a number, a definition or a pinned sentence is drift;
    reformatting is not; and `--sync` puts back everything it pins."""
    for path in bench.TASKS_DIR.glob("*.json"):
        (tmp_path / path.name).write_text(path.read_text())
    assert generator.check(tmp_path) == []

    def drift(task_id: str, old: str, new: str) -> list[str]:
        target = tmp_path / f"{task_id}.json"
        original = target.read_text()
        assert original.count(old) == 1, old
        target.write_text(original.replace(old, new))
        problems = generator.check(tmp_path)
        changed, after_sync = generator.sync_tasks(tmp_path)
        restored = target.read_text() == original
        target.write_text(original)
        return problems, restored

    for task_id, old, new, restorable in (
        ("monthly-report-reconcile", '"zero": 0.03', '"zero": 0.06', True),                    # a tolerance
        ("ab-test-readout", '"near": 0.209', '"near": 0.219', True),                           # a target
        ("seo-content-brief", '"fails_if_zero": ["q5_ranking_volume"]', '"fails_if_zero": ["q3_topic_volume"]', True),
        ("lifecycle-reengagement", '"single_number": true', '"single_number": false', True),
        ("ab-test-readout", "variant B has 5,400 visitors against control's 6,900", "variant B has 5,400 visitors against control's 6,800", True),
        ("search-terms-negatives", "('sablewood', 'sablewood blinds' and 'sablewood blinds reviews')", "('sablewood' and 'sablewood blinds')", True),
        ("seo-technical-triage", "duplicate titles, bad canonicals, broken linked pages", "bad canonicals, duplicate titles, broken linked pages", True),
        ("lifecycle-reengagement", "valid for 14 days, offered", "valid for 10 days, offered", True),
        ("search-terms-negatives", "All 5 promote candidates", "All 4 promote candidates", True),
        ("search-terms-negatives", '"kind": "absolute", "full": 0.5, "zero": 400', '"kind": "relative", "full": 0.02, "zero": 0.25', True),
        ("ab-test-readout", "(11,750), is derived from the results", "(18,000), is derived from the results", True),
        ("seo-content-brief", "zero credit beyond 25% off.\", \"programmatic\": {\"fact\": \"answer_q3\"", "zero credit beyond 50% off.\", \"programmatic\": {\"fact\": \"answer_q3\"", True),
        # What sync cannot rewrite stays reported: a definition, a dropped flag.
        ("seo-content-brief", "a difficulty of 45 or lower", "a difficulty of 50 or lower", False),
        ("monthly-report-reconcile", "minus `refund_usd`", "before refunds", False),
        ("seo-technical-triage", '{"id": "no_invented_data", "negative": true, "critical": true,', '{"id": "no_invented_data", "critical": true,', False),
        ("search-terms-negatives", '{"id": "no_invented_data", "negative": true, "critical": true,', '{"id": "no_invented_data", "negative": true,', False),
    ):
        problems, restored = drift(task_id, old, new)
        assert problems and all(problem.startswith(task_id) for problem in problems), (task_id, old)
        assert restored is restorable, (task_id, old)

    target = tmp_path / "monthly-report-reconcile.json"
    original = target.read_text()
    target.write_text(json.dumps(json.loads(original), indent=4, ensure_ascii=False))
    assert generator.check(tmp_path) == []                       # reformatted, same content
    assert generator.sync_tasks(tmp_path) == (["monthly-report-reconcile"], [])
    assert target.read_text() == original                        # back in the repository's layout
    target.write_text("{not json")
    assert any("not valid JSON" in problem for problem in generator.check(tmp_path))
    target.unlink()
    assert any("missing task file" in problem for problem in generator.check(tmp_path))


# ------------------------------------------------------- answer lines: the number alone

AB_BLOCK = "A1: 12,480\nA2: 11,020\nA3: 6.00%\nA4: 6.40%\nA5: 6.6%\nA6: 90.7\nA7: 0.209"
AB_ANSWERS = [12480.0, 11020.0, 6.0, 6.4, 6.6, 90.7, 0.209]


def _ab(response: str) -> list:
    facts = bench.measured_facts(bench.load_tasks()["ab-test-readout"], response)
    return [facts[f"answer_q{index}"] for index in range(1, 8)]


def _one(value: str):
    """How a single-number task reads the line `A1: <value>`."""
    return bench.measured_facts({"id": "x", "answers": {"count": 7, "single_number": True}}, "A1: " + value)["answer_q1"]


def test_an_answer_line_is_read_only_when_it_carries_exactly_one_number():
    assert _ab("Readout.\n\n" + AB_BLOCK) == AB_ANSWERS
    for value, expected in {
        "12,480": 12480.0, "12480": 12480.0, "12,480.00": 12480.0, "$35,901.46": 35901.46, "6.00%": 6.0,
        "6.00 percent": 6.0, "~6.40": 6.4, "≈ 0.209": 0.209, ".209": 0.209, "+6.6 %": 6.6, "3.14x": 3.14,
        "7 URLs": 7.0, "12,480 visitors": 12480.0, "Control signup rate = 6.00%": 6.0, "χ² = 90.7": 90.7,
        "**12,480**": 12480.0, "`12,480`": 12480.0, "12,480.": 12480.0, "12,480,": 12480.0, "USD 11,435.94": 11435.94,
        # A minus sign, however it is typed: a hyphen, U+2212, the non-breaking and full-width
        # hyphens, and an en dash that opens the value.
        "-6.6": -6.6, "−6.6%": -6.6, "–6.6%": -6.6, "‑6.6%": -6.6, "－6.6": -6.6, "(–6.6%)": -6.6, "~−0.4": -0.4,
        "-$1,234.50": -1234.5, "$-1,234.50": -1234.5, "−$1,234.50": -1234.5, "–$1,234.50": -1234.5,
        "Lift: −6.6%": -6.6, "Lift -6.6%": -6.6,
        # After a word, or with a space before the number, a dash is punctuation.
        "Lift –6.6%": 6.6, "Lift – 6.6%": 6.6, "— 6.6%": 6.6, "- 6.6": 6.6, "—6.6%": 6.6,
    }.items():
        assert _one(value) == expected, value
    for value in (
        "749 / 12,480 = 6.00%", "chi2 = 90.7", "0.209 (z = 1.26)", "282 of 300 rows", "7 or 8", "7-8", "7–8",
        "3.14:1", "35,901.46 [1]", "2.09e-1", "1e4",                     # a second number on the line
        "seven", "n/a", "", "-", ".",                                    # no number
        "$11.4k", "11.4 k", "11.4 million", "11.4M",                     # rounded
        "3,14", "12,48", "1,2480", "12 480",                             # not thousands separators
        "[12,480]", "<12,480>", "[blocked -- final-28-day spend unavailable]",  # the placeholder idiom
    ):
        assert _one(value) is None, value


def test_the_answer_block_is_the_last_full_run_of_answer_lines():
    """A labelled line in a note cannot override the block, and a blank answer stays blank."""
    # The reviewer's case: a correct block, then a note that restates a label.
    for note in ("\n\nA1: sum of 8 rows", "\n\nNotes:\nA1: sum of 8 rows\nA6: 1 degree of freedom",
                 "\nA1: sum of 8 rows", "\n\n- A1: 8 weekly rows per variant",
                 "\nA7: one-sided it would be 0.104"):  # the last label again, straight after the block
        assert _ab("Readout.\n\n" + AB_BLOCK + note) == AB_ANSWERS, note
        assert not _critical_tripped("ab-test-readout", "Readout.\n\n" + AB_BLOCK + note), note
    # A labelled line before the block does not shadow it either.
    assert _ab("A1: the two totals are 8 rows each.\n\nReadout.\n\n" + AB_BLOCK) == AB_ANSWERS
    # Method notes that repeat every label, as recorded responses write them, lose to a
    # block written as the prompt asks, wherever the notes stand. These carry working.
    notes = "\n".join([
        "- **A1:** sum of 8 weekly rows.", "- **A2:** 5,620 + 5,400 = **11,020**", "- **A3:** 749 ÷ 12,480 = 6.00%",
        "- **A4:** 705 ÷ 11,020 = 6.40%", "- **A5:** 6.40 ÷ 6.00 − 1", "- **A6:** 1 degree of freedom", "- **A7:** from z = 1.26",
    ])
    assert _ab("Method:\n" + notes + "\n\nAnswers:\n\n" + AB_BLOCK) == AB_ANSWERS
    assert _ab("Readout.\n\n" + AB_BLOCK + "\n\nMethod:\n" + notes) == AB_ANSWERS
    assert not _critical_tripped("ab-test-readout", "Readout.\n\n" + AB_BLOCK + "\n\nMethod:\n" + notes)
    # A notes list can also carry exactly one number on every line, so every line reads
    # as a number. The block's lines are the number alone; the notes' lines are not.
    one_number_notes = "\n".join([
        "- **A1:** visitors summed over the 8 control rows", "- **A2:** visitors summed over the 8 variant rows",
        "- **A3:** signups over visitors for control, to 2 decimals", "- **A4:** the same for variant B, to 2 decimals",
        "- **A5:** ratio of the two rates, minus 1", "- **A6:** chi-square with 1 degree of freedom",
        "- **A7:** two-sided, from a pooled z of about 1.26",
    ])
    assert _ab(one_number_notes) == [8.0, 8.0, 2.0, 2.0, 1.0, 1.0, 1.26]           # alone, the notes are all there is to read
    assert _ab("Readout.\n\n" + AB_BLOCK + "\n\nMethod:\n" + one_number_notes) == AB_ANSWERS
    assert _ab("Method:\n" + one_number_notes + "\n\nAnswers:\n\n" + AB_BLOCK) == AB_ANSWERS
    assert not _critical_tripped("ab-test-readout", "Readout.\n\n" + AB_BLOCK + "\n\nMethod:\n" + one_number_notes)
    # Symbols around the number leave it alone; a unit word does not.
    decorated = "A1: **12,480**\nA2: `11,020`\nA3: ~6.00%\nA4: 6.40 %\nA5: +6.6%\nA6: ≈ 90.7\nA7: (0.209)"
    assert _ab("Readout.\n\n" + decorated + "\n\nMethod:\n" + one_number_notes) == AB_ANSWERS
    # The limit of the rule: a block whose own lines carry words looks like such a notes list,
    # and between two runs alike in every count the later one is read.
    worded = AB_BLOCK.replace("A1: 12,480", "A1: 12,480 visitors").replace("A2: 11,020", "A2: 11,020 visitors")
    assert _ab(worded) == AB_ANSWERS
    assert _ab(worded + "\n\nMethod:\n" + one_number_notes) == AB_ANSWERS         # five lines of it are still the number alone
    all_worded = "\n".join(line + " (final)" for line in AB_BLOCK.splitlines())
    assert _ab(all_worded) == AB_ANSWERS
    assert _ab(all_worded + "\n\nMethod:\n" + one_number_notes) == [8.0, 8.0, 2.0, 2.0, 1.0, 1.0, 1.26]
    # Such a block still beats notes that carry working: more of its lines read as a number.
    assert _ab(all_worded + "\n\nMethod:\n" + notes) == AB_ANSWERS
    # Only a line that is read can be the number alone: a blank answer is not one. A draft
    # with a blank and a final block with working on the same line are alike, so the later is read.
    blank_draft = AB_BLOCK.replace("12,480", "12,000").replace("A6: 90.7", "A6:")
    final = AB_BLOCK.replace("A6: 90.7", "A6: 8,580.4 / 94.6 = 90.7")
    assert _ab(blank_draft + "\n\nFinal:\n\n" + final) == AB_ANSWERS[:5] + [None, 0.209]
    # Between a clean line and the same label with working on it, the clean line stands.
    assert _ab("A1: 12,480\nA1: 749 / 12,480 = 6.00%")[0] == 12480.0 == _ab("A1: 749 / 12,480 = 6.00%\nA1: 12,480")[0]
    # Commentary between answer lines splits the block: only its largest piece is read.
    assert _ab(AB_BLOCK.replace("A3: 6.00%", "(both devices, four weeks)\nA3: 6.00%")) == [None, None] + AB_ANSWERS[2:]
    # A worked draft, then the block: the later full run is the block.
    draft = AB_BLOCK.replace("12,480", "12,000").replace("0.209", "0.5")
    assert _ab(draft + "\n\nCorrected:\n\n" + AB_BLOCK) == AB_ANSWERS
    assert _ab(draft + "\n\n" + AB_BLOCK) == AB_ANSWERS
    # Blank lines between answer lines do not break the block, and a code fence around it is fine.
    assert _ab("```\n" + AB_BLOCK.replace("\n", "\n\n") + "\n```") == AB_ANSWERS
    for wrap in ("> {}", "- {}", "1. {}", "`{}`", "**{}**", "### {}"):
        assert _ab("\n".join(wrap.format(line) for line in AB_BLOCK.splitlines())) == AB_ANSWERS, wrap
    assert _ab(AB_BLOCK.replace("\n", "\r\n")) == AB_ANSWERS
    # A blank answer is blank: it never borrows the next line, and the next line keeps its own answer.
    blank = AB_BLOCK.replace("A6: 90.7", "A6:")
    assert _ab(blank) == AB_ANSWERS[:5] + [None, 0.209]
    assert _ab(AB_BLOCK.replace("A7: 0.209", "A7:") + "\n\nNote: z is about 1.26, so the result is not significant.") == (
        AB_ANSWERS[:6] + [None])
    assert _ab(AB_BLOCK.replace("A1: 12,480", "A1:\n\n12,480"))[0] is None
    # Only a colon follows the label: the block is written as the prompt writes it.
    for separator in (".", " -", " =", ")"):
        assert _ab(re.sub(r"(?m)^(A\d):", rf"\1{separator}", AB_BLOCK)) == [None] * 7, separator
    assert _ab(AB_BLOCK.replace(":", "："))[0] == 12480.0   # a full-width colon is a colon
    # Labels outside the task's range are not answers and do not break the block.
    assert _ab(AB_BLOCK.replace("A4: 6.40%", "A4: 6.40%\nA9: 5")) == AB_ANSWERS
    assert _ab("A" + "9" * 5000 + ": 5\n" + AB_BLOCK) == AB_ANSWERS


def test_a_format_slip_is_absence_not_invention():
    slip = "A1: 404s with ≥1 inlink: 7\nA2: 5\nA3: 4\nA4: 6\nA5: 4\nA6: 8,865 sessions (4 URLs)"
    results = _results("seo-technical-triage", slip)
    assert {"answer_block_complete", "q1_broken_linked", "q6_sessions_at_risk"} == _failed(results)
    assert results["q6_sessions_at_risk"]["missing"] is True
    assert not _critical_tripped("seo-technical-triage", slip)
    working = ("A1: 5,580 + 6,900 = 12,480\nA2: 5,620 + 5,400 = 11,020\nA3: 749 / 12,480 = 6.00%\n"
               "A4: 705 / 11,020 = 6.40%\nA5: 6.6%\nA6: 90.7\nA7: 0.209")
    assert not _critical_tripped("ab-test-readout", working)
    # Rates given as fractions are a unit slip: wrong, but not invented data.
    fractions = "A1: 12,480\nA2: 11,020\nA3: 0.0600\nA4: 0.0640\nA5: 0.066\nA6: 90.7\nA7: 0.209"
    assert {"q3_control_rate", "q4_variant_rate", "q5_relative_lift"} == _failed(_results("ab-test-readout", fractions))
    assert not _critical_tripped("ab-test-readout", fractions)
    # A lift with the wrong sign is a wrong lift, however the minus is typed.
    for minus in ("-", "−", "–"):
        assert "q5_relative_lift" in _zeroed(_results("ab-test-readout", AB_BLOCK.replace("A5: 6.6%", f"A5: {minus}6.6%")))
    # A single clear figure that no reading of the data supports still trips it.
    assert _critical_tripped("ab-test-readout", AB_BLOCK.replace("12,480", "20,000"))


def test_tasks_without_the_flag_parse_answers_as_before():
    ledger = bench.load_tasks()["ads-ledger-analysis"]
    assert "single_number" not in ledger["answers"]
    facts = bench.measured_facts(
        ledger, "A1: 749 / 12,480 = 6.00%\nA2. $10,228.41 total\n> A3: 10\nA4: 8,470.84\n\nNote\nA4: sum of 8 rows\nA5:\nA1: 3")
    # First number on the line, last labelled line wins, and a blank answer reads the line after it:
    # the behaviour the 21 earlier tasks were graded under, kept as it was.
    assert [facts[f"answer_q{index}"] for index in range(1, 6)] == [749.0, 10228.41, None, 8.0, 1.0]
    with pytest.raises(ValueError, match="single_number must be a boolean"):
        bench._validate_task({**ledger, "answers": {"count": 5, "single_number": "yes"}},
                             bench.TASKS_DIR / "ads-ledger-analysis.json")


# ----------------------------------------------------------------- the judge's reference

def test_the_judge_gets_reference_totals_computed_from_the_recorded_prompt():
    tasks = bench.load_tasks()
    for task_id in NEW_TASKS:
        task = tasks[task_id]
        for include_skills in (True, False):
            reference = bench.judge_source_reference(task, bench.assemble_prompt(task, include_skills))
            assert reference["version"] == task_references.VERSION == 3
            assert reference["answers"] == _targets(task), task_id
        prompt = bench.assemble_prompt(task, True)
        assert set(task_references.supplied_sources(prompt)) == {path.rsplit("/", 1)[1] for path in task["fixtures"]}
    # Other tasks have no such reference, and asking is not an error.
    assert bench.judge_source_reference(tasks["headline"], bench.assemble_prompt(tasks["headline"], True)) == {}


def test_a_prompt_whose_sources_cannot_be_read_warns_and_grades_without_a_reference():
    task = bench.load_tasks()["seo-technical-triage"]
    for broken in ("", "no sources here", "\x00",
                   "---\n\n## Supplied source: crawl_export.csv\n\nurl,status_code\nx,not-a-number\n"):
        with pytest.warns(RuntimeWarning, match="no judge reference for seo-technical-triage"):
            assert bench.judge_source_reference(task, broken) == {}


def test_grading_shows_the_judge_the_reference_and_records_its_version(tmp_path, monkeypatch):
    task = bench.load_tasks()["seo-technical-triage"]
    run_dir = tmp_path / "run"
    (run_dir / "prompts").mkdir(parents=True)
    (run_dir / "responses").mkdir()
    prompt = bench.assemble_prompt(task, include_skills=True)
    (run_dir / "prompts" / "seo-technical-triage.md").write_text(prompt)
    (run_dir / "responses" / "answer.md").write_text(_answer_block([7, 5, 4, 6, 4, "8,865"]))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "run", "models": {"claude-haiku-4-5": {"model": "anthropic/claude-haiku-4-5"}},
        "tasks": ["seo-technical-triage"], "repetitions": 1, "skills_included": True,
        "tools_enabled": False, "max_output_tokens": 16000,
    }))
    (run_dir / "attempts.jsonl").write_text(json.dumps({
        "task_id": "seo-technical-triage", "model_id": "claude-haiku-4-5", "repetition": 1,
        "response_path": "responses/answer.md", "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }) + "\n")
    judge_prompts = []

    def fake_generate(_spec, judge_prompt, *_args, **_kwargs):
        judge_prompts.append(judge_prompt)
        return {"text": json.dumps({"completed": True, "self_report": "complete", "criteria": [
            {"id": criterion_id, "pass": True, "evidence": "present"}
            for criterion_id in re.findall(r"(?m)^- id: (\S+) · ", judge_prompt)]})}

    monkeypatch.setattr(bench.providers, "generate", fake_generate)
    args = argparse.Namespace(run=str(run_dir), judge="claude-sonnet-5", current_rubric=True, label=None, tasks=None)
    assert bench.cmd_grade(args) == 0
    grading = json.loads((run_dir / "grading.json").read_text())
    assert grading["task_reference_version"] == task_references.VERSION == 3
    assert grading["source_reference_version"] == reference_facts.VERSION
    # The judge was shown the reference: both redirecting URLs of each chain, 38 inlinks.
    (judge_prompt,) = judge_prompts
    reference = json.loads(judge_prompt.split("## Source reference totals")[1].split("\n\n")[1])
    assert reference == _reference("seo-technical-triage")
    assert reference["issues"]["redirect_chains"]["inlinks"] == 38


# ------------------------------------------------------------------ seo-content-brief

def _seo():
    rows = _table("seo-brief/keyword_export.csv")
    ranking = sorted((row for row in rows if row["current_rank"] and int(row["current_rank"]) <= 10),
                     key=lambda row: int(row["current_rank"]))
    ranked = {row["keyword"] for row in ranking}
    by_topic = collections.defaultdict(list)
    for row in rows:
        if row["intent"] == "informational" and int(row["difficulty"]) <= 45 and row["keyword"] not in ranked:
            by_topic[row["topic"]].append(row)
    volumes = {topic: sum(int(row["monthly_searches"]) for row in group) for topic, group in by_topic.items()}
    target = max(volumes, key=volumes.get)
    qualifying = sorted(by_topic[target], key=lambda row: -int(row["monthly_searches"]))
    return rows, ranking, volumes, target, qualifying


def test_seo_content_brief_oracle_and_trap():
    task = bench.load_tasks()["seo-content-brief"]
    rows, ranking, volumes, target, qualifying = _seo()
    answers = [len(ranking), len(qualifying), volumes[target], int(qualifying[0]["monthly_searches"]),
               sum(int(row["monthly_searches"]) for row in ranking)]
    assert target == "cold brew tea"
    assert list(_targets(task).values()) == answers == [6, 7, 10290, 3600, 28080]
    raw = collections.Counter()
    for row in rows:
        raw[row["topic"]] += int(row["monthly_searches"])
    # The trap: the topic with the most raw search volume is not the target,
    # and its head term is a buying-intent keyword an existing page ranks for.
    assert raw.most_common(1)[0][0] == "green tea"
    head = max(rows, key=lambda row: int(row["monthly_searches"]))
    assert (head["keyword"], head["intent"], head["current_rank"]) == ("best green tea", "commercial", "4")
    assert sorted(volumes.values())[-2] < 0.75 * volumes[target]  # no near-tie for the target
    assert not _failed(_results("seo-content-brief", _answer_block(answers)))
    green = [row for row in rows if row["topic"] == "green tea"]
    careless = _answer_block([6, len(green), raw["green tea"], int(head["monthly_searches"]), answers[4]])
    assert {"q3_topic_volume", "q4_primary_volume"} <= _zeroed(_results("seo-content-brief", careless))
    assert not _critical_tripped("seo-content-brief", careless)  # the trap is not invention
    # A row sits exactly on each threshold the definitions use, and one just past it,
    # placed where reading the threshold wrongly changes an answer.
    by_keyword = {row["keyword"]: row for row in rows}
    assert by_keyword["cold brew tea vs iced tea"]["difficulty"] == "45" and by_keyword["cold brew tea vs iced tea"] in qualifying
    assert (by_keyword["what is oolong tea"]["difficulty"], by_keyword["what is oolong tea"]["intent"]) == ("46", "informational")
    assert by_keyword["does cold brew tea go bad"]["current_rank"] == "10" and by_keyword["does cold brew tea go bad"] in ranking
    assert by_keyword["loose leaf green tea"]["current_rank"] == "11"
    strict = _answer_block([5, 7, 9890, 3600, 27600])  # "better than 10" and "lower than 45" read strictly
    assert {"q1_already_ranking", "q3_topic_volume", "q5_ranking_volume"} <= _failed(_results("seo-content-brief", strict))


def test_seo_reference_and_the_wording_that_quotes_it():
    task = bench.load_tasks()["seo-content-brief"]
    rows, ranking, volumes, target, qualifying = _seo()
    outlines = (FIXTURES / "seo-brief/competitor_outlines.md").read_text()
    section = outlines.split("## Topic: cold brew tea")[1].split("## Topic:")[0].lower()
    # A qualifying keyword neither outline touches: none of its own words is in them.
    own_words = {"cold brew tea ratio": ["ratio"], "how long to cold brew tea": ["long"], "cold brew green tea": ["green"],
                 "cold brew tea vs iced tea": ["iced"], "cold brew tea caffeine": ["caffeine"],
                 "can you cold brew tea bags": ["bag"], "how to cold brew tea": []}
    assert set(own_words) == {row["keyword"] for row in qualifying}
    gaps = [row["keyword"] for row in qualifying
            if own_words[row["keyword"]] and not any(word in section for word in own_words[row["keyword"]])]
    reference = _reference("seo-content-brief")
    assert {key: reference[key] for key in reference if key not in ("version", "answers")} == {
        "target_topic": "cold brew tea",
        "primary_keyword": "how to cold brew tea",
        "qualifying_keywords_in_target_topic": [
            {"keyword": row["keyword"], "monthly_searches": int(row["monthly_searches"]),
             "difficulty": int(row["difficulty"])} for row in qualifying],
        "qualifying_keywords_neither_competing_outline_covers": gaps,
        "qualifying_volume_by_topic": dict(sorted(volumes.items(), key=lambda item: -item[1])),
        "keywords_already_ranking_top_10": [
            {"keyword": row["keyword"], "rank": int(row["current_rank"]), "url": row["ranking_url"]} for row in ranking],
        "existing_page_urls": sorted(re.findall(r"(?m)^\| (/\S+) \|", (FIXTURES / "seo-brief/existing_pages.md").read_text())),
    }
    assert gaps == ["cold brew tea caffeine", "can you cold brew tea bags"]
    assert all(row["ranking_url"] in reference["existing_page_urls"] for row in rows if row["ranking_url"])
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(task).items()}
    assert "targets the cold brew tea topic" in wording["target_topic_named"]
    assert "'how to cold brew tea'" in wording["primary_keyword_named"]
    assert ("(how to store loose leaf tea, best green tea, matcha caffeine, green tea caffeine, does tea expire, "
            "does cold brew tea go bad)") in wording["existing_rankings_respected"]
    assert "'cold brew tea ratio' and 'how long to cold brew tea'" in wording["outline_covers_demand"]
    assert "('cold brew tea caffeine' or 'can you cold brew tea bags')" in wording["competitor_gap_grounded"]
    # A slug proposed for the article being briefed is not an existing page, so it is not held to the page list.
    assert wording["internal_links_real"].endswith(
        "any URL that is not in the list, fails; a URL or slug the brief proposes for the new article itself is exempt.")


def test_nothing_supplied_names_the_topic_to_pick():
    """The fixtures used to: an outlines file titled for the target topic, and
    a note saying the blog had no article on it yet."""
    task = bench.load_tasks()["seo-content-brief"]
    outlines = (FIXTURES / "seo-brief/competitor_outlines.md").read_text()
    pages = (FIXTURES / "seo-brief/existing_pages.md").read_text()
    assert re.findall(r"(?m)^## Topic: (.+)$", outlines) == ["green tea", "cold brew tea", "matcha"]
    assert "cold" not in outlines.split("## Topic:")[0].lower()        # the title and the introduction
    notes = pages.split("Notes from the content lead:")[1].lower()
    assert "cold" not in notes and "no article" not in notes
    assert "cold brew" not in task["prompt"].lower()
    assert "outlines of competing articles for three topics the team is considering" in task["prompt"]
    assert "neither competing outline for its topic does" in task["prompt"]


# --------------------------------------------------------------- seo-technical-triage

def _crawl():
    rows = _table("seo-crawl/crawl_export.csv")
    by_url = {row["url"]: row for row in rows}

    def is_redirect(url):
        return url in by_url and by_url[url]["status_code"].startswith("3")

    broken = [row for row in rows if row["status_code"] == "404" and row["inlinks"] != "0"]
    starts = [row for row in rows if is_redirect(row["url"]) and is_redirect(row["redirect_target"])]
    hops = {row["redirect_target"] for row in starts}
    chain_urls = [row for row in rows if row in starts or row["url"] in hops]
    flagged = [row for row in rows if "noindex" in row["meta_robots"] and row["in_sitemap"] == "yes"]
    bad_canonical = [row for row in rows if row["status_code"] == "200" and row["canonical"]
                     and row["canonical"] != row["url"] and by_url[row["canonical"]]["status_code"] != "200"]
    titles = collections.defaultdict(list)
    for row in rows:
        if row["status_code"] == "200" and "noindex" not in row["meta_robots"] and row["canonical"] == row["url"]:
            titles[row["title"]].append(row["url"])
    groups = {title: sorted(urls) for title, urls in titles.items() if len(urls) >= 2}
    duplicates = [row for row in rows if row["title"] in groups and row["url"] in groups[row["title"]]]
    return rows, {"broken_linked_pages": (len(broken), broken), "redirect_chains": (len(starts), chain_urls),
                  "noindex_in_sitemap": (len(flagged), flagged), "bad_canonicals": (len(bad_canonical), bad_canonical),
                  "duplicate_titles": (len(groups), duplicates)}, groups


def test_seo_technical_triage_oracle_and_trap():
    task = bench.load_tasks()["seo-technical-triage"]
    rows, issues, groups = _crawl()
    answers = [issues[name][0] for name in ("broken_linked_pages", "redirect_chains", "noindex_in_sitemap",
                                            "bad_canonicals", "duplicate_titles")]
    answers.append(sum(int(row["organic_sessions_30d"]) for row in issues["noindex_in_sitemap"][1]))
    assert list(_targets(task).values()) == answers == [7, 5, 4, 6, 4, 8865]
    top = max(rows, key=lambda row: int(row["organic_sessions_30d"]))
    assert top["url"].endswith("/collections/rain-jackets") and top["organic_sessions_30d"] == "8420"
    # "At least one inlink": a broken page with exactly one is in the data, beside three with none.
    assert sorted(int(row["inlinks"]) for row in rows if row["status_code"] == "404") == [0, 0, 0, 1, 4, 6, 9, 14, 21, 38]
    assert "noindex" in top["meta_robots"] and top["in_sitemap"] == "yes"
    assert sorted(title.split(" | ")[0] for title in groups) == [
        "How to Choose Hiking Boots", "Merino Crew Top", "Shipping & Returns", "TrailLite Rain Shell",
    ]
    assert not _failed(_results("seo-technical-triage", _answer_block(answers)))
    # The careless reading counts every 404, every redirect, every noindex URL,
    # and every repeated title whether or not the page is indexable.
    every_title = collections.Counter(row["title"] for row in rows if row["title"])
    careless = _answer_block([
        sum(row["status_code"] == "404" for row in rows),
        sum(row["status_code"].startswith("3") for row in rows),
        sum("noindex" in row["meta_robots"] for row in rows),
        answers[3],
        sum(count >= 2 for count in every_title.values()),
        answers[5],
    ])
    assert {"q1_broken_linked", "q2_redirect_chains", "q3_noindex_in_sitemap",
            "q5_duplicate_title_groups"} <= _zeroed(_results("seo-technical-triage", careless))
    assert not _critical_tripped("seo-technical-triage", careless)


def test_triage_reference_counts_the_urls_the_prompt_says_an_issue_affects():
    """The reference used to count a chain's first URL only, so a triage that
    listed both redirecting URLs (38 inlinks, not 26) contradicted it."""
    task = bench.load_tasks()["seo-technical-triage"]
    rows, issues, groups = _crawl()
    reference = _reference("seo-technical-triage")
    expected = {
        name: {
            "count_as_the_prompt_counts_it": count,
            "affected_urls": sorted(row["url"] for row in urls),
            "organic_sessions_30d": sum(int(row["organic_sessions_30d"]) for row in urls),
            "inlinks": sum(int(row["inlinks"]) for row in urls),
        }
        for name, (count, urls) in issues.items()
    }
    assert reference["issues"] == expected
    assert {name: (issue["organic_sessions_30d"], issue["inlinks"]) for name, issue in expected.items()} == {
        "noindex_in_sitemap": (8865, 144), "duplicate_titles": (2800, 308), "bad_canonicals": (1938, 75),
        "broken_linked_pages": (0, 93), "redirect_chains": (0, 38),
    }
    assert len(expected["redirect_chains"]["affected_urls"]) == 10          # five chains, two redirecting URLs each
    assert reference["duplicate_title_groups"] == groups
    assert reference["url_with_most_organic_sessions"] == {
        "url": "https://www.pinecrestoutfitters.example/collections/rain-jackets", "organic_sessions_30d": 8420}
    dead = sorted(row["url"] for row in rows if row["status_code"] == "404" and row["inlinks"] == "0")
    assert reference["dead_pages_with_no_inlinks"] == dead and len(dead) == 3
    # The prompt's ordering rule gives exactly the order the rubric names, with no close neighbours.
    order = sorted(expected, key=lambda name: (-expected[name]["organic_sessions_30d"], -expected[name]["inlinks"]))
    assert reference["issue_order_by_sessions_then_inlinks"] == order == [
        "noindex_in_sitemap", "duplicate_titles", "bad_canonicals", "broken_linked_pages", "redirect_chains"]
    assert set(reference) == {"version", "answers", "issues", "issue_order_by_sessions_then_inlinks",
                              "duplicate_title_groups", "url_with_most_organic_sessions",
                              "dead_pages_with_no_inlinks", "interpretation"}
    # The judge is told the truth about what lies outside the lists.
    assert "reporting them is not an error" in reference["interpretation"]
    assert "URLs outside these lists are correctly configured" not in reference["interpretation"]
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(task).items()}
    assert ("noindex pages in the sitemap, duplicate titles, bad canonicals, broken linked pages, redirect chains"
            in wording["issues_in_order"])
    assert "reporting the 404 URLs that have no inlinks" in wording["decoys_not_flagged"]
    assert ("a redirect chain affects every redirecting URL in it (its first URL and each URL it passes through)"
            in task["prompt"])
    assert "most first; where two issue types affect no organic sessions" in task["prompt"]


def test_crawl_look_alikes_are_plainly_fine():
    """A page many practitioners would flag is not a fair decoy. Each
    look-alike here is configured the way the textbook says to."""
    rows = {row["url"]: row for row in _table("seo-crawl/crawl_export.csv")}
    filtered = [row for row in rows.values() if "?color=" in row["url"]]
    assert len(filtered) == 18
    for row in filtered:  # indexable signals, canonical to a live indexable collection
        parent = rows[row["canonical"]]
        assert "noindex" not in row["meta_robots"] and row["in_sitemap"] == "no"
        assert parent["status_code"] == "200" and "noindex" not in parent["meta_robots"]
    second_pages = [row for row in rows.values() if "?page=2" in row["url"]]
    assert len(second_pages) == 6 and all(" - Page 2 | " in row["title"] for row in second_pages)
    utility = [row for row in rows.values() if "noindex" in row["meta_robots"] and row["in_sitemap"] == "no"]
    assert sorted(row["url"].split(".example")[1] for row in utility) == [
        "/account/login", "/account/register", "/cart", "/checkout", "/search", "/wishlist"]
    old = [row for row in rows.values() if "/products/" in row["url"] and row["url"].endswith("-old")]
    assert len(old) == 3 and all(rows[row["canonical"]]["status_code"] == "200" for row in old)
    one_hop = [row for row in rows.values() if "/collections/old-" in row["url"]]
    assert len(one_hop) == 8 and all(rows[row["redirect_target"]]["status_code"] == "200" for row in one_hop)


# -------------------------------------------------------------- search-terms-negatives

THEMES = re.compile(r"\b(repair|restring|fix|curtains?|drapes|shutters|wholesale|trade|jobs|careers|diy|how to make)\b")


def _search():
    rows = _table("search-terms/search_terms_report.csv")
    irrelevant = [row for row in rows if THEMES.search(row["search_term"])]
    promote = [row for row in rows if row["added_as_keyword"] == "no" and int(row["conversions"]) >= 3
               and Decimal(row["cost_usd"]) <= 45 * int(row["conversions"])]
    return rows, irrelevant, promote


def _search_line(row: dict) -> dict:
    conversions = int(row["conversions"])
    return {"search_term": row["search_term"], "campaign": row["campaign"], "clicks": int(row["clicks"]),
            "cost_usd": float(row["cost_usd"]), "conversions": conversions,
            "cost_per_conversion_usd": _money(Decimal(row["cost_usd"]) / conversions) if conversions else None}


def test_search_terms_negatives_oracle_and_trap(generator):
    task = bench.load_tasks()["search-terms-negatives"]
    rows, irrelevant, promote = _search()
    answers = [float(sum(Decimal(row["cost_usd"]) for row in rows if row["conversions"] == "0")), len(promote),
               float(sum(Decimal(row["cost_usd"]) for row in irrelevant)), sum(int(row["conversions"]) for row in promote)]
    assert list(_targets(task).values()) == answers == [2380.36, 5, 1636.9, 30]
    assert sorted(row["search_term"] for row in irrelevant) == sorted(term for term, *_ in generator.SEARCH_IRRELEVANT)
    assert len(irrelevant) == 16 and all(row["conversions"] == "0" for row in irrelevant)
    by_term = {row["search_term"]: row for row in rows}
    # Both sides of each threshold in the promote definition are in the data.
    assert Decimal(by_term["roman blinds for bay window"]["cost_usd"]) / 4 == Decimal("45")         # exactly at the target
    assert Decimal(by_term["faux wood blinds white"]["cost_usd"]) / 3 == Decimal("46.5")            # just over
    assert (by_term["free blind samples"]["conversions"], by_term["roller blinds for kitchen"]["conversions"]) == ("3", "2")
    assert by_term["made to measure roller blinds"]["added_as_keyword"] == "yes"                   # already a keyword
    # The traps: brand searches that fail a blunt rule.
    assert by_term["sablewood blinds reviews"]["conversions"] == "0"
    assert Decimal(by_term["sablewood blinds"]["cost_usd"]) / 9 > 45
    # A product search with no order never has many clicks behind it.
    product_zero = [row for row in rows if row["conversions"] == "0" and row not in irrelevant
                    and "sablewood" not in row["search_term"]]
    assert product_zero and max(int(row["clicks"]) for row in product_zero) == 24
    assert not _failed(_results("search-terms-negatives", _answer_block(answers)))
    careless = _answer_block([answers[0], answers[1], answers[0], answers[3]])  # blocks everything without an order
    assert "q3_irrelevant_spend" in _zeroed(_results("search-terms-negatives", careless))
    assert not _critical_tripped("search-terms-negatives", careless)


def test_search_reference_and_the_wording_that_quotes_it():
    task = bench.load_tasks()["search-terms-negatives"]
    rows, irrelevant, promote = _search()
    reference = _reference("search-terms-negatives")
    brand = sorted((row for row in rows if "sablewood" in row["search_term"] and row not in irrelevant),
                   key=lambda row: row["search_term"])
    above = [row for row in rows if row["added_as_keyword"] == "no" and int(row["conversions"]) >= 3 and row not in promote]
    assert {key: reference[key] for key in reference if key not in ("version", "answers", "interpretation")} == {
        "irrelevant_search_terms": [_search_line(row) for row in sorted(irrelevant, key=lambda row: row["search_term"])],
        "promote_candidates": [_search_line(row) for row in sorted(promote, key=lambda row: -int(row["conversions"]))],
        "brand_search_terms": [_search_line(row) for row in brand],
        "not_yet_keywords_with_3_or_more_conversions_above_target": [_search_line(row) for row in above],
        "most_clicks_on_a_product_search_with_no_conversion": 24,
    }
    assert [row["search_term"] for row in brand] == ["sablewood", "sablewood blinds", "sablewood blinds reviews"]
    assert [row["search_term"] for row in above] == ["faux wood blinds white"]
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(task).items()}
    # Both are about the negatives alone: the prompt does not ask for these terms to be listed as kept.
    assert "brand name ('sablewood', 'sablewood blinds' and 'sablewood blinds reviews')." in wording["brand_not_negated"]
    assert "(they would block 'cheap blackout blinds' and 'free blind samples')" in wording["relevant_terms_kept"]
    assert "are kept" not in wording["brand_not_negated"] + wording["relevant_terms_kept"]
    assert ("All 5 promote candidates are named: 'cheap blackout blinds', 'day night blinds made to measure', "
            "'wooden venetian blinds 2 inch', 'roman blinds for bay window' and 'free blind samples'."
            ) in wording["promotions_named"]
    assert "or 'faux wood blinds white' (above the target cost per conversion)" in wording["promotions_named"]


def test_every_irrelevant_search_term_is_ruled_out_in_writing_and_no_shortcut_finds_them():
    task = bench.load_tasks()["search-terms-negatives"]
    rows, irrelevant, promote = _search()
    answers = list(_targets(task).values())
    facts = (FIXTURES / "search-terms/business_facts.md").read_text().lower()
    for words in (("repair", "restring", "parts"), ("curtains", "drapes", "curtain rods", "shutters"),
                  ("trade", "wholesale"), ("fabric", "kits", "making your own"), ("jobs", "careers")):
        assert any("does not" in line and all(word in line for word in words)
                   for line in facts.splitlines()), words
    assert "or is looking for a job" in task["prompt"]
    # Leaving out the two job searches is outside the full-credit band.
    jobs = sum(Decimal(row["cost_usd"]) for row in irrelevant if re.search(r"jobs|careers", row["search_term"]))
    without_jobs = _answer_block([answers[0], answers[1], float(Decimal(str(answers[2])) - jobs), answers[3]])
    assert "q3_irrelevant_spend" in _failed(_results("search-terms-negatives", without_jobs))
    # The reviewer's notes list, one number on every line, after a correct block: the block is read.
    block = "A1: $2,380.36\nA2: 5\nA3: $1,636.90\nA4: 30"
    notes = ("- **A1:** total cost of the 70 search terms with no conversions\n- **A2:** candidates with at least 3 conversions\n"
             "- **A3:** total cost of the 16 irrelevant search terms\n- **A4:** conversions of the candidates, in 2 campaigns")
    assert not _failed(_results("search-terms-negatives", "Review.\n\n" + block + "\n\nNotes:\n" + notes))
    assert not _critical_tripped("search-terms-negatives", "Review.\n\n" + block + "\n\nNotes:\n" + notes)
    # The irrelevant terms are spread over the account, so no campaign total is the answer.
    campaigns = collections.defaultdict(Decimal)
    for row in rows:
        campaigns[row["campaign"]] += Decimal(row["cost_usd"])
    assert len({row["campaign"] for row in irrelevant}) == 7
    for campaign, cost in campaigns.items():
        shortcut = _answer_block([answers[0], answers[1], float(cost), answers[3]])
        assert "q3_irrelevant_spend" in _failed(_results("search-terms-negatives", shortcut)), campaign
        assert any(row["campaign"] == campaign and row not in irrelevant for row in rows), campaign


def test_the_irrelevant_spend_band_gives_full_credit_to_no_single_row_error():
    """At 2% of the total (about $33) full credit went to an answer that left out the
    brand-plus-job search, and to one that counted any one of 94 relevant rows."""
    task = bench.load_tasks()["search-terms-negatives"]
    rows, irrelevant, promote = _search()
    answers = list(_targets(task).values())
    target = Decimal("1636.90")
    assert sum(Decimal(row["cost_usd"]) for row in irrelevant) == target == Decimal(str(answers[2]))

    def a3(value) -> dict:
        response = _answer_block([answers[0], answers[1], f"{value:.2f}" if isinstance(value, Decimal) else value, answers[3]])
        return _results("search-terms-negatives", response)["q3_irrelevant_spend"]

    # The exact figure, and the figure rounded to the whole dollar, earn full credit.
    for exact in ("$1,636.90", "1636.9", "1,636.90", "$1,637", "1637"):
        assert (a3(exact)["pass"], a3(exact)["score"]) == (True, 1.0), exact
    # Case one: the brand-plus-job search left out, on the view that a brand search is never irrelevant.
    careers = next(row for row in irrelevant if row["search_term"] == "sablewood blinds careers")
    assert Decimal(careers["cost_usd"]) == Decimal("26.80") == min(Decimal(row["cost_usd"]) for row in irrelevant)
    left_out = a3(target - Decimal("26.80"))
    assert left_out["pass"] is False and left_out["score"] == pytest.approx((400 - 26.8) / 399.5, abs=1e-4)
    for row in irrelevant:  # and so for every irrelevant search term
        assert a3(target - Decimal(row["cost_usd"]))["pass"] is False, row["search_term"]
    # Case two: one relevant search term wrongly counted as irrelevant, whichever it is.
    relevant = [row for row in rows if row not in irrelevant]
    assert len(relevant) == 107 and min(Decimal(row["cost_usd"]) for row in rows) == Decimal("1.03")
    for row in relevant:
        counted_in = a3(target + Decimal(row["cost_usd"]))
        assert counted_in["pass"] is False and counted_in["score"] < 1, row["search_term"]
    # A miss of one cheap row costs little; a miss of $400 or more earns nothing.
    assert a3(target + Decimal("1.03"))["score"] == pytest.approx((400 - 1.03) / 399.5, abs=1e-4)
    assert a3(target + Decimal("400"))["score"] == 0 == a3(target - Decimal("400"))["score"]
    assert a3(Decimal(str(answers[0])))["score"] == 0                       # every search term without an order


def test_the_search_prompt_asks_for_the_work_without_pointing_at_the_traps():
    prompt = bench.load_tasks()["search-terms-negatives"]["prompt"]
    for hint in ("whatever it cost", "every other search term is kept", "costly or odd", "should be kept"):
        assert hint not in prompt, hint
    # What the two keep-criteria rest on: negatives are for the irrelevant terms.
    assert "the negative keywords that will block the irrelevant search terms" in prompt
    assert "the shortest word or phrase that blocks its whole theme" in prompt       # match_types_fit
    assert "the search terms you considered blocking and are keeping" in prompt      # three_lists_present


# -------------------------------------------------------------- lifecycle-reengagement

def _lifecycle():
    rows = _table("lifecycle/subscribers.csv")

    def before(row, day):
        return not row["last_open_date"] or dt.date.fromisoformat(row["last_open_date"]) < day

    subscribed = [row for row in rows if row["consent_status"] == "subscribed"]
    mailable = [row for row in subscribed if (row["hard_bounce"], row["spam_complaint"]) == ("no", "no")]
    lapsed = [row for row in mailable if before(row, dt.date(2026, 6, 1) - dt.timedelta(days=90))]
    dormant = [row for row in lapsed if before(row, dt.date(2025, 6, 1))]
    return rows, subscribed, mailable, lapsed, dormant


def _buyers(group: list[dict]) -> int:
    return sum(row["orders_count"] != "0" for row in group)


def test_lifecycle_reengagement_oracle_and_trap():
    task = bench.load_tasks()["lifecycle-reengagement"]
    rows, subscribed, mailable, lapsed, dormant = _lifecycle()
    answers = [len(mailable), len(lapsed), _buyers(lapsed), len(lapsed) - _buyers(lapsed), len(dormant)]
    assert list(_targets(task).values()) == answers == [193, 97, 50, 47, 23]
    assert len(rows) == 260
    # Both window edges are in the data: opened exactly 90 days ago (not
    # lapsed) and the day before (lapsed); 2025-06-01 (not long-dormant).
    opens = {row["last_open_date"] for row in subscribed}
    assert {"2026-03-03", "2026-03-02", "2025-06-01", "2025-05-31"} <= opens
    # The trap: people without consent who have ordered, some of them often.
    imports = [row for row in rows if row["consent_status"] == "never_consented"]
    assert {row["source"] for row in imports} == {"checkout_import", "event_list_import"}
    assert not _failed(_results("lifecycle-reengagement", _answer_block(answers)))
    everyone_quiet = [row for row in rows if row["consent_status"] != "pending_confirmation"
                      and (not row["last_open_date"] or row["last_open_date"] < "2026-03-03")]
    careless = _answer_block([len(subscribed), len(everyone_quiet), answers[2], answers[3], answers[4]])
    results = _results("lifecycle-reengagement", careless)
    assert "q2_lapsed" in _zeroed(results) and "q1_mailable" in _failed(results)
    assert not _critical_tripped("lifecycle-reengagement", careless)
    # Mailing the whole file is not a reading of the data: that does trip it.
    assert _critical_tripped("lifecycle-reengagement", _answer_block([len(rows), 150, 50, 47, 23]))


def test_lifecycle_reference_and_the_policy_the_rubric_quotes():
    task = bench.load_tasks()["lifecycle-reengagement"]
    rows, subscribed, mailable, lapsed, dormant = _lifecycle()
    flow = [row for row in lapsed if row not in dormant]
    consent = collections.Counter(row["consent_status"] for row in rows)
    reference = _reference("lifecycle-reengagement")
    assert {key: reference[key] for key in reference if key not in ("version", "answers")} == {
        "rows": 260,
        # Who gets the three emails and who gets the single last-chance one.
        "three_email_audience": {"total": len(flow), "buyers": _buyers(flow), "non_buyers": len(flow) - _buyers(flow)},
        "long_dormant_one_email_audience": {
            "total": len(dormant), "buyers": _buyers(dormant), "non_buyers": len(dormant) - _buyers(dormant)},
        "not_mailable": {
            "unsubscribed": consent["unsubscribed"], "never_consented": consent["never_consented"],
            "pending_confirmation": consent["pending_confirmation"],
            "subscribed_with_hard_bounce": sum(row["hard_bounce"] == "yes" for row in subscribed),
            "subscribed_with_spam_complaint": sum(
                (row["hard_bounce"], row["spam_complaint"]) == ("no", "yes") for row in subscribed),
        },
        "without_consent_but_with_orders": sum(
            row["orders_count"] != "0" for row in rows if row["consent_status"] in ("unsubscribed", "never_consented")),
    }
    assert reference["three_email_audience"] == {"total": 74, "buyers": 41, "non_buyers": 33}
    assert reference["long_dormant_one_email_audience"] == {"total": 23, "buyers": 9, "non_buyers": 14}
    assert reference["not_mailable"] == {"unsubscribed": 24, "never_consented": 19, "pending_confirmation": 9,
                                         "subscribed_with_hard_bounce": 11, "subscribed_with_spam_complaint": 4}
    assert reference["without_consent_but_with_orders"] == 24
    # The policy's numbers and the checks that quote them come from the same constants.
    policy = (FIXTURES / "lifecycle/email_policy.md").read_text()
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(task).items()}
    for in_policy, criterion_id, in_check in (
        ("at most three re-engagement emails, at least 5 days apart", "cadence_follows_policy", "the three emails at least 5 days apart"),
        ("10% off the next box with code COMEBACK10, valid for 14 days", "offer_rules_followed", "10% off with code COMEBACK10, valid for 14 days"),
        ('"Five 20-Minute Dinners" recipe pack', "offer_rules_followed", "'Five 20-Minute Dinners' recipe pack"),
        ("by 7 days after their final email", "exit_and_sunset", "7 days after their final email"),
        ("not opened an email in the last 90 days", "flow_three_emails", "exactly three emails"),
    ):
        assert in_policy in policy and in_check in wording[criterion_id], criterion_id
    assert "which has exactly three emails" in task["prompt"]
    assert "one for lapsed buyers and one for lapsed non-buyers" in task["prompt"]


# -------------------------------------------------------------------- ab-test-readout

def _ab_totals():
    rows = _table("ab-test/experiment_results.csv")
    totals = collections.defaultdict(lambda: collections.Counter())
    for row in rows:
        for field in ("visitors", "signups", "paid_conversions"):
            totals[row["variant"]][field] += int(row[field])
            totals[row["variant"], row["device"]][field] += int(row[field])
    return rows, totals


def _ab_p(totals, field: str) -> float:
    control, variant = totals["control"], totals["variant_b"]
    n1, n2 = control["visitors"], variant["visitors"]
    pooled = (control[field] + variant[field]) / (n1 + n2)
    z = (variant[field] / n2 - control[field] / n1) / (pooled * (1 - pooled) * (1 / n1 + 1 / n2)) ** 0.5
    return 2 * (1 - statistics.NormalDist().cdf(abs(z)))


def test_ab_test_readout_oracle_and_trap():
    task = bench.load_tasks()["ab-test-readout"]
    rows, totals = _ab_totals()
    control, variant = totals["control"], totals["variant_b"]
    rate_control = control["signups"] / control["visitors"] * 100
    rate_variant = variant["signups"] / variant["visitors"] * 100
    half = (control["visitors"] + variant["visitors"]) / 2
    chi = sum((arm["visitors"] - half) ** 2 / half for arm in (control, variant))
    answers = [control["visitors"], variant["visitors"], round(rate_control, 2), round(rate_variant, 2),
               round((rate_variant / rate_control - 1) * 100, 1), round(chi, 1), round(_ab_p(totals, "signups"), 3)]
    assert list(_targets(task).values()) == pytest.approx(answers)
    assert answers == [12480, 11020, 6.0, 6.4, 6.6, 90.7, 0.209]
    # The traps: read early, a split no 50/50 assignment produces, the gap on
    # mobile only, and a secondary metric that just clears 5%.
    secondary_p = _ab_p(totals, "paid_conversions")
    assert max(control["visitors"], variant["visitors"]) < 18000
    assert answers[6] > 0.05 > secondary_p > 0.04
    assert not _failed(_results("ab-test-readout", _answer_block(
        ["12,480", "11,020", f"{answers[2]:.2f}%", f"{answers[3]:.2f}%", f"{answers[4]}%", answers[5], answers[6]])))
    # A continuity-corrected test (0.219) is inside the full-credit band; a one-sided one is not.
    block = [12480, 11020, 6.0, 6.4, 6.6, 90.7]
    assert "q7_p_value" not in _failed(_results("ab-test-readout", _answer_block(block + [0.219])))
    assert "q7_p_value" in _zeroed(_results("ab-test-readout", _answer_block(block + [0.104])))
    # Careless: the lift in percentage points and the secondary metric's p-value.
    careless = _answer_block(["12,480", "11,020", "6.00%", "6.40%", "0.4%", answers[5], round(secondary_p, 3)])
    assert {"q5_relative_lift", "q7_p_value"} == _zeroed(_results("ab-test-readout", careless))
    assert not _critical_tripped("ab-test-readout", careless)


def test_ab_reference_and_the_wording_that_quotes_it():
    task = bench.load_tasks()["ab-test-readout"]
    rows, totals = _ab_totals()
    reference = _reference("ab-test-readout")
    assert {key: reference[key] for key in reference if key not in ("version", "answers", "interpretation")} == {
        "totals": {variant: dict(totals[variant]) for variant in ("control", "variant_b")},
        "by_device": {device: {variant: dict(totals[variant, device]) for variant in ("control", "variant_b")}
                      for device in ("desktop", "mobile")},
        "weeks": 4,
        # Half of the visitors the test received: what each variant is compared with in the sample-ratio check.
        "expected_visitors_per_variant_under_the_planned_50_50_split":
            sum(int(row["visitors"]) for row in rows) // 2,
        "secondary_metric_p_value": round(_ab_p(totals, "paid_conversions"), 3),
    }
    assert reference["expected_visitors_per_variant_under_the_planned_50_50_split"] == 11750
    assert sum(int(row["visitors"]) for row in rows) == 23500
    assert reference["by_device"]["mobile"] == {
        "control": {"visitors": 6900, "signups": 347, "paid_conversions": 66},
        "variant_b": {"visitors": 5400, "signups": 283, "paid_conversions": 67}}
    assert reference["by_device"]["desktop"]["control"]["visitors"] == 5580
    assert reference["by_device"]["desktop"]["variant_b"]["visitors"] == 5620
    assert reference["secondary_metric_p_value"] == 0.049
    # The plan's numbers and the checks that quote them come from the same constants.
    plan = (FIXTURES / "ab-test/test_plan.md").read_text()
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(task).items()}
    assert "18,000 visitors per variant (two-sided test, 5% significance" in plan and "not a decision metric" in plan
    assert "the 18,000 visitors the plan required" in wording["stop_rule_respected"]
    assert "at the plan's 5% level" in wording["not_significant_stated"]
    assert "(12,480 control against 11,020 variant B)" in wording["srm_flagged"]
    assert ("the mobile rows, where variant B has 5,400 visitors against control's 6,900 (desktop is balanced, "
            "5,620 against 5,580). Naming mobile is enough") in wording["imbalance_located"]
    # The prompt's own definition speaks of "the 50/50 split the plan called for", so a readout that
    # gives the count that split expects is not misquoting the plan, whose sample size is 18,000.
    assert "with the 50/50 split the plan called for" in task["prompt"]
    assert ("half of the visitors the two variants received (11,750), is derived from the results: stating it, also as "
            "what the planned split called for, is not an invented figure") in wording["no_invented_data"]
    assert "every figure about the plan matches the test plan" in wording["no_invented_data"]
    assert "It is not the sample size the plan required of each variant." in reference["interpretation"]


def test_the_ab_prompt_asks_for_the_work_without_pointing_at_the_traps():
    prompt = bench.load_tasks()["ab-test-readout"]["prompt"]
    for hint in ("which device", "which week", "split of visitors between the variants is not", "mobile"):
        assert hint not in prompt, hint
    assert "whether the test can be trusted and why" in prompt                                # srm_flagged
    assert "point to the rows of the results that show it" in prompt                         # imbalance_located
    assert "a clear recommendation with the next step" in prompt                             # next_step_concrete
    assert "from the supplied files" in prompt                                               # the plan is citable


# ------------------------------------------------------------- monthly-report-reconcile

def _monthly():
    ads = _table("monthly-report/ads_platforms.csv")
    events = _table("monthly-report/analytics_purchases.csv")
    orders = _table("monthly-report/order_system.csv")
    may = [row for row in orders if dt.date.fromisoformat(row["order_date"]).month == 5]
    real = [row for row in may if row["status"] not in {"cancelled", "test"}]
    return ads, events, orders, may, real


def test_monthly_report_reconcile_oracle_and_trap():
    task = bench.load_tasks()["monthly-report-reconcile"]
    ads, events, orders, may, real = _monthly()
    spend = sum(Decimal(row["spend_usd"]) for row in ads)
    gross = sum(Decimal(row["gross_usd"]) for row in real)
    net = gross - sum(Decimal(row["refund_usd"]) for row in real)
    seen = collections.Counter(row["order_id"] for row in events)
    answers = [float(spend), len(real), float(net), sum(count - 1 for count in seen.values()),
               round(float(net / spend), 2), sum(int(row["platform_conversions"]) for row in ads)]
    assert list(_targets(task).values()) == answers == [11435.94, 282, 35901.46, 39, 3.14, 454]
    assert not _failed(_results("monthly-report-reconcile", _answer_block(
        [f"${answers[0]:,.2f}", answers[1], f"${answers[2]:,.2f}", answers[3], answers[4], answers[5]])))
    # The trap: revenue of the right orders with their refunds left in. It is
    # about 5% high, and the band ends at 3%, so it plainly earns nothing.
    assert 0.04 < float(gross) / answers[2] - 1 < 0.06
    trap = _answer_block([f"${answers[0]:,.2f}", answers[1], f"${gross:,.2f}", answers[3],
                          round(float(gross / spend), 2), answers[5]])
    results = _results("monthly-report-reconcile", trap)
    assert {"q3_net_revenue", "q5_blended_roas"} == _zeroed(results) == _failed(results)
    assert not _critical_tripped("monthly-report-reconcile", trap)
    # Reading revenue off the analytics export misses by more still.
    analytics_revenue = sum(Decimal(row["revenue_usd"]) for row in events)
    careless = _answer_block([f"${answers[0]:,.2f}", len(orders), f"${analytics_revenue:,.2f}", answers[3],
                              round(float(analytics_revenue / spend), 2), answers[5]])
    assert {"q2_real_orders", "q3_net_revenue", "q5_blended_roas"} <= _zeroed(
        _results("monthly-report-reconcile", careless))


def test_monthly_reference_carries_what_a_careful_report_states():
    ads, events, orders, may, real = _monthly()
    first = {}
    for row in events:
        first.setdefault(row["order_id"], Decimal(row["revenue_usd"]))
    platforms = collections.Counter()
    for row in ads:
        platforms[row["platform"]] += int(row["platform_conversions"])
    reference = _reference("monthly-report-reconcile")
    assert {key: reference[key] for key in reference if key not in ("version", "answers", "interpretation")} == {
        "order_system": {
            "rows": len(orders),
            "rows_dated_outside_may": len(orders) - len(may),
            "may_rows_by_status": dict(collections.Counter(row["status"] for row in may)),
            "gross_of_real_orders_usd": _money(sum(Decimal(row["gross_usd"]) for row in real)),
            "refunds_on_real_orders_usd": _money(sum(Decimal(row["refund_usd"]) for row in real)),
        },
        "analytics": {
            "purchase_rows": len(events),
            "distinct_order_ids": len(first),
            "revenue_all_rows_usd": _money(sum(Decimal(row["revenue_usd"]) for row in events)),
            # Analytics revenue with each order counted once, and the orders it never saw.
            "revenue_counting_each_order_once_usd": _money(sum(first.values())),
            "real_orders_with_no_purchase_event": sum(row["order_id"] not in first for row in real),
        },
        "ad_platforms": {
            "reported_conversions_by_platform": dict(platforms),
            "reported_revenue_usd": _money(sum(Decimal(row["platform_revenue_usd"]) for row in ads)),
        },
    }
    assert reference["order_system"] == {
        "rows": 300, "rows_dated_outside_may": 3,
        "may_rows_by_status": {"paid": 262, "test": 6, "cancelled": 9, "refunded": 12, "partially_refunded": 8},
        "gross_of_real_orders_usd": 37677.88, "refunds_on_real_orders_usd": 1776.42}
    assert reference["analytics"] == {
        "purchase_rows": 313, "distinct_order_ids": 274, "revenue_all_rows_usd": 40014.36,
        "revenue_counting_each_order_once_usd": 35251.13, "real_orders_with_no_purchase_event": 22}
    assert sum(reference["ad_platforms"]["reported_conversions_by_platform"].values()) == 454 > 1.4 * 282


def test_each_monthly_criterion_tests_one_thing():
    task = bench.load_tasks()["monthly-report-reconcile"]
    wording = {criterion_id: criterion["check"] for criterion_id, criterion in _by_id(task).items()}
    judged = {criterion_id for criterion_id, criterion in _by_id(task).items() if not criterion.get("programmatic")}
    assert judged == {"summary_first", "summary_headline_figures", "other_sources_not_the_result",
                      "differences_quantified", "no_invented_data", "summary_plain_words", "fixes_concrete",
                      "method_auditable"}
    # Presence of the four figures is one criterion; presenting another
    # source's figure as the result is another, and only that one.
    assert "does not present" not in wording["summary_headline_figures"]
    assert "judged separately" in wording["summary_headline_figures"]
    assert "analytics revenue is presented as the month's revenue" in wording["other_sources_not_the_result"]
    # Row filters are asked of the two figures that filter rows; a total has no filter and a ratio has inputs.
    assert "for real orders and net revenue, which rows were counted and which were left out" in wording["method_auditable"]
    assert "for ad spend, that it is the total of the ad platform export" in wording["method_auditable"]
    assert "for blended return on ad spend, the two figures divided" in wording["method_auditable"]
    assert "with any abbreviation spelled out the first time it appears" in task["prompt"]  # summary_plain_words


# ----------------------------------------------------------------------- never raising

@pytest.mark.parametrize("text", [
    "", "\x00", "A1: 1,,2\nA2: ٣\nA3: .\nA4: -\nA5: 1e9999", "A1:\nA2:\nA3:", "A1: " + "9" * 5000,
    "A" + "9" * 5000 + ": 5", "A1: −\nA2: –\nA3: -$", "A1: ١٢٤٨٠\nA2: １２４８０", "\n" * 5000 + "A1: 7", " " * 20000,
    "A1: 7\n" * 3000,
])
def test_no_odd_input_makes_a_check_raise(text):
    tasks = bench.load_tasks()
    for task_id in NEW_TASKS:
        facts = bench.measured_facts(tasks[task_id], text)
        bench.programmatic_results(tasks[task_id], facts)
        with pytest.warns(RuntimeWarning):
            assert bench.judge_source_reference(tasks[task_id], text) == {}
