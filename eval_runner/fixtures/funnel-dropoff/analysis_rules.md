# Bramblecote Home: checkout funnel analysis rules

## The export
- `funnel_daily.csv` has one row per day, device, browser and step. `count` is the number of sessions that reached the step that day: `cart` (viewed the cart), `shipping` (reached shipping details), `payment` (reached payment) and `order` (placed an order). A step with no sessions that day has no row.
- A segment is one device and browser pair.
- Double-fired events: the release log records each time an event fired twice for every session, with the step, the browsers it hit and the days. On those days that step's rows, for those browsers, count two events per session. Halve them.
- Automated traffic: rows whose browser is `HeadlessChrome` come from a price-monitoring crawler. Leave them out of every figure.

## Rates
- Conversion rate = orders ÷ cart sessions, over every segment, for the days in question.
- A step's rate, for one segment = its sessions at the step ÷ its sessions at the step before it (shipping ÷ cart, payment ÷ shipping, order ÷ payment). Over several days, sum the sessions of those days first.

## Breaks
- The reference week is 2026-03-02 to 2026-03-08.
- A segment's normal range for a step is the step's rate over the reference week plus or minus 5 percentage points.
- A segment's step has broken on day D when the step's daily rate is below its normal range on day D and on every later day in the export. The break begins on the first such day.
- Before the break means the days before the day the break begins; after the break means that day and every later day.

## The size of the loss
- Orders lost: for the broken segment, take its sessions at the step before the broken step, after the break. Multiply them by the segment's rate from that step to an order before the break (its orders ÷ its sessions at that step, both summed over the days before the break). Subtract the orders the segment recorded after the break, and round to the nearest whole order.
- Revenue lost = orders lost × $72.00, the store's average order value.

## Suspected causes
- A suspected cause names a date, the segments it would hit and the step it would break. The data is consistent with it only when one of those segments has that step break, beginning on that date. Otherwise the data rules it out.
