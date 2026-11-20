# Kestrel Notes: pricing-page test plan (written before launch)

Kestrel Notes is a note-taking app with a free plan and a paid plan.

- **Change tested:** variant B shows annual pricing first and moves the free-plan button below the paid plans. Control is the current page.
- **Hypothesis:** leading with annual pricing raises the share of pricing-page visitors who create an account.
- **Primary metric:** signup rate = signups ÷ visitors, per variant.
- **Secondary metric (for context only, not a decision metric):** paid conversions within 14 days of the visit.
- **Assignment:** each new visitor is assigned 50/50 to control or variant B.
- **Implementation:** variant B is served by a client-side redirect from /pricing to /pricing-b after assignment.
- **Baseline:** 6% signup rate.
- **Smallest lift worth shipping:** 12% relative.
- **Sample size:** 18,000 visitors per variant (two-sided test, 5% significance, 80% power).
- **Decision rule:** read the result once each variant has 18,000 visitors. Ship variant B only if the primary metric is higher and statistically significant at 5%. Do not stop early on a promising interim result.
