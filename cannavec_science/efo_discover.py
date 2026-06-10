"""Live EFO (Experimental Factor Ontology) discovery — indication normalization.

Spec 030 P2. Stdlib-only ``urllib`` transport, injected ``Fetcher`` for
offline tests, safety + banned-pattern preflight via ``discover_guard``
BEFORE any network call.

A research question names an indication in many ways — "MS spasticity",
"neuropathic pain", "Dravet". EFO (via EBI's OLS4) resolves a phrase to its
**canonical ontology term** (an EFO / MONDO / HP id + label + definition +
synonyms), which a researcher uses to build a precise, vocabulary-correct
literature query. EFO imports MONDO / HP / Orphanet, so the ``obo_id`` prefix
names the term's true source ontology.

OLS4 endpoint used (verified live 2026-06-04):

- ``…/ols4/api/search?q={term}&ontology=efo&rows={n}``
  → ``{"response": {"numFound", "docs": [{"obo_id","label","description",
  "synonym","iri","short_form","ontology_prefix"}]}}``.

**An ontology term id is NOT a §I primary research source** (§I's anchors are
PMID / DOI / ChEMBL / NCT / UniProt). EFO is therefore a *normalization* lane:
every row carries ``Provenance.LIVE_EFO`` and ``Level D (provisional,
live_efo)``, is framed as vocabulary context rather than evidence, and never
weaves into an answer's citable evidence tier (``answer.live_finding_from_row``
returns ``None`` for it) and never auto-promotes (§IX).
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
    "EFOTermRow",
    "EFOSearcher",
    "NetworkError",
    "default_efo_fetcher",
    "render_markdown",
    "render_json",
]


_OLS4_BASE = "https://www.ebi.ac.uk/ols4/api"
_SEARCH_URL = _OLS4_BASE + "/search?q={q}&ontology=efo&rows={rows}"
_LANDING = "https://www.ebi.ac.uk/ols4/ontologies/efo/classes?iri={iri}"

_MAX_RESULTS_CEILING = 25
_HTML_TAG_RE = re.compile(r"<[^>]+>")

_SUGGESTED_GRADE = "Level D (provisional, live_efo)"


Fetcher = Callable[[str], str]


default_efo_fetcher = make_json_fetcher("efo-discover", timeout=TIMEOUT_FAST)


@dataclass(frozen=True)
class EFOTermRow:
    efo_id: str
    term_query: str
    label: str
    ontology: str
    description: Optional[str]
    synonyms: tuple[str, ...]
    iri: str
    short_form: str
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_EFO
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", self.efo_id)
        if not self.title:
            object.__setattr__(self, "title", self.label or self.efo_id)
        if not self.url and self.iri:
            object.__setattr__(
                self, "url",
                _LANDING.format(iri=urllib.parse.quote(self.iri, safe="")),
            )
        if not self.citation:
            object.__setattr__(
                self, "citation", f"{self.label} ({self.efo_id}, {self.ontology})"
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["synonyms"] = list(self.synonyms)
        return d


class EFOSearcher:
    """Live OLS4/EFO term search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_efo_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[EFOTermRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        url = _SEARCH_URL.format(
            q=urllib.parse.quote(query.strip()), rows=max_results
        )
        data = self._fetch_json(url)
        docs = ((data.get("response") or {}).get("docs")) or []

        rows: list[EFOTermRow] = []
        for doc in docs[:max_results]:
            row = self._build_row(query, doc)
            if row is not None:
                rows.append(row)
        return rows

    def _build_row(self, query: str, doc: dict) -> Optional[EFOTermRow]:
        efo_id = doc.get("obo_id") or _short_to_obo(doc.get("short_form"))
        if not efo_id:
            return None
        ontology = efo_id.split(":", 1)[0] if ":" in efo_id else (
            doc.get("ontology_prefix") or ""
        )
        desc_list = doc.get("description") or []
        description = _clean(desc_list[0]) if desc_list else None
        return EFOTermRow(
            efo_id=efo_id,
            term_query=query,
            label=_clean(doc.get("label")) or efo_id,
            ontology=ontology,
            description=description or None,
            synonyms=tuple(s for s in (doc.get("synonym") or []) if s),
            iri=doc.get("iri") or "",
            short_form=doc.get("short_form") or "",
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
                f"OLS4 response is not valid JSON for {url}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise NetworkError(f"OLS4 response is not a JSON object for {url}")
        return parsed


def _short_to_obo(short_form: Optional[str]) -> str:
    """``EFO_0005762`` → ``EFO:0005762`` (fallback when ``obo_id`` is absent)."""
    if not short_form or "_" not in short_form:
        return ""
    return short_form.replace("_", ":", 1)


def _clean(text) -> str:
    if not text:
        return ""
    return html.unescape(_HTML_TAG_RE.sub("", str(text))).strip()


def render_markdown(query: str, rows: list[EFOTermRow]) -> str:
    lines: list[str] = []
    lines.append(f"## EFO (live_efo, provisional) — {query}")
    lines.append("")
    lines.append(
        "_Indication normalization (ontology vocabulary), not clinical "
        "evidence — use the resolved term to build a precise literature query._"
    )
    lines.append("")
    if not rows:
        lines.append("_No EFO term resolved for this phrase._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **{r.efo_id}** {r.label} ({r.ontology})"
        if r.description:
            head += f"  \n  {r.description}"
        if r.synonyms:
            head += f"  \n  Synonyms: {', '.join(r.synonyms)}"
        if r.url:
            head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[EFOTermRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_EFO.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
