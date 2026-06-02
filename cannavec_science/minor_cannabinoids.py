"""Minor-cannabinoid evidence registry.

Curated, citation-anchored evidence on the minor cannabinoids that the
v2.6 audit identified as systematically under-served: THCV, CBDV, CBC,
CBN, and CBG. Each entry separates:

- **Chemistry** — IUPAC / canonical structure note, distinguishing
  features vs Δ⁹-THC / CBD.
- **Receptor pharmacology** — CB1 / CB2 / TRP / 5-HT / PPAR receptor
  activity with assay concentrations and UniProt identifiers where
  primary sources support them. Graded ``pharmacology_grade``.
- **Human clinical evidence** — what has actually been measured in
  controlled human trials, with sample size, design, and outcome.
  Graded ``clinical_grade`` per the Cannavec evidence levels.
- **Preclinical evidence** — in-vitro / animal findings with the
  bridging-to-clinic caveat made explicit.
- **Regulatory + commercial status** — scheduling and commercial-
  product reality, including the "hemp-derived" gray-zone caveat
  where applicable.
- **Safety** — what is known and what is not known about adverse
  effects at consumer dose ranges.
- **Citations** — at least one primary PubMed-citation per claim
  category.

Design principles (mirror the interactions / AE / contraindications
registries):

- The registry is the *evidence*; surfaces do the *rendering*.
- Cannavec does not extrapolate from preclinical to clinical without
  bridging RCT evidence; entries name this gap explicitly.
- Clinical grade caps at C unless a Phase III RCT or systematic
  review of multiple RCTs exists for the specific compound + outcome
  + population. As of 2026-05, no minor cannabinoid has reached
  Level A clinical evidence for any indication.

This module is the substantive content fix for the v2.6 audit's
finding that the answer pipeline produced generic stubs when asked
about THCV / CBN / CBG / CBDV / CBC because no curated registry
held minor-cannabinoid specific evidence. ``cannavec.interactions``
already holds CYP / sedative interactions for CBN / CBG / THCV; this
module holds the broader pharmacology + clinical evidence picture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class MinorCannabinoidEvidenceClass(str, Enum):
    """Cannavec evidence levels, repeated here so this module does
    not require importing ``cannavec.evidence`` at use sites that
    only need the registry rendering."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    UNSUPPORTED = "Unsupported"


@dataclass(frozen=True)
class MinorCannabinoidCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: int | None = None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "pmid": self.pmid,
            "doi": self.doi,
            "url": self.url,
            "year": self.year,
        }


@dataclass(frozen=True)
class ReceptorActivity:
    """A single curated receptor-activity row for a minor cannabinoid."""

    target: str                   # "CB1", "CB2", "TRPV1", "5-HT1A", "PPARγ"
    uniprot: str | None           # e.g. "P21554" for CB1; None when target lacks a clean UniProt
    gene_symbol: str | None       # e.g. "CNR1" for CB1
    activity: str                 # "partial agonist", "neutral antagonist", "inverse agonist", "agonist"
    affinity_note: str            # "Ki ≈ 300 nM (assay-dependent)" — keeps the registry honest about variance
    assay: str                    # "competitive binding (rat brain membrane)"
    citations: tuple[MinorCannabinoidCitation, ...]
    # v2.7 in-vitro → clinic translation discipline (P2.13). When a
    # receptor row reports an in-vitro Ki, the registry should also
    # express what the predicted *clinical* receptor occupancy looks
    # like at a typical consumer/clinical exposure — so the user can't
    # mistake in-vitro mechanism for in-vivo effect. If predicted
    # occupancy is <10% the renderer surfaces a translation flag:
    # "in-vitro mechanism does not translate at typical clinical
    # exposure." Optional — legacy rows render unchanged.
    typical_clinical_exposure: str | None = None
    predicted_receptor_occupancy_at_typical_dose: str | None = None
    translation_caveat: str | None = None

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "uniprot": self.uniprot,
            "gene_symbol": self.gene_symbol,
            "activity": self.activity,
            "affinity_note": self.affinity_note,
            "assay": self.assay,
            "citations": [c.to_dict() for c in self.citations],
            "typical_clinical_exposure": self.typical_clinical_exposure,
            "predicted_receptor_occupancy_at_typical_dose":
                self.predicted_receptor_occupancy_at_typical_dose,
            "translation_caveat": self.translation_caveat,
        }


@dataclass(frozen=True)
class ClinicalEvidenceRow:
    """A single human-clinical-evidence row."""

    indication: str               # "appetite / weight loss", "schizophrenia (THC challenge)"
    design: str                   # "randomised double-blind crossover", "open-label", "Phase II"
    n: int                        # sample size
    dose_route: str               # "10 mg oral single dose"
    outcome: str                  # one-line outcome
    grade: MinorCannabinoidEvidenceClass
    citations: tuple[MinorCannabinoidCitation, ...]
    caveats: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "indication": self.indication,
            "design": self.design,
            "n": self.n,
            "dose_route": self.dose_route,
            "outcome": self.outcome,
            "grade": self.grade.value,
            "citations": [c.to_dict() for c in self.citations],
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class PreclinicalEvidenceRow:
    """An animal / in-vitro evidence row, marked with the bridging caveat."""

    indication_or_model: str      # "DIO mouse weight loss model", "Aβ-induced neuroinflammation in vitro"
    species_or_assay: str         # "C57BL/6 DIO mice", "HEK293 cells"
    dose_or_concentration: str    # "12.5 mg/kg/day p.o. for 30 days"
    outcome: str
    bridging_to_clinic: str       # WHY this does or does not bridge to humans
    grade: MinorCannabinoidEvidenceClass
    citations: tuple[MinorCannabinoidCitation, ...]

    def to_dict(self) -> dict:
        return {
            "indication_or_model": self.indication_or_model,
            "species_or_assay": self.species_or_assay,
            "dose_or_concentration": self.dose_or_concentration,
            "outcome": self.outcome,
            "bridging_to_clinic": self.bridging_to_clinic,
            "grade": self.grade.value,
            "citations": [c.to_dict() for c in self.citations],
        }


@dataclass(frozen=True)
class MinorCannabinoid:
    """A single curated minor-cannabinoid record."""

    name: str                              # canonical name, e.g. "THCV"
    long_name: str                         # "tetrahydrocannabivarin"
    aliases: tuple[str, ...]               # ("Δ⁹-THCV", "delta-9 tetrahydrocannabivarin")
    chemistry_note: str                    # one-paragraph chemistry summary
    receptor_activity: tuple[ReceptorActivity, ...]
    pharmacology_grade: MinorCannabinoidEvidenceClass
    clinical_evidence: tuple[ClinicalEvidenceRow, ...]
    clinical_grade: MinorCannabinoidEvidenceClass
    preclinical_evidence: tuple[PreclinicalEvidenceRow, ...]
    regulatory_status: str                 # multi-line text describing scheduling
    commercial_reality: str                # what the consumer market looks like (variability, mislabelling, etc.)
    safety_note: str                       # cannabinoid-specific safety picture
    pharmacokinetics_note: str             # route + bioavailability + half-life summary
    key_uncertainties: tuple[str, ...]     # honest knowledge gaps
    common_misconceptions: tuple[str, ...] # marketing-vs-evidence claims to refuse
    citations: tuple[MinorCannabinoidCitation, ...]  # cross-cutting citations not pinned to a row

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "long_name": self.long_name,
            "aliases": list(self.aliases),
            "chemistry_note": self.chemistry_note,
            "receptor_activity": [r.to_dict() for r in self.receptor_activity],
            "pharmacology_grade": self.pharmacology_grade.value,
            "clinical_evidence": [c.to_dict() for c in self.clinical_evidence],
            "clinical_grade": self.clinical_grade.value,
            "preclinical_evidence": [p.to_dict() for p in self.preclinical_evidence],
            "regulatory_status": self.regulatory_status,
            "commercial_reality": self.commercial_reality,
            "safety_note": self.safety_note,
            "pharmacokinetics_note": self.pharmacokinetics_note,
            "key_uncertainties": list(self.key_uncertainties),
            "common_misconceptions": list(self.common_misconceptions),
            "citations": [c.to_dict() for c in self.citations],
        }


# Re-used citation rows so the registry stays normalised.
_PERTWEE_2008 = MinorCannabinoidCitation(
    label="Pertwee RG, Br J Pharmacol 2008, ligand-binding profile of phytocannabinoids",
    pmid="17828291", year=2008,
)
_THOMAS_2005 = MinorCannabinoidCitation(
    label="Thomas A et al., Br J Pharmacol 2005, THCV CB1 antagonism in vitro and in vivo",
    pmid="16205722", year=2005,
)
_RIEDEL_2009 = MinorCannabinoidCitation(
    label="Riedel G et al., Br J Pharmacol 2009, THCV reduces food intake in mice",
    pmid="19378378", year=2009,
)
_JADOON_2016 = MinorCannabinoidCitation(
    label="Jadoon KA et al., Diabetes Care 2016, THCV in type 2 diabetes",
    pmid="27573936", year=2016,
)
_ENGLUND_2016 = MinorCannabinoidCitation(
    label="Englund A et al., J Psychopharmacol 2016, THCV attenuates THC subjective effects",
    pmid="26577065", year=2016,
)
_HILL_2012 = MinorCannabinoidCitation(
    label="Hill AJ et al., Br J Pharmacol 2012, CBDV anticonvulsant in vivo",
    pmid="22970845", year=2012,
)
_HILL_2013 = MinorCannabinoidCitation(
    label="Hill AJ et al., Br J Pharmacol 2013, CBDV mechanism review",
    pmid="23902406", year=2013,
)
_DEVINSKY_CBDV_2018 = MinorCannabinoidCitation(
    label="Brodie MJ et al., Cannabis Cannabinoid Res 2021, Phase 2 RCT of "
          "cannabidivarin (GWP42006) add-on therapy in adults with "
          "inadequately-controlled focal seizures (negative primary endpoint)",
    pmid="33998885", year=2021,
)
_DESPRES_2013 = MinorCannabinoidCitation(
    label="Borrelli F et al., Biochem Pharmacol 2013, CBC anti-inflammatory in colitis model",
    pmid="23373571", year=2012,
)
_RUSSO_2018 = MinorCannabinoidCitation(
    label="Russo EB, Front Plant Sci 2018, minor-cannabinoid pharmacology synthesis",
    pmid="30815017", year=2019,
)
_KARNIOL_1975 = MinorCannabinoidCitation(
    label="Karniol IG et al., Pharmacology 1975, CBN sedation observations (historical, low-quality)",
    pmid="1221432", year=1975,
)
# NOTE (v2.7): the Linck 2024 Sci Rep CBN-sleep crossover reference
# was previously shipped here with a `pending PubMed verification`
# label and a PubMed search-URL anchor. The 2026-05-19 Oracle Evaluator
# audit (§4.4) flagged it as violating the README promise that every
# claim cites a primary source (PMID / DOI / regulator URL). The entry
# is intentionally NOT exported as a public citation until
# `cannavec.pubmed_verify` confirms the PMID against live PubMed. The
# downstream `_CBN` clinical-evidence row is re-anchored to verified
# anchors (Russo 2018 + Karniol 1975) and its prose is updated to
# describe the emerging crossover-trial finding without naming an
# unverified specific reference. The CI gate
# `tests/test_registry_citations_verified.py` fails on any future
# `pending verification` / search-URL re-introduction.
_STOUT_2014 = MinorCannabinoidCitation(
    label="Stout SM & Cimino NM, Drug Metab Rev 2014, cannabinoid PK and drug interactions",
    pmid="24160757", year=2014,
)
_NAVARRO_2018 = MinorCannabinoidCitation(
    label="Navarro G et al., Biochem Pharmacol 2018, CBG selective α2-adrenoceptor agonism",
    pmid="29977202", year=2018,
)
_BORRELLI_2013 = MinorCannabinoidCitation(
    label="Borrelli F et al., Biochem Pharmacol 2013, CBG anti-inflammatory in IBD model",
    pmid="23415610", year=2013,
)
_VALDEOLIVAS_2015 = MinorCannabinoidCitation(
    label="Valdeolivas S et al., Neurotherapeutics 2015, CBG neuroprotection in HD model",
    pmid="25252936", year=2015,
)
_DEMEIJER_2003 = MinorCannabinoidCitation(
    label="de Meijer EPM et al., Genetics 2003, cannabinoid biosynthesis in Cannabis sativa",
    pmid="12586720", year=2003,
)


_REGISTRY: tuple[MinorCannabinoid, ...] = (

    # ── THCV ──────────────────────────────────────────────────────────
    MinorCannabinoid(
        name="THCV",
        long_name="tetrahydrocannabivarin",
        aliases=("Δ⁹-THCV", "delta-9-tetrahydrocannabivarin", "Δ9-THCV"),
        chemistry_note=(
            "THCV is a C3-propyl side-chain homologue of Δ⁹-THC (Δ⁹-THC has "
            "a C5-pentyl side chain). The shortened side chain changes "
            "receptor pharmacology profoundly — dose-dependent shift from "
            "neutral CB1 antagonism (low dose) to partial CB1 agonism "
            "(high dose). Biosynthesised via the divarinic-acid branch of "
            "the cannabinoid pathway (CBGVA precursor)."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="neutral antagonist at low dose; partial agonist at high dose",
                affinity_note=(
                    "Ki ≈ 75 nM in rat brain membrane competitive binding "
                    "(Thomas 2005); functional response is dose-dependent — "
                    "antagonist behaviour dominates at ≤ 3 mg/kg in rodents."
                ),
                assay="[³H]-CP55,940 competitive binding; mouse vas deferens functional",
                citations=(_THOMAS_2005, _PERTWEE_2008),
            ),
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="partial agonist",
                affinity_note="Ki ≈ 60 nM in transfected cell lines (assay-dependent).",
                assay="[³H]-CP55,940 competitive binding in CB2-transfected cells",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="5-HT1A",
                uniprot="P08908",
                gene_symbol="HTR1A",
                activity="agonist (in vitro)",
                affinity_note=(
                    "Mechanistically implicated in the THCV antipsychotic-"
                    "leaning signal in animal models; concentration-response "
                    "not fully characterised in human assays."
                ),
                assay="cell-based 5-HT1A functional assays",
                citations=(_PERTWEE_2008,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.B,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="metabolic — type 2 diabetes glycaemic control",
                design="randomised double-blind placebo-controlled 13-week",
                n=62,
                dose_route="5 mg oral, twice daily",
                outcome=(
                    "THCV reduced fasting plasma glucose vs placebo "
                    "(adjusted mean difference −1.2 mmol/L, 95% CI "
                    "−2.4 to −0.1; p=0.04) and improved pancreatic beta-"
                    "cell function (HOMA-2 B). No change in body weight "
                    "or HDL/LDL profile."
                ),
                grade=MinorCannabinoidEvidenceClass.C,
                citations=(_JADOON_2016,),
                caveats=(
                    "Single-site UK trial; not yet replicated in an "
                    "independent population.",
                    "Effect size is modest; clinically meaningful in the "
                    "context of add-on therapy, not as monotherapy.",
                ),
            ),
            ClinicalEvidenceRow(
                indication="acute pharmacodynamic — modulation of THC effects",
                design="randomised double-blind placebo-controlled crossover",
                n=20,
                dose_route="10 mg oral THCV daily for 5 days, then 1 mg IV THC challenge",
                outcome=(
                    "THCV pretreatment attenuated the THC-induced delayed-"
                    "recall verbal-memory impairment and reduced the "
                    "subjective intensity of THC intoxication on a 100 mm "
                    "VAS. No effect on THC-induced psychotomimetic scores "
                    "in this small sample."
                ),
                grade=MinorCannabinoidEvidenceClass.C,
                citations=(_ENGLUND_2016,),
                caveats=(
                    "Small sample, single-site, healthy volunteers; not "
                    "evidence for any clinical THCV indication.",
                    "The IV THC challenge model is non-clinical — "
                    "consumer THC dose / route is different.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.C,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="diet-induced obesity (DIO) — food intake / body weight",
                species_or_assay="C57BL/6 mice, DIO model",
                dose_or_concentration="12.5 mg/kg/day i.p. for up to 30 days",
                outcome=(
                    "Reduced food intake and modest weight loss vs vehicle; "
                    "improved glucose tolerance. Effects partially "
                    "reproduced via low-dose CB1 antagonism mechanism."
                ),
                bridging_to_clinic=(
                    "Bridges weakly — the i.p. mouse dose is not "
                    "translatable to oral human exposure, and the Jadoon "
                    "2016 human trial did NOT reproduce weight loss "
                    "despite confirming the glycaemic signal. Human "
                    "anti-obesity claims from THCV marketing exceed the "
                    "evidence base."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_RIEDEL_2009,),
            ),
        ),
        regulatory_status=(
            "US federal — THCV is not separately scheduled by name. "
            "Plant-derived THCV from sub-0.3%-Δ⁹-THC hemp falls under the "
            "2018 Farm Bill's hemp definition; THCV from non-hemp cannabis "
            "inherits its parent material's Schedule I status under the "
            "Controlled Substances Act. Several US states (Texas, "
            "Tennessee, California under DCC interpretation) treat hemp-"
            "derived intoxicating or psychoactive cannabinoids more "
            "restrictively — verify the operative state's primary "
            "regulator document. THCV is not approved as a drug substance "
            "in any major jurisdiction. EU — falls under novel-food "
            "review per Regulation 2015/2283 when sold as a supplement."
        ),
        commercial_reality=(
            "Most marketed 'THCV' products are CBD-feedstock conversions "
            "rather than chemovar-purified plant extracts. Label-claim "
            "accuracy is highly variable; independent third-party testing "
            "frequently finds products under-labelled or contaminated with "
            "Δ⁹-THC isomers from the conversion chemistry. Cannavec does "
            "not endorse any commercial product and treats potency / "
            "purity claims as unverified absent a recent COA."
        ),
        safety_note=(
            "Human safety data are limited to the small trials cited "
            "(total n ≈ 80 across pre-marketing dose-finding and the "
            "two RCT-quality trials). No serious AE signal at studied "
            "doses (1–10 mg oral). Beyond studied doses, safety is "
            "unknown — extrapolation from Δ⁹-THC safety does not apply "
            "because THCV's receptor profile is qualitatively different. "
            "Drug-interaction profile inherits Δ⁹-THC's CYP picture "
            "by structural analogy but has not been characterised in "
            "dedicated human PK studies."
        ),
        pharmacokinetics_note=(
            "Oral bioavailability not formally characterised in "
            "published human PK studies; comparable to oral Δ⁹-THC by "
            "structural analogy (~6–10% range). Inhaled bioavailability "
            "by structural analogy ~25–35%. Half-life in the range of "
            "Δ⁹-THC but unconfirmed at adequately powered scale. Per-"
            "claim PK numbers should always be sourced to the specific "
            "study, not extrapolated."
        ),
        key_uncertainties=(
            "No Phase III RCT for any indication.",
            "Dose at which the CB1 functional profile flips from "
            "antagonism to agonism in humans is not established.",
            "Long-term safety unknown.",
            "Pharmacokinetics in humans poorly characterised.",
            "Conversion-derived THCV may carry uncharacterised reaction "
            "by-products not present in plant-derived THCV.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'THCV is the diet weed.' The Jadoon 2016 "
            "trial showed glycaemic improvement, NOT weight loss; "
            "weight-loss claims rest on mouse data that did not "
            "replicate in humans.",
            "MISCONCEPTION: 'THCV is non-psychoactive.' THCV is a CB1 "
            "partial agonist at higher doses and is *not* reliably non-"
            "psychoactive — the dose-dependent functional flip means "
            "subjective effects are dose-bracket dependent.",
            "MISCONCEPTION: 'Sativa strains high in THCV are more "
            "energising.' Indica/sativa is not a pharmacology axis; "
            "Cannavec rejects this as a banned pattern.",
        ),
        citations=(_PERTWEE_2008, _RUSSO_2018),
    ),

    # ── CBDV ──────────────────────────────────────────────────────────
    MinorCannabinoid(
        name="CBDV",
        long_name="cannabidivarin",
        aliases=("cannabidivarin", "CBD-V"),
        chemistry_note=(
            "CBDV is the C3-propyl side-chain homologue of CBD (CBD has "
            "a C5-pentyl side chain). It is non-psychoactive at typical "
            "exposures and shares CBD's broad multi-target profile."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="TRPV1",
                uniprot="Q8NER1",
                gene_symbol="TRPV1",
                activity="agonist (in vitro)",
                affinity_note="EC50 in the low-micromolar range in HEK293 assays.",
                assay="calcium-imaging in TRPV1-transfected HEK293",
                citations=(_HILL_2013,),
            ),
            ReceptorActivity(
                target="GPR55",
                uniprot="Q9Y2T6",
                gene_symbol="GPR55",
                activity="antagonist (mechanism contributory to anticonvulsant effect)",
                affinity_note="IC50 reported in low-micromolar range; assay-dependent.",
                assay="β-arrestin recruitment / ERK phosphorylation",
                citations=(_HILL_2013,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.C,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="adult focal epilepsy (adjunctive)",
                design="randomised double-blind placebo-controlled Phase II",
                n=162,
                dose_route="400 mg twice daily oral (up to 800 mg/day)",
                outcome=(
                    "CBDV did NOT meet its primary endpoint: median "
                    "monthly focal-seizure frequency change vs placebo "
                    "was not statistically significant. Trial reported "
                    "as negative; CBDV-as-anticonvulsant programme has "
                    "not advanced to Phase III for this indication."
                ),
                grade=MinorCannabinoidEvidenceClass.B,
                citations=(_DEVINSKY_CBDV_2018,),
                caveats=(
                    "A negative adequately-powered RCT IS evidence — the "
                    "finding that CBDV does not reduce adult focal "
                    "seizures at the studied dose is high-quality evidence "
                    "AGAINST that specific claim, not evidence that more "
                    "trials would succeed.",
                    "Preclinical seizure-model success (Hill 2012) did "
                    "not translate — a canonical example of why mechanism "
                    "→ clinic extrapolation requires bridging RCT data.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.B,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="seizure — pentylenetetrazole and electroshock models",
                species_or_assay="rats and mice",
                dose_or_concentration="50–200 mg/kg i.p. acute dosing",
                outcome=(
                    "Dose-dependent reduction in seizure severity and "
                    "incidence across multiple acute seizure models."
                ),
                bridging_to_clinic=(
                    "Bridges weakly — the human Phase II trial "
                    "(Devinsky 2018) failed to reproduce the preclinical "
                    "anticonvulsant signal in adult focal epilepsy. This "
                    "is the textbook 'mechanism does not equal clinic' "
                    "case study for cannabinoid programmes."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_HILL_2012,),
            ),
            PreclinicalEvidenceRow(
                indication_or_model="autism spectrum — Rett-like / fragile X mouse models",
                species_or_assay="MeCP2-null and Fmr1-KO mice",
                dose_or_concentration="varies across studies; i.p. dosing",
                outcome=(
                    "Reports of behavioural and electrophysiological "
                    "improvements; mechanism implicated GPR55 + TRPV1 "
                    "modulation."
                ),
                bridging_to_clinic=(
                    "Speculative for humans. Several open-label and "
                    "small-trial programmes are pre-registered but no "
                    "adequately powered RCT has reported. ASD "
                    "marketing claims for CBDV exceed the evidence base."
                ),
                grade=MinorCannabinoidEvidenceClass.E,
                citations=(_RUSSO_2018,),
            ),
        ),
        regulatory_status=(
            "US federal — CBDV is not separately scheduled; hemp-derived "
            "CBDV is permitted under the 2018 Farm Bill subject to the "
            "0.3% Δ⁹-THC threshold. No drug-approval status. EU — novel-"
            "food review applies."
        ),
        commercial_reality=(
            "Smaller commercial footprint than CBD; products are typically "
            "tinctures or isolate powders. Label accuracy varies and "
            "third-party testing is recommended."
        ),
        safety_note=(
            "Safety profile in the Phase II epilepsy trial was comparable "
            "to placebo; no serious AE signal at studied doses. Beyond "
            "studied doses, safety is unknown. Drug-interaction profile "
            "by structural analogy is comparable to CBD (CYP3A4 / CYP2C19 "
            "modulation) but has not been characterised in dedicated "
            "human PK studies."
        ),
        pharmacokinetics_note=(
            "Oral bioavailability comparable to CBD (~6–13% range, "
            "subject to formulation and food effect) by structural "
            "analogy; not formally characterised at scale. Half-life "
            "uncertain."
        ),
        key_uncertainties=(
            "Therapeutic indication not established for any condition.",
            "Phase II negative for adult focal epilepsy is a published "
            "result, not a knowledge gap — but other paediatric or "
            "syndrome-specific epilepsy populations have not been tested.",
            "Autism-spectrum claims rest on mechanism + animal data.",
            "Long-term human safety unknown.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'CBDV is the next CBD for epilepsy.' "
            "Devinsky 2018 Phase II was negative for adult focal "
            "epilepsy; CBDV has not been approved for any indication.",
            "MISCONCEPTION: 'CBDV treats autism.' No adequately powered "
            "RCT has demonstrated benefit for any ASD symptom domain.",
        ),
        citations=(_HILL_2013, _RUSSO_2018),
    ),

    # ── CBC ───────────────────────────────────────────────────────────
    MinorCannabinoid(
        name="CBC",
        long_name="cannabichromene",
        aliases=("cannabichromene",),
        chemistry_note=(
            "CBC is one of the four 'big' phytocannabinoids by historical "
            "biosynthesis volume (alongside Δ⁹-THC, CBD, CBG). Synthesised "
            "from CBGA via CBCA synthase. Largely non-psychoactive at "
            "typical exposures; CB1 affinity is low."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="agonist (in vitro)",
                affinity_note=(
                    "Ki in the high-nanomolar to low-micromolar range "
                    "across published binding assays; functional CB2 "
                    "activity at concentrations not typically reached by "
                    "inhaled exposure."
                ),
                assay="competitive binding in CB2-transfected cells",
                citations=(_RUSSO_2018,),
            ),
            ReceptorActivity(
                target="TRPA1",
                uniprot="O75762",
                gene_symbol="TRPA1",
                activity="agonist (in vitro)",
                affinity_note="One of the more potent phytocannabinoid TRPA1 activators in vitro.",
                assay="calcium-imaging in TRPA1-transfected HEK293",
                citations=(_RUSSO_2018,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.C,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="any (human clinical evidence base)",
                design="N/A — no published adequately-powered controlled human trial",
                n=0,
                dose_route="N/A",
                outcome=(
                    "There is no published Phase II or III RCT of "
                    "isolated CBC in any indication as of 2026-05. The "
                    "compound's clinical evidence base is effectively "
                    "absent at the level of dedicated trials. Anti-"
                    "inflammatory, anti-acne, and mood-related marketing "
                    "claims rest entirely on preclinical evidence."
                ),
                grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
                citations=(),
                caveats=(
                    "Cannavec records this as 'no admissible primary "
                    "clinical evidence' rather than 'preliminary' — "
                    "the absence is structural, not a small-sample "
                    "qualifier.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="inflammation — DNBS / TNBS colitis models",
                species_or_assay="mice",
                dose_or_concentration="5–10 mg/kg i.p.",
                outcome=(
                    "Reduced colon weight/length ratio, MPO activity, "
                    "and histological inflammation scores vs vehicle."
                ),
                bridging_to_clinic=(
                    "Speculative for humans. Animal IBD models are not "
                    "reliable predictors of human IBD outcomes for "
                    "cannabinoids; the CBD experience in Crohn's disease "
                    "showed exactly this gap. CBC-anti-inflammatory "
                    "marketing claims exceed the evidence base."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_DESPRES_2013, _RUSSO_2018),
            ),
        ),
        regulatory_status=(
            "US federal — CBC is not separately scheduled; hemp-derived "
            "CBC under the 2018 Farm Bill follows the parent material's "
            "Δ⁹-THC compliance threshold. No drug-approval status."
        ),
        commercial_reality=(
            "Marketed primarily as a minor-cannabinoid additive in "
            "full-spectrum CBD products and in cosmetics (e.g. acne "
            "products). Label-claim accuracy and standalone-CBC "
            "products are limited; assume label content is unverified "
            "absent a recent COA."
        ),
        safety_note=(
            "Human safety data are essentially absent. Preclinical "
            "safety has not raised serious flags but the data are "
            "limited. No human drug-interaction studies; structural "
            "analogy to other cannabinoids does not substitute for "
            "primary CYP characterisation."
        ),
        pharmacokinetics_note=(
            "Oral bioavailability not characterised in published human "
            "PK studies. PK numbers carried in marketing material are "
            "speculative — Cannavec treats them as unsupported."
        ),
        key_uncertainties=(
            "Entire clinical evidence base is absent.",
            "Preclinical mechanism rests on assays at concentrations "
            "not reached by typical exposure.",
            "PK in humans uncharacterised.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'CBC is a proven anti-inflammatory.' No "
            "human RCT supports this; rodent IBD-model data do not "
            "bridge to human IBD without RCT confirmation.",
            "MISCONCEPTION: 'CBC clears acne.' No adequately powered "
            "human dermatology trial has demonstrated this; in-vitro "
            "sebocyte data are mechanism, not clinic.",
        ),
        citations=(_RUSSO_2018,),
    ),

    # ── CBN ───────────────────────────────────────────────────────────
    MinorCannabinoid(
        name="CBN",
        long_name="cannabinol",
        aliases=("cannabinol",),
        chemistry_note=(
            "CBN is primarily a Δ⁹-THC oxidation product; it accumulates "
            "in aged / light-exposed / oxidatively-stressed cannabis "
            "material and is *not* a primary biosynthetic product of the "
            "live plant. Commercial CBN concentration in fresh cannabis "
            "flower is typically <0.5% w/w; aged or improperly cured "
            "material may reach 1–2%."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="partial agonist (weak)",
                affinity_note=(
                    "Ki ≈ 300–500 nM in competitive binding assays "
                    "(assay- and species-dependent); CB1 affinity is "
                    "substantially lower than Δ⁹-THC's, which is part "
                    "of why CBN is weakly psychoactive at high oral "
                    "doses but not at typical commercial product doses."
                ),
                assay="[³H]-CP55,940 competitive binding",
                citations=(_PERTWEE_2008,),
                typical_clinical_exposure=(
                    "5–50 mg oral consumer dose; first-pass metabolism "
                    "substantial; estimated peak plasma low single-"
                    "digit nM range"
                ),
                predicted_receptor_occupancy_at_typical_dose=(
                    "low — predicted plasma exposure is ≥100-fold "
                    "below the reported in-vitro Ki, so receptor "
                    "occupancy at typical commercial doses is well "
                    "below the level expected to produce sustained "
                    "CB1 effect"
                ),
                translation_caveat=(
                    "In-vitro CB1 binding does not predict sustained "
                    "in-vivo CB1 effect at typical commercial CBN "
                    "doses. The faint psychoactivity sometimes "
                    "reported on very high oral CBN exposure is "
                    "consistent with the affinity gradient, not with "
                    "a marketing claim of CBN-mediated 'sedation'."
                ),
            ),
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="partial agonist",
                affinity_note="Ki ≈ 100–300 nM (assay-dependent).",
                assay="[³H]-CP55,940 competitive binding in CB2-transfected cells",
                citations=(_PERTWEE_2008,),
                typical_clinical_exposure=(
                    "same 5–50 mg oral consumer-dose range as above"
                ),
                predicted_receptor_occupancy_at_typical_dose=(
                    "low — plasma exposure remains ≥10-fold below "
                    "reported Ki at typical doses"
                ),
                translation_caveat=(
                    "In-vitro CB2 partial-agonism does not translate "
                    "to a demonstrable in-vivo immunomodulatory effect "
                    "at consumer-relevant CBN doses."
                ),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.B,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="sleep — consumer-dose evidence base",
                design=(
                    "no adequately-powered blinded RCT at consumer-"
                    "relevant doses has been verified in this registry "
                    "as of v2.7; legacy unblinded observations only"
                ),
                n=0,
                dose_route="consumer products typically deliver 5–50 mg oral CBN per dose",
                outcome=(
                    "Cannavec's curated synthesis position: marketing "
                    "claims of CBN as a sleep aid outpace the human "
                    "evidence base. Legacy unblinded observations "
                    "(Karniol 1975) are methodologically too weak to "
                    "support consumer sleep-aid claims; the synthesis "
                    "by Russo 2018 (the canonical minor-cannabinoid "
                    "review) classes CBN sedation as a marketing-driven "
                    "claim rather than a controlled-trial finding. A "
                    "recent blinded crossover trial at consumer-relevant "
                    "doses has been reported in the literature but is "
                    "intentionally NOT cited here until Cannavec's "
                    "PubMed verifier confirms its identifiers — see "
                    "the v2.7 audit at audits/2026-05-19_ORACLE_"
                    "EVALUATOR_REVIEW_v2.md §4.4 for the policy."
                ),
                grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
                citations=(_RUSSO_2018, _KARNIOL_1975),
                caveats=(
                    "Single-night crossover designs (when they are "
                    "verified into this registry) cannot exclude a "
                    "longer-onset effect at chronic dosing, but the "
                    "burden of proof shifts to a positive RCT to "
                    "support sleep-aid claims.",
                    "Pre-2000 'CBN is sedating' literature is "
                    "methodologically too weak to anchor consumer "
                    "claims; Karniol 1975 used unblinded designs.",
                    "Cannavec does NOT ship citations whose PMID is "
                    "not verified against live PubMed — when a recent "
                    "negative-result crossover trial is verified, it "
                    "will be added here with its PMID and the grade "
                    "will be raised to Level C.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="sedation — locomotor activity in rodents",
                species_or_assay="mice and rats",
                dose_or_concentration="oral and i.p. dosing at mg/kg scale",
                outcome=(
                    "Mild reduction in locomotor activity at high doses; "
                    "effect was modest and inconsistent across labs."
                ),
                bridging_to_clinic=(
                    "Bridges weakly — preclinical doses do not translate "
                    "to typical commercial CBN exposure. The synthesis "
                    "position (Russo 2018) is that consumer-dose human "
                    "sedation has not been demonstrated in controlled "
                    "trials at the inclusion bar this registry uses."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_KARNIOL_1975,),
            ),
        ),
        regulatory_status=(
            "US federal — CBN is not separately scheduled; hemp-derived "
            "CBN under the 2018 Farm Bill follows the parent material's "
            "Δ⁹-THC compliance threshold. State-level treatment of "
            "'intoxicating' or 'psychoactive' hemp-derived cannabinoids "
            "varies — CBN is generally treated as non-intoxicating but a "
            "few state regimes catch it in broader 'hemp-derived "
            "cannabinoid' rules. Verify operative jurisdiction's primary "
            "regulator document. Not approved as a drug substance."
        ),
        commercial_reality=(
            "Marketed as a sleep aid in tinctures, gummies, and capsules — "
            "almost always co-formulated with other actives (THC, "
            "melatonin, terpenes, valerian, magnolia bark). The compound "
            "formulation prevents attributing observed effects to CBN "
            "specifically and complicates dose-finding for CBN per se. "
            "Stability of CBN in formulation is poor in light/heat — "
            "label-claim potency can drift over shelf life. Cannavec "
            "treats CBN sleep-aid marketing as a claim that exceeds the "
            "evidence base."
        ),
        safety_note=(
            "Human safety data at typical commercial doses (5–50 mg "
            "oral) are limited but no serious AE signal has emerged. "
            "Drug-interaction profile — see ``cannavec.interactions`` "
            "for the CBN ↔ CYP3A4 and CBN ↔ sedative-hypnotic rows. "
            "Driving impairment data are essentially absent; prudent "
            "default is to assume potential additive sedation with "
            "other sedatives until characterised."
        ),
        pharmacokinetics_note=(
            "Oral bioavailability not formally characterised at scale; "
            "first-pass metabolism is substantial. Inhaled exposure is "
            "the better-characterised route by analogy to other "
            "cannabinoids but absolute systemic doses from typical "
            "flower / vape use are in the low-mg range total."
        ),
        key_uncertainties=(
            "Sleep-aid mechanism in humans not established.",
            "Long-term safety unknown.",
            "PK in humans poorly characterised.",
            "Effect of co-formulated actives on attributed CBN benefit.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'CBN is the sedating cannabinoid.' "
            "Marketing claims outpace human evidence; recent blinded "
            "crossover studies at consumer doses have NOT shown a "
            "reliable sleep benefit.",
            "MISCONCEPTION: 'Old flower is sedating because of CBN.' "
            "Aged flower has higher CBN AND lower terpenes AND "
            "degraded Δ⁹-THC profile; attribution to CBN specifically "
            "is unsupported by controlled data.",
            "MISCONCEPTION: 'CBN is non-psychoactive.' CBN is a weak "
            "CB1 partial agonist; at high oral doses it can produce "
            "mild THC-like subjective effects.",
        ),
        citations=(_PERTWEE_2008, _STOUT_2014, _RUSSO_2018),
    ),

    # ── CBG ───────────────────────────────────────────────────────────
    MinorCannabinoid(
        name="CBG",
        long_name="cannabigerol",
        aliases=("cannabigerol",),
        chemistry_note=(
            "CBG is the decarboxylated form of CBGA, the central "
            "biosynthetic precursor for Δ⁹-THCA, CBDA, and CBCA. In "
            "fresh cannabis flower, CBG concentration is typically low "
            "(<1% w/w) because CBGA is rapidly converted into the "
            "downstream cannabinoid acids. Dedicated 'CBG-dominant' "
            "chemovars exist and can reach 5–15% CBG by selecting for "
            "non-functional CBDA / THCA / CBCA synthase variants."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="α2-adrenoceptor",
                uniprot="P08913",
                gene_symbol="ADRA2A",
                activity="selective agonist (in vitro)",
                affinity_note=(
                    "Selective α2 agonism is the most distinctive CBG "
                    "pharmacology — separates CBG from the rest of the "
                    "phytocannabinoid family."
                ),
                assay="competitive binding + functional cAMP",
                citations=(_NAVARRO_2018,),
            ),
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="weak partial agonist or neutral antagonist (assay-dependent)",
                affinity_note=(
                    "Low CB1 affinity (Ki in the micromolar range in some "
                    "assays); CBG is not reliably psychoactive at typical "
                    "exposures."
                ),
                assay="competitive binding",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="partial agonist",
                affinity_note="Modest CB2 affinity; assay-dependent.",
                assay="competitive binding in CB2-transfected cells",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="5-HT1A",
                uniprot="P08908",
                gene_symbol="HTR1A",
                activity="antagonist (in vitro)",
                affinity_note="Inverse to the CBD profile at this receptor; mechanism notable but clinical implications unproven.",
                assay="functional cAMP",
                citations=(_NAVARRO_2018,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.B,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="any (human clinical evidence base)",
                design="N/A — no published Phase II / III RCT for any indication",
                n=0,
                dose_route="N/A",
                outcome=(
                    "There is no published adequately-powered RCT of "
                    "isolated CBG for any indication as of 2026-05. "
                    "Several open-label pilots and case series exist; "
                    "they do not anchor clinical claims. Marketing "
                    "claims (anxiety, focus, IBD, neuroprotection) rest "
                    "on preclinical evidence."
                ),
                grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
                citations=(),
                caveats=(
                    "A growing pre-registered pipeline targets Huntington "
                    "disease and IBD; until those trials report, the "
                    "clinical evidence base remains absent.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="IBD — TNBS / DNBS murine colitis",
                species_or_assay="mice",
                dose_or_concentration="1–30 mg/kg i.p.",
                outcome=(
                    "Reduced colon weight/length ratio, MPO activity, "
                    "inflammatory cytokines; effects partly attributable "
                    "to TRPA1 + PPARγ + α2-adrenoceptor pathways."
                ),
                bridging_to_clinic=(
                    "Speculative for humans. The same mechanism-rich "
                    "preclinical IBD story for CBD did not produce "
                    "robust human IBD benefit; CBG should be assumed to "
                    "face the same translation gap until an RCT reports."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_BORRELLI_2013,),
            ),
            PreclinicalEvidenceRow(
                indication_or_model="neurodegeneration — R6/2 Huntington-disease mouse model",
                species_or_assay="R6/2 mice",
                dose_or_concentration="10 mg/kg i.p.",
                outcome=(
                    "Reduced striatal neurodegeneration markers, motor "
                    "improvement on rotarod; mechanism implicated "
                    "PPARγ + α2 adrenergic + anti-inflammatory pathways."
                ),
                bridging_to_clinic=(
                    "Speculative for humans. R6/2 is an aggressive "
                    "model that has produced many positive preclinical "
                    "signals that did not translate; the HD-RCT "
                    "pipeline must report before clinical claims are "
                    "admissible."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_VALDEOLIVAS_2015,),
            ),
            PreclinicalEvidenceRow(
                indication_or_model="biosynthesis — CBGA as the precursor of THCA / CBDA / CBCA",
                species_or_assay="Cannabis sativa biosynthesis (genetic / biochemical)",
                dose_or_concentration="N/A — biosynthesis description",
                outcome=(
                    "Confirmed enzymatic pathway: CBGA → THCA via "
                    "THCA synthase; CBGA → CBDA via CBDA synthase; "
                    "CBGA → CBCA via CBCA synthase."
                ),
                bridging_to_clinic=(
                    "Not clinical — listed here to anchor CBG's "
                    "biosynthetic centrality and to support chemotype "
                    "selection in cultivation and breeding."
                ),
                grade=MinorCannabinoidEvidenceClass.C,
                citations=(_DEMEIJER_2003,),
            ),
        ),
        regulatory_status=(
            "US federal — CBG is not separately scheduled; hemp-derived "
            "CBG under the 2018 Farm Bill follows the parent material's "
            "Δ⁹-THC compliance threshold. Not approved as a drug "
            "substance in any major jurisdiction. EU — novel-food review "
            "applies."
        ),
        commercial_reality=(
            "Dedicated CBG-dominant chemovars are increasingly available, "
            "enabling extractor recovery of >5% CBG products. Marketed as "
            "tinctures, isolates, and infused products with a strong "
            "wellness-focus marketing narrative. Label-claim accuracy "
            "varies; third-party testing recommended. Cannavec does not "
            "endorse any commercial product."
        ),
        safety_note=(
            "Human safety data at consumer doses are limited but no "
            "serious AE signal has emerged in open-label observations. "
            "Drug-interaction profile — see ``cannavec.interactions`` "
            "for the CBG ↔ CYP3A4 / CYP2C9 row (in-vitro inhibition "
            "documented; in-vivo magnitude unknown). Driving "
            "impairment data are essentially absent."
        ),
        pharmacokinetics_note=(
            "Oral bioavailability not characterised at scale in "
            "published human PK studies. Inhaled bioavailability by "
            "structural analogy to other neutral cannabinoids ~25–35%. "
            "Per-claim PK numbers should always be sourced to the "
            "specific study, not extrapolated from other cannabinoids."
        ),
        key_uncertainties=(
            "Entire clinical evidence base is absent.",
            "Effect of α2-adrenoceptor agonism on blood pressure / "
            "sedation at consumer doses not characterised.",
            "PK in humans poorly characterised.",
            "Long-term safety unknown.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'CBG is the mother cannabinoid that does "
            "everything.' Biosynthetic centrality does NOT imply "
            "pharmacological centrality — CBG's clinical evidence base "
            "is essentially absent.",
            "MISCONCEPTION: 'CBG cures IBD / Crohn's / glaucoma / "
            "cancer.' No human RCT supports any of these claims.",
            "MISCONCEPTION: 'CBG is the focus / energy cannabinoid.' "
            "No human study supports a focus/energy claim.",
        ),
        citations=(_PERTWEE_2008, _NAVARRO_2018, _RUSSO_2018),
    ),

    # ── Δ⁸-THC (spec 002 US6) ──────────────────────────────────────────
    MinorCannabinoid(
        name="Δ⁸-THC",
        long_name="delta-8-tetrahydrocannabinol",
        aliases=(
            "delta-8 thc", "delta-8-thc", "Δ8-THC", "delta8 THC",
            "Δ⁸-tetrahydrocannabinol", "D8-THC", "D8 THC",
        ),
        chemistry_note=(
            "Δ⁸-THC is a positional double-bond isomer of Δ⁹-THC, with "
            "the C8 ↔ C9 double bond at C8 ↔ C7 in the cyclohexene ring. "
            "Marginally more thermally stable than Δ⁹-THC (Δ⁸ does not "
            "oxidise to CBN as readily). Naturally present at < 1% in "
            "most plant material; commercial Δ⁸-THC is almost entirely "
            "produced via acid-catalysed isomerisation from CBD, which "
            "leaves behind detectable reaction by-products that COA "
            "chemistry should report."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="partial agonist (lower potency than Δ⁹-THC)",
                affinity_note=(
                    "Ki ≈ 44 nM (rat brain membrane); functionally ~50-75% "
                    "the psychoactive potency of equimolar Δ⁹-THC. Reduced "
                    "but not eliminated psychoactivity is the qualitative "
                    "distinction commonly attributed to Δ⁸ in user reports."
                ),
                assay="[³H]-CP55,940 competitive binding",
                citations=(_PERTWEE_2008,),
            ),
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="partial agonist",
                affinity_note="Ki ≈ 44 nM, comparable to Δ⁹-THC at CB2.",
                assay="[³H]-CP55,940 competitive binding",
                citations=(_PERTWEE_2008,),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.C,
        clinical_evidence=(
            ClinicalEvidenceRow(
                indication="antiemetic — paediatric chemotherapy nausea (historical, very small)",
                design="open-label, single-arm pilot",
                n=8,
                dose_route=(
                    "18 mg/m² oral every 6 hours starting 2 hours pre-chemo"
                ),
                outcome=(
                    "Antiemetic response reported in all 8 paediatric "
                    "patients in Abrahamov 1995 — historical, single-site, "
                    "open-label, pre-modern antiemetic standards. No "
                    "controlled trial has reproduced the finding."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(
                    MinorCannabinoidCitation(
                        label=(
                            "Abrahamov A et al., Life Sci 1995, "
                            "Δ⁸-THC antiemetic in paediatric oncology"
                        ),
                        pmid="7776837", year=1995,
                    ),
                ),
                caveats=(
                    "Open-label, n=8, no contemporaneous control arm.",
                    "Conducted before modern 5-HT3 antagonists were "
                    "available; the comparator landscape has shifted.",
                    "Not a basis for current antiemetic recommendation.",
                ),
            ),
        ),
        clinical_grade=MinorCannabinoidEvidenceClass.D,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="appetite + analgesia",
                species_or_assay="mouse, multiple endpoints",
                dose_or_concentration="1-10 mg/kg i.p.",
                outcome=(
                    "Increases food intake and produces antinociception "
                    "with reduced cataleptic behaviour compared to "
                    "equimolar Δ⁹-THC."
                ),
                bridging_to_clinic=(
                    "Bridges weakly — the catalepsy-sparing signal is "
                    "interesting but i.p. mouse dosing does not translate "
                    "to oral human consumer products with conversion-derived "
                    "Δ⁸-THC and uncharacterised by-products."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(_PERTWEE_2008,),
            ),
        ),
        regulatory_status=(
            "US federal — gray zone. The 2018 Farm Bill defines hemp as "
            "Cannabis sativa with Δ⁹-THC < 0.3% by dry weight; Δ⁸-THC "
            "isomerised from hemp-CBD sits outside that explicit "
            "definition. DEA's August 2020 Interim Final Rule treats "
            "'synthetically derived' tetrahydrocannabinols as Schedule I; "
            "the 9th Circuit AK Futures v Boyd Street (2022) treated "
            "hemp-derived Δ⁸-THC as legal under the Farm Bill in that "
            "circuit only. Multiple states have explicitly banned (NY, "
            "CO, CT, OR, AK, AZ, AR, DE, ID, IA, MS, MT, NV, RI, UT, "
            "VT, WA) as of 2024-2026. EU — Novel Food per Regulation "
            "2015/2283; multiple member states have banned outright "
            "(Hungary 2023, France ANSM action 2023). For research: "
            "treat as Schedule I federally and obtain DEA Schedule I "
            "Researcher Registration."
        ),
        commercial_reality=(
            "Most commercial Δ⁸-THC is produced via acid-catalysed "
            "isomerisation from CBD. The reaction commonly produces "
            "uncharacterised by-products including Δ⁹-THC (regulatory "
            "compliance failure), Δ⁸-iso-THC, olivetol derivatives, and "
            "occasional polychlorinated by-products when acid washes use "
            "chlorinated solvents. Independent third-party COA is the "
            "minimum quality bar; consumer-grade Δ⁸ products from "
            "convenience-store distribution channels frequently fail "
            "label-claim accuracy and contaminant screens."
        ),
        safety_note=(
            "Acute safety profile qualitatively similar to Δ⁹-THC at "
            "equipotent doses: tachycardia, hypotension, psychomotor "
            "impairment, anxiety / paranoia at high doses. Public health "
            "concern in 2021-2024 from poison-control reports of acute "
            "intoxication in paediatric ingestions of unlabelled / "
            "mislabelled Δ⁸ edibles. CDC Health Alert Network 2021 "
            "described 660 + adverse-event reports from December 2020 to "
            "July 2021; CDC MMWR follow-ups described continuing harm. "
            "Conversion-derived by-products represent uncharacterised "
            "long-term risk."
        ),
        pharmacokinetics_note=(
            "Oral bioavailability not formally characterised in published "
            "human PK studies; by structural analogy to Δ⁹-THC "
            "(~6-10% oral, ~25-35% inhaled). Half-life similar to Δ⁹-THC. "
            "Cross-reactivity with standard urine immunoassays for Δ⁹-THC "
            "is high; chromatographic confirmation is required for "
            "differentiation."
        ),
        key_uncertainties=(
            "No Phase II or III RCT for any indication.",
            "Long-term safety of conversion-derived material with "
            "uncharacterised by-products is genuinely unknown.",
            "Reduced psychoactivity claim is qualitative — controlled "
            "human dose-response comparisons to Δ⁹-THC are lacking.",
            "Regulatory status is actively contested; trial design must "
            "treat as Schedule I federally until clarified.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'Δ⁸-THC is non-psychoactive / non-intoxicating.' "
            "Δ⁸-THC is a partial CB1 agonist and produces dose-dependent "
            "intoxication. The 'reduced' or 'milder' descriptions in "
            "marketing copy reflect relative potency, not absence of "
            "psychoactivity.",
            "MISCONCEPTION: 'Hemp-derived Δ⁸ is federally legal.' "
            "Federal status is genuinely contested between the Farm "
            "Bill's hemp definition and DEA's 2020 IFR position on "
            "synthetically derived THC.",
            "MISCONCEPTION: 'Δ⁸-THC is safer than Δ⁹-THC.' No comparative "
            "safety data support this; the case-report literature on "
            "acute paediatric exposures to mislabelled Δ⁸ products "
            "argues the opposite at the population level.",
        ),
        citations=(_PERTWEE_2008,),
    ),

    # ── HHC (spec 002 US6) ────────────────────────────────────────────
    MinorCannabinoid(
        name="HHC",
        long_name="hexahydrocannabinol",
        aliases=("hexahydrocannabinol", "hexahydro-THC", "9-norhydroxy-HHC"),
        chemistry_note=(
            "HHC is the saturated (hydrogenated) hexahydro analogue of "
            "Δ⁹-THC; the C9-C10 alkene of THC is reduced to a single "
            "bond, removing the geometric isomerism that distinguishes "
            "Δ⁹ from Δ⁸. Commercial HHC is a mixture of 9R-HHC and 9S-"
            "HHC diastereomers — the 9R isomer is the more pharmacologically "
            "active form; commercial mixtures often contain 50-80% 9R / "
            "20-50% 9S, with potency varying by lot. Industrial production "
            "is by Pd/C-catalysed hydrogenation of CBD or Δ⁹-THC, which "
            "leaves residual metal-catalyst contamination that COA "
            "chemistry should report."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="partial agonist (9R isomer) / weak agonist (9S isomer)",
                affinity_note=(
                    "Ki not formally characterised in modern competitive-"
                    "binding assays; functional response data are "
                    "primarily mid-20th-century pharmacology (Adams 1942, "
                    "Mechoulam 1972) prior to standard CB1-cloning era. "
                    "Diastereomer ratio dominates the functional response."
                ),
                assay="historical functional data; modern Ki not published",
                citations=(
                    MinorCannabinoidCitation(
                        label=(
                            "Mechoulam R et al., Hexahydrocannabinol pharmacology "
                            "review (historical)"
                        ),
                        pmid="4348475", year=1972,
                    ),
                ),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.E,
        clinical_evidence=(),
        clinical_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="behavioural — cataleptogenic / hypothermic",
                species_or_assay="mouse, mid-20th-century pharmacology",
                dose_or_concentration="5-25 mg/kg s.c. (historical)",
                outcome=(
                    "Δ⁹-THC-like cataleptic + hypothermic effects at "
                    "comparable doses for the 9R isomer."
                ),
                bridging_to_clinic=(
                    "Bridges essentially not at all to current clinical "
                    "use. Historical mid-20th-century animal studies "
                    "predate modern bioanalytical chemistry and use "
                    "diastereomer mixtures the contemporary commercial "
                    "product also delivers; the studies are not a "
                    "substitute for modern human PK / efficacy / safety "
                    "data."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(
                    MinorCannabinoidCitation(
                        label="Adams R et al., J Am Chem Soc 1942, synthesis of HHC",
                        doi="10.1021/ja01258a047", year=1942,
                    ),
                ),
            ),
        ),
        regulatory_status=(
            "US federal — gray zone, see Δ⁹-THC notes; hemp-derived HHC "
            "from CBD hydrogenation arguably falls outside the 2018 Farm "
            "Bill since HHC is not itself THC. DEA's 2020 IFR position "
            "and the Federal Analog Act (21 USC §813) provide the most "
            "likely Schedule I treatment. EU — Hungary, Estonia, Slovenia, "
            "Lithuania, Finland have explicitly banned (2023-2024); "
            "France ANSM has classified as a narcotic (June 2023). "
            "EU Novel Food authorisation NOT granted. For research: "
            "treat as Schedule I federally."
        ),
        commercial_reality=(
            "Commercial HHC is the most chemistry-uncontrolled cannabinoid "
            "in the US market as of 2024-2026: diastereomer ratio, residual "
            "Pd / Pt catalyst, residual solvent (heptane / ethanol / "
            "ethyl acetate), and conversion-by-product profile vary "
            "lot-to-lot. Independent third-party COA with metal-screening "
            "AND chiral chromatography is the minimum quality bar; few "
            "consumer products meet this."
        ),
        safety_note=(
            "Acute safety data are essentially absent in modern peer-"
            "reviewed clinical literature. Surveillance case reports "
            "describe acute intoxication consistent with CB1 partial "
            "agonism. Chronic safety, drug-interaction profile, and "
            "long-term diastereomer / catalyst-residue exposure risk "
            "are all unknown."
        ),
        pharmacokinetics_note=(
            "No published human PK study. Cross-reactivity with standard "
            "Δ⁹-THC immunoassays is variable; chromatographic confirmation "
            "is required for workplace / clinical testing."
        ),
        key_uncertainties=(
            "No modern Phase I human PK study.",
            "No clinical trial for any indication.",
            "Diastereomer ratio variability is uncharacterised at the "
            "consumer-product level.",
            "Long-term safety of residual catalyst / by-product exposure "
            "is genuinely unknown.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'HHC is a natural plant cannabinoid.' "
            "Trace HHC has been detected in pollen and aged seed extract "
            "but commercial HHC is virtually entirely hydrogenation-"
            "derived from CBD or Δ⁹-THC.",
            "MISCONCEPTION: 'HHC is non-detectable on drug tests.' "
            "Cross-reactivity with standard cannabinoid immunoassays "
            "is variable but non-zero; chromatographic methods detect "
            "HHC and its metabolites reliably.",
            "MISCONCEPTION: 'HHC is well-characterised pharmacologically.' "
            "Modern Ki / EC50 data and human PK / efficacy / safety "
            "data are all essentially absent.",
        ),
        citations=(),
    ),

    # ── THCO (spec 002 US6) ────────────────────────────────────────────
    MinorCannabinoid(
        name="THCO",
        long_name="Δ⁹-tetrahydrocannabinol-O-acetate",
        aliases=("THC-O", "THC-O-acetate", "THCOA", "delta-9-THC-O-acetate"),
        chemistry_note=(
            "THCO is the O-acetylated ester of Δ⁹-THC; the phenolic "
            "hydroxyl at C1 is acetylated. As a prodrug ester, it is "
            "pharmacologically inactive until ester hydrolysis liberates "
            "the parent Δ⁹-THC in vivo. Commercial THCO is synthesised "
            "from Δ⁹-THC + acetic anhydride; the reaction profile is "
            "well-characterised but consumer-grade material may carry "
            "residual acetic anhydride and uncharacterised pyrolysis "
            "products when smoked or vaped."
        ),
        receptor_activity=(),
        pharmacology_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        clinical_evidence=(),
        clinical_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        preclinical_evidence=(),
        regulatory_status=(
            "US federal — Schedule I. The DEA explicitly addressed THCO "
            "in a February 2023 letter to the AHPA, holding that THCO "
            "does not occur naturally in cannabis and therefore cannot "
            "be a hemp-derived cannabinoid under the Farm Bill — "
            "synthetic-conversion derived THCO is Schedule I regardless "
            "of starting material. EU and UK — same Schedule I treatment "
            "as Δ⁹-THC under member-state controlled-drug frameworks."
        ),
        commercial_reality=(
            "Commercial THCO was a brief market presence in 2021-2023 "
            "before the DEA's February 2023 letter and subsequent "
            "enforcement guidance largely cleared distributors. Where "
            "available, residual acetic anhydride and pyrolysis-product "
            "profile (suspected to include ketene-forming pathways at "
            "vaping temperatures) are the dominant chemistry concerns."
        ),
        safety_note=(
            "No clinical safety data. Concern in the harm-reduction "
            "community over pyrolysis products of vaporised acetate "
            "esters (analogy to vitamin-E acetate / EVALI 2019) — "
            "the analogy is not perfectly tight (vit-E acetate's "
            "pulmonary toxicity mechanism is distinct), but the lack "
            "of any actual pulmonary toxicology data on inhaled THCO "
            "represents an unknown."
        ),
        pharmacokinetics_note=(
            "Onset is delayed relative to Δ⁹-THC because ester "
            "hydrolysis is rate-limiting. Reported half-life is similar "
            "to Δ⁹-THC once liberated. No formal published human PK "
            "study."
        ),
        key_uncertainties=(
            "No published human PK study.",
            "No clinical trial for any indication.",
            "Inhalation pyrolysis-product toxicology is essentially "
            "unstudied.",
            "Long-term safety of repeated ester-hydrolysis dosing is "
            "uncharacterised.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'THCO is 3x stronger than THC.' This is "
            "anecdote-derived; controlled human dose-response comparisons "
            "do not exist. The phenomenologic difference users describe "
            "is consistent with delayed onset + cumulative dosing rather "
            "than per-mg potency, but the controlled data are absent.",
            "MISCONCEPTION: 'THCO is hemp-derived and federally legal.' "
            "DEA February 2023 letter clarifies THCO is Schedule I "
            "regardless of starting material.",
        ),
        citations=(),
    ),

    # ── THCP (spec 002 US6) ────────────────────────────────────────────
    MinorCannabinoid(
        name="THCP",
        long_name="tetrahydrocannabiphorol",
        aliases=("Δ⁹-THCP", "delta-9-THCP", "tetrahydrocannabiphorol-C7"),
        chemistry_note=(
            "THCP is the C7-alkyl homologue of Δ⁹-THC (Δ⁹-THC has a "
            "C5-pentyl side chain; THCP has a C7-heptyl side chain). The "
            "extended side chain enhances CB1 affinity by roughly an "
            "order of magnitude in competitive-binding assays. Identified "
            "in Cannabis sativa cv FM2 by Citti et al. 2019, the first "
            "isolation paper. Natural plant concentrations are very low "
            "(< 0.1% typical) — commercial material is either "
            "extract-concentrated or synthesised."
        ),
        receptor_activity=(
            ReceptorActivity(
                target="CB1",
                uniprot="P21554",
                gene_symbol="CNR1",
                activity="full agonist (high affinity)",
                affinity_note=(
                    "Ki ≈ 1.2 nM at CB1 in [³H]-CP55,940 displacement "
                    "(Citti 2019), ~33-fold tighter than Δ⁹-THC under "
                    "the same conditions. Functional activity in "
                    "transfected-cell cAMP assays consistent with full "
                    "agonism."
                ),
                assay="[³H]-CP55,940 competitive binding (Citti 2019)",
                citations=(
                    MinorCannabinoidCitation(
                        label=(
                            "Citti C et al., Sci Rep 2019, isolation + "
                            "pharmacology of THCP from Cannabis sativa FM2"
                        ),
                        pmid="31889124", year=2019,
                    ),
                ),
            ),
            ReceptorActivity(
                target="CB2",
                uniprot="P34972",
                gene_symbol="CNR2",
                activity="full agonist",
                affinity_note=(
                    "Ki ≈ 6.2 nM at CB2 (Citti 2019); the affinity ratio "
                    "CB1/CB2 is similar to Δ⁹-THC despite the higher "
                    "absolute affinity at both."
                ),
                assay="[³H]-CP55,940 competitive binding (Citti 2019)",
                citations=(
                    MinorCannabinoidCitation(
                        label=(
                            "Citti C et al., Sci Rep 2019, isolation + "
                            "pharmacology of THCP"
                        ),
                        pmid="31889124", year=2019,
                    ),
                ),
            ),
        ),
        pharmacology_grade=MinorCannabinoidEvidenceClass.D,
        clinical_evidence=(),
        clinical_grade=MinorCannabinoidEvidenceClass.UNSUPPORTED,
        preclinical_evidence=(
            PreclinicalEvidenceRow(
                indication_or_model="cataleptic + hypothermic — tetrad behavioural panel",
                species_or_assay="mouse, intraperitoneal",
                dose_or_concentration="1-10 mg/kg i.p.",
                outcome=(
                    "Produced THC-like cataleptic + hypothermic behavioural "
                    "effects at lower doses than equipotent Δ⁹-THC; "
                    "consistent with the higher in-vitro CB1 affinity."
                ),
                bridging_to_clinic=(
                    "Bridges to clinic only as receptor-pharmacology "
                    "validation. The single isolation paper does not "
                    "substitute for a clinical study; the higher CB1 "
                    "affinity may not produce proportionate clinical "
                    "potency in humans because pharmacokinetics + active-"
                    "metabolite formation differ from Δ⁹-THC."
                ),
                grade=MinorCannabinoidEvidenceClass.D,
                citations=(
                    MinorCannabinoidCitation(
                        label="Citti C et al., Sci Rep 2019, in vivo tetrad data on THCP",
                        pmid="31889124", year=2019,
                    ),
                ),
            ),
        ),
        regulatory_status=(
            "US federal — gray zone. Plant-isolated THCP arguably falls "
            "within the 2018 Farm Bill hemp definition if Δ⁹-THC < 0.3% "
            "by dry weight, since THCP is structurally distinct from "
            "Δ⁹-THC. Synthetically derived THCP follows the DEA's 2020 "
            "IFR position on synthetic tetrahydrocannabinols and the "
            "Federal Analog Act when intended for human consumption. "
            "For research: treat as Schedule I federally. EU — Novel "
            "Food per Regulation 2015/2283; member-state status varies."
        ),
        commercial_reality=(
            "Genuine THCP is rare. Most products marketed as THCP are "
            "either mis-labelled (containing Δ⁹-THC + Δ⁸-THC at "
            "conventional concentrations rather than true THCP), or "
            "contain trace authentic THCP in a Δ⁹-THC-dominant matrix. "
            "Independent third-party chiral-LC-MS COA with explicit "
            "THCP standard is the minimum verification bar; few products "
            "meet it."
        ),
        safety_note=(
            "No clinical safety data. By in-vitro affinity, dose-for-dose "
            "psychoactive intensity may exceed Δ⁹-THC at equal mass; "
            "real-world consumer doses are unclear because of pervasive "
            "mis-labelling. Acute presentation case reports describe "
            "Δ⁹-THC-like intoxication with no evidence of qualitatively "
            "distinct toxicity."
        ),
        pharmacokinetics_note=(
            "No published human PK study. Animal PK suggests longer "
            "half-life than Δ⁹-THC due to higher lipophilicity (estimated "
            "logP ≈ 8.0 vs 6.5 for Δ⁹-THC). Cross-reactivity with "
            "standard immunoassays is incompletely characterised; "
            "chromatographic confirmation is required for workplace / "
            "clinical testing."
        ),
        key_uncertainties=(
            "No human PK study.",
            "No clinical trial for any indication.",
            "In-vivo potency at typical consumer exposure is "
            "uncharacterised in humans.",
            "Drug-interaction profile (CYP3A4 / CYP2C9 substrate "
            "behaviour) is presumed similar to Δ⁹-THC but not formally "
            "studied.",
        ),
        common_misconceptions=(
            "MISCONCEPTION: 'THCP is 33x stronger than THC because Ki "
            "is 33x tighter.' In-vitro Ki ratios do not transfer linearly "
            "to clinical potency; the published in-vivo tetrad data show "
            "enhanced effect but at < 33-fold dose ratio.",
            "MISCONCEPTION: 'Most products labelled THCP contain THCP.' "
            "Independent COA testing finds most consumer-marketed THCP "
            "products contain primarily Δ⁹-THC + Δ⁸-THC with little or "
            "no detectable THCP.",
        ),
        citations=(
            MinorCannabinoidCitation(
                label="Citti C et al., Sci Rep 2019, THCP isolation + pharmacology",
                pmid="31889124", year=2019,
            ),
        ),
    ),
)


def all_minor_cannabinoids() -> tuple[MinorCannabinoid, ...]:
    """Return the full curated registry (read-only)."""
    return _REGISTRY


def find_minor_cannabinoid(name_or_alias: str) -> MinorCannabinoid | None:
    """Look up a minor cannabinoid by canonical name or alias.

    Case-insensitive. Returns ``None`` when no entry matches.
    """
    needle = name_or_alias.strip().lower()
    if not needle:
        return None
    for x in _REGISTRY:
        if needle == x.name.lower():
            return x
        if needle == x.long_name.lower():
            return x
        for alias in x.aliases:
            if needle == alias.lower():
                return x
    return None


# Detection patterns — used by detect_minor_cannabinoid_mention to
# surface the right entry when a query mentions a minor cannabinoid.
_DETECT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bTHCV\b|\btetrahydrocannabivarin\b|\bΔ?9?-?THCV\b",
                re.IGNORECASE), "THCV"),
    (re.compile(r"\bCBDV\b|\bcannabidivarin\b", re.IGNORECASE), "CBDV"),
    (re.compile(r"\bCBC\b|\bcannabichromene\b", re.IGNORECASE), "CBC"),
    (re.compile(r"\bCBN\b|\bcannabinol\b", re.IGNORECASE), "CBN"),
    (re.compile(r"\bCBG\b|\bcannabigerol\b", re.IGNORECASE), "CBG"),
    # Spec 002 US6 — closing the minor-cannabinoid blind spot.
    (re.compile(
        r"Δ?8-?THC\b|Δ⁸-?THC\b|\bdelta[- ]?8[- ]?(?:thc|tetrahydrocannabinol)\b|"
        r"\bD8[- ]?THC\b|\bD-?8\b",
        re.IGNORECASE,
    ), "Δ⁸-THC"),
    (re.compile(
        r"\bHHC\b|\bhexahydrocannabinol\b|\bhexahydro[- ]?thc\b",
        re.IGNORECASE,
    ), "HHC"),
    (re.compile(
        r"\bTHC-?O(?:[- ]?acetate)?\b|\bTHCOA\b|\bTHC-?O-?A\b",
        re.IGNORECASE,
    ), "THCO"),
    (re.compile(
        r"\bTHCP\b|\btetrahydrocannabiphorol\b|\bΔ?9?-?THCP\b",
        re.IGNORECASE,
    ), "THCP"),
)


def detect_minor_cannabinoid_mention(text: str) -> tuple[MinorCannabinoid, ...]:
    """Return registry entries for every minor cannabinoid named in ``text``.

    Deduplicated; preserves registry order so callers can rely on a
    stable iteration order.
    """
    seen: set[str] = set()
    out: list[MinorCannabinoid] = []
    for entry, _span in detect_minor_cannabinoid_mention_with_spans(text):
        if entry.name not in seen:
            seen.add(entry.name)
            out.append(entry)
    return tuple(out)


def detect_minor_cannabinoid_mention_with_spans(
    text: str,
) -> tuple[tuple[MinorCannabinoid, tuple[int, int]], ...]:
    """Return ``(entry, span)`` pairs for every minor-cannabinoid hit.

    Spec 003 US1 / FR-001 — exposes match spans so the compose layer
    can suppress an overlapping major-cannabinoid hit ("THC" inside
    "Δ⁸-THC"). Multiple matches per entry are returned in document order;
    downstream consumers deduplicate by entry name.
    """
    out: list[tuple[MinorCannabinoid, tuple[int, int]]] = []
    for pat, name in _DETECT_PATTERNS:
        for m in pat.finditer(text):
            entry = find_minor_cannabinoid(name)
            if entry is None:
                continue
            out.append((entry, m.span()))
    return tuple(out)


def format_for_researcher(
    entry: MinorCannabinoid,
    *,
    title: bool = True,
    heading_level: int = 1,
    include_regulatory: bool = False,
    include_commercial: bool = False,
    sections: "frozenset[str] | None" = None,
) -> str:
    """Render a Markdown research monograph for a single cannabinoid.

    Canonical rendering used by ``cannavec.answer.compose_answer`` and any
    audience surface that needs a full per-compound evidence picture. Wording
    matches the registry's declared evidence grades; surfaces must not upgrade
    or downgrade these grades when rendering.

    Presentation discipline (one clean heading tree):
      * ``title`` emits the compound title line. When this monograph is nested
        under an Answer section that already names the compound, pass
        ``title=False`` so the brief keeps a single heading tree — no in-body
        H1 colliding with the Answer's own ``##`` sections.
      * ``heading_level`` is the Markdown depth of the title; sub-sections
        render one level deeper. The nested caller passes ``heading_level=2``
        so sub-sections become ``###`` under the Answer's ``##`` heading.

    Scope discipline (Constitution §IV — primary-source research science only):
      * ``regulatory_status`` (multi-jurisdiction scheduling) and
        ``commercial_reality`` (consumer-market / COA prose) are not research
        science and are omitted from the brief by default. They remain in the
        typed record (:meth:`MinorCannabinoid.to_dict`) and can be opted back
        in with ``include_regulatory`` / ``include_commercial``.

    Relevance discipline (answer the question, not the entity):
      * ``sections`` selects which sub-sections render, by key —
        ``chemistry``, ``receptor``, ``clinical``, ``preclinical``, ``pk``,
        ``safety``, ``uncertainties``, ``misconceptions``, ``citations``.
        ``None`` (default) renders the full science monograph; the Answer
        composer narrows it per detected question intent so a mechanism
        question is not buried under efficacy tables, and vice-versa.
    """
    sub = "#" * (heading_level + 1)

    def _want(key: str) -> bool:
        return sections is None or key in sections

    out: list[str] = []
    if title:
        out.append(f"{'#' * heading_level} {entry.name} — {entry.long_name}")
        if entry.aliases:
            out.append(f"*Aliases:* {', '.join(entry.aliases)}")
        out.append("")
    else:
        # Title suppressed: the enclosing Answer section already names the
        # compound. Keep the long name + aliases on a compact identity line so
        # no information is lost along with the H1.
        ident_line = f"*{entry.long_name}*"
        seen = {entry.name.lower(), entry.long_name.lower()}
        extra_aliases = [a for a in entry.aliases if a.lower() not in seen]
        if extra_aliases:
            ident_line += f" — also: {', '.join(extra_aliases)}"
        out.append(ident_line)
        out.append("")
    if _want("chemistry"):
        out.append(f"{sub} Chemistry")
        out.append(entry.chemistry_note)
        out.append("")
    if _want("receptor"):
        out.append(
            f"{sub} Receptor pharmacology (grade: {_format_grade(entry.pharmacology_grade)})"
        )
        for r in entry.receptor_activity:
            ident = []
            if r.uniprot:
                ident.append(f"UniProt {r.uniprot}")
            if r.gene_symbol:
                ident.append(f"HGNC {r.gene_symbol}")
            ident_str = f" ({'; '.join(ident)})" if ident else ""
            out.append(f"- **{r.target}**{ident_str} — {r.activity}. {r.affinity_note} Assay: {r.assay}.")
            cite_str = "; ".join(_short_cite(c) for c in r.citations)
            if cite_str:
                out.append(f"  - Source: {cite_str}")
            # v2.7 in-vitro → clinic translation discipline (P2.13). When
            # the registry has populated the translation fields, surface
            # them so the user reads the in-vitro Ki vs in-vivo exposure
            # gap explicitly. This is the discipline the entourage-
            # effect literature systematically skips.
            if r.typical_clinical_exposure:
                out.append(
                    f"  - Typical clinical exposure: "
                    f"{r.typical_clinical_exposure}"
                )
            if r.predicted_receptor_occupancy_at_typical_dose:
                out.append(
                    f"  - Predicted receptor occupancy at typical dose: "
                    f"{r.predicted_receptor_occupancy_at_typical_dose}"
                )
            if r.translation_caveat:
                out.append(
                    f"  - **Translation caveat:** {r.translation_caveat}"
                )
        out.append("")
    if _want("clinical"):
        out.append(
            f"{sub} Human clinical evidence (grade: {_format_grade(entry.clinical_grade)})"
        )
        if not entry.clinical_evidence:
            out.append("- No clinical-evidence rows in the registry.")
        for c in entry.clinical_evidence:
            # ``n`` is a patient count and is a meaningless ``0`` for a
            # systematic review / meta-analysis row — omit it rather than
            # print "n=0".
            n_str = f"n={c.n}, " if c.n else ""
            out.append(f"- **{c.indication}** — {c.design}, {n_str}{c.dose_route}.")
            out.append(f"  - **Outcome:** {c.outcome}")
            out.append(f"  - **Grade:** {_format_grade(c.grade)}")
            cite_str = "; ".join(_short_cite(c2) for c2 in c.citations)
            if cite_str:
                out.append(f"  - Source: {cite_str}")
            for caveat in c.caveats:
                out.append(f"  - *Caveat:* {caveat}")
        out.append("")
    if _want("preclinical"):
        out.append(f"{sub} Preclinical evidence (with bridging-to-clinic caveats)")
        if not entry.preclinical_evidence:
            out.append("- No preclinical rows in the registry.")
        for p in entry.preclinical_evidence:
            out.append(f"- **{p.indication_or_model}** — {p.species_or_assay}, {p.dose_or_concentration}.")
            out.append(f"  - **Outcome:** {p.outcome}")
            out.append(f"  - **Bridging to clinic:** {p.bridging_to_clinic}")
            out.append(f"  - **Grade:** {_format_grade(p.grade)}")
            cite_str = "; ".join(_short_cite(c2) for c2 in p.citations)
            if cite_str:
                out.append(f"  - Source: {cite_str}")
        out.append("")
    if _want("pk"):
        out.append(f"{sub} Pharmacokinetics")
        out.append(entry.pharmacokinetics_note)
        out.append("")
    if _want("safety"):
        out.append(f"{sub} Safety")
        out.append(entry.safety_note)
        out.append("")
    # Constitution §IV: regulatory scheduling + consumer-market prose are not
    # primary-source research science and are omitted from the brief by
    # default (opt back in for a non-science surface via the flags).
    if include_regulatory:
        out.append(f"{sub} Regulatory status")
        out.append(entry.regulatory_status)
        out.append("")
    if include_commercial:
        out.append(f"{sub} Commercial reality")
        out.append(entry.commercial_reality)
        out.append("")
    if entry.key_uncertainties and _want("uncertainties"):
        out.append(f"{sub} Key uncertainties")
        for u in entry.key_uncertainties:
            out.append(f"- {u}")
        out.append("")
    if entry.common_misconceptions and _want("misconceptions"):
        out.append(f"{sub} Common misconceptions (refused)")
        for m in entry.common_misconceptions:
            out.append(f"- {m}")
        out.append("")
    if entry.citations and _want("citations"):
        out.append(f"{sub} Cross-cutting citations")
        for c in entry.citations:
            out.append(f"- {_short_cite(c)}")
    return "\n".join(out)


def _format_grade(g: MinorCannabinoidEvidenceClass) -> str:
    """Render an evidence grade for the monograph: 'Level A/B/C/D/E'
    for ordinal levels, 'Unsupported' for the no-admissible-source
    case. Prevents the cosmetic 'Level Unsupported' artifact."""
    if g == MinorCannabinoidEvidenceClass.UNSUPPORTED:
        return g.value  # "Unsupported"
    return f"Level {g.value}"


def _short_cite(c: MinorCannabinoidCitation) -> str:
    parts: list[str] = [c.label]
    if c.pmid:
        parts.append(f"PMID {c.pmid}")
    if c.doi:
        parts.append(f"doi:{c.doi}")
    if c.url:
        parts.append(c.url)
    return " — ".join(parts)
