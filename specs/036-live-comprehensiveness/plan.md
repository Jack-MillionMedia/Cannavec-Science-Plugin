# Live Comprehensiveness (Phase 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. TDD, frequent commits. Steps use `- [ ]`.

**Goal:** Every answer + `/cv:pdf` packed with all relevant, credible, ON-TOPIC,
GRADE-graded live evidence about the question — nothing off-topic, nothing inflated.

**Architecture:** Insert an on-topic gate + honest metadata-only GRADE at the
single live merge point (`live.weave_live_findings`), reusing the curated tier's
proven `intent.indication_terms` + BM25 + `_recovered_claim_is_wrong_indication`
and the existing `best_supportable_grade` engine; bring the graded live surface
inside the §XI gate; broaden retrieval. Never touch `evidence_summary` (§IX).

**Tech:** stdlib-only Python ≥3.9; offline-deterministic; fetcher-injected lanes.

**Canonical commands:** full suite `python3 -m unittest discover -s tests`;
baseline is **2108 green**. After every task: suite green + `evidence_summary`
unchanged by live data.

---

## Key seams (from the scout audit — verify each before editing)
- `cannavec_science/live.py` — `run_discovery` (~218), **`weave_live_findings(answer, result, *, query)` (~266; the single merge point — ranks at ~315 then `add_live_finding` loop ~329-353)**, `augment_answer` (~357), `is_thin` (~395).
- `cannavec_science/answer.py` — `live_finding_from_row(source_key, row)` (~1297; identifier precedence + retraction; returns None for non-§I), `add_live_finding` (~340), `to_markdown` Live/Verified sections (~593-665), `to_dict` (~732-859), `_recovered_claim_is_wrong_indication` (~2611), `_drop_offkb_indication_efficacy_claims` (~2724), the dead `weave_verified_findings` flywheel import (~2033-2036).
- `cannavec_science/ranker.py` — `rank_candidates(query, candidates, top_k)` (~613), `candidates_from_discovery`, `provenance_gate`.
- `cannavec_science/retrieval.py` — `DEFAULT_MIN_BM25=6.0`, `DEFAULT_STRONG_BM25=11.0`, `DEFAULT_MIN_COVERAGE=0.34`, gate logic (~309-325).
- `cannavec_science/evidence.py` — `grade_from_source`, `apply_grade_modifiers`, `Claim.best_supportable_grade`, `SourceTier`, `_is_canonical_sr`, `grade_rationale`, `EvidenceLevel`.
- `cannavec_science/intent.py` — `indication_terms(text)` (~286), `topic_keywords(text)` (~176).
- `cannavec_science/synthesis.py` — `synthesize`, `build_claim_clusters` (~391), `_convergence_for_clusters`, `_SOURCE_KEYS`.
- `cannavec_science/pdf_export.py` — `_findings` (~407), `_evidence_surface` (~550), `assert_render_faithful` (~577), `_ev()` markers.
- Tests: `tests/test_live_discovery.py`, `tests/test_live_findings.py`, `tests/test_lane_registry_invariants.py`, `tests/test_pdf_export.py`.

---

### Task 1 (Step 0): Guardrail RED tests — define the Phase-2 contract

**Files:** Create `tests/test_live_ontopic_gate.py`, `tests/test_live_grade.py` (skeletons), `tests/test_live_findings_gate.py`.

- [ ] **Step 1: Write failing contract tests.** Read `tests/test_live_discovery.py` to learn how a discovery `result` + stub fetchers are built, then mirror that setup. Write:
  - `test_ontopic_gate.py::test_wrong_indication_efficacy_live_row_is_dropped` — compose `CBD for Tourette` (uncurated), inject (via stub lane fetchers) a live PubMed efficacy row about **Dravet seizures**; after `augment_answer`, assert that row is NOT in `answer.live_findings` (or is flagged off-topic), while an on-topic CBD/Tourette row survives.
  - `test_ontopic_gate.py::test_offtopic_low_relevance_row_is_demoted_not_dropped` — an on-domain-but-tangential row is present but ranked last / flagged, not leading.
  - `test_ontopic_gate.py::test_on_topic_breadth_survives` — a genuinely on-topic mechanistic row is retained (gate must not over-filter).
  - `test_live_findings_gate.py::test_forged_inflated_live_grade_is_refused` — render a brief with a graded live finding to PDF; forge its grade upward; `assert_render_faithful` raises.
  These will FAIL/ERROR now (the gate + grading don't exist). That's the point — they pin the contract.
- [ ] **Step 2: Run, confirm RED.** `python3 -m pytest tests/test_live_ontopic_gate.py tests/test_live_findings_gate.py -q` → fail.
- [ ] **Step 3: Commit** the RED guardrails: `git add tests/ && git commit -m "test(live): RED guardrails for Phase-2 on-topic gate + graded-finding §XI coverage"`.

---

### Task 2 (Step 1): On-topic gate in `weave_live_findings`

**Files:** Modify `cannavec_science/live.py` (`run_discovery`/`weave_live_findings`), `cannavec_science/ranker.py` (`rank_candidates` tunable floor), `cannavec_science/answer.py` (reuse indication logic — do NOT duplicate). Test: `tests/test_live_ontopic_gate.py`.

- [ ] **Step 1:** Add optional `min_bm25: float|None=None`, `min_coverage: float|None=None` params to `ranker.rank_candidates` that, when set, drop candidates whose BM25 score / query-term coverage fall below the floor (reuse the existing BM25 scorer; precedent: `retrieval.py`). Default `None` = current behavior (no regression).
- [ ] **Step 2:** In `live.weave_live_findings`, after ranking: (a) compute `prompt_inds = intent.indication_terms(query)`; (b) for each candidate finding that is a **clinical-efficacy** row whose indication mismatches `prompt_inds`, DROP it — reuse `answer`-level indication logic (expose a small reusable predicate from answer.py, e.g. `live_row_is_wrong_indication(row, prompt_inds)`, sharing `intent.indication_terms`; do not copy regex); (c) apply a LOOSE relevance floor (e.g. `min_bm25 = retrieval.DEFAULT_MIN_BM25 * 0.5`, tune via the RED tests) — rows below it are DEMOTED (sorted last + flagged), context-lane rows never dropped. Attach `on_topic` / `relevance_score` to the finding dict.
- [ ] **Step 3:** Thread `on_topic_filter_applied: bool` + `live_dropped_count: int` onto the Answer (or `live_synthesis`), surfaced in `to_dict`. Run the gate BEFORE `synthesis.synthesize` sees rows (so convergence uses on-topic rows).
- [ ] **Step 4:** Make the Task-1 on-topic tests pass. Run `tests/test_live_ontopic_gate.py` + `tests/test_live_discovery.py` (must stay green) + full suite. Confirm `evidence_summary` unchanged. Update any pinned synthesis/discovery expectations that legitimately change (convergence now on-topic-only) — keep strict.
- [ ] **Step 5: Commit** `feat(live): on-topic + wrong-indication gate at the live merge point (drop efficacy off-indication, demote low-relevance)`.

---

### Task 3 (Step 2): Honest metadata-only GRADE for live hits

**Files:** Modify `cannavec_science/evidence.py` (tier-inference helpers), create `data/journal_tiers.json`, modify `cannavec_science/answer.py` (`live_finding_from_row` → real grade). Test: `tests/test_live_grade.py`.

- [ ] **Step 1 (TDD):** Write `tests/test_live_grade.py` asserting `infer_tier_from_pubtypes`: `('Systematic Review','Meta-Analysis')→SR tier`; `('Randomized Controlled Trial',)→RCT tier`; `('Observational Study',)`/`('Case Reports',)`→low tiers; `()`→UNSUPPORTED/lowest; ambiguous→prefer LOWER. And `journal_tier_from_name('N Engl J Med')` → high tier; unknown → low. And the end-to-end cap: a live RCT in a top journal grades **Moderate at most → clamped to Low (Level C)** (never High/A from a live hit); a preprint → Very low (Level D). Run → RED.
- [ ] **Step 2:** Implement in `evidence.py`: `infer_tier_from_pubtypes(pubtypes)→SourceTier`, `journal_tier_from_name(journal)→SourceTier` (load `data/journal_tiers.json`: ~100-200 high-impact names → SR/RCT tiers; conservative fallback), `study_design_signal_from_abstract(title, abstract)→(pre_registered, adequately_powered)` (regex NCT/ISRCTN → pre_reg; `N=\d+`, enrollment ≥100 → powered). Create `data/journal_tiers.json` (NEJM, JAMA, Lancet, Nature, Science, BMJ, PAIN, Epilepsia, etc.).
- [ ] **Step 3:** Add `live_source_from_row(source_key, row)→Source|None` (in answer.py or evidence.py) building a `Source` from already-present row metadata (no network); compute `Claim([source]).best_supportable_grade()`; **clamp** to ≤ Level C for journal live hits, Level D for preprints — never above. Extend `live_finding_from_row` to attach `grade` (EvidenceLevel value), `certainty`, `grade_rationale` (reuse Phase-1 `grade_rationale`), and a `provisional=True` / `live · provisional` qualifier. When metadata is absent → fall back to the current provisional string.
- [ ] **Step 4:** Pass `tests/test_live_grade.py`; full suite green; `evidence_summary` unchanged; the JSON `to_dict` live findings now carry grade+rationale (update the serialization pin, keep strict).
- [ ] **Step 5: Commit** `feat(grade): honest metadata-only GRADE for live hits (single-study caps, never High, rationale + provisional qualifier)`.

---

### Task 4 (Step 3): Bring graded live findings inside the §XI gate

**Files:** Modify `cannavec_science/pdf_export.py` (`_findings` → wrap graded sub-section in `_ev`; `assert_render_faithful`), `cannavec_science/answer.py` (`to_markdown` findings render shows certainty grade). Test: `tests/test_live_findings_gate.py`, `tests/test_pdf_export.py`.

- [ ] **Step 1 (TDD):** Extend `tests/test_live_findings_gate.py`: a brief with an on-topic graded live finding → `assert_render_faithful` passes; forging the live finding's grade to a higher certainty → raises `FaithfulnessError`; an ungraded context row beside the finding shows no grade. Run → RED.
- [ ] **Step 2:** In `pdf_export._findings`, render each live finding's grade as the certainty display (`Low certainty (Level C) · live`), and wrap the GRADED live sub-section in `_ev(...)` markers so `_evidence_surface` includes it; ensure `grade_inflation_failures`/`grade_adjacency_failures` (already certainty-aware from spec 035) run over it in `assert_render_faithful`. Context/ungraded rows stay OUTSIDE `_ev` (covered only by the identifier floor). `to_markdown` Live section shows the certainty grade + `· live` qualifier.
- [ ] **Step 3:** Pass the gate tests + the 10 `TestRefusesKnownBypasses` + lossless. Full suite green.
- [ ] **Step 4: Commit** `feat(pdf): graded live findings enter the §XI evidence surface — forged live grade refused`.

---

### Task 5 (Step 4): Render comprehensively — snippet + direction + provenance line

**Files:** Modify `cannavec_science/answer.py` (`live_finding_from_row`, `to_markdown`, `to_dict`), `cannavec_science/pdf_export.py` (`_findings`), port `archive/cannavec_science/flywheel.py` `_supporting_sentence`/`verify_quote` (offline substring-verified). Test: `tests/test_live_findings.py`.

- [ ] **Step 1 (TDD):** Tests: a live finding carries an `abstract_snippet` that is a verified substring of its abstract (when an abstract is present); the Live section renders a "searched <date> · N found · M on-topic" provenance line; a finding's `direction` (supports/refutes/neutral) renders where synthesis provides it. Run → RED.
- [ ] **Step 2:** Port `_supporting_sentence(content_words, abstract)` + `verify_quote(quote, abstract)` from `archive/cannavec_science/flywheel.py` into a small offline module (or evidence/util); attach `abstract_snippet` in `live_finding_from_row` when the row carries an abstract (PubMed/EuropePMC do). Add the provenance line + `direction` (from synthesis per-finding attribution, Task 6) to `to_markdown`/`_findings`. Snippet must be a true substring (no paraphrase) — §I/M5.
- [ ] **Step 3:** Pass tests; full suite green; serialization pins updated (strict).
- [ ] **Step 4: Commit** `feat(live): per-finding verified snippet + direction + search-provenance line`.

---

### Task 6 (Step 5): Synthesis hardening + comprehensive retrieval

**Files:** Modify `cannavec_science/synthesis.py` (condition canonicalization via `intent`, post-gate convergence, prose, per-finding direction), `cannavec_science/live.py` (broaden default lane set + multi-query for the answer/PDF path). Test: `tests/test_synthesis.py`, `tests/test_live_discovery.py`.

- [ ] **Step 1 (TDD):** Tests: epilepsy subtypes (Dravet, Lennox-Gastaut) cluster to one condition; convergence verdict counts only on-topic (post-gate) rows; `synthesize` emits a human-readable prose string; the answer/PDF augment path queries the broadened lane set. Run → RED.
- [ ] **Step 2:** In `synthesis.build_claim_clusters`/`_convergence_for_clusters`, canonicalize the cluster condition via `intent.indication_terms`; exclude low-relevance/off-topic clusters from the verdict; emit `SynthesisBlock.prose` ("N sources agree X improves Y"); attach per-finding `direction`. In `live.augment_answer` (answer/PDF path only — NOT the web-API `DEFAULT_SOURCES`), default to a literature-breadth lane set (pubmed, europepmc, ctgov, openalex) and add bounded multi-query coverage (broad + compound×indication) for the literature lanes; degrade gracefully when a lane is unreachable.
- [ ] **Step 3:** Pass tests; registry invariants green; full suite green; `evidence_summary` unchanged.
- [ ] **Step 4: Commit** `feat(synthesis): on-topic convergence + prose + condition canonicalization; broaden live breadth for the brief`.

---

### Task 7: Fix the dead verified-tier import + end-to-end verification

**Files:** Modify `cannavec_science/answer.py` (the swallowed flywheel import). Test: docs + a smoke E2E.

- [ ] **Step 1:** Make `weave_verified_findings` no longer raise-and-swallow: guard the archived-`flywheel` import explicitly so a missing module is a clean no-op (verified tier stays empty) rather than a swallowed exception. Add a test that the import path is a clean no-op, not a silent failure.
- [ ] **Step 2:** E2E smoke (offline, stub fetchers): for `CBD for chronic pain` with `augment_live`, the brief contains on-topic live findings, each with a conservative grade + rationale + snippet, no wrong-indication row, `evidence_summary` still curated-only; `assert_render_faithful` passes on the PDF.
- [ ] **Step 3:** CHANGELOG + README/plugin test-count (use the floor pattern). Full suite green.
- [ ] **Step 4: Commit** `fix(live): verified-tier import is a clean no-op; docs + E2E for Phase-2 live comprehensiveness`.

---

## Self-review notes
- **Spec coverage:** Step 0→T1, Step 1→T2, Step 2→T3, Step 3→T4, Step 4→T5, Step 5→T6, verified-import + E2E→T7. Covered.
- **Invariant after every task:** full suite green; `evidence_summary` curated-only (live never re-grades core, §IX); registry invariants green; no gate/bypass regression.
- **Honesty guards:** live grade never exceeds Low (journal) / Very low (preprint); metadata-only (no per-finding network); snippet is a verified substring; off-topic dropped/demoted with an observable count.
