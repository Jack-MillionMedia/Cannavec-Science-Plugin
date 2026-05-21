"""Tests for cannavec_science.pubchem_discover.

Cannabis-primary-source widening — life-science skill layer. Mirrors
the chembl_discover test style: injected fetcher, fixture JSON, no
real network.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.pubchem_discover import (  # noqa: E402
    NetworkError,
    PubChemCompoundRow,
    PubChemSearcher,
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


_CBD_NAME_RESOLVE = json.dumps({"IdentifierList": {"CID": [644019]}})

_CBD_PROPERTIES = json.dumps({
    "PropertyTable": {
        "Properties": [{
            "CID": 644019,
            "MolecularFormula": "C21H30O2",
            "MolecularWeight": "314.46",
            "CanonicalSMILES": "CCCCCC1=CC(=C(C(=C1)O)C2CC=C(CC2C(=C)C)C)O",
            "IsomericSMILES": (
                "CCCCCc1cc(O)c([C@@H]2CC(=CC[C@H]2C(=C)C)C)c(O)c1"
            ),
            "InChI": "InChI=1S/C21H30O2/c1-5-6-7-8-15-12-18(22)20(19(13-15)23)16-11-14(2)9-10-17(16)21(3)4/h11-13,16-17,22-23H,3,5-10H2,1-2,4H3",
            "InChIKey": "QHMBSVQNZZTUGM-ZWKOTPCHSA-N",
            "IUPACName": "2-[(1R,6R)-3-methyl-6-prop-1-en-2-ylcyclohex-2-en-1-yl]-5-pentylbenzene-1,3-diol",
            "XLogP": 6.99,
            "HBondDonorCount": 2,
            "HBondAcceptorCount": 2,
        }]
    }
})

_CBD_SYNONYMS = json.dumps({
    "InformationList": {
        "Information": [{
            "CID": 644019,
            "Synonym": [
                "Cannabidiol", "CBD", "Epidiolex", "13956-29-1",
            ],
        }]
    }
})


def _empty_cids() -> str:
    return json.dumps({"IdentifierList": {"CID": []}})


class HappyPathTests(unittest.TestCase):
    def test_cbd_name_resolves_to_row(self) -> None:
        fetcher = _StubFetcher({
            "compound/name/": _CBD_NAME_RESOLVE,
            "compound/cid/644019/property/": _CBD_PROPERTIES,
            "compound/cid/644019/synonyms/": _CBD_SYNONYMS,
        })
        s = PubChemSearcher(fetcher=fetcher)
        rows = s.search("CBD", max_results=1)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.cid, 644019)
        self.assertEqual(r.molecular_formula, "C21H30O2")
        self.assertEqual(r.inchikey, "QHMBSVQNZZTUGM-ZWKOTPCHSA-N")
        self.assertIn("Cannabidiol", r.synonyms)
        self.assertEqual(r.source, Provenance.LIVE_PUBCHEM)
        self.assertIn("live_pubchem", r.suggested_grade)
        self.assertIn("provisional", r.suggested_grade)

    def test_direct_cid_lookup_skips_name_resolve(self) -> None:
        fetcher = _StubFetcher({
            "compound/cid/644019/property/": _CBD_PROPERTIES,
            "compound/cid/644019/synonyms/": _CBD_SYNONYMS,
        })
        s = PubChemSearcher(fetcher=fetcher)
        rows = s.search("644019")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].cid, 644019)
        for url in fetcher.calls:
            self.assertNotIn("compound/name/", url)


class EmptyResultTests(unittest.TestCase):
    def test_unknown_name_returns_empty_list(self) -> None:
        fetcher = _StubFetcher({
            "compound/name/": _empty_cids(),
        })
        s = PubChemSearcher(fetcher=fetcher)
        self.assertEqual(s.search("NonexistentCompound42"), [])

    def test_cid_with_no_properties_returns_empty(self) -> None:
        fetcher = _StubFetcher({
            "compound/name/": _CBD_NAME_RESOLVE,
            "compound/cid/644019/property/": json.dumps({
                "PropertyTable": {"Properties": []}
            }),
            "compound/cid/644019/synonyms/": _CBD_SYNONYMS,
        })
        s = PubChemSearcher(fetcher=fetcher)
        self.assertEqual(s.search("CBD"), [])


class RefusalTests(unittest.TestCase):
    """Banned-pattern preflight must short-circuit BEFORE any fetch."""

    def test_banned_query_refused_before_network(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise AssertionError("preflight failed to refuse — fetched anyway!")
        s = PubChemSearcher(fetcher=angry_fetcher)
        with self.assertRaises(DiscoverRefused):
            # Synthetic-cannabinoid synthesis route — should hard-refuse
            # per Constitution §V (Safety-Layer Sovereignty).
            s.search("how to synthesize K2 Spice JWH-018 at home")


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = PubChemSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")

    def test_max_results_ceiling_enforced(self) -> None:
        s = PubChemSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=999)

    def test_max_results_minimum_enforced(self) -> None:
        s = PubChemSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=0)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")
        s = PubChemSearcher(fetcher=angry_fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")

    def test_html_body_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({
            "compound/name/": "<html>500</html>",
        })
        s = PubChemSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")


class RenderingTests(unittest.TestCase):
    def test_markdown_includes_live_pubchem_header(self) -> None:
        row = PubChemCompoundRow(
            cid=644019,
            name_query="CBD",
            iupac_name="Cannabidiol",
            molecular_formula="C21H30O2",
            molecular_weight=314.46,
            canonical_smiles=None,
            isomeric_smiles=None,
            inchi=None,
            inchikey="QHMBSVQNZZTUGM-ZWKOTPCHSA-N",
            xlogp=6.99,
            hbond_donors=2,
            hbond_acceptors=2,
            synonyms=("CBD", "Cannabidiol"),
        )
        md = render_markdown("CBD", [row])
        self.assertIn("live_pubchem, provisional", md)
        self.assertIn("CID 644019", md)
        self.assertIn("QHMBSVQNZZTUGM-ZWKOTPCHSA-N", md)

    def test_markdown_empty_rows_has_friendly_note(self) -> None:
        md = render_markdown("Phlogiston", [])
        self.assertIn("No PubChem compound", md)

    def test_json_round_trip(self) -> None:
        row = PubChemCompoundRow(
            cid=644019, name_query="CBD",
            iupac_name=None, molecular_formula=None, molecular_weight=None,
            canonical_smiles=None, isomeric_smiles=None,
            inchi=None, inchikey=None,
            xlogp=None, hbond_donors=None, hbond_acceptors=None,
            synonyms=(),
        )
        payload = json.loads(render_json("CBD", [row]))
        self.assertEqual(payload["provenance"], "live_pubchem")
        self.assertEqual(payload["hits"][0]["cid"], 644019)
        self.assertEqual(payload["hits"][0]["source"], "live_pubchem")


if __name__ == "__main__":
    unittest.main()
