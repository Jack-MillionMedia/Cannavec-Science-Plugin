# Spec 027 — Cross-registry retrieval recovery (Improvement Plan §1)

**Status**: Implemented

**Created**: 2026-06-03

**Constitutional gates**: §I, §II, §III, §VI, §VII, §IX, §X.

## Why this priority

This is item **#1** of the Improvement Plan — the highest-ROI fix — and the
honest diagnosis is blunt: *the product cannot reliably retrieve the knowledge
it already holds.* `compose_answer` routes a prompt to curated rows through
~20 per-registry keyword/regex detectors. They are high **precision** but low
**recall**: word-order- and phrasing-sensitive. Measured failures on data the
registries demonstrably carry:

- **"how does THC impair driving"** → 0 claims. The driving detector wants the
  tokens `thc driving impair` contiguous and in that order; the prompt has
  "THC impair driving", so the registry's five rows never surface.
- **"what CYP enzymes does CBD inhibit"** → 0 claims, although the interaction
  registry holds 100+ CYP rows.

These are *"we have it but didn't find it"* misses — a retrieval-engineering
problem, not a content problem. The fix recovers existing, already-verified,
already-GRADE'd evidence; it makes everything downstream look better without
touching the evidence bar.

The approach is the one the plan names: a **BM25** relevance layer over every
curated row, with an **optional** embedding/LLM rerank stage injected exactly
like the existing `ranker_llm` backend. BM25's inverse-document-frequency
weighting is the load-bearing trick — generic tokens (`cannabis`, `cbd`) are
common across the corpus and contribute little, so a bare definitional prompt
stays below threshold, while a rare, specific token (`bioavailability`,
`driving`, `cyp2c19`) lights up exactly the rows that carry it.

**Constitution fit.** The BM25 core is pure stdlib (it reuses the tested Okapi
engine in `cannavec_science.ranker`), so `python3 -m cannavec_science` and the
offline suite still run with zero installs (§X). The embeddings layer the plan
describes is a dependency, so it stays in the optional/website tier — here it is
the injected `reranker` seam (duck-typed, like `ranker_llm`); the deterministic
BM25 is the always-available floor it would reorder, never undercut. Retrieval
surfaces **curated** rows only and changes only *which curated rows are found* —
never *what counts as evidence* (§I), never a grade (§VII), never a promotion
(§IX). It honours the spec-003-US2 cannabinoid scope filter, so it cannot
attribute one cannabinoid's evidence to another (§VI).

## User stories

### P1 — `retrieval.retrieve(query)` → ranked curated rows

`cannavec_science.retrieval` builds a BM25 corpus of every claim-bearing curated
row (the 18 registries the composer threads through `to_claim()`) and returns
the best lexical matches as `RetrievedRow`s. A row surfaces only past the gates
(a multi-term match above the BM25 floor with sufficient query coverage, or a
single decisive term above a higher floor), so generic-definition and
off-domain prompts return `[]`. Pure stdlib, deterministic, cached, offline.

### P2 — retrieval recovery in `compose_answer(..., retrieval=...)`

`compose_answer` gains a `retrieval` mode. `"fallback"` (default) runs retrieval
**only when the detectors produced no claim**, so it never disturbs a prompt the
detectors already answered — it cannot regress existing coverage, only recover
misses. `"augment"` makes retrieval the primary path (unioned with detectors);
`"off"` restores pre-§1 routing. Recovered rows attach through the normal claim
path, so retraction (§VIII), GRADE (§VII), and wording (§VII) enforcement all
still apply. Out-of-scope / deferred prompts keep their deliberate guidance
notes (spec 003 US9); a named-cannabinoid prompt recovers only rows about that
cannabinoid (spec 003 US2).

### P3 — optional rerank seam + CLI

`retrieve(..., reranker=...)` accepts a duck-typed `RankerBackend` (e.g.
`ranker_llm.LLMReranker`) that reorders the gated shortlist, provenance-gated so
it can only permute, never inject (§I / §IX). `answer --retrieval
{fallback,augment,off}` exposes the modes on the CLI.

## Acceptance gate

- `python3 -m unittest discover -s tests` stays green (2034 → 2059 tests).
- `compose_answer("how does THC impair driving")` and
  `compose_answer("what CYP enzymes does CBD inhibit")` each return ≥ 1
  primary-source-anchored claim; with `retrieval="off"` both return 0
  (the recovery — not some other change — is what fixes them).
- A detector-answered prompt ("CBD evidence in Dravet syndrome") is byte-for-byte
  unchanged with retrieval on vs off (fallback never fires when a claim exists).
- `compose_answer("HHC safety profile and adverse events")` recovers 0 claims and
  surfaces no CBD / Δ⁹-THC claim (cannabinoid scope filter).
- A cultivation/cultivar prompt keeps its out-of-scope guidance note.
- Generic ("What is CBD?", "cannabis") and off-domain ("hello world stock
  market") queries retrieve nothing.
- The injected reranker reorders the same shortlist set and cannot introduce an
  identifier the lexical stage did not surface.
- Five `routing_surfacing` eval prompts (detector-hostile phrasings) lock the
  win in `evals/canonical_research_questions.json`.
