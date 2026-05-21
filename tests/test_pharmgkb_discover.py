"""Tests for cannavec_science.pharmgkb_discover.

Cannabis-primary-source widening — life-science skill layer.
Mirrors the chembl_discover test style: injected fetcher, fixture JSON,
no real network. PharmGKB is the highest-yield primary source for the
CYP2C9 / CYP2C19 / CYP3A4 × THC/CBD metabolism axis.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.pharmgkb_discover import (  # noqa: E402
    NetworkError,
    PharmGKBAnnotationRow,
    PharmGKBSearcher,
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


_CBD_CHEMICAL = json.dumps({
    "data": [{
        "id": "PA166159594",
        "accessionId": "PA166159594",
        "name": "cannabidiol",
    }]
})

_CBD_ANNOTATIONS = json.dumps({
    "data": [
        {
            "id": "1184784522",
            "relatedGenes": [
                {"symbol": "CYP2C19", "id": "PA124"},
            ],
            "relatedVariants": [
                {"symbol": "rs4244285", "id": "PA166154774"},
            ],
            "phenotypeCategories": [
                {"term": "Metabolism/PK"}
            ],
            "levelOfEvidence": {"term": "1A"},
            "summaryMarkdown": {"html": "Reduced CYP2C19 activity slows CBD metabolism."},
        },
        {
            "id": "1184784523",
            "relatedGenes": [
                {"symbol": "CYP3A4", "id": "PA130"},
            ],
            "relatedVariants": [],
            "phenotypeCategories": [
                {"term": "Metabolism/PK"}
            ],
            "levelOfEvidence": {"term": "3"},
            "summaryMarkdown": {"html": "Mechanistic evidence only."},
        },
    ]
})


class HappyPathTests(unittest.TestCase):
    def test_cbd_resolves_to_clinical_annotation_rows(self) -> None:
        fetcher = _StubFetcher({
            "/chemical?": _CBD_CHEMICAL,
            "/clinicalAnnotation": _CBD_ANNOTATIONS,
        })
        s = PharmGKBSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first.source, Provenance.LIVE_PHARMGKB)
        self.assertIn("CYP2C19", first.related_genes)
        self.assertEqual(first.level_of_evidence, "1A")
        # 1A maps to Level B per Constitution §VII single-study cap.
        self.assertIn("Level B", first.suggested_grade)
        self.assertIn("provisional", first.suggested_grade)

    def test_level3_evidence_maps_to_level_d_grade(self) -> None:
        fetcher = _StubFetcher({
            "/chemical?": _CBD_CHEMICAL,
            "/clinicalAnnotation": _CBD_ANNOTATIONS,
        })
        s = PharmGKBSearcher(fetcher=fetcher)
        rows = s.search("CBD")
        self.assertIn("Level D", rows[1].suggested_grade)

    def test_direct_pharmgkb_accession_skips_resolver(self) -> None:
        # Chemical resolver should be skipped; only the annotations URL
        # is reached.
        fetcher = _StubFetcher({
            "/clinicalAnnotation": _CBD_ANNOTATIONS,
        })
        s = PharmGKBSearcher(fetcher=fetcher)
        rows = s.search("PA166159594")
        self.assertGreaterEqual(len(rows), 1)
        for url in fetcher.calls:
            self.assertNotIn("/chemical?", url)


class EmptyResultTests(unittest.TestCase):
    def test_unknown_chemical_returns_empty_list(self) -> None:
        fetcher = _StubFetcher({
            "/chemical?": json.dumps({"data": []}),
        })
        s = PharmGKBSearcher(fetcher=fetcher)
        self.assertEqual(s.search("NotARealDrug"), [])

    def test_chemical_resolves_but_no_annotations(self) -> None:
        fetcher = _StubFetcher({
            "/chemical?": _CBD_CHEMICAL,
            "/clinicalAnnotation": json.dumps({"data": []}),
        })
        s = PharmGKBSearcher(fetcher=fetcher)
        self.assertEqual(s.search("CBD"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise AssertionError("preflight failed to refuse")
        s = PharmGKBSearcher(fetcher=angry_fetcher)
        with self.assertRaises(DiscoverRefused):
            s.search("synthesize K2 Spice JWH-018")


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = PharmGKBSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("   ")

    def test_max_results_out_of_range(self) -> None:
        s = PharmGKBSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("CBD", max_results=999)


class NetworkErrorTests(unittest.TestCase):
    def test_fetcher_raising_surfaces_network_error(self) -> None:
        def angry_fetcher(url: str) -> str:
            raise OSError("connection refused")
        s = PharmGKBSearcher(fetcher=angry_fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")

    def test_html_body_surfaces_network_error(self) -> None:
        fetcher = _StubFetcher({
            "/chemical?": "<html>500</html>",
        })
        s = PharmGKBSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("CBD")


class RenderingTests(unittest.TestCase):
    def test_markdown_includes_pharmgkb_header(self) -> None:
        row = PharmGKBAnnotationRow(
            accession_id="1184784522",
            chemical_accession="PA166159594",
            chemical_name="cannabidiol",
            related_genes=("CYP2C19",),
            related_variants=("rs4244285",),
            phenotype_categories=("Metabolism/PK",),
            level_of_evidence="1A",
            suggested_grade="Level B (provisional, live_pharmgkb)",
            summary=None,
        )
        md = render_markdown("CBD", [row])
        self.assertIn("live_pharmgkb, provisional", md)
        self.assertIn("CYP2C19", md)
        self.assertIn("1A", md)

    def test_markdown_empty_rows_has_friendly_note(self) -> None:
        md = render_markdown("nothing", [])
        self.assertIn("No PharmGKB", md)

    def test_json_round_trip(self) -> None:
        row = PharmGKBAnnotationRow(
            accession_id="X", chemical_accession=None,
            chemical_name=None,
            related_genes=(), related_variants=(),
            phenotype_categories=(),
            level_of_evidence=None,
            suggested_grade="Level D (provisional, live_pharmgkb)",
            summary=None,
        )
        payload = json.loads(render_json("q", [row]))
        self.assertEqual(payload["provenance"], "live_pharmgkb")
        self.assertEqual(payload["hits"][0]["source"], "live_pharmgkb")


if __name__ == "__main__":
    unittest.main()
