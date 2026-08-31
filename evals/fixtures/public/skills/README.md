# Skill guidance provenance

These SKILL.md files are **verbatim, unmodified copies** from
[marketingskills](https://github.com/coreyhaines31/marketingskills) — the
open marketing skill pack written by Corey Haines, co-founder of Magister —
vendored via Magister's production fork
([elliot-ylambda/marketingskills](https://github.com/elliot-ylambda/marketingskills))
at commit `b7386fbafad49af99342b426b13c80115d991d92`, the same pin that ships
on every Magister agent machine.

| Benchmark path | Upstream path | Version |
|---|---|---|
| `ad-creative/SKILL.md` | `skills/ad-creative/SKILL.md` | 2.8.2 |
| `analytics/SKILL.md` | `skills/analytics/SKILL.md` | see frontmatter |
| `copywriting/SKILL.md` | `skills/copywriting/SKILL.md` | 2.0.1 |
| `cro/SKILL.md` | `skills/cro/SKILL.md` | see frontmatter |
| `emails/SKILL.md` | `skills/emails/SKILL.md` | see frontmatter |
| `site-architecture/SKILL.md` | `skills/site-architecture/SKILL.md` | see frontmatter |

How they reach the model: `assemble_prompt` in `eval_runner/bench.py` appends
each task's listed skill files to the prompt as plain-text blocks under
`## Skill guidance you should follow`. The `--no-skills` arm omits those
blocks and changes nothing else. Because the files are verbatim production
skills, they contain workspace conventions (BRAND.md checks, "ask if not
provided") that a single-shot benchmark prompt cannot satisfy; applying the
skill sensibly with only the supplied fixtures is part of what the benchmark
measures.

To refresh: copy the files from the fork checkout unchanged and update the
pinned commit above. Do not edit the skill bodies — a benchmark-local edit
breaks the claim that the skills arm tests the shipped skill pack. Before the
2026-08-25 runs these paths held ~500-byte benchmark-written distillations;
runs recorded before then used that older guidance (each run directory
snapshots the exact prompts it sent).
