# Security

This repository is private while the security and disclosure policy is being
prepared. Report suspected vulnerabilities privately to the repository
administrators; do not copy secrets, customer data, or production traces into
an issue.

Before public release, this file must be replaced with the approved security
contact and coordinated-disclosure policy. The runtime security model is
documented in `evals/open_source/SECURITY.md`.

Never commit provider keys. The direct OpenAI adapter accepts
`OPENAI_API_KEY` only from its process environment and deliberately excludes
the value from command-line arguments and evidence.
