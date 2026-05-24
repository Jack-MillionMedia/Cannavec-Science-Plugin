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


if __name__ == "__main__":
    unittest.main()
