"""Live GWAS Catalog discovery — cannabis-use-disorder genetic loci.

Cannabis-primary-source widening: the GWAS Catalog (EBI/NHGRI) is the
canonical primary source for human genetic associations. The
cannabis-relevant evidence base — cannabis use disorder (CUD), cannabis
dependence, age of first use — is curated under EFO terms such as
EFO_0007821 (cannabis use measurement). Citing "rs2501432 in CADM2 was
associated with cannabis use in a UKB-scale GWAS" needs the actual
study accession (e.g., GCST007090) and a p-value, both of which the
GWAS REST API serves.

Endpoints used (https://www.ebi.ac.uk/gwas/rest/api/v2):

- GET ``…/studies?diseaseTrait={trait}&size={n}``
  — studies whose disease trait matches the free-text query.
- GET ``…/efoTraits/search/findByEfoTrait?trait={trait}``
  — EFO trait lookup (used as a fallback resolver).
- GET ``…/studies/{study_accession}``
  — single-study detail.

Every emitted row carries ``Provenance.LIVE_GWAS`` and the suggested
grade ``Level B (provisional, live_gwas)`` if the underlying study is
genome-wide significant (the GWAS Catalog inclusion threshold) else
Level C.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "GWASStudyRow",
    "GWASSearcher",
    "NetworkError",
    "default_gwas_fetcher",
    "render_markdown",
    "render_json",
]


_GWAS_BASE = "https://www.ebi.ac.uk/gwas/rest/api/v2"
_STUDIES_BY_TRAIT_URL = (
    _GWAS_BASE + "/studies?disease_trait={trait}&size={size}"
)
_STUDY_DETAIL_URL = _GWAS_BASE + "/studies/{accession}"

_PUBLIC_URL = "https://www.ebi.ac.uk/gwas/studies/{accession}"

_DEFAULT_TIMEOUT = 12
_MAX_RESULTS_CEILING = 25


class NetworkError(Exception):
    """Raised when a GWAS Catalog fetch / parse fails after preflight."""


Fetcher = Callable[[str], str]


def default_gwas_fetcher(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cannavec-gwas-discover/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


@dataclass(frozen=True)
class GWASStudyRow:
    accession_id: str
    query: str
    disease_trait: Optional[str]
    initial_sample_description: Optional[str]
    pubmed_id: Optional[str]
    publication_date: Optional[str]
    journal: Optional[str]
    n_associations: Optional[int]
    n_efo_traits: Optional[int]
    is_genome_wide: bool
    suggested_grade: str
    source: Provenance = Provenance.LIVE_GWAS
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", self.accession_id)
        if not self.title:
            object.__setattr__(
                self,
                "title",
                self.disease_trait or self.accession_id,
            )
        if not self.url:
            object.__setattr__(
                self,
                "url",
                _PUBLIC_URL.format(accession=self.accession_id),
            )
        if not self.citation:
            tag = f"PMID {self.pubmed_id}" if self.pubmed_id else self.accession_id
            object.__setattr__(
                self,
                "citation",
                f"GWAS Catalog {self.accession_id} ({tag})",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        return d


class GWASSearcher:
    """Live GWAS Catalog search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_gwas_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[GWASStudyRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        q = query.strip()
        if q.upper().startswith("GCST") and q[4:].isdigit():
            row = self._fetch_one(q.upper(), query)
            return [row] if row is not None else []

        size = min(max_results * 2, _MAX_RESULTS_CEILING)
        url = _STUDIES_BY_TRAIT_URL.format(
            trait=urllib.parse.quote(q), size=size
        )
        data = self._fetch_json(url)
        studies = (
            (data.get("_embedded") or {}).get("studies")
            or data.get("studies")
            or []
        )
        rows: list[GWASStudyRow] = []
        for entry in studies:
            rows.append(_parse_study(entry, query))
        return rows[:max_results]

    def _fetch_one(
        self, accession: str, query: str,
    ) -> Optional[GWASStudyRow]:
        url = _STUDY_DETAIL_URL.format(accession=accession)
        data = self._fetch_json(url)
        if not data:
            return None
        if "accessionId" not in data and "accession_id" not in data:
            return None
        return _parse_study(data, query)

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
                f"GWAS Catalog response is not valid JSON for {url}: {exc}"
            ) from exc


def _parse_study(entry: dict, query: str) -> GWASStudyRow:
    accession = (
        entry.get("accessionId")
        or entry.get("accession_id")
        or entry.get("id")
        or ""
    )
    disease_trait = (
        entry.get("diseaseTrait", {}).get("trait")
        if isinstance(entry.get("diseaseTrait"), dict)
        else entry.get("diseaseTrait") or entry.get("disease_trait")
    )
    initial_sample = (
        entry.get("initialSampleSize")
        or entry.get("initial_sample_size")
        or entry.get("initialSampleDescription")
    )

    publication = entry.get("publication") or {}
    pubmed_id = (
        publication.get("pubmedId")
        or publication.get("pubmed_id")
        or entry.get("pubmedId")
    )
    publication_date = (
        publication.get("publicationDate")
        or publication.get("publication_date")
        or entry.get("publicationDate")
    )
    journal = publication.get("journal") or entry.get("journal")

    associations = entry.get("associations") or {}
    n_assoc = associations.get("count") if isinstance(associations, dict) else None
    if n_assoc is None:
        n_assoc = entry.get("associationCount") or entry.get("association_count")

    efo_traits = entry.get("efoTraits") or entry.get("efo_traits") or []
    if isinstance(efo_traits, dict):
        # _embedded shape carries a {"_embedded": {"efoTraits": [...]}} blob.
        efo_traits = (efo_traits.get("_embedded") or {}).get("efoTraits") or []
    n_efo = len(efo_traits) if isinstance(efo_traits, list) else None

    is_genome_wide = bool(
        entry.get("genomewideArray") or entry.get("genomewide_array") or
        entry.get("fullPvalueSet") or entry.get("full_pvalue_set")
    )

    grade = (
        "Level B (provisional, live_gwas)"
        if is_genome_wide
        else "Level C (provisional, live_gwas)"
    )

    return GWASStudyRow(
        accession_id=str(accession),
        query=query,
        disease_trait=disease_trait,
        initial_sample_description=initial_sample,
        pubmed_id=str(pubmed_id) if pubmed_id else None,
        publication_date=publication_date,
        journal=journal,
        n_associations=int(n_assoc) if isinstance(n_assoc, int) else None,
        n_efo_traits=n_efo,
        is_genome_wide=is_genome_wide,
        suggested_grade=grade,
    )


def render_markdown(query: str, rows: list[GWASStudyRow]) -> str:
    lines: list[str] = []
    lines.append(f"## GWAS Catalog (live_gwas, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No GWAS Catalog studies for this trait._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **{r.accession_id}** — {r.disease_trait or '?'}"
        if r.pubmed_id:
            head += f"  \n  PMID: {r.pubmed_id}"
        if r.journal:
            yr = (r.publication_date or "")[:4]
            head += f"  \n  {r.journal} {yr}".rstrip()
        if r.initial_sample_description:
            head += (
                f"  \n  Cohort: {r.initial_sample_description[:140]}"
            )
        if r.n_associations is not None:
            head += f"  \n  Associations: {r.n_associations}"
        head += f"  \n  Suggested grade: {r.suggested_grade}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(query: str, rows: list[GWASStudyRow]) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_GWAS.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
