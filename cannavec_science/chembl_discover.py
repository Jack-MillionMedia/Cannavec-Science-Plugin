"""Live ChEMBL discovery — compound bioactivity + mechanism + ADMET.

Spec 002 User Story 1. Mirrors the cannavec.pubmed_search pattern:
stdlib-only urllib transport, injected ``Fetcher`` for offline tests,
safety + banned-pattern preflight via cannavec.discover_guard BEFORE
any network call.

ChEMBL public REST endpoints used:

- ``…/molecule.json?molecule_synonyms__synonyms__iexact={name}``
  — resolve compound name → ChEMBL ID + molecule_properties (ADMET).
- ``…/molecule/{chembl_id}.json``
  — fetch compound by ChEMBL ID directly.
- ``…/activity.json?molecule_chembl_id={chembl_id}&limit={n}``
  — bioactivity rows (Ki / IC50 / EC50 / etc. against named targets).
- ``…/mechanism.json?molecule_chembl_id={chembl_id}``
  — mechanism of action (optional; advisory only — bioactivity rows
  are the primary deliverable).

Each emitted row carries ``provenance=live_chembl`` and never
auto-promotes to the curated registry (FR-018). The suggested-grade
heuristic carries the ``(provisional, live_chembl)`` suffix per
Constitution Principle VI.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from cannavec_science._http import TIMEOUT_FAST, retry_urlopen, user_agent
from cannavec_science.discover_guard import DiscoverRefused, Provenance, preflight


__all__ = [
    "ChEMBLBioactivityRow",
    "ChEMBLSearcher",
    "NetworkError",
    "default_chembl_fetcher",
    "render_markdown",
    "render_json",
]


# ── URLs ──────────────────────────────────────────────────────────────


_CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_MOLECULE_SEARCH_URL = (
    _CHEMBL_BASE
    + "/molecule.json?molecule_synonyms__synonyms__iexact={name}&limit=5"
)
# Fallback when iexact misses: ChEMBL stores Δ⁹-THC under TETRAHYDROCANNABINOL /
# dronabinol / Delta9-THC, so a bare "THC" iexact returns zero molecules. A
# bounded substring (icontains) search resolves the §VI-named cannabinoids
# instead of silently returning no rows. Kept to limit=5 so it stays one
# bounded request.
_MOLECULE_SEARCH_ICONTAINS_URL = (
    _CHEMBL_BASE
    + "/molecule.json?molecule_synonyms__synonyms__icontains={name}&limit=5"
)
_MOLECULE_DETAIL_URL = _CHEMBL_BASE + "/molecule/{chembl_id}.json"
_ACTIVITY_URL = (
    _CHEMBL_BASE + "/activity.json?molecule_chembl_id={chembl_id}&limit={limit}"
)
_MECHANISM_URL = (
    _CHEMBL_BASE + "/mechanism.json?molecule_chembl_id={chembl_id}"
)

_COMPOUND_REPORT_URL = (
    "https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/"
)

_MAX_RESULTS_CEILING = 50

# Suggested-grade heuristic — ChEMBL rows are mechanistic / pre-clinical.
# Their evidence weight for a CLINICAL claim is C at best. Without
# clinical anchoring, the safest provisional grade is C.
_SUGGESTED_GRADE = "Level C (provisional, live_chembl)"


# ── Exceptions ────────────────────────────────────────────────────────


class NetworkError(Exception):
    """Raised when a ChEMBL fetch fails (HTTP error, timeout, JSON
    parse error).

    Distinct from :class:`DiscoverRefused` (raised by the safety
    preflight before any network call): a NetworkError surfaces an
    operational problem the caller may want to retry or report.
    """


# ── Fetcher ───────────────────────────────────────────────────────────


Fetcher = Callable[[str], str]


def default_chembl_fetcher(url: str) -> str:
    """Production fetcher — polite User-Agent, fast timeout, bounded retry.

    Tests inject a stub fetcher; in production we hit the EBI host via
    :func:`retry_urlopen` so transient 429 / 503 responses are backed off
    before surfacing to the caller.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent("chembl-discover"),
            "Accept": "application/json",
        },
    )
    with retry_urlopen(req, timeout=TIMEOUT_FAST) as resp:
        raw = resp.read()
    return raw.decode("utf-8")


# ── Row dataclass ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChEMBLBioactivityRow:
    chembl_id: str
    target_chembl_id: str
    target_name: str
    target_uniprot_id: Optional[str]
    assay_description: str
    assay_type: str
    activity_value: Optional[float]
    activity_units: Optional[str]
    activity_type: Optional[str]
    confidence_score: Optional[int]
    source_pmid: Optional[str]
    suggested_grade: str
    # WS3 — fields the real ChEMBL /activity endpoint actually returns (default
    # None so legacy fixtures, direct constructions, and the rare embedded-target
    # case still build). pchembl_value (-log10 molar potency) is present on
    # essentially every quantitative row and is the always-available ranking
    # key; standard_relation preserves Ki/IC50 censoring ('>' / '<');
    # document_chembl_id recovers a citable record id when no PMID is present.
    pchembl_value: Optional[float] = None
    standard_relation: Optional[str] = None
    target_organism: Optional[str] = None
    document_year: Optional[int] = None
    document_chembl_id: Optional[str] = None
    source: Provenance = Provenance.LIVE_CHEMBL
    retraction_status: str = "ok"
    url: str = ""
    native_id: str = ""
    title: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        # Defaults derived from chembl_id when caller didn't set them.
        # Use object.__setattr__ because dataclass is frozen.
        if not self.native_id:
            object.__setattr__(self, "native_id", self.chembl_id)
        if not self.title:
            object.__setattr__(
                self,
                "title",
                f"{self.chembl_id} @ {self.target_name or 'unknown target'}",
            )
        if not self.url:
            object.__setattr__(
                self,
                "url",
                _COMPOUND_REPORT_URL.format(chembl_id=self.chembl_id),
            )
        if not self.citation:
            if self.source_pmid:
                object.__setattr__(
                    self, "citation", f"PMID {self.source_pmid}"
                )
            elif self.document_chembl_id:
                object.__setattr__(
                    self,
                    "citation",
                    f"ChEMBL document {self.document_chembl_id}",
                )
            else:
                object.__setattr__(
                    self,
                    "citation",
                    f"ChEMBL {self.chembl_id} bioactivity record",
                )

    def to_dict(self) -> dict:
        d = asdict(self)
        # Keep `source` as a string for JSON round-trip (the enum is
        # itself a str subclass; asdict preserves the enum object).
        d["source"] = self.source.value
        return d


# ── Searcher ──────────────────────────────────────────────────────────


class ChEMBLSearcher:
    """Live ChEMBL search with injected-fetcher fixtures.

    Production callers leave ``fetcher`` at None to use the polite
    default. Tests inject a stub fetcher so the suite runs offline.
    """

    def __init__(self, *, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or default_chembl_fetcher

    # ── Public API ───────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[ChEMBLBioactivityRow]:
        """Resolve compound → bioactivity rows.

        Raises :class:`DiscoverRefused` when the safety preflight or
        banned-pattern detector rejects the query (no network call).
        Raises :class:`ValueError` for invalid arguments.
        Raises :class:`NetworkError` for transport or parsing failures.
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= _MAX_RESULTS_CEILING:
            raise ValueError(
                f"max_results must be in [1, {_MAX_RESULTS_CEILING}]; "
                f"got {max_results}"
            )

        # FR-002: preflight BEFORE any network call.
        preflight(query)

        compound = self._resolve_compound(query)
        if compound is None:
            return []

        chembl_id = compound["molecule_chembl_id"]
        rows = self._fetch_bioactivity(chembl_id, max_results)
        return _sort_rows(rows)[:max_results]

    def fetch_compound(self, chembl_id: str) -> Optional[dict]:
        """Fetch a single ChEMBL compound record by ID (spec 003 US5 / FR-005).

        Returns the raw molecule dict (with ``molecule_chembl_id``,
        ``pref_name``, ``molecule_properties`` keys) or ``None`` when
        the ID is malformed or unresolved.
        """
        q = (chembl_id or "").strip().upper()
        if not (q.startswith("CHEMBL") and q[6:].isdigit()):
            raise ValueError(
                f"ChEMBL IDs must match ^CHEMBL\\d+$; got {chembl_id!r}"
            )
        preflight(q)
        url = _MOLECULE_DETAIL_URL.format(chembl_id=q)
        try:
            data = self._fetch_json(url)
        except NetworkError:
            return None
        if "molecule_chembl_id" in data:
            return data
        return None

    # ── Internals ────────────────────────────────────────────────────

    def _resolve_compound(self, query: str) -> Optional[dict]:
        """Return the first compound match, or None if not found.

        If the query is already a ChEMBL ID (CHEMBL<digits>), hit the
        detail endpoint directly. Otherwise resolve via synonym search.
        """
        q = query.strip()
        if q.upper().startswith("CHEMBL") and q[6:].isdigit():
            url = _MOLECULE_DETAIL_URL.format(chembl_id=q.upper())
            data = self._fetch_json(url)
            # Detail endpoint returns the compound directly, not in a list.
            if "molecule_chembl_id" in data:
                return data
            return None

        url = _MOLECULE_SEARCH_URL.format(name=urllib.parse.quote(q))
        data = self._fetch_json(url)
        molecules = data.get("molecules") or []
        if molecules:
            return molecules[0]
        # iexact requires the query to equal a stored synonym exactly, so a bare
        # cannabinoid token ("THC") resolves to nothing. Fall back to a single
        # bounded substring search. But icontains is a substring match, so an
        # ambiguous token ("THC" matches THCV / THCA / dronabinol / …) can
        # return several distinct cannabinoids — taking molecules[0] would risk
        # surfacing the WRONG isomer's bioactivity as the queried compound's
        # (§VI phytochemistry precision). Only accept an UNAMBIGUOUS single hit;
        # otherwise return None — a safe "no rows" beats a wrong-compound answer.
        url = _MOLECULE_SEARCH_ICONTAINS_URL.format(name=urllib.parse.quote(q))
        data = self._fetch_json(url)
        molecules = data.get("molecules") or []
        if len(molecules) == 1:
            return molecules[0]
        return None

    def _fetch_bioactivity(
        self, chembl_id: str, limit: int,
    ) -> list[ChEMBLBioactivityRow]:
        # Ask for more than `limit` so the sort+cap downstream has
        # headroom. ChEMBL itself caps at 1000 per page.
        ask = min(limit * 5, 50)
        url = _ACTIVITY_URL.format(chembl_id=chembl_id, limit=ask)
        data = self._fetch_json(url)
        activities = data.get("activities") or []

        rows: list[ChEMBLBioactivityRow] = []
        for a in activities:
            rows.append(_parse_activity(a, chembl_id))
        return rows

    def _fetch_json(self, url: str) -> dict:
        try:
            body = self._fetcher(url)
        except DiscoverRefused:
            raise
        except Exception as exc:  # urllib HTTPError, URLError, OSError, etc.
            raise NetworkError(f"fetch failed: {url}: {exc}") from exc

        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NetworkError(
                f"ChEMBL response is not valid JSON for {url}: {exc}"
            ) from exc


# ── Parsing helpers ───────────────────────────────────────────────────


def _as_float(value) -> Optional[float]:
    """Coerce a ChEMBL numeric field to float, or None when absent/malformed."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> Optional[int]:
    """Coerce a ChEMBL integer field to int, or None when absent/malformed."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_activity(
    a: dict, chembl_id: str
) -> ChEMBLBioactivityRow:
    """Build a ChEMBLBioactivityRow from one /activity row.

    Reads the fields the REAL EBI /activity endpoint returns (pchembl_value,
    standard_relation, target_organism, document_year, document_chembl_id) and
    still best-effort reads confidence_score / target_components for the rare
    response that embeds them — neither is on the /activity endpoint (they live
    on /assay and /target). Every optional field uses ``.get()`` so a missing
    key surfaces as None, not a KeyError.
    """
    target_components = a.get("target_components") or []
    uniprot = None
    if target_components:
        uniprot = target_components[0].get("accession")
        if isinstance(uniprot, list):
            uniprot = uniprot[0] if uniprot else None

    return ChEMBLBioactivityRow(
        chembl_id=a.get("molecule_chembl_id") or chembl_id,
        target_chembl_id=a.get("target_chembl_id") or "",
        target_name=a.get("target_pref_name") or "",
        target_uniprot_id=uniprot,
        assay_description=a.get("assay_description") or "",
        assay_type=a.get("assay_type") or "",
        activity_value=_as_float(a.get("standard_value")),
        activity_units=a.get("standard_units"),
        activity_type=a.get("standard_type"),
        confidence_score=_as_int(a.get("confidence_score")),
        source_pmid=None,
        suggested_grade=_SUGGESTED_GRADE,
        pchembl_value=_as_float(a.get("pchembl_value")),
        standard_relation=a.get("standard_relation"),
        target_organism=a.get("target_organism"),
        document_year=_as_int(a.get("document_year")),
        document_chembl_id=a.get("document_chembl_id"),
    )


def _sort_rows(
    rows: list[ChEMBLBioactivityRow],
) -> list[ChEMBLBioactivityRow]:
    """Sort by pchembl_value desc, then confidence desc, then activity asc,
    then chembl_id — None always last for each key.

    pchembl_value (-log10 molar potency) is present on essentially every real
    quantitative /activity row, so it is the primary potency key (higher =
    more potent → first). confidence_score is an /assay-level field absent on
    the /activity endpoint, so it is kept only as a secondary tie-break for any
    caller that still supplies it (it no longer collapses every row into one
    bucket). Smaller IC50/Ki then breaks remaining ties.
    """
    def key(r: ChEMBLBioactivityRow):
        # Ascending sort: negate "higher = better" keys; push None to the end.
        pchembl_key = (
            -r.pchembl_value if r.pchembl_value is not None else float("inf")
        )
        conf_key = (
            -r.confidence_score
            if r.confidence_score is not None
            else float("inf")
        )
        act_key = (
            r.activity_value if r.activity_value is not None else float("inf")
        )
        return (pchembl_key, conf_key, act_key, r.chembl_id)

    return sorted(rows, key=key)


# ── Renderers ─────────────────────────────────────────────────────────


def render_markdown(
    query: str, rows: list[ChEMBLBioactivityRow]
) -> str:
    """Render hits as a Markdown section.

    Mirrors the cannavec.pubmed_search.render_markdown shape. The
    ``live_chembl, provisional`` header is mandatory — readers MUST
    distinguish live-discovery rows from curated-registry claims.
    """
    lines: list[str] = []
    lines.append(f"## ChEMBL (live_chembl, provisional) — {query}")
    lines.append("")
    if not rows:
        lines.append("_No bioactivity rows found in ChEMBL for this query._")
        return "\n".join(lines)
    for r in rows:
        activity = "—"
        relation = "="
        if r.activity_value is not None and r.activity_units:
            # Preserve censoring: a '>' / '<' Ki/IC50 bound renders with its own
            # operator (e.g. "Ki > 10000 nM") so it is never shown as a hard
            # equality. '=' / '~' / absent relations keep the default separator.
            rel = (r.standard_relation or "").strip()
            if rel and rel not in ("=", "~"):
                relation = rel
            activity = f"{r.activity_value:g} {r.activity_units}"
        conf = f"conf {r.confidence_score}" if r.confidence_score is not None else "conf n/a"
        line = (
            f"- **{r.chembl_id}** @ {r.target_name} "
            f"({r.target_chembl_id})"
        )
        if r.target_uniprot_id:
            line += f" [UniProt {r.target_uniprot_id}]"
        line += (
            f" — {r.activity_type or '?'} {relation} {activity} "
            f"({r.assay_type or '?'}, {conf})."
        )
        if r.url:
            line += f"  \n  {r.url}"
        lines.append(line)
    return "\n".join(lines)


def render_json(
    query: str, rows: list[ChEMBLBioactivityRow]
) -> str:
    """Render hits as JSON per the contract."""
    payload = {
        "query": query,
        "provenance": Provenance.LIVE_CHEMBL.value,
        "hits": [r.to_dict() for r in rows],
    }
    return json.dumps(payload, indent=2)
