"""Tests for cannavec_science.opentargets_discover.

Cannabis-primary-source widening — life-science skill layer.
GraphQL POST + injected fetcher, no real network.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.opentargets_discover import (  # noqa: E402
    NetworkError,
    OpenTargetsAssociationRow,
    OpenTargetsSearcher,
    render_json,
    render_markdown,
)
from cannavec_science.discover_guard import (  # noqa: E402
    DiscoverRefused,
    Provenance,
)


class _StubFetcher:
    """Routes GraphQL POSTs by the operation name in the request body."""

    def __init__(self, body_map: dict[str, str]) -> None:
        # body_map: substring-of-query-string → response body.
        self._body_map = body_map
        self.calls: list[tuple[str, bytes | None]] = []

    def __call__(self, url: str, *, body: bytes | None = None) -> str:
        self.calls.append((url, body))
        if body is None:
            raise AssertionError("Open Targets calls must POST a body")
        body_str = body.decode("utf-8")
        for needle, payload in self._body_map.items():
            if needle in body_str:
                return payload
        raise AssertionError(
            f"Unexpected GraphQL body: {body_str[:200]!r}. "
            f"Known needles: {list(self._body_map)}"
        )


_RESOLVE_RESULT = json.dumps({
    "data": {
        "search": {
            "hits": [{
                "id": "ENSG00000118432",
                "name": "CNR1",
                "entity": "target",
                "object": {
                    "id": "ENSG00000118432",
                    "approvedSymbol": "CNR1",
                    "approvedName": "cannabinoid receptor 1",
                },
            }]
        }
    }
})

_ASSOCIATIONS_RESULT = json.dumps({
    "data": {
        "target": {
            "id": "ENSG00000118432",
            "approvedSymbol": "CNR1",
            "approvedName": "cannabinoid receptor 1",
            "associatedDiseases": {
                "count": 2,
                "rows": [
                    {
                        "disease": {
                            "id": "EFO_0000094",
                            "name": "drug dependence",
                            "therapeuticAreas": [
                                {"id": "EFO_0005774", "name": "psychiatric disorder"},
                            ],
                        },
                        "score": 0.84,
                        "datatypeScores": [
                            {"id": "genetic_association", "score": 0.71},
                            {"id": "literature", "score": 0.62},
                        ],
                    },
                    {
                        "disease": {
                            "id": "EFO_0000196",
                            "name": "obesity",
                            "therapeuticAreas": [
                                {"id": "EFO_0009605", "name": "metabolic disease"},
                            ],
                        },
                        "score": 0.61,
                        "datatypeScores": [
                            {"id": "known_drug", "score": 0.55},
                        ],
                    },
                ],
            },
        }
    }
})


class HappyPathTests(unittest.TestCase):
    def test_cb1_resolves_and_returns_associations(self) -> None:
        fetcher = _StubFetcher({
            "associatedDiseases": _ASSOCIATIONS_RESULT,
            "resolveTarget": _RESOLVE_RESULT,
        })
        s = OpenTargetsSearcher(fetcher=fetcher)
        rows = s.search("CB1", max_results=2)
        self.assertEqual(len(rows), 2)
        # CB1 hint should bypass the search call entirely.
        post_bodies = [b.decode("utf-8") for _u, b in fetcher.calls if b]
        self.assertTrue(
            any("associatedDiseases" in b for b in post_bodies),
            "associatedDiseases query must run",
        )
        self.assertFalse(
            any("resolveTarget" in b for b in post_bodies),
            "CB1 fast-path should skip resolveTarget",
        )
        first = rows[0]
        self.assertEqual(first.ensembl_id, "ENSG00000118432")
        self.assertEqual(first.target_symbol, "CNR1")
        self.assertEqual(first.disease_name, "drug dependence")
        self.assertAlmostEqual(first.overall_score or 0.0, 0.84)
        self.assertEqual(first.source, Provenance.LIVE_OPENTARGETS)
        self.assertIn("live_opentargets", first.suggested_grade)

    def test_unknown_query_falls_through_to_search(self) -> None:
        fetcher = _StubFetcher({
            "resolveTarget": _RESOLVE_RESULT,
            "associatedDiseases": _ASSOCIATIONS_RESULT,
        })
        s = OpenTargetsSearcher(fetcher=fetcher)
        rows = s.search("cannabinoid receptor 1")
        self.assertGreater(len(rows), 0)


class EmptyResultTests(unittest.TestCase):
    def test_target_not_resolved_returns_empty(self) -> None:
        fetcher = _StubFetcher({
            "resolveTarget": json.dumps({"data": {"search": {"hits": []}}}),
        })
        s = OpenTargetsSearcher(fetcher=fetcher)
        self.assertEqual(s.search("ridiculously rare protein"), [])

    def test_resolver_returns_empty_associations(self) -> None:
        fetcher = _StubFetcher({
            "associatedDiseases": json.dumps({
                "data": {
                    "target": {
                        "id": "ENSG00000118432",
                        "approvedSymbol": "CNR1",
                        "approvedName": "cannabinoid receptor 1",
                        "associatedDiseases": {"count": 0, "rows": []},
                    }
                }
            }),
        })
        s = OpenTargetsSearcher(fetcher=fetcher)
        self.assertEqual(s.search("CB1"), [])


class RefusalTests(unittest.TestCase):
    def test_banned_query_refused_before_network(self) -> None:
        def angry(url, *, body=None):
            raise AssertionError("fetched anyway")
        s = OpenTargetsSearcher(fetcher=angry)
        with self.assertRaises(DiscoverRefused):
            s.search("synthesize K2 Spice JWH-018")


class GraphQLErrorTests(unittest.TestCase):
    def test_graphql_errors_surface_as_network_error(self) -> None:
        fetcher = _StubFetcher({
            "associatedDiseases": json.dumps({
                "errors": [{"message": "field X not found"}]
            }),
        })
        s = OpenTargetsSearcher(fetcher=fetcher)
        with self.assertRaises(NetworkError):
            s.search("CB1")


class InputValidationTests(unittest.TestCase):
    def test_empty_query_raises_value_error(self) -> None:
        s = OpenTargetsSearcher(fetcher=_StubFetcher({}))
        with self.assertRaises(ValueError):
            s.search("")


class RenderingTests(unittest.TestCase):
    def test_markdown_includes_header(self) -> None:
        row = OpenTargetsAssociationRow(
            ensembl_id="ENSG00000118432",
            target_symbol="CNR1",
            target_name="cannabinoid receptor 1",
            query="CB1",
            disease_id="EFO_0000094",
            disease_name="drug dependence",
            therapeutic_areas=("psychiatric disorder",),
            overall_score=0.84,
            datatype_scores=(("genetic_association", 0.71),),
        )
        md = render_markdown("CB1", [row])
        self.assertIn("live_opentargets", md)
        self.assertIn("CNR1", md)
        self.assertIn("drug dependence", md)

    def test_json_round_trip(self) -> None:
        row = OpenTargetsAssociationRow(
            ensembl_id="ENSG0", target_symbol=None,
            target_name=None, query="q",
            disease_id="EFO_X", disease_name="x",
            therapeutic_areas=(), overall_score=None,
            datatype_scores=(),
        )
        payload = json.loads(render_json("q", [row]))
        self.assertEqual(payload["provenance"], "live_opentargets")
        self.assertEqual(payload["hits"][0]["source"], "live_opentargets")


if __name__ == "__main__":
    unittest.main()
