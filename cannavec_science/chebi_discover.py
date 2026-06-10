"""Live ChEBI 2.0 discovery — curated chemical ontology for cannabinoids.

Spec 029 P1. Mirrors the ``pubchem_discover`` pattern: stdlib-only
``urllib`` transport, injected ``Fetcher`` for offline tests, safety +
banned-pattern preflight via ``discover_guard`` BEFORE any network call.

Where PubChem catalogs *structure* and ChEMBL catalogs *bioactivity*, ChEBI
(Chemical Entities of Biological Interest, EBI) catalogs *meaning*: a
manually-curated definition, a role ontology (``antimicrobial agent``,
``psychotropic drug``, ``cannabinoid receptor agonist`` …), a curation-quality
star rating, secondary identifiers, cross-database accessions, and — uniquely —
``compound_origins`` naming the **source species** (``Cannabis sativa``). That
botanical provenance and role classification are the phytochemistry context
(Constitution §VI) the other chemical lanes cannot supply.

ChEBI 2.0 backend REST endpoints used (verified live 2026-06-04):

- ``…/chebi/backend/api/public/es_search/?term={q}&size={n}``
  — free-text resolve name → ``{"results":[{"_id","_source":{"chebi_accession"}}]}``.
- ``…/chebi/backend/api/public/compound/{accession}/``
  — the curated record (definition, stars, chemical_data, roles_classification,
  compound_origins, database_accessions, secondary_ids).

Every emitted row carries ``Provenance.LIVE_CHEBI`` and the suggested grade
``Level D (provisional, live_chebi)`` — an ontology record is curated context,
not clinical evidence, so an answer drawn purely from ChEBI cannot exceed
Level D (§VII). Rows never auto-promote to the curated tier (§IX).
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science._http import NetworkError, TIMEOUT_FAST, make_json_fetcher
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "ChEBICompoundRow",
    "ChEBISearcher",
    "NetworkError",
    "default_chebi_fetcher",
    "render_markdown",
    "render_json",
]


_CHEBI_BASE = "https://www.ebi.ac.uk/chebi/backend/api/public"
_SEARCH_URL = _CHEBI_BASE + "/es_search/?term={term}&size={size}"
_COMPOUND_URL = _CHEBI_BASE + "/compound/{accession}/"
_LANDING_URL = "https://www.ebi.ac.uk/chebi/searchId.do?chebiId={accession}"

_MAX_RESULTS_CEILING = 25
_MAX_XREFS = 6

_SUGGESTED_GRADE = "Level D (provisional, live_chebi)"

_ACCESSION_RE = re.compile(r"^chebi:(\d+)$", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


Fetcher = Callable[[str], str]


default_chebi_fetcher = make_json_fetcher("chebi-discover", timeout=TIMEOUT_FAST)


@dataclass(frozen=True)
class ChEBICompoundRow:
    chebi_id: str
    name_query: str
    chebi_name: str
    definition: Optional[str]
    stars: Optional[int]
    formula: Optional[str]
    mass: Optional[float]
    charge: Optional[int]
    roles: tuple[str, ...]
    cannabis_origin: bool
    origin_species: tuple[str, ...]
    secondary_ids: tuple[str, ...]
    xrefs: tuple[str, ...]
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_CHEBI
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", self.chebi_id)
        if not self.title:
            object.__setattr__(
                self, "title", self.chebi_name or self.name_query or self.chebi_id
            )
        if not self.url:
            object.__setattr__(
                self, "url", _LANDING_URL.format(accession=self.chebi_id)
            )
        if not self.citation:
            object.__setattr__(
                self,
                "citation",
                f"ChEBI {self.chebi_id} ({self.chebi_name or self.name_query})",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["roles"] = list(self.roles)
        d["origin_species"] = list(self.origin_species)
        d["secondary_ids"] = list(self.secondary_ids)
        d["xrefs"] = list(self.xrefs)
        return d


class ChEBISearcher:
    """Live ChEBI search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_chebi_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[ChEBICompoundRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        accessions = self._resolve_accessions(query, max_results)
        rows: list[ChEBICompoundRow] = []
        for accession in accessions[:max_results]:
            row = self._build_row(query, accession)
            if row is not None:
                rows.append(row)
        return rows

    def _resolve_accessions(self, query: str, max_results: int) -> list[str]:
        q = query.strip()
        m = _ACCESSION_RE.match(q)
        if m:
            return [f"CHEBI:{m.group(1)}"]
        if q.isdigit():
            return [f"CHEBI:{q}"]
        url = _SEARCH_URL.format(
            term=urllib.parse.quote(q), size=max_results
        )
        data = self._fetch_json(url)
        out: list[str] = []
        for hit in (data.get("results") or []):
            src = hit.get("_source") or {}
            acc = src.get("chebi_accession") or (
                f"CHEBI:{hit['_id']}" if hit.get("_id") else None
            )
            if acc and acc not in out:
                out.append(acc)
        return out

    def _build_row(self, query: str, accession: str) -> Optional[ChEBICompoundRow]:
        data = self._fetch_json(_COMPOUND_URL.format(accession=accession))
        if not data.get("chebi_accession"):
            return None
        chebi_id = data["chebi_accession"]

        chem = data.get("chemical_data") or {}
        roles = _dedup(
            r.get("name") for r in (data.get("roles_classification") or [])
        )
        species = _dedup(
            o.get("species_text") for o in (data.get("compound_origins") or [])
        )
        cannabis_origin = any("cannabis" in s.lower() for s in species)

        return ChEBICompoundRow(
            chebi_id=chebi_id,
            name_query=query,
            chebi_name=_clean_text(data.get("name") or data.get("ascii_name") or ""),
            definition=_clean_text(data.get("definition")) or None,
            stars=_to_int(data.get("stars")),
            formula=chem.get("formula") or None,
            mass=_to_float(chem.get("mass")),
            charge=_to_int(chem.get("charge")),
            roles=tuple(roles),
            cannabis_origin=cannabis_origin,
            origin_species=tuple(species),
            secondary_ids=tuple(data.get("secondary_ids") or ()),
            xrefs=_flatten_xrefs(data.get("database_accessions")),
        )

    def _fetch_json(self, url: str) -> dict:
        try:
            body = self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(f"fetch failed: {url}: {exc}") from exc
        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NetworkError(
                f"ChEBI response is not valid JSON for {url}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise NetworkError(f"ChEBI response is not a JSON object for {url}")
        return parsed


def _clean_text(text) -> str:
    """Strip ChEBI's inline HTML markup (``Δ<small><sup>9</small></sup>-…``,
    and the ``<stereo>`` / entity markup that appears in definitions) so the
    field renders cleanly as plain text (Constitution §VI)."""
    if not text:
        return ""
    return html.unescape(_HTML_TAG_RE.sub("", str(text))).strip()


def _dedup(values) -> list[str]:
    """Order-preserving de-dup as plain strings, dropping empty / None."""
    out: list[str] = []
    for v in values:
        if not v:
            continue
        s = v.strip() if isinstance(v, str) else str(v)
        if s and s not in out:
            out.append(s)
    return out


def _flatten_xrefs(db_accessions) -> tuple[str, ...]:
    """``{"CAS":[{"accession_number":...}]}`` → ``("CAS:13956-29-1", …)``."""
    if not isinstance(db_accessions, dict):
        return ()
    out: list[str] = []
    for db_type, entries in db_accessions.items():
        for e in (entries or []):
            acc = e.get("accession_number") if isinstance(e, dict) else None
            if acc:
                out.append(f"{db_type}:{acc}")
            if len(out) >= _MAX_XREFS:
                return tuple(out)
    return tuple(out)


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def render_markdown(query: str, rows: list[ChEBICompoundRow]) -> str:
    lines: list[str] = []
    lines.append(f"## ChEBI (live_chebi, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No ChEBI entity resolved for this query._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **{r.chebi_id}** {r.chebi_name}"
        if r.stars:
            head += f" ({r.stars}★ curated)"
        if r.formula:
            head += f"  \n  Formula: {r.formula}"
            if r.mass is not None:
                head += f" ({r.mass:g} g/mol)"
        if r.cannabis_origin:
            head += f"  \n  Origin: {', '.join(r.origin_species)}"
        if r.roles:
            head += f"  \n  Roles: {', '.join(r.roles)}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[ChEBICompoundRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_CHEBI.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
