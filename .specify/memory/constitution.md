# Cannavec Science Constitution

## Mission (the north star — read this before anything else)

**Cannavec Science exists to ground AI models in credible, verifiable,
non-hallucinated research so experts can become dramatically more productive
without sacrificing accuracy, trust, or scientific rigor.**

The goal is to build the world's best AI-powered cannabis scientific research
tool — an expert-grade research *grounding* system that lets researchers,
clinicians, analysts, and domain experts do a significant amount of extremely
high-quality research **at scale**.

It is **not** a toy chatbot. It is **not** a static answer engine. It is **not**
a generic automation script. It is the credibility, retrieval, and verification
substrate that makes an AI reasoner (Claude, ChatGPT, or any frontier model)
trustworthy, useful, and scientifically disciplined when it works on cannabis
science.

Every improvement, feature, workflow, agent, schema, retrieval method,
evaluation, and engineering decision MUST be judged against this goal. This
constitution governs every spec, plan, task, and implementation under `specs/`.

## The Seven Mission Mandates (non-negotiable, governing layer)

These seven mandates sit **above** the operational principles (§I–§XI) and
decide what the project optimizes for. The operational principles are *how* we
honour the mandates; when a surface and a mandate disagree, the mandate wins and
the surface is brought into compliance via a spec.

**M1 — Research grounding over answer generation.** The project's job is to
connect an AI model to credible sources, structured evidence, and verifiable
research context so the model can *reason from trustworthy evidence*. The job is
**not** to emit canned answers. We optimize for the quality of the grounding —
retrieval, evidence structuring, transparent citation, claim-level traceability
— not for the cleverness of a static response builder. (Enforced by §I, §II, §IX.)

**M2 — Zero tolerance for hallucinated authority.** No output may ever present an
unsupported claim as fact. Any scientific, clinical, regulatory, safety, dosing,
interaction, or efficacy claim MUST be traceable to credible primary-source
evidence, or it is graded `Unsupported` / refused. A confident sentence with no
verifiable identifier behind it is a defect, not a feature. (Enforced by §I, §V,
§VI, §VII, §VIII; this is the operational meaning of *Primacy Of Evidence*.)

**M3 — Expert productivity is the target metric.** Success is measured by how
much faster a *domain expert* can review evidence, find gaps, compare sources,
and reach a higher-quality conclusion — at scale. We measure expert leverage and
grounding fidelity, not template coverage or answer-string completeness. The
product is built for experts doing serious research; widening *who* can read an
answer never lowers *what counts as evidence*. (Enforced by §IV.)

**M4 — Credibility must be engineered into the system.** Trust is not asserted in
prose; it is built from mechanisms: source-quality controls, citation
requirements, evidence grading, retrieval transparency, claim-level traceability,
uncertainty handling, retraction enforcement, and reproducible, offline-testable
workflows. Every component must *strengthen* one of these. (Enforced by §II, §III,
§V–§VIII, §X, §XI.)

**M5 — No brittle hard-coded intelligence.** Hard-coded answer logic, static
response templates, registry-only "answers" presented as the product, and
simplistic Python generators standing in for research reasoning are **anti-
patterns**, not architecture. Deterministic code exists to *retrieve, validate,
grade, verify, format, evaluate, and orchestrate* — it does **not** replace
research reasoning with canned output. (Enforced by §II.)

**M6 — Every change must pass the Mission Test.** Before adding or changing
anything, ask: *"Does this make the AI more grounded, more accurate, more
verifiable, more useful to experts, or more resistant to hallucination?"* If the
honest answer is no, it is not a priority and does not ship as if it were.
(Enforced by Governance → The Mission Test.)

**M7 — Build toward modern elite research infrastructure.** Cannavec Science is a
serious, extensible research platform, not a one-off script. We build toward
structured knowledge, high-quality retrieval (including semantic / vector
retrieval), rigorous evaluation, source-aware agents, audit trails, expert
feedback loops, and workflows that measurably improve over time. (Enforced by
§IX, §X, §XI.)

## Primacy Of Evidence (governing clause)

Credible primary-source science is the first-order commitment and it outranks
every other goal except the Mission that requires it. The capabilities added by
amendment — broad-audience *delivery* (§IV), the knowledge-base growth flywheel
(§IX), presentable/exportable rendering (§XI), and richer retrieval/reasoning
infrastructure (§X) — are **strictly subordinate** to the evidence-and-safety
principles: §I (Primary-Source Or Refuse), §V (Safety-Layer Sovereignty),
§VI (Phytochemistry Precision), §VII (GRADE Honesty), and §VIII (Retraction
Enforcement). When a reach-, growth-, presentation-, or convenience-goal
conflicts with any evidence-or-safety principle, the evidence principle wins and
the feature yields. Widening *who* receives an answer, *how* it is rendered, or
*what infrastructure* produces it never widens *what counts as evidence*. This is
the operational guarantee behind M2 and M4.

## Core Principles

### I. Primary-Source Or Refuse

Every cannabis-science claim surfaced through Cannavec Science MUST cite a
primary source — PMID, DOI, ChEMBL ID, NCT ID, or UniProt accession —
verifiable by the reader. Claims that cannot be anchored to a primary source
MUST be graded `Unsupported` or refused. This holds whether the claim was
retrieved from a curated registry, surfaced by live discovery, **or generated by
an AI model**: a model-authored sentence is held to exactly the same anchoring
standard as a hand-curated row, and is verified before it reaches the user.
Marketing copy, secondary reviews citing reviews, and "common knowledge" without
an identifier are not evidence. This is M2 made concrete.

### II. Deterministic Verification, Not Deterministic Intelligence

The Python backbone in `cannavec_science/` exists to **ground and verify AI
reasoning, not to replace it**. Its proper jobs are deterministic because
credibility cannot be probabilistic: retrieve primary-source evidence, verify
identifiers, enforce retractions, assign GRADE, run the phytochemistry/reporting
rigor and safety checks, export citations, and evaluate. The **reasoning** — the
synthesis, comparison, gap-finding, and the research brief itself — is the AI
model's job, performed over grounded, retrieved, verified evidence.

The division of labour is strict and non-negotiable:

- **The model proposes; the deterministic layer disposes.** Every *credibility*
  claim — a citation is real, a source is not retracted, a GRADE level, a safety
  verdict, a rigor violation — MUST be computed and enforced by code with a unit
  test, and MUST gate model output before it reaches the user. A model may *not*
  self-certify a citation, a grade, or a not-retracted status.
- **Promised rigor must be mechanically verifiable.** A slash command, agent, or
  skill that promises a credibility guarantee it cannot mechanically verify is
  marketing, not a feature.
- **Banned anti-patterns (M5).** Hard-coded answer logic, static response
  templates, registry-only output presented *as if it were the intelligence*,
  and simplistic Python generators substituting for research reasoning are
  prohibited as terminal surfaces. Curated registries are a **trusted grounding
  corpus** the model reasons over and the verifier checks — they are not a
  canned-answer source. `compose_answer()`-style composition is a *grounding and
  verification* primitive (it assembles verified evidence and produces a
  citation-lossless, machine-checkable artifact); it MUST NOT be treated as, or
  evolved into, a substitute for model reasoning. New work moves the project
  toward *model-reasoning-grounded-by-retrieval-and-verification*, never deeper
  into static generation.

### III. Test-First (NON-NEGOTIABLE)

Every change ships with regression tests in `tests/`. CI gates on
`python3 -m unittest discover -s tests` remaining green. New banned patterns, new
registry rows, new rigor detectors, new retrieval lanes, and new verification
rules MUST ship with at least one positive and one negative test case. Tests run
offline — network calls use injected fetcher fixtures. Reproducible,
offline-verifiable behaviour is part of how credibility is engineered (M4); an
unverifiable claim of correctness is itself a defect.

### IV. Research-Grade For Experts, At Scale

The target user and the success metric is the **expert** — the researcher,
clinician, analyst, or scientist using Cannavec to do high-quality research at
scale (M3). The product is optimized to make that expert dramatically more
productive: faster evidence review, sharper gap-finding, defensible
source-to-source comparison, and verifiable conclusions.

Cannavec may deliver research-grade science to **any** reader who uses it
(including non-specialist users of cannavec.ai), but the **evidence standard is
invariant**: every answer, for every audience, carries the same primary-source
anchoring (§I), GRADE honesty (§VII), phytochemistry precision (§VI), and
retraction enforcement (§VIII) a peer reviewer would demand. Audience may change
*presentation* (reading level, format, length); it MUST NOT change *evidence*,
and it MUST NOT shift the metric away from expert leverage and grounding fidelity.

Two hard limits keep this science-first:

1. **No individualized advice, ever.** Individualized medical, dosing,
   interaction, or legal advice is refused for every audience by the §V safety
   layer. Broadening the audience strengthens this gate; it never relaxes it.
   Cannavec answers "what does the evidence say," never "what should *you* take."
2. **No non-science operational surfaces.** Cultivation/IPM advice, lab-QC /
   certificate-of-analysis tooling, compliance / GMP / GACP workflows, retail
   product recommendations, dosing pamphlets, industrial-hemp material science,
   and jurisdiction-specific legal / policy operations remain out-of-scope — not
   because of *who* asks, but because they are not primary-source research
   science. They live in the parent Cannavec plugin.

The original "researcher-only" scope lock (v1.0.0 §IV) was superseded by the
"research-grade for every audience" amendment (v2.0.0); v3.0.0 re-centers the
*metric* on expert productivity without re-narrowing the audience. See
`specs/010-constitution-amendment/spec.md` for the v2.0.0 trade-off analysis.

### V. Safety-Layer Sovereignty

The safety preflight (`cannavec_science.safety`) and banned-pattern detector
(`cannavec_science.banned_patterns`) MUST run before any registry composition,
retrieval/grounding fan-out, or model-reasoning step. A registry hit, a retrieval
match, or a model proposal NEVER overrides a refuse verdict. Synthesis-route
requests for synthetic cannabinoids (K2/Spice) MUST hard-refuse regardless of
audience framing. Safety is computed deterministically and is sovereign over
every other layer, including the AI reasoner.

### VI. Phytochemistry Precision Is Non-Negotiable

Every cannabinoid MUST be named by isomer (Δ⁹-THC, Δ⁸-THC, THCA, CBD, CBDA, CBG,
CBGA, CBN, CBC, THCV, CBDV). Bare "THC" or "CBD" in a pharmacology, dose, or
assay context is a deterministic violation. Every receptor MUST carry its
UniProt accession (CB1 = P21554, CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231,
etc.). Every dose claim MUST carry route + bioavailability. Every assay value
MUST carry a matrix tag (plasma / urine / flower / extract). THCA-vs-THC,
matrix-unit confusion, and decarb-context-missing are rejected deterministically
— including when the offending text was produced by an AI model.

### VII. GRADE Honesty Over Confidence-Laundering

Evidence grades (Level A → E + Unsupported) are assigned by the deterministic
grader, not by prose adjectives and not by a model's self-assessment. Single
primary studies cap at Level B (pre-registered powered RCT in major journal) or
Level C (observational). Level A requires a Cochrane/AHRQ/NICE systematic review
or ≥ 2 independent high-quality RCTs in alignment. Verbs MUST match grade: Level
C does not say "evidence shows." The uncertainty wording-vs-grade consistency
checker enforces this on every surfaced claim, model-authored or curated.

### VIII. Retractions Are Enforced At Composition, Not Post-Hoc

A retracted citation MUST NOT appear in a Cannavec Science answer unless it is
explicitly badged as retracted. The retraction registry is consulted **inside
the composition/verification path** — not only at artifact-sign time. Default
policy for the researcher audience is `strict` (suppress claims whose sole
citation is retracted) with a visible "N claims suppressed: retracted citation"
header. A signed Cannavec Science artifact citing a retracted PMID is a
credibility catastrophe; the constitution treats prevention as P0.

This enforcement extends to the **live-discovery / grounding-retrieval tier**. A
retrieved or model-cited finding whose identifier matches the retraction registry
MUST be badged (⚠ retracted / expression-of-concern / under-correction) and
pinned last in the reranked breadth — never silently surfaced as citable, however
query-relevant it is. A plain correction (the paper stands) is neither badged nor
demoted. Curated claims follow the `strict` suppress-or-badge policy; the live
tier is *badged rather than suppressed* because it is already fenced as
provisional and the warning itself is useful (the paper exists but must not be
cited).

### IX. Read-Time Discovery & Grounding Retrieval Is As Important As Write-Time Checking

Retrieval **is** the product's grounding layer, and it is a first-class
investment equal to write-time verification (M1, M7). The product ships live
discovery and retrieval across its primary scientific sources (PubMed, ChEMBL,
ClinicalTrials.gov, Europe PMC, and the widened lane set in the plan addendum),
and may use semantic / vector retrieval to surface the most relevant evidence for
an expert's question. Retrieved rows carry per-source provenance tags
(`live_pubmed`, `live_chembl`, `live_ctgov`, …) and a deterministic cross-source
synthesis verdict (STRONG / MIXED / WEAK / NONE convergence). Retrieved rows
NEVER silently become curated facts at read time.

**The canonical delivery is one blended, grounded brief.** A single answer MAY
merge the verified curated **core** with citation-checked retrieved **breadth** as
the grounding an AI reasoner works over — the realistic path to "answer any
topic" at expert depth (§IV) — provided the two tiers stay visibly distinct:
curated claims keep their GRADE inline at each citation (§XI) under their own
heading; retrieved findings stay under a fenced, provenance-tagged, provisional
section, reranked for relevance and retraction-checked (§VIII); and the
cross-source synthesis verdict rides in the *same* brief rather than a separate
surface. The blend MUST be offline-testable per §X (the curated core grounds with
zero network; the retrieval weave uses injected fetchers in tests) and MUST NOT
raise or lower the curated GRADE — breadth augments the grounding, it never
re-grades it. This converts a thin-curated-tier into broad, credible grounding
without lowering the evidence bar (Primacy Of Evidence).

**Knowledge-base growth is human-approved (the flywheel).** Discovered rows MAY
be promoted into the curated knowledge base, but only through a deterministic,
auditable `apply` flow with a human curator as the last gate. A row is eligible
to promote ONLY when it clears the **same** admission gate as a hand-curated row:
a verifiable primary-source identifier (§I), a not-retracted status checked at
promotion time (§VIII), and a clean phytochemistry-rigor pass (§VI). The curator
must explicitly approve each promotion; every promotion records its provenance,
the approving curator, and a timestamp, and is reversible. **Fully-automatic
promotion (no human gate) remains out-of-scope** — the flywheel may stage and
rank candidates deterministically, but a human confirms before a candidate
becomes a curated fact. The knowledge base thus grows without ever lowering the
evidence bar, and the audit trail it produces is itself part of the credibility
engineering (M4, M7).

### X. Reproducible, Offline-Testable Verification Core; Right Tool For Retrieval

The **evidence, safety, grading, rigor, retraction, composition, and
verification core** MUST remain reproducible and offline-testable. It defaults to
stdlib Python so that `python3 -m cannavec_science` and
`python3 -m unittest discover -s tests` run with zero `pip install` steps, in any
Python ≥ 3.9 environment. Reproducibility is non-negotiable here because the
verification core *is* the credibility guarantee (M4): a check you cannot re-run
deterministically is not a check.

Beyond that core, M7 requires building modern research infrastructure, and the
constitution explicitly allows it: **retrieval, embeddings, semantic / vector
search, model orchestration, and presentable rendering use the right tool for the
job**, in their own clearly-separated layer, with a written justification in the
relevant `plan.md` and an explicit fallback path. Network calls in the core MUST
still use `urllib` + injected fetcher fixtures so the offline test suite passes;
infrastructure layers (e.g. a vector index, an embedding service, a PDF/slide
renderer, the website API) MUST degrade gracefully so the core remains runnable
and testable without them. Adding a dependency is a deliberate, justified,
reversible decision — never a casual one.

### XI. Citable, Presentable, Traceable Output Is The Default

Every research brief MUST be exportable as a bibliography in BibTeX, RIS, and
CSL-JSON. A user MUST be able to drop the answer's citations directly into Zotero
/ Mendeley / EndNote without re-keying. GRADE level MUST be annotated inline at
the citation site, not only in a synthesis block. Every claim MUST be traceable
to the source that grounds it — claim-level traceability is a hard requirement,
not a nicety (M2, M4).

Briefs MAY additionally be rendered into presentable formats of the user's choice
(PDF, slide deck, etc.). The **canonical artifact** is the structured Markdown
brief plus the typed `--json` `Answer`; any rendered format is a transform of
that artifact and MUST be **citation-lossless** — every primary-source identifier
and every inline GRADE annotation MUST survive into the rendered output. A
presentable format that drops, softens, or de-anchors a citation or a GRADE label
violates this principle and §VII. Rendering lives in the optional layer per §X.

## Honest Surface Constraints

- A slash command, agent file, or skill that promises orchestration or a
  credibility guarantee MUST be backed by deterministic code OR carry an explicit
  honesty disclaimer in its frontmatter description.
- Agents and skills **reason over** the grounded, retrieved, verified evidence —
  that is their value. But every *credibility* verdict (GRADE level, refusal,
  retraction status, citation validity, rigor violation) is computed by
  `cannavec_science/` and never invented in prose. Reasoning is the model's;
  certification is the code's.
- A surface that presents canned, registry-only output *as if it were research
  intelligence* violates §II / M5 and is removed, not relabelled.
- Live/retrieved results MUST be visually distinct from curated rows
  (`live_*` provenance tag + provisional grade suffix). A surface that conflates
  the two is a constitution violation.
- The eval suite is the floor. Failure to add a regression test for a newly fixed
  bug is itself a regression.
- "Coming soon" is not a feature. Half-implemented surfaces are removed, not
  labelled "experimental."

## Development Workflow

1. Every non-trivial change starts as a feature spec in
   `specs/<NNN>-<short-name>/spec.md` driven by the spec-kit skills, and states in
   its "Why this priority" section how it passes the **Mission Test** (M6).
2. Specs MUST list prioritized user stories (P1, P2, ...) each independently
   testable so an MVP can ship from P1 alone.
3. Plans MUST identify which `cannavec_science/` primitives are touched, which
   curated registries gain rows, which retrieval/grounding lanes change, and how
   the change interacts with the safety + banned-pattern + verification layer.
4. Tasks MUST be ordered by dependency. Test-writing tasks come before
   implementation tasks for the same module.
5. PRs MUST include a `tests/` diff or document why none was needed.

## Deliberately Out Of Scope

The following remain out-of-scope; they may exist in the larger Cannavec plugin
and are explicitly NOT promised by this build. Demo-time conflation between the
two products is a constitution violation.

- Individualized advice for any audience (refused by §V) and non-science
  operational surfaces (patient dosing pamphlets, clinician decision support,
  cultivator/agronomy, lab QC, compliance, retail, policy, hemp material science,
  veterinary) — these are not primary-source research science.
- *Fully-automatic* KB promotion, automatic gap detection, and automatic proposal
  generation with **no human gate**. Human-approved KB promotion — the §IX
  flywheel — IS in-scope.
- Per-state US regulatory-feasibility rows (any shipped advisory is US-federal /
  EU / Canada / UK only; per-state law lives in the parent plugin).
- Hemp-derived intoxicating-cannabinoid state law; industrial-hemp
  material-science framing.
- CourtListener / legal-discovery integration as a research surface.
- AlphaFold predicted structures (RCSB experimental only).
- Curator-agent *auto*-mutation of registry rows without a human gate.

## Governance

This constitution supersedes ad-hoc decisions in slash command files, agent
prompts, and skill descriptions. When a surface and the constitution disagree, the
constitution wins and the surface must be brought into compliance via a spec.

### The Mission Test (M6, applied to every change)

Before any feature, refactor, schema, retrieval method, agent, or engineering
decision is prioritized or merged, it MUST be able to answer **yes** to at least
one, and contradict **none**, of:

> Does this make the AI more grounded, more accurate, more verifiable, more useful
> to experts, or more resistant to hallucination?

A change that does not advance the mission is not a priority. A change that
*regresses* grounding, verifiability, expert leverage, or hallucination-resistance
— including any move toward static/hard-coded answer generation (M5) — is blocked,
the same way an evidence-or-safety regression is blocked.

### Amendments

Amendments live in `specs/<NNN>-constitution-amendment/` and require the same
spec → plan → tasks → implement workflow as a feature. An amendment that broadens
audience scope MUST surface the trade-off in the spec's "Why this priority"
section and document the new eval surface area. An amendment that touches the
Mission or the Seven Mandates MUST justify it against M6 and is presumed MAJOR.

**Version**: 3.0.0 | **Ratified**: 2026-05-21 | **Last Amended**: 2026-06-04

### Amendment log

- **v3.0.0 (2026-06-04)** — "Mission realignment: research grounding over answer
  generation" amendment. Adds the **Mission** preamble and the **Seven Mission
  Mandates (M1–M7)** as the governing layer, and adds the **Mission Test** to
  Governance. Reframes §II from "Deterministic-Backbone Over Prose" to
  **"Deterministic Verification, Not Deterministic Intelligence"** — the
  deterministic backbone is now defined as the *grounding + verification harness
  around an AI reasoner*, and hard-coded/static/canned answer generation
  (`compose_answer()`-as-intelligence, response templates, registry-only terminal
  output) is named an explicit anti-pattern (M5). Re-centers §IV's *metric* on
  expert productivity at scale without re-narrowing the v2.0.0 audience. Reframes
  §X to keep the verification core stdlib + offline-testable while explicitly
  permitting modern retrieval/embeddings/vector-search/model-orchestration
  infrastructure in a justified, gracefully-degrading layer (resolving a latent
  conflict with M7 and with the already-shipped semantic-retrieval work, spec
  027). Strengthens §I, §VI, §VII, §VIII so model-authored text is held to the
  same verification standard as curated rows, and updates the Honest Surface
  Constraints so agents may *reason* while code retains sole authority over
  credibility verdicts. **No evidence-or-safety principle was weakened** — Primacy
  Of Evidence is preserved and re-grounded in M2/M4. MAJOR bump: §II's
  reframing is backward-incompatible with any surface that treated static Python
  generation as the terminal intelligence; those surfaces are reconciled via the
  follow-up migration spec.

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
