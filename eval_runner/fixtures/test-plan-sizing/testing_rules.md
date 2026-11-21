# Quillfeather Coffee Roasters: experimentation rules, next testing calendar

These rules decide which proposed tests in `test_backlog.csv` run in the next calendar, when each starts, and which are rejected. They apply to every storefront in `sites.csv`.

## Sizing a test
- Every test is an A/B test: control and one variant. A test runs on the share of its page's users in `traffic_share_pct`, split half and half between control and the variant.
- p1 is the test's baseline rate (`baseline_rate_pct` ÷ 100). p2 is the rate the expected lift would give. A lift whose `lift_unit` is `relative %` multiplies the baseline: p2 = p1 × (1 + `expected_lift` ÷ 100). A lift whose `lift_unit` is `percentage points` adds to it: p2 = p1 + `expected_lift` ÷ 100.
- Sample size per variant: n = (1.96 + 0.84)² × (p1 × (1 − p1) + p2 × (1 − p2)) ÷ (p2 − p1)², rounded up to the next whole user. 1.96 is the z-value of a two-sided 5% significance level and 0.84 the z-value of 80% power.
- A page's weekly users are the mean of its weeks in `traffic_by_page.csv`, leaving out every week whose `note` is `tracking outage`. A site whose analytics counts sessions (`unit` is `sessions`) has the users per session given in `sites.csv`: its pages' weekly users are that figure × the mean of their weekly sessions.
- Weeks needed = 2 × n ÷ (the page's weekly users × `traffic_share_pct` ÷ 100), rounded up to a whole week.

## Limits
- A test that needs more than 4 weeks is rejected as too long.
- One test at a time on each page of a site.
- A site runs at most its `max_tests_at_once` tests in any one week.
- No test may be running in its site's `freeze_week`.
- The calendar runs from week 1 to week 12. A test runs whole, consecutive weeks and must end by week 12.

## Priority and the calendar
- A test's priority is its page's weekly users × `traffic_share_pct` ÷ 100 × (p2 − p1): the extra conversions a week its expected lift would bring. Higher priority goes first; a tie goes to the lower test number.
- Take every test not rejected as too long, from every site at once, in priority order. Give each one the earliest start week at which none of its weeks is its site's freeze week, none of its weeks overlaps a test already placed on the same page of the same site, in none of its weeks would its site be running more than `max_tests_at_once` tests (counting the tests already placed), and it ends by week 12. A test that cannot be placed has no slot and is rejected.
