"""Primary-source discovery index — a candidate pool for live discovery and
the ranker layer. **These are NOT curated facts.**

The index holds real PubMed / PMC / DOI identifiers harvested from a
cannabis-research library, tagged by topic. Per Constitution §IX a discovered
row never silently becomes a curated fact: anything surfaced from this index
must still pass the deterministic **verify + retraction + GRADE** gate before
it appears in an answer, and the **human-gated apply flow** before it becomes a
curated registry row. The index is deliberately *not* scope-locked (§IV applies
to the curated tier) — discovery may surface any real primary source; only
promotion is gated. The ``curated`` flag marks the identifiers already promoted
into the curated registries.

Stdlib only. Data ships as ``data/primary_source_index.csv``.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from functools import lru_cache

__all__ = [
    "SourceRef",
    "load_index",
    "topics",
    "by_topic",
    "is_curated",
    "candidates",
]

_DATA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "primary_source_index.csv"
)


@dataclass(frozen=True)
class SourceRef:
    """One discovery candidate. ``curated`` = already a curated registry fact."""

    type: str          # PubMed | PMC | DOI
    identifier: str    # PMID / PMCID / DOI string
    url: str
    topic: str
    curated: bool


@lru_cache(maxsize=1)
def load_index() -> tuple[SourceRef, ...]:
    """Load the full discovery index (cached)."""
    with open(_DATA, encoding="utf-8") as fh:
        return tuple(
            SourceRef(
                type=row["type"],
                identifier=row["identifier"],
                url=row["url"],
                topic=row["topic"],
                curated=row["curated"] == "true",
            )
            for row in csv.DictReader(fh)
        )


def topics() -> tuple[str, ...]:
    """Sorted distinct topic tags present in the index."""
    return tuple(sorted({s.topic for s in load_index()}))


def by_topic(topic: str) -> tuple[SourceRef, ...]:
    """All candidates whose topic matches (case-insensitive)."""
    t = topic.strip().lower()
    return tuple(s for s in load_index() if s.topic.lower() == t)


def is_curated(identifier: str) -> bool:
    """True if this identifier is already a curated registry fact."""
    return any(s.identifier == identifier and s.curated for s in load_index())


def candidates(topic: str | None = None, include_curated: bool = True):
    """Discovery candidates, optionally filtered by topic / excluding curated."""
    items = load_index() if topic is None else by_topic(topic)
    if not include_curated:
        items = tuple(s for s in items if not s.curated)
    return items
