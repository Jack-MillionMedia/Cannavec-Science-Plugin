"""Rigorous chunk evaluation — decide, for one KB chunk, whether it is **correct,
incomplete, outdated, weakly-cited, misleading, or needs-improvement**, by composing
every deterministic detector the engine has AND comparing the chunk's claim against
the broader credible literature.

Where ``chunk_audit`` runs four shallow per-chunk detectors, this layer adds the depth
the KB-improvement mission needs:

- **prose rigor** — runs the full §VI/§VII detector stack (``rigor_checks`` ×8 +
  ``reporting_rigor`` ×6 + ``banned_patterns`` + GRADE-vs-wording) over the chunk text.
  Nothing aggregated these over a chunk before; together they are the deterministic
  spine of the *misleading* / *weakly-cited* verdicts.
- **claim vs corpus** — runs live discovery for the chunk's topic, tiers each credible
  source through the GRADE engine (spec 036), and checks the chunk's claim against the
  weight of that literature: missing high-tier evidence (*incomplete*), newer evidence
  that supersedes the chunk's citations (*outdated*), a strong claim cited only by weak
  evidence (*weakly-cited*), and — at a deliberately high bar — a claim the credible
  corpus *contradicts* (*misleading*). This is "compare against as much credible
  research as possible," kept deterministic and §IX-safe (it evaluates, never authors).
- **freshness** — the repo's own Truth-Layer staleness rule
  (``today − last_verified_at > decay_horizon_days``) → *outdated*.
- **coherence** — does a chunk contradict a sibling chunk in the same batch?

Every verdict is computed by code (§II). The only model seam is
``claim_support.review_claim(backend=…)`` — identifier-free, grade-free, quote-gated,
and a deterministic CONTRADICTION always escalates to human. ``backend=None`` (default)
is the deterministic floor; ``corpus_fn=None`` (default) keeps the whole evaluator
offline. **A false ``misleading`` on a correct chunk is the worst error**, so corpus
contradiction requires a strong majority *and* a minimum sample, else it softens.

This layer **flags and routes** — it never authors clinical text and never sets/upgrades
a grade (M5; the KB repo's Agent Boundary Rule).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Iterable, Optional

from cannavec_science import chunk_audit
from cannavec_science.chunk_audit import Chunk, ChunkIssue

__all__ = [
    "ChunkVerdict", "Corroboration", "CorpusSource", "evaluate_chunk",
    "evaluate_chunks", "live_corpus", "content_hash",
    "CORRECT", "INCOMPLETE", "OUTDATED", "WEAKLY_CITED", "MISLEADING",
    "NEEDS_IMPROVEMENT", "UNEVALUATED",
]

# Status taxonomy, ordered most-severe → least so the rollup is unambiguous.
MISLEADING = "misleading"
OUTDATED = "outdated"
WEAKLY_CITED = "weakly_cited"
INCOMPLETE = "incomplete"
NEEDS_IMPROVEMENT = "needs_improvement"
CORRECT = "correct"
UNEVALUATED = "unevaluated"

_SEVERITY = [MISLEADING, OUTDATED, WEAKLY_CITED, INCOMPLETE, NEEDS_IMPROVEMENT,
             CORRECT, UNEVALUATED]

# verdict (the ChunkIssue.verdict string) → the status it contributes to the rollup.
_STATUS_BY_VERDICT = {
    # misleading
    "contradiction": MISLEADING, "corpus_contradiction": MISLEADING,
    "rigor_violation": MISLEADING, "reporting_gap": MISLEADING,
    "banned_misleading": MISLEADING, "wording_overclaim": MISLEADING,
    # outdated
    "retracted_citation": OUTDATED, "stale": OUTDATED, "superseded": OUTDATED,
    # weakly_cited
    "fabricated_citation": WEAKLY_CITED, "misattributed_citation": WEAKLY_CITED,
    "uncited_claim": WEAKLY_CITED, "grade_inflation": WEAKLY_CITED,
    "cherry_picked": WEAKLY_CITED, "under_cited": WEAKLY_CITED,
    # incomplete
    "thin_stub": INCOMPLETE, "thin_recall": INCOMPLETE, "weak_relevance": INCOMPLETE,
    "missing_evidence": INCOMPLETE,
    # needs_improvement
    "unverified": NEEDS_IMPROVEMENT, "coherence_conflict": NEEDS_IMPROVEMENT,
}

# Corpus contradiction bar — high, because a false `misleading` is the worst error.
MIN_CORPUS_CONTRA = 3        # need ≥ this many credible sources checked
CONTRA_FRACTION = 0.6        # ≥ 60% of them must contradict
MAX_CORPUS_CHECK = 6         # bound the abstract fetches per chunk
# Freshness fallback when a chunk carries freshness_class but no decay_horizon_days.
_FRESHNESS_HORIZON = {"mechanism_stable": 1825, "clinical_evolving": 365,
                      "legal_volatile": 30}


# ── data model ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CorpusSource:
    """One credible primary source discovered for a chunk's topic, tiered through
    the GRADE engine (live grade is clamped: ≤ Level C journal / ≤ D preprint)."""
    identifier: str
    year: Optional[int]
    tier: int                # SourceTier int (1 strongest … 8)
    level_rank: int          # EvidenceLevel.rank (5=A … 0=Unsupported)
    has_abstract: bool


@dataclass(frozen=True)
class Corroboration:
    supported: int
    contradicted: int
    checked: int

    @property
    def score(self) -> Optional[float]:
        denom = self.supported + self.contradicted
        return round(self.supported / denom, 3) if denom else None

    def to_dict(self) -> dict:
        return {"supported": self.supported, "contradicted": self.contradicted,
                "checked": self.checked, "score": self.score}


@dataclass(frozen=True)
class ChunkVerdict:
    chunk_key: str
    doc_id: str
    h2_anchor: str
    status: str
    confidence: str               # high | medium | low
    issues: tuple                 # ChunkIssue[]
    corroboration: Optional[Corroboration]
    evidence_checked: bool
    content_hash: str

    def statuses_present(self) -> tuple:
        seen = {_STATUS_BY_VERDICT.get(i.verdict, NEEDS_IMPROVEMENT) for i in self.issues}
        return tuple(s for s in _SEVERITY if s in seen)

    def to_dict(self) -> dict:
        return {
            "chunk_key": self.chunk_key, "doc_id": self.doc_id,
            "h2_anchor": self.h2_anchor, "status": self.status,
            "confidence": self.confidence,
            "issues": [i.to_dict() for i in self.issues],
            "corroboration": self.corroboration.to_dict() if self.corroboration else None,
            "evidence_checked": self.evidence_checked,
            "content_hash": self.content_hash,
        }


def content_hash(text: str) -> str:
    """Stable hash of the chunk body so the ledger can tell a fix (content changed)
    from an unchanged-but-still-broken chunk."""
    norm = " ".join((text or "").split()).lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _issue(verdict, status_dim, chunk, detail, evidence, action, route) -> ChunkIssue:
    return ChunkIssue(
        dimension=status_dim, chunk_key=chunk.chunk_key, doc_id=chunk.doc_id,
        h2_anchor=chunk.h2_anchor, verdict=verdict, detail=detail,
        evidence=evidence, recommended_action=action, route=route)


# ── prose rigor aggregator (deterministic; the misleading/weakly-cited spine) ─

def detect_prose_rigor_issues(chunk: Chunk) -> "list[ChunkIssue]":
    """Run the full rigor stack over the chunk's prose. Composes detectors that
    already exist but were never aggregated per chunk."""
    text = chunk.text or ""
    if not text.strip():
        return []
    issues: list[ChunkIssue] = []

    from cannavec_science.rigor_checks import run_rigor_checks
    rep = run_rigor_checks(text)
    if not rep.clean:
        groups = [
            ("isomer", rep.isomer_violations), ("isomer_equivalence", rep.isomer_equivalence_violations),
            ("receptor_id", rep.receptor_violations), ("dose_route", rep.dose_route_violations),
            ("thca_thc", rep.thca_thc_violations), ("matrix_unit", rep.matrix_unit_violations),
            ("decarb", rep.decarb_context_violations), ("entourage", rep.entourage_violations),
        ]
        for name, viols in groups:
            for v in viols:
                issues.append(_issue(
                    "rigor_violation", "accuracy", chunk,
                    f"phytochemistry/pharmacology rigor: {name}", v.why,
                    "correct the scientific imprecision flagged by rigor_checks",
                    chunk_audit.ROUTE_IMPROVE))
        for v in rep.reporting_rigor_violations:
            issues.append(_issue(
                "reporting_gap", "accuracy", chunk,
                f"reporting standard not acknowledged: {getattr(v.kind, 'value', v.kind)}",
                v.why, "add the missing reporting-guideline framing (CONSORT/PRISMA/…)",
                chunk_audit.ROUTE_RESEARCH))

    from cannavec_science.banned_patterns import detect_banned_patterns
    _WEAK = {"cherry_picked"}
    for hit in detect_banned_patterns(text):
        pid = hit.pattern.id
        is_weak = pid in _WEAK
        issues.append(_issue(
            "cherry_picked" if is_weak else "banned_misleading",
            "citation" if is_weak else "accuracy", chunk,
            f"unscientific pattern: {hit.pattern.title}", hit.pattern.why,
            f"rephrase per the banned-pattern guidance: {hit.pattern.replacement}",
            chunk_audit.ROUTE_IMPROVE))

    from cannavec_science.uncertainty import grade_wording_consistency, detect_declared_level
    declared = detect_declared_level(text)
    if declared is not None:
        for w in grade_wording_consistency(text, declared):
            issues.append(_issue(
                "wording_overclaim", "accuracy", chunk,
                "wording overstates the declared evidence grade", w.why,
                "soften the wording to the grade's acceptable vocabulary, or raise the "
                "grade only with sufficient evidence (grade change is human-only)",
                chunk_audit.ROUTE_IMPROVE))
    return issues


# ── citation (finer than chunk_audit: retracted vs fabricated vs misattributed) ─

def detect_citation_issues_fine(chunk: Chunk, *, verifier=None, retraction_fn=None
                                ) -> "list[ChunkIssue]":
    from cannavec_science.kb_audit.checks import check_citation
    from cannavec_science.kb_audit.model import Citation
    from cannavec_science import source_audit

    if verifier is None or retraction_fn is None:
        from cannavec_science.kb_audit.run import _real_verify, _real_retracted
        verify_fn = verifier or _real_verify
        retracted_fn = retraction_fn or _real_retracted
    else:
        verify_fn, retracted_fn = verifier, retraction_fn

    issues: list[ChunkIssue] = []
    seen: set[str] = set()
    _MAP = {"retracted": ("retracted_citation", chunk_audit.ROUTE_IMPROVE),
            "fabricated": ("fabricated_citation", chunk_audit.ROUTE_IMPROVE),
            "misattributed": ("misattributed_citation", chunk_audit.ROUTE_IMPROVE)}
    for raw in chunk.citations:
        kind, ident = source_audit._classify(raw)
        low = ident.lower()
        if low in seen:
            continue
        seen.add(low)
        id_type = {"pmid": "PMID", "doi": "DOI"}.get(kind, "OTHER")
        if id_type == "OTHER":
            continue
        f = check_citation(Citation(ident, id_type, ""),
                           verify_fn=verify_fn, retracted_fn=retracted_fn)
        if f is None or f.verdict == "inconclusive":
            continue
        verdict, route = _MAP.get(f.verdict, ("fabricated_citation", chunk_audit.ROUTE_IMPROVE))
        issues.append(_issue(verdict, "citation", chunk, f.issue, f.evidence,
                             f.recommended_action, route))
    # uncited clinical claim (reuse the conservative cue).
    if not chunk.citations and chunk_audit.default_clinical_claim(chunk.text):
        issues.append(_issue(
            "uncited_claim", "citation", chunk,
            "clinical claim with zero citations",
            "cannabinoid + efficacy/dose cue present, no PMID/DOI",
            "add a primary-source citation or hedge to the sourced grade",
            chunk_audit.ROUTE_RESEARCH))
    return issues


# ── claim vs corpus (the new rigor) ──────────────────────────────────────────

def live_corpus(topic: str, *, sources=("pubmed", "europepmc", "ctgov"),
                max_results: int = 8, runners=None) -> "list[CorpusSource]":
    """Default corpus assembler: live discovery → GRADE-tiered credible sources.
    Best-effort and §IX-safe (candidates, never auto-promoted). ``runners`` injects
    fakes for offline tests."""
    try:
        from cannavec_science import live
        from cannavec_science import answer
        payload = live.run_discovery(topic, sources=sources,
                                     max_results=max_results, runners=runners)
    except Exception:  # noqa: BLE001 — corpus is best-effort
        return []
    out: list[CorpusSource] = []
    seen: set[str] = set()
    src_map = payload.get("sources", {}) if isinstance(payload, dict) else {}
    for src_key, rows in src_map.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            source = answer.live_source_from_row(src_key, row)
            graded = answer._live_grade_for_row(src_key, row)
            if source is None or graded is None:
                continue
            ident = source.pmid or source.doi or source.url or ""
            if not ident or ident.lower() in seen:
                continue
            seen.add(ident.lower())
            out.append(CorpusSource(
                identifier=ident, year=source.year, tier=int(source.tier),
                level_rank=graded[0].rank, has_abstract=bool(row.get("abstract"))))
    return out


def _norm_ids(citations) -> set:
    from cannavec_science import source_audit
    return {source_audit._classify(c)[1].lower() for c in citations if str(c).strip()}


def detect_corpus_issues(
    chunk: Chunk, topic: str, *, corpus_fn, abstract_fn=None, backend=None,
) -> "tuple[list[ChunkIssue], Optional[Corroboration]]":
    """Compare the chunk's claim against the live credible corpus. Returns
    (issues, corroboration). All network is via the injected corpus_fn/abstract_fn,
    and a raising fetcher degrades to empty (the corpus is best-effort, §IX)."""
    try:
        corpus = list(corpus_fn(topic) or [])
    except Exception:  # noqa: BLE001 — corpus is best-effort; never abort the batch
        return [], None
    if not corpus:
        return [], None
    issues: list[ChunkIssue] = []
    cited = _norm_ids(chunk.citations)
    high_tier = [c for c in corpus if c.tier <= 2]          # SR_FLAGSHIP / JOURNAL_RCT
    cited_in_corpus = [c for c in corpus if c.identifier.lower() in cited]
    cites_high_tier = any(c.tier <= 2 for c in cited_in_corpus)

    # missing-evidence (incomplete): strong corpus sources the chunk omits — but only
    # when the chunk does NOT already cite a high-tier source (don't nag a well-cited
    # chunk, and don't churn when its own SR simply wasn't returned this run).
    uncited_high = [c for c in high_tier if c.identifier.lower() not in cited]
    if uncited_high and not cites_high_tier:
        ids = ", ".join(c.identifier for c in uncited_high[:5])
        issues.append(_issue(
            "missing_evidence", "completeness", chunk,
            f"{len(uncited_high)} high-tier source(s) on this topic not cited",
            f"credible sources the chunk omits: {ids}",
            "consider citing the strongest available evidence for this topic",
            chunk_audit.ROUTE_RESEARCH))

    # under-cited (weakly_cited): a strong clinical claim whose VISIBLE citations are
    # all weak-tier while the corpus has strong evidence. Requires the chunk's own
    # citations to be visible in the corpus — else we can't conclude they're weak
    # (no guessing: a cited SR not returned this run must not manufacture a flag).
    if (chunk_audit.default_clinical_claim(chunk.text) and high_tier
            and cited_in_corpus and not cites_high_tier):
        issues.append(_issue(
            "under_cited", "citation", chunk,
            "strong clinical claim cited only by weak-tier evidence",
            f"corpus has {len(high_tier)} high-tier source(s); the chunk's own citations "
            "are all weaker",
            "cite a systematic review or RCT for this clinical claim, or hedge it",
            chunk_audit.ROUTE_RESEARCH))

    # superseded (outdated): a high-tier source newer than everything the chunk cites.
    cited_years = [c.year for c in corpus if c.identifier.lower() in cited and c.year]
    if cited_years:
        newest_cited = max(cited_years)
        newer = [c for c in high_tier
                 if c.year and c.year > newest_cited and c.identifier.lower() not in cited]
        if newer:
            yr = max(c.year for c in newer)
            issues.append(_issue(
                "superseded", "completeness", chunk,
                f"newer high-tier evidence ({yr}) exists beyond the chunk's citations "
                f"(newest cited {newest_cited})",
                f"e.g. {newer[0].identifier} ({yr})",
                "review whether the newer evidence updates or supersedes this chunk",
                chunk_audit.ROUTE_RESEARCH))

    # claim agreement (misleading/correct): the high-bar corpus-contradiction check.
    corr = None
    if abstract_fn is not None:
        claim = _lead_claim(chunk.text)
        if claim:
            corr = _corpus_claim_agreement(claim, corpus, abstract_fn=abstract_fn,
                                           backend=backend)
            if corr and corr.checked >= MIN_CORPUS_CONTRA:
                if corr.contradicted >= max(MIN_CORPUS_CONTRA,
                                            -(-corr.checked * 6 // 10)):  # ceil(0.6·checked)
                    issues.append(_issue(
                        "corpus_contradiction", "accuracy", chunk,
                        f"{corr.contradicted}/{corr.checked} credible sources contradict "
                        "the chunk's claim",
                        "the weight of the credible literature opposes the claim direction",
                        "rework the claim — the broader evidence contradicts it "
                        "(model/human review)",
                        chunk_audit.ROUTE_MODEL))
    return issues, corr


def _lead_claim(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", t)
    return " ".join(parts[:2]).strip()[:400]


# The deterministic claimed_direction first-matches a direction verb and IGNORES
# negation: "CBD does NOT increase seizures" reads as 'increase'. A corpus that
# correctly says 'decrease' would then look like a contradiction of a *correct*
# chunk — the worst-error class. When the lead's direction cue is negated, the
# direction is unreliable, so we never count a CONTRADICTION from it.
_DIR_NEEDLE = re.compile(
    r"\b(inhibit|suppress|blockad|induc|upregulat|increas|elevat|augment|rais|"
    r"decreas|reduc|lower|diminish|attenuat)", re.IGNORECASE)
_NEG_NEAR = re.compile(
    r"\b(not|never|no|cannot|without|fails?\s+to|rather\s+than|instead\s+of|"
    r"does\s+not|did\s+not|do\s+not|doesn't|didn't|don't|isn't|aren't)\b", re.IGNORECASE)


def _direction_unreliable(claim: str) -> bool:
    """True if the claim's first direction cue is preceded (within ~30 chars) by a
    negation/contrast marker, making the deterministic direction untrustworthy."""
    m = _DIR_NEEDLE.search(claim or "")
    if not m:
        return False
    window = claim[max(0, m.start() - 30):m.start()]
    return bool(_NEG_NEAR.search(window))


def _corpus_claim_agreement(claim, corpus, *, abstract_fn, backend) -> Corroboration:
    from cannavec_science.claim_support import review_claim, Verdict
    supported = contradicted = checked = 0
    unreliable = _direction_unreliable(claim)
    # strongest first, only sources whose abstract we can read.
    ranked = sorted(corpus, key=lambda c: (c.tier, -(c.year or 0)))
    for c in ranked:
        if checked >= MAX_CORPUS_CHECK:
            break
        try:
            abstract = abstract_fn(c.identifier)
        except Exception:  # noqa: BLE001 — a flaky fetcher must not abort the tally
            abstract = ""
        if not abstract:
            continue
        review = review_claim(claim, abstract, backend=backend)
        checked += 1
        det = review.report.verdict
        if det == Verdict.CONTRADICTION:
            # A negated-direction lead makes CONTRADICTION untrustworthy → do not
            # count it (the source likely agrees with the claim's TRUE direction).
            if not unreliable:
                contradicted += 1
        elif det == Verdict.SUPPORTED:
            supported += 1
    return Corroboration(supported=supported, contradicted=contradicted, checked=checked)


# ── freshness (outdated via the repo Truth-Layer) ────────────────────────────

def _parse_date(s) -> Optional[date]:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def detect_freshness_issue(chunk: Chunk, *, meta: Optional[dict] = None,
                           now: Optional[date] = None) -> "list[ChunkIssue]":
    """Stale per the repo's own rule: today − last_verified_at > decay_horizon_days,
    or past next_grade_review_at, or decay_breach_count > 0. meta is the chunk's
    forwarded Truth-Layer frontmatter (or None → skip)."""
    if not meta:
        return []
    today = now or datetime.now(timezone.utc).date()
    last = _parse_date(meta.get("last_verified_at"))
    horizon = meta.get("decay_horizon_days")
    if horizon is None:
        horizon = _FRESHNESS_HORIZON.get(str(meta.get("freshness_class", "")))
    breach = meta.get("decay_breach_count")
    nxt = _parse_date(meta.get("next_grade_review_at"))

    stale = False
    why = ""
    if last and horizon:
        try:
            if (today - last).days > int(horizon):
                stale, why = True, (f"last verified {last.isoformat()}, "
                                    f"horizon {horizon}d exceeded")
        except (TypeError, ValueError):
            pass
    if not stale and nxt and today > nxt:
        stale, why = True, f"past next_grade_review_at {nxt.isoformat()}"
    if not stale and isinstance(breach, int) and breach > 0:
        stale, why = True, f"decay_breach_count={breach}"
    if not stale:
        return []
    return [_issue(
        "stale", "completeness", chunk, "chunk is past its freshness horizon", why,
        "re-verify against current evidence; flag vectorStatus=needs-update (do not "
        "edit last_verified_at by hand)", chunk_audit.ROUTE_RESEARCH)]


# ── rollup ───────────────────────────────────────────────────────────────────

def _rollup_status(issues, *, evidence_checked, corr) -> "tuple[str, str]":
    present = {_STATUS_BY_VERDICT.get(i.verdict, NEEDS_IMPROVEMENT) for i in issues}
    for status in _SEVERITY:
        if status in present:
            # confidence: high for deterministic hard signals, medium for soft.
            conf = "high" if status in (MISLEADING, OUTDATED, WEAKLY_CITED) else "medium"
            if status == MISLEADING and any(i.verdict == "corpus_contradiction" for i in issues):
                conf = "high"
            return status, conf
    # CORRECT requires POSITIVE corroboration with NO contradicting source — a chunk
    # the corpus partly contradicts (even below the misleading bar) is not "correct".
    if evidence_checked and corr and corr.contradicted == 0 and corr.supported >= 2 \
            and corr.score is not None and corr.score >= 0.75:
        return CORRECT, "high" if corr.checked >= MIN_CORPUS_CONTRA else "medium"
    if evidence_checked and corr and corr.contradicted == 0 and corr.supported >= 1:
        return CORRECT, "low"
    return UNEVALUATED, "low"


def evaluate_chunk(
    chunk, topic: str, *,
    corpus_fn: Optional[Callable] = None,
    abstract_fn: Optional[Callable] = None,
    verifier: Optional[Callable] = None,
    retraction_fn: Optional[Callable] = None,
    backend=None,
    meta: Optional[dict] = None,
    check_cited_accuracy: bool = True,
    now: Optional[date] = None,
) -> ChunkVerdict:
    """Evaluate one chunk across every dimension and roll up to a single status.
    Fully offline when corpus_fn is None and verifier/abstract_fn are injected."""
    ch = chunk if isinstance(chunk, Chunk) else Chunk.from_dict(chunk)
    issues: list[ChunkIssue] = []

    # shallow per-chunk detectors (retrieval / completeness / cited-source accuracy)
    r = chunk_audit.detect_retrieval_issue(topic, ch)
    if r is not None:
        issues.append(r)
    issues.extend(chunk_audit.detect_completeness_issues(ch))
    if check_cited_accuracy and abstract_fn is not None:
        issues.extend(chunk_audit.detect_accuracy_issues(ch, abstract_fn=abstract_fn))

    # finer citation + prose rigor + freshness (all deterministic)
    issues.extend(detect_citation_issues_fine(ch, verifier=verifier,
                                              retraction_fn=retraction_fn))
    issues.extend(detect_prose_rigor_issues(ch))
    issues.extend(detect_freshness_issue(ch, meta=meta, now=now))

    # claim vs corpus — ONLY when the chunk is on-topic for the query the corpus was
    # built from. The corpus is assembled once from the batch query; a chunk that is
    # off-topic for that query (flagged weak_relevance above) is not what the corpus
    # is about, so comparing it would manufacture false contradictions — the cardinal
    # "false MISLEADING on a correct chunk" error. Off-topic chunks still get every
    # other check (prose rigor, citation, freshness) and the weak_relevance flag.
    corr = None
    evidence_checked = False
    chunk_on_topic = r is None
    if corpus_fn is not None and chunk_on_topic:
        c_issues, corr = detect_corpus_issues(ch, topic, corpus_fn=corpus_fn,
                                              abstract_fn=abstract_fn, backend=backend)
        issues.extend(c_issues)
        evidence_checked = True

    status, conf = _rollup_status(issues, evidence_checked=evidence_checked, corr=corr)
    return ChunkVerdict(
        chunk_key=ch.chunk_key, doc_id=ch.doc_id, h2_anchor=ch.h2_anchor,
        status=status, confidence=conf, issues=tuple(issues), corroboration=corr,
        evidence_checked=evidence_checked, content_hash=content_hash(ch.text))


# ── cross-chunk coherence ────────────────────────────────────────────────────

def _claim_signature(text: str) -> "tuple[frozenset, Optional[str]]":
    from cannavec_science.claim_support import extract_entities, claimed_direction
    from cannavec_science.intent import indication_terms
    ents = extract_entities(text or "")
    inds = indication_terms(text or "")
    key = frozenset(ents.cannabinoids) | inds
    return key, claimed_direction(text or "")


_OPP = {"inhibit": "induce", "induce": "inhibit", "increase": "decrease",
        "decrease": "increase"}


def detect_coherence_issues(chunks: "list[Chunk]") -> "list[ChunkIssue]":
    """Flag two chunks in the batch that assert OPPOSITE directions about the same
    cannabinoid+indication — an internal-consistency conflict the KB must resolve."""
    sigs = [(_claim_signature(c.text), c) for c in chunks]
    issues: list[ChunkIssue] = []
    seen_pairs: set = set()
    for i in range(len(sigs)):
        (k1, d1), c1 = sigs[i]
        if not k1 or not d1:
            continue
        for j in range(i + 1, len(sigs)):
            (k2, d2), c2 = sigs[j]
            if not k2 or not d2 or not (k1 & k2):
                continue
            if _OPP.get(d1) == d2 and d1 != d2:
                pair = tuple(sorted((c1.chunk_key, c2.chunk_key)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                for a, b, d in ((c1, c2, d1), (c2, c1, d2)):
                    issues.append(_issue(
                        "coherence_conflict", "accuracy", a,
                        f"contradicts sibling chunk `{b.chunk_key}` on the same topic",
                        f"this chunk asserts '{d}'; the sibling asserts the opposite",
                        "reconcile the two chunks (mark contradiction_status=contested "
                        "for human review)", chunk_audit.ROUTE_MODEL))
    return issues


def evaluate_chunks(query: str, chunks: Iterable, *, metas=None, **kw) -> "list[ChunkVerdict]":
    """Evaluate a batch and add cross-chunk coherence. Per-chunk topic defaults to
    the shared query. ``metas`` (optional, aligned with ``chunks``) supplies each
    chunk's Truth-Layer frontmatter for the freshness check."""
    parsed = [c if isinstance(c, Chunk) else Chunk.from_dict(c) for c in chunks]
    metas = list(metas) if metas else [None] * len(parsed)
    verdicts = [evaluate_chunk(c, query, meta=metas[i] if i < len(metas) else None, **kw)
                for i, c in enumerate(parsed)]
    coh = detect_coherence_issues(parsed)
    if not coh:
        return verdicts
    by_key: dict = {}
    for issue in coh:
        by_key.setdefault(issue.chunk_key, []).append(issue)
    out: list[ChunkVerdict] = []
    for v in verdicts:
        extra = by_key.get(v.chunk_key)
        if not extra:
            out.append(v)
            continue
        merged = v.issues + tuple(extra)
        status, conf = _rollup_status(merged, evidence_checked=v.evidence_checked,
                                      corr=v.corroboration)
        out.append(ChunkVerdict(
            chunk_key=v.chunk_key, doc_id=v.doc_id, h2_anchor=v.h2_anchor,
            status=status, confidence=conf, issues=merged,
            corroboration=v.corroboration, evidence_checked=v.evidence_checked,
            content_hash=v.content_hash))
    return out
