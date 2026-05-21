# Feature Specification: Cannavec Science MVP

**Feature Branch**: `claude/cannavec-science-plugin-mvp-FYkM0`

**Created**: 2026-05-21

**Status**: Approved for `/speckit-plan`

**Input**: User description: "My current Cannavec-Plugin is too large and I want to refine it into an MVP specializing in cannabis research on science only in Cannavec-Science-Plugin. Use the absolute best parts of my current plugin but simplify and make it easier to test myself and actually show potential clients something impressive, not something that's half done because it tries to do everything off the rip."

## Background

The parent Cannavec plugin grew to **41 slash commands, 14 agents, 10
skills, 12 curated registries, 15 audience surfaces, 59 Python
modules (~35,500 LOC), and 1,748 tests across four spec iterations**.
It is research-grade but unwieldy: the surface promises more than any
demo can credibly cover in a single session, and a potential client
sees fragments of every audience rather than mastery of any one.

The MVP corrects this by **narrowing to the researcher audience** and
shipping only the modules that prove cannabis-science rigor end-to-end:

- The deterministic backbone (GRADE, banned patterns, safety preflight,
  phytochemistry rigor checks, PubMed verification, retraction enforcement).
- Five curated science registries (major + minor cannabinoids, terpenes,
  drug interactions, adverse events, populations, contraindications,
  pharmacogenomics).
- Live read-time discovery across **PubMed, ChEMBL, ClinicalTrials.gov**
  with cross-source synthesis.
- Bibliography export (BibTeX, RIS, CSL-JSON) with inline GRADE
  annotation.

Out-of-scope (per Constitution §IV and "Out Of Scope For v0.x"):
all non-researcher audience templates, the KB flywheel, signed
artifacts, watchlists, multi-jurisdiction legal surface, hemp /
microbiome / veterinary / industrial-hemp surfaces, CourtListener
integration, pesticides registry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Researcher Brief With Curated Science (Priority: P1)

**Persona**: Cannabis-research scientist (academic, industry, or
clinical-trial). They have a research question and want a brief that
they can defend to their PI, journal reviewer, or IRB.

A researcher asks `/cannavec-science:research "What is the evidence for
CBD in Dravet syndrome?"`. The plugin returns a structured brief with:

- **PICO framing** of the question.
- **GRADE-graded claims** from the curated registries (populations,
  interactions, AEs, contraindications, cannabinoids, terpenes, PGx).
- **Inline citations** (PMID / DOI / NCT / ChEMBL / UniProt) at the
  claim site, with the GRADE level annotated inline.
- **Evidence synthesis block** — grade buckets, claim-type buckets,
  distinct sources, mean provenance score, surfaced contradictions.
- **Phytochemistry rigor pass** — text containing bare "THC" in
  pharmacology context, missing receptor IDs, dose-without-route,
  THCA/THC conflation, matrix-unit confusion, or decarb-context-missing
  is flagged and the brief refuses to render until corrected.
- **Honest disclosure** — what the registries did not cover; where to
  look next.

**Why this priority**: This is the demo. A client watching a five-minute
walkthrough sees this command produce a research-grade brief on a real
question, with every claim cited, every grade defensible, and every
phytochemistry shortcut caught. If this story does not land, nothing
else matters.

**Independent Test**: `python3 -m cannavec_science answer "CBD evidence
in Dravet syndrome" --audience researcher --json` returns a typed
`Answer` artifact with ≥ 3 claims, each cited, each graded; the
deterministic synthesis block reports ≥ 1 Level A or Level B claim;
the rigor-check report shows zero violations on the rendered text.
Tests assert artifact shape, claim count, citation backing, grade
consistency, banned-pattern absence.

**Acceptance Scenarios**:

1. **Given** the question "What is the evidence for CBD in Dravet
   syndrome?", **When** `/cannavec-science:research` runs, **Then** the
   output includes Devinsky-2017 (PMID 28538134) or equivalent Level A
   citation, PICO framing, GRADE buckets, and zero banned-pattern hits.
2. **Given** a prompt with bare "THC" in pharmacology context, **Then**
   the rigor check flags `BARE_THC_PHARMACOLOGY` and the answer refuses
   to render until disambiguated to Δ⁹-THC.
3. **Given** a registry row cites a retracted PMID, **Then**
   `compose_answer(retraction_policy="strict")` excludes the claim AND
   surfaces a "1 claim suppressed: retracted citation" header.
4. **Given** the `--json` flag, **Then** the typed `Answer` artifact is
   emitted to stdout with stable schema fields (claims, citations,
   evidence_summary, retractions_suppressed, rigor_report).
5. **Given** the question references the entourage effect, **Then** the
   output names the hypothesis as open-empirical with mixed evidence
   and refuses to write Level A wording for it.
6. **Given** the rigor check finds a violation, **Then** the offending
   span MUST be returned with a resolution hint (not just a flag).

---

### User Story 2 — Live Multi-Source Discovery (Priority: P1)

**Persona**: A researcher who needs primary literature published
after the curated registry's snapshot date, or who is exploring a
topic the curated registries do not yet cover.

A researcher runs `/cannavec-science:discover "CBD PTSD 2025"`. The
plugin fans out across **PubMed**, **ChEMBL**, and
**ClinicalTrials.gov**, applies the safety preflight + banned-pattern
detector to the query, and returns a triaged list of candidates
tagged with per-source provenance (`live_pubmed`, `live_chembl`,
`live_ctgov`) and a **cross-source synthesis verdict**
(STRONG / MIXED / WEAK / NONE convergence). Every row carries the
identifier (PMID / ChEMBL ID / NCT), the year, the study type or
assay context, and a "provisional, live-search" GRADE suffix.

**Why this priority**: The single biggest credibility upgrade over a
demo that "answers from a 2026 snapshot." A live demo that surfaces a
2025 trial PMID is the moment a potential client believes the plugin
keeps up with the literature.

**Independent Test**:
`python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01 --max 10`
on a network-enabled host returns a structured list of ≥ 1 candidate
per source (when each has hits), each tagged with the right provenance,
each carrying its identifier and year. With the network stubbed
(injected fetchers), `tests/test_discover_live.py` asserts shape,
banned-pattern filtering, safety refusal, source-tag correctness, and
the cross-source synthesis verdict logic.

**Acceptance Scenarios**:

1. **Given** the query "CBD PTSD", **When** `/cannavec-science:discover`
   runs against the three live sources, **Then** the output lists rows
   with `provenance ∈ {live_pubmed, live_chembl, live_ctgov}` and a
   synthesis block at the bottom with verdict + disagreement notes.
2. **Given** a banned-pattern query ("indica cures PTSD"), **Then** the
   discover surface refuses with the same refusal layer
   `compose_answer` uses — **no external request is fired**.
3. **Given** a synthesis-route query ("K2 synthesis"), **Then** the
   safety preflight hard-refuses before any live call.
4. **Given** network is unavailable for one source but available for
   the others, **Then** the failed source surfaces a "live source
   unavailable" note and the other sources still render their rows.
5. **Given** `--json`, **Then** structured JSON appears on stdout with
   the per-source rows and the synthesis verdict.
6. **Given** the curated registry already has a row for the topic,
   **Then** the live rows are presented *alongside* (not in place of)
   the curated row, with the curated row marked as such.

---

### User Story 3 — Bibliography Export For Reference Managers (Priority: P1)

**Persona**: A researcher writing for publication, an IRB protocol
author, a regulator-facing brand team. They want the answer's
citations in Zotero / Mendeley / EndNote without re-keying.

A researcher runs `/cannavec-science:research "..." --bibliography bibtex`
(or `ris` or `csljson`). The plugin emits a valid `.bib` / `.ris` /
`.json` file containing every cited identifier in the answer, with
**GRADE level annotated inline** in the entry (e.g., a BibTeX `note`
field or a CSL-JSON `note` key). A standalone subcommand
`cannavec_science bibliography <answer.json> --format bibtex` re-renders
a previously-emitted JSON answer without recomposing.

**Why this priority**: Researchers do not trust a tool they cannot
export from. This story turns Cannavec Science from "interesting
demo" into "I'm using this for my next paper."

**Independent Test**:
`python3 -m cannavec_science answer "CBD Dravet" --bibliography bibtex
--out /tmp/refs.bib` produces a `/tmp/refs.bib` parseable by `pybtex`
or `bibtexparser` (verified in tests via a stdlib-only validator),
with one entry per cited PMID/DOI and the GRADE level in the `note`
field. The standalone subcommand re-renders the same artifact's
bibliography in any of the three formats.

**Acceptance Scenarios**:

1. **Given** an answer with N cited PMIDs/DOIs, **When**
   `--bibliography bibtex` is set, **Then** N entries are emitted with
   well-formed BibTeX (`@article{key, ...}`), each containing inline
   GRADE annotation in `note`.
2. **Given** `--bibliography ris`, **Then** the output uses standard
   RIS tags (`TY  - JOUR`, `AU  - ...`, `PY  - YYYY`, `DO  - ...`,
   ending `ER  -`) with GRADE in `N1`.
3. **Given** `--bibliography csljson`, **Then** the output is valid
   JSON conforming to the CSL-JSON schema with `note` carrying GRADE.
4. **Given** `cannavec_science bibliography <answer.json> --format
   bibtex`, **Then** the bibliography is re-emitted from the typed
   `Answer` without recomposing or re-hitting external sources.
5. **Given** no `--out`, **Then** the bibliography prints to stdout for
   piping (`> refs.bib`, `| pbcopy`, etc.).
6. **Given** a claim whose only citation was retraction-suppressed,
   **Then** that identifier MUST NOT appear in the bibliography.

---

### User Story 4 — Citation & Rigor Spot-Check (Priority: P2)

**Persona**: A researcher reviewing someone else's claim or their
own draft. They want to verify a single PMID or run rigor checks on
a paragraph without composing a whole brief.

`/cannavec-science:verify <PMID|DOI|NCT|ChEMBL>` confirms the
identifier exists on the primary registry (PubMed / Crossref /
ClinicalTrials.gov / ChEMBL), returns first author + year + journal +
retraction status, and emits PASS / PARTIAL / FAIL with rationale.

`/cannavec-science:rigor "<paragraph>"` runs the six phytochemistry
rigor detectors (isomer-collapse, receptor-without-ID,
dose-without-route, THCA-vs-THC conflation, matrix-unit confusion,
decarb-context-missing) and the 15-pattern banned-pattern detector
against arbitrary text, returning a structured report with each
violation's span and resolution hint.

**Why this priority**: P2 because P1 (the research brief) already
incorporates these checks. But shipping them as standalone surfaces
makes the deterministic backbone *demonstrable* — a client can see the
rigor checks fire on text that isn't from a curated-registry answer.

**Independent Test**:
- `python3 -m cannavec_science verify 28538134` returns
  `Devinsky / 2017 / N Engl J Med / not retracted / PASS`.
- `python3 -m cannavec_science rigor "this cultivar tests at 22% THC by
  HPLC"` returns a `THCA_VS_THC_CONFLATION` violation with the matched
  span and a resolution hint.
- Banned-pattern detection fires on "natural therefore safe."

**Acceptance Scenarios**:

1. **Given** a valid PMID, **When** `verify` runs, **Then** the
   response includes first author, year, journal, and a
   `retraction_status` field.
2. **Given** a retracted PMID, **Then** the verify response is `FAIL`
   with a `retraction_date` and `retraction_reason`.
3. **Given** arbitrary text, **When** `rigor` runs, **Then** each
   detector returns its violations independently and aggregates into
   a single `RigorCheckReport`.
4. **Given** clean text with explicit isomers and matrix tags, **Then**
   `rigor` returns zero violations.
5. **Given** the banned-pattern detector fires on "indica calms
   anxiety," **Then** the violation carries the pattern ID, the matched
   span, and an explanation.
6. **Given** a 30-character negation window ("indica does NOT calm
   anxiety"), **Then** the detector does NOT fire (negation guard).

---

### Edge Cases

- **Network failure during discover**: each source independently
  surfaces a "live source unavailable" note; partial results still
  render with their per-source provenance tags. The synthesis verdict
  downgrades to reflect missing sources.
- **Empty registry result with no live hits**: the answer renders
  with `0 claims, Unsupported` and an explicit "the curated registries
  did not cover this topic, and live discovery returned no hits."
  No invention.
- **Retracted citation in curated registry**: `compose_answer` in
  `strict` mode suppresses the claim and emits the
  `retractions_suppressed` count; the bibliography excludes the
  retracted identifier.
- **Banned-pattern hit in the user's query itself**: the discover
  surface refuses BEFORE any external network call. The research-brief
  surface refuses before composing claims.
- **Disambiguation: "CBD" as casual shorthand vs CBD as pharmacology
  topic**: bare "CBD" in a pharmacology / dose / receptor-binding
  context fires the isomer-collapse detector; bare "CBD" in a
  market-context sentence does not.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST refuse to render any claim without a
  primary-source identifier (PMID, DOI, NCT, ChEMBL ID, or UniProt
  accession).
- **FR-002**: System MUST grade every claim using the deterministic
  GRADE grader (A / B / C / D / E / Unsupported) and MUST refuse to
  emit prose whose verb does not match the assigned grade.
- **FR-003**: System MUST run the banned-pattern detector (15 patterns
  with a 30-character negation guard) and the safety preflight
  (refuse-harmful / refuse-individualized / add-caution / proceed)
  on every user input BEFORE composing claims or firing live calls.
- **FR-004**: System MUST run six phytochemistry rigor detectors
  on every rendered answer text: isomer-collapse, receptor-without-ID,
  dose-without-route, THCA-vs-THC conflation, matrix-unit confusion,
  decarb-context-missing.
- **FR-005**: System MUST consult the retraction registry inside
  `compose_answer()` and, in `strict` mode (the default for the
  researcher audience), MUST suppress any claim whose sole citation
  is retracted.
- **FR-006**: System MUST live-fan-out queries across PubMed, ChEMBL,
  and ClinicalTrials.gov, tag every row with a per-source provenance
  field, and emit a deterministic cross-source synthesis verdict
  (STRONG / MIXED / WEAK / NONE).
- **FR-007**: System MUST never auto-promote a `live_*` row to the
  curated tier in v0.x. Promotion paths are out-of-scope.
- **FR-008**: System MUST export the answer's bibliography as BibTeX,
  RIS, or CSL-JSON with inline GRADE annotation, both as an
  `--bibliography` flag on `answer` and as a standalone
  `bibliography <answer.json>` subcommand.
- **FR-009**: System MUST run offline (zero `pip install`,
  stdlib-only) with injected fetcher fixtures driving all network
  paths in tests.
- **FR-010**: System MUST ship five slash commands and only five:
  `/cannavec-science:research`, `/cannavec-science:ask`,
  `/cannavec-science:discover`, `/cannavec-science:verify`,
  `/cannavec-science:rigor`. Adding a sixth without a constitutional
  amendment is a scope violation.

### Key Entities

- **`Claim`**: a single typed statement (claim text, claim type,
  GRADE level, list of `Source` citations, jurisdiction tag if
  applicable). Composable into an `Answer`.
- **`Source`**: a primary-source identifier (PMID, DOI, NCT,
  ChEMBL ID, UniProt accession) with first author, year, journal /
  registry, study type, retraction status, source-authority tier.
- **`Answer`**: the typed artifact (prompt, audience, claims,
  evidence_summary, rigor_report, retractions_suppressed,
  bibliography_emit_path, banned_patterns_hit, safety_verdict).
- **`EvidenceSynthesis`**: deterministic rollup over an `Answer`
  (grade buckets, claim-type buckets, contradictions, distinct
  sources, mean provenance score).
- **`RigorCheckReport`**: aggregated violations across six detectors
  with span + resolution hint per violation.
- **`LiveDiscoveryRow`**: a single hit from PubMed, ChEMBL, or CTGov
  (identifier, year, source-tag, abstract or assay-context excerpt,
  provisional grade).
- **`CrossSourceSynthesis`**: STRONG / MIXED / WEAK / NONE verdict +
  per-source counts + disagreement notes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A potential client watching a five-minute walkthrough
  sees `/cannavec-science:research` produce a brief on a real cannabis
  question (CBD/Dravet, CBN/sleep, THC/CYP3A4) with ≥ 3 cited claims,
  ≥ 1 Level B or higher, zero banned-pattern hits, and a clean rigor
  report.
- **SC-002**: A researcher running `/cannavec-science:discover "CBD
  PTSD 2025"` sees at least one row from each of PubMed, ChEMBL, and
  ClinicalTrials.gov, with the synthesis verdict reflecting genuine
  convergence or disagreement.
- **SC-003**: The bibliography exporter produces output parseable by
  Zotero (BibTeX path) and by the CSL-JSON validator with inline
  GRADE annotation present on every entry.
- **SC-004**: Tests pass with `python3 -m unittest discover -s tests`
  in ≤ 30 seconds on a stdlib-only Python 3.9+ environment.
- **SC-005**: The deterministic rigor-check + banned-pattern surface
  catches every one of ten seed violations in a tightly-scoped eval
  suite (`evals/canonical_research_questions.yaml`), with no false
  positives on ten matched-clean prompts.
- **SC-006**: A retracted PMID seeded in the registry never appears
  in a rendered answer or bibliography under `--retraction-policy
  strict`, verified by a regression test.
- **SC-007**: The total Python LOC under `cannavec_science/` stays
  under 20,000 lines (a 50%+ reduction from the parent's ~35,500).
  The bulk of the remaining LOC is registry data with citation graphs,
  not new code surface. The total slash-command count stays at five.
  Any drift in command count triggers a constitutional review.

## Out Of Scope (Explicit)

The MVP **does not** ship any of the following — deferring them is
the point of this spec:

- Patient, clinician, cultivator, lab, compliance, retail,
  public-health, operator, policy, product, hemp, microbiome,
  veterinary audience surfaces.
- KB flywheel, gap detection, BM25 search, proposal generation,
  `apply --live` flow.
- Signed reproducible artifacts (`--sign`, `verify-artifact`).
- Watchlist + daily digest.
- Persistent expert profile.
- Multi-jurisdiction legal surface, per-state hemp-derived
  cannabinoid law.
- CourtListener / legal discovery.
- bioRxiv / medRxiv preprint discovery.
- Pesticides registry.
- Industrial-hemp material-science framing.
- Oncology palliation-vs-cure framing as a standalone surface.

These exist in the parent Cannavec plugin and may return in v0.2+
behind a constitutional amendment with documented eval coverage.

## Dependencies

- Python 3.9+ (stdlib only; no `pip install` for the runtime path).
- Network access to `eutils.ncbi.nlm.nih.gov` (PubMed E-utilities),
  `www.ebi.ac.uk/chembl/api` (ChEMBL REST), and
  `clinicaltrials.gov/api/v2` (CTGov API) for live discovery.
  All injected as fetchers in tests for offline CI.
