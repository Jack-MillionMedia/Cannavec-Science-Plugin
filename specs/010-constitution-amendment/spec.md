# Constitution Amendment: Research-Grade For Every Audience (v2.0.0)

**Feature Branch**: `claude/compassionate-ptolemy-ehj2x`

**Created**: 2026-06-01

**Status**: Ratified — constitution amended in this branch; surface +
code reconciliation tracked as the task list below.

**Input**: User request — "focus on the research quality. Amend the
constitution for this new vision but keep credible science research
first." The "new vision" (from the prior turn) is the cannavec.ai
credible-research feature: find research beyond the existing RAG
knowledge base, deliver it to **the user of cannavec** in a presentable,
exportable format of their choice (PDF, slideshow, …), and run a
**flywheel** that grows/improves the knowledge base over time.

## Why amend (and why now)

Three pieces of the vision were forbidden or deferred by Constitution
v1.0.0:

1. **Audience.** §IV locked the audience to researchers only; "the user
   of cannavec" is broader.
2. **Flywheel.** §IX said live rows "NEVER auto-promote … requires a
   future manual `apply` flow which is explicitly out-of-MVP-scope," and
   the out-of-scope list banned "KB flywheel / gap detection / proposal
   generation" and "curator-agent auto-mutation."
3. **Presentable output.** §XI mandated only BibTeX/RIS/CSL-JSON; §X is
   stdlib-only, and PDF/slide rendering needs a renderer.

The Constitution's own Governance clause is the mechanism for changing
this: amendments live here and "an amendment that broadens audience scope
MUST surface the trade-off … and document the new eval surface area."
This spec does both.

## The first-order constraint: credible science stays first

The amendment adds a new governing clause, **Primacy Of Evidence**, placed
above the Core Principles. It states that broad-audience delivery (§IV),
the KB-growth flywheel (§IX), and presentable rendering (§XI) are *strictly
subordinate* to the evidence-and-safety principles (§I, §V, §VI, §VII,
§VIII). When a reach/growth/presentation goal conflicts with an
evidence-or-safety principle, evidence wins and the feature yields. This is
the literal encoding of "keep credible science research first": the three
new capabilities can only widen *who* gets an answer and *how* it is
rendered — never *what counts as evidence*.

## What changed in the constitution

| Section | v1.0.0 | v2.0.0 |
|---|---|---|
| **Primacy Of Evidence** (new) | — | New governing clause; evidence/safety outrank reach/growth/presentation. |
| **§IV** | "Researcher Audience Only (MVP Scope Lock)" | "Research-Grade For Every Audience." Evidence standard invariant across audiences; audience changes presentation, not evidence. Two hard limits: no individualized advice (refused by §V for everyone), no non-science operational surfaces. |
| **§IX** | Live rows never promote; apply flow out-of-scope | Human-approved KB-growth flywheel: rows promote only via a deterministic, auditable `apply` flow behind a curator gate, after clearing the same primary-source (§I) + retraction-at-promotion (§VIII) + rigor (§VI) gate as a hand-curated row. Fully-automatic promotion stays out. |
| **§X** | Stdlib-only | Unchanged for the **core**; presentable rendering that needs a third-party engine must live in an **optional** layer so the CLI + tests still run with zero installs. |
| **§XI** | "Citable Output Is The Default" | "Citable, **Presentable** Output." PDF/slides allowed as **citation-lossless** transforms of the canonical Markdown + `--json` artifact — every identifier + GRADE label must survive rendering. |
| **Out Of Scope** | Multi-audience, KB flywheel, auto-mutation listed | Reframed: audience-tailored *presentation* in-scope; human-approved promotion in-scope; fully-automatic promotion + agent self-mutation + non-science surfaces stay out. |
| **Version** | 1.0.0 | 2.0.0 (MAJOR — §IV redefinition is backward-incompatible) + amendment log. |

## Audience trade-off *(required by Governance for audience-broadening)*

**The win:** cannavec.ai can put research-grade answers in front of every
visitor, not just academics — which is the whole point of the feature.

**The risk it could have introduced:** "serving a broader audience" is the
classic on-ramp to lowering the evidence bar (simplify → soften the grade →
drop the citation) or to drifting into individualized medical advice.

**Why this amendment does not pay that price:**

- The evidence bar is held *invariant* in the §IV text and enforced by the
  unchanged deterministic backbone (`evidence.py` GRADE, `rigor_checks.py`,
  `banned_patterns.py`, retraction enforcement in `compose_answer`).
  Broadening §IV changed prose, not a single grading rule.
- Individualized advice was *already* refused independently of audience by
  `safety.py` (`REFUSE_INDIVIDUALIZED`, `is_individualized_medical_question`).
  A broader audience makes that gate *more* load-bearing, not less; the
  amendment explicitly strengthens, never relaxes, it (§IV limit 1 + §V).
- Non-science operational surfaces (cultivation, lab-QC, compliance,
  retail, dosing pamphlets, jurisdictional law) stay out — the boundary
  moved from *who asks* to *what is research science*, which is the
  science-first framing.

**Alternative considered and rejected:** "Full multi-audience" (tailored
patient/clinician decision-support surfaces). Rejected for this amendment
because it materially expands the §V safety surface and would need its own
safety spec; it is not required to deliver research-grade answers to a
general reader.

## New eval surface area *(required by Governance)*

The eval/test suite must grow to defend the amendment's invariants. These
are specified here and land with the implementation tasks (T2–T4), not as
prose-only promises:

1. **Audience-invariance** — a lay-framed question (e.g. "in simple terms,
   does CBD help anxiety?") returns the *same* GRADE-graded, primary-source
   citations as the expert framing; no grade is softened and no citation is
   dropped when presentation is simplified.
2. **Individualized-advice refusal across framings** — "should *I* take CBD
   for *my* anxiety?" and other second-person/imperative framings still
   refuse for every audience (extends existing `tests/test_safety*.py`).
3. **Flywheel admission gate** — a candidate row that lacks a primary
   identifier, is retracted at promotion time, or fails rigor is NOT
   promotable; a clean row is *stageable* but requires recorded human
   approval before it becomes curated; every promotion is reversible and
   carries provenance + curator + timestamp.
4. **Presentation citation-losslessness** — a rendered artifact contains
   every PMID/DOI and every inline GRADE label present in the source brief
   (no citation or grade is dropped or softened by rendering).

## Reconciliation tasks

- **T1 — Constitution + directly-owned surfaces (done in this branch).**
  Amend `.specify/memory/constitution.md` (v2.0.0); reconcile
  `agents/cannabis-research-lead.md` and the `README.md` §IV / "What does
  NOT ship" framing so no live surface contradicts the amended §IV/§IX/§XI.
- **T2 — Audience-presentation layer (follow-up, code + tests).** A
  presentation control on `answer` (reading level / length / format) that
  changes *only* presentation, with eval #1 + #2 proving evidence- and
  refusal-invariance. Constitution §II/§III: deterministic + test-first.
- **T3 — Human-approved KB `apply` flow (follow-up, code + tests).** A
  staging store + the deterministic admission gate (§I identifier, §VIII
  retraction-at-promotion, §VI rigor) + a curator-approval record
  (provenance + curator + timestamp) + reversibility, with eval #3.
- **T4 — Presentable renderer (follow-up, optional layer).** A
  PDF/slide renderer that consumes the Markdown + `--json` artifact,
  citation-lossless (eval #4), shipped as an opt-in extra or in the
  website layer so the core stays stdlib-only (§X).
- **T5 — Remaining prose surfaces (follow-up).** Reconcile
  `commands/*.md` and the `plugin.json` description to the research-grade-
  for-all framing as they are next touched.

## Out of scope (what this amendment deliberately does NOT do)

- Does NOT weaken any evidence-or-safety principle (§I, §V, §VI, §VII,
  §VIII unchanged; the Primacy clause makes them supreme).
- Does NOT add individualized medical/dosing/legal advice for any audience.
- Does NOT add non-science operational surfaces (still parent-plugin).
- Does NOT permit fully-automatic KB promotion (human curator is the last
  gate).
- Does NOT add a runtime dependency to the core (rendering is optional).
- Does NOT implement T2–T4 here — this spec ratifies the principles and
  reconciles the prose; the code lands under its own test-first tasks.

## Acceptance Gate

- `python3 -m unittest discover -s tests` exits 0 (no code changed; the
  amendment is prose + surface reconciliation).
- The constitution declares **Version 2.0.0** with an amendment log and a
  **Primacy Of Evidence** clause; §IV, §IX, §X, §XI carry the amended text.
- No live surface (agent files, README) contradicts the amended §IV/§IX/§XI.
- The slash-command count is exactly five (Constitution §IV unchanged on
  this axis — no surface expansion in this amendment).
- `pyproject.toml` `dependencies = []` unchanged (core stays stdlib; §X).
