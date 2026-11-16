# Fresh single-model comparison

Use the existing 20 direct-compatible tasks and a fixed evaluator for the
first refreshed comparison. The decoy task requires a prior turn and stays out
of this set. Previously inspected tasks, including those still labelled
`holdout` in historical manifests, are development evidence here.

Each condition receives the same assignment and source facts. Compare the
plain API with web search, the same API with web search and the selected full
skill files, and a separately executed native product. Record the native
runtime and skill hashes downstream; keep private access and identities out
of this repository. Native tools, skill discovery, references and multiple
model calls are part of the treatment. This is not an equal-compute experiment.

Gemini Flash high now requests a 65,536-token ceiling, the model's advertised
completion limit, in every condition. Earlier direct runs truncated four of
twenty tasks at the old 16,000 ceiling. The new limit gives the direct baseline
room to answer and is recorded explicitly; old scores are not a controlled
comparison with these new runs. Temperature remains omitted.

Generate each direct arm separately (paid, operator-only):

```sh
python -m eval_runner.bench run --models gemini-3.8-flash-high \
  --repetitions 1 --tools --no-skills --strict-attempts \
  --request-timeout-seconds 600 --stop-after-cost-usd 5 \
  --env-file /path/to/private/provider.env --yes
python -m eval_runner.bench run --models gemini-3.8-flash-high \
  --repetitions 1 --tools --strict-attempts \
  --request-timeout-seconds 600 --stop-after-cost-usd 5 \
  --env-file /path/to/private/provider.env --yes
```

Strict mode makes serial calls without transport retries or output-ceiling
retries. It requires OpenRouter's returned model, allowed provider label and
response ID. Responses, empty completions and billed failures remain evidence.
Dispatch and completed-attempt journals are flushed to disk. A generation
error, unverified route, unknown cost or observed spend stop halts subsequent
calls; the remaining planned cells are recorded as undispatched failures.
The cost threshold is not a hard cap: one in-flight request can exceed it.
Strict runs cannot be retried in place. A new experiment gets a new run.

Reports include observed failed-call spend and label unknown billing as a lower
bound. Request timeouts do not prove the provider stopped its own work. Raw
provider receipts distinguish recorded cost from token-rate estimates.

Freeze task, fixture, skill, model, provider, grading and runner sources before
generation. Use one unchanged grader and retain all outputs, including errors.
Review disagreements and sampled passes without silently replacing original
grades. Publish one repetition as preliminary, with cost, latency, failures and
the declared treatment differences. No product deployment or migration is
required for this runner change.
