# Implementation Plan: v0.6 Research-Domain Breadth & Rigor Extensions

**Spec**: `specs/006-research-domain-breadth/spec.md`

**Status**: Approved for `/speckit-tasks` and immediate implementation

## Architecture

v0.6 mirrors the v0.5 architecture exactly. Four new curated-registry
modules + one new rigor module + one new live-discovery module + the
glue work. Stdlib-only. Test-first per Constitution §III.

```
cannavec_science/
├── pain_medicine.py            (NEW, US1)
├── psychiatry.py               (NEW, US2)
├── driving_impairment.py       (NEW, US3)
├── ptsd_anxiety_sleep.py       (NEW, US4)
├── reporting_rigor.py          (NEW, US5)
├── openalex_discover.py        (NEW, US6)
├── registries.py               (MODIFIED — 4 builders, all_registry_groups, _BUILDERS)
├── answer.py                   (MODIFIED — 4 detector imports, 4 trace counters,
                                  4 row-claim attachments, reporting-rigor pass-through)
├── rigor_checks.py             (MODIFIED — RigorCheckReport gains reporting-rigor field)
├── discover_guard.py           (MODIFIED — openalex source name handling)
├── source_health.py            (MODIFIED — openalex probe)
├── __init__.py                 (MODIFIED — version 0.6.0)
└── __main__.py                 (MODIFIED — --include-openalex flag)

tests/
├── test_pain_medicine.py       (NEW)
├── test_psychiatry.py          (NEW)
├── test_driving_impairment.py  (NEW)
├── test_ptsd_anxiety_sleep.py  (NEW)
├── test_reporting_rigor.py     (NEW)
├── test_openalex_discover.py   (NEW)
├── test_spec_006_routing.py    (NEW — composer integration tests)
├── test_registries.py          (MODIFIED — 4 new groups)
├── test_eval_coverage.py       (MODIFIED — research_domain_breadth ≥ 16)
└── test_source_health.py       (MODIFIED — openalex probe)

evals/
└── canonical_research_questions.json   (MODIFIED — +18 research_domain_breadth,
                                         +5 rigor_positive reporting-rigor,
                                         +2 live OpenAlex)

specs/006-research-domain-breadth/
├── spec.md                     (DONE)
├── plan.md                     (this file)
└── tasks.md                    (NEXT)

.claude-plugin/plugin.json      (MODIFIED — version 0.6.0)
pyproject.toml                  (MODIFIED — version 0.6.0)
README.md                       (MODIFIED — v0.6 section + preserved v0.5)
docs/V06_RATING_DELTA.md        (NEW)
```

## Module shapes (mirror v0.5 exactly)

### `pain_medicine.py`
- `PainMedicineCitation` dataclass (label + pmid|doi + year).
- `PainMedicineRow` dataclass:
  - Required: `name`, `topic`, `claim_text`, `claim_type`,
    `evidence_level`, `source_tier`, `citations` (≥ 1, ≥ 1 PMID/DOI).
  - Optional: `population` (chronic-pain / neuropathic / experimental),
    `n_patients` (int), `key_finding_summary`, `last_verified`,
    `watch_pmids`, `key_notes`.
  - `to_claim()` returns a typed `Claim` via the standard
    `Source(...)` constructor.
  - `__post_init__` enforces §I (≥ 1 citation, each with PMID or DOI).
- `PainMedicineTopic` constants:
  `NASEM_FINDING`, `SR_CHRONIC_PAIN`, `SR_NEUROPATHIC`,
  `COCHRANE_REVIEW`, `COHORT_OBSERVATIONAL`, `IPD_META_ANALYSIS`,
  `EXPERIMENTAL_PAIN`.
- `_REGISTRY` tuple of ≥ 7 rows.
- `all_pain_medicine_rows()`, `find_pain_medicine_rows(name_or_topic)`,
  `detect_pain_medicine_mention(text)` topic-keyword regex matcher
  returning rows whose topic matches.
- `render_markdown(rows)` for the composer.

### `psychiatry.py`
- Same shape. `PsychiatryRow` has `study_design` (case_control /
  meta_analysis / mendelian_randomization / acute_pharmacology /
  national_register / narrative_review).
- Topics: `CASE_CONTROL_PSYCHOSIS`, `DOSE_RESPONSE_SR`,
  `MR_CAUSALITY`, `ACUTE_PHARMACOLOGY`, `NATIONAL_COHORT`,
  `REVIEW_LANCET`.
- ≥ 6 rows.

### `driving_impairment.py`
- Same shape. `DrivingImpairmentRow` has `matrix` (plasma / whole-
  blood / oral-fluid / device-screen) and `key_finding_summary`.
- Topics: `CASE_CONTROL_CRASH`, `PLASMA_DOSE_RESPONSE`,
  `SIMULATOR_RCT`, `PROSPECTIVE_COHORT_CRASH`, `SYSTEMATIC_REVIEW`.
- ≥ 5 rows.
- NOTE: NHTSA report is cited by DOT HS report number (not PMID).
  The `PainMedicineCitation` shape supports DOI-only; the
  `DrivingImpairmentCitation` supports a `report_id` field as a
  third identifier (DOT HS 812 411 for Compton 2017). §I is still
  satisfied because Compton 2017 NHTSA report is a verifiable
  primary government publication with a stable identifier.

### `ptsd_anxiety_sleep.py`
- Same shape. `PtsdAnxietySleepRow` has `indication` (PTSD / SAD /
  sleep / acute-anxiety) and `key_finding_summary`.
- Topics: `PTSD_RCT`, `SAD_ACUTE_CHALLENGE`, `SLEEP_SR`,
  `ACUTE_ANXIETY_DOSE_RESPONSE`.
- ≥ 5 rows.

### `reporting_rigor.py` (rigor extension, not a registry)
- `ReportingGuideline` enum: `CONSORT`, `PRISMA`, `STROBE`, `STARD`,
  `CHEERS`, `ROB_2`, `ROBINS_I`, `AMSTAR_2`, `QUADAS_2`.
- `ReportingGuidelineViolation` dataclass:
  `kind` (ReportingGuideline), `span` (start, end), `why`,
  `recommendation_pmid`, `anchor_text` (matched trigger).
- Detectors (one per guideline):
  - `detect_missing_consort(text)` — fires when text mentions
    randomized trial / RCT language without CONSORT mention.
  - `detect_missing_prisma(text)` — fires on systematic review /
    meta-analysis language without PRISMA mention.
  - `detect_missing_strobe(text)` — fires on observational / cohort
    / case-control language without STROBE.
  - `detect_missing_rob2(text)` — fires when prompt requests bias
    appraisal of an RCT without naming ROB-2 / Cochrane RoB 2.
  - `detect_missing_robins_i(text)` — fires when prompt requests bias
    appraisal of a non-randomized intervention study without naming
    ROBINS-I.
  - `detect_missing_amstar2(text)` — fires when prompt requests
    quality appraisal of a systematic review without naming AMSTAR-2.
- All detectors are deterministic regex pairs:
  - **trigger** regex (study-design language) AND
  - **acknowledgment** regex (guideline / tool mention) — if BOTH
    fire, the detector is silent; if only TRIGGER fires, the
    detector raises a violation.
- `run_reporting_rigor_checks(text)` → tuple of violations.
- Integrates into `rigor_checks.RigorCheckReport` as
  `reporting_rigor_violations`. The existing `run_rigor_checks()`
  function calls it.

### `openalex_discover.py`
- `OPENALEX_BASE_URL = "https://api.openalex.org/works"`.
- `search(query, *, limit=25, fetch=urlopen)` returns a tuple of
  parsed dicts. Each dict has: `id` (OpenAlex W-ID), `title`,
  `doi`, `pmid` (if mapped), `year`, `authors`, `cited_by_count`,
  `topic_concepts` (top 3 concepts).
- `to_provenance_rows(items)` returns rows with `provenance =
  "live_openalex"` and `provisional_grade = "Level D (live)"`.
- Offline-safe: every test injects a `fetch` callable returning a
  canned JSON byte payload.
- Source-health probe: `probe()` calls a short `search("test",
  limit=1)` against the injected fetcher.

## Composer wire-up (answer.py)

Add inside the existing `_compose_internal()` after the spec-005
imports:

```python
# Spec 006 US1-US4 / FR-006 — research-domain-breadth registries.
from cannavec_science.pain_medicine import detect_pain_medicine_mention
from cannavec_science.psychiatry import detect_psychiatry_mention
from cannavec_science.driving_impairment import (
    detect_driving_impairment_mention,
)
from cannavec_science.ptsd_anxiety_sleep import (
    detect_ptsd_anxiety_sleep_mention,
)
matched_pain_rows = detect_pain_medicine_mention(prompt)
matched_psych_rows = detect_psychiatry_mention(prompt)
matched_driving_rows = detect_driving_impairment_mention(prompt)
matched_ptsd_rows = detect_ptsd_anxiety_sleep_mention(prompt)
```

Trace counters:
```python
a.add_trace("registry.pain_medicine", len(matched_pain_rows))
a.add_trace("registry.psychiatry", len(matched_psych_rows))
a.add_trace("registry.driving_impairment", len(matched_driving_rows))
a.add_trace("registry.ptsd_anxiety_sleep", len(matched_ptsd_rows))
```

Citation attachment + claim attachment follow the existing pattern.

## Registries.py wire-up

Append to `all_registry_groups()`:
```python
"pain_medicine",
"psychiatry",
"driving_impairment",
"ptsd_anxiety_sleep",
```

Add four builders:
```python
def _build_pain_medicine() -> RegistryGroup:
    from cannavec_science.pain_medicine import all_pain_medicine_rows
    rows = all_pain_medicine_rows()
    entries = tuple(sorted({f"{r.topic}: {r.name}" for r in rows}))
    return RegistryGroup(
        name="pain_medicine",
        label="Pain medicine (v0.6)",
        row_count=len(rows),
        entries=entries,
        last_verified=_latest_last_verified(rows),
    )
```
... and analogous for the other three.

Append to `_BUILDERS`:
```python
"pain_medicine": _build_pain_medicine,
"psychiatry": _build_psychiatry,
"driving_impairment": _build_driving_impairment,
"ptsd_anxiety_sleep": _build_ptsd_anxiety_sleep,
```

## Rigor.py wire-up (rigor_checks.py)

`RigorCheckReport` gains:
```python
reporting_rigor_violations: tuple[ReportingGuidelineViolation, ...] = ()
```

`clean` property includes it. `summary()` renders a
`## Reporting-rigor violations` section.

`run_rigor_checks()` calls `run_reporting_rigor_checks(text)`.

## OpenAlex wire-up

- `__main__.py` discover subcommand learns `--include-openalex`
  similar to `--include-europepmc`.
- `discover_guard.py` (or whichever module maps source names) learns
  `openalex` → `openalex_discover`.
- `source_health.py` adds the OpenAlex probe.

## Eval coverage

`evals/canonical_research_questions.json`:
- Add `"research_domain_breadth": 16` to `category_minimums`.
- Add ≥ 18 prompts to `prompts` with `"category":
  "research_domain_breadth"`.
- Add ≥ 5 reporting-rigor prompts to `rigor_positive` bucket.
- Add ≥ 2 OpenAlex prompts to `live` bucket.

`tests/test_eval_coverage.py`:
- Assert the bucket-minimum table includes
  `research_domain_breadth` and the bucket has ≥ 16 prompts.
- Assert `rigor_positive` floor remains satisfied with the new
  prompts.

## Version + docs

- `cannavec_science/__init__.py`: `__version__ = "0.6.0"`.
- `pyproject.toml`: `version = "0.6.0"`.
- `.claude-plugin/plugin.json`: `"version": "0.6.0"`.
- `README.md`: prepend a v0.6 "research-domain-breadth" section;
  preserve v0.5 / v0.4 sections; document the four new registries +
  reporting-rigor + OpenAlex.
- `docs/V06_RATING_DELTA.md`: short delta-table summary (rows added,
  detectors added, eval count, test count).

## Risk + non-risk

- **Risk**: The reporting-rigor detectors are prompt-level rigor
  checks; they have to be carefully scoped so they don't fire on
  *answers* that the composer already provides. Mitigation: detectors
  only fire when invoked through the `rigor` subcommand on user-
  provided text, not on `answer` output prose.
- **Risk**: The pain-medicine NASEM 2017 row could be confused with
  a clinical-guidance row. Mitigation: claim_text is descriptive of
  what NASEM concluded, NOT a recommendation; evidence-level reflects
  the SR backbone (Whiting 2015).
- **Risk**: The Bonn-Miller 2021 PTSD row could be misread as
  endorsing cannabis for PTSD. Mitigation: the claim_text explicitly
  states the primary endpoints were largely negative, exactly as
  the trial reported.
- **Non-risk**: All four registries are stdlib-only, follow the
  existing dataclass + topic-detector + render_markdown shape. The
  composer wire-up is mechanical.
- **Non-risk**: The OpenAlex fetcher uses the same urllib + injected-
  fetch contract as PubMed and Europe PMC.

## Trace + observability

Every new registry gets a `registry.<name>` trace counter. Every
reporting-rigor violation gets a `rigor.reporting.<kind>` trace
counter. OpenAlex gets `live.openalex.fetch_attempted` /
`live.openalex.fetch_failed` traces.

## Backward compatibility

- The existing rigor-check API (`run_rigor_checks(text)`) returns
  the same `RigorCheckReport` shape; the new field defaults to an
  empty tuple, so existing callers that don't access it see no
  change.
- The four new registries are additive — no existing registry is
  modified. No existing PMID is moved. No existing test's expected
  PMID list is reduced.
- The `--include-openalex` flag is opt-in; default `discover`
  behaviour is identical to v0.5.

## Test ordering (Constitution §III)

Per the constitution, tests are written BEFORE implementation for
new modules. Order per user-story:

1. Write `tests/test_pain_medicine.py` (assertions on row count,
   detector positives/negatives, claim_text shape, banned-pattern
   pass-through). Run → fail.
2. Implement `cannavec_science/pain_medicine.py`. Run → pass.
3. Repeat for psychiatry, driving-impairment, PTSD-anxiety-sleep.
4. Reporting-rigor: write `tests/test_reporting_rigor.py` first,
   then implement.
5. OpenAlex: write `tests/test_openalex_discover.py` first, then
   implement.
6. Composer wire-up: write `tests/test_spec_006_routing.py` first,
   then modify `answer.py`.
7. Registry inventory: update `tests/test_registries.py` first,
   then modify `cannavec_science/registries.py`.
8. Eval coverage: update prompts JSON first, then assert in
   `tests/test_eval_coverage.py`, then run `evals/run_evals.py`
   to verify.

Each step closes with `python3 -m unittest discover -s tests`
green.

## Out of scope for v0.6 (deferred)

The following were considered and explicitly NOT shipped in v0.6:

- **NASEM-2017 full chapter mapping** (chapter-by-chapter conclusive/
  substantial/moderate/limited evidence-level table). v0.6 ships
  the chapter-4 chronic-pain finding only; full mapping is a v0.7
  candidate.
- **Cannabinoid medicines regulatory-science registry** (Epidiolex
  FDA label, Sativex EMA label, nabilone, dronabinol). v0.6 keeps
  the existing single-layer regulatory-feasibility advisory; the
  per-product label-data deepening is a v0.7 candidate.
- **Pharmacovigilance / FAERS** signal-detection methodology surface.
  v0.7 candidate.
- **NASEM-2017 PTSD chapter mapping** (the PTSD "limited evidence"
  finding). The Bonn-Miller 2021 RCT row carries the actual trial
  claim; the NASEM cross-reference is a v0.7 polishing item.
- **Hjorthøj 2023 vs Marconi 2016 attributable-fraction comparison**
  surface (research-question-level synthesis). v0.7 candidate.
- All items explicitly deferred under the constitution's "Out Of
  Scope For v0.2" list remain deferred.

## Definition of done

- `python3 -m unittest discover -s tests` exits 0 with ≥ 1,460 tests.
- `python3 evals/run_evals.py` (offline subset) green.
- All SC-001 through SC-013 from the spec verified.
- Branch `claude/modest-knuth-PUits` pushed to origin.
- A single commit ` feat(006): v0.6 research-domain-breadth — pain
  medicine + psychiatry + driving impairment + PTSD/anxiety/sleep +
  reporting rigor + OpenAlex` representing the full release.
