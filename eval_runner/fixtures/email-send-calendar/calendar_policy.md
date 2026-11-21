# Marrowfield Garden Co.: email calendar policy

The CRM team lists the month's campaigns in `campaigns.csv`. The calendar is
built from that list by the procedure below, so two people who follow it get
the same calendar. February 2027 starts on a Monday and has 28 days.

## Who receives a campaign

The subscriber export has one row per subscriber and one column per segment:
`veg_growers`, `houseplants`, `vip`, `new_subscribers`, `lapsed_buyers`, `local`. A 1 means the subscriber is in that segment.

A campaign goes to every subscriber whose `status` is `active` and who is in
at least one of the campaign's segments. A subscriber in several of its
segments receives it once. Subscribers whose status is `unsubscribed` or
`bounced` receive nothing.

## The rules a send date must meet

1. **Blackout dates.** Nothing is sent on:
   - Monday 15 February (Presidents' Day)
   - Wednesday 24 February (email platform maintenance)
2. **Send days.** Each type of campaign goes out only on these days:
   - `newsletter`: Tuesday and Thursday
   - `promo`: Wednesday, Friday and Saturday
   - `teaser`: Monday to Friday
   - `launch`: Tuesday to Thursday
   - `event`: Monday to Wednesday
   - `survey`: Monday to Thursday
3. **Teaser before launch.** A campaign with a `depends_on` is sent at least
   3 days after the campaign it depends on: a teaser sent on the 2nd allows
   its launch on the 5th or later. If that campaign is not sent, neither is
   this one.
4. **Frequency cap.** No subscriber receives more than 3 emails in any
   7 consecutive days. Nothing sent before 1 February counts.

A campaign is never sent after its `deadline`.

## How to build the calendar

Take the campaigns in order of `priority`, 1 first. For each one:

1. Try its `requested_date`, then each following date up to its `deadline`.
2. A date is allowed when the campaign meets rules 1 to 4 on it, given the
   campaigns already on the calendar.
3. The campaign goes on the first allowed date and stays there. A campaign
   already on the calendar is never moved to make room for a later one.
4. If no date up to the deadline is allowed, the campaign is not sent.

## Reasons

When a campaign does not go out on its requested date (it moved, or it is not
sent), its reason is the first of these rules that rules out the requested
date, in this order: `blackout`, `send_day`, `dependency`, `frequency_cap`.
