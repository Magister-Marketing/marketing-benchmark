# Whole-answer factual grading

The September 18 development rerun passed short judge calibration probes but
still received false passes for unsupported product attributes and unreconciled
budget recommendations. Other checks did not cover lost product qualifications
or an audit incorrectly certifying defective items clean. High aggregate scores
therefore did not establish factual correctness.

Judge protocol 3 retains the whole-answer checks introduced in protocol 2. It checks the whole answer before deciding a universal criterion.
One correct calculation or recommendation does not validate every claim in the
response. Rubrics now cover factual claims, conditions, dates and units across
copy, visual directions, tables, notes and action plans. They continue to allow
creative staging, explicit hypotheses and conditional future budgets; these
must not be represented as observed facts or guaranteed outcomes.

For the daily ledger, deterministic reference totals are computed from the CSV
inside the **recorded generation prompt**, never from today's fixture or the
candidate's answer. The judge receives full-window, final-calendar-week and
final-28-day account/adset totals, with dates, observed daily spend, refunds and
net outcome metrics. Observed spend is not a configured budget, revenue minus
refunds is not profit, and the export does not establish causes or capacity.
Malformed, ambiguous or inconsistent daily sources are refused. These reference
totals help the evaluator check claims; they add no candidate tool or capability.

Protocol 3 also checks metric event/population/numerator/denominator definitions
explicitly. A nearby funnel stage is not interchangeable with the documented
event, and counting cohorts is not counting accounts in those cohorts.

Worked SHA-256 tables receive computed evidence: exact normalized UTF-8 values
or unambiguous trim/lowercase email examples are hashed locally. Candidate code
is never executed. The judge still interprets context: a wrong hash offered as
correct is a defect, while quoting it as a rejected example is legitimate. The
parser deliberately skips ambiguous formats and other inferred PII normalization;
no parsed examples does not mean that all hashes or payloads are correct. These
checks are evaluator evidence, not a new candidate capability or a rubric change.

Calibration includes complete synthetic reports with known errors, clean full
answers, paired attribution/email/activation/hash repairs, and contrasts for conditional proposals and narrowly scoped findings.
Each is judged with the same full rubric used in ordinary grading. Multiple
expected checks for one answer reuse one judgment and one billed call. The
examples are development regressions, not holdout evidence or a measure of
general judge reliability. Failed calibration files must be retained.

Positive contrasts also protect legitimate recommendations: funding cuts and
an increase can be one coherent reallocation; a qualitative future rebuild is
not automatically a second media-budget commitment; and proposing a conditional
vendor check does not assert that vendor's behavior is known. Numeric facts are
graded separately from causal interpretations and recommendation feasibility.

Run paid calibration manually, never in CI:

```sh
python -m eval_runner.calibration --output /tmp/factual-calibration-new.jsonl \
  --env-file "$BENCH_PROVIDER_ENV" --judge gpt-5.6-luna-high
```

The model in the example is an inexpensive calibration candidate, not a claim
that it is validated for publication. Use `--probes name1,name2` for a bounded diagnostic. Offline tests stub providers.
Record rubric and judge-protocol versions, prompt hashes, source reference
version, individual findings and costs. Partial grading refuses to mix judge
protocol versions in an existing label. For comparisons, preserve original
responses, exact prompts and judgments; create new labeled grading artifacts or
separate comparison views using identical updated rubric snapshots for both
generations. A lower score after regrading is a grading change, not a product
regression. Do not label model-assisted review as human verification.

No production deployment is required for evaluator changes. An independently
reviewed factual audit remains useful; a finite calibration set cannot prove that
the judge will catch every error in a new answer.
