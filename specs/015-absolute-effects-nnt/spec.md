# Spec 015 — Absolute effects & Number-Needed-to-Treat (GRADE Summary-of-Findings translation)

**Status**: Implemented, then archived (PR #41 MVP teardown — see git tag pre-mvp-teardown-2026-06-05)

**Created**: 2026-06-01

**Constitutional gates**: §I, §II, §III, §VII, §X.

## Why this priority

Specs 011–014 give the researcher a pooled **relative** effect (OR/RR with
CI), heterogeneity, a GRADE inconsistency verdict, publication-bias detection
and adjustment, sensitivity analysis, a prediction interval, and subgroup
moderators. What a clinician or a GRADE reviewer reaches for next is the step
that makes a pooled relative effect *actionable*: the **anticipated absolute
effect**.

A risk ratio of 0.50 is meaningless to a decision-maker until it is anchored
to a baseline risk: *0.50 on a 2 %-per-year event is 10 fewer events per
1000; on a 40 %-per-year event it is 200 fewer.* The GRADE Summary-of-Findings
(SoF) table exists precisely to carry this translation — "assumed comparator
risk → corresponding intervention risk → risk difference per 1000 → Number-
Needed-to-Treat" — and it is the single most-produced deliverable of an
evidence-review team. Today the backbone computes the relative effect and
stops; "NNT" appears in the registries only as hand-typed prose, never as a
computed, CI-bearing quantity. This spec closes that gap.

This is deterministic, stdlib-only, and operates on the §I-anchored pooled
estimate. It adds **no audience** (§IV) and **no slash command** — it extends
the existing `meta` subcommand and exposes one new module.

## User stories

### P1 — Absolute risk difference from a relative effect + assumed comparator risk

`absolute_effect(measure, estimate, ci, acr, outcome, outcome_desirable,
acr_provenance, confidence)` takes a ratio measure (`"RR"` or `"OR"`) with its
display-scale point estimate and confidence interval, plus an **assumed
comparator risk (ACR)** in (0, 1), and returns a typed `AbsoluteEffect`:

- **RR**: EER = RR · ACR.
- **OR**: EER = (OR · ACR) / (1 − ACR + OR · ACR)  — the GRADE handbook
  odds-to-risk transform.
- **Risk difference** RD = EER − ACR, and its CI by applying the *same*
  transform to the lower and upper bounds of the relative-effect CI at the
  fixed ACR (this is exactly how GRADEpro derives the absolute CI). Because
  both transforms are monotone increasing in the relative effect, the RD
  bounds inherit the relative-effect bound ordering.
- Numbers are also rendered **per 1000** for the SoF "anticipated absolute
  effects" column.

When the transform would push EER outside [0, 1] (e.g. a large RR on a high
baseline), EER is clamped to the unit interval and an `eer_clamped` flag is
set so the rounding is never silently impossible.

### P2 — Number-Needed-to-Treat with the Altman (1998) null-crossing convention

NNT = 1 / |RD|, reported as **NNTB** (benefit) or **NNTH** (harm). Direction
depends on outcome desirability — a rigor point the function refuses to guess:

- **Undesirable** outcome (seizure, relapse, adverse event): the intervention
  benefits when RD < 0 (it lowers the event risk) → NNTB.
- **Desirable** outcome (response, remission): benefit when RD > 0 → NNTB.

The honest subtlety is the **confidence interval on NNT**. When the relative-
effect CI crosses the null (RR/OR CI spans 1, so the RD CI spans 0), there is
**no single finite NNT interval**: it runs from a finite NNT-benefit, through
infinity (RD = 0, no effect), to a finite NNT-harm. Per Altman 1998 (*BMJ*
317:1309) the result is reported as

    NNTB a  to  ∞  to  NNTH b

never as a naive `(1/RD_hi, 1/RD_lo)` that hides the discontinuity. A non-
significant pooled effect therefore yields an `nnt_crosses_null = True`
`AbsoluteEffect` whose rendered NNT line contains `∞` — the §VII honesty
guarantee made arithmetic. When the CI does **not** cross the null, both NNT
bounds are finite and on the same side (NNTB…NNTB or NNTH…NNTH).

### P3 — `absolute_from_meta()` + surfacing through `meta --baseline-risk`

`absolute_from_meta(result, acr, outcome, outcome_desirable, acr_provenance,
model="random"|"fixed")` reads a `MetaAnalysisResult` for a ratio measure and
its requested-confidence CI and returns the `AbsoluteEffect`. It refuses a
non-ratio (`MD`/`SMD`) result — absolute *risk* differences are undefined for
a continuous mean difference.

`meta --baseline-risk R [--outcome L] [--outcome-desirable]
[--baseline-source L] [--baseline-pmid …] [--absolute-model random|fixed]`
appends the SoF block to the Markdown report and an `absolute_effect` key to
the `--json` payload. The baseline may also be supplied in the JSON spec
(`{"baseline": {"risk": …, "label": …, "pmid": …}}`); the CLI flag overrides.

## Deterministic contract & §I provenance

- Pure `math` only; same input → byte-identical output (§X, §II).
- The **relative** effect is §I-anchored by construction — every `EffectSize`
  feeding the meta result already required a primary-source identifier.
- The **assumed comparator risk** carries its own `RiskProvenance` (a label
  plus optional PMID/DOI/NCT/URL). GRADE permits an assumed/illustrative
  baseline, but it must never be laundered as measured fact: when the baseline
  is unsourced, the rendered SoF block and the JSON (`acr_sourced: false`)
  carry a visible "assumed baseline — not primary-source anchored" caveat, the
  same way spec 014's imputed studies are flagged explicitly hypothetical
  (§I). The absolute effect also inherits the pooled GRADE inconsistency note
  so it is never quoted with more certainty than the evidence carries (§VII).

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- RR = 0.50, ACR = 0.20, undesirable → EER = 0.10, RD = −0.10, **NNTB 10**;
  CI from RR (0.40, 0.625) → NNTB 8.33 to 13.33.
- OR = 0.50, ACR = 0.20 → EER = 0.1111, RD = −0.0889, **NNTB 11.25** (verifies
  the odds-to-risk transform differs from the RR path).
- Null-crossing RR = 0.80, CI (0.60, 1.0671875), ACR = 0.25 → point NNTB 20,
  CI **NNTB 10 to ∞ to NNTH 59.53** (`nnt_crosses_null = True`; rendered line
  contains `∞`).
- Desirable outcome RR = 1.50, ACR = 0.30 → RD = +0.15, **NNTB 6.67** (the
  direction flips with `outcome_desirable=True`).
- Refusals: ACR ∉ (0, 1); a continuous (`MD`/`SMD`) meta result; a missing
  outcome-desirability decision is required, not defaulted silently in the
  core constructor.
- Unsourced baseline → `acr_sourced: false` and a visible caveat in render.
