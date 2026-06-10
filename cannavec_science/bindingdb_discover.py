"""Live BindingDB discovery — measured cannabinoid → receptor affinities.

Cannabis-primary-source widening: BindingDB curates measured Ki / Kd /
IC50 / EC50 / pKi / pIC50 affinities for protein-ligand pairs. It
complements ChEMBL by surfacing affinity rows that bypass the ChEMBL
deposition / curation lag and by exposing similarity-search by SMILES.

For a cannabis researcher the highest-yield BindingDB workflows are:

- ``getLigandsByUniprots`` — every ligand whose affinity was measured
  against CB1 (P21554) or CB2 (P34972).
- ``getLigandsByPDBs`` — ligands measured against any structure that
  shares > 92% identity with a given PDB code (useful when the user
  starts from a cannabinoid-receptor crystal structure).

Both endpoints return JSON when ``response=application/json`` is set.

Every emitted row carries ``Provenance.LIVE_BINDINGDB`` and the
suggested grade ``Level C (provisional, live_bindingdb)`` — a single
binding measurement is mechanistic; aggregating multiple rows still
caps at Level C without clinical anchoring (Constitution §VII).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science._http import NetworkError, TIMEOUT_SLOW, make_json_fetcher
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "BindingDBRow",
    "BindingDBSearcher",
    "NetworkError",
    "default_bindingdb_fetcher",
    "render_markdown",
    "render_json",
]


_BDB_BASE = "https://bindingdb.org"
_BY_UNIPROT_URL = (
    _BDB_BASE
    + "/rest/getLigandsByUniprots"
    + "?uniprot={uniprot}&cutoff={cutoff}&response=application/json"
)
_BY_PDB_URL = (
    _BDB_BASE
    + "/rest/getLigandsByPDBs"
    + "?pdb={pdb}&cutoff={cutoff}&identity={identity}"
    + "&response=application/json"
)

_PUBLIC_LIGAND_URL = (
    "https://www.bindingdb.org/bind/chemsearch/marvin/MolStructure.jsp"
    "?monomerid={monomer_id}"
)

_MAX_RESULTS_CEILING = 50

_SUGGESTED_GRADE = "Level C (provisional, live_bindingdb)"

# Cannabis-receptor UniProt shortcuts, mirroring the rest of the codebase.
_CANNABIS_UNIPROTS = {
    "cb1": "P21554",
    "cnr1": "P21554",
    "cb2": "P34972",
    "cnr2": "P34972",
    "trpv1": "Q8NER1",
    "pparg": "P37231",
    "ppar-gamma": "P37231",
    "faah": "O00519",
    "magl": "Q99685",
    "mgll": "Q99685",
}


Fetcher = Callable[[str], str]


default_bindingdb_fetcher = make_json_fetcher("bindingdb-discover", timeout=TIMEOUT_SLOW)


@dataclass(frozen=True)
class BindingDBRow:
    monomer_id: str
    target_uniprot: str
    target_name: Optional[str]
    smiles: Optional[str]
    affinity_type: Optional[str]
    affinity_value_nm: Optional[float]
    source_pmid: Optional[str]
    source_doi: Optional[str]
    # Relational qualifier on the affinity (">", "<", "~"), or None for an
    # exact value. BindingDB reports many affinities as bounds (e.g. ">2820");
    # keeping the qualifier prevents presenting a bound as an exact
    # measurement (Constitution §VII — GRADE / evidence honesty).
    affinity_qualifier: Optional[str] = None
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_BINDINGDB
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(
                self, "native_id", f"BDBM:{self.monomer_id}"
            )
        if not self.title:
            object.__setattr__(
                self,
                "title",
                f"BDBM {self.monomer_id} @ {self.target_name or self.target_uniprot}",
            )
        if not self.url:
            object.__setattr__(
                self,
                "url",
                _PUBLIC_LIGAND_URL.format(monomer_id=self.monomer_id),
            )
        if not self.citation:
            ident = self.source_pmid or self.source_doi
            tag = "PMID" if self.source_pmid else "DOI" if self.source_doi else None
            if tag:
                object.__setattr__(
                    self,
                    "citation",
                    f"BindingDB {self.monomer_id} ({tag} {ident})",
                )
            else:
                object.__setattr__(
                    self,
                    "citation",
                    f"BindingDB {self.monomer_id}",
                )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        return d


class BindingDBSearcher:
    """Live BindingDB search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_bindingdb_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        affinity_cutoff_nm: int = 10000,
    ) -> list[BindingDBRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        q = query.strip()
        if len(q) == 4 and q.isalnum() and not q.isdigit():
            # PDB-shaped identifier.
            return self._by_pdb(q.upper(), affinity_cutoff_nm, max_results)

        uniprot = self._resolve_uniprot(q)
        if uniprot is None:
            return []
        return self._by_uniprot(uniprot, affinity_cutoff_nm, max_results)

    def _resolve_uniprot(self, query: str) -> Optional[str]:
        q = query.strip()
        if len(q) >= 6 and (q[0].isalpha() and q[1:].isalnum()):
            # Looks like a UniProt accession.
            if q.upper() in {v for v in _CANNABIS_UNIPROTS.values()}:
                return q.upper()
            # Generic UniProt accession heuristic — letter + digits/letters.
            if any(c.isdigit() for c in q):
                return q.upper()
        hint = _CANNABIS_UNIPROTS.get(q.lower())
        return hint

    def _by_uniprot(
        self, uniprot: str, cutoff: int, limit: int,
    ) -> list[BindingDBRow]:
        url = _BY_UNIPROT_URL.format(uniprot=uniprot, cutoff=cutoff)
        data = self._fetch_json(url)
        items = _affinity_rows(data)
        rows = [_parse_row(it, uniprot) for it in items]
        return rows[:limit]

    def _by_pdb(
        self, pdb_id: str, cutoff: int, limit: int,
    ) -> list[BindingDBRow]:
        url = _BY_PDB_URL.format(pdb=pdb_id, cutoff=cutoff, identity=92)
        data = self._fetch_json(url)
        items = _affinity_rows(data)
        rows = [_parse_row(it, uniprot_from_pdb=pdb_id) for it in items]
        return rows[:limit]

    def _fetch_json(self, url: str) -> dict:
        try:
            body = self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(f"fetch failed: {url}: {exc}") from exc
        # BindingDB occasionally returns an empty body when there are
        # zero hits even with JSON requested. Treat that as
        # "no results" rather than a parse error.
        if not body.strip():
            return {"affinities": []}
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NetworkError(
                f"BindingDB response is not valid JSON for {url}: {exc}"
            ) from exc


# The live API wraps results under an envelope key whose exact spelling
# varies and is, in BindingDB's own JSON, misspelled: BOTH the UniProt and
# the PDB endpoints return ``getLindsBy…Response`` ("Linds", not "Ligands").
# Match any ``getL…Response`` envelope rather than hard-coding spellings so a
# future spelling fix (or the PDB variant) keeps parsing.
_ENVELOPE_KEY_RE = re.compile(r"^getL.*Response$")


def _affinity_rows(data: dict) -> list[dict]:
    """Normalise BindingDB's varying response shapes to a list of dicts."""
    if not isinstance(data, dict):
        return []
    # Defensive: a bare top-level affinities list (also what the empty-body
    # sentinel emits). The real API never returns this shape.
    for top in ("affinities", "Affinities"):
        val = data.get(top)
        if isinstance(val, list):
            return val
    for key, block in data.items():
        if not _ENVELOPE_KEY_RE.match(key) or not isinstance(block, dict):
            continue
        nested = block.get("affinities")
        if isinstance(nested, list):
            return nested
        # An XML→JSON conversion can collapse a single-element list to one
        # object; normalise it back to a list.
        if isinstance(nested, dict):
            return [nested]
    return []


_AFFINITY_RE = re.compile(
    r"^\s*(?P<qual><=|>=|<|>|~|=)?\s*(?P<num>[0-9]*\.?[0-9]+)"
)


def _parse_affinity(raw: object) -> tuple[Optional[float], Optional[str]]:
    """Split a BindingDB affinity into ``(value_nM, qualifier)``.

    The live API returns ``affinity`` as a string that may carry a
    relational qualifier — e.g. ``">2820"`` (a lower bound) or ``"<10"``
    (an upper bound). Returns the numeric portion plus the qualifier
    (``">"``, ``"<"``, ``"~"``, or ``None`` for an exact value).
    ``(None, None)`` when no number can be parsed.
    """
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw), None
    match = _AFFINITY_RE.match(str(raw))
    if not match:
        return None, None
    try:
        value = float(match.group("num"))
    except (TypeError, ValueError):
        return None, None
    qual = match.group("qual")
    # "=" is an exact value; "<="/">=" collapse to their strict form for
    # display. Anything non-exact is retained as a bound.
    if qual in (None, "="):
        return value, None
    return value, qual[0]


def _parse_row(
    item: dict,
    uniprot: Optional[str] = None,
    *,
    uniprot_from_pdb: Optional[str] = None,
) -> BindingDBRow:
    monomer_id = (
        str(item.get("monomerid") or item.get("monomerID")
            or item.get("monomer_id") or item.get("ligandId") or "")
    )
    affinity_type = (
        item.get("affinity_type")
        or item.get("affinityType")
        or item.get("type")
    )
    raw_val = item.get("affinity") or item.get("affinity_nM") or item.get("Ki")
    affinity_value, affinity_qualifier = _parse_affinity(raw_val)

    target_uniprot = (
        item.get("uniprot")
        or item.get("uniProtId")
        or uniprot
        or (f"PDB:{uniprot_from_pdb}" if uniprot_from_pdb else "")
    )
    # The live API carries the target name under "query".
    target_name = (
        item.get("target_name")
        or item.get("targetName")
        or item.get("query")
    )
    # The live API uses the singular "smile" key.
    smiles = item.get("SMILES") or item.get("smiles") or item.get("smile")
    pmid = item.get("pmid") or item.get("PMID")
    doi = item.get("doi") or item.get("DOI")

    return BindingDBRow(
        monomer_id=monomer_id or "?",
        target_uniprot=str(target_uniprot),
        target_name=target_name,
        smiles=smiles,
        affinity_type=affinity_type,
        affinity_value_nm=affinity_value,
        affinity_qualifier=affinity_qualifier,
        source_pmid=str(pmid) if pmid else None,
        source_doi=str(doi) if doi else None,
    )


def render_markdown(query: str, rows: list[BindingDBRow]) -> str:
    lines: list[str] = []
    lines.append(f"## BindingDB (live_bindingdb, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No BindingDB affinity rows for this query._")
        return "\n".join(lines)
    for r in rows:
        head = (
            f"- **BDBM {r.monomer_id}** @ {r.target_name or r.target_uniprot}"
        )
        if r.affinity_value_nm is not None and r.affinity_type:
            rel = r.affinity_qualifier or "="
            head += (
                f"  \n  {r.affinity_type} {rel} {r.affinity_value_nm:g} nM"
            )
        if r.source_pmid:
            head += f"  \n  PMID: {r.source_pmid}"
        elif r.source_doi:
            head += f"  \n  DOI: {r.source_doi}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[BindingDBRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_BINDINGDB.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
