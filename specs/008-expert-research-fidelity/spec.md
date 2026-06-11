# Feature Specification: Expert-Research Fidelity (v0.8)

**Feature Branch**: `claude/kind-noether-OWcZ8`

**Created**: 2026-05-24

**Status**: Implemented (foundational MVP work; extended by later specs)

**Input**: User request: "Test this plugin as if you're a cannabis
expert using it for research and show me the results and add to
spec-kit what needs to be improved." The findings below come from an
end-to-end session of representative researcher queries run against
the v0.6 head (`claude/kind-noether-OWcZ8`, 1501 unit tests + 173/173
eval prompts green) on 2026-05-24.

## Background

A working cannabis-research scientist sat down with the plugin and
ran the queries they would actually issue on a Monday morning: the
canonical CBD-Dravet brief, a CBD × warfarin interaction lookup, a
CBN-as-sleep-aid evidence check, a CBD-in-adolescent-anxiety brief, a
PTSD evidence brief, a cannabis use-disorder treatment brief, a
β-caryophyllene-at-CB2 mechanism brief, a CYP2C9 / THC PGx brief, a
FAAH-in-pain mechanism brief, a `rigor` check on marketing prose, a
`verify` on the Devinsky PMID, a K2/Spice synthesis attempt
(refusal), a BibTeX export, and a `source-health` probe.

**The headline reads:** the curated content is excellent and the
refusal layer is rock-solid. The deterministic backbone catches the
right banned patterns, registers the right rigor violations, refuses
the right safety items, and the answers it does produce are
phytochemically precise and citation-anchored. **But the composer
layer that sits between the registries and the researcher leaks in
ways that a methodology-conscious scientist will notice in the first
five minutes** — and four of the six findings below directly violate
a numbered constitutional principle (§I, §VII, §XI). A v0.8 that
closes them is the difference between "impressive demo" and "tool I
trust in my actual literature review."

The acceptance gate of spec 007 (production-readiness hygiene) is
necessary but not sufficient. Spec 007 ships CI, QUICKSTART,
CHANGELOG, acceptance-gate fixtures, scope evolution, provenance, and
the production-status criteria. Spec 008 addresses the **research-
fidelity** gaps surfaced by the live session and is the next layer up.

### Findings From The Live Session

The session output, raw, lives in
`docs/v08_expert_session_2026-05-24.md` (created in this spec). The
six gaps surfaced are labelled **F1 – F6** in declining severity. The
underlying reproduction commands are listed under each finding; every
one runs offline with stdlib Python and the curated registries.

#### F1 (P0) — Composer renders claims that don't address the question

**Repro:**

```
python3 -m cannavec_science answer "What is the evidence for CBD in adolescent anxiety?"
```

**Observed:** Five claims at Level B / Level A are rendered:
Dravet syndrome, Lennox-Gastaut syndrome, MS spasticity (nabiximols),
chronic neuropathic pain, tuberous sclerosis complex. **Zero** of the
five address adolescent anxiety. The Evidence Summary reports
"Highest evidence grade across claims: **Level A**" — and a careless
reader concludes there is Level A evidence for CBD in adolescent
anxiety. There is not.

The same pattern repeats for `"What is the evidence for cannabis use
disorder treatment?"` (11 claims rendered; only the last is even
about CUD, and that one is about *risk*, not treatment) and `"What is
the evidence for cannabis in PTSD?"` (10 claims rendered; none
address PTSD specifically).

**Root cause:** `cannavec_science/answer.py:1205 _apply_topical_
relevance` correctly computes a topically-relevant subset and stashes
it on `Answer._topically_relevant_claims`. `refresh_evidence_summary`
correctly aggregates `highest_grade` over that subset only. **But
`Answer.to_markdown` at `answer.py:347` iterates `self.claims` — the
unfiltered list — to render the "## Claims" section.** The
topically-relevant subset is invisible to the reader, and the brief
visually equates "Level A in this claim block" with "Level A for the
question asked."

**Constitution violations:** §VII (GRADE Honesty Over Confidence-
Laundering) — the rendered brief inflates the answerable evidence by
showing high-grade off-topic claims; §I (Primary-Source Or Refuse) —
when zero on-topic claims exist, the answer should explicitly read
"Unsupported / no on-topic primary source in curated registry," not
"Level A across five unrelated claims."

#### F2 (P0) — BibTeX / RIS / CSL-JSON author parsing breaks on common label shapes

**Repro:**

```
python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --bibliography bibtex --out /tmp/out.bib
grep -A1 'pmid_17828291' /tmp/out.bib | head -3
```

**Observed:**

```
@article{cannavec_pmid_17828291,
  title   = {Pertwee RG, Br J Pharmacol 2008, ligand-binding profile of phytocannabinoids},
  author  = {Pertwee RG and Br J Pharmacol and lig and -binding profile of phytocannabinoids},
```

Two distinct bugs collapsed into one output line:

1. **Journal-as-author:** `"Br J Pharmacol"` (a journal name) is
   parsed as an author surname because the parser splits the label
   on commas first and treats every comma-delimited token as an
   author.
2. **Mid-word "and" split:** `"ligand-binding"` is split into
   `"lig"` + `"-binding profile..."` because the regex on
   `bibliography.py:151` is `re.split(r"\s*(?:and|&|,)\s*", head)` —
   `\s*` matches zero whitespace, so `and` inside the word `ligand`
   matches.

**Constitution violation:** §XI (Citable Output Is The Default) —
"A researcher using Cannavec Science MUST be able to drop the
answer's citations directly into Zotero / Mendeley / EndNote without
re-keying." A `.bib` file with `lig and -binding` as a co-author
fails this on first import.

**Scope of the bug:** affects every label of the shape
`"Surname Initials, Journal Year, Title"` — which is one of the two
conventional shapes used by the curated registries — and every label
whose title contains the substring `"and"` (`"ligand-binding"`,
`"cannabidiol and seizure threshold"`, etc.). Verified offline with:

```
python3 -c "
from cannavec_science import bibliography as b
print(b._extract_authors_from_label('Pertwee RG, Br J Pharmacol 2008, ligand-binding profile of phytocannabinoids'))
"
```

#### F3 (P1) — `verify` returns "PASS" with no underlying data

**Repro:**

```
python3 -m cannavec_science verify 28538134
```

**Observed (offline, on the v0.8 sandbox with no PubMed egress):**

```
## Identifier verification — PMID 28538134

- **First author:** ?
- **Year:** ?
- **Journal:** ?
- **Retraction status:** unknown
- **Verdict:** PASS
```

`PASS` is the same verdict the command returns on a live-verified
identifier; a researcher cannot distinguish "verified against
PubMed" from "could not reach PubMed, no data verified, returned PASS
anyway." The exit code is `0` in both cases.

**Constitution violation:** §I (Primary-Source Or Refuse) in spirit —
the verifier is the load-bearing primary-source enforcer, and a
green "PASS" with `?` metadata invites the exact failure mode the
principle exists to prevent.

The same network-egress restriction is also why the `source-health`
probe in the v0.8 sandbox reports `chembl / ctgov / pubmed: red
(HTTP 403)` and why `discover` returns zero rows; those reports are
correctly honest, but the `verify` PASS is not.

#### F4 (P1) — `cultivar_as_effect` banned-pattern false-positives on terpene and minor-cannabinoid names

**Repro:**

```
python3 -m cannavec_science rigor "Myrcene is a sedating terpene that causes the couch-lock effect through GABA modulation."
```

**Observed:** Two banned-pattern hits — `cultivar_as_effect` on
`"Myrcene is a sedating"` **and** `terpene_as_clinical_effect` on the
same span. Only the second is correct.

**Root cause:** `banned_patterns.py:115 cultivar_as_effect`'s leading
negative lookahead excludes English question words, cannabinoid
abbreviations (CBD, THC, CBN, …), and a handful of receptor /
regulator abbreviations — but no terpene names. So the regex's
capital-letter cultivar detector fires on `Myrcene`, `Linalool`,
`Pinene`, `Limonene`, `Caryophyllene`, `Humulene`, `Terpinolene`,
`Bisabolol`, `Ocimene`, `Δ⁸-THC`, `Δ⁹-THC`, and the same applies to
biomarker / enzyme names (`FAAH`, `MAGL`, `Anandamide`).

**Severity:** P1 not P0 because the genuine
`terpene_as_clinical_effect` rule also fires on the same prose, so a
researcher running `rigor` still gets the correct primary message —
but the false positive erodes the "deterministic, false-positive-
free" signal the rigor surface trades on, and a researcher who
checks the suggested replacement will follow the wrong remediation.

#### F5 (P2) — Topic taxonomy is too narrow for the v0.6 registry surface

**Repro:** the same three "10–11 rendered claims, zero on topic"
queries from F1.

**Root cause:** `cannavec_science/intent.py:134 _TOPIC_PATTERNS` covers
seven topics (sleep / pain / anxiety / nausea / appetite /
inflammation / focus). The v0.6 registries carry rows for
epilepsy (Dravet, LGS, TSC), spasticity (MS), CINV, HIV-AIDS cachexia,
cannabis use disorder, hyperemesis, PTSD, psychosis, driving
impairment, and the population-caution registries (adolescent,
pregnancy, elderly). None of those topics have a `_TOPIC_PATTERNS`
entry. Net effect: the `_topical_relevance_for_claim` Rule 3
("topic-keyword-matching prompt") never fires for a Dravet-question
prompt against a Dravet-tagged claim, so the composer falls through
to "claim relevant if it mentions the named cannabinoid" — which is
the F1 leak.

**Closing F5 is the cleanest mechanical fix for F1's symptom**: add
the missing topic patterns + tag every registry row with its topic
set, and the existing `_topically_relevant_claims` machinery starts
filtering correctly. F1 then becomes a smaller "render the filtered
subset" change.

#### F6 (P2) — Monograph dumping regardless of question scope

**Repro:**

```
python3 -m cannavec_science answer "What are the clinically significant drug interactions between CBD and warfarin?" | wc -l
```

**Observed:** 100+ lines. The researcher asked one focused interaction
question; the brief includes the full CBD monograph (chemistry,
receptor pharmacology, full clinical-evidence section, PK, safety,
regulatory status, commercial reality, key uncertainties, common
misconceptions, cross-cutting citations). The on-topic answer — one
CBD × warfarin interaction claim — is 1.5 lines.

The same effect repeats for any CBD-named or THC-named question. The
composer attaches a full monograph for **every** cannabinoid named in
the prompt, regardless of whether the question is about interaction,
dose, mechanism, efficacy, or safety.

**Mitigation path:** the `intent` classifier already returns one of
`DEFINITION / DOSE / MECHANISM / EFFICACY / SAFETY / INTERACTION /
OPEN_QUESTION`. The monograph composer should scope rendered sections
to the intent: interaction → interactions registry + PK only;
mechanism → receptor pharmacology only; dose → human clinical
evidence + PK only; safety → safety + AE + interactions. Definition /
open-question queries can keep the full monograph.

**Severity:** P2 not P0 because the answer is *correct*, just buried.
But "buried under 100 lines of unrequested material" is itself a
researcher-time tax that compounds the F1 noise.

---

## User Scenarios & Testing *(mandatory)*

### US1 — On-topic claim rendering (Priority: P1)

**As a** cannabis-research scientist

**I want** the "## Claims" block to render only claims topically
relevant to my question,

**so that** the Evidence Summary's `highest_grade` corresponds to
what I asked about, not to whichever curated claim happened to share
a named cannabinoid with my prompt.

**Why this priority:** F1 is the single largest credibility leak
in the v0.6 surface. Closing it directly satisfies Constitution §VII
(GRADE Honesty) and §I (Primary-Source Or Refuse). Until it ships, a
sceptical reviewer can produce a "Level A for CBD in adolescent
anxiety" screenshot in 15 seconds and the rest of the surface's
credibility collapses behind it.

**Independent Test:**

- `python3 -m cannavec_science answer "What is the evidence for CBD in adolescent anxiety?"`
  returns either zero rendered claims with `highest_grade =
  Unsupported` and the existing `_classify_zero_claims` note
  explaining why, **or** rendered claims that genuinely address
  adolescent anxiety.
- Off-topic claims (Dravet, LGS, MS, TSC, neuropathic pain) MUST NOT
  appear in the "## Claims" block when the prompt names none of those
  indications.
- Off-topic claims that the composer still wants to surface for
  *context* are moved to a clearly-labelled "## Background context
  (not graded for this question)" block, separate from the Claims
  block, so the visual hierarchy never invites a topical-vs-graded
  confusion.

**Acceptance Scenarios:**

1. **Given** the v0.6 curated registries unchanged,
   **When** the user runs `answer "What is the evidence for CBD in adolescent anxiety?"`,
   **Then** the brief reports `highest_grade = Unsupported` (or
   the closest on-topic grade), and the rendered Claims block
   contains zero of `{Dravet, Lennox-Gastaut, TSC, MS spasticity,
   neuropathic pain, CINV, HIV cachexia}` claims.

2. **Given** the same registries,
   **When** the user runs `answer "What is the evidence for CBD efficacy in Dravet syndrome?"`,
   **Then** the brief renders the Dravet claim (Devinsky 2017,
   Level B) **and** the LGS / TSC claims do NOT appear in the Claims
   block (they may appear in a clearly-labelled context block).

3. **Given** the same registries,
   **When** the user runs `answer "What is the evidence for cannabis in PTSD?"`,
   **Then** the brief renders only PTSD-tagged claims; the elderly /
   pregnant / adolescent caution-population claims do NOT appear in
   the Claims block.

---

### US2 — Citable output that survives Zotero import (Priority: P1)

**As a** scientist exporting Cannavec Science briefs as
`.bib` / `.ris` / `.json` for my literature manager,

**I want** the author field to contain authors, not journals or
mid-word fragments,

**so that** I can drop the file into Zotero / Mendeley / EndNote
without re-keying a single citation.

**Why this priority:** F2 directly violates Constitution §XI. A
literature manager that gets `"lig and -binding profile of
phytocannabinoids"` as a co-author surfaces the bug to the
researcher the moment they hit "Import."

**Independent Test:**

- The bibliography export of the Pertwee 2008, Devinsky 2017,
  Whiting 2015, Stockings 2018, and Mücke 2018 citations parses
  cleanly in Zotero's CLI importer (`zotero-cli`) **and** under
  `python3 -c "import bibtexparser; bibtexparser.loads(open(...).read())"`
  with zero author fields containing journal abbreviations or
  obvious non-name tokens.
- `cannavec_science.bibliography._extract_authors_from_label` returns
  `("Pertwee RG",)` (single-author tuple), not the 4-tuple it
  currently returns, on the Pertwee 2008 label.

**Acceptance Scenarios:**

1. **Given** the curated Pertwee 2008 citation label,
   **When** `_extract_authors_from_label` is called,
   **Then** the result is `("Pertwee RG",)` — no `"Br J Pharmacol"`,
   no `"lig"`, no `"-binding profile of phytocannabinoids"`.

2. **Given** a label whose title contains the substring `"and"`
   (e.g., `"Devinsky 2017 — CBD and seizure threshold"`),
   **When** the author parser runs,
   **Then** the title-side `"and"` does NOT split the author tuple.

3. **Given** the full v0.6 bibliography for the canonical
   `"CBD evidence in Dravet syndrome"` brief,
   **When** the BibTeX file is parsed by `bibtexparser`,
   **Then** every `author` field passes a no-journal-token /
   no-mid-word-fragment lint (regression test under
   `tests/test_bibliography_authors.py`).

---

### US3 — Honest `verify` verdicts (Priority: P2)

**As a** scientist using `verify` to confirm a PMID,

**I want** the verdict to distinguish "PubMed reachable, record
verified" from "PubMed unreachable, no data verified,"

**so that** I do not mistake an offline `PASS` for a primary-source
verification.

**Why this priority:** F3 is P2 not P1 because the production
deployment in spec 007 is expected to have PubMed egress, so the
failure mode is narrow to sandboxed / disconnected runs. But the
`PASS` with `?` data is exactly the surface a Constitution §I review
exists to catch.

**Independent Test:**

- `python3 -m cannavec_science verify 28538134` on a host with no
  PubMed egress returns either a verdict of `OFFLINE_UNVERIFIED`
  **or** exits non-zero with a clear error block — not `PASS` with
  `?` fields.
- On a host with PubMed egress, the same command returns `PASS` with
  populated `First author`, `Year`, `Journal`, and a non-`unknown`
  retraction status.

**Acceptance Scenarios:**

1. **Given** a host with no network egress to PubMed / Crossref,
   **When** `verify <PMID>` is run,
   **Then** the verdict is `OFFLINE_UNVERIFIED` (or the command
   exits non-zero), and stdout makes clear no primary-source check
   was performed.

2. **Given** a host with PubMed egress,
   **When** `verify 28538134` is run,
   **Then** `First author = Devinsky O`, `Year = 2017`,
   `Journal = N Engl J Med`, retraction status = `not_retracted`,
   verdict = `PASS`.

---

### US4 — Banned-pattern precision on the terpene / minor-cannabinoid surface (Priority: P2)

**As a** scientist running `rigor` over a draft about terpenes or
minor cannabinoids,

**I want** the banned-pattern detector to fire only on the rule that
actually applies,

**so that** I do not chase a `cultivar_as_effect` remediation on a
sentence that has no cultivar in it.

**Why this priority:** F4 is P2 because the primary message
(`terpene_as_clinical_effect`) does still fire on the right span, so
a researcher who reads the report carefully ends up at the right
remediation. But the noise erodes the surface's claim of
deterministic precision.

**Independent Test:**

- `python3 -m cannavec_science rigor "Myrcene is a sedating terpene
  that causes the couch-lock effect through GABA modulation."`
  returns exactly one banned-pattern hit (`terpene_as_clinical_effect`)
  — not two.
- The exclusion list of `cultivar_as_effect` enumerates terpenes
  (Myrcene, Linalool, Pinene, Limonene, Caryophyllene, Humulene,
  Terpinolene, Bisabolol, Ocimene, Geraniol, Nerolidol, Phytol,
  Eucalyptol), enzyme/transporter abbreviations (FAAH, MAGL, NAPE-PLD,
  DAGL, COX, LOX), and endocannabinoid names (Anandamide, 2-AG,
  PEA, OEA).
- Existing positive cases for `cultivar_as_effect` (`"OG Kush is for
  relaxation"`, `"Blue Dream produces uplifting effects"`) still
  match — regression test for the exclusion list.

**Acceptance Scenarios:**

1. **Given** the rigor text `"Myrcene is a sedating terpene that
   causes couch-lock through GABA modulation."`,
   **When** `rigor` is run,
   **Then** the banned-pattern report contains exactly one hit
   (`terpene_as_clinical_effect`) and zero `cultivar_as_effect`
   hits.

2. **Given** the rigor text `"OG Kush is for relaxation"`,
   **When** `rigor` is run,
   **Then** the banned-pattern report contains a `cultivar_as_effect`
   hit (existing-behaviour regression).

3. **Given** the rigor text `"FAAH is a hydrolase that degrades
   anandamide and is inhibited by PF-04457845"`,
   **When** `rigor` is run,
   **Then** zero banned-pattern hits — neither `cultivar_as_effect`
   nor anything else (no marketing claim is present).

---

### US5 — Topic taxonomy that covers the v0.6 registry surface (Priority: P2)

**As a** the maintainer of the topical-relevance machinery,

**I want** the topic-keyword taxonomy to cover every indication the
v0.6 registries carry rows for,

**so that** US1's on-topic filter can do its job without falling
through to "all claims relevant."

**Why this priority:** F5 is the upstream of F1; closing US5
mechanically makes US1's filter useful instead of vestigial.

**Independent Test:**

- `cannavec_science.intent.topic_keywords("evidence for CBD in
  Dravet syndrome")` returns a set containing `epilepsy` (or
  equivalent topical tag); the Dravet claim in
  `major_cannabinoids.CBD` carries the same tag; the topical
  filter accepts the pair.
- The same holds for: `lennox-gastaut` → `epilepsy`, `tuberous
  sclerosis` → `epilepsy`, `MS spasticity` → `spasticity`, `CINV` →
  `nausea`, `cachexia` → `appetite`, `cannabis use disorder` →
  `use_disorder`, `PTSD` → `ptsd`, `psychosis` → `psychosis`,
  `driving impairment` → `driving`, `hyperemesis` → `hyperemesis`,
  `pregnancy` → `pregnancy`, `adolescent` → `adolescent`, `elderly`
  → `elderly`.

**Acceptance Scenarios:**

1. **Given** the v0.6 registry surface,
   **When** `topic_keywords("Lennox-Gastaut syndrome")` is called,
   **Then** the result contains `"epilepsy"` (or the equivalent
   topical tag the registry uses).

2. **Given** the same surface,
   **When** the topical filter runs `"PTSD"` against a PTSD-tagged
   claim and against a Dravet-tagged claim,
   **Then** the PTSD claim is accepted and the Dravet claim is
   rejected.

3. **Given** a prompt that maps to no known topic,
   **When** `topic_keywords` is called,
   **Then** the result is the empty set (existing fallback
   behaviour — claims pass through unfiltered, preserving back-
   compat for neutral queries like "What is the entourage effect?").

---

### US6 — Intent-scoped monograph rendering (Priority: P3)

**As a** scientist asking a focused interaction / dose / mechanism /
safety question,

**I want** the brief to render only the monograph sections that
match my intent,

**so that** I do not scroll through 100 lines of unrequested
chemistry / regulatory / commercial-reality prose to find the
3-line answer.

**Why this priority:** F6 is P3 because the answer is correct, just
buried. Closing US1 (on-topic claims) and US5 (topic taxonomy) first
substantially reduces the noise; US6 polishes the remainder.

**Independent Test:**

- `python3 -m cannavec_science answer "What are the clinically
  significant drug interactions between CBD and warfarin?" | wc -l`
  returns < 40 lines (down from ~150).
- `python3 -m cannavec_science answer "What is the role of CBD at
  TRPV1?" | wc -l` returns < 30 lines and contains the receptor
  pharmacology section but not the clinical evidence / regulatory
  status sections.
- `python3 -m cannavec_science answer "What is cannabidiol?"`
  (definition intent) continues to render the full monograph —
  back-compat for open / definition queries.

**Acceptance Scenarios:**

1. **Given** the prompt `"What are the clinically significant drug
   interactions between CBD and warfarin?"`,
   **When** `answer` is run,
   **Then** the monograph composer renders the interactions
   registry rows + the pharmacokinetics section + the safety
   section, and OMITS chemistry, regulatory status, commercial
   reality, common misconceptions, and the full clinical-evidence
   section.

2. **Given** the prompt `"What is the role of CBD at TRPV1?"`,
   **When** `answer` is run,
   **Then** the brief renders the receptor pharmacology section
   only.

3. **Given** the prompt `"What is cannabidiol?"`,
   **When** `answer` is run,
   **Then** the full monograph is rendered (back-compat).

---

### Edge Cases

- A prompt that names two cannabinoids (e.g., `"What is the
  evidence for CBD + THC in MS spasticity?"`) MUST render both
  monographs intent-scoped, with the union of relevant sections,
  not the cross-product.

- A prompt that names a cannabinoid for which the registry has no
  claim matching the prompt's topic (e.g., `"What is the evidence
  for CBG in glaucoma?"`) MUST render either zero rendered claims
  with a `highest_grade = Unsupported` and a "no on-topic primary
  source in the curated registry as of v0.8" note, OR live-discover
  fallback rows clearly labelled `live_*` per Constitution §IX.

- The bibliography exporter MUST handle labels of all three
  curated-registry conventions:
  (a) `"Surname Year — Title (Journal)"`,
  (b) `"Surname Initials, Journal Year, Title"`,
  (c) `"Surname1 & Surname2 Year — Title"`.

- The `verify` verdict semantics MUST be JSON-stable; downstream
  CI / scripts may parse the verdict field. Adding
  `OFFLINE_UNVERIFIED` requires a `--json` schema bump documented
  in `CHANGELOG.md`.

- A prompt with no recognisable topic AND no named cannabinoid
  (e.g., `"What's interesting?"`) MUST continue to fall through to
  the current "all claims relevant" behaviour — US1 is not a
  general-purpose intent classifier, just a leak plug.

## Out of Scope For v0.8

- New runtime dependencies (Constitution §X is unchanged — the
  topic taxonomy expansion is a Python dict, not a new library).
- New audience surfaces (Constitution §IV is unchanged — every
  finding here is researcher-facing).
- New registries (the v0.6 registry surface is the v0.8 baseline;
  US5 *tags* existing rows, it does not add new ones).
- New rigor detectors (US4 *tightens* an existing detector, it
  does not add a new one).
- New live-discovery lanes (13 sources is the v0.8 baseline; F3's
  `verify` fix is hygiene on the existing PubMed verifier).
- Multi-cannabinoid intent fusion beyond the two-cannabinoid case
  in Edge Cases — three- or four-cannabinoid prompts continue to
  use the existing union-of-monographs path.

## Risks & Mitigations

- **Risk:** Adding topic tags to existing registry rows (US5) is a
  large mechanical edit and may introduce row-data drift.
  **Mitigation:** US5 ships a `tests/test_registry_topic_tags.py`
  that asserts every row in every curated registry carries at
  least one topic tag from a closed enumeration; CI gate prevents
  drift.

- **Risk:** US1's filter is too aggressive and hides a claim a
  researcher actually wanted to see (false negative on the on-topic
  filter). **Mitigation:** the "## Background context (not graded
  for this question)" block is visible by default and contains the
  filtered-out claims, so the researcher can always see what was
  pulled but is not invited to mis-grade it. The block can be
  hidden behind a `--no-context` flag for power users.

- **Risk:** US2's stricter author parser breaks an existing test
  that depended on the buggy multi-token output. **Mitigation:**
  audit the existing `tests/test_bibliography*.py` files first;
  the buggy output should not have been intentional, and any
  test that asserts on the broken output is itself a regression
  marker.

- **Risk:** US3's new `OFFLINE_UNVERIFIED` verdict breaks
  downstream JSON consumers. **Mitigation:** ship the new verdict
  behind a documented `--json` schema bump in `CHANGELOG.md`; the
  human-readable Markdown output is unchanged in shape.

- **Risk:** US4's exclusion list grows over time as new terpene /
  enzyme names appear. **Mitigation:** the exclusion list is a
  pure Python frozenset; a `tests/test_banned_patterns_exclusions.py`
  asserts the closed enumeration matches what the v0.6 registries
  actually carry. Adding a new terpene row to a registry without
  also adding it to the exclusion list fails CI.

- **Risk:** US6's intent-scoped monograph hides a section a
  researcher wanted. **Mitigation:** the `--full-monograph` flag
  on `answer` restores v0.7 behaviour for any subcommand; the
  scoped default is a UX optimisation, not a content removal.

## Acceptance Gate For v0.8

Before merging the v0.8 branch, ALL of the following MUST hold:

- `python3 -m unittest discover -s tests` exits 0 (unchanged
  from spec 001).
- `python3 evals/run_evals.py` returns ≥ 173/173 passes (unchanged
  from v0.6); the eval suite gains at least one prompt per finding
  (F1–F6 regression coverage) so the v0.8 floor is ≥ 179/179.
- `python3 -m cannavec_science answer "What is the evidence for
  CBD in adolescent anxiety?"` returns either `highest_grade =
  Unsupported` OR rendered claims that ALL contain the
  case-insensitive substring `anxiety` (or a synonym from the
  US5 anxiety topic-pattern).
- `python3 -m cannavec_science answer "CBD evidence in Dravet
  syndrome" --bibliography bibtex --out /tmp/v08.bib` produces a
  file whose every `author` field passes a no-journal-token /
  no-mid-word-`and` regex lint.
- `python3 -m cannavec_science verify 28538134` on a host with no
  PubMed egress returns a verdict that is NOT `PASS` (either
  `OFFLINE_UNVERIFIED` or a non-zero exit).
- `python3 -m cannavec_science rigor "Myrcene is a sedating
  terpene that causes couch-lock through GABA modulation."`
  returns exactly one banned-pattern hit
  (`terpene_as_clinical_effect`).
- `cannavec_science.intent.topic_keywords` covers ≥ 14 topics
  spanning the v0.6 registry surface (the seven existing plus the
  ones enumerated in US5).
- The plugin remains researcher-only (Constitution §IV unchanged,
  no audience widening).
- `dependencies = []` in `pyproject.toml` unchanged (Constitution
  §X).
- The slash-command count is exactly five (Constitution §IV — no
  surface expansion in this spec).
- A new `docs/v08_expert_session_2026-05-24.md` is committed
  containing the raw transcripts of the six findings' repro
  commands for future-session traceability.
