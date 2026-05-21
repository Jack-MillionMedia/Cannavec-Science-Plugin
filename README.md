# Cannavec Science (v0.2 — elite-tier build)

**A focused Claude Code plugin for elite-tier cannabis-research science.**

A working cannabis-research scientist needs more than a literature search:
they need primary citations they can defend, phytochemistry precision
they can publish, live access to the frontier (including preprints),
deterministic GRADE-level rigor with field-pushback signal, and
researcher-workflow scaffolding (PICO, sample-size power, GRADE
evidence-profile table, IRB protocol skeleton). Cannavec Science ships
exactly those things — researcher-only, stdlib-only, deterministic.

This is the **v0.2 elite-development build** descending from the larger
[Cannavec plugin](https://github.com/Jack-MillionMedia/Cannavec-Plugin).
The v0.1 MVP held five commands, one audience, eight curated science
registries, and a deterministic backbone in ~19,000 LOC. The v0.2 build
closes the six gaps the 2026-05-21 elite-tier rating identified
(preprints, eval breadth, citation-network analysis, registry freshness,
researcher-workflow scaffolding, cannabis-specific blind spots) without
breaking the audience scope-lock — and is now **1,045 unit tests strong**
across the deterministic backbone.

## What ships

- **Five slash commands.** No more, no less. v0.2 adds new functionality
  through flags + Python-module subcommands, never a sixth slash command
  (Constitution §IV).
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
python3 -m unittest discover -s tests   # 1,045 tests, ~0.1 s
python3 evals/run_evals.py              # 104 offline canonical evals (115 total; 11 live skipped offline)

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
python3 -m unittest discover -s tests   # 1,045 tests, offline, ~0.1 s
python3 evals/run_evals.py              # 104 offline canonical evals
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
