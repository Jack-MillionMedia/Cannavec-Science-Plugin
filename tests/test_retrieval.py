"""Tests for the cross-registry BM25 retrieval layer (Improvement Plan §1).

The per-registry keyword detectors are brittle (word-order / phrasing
sensitive), so the curated knowledge base could not reliably retrieve evidence
it already held — "how does THC impair driving" returned zero claims even
though the driving registry holds five rows. ``cannavec_science.retrieval``
fixes that with Okapi-BM25 over every curated row; this suite pins both the
engine and its integration into ``compose_answer``.

Stdlib only, fully offline, deterministic.
"""

from __future__ import annotations

import unittest

from cannavec_science import retrieval as R
from cannavec_science.answer import compose_answer
from cannavec_science.ranker import RankPlan


class CorpusTests(unittest.TestCase):
    def test_corpus_is_non_empty(self):
        self.assertGreater(R.corpus_size(), 50)

    def test_every_corpus_row_is_claim_bearing(self):
        # Retrieval surfaces curated rows that carry an identifier-anchored
        # claim (§I): every doc's row must expose ``to_claim()``.
        for d in R._corpus():
            self.assertTrue(hasattr(d.row, "to_claim"), d.identifier)

    def test_clear_cache_rebuilds(self):
        n1 = R.corpus_size()
        R.clear_corpus_cache()
        n2 = R.corpus_size()
        self.assertEqual(n1, n2)


class RetrievalGateTests(unittest.TestCase):
    """The "we have it but didn't find it" misses must fire; generic and
    off-domain queries must not (BM25 IDF + the coverage gate)."""

    def _registries(self, query: str) -> set:
        return {h.registry for h in R.retrieve(query, k=8)}

    def test_driving_query_hits_driving_registry(self):
        self.assertIn("driving_impairment",
                      self._registries("how does THC impair driving"))

    def test_cyp_query_hits_interaction_or_pgx(self):
        regs = self._registries("what CYP enzymes does CBD inhibit")
        self.assertTrue(regs & {"interactions", "pharmacogenomics"}, regs)

    def test_chs_query_hits_hyperemesis_registry(self):
        self.assertIn(
            "hyperemesis_syndrome",
            self._registries(
                "cannabinoid hyperemesis syndrome diagnostic criteria"
            ),
        )

    def test_withdrawal_query_hits_use_disorder(self):
        self.assertIn("use_disorder",
                      self._registries("cannabis withdrawal scale severity"))

    def test_generic_definition_query_returns_nothing(self):
        # A bare definitional prompt's only content token is a high-frequency
        # one (low IDF), so it must stay below threshold — the monograph path
        # owns "what is X", not retrieval.
        self.assertEqual(R.retrieve("What is CBD?"), [])
        self.assertEqual(R.retrieve("What is THC?"), [])
        self.assertEqual(R.retrieve("cannabis"), [])

    def test_off_domain_query_returns_nothing(self):
        self.assertEqual(R.retrieve("hello world stock market"), [])
        self.assertEqual(R.retrieve("what is the weather today"), [])
        self.assertEqual(R.retrieve("tell me a joke about computers"), [])

    def test_empty_query_returns_nothing(self):
        self.assertEqual(R.retrieve(""), [])
        self.assertEqual(R.retrieve("   "), [])

    def test_hits_are_sorted_by_score_desc(self):
        hits = R.retrieve("cannabinoid hyperemesis syndrome diagnostic criteria")
        scores = [h.score for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_k_caps_result_count(self):
        hits = R.retrieve("cannabis", k=3, min_bm25=0.0, min_coverage=0.0)
        self.assertLessEqual(len(hits), 3)

    def test_deterministic(self):
        q = "what CYP enzymes does CBD inhibit"
        a = [h.identifier for h in R.retrieve(q)]
        b = [h.identifier for h in R.retrieve(q)]
        self.assertEqual(a, b)


class RerankSeamTests(unittest.TestCase):
    """The optional rerank stage (e.g. the LLM reranker) reorders the gated
    shortlist; it is provenance-gated so it can only permute, never inject."""

    def test_injected_reranker_reorders_same_set(self):
        class Reverser:
            name = "fake"

            def plan(self, query, candidates):
                ids = [c.identifier for c in candidates]
                return RankPlan(order=tuple(reversed(ids)), backend="fake")

        q = "cannabinoid hyperemesis syndrome diagnostic criteria"
        base = R.retrieve(q, k=4)
        reranked = R.retrieve(q, k=4, reranker=Reverser())
        self.assertEqual(
            {h.identifier for h in base},
            {h.identifier for h in reranked},
        )
        self.assertEqual(
            [h.identifier for h in base],
            list(reversed([h.identifier for h in reranked])),
        )

    def test_reranker_cannot_inject_unknown_identifier(self):
        class Injector:
            name = "evil"

            def plan(self, query, candidates):
                return RankPlan(order=("not-a-real-id",), backend="evil")

        q = "cannabis withdrawal scale severity"
        base_ids = {h.identifier for h in R.retrieve(q, k=4)}
        reranked = R.retrieve(q, k=4, reranker=Injector())
        # The bogus identifier is dropped; the real shortlist is preserved.
        self.assertEqual({h.identifier for h in reranked}, base_ids)

    def test_reranker_exception_degrades_to_deterministic(self):
        class Broken:
            name = "broken"

            def plan(self, query, candidates):
                raise RuntimeError("backend down")

        q = "cannabis withdrawal scale severity"
        base = [h.identifier for h in R.retrieve(q, k=4)]
        reranked = [h.identifier for h in R.retrieve(q, k=4, reranker=Broken())]
        self.assertEqual(base, reranked)


class RetrievalRecoveryTests(unittest.TestCase):
    """Integration: the composer recovers curated rows the keyword detectors
    miss, without disturbing prompts the detectors already answer."""

    def _recovered(self, a) -> int:
        return sum(h for d, h in a.trace if d == "retrieval.recovered")

    def test_driving_miss_now_recovers_claims(self):
        a = compose_answer("how does THC impair driving")
        self.assertGreaterEqual(len(a.claims), 1)
        self.assertGreaterEqual(self._recovered(a), 1)

    def test_cyp_miss_now_recovers_claims(self):
        a = compose_answer("what CYP enzymes does CBD inhibit")
        self.assertGreaterEqual(len(a.claims), 1)
        self.assertGreaterEqual(self._recovered(a), 1)

    def test_recovery_is_what_fixes_it(self):
        # With retrieval off the prompt reproduces the pre-§1 zero-claim miss,
        # proving the recovery — not some other change — is responsible.
        off = compose_answer("how does THC impair driving", retrieval="off")
        self.assertEqual(len(off.claims), 0)

    def test_recovered_claims_are_primary_source_anchored(self):
        # §I — every recovered claim carries at least one verifiable identifier.
        a = compose_answer("how does THC impair driving")
        for c in a.claims:
            self.assertTrue(
                any(s.pmid or s.doi or s.url for s in c.sources),
                f"recovered claim lacks a primary source: {c.text[:60]!r}",
            )

    def test_detector_answered_prompt_is_unchanged(self):
        # Fallback retrieval must never fire when a detector already produced a
        # claim — a prompt that answers today answers identically.
        on = compose_answer("CBD evidence in Dravet syndrome")
        off = compose_answer("CBD evidence in Dravet syndrome", retrieval="off")
        self.assertEqual(len(on.claims), len(off.claims))
        self.assertEqual(self._recovered(on), 0)

    def test_cannabinoid_scope_filter_blocks_unrelated(self):
        # HHC has no curated HHC rows; retrieval must not attribute another
        # cannabinoid's evidence to it (spec 003 US2).
        a = compose_answer("HHC safety profile and adverse events")
        self.assertEqual(self._recovered(a), 0)
        for c in a.claims:
            self.assertNotIn("CBD ", c.text)
            self.assertNotIn("Δ⁹-THC ", c.text)

    def test_out_of_scope_prompt_keeps_guidance_note(self):
        # A cultivation/cultivar prompt is steered to the parent plugin by a
        # guidance note (spec 003 US9); retrieval must not override that.
        a = compose_answer("Bedrocan medical cannabis cultivars THC content")
        self.assertEqual(len(a.claims), 0)
        self.assertTrue(a.notes)
        self.assertEqual(self._recovered(a), 0)

    def test_augment_mode_unions_with_detectors(self):
        # In augment mode retrieval runs even when detectors found claims.
        a = compose_answer("how does THC impair driving", retrieval="augment")
        self.assertGreaterEqual(len(a.claims), 1)

    def test_refusal_prompt_gets_no_retrieval(self):
        a = compose_answer("How do I synthesize K2/Spice at home?")
        self.assertTrue(a.is_refusal)
        self.assertEqual(self._recovered(a), 0)


if __name__ == "__main__":
    unittest.main()
