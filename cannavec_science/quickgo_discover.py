"""Live QuickGO discovery — Gene-Ontology function for cannabinoid receptors.

Spec 029 P2. Stdlib-only ``urllib`` transport, injected ``Fetcher`` for
offline tests, safety + banned-pattern preflight via ``discover_guard``
BEFORE any network call.

§VI already demands every receptor carry its UniProt accession (CB1 = P21554,
CB2 = P34972, TRPV1 = Q8NER1, PPARγ = P37231, 5-HT1A = P08908, GPR55 = Q9Y2T6).
QuickGO turns that accession into evidence: the Gene-Ontology annotations of a
receptor — molecular function (``GO:0004949 cannabinoid receptor activity``),
biological process, cellular component — each with an **evidence code** and a
**reference** (a PMID for experimental annotations, a ``GO_REF`` for electronic
ones). That is the functional half of the mechanism the registries describe in
prose.

QuickGO REST endpoints used (verified live 2026-06-04):

- ``…/QuickGO/services/annotation/search?geneProductId={accession}&limit={n}``
  — the receptor's GO annotations. The annotation payload carries ``goName:
  null``, so the lane batch-resolves names from:
- ``…/QuickGO/services/ontology/go/terms/{id1,id2,…}``
  — id → ``{"name","aspect"}``.

Experimental (PMID-referenced) annotations are surfaced ahead of electronic
(``GO_REF``) ones (§I prefers primary sources), and a PMID reference is parsed
onto the row's ``pmid`` field so the §VIII retraction guard checks it. Every row
carries ``Provenance.LIVE_QUICKGO`` and ``Level D (provisional, live_quickgo)``
— a functional annotation is mechanistic context, not clinical evidence (§VII),
and never auto-promotes (§IX).
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
    "QuickGOAnnotationRow",
    "QuickGOSearcher",
    "NetworkError",
    "default_quickgo_fetcher",
    "render_markdown",
    "render_json",
]


_QUICKGO_BASE = "https://www.ebi.ac.uk/QuickGO/services"
_ANNOTATION_URL = (
    _QUICKGO_BASE + "/annotation/search?geneProductId={accession}&limit={limit}"
)
_TERMS_URL = _QUICKGO_BASE + "/ontology/go/terms/{ids}"
_TERM_LANDING = "https://www.ebi.ac.uk/QuickGO/term/{go_id}"

_MAX_RESULTS_CEILING = 25
# Fetch a bounded super-set of annotations so the §I primary-source-first sort
# has something to promote, then cap to the caller's max_results.
_ANNOTATION_FETCH_CAP = 50

_SUGGESTED_GRADE = "Level D (provisional, live_quickgo)"

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

# Canonical UniProt accession syntax (UniProtKB).
_UNIPROT_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)
_PMID_RE = re.compile(r"^PMID:(\d+)$", re.IGNORECASE)


Fetcher = Callable[[str], str]


default_quickgo_fetcher = make_json_fetcher("quickgo-discover", timeout=TIMEOUT_FAST)


@dataclass(frozen=True)
class QuickGOAnnotationRow:
    go_id: str
    receptor_query: str
    uniprot: str
    go_name: Optional[str]
    go_aspect: str
    evidence: str
    evidence_code: Optional[str]
    reference: str
    qualifier: str
    symbol: Optional[str]
    pmid: str = ""
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_QUICKGO
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.pmid:
            m = _PMID_RE.match(self.reference or "")
            if m:
                object.__setattr__(self, "pmid", m.group(1))
        if not self.native_id:
            object.__setattr__(self, "native_id", self.go_id)
        if not self.title:
            object.__setattr__(self, "title", self.go_name or self.go_id)
        if not self.url:
            object.__setattr__(self, "url", _TERM_LANDING.format(go_id=self.go_id))
        if not self.citation:
            label = self.go_name or self.go_id
            object.__setattr__(
                self,
                "citation",
                f"{self.uniprot} {self.qualifier} {label} "
                f"[{self.go_id}; {self.evidence}; {self.reference}]",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        return d


class QuickGOSearcher:
    """Live QuickGO annotation search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_quickgo_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[QuickGOAnnotationRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        accession = self._resolve_accession(query)
        annotations = self._fetch_annotations(accession)
        if not annotations:
            return []

        name_by_id = self._resolve_go_names(
            sorted({a["goId"] for a in annotations if a.get("goId")})
        )

        rows = [
            self._build_row(query, accession, a, name_by_id)
            for a in annotations
            if a.get("goId")
        ]
        # §I — experimental (PMID-referenced) annotations first; stable within.
        rows.sort(key=lambda r: (0 if r.pmid else 1, r.go_id))
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

    def _fetch_annotations(self, accession: str) -> list[dict]:
        url = _ANNOTATION_URL.format(
            accession=urllib.parse.quote(accession), limit=_ANNOTATION_FETCH_CAP
        )
        data = self._fetch_json(url)
        results = data.get("results")
        return [r for r in results if isinstance(r, dict)] if results else []

    def _resolve_go_names(self, go_ids: list[str]) -> dict[str, str]:
        if not go_ids:
            return {}
        # Bounded by construction: ``go_ids`` is the distinct set drawn from at
        # most ``_ANNOTATION_FETCH_CAP`` annotations, so the comma-joined terms
        # URL stays well under any practical URL-length limit.
        url = _TERMS_URL.format(ids=",".join(go_ids))
        try:
            data = self._fetch_json(url)
        except NetworkError:
            return {}  # name enrichment is best-effort; ids still stand
        out: dict[str, str] = {}
        for term in (data.get("results") or []):
            tid = term.get("id")
            if tid and term.get("name"):
                out[tid] = term["name"]
        return out

    def _build_row(
        self, query: str, accession: str, ann: dict, name_by_id: dict[str, str]
    ) -> QuickGOAnnotationRow:
        go_id = ann.get("goId") or ""
        return QuickGOAnnotationRow(
            go_id=go_id,
            receptor_query=query,
            uniprot=accession,
            go_name=name_by_id.get(go_id) or ann.get("goName"),
            go_aspect=ann.get("goAspect") or "",
            evidence=ann.get("goEvidence") or "",
            evidence_code=ann.get("evidenceCode"),
            reference=ann.get("reference") or "",
            qualifier=ann.get("qualifier") or "",
            symbol=ann.get("symbol"),
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
                f"QuickGO response is not valid JSON for {url}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise NetworkError(f"QuickGO response is not a JSON object for {url}")
        return parsed


_ASPECT_SHORT = {
    "molecular_function": "MF",
    "biological_process": "BP",
    "cellular_component": "CC",
}


def render_markdown(query: str, rows: list[QuickGOAnnotationRow]) -> str:
    lines: list[str] = []
    lines.append(f"## QuickGO (live_quickgo, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No QuickGO annotations resolved for this receptor._")
        return "\n".join(lines)
    for r in rows:
        aspect = _ASPECT_SHORT.get(r.go_aspect, r.go_aspect or "?")
        head = f"- **{r.go_id}** {r.go_name or ''} ({aspect})".rstrip()
        head += f"  \n  {r.uniprot} {r.qualifier}; evidence {r.evidence}; {r.reference}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[QuickGOAnnotationRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_QUICKGO.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
