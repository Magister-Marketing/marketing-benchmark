"""The eight tasks added in November 2026: fixtures, oracles, traps and parsing.

What is pinned here, for every task:

- the committed fixtures and every value a program decides in a task file are
  exactly what `scripts/gen_more_tasks.py` produces and pins;
- every banded target equals a figure recomputed in this file from the
  committed fixture, by code that shares nothing with `task_references`;
- a careful answer passes every programmatic criterion, and the careless
  answer the task is built to catch scores zero on the criterion meant to
  catch it without failing the critical one;
- the checks never raise and never credit an unfinished deliverable.
"""
import collections
import csv
import datetime as dt
import importlib.util
import io
import json
import re
import statistics
from decimal import Decimal

import pytest

from eval_runner import bench, task_facts, task_references

NEW_TASKS = {
    "seo-content-brief": "holdout",
    "seo-technical-triage": "development",
    "search-terms-negatives": "development",
    "lifecycle-reengagement": "holdout",
    "ab-test-readout": "development",
    "social-calendar-limits": "development",
    "monthly-report-reconcile": "holdout",
    "positioning-from-competitors": "holdout",
}
DATA_TASKS = [task_id for task_id in NEW_TASKS if task_id in task_references.REFERENCES]
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


def _targets(task: dict) -> dict[str, float]:
    return {
        criterion["id"]: criterion["programmatic"]["near"]
        for section in bench.RUBRIC_SECTIONS
        for criterion in task["rubric"][section]
        if isinstance(criterion.get("programmatic"), dict)
        and criterion["programmatic"].get("fact", "").startswith("answer_q")
    }


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


# ------------------------------------------------------------------ the set as a whole

def test_new_tasks_load_with_their_splits_versions_and_one_oracle_backed_critical():
    tasks = bench.load_tasks()
    assert {task_id: tasks[task_id]["split"] for task_id in NEW_TASKS} == NEW_TASKS
    for task_id in NEW_TASKS:
        task = tasks[task_id]
        # Version 1 was a local draft, run once and discarded.
        assert (task["prompt_version"], task["rubric_version"]) == (2, 2), task_id
        critical = bench.critical_criterion_ids(task)
        assert len(critical) == 1, task_id
        assert bench.oracle_rules(task)[next(iter(critical))], task_id
        assert bench.task_supports_harness(task, bench.HARNESS_ID)
        assert all((bench.REPO_ROOT / path).is_file() for path in task["fixtures"])
        # No criterion is already true of an empty reply.
        assert bench.free_credit_scores(task) == {}, task_id
    for task_id in DATA_TASKS:
        assert tasks[task_id]["answers"]["single_number"] is True


def test_committed_fixtures_and_task_files_are_what_the_generator_pins(generator):
    assert generator.check() == []


def test_check_reports_a_changed_tolerance_or_definition_and_survives_reformatting(generator, tmp_path):
    """A hand edit to a number or a definition is drift; reformatting is not."""
    source = bench.TASKS_DIR
    for path in source.glob("*.json"):
        (tmp_path / path.name).write_text(path.read_text())
    assert generator.check(tmp_path) == []

    target = tmp_path / "monthly-report-reconcile.json"
    original = target.read_text()
    # Reformatted, same content: no drift, no exception.
    target.write_text(json.dumps(json.loads(original), indent=4, ensure_ascii=False))
    assert generator.check(tmp_path) == []
    changed, problems = generator.sync_tasks(tmp_path)
    assert (changed, problems) == (["monthly-report-reconcile"], [])
    assert target.read_text() == original  # sync restores the repository's layout

    def drift(mutate) -> list[str]:
        task = json.loads(original)
        mutate(task)
        target.write_text(json.dumps(task))
        return generator.check(tmp_path)

    def widen(task):
        criterion = next(c for c in task["rubric"]["completion"] if c["id"] == "q3_net_revenue")
        criterion["programmatic"]["tolerance"]["zero"] = 0.05

    def redefine(task):
        task["prompt"] = task["prompt"].replace("minus `refund_usd`", "before refunds")

    def retarget(task):
        next(c for c in task["rubric"]["completion"] if c["id"] == "q2_real_orders")["programmatic"]["near"] = 300

    def reoracle(task):
        next(c for c in task["rubric"]["skill_adherence"] if c["id"] == "no_invented_data")["fails_if_zero"] = [
            "q3_net_revenue"]

    def unstrict(task):
        task["answers"] = {"count": 6}

    assert any("q3_net_revenue" in problem and "pinned" in problem for problem in drift(widen))
    assert any("no longer carries the line" in problem and "refund_usd" in problem for problem in drift(redefine))
    assert any("q2_real_orders" in problem for problem in drift(retarget))
    assert any("fails_if_zero" in problem for problem in drift(reoracle))
    assert any("answers" in problem for problem in drift(unstrict))
    target.write_text("{not json")
    assert any("not valid JSON" in problem for problem in generator.check(tmp_path))
    target.unlink()
    assert any("missing task file" in problem for problem in generator.check(tmp_path))


def test_oracle_lists_hold_only_plain_aggregates_with_wide_zero_bands():
    """A trap or a miscount costs its own criterion. Only a figure no reading
    of the data supports may fail the critical one, so an oracle-listed answer
    has a zero band of at least a tenth of its value."""
    tasks = bench.load_tasks()
    for task_id in DATA_TASKS:
        by_id = {c["id"]: c for s in bench.RUBRIC_SECTIONS for c in tasks[task_id]["rubric"][s]}
        for listed in next(iter(bench.oracle_rules(tasks[task_id]).values())):
            condition = by_id[listed]["programmatic"]
            zero = condition["tolerance"]["zero"]
            relative = zero if condition["tolerance"]["kind"] == "relative" else zero / condition["near"]
            assert relative >= 0.0999, (task_id, listed, relative)


# ------------------------------------------------------- answer lines: the number alone

def test_single_number_answers_leave_a_line_with_working_unparsed():
    """`A1: 749 / 12,480 = 6.00%` used to read 749, a wrong figure the oracle
    scored as invented. A task that opts in reads only a line with one number."""
    task = bench.load_tasks()["ab-test-readout"]

    def answers(block: str) -> list:
        facts = bench.measured_facts(task, "Readout.\n\n" + block)
        return [facts[f"answer_q{index}"] for index in range(1, 8)]

    correct = [12480.0, 11020.0, 6.0, 6.4, 6.6, 90.7, 0.209]
    plain = "A1: 12,480\nA2: 11,020\nA3: 6.00%\nA4: 6.40%\nA5: 6.6%\nA6: 90.7\nA7: 0.209"
    assert answers(plain) == correct
    assert answers(plain.replace("A3: 6.00%", "A3: 749 / 12,480 = 6.00%"))[2] is None
    assert answers(plain.replace("A6: 90.7", "A6: chi2 = 90.7"))[5] is None
    assert answers(plain.replace("A7: 0.209", "A7: 0.209 (z = 1.26)"))[6] is None
    # One number with a word, a sign or a unit around it is still one number.
    assert answers("A1: 12,480 visitors\nA2: 11,020 visitors\nA3: Control signup rate = 6.00%\nA4: ~6.40 percent\n"
                   "A5: +6.6 %\nA6: χ² = 90.7\nA7: p ≈ .209") == correct
    # Harmless wrappers around the label line.
    for wrap in ("> {}", "- {}", "1. {}", "`{}`", "**{}**", "### {}"):
        assert answers("\n".join(wrap.format(line) for line in plain.splitlines())) == correct, wrap
    # A later note that restates a label with working does not shadow the answer.
    assert answers(plain + "\n\nNotes:\nA6: with 1 degree of freedom the critical value is 3.84.")[5] == 90.7
    # Rounded, regrouped or comma-decimal money is not the number alone either.
    monthly = bench.load_tasks()["monthly-report-reconcile"]
    facts = bench.measured_facts(
        monthly, "A1: $11.4k\nA2: 282 of 300 rows\nA3: $35 901.46\nA4: 39\nA5: 3,14\nA6: 454 conversions")
    assert [facts[f"answer_q{index}"] for index in range(1, 7)] == [None, None, None, 39.0, None, 454.0]


def test_a_format_slip_is_absence_not_invention():
    slip = "A1: 404s with ≥1 inlink: 7\nA2: 5\nA3: 4\nA4: 6\nA5: 4\nA6: 8,865 sessions (4 URLs)"
    results = _results("seo-technical-triage", slip)
    assert {"answer_block_complete", "q1_broken_linked", "q6_sessions_at_risk"} <= _failed(results)
    assert results["q6_sessions_at_risk"]["missing"] is True
    assert not _critical_tripped("seo-technical-triage", slip)
    working = ("A1: 5,580 + 6,900 = 12,480\nA2: 5,620 + 5,400 = 11,020\nA3: 749 / 12,480 = 6.00%\n"
               "A4: 705 / 11,020 = 6.40%\nA5: 6.6%\nA6: 90.7\nA7: 0.209")
    assert not _critical_tripped("ab-test-readout", working)
    # Rates given as fractions are a unit slip: wrong, but not invented data.
    fractions = "A1: 12,480\nA2: 11,020\nA3: 0.0600\nA4: 0.0640\nA5: 0.066\nA6: 90.7\nA7: 0.209"
    assert {"q3_control_rate", "q4_variant_rate", "q5_relative_lift"} == _failed(_results("ab-test-readout", fractions))
    assert not _critical_tripped("ab-test-readout", fractions)
    # A single clear figure that no reading of the data supports still trips it.
    assert _critical_tripped("ab-test-readout", "A1: 20,000\nA2: 20,000\nA3: 6.00%\nA4: 6.40%\nA5: 6.6%\nA6: 90.7\nA7: 0.209")


def test_tasks_without_the_flag_parse_answers_as_before():
    ledger = bench.load_tasks()["ads-ledger-analysis"]
    assert "single_number" not in ledger["answers"]
    facts = bench.measured_facts(ledger, "A1: 749 / 12,480 = 6.00%\nA2. $10,228.41 total\n> A3: 10")
    assert (facts["answer_q1"], facts["answer_q2"], facts["answer_q3"]) == (749.0, 10228.41, None)
    with pytest.raises(ValueError, match="single_number must be a boolean"):
        bench._validate_task({**ledger, "answers": {"count": 5, "single_number": "yes"}},
                             bench.TASKS_DIR / "ads-ledger-analysis.json")


# ----------------------------------------------------------------- the judge's reference

def test_the_judge_gets_reference_totals_computed_from_the_recorded_prompt():
    tasks = bench.load_tasks()
    for task_id in DATA_TASKS:
        task = tasks[task_id]
        for include_skills in (True, False):
            reference = bench.judge_source_reference(task, bench.assemble_prompt(task, include_skills))
            assert reference["version"] == task_references.VERSION
            assert reference["answers"] == _targets(task), task_id
        # Computed from the prompt that was recorded, not from today's files.
        prompt = bench.assemble_prompt(task, True)
        assert set(task_references.supplied_sources(prompt)) == {path.rsplit("/", 1)[1] for path in task["fixtures"]}
    # No reference is not an error: other tasks, and prompts that cannot be read.
    assert bench.judge_source_reference(tasks["headline"], bench.assemble_prompt(tasks["headline"], True)) == {}
    assert bench.judge_source_reference(tasks["social-calendar-limits"], "anything") == {}
    for broken in ("", "no sources here", "---\n\n## Supplied source: crawl_export.csv\n\nurl,status_code\nx,not-a-number\n"):
        assert bench.judge_source_reference(tasks["seo-technical-triage"], broken) == {}


def test_references_name_what_the_judged_criteria_name():
    tasks = bench.load_tasks()

    def reference(task_id):
        return bench.judge_source_reference(tasks[task_id], bench.assemble_prompt(tasks[task_id], False))

    crawl = reference("seo-technical-triage")
    assert crawl["url_with_most_organic_sessions"]["organic_sessions_30d"] == 8420
    assert {name: len(issue["urls"]) for name, issue in crawl["issues"].items()} == {
        "broken_linked_pages": 7, "redirect_chains": 5, "noindex_in_sitemap": 4,
        "bad_canonicals": 6, "duplicate_title_pages": 9,
    }
    # The prompt's ordering rule (organic sessions, then inlinks) gives exactly
    # the order the rubric names, and no two neighbours are close.
    ordered = sorted(crawl["issues"], key=lambda name: (-crawl["issues"][name]["organic_sessions_30d"],
                                                       -crawl["issues"][name]["inlinks"]))
    assert ordered == ["noindex_in_sitemap", "duplicate_title_pages", "bad_canonicals",
                       "broken_linked_pages", "redirect_chains"]
    sessions = [crawl["issues"][name]["organic_sessions_30d"] for name in ordered]
    assert sessions[0] > 3 * sessions[1] and sessions[1] > 1.2 * sessions[2] and sessions[3:] == [0, 0]
    assert crawl["issues"]["broken_linked_pages"]["inlinks"] > 2 * crawl["issues"]["redirect_chains"]["inlinks"]
    wording = {c["id"]: c["check"] for s in bench.RUBRIC_SECTIONS for c in tasks["seo-technical-triage"]["rubric"][s]}
    assert ("noindex pages in the sitemap, duplicate titles, bad canonicals, broken linked pages, redirect chains"
            in wording["issues_in_order"])
    assert "most first; where two issue types affect no organic sessions" in tasks["seo-technical-triage"]["prompt"]
    search = reference("search-terms-negatives")
    assert len(search["irrelevant_search_terms"]) == 16 and len(search["promote_candidates"]) == 5
    assert [row["search_term"] for row in search["not_yet_keywords_with_3_or_more_conversions_above_target"]] == [
        "faux wood blinds white"]
    lifecycle = reference("lifecycle-reengagement")
    assert lifecycle["rows"] - sum(lifecycle["not_mailable"].values()) == lifecycle["answers"]["q1_mailable"]
    ab = reference("ab-test-readout")
    assert ab["by_device"]["mobile"]["variant_b"]["visitors"] == 5400 and ab["secondary_metric_p_value"] == 0.049
    monthly = reference("monthly-report-reconcile")
    assert monthly["order_system"]["rows_dated_outside_may"] == 3
    assert monthly["analytics"]["purchase_rows"] - monthly["analytics"]["distinct_order_ids"] == 39
    seo = reference("seo-content-brief")
    assert (seo["target_topic"], seo["primary_keyword"]) == ("cold brew tea", "how to cold brew tea")
    assert "/collections/cold-brew" in seo["existing_page_urls"]


# ------------------------------------------------------------------ seo-content-brief

def _seo_answers():
    rows = _table("seo-brief/keyword_export.csv")
    ranking = [row for row in rows if row["current_rank"] and int(row["current_rank"]) <= 10]
    ranked_keywords = {row["keyword"] for row in ranking}
    by_topic = collections.defaultdict(list)
    for row in rows:
        if (row["intent"] == "informational" and int(row["difficulty"]) <= 45
                and row["keyword"] not in ranked_keywords):
            by_topic[row["topic"]].append(int(row["monthly_searches"]))
    volumes = {topic: sum(values) for topic, values in by_topic.items()}
    target = max(volumes, key=volumes.get)
    answers = [len(ranking), len(by_topic[target]), volumes[target], max(by_topic[target]),
               sum(int(row["monthly_searches"]) for row in ranking)]
    return rows, target, answers, volumes


def test_seo_content_brief_oracle_and_trap():
    task = bench.load_tasks()["seo-content-brief"]
    rows, target, answers, volumes = _seo_answers()
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
    outlines = (FIXTURES / "seo-brief/competitor_outlines.md").read_text().lower()
    assert "caffeine" not in outlines and "tea bag" not in outlines  # the two real gaps
    assert "ratio" in outlines and "how long to steep" in outlines
    pages = (FIXTURES / "seo-brief/existing_pages.md").read_text()
    assert all(row["ranking_url"] in pages for row in rows if row["ranking_url"])


# --------------------------------------------------------------- seo-technical-triage

def _crawl_answers():
    rows = _table("seo-crawl/crawl_export.csv")
    code = {row["url"]: row["status_code"] for row in rows}
    broken = [row for row in rows if row["status_code"] == "404" and row["inlinks"] != "0"]
    chains = [row for row in rows
              if row["status_code"].startswith("3") and code[row["redirect_target"]].startswith("3")]
    flagged = [row for row in rows if "noindex" in row["meta_robots"] and row["in_sitemap"] == "yes"]
    bad_canonical = [row for row in rows if row["status_code"] == "200" and row["canonical"]
                     and row["canonical"] != row["url"] and code[row["canonical"]] != "200"]
    titles = collections.Counter(
        row["title"] for row in rows
        if row["status_code"] == "200" and "noindex" not in row["meta_robots"] and row["canonical"] == row["url"]
    )
    groups = [title for title, count in titles.items() if count >= 2]
    sessions = sum(int(row["organic_sessions_30d"]) for row in flagged)
    return rows, [len(broken), len(chains), len(flagged), len(bad_canonical), len(groups), sessions], groups


def test_seo_technical_triage_oracle_and_trap():
    task = bench.load_tasks()["seo-technical-triage"]
    rows, answers, groups = _crawl_answers()
    assert list(_targets(task).values()) == answers == [7, 5, 4, 6, 4, 8865]
    top = max(rows, key=lambda row: int(row["organic_sessions_30d"]))
    assert top["url"].endswith("/collections/rain-jackets") and top["organic_sessions_30d"] == "8420"
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


def _search_answers():
    rows = _table("search-terms/search_terms_report.csv")
    zero = sum(Decimal(row["cost_usd"]) for row in rows if row["conversions"] == "0")
    irrelevant = [row for row in rows if THEMES.search(row["search_term"])]
    promote = [row for row in rows if row["added_as_keyword"] == "no" and int(row["conversions"]) >= 3
               and Decimal(row["cost_usd"]) <= 45 * int(row["conversions"])]
    answers = [float(zero), len(promote), float(sum(Decimal(row["cost_usd"]) for row in irrelevant)),
               sum(int(row["conversions"]) for row in promote)]
    return rows, answers, irrelevant, promote


def test_search_terms_negatives_oracle_and_trap(generator):
    task = bench.load_tasks()["search-terms-negatives"]
    rows, answers, irrelevant, promote = _search_answers()
    assert list(_targets(task).values()) == answers
    assert answers[1:] == [5, 1636.9, 30]
    assert sorted(row["search_term"] for row in irrelevant) == sorted(term for term, *_ in generator.SEARCH_IRRELEVANT)
    assert len(irrelevant) == 16 and all(row["conversions"] == "0" for row in irrelevant)
    assert sorted(row["search_term"] for row in promote) == [
        "cheap blackout blinds", "day night blinds made to measure", "free blind samples",
        "roman blinds for bay window", "wooden venetian blinds 2 inch",
    ]
    by_term = {row["search_term"]: row for row in rows}
    # The traps: brand searches that fail a blunt rule, and two near misses.
    assert by_term["sablewood blinds reviews"]["conversions"] == "0"
    assert Decimal(by_term["sablewood blinds"]["cost_usd"]) / 9 > 45
    assert Decimal(by_term["faux wood blinds white"]["cost_usd"]) / 3 > 45
    assert by_term["roller blinds for kitchen"]["conversions"] == "2"
    # A product search with no order never has many clicks behind it.
    product_zero = [row for row in rows if row["conversions"] == "0" and row not in irrelevant
                    and "sablewood" not in row["search_term"]]
    assert product_zero and max(int(row["clicks"]) for row in product_zero) <= 24
    assert not _failed(_results("search-terms-negatives", _answer_block(answers)))
    careless = _answer_block([answers[0], answers[1], answers[0], answers[3]])  # blocks everything without an order
    assert "q3_irrelevant_spend" in _zeroed(_results("search-terms-negatives", careless))
    assert not _critical_tripped("search-terms-negatives", careless)


def test_every_irrelevant_search_term_is_ruled_out_in_writing_and_no_shortcut_finds_them():
    task = bench.load_tasks()["search-terms-negatives"]
    rows, answers, irrelevant, _promote = _search_answers()
    facts = (FIXTURES / "search-terms/business_facts.md").read_text().lower()
    # Each theme has its own "does not" line; job searches are named in the
    # prompt's definition as well as in the facts.
    for words in (("repair", "restring", "parts"), ("curtains", "drapes", "curtain rods", "shutters"),
                  ("trade", "wholesale"), ("fabric", "kits", "making your own"), ("jobs", "careers")):
        assert any("does not" in line and all(word in line for word in words)
                   for line in facts.splitlines()), words
    assert "or is looking for a job" in task["prompt"]
    assert "Block only irrelevant search terms" in task["prompt"]
    # Leaving out the two job searches is no longer inside the full-credit band.
    jobs = sum(Decimal(row["cost_usd"]) for row in irrelevant if re.search(r"jobs|careers", row["search_term"]))
    without_jobs = _answer_block([answers[0], answers[1], float(Decimal(str(answers[2])) - jobs), answers[3]])
    assert "q3_irrelevant_spend" in _failed(_results("search-terms-negatives", without_jobs))
    # The irrelevant terms are spread over the account, so no campaign total is the answer.
    campaigns = collections.defaultdict(Decimal)
    for row in rows:
        campaigns[row["campaign"]] += Decimal(row["cost_usd"])
    assert len({row["campaign"] for row in irrelevant}) >= 6
    for campaign, cost in campaigns.items():
        shortcut = _answer_block([answers[0], answers[1], float(cost), answers[3]])
        assert "q3_irrelevant_spend" in _failed(_results("search-terms-negatives", shortcut)), campaign
        assert any(row["campaign"] == campaign and row not in irrelevant for row in rows), campaign


# -------------------------------------------------------------- lifecycle-reengagement

def _lifecycle_answers():
    rows = _table("lifecycle/subscribers.csv")

    def before(row, day):
        return not row["last_open_date"] or dt.date.fromisoformat(row["last_open_date"]) < day

    mailable = [row for row in rows if (row["consent_status"], row["hard_bounce"], row["spam_complaint"])
                == ("subscribed", "no", "no")]
    lapsed = [row for row in mailable if before(row, dt.date(2026, 6, 1) - dt.timedelta(days=90))]
    buyers = [row for row in lapsed if row["orders_count"] != "0"]
    dormant = [row for row in lapsed if before(row, dt.date(2025, 6, 1))]
    return rows, [len(mailable), len(lapsed), len(buyers), len(lapsed) - len(buyers), len(dormant)]


def test_lifecycle_reengagement_oracle_and_trap():
    task = bench.load_tasks()["lifecycle-reengagement"]
    rows, answers = _lifecycle_answers()
    assert list(_targets(task).values()) == answers == [193, 97, 50, 47, 23]
    assert len(rows) == 260
    # Both window edges are in the data: opened exactly 90 days ago (not
    # lapsed) and the day before (lapsed); 2025-06-01 (not long-dormant).
    opens = {row["last_open_date"] for row in rows if row["consent_status"] == "subscribed"}
    assert {"2026-03-03", "2026-03-02", "2025-06-01", "2025-05-31"} <= opens
    # The trap: people without consent who have ordered, some of them often.
    no_consent = [row for row in rows if row["consent_status"] in ("unsubscribed", "never_consented")]
    assert sum(row["orders_count"] != "0" for row in no_consent) >= 20
    imports = [row for row in rows if row["consent_status"] == "never_consented"]
    assert {row["source"] for row in imports} == {"checkout_import", "event_list_import"}
    assert not _failed(_results("lifecycle-reengagement", _answer_block(answers)))
    subscribed = [row for row in rows if row["consent_status"] == "subscribed"]
    everyone_quiet = [row for row in rows if row["consent_status"] != "pending_confirmation"
                      and (not row["last_open_date"] or row["last_open_date"] < "2026-03-03")]
    careless = _answer_block([len(subscribed), len(everyone_quiet), answers[2], answers[3], answers[4]])
    results = _results("lifecycle-reengagement", careless)
    assert "q2_lapsed" in _zeroed(results) and "q1_mailable" in _failed(results)
    assert not _critical_tripped("lifecycle-reengagement", careless)
    # Mailing the whole file is not a reading of the data: that does trip it.
    assert _critical_tripped("lifecycle-reengagement", _answer_block([len(rows), 150, 50, 47, 23]))


def test_lifecycle_prompt_states_what_the_rubric_requires():
    task = bench.load_tasks()["lifecycle-reengagement"]
    policy = (FIXTURES / "lifecycle/email_policy.md").read_text()
    # The policy allows up to three emails; the number graded is the prompt's.
    assert "at most three re-engagement emails" in policy
    assert "which has exactly three emails" in task["prompt"]
    assert "one for lapsed buyers and one for lapsed non-buyers" in task["prompt"]
    for phrase in ("COMEBACK10", "14 days", "at least 5 days apart", "Five 20-Minute Dinners", "7 days after"):
        assert phrase in policy


# -------------------------------------------------------------------- ab-test-readout

def _ab_answers():
    rows = _table("ab-test/experiment_results.csv")
    totals = collections.defaultdict(lambda: collections.Counter())
    for row in rows:
        for field in ("visitors", "signups", "paid_conversions"):
            totals[row["variant"]][field] += int(row[field])
            totals[row["variant"], row["device"]][field] += int(row[field])
    control, variant = totals["control"], totals["variant_b"]

    def p_value(field):
        n1, n2 = control["visitors"], variant["visitors"]
        pooled = (control[field] + variant[field]) / (n1 + n2)
        z = (variant[field] / n2 - control[field] / n1) / (pooled * (1 - pooled) * (1 / n1 + 1 / n2)) ** 0.5
        return 2 * (1 - statistics.NormalDist().cdf(abs(z)))

    rate_control = control["signups"] / control["visitors"] * 100
    rate_variant = variant["signups"] / variant["visitors"] * 100
    half = (control["visitors"] + variant["visitors"]) / 2
    chi = sum((arm["visitors"] - half) ** 2 / half for arm in (control, variant))
    answers = [control["visitors"], variant["visitors"], round(rate_control, 2), round(rate_variant, 2),
               round((rate_variant / rate_control - 1) * 100, 1), round(chi, 1), round(p_value("signups"), 3)]
    return totals, answers, p_value("paid_conversions")


def test_ab_test_readout_oracle_and_trap():
    task = bench.load_tasks()["ab-test-readout"]
    totals, answers, secondary_p = _ab_answers()
    assert list(_targets(task).values()) == pytest.approx(answers)
    assert answers == [12480, 11020, 6.0, 6.4, 6.6, 90.7, 0.209]
    control, variant = totals["control"], totals["variant_b"]
    # The traps: read early, a split no 50/50 assignment produces, the gap on
    # mobile only, and a secondary metric that just clears 5%.
    assert max(control["visitors"], variant["visitors"]) < 18000
    assert (totals["control", "mobile"]["visitors"], totals["variant_b", "mobile"]["visitors"]) == (6900, 5400)
    assert (totals["control", "desktop"]["visitors"], totals["variant_b", "desktop"]["visitors"]) == (5580, 5620)
    assert answers[6] > 0.05 > secondary_p > 0.04
    plan = (FIXTURES / "ab-test/test_plan.md").read_text()
    assert "18,000 visitors per variant" in plan and "50/50" in plan and "not a decision metric" in plan
    assert "from the supplied files" in task["prompt"]  # the plan's figures are citable too
    assert "say where the difference is: which device, or which week" in task["prompt"]
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


# ------------------------------------------------------------- monthly-report-reconcile

def _monthly_answers():
    ads = _table("monthly-report/ads_platforms.csv")
    events = _table("monthly-report/analytics_purchases.csv")
    orders = _table("monthly-report/order_system.csv")
    spend = sum(Decimal(row["spend_usd"]) for row in ads)
    real = [row for row in orders
            if dt.date.fromisoformat(row["order_date"]).month == 5 and row["status"] not in {"cancelled", "test"}]
    gross = sum(Decimal(row["gross_usd"]) for row in real)
    net = gross - sum(Decimal(row["refund_usd"]) for row in real)
    seen = collections.Counter(row["order_id"] for row in events)
    answers = [float(spend), len(real), float(net), sum(count - 1 for count in seen.values()),
               round(float(net / spend), 2), sum(int(row["platform_conversions"]) for row in ads)]
    return events, orders, answers, gross, spend


def test_monthly_report_reconcile_oracle_and_trap():
    task = bench.load_tasks()["monthly-report-reconcile"]
    events, orders, answers, gross, spend = _monthly_answers()
    assert list(_targets(task).values()) == answers
    assert answers[1] == 282 and answers[3] == 39
    statuses = collections.Counter(row["status"] for row in orders)
    assert (statuses["cancelled"], statuses["test"], statuses["refunded"], statuses["partially_refunded"]) == (9, 6, 12, 8)
    assert sum(row["order_date"].startswith("2026-06") for row in orders) == 3
    assert answers[5] > 1.4 * answers[1]  # the platforms claim far more conversions than there were orders
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
    # One criterion asks for the four headline figures, not two.
    judged = [c["id"] for s in bench.RUBRIC_SECTIONS for c in task["rubric"][s] if not c.get("programmatic")]
    assert "summary_headline_figures" in judged and "headline_reconciled" not in judged
    assert "with any abbreviation spelled out the first time it appears" in task["prompt"]


# --------------------------------------------------------------- social-calendar-limits

CAREFUL_CALENDAR = """\
POST 1: 2026-03-02 | X | Spring is nearly here. Marlow Cycle Works runs Spring Tune-Up Week from 16 to 22 March. More soon. #TuneUpWeek
POST 2: 2026-03-03 | LinkedIn | Riding to work this spring? Spring Tune-Up Week runs 16 to 22 March at Marlow Cycle Works. A standard tune-up covers a brake adjustment, gear indexing, a chain clean and lube, a tyre check and a safety check. Booking details on Monday 9 March. #TuneUpWeek #BikeToWork
POST 3: 2026-03-04 | Instagram | What does a tune-up cover? Brakes adjusted, gears indexed, chain cleaned and lubed, tyres checked, and a safety check. About 45 minutes. Spring Tune-Up Week is 16 to 22 March. #TuneUpWeek #BikeMaintenance
POST 4: 2026-03-06 | X | Save the date: Spring Tune-Up Week, 16 to 22 March. Booking opens Monday 9 March at 9:00 am. #TuneUpWeek
POST 5: 2026-03-09 | X | Booking is open. A standard tune-up is $79 during Spring Tune-Up Week (regular price $99). Parts extra. 120 slots. Book: marlowcycle.example/tune-up #TuneUpWeek
POST 6: 2026-03-09 | LinkedIn | Booking for Spring Tune-Up Week is now open. From 16 to 22 March a standard tune-up at Marlow Cycle Works is $79; the regular price is $99. Parts extra. There are 120 slots across the week. Book yours: marlowcycle.example/tune-up #TuneUpWeek
POST 7: 2026-03-09 | Instagram | Booking is open for Spring Tune-Up Week, 16 to 22 March. Standard tune-up: $79 (regular price $99). Parts extra. 120 slots. Book at marlowcycle.example/tune-up #TuneUpWeek #BikeShop
POST 8: 2026-03-11 | LinkedIn | A standard tune-up takes about 45 minutes: brake adjustment, gear indexing, chain clean and lube, tyre check and safety check. During Spring Tune-Up Week it is $79. Parts extra. Booking closes Friday 13 March at 6:00 pm: marlowcycle.example/tune-up #TuneUpWeek
POST 9: 2026-03-12 | Instagram | Booking for Spring Tune-Up Week closes tomorrow, Friday 13 March, at 6:00 pm. Drop your bike at the workshop and collect it there. Book: marlowcycle.example/tune-up #TuneUpWeek
POST 10: 2026-03-13 | X | Last day to book Spring Tune-Up Week. Booking closes today at 6:00 pm. marlowcycle.example/tune-up #TuneUpWeek
POST 11: 2026-03-13 | LinkedIn | Booking for Spring Tune-Up Week closes today at 6:00 pm. A standard tune-up is $79 during the week (regular price $99). Parts extra. marlowcycle.example/tune-up #TuneUpWeek
POST 12: 2026-03-14 | Instagram | Booked in for Spring Tune-Up Week? Bring your bike to the workshop from Monday 16 March. Before you come, note anything that rattles, rubs or slips so we know where to look. #TuneUpWeek

The sequence moves from the dates, to what a tune-up covers, to booking opening, to the close.
"""
SOCIAL_RULES = {
    "spacing_rules", "embargo_kept", "no_booking_link_after_close", "price_note_present",
    "banned_words_absent", "prices_exact", "booking_posts_present", "hashtag_rules",
    "all_posts_present", "platform_split", "dates_in_window", "within_char_limits",
}


def _calendar(**replacements: str) -> str:
    lines = CAREFUL_CALENDAR.splitlines()
    for number, line in replacements.items():
        index = next(i for i, text in enumerate(lines) if text.startswith(f"POST {number[1:]}:"))
        lines[index] = line
    return "\n".join(lines)


def test_the_brief_is_rendered_from_the_constants_that_check_it(generator, monkeypatch):
    """The reviewer changed limits and dates in task_facts and most tests
    still passed. Every constant now changes the brief, which is committed."""
    brief = (FIXTURES / "social-calendar/campaign_brief.md").read_text()
    assert brief == generator.social_brief()
    for name, value in (
        ("SOCIAL_LIMITS", {"X": 270, "LinkedIn": 600, "Instagram": 400}),
        ("SOCIAL_LIMITS", {"X": 280, "LinkedIn": 600, "Instagram": 500}),
        ("SOCIAL_HASHTAG_LIMITS", {"X": 3, "LinkedIn": 3, "Instagram": 5}),
        ("SOCIAL_WINDOW", (dt.date(2026, 3, 2), dt.date(2026, 3, 16))),
        ("SOCIAL_WINDOW", (dt.date(2026, 3, 3), dt.date(2026, 3, 15))),
        ("SOCIAL_BOOKING_OPENS", dt.date(2026, 3, 10)),
        ("SOCIAL_BOOKING_CLOSES", dt.date(2026, 3, 12)),
        ("SOCIAL_CAMPAIGN_HASHTAG", "#TuneUp"),
        ("SOCIAL_BOOKING_LINK", "marlowcycle.example/book"),
        ("SOCIAL_PRICE_NOTE", "Parts are extra."),
        ("SOCIAL_PRICE", 69), ("SOCIAL_REGULAR_PRICE", 89), ("SOCIAL_SAVING", 10),
        ("SOCIAL_BANNED_WORDS", ("guaranteed", "cheapest", "#1")),
    ):
        with monkeypatch.context() as patch:
            patch.setattr(task_facts, name, value)
            assert generator.social_brief() != brief, name
            assert any("campaign_brief.md" in problem for problem in generator.check()), name
    assert generator.check() == []
    # The two numbers the task prompt states come from the same constants.
    prompt = bench.load_tasks()["social-calendar-limits"]["prompt"]
    assert f"Number the posts 1 to {task_facts.SOCIAL_POSTS}." in prompt
    positioning = bench.load_tasks()["positioning-from-competitors"]["prompt"]
    assert f"one sentence of {task_facts.POSITIONING_WORD_LIMIT} words or fewer" in positioning


def test_the_brief_asks_for_everything_the_judged_criteria_require():
    brief = (FIXTURES / "social-calendar/campaign_brief.md").read_text()
    task = bench.load_tasks()["social-calendar-limits"]
    judged = {c["id"] for s in bench.RUBRIC_SECTIONS for c in task["rubric"][s] if not c.get("programmatic")}
    assert judged == {"booking_window_respected", "no_invented_facts", "no_recycled_posts", "single_ask_per_post"}
    assert "No post may be a copy of another or a shortened version of another" in brief
    assert "One ask per post" in brief
    assert "do not invite people to book" in brief
    assert "State nothing about the shop, the mechanics, demand or results that is not in the facts above" in brief
    assert "at least one post dated 10 to 13 March carries it again as a reminder" in brief


def test_social_calendar_careful_answer_passes_and_each_rule_is_caught():
    assert not _failed(_results("social-calendar-limits", CAREFUL_CALENDAR))
    # A calendar may end on the day booking closes.
    assert not _failed(_results("social-calendar-limits", CAREFUL_CALENDAR.replace(
        "POST 12: 2026-03-14 | Instagram", "POST 12: 2026-03-13 | Instagram")))

    def failed(**replacements):
        return _failed(_results("social-calendar-limits", _calendar(**replacements)))

    # The date traps: the price and the link before booking opens; the link after it closes.
    assert failed(p4="POST 4: 2026-03-06 | X | Tune-ups are $79 during Spring Tune-Up Week. Parts extra. #TuneUpWeek") == {"embargo_kept"}
    assert failed(p4="POST 4: 2026-03-06 | X | Tune-ups will be 79 dollars during Spring Tune-Up Week. #TuneUpWeek") == {"embargo_kept"}
    assert failed(p1="POST 1: 2026-03-02 | X | Spring Tune-Up Week is coming: marlowcycle.example/tune-up #TuneUpWeek") == {"embargo_kept"}
    assert failed(p1="POST 1: 2026-03-02 | X | A special price is coming for Spring Tune-Up Week. #TuneUpWeek") == set()
    assert failed(p12="POST 12: 2026-03-14 | Instagram | Still time? marlowcycle.example/tune-up #TuneUpWeek") == {"no_booking_link_after_close"}
    assert failed(p8="POST 8: 2026-03-14 | LinkedIn | See you at the workshop next week. #TuneUpWeek") == {"spacing_rules"}
    assert failed(p3="POST 3: 2026-03-03 | LinkedIn | Spring Tune-Up Week is 16 to 22 March. #TuneUpWeek") == {
        "platform_split", "spacing_rules"}
    assert failed(p1="POST 1: 2026-03-01 | X | Spring Tune-Up Week is coming. #TuneUpWeek") == {"dates_in_window"}
    assert failed(p10="POST 10: 2026-03-13 | X | " + "Last day to book. " * 16 + "#TuneUpWeek") == {"within_char_limits"}
    assert failed(p1="POST 1: 2026-03-02 | X | Spring Tune-Up Week is coming. #TuneUpWeek #Bikes #Spring") == {"hashtag_rules"}
    assert failed(p1="POST 1: 2026-03-02 | X | Spring Tune-Up Week is coming.") == {"hashtag_rules"}
    assert failed(p5="POST 5: 2026-03-09 | X | Booking is open. A standard tune-up is $79. marlowcycle.example/tune-up #TuneUpWeek") == {"price_note_present"}
    assert failed(p2="POST 2: 2026-03-03 | LinkedIn | The best tune-up in town is coming 16 to 22 March. #TuneUpWeek") == {"banned_words_absent"}
    assert failed(p5="POST 5: 2026-03-09 | X | Booking is open: $69 tune-ups. marlowcycle.example/tune-up #TuneUpWeek") == {"prices_exact"}
    no_reminder = {f"p{n}": line.replace("marlowcycle.example/tune-up", "the link in our bio")
                   for n, line in ((8, CAREFUL_CALENDAR.splitlines()[7]), (9, CAREFUL_CALENDAR.splitlines()[8]),
                                   (10, CAREFUL_CALENDAR.splitlines()[9]), (11, CAREFUL_CALENDAR.splitlines()[10]))}
    assert failed(**no_reminder) == {"booking_posts_present"}


def test_social_calendar_reads_the_posts_however_they_are_dressed():
    posts = [line for line in CAREFUL_CALENDAR.splitlines() if line.startswith("POST ")]

    def dressed(change) -> str:
        return "\n".join(change(line) for line in posts)

    variants = {
        "bold label": dressed(lambda line: "**" + line.split(":", 1)[0] + ":**" + line.split(":", 1)[1]),
        "bullets": dressed(lambda line: "- " + line),
        "numbered": dressed(lambda line: line.split(":", 1)[0].split()[1] + ". " + line),
        "blockquote": dressed(lambda line: "> " + line),
        "code fence": "```\n" + "\n".join(posts) + "\n```",
        "bold platform": dressed(lambda line: line.replace("| X |", "| **X** |").replace("| LinkedIn |", "| **LinkedIn** |")),
        "lowercase platform": dressed(lambda line: line.replace("| LinkedIn |", "| linkedin |")),
        "hash before number": dressed(lambda line: line.replace("POST ", "POST #", 1)),
        "weekday after date": dressed(lambda line: line.replace(" | ", " (Mon) | ", 1)),
        "no spaces at pipes": dressed(lambda line: line.replace(" | ", "|")),
        "quoted text": dressed(lambda line: line.rsplit(" | ", 1)[0] + ' | "' + line.rsplit(" | ", 1)[1] + '"'),
        "length note": dressed(lambda line: line + f" ({len(line.rsplit(' | ', 1)[1])} chars)"),
        "restated later": "\n".join(posts) + "\n\nPOST 1: 2026-03-20 | X | $5 restated",
    }
    for name, text in variants.items():
        assert not _failed(_results("social-calendar-limits", text)), name
    # Arithmetic in the note is not a price in a post.
    with_sums = CAREFUL_CALENDAR + "\nAt $79 a slot, 120 slots is $9,480 of bookings."
    assert not _failed(_results("social-calendar-limits", with_sums))
    assert not _critical_tripped("social-calendar-limits", with_sums)


def test_an_unfinished_calendar_earns_no_rule_and_trips_nothing():
    """A one-post reply used to pass every limit check it had no chance to break."""
    one_post = "POST 1: 2026-03-09 | X | Booking is open: marlowcycle.example/tune-up #TuneUpWeek"
    for reply in (one_post, "\n".join(CAREFUL_CALENDAR.splitlines()[:11]), "", "I cannot write this."):
        assert _failed(_results("social-calendar-limits", reply)) == SOCIAL_RULES, reply[:40]
        assert not _critical_tripped("social-calendar-limits", reply)
    invented = _calendar(p5="POST 5: 2026-03-09 | X | Booking is open: $69 tune-ups. marlowcycle.example/tune-up #TuneUpWeek")
    assert _critical_tripped("social-calendar-limits", invented)
    assert not _critical_tripped("social-calendar-limits", CAREFUL_CALENDAR)
    # A draft of one post with a wrong price, then the calendar: the draft is
    # the graded line, so the price check fails, but a price the final version
    # dropped is not called invented.
    drafted = "POST 5: 2026-03-09 | X | DRAFT $75 tune-ups #TuneUpWeek\n\nFinal:\n" + CAREFUL_CALENDAR
    assert "prices_exact" not in _failed(_results("social-calendar-limits", drafted))
    assert not _critical_tripped("social-calendar-limits", drafted)
    assert _critical_tripped("social-calendar-limits", invented + "\n" + invented)


# ---------------------------------------------------------- positioning-from-competitors

CAREFUL_POSITIONING = """\
POSITIONING: For solo freelancers who want to be paid on time, Tallyhand is invoicing and payment-reminder software with one flat price and no per-invoice fee.
CLAIM-1: $12 a month, flat, with no per-invoice fee. [F5]
CLAIM-2: Customers who turned reminders on were paid a median of 9 days sooner than in their own previous quarter. [F3, F4]
CLAIM-3: A median of 4 minutes from sign-up to a first invoice in onboarding tests, and a 30-day trial with no card. [F2, F14]

What I did not use: "fastest", "#1", "most trusted", "2x faster", "bank-grade security" and "cheapest".
"""


def _positioning(old: str, new: str) -> str:
    assert old in CAREFUL_POSITIONING
    return CAREFUL_POSITIONING.replace(old, new)


def test_positioning_constants_match_the_sources(generator):
    sheet = (FIXTURES / "positioning/product_fact_sheet.md").read_text()
    competitors = (FIXTURES / "positioning/competitor_pages.md").read_text()
    dollars, percents = generator.source_prices_and_percents(sheet, competitors)
    assert dollars == set(task_facts.POSITIONING_SOURCE_DOLLARS)
    assert percents == set(task_facts.POSITIONING_SOURCE_PERCENTS)
    assert set(re.findall(r"(?m)^- (F\d+)\.", sheet)) == set(task_facts.POSITIONING_FACT_IDS)
    assert not re.search(r"\d\s?[x×]\b", sheet + competitors)  # no multiplier anywhere in the sources
    # The traps the founder's note sets: each request is unsupported by the sheet.
    note = (FIXTURES / "positioning/founder_note.md").read_text()
    for request in ("fastest", "#1", "most trusted", "2x faster", "bank-grade", "cheapest"):
        assert request in note
    assert "ranked 2nd of 11" in sheet and "Type II audit is in progress and must not be claimed" in sheet


def test_the_differentiators_the_rubric_names_follow_from_the_extracts():
    """A list the judge is told to accept must be derivable from the sources."""
    competitors = (FIXTURES / "positioning/competitor_pages.md").read_text()
    extracts = {block.split("\n", 1)[0].split(" (")[0]: block for block in competitors.split("\n## ")[1:]}
    assert set(extracts) == {"Ledgerly", "PaidUp", "Invoxa"}
    for name, text in extracts.items():
        # Every competitor takes a fee on invoices, so "no per-invoice fee" is Tallyhand's alone.
        assert re.search(r"fee on each paid invoice|of every invoice paid|for each invoice sent", text), name
        assert "solo" not in text.lower(), name          # none is built only for solo freelancers
        assert not re.search(r"median|\bdays sooner\b|\d+ minutes", text), name  # none gives a measured result
        assert "reminders" in text.lower(), name          # every one of them has reminders
    assert "no monthly price" in extracts["PaidUp"]       # so "cheapest" cannot be said
    task = bench.load_tasks()["positioning-from-competitors"]
    wording = {c["id"]: c["check"] for s in bench.RUBRIC_SECTIONS for c in task["rubric"][s]}
    assert "trial" not in wording["differentiators_real"] and "a free trial" in wording["shared_features_not_unique"]
    # Competitor facts are legitimate sources for the reasons the response gives.
    assert "nothing is stated about a competitor that its extract does not contain" in wording["no_invented_facts"]
    assert "facts about a competitor come from that competitor's extract" in task["prompt"]


def test_positioning_careful_answer_passes_and_each_rule_is_caught():
    assert not _failed(_results("positioning-from-competitors", CAREFUL_POSITIONING))

    def failed(old, new):
        return _failed(_results("positioning-from-competitors", _positioning(old, new)))

    assert failed("[F5]", "") == {"claims_cited"}
    assert failed("[F5]", "[F5, F15]") == {"claims_cited"}
    assert failed("$12 a month", "$10 a month") == {"figures_from_sources"}
    assert failed("with no per-invoice fee. [F5]", "with no per-invoice fee: $3 less than Ledgerly. [F5]") == {"figures_from_sources"}
    assert failed("were paid a median of 9 days sooner", "get paid 2x faster") == {"figures_from_sources"}
    assert failed("Tallyhand is invoicing", "Tallyhand is 40% faster invoicing") == {"figures_from_sources"}
    long_line = "POSITIONING: " + "Tallyhand is invoicing software for solo freelancers " * 6
    assert failed(CAREFUL_POSITIONING.splitlines()[0], long_line) == {"positioning_length"}
    # An unfinished deliverable earns nothing and trips nothing.
    every = {"all_lines_present", "positioning_length", "claims_cited", "figures_from_sources"}
    for reply in ("", "POSITIONING: Tallyhand is the #1 tool at $5 a month.", _positioning("CLAIM-3: A median", "A median")):
        assert _failed(_results("positioning-from-competitors", reply)) == every, reply[:30]
        assert not _critical_tripped("positioning-from-competitors", reply)


def test_positioning_figures_are_prices_percentages_and_multipliers_only():
    """One hit here scores the attempt zero, so the check counts only what is
    unmistakably a figure. The reviewer's cases, each as it should now fall."""
    def unsupported(old, new):
        facts = task_facts.positioning_facts(_positioning(old, new))
        return facts["positioning_unsupported_figure_count"]

    claim_1 = "CLAIM-1: $12 a month, flat, with no per-invoice fee. [F5]"
    fine = {
        "a fact id in round brackets": ("[F5]", "(F5)"),
        "the survey fact in round brackets": (claim_1, "CLAIM-1: Rated 4.6 out of 5 and ranked 2nd of 11 invoicing tools for ease of use. (F8)"),
        "a second fact id in prose": ("[F5]", "[F5] (see also F10 on security)"),
        "zero dollars for no fee": ("with no per-invoice fee", "with $0 per-invoice fees"),
        "zero percent against a competitor's 1%": ("with no per-invoice fee.", "with no per-invoice fee: Ledgerly takes 1% of each paid invoice, Tallyhand takes 0%."),
        "a tax-form number": ("For solo freelancers who", "For solo freelancers and 1099 contractors who"),
        "one hundred percent as 'all'": ("Tallyhand is invoicing", "Tallyhand is 100% solo-focused invoicing"),
        "a competitor's price and fee": ("with no per-invoice fee.", "with no per-invoice fee, unlike Ledgerly's $15 plus 1%."),
        "a customer count": (claim_1, "CLAIM-1: Used by 21,000 active freelancers. [F9]"),
        "the #1 superlative, which the judge handles": ("Tallyhand is invoicing", "Tallyhand is the #1 invoicing"),
    }
    for name, (old, new) in fine.items():
        assert unsupported(old, new) == 0, name
        assert not _critical_tripped("positioning-from-competitors", _positioning(old, new)), name
    invented = {
        "a multiplier": ("were paid a median of 9 days sooner", "get paid 2x faster"),
        "a derived saving": ("with no per-invoice fee.", "with no per-invoice fee: $3 less than Ledgerly."),
        "a derived annual price": ("$12 a month, flat", "$144 a year, flat"),
        "an invented price": ("$12 a month", "$9 a month"),
        "an invented percentage": ("Tallyhand is invoicing", "Tallyhand is 40% faster invoicing"),
    }
    for name, (old, new) in invented.items():
        assert unsupported(old, new) == 1, name
        assert _critical_tripped("positioning-from-competitors", _positioning(old, new)), name


def test_positioning_reads_the_lines_however_they_are_dressed():
    lines = CAREFUL_POSITIONING

    def facts(text):
        return task_facts.positioning_facts(text)

    labels = ("POSITIONING:", "CLAIM-1:", "CLAIM-2:", "CLAIM-3:")
    for name, text in {
        "bold labels": "\n".join(("**" + line.replace(":", ":**", 1)) if line.startswith(labels) else line
                                 for line in lines.splitlines()),
        "bullets": "\n".join("- " + line if line.startswith(labels) else line for line in lines.splitlines()),
        "heading": lines.replace("POSITIONING: ", "## POSITIONING: "),
        "space in the label": lines.replace("CLAIM-", "CLAIM "),
        "mixed case": lines.replace("CLAIM-", "Claim-"),
        "en dash": lines.replace("CLAIM-", "CLAIM–"),
        "round-bracket citations": lines.replace("[", "(").replace("]", ")"),
        "bare citations": lines.replace("[F5]", "F5").replace("[F3, F4]", "F3, F4").replace("[F2, F14]", "F2 and F14"),
        "fact spelled out": lines.replace("[F5]", "[Fact 5]"),
        "a range of facts": lines.replace("[F3, F4]", "[F3-F4]"),
    }.items():
        assert not _failed(_results("positioning-from-competitors", text)), name
    # A title above the real line is not the positioning sentence.
    titled = "Positioning: Tallyhand home page relaunch, 17 November\n\n" + lines
    assert not _failed(_results("positioning-from-competitors", titled))
    # A dash between words is punctuation: 35 words stay 35.
    padded = lines.replace(lines.splitlines()[0], "POSITIONING: " + " ".join(["word"] * 17) + " — " + " ".join(["word"] * 18))
    assert facts(padded)["positioning_within_word_limit"] is True
    over = lines.replace(lines.splitlines()[0], "POSITIONING: " + " ".join(["word"] * 36))
    assert facts(over)["positioning_within_word_limit"] is False
    # Only the first line bearing a label is graded.
    assert facts(lines + "\nCLAIM-1: alternative at $5 a month [F9]")["positioning_unsupported_figure_count"] == 0


# ----------------------------------------------------------------------- never raising

@pytest.mark.parametrize("text", [
    "", "\x00", "POST 1: 0000-00-00 | X | a", "POST 1: 2026-02-30 | X | $", "POST 99: 2026-03-02 | X | a",
    "POST 1: 2026-03-02 | X |", "POST 1: 2026-03-02 | X | $,", "POST 1: 2026-03-02 | X | $1,,,2",
    "POST 1: ٢٠٢٦-٠٣-٠٢ | X | a", "POST 1: 2026-03-02 | Lınkedın | a", "POST 1: 2026-03-02 | İnstagram | a",
    "POST 1: 2026-03-02 | LİNKEDIN | a", "POSITIONING: [", "CLAIM-1: [F999999] 1,,2", "CLAIM-1: ٣ days [F٣]",
    "CLAIM-1: 1e5 [F1]", "CLAIM-1: $1,,2 and 1,,2% and 9x", "POSITIONING:" + " x" * 50000,
    "\n" * 5000 + "POST 1: 2026-03-02 | X | a", " " * 20000, "A1: 1,,2\nA2: ٣\nA3: .\nA4: -\nA5: 1e9999",
])
def test_no_odd_input_makes_a_check_raise(text):
    tasks = bench.load_tasks()
    for task_id in NEW_TASKS:
        facts = bench.measured_facts(tasks[task_id], text)
        bench.programmatic_results(tasks[task_id], facts)
        assert bench.judge_source_reference(tasks[task_id], text) == {}
    # A platform name that only looks like one is not a post, and not an error.
    assert task_facts.social_calendar_facts("POST 1: 2026-03-02 | Lınkedın | a")["social_post_count"] == 0
