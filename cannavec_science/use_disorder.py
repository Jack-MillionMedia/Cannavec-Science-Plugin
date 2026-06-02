"""Cannabis use disorder & withdrawal-syndrome registry (spec 005 US2 / FR-002).

Research-grade outcome instruments and epidemiology for cannabis use
disorder (CUD) and cannabis withdrawal syndrome (CWS) — the
field-standard tools every cessation-trial protocol, withdrawal-
pharmacotherapy RCT, and treatment-as-prevention study cites. v0.4
returned 0-1 curated claims for these questions and surfaced the
Volkow 2014 NEJM review only; v0.5 ships a curated registry under
Constitution §IV (researcher-only) with primary citations per §I.

Topic coverage:

- ``dsm5_criteria`` — DSM-5 cannabis use disorder framework. Hasin
  2013 (PMID 23903334) is the field-standard publication describing
  the merger of abuse + dependence into a single severity-graded
  disorder (≥ 2 of 11 = mild; ≥ 4 = moderate; ≥ 6 = severe).
- ``screening_instrument`` — Cannabis Use Disorder Identification
  Test – Revised (CUDIT-R). Adamson 2010 (PMID 20347232) developed
  the 8-item cannabis-specific revision of the WHO AUDIT framework;
  modern protocols use the CUDIT-R as the screening tool.
- ``withdrawal_scale`` — Cannabis Withdrawal Scale (CWS). Allsop 2011
  (PMID 21724338) developed and validated the 19-item self-report
  scale used in essentially every cannabis-withdrawal trial.
- ``prevalence`` — CUD lifetime / 12-month prevalence. Hasin 2015
  (PMID 26502112) NESARC-III is the field-standard US population
  prevalence reference (~3% 12-month, ~6.3% lifetime under DSM-5).
- ``heritability`` — CUD heritability. Verweij 2010 (PMID 20402985)
  twin-and-family meta-analysis estimates broad-sense heritability
  ~0.51-0.59 for cannabis dependence (DSM-IV framework, comparable
  to other substance-use disorders).
- ``age_of_onset`` — telescoping effect / adolescent-onset risk.
  Chen 2009 (PMID 19022584) for the telescoping effect; Hall &
  Degenhardt 2009 (PMID 19837255) for adolescent-onset dependence-
  trajectory data.

Each row carries `to_claim()` returning a typed Claim, identifier-
anchored citations per §I, and is matched by a topic-keyword regex
detector. The module is reference-only.
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
    "UseDisorderCitation",
    "UseDisorderRow",
    "UseDisorderTopic",
    "all_use_disorder_rows",
    "find_use_disorder_rows",
    "detect_use_disorder_mention",
    "render_markdown",
]


class UseDisorderTopic:
    DSM5_CRITERIA = "dsm5_criteria"
    SCREENING_INSTRUMENT = "screening_instrument"
    WITHDRAWAL_SCALE = "withdrawal_scale"
    PREVALENCE = "prevalence"
    HERITABILITY = "heritability"
    AGE_OF_ONSET = "age_of_onset"


@dataclass(frozen=True)
class UseDisorderCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class UseDisorderRow:
    """One curated cannabis-use-disorder primary-source-anchored claim."""

    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[UseDisorderCitation, ...]
    instrument_name: str = ""    # DSM-5 / CUDIT-R / CWS / NESARC-III etc.
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"use-disorder row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"use-disorder row {self.name!r} citation "
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
            "instrument_name": self.instrument_name,
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {"label": c.label, "pmid": c.pmid, "doi": c.doi, "year": c.year}
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_HASIN_2013 = UseDisorderCitation(
    label="Hasin DS et al., Am J Psychiatry 2013, DSM-5 criteria for "
          "substance use disorders — recommendations and rationale",
    pmid="23903334", year=2013,
)
_ADAMSON_2010 = UseDisorderCitation(
    label="Adamson SJ et al., Drug Alcohol Depend 2010, an improved brief "
          "measure of cannabis misuse — the Cannabis Use Disorders "
          "Identification Test-Revised (CUDIT-R)",
    pmid="20347232", year=2010,
)
_ALLSOP_2011 = UseDisorderCitation(
    label="Allsop DJ et al., Drug Alcohol Depend 2011, the Cannabis "
          "Withdrawal Scale development — patterns and predictors of "
          "cannabis withdrawal and distress",
    pmid="21724338", year=2011,
)
_HASIN_2015 = UseDisorderCitation(
    label="Hasin DS et al., JAMA Psychiatry 2015, prevalence of marijuana "
          "use disorders in the United States between 2001-2002 and "
          "2012-2013 (NESARC-III)",
    pmid="26502112", year=2015,
)
_VERWEIJ_2010 = UseDisorderCitation(
    label="Verweij KJ et al., Addiction 2010, genetic and environmental "
          "influences on cannabis use initiation and problematic use — "
          "a meta-analysis of twin studies",
    pmid="20402985", year=2010,
)
_CHEN_2009 = UseDisorderCitation(
    label="Chen CY et al., Addict Behav 2009, early-onset drug use "
          "and risk for drug dependence problems",
    pmid="19022584", year=2009,
)
_HALL_DEGENHARDT_2009 = UseDisorderCitation(
    label="Hall W & Degenhardt L, Lancet 2009, adverse health effects of "
          "non-medical cannabis use",
    pmid="19837255", year=2009,
)
_BUDNEY_2004 = UseDisorderCitation(
    label="Budney AJ et al., Am J Psychiatry 2004, review of the validity "
          "and significance of cannabis withdrawal syndrome",
    pmid="15514394", year=2004,
)
_VOLKOW_2014 = UseDisorderCitation(
    label="Volkow ND et al., NEJM 2014, adverse health effects of marijuana "
          "use (CUD-risk context)",
    pmid="24897085", year=2014,
)


# ── Registry rows ──────────────────────────────────────────────────────


_DSM5_CRITERIA = UseDisorderRow(
    name="DSM-5 cannabis use disorder diagnostic criteria",
    topic=UseDisorderTopic.DSM5_CRITERIA,
    claim_text=(
        "DSM-5 (American Psychiatric Association, 2013) consolidated the "
        "DSM-IV abuse / dependence distinction into a single severity-"
        "graded cannabis use disorder (CUD) with 11 criteria across four "
        "domains (impaired control, social impairment, risky use, "
        "pharmacological — including tolerance and withdrawal). Severity "
        "is graded by criterion count: ≥ 2 of 11 = mild, ≥ 4 of 11 = "
        "moderate, ≥ 6 of 11 = severe. Cannabis withdrawal is a DSM-5-"
        "recognised diagnosis (added in DSM-5; absent from DSM-IV). The "
        "merger broadened identified prevalence relative to DSM-IV "
        "dependence and is the modern field-standard outcome framework."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    instrument_name="DSM-5 (American Psychiatric Association, 2013)",
    citations=(_HASIN_2013,),
    key_notes=(
        "DSM-IV → DSM-5 transition: legal problems criterion removed; "
        "craving criterion added. The two changes plus the abuse/"
        "dependence merger explain the headline prevalence shift in "
        "Hasin 2015 NESARC-III.",
        "ICD-11 (WHO, 2022) uses a parallel framework but the criterion "
        "count and thresholds differ — DSM-5 is the US / research "
        "standard; ICD-11 is the international / clinical standard.",
    ),
)


_CUDIT_R = UseDisorderRow(
    name="CUDIT-R — Cannabis Use Disorder Identification Test–Revised",
    topic=UseDisorderTopic.SCREENING_INSTRUMENT,
    claim_text=(
        "CUDIT-R (Adamson 2010) is the 8-item self-report screening "
        "instrument for cannabis use disorder, derived as a cannabis-"
        "specific revision of the WHO AUDIT framework. A score of ≥ 8 "
        "out of 32 indicates probable CUD with sensitivity and specificity "
        "in the 80-90% range against DSM-IV abuse/dependence diagnostic "
        "interview. CUDIT-R is the modern research-standard cannabis-use "
        "screening tool — primary care and treatment-seeking cohort "
        "protocols cite it routinely."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    instrument_name="CUDIT-R (Adamson et al., 2010)",
    citations=(_ADAMSON_2010,),
    key_notes=(
        "CUDIT-R is shorter than the original CUDIT (10 items reduced "
        "to 8) and has improved psychometric properties; the original "
        "CUDIT is now superseded.",
        "The ≥ 8 threshold has been re-validated against DSM-5 CUD in "
        "several cohorts; some recent work suggests a higher threshold "
        "(≥ 10-12) is appropriate for DSM-5 moderate-or-severe CUD.",
    ),
)


_CWS = UseDisorderRow(
    name="Cannabis Withdrawal Scale (CWS) — Allsop 2011 19-item self-report",
    topic=UseDisorderTopic.WITHDRAWAL_SCALE,
    claim_text=(
        "The Cannabis Withdrawal Scale (CWS; Allsop 2011) is a 19-item "
        "self-report inventory of withdrawal-symptom severity validated "
        "in cannabis-dependent adults during medically-supervised "
        "abstinence. Items map to the DSM-5 cannabis-withdrawal criteria "
        "(irritability, anger, anxiety, sleep difficulty, decreased "
        "appetite, restlessness, depressed mood, somatic complaints — "
        "fever, chills, sweating, headache, abdominal pain) plus craving "
        "and functional-impact items. CWS total score 0-190 scaled by "
        "10-point bands; the field-standard outcome measure for cannabis-"
        "withdrawal-pharmacotherapy RCTs."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    instrument_name="CWS (Allsop et al., 2011)",
    citations=(_ALLSOP_2011, _BUDNEY_2004),
    key_notes=(
        "Cannabis withdrawal peaks 2-6 days after cessation and largely "
        "resolves by 2-3 weeks — the CWS time-course tracks this "
        "trajectory in dependent users.",
        "Cannabis Withdrawal Symptom Checklist (CWSC, Budney 2004) is "
        "an older and more commonly-cited instrument with similar item "
        "structure but less psychometric validation than CWS — both are "
        "in use in the literature.",
    ),
)


_PREVALENCE = UseDisorderRow(
    name="CUD lifetime / 12-month prevalence — NESARC-III (Hasin 2015)",
    topic=UseDisorderTopic.PREVALENCE,
    claim_text=(
        "Hasin 2015 (JAMA Psychiatry) NESARC-III adult US population "
        "survey reports a 12-month DSM-5 cannabis use disorder prevalence "
        "of approximately 2.9% and a lifetime prevalence of approximately "
        "6.3%. Prevalence is highest in young adults (18-29) and in "
        "males. The NESARC-III estimates are substantially higher than "
        "DSM-IV-dependence-only estimates from the prior NESARC wave, "
        "reflecting both the DSM-IV → DSM-5 broadening and a true "
        "increase in cannabis use prevalence over the 2001-02 to 2012-13 "
        "interval."
    ),
    claim_type=ClaimType.EDUCATIONAL,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    instrument_name="NESARC-III (US National Epidemiologic Survey on Alcohol and Related Conditions)",
    citations=(_HASIN_2015, _VOLKOW_2014),
    key_notes=(
        "NESARC-III used in-person AUDADIS-5 structured interview "
        "(n=36,309 US adults) — the most rigorously sampled US CUD "
        "prevalence dataset.",
        "Post-NESARC-III state-level legalization rollout has changed "
        "the use-prevalence baseline; CUD-prevalence may have shifted "
        "further but no equally-rigorous national resampling has been "
        "published.",
    ),
)


_HERITABILITY = UseDisorderRow(
    name="CUD heritability — twin & family meta-analysis (Verweij 2010)",
    topic=UseDisorderTopic.HERITABILITY,
    claim_text=(
        "Verweij 2010 twin-study meta-analysis estimates broad-sense "
        "heritability of cannabis use initiation at ~0.40-0.48 and "
        "heritability of problematic cannabis use / cannabis dependence "
        "at ~0.51-0.59. Shared environmental effects are substantial for "
        "use initiation (~0.25-0.30) but minimal for dependence, "
        "consistent with classic substance-use-disorder twin findings. "
        "The CUD heritability magnitude is comparable to alcohol use "
        "disorder and other major substance use disorders."
    ),
    claim_type=ClaimType.EDUCATIONAL,
    evidence_level=EvidenceLevel.C,
    # Quantitative twin-study meta-analysis published in Addiction —
    # JOURNAL_RCT tier (specialist journal quantitative synthesis).
    # SR_FLAGSHIP would overstate (reserved for Cochrane / AHRQ / NICE /
    # WHO clinical SR; the Verweij meta-analysis is epidemiologic).
    source_tier=SourceTier.JOURNAL_RCT,
    instrument_name="Twin-study meta-analysis",
    citations=(_VERWEIJ_2010,),
    key_notes=(
        "Twin-based heritability estimates and SNP-based heritability "
        "estimates (from GWAS) routinely diverge for substance use "
        "disorders — the missing-heritability gap is an active research "
        "area; CUD GWAS efforts are catalogued in the gwas_discover lane.",
        "DSM-IV cannabis-dependence framework was used in most of the "
        "Verweij-meta-analysis cohort studies; equivalent DSM-5 CUD "
        "heritability estimates are not yet published.",
    ),
)


_AGE_OF_ONSET = UseDisorderRow(
    name="Telescoping effect & adolescent-onset CUD risk",
    topic=UseDisorderTopic.AGE_OF_ONSET,
    claim_text=(
        "Adolescent-onset cannabis use (initiation < 16 years) is "
        "associated with substantially higher lifetime risk of progressing "
        "to cannabis dependence (~17% vs ~9% for adult-onset users; the "
        "telescoping effect — time from initiation to dependence — is "
        "compressed in early-onset users). Chen 2009 documented the "
        "telescoping framework for cannabis among other substances; "
        "Hall & Degenhardt 2009 reviewed the dose-response between "
        "frequency / chronicity of adolescent use and adult dependence "
        "trajectories. Adolescent-onset use is also associated with "
        "elevated risk of cognitive sequelae, lower educational "
        "attainment, and incident psychotic disorder in vulnerable "
        "subgroups."
    ),
    claim_type=ClaimType.EDUCATIONAL,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    instrument_name="NESARC + NSDUH cohort framework",
    citations=(_CHEN_2009, _HALL_DEGENHARDT_2009, _VOLKOW_2014),
    key_notes=(
        "Causal interpretation of adolescent-onset associations is "
        "contested — confounding by family environment, peer-effect, "
        "and pre-existing conduct/mood symptoms is non-trivial. The "
        "best-controlled designs are co-twin discordant-exposure "
        "studies (Lynskey 2003, Verweij 2017).",
        "Adolescent-onset adverse-trajectory data is the basis of "
        "most public-health-framing harm-reduction messaging — the "
        "risk is age-graded, not all-or-nothing.",
    ),
)


_REGISTRY: tuple[UseDisorderRow, ...] = (
    _DSM5_CRITERIA,
    _CUDIT_R,
    _CWS,
    _PREVALENCE,
    _HERITABILITY,
    _AGE_OF_ONSET,
)


# ── Topic-keyword detectors ────────────────────────────────────────────


_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        UseDisorderTopic.DSM5_CRITERIA,
        re.compile(
            r"\b("
            r"dsm[- ]?5|dsm[- ]?iv|dsm[- ]?5[- ]?tr|"
            r"cannabis\s+use\s+disorder\s+(?:diagnost\w*|criteria|framework)|"
            r"cud\s+(?:criteria|framework|diagnost\w*)|"
            r"hasin\s+2013|"
            r"abuse[- ]?dependence\s+merge\w*"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        UseDisorderTopic.SCREENING_INSTRUMENT,
        re.compile(
            r"\b("
            r"cudit[- ]?r|cudit\b|"
            r"cannabis\s+use\s+disorder\s+identif\w*\s+test|"
            r"adamson\s+2010|"
            r"cannabis\s+(?:screen\w*|screen-?ing)\s+(?:instrument|tool)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        UseDisorderTopic.WITHDRAWAL_SCALE,
        re.compile(
            r"\b("
            r"cannabis\s+withdrawal\s+(?:scale|syndrome|symptom\w*|assessment)|"
            r"cws\s+(?:cannabis|allsop)|"
            r"allsop\s+2011|"
            r"cannabis\s+withdrawal\s+symptom\s+checklist|cwsc|"
            r"budney\s+2004|"
            r"cannabis\s+withdrawal|"
            r"marijuana\s+withdrawal"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        UseDisorderTopic.PREVALENCE,
        re.compile(
            r"\b("
            r"nesarc(?:[- ]?iii)?|"
            r"(?:cud|cannabis\s+use\s+disorder)\s+prevalence|"
            r"prevalence\s+(?:of\s+)?(?:cud|cannabis\s+use\s+disorder)|"
            r"hasin\s+2015|"
            r"(?:lifetime|12[- ]?month)\s+cud\s+prevalence|"
            r"audadis[- ]?5"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        UseDisorderTopic.HERITABILITY,
        re.compile(
            r"\b("
            r"(?:cud|cannabis\s+(?:dependence|use\s+disorder))\s+heritabil\w*|"
            r"heritabil\w*\s+(?:of\s+)?(?:cud|cannabis\s+(?:dependence|use\s+disorder))|"
            r"twin\s+study\s+(?:of\s+)?cannabis|"
            r"verweij\s+2010|"
            r"cannabis\s+twin\s+(?:study|cohort)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        UseDisorderTopic.AGE_OF_ONSET,
        re.compile(
            r"\b("
            r"adolescent[- ]?onset\s+(?:cannabis|cud|marijuana)|"
            r"early[- ]?onset\s+(?:cannabis|cud|marijuana)|"
            r"telescop\w*\s+(?:cannabis|cud)|"
            r"(?:cannabis|cud)\s+telescop\w*|"
            r"age[- ]?of[- ]?onset\s+(?:cannabis|cud)|"
            r"chen\s+2009\s+(?:cannabis|drug\s+depend\w*)|"
            r"hall\s+(?:&\s+)?degenhardt\s+2009"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# ── Public API ─────────────────────────────────────────────────────────


def all_use_disorder_rows() -> tuple[UseDisorderRow, ...]:
    return _REGISTRY


def find_use_disorder_rows(
    topic_or_name: str,
) -> tuple[UseDisorderRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out: list[UseDisorderRow] = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_use_disorder_mention(text: str) -> tuple[UseDisorderRow, ...]:
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
    UseDisorderTopic.DSM5_CRITERIA: "DSM-5 cannabis use disorder framework",
    UseDisorderTopic.SCREENING_INSTRUMENT: "Screening instrument (CUDIT-R)",
    UseDisorderTopic.WITHDRAWAL_SCALE: "Cannabis Withdrawal Scale (CWS)",
    UseDisorderTopic.PREVALENCE: "CUD prevalence (NESARC-III)",
    UseDisorderTopic.HERITABILITY: "CUD heritability (twin studies)",
    UseDisorderTopic.AGE_OF_ONSET: "Adolescent-onset & telescoping effect",
}


def render_markdown(rows: Iterable[UseDisorderRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[UseDisorderRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = []
    lines.append("## Cannabis use disorder & withdrawal registry")
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
            if r.instrument_name:
                lines.append(f"  - Instrument: {r.instrument_name}")
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
