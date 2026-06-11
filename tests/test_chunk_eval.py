"""Rigorous chunk evaluation: compose the full rigor stack + a claim-vs-corpus
comparison into a single per-chunk verdict (correct / incomplete / outdated /
weakly_cited / misleading / needs_improvement). Deterministic + offline — corpus,
abstracts, verifier, and the model backend are all injected. The cardinal guard:
a false `misleading` on a correct chunk is the worst error, so corpus contradiction
must clear a strong bar."""

from __future__ import annotations

import datetime
import unittest

from cannavec_science import chunk_eval as ce
from cannavec_science.chunk_audit import Chunk


class _Verdict:
    def __init__(self, name): self.verdict = type("V", (), {"name": name})()


def _verify(table):
    return lambda ident, id_type: _Verdict(table.get(ident, "MATCH"))


def _retracted(ids):
    return lambda **kw: ("registry hit" if next(iter(kw.values())) in ids else None)


def _src(ident, year, tier, level=3, has_abstract=True):
    return ce.CorpusSource(ident, year, tier, level, has_abstract)


# ── prose rigor aggregation ──────────────────────────────────────────────────

class ProseRigor(unittest.TestCase):
    def test_cure_claim_is_misleading(self):
        ch = Chunk("d", "S", "CBD is a miracle cure that is 100% effective for all epilepsy.")
        issues = ce.detect_prose_rigor_issues(ch)
        self.assertTrue(any(i.verdict == "banned_misleading" for i in issues))

    def test_cherry_picked_is_weakly_cited(self):
        ch = Chunk("d", "S", "Studies show CBD reduces anxiety in everyone.")
        issues = ce.detect_prose_rigor_issues(ch)
        self.assertTrue(any(i.verdict == "cherry_picked" for i in issues))

    def test_clean_prose_has_no_rigor_issues(self):
        ch = Chunk("d", "S", "Cannabidiol may reduce seizure frequency; preliminary "
                             "evidence suggests a benefit in Dravet syndrome.")
        self.assertEqual(ce.detect_prose_rigor_issues(ch), [])

    def test_empty_text_is_clean(self):
        self.assertEqual(ce.detect_prose_rigor_issues(Chunk("d", "S", "")), [])


# ── finer citation gate ──────────────────────────────────────────────────────

class CitationFine(unittest.TestCase):
    def test_retracted_vs_fabricated_vs_misattributed(self):
        ch = Chunk("d", "S", "claim", citations=("111", "222", "333"))
        issues = ce.detect_citation_issues_fine(
            ch, verifier=_verify({"222": "NOT_FOUND", "333": "MISMATCH"}),
            retraction_fn=_retracted({"111"}))
        verdicts = {i.verdict for i in issues}
        self.assertEqual(verdicts, {"retracted_citation", "fabricated_citation",
                                    "misattributed_citation"})

    def test_clean_citation_no_issue(self):
        ch = Chunk("d", "S", "claim", citations=("999",))
        issues = ce.detect_citation_issues_fine(
            ch, verifier=_verify({"999": "MATCH"}), retraction_fn=_retracted(set()))
        self.assertEqual(issues, [])

    def test_uncited_clinical_claim(self):
        ch = Chunk("d", "S", "CBD 300 mg reduced anxiety effectively.", citations=())
        issues = ce.detect_citation_issues_fine(
            ch, verifier=_verify({}), retraction_fn=_retracted(set()))
        self.assertTrue(any(i.verdict == "uncited_claim" for i in issues))


# ── claim vs corpus ──────────────────────────────────────────────────────────

class CorpusComparison(unittest.TestCase):
    def test_missing_high_tier_evidence_is_incomplete(self):
        ch = Chunk("d", "S", "Cannabidiol reduces seizures.", citations=())
        corpus = [_src("28538134", 2017, tier=1), _src("29768152", 2018, tier=2)]
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD epilepsy seizures", corpus_fn=lambda t: corpus)
        self.assertTrue(any(i.verdict == "missing_evidence" for i in issues))

    def test_strong_claim_weak_citation_is_under_cited(self):
        # clinical claim, cites only a weak-tier source while corpus has SR/RCT
        ch = Chunk("d", "S", "CBD treats epilepsy effectively.", citations=("low1",))
        corpus = [_src("low1", 2015, tier=4), _src("sr1", 2020, tier=1)]
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        self.assertTrue(any(i.verdict == "under_cited" for i in issues))

    def test_newer_evidence_is_superseded(self):
        ch = Chunk("d", "S", "CBD reduces seizures.", citations=("old",))
        corpus = [_src("old", 2014, tier=1), _src("new", 2024, tier=1)]
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        self.assertTrue(any(i.verdict == "superseded" for i in issues))

    def test_corpus_contradiction_clears_high_bar(self):
        ch = Chunk("d", "S", "CBD induces CYP3A4 activity.", citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        # every credible source asserts the opposite direction
        abstracts = {"a": "Cannabidiol inhibits CYP3A4.",
                     "b": "CBD inhibits CYP3A4 strongly.",
                     "c": "Cannabidiol is a CYP3A4 inhibitor."}
        issues, corr = ce.detect_corpus_issues(
            ch, "CBD CYP3A4", corpus_fn=lambda t: corpus,
            abstract_fn=lambda i: abstracts.get(i, ""))
        self.assertTrue(any(i.verdict == "corpus_contradiction" for i in issues))
        self.assertEqual(corr.contradicted, 3)

    def test_below_bar_does_not_flag_misleading(self):
        # 3 checked, only 2 contradict → below the 100%-at-n=3 bar → NO misleading
        ch = Chunk("d", "S", "CBD induces CYP3A4 activity.", citations=("a", "b", "c"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1)]
        abstracts = {"a": "Cannabidiol inhibits CYP3A4.",
                     "b": "CBD inhibits CYP3A4.",
                     "c": "Cannabidiol induces CYP3A4."}     # this one agrees
        issues, corr = ce.detect_corpus_issues(
            ch, "CBD CYP3A4", corpus_fn=lambda t: corpus,
            abstract_fn=lambda i: abstracts.get(i, ""))
        self.assertFalse(any(i.verdict == "corpus_contradiction" for i in issues))
        self.assertEqual((corr.contradicted, corr.supported), (2, 1))

    def test_empty_corpus_is_silent(self):
        ch = Chunk("d", "S", "CBD reduces seizures.", citations=())
        issues, corr = ce.detect_corpus_issues(ch, "q", corpus_fn=lambda t: [])
        self.assertEqual(issues, [])
        self.assertIsNone(corr)


# ── freshness (outdated) ─────────────────────────────────────────────────────

class Freshness(unittest.TestCase):
    def test_stale_past_horizon(self):
        ch = Chunk("d", "S", "text")
        meta = {"last_verified_at": "2024-01-01", "decay_horizon_days": 365}
        issues = ce.detect_freshness_issue(ch, meta=meta,
                                           now=datetime.date(2026, 6, 11))
        self.assertTrue(any(i.verdict == "stale" for i in issues))

    def test_fresh_within_horizon(self):
        ch = Chunk("d", "S", "text")
        meta = {"last_verified_at": "2026-06-01", "decay_horizon_days": 365}
        self.assertEqual(ce.detect_freshness_issue(ch, meta=meta,
                                                   now=datetime.date(2026, 6, 11)), [])

    def test_freshness_class_fallback_horizon(self):
        ch = Chunk("d", "S", "text")
        meta = {"last_verified_at": "2026-01-01", "freshness_class": "legal_volatile"}
        # legal_volatile → 30 days; >30d since Jan 1 → stale
        issues = ce.detect_freshness_issue(ch, meta=meta,
                                           now=datetime.date(2026, 6, 11))
        self.assertTrue(any(i.verdict == "stale" for i in issues))

    def test_decay_breach_count_is_stale(self):
        ch = Chunk("d", "S", "text")
        issues = ce.detect_freshness_issue(ch, meta={"decay_breach_count": 2},
                                           now=datetime.date(2026, 6, 11))
        self.assertTrue(issues)

    def test_no_meta_no_freshness_signal(self):
        self.assertEqual(ce.detect_freshness_issue(Chunk("d", "S", "t"), meta=None), [])


# ── rollup + evaluate_chunk ──────────────────────────────────────────────────

class Rollup(unittest.TestCase):
    def test_misleading_beats_everything(self):
        ch = Chunk("d", "S", "CBD is a miracle cure. " * 20)
        v = ce.evaluate_chunk(ch, "CBD epilepsy", verifier=_verify({}),
                              retraction_fn=_retracted(set()))
        self.assertEqual(v.status, ce.MISLEADING)

    def test_clean_offline_chunk_is_unevaluated_not_correct(self):
        # no issues, but no corpus check ran → we do NOT claim correctness.
        ch = Chunk("d", "S", "Cannabidiol may reduce seizure frequency in Dravet "
                             "syndrome epilepsy according to preliminary evidence. " * 4,
                   citations=("28538134",))
        v = ce.evaluate_chunk(ch, "CBD Dravet seizures",
                              verifier=_verify({"28538134": "MATCH"}),
                              retraction_fn=_retracted(set()))
        self.assertEqual(v.status, ce.UNEVALUATED)

    def test_corroborated_chunk_is_correct(self):
        ch = Chunk("d", "S", "Cannabidiol reduces seizure frequency in Dravet syndrome "
                             "epilepsy across controlled studies of treatment-resistant "
                             "paediatric patients. " * 4, citations=("111", "222"))
        corpus = [_src("111", 2017, 1), _src("222", 2018, 1)]
        abstracts = {"111": "Cannabidiol reduced seizure frequency in Dravet syndrome.",
                     "222": "CBD reduced seizure frequency in Dravet."}
        v = ce.evaluate_chunk(
            ch, "CBD Dravet seizures", corpus_fn=lambda t: corpus,
            abstract_fn=lambda i: abstracts.get(i, ""),
            verifier=_verify({"111": "MATCH", "222": "MATCH"}),
            retraction_fn=_retracted(set()))
        self.assertEqual(v.status, ce.CORRECT)
        self.assertTrue(v.evidence_checked)

    def test_outdated_from_freshness(self):
        ch = Chunk("d", "S", "Cannabidiol may reduce seizures. " * 8, citations=("28538134",))
        v = ce.evaluate_chunk(
            ch, "CBD seizures", verifier=_verify({"28538134": "MATCH"}),
            retraction_fn=_retracted(set()),
            meta={"last_verified_at": "2020-01-01", "decay_horizon_days": 365},
            now=datetime.date(2026, 6, 11))
        self.assertEqual(v.status, ce.OUTDATED)

    def test_content_hash_changes_with_text(self):
        self.assertNotEqual(ce.content_hash("abc"), ce.content_hash("abd"))
        self.assertEqual(ce.content_hash("a b"), ce.content_hash("a  b"))  # ws-normalized


# ── cross-chunk coherence ────────────────────────────────────────────────────

class Coherence(unittest.TestCase):
    def test_opposite_direction_siblings_conflict(self):
        a = Chunk("a", "S", "CBD inhibits CYP3A4 in the liver.")
        b = Chunk("b", "S", "CBD induces CYP3A4 activity.")
        issues = ce.detect_coherence_issues([a, b])
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i.verdict == "coherence_conflict" for i in issues))

    def test_same_direction_siblings_are_fine(self):
        a = Chunk("a", "S", "CBD inhibits CYP3A4.")
        b = Chunk("b", "S", "CBD inhibits CYP3A4 strongly.")
        self.assertEqual(ce.detect_coherence_issues([a, b]), [])

    def test_evaluate_chunks_merges_coherence(self):
        a = Chunk("a", "S", "CBD inhibits CYP2C9 metabolism.")
        b = Chunk("b", "S", "CBD induces CYP2C9 metabolism.")
        verdicts = ce.evaluate_chunks(
            "CBD CYP2C9", [a, b], verifier=_verify({}), retraction_fn=_retracted(set()))
        self.assertTrue(any(
            any(i.verdict == "coherence_conflict" for i in v.issues) for v in verdicts))


if __name__ == "__main__":
    unittest.main()
