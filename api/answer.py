"""Vercel serverless function — POST/GET ``/api/answer``.

Phase 1: the curated, **offline**, deterministic research-brief path. No
network, no API key, no database — it imports the stdlib-only
``cannavec_science`` engine and returns a typed, GRADE-honest ``Answer``.

Request
-------
``GET  /api/answer?question=...&format=json|markdown&retraction_policy=strict|badge``
``POST /api/answer``  body ``{"question": "...", "format": "json",
                              "retraction_policy": "strict"}``

Response
--------
``format=json`` (default) → ``{"ok", "is_refusal", "answer": <Answer.to_dict()>}``
``format=markdown``       → the rendered Markdown brief (text/markdown)

Notes
-----
- Vercel's Python runtime invokes the class named ``handler`` (a
  ``BaseHTTPRequestHandler`` subclass) — the zero-dependency pattern, so the
  web layer stays as stdlib-pure as the engine (Constitution §X: the core
  stays stdlib; rendering/web is an optional layer).
- The repo root is added to ``sys.path`` so ``import cannavec_science``
  resolves regardless of Vercel's working directory; ``vercel.json``'s
  ``includeFiles`` guarantees the package (incl. its lazily-imported
  registries) is bundled into the function.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Guarantee the engine package is importable from the function bundle.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_ALLOWED_ORIGIN = os.environ.get("CANNAVEC_ALLOWED_ORIGIN", "*")


def _compose(question: str, retraction_policy: str = "strict"):
    """Run the curated, offline brief pipeline (lazy import keeps cold start lean)."""
    from cannavec_science.answer import compose_answer

    return compose_answer(
        question,
        retraction_policy=retraction_policy,
        include_registries=True,
        include_claims=True,
        include_rigor=True,
    )


class handler(BaseHTTPRequestHandler):
    # Quiet the default access log so user questions are not written
    # to stdout verbatim; Vercel captures structured logs separately.
    def log_message(self, *args):  # noqa: D401
        return

    # ── helpers ─────────────────────────────────────────────────────────
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, payload: dict, cache_seconds: int = 86400) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if status == 200 and cache_seconds > 0:
            # Curated answers are deterministic → cacheable at the edge. A
            # live-augmented answer carries fresh data, so it is cached for a
            # shorter window (passed by the caller).
            self.send_header(
                "Cache-Control",
                f"public, s-maxage={cache_seconds}, "
                f"stale-while-revalidate={cache_seconds * 7}",
            )
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

    # ── methods ─────────────────────────────────────────────────────────
    def do_OPTIONS(self) -> None:  # CORS preflight
        self.send_response(204)
        self._cors()
        self.end_headers()

    @staticmethod
    def _truthy(v) -> bool:
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    def do_GET(self) -> None:
        q = parse_qs(urlparse(self.path).query)
        question = (q.get("question") or [""])[0].strip()
        fmt = (q.get("format") or ["json"])[0]
        policy = (q.get("retraction_policy") or ["strict"])[0]
        aug = q.get("augment")
        augment = None if not aug else self._truthy(aug[0])
        fallback = self._truthy((q.get("fallback") or ["true"])[0])
        self._handle(question, fmt, policy, augment, fallback)

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
        question = str(data.get("question", "")).strip()
        fmt = str(data.get("format", "json"))
        policy = str(data.get("retraction_policy", "strict"))
        augment = None if "augment" not in data else self._truthy(data.get("augment"))
        fallback = self._truthy(data.get("fallback", True))
        self._handle(question, fmt, policy, augment, fallback)

    def _handle(self, question: str, fmt: str, policy: str,
                augment: "bool | None" = None, fallback: bool = True) -> None:
        """Compose the curated brief, then decide on live evidence.

        Three modes:
        - ``augment=true``  → always weave live findings (Phase 2, forced).
        - default / ``fallback=true`` → **Phase 3 auto-fallback**: weave live
          findings only when curated coverage is *thin* (novel question).
        - ``augment=false`` or ``fallback=false`` → pure curated, no network.

        Live findings are provisional and never promoted (§IX); the curated
        brief always stands even if discovery is unavailable. Live data →
        shorter edge cache.
        """
        if not question:
            self._json(400, {"ok": False, "error": "missing 'question'"})
            return
        if policy not in ("strict", "badge"):
            policy = "strict"

        n_live = 0
        fallback_used = False
        try:
            from cannavec_science import live
            if augment is True:
                a = _compose(question, retraction_policy=policy)
                n_live = live.augment_answer(a, max_results=5)
            elif augment is False or not fallback:
                a = _compose(question, retraction_policy=policy)
            else:  # Phase 3 — auto-fallback when curated coverage is thin
                a, fallback_used = live.answer_with_fallback(
                    question, retraction_policy=policy, max_results=5,
                )
                n_live = len(a.live_findings)
        except Exception as exc:  # noqa: BLE001 — never leak a stack trace
            self._json(500, {"ok": False, "error": "internal error",
                             "detail": type(exc).__name__})
            return

        live_data = (augment is True) or fallback_used
        if fmt == "markdown":
            self._text(200, a.to_markdown())
        else:
            self._json(200, {
                "ok": True,
                "is_refusal": a.is_refusal,
                "augmented": n_live,
                "fallback_used": fallback_used,
                "answer": a.to_dict(),
            }, cache_seconds=3600 if live_data else 86400)
