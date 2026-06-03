"""Fast in-suite guard for the retrieval proof (Improvement Plan §1).

The full whole-KB sweep lives in ``evals/prove_retrieval.py`` and runs as a
dedicated offline CI step (≈9 s). This module keeps the cheap, load-bearing
invariants in the per-run unit suite so a regression is caught locally:

- negative controls surface nothing spurious ("reliable" ≠ "returns
  everything"), and
- on a set of natural, detector-hostile prose questions, retrieval surfaces
  the held evidence far more often than the keyword detectors alone.
"""

from __future__ import annotations

import unittest

from evals.prove_retrieval import measurement_b, measurement_c


class NegativeControlTests(unittest.TestCase):
    """Reliable retrieval must not hallucinate relevance."""

    def setUp(self):
        self.b = measurement_b()

    def test_no_generic_or_off_domain_leaks(self):
        self.assertEqual(
            self.b["false_pos"], 0,
            f"generic/off-domain queries leaked: {self.b['detail']}",
        )

    def test_no_cross_cannabinoid_leaks(self):
        self.assertEqual(
            self.b["cross_leak"], 0,
            f"cross-cannabinoid leak: {self.b['detail']}",
        )


class RealisticProbeLiftTests(unittest.TestCase):
    """Natural prose questions answer far more often with retrieval on."""

    def setUp(self):
        self.c = measurement_c()

    def test_retrieval_answers_more_than_detectors(self):
        self.assertGreater(self.c["on"], self.c["off"])

    def test_retrieval_answers_most_probes(self):
        # ≥ 80% of the natural-prose probes surface a claim with retrieval on.
        self.assertGreaterEqual(self.c["on"], int(0.8 * self.c["n"]))


if __name__ == "__main__":
    unittest.main()
