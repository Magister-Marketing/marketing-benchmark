# Bramblewood Kitchen: redirect rules for the platform move

Bramblewood Kitchen sells cookware, knives and kitchen tools online at www.bramblewoodkitchen.example. The shop moves to a new platform, on the same domain, on 2027-01-18. `old_site_urls.csv` is the crawl of the old site; `new_site_urls.csv` is the final crawl of the new site on staging. Both write URLs as paths.

## The file to deliver

`redirects.csv`, with the header `old_url,status,target`: one row for every old URL that gets a redirect (`301`) or is retired as gone (`410`), and no row for any other old URL. A 410 row has an empty `target`. Write every URL as a path, exactly as the files write it.

## The rules, in order

Take each URL in `old_site_urls.csv` and apply these rules in order. The first rule that applies decides its row.

1. **Parameter URLs.** A URL with a `?` in it gets no row. The new platform drops query strings.
2. **Dead URLs nobody links to.** A URL whose `status` is 404 and whose `backlinks` is 0 gets no row.
3. **Unchanged URLs.** A URL that appears in `new_site_urls.csv`, exactly as written, with status 200 gets no row.
4. **The trade portal.** `/wholesale` and every URL under `/wholesale/` get 410. The trade programme has closed.
5. **Old redirects.** A URL whose `status` is 301 gets the same status and target as its `redirect_target` gets under these rules, so that no visitor passes through an old address.
6. **Products on the new site.** A `/products/` URL whose `sku` appears in `new_site_urls.csv` redirects to the new URL of that SKU. Products are matched by SKU only; a product page with the same slug but another SKU is a different product.
7. **Retired products.** A `/products/` URL whose `sku` does not appear in `new_site_urls.csv` is retired. If its `inlinks`, `backlinks` and `sessions_90d` are all 0 it gets 410. Otherwise it redirects to the new address the rename table gives `/collections/<its category>`.
8. **Renamed categories and pages.** A URL in the rename table below redirects to its new address.
9. **Journal posts.** A URL under `/blogs/kitchen-notes/` moves to `/journal/` with the same slug, except that a slug that starts with a date written `YYYY-MM-` (four digits, a hyphen, two digits, a hyphen) loses that date. If the address this gives is not in `new_site_urls.csv`, the post redirects to `/journal` instead.
10. **Everything else** gets 410.

## Every redirect lands on a live page

The target of a 301 must have status 200 in `new_site_urls.csv`. Where a rule above gives an address that has status 301 in `new_site_urls.csv`, the target is that row's `redirect_to` instead. Every redirect in the new list is a single hop to a live page.

## The rename table

| Old URL | New address |
|---|---|
| `/collections/frying-pans` | `/shop/frying-pans` |
| `/collections/saucepans` | `/shop/saucepans` |
| `/collections/dutch-ovens` | `/shop/dutch-ovens` |
| `/collections/cast-iron` | `/shop/cast-iron` |
| `/collections/stainless-steel` | `/shop/stainless-steel-cookware` |
| `/collections/nonstick` | `/shop/frying-pans` |
| `/collections/knives` | `/shop/kitchen-knives` |
| `/collections/knife-sets` | `/shop/kitchen-knives` |
| `/collections/cutting-boards` | `/shop/cutting-boards` |
| `/collections/bakeware` | `/shop/bakeware` |
| `/collections/baking-tools` | `/shop/bakeware` |
| `/collections/utensils` | `/shop/kitchen-tools` |
| `/collections/gadgets` | `/shop/kitchen-tools` |
| `/collections/storage` | `/shop/food-storage` |
| `/collections/kitchen-linens` | `/shop/linens` |
| `/collections/coffee-tea` | `/shop/coffee-and-tea` |
| `/collections/gifts` | `/shop/gifts` |
| `/collections/sale` | `/shop/sale` |
| `/collections/new-arrivals` | `/shop/new` |
| `/pages/shipping` | `/pages/shipping-and-returns` |
| `/pages/returns` | `/pages/shipping-and-returns` |
| `/pages/our-story` | `/pages/about` |
| `/pages/care-guides` | `/journal/care-and-cleaning` |
| `/pages/store-locations` | `/pages/visit-us` |
| `/blogs/kitchen-notes` | `/journal` |
