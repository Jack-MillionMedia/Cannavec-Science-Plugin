# Spec 014 — Subgroup analysis & trim-and-fill

**Status**: Implemented, then archived (PR #41 MVP teardown — see git tag pre-mvp-teardown-2026-06-05)

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §X.

## Why this priority

Specs 011–013 give the researcher a pooled estimate, heterogeneity, a GRADE
inconsistency verdict, publication-bias detection (Egger), sensitivity
(leave-one-out), and a prediction interval. Two capabilities a senior
methodologist reaches for next remain:

1. **Explain the heterogeneity.** When I² is high, *why*? Subgroup analysis
   partitions the trials (e.g. by dose band, route, indication) and runs the
   Cochrane "test for subgroup differences" (Q_between) to ask whether a
   moderator explains the spread.
2. **Adjust for the publication bias.** Egger *detects* funnel asymmetry;
   Duval & Tweedie (2000) **trim-and-fill** *quantifies* it — estimating how
   many studies appear suppressed and what the pooled estimate would be if
   the funnel were symmetric.

Both are deterministic, stdlib-only, and operate on the §I-anchored
`EffectSize` set. They add **no audience** (§IV) and **no slash command**.

## User stories

### P1 — Subgroup analysis (Q_between)

Each `EffectSize` may carry a `subgroup` label. `subgroup_analysis(effects,
model="fixed"|"random")` pools within each subgroup, then treats the subgroup
summaries as the units of a between-groups test:

    M̄ = Σ w_g·M_g / Σ w_g      (w_g = 1/Var(M_g))
    Q_between = Σ w_g·(M_g − M̄)²,   df = G − 1,   p = χ²_sf(Q_between, df)
    I²_between = max(0, (Q_between − df)/Q_between)·100 %

This is exactly RevMan's "test for subgroup differences" and, under a
fixed-effect model, is algebraically identical to the Q_total − Σ Q_within
decomposition (the tests assert both give the same number). A significant
test (p < 0.05) means the moderator explains part of the heterogeneity.

### P2 — Trim-and-fill (Duval & Tweedie 2000, L0 estimator)

`trim_and_fill(effects, model=...)` runs the iterative L0 algorithm:
center → rank absolute deviations → estimate the number of suppressed studies
k0 = max(0, round((4·Tₙ − n(n+1))/(2n−1))) → trim the k0 most extreme studies
on the over-represented side → re-centre → iterate to convergence. It then
**fills** k0 mirror-image studies about the final centre and re-pools to give
a **bias-adjusted** estimate. The suppressed side is auto-detected (or forced
with `side="left"|"right"`).

The imputed studies are **explicitly hypothetical** — they carry no
primary-source identifier and are never presented as cited evidence (§I).
They exist only to express "if the funnel were symmetric, the estimate would
move from X to Y." k0 = 0 means no adjustment (the funnel is already
symmetric) and the adjusted estimate equals the observed one.

### P3 — Surfaced through `meta --diagnostics`

`meta --diagnostics` additionally runs trim-and-fill (k ≥ 3) and, when the
studies carry `subgroup` labels, subgroup analysis — appending both to the
Markdown report and the `--json` payload.

## Deterministic contract

- Pooling reuses the spec 011 fixed-effect / DerSimonian–Laird machinery.
- Ranking uses average ranks for ties; rounding is round-half-up
  (`floor(x+0.5)`); subgroup iteration order is sorted-by-label. Identical
  input → byte-identical output. Stdlib `math` only (§X).
- Ratio measures (OR/RR) display every estimate exponentiated.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- Subgroup: hand-verified Q_between = 16.0 (df = 1) on a 2×2-study example,
  with the decomposition and subgroup-summary formulas agreeing.
- Trim-and-fill: a symmetric set returns k0 = 0 / adjusted = observed; a
  hand-verified asymmetric set returns k0 = 1, one imputed effect = −0.25,
  and an adjusted estimate (0.175) pulled toward the suppressed side from the
  observed (0.26).
- Both refuse < 3 studies / < 2 subgroups and any study lacking a §I id.
