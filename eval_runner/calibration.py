"""Development judge calibration: focused contrasts and whole answers (paid only)."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

from eval_runner import bench, providers

FIXTURES = Path(__file__).parent / "fixtures" / "judge-calibration"

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
     "organic-pinterest has utm_campaign=2026q3-boards, which lacks the third <goal> component required by <year>q<quarter>-<line>-<goal>. organic-instagram uses a source absent from the allowed source list. The google-brand, begin_checkout, tiktok-prospecting, pinterest-prospecting, affiliate, and ca-UTM examples are clean."),
    ("false-positive-clean-row", "tracking-audit", "no_false_positives", False,
     "The correctly tagged pinterest-prospecting link is defective merely because it uses pinterest as its source. Fix every Pinterest link."),
    ("valid-three-arm-one-factor", "ad-performance-analysis", "bounded_test_decision", True,
     "Run a seven-day $300 test: $100 existing headline control, $100 headline A, $100 headline B. Keep audience, image, offer, landing page, placement and optimization fixed. Primary KPI is purchase CPA. Adopt a variant only if it lowers CPA by at least 15% vs control with at least 20 purchases per arm; otherwise call this inconclusive and keep the control. The single changed factor is headline."),
    ("unbounded-test", "ad-performance-analysis", "bounded_test_decision", False,
     "Try new images, audiences and copy next week. Pick whichever looks best at 95% significance."),
]

# Use whole answers with the full production rubric. A judge can pass a short
# isolated probe and still miss the same violation in an otherwise good report.
FULL_PROBES = [
    ("whole-creative-unsupported-attributes", "ad-creatives", "no_invented_proof", False),
    ("whole-ledger-invented-baselines", "ads-ledger-analysis", "no_invented_data", False),
    ("whole-ledger-unreconciled-transfer", "ads-ledger-analysis", "recommendation_grounded", False),
    ("whole-headline-dropped-qualification", "headline", "grounded_claims", False),
    ("whole-tracking-false-clean-bill", "tracking-audit", "clean_findings_supported", False),
    ("whole-tracking-unsupported-causes", "tracking-audit", "causal_claims_supported", False),
    ("whole-tracking-purchase-priority", "tracking-audit", "impact_prioritized", False),
    ("whole-performance-wrong-account-cpa", "ad-performance-analysis", "evidence_shown", False),
    ("whole-performance-causal-certainty", "ad-performance-analysis", "cautious_conclusions", False),
]


def probes():
    yield from PROBES
    for name, task, criterion, expected in FULL_PROBES:
        yield name, task, criterion, expected, (FIXTURES / f"{task}-errors.md").read_text()
    for name, task, criterion in (
        ("attribution-budget", "attribution-sensitivity", "conditional_recommendation"),
        ("email-battery", "email-flow-repair", "battery_corrected"),
        ("activation-definition", "marketing-plan", "activation_anchored"),
        ("capi-hashes", "shopify-meta-capi", "pii_hashing"),
    ):
        for kind, expected in (("errors", False), ("supported", True)):
            yield (f"whole-{name}-{kind}", task, criterion, expected,
                   (FIXTURES / f"{task}-{kind}.md").read_text())
    for name, task, criterion in (
        ("landing-page-clarity", "landing-page", "conversion_clarity"),
        ("landing-page-repair-credential", "landing-page-repair", "credential_removed"),
    ):
        for kind, expected in (("errors", False), ("supported", True)):
            yield (f"whole-{name}-{kind}", task, criterion, expected,
                   (FIXTURES / f"{name}-{kind}.md").read_text())
    capi = (FIXTURES / "shopify-meta-capi-errors.md").read_text()
    anchor = "#### Processing Window and Data Fusion"
    if capi.count(anchor) != 1:
        raise ValueError("CAPI stability contrast anchor missing or ambiguous")
    for kind, expected, policy in (
        ("supported", True, "read the originally stored identifier instead of creating another one. "
         "Use it unchanged in both browser eventID and server event_id."),
        ("errors", False, "append a fresh UUID suffix to the original identifier before sending "
         "the server event. The browser keeps its original eventID."),
    ):
        paragraph = ("For every subsequent delivery of the same commerce event—including duplicate "
                     "webhook delivery or changes to other order fields—" + policy)
        response = capi.replace(anchor, paragraph + "\n\n" + anchor)
        yield (f"whole-capi-delivery-identity-{kind}", "shopify-meta-capi",
               "event_id_retry_stability", expected, response)
    headline = (FIXTURES / "headline-supported.md").read_text()
    yield "whole-headline-qualified", "headline", "grounded_claims", True, headline
    creative = (FIXTURES / "ad-creatives-supported.md").read_text()
    yield "whole-creative-supported-attributes", "ad-creatives", "no_invented_proof", True, creative
    yield ("conditional-budget-increase", "ads-ledger-analysis", "recommendation_grounded", True,
           "The final-week observed rt-lookalike spend is $522.86, or $74.69/day. "
           "Do not assume that is its configured budget. If the owner separately approves $250/day of NEW funding, "
           "pilot $125/day each into rt-cart and rt-visitors; their full-period net ROAS is 7.23 and 5.64. "
           "Without new funding, retain current allocations while checking refund causes; the export does not prove a cause or profitable capacity.")
    yield ("scoped-clean-parameter", "tracking-audit", "clean_findings_supported", True,
           "Checked clean: organic-pinterest's utm_source=pinterest is allowed. Its overall link is NOT compliant: "
           "2026q3-boards lacks the required third campaign component. Organic-instagram's source is not on the allowed list. "
           "The google-brand link conforms to the documented UTM standard.")
    yield ("funded-reallocation-is-one-move", "ad-performance-analysis", "prioritized_action", True,
           "The primary move is to shift $400/week into Small-Space Interest: take $250/week from Launch "
           "and $150/week from Retargeting. Hold Broad unchanged while preparing the controlled test. "
           "The cuts fund the increase exactly; these are the components of one reallocation.")
    yield ("qualitative-rebuild-is-not-double-spend", "ads-ledger-analysis", "recommendation_grounded", True,
           "Primary move: pause prospecting-broad, which spent $1,873.93 in the final week with no conversions, "
           "and propose reallocating that amount to rt-cart and bs-exact (full-window net ROAS 7.23 and 5.05), "
           "subject to verifying capacity rather than assuming returns scale. Also prepare fresh creative concepts "
           "for a future prospecting rebuild. That qualitative work is not a second specified media allocation; "
           "the later launch budget has not been set. These are review proposals, not executed changes.")
    yield ("possible-vendor-check-is-not-a-diagnosis", "tracking-audit", "causal_claims_supported", True,
           "The newsletter URLs violate the HTTPS standard. Investigate server/CDN redirect handling "
           "(for example Cloudflare if that is in use) and trace whether query strings survive. "
           "The actual infrastructure and redirect behavior are not supplied; this is a check to perform, "
           "not a proven explanation of the Direct traffic.")


def prepare_probe(probe):
    _name, task_id, criterion_id, _expected, response = probe
    task = bench.load_tasks()[task_id]
    facts = bench.measured_facts(task, response)
    measured_ids = bench.programmatic_results(task, facts)
    criteria = [(section, c) for section in bench.RUBRIC_SECTIONS
                for c in task["rubric"][section] if c["id"] not in measured_ids]
    if sum(c["id"] == criterion_id for _, c in criteria) != 1:
        raise ValueError("calibration criterion missing or duplicated")
    prompt = bench.build_judge_prompt(task, response, facts, criteria=criteria)
    return task, prompt, criteria


def run_probe(probe, judge_spec, generate=None, *, prepared=None):
    name, task_id, criterion_id, expected, response = probe
    task, prompt, criteria = prepared or prepare_probe(probe)
    generate = generate or providers.generate
    record = {"probe": name, "task_id": task_id, "rubric_version": task["rubric_version"],
            "rubric_sha256": bench._rubric_sha256(task),
            "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
            "judge_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "judge_protocol_version": bench.JUDGE_PROTOCOL_VERSION,
            "criterion_id": criterion_id,
            "expected": expected, "actual": None, "matched": False,
            "judge_calls": 1, "cost_estimate_usd": None, "cost_unknown": True}
    try:
        generated = generate(judge_spec["model"], prompt, bench.MAX_OUTPUT_TOKENS,
                             settings=bench._candidate_settings(judge_spec))
        record["input_tokens"] = generated.get("input_tokens")
        record["output_tokens"] = generated.get("output_tokens")
        record["cost_estimate_usd"] = bench.attempt_cost_usd(generated, judge_spec)
        record["cost_unknown"] = record["cost_estimate_usd"] is None
        verdict = bench.parse_judge_json(generated["text"])
        if {c["id"] for c in verdict["criteria"]} != {c["id"] for _, c in criteria}:
            raise ValueError("calibration judge returned wrong criteria")
        if verdict.get("self_report") not in bench.SELF_REPORTS:
            raise ValueError("judge omitted self_report")
        actual = next(c["pass"] for c in verdict["criteria"] if c["id"] == criterion_id)
        record.update(actual=actual, matched=actual == expected, verdict=verdict)
    except Exception as exc:
        # Retain usage even if parsing fails; let other paid groups complete and
        # persist. Provider failures without usage remain explicitly unknown.
        record["error"] = type(exc).__name__
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--judge", default="claude-sonnet-5")
    parser.add_argument("--probes", help="comma-separated names for a bounded calibration rerun")
    args = parser.parse_args()
    if args.env_file:
        bench._load_env_file(args.env_file)
    spec = bench.load_models()[args.judge]
    passed = True
    groups = {}
    selected = list(probes())
    if args.probes:
        names = set(args.probes.split(","))
        unknown = names - {p[0] for p in selected}
        if unknown:
            parser.error("unknown probes: " + ", ".join(sorted(unknown)))
        selected = [p for p in selected if p[0] in names]
    for probe in selected:
        groups.setdefault((probe[1], probe[4]), []).append(probe)
    # No paid calls until every selected source and criterion has been validated.
    prepared = {probe[0]: prepare_probe(probe) for probe in selected}

    def run_group(group):
        first = run_probe(group[0], spec, prepared=prepared[group[0][0]])
        results = [first]
        actuals = {c["id"]: c["pass"] for c in first.get("verdict", {}).get("criteria", [])}
        for name, task, criterion, expected, _response in group[1:]:
            results.append({**first, "probe": name, "task_id": task,
                            "criterion_id": criterion, "expected": expected,
                            "actual": actuals.get(criterion),
                            "matched": criterion in actuals and actuals[criterion] == expected,
                            "judgment_reused_from": first["probe"], "judge_calls": 0,
                            "cost_estimate_usd": 0})
        return results

    with args.output.open("x") as stream:
        with concurrent.futures.ThreadPoolExecutor(max_workers=bench.RUN_CONCURRENCY) as pool:
            futures = [pool.submit(run_group, group) for group in groups.values()]
            for future in concurrent.futures.as_completed(futures):
                for result in future.result():
                    result["judge_model"] = args.judge
                    passed = passed and result["matched"]
                    stream.write(json.dumps(result) + "\n")
                    stream.flush()
                    print(f"{result['probe']}: matched={result['matched']}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
