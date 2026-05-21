# Feature Specification: Cannavec Science Elite Development (v0.2)

**Feature Branch**: `claude/cannavec-science-elite-development`

**Created**: 2026-05-21

**Status**: Draft — pending `/speckit-plan` approval

**Input**: User request: "Add What's keeping it from 10/10 to spec kit for
elite development" — six concrete gaps identified in the 2026-05-21 elite-tier
rating (8.2/10 as a research tool, 9/10 as a disciplined MVP) that prevent
Cannavec Science from reaching genuine elite-tier (≥ 9.5/10) status as a tool
a working cannabis-research PI would put in their lab workflow tomorrow.

## Background

The Cannavec Science MVP (spec 001) shipped a research-grade demo: 824 unit
tests passing in 33 ms, six phytochemistry rigor detectors, retraction
enforcement at composition time, deterministic GRADE adapter, nine
primary-source live discovery (after the Tier-3 widening addendum in
[plan.md §Addendum](../001-science-mvp/plan.md)), and bibliography export to
BibTeX / RIS / CSL-JSON with inline GRADE annotation.

As of the 2026-05-21 elite-tier rating, the MVP scores **8.2/10 as a research
tool** and **9/10 as a disciplined MVP**. The gap between these scores and a
defensible **≥ 9.5/10** is concrete and listable — not vague aspiration.

The six gaps:

1. **No preprint discovery** (bioRxiv / medRxiv). Half of recent
   cannabinoid-mechanism work — in particular eCBome and minor-cannabinoid
   pharmacology — lives in preprints. A 2026-grade cannabis-research tool that
   ignores preprints is missing where the field is actively moving.
2. **Eval surface is sketch-tier.** 12 canonical prompts cannot
   regression-test a tool this ambitious. Elite tools have hundreds of named
   known-bad regressions, organized by detector / registry / refusal class.
3. **No citation-network analysis.** "Who else has cited this paper, and did
   the field push back?" is a routine working-scientist question this tool
   cannot answer. Citation drift and field-pushback signals are part of
   evidence weighting in real practice.
4. **No live registry-freshness signal.** Hand-curated interaction / AE / PGx
   tables decay. There is no `last_verified` per row, no PubMed-watch on the
   cited PMID, no staleness surfaced to the reader.
5. **No researcher-workflow scaffolding.** The tool stops at "give me the
   literature." Elite tools help the researcher *use* the literature: PICO
   assembly, sample-size / power calculation, GRADE evidence-profile table
   export, IRB / protocol skeleton.
6. **Cannabis-specific blind spots.** No eCBome / endocannabinoidome mapping,
   no regulatory-feasibility check (is this experiment legally feasible in
   jurisdiction X under DEA / EMA / Health-Canada), no Δ⁸-THC / HHC / THCO /
   THCP coverage at registry depth (only regex disambiguation), no
   terpene-cannabinoid entourage-effect deterministic rigor detector.

Closing all six moves the tool from "best disciplined MVP in this space" to
"elite working-scientist tool." **None requires audience expansion.**
Researcher-only audience-lock per Constitution §IV holds throughout.

## Constitutional Impact

This spec is the **v0.2 boundary**. Per Constitution §"Out Of Scope For v0.x":
"These features may exist in the larger Cannavec plugin. They are explicitly
NOT promised by this MVP." The v0.x → v0.2 transition is the moment the
deferred items in that list can be re-evaluated against the same constitutional
gates the MVP was held to.

Per-principle impact:

- **§I (Primary-Source-Or-Refuse)**: deepened by US1 (preprint primary sources
  with explicit Level D cap), US4 (citation-network attestation strengthens
  the primary-source warrant), US6 (eCBome + minor-cannabinoid primary sources
  at registry depth).
- **§II (Deterministic-Backbone Over Prose)**: extended by US5
  (PICO / power / GRADE-evidence-profile-table generators are pure deterministic
  composers, not LLM prose), US6 (entourage-effect rigor detector is a new
  deterministic enforcer).
- **§III (Test-First)**: enforced throughout — every story carries a
  test-coverage requirement and ships tests before implementation.
- **§IV (Researcher Audience Only)**: **unchanged**. Every story stays
  researcher-only. No audience-template surface added.
- **§VI (Phytochemistry Precision)**: extended by US6 (Δ⁸-THC / HHC / THCO /
  THCP isomer rigor at registry-row depth, terpene-cannabinoid entourage
  deterministic detector).
- **§VII (GRADE Honesty)**: deepened by US5 (GRADE evidence-profile table
  output), US4 (citation-network "field pushback" signal feeds the
  inconsistency-serious GRADE downgrade).
- **§VIII (Retractions Enforced At Composition)**: extended by US3 (registry
  rows now carry `last_verified` + watch PMIDs so retractions to cited papers
  invalidate the row in real time, not only at next manual curator pass).
- **§IX (Read-Time Discovery)**: widened by US1 (bioRxiv + medRxiv as new
  Tier-3 lanes with D-grade cap and `live_biorxiv` / `live_medrxiv`
  provenance tags), US3 (per-source freshness probe extended to curated rows).
- **§XI (Citable Output Is Default)**: extended by US5 (GRADE evidence-profile
  table is a new citable output format).

**No constitutional amendment is required.** US1 lifts the v0.x out-of-scope
listing for preprints by promoting the codebase to v0.2 — which is exactly the
mechanism the constitution itself defines for that list. The promotion is
documented in [plan.md §Version-Boundary-Promotion](./plan.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Preprint Discovery (Priority: P1)

**Persona**: A cannabis-mechanism researcher reading the frontier — they
need to see the 2024-2026 bioRxiv / medRxiv work on eCBome,
minor-cannabinoid receptor pharmacology, or cannabis-trial pre-prints that
have not yet completed peer review. The published-only view is six to
eighteen months behind the field.

A researcher runs `/cannavec-science:discover "endocannabinoid CB2 macrophage"
--sources biorxiv,medrxiv`. The plugin fans out across the two preprint
servers using the existing Tier-3 contract: stdlib `urllib` transport,
safety + banned-pattern preflight before any network call, injected-fetcher
offline tests. Every row carries:

- `provenance: live_biorxiv` or `live_medrxiv`
- `native_id`: DOI (e.g., `10.1101/2026.04.12.589123`)
- `posted_date`, `revision_number`, `version_history`
- `suggested_grade: (Level D, provisional, live_biorxiv)` — **always Level D
  ceiling** because preprints have not been peer-reviewed.
- `published_version_doi`: if the preprint has since been published, the
  published DOI is surfaced so the reader can prefer the peer-reviewed
  version.

The cross-source synthesis verdict treats a `live_biorxiv` row as one
distinct source, but never auto-promotes its grade and visually distinguishes
it from peer-reviewed rows in the rendered output.

**Why this priority**: P1 because it closes the single most visible
credibility gap in the 2026-05-21 rating ("missing preprints is a real
research gap in 2026"). A working scientist who runs the discover surface
on an active research question and sees only the published literature
concludes the tool is six months behind the field. One demo with a fresh
bioRxiv hit reverses that impression.

**Independent Test**:
- `python3 -m cannavec_science discover "CBD microglia" --sources biorxiv
  --max 5` returns ≥ 1 row tagged `live_biorxiv` with a valid `10.1101/...`
  DOI, `posted_date` ≥ 2024-01-01, `suggested_grade=(D, provisional,
  live_biorxiv)`.
- `tests/test_biorxiv_discover.py` and `tests/test_medrxiv_discover.py`
  cover happy-path, refusal (K2 synthesis), banned-pattern refusal, network
  error, empty result, version-history parsing, published-version
  cross-reference.
- The synthesis block in [synthesis.py](../../cannavec_science/synthesis.py)
  is extended to count `biorxiv` and `medrxiv` as distinct sources.

**Acceptance Scenarios**:

1. **Given** the query "endocannabinoid CB2 macrophage", **When**
   `/cannavec-science:discover --sources biorxiv,medrxiv` runs, **Then** the
   output lists preprint rows with `provenance ∈ {live_biorxiv,
   live_medrxiv}` and the synthesis block lists them as distinct sources.
2. **Given** a preprint that has since been published (DOI cross-reference
   resolves), **Then** the row carries `published_version_doi` and the
   composer prefers the peer-reviewed version in claim citation.
3. **Given** a banned-pattern query ("indica cures CTE"), **Then** the
   preprint lanes refuse at the discover_guard layer — **no external request
   is fired**.
4. **Given** the K2/Spice synthesis preflight hits, **Then** both preprint
   lanes hard-refuse regardless of `--sources` selection.
5. **Given** `/cannavec-science:research <question>` with a preprint hit in
   the live fan-out, **Then** the brief includes the preprint with an
   explicit Level D cap and a visible "live_biorxiv (preprint, not
   peer-reviewed)" badge alongside the citation.
6. **Given** a preprint version history (v1, v2, v3), **Then** the row
   reports `revision_number=3` and the citation cites the latest version's
   DOI by default with prior versions available in `version_history`.

---

### User Story 2 — Researcher-Workflow Scaffolding (Priority: P1)

**Persona**: A working PI or clinical-trial protocol author who has the
literature and now needs to *use* it: frame the question rigorously
(PICO), estimate sample size from the cited effect sizes, build the GRADE
evidence-profile table the journal will ask for, and draft the IRB
protocol skeleton.

Four new pure-deterministic scaffolders ship inside the existing five
commands (no new slash commands — Constitution §IV scope lock):

- **PICO drafter**: `/cannavec-science:research <question> --pico` emits a
  structured Population / Intervention / Comparator / Outcomes block
  derived deterministically from the question's intent classification +
  population registry hits.
- **Power calculator**: `/cannavec-science:research <question>
  --power-calc` reads the cited effect sizes from the linked PMIDs and
  emits sample-size-for-α=0.05-β=0.20 calculations using the standard
  two-arm formulas (continuous: Cohen's d; dichotomous: odds ratio +
  baseline rate). Stdlib-only — no scipy. Conservative on
  failure: missing inputs → "insufficient effect-size data; specify
  expected effect magnitude" rather than guessing.
- **GRADE evidence-profile table**: `/cannavec-science:research <question>
  --grade-profile` emits the table journals expect: outcome × number of
  studies × risk-of-bias × inconsistency × indirectness × imprecision ×
  publication-bias × effect estimate × certainty. Rendered as Markdown
  by default; `--grade-profile-format csv` for spreadsheet import.
- **IRB / protocol skeleton**: `/cannavec-science:research <question>
  --protocol-skeleton` emits a 9-section IRB-ready protocol stub
  (Background / Hypothesis / Specific Aims / Study Design / Population /
  Intervention / Endpoints / Statistical Analysis / Safety Monitoring),
  pre-populated from the answer's claims and PICO block. Explicit
  watermark: "Auto-generated skeleton — PI must review and supplement."

**Why this priority**: P1 because this is the lever that converts
Cannavec Science from "interesting literature-search tool" into "tool I
use for every grant / paper / protocol." The 2026-05-21 rating identified
this as the gap between 8.2/10 and elite — "stops at give me the
literature; elite tools help the researcher use the literature." Without
it, the tool's daily-use coefficient is low even if its rigor is high.

**Independent Test**:
- `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome"
  --pico` includes a `pico` block with non-empty P / I / C / O fields.
- `python3 -m cannavec_science answer "CBD PTSD" --power-calc` emits a
  sample-size estimate when effect sizes are present in cited PMIDs;
  emits an explicit "insufficient effect-size data" message otherwise.
- `python3 -m cannavec_science answer "CBD seizures" --grade-profile`
  emits a Markdown table whose rows align 1:1 with the answer's claims.
- `python3 -m cannavec_science answer "..." --protocol-skeleton` emits
  the 9-section stub with the watermark on line 1.
- New module `tests/test_pico.py`, `tests/test_power_calc.py`,
  `tests/test_grade_profile.py`, `tests/test_protocol_skeleton.py`.
  At least one positive and one "insufficient input" test per module.

**Acceptance Scenarios**:

1. **Given** a clinical-efficacy question, **When** `--pico` is set,
   **Then** the answer includes a `pico` block populated from the
   population registry and intent classifier.
2. **Given** a question whose claims cite RCTs with reported effect
   sizes (mean difference + SD, or OR + CI), **When** `--power-calc` is
   set, **Then** the answer includes per-outcome sample-size
   calculations for α=0.05 / β=0.20.
3. **Given** a question whose claims have no extractable effect size,
   **When** `--power-calc` is set, **Then** the answer surfaces
   "insufficient effect-size data — specify expected magnitude" rather
   than fabricating an estimate.
4. **Given** an answer with N claims spanning M outcomes, **When**
   `--grade-profile` is set, **Then** the GRADE table has exactly M
   outcome rows and column totals match the GRADE adapter's per-claim
   downgrades.
5. **Given** `--protocol-skeleton`, **Then** the emitted document is
   < 1500 words, has exactly nine `## ` section headers, and carries
   the auto-generation watermark on line 1.
6. **Given** the user combines `--pico --power-calc --grade-profile
   --protocol-skeleton` in one invocation, **Then** all four blocks
   compose without conflict in the rendered Markdown output.

---

### User Story 3 — Eval-Suite Expansion to ≥ 100 Prompts (Priority: P1)

**Persona**: The maintainer of Cannavec Science (current and future)
needs a regression battery dense enough that any change to the
deterministic backbone — a new banned pattern, a tightened rigor
detector, a registry edit, a new live source, a refactor — produces a
clear pass/fail signal across the entire research surface.

The current `evals/canonical_research_questions.json` ships **12 prompts**.
The elite tier requires **≥ 100 canonical eval prompts** distributed
across:

- **Curated-registry hits**: ≥ 25. Cover each registry (major
  cannabinoids, minor cannabinoids, terpenes, interactions, AEs,
  populations, contraindications, PGx) with ≥ 3 prompts each.
- **Rigor positives (detector must fire)**: ≥ 30. ≥ 5 per detector ×
  6 detectors = 30 minimum, exercising boundary cases for each detector's
  false-positive guards.
- **Rigor negatives (detector must NOT fire)**: ≥ 20. Adversarial
  near-miss prompts that previously caused false positives in
  regression history.
- **Refusal class**: ≥ 15. Safety preflight (K2 synthesis,
  individualized dosing, pregnancy, paediatric, etc.) and
  banned-pattern refusals.
- **Live discovery**: ≥ 10. One per `live_*` source (PubMed, ChEMBL,
  CTGov, PubChem, PharmGKB, RCSB, Open Targets, GWAS, BindingDB,
  bioRxiv) — exercise the discoverer and the synthesis verdict.
- **Cross-cutting / regression**: ≥ 5. Each one a named known-bad
  output from the change-history of Cannavec Science. New regressions
  add a prompt; the count grows monotonically.

Every prompt declares the same expectation shape used by the current
12 — `is_refusal`, `min_claims`, `min_grade`, `must_include_pmid`,
`rigor_detectors_fire`, `must_not_banned`, etc. The eval runner
(`evals/run_evals.py`) gates CI: any regression fails the build.

**Why this priority**: P1 because eval coverage is the **foundation**
that protects every other story in this spec. Without ≥ 100 prompts,
US1 (preprints), US5 (workflow scaffolding), and US6 (cannabis blind
spots) cannot be added with confidence. The 2026-05-21 rating
specifically flagged this — "elite tools have hundreds of named
known-bad regressions" — and the entire deterministic-backbone
philosophy depends on a regression battery dense enough to catch drift.

**Independent Test**:
- `evals/canonical_research_questions.json` contains ≥ 100 prompts
  conforming to the existing schema.
- Category counts meet the per-bucket minimums above.
- `python3 evals/run_evals.py` exits 0 on a clean build and exits
  non-zero on any planted regression.
- `tests/test_eval_coverage.py` enforces the per-bucket minimums as a
  unit test so future contributors cannot lower the bar.

**Acceptance Scenarios**:

1. **Given** the populated eval file, **When** the maintainer counts
   prompts by `category`, **Then** every bucket meets its minimum and
   the total is ≥ 100.
2. **Given** a planted regression (e.g., a deliberately-broken rigor
   detector), **When** `run_evals.py` runs, **Then** the build fails
   with the specific failing prompt named.
3. **Given** a new banned pattern added to the registry, **Then** the
   eval suite includes ≥ 1 positive and ≥ 1 negative prompt covering
   the new pattern.
4. **Given** a registry row whose cited PMID is later retracted,
   **Then** the eval includes a regression prompt asserting the row
   is suppressed under `--retraction-policy strict`.
5. **Given** `tests/test_eval_coverage.py`, **Then** the test fails if
   any bucket falls below its minimum count.
6. **Given** the runner reports a failure, **Then** the report names
   the prompt id, the failing expectation, and the actual output —
   the maintainer fixes the code, not the eval.

---

### User Story 4 — Citation-Network & Field-Pushback Signal (Priority: P2)

**Persona**: A researcher reviewing a draft or evaluating a claim
needs to know not just "is this paper real" but "what did the field
say about it afterward." A cited paper with 50 follow-up citations
that pushed back is a different evidence weight than a paper cited
once by its own authors.

`/cannavec-science:verify <PMID>` is extended with a citation-network
block:

- **Citation count** from PubMed's E-utilities `elink cmd=neighbor`
  (with NCBI etiquette: tool/email query params, polite User-Agent).
- **Forward-citation sentiment**: applies the existing
  `pubmed_sentiment()` from [synthesis.py](../../cannavec_science/synthesis.py)
  to each forward-cite abstract, returning per-cite direction
  (`supports`, `refutes`, `neutral`). Aggregates into a
  `field_pushback_signal: {supports: N, refutes: M, neutral: K}` block.
- **Replication / failure-to-replicate flag**: if ≥ 2 forward cites
  contain explicit replication language (`"we replicated"`,
  `"we failed to replicate"`, `"did not reproduce"`), the result is
  surfaced as `replication_status: replicated` /
  `replication_status: replication_failed` / `replication_status: mixed`.
- The signal feeds `apply_grade_modifiers(inconsistency_serious=True)`
  when forward-cite refute count > support count by ≥ 2 — the GRADE
  adapter downgrades the claim by one level. This makes
  field-pushback **deterministic**, not a prose note.

**Why this priority**: P2 because it deepens existing rigor rather
than opening new surface. The MVP already verifies citations exist;
this story adds "did the field accept them." Critical for elite tier
but not blocking for daily use.

**Independent Test**:
- `python3 -m cannavec_science verify 28538134` returns the existing
  Devinsky-2017 block plus a `citation_network` field with `count`,
  `field_pushback_signal`, and `replication_status`.
- `tests/test_citation_network.py` covers: ≥ 1 cite, mixed pushback,
  replication-success language, replication-failure language,
  network-error fallback, NCBI-rate-limit graceful degradation.
- The GRADE downgrade integration is tested in
  `tests/test_evidence.py`: an inconsistency-serious flag set by the
  citation-network signal correctly drops a Level B claim to Level C.

**Acceptance Scenarios**:

1. **Given** a verified PMID with ≥ 1 forward citation, **When**
   `verify` runs, **Then** the response includes a `citation_network`
   block with non-zero `count`.
2. **Given** forward citations with > 2 refute-sentiment hits and
   ≤ 1 support-sentiment hits, **Then** the
   `field_pushback_signal.aggregate` is `"refute_heavy"` and the
   suggested GRADE downgrade flag is set.
3. **Given** ≥ 2 forward cites with explicit replication language,
   **Then** `replication_status` is set; cases without replication
   language report `replication_status: not_reported`.
4. **Given** an NCBI rate-limit response, **Then** the verify
   surface degrades gracefully — returns the existing PubMed record
   with `citation_network: {error: "rate_limited"}` rather than
   failing the whole verify call.
5. **Given** the `--json` flag, **Then** the citation_network block
   is part of the structured output schema for downstream tooling.
6. **Given** `compose_answer` cites a paper whose citation network
   shows refute-heavy pushback, **Then** the composer applies
   `inconsistency_serious=True` and the claim's grade is one level
   lower than the same paper without pushback would yield.

---

### User Story 5 — Registry Freshness & Retraction-Watch (Priority: P2)

**Persona**: A long-tail Cannavec Science user — the tool has been
in their workflow for six months. They need confidence that the
hand-curated registries (interactions, AEs, contraindications, PGx)
have not silently rotted: cited PMIDs may have been retracted, new
evidence may have shifted a Level B claim to Level A, regulator
status (FDA approval, scheduling) may have changed.

Every registry row gains two new fields:

- `last_verified: "YYYY-MM-DD"` — date the row's primary citations
  were last re-checked against PubMed + Crossref + retraction
  registry by the curator (or by the automated freshness probe).
- `watch_pmids: tuple[str, ...]` — the set of PMIDs the registry
  row's claim depends on. The retraction-watch probe re-verifies
  these on a schedule.

Two new CLI subcommands:

- `python3 -m cannavec_science freshness [--registry <name>]` — runs
  the existing `pubmed_verify` + retraction lookup against every
  `watch_pmids` in the named registry (or all). Reports per-row
  status: `clean` / `retraction_detected` / `eoc_detected` /
  `network_error` / `last_verified_stale`. Stale = `last_verified`
  older than 180 days.
- `python3 -m cannavec_science freshness-report --since YYYY-MM-DD`
  — emits a Markdown freshness report for the curator: rows whose
  cited PMIDs have flipped state since the given date.

**No automatic mutation of registry rows.** The probe surfaces the
gap; the curator updates the row by hand. This preserves the
"curated rows never auto-promoted" discipline of Constitution §IX,
extended in mirror to "curated rows never auto-invalidated."

The `compose_answer` path is extended: if a row whose
`last_verified` is > 365 days old is composed into an answer, the
rendered citation block carries a `[freshness: stale (verified
YYYY-MM-DD)]` suffix. The answer still renders — staleness is a
caveat, not a block — but the reader sees it.

**Why this priority**: P2 because it pays off over months, not
in the first session. Critical for long-term trust but not
blocking for the demo or first-week adoption.

**Independent Test**:
- Every existing registry row (interactions, AEs, contraindications,
  PGx, populations, terpenes, major + minor cannabinoids) has
  `last_verified` and `watch_pmids` populated at registry-build time.
- `python3 -m cannavec_science freshness --registry interactions`
  exits 0 with a per-row status table.
- `tests/test_freshness.py` covers: clean probe, retraction-detected
  probe, eoc-detected probe, stale-verified probe, network-error
  probe (graceful degradation), CLI exit codes.
- `tests/test_answer_freshness.py` asserts the `[freshness: stale]`
  suffix appears when the registry row is older than 365 days.

**Acceptance Scenarios**:

1. **Given** every registry row, **Then** the row's dataclass
   carries `last_verified: str` and `watch_pmids: tuple[str, ...]`
   fields populated.
2. **Given** `python3 -m cannavec_science freshness --registry
   interactions`, **Then** the output is a per-row status table
   with one row per `watch_pmid`.
3. **Given** a retracted PMID detected in the freshness probe,
   **Then** the report flags it and the row is candidate for
   curator review — **the row is not auto-mutated**.
4. **Given** a row with `last_verified` > 365 days ago composed
   into an answer, **Then** the rendered citation has the
   `[freshness: stale]` suffix.
5. **Given** `freshness-report --since 2026-01-01`, **Then** the
   report lists rows whose `watch_pmids` changed state since that
   date.
6. **Given** any network failure during the probe, **Then** the
   row status is `network_error` and the probe continues to the
   next row rather than aborting.

---

### User Story 6 — Cannabis-Specific Blind-Spot Closures (Priority: P2)

**Persona**: A working endocannabinoid researcher whose questions
sit in the gaps the MVP doesn't cover: minor cannabinoids at
registry depth (Δ⁸-THC, HHC, THCO, THCP), endocannabinoidome
mapping (the eCBome — endocannabinoid + cannabinoid-like lipid
mediators + their receptors / transporters / enzymes), regulatory
feasibility ("can I legally study this in jurisdiction X under
DEA / EMA / Health-Canada"), terpene-cannabinoid entourage claims.

Four blind-spot closures:

1. **Minor-cannabinoid registry depth.** [minor_cannabinoids.py](../../cannavec_science/minor_cannabinoids.py)
   gains rows for Δ⁸-THC, HHC, THCO, THCP at the same evidence-honesty
   depth as the existing THCV/CBDV/CBC/CBN/CBG rows. Where peer-reviewed
   evidence is genuinely absent (THCO, THCP), the row honestly grades as
   `Unsupported` with an explicit "no admissible primary evidence; see
   preprint discovery" pointer — not hidden.
2. **eCBome reference module.** New module `cannavec_science/ecbome.py`
   encoding the endocannabinoidome's primary mediators (AEA, 2-AG, PEA,
   OEA, virodhamine, NADA, 2-AGE, NAGly), receptors (CB1, CB2, GPR55,
   GPR119, GPR18, PPARα, PPARγ, TRPV1, TRPA1, TRPM8), enzymes (FAAH,
   MAGL, DAGLα, DAGLβ, NAPE-PLD, ABHD6, ABHD12, COX-2 secondary
   metabolism), transporters (FABP5, FABP7). Every entry carries a
   UniProt or HMDB primary identifier.
3. **Regulatory-feasibility advisory.** New module
   `cannavec_science/regulatory_feasibility.py` that, given a research
   question + jurisdiction (US-federal / EU-EMA / Canada / UK-MHRA),
   reports whether the proposed work touches Schedule I controlled
   substances and what licensing path applies (DEA Schedule I research
   registration, MHRA controlled-drug licence, Health-Canada research
   exemption, etc.). **Advisory only** — explicit watermark "This is
   not legal advice; consult your institutional research-compliance
   office." Conservative on the gray zones (Δ⁸ THC US-federal, HHC
   EU-novel-food).
4. **Terpene-cannabinoid entourage rigor detector.** Extend
   [rigor_checks.py](../../cannavec_science/rigor_checks.py) with
   `detect_entourage_overclaim()`. Fires when text claims a specific
   terpene + cannabinoid synergy (e.g., "myrcene potentiates THC")
   without citing one of the small set of papers with measured
   evidence (Russo 2011, Finlay 2020, Santiago 2019, LaVigne 2021).
   Conservative — the entourage hypothesis is open-empirical with
   mixed evidence; the detector enforces grade honesty, not the
   hypothesis itself.

**Why this priority**: P2 because each closes a specific blind spot
named in the rating. Together they remove the "missing where the
research is actually going in 2026" criticism. None blocks the demo
or first-week use; each materially raises the daily-use coefficient
for working researchers in their respective lanes.

**Independent Test**:
- `python3 -m cannavec_science answer "What is the evidence for
  Δ⁸-THC analgesia?"` returns a brief that includes the new minor-
  cannabinoid row at the appropriate grade.
- `python3 -m cannavec_science answer "Map the endocannabinoidome
  enzymes regulating 2-AG"` returns rows naming MAGL (Q99685),
  ABHD6, ABHD12, DAGLα (Q9Y4D2) with UniProt IDs.
- `python3 -m cannavec_science answer "Can I study Δ⁹-THC in
  rats in California?" --regulatory-feasibility` returns the DEA
  Schedule I research-registration path with the explicit "not
  legal advice" watermark.
- `python3 -m cannavec_science rigor "myrcene potentiates THC's
  sedative effect"` fires the new `entourage_overclaim` detector;
  the same sentence with a Russo-2011 citation does not fire.
- New tests: `tests/test_ecbome.py`, `tests/test_regulatory_feasibility.py`,
  `tests/test_entourage_detector.py`, and extensions to
  `tests/test_minor_cannabinoids.py`.

**Acceptance Scenarios**:

1. **Given** the question "What is the evidence for HHC analgesia?",
   **Then** the answer surfaces the new HHC row with grade honest
   to current literature (likely Unsupported or Level D) — never
   inflated.
2. **Given** the question about eCBome enzymes, **Then** the
   answer cites every named enzyme with UniProt ID and the
   receptor-without-id rigor check returns zero violations.
3. **Given** a US-federal regulatory-feasibility query about a
   Schedule I cannabinoid, **Then** the output names the DEA
   Schedule I research-registration path and includes the watermark.
4. **Given** an entourage-effect claim without a primary citation,
   **Then** the entourage_overclaim detector fires with a
   resolution hint pointing at the four canonical entourage papers.
5. **Given** an entourage claim with one of the four canonical
   citations, **Then** the detector does NOT fire.
6. **Given** the regulatory-feasibility module receives a jurisdiction
   outside the supported set (US, EU, Canada, UK), **Then** it returns
   `unsupported_jurisdiction` rather than fabricating advice.

---

### Edge Cases

- **Preprint that gets retracted before peer review**: bioRxiv supports
  withdrawal; the freshness probe (US3) catches withdrawn preprints by
  re-fetching the DOI and flagging the row.
- **Preprint that disagrees with the published version**: the
  `published_version_doi` cross-reference (US1) surfaces both, and the
  composer prefers the peer-reviewed version while keeping the preprint
  visible.
- **Power calculator on a single-arm or open-label trial**: emits
  "single-arm — power-calculation requires two-arm design; specify
  expected effect magnitude vs historical control."
- **GRADE evidence-profile table with zero claims**: emits the table
  header with one row reading "No admissible evidence — see Unsupported
  claims block."
- **Citation network for a paper with zero forward cites**: the verify
  surface reports `count: 0` and does not invoke the GRADE downgrade
  flag.
- **Freshness probe on a row whose watch_pmid is itself retracted**:
  the row status flips to `retraction_detected` and the answer renders
  with `[freshness: retracted-citation]` until the curator updates it.
- **Eval expansion runner crashes**: the per-prompt isolation in
  `run_evals.py` reports the crashing prompt id and continues.
- **eCBome question that names a non-eCBome receptor**: the receptor-
  without-id detector still fires on the non-eCBome receptor; the eCBome
  module does not lift the receptor-id requirement.
- **Regulatory-feasibility query on a state-level question (e.g.,
  California-specific)**: reports the US-federal layer plus an explicit
  "state-level law varies; out of MVP scope; see parent Cannavec plugin
  for per-state coverage" pointer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-201**: System MUST live-fan-out queries to bioRxiv and medRxiv
  on the same Tier-3 contract as the existing nine sources (stdlib
  urllib, injected fetchers, safety + banned-pattern preflight,
  `live_<source>` provenance, never auto-promoted to curated tier).
- **FR-202**: System MUST cap any preprint-only-supported claim at
  Level D in the GRADE adapter, regardless of grade hints from the
  preprint server.
- **FR-203**: System MUST emit a PICO block deterministically from
  question intent + population registry when `--pico` is set.
- **FR-204**: System MUST emit a sample-size / power calculation
  deterministically from cited effect sizes when `--power-calc` is
  set, OR emit an "insufficient effect-size data" message when the
  inputs are absent. No guessing.
- **FR-205**: System MUST emit a GRADE evidence-profile table
  (Markdown or CSV) deterministically from the typed `Answer` when
  `--grade-profile` is set, with column totals matching the GRADE
  adapter's per-claim downgrades.
- **FR-206**: System MUST emit a 9-section IRB / protocol skeleton
  carrying a `Auto-generated skeleton — PI must review and supplement`
  watermark on line 1 when `--protocol-skeleton` is set.
- **FR-207**: System MUST ship ≥ 100 canonical eval prompts in
  `evals/canonical_research_questions.json` meeting per-bucket
  minimums (≥ 25 curated, ≥ 30 rigor-positive, ≥ 20 rigor-negative,
  ≥ 15 refusal, ≥ 10 live-discovery, ≥ 5 cross-cutting).
- **FR-208**: System MUST enforce eval-suite bucket minimums via a
  unit test so future contributors cannot reduce coverage silently.
- **FR-209**: System MUST extend `verify <PMID>` with a
  `citation_network` block reporting forward-citation count,
  field-pushback signal, and replication status.
- **FR-210**: System MUST apply `inconsistency_serious=True` in the
  GRADE adapter when the citation-network field-pushback signal is
  `refute_heavy` (refutes > supports + 2), producing a deterministic
  one-level downgrade.
- **FR-211**: System MUST extend every registry row with
  `last_verified: str` and `watch_pmids: tuple[str, ...]` fields.
- **FR-212**: System MUST expose `python3 -m cannavec_science
  freshness` and `freshness-report` subcommands that probe
  `watch_pmids` against PubMed + retraction registry without
  auto-mutating registry rows.
- **FR-213**: System MUST append `[freshness: stale (verified
  YYYY-MM-DD)]` to citations whose backing registry row's
  `last_verified` is > 365 days old.
- **FR-214**: System MUST extend [minor_cannabinoids.py](../../cannavec_science/minor_cannabinoids.py)
  with rows for Δ⁸-THC, HHC, THCO, THCP at honest evidence depth
  (no inflation; Unsupported is acceptable).
- **FR-215**: System MUST ship a new `cannavec_science/ecbome.py`
  module mapping endocannabinoidome mediators, receptors, enzymes,
  and transporters — every entry carries a UniProt or HMDB primary
  identifier.
- **FR-216**: System MUST ship a `cannavec_science/regulatory_feasibility.py`
  module advisory-only with the watermark "This is not legal
  advice; consult your institutional research-compliance office,"
  covering US-federal, EU-EMA, Canada, UK-MHRA jurisdictions.
- **FR-217**: System MUST extend [rigor_checks.py](../../cannavec_science/rigor_checks.py)
  with `detect_entourage_overclaim()` — fires on terpene-cannabinoid
  synergy claims missing one of the canonical entourage citations
  (Russo 2011, Finlay 2020, Santiago 2019, LaVigne 2021).
- **FR-218**: System MUST hold all existing FR-001 through FR-010
  from spec 001 unchanged — including FR-010 (exactly five slash
  commands). The new functionality ships as flags on existing
  commands and new subcommands of `python3 -m cannavec_science`,
  not new slash commands.
- **FR-219**: System MUST remain stdlib-only (Constitution §X). Any
  proposed dependency requires a written justification in
  [plan.md](./plan.md) and an explicit stdlib fallback path.
- **FR-220**: System MUST hold the offline-test guarantee — every
  new network path injects a fetcher in tests so
  `python3 -m unittest discover -s tests` runs without network.

### Key Entities

- **`PreprintRow`**: a live-discovery row from bioRxiv / medRxiv
  carrying DOI, posted_date, revision_number, version_history,
  published_version_doi, provisional Level D grade,
  `live_biorxiv` / `live_medrxiv` provenance.
- **`PICOBlock`**: a Population / Intervention / Comparator /
  Outcomes block emitted deterministically from intent + populations.
- **`PowerCalculation`**: per-outcome sample-size estimate for
  α=0.05 / β=0.20 with explicit effect-size inputs and formula
  used (Cohen's d / OR / proportion-difference).
- **`GradeEvidenceProfile`**: a row per outcome with columns
  (#studies, risk-of-bias, inconsistency, indirectness, imprecision,
  publication-bias, effect estimate, certainty).
- **`ProtocolSkeleton`**: a 9-section IRB-ready Markdown stub with
  the auto-generation watermark.
- **`CitationNetworkBlock`**: forward-citation count + per-cite
  sentiment counts + replication status + aggregate field-pushback
  classification.
- **`FreshnessStatus`**: per-row probe result: `clean` /
  `retraction_detected` / `eoc_detected` / `last_verified_stale` /
  `network_error`.
- **`EcbomeEntry`**: an endocannabinoidome entity (mediator /
  receptor / enzyme / transporter) with UniProt or HMDB ID, role,
  primary citations.
- **`RegulatoryFeasibilityAdvisory`**: per-jurisdiction +
  per-compound advisory (schedule, licensing path, gray-zone
  flags, watermark).
- **`EntourageViolation`**: a terpene-cannabinoid synergy claim
  missing a canonical primary citation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-201**: A researcher running `/cannavec-science:discover "CB2
  microglia" --sources biorxiv,medrxiv --max 5` sees ≥ 1 preprint
  row tagged `live_biorxiv` or `live_medrxiv` with a valid `10.1101/...`
  DOI and a Level D grade ceiling that is visually distinct from
  peer-reviewed rows.
- **SC-202**: A researcher running `/cannavec-science:research "CBD
  Dravet" --pico --power-calc --grade-profile --protocol-skeleton`
  receives all four scaffolds in one composed Markdown answer, each
  deterministically derived from the underlying claims.
- **SC-203**: `evals/canonical_research_questions.json` contains
  ≥ 100 prompts meeting every per-bucket minimum, and `python3
  evals/run_evals.py` exits 0 on a clean build.
- **SC-204**: `python3 -m cannavec_science verify 28538134` returns
  the existing Devinsky-2017 record plus a `citation_network` block;
  a planted refute-heavy forward-cite set deterministically
  downgrades the same claim by one GRADE level in `compose_answer`.
- **SC-205**: Every existing registry row carries `last_verified`
  and `watch_pmids`; `python3 -m cannavec_science freshness`
  produces a status table; a synthetic retracted-watch-pmid is
  caught and flagged without mutating the registry row.
- **SC-206**: `python3 -m cannavec_science answer "What is the
  evidence for HHC analgesia?"` returns a brief with the HHC row
  at honest grade; `python3 -m cannavec_science rigor "myrcene
  potentiates THC sedation"` fires the entourage-overclaim
  detector; a US-federal regulatory-feasibility query on Δ⁹-THC
  rat research returns the DEA Schedule I path with the watermark.
- **SC-207**: `python3 -m unittest discover -s tests` exits 0 in
  ≤ 60 seconds on a stdlib-only Python ≥ 3.9 environment with no
  network access. Total test count rises from 824 to ≥ 1,100 with
  the new modules.
- **SC-208**: Total Python LOC under `cannavec_science/` stays under
  **25,000 lines** (versus the v0.1 cap of 20,000, expanded by ~25%
  to accommodate four new modules and the workflow scaffolders).
  The slash-command count stays at exactly **five**.
- **SC-209**: The 2026-05-21 elite-tier rating (or its successor)
  re-runs and scores the tool ≥ 9.5/10 across the same ten
  dimensions, with the specific gaps from §"What's keeping it from
  10/10" each demonstrably closed.

## Out Of Scope (Explicit)

These items are deliberately deferred past v0.2:

- **Multi-audience templates** (patient, clinician, cultivator, lab,
  compliance, retail, policy, hemp, microbiome, veterinary) —
  Constitution §IV still holds; audience expansion requires its own
  spec and a constitutional amendment.
- **Per-state US regulatory feasibility** — US-federal layer only.
  Per-state hemp-derived cannabinoid law and per-state Schedule I
  research law lives in the parent Cannavec plugin.
- **Signed reproducible artifacts** (`--sign`, `verify-artifact`).
- **KB flywheel / gap detection / proposal generation / `apply --live`**.
- **CourtListener / legal discovery**.
- **Pesticides registry**.
- **AlphaFold predicted structures as equivalent to RCSB experimental
  structures** — preprint policy (Level D cap) does not transfer to
  predicted structures, which would need their own rigor framing.
- **Automatic curator agent that mutates registry rows on freshness
  probe results** — US3 surfaces the gap; human curator updates the row.

## Dependencies

- Python 3.9+, stdlib only (Constitution §X).
- Network access to bioRxiv API (`api.biorxiv.org`) and medRxiv API
  (`api.medrxiv.org`) for US1 — injected fetchers in tests.
- NCBI E-utilities `elink cmd=neighbor` endpoint for US4 — same
  polite-User-Agent contract as `pubmed_verify`.
- No new runtime deps. Test deps unchanged.

## Open Questions

The following are explicitly deferred to [plan.md](./plan.md) for the
implementing engineer to resolve, not blockers for spec approval:

- Whether the four scaffolders in US2 land as four separate flags or as
  one `--scaffold pico,power,grade,protocol` enum — UX call.
- Whether US5's freshness probe runs synchronously per-row or fans out
  with a small thread pool (stdlib `concurrent.futures.ThreadPoolExecutor`
  is allowed) — performance call when the registry watch-set grows.
- Whether US4's citation-network sentiment uses the existing
  `pubmed_sentiment()` regex as-is or grows a small replication-language
  classifier — accuracy/scope call.
