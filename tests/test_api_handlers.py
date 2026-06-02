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
from unittest import mock
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
        self.last_headers = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, data

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class _FakeReranker:
    """Patched-in stand-in for LLMReranker — reorders without any network."""

    name = "llm"

    def __init__(self, *args, **kwargs):
        pass

    def plan(self, query, candidates):
        from cannavec_science.ranker import RankPlan
        order = tuple(c.identifier for c in reversed(list(candidates)))
        return RankPlan(order=order, rationales={}, backend="llm")


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
        # Ranking capability probe: deterministic ranking always on; the LLM
        # rerank flag is split so a false value is diagnosable (package vs key).
        self.assertTrue(payload["ranking"])
        self.assertIn("anthropic_installed", payload)
        self.assertIn("anthropic_key_set", payload)
        self.assertEqual(
            payload["llm_rerank"],
            payload["anthropic_installed"] and payload["anthropic_key_set"],
        )

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


class DiscoverHandlerTests(unittest.TestCase):
    """Phase-2 /api/discover — exercised with live.run_discovery monkeypatched
    so no network is touched."""

    def test_discover_get_returns_synthesis(self):
        from cannavec_science import live
        canned = {
            "query": "cannabis melatonin",
            "sources": {"pubmed": [{"pmid": "123", "title": "x"}]},
            "synthesis": {"convergence": "WEAK"},
        }
        mod = _load("discover")
        with mock.patch.object(live, "run_discovery", return_value=canned):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/?query=cannabis%20melatonin")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["synthesis"]["convergence"], "WEAK")

    def test_discover_missing_query_is_400(self):
        mod = _load("discover")
        with _Server(mod.handler) as s:
            status, data = s.request("GET", "/api/discover")
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(data)["ok"])

    def test_discover_refusal_is_422(self):
        from cannavec_science import live
        mod = _load("discover")
        with mock.patch.object(
            live, "run_discovery",
            side_effect=live.DiscoverRefused("refused: synthesis route"),
        ):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/?query=make%20K2%20at%20home")
        self.assertEqual(status, 422)
        payload = json.loads(data)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["refused"])

    def test_discover_includes_deterministic_ranking_by_default(self):
        from cannavec_science import live
        canned = {
            "query": "cbd epilepsy",
            "sources": {"pubmed": [
                {"pmid": "1", "title": "Cannabidiol for epilepsy: a systematic review",
                 "year": 2022, "pubtypes": ["Systematic Review"],
                 "retraction_status": "clean"},
                {"pmid": "2", "title": "A case report on hop brewing chemistry",
                 "year": 2005, "pubtypes": ["Case Reports"],
                 "retraction_status": "clean"},
            ]},
            "synthesis": {"convergence": "WEAK"},
        }
        mod = _load("discover")
        with mock.patch.object(live, "run_discovery", return_value=canned):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/?query=cbd%20epilepsy")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertIn("ranking", payload)
        self.assertEqual(payload["ranking"]["backend_used"], "deterministic")
        ids = [r["identifier"] for r in payload["ranking"]["ranked"]]
        self.assertEqual(ids[0], "1")  # the on-topic SR outranks the off-topic case report

    def test_discover_rank_false_omits_ranking(self):
        from cannavec_science import live
        canned = {"query": "x", "sources": {"pubmed": [{"pmid": "1", "title": "x"}]},
                  "synthesis": {"convergence": "WEAK"}}
        mod = _load("discover")
        with mock.patch.object(live, "run_discovery", return_value=canned):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/?query=x&rank=false")
        self.assertEqual(status, 200)
        self.assertNotIn("ranking", json.loads(data))

    def test_discover_rerank_force_calls_llm_even_when_decisive(self):
        # A clearly-dominant SR would not naturally escalate; rerank=force
        # bypasses the short-circuit and exercises the LLM path on demand.
        from cannavec_science import live
        canned = {"query": "cbd epilepsy", "sources": {"pubmed": [
            {"pmid": "1", "title": "Cannabidiol for epilepsy: a systematic review and meta-analysis",
             "year": 2024, "pubtypes": ["Systematic Review"], "retraction_status": "clean"},
            {"pmid": "2", "title": "Hop brewing chemistry", "year": 2005,
             "pubtypes": ["Case Reports"], "retraction_status": "clean"},
            {"pmid": "3", "title": "Industrial hemp fibre processing", "year": 2004,
             "pubtypes": ["Case Reports"], "retraction_status": "clean"},
        ]}, "synthesis": {"convergence": "WEAK"}}
        mod = _load("discover")
        with mock.patch.object(live, "run_discovery", return_value=canned), \
                mock.patch("cannavec_science.ranker_llm.LLMReranker", _FakeReranker):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/?query=cbd%20epilepsy&rerank=force")
        self.assertEqual(status, 200)
        ranking = json.loads(data)["ranking"]
        self.assertEqual(ranking["backend_used"], "llm")
        self.assertTrue(ranking["escalated"])


class AnswerAugmentHandlerTests(unittest.TestCase):
    def test_augment_true_weaves_live_findings(self):
        from cannavec_science import live

        def _fake_augment(answer, **kw):
            answer.add_live_finding(
                label="Fresh hit", identifier="PMID 42",
                source_tag="live_pubmed",
            )
            return 1

        mod = _load("answer")
        with mock.patch.object(live, "augment_answer", side_effect=_fake_augment):
            with _Server(mod.handler) as s:
                status, data = s.request(
                    "GET", "/?question=CBD%20in%20Dravet%20syndrome&augment=true"
                )
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["augmented"], 1)
        self.assertEqual(len(payload["answer"]["live_findings"]), 1)

    def test_default_answer_is_not_augmented(self):
        # A well-curated question must NOT trigger the Phase-3 fallback.
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, data = s.request(
                "GET", "/?question=CBD%20in%20Dravet%20syndrome"
            )
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["augmented"], 0)
        self.assertFalse(payload["fallback_used"])


class AnswerFallbackHandlerTests(unittest.TestCase):
    """Phase 3 — /api/answer auto-falls-back to live discovery when curated
    coverage is thin, with no augment flag."""

    _NOVEL = (
        "What is the effect of cannabidiol on the tensile strength of "
        "spider silk fibres?"
    )

    def test_thin_question_triggers_fallback(self):
        from cannavec_science import live

        def _fake_fallback(question, **kw):
            from cannavec_science.answer import compose_answer
            a = compose_answer(question)
            a.add_live_finding(
                label="Live frontier hit", identifier="PMID 7",
                source_tag="live_pubmed",
            )
            return a, True

        mod = _load("answer")
        with mock.patch.object(live, "answer_with_fallback",
                               side_effect=_fake_fallback):
            with _Server(mod.handler) as s:
                status, data = s.request(
                    "GET", "/?question=some%20novel%20cannabis%20question"
                )
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["augmented"], 1)
        self.assertEqual(len(payload["answer"]["live_findings"]), 1)

    def test_curated_question_does_not_fall_back(self):
        # Real call (no monkeypatch): insulin is curated → not thin → no live
        # search, so this stays fully offline.
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, data = s.request(
                "GET",
                "/?question=How%20does%20chronic%20cannabis%20use%20alter%20"
                "insulin%20sensitivity%20in%20metabolic%20syndrome%3F",
            )
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertFalse(payload["fallback_used"])
        self.assertEqual(payload["augmented"], 0)
        pmids = {c.get("pmid") for c in payload["answer"]["citations"]}
        self.assertIn("23684393", pmids)

    def test_fallback_can_be_disabled(self):
        # fallback=false routes to the pure-curated path → no live search even
        # for a thin question (offline-safe, deterministic).
        mod = _load("answer")
        with _Server(mod.handler) as s:
            status, data = s.request(
                "GET",
                "/?question=" + self._NOVEL.replace(" ", "%20") + "&fallback=false",
            )
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertFalse(payload["fallback_used"])
        self.assertEqual(payload["augmented"], 0)
        self.assertEqual(len(payload["answer"]["live_findings"]), 0)


class HealthLiveFlagTests(unittest.TestCase):
    def test_live_discovery_true_when_key_set(self):
        mod = _load("health")
        with mock.patch.dict("os.environ", {"NCBI_API_KEY": "KEY"}):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/api/health")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertTrue(payload["live_discovery"])
        self.assertEqual(payload["phase"], 2)

    def test_live_discovery_false_when_key_absent(self):
        mod = _load("health")
        with mock.patch.dict("os.environ", {}, clear=True):
            with _Server(mod.handler) as s:
                status, data = s.request("GET", "/api/health")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertFalse(payload["live_discovery"])
        self.assertEqual(payload["phase"], 1)

    def test_health_is_never_cached(self):
        # A liveness probe must always reflect the running deployment.
        mod = _load("health")
        with _Server(mod.handler) as s:
            s.request("GET", "/api/health")
            self.assertEqual(s.last_headers.get("cache-control"), "no-store")


if __name__ == "__main__":
    unittest.main()
