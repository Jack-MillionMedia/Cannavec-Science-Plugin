# Spec 023 — Pharmacovigilance disproportionality (signal detection)

**Status**: Implemented, then archived (PR #41 MVP teardown — see archive/ARCHIVE_MANIFEST.md)

**Created**: 2026-06-01

**Constitutional gates**: §II, §III, §V, §VII, §X.

## Why this priority

The product's force-multiplier vision names four expert personas — clinicians,
pharmacologists, toxicologists, scientific reviewers. The quantitative-synthesis
arc (specs 011–022) served the reviewer and the trialist. The **toxicologist /
pharmacovigilance** persona had no quantitative tool: the curated `adverse_events`
registry lists known cannabinoid AEs, but nothing computed a **disproportionality
signal** for a drug-event pair from a spontaneous-reporting database (FAERS,
VigiBase, EudraVigilance) — the single most common safety-surveillance
computation a toxicologist runs.

This spec adds it: the **Proportional Reporting Ratio** (PRR; Evans 2001) and the
**Reporting Odds Ratio** (ROR; Rothman 2004) with confidence intervals and a
Yates χ², plus the **MHRA/Evans signal criterion** (PRR ≥ 2, χ² ≥ 4, a ≥ 3). It
is deterministic and stdlib-only (§X) — a 0.5 continuity correction handles a
zero cell; the χ² uses raw counts.

The §VII honesty discipline is load-bearing here. Disproportionality is
**hypothesis-generating, not causal**: a spontaneous-reporting signal is the
*start* of an investigation, confounded by reporting bias, indication, and
notoriety, and is not an incidence or a risk. The tool says exactly that on every
result, and the signal criterion's `a ≥ 3` / `χ² ≥ 4` gates refuse to fire on
sparse counts (a PRR of 9 from one report is **not** a signal) — the same
refusal-to-overcall posture as the OIS, HKSJ, and Fragility surfaces. This stays
within §V: it reports *what the reports say*, never individualized risk advice.

## User stories

### P1 — `disproportionality.disproportionality(a, b, c, d)`

From the 2×2 of report counts cross-classified by (this drug?) × (this event?),
returns a typed `DisproportionalityResult` with `to_dict()`: PRR + CI, ROR + CI,
the Yates χ², and the signal verdict against the configurable MHRA/Evans
criterion. A zero cell triggers a 0.5 continuity correction (flagged); a
degenerate margin (no reports on the drug, off the drug, of the event, or of
other events) refuses.

### P2 — Honest, non-causal framing (§VII)

Every result's rationale states that disproportionality is hypothesis-generating
from spontaneous reports — not an incidence, a risk, or causation — and names the
unadjusted confounders. The signal gates (`a ≥ 3`, `χ² ≥ 4`) prevent a high PRR
from a handful of reports from being called a signal, and the rationale spells
out which gate failed.

### P3 — `python3 -m cannavec_science signal …`

`signal --drug-event a --drug-other b --other-event c --other-other d [--json]`
renders the PRR/ROR/χ²/verdict to Markdown and JSON. A degenerate table exits
non-zero. The `cannabis-evidence-synthesis` skill routes safety-surveillance
questions to it.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green.
- `disproportionality(25, 1000, 70, 9000)` gives PRR ≈ 3.16, ROR ≈ 3.21, Yates
  χ² ≈ 25.70, and **signal = True**; the ROR CI follows
  `exp(ln ROR ± 1.96·√(1/a+1/b+1/c+1/d))`.
- The signal is withheld when any gate fails: `a < 3`, `χ² < 4`, or `PRR < 2` —
  each exercised independently.
- A zero cell applies the 0.5 continuity correction (flagged); a zero margin
  refuses.
- `signal …` renders Markdown and `--json`; a degenerate table exits non-zero;
  every result carries the hypothesis-generating / non-causal caveat.
