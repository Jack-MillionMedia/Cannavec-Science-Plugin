"""Recursive learning — the KB's longitudinal memory, so the flywheel *refines the
knowledge base over time* instead of re-auditing it from scratch each pass.

Every chunk evaluation (:mod:`cannavec_science.chunk_eval`) is appended to a per-user
ledger keyed on the chunk and a hash of its content. On the next pass the ledger diffs
the new verdict against the last one for that chunk and classifies the change:

- **resolved**  — the chunk was flagged, its content changed, and it is now clean →
                  stop re-flagging it; record the win.
- **regressed** — the chunk was ``correct`` and is now flagged → a high-priority alert.
- **reopened**  — the chunk's content is unchanged, but newer credible evidence has
                  appeared for its topic (the stored *evidence snapshot* moved) → the
                  chunk is potentially **outdated** even though nobody touched it. This
                  is the engine that makes the KB chase the moving frontier of science.
- **recurring** — same issue, same content → bump its demand/priority.

``kb_health`` rolls the latest verdict per chunk into a status distribution and a
``snapshot_health`` cycle log, so KB improvement is *provable*, not asserted. A minimal
``eval_feedback`` store lets an operator mark a false flag; that exact
``(chunk_key, verdict)`` is then suppressed until the chunk's content hash changes —
the evaluator's precision compounds as transparent, human-reviewed data (§II: the rule
store evolves under review; the credibility verdict stays deterministic).

Deterministic and offline: timestamps/dates are injected; all state is plain JSONL.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cannavec_science import source_audit
from cannavec_science.chunk_eval import CORRECT, UNEVALUATED

__all__ = [
    "LedgerDiff", "KbHealth", "record_evaluation", "latest_by_chunk",
    "kb_health", "snapshot_health", "health_trend",
    "suppress_flag", "is_suppressed", "ledger_path",
    "NEW", "RESOLVED", "REGRESSED", "REOPENED", "RECURRING", "UPDATED", "UNCHANGED",
]

NEW = "new"
RESOLVED = "resolved"
REGRESSED = "regressed"
REOPENED = "reopened"
RECURRING = "recurring"
UPDATED = "updated"        # content changed, still flagged (partial progress — re-review)
UNCHANGED = "unchanged"

_CLEAN = {CORRECT, UNEVALUATED}


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _store(name: str, store_dir=None) -> Path:
    return source_audit.improve_queue_path(store_dir).parent / name


def ledger_path(store_dir=None) -> Path:
    return _store("chunk_ledger.jsonl", store_dir)


# ── diff model ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LedgerDiff:
    chunk_key: str
    change: str                 # new | resolved | regressed | reopened | recurring | unchanged
    prev_status: Optional[str]
    new_status: str
    detail: str

    @property
    def is_alert(self) -> bool:
        return self.change in (REGRESSED, REOPENED)

    def to_dict(self) -> dict:
        return {"chunk_key": self.chunk_key, "change": self.change,
                "prev_status": self.prev_status, "new_status": self.new_status,
                "detail": self.detail}


def _read_lines(path: Path) -> "list[dict]":
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return []
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def latest_by_chunk(*, path=None, store_dir=None) -> "dict[str, dict]":
    """Most recent ledger record per chunk_key (last-write-wins by file order)."""
    p = Path(path) if path else ledger_path(store_dir)
    latest: dict[str, dict] = {}
    for rec in _read_lines(p):
        key = rec.get("chunk_key")
        if isinstance(key, str) and key:
            latest[key] = rec
    return latest


def _snapshot_newer(new: Optional[dict], old: Optional[dict]) -> bool:
    """Did genuinely NEWER credible evidence appear since the prior snapshot? Gated on
    a strictly newer max year only — live discovery is capped + non-deterministic, so
    a bare new-id delta is membership churn, not new science, and must not reopen a
    settled chunk."""
    if not new or not old:
        return False
    return int(new.get("max_year", 0) or 0) > int(old.get("max_year", 0) or 0)


def _classify(prev: Optional[dict], new_status: str, content_hash: str,
              snapshot: Optional[dict]) -> "tuple[str, str]":
    if prev is None:
        return NEW, "first evaluation of this chunk"
    prev_status = prev.get("status", "")
    prev_clean = prev_status in _CLEAN
    new_clean = new_status in _CLEAN
    content_unchanged = prev.get("content_hash") == content_hash
    if prev_status == CORRECT and not new_clean:
        return REGRESSED, f"was correct, now {new_status}"
    if not prev_clean and new_clean:
        return RESOLVED, f"was {prev_status}, now {new_status}"
    if prev_clean and content_unchanged and _snapshot_newer(snapshot, prev.get("evidence_snapshot")):
        return REOPENED, "unchanged chunk, but newer credible evidence appeared — re-check"
    if not new_clean and content_unchanged:
        return RECURRING, f"still {new_status}, content unchanged"
    if not content_unchanged:
        return UPDATED, f"content changed: {prev_status} → {new_status}"
    return UNCHANGED, f"{prev_status} → {new_status}"


def record_evaluation(verdict, *, evidence_snapshot: Optional[dict] = None,
                      now: Optional[str] = None, store_dir=None,
                      log: bool = True) -> LedgerDiff:
    """Append a chunk verdict to the ledger and return how it changed vs last time.
    ``verdict`` is a chunk_eval.ChunkVerdict. ``evidence_snapshot`` = {ids, max_year}
    of the credible corpus at eval time (drives reopen-on-new-evidence)."""
    p = ledger_path(store_dir)
    prev = latest_by_chunk(path=p).get(verdict.chunk_key)
    change, detail = _classify(prev, verdict.status, verdict.content_hash, evidence_snapshot)
    diff = LedgerDiff(chunk_key=verdict.chunk_key, change=change,
                      prev_status=(prev or {}).get("status"),
                      new_status=verdict.status, detail=detail)
    if log:
        rec = {
            "ts": now or _utcnow(), "chunk_key": verdict.chunk_key,
            "doc_id": verdict.doc_id, "content_hash": verdict.content_hash,
            "status": verdict.status, "confidence": verdict.confidence,
            "corroboration": verdict.corroboration.to_dict() if verdict.corroboration else None,
            "evidence_snapshot": evidence_snapshot, "change": change,
        }
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return diff


# ── KB-health rollup + trend ─────────────────────────────────────────────────

@dataclass(frozen=True)
class KbHealth:
    total: int
    by_status: tuple                  # ((status, count), ...) desc
    correct_fraction: Optional[float]

    def to_dict(self) -> dict:
        return {"total": self.total,
                "by_status": [{"status": s, "count": c} for s, c in self.by_status],
                "correct_fraction": self.correct_fraction}


def kb_health(*, path=None, store_dir=None) -> KbHealth:
    """Status distribution over the LATEST verdict per chunk — the KB's current
    health. correct_fraction is the share of evaluated chunks that are ``correct``."""
    latest = latest_by_chunk(path=path, store_dir=store_dir)
    counts: dict[str, int] = {}
    for rec in latest.values():
        s = rec.get("status", UNEVALUATED)
        counts[s] = counts.get(s, 0) + 1
    total = sum(counts.values())
    ranked = tuple(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    frac = round(counts.get(CORRECT, 0) / total, 3) if total else None
    return KbHealth(total=total, by_status=ranked, correct_fraction=frac)


def snapshot_health(*, now: Optional[str] = None, store_dir=None,
                    path=None) -> KbHealth:
    """Compute current KB health and append it to the kb_health time series, so
    improvement across cycles is provable."""
    h = kb_health(path=path, store_dir=store_dir)
    rec = {"ts": now or _utcnow(), "total": h.total,
           "by_status": dict(h.by_status), "correct_fraction": h.correct_fraction}
    hp = _store("kb_health.jsonl", store_dir)
    try:
        hp.parent.mkdir(parents=True, exist_ok=True)
        with open(hp, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return h


def health_trend(*, store_dir=None) -> "list[dict]":
    """The kb_health cycle log, oldest → newest."""
    return _read_lines(_store("kb_health.jsonl", store_dir))


# ── eval feedback (learn from false flags) ───────────────────────────────────

def _feedback_path(store_dir=None) -> Path:
    return _store("eval_feedback.json", store_dir)


def _load_feedback(store_dir=None) -> dict:
    try:
        return json.loads(_feedback_path(store_dir).read_text(encoding="utf-8"))
    except (OSError, FileNotFoundError, ValueError):
        return {"suppressed": []}


def suppress_flag(chunk_key: str, verdict: str, content_hash: str, *,
                  reason: str = "", store_dir=None) -> None:
    """Operator marks a flag a false positive: suppress this exact (chunk_key,
    verdict) until the chunk's content hash changes. Transparent, reviewable data."""
    data = _load_feedback(store_dir)
    entry = {"chunk_key": chunk_key, "verdict": verdict,
             "content_hash": content_hash, "reason": reason}
    if entry not in data["suppressed"]:
        data["suppressed"].append(entry)
    p = _feedback_path(store_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def is_suppressed(chunk_key: str, verdict: str, content_hash: str, *,
                  store_dir=None) -> bool:
    """True if this flag was marked a false positive AND the chunk's content has not
    changed since (a content change re-arms the check — the chunk is different now)."""
    for e in _load_feedback(store_dir).get("suppressed", []):
        if (e.get("chunk_key") == chunk_key and e.get("verdict") == verdict
                and e.get("content_hash") == content_hash):
            return True
    return False
