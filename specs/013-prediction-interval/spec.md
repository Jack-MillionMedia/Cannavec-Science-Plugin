# Spec 013 — Random-effects prediction interval

**Status**: Implemented, then archived (PR #41 MVP teardown — see archive/ARCHIVE_MANIFEST.md)

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §X.

## Why this priority

A random-effects **confidence interval** describes uncertainty about the
*mean* effect. It is routinely — and dangerously — misread as the range of
effects a *new* setting might see. When between-study heterogeneity (τ²) is
non-trivial, those two intervals diverge sharply. Since IntHout et al. (2016,
BMJ Open) and the Cochrane Handbook, an elite random-effects meta-analysis
reports the **95% prediction interval (PI)** alongside the CI precisely to
stop that misreading.

The PI is the single most-requested addition a methodologist makes to a
random-effects summary, and the spec 011/012 subsystem already computes
everything it needs (τ², the pooled variance). This spec closes that gap.

## Deterministic contract

For k ≥ 3 studies, the 95% prediction interval is

    μ̂ ± t_{k−2, 0.975} · √(τ² + Var(μ̂))

(Higgins, Thompson & Spiegelhalter 2009; IntHout 2016), where μ̂ is the
random-effects estimate, Var(μ̂) its variance, and τ² the DerSimonian–Laird
between-study variance. The t-quantile is obtained by deterministic bisection
on the existing stdlib Student's-t survival function (no SciPy). For k < 3 the
PI is undefined and reported as `None`. Ratio measures (OR/RR) display the PI
exponentiated, exactly like the CI.

The PI **widens** the CI whenever τ² > 0 and never narrows it; with τ² = 0 it
still differs from the CI because it uses the t- rather than z-quantile and
adds no shrinkage. The computation is deterministic — identical studies →
identical PI.

## User stories

### P1 — PI in the `meta` output

`meta_analyze` populates `MetaAnalysisResult.prediction_interval` (and a
display variant for ratio measures). `render_markdown` and `--json` surface
it on the random-effects line. Backward compatible — the field defaults to
`None` and existing callers/tests are unaffected.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- New tests: the t-quantile matches known critical values; the PI is wider
  than the CI under heterogeneity; PI is `None` for k < 2; a hand-verified
  reference PI on a k = 3 example; ratio-measure PI displays exponentiated.
