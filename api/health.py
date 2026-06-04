"""Vercel serverless function — GET ``/api/health``.

Cheap liveness + capability probe. Confirms the engine imports, reports the
version and curated-registry count, and lists the public surface. Offline.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_ALLOWED_ORIGIN = os.environ.get("CANNAVEC_ALLOWED_ORIGIN", "*")


class handler(BaseHTTPRequestHandler):
    # Quiet the default access log so user questions are not written
    # to stdout verbatim; Vercel captures structured logs separately.
    def log_message(self, *args):  # noqa: D401
        return

    def do_GET(self) -> None:
        payload: dict = {"status": "ok"}
        try:
            import cannavec_science
            from cannavec_science.registries import all_registry_groups
            from cannavec_science._http import ncbi_api_key
            groups = all_registry_groups()
            # Live discovery is *configured* when an NCBI key is present; the
            # curated path needs neither key nor network.
            live_ready = ncbi_api_key() is not None
            payload["version"] = getattr(cannavec_science, "__version__", "unknown")
            payload["phase"] = 2 if live_ready else 1
            payload["live_discovery"] = live_ready
            payload["curated_registries"] = len(groups)
            payload["registry_names"] = list(groups)
            payload["endpoints"] = ["/api/answer", "/api/discover", "/api/rigor",
                                    "/api/registries", "/api/health"]
        except Exception as exc:  # noqa: BLE001
            payload["status"] = "degraded"
            payload["error"] = type(exc).__name__

        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(200 if payload["status"] == "ok" else 500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        # A liveness/version probe must always reflect the running deployment,
        # never an edge-cached copy from a previous one.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)
