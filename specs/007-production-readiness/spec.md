# Feature Specification: Production-Readiness Hardening (v0.7)

**Feature Branch**: `claude/kind-shannon-KQgsY`

**Created**: 2026-05-24

**Status**: Implemented (foundational MVP work; extended by later specs)

**Input**: User request: "how close is this plugin to being production
ready and a great MVP plugin that will impress cannabis researchers"
followed by "yes add to spec-kit to pick up development tomorrow to
make it production ready."

## Background

Spec 006 shipped v0.6 research-domain-breadth: four new curated
registries (pain medicine, psychiatry/psychosis, driving impairment,
PTSD/anxiety/sleep), the reporting-rigor module (CONSORT / PRISMA /
STROBE / ROB-2 / ROBINS-I / AMSTAR-2), and the OpenAlex 13th live-
discovery lane. v0.6 surfaces are green at **1,501 unit tests** and
**173/173 offline eval prompts** across nine buckets. The scientific
content surface a working PI hits in the first hour of demo is in
place across all major cannabis-research domains.

A production-readiness audit against the v0.6 head of
`claude/kind-shannon-KQgsY` finds the **scientific backbone is
demo-ready but the production hygiene around it is not**. A
methodology-conscious cannabis researcher (the §IV audience) trying to
adopt Cannavec Science into their lab's workflow today hits the
following frictions within the first ten minutes:

- **G1 (P0, no CI)** — There is no `.github/workflows/` directory. The
  only quality gate is a human remembering to run
  `python3 -m unittest discover -s tests`. For a plugin whose entire
  trust story is "deterministic backbone enforced by tests" (Constitution
  §II + §III), the absence of CI is the single largest production-
  credibility gap. A green-badge `Tests` workflow + the eval suite
  passing on every push to `main` and every PR is table stakes.
- **G2 (P0, no QUICKSTART)** — The README is 35,675 bytes; the
  `pyproject.toml` description is one ~5,000-character paragraph of
  dense citations. A first-time visitor cannot find "what do I type to
  see this work" in under a minute. There is no `QUICKSTART.md`, no
  three-command onboarding, no expected-output example. The result is
  that the most-impressive-on-first-touch demo (the CBD-Dravet brief)
  is buried behind a citation wall. Researchers will bounce.
- **G3 (P0, no CHANGELOG)** — `docs/` contains six version-rating-delta
  files (`V02_RATING_DELTA.md` … `V06_RATING_DELTA.md`) but no canonical
  `CHANGELOG.md`. Researchers diff between versions to decide whether
  to upgrade their workflow; a tool that does not expose a single
  authoritative changelog signals "personal project" not "lab
  infrastructure." The rating-delta files are valuable but they are
  rationale, not changelog.
- **G4 (P1, scope-drift in spec 001)** — Spec 001's `plan.md` listed
  ~15 modules and a < 20,000 LOC ceiling and explicitly enumerated
  bioRxiv/medRxiv preprints as "v0.2 behind a constitutional amendment."
  Reality at v0.6: ~65 Python modules, ~34,000 LOC, preprints shipped
  under spec 002 (legitimised retroactively by the v0.x → v0.2
  constitutional crossing). A careful reviewer will find this divergence
  and either ask for an explanation or lose trust. The plan needs a
  reconciliation pass — either an updated module/LOC table at HEAD or a
  `docs/SCOPE_EVOLUTION.md` that walks v0.1 → v0.6 honestly.
- **G5 (P1, acceptance-gate evidence is partial)** — Spec 001's
  acceptance gates included `python3 -m cannavec_science verify
  28538134` returning the Devinsky-2017 record with
  `retraction_status: not_retracted`. In the current container
  (network-isolated), the verify call returns `?` for author / year /
  journal because PubMed E-utilities is blocked. The offline backbone
  works; the network gate is unverified at HEAD. A recorded-fixture
  smoke test (`tests/test_acceptance_gates.py`) that exercises every
  acceptance-gate command against canned fixtures would close the loop
  without depending on PubMed being reachable from CI.
- **G6 (P1, no demo-fixture mode)** — Three of the live commands
  (`discover`, `verify`, `source-health`) depend on PubMed / ChEMBL /
  CTGov / etc. being reachable. A laptop demo on conference WiFi is a
  known failure mode; spec 001 §"Risks & Mitigations" called this out
  but no `--demo` / `--fixture` flag exists at HEAD. A
  `--fixture-dir PATH` argument that replays canned JSON responses
  would make the demo bulletproof and the eval suite richer.
- **G7 (P2, README + pyproject prose is overwhelming)** — README.md
  (35 KB) reads like a release-notes archive concatenated with a
  citation bibliography. `pyproject.toml`'s `description` field is a
  60-line citation-dense paragraph that breaks `pip show cannavec-
  science` formatting. A surgical pass would (a) hoist the citation
  wall into `docs/PROVENANCE.md`, (b) leave a 200-line README that
  opens with the three-command quickstart and links to deeper docs,
  and (c) cut the `pyproject` description to ≤ 350 characters so PyPI
  / pip rendering is clean.
- **G8 (P2, no Development-Status discipline)** — `pyproject.toml`
  declares `Development Status :: 4 - Beta` which is honest given the
  absence of CI. After G1 + G2 + G3 land and stay green for two weeks,
  bumping to `Development Status :: 5 - Production/Stable` is
  warranted. Until then, the Beta label is the right honesty signal.
  This story documents the bump criteria and parks the bump itself
  behind those criteria.

## User Stories

Each story is independently testable; the MVP of v0.7 is US1 + US2 +
US3 alone (the three P0 stories). US4–US8 deepen production hygiene
but a researcher could adopt v0.7 with just the P0 trio.

### US1 — CI workflow (Priority: P1 ✦ ship as P0)

**As a** working cannabis researcher evaluating Cannavec Science for
my lab's literature-review pipeline,

**I want** a green CI badge on every PR proving the 1,501 tests and
173 eval prompts pass on a clean Python ≥ 3.9 environment,

**so that** I can trust the "deterministic backbone enforced by tests"
story without running the suite myself.

**Why this priority:** Constitution §II + §III claim test enforcement
as the load-bearing trust mechanism. A plugin that makes that claim
but ships with no CI is leaving its primary credibility signal on the
table.

**Acceptance criteria:**
- `.github/workflows/test.yml` runs `python3 -m unittest discover -s
  tests` on `push` to `main` and on every PR.
- A second job (or step) runs `python3 evals/run_evals.py` in offline
  mode (defaults).
- Matrix tests Python 3.9, 3.11, and 3.13 (the constitutional floor
  and two widely-deployed-in-academia versions).
- The README gains a Tests badge near the top.
- Workflow runs on ubuntu-latest only (stdlib-only means OS matrix is
  unnecessary for the MVP of this story).

### US2 — QUICKSTART (Priority: P1 ✦ ship as P0)

**As a** first-time visitor to the repository,

**I want** a one-page `QUICKSTART.md` that shows three commands and
what each one prints,

**so that** I can decide in under sixty seconds whether to keep
reading.

**Why this priority:** The most-impressive-on-first-touch surface is
the CBD-Dravet brief; today it is buried behind 35 KB of README. A
quickstart is the bridge between "I clicked the repo" and "I ran the
brief."

**Acceptance criteria:**
- `QUICKSTART.md` exists at repo root and renders in ≤ 200 lines.
- Three commands are shown verbatim with the first ~10 lines of their
  expected output:
  1. `python3 -m cannavec_science answer "CBD evidence in Dravet
     syndrome"`
  2. `python3 -m cannavec_science rigor "this cultivar tests at 22%
     THC by HPLC"`
  3. `python3 -m cannavec_science registries`
- A "What this is / what this is not" header section under 100 words
  surfaces the §IV researcher-only scope-lock honestly.
- The README opens with a link to `QUICKSTART.md` in the first 20
  lines.

### US3 — Canonical CHANGELOG (Priority: P1 ✦ ship as P0)

**As a** researcher comparing v0.6 to a hypothetical v0.7 before
upgrading my lab's pinned version,

**I want** a single `CHANGELOG.md` listing every shipped version with
its scope, added registries, added detectors, and breaking changes,

**so that** I do not have to read six rating-delta files to learn
what changed between two consecutive versions.

**Why this priority:** "What changed between versions" is the single
most-frequent diff a methodologically-conscious researcher runs
against a tool they adopt. The rating-delta files are rationale, not
changelog; they are kept but supplemented.

**Acceptance criteria:**
- `CHANGELOG.md` exists at repo root.
- One section per shipped version: 0.1 (MVP), 0.2 (elite-development),
  0.3 (routing-and-surfacing), 0.4 (industry-expert-depth), 0.5
  (clinical-pharmacology-depth), 0.6 (research-domain-breadth), 0.7
  (production-readiness — this spec).
- Each section lists: added curated registries with row counts, added
  rigor detectors, added live-discovery lanes, added CLI subcommands /
  flags, breaking changes (none expected), and a link to the
  governing spec under `specs/NNN-*`.
- Format follows Keep-A-Changelog 1.1.0 conventions
  (https://keepachangelog.com/en/1.1.0/) with `[Unreleased]` at the
  top.
- The README links to `CHANGELOG.md` in its first 20 lines (alongside
  the QUICKSTART link).

### US4 — Scope-evolution reconciliation (Priority: P2)

**As a** careful reviewer auditing whether the codebase matches its
own governing plan,

**I want** the divergence between spec 001's "15 modules / < 20,000
LOC" target and the v0.6 reality (~65 modules / ~34,000 LOC) to be
documented honestly,

**so that** I do not lose trust in the spec-kit governance when I
notice the divergence on my own.

**Why this priority:** Constitution §"Honest Surface Constraints"
says "coming soon is not a feature" and the same honesty applies to
spec drift. This is rationale work, not code work, but it directly
underwrites the spec-kit credibility story.

**Acceptance criteria:**
- `docs/SCOPE_EVOLUTION.md` exists and walks the v0.1 → v0.6 journey
  with one paragraph per version explaining (a) what shipped, (b)
  what the governing spec authorised, and (c) what (if anything) the
  ship exceeded the spec's text and how that was legitimised
  (constitutional v0.x → v0.2 crossing, subsequent spec adding the
  surface, etc.).
- The current module count and LOC count at HEAD are stated against
  spec 001's original targets.
- A "lessons for future specs" closing paragraph captures whether the
  spec-001 module-count ceiling was the right scoping mechanism or
  should be replaced with a different one.
- This document is referenced from `CHANGELOG.md`'s v0.7 section and
  from `specs/001-science-mvp/plan.md`'s top-of-file Status block via
  a one-line "see SCOPE_EVOLUTION.md for HEAD-vs-original reconciliation"
  note.

### US5 — Acceptance-gate smoke tests (Priority: P2)

**As a** CI runner with no PubMed network access,

**I want** the spec-001 acceptance gates to run as a single offline
unittest case using canned fixtures,

**so that** the acceptance gates remain provably green forever, not
just on the day they were first verified.

**Why this priority:** Constitution §"Honest Surface Constraints"
says "failure to add a regression test for a newly-fixed bug is
itself a regression." The acceptance-gate evidence is currently a
one-time human attestation; converting it to a fixture-backed
unittest closes the loop.

**Acceptance criteria:**
- `tests/test_acceptance_gates.py` exists with one test per gate:
  - `test_dravet_brief_has_three_claims_one_level_b()` — exercises
    `compose_answer` with the canonical Dravet question via the
    same injected-fetcher pattern the discovery tests use; asserts
    ≥ 3 cited claims with ≥ 1 Level A or B and zero banned-pattern
    hits.
  - `test_verify_28538134_returns_devinsky_2017()` — exercises the
    `verify` CLI with a fixture E-utilities + Crossref response;
    asserts Devinsky 2017 metadata and `retraction_status:
    not_retracted`.
  - `test_rigor_thca_vs_thc_conflation_fires()` — exercises the
    `rigor` CLI with `"this cultivar tests at 22% THC by HPLC"`;
    asserts a `THCA_VS_THC_CONFLATION` violation.
  - `test_slash_command_count_is_exactly_five()` — counts files in
    `commands/`; asserts equal to 5.
  - `test_python_loc_under_cannavec_science_under_50000()` — counts
    .py LOC; asserts under a documented HEAD ceiling (the original
    20,000 number is no longer realistic; document the new ceiling
    in `docs/SCOPE_EVOLUTION.md`).
- Fixtures live under `tests/fixtures/acceptance_gates/` as JSON.
- Total runtime of the new test file is under 200 ms on the same
  machine that runs the existing 2.4-second suite.

### US6 — Demo-fixture mode (Priority: P3)

**As a** plugin author demoing Cannavec Science on conference WiFi,

**I want** a `--fixture-dir PATH` flag on `discover`, `verify`, and
`source-health`,

**so that** the demo flows succeed even when the network is hostile.

**Why this priority:** Spec 001 §"Risks & Mitigations" identified
this risk and proposed the mitigation; v0.7 ships it. P3 because the
P0–P1 stories are higher-leverage for production-readiness; this is
demo-resilience.

**Acceptance criteria:**
- `python3 -m cannavec_science discover "CBD epilepsy" --fixture-dir
  evals/fixtures/demo/` replays canned JSON from `evals/fixtures/demo/
  pubmed_search/cbd_epilepsy.json`, `chembl_discover/cbd_epilepsy.
  json`, etc.
- Missing-fixture errors are explicit (`error: no fixture at
  evals/fixtures/demo/pubmed_search/<slug>.json — record one with
  --record-fixture-dir`).
- A `--record-fixture-dir PATH` flag captures live responses to the
  same on-disk layout so fixtures can be refreshed pre-demo.
- `tests/test_fixture_mode.py` exercises both replay and record paths
  against a temp directory with an injected fake fetcher.
- The demo script (`docs/DEMO_SCRIPT.md`) gains a "demo over hostile
  network" callout box that points at `--fixture-dir`.

### US7 — README + pyproject surgical trim (Priority: P3)

**As a** PyPI visitor reading the rendered project description,

**I want** the `pyproject.toml` description to be a single readable
sentence and the README to open with the QUICKSTART, not a citation
wall,

**so that** the first-touch surface matches the actual onboarding
flow.

**Why this priority:** The citation provenance is valuable — it is
the proof that the curated registries are evidence-backed — but it
belongs in a dedicated `docs/PROVENANCE.md`, not in pip's `Summary`
field or the README's opening screen.

**Acceptance criteria:**
- `pyproject.toml` `description` is ≤ 350 characters and renders
  cleanly in `pip show cannavec-science` output.
- The bulk of the citation density moves to `docs/PROVENANCE.md`
  organised by registry (`## Pain medicine — primary sources`, etc.).
- The README is reorganised to: (a) one-paragraph what-it-is opener,
  (b) badges (CI, license), (c) QUICKSTART link, (d) CHANGELOG link,
  (e) the "What's in the box" section with a row-count table per
  registry, (f) link out to PROVENANCE / DEMO_SCRIPT / SCOPE_EVOLUTION /
  spec-kit. No more than 600 lines of README at HEAD.
- The six `V0X_RATING_DELTA.md` files stay under `docs/` unchanged —
  they are version-rationale archives, not the README's job to
  replicate.

### US8 — Development-Status discipline (Priority: P3)

**As a** PyPI installer reading classifiers,

**I want** the `Development Status` classifier to track reality,

**so that** "Beta" or "Production/Stable" is a load-bearing signal,
not a default.

**Why this priority:** The bump itself is trivial; the discipline is
what matters. This story documents the criteria and parks the bump
behind them.

**Acceptance criteria:**
- `pyproject.toml` keeps `Development Status :: 4 - Beta` until ALL of
  the following hold for ≥ 14 consecutive days:
  - US1 CI workflow is green on every push to `main`.
  - US2 QUICKSTART, US3 CHANGELOG, and US5 acceptance-gate tests are
    in place.
  - Zero unresolved P0 or P1 issues open in the GitHub issue tracker.
- A `docs/PRODUCTION_STATUS_CRITERIA.md` enumerates the checklist and
  is referenced from `CHANGELOG.md`'s `[Unreleased]` section.
- When the criteria are satisfied, the bump to `Development Status ::
  5 - Production/Stable` ships in a documented v0.7.x patch release
  with a `CHANGELOG.md` entry; this story does NOT pre-commit to a
  version number for the bump.

## Out of Scope For v0.7

The following are deliberately deferred past v0.7 (most live in the
constitution's existing out-of-scope list):

- Anything that would broaden Constitution §IV (researcher-only).
- New curated registries (the v0.6 surface is the v0.7 baseline; v0.8
  may add domains, v0.7 is hygiene-only).
- New rigor detectors (same reason).
- New live-discovery lanes (13 sources is the v0.7 baseline).
- Signed reproducible artifacts (constitution out-of-scope list).
- KB flywheel / watchlist / persistent expert profiles (same).
- Multi-audience templates (Constitution §IV).
- Anything that requires a new runtime dependency (Constitution §X).
  The CI workflow itself runs under GitHub Actions' default Python
  install — no `pip install` required.

## Risks & Mitigations

- **Risk:** Adding CI surfaces test flakes that did not show up under
  manual runs (e.g. network-dependent tests that pass on the author's
  laptop because of `~/.cache/` artifacts). **Mitigation:** US1
  explicitly runs the suite on a clean ubuntu-latest with no warm
  cache. Any flakes surfaced are bugs to fix, not reasons to skip CI.
- **Risk:** Acceptance-gate fixtures drift from live PubMed responses
  over time. **Mitigation:** US6's `--record-fixture-dir` regenerates
  fixtures from live responses; documented in `docs/DEMO_SCRIPT.md`.
- **Risk:** Reorganising the README breaks links from the parent
  Cannavec plugin or from external posts. **Mitigation:** Preserve
  every heading anchor used by current `docs/V0X_RATING_DELTA.md`
  files; add a "moved to" note for any heading that does relocate.

## Acceptance Gate For v0.7

Before merging the v0.7 branch, ALL of the following MUST hold:

- `python3 -m unittest discover -s tests` exits 0 (unchanged from
  spec 001).
- `python3 evals/run_evals.py` returns ≥ 173/173 passes (unchanged
  from v0.6).
- `.github/workflows/test.yml` exists and is green on the PR.
- `QUICKSTART.md`, `CHANGELOG.md` exist at repo root.
- `docs/SCOPE_EVOLUTION.md`, `docs/PRODUCTION_STATUS_CRITERIA.md`,
  `docs/PROVENANCE.md` exist under `docs/`.
- `tests/test_acceptance_gates.py` exists and passes offline.
- `pyproject.toml` `description` is ≤ 350 characters.
- README opens with QUICKSTART + CHANGELOG links in its first 20
  lines.
- No new runtime dependency added (`dependencies = []` in
  `pyproject.toml` unchanged).
- The plugin remains researcher-only (Constitution §IV unchanged,
  no audience widening).
