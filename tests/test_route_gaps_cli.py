"""The `audit-mcp --chunks` and `route-gaps` CLI paths — offline. Locks the
shipped, user-facing output and the safety invariant (route-gaps never writes the
curated RESEARCH_BACKLOG.md) so they can't silently regress. Coverage the
library-level tests don't exercise."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import cannavec_science.__main__ as cli


class _Env:
    """Isolated CANNAVEC_HOME (improve-queue) + a temp KB root."""

    def __enter__(self):
        self._tmp = tempfile.mkdtemp(prefix="cv_route_cli_")
        self.home = Path(self._tmp) / "home"
        self.kb = Path(self._tmp) / "kb"
        self.home.mkdir()
        (self.kb / "cannabis" / "logs").mkdir(parents=True)
        (self.kb / "RESEARCH_BACKLOG.md").write_text("# CURATED\n", encoding="utf-8")
        self._saved = os.environ.get("CANNAVEC_HOME")
        os.environ["CANNAVEC_HOME"] = str(self.home)
        return self

    def __exit__(self, *_a):
        if self._saved is None:
            os.environ.pop("CANNAVEC_HOME", None)
        else:
            os.environ["CANNAVEC_HOME"] = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)


def _ns(**kw):
    base = dict(query=None, sources=None, chunks=None, no_discover=False,
               no_accuracy=True, review=False, json=False,
               kb_root=None, dry_run=False)
    base.update(kw)
    return argparse.Namespace(**base)


class AuditMcpChunksCli(unittest.TestCase):
    def test_chunks_audit_logs_and_renders(self):
        chunks = json.dumps([
            {"doc_id": "anx", "h2_anchor": "Dosing",
             "text": "CBD 300 mg reduced anxiety effectively in a trial.",
             "citations": []},
        ])
        with _Env() as env:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(_ns(query="CBD anxiety dose", chunks=chunks))
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("KB chunk audit", text)
            self.assertIn("uncited_claim", text)
            self.assertTrue((env.home / "improve_queue.jsonl").exists())

    def test_chunks_inline_bad_json_is_clean_error(self):
        with _Env():
            err = io.StringIO()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(_ns(query="q", chunks="{not json"))
        self.assertEqual(rc, 2)

    def test_needs_query(self):
        with _Env():
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(_ns(query=None, chunks="[]"))
        self.assertEqual(rc, 2)


class RouteGapsCli(unittest.TestCase):
    def _seed_queue(self, home: Path):
        (home / "improve_queue.jsonl").write_text(
            json.dumps({"ts": "t", "query": "CBD for Dravet epilepsy seizures",
                        "chunk_issues": [
                            {"dimension": "accuracy", "verdict": "contradiction",
                             "doc_id": "dravet", "chunk_key": "dravet#S",
                             "detail": "cited PMID contradicts", "evidence": "e",
                             "recommended_action": "rework", "route": "improve_agent"}]})
            + "\n", encoding="utf-8")

    def test_route_writes_live_backlog_not_curated(self):
        with _Env() as env:
            self._seed_queue(env.home)
            before = (env.kb / "RESEARCH_BACKLOG.md").read_text()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_route_gaps(_ns(kb_root=str(env.kb)))
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("live gaps", text)
            self.assertTrue((env.kb / "RESEARCH_BACKLOG.live.md").exists())
            self.assertTrue(any((env.kb / "cannabis" / "logs" / "live-gap").glob("*.json")))
            # curated backlog byte-identical
            self.assertEqual((env.kb / "RESEARCH_BACKLOG.md").read_text(), before)

    def test_review_writes_nothing(self):
        with _Env() as env:
            self._seed_queue(env.home)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_route_gaps(_ns(kb_root=str(env.kb), review=True))
            self.assertEqual(rc, 0)
            self.assertFalse((env.kb / "RESEARCH_BACKLOG.live.md").exists())

    def test_empty_queue_is_clean(self):
        with _Env() as env:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_route_gaps(_ns(kb_root=str(env.kb)))
            self.assertEqual(rc, 0)
            self.assertIn("nothing to route", out.getvalue())

    def test_json_plan_is_machine_readable(self):
        with _Env() as env:
            self._seed_queue(env.home)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_route_gaps(_ns(kb_root=str(env.kb), review=True, json=True))
            data = json.loads(out.getvalue())
            self.assertEqual(rc, 0)
            self.assertEqual(data["counts"]["P0"], 1)


if __name__ == "__main__":
    unittest.main()
