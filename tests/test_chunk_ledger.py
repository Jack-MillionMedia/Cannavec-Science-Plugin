"""Recursive learning: the longitudinal chunk ledger that lets the flywheel refine
the KB over time — confirming fixes (resolved), catching regressions, and re-opening
settled chunks when NEW evidence appears. Deterministic + offline (temp store, injected
timestamps)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cannavec_science import chunk_ledger as cl
from cannavec_science import chunk_eval as ce
from cannavec_science.chunk_audit import Chunk


def _verdict(chunk_key, status, content_hash="h1", corr=None):
    return ce.ChunkVerdict(
        chunk_key=chunk_key, doc_id=chunk_key.split("#")[0], h2_anchor="S",
        status=status, confidence="high", issues=(), corroboration=corr,
        evidence_checked=corr is not None, content_hash=content_hash)


class LedgerDiff(unittest.TestCase):
    def test_first_eval_is_new(self):
        with tempfile.TemporaryDirectory() as d:
            diff = cl.record_evaluation(_verdict("c1", ce.MISLEADING), store_dir=d,
                                        now="2026-06-11T00:00:00+00:00")
        self.assertEqual(diff.change, cl.NEW)

    def test_flagged_then_fixed_is_resolved(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict("c1", ce.WEAKLY_CITED, content_hash="old"),
                                 store_dir=d, now="t1")
            diff = cl.record_evaluation(_verdict("c1", ce.CORRECT, content_hash="new"),
                                        store_dir=d, now="t2")
        self.assertEqual(diff.change, cl.RESOLVED)

    def test_correct_then_flagged_is_regressed(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict("c1", ce.CORRECT, content_hash="h"),
                                 store_dir=d, now="t1")
            diff = cl.record_evaluation(_verdict("c1", ce.MISLEADING, content_hash="h2"),
                                        store_dir=d, now="t2")
        self.assertEqual(diff.change, cl.REGRESSED)
        self.assertTrue(diff.is_alert)

    def test_recurring_when_unchanged_and_still_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict("c1", ce.INCOMPLETE, content_hash="h"),
                                 store_dir=d, now="t1")
            diff = cl.record_evaluation(_verdict("c1", ce.INCOMPLETE, content_hash="h"),
                                        store_dir=d, now="t2")
        self.assertEqual(diff.change, cl.RECURRING)

    def test_reopened_when_new_evidence_appears(self):
        # chunk unchanged + previously clean, but the evidence snapshot moved forward.
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(
                _verdict("c1", ce.CORRECT, content_hash="h"), store_dir=d, now="t1",
                evidence_snapshot={"ids": ["111"], "max_year": 2018})
            diff = cl.record_evaluation(
                _verdict("c1", ce.UNEVALUATED, content_hash="h"), store_dir=d, now="t2",
                evidence_snapshot={"ids": ["111", "999"], "max_year": 2025})
        self.assertEqual(diff.change, cl.REOPENED)
        self.assertTrue(diff.is_alert)

    def test_not_reopened_when_evidence_static(self):
        with tempfile.TemporaryDirectory() as d:
            snap = {"ids": ["111"], "max_year": 2018}
            cl.record_evaluation(_verdict("c1", ce.CORRECT, content_hash="h"),
                                 store_dir=d, now="t1", evidence_snapshot=snap)
            diff = cl.record_evaluation(_verdict("c1", ce.CORRECT, content_hash="h"),
                                        store_dir=d, now="t2", evidence_snapshot=snap)
        self.assertNotEqual(diff.change, cl.REOPENED)


class KbHealthTrend(unittest.TestCase):
    def test_health_counts_latest_per_chunk(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict("c1", ce.MISLEADING), store_dir=d, now="t1")
            cl.record_evaluation(_verdict("c1", ce.CORRECT, content_hash="h2"),
                                 store_dir=d, now="t2")        # c1 latest = correct
            cl.record_evaluation(_verdict("c2", ce.WEAKLY_CITED), store_dir=d, now="t3")
            h = cl.kb_health(store_dir=d)
        self.assertEqual(h.total, 2)                            # 2 distinct chunks
        by = dict(h.by_status)
        self.assertEqual(by.get(ce.CORRECT), 1)
        self.assertEqual(by.get(ce.WEAKLY_CITED), 1)
        self.assertEqual(h.correct_fraction, 0.5)

    def test_snapshot_health_appends_trend(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict("c1", ce.CORRECT), store_dir=d, now="t1")
            cl.snapshot_health(store_dir=d, now="t1")
            cl.record_evaluation(_verdict("c2", ce.CORRECT), store_dir=d, now="t2")
            cl.snapshot_health(store_dir=d, now="t2")
            trend = cl.health_trend(store_dir=d)
        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[-1]["total"], 2)


class EvalFeedback(unittest.TestCase):
    def test_suppress_then_is_suppressed_until_content_changes(self):
        with tempfile.TemporaryDirectory() as d:
            cl.suppress_flag("c1#S", "missing_evidence", "hashA",
                             reason="false positive", store_dir=d)
            self.assertTrue(cl.is_suppressed("c1#S", "missing_evidence", "hashA",
                                             store_dir=d))
            # a content change re-arms the check (the chunk is different now)
            self.assertFalse(cl.is_suppressed("c1#S", "missing_evidence", "hashB",
                                              store_dir=d))
            # a different verdict is not suppressed
            self.assertFalse(cl.is_suppressed("c1#S", "superseded", "hashA",
                                              store_dir=d))

    def test_missing_feedback_file_is_not_suppressed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(cl.is_suppressed("x", "y", "z", store_dir=d))


if __name__ == "__main__":
    unittest.main()
