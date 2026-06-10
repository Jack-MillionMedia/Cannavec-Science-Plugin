"""Retraction / expression-of-concern detector for cited papers.

A research-grade cannabis system must not cite retracted papers as
primary evidence. This module is the deterministic primitive that
scans an answer's citations against a known-retracted registry and
flags hits.

Three pieces:

- :class:`RetractionRecord` — typed record per retracted paper.
- :func:`is_retracted` — point check by PMID or DOI.
- :func:`scan_text_for_retracted_pmids` — sweep an answer's prose for
  any PMID / DOI matching a registry entry.

The registry is intentionally small and explicitly labelled. Cannavec
does NOT bundle a full Retraction Watch mirror — that lives upstream.
Operators can extend the registry by passing a YAML file path to
:func:`load_registry_from_yaml`. The bundled seed (loaded from
``data/retraction_seed.json``) ships a curated set of REAL
cannabis-relevant retractions ground-truthed against Crossref /
Retraction Watch, plus two clearly-marked synthetic fixtures retained so
the scanner has deterministic placeholders to test against.

The real seed entries key on the ORIGINAL paper's DOI — the identifier a
researcher actually cites — because Crossref's structured
``is_retracted`` flag is *false* on these originals (they carry only a
title-prefix ``RETRACTED:`` notice). The local registry exists precisely
to catch that gap at composition time (§VIII).

Inclusion bar for upstream operators adding entries:

- The paper must appear in PubMed marked as ``Retraction in`` or
  ``Retracted publication``, OR
- The publisher's website carries a retraction notice with date, OR
- Retraction Watch has a public record with a primary-source URL.

Speculation, blog-only allegations, or anonymous tips do NOT meet
the bar. The retraction-status fact must be as well-cited as the
original paper it concerns.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from cannavec_science import _identifiers as _ids


class RetractionStatus(str, Enum):
    RETRACTED = "retracted"
    EXPRESSION_OF_CONCERN = "expression_of_concern"
    UNDER_CORRECTION = "under_correction"
    CORRECTED = "corrected"           # correction issued, paper stands


@dataclass(frozen=True)
class RetractionRecord:
    """A single, citable retraction / EOC / correction record."""

    pmid: str | None
    doi: str | None
    title: str
    journal: str
    year: int
    status: RetractionStatus
    notice_url: str | None
    reason_summary: str
    flagged_at: str               # ISO date when the registry recorded the status
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "pmid": self.pmid,
            "doi": self.doi,
            "title": self.title,
            "journal": self.journal,
            "year": self.year,
            "status": self.status.value,
            "notice_url": self.notice_url,
            "reason_summary": self.reason_summary,
            "flagged_at": self.flagged_at,
            "notes": self.notes,
        }


# ── Seed registry ────────────────────────────────────────────────────
#
# Loaded from data/retraction_seed.json so the curated set is editable
# without code churn (and so the §VIII net ships armed with REAL
# retractions, not just placeholders). The bundled file carries:
#
#  - REAL cannabis-relevant retractions, ground-truthed against Crossref
#    / Retraction Watch (and PubMed's "Retracted Publication" type), keyed
#    on the ORIGINAL paper's DOI — and its PMID where verified — because
#    that is the identifier a citation actually contains; notice_url points
#    at the retraction notice. Crossref's structured is_retracted flag is
#    false on these originals (title-prefix "RETRACTED:" only), which is
#    exactly why the local registry is needed.
#  - Two synthetic fixtures (PMID 99000001 / 99000002, DOI 10.99999/...)
#    in the guaranteed-unused 99000000+ / 10.99999 ranges, retained so
#    the scanner has deterministic placeholders to test against.
#
# Operators replace the whole runtime registry via load_registry_from_yaml().

def _record_from_dict(d: dict[str, object]) -> RetractionRecord:
    status_raw = str(d.get("status") or "retracted")
    try:
        status = RetractionStatus(status_raw)
    except ValueError as e:
        raise ValueError(
            f"unknown retraction status {status_raw!r}; expected one of "
            f"{[s.value for s in RetractionStatus]}"
        ) from e
    return RetractionRecord(
        pmid=d.get("pmid") if isinstance(d.get("pmid"), str) else None,
        doi=d.get("doi") if isinstance(d.get("doi"), str) else None,
        title=str(d.get("title") or "untitled"),
        journal=str(d.get("journal") or "unknown"),
        year=int(d["year"]) if isinstance(d.get("year"), int) else 0,
        status=status,
        notice_url=d.get("notice_url") if isinstance(d.get("notice_url"), str) else None,
        reason_summary=str(d.get("reason_summary") or ""),
        flagged_at=str(d.get("flagged_at") or ""),
        notes=str(d.get("notes") or ""),
    )


_SEED_JSON_PATH = Path(__file__).resolve().parent / "data" / "retraction_seed.json"


def _load_seed_from_json(path: Path) -> tuple[RetractionRecord, ...]:
    """Build the seed registry from the bundled JSON data file.

    There is no silent fallback: a corrupt or missing seed file is a
    packaging error and must surface loudly at import time rather than
    silently disarming the §VIII net.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    records: list[RetractionRecord] = []
    for entry in raw.get("records", ()):
        records.append(_record_from_dict(entry))
    return tuple(records)


_SEED_REGISTRY: tuple[RetractionRecord, ...] = _load_seed_from_json(_SEED_JSON_PATH)


# Operators populate the runtime registry via load_registry_from_yaml.
# Until they do, the seed registry is what scanners see.
_RUNTIME_REGISTRY: list[RetractionRecord] = list(_SEED_REGISTRY)


def all_records() -> tuple[RetractionRecord, ...]:
    """Return the current runtime retraction registry (seed + loaded)."""
    return tuple(_RUNTIME_REGISTRY)


def reset_to_seed() -> None:
    """Reset the runtime registry to the bundled seed entries.

    Useful for tests that want to start from a known state.
    """
    _RUNTIME_REGISTRY.clear()
    _RUNTIME_REGISTRY.extend(_SEED_REGISTRY)


def add_records(records: Iterable[RetractionRecord]) -> None:
    """Append records to the runtime registry.

    Does not dedupe. Operators are responsible for the canonical list.
    """
    _RUNTIME_REGISTRY.extend(records)


def is_retracted(
    *,
    pmid: str | None = None,
    doi: str | None = None,
) -> RetractionRecord | None:
    """Return the matching :class:`RetractionRecord` if found.

    Matches on either PMID or DOI (whichever is supplied). Returns
    None if neither identifier is registered. Records with status
    :attr:`RetractionStatus.CORRECTED` are still returned — callers
    decide how to treat them (a correction is not a retraction).
    """
    if not (pmid or doi):
        return None
    for r in _RUNTIME_REGISTRY:
        if pmid and r.pmid and r.pmid == pmid:
            return r
        if doi and r.doi and r.doi.lower() == doi.lower():
            return r
    return None


# §VIII sweep patterns — centralized in cannavec_science._identifiers (the BARE
# PMID scan, >= 6 digits so a year is not mistaken for a PMID, and the narrower
# DOI trailing class). See that module for the prefixed-verifier siblings.
_PMID_IN_TEXT = _ids.PMID_BARE_SCAN
_DOI_IN_TEXT = _ids.DOI_RETRACTION_SCAN


@dataclass(frozen=True)
class RetractionHit:
    matched_identifier: str
    matched_kind: str              # "pmid" | "doi"
    span: tuple[int, int]
    record: RetractionRecord


def scan_text_for_retracted_pmids(
    text: str,
) -> tuple[RetractionHit, ...]:
    """Sweep ``text`` for any PMID or DOI matching the registry.

    Returns hits in document order. A single text scan checks both
    PMID and DOI patterns; the caller can render the offending span
    and the registry record together.
    """
    hits: list[RetractionHit] = []
    for m in _PMID_IN_TEXT.finditer(text):
        pmid = m.group(1)
        rec = is_retracted(pmid=pmid)
        if rec:
            hits.append(RetractionHit(
                matched_identifier=pmid,
                matched_kind="pmid",
                span=m.span(1),
                record=rec,
            ))
    for m in _DOI_IN_TEXT.finditer(text):
        doi = m.group(1).rstrip(").,;")
        rec = is_retracted(doi=doi)
        if rec:
            hits.append(RetractionHit(
                matched_identifier=doi,
                matched_kind="doi",
                span=m.span(1),
                record=rec,
            ))
    hits.sort(key=lambda h: h.span[0])
    return tuple(hits)


def load_registry_from_yaml(path: str | Path) -> int:
    """Replace the runtime registry from a YAML file.

    The YAML shape is the deliberately minimal one this module's
    :class:`RetractionRecord` carries — each entry must declare
    ``status`` matching :class:`RetractionStatus`. Unknown statuses
    raise. Returns the number of records loaded.

    YAML structure expected::

        records:
          - pmid: "12345678"
            doi: null
            title: "Paper title"
            journal: "Journal name"
            year: 2020
            status: "retracted"
            notice_url: "https://..."
            reason_summary: "Why it was retracted."
            flagged_at: "2026-05-16"
            notes: ""

    PyYAML is not a Cannavec dependency. This loader uses a small
    hand-rolled YAML reader limited to the structure above.
    """
    text = Path(path).read_text(encoding="utf-8")
    records = _parse_minimal_yaml(text)
    _RUNTIME_REGISTRY.clear()
    _RUNTIME_REGISTRY.extend(records)
    return len(records)


def _parse_minimal_yaml(text: str) -> list[RetractionRecord]:
    """Minimal YAML reader for the registry shape only."""
    lines = text.splitlines()
    records: list[RetractionRecord] = []
    current: dict[str, object] | None = None

    def _strip_quote(s: str) -> str:
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or \
           (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if re.match(r"^\s{2}-\s+pmid:", raw):
            if current is not None:
                records.append(_record_from_dict(current))
            current = {}
            _, _, val = raw.partition("pmid:")
            v = _strip_quote(val)
            current["pmid"] = None if v in ("null", "~", "") else v
            continue
        if current is None:
            continue
        m = re.match(r"^\s{4}(\w+):\s*(.*)$", raw)
        if m:
            key, val = m.group(1), _strip_quote(m.group(2))
            if val in ("null", "~", ""):
                current[key] = None
            elif val == "true":
                current[key] = True
            elif val == "false":
                current[key] = False
            elif val.lstrip("-").isdigit():
                current[key] = int(val)
            else:
                current[key] = val
    if current is not None:
        records.append(_record_from_dict(current))
    return records


def format_hits(hits: Iterable[RetractionHit]) -> str:
    """Render a Markdown report of retraction-scanner hits."""
    items = list(hits)
    if not items:
        return "_Clean — no cited identifiers match the retraction registry._"
    lines = ["| Identifier | Status | Title | Reason | Notice |",
             "|---|---|---|---|---|"]
    for h in items:
        rec = h.record
        notice = rec.notice_url or ""
        title = rec.title.replace("\n", " ")
        if len(title) > 80:
            title = title[:77] + "..."
        reason = rec.reason_summary.replace("\n", " ")
        if len(reason) > 120:
            reason = reason[:117] + "..."
        ident_kind = h.matched_kind.upper()
        lines.append(
            f"| {ident_kind} {h.matched_identifier} | "
            f"{rec.status.value} | {title} | {reason} | {notice} |"
        )
    lines.append("")
    lines.append(
        "**Action**: do not cite the flagged identifier as primary "
        "evidence. Replace with a non-retracted source or remove the "
        "claim."
    )
    return "\n".join(lines)
