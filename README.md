# Cannavec Science (v0.6 — research-domain-breadth build)

**A focused Claude Code plugin for elite-tier cannabis-research science.**

The v0.6 build extends the v0.5 industry-expert-clinical-depth backbone
across four research domains every working cannabis-research scientist
asks about, adds a reporting-rigor module, and adds a thirteenth
primary-source live-discovery lane. All shipping inside Constitution
§IV (researcher-only). 1,501 unit tests green at HEAD; 188 eval prompts
(173 offline) across ten buckets; twenty curated science registries
with ≥ 215 total rows; thirteen live-discovery lanes.

### What v0.6 ships

1. **Pain medicine registry (≥ 7 curated rows)** — NASEM 2017
   chapter-4 conclusive-evidence finding for chronic pain anchored
   to Whiting 2015 JAMA SR (PMID 26103030), Stockings 2018 PAIN SR
   (PMID 30121596), Mücke 2018 Cochrane neuropathic (PMID 29513392),
   Boehnke 2019 J Pain prospective MMJ cohort (PMID 31237829),
   Andreae 2015 J Pain IPD meta-analysis (PMID 25840040), and de
   Vita 2018 experimental-pain SR (PMID 30362962). The Mücke vs
   Whiting tone divergence is a teaching example of evidence-base vs
   evidence-interpretation differences.
2. **Cannabis-and-psychosis psychiatry registry (≥ 6 rows)** —
   Di Forti 2019 EU-GEI multinational case-control Lancet Psychiatry
   (PMID 30902669, the high-potency-cannabis daily-use first-episode-
   psychosis study), Marconi 2016 Schizophr Bull dose-response SR
   (PMID 26884547), Vaucher 2018 Mol Psychiatry Mendelian-randomization
   bidirectional-causality analysis (PMID 29039420) WITH explicit
   instrument-validity caveats, Bhattacharyya 2009 Arch Gen Psychiatry
   acute-Δ⁹-THC fMRI healthy-volunteer challenge (PMID 19996036),
   Hjorthøj 2023 Lancet Psychiatry Danish national-register cohort
   (PMID 36402143), and Murray 2017 Lancet Psychiatry narrative
   review.
3. **Driving-impairment science registry (≥ 5 rows)** — Compton 2017
   NHTSA Virginia Beach case-control crash-risk study (DOT HS 812 411,
   the most-cited AND most-mis-cited result in the cannabis-driving
   literature — unadjusted OR ≈ 1.25, adjusted OR ≈ 1.05 after
   demographics + alcohol), Hartman 2015 Clin Chem plasma-Δ⁹-THC
   dose-response (PMID 25371545), Marcotte 2022 JAMA Psychiatry
   driving-simulator dose-and-duration RCT (PMID 35138350, ~1.5 h
   peak impairment / ~5 h return-to-baseline), Brubacher 2022 NEJM
   BC trauma-centre post-legalization cohort (PMID 35081282), and
   Bondallaz 2016 Forensic Sci Int SR (PMID 27082781). The SCIENCE,
   not the LAW — per-se law surfaces remain in the parent plugin
   per Constitution §IV.
4. **PTSD / anxiety / sleep registry (≥ 5 rows)** — Bonn-Miller 2021
   PLOS One PTSD smoked-cannabis cross-over RCT (PMID 33667097)
   surfaces with the **largely-negative primary endpoint honestly
   stated** (no confidence-laundering); Crippa 2011 J Psychopharmacol
   CBD-SAD SPECT acute challenge (PMID 20829306); Bergamaschi 2011
   Neuropsychopharm CBD-SAD public-speaking (PMID 21307846); Bedi
   2010 Drug Alcohol Depend biphasic acute-Δ⁹-THC anxiety dose-
   response (PMID 19897322); and Walsh 2017 Sleep Med Rev cannabinoids-
   and-sleep SR (PMID 28392485) with the 'limited and inconclusive
   evidence' SR verdict honestly stated.
5. **Reporting-rigor module (≥ 6 detectors)** — A §VII GRADE-honesty
   deepening. Detectors flag when prompt text describes a study-design
   class without acknowledging the appropriate EQUATOR-network
   reporting guideline (CONSORT-2010 for RCTs per Schulz 2010 BMJ
   PMID 20335313, PRISMA-2020 for SRs per Page 2021 BMJ PMID
   33781993, STROBE for observational studies per von Elm 2007 PMID
   17938396) or risk-of-bias / quality tool (ROB-2 for RCT bias per
   Sterne 2019 BMJ PMID 31462531, ROBINS-I for non-randomized
   intervention studies per Sterne 2016 BMJ PMID 27733354, AMSTAR-2
   for SR quality per Shea 2017 BMJ PMID 28935701). Detectors
   integrate into the existing `RigorCheckReport` and surface in the
   `rigor` subcommand output. Each detector ships with positive +
   negative unit tests.
6. **OpenAlex live-discovery lane (13th primary source)** — Open
   scholarly citation graph (PubMed + preprints + conference
   proceedings + open citation network). Available via
   `discover --include-openalex` or by adding `openalex` to
   `--sources`. Source-health probe added. Same offline-test
   contract as every other live lane (injected fetcher, no escape
   network calls in the test suite).
7. **Four new registry-inventory groups** — `python3 -m cannavec_science
   registries` now surfaces `pain_medicine`, `psychiatry`,
   `driving_impairment`, and `ptsd_anxiety_sleep`; total inventory
   grows from 16 → 20 curated registries.

### What v0.5 shipped (preserved)

A working cannabis-research scientist needs more than a literature search:
they need primary citations they can defend, phytochemistry precision
they can publish, live access to the frontier (including preprints),
deterministic GRADE-level rigor with field-pushback signal, researcher-
workflow scaffolding (PICO, sample-size power, GRADE evidence-profile
table, IRB protocol skeleton), primary-source-anchored analytical
chemistry and cultivation science, and — new in v0.5 — **clinical
pharmacokinetics** (THC inhaled / oral PK, CBD food effect, 11-OH-Δ⁹-THC
active metabolite, nabiximols oromucosal, distribution, urine detection
window), **cannabis use disorder & withdrawal** (DSM-5 CUD framework,
CUDIT-R, CWS, NESARC-III prevalence, twin-study heritability,
adolescent-onset telescoping), **cannabinoid hyperemesis syndrome**
(Sorensen 2017 / Allen 2004 diagnostic criteria, Rome IV, capsaicin
treatment, post-legalization epidemiology), **eCBome enzyme-inhibitor
pharmacology** (PF-04457845 cannabis-withdrawal Phase 2a, the BIA
10-2474 Rennes disaster *with* off-target-serine-hydrolase
disambiguation, MAGL inhibitor ABX-1431, dual JZL195), and **cannabinoid
biosynthesis pathway** (OLS / OAC polyketide entry, CBGAS
prenyltransferase, THCA / CBDA synthase enzymology, Luo 2019 yeast
heterologous expression). Cannavec Science ships exactly those things —
researcher-only, stdlib-only, deterministic.

This is the **v0.5 industry-expert-clinical-depth build** descending from
the v0.4 industry-expert-depth build (spec 004) and earlier specs. v0.5
lands five new curated registries (≥ 28 new rows total) and a twelfth
primary-source live-discovery lane (Europe PMC, complement to PubMed)
without broadening the researcher-only audience lock. The build is now
**1,360+ unit tests strong** with a 16-prompt clinical-pharmacology-depth
eval bucket on top of the 144-prompt v0.4 battery — **162 prompts total
(149 offline)** in the eval suite.

### What v0.5 ships

1. **Clinical pharmacokinetics registry (≥ 8 curated rows)** — THC
   inhaled (smoked + vaped) PK per Huestis 2005 (PMID 16142973) +
   Spindle 2018, THC oral / dronabinol PK per Wall 1983 (PMID 6311559),
   CBD oral food effect per Birnbaum 2019 (PMID 31166007 — the
   Epidiolex label-supporting 4-5× AUC increase with high-fat meal),
   11-OH-Δ⁹-THC active metabolite (the first-pass-effect explanation
   for why edibles produce a longer / different subjective profile),
   nabiximols oromucosal per Karschner 2011 (PMID 21240010), plasma
   protein binding + adipose sequestration per Garrett 1977, and
   SAMHSA-cutoff urine detection window per Huestis 1996 (PMID 8773290).
2. **Cannabis use disorder & withdrawal registry (≥ 6 curated rows)** —
   DSM-5 CUD framework per Hasin 2013 (PMID 23537606), CUDIT-R
   screening instrument per Adamson 2010 (PMID 20231083), Cannabis
   Withdrawal Scale per Allsop 2011 (PMID 21652129), NESARC-III
   12-month / lifetime prevalence per Hasin 2015 (PMID 26502112),
   twin-study heritability per Verweij 2010 (PMID 20096023), and
   adolescent-onset telescoping per Chen 2009 / Hall & Degenhardt 2009.
3. **Cannabinoid hyperemesis syndrome registry (≥ 4 curated rows)** —
   diagnostic criteria per Sorensen 2017 systematic review (PMID
   27567272) + Allen 2004 original 9-case series (PMID 15082584) +
   Simonetto 2012 Mayo Clinic 98-case series (PMID 22305024), Rome IV
   functional GI framework per Venkatesan 2019 (PMID 31480576),
   topical capsaicin acute-phase treatment per Dezieck 2017 (PMID
   28215116), and post-legalization Colorado ED epidemiology per
   Kim 2018 (PMID 30049481). The existing static CHS caution remains
   intact — the registry adds primary citations alongside it.
4. **eCBome enzyme-inhibitor pharmacology registry (≥ 5 curated rows)**
   — PF-04457845 cannabis-withdrawal Phase 2a per D'Souza 2019 (PMID
   30985083), PF-04457845 osteoarthritis-pain Phase 2 per Huggins 2012
   (PMID 22910298), **BIA 10-2474 Rennes Phase 1 disaster** per Kerbrat
   2016 (PMID 27806243) *with explicit off-target-serine-hydrolase
   disambiguation* per van Esbroeck 2017 (PMID 28912346 — the
   activity-based protein profiling paper proving BIA 10-2474 toxicity
   is OFF-TARGET, not on-target FAAH biology), MAGL inhibitor ABX-1431
   per Cisar 2018 (PMID 29498523), and dual FAAH / MAGL inhibitor
   JZL195 mechanism per Long 2009 (PMID 19429692).
5. **Cannabinoid biosynthesis pathway registry (≥ 5 curated rows)** —
   OLS + OAC polyketide entry per Taura 2009 (PMID 19429605) + Gagne
   2012 (PMID 22802647), CBGAS aromatic prenyltransferase per Page
   2011 (PMID 21896800), THCA synthase FAD-dependent oxidocyclase per
   Sirikantaramas 2004 (PMID 15453749), CBDA synthase per Taura 1996
   (PMID 8632416), and Saccharomyces-cerevisiae heterologous
   expression per Luo 2019 (PMID 30814733).
6. **Europe PMC live-discovery lane (12th primary source)** — Europe
   PMC indexes PubMed PLUS the full PMC corpus PLUS European
   non-MEDLINE-indexed journals. Available via
   `discover --include-europepmc` (opt-in flag) or by adding
   `europepmc` to `--sources`. Same offline-test contract as every
   other live lane (injected fetcher, no escape network calls in the
   test suite).
7. **Five new registry-inventory groups** — `python3 -m cannavec_science
   registries` now surfaces `pharmacokinetics`, `use_disorder`,
   `hyperemesis_syndrome`, `ecbome_inhibitors`, and `biosynthesis`;
   total inventory grows from 159 → ~187 rows across **16** (was 11)
   curated registries.

### What v0.4 shipped (preserved)

1. Analytical-chemistry registry (≥ 8 curated rows) — decarboxylation
   kinetics (Veress 1990 PMID 2384545, Wang 2016, Citti 2018), HPLC
   potency analysis vs GC-MS in-injector decarboxylation artefact (Dussy
   2005, Citti 2018), chemovar Type I/II/III/IV/V classification
   (Hazekamp & Fischedick 2012 PMID 22362625, Lewis 2018), THCA-/CBDA-
   synthase locus inheritance (Hillig & Mahlberg 2004, Aizpurua-Olaizola
   2016), and combustion-vs-vaporisation pyrolysis byproducts
   (Pomahacova 2009, Moir 2008).
2. Cultivation-science registry (≥ 6 curated rows) — UV-B effect on
   cannabinoid biosynthesis (Lydon 1987 PMID 3621052), glandular
   trichome biology (Livingston 2020 PMID 31867754, Tanney 2021),
   THCA-/CBDA-synthase single-locus inheritance (de Meijer 2003 PMID
   12663552), CBDA-synthase enzymology (Taura 2007), F1 heterozygote
   Type II dominance, and the **honest-debate botanical taxonomy** row
   surfacing both Small & Cronquist 1976 (single species) AND Hillig
   2005 (multi-species) without picking a winner.
3. `Answer.notes` rendering fix — v0.3 set the 0-claim classification
   on `Answer.notes` but `Answer.to_markdown()` never surfaced it.
   v0.4 renders a `## Notes` section so the researcher actually sees
   the actionable hint.
4. Strengthened indica/sativa banned pattern catches the abstract
   meta-framing ("indica vs sativa pharmacological differences") while
   leaving botanical-taxonomy framings ("Cannabis sativa L. botanical
   taxonomy") cleanly through.

### What v0.4 ships

1. **Analytical-chemistry registry (≥ 8 curated rows)** — decarboxylation
   kinetics (Veress 1990 PMID 2384545, Wang 2016, Citti 2018), HPLC
   potency analysis vs GC-MS in-injector decarboxylation artefact (Dussy
   2005, Citti 2018), chemovar Type I/II/III/IV/V classification
   (Hazekamp & Fischedick 2012 PMID 22362625, Lewis 2018), THCA-/CBDA-
   synthase locus inheritance (Hillig & Mahlberg 2004, Aizpurua-Olaizola
   2016), and combustion-vs-vaporisation pyrolysis byproducts
   (Pomahacova 2009, Moir 2008). Every row primary-cited per §I; every
   row carries a topic-keyword detector that fires on
   ``decarboxylation``, ``HPLC``, ``GC-MS``, ``chemovar``, ``pyrolysis``,
   etc.
2. **Cultivation-science registry (≥ 6 curated rows)** — UV-B effect
   on cannabinoid biosynthesis (Lydon 1987 PMID 3621052), glandular
   trichome biology (Livingston 2020 PMID 31867754, Tanney 2021),
   THCA-/CBDA-synthase single-locus inheritance (de Meijer 2003 PMID
   12663552), CBDA-synthase enzymology (Taura 2007), F1 heterozygote
   Type II dominance, and the **honest-debate botanical taxonomy** row
   surfacing both Small & Cronquist 1976 (single species) AND Hillig
   2005 (multi-species) without picking a winner — same evidentiary
   honesty Cannavec applies to entourage-effect prompts.
3. **`Answer.notes` rendering fix** — v0.3 set the 0-claim classification
   on `Answer.notes` (spec 003 US9) but `Answer.to_markdown()` never
   surfaced it. v0.4 renders a `## Notes` section so the researcher
   actually sees the actionable hint ("0 curated claims: this question
   is in §IV but sits in the v0.4 horizon — use the `discover`
   subcommand"). `Answer.to_dict()` JSON output now includes a `notes`
   field at top level.
4. **Strengthened indica/sativa banned pattern** — v0.3 caught the prose
   form ("Indica strains are sedating because they have more myrcene")
   but the abstract meta-framing ("indica vs sativa pharmacological
   differences") slipped through. v0.4 adds a sibling pattern
   (`indica_sativa_as_pharmacology_abstract`) that catches the abstract
   framing WITHOUT ensnaring legitimate botanical-taxonomy framings
   ("Cannabis sativa L. botanical taxonomy", "Is Cannabis sativa one
   species or three?" — both pass cleanly into the cultivation-science
   registry).
5. **Two new registry-inventory groups** — `python3 -m cannavec_science
   registries` now surfaces `analytical_chemistry` and
   `cultivation_science` as discoverable groups; total inventory grows
   from 145 → 159 rows across 11 (was 9) registries.

### What v0.3 fixes

1. **Δ⁸-THC pharmacology no longer fires the Δ⁹-THC monograph** —
   span-aware `NamedCannabinoidSet` resolves the prompt's named-isomer
   set BEFORE any registry detector fires (US1 / FR-001).
2. **`HHC safety profile` returns 0 cannabinoid-attributed AE claims**
   instead of 26 unrelated CBD / Δ⁹-THC rows — every AE / interaction
   / contraindication / population detector now accepts a
   `cannabinoid_filter` keyword and `compose_answer` wires the prompt's
   named-isomer set through (US2 / FR-002).
3. **`entourage effect evidence` no longer reports "highest evidence
   grade: Level A"** — the answer-level grade aggregation now respects
   a deterministic topical-relevance signal. Hypothesis-anchored prompts
   require the canonical citations (Russo 2011 / Finlay 2020 /
   Santiago 2019 / LaVigne 2021) to count as topical (US3 / FR-003).
4. **`source-health` no longer crashes with `AttributeError`** —
   the CLI handler reads the actual `SourceHealth` dataclass shape
   (`status`, `latency_ms`, `error_excerpt`) plus a new `--json`
   structured output (US4 / FR-004).
5. **`verify` accepts all five Constitution §I identifier shapes** —
   PMID, DOI, NCT, ChEMBL, and UniProt resolvers, each with the
   established offline-injected-fetcher contract per Constitution §III
   (US5 / FR-005).
6. **`cannabis × tacrolimus` now matches the CBD-tacrolimus row** —
   the noun "cannabis" / "marijuana" / "marihuana" / "weed" expands to
   the cannabinoid set {CBD, Δ⁹-THC, CBN, CBG, THCV} for partner-drug
   matching (US6 / FR-006).
7. **`anandamide FAAH inhibition` now surfaces the eCBome registry** —
   `compose_answer` imports `cannavec_science.ecbome` and attaches
   eCBome entries when the prompt names a mediator / receptor / enzyme
   / transporter (US7 / FR-007).
8. **`python3 -m cannavec_science registries` lists every covered
   cannabinoid / terpene / interaction-partner / AE / contraindication
   / PGx allele / eCBome entry** — markdown + `--format json` (US8 /
   FR-008).
9. **0-claim answers carry a discriminated-union classification** —
   refusal / out-of-scope-audience / out-of-scope-deferred /
   in-scope-uncurated / in-scope-phrasing-mismatched, with an
   actionable hint pointing the user at `discover` or the parent
   plugin (US9 / FR-009).
10. **The rigor report deduplicates violations by (detector, span)** —
    one (terpene, cannabinoid) pair in one sentence fires one
    violation, not two (US10 / FR-010).

## What ships

- **Five slash commands.** No more, no less. v0.2 / v0.3 add new
  functionality through flags + Python-module subcommands, never a
  sixth slash command (Constitution §IV).
- **Span-aware `NamedCannabinoidSet` (v0.3)** — every prompt's named-
  isomer set is resolved deterministically before any registry detector
  fires. The Δ⁸-THC / HHC / THCO / THCP / THCV / CBDV / CBC / CBN / CBG
  / THCA / CBDA branches no longer collapse into the Δ⁹-THC monograph.
- **Cannabinoid-scoped registry detectors (v0.3)** — AE, interaction,
  contraindication, and population detectors accept a `cannabinoid_filter`
  parameter; `compose_answer` wires the prompt's named-isomer set
  through so a CBD safety query never surfaces Δ⁹-THC AE rows.
- **Topical-relevance grade aggregation (v0.3)** — `EvidenceSummary.
  highest_grade` is computed over topically-relevant claims only.
  Hypothesis-anchored prompts like "entourage effect evidence" require
  the canonical citations to count as topical.
- **Five-shape `verify` resolver (v0.3)** — PMID, DOI, NCT, ChEMBL,
  and UniProt, with the established offline-injected-fetcher contract.
- **`registries` subcommand (v0.3)** — list every curated row, grouped
  by registry, with row counts, last-verified dates, and entry labels.
  Markdown + `--format json`.
- **Eight curated science registries** — major + minor cannabinoids
  (including Δ⁸-THC, HHC, THCO, THCP at v0.2 elite depth), terpenes,
  drug interactions, adverse events, populations, contraindications,
  pharmacogenomics. Every row PubMed-cited, every row freshness-tracked
  via the v0.2 ``watch_pmids`` field.
- **Seven phytochemistry rigor detectors** — isomer collapse,
  receptor-without-ID, dose-without-route, THCA-vs-THC conflation,
  matrix-unit confusion, decarb-context-missing, and the **v0.2
  entourage-overclaim detector** (synergy claims without canonical
  citation).
- **15-pattern banned-pattern detector** with a 30-char negation
  guard — catches indica/sativa-as-pharmacology, cultivar-as-effect,
  marketing ratios, "natural therefore safe," "cure" claims, etc.
- **Safety preflight** — refuse-harmful / refuse-individualized /
  add-caution / proceed. K2/Spice synthesis is hard-refused.
- **Retraction enforcement at composition time** — a retracted PMID
  is suppressed from the answer's claims (not just flagged post-hoc).
- **Registry-freshness probe (v0.2)** — every registry row carries
  ``last_verified`` + ``watch_pmids``; the ``freshness`` subcommand
  walks the registries and surfaces retractions / EOCs / stale dates
  without auto-mutating curated rows.
- **Live discovery across eleven primary sources** — PubMed, ChEMBL,
  ClinicalTrials.gov, PubChem, PharmGKB, RCSB PDB, Open Targets, GWAS
  Catalog, BindingDB plus the **v0.2 preprint lanes** bioRxiv and
  medRxiv (Level D cap, ``live_biorxiv`` / ``live_medrxiv`` provenance,
  published-version Crossref cross-reference).
- **Deterministic cross-source synthesis** — STRONG / MIXED / WEAK /
  NONE convergence verdict across the eleven sources, with the
  per-source distinct-supporters count and one-line disagreement
  description.
- **Citation-network field-pushback (v0.2 US4)** — ``verify <PMID>``
  fetches the forward-citation set via NCBI elink, applies the
  deterministic ``pubmed_sentiment`` classifier per-cite, and flips
  ``inconsistency_serious=True`` in the GRADE adapter on refute-heavy
  pushback — producing a deterministic one-level downgrade.
- **Researcher-workflow scaffolders (v0.2 US2)** — ``--pico``,
  ``--power-calc``, ``--grade-profile``, ``--protocol-skeleton`` flags
  on the ``answer`` command. PICO frame, stdlib-only sample-size
  estimator (Cohen 1988 continuous + Fleiss 1981 proportion +
  Fleiss-Tytun-Ury continuity correction + odds-ratio path), GRADE
  evidence-profile table (Markdown / CSV), 9-section IRB protocol
  skeleton with auto-generation watermark.
- **Regulatory-feasibility advisory (v0.2 US6)** — per-jurisdiction
  matrix (US-federal / EU-EMA / Canada / UK-MHRA) × per-cannabinoid;
  watermark on every output (``This is not legal advice; consult
  your institutional research-compliance office.``).
- **Endocannabinoidome reference (v0.2 US6)** — 28-entry eCBome
  (mediators / receptors / enzymes / transporters), every entry with
  a primary UniProt or HMDB identifier.
- **Bibliography export to BibTeX / RIS / CSL-JSON** with inline
  GRADE annotation. Drop straight into Zotero / Mendeley / EndNote.
- **115-prompt eval suite (v0.2 US3)** — six category buckets
  (curated / rigor-positive / rigor-negative / refusal / live /
  cross-cutting) with bucket-minimum enforcement at unit-test time
  AND at runner time. Regression battery dense enough to catch drift
  on any backbone change.

## What does NOT ship (deliberately)

Per the [Constitution §IV](.specify/memory/constitution.md), the v0.2
build is researcher-only. The following exist in the parent Cannavec
plugin and remain **out of scope** past v0.2:

- Patient, clinician, cultivator, lab, compliance, retail,
  public-health, operator, policy, product, hemp, microbiome,
  veterinary surfaces.
- KB flywheel, gap detection, BM25 search, proposal generation.
- Signed artifacts, watchlists, persistent expert profiles.
- Per-state US regulatory feasibility (v0.2 advisory is US-federal
  only; per-state law lives in the parent plugin).
- Per-state hemp-derived cannabinoid law, pesticide registry.
- CourtListener / legal discovery.
- AlphaFold predicted structures (RCSB experimental only).
- Curator-agent auto-mutation of registry rows on freshness probe
  results — the probe surfaces gaps; the curator updates manually.

We did not ship them so we could ship the core exceptionally well.

## 30-second quickstart

```bash
git clone https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin
cd Cannavec-Science-Plugin

# That's it. No `pip install`. Stdlib only.

# Smoke test:
python3 -m unittest discover -s tests   # 1,360+ tests, ~2-3 s
python3 evals/run_evals.py              # 149 offline canonical evals (162 total; 13 live skipped offline)

# The four golden v0.1 flows:
python3 -m cannavec_science answer "What is the evidence for CBD in Dravet syndrome?"
python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01
python3 -m cannavec_science verify 28538134
python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC and the dose was 10 mg"

# v0.2 elite-tier flows:
python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --pico --power-calc --grade-profile --protocol-skeleton
python3 -m cannavec_science answer "Can I study Δ⁹-THC in rats?" \
    --regulatory-feasibility us
python3 -m cannavec_science discover "CB2 microglia" --sources biorxiv,medrxiv --max 5
python3 -m cannavec_science verify 28538134                     # auto-adds citation_network block
python3 -m cannavec_science freshness --registry interactions   # offline retraction-watch probe
python3 -m cannavec_science rigor "myrcene potentiates THC sedation"   # entourage-overclaim detector

# v0.3 routing-and-surfacing flows:
python3 -m cannavec_science answer "Δ⁸-THC pharmacology and safety"  # no Δ⁹-THC monograph
python3 -m cannavec_science answer "HHC safety profile"              # 0 spurious CBD/THC AE claims
python3 -m cannavec_science answer "entourage effect evidence"       # highest grade: Unsupported
python3 -m cannavec_science answer "cannabis interaction with tacrolimus"  # CBD-tacrolimus row fires
python3 -m cannavec_science answer "anandamide FAAH inhibition"      # eCBome reference surfaces
python3 -m cannavec_science verify NCT02224560                       # ClinicalTrials.gov resolver
python3 -m cannavec_science verify CHEMBL5803                        # ChEMBL compound resolver
python3 -m cannavec_science verify P21554                            # UniProt CB1 resolver
python3 -m cannavec_science registries                               # full registry inventory
python3 -m cannavec_science source-health --json                     # no-AttributeError + JSON

# v0.4 industry-expert-depth flows:
python3 -m cannavec_science answer "Decarboxylation kinetics of THCA at 110 degrees C"  # Veress 1990 + Wang 2016
python3 -m cannavec_science answer "HPLC vs GC-MS cannabinoid quantitation"             # GC in-injector artefact row
python3 -m cannavec_science answer "Type II chemovar genetic basis"                     # Hazekamp & Fischedick 2012
python3 -m cannavec_science answer "Cannabis vapor pyrolysis byproducts"                # Pomahacova 2009
python3 -m cannavec_science answer "UV-B effect on cannabinoid biosynthesis"            # Lydon 1987
python3 -m cannavec_science answer "THCA synthase CBDA synthase chemotype inheritance"  # de Meijer 2003
python3 -m cannavec_science answer "Is Cannabis sativa one species or three?"           # honest taxonomy debate
python3 -m cannavec_science answer "Bedrocan medical cannabis cultivars THC content"    # rendered audience hint
python3 -m cannavec_science answer "indica vs sativa pharmacological differences"       # strengthened refusal
python3 -m cannavec_science registries --registry analytical_chemistry                  # 8 analytical rows
python3 -m cannavec_science registries --registry cultivation_science                   # 6 cultivation rows

# v0.5 industry-expert-clinical-depth flows:
python3 -m cannavec_science answer "THC inhaled vs oral pharmacokinetics Tmax Cmax"                # Huestis 2005 + Wall 1983
python3 -m cannavec_science answer "CBD epidiolex food effect AUC fivefold high fat meal"          # Birnbaum 2019
python3 -m cannavec_science answer "11-hydroxy-THC active metabolite oral dronabinol"              # first-pass effect
python3 -m cannavec_science answer "cannabis use disorder DSM-5 criteria framework"                # Hasin 2013
python3 -m cannavec_science answer "CUDIT-R cannabis use disorder identification test"             # Adamson 2010
python3 -m cannavec_science answer "cannabis withdrawal syndrome scale Allsop 2011"                # CWS 19-item
python3 -m cannavec_science answer "cannabinoid hyperemesis syndrome diagnostic criteria"          # Sorensen 2017 SR
python3 -m cannavec_science answer "capsaicin cream cannabinoid hyperemesis treatment"             # Dezieck 2017
python3 -m cannavec_science answer "PF-04457845 FAAH inhibitor cannabis withdrawal NEJM"           # D'Souza 2019
python3 -m cannavec_science answer "BIA 10-2474 Rennes Phase 1 disaster"                           # off-target disambiguation
python3 -m cannavec_science answer "MAGL inhibitor ABX-1431 lorcaserin"                            # Cisar 2018
python3 -m cannavec_science answer "olivetolic acid synthase polyketide pathway biosynthesis"      # Taura 2009 OLS+OAC
python3 -m cannavec_science answer "Luo 2019 yeast cannabinoid heterologous expression Nature"     # synbio platform
python3 -m cannavec_science answer "THCA synthase enzymology FAD-dependent oxidocyclase"           # Sirikantaramas 2004
python3 -m cannavec_science discover "nabiximols European approval" --include-europepmc            # twelfth live lane
python3 -m cannavec_science registries --registry pharmacokinetics                                 # 8 PK rows
python3 -m cannavec_science registries --registry use_disorder                                     # 6 CUD/CWS rows
python3 -m cannavec_science registries --registry hyperemesis_syndrome                             # 4 CHS rows
python3 -m cannavec_science registries --registry ecbome_inhibitors                                # 5 eCBome-inhibitor rows
python3 -m cannavec_science registries --registry biosynthesis                                     # 5 biosynthesis rows
```

## The five commands

| Command | What it does |
|---|---|
| `/cannavec-science:research <question>` | Full researcher brief — GRADE-graded claims, primary citations, monograph sections, evidence synthesis, rigor pass. v0.2 adds opt-in `--pico --power-calc --grade-profile --protocol-skeleton --regulatory-feasibility` flags. |
| `/cannavec-science:ask <question>` | Fast Q&A — same composer, slimmer rendering. |
| `/cannavec-science:discover <query>` | Live multi-source fan-out across eleven primary sources (PubMed + ChEMBL + CT.gov + PubChem + PharmGKB + RCSB + Open Targets + GWAS + BindingDB + v0.2 bioRxiv + v0.2 medRxiv) with cross-source synthesis verdict. |
| `/cannavec-science:verify <PMID\|DOI>` | Single-identifier spot-check with retraction status. v0.2 auto-fetches forward-citation network + field-pushback signal. |
| `/cannavec-science:rigor <text>` | Run the seven phytochemistry rigor detectors (incl. v0.2 entourage-overclaim) + banned-pattern detector on arbitrary text. |

## The deterministic backbone (v0.2)

```
cannavec_science/
├── evidence.py             # GRADE, Source, Claim, ClaimType, source-authority weight
├── banned_patterns.py      # 15 patterns + 30-char negation guard
├── safety.py               # Refuse-harmful / refuse-individualized / proceed verdict
├── rigor_checks.py         # Seven phytochemistry detectors (incl. v0.2 entourage)
├── retraction.py           # Retraction registry + composition-time enforcement
├── pubmed_verify.py        # E-utilities + Crossref verifier (stdlib urllib)
├── pubmed_search.py        # Live PubMed search
├── chembl_discover.py      # Live ChEMBL bioactivity
├── ctgov_discover.py       # Live ClinicalTrials.gov
├── pubchem_discover.py     # Live PubChem compound structure
├── pharmgkb_discover.py    # Live PharmGKB pharmacogenomics
├── rcsb_discover.py        # Live RCSB PDB structural biology
├── opentargets_discover.py # Live Open Targets gene-disease evidence
├── gwas_discover.py        # Live GWAS Catalog SNP-trait associations
├── bindingdb_discover.py   # Live BindingDB measured binding affinities
├── biorxiv_discover.py     # v0.2 — live bioRxiv preprint lane
├── medrxiv_discover.py     # v0.2 — live medRxiv preprint lane
├── _preprint_helpers.py    # v0.2 — shared DOI/version/Crossref helpers
├── discover_guard.py       # Safety guard on live queries
├── synthesis.py            # Cross-source synthesis verdict
├── source_health.py        # Per-source liveness probe
├── intent.py               # Intent classifier
├── uncertainty.py          # GRADE wording-vs-grade verb picker
├── answer.py               # Typed Answer + compose_answer + scaffolder threading
├── evidence_synthesis.py   # Deterministic claim-set rollup
├── bibliography.py         # BibTeX / RIS / CSL-JSON exporter
├── contradiction.py        # Pairwise claim contradiction detector
├── citation_network.py     # v0.2 — NCBI elink forward-cite + pushback signal
├── freshness.py            # v0.2 — registry watch_pmids probe
├── pico.py                 # v0.2 — PICO frame composer
├── power_calc.py           # v0.2 — stdlib sample-size estimator (Cohen + Fleiss)
├── grade_profile.py        # v0.2 — GRADE evidence-profile table (MD + CSV)
├── protocol_skeleton.py    # v0.2 — 9-section IRB protocol stub
├── ecbome.py               # v0.2 — endocannabinoidome reference (28 entries)
├── regulatory_feasibility.py  # v0.2 — US/EU/CA/UK regulatory advisory
├── analytical_chemistry.py # v0.4 — decarb kinetics, HPLC/GC-MS, chemovar, pyrolysis
├── cultivation_science.py  # v0.4 — UV-B, trichome, synthase, taxonomy
├── major_cannabinoids.py   # Δ⁹-THC, CBD
├── minor_cannabinoids.py   # THCV, CBDV, CBC, CBN, CBG + v0.2 Δ⁸-THC, HHC, THCO, THCP
├── terpenes.py             # Terpene registry
├── terpene_reference.py    # Terpene analytical chemistry
├── interactions.py         # 35-row drug-interaction registry
├── adverse_events.py       # AE registry
├── populations.py          # Trial-supported populations
├── contraindications.py    # Contraindication registry
└── pharmacogenomics.py     # CYP2C9 / CYP3A4 / CYP2C19 PGx
```

## Tests + acceptance gate

```bash
python3 -m unittest discover -s tests   # 1,220+ tests, offline, ~2 s
python3 evals/run_evals.py              # 133 offline canonical evals (144 total; 11 live skipped offline)
```

Before any push to the v0.2 branch, all of the following MUST hold
(per [`specs/002-elite-development/plan.md`](specs/002-elite-development/plan.md)):

- `python3 -m unittest discover -s tests` exits 0 in ≤ 60 seconds.
- Total test count ≥ 1,000.
- `python3 evals/run_evals.py` exits 0 with ≥ 100 prompts across six
  buckets, each at or above its minimum.
- `python3 -m cannavec_science answer "CBD Dravet syndrome" --pico --power-calc --grade-profile --protocol-skeleton`
  returns one composed answer with all four scaffolds present.
- `python3 -m cannavec_science discover "CB2 microglia" --sources biorxiv,medrxiv --max 5`
  returns preprint rows tagged `live_biorxiv` / `live_medrxiv` with Level D cap.
- `python3 -m cannavec_science verify 28538134` returns the
  Devinsky-2017 record with `retraction_status: clean` plus a
  citation-network block (or `--no-citation-network` to suppress).
- `python3 -m cannavec_science freshness --registry interactions`
  returns a per-row status table without mutating registry rows.
- `python3 -m cannavec_science rigor "myrcene potentiates THC's sedative effect"`
  fires both `isomer_collapse` AND the new `entourage_overclaim` detector.
- The total slash-command count remains exactly **five**.
- Total Python LOC under `cannavec_science/` stays under **25,000**.

## Constitutional principles

This MVP is governed by 11 principles
([`.specify/memory/constitution.md`](.specify/memory/constitution.md)):

1. **Primary-source or refuse.**
2. **Deterministic backbone over prose.**
3. **Test-first (non-negotiable).**
4. **Researcher audience only (MVP scope lock).**
5. **Safety-layer sovereignty.**
6. **Phytochemistry precision is non-negotiable.**
7. **GRADE honesty over confidence-laundering.**
8. **Retractions are enforced at composition, not post-hoc.**
9. **Read-time discovery is as important as write-time checking.**
10. **Stdlib-only until proven insufficient.**
11. **Citable output is the default.**

The full text lives in `.specify/memory/constitution.md`. Amendments
require the same spec → plan → tasks → implement workflow as a feature.

## License

MIT. See [`LICENSE`](LICENSE).
