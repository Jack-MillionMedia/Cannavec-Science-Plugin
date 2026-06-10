# Cannavec Science v0.6 — Rating delta

**Release**: v0.6 research-domain-breadth (spec 006)

**Branch**: `claude/modest-knuth-PUits`

**Date**: 2026-05-24

## Summary

v0.6 fills the four largest demo-time silences a working cannabis-
research scientist hits in v0.5 (pain medicine, cannabis-psychosis,
driving impairment, PTSD / anxiety / sleep), adds a reporting-rigor
deepening on §VII GRADE Honesty (six EQUATOR-network + risk-of-bias
detectors), and adds a thirteenth primary-source live-discovery lane
(OpenAlex). All shipping inside Constitution §IV (researcher-only).

## Delta table

| Surface | v0.5 | v0.6 | Delta |
|---|---|---|---|
| Curated registries | 16 | 20 | +4 (pain_medicine, psychiatry, driving_impairment, ptsd_anxiety_sleep) |
| Total registry rows | ~187 | ~215 | +28 |
| Rigor detectors (phytochemistry) | 7 | 7 | 0 (no regression) |
| Rigor detectors (reporting-guideline + RoB) | 0 | 6 | +6 (CONSORT, PRISMA, STROBE, ROB-2, ROBINS-I, AMSTAR-2) |
| Live-discovery lanes | 12 | 13 | +1 (OpenAlex) |
| Banned-pattern detectors | 16 | 16 | 0 |
| Slash commands | 5 | 5 | 0 (constitution-locked) |
| Unit tests | 1,369 | 1,501 | +132 |
| Eval prompts (total) | 162 | 188 | +26 |
| Eval prompts (offline) | 149 | 173 | +24 |
| Eval bucket: research_domain_breadth | n/a | 19 | new bucket (min 16) |
| Eval bucket: rigor_positive | 35 | 40 | +5 (reporting-rigor positives) |
| Eval bucket: live | 13 | 15 | +2 (OpenAlex) |
| Python LOC under `cannavec_science/` | ~30,700 | ~33,700 | +~3,000 |

## What v0.6 ships

### Pain medicine registry (≥ 7 rows)

The #1 medical-cannabis topic. Anchored to NASEM 2017 chapter-4
"conclusive evidence" finding (Whiting 2015 PMID 26103030 anchor) +
Stockings 2018 + Mücke 2018 Cochrane + Boehnke 2019 + Andreae 2015
IPD-MA + de Vita 2018 experimental-pain SR. The Mücke vs Whiting tone
divergence is a teaching example of evidence-base vs evidence-
interpretation differences.

### Cannabis-and-psychosis psychiatry registry (≥ 6 rows)

One of the most-cited and most-controversial cannabis-research areas.
Anchored to Di Forti 2019 EU-GEI Lancet Psychiatry (PMID 30902669,
the high-potency / daily-use case-control study) + Marconi 2016
dose-response SR + Vaucher 2018 MR (with explicit instrument-validity
caveats) + Bhattacharyya 2009 acute-THC fMRI + Hjorthøj 2023 Danish
national register + Murray 2017 Lancet Psychiatry narrative review.

### Driving-impairment science registry (≥ 5 rows)

The SCIENCE, not the LAW. Anchored to Compton 2017 NHTSA Virginia
Beach case-control (the most-cited AND most-mis-cited result in the
literature — unadjusted OR ≈ 1.25, adjusted OR ≈ 1.05 after
demographics + alcohol) + Hartman 2015 Clin Chem plasma-THC dose-
response + Marcotte 2022 JAMA Psychiatry driving-simulator RCT (the
~1.5 h peak impairment / ~5 h return-to-baseline time-course) +
Brubacher 2022 NEJM post-legalization BC cohort + Bondallaz 2016
Forensic Sci Int SR.

### PTSD / anxiety / sleep registry (≥ 5 rows)

The largest commercial-claim space and the literature is sparser
and more cautionary than commercial copy suggests. Bonn-Miller 2021
PLOS One PTSD smoked-cannabis cross-over RCT (PMID 33667097) — the
only RCT and importantly **largely negative** on the primary CAPS-5
endpoint — surfaces with the negative result honestly stated, not
miscited as 'evidence for cannabis in PTSD'. Plus Crippa 2011 and
Bergamaschi 2011 CBD-SAD acute challenges, Bedi 2010 biphasic
Δ⁹-THC anxiety dose-response, and Walsh 2017 Sleep Med Rev SR
('limited and inconclusive evidence').

### Reporting-rigor module (≥ 6 detectors)

A §VII GRADE-honesty deepening. Detectors fire when prompt text
mentions a study-design class without acknowledging the appropriate
EQUATOR-network reporting guideline or risk-of-bias tool. CONSORT
for RCTs, PRISMA-2020 for SRs, STROBE for observational studies,
ROB-2 for RCT bias, ROBINS-I for NRSI bias, AMSTAR-2 for SR
quality. Detectors integrate cleanly into the existing
`RigorCheckReport` envelope. Each detector ships with primary-source
PMID anchor (Schulz 2010, Page 2021, von Elm 2007, Sterne 2019,
Sterne 2016, Shea 2017).

### OpenAlex live-discovery lane (13th)

Open scholarly citation graph (PubMed + preprints + conference
proceedings + open citation network). Opt-in via
`--include-openalex` flag on the `discover` subcommand. Source-
health probe added. Offline-safe with injected-fetcher fixtures.

## Constitutional impact

- **§I (Primary-Source Or Refuse)**: deepened — every new registry
  row and every reporting-rigor detector carries a primary PMID.
- **§II (Deterministic-Backbone)**: deepened — each new registry has
  a deterministic topic-keyword detector; each reporting-rigor
  detector is a deterministic regex pair.
- **§III (Test-First)**: enforced — 132 new tests across the four
  registries, reporting-rigor, OpenAlex, registry inventory wiring,
  eval coverage.
- **§IV (Researcher Audience Only)**: unchanged. Driving-impairment
  surfaces are research literature only; per-se law surfaces remain
  in the parent plugin.
- **§V (Safety-Layer Sovereignty)**: unchanged.
- **§VI (Phytochemistry Precision)**: unchanged.
- **§VII (GRADE Honesty)**: deepened by reporting-rigor — flagging
  RCTs without CONSORT, SRs without PRISMA, etc.
- **§VIII (Retractions At Composition)**: unchanged — new rows
  participate in the existing retraction-suppression flow.
- **§IX (Live Discovery)**: deepened by OpenAlex — 13 live sources.
- **§X (Stdlib-Only)**: unchanged — OpenAlex uses urllib with
  injected fetcher.
- **§XI (Citable Output)**: deepened — bibliography export continues
  to work over the v0.6 typed Answer.

No amendment required.

## Industry-expert trust heuristics (verified at demo time)

| Heuristic | v0.5 result | v0.6 result |
|---|---|---|
| Pain: "NASEM 2017 cannabis chronic pain conclusive evidence" | 0 curated claims | ≥ 1 Level A claim citing Whiting 2015 (PMID 26103030) |
| Psychiatry: "high potency cannabis psychosis Di Forti EU-GEI" | 0 curated claims | ≥ 1 Level B claim citing Di Forti 2019 (PMID 30902669) |
| Driving: "cannabis driving impairment Compton 2017 NHTSA" | 0 curated claims | ≥ 1 claim citing Compton 2017 NHTSA (DOT HS 812 411) with adjusted vs unadjusted OR disambiguation |
| PTSD: "Bonn-Miller 2021 PTSD cannabis trial" | 0 curated claims | ≥ 1 Level B claim citing Bonn-Miller 2021 (PMID 33667097) with negative primary endpoint honestly stated |
| Reporting-rigor: "we conducted a randomized trial of CBD in chronic pain" | no detector flags | CONSORT-missing violation flagged (Schulz 2010 BMJ PMID 20335313 anchor) |
| OpenAlex: `--include-openalex` on `discover` | flag does not exist | OpenAlex lane fans out alongside PubMed / ChEMBL / CT.gov |

## v0.7 horizon (deferred)

- NASEM-2017 full chapter mapping (chapter-by-chapter conclusive /
  substantial / moderate / limited evidence-level table). v0.6 ships
  the chapter-4 chronic-pain finding only.
- Cannabinoid medicines regulatory-science registry (Epidiolex
  FDA label, Sativex EMA label, nabilone, dronabinol).
- Pharmacovigilance / FAERS signal-detection methodology surface.
- Hjorthøj vs Marconi attributable-fraction synthesis surface.
- Heterogeneity-meta-analysis literacy (I² / τ² reporting).
