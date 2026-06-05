# Spec 029 — ChEBI chemical-ontology + QuickGO functional-annotation discovery

**Status**: Implemented

**Created**: 2026-06-04

**Constitutional gates**: §I, §II, §III, §V, §VI, §VIII, §IX, §X.

## Why this priority

The project already runs thirteen live primary-source lanes, but its **chemical**
coverage is structure-and-bioactivity only: PubChem gives the structure (CID,
InChIKey, SMILES), ChEMBL gives the bioactivity (Ki/IC50), RCSB gives the
crystal. None of them answer the two questions a cannabis pharmacologist asks
*next*:

1. **"What *is* this compound, ontologically — and is it actually from
   cannabis?"** ChEBI is the EBI's manually-curated chemical ontology. Its record
   for cannabidiol (`CHEBI:69478`) carries a curated **definition**, a **role
   classification** (`antimicrobial agent`, `anti-inflammatory agent`,
   `psychotropic drug`, …), a curation-quality **star** rating, **secondary IDs**,
   cross-database **accessions**, and — uniquely — **`compound_origins`**
   (`species_text: "Cannabis sativa", component: "aerial part"`). That botanical
   provenance and the role ontology are exactly the phytochemistry context (§VI)
   the other chemical lanes cannot supply.

2. **"What does the *receptor* this compound hits actually do?"** §VI already
   demands every receptor carry its UniProt accession (CB1 = P21554,
   CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231). QuickGO turns that accession
   into evidence: CB1 has **45 Gene-Ontology annotations** — molecular function
   (`GO:0004949 cannabinoid receptor activity`), biological process, cellular
   component — each carrying an **evidence code** and a **reference** (a PMID for
   experimental annotations, a `GO_REF` for electronic ones). That is the
   functional half of the mechanism the registries describe in prose.

Both are EBI public REST APIs reachable with stdlib `urllib` (§X). Both emit rows
anchored to a verifiable primary identifier (§I: a ChEBI accession; a GO id plus
its reference). Neither is a dose, a regimen, or individualized advice (§V).
Neither raises a curated GRADE — both are capped at **Level D (provisional)**
because an ontology record and a functional annotation are context, not clinical
evidence (§VII). They widen *what a researcher can discover*, never *what counts
as curated evidence* (Primacy Of Evidence).

This is a disciplined subset of a larger set of staged EBI/NCBI retrieval skills:
duplicative lanes (ClinicalTrials, PubChem, RCSB, UniProt, OpenTargets, Entrez)
already exist; out-of-scope sources (AlphaFold — barred by the Out-Of-Scope list;
MGnify microbiome — deferred; single-cell / proteomics / genome-assembly atlases —
not primary-source *cannabis* science under §IV) are deliberately excluded.

## User stories

### P1 — ChEBI lane: `chebi_discover.ChEBISearcher` + full fan-out wiring

`ChEBISearcher().search("cannabidiol")` resolves *name → CHEBI accession* via the
ChEBI 2.0 `es_search` endpoint, then fetches the `compound/<accession>/` record
and emits a frozen `ChEBICompoundRow` carrying: `chebi_id` (`CHEBI:69478`),
`chebi_name` (isomer-precise, §VI), `definition`, `stars`, `roles`
(name + ChEBI role accession), `cannabis_origin` (True when `compound_origins`
names *Cannabis sativa*), `xref_accessions`, `secondary_ids`, `url`, and
`suggested_grade = "Level D (provisional, live_chebi)"`. A bare accession
(`"CHEBI:69478"`) skips name resolution. `preflight()` runs as line 1 — a banned
or refused query raises `DiscoverRefused` before any network call (§V). Network
goes through an injected `Fetcher`; `default_chebi_fetcher` uses the polite UA +
bounded retry in `_http`. `render_markdown` / `render_json` mirror the PubChem
lane.

The lane is wired into every fan-out seam so it is not a half-surface (§Honest
Surface Constraints): `Provenance.LIVE_CHEBI`; `__main__._DISCOVERER_REGISTRY`
(`discover --sources chebi`) with updated help text; `live.SUPPORTED_SOURCES` +
`default_runners` (so `/api/discover?sources=chebi` resolves); `synthesis`
`_SOURCE_KEYS` + `_SOURCE_DISPLAY` (cross-source verdict counts ChEBI);
`ranker._ID_KEYS`, `answer.live_finding_from_row`, and the CLI/API identifier
display (so ChEBI rows attach to the blended brief, §IX); and a `source_health`
liveness probe.

### P2 — QuickGO lane: `quickgo_discover.QuickGOSearcher` + wiring

`QuickGOSearcher().search("CB2")` accepts either a UniProt accession (`P34972`)
or a §VI receptor name (`CB1`, `CB2`, `TRPV1`, `PPARγ`, `5-HT1A`, `GPR55`),
mapping the name to its accession via a small explicit receptor→UniProt table in
the lane, seeded from the §VI canon named in `answer.py` (CB1=P21554,
CB2=P34972, TRPV1=Q8NER1, PPARγ=P37231, 5-HT1A=P08908, GPR55=Q9Y2T6). It queries
QuickGO
`annotation/search?geneProductId=<acc>`, batch-resolves each distinct `goId`'s
name + aspect via `ontology/go/terms/<ids>`, and emits a `QuickGOAnnotationRow`
per annotation carrying: `go_id`, `go_name`, `go_aspect`
(molecular_function / biological_process / cellular_component), `evidence`
(`goEvidence` + `evidenceCode`), `reference` (the annotation's PMID or GO_REF),
`uniprot` accession, `qualifier`, and `suggested_grade =
"Level D (provisional, live_quickgo)"`. When `reference` is a PMID it is surfaced
on the row's `pmid` field so the existing §VIII retraction guard checks it. Same
preflight-first, injected-fetcher, render contract; wired into all the P1 seams
with `Provenance.LIVE_QUICKGO`.

### P3 — Blended brief, cross-source synthesis, and routing docs

`discover "cannabidiol" --sources pubmed,chembl,chebi,quickgo --json` returns all
four lanes plus a cross-source synthesis block whose `per_source_counts` include
`chebi` and `quickgo`. The `cannabis-primary-source-routing` skill documents the
routing rule (structure → PubChem; bioactivity → ChEMBL; **ontology / role /
botanical origin → ChEBI; receptor function → QuickGO**), and the README live-lane
inventory lists both. No curated grade is raised by either lane (§IX).

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green (the existing suite plus
  `tests/test_chebi_discover.py` and `tests/test_quickgo_discover.py`).
- **Fixtures are captured from the real EBI APIs**, never invented (the project's
  ChEMBL `/activity` lesson): the ChEBI happy-path fixture is the verbatim
  `es_search` + `compound/CHEBI:69478/` response for cannabidiol; the QuickGO
  fixture is the verbatim `annotation/search?geneProductId=P21554` + terms
  response for CB1.
- ChEBI: `search("cannabidiol")[0].chebi_id == "CHEBI:69478"`,
  `.cannabis_origin is True`, `.roles` is non-empty and contains the verified
  member `"antimicrobial agent"`, `.suggested_grade` contains `live_chebi` and
  `provisional`. A bare
  `"CHEBI:69478"` query issues no `es_search` call. An unknown name returns `[]`.
- QuickGO: `search("CB1")` maps to `UniProtKB:P21554`, returns ≥1 row whose
  `go_id` matches `GO:\d{7}`, with a resolved `go_name` and a non-empty
  `reference`; a receptor with no §VI accession and no UniProt-shaped input
  refuses with `ValueError`.
- Both lanes: a synthetic-cannabinoid synthesis query
  (`"how to synthesize K2 Spice JWH-018"`) raises `DiscoverRefused` **before** the
  injected fetcher is called (§V); an empty query and an over-ceiling
  `max_results` raise `ValueError`; an HTML/`OSError` fetcher surfaces
  `NetworkError`.
- `discover --sources chebi,quickgo` and the `/api/discover` handler both surface
  the new lanes; `synthesis` renders without `KeyError` (both `_SOURCE_KEYS` and
  `_SOURCE_DISPLAY` updated together).
- **Live proof (manual, documented):** a captured transcript of `ChEBISearcher`
  and `QuickGOSearcher` hitting the real APIs for Δ⁹-THC / CBD / CB1 — evidence
  the lanes work against production, not only fixtures.
