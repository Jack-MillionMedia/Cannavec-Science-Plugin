"""Tests for cannavec_science.rcsb_discover.

Cannabis-primary-source widening — life-science skill layer.
Covers full-text search, direct PDB ID lookup, and refusal preflight.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.rcsb_discover import (  # noqa: E402
    NetworkError,
    RCSBEntryRow,
    RCSBSearcher,
    render_json,
    render_markdown,
)
from cannavec_science.discover_guard import (  # noqa: E402
    DiscoverRefused,
    Provenance,
)


class _StubFetcher:
    """Variadic stub matching both `fetcher(url)` and `fetcher(url, body=...)`."""

    def __init__(self, url_map: dict[str, str]) -> None:
        self._url_map = url_map
        self.calls: list[tuple[str, bytes | None]] = []

    def __call__(self, url: str, *, body: bytes | None = None) -> str:
        self.calls.append((url, body))
        for needle, payload in self._url_map.items():
            if needle in url:
                return payload
        raise AssertionError(
            f"Unexpected URL: {url!r}. Known: {list(self._url_map)}"
        )


_SEARCH_RESULT = json.dumps({
    "result_set": [
        {"identifier": "6N4B", "score": 1.0},
        {"identifier": "6PT0", "score": 0.98},
    ],
    "total_count": 2,
})


def _entry_fixture(pdb_id: str = "6N4B") -> str:
    return json.dumps({
        "struct": {
            "title": (
                "Crystal structure of human CB1 receptor in complex with "
                "agonist AM11542"
            ),
        },
        "exptl": [{"method": "X-RAY DIFFRACTION"}],
        "refine": [{"ls_d_res_high": 2.6}],
        "rcsb_entry_info": {
            "resolution_combined": [2.6],
            "polymer_entity_count": 2,
        },
        "rcsb_accession_info": {
            "deposit_date": "2018-11-21",
            "initial_release_date": "2019-01-23",
        },
        "entity_src_gen": [{
            "pdbx_gene_src_scientific_name": "Homo sapiens",
        }],
        "citation": [{
            "id": "primary",
            "pdbx_database_id_pub_med": 30664813,
            "pdbx_database_id_doi": "10.1016/j.cell.2018.11.040",
        }],
    })


class HappyPathTests(unittest.TestCase):
    def test_full_text_search_yields_rows(self) -> None:
        fetcher = _StubFetcher({
            "/rcsbsearch/v2/query": _SEARCH_RESULT,
            "/core/entry/6N4B": _entry_fixture("6N4B"),
            "/core/entry/6PT0": _entry_fixture("6PT0"),
        })
        s = RCSBSearcher(fetcher=fetcher)
        rows = s.search("cannabinoid CB1 agonist", max_results=2)
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first.pdb_id, "6N4B")
        self.assertIn("CB1", first.title)
        self.assertEqual(first.source, Provenance.LIVE_RCSB)
        self.assertEqual(first.primary_citation_pmid, "30664813")
        self.assertAlmostEqual(first.resolution_angstrom or 0.0, 2.6)
        self.assertIn("live_rcsb", first.suggested_grade)

    def test_direct_pdb_id_short_circuits_search(self) -> None:
        fetcher = _StubFetcher({
            "/core/entry/6N4B": _entry_fixture("6N4B"),
        })
        s = RCSBSearcher(fetcher=fetcher)
        rows = s.search("6N4B")
        self.assertEqual(len(rows), 1)
        # The search endpoint must not have been touched.
        for url, _body in fetcher.calls:
            self.assertNotIn("rcsbsearch", url)


class EmptyResultTests(unittest.TestCase):
    def test_search_with_no_hits_returns_empty_list(self) -> None:
        fetcher = _StubFetcher({
            "/rcsbsearch/v2/query": json.dumps({"result_set": []}),
        })
        s = RCSBSearcher(fetcher=fetcher)
        self.assertEqual(s.search("ridiculously rare ligand"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry(url, *, body=None):
            raise AssertionError("fetched anyway")
        s = RCSBSearcher(fetcher=angry)
        with self.assertRaises(DiscoverRefused):
            s.search("how to make JWH-018 K2 spice")


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = RCSBSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")

    def test_max_results_out_of_range(self) -> None:
        s = RCSBSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CB1", max_results=999)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry(url, *, body=None):
            raise OSError("connection refused")
        s = RCSBSearcher(fetcher=angry)
        with self.assertRaises(NetworkError):
            s.search("CB1")


class RenderingTests(unittest.TestCase):
    def test_markdown_includes_rcsb_header(self) -> None:
        row = RCSBEntryRow(
            pdb_id="6N4B", query="CB1",
            title="Crystal structure of CB1 with AM11542",
            deposit_date="2018-11-21",
            release_date="2019-01-23",
            experimental_method="X-RAY DIFFRACTION",
            resolution_angstrom=2.6,
            polymer_entity_count=2,
            source_organisms=("Homo sapiens",),
            primary_citation_pmid="30664813",
            primary_citation_doi="10.1016/j.cell.2018.11.040",
        )
        md = render_markdown("CB1", [row])
        self.assertIn("live_rcsb", md)
        self.assertIn("6N4B", md)
        self.assertIn("X-RAY", md)
        self.assertIn("2.6", md)

    def test_markdown_empty_rows_friendly_note(self) -> None:
        md = render_markdown("phlogiston", [])
        self.assertIn("No PDB entries", md)

    def test_json_round_trip(self) -> None:
        row = RCSBEntryRow(
            pdb_id="6N4B", query="CB1",
            title="x",
            deposit_date=None, release_date=None,
            experimental_method=None,
            resolution_angstrom=None,
            polymer_entity_count=None,
            source_organisms=(),
            primary_citation_pmid=None,
            primary_citation_doi=None,
        )
        payload = json.loads(render_json("CB1", [row]))
        self.assertEqual(payload["provenance"], "live_rcsb")
        self.assertEqual(payload["hits"][0]["source"], "live_rcsb")


if __name__ == "__main__":
    unittest.main()
