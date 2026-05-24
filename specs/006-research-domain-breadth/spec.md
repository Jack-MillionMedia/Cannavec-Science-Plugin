# Feature Specification: Research-Domain Breadth & Rigor Extensions (v0.6)

**Feature Branch**: `claude/modest-knuth-PUits`

**Created**: 2026-05-24

**Status**: Approved for `/speckit-plan` and immediate implementation

**Input**: User request: "continue developing this claude plugin to be
elite for credible/expert cannabis research. Use spec-kit to make and
plan significant improvements."

## Background

Spec 005 shipped v0.5 industry-expert-clinical-depth: five new
registries (pharmacokinetics, use-disorder/withdrawal, hyperemesis
syndrome, eCBome inhibitors, biosynthesis pathway) plus the Europe
PMC live-discovery lane. v0.5 surfaces are green at 1,369 unit tests
and 162 eval prompts across nine buckets. The clinical-pharmacology
depth a working PI hits in their first hour of demo is in place.

A fourth-pass industry-expert review against the v0.5 head of
`claude/modest-knuth-PUits` exposes **four new credibility gaps a
working cannabis-research scientist hits within minutes**, plus a
sustained quality gap on reporting-rigor literacy and a thirteenth
primary-source live-discovery lane:

- **N1 (P1, content-gap)** — A pain-medicine researcher asks
  `chronic pain cannabis systematic review NASEM 2017`, `nabiximols
  neuropathic pain Cochrane`, `Whiting 2015 JAMA cannabis chronic
  pain`, or `Andreae 2015 IPD meta analysis neuropathic`. v0.5
  returns 0-1 curated claims — the NASEM 2017 chapter-4 conclusive-
  evidence finding for chronic pain (the single most-cited cannabis-
  medicine statement) is entirely absent; Whiting 2015 JAMA SR (PMID
  26103030), Stockings 2018 PAIN SR (PMID 30121596), Mücke 2018
  Cochrane (PMID 29513392), Boehnke 2019 J Pain (PMID 31237829), and
  Andreae 2015 IPD-MA (PMID 25840040) are nowhere in the curated
  surface. This is the single largest demo-time silence in v0.5 for
  the most-asked medical-cannabis topic.
- **N2 (P1, content-gap)** — A psychiatry researcher asks `high
  potency cannabis psychosis Di Forti EU-GEI`, `cannabis psychosis
  meta-analysis Marconi 2016`, `Vaucher 2018 Mendelian randomization
  cannabis schizophrenia`, or `Bhattacharyya acute THC fMRI
  prefrontal`. v0.5 returns 0 curated claims — neither the Di Forti
  2019 EU-GEI Lancet Psychiatry first-episode-psychosis case-control
  study (PMID 30902669), the Marconi 2016 Schizophr Bull dose-
  response SR (PMID 26884547), the Vaucher 2018 Mol Psychiatry MR
  (PMID 29039420), nor the Hjorthøj 2023 Lancet Psychiatry national-
  register study (PMID 36402143) is in the curated surface. The
  cannabis-psychosis literature is one of the most-cited and most-
  contentious cannabis research areas; silence here makes the tool
  look incomplete.
- **N3 (P1, content-gap)** — A traffic-medicine / forensic-toxicology
  researcher asks `cannabis driving impairment Compton 2017 NHTSA`,
  `Hartman 2015 THC plasma crash risk`, `Marcotte 2022 JAMA Psychiatry
  driving simulator`, or `Brubacher 2022 cannabis cohort crash BC`.
  v0.5 returns 0 curated claims — the Compton 2017 NHTSA case-control
  driver-risk study (DOT HS 812 411), the Hartman 2015 Clin Chem dose-
  response (PMID 25371545), the Marcotte 2022 JAMA Psychiatry driving-
  simulator RCT (PMID 35138350), and the Bondallaz 2016 Forensic Sci
  Int SR (PMID 27082781) are nowhere curated. Driving impairment is
  asked at every cannabis-research conference; the policy-adjacent
  surface stays inside Constitution §IV when anchored to primary
  research only.
- **N4 (P2, content-gap)** — A PTSD / anxiety / sleep researcher asks
  `Bonn-Miller 2021 PTSD cannabis trial`, `CBD social anxiety Crippa
  Bergamaschi`, `cannabis sleep Walsh 2017 systematic review`, or
  `acute THC anxiety Bedi 2010`. v0.5 returns 0-1 curated claims —
  the Bonn-Miller 2021 PLOS One PTSD RCT (PMID 33667097 — the only
  randomized trial in PTSD and importantly largely negative on most
  endpoints), Walsh 2017 Sleep Med Rev (PMID 28392485), Crippa 2011
  J Psychopharmacol CBD-SAD (PMID 20829306), Bergamaschi 2011
  Neuropsychopharmacology CBD-SAD speech (PMID 21307846), and Bedi
  2010 Drug Alcohol Depend acute-THC anxiety (PMID 19897322) are
  nowhere in the curated surface. Mood / anxiety / sleep is the
  largest cannabis-medicine commercial-claim space and the
  literature is sparser and more cautionary than commercial copy
  suggests — exactly the asymmetry the deterministic backbone is
  best at flagging.
- **N5 (P2, rigor-extension gap)** — When a prompt contains study-
  design language ("randomized trial", "systematic review",
  "observational cohort", "diagnostic accuracy"), v0.5 has no
  reporting-guideline rigor surface that asks whether the trial /
  SR / study cites the appropriate EQUATOR-network reporting guideline
  (CONSORT for RCTs, PRISMA-2020 for SRs, STROBE for observational
  studies, STARD for diagnostic accuracy) or the appropriate risk-of-
  bias / quality tool (ROB-2 for RCTs, ROBINS-I for non-randomized
  intervention studies, AMSTAR-2 for SR quality). This is a §VII
  GRADE-honesty deepening — researchers reading or writing a cannabis
  trial benefit from the reporting-rigor scaffolding. The detectors
  are PROMPT-LEVEL (do you mention CONSORT when discussing an RCT?
  do you mention ROB-2 when grading bias?), not output-text-level.
- **N6 (P3, live-discovery widening)** — Live discovery covers 12
  primary scientific sources but omits **OpenAlex** (formerly
  Microsoft Academic Graph successor), which is the largest open
  scholarly citation index — covers PubMed PLUS arXiv / bioRxiv /
  medRxiv PLUS conference proceedings, and exposes the full open
  citation graph (cited-by / references). A researcher running
  `discover` for a citation-network-anchored question (e.g. who has
  cited Di Forti 2019 in the last 12 months) currently has to leave
  the tool to use Google Scholar / OpenAlex web. Adding OpenAlex as
  the 13th lane closes that gap stdlib-only.

This spec **bundles four new curated registries (N1-N4) with one new
rigor module (N5) and one new live-discovery lane (N6)**, plus the
surrounding eval / docs / version-bump work to ship v0.6 cleanly.
Every story stays inside Constitution §IV (researcher only). No
amendment required — chronic-pain medicine, cannabis-psychosis
epidemiology, driving impairment, PTSD/anxiety/sleep, reporting-
rigor literacy, and an open citation-graph live source are all
explicitly research-grade primary-literature topics inside the
existing audience scope-lock.

## What v0.5 Already Does Well (preserve in v0.6)

These are the surfaces v0.6 MUST NOT regress. Every regression is a
constitution violation:

1. All v0.5 surfaces (US1-US8 of spec 005 + the v0.4 / v0.3 /
   v0.2 / v0.1 backbone).
2. The five v0.5 registries (pharmacokinetics ≥ 8, use_disorder ≥ 6,
   hyperemesis_syndrome ≥ 4, ecbome_inhibitors ≥ 5, biosynthesis
   ≥ 5) surface for their topic-keyword prompts.
3. Europe PMC live-discovery lane (12th source) with `--include-
   europepmc` opt-in and source-health probe (spec 005 US6).
4. Registry inventory subcommand emits the 16 v0.5 groups in markdown
   + JSON (spec 005 US7).
5. The eval suite remains ≥ 162 prompts in nine buckets, all
   bucket-minimums green.
6. K2/Spice hard-refuse, the 16 banned-pattern detectors, span-aware
   `NamedCannabinoidSet`, retraction-at-composition, GRADE wording-vs-
   grade consistency, cannabinoid-scoped registry filtering, seven
   phytochemistry rigor detectors with (detector, span) deduplication.
7. Bibliography export (BibTeX / RIS / CSL-JSON) under §XI for every
   answer including the v0.5 typed Answer payload.

## Review Methodology (v0.5 fourth pass)

Same shape as specs 003 / 004 / 005: every test is a `python3 -m
cannavec_science <cmd>` invocation against HEAD of
`claude/modest-knuth-PUits`. Findings are P1 / P2 / P3 by severity.
Findings either point to a new shipping content gap (N-prefix) or
restate a v0.6 horizon item.

### Findings transcript

```
$ python3 -m cannavec_science answer "chronic pain cannabis systematic review NASEM 2017"
**Q:** chronic pain cannabis systematic review NASEM 2017
## Evidence summary
- Highest evidence grade across claims: **Unsupported**
- Claims: 0
```

```
$ python3 -m cannavec_science answer "high potency cannabis psychosis Di Forti EU-GEI"
**Q:** high potency cannabis psychosis Di Forti EU-GEI
## Evidence summary
- Claims: 0  (no curated psychosis surface)
```

```
$ python3 -m cannavec_science answer "cannabis driving impairment Compton 2017 NHTSA"
**Q:** cannabis driving impairment Compton 2017 NHTSA
## Evidence summary
- Claims: 0
```

```
$ python3 -m cannavec_science answer "Bonn-Miller 2021 PTSD cannabis trial"
**Q:** Bonn-Miller 2021 PTSD cannabis trial
## Evidence summary
- Claims: 0  (only the existing populations PTSD row, not the trial)
```

```
$ python3 -m cannavec_science rigor "we conducted a randomized trial of CBD in chronic pain"
[no reporting-guideline / risk-of-bias detector fires; CONSORT not flagged as missing]
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Pain medicine registry (Priority: P1, finding N1)

A pain-medicine researcher asks `chronic pain cannabis systematic
review NASEM 2017`, `nabiximols neuropathic pain Cochrane`, `Whiting
2015 JAMA cannabis chronic pain`, or `Andreae 2015 IPD meta analysis
neuropathic`. v0.5 returns 0-1 curated claims for every one — no pain-
medicine registry exists.

**Why this priority**: P1. Chronic pain is the most-common
qualifying condition for medical cannabis programs worldwide; the
NASEM 2017 "conclusive evidence" finding for chronic pain is the
most-cited statement in cannabis-medicine literature. A researcher
who asks `chronic pain cannabis Whiting 2015` and gets silence will
not trust the tool for any clinical claim.

**Independent Test**: A new `pain_medicine.py` module with ≥ 7
registry rows covering the NASEM 2017 chapter 4 chronic-pain
conclusive-evidence finding, Whiting 2015 JAMA SR, Stockings 2018
PAIN SR neuropathic, Mücke 2018 Cochrane neuropathic, Boehnke 2019
J Pain prospective MMJ cohort, Andreae 2015 IPD-MA neuropathic, and
the de Vita 2018 experimental-pain SR. Each row carries primary
PMID / DOI per §I, a `to_claim()`, and ≥ 1 positive + 1 negative
unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("chronic pain cannabis NASEM 2017")`,
   **When** the pain-medicine registry is in place, **Then** ≥ 1
   Level A claim is emitted referencing the NASEM 2017 chapter-4
   "conclusive evidence: cannabis effective for chronic pain in
   adults" finding with the Whiting 2015 JAMA SR (PMID 26103030)
   anchor.
2. **Given** `compose_answer("Whiting 2015 JAMA cannabis chronic
   pain")`, **When** the registry is in place, **Then** the Whiting
   2015 JAMA SR (PMID 26103030) is surfaced at Level A.
3. **Given** `compose_answer("nabiximols neuropathic pain Mücke
   Cochrane 2018")`, **When** the registry is in place, **Then** the
   Mücke 2018 Cochrane review (PMID 29513392) is surfaced with the
   "low-quality evidence; modest benefit; AE-driven discontinuation"
   summary the Cochrane review actually concluded.
4. **Given** `compose_answer("Andreae 2015 IPD meta-analysis
   neuropathic pain inhaled cannabis")`, **When** the registry is in
   place, **Then** the Andreae 2015 J Pain IPD-MA (PMID 25840040)
   claim is surfaced at Level A.

---

### User Story 2 — Cannabis & psychosis registry (Priority: P1, finding N2)

A psychiatry researcher asks `high potency cannabis psychosis Di Forti
EU-GEI`, `Marconi 2016 cannabis psychosis dose response meta-analysis`,
`Vaucher 2018 cannabis schizophrenia MR`, or `Bhattacharyya acute THC
fMRI prefrontal`. v0.5 returns 0 curated claims for every one — the
cannabis-psychosis literature is absent from the curated surface.

**Why this priority**: P1. Cannabis-and-psychosis is one of the most-
cited and most-controversial cannabis-research areas. A researcher
who asks `Di Forti 2019 EU-GEI` and gets silence cannot trust the
tool to mediate the literature it most needs to mediate.

**Independent Test**: A new `psychiatry.py` module with ≥ 6 registry
rows covering Di Forti 2019 EU-GEI (PMID 30902669), Marconi 2016
Schizophr Bull dose-response SR (PMID 26884547), Murray 2017 Lancet
Psychiatry review (PMID 28935667), Vaucher 2018 Mol Psychiatry MR
(PMID 29039420), Bhattacharyya 2009 Arch Gen Psychiatry acute-THC
fMRI (PMID 19996036), and Hjorthøj 2023 Lancet Psychiatry national-
register cohort (PMID 36402143 or equivalent). Each row carries
primary PMID per §I and ≥ 1 positive + 1 negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("high potency cannabis psychosis Di
   Forti EU-GEI")`, **When** the psychiatry registry is in place,
   **Then** ≥ 1 Level B / Level C claim is emitted citing Di Forti
   2019 EU-GEI Lancet Psychiatry (PMID 30902669) with the
   high-potency-cannabis daily-use adjusted-odds-ratio finding.
2. **Given** `compose_answer("Marconi 2016 cannabis psychosis dose
   response")`, **When** the registry is in place, **Then** the
   Marconi 2016 Schizophr Bull SR (PMID 26884547) dose-response
   claim is surfaced at Level A (SR).
3. **Given** `compose_answer("Vaucher 2018 Mendelian randomization
   cannabis schizophrenia")`, **When** the registry is in place,
   **Then** the Vaucher 2018 Mol Psychiatry MR (PMID 29039420)
   causality-direction claim is surfaced with the MR-methodology
   caveat (genetic-instrument validity assumption).
4. **Given** `compose_answer("acute THC fMRI prefrontal Bhattacharyya
   2009")`, **When** the registry is in place, **Then** the
   Bhattacharyya 2009 Arch Gen Psychiatry acute-THC fMRI claim is
   surfaced with the mechanism caveat (acute pharmacological challenge
   in healthy volunteers, not patient phenotype).

---

### User Story 3 — Driving-impairment registry (Priority: P1, finding N3)

A traffic-medicine / forensic-toxicology researcher asks `cannabis
driving impairment Compton 2017 NHTSA`, `Hartman 2015 THC plasma
crash risk`, `Marcotte 2022 JAMA Psychiatry driving simulator`, or
`Brubacher 2022 cannabis cohort crash BC`. v0.5 returns 0 curated
claims for every one.

**Why this priority**: P1. Driving impairment is asked at every
cannabis-research conference, every legalisation policy hearing, and
every workplace-safety conversation. The primary-research literature
(Compton 2017 NHTSA, Hartman 2015 Clin Chem, Marcotte 2022 JAMA
Psychiatry, Bondallaz 2016 SR, Brubacher 2022 cohort) is well-
established. The surface stays inside Constitution §IV by being
*research literature only*, not policy advice — per-se laws live in
the parent plugin, NOT here.

**Independent Test**: A new `driving_impairment.py` module with ≥ 5
registry rows covering Compton 2017 NHTSA case-control (DOT HS 812
411), Hartman 2015 Clin Chem plasma-THC dose-response (PMID 25371545),
Marcotte 2022 JAMA Psychiatry driving-simulator RCT (PMID 35138350),
Brubacher 2022 cohort (PMID 36066903 or equivalent), and Bondallaz
2016 Forensic Sci Int SR (PMID 27082781). Each row carries primary
PMID / report citation per §I and ≥ 1 positive + 1 negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("cannabis driving impairment Compton
   2017 NHTSA")`, **When** the driving-impairment registry is in
   place, **Then** ≥ 1 Level B / Level C claim is emitted referencing
   the Compton 2017 NHTSA case-control crash-risk study (DOT HS 812
   411) with the adjusted-odds-ratio attenuation finding after
   demographic / alcohol adjustment.
2. **Given** `compose_answer("Hartman 2015 THC plasma crash risk")`,
   **When** the registry is in place, **Then** the Hartman 2015 Clin
   Chem dose-response analysis (PMID 25371545) is surfaced with the
   plasma-THC threshold caveat.
3. **Given** `compose_answer("Marcotte 2022 JAMA Psychiatry driving
   simulator")`, **When** the registry is in place, **Then** the
   Marcotte 2022 JAMA Psychiatry RCT (PMID 35138350) driving-
   simulator dose-response claim is surfaced.
4. **Given** `compose_answer("cannabis driving impairment systematic
   review Bondallaz 2016")`, **When** the registry is in place,
   **Then** the Bondallaz 2016 Forensic Sci Int SR (PMID 27082781)
   claim is surfaced.

---

### User Story 4 — PTSD / anxiety / sleep registry (Priority: P2, finding N4)

A PTSD / anxiety / sleep researcher asks `Bonn-Miller 2021 PTSD
cannabis trial`, `CBD social anxiety Crippa Bergamaschi`, `cannabis
sleep Walsh 2017 systematic review`, or `acute THC anxiety Bedi
2010`. v0.5 returns 0-1 curated claims for every one.

**Why this priority**: P2. Mood / anxiety / sleep is the largest
commercial-claim space and the literature is sparser and more
cautionary than the marketing copy suggests. A researcher who asks
`Bonn-Miller 2021 PTSD cannabis trial` should be told it exists AND
that its primary endpoints were largely negative — exactly the kind
of asymmetric correction the deterministic backbone is best at.

**Independent Test**: A new `ptsd_anxiety_sleep.py` module with ≥ 5
registry rows covering Bonn-Miller 2021 PLOS One PTSD RCT (PMID
33667097), Walsh 2017 Sleep Med Rev (PMID 28392485), Crippa 2011 J
Psychopharmacol CBD-SAD (PMID 20829306), Bergamaschi 2011
Neuropsychopharm CBD-SAD speech (PMID 21307846), and Bedi 2010 Drug
Alcohol Depend acute-THC anxiety (PMID 19897322). Each row carries
primary PMID per §I and ≥ 1 positive + 1 negative unit test.

**Acceptance Scenarios**:

1. **Given** `compose_answer("Bonn-Miller 2021 PTSD cannabis trial")`,
   **When** the registry is in place, **Then** ≥ 1 Level B claim is
   emitted citing Bonn-Miller 2021 PLOS One (PMID 33667097) with the
   primary-endpoint negative result honestly stated.
2. **Given** `compose_answer("CBD social anxiety Crippa 2011
   Bergamaschi 2011")`, **When** the registry is in place, **Then**
   ≥ 1 Level C claim citing Crippa 2011 J Psychopharmacol (PMID
   20829306) AND Bergamaschi 2011 Neuropsychopharm (PMID 21307846)
   is surfaced.
3. **Given** `compose_answer("cannabis sleep Walsh 2017 systematic
   review")`, **When** the registry is in place, **Then** the
   Walsh 2017 Sleep Med Rev SR (PMID 28392485) claim is surfaced
   at Level B with the "limited and inconclusive evidence" caveat
   the SR actually reported.
4. **Given** `compose_answer("acute THC anxiety dose response Bedi
   2010")`, **When** the registry is in place, **Then** the Bedi
   2010 Drug Alcohol Depend (PMID 19897322) acute-THC dose-anxiety
   claim is surfaced with the dose-dependent biphasic-effect framing.

---

### User Story 5 — Reporting-guideline & risk-of-bias rigor extensions (Priority: P2, finding N5)

When a prompt contains study-design language (e.g. "we ran an RCT in
chronic pain", "this systematic review of cannabinoid trials", "this
observational cohort"), v0.5 has no rigor detector that asks whether
the appropriate EQUATOR-network reporting guideline (CONSORT-2010 for
RCTs, PRISMA-2020 for SRs, STROBE for observational studies, STARD
for diagnostic accuracy, CHEERS for economic evaluation) is mentioned,
or whether the appropriate risk-of-bias / quality-appraisal tool
(ROB-2 for RCTs, ROBINS-I for non-randomized intervention studies,
AMSTAR-2 for SR quality, QUADAS-2 for diagnostic accuracy) is
mentioned.

**Why this priority**: P2. This is a §VII GRADE-honesty deepening. A
researcher reading or drafting a cannabis-trial protocol benefits
from the reporting-rigor scaffolding the same way they benefit from
the existing isomer / receptor-id / dose-route detectors. The
rigor-extension module FLAGS rather than refuses; the output of
`rigor` lists missing reporting guidelines as a separate violation
class.

**Independent Test**: A new `reporting_rigor.py` module with ≥ 6
detectors covering CONSORT-2010 (Schulz 2010 BMJ PMID 20335313),
PRISMA-2020 (Page 2021 BMJ PMID 33781993), STROBE (von Elm 2007
PMID 17938396), ROB-2 (Sterne 2019 BMJ PMID 31462531), ROBINS-I
(Sterne 2016 BMJ PMID 27733354), and AMSTAR-2 (Shea 2017 BMJ PMID
28935701). Each detector ships with ≥ 1 positive + 1 negative unit
test. The detector output integrates into the existing
`RigorCheckReport` shape.

**Acceptance Scenarios**:

1. **Given** `rigor("we conducted a randomized controlled trial of
   CBD in chronic pain")`, **When** the reporting-rigor module is in
   place, **Then** a CONSORT-missing violation is flagged with the
   Schulz 2010 BMJ PMID 20335313 anchor.
2. **Given** `rigor("this systematic review of cannabinoid trials")`,
   **When** the reporting-rigor module is in place, **Then** a
   PRISMA-2020-missing violation is flagged with the Page 2021 BMJ
   PMID 33781993 anchor.
3. **Given** `rigor("this prospective observational cohort of
   medical-cannabis users")`, **When** the reporting-rigor module
   is in place, **Then** a STROBE-missing violation is flagged
   with the von Elm 2007 PMID 17938396 anchor.
4. **Given** `rigor("we used the Cochrane Risk of Bias 2 tool to
   appraise the included RCTs")`, **When** the reporting-rigor module
   is in place, **Then** NO violation fires for the RCT — ROB-2 is
   acknowledged; the detector is silent.
5. **Given** `rigor("this CONSORT-compliant RCT used ROB-2 for
   bias appraisal")`, **When** the reporting-rigor module is in
   place, **Then** NO violation fires — both reporting guideline
   and risk-of-bias tool are present.

---

### User Story 6 — OpenAlex live-discovery lane (Priority: P3, finding N6)

A researcher running `discover` for a citation-network question
(e.g. who has cited Di Forti 2019 in the last 12 months, what
papers cite Whiting 2015 JAMA) currently has to leave the tool and
use Google Scholar / OpenAlex web. Adding OpenAlex as the 13th lane
closes that gap stdlib-only.

**Why this priority**: P3. PubMed already covers MEDLINE; OpenAlex
is a *complement* with broader coverage (PubMed PLUS arXiv / bioRxiv
/ medRxiv / conference proceedings) AND an open citation graph
(cited-by / references) that PubMed does not expose. For citation-
network questions OpenAlex is uniquely useful.

**Independent Test**: A new `openalex_discover.py` module with the
same shape as `pubmed_search.py` (injected fetcher, deterministic
JSON parser, offline-safe with fixture injection). The `discover`
subcommand learns the `openalex` source name and the cross-source
synthesis layer counts the new lane. The `source-health` subcommand
learns the new probe.

**Acceptance Scenarios**:

1. **Given** `python3 -m cannavec_science discover "cannabis
   psychosis" --include-openalex`, **When** the discover fan-out
   runs, **Then** the `live_openalex` lane is included in the output
   alongside `live_pubmed` / `live_chembl` / `live_ctgov`.
2. **Given** the offline test fixture, **When** the OpenAlex fetcher
   returns the canned JSON, **Then** the parsed rows carry the
   `live_openalex` provenance tag and a provisional Level grade.
3. **Given** `python3 -m cannavec_science source-health`, **When** the
   subcommand runs, **Then** `openalex` appears in the probe table.
4. **Given** the offline test suite, **When** `python3 -m unittest
   discover -s tests` runs, **Then** the OpenAlex fetcher is invoked
   only via injected fixture — no network calls escape.

---

### User Story 7 — Inventory the new registries (Priority: P3)

`python3 -m cannavec_science registries` does not list the four new
registries until they are wired into `cannavec_science/registries.py`.
Mechanical follow-on to US1-US4.

**Independent Test**: A unit test asserts that `build_inventory()`
includes all four new groups, each with row counts and entry labels;
total registries 16 → 20.

**Acceptance Scenarios**:

1. **Given** `build_inventory()`, **When** the inventory is built after
   US1-US4 land, **Then** the result includes `pain_medicine`,
   `psychiatry`, `driving_impairment`, and `ptsd_anxiety_sleep` groups.
2. **Given** `python3 -m cannavec_science registries --registry
   pain_medicine`, **When** the command runs, **Then** only that
   group is returned.
3. **Given** `python3 -m cannavec_science registries --format json`,
   **When** the command runs, **Then** the JSON includes all 20 groups.

---

### User Story 8 — Eval bucket for v0.6 (Priority: P3)

The v0.5 eval suite has 162 prompts in nine buckets. v0.6 adds a new
`research_domain_breadth` bucket with ≥ 18 prompts exercising:

- Pain medicine (NASEM 2017 + Whiting 2015 + Stockings 2018 + Mücke
  2018 + Boehnke 2019 + Andreae 2015) — 6 prompts.
- Psychiatry / psychosis (Di Forti 2019 + Marconi 2016 + Vaucher
  2018 + Bhattacharyya 2009 + Hjorthøj 2023) — 5 prompts.
- Driving impairment (Compton 2017 + Hartman 2015 + Marcotte 2022 +
  Bondallaz 2016) — 4 prompts.
- PTSD / anxiety / sleep (Bonn-Miller 2021 + Crippa 2011 + Walsh
  2017) — 3 prompts.

Plus the `rigor_positive` bucket gains ≥ 5 reporting-rigor prompts
(CONSORT, PRISMA, STROBE, ROB-2, AMSTAR-2 positives), and the `live`
bucket gains ≥ 2 OpenAlex prompts.

**Acceptance Scenarios**:

1. **Given** the eval suite, **When** `python3 evals/run_evals.py` runs,
   **Then** the `research_domain_breadth` bucket has ≥ 18 prompts
   and all pass. Total eval prompt count rises to ≥ 187 (offline ≥ 172).
2. **Given** the v0.5 buckets, **When** evals run, **Then** every
   existing bucket still meets its minimum.

---

### Edge Cases

- **Pain-medicine NASEM 2017 row** must coexist with the existing
  major-cannabinoid monographs. NASEM 2017 references the Whiting
  2015 JAMA SR as anchor; the pain-medicine row about NASEM 2017
  carries Whiting 2015 PMID 26103030 and does NOT shadow the
  cannabidiol / Δ⁹-THC monograph.
- **Psychiatry / psychosis row** must coexist with the adverse-events
  registry (which carries the Volkow 2014 NEJM review row on cannabis
  & psychosis risk). The new psychiatry registry surfaces the
  primary-literature studies (Di Forti, Marconi, Vaucher); the
  adverse-events registry surfaces the review. Both surface side-by-
  side without double-rendering of the same PMID.
- **Driving-impairment row** must NOT be confused with the existing
  regulatory-feasibility advisory. Driving impairment surfaces research
  literature; per-se law surfaces are NOT added — those remain in the
  parent plugin per Constitution §IV. The driving-impairment registry
  is the SCIENCE, not the LAW.
- **PTSD / anxiety / sleep row** must coexist with the populations
  registry (which carries PTSD-population rows for clinical context).
  The new registry adds primary-research-trial citations the
  populations row does not.
- **Reporting-rigor detector** must NOT fire on prompts that already
  cite the appropriate guideline. "We used CONSORT-2010 to report
  this RCT" produces NO violation; "we ran an RCT" produces a
  CONSORT-missing violation. The detector is positive on missing,
  silent on present.
- **OpenAlex fetcher** must respect the same offline-test contract
  as PubMed / Europe PMC: an injected `fetch` callable, no network
  calls escape in the unit-test suite, and a deterministic JSON
  parser.
- **Banned-pattern interaction**: every new registry's claim_text
  passes the banned-pattern detector (no marketing copy, no entourage
  overclaim, no abstract indica/sativa, no synthetic-cannabinoid
  synthesis framing). Verified by an explicit "registry claim text
  passes banned-pattern detector" unit test.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new `pain_medicine.py` module MUST ship with ≥ 7
  registry rows covering: NASEM 2017 chapter-4 conclusive-evidence
  finding (Whiting 2015 anchor), Whiting 2015 JAMA SR, Stockings
  2018 PAIN SR neuropathic, Mücke 2018 Cochrane neuropathic, Boehnke
  2019 J Pain MMJ cohort, Andreae 2015 IPD-MA, and de Vita 2018
  experimental-pain SR. Each row carries primary PMID / DOI per §I,
  a `to_claim()` returning a typed `Claim`, and ≥ 1 positive + 1
  negative unit test.
- **FR-002**: A new `psychiatry.py` module MUST ship with ≥ 6 rows
  covering Di Forti 2019 EU-GEI (PMID 30902669), Marconi 2016 SR
  (PMID 26884547), Murray 2017 Lancet Psychiatry review (PMID
  28935667), Vaucher 2018 MR (PMID 29039420), Bhattacharyya 2009
  acute-THC fMRI (PMID 19996036), and Hjorthøj 2023 national-register
  cohort. Each row carries primary PMID per §I and unit tests.
- **FR-003**: A new `driving_impairment.py` module MUST ship with ≥ 5
  rows covering Compton 2017 NHTSA (DOT HS 812 411), Hartman 2015
  Clin Chem (PMID 25371545), Marcotte 2022 JAMA Psychiatry (PMID
  35138350), Brubacher 2022, and Bondallaz 2016 SR (PMID 27082781).
  Each row carries primary PMID / report citation per §I and unit
  tests.
- **FR-004**: A new `ptsd_anxiety_sleep.py` module MUST ship with ≥ 5
  rows covering Bonn-Miller 2021 PLOS One (PMID 33667097), Walsh
  2017 Sleep Med Rev (PMID 28392485), Crippa 2011 (PMID 20829306),
  Bergamaschi 2011 (PMID 21307846), and Bedi 2010 (PMID 19897322).
  Each row carries primary PMID per §I and unit tests.
- **FR-005**: A new `reporting_rigor.py` module MUST ship with ≥ 6
  detectors: CONSORT-2010 (Schulz 2010 BMJ PMID 20335313), PRISMA-
  2020 (Page 2021 BMJ PMID 33781993), STROBE (von Elm 2007 PMID
  17938396), ROB-2 (Sterne 2019 BMJ PMID 31462531), ROBINS-I (Sterne
  2016 BMJ PMID 27733354), AMSTAR-2 (Shea 2017 BMJ PMID 28935701).
  Each detector fires when the prompt mentions the study-design
  language without the appropriate guideline / tool. Detectors
  integrate into `RigorCheckReport` and surface in the `rigor`
  subcommand output.
- **FR-006**: `compose_answer` MUST import the four new registries
  and surface matching rows. Detection is via topic-keyword regex
  matchers (mirror `detect_pharmacokinetics_mention`). Trace counters
  added for each.
- **FR-007**: A new `openalex_discover.py` module MUST ship
  implementing an OpenAlex live-discovery lane with the same shape
  as `pubmed_search.py` — injected `fetch` callable, deterministic
  JSON parser, offline-safe with fixture injection. The lane is
  opt-in via `--include-openalex` to the `discover` subcommand.
  Source-health probe added.
- **FR-008**: `cannavec_science/registries.py` MUST add four builder
  functions and entries in `all_registry_groups()` / `_BUILDERS` for
  the new registries. The CLI handler MUST accept all four new names.
- **FR-009**: The eval suite gains a new `research_domain_breadth`
  bucket with ≥ 18 prompts and the bucket-minimum enforcement table
  includes `research_domain_breadth: 16`. The `rigor_positive` bucket
  gains ≥ 5 reporting-rigor prompts. The `live` bucket gains ≥ 2
  OpenAlex prompts.
- **FR-010**: The version stamp bumps to `0.6.0` in three places:
  `.claude-plugin/plugin.json`, `pyproject.toml`,
  `cannavec_science/__init__.py`.
- **FR-011**: README adds a "v0.6 research-domain-breadth" section;
  `docs/V06_RATING_DELTA.md` summarises the delta.
- **FR-012**: All v0.5 surfaces remain regression-protected. No
  existing test weakens. `python3 -m unittest discover -s tests`
  exits 0 with ≥ 1,460 tests passing in ≤ 6 s.

### Key Entities

- **PainMedicineRow**: dataclass with `name`, `topic`
  (nasem_finding / sr_chronic_pain / sr_neuropathic / cochrane_review
  / cohort_observational / ipd_meta_analysis / experimental_pain),
  `claim_text`, `claim_type`, `evidence_level`, `source_tier`,
  `primary_citations`, `population` (chronic-pain / neuropathic /
  experimental), `n_patients`, `key_finding_summary`, `last_verified`,
  `watch_pmids`. Implements `to_claim()`.
- **PsychiatryRow**: dataclass with `name`, `topic` (case_control_psychosis
  / dose_response_sr / mr_causality / acute_pharmacology / national_cohort
  / review_lancet), `claim_text`, `claim_type`, `evidence_level`,
  `source_tier`, `primary_citations`, `study_design`, `key_finding_summary`,
  `last_verified`, `watch_pmids`. Implements `to_claim()`.
- **DrivingImpairmentRow**: dataclass with `name`, `topic`
  (case_control_crash / plasma_dose_response / simulator_rct /
  prospective_cohort_crash / systematic_review), `claim_text`,
  `claim_type`, `evidence_level`, `source_tier`, `primary_citations`,
  `matrix` (plasma / whole-blood / oral fluid), `key_finding_summary`,
  `last_verified`, `watch_pmids`. Implements `to_claim()`.
- **PtsdAnxietySleepRow**: dataclass with `name`, `topic`
  (ptsd_rct / sad_acute_challenge / sleep_sr / acute_anxiety_dose_response),
  `claim_text`, `claim_type`, `evidence_level`, `source_tier`,
  `primary_citations`, `indication` (PTSD / SAD / sleep / acute-anxiety),
  `key_finding_summary`, `last_verified`, `watch_pmids`. Implements
  `to_claim()`.
- **DetectPainMedicineMention** / **DetectPsychiatryMention** /
  **DetectDrivingImpairmentMention** / **DetectPtsdAnxietySleepMention**:
  topic-keyword regex matchers that return matching subset of registry
  rows. Same shape as `detect_pharmacokinetics_mention`.
- **ReportingGuidelineViolation**: dataclass with `kind`
  (CONSORT / PRISMA / STROBE / STARD / CHEERS / ROB-2 / ROBINS-I /
  AMSTAR-2 / QUADAS-2), `span` (start, end of trigger), `why`,
  `recommendation_pmid` (PMID of the guideline paper). Implements
  `to_markdown()` for the rigor report.
- **OpenAlexLane** (live-discovery): module-level functions
  `search(...)` and `to_provenance_rows(...)` mirroring the
  `pubmed_search.py` shape.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (v0.6 acceptance): `python3 -m unittest discover -s tests`
  exits 0 with at least **1,460 tests** (≥ 90 new tests across the
  four new registries, reporting-rigor module, OpenAlex discover lane,
  registry inventory wiring, eval-coverage assertions).
- **SC-002** (v0.6 acceptance): `python3 -m cannavec_science answer
  "chronic pain cannabis Whiting 2015 JAMA"` returns ≥ 1 Level A
  claim citing Whiting 2015 (PMID 26103030); highest_grade is no
  longer `Unsupported`.
- **SC-003** (v0.6 acceptance): `python3 -m cannavec_science answer
  "high potency cannabis psychosis Di Forti EU-GEI"` returns ≥ 1
  Level B / C claim citing Di Forti 2019 (PMID 30902669).
- **SC-004** (v0.6 acceptance): `python3 -m cannavec_science answer
  "cannabis driving impairment Compton 2017 NHTSA"` returns ≥ 1
  Level B / C claim citing Compton 2017 NHTSA.
- **SC-005** (v0.6 acceptance): `python3 -m cannavec_science answer
  "Bonn-Miller 2021 PTSD cannabis trial"` returns ≥ 1 Level B claim
  citing Bonn-Miller 2021 (PMID 33667097).
- **SC-006** (v0.6 acceptance): `python3 -m cannavec_science rigor "we
  conducted a randomized controlled trial of CBD in chronic pain"`
  flags a CONSORT-missing reporting-rigor violation referencing
  Schulz 2010 (PMID 20335313).
- **SC-007** (v0.6 acceptance): `python3 -m cannavec_science discover
  "cannabis psychosis" --include-openalex` includes the
  `live_openalex` lane (or, when offline, the source-unavailable
  marker for it).
- **SC-008** (v0.6 acceptance): `python3 -m cannavec_science registries`
  lists all 20 groups (16 v0.5 + 4 v0.6) in markdown and
  `--format json`.
- **SC-009** (v0.6 acceptance): The eval suite has ≥ **187 prompts**
  (offline ≥ 172), with `research_domain_breadth` bucket ≥ 16 and
  every existing bucket regression-protected.
- **SC-010** (v0.6 acceptance): `.claude-plugin/plugin.json`,
  `pyproject.toml`, `cannavec_science/__init__.py` all report
  version `0.6.0`.
- **SC-011** (v0.6 acceptance): README's "What ships" section documents
  the v0.6 deliverables (≥ 7 pain-medicine rows, ≥ 6 psychiatry rows,
  ≥ 5 driving-impairment rows, ≥ 5 PTSD/anxiety/sleep rows, ≥ 6
  reporting-rigor detectors, OpenAlex lane).
- **SC-012** (v0.6 acceptance): Total Python LOC under
  `cannavec_science/` stays under **45,000**.
- **SC-013** (v0.6 acceptance): Slash-command count remains exactly 5;
  subcommand count rises by 0 (OpenAlex is a flag on `discover`).

### Industry-Expert Trust Heuristics (qualitative, but checked at demo)

- **Pain-medicine NASEM test**: a pain-medicine PI asks "NASEM 2017
  cannabis chronic pain conclusive evidence" — gets the Whiting 2015
  JAMA SR (PMID 26103030) -anchored Level A claim, not silence.
- **Psychosis Di Forti test**: a psychiatry researcher asks "high
  potency cannabis daily use psychosis Di Forti EU-GEI" — gets the
  Di Forti 2019 Lancet Psychiatry (PMID 30902669) claim with the
  daily-high-potency adjusted-odds-ratio finding, not silence.
- **Driving Compton test**: a forensic-toxicology researcher asks
  "cannabis crash risk Compton 2017 NHTSA case-control" — gets the
  Compton 2017 report claim with the demographic-adjustment
  attenuation honestly stated, not silence.
- **PTSD Bonn-Miller test**: a PTSD researcher asks "Bonn-Miller 2021
  PTSD cannabis primary endpoint" — gets the Bonn-Miller 2021 (PMID
  33667097) claim with the largely-negative primary-endpoint finding,
  not a confidence-laundered "cannabis effective for PTSD" framing.
- **CONSORT-missing test**: a researcher rigor-checks "we ran an RCT
  of CBD in 80 patients" — gets the CONSORT-missing flag with
  Schulz 2010 BMJ (PMID 20335313) anchor.
- **OpenAlex test**: a citation-network researcher runs `discover
  "cannabis psychosis" --include-openalex` — sees the OpenAlex lane
  in the discover output (or the source-unavailable marker offline).

## Assumptions

- v0.6 stays inside Constitution §IV (researcher only). The four new
  registries (pain medicine, psychiatry/psychosis, driving impairment,
  PTSD/anxiety/sleep) and one new rigor module are research-grade
  primary-literature topics. The driving-impairment registry is the
  SCIENCE (research literature) not the LAW (per-se law surfaces
  remain in the parent plugin).
- v0.6 stays stdlib-only per §X. OpenAlex fetcher uses `urllib` with
  the existing injected-fetch test contract.
- The existing 1,369 unit tests are regression-protected.
- The five-slash-command lock per Constitution §IV holds. OpenAlex
  is a `discover` flag, not a new subcommand. Reporting-rigor
  detectors integrate into the existing `rigor` subcommand.
- The Whiting 2015 PMID 26103030, Stockings 2018 PMID 30121596,
  Mücke 2018 PMID 29513392, Boehnke 2019 PMID 31237829, Andreae
  2015 PMID 25840040, de Vita 2018 PMID 30362962, Di Forti 2019
  PMID 30902669, Marconi 2016 PMID 26884547, Murray 2017 PMID
  28935667, Vaucher 2018 PMID 29039420, Bhattacharyya 2009 PMID
  19996036, Hjorthøj 2023 PMID 36402143, Compton 2017 NHTSA, Hartman
  2015 PMID 25371545, Marcotte 2022 PMID 35138350, Bondallaz 2016
  PMID 27082781, Bonn-Miller 2021 PMID 33667097, Walsh 2017 PMID
  28392485, Crippa 2011 PMID 20829306, Bergamaschi 2011 PMID
  21307846, Bedi 2010 PMID 19897322, Schulz 2010 PMID 20335313,
  Page 2021 PMID 33781993, von Elm 2007 PMID 17938396, Sterne 2019
  PMID 31462531, Sterne 2016 PMID 27733354, Shea 2017 PMID 28935701
  citations are the v0.6 backbone and anchor the very first rows in
  each registry / detector.
- No new slash commands. The new registries surface through `answer` /
  `ask` / `discover` / `rigor` and the `registries` subcommand.

## Constitutional Impact

This spec is an in-constitution evolution. Per-principle impact:

- **§I (Primary-Source Or Refuse)**: deepened by FR-001 through FR-005
  — every new registry row and reporting-rigor detector carries a
  primary PMID per §I.
- **§II (Deterministic-Backbone Over Prose)**: deepened by FR-006 (each
  new registry has a deterministic topic-keyword detector) and FR-005
  (each reporting-rigor detector is a deterministic regex matcher).
- **§III (Test-First)**: enforced — every user story carries positive
  + negative test triples. v0.6 ships ≥ 90 new tests.
- **§IV (Researcher Audience Only)**: **unchanged**. Pain medicine,
  psychiatry/psychosis, driving-impairment science (not law), PTSD/
  anxiety/sleep, reporting-rigor, and an open citation-graph live
  source are all research-grade primary-literature topics. The
  driving-impairment registry surfaces the science only; per-se law
  rows remain in the parent plugin.
- **§V (Safety-Layer Sovereignty)**: unchanged.
- **§VI (Phytochemistry Precision)**: deepened — pain-medicine,
  psychiatry, and driving-impairment rows name cannabinoids by
  isomer when relevant.
- **§VII (GRADE Honesty)**: deepened by FR-005 — reporting-rigor
  detectors raise the floor on what counts as a defensible study
  description. Reviews that omit CONSORT / PRISMA / STROBE are
  flagged. The wording-vs-grade consistency checker continues to
  enforce the Level A/B/C → "evidence shows/suggests/raises the
  possibility" mapping.
- **§VIII (Retractions At Composition)**: unchanged — new rows
  participate in the existing retraction-suppression flow.
- **§IX (Live Discovery)**: deepened by FR-007 — OpenAlex joins
  PubMed / ChEMBL / CT.gov / PubChem / PharmGKB / RCSB / Open
  Targets / GWAS / BindingDB / bioRxiv / medRxiv / Europe PMC.
  Thirteen live sources total.
- **§X (Stdlib-Only)**: unchanged — OpenAlex uses urllib with
  injected fetcher.
- **§XI (Citable Output Is The Default)**: deepened — bibliography
  export continues to work over the v0.6 typed Answer, including
  the new pain-medicine / psychiatry / driving-impairment / PTSD-
  anxiety-sleep citations.

No amendment is required. The v0.6 release continues the
v0.x → v0.5 trajectory: research-grade primary-literature depth in
the most-asked domains is exactly the extension §IV explicitly
permits.
