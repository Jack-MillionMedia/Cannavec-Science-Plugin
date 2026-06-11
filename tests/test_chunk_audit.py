"""The chunk-level KB flywheel: every chunk the live Cannavec MCP returns is
judged for retrieval / citation / accuracy / completeness problems, each keyed to
the chunk and appended to the one operator improve-queue so real usage grows the
KB. The audit LOGIC is deterministic and offline — verifier, abstract-fn, and
claim-detector are injected here, no network."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cannavec_science import chunk_audit as ca
from cannavec_science import source_audit as sa


def _verifier_from(table):
    """id -> (verdict, reason); default PASS (a real, non-retracted source)."""
    return lambda ident: table.get(ident, ("PASS", "ok"))


_CLEAN = {"verifier": _verifier_from({}), "abstract_fn": lambda p: "",
          "check_accuracy": True}


# ── Chunk parsing ────────────────────────────────────────────────────────────

class ChunkParsing(unittest.TestCase):
    def test_from_dict_accepts_aliases_and_chunk_key(self):
        c = ca.Chunk.from_dict({"id": "cbd_epilepsy", "heading": "Overview",
                                "content": "text here", "identifiers": ["28538134"],
                                "score": "0.81"})
        self.assertEqual(c.doc_id, "cbd_epilepsy")
        self.assertEqual(c.h2_anchor, "Overview")
        self.assertEqual(c.citations, ("28538134",))
        self.assertEqual(c.score, 0.81)
        self.assertEqual(c.chunk_key, "cbd_epilepsy#Overview")

    def test_chunk_key_without_anchor_is_doc_id(self):
        self.assertEqual(ca.Chunk(doc_id="d").chunk_key, "d")

    def test_garbage_dict_degrades_not_crashes(self):
        c = ca.Chunk.from_dict({"score": "not-a-number"})
        self.assertEqual(c.doc_id, "")
        self.assertIsNone(c.score)


# ── retrieval ────────────────────────────────────────────────────────────────

class RetrievalRelevance(unittest.TestCase):
    def test_on_topic_chunk_is_clean(self):
        chunk = ca.Chunk("d", "Overview",
                         "Cannabidiol reduces seizure frequency in Dravet syndrome epilepsy.")
        self.assertIsNone(ca.detect_retrieval_issue("CBD for Dravet epilepsy seizures", chunk))

    def test_off_topic_chunk_flags_weak_relevance(self):
        # query is about breast cancer; chunk is a drug-interaction row → misses
        # the discriminating terms.
        chunk = ca.Chunk("ddi", "Interactions",
                         "CBD inhibits CYP3A4 and may raise warfarin INR; monitor closely.")
        issue = ca.detect_retrieval_issue("CBD for breast cancer tumour", chunk)
        self.assertIsNotNone(issue)
        self.assertEqual(issue.dimension, ca.RETRIEVAL)
        self.assertEqual(issue.verdict, "weak_relevance")
        self.assertEqual(issue.route, ca.ROUTE_RESEARCH)

    def test_neutral_query_is_not_flagged(self):
        # "what is cbd" reduces to no discriminating terms → no basis to flag.
        chunk = ca.Chunk("d", "Overview", "Cannabidiol is a phytocannabinoid.")
        self.assertIsNone(ca.detect_retrieval_issue("What is CBD?", chunk))


class ThinRecall(unittest.TestCase):
    def test_zero_chunks_for_a_real_query_is_thin_recall(self):
        res = ca.audit_chunks("CBD for lupus nephritis", [], log=False, **_CLEAN)
        kinds = [(i.dimension, i.verdict) for i in res.issues]
        self.assertIn((ca.RETRIEVAL, "thin_recall"), kinds)

    def test_all_weak_chunks_emit_a_query_level_gap(self):
        chunks = [ca.Chunk("a", "x", "totally unrelated text about hardware vaporisers"),
                  ca.Chunk("b", "y", "more unrelated text about packaging logistics")]
        res = ca.audit_chunks("CBD for fibromyalgia pain", chunks, log=False, **_CLEAN)
        self.assertTrue(any(i.verdict == "thin_recall" for i in res.issues))

    def test_one_strong_chunk_prevents_thin_recall(self):
        chunks = [ca.Chunk("a", "x", "off topic packaging text"),
                  ca.Chunk("b", "y", "Cannabidiol eases fibromyalgia pain in a trial.")]
        res = ca.audit_chunks("CBD for fibromyalgia pain", chunks, log=False, **_CLEAN)
        self.assertFalse(any(i.verdict == "thin_recall" for i in res.issues))


# ── citation ─────────────────────────────────────────────────────────────────

class CitationGate(unittest.TestCase):
    def test_real_citation_is_clean(self):
        chunk = ca.Chunk("d", "S", "CBD reduces seizures.", citations=("28538134",))
        out = ca.detect_citation_issues(
            chunk, verifier=_verifier_from({"28538134": ("PASS", "real")}),
            claim_detector=ca.default_clinical_claim)
        self.assertEqual(out, [])

    def test_fabricated_and_retracted_flag_false_citation(self):
        chunk = ca.Chunk("d", "S", "claim", citations=("99999999", "10.1/x"))
        table = {"99999999": ("FAIL", "not found upstream (fabricated?)"),
                 "10.1/x": ("FAIL", "retracted — never a valid primary citation")}
        out = ca.detect_citation_issues(chunk, verifier=_verifier_from(table),
                                        claim_detector=ca.default_clinical_claim)
        self.assertEqual({i.verdict for i in out}, {"false_citation"})
        self.assertEqual({i.route for i in out}, {ca.ROUTE_IMPROVE})
        self.assertEqual(len(out), 2)

    def test_network_unverified_citation_is_not_flagged(self):
        chunk = ca.Chunk("d", "S", "claim", citations=("123",))
        out = ca.detect_citation_issues(
            chunk, verifier=_verifier_from({"123": ("UNVERIFIED", "net")}),
            claim_detector=ca.default_clinical_claim)
        self.assertEqual(out, [])

    def test_uncited_clinical_claim_is_flagged(self):
        chunk = ca.Chunk("anx", "Dosing",
                         "CBD 300-600 mg reduced anxiety effectively in a Phase 3 trial.",
                         citations=())
        out = ca.detect_citation_issues(chunk, verifier=_verifier_from({}),
                                        claim_detector=ca.default_clinical_claim)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].verdict, "uncited_claim")
        self.assertEqual(out[0].route, ca.ROUTE_RESEARCH)

    def test_non_clinical_uncited_chunk_is_not_flagged(self):
        chunk = ca.Chunk("hist", "Overview",
                         "Cannabis cultivation has a long agricultural history.",
                         citations=())
        out = ca.detect_citation_issues(chunk, verifier=_verifier_from({}),
                                        claim_detector=ca.default_clinical_claim)
        self.assertEqual(out, [])

    def test_default_clinical_claim_cue(self):
        self.assertTrue(ca.default_clinical_claim("CBD treats epilepsy at 10 mg/kg."))
        self.assertTrue(ca.default_clinical_claim("THC 5 mg improved sleep."))
        self.assertFalse(ca.default_clinical_claim("The endocannabinoid system has CB1 receptors."))
        self.assertFalse(ca.default_clinical_claim(""))


# ── accuracy ─────────────────────────────────────────────────────────────────

class AccuracyAgainstAbstract(unittest.TestCase):
    def test_contradiction_flags_deterministically(self):
        chunk = ca.Chunk("ddi", "Interaction",
                         "CBD induces CYP3A4 activity.", citations=("111",))
        # abstract asserts the opposite direction (inhibition)
        abstract = "Cannabidiol (CBD) inhibits CYP3A4 in human liver microsomes."
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: abstract)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].verdict, "contradiction")
        self.assertEqual(out[0].route, ca.ROUTE_IMPROVE)

    def test_unverified_routes_to_model_review(self):
        # the cited abstract never mentions the claim's core entity → ambiguous.
        chunk = ca.Chunk("d", "S", "CBG reduces intraocular pressure.", citations=("222",))
        abstract = "This study examined tomato ripening enzymes."
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: abstract)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].verdict, "unverified")
        self.assertEqual(out[0].route, ca.ROUTE_MODEL)

    def test_supported_claim_is_clean(self):
        chunk = ca.Chunk("d", "S", "CBD reduces seizure frequency.", citations=("333",))
        abstract = "Cannabidiol significantly reduced seizure frequency in Dravet syndrome."
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: abstract)
        self.assertEqual(out, [])

    def test_no_abstract_is_inconclusive_not_a_flag(self):
        chunk = ca.Chunk("d", "S", "CBD reduces seizures.", citations=("444",))
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: "")
        self.assertEqual(out, [])

    def test_doi_citation_is_not_accuracy_checked(self):
        chunk = ca.Chunk("d", "S", "CBD reduces seizures.", citations=("10.1/abc",))
        out = ca.detect_accuracy_issues(chunk, abstract_fn=lambda p: "anything")
        self.assertEqual(out, [])


# ── completeness ─────────────────────────────────────────────────────────────

class Completeness(unittest.TestCase):
    def test_thin_stub_is_flagged(self):
        chunk = ca.Chunk("d", "S", "CBD is a cannabinoid.")
        out = ca.detect_completeness_issues(chunk)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].verdict, "thin_stub")

    def test_substantial_chunk_is_clean(self):
        chunk = ca.Chunk("d", "S", "word " * 80)
        self.assertEqual(ca.detect_completeness_issues(chunk), [])

    def test_grade_inflation_is_flagged_and_human_only(self):
        chunk = ca.Chunk("d", "S", "word " * 80)
        out = ca.detect_completeness_issues(
            chunk, declared_grade="Level A",
            study_counts={"in_vitro": 1})            # supports at most Level D
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].verdict, "grade_inflation")
        self.assertIn("human-only", out[0].recommended_action)

    def test_no_study_counts_means_no_grade_judgement(self):
        chunk = ca.Chunk("d", "S", "word " * 80)
        out = ca.detect_completeness_issues(chunk, declared_grade="Level A",
                                            study_counts={})
        self.assertEqual(out, [])

    def test_empty_chunk_is_not_a_stub(self):
        # an entirely empty chunk has 0 tokens — handled by retrieval/thin-recall,
        # not double-counted as a stub.
        self.assertEqual(ca.detect_completeness_issues(ca.Chunk("d", "S", "")), [])


# ── orchestration + flywheel queue ───────────────────────────────────────────

class AuditChunksAndQueue(unittest.TestCase):
    def test_clean_run_logs_nothing(self):
        chunk = ca.Chunk("d", "Overview",
                         "Cannabidiol reduces Dravet seizure frequency. " * 10,
                         citations=("28538134",))
        with tempfile.TemporaryDirectory() as d:
            res = ca.audit_chunks(
                "CBD Dravet seizures", [chunk],
                verifier=_verifier_from({"28538134": ("PASS", "real")}),
                abstract_fn=lambda p: "Cannabidiol reduced seizure frequency in Dravet.",
                store_dir=d)
        self.assertIsNone(res.logged_path)
        self.assertEqual(res.issues, ())

    def test_dirty_run_appends_one_chunk_issue_line(self):
        chunk = ca.Chunk("anx", "Dosing",
                         "CBD 300 mg reduced anxiety.", citations=("99999999",))
        with tempfile.TemporaryDirectory() as d:
            res = ca.audit_chunks(
                "CBD anxiety dose", [chunk],
                verifier=_verifier_from({"99999999": ("FAIL", "not found")}),
                abstract_fn=lambda p: "", store_dir=d,
                now="2026-06-11T00:00:00+00:00")
            self.assertIsNotNone(res.logged_path)
            lines = Path(res.logged_path).read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["query"], "CBD anxiety dose")
            self.assertEqual(entry["ts"], "2026-06-11T00:00:00+00:00")
            self.assertTrue(entry["chunk_issues"])
            self.assertTrue(any(i["verdict"] == "false_citation"
                                for i in entry["chunk_issues"]))

    def test_by_dimension_counts(self):
        chunks = [
            ca.Chunk("a", "S", "CBD is a cannabinoid.", citations=("28538134",)),  # thin_stub
            ca.Chunk("b", "S", "unrelated hardware packaging text " * 10),         # weak_relevance
        ]
        res = ca.audit_chunks("CBD epilepsy Dravet seizures", chunks, log=False,
                              verifier=_verifier_from({}), abstract_fn=lambda p: "")
        bd = res.by_dimension()
        self.assertGreaterEqual(bd.get(ca.COMPLETENESS, 0), 1)
        self.assertGreaterEqual(bd.get(ca.RETRIEVAL, 0), 1)

    def test_check_accuracy_false_skips_network_dimension(self):
        chunk = ca.Chunk("d", "Overview", "CBD reduces Dravet seizures. " * 10,
                         citations=("111",))
        calls = []
        res = ca.audit_chunks(
            "CBD Dravet seizures", [chunk], check_accuracy=False, log=False,
            verifier=_verifier_from({"111": ("PASS", "ok")}),
            abstract_fn=lambda p: calls.append(p) or "x")
        self.assertEqual(calls, [])
        self.assertEqual(res.issues, ())


# ── backward-compat: chunk lines coexist with source lines in one queue ───────

class OneQueueTwoTiers(unittest.TestCase):
    def test_summarize_tallies_both_tiers(self):
        with tempfile.TemporaryDirectory() as d:
            # source tier line
            sa.audit_sources("q1", ["999"],
                             verifier=lambda i: ("FAIL", "not found"),
                             discoverer=lambda q: ["777"], store_dir=d,
                             now="2026-06-11T00:00:00+00:00")
            # chunk tier line, same queue
            ca.audit_chunks("q2", [ca.Chunk("anx", "Dosing", "CBD 300 mg cut anxiety.",
                                            citations=("99999999",))],
                            verifier=_verifier_from({"99999999": ("FAIL", "not found")}),
                            abstract_fn=lambda p: "", store_dir=d,
                            now="2026-06-11T00:01:00+00:00")
            s = sa.summarize_improve_queue(store_dir=d)
        self.assertEqual(s.entries, 2)
        self.assertEqual(s.missing_by_id, (("777", 1),))        # source tier intact
        self.assertGreaterEqual(s.chunk_issues, 1)              # chunk tier tallied
        self.assertTrue(any(dim == ca.CITATION for dim, _ in s.chunk_by_dimension))

    def test_source_only_queue_reports_zero_chunk_issues(self):
        with tempfile.TemporaryDirectory() as d:
            sa.audit_sources("q", ["999"], verifier=lambda i: ("FAIL", "x"),
                             discoverer=lambda q: [], store_dir=d)
            s = sa.summarize_improve_queue(store_dir=d)
        self.assertEqual(s.chunk_issues, 0)
        self.assertEqual(s.chunk_by_dimension, ())


if __name__ == "__main__":
    unittest.main()
