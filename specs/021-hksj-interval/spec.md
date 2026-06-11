# Spec 021 — Hartung-Knapp-Sidik-Jonkman interval

**Status**: Implemented, then archived (PR #41 MVP teardown — see git tag pre-mvp-teardown-2026-06-05)

**Created**: 2026-06-01

**Constitutional gates**: §II, §III, §VII, §X.

## Why this priority

This completes a deliberate triad. The product already refuses to overstate
certainty with few studies in two ways:

- the **random-effects prediction interval** (spec 013, IntHout 2016) — where a
  *new* study's effect could land, not just where the mean is;
- the **Optimal Information Size** imprecision criterion (spec 018, Guyatt 2011)
  — a pool below a single adequately powered trial is imprecise even when its CI
  looks tight.

The missing third piece is the **confidence interval for the pooled estimate
itself**. The classic DerSimonian-Laird z-interval is the one number a reader
trusts most — and it is the one that is **most wrong when k is small**, the
dominant case in cannabis meta-analysis. IntHout 2014 ("The Hartung-Knapp-Sidik-
Jonkman method … is straightforward and considerably outperforms the standard
DerSimonian-Laird method") and the current Cochrane Handbook both recommend the
**HKSJ** interval as the default for random-effects meta-analysis. Shipping a
prediction interval and an OIS check while still reporting a too-narrow DL
z-interval as the headline CI is an inconsistency this spec closes.

It is **composition** (§II): the HKSJ interval reuses the pooled estimate and
τ² already on the `MetaAnalysisResult`, rescales the variance by the observed
weighted residual, and switches the normal quantile for a t with k−1 df. Stdlib
`math` only (§X). It is **non-breaking** — the DL z-interval remains the default
headline; HKSJ is an opt-in `--knha` addition, surfaced beside it so the reader
sees both.

## User stories

### P1 — `meta_analysis.hksj_interval(result)` → modified HKSJ CI

Returns a typed `HKSJResult` with `to_dict()`: the pooled estimate (display
scale), the HKSJ CI, the raw HK variance-scaling factor `q`, whether it was
clamped, the t critical value, the t-statistic, and the two-sided p-value. The
**default is the modified HKSJ** (Röver, Knapp & Friede 2015): the scaling
factor is clamped to ≥ 1 so the interval is **never narrower than the DL-t
interval** — the right default for §VII, since the raw HKSJ can paradoxically
understate uncertainty when studies are more consistent than chance.
`modified=False` recovers the raw `metafor` `test="knha"` interval. Requires
k ≥ 2 (a t needs df ≥ 1).

### P2 — Honest, legible contrast (§VII)

The result's rationale states the q factor, whether it was clamped (and why),
and whether the resulting interval is wider than the DL z-interval. A k = 3 pool
whose DL CI reads a deceptively tight `[0.40, 0.68]` surfaces an honest HKSJ CI
of `[0.30, 0.92]` — the reader sees exactly how much the few-studies penalty
widens the estimate.

### P3 — `meta --knha` surfaces it

`--knha` becomes "use Hartung-Knapp throughout": it adds the modified-HKSJ CI for
the pooled estimate (this spec) **and** selects the Knapp-Hartung t for the
meta-regression slope (spec 020). The HKSJ block renders to Markdown and `--json`
(`hksj`), beside the DL estimate it complements.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- The modified HKSJ interval is **never narrower** than the DL random-effects
  interval (verified on a consistent and a heterogeneous pool).
- A consistent k = 3 RR pool clamps (`q ≈ 0.076 → 1.0`, `clamped = True`) and
  yields a CI wider than DL; with `modified=False` the same pool's raw HKSJ CI
  is narrower than DL (the documented pitfall).
- A heterogeneous pool with `q > 1` is **not** clamped.
- The HKSJ point estimate equals the DL random estimate; the interval uses a t
  with k−1 df; k < 2 refuses.
- `meta --knha` renders the HKSJ block in Markdown and `--json`
  (`hksj.method = "hksj_modified"`); without `--knha` no HKSJ block appears.
