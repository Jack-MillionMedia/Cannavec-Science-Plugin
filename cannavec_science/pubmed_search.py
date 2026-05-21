"""Live PubMed E-utilities search — read-time discovery surface.

cannabis-insight-engine spec 001 User Story 1.

Cannavec's curated registries are a 2026-05 snapshot. A researcher or
clinician needs to find primary literature published AFTER the snapshot.
This module wraps PubMed E-utilities ``esearch`` + ``esummary`` so the
plugin can surface unverified-but-recent candidate papers — with a hard
disclaimer distinguishing them from curated-tier claims.

Design constraints (constitution):

- **Stdlib-only.** Same ``urllib.request`` + injected-fetcher pattern
  as :mod:`cannavec.pubmed_verify`.
- **Safety-layer sovereignty.** The safety preflight and the banned-
  pattern detector run BEFORE any network call. A refused verdict
  raises :class:`SearchRefused`; no NCBI traffic is emitted under the
  plugin's tool name on a refused prompt.
- **Provenance honest.** Every emitted row carries
  ``provenance="live_pubmed"`` (per the Provenance enum shared
  across every live-discovery source — spec 002 FR-017) and the
  rendered output marks the results as unverified. Live hits do
  NOT promote to the curated tier without an operator's deliberate
  registry-row patch.
- **Retraction-aware.** When NCBI flags a result as
  ``Retracted Publication``, it is sorted to the bottom of the result
  list with a visible flag.
- **Provisional grade only.** The pubtype → GRADE heuristic is a
  hint, not a verdict. Every rendered row carries the
  "(provisional)" suffix.

Public surface:

- :class:`LivePubMedHit` — typed row.
- :class:`PubMedSearcher` — search class with injected fetchers.
- :class:`SearchRefused` — exception type when safety / banned-pattern
  gates reject the query before network.
- :func:`render_markdown(query, hits)` — Markdown contract renderer.
- :func:`render_json(query, hits)` — JSON contract renderer.
- :func:`suggested_grade_for_pubtypes(pubtypes)` — provisional grade
  heuristic; exposed for tests and downstream callers.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, asdict, field
from typing import Callable, Optional

from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight
from cannavec_science.pubmed_verify import (
    Fetcher,
    default_pubmed_fetcher,
    _parse_pubmed_year,
)


__all__ = [
    "LivePubMedHit",
    "PubMedSearcher",
    "SearchRefused",
    "render_markdown",
    "render_json",
    "suggested_grade_for_pubtypes",
]


# ── URLs ──────────────────────────────────────────────────────────────

_PUBMED_ESEARCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&retmode=json&tool=cannavec"
)
_PUBMED_ESUMMARY_URL_BULK = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    "?db=pubmed&retmode=json&tool=cannavec&id={ids}"
)


_MAX_RESULTS_CEILING = 50
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Exception ─────────────────────────────────────────────────────────


class SearchRefused(Exception):
    """Raised when the safety preflight or banned-pattern detector
    rejects a search query before any network call.

    The caller (CLI / slash command) catches this and emits the
    standard refusal to the user. The exception's ``reason`` field
    carries the structured refusal reason (e.g.
    ``"individualized_dosing"`` or
    ``"banned_pattern:cultivar_as_effect"``).
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


# ── Hit dataclass ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class LivePubMedHit:
    """A single live-search result.

    The ``provenance`` field is the load-bearing distinction from
    curated-registry rows. Renderers MUST surface this on every row.
    """

    pmid: str
    title: str
    first_author_surname: str
    year: Optional[int]
    journal: str
    pubtypes: tuple[str, ...]
    retraction_status: str
    suggested_grade: str
    provenance: str = Provenance.LIVE_PUBMED.value

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pubtypes"] = list(self.pubtypes)
        return d


# ── Suggested-grade heuristic ────────────────────────────────────────


def suggested_grade_for_pubtypes(pubtypes: tuple[str, ...]) -> str:
    """Map NCBI ``pubtype`` tokens to a provisional GRADE hint.

    Static, deterministic, no LLM. The ``(provisional)`` suffix is
    mandatory — Cannavec's verified grades come from curated rows,
    not from PubMed metadata. Ordered most-specific first so a paper
    that is both "Review" and "Systematic Review" grades to A.
    """
    types_lower = {p.lower() for p in pubtypes}

    def has(*needles: str) -> bool:
        return any(any(n in t for n in needles) for t in types_lower)

    if has("meta-analysis"):
        return "Level A (provisional)"
    if has("systematic review"):
        return "Level A (provisional)"
    if has("randomized controlled trial"):
        return "Level B (provisional)"
    if has("clinical trial"):
        return "Level C (provisional)"
    if has("observational study", "cohort"):
        return "Level C (provisional)"
    if has("case reports"):
        return "Level D (provisional)"
    if has("review"):
        return "Level D (provisional)"
    return "Unsupported (provisional)"


# ── Searcher ─────────────────────────────────────────────────────────


class PubMedSearcher:
    """Live PubMed search with injected-fetcher fixtures.

    Production callers leave the fetcher arguments at None to use the
    polite ``cannavec-pubmed-verify`` User-Agent. Tests inject
    fixture fetchers so the suite runs offline.
    """

    def __init__(
        self,
        *,
        esearch_fetcher: Optional[Fetcher] = None,
        esummary_fetcher: Optional[Fetcher] = None,
    ) -> None:
        self._esearch_fetcher = esearch_fetcher or default_pubmed_fetcher
        self._esummary_fetcher = esummary_fetcher or default_pubmed_fetcher

    def search(
        self,
        query: str,
        *,
        since: Optional[str] = None,
        max_results: int = 10,
    ) -> tuple[LivePubMedHit, ...]:
        """Run an esearch + esummary pair and return typed hits.

        Raises :class:`SearchRefused` when the safety preflight or the
        banned-pattern detector rejects the query.
        Raises :class:`ValueError` when ``since`` is malformed.
        """
        # Argument validation FIRST — the safety gates use the raw
        # query so we don't pre-process before the check.
        if since is not None and not _SINCE_RE.match(since):
            raise ValueError(
                f"--since must be YYYY-MM-DD; got {since!r}"
            )

        # Shared safety + banned-pattern preflight (Constitution
        # principle IV). Network calls only happen for non-refused
        # queries. Delegated to cannavec.discover_guard.preflight so
        # every live-discovery source uses the identical gate (spec
        # 002 foundational layer). SearchRefused remains the public
        # exception type for PubMed-specific callers; we translate
        # the shared DiscoverRefused into it to preserve the
        # backwards-compatible public API.
        try:
            preflight(query)
        except DiscoverRefused as exc:
            raise SearchRefused(reason=exc.reason, detail=exc.detail) from exc

        # esearch
        capped = min(max(1, int(max_results)), _MAX_RESULTS_CEILING)
        esearch_url = self._build_esearch_url(query, since, capped)
        body = self._esearch_fetcher(esearch_url)
        pmids = self._parse_esearch_idlist(body)

        if not pmids:
            return ()

        # esummary
        esummary_url = _PUBMED_ESUMMARY_URL_BULK.format(
            ids=",".join(pmids)
        )
        sumbody = self._esummary_fetcher(esummary_url)
        records = self._parse_esummary_bulk(sumbody, pmids)

        # Build typed hits
        hits: list[LivePubMedHit] = []
        for pmid in pmids:
            rec = records.get(pmid)
            if rec is None:
                continue
            hits.append(self._record_to_hit(pmid, rec))

        # Sort retracted to bottom; otherwise preserve esearch's
        # relevance order.
        return tuple(sorted(
            hits, key=lambda h: 1 if h.retraction_status == "retracted" else 0
        ))

    # ── URL building ─────────────────────────────────────────────

    def _build_esearch_url(
        self, query: str, since: Optional[str], retmax: int
    ) -> str:
        parts = [
            _PUBMED_ESEARCH_URL,
            f"&term={urllib.parse.quote(query)}",
            f"&retmax={retmax}",
            "&sort=date",
        ]
        if since is not None:
            # NCBI expects YYYY/MM/DD with slashes; we accept dashes
            # and convert. datetype=pdat = publication date. Force
            # slash encoding (safe="") so the URL is unambiguous when
            # logged or re-parsed.
            ncbi_date = since.replace("-", "/")
            parts.append(
                f"&mindate={urllib.parse.quote(ncbi_date, safe='')}"
                f"&datetype=pdat"
            )
        return "".join(parts)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_esearch_idlist(body: str) -> tuple[str, ...]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return ()
        result = payload.get("esearchresult", {}) or {}
        ids = result.get("idlist") or []
        return tuple(str(x) for x in ids if x)

    @staticmethod
    def _parse_esummary_bulk(
        body: str, pmids: tuple[str, ...]
    ) -> dict[str, dict]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {}
        result = payload.get("result", {}) or {}
        out: dict[str, dict] = {}
        for pmid in pmids:
            rec = result.get(pmid)
            if isinstance(rec, dict) and "error" not in rec:
                out[pmid] = rec
        return out

    @staticmethod
    def _record_to_hit(pmid: str, rec: dict) -> LivePubMedHit:
        title = (rec.get("title") or "").strip()
        journal = (rec.get("source") or "").strip()
        year = _parse_pubmed_year(rec.get("pubdate") or "")
        authors = rec.get("authors") or []
        first_surname = ""
        if authors and isinstance(authors[0], dict):
            name = authors[0].get("name") or ""
            if name:
                first_surname = name.strip().split()[0]
        pubtypes_field = rec.get("pubtype") or []
        pubtypes = tuple(
            p for p in pubtypes_field if isinstance(p, str)
        )
        # Retraction detection mirrors PubMedRecord.retraction_status
        # so the live-search surface matches the verifier's semantics.
        types_lower = {p.lower() for p in pubtypes}
        if any("retract" in p for p in types_lower):
            retraction = "retracted"
        elif any("expression of concern" in p for p in types_lower):
            retraction = "expression_of_concern"
        elif any("correct" in p or "errat" in p for p in types_lower):
            retraction = "correction"
        else:
            retraction = "clean"

        return LivePubMedHit(
            pmid=pmid,
            title=title,
            first_author_surname=first_surname,
            year=year,
            journal=journal,
            pubtypes=pubtypes,
            retraction_status=retraction,
            suggested_grade=suggested_grade_for_pubtypes(pubtypes),
            provenance=Provenance.LIVE_PUBMED.value,
        )


# ── Renderers ─────────────────────────────────────────────────────────


def render_markdown(
    query: str, hits: tuple[LivePubMedHit, ...]
) -> str:
    """Render the live-search hits as Markdown per the contract."""
    lines: list[str] = [
        f"## Live PubMed search — {query}",
        "",
        "_Source: live PubMed E-utilities, not Cannavec's curated "
        "registry. Each row is unverified by Cannavec; treat as a "
        "research lead, not as a settled claim. Suggested grades are "
        "provisional pubtype heuristics; the verified grade lives in "
        "the curated registry only._",
        "",
    ]
    if not hits:
        lines.append("_No hits returned by PubMed for this query._")
        return "\n".join(lines) + "\n"

    lines.append(
        "| PMID | Year | First author | Journal | Type | Grade (provisional) |"
    )
    lines.append("|---|---|---|---|---|---|")
    for h in hits:
        type_str = (
            h.pubtypes[0] if h.pubtypes else "Journal Article"
        )
        flag = (
            f" ⚠ {h.retraction_status}"
            if h.retraction_status != "clean" else ""
        )
        lines.append(
            f"| [{h.pmid}](https://pubmed.ncbi.nlm.nih.gov/{h.pmid}/) "
            f"| {h.year or '—'} "
            f"| {h.first_author_surname or '—'} "
            f"| {h.journal or '—'} "
            f"| {type_str}{flag} "
            f"| {h.suggested_grade} |"
        )

    if any(h.retraction_status != "clean" for h in hits):
        lines.append("")
        lines.append(
            "_⚠ One or more results have a retraction / correction "
            "flag. They appear at the bottom of the table. Do not "
            "cite without independent verification._"
        )

    return "\n".join(lines) + "\n"


def render_json(
    query: str, hits: tuple[LivePubMedHit, ...]
) -> str:
    """Render the live-search hits as JSON per the contract."""
    return json.dumps(
        {
            "query": query,
            "hits": [h.to_dict() for h in hits],
            "provenance": Provenance.LIVE_PUBMED.value,
        },
        indent=2,
        sort_keys=True,
    )
