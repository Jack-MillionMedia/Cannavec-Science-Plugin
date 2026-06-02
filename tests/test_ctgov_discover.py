"""Tests for cannavec.ctgov_discover (spec 002 US2).

ClinicalTrials.gov v2 live discovery surface — trial search by
condition/intervention/status, investigator search, side-by-side
endpoint comparison. Mirrors cannavec.pubmed_search test pattern.

elite-expert-engine-002 US2
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.ctgov_discover import (  # noqa: E402
    CTGovSearcher,
    CTGovTrialRow,
    NetworkError,
    render_endpoint_comparison,
    render_json,
    render_markdown,
)
from cannavec_science.discover_guard import DiscoverRefused, Provenance  # noqa: E402


# ── Fetcher stub ─────────────────────────────────────────────────────────


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
            f"Unexpected fetcher call: {url!r}. Known needles: {list(self._url_map)}"
        )


# ── Fixtures ─────────────────────────────────────────────────────────────


def _study_payload(
    nct: str = "NCT05123456",
    status: str = "RECRUITING",
    phase: str = "PHASE3",
    pi: str = "Smith, John",
    condition: str = "PTSD",
    intervention: str = "Cannabidiol",
    sites: tuple[str, ...] = ("United States",),
    start: str = "2025-04-01",
    enrolment: int = 240,
    endpoint: str = "CAPS-5 score at 12 weeks",
) -> dict:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct,
                "briefTitle": f"A {phase} study of {intervention} in {condition}",
                "officialTitle": f"Official: {nct}",
            },
            "statusModule": {
                "overallStatus": status,
                "startDateStruct": {"date": start},
            },
            "designModule": {
                "phases": [phase],
                "enrollmentInfo": {"count": enrolment},
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "ABC Pharma"},
                "responsibleParty": {
                    "investigatorFullName": pi,
                },
            },
            "conditionsModule": {"conditions": [condition]},
            "armsInterventionsModule": {
                "interventions": [{"name": intervention, "type": "DRUG"}],
            },
            "outcomesModule": {
                "primaryOutcomes": [{"measure": endpoint, "timeFrame": "12 weeks"}],
            },
            "contactsLocationsModule": {
                "locations": [
                    {"country": s, "city": "Somewhere", "state": "CA"} for s in sites
                ],
            },
        }
    }


def _search_fixture(studies: list[dict]) -> str:
    return json.dumps({"studies": studies, "totalCount": len(studies)})


def _detail_fixture(study: dict) -> str:
    return json.dumps(study)


# ── Tests ─────────────────────────────────────────────────────────────────


class HappyPathTests(unittest.TestCase):
    def test_search_returns_trial_rows(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD cannabinoid")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.source, Provenance.LIVE_CTGOV)
        self.assertEqual(r.nct_id, "NCT05123456")
        self.assertEqual(r.status, "RECRUITING")
        self.assertEqual(r.phase, "PHASE3")
        self.assertEqual(r.sponsor, "ABC Pharma")
        self.assertEqual(r.pi_name, "Smith, John")
        self.assertIn("PTSD", r.condition)
        self.assertIn("Cannabidiol", r.intervention)
        self.assertEqual(r.enrollment_count, 240)
        self.assertEqual(r.primary_endpoints, ("CAPS-5 score at 12 weeks",))


class SafetyGateTests(unittest.TestCase):
    def test_banned_pattern_short_circuit_no_network(self) -> None:
        fetcher = _StubFetcher({})
        s = CTGovSearcher(fetcher=fetcher)
        with self.assertRaises(DiscoverRefused) as ctx:
            s.search("indica cures cancer")
        self.assertTrue(ctx.exception.reason.startswith("banned:"))
        self.assertEqual(len(fetcher.calls), 0)

    def test_safety_refusal_short_circuit_no_network(self) -> None:
        fetcher = _StubFetcher({})
        s = CTGovSearcher(fetcher=fetcher)
        with self.assertRaises(DiscoverRefused):
            s.search("How do I synthesize K2 / Spice?")
        self.assertEqual(len(fetcher.calls), 0)

    def test_search_investigator_runs_preflight(self) -> None:
        fetcher = _StubFetcher({})
        s = CTGovSearcher(fetcher=fetcher)
        with self.assertRaises(DiscoverRefused):
            s.search_investigator("OG Kush is good for pain")
        self.assertEqual(len(fetcher.calls), 0)


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises(self) -> None:
        s = CTGovSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")

    def test_max_results_ceiling(self) -> None:
        s = CTGovSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=51)

    def test_max_results_zero_invalid(self) -> None:
        s = CTGovSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=0)

    def test_invalid_since_date(self) -> None:
        s = CTGovSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", since="not-a-date")

    def test_compare_endpoints_invalid_nct(self) -> None:
        s = CTGovSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.compare_endpoints("NCT05123456", "NOT-A-NCT")


class FilterTests(unittest.TestCase):
    def test_status_filter_passed_to_query_string(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        s.search("PTSD", status="RECRUITING")
        # Look for the status filter on the URL.
        url = fetcher.calls[0]
        self.assertIn("RECRUITING", url)

    def test_since_filter_passed_to_query_string(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        s.search("PTSD", since="2024-01-01")
        url = fetcher.calls[0]
        self.assertIn("2024-01-01", url)


class ShapeTests(unittest.TestCase):
    def test_max_results_cap_honoured(self) -> None:
        studies = [
            _study_payload(nct=f"NCT0512345{i}", phase="PHASE3")
            for i in range(20)
        ]
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture(studies),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD", max_results=5)
        self.assertEqual(len(rows), 5)

    def test_empty_results_returns_empty_list(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("NonexistentCondition")
        self.assertEqual(rows, [])


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")

        s = CTGovSearcher(fetcher=angry_fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")

    def test_json_parse_failure_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": "<html>error</html>",
        })
        s = CTGovSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")


class SortOrderTests(unittest.TestCase):
    def test_recruiting_sorted_before_completed(self) -> None:
        studies = [
            _study_payload(nct="NCT05111111", status="COMPLETED", start="2023-01-01"),
            _study_payload(nct="NCT05222222", status="RECRUITING", start="2024-01-01"),
            _study_payload(nct="NCT05333333", status="ACTIVE_NOT_RECRUITING", start="2024-06-01"),
        ]
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture(studies),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        statuses = [r.status for r in rows]
        self.assertEqual(statuses[0], "RECRUITING")
        self.assertEqual(statuses[-1], "COMPLETED")

    def test_within_same_status_newest_first(self) -> None:
        studies = [
            _study_payload(nct="NCT05111111", status="RECRUITING", start="2022-01-01"),
            _study_payload(nct="NCT05222222", status="RECRUITING", start="2024-01-01"),
            _study_payload(nct="NCT05333333", status="RECRUITING", start="2023-01-01"),
        ]
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture(studies),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        dates = [r.start_date for r in rows]
        self.assertEqual(dates, sorted(dates, reverse=True))


class ProvenanceTests(unittest.TestCase):
    def test_every_row_carries_live_ctgov_provenance(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        for r in rows:
            self.assertEqual(r.source, Provenance.LIVE_CTGOV)

    def test_suggested_grade_carries_live_ctgov_suffix(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        for r in rows:
            self.assertIn("live_ctgov", r.suggested_grade)


class DefensiveParsingTests(unittest.TestCase):
    def test_missing_pi_does_not_break(self) -> None:
        study = _study_payload()
        del study["protocolSection"]["sponsorCollaboratorsModule"]["responsibleParty"]
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([study]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].pi_name)

    def test_missing_enrolment_handled(self) -> None:
        study = _study_payload()
        del study["protocolSection"]["designModule"]["enrollmentInfo"]
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([study]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        self.assertIsNone(rows[0].enrollment_count)


class InvestigatorSearchTests(unittest.TestCase):
    def test_substring_match_case_insensitive(self) -> None:
        studies = [
            _study_payload(nct="NCT05111111", pi="Smith, John"),
            _study_payload(nct="NCT05222222", pi="Jones, Sarah"),
            _study_payload(nct="NCT05333333", pi="Smithson, Alex"),
        ]
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture(studies),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search_investigator("smith")
        # "smith" appears in "Smith, John" and "Smithson, Alex".
        self.assertEqual(len(rows), 2)
        ncts = {r.nct_id for r in rows}
        self.assertIn("NCT05111111", ncts)
        self.assertIn("NCT05333333", ncts)


class EndpointComparisonTests(unittest.TestCase):
    def test_compare_endpoints_returns_side_by_side(self) -> None:
        study_a = _study_payload(
            nct="NCT05111111",
            endpoint="CAPS-5 score at 12 weeks",
        )
        study_b = _study_payload(
            nct="NCT05222222",
            endpoint="CAPS-5 score at 8 weeks",
        )
        # Add a second endpoint to study A so we have a divergent.
        study_a["protocolSection"]["outcomesModule"]["primaryOutcomes"].append({
            "measure": "PHQ-9 at 12 weeks", "timeFrame": "12 weeks"
        })
        fetcher = _StubFetcher({
            "/api/v2/studies/NCT05111111": _detail_fixture(study_a),
            "/api/v2/studies/NCT05222222": _detail_fixture(study_b),
        })
        s = CTGovSearcher(fetcher=fetcher)
        payload = s.compare_endpoints("NCT05111111", "NCT05222222")
        self.assertEqual(payload["nct_a"]["nct"], "NCT05111111")
        self.assertEqual(payload["nct_b"]["nct"], "NCT05222222")
        self.assertEqual(len(payload["nct_a"]["endpoints"]), 2)
        self.assertEqual(len(payload["nct_b"]["endpoints"]), 1)
        # PHQ-9 is in A but not B → divergent.
        self.assertIn("PHQ-9 at 12 weeks", payload["divergent_endpoints"])

    def test_compare_endpoints_renderer_produces_markdown_table(self) -> None:
        payload = {
            "nct_a": {"nct": "NCT01", "endpoints": ["E1", "E2"], "phase": "PHASE3"},
            "nct_b": {"nct": "NCT02", "endpoints": ["E1"], "phase": "PHASE2"},
            "shared_endpoints": ["E1"],
            "divergent_endpoints": ["E2"],
        }
        out = render_endpoint_comparison(payload)
        self.assertIn("NCT01", out)
        self.assertIn("NCT02", out)
        self.assertIn("E1", out)
        self.assertIn("E2", out)


class DataclassTests(unittest.TestCase):
    def test_to_dict_round_trips(self) -> None:
        row = CTGovTrialRow(
            nct_id="NCT05123456",
            status="RECRUITING",
            phase="PHASE3",
            sponsor="ABC Pharma",
            pi_name="Smith, John",
            condition=("PTSD",),
            intervention=("Cannabidiol",),
            primary_endpoints=("CAPS-5",),
            enrollment_count=240,
            site_jurisdictions=("United States",),
            start_date="2025-04-01",
            suggested_grade="Level B (provisional, live_ctgov)",
        )
        d = row.to_dict()
        self.assertEqual(d["nct_id"], "NCT05123456")
        self.assertEqual(d["source"], "live_ctgov")
        self.assertEqual(d["enrollment_count"], 240)


class RendererTests(unittest.TestCase):
    def test_render_markdown_includes_safe_url(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        out = render_markdown("PTSD", rows)
        self.assertIn("ClinicalTrials.gov", out)
        self.assertIn("live_ctgov", out)
        self.assertIn("NCT05123456", out)
        self.assertIn("clinicaltrials.gov/study/NCT05123456", out)

    def test_render_json_shape(self) -> None:
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([_study_payload()]),
        })
        s = CTGovSearcher(fetcher=fetcher)
        rows = s.search("PTSD")
        payload = json.loads(render_json("PTSD", rows))
        self.assertEqual(payload["query"], "PTSD")
        self.assertEqual(payload["provenance"], "live_ctgov")
        self.assertEqual(len(payload["hits"]), 1)
        self.assertEqual(payload["hits"][0]["nct_id"], "NCT05123456")

    def test_empty_results_renderer(self) -> None:
        out = render_markdown("X", [])
        self.assertIn("no", out.lower())


class FetcherInjectionTests(unittest.TestCase):
    def test_default_fetcher_attribute_present(self) -> None:
        from cannavec_science.ctgov_discover import default_ctgov_fetcher
        self.assertTrue(callable(default_ctgov_fetcher))


class CannabisRelevanceFilterTests(unittest.TestCase):
    """Spec 029 — the CT.gov lane must not surface trials that match a broad
    free-text query but have nothing to do with cannabinoids."""

    def _mixed_fetcher(self) -> "_StubFetcher":
        return _StubFetcher({
            "/api/v2/studies?": _search_fixture([
                _study_payload(
                    nct="NCT0CANN", intervention="Cannabidiol",
                    condition="Metabolic Syndrome",
                ),
                _study_payload(
                    nct="NCT0HCV", intervention="Boceprevir",
                    condition="HCV Coinfection",
                ),
            ]),
        })

    def test_default_keeps_all_trials(self) -> None:
        rows = CTGovSearcher(fetcher=self._mixed_fetcher()).search(
            "metabolic syndrome"
        )
        self.assertEqual({r.nct_id for r in rows}, {"NCT0CANN", "NCT0HCV"})

    def test_cannabis_only_drops_unrelated_trial(self) -> None:
        rows = CTGovSearcher(fetcher=self._mixed_fetcher()).search(
            "cannabis insulin metabolic syndrome", cannabis_relevant_only=True
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].nct_id, "NCT0CANN")
        self.assertIn("Cannabidiol", rows[0].intervention)

    def test_cannabis_only_constrains_intervention_field(self) -> None:
        # Recall fix: the cannabinoid constraint goes into CT.gov's
        # intervention field, and the term is the cannabis-stripped topic.
        from urllib.parse import urlsplit, parse_qs
        fetcher = _StubFetcher({
            "/api/v2/studies?": _search_fixture([
                _study_payload(nct="NCT0CANN", intervention="Cannabidiol",
                               condition="Metabolic Syndrome"),
            ]),
        })
        CTGovSearcher(fetcher=fetcher).search(
            "cannabis insulin metabolic syndrome", cannabis_relevant_only=True
        )
        qs = parse_qs(urlsplit(fetcher.calls[0]).query)
        self.assertIn("query.intr", qs)
        self.assertIn("cannabidiol", " ".join(qs["query.intr"]).lower())
        # "cannabis" was stripped out of the topic term.
        self.assertNotIn("cannabis", " ".join(qs.get("query.term", [""])).lower())
        self.assertIn("insulin", " ".join(qs.get("query.term", [""])).lower())

    def test_relevance_helper(self) -> None:
        from cannavec_science.ctgov_discover import _trial_is_cannabis_relevant
        cann = CTGovTrialRow(
            nct_id="NCT1", status="COMPLETED", phase="PHASE2", sponsor="x",
            pi_name=None, intervention=("THC oral solution",),
            condition=("Chronic pain",),
        )
        non = CTGovTrialRow(
            nct_id="NCT2", status="COMPLETED", phase="PHASE2", sponsor="x",
            pi_name=None, intervention=("Boceprevir",),
            condition=("HCV",), title="Boceprevir in HCV",
        )
        self.assertTrue(_trial_is_cannabis_relevant(cann))
        self.assertFalse(_trial_is_cannabis_relevant(non))


if __name__ == "__main__":
    unittest.main()
