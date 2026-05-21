---
name: discover
description: Live multi-source primary-literature discovery across PubMed + ChEMBL + ClinicalTrials.gov. Returns candidate rows with per-source provenance tags (live_pubmed, live_chembl, live_ctgov) and a deterministic cross-source synthesis verdict (STRONG / MIXED / WEAK / NONE convergence). Used when the curated registries are silent or the user needs literature post-snapshot.
argument-hint: '<query — e.g. "CBD PTSD", "Δ⁹-THC CYP2C9 inhibition", "nabiximols spasticity 2025">'
allowed-tools: Bash
---

# Cannabis Science Live Discovery

The user wants real-time literature discovery on:

**`$ARGUMENTS`**

## How to dispatch

```bash
python3 -m cannavec_science discover "$ARGUMENTS" --since 2024-01-01 --max 10
```

Optional flags:

- `--sources pubmed,chembl,ctgov` — restrict to a subset.
- `--since YYYY-MM-DD` — date floor for PubMed publication date.
- `--max N` — per-source row cap (default 10).
- `--json` — emit structured JSON for downstream tools.

The composer:

1. Runs the safety preflight + banned-pattern detector on the query.
   A refused query fires NO external network calls.
2. Fans out to PubMed (E-utilities), ChEMBL (REST), and
   ClinicalTrials.gov (API v2) with stdlib `urllib`.
3. Returns per-source rows tagged with `live_pubmed` / `live_chembl` /
   `live_ctgov` provenance.
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
