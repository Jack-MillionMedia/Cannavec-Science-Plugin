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


class AdjudicateHarness(unittest.TestCase):
    """The optional LLM-adjudication layer over the real registry, fully offline
    via an injected fake client — proving the deterministic flagger gates which
    rows reach the model and that surfaced quotes are provenance-gated."""

    # A verbatim span of _RICH — a quote the provenance gate must accept.
    _QUOTE = "increasing clobazam, warfarin, midazolam and tacrolimus exposure"

    def _make_client(self, verdict: str, quote: str):
        import json

        body = json.dumps({"verdict": verdict, "quote": quote})

        class _Block:
            def __init__(self, t):
                self.text = t

        class _Resp:
            def __init__(self, t):
                self.content = [_Block(t)]

        class _Msgs:
            def create(self, **kwargs):
                return _Resp(body)

        class _Client:
            def __init__(self):
                self.messages = _Msgs()

        return _Client()

    def test_deterministic_only_review_queue(self) -> None:
        # No adjudicator: the flagged minority still surfaces, verdict-only.
        reviews, checked, inconclusive = audit_claim_support.adjudicate_interactions(
            fetch=lambda pmid: _RICH
        )
        self.assertGreater(checked, 0)
        self.assertEqual(inconclusive, 0)
        self.assertGreater(len(reviews), 0)
        for _cb, _drug, pmid, review in reviews:
            self.assertTrue(pmid)
            self.assertFalse(review.escalated)        # no backend ran
            self.assertIsNone(review.adjudication)

    def test_injected_adjudicator_attaches_verified_quotes(self) -> None:
        from cannavec_science.claim_support_llm import LLMAdjudicator

        adj = LLMAdjudicator(client=self._make_client("supported", self._QUOTE))
        reviews, checked, inconclusive = audit_claim_support.adjudicate_interactions(
            fetch=lambda pmid: _RICH, adjudicator=adj
        )
        self.assertEqual(inconclusive, 0)
        self.assertGreater(len(reviews), 0)
        # Every flagged row was escalated and carries the verbatim, verified quote.
        for _cb, _drug, _pmid, review in reviews:
            self.assertTrue(review.escalated)
            self.assertIsNotNone(review.adjudication)
            self.assertTrue(review.adjudication.quote_verified)
            self.assertEqual(review.adjudication.model, "claude-opus-4-8")

    def test_injected_adjudicator_drops_fabricated_quote(self) -> None:
        from cannavec_science.claim_support_llm import LLMAdjudicator

        adj = LLMAdjudicator(
            client=self._make_client("supported", "this sentence is nowhere in the source")
        )
        reviews, _checked, _inc = audit_claim_support.adjudicate_interactions(
            fetch=lambda pmid: _RICH, adjudicator=adj
        )
        self.assertGreater(len(reviews), 0)
        for _cb, _drug, _pmid, review in reviews:
            self.assertEqual(review.quote, "")          # fabricated → dropped
            self.assertFalse(review.adjudication.quote_verified)
            self.assertTrue(review.needs_human)         # contested → human


if __name__ == "__main__":
    unittest.main()
