"""Per-source health probe + persisted state for live discoverers.

Spec 002 User Story 7 (Wave C). Used by:

- ``auditor/doctor.sh --sources`` to render a per-source status table.
- ``cannavec discover`` to short-circuit on all-sources-unreachable.

Health status thresholds:

- **green**  — probe succeeded in < 5 s.
- **yellow** — probe succeeded in 5–15 s.
- **red**    — probe failed (error) or took > 15 s.

Stdlib-only, deterministic, no LLM. The probe function is injected so
tests run offline; the default probe issues a HEAD-ish GET against a
documented tiny endpoint per source.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from cannavec_science._http import TIMEOUT_SLOW, user_agent


__all__ = [
    "HealthStatus",
    "SourceHealth",
    "default_probe",
    "load_health_state",
    "ping",
    "ping_all",
    "save_health_state",
]


# ── Constants ────────────────────────────────────────────────────────


_GREEN_LATENCY_S = 5.0
_YELLOW_LATENCY_S = 15.0
# The probe deliberately does NOT use retry_urlopen — its job is to
# observe transient failures, not paper over them.
_DEFAULT_TIMEOUT = TIMEOUT_SLOW

_DEFAULT_STATE_PATH = (
    Path(os.environ.get("CANNAVEC_STATE_DIR", "state")) / "source_health.json"
)

# Per-source probe URLs — tiny endpoints chosen so the probe doesn't
# move much data. Any 200/4xx response counts as "reachable" — we just
# want to confirm the host answers.
_PROBE_URLS = {
    "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi",
    "chembl": "https://www.ebi.ac.uk/chembl/api/data/status.json",
    "ctgov": "https://clinicaltrials.gov/api/v2/version",
    "biorxiv": "https://api.biorxiv.org/details/biorxiv/2024-01-01/2024-01-02/0/json",
    "medrxiv": "https://api.biorxiv.org/details/medrxiv/2024-01-01/2024-01-02/0/json",
    "courtlistener": "https://www.courtlistener.com/api/rest/v4/",
    # Cannabis-primary-source widening (life-science skill layer).
    "pubchem": (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/644019/"
        "property/MolecularFormula/JSON"
    ),
    "pharmgkb": "https://api.pharmgkb.org/v1/data/chemical?name=cannabidiol&view=base",
    "rcsb": "https://data.rcsb.org/rest/v1/core/entry/6N4B",
    "opentargets": "https://api.platform.opentargets.org/api/v4/graphql",
    "gwas": "https://www.ebi.ac.uk/gwas/rest/api/v2/metadata",
    "bindingdb": (
        "https://bindingdb.org/rest/getLigandsByUniprots"
        "?uniprot=P21554&cutoff=10000&response=application/json"
    ),
    # Spec 005 US6 — Europe PMC twelfth primary-source live lane.
    "europepmc": (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        "?query=cannabidiol&resulttype=core&format=json&pageSize=1"
    ),
    # Spec 006 US6 — OpenAlex thirteenth primary-source live lane.
    "openalex": (
        "https://api.openalex.org/works?search=cannabidiol&per_page=1"
    ),
    # Spec 029 — EBI chemical-ontology + functional-annotation lanes.
    "chebi": (
        "https://www.ebi.ac.uk/chebi/backend/api/public/es_search/"
        "?term=cannabidiol&size=1"
    ),
    "quickgo": (
        "https://www.ebi.ac.uk/QuickGO/services/annotation/search"
        "?geneProductId=P21554&limit=1"
    ),
    # Spec 030 — pathway + disease-ontology lanes.
    "reactome": (
        "https://reactome.org/ContentService/data/mapping/UniProt/P21554/"
        "pathways?species=Homo%20sapiens"
    ),
    "efo": (
        "https://www.ebi.ac.uk/ols4/api/search?q=epilepsy&ontology=efo&rows=1"
    ),
}


# ── Enums ────────────────────────────────────────────────────────────


class HealthStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceHealth:
    source: str
    status: HealthStatus
    latency_ms: Optional[int]
    last_success_iso: Optional[str]
    error_excerpt: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "last_success_iso": self.last_success_iso,
            "error_excerpt": self.error_excerpt,
        }


# ── Probe ────────────────────────────────────────────────────────────


Probe = Callable[[str], float]


def default_probe(url: str) -> float:
    """Production probe: issues a GET and returns measured wall-clock
    seconds. Raises the underlying exception on transport error.
    """
    start = time.monotonic()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent("source-health"),
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        # Drain a small read so we know we got something.
        resp.read(64)
    elapsed = time.monotonic() - start
    return elapsed


def ping(source: str, *, probe: Optional[Probe] = None) -> SourceHealth:
    """Probe one source and return its current health snapshot.

    Unknown source name raises ValueError.
    """
    if source not in _PROBE_URLS:
        raise ValueError(
            f"unknown source: {source!r}. Known: {sorted(_PROBE_URLS)}"
        )
    p = probe or default_probe
    url = _PROBE_URLS[source]
    try:
        elapsed = p(url)
    except Exception as exc:
        return SourceHealth(
            source=source,
            status=HealthStatus.RED,
            latency_ms=None,
            last_success_iso=None,
            error_excerpt=_excerpt_error(exc),
        )

    latency_ms = int(elapsed * 1000)
    if elapsed >= _YELLOW_LATENCY_S:
        # Slow enough to be on the edge — treat as RED.
        return SourceHealth(
            source=source,
            status=HealthStatus.RED,
            latency_ms=latency_ms,
            last_success_iso=_iso_now(),
            error_excerpt=f"latency {elapsed:.1f}s exceeds 15s threshold",
        )
    if elapsed >= _GREEN_LATENCY_S:
        return SourceHealth(
            source=source,
            status=HealthStatus.YELLOW,
            latency_ms=latency_ms,
            last_success_iso=_iso_now(),
            error_excerpt=None,
        )
    return SourceHealth(
        source=source,
        status=HealthStatus.GREEN,
        latency_ms=latency_ms,
        last_success_iso=_iso_now(),
        error_excerpt=None,
    )


def ping_all(*, probe: Optional[Probe] = None) -> list[SourceHealth]:
    """Probe every known source. Deterministic order."""
    return [ping(s, probe=probe) for s in sorted(_PROBE_URLS)]


# ── Persistence ──────────────────────────────────────────────────────


def save_health_state(
    results: list[SourceHealth],
    *,
    state_path: Optional[Path] = None,
) -> None:
    """Persist health results to JSON. Parent directory is created if
    missing."""
    path = Path(state_path) if state_path else _DEFAULT_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": _iso_now(),
        "sources": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_health_state(
    *, state_path: Optional[Path] = None,
) -> list[SourceHealth]:
    """Load persisted health snapshots; returns empty list if file
    is missing."""
    path = Path(state_path) if state_path else _DEFAULT_STATE_PATH
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[SourceHealth] = []
    for entry in data.get("sources") or []:
        rows.append(SourceHealth(
            source=entry["source"],
            status=HealthStatus(entry["status"]),
            latency_ms=entry.get("latency_ms"),
            last_success_iso=entry.get("last_success_iso"),
            error_excerpt=entry.get("error_excerpt"),
        ))
    return rows


# ── Helpers ──────────────────────────────────────────────────────────


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _excerpt_error(exc: Exception) -> str:
    """Trim the error message to one short line for the renderer."""
    text = str(exc)
    if len(text) > 200:
        text = text[:197] + "…"
    return text
