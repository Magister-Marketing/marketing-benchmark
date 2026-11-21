# Fernmoor: Q2 2027 demand budget, planning brief

From Ines Varga, Head of Demand Generation. Fernmoor sells practice-management
software to physiotherapy clinics. This brief sets the rules for splitting next
quarter's demand budget across our six paid channels. The two files beside it
are `channel_terms.csv` (each channel's limits and fees) and
`channel_forecasts.csv` (the leads each block of spend is projected to bring).

## The money

- **Quarter budget:** $128,000. Everything the plan buys comes out of it: media blocks
  and channel fees. The plan may not go over it. Money left over stays unspent.
- **Blocks:** spend is bought in whole blocks of $5,000. A channel's blocks are bought in
  order: block 1, then block 2, and so on.
- **Forecasts:** `added_leads` in `channel_forecasts.csv` is the number of qualified leads that
  block adds on top of the channel's earlier blocks. A channel's projected leads for n blocks are
  the sum of its first n rows. `spend_through_block_usd` is the media spend once that block is
  bought.
- **Fees:** `fee_usd_per_month` is a licence the channel needs for every month of the quarter in
  which it runs. A channel that buys any block runs for the whole quarter, so it pays three months
  of its fee. A channel that buys no block pays nothing.

## Channel terms

- `max_blocks`: the most blocks the channel can take this quarter.
- `minimum_if_used_blocks`: if the channel is used at all, it must buy at least this many blocks.
  0 means there is no minimum.
- `committed_blocks`: blocks already contracted for this quarter. The plan must buy at least this
  many, and they are paid from this quarter's budget like any other block.
- `routed_to_aes`: whether the channel's leads go to the account executives.

## Account executive capacity

Leads from the channels routed to the AEs (linkedin and webinars) ask for a demo and go to our
four account executives, who can take at most **520 new leads** this quarter in total. The
projected leads of the routed channels together may not exceed 520. Leads from the other
channels go to the self-serve trial and do not count against it.

## What I need

The split of the budget that projects the most leads while keeping every rule above. If two splits
project the same number of leads, take the one that costs less.

## Constraints, by name

For each of these constraints, say whether it binds in your split: `budget`, `ae_capacity`, `search_max`, `linkedin_max`, `webinars_max`, `syndication_min_order`, `syndication_max`, `review_sites_commitment`, `review_sites_max`, `meta_max`.

- `budget` binds when less than $5,000 of the quarter budget is left unspent.
- `ae_capacity` binds when at least one routed channel is below its maximum and, for every routed
  channel that is below its maximum, buying its next block would take the routed leads above
  520.
- `search_max`, `linkedin_max`, `webinars_max`, `syndication_max`, `review_sites_max`, `meta_max`: each binds when that channel buys exactly its `max_blocks`.
- `syndication_min_order` binds when syndication buys exactly its minimum order (4 blocks).
- `review_sites_commitment` binds when review sites buy exactly their committed blocks (2).
