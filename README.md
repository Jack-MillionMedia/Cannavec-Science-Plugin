# Cannavec Science (v0.6 — research-domain-breadth build)

**A focused Claude Code plugin for elite-tier cannabis-research science.**

The v0.6 build extends the v0.5 industry-expert-clinical-depth backbone
across four research domains every working cannabis-research scientist
asks about, adds a reporting-rigor module, and adds a thirteenth
primary-source live-discovery lane. All shipping inside Constitution
§IV (v2.0.0 — research-grade for every audience, evidence standard invariant). It also adds a deterministic **quantitative
evidence-synthesis** primitive (specs 011–012): the `meta` subcommand pools
effect sizes into fixed/random-effects estimates with heterogeneity (Q, I²,
τ²), a random-effects **prediction interval**, a GRADE inconsistency verdict,
and `--diagnostics` robustness checks — Egger's small-study-effects test
(→ GRADE publication bias), a leave-one-out sensitivity analysis, **subgroup
analysis** (Cochrane Q_between), and **Duval–Tweedie trim-and-fill** — all
feeding the grade machinery, and `--certainty` rates the pooled body on the
GRADE ⊕-scale with **both** imprecision criteria (CI-vs-null **and** the
Optimal Information Size, spec 018). `--measure prop` additionally pools
**single-arm rates** (adverse-event incidence, prevalence) with the
Freeman-Tukey double-arcsine transform (spec 019), defined even at 0 % / 100 %.
1,760 unit tests green at HEAD; 188 eval prompts
(173 offline) across ten buckets; twenty curated science registries
with ≥ 215 total rows; thirteen live-discovery lanes.

## Read this first

### What this plugin refuses to do (Constitution §IV, v2.0.0)

Cannavec Science delivers **research-grade cannabis science to every
audience** — the evidence standard never drops, whoever is asking. What it
refuses is not a *who* but a *what*: it never lowers the evidence bar, never
gives individualized advice, and never adds non-science operational
surfaces. The following stay out-of-scope (they live in the parent Cannavec
plugin), not because of who asks but because they are not primary-source
research science:

- **Cultivators / growers** — no agronomy advice, IPM, nutrient regimens, or
  lighting recommendations beyond the science-cited row in `cultivation_science`.
- **Lab QC / certificate-of-analysis** — no COA parsers, no ISO 17025 templates,
  no method-validation worksheets.
- **Compliance / regulatory operations** — no GMP, GACP, USDA, FDA, DEA, EFSA, or
  state-license workflows.
- **Retail / dispensary / consumer** — no product recommendations, dosing
  pamphlets, or strain finders.
- **Hemp-industry material science** — no fiber, grain, or industrial-hemp
  surfaces.
- **Individualized medical / dosing / interaction / legal advice** —
  refused for *every* audience by the §V safety layer. Cannavec answers
  "what does the evidence say," never "what should *you* take"; clinical
  decisions remain with licensed clinicians.

If you need any of these, the parent Cannavec plugin or a dedicated industry
tool is the right home.

### How to verify any claim

Every citation Cannavec Science emits is a primary-source identifier you can
re-check yourself. Worked example:

```bash
$ python3 -m cannavec_science verify 28538134
## Identifier verification — PMID 28538134
- **First author:** Devinsky
- **Year:** 2017
- **Journal:** The New England journal of medicine
- **Title:** Trial of Cannabidiol for Drug-Resistant Seizures in the Dravet Syndrome.
- **Retraction status:** clean
- **Verdict:** PASS
```

`verify` accepts all five Constitution §I identifier shapes — **PMID, DOI, NCT,
ChEMBL, UniProt** — and surfaces a `FAIL` verdict (non-zero exit) when the
upstream returns nothing or the local retraction registry flags the identifier.

### Rigor philosophy

Cannavec Science enforces three deterministic rule sets on every composed
answer and on any text submitted to `/rigor`:

1. **Seven phytochemistry detectors** catch the cannabis-domain traps
   non-specialists fall into: bare "THC" without the Δ⁹ / Δ⁸ / THCA isomer
   prefix, receptor names without their UniProt accession (CB1 = P21554,
   CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231), doses without route,
   THCA-vs-Δ⁹-THC conflation, matrix-unit confusion (10 µg/mL of what?),
   missing decarb context, and entourage-effect overclaims without one of
   four named primary sources (Russo 2011, Finlay 2020, Santiago 2019,
   LaVigne 2021).
2. **Six EQUATOR reporting-guideline triggers** — when prompt text mentions
   an RCT, SR, observational study, intervention trial, or systematic review,
   the rigor pass attaches the appropriate CONSORT-2010 / PRISMA-2020 /
   STROBE / ROB-2 / ROBINS-I / AMSTAR-2 expectation.
3. **Sixteen banned-pattern detectors** with a 30-character negation guard:
   indica/sativa as pharmacology, cure claims, ECS as "master regulator",
   "natural = safe", full-spectrum superiority claims without RCT anchoring,
   anecdotes as evidence, and so on.

A clean rigor report means: every claim cites a primary source, no claim's
verb exceeds its evidence grade, no banned pattern fired, and every detected
study-design class has the right reporting guideline attached.

### Network etiquette

Every live discoverer sends a polite `User-Agent` of the form
`cannavec-<lane>/<version>` (e.g. `cannavec-pubmed-verify/0.6`,
`cannavec-chembl-discover/0.6`). Sysadmins watching NCBI / Crossref / EBI /
EuropePMC traffic see exactly which lane is calling.

For Crossref's polite-pool, set `CANNAVEC_CROSSREF_MAILTO` to an email
address you control:

```bash
export CANNAVEC_CROSSREF_MAILTO="research@your-org.example"
```

If the env var is unset the fetcher sends no mailto — polite-anonymous beats
impolitely-fake. The same address is forwarded to OpenAlex (which grants
higher per-IP rate limits to identified clients).

All 13 lanes use bounded retry + exponential backoff on transient HTTP 429
/ 502 / 503 / 504 and on `URLError`, honouring `Retry-After` (capped at 30
seconds) so a misbehaving upstream cannot stall the fan-out. Operators who
want internal diagnostics can set `CANNAVEC_LOG_LEVEL=DEBUG`; the structured
logger writes to stderr and never pollutes the JSON / Markdown output stream.

### Determinism guarantee

There is no LLM in the inference path. Every claim's GRADE is computed by
`evidence.py:apply_grade_modifiers`. Every refusal is computed by
`safety.py` and `banned_patterns.py`. Every rigor violation is a regex match
in `rigor_checks.py` or `reporting_rigor.py`. Two identical inputs produce
byte-identical outputs — modulo the `generated_at` timestamp — so a
peer-reviewer can re-run any answer and get exactly the same brief.

### Power-user CLI

The five slash commands wrap the underlying CLI; advanced operational
subcommands are accessible directly via `python3 -m cannavec_science <cmd>`:

| Subcommand | Purpose |
|---|---|
| `bibliography <answer.json>` | Re-render a saved Answer's citations into BibTeX, RIS, or CSL-JSON. |
| `registries [--registry <name>] [--format json]` | Inventory the 20 curated registries — row counts, freshness dates. |
| `source-health [--sources <list>] [--json]` | Per-source liveness probe. Non-zero exit if any source is yellow / red. |
| `freshness [--registry <name>] [--network] [--parallel N]` | Retraction-watch probe over `watch_pmids`. Offline by default. |
| `freshness-report [--since <date>]` | Curator-facing freshness report with a date filter. |
| `meta <studies.json> [--measure OR\|RR\|MD\|SMD\|prop\|generic] [--diagnostics] [--certainty] [--json]` | Pool per-study effect sizes (specs 011–019) into a fixed-effect + DerSimonian–Laird random-effects estimate with heterogeneity (Cochran's Q, I², τ²), a prediction interval, and a **GRADE inconsistency verdict**. `--diagnostics` adds Egger's small-study-effects test, leave-one-out sensitivity, **subgroup analysis** (Q_between), and **trim-and-fill** bias adjustment; `--certainty` adds the GRADE ⊕ rating (with the spec 018 Optimal-Information-Size imprecision criterion); `--measure prop` pools **single-arm rates** (Freeman–Tukey double-arcsine, spec 019 — incidence/prevalence, valid at 0 %/100 %). Every study must carry a primary-source identifier (§I), and may carry a `subgroup` label; the run refuses with a non-zero exit on a missing identifier. |

`discover` accepts `--parallel N` (default 1; recommended ≤ 4 for NCBI
etiquette) to fan out across the 13 lanes concurrently. Result ordering
stays alphabetical-by-source regardless of completion order so identical
runs produce identical JSON.

### Quantitative evidence synthesis (`meta`, spec 011)

Discovery and grading tell you *which* studies exist and *how trustworthy*
each one is. The `meta` subcommand answers the next question a review team
asks: **do the studies agree, and what does pooling them say?** It is the
backbone's biostatistician — a deterministic, stdlib-only meta-analysis with
no LLM and no network in the path.

Feed it a JSON list of effect sizes (raw 2×2 tables for OR/RR, raw arm
summaries for MD/Hedges'-g SMD, or precomputed `yi`/`vi`) and it returns an
inverse-variance **fixed-effect** and **DerSimonian–Laird random-effects**
pooled estimate, **Cochran's Q** (with its χ² p-value), **I²**, and **τ²**:

```bash
$ python3 -m cannavec_science meta cbd_seizures.json --measure OR
## Meta-analysis — OR (3 studies)

| Study | Identifier | Effect | 95% CI | Weight |
|---|---|---|---|---|
| Devinsky 2017 (Dravet) | PMID:28538134 | 0.287 | [0.096, 0.857] | 27.1% |
| Devinsky 2018 (LGS)    | PMID:29768151 | 0.359 | [0.145, 0.889] | 39.5% |
| Thiele 2018 (LGS)      | PMID:29503056 | 0.300 | [0.112, 0.804] | 33.4% |

**Random effects (DerSimonian–Laird):** 0.318 [0.180, 0.563]  (p = 0.0001)
**Heterogeneity:** Q = 0.118 (df = 2, p = 0.9429), I² = 0%, τ² = 0.000
**GRADE inconsistency:** not serious — I² = 0% indicates low heterogeneity (< 40%).
```

For k ≥ 3 the random-effects line also carries a **95% prediction interval**
(Higgins–Thompson–Spiegelhalter 2009; IntHout 2016) — the range a *new*
study's true effect would plausibly fall in. When heterogeneity is high it is
far wider than the confidence interval, which is exactly the point: a pooled
CI of `[−0.05, 0.85]` at I² = 75% hides a prediction interval of
`[−4.89, 5.69]`. The t-quantile comes from a stdlib bisection on the Student's-t
survival function — no SciPy.

The headline output is a **GRADE inconsistency verdict** derived from I² on
the Cochrane thresholds (`< 40%` → not serious; `40–75%` → serious, one
downgrade; `≥ 75%` → very serious, two downgrades). That verdict flows
straight into the existing `evidence.apply_grade_modifiers` ladder and the
`grade_profile` table — closing the loop that previously hardcoded the
inconsistency column to "not serious". Two constitutional invariants hold:

- **§I.** Every effect size must carry a primary-source identifier
  (PMID / DOI / NCT / ChEMBL / UniProt / URL). A study without one refuses
  with a non-zero exit; you cannot pool an unanchored number.
- **§VII.** The inconsistency downgrade is *computed*, not asserted — the
  same studies always produce the same verdict.

**Robustness diagnostics (`--diagnostics`, spec 012).** A reviewer never
stops at the pooled number. Add `--diagnostics` and `meta` also runs **Egger's
regression test** for funnel-plot asymmetry / small-study effects and a
**leave-one-out sensitivity analysis** that re-pools the evidence dropping
each trial in turn (surfacing the study whose removal would most change the
conclusion). The publication-bias verdict is GRADE-honest about its own
limits: Egger's test is underpowered below 10 studies (Sterne 2011, BMJ), so a
positive test with `3 ≤ k < 10` is *reported but does not trigger a downgrade*
— only `k ≥ 10` with `p < 0.10` is "strongly suspected". When fed into
`grade_profile`, the Egger and heterogeneity findings downgrade the certainty
grade *cumulatively*, through the same `evidence._downgrade` ladder the GRADE
adapter uses. The Student's-t and incomplete-beta numerics are stdlib `math`
only — no SciPy.

**Explain it and adjust it (spec 014).** `--diagnostics` also runs the two
methods a senior reviewer reaches for next. **Subgroup analysis** partitions
the trials by a `subgroup` moderator (dose band, route, indication) and runs
Cochrane's *test for subgroup differences* (Q_between) — a significant result
means the moderator explains part of the heterogeneity (e.g. high-dose OR 0.21
vs low-dose OR 0.66, Q_between p = 0.006). **Trim-and-fill** (Duval & Tweedie
2000, L0) estimates how many studies the funnel asymmetry implies are missing,
imputes their mirror images, and reports a **bias-adjusted estimate** — the
imputed studies are explicitly hypothetical, carry no identifier, and are
never presented as cited evidence (§I). Both reuse the spec 011 pooling core
and stay byte-for-byte deterministic.

**Make it actionable — absolute effects & NNT (`--baseline-risk`, spec 015).**
A pooled odds ratio of 0.52 is not yet a decision. The GRADE *Summary-of-
Findings* table turns it into one by anchoring it to an **assumed comparator
risk** and reading off the **anticipated absolute effect**. Pass
`--baseline-risk` (with `--outcome`, optional `--baseline-pmid` to anchor the
baseline per §I, and `--outcome-desirable` to flip the benefit direction) and
`meta` appends that row:

```bash
$ python3 -m cannavec_science meta cbd_seizures.json --measure RR \
    --baseline-risk 0.40 --outcome "convulsive seizures" \
    --baseline-source "pooled placebo arms" --baseline-pmid 28538134
### Anticipated absolute effects — convulsive seizures

- **Relative effect:** RR 0.52 (95% CI 0.4 to 0.68)
- **Assumed comparator risk:** 400 per 1000 (40%) — pooled placebo arms [PMID:28538134]
- **Corresponding intervention risk:** 208 per 1000 (95% CI 161 to 270)
- **Risk difference:** 192 fewer per 1000 (95% CI 239 fewer to 130 fewer)
- **Number needed to treat:** NNTB 5.22 (95% CI 4.18 to 7.69)
```

Two rigor guarantees come with it. **Direction is never guessed** — NNTB vs
NNTH is derived from whether the outcome is desirable, so a risk *increase* is
a benefit for "responders" and a harm for "adverse events" (§VII). And the
**NNT confidence interval is honest about the null**: when the relative-effect
CI crosses 1, there is no finite NNT range — it runs from a benefit, through
infinity, to a harm. Per Altman 1998 (*BMJ* 317:1309) `meta` prints
`NNTB 13.85 to ∞ to NNTH 13.97` rather than a naive finite interval that hides
the discontinuity. The assumed baseline carries its own provenance: an
unsourced one is rendered with a visible "not primary-source anchored" caveat
and `acr_sourced: false` in `--json`, so an illustrative baseline is never
laundered as a measured fact (§I). The translation is `RR · ACR` for risk
ratios and the GRADE odds→risk transform for odds ratios; pure stdlib `math`.

**Rate the certainty — the SoF table's first column (`--certainty`, spec 016).**
A Summary-of-Findings table reports an effect *and how much to trust it*. Add
`--certainty` and `meta` rates the pooled body of evidence on the GRADE
⊕-scale, routing the five downgrade domains through the **same**
`evidence._downgrade` ladder the evidence-profile table uses. It is honest
about which domains it can and cannot compute: **inconsistency** (the I²
verdict), **imprecision** (**both** GRADE criteria, spec 018 — the pooled 95% CI
crossing the null *and* the **Optimal Information Size**: a pool whose total
enrolment falls short of a single adequately powered trial is downgraded even
when its CI looks tight, the confidence-laundering a CI-only check misses), and
**publication bias** (Egger, under `--diagnostics`, with the `k ≥ 10` honesty)
are *computed*; **risk of bias** and **indirectness** are taken as reviewer
inputs (`--risk-of-bias`, `--indirectness`) and tagged as such, never fabricated
(§II). The OIS is sized from the pooled effect and the assumed control rate
(`--baseline-risk` for RR/OR; an SMD pool needs nothing; `--pooling-sd` for MD)
by composing the same Cohen-1988 / Fleiss-1981 calculators the `--power-calc`
scaffolder uses — so one control rate drives both the absolute effect and the
imprecision verdict. The starting grade is the body design (`--evidence-base
rct|observational` → High / Low). Together with `--baseline-risk` this is the
full GRADEpro deliverable:

```
### GRADE certainty of evidence
**⊕⊕⊕⊝ Moderate** (Level B) — 1 downgrade step(s) from Level A.

| Domain | Assessment | Downgrade | Basis |
|---|---|---|---|
| Risk of bias     | serious     | −1 | reviewer-assessed             |
| Inconsistency    | not serious | —  | computed (I²=0%)              |
| Indirectness     | not serious | —  | reviewer-assessed             |
| Imprecision      | not serious | —  | computed (pooled 95% CI vs null; OIS 605/202 (meets)) |
| Publication bias | not assessed| —  | not assessed (run --diagnostics) |
```

certainty → relative effect → assumed/corresponding risk → NNT, one command,
no LLM in the path.

**Weave it into the brief (`answer --sof FILE`, spec 017).** The Summary-of-
Findings table is most useful *inside* a research brief, beside the prose and
the per-claim GRADE evidence profile. `answer --sof sidecar.json` pools the
§I-anchored studies for each named outcome and appends a **Summary of
Findings** section — one block per outcome carrying the full
certainty → relative → absolute → NNT chain — to both the Markdown brief and
the `--json` `scaffolders.summary_of_findings`. The sidecar is a list of
outcomes, each with its `studies`, `measure`, optional `baseline`, and the
reviewer-assessed GRADE domains; everything else reuses the spec 011/015/016
backbone (no new statistics). A study without a primary-source identifier
refuses the whole section — a brief never carries an unanchored pooled number.

**Pool a single-arm rate (`meta --measure prop`, spec 019).** Not every question
is a contrast. A toxicologist pooling adverse-event *incidence*, or an
epidemiologist pooling *prevalence*, needs a rate — not an odds ratio. `meta
--measure prop` pools single-arm counts with the **Freeman-Tukey double-arcsine**
transform (defined at 0 % and 100 %, where a logit pool fails), reusing the same
fixed/random pooling, heterogeneity, prediction-interval, and GRADE-inconsistency
machinery, then back-transforms to a rate via the Miller-1978 inverse:

```
## Single-arm proportion meta-analysis (Freeman-Tukey)
- **Studies (k):** 4
- **Pooled rate (random):** 40.2% (95% CI 29.1% to 51.7%)
- **Heterogeneity:** Q = 11.95 (df 3), I² = 75%, τ² = 0.0411
- **95% prediction interval:** 2.7% to 86.8% (plausible rate in a new setting)
- **GRADE inconsistency:** serious — I² = 75% …
```

The sidecar is single-arm `{events, n}` rows, each §I-anchored; the footnote
states plainly that a pooled rate **carries no comparator — it is not a treatment
effect**, so the surface can never be read as an efficacy claim.

### What v0.6 ships

1. **Pain medicine registry (≥ 7 curated rows)** — NASEM 2017
   chapter-4 conclusive-evidence finding for chronic pain anchored
   to Whiting 2015 JAMA SR (PMID 26103030), Stockings 2018 PAIN SR
   (PMID 30121596), Mücke 2018 Cochrane neuropathic (PMID 29513392),
   Boehnke 2019 J Pain prospective MMJ cohort (PMID 31237829),
   Andreae 2015 J Pain IPD meta-analysis (PMID 25840040), and de
   Vita 2018 experimental-pain SR (PMID 30362962). The Mücke vs
   Whiting tone divergence is a teaching example of evidence-base vs
   evidence-interpretation differences.
2. **Cannabis-and-psychosis psychiatry registry (≥ 6 rows)** —
   Di Forti 2019 EU-GEI multinational case-control Lancet Psychiatry
   (PMID 30902669, the high-potency-cannabis daily-use first-episode-
   psychosis study), Marconi 2016 Schizophr Bull dose-response SR
   (PMID 26884547), Vaucher 2018 Mol Psychiatry Mendelian-randomization
   bidirectional-causality analysis (PMID 29039420) WITH explicit
   instrument-validity caveats, Bhattacharyya 2009 Arch Gen Psychiatry
   acute-Δ⁹-THC fMRI healthy-volunteer challenge (PMID 19996036),
   Hjorthøj 2023 Lancet Psychiatry Danish national-register cohort
   (PMID 36402143), and Murray 2017 Lancet Psychiatry narrative
   review.
3. **Driving-impairment science registry (≥ 5 rows)** — Compton 2017
   NHTSA Virginia Beach case-control crash-risk study (DOT HS 812 411,
   the most-cited AND most-mis-cited result in the cannabis-driving
   literature — unadjusted OR ≈ 1.25, adjusted OR ≈ 1.05 after
   demographics + alcohol), Hartman 2015 Clin Chem plasma-Δ⁹-THC
   dose-response (PMID 25371545), Marcotte 2022 JAMA Psychiatry
   driving-simulator dose-and-duration RCT (PMID 35138350, ~1.5 h
   peak impairment / ~5 h return-to-baseline), Brubacher 2022 NEJM
   BC trauma-centre post-legalization cohort (PMID 35081282), and
   Bondallaz 2016 Forensic Sci Int SR (PMID 27082781). The SCIENCE,
   not the LAW — per-se law surfaces remain in the parent plugin
   per Constitution §IV.
4. **PTSD / anxiety / sleep registry (≥ 5 rows)** — Bonn-Miller 2021
   PLOS One PTSD smoked-cannabis cross-over RCT (PMID 33667097)
   surfaces with the **largely-negative primary endpoint honestly
   stated** (no confidence-laundering); Crippa 2011 J Psychopharmacol
   CBD-SAD SPECT acute challenge (PMID 20829306); Bergamaschi 2011
   Neuropsychopharm CBD-SAD public-speaking (PMID 21307846); Bedi
   2010 Drug Alcohol Depend biphasic acute-Δ⁹-THC anxiety dose-
   response (PMID 19897322); and Walsh 2017 Sleep Med Rev cannabinoids-
   and-sleep SR (PMID 28392485) with the 'limited and inconclusive
   evidence' SR verdict honestly stated.
5. **Reporting-rigor module (≥ 6 detectors)** — A §VII GRADE-honesty
   deepening. Detectors flag when prompt text describes a study-design
   class without acknowledging the appropriate EQUATOR-network
   reporting guideline (CONSORT-2010 for RCTs per Schulz 2010 BMJ
   PMID 20335313, PRISMA-2020 for SRs per Page 2021 BMJ PMID
   33781993, STROBE for observational studies per von Elm 2007 PMID
   17938396) or risk-of-bias / quality tool (ROB-2 for RCT bias per
   Sterne 2019 BMJ PMID 31462531, ROBINS-I for non-randomized
   intervention studies per Sterne 2016 BMJ PMID 27733354, AMSTAR-2
   for SR quality per Shea 2017 BMJ PMID 28935701). Detectors
   integrate into the existing `RigorCheckReport` and surface in the
   `rigor` subcommand output. Each detector ships with positive +
   negative unit tests.
6. **OpenAlex live-discovery lane (13th primary source)** — Open
   scholarly citation graph (PubMed + preprints + conference
   proceedings + open citation network). Available via
   `discover --include-openalex` or by adding `openalex` to
   `--sources`. Source-health probe added. Same offline-test
   contract as every other live lane (injected fetcher, no escape
   network calls in the test suite).
7. **Four new registry-inventory groups** — `python3 -m cannavec_science
   registries` now surfaces `pain_medicine`, `psychiatry`,
   `driving_impairment`, and `ptsd_anxiety_sleep`; total inventory
   grows from 16 → 20 curated registries.

### What v0.5 shipped (preserved)

A working cannabis-research scientist needs more than a literature search:
they need primary citations they can defend, phytochemistry precision
they can publish, live access to the frontier (including preprints),
deterministic GRADE-level rigor with field-pushback signal, researcher-
workflow scaffolding (PICO, sample-size power, GRADE evidence-profile
table, IRB protocol skeleton), primary-source-anchored analytical
chemistry and cultivation science, and — new in v0.5 — **clinical
pharmacokinetics** (THC inhaled / oral PK, CBD food effect, 11-OH-Δ⁹-THC
active metabolite, nabiximols oromucosal, distribution, urine detection
window), **cannabis use disorder & withdrawal** (DSM-5 CUD framework,
CUDIT-R, CWS, NESARC-III prevalence, twin-study heritability,
adolescent-onset telescoping), **cannabinoid hyperemesis syndrome**
(Sorensen 2017 / Allen 2004 diagnostic criteria, Rome IV, capsaicin
treatment, post-legalization epidemiology), **eCBome enzyme-inhibitor
pharmacology** (PF-04457845 cannabis-withdrawal Phase 2a, the BIA
10-2474 Rennes disaster *with* off-target-serine-hydrolase
disambiguation, MAGL inhibitor ABX-1431, dual JZL195), and **cannabinoid
biosynthesis pathway** (OLS / OAC polyketide entry, CBGAS
prenyltransferase, THCA / CBDA synthase enzymology, Luo 2019 yeast
heterologous expression). Cannavec Science ships exactly those things —
researcher-only, stdlib-only, deterministic.

This is the **v0.5 industry-expert-clinical-depth build** descending from
the v0.4 industry-expert-depth build (spec 004) and earlier specs. v0.5
lands five new curated registries (≥ 28 new rows total) and a twelfth
primary-source live-discovery lane (Europe PMC, complement to PubMed)
without broadening the researcher-only audience lock. The build is now
**1,360+ unit tests strong** with a 16-prompt clinical-pharmacology-depth
eval bucket on top of the 144-prompt v0.4 battery — **162 prompts total
(149 offline)** in the eval suite.

### What v0.5 ships

1. **Clinical pharmacokinetics registry (≥ 8 curated rows)** — THC
   inhaled (smoked + vaped) PK per Huestis 2005 (PMID 16142973) +
   Spindle 2018, THC oral / dronabinol PK per Wall 1983 (PMID 6311559),
   CBD oral food effect per Birnbaum 2019 (PMID 31166007 — the
   Epidiolex label-supporting 4-5× AUC increase with high-fat meal),
   11-OH-Δ⁹-THC active metabolite (the first-pass-effect explanation
   for why edibles produce a longer / different subjective profile),
   nabiximols oromucosal per Karschner 2011 (PMID 21240010), plasma
   protein binding + adipose sequestration per Garrett 1977, and
   SAMHSA-cutoff urine detection window per Huestis 1996 (PMID 8773290).
2. **Cannabis use disorder & withdrawal registry (≥ 6 curated rows)** —
   DSM-5 CUD framework per Hasin 2013 (PMID 23537606), CUDIT-R
   screening instrument per Adamson 2010 (PMID 20231083), Cannabis
   Withdrawal Scale per Allsop 2011 (PMID 21652129), NESARC-III
   12-month / lifetime prevalence per Hasin 2015 (PMID 26502112),
   twin-study heritability per Verweij 2010 (PMID 20096023), and
   adolescent-onset telescoping per Chen 2009 / Hall & Degenhardt 2009.
3. **Cannabinoid hyperemesis syndrome registry (≥ 4 curated rows)** —
   diagnostic criteria per Sorensen 2017 systematic review (PMID
   27567272) + Allen 2004 original 9-case series (PMID 15082584) +
   Simonetto 2012 Mayo Clinic 98-case series (PMID 22305024), Rome IV
   functional GI framework per Venkatesan 2019 (PMID 31480576),
   topical capsaicin acute-phase treatment per Dezieck 2017 (PMID
   28215116), and post-legalization Colorado ED epidemiology per
   Kim 2018 (PMID 30049481). The existing static CHS caution remains
   intact — the registry adds primary citations alongside it.
4. **eCBome enzyme-inhibitor pharmacology registry (≥ 5 curated rows)**
   — PF-04457845 cannabis-withdrawal Phase 2a per D'Souza 2019 (PMID
   30985083), PF-04457845 osteoarthritis-pain Phase 2 per Huggins 2012
   (PMID 22910298), **BIA 10-2474 Rennes Phase 1 disaster** per Kerbrat
   2016 (PMID 27806243) *with explicit off-target-serine-hydrolase
   disambiguation* per van Esbroeck 2017 (PMID 28912346 — the
   activity-based protein profiling paper proving BIA 10-2474 toxicity
   is OFF-TARGET, not on-target FAAH biology), MAGL inhibitor ABX-1431
   per Cisar 2018 (PMID 29498523), and dual FAAH / MAGL inhibitor
   JZL195 mechanism per Long 2009 (PMID 19429692).
5. **Cannabinoid biosynthesis pathway registry (≥ 5 curated rows)** —
   OLS + OAC polyketide entry per Taura 2009 (PMID 19429605) + Gagne
   2012 (PMID 22802647), CBGAS aromatic prenyltransferase per Page
   2011 (PMID 21896800), THCA synthase FAD-dependent oxidocyclase per
   Sirikantaramas 2004 (PMID 15453749), CBDA synthase per Taura 1996
   (PMID 8632416), and Saccharomyces-cerevisiae heterologous
   expression per Luo 2019 (PMID 30814733).
6. **Europe PMC live-discovery lane (12th primary source)** — Europe
   PMC indexes PubMed PLUS the full PMC corpus PLUS European
   non-MEDLINE-indexed journals. Available via
   `discover --include-europepmc` (opt-in flag) or by adding
   `europepmc` to `--sources`. Same offline-test contract as every
   other live lane (injected fetcher, no escape network calls in the
   test suite).
7. **Five new registry-inventory groups** — `python3 -m cannavec_science
   registries` now surfaces `pharmacokinetics`, `use_disorder`,
   `hyperemesis_syndrome`, `ecbome_inhibitors`, and `biosynthesis`;
   total inventory grows from 159 → ~187 rows across **16** (was 11)
   curated registries.

### What v0.4 shipped (preserved)

1. Analytical-chemistry registry (≥ 8 curated rows) — decarboxylation
   kinetics (Veress 1990 PMID 2384545, Wang 2016, Citti 2018), HPLC
   potency analysis vs GC-MS in-injector decarboxylation artefact (Dussy
   2005, Citti 2018), chemovar Type I/II/III/IV/V classification
   (Hazekamp & Fischedick 2012 PMID 22362625, Lewis 2018), THCA-/CBDA-
   synthase locus inheritance (Hillig & Mahlberg 2004, Aizpurua-Olaizola
   2016), and combustion-vs-vaporisation pyrolysis byproducts
   (Pomahacova 2009, Moir 2008).
2. Cultivation-science registry (≥ 6 curated rows) — UV-B effect on
   cannabinoid biosynthesis (Lydon 1987 PMID 3621052), glandular
   trichome biology (Livingston 2020 PMID 31867754, Tanney 2021),
   THCA-/CBDA-synthase single-locus inheritance (de Meijer 2003 PMID
   12663552), CBDA-synthase enzymology (Taura 2007), F1 heterozygote
   Type II dominance, and the **honest-debate botanical taxonomy** row
   surfacing both Small & Cronquist 1976 (single species) AND Hillig
   2005 (multi-species) without picking a winner.
3. `Answer.notes` rendering fix — v0.3 set the 0-claim classification
   on `Answer.notes` but `Answer.to_markdown()` never surfaced it.
   v0.4 renders a `## Notes` section so the researcher actually sees
   the actionable hint.
4. Strengthened indica/sativa banned pattern catches the abstract
   meta-framing ("indica vs sativa pharmacological differences") while
   leaving botanical-taxonomy framings ("Cannabis sativa L. botanical
   taxonomy") cleanly through.

### What v0.3 fixes

1. **Δ⁸-THC pharmacology no longer fires the Δ⁹-THC monograph** —
   span-aware `NamedCannabinoidSet` resolves the prompt's named-isomer
   set BEFORE any registry detector fires (US1 / FR-001).
2. **`HHC safety profile` returns 0 cannabinoid-attributed AE claims**
   instead of 26 unrelated CBD / Δ⁹-THC rows — every AE / interaction
   / contraindication / population detector now accepts a
   `cannabinoid_filter` keyword and `compose_answer` wires the prompt's
   named-isomer set through (US2 / FR-002).
3. **`entourage effect evidence` no longer reports "highest evidence
   grade: Level A"** — the answer-level grade aggregation now respects
   a deterministic topical-relevance signal. Hypothesis-anchored prompts
   require the canonical citations (Russo 2011 / Finlay 2020 /
   Santiago 2019 / LaVigne 2021) to count as topical (US3 / FR-003).
4. **`source-health` no longer crashes with `AttributeError`** —
   the CLI handler reads the actual `SourceHealth` dataclass shape
   (`status`, `latency_ms`, `error_excerpt`) plus a new `--json`
   structured output (US4 / FR-004).
5. **`verify` accepts all five Constitution §I identifier shapes** —
   PMID, DOI, NCT, ChEMBL, and UniProt resolvers, each with the
   established offline-injected-fetcher contract per Constitution §III
   (US5 / FR-005).
6. **`cannabis × tacrolimus` now matches the CBD-tacrolimus row** —
   the noun "cannabis" / "marijuana" / "marihuana" / "weed" expands to
   the cannabinoid set {CBD, Δ⁹-THC, CBN, CBG, THCV} for partner-drug
   matching (US6 / FR-006).
7. **`anandamide FAAH inhibition` now surfaces the eCBome registry** —
   `compose_answer` imports `cannavec_science.ecbome` and attaches
   eCBome entries when the prompt names a mediator / receptor / enzyme
   / transporter (US7 / FR-007).
8. **`python3 -m cannavec_science registries` lists every covered
   cannabinoid / terpene / interaction-partner / AE / contraindication
   / PGx allele / eCBome entry** — markdown + `--format json` (US8 /
   FR-008).
9. **0-claim answers carry a discriminated-union classification** —
   refusal / out-of-scope-audience / out-of-scope-deferred /
   in-scope-uncurated / in-scope-phrasing-mismatched, with an
   actionable hint pointing the user at `discover` or the parent
   plugin (US9 / FR-009).
10. **The rigor report deduplicates violations by (detector, span)** —
    one (terpene, cannabinoid) pair in one sentence fires one
    violation, not two (US10 / FR-010).

## What ships

- **Five slash commands.** No more, no less. v0.2 / v0.3 add new
  functionality through flags + Python-module subcommands, never a
  sixth slash command (Constitution §IV).
- **Span-aware `NamedCannabinoidSet` (v0.3)** — every prompt's named-
  isomer set is resolved deterministically before any registry detector
  fires. The Δ⁸-THC / HHC / THCO / THCP / THCV / CBDV / CBC / CBN / CBG
  / THCA / CBDA branches no longer collapse into the Δ⁹-THC monograph.
- **Cannabinoid-scoped registry detectors (v0.3)** — AE, interaction,
  contraindication, and population detectors accept a `cannabinoid_filter`
  parameter; `compose_answer` wires the prompt's named-isomer set
  through so a CBD safety query never surfaces Δ⁹-THC AE rows.
- **Topical-relevance grade aggregation (v0.3)** — `EvidenceSummary.
  highest_grade` is computed over topically-relevant claims only.
  Hypothesis-anchored prompts like "entourage effect evidence" require
  the canonical citations to count as topical.
- **Five-shape `verify` resolver (v0.3)** — PMID, DOI, NCT, ChEMBL,
  and UniProt, with the established offline-injected-fetcher contract.
- **`registries` subcommand (v0.3)** — list every curated row, grouped
  by registry, with row counts, last-verified dates, and entry labels.
  Markdown + `--format json`.
- **Eight curated science registries** — major + minor cannabinoids
  (including Δ⁸-THC, HHC, THCO, THCP at v0.2 elite depth), terpenes,
  drug interactions, adverse events, populations, contraindications,
  pharmacogenomics. Every row PubMed-cited, every row freshness-tracked
  via the v0.2 ``watch_pmids`` field.
- **Seven phytochemistry rigor detectors** — isomer collapse,
  receptor-without-ID, dose-without-route, THCA-vs-THC conflation,
  matrix-unit confusion, decarb-context-missing, and the **v0.2
  entourage-overclaim detector** (synergy claims without canonical
  citation).
- **15-pattern banned-pattern detector** with a 30-char negation
  guard — catches indica/sativa-as-pharmacology, cultivar-as-effect,
  marketing ratios, "natural therefore safe," "cure" claims, etc.
- **Safety preflight** — refuse-harmful / refuse-individualized /
  add-caution / proceed. K2/Spice synthesis is hard-refused.
- **Retraction enforcement at composition time** — a retracted PMID
  is suppressed from the answer's claims (not just flagged post-hoc).
- **Registry-freshness probe (v0.2)** — every registry row carries
  ``last_verified`` + ``watch_pmids``; the ``freshness`` subcommand
  walks the registries and surfaces retractions / EOCs / stale dates
  without auto-mutating curated rows.
- **Live discovery across eleven primary sources** — PubMed, ChEMBL,
  ClinicalTrials.gov, PubChem, PharmGKB, RCSB PDB, Open Targets, GWAS
  Catalog, BindingDB plus the **v0.2 preprint lanes** bioRxiv and
  medRxiv (Level D cap, ``live_biorxiv`` / ``live_medrxiv`` provenance,
  published-version Crossref cross-reference).
- **Deterministic cross-source synthesis** — STRONG / MIXED / WEAK /
  NONE convergence verdict across the eleven sources, with the
  per-source distinct-supporters count and one-line disagreement
  description.
- **Citation-network field-pushback (v0.2 US4)** — ``verify <PMID>``
  fetches the forward-citation set via NCBI elink, applies the
  deterministic ``pubmed_sentiment`` classifier per-cite, and flips
  ``inconsistency_serious=True`` in the GRADE adapter on refute-heavy
  pushback — producing a deterministic one-level downgrade.
- **Researcher-workflow scaffolders (v0.2 US2)** — ``--pico``,
  ``--power-calc``, ``--grade-profile``, ``--protocol-skeleton`` flags
  on the ``answer`` command. PICO frame, stdlib-only sample-size
  estimator (Cohen 1988 continuous + Fleiss 1981 proportion +
  Fleiss-Tytun-Ury continuity correction + odds-ratio path), GRADE
  evidence-profile table (Markdown / CSV), 9-section IRB protocol
  skeleton with auto-generation watermark.
- **Regulatory-feasibility advisory (v0.2 US6)** — per-jurisdiction
  matrix (US-federal / EU-EMA / Canada / UK-MHRA) × per-cannabinoid;
  watermark on every output (``This is not legal advice; consult
  your institutional research-compliance office.``).
- **Endocannabinoidome reference (v0.2 US6)** — 28-entry eCBome
  (mediators / receptors / enzymes / transporters), every entry with
  a primary UniProt or HMDB identifier.
- **Bibliography export to BibTeX / RIS / CSL-JSON** with inline
  GRADE annotation. Drop straight into Zotero / Mendeley / EndNote.
- **115-prompt eval suite (v0.2 US3)** — six category buckets
  (curated / rigor-positive / rigor-negative / refusal / live /
  cross-cutting) with bucket-minimum enforcement at unit-test time
  AND at runner time. Regression battery dense enough to catch drift
  on any backbone change.

## What does NOT ship (deliberately)

Per the [Constitution §IV](.specify/memory/constitution.md) (v2.0.0,
research-grade for every audience), the following remain **out of scope** —
either because they would lower the evidence bar, give individualized
advice, or are non-science operational surfaces that live in the parent
Cannavec plugin:

- Patient, clinician, cultivator, lab, compliance, retail,
  public-health, operator, policy, product, hemp, microbiome,
  veterinary surfaces.
- *Fully-automatic* KB promotion, gap detection, BM25 search, proposal
  generation. (Human-approved KB promotion — the §IX v2.0.0 flywheel — is
  now in-scope: a curator approves each promotion and the row must clear
  the same primary-source + retraction + rigor gate as a hand-curated row.)
- Signed artifacts, watchlists, persistent expert profiles.
- Per-state US regulatory feasibility (v0.2 advisory is US-federal
  only; per-state law lives in the parent plugin).
- Per-state hemp-derived cannabinoid law, pesticide registry.
- CourtListener / legal discovery.
- AlphaFold predicted structures (RCSB experimental only).
- Curator-agent *auto*-mutation of registry rows without a human gate —
  the freshness probe and the discovery flywheel surface and stage
  candidates; a human curator approves before anything becomes a curated
  fact (§IX v2.0.0).

We did not ship them so we could ship the core exceptionally well.

## 30-second quickstart

```bash
git clone https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin
cd Cannavec-Science-Plugin

# That's it. No `pip install`. Stdlib only.

# Smoke test:
python3 -m unittest discover -s tests   # 1,501 tests, ~2-3 s
python3 evals/run_evals.py              # 173 offline canonical evals (188 total; 15 live skipped offline)

# The four golden v0.1 flows:
python3 -m cannavec_science answer "What is the evidence for CBD in Dravet syndrome?"
python3 -m cannavec_science discover "CBD PTSD" --since 2024-01-01
python3 -m cannavec_science verify 28538134
python3 -m cannavec_science rigor "this cultivar tests at 22% THC by HPLC and the dose was 10 mg"

# v0.2 elite-tier flows:
python3 -m cannavec_science answer "CBD evidence in Dravet syndrome" \
    --pico --power-calc --grade-profile --protocol-skeleton
python3 -m cannavec_science answer "Can I study Δ⁹-THC in rats?" \
    --regulatory-feasibility us
python3 -m cannavec_science discover "CB2 microglia" --sources biorxiv,medrxiv --max 5
python3 -m cannavec_science verify 28538134                     # auto-adds citation_network block
python3 -m cannavec_science freshness --registry interactions   # offline retraction-watch probe
python3 -m cannavec_science rigor "myrcene potentiates THC sedation"   # entourage-overclaim detector

# v0.3 routing-and-surfacing flows:
python3 -m cannavec_science answer "Δ⁸-THC pharmacology and safety"  # no Δ⁹-THC monograph
python3 -m cannavec_science answer "HHC safety profile"              # 0 spurious CBD/THC AE claims
python3 -m cannavec_science answer "entourage effect evidence"       # highest grade: Unsupported
python3 -m cannavec_science answer "cannabis interaction with tacrolimus"  # CBD-tacrolimus row fires
python3 -m cannavec_science answer "anandamide FAAH inhibition"      # eCBome reference surfaces
python3 -m cannavec_science verify NCT02224560                       # ClinicalTrials.gov resolver
python3 -m cannavec_science verify CHEMBL5803                        # ChEMBL compound resolver
python3 -m cannavec_science verify P21554                            # UniProt CB1 resolver
python3 -m cannavec_science registries                               # full registry inventory
python3 -m cannavec_science source-health --json                     # no-AttributeError + JSON

# v0.4 industry-expert-depth flows:
python3 -m cannavec_science answer "Decarboxylation kinetics of THCA at 110 degrees C"  # Veress 1990 + Wang 2016
python3 -m cannavec_science answer "HPLC vs GC-MS cannabinoid quantitation"             # GC in-injector artefact row
python3 -m cannavec_science answer "Type II chemovar genetic basis"                     # Hazekamp & Fischedick 2012
python3 -m cannavec_science answer "Cannabis vapor pyrolysis byproducts"                # Pomahacova 2009
python3 -m cannavec_science answer "UV-B effect on cannabinoid biosynthesis"            # Lydon 1987
python3 -m cannavec_science answer "THCA synthase CBDA synthase chemotype inheritance"  # de Meijer 2003
python3 -m cannavec_science answer "Is Cannabis sativa one species or three?"           # honest taxonomy debate
python3 -m cannavec_science answer "Bedrocan medical cannabis cultivars THC content"    # rendered audience hint
python3 -m cannavec_science answer "indica vs sativa pharmacological differences"       # strengthened refusal
python3 -m cannavec_science registries --registry analytical_chemistry                  # 8 analytical rows
python3 -m cannavec_science registries --registry cultivation_science                   # 6 cultivation rows

# v0.5 industry-expert-clinical-depth flows:
python3 -m cannavec_science answer "THC inhaled vs oral pharmacokinetics Tmax Cmax"                # Huestis 2005 + Wall 1983
python3 -m cannavec_science answer "CBD epidiolex food effect AUC fivefold high fat meal"          # Birnbaum 2019
python3 -m cannavec_science answer "11-hydroxy-THC active metabolite oral dronabinol"              # first-pass effect
python3 -m cannavec_science answer "cannabis use disorder DSM-5 criteria framework"                # Hasin 2013
python3 -m cannavec_science answer "CUDIT-R cannabis use disorder identification test"             # Adamson 2010
python3 -m cannavec_science answer "cannabis withdrawal syndrome scale Allsop 2011"                # CWS 19-item
python3 -m cannavec_science answer "cannabinoid hyperemesis syndrome diagnostic criteria"          # Sorensen 2017 SR
python3 -m cannavec_science answer "capsaicin cream cannabinoid hyperemesis treatment"             # Dezieck 2017
python3 -m cannavec_science answer "PF-04457845 FAAH inhibitor cannabis withdrawal NEJM"           # D'Souza 2019
python3 -m cannavec_science answer "BIA 10-2474 Rennes Phase 1 disaster"                           # off-target disambiguation
python3 -m cannavec_science answer "MAGL inhibitor ABX-1431 lorcaserin"                            # Cisar 2018
python3 -m cannavec_science answer "olivetolic acid synthase polyketide pathway biosynthesis"      # Taura 2009 OLS+OAC
python3 -m cannavec_science answer "Luo 2019 yeast cannabinoid heterologous expression Nature"     # synbio platform
python3 -m cannavec_science answer "THCA synthase enzymology FAD-dependent oxidocyclase"           # Sirikantaramas 2004
python3 -m cannavec_science discover "nabiximols European approval" --include-europepmc            # twelfth live lane
python3 -m cannavec_science registries --registry pharmacokinetics                                 # 8 PK rows
python3 -m cannavec_science registries --registry use_disorder                                     # 6 CUD/CWS rows
python3 -m cannavec_science registries --registry hyperemesis_syndrome                             # 4 CHS rows
python3 -m cannavec_science registries --registry ecbome_inhibitors                                # 5 eCBome-inhibitor rows
python3 -m cannavec_science registries --registry biosynthesis                                     # 5 biosynthesis rows
```

## The five commands

| Command | What it does |
|---|---|
| `/cannavec-science:research <question>` | Full researcher brief — GRADE-graded claims, primary citations, monograph sections, evidence synthesis, rigor pass. v0.2 adds opt-in `--pico --power-calc --grade-profile --protocol-skeleton --regulatory-feasibility` flags. |
| `/cannavec-science:ask <question>` | Fast Q&A — same composer, slimmer rendering. |
| `/cannavec-science:discover <query>` | Live multi-source fan-out across eleven primary sources (PubMed + ChEMBL + CT.gov + PubChem + PharmGKB + RCSB + Open Targets + GWAS + BindingDB + v0.2 bioRxiv + v0.2 medRxiv) with cross-source synthesis verdict. |
| `/cannavec-science:verify <PMID\|DOI>` | Single-identifier spot-check with retraction status. v0.2 auto-fetches forward-citation network + field-pushback signal. |
| `/cannavec-science:rigor <text>` | Run the seven phytochemistry rigor detectors (incl. v0.2 entourage-overclaim) + banned-pattern detector on arbitrary text. |

## The research agents

Three subagents wrap the deterministic backbone. None of them grades,
refuses, or cites in prose — every verdict is computed by
`cannavec_science/` and relayed verbatim.

| Agent | Role |
|---|---|
| `cannabis-research-lead` | Front-door orchestrator (a.k.a. CANNA-RESEARCH-AGENT). Decomposes a research objective into a deterministic execution blueprint — route → `answer` → `discover` → `rigor`/review → `verify` → bibliography — and relays the backbone's verdicts. Carries an explicit honesty disclaimer: the "research team" is sequenced subcommands plus two delegate subagents, **not** an autonomous swarm (Constitution §II). Emits a "curation candidates" block that feeds the human-approved §IX KB-growth flow; it never promotes rows itself. |
| `cannabis-source-hunter` | Live primary-literature discovery across the 13 lanes. Wraps `discover`; never auto-promotes `live_*` rows (Constitution §IX). |
| `cannabis-research-reviewer` | Final review pass — the Verity Test + the deterministic `rigor` pass + GRADE wording consistency. Returns PASS / REVISE. |

## The deterministic backbone

```
cannavec_science/                       # 68 modules · stdlib-only

# Core evidence + safety
├── evidence.py                  # GRADE, Source, Claim, ClaimType, source-authority weight
├── banned_patterns.py           # 16 patterns + 30-char negation guard
├── safety.py                    # Refuse-harmful / refuse-individualized / proceed verdict
├── rigor_checks.py              # 7 phytochemistry detectors (incl. entourage-overclaim)
├── reporting_rigor.py           # 6 EQUATOR-network detectors (CONSORT / PRISMA / STROBE / ROB-2 / ROBINS-I / AMSTAR-2)
├── retraction.py                # Retraction registry + composition-time enforcement
├── uncertainty.py               # GRADE wording-vs-grade verb picker

# Identifier verification
├── pubmed_verify.py             # E-utilities + Crossref (stdlib urllib)
├── uniprot_verify.py            # UniProt accession resolver

# Live discovery (13 lanes)
├── pubmed_search.py             # PubMed E-utilities search
├── chembl_discover.py           # ChEMBL bioactivity
├── ctgov_discover.py            # ClinicalTrials.gov
├── pubchem_discover.py          # PubChem compound structure
├── pharmgkb_discover.py         # PharmGKB pharmacogenomics
├── rcsb_discover.py             # RCSB PDB structural biology
├── opentargets_discover.py      # Open Targets gene-disease evidence
├── gwas_discover.py             # GWAS Catalog SNP-trait associations
├── bindingdb_discover.py        # BindingDB measured binding affinities
├── biorxiv_discover.py          # bioRxiv preprints
├── medrxiv_discover.py          # medRxiv preprints
├── europepmc_discover.py        # Europe PMC (PubMed + PMC full-text + EU journals)
├── openalex_discover.py         # OpenAlex open scholarly citation graph
├── _preprint_helpers.py         # Shared DOI/version/Crossref helpers
├── discover_guard.py            # Safety + banned-pattern preflight on live queries
├── synthesis.py                 # Cross-source convergence verdict
├── source_health.py             # Per-source liveness probe

# Composition + export
├── intent.py                    # Intent classifier
├── answer.py                    # Typed Answer + compose_answer + scaffolder threading
├── evidence_synthesis.py        # Deterministic claim-set rollup
├── contradiction.py             # Pairwise claim contradiction detector
├── citation_network.py          # NCBI elink forward-cite + pushback signal
├── freshness.py                 # Registry watch_pmids probe
├── bibliography.py              # BibTeX / RIS / CSL-JSON exporter (inline GRADE)
├── registries.py                # Registry inventory subcommand surface

# Researcher-workflow scaffolders
├── pico.py                      # PICO frame composer
├── power_calc.py                # Stdlib sample-size estimator (Cohen + Fleiss)
├── grade_profile.py             # GRADE evidence-profile table (MD + CSV)
├── protocol_skeleton.py         # 9-section IRB protocol stub
├── regulatory_feasibility.py    # US-federal / EU-EMA / Canada / UK advisory

# Quantitative evidence synthesis
├── meta_analysis.py             # Fixed + DL random effects, Q/I²/τ², Egger, leave-one-out, prediction interval, subgroup, trim-and-fill
├── absolute_effects.py          # Relative→absolute (GRADE SoF): risk difference + NNTB/NNTH (Altman 1998 null-crossing CI)

# Curated science registries (20)
├── major_cannabinoids.py        # Δ⁹-THC, CBD, THCA, CBDA
├── minor_cannabinoids.py        # THCV, CBDV, CBC, CBN, CBG, Δ⁸-THC, HHC, THCO, THCP
├── terpenes.py                  # Terpene registry
├── terpene_reference.py         # Terpene analytical chemistry
├── interactions.py              # Drug-interaction registry
├── adverse_events.py            # AE registry
├── populations.py               # Trial-supported populations
├── contraindications.py         # Contraindication registry
├── pharmacogenomics.py          # CYP2C9 / CYP3A4 / CYP2C19 PGx
├── ecbome.py                    # Endocannabinoidome reference
├── ecbome_inhibitors.py         # FAAH / MAGL drug-development pharmacology
├── analytical_chemistry.py      # Decarb kinetics, HPLC/GC-MS, chemovar, pyrolysis
├── cultivation_science.py       # UV-B, trichome, synthase genetics, taxonomy
├── biosynthesis.py              # OLS/OAC → CBGAS → THCA/CBDA synthase pathway
├── pharmacokinetics.py          # THC inhaled/oral PK, CBD food effect, 11-OH-THC
├── use_disorder.py              # DSM-5 CUD, CUDIT-R, CWS, NESARC-III
├── hyperemesis_syndrome.py      # CHS diagnostic criteria, Rome IV, capsaicin
├── pain_medicine.py             # NASEM 2017 chronic pain + Whiting / Stockings / Mücke / Boehnke
├── psychiatry.py                # Di Forti EU-GEI, Marconi, Vaucher MR, Hjorthøj
├── driving_impairment.py        # Compton NHTSA, Hartman, Marcotte, Brubacher
├── ptsd_anxiety_sleep.py        # Bonn-Miller 2021, Crippa/Bergamaschi CBD-SAD, Walsh sleep SR

# Internal helpers
├── _normalize.py                # Text normalization
├── _markdown_skip.py            # Markdown-aware tokenization
├── __init__.py
└── __main__.py                  # CLI: python3 -m cannavec_science <subcommand>
```

## Tests + acceptance gate

```bash
python3 -m unittest discover -s tests   # 1,501 tests, offline, ~2-3 s
python3 evals/run_evals.py              # 173 offline canonical evals (188 total; 15 live skipped offline)
```

Before any push to a release branch, all of the following MUST hold
(per [`specs/002-elite-development/plan.md`](specs/002-elite-development/plan.md)
and the per-spec gates in `specs/004` → `specs/006`):

- `python3 -m unittest discover -s tests` exits 0 in ≤ 60 seconds.
- Total test count ≥ 1,500.
- `python3 evals/run_evals.py` exits 0 with ≥ 170 offline prompts
  across the nine current buckets, each at or above its minimum.
- `python3 -m cannavec_science answer "CBD Dravet syndrome" --pico --power-calc --grade-profile --protocol-skeleton`
  returns one composed answer with all four scaffolds present.
- `python3 -m cannavec_science discover "CB2 microglia" --sources biorxiv,medrxiv --max 5`
  returns preprint rows tagged `live_biorxiv` / `live_medrxiv` with Level D cap.
- `python3 -m cannavec_science verify 28538134` returns the
  Devinsky-2017 record with `retraction_status: clean` plus a
  citation-network block (or `--no-citation-network` to suppress).
- `python3 -m cannavec_science freshness --registry interactions`
  returns a per-row status table without mutating registry rows.
- `python3 -m cannavec_science rigor "myrcene potentiates THC's sedative effect"`
  fires both `isomer_collapse` AND the new `entourage_overclaim` detector.
- The total slash-command count remains exactly **five**.
- Total Python LOC under `cannavec_science/` stays under **25,000**.

## Constitutional principles

This MVP is governed by 11 principles
([`.specify/memory/constitution.md`](.specify/memory/constitution.md)):

1. **Primary-source or refuse.**
2. **Deterministic backbone over prose.**
3. **Test-first (non-negotiable).**
4. **Researcher audience only (MVP scope lock).**
5. **Safety-layer sovereignty.**
6. **Phytochemistry precision is non-negotiable.**
7. **GRADE honesty over confidence-laundering.**
8. **Retractions are enforced at composition, not post-hoc.**
9. **Read-time discovery is as important as write-time checking.**
10. **Stdlib-only until proven insufficient.**
11. **Citable output is the default.**

The full text lives in `.specify/memory/constitution.md`. Amendments
require the same spec → plan → tasks → implement workflow as a feature.

## License

MIT. See [`LICENSE`](LICENSE).
