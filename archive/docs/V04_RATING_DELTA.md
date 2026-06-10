# v0.4 Industry-Expert Rating Delta

**Companion to**: [`specs/004-industry-expert-depth/spec.md`](../specs/004-industry-expert-depth/spec.md)

**Build**: Cannavec Science v0.4 industry-expert-depth at HEAD of
`claude/fervent-lovelace-3jFjR`

**Date**: 2026-05-21

**Baseline**: v0.3 (1,143 tests / 130 evals, 9 registries / 145 rows).

## Headline

> **v0.3 had a credible surface with a few honest gaps. v0.4 closes the
> gaps, deepens the curated registries, and renders the v0.3 honesty
> language that had been silently dropped on the floor.**

The v0.4 build is the natural progression from spec 003's "what would an
industry expert want next" review. It does not broaden the audience
lock; it deepens the researcher surface.

## What v0.3 already did well (preserved)

Every v0.3 deliverable continues to work, regression-protected by the
expanded unit and eval suites:

- Δ⁸-THC / HHC / THCO / THCP route to their own monographs
- HHC safety profile returns 0 spurious AE claims
- Entourage-effect prompts return `highest_grade: Unsupported`
- `source-health` does not crash
- `verify` accepts PMID / DOI / NCT / ChEMBL / UniProt
- `cannabis × tacrolimus` matches the CBD-tacrolimus row
- eCBome registry surfaces on anandamide / FAAH / 2-AG prompts
- `registries` lists every curated group
- 0-claim cases set `Answer.notes` (now actually rendered — see N1)
- Rigor-report dedupes by (detector, span)
- K2/Spice hard-refuse, banned-pattern detector, retraction enforcement,
  GRADE wording-vs-grade guard, span-aware `NamedCannabinoidSet`

## New v0.4 closures (P1 bugs + P2 confidence-laundering)

| Finding | Severity | Closure |
|---|---|---|
| **N1** Answer.notes set but never rendered in `to_markdown` / `to_dict` | P1 | `## Notes` section added; `to_dict()` surfaces `notes` list. Tested via `test_spec_004_notes_render.py`. |
| **N2** "indica vs sativa pharmacological differences" returned silent 0 claims | P2 | New sibling banned pattern `indica_sativa_as_pharmacology_abstract` fires the refusal. Tested via `test_spec_004_banned_pattern_abstract.py`. |
| **N3** Inventory only listed 9 registries (no analytical / cultivation) | P3 | Wired both v0.4 registries into `registries.py`; inventory now totals 159 rows across 11 groups. |

## New v0.4 deliverables (US11 + US12 from spec 003)

### Analytical-chemistry registry (`cannavec_science/analytical_chemistry.py`)

8 curated primary-source-anchored rows across 5 topics:

| Topic | Rows | Canonical citations |
|---|---|---|
| Decarboxylation kinetics | 3 | Veress 1990 PMID 2384545, Wang 2016, Citti 2018, Leghissa 2018 |
| HPLC validation | 1 | Citti 2018, Dussy 2005 |
| GC-MS in-injector artefact | 1 | Dussy 2005, Citti 2018 |
| Chemovar classification | 2 | Hazekamp & Fischedick 2012 PMID 22362625, Lewis 2018, Hillig & Mahlberg 2004, Aizpurua-Olaizola 2016 |
| Vapor pyrolysis byproducts | 1 | Pomahacova 2009, Moir 2008 |

### Cultivation-science registry (`cannavec_science/cultivation_science.py`)

6 curated primary-source-anchored rows across 4 topics:

| Topic | Rows | Canonical citations |
|---|---|---|
| Light spectrum (UV-B effect) | 1 | Lydon 1987 PMID 3621052, Magagnini 2018 |
| Trichome biology | 1 | Livingston 2020 PMID 31867754, Tanney 2021 |
| Synthase genetics | 3 | de Meijer 2003 PMID 12663552, Onofri 2015, van Bakel 2011, Taura 2007 |
| Botanical taxonomy (honest debate) | 1 | Small & Cronquist 1976, Hillig 2005, McPartland 2018 |

The botanical-taxonomy row is **explicitly an honest-debate row** —
Cannavec Science cites both the single-species and multi-species
camps and does NOT pick a winner. This is the same evidentiary
honesty v0.3 applied to entourage-effect prompts.

## Industry-expert trust delta

| Heuristic | v0.3 | v0.4 |
|---|---|---|
| **Analytical-chemistry question** (decarb kinetics, HPLC vs GC-MS) | silent 0 claims | Level C claim with primary citation |
| **Cultivation-science question** (UV-B, trichome, synthase) | silent 0 claims | Level C claim with primary citation |
| **Botanical-taxonomy question** | silent 0 claims | Honest-debate Level C claim citing both camps |
| **0-claim honest hint** | set internally but never rendered | rendered as `## Notes` section |
| **Indica vs sativa pharmacology** (abstract framing) | silent 0 claims | refused with strengthened pattern |
| **Indica vs sativa pharmacology** (prose framing) | refused | refused (regression-protected) |
| **Cannabis sativa L. botany framing** | (untested) | passes cleanly into cultivation_science |

## What does NOT ship (deliberately)

The Constitution §IV audience-lock remains intact. v0.4 does NOT add:

- Per-state US regulatory feasibility rows (still in parent plugin)
- Per-state hemp-derived cannabinoid law
- Pesticides registry / lab-QC audience
- Cultivator / retail / patient / clinician audience surfaces
- CourtListener / legal discovery
- Curator-agent auto-mutation of registry rows
- AlphaFold predicted structures (RCSB experimental only)
- Multi-audience templates

Adding any of the above requires a constitutional amendment per the
v0.4 spec's "Out Of Scope" section.

## Test + eval suite delta

| Metric | v0.3 | v0.4 |
|---|---|---|
| Total unit tests | 1,143 | **1,228** (+85) |
| Eval prompts (offline) | 119 | **133** (+14) |
| Eval prompts (total) | 130 | **144** (+14) |
| Eval buckets | 7 | **8** (added `analytical_cultivation`) |
| Curated registries | 9 | **11** (+2) |
| Curated rows total | 145 | **159** (+14) |
| Banned-pattern detectors | 15 | **16** (+1 sibling) |
| Python LOC under `cannavec_science/` | 25,778 | ~26,500 (well below 30,000 ceiling) |
| Total runtime (`python3 -m unittest`) | ~1.8 s | ~1.8 s |

## Constitutional posture

In-constitution. No amendment required. Per-principle impact:

- **§I (Primary-Source Or Refuse)**: deepened — every new registry
  row anchors to PMID / DOI per §I.
- **§II (Deterministic-Backbone Over Prose)**: deepened — analytical
  / cultivation detectors are deterministic topic-keyword matchers;
  the strengthened banned-pattern is a deterministic refusal enforcer.
- **§III (Test-First)**: enforced — 85 new tests across the four
  user stories.
- **§IV (Researcher Audience Only)**: **unchanged**.
- **§V (Safety-Layer Sovereignty)**: deepened by N2 closure.
- **§VI (Phytochemistry Precision)**: deepened — the GC-MS in-injector
  artefact row surfaces at the registry layer the SAME artefact the
  v0.3 THCA-vs-THC rigor detector catches at prose level. The two
  surfaces reinforce each other.
- **§VII (GRADE Honesty)**: deepened — every new registry row caps
  at the source-tier maximum.
- **§VIII (Retractions At Composition)**: unchanged.
- **§IX (Live Discovery)**: unchanged.
- **§X (Stdlib-Only)**: unchanged.
- **§XI (Citable Output Is The Default)**: deepened — bibliography
  export continues to work over the v0.4 typed Answer, including
  the new analytical-chemistry and cultivation-science citations.

## What's next (v0.5+ horizon, not committed)

The spec 003 v0.4 horizon is now complete. Plausible v0.5 directions
(none promised by this build):

- **Solubility / log P table** for cannabinoid formulation work
  (parallel-of-analytical_chemistry, narrower topic).
- **Cannabinoid-acid chemistry** beyond decarb — esterification,
  oxidation, isomerisation under acid catalysis (the conversion
  pathways for HHC / Δ⁸-THC commercial production).
- **Glandular trichome metabolic models** — connecting trichome
  biology to per-cell flux models.
- **Live-discovery cross-registry retrieval** — when a registry row
  cites a watch_pmid that the v0.2 freshness probe finds has gained
  forward citations, surface them in the answer.

These are not promised by this build and would require their own spec.
