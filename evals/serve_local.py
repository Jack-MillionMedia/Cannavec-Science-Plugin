#!/usr/bin/env python3
"""Run the whole Vercel API locally on one port — a dependency-free `vercel dev`.

Each ``api/<name>.py`` is a standalone Vercel function; locally we mount them all
behind a single router so the API can be exercised end to end without Vercel and
without network (the curated paths are offline). Pair it with the smoke tester::

    python3 evals/serve_local.py 8000 &
    python3 evals/smoke_api.py http://127.0.0.1:8000

The router delegates each request to the matched function's ``handler`` by
sharing the live request state (``rfile`` / ``wfile`` / ``path`` / ``headers``)
with a fresh, un-initialised instance of that handler class — so the function
runs exactly as it would on Vercel, helper methods and all.

Stdlib only.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

_API_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
_NAMES = ("health", "answer", "discover", "rigor", "registries")


def _load(name: str):
    path = os.path.join(_API_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"api_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MODS = {n: _load(n) for n in _NAMES}


def make_router() -> type:
    """Build the routing handler class (also used by the offline smoke test)."""

    class Router(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            return

        def _route(self):
            path = self.path.split("?", 1)[0].strip("/")
            parts = path.split("/")
            name = parts[1] if parts[:1] == ["api"] and len(parts) > 1 else (parts[0] or "")
            return _MODS.get(name)

        def _dispatch(self, method: str) -> None:
            mod = self._route()
            if mod is None:
                body = b'{"ok":false,"error":"not found"}'
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            # Run the real Vercel function with this request's live state.
            h = mod.handler.__new__(mod.handler)
            h.__dict__ = self.__dict__
            fn = getattr(h, f"do_{method}", None)
            if fn is None:
                self.send_response(405)
                self.end_headers()
                return
            fn()

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_OPTIONS(self):
            self._dispatch("OPTIONS")

    return Router


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else int(os.environ.get("PORT", "8000"))
    httpd = HTTPServer(("127.0.0.1", port), make_router())
    print(f"[serve-local] http://127.0.0.1:{port}  routes: "
          + ", ".join(f"/api/{n}" for n in _NAMES))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
