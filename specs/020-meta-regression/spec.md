# Spec 020 — Meta-regression on a continuous moderator

**Status**: Implemented

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §X.

## Why this priority

The `meta` surface can already *detect* heterogeneity (Q, I², τ², the spec 013
prediction interval) and *split* it by a categorical moderator (the spec 014
subgroup analysis). The missing half is **explaining** it with a **continuous**
moderator — the single most common follow-up a reviewer asks when I² is high:

- Does the effect grow with **THC dose**?
- Does it drift with **study year** (a secular trend / changing populations)?
- Does it track **baseline severity**, **mean age**, or **trial duration**?

Subgroup analysis cannot answer these — bucketing a dose continuum into "low /
high" throws away information and invites cut-point fishing. Meta-regression is
the right tool, and its absence is a conspicuous gap in an otherwise
Cochrane-grade synthesis surface.

This spec adds a **random-effects meta-regression** on one continuous moderator,
the continuous analogue of the existing subgroup analysis. It is **composition**
(§II): weighted least squares plus a DerSimonian-Laird residual-τ² estimator,
built from the same stdlib numerics (`math` only, §X) the rest of the module
uses — no NumPy, no `statsmodels`. It anchors to the same §I gate (every effect
needs a primary-source identifier) and reports honestly under §VII: it never
hides that meta-regression with few studies is fragile.

## User stories

### P1 — `meta_analysis.meta_regression(effects, moderators, …)`

Fits `yᵢ = β₀ + β₁·xᵢ` by WLS with random weights `1/(vᵢ + τ²_res)`, where
`τ²_res` is the DerSimonian-Laird residual heterogeneity (the moment estimator
`(Q_E − (k−p)) / tr(P)`). Returns a typed `MetaRegressionResult` with `to_dict()`:
slope + SE + CI + test statistic + p-value, intercept, **R²** (the share of
between-study τ² the moderator explains), residual Q / I² / τ², and the
small-study honesty flag. The slope test defaults to the Wald z; `knha=True`
selects the **Knapp-Hartung** t (recommended for few studies). Refuses when
`k ≤ 2` (cannot estimate a slope plus residual heterogeneity) or the moderator
has no variance.

### P2 — Small-k honesty (§VII)

Meta-regression needs ≈ 10 studies per covariate (Higgins & Thompson). When
`k < 10` the result carries `enough_studies = False` and the rationale appends a
visible `CAUTION: … treat as exploratory` clause — the same honest-about-limits
posture the Egger `k ≥ 10` rule and the spec 018 OIS criterion take. The tool
computes the regression but never lets a thin pool masquerade as a firm trend.

### P3 — `meta --moderator-key KEY [--knha]` surfaces it

The `meta` subcommand reads a numeric field named by `--moderator-key` from each
study record and appends a **Meta-regression on KEY** block — slope, CI, test,
R², residual heterogeneity — to Markdown and `--json` (`meta_regression`), with
`--knha` selecting the Knapp-Hartung t. A missing or non-numeric moderator field
exits non-zero with a clear message.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- An exactly linear pool (`yᵢ = 1 + 0.5·xᵢ`, equal variances) recovers
  slope = 0.5, intercept = 1.0, R² = 1.0, residual Q = 0 to machine precision.
- A pool with a real positive trend returns a significant slope (Wald z and
  Knapp-Hartung t agree on direction; the t-statistic differs from the z on the
  same slope), with R² and residual I² reported.
- A flat moderator returns a near-zero, non-significant slope and low R².
- `k ≤ 2`, a zero-variance moderator, and a length mismatch all refuse; a thin
  pool (`k < 10`) is flagged `enough_studies = False` with a CAUTION rationale.
- `meta --moderator-key dose` renders the block in Markdown and `--json`; a
  missing/non-numeric field exits non-zero.
