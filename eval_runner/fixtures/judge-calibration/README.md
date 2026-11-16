# Whole-answer judge calibration

These are synthetic development examples, not customer conversations or holdout
evidence. The `*-errors.md` files preserve complete generated answers with known
factual mistakes; run-owned file paths were replaced by a neutral draft path.
The `*-supported.md` controls contain explicitly qualified source-backed claims
and labeled creative hypotheses. Both kinds are graded with the whole task
rubric, not just an isolated criterion.

Only named expected checks determine calibration success. A short contrast can
legitimately fail unrelated completion criteria. Multiple checks of the same
answer reuse one judgment and one billed call. Calibration is a paid manual
command; ordinary tests stub the provider and never call a model.

Passing these examples establishes regression coverage for known failures, not
judge accuracy on unseen tasks. Preserve failed calibration runs and validate
future generalization with different sources and scenarios.

The attribution, email-flow, marketing-plan and CAPI pairs exercise four known
whole-answer false passes: causal budget recommendations despite a disclaimer,
an unqualified subject-line claim, a changed activation definition, and invalid
worked hashes. Supported variants repair the named check only; they are not
certified perfect answers to the other criteria. CAPI email hashes are recomputed
by the harness; other raw-field normalization is intentionally left to review.
The parser is conservative and absence of a parsed example is not evidence that
hashing is correct. Do not use these development pairs as unseen evaluations.

Boundary controls distinguish a visually clear booking CTA from a hidden one,
and an outside clinician referral from an invented credential for the service
provider. The original broken booking target and unrelated answer defects remain
in both variants. Each answer is graded against the full rubric; only the named
criterion determines calibration success. The CAPI
delivery-identity pair makes repeated delivery behavior explicit; its positive
version is strengthened and does not settle the earlier disagreement about an
answer that implied stability through a deterministic order ID. No rubric or
judge instruction was changed to match these examples.

Calibration records preserve bounded provider identity, usage, elapsed time and
structured failure category/status when available. They omit raw error messages,
bodies and headers. A failed request can have a partial usage receipt while its
total cost remains unknown; never count it as a free call or a judge disagreement.
These fields aid future investigation. They cannot reconstruct billing or an
error category discarded by an older run.
