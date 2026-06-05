"""Claim-pair contradiction detector.

The Contradiction Auditor lives as a prose agent spec. This module is
the deterministic, machine-grade version: given two claim-like strings,
flag direct contradictions on the same topic.

Three kinds of contradictions are detected:

1. **Directional** — both claims share a topic (same compound + same
   outcome) but assert opposite directions ("increases" vs "decreases",
   "effective" vs "ineffective", "legal" vs "illegal").
2. **Numeric** — both claims give a quantity for the same compound +
   metric but the ranges do not overlap (e.g. bioavailability 6-20%
   vs 35-50%).
3. **Yes/no** — one claim affirms, the other denies, the same
   proposition.

The detector is intentionally narrow. False positives are worse than
false negatives — a flagged contradiction surfaces to a human, and
noise makes humans tune out the signal. The detector does not try to
infer topic equality across paraphrase; it requires shared lexical
anchors (compound name, target name, outcome term).

Design rules:

- Deterministic.
- Pure functions.
- Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ContradictionType(str, Enum):
    DIRECTIONAL = "directional"
    NUMERIC = "numeric"
    AFFIRM_DENY = "affirm_deny"


@dataclass(frozen=True)
class Contradiction:
    kind: ContradictionType
    topic: str             # shared anchor (compound / outcome)
    claim_a: str
    claim_b: str
    detail: str


# ── Shared-anchor extraction ──────────────────────────────────────────

# Canonical compound aliases.
_COMPOUND_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:Δ?9?[-\s]?THC|delta[-\s]?9[-\s]?THC|tetrahydrocannabinol)\b",
                re.IGNORECASE), "Δ⁹-THC"),
    (re.compile(r"\b(?:Δ?8?[-\s]?THC|delta[-\s]?8[-\s]?THC)\b",
                re.IGNORECASE), "Δ⁸-THC"),
    (re.compile(r"\b(?:THCA|tetrahydrocannabinolic acid)\b",
                re.IGNORECASE), "THCA"),
    (re.compile(r"\b(?:CBD|cannabidiol)\b", re.IGNORECASE), "CBD"),
    (re.compile(r"\b(?:CBDA|cannabidiolic acid)\b", re.IGNORECASE), "CBDA"),
    (re.compile(r"\b(?:CBG|cannabigerol)\b", re.IGNORECASE), "CBG"),
    (re.compile(r"\b(?:CBN|cannabinol)\b", re.IGNORECASE), "CBN"),
    (re.compile(r"\b(?:CBC|cannabichromene)\b", re.IGNORECASE), "CBC"),
    (re.compile(r"\b(?:THCV|tetrahydrocannabivarin)\b", re.IGNORECASE), "THCV"),
    (re.compile(r"\b(?:CBDV|cannabidivarin)\b", re.IGNORECASE), "CBDV"),
    (re.compile(r"\bnabiximols\b|\bSativex\b", re.IGNORECASE), "nabiximols"),
    (re.compile(r"\bEpidiolex\b|\bcannabidiol\s+oral\s+solution\b", re.IGNORECASE),
     "Epidiolex"),
    (re.compile(r"\bnabilone\b|\bCesamet\b", re.IGNORECASE), "nabilone"),
    (re.compile(r"\bdronabinol\b|\bMarinol\b", re.IGNORECASE), "dronabinol"),
)


# Anchor terms that identify the *outcome* being claimed.
_OUTCOME_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:seizures?|convuls\w*)\b", re.IGNORECASE), "seizures"),
    (re.compile(r"\b(?:anxiety|anxious|anxiogen|anxiolytic)\b", re.IGNORECASE), "anxiety"),
    (re.compile(r"\b(?:pain|analges\w*|nociception)\b", re.IGNORECASE), "pain"),
    (re.compile(r"\b(?:nausea|emesis|vomit\w*|CINV)\b", re.IGNORECASE), "nausea"),
    (re.compile(r"\b(?:appetite|food intake|hunger|orexigenic)\b", re.IGNORECASE), "appetite"),
    (re.compile(r"\b(?:spasticity|spasms?)\b", re.IGNORECASE), "spasticity"),
    (re.compile(r"\b(?:sleep|insomnia|sleep onset|sleep latency)\b", re.IGNORECASE), "sleep"),
    (re.compile(r"\b(?:psychosis|psychotic|schizophreni\w*)\b", re.IGNORECASE), "psychosis"),
    (re.compile(r"\b(?:depression|depressed mood|mdd)\b", re.IGNORECASE), "depression"),
    (re.compile(r"\b(?:bioavailability|absorption)\b", re.IGNORECASE), "bioavailability"),
    (re.compile(r"\b(?:half[-\s]?life|t.{0,2}½|t1/2)\b", re.IGNORECASE), "half-life"),
    (re.compile(r"\b(?:CYP\d[A-Z]?\d*)\b"), "cyp_isoform"),
    (re.compile(r"\b(?:legal|illegal|legali[sz]ed?|scheduled?|schedule [iI]+)\b",
                re.IGNORECASE), "legal_status"),
    # Liver / hepatic safety outcomes: catches CBD-valproate hepatic
    # signal and ensures hepatic adverse-event claims pair correctly.
    (re.compile(r"\b(?:alt|ast|transaminas\w*|hepatotox\w*|liver enzymes?|"
                r"hepatic (?:enzymes?|safety|injury))\b", re.IGNORECASE),
     "hepatic"),
)


def _detect_anchors(
    aliases: tuple[tuple[re.Pattern[str], str], ...],
    text: str,
) -> set[str]:
    return {label for regex, label in aliases if regex.search(text)}


@dataclass(frozen=True)
class _Anchor:
    """The shared lexical anchor between two claims.

    ``label`` is for display. ``has_compound`` / ``has_outcome`` tell
    the caller which contradiction kinds are admissible: directional
    and numeric require BOTH compound and outcome to share, while
    affirm/deny is admissible on either.
    """

    label: str
    has_compound: bool
    has_outcome: bool


def _shared_anchor(a: str, b: str) -> _Anchor | None:
    compounds_a = _detect_anchors(_COMPOUND_ALIASES, a)
    compounds_b = _detect_anchors(_COMPOUND_ALIASES, b)
    shared_compounds = compounds_a & compounds_b
    outcomes_a = _detect_anchors(_OUTCOME_ALIASES, a)
    outcomes_b = _detect_anchors(_OUTCOME_ALIASES, b)
    shared_outcomes = outcomes_a & outcomes_b

    if shared_compounds and shared_outcomes:
        compound = sorted(shared_compounds)[0]
        outcome = sorted(shared_outcomes)[0]
        return _Anchor(
            label=f"{compound} / {outcome}",
            has_compound=True,
            has_outcome=True,
        )
    if shared_compounds:
        return _Anchor(
            label=sorted(shared_compounds)[0],
            has_compound=True,
            has_outcome=False,
        )
    if shared_outcomes:
        return _Anchor(
            label=sorted(shared_outcomes)[0],
            has_compound=False,
            has_outcome=True,
        )
    return None


# ── Directional contradiction ────────────────────────────────────────

_INCREASE_VERBS = re.compile(
    r"\b(?:increase\w*|raise\w*|elevate\w*|worsen\w*|"
    r"exacerbate\w*|induce\w*|trigger\w*|"
    r"is associated with (?:greater|higher|more) |"
    r"is effective for|reduces?|reduced|decreases?|decreased|"
    r"lowers?|lowered|alleviat\w*|relieves?|relieved|"
    r"mitigat\w*|attenuat\w*|improves?|improved)\b",
    re.IGNORECASE,
)

_INCREASE_TOKENS = {
    "increase", "increases", "increased", "increasing", "raise", "raises",
    "raised", "raising", "elevate", "elevates", "elevated", "elevating",
    "worsen", "worsens", "worsened", "worsening", "exacerbate", "exacerbates",
    "exacerbated", "exacerbating", "induce", "induces", "induced", "inducing",
    "trigger", "triggers", "triggered", "triggering", "greater", "higher",
    "more",
}

_DECREASE_TOKENS = {
    "reduce", "reduces", "reduced", "reducing", "decrease", "decreases",
    "decreased", "decreasing", "lower", "lowers", "lowered", "lowering",
    "alleviate", "alleviates", "alleviated", "alleviating",
    "relieve", "relieves", "relieved", "relieving",
    "mitigate", "mitigates", "mitigated", "mitigating",
    "attenuate", "attenuates", "attenuated", "attenuating",
    "improve", "improves", "improved", "improving",
    "effective",  # "is effective for"
}


def _direction_of(text: str) -> str | None:
    """Return ``"increase"``, ``"decrease"`` or ``None``."""
    lower = text.lower()
    tokens = set(re.findall(r"[a-z]+", lower))
    has_inc = bool(tokens & _INCREASE_TOKENS)
    has_dec = bool(tokens & _DECREASE_TOKENS)
    if has_inc and not has_dec:
        return "increase"
    if has_dec and not has_inc:
        return "decrease"
    return None


# ── Numeric contradiction ────────────────────────────────────────────

_RANGE_RE = re.compile(
    r"(?P<lo>\d+(?:\.\d+)?)\s*"
    r"(?:[-–]|to)\s*(?P<hi>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|mg/kg|mg|µg/g|ug/g|ng/ml|nM|μM|uM|kPa|mPa|GPa|MPa|"
    r"hours?|h|min|months?|days?|years?)?",
    re.IGNORECASE,
)


def _extract_ranges(text: str) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for m in _RANGE_RE.finditer(text):
        lo = float(m.group("lo"))
        hi = float(m.group("hi"))
        unit = (m.group("unit") or "").lower()
        if lo > hi:
            lo, hi = hi, lo
        out.append((lo, hi, unit))
    return out


def _ranges_disjoint(
    a: tuple[float, float, str],
    b: tuple[float, float, str],
) -> bool:
    lo_a, hi_a, unit_a = a
    lo_b, hi_b, unit_b = b
    if unit_a != unit_b:
        return False    # Can't compare apples to oranges.
    if hi_a < lo_b or hi_b < lo_a:
        return True
    return False


# ── Affirm / deny contradiction ──────────────────────────────────────

_NEGATION_RE = re.compile(
    r"\b(?:no|not|none|never|cannot|can(?:not| not| ?'?t)|"
    r"does not|do not|did not|isn't|is not|are not|aren't|"
    r"won't|will not)\b",
    re.IGNORECASE,
)


def _affirms(text: str) -> bool:
    return not bool(_NEGATION_RE.search(text))


# ── Public API ───────────────────────────────────────────────────────


def compare_claims(claim_a: str, claim_b: str) -> tuple[Contradiction, ...]:
    """Return any contradictions detected between two claim strings.

    Empty tuple means the detector found no contradiction *under its
    narrow definition*. Absence of detection is NOT the same as
    "the claims agree" — pairs without shared lexical anchors are
    simply not comparable here.
    """
    anchor = _shared_anchor(claim_a, claim_b)
    if anchor is None:
        return ()

    found: list[Contradiction] = []

    # Directional and numeric contradictions only fire when BOTH the
    # compound and the outcome anchor are shared. Without the outcome
    # anchor, "CBD reduces seizures" and "CBD elevates ALT" look like
    # a directional contradiction (decrease vs increase on shared
    # compound CBD) — but they are about different outcomes, so they
    # are not contradictory at all.
    strict_anchor = anchor.has_compound and anchor.has_outcome

    # Directional contradiction.
    if strict_anchor:
        dir_a = _direction_of(claim_a)
        dir_b = _direction_of(claim_b)
        if dir_a and dir_b and dir_a != dir_b:
            found.append(Contradiction(
                kind=ContradictionType.DIRECTIONAL,
                topic=anchor.label,
                claim_a=claim_a,
                claim_b=claim_b,
                detail=(
                    f"Claim A asserts '{dir_a}'; claim B asserts '{dir_b}' "
                    f"on the same topic: {anchor.label}."
                ),
            ))

    # Numeric contradiction.
    if strict_anchor:
        ranges_a = _extract_ranges(claim_a)
        ranges_b = _extract_ranges(claim_b)
        for ra in ranges_a:
            for rb in ranges_b:
                if _ranges_disjoint(ra, rb):
                    found.append(Contradiction(
                        kind=ContradictionType.NUMERIC,
                        topic=anchor.label,
                        claim_a=claim_a,
                        claim_b=claim_b,
                        detail=(
                            f"Numeric ranges {ra[0]}-{ra[1]}{ra[2]} and "
                            f"{rb[0]}-{rb[1]}{rb[2]} are disjoint on topic "
                            f"{anchor.label}."
                        ),
                    ))

    # Affirm / deny contradiction (only when no directional was found,
    # to avoid double-counting). Admissible on either compound-only or
    # outcome-only shared anchors — the question is "do the claims
    # agree about this thing?", not "do they share both axes?".
    if not any(c.kind == ContradictionType.DIRECTIONAL for c in found):
        a_aff = _affirms(claim_a)
        b_aff = _affirms(claim_b)
        if a_aff != b_aff:
            found.append(Contradiction(
                kind=ContradictionType.AFFIRM_DENY,
                topic=anchor.label,
                claim_a=claim_a,
                claim_b=claim_b,
                detail=(
                    f"Claim A {'affirms' if a_aff else 'denies'}; "
                    f"claim B {'affirms' if b_aff else 'denies'} the same "
                    f"topic: {anchor.label}."
                ),
            ))

    return tuple(found)


def scan_claims(
    claims: list[str],
) -> tuple[Contradiction, ...]:
    """Pairwise scan a list of claim strings, returning every contradiction.

    O(n²) pairwise — fine for the typical Cannavec answer (≤ 20 claims).
    The same contradiction will only be reported once (claim_a is the
    earlier one in the list).
    """
    out: list[Contradiction] = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            out.extend(compare_claims(claims[i], claims[j]))
    return tuple(out)
