"""SQLite verified-source cache — the live-retrieval flywheel (M2).

This is **not** the archived §IX curation flywheel. That one staged verified
sources for human promotion *into the curated registry*, which grows the
static-answer substrate the constitution names an anti-pattern (M5). This
module is the opposite: it caches §I-verified, non-retracted **live** sources
to accelerate and harden the *grounding* layer —

- **Write-through (KB growth):** every successful live discovery upserts the
  rows that carry a resolvable primary identifier and a clean retraction status.
  The offline store of real primary sources grows with every query.
- **Read (speed + resilience):** the same query — or an explicit offline run —
  can be served from the store when the live upstreams are unreachable.

Cached rows stay in the live / provisional tier: they are never promoted to the
curated registry (§IX) and never feed the static generator (M5). Retraction is
**re-checked on every read** (§VIII): a source clean when cached but retracted
later is dropped, never served.

Design constraints (constitution):

- **Stdlib only** — :mod:`sqlite3`. No pip install (§X).
- **Offline-testable** — every entry takes an optional ``store_dir`` so the
  suite writes to a tmp dir, and a ``is_retracted`` checker is injectable so the
  retraction re-check runs without the registry singleton.
- **Degrade silently** — a read-only filesystem (serverless), a missing file, or
  a corrupt row must never break discovery. Every public function swallows store
  faults and returns a safe empty/zero result.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Callable, Optional

from cannavec_science.intent import distill_query
from cannavec_science.retraction import is_retracted as _default_is_retracted

__all__ = [
    "cache_dir",
    "db_file",
    "resolve_identifier",
    "normalize_query",
    "record_discovery",
    "fetch_for_query",
    "stats",
    "CACHE_FILENAME",
]

CACHE_FILENAME = "live_cache.sqlite3"

_PKG_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Citable primary identifiers, in the SAME resolution order the live-finding
# builder uses (answer.live_finding_from_row). ``efo_id`` / ``pathway_id`` are
# deliberately excluded: an ontology id is not a citable primary source, so an
# ontology-only row never enters the verified-source store (§I).
_ID_FIELDS: tuple[str, ...] = (
    "pmid",
    "nct_id",
    "activity_id",
    "cid",
    "pdb_id",
    "accession_id",
    "ensembl_id",
    "monomer_id",
    "chembl_id",
    "chebi_id",
    "go_id",
    "doi",
)

# Retraction states that bar a row from being cached / served. ``corrected`` is
# NOT here — a correction is not a retraction (mirrors retraction.is_retracted).
_FLAGGED_STATES = frozenset(
    {"retracted", "expression_of_concern", "under_correction"}
)

IsRetracted = Callable[..., object]

# Default ceiling on the verified-source store so a long-lived operator cache
# cannot grow without limit. Generous for a research cache; override with
# CANNAVEC_CACHE_MAX_SOURCES.
_DEFAULT_MAX_SOURCES = 5000


def _max_sources() -> int:
    try:
        return max(100, int(os.environ.get("CANNAVEC_CACHE_MAX_SOURCES", "")))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_SOURCES


def _prune(conn: sqlite3.Connection, *, max_sources: int) -> int:
    """Evict the lowest-value verified_sources rows beyond ``max_sources``.

    Value order keeps the freshest, most-hit rows: rows are evicted by
    ``last_verified ASC, hit_count ASC`` (oldest, least-hit first). Their now
    orphaned ``query_hits`` are deleted too, so the index does not leak. Returns
    the number of source rows evicted (0 when under the cap).
    """
    total = conn.execute("SELECT COUNT(*) FROM verified_sources").fetchone()[0]
    if total <= max_sources:
        return 0
    over = total - max_sources
    conn.execute(
        "DELETE FROM verified_sources WHERE citation_key IN ("
        "SELECT citation_key FROM verified_sources "
        "ORDER BY last_verified ASC, hit_count ASC LIMIT ?)",
        (over,),
    )
    conn.execute(
        "DELETE FROM query_hits WHERE citation_key NOT IN "
        "(SELECT citation_key FROM verified_sources)"
    )
    return over


def cache_dir(store_dir: Optional[str] = None) -> str:
    """Resolve the cache directory.

    Precedence: explicit ``store_dir`` > ``CANNAVEC_CACHE_DIR`` env > a
    ``live_cache`` subdir of the package ``data/`` directory. Created if missing.
    On a read-only filesystem the ``makedirs`` raises; callers wrap this so a
    serverless deploy degrades to "no cache" rather than crashing.
    """
    d = store_dir or os.environ.get("CANNAVEC_CACHE_DIR") or os.path.join(
        _PKG_DATA, "live_cache"
    )
    os.makedirs(d, exist_ok=True)
    return d


def db_file(store_dir: Optional[str] = None) -> str:
    """Absolute path to the SQLite file inside the resolved cache directory."""
    return os.path.join(cache_dir(store_dir), CACHE_FILENAME)


def _connect(store_dir: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file(store_dir))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_sources (
    citation_key      TEXT PRIMARY KEY,
    identifier        TEXT NOT NULL,
    id_kind           TEXT NOT NULL,
    source_lane       TEXT,
    title             TEXT,
    year              TEXT,
    url               TEXT,
    grade             TEXT,
    retraction_status TEXT NOT NULL DEFAULT 'clean',
    row_json          TEXT NOT NULL,
    first_seen        TEXT NOT NULL,
    last_verified     TEXT NOT NULL,
    hit_count         INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS query_hits (
    query_norm   TEXT NOT NULL,
    citation_key TEXT NOT NULL,
    seen_at      TEXT NOT NULL,
    PRIMARY KEY (query_norm, citation_key)
);
CREATE INDEX IF NOT EXISTS idx_query_hits_q ON query_hits(query_norm);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_identifier(row: dict) -> Optional[tuple[str, str]]:
    """Return ``(id_kind, value)`` for the row's headline citable identifier.

    Resolution order mirrors the live-finding builder. Returns ``None`` for a
    row with no citable primary identifier (ontology-only or title-only rows),
    so such rows are never cached as if they were sources.
    """
    if not isinstance(row, dict):
        return None
    for kind in _ID_FIELDS:
        v = row.get(kind)
        if v:
            return kind, str(v)
    return None


def _is_flagged(row: dict, checker: IsRetracted) -> bool:
    """True if the row is retracted / EOC / under-correction — by its own stored
    status OR by a live re-check against the retraction registry."""
    status = (row.get("retraction_status") or "").strip().lower()
    if status in _FLAGGED_STATES:
        return True
    pmid = row.get("pmid")
    doi = row.get("doi")
    if not (pmid or doi):
        return False
    rec = checker(pmid=str(pmid) if pmid else None, doi=str(doi) if doi else None)
    if rec is None:
        return False
    rec_status = str(getattr(rec, "status", "") or "").lower()
    # A bare record with no parseable status is treated as flagged (fail-safe);
    # an explicit "corrected" is allowed through.
    return rec_status != "corrected"


def normalize_query(query: str) -> str:
    """Deterministic cache key for a query.

    Distils interrogative scaffolding (so "What is X?" and "X" collapse) then
    lowercases and collapses whitespace. Order-preserving and predictable —
    semantic / fuzzy matching is deliberately out of scope (§X offline core).
    """
    distilled = distill_query(query or "")
    return " ".join(distilled.lower().split())


def record_discovery(
    query: str,
    sources_payload: dict,
    *,
    store_dir: Optional[str] = None,
    is_retracted: Optional[IsRetracted] = None,
    now: Optional[str] = None,
    max_sources: Optional[int] = None,
) -> int:
    """Write-through: cache every verified, non-retracted row from a discovery.

    A row is admitted iff it has a resolvable primary identifier (§I) and is not
    currently flagged retracted/EOC (§VIII). Returns the number of rows
    recorded. The store is bounded: after the write it is pruned to
    ``max_sources`` rows (default :func:`_max_sources`), evicting the oldest,
    least-hit sources. All store faults degrade to a partial/zero count — never
    raise.
    """
    checker = is_retracted or _default_is_retracted
    cap = max_sources if max_sources is not None else _max_sources()
    qn = normalize_query(query)
    if not qn:
        return 0
    ts = now or _utcnow()
    try:
        conn = _connect(store_dir)
    except Exception:  # noqa: BLE001 — read-only fs / locked db: no cache, no crash
        return 0
    cached = 0
    try:
        with conn:
            for lane, val in sources_payload.items():
                if not isinstance(val, list):
                    continue
                for row in val:
                    ident = resolve_identifier(row)
                    if ident is None or _is_flagged(row, checker):
                        continue
                    kind, value = ident
                    ckey = f"{kind}:{value}"
                    conn.execute(
                        "INSERT INTO verified_sources (citation_key, identifier, "
                        "id_kind, source_lane, title, year, url, grade, "
                        "retraction_status, row_json, first_seen, last_verified, "
                        "hit_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1) "
                        "ON CONFLICT(citation_key) DO UPDATE SET "
                        "last_verified=excluded.last_verified, "
                        "row_json=excluded.row_json, "
                        "retraction_status=excluded.retraction_status, "
                        "hit_count=verified_sources.hit_count+1",
                        (
                            ckey, value, kind,
                            row.get("source_tag") or row.get("source") or lane,
                            row.get("title") or row.get("label") or "",
                            str(row.get("year") or ""),
                            row.get("url") or "",
                            row.get("grade") or "",
                            (row.get("retraction_status") or "clean"),
                            json.dumps(row, default=str, ensure_ascii=False),
                            ts, ts,
                        ),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO query_hits (query_norm, "
                        "citation_key, seen_at) VALUES (?,?,?)",
                        (qn, ckey, ts),
                    )
                    cached += 1
            # Bound the store: evict the oldest, least-hit sources beyond the cap.
            _prune(conn, max_sources=cap)
    except Exception:  # noqa: BLE001 — never let a cache write break discovery
        pass
    finally:
        conn.close()
    return cached


def fetch_for_query(
    query: str,
    *,
    store_dir: Optional[str] = None,
    max_results: int = 25,
    is_retracted: Optional[IsRetracted] = None,
) -> list[dict]:
    """Return cached rows for ``query``, retraction RE-CHECKED on read (§VIII).

    Rows now flagged retracted/EOC are dropped — a source clean when cached but
    retracted later is never served. Each returned row is tagged
    ``from_cache=True``. Missing/corrupt store → empty list (degrade, no crash).
    """
    checker = is_retracted or _default_is_retracted
    qn = normalize_query(query)
    if not qn:
        return []
    try:
        conn = _connect(store_dir)
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    try:
        cur = conn.execute(
            "SELECT v.row_json FROM query_hits q "
            "JOIN verified_sources v ON v.citation_key = q.citation_key "
            "WHERE q.query_norm = ? ORDER BY v.hit_count DESC, q.seen_at DESC "
            "LIMIT ?",
            (qn, max(1, int(max_results))),
        )
        for (row_json,) in cur.fetchall():
            try:
                row = json.loads(row_json)
            except Exception:  # noqa: BLE001 — skip a corrupt row, keep the rest
                continue
            if not isinstance(row, dict) or _is_flagged(row, checker):
                continue
            row["from_cache"] = True
            out.append(row)
    except Exception:  # noqa: BLE001
        pass
    finally:
        conn.close()
    return out


def stats(store_dir: Optional[str] = None) -> dict:
    """Cache size summary for an operator surface. Degrades to zeros on fault."""
    try:
        conn = _connect(store_dir)
    except Exception:  # noqa: BLE001
        return {"sources": 0, "queries": 0}
    try:
        sources = conn.execute(
            "SELECT COUNT(*) FROM verified_sources"
        ).fetchone()[0]
        queries = conn.execute(
            "SELECT COUNT(DISTINCT query_norm) FROM query_hits"
        ).fetchone()[0]
        return {"sources": int(sources), "queries": int(queries)}
    except Exception:  # noqa: BLE001
        return {"sources": 0, "queries": 0}
    finally:
        conn.close()
