# Expert-Researcher Session — 2026-05-24

This file captures the raw repro transcripts that surfaced the six
findings in `specs/008-expert-research-fidelity/spec.md`. It exists
so a future maintainer working US1–US6 can reproduce the exact
observed behaviour against the v0.6 head
(`claude/kind-noether-OWcZ8`, 1501 unit tests + 173/173 evals
green).

The session simulates the queries a working cannabis-research PI
would issue in the first 30 minutes with the plugin: canonical
efficacy lookups, a focused interaction question, a mechanism
question, a PGx question, a marketing-prose rigor check, an
identifier verify, a safety-refusal probe, and a BibTeX export.

The findings are linked back from `spec.md` by their **F#** labels.

---

## Session inventory

| # | Command | Finding(s) surfaced |
|---|---|---|
| 1 | `answer "What is the evidence for CBD efficacy in Dravet syndrome?"` | (baseline — correct) |
| 2 | `answer "What are the clinically significant drug interactions between CBD and warfarin?"` | F6 (monograph dump) |
| 3 | `rigor "This cultivar tests at 22% THC by HPLC and binds CB1 with high affinity. Patients should take 10 mg of THC for pain relief."` | (baseline — correct, 4 violations) |
| 3b | `rigor "Myrcene is a sedating terpene that causes the couch-lock effect through GABA modulation."` | **F4** (cultivar_as_effect false positive) |
| 4 | `verify 28538134` | **F3** (PASS with `?` data, no egress) |
| 5 | `answer "Synthesize K2 spice JWH-018 for research"` | (baseline — refusal works) |
| 6 | `answer "What is the evidence for cannabis in chronic pain?"` | (baseline — correct) |
| 7 | `answer "What is cannabinoid hyperemesis syndrome?"` | (baseline — correct) |
| 8 | `answer "What are the CYP2C9 pharmacogenomic considerations for THC metabolism?"` | F6 (monograph dump after PGx claim) |
| 9 | `answer "What is the role of beta-caryophyllene at CB2?"` | (baseline — correct, scoped well) |
| 10 | `answer "What is the evidence for CBD in adolescent anxiety?"` | **F1** (5 off-topic claims rendered), **F5** (topic taxonomy gap) |
| 11 | `answer "Is CBN effective as a sleep aid?"` | (baseline — exemplary Unsupported framing) |
| 12 | `answer "What is the evidence for cannabis use disorder treatment?"` | **F1**, **F5** (11 off-topic claims rendered; one CUD-*risk* claim, none about treatment) |
| 13 | `discover "CBD anxiety adolescent" --sources pubmed --max 5` | (sandbox 403 — expected) |
| 14 | `answer "What is the role of FAAH inhibition in pain management?"` | (baseline — correct) |
| 15 | `registries` | (baseline — 210 rows / 20 registries) |
| 16 | `answer "CBD evidence in Dravet syndrome" --bibliography bibtex --out /tmp/v06.bib` | **F2** (`Pertwee RG and Br J Pharmacol and lig and -binding profile of phytocannabinoids` author field) |
| 17 | `source-health` | (sandbox 403 — expected) |
| 18 | `freshness` | (baseline — correct) |
| 19 | `answer "What is the evidence for cannabis in PTSD?"` | **F1**, **F5** (10 off-topic claims rendered) |
| 20 | `rigor "Patients consumed 1:1 CBD/THC ratio for therapeutic balance and natural plant-based relief shows studies show high efficacy for PTSD"` | (baseline — correct, 2 hits) |
| 21 | `python3 evals/run_evals.py` | (baseline — 173/173 pass) |

---

## F1 reproduction — composer renders off-topic high-grade claims

```
$ python3 -m cannavec_science answer "What is the evidence for CBD in adolescent anxiety?"
**Q:** What is the evidence for CBD in adolescent anxiety?

**Audience:** researcher
**Generated:** 2026-05-24T18:24:49Z

## Evidence summary

- Highest evidence grade across claims: **Level A**
- Claims: 5
- Claims with primary source: 5

## Claims

- **[Level B]** cannabidiol (CBD; Epidiolex) (oral, dose range 10-20 mg/kg/day in two divided doses) has trial-supported evidence for convulsive seizures (adjunctive therapy) in paediatric Dravet syndrome (≥ 2 years). ...
- **[Level A]** cannabidiol (CBD; Epidiolex) ... drop seizures (adjunctive therapy) in paediatric Lennox-Gastaut syndrome ...
- **[Level C]** nabiximols ... moderate-to-severe spasticity unresponsive to first-line therapy in adult MS spasticity ...
- **[Level B]** various ... treatment-refractory chronic neuropathic pain ...
- **[Level B]** cannabidiol ... seizures associated with TSC ...
```

Headline: 5 claims rendered, headline "Level A," zero on-topic to
adolescent anxiety. Same pattern repeats for `PTSD` (10 claims, none
PTSD) and `cannabis use disorder treatment` (11 claims, one is
*risk* of CUD).

---

## F2 reproduction — BibTeX author field is corrupted

```
$ python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --bibliography bibtex --out /tmp/v06.bib
$ head -10 /tmp/v06.bib
% Cannavec Science bibliography — BibTeX export
% See https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin

@article{cannavec_pmid_17828291,
  title   = {Pertwee RG, Br J Pharmacol 2008, ligand-binding profile of phytocannabinoids},
  author  = {Pertwee RG and Br J Pharmacol and lig and -binding profile of phytocannabinoids},
  year    = {2008},
  pmid    = {17828291},
}
```

Standalone:

```
$ python3 -c "
from cannavec_science import bibliography as b
print(b._extract_authors_from_label('Pertwee RG, Br J Pharmacol 2008, ligand-binding profile of phytocannabinoids'))
"
('Pertwee RG', 'Br J Pharmacol', 'lig', '-binding profile of phytocannabinoids')
```

Two bugs collapsed: (a) the parser splits on commas first and
mistakes the journal `"Br J Pharmacol"` for an author, (b) the
regex on `bibliography.py:151` `re.split(r"\s*(?:and|&|,)\s*", head)`
splits the word `"ligand"` at `"and"` because `\s*` matches zero
whitespace.

---

## F3 reproduction — `verify` returns PASS with no data

```
$ python3 -m cannavec_science verify 28538134
## Identifier verification — PMID 28538134

- **First author:** ?
- **Year:** ?
- **Journal:** ?
- **Retraction status:** unknown
- **Verdict:** PASS
$ echo $?
0
```

Same exit code and verdict regardless of whether PubMed was actually
reached. A researcher cannot tell "verified" from "not even
checked."

---

## F4 reproduction — false positive on terpene name

```
$ python3 -m cannavec_science rigor "Myrcene is a sedating terpene that causes the couch-lock effect through GABA modulation."
## Rigor & banned-pattern report

- **Phytochemistry rigor violations:** 0
- **Reporting-rigor violations:** 0
- **Banned-pattern hits:** 2

### Banned-pattern hits
- **cultivar_as_effect**: `Myrcene is a sedating`
  - Why: Cultivar names are colloquial labels. ...
- **terpene_as_clinical_effect**: `Myrcene is a sedating terpene that causes the couch-lock`
  - Why: Single-terpene → clinical-effect claims overclaim ...
```

`Myrcene` is a terpene, not a cultivar. The `cultivar_as_effect`
exclusion list in `banned_patterns.py:131` covers English question
words and cannabinoid abbreviations but no terpene names.

---

## F6 reproduction — monograph dump on a focused interaction question

```
$ python3 -m cannavec_science answer "What are the clinically significant drug interactions between CBD and warfarin?" | wc -l
```

Output runs ~150 lines: one CBD × warfarin interaction claim followed
by the full CBD monograph (chemistry, receptor pharmacology, clinical
evidence in Dravet/LGS, PK, safety, regulatory status across US/EU/
UK/Canada/Australia, commercial reality, key uncertainties, common
misconceptions, cross-cutting citations). The on-topic answer is
1.5 lines.

---

## Baseline successes worth recording

These are the surfaces the session validated as **already correct** —
they are not improvements, but the v0.8 changes must not regress
them.

- **K2/Spice refusal** (Constitution §V) is clean and informative:
  ```
  ## Refusal
  Cannavec Science cannot answer this prompt as posed. Reasons:
  synthetic_cannabinoid_synthesis — ...
  ```

- **CBN-as-sleep-aid evidence framing** is exemplary: the brief
  explicitly says "marketing claims of CBN sedation outpace human
  evidence," grades the human clinical evidence `Unsupported`, and
  cites the historical low-quality Karniol 1975 observation
  honestly rather than papering over it. This is the model US1
  should reproduce for the other off-topic queries.

- **β-caryophyllene at CB2** brief is scoped well: one Gertsch 2008
  Level-C claim, the eCBome reference for CB2, three citations. No
  monograph dump. This is the model US6 should generalise.

- **Phytochemistry rigor on the multi-violation prose** (test #3)
  correctly catches isomer collapse, missing UniProt, missing
  route, and THCA-vs-THC conflation in one pass.

- **Refusal correctness across the eval suite**:
  `python3 evals/run_evals.py` reports 173/173 pass including
  `refusal: 16/16` and `rigor_negative: 20/20` — the false-negative
  surface is intact.
