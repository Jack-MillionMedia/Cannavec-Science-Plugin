# v0.5 Industry-Expert Rating Delta

**Companion to**: [`specs/005-clinical-pharmacology-depth/spec.md`](../specs/005-clinical-pharmacology-depth/spec.md)

**Build**: Cannavec Science v0.5 industry-expert-clinical-depth at HEAD of
`claude/exciting-shannon-cMhTQ`

**Date**: 2026-05-24

**Baseline**: v0.4 (1,228 tests / 144 evals (133 offline), 11 registries / 159 rows).

## Headline

> **v0.4 had two strong horizon registries (analytical chemistry,
> cultivation science) but left credible-researcher silence on five
> high-frequency clinical-pharmacology topics. v0.5 lands all five plus
> a twelfth primary-source live lane (Europe PMC) inside the same
> researcher-only audience lock.**

The v0.5 build closes the largest demo silences a credible cannabis-
research scientist hits in v0.4: pharmacokinetics, cannabis use disorder
+ withdrawal-syndrome instruments, cannabinoid hyperemesis syndrome,
eCBome enzyme-inhibitor drug-development translation, and cannabinoid
biosynthesis pathway. It does not broaden the audience lock; it deepens
the researcher surface.

## What v0.4 already did well (preserved)

Every v0.4 deliverable continues to work, regression-protected by the
expanded unit + eval suites:

- Analytical-chemistry registry (≥ 8 rows) surfaces for decarb-kinetics
  / HPLC / GC-MS / chemovar / pyrolysis prompts.
- Cultivation-science registry (≥ 6 rows) surfaces for UV-B / trichome
  / synthase / botanical-taxonomy prompts.
- `Answer.notes` renders as `## Notes` section when present and not a
  refusal.
- Sibling `indica_sativa_as_pharmacology_abstract` banned pattern fires
  on abstract framings; botany framings escape cleanly.
- Registry inventory subcommand emits the 11 v0.4 groups.
- K2/Spice hard-refuse, 16 banned-pattern detectors, span-aware
  `NamedCannabinoidSet`, retraction-at-composition, GRADE wording-vs-
  grade consistency, cannabinoid-scoped registry filtering, seven
  phytochemistry rigor detectors with (detector, span) deduplication —
  all hold.

## New v0.5 deliverables (5 curated registries + 1 live lane)

### N1 (P1) — Clinical pharmacokinetics registry [closed]

A clinical-pharmacology PI asks `THC inhaled vs oral pharmacokinetics
Tmax Cmax`, `CBD epidiolex food effect`, or `11-hydroxy-THC active
metabolite`. v0.4 returned **0 claims** for every PK question.

v0.5: A new `pharmacokinetics.py` module ships **8 curated rows** —
THC inhaled (smoked + vaped) per Huestis 2005 (PMID 16142973) + Spindle
2018, THC oral / dronabinol per Wall 1983 (PMID 6311559), CBD food
effect per Birnbaum 2019 (PMID 31166007), 11-OH-Δ⁹-THC active
metabolite, nabiximols oromucosal per Karschner 2011 (PMID 21240010),
plasma protein binding + adipose distribution per Garrett 1977,
SAMHSA-cutoff urine detection window per Huestis 1996 (PMID 8773290).
Test coverage: 20 unit tests + 6 integration evals.

### N2 (P1) — Cannabis use disorder & withdrawal registry [closed]

An addiction-medicine researcher asks `cannabis use disorder DSM-5
criteria`, `CUDIT-R psychometric properties`, or `cannabis withdrawal
syndrome scale Allsop 2011`. v0.4 returned **0-1 claims** with only
the Volkow 2014 NEJM review surfaced for CUD.

v0.5: A new `use_disorder.py` module ships **6 curated rows** — DSM-5
CUD framework per Hasin 2013 (PMID 23537606), CUDIT-R per Adamson 2010
(PMID 20231083), Cannabis Withdrawal Scale per Allsop 2011 (PMID
21652129), NESARC-III prevalence per Hasin 2015 (PMID 26502112),
twin-study heritability per Verweij 2010 (PMID 20096023), and
adolescent-onset telescoping per Chen 2009 (PMID 19166934). Test
coverage: 19 unit tests + 3 integration evals.

### N3 (P1) — Cannabinoid hyperemesis syndrome registry [closed]

A clinical-toxicology / GI researcher asks `cannabinoid hyperemesis
syndrome diagnostic criteria`. v0.4 returned **0 claims** (only a
static safety caution).

v0.5: A new `hyperemesis_syndrome.py` module ships **4 curated rows**
— diagnostic criteria per Sorensen 2017 SR (PMID 27567272) + Allen
2004 original 9-case series (PMID 15082584) + Simonetto 2012 Mayo
Clinic series (PMID 22305024), Rome IV framework per Venkatesan 2019
(PMID 31480576), topical capsaicin acute-phase treatment per Dezieck
2017 (PMID 28215116), post-legalization Colorado ED epidemiology per
Kim 2018 (PMID 30049481). The static caution remains intact alongside
the new rows. Test coverage: 17 unit tests + 3 integration evals.

### N4 (P2) — eCBome enzyme-inhibitor pharmacology registry [closed]

A drug-development researcher asks `PF-04457845 FAAH inhibitor cannabis
withdrawal NEJM` or `BIA 10-2474 Rennes Phase 1 disaster`. v0.4
surfaced only the static eCBome enzyme reference (FAAH / MAGL) with
**no inhibitor pharmacology claims**.

v0.5: A new `ecbome_inhibitors.py` module ships **5 curated rows** —
PF-04457845 cannabis-withdrawal Phase 2a per D'Souza 2019 (PMID
30985083), PF-04457845 OA-pain Phase 2 per Huggins 2012 (PMID
22910298), BIA 10-2474 Rennes disaster per Kerbrat 2016 (PMID
27806243) **with explicit off-target-serine-hydrolase disambiguation**
per van Esbroeck 2017 (PMID 28912346), MAGL inhibitor ABX-1431 per
Cisar 2018 (PMID 29498523), dual FAAH/MAGL JZL195 per Long 2009
(PMID 19429692). The BIA-10-2474-off-target row is the most important
pedagogical content — every FAAH-inhibitor literature citation MUST
distinguish on-target (PF-04457845-class) from off-target (BIA-class)
chemistry. Test coverage: 20 unit tests + 2 integration evals.

### N5 (P2) — Cannabinoid biosynthesis pathway registry [closed]

A synthetic-biology / plant-secondary-metabolism researcher asks
`olivetolic acid synthase polyketide pathway` or `Luo 2019 yeast
cannabinoid heterologous expression Nature`. v0.4 returned **0
claims**.

v0.5: A new `biosynthesis.py` module ships **5 curated rows** — OLS +
OAC polyketide entry per Taura 2009 (PMID 19429605) + Gagne 2012 (PMID
22802647), CBGAS aromatic prenyltransferase per Page 2011 (PMID
21896800), THCA synthase FAD-dependent oxidocyclase per Sirikantaramas
2004 (PMID 15453749), CBDA synthase per Taura 1996 (PMID 8632416),
Saccharomyces-cerevisiae heterologous expression per Luo 2019 (PMID
30814733). Coexists with the v0.4 cultivation-science chemotype-
inheritance rows (different topics: cultivation = breeder-angle
inheritance; biosynthesis = enzyme mechanism). Test coverage: 18 unit
tests + 2 integration evals.

### N6 (P3) — Europe PMC twelfth primary-source live lane [closed]

A researcher running `discover` on a European-centred query loses
Europe-only-indexed literature that PubMed misses.

v0.5: A new `europepmc_discover.py` module adds Europe PMC as a twelfth
primary-source live-discovery lane (`live_europepmc` provenance tag).
Opt-in via `discover --include-europepmc` or by adding `europepmc` to
`--sources`. Same offline-test contract as every other lane (injected
fetcher, no network calls escape the test suite). Cross-source
synthesis layer counts the new lane. `source-health` probes Europe PMC.
Test coverage: 22 unit tests + 2 integration evals (live category, skipped offline).

## v0.5 acceptance snapshot

| Gate | v0.4 (shipped) | v0.5 (shipped) | Δ |
|---|---|---|---|
| Unit tests | 1,228 | **1,367** | +139 |
| Eval prompts (total) | 144 | **162** | +18 |
| Eval prompts (offline) | 133 | **149** | +16 |
| Curated registries | 11 | **16** | +5 |
| Live discover lanes | 11 | **12** | +1 (europepmc) |
| Curated rows total | 159 | **~187** | +~28 |
| Banned-pattern count | 16 | **16** | 0 (no new safety surface) |
| Version stamp | 0.4.0 | **0.5.0** | +0.1 |
| Slash-command count | 5 | **5** | 0 (no new commands per §IV) |

## Industry-Expert Trust Heuristics — v0.5 results

- **Pharmacokinetics test** — a clinical-pharmacology PI asks
  "11-OH-THC oral dronabinol" — receives the Wall 1983 + Huestis 2005
  PK row with the first-pass-effect explanation for why edibles
  produce a longer / qualitatively-different subjective profile. ✓
- **CUD-instrument test** — an addiction-medicine researcher asks
  "CUDIT-R psychometric properties" — receives the Adamson 2010 8-item
  screening-instrument citation. ✓
- **CWS test** — receives the Allsop 2011 19-item Cannabis Withdrawal
  Scale row with the DSM-5 cannabis-withdrawal criterion mapping. ✓
- **CHS-criteria test** — a GI researcher asks "CHS Rome IV criteria"
  — receives the Sorensen 2017 + Allen 2004 + Venkatesan 2019 row set,
  not the static caution alone. ✓
- **FAAH-disaster test** — a drug-development researcher asks "BIA
  10-2474 Rennes disaster" — receives the Kerbrat 2016 reference
  alongside the van Esbroeck 2017 off-target-serine-hydrolase
  disambiguation. The row's claim text leads with the disambiguation.
  ✓
- **Biosynthesis test** — a synbio researcher asks "olivetolic acid
  synthase Taura 2009" — receives the OLS / OAC pathway claim. ✓
- **Europe PMC test** — `discover --include-europepmc` surfaces the
  Europe PMC lane in the discover output (or the source-unavailable
  marker offline). ✓

## What still does NOT ship (deliberately)

The v0.5 release does not broaden the researcher-only audience lock
(Constitution §IV). The following remain explicitly out-of-scope:

- Multi-audience templates (patient, clinician, cultivator, lab,
  compliance, retail, policy, hemp, microbiome, veterinary).
- KB flywheel / gap detection / proposal generation.
- Signed reproducible artifacts and verification.
- Watchlist + daily digest.
- Persistent expert profiles.
- Per-state US regulatory feasibility (v0.5 advisory is US-federal
  only).
- Hemp-derived intoxicating-cannabinoid state law.
- Industrial-hemp material-science framing.
- CourtListener / legal-discovery integration.
- AlphaFold predicted structures (RCSB experimental only).
- Curator-agent auto-mutation of registry rows on freshness-probe
  results.

These features may exist in the larger Cannavec plugin. They are
explicitly NOT promised by this elite-tier build. Demo-time conflation
between the two products is a constitution violation.

## Constitutional posture

This release is **in-constitution** (no amendment required). The five
new registries are research-grade primary-literature topics that sit
inside §IV (researcher-only). Europe PMC is a twelfth primary-source
live lane operating under the existing §IX contract (provenance tags,
deterministic synthesis verdict, no auto-promotion to curated tier,
offline-safe injected fetcher).
