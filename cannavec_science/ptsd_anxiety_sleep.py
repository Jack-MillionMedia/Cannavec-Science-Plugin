"""PTSD / anxiety / sleep registry (spec 006 US4 / FR-004).

Research-grade primary literature on cannabis / cannabinoid effects on
PTSD, social-anxiety-disorder (SAD), sleep, and acute-anxiety dose-
response. Spec 005 returned 0-1 curated claims for every prompt;
mood / anxiety / sleep is the largest commercial-claim space and the
literature is sparser and more cautionary than commercial copy
suggests — exactly the asymmetric correction the deterministic
backbone exists to make.

Topic coverage:

- ``ptsd_rct`` — Bonn-Miller 2021 PLOS One the-only-RCT in PTSD
  (PMID 33730032). Cannabis pharmacotherapy in U.S. veterans with
  PTSD; primary endpoints were largely negative on Clinician-
  Administered PTSD Scale change. Often-cited as "evidence FOR
  cannabis in PTSD" but the primary read of the trial is far more
  cautious.
- ``sad_acute_challenge`` — CBD social-anxiety-disorder acute
  challenge: Crippa 2011 J Psychopharmacol (PMID 20829306) and
  Bergamaschi 2011 Neuropsychopharm public-speaking simulation
  (PMID 21307846). Small mechanistic studies in SAD patients
  showing acute CBD anxiolysis on standardized stressor paradigms.
- ``sleep_sr`` — Suraev 2020 Sleep Med Rev SR (PMID 32603954) of
  cannabinoid therapies for sleep disorders. Concluded the evidence
  base is insufficient (moderate-to-high risk of bias) — exactly the
  asymmetric correction to the marketing-copy-implied story.
- ``acute_anxiety_dose_response`` — Childs 2017 Drug Alcohol Depend
  (PMID 28599212) on dose-dependent acute Δ⁹-THC effects on stress.
  Low Δ⁹-THC doses (~5 mg oral) produce anxiolysis; higher doses
  (15+ mg) produce anxiogenesis — the biphasic dose-response that
  underlies clinical-safety considerations.
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
    "PtsdAnxietySleepCitation",
    "PtsdAnxietySleepRow",
    "PtsdAnxietySleepTopic",
    "all_ptsd_anxiety_sleep_rows",
    "find_ptsd_anxiety_sleep_rows",
    "detect_ptsd_anxiety_sleep_mention",
    "render_markdown",
]


class PtsdAnxietySleepTopic:
    PTSD_RCT = "ptsd_rct"
    SAD_ACUTE_CHALLENGE = "sad_acute_challenge"
    SLEEP_SR = "sleep_sr"
    ACUTE_ANXIETY_DOSE_RESPONSE = "acute_anxiety_dose_response"


@dataclass(frozen=True)
class PtsdAnxietySleepCitation:
    label: str
    pmid: str | None = None
    doi: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class PtsdAnxietySleepRow:
    name: str
    topic: str
    claim_text: str
    claim_type: ClaimType
    evidence_level: EvidenceLevel
    source_tier: SourceTier
    citations: tuple[PtsdAnxietySleepCitation, ...]
    indication: str = ""
    key_finding_summary: str = ""
    last_verified: str = "2026-05-24"
    watch_pmids: tuple[str, ...] = ()
    key_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                f"ptsd-anxiety-sleep row {self.name!r} must have ≥ 1 citation"
            )
        for c in self.citations:
            if not (c.pmid or c.doi):
                raise ValueError(
                    f"ptsd-anxiety-sleep row {self.name!r} citation "
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
            "indication": self.indication,
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

_BONN_MILLER_2021 = PtsdAnxietySleepCitation(
    label="Bonn-Miller MO et al., PLOS One 2021, the short-term impact of "
          "3 smoked cannabis preparations versus placebo on PTSD symptoms — "
          "a randomized cross-over clinical trial",
    pmid="33730032", year=2021,
)
_CRIPPA_2011 = PtsdAnxietySleepCitation(
    label="Crippa JAS et al., Journal of Psychopharmacology 2011, neural "
          "basis of anxiolytic effects of cannabidiol (CBD) in generalized "
          "social anxiety disorder — a preliminary report",
    pmid="20829306", year=2011,
)
_BERGAMASCHI_2011 = PtsdAnxietySleepCitation(
    label="Bergamaschi MM et al., Neuropsychopharmacology 2011, cannabidiol "
          "reduces the anxiety induced by simulated public speaking in "
          "treatment-naïve social phobia patients",
    pmid="21307846", year=2011,
)
# Re-cited from the unverifiable "Bedi 2010" / "Walsh 2017" labels (whose
# PMIDs resolved to unrelated papers) to the verified Childs 2017 / Suraev 2020
# papers whose findings they actually described; variable names retained for
# reference stability.
_BEDI_2010 = PtsdAnxietySleepCitation(
    label="Childs E, Lutz JA & de Wit H, Drug and Alcohol Dependence 2017, "
          "dose-related effects of Δ⁹-tetrahydrocannabinol on emotional "
          "responses to acute psychosocial stress",
    pmid="28599212", year=2017,
)
_WALSH_2017 = PtsdAnxietySleepCitation(
    label="Suraev AS et al., Sleep Medicine Reviews 2020, cannabinoid "
          "therapies in the management of sleep disorders — a systematic "
          "review of preclinical and clinical studies",
    pmid="32603954", year=2020,
)
_VELZEBOER_2022 = PtsdAnxietySleepCitation(
    label="Velzeboer R et al., Sleep 2022, cannabis dosing and "
          "administration for sleep — a systematic review",
    pmid="36107800", year=2022,
)


# ── Registry rows ──────────────────────────────────────────────────────

_BONN_MILLER_PTSD = PtsdAnxietySleepRow(
    name="Bonn-Miller 2021 PLOS One — PTSD smoked-cannabis cross-over RCT in US veterans",
    topic=PtsdAnxietySleepTopic.PTSD_RCT,
    claim_text=(
        "Bonn-Miller et al. 2021 PLOS One conducted the first (and as of "
        "v0.6 still the only) randomized cross-over clinical trial of "
        "smoked-cannabis vs placebo in US veterans with PTSD (n = 80). "
        "Three smoked-cannabis preparations were tested — high-Δ⁹-THC / "
        "low-CBD (~12% THC / ~0% CBD), high-CBD / low-Δ⁹-THC (~11% CBD / "
        "~1% THC), and Δ⁹-THC + CBD combination (~7.9% / ~8.1%) vs "
        "placebo (~0%). The PRIMARY ENDPOINT was Clinician-Administered "
        "PTSD Scale for DSM-5 (CAPS-5) change at end-of-stage. The "
        "primary endpoint was LARGELY NEGATIVE — no statistically "
        "significant difference between any active preparation and "
        "placebo on CAPS-5 change. Secondary self-report measures showed "
        "some positive signals. The Bonn-Miller 2021 trial is often "
        "miscited as 'evidence FOR cannabis in PTSD'; the primary read "
        "is much more cautious — the trial provides limited Level B "
        "evidence that smoked cannabis at common potencies did NOT "
        "outperform placebo on the field-standard PTSD endpoint."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.B,
    source_tier=SourceTier.JOURNAL_RCT,
    citations=(_BONN_MILLER_2021,),
    indication="PTSD (US veterans)",
    key_finding_summary=(
        "Primary endpoint (CAPS-5 change) LARGELY NEGATIVE; secondary "
        "self-report signals mixed — cautious interpretation required"
    ),
    key_notes=(
        "The trial used a within-subject cross-over with smoked "
        "cannabis — generalizability to oral / oromucosal "
        "formulations (e.g. nabiximols) is limited.",
        "PTSD treatment trials are notoriously sensitive to "
        "placebo response; the negative primary-endpoint result "
        "is consistent with the broader literature on PTSD "
        "pharmacotherapy.",
        "NASEM 2017 classified PTSD evidence as 'limited' — "
        "Bonn-Miller 2021 does not change that classification.",
    ),
)


_CRIPPA_SAD = PtsdAnxietySleepRow(
    name="Crippa 2011 + Bergamaschi 2011 — acute CBD in social anxiety disorder",
    topic=PtsdAnxietySleepTopic.SAD_ACUTE_CHALLENGE,
    claim_text=(
        "Two small mechanistic studies addressed acute CBD effects in "
        "treatment-naïve social-anxiety-disorder (SAD) patients. Crippa "
        "et al. 2011 J Psychopharmacol (n = 10 SAD patients) used SPECT "
        "neuroimaging to show acute oral CBD (400 mg) altered regional "
        "cerebral blood flow in limbic / paralimbic regions vs placebo "
        "with concurrent reductions in subjective anxiety. Bergamaschi "
        "et al. 2011 Neuropsychopharmacology (n = 24 SAD patients, plus "
        "12 healthy controls) used a simulated public-speaking paradigm "
        "to show acute oral CBD (600 mg) significantly reduced anxiety, "
        "cognitive impairment, and discomfort during the speech task. "
        "These two studies are the most-cited acute-CBD-in-SAD primary "
        "evidence — but each is small, mechanistic, and uses an acute-"
        "challenge paradigm rather than a longitudinal-treatment design. "
        "They support proof-of-concept anxiolysis but not chronic-"
        "treatment efficacy."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_CRIPPA_2011, _BERGAMASCHI_2011),
    indication="Social anxiety disorder (acute CBD challenge)",
    key_finding_summary=(
        "Acute CBD (400-600 mg oral) anxiolysis on standardized stressor "
        "paradigms; small samples, acute paradigm, no longitudinal data"
    ),
    key_notes=(
        "Both studies used oral CBD doses (400-600 mg) at the upper "
        "end of investigational doses — well above the 25-75 mg/day "
        "wellness doses common in commercial CBD products.",
        "The simulated-public-speaking paradigm has been validated as "
        "a standardized stressor for SAD research but does not "
        "directly model real-world social-anxiety exposure.",
    ),
)


_BEDI_ANXIETY = PtsdAnxietySleepRow(
    name="Childs 2017 Drug Alcohol Depend — biphasic acute Δ⁹-THC anxiety/stress dose-response",
    topic=PtsdAnxietySleepTopic.ACUTE_ANXIETY_DOSE_RESPONSE,
    claim_text=(
        "Childs, Lutz & de Wit 2017 (Drug and Alcohol Dependence) ran a "
        "double-blind randomized trial (N = 42 healthy volunteers) of oral "
        "Δ⁹-THC (0, 7.5, or 12.5 mg) administered before the Trier Social "
        "Stress Test. The low 7.5 mg dose significantly reduced self-"
        "reported distress and attenuated appraisal of the stressor as "
        "threatening, whereas the higher 12.5 mg dose increased negative "
        "mood both before and during the tasks and impaired task "
        "performance. This dose-related (biphasic) pattern — low-dose "
        "stress-relief, higher-dose negative mood — is the best-"
        "characterized controlled-laboratory evidence for why 'cannabis "
        "for anxiety' framing requires dose-context disambiguation, and "
        "underlies start-low / go-slow oral-cannabinoid titration guidance."
    ),
    claim_type=ClaimType.PHARMACOKINETIC,
    evidence_level=EvidenceLevel.C,
    source_tier=SourceTier.SINGLE_ARM_OR_MECH,
    citations=(_BEDI_2010,),
    indication="Acute Δ⁹-THC dose-response (healthy volunteers)",
    key_finding_summary=(
        "Biphasic dose-response — low Δ⁹-THC anxiolytic / high "
        "Δ⁹-THC anxiogenic in controlled lab paradigm"
    ),
    key_notes=(
        "Biphasic Δ⁹-THC dose-response is consistent across "
        "controlled-dose labs (Childs, Bidwell, Hindocha groups); "
        "the threshold between low / high dose is highly individual.",
        "The biphasic shape is a textbook example of why 'cannabis "
        "for anxiety' framing requires dose-context disambiguation — "
        "the same molecule can be anxiolytic or anxiogenic.",
    ),
)


_WALSH_SLEEP = PtsdAnxietySleepRow(
    name="Suraev 2020 Sleep Med Rev — cannabinoids and sleep-disorders systematic review",
    topic=PtsdAnxietySleepTopic.SLEEP_SR,
    claim_text=(
        "Suraev et al. 2020 (Sleep Medicine Reviews) systematically "
        "reviewed cannabinoid therapies for sleep disorders across 14 "
        "preclinical and 12 clinical studies. The review concluded there "
        "is insufficient evidence to support routine clinical use of "
        "cannabinoid therapies for any sleep disorder, citing a moderate-"
        "to-high risk of bias across most studies to date. It identified "
        "promising preliminary signals — a rationale for future RCTs in "
        "sleep apnea, insomnia, PTSD-related nightmares, restless legs "
        "syndrome, REM-sleep behaviour disorder, and narcolepsy — but "
        "stressed the need for larger, rigorously controlled, longer-term "
        "trials. It is an essential primary-source corrective to "
        "marketing-implied 'cannabis for sleep' framings. A second "
        "systematic review (Velzeboer et al. 2022, Sleep; 31 studies) "
        "converged on the same verdict — sleep benefits were inconsistent "
        "and concentrated in pain-related sleep disturbance, with "
        "heterogeneity precluding specific dosing recommendations."
    ),
    claim_type=ClaimType.CLINICAL_EFFICACY,
    evidence_level=EvidenceLevel.A,
    source_tier=SourceTier.SR_FLAGSHIP,
    citations=(_WALSH_2017, _VELZEBOER_2022),
    indication="Sleep (across formulations)",
    key_finding_summary=(
        "Limited and inconclusive evidence; some short-term signals "
        "in pain-related sleep disturbance; no robust primary-"
        "treatment evidence"
    ),
    key_notes=(
        "Cannabis-for-sleep is one of the largest commercial-claim "
        "spaces; the Suraev 2020 SR's 'insufficient evidence' "
        "verdict is an essential primary-source corrective.",
        "The Suraev SR stresses a moderate-to-high risk of bias across "
        "the cannabinoid-sleep literature — complicating simple "
        "'cannabis improves sleep' framings.",
    ),
)


_REGISTRY: tuple[PtsdAnxietySleepRow, ...] = (
    _BONN_MILLER_PTSD,
    _CRIPPA_SAD,
    _BEDI_ANXIETY,
    _WALSH_SLEEP,
    PtsdAnxietySleepRow(
        # Alias row separating Bergamaschi from Crippa for find() / topic
        # surfacing, even though both cite together in the SAD row.
        name="Bergamaschi 2011 Neuropsychopharm — public-speaking CBD acute challenge",
        topic=PtsdAnxietySleepTopic.SAD_ACUTE_CHALLENGE,
        claim_text=(
            "Bergamaschi et al. 2011 Neuropsychopharm conducted the "
            "simulated-public-speaking-paradigm acute oral CBD (600 mg) "
            "study in treatment-naïve social-anxiety-disorder (SAD) "
            "patients (n = 24) plus healthy controls (n = 12). Acute CBD "
            "significantly reduced anxiety, cognitive impairment, and "
            "discomfort during the public-speaking task. The Bergamaschi "
            "2011 study is the most-cited single CBD-in-SAD primary "
            "study — small, mechanistic, but high-quality double-blind "
            "design at the upper end of investigational doses."
        ),
        claim_type=ClaimType.CLINICAL_EFFICACY,
        evidence_level=EvidenceLevel.C,
        source_tier=SourceTier.SINGLE_ARM_OR_MECH,
        citations=(_BERGAMASCHI_2011,),
        indication="Social anxiety disorder (CBD 600 mg oral acute)",
        key_finding_summary=(
            "Acute oral CBD 600 mg reduces anxiety + cognitive impairment "
            "during simulated-public-speaking task in SAD patients (n=24)"
        ),
        key_notes=(
            "600 mg oral CBD is well above commercial-product daily "
            "doses (typically 25-75 mg); generalisability to wellness-"
            "product dosing is unwarranted.",
        ),
    ),
)


# ── Topic-keyword detectors ────────────────────────────────────────────

_TOPIC_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        PtsdAnxietySleepTopic.PTSD_RCT,
        re.compile(
            r"\b("
            r"bonn[- ]?miller\s+(?:2021|et\s+al)|"
            r"ptsd.{0,30}(?:cannabis|cannabinoid).{0,30}(?:rct|trial|randomi[sz]ed)|"
            r"(?:cannabis|cannabinoid).{0,30}ptsd.{0,30}(?:rct|trial|randomi[sz]ed)|"
            r"veterans.{0,30}(?:cannabis|cannabinoid).{0,30}ptsd|"
            r"caps[- ]?5.{0,30}cannabis|"
            r"ptsd\s+cannabis\s+(?:trial|rct|study)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PtsdAnxietySleepTopic.SAD_ACUTE_CHALLENGE,
        re.compile(
            r"\b("
            r"crippa\s+(?:2011|et\s+al)|"
            r"bergamaschi\s+(?:2011|et\s+al)|"
            r"cbd.{0,30}social\s+anxiety|social\s+anxiety.{0,30}cbd|"
            r"public[- ]?speaking.{0,30}(?:cbd|cannabidiol)|"
            r"(?:cbd|cannabidiol).{0,30}public[- ]?speaking|"
            r"sad.{0,30}(?:cbd|cannabidiol)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PtsdAnxietySleepTopic.SLEEP_SR,
        re.compile(
            r"\b("
            r"suraev\s+(?:2020|et\s+al)|"
            r"cannabis.{0,30}sleep.{0,30}(?:systematic|review|sr|meta[- ]?analysis)|"
            r"(?:systematic|review|sr|meta[- ]?analysis).{0,30}cannabis.{0,30}sleep|"
            r"cannabinoid\w*\s+sleep.{0,30}(?:systematic|review|sr)|"
            r"sleep\s+medicine\s+reviews?.{0,30}cannabis"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        PtsdAnxietySleepTopic.ACUTE_ANXIETY_DOSE_RESPONSE,
        re.compile(
            r"\b("
            r"childs\s+(?:2017|et\s+al)|"
            r"acute\s+thc.{0,30}anxiety|anxiety.{0,30}acute\s+thc|"
            r"biphasic.{0,30}(?:thc|cannabinoid).{0,30}anxiety|"
            r"(?:thc|cannabinoid)\s+anxiety\s+dose[- ]?response|"
            r"low\s+dose\s+thc.{0,30}anxi(?:ety|olytic)"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


def all_ptsd_anxiety_sleep_rows() -> tuple[PtsdAnxietySleepRow, ...]:
    return _REGISTRY


def find_ptsd_anxiety_sleep_rows(
    topic_or_name: str,
) -> tuple[PtsdAnxietySleepRow, ...]:
    if not topic_or_name:
        return ()
    q = topic_or_name.lower().strip()
    out = []
    for row in _REGISTRY:
        if q == row.topic.lower() or q in row.name.lower():
            out.append(row)
    return tuple(out)


def detect_ptsd_anxiety_sleep_mention(
    text: str,
) -> tuple[PtsdAnxietySleepRow, ...]:
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
    PtsdAnxietySleepTopic.PTSD_RCT: "PTSD RCT (Bonn-Miller 2021)",
    PtsdAnxietySleepTopic.SAD_ACUTE_CHALLENGE: (
        "Acute CBD in social anxiety (Crippa 2011 / Bergamaschi 2011)"
    ),
    PtsdAnxietySleepTopic.SLEEP_SR: (
        "Sleep SR (Walsh 2017 Sleep Med Rev)"
    ),
    PtsdAnxietySleepTopic.ACUTE_ANXIETY_DOSE_RESPONSE: (
        "Biphasic acute Δ⁹-THC anxiety (Bedi 2010)"
    ),
}


def render_markdown(rows: Iterable[PtsdAnxietySleepRow]) -> str:
    rows = tuple(rows)
    if not rows:
        return ""
    by_topic: dict[str, list[PtsdAnxietySleepRow]] = {}
    for r in rows:
        by_topic.setdefault(r.topic, []).append(r)
    lines: list[str] = ["## PTSD / anxiety / sleep registry", ""]
    for topic, display in _TOPIC_DISPLAY_NAMES.items():
        bucket = by_topic.get(topic)
        if not bucket:
            continue
        lines.append(f"### {display}")
        lines.append("")
        for r in bucket:
            lines.append(f"- **{r.name}** ({r.evidence_level.value})")
            lines.append(f"  - {r.claim_text}")
            if r.indication:
                lines.append(f"  - Indication: {r.indication}")
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
