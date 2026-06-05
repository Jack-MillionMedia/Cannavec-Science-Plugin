"""CLI source-health regression tests (spec 003 US4 / FR-004).

The CLI handler ``_cmd_source_health`` previously read deleted dataclass
fields (``ok``/``rtt_ms``/``error``) and crashed with AttributeError on
every invocation. These tests pin the new behaviour:

- ``source-health`` exits 0 when every requested source is green,
- exits 1 when any source is red or not configured,
- emits structured JSON when ``--json`` is passed,
- never raises AttributeError on a healthy probe.
"""

from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from cannavec_science.__main__ import _cmd_source_health
from cannavec_science.source_health import HealthStatus, SourceHealth


def _green(source: str) -> SourceHealth:
    return SourceHealth(
        source=source, status=HealthStatus.GREEN,
        latency_ms=120, last_success_iso="2026-05-21T00:00:00+00:00",
        error_excerpt=None,
    )


def _red(source: str, error: str = "connection refused") -> SourceHealth:
    return SourceHealth(
        source=source, status=HealthStatus.RED,
        latency_ms=None, last_success_iso=None,
        error_excerpt=error,
    )


def _yellow(source: str) -> SourceHealth:
    return SourceHealth(
        source=source, status=HealthStatus.YELLOW,
        latency_ms=8000, last_success_iso="2026-05-21T00:00:00+00:00",
        error_excerpt=None,
    )


class SourceHealthCLINoAttributeErrorTests(unittest.TestCase):
    def test_no_attribute_error_on_green(self):
        """Pre-fix: AttributeError on h.ok / h.rtt_ms / h.error."""
        args = argparse.Namespace(
            sources="pubmed,chembl,ctgov", json=False,
        )
        healths = [_green("pubmed"), _green("chembl"), _green("ctgov")]
        with patch(
            "cannavec_science.source_health.ping_all",
            return_value=healths,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_source_health(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("pubmed", out)
        self.assertIn("green", out)
        # The exact rtt format is documented per spec ("rtt <N>ms"); the
        # critical regression is "no AttributeError" which we got past
        # already by reaching here.
        self.assertIn("rtt", out)

    def test_red_source_exits_nonzero(self):
        args = argparse.Namespace(
            sources="pubmed,chembl,ctgov", json=False,
        )
        healths = [_green("pubmed"), _red("chembl"), _green("ctgov")]
        with patch(
            "cannavec_science.source_health.ping_all",
            return_value=healths,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_source_health(args)
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("red", out)
        self.assertIn("connection refused", out)

    def test_unknown_source_marks_not_configured(self):
        args = argparse.Namespace(
            sources="pubmed,nonexistent", json=False,
        )
        healths = [_green("pubmed"), _green("chembl")]
        with patch(
            "cannavec_science.source_health.ping_all",
            return_value=healths,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_source_health(args)
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("nonexistent", out)
        self.assertIn("not configured", out)


class SourceHealthCLIJSONTests(unittest.TestCase):
    def test_json_emits_structured_payload(self):
        args = argparse.Namespace(
            sources="pubmed,chembl", json=True,
        )
        healths = [_green("pubmed"), _yellow("chembl")]
        with patch(
            "cannavec_science.source_health.ping_all",
            return_value=healths,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_source_health(args)
        # yellow ≠ green → non-zero exit
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue())
        self.assertIn("sources", payload)
        by_src = {row["source"]: row for row in payload["sources"]}
        self.assertEqual(by_src["pubmed"]["status"], "green")
        self.assertEqual(by_src["chembl"]["status"], "yellow")
        self.assertEqual(by_src["pubmed"]["latency_ms"], 120)
        # error_excerpt must round-trip in JSON, including None
        self.assertIn("error_excerpt", by_src["pubmed"])

    def test_json_includes_all_three_default_sources(self):
        args = argparse.Namespace(sources=None, json=True)
        healths = [
            _green("pubmed"), _green("chembl"), _green("ctgov"),
            _green("biorxiv"),  # extra probe — should be filtered out
        ]
        with patch(
            "cannavec_science.source_health.ping_all",
            return_value=healths,
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _cmd_source_health(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        srcs = {row["source"] for row in payload["sources"]}
        # Default sources only (no biorxiv since it wasn't requested).
        self.assertEqual(srcs, {"pubmed", "chembl", "ctgov"})


if __name__ == "__main__":
    unittest.main()
