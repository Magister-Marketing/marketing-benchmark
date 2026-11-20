# Sorrel Kitchen: email policy (marketing sends)

Sorrel Kitchen is a weekly meal-kit subscription. This policy applies to every marketing email.

## Who may be emailed
- Only people whose `consent_status` is `subscribed`.
- `unsubscribed` people are never emailed marketing, whatever their order history.
- `never_consented` records came from checkout and event-list imports. They did not opt in and are never emailed marketing, whatever their order history.
- `pending_confirmation` people have not confirmed their address and are not emailed until they do.
- An address with a hard bounce or a spam complaint is suppressed.

## Re-engagement rules
- A subscriber is lapsed when they have not opened an email in the last 90 days.
- A lapsed subscriber gets at most three re-engagement emails, at least 5 days apart.
- A subscriber with no open in the last 12 months gets one last-chance email only, not the three-email flow.
- Anyone who opens, clicks or orders leaves the flow at once and returns to regular sends.
- Anyone who has not opened or clicked by 7 days after their final email is suppressed from marketing.

## Offers
- The only approved incentive is 10% off the next box with code COMEBACK10, valid for 14 days from the send. It is for lapsed subscribers who have ordered before.
- Lapsed subscribers who have never ordered get the free "Five 20-Minute Dinners" recipe pack instead. No discount.

## Every email
- Carries an unsubscribe link and a link to email preferences.
- Uses an honest subject line. No "Re:" or "Fwd:" prefixes and no fake urgency.
