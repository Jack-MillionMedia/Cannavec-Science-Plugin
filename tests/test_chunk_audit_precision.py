"""Precision regressions for the chunk flywheel — guards against the false-flag
bugs the adversarial review surfaced. The flywheel feeds a curated research
backlog, so an on-topic, well-cited chunk must NOT manufacture a coverage/citation
gap (over-flagging erodes operator trust and violates the detector's promised
conservatism). All offline."""

from __future__ import annotations

import unittest

from cannavec_science import chunk_audit as ca


class RetrievalMorphology(unittest.TestCase):
    """Plural/singular mismatch must not flag an on-topic chunk as a mis-retrieval."""

    def test_plural_query_matches_singular_chunk(self):
        # query 'seizures'; chunk says 'seizure frequency' — same topic.
        chunk = ca.Chunk("d", "S",
                         "Cannabidiol reduces seizure frequency in Dravet epilepsy.")
        self.assertIsNone(ca.detect_retrieval_issue("CBD epilepsy seizures", chunk))

    def test_singular_query_matches_plural_chunk(self):
        chunk = ca.Chunk("d", "S", "Cannabidiol reduces seizures in epilepsy.")
        self.assertIsNone(ca.detect_retrieval_issue("CBD epilepsy seizure", chunk))

    def test_genuinely_off_topic_still_flags(self):
        # the fix must not blunt true mis-retrieval detection.
        chunk = ca.Chunk("hw", "S", "Vaporiser hardware temperature calibration guide.")
        self.assertIsNotNone(ca.detect_retrieval_issue("CBD breast cancer tumour", chunk))


class StringCitations(unittest.TestCase):
    """A model that forwards citations as a delimited string must parse the same
    as the list form — else a cited clinical chunk is misread as uncited."""

    def test_string_citations_parse_like_list(self):
        as_list = ca.Chunk.from_dict({"doc_id": "d", "citations": ["28538134", "10.1/x"]})
        as_str = ca.Chunk.from_dict({"doc_id": "d", "citations": "28538134, 10.1/x"})
        self.assertEqual(as_str.citations, as_list.citations)

    def test_cited_clinical_chunk_via_string_is_not_uncited(self):
        chunk = ca.Chunk.from_dict({
            "doc_id": "anx", "h2_anchor": "Dosing",
            "text": "CBD 300 mg reduced anxiety effectively in a Phase 3 trial.",
            "citations": "PMID:28538134"})
        out = ca.detect_citation_issues(
            chunk, verifier=lambda i: ("PASS", "ok"),
            claim_detector=ca.default_clinical_claim)
        self.assertEqual(out, [])              # it HAS a citation → no uncited_claim


class NeutralZeroChunk(unittest.TestCase):
    """A neutral query (no discriminating terms) gives no basis to assert a
    coverage gap, regardless of hit count."""

    def test_neutral_query_zero_chunks_no_thin_recall(self):
        res = ca.audit_chunks("What is cannabis?", [], log=False,
                              verifier=lambda i: ("PASS", "ok"),
                              abstract_fn=lambda p: "")
        self.assertFalse(any(i.verdict == "thin_recall" for i in res.issues))

    def test_real_query_zero_chunks_still_thin_recall(self):
        res = ca.audit_chunks("CBD for lupus nephritis", [], log=False,
                              verifier=lambda i: ("PASS", "ok"),
                              abstract_fn=lambda p: "")
        self.assertTrue(any(i.verdict == "thin_recall" for i in res.issues))


class MultiCitationAccuracyNoise(unittest.TestCase):
    """For a multi-citation chunk, an unrelated-but-correct citation must not be
    flagged 'unverified' against the lead claim (review-queue noise). A direct
    contradiction is still surfaced regardless of citation count."""

    def test_multi_citation_unverified_is_suppressed(self):
        chunk = ca.Chunk("d", "S",
                         "CBD reduces seizure frequency in Dravet syndrome.",
                         citations=("111", "222"))
        # 222's abstract is about an unrelated topic → would be 'unverified' for the lead
        def abstract(pmid):
            return ("Cannabidiol reduced seizure frequency in Dravet syndrome."
                    if pmid == "111" else "A study of tomato ripening enzymes.")
        out = ca.detect_accuracy_issues(chunk, abstract_fn=abstract)
        self.assertFalse(any(i.verdict == "unverified" for i in out))

    def test_single_citation_unverified_still_flags(self):
        chunk = ca.Chunk("d", "S", "CBG lowers intraocular pressure.", citations=("999",))
        out = ca.detect_accuracy_issues(
            chunk, abstract_fn=lambda p: "A study of tomato ripening enzymes.")
        self.assertTrue(any(i.verdict == "unverified" for i in out))

    def test_multi_citation_contradiction_still_flags(self):
        chunk = ca.Chunk("d", "S", "CBD induces CYP3A4 activity.",
                         citations=("111", "222"))
        def abstract(pmid):
            return ("Cannabidiol inhibits CYP3A4 in human liver microsomes."
                    if pmid == "111" else "Unrelated.")
        out = ca.detect_accuracy_issues(chunk, abstract_fn=abstract)
        self.assertTrue(any(i.verdict == "contradiction" for i in out))


if __name__ == "__main__":
    unittest.main()
