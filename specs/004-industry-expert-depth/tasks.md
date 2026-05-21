# Implementation Tasks: Cannavec Science v0.4 Industry-Expert Depth

**Spec**: [`spec.md`](./spec.md)

**Plan**: [`plan.md`](./plan.md)

**Status**: Shipped — all tasks complete on `claude/fervent-lovelace-3jFjR`.

## Acceptance Snapshot

| Gate | v0.3 | v0.4 |
|---|---|---|
| Unit tests | 1,143 | **1,228** (+85) |
| Eval prompts | 130 | **144** (offline 133) |
| Curated registries | 9 | **11** (analytical_chemistry + cultivation_science) |
| Curated rows total | 145 | **159** (+14) |
| Banned-pattern count | 15 | **16** (indica_sativa_as_pharmacology_abstract) |
| Version stamp | 0.3.0 | **0.4.0** |
| Python LOC (cannavec_science/) | 25,778 | ~26,500 (under 30k ceiling) |

## Task List (ordered by execution sequence)

### T1 — US3: Render `Answer.notes`

- [x] `cannavec_science/answer.py`: `to_markdown()` appends a
      `## Notes` section when `self.notes` is non-empty and the
      answer is not a refusal.
- [x] `cannavec_science/answer.py`: `to_dict()` surfaces a `notes`
      list at top level.
- [x] `tests/test_spec_004_notes_render.py`: new file, 8 tests
      covering markdown render + JSON serialisation + refusal /
      claims-present negative cases.

### T2 — US4: Strengthen indica/sativa banned pattern

- [x] `cannavec_science/banned_patterns.py`: new sibling pattern
      `indica_sativa_as_pharmacology_abstract` that fires on
      indica/sativa/hybrid + abstract framing words
      (`pharmacolog\w*` / `effect\w*` / `difference\w*` /
      `pharmacodynam\w*` / `pharmacokineti\w*` / `mechanism\w*` /
      `receptor\s+activit\w*`), with negative lookbehinds for
      `Cannabis sativa` / `C. sativa` and negative lookaheads for
      botany / taxonomy / systematics / species-debate framings.
- [x] `tests/test_spec_004_banned_pattern_abstract.py`: new file,
      18 tests across positive (5) / botany-escape (6) / v0.3
      prose-form regression (1) / compose_answer integration (2) /
      cross-wiring with cultivation_science (1) plus 3 misc.

### T3 — US1: Analytical-chemistry registry

- [x] `cannavec_science/analytical_chemistry.py`: new module, 8
      curated rows across 5 topics (decarb_kinetics × 3,
      hplc_validation × 1, gc_ms_artefact × 1, chemovar × 2,
      pyrolysis × 1). Each row carries `to_claim()` returning a
      typed `Claim`, identifier-anchored citations per §I, and
      a topic-keyword regex detector.
- [x] `tests/test_analytical_chemistry.py`: new file, 24 tests
      covering shape, validation, detection (positive + negative),
      claim round-trip, isomer-disambiguation cleanliness, renderer,
      freshness.

### T4 — US2: Cultivation-science registry

- [x] `cannavec_science/cultivation_science.py`: new module, 6
      curated rows across 4 topics (light_spectrum × 1,
      trichome_biology × 1, synthase_genetics × 3,
      botanical_taxonomy × 1). The botanical-taxonomy row is the
      honest-debate row citing both Small & Cronquist 1976 and
      Hillig 2005 + McPartland 2018.
- [x] `tests/test_cultivation_science.py`: new file, 22 tests
      including the coexistence-with-banned-pattern guarantee
      (botany framings do NOT trigger the v0.4 abstract pattern).

### T5 — compose_answer wiring

- [x] `cannavec_science/answer.py`: import + call
      `detect_analytical_chemistry_mention(prompt)` and
      `detect_cultivation_science_mention(prompt)`. Rows attach
      citations regardless of refusal; claims attach when not
      refused. Renders as `## Analytical-chemistry registry` and
      `## Cultivation-science registry` sections.
- [x] Trace counters added (`registry.analytical_chemistry`,
      `registry.cultivation_science`).

### T6 — US5: Registry inventory wiring

- [x] `cannavec_science/registries.py`: new `_build_analytical_
      chemistry()` and `_build_cultivation_science()` builders;
      both names added to `all_registry_groups()` and `_BUILDERS`.
- [x] `cannavec_science/__main__.py`: --registry help text lists
      the two new names.
- [x] `tests/test_registries.py`: assertions bumped to 11 groups
      (was 9).

### T7 — US6: Eval bucket + version bump

- [x] `evals/canonical_research_questions.json`: 13 prompts in
      new `analytical_cultivation` bucket; 1 prompt added to
      `refusal` bucket (indica_sativa abstract). Bucket minimum
      `analytical_cultivation: 10` added.
- [x] `tests/test_eval_coverage.py`: new assertions for the
      `analytical_cultivation` minimum + the ≥ 142 total-prompt
      ceiling.
- [x] `.claude-plugin/plugin.json` version → `0.4.0`,
      description updated.
- [x] `pyproject.toml` version → `0.4.0`, description updated,
      keywords expanded.
- [x] `cannavec_science/__init__.py` `__version__` → `0.4.0`,
      docstring updated.
- [x] `README.md` headline replaced; "What v0.4 ships" section
      added; v0.4 quickstart block added; test/eval counts
      bumped.

### T8 — Documentation

- [x] `docs/V04_RATING_DELTA.md`: new file summarising the v0.4
      industry-expert rating delta.
- [x] `docs/DEMO_SCRIPT.md`: v0.4 demo block appended.

### T9 — Final regression + push

- [x] `python3 -m unittest discover -s tests` exits 0 with 1,228
      tests passing, ~2 s runtime.
- [x] `python3 evals/run_evals.py` exits 0 with 133/133 pass.
- [x] Commit + push to `claude/fervent-lovelace-3jFjR`.

## Verification Commands

```bash
# Confirms test + eval suites still green.
python3 -m unittest discover -s tests | tail -3
python3 evals/run_evals.py | tail -15

# v0.4 acceptance smokes.
python3 -m cannavec_science answer "Decarboxylation kinetics of THCA at 110 degrees C"
python3 -m cannavec_science answer "Is Cannabis sativa one species or three?"
python3 -m cannavec_science answer "indica vs sativa pharmacological differences"  # refused
python3 -m cannavec_science answer "Bedrocan medical cannabis cultivars THC content"  # rendered hint
python3 -m cannavec_science registries --registry analytical_chemistry
python3 -m cannavec_science registries --registry cultivation_science
```

## Constitutional Posture

This release is **in-constitution** (no amendment required). The new
registries are research-grade primary-literature topics that sit inside
§IV (researcher-only) — same posture as the v0.2 endocannabinoidome
registry and the v0.3 routing-and-surfacing closures. The 16th banned
pattern is a tightening of the existing §V refusal contract, not a
new safety surface. The notes-render fix closes a v0.3 promise the
unit tests had asserted on the data layer but not on the render layer.
