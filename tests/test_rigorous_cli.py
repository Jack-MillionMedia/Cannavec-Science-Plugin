"""The `audit-mcp --rigorous` and `kb-health` CLI paths — offline (--no-corpus, so
no network). Locks the shipped rigorous-evaluation render + the recursive-learning
ledger/health surface."""

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


class _Home:
    def __enter__(self) -> Path:
        self._tmp = tempfile.mkdtemp(prefix="cv_rig_cli_")
        self._saved = os.environ.get("CANNAVEC_HOME")
        os.environ["CANNAVEC_HOME"] = self._tmp
        return Path(self._tmp)

    def __exit__(self, *_a):
        if self._saved is None:
            os.environ.pop("CANNAVEC_HOME", None)
        else:
            os.environ["CANNAVEC_HOME"] = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)


def _ns(**kw):
    base = dict(query=None, sources=None, chunks=None, no_discover=False,
                no_accuracy=True, rigorous=True, no_corpus=True, review=False, json=False)
    base.update(kw)
    return argparse.Namespace(**base)


_MISLEADING = json.dumps([{
    "doc_id": "anx", "h2_anchor": "Efficacy",
    "text": "CBD is a miracle cure that is 100% effective and completely safe.",
    "citations": []}])


class RigorousCli(unittest.TestCase):
    def test_rigorous_renders_status_and_writes_ledger(self):
        with _Home() as home:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(_ns(query="CBD anxiety", chunks=_MISLEADING))
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Rigorous chunk evaluation", text)
            self.assertIn("MISLEADING", text)
            self.assertTrue((home / "chunk_ledger.jsonl").exists())

    def test_rigorous_json_is_machine_readable(self):
        with _Home():
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(_ns(query="CBD anxiety", chunks=_MISLEADING,
                                            json=True))
            data = json.loads(out.getvalue())
            self.assertEqual(rc, 0)
            self.assertEqual(data["verdicts"][0]["status"], "misleading")

    def test_rerun_detects_resolution(self):
        # Same chunk, same on-topic query, fixed content: a misleading botanical chunk
        # rewritten to clean, on-topic, citation-free botanical prose → resolved.
        q = "cannabis sativa plant morphology and taxonomy"
        bad = json.dumps([{
            "doc_id": "bot", "h2_anchor": "Overview",
            "text": "Cannabis is a miracle cure that is 100% effective and completely "
                    "safe for every condition.",
            "citations": []}])
        good = json.dumps([{
            "doc_id": "bot", "h2_anchor": "Overview",
            "text": "Cannabis sativa is an annual herbaceous flowering plant cultivated "
                    "for millennia; its botanical taxonomy, plant morphology, growth "
                    "habit, and documented historical uses appear extensively in the "
                    "agricultural and ethnographic literature spanning many continents "
                    "and centuries of recorded cultivation and trade practice.",
            "citations": []}])
        with _Home():
            with redirect_stdout(io.StringIO()):
                cli._cmd_audit_mcp(_ns(query=q, chunks=bad))
            out = io.StringIO()
            with redirect_stdout(out):
                cli._cmd_audit_mcp(_ns(query=q, chunks=good, json=True))
            data = json.loads(out.getvalue())
        self.assertEqual(data["verdicts"][0]["status"], "unevaluated")  # now clean
        self.assertEqual(data["ledger"][0]["change"], "resolved")


class KbHealthCli(unittest.TestCase):
    def test_empty_health(self):
        with _Home():
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_kb_health(argparse.Namespace(json=False))
            self.assertEqual(rc, 0)
            self.assertIn("no chunks evaluated", out.getvalue())

    def test_health_after_eval(self):
        with _Home():
            with redirect_stdout(io.StringIO()):
                cli._cmd_audit_mcp(_ns(query="CBD anxiety", chunks=_MISLEADING))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_kb_health(argparse.Namespace(json=True))
            data = json.loads(out.getvalue())
            self.assertEqual(rc, 0)
            self.assertEqual(data["health"]["total"], 1)
            self.assertGreaterEqual(len(data["trend"]), 1)


if __name__ == "__main__":
    unittest.main()
