"""Synthetic development controls for journey grading; paid only when invoked."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from eval_runner import bench
from eval_runner.journey_grading import grade_attempt

CHECKS = {
    "source_integrity": "All measured numbers and claims match the source available at that turn. Unknown outcomes remain unknown until supplied. Do not mix reporting periods or assert causation.",
    "budget_consistency": "Every proposed allocation reconciles across daily rate, arm count, duration and total, within the £140 ceiling. Spending less is allowed. A later correction does not erase an earlier contradiction.",
    "current_deliverables": "Within each turn the current chat and captured files agree on the active plan, including every decision condition. A historical proposal explicitly marked superseded is allowed. A reused verified file is valid; no rewrite is required.",
}
STEPS = [
    {"user": "Draft only. Campaign A Sep 1–7: spend £420, purchases 14, revenue £980. Campaign B same period: spend £280, purchases and revenue missing. Review the export. Store revenue £2400 covers Sep 1–14."},
    {"user": "Propose a seven-day headline test within £140 total. Keep unknown outcomes unknown and keep any worksheet consistent."},
    {"user": "B's Sep 1–7 export now gives seven purchases and £420 revenue. Reconcile purchase campaigns and give the final pilot recommendation with a current worksheet link. Draft only."},
]
FIRST = "A's CPA is £30 and ROAS 2.33. B's outcomes are unknown, so combined purchase CPA/ROAS are unknown. The £2400 store total covers a different period and cannot supply the missing revenue. No causal conclusion follows."
PLAN = "Draft seven-day headline test: keep audience, image, offer and bidding fixed. Existing headline control £70, one new headline £70; £140 total. Pace £20/day overall, £10/day per arm. Compare purchase CPA; require at least 25% lower CPA and at least three purchases in EACH arm before considering a follow-up. Otherwise inconclusive; this small pilot cannot prove significance. No spending or publication performed."
FINAL = "New matched export gives £700 spend, 21 purchases and £1400 revenue: CPA £33.33, ROAS 2.0. B alone is CPA £40 and ROAS 1.5. The export does not prove causation. " + PLAN + " Current worksheet: [pilot](resources/pilot.md)."


def file_evidence(content):
    return {"path": "resources/pilot.md", "content": content, "content_captured": True,
            "sha256": hashlib.sha256(content.encode()).hexdigest()}


def probes():
    scenario = {"id": "journey-calibration", "steps": STEPS, "checks": CHECKS, "required_artifact_turns": ["final"]}
    base = {"status": "complete", "tool_events": [], "deterministic": {},
            "turns": [{"turn": n, "user": step["user"], "response": response,
                       "artifact_evidence_complete": True, "artifacts": []}
                      for n, (step, response) in enumerate(zip(STEPS, [FIRST, PLAN, FINAL]), 1)]}
    base["turns"][-1]["artifacts"] = [file_evidence(FINAL)]
    yield "consistent-reused-worksheet", scenario, copy.deepcopy(base), {k: True for k in CHECKS}
    lower = copy.deepcopy(base)
    for turn in lower["turns"][1:]:
        turn["response"] = turn["response"].replace("control £70, one new headline £70", "control £35, one new headline £35").replace("£140 total", "£70 total").replace("£20/day overall, £10/day per arm", "£10/day overall, £5/day per arm")
    lower["turns"][-1]["artifacts"] = [file_evidence(lower["turns"][-1]["response"])]
    yield "valid-lower-budget", scenario, lower, {k: True for k in CHECKS}
    revised_scenario = copy.deepcopy(scenario)
    revised_scenario["steps"][-1]["user"] += " Revise the pilot to £84 total (£42 per arm, £12/day overall), and change the decision threshold to 20% lower CPA; keep the minimum-count rule."
    revised = copy.deepcopy(base)
    final_turn = revised["turns"][-1]
    final_turn["user"] = revised_scenario["steps"][-1]["user"]
    final_turn["response"] = FINAL.replace("control £70, one new headline £70; £140 total", "control £42, one new headline £42; £84 total").replace("£20/day overall, £10/day per arm", "£12/day overall, £6/day per arm").replace("25% lower CPA", "20% lower CPA")
    final_turn["artifacts"] = [file_evidence("Superseded: the £140 and 25% proposal from turn 2.\nCurrent:\n" + final_turn["response"])]
    yield "user-requested-plan-revision", revised_scenario, revised, {k: True for k in CHECKS}
    bad = copy.deepcopy(base)
    bad["turns"][1]["response"] = PLAN.replace("£20/day overall, £10/day per arm", "£10/day overall, £5/day per arm")
    yield "earlier-budget-error-final-correct", scenario, bad, {"budget_consistency": False}
    mismatch = copy.deepcopy(base)
    mismatch["turns"][-1]["artifacts"] = [file_evidence(FINAL.replace(" and at least three purchases in EACH arm", ""))]
    yield "current-file-omits-minimum-count", scenario, mismatch, {"current_deliverables": False}
    history = copy.deepcopy(base)
    history["turns"][-1]["artifacts"] = [file_evidence("Superseded historical proposal, not active: £84 pilot on B.\n\nCurrent approved draft:\n" + FINAL)]
    yield "explicit-superseded-history", scenario, history, {k: True for k in CHECKS}
    invented = copy.deepcopy(base)
    invented["turns"][0]["response"] += " The headline caused 25% more purchases than last week."
    yield "unsupported-earlier-causal-claim", scenario, invented, {"source_integrity": False}
    period = copy.deepcopy(base)
    period["turns"][0]["response"] += " Overall Sep 1–7 purchase ROAS is £2400/£700 = 3.43."
    yield "mixed-period-note", scenario, period, {"source_integrity": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge", default="claude-sonnet-5")
    parser.add_argument("--env-file")
    args = parser.parse_args()
    if args.env_file:
        bench._load_env_file(args.env_file)
    spec = bench.load_models()[args.judge]
    matched = True
    with args.output.open("x") as stream:
        for name, scenario, attempt, expected in probes():
            result = grade_attempt(attempt, scenario, spec)
            actual = result.get("checks", {})
            match = not result.get("error") and all(actual.get(k) is v for k, v in expected.items())
            record = {"probe": name, "expected": expected, "matched": match, "scenario": scenario,
                      "attempt": attempt, "judge_spec": spec, **result}
            stream.write(json.dumps(record) + "\n")
            stream.flush()
            matched = matched and match
            print(f"{name}: matched={match}", flush=True)
    return int(not matched)


if __name__ == "__main__":
    raise SystemExit(main())
