---
name: verify
description: Spot-check a single identifier — PMID, DOI, NCT, ChEMBL, or UniProt accession (the five Constitution §I shapes). Confirms it resolves upstream, returns metadata + retraction status, and emits PASS / FAIL / UNVERIFIED with rationale. Used when a reviewer wants to verify one citation without composing a whole brief.
argument-hint: '<PMID | DOI | NCT | ChEMBL | UniProt>'
allowed-tools: Bash
---

# Cannabis Science — Single-Citation Verification

The user wants to verify the identifier:

**`$ARGUMENTS`**

## How to dispatch

```bash
cd "${CLAUDE_PLUGIN_ROOT:-.}" && python3 -m cannavec_science verify "$ARGUMENTS"
```

The verifier:

1. Classifies the identifier into one of the five Constitution §I shapes:
   - **PMID** — digits (e.g. `28538134`)
   - **DOI** — `10.<registrant>/...` (contains `/` or starts with `10.`)
   - **NCT** — `NCT` + 8 digits (ClinicalTrials.gov)
   - **ChEMBL** — `CHEMBL` + digits
   - **UniProt** — accession (e.g. `P21554`, `Q8NER1`)
2. Queries the matching upstream with stdlib `urllib` — PubMed E-utilities
   (PMID), Crossref (DOI), ClinicalTrials.gov v2 (NCT), the ChEMBL REST API
   (ChEMBL), or UniProt (accession).
3. Returns the available metadata (author / year / journal / title /
   retraction status) and a verdict.
4. Cross-checks PMIDs/DOIs against the local retraction registry
   (`cannavec_science.retraction`).

## Verdicts and exit codes

The command is CI-gateable — it exits with a distinct code per verdict:

| Exit | Verdict | Meaning |
|------|---------|---------|
| `0` | **PASS** | Resolves upstream, no retraction / expression-of-concern. |
| `1` | **FAIL** | Identifier does not resolve, is retracted / flagged, or its metadata mismatches. |
| `2` | **error** | Not a recognized identifier shape — the error lists the five accepted shapes so the user can re-key. |
| `3` | **UNVERIFIED** | Could not confirm upstream (network error). Never PASS — §I requires a positive confirmation; an unconfirmed citation is not trustworthy. |

## Offline behaviour

Without network, the verifier still runs the local retraction-registry lookup but
cannot confirm upstream existence, so it reports **UNVERIFIED** with **exit code
3** (distinct from FAIL). A retracted identifier already in the local registry is
still caught offline and FAILs.
