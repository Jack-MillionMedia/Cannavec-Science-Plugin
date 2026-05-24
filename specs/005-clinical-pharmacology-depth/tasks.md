# Implementation Tasks: Cannavec Science v0.5 Clinical-Pharmacology Depth

**Spec**: [`spec.md`](./spec.md)

**Plan**: [`plan.md`](./plan.md)

**Status**: Shipped — all tasks complete on `claude/exciting-shannon-cMhTQ`.

## Acceptance Snapshot

| Gate | v0.4 (shipped) | v0.5 (shipped) |
|---|---|---|
| Unit tests | 1,228 | **1,369** (+141) |
| Eval prompts (total) | 144 | **162** (+18) |
| Eval prompts (offline) | 133 | **149** (+16) |
| Curated registries | 11 | **16** (+5) |
| Live discover lanes | 11 | **12** (+europepmc) |
| Curated rows total | 159 | **187** (+28) |
| Version stamp | 0.4.0 | **0.5.0** |
| Python LOC (cannavec_science/) | ~26,500 | 30,667 (under 35k ceiling) |
| Slash command count | 5 | **5** (unchanged) |

## Task List (ordered by execution sequence)

### T1 — US1: Pharmacokinetics registry

- [x] `cannavec_science/pharmacokinetics.py`: new module, ≥ 8 curated
      rows across 7 topics (inhaled_pk × 2, oral_pk × 1, food_effect × 1,
      active_metabolite × 1, oromucosal_pk × 1, distribution × 1,
      detection_window × 1). Each row carries `to_claim()` returning a
      typed `Claim`, identifier-anchored citations per §I, and a
      topic-keyword regex detector.
- [x] `tests/test_pharmacokinetics.py`: new file, ≥ 24 tests covering
      shape, validation, detection (positive + negative), claim
      round-trip, isomer-disambiguation cleanliness (Δ⁹-THC and
      11-OH-Δ⁹-THC named correctly), renderer, freshness, and
      coexistence with the major-cannabinoid monograph.

### T2 — US2: Cannabis use disorder & withdrawal registry

- [x] `cannavec_science/use_disorder.py`: new module, ≥ 6 curated rows
      across 6 topics (dsm5_criteria × 1, screening_instrument × 1,
      withdrawal_scale × 1, prevalence × 1, heritability × 1,
      age_of_onset × 1). Each row carries `to_claim()`, identifier-
      anchored citations per §I, and a topic-keyword detector.
- [x] `tests/test_use_disorder.py`: new file, ≥ 22 tests covering shape,
      validation, detection, claim round-trip, integration with the
      existing adverse-events Volkow 2014 CUD-risk row (both fire
      cleanly), and freshness.

### T3 — US3: Cannabinoid hyperemesis syndrome registry

- [x] `cannavec_science/hyperemesis_syndrome.py`: new module, ≥ 4
      curated rows across 4 topics (diagnostic_criteria × 1, rome_iv × 1,
      capsaicin_treatment × 1, cyclic_vomiting_dx + epidemiology × 1).
      Each row carries `to_claim()`, identifier-anchored citations per
      §I, and a topic-keyword detector.
- [x] `tests/test_hyperemesis_syndrome.py`: new file, ≥ 16 tests
      covering shape, validation, detection, claim round-trip,
      integration with the existing static CHS caution (caution
      remains; row fires alongside), and freshness.

### T4 — US4: eCBome enzyme-inhibitor pharmacology registry

- [x] `cannavec_science/ecbome_inhibitors.py`: new module, ≥ 5 curated
      rows across 4 topics (faah_inhibitor_efficacy × 2,
      faah_inhibitor_safety_disaster × 1, magl_inhibitor × 1,
      dual_inhibitor × 1). Each row carries `to_claim()`, identifier-
      anchored citations per §I, and a topic-keyword detector. The BIA
      10-2474 row carries the off-target serine-hydrolase
      disambiguation explicitly.
- [x] `tests/test_ecbome_inhibitors.py`: new file, ≥ 20 tests covering
      shape, validation, detection, claim round-trip, the BIA-10-2474
      off-target-disambiguation assertion, integration with the
      existing eCBome reference registry (both surfaces co-fire), and
      freshness.

### T5 — US5: Cannabinoid biosynthesis pathway registry

- [x] `cannavec_science/biosynthesis.py`: new module, ≥ 5 curated rows
      across 4 topics (polyketide_origin × 1, prenyltransferase × 1,
      acid_synthase × 2, heterologous_expression × 1). Each row carries
      `to_claim()`, identifier-anchored citations per §I, and a
      topic-keyword detector.
- [x] `tests/test_biosynthesis.py`: new file, ≥ 20 tests covering
      shape, validation, detection, claim round-trip, integration with
      the cultivation-science synthase-genetics chemotype-inheritance
      row (both fire cleanly — distinct topics), and freshness.

### T6 — US6: Europe PMC live-discovery lane

- [x] `cannavec_science/europepmc_discover.py`: new module, Europe PMC
      REST API client with injected fetcher, deterministic JSON parser,
      provisional GRADE assignment, `live_europepmc` provenance tag.
- [x] `tests/test_europepmc_discover.py`: new file, ≥ 14 tests covering
      shape, fixture-based parse, no-network assertion, error-path
      (offline / 403 / 5xx surfacing the source-unavailable marker),
      provenance-tag assertion.
- [x] `cannavec_science/__main__.py`: `discover` subcommand learns
      `--include-europepmc` flag. Fan-out lane appended.
- [x] `cannavec_science/source_health.py`: add `europepmc` probe entry.
- [x] `cannavec_science/synthesis.py`: cross-source synthesis layer
      counts the new lane (bookkeeping only).
- [x] `tests/test_cli_source_health.py`: assert `europepmc` row appears.
- [x] `tests/test_synthesis.py`: assert cross-source synthesis accepts
      an `europepmc` lane row.

### T7 — `compose_answer` wiring

- [x] `cannavec_science/answer.py`: import + call the five new
      detectors. Rows attach citations regardless of refusal; claims
      attach when not refused. Render each as its own dedicated
      registry section. Trace counters added for each.

### T8 — US7: Registry inventory wiring

- [x] `cannavec_science/registries.py`: new five `_build_*` functions;
      five names added to `all_registry_groups()` and `_BUILDERS`.
- [x] `cannavec_science/__main__.py`: --registry help text lists the
      five new names.
- [x] `tests/test_registries.py`: assertions bumped to 16 groups (was
      11); add ≥ 6 tests asserting the new groups appear with row
      counts and entry labels.

### T9 — US8: Eval bucket + version bump

- [x] `evals/canonical_research_questions.json`: ≥ 16 prompts in new
      `clinical_pharmacology_depth` bucket; ≥ 2 Europe PMC prompts in
      `live` bucket. Bucket minimum `clinical_pharmacology_depth: 14`
      added.
- [x] `tests/test_eval_coverage.py`: new assertions for the
      `clinical_pharmacology_depth` minimum + the ≥ 162 total-prompt
      assertion + the ≥ 149 offline-prompt assertion.
- [x] `.claude-plugin/plugin.json` version → `0.5.0`, description
      updated, keywords expanded.
- [x] `pyproject.toml` version → `0.5.0`, description updated,
      keywords expanded.
- [x] `cannavec_science/__init__.py` `__version__` → `0.5.0`,
      docstring updated.
- [x] `README.md` headline replaced; "What v0.5 ships" section added;
      v0.5 quickstart block added; test/eval counts bumped.

### T10 — Documentation

- [x] `docs/V05_RATING_DELTA.md`: new file summarising the v0.5
      industry-expert rating delta.
- [x] `docs/DEMO_SCRIPT.md`: v0.5 demo block appended.

### T11 — Final regression + push

- [x] `python3 -m unittest discover -s tests` exits 0 with ≥ 1,330
      tests passing, ≤ 5 s runtime.
- [x] `python3 evals/run_evals.py` exits 0 with ≥ 149/149 pass offline.
- [x] Commit + push to `claude/exciting-shannon-cMhTQ`.

## Verification Commands

```bash
# Confirms test + eval suites still green.
python3 -m unittest discover -s tests | tail -3
python3 evals/run_evals.py | tail -15

# v0.5 acceptance smokes.
python3 -m cannavec_science answer "THC inhaled vs oral pharmacokinetics Tmax Cmax"
python3 -m cannavec_science answer "CBD epidiolex food effect AUC fivefold high fat meal"
python3 -m cannavec_science answer "11-hydroxy-THC active metabolite oral dronabinol"
python3 -m cannavec_science answer "cannabis use disorder DSM-5 criteria"
python3 -m cannavec_science answer "cannabis withdrawal syndrome assessment scale"
python3 -m cannavec_science answer "cannabinoid hyperemesis syndrome diagnostic criteria"
python3 -m cannavec_science answer "PF-04457845 FAAH inhibitor cannabis withdrawal NEJM"
python3 -m cannavec_science answer "BIA 10-2474 Rennes Phase 1 disaster off-target"
python3 -m cannavec_science answer "olivetolic acid synthase polyketide pathway biosynthesis"
python3 -m cannavec_science answer "Luo 2019 yeast cannabinoid heterologous expression Nature"
python3 -m cannavec_science discover "nabiximols European approval" --include-europepmc
python3 -m cannavec_science registries
python3 -m cannavec_science registries --registry pharmacokinetics
python3 -m cannavec_science registries --registry use_disorder
python3 -m cannavec_science registries --registry hyperemesis_syndrome
python3 -m cannavec_science registries --registry ecbome_inhibitors
python3 -m cannavec_science registries --registry biosynthesis
```

## Constitutional Posture

This release is **in-constitution** (no amendment required). The five
new registries are research-grade primary-literature topics that sit
inside §IV (researcher-only) — same posture as the v0.4
analytical-chemistry / cultivation-science promotion. Europe PMC is a
twelfth primary-source live lane operating under the same §IX
contract as the existing eleven (provenance tags, deterministic
synthesis verdict, no auto-promotion to curated tier, offline-safe
injected fetcher). The notes-render and banned-pattern fixes from v0.4
remain intact; the safety preflight, K2/Spice hard-refuse, retraction
enforcement at composition, GRADE wording-vs-grade consistency, and
span-aware named-cannabinoid resolution remain intact.
