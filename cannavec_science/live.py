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
    return CTGovSearcher().search(query, max_results=n)


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
