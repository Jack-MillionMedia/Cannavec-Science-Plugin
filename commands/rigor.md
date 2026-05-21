---
name: rigor
description: Run the six phytochemistry rigor detectors plus the 15-pattern banned-pattern detector against arbitrary text. Returns structured violations with span + resolution hint per violation. Used when a researcher wants to audit a paragraph (their own draft, a reviewer comment, a marketing claim) without composing a whole brief.
argument-hint: '<text — paragraph or single sentence>'
allowed-tools: Bash
---

# Cannabis Science — Rigor Audit

The user wants to run the rigor + banned-pattern detectors on:

**`$ARGUMENTS`**

## How to dispatch

```bash
python3 -m cannavec_science rigor "$ARGUMENTS"
```

The audit runs six phytochemistry rigor detectors plus the
15-pattern banned-pattern detector:

| Detector | What it catches |
|---|---|
| `isomer_collapse` | Bare "THC" / "CBD" in pharmacology context |
| `receptor_without_id` | Receptor named without UniProt accession |
| `dose_without_route` | Dose value missing oral/inhaled/sublingual route |
| `thca_vs_thc_conflation` | "22% THC by HPLC" without THCA disambiguation |
| `matrix_unit_confusion` | ng/mL adjacent to cannabinoid without matrix tag |
| `decarb_context_missing` | THC/CBD pharmacology claim from raw-extract study |
| `banned_patterns` (15) | Indica/sativa-as-pharmacology, cultivar-as-effect, "cure" claims, "natural therefore safe", etc. |

Exit code: 0 if clean, 1 if any violation. Suitable for CI gating
on a researcher's own drafts.

## Hard rules

The detectors are deterministic regex / pattern matchers, not LLM-based.
They are conservative — false positives are preferred to false negatives
when a researcher's credibility is at stake. Each violation surfaces
the matched span and a resolution hint.

## Negation guard

Banned-pattern detection uses a 30-character negation window —
text like "indica does NOT cure cancer" does not fire the cure-claim
pattern. The negation guard prevents over-policing when the
researcher is quoting or rebutting someone else's framing.
