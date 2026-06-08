# Changelog

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
  preserved under `archive/`, restorable (see `archive/ARCHIVE_MANIFEST.md`).
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
