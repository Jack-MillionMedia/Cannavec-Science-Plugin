"""Live medRxiv discovery (spec 002 US1).

Identical Tier-3 contract to ``biorxiv_discover.py``; medRxiv uses
the same Cold Spring Harbor preprint API, so this module subclasses
the bioRxiv searcher and overrides the server-name + URL templates.

The two preprint lanes are kept as separate modules — not merged
into one — because the cross-source synthesis verdict
(``synthesis.py``) counts them as distinct sources, and the
``commands/discover.md`` slash-command documents them separately.
"""

from __future__ import annotations

import datetime
import json
import urllib.parse
from typing import Optional

from cannavec_science._preprint_helpers import (
    NetworkError,
    PREPRINT_GRADE_CEILING,
    PreprintFetcher,
    PreprintRow,
    default_preprint_fetcher,
    lookup_published_version,
    parse_collection_payload,
    parse_doi,
)
from cannavec_science.discover_guard import DiscoverRefused, preflight


__all__ = [
    "MedRxivSearcher",
    "PreprintRow",
    "NetworkError",
    "default_medrxiv_fetcher",
    "render_markdown",
    "render_json",
]


_MEDRXIV_DETAILS_URL = (
    "https://api.medrxiv.org/details/medrxiv/{ident}/na/json"
)
_MEDRXIV_DATE_RANGE_URL = (
    "https://api.medrxiv.org/details/medrxiv/{since}/{until}/0/json"
)


def default_medrxiv_fetcher(url: str) -> str:
    return default_preprint_fetcher(url)


class MedRxivSearcher:
    server: str = "medrxiv"

    def __init__(
        self,
        *,
        fetcher: Optional[PreprintFetcher] = None,
        crossref_fetcher: Optional[PreprintFetcher] = None,
    ) -> None:
        self._fetcher = fetcher or default_medrxiv_fetcher
        self._crossref_fetcher = crossref_fetcher

    def search(
        self,
        query: str,
        *,
        since: Optional[str] = None,
        max_results: int = 10,
    ) -> list[PreprintRow]:
        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        if not 1 <= max_results <= 50:
            raise ValueError(f"max_results must be in [1, 50]; got {max_results}")

        preflight(query)

        parsed_doi = parse_doi(query.strip())
        if parsed_doi is not None:
            canonical, _ = parsed_doi
            return self._search_by_doi(canonical, max_results)
        return self._search_by_keyword(query, since=since, max_results=max_results)

    def _search_by_doi(self, doi: str, max_results: int) -> list[PreprintRow]:
        url = _MEDRXIV_DETAILS_URL.format(ident=urllib.parse.quote(doi))
        rows = self._fetch_and_parse(url)
        return self._enrich(rows)[:max_results]

    def _search_by_keyword(
        self,
        query: str,
        *,
        since: Optional[str],
        max_results: int,
    ) -> list[PreprintRow]:
        until = datetime.date.today().isoformat()
        if since:
            since_date = since
        else:
            since_date = (
                datetime.date.today() - datetime.timedelta(days=30)
            ).isoformat()
        url = _MEDRXIV_DATE_RANGE_URL.format(since=since_date, until=until)
        rows = self._fetch_and_parse(url)
        keyword_lower = query.lower()
        filtered = [
            r for r in rows
            if keyword_lower in r.title.lower()
            or keyword_lower in r.abstract.lower()
            or (r.category and keyword_lower in r.category.lower())
        ]
        if not filtered:
            tokens = [t for t in keyword_lower.split() if len(t) >= 4]
            if tokens:
                filtered = [
                    r for r in rows
                    if any(
                        t in r.title.lower() or t in r.abstract.lower()
                        for t in tokens
                    )
                ]
        return self._enrich(filtered)[:max_results]

    def _fetch_and_parse(self, url: str) -> tuple[PreprintRow, ...]:
        try:
            body = self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:  # noqa: BLE001
            raise NetworkError(f"fetch failed: {url}: {exc}") from exc
        return parse_collection_payload(self.server, body)

    def _enrich(self, rows: tuple[PreprintRow, ...]) -> list[PreprintRow]:
        enriched: list[PreprintRow] = []
        for r in rows:
            if r.published_version_doi:
                enriched.append(r)
                continue
            if self._crossref_fetcher is not None:
                try:
                    pub_doi = lookup_published_version(
                        r.doi, fetcher=self._crossref_fetcher,
                    )
                except Exception:
                    pub_doi = None
                if pub_doi:
                    enriched.append(
                        PreprintRow(
                            server=r.server, doi=r.doi, title=r.title,
                            abstract=r.abstract, authors=r.authors,
                            posted_date=r.posted_date,
                            revision_number=r.revision_number,
                            version_history=r.version_history,
                            published_version_doi=pub_doi,
                            license=r.license, category=r.category,
                            suggested_grade=r.suggested_grade,
                        )
                    )
                    continue
            enriched.append(r)
        return enriched


def render_markdown(query: str, rows: list[PreprintRow]) -> str:
    lines: list[str] = []
    lines.append(f"## medRxiv (live_medrxiv, preprint — not peer-reviewed) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No preprints matched in medRxiv for this query._")
        return "\n".join(lines)
    for r in rows:
        line = (
            f"- **doi:{r.doi}** ({r.posted_date}) {r.title}"
        )
        if r.revision_number > 1:
            line += f" — v{r.revision_number}"
        if r.published_version_doi:
            line += f" → published as doi:{r.published_version_doi}"
        line += "  \n  Authors: " + ", ".join(r.authors[:4])
        if len(r.authors) > 4:
            line += f", +{len(r.authors) - 4} more"
        line += f"  \n  Suggested grade: {r.suggested_grade}"
        lines.append(line)
    return "\n".join(lines)


def render_json(query: str, rows: list[PreprintRow]) -> str:
    payload = {
        "query": query,
        "provenance": "live_medrxiv",
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
