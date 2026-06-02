"""Cannabis endocrinology registry (spec 026 US1 / FR-026).

Research-grade primary literature on how cannabis / phytocannabinoids /
the endocannabinoid system interact with the human (and model-organism)
endocrine system — the metabolic, reproductive, thyroid, adrenal,
somatotropic, and skeletal axes. This is one of the most-asked and
least-curated cannabis-research surfaces: spec 025 returned 0 curated
claims for every endocrine-axis prompt (insulin sensitivity, HPT/HPA/HPG
axes, adipogenesis, embryo implantation, bone mineral density). Spec 026
ships the curated backbone under Constitution §IV with a primary citation
per §I for every row.

Evidence-honesty note (§VII). The cannabis-endocrinology literature is
overwhelmingly **observational** (cross-sectional surveys, infertility
cohorts, register studies) or **preclinical/mechanistic** (rodent and
primate models, receptor-trafficking assays). There is almost no
pre-registered, adequately-powered RCT evidence on these endpoints, and
several endpoints (adolescent neuroendocrine response; THC:CBD-ratio
receptor trafficking in *endocrine* tissue specifically) have **no**
direct human data at all. The deterministic grader therefore caps every
row at **Level C** (single primary study / mechanism), which is the
correct, credible grade — not a limitation. Each row carries the
study design and the causal-inference caveat a reviewer would demand.

Topic coverage (one per canonical endocrine question):

- ``metabolic_insulin`` — Penner 2013 Am J Med, NHANES 2005-2010
  cross-sectional (PMID 23684393). Current cannabis use associated with
  ~16-17% lower fasting insulin / HOMA-IR and smaller waist
  circumference. Association, not causation; no dose-response.
- ``adipogenesis_leptin`` — Vettor & Pagano 2009 Best Pract Res Clin
  Endocrinol Metab (PMID 19285260). CB1-receptor activation stimulates
  lipogenesis / adipogenesis / LPL in adipocytes; the leptin–
  endocannabinoid feedback loop. Mechanism (mostly rodent + in vitro).
- ``diabetic_ketoacidosis`` — Akturk 2019 JAMA Intern Med (PMID
  30398521) + Akturk 2022 Diabetes Care (PMID 34880067). Cannabis use
  associated with higher DKA risk in adults with type 1 diabetes, with
  the cannabinoid-hyperemesis confounder dissected in the 2022 paper.
- ``thyroid_hpt`` — Bonnet 2013 Pharmacopsychiatry (PMID 22821384) +
  Brown & Dobs 2002 (PMID 12412841) + Murphy 1998 (PMID 9974176). The
  one human study found TSH / T3 / free-T4 within range and *no*
  correlation with serum Δ⁹-THC; animal data show TSH suppression.
- ``growth_hormone_prolactin`` — Brown & Dobs 2002 (PMID 12412841) +
  Murphy 1998 (PMID 9974176). Acute cannabinoid suppresses growth
  hormone and prolactin in animals; human data inconsistent; **no**
  controlled adolescent-versus-adult data exist.
- ``gonadal_hpg`` — Payne 2019 J Urol systematic review (PMID 30916627)
  + Belladelli 2022 Andrology cohort (PMID 35868833) + Smith & Asch 1984
  primate (PMID 6090911). Lowered LH, inconsistent testosterone in men;
  ovulatory disruption in female primates; reversible, tolerance.
- ``embryo_implantation`` — Wang/Dey 2006 J Clin Invest mouse (PMID
  16886060) + Maccarrone 2002 Mol Hum Reprod human IVF (PMID 11818522).
  A tightly-regulated anandamide "tone" (FAAH-set) gates implantation;
  dysregulation (high AEA / exogenous Δ⁹-THC) impairs it.
- ``adrenal_hpa`` — van Leeuwen 2011 Addiction TRAILS cohort (PMID
  21631618) + Petrowski 2019 (PMID 30879013) + Brown & Dobs 2002.
  Acute Δ⁹-THC activates the HPA axis; chronic use blunts cortisol
  stress reactivity (and, by extension, the cortisol awakening response).
- ``receptor_desensitization`` — Lazenka 2012 Life Sci (PMID 22940268)
  + Rubino 2005 J Neurochem (PMID 15857401). Repeated Δ⁹-THC drives
  region-specific CB1 desensitization and downregulation; endocrine-
  tissue-specific and THC:CBD-ratio-resolved data are essentially absent.
- ``bone_remodeling`` — Ofek 2006 PNAS (PMID 16407142) + Bab & Zimmer
  2007 Br J Pharmacol (PMID 18071301). CB2 maintains bone mass (CB2-KO
  → osteoporosis-like loss; agonist protective); CB1 modulates bone via
  sympathetic tone; human CNR2 variants track BMD. Preclinical-dominant.

Each row carries ``to_claim()``, identifier-anchored citations per §I,
and a topic-keyword regex detector. Reference-only — no live discovery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from cannavec_science.evidence import (
    Claim,
    ClaimType,
    EvidenceLevel,
    Source,
    SourceTier,
    required_disclosures,
)


__all__ = [
    "EndocrineCitation",
    "EndocrineRow",
    "EndocrineTopic",
    "all_endocrine_rows",
    "find_endocrine_rows",
    "detect_endocrine_mention",
    "render_markdown",
]


class EndocrineTopic:
    METABOLIC_INSULIN = "metabolic_insulin"
    ADIPOGENESIS_LEPTIN = "adipogenesis_leptin"
    DIABETIC_KETOACIDOSIS = "diabetic_ketoacidosis"
    THYROID_HPT = "thyroid_hpt"
    GROWTH_HORMONE_PROLACTIN = "growth_hormone_prolactin"
    GONADAL_HPG = "gonadal_hpg"
    EMBRYO_IMPLANTATION = "embryo_implantation"
    ADRENAL_HPA = "adrenal_hpa"
    RECEPTOR_DESENSITIZATION = "receptor_desensitization"
    BONE_REMODELING = "bone_remodeling"
    # Spec 027 — second endocrine question wave.
    AUTOIMMUNE_THYROIDITIS = "autoimmune_thyroiditis"
    BETA_CELL_SURVIVAL = "beta_cell_survival"
    PRENATAL_NEUROENDOCRINE = "prenatal_neuroendocrine"
    MELATONIN_CIRCADIAN = "melatonin_circadian"
    CBD_FULLSPECTRUM_CORTISOL = "cbd_fullspectrum_cortisol"
    CHS_ADH_ELECTROLYTE = "chs_adh_electrolyte"
    CB1_ANTAGONIST_BAT = "cb1_antagonist_bat"
    LIPID_PROFILE = "lipid_profile"
    GI_INCRETIN = "gi_incretin"
    DELIVERY_ROUTE_HPG = "delivery_route_hpg"


@dataclass(frozen=True)
class EndocrineCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class EndocrineRow:
    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[EndocrineCitation, ...]
    study_design: str = ""
    key_finding_summary: str = ""
    last_verified: str = "2026-06-02"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"endocrine row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"endocrine row {self.name!r} citation "
                    f"{c.label!r} must have a PMID or DOI"
                )
        if not self.watch_pmids:
            object.__setattr__(
                self,
                "watch_pmids",
                tuple(c.pmid for c in self.citations if c.pmid),
            )

    def to_claim(self) -> Claim:
        sources = tuple(
            Source(
                title=c.label,
                tier=self.source_tier,
                pmid=c.pmid,
                doi=c.doi,
                year=c.year,
            )
            for c in self.citations
        )
        return Claim(
            text=self.claim_text,
            claim_type=self.claim_type,
            sources=sources,
            disclosures_present=required_disclosures(self.claim_type),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "topic": self.topic,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type.value,
            "evidence_level": self.evidence_level.value,
            "source_tier": int(self.source_tier),
            "study_design": self.study_design,
            "key_finding_summary": self.key_finding_summary,
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_PENNER_2013 = EndocrineCitation(
    label="Penner EA, Buettner H, Mittleman MA, Am J Med 2013, the impact "
          "of marijuana use on glucose, insulin, and insulin resistance "
          "among US adults (NHANES 2005-2010 cross-sectional, n=4,657)",
    pmid="23684393", doi="10.1016/j.amjmed.2013.03.002", year=2013,
)
_VETTOR_2009 = EndocrineCitation(
    label="Vettor R, Pagano C, Best Pract Res Clin Endocrinol Metab 2009, "
          "the role of the endocannabinoid system in lipogenesis and fatty "
          "acid metabolism (adipocyte CB1 review)",
    pmid="19285260", doi="10.1016/j.beem.2008.10.002", year=2009,
)
_AKTURK_2019 = EndocrineCitation(
    label="Akturk HK et al., JAMA Internal Medicine 2019, association "
          "between cannabis use and risk for diabetic ketoacidosis in "
          "adults with type 1 diabetes (cross-sectional survey)",
    pmid="30398521", doi="10.1001/jamainternmed.2018.5142", year=2019,
)
_AKTURK_2022 = EndocrineCitation(
    label="Akturk HK et al., Diabetes Care 2022, differentiating diabetic "
          "ketoacidosis and hyperglycemic ketosis due to cannabis "
          "hyperemesis syndrome in adults with type 1 diabetes",
    pmid="34880067", doi="10.2337/dc21-1730", year=2022,
)
_BONNET_2013 = EndocrineCitation(
    label="Bonnet U, Pharmacopsychiatry 2013, chronic cannabis abuse, "
          "delta-9-tetrahydrocannabinol and thyroid function (n=39 "
          "in-patient detoxification cohort)",
    pmid="22821384", doi="10.1055/s-0032-1316342", year=2013,
)
_BROWN_DOBS_2002 = EndocrineCitation(
    label="Brown TT, Dobs AS, J Clin Pharmacol 2002, endocrine effects of "
          "marijuana (narrative review of the animal and human "
          "neuroendocrine literature)",
    pmid="12412841", doi="10.1002/j.1552-4604.2002.tb06008.x", year=2002,
)
_MURPHY_1998 = EndocrineCitation(
    label="Murphy LL et al., Neurobiol Dis 1998, function of cannabinoid "
          "receptors in the neuroendocrine regulation of hormone secretion "
          "(anterior-pituitary review)",
    pmid="9974176", doi="10.1006/nbdi.1998.0224", year=1998,
)
_PAYNE_2019 = EndocrineCitation(
    label="Payne KS, Mazur DJ, Hotaling JM, Pastuszak AW, J Urol 2019, "
          "cannabis and male fertility — a systematic review",
    pmid="30916627", doi="10.1097/JU.0000000000000248", year=2019,
)
_BELLADELLI_2022 = EndocrineCitation(
    label="Belladelli F et al., Andrology 2022, effects of recreational "
          "cannabis on testicular function in primary infertile men "
          "(n=2,074 cross-sectional)",
    pmid="35868833", doi="10.1111/andr.13235", year=2022,
)
_SMITH_ASCH_1984 = EndocrineCitation(
    label="Smith CG, Asch RH, NIDA Res Monogr 1984, acute, short-term, and "
          "chronic effects of marijuana on the female primate reproductive "
          "function",
    pmid="6090911", year=1984,
)
_WANG_DEY_2006 = EndocrineCitation(
    label="Wang H et al. (Dey SK lab), J Clin Invest 2006, fatty acid amide "
          "hydrolase deficiency limits early pregnancy events (mouse "
          "preimplantation / oviductal transport)",
    pmid="16886060", doi="10.1172/JCI28621", year=2006,
)
_MACCARRONE_2002 = EndocrineCitation(
    label="Maccarrone M et al., Mol Hum Reprod 2002, low fatty acid amide "
          "hydrolase and high anandamide levels are associated with failure "
          "to achieve an ongoing pregnancy after IVF and embryo transfer",
    pmid="11818522", doi="10.1093/molehr/8.2.188", year=2002,
)
_VAN_LEEUWEN_2011 = EndocrineCitation(
    label="van Leeuwen AP et al., Addiction 2011 (TRAILS), hypothalamic-"
          "pituitary-adrenal axis reactivity to social stress and "
          "adolescent cannabis use (n=591 prospective cohort)",
    pmid="21631618", doi="10.1111/j.1360-0443.2011.03448.x", year=2011,
)
_PETROWSKI_2019 = EndocrineCitation(
    label="Petrowski K, Conrad R, Psychopathology 2019, comparison of "
          "cortisol stress response in patients with panic disorder, "
          "cannabis-induced panic disorder, and healthy controls (small "
          "matched groups)",
    pmid="30879013", doi="10.1159/000496559", year=2019,
)
_LAZENKA_2012 = EndocrineCitation(
    label="Lazenka MF, Selley DE, Sim-Selley LJ, Life Sci 2012, brain "
          "regional differences in CB1 receptor adaptation and regulation "
          "of transcription (repeated Δ⁹-THC)",
    pmid="22940268", doi="10.1016/j.lfs.2012.08.023", year=2012,
)
_RUBINO_2005 = EndocrineCitation(
    label="Rubino T et al., J Neurochem 2005, Ras/ERK signalling in "
          "cannabinoid tolerance — CB1 receptor down-regulation and "
          "desensitization after subchronic Δ⁹-THC",
    pmid="15857401", doi="10.1111/j.1471-4159.2005.03101.x", year=2005,
)
_OFEK_2006 = EndocrineCitation(
    label="Ofek O et al. (Bab I, Zimmer A), PNAS 2006, peripheral "
          "cannabinoid receptor CB2 regulates bone mass (CB2-knockout and "
          "CB2-agonist mouse skeletal phenotype)",
    pmid="16407142", doi="10.1073/pnas.0504187103", year=2006,
)
_BAB_ZIMMER_2007 = EndocrineCitation(
    label="Bab I, Zimmer A, Br J Pharmacol 2007, cannabinoid receptors and "
          "the regulation of bone mass (review; CNR2 / BMD association)",
    pmid="18071301", doi="10.1038/sj.bjp.0707593", year=2007,
)


# ── Registry rows ──────────────────────────────────────────────────────

_METABOLIC_INSULIN = EndocrineRow(
    name="Cannabis use, fasting insulin & insulin resistance (Penner 2013 NHANES)",
    topic=EndocrineTopic.METABOLIC_INSULIN,
    claim_text=(
        "In the Penner et al. 2013 (Am J Med) analysis of NHANES 2005-2010 "
        "(n=4,657 adults; 579 current users), current cannabis use was "
        "cross-sectionally associated with ~16% lower fasting insulin "
        "(95% CI -26 to -6), ~17% lower HOMA-IR (95% CI -27 to -6), and "
        "smaller waist circumference, after multivariable adjustment. The "
        "direction is paradoxical given that acute Δ⁹-THC stimulates "
        "appetite, and is the most-cited human signal linking cannabis to "
        "peripheral insulin sensitivity. Critically, this is a CROSS-"
        "SECTIONAL association: it cannot establish that cannabis improves "
        "insulin sensitivity, no dose-response was seen among current "
        "users, reverse causation and residual confounding (diet, "
        "adiposity, activity) are unexcluded, and there is no dedicated "
        "trial in diagnosed metabolic-syndrome patients. Fasting glucose "
        "itself is largely unchanged across most surveys; the signal is "
        "carried by insulin / HOMA-IR, not glucose."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_PENNER_2013,),
    study_design="cross-sectional survey (NHANES 2005-2010, n=4,657)",
    key_finding_summary=(
        "Current use associated with ~16-17% lower fasting insulin / "
        "HOMA-IR and smaller waist; cross-sectional, no dose-response"
    ),
    key_notes=(
        "Cross-sectional NHANES data cannot separate a true metabolic "
        "effect of cannabinoids from confounding by leanness, diet, or "
        "lifestyle — the association is hypothesis-generating, not "
        "causal.",
        "Fasting glucose is typically NOT significantly altered; the "
        "metabolic signal in the literature is on fasting insulin and "
        "HOMA-IR, so 'fasting glucose levels' is the weaker half of the "
        "question.",
        "No randomized or prospective trial has tested chronic cannabis "
        "on insulin sensitivity specifically within a metabolic-syndrome "
        "cohort; that gap is the honest limit of the evidence.",
    ),
)


_ADIPOGENESIS_LEPTIN = EndocrineRow(
    name="CB1 activation, adipogenesis & the leptin feedback loop (Vettor 2009)",
    topic=EndocrineTopic.ADIPOGENESIS_LEPTIN,
    claim_text=(
        "Mechanistically, CB1 cannabinoid receptors (UniProt P21554; HGNC "
        "CNR1) are expressed on adipocytes, and their activation — by "
        "endocannabinoids or by Δ⁹-THC — stimulates lipoprotein-lipase "
        "activity, glucose uptake, lipogenesis and adipocyte "
        "differentiation (adipogenesis), effects blocked by the CB1 "
        "inverse agonist rimonabant (Vettor & Pagano 2009 review). Leptin "
        "is the key feedback signal: leptin normally suppresses "
        "hypothalamic endocannabinoid tone, and defective leptin signalling "
        "raises endocannabinoid levels, so obesity tends to co-occur with an "
        "over-active peripheral endocannabinoid system. Ghrelin, the "
        "orexigenic gut hormone, interacts with CB1 signalling in the "
        "hypothalamus to drive the appetite ('munchies') response, and CB1 "
        "blockade lowers ghrelin — but the ghrelin arm is less firmly "
        "characterized than the leptin arm. This is mechanistic evidence, "
        "predominantly rodent and in-vitro; it describes a plausible "
        "adipogenic pathway, not a demonstrated clinical outcome in humans."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_VETTOR_2009,),
    study_design="mechanistic review (rodent + in-vitro adipocyte biology)",
    key_finding_summary=(
        "Adipocyte CB1 (P21554) activation promotes lipogenesis / "
        "adipogenesis; leptin suppresses endocannabinoid tone; ghrelin arm "
        "less established"
    ),
    key_notes=(
        "The adipogenic CB1 mechanism is well-characterized in rodents "
        "and cell lines; extrapolating it to chronic human cannabis "
        "exposure (where tolerance and route matter) is not direct "
        "evidence of net human fat-mass effect — indeed users tend to be "
        "leaner cross-sectionally.",
        "The leptin → endocannabinoid feedback link (Di Marzo and "
        "colleagues) is more firmly established than the ghrelin link; "
        "state the ghrelin interaction as a plausible, less-anchored "
        "mechanism rather than a settled fact.",
    ),
)


_DIABETIC_KETOACIDOSIS = EndocrineRow(
    name="Cannabis use & diabetic ketoacidosis risk in type 1 diabetes (Akturk)",
    topic=EndocrineTopic.DIABETIC_KETOACIDOSIS,
    claim_text=(
        "Akturk et al. 2019 (JAMA Internal Medicine), a cross-sectional "
        "survey of adults with type 1 diabetes, reported that cannabis "
        "users had a substantially higher prevalence of diabetic "
        "ketoacidosis (DKA) than non-users (roughly a doubling of the odds "
        "in adjusted models). The proposed mechanism is that cannabis can "
        "promote ketosis / gastrointestinal effects and reduce self-care "
        "adherence. The association reaches conventional statistical "
        "significance, but the design is cross-sectional and self-reported, "
        "so it shows correlation, not causation. The same group's 2022 "
        "(Diabetes Care) follow-up is essential nuance: some apparent 'DKA' "
        "in cannabis users is actually hyperglycemic ketosis from "
        "cannabinoid hyperemesis syndrome (HK-CHS), which presents at much "
        "higher pH (7.42 vs 7.09) and bicarbonate (19.2 vs 9.1 mmol/L) than "
        "true DKA — meaning crude event counts can over- or mis-classify "
        "the endpoint. Net: there is a statistically significant "
        "association, of modest-to-moderate size, from observational data."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_AKTURK_2019, _AKTURK_2022),
    study_design="cross-sectional survey + ketosis-phenotype differentiation study",
    key_finding_summary=(
        "Cannabis use associated with ~2× higher DKA odds in adults with "
        "T1D (observational); some events are HK-CHS, not true DKA"
    ),
    key_notes=(
        "The association is statistically significant but cross-sectional "
        "and self-reported — confounding by overall risk behaviour and "
        "adherence is plausible, and no randomized evidence exists.",
        "The 2022 differentiation study matters for accuracy: cannabinoid "
        "hyperemesis can masquerade as DKA, so the magnitude of the true-"
        "DKA association may be partly inflated by mis-classification.",
        "Evidence is in adults; pediatric / adolescent T1D DKA-and-"
        "cannabis data are sparser still.",
    ),
)


_THYROID_HPT = EndocrineRow(
    name="Phytocannabinoids & the HPT axis — TSH / T3 / free-T4 (Bonnet 2013)",
    topic=EndocrineTopic.THYROID_HPT,
    claim_text=(
        "Human data on cannabis and the hypothalamic-pituitary-thyroid "
        "(HPT) axis are sparse, and the best dedicated human study is "
        "reassuringly null: Bonnet 2013 (Pharmacopsychiatry) measured TSH, "
        "total T3 and free T4 in 39 chronic cannabis-dependent patients at "
        "detoxification admission and found all values within the "
        "population reference range, with NO significant correlation "
        "between thyroid-hormone levels and serum Δ⁹-THC, 11-OH-THC or "
        "THC-COOH — arguing against a clinically relevant effect of chronic "
        "cannabis on human thyroid function. This contrasts with animal / "
        "neuroendocrine work (Brown & Dobs 2002; Murphy 1998) showing that "
        "acute cannabinoid exposure can suppress thyrotropin (TSH) release "
        "via hypothalamic CB1 (UniProt P21554; HGNC CNR1) signalling and "
        "lower circulating thyroid "
        "hormone in rodents. The species discrepancy is usually attributed "
        "to tolerance with chronic human use. Bottom line: phytocannabinoids "
        "can acutely suppress the HPT axis in animals, but the limited "
        "human evidence does not show meaningful TSH / free-T3 / free-T4 "
        "shifts in chronic users."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_BONNET_2013, _BROWN_DOBS_2002, _MURPHY_1998),
    study_design="small human cohort (null) + animal/neuroendocrine reviews",
    key_finding_summary=(
        "One human cohort: TSH/T3/free-T4 within range, no THC correlation; "
        "animal data show acute TSH suppression (tolerance with chronic use)"
    ),
    key_notes=(
        "The single human study (n=39) is small and is a detox-population "
        "snapshot, so 'no effect' is a low-certainty conclusion — but it "
        "is the most direct human evidence and it is negative.",
        "Most 'cannabis lowers thyroid hormone' statements trace to rodent "
        "acute-dosing work; do not present the animal TSH-suppression "
        "finding as if it were an established human effect.",
    ),
)


_GROWTH_HORMONE_PROLACTIN = EndocrineRow(
    name="Acute THC on growth hormone & prolactin; the adolescent data gap",
    topic=EndocrineTopic.GROWTH_HORMONE_PROLACTIN,
    claim_text=(
        "In animal models, acute Δ⁹-THC suppresses both growth-hormone (GH) "
        "and prolactin secretion through hypothalamic CB1 (UniProt P21554; "
        "HGNC CNR1) modulation of the anterior pituitary (Murphy 1998; "
        "Brown & Dobs 2002). In humans the picture is inconsistent: acute "
        "cannabis can transiently lower GH and can either lower or not "
        "change prolactin, and chronic exposure attenuates these responses "
        "as tolerance develops, so reported effects are small and "
        "variable. The specific comparison the question asks for — acute "
        "THC ingestion in ADOLESCENTS versus ADULTS — has essentially NO "
        "direct controlled human evidence, because deliberately dosing "
        "minors with THC is ethically prohibited; adolescent inferences "
        "rest on animal pubertal-exposure models, which suggest the "
        "developing neuroendocrine axis is more vulnerable. Any claim of a "
        "quantified adolescent-versus-adult difference in GH / prolactin "
        "response to THC would therefore be unsupported by primary human "
        "data and should be flagged as a genuine evidence gap."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_BROWN_DOBS_2002, _MURPHY_1998),
    study_design="animal/neuroendocrine reviews; no controlled adolescent human data",
    key_finding_summary=(
        "Acute cannabinoid suppresses GH & prolactin in animals; human data "
        "inconsistent; NO controlled adolescent-vs-adult human evidence"
    ),
    key_notes=(
        "The honest core of this answer is the gap: there is no ethical "
        "controlled adolescent THC-challenge study, so an adolescent-vs-"
        "adult GH/prolactin contrast cannot be quantified from human data.",
        "Adult human prolactin responses to cannabis are inconsistent "
        "across studies; do not assert a uniform direction.",
    ),
)


_GONADAL_HPG = EndocrineRow(
    name="Chronic high-potency THC & the HPG axis (Payne SR + Belladelli + Smith)",
    topic=EndocrineTopic.GONADAL_HPG,
    claim_text=(
        "Cannabinoids suppress the hypothalamic-pituitary-gonadal (HPG) "
        "axis most clearly in animals: Δ⁹-THC lowers GnRH-driven LH and FSH "
        "release, reducing gonadal steroid output and disrupting ovulation "
        "and spermatogenesis, with effects that are reversible on cessation "
        "and subject to tolerance (Smith & Asch 1984 primate). In men, the "
        "human evidence is mixed: a systematic review (Payne 2019, J Urol) "
        "found lowered LH and inconsistent / inconclusive testosterone "
        "changes alongside reduced semen parameters, while a large "
        "infertility cohort (Belladelli 2022, n=2,074) found cannabis use "
        "independently associated with LOWER total testosterone "
        "(β ≈ -0.37 ng/mL) but NOT with FSH or LH. In women, chronic use is "
        "linked, in observational and animal data, to disrupted menstrual "
        "cyclicity and altered estrogen / progesterone dynamics, "
        "but human female endocrine datasets are smaller and less "
        "consistent. So: directionally the HPG axis is suppressed / "
        "dysregulated, but the human testosterone literature is "
        "inconsistent and the female-axis evidence is thinner — this is "
        "low-certainty, observational-plus-preclinical evidence, not a "
        "settled dose-response."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_PAYNE_2019, _BELLADELLI_2022, _SMITH_ASCH_1984),
    study_design="systematic review + large infertility cohort + primate model",
    key_finding_summary=(
        "Animal: clear LH/FSH/testosterone suppression. Human men: lowered "
        "LH, inconsistent testosterone. Women: thinner, less consistent data"
    ),
    key_notes=(
        "Human male testosterone findings genuinely conflict across "
        "studies (some show lower, some no change, a few slightly higher) — "
        "present this as inconsistent, not as a uniform suppression.",
        "Female HPG-axis data (estrogen/progesterone, cycle disruption) "
        "are dominated by older or animal work; the female half of the "
        "question is the weaker-evidenced half.",
        "'High-potency' specificity is largely unstudied — most cohorts "
        "did not quantify product THC concentration, so a potency dose-"
        "response cannot be asserted.",
    ),
)


_EMBRYO_IMPLANTATION = EndocrineRow(
    name="Endocannabinoid 'anandamide tone' gates embryo implantation (Wang/Dey + Maccarrone)",
    topic=EndocrineTopic.EMBRYO_IMPLANTATION,
    claim_text=(
        "Embryo implantation depends on a tightly-regulated local "
        "anandamide (AEA) 'tone', set by the balance of AEA synthesis "
        "(NAPE-PLD) and degradation (FAAH) and signalling through CB1 "
        "(UniProt P21554; HGNC CNR1). In mice, FAAH deficiency — or "
        "experimentally raised cannabinoid levels, including (-)-Δ⁹-THC — "
        "elevates AEA and constrains preimplantation embryo development and "
        "oviductal transport, deferring on-time implantation and worsening "
        "pregnancy outcome (Wang/Dey 2006, J Clin Invest). In humans, "
        "Maccarrone 2002 found that women who failed to achieve an ongoing "
        "pregnancy after IVF/embryo transfer had significantly LOWER "
        "lymphocyte FAAH activity and HIGHER blood AEA than those who "
        "conceived. Both too-high and too-low AEA are detrimental, so the "
        "relationship is a narrow optimal window rather than 'more "
        "endocannabinoid is worse'. Exogenous phytocannabinoid exposure "
        "(Δ⁹-THC) is expected to perturb this window, which is the "
        "mechanistic basis for cannabis being discouraged peri-conception — "
        "though the direct human exposure-outcome trials do not exist."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_WANG_DEY_2006, _MACCARRONE_2002),
    study_design="mouse genetic/mechanistic model + human IVF biomarker study",
    key_finding_summary=(
        "FAAH-set anandamide tone gates implantation; high AEA / low FAAH "
        "(mouse) and high AEA (human IVF) track implantation failure"
    ),
    key_notes=(
        "The biology is a U-shaped optimum: implantation needs AEA neither "
        "too high nor too low. State it as a regulated window, not a "
        "monotonic 'endocannabinoids disrupt implantation'.",
        "Human evidence (Maccarrone) is an association between a blood/"
        "lymphocyte biomarker and IVF outcome — it is not a cannabis-"
        "exposure trial, so the leap to 'cannabis use disrupts human "
        "implantation' is mechanistically motivated but not directly "
        "demonstrated.",
    ),
)


_ADRENAL_HPA = EndocrineRow(
    name="Cannabis, the HPA axis & blunted cortisol stress/awakening response",
    topic=EndocrineTopic.ADRENAL_HPA,
    claim_text=(
        "Acute Δ⁹-THC activates the hypothalamic-pituitary-adrenal (HPA) "
        "axis, transiently raising ACTH and cortisol (Brown & Dobs 2002), "
        "whereas CHRONIC / continuous use blunts HPA reactivity. In the "
        "prospective adolescent TRAILS cohort (van Leeuwen 2011, n=591), "
        "lifetime and repeated cannabis users showed significantly LOWER "
        "cortisol responses to a standardized social-stress task "
        "(OR ≈ 0.68, 95% CI 0.55-0.85) than abstainers — i.e. a blunted, "
        "hyporesponsive axis. A small clinical study (Petrowski 2019) "
        "similarly found cortisol hyporesponsiveness in cannabis-induced "
        "panic disorder. This blunting of dynamic HPA output is the same "
        "phenomenon that flattens the cortisol awakening response (CAR) in "
        "regular users. The interaction with chronic anxiety is "
        "bidirectional and confounded — anxiety disorders themselves alter "
        "HPA tone — so the cannabis-specific contribution cannot be cleanly "
        "isolated from observational data. Direction of travel: chronic "
        "cannabis use may be associated with a blunted cortisol stress "
        "response and a dampened CAR, on low-certainty observational evidence."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_VAN_LEEUWEN_2011, _PETROWSKI_2019, _BROWN_DOBS_2002),
    study_design="prospective cohort + small clinical study + neuroendocrine review",
    key_finding_summary=(
        "Acute Δ⁹-THC raises cortisol; chronic use blunts cortisol stress "
        "reactivity and the CAR (OR≈0.68 in adolescents)"
    ),
    key_notes=(
        "Acute vs chronic is the crux: a single dose RAISES cortisol while "
        "habitual use BLUNTS the dynamic response — conflating the two is "
        "a common error.",
        "In a chronic-anxiety population the HPA changes are confounded by "
        "the anxiety disorder itself; observational data cannot attribute "
        "the blunting solely to cannabis.",
        "Direct cortisol-awakening-response measurements specifically in "
        "diagnosed chronic-anxiety cannabis users are sparse; the CAR "
        "inference is extrapolated from broader stress-reactivity data.",
    ),
)


_RECEPTOR_DESENSITIZATION = EndocrineRow(
    name="THC-driven CB1 desensitization / downregulation; the THC:CBD-ratio & endocrine-tissue gap",
    topic=EndocrineTopic.RECEPTOR_DESENSITIZATION,
    claim_text=(
        "Repeated Δ⁹-THC drives homologous desensitization and "
        "downregulation of CB1 receptors (UniProt P21554; HGNC CNR1) — "
        "GRK/β-arrestin-mediated uncoupling from G-protein signalling "
        "(measured as reduced agonist-stimulated [35S]GTPγS binding) "
        "followed by receptor internalization and loss of binding sites. "
        "This adaptation is region-specific in brain: it is pronounced in "
        "hippocampus and cerebellum but blunted in striatum, and is gated "
        "by Ras/ERK signalling (Lazenka 2012; Rubino 2005). CB2 receptors "
        "(UniProt P34972; HGNC CNR2) desensitize/internalize on a different "
        "schedule. CBD is not a simple CB1 agonist — it behaves as a "
        "negative allosteric modulator of CB1 and can modestly temper THC's "
        "CB1 effects — so THC:CBD ratio plausibly shifts the tolerance "
        "trajectory. However, two honest gaps dominate: (1) the "
        "quantitative, ratio-resolved trafficking data are characterized in "
        "neurons and transfected cell lines, NOT in ENDOCRINE tissue "
        "specifically; and (2) there is no controlled human dataset mapping "
        "THC:CBD ratio to CB1/CB2 internalization in pituitary, gonad, "
        "adipose or adrenal tissue. The mechanism is real; the endocrine-"
        "tissue, ratio-specific claim is extrapolation."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_LAZENKA_2012, _RUBINO_2005),
    study_design="rodent CNS receptor-trafficking / tolerance mechanism studies",
    key_finding_summary=(
        "Repeated Δ⁹-THC → region-specific CB1 (P21554) desensitization & "
        "downregulation; endocrine-tissue & THC:CBD-ratio specificity unstudied"
    ),
    key_notes=(
        "Desensitization data are overwhelmingly CNS (and cell-line); "
        "applying them to 'endocrine tissues' is a reasonable mechanistic "
        "extrapolation but not a directly measured result.",
        "CBD's CB1 negative-allosteric-modulator behaviour motivates a "
        "ratio effect, but no study quantifies CB1/CB2 internalization as "
        "a function of THC:CBD ratio in endocrine tissue — flag this as an "
        "open question, not a known dose-ratio response.",
    ),
)


_BONE_REMODELING = EndocrineRow(
    name="Cannabinoid receptors regulate bone — osteoblasts, osteoclasts & BMD (Ofek + Bab)",
    topic=EndocrineTopic.BONE_REMODELING,
    claim_text=(
        "The skeleton is a genuine physiological target of the "
        "endocannabinoid system. CB2 receptors (UniProt P34972; HGNC CNR2) "
        "are expressed on osteoblasts, osteocytes and osteoclasts: CB2-"
        "knockout mice develop accelerated age-related trabecular bone loss "
        "resembling osteoporosis, while a non-psychoactive CB2-selective "
        "agonist increases osteoblast number/activity, restrains "
        "osteoclastogenesis (partly via RANKL), and attenuates ovariectomy-"
        "induced bone loss (Ofek 2006, PNAS). CB1 receptors (UniProt "
        "P21554; HGNC CNR1) act mainly in sympathetic nerve terminals in "
        "bone, where they tonically modulate the adrenergic restraint of "
        "bone formation, and CB1-null skeletal phenotypes are strain- and "
        "sex-dependent (Bab & Zimmer 2007). In humans, CNR2 gene "
        "polymorphisms may be linked to low bone mineral density, and "
        "heavy cannabis use has been linked to lower BMD in observational "
        "data. Net effect is therefore receptor- and context-dependent: "
        "CB2 signalling is broadly bone-PROTECTIVE (a drug target for "
        "osteoporosis), while heavy exogenous Δ⁹-THC exposure may be "
        "linked to lower BMD — on predominantly preclinical evidence "
        "plus human genetic-association data."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_OFEK_2006, _BAB_ZIMMER_2007),
    study_design="mouse knockout/agonist skeletal models + human CNR2/BMD association review",
    key_finding_summary=(
        "CB2 (P34972) is bone-protective (KO→loss, agonist→gain); CB1 "
        "(P21554) modulates via sympathetic tone; human CNR2 variants & "
        "heavy use track lower BMD"
    ),
    key_notes=(
        "Distinguish the two receptors: CB2 activation is osteoprotective "
        "(an anti-osteoporosis target), whereas the net effect of HEAVY "
        "cannabis (high Δ⁹-THC) in humans trends toward lower BMD — these "
        "are not contradictory once receptor and exposure are specified.",
        "Human bone evidence is genetic-association and observational; the "
        "causal, dose-resolved human BMD effect of cannabis is not "
        "established by trial data.",
    ),
)


# ══════════════════════════════════════════════════════════════════════
# Spec 027 — second endocrine question wave (autoimmune thyroiditis, β-cell
# survival, prenatal neuroendocrine programming, melatonin/circadian, CBD-
# vs-full-spectrum cortisol, CHS-ADH/electrolytes, CB1-antagonist/BAT-UCP1,
# lipid profile, GI incretins, delivery-route → HPG). Same honesty bar: the
# grader caps each at Level C, and three of these (autoimmune thyroiditis,
# CHS→ADH, delivery-route→HPG) are HONEST-GAP rows — the curated answer is
# "no direct evidence; here is the mechanistic plausibility / indirect data"
# rather than a confidently-wrong off-target match.
# ══════════════════════════════════════════════════════════════════════

_NAGARKATTI_2009 = EndocrineCitation(
    label="Nagarkatti P, Pandey R, Rieder SA, Hegde VL, Nagarkatti M, Future "
          "Med Chem 2009, cannabinoids as novel anti-inflammatory drugs "
          "(CB2 immunomodulation / autoimmune-disease review)",
    pmid="20191092", doi="10.4155/fmc.09.93", year=2009,
)
_GONZALEZ_MARISCAL_2021 = EndocrineCitation(
    label="González-Mariscal I et al., Biomed Pharmacother 2021, abnormal "
          "cannabidiol (Abn-CBD) ameliorates inflammation preserving "
          "pancreatic beta cells in mouse models of experimental type 1 "
          "diabetes and beta-cell damage (NOD + STZ mice)",
    pmid="34872800", doi="10.1016/j.biopha.2021.112361", year=2021,
)
_FRAU_MELIS_2023 = EndocrineCitation(
    label="Frau R, Melis M, J Neuroendocrinol 2023, sex-specific "
          "susceptibility to psychotic-like states provoked by prenatal THC "
          "exposure — mesolimbic dopamine, reversal by pregnenolone (review "
          "of preclinical prenatal-cannabis neuroendocrine programming)",
    pmid="36810840", doi="10.1111/jne.13240", year=2023,
)
_RIED_2022 = EndocrineCitation(
    label="Ried K, Tamanna T, Matthews S, Sali A, J Sleep Res 2022, "
          "medicinal cannabis (THC 10 mg/mL + CBD 15 mg/mL oil) improves "
          "sleep in adults with insomnia — randomised double-blind placebo-"
          "controlled crossover (n=29), midnight salivary melatonin endpoint",
    pmid="36539991", doi="10.1111/jsr.13793", year=2022,
)
_APPIAH_KUSI_2020 = EndocrineCitation(
    label="Appiah-Kusi E et al., Psychopharmacology 2020, effects of short-"
          "term cannabidiol (600 mg/day) on response to social stress (TSST) "
          "in subjects at clinical high risk of psychosis — RCT, serum "
          "cortisol endpoint",
    pmid="31915861", doi="10.1007/s00213-019-05442-6", year=2020,
)
_DAVIES_2021 = EndocrineCitation(
    label="Davies C et al., Eur Arch Psychiatry Clin Neurosci 2021, altered "
          "relationship between cortisol response to social stress and "
          "mediotemporal function — exploratory cannabidiol RCT arm",
    pmid="34480630", doi="10.1007/s00406-021-01318-z", year=2021,
)
_VERTY_2008 = EndocrineCitation(
    label="Verty ANA, Allen AM, Oldfield BJ, Obesity (Silver Spring) 2008, "
          "the effects of rimonabant (CB1 antagonist) on brown adipose "
          "tissue in rat — BAT thermogenesis and UCP1, CNS-mediated",
    pmid="19057531", doi="10.1038/oby.2008.509", year=2008,
)
_REIMANN_GRIBBLE_2016 = EndocrineCitation(
    label="Reimann F, Gribble FM, J Diabetes Investig 2016, mechanisms "
          "underlying glucose-dependent insulinotropic polypeptide (GIP) and "
          "glucagon-like peptide-1 (GLP-1) secretion (enteroendocrine review; "
          "CB1 agonists selectively inhibit GIP)",
    pmid="27186350", doi="10.1111/jdi.12478", year=2016,
)
_MHALLA_2018 = EndocrineCitation(
    label="Mhalla A et al., Tunis Med 2018, lipid profile in schizophrenia — "
          "case-control study in which cannabis consumption was associated "
          "with significantly lower triglycerides (secondary, confounded "
          "finding)",
    pmid="30324988", year=2018,
)
_SORENSEN_2017 = EndocrineCitation(
    label="Sorensen CJ et al., J Med Toxicol 2017, cannabinoid hyperemesis "
          "syndrome — diagnosis, pathophysiology, and treatment (systematic "
          "review of 64 case series)",
    pmid="28000146", doi="10.1007/s13181-016-0595-z", year=2017,
)
_VENKATESAN_2019 = EndocrineCitation(
    label="Venkatesan T et al., Neurogastroenterol Motil 2019, ACG/CAPS "
          "consensus on cannabinoid hyperemesis syndrome within the cyclic-"
          "vomiting-syndrome spectrum",
    pmid="31241819", doi="10.1111/nmo.13604", year=2019,
)


_AUTOIMMUNE_THYROIDITIS = EndocrineRow(
    name="Cannabis & autoimmune thyroiditis (Hashimoto's) — an honest evidence gap",
    topic=EndocrineTopic.AUTOIMMUNE_THYROIDITIS,
    claim_text=(
        "There is essentially NO direct human (or animal) evidence on whether "
        "cannabis use changes the onset age or clinical progression of "
        "autoimmune thyroiditis (Hashimoto's disease) specifically — a "
        "targeted literature search returns no dedicated study, so any "
        "quantified claim about Hashimoto's onset/progression would be "
        "unsupported. What CAN be said is mechanistic and indirect: "
        "cannabinoids are broadly immunomodulatory — CB2 (UniProt P34972; "
        "HGNC CNR2) is expressed on immune cells, and Δ⁹-THC can trigger "
        "T-cell and dendritic-cell apoptosis, downregulate pro-inflammatory "
        "cytokines, and upregulate regulatory T cells, an largely "
        "immunosuppressive / anti-inflammatory profile (Nagarkatti 2009 "
        "review). That profile makes a modulatory effect on an organ-specific "
        "autoimmune process such as Hashimoto's biologically plausible "
        "(potentially dampening autoimmune attack), but plausibility is not "
        "evidence: direction, magnitude, onset-age and progression effects in "
        "thyroid autoimmunity are unstudied and must be flagged as a genuine "
        "research gap, not inferred from the general immunology."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_NAGARKATTI_2009,),
    study_design="no disease-specific study; general CB2 immunomodulation review",
    key_finding_summary=(
        "No direct Hashimoto's data; cannabinoids are broadly "
        "immunosuppressive (CB2), making a modulatory effect plausible but "
        "unproven"
    ),
    key_notes=(
        "This is an HONEST-GAP row: the correct answer to the Hashimoto's "
        "question is 'not directly studied', not a number — do not let a "
        "generic thyroid-function answer stand in for the autoimmune "
        "question.",
        "General immunosuppression does not predict a specific autoimmune-"
        "thyroiditis outcome; organ-specific autoimmunity can respond "
        "differently from the systemic models Nagarkatti reviews.",
    ),
)


_BETA_CELL_SURVIVAL = EndocrineRow(
    name="Cannabinoids & pancreatic β-cell apoptosis under cytokine stress (González-Mariscal 2021)",
    topic=EndocrineTopic.BETA_CELL_SURVIVAL,
    claim_text=(
        "In preclinical models, certain cannabinoids appear β-cell-protective "
        "rather than toxic under inflammatory stress. González-Mariscal 2021 "
        "showed that abnormal cannabidiol (Abn-CBD, an atypical synthetic "
        "cannabinoid) reduced the severity of insulitis, lowered circulating "
        "and intra-islet pro-inflammatory cytokines, decreased intra-islet "
        "phospho-NF-κB and TXNIP, shifted the CD4/CD8 T-cell profile away "
        "from pro-inflammatory, and significantly reduced islet-cell "
        "apoptosis while improving glucose tolerance in NOD mice and "
        "streptozotocin-challenged mice. Mechanistically this fits the wider "
        "picture that endocannabinoid-system tone modulates cytokine-driven "
        "β-cell death (CB1 (UniProt P21554; HGNC CNR1) signalling tends to be "
        "pro-apoptotic/pro-inflammatory in islets, whereas CB2 (UniProt "
        "P34972; HGNC CNR2) and atypical-cannabinoid signalling tend to be "
        "protective). All of this is rodent / cell-level evidence with a "
        "synthetic cannabinoid; it does NOT establish that smoked or ingested "
        "cannabis protects human β-cells, and Δ⁹-THC's net islet effect is "
        "less favourable than Abn-CBD's."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_GONZALEZ_MARISCAL_2021,),
    study_design="mouse models (NOD autoimmune + STZ β-cell damage)",
    key_finding_summary=(
        "Abn-CBD reduced insulitis, islet cytokines and β-cell apoptosis "
        "(mouse); CB2/atypical protective vs CB1 pro-apoptotic in islets"
    ),
    key_notes=(
        "The protective signal is for a synthetic atypical cannabinoid "
        "(Abn-CBD) in mice — not a green light for Δ⁹-THC or human cannabis; "
        "CB1 activation is generally pro-apoptotic in islets.",
        "No human trial has tested any cannabinoid for β-cell preservation; "
        "this is early-stage target-validation evidence.",
    ),
)


_PRENATAL_NEUROENDOCRINE = EndocrineRow(
    name="Maternal cannabis, fetal endocannabinoid tone & offspring neuroendocrine development (Frau & Melis 2023)",
    topic=EndocrineTopic.PRENATAL_NEUROENDOCRINE,
    claim_text=(
        "The endocannabinoid system has a well-characterised instructive role "
        "in fetal neurodevelopment — CB1 (UniProt P21554; HGNC CNR1) "
        "signalling guides "
        "neural progenitor proliferation, migration and axon guidance — so "
        "exogenous Δ⁹-THC crossing the placenta perturbs a developmentally "
        "instructive signal at a sensitive window. In preclinical models, "
        "prenatal THC exposure deranges mesolimbic dopamine-system "
        "development and predisposes offspring to schizophrenia-relevant, "
        "psychotic-like endophenotypes that emerge specifically on a 'second "
        "hit' (stress or adolescent THC); the effect is sex-specific (male "
        "offspring more affected) and is normalised by the neurosteroid "
        "pregnenolone (Frau & Melis 2023). Human longitudinal cohorts "
        "corroborate heightened psychopathology risk after maternal cannabis "
        "use. Net: maternal cannabis lowers/disorders fetal endocannabinoid "
        "tone and reprograms dopaminergic (and HPA/stress) neuroendocrine "
        "trajectories in offspring — robust in animals, supported but "
        "confounded in human observational data, and not quantifiable as a "
        "dose-response from controlled human trials (which are ethically "
        "impossible)."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_FRAU_MELIS_2023,),
    study_design="preclinical review (prenatal-THC rodent models) + human longitudinal context",
    key_finding_summary=(
        "Prenatal Δ⁹-THC disorders fetal ECS-guided mesolimbic dopamine "
        "development → sex-specific psychotic-like phenotypes on a second hit "
        "(animal); pregnenolone reverses"
    ),
    key_notes=(
        "Human evidence is observational and confounded (polysubstance use, "
        "socioeconomics); the mechanistic causal detail comes from animal "
        "models.",
        "Effects are most evident as latent vulnerability unmasked by later "
        "stress or THC, not as an unconditional deficit — and are sex-"
        "specific.",
    ),
)


_MELATONIN_CIRCADIAN = EndocrineRow(
    name="Cannabis, melatonin secretion & circadian/metabolic rhythm (Ried 2022 RCT)",
    topic=EndocrineTopic.MELATONIN_CIRCADIAN,
    claim_text=(
        "Direct human data are limited but suggestive. In a randomised "
        "double-blind placebo-controlled crossover trial in adults with "
        "insomnia (Ried 2022, n=29), a Δ⁹-THC (10 mg/mL) + CBD (15 mg/mL) oil "
        "raised midnight salivary melatonin by ~30% versus a ~20% decline on "
        "placebo (p=0.035), alongside improved sleep — i.e. cannabis "
        "constituents can acutely shift the melatonin rhythm upward. Older "
        "human work likewise reported that smoked Δ⁹-THC could increase "
        "nocturnal plasma melatonin. This contrasts with the broader concern "
        "that chronic, late-night use can disrupt circadian timing and, via "
        "CB1 (UniProt P21554; HGNC CNR1) effects on the suprachiasmatic clock "
        "and on appetite/energy-balance circuits, degrade glucose handling "
        "and weight regulation. The "
        "evidence is a small RCT plus mechanistic inference: a single short "
        "trial cannot establish chronic circadian or metabolic consequences, "
        "and effects likely depend on dose, timing, THC:CBD ratio and "
        "tolerance."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_RIED_2022,),
    study_design="small randomised double-blind placebo-controlled crossover (n=29)",
    key_finding_summary=(
        "One small RCT: THC+CBD oil raised midnight melatonin ~30% vs placebo "
        "(p=0.035); chronic circadian/metabolic effects not established"
    ),
    key_notes=(
        "A single small crossover RCT on an insomnia population does not "
        "generalise to chronic-use circadian disruption — the long-term and "
        "metabolic limb of the question is mechanistic inference, not data.",
        "Acute melatonin elevation (sleep aid) and chronic circadian "
        "disruption are not contradictory: timing and chronicity matter.",
    ),
)


_CBD_FULLSPECTRUM_CORTISOL = EndocrineRow(
    name="Isolated CBD vs full-spectrum extract on the acute cortisol stress response (Appiah-Kusi 2020)",
    topic=EndocrineTopic.CBD_FULLSPECTRUM_CORTISOL,
    claim_text=(
        "Isolated CBD has direct human evidence of blunting the acute "
        "cortisol stress response: in an RCT using the Trier Social Stress "
        "Test, 600 mg/day CBD for one week produced an intermediate cortisol "
        "reactivity between healthy controls and placebo-treated clinical-"
        "high-risk patients (Appiah-Kusi 2020; companion analysis Davies "
        "2021), and earlier work (Zuardi and colleagues) showed CBD "
        "attenuates cortisol. The specific head-to-head the question asks — "
        "isolated CBD VERSUS full-spectrum hemp extract on cortisol during "
        "acute stress testing — has NOT been done: no controlled study "
        "compares an isolate to a matched full-spectrum extract at equivalent "
        "CBD dose on a cortisol endpoint. The 'entourage' rationale (minor "
        "cannabinoids/terpenes modifying the response) is a hypothesis, and "
        "any full-spectrum residual Δ⁹-THC would, if anything, tend to RAISE "
        "acute cortisol (opposing CBD), so the net direction of a full-"
        "spectrum extract is not predictable from the isolate data. Clinical "
        "superiority of full-spectrum over isolate for cortisol is unproven."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_APPIAH_KUSI_2020, _DAVIES_2021),
    study_design="CBD RCTs (TSST cortisol); no isolate-vs-full-spectrum head-to-head",
    key_finding_summary=(
        "Isolated CBD (600 mg) blunts/normalises TSST cortisol (RCT); no "
        "controlled isolate-vs-full-spectrum comparison exists"
    ),
    key_notes=(
        "The comparative half of the question is unstudied — do not assert a "
        "full-spectrum advantage; full-spectrum THC could oppose CBD's "
        "cortisol-lowering.",
        "CBD cortisol RCTs are in clinical-high-risk / anxiety samples, not "
        "healthy general population — generalisability is limited.",
    ),
)


_CHS_ADH_ELECTROLYTE = EndocrineRow(
    name="Cannabinoid hyperemesis syndrome, ADH & electrolytes — secondary, not a primary endocrine effect",
    topic=EndocrineTopic.CHS_ADH_ELECTROLYTE,
    claim_text=(
        "Cannabinoid hyperemesis syndrome (CHS) — cyclic severe vomiting in "
        "chronic cannabis users, relieved by hot showers and by cessation "
        "(Sorensen 2017; Venkatesan 2019) — does cause electrolyte "
        "disturbances and volume depletion, but these are the EXPECTED "
        "SECONDARY consequence of protracted vomiting and dehydration "
        "(hypokalaemia, hypochloraemic metabolic alkalosis, prerenal acute "
        "kidney injury, and a secondary rise in antidiuretic hormone / "
        "vasopressin driven by hypovolaemia and nausea), NOT evidence of a "
        "primary cannabinoid action on ADH secretion. There is essentially "
        "no study measuring a direct cannabinoid effect on ADH/vasopressin in "
        "CHS, so a claim of CHS 'triggering significant acute ADH "
        "fluctuations' as a primary endocrine mechanism is unsupported — the "
        "fluctuations are physiologically appropriate responses to vomiting "
        "and hypovolaemia. The clinically important point is real: CHS "
        "episodes warrant electrolyte and volume monitoring."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_SORENSEN_2017, _VENKATESAN_2019),
    study_design="CHS systematic review + consensus; no primary ADH/vasopressin study",
    key_finding_summary=(
        "CHS electrolyte/volume disturbance is secondary to vomiting + "
        "dehydration (with appropriate hypovolaemic ADH rise); no primary "
        "cannabinoid-ADH effect demonstrated"
    ),
    key_notes=(
        "HONEST-GAP row: distinguish a SECONDARY ADH/electrolyte response to "
        "vomiting from a PRIMARY cannabinoid effect on ADH — only the former "
        "is supported.",
        "Clinically, CHS dehydration and AKI are well documented; the "
        "endocrine framing (ADH) is reactive physiology, not a cannabinoid "
        "secretagogue effect.",
    ),
)


_CB1_ANTAGONIST_BAT = EndocrineRow(
    name="CB1 antagonists/inverse agonists, brown-adipose thermogenesis & UCP1 (Verty 2008)",
    topic=EndocrineTopic.CB1_ANTAGONIST_BAT,
    claim_text=(
        "Blocking CB1 (UniProt P21554; HGNC CNR1) increases energy "
        "expenditure partly via brown adipose tissue (BAT) thermogenesis. In "
        "rats, chronic rimonabant (a CB1 antagonist/inverse agonist, "
        "10 mg/kg for 21 days) produced sustained weight loss despite only a "
        "transient drop in food intake, with a marked rise in interscapular "
        "BAT temperature and a corresponding increase in uncoupling protein 1 "
        "(UCP1) mRNA and protein; surgically denervating the BAT attenuated "
        "both the temperature rise and the weight loss, showing the effect is "
        "substantially CNS-mediated (sympathetic drive to BAT) rather than a "
        "purely local adipocyte action (Verty 2008). This is the "
        "physiological mirror image of CB1 AGONISM (which promotes lipogenesis "
        "and energy storage). The evidence is robust preclinically; the "
        "human translation is cautionary, because the CB1-antagonist drug "
        "class (rimonabant) was withdrawn for psychiatric adverse effects, so "
        "central CB1 blockade is not a usable human therapy despite the clear "
        "BAT/UCP1 energetics."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_VERTY_2008,),
    study_design="rodent mechanistic study (telemetry BAT temperature, UCP1, BAT denervation)",
    key_finding_summary=(
        "CB1 antagonist (rimonabant) raised BAT thermogenesis + UCP1 and "
        "energy expenditure in rats, CNS/sympathetically mediated"
    ),
    key_notes=(
        "Rodent evidence; the human CB1-antagonist class (rimonabant) was "
        "withdrawn for depression/suicidality — the energetics are real but "
        "central CB1 blockade is not a viable human therapy.",
        "Peripherally-restricted CB1 antagonists are under investigation "
        "precisely to capture this metabolic benefit without CNS harm.",
    ),
)


_LIPID_PROFILE = EndocrineRow(
    name="Daily cannabis use & the lipid profile (HDL/LDL/VLDL) — inconsistent human evidence",
    topic=EndocrineTopic.LIPID_PROFILE,
    claim_text=(
        "Human evidence on cannabis and the lipid profile is inconsistent and "
        "mostly cross-sectional/secondary, so no confident HDL/LDL/VLDL "
        "direction can be asserted. Two forces pull opposite ways: "
        "mechanistically, CB1 (UniProt P21554; HGNC CNR1) activation promotes "
        "hepatic lipogenesis and VLDL/triglyceride synthesis (which would "
        "WORSEN lipids), yet cannabis users are cross-sectionally leaner with "
        "lower fasting insulin, which tends to associate with a more "
        "favourable profile. Reported human associations are mixed — for "
        "example, one case-control cohort found cannabis use associated with "
        "significantly LOWER triglycerides (Mhalla 2018, a secondary, "
        "confounded finding in a psychiatric sample), while other surveys show "
        "little consistent effect on HDL or LDL. No dedicated, adequately-"
        "powered prospective study has tested daily cannabis on hepatic VLDL "
        "synthesis or a full fasting lipid panel, so the honest answer is "
        "'inconsistent / understudied', with a mechanistic expectation that "
        "the direct hepatic CB1 effect (pro-lipogenic) is partly offset by "
        "the leaner metabolic phenotype of users."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_VETTOR_2009, _MHALLA_2018),
    study_design="mechanistic review + secondary cross-sectional association (mixed evidence)",
    key_finding_summary=(
        "Inconsistent human data; CB1 is pro-lipogenic (↑VLDL) yet users are "
        "leaner — opposing forces; no dedicated lipid trial"
    ),
    key_notes=(
        "Do not assert a clean HDL/LDL/VLDL direction — the human literature "
        "is mixed and confounded by tobacco co-use, diet and adiposity.",
        "The pro-lipogenic CB1 mechanism (↑VLDL/TG) and the lean-user "
        "epidemiology genuinely conflict; that tension IS the answer.",
    ),
)


_GI_INCRETIN = EndocrineRow(
    name="Gut cannabinoid signalling & incretin (GLP-1 / GIP) secretion (Reimann & Gribble 2016)",
    topic=EndocrineTopic.GI_INCRETIN,
    claim_text=(
        "Localised endocannabinoid/CB1 signalling in the gastrointestinal "
        "tract modulates incretin secretion from enteroendocrine cells. In "
        "the enteroendocrine-physiology literature (Reimann & Gribble 2016), "
        "CB1 (UniProt P21554; HGNC CNR1) agonists have been shown to "
        "selectively INHIBIT glucose-dependent insulinotropic polypeptide "
        "(GIP) secretion from K-cells, while the lipid-sensing receptor "
        "GPR119 (a target shared by some endocannabinoid-like mediators such "
        "as oleoylethanolamide) PROMOTES glucagon-like peptide-1 (GLP-1) "
        "release from L-cells. Thus the endocannabinoidome can push incretin "
        "tone in opposite directions depending on the receptor and ligand: "
        "CB1 tone tends to blunt GIP, whereas GPR119/PPARα-type signalling "
        "augments GLP-1. This is mechanistic/physiological evidence "
        "(rodent + cell models, human enteroendocrine biology); the net "
        "effect of smoked or ingested cannabis on human postprandial GLP-1 "
        "and GIP has not been characterised in a dedicated clinical study."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_REIMANN_GRIBBLE_2016,),
    study_design="enteroendocrine mechanism review (rodent + cell + human gut biology)",
    key_finding_summary=(
        "CB1 agonism selectively inhibits GIP; GPR119 (endocannabinoid-like "
        "ligands) promotes GLP-1 — receptor-dependent, opposite directions"
    ),
    key_notes=(
        "The incretin effect is receptor-specific (CB1↓GIP vs GPR119↑GLP-1) "
        "— a blanket 'cannabis changes incretins' statement is too coarse.",
        "No human cannabis-exposure study measures postprandial GLP-1/GIP; "
        "this is target-level physiology, not clinical pharmacology.",
    ),
)


_DELIVERY_ROUTE_HPG = EndocrineRow(
    name="Delivery route (inhaled/oral/topical) and effects on testosterone / LH — PK is known, the HPG endpoint is not route-resolved",
    topic=EndocrineTopic.DELIVERY_ROUTE_HPG,
    claim_text=(
        "Route of administration sharply changes Δ⁹-THC pharmacokinetics: "
        "inhalation gives a rapid, high plasma peak (Cmax within minutes, "
        "bioavailability ~10-35%); oral ingestion gives a delayed, lower, "
        "prolonged peak (Tmax 1-3 h) with a large first-pass conversion to "
        "the active 11-OH-THC metabolite; topical/transdermal application of "
        "non-permeation-enhanced cannabinoids produces little to no systemic "
        "absorption. From those PK facts it FOLLOWS that any "
        "hypothalamic-pituitary-gonadal effect would track systemic exposure "
        "— inhaled and oral routes can engage the HPG axis (the broader "
        "literature links cannabis to lowered LH and inconsistent "
        "testosterone), whereas a truly topical, non-systemic application "
        "would not be expected to move serum testosterone or LH. HOWEVER, no "
        "study has actually MEASURED route-resolved peak effects on serum "
        "testosterone and LH, so the route-versus-hormone comparison is an "
        "inference from pharmacokinetics, not a directly demonstrated "
        "dose-by-route endocrine result — that specific comparison is a "
        "genuine evidence gap."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_PAYNE_2019, _BROWN_DOBS_2002),
    study_design="route PK (established) + HPG-hormone literature; no route-resolved hormone study",
    key_finding_summary=(
        "Route sets systemic exposure (inhaled>oral>>topical≈0); HPG effects "
        "track exposure, but no study measures route-resolved testosterone/LH"
    ),
    key_notes=(
        "HONEST-GAP row: PK-by-route is well established and HPG suppression "
        "is documented, but their PRODUCT (route → peak testosterone/LH) is "
        "inferred, not measured.",
        "Topical/transdermal cannabinoids are largely non-systemic, so a "
        "meaningful HPG effect from a topical is mechanistically unlikely.",
    ),
)


_REGISTRY: tuple[EndocrineRow, ...] = (
    _METABOLIC_INSULIN,
    _ADIPOGENESIS_LEPTIN,
    _DIABETIC_KETOACIDOSIS,
    _THYROID_HPT,
    _GROWTH_HORMONE_PROLACTIN,
    _GONADAL_HPG,
    _EMBRYO_IMPLANTATION,
    _ADRENAL_HPA,
    _RECEPTOR_DESENSITIZATION,
    _BONE_REMODELING,
    # Spec 027 — second endocrine question wave.
    _AUTOIMMUNE_THYROIDITIS,
    _BETA_CELL_SURVIVAL,
    _PRENATAL_NEUROENDOCRINE,
    _MELATONIN_CIRCADIAN,
    _CBD_FULLSPECTRUM_CORTISOL,
    _CHS_ADH_ELECTROLYTE,
    _CB1_ANTAGONIST_BAT,
    _LIPID_PROFILE,
    _GI_INCRETIN,
    _DELIVERY_ROUTE_HPG,
)


# ── Topic-keyword detectors ────────────────────────────────────────────
#
# Each detector requires a cannabis / cannabinoid / endocannabinoid /
# THC / CBD / CB1 / CB2 context AND a topic-specific endocrine keyword,
# so unrelated endocrine prompts (no cannabinoid) and unrelated cannabis
# prompts (no endocrine endpoint) both stay quiet. ``_CANN`` is the
# shared cannabis-context alternation.

_CANN = (
    r"(?:cannab\w*|marijuana|marihuana|\bthc\b|tetrahydrocannabinol|dronabinol|"
    r"\bcbd\b|cannabidiol|phytocannabinoid\w*|endocannabinoid\w*|anandamide|"
    r"\bcb1\b|\bcb2\b|cb_?\{?1\}?|cb_?\{?2\}?|cnr1|cnr2|\baea\b|2-ag)"
)


def _topic_rx(endocrine_keywords: str) -> re.Pattern[str]:
    """Build a detector requiring both a cannabis context and an endocrine
    keyword, in either order, within a reasonable window."""
    return re.compile(
        rf"(?:{_CANN}[\s\S]{{0,120}}(?:{endocrine_keywords})"
        rf"|(?:{endocrine_keywords})[\s\S]{{0,120}}{_CANN})",
        re.IGNORECASE,
    )


_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        EndocrineTopic.METABOLIC_INSULIN,
        _topic_rx(
            r"insulin\s+sensitiv\w*|insulin\s+resist\w*|fasting\s+insulin|"
            r"fasting\s+glucose|homa[- ]?ir|glyc(?:a|ae)mic|metabolic\s+syndrome|"
            r"glucose\s+(?:level|toler\w*|homeostasis)"
        ),
    ),
    (
        EndocrineTopic.ADIPOGENESIS_LEPTIN,
        _topic_rx(
            r"adipogen\w*|adipocyt\w*|lipogen\w*|leptin|ghrelin|"
            r"fat\s+cell|adipose"
        ),
    ),
    (
        EndocrineTopic.DIABETIC_KETOACIDOSIS,
        _topic_rx(
            r"ketoacidosis|\bdka\b|type\s*[1i]\s+diabet\w*|t1d\b|"
            r"diabetic\s+ketoacid\w*"
        ),
    ),
    (
        EndocrineTopic.THYROID_HPT,
        _topic_rx(
            r"thyroid|\btsh\b|thyrotropin|free\s*t3|free\s*t4|"
            r"\bt3\b|\bt4\b|triiodothyronine|thyroxine|"
            r"hypothalamic[- ]pituitary[- ]thyroid|hpt\s+axis"
        ),
    ),
    (
        EndocrineTopic.GROWTH_HORMONE_PROLACTIN,
        _topic_rx(
            r"growth\s+hormone|\bgh\b|somatotropin|somatotroph\w*|"
            r"prolactin|\bprl\b"
        ),
    ),
    (
        EndocrineTopic.GONADAL_HPG,
        _topic_rx(
            r"testosterone|lutein\w*\s+hormone|\blh\b|\bfsh\b|"
            r"hypothalamic[- ]pituitary[- ]gonadal|hpg\s+axis|gonadal|"
            r"estrogen|oestrogen|progesterone|spermatogen\w*|"
            r"semen|sperm\b|menstrual|ovulat\w*"
        ),
    ),
    (
        EndocrineTopic.EMBRYO_IMPLANTATION,
        _topic_rx(
            r"embryo\s+implant\w*|implantation|placent\w*|"
            r"early\s+pregnan\w*|preimplant\w*|blastocyst|"
            r"\bfaah\b|fatty\s+acid\s+amide\s+hydrolase"
        ),
    ),
    (
        EndocrineTopic.ADRENAL_HPA,
        _topic_rx(
            r"cortisol|\bhpa\b|hypothalamic[- ]pituitary[- ]adrenal|"
            r"cortisol\s+awakening|adrenal\s+axis|\bacth\b|"
            r"stress\s+reactiv\w*|glucocorticoid"
        ),
    ),
    (
        EndocrineTopic.RECEPTOR_DESENSITIZATION,
        _topic_rx(
            r"desensiti[sz]\w*|internali[sz]\w*|down[- ]?regulat\w*|"
            r"receptor\s+tolerance|β[- ]?arrestin|beta[- ]?arrestin|"
            r"thc[:/]\s*cbd|cbd[:/]\s*thc|thc.{0,10}cbd\s+ratio|"
            r"receptor\s+traffick\w*"
        ),
    ),
    (
        EndocrineTopic.BONE_REMODELING,
        _topic_rx(
            r"osteoblast\w*|osteoclast\w*|bone\s+mineral\s+densit\w*|"
            r"\bbmd\b|bone\s+mass|bone\s+remodel\w*|osteoporos\w*|"
            r"skeletal|bone\s+loss"
        ),
    ),
    # ── Spec 027 — second wave ──────────────────────────────────────────
    (
        EndocrineTopic.AUTOIMMUNE_THYROIDITIS,
        _topic_rx(
            r"hashimoto\w*|autoimmune\s+thyroid\w*|thyroid\s+autoimmun\w*|"
            r"thyroiditis|graves[\s']*\s*disease|thyroid\s+peroxidase|"
            r"anti[- ]?tpo|thyroid\s+autoantibod\w*"
        ),
    ),
    (
        EndocrineTopic.BETA_CELL_SURVIVAL,
        _topic_rx(
            r"beta[- ]?cell\w*|β[- ]?cell\w*|islet\w*|insulitis|"
            r"insulin[- ]?secreting|pancreatic\s+(?:beta|β)"
        ),
    ),
    (
        EndocrineTopic.PRENATAL_NEUROENDOCRINE,
        _topic_rx(
            r"maternal|prenatal|in\s*utero|fetal|foetal|offspring|"
            r"gestational|perinatal|neurodevelopment\w*|"
            r"neuroendocrine\s+develop\w*"
        ),
    ),
    (
        EndocrineTopic.MELATONIN_CIRCADIAN,
        _topic_rx(
            r"melatonin|circadian|suprachiasmatic|pineal\b"
        ),
    ),
    (
        EndocrineTopic.CHS_ADH_ELECTROLYTE,
        _topic_rx(
            r"(?:hyperemesis|cannabinoid\s+hyperemesis|\bchs\b)[\s\S]{0,90}"
            r"(?:\badh\b|antidiuretic|vasopressin|electrolyte\w*|sodium|"
            r"hyponatr\w*|dehydrat\w*)|"
            r"(?:\badh\b|antidiuretic|vasopressin|electrolyte\w*|hyponatr\w*)"
            r"[\s\S]{0,90}(?:hyperemesis|\bchs\b)"
        ),
    ),
    (
        EndocrineTopic.CB1_ANTAGONIST_BAT,
        _topic_rx(
            r"ucp1|uncoupling\s+protein|brown\s+adipose|brown\s+fat|"
            r"thermogen\w*"
        ),
    ),
    (
        EndocrineTopic.LIPID_PROFILE,
        _topic_rx(
            r"lipid\s+profile|\bhdl\b|\bldl\b|\bvldl\b|cholesterol|"
            r"triglycerid\w*|dyslipid\w*|lipogenesis|lipoprotein"
        ),
    ),
    (
        EndocrineTopic.GI_INCRETIN,
        _topic_rx(
            r"incretin\w*|glp[- ]?1|\bgip\b|glucagon[- ]?like\s+peptide|"
            r"enteroendocrine"
        ),
    ),
    # CBD-vs-full-spectrum cortisol: needs BOTH the comparison framing AND a
    # cortisol endpoint (so it does not hijack every full-spectrum question
    # nor every cortisol question — those route to ADRENAL_HPA).
    (
        EndocrineTopic.CBD_FULLSPECTRUM_CORTISOL,
        re.compile(
            r"(?=[\s\S]*(?:full[- ]?spectrum|isolate\b|isolated\s+cbd|"
            r"cbd\s+isolate|broad[- ]?spectrum|hemp\s+extract))"
            r"(?=[\s\S]*cortisol)",
            re.IGNORECASE,
        ),
    ),
    # Delivery-route → testosterone/LH: keyed on (route × gonadal hormone)
    # WITHOUT requiring an explicit cannabinoid token — the canonical prompt
    # ("inhalation, ingestion, topical … testosterone and LH") names no
    # cannabinoid, which is exactly why the cannabis-context detectors stayed
    # silent. Route-vocabulary + a gonadal hormone is specific enough.
    (
        EndocrineTopic.DELIVERY_ROUTE_HPG,
        re.compile(
            r"(?=[\s\S]*(?:inhalation|inhaled|ingestion|ingested|edible\w*|"
            r"smoked|vaporiz\w*|vaporis\w*|sublingual|oromucosal|topical|"
            r"transdermal|route\s+of\s+administration|delivery\s+method\w*))"
            r"(?=[\s\S]*(?:testosterone|luteinizing|luteinising|\blh\b))",
            re.IGNORECASE,
        ),
    ),
)


def all_endocrine_rows() -> tuple[EndocrineRow, ...]:
    return _REGISTRY


def find_endocrine_rows(topic_or_name: str) -> tuple[EndocrineRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[EndocrineRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_endocrine_mention(text: str) -> tuple[EndocrineRow, ...]:
    if not text:
        return ()
    matched: set[str] = set()
    for topic, rx in _TOPIC_KEYWORDS:
        if rx.search(text):
            matched.add(topic)
    if not matched:
        return ()
    return tuple(r for r in _REGISTRY if r.topic in matched)


_TOPIC_DISPLAY_NAMES = {
    EndocrineTopic.METABOLIC_INSULIN: (
        "Metabolic — insulin sensitivity & fasting glucose (Penner 2013)"
    ),
    EndocrineTopic.ADIPOGENESIS_LEPTIN: (
        "Adipogenesis & leptin/ghrelin signalling (Vettor 2009)"
    ),
    EndocrineTopic.DIABETIC_KETOACIDOSIS: (
        "Diabetic ketoacidosis in type 1 diabetes (Akturk 2019/2022)"
    ),
    EndocrineTopic.THYROID_HPT: (
        "HPT axis — TSH / T3 / free-T4 (Bonnet 2013)"
    ),
    EndocrineTopic.GROWTH_HORMONE_PROLACTIN: (
        "Growth hormone & prolactin (Brown & Dobs 2002)"
    ),
    EndocrineTopic.GONADAL_HPG: (
        "HPG axis — testosterone / estrogen / progesterone (Payne 2019)"
    ),
    EndocrineTopic.EMBRYO_IMPLANTATION: (
        "Embryo implantation & anandamide tone (Wang/Dey 2006)"
    ),
    EndocrineTopic.ADRENAL_HPA: (
        "HPA axis & cortisol response (van Leeuwen 2011 TRAILS)"
    ),
    EndocrineTopic.RECEPTOR_DESENSITIZATION: (
        "CB1/CB2 desensitization & internalization (Lazenka 2012)"
    ),
    EndocrineTopic.BONE_REMODELING: (
        "Bone — osteoblast/osteoclast & BMD (Ofek 2006)"
    ),
    EndocrineTopic.AUTOIMMUNE_THYROIDITIS: (
        "Autoimmune thyroiditis / Hashimoto's — evidence gap (Nagarkatti 2009)"
    ),
    EndocrineTopic.BETA_CELL_SURVIVAL: (
        "Pancreatic β-cell apoptosis & cytokines (González-Mariscal 2021)"
    ),
    EndocrineTopic.PRENATAL_NEUROENDOCRINE: (
        "Maternal cannabis & offspring neuroendocrine development (Frau 2023)"
    ),
    EndocrineTopic.MELATONIN_CIRCADIAN: (
        "Melatonin secretion & circadian/metabolic rhythm (Ried 2022 RCT)"
    ),
    EndocrineTopic.CBD_FULLSPECTRUM_CORTISOL: (
        "Isolated CBD vs full-spectrum on acute cortisol (Appiah-Kusi 2020)"
    ),
    EndocrineTopic.CHS_ADH_ELECTROLYTE: (
        "CHS, ADH & electrolytes — secondary, not primary (Sorensen 2017)"
    ),
    EndocrineTopic.CB1_ANTAGONIST_BAT: (
        "CB1 antagonist → BAT thermogenesis & UCP1 (Verty 2008)"
    ),
    EndocrineTopic.LIPID_PROFILE: (
        "Cannabis & lipid profile (HDL/LDL/VLDL) — inconsistent (Vettor/Mhalla)"
    ),
    EndocrineTopic.GI_INCRETIN: (
        "Gut cannabinoid signalling & incretins GLP-1/GIP (Reimann 2016)"
    ),
    EndocrineTopic.DELIVERY_ROUTE_HPG: (
        "Delivery route → testosterone/LH — PK known, endpoint not resolved"
    ),
}


def render_markdown(rows: Iterable[EndocrineRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[EndocrineRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = ["## Endocrinology registry", ""]
    for topic, display in _TOPIC_DISPLAY_NAMES.items():
        bucket = by_topic.get(topic)
        if not bucket:
            continue
        lines.append(f"### {display}")
        lines.append("")
        for r in bucket:
            lines.append(f"- **{r.name}** ({r.evidence_level.value})")
            lines.append(f"  - {r.claim_text}")
            if r.study_design:
                lines.append(f"  - Design: {r.study_design}")
            if r.key_finding_summary:
                lines.append(f"  - Key finding: {r.key_finding_summary}")
            for c in r.citations:
                ident = []
                if c.pmid:
                    ident.append(f"PMID {c.pmid}")
                if c.doi:
                    ident.append(f"doi:{c.doi}")
                lines.append(
                    f"  - Source: {c.label}"
                    + (f" — {' / '.join(ident)}" if ident else "")
                )
        lines.append("")
    return "\n".join(lines).rstrip()
