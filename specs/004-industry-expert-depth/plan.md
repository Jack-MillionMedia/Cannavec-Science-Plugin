# Implementation Plan: Cannavec Science v0.4 Industry-Expert Depth

**Spec**: [`spec.md`](./spec.md)

**Created**: 2026-05-21

**Status**: Approved — implementation in flight on `claude/fervent-lovelace-3jFjR`

## Strategy

Six independently shippable user stories, ordered by P-priority and
dependency. US3 (notes-render bug) lands first because the
classification it surfaces is a precondition for US1 + US2 to feel
credible at the demo (silence-after-0-claims is the worst v0.3 UX).
US4 (banned-pattern strengthening) lands next because it changes the
refusal surface, which US2's botanical-taxonomy row must coexist with.
Then US1 + US2 (the two new registries) in parallel. Then US5 (registry
inventory wiring) and US6 (evals + version bump + README).

```
US3 (notes render, P1)
  ↓
US4 (banned-pattern strengthening, P2)
  ↓
US1 (analytical_chemistry registry, P2)     US2 (cultivation_science, P2)
  ↓                                            ↓
                US5 (registry inventory wiring, P3)
  ↓
US6 (evals + version bump + README, P3)
```

## Version-Boundary Promotion

This spec lifts the version stamp from `0.3.0` to `0.4.0` across three
files:

1. `.claude-plugin/plugin.json` `version`.
2. `pyproject.toml` `project.version`.
3. `cannavec_science/__init__.py` `__version__`.

The README's "v0.3" headline tag is replaced with a "v0.4
industry-expert-depth" tag.

**No constitutional amendment is required.** The v0.x qualifier in the
"Out Of Scope For v0.2" section (already in the constitution as of the
v0.2 promotion) is the mechanism: research-grade analytical and
cultivation depth was already eligible for v0.4 evaluation against the
same §I / §II / §III / §VI / §VII gates the MVP was held to.

## Files To Create / Modify

### US3 — Render `Answer.notes`

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `Answer.to_markdown()` appends a `## Notes` section when `self.notes` is non-empty and `is_refusal` is False. `Answer.to_dict()` already serialises `notes` (verify). |
| `cannavec_science/__main__.py` | The `--json` answer renderer surfaces `notes` at top level (verify; likely already present via the existing `to_dict()`). |
| `tests/test_answer_v04_notes_render.py` | New file. 6 tests: deferred-classification, audience-classification, in-scope-uncurated, in-scope-phrasing-mismatched, JSON serialisation, no-notes-when-claims-present regression. |

### US4 — Banned-pattern strengthening

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/banned_patterns.py` | Add a second `indica_sativa_as_pharmacology_abstract` pattern. Original pattern keeps its sedative/energetic predicate; the new sibling fires on indica/sativa + (`pharmacolog\w*` / `effect\w*` / `difference\w*`) with a negative-lookbehind for `Cannabis sativa L.?` / `botanical\s+taxonomy` / `species\s+debate`. |
| `tests/test_banned_patterns.py` | Add ≥ 4 tests: positive (abstract pharmacology phrasing), positive (effects phrasing), negative (Cannabis sativa L. botany), negative (species debate). |

### US1 — Analytical-chemistry registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/analytical_chemistry.py` | 8-row registry (decarb kinetics × 2, HPLC vs GC-MS × 2, chemovar Type I-V × 2, vapor pyrolysis × 1, edible/extract decarb completion × 1). Topic-keyword detector. `to_claim()` method. | ~480 |
| `tests/test_analytical_chemistry.py` | Shape, primary-citation, detector positive/negative, `to_claim()` round-trip, freshness field. | ~280 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_analytical_chemistry_mention(prompt)`. Rows attach citations + claims (when not refused). Renders as `## Analytical chemistry registry` section. |
| `cannavec_science/__main__.py` | Add `analytical_chemistry` to the registry-subcommand handler's allowed names. |

### US2 — Cultivation-science registry

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/cultivation_science.py` | 6-row registry (UV-B / light × 1, trichome biology × 1, THCA synthase × 1, CBDA synthase × 1, botanical taxonomy × 1, chemotype inheritance × 1). Topic-keyword detector. `to_claim()` method. | ~420 |
| `tests/test_cultivation_science.py` | Shape, primary-citation, detector positive/negative, botanical-vs-pharmacology coexistence with US4, `to_claim()` round-trip. | ~260 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/answer.py` | `compose_answer` calls `detect_cultivation_science_mention(prompt)`. Same wiring as US1. Renders as `## Cultivation science registry` section. |
| `cannavec_science/__main__.py` | Add `cultivation_science` to the registry-subcommand handler's allowed names. |

### US5 — Registry inventory wiring

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/registries.py` | Add `_build_analytical_chemistry()` and `_build_cultivation_science()` builders. Append names to `all_registry_groups()` and the `_BUILDERS` map. |
| `tests/test_registries.py` | Add tests asserting the two new groups appear in the default inventory and via direct lookup; bump total-row assertion. |

### US6 — Evals + version + README

**Modified:**

| File | Change |
|---|---|
| `evals/canonical_research_questions.json` | Add ≥ 12 prompts in a new `analytical_cultivation` bucket. Add `analytical_cultivation: 10` to `category_minimums`. |
| `evals/run_evals.py` | No code change — runner already drives bucket-minimum enforcement from JSON. |
| `tests/test_eval_coverage.py` | Bump per-bucket assertion / total-prompt assertion. |
| `.claude-plugin/plugin.json` | Version → `0.4.0`. Description gains v0.4 deliverables. |
| `pyproject.toml` | Version → `0.4.0`. Description gains v0.4 deliverables. |
| `cannavec_science/__init__.py` | `__version__` → `0.4.0`. Docstring updated. |
| `README.md` | Replace "v0.3" headline with "v0.4". Add a "What v0.4 ships" section. Add v0.4 quickstart prompts. |
| `docs/V04_RATING_DELTA.md` | New file — v0.4 industry-expert rating delta summary. |
| `docs/DEMO_SCRIPT.md` | Add a v0.4 demo block. |

## Module Architecture (v0.4 additions only)

```
cannavec_science/
├── analytical_chemistry.py   # v0.4 — decarb, HPLC/GC-MS, chemovar, pyrolysis
├── cultivation_science.py    # v0.4 — UV-B, trichome, synthase, taxonomy
└── (everything else unchanged from v0.3)
```

## Public CLI Surface (v0.4 additions)

`python -m cannavec_science <subcommand>`:

- `answer` — surfaces analytical-chemistry / cultivation-science rows
  when the prompt names a covered topic. Rendered notes section when
  zero claims and no refusal.
- `registries [--registry analytical_chemistry|cultivation_science]` —
  the two new groups appear.

No new slash command. No new subcommand. The v0.4 surface is **purely
deeper** in the existing surfaces — Constitution §IV remains intact.

## Trade-offs & Decisions

1. **Topic-keyword detection vs cannabinoid-name detection.**
   Analytical / cultivation questions are about the PLANT or METHOD,
   not a single named cannabinoid. So the detector is regex on the
   topic noun (`decarboxylation kinetics`, `chemovar`, `UV-B`,
   `trichome`, etc.), not the existing `NamedCannabinoidSet` pathway.
   The detector returns a tuple of rows; the composer iterates and
   attaches claims.

2. **Sibling pattern, not regex bicycle-shed.** US4 adds a new
   `indica_sativa_as_pharmacology_abstract` pattern alongside the
   existing one rather than mutating it. Reason: the existing pattern
   passes 15 banned-pattern tests including the demo input "Indica
   strains are sedating because they have more myrcene". Mutating the
   existing regex risks regression. A new pattern is its own row in
   the registry; the refusal verdict aggregates per the existing
   pipeline.

3. **Notes rendering: a single `## Notes` section, not per-note
   inline.** US3 collects the v0.3 classification messages into one
   trailing section so the markdown stays clean. JSON keeps the field
   at top level (already correct via `to_dict()`).

4. **Don't double-render the GC-MS artefact.** The analytical-chemistry
   registry surfaces "GC-MS produces in-injector decarboxylation"
   as a curated Level C claim. The v0.3 THCA-vs-THC rigor detector
   continues to catch the SAME artefact in PROSE. The two surfaces
   are complementary — registry teaches the user about the artefact;
   rigor detector catches the user when they conflate it.

5. **Botanical taxonomy as honest debate, not resolution.** The
   `is Cannabis sativa one species or three` row in
   `cultivation_science.py` reports BOTH the Small & Cronquist 1976
   single-species view AND the Hillig & Mahlberg 2004 multi-species
   view, graded as Level C with citations to both. Cannavec Science
   does not pick a winner; it reflects the live botanical debate
   honestly.

6. **Eval bucket name is `analytical_cultivation`, not two buckets.**
   One bucket is easier to enforce a minimum on; the two topics are
   v0.4-scope-twins. Internally each prompt carries a `subcategory`
   tag (`analytical` / `cultivation`) so we can split later if we want.

## Implementation Order

1. **US3 — notes rendering bug** (1 file edit + 6 tests). Lands first
   so the v0.4 horizon-deferred classification renders, making US1 /
   US2 demos clean even before they ship.
2. **US4 — banned-pattern strengthening** (1 file edit + ≥ 4 tests).
   Lands second because US2's botanical-taxonomy row must coexist
   with it.
3. **US1 + US2 — registries in parallel**. Both modules are pure-data
   leaves of the dependency graph; tests can be written alongside.
4. **`compose_answer` wiring** for both registries.
5. **US5 — registry inventory wiring** (1 file edit + 2 tests).
6. **US6 — evals + version + README + docs**.
7. **Final regression**: `python3 -m unittest discover -s tests`
   exits 0 with ≥ 1,190 tests. `python3 evals/run_evals.py` exits 0
   with ≥ 142 prompts.
8. **Commit + push to `claude/fervent-lovelace-3jFjR`**.

## Acceptance Gate

Before pushing the v0.4 branch, ALL of the following MUST hold:

- `python3 -m unittest discover -s tests` exits 0, ≥ 1,190 tests, ≤ 5 s.
- `python3 evals/run_evals.py` exits 0, ≥ 142 prompts (offline ≥ 131),
  every bucket meets its minimum.
- `python3 -m cannavec_science answer "Decarboxylation kinetics of THCA
  at 110°C"` returns ≥ 1 Level C/D claim with primary citation.
- `python3 -m cannavec_science answer "Is Cannabis sativa one species
  or three?"` returns ≥ 1 Level C claim with primary citation AND
  does NOT fire the indica/sativa-as-pharmacology banned pattern.
- `python3 -m cannavec_science answer "indica vs sativa pharmacological
  differences"` fires the refusal (NOT silent 0-claims).
- `python3 -m cannavec_science answer "Bedrocan cultivars THC content"`
  markdown output contains the audience-classification hint.
- `python3 -m cannavec_science registries` lists `analytical_chemistry`
  and `cultivation_science` groups.
- `.claude-plugin/plugin.json` / `pyproject.toml` /
  `cannavec_science/__init__.py` all report `0.4.0`.
- Total Python LOC under `cannavec_science/` stays under 30,000.
- The total slash-command count remains exactly **five**.

## Risks & Mitigations

- **Risk**: A new analytical-chemistry row's claim_text accidentally
  contains a phrase the THCA-vs-THC rigor detector flags as a
  violation. **Mitigation**: each row's `to_claim()` is unit-tested
  against `rigor_checks.detect_all_violations` to assert clean.
- **Risk**: The strengthened banned-pattern regex catches a legitimate
  research question that names `sativa` for taxonomic reasons.
  **Mitigation**: the new pattern carries explicit negative lookaheads
  for `Cannabis sativa L.`, `botanical taxonomy`, `species debate`,
  `taxonomic`. The cultivation_science registry has positive tests
  asserting the botany framing escapes the refusal.
- **Risk**: The notes-render change introduces a regression where a
  refused answer also renders notes. **Mitigation**: the render
  predicate is `self.notes and not self.is_refusal`. A regression test
  asserts that the K2/Spice refusal does NOT render notes.
- **Risk**: The eval bucket assertion overshoots and a legitimate v0.4
  registry change breaks the regression. **Mitigation**: bucket
  minimum is 10 with 12 prompts shipping — 20% headroom.
