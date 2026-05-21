"""Live Open Targets Platform discovery — cannabinoid-receptor disease associations.

Cannabis-primary-source widening: Open Targets is the canonical
target-vs-disease evidence aggregator. For cannabis pharmacology the
most-cited targets are CNR1 (CB1, ENSG00000118432), CNR2 (CB2,
ENSG00000188822), TRPV1 (ENSG00000196689), PPARG (ENSG00000132170),
and FAAH (ENSG00000117480). Open Targets returns an aggregated
association score per (target, disease) pair plus per-datasource
breakdowns (GeneticAssociations, RNAExpression, KnownDrug,
Literature, etc.) which lets a researcher cite "Disease X has Open
Targets association score Y for CB1" with the actual upstream
datasources.

GraphQL endpoint: https://api.platform.opentargets.org/api/v4/graphql
POST + JSON, no auth, urllib-friendly.

Every emitted row carries ``Provenance.LIVE_OPENTARGETS`` and the
suggested grade ``Level C (provisional, live_opentargets)`` — an
association score is mechanistic / hypothesis-generating; it cannot
on its own move past Level C without clinical anchoring.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "OpenTargetsAssociationRow",
    "OpenTargetsSearcher",
    "NetworkError",
    "default_opentargets_fetcher",
    "render_markdown",
    "render_json",
]


_GQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

_DEFAULT_TIMEOUT = 12
_MAX_RESULTS_CEILING = 25

_SUGGESTED_GRADE = "Level C (provisional, live_opentargets)"

# Symbol → Ensembl ID for the cannabis-relevant default targets. The
# search() entry point first tries the user query as-is; if it does
# not look like an Ensembl ID, we fall through to a search-by-symbol
# GraphQL query.
_CANNABIS_TARGET_HINTS = {
    "cb1": "ENSG00000118432",
    "cnr1": "ENSG00000118432",
    "cb2": "ENSG00000188822",
    "cnr2": "ENSG00000188822",
    "trpv1": "ENSG00000196689",
    "pparg": "ENSG00000132170",
    "ppar-gamma": "ENSG00000132170",
    "faah": "ENSG00000117480",
    "magl": "ENSG00000074416",
    "mgll": "ENSG00000074416",
}


_RESOLVE_QUERY = """
query resolveTarget($q: String!) {
  search(queryString: $q, entityNames: ["target"], page: {index: 0, size: 5}) {
    hits {
      id
      name
      entity
      object {
        ... on Target {
          id
          approvedSymbol
          approvedName
        }
      }
    }
  }
}
""".strip()


_ASSOCIATIONS_QUERY = """
query associatedDiseases($ensemblId: String!, $size: Int!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    approvedName
    associatedDiseases(page: {index: 0, size: $size}) {
      count
      rows {
        disease {
          id
          name
          therapeuticAreas { id name }
        }
        score
        datatypeScores { id score }
      }
    }
  }
}
""".strip()


class NetworkError(Exception):
    """Raised when an Open Targets fetch / parse fails after preflight."""


Fetcher = Callable[..., str]


def default_opentargets_fetcher(
    url: str, *, body: Optional[bytes] = None,
) -> str:
    """Production fetcher — POST GraphQL body, JSON."""
    headers = {
        "User-Agent": "cannavec-opentargets-discover/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


@dataclass(frozen=True)
class OpenTargetsAssociationRow:
    ensembl_id: str
    target_symbol: Optional[str]
    target_name: Optional[str]
    query: str
    disease_id: str
    disease_name: str
    therapeutic_areas: tuple[str, ...]
    overall_score: Optional[float]
    datatype_scores: tuple[tuple[str, float], ...]
    suggested_grade: str = _SUGGESTED_GRADE
    source: Provenance = Provenance.LIVE_OPENTARGETS
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.native_id:
            object.__setattr__(
                self, "native_id", f"{self.ensembl_id}::{self.disease_id}"
            )
        if not self.title:
            sym = self.target_symbol or self.ensembl_id
            object.__setattr__(
                self, "title", f"{sym} ↔ {self.disease_name}"
            )
        if not self.url:
            object.__setattr__(
                self,
                "url",
                "https://platform.opentargets.org/evidence/"
                f"{self.ensembl_id}/{self.disease_id}",
            )
        if not self.citation:
            object.__setattr__(
                self,
                "citation",
                f"Open Targets {self.ensembl_id}↔{self.disease_id}"
                f" (overall={self.overall_score})",
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["therapeutic_areas"] = list(self.therapeutic_areas)
        d["datatype_scores"] = [
            {"id": k, "score": v} for k, v in self.datatype_scores
        ]
        return d


class OpenTargetsSearcher:
    """Live Open Targets search with injected-fetcher fixtures."""

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_opentargets_fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[OpenTargetsAssociationRow]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        preflight(query)

        ensembl_id = self._resolve_target(query)
        if ensembl_id is None:
            return []

        return self._fetch_associations(query, ensembl_id, max_results)

    def _resolve_target(self, query: str) -> Optional[str]:
        q = query.strip()
        if q.upper().startswith("ENSG") and len(q) >= 11:
            return q.upper()
        # Cannabis-receptor fast path.
        hint = _CANNABIS_TARGET_HINTS.get(q.lower())
        if hint:
            return hint
        data = self._gql(_RESOLVE_QUERY, {"q": q})
        hits = (
            (data.get("data") or {}).get("search", {}).get("hits") or []
        )
        for hit in hits:
            obj = hit.get("object") or {}
            tid = obj.get("id") or hit.get("id")
            if tid and str(tid).startswith("ENSG"):
                return str(tid)
        return None

    def _fetch_associations(
        self, query: str, ensembl_id: str, size: int,
    ) -> list[OpenTargetsAssociationRow]:
        data = self._gql(
            _ASSOCIATIONS_QUERY, {"ensemblId": ensembl_id, "size": size}
        )
        target = (data.get("data") or {}).get("target") or {}
        rows_block = (target.get("associatedDiseases") or {}).get("rows") or []
        rows: list[OpenTargetsAssociationRow] = []
        for entry in rows_block:
            disease = entry.get("disease") or {}
            ta = tuple(
                (t.get("name") or "")
                for t in (disease.get("therapeuticAreas") or [])
                if t.get("name")
            )
            dt_scores = tuple(
                (dts.get("id") or "", float(dts.get("score") or 0.0))
                for dts in (entry.get("datatypeScores") or [])
                if dts.get("id")
            )
            overall = entry.get("score")
            if overall is not None:
                try:
                    overall = float(overall)
                except (TypeError, ValueError):
                    overall = None
            rows.append(
                OpenTargetsAssociationRow(
                    ensembl_id=ensembl_id,
                    target_symbol=target.get("approvedSymbol"),
                    target_name=target.get("approvedName"),
                    query=query,
                    disease_id=str(disease.get("id") or ""),
                    disease_name=str(disease.get("name") or ""),
                    therapeutic_areas=ta,
                    overall_score=overall,
                    datatype_scores=dt_scores,
                )
            )
        return rows[:size]

    def _gql(self, query: str, variables: dict) -> dict:
        body = json.dumps(
            {"query": query, "variables": variables}
        ).encode("utf-8")
        try:
            raw = self._fetcher(_GQL_URL, body=body)
        except TypeError:
            try:
                raw = self._fetcher(_GQL_URL)
            except DiscoverRefused:
                raise
            except Exception as exc:
                raise NetworkError(
                    f"GraphQL POST failed: {_GQL_URL}: {exc}"
                ) from exc
        except DiscoverRefused:
            raise
        except Exception as exc:
            raise NetworkError(
                f"GraphQL POST failed: {_GQL_URL}: {exc}"
            ) from exc
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NetworkError(
                f"OpenTargets response is not valid JSON: {exc}"
            ) from exc
        if data.get("errors"):
            messages = [
                (e.get("message") or "graphql error")
                for e in data["errors"]
            ]
            raise NetworkError(
                "OpenTargets GraphQL error: " + "; ".join(messages)
            )
        return data


def render_markdown(
    query: str, rows: list[OpenTargetsAssociationRow]
) -> str:
    lines: list[str] = []
    lines.append(f"## Open Targets (live_opentargets, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No Open Targets associated diseases for this target._")
        return "\n".join(lines)
    for r in rows:
        head = (
            f"- **{r.target_symbol or r.ensembl_id}** ↔ {r.disease_name} "
            f"({r.disease_id})"
        )
        if r.overall_score is not None:
            head += f"  \n  Overall score: {r.overall_score:.3f}"
        if r.therapeutic_areas:
            head += f"  \n  Areas: {', '.join(r.therapeutic_areas[:3])}"
        if r.datatype_scores:
            top = ", ".join(
                f"{k}={v:.2f}" for k, v in r.datatype_scores[:4]
            )
            head += f"  \n  Datasources: {top}"
        head += f"  \n  {r.url}"
        lines.append(head)
    return "\n".join(lines)


def render_json(
    query: str, rows: list[OpenTargetsAssociationRow]
) -> str:
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_OPENTARGETS.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
