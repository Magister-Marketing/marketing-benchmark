# Quillfeather Coffee Roasters: experimentation rules

These rules decide which proposed tests run in the next testing calendar, when each one starts, and which are rejected. They apply to every test in `test_backlog.csv`.

## Sizing a test
- Every test is an A/B test: control and one variant, each shown to half of the page's users. A running test takes all of its page's traffic.
- p1 is the test's baseline rate (`baseline_rate_pct` ÷ 100). p2 is the rate the expected lift would give. A lift whose `lift_unit` is `relative %` multiplies the baseline: p2 = p1 × (1 + `expected_lift` ÷ 100). A lift whose `lift_unit` is `percentage points` adds to it: p2 = p1 + `expected_lift` ÷ 100.
- Sample size per variant: n = (1.96 + 0.84)² × (p1 × (1 − p1) + p2 × (1 − p2)) ÷ (p2 − p1)², rounded up to the next whole user. 1.96 is the z-value of a two-sided 5% significance level and 0.84 the z-value of 80% power.
- A page's weekly users are the mean of its 8 weeks in `traffic_by_page.csv`. A page measured in sessions (`unit` is `sessions`) has 0.8 users per session: its weekly users are 0.8 × the mean of its weekly sessions.
- Weeks needed = 2 × n ÷ the page's weekly users, rounded up to a whole week.

## Limits
- A test that needs more than 4 weeks is rejected.
- One test at a time on each page. Tests on different pages may run in the same weeks.
- The calendar runs from week 1 to week 10. Week 5 is the spring-sale code freeze: no test may be running in week 5. A test runs whole, consecutive weeks and must end by week 10.

## Priority and the calendar
- A test's priority is its page's weekly users × (p2 − p1): the extra conversions a week its expected lift would bring. Higher priority goes first; a tie goes to the lower test number.
- Take the tests that are not rejected in priority order. Give each one the earliest start week at which every week it runs is free of the tests already placed on its page, none of its weeks is week 5, and it ends by week 10. A test that cannot be placed is rejected.
