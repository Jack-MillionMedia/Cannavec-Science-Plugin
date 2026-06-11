"""Live PharmGKB discovery — pharmacogenomic annotations for cannabis metabolism.

Cannabis-primary-source widening: PharmGKB catalogs how human genetic
variation in CYP2C9, CYP2C19, CYP3A4, COMT, and FAAH alters individual
metabolism of THC and CBD. The curated ``pharmacogenomics`` registry
ships a small high-confidence row set; this discoverer surfaces live
PharmGKB clinical annotations and dosing guidelines for the same
metabolic axis so a researcher can cross-check the curated rows against
the latest PharmGKB grading.

Endpoints used (https://api.pharmgkb.org/v1/data):

- ``…/chemical?name={drug}`` — resolve drug → PharmGKB chemical accession.
- ``…/clinicalAnnotation?relatedChemicals.accessionId={pa-id}&view=base``
  — clinical annotations for the chemical.
- ``…/gene/{pa-id}`` — gene metadata (symbol, aliases).

Every emitted row carries ``Provenance.LIVE_PHARMGKB`` and a provisional
grade. PharmGKB rates evidence on its own 1A → 4 scale; the suggested
grade derived here is conservative — Level B if the PharmGKB level is
1A or 1B (FDA-label adjacent / professional society guideline), else
Level C.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science._http import NetworkError, TIMEOUT_FAST, make_json_fetcher
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "PharmGKBAnnotationRow",
    "PharmGKBSearcher",
    "NetworkError",
    "default_pharmgkb_fetcher",
    "render_markdown",
    "render_json",
]


_PGKB_BASE = "https://api.pharmgkb.org/v1/data"
_CHEMICAL_SEARCH_URL = _PGKB_BASE + "/chemical?name={name}&view=base"
_CLINICAL_ANNOTATION_URL = (
    _PGKB_BASE
    + "/clinicalAnnotation"
    + "?relatedChemicals.accessionId={accession}"
    + "&view=base&limit={limit}"
)
_GENE_URL = _PGKB_BASE + "/gene/{accession}"

_PUBLIC_PAGE_URL = "https://www.pharmgkb.org/{kind}/{accession}"

_MAX_RESULTS_CEILING = 25


Fetcher = Callable[[str], str]


default_pharmgkb_fetcher = make_json_fetcher("pharmgkb-discover", timeout=TIMEOUT_FAST)


# PharmGKB level-of-evidence → Cannavec GRADE mapping.
# PharmGKB scale: 1A > 1B > 2A > 2B > 3 > 4.
# Cannavec Constitution §VII caps single primary studies at Level B.
_LEVEL_GRADE_MAP = {
    "1A": "Level B (provisional, live_pharmgkb)",
    "1B": "Level B (provisional, live_pharmgkb)",
    "2A": "Level C (provisional, live_pharmgkb)",
    "2B": "Level C (provisional, live_pharmgkb)",
    "3":  "Level D (provisional, live_pharmgkb)",
    "4":  "Level D (provisional, live_pharmgkb)",
}
_DEFAULT_GRADE = "Level D (provisional, live_pharmgkb)"


@dataclass(frozen=True)
class PharmGKBAnnotationRow:
    accession_id: str
    chemical_accession: Optional[str]
    chemical_name: Optional[str]
    related_genes: tuple[str, ...]
    related_variants: tuple[str, ...]
    phenotype_categories: tuple[str, ...]
    level_of_evidence: Optional[str]
    suggested_grade: str
    summary: Optional[str]
    source: Provenance = Provenance.LIVE_PHARMGKB
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(self, "native_id", self.accession_id)
        if not self.title:
            gene_part = ", ".join(self.related_genes[:3]) or "?"
            object.__setattr__(
                self,
                "title",
                f"{self.chemical_name or 'PGx'} × {gene_part}",
            )
        if not self.url:
            object.__setattr__(
                self,
                "url",
                _PUBLIC_PAGE_URL.format(
                    kind="clinicalAnnotation", accession=self.accession_id
                ),
            )
        if not self.citation:
            level = self.level_of_evidence or "?"
            object.__setattr__(
                self,
                "citation",
                f"PharmGKB {self.accession_id} (level {level})",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["related_genes"] = list(self.related_genes)
        d["related_variants"] = list(self.related_variants)
        d["phenotype_categories"] = list(self.phenotype_categories)
        return d


class PharmGKBSearcher:
    """Live PharmGKB search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_pharmgkb_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[PharmGKBAnnotationRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        chemical = self._resolve_chemical(query)
        if chemical is None:
            return []

        accession = chemical.get("id") or chemical.get("accessionId")
        if not accession:
            return []
        chemical_name = chemical.get("name")

        rows = self._fetch_clinical_annotations(
            str(accession), chemical_name, max_results
        )
        return rows[:max_results]

    def _resolve_chemical(self, query: str) -> Optional[dict]:
        q = query.strip()
        if q.upper().startswith("PA") and q[2:].isdigit():
            return {"id": q.upper(), "name": q.upper()}
        url = _CHEMICAL_SEARCH_URL.format(name=urllib.parse.quote(q))
        data = self._fetch_json(url)
        candidates = data.get("data") or []
        if not candidates:
            return None
        # PharmGKB returns the closest matches first.
        return candidates[0]

    def _fetch_clinical_annotations(
        self,
        accession: str,
        chemical_name: Optional[str],
        limit: int,
    ) -> list[PharmGKBAnnotationRow]:
        ask = min(limit * 2, _MAX_RESULTS_CEILING)
        url = _CLINICAL_ANNOTATION_URL.format(
            accession=accession, limit=ask
        )
        data = self._fetch_json(url)
        items = data.get("data") or []
        rows: list[PharmGKBAnnotationRow] = []
        for item in items:
            rows.append(_parse_annotation(item, accession, chemical_name))
        return rows

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
                f"PharmGKB response is not valid JSON for {url}: {exc}"
            ) from exc


def _parse_annotation(
    item: dict, chemical_accession: str, chemical_name: Optional[str],
) -> PharmGKBAnnotationRow:
    accession_id = (
        item.get("id") or item.get("accessionId") or item.get("@id") or ""
    )

    related_genes = tuple(
        sorted({
            (g.get("symbol") or g.get("name") or "")
            for g in (item.get("relatedGenes") or [])
            if g.get("symbol") or g.get("name")
        })
    )
    related_variants = tuple(
        sorted({
            (v.get("symbol") or v.get("name") or "")
            for v in (item.get("relatedVariants") or [])
            if v.get("symbol") or v.get("name")
        })
    )
    phenotype_categories = tuple(
        sorted({
            (p.get("term") or p.get("name") or "")
            for p in (item.get("phenotypeCategories") or [])
            if p.get("term") or p.get("name")
        })
    )

    level = (
        item.get("levelOfEvidence", {}).get("term")
        if isinstance(item.get("levelOfEvidence"), dict)
        else item.get("levelOfEvidence")
    )
    level_key = (level or "").strip()
    grade = _LEVEL_GRADE_MAP.get(level_key, _DEFAULT_GRADE)

    summary = (
        item.get("summaryMarkdown", {}).get("html")
        if isinstance(item.get("summaryMarkdown"), dict)
        else (item.get("summary") or item.get("text"))
    )
    if isinstance(summary, str):
        summary = summary.strip() or None

    return PharmGKBAnnotationRow(
        accession_id=str(accession_id),
        chemical_accession=chemical_accession,
        chemical_name=chemical_name,
        related_genes=related_genes,
        related_variants=related_variants,
        phenotype_categories=phenotype_categories,
        level_of_evidence=level_key or None,
        suggested_grade=grade,
        summary=summary,
    )


def render_markdown(
    query: str, rows: list[PharmGKBAnnotationRow]
) -> str:
    lines: list[str] = []
    lines.append(f"## PharmGKB (live_pharmgkb, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No PharmGKB clinical annotations for this query._")
        return "\n".join(lines)
    for r in rows:
        head = f"- **{r.accession_id}** — {r.chemical_name or '?'}"
        if r.related_genes:
            head += f"  \n  Genes: {', '.join(r.related_genes[:4])}"
        if r.related_variants:
            head += f"  \n  Variants: {', '.join(r.related_variants[:4])}"
        if r.phenotype_categories:
            head += (
                f"  \n  Phenotype: "
                f"{', '.join(r.phenotype_categories[:3])}"
            )
        if r.level_of_evidence:
            head += f"  \n  PharmGKB level: {r.level_of_evidence}"
        head += f"  \n  Suggested grade: {r.suggested_grade}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(
    query: str, rows: list[PharmGKBAnnotationRow]
) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_PHARMGKB.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
