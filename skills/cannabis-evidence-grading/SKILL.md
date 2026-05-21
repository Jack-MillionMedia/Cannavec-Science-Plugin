---
name: cannabis-evidence-grading
description: GRADE-style evidence grading for cannabis claims. Auto-activate when evaluating, citing, or grading evidence for cannabis efficacy, safety, mechanism, or pharmacology claims. Maps source types to evidence levels (A/B/C/D/E), defines the Source Authority Hierarchy with multiplicative modifiers, and lists required disclosures per claim type.
version: 1.0.0
---

# Cannabis Evidence Grading

Apply this skill any time you evaluate the strength of evidence for a cannabis claim.

## Evidence grades (per cannabis-authoring-standard.md v2.6)

| Grade | Source basis | Acceptable claim wording |
|---|---|---|
| **Level A** | Cochrane / AHRQ / NICE systematic review **OR** ≥ 2 independent high-quality RCTs in alignment | "Established", "demonstrates", "is effective for" |
| **Level B** | Pre-registered, adequately-powered RCT in major journal **OR** specialist-journal RCT pre-registered | "Likely effective", "appears to reduce", "is associated with" |
| **Level C** | Single primary study, observational with multivariable adjustment, single-arm trial n>100, or mechanistic study with primary-database verification | "May reduce", "suggests potential benefit", "preliminary evidence" |
| **Level D** | Open-label / case series n>10 / animal model with translational rationale | "Anecdotal reports", "open-label observations" |
| **Level E** | Single case report / unverified report | "Unverified report", "case report only" |

## GRADE framework domains (applied to every clinical claim before grade assignment)

The grade above is the *starting point*. Apply the five GRADE Working Group domains to downgrade as appropriate. Cannabis-specific notes in brackets.

| Domain | What to assess | Downgrade trigger |
|---|---|---|
| **Risk of bias** | Randomisation, allocation concealment, blinding (notoriously hard for cannabis — patients may unblind via subjective effect), incomplete outcome data, selective reporting [cannabis trials often have unblinding via psychoactivity → mark this explicitly] | Serious limitations: −1; very serious: −2 |
| **Inconsistency** | Heterogeneity across trials in effect direction or magnitude; I² statistic; sub-group analyses [chemotype variation, dose-route variation are common sources for cannabis] | I² > 50%: consider −1; conflicting direction: −1 to −2 |
| **Indirectness** | Population, intervention, comparator, outcome don't match the question (PICO mismatch); surrogate endpoints; mechanism studies extrapolated to clinic [extremely common for cannabis — in vitro CB1 binding ≠ clinical analgesia] | Indirect population/intervention/comparator: −1; mechanism→clinic leap: −2 |
| **Imprecision** | Wide CI crossing the line of no effect; small total event count; underpowered trials [cannabis pilot trials are often n < 50] | CI crosses 0 with wide bounds: −1; total events < 300 for binary outcome: consider −1 |
| **Publication bias** | Asymmetric funnel plot; few small negative studies; trial registry vs publication discrepancy [industry funding skews toward positive reports — flag explicitly] | Suspected: −1; strong evidence: −2 |

For **observational evidence**, apply GRADE upgrade factors after the base downgrades:

| Upgrade factor | Apply when |
|---|---|
| Large effect | RR > 2 or RR < 0.5 with no plausible confounding |
| Dose-response gradient | Clear monotonic relationship across dose/exposure strata |
| Plausible residual confounding biases toward null | Suggests true effect is even larger |

Final claim wording must match the *post-downgrade* grade. If GRADE assessment reduces a single-RCT claim from Level B to Level C+ via indirectness, write "may reduce" not "appears to reduce."

## CONSORT and PRISMA — reporting-quality gates (orthogonal to GRADE)

Before assigning Level A or B to a trial, verify the report meets reporting-quality standards. A trial that fails CONSORT (or PRISMA for SRs) reporting items is **methods_unverified** until the gap is filled.

- **CONSORT 2010 (RCTs)** — must report: trial design, eligibility, intervention with sufficient detail to replicate, primary/secondary outcomes pre-specified, sample size calculation basis, randomisation method, blinding scope, statistical methods, participant flow (CONSORT diagram), baseline data, harms, registration, protocol availability, funding.
- **PRISMA 2020 (systematic reviews / meta-analyses)** — must report: PICO, eligibility, information sources, search strategy with date, selection process, data extraction process, risk-of-bias assessment, effect measures, synthesis methods, certainty of evidence assessment (GRADE), funding.
- **STROBE (observational studies)** — must report: study design at title level, setting, participants with eligibility, variables (exposure, outcome, confounders, effect modifiers), data sources, bias measures, study size, quantitative variables, statistical methods, descriptive data.

A trial registered post-hoc, with primary outcome switched after enrolment, or with funding source omitted, is **automatically capped at Level C** regardless of journal or sample size.

**Penalty rules:**
- Methods Section unread (abstract-only citation) → cap at Level C, mark `methods_unverified: true`
- Single primary study (no replication) → cap at Level C unless pre-registered + adequately powered + major journal (then Level B max)
- Exploratory / post-hoc finding → one-grade penalty until replicated
- Industry-funded with undeclared COI → one-grade penalty
- Pay-to-publish journal (Beall's list / DOAJ-discontinued) → one-grade penalty

## Source Authority Hierarchy (Charter § Source Authority Hierarchy)

Multiplicative weights, capped at 1.00:

| Tier | Source class | Default weight |
|---|---|---|
| 1 | Cochrane / AHRQ / NICE / IQWiG / WHO systematic reviews | 1.00 |
| 1 | Pre-registered, adequately-powered RCT in NEJM/JAMA/Lancet/BMJ/Annals/Nature Med with declared methods | 0.95 |
| 2 | Specialist-journal RCT, pre-registered, peer-reviewed | 0.85 |
| 2 | Major-journal systematic review or meta-analysis (non-Cochrane) | 0.85 |
| 2 | Major-journal observational cohort, n > 1,000, multivariable adjustment | 0.75 |
| 3 | Open-label / single-arm trial, n > 100, declared methods | 0.65 |
| 3 | Mechanistic study with primary-database verification (ChEMBL, BindingDB, etc.) | 0.70 (mechanism), 0.40 (clinic) |
| 3 | Animal model with translational rationale | 0.55 (mechanism), 0.25 (clinic) |
| 4 | Preprint, named authors at credentialed institutions | 0.50 |
| 4 | Case series, n > 10 | 0.45 |
| 5 | Regulatory primary documents (FDA approvals, EMA assessments, schedule notices) | 1.00 for regulatory claims |
| 5 | National pharmacopoeias / formularies | 0.95 for product / preparation claims |
| 5 | Specialist consensus statements (IACM, ICRS, ASAM, AAN, etc.) | 0.70 |
| 6 | Industry whitepaper | 0.35 — record COI flag |
| 6 | Conference proceedings (not subsequently published) | 0.40 |
| 7 | Trade press, news article | 0.20 — record as context only |
| 7 | Advocacy organisation position paper | 0.15 for clinical; up to 0.70 for policy claims |
| 8 | Unsigned blog, anonymous source, content farm | 0.05 — reject by default |

## Multiplicative modifiers

Apply to the base weight. Cap final at 1.00.

| Modifier | Multiplier |
|---|---|
| Pre-registered protocol | × 1.10 |
| Adequately-powered (per pre-stated sample-size calculation) | × 1.05 |
| Replication of prior finding | × 1.10 |
| Conflict of interest declared and material | × 0.85 |
| Conflict of interest undeclared but later surfaced | × 0.50 |
| Author has prior retraction | × 0.70 |
| Pay-to-publish journal (Beall's list / DOAJ-discontinued) | × 0.50 |
| Single-arm trial | × 0.70 |
| n < 20 | × 0.60 |

## Required disclosures per claim type

A claim missing any mandatory disclosure is **downgraded one evidence grade** and **surfaced to Reviewer**:

| Claim type | Mandatory disclosures |
|---|---|
| Clinical efficacy | effect size, 95% CI, n, comparator, primary outcome, evidence grade, funding, COI |
| Mechanism | receptor / enzyme / pathway with identifier, assay, concentration / dose, species, primary source |
| Pharmacokinetic | route, bioavailability range, Tmax, Cmax, t½, primary source, study population |
| Dose / dosing | route, dose range, titration schedule, dose-response source, population, frequency, max dose |
| Drug interaction | substrate, modifier (inhibitor/inducer), CYP isoform, magnitude (Cmax / AUC ratio), source |
| Safety / adverse event | event type, incidence with denominator, severity, reversibility, study type, source |
| Phytochemistry quantity | compound (with isomer), value with units, method (HPLC/GC-MS/etc.), LOD, sample provenance |
| Legal / regulatory | jurisdiction, statutory citation, effective date, scope (medical / recreational / industrial), source URL |
| Cultivation parameter | environment (indoor/outdoor/greenhouse), substrate, light spectrum, photoperiod, climate zone, source |
| Market data | jurisdiction, time period, methodology, sample, source organisation, data vintage |

## Computing a provenance score

```
provenance_score = link_liveness_factor × retraction_factor × source_authority_weight
```

| Component | Range |
|---|---|
| `link_liveness_factor` | 1.0 LIVE, 0.5 REDIRECT_OK, 0.0 DEAD/RETRACTED |
| `retraction_factor` | 1.0 CLEAN, 0.5 EXPRESSION_OF_CONCERN, 0.3 UNDER_CORRECTION, 0.0 RETRACTED |
| `source_authority_weight` | per hierarchy + modifiers, capped at 1.00 |

| Score | Acceptable use |
|---|---|
| ≥ 0.80 | Level A/B claim support |
| 0.60–0.79 | Level C claim support with hedging |
| 0.40–0.59 | Context only, not primary support |
| < 0.40 | Reject; do not cite as primary |

## How to apply

When you are evaluating a cannabis claim's evidence:

1. Identify the source's tier and base weight
2. Apply applicable modifiers (multiplicatively)
3. Match the claim's wording to the highest grade the evidence supports
4. Verify all required disclosures for the claim type
5. If any disclosure is missing, downgrade by one grade and note the omission explicitly
6. Compute provenance score; if < 0.40, do not cite as primary

This skill works in tandem with `cannabis-research-rigor` (Pillar I — Methodological Rigor).
