"""Route captured live-retrieval gaps into the mc-knowledge-base research backlog.
Deterministic + offline: reads a temp improve-queue, writes a temp kb-root. Pins
the Agent-Boundary invariants (never authors clinical text; never touches the
curated RESEARCH_BACKLOG.md) and the priority/demand-boost logic."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cannavec_science import gap_router as gr


def _queue(d: Path, rows) -> Path:
    p = d / "improve_queue.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def _chunk_line(query, *issues):
    return {"ts": "2026-06-11T00:00:00+00:00", "query": query,
            "chunk_issues": list(issues)}


def _ci(dimension, verdict, doc_id="", chunk_key="", detail="d", action="a"):
    return {"dimension": dimension, "verdict": verdict, "doc_id": doc_id,
            "chunk_key": chunk_key or doc_id, "detail": detail,
            "recommended_action": action, "route": "deeper_research"}


# ── area mapping ─────────────────────────────────────────────────────────────

class AreaMapping(unittest.TestCase):
    def test_keyword_routes_clinical_query(self):
        self.assertEqual(gr.area_for("", "CBD for epilepsy seizures"), "faq-clinical")

    def test_keyword_routes_pharmacology(self):
        self.assertEqual(gr.area_for("cb1_receptor", "CB1 receptor binding mechanism"),
                         "04-pharmacology-mechanisms")

    def test_keyword_routes_legal(self):
        self.assertEqual(gr.area_for("", "cannabis scheduling law in Germany"),
                         "faq-legal-products")

    def test_unmatched_is_unclassified_not_dropped(self):
        self.assertEqual(gr.area_for("", "zzzqqq nonsense"), "unclassified")

    def test_repo_file_resolution_beats_keywords(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            doc = root / "cannabis" / "4. Pharmacology & Mechanisms" / "cb1_receptor.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# CB1\n", encoding="utf-8")
            # query keywords say 'legal', but the resolved file says pharmacology
            area = gr.area_for("cb1_receptor", "is this legal", kb_root=root)
        self.assertEqual(area, "04-pharmacology-mechanisms")

    def test_faq_cluster_path_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            doc = root / "cannabis-faq" / "costs_and_access" / "how_much.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# cost\n", encoding="utf-8")
            self.assertEqual(gr.area_for("how_much", "anything", kb_root=root),
                             "faq-access")


# ── priority + demand boost ──────────────────────────────────────────────────

class PriorityAndDemand(unittest.TestCase):
    def test_high_clinical_deep_research_is_p0(self):
        with tempfile.TemporaryDirectory() as d:
            q = _queue(Path(d), [_chunk_line(
                "CBD for Dravet epilepsy seizures",
                _ci("accuracy", "contradiction", doc_id="dravet"))])
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        g = res.gaps[0]
        self.assertEqual(g.classification, "deep_research")
        self.assertEqual(g.priority, "P0")

    def test_demand_boost_bumps_severity_band(self):
        # a weak_relevance gap is base 'medium' (→P2); seen 3× → 'high' (→P1/P0)
        with tempfile.TemporaryDirectory() as d:
            rows = [_chunk_line("CBD epilepsy seizures",
                                _ci("retrieval", "weak_relevance",
                                    doc_id="x", chunk_key="x#S")) for _ in range(3)]
            q = _queue(Path(d), rows)
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        g = res.gaps[0]
        self.assertEqual(g.occurrences, 3)
        self.assertEqual(g.severity, "high")          # boosted from medium
        self.assertIn(g.priority, ("P0", "P1"))

    def test_single_occurrence_not_boosted(self):
        with tempfile.TemporaryDirectory() as d:
            q = _queue(Path(d), [_chunk_line("history of hemp rope",
                                             _ci("completeness", "thin_stub",
                                                 doc_id="hemp"))])
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        g = res.gaps[0]
        self.assertEqual(g.occurrences, 1)
        self.assertEqual(g.severity, "low")           # non-clinical thin_stub
        self.assertEqual(g.priority, "P3")

    def test_false_citation_is_small_fix_no_priority(self):
        with tempfile.TemporaryDirectory() as d:
            q = _queue(Path(d), [_chunk_line("CBD anxiety",
                                             _ci("citation", "false_citation",
                                                 doc_id="anx"))])
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        g = res.gaps[0]
        self.assertEqual(g.classification, "small_fix")
        self.assertIsNone(g.priority)


# ── identifier tier ──────────────────────────────────────────────────────────

class IdentifierTier(unittest.TestCase):
    def test_missing_and_false_sources_become_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [{"ts": "t", "query": "thc pain",
                     "false_sources": [{"identifier": "999", "reason": "retracted"}],
                     "missing_sources": ["NCT01", "NCT01"]}]
            q = _queue(Path(d), rows)
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        verdicts = {g.dimension + ":" + g.location for g in res.gaps}
        self.assertIn("source:999", verdicts)
        self.assertIn("source:NCT01", verdicts)
        nct = next(g for g in res.gaps if g.location == "NCT01")
        self.assertEqual(nct.occurrences, 2)          # aggregated across the line


# ── writing + safety invariants ──────────────────────────────────────────────

class WritingAndSafety(unittest.TestCase):
    def _seed_kb(self, root: Path):
        (root / "cannabis" / "logs").mkdir(parents=True, exist_ok=True)
        curated = root / "RESEARCH_BACKLOG.md"
        curated.write_text("# HAND CURATED — do not touch\n", encoding="utf-8")
        return curated

    def test_writes_json_and_regenerable_backlog(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "kb"
            root.mkdir()
            self._seed_kb(root)
            q = _queue(Path(d), [_chunk_line(
                "CBD for Dravet epilepsy seizures",
                _ci("accuracy", "contradiction", doc_id="dravet"))])
            res = gr.route_gaps(queue_path=q, kb_root=root, write=True,
                                generated="2026-06-11")
            live = root / "RESEARCH_BACKLOG.live.md"
            self.assertTrue(live.exists())
            self.assertIn("Live-Retrieval Gap Backlog", live.read_text())
            jpath = root / "cannabis" / "logs" / "live-gap"
            self.assertTrue(any(jpath.glob("*.json")))
            self.assertIsNotNone(res.backlog_path)

    def test_never_touches_curated_backlog(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "kb"
            root.mkdir()
            curated = self._seed_kb(root)
            before = curated.read_text()
            q = _queue(Path(d), [_chunk_line("CBD epilepsy",
                                             _ci("citation", "false_citation",
                                                 doc_id="anx"))])
            gr.route_gaps(queue_path=q, kb_root=root, write=True)
            self.assertEqual(curated.read_text(), before)   # byte-identical

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "kb"
            root.mkdir()
            q = _queue(Path(d), [_chunk_line("CBD epilepsy",
                                             _ci("completeness", "thin_stub",
                                                 doc_id="x"))])
            res = gr.route_gaps(queue_path=q, kb_root=root, write=False)
            self.assertEqual(res.files_written, ())
            self.assertFalse((root / "RESEARCH_BACKLOG.live.md").exists())
            self.assertFalse((root / "cannabis" / "logs" / "live-gap").exists())
            self.assertGreater(res.counts["total"], 0)      # plan still computed

    def test_render_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            q = _queue(Path(d), [
                _chunk_line("CBD epilepsy seizures",
                            _ci("accuracy", "contradiction", doc_id="a")),
                _chunk_line("THC pain relief dose",
                            _ci("completeness", "thin_stub", doc_id="b")),
            ])
            r1 = gr.route_gaps(queue_path=q, kb_root=Path(d) / "x", write=False)
            r2 = gr.route_gaps(queue_path=q, kb_root=Path(d) / "x", write=False)
        md1 = gr.render_backlog_md(list(r1.gaps), generated="2026-06-11")
        md2 = gr.render_backlog_md(list(r2.gaps), generated="2026-06-11")
        self.assertEqual(md1, md2)

    def test_missing_queue_is_empty_plan_not_error(self):
        with tempfile.TemporaryDirectory() as d:
            res = gr.route_gaps(queue_path=Path(d) / "nope.jsonl",
                                kb_root=Path(d), write=True)
        self.assertEqual(res.counts["total"], 0)
        self.assertEqual(res.files_written, ())

    def test_to_dict_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as d:
            q = _queue(Path(d), [_chunk_line("CBD epilepsy",
                                             _ci("citation", "uncited_claim",
                                                 doc_id="anx"))])
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "x", write=False)
            blob = json.dumps(res.to_dict())            # must serialize
        self.assertIn("counts", json.loads(blob))


if __name__ == "__main__":
    unittest.main()
