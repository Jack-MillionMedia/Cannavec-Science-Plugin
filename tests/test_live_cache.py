"""Tests for :mod:`cannavec_science.live_cache` — the verified-source flywheel.

Fully offline (Constitution §X): every test points the store at a tmp dir and
injects a fake retraction checker, so neither the network nor the package
``data/`` directory is touched.

The cache is a LIVE-tier accelerator, not the archived §IX curation flywheel:
it never promotes to the curated registry, and retraction is RE-CHECKED on
every read (§VIII) — a source clean at write time but retracted later is never
served.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from cannavec_science import live_cache as lc


def _row(**d) -> dict:
    return dict(d)


# A fake retraction checker: flags the PMIDs in ``flagged`` as retracted.
def _checker(flagged: set[str]):
    class _Rec:
        status = "retracted"

    def _is_retracted(*, pmid=None, doi=None):
        if pmid and pmid in flagged:
            return _Rec()
        return None
    return _is_retracted


class CacheRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="cvcache-")

    def test_write_through_then_read_same_query(self):
        sources = {
            "pubmed": [
                _row(pmid="42077359", title="CB1 and working memory", year="2026",
                     source_tag="live_pubmed", retraction_status="clean"),
                _row(pmid="40876704", title="Cannabis and brain", year="2026",
                     retraction_status="clean"),
            ],
        }
        n = lc.record_discovery(
            "How does cannabis CB1 alter short-term memory?",
            sources, store_dir=self._dir, is_retracted=_checker(set()),
        )
        self.assertEqual(n, 2)
        hits = lc.fetch_for_query(
            "How does cannabis CB1 alter short-term memory?",
            store_dir=self._dir, is_retracted=_checker(set()),
        )
        self.assertEqual({h["pmid"] for h in hits}, {"42077359", "40876704"})
        self.assertTrue(all(h.get("from_cache") for h in hits))

    def test_rows_without_resolvable_identifier_are_not_cached(self):
        # An ontology-only / title-only row has no citable identifier — it must
        # not enter the verified-source store (§I primary-source).
        sources = {"efo": [_row(efo_id="EFO:0000249", title="alzheimer disease")]}
        n = lc.record_discovery(
            "alzheimer", sources, store_dir=self._dir, is_retracted=_checker(set()),
        )
        self.assertEqual(n, 0)
        self.assertEqual(
            lc.fetch_for_query("alzheimer", store_dir=self._dir,
                               is_retracted=_checker(set())),
            [],
        )

    def test_retracted_row_not_cached_at_write(self):
        sources = {"pubmed": [
            _row(pmid="111", title="bad", year="2020", retraction_status="clean"),
        ]}
        # The checker flags 111 as retracted → it must be refused at write.
        n = lc.record_discovery(
            "q", sources, store_dir=self._dir, is_retracted=_checker({"111"}),
        )
        self.assertEqual(n, 0)

    def test_retraction_rechecked_on_read(self):
        # Cached clean, but the registry later flags it retracted → never served.
        sources = {"pubmed": [
            _row(pmid="222", title="ok then retracted", year="2021",
                 retraction_status="clean"),
        ]}
        lc.record_discovery("q2", sources, store_dir=self._dir,
                            is_retracted=_checker(set()))
        # Read with a checker that now flags 222.
        hits = lc.fetch_for_query("q2", store_dir=self._dir,
                                  is_retracted=_checker({"222"}))
        self.assertEqual(hits, [], "a now-retracted source must not be served")

    def test_query_normalization_matches_rephrased_scaffolding(self):
        # Interrogative scaffolding is distilled away, so "What is X?" and "X"
        # resolve to the same cache key.
        sources = {"pubmed": [_row(pmid="333", title="t", year="2022")]}
        lc.record_discovery("What is THC CB1 agonism?", sources,
                            store_dir=self._dir, is_retracted=_checker(set()))
        hits = lc.fetch_for_query("THC CB1 agonism", store_dir=self._dir,
                                  is_retracted=_checker(set()))
        self.assertEqual({h["pmid"] for h in hits}, {"333"})

    def test_missing_store_degrades_to_empty(self):
        empty = os.path.join(self._dir, "does-not-exist-yet")
        self.assertEqual(
            lc.fetch_for_query("q", store_dir=empty, is_retracted=_checker(set())),
            [],
        )

    def test_stats_counts_sources_and_queries(self):
        sources = {"pubmed": [
            _row(pmid="1", title="a", year="2020"),
            _row(pmid="2", title="b", year="2021"),
        ]}
        lc.record_discovery("qA", sources, store_dir=self._dir,
                            is_retracted=_checker(set()))
        lc.record_discovery("qB", {"pubmed": [_row(pmid="1", title="a", year="2020")]},
                            store_dir=self._dir, is_retracted=_checker(set()))
        st = lc.stats(store_dir=self._dir)
        # 2 distinct sources (pmid 1, 2); 2 distinct queries.
        self.assertEqual(st["sources"], 2)
        self.assertEqual(st["queries"], 2)


class ResolveIdentifierTests(unittest.TestCase):
    def test_pmid_preferred_over_doi(self):
        self.assertEqual(
            lc.resolve_identifier({"pmid": "9", "doi": "10.1/x"}), ("pmid", "9"),
        )

    def test_doi_when_no_pmid(self):
        self.assertEqual(
            lc.resolve_identifier({"doi": "10.1/x"}), ("doi", "10.1/x"),
        )

    def test_ontology_only_row_has_no_citable_id(self):
        # efo_id / pathway_id are ontology ids, not citable primary sources.
        self.assertIsNone(lc.resolve_identifier({"efo_id": "EFO:1", "title": "t"}))
        self.assertIsNone(lc.resolve_identifier({"title": "no id at all"}))


if __name__ == "__main__":
    unittest.main()
