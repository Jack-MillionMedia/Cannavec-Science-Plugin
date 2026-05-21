# Cannavec Science Constitution

Cannavec Science is a focused MVP: **research-grade cannabis science for the
working scientist.** It descends from the larger Cannavec plugin but
deliberately narrows scope so the surface stays demonstrable and the
deterministic backbone stays load-bearing.

This constitution governs every spec, plan, task, and implementation
under `specs/`. The MVP exists to be **trustworthy in five minutes** —
not to cover every audience, jurisdiction, or operational workflow.

## Core Principles

### I. Primary-Source Or Refuse

Every cannabis-science claim emitted by Cannavec Science MUST cite a
primary source — PMID, DOI, ChEMBL ID, NCT ID, or UniProt accession —
verifiable by the reader. Claims that cannot be anchored to a primary
source MUST be graded `Unsupported` or refused. Marketing copy,
secondary reviews citing reviews, and "common knowledge" without an
identifier are not evidence.

### II. Deterministic-Backbone Over Prose

User-facing surfaces (slash commands, skills, agent prompts) describe
behaviour; the Python backbone in `cannavec_science/` enforces it.
Every rule MUST be implemented in code with a unit test before any
prose surface mentions it. A skill that promises rigor without a
deterministic enforcer is marketing, not a feature.

### III. Test-First (NON-NEGOTIABLE)

Every change ships with regression tests in `tests/`. CI gates on
`python3 -m unittest discover -s tests` remaining green. New banned
patterns, new registry rows, new rigor detectors MUST ship with at
least one positive and one negative test case. Tests run offline —
network calls use injected fetcher fixtures.

### IV. Researcher Audience Only (MVP Scope Lock)

The MVP serves **one audience**: the cannabis-science researcher
(academic, clinical-trial, industry-research scientist). Patient,
clinician, cultivator, lab-QC, compliance, retail, hemp, microbiome,
veterinary, and policy surfaces are explicitly out-of-scope for v0.x
and MUST NOT be added without a constitutional amendment. The point
of the MVP is to do one thing exceptionally well — not many things
adequately.

### V. Safety-Layer Sovereignty

The safety preflight (`cannavec_science.safety`) and banned-pattern
detector (`cannavec_science.banned_patterns`) MUST run before any
registry composition or live-discovery fan-out. A registry hit
NEVER overrides a refuse verdict. Synthesis-route requests for
synthetic cannabinoids (K2/Spice) MUST hard-refuse regardless of
audience framing.

### VI. Phytochemistry Precision Is Non-Negotiable

Every cannabinoid MUST be named by isomer (Δ⁹-THC, Δ⁸-THC, THCA, CBD,
CBDA, CBG, CBGA, CBN, CBC, THCV, CBDV). Bare "THC" or "CBD" in a
pharmacology, dose, or assay context is a deterministic violation.
Every receptor MUST carry its UniProt accession (CB1 = P21554,
CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231, etc.). Every dose
claim MUST carry route + bioavailability. Every assay value MUST
carry a matrix tag (plasma / urine / flower / extract). THCA-vs-THC,
matrix-unit confusion, and decarb-context-missing are rejected
deterministically.

### VII. GRADE Honesty Over Confidence-Laundering

Evidence grades (Level A → E + Unsupported) are assigned by the
deterministic grader, not by prose adjectives. Single primary studies
cap at Level B (pre-registered powered RCT in major journal) or
Level C (observational). Level A requires a Cochrane/AHRQ/NICE
systematic review or ≥ 2 independent high-quality RCTs in alignment.
Verbs MUST match grade: Level C does not say "evidence shows."
The uncertainty wording-vs-grade consistency checker enforces this.

### VIII. Retractions Are Enforced At Composition, Not Post-Hoc

A retracted citation MUST NOT appear in a Cannavec Science answer
unless it is explicitly badged as retracted. The retraction registry
is consulted **inside `compose_answer()`** — not only at artifact-sign
time. Default policy for the researcher audience is `strict` (suppress
claims whose sole citation is retracted) with a visible
"N claims suppressed: retracted citation" header. A signed Cannavec
Science artifact citing a retracted PMID is a credibility catastrophe;
the constitution treats prevention as P0.

### IX. Read-Time Discovery Is As Important As Write-Time Checking

The MVP ships live discovery across three primary scientific sources:
**PubMed**, **ChEMBL**, and **ClinicalTrials.gov**. Live rows carry
per-source provenance tags (`live_pubmed`, `live_chembl`, `live_ctgov`)
and a deterministic cross-source synthesis verdict
(STRONG / MIXED / WEAK / NONE convergence). Live rows NEVER auto-promote
to the curated registry tier; that path requires a future manual
`apply` flow which is explicitly out-of-MVP-scope.

### X. Stdlib-Only Until Proven Insufficient

Cannavec Science's backbone is stdlib Python. New runtime dependencies
require a written justification in the relevant `plan.md` and an
explicit fallback path. Network calls MUST use `urllib` + injected
fetcher fixtures so the offline test suite still passes. The MVP runs
in any Python ≥ 3.9 environment with zero `pip install` steps.

### XI. Citable Output Is The Default

Every research brief MUST be exportable as a bibliography in BibTeX,
RIS, and CSL-JSON. A researcher using Cannavec Science MUST be able to
drop the answer's citations directly into Zotero / Mendeley / EndNote
without re-keying. GRADE level MUST be annotated inline at the
citation site, not only in a synthesis block.

## Honest Surface Constraints

- A slash command, agent file, or skill that promises orchestration
  MUST be backed by deterministic code OR carry an explicit honesty
  disclaimer in its frontmatter description.
- Live-discovery results MUST be visually distinct from curated rows
  (`live_*` provenance tag + provisional grade suffix). A demo that
  conflates the two is a constitution violation.
- The eval suite is the floor. Failure to add a regression test for a
  newly fixed bug is itself a regression.
- "Coming soon" is not a feature. Half-implemented surfaces are
  removed, not labelled "experimental."

## Development Workflow

1. Every non-trivial change starts as a feature spec in
   `specs/<NNN>-<short-name>/spec.md` driven by the spec-kit skills.
2. Specs MUST list prioritized user stories (P1, P2, ...) each
   independently testable so an MVP can ship from P1 alone.
3. Plans MUST identify which `cannavec_science/` primitives are
   touched, which curated registries gain rows, and how the change
   interacts with the safety + banned-pattern layer.
4. Tasks MUST be ordered by dependency. Test-writing tasks come before
   implementation tasks for the same module.
5. PRs MUST include a `tests/` diff or document why none was needed.

## Out Of Scope For v0.x

The following are deliberately deferred until after the MVP proves
client value:

- Multi-audience templates (patient, clinician, cultivator, lab,
  compliance, retail, policy, hemp, microbiome, veterinary)
- KB flywheel / gap detection / proposal generation
- Signed reproducible artifacts and verification
- Watchlist + daily digest
- Persistent expert profiles
- Multi-jurisdiction legal / regulatory surface
- Hemp-derived intoxicating-cannabinoid state law
- Industrial-hemp material-science framing
- Microbiome / endocannabinoidome surface
- CourtListener / legal-discovery integration
- Pesticides registry
- Per-state US compliance rows
- Oncology palliation-vs-cure framing as a standalone surface

These features may exist in the larger Cannavec plugin. They are
explicitly NOT promised by this MVP. Demo-time conflation between
the two products is a constitution violation.

## Governance

This constitution supersedes ad-hoc decisions in slash command files,
agent prompts, and skill descriptions. When a surface and the
constitution disagree, the constitution wins and the surface must be
brought into compliance via a spec.

Amendments live in `specs/<NNN>-constitution-amendment/` and require
the same spec → plan → tasks → implement workflow as a feature. An
amendment that broadens audience scope MUST surface the trade-off in
the spec's "Why this priority" section and document the new eval
surface area.

**Version**: 1.0.0 | **Ratified**: 2026-05-21 | **Last Amended**: 2026-05-21
