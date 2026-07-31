# Security model for a standalone eval runner

The runner executes model-generated actions and optional operator-installed plugins. Treat both as untrusted until a scenario and plugin have passed review.

- Run replay tool environments without vendor network access or credentials. The model backend may still need provider network access. Public fixtures must be synthetic or redistributable and must keep grader oracles outside the agent workspace.
- Temporary workspaces and strict MCP configuration are isolation layers, not an operating-system sandbox. For high-assurance or adversarial agents, run the adapter in a container or VM with a minimal filesystem mount, no unrelated secrets, and the oracle source outside that mount; a locally installed agent can otherwise access anything its operating-system identity permits.
- Scenario manifests select only registered plugin IDs. They cannot name Python modules, shell commands, credentials, users, projects, or arbitrary live endpoints.
- The generic subprocess command is operator configuration, never manifest data. It runs without a shell but receives the operator's process environment; launch it from a least-privilege environment and pass only the credentials its agent needs.
- Live environments require a separate plugin, explicit confirmation, narrow read-only scopes, an exact resource allowlist, redacted evidence, and owned test accounts. Write, send, publish, spend, and delete suites require a separate safety design.
- Unknown tools and operations fail closed as external writes. Persist hashes and bounded redacted previews rather than credentials, authorization headers, cookies, customer identifiers, or complete vendor payloads.
- Adapters and environments must clean up attempt-owned resources even after failure. Never implement cleanup with a broad recursive target or a user-provided path.

Before a public release, configure a private vulnerability-reporting address and coordinated-disclosure policy. Do not publish a placeholder contact.
