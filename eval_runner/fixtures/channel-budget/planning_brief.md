# Fernmoor: Q2 2027 demand budget, planning brief

From Ines Varga, Head of Demand Generation. Fernmoor sells practice-management software to
physiotherapy clinics in three regions: North America (`na`), Europe, Middle East and Africa (`emea`), Asia-Pacific (`apac`). This brief sets the rules for splitting the
demand budget for Q2 2027, the months April (`apr`), May (`may`), June (`jun`), across twelve channels in the three regions.
The files beside it:

- `channel_terms.csv`: each channel, whether it is a field channel, and whether it needs a licence.
- `cell_limits.csv`: for each channel, region and month (a "cell"), the most blocks the cell can
  take and the blocks already committed in it.
- `forecasts.csv`: the leads each block is projected to add, for every channel except syndication.
- `syndication_vendor_forecast.csv`: the syndication vendor's own forecast, in its own format.
- `q1_actuals.csv`: what each channel delivered last quarter. It is context for the regional
  teams, not a forecast, and plays no part in the split.

## The money

- **Quarter budget:** $1,400,000. Everything the plan buys comes out of it: media blocks
  and licences. The plan may not go over it. Money left over stays unspent.
- **Blocks:** media is bought in whole blocks of $10,000, each in one channel, one region
  and one month. A cell's blocks are bought in order: block 1, then block 2, and so on, up to its
  `max_blocks`.
- **Forecasts:** in `forecasts.csv`, `added_leads` is the number of qualified leads a block adds
  on top of the earlier blocks of its cell. A cell's projected leads for n blocks are the sum of
  its first n rows. `added_leads_low` and `added_leads_high` are the forecast's range for the same
  block; plan on `added_leads` alone. The syndication vendor states instead `cumulative_leads`, the cell's leads
  once the block at that spend is bought: the leads a syndication block adds are its cumulative
  figure minus the one before it.

## Licences

Three channels need a licence. A licence is charged per channel, not per region, for the months
the channel is live, and it comes out of the quarter budget. A channel is live in a month when it
buys at least one block in that month in any region; a channel that buys no block pays nothing.

| channel | licence for the quarter |
|---|---|
| webinars | $3,200 for each month it is live |
| abm | $8,000 if it is live in one month, $13,000 if live in two, $17,000 if live in all three |
| podcasts | $5,000 one-off agency setup if it is live in any month, plus $2,000 for each month it is live |

## Regional limits

Media spend only: licences are not regional.

| region | minimum media spend in the quarter | maximum media spend in the quarter | most media spend in any one month | most field blocks in any one month |
|---|---|---|---|---|
| na | $400,000 | $600,000 | $200,000 | 4 |
| emea | $340,000 | $500,000 | $170,000 | 3 |
| apac | $360,000 | $440,000 | $130,000 | 2 |

The field channels are `webinars`, `events`, `abm`. Each block of a field channel needs the regional field
marketing team, so in each month a region can buy at most the number of field blocks above, the
three field channels together.

## Commitments

`committed_blocks` in `cell_limits.csv` are already contracted: the plan must buy at least that
many blocks in the cell. They count against every limit and are paid from the quarter budget like
any other block.

## What I need

The split of the budget that projects the most leads while keeping every rule above. If two
splits project the same number of leads, take the one that costs less.

## Constraints, by name

For each of these constraints, say whether it binds in your split: `budget`, `na_min`, `emea_min`, `apac_min`, `na_max`, `emea_max`, `apac_max`, `pacing_na_apr`, `pacing_na_may`, `pacing_na_jun`, `pacing_emea_apr`, `pacing_emea_may`, `pacing_emea_jun`, `pacing_apac_apr`, `pacing_apac_may`, `pacing_apac_jun`, `field_na_apr`, `field_na_may`, `field_na_jun`, `field_emea_apr`, `field_emea_may`, `field_emea_jun`, `field_apac_apr`, `field_apac_may`, `field_apac_jun`.

- `budget` binds when less than $10,000 of the quarter budget is left unspent.
- `<region>_min` binds when the region's media spend is exactly its minimum, and `<region>_max`
  when it is exactly its maximum.
- `pacing_<region>_<month>` binds when the region's media spend in that month is exactly its
  most in any one month.
- `field_<region>_<month>` binds when the region buys exactly its most field blocks in that month.
