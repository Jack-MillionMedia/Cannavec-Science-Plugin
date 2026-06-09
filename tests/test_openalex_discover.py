"""Tests for cannavec_science.openalex_discover (spec 006 US6 / FR-007)."""

from __future__ import annotations

import json
import unittest

from cannavec_science.discover_guard import Provenance
from cannavec_science.openalex_discover import (
    LiveOpenAlexHit,
    OpenAlexSearcher,
    SearchRefused,
    render_json,
    render_markdown,
    suggested_grade_for_openalex_type,
)


def _make_work(
    work_id: str = "W123456789",
    doi: str = "https://doi.org/10.1000/test",
    pmid: str = "12345678",
    title: str = "Cannabis psychosis test paper",
    pub_year: int = 2023,
    cited_by_count: int = 17,
    type_: str = "journal-article",
    first_author: str = "Di Forti",
    venue: str = "Lancet Psychiatry",
    is_open_access: bool = True,
    concepts: list[str] | None = None,
) -> dict:
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": doi,
        "ids": {"pmid": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"} if pmid else {},
        "title": title,
        "publication_year": pub_year,
        "cited_by_count": cited_by_count,
        "type": type_,
        "authorships": [
            {
                "author": {"display_name": "Di Forti M"},
                "author_position": "first",
            },
        ],
        "primary_location": {
            "source": {"display_name": venue},
            "is_oa": is_open_access,
        },
        "open_access": {"is_oa": is_open_access},
        "concepts": [
            {"display_name": c, "score": 0.9, "level": 2}
            for c in (concepts or ["Cannabis", "Psychosis", "Epidemiology"])
        ],
    }


def _make_payload(works: list[dict], meta_count: int | None = None) -> str:
    return json.dumps({
        "meta": {
            "count": meta_count if meta_count is not None else len(works),
            "page": 1,
            "per_page": len(works),
        },
        "results": works,
    })


def _stub_fetcher(payload: str):
    calls: list[str] = []

    def f(url: str) -> str:
        calls.append(url)
        return payload

    f.calls = calls
    return f


class HappyPathTests(unittest.TestCase):
    def test_three_hits_returned(self):
        payload = _make_payload([
            _make_work("W1", title="Paper 1"),
            _make_work("W2", title="Paper 2"),
            _make_work("W3", title="Paper 3"),
        ])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis psychosis", max_results=5)
        self.assertEqual(len(hits), 3)
        self.assertEqual(hits[0].openalex_id, "W1")

    def test_fetcher_receives_url(self):
        payload = _make_payload([_make_work()])
        fetcher = _stub_fetcher(payload)
        s = OpenAlexSearcher(fetcher=fetcher)
        s.search("cannabis psychosis Di Forti")
        self.assertTrue(fetcher.calls)
        url = fetcher.calls[0]
        self.assertIn("openalex.org", url)
        self.assertIn("cannabis", url.lower())

    def test_max_results_capped(self):
        s = OpenAlexSearcher(fetcher=_stub_fetcher(_make_payload([])))
        with self.assertRaises(ValueError):
            s.search("")  # empty query rejected

    def test_provenance_tagged(self):
        payload = _make_payload([_make_work()])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("Di Forti 2019 EU-GEI cannabis psychosis")
        self.assertEqual(hits[0].provenance, Provenance.LIVE_OPENALEX.value)


class ParseTests(unittest.TestCase):
    def test_doi_normalized(self):
        payload = _make_payload([_make_work(doi="https://doi.org/10.1234/abc")])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        h = s.search("cannabis")[0]
        self.assertEqual(h.doi, "10.1234/abc")

    def test_pmid_extracted(self):
        payload = _make_payload([_make_work(pmid="98765432")])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        h = s.search("cannabis")[0]
        self.assertEqual(h.pmid, "98765432")

    def test_no_pmid_blank(self):
        payload = _make_payload([_make_work(pmid="")])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        h = s.search("cannabis")[0]
        self.assertEqual(h.pmid, "")

    def test_empty_results(self):
        s = OpenAlexSearcher(fetcher=_stub_fetcher(_make_payload([])))
        hits = s.search("query that returns nothing")
        self.assertEqual(hits, ())

    def test_invalid_json_returns_empty(self):
        s = OpenAlexSearcher(fetcher=_stub_fetcher("not json"))
        hits = s.search("cannabis")
        self.assertEqual(hits, ())


class GradeHeuristicTests(unittest.TestCase):
    def test_meta_analysis_level_a(self):
        # OpenAlex doesn't always tag meta-analyses; we rely on
        # concept inspection. Synthetic meta-analysis concept tag.
        # Use type=journal-article + concept matching.
        self.assertTrue(
            suggested_grade_for_openalex_type(
                "journal-article", concepts=("Meta-analysis", "Cannabis")
            ).startswith("Level A")
        )

    def test_systematic_review_level_a(self):
        self.assertTrue(
            suggested_grade_for_openalex_type(
                "journal-article", concepts=("Systematic review", "Cannabis")
            ).startswith("Level A")
        )

    def test_rct_level_b(self):
        self.assertTrue(
            suggested_grade_for_openalex_type(
                "journal-article",
                concepts=("Randomized controlled trial",),
            ).startswith("Level B")
        )

    def test_preprint_level_d(self):
        self.assertTrue(
            suggested_grade_for_openalex_type(
                "preprint", concepts=("Cannabis",)
            ).startswith("Level D")
        )

    def test_unknown_unsupported(self):
        self.assertTrue(
            suggested_grade_for_openalex_type(
                "blog-post", concepts=()
            ).startswith("Unsupported")
        )


class SafetyPreflightTests(unittest.TestCase):
    def test_banned_pattern_refuses(self):
        payload = _make_payload([_make_work()])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        with self.assertRaises(SearchRefused):
            s.search("how to synthesize K2 spice synthetic cannabinoid")


class RenderingTests(unittest.TestCase):
    def test_markdown_contains_query(self):
        payload = _make_payload([_make_work(work_id="W42")])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis psychosis")
        md = render_markdown("cannabis psychosis", hits)
        self.assertIn("OpenAlex", md)
        self.assertIn("W42", md)

    def test_json_contains_provenance(self):
        payload = _make_payload([_make_work()])
        s = OpenAlexSearcher(fetcher=_stub_fetcher(payload))
        hits = s.search("cannabis")
        j = render_json("cannabis", hits)
        data = json.loads(j)
        self.assertEqual(data["provenance"], "live_openalex")
        self.assertEqual(len(data["hits"]), 1)

    def test_no_hits_renders_message(self):
        s = OpenAlexSearcher(fetcher=_stub_fetcher(_make_payload([])))
        hits = s.search("nothing")
        md = render_markdown("nothing", hits)
        self.assertIn("No hits", md)


class QueryDistillationTests(unittest.TestCase):
    """OpenAlex's ``search=`` is keyword-based and (like PubMed) returns nothing
    for a raw interrogative question. The lane must distill the query first.
    """

    def test_natural_language_question_is_distilled(self):
        from urllib.parse import unquote_plus

        fetcher = _stub_fetcher(_make_payload([_make_work()]))
        s = OpenAlexSearcher(fetcher=fetcher)
        s.search("What is the molecular difference between THC and CBD?")
        url = fetcher.calls[0]
        # Extract the search= value and decode it.
        search_val = unquote_plus(url.split("search=")[1].split("&")[0])
        tokens = search_val.split()
        self.assertNotIn("What", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("between", tokens)
        for kw in ("molecular", "difference", "THC", "CBD"):
            self.assertIn(kw, tokens)


if __name__ == "__main__":
    unittest.main()
