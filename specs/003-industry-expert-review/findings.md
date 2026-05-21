# Industry-Expert Review — Reproducible Findings Transcript

**Companion to**: [`spec.md`](./spec.md)

**Reviewed**: Cannavec Science v0.2 at HEAD of
`claude/beautiful-wozniak-CAmSt`

**Date**: 2026-05-21

**Baseline**: `python3 -m unittest discover -s tests` → 1,064 tests, all
green (1 expected skip).

This file is the reproducible test transcript that anchors the user
stories in `spec.md`. Every finding cites the exact command run and the
observed output excerpt.

---

## Bug B1 — `source-health` AttributeError (P1, Spec US4)

```
$ python3 -m cannavec_science source-health
## Source health probe

Traceback (most recent call last):
  ...
  File "/home/user/Cannavec-Science-Plugin/cannavec_science/__main__.py", line 536, in _cmd_source_health
    status = "ok" if h.ok else "FAIL"
                     ^^^^
AttributeError: 'SourceHealth' object has no attribute 'ok'
```

**Root**: `__main__.py:536-541` reads `h.ok`, `h.rtt_ms`, `h.error`. The
dataclass at `source_health.py:93-108` exposes `status: HealthStatus`,
`latency_ms`, `error_excerpt`.

---

## Bug B2 — `verify` rejects NCT / ChEMBL / UniProt (P1, Spec US5)

```
$ python3 -m cannavec_science verify NCT02224560
[error] not a recognized identifier: NCT02224560

$ python3 -m cannavec_science verify CHEMBL5803
[error] not a recognized identifier: CHEMBL5803

$ python3 -m cannavec_science verify P21554
[error] not a recognized identifier: P21554
```

Constitution §I names "PMID, DOI, ChEMBL ID, NCT ID, or UniProt
accession" as the five primary-source shapes. Only PMID/DOI resolve.

---

## Bug B3 — Δ⁸-THC query returns Δ⁹-THC monograph (P1, Spec US1)

```
$ python3 -m cannavec_science answer "Δ⁸-THC pharmacology and safety"
**Q:** Δ⁸-THC pharmacology and safety
...
- Highest evidence grade across claims: **Unsupported**
- Claims: 0

## Major cannabinoid monograph — THC

# THC — Δ⁹-tetrahydrocannabinol
*Aliases:* Δ9-THC, Δ⁹-THC, delta-9-THC, ...
```

Verified the detector reports both: 

```
$ python3 -c "from cannavec_science.minor_cannabinoids import detect_minor_cannabinoid_mention; from cannavec_science.major_cannabinoids import detect_major_cannabinoid_mention; print([c.name for c in detect_major_cannabinoid_mention('Δ⁸-THC pharmacology')], [c.name for c in detect_minor_cannabinoid_mention('Δ⁸-THC pharmacology')])"
['THC'] ['Δ⁸-THC']
```

The composer at `answer.py:633-635` fires the major monograph because
`total_compounds_named >= 2` — but the user named one compound
(Δ⁸-THC); "THC" is a substring of "Δ⁸-THC", not a separately named
isomer.

---

## Bug B4 — HHC safety query returns 26 CBD/THC AE claims (P1, Spec US2)

```
$ python3 -m cannavec_science answer "HHC safety profile and adverse events"
...
- Highest evidence grade across claims: **Level C**
- Claims: 26
- Claims with primary source: 26

## Claims

- **[Level C]** CBD carries documented somnolence risk in paediatric Dravet / Lennox-Gastaut on adjunctive CBD ...
- **[Level C]** CBD carries documented elevated transaminases ...
- **[Level C]** CBD carries documented diarrhoea risk ...
- **[Level C]** Δ⁹-THC carries documented tachycardia risk ...
[... 22 more CBD / Δ⁹-THC / cannabis AE rows, ZERO HHC-specific rows ...]
```

The AE detector fires on the safety / adverse keyword and dumps the
full registry without filtering by the cannabinoid named in the prompt.

---

## Bug B5 — entourage-effect grade laundering (P1, Spec US3)

```
$ python3 -m cannavec_science answer "What is the evidence that the entourage effect is real?"
...
- Highest evidence grade across claims: **Level A**
- Claims: 10
- Claims with primary source: 10

## Claims

- **[Level B]** cannabidiol (CBD; Epidiolex) ... Dravet syndrome ... (PMID 28538134, Level B)
- **[Level A]** cannabidiol (CBD; Epidiolex) ... Lennox-Gastaut syndrome ... (PMID 29768152, Level A) (PMID 28815401, Level A)
[... eight more claims, none about the entourage effect ...]
```

The Level A grade is attributed to the **answer** about the entourage
effect; the cited Level A studies are CBD-Lennox-Gastaut, not entourage-
effect studies. Constitution §VII (GRADE honesty over confidence
laundering) is violated at the answer-level aggregation.

The rigor pipeline does notice — when you ask
`rigor "myrcene potentiates Δ⁹-THC's sedative effect via synergy"`, the
entourage-overclaim detector correctly fires with the canonical-citation
resolution. So the detector exists; the answer-level aggregation just
ignores it.

---

## Bug B6 — `cannabis × tacrolimus` interaction not matched (P2, Spec US6)

```
$ python3 -m cannavec_science answer "cannabis interaction with tacrolimus transplant"
- Highest evidence grade across claims: **Unsupported**
- Claims: 0

$ python3 -c "from cannavec_science.interactions import detect_interaction_mention; print([(r.cannabinoid, r.partner_drug) for r in detect_interaction_mention('cannabis interaction with tacrolimus transplant')])"
[]
```

But the row exists at `cannavec_science/interactions.py:271` and is
detected when the user names CBD explicitly:

```
$ python3 -c "from cannavec_science.interactions import detect_interaction_mention; print([(r.cannabinoid, r.partner_drug) for r in detect_interaction_mention('CBD tacrolimus')])"
[('CBD', 'tacrolimus')]
```

The word "cannabis" is not expanded to {CBD, Δ⁹-THC, ...} for
interaction matching.

---

## Bug B7 — eCBome registry not wired into `compose_answer` (P2, Spec US7)

```
$ python3 -m cannavec_science answer "endocannabinoid system regulation of inflammation"
- Highest evidence grade across claims: **Unsupported**
- Claims: 0

$ python3 -m cannavec_science answer "PEA anandamide ecBome"
- Highest evidence grade across claims: **Unsupported**
- Claims: 0
```

And:

```
$ grep -n "ecbome\|EcbomeEntry\|find_ecbome\|from cannavec_science.ecbome" cannavec_science/answer.py
(no matches)

$ grep -rn "ecbome\|find_ecbome" cannavec_science/__main__.py
(no matches)
```

The 28-entry eCBome registry at `cannavec_science/ecbome.py` is fully
populated with primary identifiers (UniProt accession or HMDB ID per §I)
but no surface calls into it. Industry-expert questions about
anandamide, 2-AG, FAAH, MAGL, GPR55, PEA, NAPE-PLD never reach it.

---

## Bug B8 — Rigor report emits duplicate entourage violation (P3, Spec US10)

```
$ python3 -m cannavec_science rigor "myrcene potentiates Δ⁹-THC's sedative effect via synergy"
## Rigor & banned-pattern report

- **Phytochemistry rigor violations:** 2
- **Banned-pattern hits:** 0

### Entourage-overclaim (synergy claim without canonical citation)
- `myrcene` × `Δ⁹-THC` — cite Russo 2011 / Finlay 2020 / Santiago 2019 / LaVigne 2021 or reframe as open hypothesis.
- `myrcene` × `Δ⁹-THC` — cite Russo 2011 / Finlay 2020 / Santiago 2019 / LaVigne 2021 or reframe as open hypothesis.
```

Two identical violation entries for one input sentence.

---

## Confirmation that the rigor backbone DOES work (preserve in v0.3 / v0.4)

```
$ python3 -m cannavec_science rigor "Indica strains are sedating because they have more myrcene; sativa strains are energetic"
- **Banned-pattern hits:** 1
- **indica_sativa_as_pharmacology**: ... Why: Indica/sativa/hybrid are not biochemically meaningful ...

$ python3 -m cannavec_science rigor "This cultivar tests at 22% THC by HPLC and the dose was 10 mg"
- **Phytochemistry rigor violations:** 3
### Isomer collapse: `THC by HPLC and the dose`
### Dose without administration route: `10 mg`
### THCA-vs-THC conflation: `tests at 22% THC`

$ python3 -m cannavec_science rigor "Cannabis cures cancer; it's a natural medicine so it's safe"
- **Banned-pattern hits:** 2
- **cure_claim**: cures cancer
- **natural_therefore_safe**: natural medicine so it's safe

$ python3 -m cannavec_science answer "How do I synthesize K2/Spice?"
## Refusal
Cannavec Science cannot answer this prompt as posed. Reasons:
synthetic_cannabinoid_synthesis ... Poison Control (US: 1-800-222-1222)
```

These are the credibility-anchor surfaces. v0.3 MUST NOT regress them.

---

## Confirmation that v0.2 scaffolders + regulatory advisory work

```
$ python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" --pico --power-calc --grade-profile
[... PICO frame, power-calc table, GRADE evidence-profile table all render correctly ...]

$ python3 -m cannavec_science answer "Can I study Δ⁹-THC in rats?" --regulatory-feasibility us
**This is not legal advice; consult your institutional research-compliance office.**
## Regulatory-feasibility advisory — Δ⁹-THC (US)
- Schedule / classification: schedule_i
- Licensing path: DEA Schedule I Researcher Registration (21 CFR §1301.18) ...
- Estimated timeline: 6-18 months for the DEA registration alone
```

These are the v0.2 differentiators. They work. Preserve them.

---

## Industry-expert questions that return 0 claims (P3, v0.4 horizon)

These are research-grade questions a working cannabis-science PI asks.
They sit inside §IV but outside v0.2's clinical-pharmacology focus.

| Prompt | v0.2 result | Why missing |
|---|---|---|
| `Decarboxylation kinetics of THCA in cannabis flower` | 0 claims | analytical-chemistry registry (v0.4 US11) |
| `Pesticide residue limits cannabis testing` | 0 claims | lab-QC, out-of-§IV — explicit refusal path needed |
| `Cannabis vapor pyrolysis byproducts harm reduction` | 0 claims | analytical-chemistry / inhalation-toxicology gap (v0.4 US11) |
| `Bedrocan medical cannabis cultivars THC content` | 0 claims | cultivar-specific, out-of-§IV — refusal path needed |
| `CBD pharmacokinetics oral vs sublingual bioavailability` | 0 claims | CBD PK section is in monograph but not surfaced as claims |
| `CBG antibacterial activity` | 0 claims + CBG monograph | monograph fires but claims block stays empty |
| `endocannabinoid system regulation of inflammation` | 0 claims | eCBome not wired (US7) |
| `PEA anandamide ecBome` | 0 claims | eCBome not wired (US7) |
| `Indica vs sativa pharmacological differences` | 0 claims (silent) | should fire banned-pattern explicitly |

---

## Summary

- **4 P1 shipping bugs** (US1–US5) — visible in the demo path, fixable
  inside the v0.2 architecture without amendments.
- **3 P2 surfacing / wiring issues** (US6, US7, US8, US9) — registry data
  exists; surfacing logic doesn't reach it.
- **1 P3 cosmetic dedup bug** (US10).
- **2 P3 v0.4 registry-depth opportunities** (US11 analytical chemistry,
  US12 cultivation science).

All findings stay inside Constitution §IV (researcher only). The v0.3
release closes the bugs and surfacing gaps; v0.4 adds analytical-
chemistry and cultivation-science depth under the same constitutional
gates.
