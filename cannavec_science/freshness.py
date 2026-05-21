"""Registry freshness + retraction-watch (spec 002 US5).

Curated registry rows decay: a cited PMID may be retracted, an
Expression of Concern issued, or the row's evidence simply re-examined
under a newer SR. The freshness layer surfaces those gaps without
auto-mutating the row — the curator decides whether to update.

Two surfaces:

- :func:`probe_registry(name)` — walk every row of one registry (or all),
  extract its `watch_pmids` (from the row's `last_verified` field /
  `watch_pmids` field, or fall back to PMIDs lifted from the row's
  `citations` tuple), run :func:`pubmed_verify.verify_pmid` +
  :func:`retraction.is_retracted` against each one, and return a
  :class:`FreshnessReport`.

- :func:`stale_suffix(row)` — render-time helper used by ``answer.py``
  to append ``[freshness: stale (verified YYYY-MM-DD)]`` to a citation
  whose backing registry row is older than 365 days.

Constitution mirror (§IX): live discovery rows never auto-promote into
the curated registry. The mirror is: curated rows never auto-invalidate
from a freshness probe. The probe surfaces the gap; the curator does
the update.
"""

from __future__ import annotations

import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional


__all__ = [
    "DEFAULT_LAST_VERIFIED",
    "FreshnessStatus",
    "FreshnessRow",
    "FreshnessReport",
    "all_registry_names",
    "iter_registry_rows",
    "stale_suffix",
    "extract_watch_pmids",
    "probe_registry",
    "render_markdown",
    "render_json",
]


# ── Constants ────────────────────────────────────────────────────────


DEFAULT_LAST_VERIFIED: str = "2026-05-21"
"""Default `last_verified` date for v0.2 registry rows.

Set to the v0.2 spec landing date. Rows whose dataclass does not carry
an explicit `last_verified` field default to this value at probe time.
"""

STALE_THRESHOLD_DAYS_SOFT: int = 180
"""`last_verified` older than this is `last_verified_stale` (soft)."""

STALE_THRESHOLD_DAYS_HARD: int = 365
"""`last_verified` older than this triggers the `[freshness: stale]`
citation suffix at render time."""


# ── Status enum ──────────────────────────────────────────────────────


class FreshnessStatus(str, Enum):
    """Result of probing one registry row's watch_pmids."""

    CLEAN = "clean"
    """Every watch_pmid resolved; none retracted or under correction."""
    RETRACTION_DETECTED = "retraction_detected"
    """At least one watch_pmid is retracted — row is candidate for curator review."""
    EOC_DETECTED = "eoc_detected"
    """At least one watch_pmid carries an Expression of Concern."""
    LAST_VERIFIED_STALE = "last_verified_stale"
    """`last_verified` is older than the soft threshold."""
    NETWORK_ERROR = "network_error"
    """One or more probes failed to reach PubMed."""
    NO_WATCH_PMIDS = "no_watch_pmids"
    """Row has no PMIDs to probe (e.g. URL-only citations)."""


# ── Row + report dataclasses ─────────────────────────────────────────


@dataclass(frozen=True)
class FreshnessRow:
    """One row's probe outcome."""

    registry: str
    row_id: str
    row_label: str
    last_verified: str
    watch_pmids: tuple[str, ...]
    status: FreshnessStatus
    retracted_pmids: tuple[str, ...] = ()
    eoc_pmids: tuple[str, ...] = ()
    network_error_pmids: tuple[str, ...] = ()
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass(frozen=True)
class FreshnessReport:
    """A full registry's per-row freshness state."""

    registry: str
    rows: tuple[FreshnessRow, ...]
    generated_at: str

    @property
    def n_clean(self) -> int:
        return sum(1 for r in self.rows if r.status == FreshnessStatus.CLEAN)

    @property
    def n_retraction(self) -> int:
        return sum(
            1 for r in self.rows if r.status == FreshnessStatus.RETRACTION_DETECTED
        )

    @property
    def n_eoc(self) -> int:
        return sum(1 for r in self.rows if r.status == FreshnessStatus.EOC_DETECTED)

    @property
    def n_stale(self) -> int:
        return sum(
            1 for r in self.rows if r.status == FreshnessStatus.LAST_VERIFIED_STALE
        )

    @property
    def n_network_error(self) -> int:
        return sum(1 for r in self.rows if r.status == FreshnessStatus.NETWORK_ERROR)

    @property
    def n_no_watch(self) -> int:
        return sum(1 for r in self.rows if r.status == FreshnessStatus.NO_WATCH_PMIDS)

    @property
    def clean(self) -> bool:
        return self.n_retraction == 0 and self.n_eoc == 0

    def to_dict(self) -> dict:
        return {
            "registry": self.registry,
            "generated_at": self.generated_at,
            "summary": {
                "total": len(self.rows),
                "clean": self.n_clean,
                "retraction_detected": self.n_retraction,
                "eoc_detected": self.n_eoc,
                "last_verified_stale": self.n_stale,
                "network_error": self.n_network_error,
                "no_watch_pmids": self.n_no_watch,
            },
            "rows": [r.to_dict() for r in self.rows],
        }


# ── Registry enumeration ─────────────────────────────────────────────


def all_registry_names() -> tuple[str, ...]:
    """Names of every freshness-probe-able registry, in canonical order."""
    return (
        "major_cannabinoids",
        "minor_cannabinoids",
        "terpenes",
        "interactions",
        "adverse_events",
        "populations",
        "contraindications",
        "pharmacogenomics",
    )


def iter_registry_rows(name: str) -> Iterable[tuple[str, str, object]]:
    """Yield ``(row_id, row_label, row)`` triples for one registry.

    The triples are stable enough for the freshness probe to identify
    a row across runs (so a curator can diff probe outputs).
    """
    if name == "major_cannabinoids":
        from cannavec_science.major_cannabinoids import all_major_cannabinoids
        for row in all_major_cannabinoids():
            yield (f"major:{row.name}", row.name, row)
    elif name == "minor_cannabinoids":
        from cannavec_science.minor_cannabinoids import all_minor_cannabinoids
        for row in all_minor_cannabinoids():
            yield (f"minor:{row.name}", row.name, row)
    elif name == "terpenes":
        from cannavec_science.terpenes import all_terpenes
        for row in all_terpenes():
            yield (f"terpene:{row.name.value}", row.name.value, row)
    elif name == "interactions":
        from cannavec_science.interactions import all_interactions
        for row in all_interactions():
            label = f"{row.cannabinoid} × {row.partner_drug}"
            yield (f"interaction:{label}", label, row)
    elif name == "adverse_events":
        from cannavec_science.adverse_events import all_adverse_events
        for row in all_adverse_events():
            label = f"{row.cannabinoid} → {row.event}"
            yield (f"ae:{label}", label, row)
    elif name == "populations":
        from cannavec_science.populations import all_populations
        for row in all_populations():
            label = f"{row.cannabinoid} in {row.label}"
            yield (f"population:{label}", label, row)
    elif name == "contraindications":
        from cannavec_science.contraindications import all_contraindications
        for row in all_contraindications():
            label = f"{row.compound} × {row.population}"
            yield (f"contra:{label}", label, row)
    elif name == "pharmacogenomics":
        from cannavec_science.pharmacogenomics import all_pgx_records
        for row in all_pgx_records():
            label = f"{row.cannabinoid} × {row.enzyme} {row.allele_or_variant}"
            yield (f"pgx:{label}", label, row)
    else:
        raise ValueError(
            f"unknown registry: {name!r}; "
            f"expected one of {all_registry_names()}"
        )


# ── Watch-PMID extraction ────────────────────────────────────────────


def extract_watch_pmids(row: object) -> tuple[str, ...]:
    """Lift PMIDs off a registry row's citation graph.

    Order of resolution (first non-empty wins):
    1. The row's explicit ``watch_pmids`` field (if set and non-empty).
    2. Every PMID on every ``citations`` tuple on the row, including
       nested per-evidence-row citation tuples
       (``clinical_evidence[*].citations``, etc.).
    """
    explicit = getattr(row, "watch_pmids", None)
    if explicit:
        return tuple(p for p in explicit if p)

    pmids: list[str] = []
    seen: set[str] = set()

    def _add_pmid(c: object) -> None:
        p = getattr(c, "pmid", None)
        if p and p not in seen:
            seen.add(p)
            pmids.append(p)

    for attr in (
        "citations",
        "clinical_evidence",
        "preclinical_evidence",
        "receptor_activity",
        "human_evidence",
        "pharmacology_citations",
        "preclinical_citations",
        "human_evidence_citations",
    ):
        if not hasattr(row, attr):
            continue
        v = getattr(row, attr) or ()
        for item in v:
            # Direct citation object?
            if hasattr(item, "pmid"):
                _add_pmid(item)
                continue
            # Nested evidence row with its own citations tuple?
            nested = getattr(item, "citations", None)
            if nested:
                for c in nested:
                    _add_pmid(c)

    return tuple(pmids)


def _row_last_verified(row: object) -> str:
    """Resolve `last_verified` for a row, defaulting to v0.2 landing date."""
    v = getattr(row, "last_verified", None)
    return v or DEFAULT_LAST_VERIFIED


# ── Stale-suffix helper ──────────────────────────────────────────────


def _parse_iso(date_str: str) -> Optional[datetime.date]:
    if not date_str:
        return None
    try:
        return datetime.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None


def _age_days(date_str: str, today: Optional[datetime.date] = None) -> Optional[int]:
    parsed = _parse_iso(date_str)
    if parsed is None:
        return None
    today = today or datetime.date.today()
    return (today - parsed).days


def stale_suffix(
    row: object,
    today: Optional[datetime.date] = None,
) -> str:
    """Return the ``[freshness: stale ...]`` suffix to append at render
    time, or an empty string when the row is fresh.

    Fires when the row's ``last_verified`` is older than
    :data:`STALE_THRESHOLD_DAYS_HARD` (365) days.
    """
    lv = _row_last_verified(row)
    age = _age_days(lv, today=today)
    if age is None:
        return ""
    if age >= STALE_THRESHOLD_DAYS_HARD:
        return f" [freshness: stale (verified {lv})]"
    return ""


# ── Probe ────────────────────────────────────────────────────────────


PubMedFetcher = Callable[[str], str]


def _probe_one_row(
    registry: str,
    row_id: str,
    row_label: str,
    row: object,
    fetcher: Optional[PubMedFetcher],
    today: Optional[datetime.date],
) -> FreshnessRow:
    """Probe one row's watch_pmids and classify its freshness."""
    from cannavec_science.pubmed_verify import verify_pmid
    from cannavec_science.retraction import is_retracted

    last_verified = _row_last_verified(row)
    watch_pmids = extract_watch_pmids(row)
    today = today or datetime.date.today()

    if not watch_pmids:
        # Row has no PMIDs to probe — surface the staleness if any.
        age = _age_days(last_verified, today=today)
        if age is not None and age >= STALE_THRESHOLD_DAYS_SOFT:
            return FreshnessRow(
                registry=registry,
                row_id=row_id,
                row_label=row_label,
                last_verified=last_verified,
                watch_pmids=(),
                status=FreshnessStatus.LAST_VERIFIED_STALE,
                note=f"no watch_pmids; last_verified {age} days old",
            )
        return FreshnessRow(
            registry=registry,
            row_id=row_id,
            row_label=row_label,
            last_verified=last_verified,
            watch_pmids=(),
            status=FreshnessStatus.NO_WATCH_PMIDS,
            note="row has no PMID-bearing citations to probe",
        )

    retracted: list[str] = []
    eoc: list[str] = []
    network_error: list[str] = []

    for pmid in watch_pmids:
        # Local registry lookup first — no network call required.
        rec = is_retracted(pmid=pmid)
        if rec is not None:
            status_value = (
                rec.status.value if hasattr(rec.status, "value") else str(rec.status)
            )
            if status_value == "retracted":
                retracted.append(pmid)
                continue
            if status_value in ("expression_of_concern", "eoc"):
                eoc.append(pmid)
                continue

        # PubMed verification (only when fetcher is supplied — keeps the
        # probe offline by default; CLI / curator opts into network).
        if fetcher is not None:
            try:
                result = verify_pmid(pmid, fetcher=fetcher)
            except Exception:
                network_error.append(pmid)
                continue
            if result.verdict.value == "retracted":
                retracted.append(pmid)
            elif result.verdict.value == "network_error":
                network_error.append(pmid)
            elif result.retraction_status == "expression_of_concern":
                eoc.append(pmid)

    if retracted:
        return FreshnessRow(
            registry=registry,
            row_id=row_id,
            row_label=row_label,
            last_verified=last_verified,
            watch_pmids=watch_pmids,
            status=FreshnessStatus.RETRACTION_DETECTED,
            retracted_pmids=tuple(retracted),
            eoc_pmids=tuple(eoc),
            network_error_pmids=tuple(network_error),
            note=f"{len(retracted)} retracted PMIDs detected — curator review required",
        )
    if eoc:
        return FreshnessRow(
            registry=registry,
            row_id=row_id,
            row_label=row_label,
            last_verified=last_verified,
            watch_pmids=watch_pmids,
            status=FreshnessStatus.EOC_DETECTED,
            eoc_pmids=tuple(eoc),
            network_error_pmids=tuple(network_error),
            note=f"{len(eoc)} PMIDs under Expression of Concern",
        )
    if network_error:
        return FreshnessRow(
            registry=registry,
            row_id=row_id,
            row_label=row_label,
            last_verified=last_verified,
            watch_pmids=watch_pmids,
            status=FreshnessStatus.NETWORK_ERROR,
            network_error_pmids=tuple(network_error),
            note=f"{len(network_error)} PMIDs failed to verify",
        )
    # No retractions, no EOCs, no network errors. Check staleness.
    age = _age_days(last_verified, today=today)
    if age is not None and age >= STALE_THRESHOLD_DAYS_SOFT:
        return FreshnessRow(
            registry=registry,
            row_id=row_id,
            row_label=row_label,
            last_verified=last_verified,
            watch_pmids=watch_pmids,
            status=FreshnessStatus.LAST_VERIFIED_STALE,
            note=f"clean PMIDs but last_verified is {age} days old",
        )
    return FreshnessRow(
        registry=registry,
        row_id=row_id,
        row_label=row_label,
        last_verified=last_verified,
        watch_pmids=watch_pmids,
        status=FreshnessStatus.CLEAN,
    )


def probe_registry(
    name: str,
    *,
    fetcher: Optional[PubMedFetcher] = None,
    parallel: int = 1,
    today: Optional[datetime.date] = None,
) -> FreshnessReport:
    """Probe every row of one registry.

    Parameters
    ----------
    name:
        One of :func:`all_registry_names`.
    fetcher:
        Optional PubMed fetcher (e.g. a stub for tests, or
        :func:`cannavec_science.pubmed_verify.default_pubmed_fetcher`
        for live probes). When omitted the probe runs offline using
        only the local retraction registry — fast and safe for CI.
    parallel:
        Number of worker threads for the per-row probe. Default 1
        (serial); the probe is I/O-bound when a network fetcher is
        injected and benefits from a small pool.
    """
    if name not in all_registry_names():
        raise ValueError(
            f"unknown registry: {name!r}; "
            f"expected one of {all_registry_names()}"
        )

    rows_input = list(iter_registry_rows(name))

    def _job(triple: tuple[str, str, object]) -> FreshnessRow:
        row_id, row_label, row = triple
        return _probe_one_row(
            name, row_id, row_label, row, fetcher=fetcher, today=today,
        )

    results: list[FreshnessRow] = []
    if parallel <= 1 or len(rows_input) <= 1:
        for triple in rows_input:
            results.append(_job(triple))
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(_job, t): t for t in rows_input}
            indexed: list[tuple[int, FreshnessRow]] = []
            ordered = list(rows_input)
            for f in as_completed(futures):
                t = futures[f]
                idx = ordered.index(t)
                indexed.append((idx, f.result()))
            indexed.sort(key=lambda p: p[0])
            results = [r for _, r in indexed]

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return FreshnessReport(
        registry=name, rows=tuple(results), generated_at=now,
    )


def probe_all(
    *,
    fetcher: Optional[PubMedFetcher] = None,
    parallel: int = 1,
    today: Optional[datetime.date] = None,
) -> tuple[FreshnessReport, ...]:
    """Probe every registry in canonical order."""
    return tuple(
        probe_registry(n, fetcher=fetcher, parallel=parallel, today=today)
        for n in all_registry_names()
    )


# ── Renderers ────────────────────────────────────────────────────────


def render_markdown(report: FreshnessReport) -> str:
    """Curator-facing per-row table."""
    lines: list[str] = []
    lines.append(f"## Freshness probe — {report.registry}")
    lines.append("")
    lines.append(f"_Generated: {report.generated_at}_")
    lines.append("")
    lines.append(
        f"- Total rows: {len(report.rows)}"
    )
    lines.append(f"- Clean: {report.n_clean}")
    if report.n_retraction:
        lines.append(f"- **Retraction detected: {report.n_retraction}**")
    if report.n_eoc:
        lines.append(f"- Expression of Concern: {report.n_eoc}")
    if report.n_stale:
        lines.append(f"- Last-verified stale (≥ 180d): {report.n_stale}")
    if report.n_network_error:
        lines.append(f"- Network error: {report.n_network_error}")
    if report.n_no_watch:
        lines.append(f"- No watch PMIDs: {report.n_no_watch}")
    lines.append("")
    lines.append("| Row | Status | Watch PMIDs | Note |")
    lines.append("|---|---|---|---|")
    for r in report.rows:
        watch = ",".join(r.watch_pmids[:3])
        if len(r.watch_pmids) > 3:
            watch += f",+{len(r.watch_pmids) - 3}"
        lines.append(f"| {r.row_label} | `{r.status.value}` | {watch or '—'} | {r.note} |")
    return "\n".join(lines)


def render_json(report: FreshnessReport) -> str:
    return json.dumps(report.to_dict(), indent=2)
