# Feature Specification: Industry-Expert Depth Release (v0.4)

**Feature Branch**: `claude/fervent-lovelace-3jFjR`

**Created**: 2026-05-21

**Status**: Approved for `/speckit-plan` and immediate implementation

**Input**: User request: "continue developing this elite research plugin
for cannabis by using spec-kit and picking up what needs to be done to
level up this project significantly — v0.4 plus any new bugs surfaced by
an industry-expert review of the v0.3 surface."

## Background

Spec 003 closed every P1/P2/P3 finding from the 2026-05-21 industry-expert
review of v0.2 and shipped the v0.3 routing-and-surfacing release.
Spec 003 also scoped two **v0.4 horizon items** that sit inside
Constitution §IV (researcher-only) but outside v0.3's clinical-pharmacology
focus:

- **US11 — Analytical-chemistry registry** (≥ 8 rows): decarboxylation
  kinetics, HPLC/GC method validation, chemovar classification, vapor
  pyrolysis byproducts.
- **US12 — Cultivation-science registry** (≥ 6 rows): light-spectrum
  effects, trichome biology, synthase genetics, botanical taxonomy.

A second-pass industry-expert review of v0.3 — done at the head of
`claude/fervent-lovelace-3jFjR`, with 1,143 unit tests passing and the
119/119 offline eval suite green — found **three new issues** inside the
otherwise-credible v0.3 surface, all inside the existing researcher-only
audience lock:

- **N1 (P1, demo-blocker)** — `Answer.notes` set by
  `_classify_zero_claims` is computed correctly but never rendered in
  `Answer.to_markdown()`. A researcher running `decarboxylation kinetics
  of THCA` gets the silent `Claims: 0` output instead of the well-crafted
  v0.3 classification ("0 curated claims: this question is in §IV but
  sits in the v0.4 analytical-chemistry horizon — use the `discover`
  subcommand"). Spec 003 US9 / FR-009 advertised this surface; v0.3
  shipped the data layer but not the render layer.
- **N2 (P2, confidence-laundering)** — `indica vs sativa pharmacological
  differences` returns silent 0 claims. The banned-pattern regex requires
  an effect/sedative keyword (sleep / sedat / energ / uplift / relax) to
  appear within 180 chars of "indica" / "sativa". When the researcher
  writes the abstract question ("pharmacological differences" alone), no
  keyword matches and the system silently returns 0 claims — implicitly
  accepting the framing rather than refusing it.
- **N3 (P3, cosmetic)** — the registry inventory subcommand emits no
  entries for newly-shipped v0.4 registries until they are wired into
  `cannavec_science/registries.py`. v0.3 only inventoried the 9 existing
  registries; v0.4 needs two more groups.

This spec **bundles US11 + US12 from spec 003 with closures for N1, N2,
N3**, and the surrounding eval / docs / version-bump work needed to ship
v0.4 cleanly. Every story stays inside Constitution §IV. No amendment
required.

## What v0.3 Already Does Well (preserve in v0.4)

These are the surfaces v0.4 MUST NOT regress. Every regression is a
constitution violation:

1. Δ⁸-THC / HHC / THCO / THCP route to their own minor-cannabinoid
   monographs, NOT to the Δ⁹-THC monograph (US1).
2. `HHC safety profile` returns 0 cannabinoid-attributed AE claims (US2).
3. `entourage effect evidence` returns `highest_grade: Unsupported`
   unless the canonical-citation set (Russo 2011 / Finlay 2020 / Santiago
   2019 / LaVigne 2021) is hit (US3).
4. `source-health` does not crash with AttributeError (US4).
5. `verify` accepts PMID, DOI, NCT, ChEMBL, and UniProt (US5).
6. `cannabis × tacrolimus` matches the CBD-tacrolimus row (US6).
7. `anandamide FAAH inhibition` surfaces the eCBome registry (US7).
8. `registries` subcommand emits the inventory (US8).
9. Zero-claim cases set `Answer.notes` — even when not rendered (US9).
10. Rigor-report violations are deduplicated by `(detector, span)` (US10).
11. K2/Spice hard-refuse, banned-pattern detector, retraction enforcement,
    GRADE wording-vs-grade guard, span-aware `NamedCannabinoidSet`,
    cannabinoid-scoped registry detectors all hold.

## Review Methodology (v0.3 second pass)

Same shape as spec 003: every test is a `python3 -m cannavec_science <cmd>`
invocation against HEAD of `claude/fervent-lovelace-3jFjR`. Findings are
P1 / P2 / P3 by severity. Findings either point to a new shipping issue
(N-prefix) or restate a v0.4 horizon item from spec 003 (US-prefix).

### Findings transcript

```
$ python3 -m cannavec_science answer "decarboxylation kinetics of THCA in cannabis flower"
**Q:** decarboxylation kinetics of THCA in cannabis flower
**Audience:** researcher
**Generated:** 2026-05-21T21:33:01Z

## Evidence summary
- Highest evidence grade across claims: **Unsupported**
- Claims: 0
- Claims with primary source: 0
```

But the internal state DOES carry the v0.3 classification:

```
$ python3 -c "from cannavec_science.answer import compose_answer
>>> a = compose_answer('decarboxylation kinetics of THCA in cannabis flower')
>>> print(a.notes)
('0 curated claims: this question is in §IV (research-grade) but sits in
the v0.4 analytical-chemistry / cultivation-science horizon — see spec
003 US11 / US12. Use the `discover` subcommand for a live PubMed / ChEMBL
search.',)
```

The classification is set; the render is missing.

```
$ python3 -m cannavec_science answer "indica vs sativa pharmacological differences"
**Q:** indica vs sativa pharmacological differences
## Evidence summary
- Highest evidence grade across claims: **Unsupported**
- Claims: 0
- Claims with primary source: 0
```

The banned-pattern detector requires a sedative/energetic keyword in the
prompt; "pharmacological differences" alone does not satisfy the
co-occurrence constraint, so the silent-0-claims case fires instead of
the refusal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Analytical-chemistry registry seed (Priority: P2, was US11)

A cannabis-research PI asks `Decarboxylation kinetics of THCA in cannabis
flower at 110°C`, or `HPLC vs GC-MS for cannabinoid potency`, or
`Cannabis vapor pyrolysis byproducts at combustion versus vaporisation
temperatures`. v0.3 returns 0 claims for every analytical-chemistry
question because no registry covers the topic.

**Why this priority**: This is the largest content gap an industry expert
hits in v0.3 — the topic is research-grade primary-literature analytical
chemistry, sits inside Constitution §IV, and was explicitly named in
spec 003 as the v0.4 horizon. P2 (not P1) because the absence is honest —
the 0-claim classification (once rendered, US3 below) tells the user
exactly which horizon item to expect. But once US3 lands, the actionable
"discover" hint will be more credible if it has a curated registry to
fall back on.

**Independent Test**: A new `analytical_chemistry.py` module with at
least 8 registry rows, each citing primary literature. Each row carries
a positive + negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("Decarboxylation kinetics of THCA at 110°C")`,
   **When** the analytical-chemistry registry is in place, **Then** at
   least one Level C or Level D claim is emitted with a primary
   citation (Veress 1990 PMID 2384545 or equivalent rate-constant
   primary literature).
2. **Given** `compose_answer("HPLC vs GC-MS cannabinoid quantitation")`,
   **When** the registry is in place, **Then** the GC-induced decarb
   artefact warning is surfaced as a Level C claim — the same artefact
   the THCA-vs-THC rigor detector catches at prose level.
3. **Given** `compose_answer("Type II chemovar genetic basis")`, **When**
   the registry is in place, **Then** the Hazekamp & Fischedick 2012 (or
   equivalent) chemovar classification is surfaced.
4. **Given** `compose_answer("Cannabis vapor pyrolysis byproducts")`,
   **When** the registry is in place, **Then** the combustion-vs-
   vaporisation byproduct profile is surfaced (Pomahacova 2009 or
   equivalent) as a Level C claim.

---

### User Story 2 — Cultivation-science registry seed (Priority: P2, was US12)

A cannabis-research PI in a horticultural-science department asks
`UV-B effect on cannabinoid biosynthesis`, or `Trichome density and
cannabinoid yield`, or `THCA synthase versus CBDA synthase chemotype
inheritance`, or `Is Cannabis sativa one species or three?`. v0.3
returns 0 claims for every cultivation-science question.

**Why this priority**: Same shape as US1. P2 because the absence is
honest (once US3 renders the classification) but a researcher in plant
science deserves a curated landing surface.

**Independent Test**: A new `cultivation_science.py` module with at least
6 registry rows, each citing primary literature. The botanical-taxonomy
row coexists with the existing indica/sativa banned pattern (they are
distinct intents — botany vs pharmacology).

**Acceptance Scenarios**:

1. **Given** `compose_answer("UV-B effect on cannabinoid biosynthesis")`,
   **When** the cultivation-science registry is in place, **Then** at
   least one Level C claim is emitted (Lydon 1987 PMID 3621052 or
   equivalent — the canonical UV-B / THC primary literature).
2. **Given** `compose_answer("THCA synthase CBDA synthase chemotype
   inheritance")`, **When** the registry is in place, **Then** the
   de Meijer 2003 primary citation (Genetics) is surfaced as Level C.
3. **Given** `compose_answer("Is Cannabis sativa one species or three?")`,
   **When** the registry is in place, **Then** the botanical-taxonomy
   row (Small & Cronquist 1976 / Mediavilla & Steinemann 1997 / McPartland
   2018) is surfaced as a Level C claim WITHOUT firing the indica/sativa-
   as-pharmacology banned pattern — the prompt is botany, not pharmacology.
4. **Given** `compose_answer("Trichome density cannabinoid yield")`,
   **When** the registry is in place, **Then** the Livingston 2020
   (or equivalent) glandular-trichome primary literature is surfaced.

---

### User Story 3 — Render `Answer.notes` (Priority: P1, new finding N1)

`compose_answer` sets a well-crafted 0-claim classification on
`Answer.notes` (per spec 003 US9 / FR-009), but `Answer.to_markdown()`
never renders that field. Every analytical-chemistry / cultivation /
out-of-scope-audience query silently emits `Claims: 0` and stops — the
researcher gets no actionable hint.

**Why this priority**: P1. spec 003 SC-006 acceptance was the
classification predicate; the render side was not unit-tested. v0.4 must
close the loop so the researcher actually sees the hint. Once US1 and
US2 ship, the "use `discover` subcommand" hint becomes the bridge
between the registry-uncurated case and the live-discovery surface.

**Independent Test**: A unit test asserts that
`compose_answer("decarboxylation kinetics of THCA").to_markdown()`
contains the substring "analytical-chemistry" or "use the `discover`"
(both phrases from `_classify_zero_claims`).

**Acceptance Scenarios**:

1. **Given** `compose_answer("decarboxylation kinetics of THCA").to_markdown()`,
   **When** the markdown is emitted (AFTER US1 lands, classification
   shifts to the new `OutOfScopeDeferred` path), **Then** the markdown
   MUST include the deferred-classification hint OR — once US1 ships —
   the analytical-chemistry registry rows.
2. **Given** `compose_answer("Bedrocan cultivar THC content").to_markdown()`,
   **When** the markdown is emitted, **Then** the markdown MUST include
   the out-of-scope-audience hint pointing at the parent Cannavec plugin.
3. **Given** `compose_answer("CBD evidence in Dravet syndrome").to_markdown()`,
   **When** claims are present, **Then** no zero-claim hint section is
   rendered (regression-protected — the hint is conditional on zero
   claims).
4. **Given** the JSON output (`--json`), **When** the answer is
   serialised, **Then** the `notes` field MUST be present in the JSON.

---

### User Story 4 — Strengthen indica/sativa banned-pattern (Priority: P2, new finding N2)

The v0.3 banned-pattern regex for indica/sativa-as-pharmacology requires
a sedative/energetic keyword (sleep / sedat / energ / uplift / relax /
alert / daytime / focus / cerebral / etc.) to appear within 180 chars
of the indica/sativa noun. A researcher writing the abstract question
"indica vs sativa pharmacological differences" satisfies neither half of
the regex and gets a silent 0-claims output — the framing slips through.

**Why this priority**: P2 (not P1) because the existing pattern correctly
catches the most common framing failures (the v0.2 demo input "Indica
strains are sedating because they have more myrcene"). The gap is the
abstract / meta question, which is rare but worth catching: a researcher
asking it deserves the same crisp pushback the prose-form question gets.

**Independent Test**: A unit test asserts that
`detect_banned_patterns("indica vs sativa pharmacological differences")`
returns a hit with the same `indica_sativa_as_pharmacology` pattern ID.
A negative test asserts that
`detect_banned_patterns("Cannabis sativa L. botanical taxonomy")` does
NOT fire (botany is a distinct intent — US2 needs this distinction).

**Acceptance Scenarios**:

1. **Given** `detect_banned_patterns("indica vs sativa pharmacological
   differences")`, **When** the detector runs, **Then** the
   `indica_sativa_as_pharmacology` pattern fires with the existing
   replacement guidance ("Describe by chemotype Type I/II/III/IV/V…").
2. **Given** `detect_banned_patterns("indica vs sativa effects")`,
   **When** the detector runs, **Then** the same pattern fires.
3. **Given** `detect_banned_patterns("Cannabis sativa L. botanical
   taxonomy and species debate")`, **When** the detector runs, **Then**
   no banned-pattern hit is emitted (this is research-grade botany, not
   pharmacology framing).
4. **Given** `compose_answer("indica vs sativa pharmacological
   differences")`, **When** the composer runs, **Then** the refusal
   surface (NOT the silent-0-claims surface) fires.

---

### User Story 5 — Inventory the new registries (Priority: P3, new finding N3)

`python3 -m cannavec_science registries` does not list
analytical-chemistry or cultivation-science rows until the new groups
are wired into `cannavec_science/registries.py`. This is mechanical
follow-on work to US1 and US2.

**Independent Test**: A unit test asserts that `build_inventory()`
includes both new groups, each with row counts and entry labels.

**Acceptance Scenarios**:

1. **Given** `build_inventory()`, **When** the inventory is built after
   US1 and US2 land, **Then** the result includes an
   `analytical_chemistry` group with row_count ≥ 8 and a
   `cultivation_science` group with row_count ≥ 6.
2. **Given** `build_inventory("analytical_chemistry")`, **When** the
   command runs, **Then** only that group is returned.
3. **Given** `python3 -m cannavec_science registries --format json`,
   **When** the command runs after v0.4 lands, **Then** the JSON
   includes both new groups.

---

### User Story 6 — Eval bucket for v0.4 (Priority: P3)

The v0.3 eval suite has 130 prompts in 6 buckets (curated /
rigor_positive / rigor_negative / refusal / live / cross_cutting /
routing_surfacing). v0.4 adds a new `analytical_cultivation` bucket
with at least 12 prompts exercising:

- Decarboxylation kinetics at multiple temperatures.
- HPLC vs GC-MS quantitation.
- Chemovar Type I/II/III/IV/V classification.
- Vapor pyrolysis byproducts.
- UV-B / light-spectrum / synthase-genetics / trichome-biology.
- The botanical-taxonomy distinction (US4 negative test).
- N1 regression: 0-claim hint rendered.

**Acceptance Scenarios**:

1. **Given** the eval suite, **When** `python3 evals/run_evals.py` runs,
   **Then** the `analytical_cultivation` bucket has at least 12 prompts
   and all pass. Total eval prompt count rises to ≥ 142 (offline ≥ 131).
2. **Given** the v0.3 buckets, **When** evals run, **Then** every existing
   bucket still meets its minimum (regression-protected).

---

### Edge Cases

- **`Cannabis sativa L. botanical taxonomy`** must coexist with the
  banned-pattern strengthening (US4): the botany intent does NOT trip
  the pharmacology detector. The new cultivation_science row carries
  the canonical citation; the strengthened banned-pattern regex
  excludes "sativa L." / "botanical taxonomy" / "species" framing
  from the indica/sativa pharmacology pattern.
- **`THCA decarboxylation kinetics`** must coexist with the THCA-vs-THC
  rigor detector. The analytical-chemistry registry row CITES the
  decarb chemistry and surfaces it as Level C; the rigor detector
  catches THCA-vs-THC conflation at the PROSE level. The two surfaces
  do not double-render.
- **`GC-MS cannabis potency`** must coexist with the THCA-vs-THC
  detector. The registry row surfaces "GC-MS produces in-injector
  decarboxylation; the apparent THC reading on a GC-MS chromatogram
  is the sum of native THC + decarboxylated THCA." This is the same
  artefact the rigor detector catches in prose; the registry surfaces
  it as a curated claim WITH a primary citation, and the rigor detector
  still fires when an answer body contains the conflated wording.
- **`UV-B and cannabinoid biosynthesis`** must not double-render with
  any eCBome receptor. UV-B is a cultivation parameter; no eCBome
  receptor is named in the prompt.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new `analytical_chemistry.py` module MUST ship with at
  least 8 registry rows covering: THCA → Δ⁹-THC decarboxylation kinetics
  (≥ 2 rows at different temperature/matrix conditions), HPLC vs GC-MS
  quantitation method validation (≥ 2 rows including the GC in-injector
  decarboxylation artefact), chemovar classification Type I/II/III/IV/V
  (≥ 2 rows), and vapor pyrolysis byproducts (≥ 1 row covering benzene
  / toluene / naphthalene at combustion vs vaporisation temperatures).
  Each row carries a primary PMID / DOI citation per Constitution §I,
  a `to_claim()` method that returns a typed `Claim`, and at least one
  positive + one negative unit test.
- **FR-002**: A new `cultivation_science.py` module MUST ship with at
  least 6 registry rows covering: light spectrum / UV-B effects on
  cannabinoid biosynthesis (≥ 1 row), trichome density / glandular
  trichome biology (≥ 1 row), THCA-synthase / CBDA-synthase allelic
  dominance and chemotype inheritance (≥ 2 rows), and botanical taxonomy
  (Cannabis sativa as one species vs three) (≥ 1 row). Each row carries
  a primary citation per Constitution §I, a `to_claim()` method, and at
  least one positive + one negative unit test.
- **FR-003**: `compose_answer` MUST import `analytical_chemistry` and
  `cultivation_science` and surface matching rows. Detection is on
  topic-keyword regex (decarb-kinetics / HPLC / GC-MS / chemovar /
  pyrolysis for analytical; UV-B / trichome / synthase / botanical
  taxonomy for cultivation), NOT on cannabinoid-name match (cultivation
  / analytical questions are about the PLANT or METHOD, not a single
  named cannabinoid).
- **FR-004**: `Answer.to_markdown()` MUST render `Answer.notes` as a
  trailing `## Notes` section when present and the answer is not a
  refusal. JSON output (`--json`) MUST surface the `notes` field at
  top level.
- **FR-005**: The `indica_sativa_as_pharmacology` banned-pattern regex
  MUST also fire when the prompt names indica/sativa alongside the
  abstract words `pharmacolog\w*` / `effect\w*` / `difference\w*`,
  WITHOUT firing on the botany framing
  (`sativa\s+L\.?` / `botanical\s+taxonomy` / `species\s+debate` /
  `taxonom\w*`). The implementation MAY add a second sibling pattern
  rather than mutating the existing one — the goal is the same
  refusal verdict, not a regex bicycle-shed.
- **FR-006**: `cannavec_science/registries.py` MUST add two builder
  functions and entries in `all_registry_groups()` /
  `_BUILDERS` for `analytical_chemistry` and `cultivation_science`.
  The CLI handler for `python3 -m cannavec_science registries
  --registry <name>` MUST accept the two new names.
- **FR-007**: The eval suite gains a new `analytical_cultivation`
  bucket with at least 12 prompts, and the bucket-minimum enforcement
  table in `canonical_research_questions.json` includes
  `analytical_cultivation: 10` (floor of 10 to allow for honest
  v0.4-horizon scope; the bucket actually ships ≥ 12).
- **FR-008**: The version stamp bumps to `0.4.0` in three places:
  `.claude-plugin/plugin.json`, `pyproject.toml`,
  `cannavec_science/__init__.py`.
- **FR-009**: README adds a "v0.4 industry-expert-depth" section
  describing what landed; the demo script gains a v0.4-flow block.

### Key Entities

- **AnalyticalChemistryRow**: dataclass with `name`, `topic`
  (decarb_kinetics / hplc_validation / gc_ms_artefact / chemovar /
  pyrolysis), `claim_text`, `claim_type`, `evidence_level`,
  `primary_citations` (tuple of typed citations with PMID / DOI),
  `last_verified`, `watch_pmids`. Implements `to_claim()` returning
  a typed `Claim` for the composer's claim list.
- **CultivationScienceRow**: dataclass with `name`, `topic`
  (light_spectrum / trichome_biology / synthase_genetics /
  botanical_taxonomy), `claim_text`, `claim_type`, `evidence_level`,
  `primary_citations`, `last_verified`, `watch_pmids`. Implements
  `to_claim()` for the composer.
- **DetectAnalyticalChemistryMention** / **DetectCultivationScienceMention**:
  Topic-keyword regex matchers (NOT cannabinoid-name) that return the
  matching subset of registry rows. Idiomatically these mirror the
  existing `detect_ae_mention` / `detect_interaction_mention` shape so
  the composer wire-up is uniform.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (v0.4 acceptance): `python3 -m unittest discover -s tests`
  exits 0 with at least **1,190 tests** (≥ 47 new tests across
  analytical chemistry, cultivation science, the notes-render bug, the
  banned-pattern strengthening, and the registry inventory wiring).
- **SC-002** (v0.4 acceptance): `python3 -m cannavec_science answer
  "Decarboxylation kinetics of THCA at 110°C"` returns at least one
  Level C or Level D claim with the canonical primary citation; the
  highest_grade is no longer `Unsupported` for analytical-chemistry
  prompts.
- **SC-003** (v0.4 acceptance): `python3 -m cannavec_science answer
  "Is Cannabis sativa one species or three?"` returns at least one
  Level C claim, sourced to the cultivation_science registry, AND
  does NOT fire the indica/sativa-as-pharmacology banned pattern.
- **SC-004** (v0.4 acceptance): `python3 -m cannavec_science answer
  "indica vs sativa pharmacological differences"` returns a refusal
  with the strengthened banned-pattern hit (NOT a silent 0-claims
  output).
- **SC-005** (v0.4 acceptance): `python3 -m cannavec_science answer
  "decarboxylation kinetics of THCA"` markdown output includes the
  classification hint OR — once the registry surfaces rows — the
  curated rows. Either way, the user is not staring at the silent
  `Claims: 0` block.
- **SC-006** (v0.4 acceptance): `python3 -m cannavec_science registries`
  emits both new groups (analytical_chemistry, cultivation_science) in
  markdown and `--format json`.
- **SC-007** (v0.4 acceptance): The eval suite has at least **142
  prompts** (offline ≥ 131), with `analytical_cultivation` bucket
  meeting its minimum and every existing bucket regression-protected.
- **SC-008** (v0.4 acceptance): `.claude-plugin/plugin.json`,
  `pyproject.toml`, `cannavec_science/__init__.py` all report
  version `0.4.0`.
- **SC-009** (v0.4 acceptance): README's "What ships" section
  documents the v0.4 deliverables (≥ 8 analytical-chemistry rows;
  ≥ 6 cultivation-science rows; rendered 0-claim hints;
  strengthened indica/sativa pattern).
- **SC-010** (v0.4 acceptance): Total Python LOC under
  `cannavec_science/` stays under **30,000**.

### Industry-Expert Trust Heuristics (qualitative, but checked at demo)

- **Analytical-chemistry test**: a formulation scientist asks
  "decarboxylation kinetics at 110°C" — gets a Level C / Level D
  primary-cited registry row, not silence.
- **Cultivation-science test**: a horticultural researcher asks
  "UV-B effect on cannabinoid biosynthesis" — gets the Lydon 1987
  primary citation, not silence.
- **Honest-hint test**: a researcher asks a question that genuinely
  has no curated row — the v0.3 classification message renders, NOT
  the silent `Claims: 0` block.
- **Indica/sativa abstraction test**: the abstract question is
  refused with the same crisp guidance as the prose form, AND the
  botany framing escapes the refusal cleanly.

## Assumptions

- v0.4 stays inside Constitution §IV (researcher only). The new
  registries are research-grade primary-literature topics, NOT
  retail / cultivator / lab-QC audience surfaces.
- v0.4 stays stdlib-only per §X. No new runtime dependencies.
- The existing 1,143 unit tests are regression-protected — none weaken
  under v0.4 changes. The 2-second total runtime is the ceiling.
- The five-slash-command lock per Constitution §IV holds.
- The Hazekamp & Fischedick chemovar paper (2012) was published in
  Cannabis & Cannabinoid Research / Chemistry & Biodiversity and has a
  resolvable DOI; the Veress 1990 decarb-kinetics paper has PMID 2384545;
  the Lydon 1987 UV-B paper has PMID 3621052; the de Meijer 2003 paper
  has PMID 12663552. These four citations are the v0.4 backbone and
  ship in the very first registry rows.
- The botanical-taxonomy debate (Small & Cronquist 1976 / Hillig &
  Mahlberg 2004 / Mediavilla & Steinemann 1997 / McPartland 2018) is
  reflected as a Level C claim that *acknowledges the debate* without
  claiming resolution — the same evidentiary honesty Cannavec Science
  applies to entourage-effect prompts.
- No new slash commands. The new registries are surfaced through the
  existing `answer` / `ask` / `discover` / `rigor` commands and the
  Python-module `registries` subcommand.

## Constitutional Impact

This spec is an in-constitution evolution. Per-principle impact:

- **§I (Primary-Source Or Refuse)**: deepened by FR-001 / FR-002 —
  every new registry row carries a primary PMID / DOI per §I.
- **§II (Deterministic-Backbone Over Prose)**: deepened by FR-003
  (analytical / cultivation detectors are deterministic topic-keyword
  matchers), FR-005 (strengthened banned-pattern is a deterministic
  refusal enforcer).
- **§III (Test-First)**: enforced — every user story carries the
  positive + negative test triples. v0.4 ships ≥ 47 new tests.
- **§IV (Researcher Audience Only)**: **unchanged**. Analytical
  chemistry + cultivation science are research-grade topics, not
  audience surfaces.
- **§V (Safety-Layer Sovereignty)**: unchanged.
- **§VI (Phytochemistry Precision)**: deepened by US1 — decarboxylation
  kinetics and GC-MS-in-injector artefact rows surface the SAME
  precision the v0.3 THCA-vs-THC rigor detector enforces at prose
  level.
- **§VII (GRADE Honesty)**: deepened — every new registry row caps
  evidence grade at the source-tier maximum.
- **§VIII (Retractions At Composition)**: unchanged — new rows
  participate in the existing retraction-suppression flow.
- **§IX (Live Discovery)**: unchanged.
- **§X (Stdlib-Only)**: unchanged.
- **§XI (Citable Output Is The Default)**: deepened — bibliography
  export continues to work over the v0.4 typed Answer, including the
  new analytical-chemistry / cultivation-science citations.

No amendment is required. The v0.x → v0.2 boundary (already crossed in
spec 002) is the mechanism for v0.4: research-grade analytical and
cultivation depth is the kind of extension §IV explicitly permits.
