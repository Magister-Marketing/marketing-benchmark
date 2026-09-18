# Usage-grounded conversation cases, version 1

This separately loaded pack measures ordinary analytical and coordination tasks:
complete reporting periods, corrections across turns, data freshness, and the
difference between connected access and permission to act. It contains **two
development cases and three holdout variants**. All five are unrun against
candidate models at authoring; there are no scores or quality claims yet.

The existing `journeys.SCENARIOS`, runner defaults, grader and historical results
are unchanged. These cases are not implicitly added to any benchmark run.

## Why these cases

Selection followed a bounded private review of 10 recent conversations across
six live paid projects, selected by recency rather than reported failure. It was
a convenience sample, not a representative estimate of user behavior: no Free
projects, some user-initiated task launches had generated briefs, and older
context was sometimes truncated. Successful follow-through and honest handling
of missing access were present alongside reporting-period confusion. Delivery
of an answer was not treated as proof of task success; silence or cancellation
was not classified as dissatisfaction.

The development cases target two supported themes: unequal comparison windows
and confusion between daily and cumulative totals. Holdout variants explore
plausible generalizations and one integration-readiness clarity issue. Leap/DST
behavior and the exact simulated capability transitions are **design
assumptions**, not claims that those specific failures were observed in users.

Every business, date, number, capability snapshot and phrase in these fixtures
is invented. No customer text, identifiers, account records, URLs or production
traces are distributed here. The private review is not a source of public test
data. The aggregate sample description motivates coverage, not prevalence or a
claim that these cases reproduce five independently established incidents.

| Partition | Case | Distinct behavior |
| --- | --- | --- |
| Development | `usage-complete-periods-dev` | Choose consecutive complete 21-day windows; distinguish measured growth from causal claims. |
| Development | `usage-daily-lifetime-dev` | Reconcile dashboard filters, replace a provisional snapshot, and retain labels on a later refresh. |
| Holdout | `usage-leap-dst-holdout` | Preserve 14 local calendar dates across leap day and a 23-hour day. |
| Holdout | `usage-lag-coverage-holdout` | Use shared complete periods while retaining differences in source coverage and attribution. |
| Holdout | `usage-integration-readiness-holdout` | Distinguish connected/readable/writable and retain plan-only approval after a capability change. |

## Calendar and evidence contracts

Each fixture explicitly defines inclusive reporting dates, reporting timezone,
current time and freshness/complete-data boundary. The local-day comparison
includes both endpoints. A completed local day can have 23 or 25 elapsed hours;
it need not be a fixed 24-hour interval. Cross-source reports must share a
compatible observation window before their totals are compared. Missing rows
are not measured zeros; provider-attributed revenue is not interchangeable with
store-wide revenue.

These are **synthetic provider contracts**, not claims that every real provider
supports an arbitrary account timezone. Real adapters must preserve their own
provider's definition:

- Google Search Console defines inclusive `startDate` and `endDate` in Pacific
  Time in its [Search Analytics query contract](https://developers.google.com/webmaster-tools/v1/searchanalytics/query).
- Google Analytics defines inclusive dates and evaluates relative dates in the
  property's reporting timezone in its [DateRange contract](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/DateRange).

Do not hardcode a universal freshness delay or silently translate the synthetic
contract into a different live-provider contract. The lag fixture supplies its
own known cutoff; a live product must establish availability from actual evidence.

Positive controls are deliberate: valid complete periods remain analyzable even
when newer data is provisional; daily and cumulative values can both be correct;
local-day comparisons remain useful across DST; a connected platform can be
readable without write permission; a newly writable platform should not be
called disconnected. Checks permit equivalent phrasing and reasonable rounding,
conditional recommendations and honestly labeled alternative analyses. They do
not require an arbitrary percentage threshold or a preferred writing style.

## Offline loading and validation

```bash
# Default loads only the two development cases; no model or vendor calls.
python3 -m eval_runner.journey_packs

# Holdout loading is refused without this explicit opt-in.
# This command validates metadata/shape, not model behavior or answer quality.
python3 -m eval_runner.journey_packs \
  eval_runner/fixtures/journeys/usage-grounded-v1/holdout.json --allow-holdout

python3 -m pytest tests/test_journey_packs.py tests/test_journeys.py -q
```

The loader returns the existing `id`, `steps`, `checks` scenario shape:

```python
from eval_runner.journey_packs import load_pack

scenarios = load_pack()  # development only
# An authorized adapter can pass each scenario to the existing run_journey.
```

The supplied fixtures are embedded in the relevant user turn, so no staging,
network connection or new simulator is required. These are conversation/reasoning
cases; without an execution simulator they cannot prove that a real integration
or approval gate prevents writes. The fixture snapshots are user-supplied
simulated evidence, not authenticated live tool receipts.

A consuming adapter must explicitly select this pack, freeze its bytes/hash and
selected scenarios in run metadata, and pass only the current step's `user` text
to the candidate. Do not send `checks` or future turns to the candidate. Existing
`run_journey` handles the ordered conversation; the existing grader can consume
the snapshotted checks. No new paid-run command or default integration is added
here. This loader does not authorize generation or spending.

## Holdout isolation and lifecycle

`development.json` and `holdout.json` are separate files. `load_pack()` defaults
to development; loading a declared holdout pack requires `allow_holdout=True`.
The validator emits IDs only and does not generate candidate answers. Offline
unit tests use a fixed stub to verify controller compatibility and inspect
fixture arithmetic, which does **not** constitute a candidate-model run.

This is protection against accidental inclusion, not secrecy or access control.
Authors, reviewers and tests can see the holdouts. They are not model-training
holdouts and are not hidden from the repository. Their intended isolation is:
no candidate outputs or holdout scores are used to tune the product before a
separately declared evaluation. Offline review of fixture correctness is allowed.

`generation_status: unrun_at_authoring` is immutable authoring provenance, not a
live assertion that no one has ever run a case. Record subsequent execution in
new run artifacts. If a case's results inform tuning, mark that consumption in
the experiment report and create fresh unseen variants for the next holdout
claim. Keep these authored versions and historical grades unchanged; rubric or
fixture corrections require a new version and explicit comparability note.
