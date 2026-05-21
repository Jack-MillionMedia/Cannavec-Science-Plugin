# Cannavec Science

**A focused Claude Code plugin for research-grade cannabis science.**

A working cannabis-research scientist needs three things from a research
tool: primary citations they can defend, phytochemistry precision they
can publish, and live access to the literature. Cannavec Science ships
exactly those things — and nothing else.

This is the **MVP distillation** of the larger
[Cannavec plugin](https://github.com/Jack-MillionMedia/Cannavec-Plugin)
(41 commands, 14 agents, ~35,500 LOC, 15 audience surfaces). Cannavec
Science strips it down to **five commands, one audience, eight curated
science registries, and ~6,000 LOC** — built to be impressive in
five minutes, defensible in a peer review, and stdlib-only in any
Python ≥ 3.9 environment.

## What ships

- **Five slash commands.** No more, no less.
- **Eight curated science registries** — major + minor cannabinoids,
  terpenes, drug interactions, adverse events, populations,
  contraindications, pharmacogenomics. Every row PubMed-cited.
- **Six phytochemistry rigor detectors** — isomer collapse,
  receptor-without-ID, dose-without-route, THCA-vs-THC conflation,
  matrix-unit confusion, decarb-context-missing.
- **15-pattern banned-pattern detector** with a 30-char negation
  guard — catches indica/sativa-as-pharmacology, cultivar-as-effect,
  marketing ratios, "natural therefore safe," "cure" claims, etc.
- **Safety preflight** — refuse-harmful / refuse-individualized /
  add-caution / proceed. K2/Spice synthesis is hard-refused.
- **Retraction enforcement at composition time** — a retracted PMID
  is suppressed from the answer's claims (not just flagged post-hoc).
- **Live discovery across PubMed + ChEMBL + ClinicalTrials.gov**
  with deterministic cross-source synthesis
  (STRONG / MIXED / WEAK / NONE convergence).
- **Bibliography export to BibTeX / RIS / CSL-JSON** with inline
  GRADE annotation. Drop straight into Zotero / Mendeley / EndNote.

## What does NOT ship (deliberately)

Per the [Constitution §IV](.specify/memory/constitution.md), the MVP
is researcher-only. The following exist in the parent Cannavec plugin
and are **out of scope** for v0.x:

- Patient, clinician, cultivator, lab, compliance, retail,
  public-health, operator, policy, product, hemp, microbiome,
  veterinary surfaces.
- KB flywheel, gap detection, BM25 search, proposal generation.
- Signed artifacts, watchlists, persistent expert profiles.
- Multi-jurisdiction legal surface, per-state hemp-derived
  cannabinoid law, pesticide registry.
- CourtListener / legal discovery.
- bioRxiv / medRxiv preprint discovery.

We did not ship them so we could ship the core well.

## 30-second quickstart

```bash
git clone https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin
cd Cannavec-Science-Plugin

# That's it. No `pip install`. Stdlib only.

# Smoke test:
python3 -m unittest discover -s tests  # 759 tests, ~0.1 s

# Try the four golden flows:
python3 -m cannavec_science answer "What is the evidence for CBD in Dravet syndrome?"
python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01
python3 -m cannavec_science verify 28538134
python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC and the dose was 10 mg"
```

## The five commands

| Command | What it does |
|---|---|
| `/cannavec-science:research <question>` | Full researcher brief — PICO framing, GRADE-graded claims, primary citations, monograph sections, evidence synthesis, rigor pass on the prompt. |
| `/cannavec-science:ask <question>` | Fast Q&A — same composer, slimmer rendering. |
| `/cannavec-science:discover <query>` | Live multi-source fan-out (PubMed + ChEMBL + ClinicalTrials.gov) with cross-source synthesis verdict. |
| `/cannavec-science:verify <PMID\|DOI>` | Single-identifier spot-check with retraction status. |
| `/cannavec-science:rigor <text>` | Run the six phytochemistry rigor detectors + banned-pattern detector on arbitrary text. |

## The deterministic backbone

```
cannavec_science/
├── evidence.py            # GRADE, Source, Claim, ClaimType, source-authority weight
├── banned_patterns.py     # 15 patterns + 30-char negation guard
├── safety.py              # Refuse-harmful / refuse-individualized / proceed verdict
├── rigor_checks.py        # Six phytochemistry detectors
├── retraction.py          # Retraction registry + composition-time enforcement
├── pubmed_verify.py       # E-utilities + Crossref verifier (stdlib urllib)
├── pubmed_search.py       # Live PubMed search
├── chembl_discover.py     # Live ChEMBL bioactivity
├── ctgov_discover.py      # Live ClinicalTrials.gov
├── discover_guard.py      # Safety guard on live queries
├── synthesis.py           # Cross-source synthesis verdict
├── source_health.py       # Per-source liveness probe
├── intent.py              # Intent classifier
├── uncertainty.py         # GRADE wording-vs-grade verb picker
├── answer.py              # Typed Answer + compose_answer
├── evidence_synthesis.py  # Deterministic claim-set rollup
├── bibliography.py        # BibTeX / RIS / CSL-JSON exporter
├── contradiction.py       # Pairwise claim contradiction detector
├── major_cannabinoids.py  # Δ9-THC, CBD, THCA, CBDA
├── minor_cannabinoids.py  # THCV, CBDV, CBC, CBN, CBG
├── terpenes.py            # Terpene registry
├── terpene_reference.py   # Terpene analytical chemistry
├── interactions.py        # 32-row drug-interaction registry
├── adverse_events.py      # AE registry
├── populations.py         # Trial-supported populations
├── contraindications.py   # Contraindication registry
└── pharmacogenomics.py    # CYP2C9 / CYP3A4 / CYP2C19 PGx
```

## Tests + acceptance gate

```bash
python3 -m unittest discover -s tests   # 759 tests, offline, ~0.1 s
```

Before any push to the MVP branch, all of the following MUST hold
(per [`specs/001-science-mvp/plan.md`](specs/001-science-mvp/plan.md)):

- `python3 -m unittest discover -s tests` exits 0.
- `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome"`
  returns ≥ 3 cited claims, ≥ 1 Level A or B, zero banned-pattern hits.
- `python3 -m cannavec_science verify 28538134` returns the
  Devinsky-2017 record with `retraction_status: clean`.
- `python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC"`
  returns a `thca_vs_thc_conflation` violation.
- The total slash-command count is exactly five.
- The total Python LOC under `cannavec_science/` is under 8,000.

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
