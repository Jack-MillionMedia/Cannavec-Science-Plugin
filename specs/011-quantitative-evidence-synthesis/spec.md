# Spec 011 — Quantitative Evidence Synthesis (deterministic meta-analysis)

**Status**: Implemented

**Created**: 2026-06-01

**Constitutional gates**: §I (Primary-Source-Or-Refuse), §II (Deterministic
Backbone), §III (Test-First), §VII (GRADE Honesty), §X (Stdlib-Only).

## Why this priority

The platform already does write-time rigor (rigor_checks, banned_patterns),
read-time discovery (13 live lanes), and a GRADE *evidence-profile table*
(`grade_profile.py`). But the profile's **inconsistency column is a stub** —
it is hardcoded to `"not serious"` because nothing in the backbone computes
heterogeneity. A working cannabis-research team has a biostatistician who
pools effect sizes across studies and a GRADE methodologist who downgrades
for inconsistency when those estimates disagree. That is exactly the
"force-multiplier" capability missing from the deterministic backbone.

This spec adds **quantitative evidence synthesis**: an inverse-variance
meta-analysis primitive that turns a set of per-study effect sizes into a
pooled estimate, a heterogeneity assessment (Cochran's Q, I², τ²), and a
GRADE *inconsistency* verdict that plugs into the existing
`evidence.apply_grade_modifiers(inconsistency_serious=...)` machinery and
the `grade_profile` table.

It widens **no audience** (§IV) and adds **no slash command** (the surface
stays at five). It deepens §VII (GRADE honesty) by making the inconsistency
domain data-driven instead of an optimistic default, and it stays inside
§I by **refusing any effect size that is not anchored to a primary-source
identifier** (PMID / DOI / NCT / ChEMBL / UniProt / URL).

## User stories

### P1 — Pool a set of effect sizes (CLI `meta`)

A researcher has extracted effect estimates from N trials (raw 2×2 tables,
raw continuous arm summaries, or precomputed yᵢ/vᵢ). They run:

```bash
python3 -m cannavec_science meta studies.json --measure OR
```

and get a deterministic forest table + fixed-effect and DerSimonian–Laird
random-effects pooled estimate (with 95 % CI and a two-sided p-value),
Cochran's Q (with its χ² p-value), I², τ², and a GRADE inconsistency verdict
with its rationale. `--json` emits the typed result for downstream tooling.
Every study row shows its primary-source identifier.

**Independently testable.** Refusal exit code (non-zero) when a study lacks
an identifier (§I), when fewer than one study is supplied, or when a 2×2
table / variance is impossible.

### P2 — Feed the verdict into the GRADE evidence profile

`grade_profile.build_profile(answer, meta_by_outcome=...)` accepts a mapping
of outcome label → `MetaAnalysisResult` and uses each result's computed
inconsistency verdict (and certainty downgrade) instead of the hardcoded
default. Backward compatible: the parameter defaults to `None` and the
existing behaviour (and all existing tests) is unchanged.

## Deterministic contract

- **Effect measures**: odds ratio (OR) and risk ratio (RR) for binary
  outcomes (Haldane–Anscombe 0.5 continuity correction on any zero cell);
  mean difference (MD) and standardized mean difference (Hedges' g, SMD) for
  continuous outcomes; and a `generic` mode taking precomputed (yᵢ, vᵢ).
- **Pooling**: inverse-variance fixed effect; DerSimonian–Laird random
  effects. Ratio measures are pooled on the log scale and displayed
  exponentiated.
- **Heterogeneity**: Cochran's Q, df = k − 1, I² = max(0, (Q − df)/Q)·100 %,
  τ² = max(0, (Q − df)/C) with C = Σwᵢ − Σwᵢ²/Σwᵢ. The Q p-value is the χ²
  survival function (regularized upper incomplete gamma, stdlib `math` only).
- **GRADE inconsistency mapping** (Cochran/GRADE thresholds): I² < 40 % →
  *not serious*; 40 ≤ I² < 75 % → *serious* (one downgrade); I² ≥ 75 % →
  *very serious* (two downgrades). k < 2 → *not assessable (single study)*.
- **Determinism**: identical input → byte-identical output. No LLM, no
  network, no randomness. Stdlib `math` only (`erf`/`erfc`/`lgamma`).

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- New `tests/test_meta_analysis.py` ships positive + negative + refusal
  cases for every public function (§III), including reference values
  hand-verified against a worked example.
- A high-I² result downgrades a Level-A base grade to Level B through the
  existing `apply_grade_modifiers` path (proves the GRADE bridge).
- `python3 -m cannavec_science meta <file>` returns non-zero when any study
  lacks a primary-source identifier (§I).
