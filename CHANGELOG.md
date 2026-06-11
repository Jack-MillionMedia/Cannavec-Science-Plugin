# Changelog

## Chunk-level KB flywheel + rigorous evaluation + recursive learning (v0.8.0, 2026-06)

Turn live KB usage into a knowledge-base research backlog, and judge each chunk
rigorously against the credible literature. Offline suite 2,262 → 2,468 tests; the
verification core stays stdlib-only, Python ≥ 3.9, offline-deterministic.

- **Chunk flywheel (spec 037).** `audit-mcp --chunks` captures per-chunk
  retrieval / citation / accuracy / completeness issues from what the live KB
  returned — the model forwards the chunks; deterministic code computes every
  verdict (§II). `route-gaps` folds the queue into the `mc-knowledge-base`
  research backlog (gitignored per-area JSON + a regenerable
  `RESEARCH_BACKLOG.live.md`) and never touches the curated `RESEARCH_BACKLOG.md`
  (Agent Boundary Rule: flags, never authors).
- **Rigorous evaluation + recursive learning (spec 038).** `audit-mcp --chunks
  --rigorous` classifies each chunk as correct / incomplete / outdated /
  weakly-cited / misleading via the full rigor stack (`rigor_checks` +
  `reporting_rigor` + `banned_patterns` + grade-vs-wording) plus a claim-vs-corpus
  comparison (live discovery → GRADE-tiered sources). A false `misleading` is the
  worst error, so corpus contradiction is gated behind a strong-majority +
  minimum-sample bar **and** only runs on chunks on-topic for the query (an
  off-topic chunk is never judged against a query-built corpus). A per-chunk
  ledger makes the loop recursive (resolved / regressed / reopened-on-newer-
  evidence); `kb-health` shows the improvement trend; `eval-feedback` suppresses
  confirmed false positives. The verdict is deterministic; the only model seam
  (`review_claim` backend) is off by default (no API key required).
- **New operator CLI:** `audit-mcp --chunks [--rigorous]`, `route-gaps`,
  `kb-health`, `eval-feedback`. The five slash commands are unchanged.
- **Production + UX fixes.** Fixed the MCP-connect empty-`Bearer` trap (export the
  key first); a no-NCBI-key hint on slow live `verify`/`discover`; `setup --show`
  now exits 0 (informational); the cross-source synthesis no longer mislabels an
  off-topic indication (an epilepsy query no longer reports "addresses cannabis
  for autism"); honest ledger-write message when `CANNAVEC_HOME` is read-only.
- **New docs:** `docs/MCP_SETUP.md` (Claude Code / Desktop / web), `docs/QUICKSTART.md`
  (tester walkthrough), and expanded `docs/KNOWN_LIMITATIONS.md`.

## Production-readiness pass (2026-06)

A first-principles audit drove a four-phase cleanup; every change is test-first
and the offline suite stayed green throughout (2,239 → 2,262 tests).

- **P0 — safety + grounding fixes.** Closed a §I confabulation leak (an off-KB
  efficacy question phrased "evidence for CBD to treat &lt;disease&gt;" returned a
  confident wrong-disease GRADE brief; the structural backstop now scans every
  efficacy frame and the natural phrasings — treat / help with / useful in /
  works for) and two §V dosing bypasses (mid-sentence imperatives, `microdose`),
  with a research-prose carve-out so trial methodology is not over-refused.
- **P1 — doc truth + dead code.** Removed two dead eval drivers and the
  misleading `DEMO_SCRIPT.md` / `FLYWHEEL.md`; fixed the rotted `pyproject.toml`
  description (with a guard test) and a false constitution attribution in
  `CLAUDE.md`.
- **P2 — single source of truth.** Centralized the §I PMID/DOI/NCT identifier
  patterns (`_identifiers.py`), the §VIII flagged-status set + badge labels
  (`retraction.py`), and the per-lane HTTP fetcher + `NetworkError`
  (`_http.make_json_fetcher`); consolidated the split-brain slash-command surface
  onto the plugin's `commands/` (`/cannavec-science:*`).
- **P3 — bloat removal.** The post-MVP `archive/` tree (~19% of LOC) was removed
  from the working tree. It is import-isolated and fully recoverable from git
  history — `git checkout pre-mvp-teardown-2026-06-05` restores the pre-teardown
  state, or check out any pre-removal commit for the manifest and parked modules.

## Live-retrieval reliability + the grounding-layer flywheel (2026-06)

The live primary-source tier becomes reliable, offline-resilient, and self-growing —
without lowering the evidence floor. Three milestones, all test-first.

- **Reliability hardening.** The key-less PubMed lane failed ~2/3 of runs (transient
  HTTP 500 + body-read timeout). `_http` now retries 500 (a 5xx *server* error,
  mislabeled with the 4xx client errors) and adds `retry_fetch`, which retries the
  body `read()` so a `socket.timeout` — NCBI's most common key-less failure — is
  retried instead of escaping `retry_urlopen`'s scope. When PubMed is wholly down,
  **Europe PMC backfills** the same MEDLINE from a different host (fires only on
  failure; cross-source de-dup prevents convergence inflation). A key-less empty
  PubMed emits a one-line `NCBI_API_KEY` operator hint on stderr.
- **Verified-source cache (the flywheel).** A new stdlib-`sqlite3` store
  (`live_cache.py`) caches §I-verified, non-retracted **live** sources keyed by
  citation identifier. Write-through grows an offline KB from every discovery;
  read-fallback serves a query's cached sources when every upstream is down.
  Retraction is **re-checked on every read** (§VIII); cached rows stay live /
  provisional — never promoted to the curated registry (§IX), never fed to the
  static generator (M5-safe). This is **not** the archived §IX curation flywheel
  (that grew the static answer substrate); it accelerates the *grounding* layer.
- **Mechanism-question retrieval eval + Europe PMC quality fixes.**
  `evals/eval_live_retrieval.py` drives the real `discover` command over eight
  cannabis-mechanism questions and scores coverage / relevance / top-1. It surfaced
  two gaps, both fixed: the Europe PMC lane sent the *raw* interrogative question to
  the API (only PubMed distilled) — now distills to content terms; conference /
  meeting abstracts (pubType `Abstract`) polluted results — now dropped, with a 3×
  over-fetch so coverage holds. Measured: mean relevance 29% → 37.5%, top-1 on-topic
  37.5% → 50%, coverage 100%. Lifting the *specific* mechanism paper to #1 reliably
  is the semantic-retrieval frontier (next milestone), and the eval gates on that
  honest floor.

## Phase 2 — live comprehensiveness (spec 036, 2026-06)

The live primary-source tier graduates from a bare "provisional, unverified" list
into honest, on-topic, conservatively-graded breadth that widens coverage **without
lowering the evidence floor** — and `/cv:pdf` now packs it by default.

- **On-topic gate on the live tier.** Live rows are gated at the single merge point
  before they reach the brief: a wrong-indication efficacy row (e.g. a Dravet
  seizure trial surfaced for a Tourette / chronic-pain query) is **dropped**, with
  the same sibling-subtype precision the curated predicate has (Dravet vs TSC share
  the `epilepsy` family tag); a low-relevance context row is **demoted**, never
  silently lost. The Answer exposes `on_topic_filter_applied` + a dropped count.
- **Honest, metadata-only GRADE for live hits.** Each live hit is graded from the
  metadata its lane already returned (journal + pubtypes; preprint server name) —
  no per-finding network fetch — through the same GRADE engine as the curated tier,
  then **clamped**: a live journal hit is at most **Level C (Low certainty)**, a
  preprint at most **Level D**, never A/B. A non-empty grade rationale and a visible
  `· live · provisional` qualifier ride along; an ungradeable row degrades to the
  provisional string. A live grade can never raise the curated `evidence_summary`.
- **Graded live findings enter the §XI evidence surface.** A graded live finding's
  identifier + grade now survive a render losslessly, and **forging that grade
  upward is refused** by the citation-integrity gate — the live tier is held to the
  same no-inflation guarantee as a curated claim.
- **Informative live findings.** Each on-topic finding renders, where the data
  allows: a verified `abstract_snippet` (a true substring of the abstract, never a
  paraphrase), a `direction` (supports / refutes / neutral) sourced only from the
  existing synthesis attributor, and a Live-section search-provenance line
  ("Searched N live sources · M found · K on-topic").
- **On-topic convergence + honest synthesis prose.** Cross-source convergence is
  computed over post-gate rows only (a dropped row never manufactures agreement);
  sibling epilepsy subtypes canonicalize to one family cluster; and `synthesize`
  emits a human-readable prose line whose wording matches the verdict and **never
  asserts efficacy**.
- **`BRIEF_SOURCES` literature-breadth set.** A named superset of the lean serverless
  `DEFAULT_SOURCES` (adds Europe PMC + ChEMBL) used by the brief / PDF augment path;
  the lean web-API default is unchanged (registry invariants intact).
- **`/cv:pdf` packs on-topic graded live evidence by default.** The PDF brief now
  augments the verified curated core with the live frontier (`BRIEF_SOURCES`) before
  rendering — and **never crashes or refuses** because of it: an unreachable lane or
  a live finding that would trip the §XI gate degrades silently to the curated-only
  brief. `--no-live` opts out for a reproducible, offline curated-only artifact.
- **Cleanup.** The archived curation-flywheel weaver (`weave_verified_findings`) is
  now a clean no-op when the flywheel module is absent (post-MVP, removed from the tree),
  instead of a raised-and-swallowed `ImportError` that masked real errors.

## GRADE-certainty grading + expert credibility (2026-06)

- **GRADE-certainty wording, system-wide.** Every output surface (Markdown brief,
  JSON, CLI, `/cv:cite`, `/cv:pdf`) now leads with the recognized GRADE vocabulary
  — **High / Moderate / Low / Very low / Insufficient** certainty — with the letter
  kept as a small secondary auditable tag: "High certainty (Level A)". Single source
  of truth in `EvidenceLevel.certainty` + `display()` (spec 035).
- **Transparent per-source grade rationale.** The determinants already computed by
  `best_supportable_grade` (SR/RCT counts, pre-registration, power, single-study cap,
  missing-disclosure downgrades) are now surfaced as a short, honest rationale string
  alongside each citation — explicitly marking un-assessable factors (indirectness,
  publication bias) as "not assessed" rather than fabricating them.
- **Per-study certainty in the references/evidence list.** Each curated citation is
  rendered as a distinct entry with its own certainty, rationale, study type, year,
  and key result — not a flat link list.
- **Internal/system language removed from all rendered output.** Constitutional
  framing (`§…`, `M5`, "scaffolding to reason over") is stripped from every
  user-facing surface; guarded by `tests/test_no_system_language.py` regression.
- **§XI citation-integrity gate extended to the certainty vocabulary.** The
  citation-lossless + grade-inflation gate and its bypass-regression tests stay green
  under the new certainty wording; the audit is pinned by
  `tests/test_grade_value_unchanged_audit.py`, which asserts the GRADE *letter* per
  curated question is unchanged (display-only change, not a grade shift).

## Output layer — `/cv:pdf` + grade-inflation gate (2026-06)

- **`/cv:pdf` — the flagship output skill.** Renders the verified `Answer` into a
  polished, professional **evidence brief** (clinical-journal style): a
  self-contained, print-optimized HTML (stdlib-only, works anywhere) converted to
  PDF via the best available backend — headless Chrome → reportlab → "Print to
  PDF" — gracefully degrading. It is a **citation-lossless transform, never a
  document generator** (§XI / M5): every identifier and GRADE survives, none is
  inflated, and it renders an honest brief (or refusal) for anything unverified.
  New `pdf` CLI subcommand + `skills/cv-pdf/SKILL.md` (spec 034).
- **Closed the export.py grade-INFLATION hole.** The lossless gate guarded GRADE
  *loss* but not *inflation* — "Level A" beside a Level-B citation passed. New
  `export.grade_inflation_failures` (nearest-binding, the mirror of the adjacency
  check) makes presenting evidence above its verified grade a code-computed
  refusal; the GRADE-presence floor is now token-boundary-scoped ("Level Below"
  no longer masks "Level B"); `Answer.to_dict` now exposes `is_refusal`.
- **Hardened the gate against adversarial tampering** (driven by two rounds of a
  multi-agent red-team that broke earlier cuts). Over the evidence surface the
  inflation check (a) flags a grade attached to an *ungraded* citation
  (`flag_ungraded`), bound by bare identifier so a swapped URL can't dodge it;
  (b) scans **normalized visible text** — HTML entities decoded, tags/comments
  stripped, NFKD + combining-mark fold, script-confusable fold — so
  `Level&nbsp;A`, `Level <b>A</b>`, fullwidth/Cyrillic/Greek homoglyph grades,
  and "Grade A" synonyms can't slip a fake grade past an ASCII scan; (c) rejects
  content-hiding inline styles. Each found bypass is locked by a regression test.

## MVP — first-principles teardown (2026-06)

Refocused the project on its mission: **grounding an AI reasoner in verifiable
primary-source cannabis science**, not generating canned answers.

- **Demoted the static answer engine.** The brief is now produced by the model
  reasoning over live `discover` + `verify` + `rigor`; the curated registries are
  retained as a clearly-labelled offline *reference* tier, never the answer
  itself (Constitution M1/M5).
- **Slimmed the surface.** CLI 20 → 6 subcommands; the 5 slash commands
  (`research`, `ask`, `discover`, `verify`, `rigor`) now run the grounded flow.
- **Parked post-MVP machinery** (~9K LOC): the curation flywheel, meta-analysis
  stack, niche stat calculators, researcher scaffolders, and ops commands —
  preserved in git history, restorable via tag `pre-mvp-teardown-2026-06-05`.
- **Made the suites honestly green.** Quarantined 28 environmental socket-bind
  tests (skip-if-cannot-bind); re-scoped `run_evals.py` to gate on the MVP
  contract (verification / rigor / refusal / routing = 100%) while reporting
  curated-breadth coverage transparently as a tracked, non-gating roadmap.
- **Replaced the 66KB README** with a one-page front door; the full v0.7
  engineering reference is preserved at `docs/full-reference-v0.7.md`.

## v0.7 and earlier

Citation-accuracy, recall, and mechanism-claims build; quantitative
evidence-synthesis; live-discovery lanes; curated science registries. Full
detail: `docs/full-reference-v0.7.md`.
