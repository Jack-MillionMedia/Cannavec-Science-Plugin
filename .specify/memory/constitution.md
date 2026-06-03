# Cannavec Science Constitution

Cannavec Science is a focused MVP: **research-grade cannabis science for the
working scientist.** It descends from the larger Cannavec plugin but
deliberately narrows scope so the surface stays demonstrable and the
deterministic backbone stays load-bearing.

This constitution governs every spec, plan, task, and implementation
under `specs/`. The product exists to be **trustworthy in five minutes**
and to deliver research-grade cannabis science to everyone who uses
Cannavec — without ever lowering the evidence bar to do so.

## Primacy Of Evidence (governing clause)

Credible primary-source science is the first-order commitment and it
outranks every other goal. The capabilities added by amendment —
broad-audience delivery (§IV), the knowledge-base growth flywheel (§IX),
and presentable/exportable rendering (§XI) — are **strictly subordinate**
to the evidence-and-safety principles: §I (Primary-Source Or Refuse),
§V (Safety-Layer Sovereignty), §VI (Phytochemistry Precision),
§VII (GRADE Honesty), and §VIII (Retraction Enforcement). When a reach-,
growth-, or presentation-goal conflicts with any evidence-or-safety
principle, the evidence principle wins and the feature yields. Widening
*who* receives an answer, or *how* it is rendered, never widens *what
counts as evidence*.

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

### IV. Research-Grade For Every Audience

Cannavec delivers research-grade cannabis science to **any** reader who
uses it — including non-specialist users of cannavec.ai — but the
**evidence standard is invariant**: every answer, for every audience,
carries the same primary-source anchoring (§I), GRADE honesty (§VII),
phytochemistry precision (§VI), and retraction enforcement (§VIII) a peer
reviewer would demand. Audience may change *presentation* (reading level,
format, length); it MUST NOT change *evidence*.

Two hard limits keep this science-first:

1. **No individualized advice, ever.** Individualized medical, dosing,
   interaction, or legal advice is refused for every audience by the §V
   safety layer. Broadening the audience strengthens this gate; it never
   relaxes it. Cannavec answers "what does the evidence say," never "what
   should *you* take."
2. **No non-science operational surfaces.** Cultivation/IPM advice,
   lab-QC / certificate-of-analysis tooling, compliance / GMP / GACP
   workflows, retail product recommendations, dosing pamphlets,
   industrial-hemp material science, and jurisdiction-specific legal /
   policy operations remain out-of-scope — not because of *who* asks, but
   because they are not primary-source research science. They live in the
   parent Cannavec plugin.

The previous "researcher-only" scope lock (Constitution v1.0.0 §IV) is
superseded by this principle as of v2.0.0; see
`specs/010-constitution-amendment/spec.md` for the trade-off analysis and
the new eval surface.

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

This enforcement extends to the **live-discovery tier**. A live finding
whose identifier matches the retraction registry MUST be badged (⚠
retracted / expression-of-concern / under-correction) and pinned last in
the reranked live breadth — never silently surfaced as citable, however
query-relevant it is. A plain correction (the paper stands) is neither
badged nor demoted. Curated claims follow the `strict` suppress-or-badge
policy above; the live tier is *badged rather than suppressed* because it
is already fenced as provisional and the warning itself is useful (the
paper exists but must not be cited).

### IX. Read-Time Discovery Is As Important As Write-Time Checking

The product ships live discovery across its primary scientific sources
(PubMed, ChEMBL, ClinicalTrials.gov, and the widened set in the plan
addendum). Live rows carry per-source provenance tags (`live_pubmed`,
`live_chembl`, `live_ctgov`, …) and a deterministic cross-source
synthesis verdict (STRONG / MIXED / WEAK / NONE convergence). Live rows
NEVER silently become curated facts at read time.

**The canonical delivery is one blended brief, not two endpoints.** A
single answer MAY merge the verified curated **core** with citation-
checked live **breadth** in the same artifact — the realistic path to
"answer any topic" (§IV) — provided the two tiers stay visibly distinct:
curated claims keep their GRADE inline at each citation (§XI) under their
own heading; live findings stay under a fenced, provenance-tagged,
provisional section, reranked for relevance and retraction-checked (§VIII);
and the cross-source synthesis verdict rides in the *same* brief rather
than a separate surface. The blend MUST be opt-in and offline-testable per
§X (the curated core composes with zero network; the live weave uses
injected fetchers in tests) and MUST NOT raise or lower the curated GRADE —
breadth augments the core, it never re-grades it. This converts the thin-
curated-tier weakness into a strength without lowering the evidence bar
(Primacy Of Evidence).

**Knowledge-base growth is human-approved (the flywheel).** Discovered
rows MAY be promoted into the curated knowledge base, but only through a
deterministic, auditable `apply` flow with a human curator as the last
gate. A row is eligible to promote ONLY when it clears the **same**
admission gate as a hand-curated row: a verifiable primary-source
identifier (§I), a not-retracted status checked at promotion time (§VIII),
and a clean phytochemistry-rigor pass (§VI). The curator must explicitly
approve each promotion; every promotion records its provenance, the
approving curator, and a timestamp, and is reversible. **Fully-automatic
promotion (no human gate) remains out-of-scope** — the flywheel may stage
and rank candidates deterministically, but a human confirms before a
candidate becomes a curated fact. The knowledge base thus grows without
ever lowering the evidence bar (see Primacy Of Evidence).

### X. Stdlib-Only Until Proven Insufficient

Cannavec Science's backbone is stdlib Python. New runtime dependencies
require a written justification in the relevant `plan.md` and an
explicit fallback path. Network calls MUST use `urllib` + injected
fetcher fixtures so the offline test suite still passes. The MVP runs
in any Python ≥ 3.9 environment with zero `pip install` steps.

This applies to the **core**: the evidence, safety, registry, discovery,
composition, and bibliography backbone MUST remain stdlib-only and
offline-testable. Presentable-output rendering (§XI) that genuinely needs
a third-party engine (e.g. PDF or slide generation) MUST live in an
**optional** layer — an opt-in extra, or the website layer that consumes
the core's Markdown / JSON — so that `python3 -m cannavec_science` and
`python3 -m unittest discover -s tests` still run with zero installs.

### XI. Citable, Presentable Output Is The Default

Every research brief MUST be exportable as a bibliography in BibTeX,
RIS, and CSL-JSON. A user MUST be able to drop the answer's citations
directly into Zotero / Mendeley / EndNote without re-keying. GRADE level
MUST be annotated inline at the citation site, not only in a synthesis
block.

Briefs MAY additionally be rendered into presentable formats of the
user's choice (PDF, slide deck, etc.). The **canonical artifact** is the
structured Markdown brief plus the typed `--json` `Answer`; any rendered
format is a transform of that artifact and MUST be **citation-lossless** —
every primary-source identifier and every inline GRADE annotation in the
brief MUST survive into the rendered output. A presentable format that
drops, softens, or de-anchors a citation or a GRADE label violates this
principle and §VII. Rendering lives in the optional layer per §X.

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

## Out Of Scope For v0.2

The v0.2 elite-development build (spec 002) crossed the v0.x boundary
and promoted four items previously deferred: bioRxiv / medRxiv preprint
discovery (US1), the endocannabinoidome reference surface (US6), a
single-layer regulatory-feasibility advisory for US-federal / EU / Canada
/ UK (US6), and researcher-workflow scaffolders (PICO, power, GRADE
evidence-profile, IRB protocol skeleton) under US2. These now ship under
the same constitutional gates (§I primary-source, §II deterministic
backbone, §III test-first, §V safety, §VI phytochemistry precision, §VII
GRADE honesty, §IX live-discovery contract). Adding them did NOT broaden
the researcher-only audience scope-lock in §IV.

The following remain deliberately deferred past v0.2:

- Audience-tailored *presentation* of research-grade science is now
  in-scope (§IV, v2.0.0). What stays out: individualized advice for any
  audience (refused by §V) and non-science operational surfaces (patient
  dosing pamphlets, clinician decision support, cultivator/agronomy, lab
  QC, compliance, retail, policy, hemp material science, microbiome,
  veterinary) — these are not primary-source research science and live in
  the parent plugin.
- *Fully-automatic* KB promotion, automatic gap detection, and automatic
  proposal generation (no human gate). Human-approved KB promotion — the
  §IX v2.0.0 flywheel — IS now in-scope.
- Signed reproducible artifacts and verification
- Watchlist + daily digest
- Persistent expert profiles
- Per-state US regulatory-feasibility rows (the v0.2 advisory is
  US-federal only; per-state law lives in the parent plugin)
- Hemp-derived intoxicating-cannabinoid state law
- Industrial-hemp material-science framing
- Microbiome surface (the eCBome ships in v0.2 but the gut-microbiome
  / endocannabinoidome cross-talk surface does not)
- CourtListener / legal-discovery integration
- Pesticides registry
- Oncology palliation-vs-cure framing as a standalone surface
- AlphaFold predicted structures (RCSB experimental only)
- Curator-agent *auto*-mutation of registry rows without a human gate
  (the human-approved §IX apply flow is in-scope; agent self-mutation
  without a curator approving is not)

These features may exist in the larger Cannavec plugin. They are
explicitly NOT promised by this elite-tier build. Demo-time conflation
between the two products is a constitution violation.

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

**Version**: 2.1.0 | **Ratified**: 2026-05-21 | **Last Amended**: 2026-06-03

### Amendment log

- **v2.1.0 (2026-06-03)** — "One blended brief" amendment, ratified via
  `specs/028-blended-answer/`. Additive and non-weakening: deepens §VIII
  (retraction enforcement now extends to the live-discovery tier — a
  retracted / EOC / under-correction live finding is badged and pinned last,
  never silently surfaced) and §IX (names the curated-core + live-breadth
  *single blended brief* as the canonical delivery, with three invariants:
  provenance visibly distinct, GRADE inline at each curated citation, and the
  cross-source synthesis verdict in the same brief). No evidence-or-safety
  principle was weakened — §X is explicitly preserved (the blend is opt-in and
  offline-testable; the curated core composes with zero network) and the live
  tier still never raises the curated GRADE or auto-promotes (§IX). MINOR bump:
  both changes strengthen existing principles without breaking any surface.

- **v2.0.0 (2026-06-01)** — "Research-grade for every audience" amendment,
  ratified via `specs/010-constitution-amendment/`. Adds the **Primacy Of
  Evidence** governing clause; redefines §IV (researcher-only →
  research-grade-for-all, evidence standard invariant, individualized
  advice still refused by §V); extends §IX with the human-approved
  KB-growth flywheel (deterministic + auditable promotion behind a curator
  gate); extends §X (core stays stdlib; rendering is an optional layer);
  and extends §XI to citation-lossless presentable output (PDF / slides).
  No evidence-or-safety principle was weakened — all three new capabilities
  are subordinate to §I / §V / §VI / §VII / §VIII by the Primacy clause.
  MAJOR bump: §IV's scope redefinition is backward-incompatible with
  surfaces that relied on the researcher-only lock; those surfaces are
  reconciled via spec 010's task list.

- **v1.0.0 (2026-05-21)** — Initial ratification. Codebase boundary
  v0.x → v0.2 crossed via spec 002 (elite development) without an
  amendment, using the v0.x qualifier mechanism the constitution defines
  for moving items off the "Out Of Scope" list. The principle texts that
  deepened under v0.2 (§I, §VI, §VII, §VIII, §IX, §XI) kept their
  numbering and ordering.
