# Tracking standard

## Asset ids

An asset id is `FH-<audience code>-<placement code>-<variant>`, in capitals,
joined by hyphens: `FH-RST-MF-A` is the Restaurants Meta feed ad, variant A.

| audience code | audience |
|---|---|
| `RST` | restaurants |
| `CLN` | clinics |
| `RTL` | retail |

| placement code | channel | placement | utm_content stem |
|---|---|---|---|
| `MF` | meta | feed | `feed` |
| `MS` | meta | stories | `stories` |
| `GS` | google | search | `search` |
| `LF` | linkedin | feed | `feed` |
| `EL` | email | launch | `launch` |
| `ER` | email | reminder | `reminder` |

## Final URLs

A final URL is the audience's landing page, then `?`, then these parameters
joined by `&`, in this order. Every value is lower case, words joined by
underscores, no spaces. No other parameters, and no `#` fragment.

1. `utm_source` and 2. `utm_medium`, by channel:

| channel | utm_source | utm_medium |
|---|---|---|
| meta | `meta` | `paid_social` |
| google | `google` | `cpc` |
| linkedin | `linkedin` | `paid_social` |
| email | `newsletter` | `email` |

3. `utm_campaign`: `shifts_<audience code in lower case>_<launch month>`. The launch
   month is the year and month in which the flight starts, as six digits
   (`yyyymm`), for every asset of the launch: it stays the start month even
   when most of the flight, or the asset's own send, falls in a later month.
4. `utm_content`: the placement's stem, an underscore and the variant in lower
   case: `feed_a`, `search_b`, `reminder_a`.
5. Google Search only: `utm_term={keyword}`, written exactly so, braces included. Google
   fills in the keyword. No other channel has a `utm_term`.

For example, `FH-RTL-LF-B` links to:

`https://www.fernhollow.example/shifts/retail?utm_source=linkedin&utm_medium=paid_social&utm_campaign=shifts_rtl_202702&utm_content=feed_b`

## Landing pages

Each audience's page is in `landing_pages.csv`. Link an audience's page only
when its status is `live`. When it has any other status, every asset of that
audience links to the fallback page, `https://www.fernhollow.example/shifts`, with the same
parameters. A page that is not live is never linked.
