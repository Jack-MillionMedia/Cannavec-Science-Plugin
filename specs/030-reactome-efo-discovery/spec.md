# Spec 030 — Reactome pathway + EFO indication-normalization discovery

**Status**: Implemented

**Created**: 2026-06-04

**Constitutional gates**: §I, §II, §III, §V, §VI, §VIII, §IX, §X.

## Why this priority

Spec 029 gave the researcher the *chemistry* (ChEBI) and the *receptor function*
(QuickGO) behind a cannabis question. Two gaps remain that a working scientist
hits immediately after:

1. **"What *pathway* does this receptor act in?"** A GO molecular-function
   annotation tells you CB1 *enables* G-protein-coupled-receptor activity;
   it does not place that activity in a signalling cascade. **Reactome** does:
   CB1 (UniProt P21554) maps to `R-HSA-373076` (Class A/1 rhodopsin-like
   receptors) and `R-HSA-418594` (G alpha (i) signalling events), each a
   manually-curated pathway carrying a summary and **literature PMIDs**. That
   is the mechanistic context the eCBome registry describes in prose, now with
   stable pathway identifiers and primary-source references.

2. **"What is the *canonical name* for this indication?"** Cannabis questions
   arrive in lay or variant phrasing — "MS spasticity", "nerve pain", "Dravet".
   A precise literature query needs the controlled vocabulary. **EFO** (via
   EBI's OLS4) resolves a phrase to its ontology term (`neuropathic pain` →
   `EFO:0005762`; `multiple sclerosis` → `MONDO:0005301`) with definition and
   synonyms, so the researcher queries the right concept instead of guessing.

Reactome rows are §I-anchored by a verifiable pathway id **plus** the pathway's
literature PMIDs. EFO terms are an **explicit exception**: an ontology id is not
one of §I's primary-source anchors (PMID / DOI / ChEMBL / NCT / UniProt), so EFO
is a *normalization* lane — capped at Level D, framed as vocabulary context, and
it deliberately never weaves into an answer's citable evidence tier. Both are
stdlib `urllib` (§X), run the §V preflight first, carry `live_*` provenance, and
never auto-promote (§IX). Neither raises a curated GRADE (§VII).

## User stories

### P1 — Reactome lane: `reactome_discover.ReactomeSearcher` + full fan-out wiring

`ReactomeSearcher().search("CB1")` resolves the receptor name (or a UniProt
accession) via the §VI canon, calls Reactome `mapping/UniProt/{acc}/pathways`,
and for each human pathway fetches `data/query/{stId}` (best-effort) to attach
its `summation` and `literatureReference[].pubMedIdentifier`. It emits a frozen
`ReactomePathwayRow` carrying `pathway_id` (`R-HSA-…`), `display_name`,
`uniprot`, `is_disease`, `summary`, `pmids`, and `suggested_grade =
"Level D (provisional, live_reactome)"`. Pathways with a literature PMID sort
first (§I); the first PMID rides `pmid` for the §VIII retraction guard. Wired
into all fan-out seams (CLI `--sources reactome`, `live.SUPPORTED_SOURCES` +
`default_runners`, `synthesis._SOURCE_KEYS`/`_SOURCE_DISPLAY`, `ranker._ID_KEYS`,
CLI/API identifier display, `source_health`) with `Provenance.LIVE_REACTOME`. A
PMID-bearing pathway weaves into the blended brief via the existing `pmid` path;
a PMID-less pathway does not (it is not §I-citable).

### P2 — EFO lane: `efo_discover.EFOSearcher` + wiring

`EFOSearcher().search("neuropathic pain")` calls OLS4
`search?q={term}&ontology=efo` and emits an `EFOTermRow` per hit carrying
`efo_id` (`EFO:0005762`; the `obo_id` prefix names the true source ontology —
EFO / MONDO / HP), `label`, `ontology`, `description`, `synonyms`, `iri`, and
`suggested_grade = "Level D (provisional, live_efo)"`. Same preflight-first,
injected-fetcher, render contract; wired into the same seams with
`Provenance.LIVE_EFO`. **Citability contract:** EFO rows carry no §I primary
identifier, so `answer.live_finding_from_row` returns `None` for them — they
surface in `discover` / `/api/discover` / synthesis counts as normalization
context, but never as a citable finding in a composed answer.

### P3 — Routing, synthesis, and docs

`discover "CB1" --sources quickgo,reactome` returns receptor function *and*
pathways; `discover "MS spasticity" --sources efo` returns the normalized
indication term. The cross-source synthesis `per_source_counts` include
`reactome` and `efo` without manufacturing a cannabinoid convergence verdict
(both cluster off the cannabinoid axis). The `cannabis-primary-source-routing`
skill documents the routing rule (receptor pathways → Reactome; indication
normalization → EFO, explicitly not a citation source) and the README live-lane
inventory lists both. No curated grade is raised by either lane (§IX).

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green (the existing suite plus
  `tests/test_reactome_discover.py` and `tests/test_efo_discover.py`).
- **Fixtures are captured from the real APIs**: the Reactome happy-path fixture
  is the verbatim `mapping/UniProt/P21554/pathways` + `data/query/R-HSA-418594`
  responses; the EFO fixture is the verbatim `search?q=neuropathic pain` response.
- Reactome: `search("CB1")` returns rows whose `pathway_id` matches `R-HSA-\d+`,
  `uniprot == "P21554"`; the PMID-bearing pathway leads and exposes its `pmid`;
  an unknown receptor refuses with `ValueError`; no pathways → `[]`.
- EFO: `search("neuropathic pain")[0].efo_id == "EFO:0005762"`, `.ontology` is
  derived from the `obo_id` prefix (so an imported `HP:`/`MONDO:` term reports
  `HP`/`MONDO`), synonyms surface; **`live_finding_from_row("efo", row)` is
  `None`** (the normalization-not-evidence contract).
- Both: a synthetic-cannabinoid synthesis query raises `DiscoverRefused` before
  the fetcher is called (§V); empty query and over-ceiling `max_results` raise
  `ValueError`; an HTML/`OSError` fetcher surfaces `NetworkError`.
- `discover --sources reactome,efo` and `/api/discover` both surface the lanes;
  `synthesis` renders without `KeyError`.
- **Live proof (manual, documented):** captured transcripts of `ReactomeSearcher`
  and `EFOSearcher` hitting the real APIs for CB1 / CB2 and real indications.
