# Feature Specification: Clinical-Pharmacology Depth Release (v0.5)

**Feature Branch**: `claude/exciting-shannon-cMhTQ`

**Created**: 2026-05-24

**Status**: Approved for `/speckit-plan` and immediate implementation

**Input**: User request: "continue developing this claude plugin to be
elite for credible/expert cannabis research. Use spec-kit."

## Background

Spec 004 shipped the v0.4 industry-expert-depth release: analytical-
chemistry (8 rows), cultivation-science (6 rows), the `Answer.notes`
render closure, and the abstract indica/sativa-as-pharmacology sibling
banned pattern. The v0.4 surface is green at 1,228 unit tests and 133/133
offline evals.

A third-pass industry-expert review of v0.4 — done at the head of
`claude/exciting-shannon-cMhTQ` — found **five new content gaps a
credible cannabis-research scientist hits inside Constitution §IV
(researcher-only)**, plus one live-discovery widening:

- **N1 (P1, content-gap)** — A clinical-pharmacology PI asks
  `THC inhaled vs oral pharmacokinetics Tmax Cmax`, `CBD epidiolex food
  effect AUC fivefold high fat meal`, or `11-hydroxy-THC active
  metabolite half-life`. v0.4 returns 0 curated claims for every one.
  No pharmacokinetics registry exists; the major-cannabinoid monograph
  carries receptor-binding and clinical-efficacy depth but no
  systematic ADME / PK depth. This is the single largest demo-time
  silence an industry-expert reviewer hits in v0.4.
- **N2 (P1, content-gap)** — An addiction-medicine researcher asks
  `cannabis use disorder DSM-5 criteria` (gets the Volkow 2014 NEJM
  review only — no DSM-5 framework citation, no CUDIT-R, no Cannabis
  Withdrawal Scale) or `cannabis withdrawal syndrome assessment scale`
  (gets 0 curated claims, only a `discover` hint). The DSM-5 CUD
  criteria, CUDIT-R (Adamson 2010 PMID 20231083), and the Cannabis
  Withdrawal Scale (Allsop 2011 PMID 21652129) are the field-standard
  instruments — every withdrawal-trial protocol cites them. Their
  absence is a credibility hit.
- **N3 (P1, content-gap)** — A clinical-toxicology / GI researcher asks
  `cannabinoid hyperemesis syndrome diagnostic criteria` or `Rome IV
  criteria`. v0.4 returns 0 curated claims (only the static caution
  "Cannabis hyperemesis syndrome is paradoxical and requires cessation,
  not adjustment of cannabis use" — useful to the clinician audience,
  uncited to the researcher). The Sorensen 2017 systematic review
  (PMID 27567272), Allen 2004 case-series (PMID 15082584), Simonetto
  2012 Mayo Clinic case-series (PMID 22305024), and Rome IV functional
  GI criteria (Stanghellini 2016) are well-established primary
  literature.
- **N4 (P2, content-gap on existing surface)** — The v0.3 eCBome
  registry surfaces FAAH / MAGL enzyme reference rows but no curated
  inhibitor-pharmacology claims. A researcher asks
  `PF-04457845 FAAH inhibitor cannabis withdrawal NEJM` or
  `MAGL inhibitor ABX-1431 GABA tone` and gets the static reference
  table — no D'Souza 2019 PF-04457845 cannabis-withdrawal trial (PMID
  30985083), no Kerbrat 2016 BIA 10-2474 disaster reference (PMID
  27806243), no Cisar 2018 ABX-1431 MAGL paper (PMID 29498523). This
  is the most important pharmacological story in eCBome — drug-
  development translation — and v0.4 omits it.
- **N5 (P2, content-gap)** — A synthetic-biology researcher asks
  `olivetolic acid synthase polyketide pathway biosynthesis` or
  `THCA synthase enzymology Sirikantaramas 2004`. v0.4 returns 0
  curated claims. The cannabinoid biosynthesis pathway — olivetol
  synthase + olivetolic acid cyclase (Taura 2009 PMID 19429605; Gagne
  2012 PMID 22802647), prenyltransferase CBGAS (Page 2011 PMID
  21896800), THCA synthase (Sirikantaramas 2004 PMID 15453749), CBDA
  synthase (Taura 1996 PMID 8632416), Luo 2019 yeast heterologous
  expression Nature paper (PMID 30814733) — is canonical primary
  literature. Its absence makes Cannavec Science feel like a clinical
  tool only, not a comprehensive research tool.
- **N6 (P3, live-discovery widening)** — Live discovery covers 11
  primary scientific sources but omits **Europe PMC**, which indexes
  PubMed *plus* PubMed Central full-text *plus* European
  non-MEDLINE-indexed journals (e.g. some MDPI / Wellcome / European
  Cannabinoid Research Society proceedings). A researcher running
  `discover` for a European-centred topic (e.g. `nabiximols European
  approval cannabinoid medicine`) currently misses European-indexed
  literature PubMed does not pick up.

This spec **bundles five new curated registries (N1-N5) with one new
live-discovery lane (N6)**, plus the surrounding eval / docs /
version-bump work to ship v0.5 cleanly. Every story stays inside
Constitution §IV. No amendment required — research-grade clinical
pharmacology depth, addiction-medicine instruments, GI-syndrome
diagnostic criteria, eCBome inhibitor translation, biosynthesis enzymology,
and a sixth-tier live source are all explicitly research-grade primary-
literature topics inside the existing audience scope-lock.

## What v0.4 Already Does Well (preserve in v0.5)

These are the surfaces v0.5 MUST NOT regress. Every regression is a
constitution violation:

1. All v0.3 surfaces (US1-US10 + the v0.2 / v0.1 backbone).
2. Analytical-chemistry registry (≥ 8 rows) surfaces for decarb-kinetics
   / HPLC / GC-MS / chemovar / pyrolysis prompts (spec 004 US1).
3. Cultivation-science registry (≥ 6 rows) surfaces for UV-B / trichome
   / synthase / botanical-taxonomy prompts (spec 004 US2).
4. `Answer.notes` renders as a trailing `## Notes` section when present
   and the answer is not a refusal (spec 004 US3).
5. The sibling `indica_sativa_as_pharmacology_abstract` banned pattern
   fires on abstract framings AND botany prompts (`Cannabis sativa L.`,
   `botanical taxonomy`, `species debate`) escape cleanly (spec 004 US4).
6. Registry inventory subcommand emits the 11 v0.4 groups (spec 004 US5).
7. K2/Spice hard-refuse, 16 banned-pattern detectors, span-aware
   `NamedCannabinoidSet`, retraction-at-composition, GRADE wording-vs-
   grade consistency, cannabinoid-scoped registry filtering, seven
   phytochemistry rigor detectors with (detector, span) deduplication.

## Review Methodology (v0.4 third pass)

Same shape as spec 003 / 004: every test is a `python3 -m
cannavec_science <cmd>` invocation against HEAD of
`claude/exciting-shannon-cMhTQ`. Findings are P1 / P2 / P3 by severity.
Findings either point to a new shipping content gap (N-prefix) or
restate a v0.5 horizon item.

### Findings transcript

```
$ python3 -m cannavec_science answer "THC inhaled vs oral pharmacokinetics Tmax Cmax"
**Q:** THC inhaled vs oral pharmacokinetics Tmax Cmax
## Evidence summary
- Highest evidence grade across claims: **Unsupported**
- Claims: 0
- Claims with primary source: 0
## Major cannabinoid monograph — THC
[receptor-binding monograph but no ADME / PK section]
```

```
$ python3 -m cannavec_science answer "cannabis use disorder DSM-5 criteria"
**Q:** cannabis use disorder DSM-5 criteria
## Evidence summary
- Claims: 1  (Volkow 2014 NEJM review only — no DSM-5 framework, no CUDIT-R)
```

```
$ python3 -m cannavec_science answer "cannabinoid hyperemesis syndrome diagnostic criteria"
**Q:** cannabinoid hyperemesis syndrome diagnostic criteria
## Evidence summary
- Claims: 0  (static caution only; no Sorensen 2017 / Allen 2004 citation)
```

```
$ python3 -m cannavec_science answer "PF-04457845 FAAH inhibitor cannabis withdrawal NEJM"
**Q:** PF-04457845 FAAH inhibitor cannabis withdrawal NEJM
## Evidence summary
- Claims: 0  (FAAH static reference only; no D'Souza 2019, no BIA 10-2474)
```

```
$ python3 -m cannavec_science answer "olivetolic acid synthase polyketide pathway biosynthesis"
**Q:** olivetolic acid synthase polyketide pathway biosynthesis
## Evidence summary
- Claims: 0
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Clinical pharmacokinetics registry (Priority: P1, finding N1)

A clinical-pharmacology PI asks `THC inhaled vs oral pharmacokinetics
Tmax Cmax`, `CBD epidiolex food effect AUC fivefold high fat meal`,
`11-hydroxy-THC active metabolite half-life`, or `nabiximols oromucosal
absorption`. v0.4 returns 0 claims for every one — no pharmacokinetics
registry exists. The single largest demo silence in v0.4.

**Why this priority**: P1. Pharmacokinetics is the entry door for any
clinical-pharmacology or formulation question. A researcher who asks
`THC oral bioavailability` and gets silence will not trust the tool for
the deeper questions either. The Huestis 2005 (PMID 16142973), Karschner
2011 (PMID 21240010), Birnbaum 2019 (PMID 31166007), and Wall 1983
(PMID 6311559) primary literature anchor the field; their absence is
a credibility hit.

**Independent Test**: A new `pharmacokinetics.py` module with at least
8 registry rows covering THC inhaled PK, THC oral PK, CBD oral PK, CBD
food effect, 11-OH-THC active-metabolite PK, nabiximols oromucosal PK,
plasma protein binding & lipid sequestration, and metabolite urine
window for cannabis-positivity testing. Each row carries primary PMID
/ DOI citation per §I, a `to_claim()`, and ≥ 1 positive + 1 negative
unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("THC inhaled vs oral pharmacokinetics
   Tmax Cmax")`, **When** the pharmacokinetics registry is in place,
   **Then** ≥ 2 Level C / Level D claims are emitted including the
   inhaled-route claim (Huestis 2005 PMID 16142973) and the oral-route
   claim (Wall 1983 PMID 6311559).
2. **Given** `compose_answer("CBD epidiolex food effect AUC fivefold
   high fat meal")`, **When** the registry is in place, **Then** the
   Birnbaum 2019 (PMID 31166007) food-effect claim is surfaced —
   highest_grade ≥ Level C, NOT Unsupported.
3. **Given** `compose_answer("11-hydroxy-THC active metabolite oral
   dronabinol")`, **When** the registry is in place, **Then** the
   11-OH-THC active-metabolite ratio claim (Wall 1983 PMID 6311559)
   is surfaced, mentioning that oral THC produces 11-OH-THC at ~equimolar
   AUC ratio whereas inhaled THC produces it at ~10% AUC ratio (the
   first-pass-effect explanation for why edibles produce a different
   subjective profile from smoked cannabis).
4. **Given** `compose_answer("nabiximols Sativex oromucosal PK")`,
   **When** the registry is in place, **Then** the Karschner 2011
   (PMID 21240010) nabiximols oromucosal absorption claim is surfaced.

---

### User Story 2 — Cannabis use disorder & withdrawal syndrome registry (Priority: P1, finding N2)

An addiction-medicine researcher asks `cannabis use disorder DSM-5
criteria`, `CUDIT-R psychometric properties Adamson 2010`, `cannabis
withdrawal syndrome scale Allsop 2011`, or `cannabis withdrawal
prevalence heritability twin`. v0.4 returns 0-1 claims for most and the
DSM-5 framework, CUDIT-R, and CWS instruments are entirely missing.

**Why this priority**: P1. CUD and CWS are the field-standard outcome
measures for every cannabis-cessation, withdrawal-pharmacotherapy, or
treatment-as-prevention trial. Their absence is the difference between
"helps me read a paper" and "actually unusable for my IRB protocol".

**Independent Test**: A new `use_disorder.py` module with ≥ 6 registry
rows covering DSM-5 CUD criteria (Hasin 2013 PMID 23537606), CUDIT-R
(Adamson 2010 PMID 20231083), Cannabis Withdrawal Scale (Allsop 2011
PMID 21652129), CUD lifetime / 12-month prevalence (Hasin 2015 JAMA
Psychiatry PMID 26502112), CUD heritability twin estimate (Verweij 2010
PMID 20096023), and CUD telescoping / age-of-onset effect (Chen 2009
PMID 19166934). Each row carries primary PMID per §I and ≥ 1 positive
+ 1 negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("cannabis use disorder DSM-5 criteria")`,
   **When** the registry is in place, **Then** the Hasin 2013 (PMID
   23537606) DSM-5 framework citation is surfaced at ≥ Level C with the
   11-criterion threshold structure (≥ 2 of 11 = mild; ≥ 4 = moderate;
   ≥ 6 = severe).
2. **Given** `compose_answer("CUDIT-R cannabis use disorder identification
   test")`, **When** the registry is in place, **Then** the Adamson 2010
   (PMID 20231083) CUDIT-R 8-item screening instrument is surfaced.
3. **Given** `compose_answer("cannabis withdrawal syndrome assessment
   scale")`, **When** the registry is in place, **Then** the Allsop 2011
   (PMID 21652129) Cannabis Withdrawal Scale (CWS) 19-item instrument
   is surfaced.
4. **Given** `compose_answer("cannabis use disorder prevalence
   adolescent-onset")`, **When** the registry is in place, **Then** the
   Hasin 2015 (PMID 26502112) NESARC-III lifetime / 12-month prevalence
   claim is surfaced along with the existing Volkow 2014 NEJM review row.

---

### User Story 3 — Cannabinoid hyperemesis syndrome registry (Priority: P1, finding N3)

A clinical-toxicology / GI researcher asks `cannabinoid hyperemesis
syndrome diagnostic criteria`, `CHS Rome IV functional GI criteria`,
`capsaicin cream treatment cannabinoid hyperemesis`, or `cyclic
vomiting differential cannabinoid`. v0.4 returns 0 curated claims for
every one — only the static caution renders.

**Why this priority**: P1. CHS is one of the most-asked cannabis-
medicine questions because emergency-department case-load has risen
sharply with legalization. The Sorensen 2017 systematic review (PMID
27567272), Allen 2004 (PMID 15082584), and Simonetto 2012 Mayo Clinic
(PMID 22305024) primary literature is well-established; the Dezieck
2017 capsaicin treatment paper (PMID 28215116) is a key clinical
intervention reference.

**Independent Test**: A new `hyperemesis_syndrome.py` module with ≥ 4
registry rows covering diagnostic criteria (Sorensen 2017 + Allen 2004),
Rome IV functional GI criteria (Venkatesan 2019 PMID 31480576), capsaicin
acute-phase treatment (Dezieck 2017 PMID 28215116; Richards 2017 PMID
28634640), and cyclic-vomiting-vs-CHS differential. Each row carries
primary PMID per §I and ≥ 1 positive + 1 negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("cannabinoid hyperemesis syndrome diagnostic
   criteria")`, **When** the registry is in place, **Then** ≥ 2 Level C
   claims are emitted citing Sorensen 2017 (PMID 27567272) and Allen 2004
   (PMID 15082584).
2. **Given** `compose_answer("CHS capsaicin cream treatment")`, **When**
   the registry is in place, **Then** the Dezieck 2017 (PMID 28215116)
   capsaicin acute-phase treatment claim is surfaced with the caveat
   that cessation remains the only definitive long-term resolution.
3. **Given** `compose_answer("cyclic vomiting syndrome vs cannabinoid
   hyperemesis differential")`, **When** the registry is in place,
   **Then** the cyclic-vomiting / CHS overlap is surfaced (Venkatesan
   2019 Rome IV criteria) with both syndromes acknowledged as distinct.
4. **Given** `compose_answer("CHS prevalence emergency department
   legalization")`, **When** the registry is in place, **Then** the
   post-legalization ED case-load increase claim is surfaced (Kim 2018
   PMID 30049481 or equivalent).

---

### User Story 4 — eCBome enzyme-inhibitor pharmacology depth (Priority: P2, finding N4)

A drug-development researcher asks `PF-04457845 FAAH inhibitor cannabis
withdrawal NEJM`, `BIA 10-2474 FAAH inhibitor Phase 1 Rennes disaster`,
`MAGL inhibitor ABX-1431 lorcaserin GABA tone`, or `dual FAAH / MAGL
inhibitor JZL195`. v0.4 surfaces the static FAAH / MAGL enzyme reference
in the eCBome registry but no curated inhibitor-pharmacology claims —
the entire drug-development translation story is absent.

**Why this priority**: P2. The eCBome registry is the v0.2 deliverable
that justified the "endocannabinoidome" claim in the v0.2 description.
A researcher running an eCBome-inhibitor query expects to see the
clinical-trial landscape (D'Souza 2019 PF-04457845 cannabis-withdrawal
trial PMID 30985083; Huggins 2012 PF-04457845 OA-pain trial PMID
22910298) AND the safety-disaster reference (Kerbrat 2016 BIA 10-2474
Rennes disaster PMID 27806243) AND the MAGL-inhibitor pharmacology
(Cisar 2018 ABX-1431 PMID 29498523). The depth is essential to make
the eCBome registry credible to a pharmacology audience.

**Independent Test**: A new `ecbome_inhibitors.py` module with ≥ 5 rows
covering PF-04457845 cannabis withdrawal (D'Souza 2019 PMID 30985083),
PF-04457845 osteoarthritis pain (Huggins 2012 PMID 22910298), BIA
10-2474 Phase 1 Rennes disaster (Kerbrat 2016 PMID 27806243), MAGL
inhibitor ABX-1431 / lorcaserin GABA-tone PD profile (Cisar 2018 PMID
29498523), and dual FAAH / MAGL inhibitor JZL195 mechanism (Long 2009
PMID 19429692). Each row carries primary PMID and ≥ 1 positive + 1
negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("PF-04457845 FAAH inhibitor cannabis
   withdrawal NEJM")`, **When** the registry is in place, **Then** the
   D'Souza 2019 (PMID 30985083) Phase 2a cannabis-withdrawal trial
   claim is surfaced at Level B.
2. **Given** `compose_answer("BIA 10-2474 Rennes Phase 1 disaster")`,
   **When** the registry is in place, **Then** the Kerbrat 2016 (PMID
   27806243) safety-disaster narrative is surfaced with the explicit
   caveat that the BIA 10-2474 toxicity is attributed to OFF-TARGET
   serine-hydrolase inhibition, NOT to on-target FAAH biology — an
   essential disambiguation for a researcher reading the BIA 10-2474
   case in the press.
3. **Given** `compose_answer("MAGL inhibitor ABX-1431 cannabis-related
   PD")`, **When** the registry is in place, **Then** the Cisar 2018
   (PMID 29498523) ABX-1431 SAR / mechanism paper is surfaced.
4. **Given** `compose_answer("dual FAAH MAGL inhibitor JZL195")`, **When**
   the registry is in place, **Then** the Long 2009 (PMID 19429692)
   JZL195 dual-inhibitor mechanism claim is surfaced.

---

### User Story 5 — Cannabinoid biosynthesis pathway registry (Priority: P2, finding N5)

A synthetic-biology / plant-secondary-metabolism researcher asks
`olivetolic acid synthase polyketide pathway biosynthesis`, `olivetolic
acid cyclase OAC Gagne 2012`, `prenyltransferase CBGAS Page 2011`,
`THCA synthase enzymology Sirikantaramas 2004`, or `Luo 2019 yeast
cannabinoid heterologous expression Nature`. v0.4 returns 0 curated
claims for every one.

**Why this priority**: P2. The biosynthesis pathway is the canonical
plant-biochemistry story — every cultivation-genetics paper assumes the
reader knows it. The Taura 2009 (PMID 19429605), Gagne 2012 (PMID
22802647), Page 2011 (PMID 21896800), Sirikantaramas 2004 (PMID
15453749), Taura 1996 (PMID 8632416), and Luo 2019 (PMID 30814733)
primary literature is well-established. Its absence makes Cannavec
Science feel like a clinical tool only, not a comprehensive research
tool. Synbio researchers running heterologous-expression projects need
this surface.

**Independent Test**: A new `biosynthesis.py` module with ≥ 5 registry
rows covering olivetol synthase + olivetolic acid cyclase (Taura 2009
PMID 19429605, Gagne 2012 PMID 22802647), prenyltransferase CBGAS
(Page 2011 PMID 21896800), THCA synthase (Sirikantaramas 2004 PMID
15453749), CBDA synthase (Taura 1996 PMID 8632416), and yeast
heterologous expression (Luo 2019 PMID 30814733). Each row carries
primary PMID and ≥ 1 positive + 1 negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("olivetolic acid synthase polyketide
   pathway biosynthesis")`, **When** the registry is in place, **Then**
   the Taura 2009 (PMID 19429605) OLS / OAC dual-enzyme pathway claim
   is surfaced at Level C.
2. **Given** `compose_answer("THCA synthase enzymology Sirikantaramas
   2004")`, **When** the registry is in place, **Then** the
   Sirikantaramas 2004 (PMID 15453749) THCA synthase FAD-dependent
   oxidocyclase mechanism is surfaced.
3. **Given** `compose_answer("Luo 2019 yeast cannabinoid heterologous
   expression Nature")`, **When** the registry is in place, **Then**
   the Luo 2019 (PMID 30814733) Saccharomyces-cerevisiae cannabinoid
   biosynthesis platform claim is surfaced.
4. **Given** `compose_answer("CBDA synthase Taura 1996 enzymology")`,
   **When** the registry is in place, **Then** the Taura 1996 (PMID
   8632416) CBDA synthase characterisation claim is surfaced.

---

### User Story 6 — Europe PMC live-discovery lane (Priority: P3, finding N6)

A researcher running `discover` for a European-centred topic (e.g.
`nabiximols European approval`, `Bedrocan medical cannabis Netherlands`,
or any Spanish / Italian / German cannabinoid research society
proceedings paper) currently misses European-indexed literature PubMed
does not pick up. Europe PMC indexes PubMed PLUS the full PMC corpus
PLUS European non-MEDLINE-indexed journals — adding a sixth-tier live
source rounds out the discovery layer.

**Why this priority**: P3. PubMed already covers the vast majority of
indexed cannabinoid research. Europe PMC is a *complement*, not a
replacement — it picks up European preprint mirrors, MDPI cannabinoid-
research papers not yet in MEDLINE, Wellcome Open Research, EU
clinical-trial-registry-linked papers, etc.

**Independent Test**: A new `europepmc_discover.py` module with the
same shape as `pubmed_search.py` (injected fetcher, deterministic
parsing, offline-safe). The `discover` subcommand learns the
`europepmc` source name and the cross-source synthesis layer counts
the new lane. The `source-health` subcommand learns the new probe.

**Acceptance Scenarios**:

1. **Given** `python3 -m cannavec_science discover "nabiximols European
   approval" --include-europepmc`, **When** the discover fan-out
   runs, **Then** the `live_europepmc` lane is included in the output
   alongside `live_pubmed` / `live_chembl` / `live_ctgov`.
2. **Given** the offline test fixture, **When** the Europe PMC fetcher
   returns the canned JSON, **Then** the parsed rows carry the
   `live_europepmc` provenance tag and a provisional Level grade.
3. **Given** `python3 -m cannavec_science source-health`, **When** the
   subcommand runs, **Then** `europepmc` appears in the probe table.
4. **Given** the offline test suite, **When** `python3 -m unittest
   discover -s tests` runs, **Then** the Europe PMC fetcher is invoked
   only via injected fixture — no network calls escape.

---

### User Story 7 — Inventory the new registries (Priority: P3)

`python3 -m cannavec_science registries` does not list the five new
registries until they are wired into `cannavec_science/registries.py`.
Mechanical follow-on to US1-US5.

**Independent Test**: A unit test asserts that `build_inventory()`
includes all five new groups, each with row counts and entry labels;
total registries 11 → 16.

**Acceptance Scenarios**:

1. **Given** `build_inventory()`, **When** the inventory is built after
   US1-US5 land, **Then** the result includes `pharmacokinetics`,
   `use_disorder`, `hyperemesis_syndrome`, `ecbome_inhibitors`, and
   `biosynthesis` groups.
2. **Given** `python3 -m cannavec_science registries --registry
   pharmacokinetics`, **When** the command runs, **Then** only that
   group is returned.
3. **Given** `python3 -m cannavec_science registries --format json`,
   **When** the command runs, **Then** the JSON includes all 16 groups.

---

### User Story 8 — Eval bucket for v0.5 (Priority: P3)

The v0.4 eval suite has 144 prompts in 8 buckets. v0.5 adds a new
`clinical_pharmacology_depth` bucket with ≥ 16 prompts exercising:

- THC inhaled vs oral PK (3 prompts).
- CBD oral PK + food effect (2 prompts).
- 11-OH-THC active metabolite (1 prompt).
- CUD DSM-5 criteria + CUDIT-R + Hasin prevalence (3 prompts).
- Cannabis Withdrawal Scale (1 prompt).
- CHS diagnostic criteria + capsaicin + cyclic-vomiting differential (3 prompts).
- FAAH-inhibitor pharmacology (PF-04457845 + BIA 10-2474) (2 prompts).
- MAGL-inhibitor pharmacology (1 prompt).
- Biosynthesis pathway (Taura 2009 + Sirikantaramas 2004) (2 prompts).

Plus the `live` bucket gains ≥ 2 prompts exercising the Europe PMC lane.

**Acceptance Scenarios**:

1. **Given** the eval suite, **When** `python3 evals/run_evals.py` runs,
   **Then** the `clinical_pharmacology_depth` bucket has ≥ 16 prompts
   and all pass. Total eval prompt count rises to ≥ 162 (offline ≥ 149).
2. **Given** the v0.4 buckets, **When** evals run, **Then** every
   existing bucket still meets its minimum.

---

### Edge Cases

- **CBD-clobazam (existing v0.3 row)** must continue to fire when
  prompts mention CBD + clobazam. The pharmacokinetics row about CBD
  oral PK MUST NOT shadow / override the existing CBD-clobazam
  interaction row; both surface side-by-side.
- **THC → 11-OH-THC active metabolite** must coexist with the
  THCA-vs-THC rigor detector. The PK row about 11-OH-THC is a
  metabolite story (Δ⁹-THC → 11-OH-Δ⁹-THC via CYP2C9 first-pass), NOT
  a THCA-vs-THC conflation; the rigor detector does NOT fire.
- **CUD DSM-5 criteria** must coexist with the existing populations /
  adverse-events surfaces. CUD is a registry row about the diagnostic
  framework; the adverse-event row about CUD risk (Volkow 2014 NEJM)
  continues to fire as its own claim. The two rows are complementary.
- **CHS caution + CHS registry row** must coexist. The static caution
  remains for clinical-safety reasons; the registry row surfaces
  primary citations the researcher needs. No double-rendering.
- **FAAH inhibitor pharmacology** must coexist with the eCBome
  reference. The eCBome registry shows the static FAAH enzyme reference
  (UniProt O00519); the inhibitor registry surfaces the drug-development
  claims with their primary PMIDs. Two distinct surfaces.
- **Olivetolic acid synthase** must coexist with the existing
  cultivation-science synthase-genetics rows. Cultivation-science rows
  cover THCA-synthase / CBDA-synthase chemotype inheritance; biosynthesis
  rows cover the upstream pathway (OLS / OAC / PT) AND the downstream
  enzymology (THCAS / CBDAS mechanism). Complementary.
- **Europe PMC fetcher** must respect the same offline-test contract
  as PubMed: an injected `fetch` callable, no network calls escape in
  the unit-test suite, and a deterministic JSON parser.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new `pharmacokinetics.py` module MUST ship with ≥ 8
  registry rows covering: THC inhaled PK (≥ 2 rows: smoked + vaped),
  THC oral PK (≥ 1 row), CBD oral PK (≥ 1 row), CBD food effect (≥ 1
  row), 11-OH-THC active metabolite (≥ 1 row), nabiximols oromucosal
  PK (≥ 1 row), and plasma-protein-binding / lipid-sequestration / urine
  detection window (≥ 1 row). Each row carries primary PMID / DOI per
  §I, a `to_claim()` returning a typed `Claim`, and ≥ 1 positive + 1
  negative unit test.
- **FR-002**: A new `use_disorder.py` module MUST ship with ≥ 6 rows
  covering DSM-5 CUD criteria (Hasin 2013), CUDIT-R (Adamson 2010),
  Cannabis Withdrawal Scale (Allsop 2011), CUD prevalence (Hasin 2015),
  CUD heritability (Verweij 2010), and CUD telescoping / age-of-onset
  (Chen 2009). Each row carries primary PMID per §I and unit tests.
- **FR-003**: A new `hyperemesis_syndrome.py` module MUST ship with ≥ 4
  rows covering diagnostic criteria (Sorensen 2017 + Allen 2004), Rome
  IV criteria (Venkatesan 2019), capsaicin treatment (Dezieck 2017),
  and cyclic-vomiting differential. Each row carries primary PMID per
  §I and unit tests.
- **FR-004**: A new `ecbome_inhibitors.py` module MUST ship with ≥ 5
  rows covering PF-04457845 cannabis withdrawal (D'Souza 2019),
  PF-04457845 osteoarthritis pain (Huggins 2012), BIA 10-2474 Phase 1
  disaster (Kerbrat 2016), MAGL inhibitor ABX-1431 (Cisar 2018), and
  dual FAAH / MAGL JZL195 (Long 2009). Each row carries primary PMID
  per §I and unit tests.
- **FR-005**: A new `biosynthesis.py` module MUST ship with ≥ 5 rows
  covering olivetol synthase + olivetolic acid cyclase (Taura 2009 +
  Gagne 2012), prenyltransferase CBGAS (Page 2011), THCA synthase
  (Sirikantaramas 2004), CBDA synthase (Taura 1996), and yeast
  heterologous expression (Luo 2019). Each row carries primary PMID
  per §I and unit tests.
- **FR-006**: `compose_answer` MUST import the five new registries and
  surface matching rows. Detection is on topic-keyword regex for each
  registry; the detector signatures mirror
  `detect_analytical_chemistry_mention(prompt)` exactly. Trace counters
  added for each.
- **FR-007**: A new `europepmc_discover.py` module MUST ship implementing
  a Europe PMC live-discovery lane with the same shape as
  `pubmed_search.py` — injected `fetch` callable, deterministic JSON
  parser, offline-safe with fixture injection. The lane is opt-in via
  `--include-europepmc` to the `discover` subcommand. Source-health
  probe added.
- **FR-008**: `cannavec_science/registries.py` MUST add five builder
  functions and entries in `all_registry_groups()` / `_BUILDERS` for
  the new registries. The CLI handler MUST accept all five new names.
- **FR-009**: The eval suite gains a new `clinical_pharmacology_depth`
  bucket with ≥ 16 prompts, and the bucket-minimum enforcement table
  includes `clinical_pharmacology_depth: 14` (floor of 14; bucket ships
  ≥ 16). The `live` bucket gains ≥ 2 Europe PMC prompts.
- **FR-010**: The version stamp bumps to `0.5.0` in three places:
  `.claude-plugin/plugin.json`, `pyproject.toml`,
  `cannavec_science/__init__.py`.
- **FR-011**: README adds a "v0.5 industry-expert-clinical-depth"
  section; the demo script gains a v0.5-flow block;
  `docs/V05_RATING_DELTA.md` summarises the delta.
- **FR-012**: All v0.4 surfaces remain regression-protected. No existing
  test weakens. `python3 -m unittest discover -s tests` exits 0 with
  ≥ 1,330 tests passing in ≤ 5 s.

### Key Entities

- **PharmacokineticsRow**: dataclass with `name`, `topic`
  (inhaled_pk / oral_pk / food_effect / active_metabolite /
  oromucosal_pk / distribution / detection_window), `claim_text`,
  `claim_type`, `evidence_level`, `source_tier`, `primary_citations`,
  `route` (smoked / vaped / oral / oromucosal / IV), `matrix`
  (plasma / urine / saliva / hair / breath), `key_pk_params` (tuple
  of `Tmax=...`, `Cmax=...`, `t½=...` strings), `last_verified`,
  `watch_pmids`. Implements `to_claim()`.
- **UseDisorderRow**: dataclass with `name`, `topic` (dsm5_criteria /
  screening_instrument / withdrawal_scale / prevalence / heritability
  / age_of_onset), `claim_text`, `claim_type`, `evidence_level`,
  `source_tier`, `primary_citations`, `instrument_name` (DSM-5 / CUDIT-R
  / CWS / NESARC-III), `last_verified`, `watch_pmids`. Implements
  `to_claim()`.
- **HyperemesisSyndromeRow**: dataclass with `name`, `topic`
  (diagnostic_criteria / rome_iv / capsaicin_treatment / cyclic_vomiting_dx /
  epidemiology), `claim_text`, `claim_type`, `evidence_level`,
  `source_tier`, `primary_citations`, `key_clinical_notes`,
  `last_verified`, `watch_pmids`. Implements `to_claim()`.
- **EcbomeInhibitorRow**: dataclass with `name`, `topic`
  (faah_inhibitor / magl_inhibitor / dual_inhibitor / safety_disaster),
  `claim_text`, `claim_type`, `evidence_level`, `source_tier`,
  `primary_citations`, `target_protein` (FAAH / MAGL / both),
  `compound_id` (e.g. PF-04457845, BIA 10-2474, ABX-1431),
  `chembl_id` (when applicable), `last_verified`, `watch_pmids`.
  Implements `to_claim()`.
- **BiosynthesisRow**: dataclass with `name`, `topic` (polyketide_origin /
  prenyltransferase / acid_synthase / heterologous_expression),
  `claim_text`, `claim_type`, `evidence_level`, `source_tier`,
  `primary_citations`, `enzyme_name` (OLS / OAC / CBGAS / THCAS / CBDAS),
  `ec_number` (e.g. EC 2.3.1.206 for OLS), `last_verified`,
  `watch_pmids`. Implements `to_claim()`.
- **DetectPharmacokineticsMention** / **DetectUseDisorderMention** /
  **DetectHyperemesisSyndromeMention** / **DetectEcbomeInhibitorMention** /
  **DetectBiosynthesisMention**: topic-keyword regex matchers that
  return matching subset of registry rows. Same shape as
  `detect_analytical_chemistry_mention` so the composer wire-up is uniform.
- **EuropePmcLane** (live-discovery): module-level functions
  `search(...)` and `to_provenance_rows(...)` mirroring the
  `pubmed_search.py` shape.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (v0.5 acceptance): `python3 -m unittest discover -s tests`
  exits 0 with at least **1,330 tests** (≥ 100 new tests across the
  five new registries, Europe PMC discover lane, registry inventory
  wiring, eval-coverage assertions).
- **SC-002** (v0.5 acceptance): `python3 -m cannavec_science answer
  "THC inhaled vs oral pharmacokinetics Tmax Cmax"` returns ≥ 2 Level
  C / Level D claims; highest_grade is no longer `Unsupported` for
  pharmacokinetics prompts.
- **SC-003** (v0.5 acceptance): `python3 -m cannavec_science answer
  "cannabis withdrawal syndrome assessment scale"` returns ≥ 1 Level C
  claim citing Allsop 2011 (PMID 21652129).
- **SC-004** (v0.5 acceptance): `python3 -m cannavec_science answer
  "cannabinoid hyperemesis syndrome diagnostic criteria"` returns ≥ 2
  Level C claims citing Sorensen 2017 + Allen 2004.
- **SC-005** (v0.5 acceptance): `python3 -m cannavec_science answer
  "PF-04457845 FAAH inhibitor cannabis withdrawal NEJM"` returns ≥ 1
  Level B claim citing D'Souza 2019 (PMID 30985083).
- **SC-006** (v0.5 acceptance): `python3 -m cannavec_science answer
  "olivetolic acid synthase polyketide pathway biosynthesis"` returns
  ≥ 1 Level C claim citing Taura 2009 (PMID 19429605).
- **SC-007** (v0.5 acceptance): `python3 -m cannavec_science discover
  "nabiximols European approval" --include-europepmc` includes the
  `live_europepmc` lane (or, when offline, the source-unavailable
  marker for it).
- **SC-008** (v0.5 acceptance): `python3 -m cannavec_science registries`
  lists all 16 groups (11 v0.4 + 5 v0.5) in markdown and `--format json`.
- **SC-009** (v0.5 acceptance): The eval suite has ≥ **162 prompts**
  (offline ≥ 149), with `clinical_pharmacology_depth` bucket ≥ 14 and
  every existing bucket regression-protected.
- **SC-010** (v0.5 acceptance): `.claude-plugin/plugin.json`,
  `pyproject.toml`, `cannavec_science/__init__.py` all report
  version `0.5.0`.
- **SC-011** (v0.5 acceptance): README's "What ships" section documents
  the v0.5 deliverables (≥ 8 PK rows, ≥ 6 CUD/CWS rows, ≥ 4 CHS rows,
  ≥ 5 eCBome-inhibitor rows, ≥ 5 biosynthesis rows, Europe PMC lane).
- **SC-012** (v0.5 acceptance): Total Python LOC under
  `cannavec_science/` stays under **35,000**.
- **SC-013** (v0.5 acceptance): Slash-command count remains exactly 5;
  subcommand count rises by 0 (Europe PMC is a flag on `discover`).

### Industry-Expert Trust Heuristics (qualitative, but checked at demo)

- **Pharmacokinetics test**: a clinical-pharmacology PI asks
  "11-OH-THC oral dronabinol" — gets a Level C / Level D primary-cited
  PK claim with the first-pass-effect explanation, not silence.
- **CUD-instrument test**: an addiction-medicine researcher asks
  "CUDIT-R psychometric properties" — gets the Adamson 2010 (PMID
  20231083) screening-instrument citation, not the Volkow review only.
- **CHS-criteria test**: a GI researcher asks "CHS Rome IV criteria"
  — gets the Sorensen 2017 + Allen 2004 + Venkatesan 2019 row set,
  not the static caution alone.
- **FAAH-disaster test**: a drug-development researcher asks "BIA
  10-2474 Rennes disaster" — gets the Kerbrat 2016 reference WITH the
  off-target-serine-hydrolase disambiguation, NOT a confused
  "FAAH is unsafe" framing.
- **Biosynthesis test**: a synbio researcher asks "olivetolic acid
  synthase Taura 2009" — gets the OLS / OAC pathway claim with the
  Taura 2009 PMID, not silence.
- **Europe PMC test**: a European researcher asks "Bedrocan
  Netherlands cannabinoid pharmacology" with `--include-europepmc`
  — sees the Europe PMC lane in the discover output (or the
  source-unavailable marker offline).

## Assumptions

- v0.5 stays inside Constitution §IV (researcher only). The five new
  registries are research-grade primary-literature topics covering
  clinical pharmacokinetics, addiction-medicine instruments, GI
  syndrome diagnostic criteria, eCBome drug-development translation,
  and plant-biochemistry biosynthesis — all explicit researcher
  audience targets.
- v0.5 stays stdlib-only per §X. Europe PMC fetcher uses `urllib`
  with the existing injected-fetch test contract.
- The existing 1,228 unit tests are regression-protected. The
  ~2-second total runtime is the ceiling.
- The five-slash-command lock per Constitution §IV holds. The Europe
  PMC lane is a `discover` flag, not a new subcommand.
- The Huestis 2005 PMID 16142973, Karschner 2011 PMID 21240010,
  Birnbaum 2019 PMID 31166007, Wall 1983 PMID 6311559, Hasin 2013
  PMID 23537606, Adamson 2010 PMID 20231083, Allsop 2011 PMID 21652129,
  Hasin 2015 PMID 26502112, Sorensen 2017 PMID 27567272, Allen 2004
  PMID 15082584, Dezieck 2017 PMID 28215116, D'Souza 2019 PMID 30985083,
  Kerbrat 2016 PMID 27806243, Cisar 2018 PMID 29498523, Taura 2009 PMID
  19429605, Gagne 2012 PMID 22802647, Page 2011 PMID 21896800,
  Sirikantaramas 2004 PMID 15453749, Luo 2019 PMID 30814733 citations
  are the v0.5 backbone and anchor the very first rows in each registry.
- No new slash commands. The new registries surface through `answer` /
  `ask` / `discover` / `rigor` and the `registries` subcommand. Europe
  PMC is a `discover` flag.

## Constitutional Impact

This spec is an in-constitution evolution. Per-principle impact:

- **§I (Primary-Source Or Refuse)**: deepened by FR-001 through FR-005
  — every new registry row carries a primary PMID / DOI per §I.
- **§II (Deterministic-Backbone Over Prose)**: deepened by FR-006 (each
  new registry has a deterministic topic-keyword detector).
- **§III (Test-First)**: enforced — every user story carries positive
  + negative test triples. v0.5 ships ≥ 100 new tests.
- **§IV (Researcher Audience Only)**: **unchanged**. Clinical
  pharmacokinetics, addiction-medicine instruments, GI syndromes,
  eCBome drug development, and cannabinoid biosynthesis are all
  research-grade primary-literature topics.
- **§V (Safety-Layer Sovereignty)**: unchanged. CHS rows fire AFTER
  safety preflight; the existing static caution is preserved.
- **§VI (Phytochemistry Precision)**: deepened by US1 — PK rows name
  cannabinoids by isomer (Δ⁹-THC vs 11-OH-Δ⁹-THC) and matrix
  (plasma / urine / saliva). The THCA-vs-THC rigor detector does NOT
  fire on metabolite stories (PK row about 11-OH-THC is correctly
  identified as a metabolite).
- **§VII (GRADE Honesty)**: deepened — every new row caps evidence
  grade at the source-tier maximum. D'Souza 2019 Phase 2a (Level B,
  not Level A — single trial, not Cochrane SR). Kerbrat 2016 case
  series (Level D). PK rows from controlled-dose human studies (Level
  C / D depending on n).
- **§VIII (Retractions At Composition)**: unchanged — new rows
  participate in the existing retraction-suppression flow.
- **§IX (Live Discovery)**: deepened by FR-007 — Europe PMC joins
  PubMed / ChEMBL / CT.gov / PubChem / PharmGKB / RCSB / Open Targets
  / GWAS / BindingDB / bioRxiv / medRxiv. Twelve live sources total.
- **§X (Stdlib-Only)**: unchanged — Europe PMC uses urllib with
  injected fetcher.
- **§XI (Citable Output Is The Default)**: deepened — bibliography
  export continues to work over the v0.5 typed Answer, including the
  new pharmacokinetics / CUD / CHS / eCBome-inhibitor / biosynthesis
  citations.

No amendment is required. The v0.5 release continues the v0.x → v0.4
trajectory: research-grade clinical-pharmacology depth is exactly the
extension §IV explicitly permits.
