# Spec 016 — GRADE certainty rating for the meta pool (completes the SoF table)

**Status**: Implemented

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §X.

## Why this priority

Spec 015 gave `meta --baseline-risk` the *relative effect → absolute effect →
NNT* columns of a GRADE Summary-of-Findings (SoF) table. A SoF table has one
more column, and it is the one reviewers read first: **the certainty of the
evidence** (⊕⊕⊕⊕ High → ⊕⊝⊝⊝ Very Low). Without it the table reports an
effect without telling the reader how much to trust it — which is exactly the
confidence-laundering §VII forbids.

The pieces already exist and are scattered: the meta module computes the
**inconsistency** downgrade from I² (spec 011) and a **publication-bias**
verdict from Egger (spec 012); the `evidence._downgrade` ladder is the
project's canonical grader (§VII). This spec composes them into a single
deterministic certainty rating and surfaces it as the head of the SoF
deliverable — turning the `meta` pipeline into a GRADEpro-equivalent
Summary-of-Findings generator. It adds **no audience** (§IV) and **no slash
command**.

## What is computed vs. what is an honest input

GRADE has five downgrade domains. Three are derivable from the pooled body of
evidence and are **computed deterministically**; two require reviewer judgment
and are taken as **explicit inputs**, never fabricated (§II — a rule the
backbone cannot enforce deterministically is not asserted as if it could):

| Domain | Source |
|---|---|
| **Inconsistency** | Computed — the spec 011 I² → downgrade-steps verdict (0/1/2). |
| **Imprecision** | Computed — *serious* (−1) when the pooled 95% CI crosses the null (the same crossing that makes spec 015's NNT span ∞). |
| **Publication bias** | Computed from Egger when `--diagnostics` ran (with the spec 012 honesty: only `k ≥ 10`, `p < 0.10` downgrades); otherwise "not assessed". |
| **Risk of bias** | Reviewer input (`--risk-of-bias not-serious\|serious\|very-serious`). |
| **Indirectness** | Reviewer input (`--indirectness not-serious\|serious\|very-serious`). |

The **starting certainty** is the body design: a randomised-trial body starts
High (Level A); an observational body starts Low (Level C), per §VII. Set with
`--evidence-base rct|observational`.

## User stories

### P1 — `certainty_from_meta(result, …) → MetaCertainty`

Starts from the base grade, sums the downgrade steps across the five domains,
and applies `evidence._downgrade` (the **same** ladder
`apply_grade_modifiers` and the GRADE evidence-profile table use — no parallel
grader). Returns a typed `MetaCertainty`: the final `EvidenceLevel`, the GRADE
certainty word + ⊕ glyph (A↔High, B↔Moderate, C↔Low, D/E↔Very Low — the
correspondence already in `uncertainty._GRADE_FROM_STR`), an ordered
per-domain breakdown with each domain's contribution and provenance, and a
rationale. Deterministic, stdlib-only.

### P2 — `meta --certainty` surfaces it (and heads the SoF deliverable)

`meta --certainty [--evidence-base …] [--risk-of-bias …] [--indirectness …]`
prints a "GRADE certainty of evidence" block (the ⊕ rating + the domain table
+ rationale + the explicit note that risk-of-bias and indirectness are
reviewer-assessed inputs) and adds a `certainty` key to `--json`. Combined with
`--baseline-risk` (spec 015) it yields the complete SoF row:

    certainty → relative effect → assumed/corresponding risk → NNT.

## Deterministic contract

- Reuses `evidence._downgrade` / `EvidenceLevel`; no new grade ladder (§II).
- Imprecision uses `MetaAnalysisResult.null_value_display` so it is correct for
  ratio (null = 1) and difference (null = 0) measures alike.
- Same input → byte-identical output. Stdlib only (§X).

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- RCT base, all domains not-serious, CI excludes the null → Level A / **High** /
  ⊕⊕⊕⊕.
- A CI that crosses the null adds exactly one imprecision step (Level A → B /
  **Moderate**), and the imprecision domain is tagged *computed*.
- A high-I² pool (inconsistency very serious, 2 steps) downgrades two levels.
- `--risk-of-bias serious --indirectness serious` adds two steps and both are
  tagged *reviewer-assessed*.
- `--evidence-base observational` starts at Level C / **Low**.
- `meta --certainty` renders a ⊕ glyph and a domain table; `--json` carries a
  `certainty` object; `--baseline-risk … --certainty` renders both blocks.
