"""Regressions for the adversarial-review findings on the rigorous evaluator:
the false-`misleading` vectors (the worst-error class), the now-wired false-positive
suppression, reopen-on-new-evidence noise, fetcher exception-safety, and the
CORRECT-despite-contradiction rollup hole. All offline."""

from __future__ import annotations

import tempfile
import unittest

from cannavec_science import chunk_eval as ce
from cannavec_science import chunk_ledger as cl
from cannavec_science.chunk_audit import Chunk


def _src(ident, year, tier, has_abstract=True):
    return ce.CorpusSource(ident, year, tier, 3, has_abstract)


class _Verdict:
    def __init__(self, name): self.verdict = type("V", (), {"name": name})()


class NegatedDirectionIsNotMisleading(unittest.TestCase):
    """A factually correct chunk phrased with a negated direction must NOT be
    labelled misleading just because claimed_direction first-matches the negated
    verb."""

    def test_negated_claim_with_agreeing_corpus_is_not_misleading(self):
        ch = Chunk("d", "S", "CBD does not increase seizure frequency; rather it "
                             "reduces seizures in Dravet syndrome.", citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        # every source correctly says CBD reduces/decreases seizures
        abstracts = {"a": "Cannabidiol reduced seizure frequency in Dravet.",
                     "b": "CBD decreased seizures markedly.",
                     "c": "Cannabidiol lowered seizure counts."}
        issues, corr = ce.detect_corpus_issues(
            ch, "CBD Dravet seizures", corpus_fn=lambda t: corpus,
            abstract_fn=lambda i: abstracts.get(i, ""))
        self.assertFalse(any(i.verdict == "corpus_contradiction" for i in issues))
        self.assertEqual(corr.contradicted, 0)

    def test_plain_contradiction_still_fires(self):
        # a non-negated wrong claim must still be caught
        ch = Chunk("d", "S", "CBD induces CYP3A4.", citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        abstracts = {k: "Cannabidiol inhibits CYP3A4." for k in ("a", "b", "c")}
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD CYP3A4", corpus_fn=lambda t: corpus,
            abstract_fn=lambda i: abstracts.get(i, ""))
        self.assertTrue(any(i.verdict == "corpus_contradiction" for i in issues))


class CorpusOverFlagTightened(unittest.TestCase):
    def test_under_cited_needs_visible_weak_citations(self):
        # chunk cites a source NOT in this run's corpus → cannot conclude weak → no flag
        ch = Chunk("d", "S", "CBD treats epilepsy effectively.", citations=("not_in_corpus",))
        corpus = [_src("sr1", 2020, 1)]
        issues, _ = ce.detect_corpus_issues(ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        self.assertFalse(any(i.verdict == "under_cited" for i in issues))

    def test_missing_evidence_skipped_when_chunk_cites_a_high_tier(self):
        ch = Chunk("d", "S", "CBD reduces seizures.", citations=("sr1",))
        corpus = [_src("sr1", 2019, 1), _src("sr2", 2020, 1)]   # cites sr1 (tier1)
        issues, _ = ce.detect_corpus_issues(ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        self.assertFalse(any(i.verdict == "missing_evidence" for i in issues))


class FetcherExceptionSafety(unittest.TestCase):
    def test_raising_corpus_fn_yields_no_issues_not_crash(self):
        ch = Chunk("d", "S", "CBD reduces seizures.")
        def boom(_t): raise RuntimeError("upstream down")
        issues, corr = ce.detect_corpus_issues(ch, "q", corpus_fn=boom)
        self.assertEqual(issues, [])
        self.assertIsNone(corr)

    def test_raising_abstract_fn_does_not_abort(self):
        ch = Chunk("d", "S", "CBD induces CYP3A4.", citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        def boom(_i): raise RuntimeError("fetch failed")
        issues, corr = ce.detect_corpus_issues(
            ch, "q", corpus_fn=lambda t: corpus, abstract_fn=boom)
        self.assertEqual(corr.checked, 0)            # no abstract read, but no crash


class CorrectRequiresNoContradiction(unittest.TestCase):
    def test_mixed_corpus_just_under_bar_is_not_correct(self):
        # checked=5, supported=3, contradicted=2 (score 0.6, below misleading bar) →
        # NOT correct (a contradicted source means we can't certify correctness).
        ch = Chunk("d", "S", "CBD reduces seizure frequency in Dravet syndrome epilepsy "
                             "across multiple controlled studies of paediatric patients. " * 3,
                   citations=("a", "b", "c", "d", "e"))
        corpus = [_src(x, 2020, 1) for x in ("a", "b", "c", "d", "e")]
        abstracts = {"a": "Cannabidiol reduced seizures.", "b": "CBD reduced seizures.",
                     "c": "Cannabidiol lowered seizure frequency.",
                     "d": "CBD increased seizures.", "e": "Cannabidiol increased seizures."}
        v = ce.evaluate_chunk(
            ch, "CBD Dravet seizures", corpus_fn=lambda t: corpus,
            abstract_fn=lambda i: abstracts.get(i, ""),
            verifier=lambda ident, idt: type("V", (), {"verdict": type("X", (), {"name": "MATCH"})()})(),
            retraction_fn=lambda **k: None)
        self.assertNotEqual(v.status, ce.CORRECT)


class OffTopicChunkSkipsBatchCorpus(unittest.TestCase):
    """The corpus is assembled ONCE from the batch query; a chunk that is OFF-topic
    for that query must NOT be judged against it — that manufactured a live false
    MISLEADING on a TRUE seizure chunk evaluated under a CYP3A4/clobazam query."""

    def _verify_match(self, ident, id_type):
        return _Verdict("MATCH")

    def test_off_topic_chunk_not_misleading_against_query_corpus(self):
        ch = Chunk("d", "S", "CBD reduces seizure frequency in Dravet syndrome.",
                   citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        abstracts = {k: "Cannabidiol inhibits CYP3A4 in liver microsomes." for k in "abc"}
        v = ce.evaluate_chunk(
            ch, "Does CBD inhibit CYP3A4 and interact with clobazam?",
            corpus_fn=lambda t: corpus, abstract_fn=lambda i: abstracts.get(i, ""),
            verifier=self._verify_match, retraction_fn=lambda **k: None)
        self.assertNotEqual(v.status, ce.MISLEADING)
        self.assertFalse(v.evidence_checked)        # corpus skipped (chunk off-topic)

    def test_on_topic_chunk_still_corpus_checked(self):
        ch = Chunk("d", "S", "CBD inhibits CYP3A4 and interacts with clobazam "
                             "metabolism in the liver.", citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        abstracts = {k: "Cannabidiol inhibits CYP3A4." for k in "abc"}
        v = ce.evaluate_chunk(
            ch, "Does CBD inhibit CYP3A4 and interact with clobazam?",
            corpus_fn=lambda t: corpus, abstract_fn=lambda i: abstracts.get(i, ""),
            verifier=self._verify_match, retraction_fn=lambda **k: None)
        self.assertTrue(v.evidence_checked)          # on-topic → corpus ran


class ReopenOnlyOnNewerYear(unittest.TestCase):
    def test_new_id_same_year_does_not_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            v = ce.ChunkVerdict("c1", "c1", "S", ce.CORRECT, "high", (), None, False, "h")
            cl.record_evaluation(v, store_dir=d, now="t1",
                                 evidence_snapshot={"ids": ["a"], "max_year": 2020})
            diff = cl.record_evaluation(
                v, store_dir=d, now="t2",
                evidence_snapshot={"ids": ["a", "b"], "max_year": 2020})  # new id, same year
        self.assertNotEqual(diff.change, cl.REOPENED)

    def test_newer_year_reopens(self):
        with tempfile.TemporaryDirectory() as d:
            v = ce.ChunkVerdict("c1", "c1", "S", ce.CORRECT, "high", (), None, False, "h")
            cl.record_evaluation(v, store_dir=d, now="t1",
                                 evidence_snapshot={"ids": ["a"], "max_year": 2020})
            diff = cl.record_evaluation(v, store_dir=d, now="t2",
                                        evidence_snapshot={"ids": ["a"], "max_year": 2025})
        self.assertEqual(diff.change, cl.REOPENED)


if __name__ == "__main__":
    unittest.main()
