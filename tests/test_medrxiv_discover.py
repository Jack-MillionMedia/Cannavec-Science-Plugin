"""Tests for live medRxiv discovery (spec 002 US1).

Mirrors test_biorxiv_discover.py — the two preprint lanes share the
underlying ``_preprint_helpers`` module so the heavy parsing tests are
in the bioRxiv suite; this suite focuses on the medRxiv-specific bits
(provenance tag, URL hostname, search class).
"""

import json
import unittest

from cannavec_science._preprint_helpers import (
    NetworkError,
    PREPRINT_GRADE_CEILING,
    parse_collection_payload,
)
from cannavec_science.discover_guard import DiscoverRefused
from cannavec_science.medrxiv_discover import (
    MedRxivSearcher,
    render_json,
    render_markdown,
)


def _payload_one():
    return json.dumps({
        "messages": [{"status": "ok"}],
        "collection": [
            {
                "doi": "10.1101/2026.05.10.567890",
                "title": "CBD pharmacokinetics in adolescent epilepsy patients",
                "abstract": (
                    "We characterised CBD pharmacokinetics in 24 "
                    "adolescents with refractory epilepsy. Half-life was "
                    "consistent with the adult literature."
                ),
                "authors": "Patel R; Garcia M; Kim S",
                "date": "2026-05-10",
                "version": "1",
                "published": "na",
                "category": "Clinical Pharmacology",
            },
        ],
    })


def _payload_empty():
    return json.dumps({
        "messages": [{"status": "no posts found"}],
        "collection": [],
    })


class ParseTests(unittest.TestCase):
    def test_medrxiv_provenance_tagged(self):
        rows = parse_collection_payload("medrxiv", _payload_one())
        self.assertEqual(rows[0].provenance, "live_medrxiv")

    def test_level_d_grade(self):
        rows = parse_collection_payload("medrxiv", _payload_one())
        self.assertEqual(rows[0].suggested_grade, PREPRINT_GRADE_CEILING)

    def test_url_uses_medrxiv_hostname(self):
        rows = parse_collection_payload("medrxiv", _payload_one())
        self.assertIn("medrxiv.org", rows[0].url)


class SearcherTests(unittest.TestCase):
    def test_keyword_search_happy_path(self):
        def stub(url: str) -> str:
            return _payload_one()
        searcher = MedRxivSearcher(fetcher=stub)
        rows = searcher.search("epilepsy")
        self.assertEqual(len(rows), 1)

    def test_doi_direct_lookup(self):
        called_urls = []

        def stub(url: str) -> str:
            called_urls.append(url)
            return _payload_one()

        searcher = MedRxivSearcher(fetcher=stub)
        rows = searcher.search("10.1101/2026.05.10.567890")
        self.assertEqual(len(rows), 1)
        # medRxiv URL hostname.
        self.assertTrue(any("medrxiv" in u for u in called_urls))

    def test_preflight_refusal(self):
        def stub(url: str) -> str:
            raise AssertionError("must not call network on refused query")

        searcher = MedRxivSearcher(fetcher=stub)
        with self.assertRaises(DiscoverRefused):
            searcher.search("How do I synthesize JWH-018 at home?")

    def test_network_error_raises(self):
        def stub(url: str) -> str:
            raise IOError("network down")

        searcher = MedRxivSearcher(fetcher=stub)
        with self.assertRaises(NetworkError):
            searcher.search("epilepsy")

    def test_empty_results(self):
        def stub(url: str) -> str:
            return _payload_empty()
        searcher = MedRxivSearcher(fetcher=stub)
        rows = searcher.search("nonexistent-topic-xyz")
        self.assertEqual(len(rows), 0)


class RenderTests(unittest.TestCase):
    def test_markdown_includes_preprint_disclaimer(self):
        rows = list(parse_collection_payload("medrxiv", _payload_one()))
        md = render_markdown("epilepsy", rows)
        self.assertIn("preprint", md.lower())
        self.assertIn("Level D", md)

    def test_json_carries_provenance(self):
        rows = list(parse_collection_payload("medrxiv", _payload_one()))
        payload = json.loads(render_json("epilepsy", rows))
        self.assertEqual(payload["provenance"], "live_medrxiv")


if __name__ == "__main__":
    unittest.main()
