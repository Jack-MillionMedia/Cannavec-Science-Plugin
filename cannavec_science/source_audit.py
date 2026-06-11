"""KB source-audit flywheel — the verification engine as the Cannavec KB's immune
system AND growth engine.

When the semantic KB (the Cannavec MCP) returns sources for a query, every one is
run through the §I/§VIII gate BEFORE it reaches the user, so KB output is held to
the same evidence floor as everything else:

- **elite**     — the identifier resolves to a real, non-retracted primary source.
- **failed**    — fabricated (not found), retracted, or unrecognisable: a FALSE
                  source the KB should not have returned.
- **unverified**— the upstream could not be reached (network); not the KB's fault.

It also detects **missing** coverage: primary sources the engine's own live
discovery finds for the same query that the KB did NOT return — gaps the KB
should add. ``failed`` and ``missing`` are appended to an operator improve-queue
(``~/.cannavec/improve_queue.jsonl``) so the KB gets better as it is used.

Live by nature (it verifies identifiers + runs discovery), but the audit LOGIC is
deterministic and offline-testable: the ``verifier`` and ``discoverer`` are
injectable. Per §II, the credibility verdict (real? retracted?) is computed by
deterministic code, never asserted by the model.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

__all__ = ["AuditedSource", "SourceAudit", "QueueSummary", "audit_sources",
           "improve_queue_path", "summarize_improve_queue"]

# id -> (verdict, reason); verdict ∈ {"PASS", "FAIL", "UNVERIFIED"}
Verifier = Callable[[str], "tuple[str, str]"]
# query -> iterable of verified primary identifiers the engine found
Discoverer = Callable[[str], Iterable[str]]


@dataclass(frozen=True)
class AuditedSource:
    identifier: str
    kind: str            # "pmid" | "doi" | "unknown"
    verdict: str         # "PASS" | "FAIL" | "UNVERIFIED"
    reason: str

    def to_dict(self) -> dict:
        return {"identifier": self.identifier, "kind": self.kind,
                "verdict": self.verdict, "reason": self.reason}


@dataclass(frozen=True)
class SourceAudit:
    query: str
    elite: tuple = ()
    failed: tuple = ()          # FALSE sources (fabricated / retracted / bad shape)
    unverified: tuple = ()      # could not reach upstream
    missing: tuple = ()         # engine found these primary sources; the KB did not
    logged_path: Optional[str] = None

    def grounding_scores(self) -> dict:
        """Honest quality signal over the audit counts — no invented composite.

        - ``precision`` = elite / (elite + false): of the verifiable sources the
          KB returned, the fraction that are real + not retracted. ``None`` when
          the KB returned nothing verifiable (e.g. only network-unverified) — the
          score is undefined, never a misleading 0.0.
        - ``coverage`` = elite / (elite + missing): of the credible primary
          sources for this query, the fraction the KB already had.
        """
        n_elite, n_false, n_missing = len(self.elite), len(self.failed), len(self.missing)
        returned = n_elite + n_false
        coverage_den = n_elite + n_missing
        return {
            "precision": round(n_elite / returned, 3) if returned else None,
            "coverage": round(n_elite / coverage_den, 3) if coverage_den else None,
            "elite": n_elite, "false": n_false, "missing": n_missing,
        }

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "elite": [s.to_dict() for s in self.elite],
            "failed": [s.to_dict() for s in self.failed],
            "unverified": [s.to_dict() for s in self.unverified],
            "missing": list(self.missing),
            "scores": self.grounding_scores(),
            "logged_path": self.logged_path,
        }


@dataclass(frozen=True)
class QueueSummary:
    """A frequency ranking of the operator improve-queue: which gaps recur most,
    so the highest-impact ones are reviewed first. Pure reporting over the log —
    no automation, no writes.

    Source-level fields (``missing_by_id`` / ``false_by_id``) come from the
    identifier tier; the ``chunk_*`` fields come from the chunk tier
    (:mod:`cannavec_science.chunk_audit`). Both tiers share this one queue."""
    entries: int                       # audit events logged
    missing_by_id: tuple = ()          # ((identifier, count), ...) desc
    false_by_id: tuple = ()            # ((identifier, count, reason), ...) desc
    queries_by_count: tuple = ()       # ((query, count), ...) desc
    path: Optional[str] = None
    chunk_issues: int = 0              # total chunk-level issues logged
    chunk_by_dimension: tuple = ()     # ((dimension, count), ...) desc
    chunk_by_key: tuple = ()           # ((chunk_key, count), ...) desc — recurring chunks

    def to_dict(self) -> dict:
        return {
            "entries": self.entries,
            "missing_by_id": [{"identifier": i, "count": c} for i, c in self.missing_by_id],
            "false_by_id": [{"identifier": i, "count": c, "reason": r}
                            for i, c, r in self.false_by_id],
            "queries_by_count": [{"query": q, "count": c} for q, c in self.queries_by_count],
            "path": self.path,
            "chunk_issues": self.chunk_issues,
            "chunk_by_dimension": [{"dimension": d, "count": c}
                                   for d, c in self.chunk_by_dimension],
            "chunk_by_key": [{"chunk_key": k, "count": c} for k, c in self.chunk_by_key],
        }


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _classify(identifier: str) -> "tuple[str, str]":
    """Return ``(kind, normalized_id)``. Strips a leading ``PMID:`` / ``doi:``."""
    s = (identifier or "").strip()
    low = s.lower()
    if low.startswith("pmid:"):
        s = s[5:].strip()
        low = s.lower()
    elif low.startswith("doi:"):
        s = s[4:].strip()
        low = s.lower()
    if s.isdigit():
        return "pmid", s
    if low.startswith("10.") or "/" in s:
        return "doi", s
    return "unknown", s


def improve_queue_path(store_dir: "str | Path | None" = None) -> Path:
    """Operator improve-queue file: ``$store_dir/improve_queue.jsonl`` or, by
    default, next to the credentials (``~/.cannavec/improve_queue.jsonl``)."""
    if store_dir:
        return Path(store_dir) / "improve_queue.jsonl"
    from cannavec_science import _creds
    return _creds.credentials_path().parent / "improve_queue.jsonl"


def _rank(counter: "dict[str, int]") -> tuple:
    """Most-frequent first; ties broken alphabetically so output is deterministic
    (reproducibility — same queue, same ranking, every time)."""
    return tuple(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def summarize_improve_queue(*, path=None, store_dir=None) -> QueueSummary:
    """Read the operator improve-queue and rank its gaps by recurrence (highest-
    impact first). Read-only; tolerant of a missing file or malformed lines."""
    p = Path(path) if path else improve_queue_path(store_dir)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return QueueSummary(entries=0, path=str(p))

    entries = 0
    missing: "dict[str, int]" = {}
    false_ids: "dict[str, int]" = {}
    false_reason: "dict[str, str]" = {}
    queries: "dict[str, int]" = {}
    chunk_total = 0
    chunk_dim: "dict[str, int]" = {}
    chunk_key: "dict[str, int]" = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        entries += 1
        q = obj.get("query")
        if isinstance(q, str) and q:
            queries[q] = queries.get(q, 0) + 1
        for m in obj.get("missing_sources", []) or []:
            key = str(m)
            missing[key] = missing.get(key, 0) + 1
        for f in obj.get("false_sources", []) or []:
            if isinstance(f, dict):
                fid = str(f.get("identifier", "")).strip()
                reason = str(f.get("reason", "") or "")
            else:
                fid, reason = str(f), ""
            if not fid:
                continue
            false_ids[fid] = false_ids.get(fid, 0) + 1
            false_reason.setdefault(fid, reason)
        # Chunk tier (cannavec_science.chunk_audit) — same queue, additive.
        for ci in obj.get("chunk_issues", []) or []:
            if not isinstance(ci, dict):
                continue
            chunk_total += 1
            dim = str(ci.get("dimension", "") or "").strip()
            if dim:
                chunk_dim[dim] = chunk_dim.get(dim, 0) + 1
            ck = str(ci.get("chunk_key", "") or "").strip()
            if ck:
                chunk_key[ck] = chunk_key.get(ck, 0) + 1

    false_ranked = tuple((i, c, false_reason.get(i, "")) for i, c in _rank(false_ids))
    return QueueSummary(
        entries=entries, missing_by_id=_rank(missing), false_by_id=false_ranked,
        queries_by_count=_rank(queries), path=str(p),
        chunk_issues=chunk_total, chunk_by_dimension=_rank(chunk_dim),
        chunk_by_key=_rank(chunk_key),
    )


def _append_improve_queue(query, failed, missing, *, now=None, store_dir=None) -> "str | None":
    path = improve_queue_path(store_dir)
    entry = {
        "ts": now or _utcnow(),
        "query": query,
        "false_sources": [s.to_dict() for s in failed],
        "missing_sources": list(missing),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return str(path)
    except OSError:  # read-only fs etc. — never let logging break the audit
        return None


def _live_verifier(identifier: str) -> "tuple[str, str]":
    """Default verifier: bare-verify the identifier against the live upstreams +
    the retraction registry (§I/§VIII). No claim text, so an existing,
    non-retracted record is a clean PASS."""
    from cannavec_science import pubmed_verify
    from cannavec_science.pubmed_verify import VerificationVerdict as V

    kind, ident = _classify(identifier)
    if kind == "pmid":
        res = pubmed_verify.verify_pmid(ident)
    elif kind == "doi":
        res = pubmed_verify.verify_doi(ident)
    else:
        return "FAIL", f"unrecognised identifier shape: {identifier!r}"
    v = res.verdict
    if v in (V.MATCH, V.BARE_CITE_OK):
        return "PASS", "verified real, not retracted"
    if v == V.RETRACTED:
        return "FAIL", "retracted — never a valid primary citation"
    if v == V.NOT_FOUND:
        return "FAIL", "not found upstream (fabricated?)"
    if v == V.NETWORK_ERROR:
        return "UNVERIFIED", "could not reach the upstream to confirm"
    return "FAIL", f"verdict {v.value}"


def _live_discoverer(query: str, *, max_rows: int = 10) -> "list[str]":
    """Default discoverer: run the engine's own live discovery and return the
    primary identifiers (PMID/DOI) it surfaced. Best-effort — any failure yields
    an empty list (no missing-detection rather than a crash)."""
    try:
        from cannavec_science import live
        payload = live.run_discovery(
            query, sources=("pubmed", "europepmc", "ctgov"), max_results=max_rows,
        )
    except Exception:  # noqa: BLE001 — gap detection is best-effort
        return []
    ids: list[str] = []
    sources = payload.get("sources", {}) if isinstance(payload, dict) else {}
    for rows in sources.values():
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            for keyname in ("pmid", "doi", "native_id", "identifier"):
                val = r.get(keyname)
                if val:
                    ids.append(str(val))
                    break
    return ids


def audit_sources(
    query: str,
    kb_identifiers: Iterable[str],
    *,
    verifier: Optional[Verifier] = None,
    discoverer: Optional[Discoverer] = None,
    detect_missing: bool = True,
    log: bool = True,
    now: Optional[str] = None,
    store_dir: "str | Path | None" = None,
) -> SourceAudit:
    """Audit the KB's returned sources and detect missing coverage; append the
    flywheel improve-queue. ``verifier`` / ``discoverer`` are injectable so the
    logic is fully offline-testable."""
    verify = verifier or _live_verifier
    elite: list[AuditedSource] = []
    failed: list[AuditedSource] = []
    unverified: list[AuditedSource] = []
    seen: set[str] = set()
    kb_norm: set[str] = set()

    for raw in kb_identifiers:
        kind, ident = _classify(raw)
        kb_norm.add(ident.lower())
        if ident.lower() in seen:
            continue
        seen.add(ident.lower())
        verdict, reason = verify(ident)
        src = AuditedSource(ident, kind, verdict, reason)
        if verdict == "PASS":
            elite.append(src)
        elif verdict == "UNVERIFIED":
            unverified.append(src)
        else:
            failed.append(src)

    missing: tuple = ()
    if detect_missing:
        discover = discoverer or _live_discoverer
        try:
            discovered = list(discover(query))
        except Exception:  # noqa: BLE001 — gap detection never breaks the audit
            discovered = []
        seen_missing: set[str] = set()
        out_missing: list[str] = []
        for d in discovered:
            dl = str(d).lower()
            if dl and dl not in kb_norm and dl not in seen_missing:
                seen_missing.add(dl)
                out_missing.append(str(d))
        missing = tuple(out_missing)

    logged_path = None
    if log and (failed or missing):
        logged_path = _append_improve_queue(
            query, failed, missing, now=now, store_dir=store_dir)

    return SourceAudit(
        query=query, elite=tuple(elite), failed=tuple(failed),
        unverified=tuple(unverified), missing=missing, logged_path=logged_path,
    )
