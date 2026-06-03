"""CLI ``discover`` integration tests (Plan R3 + R7).

The discover subcommand was previously exercised only via per-discoverer
unit tests. These tests pin the CLI-level contract:

- ``_cmd_discover`` dispatches to the right registry entries based on
  ``--sources``.
- Per-source exceptions are caught and surfaced as
  ``{"error": "..."}`` in the JSON output, not crashes.
- ``--parallel N`` preserves output ordering (alphabetical by source
  key) so JSON / Markdown stays deterministic.
- ``--include-europepmc`` / ``--include-openalex`` widen the source set.
"""

from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from cannavec_science.__main__ import _cmd_discover


class _FakeRow:
    """Minimal stand-in for a discoverer row with ``to_dict()``."""

    def __init__(self, source: str, ident: str):
        self._source = source
        self._ident = ident

    def to_dict(self) -> dict:
        return {
            "source": self._source,
            "pmid": self._ident,
            "title": f"{self._source} row {self._ident}",
            "year": 2025,
        }


def _runner(source: str, n: int = 2):
    """Build a fake runner that returns ``n`` rows for ``source``."""
    def _run(args):
        return [_FakeRow(source, f"{source}-{i}") for i in range(n)]
    return _run


def _failing_runner(source: str, exc: Exception):
    def _run(args):
        raise exc
    return _run


class DiscoverSequentialTests(unittest.TestCase):
    def _args(self, **kwargs) -> argparse.Namespace:
        defaults = dict(
            query="cbd epilepsy",
            sources="pubmed,chembl",
            since=None,
            max=5,
            include_europepmc=False,
            include_openalex=False,
            parallel=1,
            json=True,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_two_lanes_dispatched_sequentially(self):
        registry = {"pubmed": _runner("pubmed"), "chembl": _runner("chembl")}
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            registry, clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(self._args())
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(set(payload["sources"]), {"pubmed", "chembl"})
        self.assertEqual(len(payload["sources"]["pubmed"]), 2)
        self.assertEqual(len(payload["sources"]["chembl"]), 2)

    def test_ranked_output_capped_to_max(self):
        # Retrieve wide, rank narrow: a 20-row pool is fetched and ranked, but
        # only --max ranked rows are surfaced (the over-fetch must not dump the
        # whole pool into the ranked table).
        registry = {"pubmed": _runner("pubmed", n=20)}
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            registry, clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(self._args(sources="pubmed", max=3))
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(len(payload["ranking"]["ranked"]), 3)   # ranked = top --max
        self.assertEqual(len(payload["sources"]["pubmed"]), 20)  # full pool retained as raw

    def test_unknown_source_surfaces_error_not_crash(self):
        registry = {"pubmed": _runner("pubmed")}
        args = self._args(sources="pubmed,whatever")
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            registry, clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("error", payload["sources"]["whatever"])
        self.assertIn("unknown source", payload["sources"]["whatever"]["error"])

    def test_lane_exception_surfaces_as_error_dict(self):
        registry = {
            "pubmed": _runner("pubmed"),
            "chembl": _failing_runner("chembl", RuntimeError("boom")),
        }
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            registry, clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(self._args())
        self.assertEqual(rc, 0, "one bad lane must not abort the fan-out")
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["sources"]["chembl"], {"error": "boom"})
        # Good lane still resolved.
        self.assertEqual(len(payload["sources"]["pubmed"]), 2)


class DiscoverParallelTests(unittest.TestCase):
    def _args(self, parallel: int) -> argparse.Namespace:
        return argparse.Namespace(
            query="cbd epilepsy",
            sources="pubmed,chembl,ctgov,pubchem",
            since=None,
            max=5,
            include_europepmc=False,
            include_openalex=False,
            parallel=parallel,
            json=True,
        )

    def test_parallel_preserves_alphabetical_ordering(self):
        registry = {
            "pubmed": _runner("pubmed"),
            "chembl": _runner("chembl"),
            "ctgov": _runner("ctgov"),
            "pubchem": _runner("pubchem"),
        }
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            registry, clear=True,
        ):
            # Run serial AND parallel; both JSON outputs must match.
            buf_serial = io.StringIO()
            with redirect_stdout(buf_serial):
                _cmd_discover(self._args(parallel=1))
            buf_parallel = io.StringIO()
            with redirect_stdout(buf_parallel):
                _cmd_discover(self._args(parallel=4))
        payload_serial = json.loads(buf_serial.getvalue())
        payload_parallel = json.loads(buf_parallel.getvalue())
        # Key ordering inside the dict + per-source row order both stable.
        self.assertEqual(
            list(payload_serial["sources"]),
            list(payload_parallel["sources"]),
        )
        self.assertEqual(
            payload_serial["sources"], payload_parallel["sources"],
        )

    def test_parallel_with_one_failing_lane_does_not_break_others(self):
        registry = {
            "pubmed": _runner("pubmed"),
            "chembl": _failing_runner("chembl", ValueError("upstream 500")),
            "ctgov": _runner("ctgov"),
            "pubchem": _runner("pubchem"),
        }
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            registry, clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(self._args(parallel=4))
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(
            payload["sources"]["chembl"], {"error": "upstream 500"},
        )
        for live_source in ("pubmed", "ctgov", "pubchem"):
            self.assertEqual(len(payload["sources"][live_source]), 2)


class _FakeReranker:
    """Patched-in stand-in for LLMReranker — reorders without any network."""

    name = "llm"

    def __init__(self, *args, **kwargs):
        self.model = kwargs.get("model")

    def plan(self, query, candidates):
        from cannavec_science.ranker import RankPlan

        order = tuple(c.identifier for c in reversed(list(candidates)))
        rationales = {order[0]: "fake top"} if order else {}
        return RankPlan(order=order, rationales=rationales, backend="llm")


class _RaisingReranker:
    """Simulates a missing API key / offline model — must degrade silently."""

    name = "llm"

    def __init__(self, *args, **kwargs):
        pass

    def plan(self, query, candidates):
        raise RuntimeError("no ANTHROPIC_API_KEY")


class DiscoverRankingTests(unittest.TestCase):
    """The ranker integration: deterministic by default, opt-in LLM lift."""

    def _args(self, **kwargs) -> argparse.Namespace:
        defaults = dict(
            query="cbd epilepsy",
            sources="pubmed,chembl",
            since=None,
            max=5,
            include_europepmc=False,
            include_openalex=False,
            parallel=1,
            json=True,
            rank=True,
            rerank_llm=False,
            rerank_model="claude-sonnet-4-6",
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def _registry(self):
        return {"pubmed": _runner("pubmed"), "chembl": _runner("chembl")}

    def _run(self, args):
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY",
            self._registry(), clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(args)
        return rc, json.loads(buf.getvalue())

    def test_deterministic_ranking_present_by_default(self):
        rc, payload = self._run(self._args())
        self.assertEqual(rc, 0)
        self.assertIn("ranking", payload)
        self.assertEqual(payload["ranking"]["backend_used"], "deterministic")
        self.assertFalse(payload["ranking"]["escalated"])
        # All four fanned-out candidates appear in the cross-source ranking.
        ids = {r["identifier"] for r in payload["ranking"]["ranked"]}
        self.assertEqual(ids, {"pubmed-0", "pubmed-1", "chembl-0", "chembl-1"})

    def test_no_rank_omits_ranking(self):
        rc, payload = self._run(self._args(rank=False))
        self.assertEqual(rc, 0)
        self.assertNotIn("ranking", payload)

    def test_rerank_llm_reorders_when_escalated(self):
        # Four equal-score candidates (no query overlap) → near-tie → escalates.
        with patch("cannavec_science.ranker_llm.LLMReranker", _FakeReranker):
            rc, payload = self._run(self._args(rerank_llm=True))
        self.assertEqual(rc, 0)
        self.assertEqual(payload["ranking"]["backend_used"], "llm")
        self.assertTrue(payload["ranking"]["escalated"])
        # Four equal-score candidates → the top is a near-tie.
        self.assertEqual(payload["ranking"]["escalation_reason"], "top near-tie")

    def test_rerank_llm_degrades_to_deterministic_on_failure(self):
        with patch("cannavec_science.ranker_llm.LLMReranker", _RaisingReranker):
            rc, payload = self._run(self._args(rerank_llm=True))
        self.assertEqual(rc, 0, "a failed model must never break discover")
        self.assertEqual(payload["ranking"]["backend_used"], "deterministic")
        self.assertTrue(any("failed" in n for n in payload["ranking"]["notes"]))

    def test_ranking_skipped_when_no_candidates(self):
        # A lane that errors out yields no rankable candidates → no ranking key.
        registry = {"chembl": _failing_runner("chembl", RuntimeError("boom"))}
        with patch.dict(
            "cannavec_science.__main__._DISCOVERER_REGISTRY", registry, clear=True,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_discover(self._args(sources="chembl"))
        self.assertEqual(rc, 0)
        self.assertNotIn("ranking", json.loads(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
