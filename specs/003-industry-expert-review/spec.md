# Feature Specification: Cannabis Industry-Expert Review & v0.3 Roadmap

**Feature Branch**: `claude/beautiful-wozniak-CAmSt`

**Created**: 2026-05-21

**Status**: Draft — pending `/speckit-plan` approval

**Input**: User request: "Rigorously test this cannabis Claude research
plugin on how much an expert in the cannabis industry would like to use it
and add what could make it better to the spec-kit for future development."

## Background

This spec captures the findings of a hands-on review of Cannavec Science
v0.2 from the perspective of a working cannabis-industry research expert
(the audience the Constitution §IV locks the plugin to). The review
exercised every shipped surface (`answer`, `discover`, `verify`, `rigor`,
`freshness`, `source-health`, the four v0.2 scaffolders, and the
`--regulatory-feasibility` flag) against a battery of real questions a
cannabis-research PI, formulation scientist, or industry-research lead
would actually type on day one.

The headline: **Cannavec Science v0.2 already does the hard part well.**
The deterministic backbone, GRADE wording-vs-grade guard, K2 hard-refuse,
banned-pattern detector, retraction enforcement, freshness probe,
regulatory-feasibility advisory, and the seven rigor detectors are all
on-spec and trustworthy in the demo path. A working scientist would
recognise — within five minutes — that the tool is doing real work, not
LLM theatre.

The review found **four shipping bugs**, **three confidence-laundering
failure modes**, and **eight industry-expert coverage gaps**. All sit
inside the existing researcher-only audience lock (§IV holds throughout).
None require a constitutional amendment.

This spec proposes a **v0.3 routing-and-surfacing release** that closes
the bugs and confidence-laundering, plus a **v0.4 industry-expert depth
release** that closes the coverage gaps. v0.3 is shippable on the
existing test/eval infrastructure; v0.4 is the next horizon.

## Review Methodology

Each test below was run as a stdlib-only `python3 -m cannavec_science <cmd>`
invocation against the v0.2 build at HEAD of
`claude/beautiful-wozniak-CAmSt` (1,064 unit tests passing). Findings are
labelled by:

- **Severity**: P1 (correctness bug or demo-blocker), P2 (misleading /
  confidence-laundering), P3 (coverage / discoverability gap).
- **Constitutional principle implicated**: e.g. §I (Primary-Source), §VI
  (Phytochemistry Precision), §VII (GRADE Honesty), §VIII (Retraction
  Enforcement), §IX (Live Discovery).

The test prompts were chosen to mirror what a working cannabis-research
PI would ask in their first session — not synthetic adversarial probes,
not the canonical demo path. The mix:

- **Clinical pharmacology**: CBD/Dravet (golden path), CBD/warfarin,
  CBD/tacrolimus, Δ⁹-THC/anxiety dose-response, CBD PK oral vs sublingual.
- **Minor cannabinoid pharmacology**: Δ⁸-THC pharmacology + safety,
  HHC pharmacology + safety, CBN sleep, CBG antibacterial.
- **Analytical / process chemistry**: THCA decarboxylation kinetics,
  cannabis vapor pyrolysis byproducts.
- **Endocannabinoid system**: eCB system regulation of inflammation,
  anandamide / PEA / eCBome reference questions.
- **Entourage / terpene science**: entourage-effect evidence,
  myrcene-potentiates-THC, indica-vs-sativa.
- **Industry framing**: pesticide residue limits, Bedrocan cultivar
  THC content, cannabis hyperemesis syndrome diagnostic criteria.
- **Hard refuses**: K2/Spice synthesis route (must hard-refuse), cure
  claims, natural-therefore-safe.
- **Verifier surface**: PMID 28538134, DOI, NCT02224560, ChEMBL5803,
  UniProt P21554.
- **Scaffolders**: `--pico --power-calc --grade-profile
  --protocol-skeleton --regulatory-feasibility us`.

## What v0.2 Already Does Well (preserve in v0.3 / v0.4)

These are the surfaces a cannabis-research expert would put in their
working rotation today. v0.3 and v0.4 MUST NOT regress them.

1. **K2/Spice hard-refuse** — Constitution §V is enforced verbatim,
   with a Poison Control number. An industry expert reading this
   refusal sees the safety layer is real, not prose.
2. **Banned-pattern detector + negation guard** — indica/sativa-as-
   pharmacology, cure claims, and "natural therefore safe" all fire
   crisp, citable refusals with one-line reasoning.
3. **Six core rigor detectors** — isomer collapse, THCA-vs-THC,
   dose-without-route, receptor-without-ID, matrix-unit, decarb-
   context-missing all fire deterministically on prompt-level text.
4. **Entourage-overclaim detector** — fires on
   "myrcene potentiates Δ⁹-THC's sedative effect" with the right
   canonical-citation resolution (Russo 2011 / Finlay 2020 / Santiago
   2019 / LaVigne 2021).
5. **GRADE wording-vs-grade verb picker** — Level A claims read
   "evidence shows", Level C reads "evidence suggests", Unsupported
   reads honestly as unsupported.
6. **Retraction enforcement at composition** (§VIII) — strict default,
   with a visible "N claims suppressed" header when it bites.
7. **Drug-interaction registry rigor** — `Does CBD interact with
   warfarin?` returns the correct Level C claim with both Grayson 2018
   (PMID 29744288) and Damkier 2019 (doi:10.1111/bcpt.13345) — the
   pair of canonical citations a pharmacist would expect.
8. **Cannabis Hyperemesis Syndrome (CHS)** — the registry knows the
   syndrome is paradoxical, requires cessation not adjustment, and is
   reversible. Industry-relevant and right.
9. **CBN sleep honesty** — refuses to confidence-launder; explicitly
   says marketing claims outpace the evidence base, cites Russo 2018
   as the synthesis position. A formulation scientist would respect
   this.
10. **Regulatory-feasibility advisory (US)** — DEA Schedule I researcher
    registration, 21 CFR §1301.18, NIDA Drug Supply Program reference,
    6–18 month timeline. Watermark "This is not legal advice; consult
    your institutional research-compliance office." is exactly right.
11. **Freshness probe** — surfaces every registry row's `watch_pmids`
    with `clean` / `retracted` / `stale` status without auto-mutating.
12. **PICO scaffolder** — labels comparator as "unresolved" honestly
    when the claim doesn't anchor one. Better than guessing.
13. **Test suite + eval suite** — 1,064 unit tests in ~2 s, deterministic,
    offline. This is the credibility floor.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fix cannabinoid-specific monograph routing (Priority: P1)

A cannabis-research expert asks `Δ⁸-THC pharmacology and safety` (or the
Latin-1 equivalent `Delta-8-THC potency and CB1 binding`). v0.2 returns
**the Δ⁹-THC monograph**, not the Δ⁸-THC monograph. The Δ⁸-THC monograph
exists in the registry (verified at
`cannavec_science/minor_cannabinoids.py:1131`) but the answer composer
fires the major-cannabinoid monograph instead.

**Why this priority**: This is a Constitution §VI (Phytochemistry
Precision) violation visible in the demo path. The whole point of the
plugin is that bare "THC" is rejected — but the composer itself collapses
Δ⁸-THC into the Δ⁹-THC monograph as soon as `detect_major_cannabinoid_
mention` matches on the substring "THC". An industry expert testing
Δ⁸-THC routes for one minute hits this and loses trust.

**Root cause**: `compose_answer` at `cannavec_science/answer.py:633-635`
gates on `total_compounds_named >= 2` and treats Δ⁹-THC + Δ⁸-THC as a
"comparison" — but the user did not ask for comparison; they named a
single specific isomer.

**Independent Test**: A unit test asserts that
`compose_answer("Δ⁸-THC pharmacology")` returns:

1. No Δ⁹-THC monograph block.
2. The Δ⁸-THC entry from the minor-cannabinoid monograph rendered.
3. `total_compounds_named` distinguishes "Δ⁸-THC alone" from
   "Δ⁸-THC vs Δ⁹-THC".

**Acceptance Scenarios**:

1. **Given** `compose_answer("Δ⁸-THC pharmacology and safety")`,
   **When** the composer fires registry detectors, **Then** the major-
   cannabinoid monograph for Δ⁹-THC MUST NOT be emitted, and the
   Δ⁸-THC monograph MUST be emitted instead.
2. **Given** `compose_answer("HHC vs Δ⁸-THC pharmacology")`,
   **When** the composer fires registry detectors, **Then** both the
   HHC and Δ⁸-THC monographs are emitted (a real comparison query).
3. **Given** `compose_answer("THCP CB1 affinity")`, **When** the
   composer fires, **Then** the THCP monograph is emitted (not the
   Δ⁹-THC monograph).

---

### User Story 2 — Cannabinoid-scoped adverse-event surfacing (Priority: P1)

An industry expert asks `HHC safety profile and adverse events`. v0.2
returns **26 claims**, all about CBD or Δ⁹-THC, **none about HHC**. The
AE detector fires the full registry on the keyword "safety" / "adverse"
without filtering by the cannabinoid named in the prompt. The HHC
monograph (which DOES carry HHC-specific safety information) is rendered
later in the output, but the "Claims" block shows 26 CBD/THC AEs with
"highest evidence grade: Level C" — an industry expert reads the claim
list as if it answered their question.

**Why this priority**: This is a Constitution §VII (GRADE Honesty Over
Confidence-Laundering) violation. The user asked about HHC; the answer
attributes 26 Level-C-graded claims about other cannabinoids to the
question. A pharmacovigilance officer would file this as a finding.

**Why this priority (cont.)**: It is also a §I violation — claims must
cite a primary source for *the named compound*. None of the 26 AE rows
cite HHC-specific primary sources because the registry doesn't yet have
HHC-specific AE rows; the surfacing layer should reflect that absence
honestly rather than substitute neighbouring cannabinoids' AE data.

**Independent Test**: A unit test asserts that
`compose_answer("HHC safety profile")` returns 0 cannabinoid-attributed
AE claims (because the HHC AE row count is 0) and surfaces "No HHC-
specific adverse-event registry rows; see HHC monograph for narrative
safety profile" as an explicit gap notice.

**Acceptance Scenarios**:

1. **Given** `compose_answer("HHC safety profile and adverse events")`,
   **When** AE detection runs, **Then** the AE rows MUST be filtered to
   those whose `cannabinoid` field intersects the prompt's named
   cannabinoid set (= {"HHC"}), and the result MUST be the empty list.
2. **Given** the empty filtered AE set, **When** the answer renders,
   **Then** the claim list MUST report "0 HHC-specific AE rows; the
   HHC monograph below carries the narrative safety summary" rather
   than emitting unrelated CBD/THC rows.
3. **Given** `compose_answer("CBD adverse events in paediatric
   epilepsy")`, **When** AE detection runs, **Then** the AE rows MUST
   include the CBD-Dravet AE rows and MUST exclude the Δ⁹-THC AE rows
   (cannabinoid scope filter applied).
4. The same filtering rule applies to **contraindications** and
   **interactions** and **populations** when the prompt names a
   specific cannabinoid.

---

### User Story 3 — Anti-confidence-laundering on grade aggregation (Priority: P1)

An industry expert asks `What is the evidence that the entourage effect
is real?`. v0.2 returns **highest evidence grade: Level A**. The Level A
citations are PMID 29768152 + PMID 28815401 — Devinsky 2018
(CBD-Lennox-Gastaut) and Gaston 2017 (CBD-AE patterns in epilepsy). These
have **nothing to do with the entourage effect**; the composer dumped the
full cannabinoid-monograph claim set into the answer and reported the
highest grade across the dump, not the highest grade *for the asked
question*.

**Why this priority**: This is the most consequential §VII violation in
the review. The wording-vs-grade verb picker is correct *per claim*, but
the **answer-level "highest grade" summary** in
`EvidenceSummary.highest_grade` is computed across all retrieved claims
regardless of topical relevance. A working scientist reads
"highest evidence grade: Level A" and assumes the entourage effect has
Level A evidence behind it. It does not — the answer should report
"highest evidence grade: Unsupported" with a "no claims topically
relevant to the entourage hypothesis are at-or-above Level D" note.

**Independent Test**: A unit test asserts that for
`compose_answer("entourage effect evidence")`, the EvidenceSummary's
`highest_grade` is `Unsupported`, and a new `topical_relevance` filter
or `claim_relevance_signal` is applied between registry-detect and
grade-aggregate.

**Acceptance Scenarios**:

1. **Given** `compose_answer("entourage effect evidence")`, **When**
   `EvidenceSummary.highest_grade` is computed, **Then** it MUST NOT be
   ≥ Level B unless a cited claim is itself topically about the
   entourage hypothesis (anchored by Russo 2011 / Finlay 2020 / Santiago
   2019 / LaVigne 2021).
2. **Given** the same prompt, **When** claims are emitted, **Then**
   the answer MUST distinguish "claims topically relevant to the
   question" (graded as relevant) from "claims pulled from the
   monograph for context" (rendered separately, not graded as
   evidence *for* the question).
3. **Given** `compose_answer("CBD evidence in Dravet syndrome")`,
   **When** topical relevance is computed, **Then** the Dravet claim
   IS topically relevant and the highest grade remains Level B
   (regression-protected).

---

### User Story 4 — Fix `source-health` CLI AttributeError (Priority: P1)

`python3 -m cannavec_science source-health` crashes immediately with
`AttributeError: 'SourceHealth' object has no attribute 'ok'`.

**Why this priority**: A demo-blocker. An industry expert running the
README's documented health-check command sees a Python traceback. Every
other CLI surface works; this one ships broken.

**Root cause**: `cannavec_science/__main__.py:536` reads
`status = "ok" if h.ok else "FAIL"` and `h.rtt_ms` and `h.error`. The
actual `SourceHealth` dataclass at `cannavec_science/source_health.py:93`
exposes `status: HealthStatus` (an enum: GREEN/YELLOW/RED),
`latency_ms`, and `error_excerpt`. The CLI handler was written against
an obsolete `SourceHealth` shape.

**Independent Test**: A CLI smoke test asserts
`python3 -m cannavec_science source-health` exits 0 (when all sources are
reachable) or returns a structured non-zero (when some are red),
without raising AttributeError.

**Acceptance Scenarios**:

1. **Given** the CLI is invoked with `source-health` and an injected
   probe that returns green for all sources, **When** the handler
   formats the output, **Then** no AttributeError is raised and each
   source prints `green (rtt <N>ms)`.
2. **Given** the CLI is invoked with `--sources pubmed,chembl,ctgov`,
   **When** the handler runs, **Then** only the three requested
   sources are printed and the exit code is 0 if all are green,
   1 otherwise.
3. **Given** the CLI is invoked with `--json`, **When** the handler
   runs, **Then** structured JSON with `source`, `status`, `latency_ms`,
   `error_excerpt` is emitted.

---

### User Story 5 — `verify` accepts NCT / ChEMBL / UniProt (Priority: P1)

Constitution §I lists "PMID, DOI, ChEMBL ID, NCT ID, or UniProt
accession" as the five primary-source identifiers. `python3 -m
cannavec_science verify NCT02224560` returns
`[error] not a recognized identifier: NCT02224560`. Same for `CHEMBL5803`
and `P21554`.

**Why this priority**: §I says these identifiers anchor every claim the
plugin emits. If the `verify` surface cannot resolve them, the
verification path is narrower than the citation path — a working
scientist who pastes the NCT ID from a Cannavec answer into `verify` to
spot-check it gets an error message. The README implicitly promises
identifier-anchored verifiability; the surface MUST keep that promise.

**Independent Test**: Three offline-injected-fetcher unit tests assert
that `verify` resolves an NCT ID (via ClinicalTrials.gov API v2), a
ChEMBL ID (via the ChEMBL REST), and a UniProt accession (via UniProt
REST), with the expected positive + negative + network-error test
triples per Constitution §III.

**Acceptance Scenarios**:

1. **Given** `verify NCT02224560`, **When** the CLI resolves the
   identifier, **Then** the trial title, status, completion date, and
   primary outcome are surfaced; exit code 0.
2. **Given** `verify CHEMBL5803`, **When** the CLI resolves the
   identifier, **Then** the compound name, formula, structure SMILES,
   and bioactivity summary are surfaced; exit code 0.
3. **Given** `verify P21554`, **When** the CLI resolves the identifier,
   **Then** the protein name (CB1 / CNR1), organism, and primary
   structure metadata are surfaced; exit code 0.
4. **Given** `verify XYZ123`, **When** the CLI fails to match any of
   the five identifier shapes, **Then** the error message MUST list
   all five accepted shapes (PMID, DOI, NCT, ChEMBL, UniProt) so the
   user can re-key correctly.

---

### User Story 6 — `cannabis × <drug>` interaction expansion (Priority: P2)

An industry expert asks `cannabis interaction with tacrolimus`. v0.2
returns 0 claims. The CBD-tacrolimus row exists in the interactions
registry at `cannavec_science/interactions.py:271` with the canonical
case-report citations, but the detector requires the prompt to name
both `CBD` (or `THC`) and `tacrolimus` literally. "cannabis" alone is
not expanded to the {CBD, Δ⁹-THC, CBN, CBG, THCV} cannabinoid set.

**Why this priority**: This is the most common phrasing a clinician-
researcher or transplant pharmacist would use. The registry has the
data; the detector is too literal. P2 not P1 because the workaround
(`CBD tacrolimus`) succeeds — but no industry expert phrases the
question that way on their first try.

**Independent Test**: A unit test asserts that
`detect_interaction_mention("cannabis interaction with tacrolimus")`
returns the CBD-tacrolimus row (and any other rows whose partner_drug
matches "tacrolimus"), via a cannabis-noun → cannabinoid-set expansion.

**Acceptance Scenarios**:

1. **Given** the prompt contains "cannabis" (or "marijuana", or
   "marihuana", or "weed") and a partner-drug name, **When** the
   detector runs, **Then** the interaction rows for ALL cannabinoids
   whose `partner_drug` matches the named drug MUST be returned.
2. **Given** the prompt contains "cannabis warfarin", **When** the
   detector runs, **Then** the CBD-warfarin AND Δ⁹-THC-warfarin rows
   are returned.
3. **Given** the prompt names a specific cannabinoid AND the word
   "cannabis", **When** the detector runs, **Then** the specific
   cannabinoid wins (no double-rendering of the same row).

---

### User Story 7 — Thread the endocannabinoidome registry into `compose_answer` (Priority: P2)

`compose_answer("endocannabinoid system regulation of inflammation")`
returns 0 claims. The 28-entry eCBome registry at
`cannavec_science/ecbome.py` is fully populated (mediators / receptors /
enzymes / transporters with UniProt or HMDB IDs per §I) but **nothing
in `compose_answer` calls into it**. Verified by grep on `answer.py`
and `__main__.py`: no import of `ecbome` from either module.

**Why this priority**: The README's "What ships" section advertises
the eCBome reference as a v0.2 deliverable. An industry expert asking
about anandamide, 2-AG, FAAH, MAGL, GPR55, PEA, or NAPE-PLD expects to
hit it — and gets nothing. The data is on the shelf; the wiring is
missing. P2 not P1 because the data is correct (no false claims),
just unsurfaced.

**Independent Test**: A unit test asserts that
`compose_answer("anandamide FAAH inhibition")` emits eCBome entries
for anandamide (HMDB ID) and FAAH (UniProt accession) with their
primary citations attached.

**Acceptance Scenarios**:

1. **Given** the prompt names an eCBome mediator, receptor, enzyme,
   or transporter, **When** `compose_answer` runs, **Then** the
   matched eCBome entries MUST be attached as citations + claims at
   the appropriate GRADE level (Level B for receptor pharmacology,
   Level C for in-vitro enzyme kinetics, Unsupported for prose-only
   hypotheses).
2. **Given** `compose_answer("PEA anti-inflammatory")`, **When** the
   composer runs, **Then** the PEA eCBome entry is surfaced AND the
   "inflammation" topic keyword from `intent.topic_keywords` triggers
   the matched inflammation-relevant claims.
3. **Given** `compose_answer("CBD evidence in Dravet syndrome")`,
   **When** the composer runs, **Then** the eCBome registry is NOT
   spuriously surfaced (the prompt doesn't name an eCBome entity).

---

### User Story 8 — Monograph / registry index command (Priority: P2)

There is no way for a working scientist to ask "what cannabinoids /
interactions / AEs do you cover?" without grepping the source tree. The
v0.2 build covers Δ⁹-THC, CBD, THCA, CBDA, THCV, CBDV, CBC, CBN, CBG,
Δ⁸-THC, HHC, THCO, THCP — but a researcher has no way to discover this
list except by asking each one individually.

**Why this priority**: Industry expert discoverability. The first
question a domain expert asks when sitting down with a new tool is
"what's in your registry?" v0.2 has no answer surface for this. P2
because the data is correct when prompted by name, just not browsable.

**Independent Test**: A new subcommand `python3 -m cannavec_science
registries` (or `monographs`) emits the registry inventory.

**Acceptance Scenarios**:

1. **Given** `python3 -m cannavec_science registries`, **When** the
   command runs, **Then** the output lists every covered cannabinoid,
   terpene, interaction-row partner_drug, AE category, contraindication,
   PGx allele, and eCBome entry — grouped by registry — with row
   counts and last-verified dates.
2. **Given** `python3 -m cannavec_science registries --registry
   minor_cannabinoids --format json`, **When** the command runs,
   **Then** structured JSON suitable for piping into `jq` is emitted.
3. **Given** the user asks `"What cannabinoids are in your registry?"`
   via `answer`, **When** the composer detects the meta-query intent,
   **Then** the registry inventory is surfaced inline rather than
   returning 0 claims.

---

### User Story 9 — Honest "0 claims" surfacing (Priority: P2)

When `compose_answer` returns 0 claims (e.g. for `Bedrocan medical
cannabis cultivars THC content` or `endocannabinoid system regulation of
inflammation`), the output reads:

```
- Highest evidence grade across claims: **Unsupported**
- Claims: 0
- Claims with primary source: 0
```

… and nothing else. An industry expert cannot tell whether the question
is out-of-scope, the data is missing, or the registry just didn't match
their phrasing. This is a missed opportunity for the kind of honest
"here's why" surface the rest of the tool excels at.

**Why this priority**: §I says claims that cannot be anchored MUST be
graded Unsupported or refused — but the user-facing surface should
distinguish:

- **out-of-scope per Constitution §IV** (cultivation, lab-QC, retail) —
  refuse with a one-line "v0.x is researcher-only; the parent Cannavec
  plugin covers cultivar / QC / retail" message.
- **out-of-scope per "deliberately deferred" list** — point to the
  spec's "Out Of Scope" section.
- **in-scope but not yet curated** — emit a "this question is in scope
  but no curated registry row matched; consider the `discover`
  subcommand for live PubMed / ChEMBL search" hint.
- **in-scope but phrasing didn't match a detector** — emit the
  registry-name suggestions ("did you mean: CBD tacrolimus? CBD ×
  tacrolimus?").

**Independent Test**: For each test in the "0-claim battery"
(constructed at v0.3 plan time), the answer MUST include one of the
four classifications above, deterministically derived.

**Acceptance Scenarios**:

1. **Given** `compose_answer("Bedrocan THC content")`, **When** 0
   claims match and no registry detector fires, **Then** the answer
   MUST surface "in-scope but not yet curated; try `discover Bedrocan
   THC` for a live PubMed search."
2. **Given** `compose_answer("decarboxylation kinetics of THCA")`,
   **When** 0 claims match because the question is analytical
   chemistry, **Then** the answer MUST surface the "deferred-to-v0.4
   analytical-chemistry registry" classification.
3. **Given** `compose_answer("Indica vs sativa pharmacology")`, **When**
   the banned-pattern detector fires, **Then** the refusal MUST be
   the existing banned-pattern refusal (already correct in v0.2).

---

### User Story 10 — Rigor-report violation deduplication (Priority: P3)

`python3 -m cannavec_science rigor "myrcene potentiates Δ⁹-THC's
sedative effect via synergy"` returns the entourage-overclaim violation
**twice**, with identical text. The deduplication step in the rigor
walker is dropping a `seen` set check.

**Why this priority**: Cosmetic but reduces trust. An industry expert
reading the rigor report counts violations; two identical entries
inflate the count.

**Independent Test**: A unit test asserts that for any single-sentence
input, no `(detector, matched_phrase, span)` tuple appears twice in
the rigor report.

**Acceptance Scenarios**:

1. **Given** `rigor "myrcene potentiates Δ⁹-THC's sedative effect via
   synergy"`, **When** the entourage detector runs, **Then** exactly
   one violation is reported.
2. **Given** any rigor input, **When** the rigor walker emits its
   report, **Then** the violation list is deduplicated by
   `(detector, span)`.

---

### User Story 11 — Analytical-chemistry registry seed (Priority: P3, v0.4)

Industry-expert questions that fall outside v0.2 coverage:

- THCA → Δ⁹-THC decarboxylation kinetics (temperature, time,
  matrix-dependent rate constants).
- HPLC method validation for cannabinoid potency (USP <467> /
  ASTM standards / AOAC International methods).
- GC-MS vs HPLC for THCA/THC quantitation (the GC-induced decarb
  artefact is exactly the kind of THCA-vs-THC confusion the rigor
  detector catches at the prose level).
- Chemovar Type I / II / III / IV / V classification per Hazekamp
  & Fischedick 2012.
- Cannabis vapor pyrolysis byproducts (benzene, toluene, naphthalene)
  at different combustion vs vaporisation temperatures.

These are not "industry / regulatory" topics excluded by §IV; they
are **research-grade analytical chemistry** a working cannabis-science
PI would ask about. They sit inside the researcher audience lock.

**Why this priority**: P3 because the v0.4 horizon. The MVP made a
defensible choice to ship clinical-pharmacology depth first;
analytical-chemistry depth is the next natural extension under §IV.

**Independent Test**: A new `analytical_chemistry.py` module with at
least 8 registry rows, each citing primary literature (e.g. Veress
1990 PMID 2384545 for decarb kinetics, Hazekamp 2012 for chemovar
classification), each with positive + negative tests per §III.

**Acceptance Scenarios**:

1. **Given** `compose_answer("THCA decarboxylation kinetics at
   200°C")`, **When** the analytical-chemistry registry is in place,
   **Then** at least one Level C claim is emitted with the Veress
   1990 (or equivalent) primary citation.
2. **Given** `compose_answer("HPLC vs GC-MS cannabinoid quantitation")`,
   **When** the registry is in place, **Then** the GC-induced
   decarb-artefact warning is surfaced as a Level C claim.
3. **Given** `compose_answer("Type II chemovar")`, **When** the
   registry is in place, **Then** the Hazekamp & Fischedick 2012
   chemovar definition is surfaced.

---

### User Story 12 — Cultivation-science registry seed (Priority: P3, v0.4)

A cannabis-research PI in a horticultural-science department asks about:

- Light spectrum (UV-B effect on cannabinoid biosynthesis, blue:red
  ratios for THCA accumulation).
- Trichome density × cannabinoid yield × cultivar.
- CBDA-synthase vs THCA-synthase allelic dominance (the genetic
  basis of Type I / II / III chemotypes).
- Cannabis sativa L. botanical taxonomy — `sativa`/`indica`/
  `ruderalis` species debate (this is research-grade botany, distinct
  from the banned-pattern indica/sativa-as-pharmacology claim).

**Why this priority**: P3 because the v0.4 horizon. These topics are
research-grade plant science — they sit inside §IV (researcher
audience) but outside the MVP's clinical-pharmacology focus.

**Independent Test**: A new `cultivation_science.py` module with at
least 6 registry rows for plant-science topics, each with primary
citations. The botany taxonomy row MUST coexist with the existing
indica/sativa-as-pharmacology banned-pattern (different intents).

**Acceptance Scenarios**:

1. **Given** `compose_answer("UV-B effect on cannabinoid
   biosynthesis")`, **When** the cultivation-science registry is in
   place, **Then** at least one Level C claim is emitted (Lydon
   1987 PMID 3621052 or equivalent).
2. **Given** `compose_answer("THCA synthase CBDA synthase chemotype
   inheritance")`, **When** the registry is in place, **Then** the
   de Meijer 2003 (Genetics) primary citation is surfaced.
3. **Given** `compose_answer("Is Cannabis sativa one species or three?")`,
   **When** the registry is in place, **Then** the botanical-taxonomy
   row is surfaced as a Level C claim WITHOUT firing the indica/
   sativa-as-pharmacology banned-pattern (the prompt is botany,
   not pharmacology).

---

### Edge Cases

- **Δ⁸-THC + HHC + THCO + THCP four-way comparison**: the comparison
  detector must scale beyond two cannabinoids.
- **Hemp-derived intoxicating cannabinoids legal status**: US Story 12
  / 13 already specs that this stays in the parent plugin per
  Constitution "Out Of Scope" — `compose_answer` MUST refuse with
  that pointer, not return 0 claims silently.
- **CBN sleep — new published trial**: when a new high-quality CBN
  RCT is published (and PubMed-verified), the registry update MUST
  flow through the freshness probe; the v0.2 audit-pending note in
  the CBN monograph at `minor_cannabinoids.py` MUST be removed.
- **Citation-network pushback on a Cannavec-cited paper**: when the
  v0.2 citation-network field-pushback signal flips
  `inconsistency_serious=True` on Devinsky 2017, the
  evidence_summary.highest_grade for the Dravet golden flow MUST
  downgrade from Level B to Level C deterministically.
- **eCBome ↔ cannabinoid intersection**: PEA isn't a cannabinoid but
  shares the FAAH degradation pathway with anandamide; the eCBome
  detector and cannabinoid detector both firing on PEA-cannabinoid
  questions MUST not double-render.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `compose_answer` MUST resolve the prompt's named-cannabinoid
  set BEFORE firing the major-cannabinoid-monograph detector, and MUST
  treat Δ⁸-THC / HHC / THCO / THCP / THCA / CBDA / CBC / CBN / CBG /
  THCV / CBDV as single-named-isomer queries when they appear without
  a co-named Δ⁹-THC or CBD.
- **FR-002**: Adverse-event, interaction, contraindication, and
  population detectors MUST accept an optional `cannabinoid_filter`
  parameter; when set, only rows whose `cannabinoid` field intersects
  the filter are returned. `compose_answer` MUST set this filter to
  the prompt's named-cannabinoid set.
- **FR-003**: `EvidenceSummary.highest_grade` MUST be computed over
  *topically relevant* claims only. Topical relevance is a deterministic
  predicate based on (a) registry-row direct hit on the prompt's
  named-entity set and/or (b) topic-keyword match per
  `intent.topic_keywords`.
- **FR-004**: `_cmd_source_health` MUST use the actual `SourceHealth`
  dataclass fields (`status`, `latency_ms`, `error_excerpt`); the
  `.ok` / `.rtt_ms` / `.error` references are dead code and MUST be
  replaced.
- **FR-005**: `verify` MUST accept and resolve NCT, ChEMBL, and
  UniProt identifiers in addition to PMID and DOI. Each resolver
  follows the existing Tier-3 contract (stdlib `urllib`, injected-
  fetcher offline tests, positive + negative + network-error tests).
- **FR-006**: `detect_interaction_mention` (and the AE / contraindication
  / population variants) MUST expand the word "cannabis" / "marijuana" /
  "marihuana" / "weed" to the cannabinoid set {CBD, Δ⁹-THC, CBN, CBG,
  THCV} for the purposes of partner-drug matching.
- **FR-007**: `compose_answer` MUST import `cannavec_science.ecbome`
  and surface eCBome entries when the prompt names a mediator,
  receptor, enzyme, or transporter from that registry.
- **FR-008**: A new `registries` subcommand MUST list every covered
  cannabinoid, terpene, interaction-partner-drug, AE, contraindication,
  PGx allele, and eCBome entry — grouped by registry — with row
  counts and last-verified dates.
- **FR-009**: When `compose_answer` returns 0 claims, the output MUST
  classify the 0-claim case as one of: refusal (banned pattern /
  safety), out-of-scope per §IV, out-of-scope per "deliberately
  deferred", in-scope but not yet curated (with `discover` hint), or
  in-scope but phrasing-mismatched (with did-you-mean suggestion).
- **FR-010**: The rigor-report walker MUST deduplicate violations by
  `(detector, span)` before emitting the report.
- **FR-011** (v0.4): An `analytical_chemistry.py` registry module
  MUST ship with at least 8 rows covering decarb kinetics, HPLC/GC
  method validation, chemovar classification, and vapor pyrolysis
  byproducts. Each row carries a primary citation per §I.
- **FR-012** (v0.4): A `cultivation_science.py` registry module MUST
  ship with at least 6 rows covering light-spectrum effects, trichome
  biology, synthase genetics, and botanical taxonomy. Each row carries
  a primary citation per §I.

### Key Entities

- **NamedCannabinoidSet**: the deterministic set of cannabinoid isomers
  named in a prompt. Source: union of
  `detect_major_cannabinoid_mention` and
  `detect_minor_cannabinoid_mention` outputs, with the substring
  "THC" no longer triggering Δ⁹-THC when "Δ⁸-THC" / "Δ8-THC" /
  "delta-8-THC" is the actual match. Used by FR-001 and FR-002.
- **TopicalRelevancePredicate**: a deterministic function from
  `(claim, prompt) -> bool` that decides whether a claim is
  topically relevant to the prompt for the purposes of FR-003 grade
  aggregation. Composed of registry-row direct hit + topic-keyword
  match + entity overlap.
- **ZeroClaimClassification**: a discriminated union — `Refusal` /
  `OutOfScopeAudience` / `OutOfScopeDeferred` / `InScopeUncurated` /
  `InScopePhrasingMismatched` — emitted by FR-009.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (v0.3 acceptance): All four P1 user stories (US1, US2, US3,
  US4 (US-fixed-shape `source-health`), US5) ship with the test triples
  per Constitution §III. `python3 -m unittest discover -s tests` exits
  0 with **≥ 1,100** tests (≥ 36 new tests across the four stories).
- **SC-002** (v0.3 acceptance): `python3 -m cannavec_science answer
  "Δ⁸-THC pharmacology and safety"` returns the Δ⁸-THC monograph and
  does **NOT** emit the Δ⁹-THC monograph block; `python3 -m
  cannavec_science answer "HHC safety profile"` returns 0
  cannabinoid-attributed AE claims (HHC AE row count is 0) and the
  HHC monograph narrative.
- **SC-003** (v0.3 acceptance): `python3 -m cannavec_science answer
  "What is the evidence that the entourage effect is real?"` returns
  `highest_grade: Unsupported` (no spurious Level A from
  Lennox-Gastaut citations).
- **SC-004** (v0.3 acceptance): `python3 -m cannavec_science
  source-health` exits 0 (with green probe) or non-zero (with red
  probe) without raising AttributeError; structured output present.
- **SC-005** (v0.3 acceptance): `python3 -m cannavec_science verify
  NCT02224560` returns the trial record; `verify CHEMBL5803`
  returns the compound record; `verify P21554` returns the protein
  record. All offline-injected-fetcher-tested.
- **SC-006** (v0.3 acceptance): The eval suite gains a new
  **routing-and-surfacing** bucket with at least **15 prompts** —
  specifically named Δ⁸-THC / HHC / THCO / THCP / CBN / CBG queries,
  the entourage-effect grade-laundering test, the
  cannabis-tacrolimus expansion, and the 0-claim classification.
- **SC-007** (v0.3 acceptance): `python3 -m cannavec_science registries`
  emits a registry inventory in both markdown and `--format json`.
- **SC-008** (v0.4 acceptance): At least 8 analytical-chemistry rows
  AND at least 6 cultivation-science rows ship under §I / §II / §III
  gates. Total Python LOC under `cannavec_science/` stays under
  **30,000**.
- **SC-009** (v0.3 acceptance): The README's "What ships" section is
  updated to claim only what v0.3 actually delivers (no aspirational
  Δ⁸-THC routing claim until US1 lands).
- **SC-010** (v0.3 acceptance): The demo script at
  `docs/DEMO_SCRIPT.md` exercises every v0.3 user story so the demo
  proves the fixes shipped.

### Industry-Expert Trust Heuristics (qualitative, but checked at demo)

- **5-minute test**: a working cannabis-research PI can run the
  golden demo path AND the four v0.3 fixes within 5 minutes, and
  comes away saying "this is doing real work, not LLM theatre."
- **Pharmacovigilance test**: a clinical pharmacist asking
  `HHC adverse events` does NOT see 26 CBD/THC AEs incorrectly
  attributed to HHC.
- **Pharmacology test**: a medicinal chemist asking `Δ⁸-THC CB1
  binding` does NOT see the Δ⁹-THC monograph.
- **Honesty test**: a meta-analyst asking `entourage effect evidence`
  does NOT see "highest evidence grade: Level A."

## Assumptions

- v0.3 stays inside Constitution §IV (researcher only). No new audience.
- v0.4 (analytical chemistry + cultivation science registries) stays
  inside §IV — these are research-grade primary-literature topics, not
  retail / cultivator / lab-QC audience surfaces.
- v0.3 and v0.4 stay stdlib-only per §X.
- The existing 1,064 unit tests are regression-protected — none of
  them weaken under v0.3 changes. The 2-second total runtime is the
  ceiling.
- The eval suite's bucket-minimum enforcement is the floor — every new
  bucket carries a minimum that v0.3 lifts the eval total to ≥ 130
  prompts, v0.4 to ≥ 150.
- The five-slash-command lock per Constitution §IV holds. New
  subcommands (`registries`) are Python-module subcommands, not new
  slash commands.
- No new runtime dependencies. UniProt / NCT / ChEMBL resolvers use
  stdlib `urllib` per §X.
- The parent Cannavec plugin remains the canonical home for patient /
  clinician / cultivator / lab-QC / retail / hemp / microbiome /
  veterinary surfaces. The 0-claim classification in FR-009 points
  there for those audiences without absorbing them into Cannavec
  Science.

## Constitutional Impact

This spec is an in-constitution evolution. Per-principle impact:

- **§I (Primary-Source Or Refuse)**: deepened by US5 (verify accepts the
  five identifier shapes the constitution names) and US7 (eCBome
  entries each carry UniProt or HMDB IDs already; surfacing them
  honours §I).
- **§II (Deterministic-Backbone Over Prose)**: deepened by FR-003
  (topical-relevance predicate is a new deterministic enforcer),
  FR-006 (cannabis-noun → cannabinoid-set expansion is deterministic
  table lookup), FR-009 (0-claim classification is a deterministic
  discriminated union).
- **§III (Test-First)**: enforced — every user story carries the
  positive + negative + refusal test triples. v0.3 ships ≥ 36 new tests.
- **§IV (Researcher Audience Only)**: **unchanged**. Every user story
  stays researcher-only. The 0-claim classification's
  `OutOfScopeAudience` branch points at the parent plugin without
  importing audience surfaces.
- **§V (Safety-Layer Sovereignty)**: unchanged. K2 hard-refuse, banned
  patterns, and safety preflight remain load-bearing.
- **§VI (Phytochemistry Precision)**: deepened by US1 — the composer
  itself no longer collapses Δ⁸-THC into Δ⁹-THC.
- **§VII (GRADE Honesty)**: deepened by US3 / FR-003 — answer-level
  highest-grade aggregation respects topical relevance.
- **§VIII (Retractions At Composition)**: unchanged.
- **§IX (Live Discovery)**: deepened by US5 (verify lights up NCT,
  ChEMBL, UniProt) and US4 (source-health is the live-discovery
  layer's health dashboard).
- **§X (Stdlib-Only)**: unchanged.
- **§XI (Citable Output Is The Default)**: unchanged — bibliography
  export continues to work over the v0.3 typed Answer.

No amendment is required because every story stays inside the existing
principle texts. The v0.3 milestone is a tightening of the existing
contract, not a broadening.
