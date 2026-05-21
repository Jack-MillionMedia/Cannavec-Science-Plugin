"""Wording-vs-grade vocabulary and confidence-band utilities.

The :class:`cannavec.evidence.EvidenceLevel` enum declares which verbs
are acceptable per grade. This module turns that declaration into:

- :func:`acceptable_verbs` — the verb list for a grade.
- :func:`pick_wording` — the strongest acceptable verb for a (grade,
  claim_type) pair, with hedging built in for lower grades.
- :func:`grade_wording_consistency` — detect whether the actual wording
  in a text exceeds what the declared grade supports. The single most
  common cannabis-content failure is "Level C" claims phrased as
  "established for" — this module catches that mechanically.
- :func:`confidence_band_for` — a (0.0-1.0) calibration band an answer
  should land in given its highest-supported grade.

Design rules:

- Deterministic. Same input → same output.
- Pure (no I/O, no compiled regex state).
- Forbidden-verb lists are *additive* (more general → more specific).
  A Level-C claim cannot use Level-A verbs; a Level-A claim may use
  Level-C verbs (hedging is always allowed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern

from cannavec_science._markdown_skip import code_spans, is_in_code
from cannavec_science.evidence import ClaimType, EvidenceLevel


# Verbs always forbidden, regardless of declared grade. Cures / miracle
# / 100%-safe wording is never acceptable in Cannavec output, even at
# Level A — strong evidence supports "is effective for", not "cures".
_ALWAYS_FORBIDDEN_VERBS: tuple[str, ...] = (
    r"\bcures?\b",
    r"\bcured\b",
    # "curing" is banned only when used as a medical-claim verb
    # ("cannabis is curing disease X", "curing patients with anxiety").
    # Cannabis cultivation 'curing' (post-harvest drying/conditioning)
    # is a legitimate agronomic term that must not be flagged.
    # The positive lookahead requires a medical-context noun to follow,
    # so "after curing," and "the curing process" are not violations.
    r"\bcuring\b(?=\s+(?:the\s+)?(?:disease|cancer|tumor|tumour|"
    r"illness|condition|pain|anxiety|depression|ptsd|seizure|"
    r"diabetes|arthritis|parkinson|alzheimer|patients?|people|users?|"
    r"symptoms?|disorders?|syndrome|carcinoma|glioma|leukemia|leukaemia))",
    r"\beradicates?\b",
    r"\beliminates?\b",
    r"\bheals?\b",
    r"\bmiracle\w*\b",
    r"\b100\s?%\s+effective\b",
    r"\b100\s?%\s+safe\b",
)


# Verbs that are stronger than the level can support — using any of
# these at the given level (or below) is a wording-vs-grade violation.
_FORBIDDEN_VERBS_AT_OR_BELOW: dict[EvidenceLevel, tuple[str, ...]] = {
    EvidenceLevel.A: (),   # see _ALWAYS_FORBIDDEN_VERBS instead
    EvidenceLevel.B: (
        r"\bestablished\b",
        r"\bdemonstrates?\b",
        r"\bproven\b",
        r"\bproves?\b",
        r"\bdefinitively\b",
        r"\bconclusively\b",
        r"\bis effective for\b",
        r"\bare effective for\b",
    ),
    EvidenceLevel.C: (
        r"\blikely effective\b",
        r"\bappears? to (?:reduce|increase|improve|decrease)\b",
        r"\bis associated with\b",
        r"\bare associated with\b",
    ),
    EvidenceLevel.D: (
        r"\bmay (?:reduce|increase|improve|decrease|help)\b",
        r"\bsuggests? potential benefit\b",
        r"\bpreliminary evidence\b",
    ),
    EvidenceLevel.E: (
        r"\banecdotal reports?\b",
        r"\bopen-label observations?\b",
    ),
    EvidenceLevel.UNSUPPORTED: (
        r"\bunverified report\b",
        r"\bcase report only\b",
    ),
}


def _verbs_forbidden_at(level: EvidenceLevel) -> tuple[Pattern[str], ...]:
    """Compiled verbs that would over-claim at this evidence level.

    Returns the union of (a) verbs that always exceed evidence
    (:data:`_ALWAYS_FORBIDDEN_VERBS`) and (b) verbs reserved for grades
    *at or above* ``level`` — meaning they imply stronger evidence than
    the declared level supports.

    For example, "established" is in Level B's forbidden list; a Level B
    claim that says "established" is over-claiming (that verb requires
    Level A). The check must therefore fire at Level B itself (``>=``),
    not only at levels below B (``>``).
    """
    forbidden: list[str] = list(_ALWAYS_FORBIDDEN_VERBS)
    for candidate_level, patterns in _FORBIDDEN_VERBS_AT_OR_BELOW.items():
        if candidate_level.rank >= level.rank:
            forbidden.extend(patterns)
    return tuple(re.compile(p, flags=re.IGNORECASE) for p in forbidden)


_VERB_REGEX_CACHE: dict[EvidenceLevel, tuple[Pattern[str], ...]] = {}


def _cached(level: EvidenceLevel) -> tuple[Pattern[str], ...]:
    if level not in _VERB_REGEX_CACHE:
        _VERB_REGEX_CACHE[level] = _verbs_forbidden_at(level)
    return _VERB_REGEX_CACHE[level]


def acceptable_verbs(level: EvidenceLevel) -> tuple[str, ...]:
    """Verbs that an answer at this grade may use (per the skill spec)."""
    # Pull directly from EvidenceLevel.acceptable_wording — single source
    # of truth.
    return tuple(level.acceptable_wording)


_DEFAULT_VERB_BY_LEVEL_AND_TYPE: dict[
    tuple[EvidenceLevel, ClaimType], str
] = {
    # The DEFAULTS aim for honest calibration. Picks are conservative.
    (EvidenceLevel.A, ClaimType.CLINICAL_EFFICACY): "is effective for",
    (EvidenceLevel.B, ClaimType.CLINICAL_EFFICACY): "likely effective for",
    (EvidenceLevel.C, ClaimType.CLINICAL_EFFICACY): "may reduce",
    (EvidenceLevel.D, ClaimType.CLINICAL_EFFICACY): "anecdotal reports describe",
    (EvidenceLevel.E, ClaimType.CLINICAL_EFFICACY): "case-report-only evidence describes",
    (EvidenceLevel.UNSUPPORTED, ClaimType.CLINICAL_EFFICACY): (
        "no admissible primary evidence supports a clinical-efficacy claim for"
    ),

    (EvidenceLevel.A, ClaimType.MECHANISM): "is established to act at",
    (EvidenceLevel.B, ClaimType.MECHANISM): "appears to act at",
    (EvidenceLevel.C, ClaimType.MECHANISM): "preliminary evidence suggests action at",
    (EvidenceLevel.D, ClaimType.MECHANISM): "open-label / in-vitro observations describe action at",
    (EvidenceLevel.E, ClaimType.MECHANISM): "case-report-only evidence describes action at",
    (EvidenceLevel.UNSUPPORTED, ClaimType.MECHANISM): (
        "no admissible primary mechanism evidence for"
    ),

    (EvidenceLevel.A, ClaimType.SAFETY): "is established to cause",
    (EvidenceLevel.B, ClaimType.SAFETY): "is associated with",
    (EvidenceLevel.C, ClaimType.SAFETY): "may be associated with",
    (EvidenceLevel.D, ClaimType.SAFETY): "anecdotal reports describe",
    (EvidenceLevel.E, ClaimType.SAFETY): "case-report-only evidence describes",
    (EvidenceLevel.UNSUPPORTED, ClaimType.SAFETY): (
        "no admissible primary safety evidence for"
    ),

    (EvidenceLevel.A, ClaimType.DOSING): "is the established trial-supported dose range",
    (EvidenceLevel.B, ClaimType.DOSING): "is the likely trial-supported dose range",
    (EvidenceLevel.C, ClaimType.DOSING): "is a single-trial-supported dose range",
    (EvidenceLevel.D, ClaimType.DOSING): "is an open-label dose range",
    (EvidenceLevel.E, ClaimType.DOSING): "is a case-report dose range",
    (EvidenceLevel.UNSUPPORTED, ClaimType.DOSING): (
        "no admissible primary dosing evidence for"
    ),

    (EvidenceLevel.A, ClaimType.PHARMACOKINETIC): "is the established PK profile",
    (EvidenceLevel.B, ClaimType.PHARMACOKINETIC): "is the reported PK profile",
    (EvidenceLevel.C, ClaimType.PHARMACOKINETIC): "is a preliminary PK profile",
    (EvidenceLevel.D, ClaimType.PHARMACOKINETIC): "is an open-label PK observation",
    (EvidenceLevel.E, ClaimType.PHARMACOKINETIC): "is a single-case PK observation",
    (EvidenceLevel.UNSUPPORTED, ClaimType.PHARMACOKINETIC): (
        "no admissible primary PK evidence for"
    ),

    (EvidenceLevel.A, ClaimType.DRUG_INTERACTION): "is an established drug interaction",
    (EvidenceLevel.B, ClaimType.DRUG_INTERACTION): "is a likely drug interaction",
    (EvidenceLevel.C, ClaimType.DRUG_INTERACTION): "may be a drug interaction",
    (EvidenceLevel.D, ClaimType.DRUG_INTERACTION): "an open-label drug-interaction signal",
    (EvidenceLevel.E, ClaimType.DRUG_INTERACTION): "a case-report drug-interaction signal",
    (EvidenceLevel.UNSUPPORTED, ClaimType.DRUG_INTERACTION): (
        "no admissible primary drug-interaction evidence for"
    ),

    (EvidenceLevel.A, ClaimType.LEGAL_REGULATORY): "the regulator has established",
    (EvidenceLevel.B, ClaimType.LEGAL_REGULATORY): "the regulator's published position is",
    (EvidenceLevel.C, ClaimType.LEGAL_REGULATORY): "the regulator's preliminary guidance is",
    (EvidenceLevel.D, ClaimType.LEGAL_REGULATORY): "informal regulator commentary suggests",
    (EvidenceLevel.E, ClaimType.LEGAL_REGULATORY): "anecdotal regulator commentary suggests",
    (EvidenceLevel.UNSUPPORTED, ClaimType.LEGAL_REGULATORY): (
        "no admissible primary regulator source for"
    ),

    (EvidenceLevel.A, ClaimType.PHYTOCHEMISTRY_QUANTITY): "is the established quantity",
    (EvidenceLevel.B, ClaimType.PHYTOCHEMISTRY_QUANTITY): "is the reported quantity",
    (EvidenceLevel.C, ClaimType.PHYTOCHEMISTRY_QUANTITY): "is a single-method quantity",
    (EvidenceLevel.D, ClaimType.PHYTOCHEMISTRY_QUANTITY): "is an open-label quantity",
    (EvidenceLevel.E, ClaimType.PHYTOCHEMISTRY_QUANTITY): "is a single-sample quantity",
    (EvidenceLevel.UNSUPPORTED, ClaimType.PHYTOCHEMISTRY_QUANTITY): (
        "no admissible primary quantity evidence for"
    ),

    (EvidenceLevel.A, ClaimType.CULTIVATION_PARAMETER): "is the established parameter range",
    (EvidenceLevel.B, ClaimType.CULTIVATION_PARAMETER): "is the reported parameter range",
    (EvidenceLevel.C, ClaimType.CULTIVATION_PARAMETER): "may be the parameter range",
    (EvidenceLevel.D, ClaimType.CULTIVATION_PARAMETER): "anecdotal cultivation reports describe",
    (EvidenceLevel.E, ClaimType.CULTIVATION_PARAMETER): "single-grower reports describe",
    (EvidenceLevel.UNSUPPORTED, ClaimType.CULTIVATION_PARAMETER): (
        "no admissible primary cultivation evidence for"
    ),

    (EvidenceLevel.A, ClaimType.MARKET_DATA): "is the established market figure",
    (EvidenceLevel.B, ClaimType.MARKET_DATA): "is the reported market figure",
    (EvidenceLevel.C, ClaimType.MARKET_DATA): "is a preliminary market figure",
    (EvidenceLevel.D, ClaimType.MARKET_DATA): "is an industry-source market figure",
    (EvidenceLevel.E, ClaimType.MARKET_DATA): "is a single-source market figure",
    (EvidenceLevel.UNSUPPORTED, ClaimType.MARKET_DATA): (
        "no admissible primary market source for"
    ),

    (EvidenceLevel.A, ClaimType.EDUCATIONAL): "is well-established",
    (EvidenceLevel.B, ClaimType.EDUCATIONAL): "is generally accepted",
    (EvidenceLevel.C, ClaimType.EDUCATIONAL): "is partially understood",
    (EvidenceLevel.D, ClaimType.EDUCATIONAL): "is informally understood",
    (EvidenceLevel.E, ClaimType.EDUCATIONAL): "is anecdotally described",
    (EvidenceLevel.UNSUPPORTED, ClaimType.EDUCATIONAL): "is unsupported",

    (EvidenceLevel.A, ClaimType.OPINION): "the consensus view is",
    (EvidenceLevel.B, ClaimType.OPINION): "the prevailing view is",
    (EvidenceLevel.C, ClaimType.OPINION): "a common view is",
    (EvidenceLevel.D, ClaimType.OPINION): "one view is",
    (EvidenceLevel.E, ClaimType.OPINION): "one analyst suggests",
    (EvidenceLevel.UNSUPPORTED, ClaimType.OPINION): "the question is unresolved",
}


def pick_wording(level: EvidenceLevel, claim_type: ClaimType) -> str:
    """Return the canonical wording for a (grade, claim_type) pair.

    Surfaces use this to phrase a single claim consistently. The
    output is the *starting point* — the surface may add scope, route,
    population. The verb strength matches the grade.
    """
    return _DEFAULT_VERB_BY_LEVEL_AND_TYPE.get(
        (level, claim_type),
        # Fallback: use the level's first acceptable verb.
        level.acceptable_wording[0],
    )


@dataclass(frozen=True)
class WordingViolation:
    declared_level: EvidenceLevel
    matched_phrase: str
    span: tuple[int, int]
    why: str


def grade_wording_consistency(
    text: str,
    declared_level: EvidenceLevel,
) -> tuple[WordingViolation, ...]:
    """Detect verbs that exceed the wording strength the declared grade supports.

    Returns a tuple of :class:`WordingViolation`. Empty tuple means the
    text's claim-strength wording is calibrated to or weaker than the
    declared grade.

    Example:
      - Declared Level C, text contains "is established to reduce" →
        violation (Level A verb at Level C).
      - Declared Level A, text contains "may reduce" → no violation
        (hedging is always allowed).

    Matches inside markdown inline-code (`` `cures` ``) or fenced code
    blocks are filtered out: an audit/discussion section that names a
    forbidden verb in code formatting is not asserting the claim.
    """
    spans = code_spans(text)
    out: list[WordingViolation] = []
    for regex in _cached(declared_level):
        for m in regex.finditer(text):
            if is_in_code(spans, m.start()):
                continue
            out.append(WordingViolation(
                declared_level=declared_level,
                matched_phrase=m.group(0),
                span=m.span(),
                why=(
                    f"phrase '{m.group(0)}' implies a grade higher than "
                    f"{declared_level.value}"
                ),
            ))
    out.sort(key=lambda v: v.span[0])
    return tuple(out)


_DECLARED_LEVEL_RE = re.compile(
    r"\b(?:Level\s+([A-E])|"
    r"GRADE\s+(high|moderate|low|very\s+low))",
    flags=re.IGNORECASE,
)


_GRADE_FROM_STR: dict[str, EvidenceLevel] = {
    "a": EvidenceLevel.A,
    "b": EvidenceLevel.B,
    "c": EvidenceLevel.C,
    "d": EvidenceLevel.D,
    "e": EvidenceLevel.E,
    "high": EvidenceLevel.A,
    "moderate": EvidenceLevel.B,
    "low": EvidenceLevel.C,
    "very low": EvidenceLevel.D,
}


def detect_declared_level(text: str) -> EvidenceLevel | None:
    """Return the strongest declared evidence level mentioned in ``text``."""
    found: list[EvidenceLevel] = []
    for m in _DECLARED_LEVEL_RE.finditer(text):
        token = (m.group(1) or m.group(2) or "").strip().lower()
        token = re.sub(r"\s+", " ", token)
        if token in _GRADE_FROM_STR:
            found.append(_GRADE_FROM_STR[token])
    if not found:
        return None
    return max(found, key=lambda lvl: lvl.rank)


# Confidence bands — anchor an answer's self-reported confidence to the
# strongest evidence grade it actually has.
_CONFIDENCE_BAND: dict[EvidenceLevel, tuple[float, float]] = {
    EvidenceLevel.A: (0.80, 0.95),
    EvidenceLevel.B: (0.60, 0.80),
    EvidenceLevel.C: (0.40, 0.60),
    EvidenceLevel.D: (0.20, 0.40),
    EvidenceLevel.E: (0.05, 0.20),
    EvidenceLevel.UNSUPPORTED: (0.00, 0.10),
}


def confidence_band_for(level: EvidenceLevel) -> tuple[float, float]:
    """Acceptable confidence band for an answer whose top grade is ``level``."""
    return _CONFIDENCE_BAND[level]


def confidence_consistent(confidence: float, level: EvidenceLevel) -> bool:
    """True if ``confidence`` is inside the band for the given grade."""
    lo, hi = _CONFIDENCE_BAND[level]
    # Allow a small tolerance so 0.6 sits in both B and C bands at the seam.
    return lo - 1e-9 <= confidence <= hi + 1e-9
