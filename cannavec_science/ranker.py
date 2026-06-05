"""Elite candidate ranker — cost-efficient, accuracy-preserving.

The ranker orders **already-discovered candidate papers** (live-discovery
rows or discovery-index entries) by relevance and study quality so the most
useful primary sources surface first. It is a *ranking* layer, not a
*sourcing* layer: it can only reorder candidates the caller already fetched;
it never invents an identifier and never assigns a GRADE level.

Design (first principles — cost-efficiency is architectural, never a quality
downgrade):

1. **Deterministic high-recall pre-rank** (this module, pure stdlib): an
   Okapi-BM25 relevance score over ``title + abstract + topic`` versus the
   query, modulated by a study-design prior, a gentle recency factor, and a
   hard retraction sink. This is the always-available default, the offline
   fallback, and the audit-visible accuracy *floor* a smarter backend can
   reorder but never undercut.
2. **Confidence short-circuit**: an optional LLM backend is consulted *only*
   when the deterministic top of the list is a genuine near-tie (where
   semantic judgement actually changes the answer). A decisive margin means
   the cheap ranker was already right — so skipping the model costs nothing.
3. **Provenance gate + retraction pin**: whatever a backend returns is
   intersected with the candidate set (an unknown identifier is dropped, not
   cited — Constitution §I/§IX) and retracted rows are pinned to the bottom
   regardless of any backend's opinion.

The LLM adapter lives in :mod:`cannavec_science.ranker_llm` so this core stays
import-safe and **stdlib-only** (Constitution §X). Backends are duck-typed via
the :class:`RankerBackend` protocol; the pure-stdlib :class:`DeterministicRanker`
is the default.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Mapping, Optional, Protocol, Sequence

__all__ = [
    "Candidate",
    "ScoreBreakdown",
    "RankPlan",
    "RankedCandidate",
    "RankResult",
    "RankerBackend",
    "DeterministicRanker",
    "score_candidates",
    "should_escalate",
    "has_design_inversion",
    "low_lexical_confidence",
    "provenance_gate",
    "rank_candidates",
    "candidates_from_discovery",
    "rank_discovery_result",
    "render_markdown",
    "render_json",
]


# Default "now" for the recency factor. Kept as a module constant (not
# datetime.now) so ranking is deterministic and offline-testable; callers
# pass ``now_year=`` to override.
_DEFAULT_YEAR = 2026

# BM25 baseline: every candidate carries a floor of 1.0 relevance so that
# when the query has no usable tokens (or matches nothing) the ranking still
# falls back to the quality signals instead of collapsing to all-zero.
_BASELINE = 1.0


# ── Tokenisation ──────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Deliberately small, generic stoplist — domain terms (cbd, thc, pain, …) are
# never stopped. Kept stdlib-simple; this is a ranking signal, not an NLP stack.
_STOP = frozenset(
    "a an and are as at be by for from has have in into is it its of on or "
    "that the their to was were will with we this these those study studies "
    "trial trials patient patients effect effects using use used versus vs "
    "between among also can may than then they them our".split()
)


def _tokens(text: str) -> list[str]:
    """Lowercase, split, drop stopwords, and fold trailing plural ``s``.

    The plural fold is intentionally crude (``seizures`` → ``seizure``,
    ``cannabinoids`` → ``cannabinoid``). It is applied identically to query
    and document tokens, so even linguistically-wrong folds stay *consistent*
    on both sides and only help recall.
    """
    out: list[str] = []
    for w in _TOKEN_RE.findall((text or "").lower()):
        if len(w) < 2 or w in _STOP:
            continue
        if len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return out


# ── Study-design prior ────────────────────────────────────────────────────
#
# Ordered most-authoritative first. These are *relevance priors* for ranking —
# NOT GRADE levels (Constitution §VII: this layer never assigns a grade). A
# systematic review of RCTs deserves to surface above a case report on the
# same topic; that is all this table encodes.

_DESIGN_TABLE: tuple[tuple[tuple[str, ...], float, str], ...] = (
    (("meta-analysis", "meta analysis", "metaanalysis", "meta-analyses"), 1.00, "meta-analysis"),
    (("systematic review",), 1.00, "systematic review"),
    (("randomized controlled", "randomised controlled", "randomized clinical",
      "randomised clinical", "rct"), 0.90, "RCT"),
    (("clinical trial",), 0.78, "clinical trial"),
    (("cohort", "observational", "case-control", "case control", "longitudinal",
      "prospective", "registry"), 0.75, "observational"),
    (("cross-sectional", "cross sectional", "survey"), 0.68, "cross-sectional"),
    (("preprint",), 0.60, "preprint"),
    (("case report", "case series", "case study"), 0.55, "case report"),
    (("narrative review", "review", "editorial", "comment", "letter",
      "commentary"), 0.55, "review/other"),
)
_DEFAULT_DESIGN_WEIGHT = 0.65

# Retraction factor mirrors the verifier / live-search semantics. Retracted →
# 0.0 (sunk and pinned last); EOC / under-correction heavily penalised; a plain
# correction barely matters.
_RETRACTION_FACTOR: dict[str, float] = {
    "clean": 1.0,
    "corrected": 0.95,
    "correction": 0.95,
    "expression_of_concern": 0.50,
    "under_correction": 0.40,
    "retracted": 0.0,
}


# ── Candidate ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Candidate:
    """One rankable discovery candidate.

    ``identifier`` is the provenance key (PMID / DOI / NCT / …) — the thing the
    reader can verify and the thing the provenance gate checks. A candidate
    with no identifier is not citable (§I) and is dropped by the pipeline.
    """

    identifier: str
    title: str = ""
    abstract: str = ""
    year: Optional[int] = None
    study_types: tuple[str, ...] = ()
    retraction_status: str = "clean"
    topic: str = ""
    source: str = ""          # provenance lane, e.g. "live_pubmed"
    curated: bool = False
    url: str = ""

    # Identifier resolution order mirrors answer.live_finding_from_row so the
    # ranker and the discover surface agree on a row's headline identifier.
    _ID_KEYS = (
        "pmid", "nct_id", "activity_id", "cid", "pdb_id", "accession_id",
        "ensembl_id", "monomer_id", "chembl_id", "chebi_id", "go_id",
        "pathway_id", "efo_id", "doi", "identifier", "native_id",
    )

    @classmethod
    def from_row(cls, source: str, row) -> "Candidate":
        """Adapt a discovery row (a lane's ``.to_dict()`` or a plain dict)."""
        if not isinstance(row, dict):
            row = row.to_dict() if hasattr(row, "to_dict") else dict(
                getattr(row, "__dict__", {})
            )
        ident = ""
        for k in cls._ID_KEYS:
            v = row.get(k)
            if v:
                ident = str(v).strip()
                break

        study = row.get("pubtypes") or row.get("study_types") or ()
        if isinstance(study, str):
            study = (study,)
        study = tuple(str(s) for s in study)
        design = row.get("study_design")
        if design:
            study = study + (str(design),)

        yr = row.get("year") or row.get("start_year")
        try:
            yr = int(yr) if yr not in (None, "") else None
        except (TypeError, ValueError):
            yr = None

        return cls(
            identifier=ident,
            title=str(row.get("title") or row.get("brief_title") or ""),
            abstract=str(row.get("abstract") or row.get("summary") or ""),
            year=yr,
            study_types=study,
            retraction_status=str(row.get("retraction_status") or "clean"),
            topic=str(row.get("topic") or row.get("_condition") or ""),
            source=str(row.get("provenance") or source or ""),
            curated=bool(row.get("curated", False)),
            url=str(row.get("url") or row.get("link") or ""),
        )

    @classmethod
    def from_source_ref(cls, ref) -> "Candidate":
        """Adapt a :class:`cannavec_science.source_index.SourceRef`."""
        return cls(
            identifier=str(ref.identifier),
            topic=str(getattr(ref, "topic", "") or ""),
            source="discovery_index",
            curated=bool(getattr(ref, "curated", False)),
            url=str(getattr(ref, "url", "") or ""),
        )


# ── Scoring ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScoreBreakdown:
    """Auditable per-candidate score components. ``final`` drives the order."""

    identifier: str
    bm25: float
    design_weight: float
    design_label: str
    recency_factor: float
    retraction_factor: float
    final: float

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "bm25": self.bm25,
            "design_weight": self.design_weight,
            "design_label": self.design_label,
            "recency_factor": self.recency_factor,
            "retraction_factor": self.retraction_factor,
            "final": self.final,
        }


def _bm25_scores(
    query_tokens: list[str],
    docs: list[list[str]],
    *,
    k1: float,
    b: float,
) -> list[float]:
    """Okapi BM25 over a small in-memory corpus (the candidate set itself)."""
    n = len(docs)
    if n == 0:
        return []
    qterms = set(query_tokens)
    if not qterms:
        return [0.0] * n

    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    avgdl = (sum(len(d) for d in docs) / n) or 1.0
    idf = {
        t: math.log(1.0 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
        for t in qterms
    }

    scores: list[float] = []
    for d in docs:
        if not d:
            scores.append(0.0)
            continue
        dl = len(d)
        tf: dict[str, int] = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in qterms:
            f = tf.get(t, 0)
            if f == 0:
                continue
            s += idf[t] * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * dl / avgdl))
        scores.append(s)
    return scores


def _design_weight(c: Candidate) -> tuple[float, str]:
    """Study-design prior. Pubtypes dominate; the title is a fallback only."""
    hay = " ".join(t.lower() for t in c.study_types).strip() or (c.title or "").lower()
    for needles, w, label in _DESIGN_TABLE:
        if any(nd in hay for nd in needles):
            return w, label
    return _DEFAULT_DESIGN_WEIGHT, "unclassified"


def _recency_factor(year: Optional[int], now_year: int) -> float:
    """Gentle, bounded recency preference in roughly [0.85, 1.05].

    Newer is mildly preferred but can never overpower study quality: a recent
    case report must not outrank an older systematic review on relevance ties.
    """
    if not year:
        return 1.0
    age = max(0, now_year - int(year))
    return round(0.85 + 0.20 / (1.0 + age / 8.0), 6)


def score_candidates(
    query: str,
    candidates: Sequence[Candidate],
    *,
    k1: float = 1.5,
    b: float = 0.75,
    now_year: Optional[int] = None,
) -> dict[str, ScoreBreakdown]:
    """Deterministic score for each candidate, keyed by identifier."""
    now = int(now_year or _DEFAULT_YEAR)
    cands = list(candidates)
    docs = [_tokens(f"{c.title} {c.abstract} {c.topic}") for c in cands]
    rel = _bm25_scores(_tokens(query), docs, k1=k1, b=b)

    out: dict[str, ScoreBreakdown] = {}
    for c, r in zip(cands, rel):
        dw, dl = _design_weight(c)
        rf = _recency_factor(c.year, now)
        xf = _RETRACTION_FACTOR.get(c.retraction_status, 1.0)
        final = (_BASELINE + r) * dw * rf * xf
        out[c.identifier] = ScoreBreakdown(
            identifier=c.identifier,
            bm25=round(r, 4),
            design_weight=dw,
            design_label=dl,
            recency_factor=rf,
            retraction_factor=xf,
            final=round(final, 6),
        )
    return out


def _deterministic_rationale(sb: ScoreBreakdown) -> str:
    bits = [f"BM25 {sb.bm25:.2f}", f"{sb.design_label} ({sb.design_weight:.2f})",
            f"recency {sb.recency_factor:.2f}"]
    if sb.retraction_factor < 1.0:
        bits.append(f"retraction×{sb.retraction_factor:.2f}")
    return " · ".join(bits)


def _deterministic_order(
    candidates: Sequence[Candidate],
    scores: Mapping[str, ScoreBreakdown],
) -> list[str]:
    """Identifiers sorted best-first. Tie-break by identifier for stability."""
    return sorted(
        (c.identifier for c in candidates),
        key=lambda i: (-scores[i].final, i),
    )


# ── Backend protocol ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RankPlan:
    """A backend's proposed ordering of a shortlist, as identifiers.

    ``order`` is a (possibly partial) permutation of the shortlist's
    identifiers, best first. ``rationales`` maps identifier → terse reason.
    The pipeline provenance-gates ``order`` before trusting it.
    """

    order: tuple[str, ...]
    rationales: Mapping[str, str] = field(default_factory=dict)
    backend: str = "deterministic"


class RankerBackend(Protocol):
    """Duck-typed reranking backend. ``name`` distinguishes deterministic from
    LLM-backed so the pipeline knows whether the confidence short-circuit
    applies."""

    name: str

    def plan(self, query: str, candidates: Sequence[Candidate]) -> RankPlan:
        ...


class DeterministicRanker:
    """Pure-stdlib backend — the default and the always-available fallback."""

    name = "deterministic"

    def __init__(
        self,
        *,
        k1: float = 1.5,
        b: float = 0.75,
        now_year: Optional[int] = None,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.now_year = now_year

    def plan(self, query: str, candidates: Sequence[Candidate]) -> RankPlan:
        cands = _dedupe(candidates)
        scores = score_candidates(
            query, cands, k1=self.k1, b=self.b, now_year=self.now_year
        )
        order = tuple(_deterministic_order(cands, scores))
        rats = {i: _deterministic_rationale(scores[i]) for i in order}
        return RankPlan(order=order, rationales=rats, backend="deterministic")


# ── Pipeline helpers ──────────────────────────────────────────────────────


def _dedupe(candidates: Sequence[Candidate]) -> list[Candidate]:
    """First candidate per identifier wins. Idless candidates are dropped
    (nothing citable — Constitution §I)."""
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        if not c.identifier or c.identifier in seen:
            continue
        seen.add(c.identifier)
        out.append(c)
    return out


def should_escalate(
    scored_desc: Sequence[tuple[str, float]],
    *,
    margin: float = 0.15,
    min_candidates: int = 3,
) -> bool:
    """True when the deterministic top is a near-tie worth an LLM opinion.

    ``scored_desc`` is ``(identifier, final_score)`` sorted best-first. A
    decisive lead (relative margin ≥ ``margin``) means the cheap ranker is
    already confident — escalating would spend tokens without changing the
    answer, so we don't. This is the core cost lever, and it never costs
    accuracy: we only skip the model where it had nothing to add.
    """
    if len(scored_desc) < min_candidates:
        return False
    top = scored_desc[0][1]
    second = scored_desc[1][1]
    if top <= 0:
        return False
    return (top - second) / top < margin


def has_design_inversion(
    ordered: Sequence[ScoreBreakdown],
    *,
    min_design_gap: float = 0.2,
    relevance_floor_frac: float = 0.25,
    min_candidates: int = 3,
) -> bool:
    """True when a materially stronger-design candidate is ranked *below* a
    weaker-design one while still being a genuine relevance contender.

    This is the second escalation trigger (for an expert audience): BM25
    keyword density can float a keyword-dense narrative review above a pivotal
    RCT or meta-analysis. When that happens to a paper that is still on-topic —
    not an off-topic record correctly buried for irrelevance — the ordering is
    a judgement call worth an expert (LLM) opinion.

    ``ordered`` is the deterministic best-first list of (non-retracted)
    :class:`ScoreBreakdown`. An inversion is flagged when some higher-ranked
    row ``hi`` and lower-ranked row ``lo`` satisfy both:

    - ``lo.design_weight - hi.design_weight >= min_design_gap`` — ``lo`` has a
      materially stronger study design but sits lower (e.g. RCT/SR/MA below a
      narrative review; a gap of 0.2 ignores fine distinctions like RCT vs
      cohort and fires only on real tier jumps), and
    - ``lo.bm25 >= relevance_floor_frac * max_bm25`` — ``lo`` is relevant
      enough to be a real contender, so a genuinely off-topic strong-design
      record near the bottom does *not* trigger escalation.
    """
    rows = list(ordered)
    if len(rows) < min_candidates:
        return False
    max_bm25 = max((r.bm25 for r in rows), default=0.0)
    floor = relevance_floor_frac * max_bm25
    for a in range(len(rows)):
        hi = rows[a]
        for b in range(a + 1, len(rows)):
            lo = rows[b]
            if (lo.design_weight - hi.design_weight) >= min_design_gap and \
                    lo.bm25 >= floor:
                return True
    return False


def low_lexical_confidence(
    query: str,
    candidates: Sequence[Candidate],
    *,
    min_query_coverage: float = 0.5,
    min_candidates: int = 3,
) -> bool:
    """True when no candidate lexically covers enough of the query.

    BM25 is a lexical signal, so it misses synonymy and phrasing differences —
    a ``cbd`` query never matches a ``cannabidiol`` title, a ``seizure`` query
    misses ``convulsion``. When even the best-covering candidate shares fewer
    than ``min_query_coverage`` of the distinct query terms, the deterministic
    relevance order is unreliable and the LLM's *semantic* judgement is the
    more effective ranker — exactly where spending a call is worth it.

    Only candidates that actually carry text (title/abstract) are considered:
    if the shortlist is content-free there is nothing for the LLM to read
    semantically either, so escalating would be wasteful and we do not.
    """
    cands = [c for c in candidates if (c.title or c.abstract)]
    if len(cands) < min_candidates:
        return False
    q = set(_tokens(query))
    if not q:
        return False
    best = 0.0
    for c in cands:
        doc = set(_tokens(f"{c.title} {c.abstract} {c.topic}"))
        if not doc:
            continue
        cov = len(q & doc) / len(q)
        if cov > best:
            best = cov
            if best >= min_query_coverage:
                return False  # a confident lexical match exists
    return best < min_query_coverage


def provenance_gate(
    proposed: Sequence[str],
    allowed: set[str],
) -> list[str]:
    """Keep only identifiers that are actually in the candidate set, in the
    proposed order, de-duplicated.

    This is the structural guarantee that a backend (an LLM in particular)
    can never introduce a citation the caller did not fetch (Constitution
    §I primary-source-or-refuse, §IX no-silent-promotion).
    """
    seen: set[str] = set()
    out: list[str] = []
    for i in proposed:
        if i in allowed and i not in seen:
            out.append(i)
            seen.add(i)
    return out


# ── Result types ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RankedCandidate:
    rank: int
    candidate: Candidate
    score: float                 # deterministic final score — the visible floor
    rationale: str
    signals: dict
    reordered_by_llm: bool = False

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "identifier": self.candidate.identifier,
            "title": self.candidate.title,
            "year": self.candidate.year,
            "source": self.candidate.source,
            "retraction_status": self.candidate.retraction_status,
            "score": self.score,
            "rationale": self.rationale,
            "signals": dict(self.signals),
            "reordered_by_llm": self.reordered_by_llm,
        }


@dataclass(frozen=True)
class RankResult:
    ranked: tuple[RankedCandidate, ...]
    backend_used: str
    escalated: bool
    shortlist_size: int
    notes: tuple[str, ...] = ()
    escalation_reason: Optional[str] = None  # why the LLM lift fired (or None)

    def to_dict(self) -> dict:
        return {
            "backend_used": self.backend_used,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "shortlist_size": self.shortlist_size,
            "notes": list(self.notes),
            "ranked": [r.to_dict() for r in self.ranked],
        }


# ── Pipeline ──────────────────────────────────────────────────────────────


def rank_candidates(
    query: str,
    candidates: Sequence[Candidate],
    *,
    backend: Optional[RankerBackend] = None,
    top_k: int = 10,
    escalate: Optional[bool] = None,
    margin: float = 0.15,
    min_design_gap: float = 0.2,
    relevance_floor_frac: float = 0.25,
    min_query_coverage: float = 0.5,
    now_year: Optional[int] = None,
    k1: float = 1.5,
    b: float = 0.75,
) -> RankResult:
    """Rank ``candidates`` for ``query`` — deterministic floor, optional LLM lift.

    The deterministic score is always computed (it is the floor, the tail
    order, and the fallback). An LLM ``backend`` — if supplied — is consulted
    only when the deterministic order is genuinely uncertain, via three
    triggers: a top-of-list near-tie (:func:`should_escalate`); a design
    inversion, where a still-relevant stronger-design paper is ranked below a
    weaker-design one (:func:`has_design_inversion`); or a weak lexical signal,
    where no candidate covers enough of the query so BM25 is unreliable and the
    LLM's semantic read is more effective (:func:`low_lexical_confidence`).
    ``escalate=None`` auto-decides via those triggers; pass ``True``/``False``
    to force. Whatever the backend
    returns is provenance-gated against the shortlist and retracted rows are
    pinned last, so accuracy never depends on the model behaving.
    """
    cands = _dedupe(candidates)
    if backend is None:
        backend = DeterministicRanker(k1=k1, b=b, now_year=now_year)

    if not cands:
        return RankResult((), "deterministic", False, 0, ())

    scores = score_candidates(query, cands, k1=k1, b=b, now_year=now_year)
    by_id = {c.identifier: c for c in cands}
    det_order = _deterministic_order(cands, scores)

    shortlist_ids = det_order[: max(1, top_k)]
    shortlist = [by_id[i] for i in shortlist_ids]
    shortlist_set = set(shortlist_ids)

    # Escalation triggers are scoped to the shortlist — the only rows an LLM
    # backend actually reorders — which also bounds the inversion scan to
    # O(top_k²). Both lists are already best-first (shortlist ⊆ det_order).
    shortlist_nonret = [
        scores[i] for i in shortlist_ids
        if by_id[i].retraction_status != "retracted"
    ]
    nonret_scored = [(bd.identifier, bd.final) for bd in shortlist_nonret]
    shortlist_nonret_cands = [by_id[bd.identifier] for bd in shortlist_nonret]
    llm_backed = getattr(backend, "name", "deterministic") != "deterministic"

    reason: Optional[str] = None
    if escalate is None:
        if llm_backed:
            if should_escalate(nonret_scored, margin=margin):
                reason = "top near-tie"
            elif has_design_inversion(
                shortlist_nonret,
                min_design_gap=min_design_gap,
                relevance_floor_frac=relevance_floor_frac,
            ):
                reason = "design inversion"
            elif low_lexical_confidence(
                query,
                shortlist_nonret_cands,
                min_query_coverage=min_query_coverage,
            ):
                reason = "weak lexical signal"
        do_escalate = reason is not None
    else:
        do_escalate = bool(escalate) and llm_backed
        if do_escalate:
            reason = "forced"

    notes: list[str] = []
    final_short: list[str]
    rationales: dict[str, str] = {}
    reordered: set[str] = set()
    backend_used = "deterministic"

    if do_escalate:
        plan: Optional[RankPlan] = None
        try:
            plan = backend.plan(query, shortlist)
        except Exception as exc:  # noqa: BLE001 — degrade to the floor, never abort
            notes.append(
                f"backend {backend.name!r} failed ({exc}); used deterministic order"
            )
        gated = provenance_gate(plan.order, shortlist_set) if plan else []
        if gated:
            tail = [i for i in shortlist_ids if i not in set(gated)]
            final_short = gated + tail
            rationales = dict(plan.rationales) if plan else {}
            reordered = set(gated)
            backend_used = backend.name
        else:
            if plan is not None:
                notes.append(
                    f"backend {backend.name!r} returned no usable order; "
                    f"used deterministic order"
                )
            final_short = list(shortlist_ids)
            do_escalate = False
    else:
        final_short = list(shortlist_ids)

    # Full order = reranked shortlist + deterministic tail beyond the shortlist.
    rest = [i for i in det_order if i not in set(final_short)]
    full = final_short + rest

    # Hard retraction pin: retracted rows go to the absolute bottom no matter
    # what any backend proposed (an accuracy guard the model cannot override).
    clean = [i for i in full if by_id[i].retraction_status != "retracted"]
    retr = [i for i in full if by_id[i].retraction_status == "retracted"]
    full = clean + retr

    ranked: list[RankedCandidate] = []
    for rank, i in enumerate(full, start=1):
        sb = scores[i]
        ranked.append(
            RankedCandidate(
                rank=rank,
                candidate=by_id[i],
                score=sb.final,
                rationale=rationales.get(i) or _deterministic_rationale(sb),
                signals={
                    "bm25": sb.bm25,
                    "design_weight": sb.design_weight,
                    "design_label": sb.design_label,
                    "recency_factor": sb.recency_factor,
                    "retraction_factor": sb.retraction_factor,
                },
                reordered_by_llm=i in reordered,
            )
        )

    escalated = backend_used != "deterministic"
    return RankResult(
        ranked=tuple(ranked),
        backend_used=backend_used,
        escalated=escalated,
        shortlist_size=len(shortlist_ids),
        notes=tuple(notes),
        escalation_reason=reason if escalated else None,
    )


# ── Discovery-result adapters ─────────────────────────────────────────────


def candidates_from_discovery(result: Mapping) -> tuple[Candidate, ...]:
    """Adapt a :func:`cannavec_science.live.run_discovery` result dict into
    candidates. Unreachable lanes (``{"error": ...}``) and idless rows are
    skipped."""
    out: list[Candidate] = []
    for src, rows in (result.get("sources") or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            c = Candidate.from_row(src, row)
            if c.identifier:
                out.append(c)
    return tuple(out)


def rank_discovery_result(
    query: str,
    result: Mapping,
    **kwargs,
) -> RankResult:
    """Convenience: rank the candidates inside a ``run_discovery`` result."""
    return rank_candidates(query, candidates_from_discovery(result), **kwargs)


# ── Renderers ─────────────────────────────────────────────────────────────


def render_markdown(result: RankResult) -> str:
    lines = [
        "## Ranked candidates",
        "",
        f"_Backend: {result.backend_used}"
        f"{f' (LLM rerank — {result.escalation_reason})' if result.escalated else ' (deterministic floor)'} · "
        f"shortlist {result.shortlist_size}. Ranking only — these are "
        f"discovery candidates, not curated facts; verify each identifier and "
        f"let the deterministic verify + GRADE gate assign any grade._",
        "",
    ]
    if not result.ranked:
        lines.append("_No candidates to rank._")
        return "\n".join(lines) + "\n"
    lines.append("| # | Identifier | Year | Title | Why | Source |")
    lines.append("|---|---|---|---|---|---|")
    for r in result.ranked:
        c = r.candidate
        flag = "" if c.retraction_status == "clean" else f" ⚠ {c.retraction_status}"
        title = (c.title or "—").replace("|", "/")
        if len(title) > 70:
            title = title[:67] + "..."
        marker = " ★" if r.reordered_by_llm else ""
        lines.append(
            f"| {r.rank}{marker} | {c.identifier}{flag} | {c.year or '—'} "
            f"| {title} | {r.rationale} | {c.source or '—'} |"
        )
    for n in result.notes:
        lines.append("")
        lines.append(f"_Note: {n}_")
    return "\n".join(lines) + "\n"


def render_json(result: RankResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)
