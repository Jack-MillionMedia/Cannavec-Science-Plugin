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
    "BRIEF_SOURCES",
    "DiscoverRefused",
    "run_discovery",
    "augment_answer",
    "weave_live_findings",
    "answer_with_fallback",
    "is_thin",
    "default_runners",
    "ALL_LANE_RUNNERS",
]

_log = get_logger("live")

# A runner takes (query, since, max_results) and returns an iterable of row
# objects each exposing ``.to_dict()`` (the searchers' LiveHit dataclasses).
Runner = Callable[[str, Optional[str], int], Iterable]

# Lean default keeps serverless latency + NCBI rate-limit pressure low. The
# full set is opt-in per request.
DEFAULT_SOURCES: tuple[str, ...] = ("pubmed", "ctgov")
SUPPORTED_SOURCES: tuple[str, ...] = (
    "pubmed", "ctgov", "chembl", "europepmc", "chebi", "quickgo",
    "reactome", "efo",
)

# Spec 036 Step 5 — the literature-breadth lane set for the brief / PDF / CLI
# augment path (Task 7 opts into this). Broader than the lean serverless
# ``DEFAULT_SOURCES`` (which stays the web-API default): it adds the second
# literature lane (Europe PMC) and the bioactivity lane (ChEMBL) for mechanistic
# context, so the brief is "packed with all relevant evidence" without changing
# the lean web-API default. STRICT INVARIANT (pinned by tests):
# ``DEFAULT_SOURCES ⊆ BRIEF_SOURCES ⊆ default_runners().keys()`` — every BRIEF
# lane is a real, wired lane; this is an additional named SUBSET, never a new
# lane. ``DEFAULT_SOURCES`` / ``SUPPORTED_SOURCES`` / ``default_runners`` are
# UNCHANGED (registry invariants depend on them).
BRIEF_SOURCES: tuple[str, ...] = ("pubmed", "europepmc", "ctgov", "chembl")

# Reliability backfill (M1): NCBI E-utilities is the flakiest upstream — a
# shared-IP, key-less rate limit returns transient 500s and body-read timeouts
# (now retried in _http.retry_fetch), but a wholly-down NCBI still leaves a
# PubMed query empty. Europe PMC indexes the same MEDLINE from a different host,
# so it backfills a failed/empty PubMed lane. Cross-source de-dup
# (synthesis._citation_key, PMID-first) collapses any overlap, so a paper
# surfaced by both never manufactures false convergence. Fires ONLY when PubMed
# produced nothing — zero happy-path latency.
PUBMED_FALLBACK_SOURCE = "europepmc"


def needs_pubmed_fallback(sources_payload: Mapping) -> bool:
    """True iff a PubMed lane was attempted but yielded no rows (error or
    empty) and Europe PMC has not already contributed rows.

    Centralises the *policy*; each fan-out path supplies the *mechanism* (how to
    invoke the Europe PMC runner in its own calling convention), so the two
    discovery paths — :func:`run_discovery` and the CLI ``_cmd_discover`` — stay
    consistent without duplicating the decision.
    """
    pubmed = sources_payload.get("pubmed")
    if pubmed is None:
        return False  # PubMed was not requested — nothing to back up.
    pubmed_empty = (not pubmed) if isinstance(pubmed, list) else True
    epmc = sources_payload.get(PUBMED_FALLBACK_SOURCE)
    epmc_has_rows = isinstance(epmc, list) and len(epmc) > 0
    return pubmed_empty and not epmc_has_rows


_MAX_RESULTS_CEILING = 25

# Phase-2 on-topic gate (spec 036) — DEMOTE floor: a live row scoring below
# this fraction of the strongest live row's BM25 is kept but tagged off_topic
# (sorted after the on-topic rows, never dropped). Relative because BM25 here
# is corpus-relative over the small live set; loose (0.20) so only genuinely
# weak-lexical context rows are demoted, mirroring the ranker's own
# ``relevance_floor_frac`` (0.25). The hard wrong-indication DROP is separate.
_DEMOTE_BM25_FRAC = 0.20


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


def _run_chebi(query: str, since: Optional[str], n: int):
    from cannavec_science.chebi_discover import ChEBISearcher
    return ChEBISearcher().search(query, max_results=n)


def _run_quickgo(query: str, since: Optional[str], n: int):
    from cannavec_science.quickgo_discover import QuickGOSearcher
    return QuickGOSearcher().search(query, max_results=n)


def _run_reactome(query: str, since: Optional[str], n: int):
    from cannavec_science.reactome_discover import ReactomeSearcher
    return ReactomeSearcher().search(query, max_results=n)


def _run_efo(query: str, since: Optional[str], n: int):
    from cannavec_science.efo_discover import EFOSearcher
    return EFOSearcher().search(query, max_results=n)


def _run_pubchem(query: str, since: Optional[str], n: int):
    from cannavec_science.pubchem_discover import PubChemSearcher
    return PubChemSearcher().search(query, max_results=n)


def _run_pharmgkb(query: str, since: Optional[str], n: int):
    from cannavec_science.pharmgkb_discover import PharmGKBSearcher
    return PharmGKBSearcher().search(query, max_results=n)


def _run_rcsb(query: str, since: Optional[str], n: int):
    from cannavec_science.rcsb_discover import RCSBSearcher
    return RCSBSearcher().search(query, max_results=n)


def _run_opentargets(query: str, since: Optional[str], n: int):
    from cannavec_science.opentargets_discover import OpenTargetsSearcher
    return OpenTargetsSearcher().search(query, max_results=n)


def _run_gwas(query: str, since: Optional[str], n: int):
    from cannavec_science.gwas_discover import GWASSearcher
    return GWASSearcher().search(query, max_results=n)


def _run_bindingdb(query: str, since: Optional[str], n: int):
    from cannavec_science.bindingdb_discover import BindingDBSearcher
    return BindingDBSearcher().search(query, max_results=n)


def _run_biorxiv(query: str, since: Optional[str], n: int):
    from cannavec_science.biorxiv_discover import BioRxivSearcher
    return BioRxivSearcher().search(query, since=since, max_results=n)


def _run_medrxiv(query: str, since: Optional[str], n: int):
    from cannavec_science.medrxiv_discover import MedRxivSearcher
    return MedRxivSearcher().search(query, since=since, max_results=n)


def _run_openalex(query: str, since: Optional[str], n: int):
    from cannavec_science.openalex_discover import OpenAlexSearcher
    return OpenAlexSearcher().search(query, since=since, max_results=n)


# The ONE canonical source → runner map (one tested searcher per lane), shared by
# BOTH the web-API blended path (via :func:`default_runners`) and the ``discover``
# CLI (via an args-adapter in ``__main__``). Previously these two surfaces kept
# parallel copies of ~25 near-identical wrappers that drifted; this is the single
# source of truth. Per-lane ``since`` handling is encoded here (preprint /
# Europe PMC / OpenAlex / PubMed pass it; the rest ignore it), so the args-adapter
# in ``__main__`` is uniform.
ALL_LANE_RUNNERS: dict[str, Runner] = {
    "pubmed": _run_pubmed,
    "chembl": _run_chembl,
    "ctgov": _run_ctgov,
    "pubchem": _run_pubchem,
    "pharmgkb": _run_pharmgkb,
    "rcsb": _run_rcsb,
    "opentargets": _run_opentargets,
    "gwas": _run_gwas,
    "bindingdb": _run_bindingdb,
    # Spec 002 US1 — preprint lanes (Level D cap per FR-202).
    "biorxiv": _run_biorxiv,
    "medrxiv": _run_medrxiv,
    # Spec 005/006 — Europe PMC + OpenAlex primary-source lanes.
    "europepmc": _run_europepmc,
    "openalex": _run_openalex,
    # Spec 029 — EBI chemical-ontology + functional-annotation lanes.
    "chebi": _run_chebi,
    "quickgo": _run_quickgo,
    # Spec 030 — pathway + disease-ontology lanes.
    "reactome": _run_reactome,
    "efo": _run_efo,
}


def default_runners() -> dict[str, Runner]:
    """The blended-answer source → runner map — a deliberately curated SUBSET of
    :data:`ALL_LANE_RUNNERS` (``SUPPORTED_SOURCES``).

    The web-API / blended-answer path advertises a leaner lane set than the full
    ``discover`` CLI (latency + NCBI rate-limit pressure, and only lanes whose
    rows weave cleanly as a blended brief). The subset is ``SUPPORTED_SOURCES``;
    the invariant ``SUPPORTED_SOURCES == default_runners().keys()`` is enforced by
    ``tests/test_lane_registry_invariants.py``.
    """
    return {src: ALL_LANE_RUNNERS[src] for src in SUPPORTED_SOURCES}


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

    # Reliability backfill: a failed/empty PubMed lane is backed up by Europe
    # PMC from a different host (see PUBMED_FALLBACK_SOURCE). Fires only when
    # PubMed produced nothing, so the happy path pays no extra call.
    if needs_pubmed_fallback(out["sources"]):
        fallback = runners.get(PUBMED_FALLBACK_SOURCE)
        if fallback is not None:
            try:
                rows = list(fallback(query, since, n))
                if rows:
                    out["sources"][PUBMED_FALLBACK_SOURCE] = [
                        r.to_dict() for r in rows[:n]
                    ]
                    out["pubmed_fallback"] = PUBMED_FALLBACK_SOURCE
            except DiscoverRefused:
                raise
            except Exception as exc:  # noqa: BLE001 — degrade; never abort
                _log.warning(
                    "pubmed fallback lane %s failed: %s",
                    PUBMED_FALLBACK_SOURCE, exc,
                )

    synth_rows = {
        s: v for s, v in out["sources"].items() if isinstance(v, list)
    }
    out["synthesis"] = synthesize(query, synth_rows).to_dict()

    # Write-through to the verified-source flywheel (M2): cache every verified,
    # non-retracted live row so the offline KB grows with each query. Degrades
    # silently (read-only fs, locked db) — a cache write never breaks discovery.
    try:
        from cannavec_science import live_cache
        live_cache.record_discovery(query, out["sources"])
    except Exception:  # noqa: BLE001
        pass
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
        live_row_is_wrong_indication,
    )
    from cannavec_science.intent import indication_terms
    from cannavec_science.ranker import (
        Candidate,
        candidates_from_discovery,
        rank_candidates,
    )
    from cannavec_science.synthesis import _row_direction

    sources = result.get("sources", {}) or {}

    # Spec 036 Step 4 — search-provenance counts for the Live-section header.
    # N sources QUERIED (a lane that returned a list, reachable or not) and the
    # total rows FOUND before any on-topic gating. Both deterministic, from the
    # result the caller already has — never fabricated.
    sources_searched = sum(1 for rows in sources.values() if isinstance(rows, list))
    findings_found = sum(
        len(rows) for rows in sources.values() if isinstance(rows, list)
    )

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
        answer.live_synthesis = result.get("synthesis")
        answer.live_sources_searched = sources_searched
        answer.live_findings_found = findings_found
        return 0

    bm25_by_id: dict[str, float] = {}
    try:
        ranked = rank_candidates(
            query,
            candidates_from_discovery(result),
            top_k=max(1, len(row_by_id)),
        ).ranked
        ordered_ids = [rc.candidate.identifier for rc in ranked]
        for rc in ranked:
            bm25_by_id[rc.candidate.identifier] = float(
                rc.signals.get("bm25", 0.0)
            )
    except Exception:  # noqa: BLE001 — ranking is a best-effort reorder
        ordered_ids = list(row_by_id)
    # Any id the ranker dropped (shouldn't happen) is still attached, after the
    # ranked ones, in stable insertion order — breadth is never silently lost.
    for ident in row_by_id:
        if ident not in ordered_ids:
            ordered_ids.append(ident)

    # ── Phase-2 on-topic gate (spec 036) ──────────────────────────────────
    # The single live merge point is also the single place breadth is made
    # honest. Two verdicts, applied here (never in ``evidence_summary``):
    #
    #   DROP   — a wrong-indication clinical-efficacy row (its title names a
    #            condition different from the query's) is removed: surfacing a
    #            Dravet seizure trial for a Tourette query answers a *different
    #            question* (mirrors the curated off-KB gate). Counted.
    #   DEMOTE — a low lexical-relevance / context row is KEPT (breadth is
    #            never silently lost) but tagged ``off_topic`` and sorted after
    #            the on-topic rows, so it never leads. A mechanistic/context row
    #            whose title names no indication is on-topic by default.
    #
    # The relevance floor is RELATIVE (a fraction of the strongest live row's
    # BM25), mirroring the ranker's own ``relevance_floor_frac`` — BM25 here is
    # corpus-relative over the live set, so an absolute floor is meaningless.
    prompt_inds = indication_terms(query)
    surviving_bm25 = [
        bm25_by_id.get(i, 0.0)
        for i in ordered_ids
        if not live_row_is_wrong_indication(
            row_by_id[i][1].get("title") or "", prompt_inds
        )
    ]
    max_bm25 = max(surviving_bm25, default=0.0)
    bm25_floor = _DEMOTE_BM25_FRAC * max_bm25

    findings: list[dict] = []
    dropped_off_topic = 0
    kept_rows: dict = {}  # source -> [on-topic rows] for honest synthesis
    for ident in ordered_ids:
        sr = row_by_id.get(ident)
        if sr is None:
            continue
        src, row = sr
        title = row.get("title") or ""
        if live_row_is_wrong_indication(title, prompt_inds):
            dropped_off_topic += 1
            continue  # hard DROP — never attached, never synthesized
        finding = live_finding_from_row(src, row)
        if not finding:
            continue
        # DEMOTE (keep) a low-relevance / context row so it never leads.
        if bm25_by_id.get(ident, 0.0) < bm25_floor:
            finding["off_topic"] = True
        # Spec 036 Step 4 — direction from the EXISTING synthesis attributor
        # (``_row_direction``: PubMed/preprint abstract sentiment, CTgov results,
        # else neutral). No new sentiment model — only attached where synthesis
        # already determines a non-neutral verdict, so a row with no direction
        # signal keeps its pinned shape.
        direction = _row_direction(src, row)
        if direction and direction != "neutral":
            finding["direction"] = direction
        findings.append(finding)
        kept_rows.setdefault(src, []).append(row)

    # Convergence must be computed over ON-TOPIC rows only — a dropped wrong-
    # indication row must not manufacture a cross-source agreement signal.
    if dropped_off_topic:
        answer.live_synthesis = synthesize(query, kept_rows).to_dict()
    else:
        answer.live_synthesis = result.get("synthesis")

    # §VIII hard guard is the PRIMARY pin: a retracted / EOC / under-correction
    # live row must sink last of all, however query-relevant it is — it must
    # outrank even the on-topic/off-topic split (a flagged row never leads, an
    # off-topic clean row may still lead a flagged one). Off_topic demotion is
    # the secondary key. Stable sort preserves the relevance rank *within* each
    # group. A plain correction (paper stands) is not flagged, so not demoted.
    findings.sort(
        key=lambda f: (
            f.get("retraction_status", "clean") in _LIVE_FLAGGED_STATUSES,
            bool(f.get("off_topic")),
        )
    )

    answer.on_topic_filter_applied = True
    answer.live_findings_dropped_off_topic = dropped_off_topic
    answer.live_sources_searched = sources_searched
    answer.live_findings_found = findings_found

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
