---
name: research
description: Compose a researcher-grade cannabis-science brief on a topic. Threads the deterministic backbone — banned-pattern detector, safety preflight, seven phytochemistry rigor checks (including the v0.2 entourage-overclaim detector), retraction enforcement, the eight curated science registries (major + minor cannabinoids including Δ⁸-THC/HHC/THCO/THCP, terpenes, drug interactions, adverse events, populations, contraindications, pharmacogenomics) with v0.2 freshness watch — into a typed Answer with GRADE-graded claims, inline primary-source citations, and an evidence-synthesis block. The v0.2 build adds opt-in researcher-workflow scaffolders (--pico, --power-calc, --grade-profile, --protocol-skeleton) and regulatory-feasibility advisory (--regulatory-feasibility). Researcher audience only.
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

### Output / format

- `--bibliography bibtex|ris|csljson` — emit the cited references in
  Zotero / Mendeley / EndNote-importable form (with `--out path` to
  write to a file).
- `--retraction-policy strict|badge` — `strict` (default) suppresses
  claims whose only citation is retracted; `badge` keeps them but
  annotates the retraction.
- `--json` — emit the typed `Answer` artifact for downstream tools.

### v0.2 researcher-workflow scaffolders (spec 002 US2)

- `--pico` — append a deterministic Population / Intervention /
  Comparator / Outcomes block derived from the intent classifier and
  populations registry. Confidence label (`high` / `medium` / `low`)
  surfaced.
- `--power-calc` — append per-outcome sample-size estimates
  (α = 0.05, β = 0.20) using stdlib-only Cohen's d (continuous) or
  Fleiss + Tytun-Ury continuity correction (proportion / OR).
  Reports `method_not_supported` when effect-size data are absent
  rather than guessing.
- `--grade-profile` — append a journal-grade evidence-profile table
  with per-outcome columns (#studies, design, risk of bias,
  inconsistency, indirectness, imprecision, publication bias, effect,
  certainty). Combine with `--grade-profile-format csv` for
  spreadsheet import.
- `--protocol-skeleton` — append a 9-section IRB protocol stub with
  an `Auto-generated skeleton — PI must review and supplement.`
  watermark on line 1. The intent classifier picks the recommended
  study design (RCT / crossover / cohort / mechanism); the PI fills
  in the per-protocol specifics.

### v0.2 regulatory-feasibility advisory (spec 002 US6)

- `--regulatory-feasibility {us|eu|ca|uk}` — append a per-jurisdiction
  advisory naming the controlled-substance schedule, licensing path,
  estimated timeline, and gray-zone notes for the cannabinoid in the
  prompt. **Always carries the `This is not legal advice; consult
  your institutional research-compliance office.` watermark.**
  Per-state US compliance is OUT OF SCOPE for v0.2.

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

This fans out across eleven primary sources — PubMed, ChEMBL,
ClinicalTrials.gov, PubChem, PharmGKB, RCSB PDB, Open Targets, GWAS
Catalog, BindingDB, and the v0.2 preprint lanes bioRxiv + medRxiv.
Per-source provenance tags and a cross-source synthesis verdict
(STRONG / MIXED / WEAK / NONE) are attached. Live rows are explicitly
marked `live_*` and NEVER auto-promote to the curated tier; preprint
rows carry a hard Level D cap regardless of grade hints (FR-202).

## What this brief cannot do

- Substitute for ethics-board consultation on a study design.
- Substitute for a statistician on sample-size / analysis planning.
- Be the trial protocol itself.
- Answer about cannabis legality, regulatory compliance, or
  jurisdiction-specific questions (out of MVP scope; see the larger
  Cannavec plugin for those audiences).
