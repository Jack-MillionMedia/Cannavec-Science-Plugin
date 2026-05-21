---
name: cannabis-research-rigor
description: Five Pillars of Verity for cannabis content. Auto-activate when the user is researching, writing about, citing, or summarizing cannabis, cannabinoids, terpenes, endocannabinoid system, or cannabis-derived medicinal products (CBPMs) — and especially when claims involve dose, mechanism, efficacy, safety, drug interactions, regulatory status, or market data. Loads the Verity Test, the Five Pillars (Methodology, Phytochemistry, Pharmacology, Data Integrity, Objectivity), and the banned-pattern list.
version: 1.0.0
---

# Cannabis Research Rigor — The Five Pillars of Verity

When you are about to make any cannabis-related claim, this skill applies. It is the operational standard for Cannavec and should govern any output you produce on cannabis topics, regardless of whether you are operating inside the truth layer's pipeline or just answering a one-off question.

## The Verity Test (gating predicate)

Before emitting any cannabis claim, the claim must pass these five questions. Even one "no" invalidates it.

1. **Empirical** — Does the claim trace to a primary observation (experiment, dataset, instrument readout, regulatory record)?
2. **Reproducible** — Could a stranger, given only the cited sources, reach the same conclusion?
3. **Quantified** — Are magnitudes, ranges, uncertainties, sample sizes, units explicit?
4. **Scope-bounded** — Are population, jurisdiction, dose, route, chemotype, time period stated?
5. **Disclosure-complete** — Are funding, COI, replication status, dissent surfaced?

## The Five Pillars (one-line standards)

| Pillar | Standard |
|---|---|
| **I — Methodological & Analytical Rigor** | Every claim has methodology behind it, replication weight against it, and quantified effect size with sample, comparator, and CI. |
| **II — Botanical & Phytochemical Precision** | Every cannabinoid is named by isomer; every chemotype claim has chromatographic backing; every cultivar mention carries verification or hedging. |
| **III — Pharmacological & Clinical Accuracy** | Every mechanism cites the receptor with UniProt ID and binding affinity with assay context; every dose claim carries route and bioavailability. |
| **IV — Data Architecture & Integrity** | Every artefact is structured YAML; every audit entry append-only; every quantitative claim traceable to a byte-level skill response archive. |
| **V — Objectivity & Governance** | Every source is intake-equal regardless of KB alignment; every COI disclosed; every banned framing rejected; every dissent recorded. |

## Pillar I — Methodology operational rules

1. Hierarchy of evidence is non-negotiable. Match wording strictly to GRADE level.
2. Single primary study caps a claim at Level C unless pre-registered, adequately powered RCT in major journal (then Level B max). Level A requires Cochrane/AHRQ/NICE systematic review OR ≥ 2 independent high-quality RCTs in alignment.
3. Every effect-direction claim ("reduces X") carries effect size, 95% CI, sample size, comparator. Missing fields = explicit omission + downgrade.
4. Distinguish pre-specified primary outcomes from post-hoc / exploratory subgroup. Exploratory carries one-grade penalty until replicated.
5. Read the Methods section before citing a finding. Abstract-only citations carry `methods_unverified: true` and cap at Level C.
6. Traceability: every claim resolves through `chunk → Paper Record → DOI/PMID → primary URL`. Missing any link voids the claim.
7. n < 20 = hypothesis-generating only. n < 100 cannot support population-level claims. n ≥ 1,000 or registry data required for prevalence claims.
8. Standardize: SI units; doses as mg, mg/kg, %THC w/w, mg CBD/ml; concentrations molar (M, mM, μM, nM) for pharmacology. Never "low/moderate/high" alone.

**Failure modes to catch:**
- Level inflation (Level C evidence written in Level A language)
- Confidence-laundering (confident claim citing weakly-powered study)
- Citation by association (review article cited as if it were primary)
- Wishful precision (false decimal precision beyond source measurement)

## Pillar II — Phytochemistry operational rules

1. Reject marketing taxonomy. "Indica," "sativa," "hybrid" are not biochemical categories. Survive only as historical/colloquial when source uses them.
2. Chemotype-first. Type I (THC-dominant), Type II (mixed), Type III (CBD-dominant), Type IV (CBG-dominant), Type V (cannabinoid-free) per Hillig/Mahlberg/de Meijer.
3. Cultivar identity is unstable. Cultivar claims cite chromatographic verification or hedge.
4. Phytochemical specificity. Δ⁹-THC, Δ⁸-THC, THCA, CBD, CBDA, CBG, CBGA, CBN, CBC, THCV, CBDV. Never collapse. "THC" alone is rejected for any pharmacology claim.
5. Acid vs neutral. THCA ≠ Δ⁹-THC. CBDA ≠ CBD. Decarboxylation status changes pharmacology, route relevance, legal status.
6. Chromatographic provenance. %THC, terpene ratios, residual solvents need HPLC, GC-MS, GC-FID, or LC-MS/MS with calibration standard and LOD.
7. Genotype vs phenotype. Phenotypic claims state cultivation conditions.
8. Taxonomy: *Cannabis sativa* L. (Linnaeus 1753).
9. Cultivation claims state environment (indoor/greenhouse/outdoor; soil/hydro/aero; latitude/photoperiod; climate zone).
10. Enzymatic precision. Cite enzyme, substrate, product, catalytic step.

## Pillar III — Pharmacology operational rules

1. Mechanism before clinic. Clinical claims that assert a mechanism cite receptor/enzyme/pathway with primary structural or binding evidence (BindingDB, ChEMBL, UniProt, Reactome).
2. Receptor specificity. Name CB1 (P21554), CB2 (P34972), GPR55 (Q9Y2T6), GPR119 (Q8TDV5), TRPV1 (Q8NER1), PPARγ (P37231), 5-HT1A (P08908). Affinity as Ki, IC50, EC50, % efficacy with assay context.
3. **Δ⁹-THC is a *partial* agonist at CB1 and CB2.** Not "an agonist" plain. CBD's CB1/CB2 activity is negligible at physiological concentrations.
4. Bioavailability mandatory. Any administered-dose / onset / duration / effect-magnitude claim states route + bioavailability range. Oral THC ~6–20%; inhaled THC ~10–35%; sublingual CBD ~13–19%.
5. PK completeness. Tmax, Cmax, t½, V_d, elimination route. THC: t½ biphasic ~30 min → 25–36 h. CBD: t½ ~18–32 h chronic. Note 11-OH-THC (active metabolite) for oral THC.
6. Drug metabolism explicit. CYP2C9 (THC), CYP2C19+CYP3A4 (CBD), etc., with PharmGKB or primary evidence. DDI claims state substrate, modifier, magnitude (Cmax/AUC ratio).
7. Efficacy ≠ effectiveness ≠ tolerability. Don't collapse.
8. Toxicology floor. AE reporting accompanies efficacy claims. CHS, cardiovascular (tachycardia, OH), cognitive (especially adolescent), DDIs, dependence — not omitted.
9. Synergy ("entourage effect") is open empirical hypothesis with mixed evidence. Requires direct co-administration data or controlled isolate-vs-full-spectrum trial. The v0.2 deterministic detector `detect_entourage_overclaim()` in `cannavec_science/rigor_checks.py` flags terpene-cannabinoid synergy claims missing a canonical citation (Russo 2011 PMID 21749363, Finlay 2020 PMID 32226370, Santiago 2019 PMID 30728672, LaVigne 2021 PMID 33888868) — discussion of the hypothesis as a research question does NOT fire.
10. Population specificity. Paediatric / geriatric / pregnancy / lactation named explicitly. Pregnancy: cannabinoids cross placenta; ACOG/RCOG/SOGC default to avoidance.

## Pillar IV — Data integrity operational rules

1. Every artefact is YAML-structured. Free-prose-only artefacts are rejected.
2. Every chunk carries the truth-layer metadata block (`freshness_class`, `decay_horizon_days`, `last_verified_at`, `last_verified_by`, `provenance_score`, `contradiction_status`, `claim_type`, `jurisdiction_lock`, `source_paper_ids`, `agent_review_state`, `risk_flag`).
3. Immutable provenance. Original source URL, DOI, PMID, retrieval timestamp, content hash recorded once at intake, never changed.
4. Granular over coarse. Safety-critical chunks are their own chunks.
5. Algorithmic determinism where possible. Link liveness, schema validation, retraction lookups, taxonomy compliance — deterministic checks.
6. Append-only audit. Every queue transition, Airtable write, retraction discovery logged. Edits forbidden.
7. Corrective transparency. Errors corrected via `type: retract` / `type: correct` patches citing the discovery source. Never silently overwritten.
8. Taxonomic compliance. Every chunk belongs to exactly one canonical taxonomy node.
9. High-fidelity quoting. Verbatim quotation with line/page reference. Paraphrases marked as such.
10. Longitudinal record. Every change is a new audit entry plus state_history extension. History is not deleted.

## Pillar V — Objectivity operational rules

1. Source-agnostic intake. Sources contrary to current consensus get same priority as concordant.
2. COI surfacing mandatory. Every cited paper's funding, declared COI, sponsor relationship captured.
3. Apolitical posture. Report legal status as fact, citing primary regulator documents. Editorial framing forbidden.
4. Jurisdictional neutrality. Treat UK / US / EU / DE / CA / etc. equivalently as primary-document sources.
5. Commercial neutrality. Brand / dispensary / SKU names appear only for verifiable facts (recall, approved formulation, named clinical trial).
6. Activist source identification. NORML, DPA, prohibitionist coalitions, industry trade groups are valid for policy positions, recorded as such — not for clinical/pharmacological/chemical claims.
7. Meritocratic weighting. Well-designed study from less-famous lab outranks poorly-designed study from famous lab.
8. Definitive language reserved for definitive evidence. "Established," "demonstrated," "proven" only when supported. "Suggests," "may," "preliminary" are precise — not weasel words.
9. Dissent documented, not erased. Credible dissent reported with attribution.
10. Transparent disagreement resolution. Disagreements between personas / agents / reviewers logged.

## Banned patterns (auto-rejection)

The truth layer rejects on detection any artefact containing:

1. **Indica/sativa as pharmacology** — "Sativa for energy, indica for sleep" is biochemically meaningless
2. **Cultivar-as-effect** — "OG Kush is for relaxation" requires chemotype + terpene data + clinical evidence
3. **Marketing-derived ratios** — 1:1, 4:1, 20:1 CBD:THC ratios as inherent therapeutic profile without dose-response evidence
4. **"Natural" as evidence** — Plant origin grants no safety / efficacy / interaction immunity
5. **"Cure" claims** — Cannabinoids cure no condition under current evidence
6. **Cherry-picked sample sizes** — Reporting only positive-result studies in mixed literature
7. **Mechanism-implies-clinic leaps** — "CB2 receptors on immune cells, therefore cannabis treats autoimmune disease" without bridging trial
8. **Affiliate / commercial endorsement** — Product recommendations beyond verifiable approvals or recalls
9. **Anecdote-as-evidence** — "Patients report" framings substituted for trial evidence
10. **Untestable claims** — "Strengthens immune system," "balances the body," "promotes wellness" without operational definition

## How to use this skill

When you load this skill, treat the Verity Test as the gating predicate for every cannabis claim. Treat the Five Pillars as the per-claim audit checklist. Treat the banned patterns as automatic-rejection triggers.

If you are about to write a cannabis claim:

1. Read the claim back to yourself
2. Apply the Verity Test
3. Apply the relevant Pillar(s) — at minimum I + II + III for any biological / chemical / clinical claim; IV for any structured artefact; V for every claim
4. Check the banned-pattern list
5. If anything fails, either fix the claim or downgrade / hedge / remove it

If you are unsure: hedge. Hedging is honest. Confidence without evidence is fraud.

## Reference IDs

See the `cannabis-target-reference` skill for UniProt and PubChem CIDs.
