"""Pain-medicine registry (spec 006 US1 / FR-001).

Research-grade chronic-pain, neuropathic-pain, and experimental-pain
literature for cannabinoids — the topics a pain-medicine PI,
guideline author, or systematic-review methodologist asks about.
Spec 005 returned 0-1 curated claims for every pain-medicine prompt
and the NASEM 2017 chapter-4 conclusive-evidence finding (the single
most-cited cannabis-medicine statement) was entirely absent. Spec 006
ships a curated registry under Constitution §IV (researcher-only)
with primary citations per §I.

Topic coverage:

- ``nasem_finding`` — NASEM 2017 chapter-4 "conclusive evidence:
  cannabis effective for chronic pain in adults" finding. Anchored
  to the Whiting 2015 JAMA SR (PMID 26103030) the NASEM committee
  used as the central evidence base. NASEM is the National Academies
  of Sciences, Engineering, and Medicine and the 2017 report is the
  field-standard US evidence synthesis.
- ``sr_chronic_pain`` — Whiting 2015 JAMA cannabinoid SR for
  chronic-pain indication (PMID 26103030). 28 RCTs, n ≈ 2,454.
  Modest effect-size, "moderate-quality evidence". Single most-cited
  cannabis-medicine SR.
- ``sr_neuropathic`` — Stockings 2018 PAIN systematic review of
  cannabinoid neuropathic-pain trials (PMID 29847469). 47 RCTs
  evaluated.
- ``cochrane_review`` — Mücke 2018 Cochrane review on cannabinoids
  for chronic neuropathic pain (PMID 29513392). The Cochrane
  conclusion was cautious — "low-quality evidence; modest benefit;
  AE-driven discontinuation" — different in tone from the broader
  Whiting / Stockings findings.
- ``cohort_observational`` — Boehnke 2019 J Pain prospective
  medical-cannabis cohort (PMID 30715980). Observational evidence
  from a real-world MMJ-card cohort showing opioid-reduction
  patterns; observational, not causal.
- ``ipd_meta_analysis`` — Andreae 2015 J Pain individual-patient-data
  meta-analysis of inhaled cannabis for neuropathic pain (PMID
  26362106). 5 trials, NNT ≈ 5.6.
- ``experimental_pain`` — de Vita 2018 J Pain experimental-pain SR
  (PMID 30422266). Laboratory-pain (cold-pressor, heat-pain,
  electrical) cannabinoid effects in healthy volunteers — quantitative
  vs the clinical-trial literature.

Each row carries `to_claim()` returning a typed Claim, identifier-
anchored citations per §I, and is matched by a topic-keyword regex
detector. The module is reference-only — no live discovery.
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
    "PainMedicineCitation",
    "PainMedicineRow",
    "PainMedicineTopic",
    "all_pain_medicine_rows",
    "find_pain_medicine_rows",
    "detect_pain_medicine_mention",
    "render_markdown",
]


class PainMedicineTopic:
    NASEM_FINDING = "nasem_finding"
    SR_CHRONIC_PAIN = "sr_chronic_pain"
    SR_NEUROPATHIC = "sr_neuropathic"
    COCHRANE_REVIEW = "cochrane_review"
    COHORT_OBSERVATIONAL = "cohort_observational"
    IPD_META_ANALYSIS = "ipd_meta_analysis"
    EXPERIMENTAL_PAIN = "experimental_pain"


@dataclass(frozen=True)
class PainMedicineCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class PainMedicineRow:
    """One curated pain-medicine primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[PainMedicineCitation, ...]
    population: str = ""          # chronic-pain / neuropathic / experimental
    n_patients: int = 0
    key_finding_summary: str = ""
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"pain-medicine row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"pain-medicine row {self.name!r} citation "
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
            "population": self.population,
            "n_patients": self.n_patients,
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

_WHITING_2015 = PainMedicineCitation(
    label="Whiting PF et al., JAMA 2015, cannabinoids for medical use — "
          "systematic review and meta-analysis (28 RCTs of chronic-pain "
          "indication, n ≈ 2,454; moderate-quality evidence of modest "
          "benefit)",
    pmid="26103030", year=2015,
)
_STOCKINGS_2018 = PainMedicineCitation(
    label="Stockings E et al., PAIN 2018, cannabis and cannabinoids for the "
          "treatment of people with chronic non-cancer pain — systematic "
          "review and meta-analysis",
    pmid="29847469", year=2018,
)
_MUCKE_2018_COCHRANE = PainMedicineCitation(
    label="Mücke M et al., Cochrane Database Syst Rev 2018, cannabis-based "
          "medicines for chronic neuropathic pain in adults (16 trials, "
          "n ≈ 1,750; low-quality evidence; modest benefit; AE-driven "
          "discontinuation)",
    pmid="29513392", year=2018,
)
_BOEHNKE_2019 = PainMedicineCitation(
    label="Boehnke KF et al., J Pain 2019, qualifying conditions of medical "
          "cannabis license holders in the United States — prospective "
          "cohort analyses",
    pmid="30715980", year=2019,
)
_ANDREAE_2015 = PainMedicineCitation(
    label="Andreae MH et al., J Pain 2015, inhaled cannabis for chronic "
          "neuropathic pain — individual-patient-data meta-analysis "
          "(5 trials, NNT ≈ 5.6)",
    pmid="26362106", year=2015,
)
_DEVITA_2018 = PainMedicineCitation(
    label="De Vita MJ et al., J Pain 2018, association of cannabinoid "
          "administration with experimental pain in healthy adults — "
          "systematic review and meta-analysis",
    pmid="30422266", year=2018,
)
_NASEM_2017 = PainMedicineCitation(
    label="National Academies of Sciences, Engineering, and Medicine 2017, "
          "The Health Effects of Cannabis and Cannabinoids — Chapter 4 "
          "Therapeutic Effects (conclusive evidence: cannabis or cannabinoids "
          "are effective for the treatment of chronic pain in adults)",
    doi="10.17226/24625", year=2017,
)


# ── Registry rows ──────────────────────────────────────────────────────

_NASEM_2017_CHRONIC_PAIN = PainMedicineRow(
    name="NASEM 2017 chapter-4 conclusive-evidence finding — chronic pain",
    topic=PainMedicineTopic.NASEM_FINDING,
    claim_text=(
        "The 2017 National Academies of Sciences, Engineering, and Medicine "
        "(NASEM) consensus report 'The Health Effects of Cannabis and "
        "Cannabinoids' (chapter 4, Therapeutic Effects) concluded that "
        "there is *conclusive or substantial evidence* that cannabis or "
        "cannabinoids are effective for the treatment of chronic pain in "
        "adults. This is the highest evidence-grade tier in the NASEM "
        "schema and is the single most-cited statement in cannabis-medicine "
        "literature. The NASEM evidence base for chronic-pain effectiveness "
        "was anchored to the Whiting 2015 JAMA systematic review (PMID "
        "26103030) and consistent SRs and meta-analyses. The NASEM report "
        "did NOT make a clinical-practice recommendation — it summarised "
        "the evidence; clinical-practice recommendations belong to the "
        "specialty societies (AAPM, IASP, etc.)."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_NASEM_2017, _WHITING_2015),
    population="adults with chronic pain (heterogeneous etiologies)",
    n_patients=0,
    key_finding_summary=(
        "Conclusive / substantial evidence — the top NASEM evidence tier"
    ),
    key_notes=(
        "NASEM evidence-tier hierarchy (top→bottom): conclusive, "
        "substantial, moderate, limited, insufficient, no/limited.",
        "Chronic pain is the most-cited NASEM 'conclusive' finding; "
        "the related 'substantial evidence' finding covers chemotherapy-"
        "induced nausea & vomiting (oral cannabinoids) and patient-"
        "reported MS spasticity.",
        "NASEM 2017 'limited evidence' findings include sleep "
        "disturbance in chronic-pain patients; 'insufficient evidence' "
        "covers depression, anxiety disorders, PTSD, and a number of "
        "other psychiatric indications — see psychiatry / PTSD-anxiety-"
        "sleep registries for the per-indication primary literature.",
    ),
)


_WHITING_2015_SR = PainMedicineRow(
    name="Whiting 2015 JAMA cannabinoids-for-medical-use systematic review",
    topic=PainMedicineTopic.SR_CHRONIC_PAIN,
    claim_text=(
        "Whiting et al. 2015 JAMA published the canonical systematic review "
        "and meta-analysis of cannabinoids for medical use, evaluating 79 "
        "trials (n ≈ 6,462) across multiple indications. For chronic-pain "
        "specifically, 28 RCTs (n ≈ 2,454) were pooled. The effect-size "
        "estimate was an average ~30% reduction in pain compared with "
        "placebo (OR ≈ 1.41, 95% CI 0.99-2.00 for ≥ 30% pain reduction), "
        "categorised as 'moderate-quality evidence'. Adverse-event burden "
        "was substantial (dizziness, dry mouth, somnolence, hallucination, "
        "psychiatric symptoms — moderate-quality evidence of increased AE "
        "risk). Whiting 2015 is the most-cited evidence base for cannabis-"
        "medicine SRs since its publication."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_WHITING_2015,),
    population="chronic non-cancer pain (heterogeneous etiologies)",
    n_patients=2454,
    key_finding_summary=(
        "OR ≈ 1.41 for ≥ 30% pain reduction; moderate-quality evidence"
    ),
    key_notes=(
        "Whiting 2015 included a wide range of cannabinoid products "
        "(nabiximols, dronabinol, nabilone, smoked / vaporised cannabis, "
        "ajulemic acid); heterogeneity is substantial.",
        "Quality-of-evidence grading: GRADE-style; the chronic-pain "
        "indication was rated 'moderate-quality' due to inconsistency "
        "and imprecision rather than risk-of-bias.",
    ),
)


_STOCKINGS_2018_SR = PainMedicineRow(
    name="Stockings 2018 PAIN cannabinoid chronic-non-cancer-pain SR",
    topic=PainMedicineTopic.SR_NEUROPATHIC,
    claim_text=(
        "Stockings et al. 2018 PAIN published a systematic review and "
        "meta-analysis of cannabis and cannabinoids for chronic non-cancer "
        "pain (47 RCTs evaluated, plus 57 observational studies). For "
        "neuropathic pain specifically, the SR found a number-needed-to-"
        "treat for ≥ 30% pain reduction of ~24, with substantial "
        "heterogeneity. The authors concluded 'evidence for effectiveness "
        "of cannabinoids in chronic non-cancer pain is limited'. The "
        "Stockings SR is more cautious in interpretation than Whiting "
        "2015 due to inclusion of observational data and a stricter "
        "outcome-definition framework."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_STOCKINGS_2018,),
    population="chronic non-cancer pain (neuropathic emphasis)",
    n_patients=0,
    key_finding_summary=(
        "NNT (≥ 30% pain reduction) ~24 — limited evidence overall"
    ),
    key_notes=(
        "The Stockings 2018 NNT is much higher than the Andreae 2015 "
        "IPD-MA neuropathic-pain NNT (~5.6), illustrating the well-"
        "established difference between trial-level pooled estimates "
        "and individual-patient-data estimates.",
        "Stockings included observational studies separately — the "
        "real-world cohort signal (lower pain-VAS scores, opioid "
        "reductions) is consistent with the RCT signal but cannot "
        "be causally interpreted.",
    ),
)


_MUCKE_2018_COCHRANE_ROW = PainMedicineRow(
    name="Mücke 2018 Cochrane review — cannabinoids for chronic neuropathic pain",
    topic=PainMedicineTopic.COCHRANE_REVIEW,
    claim_text=(
        "Mücke et al. 2018 published the Cochrane systematic review on "
        "cannabis-based medicines for chronic neuropathic pain in adults "
        "(16 trials, n ≈ 1,750, nabiximols / dronabinol / nabilone / "
        "smoked cannabis). The Cochrane conclusion was deliberately "
        "cautious — 'low-quality evidence' that cannabis-based medicines "
        "may produce modest pain reductions, with adverse-event-driven "
        "discontinuation rates that may offset any benefit. The Cochrane "
        "verdict differs in tone from the broader Whiting 2015 / Andreae "
        "2015 SRs, reflecting Cochrane's stricter GRADE-evidence-level "
        "framework and tighter risk-of-bias appraisal (ROB-2 / older "
        "Cochrane risk-of-bias tool)."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_MUCKE_2018_COCHRANE,),
    population="chronic neuropathic pain in adults",
    n_patients=1750,
    key_finding_summary=(
        "Low-quality evidence of modest benefit; AE-driven discontinuation"
    ),
    key_notes=(
        "The Mücke / Whiting tone divergence is a teaching example of "
        "evidence-base vs evidence-interpretation differences — same "
        "underlying trials, different framing.",
        "Cochrane SRs are typically the gold-standard tier in the "
        "Cannavec Science source-tier ranking (Level A) — the "
        "low-quality-evidence GRADE descriptor reflects the BODY of "
        "evidence, not the Cochrane methodology.",
    ),
)


_BOEHNKE_2019_COHORT = PainMedicineRow(
    name="Boehnke 2019 J Pain medical-cannabis prospective cohort",
    topic=PainMedicineTopic.COHORT_OBSERVATIONAL,
    claim_text=(
        "Boehnke et al. 2019 J Pain analysed US medical-cannabis-license "
        "holder qualifying conditions over 2016-2017 — chronic pain was "
        "the most common qualifying condition (~62% of patients). The "
        "Boehnke prospective MMJ-card cohort reports lower opioid use, "
        "lower pain-VAS scores, and improved quality-of-life measures vs "
        "baseline. The Boehnke evidence is OBSERVATIONAL — not causal "
        "(no placebo arm; self-selection bias inherent to MMJ-cohort "
        "design). The signal is consistent with the RCT literature but "
        "should be interpreted as descriptive epidemiology of real-world "
        "MMJ patients, not as efficacy evidence for chronic-pain "
        "indication."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_BOEHNKE_2019,),
    population="US medical-cannabis-license holders (real-world cohort)",
    n_patients=0,
    key_finding_summary=(
        "Chronic pain = 62% of qualifying conditions; observational "
        "evidence consistent with RCT signal"
    ),
    key_notes=(
        "Observational MMJ-cohort designs inherently select for "
        "patients who chose to apply for an MMJ card — a strong "
        "self-selection signal that makes causal interpretation "
        "inappropriate.",
        "STROBE reporting standard applies (see reporting-rigor "
        "module); observational cohort studies should report adherence "
        "to STROBE.",
    ),
)


_ANDREAE_2015_IPD = PainMedicineRow(
    name="Andreae 2015 J Pain IPD meta-analysis — inhaled cannabis neuropathic pain",
    topic=PainMedicineTopic.IPD_META_ANALYSIS,
    claim_text=(
        "Andreae et al. 2015 J Pain published an individual-patient-data "
        "meta-analysis of 5 RCTs of inhaled cannabis for chronic "
        "neuropathic pain (n ≈ 178 IPD patients). The pooled NNT for ≥ "
        "30% pain reduction was ≈ 5.6 (95% CI 3.4-14). The Andreae 2015 "
        "IPD-MA is methodologically stronger than the trial-level pooled "
        "estimates because IPD pooling controls for the heterogeneity in "
        "outcome-definition across trials. The Andreae NNT (~5.6) and the "
        "Stockings 2018 NNT (~24) bracket the cannabinoid-neuropathic-pain "
        "effect estimate."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_ANDREAE_2015,),
    population="chronic neuropathic pain (IPD pooled across 5 trials)",
    n_patients=178,
    key_finding_summary="NNT ≈ 5.6 (95% CI 3.4-14) for ≥ 30% pain reduction",
    key_notes=(
        "IPD meta-analyses are the highest evidence tier within the SR "
        "framework — the Andreae 2015 IPD-MA is the most-cited "
        "cannabinoid-IPD synthesis.",
        "The Andreae study restricted to inhaled cannabis (smoked or "
        "vaporised) — oral cannabinoid effects on neuropathic pain "
        "are addressed by Whiting 2015 and Mücke 2018.",
    ),
)


_DEVITA_2018_EXP_PAIN = PainMedicineRow(
    name="de Vita 2018 J Pain experimental-pain SR — laboratory pain in healthy volunteers",
    topic=PainMedicineTopic.EXPERIMENTAL_PAIN,
    claim_text=(
        "De Vita et al. 2018 J Pain published a systematic review and "
        "meta-analysis of cannabinoid effects on experimental-pain "
        "outcomes (cold-pressor, heat-pain, electrical, ischemic) in "
        "healthy adult volunteers. The SR pooled 18 studies (n ≈ 442 "
        "participants). The pooled finding was that cannabinoids increase "
        "pain threshold and tolerance (small-to-moderate effect sizes) "
        "without reducing pain intensity at supra-threshold stimulation. "
        "The de Vita SR is a useful quantitative complement to the "
        "clinical-trial literature — laboratory-pain endpoints in "
        "healthy volunteers cannot directly substitute for clinical pain "
        "but illuminate the mechanistic signal."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_DEVITA_2018,),
    population="healthy adult volunteers (experimental-pain stimuli)",
    n_patients=442,
    key_finding_summary=(
        "Cannabinoids increase pain threshold / tolerance; do not reduce "
        "supra-threshold pain intensity"
    ),
    key_notes=(
        "Experimental-pain endpoints (cold-pressor, heat-pain, "
        "electrical) are mechanistic surrogates for clinical pain — "
        "useful for dose-response and PK-PD modelling but not direct "
        "substitutes for clinical-trial endpoints.",
        "The de Vita 2018 finding (threshold up, supra-threshold "
        "intensity unchanged) is consistent with the cannabinoid "
        "modulation of descending-inhibitory pain pathways via CB1 "
        "(UniProt P21554) signalling at the PAG / RVM.",
    ),
)


_REGISTRY: tuple[PainMedicineRow, ...] = (
    _NASEM_2017_CHRONIC_PAIN,
    _WHITING_2015_SR,
    _STOCKINGS_2018_SR,
    _MUCKE_2018_COCHRANE_ROW,
    _BOEHNKE_2019_COHORT,
    _ANDREAE_2015_IPD,
    _DEVITA_2018_EXP_PAIN,
)


# ── Topic-keyword detectors ────────────────────────────────────────────

_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        PainMedicineTopic.NASEM_FINDING,
        re.compile(
            r"\b("
            r"nasem\s+2017|"
            r"national\s+academies\s+(?:of\s+)?(?:sciences?|cannabis)|"
            r"nasem\s+(?:chapter|conclusive|substantial|cannabis)|"
            r"(?:cannabis|cannabinoid).{0,30}nasem|"
            r"nasem.{0,30}(?:cannabis|cannabinoid|conclusive)|"
            r"conclusive\s+evidence.{0,30}(?:cannabis|cannabinoid).{0,30}pain|"
            r"cannabis.{0,30}conclusive\s+evidence.{0,30}pain"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PainMedicineTopic.SR_CHRONIC_PAIN,
        re.compile(
            r"\b("
            r"whiting\s+(?:2015|et\s+al)|"
            r"cannabinoid\w*\s+(?:for\s+)?medical\s+use|"
            r"jama\s+2015\s+(?:cannabis|cannabinoid)|"
            r"cannabis.{0,30}chronic\s+pain.{0,30}systematic\s+review|"
            r"systematic\s+review.{0,30}cannabis.{0,30}chronic\s+pain|"
            r"chronic\s+pain.{0,30}cannabis.{0,30}meta[- ]?analysis"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PainMedicineTopic.SR_NEUROPATHIC,
        re.compile(
            r"\b("
            r"stockings\s+(?:2018|et\s+al)|"
            r"cannabis.{0,30}neuropathic\s+pain.{0,30}systematic\s+review|"
            r"systematic\s+review.{0,30}cannabis.{0,30}neuropathic|"
            r"cannabinoid\w*\s+chronic\s+non[- ]?cancer\s+pain"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PainMedicineTopic.COCHRANE_REVIEW,
        re.compile(
            r"\b("
            r"m(?:ü|u)cke\s+(?:2018|et\s+al)|"
            r"cochrane.{0,30}(?:cannabis|cannabinoid|nabiximols).{0,30}(?:neuropathic|pain)|"
            r"(?:cannabis|cannabinoid|nabiximols).{0,30}cochrane.{0,30}(?:neuropathic|pain)|"
            r"nabiximols.{0,30}neuropathic\s+pain.{0,30}(?:cochrane|systematic)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PainMedicineTopic.COHORT_OBSERVATIONAL,
        re.compile(
            r"\b("
            r"boehnke\s+(?:2019|et\s+al)|"
            r"medical\s+cannabis.{0,30}(?:prospective\s+cohort|cohort\s+study)|"
            r"(?:prospective|real[- ]?world)\s+cohort.{0,30}medical\s+cannabis|"
            r"qualifying\s+conditions?\s+medical\s+cannabis|"
            r"medical\s+cannabis\s+(?:opioid\s+reduction|opioid[- ]?sparing)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PainMedicineTopic.IPD_META_ANALYSIS,
        re.compile(
            r"\b("
            r"andreae\s+(?:2015|et\s+al)|"
            r"individual[- ]?patient[- ]?data.{0,30}cannabis|"
            r"ipd.{0,30}meta[- ]?analysis.{0,30}(?:cannabis|cannabinoid|inhaled)|"
            r"inhaled\s+cannabis.{0,30}neuropathic.{0,30}meta[- ]?analysis|"
            r"nnt.{0,30}cannabis.{0,30}neuropathic"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PainMedicineTopic.EXPERIMENTAL_PAIN,
        re.compile(
            r"\b("
            r"de\s+vita\s+(?:2018|et\s+al)|"
            r"experimental\s+pain.{0,30}(?:cannabis|cannabinoid)|"
            r"(?:cannabis|cannabinoid).{0,30}experimental\s+pain|"
            r"(?:cold[- ]?pressor|heat[- ]?pain|electrical\s+stim\w*).{0,30}cannabinoid|"
            r"laboratory\s+pain.{0,30}(?:cannabis|cannabinoid)|"
            r"pain\s+threshold.{0,30}(?:cannabis|cannabinoid)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_pain_medicine_rows() -> tuple[PainMedicineRow, ...]:
    return _REGISTRY


def find_pain_medicine_rows(topic_or_name: str) -> tuple[PainMedicineRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[PainMedicineRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_pain_medicine_mention(text: str) -> tuple[PainMedicineRow, ...]:
    """Return rows whose topic-keyword regex matches ``text``."""
    if not text:
        return ()
    matched_topics: set[str] = set()
    for topic, rx in _TOPIC_KEYWORDS:
        if rx.search(text):
            matched_topics.add(topic)
    if not matched_topics:
        return ()
    return tuple(r for r in _REGISTRY if r.topic in matched_topics)


# ── Renderer ───────────────────────────────────────────────────────────


_TOPIC_DISPLAY_NAMES = {
    PainMedicineTopic.NASEM_FINDING: "NASEM 2017 chapter-4 finding",
    PainMedicineTopic.SR_CHRONIC_PAIN: "Chronic-pain SR (Whiting 2015 JAMA)",
    PainMedicineTopic.SR_NEUROPATHIC: "Neuropathic-pain SR (Stockings 2018)",
    PainMedicineTopic.COCHRANE_REVIEW: "Cochrane review (Mücke 2018)",
    PainMedicineTopic.COHORT_OBSERVATIONAL: (
        "Prospective MMJ cohort (Boehnke 2019)"
    ),
    PainMedicineTopic.IPD_META_ANALYSIS: (
        "IPD meta-analysis (Andreae 2015)"
    ),
    PainMedicineTopic.EXPERIMENTAL_PAIN: (
        "Experimental-pain SR (de Vita 2018)"
    ),
}


def render_markdown(rows: Iterable[PainMedicineRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[PainMedicineRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Pain medicine registry")
    lines.append("")
    for topic, display in _TOPIC_DISPLAY_NAMES.items():
        bucket = by_topic.get(topic)
        if not bucket:
            continue
        lines.append(f"### {display}")
        lines.append("")
        for r in bucket:
            lines.append(f"- **{r.name}** ({r.evidence_level.value})")
            lines.append(f"  - {r.claim_text}")
            if r.population:
                lines.append(f"  - Population: {r.population}")
            if r.n_patients:
                lines.append(f"  - n ≈ {r.n_patients}")
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
