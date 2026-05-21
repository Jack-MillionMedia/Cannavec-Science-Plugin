"""Tests for cannavec.chembl_discover (spec 002 US1).

ChEMBL live discovery surface — compound bioactivity, mechanism of
action, ADMET. Mirrors the cannavec.pubmed_search test pattern:
injected fetcher, fixture JSON, no real network in the test suite.

elite-expert-engine-002 US1
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.chembl_discover import (  # noqa: E402
    ChEMBLBioactivityRow,
    ChEMBLSearcher,
    NetworkError,
    render_json,
    render_markdown,
)
from cannavec_science.discover_guard import DiscoverRefused, Provenance  # noqa: E402


# ── Fetcher stub ─────────────────────────────────────────────────────────


class _StubFetcher:
    """Records every URL it was called with and returns canned strings.

    The fetcher is initialised with a ``url_map: dict[str, str]`` of
    URL substring → response body. Lookup is by *substring* so tests
    don't have to encode the full query string.
    """

    def __init__(self, url_map: dict[str, str]) -> None:
        self._url_map = url_map
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        for needle, body in self._url_map.items():
            if needle in url:
                return body
        raise AssertionError(
            f"Unexpected fetcher call: {url!r}. Known needles: {list(self._url_map)}"
        )


# ── Fixture JSON ─────────────────────────────────────────────────────────


def _molecule_search_fixture(chembl_id: str = "CHEMBL190") -> str:
    return json.dumps({
        "molecules": [
            {
                "molecule_chembl_id": chembl_id,
                "pref_name": "CANNABIDIOL",
                "molecule_properties": {
                    "alogp": 6.99,
                    "psa": 40.5,
                    "hba": 2,
                    "hbd": 2,
                    "rtb": 6,
                    "full_mwt": 314.46,
                },
            }
        ],
    })


def _molecule_detail_fixture(chembl_id: str = "CHEMBL190") -> str:
    return json.dumps({
        "molecule_chembl_id": chembl_id,
        "pref_name": "CANNABIDIOL",
        "molecule_properties": {
            "alogp": 6.99,
            "psa": 40.5,
            "full_mwt": 314.46,
        },
    })


def _activity_fixture(
    chembl_id: str = "CHEMBL190",
    rows: int = 3,
) -> str:
    """Build N synthetic bioactivity rows with descending confidence."""
    activities = []
    for i in range(rows):
        activities.append({
            "molecule_chembl_id": chembl_id,
            "target_chembl_id": f"CHEMBL21{i + 8}",
            "target_pref_name": ["Cannabinoid CB1 receptor", "Cannabinoid CB2 receptor", "GPR55"][i % 3],
            "target_components": [{"accession": ["P21554", "P34972", "Q9Y2T6"][i % 3]}],
            "assay_type": "B",
            "assay_description": f"Binding assay variant {i + 1}",
            "standard_type": "Ki",
            "standard_value": 4400.0 + i * 1000,
            "standard_units": "nM",
            "confidence_score": 9 - i,
            "document_chembl_id": f"CHEMBL_DOC_{i}",
            "src_id": 1,
            "pchembl_value": 5.5 - i * 0.3,
        })
    return json.dumps({"activities": activities})


def _mechanism_fixture(chembl_id: str = "CHEMBL190") -> str:
    return json.dumps({
        "mechanisms": [
            {
                "molecule_chembl_id": chembl_id,
                "target_chembl_id": "CHEMBL218",
                "mechanism_of_action": "Cannabinoid CB1 receptor inverse agonist",
                "action_type": "INVERSE AGONIST",
            }
        ],
    })


def _empty_molecule_fixture() -> str:
    return json.dumps({"molecules": []})


def _empty_activity_fixture() -> str:
    return json.dumps({"activities": []})


# ── Tests ─────────────────────────────────────────────────────────────────


class HappyPathTests(unittest.TestCase):
    def test_search_by_name_returns_bioactivity_rows(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD", max_results=10)
        self.assertGreaterEqual(len(rows), 3)
        for r in rows:
            self.assertIsInstance(r, ChEMBLBioactivityRow)
            self.assertEqual(r.source, Provenance.LIVE_CHEMBL)
            self.assertEqual(r.chembl_id, "CHEMBL190")
            self.assertIn(r.target_uniprot_id, {"P21554", "P34972", "Q9Y2T6"})

    def test_search_by_chembl_id_skips_synonym_lookup(self) -> None:
        fetcher = _StubFetcher({
            "molecule/CHEMBL190": _molecule_detail_fixture(),
            "activity.json?": _activity_fixture(),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CHEMBL190", max_results=10)
        self.assertGreater(len(rows), 0)
        # The synonym-search endpoint should NOT have been hit because
        # the input was already a ChEMBL ID.
        for url in fetcher.calls:
            self.assertNotIn("molecule_synonyms__synonyms__iexact", url)


class SafetyGateTests(unittest.TestCase):
    """Per FR-002: preflight runs BEFORE any network call."""

    def test_banned_pattern_short_circuit_no_network(self) -> None:
        fetcher = _StubFetcher({})  # any call would raise AssertionError
        s = ChEMBLSearcher(fetcher=fetcher)
        with self.assertRaises(DiscoverRefused) as ctx:
            s.search("indica cures cancer")
        self.assertTrue(ctx.exception.reason.startswith("banned:"))
        self.assertEqual(len(fetcher.calls), 0)

    def test_safety_refusal_short_circuit_no_network(self) -> None:
        fetcher = _StubFetcher({})
        s = ChEMBLSearcher(fetcher=fetcher)
        with self.assertRaises(DiscoverRefused) as ctx:
            s.search("How do I synthesize K2 / Spice?")
        self.assertTrue(
            ctx.exception.reason.startswith("safety:")
            or ctx.exception.reason.startswith("banned:")
        )
        self.assertEqual(len(fetcher.calls), 0)


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = ChEMBLSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")

    def test_whitespace_only_query_raises_value_error(self) -> None:
        s = ChEMBLSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("   ")

    def test_max_results_ceiling(self) -> None:
        s = ChEMBLSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=51)

    def test_max_results_minimum(self) -> None:
        s = ChEMBLSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=0)


class ResultShapeTests(unittest.TestCase):
    def test_max_results_cap_honoured(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(rows=20),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD", max_results=5)
        self.assertLessEqual(len(rows), 5)

    def test_compound_not_found_returns_empty_list(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _empty_molecule_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("NonexistentCompound42", max_results=10)
        self.assertEqual(rows, [])

    def test_compound_with_no_activity_returns_empty(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _empty_activity_fixture(),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD", max_results=10)
        self.assertEqual(rows, [])


class NetworkErrorTests(unittest.TestCase):
    """A network failure surfaces as NetworkError (not silent zero)."""

    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")

        s = ChEMBLSearcher(fetcher=angry_fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")

    def test_json_parse_failure_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": "<html>error page</html>",
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")


class SortOrderTests(unittest.TestCase):
    """Confidence-desc, then activity-asc (smaller IC50 = more potent first)."""

    def test_higher_confidence_first(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(rows=3),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD", max_results=10)
        confidences = [r.confidence_score for r in rows]
        # All non-None, sorted descending.
        non_none = [c for c in confidences if c is not None]
        self.assertEqual(non_none, sorted(non_none, reverse=True))


class ProvenanceTests(unittest.TestCase):
    def test_every_row_carries_live_chembl_provenance(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        for r in rows:
            self.assertEqual(r.source, Provenance.LIVE_CHEMBL)

    def test_suggested_grade_carries_live_chembl_suffix(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        for r in rows:
            self.assertIn("provisional", r.suggested_grade)
            self.assertIn("live_chembl", r.suggested_grade)


class UniProtIDTests(unittest.TestCase):
    def test_uniprot_id_parsed_when_present(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(rows=3),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        uniprots = {r.target_uniprot_id for r in rows if r.target_uniprot_id}
        self.assertEqual(uniprots, {"P21554", "P34972", "Q9Y2T6"})

    def test_uniprot_id_optional_when_target_components_missing(self) -> None:
        activity_no_components = json.dumps({
            "activities": [{
                "molecule_chembl_id": "CHEMBL190",
                "target_chembl_id": "CHEMBL218",
                "target_pref_name": "Cannabinoid CB1 receptor",
                "assay_type": "B",
                "assay_description": "Binding assay",
                "standard_type": "Ki",
                "standard_value": 4400.0,
                "standard_units": "nM",
                "confidence_score": 9,
            }],
        })
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": activity_no_components,
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        self.assertEqual(rows[0].target_uniprot_id, None)


class DefensiveParsingTests(unittest.TestCase):
    def test_activity_with_missing_standard_value_handled(self) -> None:
        activity_no_value = json.dumps({
            "activities": [{
                "molecule_chembl_id": "CHEMBL190",
                "target_chembl_id": "CHEMBL218",
                "target_pref_name": "Cannabinoid CB1 receptor",
                "assay_type": "B",
                "assay_description": "Binding assay",
                # standard_value, standard_units, standard_type all absent
            }],
        })
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": activity_no_value,
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        # Row still emitted — defensive .get() means no KeyError.
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].activity_value)
        self.assertIsNone(rows[0].activity_units)


class DataclassTests(unittest.TestCase):
    def test_to_dict_round_trips(self) -> None:
        row = ChEMBLBioactivityRow(
            chembl_id="CHEMBL190",
            target_chembl_id="CHEMBL218",
            target_name="Cannabinoid CB1 receptor",
            target_uniprot_id="P21554",
            assay_description="Binding assay",
            assay_type="B",
            activity_value=4400.0,
            activity_units="nM",
            activity_type="Ki",
            confidence_score=9,
            source_pmid=None,
            suggested_grade="Level C (provisional, live_chembl)",
            url="https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL190/",
        )
        d = row.to_dict()
        self.assertEqual(d["chembl_id"], "CHEMBL190")
        self.assertEqual(d["source"], "live_chembl")
        self.assertEqual(d["target_uniprot_id"], "P21554")

    def test_native_id_defaults_to_chembl_id(self) -> None:
        row = ChEMBLBioactivityRow(
            chembl_id="CHEMBL190",
            target_chembl_id="CHEMBL218",
            target_name="CB1",
            target_uniprot_id=None,
            assay_description="x",
            assay_type="B",
            activity_value=None,
            activity_units=None,
            activity_type=None,
            confidence_score=None,
            source_pmid=None,
            suggested_grade="Level C (provisional, live_chembl)",
        )
        self.assertEqual(row.native_id, "CHEMBL190")


class RendererTests(unittest.TestCase):
    def test_render_json_has_expected_shape(self) -> None:
        rows = [
            ChEMBLBioactivityRow(
                chembl_id="CHEMBL190",
                target_chembl_id="CHEMBL218",
                target_name="CB1",
                target_uniprot_id="P21554",
                assay_description="binding",
                assay_type="B",
                activity_value=4400.0,
                activity_units="nM",
                activity_type="Ki",
                confidence_score=9,
                source_pmid=None,
                suggested_grade="Level C (provisional, live_chembl)",
            )
        ]
        payload = json.loads(render_json("CBD", rows))
        self.assertEqual(payload["query"], "CBD")
        self.assertEqual(payload["provenance"], "live_chembl")
        self.assertEqual(len(payload["hits"]), 1)
        self.assertEqual(payload["hits"][0]["chembl_id"], "CHEMBL190")

    def test_render_markdown_includes_source_and_target(self) -> None:
        rows = [
            ChEMBLBioactivityRow(
                chembl_id="CHEMBL190",
                target_chembl_id="CHEMBL218",
                target_name="CB1",
                target_uniprot_id="P21554",
                assay_description="binding",
                assay_type="B",
                activity_value=4400.0,
                activity_units="nM",
                activity_type="Ki",
                confidence_score=9,
                source_pmid=None,
                suggested_grade="Level C (provisional, live_chembl)",
            )
        ]
        out = render_markdown("CBD", rows)
        self.assertIn("ChEMBL", out)
        self.assertIn("live_chembl", out)
        self.assertIn("CHEMBL190", out)
        self.assertIn("CB1", out)
        self.assertIn("4400", out)

    def test_render_markdown_empty_results_is_explicit(self) -> None:
        out = render_markdown("NonexistentCompound", [])
        self.assertIn("no", out.lower())

    def test_render_json_empty_results_is_valid(self) -> None:
        payload = json.loads(render_json("X", []))
        self.assertEqual(payload["hits"], [])


class FetcherInjectionTests(unittest.TestCase):
    """The fetcher Protocol is the load-bearing test seam."""

    def test_custom_fetcher_records_every_call(self) -> None:
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": _activity_fixture(rows=2),
            "mechanism.json?": _mechanism_fixture(),
        })
        s = ChEMBLSearcher(fetcher=fetcher)
        _ = s.search("CBD")
        # At least molecule.json + activity.json. Mechanism is optional.
        self.assertGreaterEqual(len(fetcher.calls), 2)
        urls_joined = " ".join(fetcher.calls)
        self.assertIn("molecule.json", urls_joined)
        self.assertIn("activity.json", urls_joined)

    def test_default_fetcher_attribute_present(self) -> None:
        from cannavec_science.chembl_discover import default_chembl_fetcher
        self.assertTrue(callable(default_chembl_fetcher))


if __name__ == "__main__":
    unittest.main()
