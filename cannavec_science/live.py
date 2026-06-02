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

import re
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
    "answer_with_fallback",
    "is_thin",
    "refine_query",
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


# A natural-language question is a poor literature-search query — PubMed
# E-utilities ANDs terms, so function words and generic research verbs
# ("does", "effect", "alter", "in") over-restrict and tank recall. Strip them
# and keep the content terms (cannabinoids, anatomy, hormones, conditions —
# including short medical tokens like T3, LH, CB1).
_QUERY_STOPWORDS = frozenset({
    # articles / auxiliaries / question words / prepositions / conjunctions
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "am",
    "do", "does", "did", "done", "how", "what", "why", "when", "where",
    "which", "who", "whom", "whose", "of", "in", "on", "to", "for", "and",
    "or", "but", "with", "without", "by", "from", "at", "as", "into", "than",
    "then", "that", "this", "these", "those", "it", "its", "between", "among",
    "during", "via", "vs", "versus", "about", "over", "under", "per", "not",
    "no", "any", "there", "their", "they", "we", "you", "your",
    # generic research verbs/nouns that rarely appear in indexed text and
    # only narrow the AND-query
    "effect", "effects", "impact", "impacts", "role", "roles", "level",
    "levels", "alter", "alters", "affect", "affects", "modify", "modifies",
    "modulate", "modulates", "influence", "influences", "change", "changes",
    "contribute", "contributes", "cause", "causes", "use", "uses", "using",
    "associated", "association", "incidence", "extent", "distinct",
})

_MAX_QUERY_TOKENS = 16


def refine_query(question: str) -> str:
    """Turn a natural-language question into a keyword search query.

    Drops function words and generic research verbs, keeps content terms
    (including short medical abbreviations such as ``T3``/``LH``/``CB1``),
    de-duplicates preserving order, and caps length. Falls back to the
    original text if stripping would leave nothing. Used for the auto-fallback
    live search, where the input is a question, not a curated query.
    """
    if not question:
        return question
    tokens = re.findall(r"[a-z0-9][a-z0-9-]*", question.lower())
    kept: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if len(t) < 2 or t in _QUERY_STOPWORDS:
            continue
        if t in seen:
            continue
        seen.add(t)
        kept.append(t)
        if len(kept) >= _MAX_QUERY_TOKENS:
            break
    return " ".join(kept) or question


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


def augment_answer(
    answer,
    *,
    sources: Optional[Sequence[str]] = None,
    max_results: int = 5,
    since: Optional[str] = None,
    runners: Optional[Mapping[str, Runner]] = None,
) -> int:
    """Attach clearly-tagged, provisional live findings to ``answer`` (§IX).

    Returns the number of live findings attached. Degrades silently: a
    refused prompt, an offline lane, or any error leaves the curated answer
    untouched and returns ``0`` — the curated brief always stands. Never
    promotes a live row to the curated grade.
    """
    from cannavec_science.answer import live_finding_from_row

    if getattr(answer, "is_refusal", False):
        return 0
    # Search the keyword-refined question, not the raw sentence — far better
    # literature-search recall (see refine_query).
    query = refine_query(answer.prompt)
    try:
        result = run_discovery(
            query,
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

    attached = 0
    for src, rows in result.get("sources", {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            finding = live_finding_from_row(src, row)
            if finding:
                answer.add_live_finding(**finding)
                attached += 1
    return attached


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
    elif not answer.live_findings and not had_claims:
        # Fallback ran but found no precise primary-source match. Be honest
        # and point the user at the focused-keyword path — robustly turning a
        # full natural-language question into a precise query is a concept-
        # extraction task the deterministic backbone does not attempt.
        answer.notes = answer.notes + (
            "0 curated claims and live discovery found no precise primary-"
            "source match for this phrasing. Try the discover surface with "
            "focused keywords (the cannabinoid + the condition/target, e.g. "
            "'cannabidiol dry eye' rather than a full sentence).",
        )
    return answer, True
