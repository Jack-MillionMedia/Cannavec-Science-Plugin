# Spec 038 — Rigorous chunk evaluation + recursive KB refinement

**Status**: Draft — 2026-06-11
**Builds on**: spec 037 (chunk flywheel), spec 036 (live GRADE), spec 032 (kb-audit).
**Constitutional gates**: §I (primary-source), §II (deterministic verification, not
deterministic intelligence), §III (test-first), §VII (GRADE honesty), §VIII
(retraction), §IX (live discovery never auto-promoted), §X (offline stdlib core); M5.

---

## North Star

Make the chunk evaluator **as rigorous as the deterministic engine allows**: decide,
for each KB chunk, whether it is **correct, incomplete, outdated, weakly-cited,
misleading, or needs-improvement** — by comparing it against **as much credible
scientific research as the engine can reach**, so the KB becomes more meticulous
every cycle. And make the loop **recursive**: each pass remembers what it found, so
fixes are confirmed, regressions are caught, and *settled chunks re-open only when
new evidence appears*.

Two hard invariants:
1. **§II — the verdict is code, never the model.** Every status is computed by
   deterministic detectors. The optional LLM adjudicator (`review_claim(backend=)`)
   is identifier-free, grade-free, quote-gated, and a deterministic CONTRADICTION
   *always* escalates to human — the model never overturns an opposition signal.
2. **A false `misleading` on a correct chunk is the worst error.** Corpus-based
   `misleading` requires a strong majority of credible sources contradicting **and**
   a minimum sample; below the bar it softens to `incomplete`/needs-review. Honesty
   over aggressiveness.

Scientific chunks only (per the operator's scope). The ledger + loop are
content-type-agnostic, so widening later is a new detector set, not a re-architecture.

## The verdict taxonomy (rollup, most-severe-wins)

`misleading > outdated > weakly_cited > incomplete > needs_improvement > correct > unevaluated`

| Status | Deterministic signals (composed from the existing engine) |
|---|---|
| **misleading** | `assess_support` CONTRADICTION (cited *or* corpus source asserts the opposite direction); all 8 `rigor_checks` (isomer/receptor-id/dose-route/THCA·THC/matrix-unit/decarb/entourage); 6 `reporting_rigor`; most `banned_patterns` (cure/false-safety/absolutist/miracle/mechanism-to-clinic/…); `grade_wording_consistency` overclaim |
| **outdated** | retracted citation (§VIII); **stale** per the repo Truth-Layer (`today − last_verified_at > decay_horizon_days`, or past `next_grade_review_at`, or `decay_breach_count > 0`); **superseded** — the live corpus has credible sources newer than everything the chunk cites |
| **weakly_cited** | fabricated/misattributed citation; uncited clinical claim; GRADE inflation (`check_grade`); `cherry_picked`; **under-cited** — strong claim, low-tier cited sources, while higher-tier evidence exists in the corpus |
| **incomplete** | thin stub; **missing-evidence** — high-tier corpus sources (SR_FLAGSHIP/JOURNAL_RCT) the chunk doesn't cite; weak retrieval coverage |
| **needs_improvement** | `assess_support` UNVERIFIED (ambiguous → model review); **coherence conflict** with a sibling chunk |
| **correct** | every detector clean **and** the claim is corroborated by the weight of credible literature actually checked (positive confirmation, not mere absence of flags) |
| **unevaluated** | clean, but no corpus check ran — we did not *confirm* correctness, so we don't claim it |

## Claim-vs-corpus (the new rigor) — `chunk_eval.detect_corpus_issues`

Offline-testable chain (all injected): `corpus_fn(topic)` →
`run_discovery(runners=…)` → `answer.live_source_from_row` (tier/year/id) →
`answer._live_grade_for_row` (clamped `EvidenceLevel`; live ≤ C journal / ≤ D
preprint, never A — §IX). For a topic this yields credible sources each as
`{id, year, tier, level, has_abstract}`.

- **metadata-only (cheap, no network beyond discovery):** missing-evidence
  (incomplete), superseded (outdated), under-cited (weakly_cited).
- **claim-agreement (heavier — needs abstracts):** for ≤ `MAX_CORPUS_CHECK` top
  credible sources, fetch the abstract (`abstract_fn`) and run
  `review_claim(chunk_claim, abstract, backend=…)` → tally supported/contradicted.
  - `contradicted ≥ ⌈0.6·checked⌉` **and** `checked ≥ MIN_CORPUS_CONTRA` → `misleading`.
  - else record a `Corroboration{supported, contradicted, checked, score}` for the
    rollup (`correct` when supported is the clear majority).

Discovery is §IX: it **evaluates** the chunk, it never authors content or promotes a
candidate to a fact. `corpus_fn=None` (default) → the evaluator runs fully offline on
prose + citation + freshness signals only.

## Recursive learning — `chunk_ledger`

A longitudinal, deterministic, offline memory (`~/.cannavec/chunk_ledger.jsonl`). Each
evaluation appends `{ts, chunk_key, content_hash, status, corroboration, cited_ids,
evidence_snapshot}`. On the next pass, `diff(verdict)` compares to the last record for
that `chunk_key`:

- **resolved** — content changed (hash differs) and status improved to correct → stop re-flagging.
- **regressed** — was `correct`, now flagged → highest-priority alert.
- **reopened** — content unchanged, but the topic's `evidence_snapshot` now contains
  credible sources *newer* than last time → the chunk is potentially **outdated**
  though nobody touched it. **This is the engine of "refine over time."**
- **recurring** — same issue, same content → bump demand/priority.

`kb_health` is a per-cycle time series (counts by status, mean corroboration, #resolved,
#regressed, #reopened, P0 trend) so improvement is *provable*, not asserted.
`eval_feedback` is a minimal, reviewable false-positive store: an operator-confirmed
false flag suppresses that exact `(chunk_key, verdict)` until the chunk's content hash
changes — the evaluator's precision compounds upward as transparent data, never weights.

## Agent-Boundary mapping (mc-knowledge-base)

The evaluator **flags**, never authors. Verdicts map onto the repo's own vocabulary as
*suggested, additive* metadata for human sign-off: `outdated` → flag
`vectorStatus: needs-update` / note staleness (never edit `last_verified_at`);
`misleading`/coherence → suggest `contradiction_status: contested` +
`agent_review_state: pending_review`; grade problems → flag **downgrade** review only
(evidence-grade is human-only — never set, never upgrade). The router emits these as
backlog suggestions; it writes no markdown body and never touches `RESEARCH_BACKLOG.md`.

## Model boundary (where Opus may sit)

`review_claim(backend=…)` is the only model seam. Default `backend=None` → deterministic
floor (`assess_support`). When an Opus adjudicator is injected it is identifier-free,
grade-free, quote-gated (`verify_quote` drops any fabricated quote), and a deterministic
CONTRADICTION still `needs_human`. The model proposes a reading; code disposes the verdict.

## CLI

- `audit-mcp --chunks --rigorous` — run the full evaluator (rollup status + corpus when
  reachable) and record to the ledger; emit per-chunk status + corroboration.
- `kb-health [--json]` — show the KB-health trend across cycles.
- `route-gaps` — consumes the richer status: `misleading`/`outdated` in a clinical area
  → P0; `regressed` → P0.

## Test plan (§III — positive + negative per detector)

`test_chunk_eval.py` (prose-rigor aggregation; corpus missing/superseded/under-cited;
corpus-contradiction bar incl. the *below-bar does NOT flag misleading* case;
corroboration→correct; freshness stale/fresh; coherence conflict; rollup precedence;
content_hash). `test_chunk_ledger.py` (resolved/regressed/reopened/recurring; reopen on
newer evidence snapshot; kb_health series; feedback suppression). CLI tests. All offline
via injected `corpus_fn`/`abstract_fn`/`verifier`/`backend`/`now`.

## Out of scope (v1)

Wiring a live Opus adjudicator backend (the seam exists; default stays deterministic).
Writing to Airtable. Auto-applying any fix. Non-scientific content types.
