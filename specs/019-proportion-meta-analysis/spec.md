# Spec 019 — Single-arm proportion meta-analysis (Freeman-Tukey)

**Status**: Implemented, then archived (PR #41 MVP teardown — see archive/ARCHIVE_MANIFEST.md)

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §IX, §X.

## Why this priority

The `meta` surface (specs 011–018) pools **two-arm comparative** effect sizes —
OR, RR, MD, SMD. Every one of those is a *contrast between two arms*. None can
pool a **single-arm rate**, and single-arm rates are everywhere a working
cannabis-research scientist actually looks:

- **Adverse-event incidence** across trial arms — "what is the pooled incidence
  of somnolence across the Epidiolex CBD arms?" A toxicologist reads a *rate*,
  not a ratio.
- **Prevalence** across cohorts — cannabis-use-disorder prevalence among daily
  users; cannabinoid-hyperemesis prevalence among heavy users; the proportion
  of THC-positive injury presentations.
- **Responder / remission proportions** in single-arm or open-label studies.

Today those questions return nothing the `meta` surface can pool. This spec adds
the standard tool: a **Freeman-Tukey double-arcsine** single-arm proportion
meta-analysis. The double arcsine is the right transform precisely because it is
**defined at 0 % and 100 %** — exactly the boundary cells (zero adverse events,
universal response) where a logit pool breaks — and stabilises the variance so a
50/500 study and a 3/8 study pool honestly.

The increment is mostly *composition* (§II): once each rate is transformed to a
`(yi, vi)` pair, the **entire** existing pooling pipeline — fixed-effect, DL
random-effects, Cochran's Q / I² / τ², the spec 013 prediction interval, and the
spec 011 GRADE inconsistency verdict — applies unchanged. Only two pieces are
new: the input transform and the Miller (1978) back-transformation of the pooled
estimate. It adds **no slash command**, **no audience** (§IV), and **no new
dependency** — stdlib `math` only (§X). Live rows never auto-promote (§IX): a
pooled rate is an explicit, identifier-anchored computation a researcher runs,
not a curated fact.

## User stories

### P1 — `meta_analysis.proportion_effect(study_id, events, n, …)` transforms one rate

A single-arm record `(events, n)` becomes an `EffectSize` on the Freeman-Tukey
scale: `yi = arcsin(√(x/(n+1))) + arcsin(√((x+1)/(n+1)))`, `vi = 1/(n+1)`
(Freeman & Tukey 1950). The §I identifier requirement is unchanged — a rate with
no primary-source anchor refuses, exactly like every other effect size. Range is
validated (`0 ≤ events ≤ n`, `n > 0`).

### P2 — `proportion_meta_analyze(effects)` pools and back-transforms

Reuses `meta_analyze` for every numeric quantity, then back-transforms the
pooled fixed/random estimates, their CIs, and the prediction interval to
proportions via the Miller (1978) inverse using the **harmonic-mean** sample
size. Returns a typed `ProportionMetaResult` with `to_dict()`: pooled rate +
CI (fixed and random), heterogeneity, prediction interval, the GRADE
inconsistency verdict, and per-study observed rates. The double-arcsine boundary
behaviour is preserved (an all-zero pool reports 0 % with a one-sided upper
bound).

### P3 — `meta --measure prop FILE` surfaces it

The `meta` subcommand gains a single-arm path: `{"measure": "prop", "studies":
[{"study_id", "events", "n", "pmid"}, …]}` (with `cases`/`x` and `total`
aliases). It renders a proportion-MA block — pooled rate, heterogeneity,
prediction interval, GRADE inconsistency, and a per-study observed-rate table —
to Markdown and `--json`, with `--diagnostics` adding the scale-appropriate
Egger small-study-effects test. The render footnote states plainly that a
single-arm rate **carries no comparator — it is not a treatment effect**, so the
surface can never be mistaken for an efficacy claim.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- `proportion_effect` round-trips: FT-transform then back-transform recovers the
  observed rate to 3 dp, **including 0 % and 100 %**.
- The four-study reference pool returns a random-effects pooled rate of **40.2 %
  (95% CI 29.1 % to 51.7 %)**, I² ≈ 75 %, with a wide back-transformed
  prediction interval (the I²-hides-a-wide-PI honesty of spec 013).
- A rate without a primary-source identifier **refuses** (§I); `events > n`,
  `n ≤ 0`, an empty pool, and a non-PFT effect all refuse.
- `meta --measure prop` renders the pooled rate in Markdown and `--json`
  (`measure: "PFT"`), and `--diagnostics` adds Egger; a missing identifier exits
  non-zero.
