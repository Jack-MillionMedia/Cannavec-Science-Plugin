"""Vercel serverless function — GET ``/api/registries``.

Phase 1: expose the curated-registry inventory (row counts, entries,
last-verified dates). Fully offline / stdlib-only.

``GET /api/registries?registry=all|<name>&format=json|markdown``
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


class handler(BaseHTTPRequestHandler):
    # Quiet the default access log so user questions are not written
    # to stdout verbatim; Vercel captures structured logs separately.
    def log_message(self, *args):  # noqa: D401
        return

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _raw(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 200:
            self.send_header("Cache-Control", "public, s-maxage=86400")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        q = parse_qs(urlparse(self.path).query)
        registry = (q.get("registry") or ["all"])[0]
        fmt = (q.get("format") or ["json"])[0]
        try:
            from cannavec_science.registries import (
                all_registry_groups,
                build_inventory,
                render_json,
                render_markdown,
            )
        except Exception as exc:  # noqa: BLE001
            self._raw(500, json.dumps({"ok": False, "error": "import error",
                                       "detail": type(exc).__name__}),
                      "application/json; charset=utf-8")
            return

        if registry != "all" and registry not in all_registry_groups():
            self._raw(400, json.dumps({
                "ok": False,
                "error": f"unknown registry: {registry}",
                "valid": list(all_registry_groups()) + ["all"],
            }), "application/json; charset=utf-8")
            return

        inv = build_inventory(registry)
        if fmt == "markdown":
            self._raw(200, render_markdown(inv), "text/markdown; charset=utf-8")
        else:
            # render_json already returns a JSON string.
            self._raw(200, render_json(inv), "application/json; charset=utf-8")
