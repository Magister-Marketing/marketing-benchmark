# Tracking notes for the October reconciliation (analyst handoff)

- Meta Ads Manager counts view-through conversions under its "1-day view"
  setting; GA4 never counts view-through under any setting.
- Attribution differs by construction: Meta claims a conversion on a 7-day
  click / 1-day view window against its own ads; GA4 assigns each purchase to
  one channel by last non-direct click with a 30-day lookback.
- Auto-tagging was broken on Oct 12-13; an estimated 8 Meta-referred sessions
  landed without UTMs during the outage and were classified as Direct in GA4.
- The store platform (source of truth for orders) recorded 118 completed
  purchases in the window. GA4 recorded 112 site-wide. Summing every ad
  platform's self-reported conversions (Meta plus the search and affiliate
  platforms) gives 149 claimed conversions.
- No other diagnostics are available for this window.
