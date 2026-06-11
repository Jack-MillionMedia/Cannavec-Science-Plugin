# Spec 018 — GRADE imprecision via the Optimal Information Size

**Status**: Implemented, then archived (PR #41 MVP teardown — see git tag pre-mvp-teardown-2026-06-05)

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §X.

## Why this priority

Specs 015–017 built a complete GRADE Summary-of-Findings (SoF) deliverable:
certainty (⊕) → relative effect → absolute effect → NNT, woven into the
research brief. The certainty rating is computed across five GRADE domains by
`grade_profile.certainty_from_meta`. But **one of those five domains is
half-implemented**: imprecision downgrades *only* when the pooled 95 % CI
crosses the null.

That is one of the two GRADE imprecision criteria. The other — the **Optimal
Information Size (OIS)** (Guyatt 2011, *GRADE guidelines 6. Rating the quality
of evidence — imprecision*, J Clin Epidemiol 64:1283, PMID 21839614) — says a
body of evidence whose **total enrolment is smaller than a single adequately
powered trial** is imprecise *even when its CI excludes the null*. Without it,
`certainty_from_meta` will rate three tiny trials with a deceptively tight CI as
**High / ⊕⊕⊕⊕** — exactly the confidence-laundering §VII (GRADE Honesty Over
Confidence-Laundering) exists to prevent. A pooled SMD of 0.58 from 84
participants reads "High certainty" today; its CI excludes zero but it is far
below the OIS of 96 and a GRADE methodologist would downgrade it.

This spec closes that gap. It adds **no new audience** (§IV) and **no new slash
command**; it is pure composition over two primitives the codebase already
ships — `meta_analysis.MetaAnalysisResult` (the pooled effect + per-study
enrolment) and `power_calc` (the Cohen-1988 / Fleiss-1981 single-trial
sample-size formulas, stdlib `math` only, §X). The OIS *is* "the total N of one
adequately powered trial to detect the pooled effect," so the calculator the
`--power-calc` scaffolder already uses is exactly the calculator the OIS needs.

## User stories

### P1 — `meta_analysis.optimal_information_size(result, …)` computes the OIS verdict

A new deterministic function takes a `MetaAnalysisResult` plus the assumed
control event rate (`baseline_risk`, for ratio measures) or a pooling SD
(`pooling_sd`, for raw mean differences) and returns a typed `OISResult`:
total pooled enrolment, the OIS, their ratio, and a `below_ois` verdict. It
dispatches on the pooled measure:

- **RR** — control rate `p₁ = baseline_risk`, experimental `p₂ = RR × p₁`,
  Fleiss-1981 proportion formula.
- **OR** — `calc_odds_ratio_two_arm(odds_ratio, baseline_p)`.
- **SMD** — the pooled SMD *is* Cohen's *d*; `calc_continuous_two_arm` with
  `sd = 1`. No extra input needed.
- **MD** — needs a `pooling_sd` to standardize; otherwise honestly *not
  assessed*.

The OIS is conventionally powered at **80 % / α = 0.05 two-sided** (the trial
convention Guyatt 2011 assumes), independent of the meta CI's confidence level.
The function **never guesses**: a pool whose studies do not all report `n`, a
binary measure with no `baseline_risk`, a generic precomputed effect, or a
pooled effect that maps to a null contrast (OIS unbounded) all return
`assessable = False` with a plain-language reason — and imprecision then falls
back to the CI criterion alone. Same inputs → same output (§II).

### P2 — `certainty_from_meta` applies both GRADE imprecision criteria

The imprecision domain becomes the GRADE two-criterion rule: **+1** if the CI
crosses the null, **+1** if the pool is below the OIS, capped at **2 (very
serious)** — the GRADE ceiling for a single domain. The domain's `basis` string
always carries the OIS verdict (`OIS 84/96 (below)` / `OIS not assessed — …`)
so the rendered certainty table and the `--json` payload show *why*. New
keyword-only parameters (`baseline_risk`, `pooling_sd`, `ois_power`,
`ois_alpha`) keep the signature backward compatible; an unparameterised call
behaves exactly as before for the CI criterion and reports the OIS as *not
assessed*.

### P3 — SoF and the `meta` CLI surface it

`sof.build_sof` threads each outcome's `baseline.risk` (the same control rate it
already uses for the absolute-effect column) into `certainty_from_meta`, so a
binary SoF row's certainty now reflects the OIS for free. The `meta --certainty`
CLI threads its existing `--baseline-risk` value through (one input, two GRADE
uses) and gains an optional `--pooling-sd` for the MD case. A continuous-SMD
pool needs no extra flag.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- A pooled **SMD 0.58 from 84 participants** whose 95 % CI **excludes** zero is
  rated **down one level for imprecision** because 84 < OIS 96 — it is no longer
  reported as High certainty.
- The canonical `_rr_outcome` pool (RR ≈ 0.52, N = 605, OIS ≈ 202) **meets** its
  OIS and stays **High** — no regression to the spec 017 SoF deliverable.
- A near-null RR pool with a baseline (CI crosses null **and** N ≪ OIS) is rated
  **very serious (−2)** for imprecision.
- `optimal_information_size` is **not assessed** (honest, non-zero-step-free)
  when per-study `n` is missing, when a binary measure has no baseline risk, for
  a generic effect, and when the pooled effect maps to a null contrast.
- `meta --certainty --baseline-risk R` renders the OIS verdict inside the GRADE
  certainty table and in `--json`.
