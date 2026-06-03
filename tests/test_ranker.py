"""Offline tests for the deterministic ranker core.

Pure stdlib, zero network. Pins the accuracy floor (relevance, study-design,
recency, retraction sink), the cost short-circuit, and the provenance gate —
the guarantees that let the LLM lift be cost-efficient without trading
accuracy.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cannavec_science.ranker import (  # noqa: E402
    Candidate,
    DeterministicRanker,
    RankPlan,
    ScoreBreakdown,
    candidates_from_discovery,
    has_design_inversion,
    low_lexical_confidence,
    provenance_gate,
    rank_candidates,
    render_json,
    render_markdown,
    score_candidates,
    should_escalate,
)


def _sb(identifier, bm25, design):
    """A ScoreBreakdown for direct has_design_inversion tests."""
    return ScoreBreakdown(
        identifier=identifier, bm25=bm25, design_weight=design,
        design_label="x", recency_factor=1.0, retraction_factor=1.0,
        final=(1.0 + bm25) * design,
    )


def _c(identifier, title="", abstract="", year=None, study_types=(),
       retraction_status="clean", topic="", source="live_pubmed"):
    return Candidate(
        identifier=identifier, title=title, abstract=abstract, year=year,
        study_types=tuple(study_types), retraction_status=retraction_status,
        topic=topic, source=source,
    )


def _ranked_ids(result):
    return [r.candidate.identifier for r in result.ranked]


# ── Candidate adaptation ──────────────────────────────────────────────────


class CandidateAdaptationTests(unittest.TestCase):
    def test_from_row_pubmed_shape(self):
        row = {
            "pmid": "26103030", "title": "Cannabinoids for medical use",
            "year": 2015, "pubtypes": ["Systematic Review", "Meta-Analysis"],
            "retraction_status": "clean", "provenance": "live_pubmed",
        }
        c = Candidate.from_row("pubmed", row)
        self.assertEqual(c.identifier, "26103030")
        self.assertIn("Meta-Analysis", c.study_types)
        self.assertEqual(c.year, 2015)
        self.assertEqual(c.source, "live_pubmed")

    def test_from_row_doi_fallback(self):
        c = Candidate.from_row("preprint", {"doi": "10.1101/x", "title": "T"})
        self.assertEqual(c.identifier, "10.1101/x")

    def test_from_row_bad_year_is_none(self):
        c = Candidate.from_row("pubmed", {"pmid": "1", "year": "n/a"})
        self.assertIsNone(c.year)

    def test_candidates_from_discovery_skips_errors_and_idless(self):
        result = {
            "sources": {
                "pubmed": [{"pmid": "1", "title": "a"}, {"title": "no id"}],
                "chembl": {"error": "boom"},
            }
        }
        cands = candidates_from_discovery(result)
        self.assertEqual([c.identifier for c in cands], ["1"])


# ── Relevance (BM25) ──────────────────────────────────────────────────────


class RelevanceTests(unittest.TestCase):
    def test_on_topic_beats_off_topic(self):
        cands = [
            _c("OFF", title="Hop terpene biosynthesis in brewing"),
            _c("ON", title="Cannabidiol for epilepsy seizures: a trial"),
        ]
        result = rank_candidates("cbd epilepsy seizures", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[0], "ON")

    def test_empty_query_falls_back_to_quality(self):
        # No usable query tokens → ranking driven by design/recency, not a crash.
        cands = [
            _c("CASE", title="x", study_types=("Case Reports",), year=2020),
            _c("SR", title="y", study_types=("Systematic Review",), year=2020),
        ]
        result = rank_candidates("", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[0], "SR")


# ── Study-design prior ────────────────────────────────────────────────────


class DesignPriorTests(unittest.TestCase):
    def test_sr_outranks_case_report_on_equal_relevance(self):
        cands = [
            _c("CASE", title="CBD for pain", study_types=("Case Reports",), year=2022),
            _c("SR", title="CBD for pain", study_types=("Systematic Review",), year=2022),
        ]
        result = rank_candidates("cbd pain", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[0], "SR")

    def test_design_label_surfaced_in_signals(self):
        cands = [_c("A", title="CBD pain", study_types=("Meta-Analysis",))]
        result = rank_candidates("cbd pain", cands, now_year=2026)
        self.assertEqual(result.ranked[0].signals["design_label"], "meta-analysis")


# ── Elite relevance: affix matching + preclinical detection ─────────────────


class AffixAndPreclinicalTests(unittest.TestCase):
    def test_affix_matcher_is_precise(self):
        from cannavec_science.ranker import _term_matches
        # Compound / prefixed biomedical terms match their root...
        self.assertTrue(_term_matches("permeability", "hyperpermeability"))
        self.assertTrue(_term_matches("convulsant", "anticonvulsant"))
        self.assertTrue(_term_matches("inflammatory", "proinflammatory"))
        # ...but short roots and non-suffix relations do not (no noise).
        self.assertFalse(_term_matches("gut", "foregut"))            # < 6 chars
        self.assertFalse(_term_matches("able", "permeable"))         # < 6 chars
        self.assertFalse(_term_matches("cannabidiol", "cannabinoid"))  # not a suffix

    def test_preclinical_animal_studies_demoted(self):
        from cannavec_science.ranker import _design_weight
        for title in ("CBD in a mouse model of colitis",
                      "Cannabidiol in the gut of chickens",
                      "CBD effect in a murine model",
                      "Cannabidiol in Caco-2 cell lines in vitro"):
            w, label = _design_weight(_c("x", title=title))
            self.assertEqual(label, "preclinical/animal", title)
            self.assertEqual(w, 0.50)
        # A human-classified design is never demoted by an in-vitro arm.
        w, label = _design_weight(_c(
            "y", title="Cannabidiol human trial with in vitro sub-study",
            study_types=("Randomized Controlled Trial",)))
        self.assertEqual(label, "RCT")

    def test_human_rcts_outrank_reviews_and_preclinical(self):
        # The live "cannabidiol gut permeability" case, on the real titles:
        # the human RCT (affix-credited for 'hyperpermeability') leads, and the
        # animal studies sink below it as preclinical.
        cands = [
            _c("REVIEW", year=2024, study_types=("Review",),
               title="Effects of Cannabinoids on Intestinal Motility, Barrier "
                     "Permeability, and Therapeutic Potential in Gastrointestinal Diseases"),
            _c("RCT", year=2019, study_types=("Randomized Controlled Trial",),
               title="Palmitoylethanolamide and Cannabidiol Prevent Inflammation-induced "
                     "Hyperpermeability of the Human Gut In Vitro and In Vivo - A "
                     "Randomized, Placebo-controlled, Double-blind Controlled Trial"),
            _c("MOUSE", year=2025, study_types=(),
               title="Effect of intraperitoneal cannabidiol injection on intestine "
                     "microbiome profile in a mouse model"),
            _c("CHICKEN", year=2024, study_types=(),
               title="Cannabidiol in the Gut of Chickens Applied to Different Conditions"),
        ]
        result = rank_candidates("cannabidiol gut permeability", cands, now_year=2026)
        ids = _ranked_ids(result)
        labels = {rc.candidate.identifier: rc.signals["design_label"] for rc in result.ranked}
        self.assertEqual(ids[0], "RCT")
        self.assertEqual(labels["MOUSE"], "preclinical/animal")
        self.assertEqual(labels["CHICKEN"], "preclinical/animal")
        self.assertLess(ids.index("RCT"), ids.index("MOUSE"))
        self.assertLess(ids.index("RCT"), ids.index("CHICKEN"))


# ── Recency ───────────────────────────────────────────────────────────────


class RecencyTests(unittest.TestCase):
    def test_newer_wins_all_else_equal(self):
        cands = [
            _c("OLD", title="CBD anxiety RCT", study_types=("Randomized Controlled Trial",), year=2008),
            _c("NEW", title="CBD anxiety RCT", study_types=("Randomized Controlled Trial",), year=2024),
        ]
        result = rank_candidates("cbd anxiety", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[0], "NEW")

    def test_recency_never_beats_quality(self):
        # A brand-new case report must not outrank an older systematic review.
        cands = [
            _c("NEWCASE", title="CBD sleep", study_types=("Case Reports",), year=2026),
            _c("OLDSR", title="CBD sleep", study_types=("Systematic Review",), year=2015),
        ]
        result = rank_candidates("cbd sleep", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[0], "OLDSR")

    def test_recent_review_does_not_outrank_older_rct(self):
        # The gut-permeability case: a recent narrative review must not outrank
        # an older HUMAN RCT of comparable relevance. Study design dominates the
        # (now narrowed) recency window.
        cands = [
            _c("REVIEW", title="Cannabidiol in the gut: therapeutic potential",
               abstract="cannabidiol gut permeability narrative review",
               year=2025, study_types=("Review",)),
            _c("RCT", title="Cannabidiol prevents human gut hyperpermeability in vivo",
               abstract="cannabidiol gut permeability randomized controlled trial human",
               year=2019, study_types=("Randomized Controlled Trial",)),
        ]
        result = rank_candidates("cannabidiol gut permeability", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[0], "RCT")


# ── Retraction sink ───────────────────────────────────────────────────────


class RetractionTests(unittest.TestCase):
    def test_retracted_sinks_to_bottom_even_if_most_relevant(self):
        cands = [
            _c("RETRACTED", title="CBD epilepsy seizures meta-analysis",
               study_types=("Meta-Analysis",), year=2025, retraction_status="retracted"),
            _c("CLEAN", title="CBD epilepsy", study_types=("Case Reports",), year=2010),
        ]
        result = rank_candidates("cbd epilepsy seizures", cands, now_year=2026)
        self.assertEqual(_ranked_ids(result)[-1], "RETRACTED")
        self.assertEqual(_ranked_ids(result)[0], "CLEAN")


# ── Cost short-circuit ────────────────────────────────────────────────────


class EscalationTests(unittest.TestCase):
    def test_decisive_margin_does_not_escalate(self):
        scored = [("a", 5.0), ("b", 1.0), ("c", 0.5)]
        self.assertFalse(should_escalate(scored, margin=0.15))

    def test_near_tie_escalates(self):
        scored = [("a", 5.0), ("b", 4.9), ("c", 4.8)]
        self.assertTrue(should_escalate(scored, margin=0.15))

    def test_too_few_candidates_never_escalates(self):
        self.assertFalse(should_escalate([("a", 5.0), ("b", 4.9)], margin=0.15))

    # ── design-inversion trigger (expert audience) ──────────────────────
    def test_inversion_when_relevant_strong_design_is_buried(self):
        # REVIEW(0.55) ranked above RCT(0.90); RCT bm25 0.8 >= 0.25*2.0 floor.
        rows = [_sb("REVIEW", 2.0, 0.55), _sb("RCT", 0.8, 0.90), _sb("CASE", 0.1, 0.55)]
        self.assertTrue(has_design_inversion(rows))

    def test_no_inversion_when_strong_design_is_offtopic(self):
        # The meta has stronger design but is off-topic (bm25 below the floor),
        # so it is correctly buried — not an inversion worth an expert's time.
        rows = [_sb("REVIEW", 2.0, 0.55), _sb("OFFMETA", 0.2, 1.00), _sb("CASE", 0.1, 0.55)]
        self.assertFalse(has_design_inversion(rows))

    def test_no_inversion_in_design_respecting_order(self):
        rows = [_sb("META", 2.0, 1.00), _sb("RCT", 1.5, 0.90), _sb("REVIEW", 1.0, 0.55)]
        self.assertFalse(has_design_inversion(rows))

    def test_small_design_gap_not_flagged(self):
        # cohort(0.75) above rct(0.90): gap 0.15 < 0.2 → fine distinction, skip.
        rows = [_sb("COHORT", 1.0, 0.75), _sb("RCT", 0.9, 0.90), _sb("X", 0.5, 0.65)]
        self.assertFalse(has_design_inversion(rows))

    def test_inversion_too_few_candidates(self):
        rows = [_sb("REVIEW", 2.0, 0.55), _sb("RCT", 1.0, 0.90)]
        self.assertFalse(has_design_inversion(rows))

    # ── weak-lexical-signal trigger (BM25's synonymy blind spot) ────────
    def test_low_lexical_confidence_on_synonymy_miss(self):
        # "cbd" never lexically matches "cannabidiol" — BM25 is blind here.
        cands = [
            _c("A", title="Cannabidiol mechanisms", abstract="cannabidiol pharmacology"),
            _c("B", title="Cannabidiol clinical overview", abstract="cannabidiol clinical"),
            _c("C", title="Cannabidiol safety", abstract="cannabidiol safety"),
        ]
        self.assertTrue(low_lexical_confidence("cbd", cands))

    def test_lexical_confident_when_terms_present(self):
        cands = [
            _c("A", title="Cannabidiol for epilepsy", abstract="cannabidiol epilepsy seizures"),
            _c("B", title="Cannabidiol overview", abstract="cannabidiol"),
            _c("C", title="Cannabidiol safety", abstract="cannabidiol"),
        ]
        self.assertFalse(low_lexical_confidence("cannabidiol epilepsy", cands))

    def test_lexical_skips_content_free_candidates(self):
        # Discovery-index-style rows (no title/abstract) → nothing for the LLM
        # to read semantically, so escalating would be wasted.
        bare = [_c(str(i), topic="x") for i in range(4)]
        self.assertFalse(low_lexical_confidence("cbd epilepsy", bare))

    def test_lexical_empty_query_is_false(self):
        cands = [_c("A", title="Cannabidiol"), _c("B", title="THC"), _c("C", title="CBG")]
        self.assertFalse(low_lexical_confidence("", cands))

    def test_pipeline_default_is_deterministic_no_escalation(self):
        cands = [_c("A", title="CBD pain"), _c("B", title="CBD sleep")]
        result = rank_candidates("cbd pain", cands, now_year=2026)
        self.assertEqual(result.backend_used, "deterministic")
        self.assertFalse(result.escalated)


# ── Provenance gate ───────────────────────────────────────────────────────


class ProvenanceGateTests(unittest.TestCase):
    def test_drops_unknown_and_dedupes_preserving_order(self):
        gated = provenance_gate(["b", "ghost", "a", "b"], {"a", "b"})
        self.assertEqual(gated, ["b", "a"])

    def test_empty_when_nothing_allowed(self):
        self.assertEqual(provenance_gate(["x", "y"], set()), [])


# ── Backend seam (fake LLM, no SDK) ───────────────────────────────────────


class _FakeBackend:
    """A stand-in RankerBackend that returns a fixed order — exercises the
    pipeline's escalation + gating without importing the LLM adapter."""

    name = "llm"

    def __init__(self, order, rationales=None, raises=False):
        self._order = tuple(order)
        self._rationales = rationales or {}
        self._raises = raises

    def plan(self, query, candidates):
        if self._raises:
            raise RuntimeError("model unavailable")
        return RankPlan(order=self._order, rationales=self._rationales, backend="llm")


class BackendIntegrationTests(unittest.TestCase):
    def _near_tie_candidates(self):
        # Three near-tied (same design/year, overlapping relevance) → escalates.
        return [
            _c("P1", title="cannabis pain chronic", study_types=("Randomized Controlled Trial",), year=2020),
            _c("P2", title="cannabis pain neuropathic", study_types=("Randomized Controlled Trial",), year=2020),
            _c("P3", title="cannabis pain cancer", study_types=("Randomized Controlled Trial",), year=2020),
        ]

    def test_llm_reorders_when_escalated(self):
        cands = self._near_tie_candidates()
        backend = _FakeBackend(order=["P3", "P1", "P2"],
                               rationales={"P3": "most direct"})
        result = rank_candidates("cannabis pain", cands, backend=backend,
                                 escalate=True, now_year=2026)
        self.assertTrue(result.escalated)
        self.assertEqual(result.backend_used, "llm")
        self.assertEqual(_ranked_ids(result)[0], "P3")
        self.assertTrue(result.ranked[0].reordered_by_llm)
        self.assertEqual(result.ranked[0].rationale, "most direct")
        self.assertEqual(result.escalation_reason, "forced")

    def test_design_inversion_auto_escalates_and_expert_lifts_strong_design(self):
        # A keyword-dense narrative review outscores a buried-but-relevant RCT
        # and meta-analysis on BM25 — the exact case where an expert reranker
        # should adjudicate. Auto-escalation must fire on "design inversion",
        # not a top near-tie, and the (fake) expert lift pulls the strong
        # designs back up.
        cands = [
            _c("REV", title="Cannabidiol for epilepsy in Dravet syndrome seizures: a practical guide",
               abstract=("cannabidiol epilepsy dravet seizures cannabidiol epilepsy dravet seizures "
                         "cannabidiol epilepsy dravet seizures cannabidiol epilepsy dravet seizures "
                         "cannabidiol epilepsy dravet seizures cannabidiol reduced seizures"),
               year=2021, study_types=("Review",)),
            _c("MA", title="Comparative network meta-analysis of adjunctive add-on therapies in childhood",
               abstract="we pooled randomized trials of stiripentol fenfluramine and cannabidiol for dravet using extensive frequentist methods across many comparisons reported at length here",
               year=2024, study_types=("Systematic Review", "Network Meta-Analysis")),
            _c("RCT", title="Trial of fenfluramine for convulsive seizures",
               abstract="double blind placebo controlled randomized trial of fenfluramine in children with dravet seizures over fourteen weeks",
               year=2017, study_types=("Randomized Controlled Trial",)),
            _c("REV2", title="State-of-the-art management of Dravet syndrome",
               abstract="review of dravet management and comorbidities", year=2025, study_types=("Review",)),
            _c("GUIDE", title="Epilepsy treatment overview",
               abstract="epilepsy treatment overview narrative", year=2020, study_types=("Review",)),
        ]
        query = "cannabidiol epilepsy dravet seizures"
        # Deterministic floor buries the strong designs under the dense review.
        det = rank_candidates(query, cands, now_year=2026)
        self.assertEqual(_ranked_ids(det)[0], "REV")
        # Auto-escalate with an expert backend that lifts MA/RCT above the review.
        backend = _FakeBackend(order=["MA", "RCT", "REV", "GUIDE", "REV2"])
        result = rank_candidates(query, cands, backend=backend, escalate=None, now_year=2026)
        self.assertTrue(result.escalated)
        self.assertEqual(result.escalation_reason, "design inversion")
        self.assertEqual(result.backend_used, "llm")
        self.assertEqual(_ranked_ids(result)[0], "MA")

    def test_weak_lexical_signal_auto_escalates(self):
        # "cbd" never lexically matches "cannabidiol", so BM25 is unreliable;
        # the SR dominates on design (no top-tie, no inversion) but the LLM's
        # semantic read is the effective ranker → escalate on weak lexical.
        cands = [
            _c("A", title="Cannabidiol mechanisms of action", abstract="cannabidiol pharmacology",
               year=2024, study_types=("Systematic Review",)),
            _c("B", title="Cannabidiol clinical overview", abstract="cannabidiol clinical",
               year=2022, study_types=("Review",)),
            _c("C", title="Cannabidiol safety review", abstract="cannabidiol safety",
               year=2020, study_types=("Review",)),
        ]
        backend = _FakeBackend(order=["B", "A", "C"])
        result = rank_candidates("cbd", cands, backend=backend, escalate=None, now_year=2026)
        self.assertTrue(result.escalated)
        self.assertEqual(result.escalation_reason, "weak lexical signal")
        self.assertEqual(_ranked_ids(result)[0], "B")

    def test_llm_cannot_introduce_a_citation(self):
        # Backend tries to inject an identifier not in the candidate set.
        cands = self._near_tie_candidates()
        backend = _FakeBackend(order=["GHOST", "P2", "P1", "P3"])
        result = rank_candidates("cannabis pain", cands, backend=backend,
                                 escalate=True, now_year=2026)
        self.assertNotIn("GHOST", _ranked_ids(result))
        self.assertEqual(set(_ranked_ids(result)), {"P1", "P2", "P3"})

    def test_llm_cannot_float_a_retracted_paper(self):
        cands = self._near_tie_candidates() + [
            _c("RETRACTED", title="cannabis pain", study_types=("Meta-Analysis",),
               year=2025, retraction_status="retracted"),
        ]
        backend = _FakeBackend(order=["RETRACTED", "P1", "P2", "P3"])
        result = rank_candidates("cannabis pain", cands, backend=backend,
                                 escalate=True, now_year=2026)
        self.assertEqual(_ranked_ids(result)[-1], "RETRACTED")

    def test_backend_failure_falls_back_to_deterministic(self):
        cands = self._near_tie_candidates()
        backend = _FakeBackend(order=[], raises=True)
        result = rank_candidates("cannabis pain", cands, backend=backend,
                                 escalate=True, now_year=2026)
        self.assertEqual(result.backend_used, "deterministic")
        self.assertFalse(result.escalated)
        self.assertTrue(any("failed" in n for n in result.notes))

    def test_backend_empty_plan_falls_back(self):
        cands = self._near_tie_candidates()
        backend = _FakeBackend(order=["nope", "nada"])  # none in candidate set
        result = rank_candidates("cannabis pain", cands, backend=backend,
                                 escalate=True, now_year=2026)
        self.assertEqual(result.backend_used, "deterministic")

    def test_auto_escalation_skips_when_decisive(self):
        # One clearly-dominant candidate → auto short-circuit, no backend call.
        cands = [
            _c("WIN", title="cbd epilepsy dravet seizures randomized trial",
               study_types=("Systematic Review",), year=2024),
            _c("MEH", title="hop brewing terpene", study_types=("Case Reports",), year=2005),
            _c("MEH2", title="industrial fibre", study_types=("Case Reports",), year=2004),
        ]

        class _Boom:
            name = "llm"

            def plan(self, query, candidates):
                raise AssertionError("should not be called when decisive")

        result = rank_candidates("cbd epilepsy seizures", cands, backend=_Boom(),
                                 escalate=None, now_year=2026)
        self.assertEqual(result.backend_used, "deterministic")
        self.assertEqual(_ranked_ids(result)[0], "WIN")


# ── Determinism + renderers ───────────────────────────────────────────────


class DeterminismTests(unittest.TestCase):
    def test_same_input_same_output(self):
        cands = [
            _c("A", title="CBD pain RCT", study_types=("Randomized Controlled Trial",), year=2020),
            _c("B", title="CBD pain cohort", study_types=("Cohort Studies",), year=2021),
            _c("C", title="CBD pain review", study_types=("Review",), year=2019),
        ]
        r1 = rank_candidates("cbd pain", cands, now_year=2026)
        r2 = rank_candidates("cbd pain", cands, now_year=2026)
        self.assertEqual(_ranked_ids(r1), _ranked_ids(r2))

    def test_deterministic_ranker_matches_pipeline(self):
        cands = [
            _c("A", title="CBD pain RCT", study_types=("Randomized Controlled Trial",), year=2020),
            _c("B", title="CBD pain cohort", study_types=("Cohort Studies",), year=2021),
        ]
        scores = score_candidates("cbd pain", cands, now_year=2026)
        plan = DeterministicRanker(now_year=2026).plan("cbd pain", cands)
        expected = sorted((c.identifier for c in cands),
                          key=lambda i: (-scores[i].final, i))
        self.assertEqual(list(plan.order), expected)


class RendererTests(unittest.TestCase):
    def test_markdown_has_header_and_rows(self):
        cands = [_c("A", title="CBD pain", study_types=("Meta-Analysis",), year=2024)]
        md = render_markdown(rank_candidates("cbd pain", cands, now_year=2026))
        self.assertIn("Ranked candidates", md)
        self.assertIn("A", md)
        self.assertIn("not curated facts", md)

    def test_json_shape(self):
        cands = [_c("A", title="CBD pain", study_types=("Meta-Analysis",), year=2024)]
        payload = json.loads(render_json(rank_candidates("cbd pain", cands, now_year=2026)))
        self.assertIn("ranked", payload)
        self.assertIn("backend_used", payload)
        self.assertEqual(payload["ranked"][0]["identifier"], "A")


if __name__ == "__main__":
    unittest.main()
