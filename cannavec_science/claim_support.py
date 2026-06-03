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
from typing import Mapping, Optional, Protocol, Sequence

__all__ = [
    "Verdict",
    "SupportReport",
    "extract_entities",
    "claimed_direction",
    "assess_support",
    # ── optional LLM-adjudication layer (see claim_support_llm) ──
    "Support",
    "Adjudication",
    "AdjudicatorBackend",
    "ClaimReview",
    "gates_to_llm",
    "asserts_magnitude",
    "verify_quote",
    "review_claim",
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


# ── LLM-adjudication layer ───────────────────────────────────────────────────
#
# The deterministic flagger above answers, at high recall, "is the magnitude/
# direction *evident in the abstract*?". The optional adjudicator closes the
# loop on the flagged minority: an LLM (:mod:`cannavec_science.claim_support_llm`)
# reads the cited text and returns an identifier-free verdict —
# ``supported`` / ``partial`` / ``unverified`` — with the supporting sentence
# quoted verbatim, and a human confirms the contested ones. This split mirrors
# ``ranker`` / ``ranker_llm`` exactly: the types and the gating pipeline live
# here (stdlib-only, import-safe, the always-present floor); the model adapter
# lives in the optional module and is injected, duck-typed, never imported by
# the core. The model can neither invent a citation (the payload is identifier-
# free and the schema has no identifier field) nor assign a GRADE (no grade
# field); and its quote is provenance-gated — :func:`verify_quote` drops any
# sentence that is not a real span of the source text, so a fabricated quote
# can never be surfaced as evidence. That gate is this layer's analog of the
# ranker's provenance gate, and it is what makes the verdict trustworthy.


class Support(str, Enum):
    """The adjudicator's identifier-free, GRADE-free verdict surface."""

    SUPPORTED = "supported"     # the source text states the claim's effect
    PARTIAL = "partial"         # direction/entities present, not the full claim
    UNVERIFIED = "unverified"   # effect absent, entity missing, or contradicted


@dataclass(frozen=True)
class Adjudication:
    """One LLM adjudicator's reading of a single flagged claim.

    ``verdict`` is one of :class:`Support`. ``quote`` is the supporting sentence
    the model copied from the source text; ``quote_verified`` is set by the
    pipeline (not the model) — a quote that is not a real span of the source is
    dropped and this flag is ``False``. ``reason`` is a terse, identifier-free
    rationale. There is deliberately no identifier field (§I) and no grade field
    (§VII): the model cannot emit either.
    """

    verdict: Support
    quote: str = ""
    reason: str = ""
    quote_verified: bool = False
    model: str = ""

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "quote": self.quote,
            "reason": self.reason,
            "quote_verified": self.quote_verified,
            "model": self.model,
        }


# Deterministic verdict → surfaced Support when no LLM is consulted. WEAK maps to
# PARTIAL (entities present, direction not yet evidenced); a missing entity, a
# contradiction, and a missing abstract are all "not verified" until a closer
# read says otherwise.
_DET_TO_SUPPORT: dict[Verdict, Support] = {
    Verdict.SUPPORTED: Support.SUPPORTED,
    Verdict.WEAK: Support.PARTIAL,
    Verdict.UNVERIFIED: Support.UNVERIFIED,
    Verdict.CONTRADICTION: Support.UNVERIFIED,
    Verdict.NO_TEXT: Support.UNVERIFIED,
}


class AdjudicatorBackend(Protocol):
    """Duck-typed adjudication backend. ``name`` distinguishes the deterministic
    floor from an LLM-backed reader so callers can tell whether a model ran."""

    name: str

    def adjudicate(
        self,
        claim_text: str,
        source_text: str,
        *,
        cannabinoid: Optional[str] = None,
        partner_drug: Optional[str] = None,
        cyp_isoform: Optional[str] = None,
        direction_hint: Optional[str] = None,
    ) -> "Adjudication":
        ...


# A number bound to a magnitude unit ("14.8-fold", "30%", "2x", "150 ng/mL").
# A trailing negative lookahead (not a word boundary) is used so symbol units
# like "%" — which have no \b after them — still anchor the match.
_MAGNITUDE_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:%|percent|-?fold|x|times|ng/ml|mg/ml|mg|µg|mcg|ng|µm|um|nm)(?![a-z])"
)


def asserts_magnitude(text: str) -> bool:
    """True when a claim states a checkable quantitative magnitude.

    A specific number — "AUC ×14.8", "30% reduction", "2-fold" — is exactly
    where a *right paper, wrong claim* defect hides: the cannabinoid, the
    enzyme, and the direction can all match while the cited paper never reports
    *that number*. The deterministic check above does not read magnitudes, so a
    magnitude-bearing claim is worth a closer LLM read even when the cheap check
    is otherwise satisfied — which is precisely the magnitude judgement the
    adjudicator exists to make.
    """
    if not text:
        return False
    low = text.lower()
    if _MAGNITUDE_UNIT_RE.search(low):
        return True
    # A bare number co-occurring with a PK magnitude keyword ("AUC 14.8").
    return bool(re.search(r"\d", low)) and bool(_QUANT_RE.search(_norm(low)))


def gates_to_llm(report: SupportReport, *, claim_text: str = "") -> bool:
    """The deterministic flagger decides which claims need a closer LLM read.

    Two kinds of claim are escalated. First, the **flagged minority** — ``WEAK``
    / ``UNVERIFIED`` / ``CONTRADICTION`` — where the cheap check already found
    the entities or direction not evident. Second, an otherwise-confident
    ``SUPPORTED`` claim that **asserts a quantitative magnitude**
    (:func:`asserts_magnitude`): the deterministic layer never reads numbers, so
    "CBD raises clobazam AUC 5-fold" passes the entity/direction check while the
    *5-fold* itself is unconfirmed — exactly the magnitude the LLM must judge.

    A confident ``SUPPORTED`` claim with no magnitude needs no model, and
    ``NO_TEXT`` has nothing to read; both gate out. This is the cost lever (the
    analog of the ranker's ``should_escalate`` short-circuit) and it never costs
    accuracy — it only skips the model where the deterministic floor was already
    confident and there was no number left to check.
    """
    if report.verdict in (Verdict.WEAK, Verdict.UNVERIFIED, Verdict.CONTRADICTION):
        return True
    if report.verdict is Verdict.SUPPORTED and asserts_magnitude(claim_text):
        return True
    return False


# Characters a model commonly wraps a quote in, or appends to signal truncation;
# stripped before the substring check so a verbatim quote survives reflow.
_QUOTE_WRAP = "\"'“”‘’"   # straight + smart quotes
_QUOTE_TRIM = "…. \t\n"                  # ellipsis, period, whitespace


def _collapse_ws(s: str) -> str:
    """Lowercase and collapse runs of whitespace — applied to both sides of the
    quote check so verbatim text survives reflow without loosening the match."""
    return " ".join((s or "").lower().split())


def verify_quote(quote: str, source_text: str, *, min_words: int = 3) -> bool:
    """True when ``quote`` is a real, non-trivial span of ``source_text``.

    Case and whitespace are normalised on both sides (a model may reflow a
    verbatim sentence), and wrapping quote-marks / ellipses are stripped. A
    span shorter than ``min_words`` tokens is rejected as non-evidence even if
    it technically matches. Punctuation is *not* stripped from the interior, so
    the match stays strict in the safe direction: a paraphrased or fabricated
    sentence fails. This is the structural guarantee that the adjudicator cannot
    invent its supporting evidence — :func:`review_claim` drops any quote that
    fails it (Constitution §I, the provenance-gate analog).
    """
    if not quote or not source_text:
        return False
    q = quote.strip().strip(_QUOTE_WRAP).strip(_QUOTE_TRIM)
    qn = _collapse_ws(q)
    if len(qn.split()) < min_words:
        return False
    return qn in _collapse_ws(source_text)


@dataclass(frozen=True)
class ClaimReview:
    """Deterministic flag + optional LLM adjudication for one claim.

    ``report`` is always present (the floor). ``adjudication`` is present only
    when a backend was consulted and returned a reading. The surfaced
    :attr:`verdict` prefers the adjudicator when it ran and otherwise maps the
    deterministic verdict; :attr:`quote` is the *verified* supporting sentence
    (empty if none survived the gate); :attr:`needs_human` is the human-review
    flag — a clean, quote-anchored ``supported`` is the trust-without-re-reading
    case and needs no human, everything else is contested.
    """

    report: SupportReport
    adjudication: Optional[Adjudication] = None
    escalated: bool = False
    note: str = ""

    @property
    def verdict(self) -> Support:
        if self.adjudication is not None:
            return self.adjudication.verdict
        return _DET_TO_SUPPORT.get(self.report.verdict, Support.UNVERIFIED)

    @property
    def quote(self) -> str:
        a = self.adjudication
        return a.quote if (a is not None and a.quote_verified) else ""

    @property
    def needs_human(self) -> bool:
        a = self.adjudication
        if a is None:
            # Not adjudicated: trust a deterministic SUPPORTED, flag the rest.
            return self.report.verdict is not Verdict.SUPPORTED
        # A deterministic CONTRADICTION (the abstract positively asserts the
        # opposite direction) is never silently settled by the model. The
        # model's read is still surfaced for transparency, but a human must
        # confirm before an opposition signal is overturned — the same
        # discipline that pins a retracted row in the ranker regardless of what
        # the LLM proposes.
        if self.report.verdict is Verdict.CONTRADICTION:
            return True
        # Otherwise only a quote-anchored "supported" is settled.
        return not (a.verdict is Support.SUPPORTED and a.quote_verified)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "quote": self.quote,
            "needs_human": self.needs_human,
            "escalated": self.escalated,
            "deterministic": self.report.to_dict(),
            "adjudication": self.adjudication.to_dict() if self.adjudication else None,
            "note": self.note,
        }


def review_claim(
    claim_text: str,
    source_text: str,
    *,
    backend: Optional[AdjudicatorBackend] = None,
    title: str = "",
    cannabinoid: Optional[str] = None,
    partner_drug: Optional[str] = None,
    cyp_isoform: Optional[str] = None,
    direction_hint: Optional[str] = None,
    escalate: Optional[bool] = None,
) -> ClaimReview:
    """Deterministically flag a claim, then LLM-adjudicate the flagged minority.

    :func:`assess_support` runs first and is the always-present floor. The LLM
    ``backend`` — if supplied — is consulted ONLY on a claim the flagger flagged
    (:func:`gates_to_llm`) that actually has text to read: a confident
    deterministic ``SUPPORTED``, or a ``NO_TEXT`` claim, never spends a call.
    ``escalate=None`` auto-decides via the gate; ``True`` forces a read on any
    claim with text; ``False`` disables the model entirely.

    Whatever the backend returns is quote-gated (:func:`verify_quote`) against
    the *same* source text the model read, so a hallucinated supporting sentence
    is dropped before it can be surfaced — the verdict degrades to the
    deterministic floor and a human, it never silently fabricates evidence. A
    backend that raises is caught and degrades to the floor as well.
    """
    report = assess_support(
        claim_text,
        source_text,
        title=title,
        cannabinoid=cannabinoid,
        partner_drug=partner_drug,
        cyp_isoform=cyp_isoform,
        direction_hint=direction_hint,
    )

    # The text the model reads (and the text a quote is verified against) is the
    # same title+abstract the deterministic check saw, so the three stay aligned.
    full = f"{title}\n{source_text}".strip() if title else source_text
    have_text = report.verdict is not Verdict.NO_TEXT

    if escalate is None:
        do_adjudicate = (
            backend is not None
            and have_text
            and gates_to_llm(report, claim_text=claim_text)
        )
    else:
        do_adjudicate = bool(escalate) and backend is not None and have_text

    if not do_adjudicate:
        return ClaimReview(report=report, adjudication=None, escalated=False)

    try:
        adj = backend.adjudicate(
            claim_text,
            full,
            cannabinoid=cannabinoid,
            partner_drug=partner_drug,
            cyp_isoform=cyp_isoform,
            direction_hint=direction_hint,
        )
    except Exception as exc:  # noqa: BLE001 — degrade to the floor, never abort
        return ClaimReview(
            report=report,
            adjudication=None,
            escalated=False,
            note=f"adjudicator {getattr(backend, 'name', '?')!r} failed "
            f"({exc}); used deterministic flag",
        )

    verified = verify_quote(adj.quote, full)
    gated = Adjudication(
        verdict=adj.verdict,
        quote=adj.quote if verified else "",
        reason=adj.reason,
        quote_verified=verified,
        model=adj.model,
    )
    note = "model quote not found in source text; dropped" if (
        adj.quote and not verified
    ) else ""
    return ClaimReview(report=report, adjudication=gated, escalated=True, note=note)
