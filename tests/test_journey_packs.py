import copy
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pytest

from eval_runner.journey_packs import DEFAULT_PACK, load_pack
from eval_runner.journeys import SCENARIOS, run_journey

HOLDOUT = DEFAULT_PACK.with_name("holdout.json")


def fixture(scenario, step=0):
    return json.loads(re.search(r"```json\n(.*?)\n```", scenario["steps"][step]["user"], re.S)[1])


def days(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def test_default_loader_is_development_only_and_preserves_legacy_scenarios():
    before = copy.deepcopy(SCENARIOS)
    development = load_pack()
    assert len(development) == 2
    assert all(s["id"].endswith("-dev") for s in development)
    with pytest.raises(ValueError, match="holdout loading requires"):
        load_pack(HOLDOUT)
    holdout = load_pack(HOLDOUT, allow_holdout=True)
    assert len(holdout) >= 3
    assert not {s["id"] for s in development} & {s["id"] for s in holdout}
    assert SCENARIOS == before
    assert not {s["id"] for s in development + holdout} & {s["id"] for s in SCENARIOS}


def test_all_packs_use_existing_controller_without_exposing_checks():
    # Stub responses are an offline transport compatibility check, not candidate
    # generations or quality verdicts; holdout performance remains unmeasured.
    for scenario in load_pack() + load_pack(HOLDOUT, allow_holdout=True):
        visible = []

        def respond(user, world):
            visible.append(user)
            assert not world.tools()
            return {"response": "Offline stub: no model invoked."}

        result = run_journey(scenario, respond)
        assert result["status"] == "complete"
        assert visible == [step["user"] for step in scenario["steps"]]
        assert all(check not in user for check in scenario["checks"].values() for user in visible)
        assert result["tool_events"] == []


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(partition="unknown"),
    lambda p: p.update(schema_version=True),
    lambda p: p["scenarios"].append(copy.deepcopy(p["scenarios"][0])),
    lambda p: p["scenarios"][0]["steps"][0].update(user=" "),
    lambda p: p["scenarios"][0]["steps"][0].update(checks={"hidden": "leak"}),
    lambda p: p["scenarios"][0].update(checks={"empty": ""}),
])
def test_invalid_or_accidentally_leaking_pack_is_rejected(tmp_path, mutation):
    data = json.loads(DEFAULT_PACK.read_text())
    mutation(data)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_pack(path)


def test_complete_period_fixture_and_rubric_arithmetic():
    scenario = load_pack()[0]
    data = fixture(scenario)
    current, previous = [r for r in data["reports"] if r["coverage"] == "complete"]
    assert days(current["start"], current["end"]) == days(previous["start"], previous["end"]) == 21
    assert date.fromisoformat(previous["end"]) + timedelta(days=1) == date.fromisoformat(current["start"])
    assert current["end"] == data["latest_complete_date"]
    assert current["clicks"] / previous["clicks"] - 1 == .5
    assert current["clicks"] / current["impressions"] == .03
    assert previous["clicks"] / previous["impressions"] == .02


def test_daily_fixture_replaces_provisional_data_without_double_counting():
    scenario = load_pack()[1]
    first, second = fixture(scenario), fixture(scenario, 1)
    assert first["rows"][0]["clicks"] + first["rows"][2]["clicks"] == 28
    # The first aggregate includes June15; the second June16 row replaces,
    # rather than supplements, yesterday's partial June16 snapshot.
    nonoverlapping = [second["rows"][i] for i in (0, 2, 3)]
    assert sum(r["clicks"] for r in nonoverlapping) == 35
    assert sum(r["spend"] for r in nonoverlapping) == 74
    assert second["rows"][2]["clicks"] / second["rows"][1]["clicks"] - 1 == pytest.approx(.6)


def test_holdout_calendar_fixture_really_crosses_leap_day_and_dst():
    data = fixture(load_pack(HOLDOUT, allow_holdout=True)[0])
    rows = data["daily_rows"]
    previous, current = rows[:14], rows[14:]
    assert len({r["date"] for r in rows}) == 28
    assert all(date.fromisoformat(b["date"]) - date.fromisoformat(a["date"]) == timedelta(days=1)
               for a, b in zip(rows, rows[1:]))
    assert "2036-02-29" in {r["date"] for r in current}
    start = datetime.fromisoformat(current[0]["date"]).replace(tzinfo=ZoneInfo(data["account_timezone"]))
    end = datetime.fromisoformat(current[-1]["date"]).replace(tzinfo=ZoneInfo(data["account_timezone"])) + timedelta(days=1)
    assert (end.timestamp() - start.timestamp()) / 3600 == 335
    assert sum(r["clicks"] for r in previous) == 140
    assert sum(r["clicks"] for r in current) == 168
    assert sum(r["impressions"] for r in previous) == 1400
    assert sum(r["impressions"] for r in current) == 2100


def test_lag_fixture_has_complete_shared_comparison_and_incomplete_decoy():
    data = fixture(load_pack(HOLDOUT, allow_holdout=True)[1])
    current_ads, previous_ads, _, current_store, previous_store, incomplete_store = data["reports"]
    assert current_ads["end"] == current_store["end"] == data["store_complete_through"]
    for report in (current_ads, previous_ads, current_store, previous_store):
        assert days(report["start"], report["end"]) == 7
    assert current_ads["spend"] / current_ads["purchases"] == 25
    assert previous_ads["spend"] / previous_ads["purchases"] == 20
    assert current_ads["attributed_revenue"] / current_ads["spend"] == previous_ads["attributed_revenue"] / previous_ads["spend"] == 2
    assert "missing, not zero" in incomplete_store["coverage"]
