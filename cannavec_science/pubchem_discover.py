"""Live PubChem PUG REST discovery — cannabinoid structures + properties.

Cannabis-primary-source widening: PubChem catalogs the canonical
phytocannabinoid structures and physical properties researchers cite
(Δ⁹-THC CID 16078, CBD CID 644019, THCA CID 98523, CBDA CID 12313961,
CBN CID 2543, CBG CID 5315659, THCV CID 93147, CBDV CID 12302124).
A structure-anchored claim that lacks a CID and InChIKey is, per
Constitution §I (Primary-Source-Or-Refuse), unsupported.

Endpoints used (PUG REST docs:
https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest):

- ``…/compound/name/{name}/cids/JSON``
  — resolve name → list of CIDs.
- ``…/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,
  CanonicalSMILES,IsomericSMILES,InChI,InChIKey,IUPACName,XLogP/JSON``
  — bundled property pull in one request.
- ``…/compound/cid/{cid}/synonyms/JSON``
  — synonyms / cross-references.

Every emitted row carries ``Provenance.LIVE_PUBCHEM`` and the suggested
grade ``Level D (provisional, live_pubchem)`` — PubChem is a structure
catalog, not a clinical evidence source, so an answer drawn purely from
PubChem cannot exceed Level D.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science._http import TIMEOUT_FAST, retry_urlopen, user_agent
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "PubChemCompoundRow",
    "PubChemSearcher",
    "NetworkError",
    "default_pubchem_fetcher",
    "render_markdown",
    "render_json",
]


_PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_NAME_TO_CIDS_URL = _PUG_BASE + "/compound/name/{name}/cids/JSON"
_CID_PROPERTY_URL = (
    _PUG_BASE
    + "/compound/cid/{cid}/property/"
    + "MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,"
    + "InChI,InChIKey,IUPACName,XLogP,HBondDonorCount,HBondAcceptorCount/JSON"
)
_CID_SYNONYMS_URL = _PUG_BASE + "/compound/cid/{cid}/synonyms/JSON"

_LANDING_URL = "https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"

_MAX_RESULTS_CEILING = 25

_SUGGESTED_GRADE = "Level D (provisional, live_pubchem)"


class NetworkError(Exception):
    """Raised when a PubChem fetch / parse fails after preflight passed."""


Fetcher = Callable[[str], str]


def default_pubchem_fetcher(url: str) -> str:
    """Production fetcher — polite UA, JSON Accept, fast timeout, bounded retry."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent("pubchem-discover"),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_FAST) as resp:
        return resp.read().decode("utf-8")


@dataclass(frozen=True)
class PubChemCompoundRow:
    cid: int
    name_query: str
    iupac_name: Optional[str]
    molecular_formula: Optional[str]
    molecular_weight: Optional[float]
    canonical_smiles: Optional[str]
    isomeric_smiles: Optional[str]
    inchi: Optional[str]
    inchikey: Optional[str]
    xlogp: Optional[float]
    hbond_donors: Optional[int]
    hbond_acceptors: Optional[int]
    synonyms: tuple[str, ...]
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_PUBCHEM
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", f"CID:{self.cid}")
        if not self.title:
            label = self.iupac_name or self.name_query or self.native_id
            object.__setattr__(self, "title", label)
        if not self.url:
            object.__setattr__(
                self, "url", _LANDING_URL.format(cid=self.cid)
            )
        if not self.citation:
            object.__setattr__(
                self,
                "citation",
                f"PubChem CID {self.cid} ({self.inchikey or 'no-InChIKey'})",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["synonyms"] = list(self.synonyms)
        return d


class PubChemSearcher:
    """Live PubChem search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_pubchem_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[PubChemCompoundRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        cids = self._resolve_cids(query)
        if not cids:
            return []

        rows: list[PubChemCompoundRow] = []
        for cid in cids[:max_results]:
            row = self._build_row(query, cid)
            if row is not None:
                rows.append(row)
        return rows

    def _resolve_cids(self, query: str) -> list[int]:
        q = query.strip()
        if q.lower().startswith("cid:") and q[4:].strip().isdigit():
            return [int(q[4:].strip())]
        if q.isdigit():
            return [int(q)]
        url = _NAME_TO_CIDS_URL.format(name=urllib.parse.quote(q))
        data = self._fetch_json(url)
        cids = (data.get("IdentifierList") or {}).get("CID") or []
        out: list[int] = []
        for c in cids:
            try:
                out.append(int(c))
            except (TypeError, ValueError):
                continue
        return out

    def _build_row(self, query: str, cid: int) -> Optional[PubChemCompoundRow]:
        prop_url = _CID_PROPERTY_URL.format(cid=cid)
        prop_data = self._fetch_json(prop_url)
        props = (
            (prop_data.get("PropertyTable") or {}).get("Properties") or []
        )
        if not props:
            return None
        p = props[0]

        syn_url = _CID_SYNONYMS_URL.format(cid=cid)
        try:
            syn_data = self._fetch_json(syn_url)
        except NetworkError:
            syn_data = {}
        syn_block = (syn_data.get("InformationList") or {}).get(
            "Information"
        ) or []
        synonyms = tuple(
            (syn_block[0].get("Synonym") or [])[:10]
        ) if syn_block else ()

        return PubChemCompoundRow(
            cid=cid,
            name_query=query,
            iupac_name=p.get("IUPACName"),
            molecular_formula=p.get("MolecularFormula"),
            molecular_weight=_to_float(p.get("MolecularWeight")),
            canonical_smiles=p.get("CanonicalSMILES"),
            isomeric_smiles=p.get("IsomericSMILES"),
            inchi=p.get("InChI"),
            inchikey=p.get("InChIKey"),
            xlogp=_to_float(p.get("XLogP")),
            hbond_donors=_to_int(p.get("HBondDonorCount")),
            hbond_acceptors=_to_int(p.get("HBondAcceptorCount")),
            synonyms=synonyms,
        )

    def _fetch_json(self, url: str) -> dict:
        try:
            body = self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(f"fetch failed: {url}: {exc}") from exc
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NetworkError(
                f"PubChem response is not valid JSON for {url}: {exc}"
            ) from exc


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


def render_markdown(query: str, rows: list[PubChemCompoundRow]) -> str:
    lines: list[str] = []
    lines.append(f"## PubChem (live_pubchem, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No PubChem compound resolved for this query._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **CID {r.cid}** {r.iupac_name or r.name_query}"
        if r.molecular_formula:
            head += f"  \n  Formula: {r.molecular_formula}"
            if r.molecular_weight is not None:
                head += f" ({r.molecular_weight:g} g/mol)"
        if r.inchikey:
            head += f"  \n  InChIKey: `{r.inchikey}`"
        if r.xlogp is not None:
            head += f"  \n  XLogP: {r.xlogp:g}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[PubChemCompoundRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_PUBCHEM.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
