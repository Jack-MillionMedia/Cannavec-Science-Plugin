# Spec 036 — Live Comprehensiveness: on-topic, graded, packed evidence (Phase 2)

**Status**: Draft — design from the spec-036 scout audit, 2026-06-08
**Created**: 2026-06-08
**Constitutional gates**: §I (Primary-Source Or Refuse), §II (Deterministic
Verification), §III (Test-First), §VII (GRADE Honesty), §VIII (Retraction),
§IX (Live discovery never auto-promoted), §X (offline stdlib core),
§XI (Citable/Presentable/Traceable Output); M2, M5.

---

## North Star

Make every answer and `/cv:pdf` **packed with all relevant, credible, ON-TOPIC,
GRADE-graded live evidence about the question asked** — and nothing off-topic.
Today the live tier *ranks* discovered rows but applies **no relevance or
indication gate** (off-topic / wrong-indication rows attach) and assigns only a
hardcoded "provisional" string (**no real GRADE**). Phase 2 closes both holes,
honestly:

1. **On-topic only.** Hard-drop wrong-indication clinical-efficacy live rows
   (the confident-wrong-answer hole); soft-demote — never drop, never lead — the
   lower-relevance mechanistic/context rows that give the live tier its breadth.
2. **Credibly graded.** Grade each live primary-source hit through the EXISTING
   GRADE engine from metadata the lane **already returned** (no new network),
   capped conservatively (single-study → Low; preprint → Very low; **never High
   from a live hit**), always with a rationale and a visible "live · provisional"
   qualifier distinct from a curated grade.
3. **Gate-protected.** The graded live sub-section enters the §XI evidence
   surface, so a forged/inflated grade on a live finding is **refused**, exactly
   like a curated citation.
4. **Comprehensive.** Broaden the default live lane set + multi-query coverage so
   the brief is genuinely packed, while staying offline-deterministic and
   degrading gracefully when lanes are unreachable.

This builds entirely on Phase 1's GRADE-certainty + gate machinery and the
curated tier's proven on-topic gates. It does **not** touch `evidence_summary`
(live data never re-grades the curated core — §IX).

## Decisions (open questions resolved — expert-credible / honest)

- **Context lanes (ChEBI/QuickGO/Reactome/EFO):** demote, never drop, never lead.
  EFO/Reactome-pathway stay non-citable (already `None` from `live_finding_from_row`).
- **Efficacy vs mechanistic gating:** clinical-efficacy live rows get a HARD
  wrong-indication drop (mirror `_recovered_claim_is_wrong_indication`);
  mechanistic/preclinical rows get a SOFT relevance demotion only.
- **Live GRADE labels:** real conservative grade in the certainty vocabulary, but
  rendered with a `live · provisional` qualifier and in a clearly-headed section —
  AND covered by the §XI inflation gate. Never `High`/`Level A` from a live hit.
- **Grading inputs:** metadata ALREADY returned by the lane search only (PubMed
  hits carry journal+pubtypes; CTgov carries phase+enrollment). No per-finding
  network fetch. Degrade to provisional when metadata is absent/offline.
- **journal→tier truth:** a checked-in, reviewable `data/journal_tiers.json`.
- **Convergence:** computed on POST-gate on-topic rows only.
- **Comprehensiveness budget:** the answer/PDF augment path defaults to a
  literature-breadth lane set (pubmed, europepmc, ctgov, openalex) + multi-query;
  the lean serverless `DEFAULT_SOURCES=(pubmed,ctgov)` for the web API is unchanged.
- **Verified tier (archived flywheel):** OUT of scope — a separate spec. Phase 2
  fixes the silently-failing dead `weave_verified_findings` import so it no longer
  raises-and-swallows.

## Architecture (build order — each step ships positive + negative tests, §III)

### Step 0 — Guardrail tests first (RED)
Failing tests that define the Phase-2 contract before any code:
(a) an off-topic live row is dropped/demoted by `weave_live_findings`;
(b) a wrong-indication live efficacy row (`CBD for Tourette` + a Dravet efficacy
row) does not surface; (c) a graded live finding survives losslessly to PDF and a
forged inflation on it is caught.

### Step 1 — On-topic gate at the live tier (highest value, pure-offline)
`live.run_discovery`/`weave_live_findings` call `intent.indication_terms(prompt)`
+ `intent.topic_keywords(prompt)` once; after `rank_candidates`, apply:
- a **relevance floor** (reuse the BM25 scorer via new tunable `min_bm25`/
  `min_coverage` params on `rank_candidates`; looser than the curated tier so
  breadth survives);
- an **indication gate** for clinical-efficacy live rows reusing the curated
  `_recovered_claim_is_wrong_indication` logic (DROP wrong-indication);
- **DEMOTE not drop** for low-relevance context/mechanistic rows.
Run BEFORE synthesis so convergence is computed on on-topic rows. Emit
`on_topic_filter_applied` + `dropped_count` metadata. Never touch `evidence_summary`.

### Step 2 — Honest live GRADE (metadata-only)
New `evidence.py` helpers: `infer_tier_from_pubtypes(pubtypes)→SourceTier`,
`journal_tier_from_name(journal)→SourceTier` (backed by `data/journal_tiers.json`),
`study_design_signal_from_abstract(title, abstract)→(pre_registered, adequately_powered)`.
A `live_source_from_row(source_key, row)→Source|None` builds a `Source` from
already-present metadata; route through `Claim([source]).best_supportable_grade()`
(single-study caps), then **clamp to ≤ Low (Level C)** for journal live hits and
**Very low (Level D)** for preprints — never higher. Attach `grade` +
`grade_rationale` (reuse Phase-1 `grade_rationale`) + a `live · provisional`
qualifier to the finding. Degrade to the current provisional string when metadata
is missing. Every design→tier mapping gets an offline test.

### Step 3 — §XI gate covers graded live findings
Wrap the graded live-findings sub-section in `_ev()` markers (pdf_export) so
`grade_inflation_failures`/`grade_adjacency_failures` run over it; extend
`assert_render_faithful` accordingly. A forged "High certainty" on a live finding
is refused; an ungraded context row shows no grade. Add the lossless + anti-
inflation tests for the findings surface.

### Step 4 — Render comprehensively + drill-down
Each on-topic live study renders: certainty grade (+ `live · provisional`) +
rationale + an offline substring-verified `abstract_snippet` (port the archived
`_supporting_sentence`/`verify_quote`) + `direction` (supports/refutes/neutral
from synthesis where available) + a "searched <date> · N found · M on-topic"
provenance line. Update `to_markdown`/`_findings`/`to_dict` without losing GRADE
labels; serialization tests.

### Step 5 — Synthesis hardening + comprehensive retrieval
Canonicalize conditions via `intent` (epilepsy subtypes cluster); compute
convergence on post-gate rows; emit human-readable prose ("N sources agree X
improves Y"). Broaden the answer/PDF default lane set + add multi-query coverage
(broad botanical + compound×indication) for the literature lanes, bounded and
offline-degrading. (Effect-size pooling deferred — needs full text.)

## Non-goals (YAGNI / deferred)
- Verified-tier resurrection / human-curation pipeline (separate spec).
- Promoting live → curated (forbidden, §IX).
- Per-finding network metadata fetches; effect-size meta-analytic pooling.
- New slash command (the five are capped; `/cv:*` are skills).

## Risks & mitigations
- **Over-filtering kills breadth** → demote (not drop) non-efficacy rows; gate is
  observable (`dropped_count`); adversarial tests both ways.
- **Dishonest grading (M2/§VII)** → metadata-only, single-study caps, never A,
  always rationale, visibly provisional, ambiguous→lower tier.
- **Gate blindspot** → graded findings enter `_ev`; forged grades refused.
- **§X erosion** → grade only from already-returned metadata; offline-degrade;
  fully offline tests with stub fetchers.
- **Regression surface (2108 green)** → never touch `evidence_summary`; per-change
  positive+negative test; keep registry invariants + lossless render tests green.

## Acceptance criteria
1. A wrong-indication live efficacy row never surfaces; off-topic rows are
   dropped/demoted; on-topic breadth survives; `on_topic_filter_applied` +
   `dropped_count` exposed. Convergence computed on on-topic rows only.
2. Each on-topic live primary-source hit carries a real, conservative,
   metadata-derived GRADE (≤ Low for journal, Very low for preprint, never High)
   with a rationale and a visible `live · provisional` qualifier.
3. The graded live findings surface is inside the §XI gate: a forged inflation is
   refused; identifiers + grades survive losslessly to PDF.
4. The brief is packed: a broadened default lane set + multi-query coverage, with
   per-finding snippet + direction + a search-provenance line; offline-degrading.
5. `evidence_summary` is unchanged by live data (asserted after every step); the
   dead verified-tier import no longer raises-and-swallows; full suite green.
