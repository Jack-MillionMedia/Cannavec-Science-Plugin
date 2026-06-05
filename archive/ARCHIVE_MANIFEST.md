# Archive — post-MVP machinery (parked, not deleted)

These modules were moved out of the shipping package during the **first-principles
MVP teardown** (branch `claude/mvp-first-principles-teardown`). They are preserved
here in full — with their tests and data — and are restorable at any time.

**Why they were parked:** none of them strengthen the MVP's core mission —
*grounding an AI reasoner in verifiable primary-source cannabis science*
(retrieve → verify identifiers → enforce retractions → GRADE → citation-lossless
artifact). They were either (a) machinery that **grows** the static curated
registry the constitution names an anti-pattern (M5), (b) niche statistics with
no user-facing surface, or (c) true orphans imported by nothing.

## What was archived

| Cluster | Modules | Reason |
|---|---|---|
| Curation flywheel | `flywheel`, `demand`, `curation_store`, `source_index` | The §IX registry-growth engine. Zero slash-command / API / agent / skill references. Grows the static-answer substrate (M5). Data: `primary_source_index.csv` (616 KB), `staging_queue.jsonl`, `demand_log.jsonl`. |
| Meta-analysis | `meta_analysis`, `absolute_effects`, `grade_profile` | ~3.4 K LOC of pooling statistics (DerSimonian-Laird, Egger, trim-and-fill, GRADE Summary-of-Findings). Rigorous, but outside the demo loop. Restore as a `research` sub-analysis post-MVP. |
| Stat calculators | `fragility`, `disproportionality`, `binding` | Single-purpose calculators (Fragility Index, PRR/ROR, Cheng-Prusoff). Niche; no canonical command. |
| Researcher scaffolders | `pico`, `power_calc`, `protocol_skeleton`, `sof`, `regulatory_feasibility` | Flag-gated `answer` extras. Convenience, not grounding. `regulatory_feasibility` was already declared out-of-MVP-scope. |
| Ops | `source_health`, `freshness` | Per-source liveness + registry freshness-watch. Maintenance jobs, not part of the 5-command surface. |
| Orphans | `terpene_reference`, `evidence_synthesis`, `contradiction` | Imported by nothing (or only by each other). Dead code. |
| Skill | `skills/cannabis-evidence-synthesis` | Routed to the archived `meta`/`fragility`/`signal`/`affinity` tools. |

## How to restore a module

```bash
git mv archive/cannavec_science/<module>.py cannavec_science/<module>.py
git mv archive/tests/test_<module>.py tests/test_<module>.py
# re-add its subcommand/flag wiring in cannavec_science/__main__.py
```

Full pre-teardown state is also tagged: `git checkout pre-mvp-teardown-2026-06-05`.
