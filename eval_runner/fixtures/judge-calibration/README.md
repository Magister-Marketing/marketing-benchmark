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
