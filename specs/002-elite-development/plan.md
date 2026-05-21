# Implementation Plan: Cannavec Science Elite Development (v0.2)

**Spec**: [`spec.md`](./spec.md)

**Created**: 2026-05-21

**Status**: Draft — pending `/speckit-tasks` approval

## Strategy

Six independently shippable user stories, each gated by its own test
suite, each landing without touching the others. The v0.2 boundary is
explicit — version bumps from `0.1.0` to `0.2.0` at the spec landing —
but each US ships as its own focused PR off
`claude/cannavec-science-elite-development` so a partial v0.2 is still
useful (US3 + US5 alone, for instance, is a credibility upgrade
without any new live source).

Implementation order matches priority: US3 (eval expansion) first
because every other story leans on it for regression-safety, then US1
+ US2 in parallel (the two P1 visible deltas), then US4 + US5 + US6
in parallel (the P2 deepenings).

## Version-Boundary Promotion

This spec is the **v0.x → v0.2 boundary**. Per Constitution §"Out Of
Scope For v0.x": *"These features may exist in the larger Cannavec
plugin. They are explicitly NOT promised by this MVP."* The "v0.x"
qualifier is doing the load-bearing work — once the version bumps to
0.2, the items in that list become eligible for re-evaluation against
the same constitutional gates the MVP was held to.

The v0.2 promotion:

1. Increments `.claude-plugin/plugin.json` version from `0.1.0` to
   `0.2.0`.
2. Increments `pyproject.toml` version to `0.2.0`.
3. Updates `cannavec_science/__init__.py` `__version__` to `0.2.0`.
4. Removes "bioRxiv / medRxiv preprint discovery" from the
   Constitution §"Out Of Scope For v0.x" list (US1 ships it).
5. Documents the promotion in this plan.

**No constitutional amendment is required.** The constitution's own
v0.x qualifier defines this mechanism. The principle changes (deepened
§I, §VI, §VII, §VIII, §IX, §XI) are extensions under existing
principles, not new principles.

## Files To Create / Modify

Six clusters, one per user story.

### US1 — Preprint Discovery

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/biorxiv_discover.py` | bioRxiv API v0 wrapper. Same shape as `chembl_discover.py`. | ~280 |
| `cannavec_science/medrxiv_discover.py` | medRxiv API v0 wrapper. Shares helpers with bioRxiv via internal `_preprint_helpers.py`. | ~280 |
| `cannavec_science/_preprint_helpers.py` | Shared DOI parsing, version-history extraction, published-version cross-reference via Crossref. | ~180 |
| `tests/test_biorxiv_discover.py` | Happy-path, refusal, banned-pattern, network-error, version-history, published-version. | ~250 |
| `tests/test_medrxiv_discover.py` | Same coverage as bioRxiv. | ~250 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/__main__.py` | Add `biorxiv` and `medrxiv` to `_DISCOVERER_REGISTRY`. |
| `cannavec_science/synthesis.py` | Add `"biorxiv"` and `"medrxiv"` to `_SOURCE_KEYS`. |
| `cannavec_science/discover_guard.py` | No code change — the preflight already runs on every discoverer. Verify via test. |
| `cannavec_science/evidence.py` | Add a `Level D` cap rule for sources whose `tier == SourceTier.PREPRINT_OR_SMALL` — already present; verify the new provenance tag maps to that tier. |
| `cannavec_science/answer.py` | Visual-distinction badge for preprint citations (`[preprint, not peer-reviewed]` suffix). |
| `skills/cannabis-primary-source-routing/SKILL.md` | Add bioRxiv/medRxiv lane to the routing table. |

### US2 — Researcher-Workflow Scaffolding

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/pico.py` | Deterministic PICO drafter. Uses existing intent + populations + claim types. | ~220 |
| `cannavec_science/power_calc.py` | Stdlib-only sample-size: two-arm continuous (Cohen's d), two-arm dichotomous (OR + baseline), proportion-difference. Uses `math.erf` for normal CDF; no scipy. | ~280 |
| `cannavec_science/grade_profile.py` | GRADE evidence-profile-table renderer (Markdown + CSV). Reads the typed `Answer` and produces the table journals expect. | ~240 |
| `cannavec_science/protocol_skeleton.py` | 9-section IRB stub generator. Pure deterministic composition from PICO + answer claims. | ~200 |
| `tests/test_pico.py` | Happy-path + insufficient-input + intent-classification coverage. | ~180 |
| `tests/test_power_calc.py` | Cohen's-d, OR, proportion cases + insufficient-input + edge cases (zero effect, perfect effect). | ~220 |
| `tests/test_grade_profile.py` | Per-claim row alignment, downgrade column totals, Markdown vs CSV formats. | ~180 |
| `tests/test_protocol_skeleton.py` | Section-count, watermark, word-cap, PICO inclusion. | ~140 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/__main__.py` | Add `--pico`, `--power-calc`, `--grade-profile`, `--grade-profile-format`, `--protocol-skeleton` flags to `answer` subcommand. |
| `cannavec_science/answer.py` | Thread the four scaffolders into `compose_answer` and `Answer.to_markdown`. |
| `commands/research.md` | Document the four scaffolding flags. |
| `docs/DEMO_SCRIPT.md` | Add a scaffolder-flow demo. |

### US3 — Eval Expansion

**Modified:**

| File | Change |
|---|---|
| `evals/canonical_research_questions.json` | Grow from 12 → ≥ 100 prompts. Reorganize by category buckets. Add `category_minimums` metadata block. |
| `evals/run_evals.py` | Add bucket-minimum check; richer per-prompt failure reporting (prompt id + failing expectation + actual). |

**New:**

| File | Purpose | Approx LOC |
|---|---|---|
| `tests/test_eval_coverage.py` | Unit test enforcing the per-bucket minimums (≥ 25 / 30 / 20 / 15 / 10 / 5). | ~120 |
| `evals/REGRESSION_LOG.md` | Append-only log: each regression that adds a prompt links the prompt id back to the bug. Curator discipline. | n/a (Markdown) |

### US4 — Citation Network & Field Pushback

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/citation_network.py` | Calls NCBI `elink cmd=neighbor`, aggregates per-cite sentiment via existing `pubmed_sentiment()`, detects replication language, emits `CitationNetworkBlock`. | ~340 |
| `tests/test_citation_network.py` | Network success, rate-limit, mixed-pushback, replication-success, replication-failure. | ~280 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/pubmed_verify.py` | `verify_pmid` gains optional `with_citation_network: bool` flag; default False (back-compat) but the `verify` subcommand sets it True. |
| `cannavec_science/__main__.py` | `verify` subcommand always populates citation_network unless `--no-citation-network` is set. |
| `cannavec_science/evidence.py` | `apply_grade_modifiers` already accepts `inconsistency_serious=True`; new code path in `compose_answer` flips it based on citation_network. |
| `cannavec_science/answer.py` | Citation-network signal threading into per-claim grade computation. |
| `tests/test_evidence.py` | Add test: refute-heavy pushback → one-level downgrade. |

### US5 — Registry Freshness & Retraction Watch

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/freshness.py` | Generic freshness prober: enumerate registry rows → extract `watch_pmids` → call `pubmed_verify` + retraction lookup → produce `FreshnessStatus` per row. Stdlib only; serial by default; optional `ThreadPoolExecutor` fan-out controlled by `--parallel N`. | ~340 |
| `tests/test_freshness.py` | Clean / retraction / eoc / stale / network-error / CLI exit codes. | ~280 |
| `tests/test_answer_freshness.py` | Stale-suffix appears when registry row is > 365 days old. | ~120 |

**Modified (every registry):**

| File | Change |
|---|---|
| `cannavec_science/major_cannabinoids.py` | Every row gains `last_verified: str` (date-of-port = `2026-05-21`) and `watch_pmids: tuple[str, ...]` populated from the row's existing citations. |
| `cannavec_science/minor_cannabinoids.py` | Same. |
| `cannavec_science/terpenes.py` | Same. |
| `cannavec_science/interactions.py` | Same — 32 rows. |
| `cannavec_science/adverse_events.py` | Same. |
| `cannavec_science/populations.py` | Same. |
| `cannavec_science/contraindications.py` | Same. |
| `cannavec_science/pharmacogenomics.py` | Same. |
| `cannavec_science/__main__.py` | New subcommands: `freshness` and `freshness-report`. |
| `cannavec_science/answer.py` | Citation renderer appends `[freshness: stale (verified YYYY-MM-DD)]` when row age > 365 days. |

### US6 — Cannabis-Specific Blind-Spot Closures

**New modules:**

| File | Purpose | Approx LOC |
|---|---|---|
| `cannavec_science/ecbome.py` | Endocannabinoidome reference: mediators (AEA / 2-AG / PEA / OEA / virodhamine / NADA / 2-AGE / NAGly), receptors (CB1 / CB2 / GPR55 / GPR119 / GPR18 / PPARα / PPARγ / TRPV1 / TRPA1 / TRPM8), enzymes (FAAH / MAGL / DAGLα / DAGLβ / NAPE-PLD / ABHD6 / ABHD12 / COX-2), transporters (FABP5 / FABP7). Every entry has a UniProt or HMDB ID. | ~520 |
| `cannavec_science/regulatory_feasibility.py` | Advisory module: US-federal (DEA Schedule I research registration), EU-EMA, Canada (Health-Canada §56 exemption), UK-MHRA. Per-compound × per-jurisdiction matrix. Watermark on every output. | ~380 |
| `tests/test_ecbome.py` | Identifier presence, receptor-id rigor on eCBome rows, mediator-receptor pairing. | ~220 |
| `tests/test_regulatory_feasibility.py` | US-federal Schedule I, EU novel-food gray zone, Canada exemption path, unsupported-jurisdiction graceful fail, watermark presence. | ~240 |
| `tests/test_entourage_detector.py` | Positive (uncited synergy claim) and negative (cited synergy claim with each canonical reference). | ~180 |

**Modified:**

| File | Change |
|---|---|
| `cannavec_science/minor_cannabinoids.py` | New rows: Δ⁸-THC, HHC, THCO, THCP. Each at honest evidence depth; Unsupported is acceptable. |
| `cannavec_science/rigor_checks.py` | New detector `detect_entourage_overclaim()` + `EntourageViolation` dataclass; added to `RigorCheckReport`. |
| `cannavec_science/answer.py` | eCBome + regulatory-feasibility threading; new flag `--regulatory-feasibility {us|eu|ca|uk}`. |
| `cannavec_science/__main__.py` | New `--regulatory-feasibility` flag on `answer` and `research`. |
| `tests/test_rigor_checks.py` | Add coverage for the new detector at the existing per-detector test pattern. |
| `tests/test_minor_cannabinoids.py` | Add coverage for the four new rows. |

## Module Architecture (post v0.2)

```
cannavec_science/
├── __init__.py
├── __main__.py
├── evidence.py
├── banned_patterns.py
├── safety.py
├── rigor_checks.py            ← +entourage detector
├── retraction.py
├── pubmed_verify.py           ← +citation_network flag
├── pubmed_search.py
├── chembl_discover.py
├── ctgov_discover.py
├── pubchem_discover.py
├── pharmgkb_discover.py
├── rcsb_discover.py
├── opentargets_discover.py
├── gwas_discover.py
├── bindingdb_discover.py
├── biorxiv_discover.py        ← NEW (US1)
├── medrxiv_discover.py        ← NEW (US1)
├── _preprint_helpers.py       ← NEW (US1)
├── discover_guard.py
├── synthesis.py               ← +biorxiv/medrxiv keys
├── source_health.py
├── intent.py
├── uncertainty.py
├── answer.py                  ← +scaffolders, +freshness suffix, +eCBome, +regfeas
├── evidence_synthesis.py
├── bibliography.py
├── contradiction.py
├── major_cannabinoids.py      ← +last_verified, +watch_pmids
├── minor_cannabinoids.py      ← +last_verified, +watch_pmids, +Δ8/HHC/THCO/THCP
├── terpenes.py                ← +last_verified, +watch_pmids
├── terpene_reference.py
├── interactions.py            ← +last_verified, +watch_pmids
├── adverse_events.py          ← +last_verified, +watch_pmids
├── populations.py             ← +last_verified, +watch_pmids
├── contraindications.py       ← +last_verified, +watch_pmids
├── pharmacogenomics.py        ← +last_verified, +watch_pmids
├── pico.py                    ← NEW (US2)
├── power_calc.py              ← NEW (US2)
├── grade_profile.py           ← NEW (US2)
├── protocol_skeleton.py       ← NEW (US2)
├── citation_network.py        ← NEW (US4)
├── freshness.py               ← NEW (US5)
├── ecbome.py                  ← NEW (US6)
└── regulatory_feasibility.py  ← NEW (US6)
```

Module count: 37 → **48** (+11 new modules; no modules removed).

LOC budget: 19,060 → estimated 24,200. Stays under the 25,000 SC-208
cap. Headroom of ~800 LOC absorbs registry-row expansion from
`last_verified` + `watch_pmids` and the four new minor-cannabinoid rows.

## Public CLI Surface (post v0.2)

`python3 -m cannavec_science <subcommand>`:

```
answer "<question>" [--bibliography {bibtex|ris|csljson}] [--out PATH]
                    [--retraction-policy {strict|badge}] [--json]
                    [--pico] [--power-calc]
                    [--grade-profile] [--grade-profile-format {markdown|csv}]
                    [--protocol-skeleton]
                    [--regulatory-feasibility {us|eu|ca|uk}]

discover "<query>" [--since YYYY-MM-DD] [--max N]
                   [--sources pubmed,chembl,ctgov,pubchem,pharmgkb,rcsb,
                              opentargets,gwas,bindingdb,biorxiv,medrxiv]
                   [--json]

verify <PMID|DOI|NCT|ChEMBL> [--no-citation-network] [--json]

rigor "<text>"  ← entourage detector now part of report

bibliography <answer.json> --format {bibtex|ris|csljson} [--out PATH]

source-health [--sources ...]  ← biorxiv,medrxiv added

freshness [--registry <name>] [--parallel N]   ← NEW (US5)
freshness-report --since YYYY-MM-DD             ← NEW (US5)
```

**Slash command count remains five** (FR-218 / Constitution §IV). All
new functionality ships as flags on existing slash commands and as
new subcommands of the Python module CLI — no `commands/*.md` file is
added.

## Trade-offs & Decisions

1. **No constitutional amendment.** The v0.x → v0.2 boundary mechanism
   is defined by the constitution itself. Adding preprints under the
   primary-source widening contract (Level D cap, `live_*` provenance,
   discover_guard preflight, no auto-promotion) honors Constitution §I
   and §IX without amendment.

2. **Four scaffolders ship as flags, not new commands.** Constitution
   §IV scope-locks to five slash commands. `--pico`, `--power-calc`,
   `--grade-profile`, `--protocol-skeleton` enrich the existing
   `/cannavec-science:research` and `/cannavec-science:ask` flows. No
   sixth slash command.

3. **No scipy / numpy / statsmodels.** US2's power calculator uses
   `math.erf` for the normal CDF inverse and the standard Cohen's-d /
   OR / proportion-difference formulas. Stays within Constitution §X
   (stdlib-only). Loses access to fancier power methods (non-inferiority,
   adaptive designs, simulation-based); the calculator surfaces
   "method-not-supported" honestly for those cases rather than emitting
   a guess.

4. **No auto-mutation of registry rows from freshness probes.** US5
   surfaces gaps; the curator updates the row by hand. Mirrors
   Constitution §IX's "curated rows never auto-promoted" with the
   inverse "curated rows never auto-invalidated." A future spec could
   propose a curator-agent path; this spec does not.

5. **Regulatory-feasibility is US-federal / EU / Canada / UK only.**
   Per-state US law lives in the parent Cannavec plugin. Adding it
   here would expand audience and scope; defer to a later spec.

6. **eCBome module is reference-only.** No new live discovery for
   metabolomics databases (HMDB, Metabolights). The eCBome entries
   point at HMDB IDs but the live HMDB discoverer is out-of-scope
   for v0.2; deferred to a later spec.

7. **US6 entourage detector is conservative.** It enforces
   citation-discipline on entourage claims, not the entourage
   hypothesis itself. The hypothesis is open-empirical with mixed
   evidence; the detector treats it the same way `rigor_checks.py`
   treats any uncited pharmacology claim.

8. **Eval expansion includes a `tests/test_eval_coverage.py` guard.**
   Documentation alone doesn't enforce per-bucket minimums; a unit
   test does. Future contributors cannot silently lower the bar
   without the test failing.

9. **Citation-network signal is deterministic, not LLM-judged.** US4
   reuses the existing `pubmed_sentiment()` regex. Accuracy is what
   it is — the goal is reproducibility and Constitution §II compliance
   ("a skill that promises rigor without a deterministic enforcer is
   marketing"), not state-of-the-art NLP.

10. **Network-probing subcommands `freshness` and `source-health`
    are not run by default in `compose_answer`.** They are operator
    subcommands. The answer composer still trusts the registry rows
    at call time; the operator runs freshness on a schedule and the
    curator updates rows when the probe surfaces a flip.

## Implementation Order

Sequenced so partial landings are useful and dependencies resolve
cleanly.

1. **US3 (Eval Expansion)** — foundation. Lands first because every
   other story regression-tests against the expanded eval surface.
   Without this, US1/US4/US6 can introduce regressions invisibly.
2. **US5 (Registry Freshness)** — landed second because it touches
   every registry row and its tests catch unintended row mutations
   while later stories edit registries.
3. **US1 (Preprint Discovery)** in parallel with **US2 (Workflow
   Scaffolders)** — both P1 and both visibility-critical. Independent
   modules; can ship as separate PRs.
4. **US4 (Citation Network)** — extends `verify` + `pubmed_verify`;
   integration into `compose_answer` via `apply_grade_modifiers`.
5. **US6 (Cannabis Blind Spots)** — multi-pronged but each prong is
   independent (minor-cannabinoid rows, eCBome module,
   regulatory-feasibility, entourage detector); can ship as four
   sub-PRs under one branch.

## Acceptance Gate (v0.2 ship)

Before pushing v0.2 to the release branch, ALL of the following MUST
hold:

- `python3 -m unittest discover -s tests` exits 0 in ≤ 60 seconds.
- Total test count ≥ 1,100.
- `python3 evals/run_evals.py` exits 0 with ≥ 100 prompts loaded
  across the six category buckets, each at or above its minimum.
- `python3 -m cannavec_science discover "CB2 microglia" --sources
  biorxiv,medrxiv --max 5` returns at least one preprint row tagged
  `live_biorxiv` or `live_medrxiv` with a valid `10.1101/...` DOI and
  Level D cap.
- `python3 -m cannavec_science answer "CBD Dravet syndrome" --pico
  --power-calc --grade-profile --protocol-skeleton` returns one
  composed answer with all four scaffolds present.
- `python3 -m cannavec_science verify 28538134 --json` returns the
  Devinsky-2017 record plus a `citation_network` block.
- `python3 -m cannavec_science freshness --registry interactions`
  returns a per-row status table without errors and without mutating
  any registry row (asserted via git status comparison).
- `python3 -m cannavec_science answer "What is the evidence for HHC
  analgesia?"` includes the new HHC row at honest grade.
- `python3 -m cannavec_science rigor "myrcene potentiates THC's
  sedative effect"` fires the new `entourage_overclaim` detector.
- Slash-command count remains exactly five.
- Total Python LOC under `cannavec_science/` stays under 25,000.
- Constitution §"Out Of Scope For v0.x" section is updated to remove
  the bioRxiv/medRxiv line (US1 ships it; the list is now empty or
  reduced to items genuinely deferred past v0.2).
- `.claude-plugin/plugin.json`, `pyproject.toml`, and
  `cannavec_science/__init__.py` versions read `0.2.0`.

## Risks & Mitigations

- **Risk**: bioRxiv/medRxiv API rate limits or surprises during demo.
  **Mitigation**: every preprint discoverer ships with an injected
  fixture path; demos can run from recorded fixtures if live calls
  flake. Same pattern the nine existing Tier-3 lanes already use.
- **Risk**: power calculator emits wrong sample sizes due to formula
  errors. **Mitigation**: every formula carries a test against a known
  textbook example (Cohen 1988 worked examples; Fleiss 1981 worked
  examples). The calculator is honest about method scope and refuses
  unsupported designs explicitly.
- **Risk**: eval expansion from 12 → 100+ is brittle if prompts
  encode flaky behavior. **Mitigation**: every new prompt declares
  explicit expectations; the runner is deterministic; prompts that
  depend on live network are tagged and excluded from offline CI.
- **Risk**: registry-freshness probes run too often and hammer NCBI.
  **Mitigation**: subcommand is operator-invoked, not auto-run; default
  is serial; NCBI etiquette headers carried through; documented in
  README that it should run on a schedule, not on every answer.
- **Risk**: regulatory-feasibility module gets cited as legal advice.
  **Mitigation**: watermark on every output, in the module docstring,
  in the CLI help text, and in the answer renderer. Watermark is
  asserted by `tests/test_regulatory_feasibility.py` so it cannot be
  removed silently.
- **Risk**: entourage detector false positives on legitimate
  scientific discussion of the entourage hypothesis as a research
  topic. **Mitigation**: detector fires only on synergy *claims*, not
  on *discussion* of the hypothesis; false-positive guards mirror the
  `rigor_checks.py` pattern of small-window context analysis.
- **Risk**: v0.2 LOC overshoots the 25,000 cap. **Mitigation**: SC-208
  is checked in the acceptance gate; if overshooting, trim US6's
  regulatory-feasibility module first (it's the largest new addition)
  before cutting from US1/US2/US3.

## Out-of-Plan (Reserved For v0.3+)

These were considered for v0.2 and consciously deferred:

- **AlphaFold predicted structure integration** — needs its own
  rigor framing distinct from RCSB.
- **Per-state US regulatory-feasibility** — parent Cannavec plugin
  scope.
- **HMDB live discoverer** — eCBome module references HMDB IDs but
  the live lane is deferred.
- **Curator-agent auto-mutation** — explicit non-goal per trade-off #4.
- **Multi-trial endpoint comparison** — touches CTGov heavier than
  current v0.2 surface; deferred.
- **Conflict-of-interest network mapping** — needs author-disambiguation
  and a separate primary source (ORCID, OpenAlex); deferred.

These items inform v0.3 scope but are NOT promised by v0.2.
