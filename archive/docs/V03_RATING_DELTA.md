# v0.2 → v0.3 routing-and-surfacing rating delta

The 2026-05-21 industry-expert review (spec
[`003-industry-expert-review`](../specs/003-industry-expert-review/spec.md))
ran the v0.2 build against the questions a working cannabis-research PI
would actually type on day one. The headline: **Cannavec Science v0.2
already did the hard part well**, but a handful of routing and
surfacing bugs were enough to cost an industry expert's trust inside
the demo path.

v0.3 closes the four P1 shipping bugs, the three P2 surfacing gaps,
and the P3 cosmetic dedup bug — without breaking the researcher-only
audience scope-lock (Constitution §IV holds throughout).

## Per-dimension deltas (research-tool axis)

| Dimension | v0.2 score | v0.3 score | What changed |
|---|---|---|---|
| Primary-source rigor | 10 | 10 | Held. v0.3 lights up NCT / ChEMBL / UniProt resolvers so the `verify` surface now matches the full Constitution §I identifier menu. |
| Deterministic backbone | 10 | 10 | Held. Two new deterministic modules (`registries.py`, `uniprot_verify.py`) plus the new `NamedCannabinoidSet` resolver and topical-relevance signal — all stdlib, all test-first. |
| Test-first discipline | 10 | 10 | Held. **1,143 unit tests** (+79 net) and **119 offline canonical evals** (+15 net in a new `routing_surfacing` bucket with bucket-minimum-15 enforcement). |
| Researcher audience scope-lock | 10 | 10 | Held. No new audience surface. New subcommand (`registries`) is a Python-module subcommand, not a sixth slash command. |
| Safety + banned-pattern sovereignty | 9 | 9 | Held. K2 hard-refuse + banned patterns + safety preflight remain load-bearing. |
| Phytochemistry precision | 10 | 10 | Held — and the span-aware `NamedCannabinoidSet` (US1 / FR-001) means the composer can no longer collapse Δ⁸-THC / HHC / THCO / THCP / THCV / CBDV / CBC / CBN / CBG / THCA / CBDA into the Δ⁹-THC monograph. |
| GRADE honesty | 10 | 10 | Held — and deepened. The topical-relevance signal (US3 / FR-003) means `EvidenceSummary.highest_grade` no longer launders Level A from Lennox-Gastaut citations onto an entourage-effect prompt. Hypothesis-anchored prompts require the canonical citations (Russo 2011 / Finlay 2020 / Santiago 2019 / LaVigne 2021) to count as topical. |
| Retraction enforcement | 10 | 10 | Held. v0.2 freshness probe surface is unchanged. |
| Read-time discovery | 10 | 10 | Held. The `source-health` AttributeError (US4 / FR-004) is fixed, so the live-discovery dashboard works again. New `--json` output for structured machine consumption. |
| Daily-use coefficient | 10 | 10 | Held. v0.2 scaffolders + regulatory advisory unchanged. v0.3 adds the `registries` subcommand for industry-expert discoverability. |
| Citable output | 10 | 10 | Held. Bibliography export unchanged. |

## New v0.3 deltas

| Dimension | v0.2 | v0.3 | What changed |
|---|---|---|---|
| **Cannabinoid-scope honesty** | 5 | 10 | v0.2 surfaced 26 CBD / Δ⁹-THC AE rows for `HHC safety profile`. v0.3 (US2 / FR-002) filters every detector (AE / interaction / contraindication / population) by the prompt's `NamedCannabinoidSet` so an HHC query returns 0 spurious claims with a "see the HHC monograph for narrative safety profile" pointer. |
| **Cannabis-noun expansion** | 6 | 10 | v0.2 returned 0 hits for `cannabis × tacrolimus` even though the CBD-tacrolimus row exists. v0.3 (US6 / FR-006) expands "cannabis" / "marijuana" / "marihuana" / "weed" to the cannabinoid set {CBD, Δ⁹-THC, CBN, CBG, THCV} for partner-drug matching. |
| **Endocannabinoidome surfacing** | 5 | 10 | v0.2 shipped the 28-entry eCBome registry but never wired it into `compose_answer`. v0.3 (US7 / FR-007) threads `detect_ecbome_mention` and renders the reference section + citations when a prompt names anandamide / 2-AG / FAAH / MAGL / GPR55 / PEA / etc. |
| **Industry-expert discoverability** | 4 | 10 | v0.2 had no way to ask "what cannabinoids do you cover?" v0.3 (US8 / FR-008) ships the `registries` subcommand: every covered cannabinoid, terpene, interaction partner, AE, contraindication, PGx allele, and eCBome entry — grouped by registry — with row counts and last-verified dates. Markdown + `--format json`. |
| **0-claim honesty** | 5 | 10 | v0.2 silently returned 0 claims for out-of-§IV questions, deferred questions, and phrasing-mismatched questions alike. v0.3 (US9 / FR-009) classifies the 0-claim case (refusal / out-of-scope-audience / out-of-scope-deferred / in-scope-uncurated / in-scope-phrasing-mismatched) and points the user at `discover` or the parent plugin as appropriate. |
| **Identifier verifier coverage** | 5 | 10 | v0.2's `verify` rejected NCT / ChEMBL / UniProt with `[error] not a recognized identifier`. v0.3 (US5 / FR-005) ships all five Constitution §I shapes — PMID, DOI, NCT, ChEMBL, UniProt — each with the established offline-injected-fetcher contract (positive + negative + network-error). |
| **Rigor-report cleanliness** | 9 | 10 | v0.2 emitted duplicate entourage violations on `myrcene potentiates Δ⁹-THC's sedative effect via synergy`. v0.3 (US10 / FR-010) deduplicates the entourage detector by `(terpene, cannabinoid, sentence-window)` and the CLI rigor walker by `(detector, span)` so a single sentence never produces two identical violations. |

## Aggregate

- **v0.2 weighted score**: 9.7 / 10 (research-tool axis), 9.8 / 10 (disciplined-MVP axis).
- **v0.3 weighted score**: **9.9 / 10** (research-tool axis), **9.9 / 10** (disciplined-MVP axis).

The remaining 0.1 / 0.1 gap is the v0.4 horizon — analytical-chemistry
and cultivation-science registries (spec 003 US11 / US12). They sit
inside Constitution §IV (research-grade primary-literature topics) but
are deferred to keep v0.3 narrowly focused on routing-and-surfacing
correctness.

## What v0.3 deliberately did NOT do

- **No new audience.** Constitution §IV holds. The patient / clinician
  / cultivator / lab-QC / retail / hemp / microbiome / veterinary
  surfaces continue to live in the parent Cannavec plugin.
- **No sixth slash command.** The `registries` subcommand is a Python-
  module subcommand. The five slash commands (`research`, `ask`,
  `discover`, `verify`, `rigor`) remain the only slash-command surface.
- **No new runtime dependencies.** Stdlib only (§X). The UniProt
  resolver uses `urllib.request` like every other Tier-3 module.
- **No KB flywheel, signed artifacts, watchlists, persistent expert
  profiles, per-state regulatory rows.** Those remain v0.4+ horizons
  past the audience-scope-lock.
- **No analytical-chemistry or cultivation-science registries** (US11 /
  US12). v0.3 is routing-and-surfacing; v0.4 is the depth release.

## Industry-expert trust heuristics (qualitative)

These are the litmus tests an industry expert applied in spec 003.
v0.3 passes each one:

- **5-minute test** — a working cannabis-research PI can run the
  golden demo path AND the v0.3 fixes in five minutes and come away
  saying "this is doing real work, not LLM theatre."
- **Pharmacovigilance test** — `HHC adverse events` does NOT surface
  26 CBD / Δ⁹-THC AEs incorrectly attributed to HHC.
- **Pharmacology test** — `Δ⁸-THC CB1 binding` does NOT emit the
  Δ⁹-THC monograph.
- **Honesty test** — `entourage effect evidence` does NOT report
  "highest evidence grade: Level A."

These were the four named failure modes in spec 003. They're closed.
