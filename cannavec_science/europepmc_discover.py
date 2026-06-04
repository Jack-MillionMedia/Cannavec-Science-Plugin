"""Live Europe PMC search — read-time discovery surface (spec 005 US6).

Europe PMC (https://europepmc.org/) is the European complement to
PubMed: it indexes PubMed PLUS the full PMC corpus PLUS European
non-MEDLINE-indexed journals (MDPI cannabinoid-research output not yet
in MEDLINE, Wellcome Open Research, European Cannabinoid Research
Society proceedings, etc.). Adding it as a twelfth live primary-source
lane improves recall for European-centred research questions where
PubMed alone misses indexed-elsewhere literature.

Design constraints (constitution):

- **Stdlib-only.** ``urllib.request`` + injected-fetcher pattern,
  matching every existing live discoverer (PubMed, ChEMBL, CT.gov,
  PubChem, PharmGKB, RCSB, Open Targets, GWAS, BindingDB, bioRxiv,
  medRxiv).
- **Safety-layer sovereignty.** ``discover_guard.preflight`` runs
  BEFORE any network call. Refusal raises :class:`SearchRefused`; no
  Europe PMC traffic is emitted under the plugin's tool name on a
  refused prompt.
- **Provenance honest.** Every emitted row carries
  ``provenance="live_europepmc"`` (Provenance enum extended in v0.5)
  and the rendered output marks the results as unverified. Live hits
  do NOT promote to the curated tier without a deliberate registry-row
  patch.
- **Provisional grade only.** The Europe PMC ``pubType`` → GRADE
  heuristic is a hint, not a verdict. Every rendered row carries the
  ``(provisional)`` suffix.

Public surface mirrors :mod:`cannavec_science.pubmed_search`:

- :class:`LiveEuropePMCHit` — typed row.
- :class:`EuropePMCSearcher` — search class with injected fetcher.
- :class:`SearchRefused` — exception type when the safety / banned-
  pattern gate rejects the query before any network call.
- :func:`render_markdown(query, hits)` / :func:`render_json(query, hits)`
  — contract renderers.
- :func:`suggested_grade_for_pubtypes(pubtypes)` — provisional GRADE
  heuristic.
- :func:`default_europepmc_fetcher` — production fetcher with polite
  User-Agent.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Callable, Optional

from cannavec_science._http import TIMEOUT_SLOW, retry_urlopen, user_agent
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "LiveEuropePMCHit",
    "EuropePMCSearcher",
    "SearchRefused",
    "default_europepmc_fetcher",
    "render_markdown",
    "render_json",
    "suggested_grade_for_pubtypes",
]


# ── URLs ──────────────────────────────────────────────────────────────

_EUROPEPMC_SEARCH_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    "?resulttype=core&format=json"
)


_MAX_RESULTS_CEILING = 50
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
def _europepmc_user_agent() -> str:
    return (
        f"{user_agent('europepmc-discover')} "
        "(+https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin)"
    )


# ── Exception ─────────────────────────────────────────────────────────


class SearchRefused(Exception):
    """Raised when the safety / banned-pattern preflight rejects a query
    before any Europe PMC network call.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


# ── Fetcher ───────────────────────────────────────────────────────────


Fetcher = Callable[[str], str]


def default_europepmc_fetcher(url: str) -> str:
    """Production fetcher — polite User-Agent, slow timeout, bounded retry.

    Tests inject a fixture fetcher; this is the production path that
    is only invoked when the operator explicitly opts into the
    --include-europepmc lane on `discover`.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _europepmc_user_agent(),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_SLOW) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ── Hit dataclass ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class LiveEuropePMCHit:
    """A single Europe PMC live-search result.

    Europe PMC returns a richer record than PubMed esummary; we keep
    the same load-bearing fields as :class:`LivePubMedHit` plus the
    Europe PMC-specific ``source`` and ``europe_pmc_id`` fields.
    """

    europe_pmc_id: str   # e.g. "12345678" (PMID-like) or "PMC1234567"
    source: str          # MED / PMC / PPR / AGR / CBA / CTX / ETH / HIR / NBK / PAT
    pmid: str
    doi: str
    title: str
    first_author_surname: str
    year: Optional[int]
    journal: str
    pubtypes: tuple[str, ...]
    is_open_access: bool
    suggested_grade: str
    provenance: str = Provenance.LIVE_EUROPEPMC.value

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pubtypes"] = list(self.pubtypes)
        return d


# ── Suggested-grade heuristic ────────────────────────────────────────


def suggested_grade_for_pubtypes(pubtypes: tuple[str, ...]) -> str:
    """Map Europe PMC pubType tokens to a provisional GRADE hint.

    Same mapping as PubMed's pubtype heuristic (the vocabularies overlap
    heavily because Europe PMC re-uses MEDLINE pubtypes for the indexed-
    in-MEDLINE subset). Static, deterministic, no LLM. The
    ``(provisional)`` suffix is mandatory.
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
    if has("preprint"):
        return "Level D (provisional)"
    # Non-evidence record types — corrections, letters, news, biography —
    # frequently co-carry "Journal Article" but are NOT admissible primary
    # evidence; keep them Unsupported rather than floor them to Level D.
    if has("erratum", "retraction", "comment", "editorial", "newspaper",
           "biography", "historical"):
        return "Unsupported (provisional)"
    # Journal-article floor: a real primary research article whose design we
    # could not classify above (the generic "Journal Article" / "research-
    # article" token nearly every MEDLINE / Europe PMC record carries) is
    # admissible-but-unranked evidence, not "no evidence" — floor it to Level D
    # rather than mislabel it Unsupported. Match the specific generic-article
    # tokens (not a bare "article" substring, which over-matches "Newspaper
    # Article" etc.). Matches the OpenAlex lane. Only a genuinely empty /
    # design-signal-free pubtype set stays Unsupported.
    if has("journal article", "research-article", "journal-article"):
        return "Level D (provisional)"
    return "Unsupported (provisional)"


# ── Searcher ─────────────────────────────────────────────────────────


class EuropePMCSearcher:
    """Live Europe PMC search with injected-fetcher fixtures."""

    def __init__(
        self,
        *,
        fetcher: Optional[Fetcher] = None,
    ) -> None:
        self._fetcher = fetcher or default_europepmc_fetcher

    def search(
        self,
        query: str,
        *,
        since: Optional[str] = None,
        max_results: int = 10,
        open_access_only: bool = False,
    ) -> tuple[LiveEuropePMCHit, ...]:
        """Run a Europe PMC search and return typed hits.

        Raises :class:`SearchRefused` when the safety preflight or
        banned-pattern detector rejects the query before any
        Europe PMC HTTP call.

        Raises :class:`ValueError` when ``since`` is malformed or
        ``max_results`` is out of range.
        """
        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        if since is not None and not _SINCE_RE.match(since):
            raise ValueError(f"--since must be YYYY-MM-DD; got {since!r}")

        # Safety + banned-pattern preflight (shared across every
        # live-discovery source via discover_guard.preflight).
        try:
            preflight(query)
        except DiscoverRefused as exc:
            raise SearchRefused(reason=exc.reason, detail=exc.detail) from exc

        capped = min(max(1, int(max_results)), _MAX_RESULTS_CEILING)
        url = self._build_search_url(
            query, since, capped, open_access_only,
        )
        body = self._fetcher(url)
        records = self._parse_search_payload(body)

        hits: list[LiveEuropePMCHit] = []
        for rec in records[:capped]:
            hit = self._record_to_hit(rec)
            if hit is not None:
                hits.append(hit)

        return tuple(hits)

    # ── URL building ─────────────────────────────────────────────

    def _build_search_url(
        self,
        query: str,
        since: Optional[str],
        page_size: int,
        open_access_only: bool,
    ) -> str:
        # Europe PMC query syntax is rich; we use a minimal subset for
        # the cannabis-research use case: the raw user query plus an
        # optional date floor + optional open-access filter.
        #
        # We deliberately pass NO ``sort`` parameter and rely on Europe PMC's
        # default RELEVANCE ranking. The current Europe PMC REST API silently
        # returns a degenerate ``{"version": ...}`` body — no ``resultList``,
        # no ``hitCount`` — for an unrecognised sort token (e.g. the legacy
        # ``FIRST_PDATE desc`` / ``P_PDATE_D``) instead of an HTTP error, which
        # had silently killed this lane (every query returned zero hits).
        # Relevance is robust to that and is the right default for a
        # research-lead surface; a date floor is still available via ``since``
        # (``FIRST_PDATE:[since TO *]`` is QUERY syntax, not sort syntax, and is
        # accepted). See tests/test_europepmc_discover.py::test_url_omits_sort_*.
        terms: list[str] = [query.strip()]
        if since is not None:
            # Europe PMC accepts FIRST_PDATE:[2023-01-01 TO *]
            # for "first publication date on or after".
            terms.append(f"FIRST_PDATE:[{since} TO *]")
        if open_access_only:
            terms.append("OPEN_ACCESS:Y")
        compound_query = " AND ".join(terms)
        return (
            f"{_EUROPEPMC_SEARCH_URL}"
            f"&query={urllib.parse.quote(compound_query)}"
            f"&pageSize={page_size}"
        )

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_search_payload(body: str) -> list[dict]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return []
        result_list = payload.get("resultList", {}) or {}
        results = result_list.get("result") or []
        return [r for r in results if isinstance(r, dict)]

    @staticmethod
    def _record_to_hit(rec: dict) -> Optional[LiveEuropePMCHit]:
        ident = (rec.get("id") or "").strip()
        source = (rec.get("source") or "").strip()
        if not ident:
            return None
        pmid = (rec.get("pmid") or "").strip()
        doi = (rec.get("doi") or "").strip()
        title = (rec.get("title") or "").strip()
        # Europe PMC's authorString is comma-separated; the first
        # token is "Surname Initials" — extract the surname.
        author_string = (rec.get("authorString") or "").strip()
        first_surname = ""
        if author_string:
            first_token = author_string.split(",")[0].strip()
            if first_token:
                # "Smith J" → "Smith"; "Smith JK" → "Smith"
                parts = first_token.split()
                first_surname = parts[0] if parts else ""
        year_raw = rec.get("pubYear") or ""
        try:
            year: Optional[int] = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            year = None
        journal = (rec.get("journalTitle") or "").strip()
        # Europe PMC pubTypeList is a dict with a "pubType" list.
        pubtypes_field = rec.get("pubTypeList") or {}
        pubtypes_raw = pubtypes_field.get("pubType") or []
        pubtypes = tuple(
            p for p in pubtypes_raw if isinstance(p, str)
        )
        is_open_access = (rec.get("isOpenAccess") or "").upper() == "Y"
        return LiveEuropePMCHit(
            europe_pmc_id=ident,
            source=source,
            pmid=pmid,
            doi=doi,
            title=title,
            first_author_surname=first_surname,
            year=year,
            journal=journal,
            pubtypes=pubtypes,
            is_open_access=is_open_access,
            suggested_grade=suggested_grade_for_pubtypes(pubtypes),
            provenance=Provenance.LIVE_EUROPEPMC.value,
        )


# ── Renderers ─────────────────────────────────────────────────────────


def render_markdown(
    query: str, hits: tuple[LiveEuropePMCHit, ...]
) -> str:
    lines: list[str] = [
        f"## Live Europe PMC search — {query}",
        "",
        "_Source: live Europe PMC REST API (complement to PubMed; "
        "indexes PubMed + PMC full-text + European non-MEDLINE-indexed "
        "journals). Each row is unverified by Cannavec; treat as a "
        "research lead, not as a settled claim. Suggested grades are "
        "provisional pubtype heuristics; the verified grade lives in "
        "the curated registry only._",
        "",
    ]
    if not hits:
        lines.append("_No hits returned by Europe PMC for this query._")
        return "\n".join(lines) + "\n"

    lines.append(
        "| ID | Source | Year | First author | Journal | Type | Grade (provisional) | OA |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for h in hits:
        type_str = h.pubtypes[0] if h.pubtypes else "Journal Article"
        oa_flag = "✓" if h.is_open_access else ""
        link = (
            f"[{h.europe_pmc_id}]"
            f"(https://europepmc.org/article/{h.source}/{h.europe_pmc_id})"
            if h.source else h.europe_pmc_id
        )
        lines.append(
            f"| {link} "
            f"| {h.source or '—'} "
            f"| {h.year or '—'} "
            f"| {h.first_author_surname or '—'} "
            f"| {h.journal or '—'} "
            f"| {type_str} "
            f"| {h.suggested_grade} "
            f"| {oa_flag} |"
        )

    return "\n".join(lines) + "\n"


def render_json(
    query: str, hits: tuple[LiveEuropePMCHit, ...]
) -> str:
    return json.dumps(
        {
            "query": query,
            "hits": [h.to_dict() for h in hits],
            "provenance": Provenance.LIVE_EUROPEPMC.value,
        },
        indent=2,
        sort_keys=True,
    )
