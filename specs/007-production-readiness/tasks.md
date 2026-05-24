# Tasks: v0.7 Production-Readiness Hardening

Tasks are ordered by dependency. Test-writing tasks come before
implementation tasks for the same surface per Constitution §III. The
ordering below matches the "Implementation order" section of
`plan.md`: US1 → US3 → US2 → US5 → US4 → US7 → US8 → US6.

Pick up here at the start of the next session. Every task ends with
"Run `python3 -m unittest discover -s tests` and `python3 evals/run_evals.py`
→ both green" unless the task is documentation-only.

## Pre-flight

- **T000**: Confirm working branch is `claude/kind-shannon-KQgsY`.
  Confirm `python3 -m unittest discover -s tests` is green (1,501
  pass) and `python3 evals/run_evals.py` is green (173/173) at HEAD.
  These are the v0.7 baseline.

## US1 — CI workflow

- **T001**: Create `.github/workflows/test.yml` per `plan.md` §US1.
  Matrix Python 3.9, 3.11, 3.13. Two steps per job: unittest + eval
  suite. Push to branch; verify the workflow appears under the
  Actions tab.
- **T002**: Open a draft PR for branch `claude/kind-shannon-KQgsY`
  → `main`. Confirm the CI workflow runs against the PR and goes
  green on all three Python versions. Do NOT merge the PR yet — it
  stays open as v0.7's integration PR.
- **T003**: Add a `Tests` badge to the top of `README.md` (under the
  H1, above any prose) pointing at the workflow's badge URL. Commit.
  Push. Confirm badge renders on the PR's README preview.

## US3 — Canonical CHANGELOG (lands before US2 so quickstart can link to it)

- **T004**: Create `CHANGELOG.md` at repo root following Keep-A-
  Changelog 1.1.0 format per `plan.md` §US3. Distill each
  `docs/V0X_RATING_DELTA.md` (V02 → V06) into its `## [0.X.0]`
  section's bullets. The `## [0.1.0]` section distils
  `specs/001-science-mvp/spec.md`. The `## [Unreleased]` section
  points at `docs/PRODUCTION_STATUS_CRITERIA.md` (which lands in T026).
- **T005**: Add a `[Unreleased]` placeholder for v0.7 listing the
  spec-007 user stories as "in progress" bullets that will move to
  `## [0.7.0]` when v0.7 ships.

## US2 — QUICKSTART

- **T006**: Run the three QUICKSTART commands locally:
  - `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" | head -30`
  - `python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC"`
  - `python3 -m cannavec_science registries | head -25`
  Capture the output verbatim into a scratch file.
- **T007**: Create `QUICKSTART.md` per `plan.md` §US2 using the
  captured output. Hard cap at 200 lines. Include the "What this is /
  what this is NOT" section honestly stating Constitution §IV.
- **T008**: Edit `README.md` to add a `## Quickstart` link in the
  first 20 lines pointing at `QUICKSTART.md` and a `## Changelog`
  link pointing at `CHANGELOG.md`. Do not yet do the full README
  reorganisation — that is US7.

## US5 — Acceptance-gate offline tests

- **T009**: Create `tests/fixtures/acceptance_gates/` directory.
- **T010**: Record `pubmed_28538134.json` by running (when network
  reachable, or curl directly): the E-utilities efetch response for
  PMID 28538134. Save to the fixtures dir. Similarly record
  `crossref_devinsky_2017.json` for DOI 10.1056/NEJMoa1611618 and
  `retraction_28538134.json` as `{"retracted": false, "reason": null}`.
- **T011**: Write `tests/test_acceptance_gates.py` per `plan.md` §US5.
  Five test cases:
  1. `test_dravet_brief_has_three_claims_one_level_b` — uses
     `compose_answer` with injected fixture fetcher; asserts claim
     count, grade distribution, banned-pattern count.
  2. `test_verify_28538134_returns_devinsky_2017` — uses
     `pubmed_verify` with injected fixture fetcher.
  3. `test_rigor_thca_vs_thc_conflation_fires` — pure CPU.
  4. `test_slash_command_count_is_exactly_five` — counts `commands/*.md`.
  5. `test_python_loc_under_cannavec_science_under_ceiling` —
     uses a ceiling constant defined in the test file with a
     comment pointing at `docs/SCOPE_EVOLUTION.md` (T013–T014).
- **T012**: Run `python3 -m unittest tests.test_acceptance_gates`
  → all five tests pass in ≤ 200 ms total.

## US4 — Scope-evolution reconciliation

- **T013**: Tally current `cannavec_science/*.py` module count and
  total LOC (`wc -l cannavec_science/*.py | tail -1`). Record under
  v0.6 / HEAD column in a scratchpad.
- **T014**: Create `docs/SCOPE_EVOLUTION.md` per `plan.md` §US4 with
  one paragraph per version v0.1 → v0.6. Cite the governing spec
  for each. Reconcile the spec-001 "15 modules / < 20,000 LOC"
  target against the v0.6 reality honestly. Document the
  T011-T012 LOC ceiling constant.
- **T015**: Add a one-line "See `docs/SCOPE_EVOLUTION.md` for HEAD
  reconciliation vs original module / LOC targets" note at the top
  of `specs/001-science-mvp/plan.md` under the existing Status
  block. Do NOT edit anything else in spec 001 — it is a historical
  document.
- **T016**: Link `docs/SCOPE_EVOLUTION.md` from `CHANGELOG.md`'s
  `## [0.7.0]` section under `### Added`.

## US7 — README + pyproject surgical trim

- **T017**: Create `docs/PROVENANCE.md`. Move every paragraph from
  `README.md` that reads as "v0.X shipped: …registry with primary
  sources A, B, C…" into PROVENANCE organised **by registry** (one
  H2 per registry). Each PROVENANCE entry has registry name, row
  count, governing spec, and the primary-source citation list.
- **T018**: Rewrite `README.md` to ≤ 600 lines per `plan.md` §US7
  layout (what-it-is paragraph, badges, QUICKSTART link, CHANGELOG
  link, "What's in the box" registry table, live-discovery lanes
  table, surface counts, scope statement, link-out section). Preserve
  every heading anchor that other docs link to. Add "moved to
  `docs/PROVENANCE.md`" notes for relocated content.
- **T019**: Edit `pyproject.toml`:
  - `description = "Researcher-only cannabis-science plugin for
    Claude Code. Deterministic, stdlib-only Python ≥ 3.9 backbone:
    20 curated registries (≥ 210 primary-source-anchored rows), 13
    rigor detectors, 16 banned-pattern detectors, 13 live-discovery
    lanes, GRADE-honest output, BibTeX/RIS/CSL bibliography export."`
  - Bump `version = "0.7.0"`.
- **T020**: Edit `.claude-plugin/plugin.json`:
  - Trim `description` to ≤ 600 chars; same shape as the pyproject
    description sentence plus the live-discovery-source name list.
  - Bump `version` to `"0.7.0"`.
- **T021**: Edit `cannavec_science/__init__.py` — bump `__version__`
  to `"0.7.0"`.

## US8 — Production status criteria

- **T022**: Create `docs/PRODUCTION_STATUS_CRITERIA.md` per
  `plan.md` §US8. Checklist format with a 14-day green-CI
  requirement.
- **T023**: Confirm `pyproject.toml` still declares
  `"Development Status :: 4 - Beta"`. Do NOT bump it in v0.7 — the
  bump is a future v0.7.x patch contingent on the criteria.
- **T024**: Link `docs/PRODUCTION_STATUS_CRITERIA.md` from
  `CHANGELOG.md`'s `[Unreleased]` section.

## US6 — Demo-fixture mode (last, because it touches module code)

- **T025**: Write `tests/test_fixture_mode.py` (NEW). Tests:
  - `test_pubmed_search_replays_from_fixture_dir` (replay path).
  - `test_pubmed_search_record_fixture_dir_writes_response` (record
    path, against a temp dir + injected fake live fetcher).
  - `test_missing_fixture_raises_with_guidance_message`.
  - Repeat for `chembl_discover`, `ctgov_discover`, `pubmed_verify`
    if time permits; otherwise pubmed_search alone is the v0.7 MVP
    of this story.
  Run → fails (helper not implemented).
- **T026**: Create `cannavec_science/_fixture_replay.py` with the
  `fixture_fetcher(fixture_dir, lane)` helper per `plan.md` §US6.
- **T027**: Wire `--fixture-dir PATH` + `--record-fixture-dir PATH`
  flags into `cannavec_science/__main__.py` for the `discover`,
  `verify`, and (read-only) `source-health` subcommands.
- **T028**: Modify `cannavec_science/pubmed_search.py` to accept a
  `fixture_dir` argument that flips the fetcher to the replay
  helper. Modify `chembl_discover.py`, `ctgov_discover.py`,
  `pubmed_verify.py` analogously.
- **T029**: Run T025 → all green. Run the full suite → ≥ 1,501 + N
  new tests, zero regressions.
- **T030**: Add a "Demo over hostile network" callout box to
  `docs/DEMO_SCRIPT.md` flow-1 or top-of-file pointing at
  `--fixture-dir`. Record an `evals/fixtures/demo/` set for the
  flagship CBD-Dravet flow so the demo script's flow 1 works
  offline end-to-end.

## Release

- **T031**: Update `CHANGELOG.md`'s `[Unreleased]` block by moving
  every completed user-story bullet into a fresh `## [0.7.0] —
  2026-05-2X` (insert real date) section. Leave `[Unreleased]` with
  a "(production-status bump pending — see PRODUCTION_STATUS_CRITERIA.md)"
  placeholder.
- **T032**: Run the full suite one last time:
  - `python3 -m unittest discover -s tests` → 0 failures.
  - `python3 evals/run_evals.py` → 173/173 (+ any new prompts) pass.
  - `python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" | wc -l`
    → still produces a substantive brief.
- **T033**: Commit each finished user story as its own commit
  (no squash) using the existing commit style:
  - `feat(007): CI workflow (US1)`
  - `feat(007): CHANGELOG.md (US3)`
  - `feat(007): QUICKSTART.md (US2)`
  - `feat(007): acceptance-gate offline tests (US5)`
  - `docs(007): scope-evolution reconciliation (US4)`
  - `feat(007): README + pyproject trim (US7)`
  - `docs(007): production-status criteria (US8)`
  - `feat(007): demo-fixture mode (US6)`
  - `chore(007): release v0.7.0`
- **T034**: Push branch (`git push -u origin claude/kind-shannon-KQgsY`),
  request review on the PR opened in T002, mark "ready for review."

## Notes for the next session

- The branch is already `claude/kind-shannon-KQgsY` per the
  development-branch requirement in CLAUDE-on-the-web context.
- Constitution §X (stdlib only) means **no** task may add a
  runtime dependency. CI uses GitHub Actions' default Python install.
- Constitution §III means EVERY US that touches code (US1, US5, US6)
  ships tests in the same commit, not a follow-up.
- Constitution §IV (researcher-only) is unchanged by v0.7. Any task
  that drifts the audience surface is out-of-scope and must be
  pushed to a separate spec.
- The v0.6 baseline at HEAD is 1,501 unit tests + 173 eval prompts
  green. Every commit on this branch must preserve that baseline.
