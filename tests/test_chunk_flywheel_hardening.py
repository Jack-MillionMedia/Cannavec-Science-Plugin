"""Adversarial edge-case hardening for the chunk-level KB flywheel.

These cases harden ``chunk_audit`` and ``gap_router`` beyond the happy-path
coverage in ``test_chunk_audit.py``, ``test_gap_router.py``, and
``test_route_gaps_cli.py``. They target the genuinely tricky boundaries — malformed
forwarded payloads, dedup, the WEAK/NO_TEXT accuracy verdicts that must NOT flag,
aggregation separation, the unclassified-still-written invariant, fresh-dir
creation, gap-audit-shape validation, and byte-identical determinism.

All offline: the verifier, abstract-fn, and claim-detector are injected; the
queue and kb_root live in ``tempfile`` dirs; nothing touches the network.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cannavec_science import chunk_audit as ca
from cannavec_science import gap_router as gr


def _verifier_from(table):
    """id -> (verdict, reason); default PASS (a real, non-retracted source)."""
    return lambda ident: table.get(ident, ("PASS", "ok"))


# A clean injected environment: every citation verifies PASS, every abstract is
# empty (→ accuracy inconclusive). Overridden per test where the edge needs it.
_CLEAN = {"verifier": _verifier_from({}), "abstract_fn": lambda p: "",
          "check_accuracy": True}


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


# ── chunk_audit: malformed / hostile parsing ─────────────────────────────────

class ChunkParsingHardening(unittest.TestCase):
    def test_citations_as_string_parses_not_iterated_charwise(self):
        # A model-forwarded payload where citations is a bare string must parse to
        # the identifier(s) it names — NOT iterate char-by-char, NOT drop to empty
        # (the latter would misread a cited chunk as uncited). See the precision
        # regression in test_chunk_audit_precision.StringCitations.
        payload = {"id": "d", "content": "text", "citations": "28538134"}
        chunk = ca.Chunk.from_dict(payload)
        self.assertEqual(chunk.citations, ("28538134",))

    def test_citations_as_dict_degrades_to_empty_tuple(self):
        # Arrange
        payload = {"id": "d", "content": "x", "citations": {"pmid": "28538134"}}
        # Act
        chunk = ca.Chunk.from_dict(payload)
        # Assert
        self.assertEqual(chunk.citations, ())

    def test_whitespace_only_text_is_not_a_stub(self):
        # Arrange: text is only whitespace → 0 tokens after split() (not 1..40).
        chunk = ca.Chunk("d", "S", "   \n\t  ")
        # Act
        out = ca.detect_completeness_issues(chunk)
        # Assert: a 0-token chunk is a recall/thin-recall concern, never a stub.
        self.assertEqual(out, [])

    def test_whitespace_only_text_is_clean_through_full_audit(self):
        # Arrange: a whitespace chunk against a neutral query should produce no
        # stub and no crash through the full orchestration path.
        chunk = ca.Chunk("d", "S", "   ")
        # Act
        res = ca.audit_chunks("What is CBD?", [chunk], log=False, **_CLEAN)
        # Assert
        self.assertFalse(any(i.verdict == "thin_stub" for i in res.issues))


# ── chunk_audit: retrieval edge cases ────────────────────────────────────────

class RetrievalHardening(unittest.TestCase):
    def test_all_stopword_query_skips_retrieval_flag(self):
        # Arrange: a query made entirely of stopwords/scaffolding distils to zero
        # discriminating terms → there is no basis to flag a mis-retrieval.
        chunk = ca.Chunk("d", "S", "totally unrelated packaging logistics text")
        # Act
        issue = ca.detect_retrieval_issue("what are the effects of using it", chunk)
        # Assert
        self.assertIsNone(issue)

    def test_all_stopword_query_with_hits_emits_no_thin_recall(self):
        # Arrange: a neutral (all-stopword) query that DID get chunks must not be
        # reported as a coverage gap.
        chunks = [ca.Chunk("d", "S", "off topic but the KB still returned something")]
        # Act
        res = ca.audit_chunks("how does it work", chunks, log=False, **_CLEAN)
        # Assert
        self.assertFalse(any(i.verdict == "thin_recall" for i in res.issues))

    def test_exactly_one_strong_chunk_blocks_thin_recall_but_flags_the_weak(self):
        # Arrange: among three chunks exactly ONE strongly covers the query — the
        # all-weak boundary must be False (no thin_recall) yet each weak chunk is
        # still individually flagged.
        chunks = [
            ca.Chunk("a", "x", "off topic packaging logistics text"),
            ca.Chunk("b", "y", "off topic vaporiser hardware text"),
            ca.Chunk("c", "z", "Cannabidiol eases fibromyalgia pain in a trial."),
        ]
        # Act
        res = ca.audit_chunks("CBD for fibromyalgia pain", chunks, log=False, **_CLEAN)
        # Assert
        self.assertFalse(any(i.verdict == "thin_recall" for i in res.issues))
        self.assertEqual(sum(1 for i in res.issues if i.verdict == "weak_relevance"), 2)


# ── chunk_audit: citation dedup + the cited-claim carve-out ──────────────────

class CitationHardening(unittest.TestCase):
    def test_duplicate_failing_citation_is_flagged_once(self):
        # Arrange: the same fabricated PMID appears twice (with stray whitespace)
        # — dedup must collapse it to a single false_citation issue.
        chunk = ca.Chunk("d", "S", "claim", citations=("99999999", " 99999999 "))
        # Act
        out = ca.detect_citation_issues(
            chunk, verifier=_verifier_from({"99999999": ("FAIL", "not found")}),
            claim_detector=ca.default_clinical_claim)
        # Assert
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].verdict, "false_citation")

    def test_clinical_claim_with_a_passing_citation_is_not_uncited_claim(self):
        # Arrange: a graded clinical chunk that DOES carry a (verified) citation
        # must never trip the uncited-claim hole — having a citation is the cure.
        chunk = ca.Chunk("anx", "Dosing",
                         "CBD 300 mg reduced anxiety effectively in a Phase 3 trial.",
                         citations=("28538134",))
        # Act
        out = ca.detect_citation_issues(
            chunk, verifier=_verifier_from({"28538134": ("PASS", "real")}),
            claim_detector=ca.default_clinical_claim)
        # Assert
        self.assertEqual(out, [])

    def test_uncited_claim_fires_only_when_citations_truly_absent(self):
        # Arrange: a control proving the carve-out above is real — strip the
        # citation and the same clinical chunk now flags uncited_claim.
        chunk = ca.Chunk("anx", "Dosing",
                         "CBD 300 mg reduced anxiety effectively in a Phase 3 trial.",
                         citations=())
        # Act
        out = ca.detect_citation_issues(chunk, verifier=_verifier_from({}),
                                        claim_detector=ca.default_clinical_claim)
        # Assert
        self.assertEqual([i.verdict for i in out], ["uncited_claim"])


# ── chunk_audit: accuracy verdicts that must NOT flag ────────────────────────

class AccuracyHardening(unittest.TestCase):
    def test_weak_support_does_not_flag(self):
        # Arrange: an abstract with only a sliver of overlap → assess_support
        # returns WEAK, which is neither CONTRADICTION nor UNVERIFIED → no issue.
        chunk = ca.Chunk("d", "S", "CBD reduces seizure frequency.", citations=("111",))
        # Act
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: "cbd seizure")
        # Assert
        self.assertEqual(out, [])

    def test_textless_nonempty_abstract_no_text_verdict_does_not_flag(self):
        # Arrange: a non-empty-but-textless abstract (e.g. "...") passes the
        # truthiness gate but yields NO_TEXT from assess_support → must not flag.
        chunk = ca.Chunk("d", "S", "CBD reduces seizure frequency in Dravet syndrome.",
                         citations=("222",))
        # Act
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: "...")
        # Assert
        self.assertEqual(out, [])

    def test_check_accuracy_false_never_calls_abstract_fn(self):
        # Arrange: a chunk with a PMID that WOULD trip the accuracy path; record
        # every abstract_fn call to prove the dimension is genuinely skipped.
        chunk = ca.Chunk("d", "Overview", "CBD reduces Dravet seizures. " * 10,
                         citations=("111",))
        calls = []

        def spy(pmid):
            calls.append(pmid)
            return "Cannabidiol induces CYP3A4."  # would CONTRADICT if reached

        # Act
        res = ca.audit_chunks(
            "CBD Dravet seizures", [chunk], check_accuracy=False, log=False,
            verifier=_verifier_from({"111": ("PASS", "ok")}), abstract_fn=spy)
        # Assert
        self.assertEqual(calls, [])
        self.assertFalse(any(i.dimension == ca.ACCURACY for i in res.issues))


# ── gap_router: aggregation separation + occurrence counting ─────────────────

class AggregationHardening(unittest.TestCase):
    def test_distinct_chunk_keys_same_verdict_aggregate_separately(self):
        # Arrange: two DIFFERENT chunk_keys carrying the same verdict must remain
        # two gaps — the dedup key includes the location, not just the verdict.
        with tempfile.TemporaryDirectory() as d:
            rows = [_chunk_line("CBD epilepsy seizures",
                                _ci("retrieval", "weak_relevance",
                                    doc_id="a", chunk_key="a#S")),
                    _chunk_line("CBD epilepsy seizures",
                                _ci("retrieval", "weak_relevance",
                                    doc_id="b", chunk_key="b#S"))]
            q = _queue(Path(d), rows)
            # Act
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        # Assert
        locations = sorted(g.location for g in res.gaps)
        self.assertEqual(locations, ["a#S", "b#S"])
        self.assertTrue(all(g.occurrences == 1 for g in res.gaps))

    def test_same_chunk_key_verdict_across_three_lines_aggregates_and_boosts(self):
        # Arrange: the identical chunk_key+verdict on three queue lines is ONE gap
        # with occurrences=3, which crosses DEMAND_BOOST_THRESHOLD → severity bumps.
        with tempfile.TemporaryDirectory() as d:
            rows = [_chunk_line(f"CBD epilepsy variant {i}",
                                _ci("retrieval", "weak_relevance",
                                    doc_id="x", chunk_key="x#S")) for i in range(3)]
            q = _queue(Path(d), rows)
            # Act
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        # Assert
        self.assertEqual(len(res.gaps), 1)
        g = res.gaps[0]
        self.assertEqual(g.occurrences, 3)
        self.assertEqual(g.severity, "high")  # boosted from medium

    def test_mixed_source_and_chunk_tier_lines_route_both(self):
        # Arrange: one queue line carries a source-tier false source AND a
        # chunk-tier issue — both tiers must surface as gaps.
        with tempfile.TemporaryDirectory() as d:
            rows = [{"ts": "t", "query": "thc pain",
                     "false_sources": [{"identifier": "999", "reason": "retracted"}],
                     "chunk_issues": [_ci("completeness", "thin_stub",
                                          doc_id="pain", chunk_key="pain#S")]}]
            q = _queue(Path(d), rows)
            # Act
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        # Assert
        dims = {g.dimension for g in res.gaps}
        self.assertIn("source", dims)
        self.assertIn("completeness", dims)


# ── gap_router: unclassified-still-written + render robustness ────────────────

class RoutingHardening(unittest.TestCase):
    def test_unclassified_gap_is_written_not_dropped(self):
        # Arrange: a gap that matches no area keyword and resolves no repo file
        # is 'unclassified' — it must still be written to its own json, never lost.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "kb"
            (root / "cannabis" / "logs").mkdir(parents=True)
            q = _queue(Path(d), [_chunk_line(
                "zzzqqq nonsense", _ci("completeness", "thin_stub",
                                       doc_id="zz", chunk_key="zz#S"))])
            # Act
            res = gr.route_gaps(queue_path=q, kb_root=root, write=True,
                                generated="2026-06-11")
            # Assert (inside the temp-dir scope, before it is torn down)
            self.assertIn("unclassified", res.by_area)
            self.assertTrue((root / "cannabis" / "logs" / "live-gap"
                             / "unclassified.json").exists())

    def test_render_with_only_small_fix_and_no_deep_research_is_valid(self):
        # Arrange: a backlog containing ONLY small-fix items (zero deep_research)
        # must still render a complete, valid document with the empty-tier note.
        with tempfile.TemporaryDirectory() as d:
            q = _queue(Path(d), [_chunk_line(
                "CBD anxiety", _ci("citation", "false_citation",
                                   doc_id="anx", chunk_key="anx#S"))])
            res = gr.route_gaps(queue_path=q, kb_root=Path(d) / "nokb", write=False)
        # Act
        md = gr.render_backlog_md(list(res.gaps), generated="2026-06-11")
        # Assert: the deep-research section exists but reports zero per priority.
        self.assertEqual(res.counts["deep_research"], 0)
        self.assertGreaterEqual(res.counts["small_fix"], 1)
        self.assertIn("Live-Retrieval Gap Backlog", md)
        self.assertIn("Deep-research backlog (prioritized)", md)
        self.assertIn("**P0 = 0**", md)

    def test_write_creates_kb_dirs_when_root_does_not_exist_yet(self):
        # Arrange: kb_root points at a path that does NOT exist — writing must
        # create the directory tree rather than error.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "brand" / "new" / "kb"
            self.assertFalse(root.exists())
            q = _queue(Path(d), [_chunk_line(
                "CBD for Dravet epilepsy seizures",
                _ci("accuracy", "contradiction", doc_id="dravet",
                    chunk_key="dravet#S"))])
            # Act
            res = gr.route_gaps(queue_path=q, kb_root=root, write=True,
                                generated="2026-06-11")
            # Assert (inside the temp-dir scope, before it is torn down)
            self.assertTrue((root / "cannabis" / "logs" / "live-gap").is_dir())
            self.assertTrue((root / "RESEARCH_BACKLOG.live.md").exists())
            self.assertIsNotNone(res.backlog_path)


# ── gap_router: gap-audit schema shape of the live-gap json ──────────────────

class GapAuditShape(unittest.TestCase):
    _REQUIRED = ("title", "kind", "location", "observation", "classification",
                 "severity", "proposedAction")

    def test_written_live_gap_json_is_gap_audit_shaped(self):
        # Arrange: route a real gap and write the per-area json.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "kb"
            (root / "cannabis" / "logs").mkdir(parents=True)
            q = _queue(Path(d), [_chunk_line(
                "CBD for Dravet epilepsy seizures",
                _ci("accuracy", "contradiction", doc_id="dravet",
                    chunk_key="dravet#S"))])
            gr.route_gaps(queue_path=q, kb_root=root, write=True,
                          generated="2026-06-11")
            log_dir = root / "cannabis" / "logs" / "live-gap"
            files = list(log_dir.glob("*.json"))
            self.assertTrue(files)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
        # Act
        gap = payload["gaps"][0]
        # Assert: every gap-audit-required field is present on the gap object.
        for fieldname in self._REQUIRED:
            self.assertIn(fieldname, gap, f"gap json missing '{fieldname}'")
        self.assertIn("severity", gap)
        self.assertIn(gap["severity"], ("high", "medium", "low"))
        self.assertIn(gap["classification"], ("deep_research", "small_fix"))


# ── determinism: byte-identical regeneration with a pinned date ──────────────

class DeterministicRegeneration(unittest.TestCase):
    def test_same_queue_yields_byte_identical_backlog_across_two_runs(self):
        # Arrange: a multi-gap, multi-tier queue routed twice with a fixed
        # generated= date must produce byte-identical RESEARCH_BACKLOG.live.md.
        rows = [
            _chunk_line("CBD for Dravet epilepsy seizures",
                        _ci("accuracy", "contradiction", doc_id="dravet",
                            chunk_key="dravet#S")),
            _chunk_line("THC pain relief dose",
                        _ci("completeness", "thin_stub", doc_id="pain",
                            chunk_key="pain#S")),
            {"ts": "t", "query": "thc pain",
             "false_sources": [{"identifier": "999", "reason": "retracted"}],
             "missing_sources": ["NCT01"]},
        ]
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            root1 = Path(d1) / "kb"
            (root1 / "cannabis" / "logs").mkdir(parents=True)
            root2 = Path(d2) / "kb"
            (root2 / "cannabis" / "logs").mkdir(parents=True)
            q1 = _queue(Path(d1), rows)
            q2 = _queue(Path(d2), rows)
            # Act
            gr.route_gaps(queue_path=q1, kb_root=root1, write=True,
                          generated="2026-06-11")
            gr.route_gaps(queue_path=q2, kb_root=root2, write=True,
                          generated="2026-06-11")
            md1 = (root1 / "RESEARCH_BACKLOG.live.md").read_text(encoding="utf-8")
            md2 = (root2 / "RESEARCH_BACKLOG.live.md").read_text(encoding="utf-8")
        # Assert
        self.assertEqual(md1, md2)


if __name__ == "__main__":
    unittest.main()
