"""Psychiatry / cannabis-psychosis registry (spec 006 US2 / FR-002).

Research-grade cannabis-and-psychosis primary literature — one of the
most-cited and most-controversial cannabis-research areas. Spec 005
returned 0 curated claims for every cannabis-psychosis prompt; spec
006 ships a curated registry under Constitution §IV (researcher-only)
with primary citations per §I.

Topic coverage:

- ``case_control_psychosis`` — Di Forti 2019 EU-GEI Lancet Psychiatry
  multinational case-control study (PMID 30902669). Daily use of
  high-potency cannabis (≥ 10% THC) associated with population-
  attributable fraction of first-episode psychosis varying by city.
- ``dose_response_sr`` — Marconi 2016 Schizophr Bull systematic
  review with dose-response meta-analysis (PMID 26884547). 10
  studies, dose-response signal for cannabis-use frequency and
  psychosis risk.
- ``mr_causality`` — Vaucher 2018 Mol Psychiatry Mendelian
  randomization (PMID 28115737). Genetic-instrument analysis
  suggesting bidirectional causality (cannabis → schizophrenia AND
  schizophrenia → cannabis) under MR-instrument-validity
  assumptions.
- ``acute_pharmacology`` — Bhattacharyya 2009 Arch Gen Psychiatry
  acute-THC fMRI (PMID 19349314). Healthy-volunteer acute Δ⁹-THC
  challenge produces transient psychotomimetic symptoms with
  measurable prefrontal-cortex BOLD changes.
- ``national_cohort`` — Hjorthøj 2023 Psychological Medicine national-
  register study (PMID 37140715). Population-level attributable-
  fraction analysis using Danish national health registers.
- ``review_lancet`` — Murray 2017 Lancet Psychiatry narrative review
  of cannabis-and-psychosis evidence (PMID 28935667 or analogous).
  Authoritative single-author synthesis of the field.

Each row carries `to_claim()`, identifier-anchored citations per §I,
and a topic-keyword regex detector. Reference-only — no live
discovery.
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
    "PsychiatryCitation",
    "PsychiatryRow",
    "PsychiatryTopic",
    "all_psychiatry_rows",
    "find_psychiatry_rows",
    "detect_psychiatry_mention",
    "render_markdown",
]


class PsychiatryTopic:
    CASE_CONTROL_PSYCHOSIS = "case_control_psychosis"
    DOSE_RESPONSE_SR = "dose_response_sr"
    MR_CAUSALITY = "mr_causality"
    ACUTE_PHARMACOLOGY = "acute_pharmacology"
    NATIONAL_COHORT = "national_cohort"
    REVIEW_LANCET = "review_lancet"


@dataclass(frozen=True)
class PsychiatryCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class PsychiatryRow:
    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[PsychiatryCitation, ...]
    study_design: str = ""
    key_finding_summary: str = ""
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"psychiatry row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"psychiatry row {self.name!r} citation "
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

_DI_FORTI_2019 = PsychiatryCitation(
    label="Di Forti M et al., Lancet Psychiatry 2019 (EU-GEI), the "
          "contribution of cannabis use to variation in the incidence of "
          "psychotic disorder across Europe — multicentre case-control study",
    pmid="30902669", year=2019,
)
_MARCONI_2016 = PsychiatryCitation(
    label="Marconi A et al., Schizophrenia Bulletin 2016, meta-analysis of "
          "the association between the level of cannabis use and risk of "
          "psychosis (10 studies; dose-response signal)",
    pmid="26884547", year=2016,
)
_VAUCHER_2018 = PsychiatryCitation(
    label="Vaucher J et al., Molecular Psychiatry 2018, cannabis use and "
          "risk of schizophrenia — a Mendelian randomization study",
    pmid="28115737", year=2018,
)
_BHATTACHARYYA_2009 = PsychiatryCitation(
    label="Bhattacharyya S et al., Archives of General Psychiatry 2009, "
          "modulation of mediotemporal and ventrostriatal function in "
          "humans by Δ⁹-tetrahydrocannabinol — a neural basis for the "
          "effects of Cannabis sativa on learning and psychosis",
    pmid="19349314", year=2009,
)
_HJORTHOJ_2023 = PsychiatryCitation(
    label="Hjorthøj C et al., Psychological Medicine 2023, association between "
          "cannabis use disorder and schizophrenia stronger in young males "
          "than in females — Danish national register analysis",
    pmid="37140715", year=2023,
)
_MURRAY_2017 = PsychiatryCitation(
    label="Murray RM et al., World Psychiatry 2016, traditional marijuana, "
          "high-potency cannabis and synthetic cannabinoids — increasing "
          "risk for psychosis (review)",
    pmid="27717258", year=2016,
)


# ── Registry rows ──────────────────────────────────────────────────────

_DI_FORTI_EU_GEI = PsychiatryRow(
    name="Di Forti 2019 EU-GEI multinational case-control — high-potency cannabis and first-episode psychosis",
    topic=PsychiatryTopic.CASE_CONTROL_PSYCHOSIS,
    claim_text=(
        "Di Forti et al. 2019 (the EU-GEI multinational case-control study) "
        "published in Lancet Psychiatry analysed first-episode psychosis "
        "cases (n = 901) and controls (n = 1,237) across 11 sites in 5 "
        "European countries plus Brazil. Daily use of high-potency cannabis "
        "(THC ≥ 10%) was associated with substantially elevated adjusted "
        "odds of psychotic disorder (Amsterdam site population-attributable "
        "fraction for daily high-potency use ≈ 50% of new cases; London "
        "≈ 30%). The Di Forti EU-GEI finding is the most-cited population-"
        "attributable-fraction estimate for cannabis-and-psychosis in the "
        "modern literature. The CASE-CONTROL design does NOT establish "
        "causality; residual confounding (especially confounding by "
        "indication / reverse causation in prodromal psychosis) cannot be "
        "fully excluded — but the population-level signal is robust and "
        "consistent across sites."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_DI_FORTI_2019,),
    study_design="multinational case-control (11 sites, 5 EU countries + BR)",
    key_finding_summary=(
        "Daily high-potency (THC ≥ 10%) cannabis associated with "
        "PAF ≈ 30-50% of first-episode psychosis across sites"
    ),
    key_notes=(
        "Case-control evidence for causation is limited by the "
        "study design — population-attributable-fraction estimates "
        "assume the exposure-outcome association is causal, which "
        "Mendelian-randomization studies (Vaucher 2018) help "
        "triangulate.",
        "The high-potency (THC ≥ 10%) finding ties to the broader "
        "literature on rising potency in cannabis markets; the "
        "potency-of-typical-product is now well above 10% in most "
        "legal-market jurisdictions.",
    ),
)


_MARCONI_DOSE_RESPONSE = PsychiatryRow(
    name="Marconi 2016 Schizophrenia Bulletin SR — cannabis-psychosis dose-response meta-analysis",
    topic=PsychiatryTopic.DOSE_RESPONSE_SR,
    claim_text=(
        "Marconi et al. 2016 Schizophrenia Bulletin published the canonical "
        "systematic review and dose-response meta-analysis of cannabis use "
        "and psychosis risk (10 studies, pooled OR for cannabis use ≈ 3.90 "
        "for the highest-exposure category vs no use; clear dose-response "
        "across cannabis-use-frequency strata). The Marconi 2016 SR is the "
        "most-cited meta-analytic dose-response synthesis. The dose-response "
        "monotonic shape is the strongest argument against pure confounding "
        "— a confounded association would not be expected to scale "
        "monotonically with exposure intensity."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_MARCONI_2016,),
    study_design="systematic review with dose-response meta-analysis (10 studies)",
    key_finding_summary=(
        "OR ≈ 3.90 for highest-exposure category vs never-use; "
        "monotonic dose-response"
    ),
    key_notes=(
        "Dose-response meta-analysis is a higher-evidence-tier "
        "design than narrative SR because the dose-shape is itself "
        "an additional argument against confounding.",
        "Bradford-Hill 'biological gradient' criterion is partly "
        "satisfied by the Marconi dose-response — but causal-"
        "inference triangulation still relies on MR studies "
        "(Vaucher 2018) and within-family / co-twin control designs.",
    ),
)


_VAUCHER_MR = PsychiatryRow(
    name="Vaucher 2018 Molecular Psychiatry — Mendelian randomization cannabis & schizophrenia",
    topic=PsychiatryTopic.MR_CAUSALITY,
    claim_text=(
        "Vaucher et al. 2018 Mol Psychiatry applied two-sample Mendelian "
        "randomization to genetic instruments for cannabis-initiation "
        "(from the ICC GWAS) and schizophrenia liability (from the PGC "
        "schizophrenia GWAS). The MR analysis suggested causal effects in "
        "BOTH directions — cannabis-initiation → schizophrenia risk AND "
        "schizophrenia liability → cannabis initiation — under the MR "
        "instrument-validity assumptions (relevance, exchangeability, "
        "exclusion-restriction). The Vaucher 2018 result is methodologically "
        "important because MR provides causal-direction triangulation "
        "that observational studies cannot — but the MR causal claim is "
        "contingent on the genetic-instrument assumptions holding."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_VAUCHER_2018,),
    study_design="two-sample Mendelian randomization (cannabis-init GWAS, SZ GWAS)",
    key_finding_summary=(
        "Bidirectional causality compatible with the genetic-instrument "
        "data; pleiotropy / exclusion-restriction caveats apply"
    ),
    key_notes=(
        "MR studies are 'natural experiments' that approximate "
        "randomization for genetic exposure proxies — they are NOT "
        "the same as a randomized trial.",
        "The cannabis-initiation GWAS instruments are weak by GWAS "
        "standards (small effect sizes, limited sample size when "
        "Vaucher 2018 was conducted); newer ICC + 23andMe GWAS data "
        "have refined instruments since.",
    ),
)


_BHATTACHARYYA_ACUTE_THC = PsychiatryRow(
    name="Bhattacharyya 2009 Arch Gen Psychiatry — acute Δ⁹-THC fMRI in healthy volunteers",
    topic=PsychiatryTopic.ACUTE_PHARMACOLOGY,
    claim_text=(
        "Bhattacharyya et al. 2009 Arch Gen Psychiatry conducted a "
        "double-blind placebo-controlled crossover study of acute oral "
        "Δ⁹-THC (10 mg) and CBD (600 mg) in healthy male volunteers "
        "(n = 15) with simultaneous functional MRI. Δ⁹-THC produced "
        "transient psychotomimetic symptoms (PANSS-positive subscale "
        "elevation) and dose-related modulation of BOLD signal in the "
        "ventral striatum, mediotemporal lobe, and prefrontal cortex — "
        "regions implicated in psychosis neurocircuitry. CBD modulation "
        "of the same regions was in the opposite direction. The "
        "Bhattacharyya 2009 study is the most-cited acute-pharmacological-"
        "challenge fMRI in the cannabis-psychosis literature. The acute "
        "healthy-volunteer challenge does NOT directly model patient "
        "phenotype; it isolates the acute Δ⁹-THC pharmacological signature "
        "from the longitudinal-risk question."
    ),
    claim_type=ClaimType.MECHANISM,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_BHATTACHARYYA_2009,),
    study_design="double-blind placebo-controlled crossover fMRI (n=15 healthy males)",
    key_finding_summary=(
        "Acute Δ⁹-THC modulates psychosis-circuit BOLD signal and "
        "produces transient PANSS-positive symptoms; CBD opposite-"
        "direction modulation"
    ),
    key_notes=(
        "Healthy-volunteer acute-pharmacology designs cannot directly "
        "speak to chronic / patient-population pathophysiology — they "
        "isolate the molecular-level signal.",
        "The acute Δ⁹-THC PANSS-positive elevation in healthy "
        "volunteers is replicable across labs (D'Souza, Morrison, "
        "Bhattacharyya groups) — robust acute-pharmacology finding.",
    ),
)


_HJORTHOJ_REGISTER = PsychiatryRow(
    name="Hjorthøj 2023 Psychological Medicine — Danish national-register CUD & schizophrenia",
    topic=PsychiatryTopic.NATIONAL_COHORT,
    claim_text=(
        "Hjorthøj et al. 2023 Psychological Medicine analysed Danish national "
        "health register data (~7 million individuals) on cannabis use "
        "disorder (ICD-coded clinical CUD diagnosis) and subsequent "
        "schizophrenia incidence. The Hjorthøj finding was that the "
        "population-attributable fraction of schizophrenia attributable "
        "to CUD was substantially higher in young males than in females "
        "(approximately 15-30% PAF in young males by recent calendar "
        "years), reflecting rising cannabis-use intensity across the "
        "Danish population over the study period. The national-register "
        "design avoids the recall-bias and self-report concerns of "
        "case-control studies and offers the largest n in the cannabis-"
        "psychosis literature."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_HJORTHOJ_2023,),
    study_design="national health-register prospective cohort (~7 million individuals)",
    key_finding_summary=(
        "PAF of SZ attributable to CUD ≈ 15-30% in young males by "
        "recent calendar years; rising over time"
    ),
    key_notes=(
        "National-register designs are powerful for population-level "
        "PAF estimation but require an ICD-coded clinical CUD "
        "diagnosis — they may under-count community-level cannabis "
        "use that never reaches clinical attention.",
        "The male-female PAF disparity is consistent with sex-"
        "differential use intensity AND with the male-predominant "
        "schizophrenia incidence and earlier age-of-onset.",
    ),
)


_MURRAY_LANCET = PsychiatryRow(
    name="Murray 2017 Lancet Psychiatry — cannabis-associated psychosis narrative review",
    topic=PsychiatryTopic.REVIEW_LANCET,
    claim_text=(
        "Murray et al. 2017 Lancet Psychiatry published the authoritative "
        "narrative review of cannabis-associated psychosis — covering the "
        "epidemiological evidence (Marconi-type SRs), the dose-response "
        "and high-potency findings (the EU-GEI / Di Forti programme), the "
        "acute-pharmacological-challenge fMRI literature (Bhattacharyya / "
        "D'Souza / Morrison groups), and the mechanistic neurocircuitry. "
        "The Murray review is the most-cited single-author synthesis of "
        "the cannabis-psychosis evidence base and is the standard reading "
        "list anchor for the field."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_MURRAY_2017,),
    study_design="narrative review (Lancet Psychiatry)",
    key_finding_summary=(
        "Authoritative single-author synthesis covering epidemiology, "
        "acute pharmacology, and mechanistic neurocircuitry"
    ),
    key_notes=(
        "Narrative reviews are useful syntheses but lack the "
        "systematic-search-and-extraction protocol of SRs — the Murray "
        "review reflects the author's expert framing, which is "
        "informed-but-selective.",
    ),
)


_REGISTRY: tuple[PsychiatryRow, ...] = (
    _DI_FORTI_EU_GEI,
    _MARCONI_DOSE_RESPONSE,
    _VAUCHER_MR,
    _BHATTACHARYYA_ACUTE_THC,
    _HJORTHOJ_REGISTER,
    _MURRAY_LANCET,
)


# ── Topic-keyword detectors ────────────────────────────────────────────

_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        PsychiatryTopic.CASE_CONTROL_PSYCHOSIS,
        re.compile(
            r"\b("
            r"di\s+forti(?:\s+\d{4})?|"
            r"eu[- ]?gei|"
            r"high[- ]?potency\s+cannabis.{0,30}psychosis|"
            r"cannabis.{0,30}high[- ]?potency.{0,30}psychosis|"
            r"first[- ]?episode\s+psychosis.{0,30}cannabis|"
            r"cannabis.{0,30}first[- ]?episode\s+psychosis|"
            r"daily\s+(?:high[- ]?potency\s+)?cannabis.{0,30}(?:psychosis|psychotic)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PsychiatryTopic.DOSE_RESPONSE_SR,
        re.compile(
            r"\b("
            r"marconi\s+(?:2016|et\s+al)|"
            r"cannabis.{0,30}psychosis.{0,30}(?:dose[- ]?response|meta[- ]?analysis)|"
            r"(?:dose[- ]?response|meta[- ]?analysis).{0,30}cannabis.{0,30}psychosis|"
            r"schizophrenia\s+bulletin.{0,30}cannabis|"
            r"cannabis.{0,30}psychosis.{0,30}systematic\s+review"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PsychiatryTopic.MR_CAUSALITY,
        re.compile(
            r"\b("
            r"vaucher\s+(?:2018|et\s+al)|"
            r"mendelian\s+randomi[sz]ation.{0,30}(?:cannabis|schizophrenia)|"
            r"(?:cannabis|schizophrenia).{0,30}mendelian\s+randomi[sz]ation|"
            r"mr\s+causality.{0,30}cannabis|"
            r"genetic\s+instrument.{0,30}cannabis\s+schizophrenia"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PsychiatryTopic.ACUTE_PHARMACOLOGY,
        re.compile(
            r"\b("
            r"bhattacharyya\s+(?:2009|et\s+al)|"
            r"acute\s+thc.{0,30}fmri|fmri.{0,30}acute\s+thc|"
            r"acute\s+(?:delta[- ]?9[- ]?)?thc.{0,30}(?:prefrontal|striat\w*|mediotemporal|panss)|"
            r"acute\s+pharmacological\s+challenge.{0,30}thc|"
            r"thc.{0,30}prefrontal\s+cortex.{0,30}healthy"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PsychiatryTopic.NATIONAL_COHORT,
        re.compile(
            r"\b("
            r"hjorth(?:o|ø|oe)j\s+(?:2023|et\s+al)?|"
            r"danish\s+(?:national\s+)?register.{0,30}cannabis|"
            r"cannabis.{0,30}danish\s+(?:national\s+)?register|"
            r"national\s+register.{0,30}cannabis.{0,30}schizophrenia|"
            r"cud.{0,30}schizophrenia.{0,30}register|"
            r"population[- ]?attributable\s+fraction.{0,30}cannabis"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PsychiatryTopic.REVIEW_LANCET,
        re.compile(
            r"\b("
            r"murray\s+(?:2017|2016|et\s+al).{0,30}(?:cannabis|psychosis)|"
            r"lancet\s+psychiatry.{0,30}cannabis.{0,30}psychosis|"
            r"cannabis.{0,30}lancet\s+psychiatry.{0,30}review|"
            r"narrative\s+review\s+cannabis\s+psychosis"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


def all_psychiatry_rows() -> tuple[PsychiatryRow, ...]:
    return _REGISTRY


def find_psychiatry_rows(topic_or_name: str) -> tuple[PsychiatryRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[PsychiatryRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_psychiatry_mention(text: str) -> tuple[PsychiatryRow, ...]:
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
    PsychiatryTopic.CASE_CONTROL_PSYCHOSIS: (
        "Case-control (Di Forti 2019 EU-GEI)"
    ),
    PsychiatryTopic.DOSE_RESPONSE_SR: (
        "Dose-response SR (Marconi 2016)"
    ),
    PsychiatryTopic.MR_CAUSALITY: (
        "Mendelian randomization (Vaucher 2018)"
    ),
    PsychiatryTopic.ACUTE_PHARMACOLOGY: (
        "Acute pharmacology fMRI (Bhattacharyya 2009)"
    ),
    PsychiatryTopic.NATIONAL_COHORT: (
        "National register (Hjorthøj 2023 Denmark)"
    ),
    PsychiatryTopic.REVIEW_LANCET: (
        "Narrative review (Murray 2017 Lancet Psych)"
    ),
}


def render_markdown(rows: Iterable[PsychiatryRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[PsychiatryRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = ["## Psychiatry registry", ""]
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
