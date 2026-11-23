# Source and licence of the headline pairs

`pairs_clear.jsonl` and `pairs_unpublished.jsonl` are derived from the
exploratory dataset of the Upworthy Research Archive:

Matias, J. N., Munger, K., Le Quere, M. A., & Ebersole, C. (2021). The
Upworthy Research Archive, a time series of 32,487 experiments in U.S. media.
*Scientific Data*, 8, 195. https://doi.org/10.1038/s41597-021-00934-7

The archive is published by Cornell University under a Creative Commons
Attribution 4.0 International License
(https://creativecommons.org/licenses/by/4.0/), through an agreement between
Good/Upworthy and Cornell University. Data: https://osf.io/jd64p/.

What was changed: each row here is one pair of headlines from one test, the
best and the worst by click-through rate, with the rates, their ratio and a
two-proportion p-value computed from the archive's impressions and clicks.
Whitespace in headlines is collapsed. Nothing else is altered.

Which tests qualify:

- every arm of the test shared one image, excerpt and lede, so the headline
  is the only thing that varied;
- each headline had at least 1,000 impressions;
- the gap between the two is at p < 0.001 (strict, because best against
  worst of several arms is a picked contrast);
- the test did not run between 2013-06-25 and 2014-01-10, which the
  archive's authors advise against for confirmatory use: no test from the
  archive's weeks 201325 to 201401 (its `test_week` starts on Sunday, so
  these run from 2013-06-23 to 2014-01-11), and none created in that window
  by its id's timestamp;
- for `pairs_unpublished.jsonl`, neither headline was the test's top
  performer or flagged as its winner: these are not the versions Upworthy
  went on to publish, so a model cannot score by recognising a headline that
  spread on the web.

100 pairs each, the winner on side A in exactly 50, and no test in both
files. `scripts/build_headline_pairs.py` is how they were derived; each row's
`source_test_id` is the archive's `clickability_test_id`, so any pair and its
rates can be checked against the archive.
