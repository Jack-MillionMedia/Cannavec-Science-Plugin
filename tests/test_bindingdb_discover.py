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


# Fixtures captured verbatim from the live BindingDB REST API on 2026-06-07
# (a trimmed subset of the real rows), NOT a hand-written shape. The live
# API wraps results under "getLindsByUniprotsResponse" / "getLindsByPDBsResponse"
# — note "Linds", a typo in BindingDB's own JSON — with the affinity list
# under .affinities, and uses singular "smile", string "affinity" values that
# may carry a ">"/"<" relational qualifier, and "query" for the target name.
# Earlier hand-written fixtures used a top-level {"affinities": [...]} shape
# the server never returns, so the lane returned 0 rows for every real query.
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bindingdb"
_CB1_UNIPROT_RESPONSE = (_FIXTURES / "getLigandsByUniprots_P21554.json").read_text()
_PDB_6N4B_RESPONSE = (_FIXTURES / "getLigandsByPDBs_6N4B.json").read_text()


class HappyPathTests(unittest.TestCase):
    def test_cb1_keyword_resolves_to_uniprot_and_returns_rows(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": _CB1_UNIPROT_RESPONSE,
        })
        s = BindingDBSearcher(fetcher=fetcher)
        rows = s.search("CB1", max_results=2)
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first.source, Provenance.LIVE_BINDINGDB)
        self.assertEqual(first.monomer_id, "21256")
        self.assertEqual(first.target_uniprot, "P21554")
        # Target name comes from the live "query" field.
        self.assertEqual(first.target_name, "Cannabinoid receptor 1")
        self.assertEqual(first.affinity_type, "Ki")
        self.assertAlmostEqual(first.affinity_value_nm or 0.0, 37.0)
        self.assertEqual(first.source_pmid, "18293908")
        self.assertEqual(first.source_doi, "10.1021/jm070566z")
        self.assertIn("live_bindingdb", first.suggested_grade)

    def test_real_typo_envelope_key_yields_rows(self) -> None:
        # Regression: the real envelope key is "getLindsByUniprotsResponse"
        # ("Linds"). A parser that only recognises the correctly-spelled or
        # differently-misspelled keys returns 0 rows for every real query.
        self.assertIn("getLindsByUniprotsResponse", _CB1_UNIPROT_RESPONSE)
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": _CB1_UNIPROT_RESPONSE,
        })
        rows = BindingDBSearcher(fetcher=fetcher).search("CB1", max_results=10)
        self.assertEqual(len(rows), 5)

    def test_smile_field_is_parsed(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": _CB1_UNIPROT_RESPONSE,
        })
        rows = BindingDBSearcher(fetcher=fetcher).search("CB1", max_results=10)
        # The live API uses the singular "smile" key; SMILES must survive.
        self.assertEqual(
            rows[0].smiles,
            "Cc1c(nn(c1-n1cccc1)-c1ccc(Cl)cc1Cl)C(=O)NCc1ccc(Cl)c(Cl)c1",
        )
        self.assertTrue(all(r.smiles for r in rows))

    def test_qualified_affinity_retains_bound(self) -> None:
        # ">50" is a lower bound and "<10"/"<100" are upper bounds; the
        # numeric portion is parsed and the relational qualifier retained so
        # a bound is never presented as an exact measurement.
        fetcher = _StubFetcher({
            "/rest/getLigandsByUniprots": _CB1_UNIPROT_RESPONSE,
        })
        rows = BindingDBSearcher(fetcher=fetcher).search("CB1", max_results=10)
        by_id = {r.monomer_id: r for r in rows}

        plain = by_id["21256"]
        self.assertAlmostEqual(plain.affinity_value_nm or 0.0, 37.0)
        self.assertIsNone(plain.affinity_qualifier)

        lower = by_id["50265648"]
        self.assertAlmostEqual(lower.affinity_value_nm or 0.0, 50.0)
        self.assertEqual(lower.affinity_qualifier, ">")

        upper = by_id["614222"]
        self.assertAlmostEqual(upper.affinity_value_nm or 0.0, 10.0)
        self.assertEqual(upper.affinity_qualifier, "<")

    def test_pdb_query_uses_pdb_endpoint(self) -> None:
        fetcher = _StubFetcher({
            "/rest/getLigandsByPDBs": _PDB_6N4B_RESPONSE,
        })
        s = BindingDBSearcher(fetcher=fetcher)
        rows = s.search("6N4B")
        self.assertGreater(len(rows), 0)
        self.assertTrue(
            any("getLigandsByPDBs" in u for u in fetcher.calls)
        )
        # The PDB envelope is also misspelled ("getLindsByPDBsResponse") and
        # carries ">2820" lower-bound affinities — both must parse.
        first = rows[0]
        self.assertAlmostEqual(first.affinity_value_nm or 0.0, 2820.0)
        self.assertEqual(first.affinity_qualifier, ">")


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

    def test_markdown_shows_qualifier_not_equals(self) -> None:
        # A lower-bound affinity must render as "Ki > 2820 nM", never
        # "Ki = 2820 nM" — a bound is not an exact measurement.
        row = BindingDBRow(
            monomer_id="21243",
            target_uniprot="P21554",
            target_name="Cannabinoid receptor 1",
            smiles="O=C(NN1CCCCC1)c1cc(-n2cccc2)n(n1)-c1ccccc1",
            affinity_type="Ki",
            affinity_value_nm=2820.0,
            source_pmid="18293908",
            source_doi=None,
            affinity_qualifier=">",
        )
        md = render_markdown("6N4B", [row])
        self.assertIn("Ki > 2820 nM", md)
        self.assertNotIn("Ki = 2820 nM", md)

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
