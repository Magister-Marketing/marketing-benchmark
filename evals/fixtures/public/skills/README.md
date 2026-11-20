# Skill guidance provenance

These SKILL.md files are **verbatim, unmodified copies** from
[marketingskills](https://github.com/coreyhaines31/marketingskills) — the
open marketing skill pack written by Corey Haines, co-founder of Magister —
vendored via Magister's production fork
([Magister-Marketing/marketingskills](https://github.com/Magister-Marketing/marketingskills))
at commit `2c38021374f4871eca784b1525be742d7ac08aa1` (pack version 2.8.23,
2026-11-20), the pin Magister's agent machines ran that day. The copies before
this one were made on 2026-08-31 at `1982ce1b1206e24b0c291d3f4dc9535108505aba`
(pack version 2.8.16); a run made before the refresh used those, and a
"with skills" run is only comparable with a Magister run when both used the
same pack.

Each file's own version is in its frontmatter. At this pin:

| Benchmark path | Upstream path | Version |
|---|---|---|
| `ad-creative/SKILL.md` | `skills/ad-creative/SKILL.md` | 2.9.4 |
| `analytics/SKILL.md` | `skills/analytics/SKILL.md` | 2.3.2 |
| `copywriting/SKILL.md` | `skills/copywriting/SKILL.md` | 2.1.7 |
| `cro/SKILL.md` | `skills/cro/SKILL.md` | 2.0.0 |
| `emails/SKILL.md` | `skills/emails/SKILL.md` | 2.0.3 |
| `site-architecture/SKILL.md` | `skills/site-architecture/SKILL.md` | 2.0.0 |

How they reach the model: `assemble_prompt` in `eval_runner/bench.py` appends
each task's listed skill files to the prompt as plain-text blocks under
`## Skill guidance you should follow`. The `--no-skills` arm omits those
blocks and changes nothing else. Because the files are verbatim production
skills, they contain workspace conventions (BRAND.md checks, "ask if not
provided") that a single-shot benchmark prompt cannot satisfy; applying the
skill sensibly with only the supplied fixtures is part of what the benchmark
measures.

To refresh: copy the files from the fork checkout unchanged and update the
pinned commit and the versions above. Refresh before any run whose "with
skills" numbers will sit beside a Magister run. Do not edit the skill bodies — a benchmark-local edit
breaks the claim that the skills arm tests the shipped skill pack. Before the
2026-08-25 runs these paths held ~500-byte benchmark-written distillations;
runs recorded before then used that older guidance (each run directory
snapshots the exact prompts it sent).
