# Spec 037 — Chunk-level KB flywheel: turn live usage into a research backlog

**Status**: Draft — 2026-06-11
**Constitutional gates**: §I (Primary-Source Or Refuse), §II (Deterministic
Verification, Not Deterministic Intelligence), §III (Test-First), §VII (GRADE
Honesty), §VIII (Retraction), §X (offline stdlib core); M5.

---

## North Star

Turn real user activity into a **knowledge-base improvement flywheel**. When the
live Cannavec MCP answers a question, every chunk it returned is judged for
**retrieval, accuracy, citation, and completeness** problems, and every problem
becomes a **logged research task tied to the exact chunk, the evidence, and a
correction path** — routed into the `mc-knowledge-base` repo's research backlog
for human review.

The existing flywheel (`source_audit.py`, spec 032/semantic) captures gaps at the
**identifier** level (false / missing PMIDs+DOIs). This spec extends it to the
**chunk** level — the unit the KB is actually authored and embedded in — and adds
a **router** that folds both layers into the KB repo's backlog.

This is the immune system + growth engine for the KB: users "train" it through
usage. It is **not** a content generator — per M5 and the repo's Agent Boundary
Rule, it **flags and routes**, it never authors clinical claims or changes grades.

## Why these four dimensions (chunk-level definitions)

| Dimension | A chunk has this problem when… | Deterministic? |
|---|---|---|
| **retrieval** | it is weakly relevant to the query (lexical-coverage floor), or *every* returned chunk is weak → the KB has no good answer (coverage gap) | yes (lexical) |
| **citation** | one of its identifiers is fabricated / retracted / misattributed, **or** it makes a graded clinical claim with **zero** citations | yes |
| **accuracy** | a cited abstract **contradicts** the chunk's claim; genuinely ambiguous (unsupported-but-not-opposed) cases are **routed to model review**, never auto-judged | hybrid |
| **completeness** | it is a thin stub (token floor), or its `evidence_grade` exceeds what its study composition supports (grade inflation) | yes |

Only the *ambiguous accuracy* case requires model judgement; it is flagged
`route: needs_model_review` and **not** resolved by this layer (§II: the model
proposes, deterministic code disposes; an unresolvable judgement is escalated,
not faked).

## Architecture (model proposes, code disposes)

`search_cannabis_kb` is an **external** MCP — its chunk prose reaches the model's
session, not the plugin's Python. So the capture point stays where the existing
flywheel already is: the `audit-mcp` CLI. Today the model forwards a flat
identifier list (`--sources`). We add a backward-compatible `--chunks` payload:
the model forwards *what the KB actually returned* as JSON, and **deterministic
code computes every verdict**. The model never asserts credibility; it only
forwards what it retrieved.

```
user question
  → search_cannabis_kb (external MCP) → chunk prose to the model
  → model forwards chunks:  audit-mcp --query Q --chunks '[{doc_id,h2_anchor,text,citations,score}]'
  → chunk_audit.audit_chunks()  → 4 deterministic detectors → ChunkIssue[]
  → appended to ~/.cannavec/improve_queue.jsonl   (one operator queue, additive line)
  → route-gaps --kb-root ~/mc-knowledge-base
       → cannabis/logs/live-gap/<area>.json   (gitignored, gap-audit schema + live fields)
       → RESEARCH_BACKLOG.live.md             (regenerable; never touches curated RESEARCH_BACKLOG.md)
```

## Data model (`chunk_audit.py`)

- `Chunk(doc_id, h2_anchor="", text="", citations=(), score=None)` — `.chunk_key`
  = `doc_id#h2_anchor`. Tolerant `from_dict()` parses the model-forwarded payload.
- `ChunkIssue(dimension, chunk_key, doc_id, h2_anchor, verdict, detail, evidence,
  recommended_action, route)` — mirrors `kb_audit.model.Finding`. `route ∈
  {improve_agent, deeper_research, quick_fix, needs_model_review}`.
- `ChunkAudit(query, chunks_seen, issues, logged_path)` — `by_dimension()`,
  `to_dict()`.

Detectors are **injected** (`verifier`, `abstract_fn`, `claim_detector`) so the
logic is fully offline-testable (§X). Defaults reuse the engine:
`source_audit._live_verifier` (citation), `claim_support.assess_support`
(accuracy), `kb_audit.checks.check_grade` (completeness/grade), and
`intent.topic_keywords` (retrieval lexical coverage).

The queue line is **additive**: `{"ts","query","chunk_issues":[…]}` written to the
same `improve_queue.jsonl` `source_audit` uses (one flywheel). A clean chunk run
logs nothing (mirrors `source_audit`). `summarize_improve_queue` is extended with
chunk tallies (new fields only; existing fields/tests unchanged).

## Routing (`gap_router.py`) — Agent Boundary Rule honored

Reads the operator queue (source-level **and** chunk-level), aggregates recurring
gaps (`occurrences` = real user-demand signal), maps each to one of the 11
`cannabis/` chapters / 10 `cannabis-faq/` clusters, and emits the repo's existing
**gap-audit JSON shape** (`title/kind/location/observation/classification/
severity/proposedAction` + live extras) plus a regenerable `RESEARCH_BACKLOG.live.md`.

- **Never authors clinical content.** Any gap needing a sourced clinical claim is
  `classification: deep_research` (mirrors the repo header's invariant); citation
  corrections / grade-inflation are `small_fix`.
- **Evidence-grade is human-only** — the router only *flags* grade inflation for
  downgrade review; it never sets a grade.
- **Priority** mirrors `gen_backlog.py` (deep_research + high-severity in the
  CLINICAL area set → P0; high elsewhere → P1; medium → P2; low → P3) with a
  **demand boost**: a gap recurring ≥ `DEMAND_BOOST_THRESHOLD` user queries is
  bumped up one band (live evidence of real demand beats audit-discovered gaps).
- Writes only under `cannabis/logs/live-gap/` (gitignored, like the other machine
  logs) + a root-level regenerable file. **The hand-curated `RESEARCH_BACKLOG.md`
  is never touched.**

## CLI

- `audit-mcp --query Q --chunks <file|inline-json>` — run the chunk audit (the
  `--sources` path is unchanged and may be combined).
- `route-gaps --kb-root PATH [--dry-run] [--review] [--json]` — fold the queue
  into the KB backlog. `--kb-root` defaults to `$CANNAVEC_KB_ROOT` or
  `~/mc-knowledge-base`. `--review`/`--dry-run` never write.

## Fable / Opus split (this build)

- **Fable** (engine, this spec): all deterministic detectors, capture, routing,
  CLI, tests, docs.
- **Opus-reserved, only *flagged* never auto-done**: ambiguous accuracy
  adjudication (`needs_model_review`), authoring corrected clinical text
  (`deep_research`), and evidence-grade changes (human-only). The flywheel
  *captures and routes* these; it does not resolve them.

## Test plan (§III — positive + negative each)

- `test_chunk_audit.py` — each detector clean vs. dirty; injected fns (offline);
  queue append + clean-run-logs-nothing; backward-compat (source_audit lines still
  parse); `summarize_improve_queue` chunk tallies.
- `test_gap_router.py` — area mapping, priority + demand boost, JSON shape,
  markdown render determinism, dry-run writes nothing, missing-queue tolerance,
  never-touches-RESEARCH_BACKLOG.md.
- `test_route_gaps_cli.py` — CLI both branches, isolated `CANNAVEC_HOME`/temp
  kb-root.

## Out of scope (v1)

Airtable `vectorStatus=needs-update` flagging of existing chunks (AGENT_PROTOCOL
path) — deferred; v1 stops at the backlog/JSON layer, matching the repo's own
audit-pass practice. No re-query of Pinecone (we capture what the *live* MCP
returned, not a different store).
