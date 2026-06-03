# Spec 028 — One blended brief (curated core + live breadth)

**Status**: Implemented

**Created**: 2026-06-03

**Constitutional gates**: §I, §II, §III, §IV, §VI, §VII, §VIII, §IX, §X, §XI.

**Carries a constitutional amendment** (v2.0.0 → v2.1.0). See "Constitutional
change" below.

## Why this priority

Today the two halves of the product live behind two doors. `/api/answer`
returns the **curated** brief (verified, GRADE'd, retraction-checked).
`/api/discover` returns the **live** primary-source fan-out (provenance-tagged
`live_*`, reranked) with a cross-source synthesis verdict. A researcher who
wants "the answer" has to call both and merge them in their head — and the
single most decision-useful signal, the **STRONG / MIXED / WEAK convergence
verdict**, never reaches the answer brief at all.

That split is also the honest framing of the product's biggest weakness: a
**thin curated tier**. The curated registries are deep but finite; for a novel
question they return little. The realistic path to "answer any topic" is not to
lower the evidence bar — it is to pair a verified curated **core** with a
citation-checked live **breadth** in *one* place, with the two tiers visibly
distinct so nobody mistakes a live preprint for a curated Level-A claim.

This spec makes that blend a first-class capability of `compose_answer` and the
default shape of the answer surface, converting "thin curated tier" from a
weakness into a strength **without touching the evidence bar**.

## What changed

### `compose_answer(..., live=...)` — the merge happens in the composer

`compose_answer` gains an opt-in `live` seam (`live`, `live_sources`,
`live_max`, `live_since`). When `live` is falsy / omitted (**the default**) the
composer is byte-for-byte the offline, deterministic curated path it always was
— the entire pinned suite is unchanged (§X). When `live` is truthy, after the
curated core is composed (and unless the prompt was refused), the live tier is
fanned out and **woven onto the same `Answer`**:

- **Provenance visibly distinct** (§IX honesty rule): curated claims render
  under `## Claims` with GRADE inline; live findings render under a fenced
  `## Live discovery — provisional, not curated` section, each tagged
  `live_<source>` with a *provisional* grade.
- **GRADE inline at each curated citation** (§XI): unchanged, now explicitly
  pinned by a blend regression test.
- **Cross-source synthesis verdict in the same brief** (§IX): the
  STRONG / MIXED / WEAK / NONE convergence from `synthesis.py` is captured into
  the new `Answer.live_synthesis` field and rendered at the top of the live
  section — no second endpoint required.
- **Reranked breadth** (not raw): the live rows are ordered by the deterministic
  `ranker` (BM25 relevance × study-design prior × recency) so the most useful
  primary sources surface first.
- **Retraction-checked breadth** (§VIII, deepened): each live finding's
  identifier is checked against the retraction registry; a retracted /
  expression-of-concern / under-correction hit is **badged (⚠) and pinned
  last**, never silently surfaced — independent of how query-relevant it is.

The live tier **never** raises or lowers the curated `evidence_summary` grade
and never auto-promotes (§IX). The weave degrades silently: a refusal, an
offline lane, or any error leaves the curated brief intact.

### One implementation, every surface

The merge logic lives in one place — `live.weave_live_findings(answer, result,
*, query)` — and is reused by `live.augment_answer` (and therefore
`live.answer_with_fallback`), by `compose_answer(live=...)`, and by the CLI
`answer --augment-live` path. So the library, the CLI, and the web API all
produce the identical blended brief, and the synthesis verdict + rerank +
retraction badging are guaranteed consistent.

### API: one answer, not two endpoints

`/api/answer` keeps its offline-safe default (curated core, Phase-3 auto-
fallback to live only when curated coverage is thin) so the offline test
contract holds. It gains a researcher-facing `blend=true` alias (for
`augment=true`) — the single call that returns curated core + live breadth +
synthesis — and surfaces the convergence verdict at the top level
(`"synthesis"`) as well as inside `answer.live_synthesis`. A client never has to
also call `/api/discover` and merge by hand.

## Constitutional change (v2.0.0 → v2.1.0)

The blend was **already permitted** by the constitution — §IX defines the
provenance tags + synthesis verdict + no-silent-promotion contract, §IV defines
the curated-core-plus-breadth path, §XI mandates inline GRADE. Nothing in the
constitution *restricted* this work, so no principle had to be weakened to ship
it at maximum quality. The amendment is therefore **additive and non-weakening**:

1. **§VIII deepened** — retraction enforcement now explicitly extends to the
   live tier (badge + sink, never silently cite). Previously §VIII spoke only to
   curated claims/citations; the live tier was un-checked. This is new, real
   behaviour, so it is written into the principle.
2. **§IX clarified** — the curated-core + live-breadth *single blended brief* is
   named the canonical delivery surface, with its three invariants pinned
   (provenance distinct, GRADE inline, synthesis verdict in the same brief), and
   the §X opt-in / offline-testable + no-re-grade guarantees restated.

MINOR bump: both strengthen existing evidence-or-safety principles without
breaking any surface and without broadening audience scope (§IV unchanged).

## Acceptance surface (`tests/test_blend.py` + `tests/test_api_handlers.py`)

- Default `compose_answer` stays offline: `live_synthesis is None`, no live
  section, no `live_synthesis` key in `to_dict`.
- `compose_answer(live=<injected runners>)` weaves curated + live + synthesis;
  curated GRADE is unchanged by the live tier.
- A refused prompt never fans out live (spy runner asserted un-called).
- Provenance is visibly distinct; GRADE is inline at each curated citation;
  the synthesis verdict renders in the brief.
- Convergence: three converging sources → STRONG; one source → WEAK.
- Reranking: the most query-relevant live row surfaces first.
- §VIII: a retracted live finding is badged and **pinned last even when it is
  the single most query-relevant row** (the adversarial case); a plain
  correction is neither badged nor demoted.
- `weave_live_findings` is pure (no I/O) given a result dict.
- API: `blend=true` (GET + POST) weaves and surfaces the synthesis verdict; the
  pre-existing default / augment / fallback contracts are unchanged.

All offline (§X): every test injects fake searcher runners; the network is
never touched.
