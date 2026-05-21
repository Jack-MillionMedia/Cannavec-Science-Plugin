# Tasks: Cannavec Science Elite Development (v0.2)

**Spec**: [`spec.md`](./spec.md) | **Plan**: [`plan.md`](./plan.md)

**Created**: 2026-05-21

Dependency-ordered. Test tasks (`Tnnn`) precede implementation tasks
(`Innn`) for the same module per Constitution §III. Tasks marked `[P]`
are parallel-safe with peers in the same phase. Phase ordering matches
the implementation order in [plan.md §Implementation Order](./plan.md):
US3 → US5 → (US1 ∥ US2) → US4 → US6.

## Phase 0 — Meta / version-boundary

- **M001** Bump `cannavec_science/__init__.py` `__version__` to
  `0.2.0`.
- **M002** Bump `.claude-plugin/plugin.json` version to `0.2.0`;
  update the description's "live discovery across nine" to "eleven"
  and add `biorxiv`, `medrxiv` to `keywords`.
- **M003** Bump `pyproject.toml` version to `0.2.0`.
- **M004** Update `.specify/memory/constitution.md` §"Out Of Scope For
  v0.x": remove the bioRxiv / medRxiv line. Note in the §"Version"
  footer: ratified-version remains 1.0.0 (no constitutional amendment),
  but the v0.x → v0.2 boundary is crossed via this spec.
- **M005** Update root `README.md`: change LOC and command counts in
  the headline, add the four scaffolders, the eleven sources, and
  US5/US6 notes. Bump test-count line as Phase 9 lands.
- **M006** Update `CLAUDE.md` if needed (path to plan.md is unchanged;
  no edit expected).

## Phase 1 — US3 (Eval Expansion) — lands first per plan.md

### Per-bucket prompt authoring (parallel-safe, one author per file region)

- **E101** [P] Add ≥ 25 curated-registry prompts to
  `evals/canonical_research_questions.json`. Cover each registry
  (major / minor cannabinoids, terpenes, interactions, AEs,
  populations, contraindications, PGx) with ≥ 3 prompts.
- **E102** [P] Add ≥ 30 rigor-positive prompts — ≥ 5 per detector ×
  6 detectors. Include the new `entourage_overclaim` detector
  (placeholder; the prompts land now, the detector lands in US6;
  the test that asserts they fire is in T606).
- **E103** [P] Add ≥ 20 rigor-negative prompts (adversarial near-miss
  against false-positive guards). Each prompt names the detector it
  intentionally avoids.
- **E104** [P] Add ≥ 15 refusal-class prompts: K2 synthesis,
  individualized dosing, pregnancy, paediatric, suicide framing, etc.
- **E105** [P] Add ≥ 10 live-discovery prompts — one per `live_*`
  source (pubmed, chembl, ctgov, pubchem, pharmgkb, rcsb, opentargets,
  gwas, bindingdb, biorxiv). Mark each with `live: true` so the
  offline runner can exclude them in CI.
- **E106** [P] Add ≥ 5 cross-cutting / regression prompts. Seed with
  any known regressions from spec-001 PR history; the curator adds to
  this monotonically.
- **E107** Add a `category_minimums` metadata block at the top of
  `canonical_research_questions.json` documenting the per-bucket
  floor (this is the source-of-truth the coverage test reads).

### Runner upgrades

- **T108** Write `tests/test_eval_coverage.py` asserting per-bucket
  minimums against `category_minimums` metadata.
- **I108** Implement bucket-count check in
  `evals/run_evals.py`. Add richer per-prompt failure reporting
  (prompt id + failing expectation + actual output).
- **T109** Add a planted-regression smoke test: deliberately break a
  detector in a test-only patch; assert the runner fails with the
  specific prompt id named.
- **E110** Create `evals/REGRESSION_LOG.md` (append-only Markdown)
  with the discipline note for curators: every regression that adds
  a prompt links back to the bug.

## Phase 2 — US5 (Registry Freshness) — lands second per plan.md

### Registry-row dataclass extension (parallel-safe, one file per task)

- **T201** [P] Write `tests/test_registry_freshness_fields.py`
  asserting every registry's row dataclass has `last_verified` and
  `watch_pmids` fields.
- **I201** [P] Add `last_verified: str` and `watch_pmids: tuple[str,
  ...]` to `cannavec_science/major_cannabinoids.py` row dataclass.
  Populate `last_verified="2026-05-21"` and pull `watch_pmids` from
  each row's existing citations.
- **I202** [P] Same for `cannavec_science/minor_cannabinoids.py`.
- **I203** [P] Same for `cannavec_science/terpenes.py`.
- **I204** [P] Same for `cannavec_science/interactions.py` (32 rows).
- **I205** [P] Same for `cannavec_science/adverse_events.py`.
- **I206** [P] Same for `cannavec_science/populations.py`.
- **I207** [P] Same for `cannavec_science/contraindications.py`.
- **I208** [P] Same for `cannavec_science/pharmacogenomics.py`.

### Freshness prober + CLI

- **T209** Write `tests/test_freshness.py` covering: clean probe,
  retraction-detected, eoc-detected, stale (`last_verified` > 180
  days), network-error fallback, CLI exit codes, no-mutation
  assertion (registry row dataclasses unchanged after probe).
- **I209** Implement `cannavec_science/freshness.py` — generic
  registry-row enumerator, `pubmed_verify` + retraction lookup, typed
  `FreshnessStatus`. Stdlib only; serial by default; optional
  `ThreadPoolExecutor` fan-out via `--parallel N`.
- **T210** Write `tests/test_freshness_cli.py` covering `freshness
  --registry <name>` and `freshness-report --since YYYY-MM-DD` exit
  codes and output shape.
- **I210** Wire `freshness` and `freshness-report` subcommands into
  `cannavec_science/__main__.py`.

### Stale-suffix integration

- **T211** Write `tests/test_answer_freshness.py` asserting the
  `[freshness: stale (verified YYYY-MM-DD)]` suffix appears when a
  composed answer cites a registry row with `last_verified` > 365
  days old.
- **I211** Extend `cannavec_science/answer.py` citation renderer to
  append the stale suffix at row-age > 365 days.

## Phase 3 — US1 (Preprint Discovery) — parallel with Phase 4

### Tier-3 wrappers (parallel-safe)

- **T301** Write `tests/test_biorxiv_discover.py` with injected
  fetcher fixtures (bioRxiv API v0 response samples). Cover
  happy-path, refusal (K2 / banned-pattern), network-error,
  empty-result, version-history parsing, published-version
  cross-reference.
- **I301** Implement `cannavec_science/_preprint_helpers.py` — DOI
  parsing, version-history extraction, Crossref-based
  published-version cross-reference.
- **I302** Implement `cannavec_science/biorxiv_discover.py` using
  `_preprint_helpers`. Same Tier-3 contract as the existing nine
  discoverers (urllib transport, injected fetchers, discover_guard
  preflight, `live_biorxiv` provenance, Level D cap).
- **T303** Write `tests/test_medrxiv_discover.py` mirroring T301.
- **I303** Implement `cannavec_science/medrxiv_discover.py` using
  `_preprint_helpers`.

### CLI + synthesis integration

- **T304** Extend `tests/test_synthesis.py` with `biorxiv` and
  `medrxiv` cluster cases.
- **I304** Add `"biorxiv"` and `"medrxiv"` to
  `cannavec_science/synthesis.py` `_SOURCE_KEYS`.
- **I305** Add `biorxiv` and `medrxiv` runners to
  `_DISCOVERER_REGISTRY` in `cannavec_science/__main__.py`.
- **T306** Extend `tests/test_discover_guard.py` to assert preprint
  lanes also refuse on K2 / banned-pattern.
- **I306** No code change to `discover_guard.py` expected — the
  preflight is generic. Verify via the test.

### Composer integration

- **T307** Write `tests/test_answer_preprint_badge.py` asserting that
  a preprint-only-supported claim renders with `[preprint, not
  peer-reviewed]` badge AND caps at Level D.
- **I307** Extend `cannavec_science/answer.py` citation renderer to
  emit the badge when the source's provenance is `live_biorxiv` or
  `live_medrxiv`.
- **I308** Update `skills/cannabis-primary-source-routing/SKILL.md`
  to add bioRxiv / medRxiv lane with the routing heuristic ("when
  the question is about 2024+ mechanism work that may not yet have
  reached PubMed").

## Phase 4 — US2 (Workflow Scaffolders) — parallel with Phase 3

### PICO drafter

- **T401** [P] Write `tests/test_pico.py` covering happy-path with
  clinical-efficacy intent, populated-population-registry case,
  insufficient-input case (no intent match), and the typed
  `PICOBlock` shape.
- **I401** [P] Implement `cannavec_science/pico.py` — pure
  deterministic composer using intent classifier + populations
  registry. Emits `PICOBlock`.

### Power calculator

- **T402** [P] Write `tests/test_power_calc.py` covering Cohen's-d
  two-arm (test against Cohen 1988 worked example), OR two-arm
  (Fleiss 1981 worked example), proportion-difference,
  insufficient-input message, zero-effect edge case, perfect-effect
  edge case.
- **I402** [P] Implement `cannavec_science/power_calc.py` using
  `math.erf` for normal CDF. No scipy/numpy. Emits `PowerCalculation`.
  Surface `method_not_supported` for non-inferiority / adaptive
  designs (honest failure mode, not silent guess).

### GRADE evidence-profile table

- **T403** [P] Write `tests/test_grade_profile.py` asserting per-claim
  row alignment, downgrade column totals match the GRADE adapter,
  Markdown vs CSV format differences, zero-claims edge case (renders
  header + single "no admissible evidence" row).
- **I403** [P] Implement `cannavec_science/grade_profile.py` reading
  the typed `Answer` and emitting `GradeEvidenceProfile` in Markdown
  or CSV.

### Protocol skeleton

- **T404** [P] Write `tests/test_protocol_skeleton.py` asserting
  section count (exactly 9), watermark on line 1, < 1500 word cap,
  PICO inclusion (when PICO block exists).
- **I404** [P] Implement `cannavec_science/protocol_skeleton.py` —
  deterministic 9-section IRB stub generator. Emits
  `ProtocolSkeleton`.

### CLI + composer integration

- **T405** Write `tests/test_cli_scaffolders.py` covering `--pico`,
  `--power-calc`, `--grade-profile`, `--grade-profile-format
  {markdown|csv}`, `--protocol-skeleton` flags, single-invocation
  combination, exit codes.
- **I405** Wire the four flags into the `answer` subcommand in
  `cannavec_science/__main__.py`.
- **I406** Extend `cannavec_science/answer.py` `compose_answer` and
  `Answer.to_markdown` to thread the four scaffolders. Each scaffolder
  is opt-in; absence reverts to current behavior.
- **I407** Update `commands/research.md` and `commands/ask.md` to
  document the four flags. **No new `commands/*.md` file** —
  Constitution §IV scope lock.
- **I408** Add a scaffolder demo paragraph to `docs/DEMO_SCRIPT.md`.

## Phase 5 — US4 (Citation Network) — depends on Phase 3 (verify)

- **T501** Write `tests/test_citation_network.py` covering network
  success (NCBI elink), rate-limit graceful degradation,
  mixed-pushback, replication-success language, replication-failure
  language, zero-forward-cites edge case.
- **I501** Implement `cannavec_science/citation_network.py` —
  NCBI elink `cmd=neighbor` wrapper, per-cite sentiment via existing
  `pubmed_sentiment()` from `synthesis.py`, replication-language
  detector, emits `CitationNetworkBlock`.
- **T502** Extend `tests/test_pubmed_verify.py` to cover the new
  `with_citation_network: bool` flag on `verify_pmid`.
- **I502** Add `with_citation_network` flag to
  `cannavec_science.pubmed_verify.verify_pmid` (default False for
  back-compat). The `verify` CLI subcommand sets it True unless
  `--no-citation-network` is passed.
- **T503** Extend `tests/test_evidence.py` to cover the deterministic
  GRADE downgrade: a refute-heavy `citation_network` block sets
  `inconsistency_serious=True` in `apply_grade_modifiers`, dropping
  Level B → Level C.
- **I503** Wire the citation-network signal into
  `cannavec_science/answer.py`'s per-claim grade computation. The
  composer reads `citation_network.field_pushback_signal.aggregate`
  and flips `inconsistency_serious` when `refute_heavy`.
- **T504** Write `tests/test_cli_verify_citation_network.py`
  asserting the verify subcommand's JSON output includes the
  `citation_network` block.
- **I504** Update `__main__.py` `verify` subcommand: emit
  `citation_network` by default; honor `--no-citation-network` flag.

## Phase 6 — US6 (Cannabis Blind-Spot Closures) — last because it
depends on US5's `last_verified` discipline and US3's eval coverage

### Minor-cannabinoid expansion

- **T601** [P] Extend `tests/test_minor_cannabinoids.py` to cover
  the four new rows (Δ⁸-THC, HHC, THCO, THCP). Assert honest grade
  for each — Unsupported is acceptable where evidence is genuinely
  absent.
- **I601** [P] Add Δ⁸-THC, HHC, THCO, THCP rows to
  `cannavec_science/minor_cannabinoids.py`. Each row carries
  `last_verified="2026-05-21"` and `watch_pmids` (per US5 contract).

### eCBome reference module

- **T602** [P] Write `tests/test_ecbome.py` — every entry has a
  UniProt or HMDB identifier; mediator-receptor pairing sanity
  (AEA ↔ CB1 / CB2 / TRPV1 etc.); receptor-id rigor pass on
  composed eCBome answers returns zero violations.
- **I602** [P] Implement `cannavec_science/ecbome.py` — typed
  `EcbomeEntry` for mediators / receptors / enzymes / transporters.
  Every entry has a primary identifier.

### Regulatory-feasibility advisory

- **T603** [P] Write `tests/test_regulatory_feasibility.py` — US
  Schedule I path (DEA research registration), EU novel-food gray
  zone (Δ⁸-THC, HHC), Canada §56 exemption, UK-MHRA controlled-drug
  licence, unsupported-jurisdiction graceful fail, watermark presence
  on every output.
- **I603** [P] Implement `cannavec_science/regulatory_feasibility.py`
  — advisory module with `RegulatoryFeasibilityAdvisory` dataclass.
  Watermark on every output: "This is not legal advice; consult your
  institutional research-compliance office."

### Entourage rigor detector

- **T604** Write `tests/test_entourage_detector.py` — positive
  (synergy claim without canonical citation), negative (synergy claim
  WITH each of Russo 2011 / Finlay 2020 / Santiago 2019 / LaVigne
  2021 cited), false-positive guard (discussion of the entourage
  hypothesis as a research topic does NOT fire).
- **I604** Add `detect_entourage_overclaim()` + `EntourageViolation`
  dataclass to `cannavec_science/rigor_checks.py`. Include in
  `RigorCheckReport`.
- **T605** Extend `tests/test_rigor_checks.py` to assert the new
  detector is part of the report's `clean` property.
- **I605** Update `RigorCheckReport.clean`, `RigorCheckReport.summary`,
  and the `run_rigor_checks()` aggregator.
- **T606** Re-run the rigor-positive prompts from E102 that target
  the entourage detector; assert they now fire.

### CLI + composer integration

- **T607** Write `tests/test_cli_regulatory_feasibility.py` covering
  `--regulatory-feasibility {us|eu|ca|uk}` flag exit codes and
  output shape.
- **I607** Wire `--regulatory-feasibility` flag into the `answer`
  subcommand in `cannavec_science/__main__.py`.
- **I608** Extend `cannavec_science/answer.py` to thread the
  regulatory-feasibility advisory and the eCBome entries into the
  composed answer when relevant intent fires.

## Phase 7 — Documentation refresh

- **D701** Update `README.md`: bump LOC / command / source counts;
  add bioRxiv / medRxiv; add scaffolders; add freshness probe; add
  eCBome and regulatory-feasibility flags; add Δ⁸ / HHC / THCO / THCP
  to the minor-cannabinoid list.
- **D702** Update `docs/DEMO_SCRIPT.md` — extend the five-minute
  walkthrough with: a preprint-discovery beat (US1), a
  one-invocation `--pico --power-calc --grade-profile
  --protocol-skeleton` beat (US2), a `verify` with citation-network
  beat (US4), a `freshness` operator beat (US5), an entourage-detector
  beat (US6).
- **D703** Update `skills/cannabis-research-rigor/SKILL.md` to
  include the entourage detector in the rigor catalogue.
- **D704** Update `skills/cannabis-evidence-grading/SKILL.md` to
  document the citation-network deterministic GRADE downgrade.
- **D705** Update `skills/cannabis-primary-source-routing/SKILL.md`
  to add bioRxiv / medRxiv lane (also see I308).

## Phase 8 — Acceptance-gate verification

- **V801** Run `python3 -m unittest discover -s tests`. Expect
  ≥ 1,100 tests, all green, in ≤ 60 seconds. Total test count
  recorded in commit message.
- **V802** Run `python3 evals/run_evals.py`. Expect exit 0 with
  ≥ 100 prompts loaded.
- **V803** Run the v0.2 golden-flow demos end-to-end:
  - `python3 -m cannavec_science discover "CB2 microglia" --sources
    biorxiv,medrxiv --max 5`
  - `python3 -m cannavec_science answer "CBD Dravet syndrome" --pico
    --power-calc --grade-profile --protocol-skeleton`
  - `python3 -m cannavec_science verify 28538134 --json`
  - `python3 -m cannavec_science freshness --registry interactions`
  - `python3 -m cannavec_science answer "What is the evidence for
    HHC analgesia?"`
  - `python3 -m cannavec_science rigor "myrcene potentiates THC's
    sedative effect"`
- **V804** Verify LOC budget: `wc -l cannavec_science/*.py` shows
  total < 25,000.
- **V805** Verify slash-command count: `ls commands/*.md | wc -l`
  shows exactly 5.
- **V806** Verify constitution update: §"Out Of Scope For v0.x" no
  longer lists bioRxiv / medRxiv.
- **V807** Verify version bump: `plugin.json`, `pyproject.toml`,
  `__init__.py` all read `0.2.0`.
- **V808** Capture before-and-after rating: re-run the 2026-05-21
  elite-tier scoring rubric. Target ≥ 9.5/10. Record per-dimension
  deltas in `docs/V02_RATING_DELTA.md`.

## Phase 9 — Ship

- **X901** `git add` the v0.2 deltas; commit per the
  conventional-commits style used in spec 001:
  `feat(002): elite-tier development — preprints, scaffolders,
  freshness, citation network, blind-spot closures`.
- **X902** Push the branch and open a PR with the gate-verification
  output from V801–V808 in the description.
- **X903** After merge: tag `v0.2.0`; update `README.md` install
  example to reference the tag.

## Definition Of Done

Every task in Phases 0–8 closes with green tests + a corresponding diff
under the right directory. The v0.2 acceptance gate from
[plan.md](./plan.md) holds. The slash-command count remains exactly
five. The rating delta in V808 documents the move from 8.2/10 to
≥ 9.5/10 across the same ten dimensions the 2026-05-21 rating used.
