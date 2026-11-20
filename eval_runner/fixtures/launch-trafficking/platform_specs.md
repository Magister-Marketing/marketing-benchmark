# Platform specs: Fernhollow Shifts launch

## Assets

An asset is one ad, or one email, for one audience, in one placement, in one
variant. Every audience gets two variants, `A` and `B`, in each of the six
placements below: 3 audiences x 6 placements x 2 variants, 36 assets. An asset
has every field its placement lists, each once, and no other field.

## Placements and fields

The limit is the most characters the field may hold, spaces and punctuation
included. "Must contain" means the exact characters shown, in any case.

| channel | placement | field | limit | must contain |
|---|---|---|---:|---|
| meta | feed | `primary_text` | 125 | `FERN30` and the legal line |
| meta | feed | `headline` | 40 | `Fernhollow` |
| meta | feed | `description` | 30 | - |
| meta | stories | `primary_text` | 80 | `FERN30` |
| meta | stories | `headline` | 25 | `Fernhollow` |
| google | search | `headline_1` | 30 | `Fernhollow` |
| google | search | `headline_2` | 30 | - |
| google | search | `headline_3` | 30 | - |
| google | search | `headline_4` | 30 | - |
| google | search | `headline_5` | 30 | - |
| google | search | `description_1` | 90 | `30% off` |
| google | search | `description_2` | 90 | - |
| linkedin | feed | `intro_text` | 150 | `FERN30` and the legal line |
| linkedin | feed | `headline` | 70 | `Fernhollow` |
| linkedin | feed | `description` | 100 | - |
| email | launch | `subject` | 60 | `Fernhollow` |
| email | launch | `preheader` | 90 | `FERN30` |
| email | reminder | `subject` | 45 | `FERN30` |
| email | reminder | `preheader` | 90 | `Mar 31` |

The legal line, exactly: `Offer ends Mar 31, 2027. New accounts only.`

Only the two fields marked above require it.

## Promo codes

- A Fernhollow promo code is `FERN` followed by digits. `FERN30` is the only
  code any copy may carry: `FERN20` has expired, and no other code may appear.
- Google Search ads carry no promo code at all: a code in a search ad draws
  coupon sites. A Google ad states the offer as `30% off` instead.

## Claims copy never makes

Any case, as a whole word or phrase:

- `best`: a superlative nobody has measured.
- `#1`: a ranking nobody has published.
- `guarantee`: Fernhollow guarantees nothing.
- `guaranteed`: the same.
- `free forever`: there is no free plan, only the launch offer.
- `unlimited`: every plan is priced per user.
- `hipaa`: Fernhollow is not a health-records product: no HIPAA claim of any kind, even for clinics.

## Copy written for its audience

Every asset names its own audience's problem or proof point: at least one of
its fields contains one of that audience's problem keywords or its proof
point, worded as the brief words them (any case; a hyphen may be a space).
Another audience's words do not count.

| audience | problem keywords | proof point |
|---|---|---|
| restaurants | `no-shows`, `no-show` | `18% less overtime` |
| clinics | `double-booked`, `double-booking` | `5 hours a week` |
| retail | `weekend rush` | `98% of shifts filled` |

No field may hold the same text as the same field of the same placement for
another audience, in either variant. Case, spacing and punctuation do not make
two texts different.
