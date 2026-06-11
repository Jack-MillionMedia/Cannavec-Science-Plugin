"""Regressions for the adversarial hardening audit — each pins a fix for a REAL
weak link (silent false-negative, ledger scale/durability, stale routing, unguarded
fetch). All offline."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import cannavec_science.__main__ as cli
from cannavec_science import chunk_eval as ce
from cannavec_science import chunk_ledger as cl
from cannavec_science import gap_router as gr
from cannavec_science.chunk_audit import Chunk


# ── #2 stable key for no-doc_id chunks (they used to vanish from kb-health) ───

class StableChunkKey(unittest.TestCase):
    def test_no_id_chunk_gets_stable_distinct_noid_key(self):
        a = Chunk("", "", "Cannabidiol reduces seizures.")
        b = Chunk("", "", "THC increases appetite.")
        self.assertTrue(a.chunk_key.startswith("noid:"))
        self.assertNotEqual(a.chunk_key, b.chunk_key)           # distinct chunks → distinct keys
        self.assertEqual(a.chunk_key, Chunk("", "", "Cannabidiol  reduces seizures.").chunk_key)  # stable (ws-norm)

    def test_doc_id_chunk_key_unchanged(self):
        self.assertEqual(Chunk("d", "S", "x").chunk_key, "d#S")
        self.assertEqual(Chunk("d", "", "x").chunk_key, "d")

    def test_no_id_chunks_are_visible_in_kb_health(self):
        with tempfile.TemporaryDirectory() as d:
            for txt, st in (("CBD reduces seizures.", ce.MISLEADING),
                            ("THC increases appetite.", ce.WEAKLY_CITED)):
                ch = Chunk("", "", txt)
                v = ce.ChunkVerdict(ch.chunk_key, "", "", st, "high", (), None,
                                    False, ce.content_hash(txt))
                cl.record_evaluation(v, store_dir=d, now="t")
            h = cl.kb_health(store_dir=d)
        self.assertEqual(h.total, 2)                            # both visible, not collapsed


# ── #4 ledger compaction: bounded latest-per-chunk + atomic ──────────────────

class LedgerCompaction(unittest.TestCase):
    def _v(self, key, status, h):
        return ce.ChunkVerdict(key, key, "S", status, "high", (), None, False, h)

    def test_repeated_evals_of_one_chunk_stay_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(10):
                cl.record_evaluation(self._v("c1", ce.INCOMPLETE, f"h{i}"),
                                     store_dir=d, now=f"t{i}")
            lines = cl.ledger_path(store_dir=d).read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)                         # compacted, not 10
        self.assertEqual(json.loads(lines[0])["content_hash"], "h9")  # latest kept

    def test_distinct_chunks_each_keep_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(self._v("a", ce.CORRECT, "h"), store_dir=d, now="t")
            cl.record_evaluation(self._v("b", ce.MISLEADING, "h"), store_dir=d, now="t")
            lines = cl.ledger_path(store_dir=d).read_text().strip().splitlines()
        self.assertEqual(len(lines), 2)

    def test_diff_still_works_after_compaction(self):
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(self._v("c1", ce.CORRECT, "h1"), store_dir=d, now="t1")
            diff = cl.record_evaluation(self._v("c1", ce.MISLEADING, "h2"),
                                        store_dir=d, now="t2")
        self.assertEqual(diff.change, cl.REGRESSED)             # prev still read correctly

    def test_preexisting_torn_line_is_dropped_on_next_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = cl.ledger_path(store_dir=d)
            p.parent.mkdir(parents=True, exist_ok=True)
            # a torn/partial line (crash mid-append) followed by a good record
            p.write_text('{"chunk_key": "c1", "status": "correct", "content_hash": "h1"}\n'
                         '{"chunk_key": "c2", "status": "misl', encoding="utf-8")
            cl.record_evaluation(self._v("c3", ce.CORRECT, "h"), store_dir=d, now="t")
            text = p.read_text()
        # every line is now valid JSON (the torn one was compacted away), c1 + c3 kept
        for line in text.strip().splitlines():
            json.loads(line)
        keys = {json.loads(l)["chunk_key"] for l in text.strip().splitlines()}
        self.assertIn("c1", keys)
        self.assertIn("c3", keys)


# ── #5 unguarded abstract fetch no longer crashes the batch ──────────────────

class AbstractFetchGuarded(unittest.TestCase):
    def test_raising_abstract_fn_does_not_crash_accuracy(self):
        from cannavec_science import chunk_audit
        ch = Chunk("d", "S", "CBD inhibits CYP3A4.", citations=("111",))
        def boom(_pmid):
            raise RuntimeError("efetch 500")
        # must not raise — degrades to inconclusive (no flag)
        out = chunk_audit.detect_accuracy_issues(ch, abstract_fn=boom)
        self.assertEqual(out, [])


# ── #6 route-gaps removes stale area JSON when an area's gaps resolve ─────────

class RouteGapsClearsStale(unittest.TestCase):
    def _queue(self, d: Path, *lines):
        p = d / "improve_queue.jsonl"
        p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
        return p

    def _chunk_line(self, query, doc_id, verdict):
        return {"ts": "t", "query": query, "chunk_issues": [
            {"dimension": "accuracy", "verdict": verdict, "doc_id": doc_id,
             "chunk_key": f"{doc_id}#S", "detail": "d", "evidence": "e",
             "recommended_action": "a", "route": "improve_agent"}]}

    def test_resolved_area_json_is_removed_on_next_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "kb"
            (root / "cannabis" / "logs").mkdir(parents=True)
            # run 1: a pharmacology gap → 04-...json written
            q = self._queue(Path(d), self._chunk_line(
                "CBD CYP3A4 receptor mechanism", "cb1_receptor", "contradiction"))
            gr.route_gaps(queue_path=q, kb_root=root, write=True, generated="2026-06-11")
            area_dir = root / "cannabis" / "logs" / "live-gap"
            self.assertTrue(any(area_dir.glob("*.json")))
            before = {p.name for p in area_dir.glob("*.json")}
            # run 2: queue now has only an unrelated FAQ gap → the pharmacology JSON is stale
            q2 = self._queue(Path(d), self._chunk_line(
                "CBD for epilepsy seizures", "epilepsy_faq", "contradiction"))
            gr.route_gaps(queue_path=q2, kb_root=root, write=True, generated="2026-06-11")
            after = {p.name for p in area_dir.glob("*.json")}
        self.assertNotEqual(before, after)
        self.assertNotIn("04-pharmacology-mechanisms.json", after)   # stale one removed


# ── #1 / #3 CLI: degenerate payload is surfaced; empty batch ≠ "not writable" ─

class _Home:
    def __enter__(self):
        self._tmp = tempfile.mkdtemp(prefix="cv_hard_")
        self._saved = os.environ.get("CANNAVEC_HOME")
        os.environ["CANNAVEC_HOME"] = self._tmp
        return Path(self._tmp)

    def __exit__(self, *_a):
        if self._saved is None:
            os.environ.pop("CANNAVEC_HOME", None)
        else:
            os.environ["CANNAVEC_HOME"] = self._saved
        shutil.rmtree(self._tmp, ignore_errors=True)


def _ns(chunks, **kw):
    base = dict(query="cannabis cbd thc", sources=None, chunks=chunks,
                no_discover=False, no_accuracy=True, rigorous=True, no_corpus=True,
                review=False, json=False)
    base.update(kw)
    return argparse.Namespace(**base)


class DegeneratePayloadVisible(unittest.TestCase):
    def test_empty_object_chunk_warns_on_stderr(self):
        with _Home():
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                cli._cmd_audit_mcp(_ns('[{}]'))
        self.assertIn("no doc_id and no text", err.getvalue())

    def test_empty_array_warns_nothing_audited(self):
        with _Home():
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                cli._cmd_audit_mcp(_ns('[]'))
        self.assertIn("no chunks forwarded", err.getvalue())

    def test_empty_array_does_not_falsely_blame_filesystem(self):
        with _Home():
            out = io.StringIO()
            with redirect_stderr(io.StringIO()), redirect_stdout(out):
                cli._cmd_audit_mcp(_ns('[]', json=True))
            data = json.loads(out.getvalue())
        self.assertTrue(data["persisted"])               # empty batch → not a write failure

    def test_real_chunk_no_false_warning(self):
        with _Home():
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                cli._cmd_audit_mcp(_ns(
                    '[{"doc_id":"d","h2_anchor":"S","text":"CBD is a miracle cure.","citations":[]}]'))
        self.assertNotIn("no doc_id", err.getvalue())


if __name__ == "__main__":
    unittest.main()
