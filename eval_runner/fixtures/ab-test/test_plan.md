# Kestrel Notes: pricing-page test plan (written before launch)

Kestrel Notes is a note-taking app with a free plan and a paid plan.

- **Change tested:** variant B shows annual pricing first and moves the free-plan button below the paid plans. Control is the current page.
- **Hypothesis:** leading with annual pricing raises the share of pricing-page visitors who create an account.
- **Primary metric:** signup rate = signups ÷ visitors.
- **Guardrail metric:** billing-support tickets opened within 7 days of the visit, per 1,000 visitors.
- **Assignment:** each new visitor is assigned once. Desktop visitors are split 50/50 between control and variant B. Mobile visitors are split 70/30: 70% to control and 30% to variant B, because variant B's mobile layout is new.
- **Duration:** 28 days, 2026-04-06 to 2026-05-03.
- **QA visits:** visits from the company's office network are recorded with source `internal`. They are the team's own checks, forced into variant B with a URL flag, and are left out of every metric, check and decision rule below; every other source counts.
- **Burn-in week:** days 1 to 7. A new page draws curiosity clicks and a new test carries set-up problems, so the burn-in week is left out of every metric, check and decision rule below. The analysis window is days 8 to 28.

## How the result is read (analysis window only)
- A variant's signup rate on a device = its signups ÷ its visitors on that device.
- Device-weighted signup rate of a variant = its desktop signup rate × desktop's share of all visitors + its mobile signup rate × mobile's share, where a device's share counts the visitors of both variants. Device-weighted lift = variant B's device-weighted rate ÷ control's − 1. This is the primary estimate, because the two devices are split differently.
- Sample-ratio check, for each device: chi-square = the sum over both variants of (observed visitors − expected visitors)² ÷ expected visitors, where expected visitors = the device's visitors × the variant's planned share on that device. The check fails on a device when its chi-square is above 3.841.
- Guardrail: billing tickets ÷ visitors × 1,000, per variant, both devices together. It is breached when variant B's rate is more than 20% above control's.

## Decision rules
Apply them in order. The first rule whose condition holds decides.
1. Either variant has fewer than 10,000 visitors: keep the test running.
2. The sample-ratio check fails on either device: the split is broken; fix the assignment and run the test again.
3. The guardrail is breached: do not ship variant B.
4. The device-weighted lift is +3.0% or more and variant B's signup rate is higher than control's on both devices: ship variant B.
5. Otherwise: keep control.
