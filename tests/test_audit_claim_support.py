"""Offline wiring/resilience test for the claim-support audit harness.

The verdict logic is covered by tests/test_claim_support.py. This exercises the
harness over the real interaction registry with an *injected* abstract fetcher,
so no network is touched: it confirms the registry is walked, the fetch is
cached/injected, and a network gap degrades to inconclusive rather than flagging.
"""

from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "evals"))

import audit_claim_support  # noqa: E402

_RICH = (
    "Cannabidiol and tetrahydrocannabinol inhibited CYP3A4, CYP2C19, CYP2C9, "
    "CYP2D6 and CYP1A2 activity, increasing clobazam, warfarin, midazolam and "
    "tacrolimus exposure (AUC and Cmax). No induction was observed."
)


class ClaimSupportHarness(unittest.TestCase):
    def test_network_gap_is_inconclusive_not_flags(self) -> None:
        flags, checked, inconclusive = audit_claim_support.review_interactions(
            fetch=lambda pmid: None
        )
        self.assertEqual(flags, [])
        self.assertEqual(checked, 0)
        self.assertGreater(inconclusive, 0)

    def test_walks_registry_with_injected_abstract(self) -> None:
        flags, checked, inconclusive = audit_claim_support.review_interactions(
            fetch=lambda pmid: _RICH
        )
        self.assertGreater(checked, 0)
        self.assertEqual(inconclusive, 0)
        # flags is well-formed: (cannabinoid, drug, pmid, report) tuples.
        for cb, drug, pmid, report in flags:
            self.assertTrue(pmid)
            self.assertTrue(report.needs_review)

    def test_fetch_is_cached_per_pmid(self) -> None:
        calls: list[str] = []

        def counting_fetch(pmid: str):
            calls.append(pmid)
            return _RICH

        audit_claim_support.review_interactions(fetch=counting_fetch)
        self.assertEqual(len(calls), len(set(calls)), "same PMID fetched more than once")


if __name__ == "__main__":
    unittest.main()
