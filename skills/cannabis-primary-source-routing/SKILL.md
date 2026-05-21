---
name: cannabis-primary-source-routing
description: Cannabis-primary-source router. Auto-activate when a cannabis-science question could be answered by more than one primary database — directs you to the right source (PubMed / ChEMBL / ClinicalTrials.gov / PubChem / PharmGKB / RCSB PDB / Open Targets / GWAS Catalog / BindingDB) before composing a claim. Encodes the Constitution §I "Primary-Source-Or-Refuse" gate into a per-question decision tree, with the matching `python -m cannavec_science discover --sources …` invocation for each lane.
version: 1.0.0
---

# Cannabis Primary-Source Routing

A cannabis-science answer is only as defensible as the primary source behind it. This skill picks the **smallest set of primary sources** that can answer the question. Always prefer one or two well-chosen sources over a broad fan-out.

This skill is the **research-router for the Cannavec Science researcher audience**. It is the cannabis-scoped sibling of the upstream life-science `research-router-skill`. The router itself does not call any tool — it tells you which live discoverers under `python -m cannavec_science discover` to invoke and in what order, then how to assemble their rows into a Constitution-§I-clean answer.

---

## Step 1 — Classify the question

Pick **one** primary lane (and at most one supporting lane).

| Lane | Triggering question shape | Primary source | Discover flag |
| ---- | ------------------------- | -------------- | ------------- |
| Compound structure / properties | "What is the structure / mass / SMILES of THCA?" | **PubChem** (CID) | `--sources pubchem` |
| Receptor binding (measured) | "What is the Ki of CBD at CB1?" | **ChEMBL** + **BindingDB** | `--sources chembl,bindingdb` |
| Receptor 3D structure | "Is there a crystal structure of CB2 with WIN-55,212-2?" | **RCSB PDB** | `--sources rcsb` |
| Target ↔ disease evidence | "What diseases is CB1 associated with?" | **Open Targets** | `--sources opentargets` |
| Cannabis-use genetics (human) | "Are there GWAS hits for cannabis use disorder?" | **GWAS Catalog** | `--sources gwas` |
| Pharmacogenomics of THC/CBD | "Does CYP2C9*3 slow THC metabolism?" | **PharmGKB** | `--sources pharmgkb` |
| Clinical efficacy / safety | "Does CBD reduce seizures in Dravet?" | **PubMed** (RCTs) + **ClinicalTrials.gov** | `--sources pubmed,ctgov` |
| Mechanism review | "How does CBD modulate PPARγ?" | **PubMed** (reviews) + **ChEMBL** | `--sources pubmed,chembl` |
| Frontier preprint (2024+ mechanism, eCBome, minor-cannabinoid pharm) | "What 2026 work is being posted on CB2 microglia?" | **bioRxiv** + **medRxiv** | `--sources biorxiv,medrxiv` |
| Adolescent / refractory / N-of-1 clinical (not yet in PubMed) | "Is there preprint clinical data on adolescent CBD pharmacokinetics?" | **medRxiv** | `--sources medrxiv` |

If two lanes both apply, the **clinical lane always wins** for evidence-grading purposes — a binding constant from ChEMBL cannot upgrade a clinical efficacy claim past Level C without a corresponding RCT.

---

## Step 2 — Resolve canonical identifiers FIRST

A claim without a primary identifier is, per Constitution §I, unsupported. Resolve identifiers **before** writing prose.

| Entity | Canonical ID system | Cannavec example |
| ------ | ------------------- | ---------------- |
| Phytocannabinoid | PubChem CID | Δ⁹-THC = CID 16078, CBD = CID 644019, THCA = CID 98523, CBDA = CID 12313961, CBG = CID 5315659, CBN = CID 2543, CBC = CID 30219, THCV = CID 93147, CBDV = CID 12302124 |
| Receptor (protein) | UniProt accession | CB1 = P21554, CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231, FAAH = O00519, MAGL = Q99685 |
| Receptor (gene / locus) | Ensembl ENSG | CNR1 = ENSG00000118432, CNR2 = ENSG00000188822, TRPV1 = ENSG00000196689, PPARG = ENSG00000132170 |
| 3D structure | PDB ID | CB1+AM11542 = 6N4B, CB1+MDMB-Fubinaca = 6KPF, CB2+WIN-55,212-2 = 6PT0, CB2+AM10257 = 5ZTY |
| Clinical trial | NCT ID | Epidiolex Dravet = NCT01362959 |
| Literature | PMID | always retrievable via `python -m cannavec_science verify <PMID>` |
| Pharmacogenomic annotation | PharmGKB ID | starts with `PA` (e.g., CYP2C9 gene = PA126, cannabidiol chemical = PA166159594) |
| Human genetic locus | GWAS Catalog accession | CUD GWAS = GCST007090, GCST006477, etc. |

If the question gives only a common name, your first step is to run the appropriate discoverer to resolve the ID:

```
python3 -m cannavec_science discover "CBD"   --sources pubchem    --max 1
python3 -m cannavec_science discover "CB1"   --sources opentargets --max 1
python3 -m cannavec_science discover "6N4B"  --sources rcsb       --max 1
```

---

## Step 3 — Compose the answer with provenance

Every row a discoverer emits already carries:

- `provenance` — one of `live_pubmed`, `live_chembl`, `live_ctgov`, `live_pubchem`, `live_pharmgkb`, `live_rcsb`, `live_opentargets`, `live_gwas`, `live_bindingdb`, `live_biorxiv`, `live_medrxiv`.
- `suggested_grade` — a `(Level X, provisional, live_<source>)` triple. The grade is **never** automatically promoted; it is a *hint* the human composer can use, not a binding registry assignment.
- `native_id`, `url`, `citation` — already formatted for inline citation.

When you compose a final answer, follow Constitution §VII:

- A row from PubChem alone caps the claim at **Level D** (compound metadata, not evidence).
- A row from ChEMBL / BindingDB / RCSB / Open Targets caps at **Level C** (mechanistic, not clinical).
- A row from PharmGKB caps at **Level B** if PharmGKB level-of-evidence ∈ {1A, 1B}, else Level C.
- A row from GWAS Catalog caps at **Level B** if genome-wide significant, else Level C.
- A row from PubMed / ClinicalTrials.gov can reach **Level B** (pre-registered powered RCT in major journal) or **Level A** when paired with a Cochrane / AHRQ / NICE systematic review.
- A row from **bioRxiv / medRxiv caps at Level D** regardless of grade hints — preprints are not peer-reviewed (per FR-202). If the preprint has been peer-published, the `published_version_doi` field surfaces the Crossref-resolved DOI; cite the peer-reviewed version when present.

The `python -m cannavec_science discover` pipeline reports all of the above per row plus a cross-source synthesis verdict (`STRONG / MIXED / WEAK / NONE`). Cite the verdict in the answer when more than one source contributed.

---

## Step 4 — Refuse what doesn't belong

This skill **does not lift** the safety, banned-pattern, or audience gates. In particular:

- A synthesis-route question for any synthetic cannabinoid (K2 / Spice / JWH-018 / AMB-Fubinaca etc.) hard-refuses **regardless** of which database the user is asking about. The preflight in `cannavec_science.discover_guard` enforces this for you — every discoverer in the registry above calls it as line 1 of `search()`.
- A jurisdiction / patient / cultivator / lab-QC / compliance question is out of audience scope per Constitution §IV. Do not synthesize an answer; redirect to the parent Cannavec plugin (which has those surfaces) or refuse.

---

## Worked examples

### Example 1 — "What's the canonical molecular formula and InChIKey for Δ⁹-THC?"

Lane: **structure**. Single source.

```
python3 -m cannavec_science discover "Delta-9-THC" --sources pubchem --max 1
```

Compose: `Δ⁹-THC (PubChem CID 16078; C₂₁H₃₀O₂; InChIKey CYQFCXCEBYINGO-IUEAMSCSSA-N) [Level D, live_pubchem]`.

### Example 2 — "Is there a PMID-anchored RCT showing CBD reduces seizures in Dravet syndrome?"

Lane: **clinical efficacy**. Two sources.

```
python3 -m cannavec_science discover "CBD Dravet syndrome" --sources pubmed,ctgov --max 5
```

Compose: cite Devinsky et al. 2017 (PMID 28538134), grade Level B; note NCT01362959 for protocol-level provenance. Use the synthesis block — if both PubMed and CT.gov returned rows clustering on Dravet, the convergence verdict will read `MIXED` or `STRONG`.

### Example 3 — "What's the measured Ki of WIN-55,212-2 at CB1?"

Lane: **binding**. Two sources cross-check.

```
python3 -m cannavec_science discover "WIN-55,212-2" --sources chembl,bindingdb --max 5
```

Compose: report ChEMBL bioactivity Ki + BindingDB Ki; if they disagree by > 10×, surface the disagreement explicitly. Cap claim at Level C.

### Example 4 — "Does CYP2C9*3 reduce Δ⁹-THC clearance?"

Lane: **pharmacogenomics**. Single source.

```
python3 -m cannavec_science discover "tetrahydrocannabinol" --sources pharmgkb --max 5
```

If PharmGKB level is 1A or 1B, compose at Level B; otherwise Level C. Always cite the PharmGKB clinicalAnnotation accession.

### Example 5 — "Is there a GWAS hit for cannabis use disorder?"

Lane: **human genetics**. Single source.

```
python3 -m cannavec_science discover "cannabis use" --sources gwas --max 5
```

Cite the GCST accession + PMID. Level B if genome-wide significant; else Level C.

### Example 6 — "Show me the crystal structure of CB1 with an agonist."

Lane: **structural biology**. Single source.

```
python3 -m cannavec_science discover "cannabinoid CB1 agonist" --sources rcsb --max 3
```

Cite the PDB ID + resolution + primary citation PMID. Level C (mechanistic).

---

## Anti-patterns

- **Do not** mention a primary database (PubChem, ChEMBL, …) in prose without showing the canonical identifier (CID, ChEMBL ID, etc.).
- **Do not** synthesize across sources before each row has been emitted by the deterministic discoverer — the cross-source de-duplication and convergence verdict live in `cannavec_science.synthesis`, not in your prose summarizer.
- **Do not** auto-promote a `live_*` row into a Cannavec curated registry. That path is intentionally out of MVP scope per Constitution §IX.
- **Do not** treat AlphaFold predicted structures (out-of-MVP) as equivalent to RCSB PDB experimental structures. The MVP only exposes RCSB; if the user explicitly asks about AlphaFold, name the gap honestly.

---

## Source-health pre-flight

Before a multi-source fan-out, probe liveness so the answer does not silently miss a lane:

```
python3 -m cannavec_science source-health \
    --sources pubmed,chembl,ctgov,pubchem,pharmgkb,rcsb,opentargets,gwas,bindingdb
```

If any source returns red, the discover command will mark that lane unreachable in its synthesis block. Do not paper over the gap — surface it.
