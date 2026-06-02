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
