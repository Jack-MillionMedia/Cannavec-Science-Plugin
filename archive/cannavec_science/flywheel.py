"""The expert-gated curation flywheel (Constitution §IX) — finally as code.

§IX names the flywheel but, until now, no module implemented it:
*live discovery → identifier audit → claim-support check → human approves →
curated.* This module is that pipeline, built as three chained workflows over
the primitives the codebase already ships — nothing here re-implements a check
that already exists; it *orchestrates* them:

1. **Fan-out & synthesize** (:func:`fanout`) — gather candidate primary sources
   from the live multi-source discovery layer (and, coarsely, the local index),
   dedup by identifier, drop anything already known, and rank by relevance ×
   study design × recency. Reuses :mod:`cannavec_science.live` and
   :mod:`cannavec_science.ranker`.

2. **Generate & filter** (:func:`gate`) — run each candidate through the *same*
   admission gate a hand-curated row clears: safety/banned preflight (§V),
   identifier audit (§I), retraction status (§VIII), claim-support with a
   verbatim quote anchor, phytochemistry rigor (§VI), and a deterministic,
   conservative GRADE (§VII). Reuses ``pubmed_verify``, ``retraction``,
   ``claim_support``, ``rigor_checks``, ``safety``, ``banned_patterns`` and the
   ``evidence`` grade backbone.

3. **Classify & act** (:func:`classify`, :func:`stage`) — route each gated
   candidate into one of three lanes and write it to the staging queue:

   - ``REJECT`` — failed a mechanical gate; recorded with the reason (so the
     defect rate is *measured*, not hidden).
   - ``NEEDS_EXPERT`` — mechanically sound, but the promote decision hinges on
     clinical depth (grade ≥ B, evidence-synthesis design, weak/partial
     support, or an identifier we could not network-verify). Held for an expert.
   - ``BASIC_APPROVABLE`` — the gate reduced the decision to facts a
     non-specialist can confirm: a verified identifier, a *supported* claim with
     a verbatim abstract quote, a clean rigor pass, and a conservative grade
     (≤ Level C, single source). Safe for a basic curator to promote.

**Nothing here promotes anything.** Promotion is :func:`apply_promotion`, a
separate, explicit, human-gated act that requires a named approver, re-checks
retraction at promotion time, and is reversible (:func:`revoke_promotion`) —
exactly the §IX contract. Fully-automatic promotion stays out of scope.

The verified tier this grows (``verified_sources.jsonl``) is deliberately a
*third* thing: gate-passed citable sources that are neither raw candidates
(``primary_source_index.csv``) nor hand-authored registry rows. It never trips
``test_source_index_integrity``.

Stdlib only. All network is injected (``runners`` for discovery, ``*_fetcher``
for verification, ``adjudicator`` for the optional LLM claim read), so the
offline suite runs the whole flywheel with zero network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Mapping, Optional, Sequence

from cannavec_science._log import get_logger
from cannavec_science.curation_store import (
    STAGING_FILE,
    VERIFIED_FILE,
    append_jsonl,
    read_jsonl,
    rewrite_jsonl,
    utcnow,
)

__all__ = [
    "TARGET_VERIFIED",
    "Lane",
    "GateResult",
    "StagedCandidate",
    "VerifiedSource",
    "FlywheelReport",
    "ApplyResult",
    "fanout",
    "gate",
    "classify",
    "stage",
    "run_flywheel",
    "sweep_holes",
    "apply_promotion",
    "reject_candidate",
    "revoke_promotion",
    "queue",
    "verified_sources",
    "verified_candidates",
    "weave_verified_findings",
    "curated_identifiers",
    "stats",
]

_log = get_logger("flywheel")

# The growth target the demand-prioritised flywheel exists to reach — through
# the gate, one human-approved turn at a time (never auto-promoted).
TARGET_VERIFIED = 1500

# §VIII statuses that must be badged and pinned last when surfacing breadth.
_RETRACT_FLAGGED = frozenset({"retracted", "expression_of_concern", "under_correction"})


class Lane(str, Enum):
    """Where a gated candidate is routed (the *act* of stage 3)."""

    REJECT = "reject"               # failed a mechanical gate
    NEEDS_EXPERT = "needs_expert"   # sound, but the call needs clinical depth
    BASIC_APPROVABLE = "basic_approvable"  # reduced to facts a basic curator can confirm


# ── identifier shape ──────────────────────────────────────────────────────

def _id_type(identifier: str) -> str:
    """Classify an identifier into the §I shapes the gate can audit."""
    s = (identifier or "").strip()
    if not s:
        return "none"
    if re.fullmatch(r"\d{1,9}", s):
        return "PMID"
    if s.lower().startswith("10."):
        return "DOI"
    if re.fullmatch(r"NCT\d{8}", s, re.IGNORECASE):
        return "NCT"
    if re.fullmatch(r"CHEMBL\d+", s, re.IGNORECASE):
        return "ChEMBL"
    if re.fullmatch(r"PMC\d+", s, re.IGNORECASE):
        return "PMC"
    from cannavec_science.uniprot_verify import is_uniprot_accession
    if is_uniprot_accession(s):
        return "UniProt"
    return "other"


# ── conservative GRADE (§VII) ─────────────────────────────────────────────

def _provisional_grade(study_types: Sequence[str]):
    """Map a candidate's study design to a *conservative* GRADE level.

    Returns ``(EvidenceLevel, design_label, grade_needs_expert)``. The flywheel
    NEVER assigns Level A — Level A requires a systematic-review / ≥2-aligned-RCT
    judgement that is exactly the clinical-depth call we defer. An evidence-
    synthesis design caps at B and is flagged for expert grading. A single RCT
    caps at C (B would require confirming pre-registration + power + major
    journal, which the gate cannot do unsupervised, §VII / evidence.py).
    """
    from cannavec_science.evidence import EvidenceLevel

    text = " ".join(str(s) for s in study_types).lower()

    def has(*keys: str) -> bool:
        return any(k in text for k in keys)

    if has("systematic review", "meta-analysis", "meta analysis", "cochrane"):
        return EvidenceLevel.B, "evidence synthesis", True
    if has("randomized", "randomised", "rct", "controlled trial"):
        return EvidenceLevel.C, "randomized controlled trial", False
    if has("cohort", "case-control", "case control", "cross-sectional",
           "observational", "registry", "prospective", "retrospective"):
        return EvidenceLevel.C, "observational", False
    if has("case report", "case series", "case-report"):
        return EvidenceLevel.E, "case report/series", False
    if has("in vitro", "animal", "mouse", "rat", "preclinical", "cell line"):
        return EvidenceLevel.D, "preclinical/mechanistic", False
    return EvidenceLevel.C, "unspecified design", True


# ── supporting-quote extraction (deterministic, no LLM) ───────────────────

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]{3,}")
_STOP = frozenset(
    "with that this from were have been into than then they them their there "
    "which while about against between compared placebo patients study trial "
    "results conclusion methods background versus among".split()
)
_DIRECTION = ("reduc", "decreas", "increas", "improv", "lower", "raise",
              "inhibit", "induc", "no effect", "no significant", "worsen")


def _content_words(text: str) -> list[str]:
    return [w for w in (m.group(0).lower() for m in _WORD.finditer(text))
            if w not in _STOP]


def _supporting_sentence(claim_text: str, abstract: str) -> str:
    """Verbatim abstract sentence that best anchors the claim.

    Scores each abstract sentence by shared content words with the claim
    (a direction term — *reduced* / *increased* / … — breaks ties), so the
    verified row ships a real, in-source quote — provenance without an LLM. The
    chosen span is confirmed a true substring via :func:`verify_quote` before it
    is surfaced; a fabricated sentence can never slip through.
    """
    from cannavec_science.claim_support import verify_quote

    if not abstract or not claim_text:
        return ""
    claim_terms = set(_content_words(claim_text))
    if not claim_terms:
        return ""
    best, best_score = "", 0.0
    for sent in (s.strip() for s in _SENT_SPLIT.split(abstract)):
        if not sent:
            continue
        low = sent.lower()
        overlap = len(claim_terms & set(_content_words(sent)))
        if overlap == 0:
            continue
        score = overlap + (0.5 if any(d in low for d in _DIRECTION) else 0.0)
        if score > best_score:
            best, best_score = sent, score
    return best if best and verify_quote(best, abstract) else ""


# ── GateResult ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GateResult:
    """The auditable outcome of running one candidate through the gate."""

    identifier: str
    id_type: str
    claim_text: str
    support_quote: str
    grade: str
    checks: dict
    fatal: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()

    @property
    def lane(self) -> Lane:
        if self.fatal:
            return Lane.REJECT
        if self.flags:
            return Lane.NEEDS_EXPERT
        return Lane.BASIC_APPROVABLE

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "id_type": self.id_type,
            "claim_text": self.claim_text,
            "support_quote": self.support_quote,
            "grade": self.grade,
            "checks": dict(self.checks),
            "fatal": list(self.fatal),
            "flags": list(self.flags),
            "lane": self.lane.value,
        }


def gate(
    candidate,
    *,
    claim_text: Optional[str] = None,
    abstract: Optional[str] = None,
    abstract_fetcher=None,
    verify_fetcher=None,
    check_identifier: Optional[bool] = None,
    adjudicator=None,
    escalate: Optional[bool] = None,
) -> GateResult:
    """Run one :class:`~cannavec_science.ranker.Candidate` through the admission
    gate — the *same* gate a hand-curated row clears (§IX).

    Network is injected and optional: ``verify_fetcher`` for the identifier
    audit, ``abstract_fetcher`` to fetch the claim-support text, ``adjudicator``
    for the optional LLM claim read. With nothing injected the gate still runs
    fully — it simply cannot *network-verify* an identifier, so such a candidate
    is flagged ``NEEDS_EXPERT`` rather than silently passed (the safe direction).

    ``check_identifier`` defaults to "verify iff a fetcher was supplied"; pass
    ``True`` to force the live default fetcher (the ``--network`` path).
    """
    from cannavec_science.banned_patterns import detect_banned_patterns
    from cannavec_science.claim_support import (
        Support,
        Verdict,
        assess_support,
        review_claim,
    )
    from cannavec_science.evidence import EvidenceLevel
    from cannavec_science.retraction import is_retracted
    from cannavec_science.rigor_checks import run_rigor_checks
    from cannavec_science.safety import check_safety

    ident = (getattr(candidate, "identifier", "") or "").strip()
    title = getattr(candidate, "title", "") or ""
    claim = (claim_text or title or "").strip()
    if abstract is None:
        abstract = getattr(candidate, "abstract", "") or ""
    if not abstract and abstract_fetcher is not None and ident:
        try:
            abstract = abstract_fetcher(ident) or ""
        except Exception as exc:  # noqa: BLE001 — a fetch miss is just "no text"
            _log.warning("abstract fetch failed for %s: %s", ident, exc)
            abstract = ""

    checks: dict = {}
    fatal: list[str] = []
    flags: list[str] = []
    id_type = _id_type(ident)

    # 0. citable at all (§I)
    if not ident:
        checks["identifier"] = "missing"
        fatal.append("no primary-source identifier (§I)")
        return GateResult(ident, id_type, claim, "", EvidenceLevel.UNSUPPORTED.value,
                          checks, tuple(fatal), tuple(flags))
    if not claim:
        flags.append("no claim text to evaluate — title/abstract empty")

    # 1. safety + banned-pattern preflight on the surfaced claim (§V)
    sv = check_safety(claim)
    if getattr(sv, "refused", False):
        checks["safety"] = "refused"
        fatal.append("safety preflight refused the claim wording (§V)")
    else:
        checks["safety"] = "proceed"
    bp = detect_banned_patterns(claim)
    if bp:
        checks["banned_patterns"] = f"{len(bp)} hit(s)"
        fatal.append(f"banned-pattern hit in claim wording: {bp[0].pattern.id} (§V)")
    else:
        checks["banned_patterns"] = "clean"

    # 2. identifier audit (§I) — injected/optional network
    if check_identifier is None:
        check_identifier = verify_fetcher is not None
    if check_identifier:
        _audit_identifier(ident, id_type, verify_fetcher, checks, fatal, flags)
    else:
        checks["identifier"] = "unverified"
        flags.append("identifier not network-verified — confirm it resolves before promoting (§I)")

    # 3. retraction registry — defence in depth, re-checked at promotion too (§VIII)
    rec = is_retracted(
        pmid=ident if id_type == "PMID" else None,
        doi=ident if id_type == "DOI" else None,
    )
    if rec is not None:
        status = getattr(getattr(rec, "status", None), "value", "flagged")
        checks["retraction"] = status
        fatal.append(f"retraction registry: {status} (§VIII)")
    else:
        checks.setdefault("retraction", "clean")

    # 4. claim-support — the "right paper, wrong claim" gate
    quote = ""
    if not abstract:
        checks["claim_support"] = "no_text"
        flags.append("no abstract to confirm claim support — cannot auto-approve")
    elif adjudicator is not None or escalate:
        review = review_claim(claim, abstract, backend=adjudicator,
                              title=title, escalate=escalate)
        v = review.verdict
        quote = review.quote or ""
        if v == Support.SUPPORTED and quote:
            checks["claim_support"] = "supported"
        elif v == Support.SUPPORTED:
            checks["claim_support"] = "supported_no_quote"
            flags.append("LLM judged supported but no verifiable quote — needs read")
        elif v == Support.PARTIAL:
            checks["claim_support"] = "partial"
            flags.append("claim only partially supported by source — needs expert read")
        else:
            checks["claim_support"] = "unverified"
            fatal.append("claim not supported by its own source (§I)")
    else:
        rep = assess_support(claim, abstract, title=title)
        if rep.verdict == Verdict.SUPPORTED:
            checks["claim_support"] = "supported"
            quote = _supporting_sentence(claim, abstract)
            if not quote:
                flags.append("supported but no verbatim anchor extractable — needs read")
        elif rep.verdict == Verdict.WEAK:
            checks["claim_support"] = "weak"
            flags.append("claim support weak (entities present, direction not evidenced) — needs read")
        elif rep.verdict == Verdict.CONTRADICTION:
            checks["claim_support"] = "contradiction"
            fatal.append("source abstract contradicts the claim direction (§I)")
        elif rep.verdict == Verdict.UNVERIFIED:
            checks["claim_support"] = "unverified"
            fatal.append("core claim entity absent from the source abstract (§I)")
        else:
            checks["claim_support"] = "no_text"
            flags.append("no abstract to confirm claim support — cannot auto-approve")

    # 5. phytochemistry rigor on the surfaced wording (§VI). Only the seven
    # phytochemistry detectors gate here — reporting-rigor completeness (inline
    # N / CI / effect size) is a §VII expert-authoring concern that belongs to
    # graduating a verified source into a full registry row, not to admitting
    # the source itself.
    rigor = run_rigor_checks(f"{claim}\n{title}")
    phyto_violations = (
        rigor.isomer_violations
        + rigor.receptor_violations
        + rigor.dose_route_violations
        + rigor.thca_thc_violations
        + rigor.matrix_unit_violations
        + rigor.decarb_context_violations
        + rigor.entourage_violations
    )
    if phyto_violations:
        checks["rigor"] = "violations"
        flags.append("claim wording needs a phytochemistry-precision rewrite before it can be cited (§VI)")
    else:
        checks["rigor"] = "clean"

    # 6. conservative GRADE (§VII)
    level, label, grade_needs_expert = _provisional_grade(
        getattr(candidate, "study_types", ()) or ()
    )
    checks["grade"] = f"{level.value} ({label})"
    if grade_needs_expert:
        flags.append(f"grade is a clinical-depth call ({label}) — requires expert confirmation (§VII)")
    if level.rank >= EvidenceLevel.B.rank:
        flags.append(f"grade {level.value} asserted — single-source promotions cap at Level C unless an expert confirms (§VII)")

    return GateResult(
        identifier=ident,
        id_type=id_type,
        claim_text=claim,
        support_quote=quote,
        grade=level.value,
        checks=checks,
        fatal=tuple(fatal),
        flags=tuple(flags),
    )


def _audit_identifier(ident, id_type, verify_fetcher, checks, fatal, flags) -> None:
    """Identifier audit branch of :func:`gate` (§I). Mutates the accumulators."""
    from cannavec_science.pubmed_verify import (
        VerificationVerdict,
        verify_doi,
        verify_pmid,
    )
    from cannavec_science.uniprot_verify import verify_uniprot

    try:
        if id_type == "PMID":
            res = verify_pmid(ident, fetcher=verify_fetcher)
        elif id_type == "DOI":
            res = verify_doi(ident, fetcher=verify_fetcher)
        elif id_type == "UniProt":
            rec = verify_uniprot(ident, fetcher=verify_fetcher)
            if rec is None:
                checks["identifier"] = "not_found"
                fatal.append("UniProt accession did not resolve (§I)")
            else:
                checks["identifier"] = "verified"
            return
        else:
            checks["identifier"] = "unchecked"
            flags.append(f"{id_type} identifier not offline-verifiable here — confirm before promoting (§I)")
            return
    except Exception as exc:  # noqa: BLE001 — a transport failure is not a defect
        checks["identifier"] = "network_error"
        flags.append(f"could not verify identifier (transport error: {exc}) — confirm before promoting")
        return

    verdict = res.verdict
    checks["retraction"] = getattr(res, "retraction_status", "unknown")
    if verdict == VerificationVerdict.RETRACTED:
        checks["identifier"] = "retracted"
        fatal.append("identifier resolves to a RETRACTED record (§VIII)")
    elif verdict == VerificationVerdict.NOT_FOUND:
        checks["identifier"] = "not_found"
        fatal.append("identifier does not resolve to a real record (§I)")
    elif verdict == VerificationVerdict.MISMATCH:
        checks["identifier"] = "mismatch"
        fatal.append("identifier resolves to a different paper than claimed (§I)")
    elif verdict == VerificationVerdict.NETWORK_ERROR:
        checks["identifier"] = "network_error"
        flags.append("identifier verification hit a network error — confirm before promoting")
    else:  # MATCH | BARE_CITE_OK
        checks["identifier"] = "verified"


def classify(result: GateResult) -> Lane:
    """Stage 3, classify: map a :class:`GateResult` to its routing :class:`Lane`.

    The rule lives on :attr:`GateResult.lane`; this is the named public entry so
    the three-workflow chain reads cleanly and the policy has one home.
    """
    return result.lane


# ── StagedCandidate / VerifiedSource ──────────────────────────────────────

@dataclass(frozen=True)
class StagedCandidate:
    """One row in the staging queue — a gated candidate awaiting a human."""

    identifier: str
    id_type: str
    url: str
    topic: str
    provenance: str
    claim_text: str
    support_quote: str
    grade: str
    lane: str
    status: str  # pending | approved | rejected
    checks: dict
    reasons: list
    staged_at: str
    decided_at: Optional[str] = None
    approver: Optional[str] = None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "id_type": self.id_type,
            "url": self.url,
            "topic": self.topic,
            "provenance": self.provenance,
            "claim_text": self.claim_text,
            "support_quote": self.support_quote,
            "grade": self.grade,
            "lane": self.lane,
            "status": self.status,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
            "staged_at": self.staged_at,
            "decided_at": self.decided_at,
            "approver": self.approver,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StagedCandidate":
        return cls(
            identifier=str(d.get("identifier", "")),
            id_type=str(d.get("id_type", "")),
            url=str(d.get("url", "")),
            topic=str(d.get("topic", "")),
            provenance=str(d.get("provenance", "")),
            claim_text=str(d.get("claim_text", "")),
            support_quote=str(d.get("support_quote", "")),
            grade=str(d.get("grade", "")),
            lane=str(d.get("lane", "")),
            status=str(d.get("status", "pending")),
            checks=dict(d.get("checks", {}) or {}),
            reasons=list(d.get("reasons", []) or []),
            staged_at=str(d.get("staged_at", "")),
            decided_at=d.get("decided_at"),
            approver=d.get("approver"),
            note=str(d.get("note", "") or ""),
        )


def _candidate_url(candidate, id_type: str, identifier: str) -> str:
    url = getattr(candidate, "url", "") or ""
    if url:
        return url
    if id_type == "PMID":
        return f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"
    if id_type == "DOI":
        return f"https://doi.org/{identifier}"
    if id_type == "PMC":
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{identifier}/"
    if id_type == "NCT":
        return f"https://clinicaltrials.gov/study/{identifier}"
    return ""


def stage(
    candidate,
    result: GateResult,
    lane: Optional[Lane] = None,
    *,
    topic: str = "",
    store_dir: Optional[str] = None,
    now: Optional[str] = None,
    _existing: Optional[set] = None,
) -> Optional[StagedCandidate]:
    """Stage 3, act: route a gated candidate into the staging queue.

    Idempotent by identifier — a candidate already staged or already verified is
    not re-routed (returns ``None``). A ``REJECT`` candidate is still recorded
    (status ``rejected``) so the *defect rate is measured*, never hidden.
    """
    lane = lane or classify(result)
    ident = result.identifier
    if not ident:
        return None
    if _existing is None:
        _existing = _known_identifiers(store_dir)
    if ident in _existing:
        return None

    sc = StagedCandidate(
        identifier=ident,
        id_type=result.id_type,
        url=_candidate_url(candidate, result.id_type, ident),
        topic=topic or getattr(candidate, "topic", "") or "",
        provenance=getattr(candidate, "source", "") or "",
        claim_text=result.claim_text,
        support_quote=result.support_quote,
        grade=result.grade,
        lane=lane.value,
        status="rejected" if lane == Lane.REJECT else "pending",
        checks=result.checks,
        reasons=list(result.fatal) + list(result.flags),
        staged_at=now or utcnow(),
    )
    append_jsonl(STAGING_FILE, sc.to_dict(), store_dir)
    return sc


# ── fan-out & synthesize (stage 1) ────────────────────────────────────────

def _index_by_topic_substr(substr: str):
    """Source-index rows whose coarse CSV topic tag contains ``substr``."""
    from cannavec_science.source_index import load_index
    s = substr.strip().lower()
    return tuple(r for r in load_index() if s in r.topic.lower())


def fanout(
    query: str,
    *,
    live: bool = False,
    sources: Optional[Sequence[str]] = None,
    max_results: int = 25,
    runners: Optional[Mapping] = None,
    since: Optional[str] = None,
    index_topic: Optional[str] = None,
    extra_candidates: Sequence = (),
    exclude_known: bool = True,
    store_dir: Optional[str] = None,
):
    """Stage 1, fan-out & synthesize: gather + dedup + rank candidate sources.

    Sources, in order of value: ``extra_candidates`` (caller-supplied, e.g. a
    seeded batch), the live discovery fan-out (``live=True`` or injected
    ``runners``), and a coarse pre-filter of the local index
    (``index_topic``, a CSV topic substring — bare identifiers, no text). The
    pool is deduped by identifier, stripped of anything already known (curated,
    verified, or staged), and ranked by the shared BM25 × design × recency
    ranker. Safety preflight (§V) runs before any network call.
    """
    from cannavec_science.discover_guard import DiscoverRefused, preflight
    from cannavec_science.ranker import (
        Candidate,
        candidates_from_discovery,
        rank_candidates,
    )

    if not query or not query.strip():
        raise ValueError("fanout() requires a non-empty query")
    preflight(query)  # §V — raises DiscoverRefused; no network on refusal

    pool: list = list(extra_candidates)

    if live or runners is not None:
        from cannavec_science.live import run_discovery
        try:
            result = run_discovery(
                query, sources=sources, max_results=max_results,
                since=since, runners=runners,
            )
            pool.extend(candidates_from_discovery(result))
        except DiscoverRefused:
            raise
        except Exception as exc:  # noqa: BLE001 — degrade; a dead lane is not fatal
            _log.warning("fanout live discovery failed: %s", exc)

    if index_topic:
        for ref in _index_by_topic_substr(index_topic):
            pool.append(Candidate.from_source_ref(ref))

    known = _known_identifiers(store_dir) if exclude_known else set()
    uniq: dict = {}
    for c in pool:
        ident = (getattr(c, "identifier", "") or "").strip()
        if not ident or ident in known or ident in uniq:
            continue
        uniq[ident] = c
    cands = list(uniq.values())
    if not cands:
        return []

    try:
        ranked = rank_candidates(query, cands, top_k=max(1, max_results)).ranked
        ordered = [rc.candidate for rc in ranked]
        seen = {c.identifier for c in ordered}
        ordered.extend(c for c in cands if c.identifier not in seen)
    except Exception as exc:  # noqa: BLE001 — ranking is best-effort
        _log.warning("fanout ranking failed: %s", exc)
        ordered = cands
    return ordered[:max_results]


# ── the orchestrator ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class FlywheelReport:
    """Summary of one flywheel turn over a query/topic."""

    query: str
    topic: str
    candidates: int
    basic_approvable: int
    needs_expert: int
    rejected: int
    staged: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "topic": self.topic,
            "candidates": self.candidates,
            "basic_approvable": self.basic_approvable,
            "needs_expert": self.needs_expert,
            "rejected": self.rejected,
            "staged": [s.to_dict() for s in self.staged],
        }


def run_flywheel(
    query: str,
    *,
    topic: Optional[str] = None,
    live: bool = False,
    sources: Optional[Sequence[str]] = None,
    max_results: int = 25,
    runners: Optional[Mapping] = None,
    since: Optional[str] = None,
    index_topic: Optional[str] = None,
    extra_candidates: Sequence = (),
    claims: Optional[Mapping[str, str]] = None,
    abstracts: Optional[Mapping[str, str]] = None,
    abstract_fetcher=None,
    verify_fetcher=None,
    check_identifier: Optional[bool] = None,
    adjudicator=None,
    store_dir: Optional[str] = None,
    now: Optional[str] = None,
) -> FlywheelReport:
    """Chain the three workflows over one query: fan-out → gate → classify+act.

    ``claims`` / ``abstracts`` let a caller supply a specific extracted claim and
    its source text per identifier (the seeding path). Everything network is
    injected, so the whole turn runs offline in tests.
    """
    from cannavec_science.demand import classify_topic

    topic = topic or classify_topic(query)
    cands = fanout(
        query, live=live, sources=sources, max_results=max_results,
        runners=runners, since=since, index_topic=index_topic,
        extra_candidates=extra_candidates, exclude_known=True, store_dir=store_dir,
    )
    existing = _known_identifiers(store_dir)
    staged: list = []
    n_basic = n_expert = n_reject = 0
    for c in cands:
        ident = (getattr(c, "identifier", "") or "").strip()
        claim_text = claims.get(ident) if claims else None
        abstract = abstracts.get(ident) if abstracts else None
        result = gate(
            c, claim_text=claim_text, abstract=abstract,
            abstract_fetcher=abstract_fetcher, verify_fetcher=verify_fetcher,
            check_identifier=check_identifier, adjudicator=adjudicator,
        )
        lane = classify(result)
        sc = stage(c, result, lane, topic=topic, store_dir=store_dir,
                   now=now, _existing=existing)
        if sc is None:
            continue
        existing.add(ident)
        staged.append(sc)
        if lane == Lane.BASIC_APPROVABLE:
            n_basic += 1
        elif lane == Lane.NEEDS_EXPERT:
            n_expert += 1
        else:
            n_reject += 1
    return FlywheelReport(
        query=query, topic=topic, candidates=len(cands),
        basic_approvable=n_basic, needs_expert=n_expert,
        rejected=n_reject, staged=staged,
    )


def sweep_holes(
    *,
    n: int = 5,
    min_misses: int = 1,
    topics: Optional[Sequence[str]] = None,
    live: bool = True,
    sources: Optional[Sequence[str]] = None,
    max_results: int = 25,
    runners: Optional[Mapping] = None,
    verify_fetcher=None,
    check_identifier: Optional[bool] = None,
    abstract_fetcher=None,
    adjudicator=None,
    store_dir: Optional[str] = None,
    demand_store_dir: Optional[str] = None,
    now: Optional[str] = None,
) -> list[FlywheelReport]:
    """Work down the demand-ranked holes — one flywheel turn per top topic.

    The batch driver behind ``curate-sweep``: reads the demand report, takes the
    top ``n`` holes (or an explicit ``topics`` list), maps each to a primary-
    source query (:func:`cannavec_science.demand.topic_query`), and runs the full
    fan-out → gate → classify → stage pipeline for each. Returns one
    :class:`FlywheelReport` per topic.

    Network is injected (``runners`` / ``verify_fetcher``), so the whole sweep
    runs offline in tests; live by default for production use via ``--network``.
    """
    from cannavec_science.demand import priority_topics, topic_query

    picks = list(topics) if topics else priority_topics(
        n, min_misses=min_misses, store_dir=demand_store_dir
    )
    reports: list[FlywheelReport] = []
    for topic in picks:
        reports.append(run_flywheel(
            topic_query(topic), topic=topic, live=live, sources=sources,
            max_results=max_results, runners=runners,
            verify_fetcher=verify_fetcher, check_identifier=check_identifier,
            abstract_fetcher=abstract_fetcher, adjudicator=adjudicator,
            store_dir=store_dir, now=now,
        ))
    return reports


# ── human-gated apply / reject / revoke (§IX) ─────────────────────────────

@dataclass(frozen=True)
class ApplyResult:
    """Outcome of a promotion attempt — ``ok`` plus an audit-ready reason."""

    ok: bool
    reason: str
    verified: Optional[dict] = None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "verified": self.verified}


@dataclass(frozen=True)
class VerifiedSource:
    """A source promoted *through the gate* into the verified tier (§IX)."""

    identifier: str
    id_type: str
    url: str
    topic: str
    provenance: str
    claim_text: str
    support_quote: str
    grade: str
    lane: str
    status: str  # verified | revoked
    approver: str
    approved_at: str
    checks: dict
    revoked_at: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "id_type": self.id_type,
            "url": self.url,
            "topic": self.topic,
            "provenance": self.provenance,
            "claim_text": self.claim_text,
            "support_quote": self.support_quote,
            "grade": self.grade,
            "lane": self.lane,
            "status": self.status,
            "approver": self.approver,
            "approved_at": self.approved_at,
            "revoked_at": self.revoked_at,
            "reason": self.reason,
            "checks": dict(self.checks),
        }


def _latest_by_identifier(records: list[dict]) -> dict:
    """Last-write-wins view of a JSONL ledger keyed by identifier."""
    out: dict = {}
    for rec in records:
        ident = rec.get("identifier")
        if ident:
            out[ident] = rec
    return out


def apply_promotion(
    identifier: str,
    *,
    approver: str,
    note: str = "",
    allow_expert_lane: bool = False,
    verify_fetcher=None,
    store_dir: Optional[str] = None,
    now: Optional[str] = None,
) -> ApplyResult:
    """Promote one staged candidate into the verified tier — the human gate (§IX).

    Refuses unless a named ``approver`` is given. Refuses to promote a
    ``REJECT`` row, or a ``NEEDS_EXPERT`` row unless ``allow_expert_lane`` (the
    explicit record that an expert acted). **Re-checks retraction at promotion
    time** (§IX): a row retracted since staging is rejected, not promoted. The
    promotion records provenance, approver, and timestamp, and is reversible via
    :func:`revoke_promotion`.
    """
    from cannavec_science.retraction import is_retracted

    approver = (approver or "").strip()
    if not approver:
        return ApplyResult(False, "promotion requires a named --approver (Constitution §IX human gate)")

    staging = read_jsonl(STAGING_FILE, store_dir)
    rec = _latest_by_identifier(staging).get(identifier)
    if rec is None:
        return ApplyResult(False, f"{identifier} is not in the staging queue")
    if rec.get("status") != "pending":
        return ApplyResult(False, f"{identifier} is not pending (status={rec.get('status')})")

    lane = rec.get("lane")
    if lane == Lane.REJECT.value:
        return ApplyResult(False, f"{identifier} was rejected by the gate and cannot be promoted")
    if lane == Lane.NEEDS_EXPERT.value and not allow_expert_lane:
        return ApplyResult(
            False,
            f"{identifier} is in the NEEDS_EXPERT lane; promotion requires an expert "
            f"(re-run with allow_expert_lane / --expert-override to record that an expert approved)",
        )

    # §IX: not-retracted, re-checked at promotion time.
    id_type = rec.get("id_type")
    rret = is_retracted(
        pmid=identifier if id_type == "PMID" else None,
        doi=identifier if id_type == "DOI" else None,
    )
    if rret is not None:
        _set_staging_status(staging, identifier, "rejected", approver,
                            f"retracted at promotion time: {getattr(rret.status, 'value', rret.status)}",
                            now, store_dir)
        return ApplyResult(False, f"{identifier} is retracted as of promotion time — not promoted (§VIII)")

    ts = now or utcnow()
    verified = VerifiedSource(
        identifier=identifier,
        id_type=id_type or "",
        url=rec.get("url", ""),
        topic=rec.get("topic", ""),
        provenance=rec.get("provenance", ""),
        claim_text=rec.get("claim_text", ""),
        support_quote=rec.get("support_quote", ""),
        grade=rec.get("grade", ""),
        lane=lane,
        status="verified",
        approver=approver,
        approved_at=ts,
        checks=rec.get("checks", {}) or {},
    )
    append_jsonl(VERIFIED_FILE, verified.to_dict(), store_dir)
    _set_staging_status(staging, identifier, "approved", approver, note, ts, store_dir)
    return ApplyResult(True, f"promoted {identifier} to the verified tier", verified.to_dict())


def reject_candidate(
    identifier: str,
    *,
    approver: str,
    reason: str = "",
    store_dir: Optional[str] = None,
    now: Optional[str] = None,
) -> ApplyResult:
    """Curator-reject a pending candidate (records who + why)."""
    approver = (approver or "").strip()
    if not approver:
        return ApplyResult(False, "rejection requires a named --approver")
    staging = read_jsonl(STAGING_FILE, store_dir)
    rec = _latest_by_identifier(staging).get(identifier)
    if rec is None:
        return ApplyResult(False, f"{identifier} is not in the staging queue")
    _set_staging_status(staging, identifier, "rejected", approver,
                        reason or "curator rejection", now or utcnow(), store_dir)
    return ApplyResult(True, f"rejected {identifier}")


def revoke_promotion(
    identifier: str,
    *,
    approver: str,
    reason: str = "",
    store_dir: Optional[str] = None,
    now: Optional[str] = None,
) -> ApplyResult:
    """Reverse a promotion — the §IX reversibility guarantee.

    Marks the verified row ``revoked`` (kept for the audit trail) and returns the
    staging row to ``pending`` so it can be re-decided.
    """
    approver = (approver or "").strip()
    if not approver:
        return ApplyResult(False, "revocation requires a named --approver")
    verified = read_jsonl(VERIFIED_FILE, store_dir)
    latest = _latest_by_identifier(verified).get(identifier)
    if latest is None or latest.get("status") != "verified":
        return ApplyResult(False, f"{identifier} is not currently verified")
    ts = now or utcnow()
    for rec in verified:
        if rec.get("identifier") == identifier and rec.get("status") == "verified":
            rec["status"] = "revoked"
            rec["revoked_at"] = ts
            rec["reason"] = reason or "curator revocation"
            rec["approver"] = approver
    rewrite_jsonl(VERIFIED_FILE, verified, store_dir)
    staging = read_jsonl(STAGING_FILE, store_dir)
    if _latest_by_identifier(staging).get(identifier):
        _set_staging_status(staging, identifier, "pending", approver,
                            f"revoked: {reason}", ts, store_dir)
    return ApplyResult(True, f"revoked {identifier}")


def _set_staging_status(staging, identifier, status, approver, note, ts, store_dir) -> None:
    """Rewrite the staging ledger with the latest row's status updated."""
    target = None
    for rec in staging:
        if rec.get("identifier") == identifier:
            target = rec  # last occurrence wins
    if target is None:
        return
    target["status"] = status
    target["approver"] = approver
    target["note"] = note
    target["decided_at"] = ts
    rewrite_jsonl(STAGING_FILE, staging, store_dir)


# ── read API ──────────────────────────────────────────────────────────────

def queue(
    lane: Optional[str] = None,
    status: Optional[str] = "pending",
    *,
    store_dir: Optional[str] = None,
) -> list[dict]:
    """The staging queue (latest state per identifier), optionally filtered."""
    records = list(_latest_by_identifier(read_jsonl(STAGING_FILE, store_dir)).values())
    if status:
        records = [r for r in records if r.get("status") == status]
    if lane:
        records = [r for r in records if r.get("lane") == lane]
    records.sort(key=lambda r: (r.get("topic", ""), r.get("grade", ""), r.get("identifier", "")))
    return records


def verified_sources(
    topic: Optional[str] = None, *, store_dir: Optional[str] = None
) -> list[dict]:
    """All currently-verified sources (status ``verified``), optionally by topic."""
    records = [
        r for r in _latest_by_identifier(read_jsonl(VERIFIED_FILE, store_dir)).values()
        if r.get("status") == "verified"
    ]
    if topic:
        records = [r for r in records if r.get("topic") == topic]
    return records


def verified_candidates(
    topic: Optional[str] = None, *, store_dir: Optional[str] = None
):
    """The verified tier adapted to :class:`~cannavec_science.ranker.Candidate`.

    The integration seam: the retrieval/ranker layer can consume the verified
    tier as an additional, clearly-tagged (``source="verified_tier"``) candidate
    band — distinct from curated registry rows and from raw live findings.
    """
    from cannavec_science.ranker import Candidate
    out = []
    for r in verified_sources(topic, store_dir=store_dir):
        out.append(Candidate(
            identifier=r.get("identifier", ""),
            title=r.get("claim_text", ""),
            abstract=r.get("support_quote", ""),
            topic=r.get("topic", ""),
            source="verified_tier",
            curated=False,
            url=r.get("url", ""),
            retraction_status="clean",
        ))
    return out


def _display_identifier(rec: dict) -> str:
    """Human display label for a verified row's identifier (`PMID 12345`)."""
    ident = rec.get("identifier", "")
    id_type = rec.get("id_type", "")
    if id_type in ("PMID", "PMC", "NCT", "ChEMBL") and ident:
        return f"{id_type} {ident}"
    return ident


def weave_verified_findings(
    answer,
    *,
    prompt: Optional[str] = None,
    topic: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> int:
    """Weave verified-tier breadth onto ``answer`` (the §IX middle tier).

    Pulls the human-approved verified sources for the prompt's topic, reranks
    them by relevance to the prompt, **re-checks retraction at composition time**
    (§VIII — a source retracted since promotion is badged and pinned last), and
    attaches each via :meth:`~cannavec_science.answer.Answer.add_verified_finding`.

    Offline and stdlib (reads the local verified store, no network). Never
    touches ``answer.evidence_summary`` — breadth augments the curated core, it
    never re-grades it. Returns the number of findings attached.
    """
    from cannavec_science.retraction import is_retracted

    if topic is None and prompt:
        from cannavec_science.demand import classify_topic
        topic = classify_topic(prompt)
    pick = topic if topic and topic != "unclassified" else None
    rows = verified_sources(pick, store_dir=store_dir)
    if not rows:
        return 0

    # Rerank by relevance to the prompt (BM25 × design × recency), best-effort.
    if prompt:
        try:
            from cannavec_science.ranker import rank_candidates
            order = {
                rc.candidate.identifier: i
                for i, rc in enumerate(
                    rank_candidates(
                        prompt, verified_candidates(pick, store_dir=store_dir),
                        top_k=max(1, len(rows)),
                    ).ranked
                )
            }
            rows = sorted(rows, key=lambda r: order.get(r.get("identifier", ""), 1 << 30))
        except Exception as exc:  # noqa: BLE001 — ranking is a best-effort reorder
            _log.warning("verified weave rerank failed: %s", exc)

    # §VIII at composition: re-check retraction, badge + pin flagged rows last.
    scored = []
    for r in rows:
        ident = r.get("identifier", "")
        id_type = r.get("id_type", "")
        rec = is_retracted(
            pmid=ident if id_type == "PMID" else None,
            doi=ident if id_type == "DOI" else None,
        )
        status = getattr(getattr(rec, "status", None), "value", "clean") if rec else "clean"
        scored.append((r, status))
    scored.sort(key=lambda t: t[1] in _RETRACT_FLAGGED)

    attached = 0
    for r, status in scored:
        before = len(answer.verified_findings)
        answer.add_verified_finding(
            label=r.get("claim_text", ""),
            identifier=_display_identifier(r),
            grade=r.get("grade", ""),
            url=r.get("url", ""),
            quote=r.get("support_quote", ""),
            approver=r.get("approver", ""),
            topic=r.get("topic", ""),
            retraction_status=status,
        )
        if len(answer.verified_findings) > before:
            attached += 1
    return attached


@lru_cache(maxsize=1)
def curated_identifiers() -> frozenset:
    """Identifiers already hand-authored into a curated registry ``.py`` module.

    Scans the package source for ``pmid="..."`` / ``doi="..."`` literals — the
    same approach ``evals/audit_pmids`` uses — so the flywheel never re-proposes
    a source the registries already curate. Cached for the process lifetime.
    """
    import glob
    import os

    pkg = os.path.dirname(os.path.abspath(__file__))
    pmid_rx = re.compile(r"""pmid\s*=\s*["'](\d{4,9})["']""", re.IGNORECASE)
    doi_rx = re.compile(r"""doi\s*=\s*["'](10\.[^"']+)["']""", re.IGNORECASE)
    skip = {"flywheel.py", "demand.py", "curation_store.py", "source_index.py"}
    found: set = set()
    for path in glob.glob(os.path.join(pkg, "*.py")):
        if os.path.basename(path) in skip:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        found.update(pmid_rx.findall(text))
        found.update(doi_rx.findall(text))
    return frozenset(found)


def _known_identifiers(store_dir: Optional[str] = None) -> set:
    """Everything we should not re-stage: curated, verified, or already staged."""
    known: set = set(curated_identifiers())
    known.update(r.get("identifier") for r in read_jsonl(VERIFIED_FILE, store_dir))
    known.update(r.get("identifier") for r in read_jsonl(STAGING_FILE, store_dir))
    known.discard(None)
    known.discard("")
    return known


def stats(store_dir: Optional[str] = None) -> dict:
    """Flywheel health: verified-tier size, queue by lane, and the defect rate.

    The defect rate (rejected / scanned) is the headline guard — growing the
    verified tier *without* growing it is the whole point, and this is where you
    watch that the gate keeps the ~8% defect classes out.
    """
    from collections import Counter

    staging = list(_latest_by_identifier(read_jsonl(STAGING_FILE, store_dir)).values())
    verified_all = list(_latest_by_identifier(read_jsonl(VERIFIED_FILE, store_dir)).values())
    verified = [v for v in verified_all if v.get("status") == "verified"]

    by_status = Counter(r.get("status") for r in staging)
    pending = [r for r in staging if r.get("status") == "pending"]
    pending_by_lane = Counter(r.get("lane") for r in pending)
    scanned = len(staging)
    rejected = by_status.get("rejected", 0)
    n_curated = len(curated_identifiers())

    return {
        "curated_registry_identifiers": n_curated,
        "verified_tier": len(verified),
        "verified_plus_curated": len(verified) + n_curated,
        "target": TARGET_VERIFIED,
        "remaining_to_target": max(0, TARGET_VERIFIED - (len(verified) + n_curated)),
        "queue_pending_total": len(pending),
        "queue_pending_basic_approvable": pending_by_lane.get(Lane.BASIC_APPROVABLE.value, 0),
        "queue_pending_needs_expert": pending_by_lane.get(Lane.NEEDS_EXPERT.value, 0),
        "approved": by_status.get("approved", 0),
        "rejected": rejected,
        "revoked": sum(1 for v in verified_all if v.get("status") == "revoked"),
        "scanned": scanned,
        "defect_rate": round(rejected / scanned, 4) if scanned else 0.0,
        "verified_by_topic": dict(Counter(v.get("topic") for v in verified)),
    }
