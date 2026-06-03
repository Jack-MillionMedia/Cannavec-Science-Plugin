"""In-suite guard for the discovery RANKING proof.

The full battery lives in ``evals/prove_ranking.py`` (and runs as a dedicated CI
step); this keeps the load-bearing invariants in the per-run unit suite so a
regression in the discovery ranking behaviour — human-trial-first, preclinical /
animal demotion, cannabinoid synonyms, affix matching, cross-source dedup,
recency-never-beats-design, retraction sink — is caught locally and offline.
"""
from __future__ import annotations

import unittest

from evals.prove_ranking import run_checks


class DiscoveryRankingProofTests(unittest.TestCase):
    def test_all_ranking_invariants_hold(self):
        failed = [(name, detail) for (name, ok, detail) in run_checks() if not ok]
        self.assertEqual(
            failed, [],
            "discovery ranking regressions:\n"
            + "\n".join(f"  {name}: {detail}" for name, detail in failed),
        )


if __name__ == "__main__":
    unittest.main()
