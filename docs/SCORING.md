# How scoring works

[Back to the overview](../README.md) · [See all tasks](TASKS.md) ·
[See scored examples](SCORED_EXAMPLES.md)

The headline rule is simple: **one task equals one point**.

```text
Model answer → requirement checks → task PASS or FAIL → tasks passed ÷ tasks attempted
```

If a model passes two of three tasks, its score is **2/3, or 67%**. Tasks are
equally weighted, even when one task has more requirements than another.

## What the fraction under a task means

Each task has a checklist of binary requirements. `7/8 checks` means seven
requirements passed and one failed. It explains the result, but it is not
partial credit: the task is still a **FAIL**.

This prevents a polished answer from earning most of a point while missing one
critical detail, such as using the wrong denominator or inventing an
unsupported claim.

## Who checks the answer

Two kinds of checks work together:

1. **Local checks** handle facts a program can settle exactly, such as word
   counts, dollar totals, required phrases, HTML structure, and the number of
   requested items.
2. **The LLM judge** handles requirements that need interpretation, such as
   whether three ad concepts are meaningfully distinct or a recommendation is
   properly supported.

The judge receives the exact task prompt and candidate answer, but not the
candidate model's identity. It has no web tools. For each requirement it must
return a literal pass or fail plus a short explanation tied to the answer.
Malformed or incomplete judge output is rejected and retried once; a second
failure counts as a failed run.

A run passes only when the answer is marked complete and every local and judge
requirement passes. A human reviewer can later agree with or override that
verdict, and reports show whether a result has been human-verified.

## What happens with repeat runs

The default is one answer per model and task, called **Pass@1**.

`--repetitions 3` asks for three independent answers. The scores are not
averaged: **all three answers must pass for the task to pass**. This makes
repeats a reliability test rather than a way for one strong answer to hide two
weak ones.

Provider errors, abnormal finishes, and judge failures count as failed
attempts.

## Tokens, time, and cost

The report keeps quality and efficiency separate:

| Measure | What it means |
|---|---|
| Output tokens | Total tokens produced by the candidate model across the selected tasks |
| Answer cost | Estimated total cost of the models answering the tasks, based on recorded usage and the price catalog |
| Average task time | Mean candidate response time; tasks may run in parallel |

Judge tokens, judge cost, and judge time are excluded from these efficiency
numbers. Some reasoning models count internal reasoning tokens in output usage,
even though those tokens are not visible in the final answer. When repeat runs
are used, the HTML and JSON reports also retain the individual attempts so
their spread can be inspected.

## Why the split matters

- **Development results** can guide improvements to prompts and rubrics. They
  are useful evidence, but they are not untouched test results.
- **Holdout results** come from tasks that were not used for tuning. Once their
  answers are inspected, those tasks are no longer pristine holdouts.

For exact data fields, retry behavior, and implementation details, see the
[direct-model runner reference](../eval_runner/README.md).
