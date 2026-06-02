"""Offline tests for the primary-source discovery index.

The index is a candidate pool (NOT curated facts); these tests pin its shape
and the discovery-vs-curated contract, not the scientific content.
"""
from __future__ import annotations

import unittest

from cannavec_science import source_index as si


class SourceIndexTests(unittest.TestCase):
    def test_loads_thousands(self):
        idx = si.load_index()
        self.assertGreaterEqual(len(idx), 7000)

    def test_schema_well_formed(self):
        for s in si.load_index()[:200]:
            self.assertIn(s.type, {"PubMed", "PMC", "DOI"})
            self.assertTrue(s.identifier)
            self.assertTrue(s.url.startswith("http"))
            self.assertIsInstance(s.curated, bool)

    def test_topics_present(self):
        self.assertGreaterEqual(len(si.topics()), 10)

    def test_by_topic_consistent(self):
        t = si.topics()[0]
        subset = si.by_topic(t)
        self.assertTrue(subset)
        self.assertTrue(all(s.topic == t for s in subset))

    def test_curated_flag_marks_some(self):
        idx = si.load_index()
        self.assertGreater(sum(1 for s in idx if s.curated), 0)

    def test_is_a_candidate_pool_not_curated_facts(self):
        # The overwhelming majority are discovery candidates, not curated —
        # the curated tier stays small and high-trust (Constitution §IX).
        idx = si.load_index()
        self.assertLess(sum(s.curated for s in idx), len(idx) // 10)

    def test_exclude_curated_filter(self):
        all_n = len(si.candidates())
        nocur = len(si.candidates(include_curated=False))
        self.assertLessEqual(nocur, all_n)


if __name__ == "__main__":
    unittest.main()
