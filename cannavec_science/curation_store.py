"""Append-only JSONL stores for the curation flywheel (Constitution §IX).

The §IX flywheel — *discovered row → gate → human-approved → curated* — needs
three durable, auditable, reversible ledgers:

- ``staging_queue.jsonl`` — candidates that cleared (or failed) the deterministic
  gate, awaiting a human curator's promote/reject decision. One record per
  identifier per decision state.
- ``verified_sources.jsonl`` — the **verified tier**: sources a human approved
  *through* the gate. Distinct from both the raw candidate pool
  (``primary_source_index.csv``) and the hand-authored registry ``.py`` modules.
- ``demand_log.jsonl`` — the misses ledger (see :mod:`cannavec_science.demand`).

Why a new store rather than the index ``curated`` flag: ``test_source_index_
integrity`` enforces that ``curated=true`` in the CSV *iff* the identifier is
hand-written into a registry module. The verified tier is a third thing — a
gate-passed citable source that has **not** been authored into a registry
narrative — so it lives in its own ledger and never trips that invariant.

Stdlib only. Every public entry takes an optional ``store_dir`` so the offline
test-suite writes to a tmp dir and never mutates the shipped ``data/``. In
production the dir resolves from ``CANNAVEC_CURATION_DIR`` or the package
``data/`` directory.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

__all__ = [
    "STAGING_FILE",
    "VERIFIED_FILE",
    "DEMAND_FILE",
    "data_dir",
    "store_path",
    "read_jsonl",
    "append_jsonl",
    "rewrite_jsonl",
    "utcnow",
]

STAGING_FILE = "staging_queue.jsonl"
VERIFIED_FILE = "verified_sources.jsonl"
DEMAND_FILE = "demand_log.jsonl"

_PKG_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def data_dir(store_dir: str | None = None) -> str:
    """Resolve the curation-store directory.

    Precedence: explicit ``store_dir`` arg > ``CANNAVEC_CURATION_DIR`` env >
    the package ``data/`` directory. The directory is created if missing so a
    first write never fails on a fresh checkout.
    """
    d = store_dir or os.environ.get("CANNAVEC_CURATION_DIR") or _PKG_DATA
    os.makedirs(d, exist_ok=True)
    return d


def store_path(filename: str, store_dir: str | None = None) -> str:
    """Absolute path to ``filename`` inside the resolved store directory."""
    return os.path.join(data_dir(store_dir), filename)


def utcnow() -> str:
    """ISO-8601 UTC timestamp (seconds precision) for audit fields."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_jsonl(filename: str, store_dir: str | None = None) -> list[dict]:
    """Read every record from a JSONL store. Missing file → empty list.

    Blank lines and unparseable lines are skipped (a partially-written tail
    never crashes a reader), so the store degrades gracefully.
    """
    path = store_path(filename, store_dir)
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def append_jsonl(filename: str, record: dict, store_dir: str | None = None) -> None:
    """Append one record as a single JSON line (the durable audit event)."""
    path = store_path(filename, store_dir)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")


def rewrite_jsonl(
    filename: str, records: list[dict], store_dir: str | None = None
) -> None:
    """Atomically replace the store with ``records``.

    Used for in-place state transitions (e.g. a queued candidate becoming
    approved). Writes to a temp file and renames so a crashed write never
    leaves a truncated store.
    """
    path = store_path(filename, store_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
