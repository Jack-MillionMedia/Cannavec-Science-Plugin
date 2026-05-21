"""Tests for cannavec_science.gwas_discover."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.gwas_discover import (  # noqa: E402
    GWASSearcher,
    GWASStudyRow,
    NetworkError,
    render_json,
    render_markdown,
)
from cannavec_science.discover_guard import (  # noqa: E402
    DiscoverRefused,
    Provenance,
)


class _StubFetcher:
    def __init__(self, url_map: dict[str, str]) -> None:
        self._url_map = url_map
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        for needle, body in self._url_map.items():
            if needle in url:
                return body
        raise AssertionError(
            f"Unexpected URL: {url!r}. Known: {list(self._url_map)}"
        )


def _study_block() -> dict:
    return {
        "accessionId": "GCST007090",
        "diseaseTrait": {"trait": "Cannabis use"},
        "initialSampleSize": "184,765 European ancestry individuals",
        "publication": {
            "pubmedId": "30150663",
            "publicationDate": "2018-08-28",
            "journal": "Nature Neuroscience",
        },
        "associations": {"count": 35},
        "efoTraits": [{"trait": "cannabis use measurement"}],
        "genomewideArray": True,
    }


_TRAIT_SEARCH = json.dumps({
    "_embedded": {
        "studies": [_study_block()]
    }
})


_SINGLE_STUDY = json.dumps(_study_block())


class HappyPathTests(unittest.TestCase):
    def test_trait_search_yields_genome_wide_row(self) -> None:
        fetcher = _StubFetcher({
            "/studies?": _TRAIT_SEARCH,
        })
        s = GWASSearcher(fetcher=fetcher)
        rows = s.search("cannabis use")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.accession_id, "GCST007090")
        self.assertEqual(r.pubmed_id, "30150663")
        self.assertTrue(r.is_genome_wide)
        # Genome-wide significance lifts the cap from C to B.
        self.assertIn("Level B", r.suggested_grade)
        self.assertEqual(r.source, Provenance.LIVE_GWAS)

    def test_direct_gcst_accession_short_circuits(self) -> None:
        fetcher = _StubFetcher({
            "/studies/GCST007090": _SINGLE_STUDY,
        })
        s = GWASSearcher(fetcher=fetcher)
        rows = s.search("GCST007090")
        self.assertEqual(len(rows), 1)
        for url in fetcher.calls:
            self.assertNotIn("disease_trait", url)

    def test_non_genome_wide_drops_to_level_c(self) -> None:
        block = _study_block()
        block["genomewideArray"] = False
        block.pop("full_pvalue_set", None)
        block.pop("fullPvalueSet", None)
        fetcher = _StubFetcher({
            "/studies?": json.dumps({"_embedded": {"studies": [block]}}),
        })
        s = GWASSearcher(fetcher=fetcher)
        rows = s.search("cannabis use")
        self.assertFalse(rows[0].is_genome_wide)
        self.assertIn("Level C", rows[0].suggested_grade)


class EmptyResultTests(unittest.TestCase):
    def test_no_studies_returns_empty(self) -> None:
        fetcher = _StubFetcher({
            "/studies?": json.dumps({"_embedded": {"studies": []}}),
        })
        s = GWASSearcher(fetcher=fetcher)
        self.assertEqual(s.search("very rare trait"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry(url):
            raise AssertionError("fetched anyway")
        s = GWASSearcher(fetcher=angry)
        with self.assertRaises(DiscoverRefused):
            s.search("synthesize K2 Spice JWH-018")


class NetworkErrorTests(unittest.TestCase):
    def test_html_body_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({"/studies?": "<html>500</html>"})
        s = GWASSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("cannabis use")


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = GWASSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")


class RenderingTests(unittest.TestCase):
    def test_markdown_includes_gwas_header(self) -> None:
        row = GWASStudyRow(
            accession_id="GCST007090", query="cannabis use",
            disease_trait="Cannabis use",
            initial_sample_description="184,765 individuals",
            pubmed_id="30150663", publication_date="2018-08-28",
            journal="Nature Neuroscience", n_associations=35,
            n_efo_traits=1, is_genome_wide=True,
            suggested_grade="Level B (provisional, live_gwas)",
        )
        md = render_markdown("cannabis use", [row])
        self.assertIn("live_gwas", md)
        self.assertIn("GCST007090", md)
        self.assertIn("30150663", md)

    def test_json_round_trip(self) -> None:
        row = GWASStudyRow(
            accession_id="X", query="q",
            disease_trait=None, initial_sample_description=None,
            pubmed_id=None, publication_date=None, journal=None,
            n_associations=None, n_efo_traits=None,
            is_genome_wide=False,
            suggested_grade="Level C (provisional, live_gwas)",
        )
        payload = json.loads(render_json("q", [row]))
        self.assertEqual(payload["provenance"], "live_gwas")
        self.assertEqual(payload["hits"][0]["source"], "live_gwas")


if __name__ == "__main__":
    unittest.main()
