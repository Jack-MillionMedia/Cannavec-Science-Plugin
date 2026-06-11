"""The `audit-mcp --review` operator render path — offline (it reads the improve-
queue file, no network). Locks the two branches (empty vs populated) and the JSON
shape so this shipped, user-facing output can't silently regress. Coverage for a
render path the library-level tests in test_source_audit.py don't exercise."""

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
    """Isolated CANNAVEC_HOME so the improve-queue lives in a temp dir."""

    def __enter__(self) -> Path:
        self._tmp = tempfile.mkdtemp(prefix="cv_review_cli_")
        self._saved = os.environ.get("CANNAVEC_HOME")
        os.environ["CANNAVEC_HOME"] = self._tmp
        return Path(self._tmp)

    def __exit__(self, *_a):
        if self._saved is None:
            os.environ.pop("CANNAVEC_HOME", None)
        else:
            os.environ["CANNAVEC_HOME"] = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)


def _seed(home: Path, rows) -> None:
    (home / "improve_queue.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class AuditMcpReviewCli(unittest.TestCase):
    def test_empty_queue_renders_empty_not_crash(self):
        with _Home():
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(argparse.Namespace(review=True, json=False))
        self.assertEqual(rc, 0)
        self.assertIn("empty", out.getvalue().lower())

    def test_populated_queue_ranks_highest_impact_first(self):
        with _Home() as home:
            _seed(home, [
                {"ts": "t1", "query": "cbd dravet",
                 "false_sources": [{"identifier": "999", "reason": "retracted"}],
                 "missing_sources": ["NCT01", "NCT02"]},
                {"ts": "t2", "query": "cbd dravet",
                 "false_sources": [], "missing_sources": ["NCT01"]},
            ])
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(argparse.Namespace(review=True, json=False))
        text = out.getvalue()
        self.assertEqual(rc, 0)
        # NCT01 recurs (2x) → must appear before the 1x NCT02 (highest-impact first)
        self.assertIn("NCT01", text)
        self.assertLess(text.index("NCT01"), text.index("NCT02"))
        self.assertIn("999", text)           # the false source is surfaced
        self.assertIn("cbd dravet", text)    # the gap-hitting query is surfaced

    def test_json_review_is_machine_readable(self):
        with _Home() as home:
            _seed(home, [{"ts": "t", "query": "q", "false_sources": [],
                          "missing_sources": ["NCT01"]}])
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_audit_mcp(argparse.Namespace(review=True, json=True))
        data = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(data["entries"], 1)
        self.assertEqual(data["missing_by_id"][0]["identifier"], "NCT01")


if __name__ == "__main__":
    unittest.main()
