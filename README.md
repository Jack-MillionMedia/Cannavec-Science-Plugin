# Cannavec Science (v0.4 — industry-expert-depth build)

**A focused Claude Code plugin for elite-tier cannabis-research science.**

A working cannabis-research scientist needs more than a literature search:
they need primary citations they can defend, phytochemistry precision
they can publish, live access to the frontier (including preprints),
deterministic GRADE-level rigor with field-pushback signal, researcher-
workflow scaffolding (PICO, sample-size power, GRADE evidence-profile
table, IRB protocol skeleton), and — new in v0.4 — primary-source-anchored
analytical chemistry (decarboxylation kinetics, HPLC vs GC-MS method
validation, chemovar Type I-V classification, vapor pyrolysis byproducts)
and cultivation science (UV-B effects on biosynthesis, trichome biology,
synthase genetics, the live botanical-taxonomy debate). Cannavec Science
ships exactly those things — researcher-only, stdlib-only, deterministic.

This is the **v0.4 industry-expert-depth build** descending from the
v0.3 routing-and-surfacing build (spec 003) and the v0.2 elite-development
build (spec 002). v0.4 lands two new curated registries (≥ 8 analytical-
chemistry rows and ≥ 6 cultivation-science rows), closes a P1 rendering
bug that swallowed the v0.3 0-claim classification messages, and tightens
the indica/sativa-as-pharmacology refusal to catch abstract framings —
all without broadening the researcher-only audience lock. The build is
now **1,220+ unit tests strong** with a 13-prompt analytical-chemistry +
cultivation-science eval bucket on top of the 130-prompt v0.3 offline
canonical battery.

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
python3 -m unittest discover -s tests   # 1,220+ tests, ~2 s
python3 evals/run_evals.py              # 133 offline canonical evals (144 total; 11 live skipped offline)

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
