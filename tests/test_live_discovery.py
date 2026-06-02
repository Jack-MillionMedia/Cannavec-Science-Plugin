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


class RefineQueryTests(unittest.TestCase):
    def test_drops_function_and_research_words(self):
        toks = live.refine_query(
            "Does cannabidiol alter tear film osmolarity in dry eye?"
        ).split()
        self.assertIn("cannabidiol", toks)
        self.assertIn("osmolarity", toks)
        for dropped in ("does", "alter", "in", "the"):
            self.assertNotIn(dropped, toks)

    def test_keeps_short_medical_tokens(self):
        toks = live.refine_query(
            "How does THC change TSH, free T3 and T4 levels?"
        ).split()
        for kept in ("thc", "tsh", "t3", "t4", "free"):
            self.assertIn(kept, toks)
        self.assertNotIn("levels", toks)

    def test_dedup_preserves_first(self):
        out = live.refine_query("cannabis cannabis cannabis insulin")
        self.assertEqual(out.split().count("cannabis"), 1)

    def test_all_stopwords_falls_back_to_original(self):
        self.assertTrue(live.refine_query("the of in and"))


class AugmentUsesRefinedQueryTests(unittest.TestCase):
    def test_augment_searches_keyword_query_not_raw_sentence(self):
        a = compose_answer(
            "What is the effect of cannabidiol on tear film osmolarity in "
            "dry eye?"
        )
        seen = {}

        def _rec(query, since, n):
            seen["q"] = query
            return []

        live.augment_answer(a, sources=["pubmed"], runners={"pubmed": _rec})
        toks = seen["q"].split()
        self.assertIn("cannabidiol", toks)
        self.assertIn("osmolarity", toks)
        # function / research words must be gone
        self.assertNotIn("what", toks)
        self.assertNotIn("effect", toks)


class IsThinTests(unittest.TestCase):
    def _fake(self, *, is_refusal=False, claims=(), highest=None):
        import types
        es = types.SimpleNamespace(highest_grade=highest) if highest else None
        return types.SimpleNamespace(
            is_refusal=is_refusal, claims=list(claims), evidence_summary=es,
        )

    def test_no_claims_is_thin(self):
        self.assertTrue(live.is_thin(self._fake(claims=[])))

    def test_refusal_is_never_thin(self):
        self.assertFalse(live.is_thin(self._fake(is_refusal=True, claims=[])))

    def test_unsupported_grade_is_thin(self):
        from cannavec_science.evidence import EvidenceLevel
        a = self._fake(claims=["x"], highest=EvidenceLevel.UNSUPPORTED)
        self.assertTrue(live.is_thin(a))

    def test_graded_claim_is_not_thin(self):
        from cannavec_science.evidence import EvidenceLevel
        a = self._fake(claims=["x"], highest=EvidenceLevel.B)
        self.assertFalse(live.is_thin(a))

    def test_real_curated_answer_is_not_thin(self):
        a = compose_answer(
            "How does chronic cannabis use alter insulin sensitivity in "
            "metabolic syndrome?"
        )
        self.assertFalse(live.is_thin(a))


class AnswerWithFallbackTests(unittest.TestCase):
    _NOVEL = (
        "What is the effect of cannabidiol on the tensile strength of "
        "spider silk fibres?"
    )

    def test_curated_question_skips_fallback(self):
        # A well-covered question must NOT trigger live discovery — the spy
        # runner must never be called.
        called = {"n": 0}

        def _spy(query, since, n):
            called["n"] += 1
            return []

        a, used = live.answer_with_fallback(
            "How does chronic cannabis use alter insulin sensitivity in "
            "metabolic syndrome?",
            runners={"pubmed": _spy, "ctgov": _spy},
        )
        self.assertFalse(used)
        self.assertEqual(called["n"], 0)
        self.assertGreaterEqual(len(a.claims), 1)
        self.assertEqual(len(a.live_findings), 0)

    def test_novel_question_triggers_fallback(self):
        rows = [_FakeHit(pmid="55555", title="A live frontier hit", year=2025)]
        a, used = live.answer_with_fallback(
            self._NOVEL,
            sources=["pubmed"],
            runners={"pubmed": _pubmed_runner(rows)},
        )
        # Confirm the question really is uncovered, then that fallback fired.
        self.assertEqual(len(a.claims), 0)
        self.assertTrue(used)
        self.assertEqual(len(a.live_findings), 1)
        # A clarifying note is added when the brief is built from live data.
        self.assertTrue(any("Live discovery" in n for n in a.notes))

    def test_novel_question_degrades_when_live_unavailable(self):
        def _boom(query, since, n):
            raise RuntimeError("offline")

        a, used = live.answer_with_fallback(
            self._NOVEL, sources=["pubmed"], runners={"pubmed": _boom}
        )
        # Fallback was attempted (used=True) but nothing attached, and the
        # curated (empty) brief still returns without error.
        self.assertTrue(used)
        self.assertEqual(len(a.live_findings), 0)

    def test_no_live_match_adds_honest_note(self):
        # Fallback runs but the live lanes find nothing → an honest note that
        # points the user at the focused-keyword path.
        a, used = live.answer_with_fallback(
            self._NOVEL, sources=["pubmed"],
            runners={"pubmed": _pubmed_runner([])},
        )
        self.assertTrue(used)
        self.assertEqual(len(a.live_findings), 0)
        self.assertTrue(
            any("no precise primary-source match" in n for n in a.notes)
        )


if __name__ == "__main__":
    unittest.main()
