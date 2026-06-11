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

Crucially, **every source the KB returns is audited before you see it** — the
engine verifies each identifier is real and not retracted (§I), so only
verified-elite evidence is cited. Two by-products feed a **flywheel**: fabricated
or retracted KB sources (FALSE) and primary sources the engine found that the KB
lacked (MISSING) are appended to `~/.cannavec/improve_queue.jsonl` — the operator
review queue for improving the KB as it's used. (`audit-mcp` does this; the
`/cannavec-science:research` command runs it automatically when the MCP is
connected.) Review the backlog anytime with `audit-mcp --review` — it ranks the
recurring gaps **highest-impact first**, so you fix what fails most often.

The flywheel also works at **chunk** granularity: `audit-mcp --chunks` judges the
chunks the KB returned across **retrieval / citation / accuracy / completeness**
(weak relevance, fabricated/uncited citations, claim-vs-evidence contradictions,
thin or grade-inflated sections), and `route-gaps` folds the whole queue into the
`mc-knowledge-base` repo's research backlog — a regenerable `RESEARCH_BACKLOG.live.md`
plus gitignored per-area JSON — so real usage becomes logged, prioritized research
tasks. It **flags, never authors**: clinical gaps are `deep_research` and the
hand-curated `RESEARCH_BACKLOG.md` is never touched. See `specs/037-chunk-flywheel/spec.md`.

A deeper, **rigorous** layer goes further: `audit-mcp --chunks --rigorous`
classifies each chunk as **correct / incomplete / outdated / weakly-cited /
misleading** by composing the full rigor stack with a **claim-vs-corpus**
comparison against live credible literature — confirming correctness positively,
not just by the absence of flags. A false `misleading` is the worst error, so it
is gated behind a high corpus-contradiction bar. Every verdict is recorded to a
per-chunk **ledger**, which makes the loop recursive: fixes are confirmed
(**resolved**), regressions on settled chunks are caught, and chunks **re-open**
when newer evidence appears in the corpus. `kb-health` shows the improvement
trend across cycles, so progress is *provable*, not asserted. Like the rest of
the flywheel it **flags, never authors**. See `specs/038-rigorous-chunk-eval/spec.md`.

**See the flywheel work (copy-paste, offline).** Forward a chunk the way the model
would after a KB hit, then read the KB-health trend:

```bash
python3 -m cannavec_science audit-mcp --query "CBD for epilepsy" --rigorous --no-corpus \
  --chunks '[{"doc_id":"cbd_epilepsy","h2_anchor":"Efficacy","text":"CBD is a miracle cure that is 100% effective and completely safe for all seizures.","citations":[]}]'
#  → ✗ MISLEADING (high) · cbd_epilepsy#Efficacy [hash] — banned_misleading + uncited_claim …
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

Direct CLI: `python3 -m cannavec_science <answer|discover|verify|rigor|bibliography|cite|pdf|registries|kb-audit|setup|audit-mcp|route-gaps|kb-health|eval-feedback>`.

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
- **Reproducible** — the verification core is stdlib-only Python (≥ 3.9), runs fully offline, and is covered by **2,460+ unit tests**. The engine is **79 modules**; run `python3 -m unittest discover -s tests`. (The "+" is a floor enforced by `tests/test_readme_claims.py` — the suite is asserted to meet it, so this number can never silently overstate reality.)

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
scaffolders) was removed from the working tree in the v3.0.0+ teardown and is
restorable from git history (tag `pre-mvp-teardown-2026-06-05`).*
