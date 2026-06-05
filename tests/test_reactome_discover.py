"""Tests for cannavec_science.reactome_discover.

Spec 030 P1. Injected fetcher; fixtures captured verbatim from the live
Reactome ContentService (``mapping/UniProt/P21554/pathways`` for CB1 and the
``data/query/<stId>`` pathway-detail responses), no real network. A pathway
that carries a literature PMID sorts ahead of one that does not (§I).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.reactome_discover import (  # noqa: E402
    NetworkError,
    ReactomePathwayRow,
    ReactomeSearcher,
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


# ── Fixtures faithful to the real Reactome responses for CB1 (P21554) ──────

_CB1_PATHWAYS = json.dumps([
    {"dbId": 373076, "displayName": "Class A/1 (Rhodopsin-like receptors)",
     "stId": "R-HSA-373076", "stIdVersion": "R-HSA-373076.10",
     "isInDisease": False, "isInferred": False, "speciesName": "Homo sapiens",
     "schemaClass": "Pathway", "name": ["Class A/1 (Rhodopsin-like receptors)"]},
    {"dbId": 418594, "displayName": "G alpha (i) signalling events",
     "stId": "R-HSA-418594", "stIdVersion": "R-HSA-418594.2",
     "isInDisease": False, "isInferred": False, "speciesName": "Homo sapiens",
     "schemaClass": "Pathway", "name": ["G alpha (i) signalling events"]},
])

# Has two literature references → sorts first.
_DETAIL_418594 = json.dumps({
    "stId": "R-HSA-418594",
    "displayName": "G alpha (i) signalling events",
    "isInDisease": False,
    "summation": [{"text": (
        "The classical signalling mechanism for G alpha (i) is inhibition of "
        "the cAMP dependent pathway through inhibition of adenylate cyclase."
    )}],
    "literatureReference": [
        {"pubMedIdentifier": 9278091, "title": "Role of subunit diversity in "
         "signaling by heterotrimeric G proteins", "journal": "Biochem Pharmacol",
         "year": 1997},
        {"pubMedIdentifier": 3113327, "title": "G proteins: transducers of "
         "receptor-generated signals", "journal": "Nature", "year": 1987},
    ],
})

# No literature reference → sorts after, but still emitted.
_DETAIL_373076 = json.dumps({
    "stId": "R-HSA-373076",
    "displayName": "Class A/1 (Rhodopsin-like receptors)",
    "isInDisease": False,
    "summation": [{"text": "GPCRs of the rhodopsin-like class A/1 family."}],
    "literatureReference": [],
})

_EMPTY_PATHWAYS = json.dumps([])


class HappyPathTests(unittest.TestCase):
    def _searcher(self) -> ReactomeSearcher:
        return ReactomeSearcher(fetcher=_StubFetcher({
            "mapping/UniProt/P21554/pathways": _CB1_PATHWAYS,
            "query/R-HSA-418594": _DETAIL_418594,
            "query/R-HSA-373076": _DETAIL_373076,
        }))

    def test_cb1_maps_and_returns_pathways(self) -> None:
        rows = self._searcher().search("CB1", max_results=5)
        self.assertEqual(len(rows), 2)
        ids = {r.pathway_id for r in rows}
        self.assertEqual(ids, {"R-HSA-418594", "R-HSA-373076"})
        for r in rows:
            self.assertEqual(r.uniprot, "P21554")
            self.assertEqual(r.source, Provenance.LIVE_REACTOME)
            self.assertIn("live_reactome", r.suggested_grade)

    def test_referenced_pathway_leads_and_carries_pmid(self) -> None:
        rows = self._searcher().search("CB1", max_results=5)
        # §I — the pathway with a literature PMID sorts first and exposes it.
        self.assertEqual(rows[0].pathway_id, "R-HSA-418594")
        self.assertIn("9278091", rows[0].pmids)
        self.assertEqual(rows[0].pmid, "9278091")
        self.assertIn("adenylate cyclase", rows[0].summary)

    def test_uniprot_accession_input_used_directly(self) -> None:
        s = self._searcher()
        s.search("P21554")
        self.assertTrue(
            any("mapping/UniProt/P21554/" in c for c in s._fetcher.calls)
        )

    def test_max_results_caps(self) -> None:
        self.assertEqual(len(self._searcher().search("CB1", max_results=1)), 1)


class MappingTests(unittest.TestCase):
    def test_unknown_receptor_refuses(self) -> None:
        with self.assertRaises(ValueError):
            ReactomeSearcher(fetcher=_StubFetcher({})).search("flubberistan")

    def test_no_pathways_returns_empty(self) -> None:
        s = ReactomeSearcher(fetcher=_StubFetcher({
            "mapping/UniProt/Q9Y2T6/pathways": _EMPTY_PATHWAYS,
        }))
        self.assertEqual(s.search("GPR55"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise AssertionError("preflight failed to refuse — fetched anyway!")
        with self.assertRaises(DiscoverRefused):
            ReactomeSearcher(fetcher=angry_fetcher).search(
                "how to synthesize K2 Spice JWH-018 at home"
            )


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            ReactomeSearcher(fetcher=_StubFetcher({})).search("")

    def test_max_results_ceiling(self) -> None:
        with self.assertRaises(ValueError):
            ReactomeSearcher(fetcher=_StubFetcher({})).search("CB1", max_results=999)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")
        with self.assertRaises(NetworkError):
            ReactomeSearcher(fetcher=angry_fetcher).search("CB1")

    def test_html_body_surfaces_network_error(self) -> None:
        s = ReactomeSearcher(fetcher=_StubFetcher({
            "mapping/UniProt/P21554/pathways": "<html>500</html>",
        }))
        with self.assertRaises(NetworkError):
            s.search("CB1")


class BestEffortDetailTests(unittest.TestCase):
    """Mapping succeeds but the per-pathway detail fetch fails — the pathway
    must still emit (with its mapping-level name + id), not vanish."""

    def test_detail_failure_does_not_lose_pathway(self) -> None:
        def selective(url: str) -> str:
            if "mapping/UniProt" in url:
                return _CB1_PATHWAYS
            raise OSError("detail unavailable")  # every query/<stId> fails

        rows = ReactomeSearcher(fetcher=selective).search("CB1", max_results=5)
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertIsNone(r.summary)
            self.assertEqual(r.pmids, ())
            self.assertEqual(r.pmid, "")


class RenderingTests(unittest.TestCase):
    def _row(self) -> ReactomePathwayRow:
        return ReactomePathwayRow(
            pathway_id="R-HSA-418594", receptor_query="CB1", uniprot="P21554",
            display_name="G alpha (i) signalling events", is_disease=False,
            summary="The classical signalling mechanism for G alpha (i).",
            pmids=("9278091", "3113327"), species="Homo sapiens",
        )

    def test_markdown_includes_live_reactome_header(self) -> None:
        md = render_markdown("CB1", [self._row()])
        self.assertIn("live_reactome, provisional", md)
        self.assertIn("R-HSA-418594", md)
        self.assertIn("G alpha (i) signalling events", md)

    def test_markdown_empty_rows_has_friendly_note(self) -> None:
        self.assertIn("No Reactome", render_markdown("CB1", []))

    def test_json_round_trip(self) -> None:
        payload = json.loads(render_json("CB1", [self._row()]))
        self.assertEqual(payload["provenance"], "live_reactome")
        self.assertEqual(payload["hits"][0]["pathway_id"], "R-HSA-418594")
        self.assertEqual(payload["hits"][0]["source"], "live_reactome")
        self.assertEqual(payload["hits"][0]["pmid"], "9278091")


if __name__ == "__main__":
    unittest.main()
