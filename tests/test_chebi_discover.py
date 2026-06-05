"""Tests for cannavec_science.chebi_discover.

Spec 029 P1. Mirrors the pubchem_discover test style: injected fetcher,
fixture JSON captured verbatim from the live ChEBI 2.0 backend API
(``es_search`` + ``compound/<accession>/`` for cannabidiol CHEBI:69478
and Δ⁹-THC CHEBI:66964), no real network.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.chebi_discover import (  # noqa: E402
    ChEBICompoundRow,
    ChEBISearcher,
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
            f"Unexpected URL: {url!r}. Known needles: {list(self._url_map)}"
        )


# ── Fixtures: trimmed but field-faithful to the real ChEBI 2.0 responses ──

_CBD_SEARCH = json.dumps({
    "results": [{
        "_index": "chebi-prod-compounds-01062026",
        "_type": "_doc",
        "_id": "69478",
        "_score": 65.737274,
        "_source": {
            "chebi_accession": "CHEBI:69478",
            "name": "cannabidiol",
            "ascii_name": "cannabidiol",
        },
    }],
    "total": 12,
    "number_pages": 4,
})

# Note the duplicated "cannabinoid receptor agonist" role — the real record
# carries it twice; the lane must de-duplicate.
_CBD_COMPOUND = json.dumps({
    "id": 69478,
    "chebi_accession": "CHEBI:69478",
    "name": "cannabidiol",
    "ascii_name": "cannabidiol",
    "stars": 3,
    "definition": (
        "A cannabinoid that is cyclohexene substituted by a methyl group, a "
        "2,6-dihydroxy-4-pentylphenyl group and a prop-1-en-2-yl group."
    ),
    "secondary_ids": ["CHEBI:3358"],
    "chemical_data": {
        "formula": "C21H30O2", "charge": 0,
        "mass": "314.469", "monoisotopic_mass": "314.22458",
    },
    "compound_origins": [{
        "species_text": "Cannabis sativa", "species_accession": "3483",
        "component_text": "aerial part",
    }],
    "roles_classification": [
        {"chebi_accession": "CHEBI:33281", "name": "antimicrobial agent",
         "biological_role": True},
        {"chebi_accession": "CHEBI:76924", "name": "plant metabolite",
         "biological_role": True},
        {"chebi_accession": "CHEBI:35472", "name": "cannabinoid receptor agonist",
         "biological_role": True},
        {"chebi_accession": "CHEBI:35472", "name": "cannabinoid receptor agonist",
         "biological_role": True},
    ],
    "database_accessions": {
        "CAS": [{"accession_number": "13956-29-1", "type": "CAS",
                 "source_name": "NIST Chemistry WebBook"}],
    },
    "is_released": True,
})

# Δ⁹-THC carries HTML markup in its ChEBI name — the lane must strip it so the
# isomer name is clean (Constitution §VI).
_THC_COMPOUND = json.dumps({
    "id": 66964,
    "chebi_accession": "CHEBI:66964",
    "name": "Δ<small><sup>9</small></sup>-tetrahydrocannabinol",
    "ascii_name": "Delta(9)-tetrahydrocannabinol",
    "stars": 3,
    "definition": "A <stereo>tetrahydrocannabinol</stereo> that is the principal psychoactive constituent of <em>Cannabis sativa</em>.",
    "secondary_ids": [],
    "chemical_data": {"formula": "C21H30O2", "charge": 0, "mass": "314.469"},
    "compound_origins": [{"species_text": "Cannabis sativa", "component_text": "plant"}],
    "roles_classification": [
        {"chebi_accession": "CHEBI:48561", "name": "psychotropic drug",
         "biological_role": True},
    ],
    "database_accessions": {},
    "is_released": True,
})

_EMPTY_SEARCH = json.dumps({"results": [], "total": 0, "number_pages": 0})


class HappyPathTests(unittest.TestCase):
    def test_cbd_name_resolves_to_row(self) -> None:
        fetcher = _StubFetcher({
            "es_search": _CBD_SEARCH,
            "compound/CHEBI:69478/": _CBD_COMPOUND,
        })
        rows = ChEBISearcher(fetcher=fetcher).search("cannabidiol", max_results=1)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.chebi_id, "CHEBI:69478")
        self.assertEqual(r.chebi_name, "cannabidiol")
        self.assertEqual(r.formula, "C21H30O2")
        self.assertEqual(r.mass, 314.469)
        self.assertTrue(r.cannabis_origin)
        self.assertIn("Cannabis sativa", r.origin_species)
        self.assertIn("antimicrobial agent", r.roles)
        # The duplicated role collapses to a single entry.
        self.assertEqual(
            r.roles.count("cannabinoid receptor agonist"), 1
        )
        self.assertEqual(r.source, Provenance.LIVE_CHEBI)
        self.assertIn("live_chebi", r.suggested_grade)
        self.assertIn("provisional", r.suggested_grade)
        self.assertIn("13956-29-1", " ".join(r.xrefs))

    def test_direct_accession_skips_search_and_strips_html(self) -> None:
        fetcher = _StubFetcher({"compound/CHEBI:66964/": _THC_COMPOUND})
        rows = ChEBISearcher(fetcher=fetcher).search("CHEBI:66964")
        self.assertEqual(len(rows), 1)
        # HTML markup stripped from the isomer name.
        self.assertEqual(rows[0].chebi_name, "Δ9-tetrahydrocannabinol")
        self.assertIn("psychotropic drug", rows[0].roles)
        # HTML markup is also stripped from the definition (ChEBI ships
        # <stereo>/<em>/entity markup in definitions).
        self.assertNotIn("<", rows[0].definition)
        self.assertIn("Cannabis sativa", rows[0].definition)
        for url in fetcher.calls:
            self.assertNotIn("es_search", url)


class EmptyResultTests(unittest.TestCase):
    def test_unknown_name_returns_empty_list(self) -> None:
        fetcher = _StubFetcher({"es_search": _EMPTY_SEARCH})
        self.assertEqual(ChEBISearcher(fetcher=fetcher).search("Phlogiston"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise AssertionError("preflight failed to refuse — fetched anyway!")
        with self.assertRaises(DiscoverRefused):
            ChEBISearcher(fetcher=angry_fetcher).search(
                "how to synthesize K2 Spice JWH-018 at home"
            )


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            ChEBISearcher(fetcher=_StubFetcher({})).search("")

    def test_max_results_ceiling_enforced(self) -> None:
        with self.assertRaises(ValueError):
            ChEBISearcher(fetcher=_StubFetcher({})).search("CBD", max_results=999)

    def test_max_results_minimum_enforced(self) -> None:
        with self.assertRaises(ValueError):
            ChEBISearcher(fetcher=_StubFetcher({})).search("CBD", max_results=0)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")
        with self.assertRaises(NetworkError):
            ChEBISearcher(fetcher=angry_fetcher).search("CBD")

    def test_html_body_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({"es_search": "<html>500</html>"})
        with self.assertRaises(NetworkError):
            ChEBISearcher(fetcher=fetcher).search("CBD")


class RenderingTests(unittest.TestCase):
    def _row(self) -> ChEBICompoundRow:
        return ChEBICompoundRow(
            chebi_id="CHEBI:69478", name_query="CBD", chebi_name="cannabidiol",
            definition="A cannabinoid.", stars=3, formula="C21H30O2",
            mass=314.469, charge=0,
            roles=("antimicrobial agent", "cannabinoid receptor agonist"),
            cannabis_origin=True, origin_species=("Cannabis sativa",),
            secondary_ids=("CHEBI:3358",), xrefs=("CAS:13956-29-1",),
        )

    def test_markdown_includes_live_chebi_header(self) -> None:
        md = render_markdown("CBD", [self._row()])
        self.assertIn("live_chebi, provisional", md)
        self.assertIn("CHEBI:69478", md)
        self.assertIn("Cannabis sativa", md)

    def test_markdown_empty_rows_has_friendly_note(self) -> None:
        self.assertIn("No ChEBI", render_markdown("Phlogiston", []))

    def test_json_round_trip(self) -> None:
        payload = json.loads(render_json("CBD", [self._row()]))
        self.assertEqual(payload["provenance"], "live_chebi")
        self.assertEqual(payload["hits"][0]["chebi_id"], "CHEBI:69478")
        self.assertEqual(payload["hits"][0]["source"], "live_chebi")


if __name__ == "__main__":
    unittest.main()
