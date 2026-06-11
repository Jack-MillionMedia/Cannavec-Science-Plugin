# cannavec_science/kb_audit/extract.py
"""Extract a FileRecord (frontmatter + cited identifiers + nearest claim) from a KB file."""
from __future__ import annotations

import os
import re

from cannavec_science import _identifiers as _ids
from cannavec_science._markdown_skip import code_spans, is_in_code
from cannavec_science.pubmed_verify import scan_pmids, scan_dois
from cannavec_science.kb_audit.frontmatter import parse_frontmatter
from cannavec_science.kb_audit.model import Citation, FileRecord
from cannavec_science.kb_audit.scope import DEFAULT_INCLUDE, is_in_scope

_NCT_RE = _ids.NCT_SCAN_CI  # centralized in cannavec_science._identifiers
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _body(text: str) -> str:
    if text.startswith("---"):
        parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            return parts[2]
    return text


def _claim_for(body: str, ident: str) -> str:
    pos = body.find(ident)
    if pos < 0:
        return ""
    head = body[:pos]
    sentences = _SENT_SPLIT.split(head)
    return (sentences[-1] if sentences else "").strip()


def extract(path: str, root: str | None = None, include=DEFAULT_INCLUDE, exclude=()) -> FileRecord:
    rel = os.path.relpath(path, root) if root else path
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as exc:
        return FileRecord(path=path, in_scope=True, declared_grade=None,
                          study_counts={}, citations=(), parse_error=str(exc))

    fm = parse_frontmatter(text)
    body = _body(text)
    spans = code_spans(body)

    seen: set[str] = set()
    cites: list[Citation] = []
    for ident, id_type in (
        [(p, "PMID") for p in scan_pmids(body)]
        + [(d, "DOI") for d in scan_dois(body)]
        + [(m.group(0).upper(), "NCT") for m in _NCT_RE.finditer(body)
           if not is_in_code(spans, m.start())]
    ):
        if ident in seen:
            continue
        seen.add(ident)
        cites.append(Citation(identifier=ident, id_type=id_type, claim=_claim_for(body, ident)))

    grade = fm.get("evidence_grade")
    return FileRecord(
        path=path,
        in_scope=is_in_scope(rel, include, exclude),
        declared_grade=grade if isinstance(grade, str) else None,
        study_counts=fm.get("study_counts", {}) if isinstance(fm.get("study_counts"), dict) else {},
        citations=tuple(cites),
    )
