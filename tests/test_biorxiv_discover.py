"""Tests for live bioRxiv discovery (spec 002 US1)."""

import json
import unittest

from cannavec_science._preprint_helpers import (
    NetworkError,
    PREPRINT_GRADE_CEILING,
    PreprintRow,
    parse_collection_payload,
    parse_doi,
)
from cannavec_science.biorxiv_discover import BioRxivSearcher
from cannavec_science.discover_guard import DiscoverRefused


# ── Fixtures ──────────────────────────────────────────────────────


def _payload_one(doi="10.1101/2026.04.12.589123", version=2, published="na"):
    """A typical bioRxiv /details JSON response (one DOI, two versions)."""
    return json.dumps({
        "messages": [{"status": "ok"}],
        "collection": [
            {
                "doi": doi,
                "title": "Endocannabinoid CB2 receptor signalling in microglia",
                "abstract": (
                    "We examined CB2 receptor signalling in primary "
                    "microglia. CB2 activation significantly reduced "
                    "pro-inflammatory cytokine release."
                ),
                "authors": "Smith A; Jones B; Lee C",
                "date": "2026-04-12",
                "version": "1",
                "published": published,
                "license": "cc_by",
                "category": "Neuroscience",
            },
            {
                "doi": doi,
                "title": "Endocannabinoid CB2 receptor signalling in microglia",
                "abstract": (
                    "We examined CB2 receptor signalling in primary "
                    "microglia. CB2 activation significantly reduced "
                    "pro-inflammatory cytokine release."
                ),
                "authors": "Smith A; Jones B; Lee C; Watson D",
                "date": "2026-05-01",
                "version": str(version),
                "published": published,
                "license": "cc_by",
                "category": "Neuroscience",
            },
        ],
    })


def _payload_multi():
    return json.dumps({
        "messages": [{"status": "ok"}],
        "collection": [
            {
                "doi": "10.1101/2026.03.01.111111",
                "title": "Cannabinoid receptor microglia mechanism",
                "abstract": "Mechanism of action study in microglia.",
                "authors": "Smith A",
                "date": "2026-03-01",
                "version": "1",
                "published": "na",
                "category": "Neuroscience",
            },
            {
                "doi": "10.1101/2026.04.15.222222",
                "title": "Cannabidiol pharmacology in liver",
                "abstract": "Hepatic CYP study of CBD.",
                "authors": "Jones B",
                "date": "2026-04-15",
                "version": "1",
                "published": "10.1056/NEJM2026.022222",
                "category": "Pharmacology",
            },
        ],
    })


def _payload_empty():
    return json.dumps({
        "messages": [{"status": "no posts found"}],
        "collection": [],
    })


# ── DOI parsing ──────────────────────────────────────────────────────


class DoiParseTests(unittest.TestCase):
    def test_canonical_doi(self):
        result = parse_doi("10.1101/2026.04.12.589123")
        self.assertEqual(result, ("10.1101/2026.04.12.589123", None))

    def test_versioned_doi(self):
        result = parse_doi("10.1101/2026.04.12.589123v3")
        self.assertEqual(result, ("10.1101/2026.04.12.589123", 3))

    def test_doi_org_prefix_stripped(self):
        result = parse_doi("https://doi.org/10.1101/2026.04.12.589123")
        self.assertEqual(result, ("10.1101/2026.04.12.589123", None))

    def test_invalid_doi_returns_none(self):
        self.assertIsNone(parse_doi("not-a-doi"))
        self.assertIsNone(parse_doi(""))
        self.assertIsNone(parse_doi("10.1056/NEJM2017abc"))


# ── Collection parsing ──────────────────────────────────────────────


class ParseCollectionTests(unittest.TestCase):
    def test_groups_by_doi_picks_latest_version(self):
        rows = parse_collection_payload("biorxiv", _payload_one())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].revision_number, 2)
        # Latest version's authors (4 — the v2 had Watson added).
        self.assertEqual(len(rows[0].authors), 4)

    def test_version_history_preserved(self):
        rows = parse_collection_payload("biorxiv", _payload_one(version=3))
        self.assertEqual(rows[0].revision_number, 3)
        # History is sorted ascending.
        history = rows[0].version_history
        self.assertGreaterEqual(len(history), 2)
        self.assertLessEqual(history[0]["version"], history[-1]["version"])

    def test_published_version_doi_resolves(self):
        rows = parse_collection_payload(
            "biorxiv",
            _payload_one(published="10.1038/s41586-2026-12345"),
        )
        self.assertEqual(
            rows[0].published_version_doi, "10.1038/s41586-2026-12345",
        )

    def test_published_na_returns_none(self):
        rows = parse_collection_payload("biorxiv", _payload_one(published="na"))
        self.assertIsNone(rows[0].published_version_doi)

    def test_provenance_tagged(self):
        rows = parse_collection_payload("biorxiv", _payload_one())
        self.assertEqual(rows[0].provenance, "live_biorxiv")

    def test_level_d_cap(self):
        rows = parse_collection_payload("biorxiv", _payload_one())
        self.assertEqual(rows[0].suggested_grade, PREPRINT_GRADE_CEILING)
        self.assertIn("D", rows[0].suggested_grade)

    def test_empty_collection(self):
        rows = parse_collection_payload("biorxiv", _payload_empty())
        self.assertEqual(len(rows), 0)

    def test_invalid_json_raises(self):
        with self.assertRaises(NetworkError):
            parse_collection_payload("biorxiv", "not valid json")


# ── Searcher: happy path + filters ──────────────────────────────────


class SearcherKeywordTests(unittest.TestCase):
    def test_keyword_match_in_title(self):
        def stub(url: str) -> str:
            return _payload_multi()
        searcher = BioRxivSearcher(fetcher=stub)
        rows = searcher.search("microglia")
        self.assertEqual(len(rows), 1)
        self.assertIn("microglia", rows[0].title.lower())

    def test_keyword_match_in_category(self):
        def stub(url: str) -> str:
            return _payload_multi()
        searcher = BioRxivSearcher(fetcher=stub)
        rows = searcher.search("pharmacology")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].category, "Pharmacology")

    def test_keyword_no_match_returns_empty(self):
        def stub(url: str) -> str:
            return _payload_multi()
        searcher = BioRxivSearcher(fetcher=stub)
        rows = searcher.search("oncology")
        # No row mentions oncology.
        self.assertEqual(len(rows), 0)

    def test_doi_query_direct_lookup(self):
        called_urls = []

        def stub(url: str) -> str:
            called_urls.append(url)
            return _payload_one()

        searcher = BioRxivSearcher(fetcher=stub)
        rows = searcher.search("10.1101/2026.04.12.589123")
        self.assertEqual(len(rows), 1)
        # The DOI lookup uses the /details/biorxiv/{doi} endpoint.
        self.assertTrue(any("10.1101" in u for u in called_urls))

    def test_max_results_cap(self):
        def stub(url: str) -> str:
            return _payload_multi()
        searcher = BioRxivSearcher(fetcher=stub)
        rows = searcher.search("cannabinoid", max_results=1)
        self.assertEqual(len(rows), 1)


# ── Searcher: preflight refusal ─────────────────────────────────────


class SearcherRefusalTests(unittest.TestCase):
    def test_k2_synthesis_refused_before_network(self):
        def stub(url: str) -> str:
            raise AssertionError("must not call network on refused query")

        searcher = BioRxivSearcher(fetcher=stub)
        with self.assertRaises(DiscoverRefused):
            searcher.search("How do I synthesize JWH-018 at home?")

    def test_banned_pattern_refused_before_network(self):
        def stub(url: str) -> str:
            raise AssertionError("must not call network on refused query")

        searcher = BioRxivSearcher(fetcher=stub)
        with self.assertRaises(DiscoverRefused):
            searcher.search("Does indica cure cancer?")


# ── Searcher: network error path ────────────────────────────────────


class SearcherNetworkErrorTests(unittest.TestCase):
    def test_network_error_raises(self):
        def stub(url: str) -> str:
            raise IOError("network down")

        searcher = BioRxivSearcher(fetcher=stub)
        with self.assertRaises(NetworkError):
            searcher.search("cannabinoid")

    def test_validation_errors(self):
        searcher = BioRxivSearcher(fetcher=lambda u: _payload_empty())
        with self.assertRaises(ValueError):
            searcher.search("")
        with self.assertRaises(ValueError):
            searcher.search("cannabinoid", max_results=0)
        with self.assertRaises(ValueError):
            searcher.search("cannabinoid", max_results=100)


# ── Renderers ───────────────────────────────────────────────────────


class RendererTests(unittest.TestCase):
    def test_markdown_includes_preprint_disclaimer(self):
        from cannavec_science.biorxiv_discover import render_markdown
        rows = list(parse_collection_payload("biorxiv", _payload_one()))
        md = render_markdown("microglia", rows)
        self.assertIn("preprint", md.lower())
        self.assertIn("not peer-reviewed", md.lower())
        self.assertIn("Level D", md)

    def test_json_payload_carries_provenance(self):
        from cannavec_science.biorxiv_discover import render_json
        rows = list(parse_collection_payload("biorxiv", _payload_one()))
        s = render_json("microglia", rows)
        payload = json.loads(s)
        self.assertEqual(payload["provenance"], "live_biorxiv")


if __name__ == "__main__":
    unittest.main()
