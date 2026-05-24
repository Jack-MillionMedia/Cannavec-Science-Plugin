"""Shared preprint-server helpers (spec 002 US1).

Both bioRxiv and medRxiv expose the same Cold Spring Harbor preprint
server API (``api.biorxiv.org`` / ``api.medrxiv.org``) with identical
response shapes — they differ only in the server hostname. This
module owns the shared bits: DOI shape validation, version-history
extraction, published-version cross-reference via Crossref.

Stdlib only — ``urllib`` transport, ``json`` parsing, no third-party
deps. Per Constitution §X.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from cannavec_science._http import TIMEOUT_SLOW, retry_urlopen, user_agent


__all__ = [
    "PreprintRow",
    "PreprintFetcher",
    "default_preprint_fetcher",
    "parse_doi",
    "parse_collection_payload",
    "lookup_published_version",
    "NetworkError",
    "PREPRINT_GRADE_CEILING",
]


# Level D cap per FR-202: preprints are not peer-reviewed.
PREPRINT_GRADE_CEILING: str = "Level D (provisional, preprint)"


# ── DOI helpers ──────────────────────────────────────────────────────


_BIORXIV_DOI_RE = re.compile(
    r"^10\.1101/\d{4}\.\d{2}\.\d{2}\.\d{6}(?:v\d+)?$",
    re.IGNORECASE,
)


def parse_doi(doi: str) -> Optional[tuple[str, Optional[int]]]:
    """Parse a bioRxiv/medRxiv DOI.

    Returns ``(canonical_doi, version_number_or_None)`` on a valid
    shape, or ``None`` for an unparseable string. The canonical DOI
    is the version-stripped form so cross-version comparisons hash
    on one identifier.
    """
    if not doi:
        return None
    raw = doi.strip().lower()
    if raw.startswith("https://doi.org/"):
        raw = raw[len("https://doi.org/"):]
    if raw.startswith("doi:"):
        raw = raw[4:]
    m = _BIORXIV_DOI_RE.match(raw)
    if not m:
        return None
    base = re.sub(r"v\d+$", "", raw)
    version = None
    vm = re.search(r"v(\d+)$", raw)
    if vm:
        try:
            version = int(vm.group(1))
        except ValueError:
            version = None
    return base, version


# ── Network ──────────────────────────────────────────────────────────


class NetworkError(Exception):
    """Raised when a preprint fetch fails."""


PreprintFetcher = Callable[[str], str]


def default_preprint_fetcher(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent("preprint-discover"),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_SLOW) as resp:
        raw = resp.read()
    return raw.decode("utf-8")


# ── Row dataclass ────────────────────────────────────────────────────


@dataclass(frozen=True)
class PreprintRow:
    """One bioRxiv / medRxiv row.

    Fields are normalised across the two preprint servers so the
    rest of the pipeline (synthesis, answer composer, render layer)
    only needs to switch on the ``provenance`` tag.
    """

    server: str                       # "biorxiv" | "medrxiv"
    doi: str                          # canonical DOI without `vN` suffix
    title: str
    abstract: str
    authors: tuple[str, ...]
    posted_date: str                  # ISO YYYY-MM-DD
    revision_number: int              # latest version
    version_history: tuple[dict, ...]  # [{"version": int, "date": str}, ...]
    published_version_doi: Optional[str] = None
    license: Optional[str] = None
    category: Optional[str] = None
    suggested_grade: str = PREPRINT_GRADE_CEILING
    provenance: str = ""              # populated by parse_collection_payload
    url: str = ""
    citation: str = ""
    native_id: str = ""

    def __post_init__(self) -> None:
        # Self-fill derived defaults — frozen dataclass requires
        # object.__setattr__.
        if not self.provenance:
            object.__setattr__(self, "provenance", f"live_{self.server}")
        if not self.url:
            object.__setattr__(
                self, "url", f"https://www.{self.server}.org/content/{self.doi}",
            )
        if not self.citation:
            year = (self.posted_date or "?")[:4]
            first_author = self.authors[0] if self.authors else "anonymous"
            object.__setattr__(
                self, "citation",
                f"{first_author}, {self.server}.org {year}, doi:{self.doi}",
            )
        if not self.native_id:
            object.__setattr__(self, "native_id", self.doi)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["authors"] = list(self.authors)
        d["version_history"] = [dict(v) for v in self.version_history]
        return d


# ── Collection payload parsing ───────────────────────────────────────


def parse_collection_payload(
    server: str,
    body: str,
) -> tuple[PreprintRow, ...]:
    """Parse a bioRxiv/medRxiv ``/details/<server>/<doi>`` or
    ``/details/<server>/<date-range>`` response into rows.

    Both endpoints return JSON in the shape::

        {"messages": [{"status": "ok"}], "collection": [
            {"doi": "10.1101/...", "title": "...", "abstract": "...",
             "authors": "Author A; Author B", "date": "YYYY-MM-DD",
             "version": "2", "published": "10.1xxx/...", ...},
            ...
        ]}

    The ``collection`` array is per-version; we group by DOI and pick
    the latest version per group (highest ``version``).
    """
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise NetworkError(f"preprint response is not JSON: {exc}") from exc
    raw = payload.get("collection") or []
    if not raw:
        return ()

    by_doi: dict[str, list[dict]] = {}
    for entry in raw:
        doi = (entry.get("doi") or "").strip().lower()
        if not doi:
            continue
        by_doi.setdefault(doi, []).append(entry)

    out: list[PreprintRow] = []
    for doi, versions in by_doi.items():
        # Sort by version number ascending; the latest is the rendered row.
        def _vnum(e: dict) -> int:
            try:
                return int(e.get("version") or 1)
            except (TypeError, ValueError):
                return 1
        versions_sorted = sorted(versions, key=_vnum)
        latest = versions_sorted[-1]
        history = tuple(
            {
                "version": _vnum(v),
                "date": (v.get("date") or "").strip(),
            }
            for v in versions_sorted
        )
        authors_raw = (latest.get("authors") or "").strip()
        if authors_raw:
            authors = tuple(a.strip() for a in authors_raw.split(";") if a.strip())
        else:
            authors = ()
        published = (latest.get("published") or "").strip().lower()
        if published in ("na", "none", "null", ""):
            published_doi = None
        else:
            published_doi = published
        out.append(PreprintRow(
            server=server,
            doi=doi,
            title=(latest.get("title") or "").strip(),
            abstract=(latest.get("abstract") or "").strip(),
            authors=authors,
            posted_date=(latest.get("date") or "").strip(),
            revision_number=_vnum(latest),
            version_history=history,
            published_version_doi=published_doi,
            license=latest.get("license") or None,
            category=latest.get("category") or None,
        ))
    # Stable order: newest posted_date first, then DOI ascending.
    out.sort(key=lambda r: (r.posted_date or "", r.doi), reverse=True)
    return tuple(out)


# ── Published-version cross-reference (Crossref) ─────────────────────


def lookup_published_version(
    preprint_doi: str,
    *,
    fetcher: Optional[PreprintFetcher] = None,
) -> Optional[str]:
    """Resolve the peer-reviewed DOI for a preprint via Crossref.

    Returns the published DOI string, or None when the preprint has
    not been peer-reviewed yet OR the Crossref relation cannot be
    resolved. Crossref exposes a ``is-preprint-of`` relation; we
    walk the ``/works/{doi}`` response's ``relation`` field.
    """
    if not preprint_doi:
        return None
    parsed = parse_doi(preprint_doi)
    if parsed is None:
        return None
    canonical, _ = parsed
    url = f"https://api.crossref.org/works/{urllib.parse.quote(canonical)}"
    fetch = fetcher or default_preprint_fetcher
    try:
        body = fetch(url)
    except (urllib.error.URLError, OSError, Exception):
        return None
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if payload.get("status") != "ok":
        return None
    relation = (payload.get("message") or {}).get("relation") or {}
    for rel_name in ("is-preprint-of", "has-version", "is-version-of"):
        for entry in relation.get(rel_name, []) or []:
            ident = entry.get("id")
            if ident and ident.lower() != canonical:
                return ident.lower()
    return None
