"""Tests for cannavec_science.quickgo_discover.

Spec 029 P2. Injected fetcher; fixtures captured verbatim from the live
QuickGO API (``annotation/search?geneProductId=P21554`` for CB1 and the
``ontology/go/terms`` batch resolution), no real network. The annotation
endpoint returns ``goName: null`` — the lane must batch-resolve names from
the terms endpoint, and surface experimental (PMID-referenced) annotations
ahead of electronic (GO_REF) ones.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.quickgo_discover import (  # noqa: E402
    NetworkError,
    QuickGOAnnotationRow,
    QuickGOSearcher,
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


# ── Fixtures: faithful to the real QuickGO responses for CB1 (P21554) ──────

_CB1_ANNOTATIONS = json.dumps({
    "numberOfHits": 45,
    "results": [
        {"id": "UniProtKB:P21554!1", "geneProductId": "UniProtKB:P21554",
         "qualifier": "enables", "goId": "GO:0004930", "goName": None,
         "goEvidence": "IEA", "goAspect": "molecular_function",
         "evidenceCode": "ECO:0000256", "reference": "GO_REF:0000002",
         "taxonId": 9606, "symbol": "CNR1"},
        {"id": "UniProtKB:P21554!2", "geneProductId": "UniProtKB:P21554",
         "qualifier": "enables", "goId": "GO:0004930", "goName": None,
         "goEvidence": "IBA", "goAspect": "molecular_function",
         "evidenceCode": "ECO:0000318", "reference": "GO_REF:0000033",
         "taxonId": 9606, "symbol": "CNR1"},
        {"id": "UniProtKB:P21554!3", "geneProductId": "UniProtKB:P21554",
         "qualifier": "enables", "goId": "GO:0004949", "goName": None,
         "goEvidence": "IEA", "goAspect": "molecular_function",
         "evidenceCode": "ECO:0000501", "reference": "GO_REF:0000120",
         "taxonId": 9606, "symbol": "CNR1"},
        {"id": "UniProtKB:P21554!4", "geneProductId": "UniProtKB:P21554",
         "qualifier": "enables", "goId": "GO:0004949", "goName": None,
         "goEvidence": "TAS", "goAspect": "molecular_function",
         "evidenceCode": "ECO:0000304", "reference": "PMID:1718258",
         "taxonId": 9606, "symbol": "CNR1"},
        {"id": "UniProtKB:P21554!5", "geneProductId": "UniProtKB:P21554",
         "qualifier": "enables", "goId": "GO:0004949", "goName": None,
         "goEvidence": "IDA", "goAspect": "molecular_function",
         "evidenceCode": "ECO:0000314", "reference": "PMID:18761332",
         "taxonId": 9606, "symbol": "CNR1"},
    ],
    "pageInfo": {"resultsPerPage": 25, "current": 1, "total": 2},
})

_GO_TERMS = json.dumps({
    "numberOfHits": 2,
    "results": [
        {"id": "GO:0004930", "isObsolete": False,
         "name": "G protein-coupled receptor activity",
         "aspect": "molecular_function"},
        {"id": "GO:0004949", "isObsolete": False,
         "name": "cannabinoid receptor activity",
         "aspect": "molecular_function"},
    ],
})

_NO_ANNOTATIONS = json.dumps({"numberOfHits": 0, "results": [], "pageInfo": {}})

_GO_RE = re.compile(r"^GO:\d{7}$")


class HappyPathTests(unittest.TestCase):
    def _searcher(self) -> QuickGOSearcher:
        return QuickGOSearcher(fetcher=_StubFetcher({
            "annotation/search": _CB1_ANNOTATIONS,
            "ontology/go/terms": _GO_TERMS,
        }))

    def test_cb1_name_maps_and_returns_annotations(self) -> None:
        rows = self._searcher().search("CB1", max_results=5)
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertTrue(_GO_RE.match(r.go_id))
            self.assertEqual(r.uniprot, "P21554")
            self.assertEqual(r.source, Provenance.LIVE_QUICKGO)
            self.assertIn("live_quickgo", r.suggested_grade)
        # goName resolved from the terms batch (the annotations carry null).
        names = {r.go_name for r in rows}
        self.assertIn("cannabinoid receptor activity", names)

    def test_primary_source_referenced_annotations_lead(self) -> None:
        rows = self._searcher().search("CB1", max_results=5)
        # §I — experimental (PMID-referenced) annotations sort ahead of the
        # electronic GO_REF ones, and their PMID rides the row for §VIII.
        self.assertTrue(rows[0].reference.startswith("PMID:"))
        self.assertTrue(rows[0].pmid)
        self.assertEqual(rows[0].pmid, rows[0].reference.split(":", 1)[1])

    def test_uniprot_accession_input_is_used_directly(self) -> None:
        s = self._searcher()
        s.search("P21554")
        self.assertTrue(
            any("geneProductId=P21554" in c for c in s._fetcher.calls)
        )

    def test_max_results_caps_rows(self) -> None:
        rows = self._searcher().search("CB1", max_results=2)
        self.assertEqual(len(rows), 2)


class MappingTests(unittest.TestCase):
    def test_unknown_receptor_refuses(self) -> None:
        s = QuickGOSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("flubberistan")

    def test_cb2_maps_to_p34972(self) -> None:
        s = QuickGOSearcher(fetcher=_StubFetcher({
            "annotation/search": _NO_ANNOTATIONS,
        }))
        s.search("CB2")
        self.assertTrue(
            any("geneProductId=P34972" in c for c in s._fetcher.calls)
        )

    def test_no_annotations_returns_empty(self) -> None:
        s = QuickGOSearcher(fetcher=_StubFetcher({
            "annotation/search": _NO_ANNOTATIONS,
        }))
        self.assertEqual(s.search("GPR55"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise AssertionError("preflight failed to refuse — fetched anyway!")
        with self.assertRaises(DiscoverRefused):
            QuickGOSearcher(fetcher=angry_fetcher).search(
                "how to synthesize K2 Spice JWH-018 at home"
            )


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            QuickGOSearcher(fetcher=_StubFetcher({})).search("  ")

    def test_max_results_ceiling_enforced(self) -> None:
        with self.assertRaises(ValueError):
            QuickGOSearcher(fetcher=_StubFetcher({})).search("CB1", max_results=999)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")
        with self.assertRaises(NetworkError):
            QuickGOSearcher(fetcher=angry_fetcher).search("CB1")

    def test_html_body_surfaces_network_error(self) -> None:
        s = QuickGOSearcher(fetcher=_StubFetcher({
            "annotation/search": "<html>500</html>",
        }))
        with self.assertRaises(NetworkError):
            s.search("CB1")


class RenderingTests(unittest.TestCase):
    def _row(self) -> QuickGOAnnotationRow:
        return QuickGOAnnotationRow(
            go_id="GO:0004949", receptor_query="CB1", uniprot="P21554",
            go_name="cannabinoid receptor activity",
            go_aspect="molecular_function", evidence="IDA",
            evidence_code="ECO:0000314", reference="PMID:18761332",
            qualifier="enables", symbol="CNR1",
        )

    def test_markdown_includes_live_quickgo_header(self) -> None:
        md = render_markdown("CB1", [self._row()])
        self.assertIn("live_quickgo, provisional", md)
        self.assertIn("GO:0004949", md)
        self.assertIn("cannabinoid receptor activity", md)

    def test_markdown_empty_rows_has_friendly_note(self) -> None:
        self.assertIn("No QuickGO", render_markdown("CB1", []))

    def test_json_round_trip(self) -> None:
        payload = json.loads(render_json("CB1", [self._row()]))
        self.assertEqual(payload["provenance"], "live_quickgo")
        self.assertEqual(payload["hits"][0]["go_id"], "GO:0004949")
        self.assertEqual(payload["hits"][0]["source"], "live_quickgo")
        self.assertEqual(payload["hits"][0]["pmid"], "18761332")


if __name__ == "__main__":
    unittest.main()
