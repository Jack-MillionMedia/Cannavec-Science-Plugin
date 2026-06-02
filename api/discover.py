"""Vercel serverless function — GET/POST ``/api/discover`` (Phase 2, live).

Live multi-source primary-source fan-out (PubMed / ClinicalTrials.gov, and
opt-in ChEMBL / Europe PMC) with a deterministic cross-source synthesis
verdict. Network-backed: production calls are authenticated via the
``NCBI_API_KEY`` environment variable (see ``cannavec_science._http``).

Request
-------
``GET  /api/discover?query=...&sources=pubmed,ctgov&max=10&since=YYYY-MM-DD``
``POST /api/discover``  body ``{"query":"...","sources":["pubmed"],"max":10}``

Ranking (cross-source) is on by default — a free, offline, deterministic
re-ordering of the fanned-out hits by relevance + study design + recency, with
retracted papers sunk to the bottom. Disable with ``rank=false``. The optional
LLM lift (``rerank=true``, model via ``rerank_model``) fires only when the
deterministic order is genuinely uncertain and degrades silently to the
deterministic order if the ``anthropic`` package or ``ANTHROPIC_API_KEY`` is
not present — so the discover response always stands.

Response → ``{"ok": true, "query", "sources": {<src>: [rows]|{"error"}},
              "synthesis": {...convergence verdict...},
              "ranking": {...ranked candidates + escalation_reason...}}``

Safety: the query passes the §V discover preflight before any network call;
a refused query returns HTTP 422 with the reason. Per-lane failures degrade
gracefully (that source carries an ``error`` field; the rest still return).
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_ALLOWED_ORIGIN = os.environ.get("CANNAVEC_ALLOWED_ORIGIN", "*")

# Default model for the opt-in LLM rerank (Sonnet 4.6 — accuracy-equivalent to
# Opus for a bounded rerank at lower cost). Override per request with
# ``rerank_model``; requires the ``anthropic`` package + ``ANTHROPIC_API_KEY``.
_DEFAULT_RERANK_MODEL = "claude-sonnet-4-6"


def _maybe_rank(query, result, *, rank, rerank, rerank_model, max_results,
                force=False):
    """Rank the fanned-out candidates across sources, or return ``None``.

    Deterministic by default (free, offline, additive). ``rerank`` adds the LLM
    lift, which auto-fires only on a genuine ranking uncertainty and degrades to
    the deterministic order on any failure. ``force`` (``rerank=force``) bypasses
    the confidence short-circuit and always calls the model — for testing the
    LLM path without waiting for a natural escalation. Ranking never fails the
    response: any unexpected error here returns ``None`` and the fan-out stands.
    """
    if not rank:
        return None
    try:
        from cannavec_science.ranker import (
            candidates_from_discovery, rank_candidates,
        )
        cands = candidates_from_discovery(result)
        if not cands:
            return None
        backend = None
        if rerank:
            from cannavec_science.ranker_llm import LLMReranker
            backend = LLMReranker(model=rerank_model)
        return rank_candidates(
            query, cands, backend=backend,
            escalate=True if force else None,
            top_k=max(1, int(max_results or 10)),
        ).to_dict()
    except Exception:  # noqa: BLE001 — ranking is additive, never fatal
        return None


def _markdown(result: dict, ranking: dict | None = None) -> str:
    lines = [f"## Live discovery — {result.get('query', '')}", ""]
    if ranking and ranking.get("ranked"):
        reason = ranking.get("escalation_reason")
        backend = ranking.get("backend_used", "deterministic")
        tag = f"LLM rerank — {reason}" if ranking.get("escalated") else "deterministic"
        lines.append(f"### Ranked candidates ({tag})")
        for r in ranking["ranked"][:10]:
            star = " ★" if r.get("reordered_by_llm") else ""
            flag = "" if r.get("retraction_status") == "clean" else f" ⚠ {r.get('retraction_status')}"
            title = (r.get("title") or "").strip()
            lines.append(
                f"{r.get('rank')}.{star} `{r.get('identifier')}`{flag} "
                f"{title}".rstrip()
            )
        lines.append("")
    for src in sorted(result.get("sources", {})):
        val = result["sources"][src]
        if isinstance(val, dict) and "error" in val:
            lines.append(f"### {src} (unavailable)")
            lines.append(f"_{val['error']}_")
            continue
        lines.append(f"### {src} ({len(val)})")
        for r in val:
            ident = (r.get("pmid") or r.get("nct_id") or r.get("chembl_id")
                     or r.get("activity_id") or "?")
            title = (r.get("title") or r.get("brief_title")
                     or r.get("compound") or "")
            lines.append(f"- `{ident}` {title}".rstrip())
        lines.append("")
    synth = result.get("synthesis") or {}
    if synth:
        lines.append("### Cross-source synthesis")
        lines.append(f"- Convergence: **{synth.get('convergence', 'NONE')}**")
    return "\n".join(lines).rstrip() + "\n"


class handler(BaseHTTPRequestHandler):
    # Quiet the default access log so user queries are not written to stdout
    # verbatim; Vercel captures structured logs separately.
    def log_message(self, *args):  # noqa: D401
        return

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if status == 200:
            # Live data — cache modestly so repeat queries are cheap without
            # going stale for long.
            self.send_header("Cache-Control",
                             "public, s-maxage=3600, stale-while-revalidate=86400")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        q = parse_qs(urlparse(self.path).query)
        query = (q.get("query") or q.get("q") or [""])[0].strip()
        sources = (q.get("sources") or [""])[0]
        sources = [s for s in sources.split(",") if s.strip()] or None
        since = (q.get("since") or [None])[0]
        fmt = (q.get("format") or ["json"])[0]
        try:
            max_results = int((q.get("max") or ["10"])[0])
        except (TypeError, ValueError):
            max_results = 10
        rank = (q.get("rank") or ["true"])[0].strip().lower() != "false"
        rerank_raw = (q.get("rerank") or ["false"])[0].strip().lower()
        rerank = rerank_raw in ("true", "force", "1", "yes")
        rerank_force = rerank_raw == "force"
        rerank_model = (q.get("rerank_model") or [_DEFAULT_RERANK_MODEL])[0]
        self._handle(query, sources, max_results, since, fmt,
                     rank, rerank, rerank_model, rerank_force)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw or b"{}")
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, TypeError):
            self._json(400, {"ok": False, "error": "invalid JSON body"})
            return
        query = str(data.get("query") or data.get("q") or "").strip()
        sources = data.get("sources")
        if isinstance(sources, str):
            sources = [s for s in sources.split(",") if s.strip()]
        since = data.get("since")
        fmt = str(data.get("format", "json"))
        try:
            max_results = int(data.get("max", 10))
        except (TypeError, ValueError):
            max_results = 10
        rank = bool(data.get("rank", True))
        rerank_raw = str(data.get("rerank", "")).strip().lower()
        rerank = data.get("rerank") is True or rerank_raw in ("true", "force", "1", "yes")
        rerank_force = rerank_raw == "force"
        rerank_model = str(data.get("rerank_model") or _DEFAULT_RERANK_MODEL)
        self._handle(query, sources or None, max_results, since, fmt,
                     rank, rerank, rerank_model, rerank_force)

    def _handle(self, query, sources, max_results, since, fmt,
                rank=True, rerank=False, rerank_model=_DEFAULT_RERANK_MODEL,
                rerank_force=False) -> None:
        if not query:
            self._json(400, {"ok": False, "error": "missing 'query'"})
            return
        # Import the module (not the symbol) so tests can monkeypatch
        # cannavec_science.live.run_discovery.
        from cannavec_science import live
        try:
            result = live.run_discovery(
                query, sources=sources, max_results=max_results, since=since
            )
        except live.DiscoverRefused as exc:
            self._json(422, {
                "ok": False,
                "refused": True,
                "reason": getattr(exc, "reason", None) or str(exc),
            })
            return
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 — never leak a stack trace
            self._json(502, {"ok": False, "error": "discovery failed",
                             "detail": type(exc).__name__})
            return

        ranking = _maybe_rank(
            query, result, rank=rank, rerank=rerank,
            rerank_model=rerank_model, max_results=max_results,
            force=rerank_force,
        )

        if fmt == "markdown":
            self._text(200, _markdown(result, ranking))
        else:
            out = {"ok": True, **result}
            if ranking is not None:
                out["ranking"] = ranking
            self._json(200, out)
