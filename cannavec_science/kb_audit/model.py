"""Shared frozen data model for the KB credibility audit (spec 032)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    identifier: str
    id_type: str
    claim: str


@dataclass(frozen=True)
class FileRecord:
    path: str
    in_scope: bool
    declared_grade: str | None
    study_counts: dict
    citations: tuple
    parse_error: str | None = None


@dataclass(frozen=True)
class Finding:
    gate: str
    issue: str
    evidence: str
    verdict: str
    recommended_action: str
    route: str


@dataclass(frozen=True)
class FileVerdict:
    path: str
    in_scope: bool
    routing: str
    status: str
    priority: int
    credibility: dict
    findings: tuple
