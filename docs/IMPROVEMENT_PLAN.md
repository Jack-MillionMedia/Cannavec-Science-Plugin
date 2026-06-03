# Cannavec Science — Improvement Plan (how to make the live product significantly better)

_Grounded in a measured assessment of the deployed product
(`cannavec-science-plugin.vercel.app`) and the codebase, 2026-06-03. Numbers
here are observed, not asserted; see §0._

---

## 0. Where it actually stands (measured)

| Dimension | Measured state | Source |
|---|---|---|
| **Answer coverage** | **50% curated hit-rate** (18/36 answerable questions returned ≥1 cited claim); **61%** even on *core* in-scope topics | 40-question eval, `answer --json` |
| **Retrieval quality** | **Broken, not just thin** — returned **10 citations for "cannabis in autism" but 0 for "oral CBD bioavailability", "how does THC impair driving", "what CYP enzymes does CBD inhibit"** — all topics the registry demonstrably covers (`driving_impairment.py` has 5 PMIDs; `interactions.py` has 88 CYP refs, 9 tacrolimus refs) | same eval + `grep` |
| **Citation integrity** | ~1 in 12 curated identifiers was **wrong or phantom** before 2026-06; now fixed and **CI-gated** across PMID/DOI/UniProt/ChEMBL | this session's audits |
| **Verified depth** | **~152 PMIDs / 43 DOIs** curated — narrow; breadth only via live search + a 7,500-row *un*verified candidate index | registry counts |
| **Claim-support** | Not solved — a v1 heuristic flagger only; "the cited paper supports the claim" is unproven | `claim_support.py` |
| **Product surface** | **A 46-line landing page over 5 API endpoints** (`answer`, `discover`, `rigor`, `health`, `registries`); no research UI, no auth, no metering | `public/index.html`, `api/` |
| **Architecture** | **Sound** — LLM fenced from being a source of truth, deterministic backbone, multi-identifier CI gate | code review |

**The one-sentence diagnosis:** the foundation is good and the citations are now trustworthy, but the product **can't reliably retrieve the knowledge it already has**, the verified tier is **thin**, and there is **no real product UX**. Fix those, in that order, and it goes from "useful demo" to "pay-worthy."

---

## 1. Biggest lever — fix retrieval (you already own the data)

The product is sitting on registry content it fails to surface. The current question→content path (intent classifier + keyword routing in `intent.py` → registry lookups) is brittle and misses obvious matches.

**Do this:**
1. **Build a semantic retrieval layer** over the union of (a) every curated claim, (b) the 7,500-row index, (c) cached abstracts. Hybrid **BM25 + embeddings**, then rerank with the **existing LLM reranker** (`ranker_llm.py`) — which is already built and fenced.
2. **Replace intent-routing with retrieval** as the primary path; keep intent as a light filter. "What CYP enzymes does CBD inhibit" must hit the 88 CYP rows.
3. **Constitutional fit (§X):** embeddings are a dependency, so the index + embedder live in the **optional/website layer** (same place the LLM reranker already lives), not the stdlib core. The core stays offline-testable; the website layer calls it.
4. **Target:** curated hit-rate **50% → 85%+**, and **zero "we have it but didn't find it" misses** on the eval set.

**Why first:** highest ROI, mostly a retrieval-engineering problem (not a content problem), weeks not quarters, and it makes everything downstream look better.

---

## 2. One answer, not two endpoints — blend curated + live

Today `/api/answer` (curated) and `/api/discover` (live) are separate. A researcher wants a single, coherent, cited answer.

**Do this:** in `compose_answer`, merge **curated claims** (verified, GRADE'd, retraction-checked) with **live discovery** (provenance-tagged `live_*`, reranked) into one brief that shows:
- curated-vs-live provenance visibly distinct (Constitution honesty rule),
- GRADE inline at each citation,
- a cross-source synthesis verdict (STRONG/MIXED/WEAK), already in `synthesis.py`.

**Why:** this is the realistic path to "answer any topic" — a verified curated **core** plus a citation-checked live **breadth**, in one place. It directly converts the "thin curated tier" weakness into a strength without lowering the evidence bar.

---

## 3. Solve claim-support — the differentiating, pay-worthy capability

"The right paper is cited" is done. "The paper actually supports the claim" is the hard problem no free tool solves.

**Do this:** build the LLM adjudicator on top of the deterministic flagger (`claim_support.py`), mirroring `ranker`/`ranker_llm`:
- fetch the cited abstract/full-text; the LLM judges support for the **magnitude/direction**, returns identifier-free verdict + **the supporting sentence quoted**; it never emits a citation or a GRADE;
- the deterministic flagger gates which claims go to the LLM; a human confirms contested ones.
- Surface per claim: **supported / partial / unverified**, with the quoted evidence.

**Why:** this is the capability that makes a researcher trust the output without re-reading every paper — the actual willingness-to-pay driver.

---

## 4. Grow the verified tier without growing the defect surface

The curated tier is ~152 PMIDs. Get it to ~1,500 **through the gate, not around it.**

**Do this — the human-gated flywheel (Constitution §IX):**
`live discovery → identifier audit (PMID/DOI/UniProt/ChEMBL) → claim-support check → human curator approves → curated`.
- **Prioritise by real demand:** instrument every answer; log the misses; promote the topics users actually ask about (the eval already shows where the holes are — CBD PK, driving, terpenes, sleep, IBD, fibromyalgia, migraine…).
- Never promote a row that hasn't cleared the same gate as a hand-curated one. This is the only way to scale depth without re-introducing the ~8% defect rate.

---

## 5. Build an actual product (the live site is an API stub)

`public/index.html` is 46 lines. That is not a product; it is documentation.

**Do this — a real research UI on the website/optional layer:**
- **Query → cited, GRADE-annotated answer**, with per-citation **verification badges**: resolves ✓ · not retracted ✓ · claim-supported ✓/⚠ · curated vs live.
- **"Show me the evidence" drill-down:** abstract + the supporting sentence (from §3).
- **One-click export:** BibTeX / RIS / CSL-JSON (the `bibliography.py` backend already exists) — drop straight into Zotero.
- **Expose the researcher tools you already have backends for:** PICO, GRADE evidence profile, power calc, protocol skeleton, SoF tables (`pico.py`, `grade_profile.py`, `power_calc.py`, `protocol_skeleton.py`, `sof.py`).
- **Make the moat visible:** a per-answer "trust panel" — *every citation re-verified in CI on `<date>`; N resolve, 0 retracted, M claim-supported.* The verification work is the differentiator; **show it.**

---

## 6. Make quality measurable and continuously enforced

- **Commit the coverage eval** (the 40-question harness) and run it in CI; track hit-rate over time; alert on regression. Turn "how comprehensive" from a guess into a dashboard.
- Keep **`citation-audit` required** in branch protection; add the **claim-support contradiction** gate.
- Publish a **trust report** endpoint/page (identifier count, % verified, last-audit date, defect rate) — the integrity work becomes a visible selling point, not an internal detail.

---

## 7. Productise for paying users

- **Auth + rate limiting + usage metering** on the API (it is currently open).
- **Tiers:** free (limited), pro (seat-based), enterprise (per-answer audit trail, private/internal corpora, SSO).
- **Validate demand** with 3 paid design-partner pilots (regulatory-affairs / medical-affairs / litigation) each producing one real defensible deliverable — the honest test of willingness to pay.

---

## Sequence & honest expected impact

| Order | Work | Expected impact | Effort |
|---|---|---|---|
| 1 | **Retrieval layer** (§1) | hit-rate **50% → ~85%** by recovering data you already have | weeks |
| 2 | **Unified curated+live answer + verification-visible UI** (§2, §5) | "answer any topic" becomes largely true; the moat becomes visible | weeks |
| 3 | **Claim-support adjudicator** (§3) | the pay-worthy, no-one-else-does-this capability | weeks–1 quarter |
| 4 | **Gated coverage expansion** (§4), instrumented by real misses | verified depth without new defects | continuous |
| 5 | **Productisation** (§6, §7) | from tool to business | parallel |

**The honest summary:** the architecture already supports all of this. The product is not held back by its design — it's held back by **(1) retrieval that can't find its own data, (2) thin verified depth, (3) unsolved claim-support, and (4) no UX**. Fix them in that order and the gap between the pitch ("query any topic → accurate verified insights at scale") and reality closes — credibly, because the verification layer underneath is now real.
