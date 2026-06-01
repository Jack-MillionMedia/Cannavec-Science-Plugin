"""Tests for the GRADE Optimal Information Size verdict (spec 018).

The OIS is the total enrolment a single adequately powered trial would need to
detect the pooled effect (Guyatt 2011, GRADE guidelines 6). Every scenario is
numerically pinned against the real ``power_calc`` + ``meta_analyze`` output
(80% power, α=0.05 two-sided).
"""

import json
import unittest

from cannavec_science import meta_analysis as ma


# ── fixtures ─────────────────────────────────────────────────────────


def _strong_rr():
    """RR ≈ 0.52 from 605 participants — a large, strong-effect pool."""
    return ma.meta_analyze([
        ma.binary_effect("Devinsky 2017", events_t=20, n_t=100,
                         events_c=40, n_c=100, measure="RR", pmid="28538134"),
        ma.binary_effect("Thiele 2018", events_t=25, n_t=110,
                         events_c=45, n_c=110, measure="RR", pmid="29642420"),
        ma.binary_effect("Miller 2020", events_t=18, n_t=90,
                         events_c=38, n_c=95, measure="RR", pmid="32444460"),
    ], measure="RR")


def _near_null_rr():
    """RR ≈ 0.96 from 605 participants — a small effect needing a huge OIS."""
    return ma.meta_analyze([
        ma.binary_effect("A", events_t=22, n_t=100, events_c=25, n_c=100,
                         measure="RR", pmid="1"),
        ma.binary_effect("B", events_t=24, n_t=110, events_c=26, n_c=110,
                         measure="RR", pmid="2"),
        ma.binary_effect("C", events_t=20, n_t=90, events_c=19, n_c=95,
                         measure="RR", pmid="3"),
    ], measure="RR")


def _strong_or():
    return ma.meta_analyze([
        ma.binary_effect("A", events_t=20, n_t=100, events_c=40, n_c=100,
                         measure="OR", pmid="1"),
        ma.binary_effect("B", events_t=25, n_t=110, events_c=45, n_c=110,
                         measure="OR", pmid="2"),
        ma.binary_effect("C", events_t=18, n_t=90, events_c=38, n_c=95,
                         measure="OR", pmid="3"),
    ], measure="OR")


def _small_smd():
    """SMD ≈ 0.58 from 84 participants — CI excludes 0 yet below OIS 96."""
    return ma.meta_analyze([
        ma.continuous_effect("S1", mean_t=0.60, sd_t=1.0, n_t=14,
                             mean_c=0.0, sd_c=1.0, n_c=14, measure="SMD", pmid="1"),
        ma.continuous_effect("S2", mean_t=0.62, sd_t=1.0, n_t=15,
                             mean_c=0.0, sd_c=1.0, n_c=15, measure="SMD", pmid="2"),
        ma.continuous_effect("S3", mean_t=0.58, sd_t=1.0, n_t=13,
                             mean_c=0.0, sd_c=1.0, n_c=13, measure="SMD", pmid="3"),
    ], measure="SMD")


def _md_pool():
    return ma.meta_analyze([
        ma.continuous_effect("A", mean_t=30, sd_t=18, n_t=60,
                             mean_c=42, sd_c=19, n_c=60, measure="MD", pmid="1"),
        ma.continuous_effect("B", mean_t=28, sd_t=17, n_t=55,
                             mean_c=40, sd_c=18, n_c=58, measure="MD", pmid="2"),
    ], measure="MD")


def _null_rr():
    """Pooled RR is exactly 1.0 → the OIS is unbounded."""
    return ma.meta_analyze([
        ma.binary_effect("A", events_t=20, n_t=100, events_c=20, n_c=100,
                         measure="RR", pmid="1"),
        ma.binary_effect("B", events_t=22, n_t=110, events_c=22, n_c=110,
                         measure="RR", pmid="2"),
    ], measure="RR")


# ── assessable verdicts ──────────────────────────────────────────────


class AssessableTests(unittest.TestCase):
    def test_strong_rr_meets_ois(self):
        o = ma.optimal_information_size(_strong_rr(), baseline_risk=0.40)
        self.assertTrue(o.assessable)
        self.assertEqual(o.total_n, 605)
        self.assertEqual(o.ois, 202)
        self.assertFalse(o.below_ois)
        self.assertGreater(o.ratio, 1.0)
        self.assertIn("meets OIS", o.rationale)

    def test_small_smd_is_below_ois_despite_tight_ci(self):
        res = _small_smd()
        # guard the fixture: the CI excludes the null (so only the OIS catches it)
        lo, hi = res.random_ci_display
        self.assertFalse(lo <= 0.0 <= hi)
        o = ma.optimal_information_size(res)          # SMD needs no baseline
        self.assertTrue(o.assessable)
        self.assertEqual(o.total_n, 84)
        self.assertEqual(o.ois, 96)
        self.assertTrue(o.below_ois)
        self.assertIn("below OIS", o.rationale)

    def test_near_null_rr_is_below_a_huge_ois(self):
        o = ma.optimal_information_size(_near_null_rr(), baseline_risk=0.40)
        self.assertTrue(o.assessable)
        self.assertTrue(o.below_ois)
        self.assertGreater(o.ois, 10000)             # tiny effect → enormous OIS

    def test_or_path_meets_ois(self):
        o = ma.optimal_information_size(_strong_or(), baseline_risk=0.40)
        self.assertTrue(o.assessable)
        self.assertEqual(o.method, "odds_ratio_two_arm")
        self.assertFalse(o.below_ois)

    def test_md_with_pooling_sd_is_assessable(self):
        o = ma.optimal_information_size(_md_pool(), pooling_sd=18.0)
        self.assertTrue(o.assessable)
        self.assertEqual(o.total_n, 233)

    def test_power_and_alpha_are_recorded(self):
        o = ma.optimal_information_size(_strong_rr(), baseline_risk=0.40,
                                        power=0.90, alpha=0.01)
        self.assertEqual(o.power, 0.90)
        self.assertEqual(o.alpha, 0.01)
        # a stricter trial needs more patients → a larger OIS
        base = ma.optimal_information_size(_strong_rr(), baseline_risk=0.40)
        self.assertGreater(o.ois, base.ois)


# ── honest "not assessed" paths ──────────────────────────────────────


class NotAssessedTests(unittest.TestCase):
    def test_binary_without_baseline_is_not_assessed(self):
        o = ma.optimal_information_size(_strong_rr())
        self.assertFalse(o.assessable)
        self.assertEqual(o.method, "not_assessed")
        self.assertFalse(o.below_ois)
        self.assertIn("control event rate", o.rationale)
        self.assertEqual(o.total_n, 605)            # n is known; baseline is not

    def test_md_without_pooling_sd_is_not_assessed(self):
        o = ma.optimal_information_size(_md_pool())
        self.assertFalse(o.assessable)
        self.assertIn("pooling SD", o.rationale)

    def test_generic_measure_is_not_assessed(self):
        res = ma.meta_analyze([
            ma.EffectSize(study_id="S1", yi=0.5, vi=0.02, pmid="1", n=80),
            ma.EffectSize(study_id="S2", yi=0.6, vi=0.02, pmid="2", n=80),
        ], measure="generic")
        o = ma.optimal_information_size(res)
        self.assertFalse(o.assessable)
        self.assertIn("generic", o.rationale)

    def test_missing_study_n_is_not_assessed(self):
        res = ma.meta_analyze([
            ma.EffectSize(study_id="S1", yi=-0.6, vi=0.02, measure="SMD", pmid="1"),
            ma.EffectSize(study_id="S2", yi=-0.7, vi=0.02, measure="SMD", pmid="2"),
        ], measure="SMD")
        o = ma.optimal_information_size(res)
        self.assertFalse(o.assessable)
        self.assertIsNone(o.total_n)
        self.assertIn("sample sizes missing", o.rationale)

    def test_null_contrast_is_not_assessed(self):
        o = ma.optimal_information_size(_null_rr(), baseline_risk=0.40)
        self.assertFalse(o.assessable)
        self.assertIn("null contrast", o.rationale)


# ── shape + render ───────────────────────────────────────────────────


class ShapeTests(unittest.TestCase):
    def test_to_dict_is_deterministic(self):
        a = ma.optimal_information_size(_strong_rr(), baseline_risk=0.40).to_dict()
        b = ma.optimal_information_size(_strong_rr(), baseline_risk=0.40).to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))

    def test_render_below_ois(self):
        text = ma.render_ois(ma.optimal_information_size(_small_smd()))
        self.assertIn("Optimal Information Size", text)
        self.assertIn("below the OIS", text)
        self.assertIn("96", text)

    def test_render_not_assessed(self):
        text = ma.render_ois(ma.optimal_information_size(_strong_rr()))
        self.assertIn("not assessed", text)


if __name__ == "__main__":
    unittest.main()
