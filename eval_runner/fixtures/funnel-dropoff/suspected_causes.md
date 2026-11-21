# Incident thread: suspected causes of the checkout drop (collected 2026-03-30)

| # | Suspected cause | Date | Segments it would hit | Step it would break |
|---|---|---|---|---|
| C1 | Address autocomplete (5.7.0) confuses shoppers | 2026-03-10 | every segment | shipping |
| C2 | The new CDN is slow on phones and the payment page times out | 2026-03-14 | mobile / Safari, mobile / Chrome | order |
| C3 | The new payment form (5.8.0) fails on iPhone Safari | 2026-03-16 | mobile / Safari | order |
| C4 | The new payment form (5.8.0) fails on iPad Safari | 2026-03-16 | tablet / Safari | order |
| C5 | The spring-sale email brought shoppers who leave before shipping | 2026-03-21 | every segment | shipping |
| C6 | The 5.8.1 hotfix broke card payments on desktop Chrome | 2026-03-24 | desktop / Chrome | order |
| C7 | Edge 136 blocks the payment page's scripts | 2026-03-20 | desktop / Edge | payment |
| C8 | Analytics SDK 5.9.0 broke Safari checkouts on desktop and iPad | 2026-03-27 | desktop / Safari, tablet / Safari | order |
| C9 | Express wallets (5.8.0) fail on Android phones | 2026-03-16 | mobile / Chrome, mobile / Samsung Internet | order |
| C10 | The new shipping-rate panel does not fit on tablets | 2026-03-18 | tablet / Safari, tablet / Chrome | shipping |
| C11 | The new shipping-rate table puts Firefox shoppers off | 2026-03-18 | desktop / Firefox, mobile / Firefox | shipping |
| C12 | The new payment form (5.8.0) fails on desktop Firefox | 2026-03-16 | desktop / Firefox | order |
| C13 | The new payment form (5.8.0) also slows the shipping step on Android tablets | 2026-03-16 | tablet / Chrome | shipping |
