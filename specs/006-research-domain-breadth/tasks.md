# Tasks: v0.6 Research-Domain Breadth & Rigor Extensions

Tasks are ordered by dependency. Test-writing tasks come before
implementation tasks for the same module per Constitution §III.

## US1 — Pain medicine registry

- **T001**: Write `tests/test_pain_medicine.py` with positive +
  negative assertions for each topic (NASEM finding, Whiting SR,
  Stockings SR, Mücke Cochrane, Boehnke cohort, Andreae IPD-MA,
  de Vita SR). Run → confirm failure (module missing).
- **T002**: Implement `cannavec_science/pain_medicine.py` per the
  plan. Run T001 → pass.

## US2 — Psychiatry / psychosis registry

- **T003**: Write `tests/test_psychiatry.py`. Run → fail.
- **T004**: Implement `cannavec_science/psychiatry.py`. Run T003
  → pass.

## US3 — Driving-impairment registry

- **T005**: Write `tests/test_driving_impairment.py`. Run → fail.
- **T006**: Implement `cannavec_science/driving_impairment.py`. Run
  T005 → pass.

## US4 — PTSD / anxiety / sleep registry

- **T007**: Write `tests/test_ptsd_anxiety_sleep.py`. Run → fail.
- **T008**: Implement `cannavec_science/ptsd_anxiety_sleep.py`. Run
  T007 → pass.

## US5 — Reporting-rigor module

- **T009**: Write `tests/test_reporting_rigor.py` for CONSORT,
  PRISMA, STROBE, ROB-2, ROBINS-I, AMSTAR-2 detectors with positive
  + negative tests. Run → fail.
- **T010**: Implement `cannavec_science/reporting_rigor.py`. Run
  T009 → pass.
- **T011**: Modify `cannavec_science/rigor_checks.py` to include
  reporting-rigor in `RigorCheckReport` and `run_rigor_checks()`.
  Add a test in `tests/test_rigor_checks_extensions.py` for the
  integration. Run → pass.

## US6 — OpenAlex live-discovery

- **T012**: Write `tests/test_openalex_discover.py` (search,
  parsing, fixture-injection, provenance tagging). Run → fail.
- **T013**: Implement `cannavec_science/openalex_discover.py`. Run
  T012 → pass.
- **T014**: Wire OpenAlex into `__main__.py` (`--include-openalex`),
  `discover_guard.py` (source-name handling), and `source_health.py`
  (probe). Add a test in `tests/test_source_health.py` for the
  OpenAlex probe. Run → pass.

## US7 — Registry inventory wire-up

- **T015**: Modify `cannavec_science/registries.py` to add four
  builder functions and entries in `all_registry_groups()` /
  `_BUILDERS`.
- **T016**: Update `tests/test_registries.py` to assert all 20
  groups are present and each has the expected entries / row count.
  Run → pass.

## US8 — Composer wire-up + eval coverage

- **T017**: Write `tests/test_spec_006_routing.py` exercising end-
  to-end `compose_answer()` for at least one prompt in each of the
  four new registries; assert claim counts ≥ FR-001 through FR-004
  minimums. Run → fail.
- **T018**: Modify `cannavec_science/answer.py` to add the four new
  detector imports, trace counters, citation attachments, and claim
  attachments. Run T017 → pass.
- **T019**: Update `evals/canonical_research_questions.json`:
  - Add `"research_domain_breadth": 16` to `category_minimums`.
  - Add ≥ 18 prompts to `prompts` with `"category":
    "research_domain_breadth"`.
  - Add ≥ 5 reporting-rigor prompts to `rigor_positive` bucket.
  - Add ≥ 2 OpenAlex prompts to `live` bucket.
- **T020**: Update `tests/test_eval_coverage.py` to:
  - Assert `research_domain_breadth` bucket min ≥ 16.
  - Assert total prompts ≥ 187 (offline ≥ 172).
  Run → pass.
- **T021**: Run `python3 evals/run_evals.py --strict-coverage`
  → exit 0.

## US? — Version + docs

- **T022**: Bump version in `.claude-plugin/plugin.json`,
  `pyproject.toml`, `cannavec_science/__init__.py` to `0.6.0`.
- **T023**: Update `README.md` with a v0.6 section; preserve v0.5 /
  v0.4 / v0.3 / v0.2 / v0.1 sections.
- **T024**: Write `docs/V06_RATING_DELTA.md` summary.

## Final gates

- **T025**: Run `python3 -m unittest discover -s tests` →
  ≥ 1,460 tests pass, ≤ 6 s total.
- **T026**: Run `python3 -m cannavec_science answer "chronic pain
  cannabis Whiting 2015 JAMA"` and confirm ≥ 1 Level A claim. Run
  the other SC-001 → SC-013 spot checks from spec.md.
- **T027**: Commit + push to `claude/modest-knuth-PUits` with the
  release-tagged feat(006) message.
