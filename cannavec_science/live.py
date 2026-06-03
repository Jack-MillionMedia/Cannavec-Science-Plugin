"""Library-level live discovery — the single, offline-testable entry point
for the multi-source primary-source fan-out (spec 028 / Phase 2).

Why this module exists
----------------------
The ``discover`` CLI orchestration lives in ``__main__`` and is coupled to
argparse. The web API (and any future caller) needs the *same* behaviour —
safety preflight, per-lane graceful degradation, cross-source synthesis —
without the CLI scaffolding. This module is that behaviour as a plain
function pair:

- :func:`run_discovery` — fan out across the requested sources, returning a
  JSON-ready dict of per-source rows plus a deterministic cross-source
  synthesis verdict.
- :func:`augment_answer` — weave clearly-tagged, never-promoted live findings
  onto a curated :class:`~cannavec_science.answer.Answer` (Constitution §IX),
  degrading silently to the curated answer on any failure.

Constitution compliance
------------------------
- **§V safety sovereignty:** every entry runs ``discover_guard.preflight``
  before any network call; a refusal raises ``DiscoverRefused``.
- **§IX live-discovery contract:** live rows carry their ``live_*``
  provenance tags and never auto-promote to the curated tier.
- **§X stdlib-only + injected fetchers:** network goes through the searchers'
  fetcher seam. Pass ``runners`` to inject fakes so the offline suite never
  touches the network. Production NCBI calls are authenticated via
  ``NCBI_API_KEY`` (see ``_http.append_ncbi_auth``).
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Optional, Sequence

from cannavec_science._log import get_logger
from cannavec_science.discover_guard import DiscoverRefused, preflight
from cannavec_science.synthesis import synthesize

__all__ = [
    "DEFAULT_SOURCES",
    "SUPPORTED_SOURCES",
    "DiscoverRefused",
    "run_discovery",
    "augment_answer",
    "weave_live_findings",
    "answer_with_fallback",
    "is_thin",
    "default_runners",
]

_log = get_logger("live")

# A runner takes (query, since, max_results) and returns an iterable of row
# objects each exposing ``.to_dict()`` (the searchers' LiveHit dataclasses).
Runner = Callable[[str, Optional[str], int], Iterable]

# Lean default keeps serverless latency + NCBI rate-limit pressure low. The
# full set is opt-in per request.
DEFAULT_SOURCES: tuple[str, ...] = ("pubmed", "ctgov")
SUPPORTED_SOURCES: tuple[str, ...] = ("pubmed", "ctgov", "chembl", "europepmc")

_MAX_RESULTS_CEILING = 25


# ── Production runners (thin wrappers over the tested searchers) ────────

def _run_pubmed(query: str, since: Optional[str], n: int):
    from cannavec_science.pubmed_search import PubMedSearcher
    return PubMedSearcher().search(query, since=since, max_results=n)


def _run_ctgov(query: str, since: Optional[str], n: int):
    from cannavec_science.ctgov_discover import CTGovSearcher
    # Per-source relevance gate: CT.gov free-text matching is broad, so a
    # cannabis-science query must not surface unrelated trials.
    return CTGovSearcher().search(
        query, max_results=n, cannabis_relevant_only=True
    )


def _run_chembl(query: str, since: Optional[str], n: int):
    from cannavec_science.chembl_discover import ChEMBLSearcher
    return ChEMBLSearcher().search(query, max_results=n)


def _run_europepmc(query: str, since: Optional[str], n: int):
    from cannavec_science.europepmc_discover import EuropePMCSearcher
    return EuropePMCSearcher().search(query, since=since, max_results=n)


def default_runners() -> dict[str, Runner]:
    """The production source → runner map (one tested searcher per lane)."""
    return {
        "pubmed": _run_pubmed,
        "ctgov": _run_ctgov,
        "chembl": _run_chembl,
        "europepmc": _run_europepmc,
    }


def _clean_sources(sources: Optional[Sequence[str]]) -> tuple[str, ...]:
    if not sources:
        return DEFAULT_SOURCES
    seen: list[str] = []
    for s in sources:
        s = (s or "").strip().lower()
        if s and s not in seen:
            seen.append(s)
    return tuple(seen) or DEFAULT_SOURCES


# ── Public API ──────────────────────────────────────────────────────────

def run_discovery(
    query: str,
    *,
    sources: Optional[Sequence[str]] = None,
    max_results: int = 10,
    since: Optional[str] = None,
    runners: Optional[Mapping[str, Runner]] = None,
) -> dict:
    """Fan out across ``sources``; return per-source rows + a synthesis verdict.

    Raises :class:`DiscoverRefused` if the safety/banned-pattern preflight
    rejects ``query`` (no network call is made). A failure in one lane is
    captured as ``{"error": ...}`` for that source and never aborts the
    others; the cross-source synthesis is computed over whatever returned.

    The returned dict is JSON-ready:
    ``{"query", "sources": {<src>: [rows]|{"error"}}, "synthesis": {...}}``.
    """
    if not query or not query.strip():
        raise ValueError("run_discovery() requires a non-empty query")
    preflight(query)  # §V — raises DiscoverRefused; no network on refusal

    runners = dict(runners) if runners is not None else default_runners()
    n = max(1, min(int(max_results or 10), _MAX_RESULTS_CEILING))
    wanted = _clean_sources(sources)

    out: dict = {"query": query, "sources": {}}
    for src in sorted(wanted):
        runner = runners.get(src)
        if runner is None:
            out["sources"][src] = {"error": f"unsupported source: {src!r}"}
            continue
        try:
            rows = list(runner(query, since, n))
            out["sources"][src] = [r.to_dict() for r in rows[:n]]
        except DiscoverRefused:
            raise
        except Exception as exc:  # noqa: BLE001 — degrade; never abort fan-out
            _log.warning("live discover lane %s failed: %s", src, exc)
            out["sources"][src] = {"error": str(exc)}

    synth_rows = {
        s: v for s, v in out["sources"].items() if isinstance(v, list)
    }
    out["synthesis"] = synthesize(query, synth_rows).to_dict()
    return out


def weave_live_findings(answer, result: Mapping, *, query: str) -> int:
    """Weave a ``run_discovery`` result onto ``answer`` as the blended brief.

    This is the single place the curated core and the live tier are merged
    (Constitution §IX), so every surface that blends agrees on the result:

    1. Capture the cross-source **synthesis verdict** (STRONG / MIXED / WEAK /
       NONE) into ``answer.live_synthesis`` — so the convergence signal rides
       in the same brief, not a separate ``/api/discover`` call.
    2. **Rerank** the live rows deterministically (BM25 relevance × study-
       design prior × recency, retracted rows sunk last) so the most useful
       primary sources surface first — breadth that is ordered, not raw.
    3. Attach each row as a provenance-tagged, retraction-checked, provisional
       live finding (via :func:`~cannavec_science.answer.live_finding_from_row`).

    Never touches the curated ``evidence_summary`` grade. Returns the number of
    findings attached. Pure given ``result`` (no network here) and stdlib-only.
    """
    from cannavec_science.answer import (
        _LIVE_FLAGGED_STATUSES,
        live_finding_from_row,
    )
    from cannavec_science.ranker import (
        Candidate,
        candidates_from_discovery,
        rank_candidates,
    )

    answer.live_synthesis = result.get("synthesis")
    sources = result.get("sources", {}) or {}

    # Map each row's headline identifier -> (source, row); first occurrence
    # wins, mirroring the ranker's de-dup so order and attachment agree.
    row_by_id: dict = {}
    for src, rows in sources.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            try:
                ident = Candidate.from_row(src, row).identifier
            except Exception:  # noqa: BLE001 — skip an unparseable row
                ident = ""
            if ident and ident not in row_by_id:
                row_by_id[ident] = (src, row)

    if not row_by_id:
        return 0

    try:
        ranked = rank_candidates(
            query,
            candidates_from_discovery(result),
            top_k=max(1, len(row_by_id)),
        ).ranked
        ordered_ids = [rc.candidate.identifier for rc in ranked]
    except Exception:  # noqa: BLE001 — ranking is a best-effort reorder
        ordered_ids = list(row_by_id)
    # Any id the ranker dropped (shouldn't happen) is still attached, after the
    # ranked ones, in stable insertion order — breadth is never silently lost.
    for ident in row_by_id:
        if ident not in ordered_ids:
            ordered_ids.append(ident)

    findings: list[dict] = []
    for ident in ordered_ids:
        sr = row_by_id.get(ident)
        if sr is None:
            continue
        src, row = sr
        finding = live_finding_from_row(src, row)
        if finding:
            findings.append(finding)

    # §VIII hard guard: a retracted / EOC / under-correction live row must
    # never lead the breadth, however query-relevant it is. Pin flagged
    # findings last, preserving the relevance rank *within* each group (stable
    # sort). A plain correction (paper stands) is not flagged, so it is not
    # demoted. This does not depend on the ranker having seen the status.
    findings.sort(
        key=lambda f: f.get("retraction_status", "clean") in _LIVE_FLAGGED_STATUSES
    )

    attached = 0
    for finding in findings:
        before = len(answer.live_findings)
        answer.add_live_finding(**finding)
        if len(answer.live_findings) > before:
            attached += 1
    return attached


def augment_answer(
    answer,
    *,
    sources: Optional[Sequence[str]] = None,
    max_results: int = 5,
    since: Optional[str] = None,
    runners: Optional[Mapping[str, Runner]] = None,
) -> int:
    """Attach clearly-tagged, provisional live findings to ``answer`` (§IX).

    Fans out live discovery on ``answer.prompt`` and weaves the result onto the
    answer via :func:`weave_live_findings` — reranked, retraction-checked
    findings plus the cross-source synthesis verdict, in one brief.

    Returns the number of live findings attached. Degrades silently: a
    refused prompt, an offline lane, or any error leaves the curated answer
    untouched and returns ``0`` — the curated brief always stands. Never
    promotes a live row to the curated grade.
    """
    if getattr(answer, "is_refusal", False):
        return 0
    try:
        result = run_discovery(
            answer.prompt,
            sources=sources,
            max_results=max_results,
            since=since,
            runners=runners,
        )
    except DiscoverRefused:
        return 0
    except Exception as exc:  # noqa: BLE001 — augmentation is best-effort
        _log.warning("augment_answer fan-out failed: %s", exc)
        return 0

    return weave_live_findings(answer, result, query=answer.prompt)


def is_thin(answer) -> bool:
    """True when the curated answer has no real coverage of the question.

    "Thin" = not a refusal AND (no curated claims OR the best curated grade is
    Unsupported). This is the Phase-3 trigger: a genuinely novel question the
    curated knowledge base does not cover, where live discovery should step in.
    A refusal is never thin (we do not fan out on a refused prompt).
    """
    if getattr(answer, "is_refusal", False):
        return False
    if not getattr(answer, "claims", None):
        return True
    from cannavec_science.evidence import EvidenceLevel
    es = getattr(answer, "evidence_summary", None)
    if es is not None and es.highest_grade == EvidenceLevel.UNSUPPORTED:
        return True
    return False


def answer_with_fallback(
    question: str,
    *,
    retraction_policy: str = "strict",
    max_results: int = 5,
    sources: Optional[Sequence[str]] = None,
    since: Optional[str] = None,
    runners: Optional[Mapping[str, Runner]] = None,
) -> tuple:
    """Phase 3 — compose the curated brief and, only if it is *thin*, fall
    back to live primary-source discovery automatically.

    Returns ``(answer, fallback_used)``. ``fallback_used`` is ``True`` when the
    live search was triggered (curated coverage was thin), regardless of how
    many findings it attached. The curated brief always stands; live findings
    are added as provisional, never-promoted rows (§IX) and, when there were
    no curated claims at all, a note clarifies the brief is built from the
    live frontier and must be verified before citing.

    Fully offline-testable: pass ``runners`` to inject fake searchers.
    """
    from cannavec_science.answer import compose_answer

    answer = compose_answer(
        question,
        retraction_policy=retraction_policy,
        include_registries=True,
        include_claims=True,
        include_rigor=True,
    )
    if not is_thin(answer):
        return answer, False

    had_claims = bool(answer.claims)
    augment_answer(
        answer, sources=sources, max_results=max_results,
        since=since, runners=runners,
    )
    if answer.live_findings and not had_claims:
        answer.notes = answer.notes + (
            "0 curated claims — the Live discovery section holds live "
            "primary-source findings (provisional, unverified; NOT curated "
            "facts). Verify each identifier before citing.",
        )
    return answer, True
