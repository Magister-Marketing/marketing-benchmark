# Quillon Pet Supply: rules for titles and meta descriptions

Quillon Pet Supply sells pet food, beds, toys and supplies online at www.quillonpets.example. Write a title and a meta description for every page in `page_inventory.csv` that is indexed, following these rules.

## Which pages
- A page whose `index` is `noindex` gets no row, and it takes no part in the keyword rule below.

## The target keyword
- Each page targets its `primary_keyword`.
- When two or more indexed pages have the same `primary_keyword`, only one of them keeps it: the page with the most `clicks_28d`; on a tie, the page whose type comes first in this order: category, product, guide; on a further tie, the page whose `page_id` comes first. Every other page of the group targets its `secondary_keyword` instead, and neither its title nor its meta description may contain the primary keyword it gave up.
- Keywords are matched as whole words. Capital letters may differ, and a hyphen may stand for a space; nothing else may.

## Titles
- At most 60 characters, counting spaces and the suffix.
- Contain the page's target keyword.
- End with the suffix for the page type, exactly:
  - category: ` | Shop Quillon Pets`
  - product: ` | Quillon Pets`
  - guide: ` | Quillon Pets Guides`
- The brand name "Quillon" appears in a title only in its suffix.
- No price and no `$`.

## Meta descriptions
- 100 to 155 characters, counting spaces.
- Contain the page's target keyword. A page that keeps its primary keyword also contains its `secondary_keyword`.
- A product page contains the first of its `attributes` (they are separated by semicolons), word for word.
- A category page contains its `product_count`, written in digits.
- An in-stock product page (`in_stock` is yes) contains its price, written as `$` and the `price` value exactly as the inventory gives it (`$34.00`). No other meta description contains a price or a `$`: an out-of-stock product's price is not shown anywhere.

## No duplicates
- No two titles are the same, and no two meta descriptions are the same.
