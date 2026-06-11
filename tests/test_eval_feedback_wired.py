"""The recursive-learning precision loop is actually WIRED end-to-end: an operator
marks a flag a false positive (`eval-feedback`), and `--rigorous` then stops
re-queuing that exact flag to the backlog until the chunk's content changes. This
guards the review finding that the suppression store was inert. Offline."""

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
from cannavec_science import chunk_ledger, source_audit


class _Home:
    def __enter__(self) -> Path:
        self._tmp = tempfile.mkdtemp(prefix="cv_fb_")
        self._saved = os.environ.get("CANNAVEC_HOME")
        os.environ["CANNAVEC_HOME"] = self._tmp
        return Path(self._tmp)

    def __exit__(self, *_a):
        if self._saved is None:
            os.environ.pop("CANNAVEC_HOME", None)
        else:
            os.environ["CANNAVEC_HOME"] = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)


# a misleading chunk (cure/miracle banned patterns) — deterministic, offline
_CHUNK = json.dumps([{
    "doc_id": "anx", "h2_anchor": "Efficacy",
    "text": "CBD is a miracle cure that is 100% effective and completely safe.",
    "citations": []}])


def _rig_ns(**kw):
    base = dict(query="CBD anxiety", sources=None, chunks=_CHUNK, no_discover=False,
                no_accuracy=True, rigorous=True, no_corpus=True, review=False, json=False)
    base.update(kw)
    return argparse.Namespace(**base)


def _queue_lines(home: Path):
    p = source_audit.improve_queue_path(str(home))
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class FeedbackSuppressionLoop(unittest.TestCase):
    def test_suppressed_flag_is_not_requeued(self):
        with _Home() as home:
            # 1) first rigorous run → issues queued
            with redirect_stdout(io.StringIO()):
                cli._cmd_audit_mcp(_rig_ns())
            first = _queue_lines(home)
            self.assertTrue(first and first[0]["chunk_issues"])
            verdicts_hash = first[0]["chunk_issues"][0]  # has chunk_key
            # find the content hash via the ledger
            latest = chunk_ledger.latest_by_chunk(store_dir=str(home))
            chash = latest["anx#Efficacy"]["content_hash"]

            # 2) operator suppresses the banned_misleading flag on that chunk
            with redirect_stdout(io.StringIO()):
                rc = cli._cmd_eval_feedback(argparse.Namespace(
                    chunk="anx#Efficacy", verdict="banned_misleading", hash=chash,
                    reason="reviewed", list=False, json=False))
            self.assertEqual(rc, 0)

            # 3) re-run on the SAME content → banned_misleading must NOT be re-queued
            with redirect_stdout(io.StringIO()):
                cli._cmd_audit_mcp(_rig_ns())
            after = _queue_lines(home)
            last_issues = after[-1]["chunk_issues"]
            self.assertFalse(any(i["verdict"] == "banned_misleading" for i in last_issues),
                             "suppressed verdict was re-queued")

    def test_list_renders(self):
        with _Home():
            cli._cmd_eval_feedback(argparse.Namespace(
                chunk="c#S", verdict="missing_evidence", hash="h", reason="",
                list=False, json=False))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli._cmd_eval_feedback(argparse.Namespace(list=True, json=True))
            data = json.loads(out.getvalue())
            self.assertEqual(rc, 0)
            self.assertEqual(data[0]["verdict"], "missing_evidence")

    def test_suppress_needs_all_fields(self):
        with _Home():
            rc = cli._cmd_eval_feedback(argparse.Namespace(
                chunk="c", verdict=None, hash=None, reason=None, list=False, json=False))
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
