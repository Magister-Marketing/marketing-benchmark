# Fennick Trailworks: Fellside collection launch, paid social build brief

Fennick Trailworks launches its new Fellside collection on paid social on
2 March 2027. This brief is the build standard for the launch account. The
build has six steps, and each one uses what the steps before it produced:
the segments chosen in step 1 become the campaigns of step 2, the ad groups
of step 2 get the ads of step 3, the URLs of step 4 and the budgets of step
5, and step 6 counts what was built. Two files come with this brief:
`audience_segments.csv` (every audience the team could target) and
`product_catalogue.csv` (every product in the range). Build exactly what the
steps produce. Names are case-sensitive.

## Step 1. Choose the audience segments

Apply these rules to `audience_segments.csv`, in this order:

1. Launch markets only: US, UK and DE. A segment in any other market is out.
2. No purchased lists: a segment whose source is `purchased` is out.
3. Consent: a `first-party` segment needs consent `opt-in`; with any other
   value it is out. A `partner` segment carries the partner's consent and
   needs nothing in our consent column.
4. Minimum size: a prospecting segment needs an est_size of at least
   50,000; a retargeting segment at least 8,000.
5. Duplicates: when two segments still in have the same market, type and
   interest, keep the one with the larger est_size; if they are the same
   size, keep the one with the lower segment_id.
6. Caps per market: each market runs at most
   2 prospecting segments and
   1 retargeting segment. If more are still
   in, keep the largest by est_size (same size: the lower segment_id).

Each segment chosen becomes one campaign.

## Step 2. Build the campaigns and ad groups

- One campaign per chosen segment, named
  `FTW_FS27_<market>_<segment_code>_<type code>`, where the type
  code is `PRO` for prospecting and
  `RTG` for retargeting. Example:
  `FTW_FS27_US_ABC_PRO`.
- In each campaign, one ad group for every product in the catalogue whose
  status is `launch`, whose category is the segment's interest, and whose
  markets include the segment's market. Nothing else gets an ad group:
  carryover and discontinued products, and products not sold in the
  campaign's market, are left out.
- Ad group name: the campaign name, an underscore, and the product's sku
  exactly as the catalogue writes it. Example:
  `FTW_FS27_US_ABC_PRO_XX-000`.

## Step 3. Write one ad per ad group

- Three fields: headline_1 (at most 30
  characters), headline_2 (at most 30) and
  description (at most 90). Spaces and
  punctuation count as characters.
- headline_1 contains the product's ad_name, word for word.
- headline_2 contains one of the product's two proof points (proof_1 or
  proof_2), word for word.
- description contains the product's price in the campaign's market with its
  currency sign, written as the catalogue gives it: $ and
  price_usd for US, £ and price_gbp for UK,
  € and price_eur for DE (for example
  £129).
- Retargeting ads only: the description also carries the returning-visitor
  code FELL10. Prospecting ads carry no code.
- Only the ad group's own product: an ad names no other product of the
  catalogue (by its ad_name or product_name), uses no other product's proof
  point, and contains no figure except those in its own product's ad_name,
  proof points and price in the campaign's market (and, in a retargeting
  ad, the code). No dates, no percentages, no other market's price.

## Step 4. Build the trafficking sheet

- One final URL per ad group.
- Landing page: `https://www.fennicktrail.example/<store>/<slug>`, where the store is
  `us` for US, `gb` for UK and `de` for
  DE, and the slug is the product's slug from the catalogue.
- Exactly four tracking parameters: `utm_source=social`,
  `utm_medium=paid`, `utm_campaign=` the campaign name in
  lower case, and `utm_content=` the ad group name in lower case.

## Step 5. Set the daily budgets

- The launch's total daily budget is $3,600, in
  US dollars for every market (the account bills in dollars), split across
  the campaigns and nothing else.
- Every campaign first gets $180.
- The rest ($3,600 less
  $180 for each campaign) is shared in proportion to
  each campaign's segment est_size, in whole dollars: each campaign gets the
  whole-dollar part of its share, and the dollars left over go one each to
  the campaigns with the largest fractional parts (a tie goes to the
  campaign whose name sorts first).
- The amounts add up to $3,600 exactly.

## Step 6. Pre-launch check

Before anything goes live, count from the files you built: the campaigns,
the ad groups, the ads carrying the returning-visitor code, the distinct
products advertised, and the total of the daily budgets.
