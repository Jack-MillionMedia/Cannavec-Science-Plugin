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

> 🧪 **Testing it?** Install and exercise everything end-to-end in ~10 minutes with
> the **[tester quickstart →](docs/QUICKSTART.md)**. It works with no API keys (just
> slower); keys add semantic recall + the flywheel.

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
#   → flags the cure claim, the "non-psychoactive CBD" misuse, and the dose with no route
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

## Install

**As a Claude Code plugin** (recommended for researchers) — run these in Claude Code:

```text
/plugin marketplace add Jack-MillionMedia/Cannavec-Science-Plugin
/plugin install cannavec-science@cannavec-science
```

There is **nothing to `pip install`** — the verification core is stdlib-only
Python (≥ 3.9). Once installed, the five commands appear under the
`cannavec-science:` namespace (e.g. `/cannavec-science:research`).

**As a direct CLI** (developers / CI):

```bash
git clone https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin
cd Cannavec-Science-Plugin
python3 -m cannavec_science verify 28538134   # no dependencies to install
```

New here? Read [what to expect and what not to trust yet](docs/KNOWN_LIMITATIONS.md)
before you start.

### Set up your free NCBI key (recommended)

Live retrieval is faster and more reliable with your **own free NCBI API key**.
NCBI requires every user to use their own key (it's free, and sharing one key is
not allowed), so Cannavec never ships a key — you add yours once, in 2 minutes:

```bash
python3 -m cannavec_science setup
```

It walks you through getting the key and stores it **on your machine only**
(`~/.cannavec/credentials`, owner-readable, never shared, never committed). Check
status anytime with `setup --show`. (A local `.env` with `NCBI_API_KEY=…` works
too.) Without a key it still runs — just slower and more rate-limited.

### Semantic search + the KB flywheel (Cannavec)

Connecting the **Cannavec MCP** unlocks semantic/vector recall over the curated
cannabis KB — concept-level retrieval that keyword search misses (the biggest
recall upgrade for mechanism questions) — plus the chunk flywheel. **New users:**
get your API key and a copy-paste command from your dashboard at
**<https://cannavec.ai/dashboard/mcp-setup>**, or follow the full step-by-step (Claude
Code, Claude Desktop, and Claude.ai) in **[docs/MCP_SETUP.md](docs/MCP_SETUP.md)**.

The Claude Code path — **export the key in the same shell first** so the `Bearer`
header resolves (otherwise the token is empty and the MCP returns 401):

```bash
export CANNAVEC_API_KEY=<your-cannavec-key>          # from cannavec.ai/dashboard/mcp-setup
claude mcp add --transport http cannavec https://cannavec.ai/api/mcp \
  --header "Authorization: Bearer ${CANNAVEC_API_KEY}"
```

> The five research commands work **without** this step — the MCP only adds
> semantic KB recall and the chunk flywheel on top.

**Every source the KB returns is audited before you see it** — verified real and
not retracted (§I), so only verified-elite evidence is cited.

### The KB-improvement flywheel

As the KB is used, the engine turns its own weak spots into a research backlog —
**it flags problems and routes them for human review; it never authors content or
edits the curated knowledge base.** This is an **operator / terminal capability**
(run from a shell, not a slash command). The fastest way to see it is the
**[tester walkthrough → QUICKSTART](docs/QUICKSTART.md)**.

| Layer | What it does | Run |
|---|---|---|
| **Source audit** | Verifies every identifier the KB returns; logs fabricated/retracted (FALSE) and engine-found-but-missing (MISSING) sources. `/research` does this automatically when the MCP is connected. | `audit-mcp --review` |
| **Chunk flywheel** | Judges each returned chunk across **retrieval / citation / accuracy / completeness** and routes gaps into the `mc-knowledge-base` backlog (a regenerable `RESEARCH_BACKLOG.live.md`; the curated `RESEARCH_BACKLOG.md` is never touched). | `audit-mcp --chunks` · `route-gaps` |
| **Rigorous + recursive** | Classifies each chunk **correct / incomplete / outdated / weakly-cited / misleading** (full rigor stack + a claim-vs-corpus check against live literature), and records every verdict to a per-chunk **ledger** so fixes are confirmed (`resolved`), regressions caught, and chunks **re-open** when newer evidence appears. | `audit-mcp --chunks --rigorous` · `kb-health` |

A false `misleading` is the worst error, so the corpus-contradiction check sits
behind a high bar and only runs on chunks on-topic for the query. Specs:
`037-chunk-flywheel`, `038-rigorous-chunk-eval`.

**See it work (copy-paste, offline):**

```bash
python3 -m cannavec_science audit-mcp --query "CBD for epilepsy" --rigorous --no-corpus \
  --chunks '[{"doc_id":"cbd_epilepsy","h2_anchor":"Efficacy","text":"CBD is a miracle cure that is 100% effective and completely safe for all seizures.","citations":[]}]'
#  → ✗ MISLEADING — banned_misleading + uncited_claim …
python3 -m cannavec_science kb-health        # status distribution + improvement trend
```

Drop `--no-corpus` to also compare each claim against the **live** literature
(PubMed / Europe PMC / ClinicalTrials.gov), and run `route-gaps --kb-root <path>`
to fold the findings into a knowledge-base repo's backlog (the curated
`RESEARCH_BACKLOG.md` is never touched). A full tester walkthrough lives in
[docs/QUICKSTART.md](docs/QUICKSTART.md).

## The five commands (in Claude, as a plugin)

| Command | What it does |
|---|---|
| `/research` | Full grounded brief — the model reasons over live `discover` + `verify` + `rigor`. |
| `/ask` | Fast, verified Q&A — a tight answer behind a confirmed citation. |
| `/discover` | Live primary-source fan-out across scientific databases. |
| `/verify` | Spot-check one identifier (PMID / DOI / NCT / ChEMBL / UniProt): real? retracted? |
| `/rigor` | Run the deterministic phytochemistry + reporting-rigor + banned-pattern detectors on any text. |

Complete CLI surface (the tables above and below cover the common verbs): `python3 -m cannavec_science <answer|discover|verify|rigor|bibliography|cite|pdf|registries|kb-audit|setup|audit-mcp|route-gaps|kb-health|eval-feedback>`.

### Operator tools (not slash commands)

A separate, **read-only, operator-only** CLI surface — not part of the five
research commands and not exposed as a slash command:

| Tool | What it does |
|---|---|
| `kb-audit <path>` | Audits the science files of a knowledge-base directory — verifies every citation is real and not retracted, checks each claim against its cited source, and flags inflated evidence grades — then triages each file into `READY` / `IMPROVE` / `PASS`. Nothing is ever written back. See `specs/032-kb-audit/spec.md`. |
| `audit-mcp --chunks [--rigorous]` | Audit the chunks the live KB returned. Base mode checks retrieval/citation/accuracy/completeness; `--rigorous` classifies each chunk (correct / incomplete / outdated / weakly-cited / misleading) via the full rigor stack + a claim-vs-corpus comparison, and records each verdict to the recursive-learning ledger. `--review` ranks the recurring gaps. See `specs/037`–`038`. |
| `route-gaps` | Folds the live-retrieval improve-queue (identifier + chunk tiers) into the `mc-knowledge-base` research backlog: gitignored per-area JSON under `cannabis/logs/live-gap/` + a regenerable `RESEARCH_BACKLOG.live.md`. Flags, never authors; never touches the curated `RESEARCH_BACKLOG.md`. `--dry-run` / `--review` write nothing. See `specs/037-chunk-flywheel/spec.md`. |
| `kb-health` | The recursive-learning trend: status distribution over the latest verdict per chunk + `% correct` across cycles, so KB improvement is provable. |
| `eval-feedback` | Mark a rigorous-evaluation flag a false positive so it stops being re-queued (until the chunk's content changes). Tunes precision; never alters a credibility verdict. |

```bash
python3 -m cannavec_science kb-audit <path-to-kb> [--json] [--out report.md]
python3 -m cannavec_science route-gaps [--kb-root PATH] [--dry-run] [--review] [--json]
```

## What makes it credible (engineered, not asserted)

- **Primary-source-or-refuse** — no claim ships without a verified identifier; a model-authored sentence is held to the same bar as a curated row.
- **Retraction enforcement** — retracted papers are blocked, checked against a local registry and live source metadata.
- **GRADE honesty** — grades are computed by code, not by confident prose; a single RCT caps at Level B.
- **Phytochemistry precision** — every cannabinoid named by isomer, every receptor by UniProt accession, every dose by route.
- **Curated reference corpus** — **twenty-one curated science registries** (cannabinoids, terpenes, interactions, adverse events, pharmacokinetics, **endocrine**, and more; 230 rows) are kept as *labelled offline reference the model reasons over* — never presented as the answer itself.
- **Reproducible** — the verification core is stdlib-only Python (≥ 3.9), runs fully offline, and is covered by **2,495+ unit tests**. The engine is **79 modules**; run `python3 -m unittest discover -s tests`. (The "+" is a floor enforced by `tests/test_readme_claims.py` — the suite is asserted to meet it, so this number can never silently overstate reality.)

## Honest scope (what it does *not* do yet)

- **Coverage is narrow by design.** The tool is elite at *verification*; curated breadth (specific indications, deep clinical-pharmacology recall) is the roadmap, not a claim. It grounds via **live retrieval**, not by memorizing papers. `python3 evals/run_evals.py` reports this transparently: the deterministic **contract** buckets (verification / rigor / refusal / routing) are 100% green; the **coverage** buckets are tracked and visibly incomplete.
- **No individualized advice.** It answers "what does the evidence say," never "what should *you* take." Safety refusals are sovereign.
- **No legal / regulatory / dosing / cultivation / lab-QC surfaces.** Out of scope — this is primary-source research science only.

## Feedback (early users)

This is an early build — **[what to expect and what not to trust yet](docs/KNOWN_LIMITATIONS.md)**
sets honest expectations (narrow curated coverage, honest refusals, a couple of
known rough edges). If you try it, please tell us how a real research task went —
especially whether you could **trust** the output:
**[open an issue →](https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin/issues/new/choose)**
(early-user feedback, or a bug report for a crash or a wrong/fabricated citation).

## Documentation

| Guide | For |
|---|---|
| **[QUICKSTART.md](docs/QUICKSTART.md)** | Install + try everything end-to-end in ~10 minutes (the verification spine *and* the flywheel). Start here. |
| **[MCP_SETUP.md](docs/MCP_SETUP.md)** | Connect the Cannavec MCP — Claude Code, Claude Desktop, Claude.ai (web) + troubleshooting. |
| **[KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)** | What's intentional vs. a real rough edge — read before filing. |

## Roadmap

1. **One-command pipeline** — pipe `discover` → `verify` → `GRADE` into a single citation-lossless artifact (today it's three steps).
2. **Continuous retraction surveillance** — re-check cited PMIDs on a schedule so a paper retracted *after* it was used is flagged proactively.
3. **Per-chunk corpus topics** — build the rigorous claim-vs-corpus comparison per chunk (today it uses one corpus per query, and skips off-topic chunks to stay honest).
4. **Wire the optional model adjudicator** — the identifier-free, quote-gated `review_claim` backend seam exists; turning it on would sharpen claim-vs-corpus on compound claims.
5. **Widen curated coverage** — close the tracked coverage gaps the evals already surface.

---

*Mission, principles, and the full evidence-standard contract live in
`.specify/memory/constitution.md`. The detailed v0.7 engineering reference is
preserved at `docs/full-reference-v0.7.md`; version history is in
`CHANGELOG.md`. Post-MVP machinery (meta-analysis, curation flywheel, researcher
scaffolders) was removed from the working tree in the v3.0.0+ teardown and is
restorable from git history (tag `pre-mvp-teardown-2026-06-05`).*
