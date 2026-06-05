"""Tests for `cannavec_science.demand` — the misses ledger + topic routing.

Offline and hermetic: every test writes to a fresh tmp store dir, so the
shipped ``data/`` is never touched.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science import demand  # noqa: E402
from cannavec_science.demand import (  # noqa: E402
    DemandEvent,
    aggregate,
    classify_topic,
    demand_report,
    instrument_answer,
    priority_topics,
    record_demand,
)
from cannavec_science.evidence import EvidenceLevel  # noqa: E402


class TestClassifyTopic(unittest.TestCase):
    def test_named_demand_topics_route(self) -> None:
        cases = {
            "What is the pharmacokinetics of oral CBD, its Tmax and bioavailability?":
                "cbd_pharmacokinetics",
            "Does cannabis impair driving performance on the road?": "driving",
            "What does the evidence say about terpenes like myrcene and limonene?":
                "terpenes",
            "Can cannabidiol improve sleep quality and insomnia?": "sleep",
            "Cannabis for inflammatory bowel disease / Crohn's": "ibd",
            "Is cannabis effective for fibromyalgia?": "fibromyalgia",
            "Cannabinoids for migraine prophylaxis": "migraine",
        }
        for prompt, expected in cases.items():
            self.assertEqual(classify_topic(prompt), expected, prompt)

    def test_specific_topic_beats_generic_pain(self) -> None:
        # fibromyalgia / migraine must win over the generic 'pain' bucket.
        self.assertEqual(classify_topic("chronic widespread fibromyalgia pain"),
                         "fibromyalgia")
        self.assertEqual(classify_topic("migraine pain attacks"), "migraine")
        # ...but a bare pain question still routes to pain.
        self.assertEqual(classify_topic("cannabis for chronic neuropathic pain"),
                         "pain")

    def test_unmatched_is_unclassified(self) -> None:
        self.assertEqual(classify_topic("how tall is the tallest building"),
                         "unclassified")
        self.assertEqual(classify_topic(""), "unclassified")


class TestThinDerivation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_zero_claims_is_thin(self) -> None:
        ev = record_demand("cannabis for IBD", n_curated_claims=0, store_dir=self.dir)
        self.assertTrue(ev.thin)

    def test_unsupported_grade_is_thin(self) -> None:
        ev = record_demand("terpene myrcene effects", n_curated_claims=3,
                           highest_grade="Unsupported", store_dir=self.dir)
        self.assertTrue(ev.thin)

    def test_good_coverage_is_not_thin(self) -> None:
        ev = record_demand("CBD in Dravet", n_curated_claims=4,
                           highest_grade="Level A", store_dir=self.dir)
        self.assertFalse(ev.thin)

    def test_refusal_is_never_a_miss(self) -> None:
        ev = record_demand("how do I dose my own seizures", n_curated_claims=0,
                           refusal=True, store_dir=self.dir)
        self.assertFalse(ev.thin)
        self.assertTrue(ev.refusal)


class TestReportAndPriority(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed(self) -> None:
        # fibromyalgia: 3 asks, all thin (a hot hole)
        for _ in range(3):
            record_demand("fibromyalgia cannabis", n_curated_claims=0,
                          store_dir=self.dir)
        # ibd: 2 asks, both thin
        for _ in range(2):
            record_demand("crohn's disease cannabidiol", n_curated_claims=0,
                          store_dir=self.dir)
        # cbd_pk: 2 asks, well covered (not thin)
        for _ in range(2):
            record_demand("oral CBD pharmacokinetics Tmax", n_curated_claims=5,
                          highest_grade="Level B", store_dir=self.dir)

    def test_report_ranks_by_miss_volume(self) -> None:
        self._seed()
        report = demand_report(self.dir)
        topics = [t.topic for t in report]
        # fibromyalgia (3 misses) ranks above ibd (2 misses) above cbd_pk (0).
        self.assertLess(topics.index("fibromyalgia"), topics.index("ibd"))
        self.assertLess(topics.index("ibd"), topics.index("cbd_pharmacokinetics"))
        fibro = next(t for t in report if t.topic == "fibromyalgia")
        self.assertEqual(fibro.asks, 3)
        self.assertEqual(fibro.misses, 3)
        self.assertAlmostEqual(fibro.thin_rate, 1.0)
        cbd = next(t for t in report if t.topic == "cbd_pharmacokinetics")
        self.assertEqual(cbd.misses, 0)

    def test_priority_topics_picks_holes_only(self) -> None:
        self._seed()
        picks = priority_topics(5, store_dir=self.dir)
        self.assertEqual(picks[0], "fibromyalgia")
        self.assertIn("ibd", picks)
        # cbd_pk had zero misses → not a promotion target.
        self.assertNotIn("cbd_pharmacokinetics", picks)

    def test_priority_excludes_unclassified(self) -> None:
        for _ in range(5):
            record_demand("totally unrelated question", n_curated_claims=0,
                          store_dir=self.dir)
        self.assertNotIn("unclassified", priority_topics(10, store_dir=self.dir))


class TestInstrumentAnswer(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _answer(self, prompt, n_claims, grade, refusal=False):
        es = types.SimpleNamespace(highest_grade=grade)
        return types.SimpleNamespace(
            prompt=prompt,
            claims=[object()] * n_claims,
            is_refusal=refusal,
            evidence_summary=es,
        )

    def test_records_covered_answer(self) -> None:
        ans = self._answer("oral CBD pharmacokinetics", 4, EvidenceLevel.B)
        ev = instrument_answer(ans, store_dir=self.dir)
        self.assertEqual(ev.topic, "cbd_pharmacokinetics")
        self.assertEqual(ev.n_claims, 4)
        self.assertEqual(ev.highest_grade, "Level B")
        self.assertFalse(ev.thin)
        # ...and it landed in the ledger.
        self.assertEqual(len(demand_report(self.dir)), 1)

    def test_records_thin_answer(self) -> None:
        ans = self._answer("cannabis for fibromyalgia", 0, EvidenceLevel.UNSUPPORTED)
        ev = instrument_answer(ans, store_dir=self.dir)
        self.assertEqual(ev.topic, "fibromyalgia")
        self.assertTrue(ev.thin)

    def _answer_with_texts(self, prompt, texts, grade):
        es = types.SimpleNamespace(highest_grade=grade)
        claims = [types.SimpleNamespace(text=t) for t in texts]
        return types.SimpleNamespace(prompt=prompt, claims=claims,
                                     is_refusal=False, evidence_summary=es)

    def test_topic_specific_miss(self) -> None:
        # A fibromyalgia question answered only with generic pain claims that
        # never mention fibromyalgia is a *miss* — even at a high grade.
        ans = self._answer_with_texts(
            "Is cannabis effective for fibromyalgia?",
            ["The 2017 NASEM report found substantial evidence for chronic pain.",
             "A systematic review found moderate evidence for neuropathic pain."],
            EvidenceLevel.A)
        ev = instrument_answer(ans, store_dir=self.dir)
        self.assertEqual(ev.topic, "fibromyalgia")
        self.assertFalse(ev.thin)            # it returned claims
        self.assertFalse(ev.topic_covered)   # ...but none about fibromyalgia
        self.assertTrue(ev.miss)             # so it is still a promotable hole

    def test_topic_covered_when_claim_addresses_topic(self) -> None:
        ans = self._answer_with_texts(
            "cannabis for fibromyalgia",
            ["In fibromyalgia, a Δ⁹-THC-rich oil reduced FIQ scores versus placebo."],
            EvidenceLevel.C)
        ev = instrument_answer(ans, store_dir=self.dir)
        self.assertTrue(ev.topic_covered)
        self.assertFalse(ev.miss)

    def test_refusal_never_a_miss_even_if_uncovered(self) -> None:
        es = types.SimpleNamespace(highest_grade=None)
        ans = types.SimpleNamespace(prompt="how do I dose my own migraine",
                                    claims=[], is_refusal=True, evidence_summary=es)
        ev = instrument_answer(ans, store_dir=self.dir)
        self.assertFalse(ev.miss)


class TestDemandEventRoundTrip(unittest.TestCase):
    def test_to_from_dict(self) -> None:
        ev = DemandEvent("2026-06-03T00:00:00+00:00", "q", "sleep", 2, "Level C",
                         False, False)
        self.assertEqual(DemandEvent.from_dict(ev.to_dict()), ev)

    def test_aggregate_empty(self) -> None:
        self.assertEqual(aggregate([]), [])


if __name__ == "__main__":
    unittest.main()
