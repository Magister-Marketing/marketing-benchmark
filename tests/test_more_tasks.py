"""The eight tasks added in November 2026: fixtures, oracles and traps.

Three things are pinned for every task. The committed fixtures are exactly
what `scripts/gen_more_tasks.py` generates. Every banded target in a task file
equals a figure recomputed here from the committed fixture, by code that does
not share the generator's solver. And a careful answer passes every
programmatic criterion while the careless one the task is built to catch
fails the criterion meant to catch it.
"""
import collections
import csv
import datetime as dt
import importlib.util
import io
import re
import statistics
from decimal import Decimal

import pytest

from eval_runner import bench, task_facts

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
FIXTURES = bench.REPO_ROOT / "eval_runner" / "fixtures"


def _generator():
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
        and "near" in criterion["programmatic"]
        and criterion["programmatic"]["fact"].startswith("answer_q")
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


def test_new_tasks_load_with_their_splits_and_an_oracle_backed_critical():
    tasks = bench.load_tasks()
    assert {task_id: tasks[task_id]["split"] for task_id in NEW_TASKS} == NEW_TASKS
    for task_id in NEW_TASKS:
        critical = bench.critical_criterion_ids(tasks[task_id])
        assert len(critical) == 1, task_id
        assert bench.oracle_rules(tasks[task_id])[next(iter(critical))], task_id
        # Every task supports the direct arms: no harness-only delivery.
        assert bench.task_supports_harness(tasks[task_id], bench.HARNESS_ID)
        assert all((bench.REPO_ROOT / path).is_file() for path in tasks[task_id]["fixtures"])


def test_committed_fixtures_and_targets_are_the_generators_output():
    assert _generator().check() == []


def test_an_empty_response_earns_nothing_but_guards():
    """Absence checks are guards the scorer excludes; nothing else is free."""
    tasks = bench.load_tasks()
    for task_id in NEW_TASKS:
        free = bench.free_credit_scores(tasks[task_id])
        assert all(criterion_id not in free for criterion_id in _targets(tasks[task_id])), task_id
        assert "answer_block_complete" not in free
    assert set(bench.free_credit_scores(tasks["social-calendar-limits"])) == {
        "spacing_rules", "hashtag_rules", "embargo_literal", "no_booking_link_after_close",
        "price_note_present", "banned_words_absent",
    }
    assert set(bench.free_credit_scores(tasks["positioning-from-competitors"])) == {"claims_cited"}


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
    return rows, target, [len(ranking), len(by_topic[target]), volumes[target], max(by_topic[target])], volumes


def test_seo_content_brief_oracle_and_trap():
    task = bench.load_tasks()["seo-content-brief"]
    rows, target, answers, volumes = _seo_answers()
    assert target == "cold brew tea"
    assert list(_targets(task).values()) == answers == [6, 7, 10290, 3600]
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
    careless = _answer_block([6, len(green), raw["green tea"], int(head["monthly_searches"])])
    assert {"q3_topic_volume", "q4_primary_volume"} <= _zeroed(_results("seo-content-brief", careless))
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
    # and duplicate titles on pages that are deliberately kept out of the index.
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


def test_search_terms_negatives_oracle_and_trap():
    task = bench.load_tasks()["search-terms-negatives"]
    rows, answers, irrelevant, promote = _search_answers()
    assert list(_targets(task).values()) == answers
    assert answers[1:] == [5, 1636.9, 30]
    # Irrelevance is unambiguous: every such term names something the facts
    # sheet rules out, none of them converted, and no other term does.
    assert len(irrelevant) == 16 and all(row["conversions"] == "0" for row in irrelevant)
    facts = (FIXTURES / "search-terms/business_facts.md").read_text().lower()
    for word in ("repair", "restring", "curtains", "drapes", "shutters", "wholesale", "trade", "careers", "kits"):
        assert word in facts
    assert sorted(row["search_term"] for row in promote) == [
        "cheap blackout blinds", "day night blinds made to measure", "free blind samples",
        "roman blinds for bay window", "wooden venetian blinds 2 inch",
    ]
    by_term = {row["search_term"]: row for row in rows}
    # The traps: brand searches that fail a naive rule, and two near misses.
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
    assert {"q1_mailable", "q2_lapsed"} <= _zeroed(_results("lifecycle-reengagement", careless))
    policy = (FIXTURES / "lifecycle/email_policy.md").read_text()
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
    answers = [round(rate_control, 2), round(rate_variant, 2), round((rate_variant / rate_control - 1) * 100, 1),
               round(chi, 1), round(p_value("signups"), 3)]
    return totals, answers, p_value("paid_conversions")


def test_ab_test_readout_oracle_and_trap():
    task = bench.load_tasks()["ab-test-readout"]
    totals, answers, secondary_p = _ab_answers()
    assert list(_targets(task).values()) == pytest.approx(answers)
    assert answers == [6.0, 6.4, 6.6, 90.7, 0.209]
    control, variant = totals["control"], totals["variant_b"]
    assert (control["visitors"], variant["visitors"]) == (12480, 11020)
    # The traps: read early, a split no 50/50 assignment produces, the gap on
    # mobile only, and a secondary metric that just clears 5%.
    assert max(control["visitors"], variant["visitors"]) < 18000
    assert (totals["control", "mobile"]["visitors"], totals["variant_b", "mobile"]["visitors"]) == (6900, 5400)
    assert (totals["control", "desktop"]["visitors"], totals["variant_b", "desktop"]["visitors"]) == (5580, 5620)
    assert answers[4] > 0.05 > secondary_p > 0.04
    plan = (FIXTURES / "ab-test/test_plan.md").read_text()
    assert "18,000 visitors per variant" in plan and "50/50" in plan and "not a decision metric" in plan
    assert not _failed(_results("ab-test-readout", _answer_block(
        [f"{answers[0]:.2f}%", f"{answers[1]:.2f}%", f"{answers[2]}%", answers[3], answers[4]])))
    # Careless: the lift in percentage points and the secondary metric's p-value.
    careless = _answer_block(["6.00%", "6.40%", "0.4%", answers[3], round(secondary_p, 3)])
    assert {"q3_relative_lift", "q5_p_value"} <= _zeroed(_results("ab-test-readout", careless))


# ------------------------------------------------------------- monthly-report-reconcile

def _monthly_answers():
    ads = _table("monthly-report/ads_platforms.csv")
    events = _table("monthly-report/analytics_purchases.csv")
    orders = _table("monthly-report/order_system.csv")
    spend = sum(Decimal(row["spend_usd"]) for row in ads)
    real = [row for row in orders
            if dt.date.fromisoformat(row["order_date"]).month == 5 and row["status"] not in {"cancelled", "test"}]
    net = sum(Decimal(row["gross_usd"]) - Decimal(row["refund_usd"]) for row in real)
    seen = collections.Counter(row["order_id"] for row in events)
    answers = [float(spend), len(real), float(net), sum(count - 1 for count in seen.values()),
               round(float(net / spend), 2), sum(int(row["platform_conversions"]) for row in ads)]
    return ads, events, orders, answers


def test_monthly_report_reconcile_oracle_and_trap():
    task = bench.load_tasks()["monthly-report-reconcile"]
    ads, events, orders, answers = _monthly_answers()
    assert list(_targets(task).values()) == answers
    assert answers[1] == 282 and answers[3] == 39
    statuses = collections.Counter(row["status"] for row in orders)
    assert (statuses["cancelled"], statuses["test"], statuses["refunded"], statuses["partially_refunded"]) == (9, 6, 12, 8)
    assert sum(row["order_date"].startswith("2026-06") for row in orders) == 3
    # The traps: the platforms claim far more conversions than there were
    # orders, and analytics revenue overstates what was kept.
    assert answers[5] > 1.4 * answers[1]
    analytics_revenue = float(sum(Decimal(row["revenue_usd"]) for row in events))
    assert analytics_revenue > 1.05 * answers[2]
    assert not _failed(_results("monthly-report-reconcile", _answer_block(
        [f"${answers[0]:,.2f}", answers[1], f"${answers[2]:,.2f}", answers[3], answers[4], answers[5]])))
    careless = _answer_block([f"${answers[0]:,.2f}", len(orders), f"${analytics_revenue:,.2f}", answers[3],
                              round(analytics_revenue / answers[0], 2), answers[5]])
    assert {"q2_real_orders", "q3_net_revenue", "q5_blended_roas"} <= _zeroed(
        _results("monthly-report-reconcile", careless))


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


def _calendar(**replacements: str) -> str:
    lines = CAREFUL_CALENDAR.splitlines()
    for number, line in replacements.items():
        index = next(i for i, text in enumerate(lines) if text.startswith(f"POST {number[1:]}:"))
        lines[index] = line
    return "\n".join(lines)


def test_social_calendar_constants_match_the_brief():
    brief = (FIXTURES / "social-calendar/campaign_brief.md").read_text()
    assert "X 280, LinkedIn 600, Instagram 400" in brief
    assert "X at most 2, LinkedIn at most 3, Instagram at most 5" in brief
    assert "from 2 March to 15 March 2026 inclusive" in brief
    assert "opens Monday 9 March 2026" in brief and "closes Friday 13 March 2026" in brief
    assert "#TuneUpWeek" in brief and task_facts.SOCIAL_BOOKING_LINK in brief
    assert f'"{task_facts.SOCIAL_PRICE_NOTE}"' in brief
    assert "guaranteed, cheapest, best, #1" in brief
    assert all(f"${int(amount)}" in brief for amount in task_facts.SOCIAL_ALLOWED_DOLLARS)
    assert [dt.date(2026, 3, day).weekday() >= 5 for day in (7, 8, 14, 15)] == [True] * 4
    assert task_facts.SOCIAL_WINDOW[0].weekday() == 0  # 2 March 2026 is a Monday, as the brief says of the 9th and 16th


def test_social_calendar_careful_answer_passes_and_each_rule_is_caught():
    assert not _failed(_results("social-calendar-limits", CAREFUL_CALENDAR))
    # Markdown dressing and a restated post do not change the graded posts.
    dressed = CAREFUL_CALENDAR.replace("POST 1: ", "- **POST 1:** ") + "\nPOST 1: 2026-03-20 | X | $5 restated"
    assert "all_posts_present" not in _failed(_results("social-calendar-limits", dressed))

    def failed(**replacements):
        return _failed(_results("social-calendar-limits", _calendar(**replacements)))

    # The date traps: the price and the link before booking opens; the link after it closes.
    assert failed(p4="POST 4: 2026-03-06 | X | Tune-ups are $79 during Spring Tune-Up Week. Parts extra. #TuneUpWeek") == {"embargo_literal"}
    assert failed(p1="POST 1: 2026-03-02 | X | Spring Tune-Up Week is coming: marlowcycle.example/tune-up #TuneUpWeek") == {"embargo_literal"}
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
    assert "all_posts_present" in failed(p7="Booking is open on Instagram too.")


def test_social_calendar_invented_price_trips_the_critical_and_silence_does_not():
    task = bench.load_tasks()["social-calendar-limits"]
    rules = bench.oracle_rules(task)
    assert rules == {"no_invented_facts": ["prices_exact"]}

    def critical_after_oracle(response):
        programmatic = list(bench.programmatic_results(task, bench.measured_facts(task, response)).values())
        judged = [{"id": "no_invented_facts", "pass": True, "score": 1.0, "evidence": "judge saw nothing"}]
        return next(item for item in bench.apply_oracle_overrides(programmatic + judged, rules)
                    if item["id"] == "no_invented_facts")

    invented = _calendar(p5="POST 5: 2026-03-09 | X | Booking is open: $69 tune-ups. marlowcycle.example/tune-up #TuneUpWeek")
    assert critical_after_oracle(invented)["oracle_failed"] is True
    assert critical_after_oracle(CAREFUL_CALENDAR)["pass"] is True
    # A reply with no calendar priced nothing: absence, not invention.
    assert critical_after_oracle("I cannot write this calendar; the brief's price is $50?")["pass"] is True
    assert bench.measured_facts(task, "")["social_wrong_dollar_amount_count"] is None


# ---------------------------------------------------------- positioning-from-competitors

CAREFUL_POSITIONING = """\
POSITIONING: For solo freelancers who want to be paid on time, Tallyhand is invoicing and payment-reminder software with one flat price and no per-invoice fee.
CLAIM-1: $12 a month, flat, with no per-invoice fee. [F5]
CLAIM-2: Customers who turned reminders on were paid a median of 9 days sooner than in their own previous quarter. [F3, F4]
CLAIM-3: A median of 4 minutes from sign-up to a first invoice in onboarding tests, and a 30-day trial with no card. [F2, F14]

What I did not use: "fastest", "#1", "most trusted", "2x faster", "bank-grade security" and "cheapest".
"""


def test_positioning_constants_match_the_sources():
    generator = _generator()
    sheet = (FIXTURES / "positioning/product_fact_sheet.md").read_text()
    competitors = (FIXTURES / "positioning/competitor_pages.md").read_text()
    assert generator.source_numbers(sheet, competitors) == set(task_facts.POSITIONING_SOURCE_NUMBERS)
    assert set(re.findall(r"(?m)^- (F\d+)\.", sheet)) == set(task_facts.POSITIONING_FACT_IDS)
    # The traps the founder's note sets: each request is unsupported by the sheet.
    note = (FIXTURES / "positioning/founder_note.md").read_text()
    for request in ("fastest", "#1", "most trusted", "2x faster", "bank-grade", "cheapest"):
        assert request in note
    assert "ranked 2nd of 11" in sheet and "Type II audit is in progress and must not be claimed" in sheet
    assert "Free plan" in competitors  # so "cheapest" cannot be said
    assert competitors.lower().count("reminders") == 3  # every competitor has them


def test_positioning_careful_answer_passes_and_each_rule_is_caught():
    assert not _failed(_results("positioning-from-competitors", CAREFUL_POSITIONING))

    def failed(old, new):
        assert old in CAREFUL_POSITIONING
        return _failed(_results("positioning-from-competitors", CAREFUL_POSITIONING.replace(old, new)))

    assert failed("[F5]", "") == {"claims_cited"}
    assert failed("[F5]", "[F5, F15]") == {"claims_cited"}
    assert failed("$12 a month", "$10 a month") == {"figures_from_sources"}
    assert failed("9 days sooner", "9 days sooner, trusted by 50,000 freelancers") == {"figures_from_sources"}
    assert failed("CLAIM-3: A median", "A median") == {"all_lines_present", "claims_cited"}
    long_line = "POSITIONING: " + "Tallyhand is invoicing software for solo freelancers " * 6
    assert failed(CAREFUL_POSITIONING.splitlines()[0], long_line) == {"positioning_length"}
    # A fact id is a citation, never a figure; figures in the note to the founder are not graded lines.
    facts = task_facts.positioning_facts(CAREFUL_POSITIONING + "\nWe could also say 99.9% uptime if we had it.")
    assert facts["positioning_unsupported_figure_count"] == 0
    assert task_facts.positioning_facts("No positioning written.")["positioning_unsupported_figure_count"] is None


def test_positioning_invented_figure_trips_the_critical():
    task = bench.load_tasks()["positioning-from-competitors"]
    rules = bench.oracle_rules(task)
    assert rules == {"no_invented_facts": ["figures_from_sources"]}
    response = CAREFUL_POSITIONING.replace("9 days sooner", "17 days sooner")
    programmatic = list(bench.programmatic_results(task, bench.measured_facts(task, response)).values())
    judged = [{"id": "no_invented_facts", "pass": True, "score": 1.0, "evidence": "judge saw nothing"}]
    critical = next(item for item in bench.apply_oracle_overrides(programmatic + judged, rules)
                    if item["id"] == "no_invented_facts")
    assert critical["oracle_failed"] is True and critical["oracle_zero_ids"] == ["figures_from_sources"]
