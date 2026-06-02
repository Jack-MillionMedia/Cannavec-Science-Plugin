"""Smoke tests for the Phase-1 Vercel API handlers (``api/*.py``).

These prove the web glue imports cleanly, exposes a ``handler`` class, and
serves the curated engine over HTTP — all offline (no network, no Vercel
runtime needed). Each handler is exercised through a real in-process
``HTTPServer`` so the GET/POST/serialization path is genuinely covered.
"""

from __future__ import annotations

import importlib.util
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent.parent / "api"


def _load(module_name: str):
    path = _API_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"api_{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Server:
    """Context manager running one handler on an ephemeral localhost port."""

    def __init__(self, handler_cls):
        self._handler_cls = handler_cls

    def __enter__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), self._handler_cls)
        self.port = self.httpd.server_address[1]
        self._t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._t.start()
        return self

    def request(self, method: str, path: str, body: bytes | None = None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"Content-Type": "application/json"} if body else {}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class HandlerShapeTests(unittest.TestCase):
    def test_every_handler_is_a_request_handler(self):
        for name in ("answer", "rigor", "registries", "health"):
            mod = _load(name)
            self.assertTrue(hasattr(mod, "handler"), f"{name}: no handler")
            self.assertTrue(
                issubclass(mod.handler, BaseHTTPRequestHandler),
                f"{name}: handler is not a BaseHTTPRequestHandler",
            )


class EngineGlueTests(unittest.TestCase):
    def test_answer_compose_helper_returns_typed_answer(self):
        mod = _load("answer")
        a = mod._compose("CBD evidence in Dravet syndrome")
        self.assertTrue(hasattr(a, "to_dict"))
        self.assertIsInstance(a.to_dict(), dict)

    def test_rigor_report_helper_flags_thca_thc(self):
        mod = _load("rigor")
        rep = mod._rigor_report("this cultivar tests at 22% THC by HPLC")
        self.assertFalse(rep["clean"])
        self.assertIn("counts", rep)


class HTTPRoundTripTests(unittest.TestCase):
    def test_health_get(self):
        mod = _load("health")
        with _Server(mod.handler) as s:
            status, data = s.request("GET", "/api/health")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["curated_registries"], 21)

    def test_answer_get_json(self):
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, data = s.request(
                "GET",
                "/?question=How%20does%20chronic%20cannabis%20use%20alter%20"
                "insulin%20sensitivity%20in%20metabolic%20syndrome%3F",
            )
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertTrue(payload["ok"])
        self.assertIn("answer", payload)
        # The curated endocrine registry should anchor this one.
        pmids = {
            c.get("pmid")
            for c in payload["answer"].get("citations", [])
            if c.get("pmid")
        }
        self.assertIn("23684393", pmids)  # Penner 2013 NHANES

    def test_answer_post_missing_question_is_400(self):
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, data = s.request("POST", "/api/answer", body=b"{}")
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(data)["ok"])

    def test_answer_markdown_format(self):
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, data = s.request(
                "GET", "/?question=CBD%20in%20Dravet%20syndrome&format=markdown"
            )
        self.assertEqual(status, 200)
        self.assertIn(b"## ", data)  # rendered Markdown

    def test_options_preflight(self):
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, _ = s.request("OPTIONS", "/api/answer")
        self.assertEqual(status, 204)


if __name__ == "__main__":
    unittest.main()
