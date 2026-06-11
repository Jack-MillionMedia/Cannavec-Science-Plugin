"""Chunk-level KB flywheel — extend the source-level audit from *identifiers* to
the *chunks* the live Cannavec KB actually returned, so real user activity
becomes a knowledge-base improvement backlog.

When the Cannavec MCP answers a user question it returns chunk prose. The model
forwards what it received (the external MCP's output never reaches this Python),
and **deterministic code computes every issue verdict** — the model proposes, the
verification layer disposes (Constitution §II). Four dimensions, per the KB
improvement brief:

- **retrieval**    — a chunk is weakly relevant to the query (lexical-coverage
                     floor), or *every* returned chunk is weak → the KB had no
                     good answer (a coverage gap worth authoring).
- **citation**     — a chunk identifier is fabricated / retracted / misattributed
                     (§I/§VIII), **or** the chunk makes a graded clinical claim
                     with **zero** citations (the uncited-claim hole).
- **accuracy**     — a cited abstract **contradicts** the chunk's claim
                     (deterministic), or does not support it (ambiguous → routed
                     to model review, never auto-judged).
- **completeness** — the chunk is a thin stub, or its declared ``evidence_grade``
                     exceeds what its study composition supports (§VII inflation).

Every issue is keyed on the chunk (``doc_id`` + H2 anchor) and appended to the
**same** operator improve-queue ``source_audit`` writes, so one flywheel feeds the
KB. Detectors are injected, so the audit logic is fully offline-testable (§X);
the defaults reuse the existing engine (no new verification logic, no new
network primitives).

This layer **flags and routes** — it never authors clinical claims and never
changes a grade (M5; the KB repo's Agent Boundary Rule). Resolution is a separate,
human/model-reviewed step.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from cannavec_science import source_audit

__all__ = [
    "Chunk", "ChunkIssue", "ChunkAudit", "audit_chunks",
    "RETRIEVAL", "CITATION", "ACCURACY", "COMPLETENESS",
]

# Dimensions (string constants so callers/tests reference one source of truth).
RETRIEVAL = "retrieval"
CITATION = "citation"
ACCURACY = "accuracy"
COMPLETENESS = "completeness"

# Routes mirror kb_audit.model.Finding.route, plus the escalation route for the
# one dimension that genuinely needs model judgement.
ROUTE_IMPROVE = "improve_agent"
ROUTE_RESEARCH = "deeper_research"
ROUTE_QUICKFIX = "quick_fix"
ROUTE_MODEL = "needs_model_review"

# Tunable, conservative thresholds. Named (not magic) so the rationale is legible.
RELEVANCE_FLOOR = 0.34          # a chunk must cover ≥ this fraction of the query's
                               # discriminating content terms, else weak-relevance.
STUB_TOKEN_FLOOR = 40           # a chunk shorter than this is a stub (the authoring
                               # standard wants 500–2,000-token H2 sections).

# id -> (verdict, reason); verdict ∈ {"PASS","FAIL","UNVERIFIED"}.  Same contract
# as source_audit's verifier, so the citation gate is identical to the source tier.
Verifier = Callable[[str], "tuple[str, str]"]
# pmid -> abstract text (or "" / None when unavailable → inconclusive, never a flag).
AbstractFn = Callable[[str], "str | None"]
# chunk text -> True if it makes a graded clinical claim that should carry a citation.
ClaimDetector = Callable[[str], bool]


# ── data model ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Chunk:
    """One KB chunk as the model forwarded it from the live MCP. All fields are
    best-effort: the external MCP decides what metadata travels, so the audit
    degrades gracefully when ``h2_anchor`` / ``score`` / ``citations`` are absent."""
    doc_id: str
    h2_anchor: str = ""
    text: str = ""
    citations: tuple = ()
    score: Optional[float] = None

    @property
    def chunk_key(self) -> str:
        return f"{self.doc_id}#{self.h2_anchor}" if self.h2_anchor else (self.doc_id or "")

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        """Tolerant parse of the model-forwarded payload. Accepts common aliases
        (``id``/``source``/``path`` for the doc; ``anchor``/``heading`` for the
        H2; ``content``/``snippet`` for the text) so the model isn't forced into
        one exact key spelling."""
        if not isinstance(d, dict):
            return cls(doc_id="")
        doc_id = str(d.get("doc_id") or d.get("id") or d.get("source")
                     or d.get("path") or d.get("canonicalId") or "").strip()
        anchor = str(d.get("h2_anchor") or d.get("anchor") or d.get("heading")
                     or d.get("h2") or "").strip()
        text = str(d.get("text") or d.get("content") or d.get("snippet") or "")
        raw_cites = d.get("citations") or d.get("identifiers") or d.get("sources") or ()
        if isinstance(raw_cites, str):
            # a model may forward citations as a delimited string ("PMID:1, 10.2/x")
            # rather than a list — parse it the same so a cited chunk isn't read as uncited.
            raw_cites = re.split(r"[,;\s]+", raw_cites)
        cites = tuple(str(c).strip() for c in raw_cites if str(c).strip()) \
            if isinstance(raw_cites, (list, tuple)) else ()
        score = d.get("score")
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        return cls(doc_id=doc_id, h2_anchor=anchor, text=text,
                   citations=cites, score=score)


@dataclass(frozen=True)
class ChunkIssue:
    """One problem found in (or about) a chunk. Mirrors kb_audit.model.Finding,
    keyed on the chunk so the backlog ties the issue to the exact content."""
    dimension: str          # retrieval | citation | accuracy | completeness
    chunk_key: str
    doc_id: str
    h2_anchor: str
    verdict: str            # short machine label, e.g. "false_citation"
    detail: str             # human one-liner
    evidence: str           # what the deterministic check observed
    recommended_action: str
    route: str              # improve_agent | deeper_research | quick_fix | needs_model_review

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension, "chunk_key": self.chunk_key,
            "doc_id": self.doc_id, "h2_anchor": self.h2_anchor,
            "verdict": self.verdict, "detail": self.detail,
            "evidence": self.evidence,
            "recommended_action": self.recommended_action, "route": self.route,
        }


@dataclass(frozen=True)
class ChunkAudit:
    query: str
    chunks_seen: int
    issues: tuple = ()
    logged_path: Optional[str] = None

    def by_dimension(self) -> dict:
        out: dict[str, int] = {}
        for i in self.issues:
            out[i.dimension] = out.get(i.dimension, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "chunks_seen": self.chunks_seen,
            "issues": [i.to_dict() for i in self.issues],
            "by_dimension": self.by_dimension(),
            "logged_path": self.logged_path,
        }


# ── retrieval (deterministic, lexical) ───────────────────────────────────────
#
# Ubiquitous domain words are dropped from the query's relevance terms — nearly
# every KB chunk says "cannabis"/"cbd"/"thc", so they carry no discriminating
# signal and would mask a real mis-retrieval. What remains is the topic /
# condition the user actually asked about; an off-topic chunk misses it.

_DOMAIN_NOISE = frozenset(
    "cannabis cannabinoid cannabinoids cbd thc marijuana hemp marijuanas".split())
_RELEVANCE_STOPWORDS = frozenset("""
a an and are as at be been being by for from has have how in into is it its of on
or that the their this to was were what when where which who why will with about
does do did can could should would may might must vs versus using use used uses
between effect effects affect benefit benefits risk risks safe safety help work
""".split()) | _DOMAIN_NOISE

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")


def _relevance_terms(query: str) -> "list[str]":
    """Discriminating content terms of a query — interrogative scaffolding and
    ubiquitous domain noise removed. Empty for a neutral query (→ skip the check
    rather than flag, exactly as topic filters fall back)."""
    from cannavec_science.intent import distill_query
    distilled = distill_query(query or "")
    terms = [w for w in _WORD_RE.findall(distilled.lower())
             if w not in _RELEVANCE_STOPWORDS]
    # de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _singular(w: str) -> str:
    """A crude de-pluralizer so a query term and chunk prose match across simple
    morphology (``seizures`` ↔ ``seizure``, ``therapies`` ↔ ``therapy``). Lexical
    only — it does not resolve synonymy (``children`` ↔ ``pediatric``)."""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _covers(term: str, hay: str) -> bool:
    """A query term is covered if it (or its singular) appears in the chunk — so a
    plural query against singular prose, or vice-versa, still matches."""
    if term in hay:
        return True
    s = _singular(term)
    return s != term and s in hay


def _coverage(terms: "list[str]", text: str) -> "tuple[int, list[str]]":
    hay = (text or "").lower()
    present = [t for t in terms if _covers(t, hay)]
    return len(present), [t for t in terms if not _covers(t, hay)]


def detect_retrieval_issue(query: str, chunk: Chunk) -> Optional[ChunkIssue]:
    """A single chunk that weakly covers the query's discriminating terms is a
    candidate mis-retrieval — routed to research (a human/model decides whether a
    more on-topic chunk exists or should be authored)."""
    terms = _relevance_terms(query)
    if not terms:
        return None                              # neutral query → no basis to flag
    covered, missing = _coverage(terms, chunk.text)
    coverage = covered / len(terms)
    if coverage >= RELEVANCE_FLOOR:
        return None
    miss = ", ".join(missing[:8])
    return ChunkIssue(
        dimension=RETRIEVAL, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
        h2_anchor=chunk.h2_anchor, verdict="weak_relevance",
        detail=f"chunk covers {covered}/{len(terms)} query terms ({coverage:.0%})",
        evidence=f"query terms absent from the chunk: {miss}",
        recommended_action="likely a mis-retrieval — confirm a more on-topic chunk "
                           "exists for this query, or author one",
        route=ROUTE_RESEARCH,
    )


def _thin_recall_issue(query: str, chunks_seen: int, all_weak: bool) -> Optional[ChunkIssue]:
    """Query-level coverage gap: the KB returned nothing, or nothing relevant.
    The single most valuable KB-growth signal — there is no good answer to author
    against yet."""
    if not _relevance_terms(query):
        return None                              # neutral query → no basis for a coverage gap
    if chunks_seen == 0:
        why = "the KB returned no chunks for this query"
    elif all_weak:
        why = "every returned chunk is weakly relevant to the query"
    else:
        return None
    return ChunkIssue(
        dimension=RETRIEVAL, chunk_key="", doc_id="", h2_anchor="",
        verdict="thin_recall", detail="coverage gap: no strongly-relevant chunk",
        evidence=why,
        recommended_action="author (or improve) a chunk that directly answers this query",
        route=ROUTE_RESEARCH,
    )


# ── citation (deterministic; §I/§VIII) ───────────────────────────────────────

_CANNABINOID_CUE = re.compile(
    r"\b(cbd|thc|thca|cbda|cbg|cbn|cbc|thcv|cbdv|cannabidiol|"
    r"tetrahydrocannabinol|cannabinoid[s]?|nabiximols|sativex|epidiolex|"
    r"dronabinol|nabilone|marinol)\b", re.IGNORECASE)
_EFFICACY_CUE = re.compile(
    r"\b(treat\w*|reduc\w*|improv\w*|relie\w*|effective|efficac\w*|alleviat\w*|"
    r"manag\w*|cur\w*|prevent\w*|control\w*|ameliorat\w*|therapeutic)\b",
    re.IGNORECASE)
_DOSE_CUE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|g|ml|%)\b|\bmg/kg\b|\bdos\w*|\btitrat\w*",
    re.IGNORECASE)


def default_clinical_claim(text: str) -> bool:
    """Conservative deterministic cue: the chunk names a cannabinoid AND asserts
    an efficacy or dosing claim. A definition / mechanism chunk does not trigger
    (better to miss than over-flag — a borderline flag only routes to review)."""
    if not text:
        return False
    return bool(_CANNABINOID_CUE.search(text)) and bool(
        _EFFICACY_CUE.search(text) or _DOSE_CUE.search(text))


def detect_citation_issues(
    chunk: Chunk, *, verifier: Verifier, claim_detector: ClaimDetector,
) -> "list[ChunkIssue]":
    issues: list[ChunkIssue] = []
    seen: set[str] = set()
    for raw in chunk.citations:
        kind, ident = source_audit._classify(raw)
        low = ident.lower()
        if low in seen:
            continue
        seen.add(low)
        verdict, reason = verifier(ident)
        if verdict == "PASS" or verdict == "UNVERIFIED":
            continue                              # real, or upstream unreachable (not KB's fault)
        issues.append(ChunkIssue(
            dimension=CITATION, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
            h2_anchor=chunk.h2_anchor, verdict="false_citation",
            detail=f"chunk cites {ident} ({kind}) — {reason}",
            evidence=reason,
            recommended_action="replace with a verified primary source (or remove)",
            route=ROUTE_IMPROVE,
        ))
    # The uncited-clinical-claim hole: a graded clinical assertion with no citation.
    if not chunk.citations and claim_detector(chunk.text):
        issues.append(ChunkIssue(
            dimension=CITATION, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
            h2_anchor=chunk.h2_anchor, verdict="uncited_claim",
            detail="chunk makes a clinical claim with zero citations",
            evidence="cannabinoid + efficacy/dose cue present, but no PMID/DOI",
            recommended_action="add a primary-source citation (PMID/DOI) or hedge "
                               "the claim to its true, sourced grade",
            route=ROUTE_RESEARCH,
        ))
    return issues


# ── accuracy (hybrid; deterministic contradiction, ambiguous → model) ────────

def _lead_claim(text: str) -> str:
    """The chunk's assertion to test against its sources — the opening sentence(s)
    (the authoring standard requires each H2 to open with its key finding)."""
    t = (text or "").strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", t)
    lead = " ".join(parts[:2]).strip()
    return lead[:400]


def detect_accuracy_issues(
    chunk: Chunk, *, abstract_fn: AbstractFn, claim_text: Optional[str] = None,
) -> "list[ChunkIssue]":
    claim = (claim_text or _lead_claim(chunk.text)).strip()
    if not claim:
        return []
    from cannavec_science.claim_support import assess_support, Verdict
    issues: list[ChunkIssue] = []
    seen: set[str] = set()
    # The claim we test is the chunk's *lead*. A direct contradiction against any
    # cited source is a strong, position-independent signal — always surfaced. The
    # softer 'unverified' (a cited abstract that doesn't mention the lead's
    # entities) is only trustworthy when one PMID is cited: in a multi-citation
    # chunk a perfectly-correct citation supporting a *later* sentence would read
    # as 'unverified' against the lead. So suppress 'unverified' there to avoid
    # backlog noise — the chunk still goes to model review on any contradiction.
    pmids = [source_audit._classify(r)[1] for r in chunk.citations
             if source_audit._classify(r)[0] == "pmid"]
    allow_unverified = len(set(pmids)) <= 1
    for raw in chunk.citations:
        kind, ident = source_audit._classify(raw)
        if kind != "pmid" or ident in seen:
            continue
        seen.add(ident)
        abstract = abstract_fn(ident)
        if not abstract:
            continue                              # inconclusive — never a flag
        report = assess_support(claim, abstract)
        if report.verdict == Verdict.CONTRADICTION:
            issues.append(ChunkIssue(
                dimension=ACCURACY, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
                h2_anchor=chunk.h2_anchor, verdict="contradiction",
                detail=f"cited PMID {ident} contradicts the chunk's claim",
                evidence=report.note or "abstract asserts the opposite direction",
                recommended_action="the cited source contradicts the claim — rework "
                                   "the claim or the citation",
                route=ROUTE_IMPROVE,
            ))
        elif report.verdict == Verdict.UNVERIFIED and allow_unverified:
            miss = ", ".join(report.missing) if report.missing else "key entities"
            issues.append(ChunkIssue(
                dimension=ACCURACY, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
                h2_anchor=chunk.h2_anchor, verdict="unverified",
                detail=f"cited PMID {ident} may not support the chunk's claim",
                evidence=f"abstract does not mention: {miss}",
                recommended_action="confirm the cited source supports the claim "
                                   "(model/human review)",
                route=ROUTE_MODEL,                # genuinely ambiguous → escalate, never auto-judge
            ))
    return issues


# ── completeness (deterministic; thin + §VII grade honesty) ──────────────────

def detect_completeness_issues(
    chunk: Chunk, *, declared_grade: Optional[str] = None,
    study_counts: Optional[dict] = None,
) -> "list[ChunkIssue]":
    issues: list[ChunkIssue] = []
    n_tokens = len((chunk.text or "").split())
    if 0 < n_tokens < STUB_TOKEN_FLOOR:
        issues.append(ChunkIssue(
            dimension=COMPLETENESS, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
            h2_anchor=chunk.h2_anchor, verdict="thin_stub",
            detail=f"chunk is ~{n_tokens} tokens (< {STUB_TOKEN_FLOOR})",
            evidence="below the authoring standard's H2 section floor",
            recommended_action="expand to a self-contained section (Finding, "
                               "Content, Clinical Relevance, Sources)",
            route=ROUTE_RESEARCH,
        ))
    if declared_grade and study_counts:
        from cannavec_science.kb_audit.checks import check_grade
        f = check_grade(declared_grade, study_counts)
        if f is not None:
            issues.append(ChunkIssue(
                dimension=COMPLETENESS, chunk_key=chunk.chunk_key,
                doc_id=chunk.doc_id, h2_anchor=chunk.h2_anchor,
                verdict="grade_inflation", detail=f.issue, evidence=f.evidence,
                recommended_action=f.recommended_action + " (grade change is "
                                   "human-only — flag for review, do not auto-set)",
                route=ROUTE_QUICKFIX,
            ))
    return issues


# ── queue append (one flywheel; additive line) ───────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append_improve_queue(query, issues, *, now=None, store_dir=None) -> "str | None":
    path = source_audit.improve_queue_path(store_dir)
    entry = {
        "ts": now or _utcnow(),
        "query": query,
        "chunk_issues": [i.to_dict() for i in issues],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return str(path)
    except OSError:                               # read-only fs etc. — never break the audit
        return None


# ── orchestration ────────────────────────────────────────────────────────────

def _default_abstract(pmid: str) -> "str | None":
    """Best-effort PubMed abstract (reuses the kb-audit fetcher). Any network gap
    → None → accuracy is inconclusive (never a fabricated flag)."""
    try:
        from cannavec_science.kb_audit.run import _real_abstract
        return _real_abstract(pmid)
    except Exception:                             # noqa: BLE001 — accuracy is best-effort
        return None


def audit_chunks(
    query: str,
    chunks: Iterable,
    *,
    verifier: Optional[Verifier] = None,
    abstract_fn: Optional[AbstractFn] = None,
    claim_detector: Optional[ClaimDetector] = None,
    check_accuracy: bool = True,
    log: bool = True,
    now: Optional[str] = None,
    store_dir: "str | Path | None" = None,
) -> ChunkAudit:
    """Audit the chunks the live KB returned across all four dimensions and append
    any issues to the operator improve-queue (the flywheel).

    Every detector is injectable so the audit is fully offline-testable; the
    defaults reuse the engine (``source_audit._live_verifier`` for citation, the
    kb-audit PubMed fetcher for accuracy). A clean run logs nothing (mirrors
    ``source_audit``).
    """
    verify = verifier or source_audit._live_verifier
    get_abstract = abstract_fn or _default_abstract
    is_claim = claim_detector or default_clinical_claim

    parsed = [c if isinstance(c, Chunk) else Chunk.from_dict(c) for c in chunks]
    issues: list[ChunkIssue] = []
    weak_flags: list[bool] = []

    for ch in parsed:
        r = detect_retrieval_issue(query, ch)
        weak_flags.append(r is not None)
        if r is not None:
            issues.append(r)
        issues.extend(detect_citation_issues(ch, verifier=verify, claim_detector=is_claim))
        if check_accuracy:
            issues.extend(detect_accuracy_issues(ch, abstract_fn=get_abstract))
        issues.extend(detect_completeness_issues(ch))

    all_weak = bool(parsed) and all(weak_flags)
    thin = _thin_recall_issue(query, len(parsed), all_weak)
    if thin is not None:
        issues.append(thin)

    logged = _append_improve_queue(query, issues, now=now, store_dir=store_dir) \
        if (log and issues) else None
    return ChunkAudit(query=query, chunks_seen=len(parsed),
                      issues=tuple(issues), logged_path=logged)
