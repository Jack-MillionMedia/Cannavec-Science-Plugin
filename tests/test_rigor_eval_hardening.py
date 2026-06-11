"""Adversarial edge-case hardening for the rigorous chunk evaluator
(:mod:`cannavec_science.chunk_eval`) and the recursive-learning ledger
(:mod:`cannavec_science.chunk_ledger`).

These cases go *beyond* the happy paths in ``test_chunk_eval.py``,
``test_chunk_ledger.py`` and ``test_rigorous_cli.py`` — they pin the exact
arithmetic of the corpus-contradiction bar, the boundary conditions of the
freshness rule, the precedence of the severity rollup, and the precise change
classes the ledger emits. The cardinal invariant under test: a *false*
``misleading`` on a correct chunk is the worst error, so the contradiction bar
must hold its precise threshold and the ledger must never alert on an
``unevaluated`` chunk that merely became flagged.

All deterministic + fully offline: corpus, abstracts, verifier, retraction, and
all stores are injected; nothing touches the network or the user's real home.
"""

from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path

from cannavec_science import chunk_eval as ce
from cannavec_science import chunk_ledger as cl
from cannavec_science.chunk_audit import Chunk


# ── shared offline doubles (mirroring the happy-path fixtures) ────────────────

class _Verdict:
    def __init__(self, name):
        self.verdict = type("V", (), {"name": name})()


def _verify(table):
    return lambda ident, id_type: _Verdict(table.get(ident, "MATCH"))


def _retracted(ids):
    return lambda **kw: ("registry hit" if next(iter(kw.values())) in ids else None)


def _src(ident, year, tier, level=3, has_abstract=True):
    return ce.CorpusSource(ident, year, tier, level, has_abstract)


def _abstracts(table):
    return lambda ident: table.get(ident, "")


def _verdict_rec(chunk_key, status, content_hash="h1", corr=None):
    """A ChunkVerdict double for the ledger (same shape as the ledger happy-path)."""
    return ce.ChunkVerdict(
        chunk_key=chunk_key, doc_id=chunk_key.split("#")[0], h2_anchor="S",
        status=status, confidence="high", issues=(), corroboration=corr,
        evidence_checked=corr is not None, content_hash=content_hash)


# A claim whose *contradiction* is the "inhibit" abstract and *support* is the
# "induce" abstract — gives us deterministic per-source verdicts to count.
_INDUCE_CLAIM = "CBD induces CYP3A4 activity."
_CONTRA_ABSTRACT = "Cannabidiol inhibits CYP3A4."
_SUPPORT_ABSTRACT = "Cannabidiol induces CYP3A4 expression."


# ── corpus-contradiction bar: exact arithmetic ──────────────────────────────

class CorpusContradictionBar(unittest.TestCase):
    def test_four_checked_two_contradict_is_below_bar_no_misleading(self):
        # Arrange: 4 credible sources, 2 contradict (50%) — below ceil(0.6·4)=3.
        ch = Chunk("d", "S", _INDUCE_CLAIM, citations=("a", "b", "c", "e"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1),
                  _src("c", 2022, 1), _src("e", 2023, 1)]
        abstracts = {"a": _CONTRA_ABSTRACT, "b": _CONTRA_ABSTRACT,
                     "c": _SUPPORT_ABSTRACT, "e": _SUPPORT_ABSTRACT}
        # Act
        issues, corr = ce.detect_corpus_issues(
            ch, "CBD CYP3A4", corpus_fn=lambda t: corpus,
            abstract_fn=_abstracts(abstracts))
        # Assert: exact counts, and no misleading verdict at 2/4.
        self.assertEqual((corr.contradicted, corr.supported, corr.checked), (2, 2, 4))
        self.assertFalse(any(i.verdict == "corpus_contradiction" for i in issues))

    def test_five_checked_three_contradict_is_exactly_at_bar_misleading(self):
        # Arrange: 5 sources, 3 contradict (60%) — ceil(0.6·5)=3, so it fires.
        ch = Chunk("d", "S", _INDUCE_CLAIM, citations=("a", "b", "c", "e", "f"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1), _src("c", 2022, 1),
                  _src("e", 2023, 1), _src("f", 2024, 1)]
        abstracts = {"a": _CONTRA_ABSTRACT, "b": _CONTRA_ABSTRACT,
                     "c": _CONTRA_ABSTRACT, "e": _SUPPORT_ABSTRACT,
                     "f": _SUPPORT_ABSTRACT}
        # Act
        issues, corr = ce.detect_corpus_issues(
            ch, "CBD CYP3A4", corpus_fn=lambda t: corpus,
            abstract_fn=_abstracts(abstracts))
        # Assert
        self.assertEqual((corr.contradicted, corr.supported, corr.checked), (3, 2, 5))
        self.assertTrue(any(i.verdict == "corpus_contradiction" for i in issues))

    def test_two_checked_both_contradict_is_below_min_sample_never_misleading(self):
        # Arrange: only 2 sources, both contradict — below MIN_CORPUS_CONTRA (3).
        ch = Chunk("d", "S", _INDUCE_CLAIM, citations=("a", "b"))
        corpus = [_src("a", 2020, 1), _src("b", 2021, 1)]
        abstracts = {"a": _CONTRA_ABSTRACT, "b": _CONTRA_ABSTRACT}
        # Act
        issues, corr = ce.detect_corpus_issues(
            ch, "CBD CYP3A4", corpus_fn=lambda t: corpus,
            abstract_fn=_abstracts(abstracts))
        # Assert: 100% contradict but n<MIN → no misleading.
        self.assertEqual((corr.contradicted, corr.supported, corr.checked), (2, 0, 2))
        self.assertFalse(any(i.verdict == "corpus_contradiction" for i in issues))

    def test_supporting_corpus_records_corroboration_and_rolls_up_correct(self):
        # Arrange: the whole corpus supports a clinical claim, enough support to
        # cross the correctness bar (score≥0.6 and supported≥2).
        text = ("Cannabidiol reduces seizure frequency in Dravet syndrome "
                "epilepsy across controlled paediatric studies. " * 4)
        ch = Chunk("d", "S", text, citations=("111", "222"))
        corpus = [_src("111", 2017, 1), _src("222", 2018, 1)]
        abstracts = {"111": "Cannabidiol reduced seizure frequency in Dravet syndrome.",
                     "222": "CBD reduced seizure frequency in Dravet."}
        # Act
        v = ce.evaluate_chunk(
            ch, "CBD Dravet seizures", corpus_fn=lambda t: corpus,
            abstract_fn=_abstracts(abstracts),
            verifier=_verify({"111": "MATCH", "222": "MATCH"}),
            retraction_fn=_retracted(set()))
        # Assert: corroboration captured, no misleading, status CORRECT.
        self.assertEqual(v.status, ce.CORRECT)
        self.assertEqual((v.corroboration.supported, v.corroboration.contradicted), (2, 0))
        self.assertFalse(any(i.verdict == "corpus_contradiction" for i in v.issues))


# ── under_cited only fires for a CLINICAL claim ──────────────────────────────

class UnderCitedGate(unittest.TestCase):
    def test_clinical_claim_with_weak_citation_is_under_cited(self):
        # Arrange: clinical claim, cites only a tier-4 source while corpus has SR/RCT.
        ch = Chunk("d", "S", "CBD treats epilepsy effectively.", citations=("low1",))
        corpus = [_src("low1", 2015, 4), _src("sr1", 2020, 1)]
        # Act
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        # Assert
        self.assertTrue(any(i.verdict == "under_cited" for i in issues))

    def test_non_clinical_chunk_with_weak_citation_does_not_flag_under_cited(self):
        # Arrange: a botanical/morphology chunk (no efficacy/dose cue) with a weak
        # citation and a strong corpus — under_cited must NOT fire.
        text = ("Cannabis sativa is an annual herbaceous flowering plant with "
                "serrated palmate leaves studied in botanical taxonomy. " * 3)
        ch = Chunk("d", "S", text, citations=("low1",))
        corpus = [_src("low1", 2015, 4), _src("sr1", 2020, 1)]
        # Act
        issues, _ = ce.detect_corpus_issues(
            ch, "cannabis morphology", corpus_fn=lambda t: corpus)
        # Assert
        self.assertFalse(any(i.verdict == "under_cited" for i in issues))


# ── superseded requires a known cited year (no guessing) ─────────────────────

class SupersededYearGuard(unittest.TestCase):
    def test_newer_high_tier_supersedes_when_cited_year_is_known(self):
        # Arrange: chunk cites a 2014 source; corpus has a 2024 high-tier source.
        ch = Chunk("d", "S", "CBD reduces seizures.", citations=("old",))
        corpus = [_src("old", 2014, 1), _src("new", 2024, 1)]
        # Act
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        # Assert
        self.assertTrue(any(i.verdict == "superseded" for i in issues))

    def test_unknown_cited_year_does_not_fire_superseded(self):
        # Arrange: the cited corpus source has no year — we cannot say what's newer.
        ch = Chunk("d", "S", "CBD reduces seizures.", citations=("old",))
        corpus = [_src("old", None, 1), _src("new", 2024, 1)]
        # Act
        issues, _ = ce.detect_corpus_issues(
            ch, "CBD epilepsy", corpus_fn=lambda t: corpus)
        # Assert: no guessing → no superseded flag.
        self.assertFalse(any(i.verdict == "superseded" for i in issues))


# ── freshness: malformed input + boundary conditions ─────────────────────────

class FreshnessBoundaries(unittest.TestCase):
    _NOW = datetime.date(2026, 6, 11)

    def test_malformed_last_verified_at_does_not_crash_or_flag(self):
        # Arrange
        ch = Chunk("d", "S", "text")
        meta = {"last_verified_at": "not-a-date", "decay_horizon_days": 365}
        # Act
        issues = ce.detect_freshness_issue(ch, meta=meta, now=self._NOW)
        # Assert
        self.assertEqual(issues, [])

    def test_exactly_at_horizon_is_not_stale(self):
        # Arrange: exactly 365 days since last_verified_at, horizon 365 — the rule is
        # strictly greater-than, so days == horizon is NOT stale.
        ch = Chunk("d", "S", "text")
        meta = {"last_verified_at": "2025-06-11", "decay_horizon_days": 365}
        self.assertEqual((self._NOW - datetime.date(2025, 6, 11)).days, 365)
        # Act
        issues = ce.detect_freshness_issue(ch, meta=meta, now=self._NOW)
        # Assert
        self.assertEqual(issues, [])

    def test_one_day_past_horizon_is_stale(self):
        # Arrange: 366 days since last_verified_at, horizon 365 — strictly past.
        ch = Chunk("d", "S", "text")
        meta = {"last_verified_at": "2025-06-10", "decay_horizon_days": 365}
        # Act
        issues = ce.detect_freshness_issue(ch, meta=meta, now=self._NOW)
        # Assert
        self.assertTrue(any(i.verdict == "stale" for i in issues))

    def test_future_next_grade_review_at_is_fresh(self):
        # Arrange: review date is in the future — nothing to flag.
        ch = Chunk("d", "S", "text")
        meta = {"next_grade_review_at": "2030-01-01"}
        # Act
        issues = ce.detect_freshness_issue(ch, meta=meta, now=self._NOW)
        # Assert
        self.assertEqual(issues, [])


# ── severity rollup precedence ───────────────────────────────────────────────

class RollupPrecedence(unittest.TestCase):
    @staticmethod
    def _status_for(verdicts):
        ch = Chunk("d", "S", "text")
        issues = [ce._issue(v, "x", ch, "detail", "evidence", "action", "route")
                  for v in verdicts]
        return ce._rollup_status(issues, evidence_checked=False, corr=None)

    def test_misleading_and_outdated_rolls_up_to_misleading(self):
        # Arrange + Act
        status, _ = self._status_for(["banned_misleading", "stale"])
        # Assert
        self.assertEqual(status, ce.MISLEADING)

    def test_outdated_and_weakly_cited_rolls_up_to_outdated(self):
        # Arrange + Act
        status, _ = self._status_for(["stale", "under_cited"])
        # Assert
        self.assertEqual(status, ce.OUTDATED)

    def test_only_needs_improvement_issues_roll_up_to_needs_improvement(self):
        # Arrange + Act: unverified + coherence_conflict are the lowest-severity dim.
        status, conf = self._status_for(["unverified", "coherence_conflict"])
        # Assert
        self.assertEqual(status, ce.NEEDS_IMPROVEMENT)
        self.assertEqual(conf, "medium")


# ── ledger change classification ─────────────────────────────────────────────

class LedgerClassification(unittest.TestCase):
    def test_unevaluated_then_flagged_is_not_regressed(self):
        # Arrange: an UNEVALUATED chunk later flagged misleading. Only CORRECT→flagged
        # is a regression/alert; an unevaluated baseline must not raise a false alert.
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict_rec("c1", ce.UNEVALUATED, content_hash="h"),
                                 store_dir=d, now="t1")
            # Act
            diff = cl.record_evaluation(_verdict_rec("c1", ce.MISLEADING, content_hash="h"),
                                        store_dir=d, now="t2")
        # Assert
        self.assertNotEqual(diff.change, cl.REGRESSED)
        self.assertFalse(diff.is_alert)

    def test_reopened_requires_unchanged_content(self):
        # Arrange: prev clean + newer snapshot, but the content CHANGED → not reopened
        # (a changed chunk is a fresh edit, classified UPDATED, not reopen-on-evidence).
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(
                _verdict_rec("c1", ce.CORRECT, content_hash="h"), store_dir=d, now="t1",
                evidence_snapshot={"ids": ["111"], "max_year": 2018})
            # Act
            diff = cl.record_evaluation(
                _verdict_rec("c1", ce.UNEVALUATED, content_hash="DIFFERENT"),
                store_dir=d, now="t2",
                evidence_snapshot={"ids": ["111", "999"], "max_year": 2025})
        # Assert
        self.assertNotEqual(diff.change, cl.REOPENED)
        self.assertEqual(diff.change, cl.UPDATED)

    def test_reopened_fires_on_prev_clean_unchanged_content_newer_snapshot(self):
        # Arrange: the genuine reopen path — prev clean, content unchanged, snapshot moved.
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(
                _verdict_rec("c1", ce.CORRECT, content_hash="h"), store_dir=d, now="t1",
                evidence_snapshot={"ids": ["111"], "max_year": 2018})
            # Act
            diff = cl.record_evaluation(
                _verdict_rec("c1", ce.UNEVALUATED, content_hash="h"), store_dir=d, now="t2",
                evidence_snapshot={"ids": ["111", "999"], "max_year": 2025})
        # Assert
        self.assertEqual(diff.change, cl.REOPENED)
        self.assertTrue(diff.is_alert)

    def test_malformed_ledger_line_is_skipped_in_health(self):
        # Arrange: one good record + one junk line appended directly to the JSONL.
        with tempfile.TemporaryDirectory() as d:
            cl.record_evaluation(_verdict_rec("c1", ce.CORRECT, content_hash="h"),
                                 store_dir=d, now="t1")
            path = cl.ledger_path(store_dir=d)
            with open(path, "a", encoding="utf-8") as f:
                f.write("this is not valid json {{{\n")
            # Act
            health = cl.kb_health(store_dir=d)
        # Assert: junk line ignored, the one real chunk still counted.
        self.assertEqual(health.total, 1)
        self.assertEqual(health.correct_fraction, 1.0)

    def test_suppress_flag_is_idempotent(self):
        # Arrange + Act: suppress the same flag twice.
        with tempfile.TemporaryDirectory() as d:
            cl.suppress_flag("c1#S", "missing_evidence", "hashA",
                             reason="false positive", store_dir=d)
            cl.suppress_flag("c1#S", "missing_evidence", "hashA",
                             reason="false positive", store_dir=d)
            raw = json.loads(cl._feedback_path(store_dir=d).read_text(encoding="utf-8"))
            still_suppressed = cl.is_suppressed("c1#S", "missing_evidence", "hashA",
                                                store_dir=d)
        # Assert: exactly one stored entry, still suppressed.
        self.assertEqual(len(raw["suppressed"]), 1)
        self.assertTrue(still_suppressed)


# ── content hash normalisation ───────────────────────────────────────────────

class ContentHashNormalisation(unittest.TestCase):
    def test_whitespace_and_case_normalised_equal(self):
        # Arrange + Act + Assert: case and collapsing whitespace are normalised away.
        self.assertEqual(ce.content_hash("CBD Reduces  Seizures"),
                         ce.content_hash("cbd reduces seizures"))
        self.assertEqual(ce.content_hash("a b"), ce.content_hash("a  b"))
        self.assertEqual(ce.content_hash("  trimmed \n text  "),
                         ce.content_hash("trimmed text"))

    def test_different_text_differs(self):
        # Arrange + Act + Assert
        self.assertNotEqual(ce.content_hash("CBD reduces seizures"),
                            ce.content_hash("CBD increases seizures"))


# ── cross-chunk coherence: exactly the conflicting pair ──────────────────────

class CoherencePairing(unittest.TestCase):
    def test_only_the_opposing_pair_is_flagged_unrelated_chunk_untouched(self):
        # Arrange: A vs B oppose on CBD/CYP3A4; C is an unrelated empty-key chunk.
        a = Chunk("a", "S", "CBD inhibits CYP3A4 in the liver.")
        b = Chunk("b", "S", "CBD induces CYP3A4 activity.")
        c = Chunk("c", "S", "The growing season spans spring to autumn in temperate "
                            "regions of cultivation.")
        # Act
        issues = ce.detect_coherence_issues([a, b, c])
        flagged = {i.chunk_key for i in issues}
        # Assert: exactly the A,B pair (2 mirrored issues); C never appears.
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i.verdict == "coherence_conflict" for i in issues))
        self.assertEqual(flagged, {a.chunk_key, b.chunk_key})
        self.assertNotIn(c.chunk_key, flagged)

    def test_chunk_with_no_direction_is_never_in_a_coherence_pair(self):
        # Arrange: A vs B oppose; D shares the CBD entity but asserts no direction.
        a = Chunk("a", "S", "CBD inhibits CYP2C9 metabolism.")
        b = Chunk("b", "S", "CBD induces CYP2C9 metabolism.")
        d = Chunk("d", "S", "CBD is a cannabinoid found in the cannabis plant.")
        # Act
        issues = ce.detect_coherence_issues([a, b, d])
        flagged = {i.chunk_key for i in issues}
        # Assert: directionless D excluded; only the A,B pair flagged.
        self.assertEqual(flagged, {a.chunk_key, b.chunk_key})
        self.assertNotIn(d.chunk_key, flagged)


if __name__ == "__main__":
    unittest.main()
