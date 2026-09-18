"""Small, explicit judge probes for the rubric-v3 corrections (paid CLI only)."""
import argparse
import json
from pathlib import Path

from eval_runner import bench, providers

PROBES = [
    ("invented-competitor-dimensions", "ad-creatives", "no_invented_proof", False,
     "Audience insight: A standard desk lamp takes a 6-to-8-inch footprint. Visual direction: show the Arc Clip Lamp freeing that space. CTA: Explore the Arc Clip Lamp."),
    ("creative-staging-is-not-proof", "ad-creatives", "no_invented_proof", True,
     "Visual direction: photograph the Arc Clip Lamp on a desk beside a notebook and a cup, with a person settling in to read. Test hypothesis: compared with the product-only control, this scene may lift click-through rate; measure it in the test. CTA: Explore the Arc Clip Lamp."),
    ("invalid-denominator-in-note", "ad-performance-analysis", "partial_metric_denominators", False,
     "Complete rows: spend $750, seven purchases, revenue $476, CPA $107.14, ROAS 0.635. Note: nominal overall CPA is $142.86 and nominal ROAS is 0.476 using the full $1,000 spend."),
    ("explicitly-rejected-denominator", "ad-performance-analysis", "partial_metric_denominators", True,
     "Matched rows only: spend $750, seven purchases, revenue $476, CPA $107.14, ROAS 0.635. We cannot report combined performance. Dividing the full $1,000 by seven ($142.86), or $476 by $1,000 (0.476), would be invalid because one row has no outcomes. These are rejected calculations, not performance estimates."),
    ("valid-pinterest-finding", "tracking-audit", "no_false_positives", True,
     "organic-pinterest has utm_campaign=2026q3-boards, which lacks the third <goal> component required by <year>q<quarter>-<line>-<goal>. organic-instagram uses a source absent from the allowed source list. The google-brand, begin_checkout, tiktok-prospecting, tiktok-retargeting, pinterest-prospecting, affiliate, and ca-UTM examples are clean."),
    ("false-positive-clean-row", "tracking-audit", "no_false_positives", False,
     "The correctly tagged pinterest-prospecting link is defective merely because it uses pinterest as its source. Fix every Pinterest link."),
    ("valid-three-arm-one-factor", "ad-performance-analysis", "bounded_test_decision", True,
     "Run a seven-day $300 test: $100 existing headline control, $100 headline A, $100 headline B. Keep audience, image, offer, landing page, placement and optimization fixed. Primary KPI is purchase CPA. Adopt a variant only if it lowers CPA by at least 15% vs control with at least 20 purchases per arm; otherwise call this inconclusive and keep the control. The single changed factor is headline."),
    ("unbounded-test", "ad-performance-analysis", "bounded_test_decision", False,
     "Try new images, audiences and copy next week. Pick whichever looks best at 95% significance."),
]


def run_probe(probe, judge_spec, generate=providers.generate):
    name, task_id, criterion_id, expected, response = probe
    task = bench.load_tasks()[task_id]
    criteria = [(section, c) for section in bench.RUBRIC_SECTIONS for c in task["rubric"][section] if c["id"] == criterion_id]
    if len(criteria) != 1:
        raise ValueError("calibration criterion missing or duplicated")
    prompt = bench.build_judge_prompt(task, response, {}, criteria=criteria)
    generated = generate(judge_spec["model"], prompt, 2048, settings=bench._candidate_settings(judge_spec))
    verdict = bench.parse_judge_json(generated["text"])
    if [c["id"] for c in verdict["criteria"]] != [criterion_id]:
        raise ValueError("calibration judge returned wrong criteria")
    return {"probe": name, "task_id": task_id, "rubric_version": task["rubric_version"],
            "expected": expected, "actual": verdict["criteria"][0]["pass"],
            "matched": verdict["criteria"][0]["pass"] == expected, "verdict": verdict,
            "cost_estimate_usd": bench.attempt_cost_usd(generated, judge_spec)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--judge", default="claude-sonnet-5")
    args = parser.parse_args()
    if args.env_file:
        bench._load_env_file(args.env_file)
    spec = bench.load_models()[args.judge]
    passed = True
    with args.output.open("x") as stream:
        for probe in PROBES:
            result = run_probe(probe, spec)
            result["judge_model"] = args.judge
            passed = passed and result["matched"]
            stream.write(json.dumps(result) + "\n")
            stream.flush()
            print(f"{result['probe']}: matched={result['matched']}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
