# Tasks: Cannavec Science MVP

**Spec**: [`spec.md`](./spec.md) | **Plan**: [`plan.md`](./plan.md)

**Created**: 2026-05-21

Dependency-ordered. Test tasks (`Tnnn`) come before implementation
tasks (`Innn`) for the same module. Tasks marked `[P]` are parallel-
safe with peers in the same phase.

## Phase 0 — Meta / scaffolding

- **M001** Create `pyproject.toml` declaring `cannavec_science`
  package, Python ≥ 3.9, zero runtime deps.
- **M002** Create `.claude-plugin/plugin.json` with `name:
  cannavec-science`, version `0.1.0`, focused description.
- **M003** Create `LICENSE` (MIT), `.gitignore`, `CLAUDE.md`
  pointing at `specs/001-science-mvp/plan.md`.
- **M004** Create `README.md` (focused, demo-first), `QUICKSTART.md`
  (one-page researcher journey).
- **M005** Create `cannavec_science/__init__.py`.

## Phase 1 — Tier 1 backbone (deterministic core)

- **T101** [P] Port `tests/test_evidence.py` (`Source`, `Claim`,
  `ClaimType`, GRADE levels).
- **I101** Port + trim `cannavec_science/evidence.py`.

- **T102** [P] Port `tests/test_banned_patterns.py` (15 patterns +
  negation guard).
- **I102** Port `cannavec_science/banned_patterns.py`.

- **T103** [P] Port `tests/test_safety.py` (K2 hard refuse, harmful /
  individualized verdicts).
- **I103** Port + trim `cannavec_science/safety.py` (drop
  jurisdiction/audience branching).

- **T104** [P] Port `tests/test_rigor_checks.py` covering all six
  detectors (isomer-collapse, receptor-without-ID, dose-without-route,
  THCA-vs-THC, matrix-unit, decarb-context).
- **I104** Port `cannavec_science/rigor_checks.py`.

- **T105** [P] Port `tests/test_retraction.py`.
- **I105** Port `cannavec_science/retraction.py`.

- **T106** [P] Port `tests/test_uncertainty.py`.
- **I106** Port `cannavec_science/uncertainty.py`.

- **T107** [P] Port `tests/test_intent.py`.
- **I107** Port `cannavec_science/intent.py`.

## Phase 2 — PubMed verifier + Crossref

- **T201** Port `tests/test_pubmed_verify.py` with injected fetcher
  fixtures.
- **I201** Port `cannavec_science/pubmed_verify.py`.

## Phase 3 — Registries (data)

- **T301** [P] `tests/test_major_cannabinoids.py`
- **I301** [P] `cannavec_science/major_cannabinoids.py`

- **T302** [P] `tests/test_minor_cannabinoids.py`
- **I302** [P] `cannavec_science/minor_cannabinoids.py`

- **T303** [P] `tests/test_terpenes.py`
- **I303** [P] `cannavec_science/terpenes.py` (merged from parent
  `terpenes.py` + `terpene_reference.py`)

- **T304** [P] `tests/test_interactions.py` covering the 32-row
  registry (original 17 + modern 15: DOACs, specific SSRIs, lithium,
  anesthesia, chemotherapy).
- **I304** [P] `cannavec_science/interactions.py`.

- **T305** [P] `tests/test_adverse_events.py`
- **I305** [P] `cannavec_science/adverse_events.py`

- **T306** [P] `tests/test_populations.py`
- **I306** [P] `cannavec_science/populations.py`

- **T307** [P] `tests/test_contraindications.py`
- **I307** [P] `cannavec_science/contraindications.py`

- **T308** [P] `tests/test_pharmacogenomics.py`
- **I308** [P] `cannavec_science/pharmacogenomics.py`

## Phase 4 — Typed Answer + composition

- **T401** Write `tests/test_answer.py` covering the typed `Answer`
  artifact + `compose_answer` happy path + banned-pattern refusal +
  retraction-strict suppression + rigor-violation gate.
- **I401** Port + trim `cannavec_science/answer.py`. Trim: drop
  jurisdiction, drop multi-audience templates, drop hemp/pesticide/
  oncology threading. Keep retraction policy, rigor report,
  bibliography hook, registry threading for the eight science
  registries.

- **T402** Write `tests/test_evidence_synthesis.py` covering grade
  buckets, claim-type buckets, contradictions, distinct-source count,
  mean provenance score.
- **I402** Port `cannavec_science/evidence_synthesis.py` (fold
  contradiction detection from parent `contradiction.py` into here).

- **T403** Write `tests/test_bibliography.py` covering BibTeX, RIS,
  CSL-JSON output + inline GRADE annotation + standalone re-render
  from `Answer` JSON.
- **I403** Port `cannavec_science/bibliography.py`.

## Phase 5 — Live discovery

- **T501** [P] Write `tests/test_pubmed_search.py` with injected
  fetcher (E-utilities response fixtures).
- **I501** [P] Port `cannavec_science/pubmed_search.py`.

- **T502** [P] Write `tests/test_chembl_discover.py` with injected
  fetcher (ChEMBL REST fixtures).
- **I502** [P] Port `cannavec_science/chembl_discover.py`.

- **T503** [P] Write `tests/test_ctgov_discover.py` with injected
  fetcher (CTGov API v2 fixtures).
- **I503** [P] Port `cannavec_science/ctgov_discover.py`.

- **T504** Write `tests/test_discover_guard.py` covering refuse paths
  (banned-pattern, safety hard-refuse).
- **I504** Port `cannavec_science/discover_guard.py`.

- **T505** Write `tests/test_synthesis.py` covering STRONG / MIXED /
  WEAK / NONE verdict logic + per-source disagreement.
- **I505** Port `cannavec_science/synthesis.py`.

- **T506** Write `tests/test_source_health.py`.
- **I506** Port `cannavec_science/source_health.py`.

## Phase 6 — CLI

- **T601** Write `tests/test_cli.py` covering `answer`, `discover`,
  `verify`, `rigor`, `bibliography`, `source-health` exit codes and
  output shape.
- **I601** Write `cannavec_science/__main__.py` wiring every primitive
  into the unified CLI.

## Phase 7 — Surfaces (slash commands, skills, agents)

- **S701** Write `commands/research.md` (full pipeline; references
  `cannavec_science answer`).
- **S702** Write `commands/ask.md` (slim Q&A flavour).
- **S703** Write `commands/discover.md` (live fan-out).
- **S704** Write `commands/verify.md` (single identifier spot-check).
- **S705** Write `commands/rigor.md` (rigor detectors on text).

- **K701** Port `skills/cannabis-research-rigor/SKILL.md` from parent.
- **K702** Port `skills/cannabis-evidence-grading/SKILL.md` from parent
  (trim audience-template references).

- **A701** Port + slim `agents/cannabis-source-hunter.md` (drop preprint
  + CourtListener references; keep PubMed + ChEMBL + CTGov).
- **A702** Write `agents/cannabis-research-reviewer.md` as a consolidated
  reviewer (replaces the parent's six-persona reviewer set).

## Phase 8 — Evals

- **E801** Write `evals/canonical_research_questions.yaml` — 12
  prompts: 3 curated registry hits, 3 live-discovery exercises, 3
  rigor-violation prompts (positive), 3 rigor-clean prompts (negative).
- **E802** Write `evals/run_evals.py` — stdlib-only static eval runner
  that asserts each prompt's expected behaviour.

## Phase 9 — Demo readiness

- **D901** Run the full test suite. Fix anything red.
- **D902** Run the four golden-flow demos end-to-end:
  - `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome"`
  - `python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01`
  - `python3 -m cannavec_science verify 28538134`
  - `python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC"`
- **D903** Capture demo output in `docs/DEMO_SCRIPT.md` for the
  five-minute walkthrough.

## Phase 10 — Ship

- **X1001** `git add` + commit with a feat(001) message.
- **X1002** `git push -u origin claude/cannavec-science-plugin-mvp-FYkM0`.
- **X1003** Update `README.md`'s install + quickstart line with the
  final repo URL.

## Definition Of Done

Every task in Phases 1–9 closes with green tests + a corresponding
diff under the right directory. The acceptance gate from `plan.md`
holds. The five-command surface is the entire user-facing API.
