# Security

## Reporting a vulnerability

Report a suspected vulnerability privately, through GitHub's private
vulnerability reporting: on this repository's **Security** tab, choose
**Report a vulnerability**. Do not open a public issue or pull request for it.

Please include what you found, the steps to reproduce it, and what an attacker
could do with it. Do not include real secrets, customer data or production
traces; describe them instead.

We acknowledge a report within three working days, keep you informed while we
fix it, and credit you when the fix is published unless you ask us not to.
Please give us a reasonable time to fix a problem before you disclose it.

## What is in scope

The code in this repository: the runners (`eval_runner/`, `evals/`), their
scripts, and anything in the tasks or fixtures that could leak a credential or
run code it should not. Magister's hosted product is not in this repository;
report problems with it the same way and we will route them.

## Keys

Never commit provider keys. The runners read API keys from the environment or
from a local `--env-file`, never from command-line arguments, and keep their
values out of every file they write. The direct OpenAI adapter accepts
`OPENAI_API_KEY` only from its process environment. The runtime security model
of the agent engine is in [evals/open_source/SECURITY.md](evals/open_source/SECURITY.md).
