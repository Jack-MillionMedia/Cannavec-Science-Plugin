"""Tests for cannavec_science.bindingdb_discover."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.bindingdb_discover import (  # noqa: E402
    BindingDBRow,
    BindingDBSearcher,
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


_CB1_AFFINITIES = json.dumps({
    "affinities": [
        {
            "monomerid": "50000123",
            "uniProtId": "P21554",
            "targetName": "Cannabinoid receptor 1",
            "type": "Ki",
            "affinity": 4.4,
            "SMILES": "CCCCCc1cc(O)c2c(c1)OC(c1cc(O)cc1)CC2",
            "pmid": "23984728",
        },
        {
            "monomerid": "50000124",
            "uniProtId": "P21554",
            "targetName": "Cannabinoid receptor 1",
            "type": "IC50",
            "affinity": 27.5,
            "pmid": "29191878",
        },
    ]
})


class HappyPathTests(unittest.TestCase):
    def test_cb1_keyword_resolves_to_uniprot_and_returns_rows(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": _CB1_AFFINITIES,
        })
        s = BindingDBSearcher(fetcher=fetcher)
        rows = s.search("CB1", max_results=2)
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first.source, Provenance.LIVE_BINDINGDB)
        self.assertEqual(first.target_uniprot, "P21554")
        self.assertEqual(first.affinity_type, "Ki")
        self.assertAlmostEqual(first.affinity_value_nm or 0.0, 4.4)
        self.assertIn("live_bindingdb", first.suggested_grade)

    def test_pdb_query_uses_pdb_endpoint(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByPDBs": _CB1_AFFINITIES,
        })
        s = BindingDBSearcher(fetcher=fetcher)
        rows = s.search("6N4B")
        self.assertGreater(len(rows), 0)
        self.assertTrue(
            any("getLigandsByPDBs" in u for u in fetcher.calls)
        )


class EmptyResultTests(unittest.TestCase):
    def test_no_affinities_returns_empty(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": json.dumps({"affinities": []}),
        })
        s = BindingDBSearcher(fetcher=fetcher)
        self.assertEqual(s.search("CB1"), [])

    def test_unresolvable_query_returns_empty(self) -> None:
        fetcher = _StubFetcher({})
        s = BindingDBSearcher(fetcher=fetcher)
        # Unknown shorthand that isn't a UniProt accession and isn't a
        # cannabis-receptor alias: nothing to fetch, return empty.
        self.assertEqual(s.search("ZZ"), [])

    def test_empty_body_treated_as_no_results(self) -> None:
        # BindingDB sometimes returns an empty body for zero-hit queries.
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": "",
        })
        s = BindingDBSearcher(fetcher=fetcher)
        self.assertEqual(s.search("CB1"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry(url):
            raise AssertionError("fetched anyway")
        s = BindingDBSearcher(fetcher=angry)
        with self.assertRaises(DiscoverRefused):
            s.search("synthesize K2 Spice JWH-018")


class NetworkErrorTests(unittest.TestCase):
    def test_html_body_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": "<html>500</html>",
        })
        s = BindingDBSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("CB1")


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = BindingDBSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")

    def test_max_results_out_of_range(self) -> None:
        s = BindingDBSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CB1", max_results=999)


class RenderingTests(unittest.TestCase):
    def test_markdown_includes_bindingdb_header(self) -> None:
        row = BindingDBRow(
            monomer_id="50000123",
            target_uniprot="P21554",
            target_name="Cannabinoid receptor 1",
            smiles="CCCCC...",
            affinity_type="Ki",
            affinity_value_nm=4.4,
            source_pmid="23984728",
            source_doi=None,
        )
        md = render_markdown("CB1", [row])
        self.assertIn("live_bindingdb", md)
        self.assertIn("Cannabinoid receptor 1", md)
        self.assertIn("Ki", md)

    def test_json_round_trip(self) -> None:
        row = BindingDBRow(
            monomer_id="x", target_uniprot="P21554",
            target_name=None, smiles=None,
            affinity_type=None, affinity_value_nm=None,
            source_pmid=None, source_doi=None,
        )
        payload = json.loads(render_json("q", [row]))
        self.assertEqual(payload["provenance"], "live_bindingdb")
        self.assertEqual(payload["hits"][0]["source"], "live_bindingdb")


if __name__ == "__main__":
    unittest.main()
