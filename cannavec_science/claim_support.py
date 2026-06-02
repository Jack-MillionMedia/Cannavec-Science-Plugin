"""Claim-support verification — does the cited paper actually support the claim?

The identifier audits (``audit_pmids`` / ``audit_uniprot`` + the offline guards)
answer "is the *right paper* cited?". This module answers the next, harder
question: "does that paper actually *support the magnitude and direction*
claimed?" — the failure mode where a correct, real PMID is attached to a claim
the paper does not make (e.g. citing an *induction* study for an *inhibition*
claim, or a CYP3A4 claim to a paper that only studied CYP2C9).

It does **not** "understand" the paper. Deterministically and offline, it:

1. extracts the *checkable entities* of a claim — cannabinoids, partner drugs,
   CYP/UGT isoforms, and the asserted direction (inhibit / induce / increase /
   decrease / no-effect); and
2. checks each against the cited paper's title + abstract, returning the
   entities that are **absent** and any **direction contradiction**.

This is a high-recall *flagger*, not a grader: it narrows thousands of curated
claims to the few whose support is not evident in the abstract, which a human
curator (or the optional :mod:`claim_support_llm` adjudicator) then reviews. It
never assigns a GRADE and never emits a citation — same discipline as the ranker.

Design mirrors the rest of the backbone: stdlib-only, pure functions, every rule
unit-tested. Network (fetching the abstract) is the caller's job and is injected,
so the offline suite never needs PubMed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence

__all__ = [
    "Verdict",
    "SupportReport",
    "extract_entities",
    "claimed_direction",
    "assess_support",
]


class Verdict(str, Enum):
    SUPPORTED = "supported"        # all core entities present, direction consistent
    WEAK = "weak"                  # entities present but direction not evidenced
    UNVERIFIED = "unverified"      # a core entity is absent from the abstract
    CONTRADICTION = "contradiction"  # abstract asserts the opposite direction
    NO_TEXT = "no_text"            # no abstract supplied — cannot assess


# ── lexicon ────────────────────────────────────────────────────────────────

# Cannabinoid abbreviations -> the words that also count as a match in prose.
_CANNABINOID_SYNONYMS = {
    "cbd": ("cbd", "cannabidiol"),
    "thc": ("thc", "tetrahydrocannabinol", "dronabinol"),
    "thca": ("thca", "tetrahydrocannabinolic"),
    "cbda": ("cbda", "cannabidiolic"),
    "cbg": ("cbg", "cannabigerol"),
    "cbn": ("cbn", "cannabinol"),
    "cbc": ("cbc", "cannabichromene"),
    "thcv": ("thcv", "tetrahydrocannabivarin"),
    "cbdv": ("cbdv", "cannabidivarin"),
}

# Direction families. Order matters only for display; membership is what counts.
# Needles are stems so inflections match (e.g. "increas" covers increase/
# increasing/increased; "induc" covers induce/induced/induction/induces).
_DIRECTIONS = {
    "inhibit": ("inhibit", "suppress", "blockad"),
    "induce": ("induc", "upregulat", "up-regulat"),
    "increase": ("increas", "elevat", "higher", "augment", "rais", "rose", "greater"),
    "decrease": ("decreas", "reduc", "lower", "diminish", "attenuat", "fewer"),
    "no_effect": ("no effect", "no significant", "not affect", "no interaction",
                  "no change", "did not", "no clinically"),
}
# The one opposition the domain cares about most (§ interactions): a mechanism
# claim of inhibition vs. induction is a real contradiction, not a nuance.
_OPPOSED = {"inhibit": "induce", "induce": "inhibit",
            "increase": "decrease", "decrease": "increase"}

_CYP_RE = re.compile(r"\bcyp\s?\d+[a-z]\d*\b")
_UGT_RE = re.compile(r"\bugt\s?\d+[a-z]?\d*\b")
_QUANT_RE = re.compile(r"\b(auc|cmax|ki|ic50|ec50|kd|tmax|half-life|fold|ratio)\b")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())


def _cyp_key(token: str) -> str:
    """Normalise 'CYP 3A4' / 'cyp3a' -> 'cyp3a' family key (drop trailing detail
    so CYP3A4 in a claim matches CYP3A in an abstract and vice versa)."""
    t = token.replace(" ", "")
    m = re.match(r"(cyp\d+[a-z])", t)
    return m.group(1) if m else t


# Map an isomer-prefixed / spelled-out cannabinoid name to its synonym key, so a
# registry field like "Δ⁹-THC" or "Δ8-THC" matches "thc"/"tetrahydrocannabinol".
# Longer keys are tried first (THCA before THC) to avoid mis-collapsing.
_CB_KEYS_BY_LEN = sorted(_CANNABINOID_SYNONYMS, key=len, reverse=True)


def _canonical_cannabinoid(name: str) -> str:
    collapsed = _norm(name).replace(" ", "")  # "Δ⁹-thc" -> "thc"
    for key in _CB_KEYS_BY_LEN:
        if key in collapsed:
            return key
    return collapsed


# Words inside a partner-drug field that name a class, not a specific drug.
_DRUG_STOP = frozenset(
    "substrate substrates inhibitor inhibitors inducer inducers drug drugs agent "
    "agents class some other and via the of with eg".split()
)


def _drug_candidates(partner_drug: str) -> list[str]:
    """Specific drug tokens inside a partner-drug field (drops class words)."""
    return [t for t in _norm(partner_drug).split()
            if len(t) >= 4 and t not in _DRUG_STOP]


def _is_drug_class(partner_drug: str) -> bool:
    """True when the field names a *class* of drugs rather than one drug."""
    pd = partner_drug.lower()
    return (
        "(" in pd or "," in pd or " and " in pd
        or any(w in pd.split() for w in _DRUG_STOP)
    )


# ── extraction ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Entities:
    cannabinoids: tuple[str, ...]
    cyps: tuple[str, ...]
    drugs: tuple[str, ...]
    quantities: tuple[str, ...]


def extract_entities(
    text: str,
    *,
    extra_drugs: Sequence[str] = (),
) -> _Entities:
    """Pull the checkable entities out of a claim (or any text)."""
    norm = _norm(text)
    cbs = tuple(
        abbr for abbr, syns in _CANNABINOID_SYNONYMS.items()
        if any(s in norm for s in syns)
    )
    cyps = tuple(sorted({_cyp_key(m) for m in _CYP_RE.findall(norm)}
                        | {_cyp_key(m) for m in _UGT_RE.findall(norm)}))
    drugs = tuple(d.lower() for d in extra_drugs if d and d.lower() in norm) \
        if extra_drugs else ()
    quants = tuple(sorted(set(_QUANT_RE.findall(norm))))
    return _Entities(cbs, cyps, drugs, quants)


def claimed_direction(text: str, *, direction_hint: Optional[str] = None) -> Optional[str]:
    """Best-guess the claim's asserted direction family (or None)."""
    if direction_hint:
        h = direction_hint.lower()
        for fam in _DIRECTIONS:
            if fam in h or h in fam:
                return fam
        if "inhibit" in h:
            return "inhibit"
        if "induc" in h:
            return "induce"
    norm = _norm(text)
    for fam, needles in _DIRECTIONS.items():
        if any(n in norm for n in needles):
            return fam
    return None


# ── assessment ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SupportReport:
    verdict: Verdict
    matched: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()        # core entities absent from the abstract
    claim_direction: Optional[str] = None
    abstract_directions: tuple[str, ...] = ()
    note: str = ""

    @property
    def needs_review(self) -> bool:
        return self.verdict in (Verdict.UNVERIFIED, Verdict.CONTRADICTION)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "matched": list(self.matched),
            "missing": list(self.missing),
            "claim_direction": self.claim_direction,
            "abstract_directions": list(self.abstract_directions),
            "needs_review": self.needs_review,
            "note": self.note,
        }


def _present(entity_kind: str, token: str, hay: str) -> bool:
    if entity_kind == "cannabinoid":
        return any(s in hay for s in _CANNABINOID_SYNONYMS.get(token, (token,)))
    if entity_kind == "cyp":
        # family match: claim cyp3a (from CYP3A4) matches abstract 'cyp3a' or 'cyp3a4'
        return token in hay.replace(" ", "")
    return token in hay


def assess_support(
    claim_text: str,
    abstract: str,
    *,
    title: str = "",
    cannabinoid: Optional[str] = None,
    partner_drug: Optional[str] = None,
    cyp_isoform: Optional[str] = None,
    direction_hint: Optional[str] = None,
) -> SupportReport:
    """Assess whether ``abstract`` (+ ``title``) supports ``claim_text``.

    Structured fields (``cannabinoid`` / ``partner_drug`` / ``cyp_isoform`` /
    ``direction_hint``) take precedence over what is parsed from the free-text
    claim, so a caller with typed registry rows gets a precise check.
    """
    hay = _norm(f"{title} {abstract}")
    if not hay.strip():
        return SupportReport(Verdict.NO_TEXT, note="no abstract supplied")

    claim_ents = extract_entities(claim_text)

    # Core entities — structured fields override what is parsed from the claim.
    core: list[tuple[str, str]] = []  # (kind, token)
    cbs = [_canonical_cannabinoid(cannabinoid)] if cannabinoid else list(claim_ents.cannabinoids)
    core += [("cannabinoid", cb) for cb in cbs if cb]
    cyps = [_cyp_key(_norm(cyp_isoform))] if cyp_isoform else list(claim_ents.cyps)
    core += [("cyp", c) for c in cyps if c]

    matched: list[str] = []
    missing: list[str] = []
    for kind, token in core:
        if _present(kind, token, hay):
            matched.append(token)
        else:
            missing.append(token)

    # Partner drug. A single named drug is core — its absence from the abstract
    # is a real flag. A drug *class* ("CYP3A4 substrates (statins, ...)") is
    # informational only: a mechanism citation need not name every downstream
    # substrate, so its absence must not flag (that was pure recall noise).
    if partner_drug:
        cands = _drug_candidates(partner_drug)
        if any(c in hay for c in cands):
            matched.append(_norm(partner_drug).strip()[:24])
        elif cands and not _is_drug_class(partner_drug):
            missing.append(_norm(partner_drug).strip()[:30])

    # Direction.
    cdir = claimed_direction(claim_text, direction_hint=direction_hint)
    abs_dirs = tuple(fam for fam, needles in _DIRECTIONS.items()
                     if any(n in hay for n in needles))

    # Verdict.
    if missing:
        return SupportReport(
            Verdict.UNVERIFIED, tuple(matched), tuple(missing), cdir, abs_dirs,
            note=f"{len(missing)} core entity(ies) not found in abstract",
        )
    if cdir and cdir in _OPPOSED:
        opp = _OPPOSED[cdir]
        if opp in abs_dirs and cdir not in abs_dirs:
            return SupportReport(
                Verdict.CONTRADICTION, tuple(matched), (), cdir, abs_dirs,
                note=f"claim asserts '{cdir}' but abstract asserts '{opp}'",
            )
    if cdir and cdir not in abs_dirs:
        return SupportReport(
            Verdict.WEAK, tuple(matched), (), cdir, abs_dirs,
            note=f"entities present but '{cdir}' not evidenced in abstract",
        )
    return SupportReport(
        Verdict.SUPPORTED, tuple(matched), (), cdir, abs_dirs,
        note="core entities and direction present in abstract",
    )
