# Implementation Plan: v0.7 Production-Readiness Hardening

**Spec**: `specs/007-production-readiness/spec.md`

**Status**: Draft — approved for `/speckit-tasks` tomorrow

## Architecture

v0.7 is **hygiene work, not new science.** Zero new
`cannavec_science/` modules, zero new registries, zero new detectors,
zero new live-discovery lanes. Every change is in `.github/`, `docs/`,
the repo root, `tests/`, and surgical edits to `pyproject.toml`,
`README.md`, and (US6 only) `__main__.py` + a handful of discover
modules.

```
.github/
└── workflows/
    └── test.yml                  (NEW, US1)

QUICKSTART.md                     (NEW, US2)
CHANGELOG.md                      (NEW, US3)

docs/
├── SCOPE_EVOLUTION.md            (NEW, US4)
├── PRODUCTION_STATUS_CRITERIA.md (NEW, US8)
├── PROVENANCE.md                 (NEW, US7 — citation density relocated here)
└── DEMO_SCRIPT.md                (MODIFIED, US6 — fixture-mode callout)

tests/
├── test_acceptance_gates.py      (NEW, US5)
└── fixtures/
    └── acceptance_gates/         (NEW, US5)
        ├── pubmed_28538134.json
        ├── crossref_devinsky_2017.json
        └── retraction_28538134.json

evals/
└── fixtures/                     (NEW, US6 — only if US6 lands in v0.7)
    └── demo/
        ├── pubmed_search/<slug>.json
        ├── chembl_discover/<slug>.json
        └── ctgov_discover/<slug>.json

cannavec_science/                 (MODIFIED, US6 ONLY)
├── __main__.py                   (--fixture-dir + --record-fixture-dir flags)
├── pubmed_search.py              (fixture-replay branch in fetcher)
├── chembl_discover.py            (same)
├── ctgov_discover.py             (same)
└── pubmed_verify.py              (same)

pyproject.toml                    (MODIFIED — description trim, version 0.7.0)
README.md                         (MODIFIED — surgical reorg per US7)
.claude-plugin/plugin.json        (MODIFIED — version 0.7.0)
cannavec_science/__init__.py      (MODIFIED — version 0.7.0)
```

## Story-by-story implementation

### US1 — CI workflow (`.github/workflows/test.yml`)

Single workflow, two jobs:

```yaml
name: Tests
on:
  push:
    branches: [main]
  pull_request:

jobs:
  unittest:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.11', '3.13']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Unit tests
        run: python3 -m unittest discover -s tests
      - name: Offline eval suite
        run: python3 evals/run_evals.py
```

Notes:
- No `pip install -e .` step required — stdlib only. The unittest
  discover works against the repo as-is.
- No `--include-live` on the eval run — keeps CI offline.
- Add a `Tests` badge to the top of `README.md` pointing at
  `https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin/actions/workflows/test.yml/badge.svg`.

### US2 — QUICKSTART.md

200-line maximum. Sections (with hard caps):

1. `# Cannavec Science — Quickstart` (1 line)
2. `## What this is` — 4 lines: researcher-only cannabis-science
   plugin, deterministic backbone, stdlib-only, primary-source-anchored.
3. `## What this is NOT` — 4 lines: patient advice, clinician tool,
   cultivator tool, legal/jurisdictional surface.
4. `## Install` — `git clone` + `cd`. No `pip install` because
   stdlib-only.
5. `## Three commands to try` — three fenced bash + output blocks,
   each ≤ 20 lines of output, lifted verbatim from a live run of:
   - `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome"`
   - `python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC"`
   - `python3 -m cannavec_science registries`
6. `## Where to go next` — links to `CHANGELOG.md`,
   `docs/DEMO_SCRIPT.md`, `docs/PROVENANCE.md`, the spec-kit folder.

### US3 — CHANGELOG.md

Keep-A-Changelog 1.1.0 format. Sections, top-to-bottom:

```
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(Production-readiness criteria tracked in
`docs/PRODUCTION_STATUS_CRITERIA.md`.)

## [0.7.0] — 2026-05-2X
### Added
- CI workflow (`.github/workflows/test.yml`)…
- `QUICKSTART.md`…
- `CHANGELOG.md` (this file)…
- `tests/test_acceptance_gates.py`…
### Changed
- `pyproject.toml` description trimmed to ≤ 350 chars…
- README reorganised per spec 007 US7…
### Spec
- `specs/007-production-readiness/`

## [0.6.0] — 2026-05-24
### Added
- Pain medicine registry (≥ 7 rows)…
- Psychiatry / psychosis registry (≥ 6 rows)…
- Driving impairment registry (≥ 5 rows)…
- PTSD / anxiety / sleep registry (≥ 5 rows)…
- Reporting-rigor module (6 EQUATOR detectors)…
- OpenAlex live-discovery lane…
### Spec
- `specs/006-research-domain-breadth/`

[…0.5.0 / 0.4.0 / 0.3.0 / 0.2.0 / 0.1.0…]
```

Each version section: distill `docs/V0X_RATING_DELTA.md` into bullets;
keep the rating-delta files intact under `docs/`.

### US4 — docs/SCOPE_EVOLUTION.md

One paragraph per version. Template:

```
## v0.X — <name>

**Spec authorised:** <one-line summary>.
**Shipped:** <one-line summary>.
**Delta:** <none | the following surfaces exceeded the spec's text and
were legitimised by …>
**Module count at end of version:** N modules / M LOC.
```

Close with a "lessons" paragraph reflecting on whether the spec-001
"15 modules / < 20,000 LOC" ceiling was the right scoping mechanism.

### US5 — tests/test_acceptance_gates.py + fixtures

Test cases:

```python
class TestSpec001AcceptanceGates(unittest.TestCase):
    def test_dravet_brief_has_three_claims_one_level_b(self):
        # Inject a fake fetcher; compose_answer with canonical Dravet question;
        # assert claim count, grade distribution, banned-pattern count.

    def test_verify_28538134_returns_devinsky_2017(self):
        # Load tests/fixtures/acceptance_gates/pubmed_28538134.json
        # and crossref_devinsky_2017.json; pass via injected fetcher to
        # the verify entrypoint; assert author, year, journal, retraction
        # status.

    def test_rigor_thca_vs_thc_conflation_fires(self):
        # Pure-CPU; no network. Call rigor.run_rigor_checks() with
        # "this cultivar tests at 22% THC by HPLC"; assert
        # THCA_VS_THC_CONFLATION present.

    def test_slash_command_count_is_exactly_five(self):
        # Count *.md under commands/; assert 5.

    def test_python_loc_under_cannavec_science_under_ceiling(self):
        # Sum LOC of cannavec_science/*.py; assert < CEILING where
        # CEILING is the documented HEAD-realistic number from
        # docs/SCOPE_EVOLUTION.md (likely 40,000 for v0.7).
```

Fixture files are minified JSON of recorded responses; commit them
under `tests/fixtures/acceptance_gates/` so the test is reproducible
without network.

### US6 — Fixture mode (`--fixture-dir`)

One new helper in (e.g.) `cannavec_science/_fixture_replay.py`:

```python
def fixture_fetcher(fixture_dir: pathlib.Path, lane: str):
    """Return a fetcher callable that reads
    <fixture_dir>/<lane>/<slugified_query>.json. Returns the recorded
    bytes verbatim. Raises FileNotFoundError with a guidance message
    on miss."""
```

Wire it into the four lanes that the demo script exercises
(`pubmed_search`, `chembl_discover`, `ctgov_discover`, `pubmed_verify`).
The other nine live lanes (PubChem, PharmGKB, RCSB, Open Targets,
GWAS, BindingDB, bioRxiv, medRxiv, EuropePMC, OpenAlex) can land
behind the same helper in a follow-up patch.

`--record-fixture-dir` wraps the real fetcher and writes the response
JSON to the same slug path before returning. Identical CLI flags
across the four wired-up subcommands.

### US7 — README + pyproject trim

- Extract every paragraph that is "here is what version X shipped"
  from `README.md` into `docs/PROVENANCE.md` organised **by registry,
  not by version** (`## Pain medicine — primary sources`,
  `## Psychiatry — primary sources`, etc.).
- Rewrite `README.md` to ≤ 600 lines:
  - 1-paragraph what-it-is.
  - Badges (Tests, License, Python ≥ 3.9, Stdlib-only).
  - QUICKSTART link.
  - CHANGELOG link.
  - "What's in the box" table: 1 row per curated registry with
    row-count + governing spec.
  - "Live-discovery lanes" table: 1 row per lane.
  - "Slash commands / skills / agents" 3-line list.
  - Honest scope statement (§IV researcher-only).
  - Links to PROVENANCE, DEMO_SCRIPT, SCOPE_EVOLUTION, spec-kit.
- Rewrite `pyproject.toml` `description` to one ≤ 350-character
  sentence:

```
Researcher-only cannabis-science plugin for Claude Code. Deterministic,
stdlib-only Python ≥ 3.9 backbone: 20 curated registries (≥ 210
primary-source-anchored rows), 13 rigor detectors, 16 banned-pattern
detectors, 13 live-discovery lanes, GRADE-honest output, BibTeX/RIS/CSL
bibliography export.
```

### US8 — PRODUCTION_STATUS_CRITERIA.md

Single page; checklist format:

```
# Production Status Criteria

Cannavec Science is currently `Development Status :: 4 - Beta`.
The plugin will bump to `Development Status :: 5 - Production/Stable`
when ALL of the following are satisfied for ≥ 14 consecutive days:

- [ ] CI workflow green on every push to `main` (US1)
- [ ] QUICKSTART.md, CHANGELOG.md present (US2 + US3)
- [ ] Acceptance-gate offline tests passing (US5)
- [ ] Zero unresolved P0 or P1 issues
- [ ] Latest release shipped ≥ 14 days ago without a follow-up patch

The bump itself ships in a v0.7.x patch release with a CHANGELOG entry.
```

## Implementation order

US1 → US3 → US2 → US5 → US4 → US7 → US8 → (US6 last because it
touches the most module code).

Rationale: US1 (CI) unblocks the trust signal that every later change
relies on. US3 (changelog) is needed before US2 (quickstart) so the
quickstart can link to it. US5 (acceptance-gate tests) before US4
(scope-evolution) so the LOC ceiling US5 enforces is documented in
US4. US7 (README trim) before US8 (status criteria) so the criteria
doc has a clean README to link from. US6 last because it is the only
story that touches `cannavec_science/*.py` and risks regressing the
1,501-test green state — best landed once everything else is stable.

## Trade-offs & decisions

1. **No `pip install -e .` in CI.** Stdlib-only means tests run
   against the repo checkout directly. Adding an install step buys
   nothing and adds a failure mode.
2. **No multi-OS matrix in CI.** Stdlib means platform parity; one
   ubuntu-latest job per Python version is enough. Add macOS/Windows
   if a stdlib-portability bug is ever found.
3. **`docs/V0X_RATING_DELTA.md` files stay.** They are version-
   rationale archives; `CHANGELOG.md` is a separate-purpose doc.
   Both exist; the README links to CHANGELOG.
4. **US6 (fixture mode) wired into 4 of 13 lanes in v0.7.** The four
   the demo script uses are enough for hostile-WiFi resilience. The
   other nine lanes are mechanical follow-ups not on v0.7's critical
   path.
5. **No version-bump to `Development Status :: 5` in v0.7 itself.**
   The criteria require ≥ 14 days of green CI; v0.7 ships the
   criteria, not the bump. The bump is the first v0.7.x patch.
6. **`pyproject.toml` description sentence is the load-bearing
   one-liner.** PyPI / pip rendering is more constrained than the
   README; cutting the description to ≤ 350 chars is a force
   function for honesty about what the plugin is.

## Risks & mitigations

- **Risk:** CI flakes on a Python 3.9 stdlib-API edge that did not
  surface on the author's 3.12. **Mitigation:** US1 matrix tests 3.9
  explicitly. Any flake is a bug to fix.
- **Risk:** Reorganising the README breaks links from the parent
  plugin or external posts. **Mitigation:** Run `grep -r '#.*' README.md`
  pre-rewrite, preserve every anchor used elsewhere; add a "moved to"
  note for any heading that does relocate. The `docs/V0X_RATING_DELTA.md`
  files do not link into README sections, so they stay safe.
- **Risk:** US6 fixture-mode introduces a subtle bug in one of the
  four discovery lanes' fetcher path. **Mitigation:** US6 is last in
  the order; the full 1,501-test suite must still be green after US6
  lands. Add at least one offline + one fixture-replay test per
  wired lane.

## Acceptance gate

The spec-007 acceptance gate is the same as spec 007's user-story
acceptance criteria summed; see `spec.md` § "Acceptance Gate For v0.7".
