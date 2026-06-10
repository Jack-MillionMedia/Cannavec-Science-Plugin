"""Live Reactome discovery — curated pathways for cannabinoid receptors.

Spec 030 P1. Stdlib-only ``urllib`` transport, injected ``Fetcher`` for
offline tests, safety + banned-pattern preflight via ``discover_guard``
BEFORE any network call.

Where QuickGO answers "what *function* does this receptor have," Reactome
answers "what *pathways* does it act in." Reactome is a manually-curated
pathway knowledgebase: a receptor's UniProt accession maps to the human
pathways it participates in (CB1 = P21554 → ``R-HSA-373076`` Class A/1
rhodopsin-like receptors, ``R-HSA-418594`` G alpha (i) signalling events),
each pathway carrying a curated summary and **literature references (PMIDs)**.

Reactome ContentService REST endpoints used (verified live 2026-06-04):

- ``…/ContentService/data/mapping/UniProt/{accession}/pathways?species=Homo%20sapiens``
  — the human pathways a protein participates in (a JSON array).
- ``…/ContentService/data/query/{stId}``
  — pathway detail: ``summation`` (curated description) +
  ``literatureReference[].pubMedIdentifier``.

A pathway that carries a literature PMID sorts ahead of one that does not
(§I prefers primary sources); the first PMID rides the row's ``pmid`` field so
the §VIII retraction guard checks it. Every row carries
``Provenance.LIVE_REACTOME`` and ``Level D (provisional, live_reactome)`` —
a pathway membership is mechanistic context, not clinical evidence (§VII), and
never auto-promotes (§IX).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science._http import NetworkError, TIMEOUT_FAST, make_json_fetcher
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "ReactomePathwayRow",
    "ReactomeSearcher",
    "NetworkError",
    "default_reactome_fetcher",
    "render_markdown",
    "render_json",
]


_BASE = "https://reactome.org/ContentService/data"
_MAPPING_URL = _BASE + "/mapping/UniProt/{accession}/pathways?species=Homo%20sapiens"
_DETAIL_URL = _BASE + "/query/{st_id}"
_LANDING = "https://reactome.org/content/detail/{st_id}"

_MAX_RESULTS_CEILING = 25
# Hard ceiling on per-pathway detail fetches so a protein in many pathways
# cannot explode the request count; mapping rarely returns more top-level
# pathways than this for one accession.
_DETAIL_FETCH_CAP = 15
_SUMMARY_MAX = 280

_SUGGESTED_GRADE = "Level D (provisional, live_reactome)"

# §VI receptor canon (the same six named in answer.py). Keys are upper-cased.
_RECEPTOR_UNIPROT = {
    "CB1": "P21554", "CNR1": "P21554",
    "CB2": "P34972", "CNR2": "P34972",
    "TRPV1": "Q8NER1",
    "PPARG": "P37231", "PPARGAMMA": "P37231", "PPAR-GAMMA": "P37231",
    "PPARΓ": "P37231",
    "5-HT1A": "P08908", "5HT1A": "P08908", "HTR1A": "P08908",
    "GPR55": "Q9Y2T6",
}
_UNIPROT_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)


Fetcher = Callable[[str], str]


default_reactome_fetcher = make_json_fetcher("reactome-discover", timeout=TIMEOUT_FAST)


@dataclass(frozen=True)
class ReactomePathwayRow:
    pathway_id: str
    receptor_query: str
    uniprot: str
    display_name: str
    is_disease: bool
    summary: Optional[str]
    pmids: tuple[str, ...]
    species: str
    pmid: str = ""
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_REACTOME
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.pmid and self.pmids:
            object.__setattr__(self, "pmid", self.pmids[0])
        if not self.native_id:
            object.__setattr__(self, "native_id", self.pathway_id)
        if not self.title:
            object.__setattr__(self, "title", self.display_name or self.pathway_id)
        if not self.url:
            object.__setattr__(
                self, "url", _LANDING.format(st_id=self.pathway_id)
            )
        if not self.citation:
            pmid_part = f"; PMID {self.pmid}" if self.pmid else ""
            object.__setattr__(
                self,
                "citation",
                f"{self.display_name} (Reactome {self.pathway_id}{pmid_part})",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["pmids"] = list(self.pmids)
        return d


class ReactomeSearcher:
    """Live Reactome pathway search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_reactome_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[ReactomePathwayRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        accession = self._resolve_accession(query)
        pathways = self._fetch_pathways(accession)
        if not pathways:
            return []

        rows = [
            self._build_row(query, accession, p)
            for p in pathways[:_DETAIL_FETCH_CAP]
        ]
        # §I — pathways with a literature PMID lead; stable within, then by id.
        rows.sort(key=lambda r: (0 if r.pmid else 1, r.pathway_id))
        return rows[:max_results]

    def _resolve_accession(self, query: str) -> str:
        q = query.strip()
        mapped = _RECEPTOR_UNIPROT.get(q.upper())
        if mapped:
            return mapped
        if _UNIPROT_RE.match(q.upper()):
            return q.upper()
        raise ValueError(
            f"{query!r} is not a known receptor name or UniProt accession; "
            f"known receptors: {sorted(set(_RECEPTOR_UNIPROT))}"
        )

    def _fetch_pathways(self, accession: str) -> list[dict]:
        url = _MAPPING_URL.format(accession=urllib.parse.quote(accession))
        data = self._fetch_json(url)
        if not isinstance(data, list):
            return []
        return [
            p for p in data
            if isinstance(p, dict)
            and p.get("stId")
            and p.get("schemaClass") == "Pathway"
            # ``or`` (not get's default) so a present-but-null speciesName is
            # treated as human rather than silently dropped.
            and (p.get("speciesName") or "Homo sapiens") == "Homo sapiens"
        ]

    def _build_row(
        self, query: str, accession: str, pathway: dict
    ) -> ReactomePathwayRow:
        st_id = pathway["stId"]
        summary: Optional[str] = None
        pmids: tuple[str, ...] = ()
        is_disease = bool(pathway.get("isInDisease"))
        # Detail enrichment is best-effort: a pathway still emits (with its
        # mapping-level name + id) if the detail call fails.
        try:
            detail = self._fetch_json(_DETAIL_URL.format(st_id=st_id))
        except NetworkError:
            detail = None
        if isinstance(detail, dict):
            is_disease = bool(detail.get("isInDisease", is_disease))
            summ = detail.get("summation") or []
            if summ and isinstance(summ[0], dict):
                text = (summ[0].get("text") or "").strip()
                summary = text[:_SUMMARY_MAX] or None
            pmids = tuple(
                str(ref.get("pubMedIdentifier"))
                for ref in (detail.get("literatureReference") or [])
                if isinstance(ref, dict) and ref.get("pubMedIdentifier")
            )

        return ReactomePathwayRow(
            pathway_id=st_id,
            receptor_query=query,
            uniprot=accession,
            display_name=(pathway.get("displayName") or st_id),
            is_disease=is_disease,
            summary=summary,
            pmids=pmids,
            species=pathway.get("speciesName") or "Homo sapiens",
        )

    def _fetch_json(self, url: str):
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
                f"Reactome response is not valid JSON for {url}: {exc}"
            ) from exc


def render_markdown(query: str, rows: list[ReactomePathwayRow]) -> str:
    lines: list[str] = []
    lines.append(f"## Reactome (live_reactome, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No Reactome pathway resolved for this receptor._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **{r.pathway_id}** {r.display_name}"
        if r.is_disease:
            head += " ⚠ disease pathway"
        head += f"  \n  {r.uniprot} participates"
        if r.pmids:
            head += f"; refs PMID {', '.join(r.pmids)}"
        if r.summary:
            head += f"  \n  {r.summary}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[ReactomePathwayRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_REACTOME.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
