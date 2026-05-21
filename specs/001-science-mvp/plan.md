# Implementation Plan: Cannavec Science MVP

**Spec**: [`spec.md`](./spec.md)

**Created**: 2026-05-21

**Status**: Approved for `/speckit-tasks`

## Strategy

The parent Cannavec plugin already has hardened, test-covered
implementations of every primitive the MVP needs. The plan is **port,
trim, and rename** — not rewrite. Each ported module gets:

1. A clean module name under `cannavec_science/` (drop legacy aliases).
2. Removal of audience branches that are not researcher.
3. Removal of jurisdiction-aware filtering (not needed for a science
   surface).
4. Removal of KB / artifact / orchestrator hooks.
5. Existing tests ported with the same renames.

## Files To Port From Parent

The parent lives at `../Cannavec-Plugin/cannavec/`. The MVP keeps the
following 15 modules (~6,000 LOC after trimming). Everything else
stays in the parent.

### Tier 1 — Deterministic backbone (must ship)

| Parent module | MVP module | Why kept |
|---|---|---|
| `evidence.py` | `cannavec_science/evidence.py` | GRADE levels, `Source`, `Claim`, `ClaimType`, source-authority weighting. |
| `banned_patterns.py` | `cannavec_science/banned_patterns.py` | 15-pattern detector + negation guard. Researcher audience still hits these. |
| `safety.py` | `cannavec_science/safety.py` | Refuse-harmful / refuse-individualized / proceed verdict. K2 synthesis hard refuse. Trim individualized-medical refusal logic (researcher audience does not need it as aggressively, but keep it). |
| `rigor_checks.py` | `cannavec_science/rigor_checks.py` | Six detectors: isomer-collapse, receptor-without-ID, dose-without-route, THCA-vs-THC, matrix-unit, decarb-context. |
| `pubmed_verify.py` | `cannavec_science/pubmed_verify.py` | E-utilities + Crossref + retraction status. Stdlib only. |
| `pubmed_search.py` | `cannavec_science/pubmed_search.py` | Live E-utilities search for the discover surface. |
| `retraction.py` | `cannavec_science/retraction.py` | Retraction registry consulted at compose time. |
| `uncertainty.py` | `cannavec_science/uncertainty.py` | Wording-vs-grade verb picker + consistency checker. |
| `answer.py` | `cannavec_science/answer.py` | Typed `Answer` + `compose_answer`. **Trim:** drop jurisdiction, drop multi-audience branching, drop hemp/pesticide/oncology registry threading. Keep retraction policy + rigor report + bibliography hook. |
| `evidence_synthesis.py` | `cannavec_science/evidence_synthesis.py` | Deterministic rollup over an `Answer`. |
| `bibliography.py` | `cannavec_science/bibliography.py` | BibTeX/RIS/CSL-JSON exporter with inline GRADE. |
| `intent.py` | `cannavec_science/intent.py` | Intent classifier (definition / dose / mechanism / efficacy / safety / interaction). Used by the research-brief composer to pick which registries to consult. |

### Tier 2 — Science registries (must ship)

| Parent module | MVP module | Why kept |
|---|---|---|
| `major_cannabinoids.py` | `cannavec_science/major_cannabinoids.py` | Δ⁹-THC, CBD, THCA, CBDA core science. |
| `minor_cannabinoids.py` | `cannavec_science/minor_cannabinoids.py` | THCV, CBDV, CBC, CBN, CBG. Already evidence-honest about CBC/CBG = Unsupported. |
| `terpenes.py` + `terpene_reference.py` | `cannavec_science/terpenes.py` | Terpene science. Merged into one module. |
| `interactions.py` | `cannavec_science/interactions.py` | 32-row drug-interaction registry (17 original + 15 modern from spec 004 Wave A). |
| `adverse_events.py` | `cannavec_science/adverse_events.py` | 13-row AE registry. |
| `populations.py` | `cannavec_science/populations.py` | Trial-supported population reference. |
| `contraindications.py` | `cannavec_science/contraindications.py` | 10-row contraindication registry. |
| `pharmacogenomics.py` | `cannavec_science/pharmacogenomics.py` | CYP2C9 / CYP3A4 / CYP2C19 rows. |

### Tier 3 — Live discovery (must ship)

| Parent module | MVP module | Why kept |
|---|---|---|
| `chembl_discover.py` | `cannavec_science/chembl_discover.py` | ChEMBL bioactivity REST. |
| `ctgov_discover.py` | `cannavec_science/ctgov_discover.py` | ClinicalTrials.gov API v2. |
| `discover_guard.py` | `cannavec_science/discover_guard.py` | Safety + banned-pattern guard on live queries. |
| `synthesis.py` | `cannavec_science/synthesis.py` | Cross-source synthesis verdict. |
| `source_health.py` | `cannavec_science/source_health.py` | Per-source health probe. |

### Modules dropped (~36 modules, ~22,000 LOC)

`agronomy.py`, `chemotype.py`, `comparative.py`, `digest.py`,
`dispatcher.py`, `domains.py`, `generators.py`, `hemp.py`,
`hemp_derived_cannabinoids.py`, `jurisdiction.py`, `kb.py`,
`kb_flywheel.py`, `kb_search.py`, `legal_discover.py`,
`metrics.py`, `oncology.py`, `orchestrator.py`,
`pesticides.py`, `preprint_discover.py`, `profile.py`,
`pubmed_snapshot.py`, `regimen.py`, `regulator_links.py`,
`self_audit.py`, `templates.py`, `watchlist.py`,
`artifacts.py`, `_pubmed_snapshot.json`, plus the contradiction
detector (folded into `evidence_synthesis.py`'s contradictions field).

## Surfaces (slash commands, agents, skills)

**Five slash commands (no more, no less):**

| Command | File | Purpose |
|---|---|---|
| `/cannavec-science:research` | `commands/research.md` | Full research brief pipeline. P1 demo surface. |
| `/cannavec-science:ask` | `commands/ask.md` | Fast Q&A. Same pipeline, slimmer output. |
| `/cannavec-science:discover` | `commands/discover.md` | Live multi-source fan-out. |
| `/cannavec-science:verify` | `commands/verify.md` | Single identifier spot-check. |
| `/cannavec-science:rigor` | `commands/rigor.md` | Run six rigor detectors on arbitrary text. |

**Two skills (auto-activating):**

| Skill | Purpose |
|---|---|
| `cannabis-research-rigor` | The Five Pillars of Verity. Loads when any cannabis-research claim is being formulated. Ported from parent. |
| `cannabis-evidence-grading` | GRADE wording-vs-grade rules. Ported from parent. |

The parent's other eight skills (banned-patterns-as-skill, domain
router, jurisdiction handler, KB flywheel, patch authoring, safety
guardrails, skill router, target reference) are **either replaced by
the deterministic backbone** (banned patterns / safety / target IDs)
**or out of scope** (KB, domain, jurisdiction, patch).

**Two agents:**

| Agent | Purpose |
|---|---|
| `cannabis-source-hunter` | Discovery — fans out across PubMed / ChEMBL / CTGov. Ported from parent. |
| `cannabis-research-reviewer` | Consolidated reviewer (replaces parent's six-persona reviewer set). Reviews drafts for evidence rigor, phytochemistry precision, GRADE wording, banned-pattern compliance. |

## Module Architecture

```
cannavec_science/
├── __init__.py
├── __main__.py            # CLI: python -m cannavec_science <subcommand>
├── evidence.py            # GRADE, Source, Claim, ClaimType
├── banned_patterns.py     # 15 patterns + negation guard
├── safety.py              # Safety preflight
├── rigor_checks.py        # Six phytochemistry detectors
├── retraction.py          # Retraction registry + lookup
├── pubmed_verify.py       # E-utilities + Crossref verifier
├── pubmed_search.py       # Live PubMed search
├── chembl_discover.py     # Live ChEMBL bioactivity
├── ctgov_discover.py      # Live ClinicalTrials.gov
├── discover_guard.py      # Safety guard on live queries
├── synthesis.py           # Cross-source synthesis verdict
├── source_health.py       # Per-source health probe
├── intent.py              # Intent classifier
├── uncertainty.py         # Wording-vs-grade verbs
├── answer.py              # Typed Answer + compose_answer
├── evidence_synthesis.py  # Deterministic rollup
├── bibliography.py        # BibTeX / RIS / CSL-JSON export
├── major_cannabinoids.py  # Δ9-THC, CBD, THCA, CBDA
├── minor_cannabinoids.py  # THCV, CBDV, CBC, CBN, CBG
├── terpenes.py            # Terpene reference (merged)
├── interactions.py        # 32-row drug-interaction registry
├── adverse_events.py      # AE registry
├── populations.py         # Trial-supported populations
├── contraindications.py   # Contraindication registry
└── pharmacogenomics.py    # PGx registry
```

## Public CLI Surface

`python -m cannavec_science <subcommand>`:

```
answer "<question>" [--bibliography {bibtex|ris|csljson}] [--out PATH]
                    [--retraction-policy {strict|badge}] [--json]
discover "<query>" [--since YYYY-MM-DD] [--max N]
                   [--sources pubmed,chembl,ctgov] [--json]
verify <PMID|DOI|NCT|ChEMBL>
rigor "<text>"
bibliography <answer.json> --format {bibtex|ris|csljson} [--out PATH]
source-health [--sources pubmed,chembl,ctgov]
```

Every subcommand returns a non-zero exit code on refusal / error so
the surface is CI-gateable.

## Trade-offs & Decisions

1. **Drop jurisdiction handling entirely.** The parent ships a
   53-entry US jurisdiction handler + 23 countries. None of it is
   relevant to a cannabis-science MVP. A scientist asking about
   CBD-Dravet evidence is not asking "in which state." This removes
   ~500 LOC and one entire registry surface.

2. **Drop bioRxiv/medRxiv preprint discovery for v0.x.** Preprints are
   valuable but reduce credibility for the demo audience (clients
   want "real PubMed papers"). Adding preprints back is a v0.2 feature
   behind a constitutional amendment.

3. **Drop CourtListener.** Legal discovery is orthogonal to science.

4. **Merge `terpenes.py` + `terpene_reference.py` into one module.**
   The parent split is historical; one terpene registry is cleaner.

5. **Fold contradiction detection into `evidence_synthesis.py`.** The
   parent's standalone contradiction module is overkill for the MVP.
   The rollup already needs contradictions; collocate them.

6. **Drop the parent's domain classifier.** Researcher is the only
   audience; there is no per-domain routing decision to make.

7. **Drop the parent's `templates.py`.** Researcher template is the
   only template; hardcode it into `answer.py`.

8. **Replace the parent's six reviewer personas with one
   `cannabis-research-reviewer` agent.** The Verity Test is the
   review checklist; we do not need six personas to apply it.

## Implementation Order

1. **Tier 1 backbone modules + their tests** (evidence, banned_patterns,
   safety, rigor_checks, retraction). These are leaves of the dependency
   graph — port and trim first.
2. **PubMed/Crossref verifier + intent classifier + uncertainty** —
   stdlib-only, network-injected fetchers, easy to test.
3. **Registries** (major / minor cannabinoids, terpenes, interactions,
   AEs, populations, contraindications, PGx) — pure data; port wholesale.
4. **`answer.py` + `compose_answer` + `evidence_synthesis.py` +
   `bibliography.py`** — wires the backbone + registries into the
   typed pipeline. Where the bulk of the trimming happens.
5. **Live discovery modules** (`pubmed_search`, `chembl_discover`,
   `ctgov_discover`, `discover_guard`, `synthesis`, `source_health`) —
   plus their offline-injected-fetcher tests.
6. **`__main__.py` CLI** — wires every primitive into a subcommand.
7. **Slash commands (5), skills (2), agents (2)** — prose surfaces.
8. **Eval seed** (`evals/canonical_research_questions.yaml`) — 12
   prompts that exercise every detector + every registry.
9. **README, QUICKSTART, CLAUDE.md, LICENSE, .gitignore,
   pyproject.toml, plugin.json** — meta files.
10. **Commit + push to `claude/cannavec-science-plugin-mvp-FYkM0`.**

## Acceptance Gate

Before pushing the MVP branch, ALL of the following MUST hold:

- `python3 -m unittest discover -s tests` exits 0.
- `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" --audience researcher` returns ≥ 3 cited claims, ≥ 1 Level A or B, zero banned-pattern hits.
- `python3 -m cannavec_science verify 28538134` returns the Devinsky-2017 record with `retraction_status: not_retracted`.
- `python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC"` returns a `THCA_VS_THC_CONFLATION` violation.
- The total slash-command count is exactly five.
- The total Python LOC under `cannavec_science/` is under 20,000
  (a 50%+ reduction from the parent's ~35,500). Most remaining LOC is
  data tables in the eight registries, not new code surface.

## Risks & Mitigations

- **Risk**: Live network calls in the demo flake under unreliable
  WiFi. **Mitigation**: every live subcommand has a `--offline` or
  injected-fetcher fixture path; the demo can be driven from
  recorded fixtures if needed.
- **Risk**: A trimmed registry loses a curated row the parent had.
  **Mitigation**: the MVP plan keeps every science registry's *data*
  intact — the trimming is at the audience/template/jurisdiction
  layer, not the registry-row layer.
- **Risk**: A potential client asks for a non-researcher surface in
  the demo. **Mitigation**: Constitution §IV is explicit; the
  honest answer is "the v0.x MVP is researcher-only; here is what
  v0.2 will look like with a constitutional amendment." This is
  itself a credibility signal.
