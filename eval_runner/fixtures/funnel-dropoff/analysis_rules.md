# Bramblecote Home: checkout funnel analysis rules

## The export
- `funnel_daily.csv` has one row per day, device, browser and step. `count` is the number of sessions that reached the step that day: `cart` (viewed the cart), `shipping` (reached shipping details), `payment` (reached payment) and `order` (placed an order). A step with no sessions that day has no row, and counts as 0.
- A segment is one device and browser pair.
- Double-fired events: the release log records each time an event fired twice for every session, with the step, the browsers it hit and the days. On those days that step's rows, for those browsers, count two events per session. Halve them first, before anything else.
- Automated traffic: a segment-day (one segment on one day) is automated when fewer than 2 in 100 of its cart sessions reached shipping, counted after the halving. Leave automated segment-days out of every figure, and a segment all of whose days are automated out of the table.

## Rates
- Conversion rate = orders ÷ cart sessions, over every segment, for the days in question.
- A step's rate, for one segment = its sessions at the step ÷ its sessions at the step before it (shipping ÷ cart, payment ÷ shipping, order ÷ payment). Over several days, sum the sessions of those days first.

## Breaks
- The reference week is 2026-03-02 to 2026-03-08.
- A segment's normal range for a step is the step's rate over the reference week plus or minus 5 percentage points.
- A segment's step has broken on day D when the step's daily rate is below its normal range on day D and on every later day in the export. The break begins on the first such day.
- The store's break date is the day the earliest break begins. Before the break means the days before the store's break date; after the break means that day and every later day.

## The size of the loss
- Orders lost, for each broken segment: take its sessions at the step before its broken step, from the day its own break begins. Multiply them by the segment's rate from that step to an order over the days before its own break (its orders ÷ its sessions at that step, both summed over those days). Subtract the orders the segment recorded from the day its own break begins, and round to the nearest whole order. A segment that did not break lost no orders.
- The store's orders lost = the sum over the broken segments. Revenue lost = orders lost × $72.00, the store's average order value.

## Verdicts
- A segment is `broken` when one of its steps broke. It is `recovered` when none broke but a step's daily rate was below its normal range on at least one day. Otherwise it is `normal`.

## Suspected causes
- A suspected cause names a date, the segments it would hit and the step it would break. The data is consistent with it only when one of those segments has that step break, beginning on that date. Otherwise the data rules it out.
