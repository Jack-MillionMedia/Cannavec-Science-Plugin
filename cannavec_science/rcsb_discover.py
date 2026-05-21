"""Live RCSB Protein Data Bank discovery — cannabinoid-receptor structures.

Cannabis-primary-source widening: a researcher claiming "Δ⁹-THC binds
CB1" should be able to cite the corresponding solved structure (PDB
6N4B — CB1 with agonist AM11542, PDB 6PT0 — CB2 with WIN-55,212-2,
etc.). RCSB PDB provides the canonical 3D atomic structures used in
cannabinoid pharmacology and rational ligand design.

The Search API is full-text + structured-query JSON; this discoverer
issues a narrow full-text query and resolves each hit through the
core-entry metadata endpoint so the row carries title, deposition
date, resolution, method, and source organism.

Endpoints used (https://search.rcsb.org / https://data.rcsb.org):

- POST ``https://search.rcsb.org/rcsbsearch/v2/query``
  — full-text search returning a list of PDB IDs.
- GET  ``https://data.rcsb.org/rest/v1/core/entry/{pdb_id}``
  — entry metadata.

Every emitted row carries ``Provenance.LIVE_RCSB`` and the suggested
grade ``Level C (provisional, live_rcsb)`` — a crystal structure is
mechanistic evidence; alone it cannot upgrade a clinical efficacy
claim past Level C without independent functional / clinical anchoring.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "RCSBEntryRow",
    "RCSBSearcher",
    "NetworkError",
    "default_rcsb_fetcher",
    "render_markdown",
    "render_json",
]


_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
_PUBLIC_URL = "https://www.rcsb.org/structure/{pdb_id}"

_DEFAULT_TIMEOUT = 10
_MAX_RESULTS_CEILING = 25

_SUGGESTED_GRADE = "Level C (provisional, live_rcsb)"


class NetworkError(Exception):
    """Raised when an RCSB fetch / parse fails after preflight passed."""


# Fetcher signature: GET takes a URL; POST takes a (url, body_bytes).
# A single fetcher protocol keeps the offline-test surface symmetrical
# with the other discoverers — the stub maps URLs to canned bodies and
# is invoked the same way whether method=GET or POST.
Fetcher = Callable[..., str]


def default_rcsb_fetcher(url: str, *, body: Optional[bytes] = None) -> str:
    """Production fetcher — GET if body is None, POST otherwise."""
    headers = {
        "User-Agent": "cannavec-rcsb-discover/1.0",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


@dataclass(frozen=True)
class RCSBEntryRow:
    pdb_id: str
    query: str
    title: str
    deposit_date: Optional[str]
    release_date: Optional[str]
    experimental_method: Optional[str]
    resolution_angstrom: Optional[float]
    polymer_entity_count: Optional[int]
    source_organisms: tuple[str, ...]
    primary_citation_pmid: Optional[str]
    primary_citation_doi: Optional[str]
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_RCSB
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", self.pdb_id)
        if not self.url:
            object.__setattr__(
                self, "url", _PUBLIC_URL.format(pdb_id=self.pdb_id)
            )
        if not self.citation:
            ident = self.primary_citation_pmid or self.primary_citation_doi
            if ident:
                tag = "PMID" if self.primary_citation_pmid else "DOI"
                object.__setattr__(
                    self, "citation", f"PDB {self.pdb_id} ({tag} {ident})"
                )
            else:
                object.__setattr__(
                    self, "citation", f"PDB {self.pdb_id}"
                )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["source_organisms"] = list(self.source_organisms)
        return d


class RCSBSearcher:
    """Live RCSB PDB search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_rcsb_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[RCSBEntryRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        q = query.strip()
        # Direct PDB ID lookup short-circuits the search API.
        if len(q) == 4 and q.isalnum():
            row = self._fetch_entry(q.upper(), query)
            return [row] if row is not None else []

        pdb_ids = self._search_ids(q, max_results)
        rows: list[RCSBEntryRow] = []
        for pid in pdb_ids[:max_results]:
            row = self._fetch_entry(pid, query)
            if row is not None:
                rows.append(row)
        return rows

    def _search_ids(self, query: str, max_results: int) -> list[str]:
        body = json.dumps({
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": query},
            },
            "return_type": "entry",
            "request_options": {
                "pager": {"start": 0, "rows": max_results},
                "sort": [
                    {"sort_by": "score", "direction": "desc"}
                ],
            },
        }).encode("utf-8")
        raw = self._post(_SEARCH_URL, body)
        data = _safe_json(raw, _SEARCH_URL)
        result_set = data.get("result_set") or []
        return [r.get("identifier") for r in result_set if r.get("identifier")]

    def _fetch_entry(
        self, pdb_id: str, query: str,
    ) -> Optional[RCSBEntryRow]:
        url = _ENTRY_URL.format(pdb_id=pdb_id)
        raw = self._get(url)
        if not raw:
            return None
        data = _safe_json(raw, url)
        return _parse_entry(pdb_id, query, data)

    def _get(self, url: str) -> str:
        try:
            return self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(f"GET failed: {url}: {exc}") from exc

    def _post(self, url: str, body: bytes) -> str:
        try:
            return self._fetcher(url, body=body)
        except TypeError:
            # Fetcher stubs that ignore `body=` kwarg still work; the
            # body-bytes argument is informative only when the stub
            # dispatches on URL.
            try:
                return self._fetcher(url)
            except DiscoverRefused:
                raise
            except Exception as exc:
                raise NetworkError(f"POST failed: {url}: {exc}") from exc
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(f"POST failed: {url}: {exc}") from exc


def _safe_json(raw: str, url: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise NetworkError(
            f"RCSB response is not valid JSON for {url}: {exc}"
        ) from exc


def _parse_entry(pdb_id: str, query: str, data: dict) -> RCSBEntryRow:
    struct = data.get("struct") or {}
    rcsb_entry_info = data.get("rcsb_entry_info") or {}
    exptl = (data.get("exptl") or [{}])[0] or {}
    refine = (data.get("refine") or [{}])[0] or {}
    accession_info = data.get("rcsb_accession_info") or {}

    title = struct.get("title") or ""

    citations = data.get("citation") or []
    pmid = None
    doi = None
    for c in citations:
        if (c.get("id") or "").lower() == "primary":
            pmid = c.get("pdbx_database_id_pub_med")
            doi = c.get("pdbx_database_id_doi")
            break
    if pmid is None and citations:
        pmid = citations[0].get("pdbx_database_id_pub_med")
        doi = citations[0].get("pdbx_database_id_doi")

    organisms = data.get("rcsb_entry_container_identifiers", {})
    organism_names = []
    for src in data.get("entity_src_gen") or []:
        name = src.get("pdbx_gene_src_scientific_name") or src.get(
            "gene_src_common_name"
        )
        if name:
            organism_names.append(name)
    # Fallback to organism_scientific on entity_src_nat.
    for src in data.get("entity_src_nat") or []:
        name = src.get("pdbx_organism_scientific")
        if name:
            organism_names.append(name)

    resolution = None
    if "resolution_combined" in rcsb_entry_info:
        res = rcsb_entry_info.get("resolution_combined") or []
        if res:
            try:
                resolution = float(res[0])
            except (TypeError, ValueError):
                resolution = None
    if resolution is None and refine.get("ls_d_res_high"):
        try:
            resolution = float(refine["ls_d_res_high"])
        except (TypeError, ValueError):
            resolution = None

    return RCSBEntryRow(
        pdb_id=pdb_id.upper(),
        query=query,
        title=title,
        deposit_date=accession_info.get("deposit_date"),
        release_date=accession_info.get("initial_release_date"),
        experimental_method=exptl.get("method"),
        resolution_angstrom=resolution,
        polymer_entity_count=rcsb_entry_info.get(
            "polymer_entity_count"
        ),
        source_organisms=tuple(sorted(set(organism_names))),
        primary_citation_pmid=str(pmid) if pmid is not None else None,
        primary_citation_doi=str(doi) if doi else None,
    )


def render_markdown(query: str, rows: list[RCSBEntryRow]) -> str:
    lines: list[str] = []
    lines.append(f"## RCSB PDB (live_rcsb, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No PDB entries matched this query._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **{r.pdb_id}** — {r.title or 'untitled'}"
        if r.experimental_method:
            head += f"  \n  Method: {r.experimental_method}"
            if r.resolution_angstrom is not None:
                head += f" ({r.resolution_angstrom:g} Å)"
        if r.source_organisms:
            head += f"  \n  Source: {', '.join(r.source_organisms[:3])}"
        if r.primary_citation_pmid:
            head += f"  \n  Primary PMID: {r.primary_citation_pmid}"
        elif r.primary_citation_doi:
            head += f"  \n  Primary DOI: {r.primary_citation_doi}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[RCSBEntryRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_RCSB.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
