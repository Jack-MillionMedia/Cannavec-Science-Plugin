"""Tests for cannavec_science.efo_discover.

Spec 030 P2. Injected fetcher; fixtures captured verbatim from the live
OLS4 EFO search API (``/ols4/api/search?q=…&ontology=efo``), no real network.

EFO is an indication-*normalization* lane: it resolves a disease / phenotype
phrase to its canonical ontology term (EFO / MONDO / HP id + label + synonyms),
which a researcher uses to build a precise literature query. An ontology id is
NOT a §I primary research source, so EFO rows are capped at Level D and never
weave into an answer's citable evidence tier.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.efo_discover import (  # noqa: E402
    EFOTermRow,
    EFOSearcher,
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


# ── Fixtures faithful to the real OLS4 EFO search responses ────────────────

_NEUROPATHIC = json.dumps({
    "response": {
        "numFound": 6,
        "docs": [
            {"iri": "http://www.ebi.ac.uk/efo/EFO_0005762", "ontology_name": "efo",
             "ontology_prefix": "EFO", "short_form": "EFO_0005762",
             "description": ["Chronic pain caused by damage to nerve fibers. It "
                             "is usually associated with tissue injury."],
             "label": "neuropathic pain", "obo_id": "EFO:0005762",
             "type": "class"},
            # EFO imports MONDO terms — the obo_id prefix is the true source.
            {"iri": "http://purl.obolibrary.org/obo/HP_0100963", "ontology_name": "efo",
             "ontology_prefix": "EFO", "short_form": "HP_0100963",
             "description": ["Hyperesthesia."], "label": "Hyperesthesia",
             "obo_id": "HP:0100963", "type": "class"},
        ],
    },
})

# A term carrying synonyms (the lane must surface them).
_MS = json.dumps({
    "response": {
        "numFound": 2,
        "docs": [
            {"iri": "http://purl.obolibrary.org/obo/MONDO_0005301",
             "ontology_name": "efo", "ontology_prefix": "EFO",
             "short_form": "MONDO_0005301",
             "description": ["A progressive autoimmune disorder affecting the "
                             "central nervous system resulting in demyelination."],
             "label": "multiple sclerosis", "obo_id": "MONDO:0005301",
             "synonym": ["MS", "disseminated sclerosis"], "type": "class"},
        ],
    },
})

_EMPTY = json.dumps({"response": {"numFound": 0, "docs": []}})


class HappyPathTests(unittest.TestCase):
    def test_resolves_disease_to_term(self) -> None:
        s = EFOSearcher(fetcher=_StubFetcher({"search": _NEUROPATHIC}))
        rows = s.search("neuropathic pain", max_results=5)
        self.assertEqual(len(rows), 2)
        r = rows[0]
        self.assertEqual(r.efo_id, "EFO:0005762")
        self.assertEqual(r.label, "neuropathic pain")
        self.assertEqual(r.ontology, "EFO")
        self.assertIn("nerve fibers", r.description)
        self.assertEqual(r.source, Provenance.LIVE_EFO)
        self.assertIn("live_efo", r.suggested_grade)

    def test_obo_prefix_reflects_true_source_ontology(self) -> None:
        s = EFOSearcher(fetcher=_StubFetcher({"search": _NEUROPATHIC}))
        rows = s.search("neuropathic pain")
        # The second doc is an HP term surfaced through EFO.
        hp = [r for r in rows if r.efo_id.startswith("HP:")]
        self.assertEqual(len(hp), 1)
        self.assertEqual(hp[0].ontology, "HP")

    def test_synonyms_surfaced(self) -> None:
        s = EFOSearcher(fetcher=_StubFetcher({"search": _MS}))
        rows = s.search("multiple sclerosis")
        self.assertIn("MS", rows[0].synonyms)
        self.assertEqual(rows[0].efo_id, "MONDO:0005301")
        self.assertEqual(rows[0].ontology, "MONDO")


class EmptyResultTests(unittest.TestCase):
    def test_no_match_returns_empty(self) -> None:
        s = EFOSearcher(fetcher=_StubFetcher({"search": _EMPTY}))
        self.assertEqual(s.search("notadiseaseatall"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise AssertionError("preflight failed to refuse — fetched anyway!")
        with self.assertRaises(DiscoverRefused):
            EFOSearcher(fetcher=angry_fetcher).search(
                "how to synthesize K2 Spice JWH-018 at home"
            )


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            EFOSearcher(fetcher=_StubFetcher({})).search("   ")

    def test_max_results_ceiling(self) -> None:
        with self.assertRaises(ValueError):
            EFOSearcher(fetcher=_StubFetcher({})).search("pain", max_results=999)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")
        with self.assertRaises(NetworkError):
            EFOSearcher(fetcher=angry_fetcher).search("pain")

    def test_html_body_surfaces_network_error(self) -> None:
        s = EFOSearcher(fetcher=_StubFetcher({"search": "<html>500</html>"}))
        with self.assertRaises(NetworkError):
            s.search("pain")


class CitabilityContractTests(unittest.TestCase):
    """EFO rows are normalization, not §I primary sources — they must NOT
    weave into an answer's citable evidence tier."""

    def test_efo_row_is_not_a_live_finding(self) -> None:
        from cannavec_science.answer import live_finding_from_row
        row = EFOTermRow(
            efo_id="EFO:0005762", term_query="neuropathic pain",
            label="neuropathic pain", ontology="EFO",
            description="x", synonyms=(), iri="http://x", short_form="EFO_0005762",
        ).to_dict()
        self.assertIsNone(live_finding_from_row("efo", row))


class RenderingTests(unittest.TestCase):
    def _row(self) -> EFOTermRow:
        return EFOTermRow(
            efo_id="EFO:0005762", term_query="neuropathic pain",
            label="neuropathic pain", ontology="EFO",
            description="Chronic pain caused by damage to nerve fibers.",
            synonyms=("nerve pain",), iri="http://www.ebi.ac.uk/efo/EFO_0005762",
            short_form="EFO_0005762",
        )

    def test_markdown_includes_live_efo_header(self) -> None:
        md = render_markdown("neuropathic pain", [self._row()])
        self.assertIn("live_efo, provisional", md)
        self.assertIn("EFO:0005762", md)
        self.assertIn("normalization", md.lower())

    def test_markdown_empty_rows_has_friendly_note(self) -> None:
        self.assertIn("No EFO", render_markdown("xyz", []))

    def test_json_round_trip(self) -> None:
        payload = json.loads(render_json("neuropathic pain", [self._row()]))
        self.assertEqual(payload["provenance"], "live_efo")
        self.assertEqual(payload["hits"][0]["efo_id"], "EFO:0005762")
        self.assertEqual(payload["hits"][0]["source"], "live_efo")


if __name__ == "__main__":
    unittest.main()
