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


class RealActivityShapeTests(unittest.TestCase):
    """WS3 — the live EBI /activity endpoint does NOT return confidence_score
    or target_components (those live on /assay and /target); it returns
    pchembl_value / standard_relation / target_organism / document_year /
    document_chembl_id. The parser must read the real shape and must not
    collapse ranking when confidence is absent."""

    @staticmethod
    def _real_shape_activities() -> str:
        return json.dumps({"activities": [
            {
                "molecule_chembl_id": "CHEMBL190",
                "target_chembl_id": "CHEMBL218",
                "target_pref_name": "Cannabinoid CB1 receptor",
                "target_organism": "Homo sapiens",
                "assay_type": "B",
                "assay_description": "Radioligand binding",
                "standard_type": "Ki",
                "standard_relation": "=",
                "standard_value": 100.0,
                "standard_units": "nM",
                "pchembl_value": 7.0,
                "document_chembl_id": "CHEMBL1135957",
                "document_year": 2010,
            },
            {
                "molecule_chembl_id": "CHEMBL190",
                "target_chembl_id": "CHEMBL253",
                "target_pref_name": "Cannabinoid CB2 receptor",
                "target_organism": "Homo sapiens",
                "assay_type": "B",
                "assay_description": "Radioligand binding",
                "standard_type": "Ki",
                "standard_relation": "=",
                "standard_value": 10000.0,
                "standard_units": "nM",
                "pchembl_value": 5.0,
                "document_chembl_id": "CHEMBL1135958",
                "document_year": 2011,
            },
        ]})

    def _rows(self):
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": self._real_shape_activities(),
            "mechanism.json?": _mechanism_fixture(),
        })
        return ChEMBLSearcher(fetcher=fetcher).search("CBD", max_results=10)

    def test_parses_real_shape_without_confidence_or_target_components(self):
        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].pchembl_value, 7.0)
        # confidence_score and uniprot are legitimately absent on this shape —
        # the parser must surface them as None, not explode.
        self.assertIsNone(rows[0].confidence_score)
        self.assertIsNone(rows[0].target_uniprot_id)
        self.assertEqual(rows[0].target_organism, "Homo sapiens")
        self.assertEqual(rows[0].document_year, 2010)

    def test_provenance_recovered_from_document_chembl_id(self):
        rows = self._rows()
        self.assertEqual(rows[0].document_chembl_id, "CHEMBL1135957")
        self.assertIn("CHEMBL1135957", rows[0].citation)

    def test_sort_uses_pchembl_when_confidence_absent(self):
        rows = self._rows()
        # pchembl 7.0 (CB1) sorts before 5.0 (CB2) although neither row has a
        # confidence_score — ranking no longer collapses to a single bucket.
        self.assertEqual([r.pchembl_value for r in rows], [7.0, 5.0])

    def test_sort_pchembl_beats_activity_when_they_disagree(self):
        # Adversarial: pair a HIGHER pchembl with a WORSE (higher) Ki so
        # pchembl-desc and activity-asc DISAGREE. The pchembl-primary key must
        # win — this case fails under the old confidence/activity-only sort.
        activities = json.dumps({"activities": [
            {"molecule_chembl_id": "CHEMBL190", "target_chembl_id": "CHEMBL1",
             "target_pref_name": "A", "assay_type": "B", "standard_type": "Ki",
             "standard_relation": "=", "standard_value": 10000.0,
             "standard_units": "nM", "pchembl_value": 8.0,
             "document_chembl_id": "D1"},
            {"molecule_chembl_id": "CHEMBL190", "target_chembl_id": "CHEMBL2",
             "target_pref_name": "B", "assay_type": "B", "standard_type": "Ki",
             "standard_relation": "=", "standard_value": 1.0,
             "standard_units": "nM", "pchembl_value": 5.0,
             "document_chembl_id": "D2"},
        ]})
        fetcher = _StubFetcher({
            "molecule.json?": _molecule_search_fixture(),
            "activity.json?": activities,
            "mechanism.json?": _mechanism_fixture(),
        })
        rows = ChEMBLSearcher(fetcher=fetcher).search("CBD", max_results=10)
        self.assertEqual([r.pchembl_value for r in rows], [8.0, 5.0])
        # The pchembl-8.0 row has the WORSE raw Ki (10000 nM vs 1.0 nM), so an
        # activity-asc sort would have ordered it last — proving pchembl primacy.
        self.assertEqual(rows[0].activity_value, 10000.0)


class CompoundResolutionFallbackTests(unittest.TestCase):
    """WS3 — iexact synonym search misses the bare cannabinoid tokens ChEMBL
    stores under long names (a live iexact for "THC" returns zero molecules).
    Fall back to a bounded icontains substring search rather than returning
    zero rows."""

    def test_icontains_fallback_when_iexact_empty(self):
        calls = {"iexact": 0, "icontains": 0}

        def fetcher(url: str) -> str:
            if "iexact" in url:
                calls["iexact"] += 1
                return _empty_molecule_fixture()
            if "icontains" in url:
                calls["icontains"] += 1
                return _molecule_search_fixture()
            if "activity.json?" in url:
                return _activity_fixture()
            if "mechanism.json?" in url:
                return _mechanism_fixture()
            raise AssertionError(f"unexpected url: {url!r}")

        rows = ChEMBLSearcher(fetcher=fetcher).search("THC", max_results=10)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(calls["iexact"], 1)
        self.assertEqual(calls["icontains"], 1)

    def test_returns_empty_when_iexact_and_icontains_both_miss(self):
        def fetcher(url: str) -> str:
            if "iexact" in url or "icontains" in url:
                return _empty_molecule_fixture()
            raise AssertionError(f"unexpected url: {url!r}")

        rows = ChEMBLSearcher(fetcher=fetcher).search(
            "NotACannabinoid999", max_results=10
        )
        self.assertEqual(rows, [])

    def test_ambiguous_icontains_returns_empty_not_wrong_compound(self):
        # icontains is a substring match: "THC" matches THCV / THCA / dronabinol
        # etc., so taking molecules[0] would risk surfacing the WRONG isomer's
        # bioactivity as THC's (§VI). An ambiguous fallback (>1 molecule) must
        # return no rows rather than guess.
        multi = json.dumps({"molecules": [
            {"molecule_chembl_id": "CHEMBL563",
             "pref_name": "TETRAHYDROCANNABIVARIN"},
            {"molecule_chembl_id": "CHEMBL465", "pref_name": "DRONABINOL"},
        ]})

        def fetcher(url: str) -> str:
            if "iexact" in url:
                return _empty_molecule_fixture()
            if "icontains" in url:
                return multi
            raise AssertionError(f"unexpected url: {url!r}")

        rows = ChEMBLSearcher(fetcher=fetcher).search("THC", max_results=10)
        self.assertEqual(rows, [])


class CensoringRenderTests(unittest.TestCase):
    """WS3 — a censored Ki/IC50 (standard_relation '>' / '<') must render with
    its relation so a '>10000 nM' bound is not shown as a hard 10000."""

    def _row(self, relation):
        return ChEMBLBioactivityRow(
            chembl_id="CHEMBL190",
            target_chembl_id="CHEMBL253",
            target_name="Cannabinoid CB2 receptor",
            target_uniprot_id="P34972",
            assay_description="binding",
            assay_type="B",
            activity_value=10000.0,
            activity_units="nM",
            activity_type="Ki",
            confidence_score=None,
            source_pmid=None,
            suggested_grade="Level C (provisional, live_chembl)",
            standard_relation=relation,
        )

    def test_greater_than_relation_rendered_as_operator(self):
        out = render_markdown("THC", [self._row(">")])
        # Censored bound renders "Ki > 10000 nM", never a hard "Ki = 10000 nM".
        self.assertIn("> 10000 nM", out)
        self.assertNotIn("= 10000 nM", out)

    def test_equality_relation_uses_plain_separator(self):
        out = render_markdown("CBD", [self._row("=")])
        self.assertIn("Ki = 10000 nM", out)
        # No doubled / censoring operator for a plain equality.
        self.assertNotIn("> 10000", out)
        self.assertNotIn("= = ", out)


if __name__ == "__main__":
    unittest.main()
