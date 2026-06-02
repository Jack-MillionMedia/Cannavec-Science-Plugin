"""Tests for the library-level live discovery (spec 028 / Phase 2).

Fully offline: every test injects fake ``runners`` (or monkeypatches the
preflight), so the network is never touched — the Constitution §X
injected-fetcher contract.
"""

from __future__ import annotations

import unittest
from unittest import mock

from cannavec_science import live
from cannavec_science.answer import compose_answer
from cannavec_science.discover_guard import DiscoverRefused


class _FakeHit:
    """Stand-in for a searcher's LiveHit (only needs ``.to_dict()``)."""

    def __init__(self, **d):
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _pubmed_runner(rows):
    def _runner(query, since, n):
        return rows[:n]
    return _runner


class RunDiscoveryTests(unittest.TestCase):
    def test_returns_rows_and_synthesis(self):
        rows = [
            _FakeHit(pmid="111", title="Hit one", year=2023),
            _FakeHit(pmid="222", title="Hit two", year=2024),
        ]
        result = live.run_discovery(
            "cannabis insulin sensitivity",
            sources=["pubmed"],
            runners={"pubmed": _pubmed_runner(rows)},
        )
        self.assertEqual(result["query"], "cannabis insulin sensitivity")
        self.assertEqual(len(result["sources"]["pubmed"]), 2)
        self.assertEqual(result["sources"]["pubmed"][0]["pmid"], "111")
        self.assertIn("synthesis", result)
        self.assertIn("convergence", result["synthesis"])

    def test_default_sources_when_none(self):
        # No runner invoked for a source we didn't fake → each unknown source
        # is captured as an error, but the default set is still consulted.
        result = live.run_discovery(
            "cannabis cortisol", runners={"pubmed": _pubmed_runner([])}
        )
        # DEFAULT_SOURCES is (pubmed, ctgov); pubmed present, ctgov errored.
        self.assertIn("pubmed", result["sources"])
        self.assertIn("ctgov", result["sources"])
        self.assertIn("error", result["sources"]["ctgov"])

    def test_lane_failure_degrades_gracefully(self):
        def _boom(query, since, n):
            raise RuntimeError("upstream 500")
        rows = [_FakeHit(pmid="333", title="ok", year=2022)]
        result = live.run_discovery(
            "cannabis bone density",
            sources=["pubmed", "chembl"],
            runners={"pubmed": _pubmed_runner(rows), "chembl": _boom},
        )
        self.assertEqual(len(result["sources"]["pubmed"]), 1)
        self.assertIn("error", result["sources"]["chembl"])
        # Synthesis still computed over the surviving lane.
        self.assertIn("synthesis", result)

    def test_empty_query_raises(self):
        with self.assertRaises(ValueError):
            live.run_discovery("   ")

    def test_max_results_clamped(self):
        rows = [_FakeHit(pmid=str(i), title="x", year=2020) for i in range(40)]
        result = live.run_discovery(
            "cannabis", sources=["pubmed"], max_results=999,
            runners={"pubmed": _pubmed_runner(rows)},
        )
        # Ceiling is 25.
        self.assertLessEqual(len(result["sources"]["pubmed"]), 25)

    def test_safety_refusal_propagates_and_skips_network(self):
        called = {"n": 0}

        def _spy(query, since, n):
            called["n"] += 1
            return []

        with mock.patch.object(
            live, "preflight",
            side_effect=DiscoverRefused("refused: test"),
        ):
            with self.assertRaises(DiscoverRefused):
                live.run_discovery(
                    "some refused query",
                    sources=["pubmed"],
                    runners={"pubmed": _spy},
                )
        self.assertEqual(called["n"], 0, "no lane should run after refusal")


class AugmentAnswerTests(unittest.TestCase):
    def test_augments_curated_answer_with_live_findings(self):
        a = compose_answer(
            "How does chronic cannabis use alter insulin sensitivity in "
            "metabolic syndrome?"
        )
        self.assertEqual(len(a.live_findings), 0)
        rows = [_FakeHit(pmid="99999999", title="Fresh live hit", year=2025)]
        n = live.augment_answer(
            a, sources=["pubmed"], runners={"pubmed": _pubmed_runner(rows)}
        )
        self.assertEqual(n, 1)
        self.assertEqual(len(a.live_findings), 1)
        self.assertEqual(a.live_findings[0]["source_tag"], "live_pubmed")
        # Curated claim is untouched (still its Level-C cited claim).
        self.assertGreaterEqual(len(a.claims), 1)

    def test_lane_failure_leaves_curated_answer_intact(self):
        a = compose_answer(
            "How does chronic cannabis use alter insulin sensitivity in "
            "metabolic syndrome?"
        )
        n_claims_before = len(a.claims)

        def _boom(query, since, n):
            raise RuntimeError("offline")

        n = live.augment_answer(
            a, sources=["pubmed"], runners={"pubmed": _boom}
        )
        self.assertEqual(n, 0)
        self.assertEqual(len(a.live_findings), 0)
        self.assertEqual(len(a.claims), n_claims_before)

    def test_refusal_degrades_to_zero(self):
        a = compose_answer("CBD in Dravet syndrome")
        with mock.patch.object(
            live, "preflight",
            side_effect=DiscoverRefused("refused"),
        ):
            n = live.augment_answer(a, sources=["pubmed"], runners={})
        self.assertEqual(n, 0)
        self.assertEqual(len(a.live_findings), 0)


if __name__ == "__main__":
    unittest.main()
