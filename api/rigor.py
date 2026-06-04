"""Vercel serverless function — POST/GET ``/api/rigor``.

Phase 1: run the six phytochemistry rigor detectors + the banned-pattern
detector on arbitrary text. Fully offline / stdlib-only.

``GET  /api/rigor?text=...``
``POST /api/rigor``  body ``{"text": "..."}``

Response → ``{"ok", "clean", "counts", "phytochemistry_violations",
              "banned_pattern_hits"}``.
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

_VIOLATION_FIELDS = (
    "isomer_violations",
    "receptor_violations",
    "dose_route_violations",
    "thca_thc_violations",
    "matrix_unit_violations",
    "decarb_context_violations",
    "entourage_violations",
    "reporting_rigor_violations",
)


def _serialize_violation(v) -> dict:
    """Best-effort JSON view of a rigor violation (shapes vary by detector)."""
    out: dict = {}
    for attr in ("matched_phrase", "receptor", "dose", "unit_phrase",
                 "claim_phrase", "terpene", "cannabinoid", "sentence", "why"):
        val = getattr(v, attr, None)
        if val:
            out[attr] = val
    if not out:
        out["repr"] = str(v)
    return out


def _rigor_report(text: str) -> dict:
    from cannavec_science.rigor_checks import run_rigor_checks
    from cannavec_science.banned_patterns import detect_banned_patterns

    report = run_rigor_checks(text)
    banned = detect_banned_patterns(text)

    phyto: dict[str, list] = {}
    counts: dict[str, int] = {}
    for field in _VIOLATION_FIELDS:
        items = list(getattr(report, field, ()) or ())
        counts[field] = len(items)
        if items:
            phyto[field] = [_serialize_violation(v) for v in items]

    banned_hits = [
        {
            "id": h.pattern.id,
            "match": h.match,
            "why": h.pattern.why,
        }
        for h in banned
    ]
    counts["banned_patterns"] = len(banned_hits)
    total = sum(counts.values())
    return {
        "ok": True,
        "clean": total == 0,
        "counts": counts,
        "phytochemistry_violations": phyto,
        "banned_pattern_hits": banned_hits,
    }


class handler(BaseHTTPRequestHandler):
    # Quiet the default access log so user questions are not written
    # to stdout verbatim; Vercel captures structured logs separately.
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
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        q = parse_qs(urlparse(self.path).query)
        self._handle((q.get("text") or [""])[0])

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
        self._handle(str(data.get("text", "")))

    def _handle(self, text: str) -> None:
        if not text.strip():
            self._json(400, {"ok": False, "error": "missing 'text'"})
            return
        try:
            self._json(200, _rigor_report(text))
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": "internal error",
                             "detail": type(exc).__name__})
