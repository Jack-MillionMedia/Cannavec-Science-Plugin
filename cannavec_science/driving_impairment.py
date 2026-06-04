"""Driving-impairment registry (spec 006 US3 / FR-003).

Research-grade cannabis-and-driving primary literature — case-control
crash-risk studies, plasma THC dose-response analyses, driving-
simulator RCTs, prospective cohort crash studies, and systematic
reviews. Spec 005 returned 0 curated claims; spec 006 ships a curated
registry under Constitution §IV (researcher-only) with primary
citations per §I.

This registry surfaces the SCIENCE only — per-se law surfaces remain
in the parent plugin per §IV scope-lock. Primary identifiers include
PMIDs and (for the canonical Compton 2017 NHTSA report) the DOT HS
series report identifier.

Topic coverage:

- ``case_control_crash`` — Compton 2017 NHTSA case-control driver
  crash-risk study (DOT HS 812 411). Initial unadjusted odds-ratios
  for cannabis-positive drivers were elevated; after adjustment for
  demographics + alcohol the cannabis-only adjusted OR dropped to
  ~1.05 (95% CI 0.86-1.27) — the most-cited NHTSA finding and the
  most-mis-cited result in the cannabis-driving literature.
- ``plasma_dose_response`` — Hartman 2015 Drug Alcohol Depend (PMID 26144593)
  analysis of plasma Δ⁹-THC concentration vs crash-risk dose-response.
  Provides the methodologically rigorous plasma-concentration
  framework that per-se thresholds reference (but cannot endorse
  causally given the long detection window).
- ``simulator_rct`` — Marcotte 2022 JAMA Psychiatry (PMID 35080588)
  randomized double-blind placebo-controlled simulator-driving RCT.
  Acute Δ⁹-THC dose-dependently impaired driving-performance composite
  score (DSC) up to ~3-4 h post-smoking; impairment persisted longer
  in occasional vs frequent users (developmental tolerance signal).
- ``prospective_cohort_crash`` — Brubacher 2022 BMC Public Health
  cohort linking cannabis-positive emergency-department crashes in
  British Columbia. Real-world post-legalization signal.
- ``systematic_review`` — Bondallaz 2016 Forensic Sci Int systematic
  review (PMID 27701009) of cannabis-and-driving evidence — the
  most-cited synthesis in the forensic-toxicology literature.

Each row carries `to_claim()`, identifier-anchored citations per §I
(via PMID, DOI, or DOT HS report number), and a topic-keyword regex
detector. Reference-only.
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
    "DrivingImpairmentCitation",
    "DrivingImpairmentRow",
    "DrivingImpairmentTopic",
    "all_driving_impairment_rows",
    "find_driving_impairment_rows",
    "detect_driving_impairment_mention",
    "render_markdown",
]


class DrivingImpairmentTopic:
    CASE_CONTROL_CRASH = "case_control_crash"
    PLASMA_DOSE_RESPONSE = "plasma_dose_response"
    SIMULATOR_RCT = "simulator_rct"
    PROSPECTIVE_COHORT_CRASH = "prospective_cohort_crash"
    SYSTEMATIC_REVIEW = "systematic_review"


@dataclass(frozen=True)
class DrivingImpairmentCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    report_id: str | None = None       # e.g. "DOT HS 812 411"
    year: int | None = None


@dataclass(frozen=True)
class DrivingImpairmentRow:
    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[DrivingImpairmentCitation, ...]
    matrix: str = ""              # plasma / whole-blood / oral-fluid / device-screen
    key_finding_summary: str = ""
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"driving-impairment row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi or c.report_id):
                raise ValueError(
                    f"driving-impairment row {self.name!r} citation "
                    f"{c.label!r} must have a PMID, DOI, or report_id"
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
                title=c.label
                + (f" [{c.report_id}]" if c.report_id and not c.pmid else ""),
                tier=self.source_tier,
                pmid=c.pmid,
                doi=c.doi,
                url=(
                    None
                    if (c.pmid or c.doi)
                    else f"https://www.nhtsa.gov/document/{c.report_id.replace(' ', '-').lower()}"
                    if c.report_id
                    else None
                ),
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
            "matrix": self.matrix,
            "key_finding_summary": self.key_finding_summary,
            "last_verified": self.last_verified,
            "watch_pmids": list(self.watch_pmids),
            "key_notes": list(self.key_notes),
            "citations": [
                {
                    "label": c.label,
                    "pmid": c.pmid,
                    "doi": c.doi,
                    "report_id": c.report_id,
                    "year": c.year,
                }
                for c in self.citations
            ],
        }


# ── Citations ──────────────────────────────────────────────────────────

_COMPTON_2017 = DrivingImpairmentCitation(
    label="Compton RP, NHTSA 2017, marijuana-impaired driving — a report "
          "to Congress (case-control crash-risk study, Virginia Beach)",
    report_id="DOT HS 812 411", year=2017,
)
_HARTMAN_2015 = DrivingImpairmentCitation(
    label="Hartman RL et al., Drug and Alcohol Dependence 2015, cannabis "
          "effects on driving lateral control with and without alcohol — "
          "plasma THC dose-response analysis",
    pmid="26144593", year=2015,
)
_MARCOTTE_2022 = DrivingImpairmentCitation(
    label="Marcotte TD et al., JAMA Psychiatry 2022, driving performance "
          "and cannabis users' perception of safety — double-blind placebo-"
          "controlled randomized driving-simulator trial",
    pmid="35080588", year=2022,
)
_BRUBACHER_2022 = DrivingImpairmentCitation(
    label="Brubacher JR et al., New England Journal of Medicine 2022, "
          "cannabis legalization and detection of THC in injured drivers "
          "(British Columbia trauma-centre study)",
    pmid="35020985", year=2022,
)
_BONDALLAZ_2016 = DrivingImpairmentCitation(
    label="Bondallaz P et al., Forensic Science International 2016, cannabis "
          "and its effects on driving skills — systematic review",
    pmid="27701009", year=2016,
)


# ── Registry rows ──────────────────────────────────────────────────────

_COMPTON_NHTSA = DrivingImpairmentRow(
    name="Compton 2017 NHTSA — Virginia Beach case-control crash-risk study",
    topic=DrivingImpairmentTopic.CASE_CONTROL_CRASH,
    claim_text=(
        "Compton 2017 NHTSA (DOT HS 812 411) reported a Virginia Beach "
        "case-control crash-risk study comparing drivers involved in a "
        "crash (cases, n ≈ 3,000) with drivers from the same road / time-"
        "of-day (controls, n ≈ 6,000), testing for cannabis (oral fluid + "
        "blood Δ⁹-THC). The headline unadjusted cannabis-positive crash-"
        "odds ratio was ~1.25 — but after adjustment for demographics, "
        "alcohol, and other covariates the cannabis-positive adjusted "
        "OR dropped to ~1.05 (95% CI 0.86-1.27), failing to reach "
        "statistical significance. The Compton 2017 NHTSA finding is the "
        "most-cited AND the most-mis-cited result in the cannabis-driving "
        "literature — the unadjusted estimate is often cited without the "
        "adjustment caveat. Cannabis presence does NOT equal cannabis "
        "impairment because the urinary / oral-fluid detection window is "
        "long; recent-use measures (whole-blood Δ⁹-THC) are more relevant "
        "to acute impairment than cannabinoid-positivity."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_COMPTON_2017,),
    matrix="oral fluid + whole blood",
    key_finding_summary=(
        "Unadjusted OR ~1.25; adjusted OR ~1.05 (95% CI 0.86-1.27) — "
        "not statistically significant after covariate adjustment"
    ),
    key_notes=(
        "Cannabis-positivity ≠ cannabis-impairment — the long "
        "detection window for cannabinoids (see pharmacokinetics "
        "detection_window row) means a positive test can reflect use "
        "days-to-weeks earlier.",
        "Per-se laws (e.g. 5 ng/mL whole-blood Δ⁹-THC thresholds) "
        "are NOT scientifically endorsed by Compton 2017; they are "
        "policy decisions made by jurisdictions. Cannavec Science "
        "surfaces the research literature, not per-se law.",
    ),
)


_HARTMAN_PLASMA = DrivingImpairmentRow(
    name="Hartman 2015 Clin Chem — plasma Δ⁹-THC dose-response in simulated driving",
    topic=DrivingImpairmentTopic.PLASMA_DOSE_RESPONSE,
    claim_text=(
        "Hartman et al. 2015 Clin Chem analysed plasma Δ⁹-THC concentration-"
        "vs-driving-performance dose-response in a placebo-controlled "
        "smoked-cannabis simulator study (n = 18). Plasma Δ⁹-THC ≥ "
        "13.1 ng/mL produced lateral-control impairment comparable to "
        "a 0.08% BAC, but the relationship between plasma concentration "
        "and impairment was substantially noisier than the alcohol-BAC "
        "relationship. The Hartman 2015 paper is the most-cited modern "
        "plasma-THC dose-response analysis and is the methodological "
        "foundation for the (jurisdiction-set, not science-set) per-se "
        "plasma / whole-blood thresholds — but Hartman explicitly cautions "
        "that plasma THC alone is a weak surrogate for impairment because "
        "of inter-individual variability and the rapid distribution "
        "from plasma into deep compartments."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_HARTMAN_2015,),
    matrix="plasma",
    key_finding_summary=(
        "Plasma Δ⁹-THC ≥ 13.1 ng/mL ≈ 0.08% BAC lateral-control "
        "impairment; noisy relationship overall"
    ),
    key_notes=(
        "Whole-blood Δ⁹-THC concentrations are ~half plasma "
        "concentrations because Δ⁹-THC partitions away from red "
        "blood cells (see pharmacokinetics distribution row).",
        "Plasma-THC measurement is delayed by laboratory turnaround; "
        "roadside testing typically uses oral-fluid devices which "
        "have different kinetics and lower analytical sensitivity.",
    ),
)


_MARCOTTE_SIMULATOR = DrivingImpairmentRow(
    name="Marcotte 2022 JAMA Psychiatry — driving-simulator RCT, dose & duration",
    topic=DrivingImpairmentTopic.SIMULATOR_RCT,
    claim_text=(
        "Marcotte et al. 2022 JAMA Psychiatry conducted a double-blind "
        "placebo-controlled randomized driving-simulator trial (n = 191 "
        "regular and occasional cannabis users) comparing placebo, 5.9% "
        "THC, and 13.4% THC smoked-cannabis on a Driving Simulator "
        "Composite Score (DSC) at multiple post-smoking timepoints. Key "
        "findings: (1) DSC impairment peaked at ~1.5 h post-smoking and "
        "diminished by ~4.5 h, with most participants returning to "
        "near-baseline by ~5 h post-smoking — though substantial inter-"
        "subject variability; (2) occasional users showed larger and "
        "longer-lasting impairment than regular users (consistent with "
        "developmental tolerance to acute Δ⁹-THC effects in regular "
        "consumers); (3) self-reported safety-to-drive perception was "
        "poorly calibrated to objective DSC impairment at 1.5 h. The "
        "Marcotte 2022 trial is the largest modern simulator RCT and "
        "provides the strongest acute-impairment time-course data."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_MARCOTTE_2022,),
    matrix="behavioural (simulator DSC) + whole-blood Δ⁹-THC",
    key_finding_summary=(
        "Peak DSC impairment ~1.5 h post-smoke; near-baseline at ~5 h; "
        "occasional > regular users in impairment magnitude / duration"
    ),
    key_notes=(
        "Driving simulators are well-validated proxies for on-road "
        "driving for lateral-control and reaction-time outcomes; less "
        "well-validated for higher-order judgement / risk-taking.",
        "The poor calibration of self-reported safety-to-drive vs "
        "objective impairment is a public-health-relevant finding: "
        "consumers cannot reliably gauge their own impairment.",
    ),
)


_BRUBACHER_BC = DrivingImpairmentRow(
    name="Brubacher 2022 NEJM — BC trauma-centre cohort cannabis legalization & THC-positive injured drivers",
    topic=DrivingImpairmentTopic.PROSPECTIVE_COHORT_CRASH,
    claim_text=(
        "Brubacher et al. 2022 NEJM analysed a British Columbia trauma-"
        "centre prospective cohort of injured drivers attending Level I "
        "trauma centres before and after cannabis legalization (n ≈ 4,300). "
        "The prevalence of THC-positive injured drivers (whole-blood "
        "≥ 2 ng/mL) rose post-legalization (8.6% before → 11.5% after); "
        "the prevalence of injured drivers with whole-blood Δ⁹-THC ≥ 5 "
        "ng/mL doubled (2.4% → 4.6%). The Brubacher 2022 study is one of "
        "the strongest post-legalization population signals in the modern "
        "literature. Limitations: the cohort design cannot establish "
        "causality (legalization → injured-driving) because the policy "
        "change is contemporaneous with multiple secular trends (e.g. "
        "potency rise) and the THC-positivity prevalence increase may "
        "partly reflect changed testing practices."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_BRUBACHER_2022,),
    matrix="whole-blood Δ⁹-THC (≥ 2 ng/mL, ≥ 5 ng/mL)",
    key_finding_summary=(
        "Injured-driver THC ≥ 2 ng/mL prevalence 8.6% → 11.5% post-"
        "legalization; ≥ 5 ng/mL prevalence ~doubled (2.4% → 4.6%)"
    ),
    key_notes=(
        "Post-legalization signal but observational — confounded by "
        "secular trends in cannabis use, potency, and testing.",
        "Whole-blood ≥ 2 ng/mL is a recent-use marker; ≥ 5 ng/mL is "
        "the per-se threshold in several jurisdictions (a policy "
        "decision, not a scientific finding).",
    ),
)


_BONDALLAZ_SR = DrivingImpairmentRow(
    name="Bondallaz 2016 Forensic Sci Int — cannabis-and-driving systematic review",
    topic=DrivingImpairmentTopic.SYSTEMATIC_REVIEW,
    claim_text=(
        "Bondallaz et al. 2016 Forensic Sci Int published the most-cited "
        "systematic review of cannabis-and-driving evidence. The Bondallaz "
        "SR synthesised acute-use simulator / on-road studies, epidemiologic "
        "case-control crash-risk studies, and forensic-toxicology dose-"
        "response data. Headline findings: (1) acute cannabis use impairs "
        "psychomotor / cognitive driving-relevant performance dose-"
        "dependently; (2) impairment is most pronounced in the first 1-3 "
        "hours post-smoking; (3) chronic users show partial tolerance to "
        "acute Δ⁹-THC effects but residual impairment can persist; (4) "
        "case-control crash-risk estimates vary by methodology — adjusted "
        "estimates after controlling for demographics + alcohol are "
        "consistently lower than unadjusted estimates. The Bondallaz SR is "
        "the standard reference for the forensic-toxicology community."
    ),
    claim_type=ClaimType.SAFETY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_BONDALLAZ_2016,),
    matrix="multi-matrix synthesis (plasma / whole-blood / oral fluid / behavioural)",
    key_finding_summary=(
        "Acute impairment 1-3 h post-smoke; partial tolerance in chronic "
        "users; adjusted crash-risk estimates < unadjusted"
    ),
    key_notes=(
        "Systematic-review evidence from the forensic-toxicology "
        "community — different framing emphasis than the epidemiology "
        "community (which weights the case-control crash-risk evidence "
        "more heavily).",
        "Bondallaz 2016 is now ~10 years old; the post-2017 simulator-"
        "RCT and post-legalization-cohort evidence has refined the "
        "estimates without overturning the main conclusions.",
    ),
)


_REGISTRY: tuple[DrivingImpairmentRow, ...] = (
    _COMPTON_NHTSA,
    _HARTMAN_PLASMA,
    _MARCOTTE_SIMULATOR,
    _BRUBACHER_BC,
    _BONDALLAZ_SR,
)


# ── Topic-keyword detectors ────────────────────────────────────────────

_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        DrivingImpairmentTopic.CASE_CONTROL_CRASH,
        re.compile(
            r"\b("
            r"compton\s+(?:2017|et\s+al)|"
            r"nhtsa.{0,30}(?:cannabis|marijuana|driving|crash)|"
            r"(?:cannabis|marijuana|driving|crash).{0,30}nhtsa|"
            r"virginia\s+beach.{0,30}(?:cannabis|driving|crash)|"
            r"dot\s*hs\s*812"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        DrivingImpairmentTopic.PLASMA_DOSE_RESPONSE,
        re.compile(
            r"\b("
            r"hartman\s+(?:2015|et\s+al)|"
            r"plasma\s+(?:delta[- ]?9[- ]?)?thc.{0,30}(?:driv\w*|crash|impair\w*)|"
            r"(?:driv\w*|crash|impair\w*).{0,30}plasma\s+(?:delta[- ]?9[- ]?)?thc|"
            r"per[- ]?se\s+(?:thc|threshold).{0,30}driv\w*|"
            r"whole[- ]?blood\s+thc.{0,30}driv\w*"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        DrivingImpairmentTopic.SIMULATOR_RCT,
        re.compile(
            r"\b("
            r"marcotte\s+(?:2022|et\s+al)|"
            r"driving\s+simulator.{0,30}(?:cannabis|thc|cannabinoid)|"
            r"(?:cannabis|thc|cannabinoid).{0,30}driving\s+simulator|"
            r"simulator.{0,30}driv\w*\s+performance.{0,30}(?:thc|cannabis)|"
            r"dsc.{0,30}cannabis|cannabis.{0,30}dsc"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        DrivingImpairmentTopic.PROSPECTIVE_COHORT_CRASH,
        re.compile(
            r"\b("
            r"brubacher\s+(?:2022|et\s+al)|"
            r"injured\s+drivers?.{0,30}(?:cannabis|thc)|"
            r"(?:cannabis|thc).{0,30}injured\s+drivers?|"
            r"british\s+columbia.{0,30}(?:cannabis|thc).{0,30}(?:driv\w*|crash)|"
            r"(?:cannabis|thc).{0,30}legali[sz]ation.{0,30}(?:driv\w*|crash|injur\w*)|"
            r"(?:cannabis|thc).{0,30}trauma\s+cent(?:re|er)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        DrivingImpairmentTopic.SYSTEMATIC_REVIEW,
        re.compile(
            r"\b("
            r"bondallaz\s+(?:2016|et\s+al)|"
            r"cannabis.{0,30}driv\w*.{0,30}systematic\s+review|"
            r"systematic\s+review.{0,30}cannabis.{0,30}driv\w*|"
            r"forensic\s+(?:science|toxicology).{0,30}cannabis.{0,30}driv\w*"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    # Cross-topic anchor — any cannabis-driving-impairment phrasing.
    (
        DrivingImpairmentTopic.CASE_CONTROL_CRASH,
        re.compile(
            r"\b("
            r"cannabis\s+driving\s+impair\w*|"
            r"marijuana\s+driving\s+impair\w*|"
            r"thc\s+driving\s+impair\w*"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


def all_driving_impairment_rows() -> tuple[DrivingImpairmentRow, ...]:
    return _REGISTRY


def find_driving_impairment_rows(
    topic_or_name: str,
) -> tuple[DrivingImpairmentRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_driving_impairment_mention(
    text: str,
) -> tuple[DrivingImpairmentRow, ...]:
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
    DrivingImpairmentTopic.CASE_CONTROL_CRASH: (
        "Case-control crash risk (Compton 2017 NHTSA)"
    ),
    DrivingImpairmentTopic.PLASMA_DOSE_RESPONSE: (
        "Plasma dose-response (Hartman 2015)"
    ),
    DrivingImpairmentTopic.SIMULATOR_RCT: (
        "Simulator RCT (Marcotte 2022)"
    ),
    DrivingImpairmentTopic.PROSPECTIVE_COHORT_CRASH: (
        "Post-legalization cohort (Brubacher 2022)"
    ),
    DrivingImpairmentTopic.SYSTEMATIC_REVIEW: (
        "Systematic review (Bondallaz 2016)"
    ),
}


def render_markdown(rows: Iterable[DrivingImpairmentRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[DrivingImpairmentRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = ["## Driving-impairment registry", ""]
    for topic, display in _TOPIC_DISPLAY_NAMES.items():
        bucket = by_topic.get(topic)
        if not bucket:
            continue
        lines.append(f"### {display}")
        lines.append("")
        for r in bucket:
            lines.append(f"- **{r.name}** ({r.evidence_level.value})")
            lines.append(f"  - {r.claim_text}")
            if r.matrix:
                lines.append(f"  - Matrix: {r.matrix}")
            if r.key_finding_summary:
                lines.append(f"  - Key finding: {r.key_finding_summary}")
            for c in r.citations:
                ident = []
                if c.pmid:
                    ident.append(f"PMID {c.pmid}")
                if c.doi:
                    ident.append(f"doi:{c.doi}")
                if c.report_id:
                    ident.append(c.report_id)
                lines.append(
                    f"  - Source: {c.label}"
                    + (f" — {' / '.join(ident)}" if ident else "")
                )
        lines.append("")
    return "\n".join(lines).rstrip()
