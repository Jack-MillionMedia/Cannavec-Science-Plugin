---
name: discover
description: Live multi-source primary-source discovery. Default lanes — PubMed + ChEMBL + ClinicalTrials.gov. Opt-in cannabis-primary widening adds PubChem (compound structures), PharmGKB (CYP2C9/CYP2C19/CYP3A4 pharmacogenomics), RCSB PDB (CB1/CB2 crystal structures), Open Targets (CNR1/CNR2 ↔ disease associations), GWAS Catalog (cannabis use disorder loci), and BindingDB (measured cannabinoid affinities). Every row carries a per-source provenance tag (`live_<source>`) and a deterministic cross-source synthesis verdict (STRONG / MIXED / WEAK / NONE convergence). Live rows never auto-promote to the curated registry tier (Constitution §IX).
argument-hint: '<query — e.g. "CBD PTSD", "Δ⁹-THC CYP2C9 inhibition", "nabiximols spasticity 2025">'
allowed-tools: Bash
---

# Cannabis Science Live Discovery

The user wants real-time literature discovery on:

**`$ARGUMENTS`**

## How to dispatch

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science discover "$ARGUMENTS" --since 2024-01-01 --max 10
```

Optional flags:

- `--sources` — comma-separated subset. Defaults to
  `pubmed,chembl,ctgov`. Cannabis-primary widening adds
  `pubchem`, `pharmgkb`, `rcsb`, `opentargets`, `gwas`, `bindingdb`.
- `--since YYYY-MM-DD` — date floor for PubMed publication date.
- `--max N` — per-source row cap (default 10).
- `--json` — emit structured JSON for downstream tools.

### Source-picking heuristic

For lane-by-lane routing — which primary source answers which kind of
cannabis-science question — load the `cannabis-primary-source-routing`
skill. It encodes the Constitution §I "Primary-Source-Or-Refuse" gate
into a per-question decision tree with the matching `--sources` flag.

The composer:

1. Runs the safety preflight + banned-pattern detector on the query.
   A refused query fires NO external network calls.
2. Fans out across the requested subset of: PubMed (E-utilities),
   ChEMBL (REST), ClinicalTrials.gov (API v2), PubChem (PUG REST),
   PharmGKB (REST), RCSB PDB (Search + data APIs), Open Targets
   (GraphQL), GWAS Catalog (REST v2), and BindingDB (REST). Every
   transport is stdlib `urllib`; tests inject fetcher fixtures.
3. Returns per-source rows tagged with the corresponding
   `live_<source>` provenance (`live_pubmed`, `live_chembl`,
   `live_ctgov`, `live_pubchem`, `live_pharmgkb`, `live_rcsb`,
   `live_opentargets`, `live_gwas`, `live_bindingdb`).
4. Emits a cross-source synthesis block with verdict
   (STRONG / MIXED / WEAK / NONE) and the first detected
   disagreement between sources, if any.

## Hard rules (Constitution §IX)

- Live rows are NEVER auto-promoted to the curated registry tier in
  v0.x.
- Live rows render with a provisional grade suffix
  (e.g., `Level B (provisional, live_pubmed)`).
- A refused query fires no external network call.
- If one source is unavailable, the other sources still surface their
  rows; the failing source surfaces a "live source unavailable" note.

## When to use this instead of /cannavec-science:research

- The user is looking for literature published after the curated
  registries' snapshot date.
- The query is novel and the curated registries return 0 claims.
- The user explicitly wants live primary literature (PubMed) plus
  the assay data (ChEMBL) plus the trial registry (ClinicalTrials.gov)
  in one pass.

For curated, GRADE-graded, retraction-enforced answers, use
`/cannavec-science:research` instead.
