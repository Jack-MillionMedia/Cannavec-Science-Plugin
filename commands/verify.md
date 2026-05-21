---
name: verify
description: Spot-check a single PMID or DOI. Confirms the identifier resolves upstream (PubMed E-utilities for PMIDs, Crossref for DOIs), returns first author + year + journal + retraction status, and emits PASS / FAIL with rationale. Used when a reviewer wants to verify a single citation without composing a whole brief.
argument-hint: '<PMID | DOI>'
allowed-tools: Bash
---

# Cannabis Science — Single-Citation Verification

The user wants to verify the identifier:

**`$ARGUMENTS`**

## How to dispatch

```bash
python3 -m cannavec_science verify "$ARGUMENTS"
```

The verifier:

1. Detects whether the identifier is a PMID (digits) or a DOI
   (contains `/` or starts with `10.`).
2. Queries PubMed E-utilities (for PMIDs) or Crossref (for DOIs)
   with stdlib `urllib`.
3. Returns first author / year / journal / title /
   retraction status / verdict.
4. Cross-checks against the local retraction registry
   (`cannavec_science.retraction`).
5. Exits non-zero on FAIL so the command is CI-gateable.

## What constitutes FAIL

- Identifier does not resolve upstream.
- Identifier is in the local retraction registry.
- PubMed's `pubtypes` field includes "Retracted Publication."

## What constitutes PARTIAL

(Future v0.2 — outside MVP scope.) An expression-of-concern record is
distinct from a retraction; the MVP folds both into FAIL for safety.

## What constitutes PASS

- Identifier resolves upstream.
- No retraction or expression-of-concern detected.
- First author / year / journal returned.

## Offline behaviour

Without network, the verifier surfaces the local retraction-registry
lookup but cannot confirm upstream existence. The result is reported as
`NETWORK_UNAVAILABLE` with exit code 2 (distinct from FAIL).
