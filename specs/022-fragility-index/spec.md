# Spec 022 — Fragility Index of a single trial

**Status**: Implemented, then archived (PR #41 MVP teardown — see archive/ARCHIVE_MANIFEST.md)

**Created**: 2026-06-01

**Constitutional gates**: §II, §III, §VII, §X.

## Why this priority

Specs 013 / 018 / 021 deepened the *meta-analytic* refusal to overstate
precision (prediction interval, OIS, HKSJ). This spec takes the same scepticism
down to the unit a reviewer actually scrutinises first: **a single trial's
"statistically significant" 2×2 result.**

A p-value of 0.04 sounds decisive. The **Fragility Index** (Walsh et al. 2014,
J Clin Epidemiol 67:622, PMID 24411409) asks the question that exposes it: *how
many patients would have had to have a different outcome for "significant" to
become "non-significant"?* When the answer is **1** — one patient out of
hundreds — the headline is fragile, and a reviewer should say so. Walsh found
the median FI across high-impact RCTs was 8, and often smaller than the number
of patients lost to follow-up. For a cannabis-research scientist appraising the
small, often-underpowered trials that dominate the field, the Fragility Index is
one of the highest-yield robustness checks available, and nothing in the product
computed it.

It is **deterministic** and **stdlib-only** (§X): exact two-sided Fisher's exact
test via `math.comb`, no SciPy. It is **honest** (§VII): the index is reported
only for an already-significant result; a non-significant input is surfaced as
such, not coerced into a misleading number. It adds **no slash command** (§IV)
— it is a new `python3 -m cannavec_science fragility` CLI subcommand, the
single-trial analogue of the `meta` pooling surface.

## User stories

### P1 — `fragility.fisher_exact_two_sided(a, b, c, d)`

An exact two-sided Fisher's exact p for a 2×2 table, by summing the
hypergeometric probabilities of every same-margin table no more likely than the
observed one. Exact integer binomials; deterministic; pinned against the
textbook `[[3,1],[1,3]] → 0.4857` value.

### P2 — `fragility.fragility_index(events_t, n_t, events_c, n_c, …)`

Converts non-events to events one at a time in the arm with the **fewer events**
— the direction that moves the table toward the null — recomputing the exact p
until it reaches α, and returns a typed `FragilityResult` with `to_dict()`: the
index, the **fragility quotient** (FI / total N, Ahmed 2016), the observed p,
the p once it crosses α, and which arm was modified. A non-significant result
returns `significant = False` with the index undefined and a plain explanation.
Inputs are range-validated.

### P3 — `python3 -m cannavec_science fragility …`

`fragility --events-t A --n-t N --events-c C --n-c M [--alpha 0.05] [--json]`
renders the index (or the honest non-significant message) to Markdown and JSON.
A non-significant result is a clean, expected outcome and exits 0; a malformed
table exits non-zero.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- `fisher_exact_two_sided(3,1,1,3) == 0.4857` (4 dp); the test is symmetric under
  row/column relabelling.
- `fragility_index(1,50,9,50)` is significant with **FI = 1**, fragility quotient
  0.01, modifies the treatment (fewer-event) arm, and its p crosses from < 0.05
  to ≥ 0.05; `(8,100,20,100) → 2`, `(10,100,25,100) → 4`.
- A reversed table `(9,50,1,50)` modifies the **control** arm (the fewer-event
  one) and still gives FI = 1.
- A non-significant result returns `significant = False`, `fragility_index =
  None`; a stricter α can flip a significant result to non-significant.
- `fragility …` renders Markdown and `--json`; a non-significant result exits 0;
  `events > n` exits non-zero.
