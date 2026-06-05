# Cannavec Science

**A grounding-and-verification layer that makes AI trustworthy for cannabis-science research.**

AI models confidently cite cannabis-science papers that are **fabricated,
retracted, or misread** — silently poisoning expert research. Cannavec Science is
the deterministic layer that catches every one *before* a human trusts it. The AI
does the reasoning; this backbone retrieves the primary sources, verifies that
every identifier is real and not retracted, grades the evidence, and flags
unscientific language — so a researcher (or the AI working for one) can do
high-volume cannabis research at machine speed without sacrificing trust.

> It is **not** a chatbot and **not** a canned-answer engine. The deliverable is
> not an "answer" — it is **verified evidence an expert can stake their name on.**

---

## The problem, the user, the value

| | |
|---|---|
| **Problem** | LLMs hallucinate citations. In cannabis science — a field thick with retractions, marketing claims, and isomer confusion — a single wrong citation can sink a review, a protocol, or a regulatory submission. |
| **Who it helps** | Cannabis-science experts who can't afford a wrong citation — clinical researchers, pharmacologists, regulatory / medical-affairs analysts, clinicians — **and the AI assistants they use.** |
| **Why the output is valuable** | Every claim carries a primary-source identifier the backbone confirmed is real and not retracted, graded honestly (GRADE A–E), with unscientific language flagged. The model proposes; deterministic code disposes. |
| **What makes it reliable** | The credibility layer is **deterministic and offline-checkable, never probabilistic.** Same input → same verdict, every time. A made-up PMID returns FAIL with null fields; a retracted paper is blocked. |

## See it work (90 seconds)

```bash
# 1. Ground the AI — pull real, current primary sources live (nothing invented)
python3 -m cannavec_science discover "cannabidiol Dravet syndrome seizure" --sources pubmed,ctgov --max 5

# 2. Verify a real paper → PASS (read live from NCBI, retraction-checked)
python3 -m cannavec_science verify 28538134
#   → Devinsky, 2017, N Engl J Med — retraction status: clean — Verdict: PASS

# 3. THE MONEY SHOT — refuse a retracted citation that looks legitimate
python3 -m cannavec_science verify 32060308
#   → Verdict: FAIL — citation is retracted

# 4. Refuse a fabricated citation — it won't invent a paper
python3 -m cannavec_science verify 99999999
#   → Verdict: FAIL — PMID not found in PubMed

# 5. Catch unscientific language deterministically (offline, <0.2s)
python3 -m cannavec_science rigor "CBD is non-psychoactive and cures all seizures. We gave cannabis at 50mg."
#   → flags: cure_claim, non_psychoactive_cbd_misuse, dose-without-route
```

An ordinary AI would happily cite that retracted paper in step 3. This one
*can't* — and every verdict is machine-readable JSON (`--json`), so an AI or a
pipeline can gate on it.

## How the workflow operates

```
  question
     │
     ▼
  rigor / safety preflight ──(refuse)──► stop
     │
     ▼
  discover  ── live fan-out → PubMed · ClinicalTrials.gov · ChEMBL (+ more)
     │         ranked, real, current candidates (not facts yet)
     ▼
  verify    ── every identifier: real?  not retracted?   (PASS / FAIL)
     │
     ▼
  GRADE     ── deterministic evidence grade (A–E / Unsupported)
     │
     ▼
  the model reasons over the verified evidence → a citation-lossless,
  machine-checkable brief. Every claim has a confirmed identifier or it
  is graded Unsupported.
```

## The five commands (in Claude, as a plugin)

| Command | What it does |
|---|---|
| `/research` | Full grounded brief — the model reasons over live `discover` + `verify` + `rigor`. |
| `/ask` | Fast, verified Q&A — a tight answer behind a confirmed citation. |
| `/discover` | Live primary-source fan-out across scientific databases. |
| `/verify` | Spot-check one identifier (PMID / DOI / NCT / ChEMBL / UniProt): real? retracted? |
| `/rigor` | Run the deterministic phytochemistry + reporting-rigor + banned-pattern detectors on any text. |

Direct CLI: `python3 -m cannavec_science <answer|discover|verify|rigor|bibliography|registries>`.

## What makes it credible (engineered, not asserted)

- **Primary-source-or-refuse** — no claim ships without a verified identifier; a model-authored sentence is held to the same bar as a curated row.
- **Retraction enforcement** — retracted papers are blocked, checked against a local registry and live source metadata.
- **GRADE honesty** — grades are computed by code, not by confident prose; a single RCT caps at Level B.
- **Phytochemistry precision** — every cannabinoid named by isomer, every receptor by UniProt accession, every dose by route.
- **Curated reference corpus** — **twenty-one curated science registries** (cannabinoids, terpenes, interactions, adverse events, pharmacokinetics, **endocrine**, and more; 230 rows) are kept as *labelled offline reference the model reasons over* — never presented as the answer itself.
- **Reproducible** — the verification core is stdlib-only Python (≥ 3.9), runs fully offline, and is covered by **1,832 unit tests**. The engine is **65 modules**; run `python3 -m unittest discover -s tests`.

## Honest scope (what it does *not* do yet)

- **Coverage is narrow by design.** The tool is elite at *verification*; curated breadth (specific indications, deep clinical-pharmacology recall) is the roadmap, not a claim. It grounds via **live retrieval**, not by memorizing papers. `python3 evals/run_evals.py` reports this transparently: the deterministic **contract** buckets (verification / rigor / refusal / routing) are 100% green; the **coverage** buckets are tracked and visibly incomplete.
- **No individualized advice.** It answers "what does the evidence say," never "what should *you* take." Safety refusals are sovereign.
- **No legal / regulatory / dosing / cultivation / lab-QC surfaces.** Out of scope — this is primary-source research science only.

## Next logical improvements

1. **Semantic / vector retrieval** over the live corpus — ground the AI in *conceptually* relevant sources, not just keyword matches (the biggest grounding upgrade).
2. **One-command pipeline** — pipe `discover` → `verify` → `GRADE` into a single citation-lossless artifact (today it's three steps).
3. **Expert feedback loop** — let a researcher mark a candidate relevant/irrelevant and feed it back into ranking.
4. **Continuous retraction surveillance** — re-check cited PMIDs on a schedule so a paper retracted *after* it was used is flagged proactively.
5. **Widen curated coverage** — close the tracked coverage gaps the evals already surface.

---

*Mission, principles, and the full evidence-standard contract live in
`.specify/memory/constitution.md`. The detailed v0.7 engineering reference is
preserved at `docs/full-reference-v0.7.md`; version history is in
`CHANGELOG.md`. Post-MVP machinery (meta-analysis, curation flywheel, researcher
scaffolders) is parked under `archive/` and is restorable — see
`archive/ARCHIVE_MANIFEST.md`.*
