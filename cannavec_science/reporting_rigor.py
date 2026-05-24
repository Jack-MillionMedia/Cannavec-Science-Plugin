"""Reporting-guideline & risk-of-bias rigor detectors (spec 006 US5 / FR-005).

Deterministic detectors that fire when prompt text mentions a study-
design class without acknowledging the appropriate EQUATOR-network
reporting guideline (CONSORT for RCTs, PRISMA-2020 for SRs, STROBE
for observational studies) or risk-of-bias / quality-appraisal tool
(ROB-2 for RCTs, ROBINS-I for non-randomized intervention studies,
AMSTAR-2 for SR quality).

Each detector is a regex pair:

- **trigger** regex matches study-design language;
- **acknowledgment** regex matches the appropriate guideline / tool
  mention.

If trigger fires AND acknowledgment fires, the detector is silent.
If trigger fires AND acknowledgment does NOT fire, the detector
raises a ``ReportingGuidelineViolation``.

The detectors complement the existing seven cannabis-specific rigor
checks (isomer / receptor-id / dose-route / THCA-vs-THC / matrix-
unit / decarb-context / entourage). They share the
:class:`cannavec_science.rigor_checks.RigorCheckReport` envelope.

Reference primary sources (PMIDs) for each guideline are anchored in
:data:`REPORTING_GUIDELINE_PMIDS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


__all__ = [
    "ReportingGuideline",
    "ReportingGuidelineViolation",
    "REPORTING_GUIDELINE_PMIDS",
    "detect_missing_consort",
    "detect_missing_prisma",
    "detect_missing_strobe",
    "detect_missing_rob2",
    "detect_missing_robins_i",
    "detect_missing_amstar2",
    "run_reporting_rigor_checks",
]


class ReportingGuideline(str, Enum):
    CONSORT = "CONSORT"
    PRISMA = "PRISMA"
    STROBE = "STROBE"
    STARD = "STARD"
    CHEERS = "CHEERS"
    ROB_2 = "ROB-2"
    ROBINS_I = "ROBINS-I"
    AMSTAR_2 = "AMSTAR-2"
    QUADAS_2 = "QUADAS-2"


REPORTING_GUIDELINE_PMIDS: dict[ReportingGuideline, str] = {
    ReportingGuideline.CONSORT: "20335313",       # Schulz 2010 BMJ
    ReportingGuideline.PRISMA: "33781993",        # Page 2021 BMJ
    ReportingGuideline.STROBE: "17938396",        # von Elm 2007 PLoS Med
    ReportingGuideline.STARD: "26511519",         # Bossuyt 2015 BMJ
    ReportingGuideline.CHEERS: "35613756",        # Husereau 2022 BMJ
    ReportingGuideline.ROB_2: "31462531",         # Sterne 2019 BMJ
    ReportingGuideline.ROBINS_I: "27733354",      # Sterne 2016 BMJ
    ReportingGuideline.AMSTAR_2: "28935701",      # Shea 2017 BMJ
    ReportingGuideline.QUADAS_2: "22007046",      # Whiting 2011 Ann Intern Med
}


@dataclass(frozen=True)
class ReportingGuidelineViolation:
    kind: ReportingGuideline
    span: tuple[int, int]
    why: str
    recommendation_pmid: str
    anchor_text: str


# ── Trigger / acknowledgment regex pairs ──────────────────────────────

_RCT_TRIGGER = re.compile(
    r"\b("
    r"randomi[sz]ed\s+controlled\s+trial|"
    r"randomi[sz]ed\s+(?:clinical\s+)?trial|"
    r"\brct\b|"
    r"double[- ]?blind\s+placebo[- ]?controlled\s+(?:randomi[sz]ed\s+)?trial|"
    r"double[- ]?blind\s+randomi[sz]ed|"
    r"placebo[- ]?controlled\s+randomi[sz]ed"
    r")\b",
    re.IGNORECASE,
)
_CONSORT_ACKNOWLEDGED = re.compile(
    r"\b("
    r"consort(?:[- ]?\d{4})?|"
    r"consolidated\s+standards?\s+of\s+reporting\s+trials"
    r")\b",
    re.IGNORECASE,
)


_SR_TRIGGER = re.compile(
    r"\b("
    r"systematic\s+review|"
    r"meta[- ]?analysis|"
    r"\bsr\s+and\s+meta[- ]?analysis|"
    r"network\s+meta[- ]?analysis|"
    r"\bipd[- ]?meta[- ]?analysis"
    r")\b",
    re.IGNORECASE,
)
_PRISMA_ACKNOWLEDGED = re.compile(
    r"\b("
    r"prisma(?:[- ]?\d{4})?|"
    r"preferred\s+reporting\s+items\s+for\s+systematic\s+reviews"
    r")\b",
    re.IGNORECASE,
)


_OBSERVATIONAL_TRIGGER = re.compile(
    r"\b("
    r"(?:prospective|retrospective)\s+(?:observational\s+)?cohort|"
    r"observational\s+(?:cohort|study|design)|"
    r"case[- ]?control\s+(?:study|design)|"
    r"cross[- ]?sectional\s+(?:study|design|survey)|"
    r"nested\s+case[- ]?control"
    r")\b",
    re.IGNORECASE,
)
_STROBE_ACKNOWLEDGED = re.compile(
    r"\b("
    r"strobe(?:[- ]?compliant)?|"
    r"strengthening\s+the\s+reporting\s+of\s+observational\s+studies"
    r")\b",
    re.IGNORECASE,
)


_BIAS_APPRAISAL_RCT_TRIGGER = re.compile(
    r"\b("
    r"appraise\w*\s+(?:the\s+)?risk\s+of\s+bias\s+(?:of|in|for)\s+"
    r"(?:the\s+)?(?:included\s+)?(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|rcts?)|"
    r"risk\s+of\s+bias\s+(?:appraisal|assessment)\s+(?:of|in|for)\s+"
    r"(?:the\s+)?(?:included\s+)?(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|rcts?)|"
    r"bias\s+(?:appraisal|assessment)\s+(?:of|in|for)\s+"
    r"(?:the\s+)?(?:included\s+)?(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|rcts?)|"
    r"appraise\w*\s+bias\s+(?:of|in)\s+(?:the\s+)?(?:included\s+)?"
    r"(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|rcts?)|"
    r"appraise\w*\s+(?:included\s+)?(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|rcts?)\s+"
    r"(?:for\s+)?(?:risk\s+of\s+)?bias|"
    r"appraised\s+(?:the\s+)?(?:risk\s+of\s+)?bias\s+(?:of\s+|in\s+)?"
    r"(?:the\s+)?(?:included\s+)?(?:randomi[sz]ed\s+(?:controlled\s+)?trials?|rcts?)"
    r")\b",
    re.IGNORECASE,
)
_ROB_2_ACKNOWLEDGED = re.compile(
    r"\b("
    r"rob[- ]?2|rob2|"
    r"cochrane\s+(?:rob|risk[- ]?of[- ]?bias)\s*2|"
    r"cochrane\s+risk\s+of\s+bias\s+2(?:[- ].*)?|"
    r"risk\s+of\s+bias\s+(?:tool\s+)?2|"
    r"updated\s+cochrane\s+risk[- ]?of[- ]?bias"
    r")\b",
    re.IGNORECASE,
)


_BIAS_APPRAISAL_NRSI_TRIGGER = re.compile(
    r"\b("
    r"(?:appraise|assess)\w*\s+(?:the\s+)?risk\s+of\s+bias\s+(?:of|in|for)\s+"
    r"(?:the\s+)?(?:included\s+)?non[- ]?randomi[sz]ed\s+(?:intervention\s+)?stud(?:y|ies)|"
    r"bias\s+(?:appraisal|assessment)\s+(?:of|in|for)\s+(?:the\s+)?"
    r"(?:included\s+)?non[- ]?randomi[sz]ed\s+(?:intervention\s+)?stud(?:y|ies)|"
    r"appraised\s+(?:the\s+)?(?:risk\s+of\s+)?bias\s+(?:of\s+|in\s+)?(?:the\s+)?"
    r"non[- ]?randomi[sz]ed\s+(?:intervention\s+)?stud(?:y|ies)|"
    r"appraised\s+risk\s+of\s+bias\s+in\s+the\s+non[- ]?randomi[sz]ed"
    r")\b",
    re.IGNORECASE,
)
_ROBINS_I_ACKNOWLEDGED = re.compile(
    r"\b("
    r"robins[- ]?i|"
    r"risk[- ]?of[- ]?bias\s+in\s+non[- ]?randomi[sz]ed\s+studies\s+of\s+interventions"
    r")\b",
    re.IGNORECASE,
)


_SR_QUALITY_TRIGGER = re.compile(
    r"\b("
    r"(?:evaluate|appraise|assess)\w*\s+(?:the\s+)?(?:methodological\s+)?"
    r"quality\s+(?:of|in)\s+(?:the\s+)?(?:included\s+)?systematic\s+reviews?|"
    r"methodological\s+quality\s+(?:appraisal|assessment)\s+(?:of|in|for)\s+"
    r"(?:the\s+)?(?:included\s+)?systematic\s+reviews?|"
    r"quality\s+appraisal\s+(?:of|in|for)\s+(?:the\s+)?(?:included\s+)?systematic\s+reviews?"
    r")\b",
    re.IGNORECASE,
)
_AMSTAR_2_ACKNOWLEDGED = re.compile(
    r"\b("
    r"amstar[- ]?2|amstar\s+2|"
    r"a\s+measurement\s+tool\s+to\s+assess\s+systematic\s+reviews"
    r")\b",
    re.IGNORECASE,
)


def _detector(
    text: str,
    trigger: re.Pattern[str],
    acknowledged: re.Pattern[str],
    kind: ReportingGuideline,
    why: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    if not text:
        return ()
    m = trigger.search(text)
    if not m:
        return ()
    if acknowledged.search(text):
        return ()
    return (
        ReportingGuidelineViolation(
            kind=kind,
            span=m.span(),
            why=why,
            recommendation_pmid=REPORTING_GUIDELINE_PMIDS[kind],
            anchor_text=m.group(0),
        ),
    )


def detect_missing_consort(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    return _detector(
        text,
        _RCT_TRIGGER,
        _CONSORT_ACKNOWLEDGED,
        ReportingGuideline.CONSORT,
        why=(
            "Randomized-controlled-trial reporting should follow the "
            "CONSORT-2010 statement (Schulz et al. 2010 BMJ, PMID "
            "20335313). The text describes an RCT without acknowledging "
            "CONSORT — recommend explicit CONSORT-statement compliance."
        ),
    )


def detect_missing_prisma(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    return _detector(
        text,
        _SR_TRIGGER,
        _PRISMA_ACKNOWLEDGED,
        ReportingGuideline.PRISMA,
        why=(
            "Systematic-review / meta-analysis reporting should follow "
            "the PRISMA-2020 statement (Page et al. 2021 BMJ, PMID "
            "33781993). The text describes an SR / MA without "
            "acknowledging PRISMA — recommend explicit PRISMA-2020 "
            "compliance and a flow-diagram + checklist."
        ),
    )


def detect_missing_strobe(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    return _detector(
        text,
        _OBSERVATIONAL_TRIGGER,
        _STROBE_ACKNOWLEDGED,
        ReportingGuideline.STROBE,
        why=(
            "Observational-study reporting (cohort, case-control, "
            "cross-sectional) should follow the STROBE statement (von "
            "Elm et al. 2007, PMID 17938396). The text describes an "
            "observational study without acknowledging STROBE — "
            "recommend explicit STROBE compliance."
        ),
    )


def detect_missing_rob2(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    return _detector(
        text,
        _BIAS_APPRAISAL_RCT_TRIGGER,
        _ROB_2_ACKNOWLEDGED,
        ReportingGuideline.ROB_2,
        why=(
            "Risk-of-bias appraisal of RCTs should use the Cochrane "
            "Risk of Bias 2 (RoB 2) tool (Sterne et al. 2019 BMJ, PMID "
            "31462531). The text describes RCT bias appraisal without "
            "naming RoB 2 — recommend explicit RoB 2 use."
        ),
    )


def detect_missing_robins_i(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    return _detector(
        text,
        _BIAS_APPRAISAL_NRSI_TRIGGER,
        _ROBINS_I_ACKNOWLEDGED,
        ReportingGuideline.ROBINS_I,
        why=(
            "Risk-of-bias appraisal of non-randomized intervention "
            "studies should use the ROBINS-I tool (Sterne et al. 2016 "
            "BMJ, PMID 27733354). The text describes NRSI bias "
            "appraisal without naming ROBINS-I — recommend explicit "
            "ROBINS-I use."
        ),
    )


def detect_missing_amstar2(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    return _detector(
        text,
        _SR_QUALITY_TRIGGER,
        _AMSTAR_2_ACKNOWLEDGED,
        ReportingGuideline.AMSTAR_2,
        why=(
            "Methodological-quality appraisal of systematic reviews "
            "should use AMSTAR-2 (Shea et al. 2017 BMJ, PMID 28935701). "
            "The text describes SR quality appraisal without naming "
            "AMSTAR-2 — recommend explicit AMSTAR-2 use."
        ),
    )


def run_reporting_rigor_checks(
    text: str,
) -> tuple[ReportingGuidelineViolation, ...]:
    """Run all reporting-guideline + risk-of-bias detectors."""
    if not text:
        return ()
    out: list[ReportingGuidelineViolation] = []
    out.extend(detect_missing_consort(text))
    out.extend(detect_missing_prisma(text))
    out.extend(detect_missing_strobe(text))
    out.extend(detect_missing_rob2(text))
    out.extend(detect_missing_robins_i(text))
    out.extend(detect_missing_amstar2(text))
    return tuple(out)
