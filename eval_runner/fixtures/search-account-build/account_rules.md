# Tidewater search account standard

Every search account we build follows this standard. It is applied to the
keyword export as written: do not improve on it, and do not skip a keyword.

## How a term matches a keyword

A term matches a keyword when all of the term's words appear in the keyword as
whole words, next to each other and in the same order. Case does not matter.
`mat` matches "standing desk mat" and does not match "matte black desk".
`desk drawer` matches "under desk drawer" and does not match "desk with
drawers". A plural is a different word unless it is listed.

## Step 1. Exclude what we do not pay for

Check every keyword against these four themes, in this order. A keyword that
matches a theme is excluded with that theme's reason, and the first theme that
matches is the reason. An excluded keyword goes in no campaign, whatever else
it contains, the brand name included.

1. **competitor** (another maker's name): `liftwell`, `ergovo`, `perchly`, `stanza desks`, `oakline`, `varidian`, `deskmate`, `uprise`
2. **unserved_location** (a place tidewater does not ship to): `uk`, `canada`, `australia`, `hawaii`, `alaska`, `europe`, `toronto`, `london`
3. **not_sold** (something tidewater does not sell or do): `used`, `second hand`, `refurbished`, `rental`, `rent`, `repair`, `replacement parts`, `diy`, `plans`, `treadmill`, `converter`, `riser`, `kids`
4. **informational** (research with no purchase in it): `how to`, `what is`, `benefits`, `vs`, `reddit`, `ideas`, `worth it`, `calories`

## Step 2. Campaign

Each keyword that is left belongs to the first campaign in this list with a
term that matches it.

1. **Brand**: `tidewater`
2. **Frames**: `frame`, `frames`, `legs`
3. **Desktops**: `desktop`, `desktops`, `tabletop`
4. **Monitor Arms**: `monitor arm`, `monitor arms`, `monitor mount`
5. **Accessories**: `cable`, `mat`, `desk drawer`, `casters`, `power strip`
6. **Desks**: every keyword no earlier campaign claimed

## Step 3. Ad group

Inside its campaign, a keyword belongs to the first ad group in that
campaign's list with a term that matches it. Only that campaign's list
applies. Ad groups are named exactly as written here. An ad group exists only
if at least one keyword lands in it.

### Brand

1. `Brand | Core`: every keyword no earlier ad group claimed

### Desks

1. `Desks | L-Shaped`: `l shaped`, `corner`
2. `Desks | Electric`: `electric`, `motorized`, `dual motor`
3. `Desks | Manual`: `manual`, `crank`
4. `Desks | Gaming`: `gaming`
5. `Desks | Size`: `48 inch`, `60 inch`, `72 inch`, `small`, `large`, `wide`
6. `Desks | Finish`: `bamboo`, `walnut`, `oak`, `white`, `black`
7. `Desks | Price`: `price`, `cheap`, `sale`, `deal`, `under 500`
8. `Desks | General`: every keyword no earlier ad group claimed

### Frames

1. `Frames | Motor`: `dual motor`, `single motor`
2. `Frames | L-Shaped`: `l shaped`, `corner`
3. `Frames | Finish`: `black`, `white`, `silver`
4. `Frames | General`: every keyword no earlier ad group claimed

### Desktops

1. `Desktops | Bamboo`: `bamboo`
2. `Desktops | Hardwood`: `walnut`, `oak`, `maple`
3. `Desktops | Laminate`: `laminate`
4. `Desktops | Size`: `48 inch`, `60 inch`, `72 inch`
5. `Desktops | General`: every keyword no earlier ad group claimed

### Monitor Arms

1. `Monitor Arms | Dual`: `dual`
2. `Monitor Arms | Single`: `single`
3. `Monitor Arms | General`: every keyword no earlier ad group claimed

### Accessories

1. `Accessories | Cable Management`: `cable`
2. `Accessories | Mats`: `mat`
3. `Accessories | Drawers`: `desk drawer`
4. `Accessories | Other`: every keyword no earlier ad group claimed

## Step 4. Match type

- Every keyword in the Brand campaign is `exact`.
- Elsewhere a keyword with 1,000 or more average monthly searches is `exact`.
- Every other keyword is `phrase`.

## Step 5. Negative keywords

Two kinds, and no others. All are `phrase` match.

- **Account level:** one negative for every term in Step 1 that matches at
  least one keyword in the export. A term that matches nothing in the export
  gets no negative.
- **In each `General` ad group:** one negative for every term of the other ad
  groups that exist in the same campaign, where that term matches at least one
  keyword targeted in that campaign. This keeps the General ad group from
  taking searches that belong to a more specific one.

## Step 6. Daily budgets

One daily budget per campaign that has keywords.

1. A keyword's expected daily cost is its average monthly searches, times the
   click rate, times the midpoint of its bid range, divided by 30.4.
   The click rate is 15% in the Brand campaign and 4% everywhere else.
2. A campaign's estimate is the sum over its targeted keywords.
3. The account has $100.00 a day. If the estimates add up to more, multiply
   every estimate by $100.00 divided by their total.
4. Round each result down to the cent.
5. A campaign that comes out under $5.00 gets $5.00. Nothing else changes when that happens.

## Step 7. One ad per ad group

Each ad has three headlines and two descriptions.

- A headline is at most 30 characters and a description at most 90, spaces and punctuation included.
- Headline 1 names what the campaign sells, with these exact words (any case):

- Brand: `Tidewater`
- Desks: `Standing Desk`
- Frames: `Desk Frame`
- Desktops: `Desktop`
- Monitor Arms: `Monitor Arm`
- Accessories: `Desk`

- Headline 2 contains `Tidewater`.
- One headline contains the ad group's own name, the part after the bar
  (`L-Shaped`, `Bamboo`, `Cable Management`). A space in place of a hyphen is
  fine. This does not apply to `Core`, `General` and `Other`.
- One description contains the shipping offer exactly as the business facts word it.
- No two headlines of one ad are the same, and no two ad groups share a first headline.
- Never: `best`, `cheapest`, `#1`, `guarantee`, `guaranteed`, `lifetime`, `free returns`.
- A dollar amount in an ad is one of that campaign's advertised prices from the
  business facts. A Brand ad may state any of them. An Accessories ad states none.
