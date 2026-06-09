---
name: research
description: Produce a grounded, citation-verified cannabis-science research brief. You (the model) do the reasoning; the deterministic backbone grounds and verifies it — live primary-source retrieval (PubMed + ClinicalTrials.gov + ChEMBL), identifier verification, retraction enforcement, GRADE grading, and phytochemistry rigor. Every claim you write must carry a primary-source identifier that the backbone has confirmed is real and not retracted, or it is graded Unsupported. This is grounding, not canned-answer generation (Constitution M1/§II).
argument-hint: '<research question — e.g. "CBD evidence in Dravet syndrome", "CB1 partial agonism of Δ⁹-THC", "CYP3A4 interaction with cannabidiol">'
allowed-tools: Bash
---

# Cannabis-Science Research Brief — grounded & verified

You are answering a cannabis-science research question for an expert
(researcher, clinician, pharmacologist, analyst). **You do the reasoning.**
The deterministic backbone's only job is to *ground and verify* what you write —
it retrieves primary sources, confirms every identifier is real and not
retracted, grades the evidence, and flags unscientific language. Your brief is
trustworthy because every credibility claim in it was computed by code, not
asserted by you.

The user asked:

**`$ARGUMENTS`**

## The grounded workflow — run these, then reason over the results

### 1. Rigor + safety preflight on the question

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science rigor "$ARGUMENTS"
```

If this returns a **safety refusal** (e.g. a synthesis-route or individualized-
dosing request), stop and surface the refusal — do not work around it. Otherwise
note any phytochemistry/banned-pattern flags so you don't repeat them.

### 2. Retrieve primary sources — live

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science discover "$ARGUMENTS" --sources pubmed,ctgov,chembl --max 8
```

This fans out live to PubMed, ClinicalTrials.gov, and ChEMBL and returns ranked,
real, current candidates (PMIDs / NCT IDs / ChEMBL IDs) with a cross-source
synthesis verdict (STRONG / MIXED / WEAK). These are **discovery candidates, not
facts** — you must verify each before citing it. If discovery is unavailable
(no network / no `NCBI_API_KEY`), say so and proceed with the curated reference
in step 4, still subject to verification.

The PubMed lane auto-distills interrogative scaffolding (e.g. "What is the … ?")
to content terms before searching, so a typed question maps cleanly. It does
**not** translate vocabulary: if a query returns 0 rows, re-run with the
*scientific* terms for any lay concept (e.g. "red eyes" → "conjunctival
hyperemia", "munchies" → "appetite stimulation / hyperphagia") — that lexical
reasoning is yours to do.

### 3. Verify every identifier you intend to cite

For each PMID / DOI / NCT / ChEMBL / UniProt accession you plan to use:

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science verify <identifier>
```

A **PASS** means the identifier resolves to a real, non-retracted source (with
author / year / journal / title read live from the source). A **FAIL** means it
is fabricated, not found, or **retracted** — never cite a FAIL. This is the
anti-hallucination gate: you may only cite identifiers the backbone confirmed.

### 4. (Optional) Pull curated reference context — clearly labelled, never the answer

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science answer "$ARGUMENTS" --json
```

Treat the curated registry content (monographs, receptor pharmacology, PK,
safety) as **offline background reference the backbone has graded** — useful
scaffolding to reason over, **not** the answer itself, and **not** a substitute
for the live-verified evidence from steps 2–3. Any identifier it surfaces still
goes through step 3 before you cite it.

### 5. Synthesize the brief — your reasoning, over verified evidence

Write a concise expert brief that:

- Leads with a **GRADE-honest bottom line** (Level A–E / Unsupported), worded to
  match the grade — a single RCT is Level B, not "evidence shows."
- Makes **every scientific claim carry a verified primary-source identifier**
  (step 3 PASS). A sentence with no verified identifier is graded **Unsupported**
  or omitted (§I, M2).
- Names every cannabinoid by **isomer** (Δ⁹-THC, Δ⁸-THC, THCA, CBD, CBDA, CBG,
  CBN, CBC, THCV, CBDV) and every receptor by **UniProt accession** (CB1 P21554,
  CB2 P34972, TRPV1 Q8NER1, PPARγ P37231); every dose carries route +
  bioavailability (§VI).
- Surfaces **uncertainty and gaps** honestly — what the evidence does *not* show,
  where it is thin, what would change the conclusion.
- Distinguishes the **live-verified** evidence (steps 2–3) from any **curated
  reference** (step 4) so the reader always knows what was freshly verified.

## Hard rules (Constitution §I, §II, §V, §VI, §VII, §VIII)

- **Primary-source-or-refuse.** No claim without a verified identifier. The model
  is held to the same evidence bar as a curated row.
- **You may not self-certify.** A citation being real, not-retracted, and its
  GRADE level are computed by the backbone (steps 2–3), never asserted by you.
- **Retracted = never cited.** If `verify` FAILs on retraction, drop the claim.
- **No individualized advice.** Answer "what does the evidence say," never "what
  should you take." Safety refusals from step 1 are sovereign.

## What this brief is not

- It is **not** a canned answer. The curated registry is reference scaffolding
  you reason over; it is never presented as the intelligence (M5).
- It does **not** give legal, regulatory, dosing, or individualized clinical
  advice — out of scope.
