"""Live OpenAlex search — read-time discovery surface (spec 006 US6 / FR-007).

OpenAlex (https://openalex.org/) is the open scholarly citation graph
that succeeded Microsoft Academic Graph — it indexes PubMed PLUS arXiv
/ bioRxiv / medRxiv PLUS conference proceedings PLUS book chapters AND
exposes a complete open citation network (works that cite a paper,
works that the paper cites). Adding OpenAlex as a thirteenth live
primary-source lane improves recall for citation-network-anchored
research questions (e.g. who has cited Di Forti 2019 EU-GEI in the
last 12 months) and extends coverage beyond MEDLINE / EBI Europe PMC.

Design constraints (constitution):

- **Stdlib-only.** ``urllib.request`` + injected-fetcher pattern,
  matching every existing live discoverer (PubMed, ChEMBL, CT.gov,
  PubChem, PharmGKB, RCSB, Open Targets, GWAS, BindingDB, bioRxiv,
  medRxiv, Europe PMC).
- **Safety-layer sovereignty.** ``discover_guard.preflight`` runs
  BEFORE any network call.
- **Provenance honest.** Every emitted row carries
  ``provenance="live_openalex"`` and the rendered output marks the
  results as unverified. Live hits do NOT promote to the curated tier.
- **Provisional grade only.** The OpenAlex ``type`` + concept tags →
  GRADE heuristic is a hint, not a verdict. Every rendered row carries
  the ``(provisional)`` suffix.

Public surface mirrors :mod:`cannavec_science.europepmc_discover`:

- :class:`LiveOpenAlexHit` — typed row.
- :class:`OpenAlexSearcher` — search class with injected fetcher.
- :class:`SearchRefused` — exception type when the safety / banned-
  pattern gate rejects the query before any network call.
- :func:`render_markdown(query, hits)` / :func:`render_json(query, hits)`
  — contract renderers.
- :func:`suggested_grade_for_openalex_type(type_, concepts)` —
  provisional GRADE heuristic.
- :func:`default_openalex_fetcher` — production fetcher with polite
  User-Agent.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Callable, Optional

from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "LiveOpenAlexHit",
    "OpenAlexSearcher",
    "SearchRefused",
    "default_openalex_fetcher",
    "render_markdown",
    "render_json",
    "suggested_grade_for_openalex_type",
]


# ── URLs ──────────────────────────────────────────────────────────────

_OPENALEX_WORKS_URL = "https://api.openalex.org/works"

_MAX_RESULTS_CEILING = 50
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_USER_AGENT = (
    "cannavec-openalex-discover/0.6 "
    "(+https://github.com/Jack-MillionMedia/Cannavec-Science-Plugin "
    "mailto:research@cannavec.example)"
)


class SearchRefused(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


Fetcher = Callable[[str], str]


def default_openalex_fetcher(url: str) -> str:
    """Production fetcher — polite User-Agent + mailto, 12s timeout.

    OpenAlex grants higher per-IP rate limits to clients that include
    ``mailto=`` in either the URL or the User-Agent header; the
    cannavec User-Agent embeds the mailto.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="replace")


@dataclass(frozen=True)
class LiveOpenAlexHit:
    openalex_id: str          # e.g. "W2741809807"
    doi: str
    pmid: str
    title: str
    first_author_surname: str
    year: Optional[int]
    venue: str                # journal / preprint server / conference
    work_type: str            # journal-article / preprint / book-chapter / ...
    concepts: tuple[str, ...] # top-3 OpenAlex concepts
    cited_by_count: int
    is_open_access: bool
    suggested_grade: str
    provenance: str = Provenance.LIVE_OPENALEX.value

    def to_dict(self) -> dict:
        d = asdict(self)
        d["concepts"] = list(self.concepts)
        return d


def suggested_grade_for_openalex_type(
    work_type: str,
    concepts: tuple[str, ...] = (),
) -> str:
    """Map OpenAlex work-type + concept tags to a provisional GRADE hint."""
    type_lower = (work_type or "").lower()
    concepts_lower = {c.lower() for c in concepts}

    def has_concept(*needles: str) -> bool:
        return any(any(n in c for n in needles) for c in concepts_lower)

    # Highest precedence: concept-tagged synthesis evidence.
    if has_concept("meta-analysis"):
        return "Level A (provisional)"
    if has_concept("systematic review"):
        return "Level A (provisional)"
    if has_concept("randomized controlled trial"):
        return "Level B (provisional)"

    # Fall back to OpenAlex work_type when concept tags are absent.
    if type_lower in {"preprint", "posted-content"}:
        return "Level D (provisional)"
    if type_lower in {"book-chapter", "book"}:
        return "Level D (provisional)"
    if type_lower == "review":
        return "Level D (provisional)"
    if type_lower == "journal-article":
        # No concept-tag for SR / RCT / MA — default conservative.
        return "Level D (provisional)"
    if type_lower in {"conference-paper", "proceedings"}:
        return "Level D (provisional)"
    return "Unsupported (provisional)"


class OpenAlexSearcher:
    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_openalex_fetcher

    def search(
        self,
        query: str,
        *,
        since: Optional[str] = None,
        max_results: int = 10,
        open_access_only: bool = False,
    ) -> tuple[LiveOpenAlexHit, ...]:
        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        if since is not None and not _SINCE_RE.match(since):
            raise ValueError(f"--since must be YYYY-MM-DD; got {since!r}")

        try:
            preflight(query)
        except DiscoverRefused as exc:
            raise SearchRefused(reason=exc.reason, detail=exc.detail) from exc

        capped = min(max(1, int(max_results)), _MAX_RESULTS_CEILING)
        url = self._build_url(query, since, capped, open_access_only)
        body = self._fetcher(url)
        records = self._parse_payload(body)

        hits: list[LiveOpenAlexHit] = []
        for rec in records[:capped]:
            hit = self._record_to_hit(rec)
            if hit is not None:
                hits.append(hit)
        return tuple(hits)

    def _build_url(
        self,
        query: str,
        since: Optional[str],
        per_page: int,
        open_access_only: bool,
    ) -> str:
        params = {
            "search": query.strip(),
            "per_page": str(per_page),
            "sort": "publication_date:desc",
        }
        filters: list[str] = []
        if since is not None:
            filters.append(f"from_publication_date:{since}")
        if open_access_only:
            filters.append("is_oa:true")
        if filters:
            params["filter"] = ",".join(filters)
        return f"{_OPENALEX_WORKS_URL}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_payload(body: str) -> list[dict]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return []
        results = payload.get("results") or []
        return [r for r in results if isinstance(r, dict)]

    @staticmethod
    def _record_to_hit(rec: dict) -> Optional[LiveOpenAlexHit]:
        # OpenAlex IDs come as full URLs; strip to the W-id.
        raw_id = (rec.get("id") or "").strip()
        if not raw_id:
            return None
        openalex_id = raw_id.rsplit("/", 1)[-1]

        # DOI comes as full URL; strip the host.
        raw_doi = (rec.get("doi") or "").strip()
        doi = raw_doi
        if raw_doi.startswith("https://doi.org/"):
            doi = raw_doi[len("https://doi.org/"):]
        elif raw_doi.startswith("http://doi.org/"):
            doi = raw_doi[len("http://doi.org/"):]

        # PMID lives in ids.pmid as a full URL when present.
        pmid = ""
        ids_field = rec.get("ids") or {}
        if isinstance(ids_field, dict):
            raw_pmid = (ids_field.get("pmid") or "").strip()
            if raw_pmid:
                pmid = raw_pmid.rsplit("/", 1)[-1]

        title = (rec.get("title") or "").strip()
        year = rec.get("publication_year")
        if not isinstance(year, int):
            try:
                year = int(year) if year is not None else None
            except (TypeError, ValueError):
                year = None

        # First-author surname (split on whitespace, surname is last
        # word of display_name e.g. "Marta Di Forti" → "Forti", but
        # the EU-GEI authorships usually list "Di Forti M" with surname
        # already first. Use a conservative heuristic: take the last
        # alphabetic token, but if the display_name contains "Di "/"De "/
        # "Van " prefixes, take from the prefix.
        first_surname = ""
        authorships = rec.get("authorships") or []
        for a in authorships:
            if not isinstance(a, dict):
                continue
            if a.get("author_position") != "first":
                continue
            author = a.get("author") or {}
            name = (author.get("display_name") or "").strip()
            if name:
                tokens = name.split()
                # Detect compound surnames: "Di Forti M", "De Vita J".
                lowered = [t.lower() for t in tokens]
                for prefix in ("di", "de", "van", "von", "del", "la"):
                    if prefix in lowered:
                        idx = lowered.index(prefix)
                        first_surname = " ".join(tokens[idx : idx + 2])
                        break
                if not first_surname:
                    # Standard format "Smith J" — surname is first
                    # token (OpenAlex normalises to surname-first when
                    # known).
                    first_surname = tokens[0]
            break
        if not first_surname and authorships:
            # Fall back to first author regardless of position flag.
            first = authorships[0]
            if isinstance(first, dict):
                author = first.get("author") or {}
                name = (author.get("display_name") or "").strip()
                if name:
                    first_surname = name.split()[0]

        # Venue + open-access.
        venue = ""
        primary_location = rec.get("primary_location") or {}
        if isinstance(primary_location, dict):
            src = primary_location.get("source") or {}
            if isinstance(src, dict):
                venue = (src.get("display_name") or "").strip()
        is_oa = False
        oa = rec.get("open_access") or {}
        if isinstance(oa, dict):
            is_oa = bool(oa.get("is_oa"))

        work_type = (rec.get("type") or "").strip()

        # Top-3 concept tags by score (already sorted desc by OpenAlex).
        concept_names: list[str] = []
        concepts_field = rec.get("concepts") or []
        for c in concepts_field[:3]:
            if isinstance(c, dict):
                n = (c.get("display_name") or "").strip()
                if n:
                    concept_names.append(n)
        concepts = tuple(concept_names)

        cited = rec.get("cited_by_count") or 0
        try:
            cited = int(cited)
        except (TypeError, ValueError):
            cited = 0

        return LiveOpenAlexHit(
            openalex_id=openalex_id,
            doi=doi,
            pmid=pmid,
            title=title,
            first_author_surname=first_surname,
            year=year,
            venue=venue,
            work_type=work_type,
            concepts=concepts,
            cited_by_count=cited,
            is_open_access=is_oa,
            suggested_grade=suggested_grade_for_openalex_type(
                work_type, concepts,
            ),
            provenance=Provenance.LIVE_OPENALEX.value,
        )


def render_markdown(query: str, hits: tuple[LiveOpenAlexHit, ...]) -> str:
    lines: list[str] = [
        f"## Live OpenAlex search — {query}",
        "",
        "_Source: live OpenAlex Works API (open scholarly citation "
        "graph; PubMed + preprints + conference proceedings + open "
        "citation network). Each row is unverified by Cannavec; treat "
        "as a research lead, not as a settled claim. Suggested grades "
        "are provisional concept-tag / work-type heuristics; the "
        "verified grade lives in the curated registry only._",
        "",
    ]
    if not hits:
        lines.append("_No hits returned by OpenAlex for this query._")
        return "\n".join(lines) + "\n"

    lines.append(
        "| OpenAlex | Year | First author | Venue | Type | "
        "Cited-by | OA | Grade (provisional) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for h in hits:
        oa_flag = "✓" if h.is_open_access else ""
        link = (
            f"[{h.openalex_id}]"
            f"(https://openalex.org/works/{h.openalex_id})"
        )
        lines.append(
            f"| {link} "
            f"| {h.year or '—'} "
            f"| {h.first_author_surname or '—'} "
            f"| {h.venue or '—'} "
            f"| {h.work_type or '—'} "
            f"| {h.cited_by_count} "
            f"| {oa_flag} "
            f"| {h.suggested_grade} |"
        )
    return "\n".join(lines) + "\n"


def render_json(query: str, hits: tuple[LiveOpenAlexHit, ...]) -> str:
    return json.dumps(
        {
            "query": query,
            "hits": [h.to_dict() for h in hits],
            "provenance": Provenance.LIVE_OPENALEX.value,
        },
        indent=2,
        sort_keys=True,
    )
