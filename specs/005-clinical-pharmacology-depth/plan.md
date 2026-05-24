# Implementation Plan: Cannavec Science v0.5 Clinical-Pharmacology Depth

**Spec**: [`spec.md`](./spec.md)

**Created**: 2026-05-24

**Status**: Approved — implementation in flight on `claude/exciting-shannon-cMhTQ`

## Strategy

Eight independently shippable user stories, ordered by P-priority and
dependency. US1-US5 (the five new registries) are pure-data leaves of
the dependency graph and can land in any order; we land them in
spec-order. US6 (Europe PMC live lane) is independent of US1-US5 and
can land in parallel. US7 (registry inventory wiring) and US8 (evals +
version + README) are the closing tasks.

```
US1 (pharmacokinetics, P1)        US2 (use_disorder, P1)
       ↓                                  ↓
US3 (hyperemesis_syndrome, P1)    US4 (ecbome_inhibitors, P2)
       ↓                                  ↓
US5 (biosynthesis, P2)            US6 (Europe PMC discover, P3)
       ↓                                  ↓
              US7 (registry inventory wiring, P3)
              ↓
              US8 (evals + version + README, P3)
```

## Version-Boundary Promotion

This spec lifts the version stamp from `0.4.0` to `0.5.0` across three
files:

1. `.claude-plugin/plugin.json` `version`.
2. `pyproject.toml` `project.version`.
3. `cannavec_science/__init__.py` `__version__`.

The README's "v0.4" headline tag is replaced with a "v0.5
industry-expert-clinical-depth" tag.

**No constitutional amendment is required.** Research-grade clinical
pharmacokinetics, addiction-medicine instruments, GI-syndrome criteria,
eCBome drug-development translation, and cannabinoid biosynthesis are
all explicit researcher-audience targets — same posture as the v0.4
analytical-chemistry / cultivation-science promotion. Europe PMC is a
twelfth primary-source live lane that complements PubMed within §IX.

## Files To Create / Modify

### US1 — Clinical pharmacokinetics registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/pharmacokinetics.py` | 8-row registry (THC inhaled smoked + vaped, THC oral, CBD oral, CBD food effect, 11-OH-THC metabolite, nabiximols oromucosal, distribution / detection window). Topic-keyword detector. `to_claim()` method. | ~600 |
| `tests/test_pharmacokinetics.py` | Shape, primary-citation, detector positive/negative, claim round-trip, isomer-disambiguation cleanliness, freshness, integration-with-major-cannabinoid coexistence. | ~330 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_pharmacokinetics_mention(prompt)`. Rows attach citations + claims (when not refused). Renders as `## Pharmacokinetics registry` section. Trace counter `registry.pharmacokinetics`. |
| `cannavec_science/__main__.py` | Add `pharmacokinetics` to the registry-subcommand handler's allowed names + --registry help text. |

### US2 — Cannabis use disorder & withdrawal-syndrome registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/use_disorder.py` | 6-row registry (DSM-5 CUD criteria Hasin 2013, CUDIT-R Adamson 2010, CWS Allsop 2011, prevalence Hasin 2015, heritability Verweij 2010, telescoping Chen 2009). Topic-keyword detector. `to_claim()` method. | ~480 |
| `tests/test_use_disorder.py` | Shape, primary-citation, detector positive/negative, claim round-trip, freshness, integration-with-adverse-events coexistence (Volkow 2014 row co-fires cleanly). | ~280 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_use_disorder_mention(prompt)`. Same wiring as US1. Renders as `## Use disorder / withdrawal registry` section. Trace counter `registry.use_disorder`. |
| `cannavec_science/__main__.py` | Add `use_disorder` to registry-subcommand handler. |

### US3 — Cannabinoid hyperemesis syndrome registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/hyperemesis_syndrome.py` | 4-row registry (diagnostic criteria Sorensen 2017 + Allen 2004, Rome IV criteria Venkatesan 2019, capsaicin Dezieck 2017, cyclic-vomiting differential / epidemiology Kim 2018). Topic-keyword detector. `to_claim()` method. | ~360 |
| `tests/test_hyperemesis_syndrome.py` | Shape, primary-citation, detector positive/negative, claim round-trip, integration-with-static-caution coexistence (caution remains; rows co-fire), freshness. | ~240 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_hyperemesis_syndrome_mention(prompt)`. Same wiring as US1. Renders as `## Cannabinoid hyperemesis syndrome registry` section. Trace counter `registry.hyperemesis_syndrome`. |
| `cannavec_science/__main__.py` | Add `hyperemesis_syndrome` to registry-subcommand handler. |

### US4 — eCBome enzyme-inhibitor pharmacology registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/ecbome_inhibitors.py` | 5-row registry (PF-04457845 cannabis withdrawal D'Souza 2019, PF-04457845 OA-pain Huggins 2012, BIA 10-2474 disaster Kerbrat 2016 with off-target-serine-hydrolase disambiguation, MAGL ABX-1431 Cisar 2018, dual JZL195 Long 2009). Topic-keyword detector. `to_claim()` method. | ~440 |
| `tests/test_ecbome_inhibitors.py` | Shape, primary-citation, detector positive/negative (incl. BIA-10-2474-as-off-target test), claim round-trip, integration-with-ecbome-reference coexistence (eCBome reference + inhibitor rows co-fire), freshness. | ~280 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_ecbome_inhibitor_mention(prompt)`. Same wiring as US1. Renders as `## eCBome inhibitor pharmacology registry` section. Trace counter `registry.ecbome_inhibitors`. |
| `cannavec_science/__main__.py` | Add `ecbome_inhibitors` to registry-subcommand handler. |

### US5 — Cannabinoid biosynthesis pathway registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/biosynthesis.py` | 5-row registry (OLS / OAC Taura 2009 + Gagne 2012, CBGAS prenyltransferase Page 2011, THCA synthase Sirikantaramas 2004, CBDA synthase Taura 1996, yeast heterologous Luo 2019). Topic-keyword detector. `to_claim()` method. | ~420 |
| `tests/test_biosynthesis.py` | Shape, primary-citation, detector positive/negative, claim round-trip, integration-with-cultivation-science coexistence (synthase-genetics chemotype-inheritance rows + biosynthesis-enzymology rows co-fire), freshness. | ~280 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_biosynthesis_mention(prompt)`. Same wiring as US1. Renders as `## Cannabinoid biosynthesis pathway registry` section. Trace counter `registry.biosynthesis`. |
| `cannavec_science/__main__.py` | Add `biosynthesis` to registry-subcommand handler. |

### US6 — Europe PMC live-discovery lane

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/europepmc_discover.py` | Europe PMC `restful` API client with injected fetcher. Same shape as `pubmed_search.py`. Deterministic JSON parser. Provisional GRADE assignment. | ~340 |
| `tests/test_europepmc_discover.py` | Shape, fixture-based parse, offline-no-network assertion, error-path (HTTP 403 / network unavailable surfacing the `live source unavailable` marker), provenance-tag assertion (`live_europepmc`). | ~230 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/__main__.py` | `discover` subcommand learns `--include-europepmc` flag. Fan-out lane appended. Source-health probe added. |
| `cannavec_science/source_health.py` | Add `europepmc` probe entry. |
| `cannavec_science/synthesis.py` | Cross-source synthesis layer counts the new `live_europepmc` lane (no logic change beyond bookkeeping). |
| `tests/test_cli_source_health.py` | Assert `europepmc` row appears in `source-health` output. |
| `tests/test_synthesis.py` | Assert cross-source synthesis accepts an `europepmc` lane row. |

### US7 — Registry inventory wiring

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/registries.py` | Add five builder functions (`_build_pharmacokinetics`, `_build_use_disorder`, `_build_hyperemesis_syndrome`, `_build_ecbome_inhibitors`, `_build_biosynthesis`). Append names to `all_registry_groups()` and `_BUILDERS`. |
| `tests/test_registries.py` | Add tests asserting the five new groups appear in default inventory and via direct lookup; bump total-row assertion (11 → 16). |

### US8 — Evals + version + README

**Modified:**

| File | Change |
|---|---|
| `evals/canonical_research_questions.json` | Add ≥ 16 prompts in a new `clinical_pharmacology_depth` bucket. Add ≥ 2 Europe PMC prompts in `live` bucket. Add `clinical_pharmacology_depth: 14` to `category_minimums`. |
| `evals/run_evals.py` | No code change — runner already drives bucket-minimum enforcement from JSON. |
| `tests/test_eval_coverage.py` | Bump per-bucket assertions / total-prompt assertion (≥ 162 prompts, offline ≥ 149). |
| `.claude-plugin/plugin.json` | Version → `0.5.0`. Description gains v0.5 deliverables. Keywords expanded. |
| `pyproject.toml` | Version → `0.5.0`. Description gains v0.5 deliverables. |
| `cannavec_science/__init__.py` | `__version__` → `0.5.0`. Docstring updated. |
| `README.md` | Replace "v0.4" headline with "v0.5". Add a "What v0.5 ships" section. Add v0.5 quickstart prompts. |
| `docs/V05_RATING_DELTA.md` | New file — v0.5 industry-expert rating delta summary. |
| `docs/DEMO_SCRIPT.md` | Add a v0.5 demo block. |

## Module Architecture (v0.5 additions only)

```
cannavec_science/
├── pharmacokinetics.py      # v0.5 — THC/CBD ADME, food effect, 11-OH-THC
├── use_disorder.py          # v0.5 — DSM-5 CUD, CUDIT-R, CWS, prevalence
├── hyperemesis_syndrome.py  # v0.5 — CHS dx criteria, capsaicin treatment
├── ecbome_inhibitors.py     # v0.5 — FAAH/MAGL drug development translation
├── biosynthesis.py          # v0.5 — OLS/OAC/PT/THCAS/CBDAS pathway
├── europepmc_discover.py    # v0.5 — twelfth primary-source live lane
└── (everything else unchanged from v0.4)
```

## Public CLI Surface (v0.5 additions)

`python -m cannavec_science <subcommand>`:

- `answer` — surfaces pharmacokinetics / use-disorder / hyperemesis /
  eCBome-inhibitor / biosynthesis rows when the prompt names a covered
  topic.
- `discover` — gains `--include-europepmc` flag (default off; opt-in
  the same way `--include-pubchem` etc. work).
- `registries [--registry pharmacokinetics|use_disorder|hyperemesis_syndrome|ecbome_inhibitors|biosynthesis]`
  — the five new groups appear.
- `source-health` — `europepmc` row added.

No new slash command. No new top-level subcommand. The v0.5 surface is
**purely deeper** in the existing surfaces — Constitution §IV remains
intact.

## Trade-offs & Decisions

1. **Five new registry modules vs one combined "clinical_depth"
   module.** Each registry has its own primary-literature corpus,
   topic vocabulary, and detector. Combining them would create a
   600+ line file that handles five orthogonal topics — harder to
   review, harder to extend in v0.6. Five small modules mirror the
   existing pattern (adverse_events, contraindications, populations,
   pharmacogenomics, ecbome, analytical_chemistry, cultivation_science
   are each their own module).

2. **Europe PMC as a `discover` flag, not a new subcommand.** The
   five-slash-command lock (Constitution §IV) holds. Europe PMC is a
   sibling live-source lane — same shape as the existing
   `--include-pubchem` / `--include-pharmgkb` / `--include-rcsb` opt-in
   flags. The cross-source synthesis layer counts it; the bookkeeping
   work is in `synthesis.py`.

3. **BIA 10-2474 row carries explicit off-target disambiguation.**
   The BIA 10-2474 Phase 1 disaster is famous in the press as "FAAH
   inhibitor killed someone" but the actual toxicology (van Esbroeck
   2017 PMID 28912346) attributes the disaster to off-target serine
   hydrolase inhibition (BIA 10-2474 is a poor-quality FAAH inhibitor
   with poor selectivity). The registry row makes this disambiguation
   explicit because a researcher who confuses BIA 10-2474 toxicology
   with on-target FAAH biology will reach wrong drug-development
   conclusions. This is the row's most important pedagogical value.

4. **CUDIT-R citation is the Adamson 2010 paper (PMID 20231083), not
   the WHO 2002 manual.** The instrument originated in the WHO 2002
   AUDIT framework but the cannabis-specific revision is Adamson 2010
   and that's the citation every modern protocol uses.

5. **11-OH-THC PK row mentions the first-pass-effect framing.** The
   reason oral THC produces ~equimolar 11-OH-THC AUC and inhaled THC
   produces ~10% 11-OH-THC AUC is the CYP2C9 first-pass effect on the
   oral route. Wall 1983 (PMID 6311559) is the classic paper. The
   row's claim text explicitly mentions this so the researcher does
   not have to chase the explanation in a different surface.

6. **CHS row coexists with the static caution.** v0.4 emits the
   static caution "Cannabis hyperemesis syndrome is paradoxical and
   requires cessation, not adjustment of cannabis use." This is
   useful clinically. v0.5's CHS registry surfaces the primary
   citations the researcher needs without removing the caution.
   Both render side by side. The v0.5 unit test asserts the caution
   remains.

7. **Biosynthesis registry coexists with cultivation-science
   synthase-genetics rows.** Cultivation-science rows (v0.4) cover
   THCA-synthase / CBDA-synthase chemotype inheritance from a
   plant-breeder angle. Biosynthesis rows (v0.5) cover the upstream
   pathway (polyketide origin, OLS / OAC, CBGAS prenyltransferase)
   AND the downstream enzyme mechanism (Sirikantaramas 2004 THCAS
   FAD-dependent oxidocyclase, Taura 1996 CBDAS characterisation).
   Complementary — chemotype-inheritance vs enzyme-mechanism.

8. **Europe PMC offline-test contract.** Like every existing live
   discover module, Europe PMC uses an injected `fetch` callable that
   defaults to `urllib.request.urlopen` in production but is replaced
   by a fixture in tests. No network calls escape the test suite. The
   fixture canned-response shape mirrors a real Europe PMC REST API
   JSON response.

## Implementation Order

1. **US1 — pharmacokinetics registry** (1 new module + tests).
2. **US2 — use_disorder registry** (1 new module + tests).
3. **US3 — hyperemesis_syndrome registry** (1 new module + tests).
4. **US4 — ecbome_inhibitors registry** (1 new module + tests).
5. **US5 — biosynthesis registry** (1 new module + tests).
6. **US6 — Europe PMC discover lane** (1 new module + tests +
   discover-CLI wiring + source-health + synthesis bookkeeping).
7. **`compose_answer` wiring** for the five new registries.
8. **US7 — registry inventory wiring** (5 builders + tests).
9. **US8 — evals + version + README + docs**.
10. **Final regression**: `python3 -m unittest discover -s tests`
    exits 0 with ≥ 1,330 tests. `python3 evals/run_evals.py` exits 0
    with ≥ 149 offline / ≥ 162 total prompts.
11. **Commit + push to `claude/exciting-shannon-cMhTQ`**.

## Acceptance Gate

Before pushing the v0.5 branch, ALL of the following MUST hold:

- `python3 -m unittest discover -s tests` exits 0, ≥ 1,330 tests, ≤ 5 s.
- `python3 evals/run_evals.py` exits 0, ≥ 162 prompts (offline ≥ 149),
  every bucket meets its minimum.
- `python3 -m cannavec_science answer "THC inhaled vs oral
  pharmacokinetics Tmax Cmax"` returns ≥ 2 Level C/D claims with
  primary citations.
- `python3 -m cannavec_science answer "cannabis withdrawal syndrome
  assessment scale"` returns ≥ 1 Level C claim citing Allsop 2011.
- `python3 -m cannavec_science answer "cannabinoid hyperemesis
  syndrome diagnostic criteria"` returns ≥ 2 Level C claims.
- `python3 -m cannavec_science answer "PF-04457845 FAAH inhibitor
  cannabis withdrawal NEJM"` returns ≥ 1 Level B claim citing D'Souza
  2019.
- `python3 -m cannavec_science answer "olivetolic acid synthase
  polyketide pathway biosynthesis"` returns ≥ 1 Level C claim citing
  Taura 2009.
- `python3 -m cannavec_science discover "nabiximols European
  approval" --include-europepmc` includes the `live_europepmc` lane.
- `python3 -m cannavec_science registries` lists all 16 groups.
- `.claude-plugin/plugin.json` / `pyproject.toml` /
  `cannavec_science/__init__.py` all report `0.5.0`.
- Total Python LOC under `cannavec_science/` stays under 35,000.
- The total slash-command count remains exactly **five**.

## Risks & Mitigations

- **Risk**: A pharmacokinetics row's claim_text mentions "THC" without
  the Δ⁹- prefix and trips the phytochemistry-precision rigor detector.
  **Mitigation**: every PK row uses Δ⁹-THC / 11-OH-Δ⁹-THC isomer
  naming; each row's `to_claim()` is unit-tested against
  `rigor_checks.detect_all_violations` to assert clean.
- **Risk**: The CUD registry's DSM-5 row trips an audience-out-of-scope
  classification because DSM-5 is a clinical diagnostic framework.
  **Mitigation**: DSM-5 is research-grade for the *researcher* audience
  — addiction-medicine outcome trials cite it as the primary outcome
  framework. The row's claim_text frames it as research-grade
  literature (Hasin 2013) not as a clinician-facing diagnostic tool.
- **Risk**: The CHS row's claim_text duplicates the static caution
  wording, creating a confusing double-render.
  **Mitigation**: row claim_text avoids the caution's exact wording
  ("paradoxical and requires cessation") and instead surfaces the
  diagnostic-criteria / treatment evidence. A unit test asserts the
  two surfaces do not collide.
- **Risk**: The BIA 10-2474 row is misinterpreted as "FAAH inhibition
  is unsafe" without the off-target context.
  **Mitigation**: claim_text leads with "The BIA 10-2474 toxicity is
  attributed to OFF-TARGET serine-hydrolase inhibition, NOT to
  on-target FAAH biology" and cites van Esbroeck 2017 (PMID 28912346)
  alongside Kerbrat 2016. A unit test asserts the off-target disambiguation
  string is in the claim.
- **Risk**: The biosynthesis registry's THCA-synthase mechanism row
  conflicts with the cultivation-science synthase-genetics row.
  **Mitigation**: the rows target different audiences inside the
  researcher lock — biosynthesis covers enzyme mechanism (FAD-dependent
  oxidocyclase, kinetic parameters), cultivation-science covers
  chemotype inheritance (Type I / II / III / IV / V allelic basis).
  Both detectors fire on different keyword sets; both rows surface
  side by side. A unit test asserts the coexistence.
- **Risk**: Europe PMC live-lane defaults change PubMed coverage.
  **Mitigation**: Europe PMC is opt-in via `--include-europepmc`. The
  default `discover` invocation continues to call PubMed / ChEMBL /
  CT.gov only. No regression to existing `discover` behaviour.
- **Risk**: Eval bucket assertion overshoots and a legitimate v0.5
  registry change breaks the regression.
  **Mitigation**: bucket minimum is 14 with 16 prompts shipping —
  14% headroom.
- **Risk**: Total LOC overshoots the 35,000 ceiling.
  **Mitigation**: Each new module is ~360-600 LOC; total v0.5
  additions ≈ 2,640 LOC. v0.4 baseline ≈ 26,500. v0.5 projected ≈
  29,140 — well under the 35,000 ceiling.
