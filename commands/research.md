---
name: research
description: Compose a researcher-grade cannabis-science brief on a topic. Threads the deterministic backbone — banned-pattern detector, safety preflight, six phytochemistry rigor checks, retraction enforcement, the eight curated science registries (major + minor cannabinoids, terpenes, drug interactions, adverse events, populations, contraindications, pharmacogenomics) — into a typed Answer with GRADE-graded claims, inline primary-source citations, and an evidence-synthesis block. Researcher audience only.
argument-hint: '<research question or topic — e.g. "CBD evidence in Dravet syndrome", "CB1 partial agonism of Δ⁹-THC", "CYP3A4 substrate interaction with cannabidiol">'
allowed-tools: Bash, Read
---

# Cannabis Science Research Brief

You are answering a cannabis-science research question for an academic,
clinical-trial, or industry-research scientist. The user asked:

**`$ARGUMENTS`**

## How to dispatch

Run the deterministic composer and surface the structured output:

```bash
python3 -m cannavec_science answer "$ARGUMENTS"
```

The composer returns:

1. **Refusal block** if the prompt triggers safety preflight or banned-pattern
   detection. Do NOT attempt to circumvent the refusal — restate the question
   in evidence-graded terms and re-run.
2. **Evidence summary** — highest GRADE, claim count, retraction-suppressed
   count.
3. **Claims** — typed, GRADE-graded, with inline PMID/DOI citations and the
   level annotated at the citation site.
4. **Monograph sections** — when a major or minor cannabinoid is named, the
   curated per-compound monograph attaches.
5. **Cautions** — safety-layer cautions per claim type.
6. **Citations** — bibliography-ready list with GRADE per entry.
7. **Rigor violations** — flagged spans the composer detected in the prompt
   itself (bare "THC" in pharmacology context, dose without route, etc.).

## Optional flags

- `--bibliography bibtex|ris|csljson` — emit the cited references in
  Zotero / Mendeley / EndNote-importable form (with `--out path` to
  write to a file).
- `--retraction-policy strict|badge` — `strict` (default) suppresses
  claims whose only citation is retracted; `badge` keeps them but
  annotates the retraction.
- `--json` — emit the typed `Answer` artifact for downstream tools.

## Hard rules (Constitution §I, §V, §VI, §VII, §VIII, §XI)

- Every claim cites a primary source (PMID, DOI, NCT, ChEMBL ID, or
  UniProt accession). Claims without primary sources are graded
  `Unsupported` or refused.
- GRADE wording matches the assigned grade — Level C does not say
  "evidence shows."
- Every cannabinoid is named by isomer (Δ⁹-THC, Δ⁸-THC, THCA, CBD,
  CBDA, CBG, CBGA, CBN, CBC, THCV, CBDV). Bare "THC" / "CBD" in
  pharmacology context is rejected.
- Every receptor carries its UniProt accession (CB1 = P21554,
  CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231).
- Every dose carries route + bioavailability.
- THCA-vs-THC, matrix-unit confusion, decarb-context-missing are
  rejected deterministically.
- Retracted citations are suppressed at composition time.
- The output is exportable to BibTeX / RIS / CSL-JSON.

## When live discovery is needed

If the curated registries do not cover the topic, or the user is
asking about literature post-snapshot, run:

```bash
python3 -m cannavec_science discover "$ARGUMENTS"
```

This fans out across PubMed, ChEMBL, and ClinicalTrials.gov live with
per-source provenance tags and a cross-source synthesis verdict.
Live rows are explicitly marked `live_*` and NEVER auto-promote to the
curated tier.

## What this brief cannot do

- Substitute for ethics-board consultation on a study design.
- Substitute for a statistician on sample-size / analysis planning.
- Be the trial protocol itself.
- Answer about cannabis legality, regulatory compliance, or
  jurisdiction-specific questions (out of MVP scope; see the larger
  Cannavec plugin for those audiences).
