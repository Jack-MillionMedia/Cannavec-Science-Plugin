# Spec 012 — Meta-analysis robustness diagnostics

**Status**: Implemented, then archived (PR #41 MVP teardown — see archive/ARCHIVE_MANIFEST.md)

**Created**: 2026-06-01

**Constitutional gates**: §I (Primary-Source-Or-Refuse), §II (Deterministic
Backbone), §III (Test-First), §VII (GRADE Honesty), §X (Stdlib-Only).

## Why this priority

Spec 011 made the GRADE **inconsistency** domain quantitative (I² → verdict →
certainty downgrade). Two GRADE downgrade domains a review team assesses
quantitatively were still left as conservative defaults: **publication bias**
(`grade_profile` hardcoded a single-source heuristic) and the *robustness* of
the pooled estimate itself. This spec closes both — completing the arc of
making the GRADE downgrade domains data-driven rather than asserted.

A Cochrane reviewer does not stop at a pooled estimate. They ask:

1. **Are small studies skewing the result?** — Egger's regression test for
   funnel-plot asymmetry / small-study effects.
2. **Is the result driven by one trial?** — a leave-one-out sensitivity
   analysis that re-pools the evidence dropping each study in turn.

Both are deterministic, stdlib-only, and operate on the §I-anchored
`EffectSize` set from spec 011, so they add **no new audience** (§IV) and
**no new slash command** (the surface stays at five).

## User stories

### P1 — Egger's small-study-effects test → GRADE publication bias

`egger_test(effects)` regresses each study's standard-normal deviate
(yᵢ/seᵢ) on its precision (1/seᵢ) and tests whether the intercept differs
from zero (Student's-t, df = k − 2). A non-zero intercept signals funnel
asymmetry. `grade_publication_bias(result)` maps the test to a GRADE
publication-bias verdict **honestly**: Egger's test is underpowered below 10
studies (Sterne 2011, BMJ), so a positive test with 3 ≤ k < 10 is reported
*but does not trigger a GRADE downgrade*; only k ≥ 10 with p < 0.10 yields a
"strongly suspected" downgrade.

### P2 — Leave-one-out sensitivity

`leave_one_out(effects)` re-runs the random-effects pool dropping each study
in turn, reporting the recomputed estimate, CI, I², and the **influence**
(shift in the pooled estimate) of each omitted study — surfacing the trial
that, if removed, would most change the conclusion.

### P3 — Surfaced through the `meta` CLI and the GRADE profile

`python3 -m cannavec_science meta studies.json --diagnostics` appends an
Egger section and a leave-one-out table (Markdown, or JSON keys with
`--json`). `grade_profile.build_profile(..., pubbias_by_outcome=...)`
consumes an Egger result per outcome, making the publication-bias column and
the certainty downgrade data-driven (mirroring spec 011's inconsistency
bridge). Both new parameters default to absent — backward compatible.

## Deterministic contract

- **Egger**: ordinary-least-squares intercept of SND on precision; intercept
  SE from the residual variance; two-sided p from the Student's-t survival
  function (regularized incomplete beta, stdlib `math.lgamma` only). Requires
  k ≥ 3 (regression df ≥ 1); refuses below that.
- **Publication-bias verdict**: k < 3 → not assessable; 3 ≤ k < 10 with
  p < 0.10 → detected-but-underpowered (no downgrade); k ≥ 10 with p < 0.10 →
  strongly suspected (one downgrade); else undetected.
- **Leave-one-out**: deterministic input ordering; requires k ≥ 2.
- **Determinism / §X**: no LLM, no network, no randomness; only `math`.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- New `tests/test_meta_diagnostics.py`: Egger intercept/t/p hand-verified on
  a non-degenerate worked example; Student's-t and incomplete-beta numerics
  checked against known values; publication-bias mapping covers the
  underpowered and ≥ 10-study regimes; leave-one-out influence is exercised
  on a homogeneous and an outlier-driven set; CLI `--diagnostics` (Markdown +
  JSON) and refusal paths.
- A k ≥ 10 positive Egger result downgrades a Level-A base grade through
  `grade_profile`'s publication-bias bridge.
