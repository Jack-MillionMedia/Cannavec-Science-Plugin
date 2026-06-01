"""Tests for the deterministic meta-analysis primitive (spec 011).

Reference values are hand-computed in the docstrings so a reviewer can
re-derive every assertion. Constitution §III: positive + negative +
refusal cases for every public function.
"""

import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import meta_analysis as ma
from cannavec_science.evidence import EvidenceLevel, apply_grade_modifiers


class EffectSizeConstructionTests(unittest.TestCase):
    def test_generic_effect_requires_identifier(self):
        # §I: an unanchored number cannot be pooled.
        with self.assertRaises(ma.MetaAnalysisError):
            ma.EffectSize(study_id="anon", yi=0.2, vi=0.04)

    def test_identifier_accepts_any_primary_scheme(self):
        for kwargs, expected in (
            ({"pmid": "28538134"}, "PMID:28538134"),
            ({"doi": "10.1056/x"}, "DOI:10.1056/x"),
            ({"nct": "NCT01"}, "NCT:NCT01"),
            ({"chembl": "CHEMBL1"}, "ChEMBL:CHEMBL1"),
            ({"uniprot": "P21554"}, "UniProt:P21554"),
            ({"url": "https://x"}, "URL:https://x"),
        ):
            es = ma.EffectSize(study_id="s", yi=0.1, vi=0.01, **kwargs)
            self.assertEqual(es.identifier, expected)

    def test_non_positive_variance_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.EffectSize(study_id="s", yi=0.1, vi=0.0, pmid="1")
        with self.assertRaises(ma.MetaAnalysisError):
            ma.EffectSize(study_id="s", yi=0.1, vi=-1.0, pmid="1")

    def test_non_finite_effect_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.EffectSize(study_id="s", yi=float("inf"), vi=0.01, pmid="1")

    def test_se_and_ci(self):
        es = ma.EffectSize(study_id="s", yi=0.5, vi=0.04, pmid="1")
        self.assertAlmostEqual(es.se, 0.2)
        lo, hi = es.ci(1.959963984540054)
        self.assertAlmostEqual(lo, 0.5 - 1.959963984540054 * 0.2, places=9)
        self.assertAlmostEqual(hi, 0.5 + 1.959963984540054 * 0.2, places=9)


class BinaryConstructorTests(unittest.TestCase):
    def test_odds_ratio(self):
        # a=10,b=90,c=20,d=80 → OR=(10*80)/(90*20)=0.4444, logOR=-0.81093
        # var=1/10+1/90+1/20+1/80=0.173611
        es = ma.binary_effect(
            "trial", events_t=10, n_t=100, events_c=20, n_c=100,
            measure="OR", pmid="111",
        )
        self.assertAlmostEqual(es.yi, math.log(0.4444444444444444), places=6)
        self.assertAlmostEqual(es.vi, 0.1736111111, places=6)
        self.assertEqual(es.measure, "OR")
        self.assertFalse(es.corrected)
        self.assertEqual(es.n, 200)

    def test_risk_ratio(self):
        # risk_t=0.1, risk_c=0.2 → RR=0.5, logRR=-0.693147
        # var=1/10-1/100+1/20-1/100=0.13
        es = ma.binary_effect(
            "trial", events_t=10, n_t=100, events_c=20, n_c=100,
            measure="RR", doi="10.x/y",
        )
        self.assertAlmostEqual(es.yi, math.log(0.5), places=6)
        self.assertAlmostEqual(es.vi, 0.13, places=6)

    def test_continuity_correction_on_zero_cell(self):
        # events_t=0 → all cells +0.5; corrected flag set.
        es = ma.binary_effect(
            "zerocell", events_t=0, n_t=10, events_c=5, n_c=10,
            measure="OR", pmid="222",
        )
        self.assertTrue(es.corrected)
        # a=0.5,b=10.5,c=5.5,d=5.5 → OR=(0.5*5.5)/(10.5*5.5)=0.047619
        self.assertAlmostEqual(es.yi, math.log(0.047619047619), places=5)
        self.assertAlmostEqual(es.vi, 2.0 + 1/10.5 + 1/5.5 + 1/5.5, places=6)

    def test_impossible_counts_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.binary_effect("x", events_t=11, n_t=10, events_c=1, n_c=10, pmid="1")
        with self.assertRaises(ma.MetaAnalysisError):
            ma.binary_effect("x", events_t=1, n_t=0, events_c=1, n_c=10, pmid="1")

    def test_bad_measure_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.binary_effect("x", events_t=1, n_t=10, events_c=1, n_c=10,
                             measure="HR", pmid="1")


class ContinuousConstructorTests(unittest.TestCase):
    def test_mean_difference(self):
        # MD = 10-8 = 2; var = 4/50 + 9/50 = 0.26
        es = ma.continuous_effect(
            "cts", mean_t=10, sd_t=2, n_t=50, mean_c=8, sd_c=3, n_c=50,
            measure="MD", pmid="333",
        )
        self.assertAlmostEqual(es.yi, 2.0, places=9)
        self.assertAlmostEqual(es.vi, 0.26, places=9)

    def test_standardized_mean_difference_hedges_g(self):
        # sp=sqrt(637/98)=2.549510; d=0.784465; J=1-3/391=0.9923274
        # g=0.778446; var_g=J^2*((100/2500)+d^2/(2*98))=0.042491
        es = ma.continuous_effect(
            "smd", mean_t=10, sd_t=2, n_t=50, mean_c=8, sd_c=3, n_c=50,
            measure="SMD", pmid="444",
        )
        self.assertAlmostEqual(es.yi, 0.778446, places=4)
        self.assertAlmostEqual(es.vi, 0.042491, places=4)

    def test_smd_sign_follows_difference(self):
        es = ma.continuous_effect(
            "neg", mean_t=8, sd_t=2, n_t=40, mean_c=10, sd_c=2, n_c=40,
            measure="SMD", pmid="555",
        )
        self.assertLess(es.yi, 0.0)

    def test_small_arm_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.continuous_effect("x", mean_t=1, sd_t=1, n_t=1, mean_c=0,
                                 sd_c=1, n_c=10, pmid="1")

    def test_zero_sd_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.continuous_effect("x", mean_t=1, sd_t=0, n_t=10, mean_c=0,
                                 sd_c=1, n_c=10, pmid="1")


class PoolingReferenceTests(unittest.TestCase):
    """Worked example with hand-computed reference values.

    Study1: yi=0.10, vi=0.01 (w=100); Study2: yi=0.50, vi=0.04 (w=25).
      fixed = 22.5/125 = 0.18; var = 1/125 = 0.008; se = 0.0894427
      Q = 100*(.1-.18)^2 + 25*(.5-.18)^2 = 0.64 + 2.56 = 3.20; df=1
      I² = (3.2-1)/3.2 = 68.75%
      C  = 125 - (100^2+25^2)/125 = 40; τ² = 2.2/40 = 0.055
      random est = 0.262503; random se = 0.196453
    """

    def setUp(self):
        self.s1 = ma.EffectSize(study_id="S1", yi=0.10, vi=0.01, pmid="1")
        self.s2 = ma.EffectSize(study_id="S2", yi=0.50, vi=0.04, pmid="2")
        self.res = ma.meta_analyze([self.s1, self.s2], measure="generic")

    def test_fixed_effect(self):
        self.assertAlmostEqual(self.res.fixed_estimate, 0.18, places=9)
        lo, hi = self.res.fixed_ci
        self.assertAlmostEqual(lo, 0.18 - 1.959963984540054 * math.sqrt(0.008), places=6)
        self.assertAlmostEqual(hi, 0.18 + 1.959963984540054 * math.sqrt(0.008), places=6)

    def test_cochran_q_and_i2(self):
        self.assertAlmostEqual(self.res.q, 3.20, places=6)
        self.assertEqual(self.res.q_df, 1)
        self.assertAlmostEqual(self.res.i_squared, 68.75, places=4)

    def test_tau_squared(self):
        self.assertAlmostEqual(self.res.tau_squared, 0.055, places=6)

    def test_random_effect(self):
        self.assertAlmostEqual(self.res.random_estimate, 0.262503, places=5)
        # τ² > 0 ⇒ random CI strictly wider than fixed CI.
        f_lo, f_hi = self.res.fixed_ci
        r_lo, r_hi = self.res.random_ci
        self.assertGreater(r_hi - r_lo, f_hi - f_lo)

    def test_q_p_value(self):
        # χ²(1) survival at 3.20 ≈ 0.0736.
        self.assertAlmostEqual(self.res.q_p, 0.0736, places=3)

    def test_inconsistency_serious_at_i2_68(self):
        self.assertEqual(self.res.inconsistency, "serious")
        self.assertTrue(self.res.inconsistency_serious)
        self.assertEqual(self.res.downgrade_steps, 1)


class HeterogeneityRegimeTests(unittest.TestCase):
    def test_identical_studies_zero_heterogeneity(self):
        a = ma.EffectSize(study_id="A", yi=0.2, vi=0.01, pmid="1")
        b = ma.EffectSize(study_id="B", yi=0.2, vi=0.01, pmid="2")
        res = ma.meta_analyze([a, b])
        self.assertAlmostEqual(res.q, 0.0, places=9)
        self.assertEqual(res.i_squared, 0.0)
        self.assertAlmostEqual(res.tau_squared, 0.0, places=9)
        self.assertEqual(res.inconsistency, "not serious")
        self.assertFalse(res.inconsistency_serious)
        # Fixed and random estimates coincide when τ²=0.
        self.assertAlmostEqual(res.fixed_estimate, res.random_estimate, places=9)

    def test_extreme_divergence_very_serious(self):
        # yi 0.0 vs 1.0, vi 0.01 each → Q=50, df=1, I²=98% → very serious.
        a = ma.EffectSize(study_id="A", yi=0.0, vi=0.01, pmid="1")
        b = ma.EffectSize(study_id="B", yi=1.0, vi=0.01, pmid="2")
        res = ma.meta_analyze([a, b])
        self.assertGreaterEqual(res.i_squared, 75.0)
        self.assertEqual(res.inconsistency, "very serious")
        self.assertTrue(res.inconsistency_serious)
        self.assertEqual(res.downgrade_steps, 2)
        self.assertFalse(res.all_cis_overlap_pooled)

    def test_single_study_inconsistency_not_assessable(self):
        a = ma.EffectSize(study_id="A", yi=0.3, vi=0.02, pmid="1")
        res = ma.meta_analyze([a])
        self.assertEqual(res.k, 1)
        self.assertEqual(res.q, 0.0)
        self.assertEqual(res.i_squared, 0.0)
        self.assertEqual(res.q_df, 0)
        self.assertIn("single study", res.inconsistency)
        self.assertFalse(res.inconsistency_serious)
        # With one study, fixed == random == the study estimate.
        self.assertAlmostEqual(res.fixed_estimate, 0.3, places=9)
        self.assertAlmostEqual(res.random_estimate, 0.3, places=9)


class RatioMeasureDisplayTests(unittest.TestCase):
    def test_or_pooled_on_log_scale_displayed_exponentiated(self):
        e1 = ma.binary_effect("T1", events_t=10, n_t=100, events_c=20, n_c=100,
                              measure="OR", pmid="1")
        e2 = ma.binary_effect("T2", events_t=12, n_t=100, events_c=22, n_c=100,
                              measure="OR", pmid="2")
        res = ma.meta_analyze([e1, e2])
        self.assertTrue(res.log_scale)
        # Both ORs < 1 ⇒ pooled OR display < 1 and equals exp(log estimate).
        self.assertAlmostEqual(
            res.random_estimate_display, math.exp(res.random_estimate), places=9
        )
        self.assertLess(res.random_estimate_display, 1.0)
        self.assertEqual(res.null_value_display, 1.0)

    def test_md_not_log_scale(self):
        e1 = ma.continuous_effect("C1", mean_t=10, sd_t=2, n_t=50,
                                  mean_c=8, sd_c=2, n_c=50, measure="MD", pmid="1")
        e2 = ma.continuous_effect("C2", mean_t=11, sd_t=2, n_t=50,
                                  mean_c=8, sd_c=2, n_c=50, measure="MD", pmid="2")
        res = ma.meta_analyze([e1, e2])
        self.assertFalse(res.log_scale)
        self.assertEqual(res.random_estimate_display, res.random_estimate)
        self.assertEqual(res.null_value_display, 0.0)


class PredictionIntervalTests(unittest.TestCase):
    """Hand-verified k=3 example with high heterogeneity.

    Three studies yi = 0.0, 0.4, 0.8, each vi = 0.04:
      fixed = 0.4; Q = 8 (df=2) → I²=75%; C=50 → τ²=0.12
      random = 0.4, Var(μ̂)=1/18.75=0.053333
      PI = 0.4 ± t_{1,0.975}·√(0.12+0.053333)
         = 0.4 ± 12.706205·0.416333 = (−4.8901, 5.6901)
      CI = 0.4 ± 1.959964·0.230940 = (−0.0526, 0.8526)
    """

    def setUp(self):
        self.res = ma.meta_analyze([
            ma.EffectSize(study_id="S1", yi=0.0, vi=0.04, pmid="1"),
            ma.EffectSize(study_id="S2", yi=0.4, vi=0.04, pmid="2"),
            ma.EffectSize(study_id="S3", yi=0.8, vi=0.04, pmid="3"),
        ])

    def test_prediction_interval_reference(self):
        self.assertIsNotNone(self.res.prediction_interval)
        lo, hi = self.res.prediction_interval
        self.assertAlmostEqual(lo, -4.8901, places=3)
        self.assertAlmostEqual(hi, 5.6901, places=3)

    def test_pi_wider_than_ci_under_heterogeneity(self):
        pi_lo, pi_hi = self.res.prediction_interval
        ci_lo, ci_hi = self.res.random_ci
        self.assertGreater(pi_hi - pi_lo, ci_hi - ci_lo)

    def test_pi_none_below_three_studies(self):
        res = ma.meta_analyze([
            ma.EffectSize(study_id="A", yi=0.1, vi=0.01, pmid="1"),
            ma.EffectSize(study_id="B", yi=0.5, vi=0.04, pmid="2"),
        ])
        self.assertIsNone(res.prediction_interval)
        self.assertIsNone(res.prediction_interval_display)

    def test_ratio_measure_pi_displayed_exponentiated(self):
        res = ma.meta_analyze([
            ma.binary_effect("T1", events_t=10, n_t=100, events_c=20, n_c=100,
                             measure="OR", pmid="1"),
            ma.binary_effect("T2", events_t=30, n_t=100, events_c=20, n_c=100,
                             measure="OR", pmid="2"),
            ma.binary_effect("T3", events_t=12, n_t=100, events_c=22, n_c=100,
                             measure="OR", pmid="3"),
        ])
        lo, hi = res.prediction_interval
        dlo, dhi = res.prediction_interval_display
        self.assertAlmostEqual(dlo, math.exp(lo), places=9)
        self.assertAlmostEqual(dhi, math.exp(hi), places=9)

    def test_t_critical_known_values(self):
        self.assertAlmostEqual(ma._t_critical(0.95, 1), 12.706205, places=3)
        self.assertAlmostEqual(ma._t_critical(0.95, 5), 2.570582, places=4)
        self.assertAlmostEqual(ma._t_critical(0.95, 10), 2.228139, places=4)

    def test_markdown_shows_prediction_interval(self):
        md = ma.render_markdown(self.res)
        self.assertIn("prediction interval", md.lower())

    def test_to_dict_carries_prediction_interval(self):
        d = self.res.to_dict()
        self.assertIsNotNone(d["random"]["prediction_interval"])
        self.assertEqual(len(d["random"]["prediction_interval"]), 2)


class GradeBridgeTests(unittest.TestCase):
    """The whole point: a quantitative inconsistency finding must flow into
    the existing GRADE machinery and actually move the certainty grade."""

    def test_serious_inconsistency_downgrades_level_a_to_b(self):
        a = ma.EffectSize(study_id="A", yi=0.0, vi=0.01, pmid="1")
        b = ma.EffectSize(study_id="B", yi=1.0, vi=0.01, pmid="2")
        res = ma.meta_analyze([a, b])
        graded = apply_grade_modifiers(
            EvidenceLevel.A,
            inconsistency_serious=res.inconsistency_serious,
        )
        self.assertEqual(graded, EvidenceLevel.B)

    def test_no_inconsistency_keeps_level_a(self):
        a = ma.EffectSize(study_id="A", yi=0.2, vi=0.01, pmid="1")
        b = ma.EffectSize(study_id="B", yi=0.2, vi=0.01, pmid="2")
        res = ma.meta_analyze([a, b])
        graded = apply_grade_modifiers(
            EvidenceLevel.A,
            inconsistency_serious=res.inconsistency_serious,
        )
        self.assertEqual(graded, EvidenceLevel.A)


class RefusalTests(unittest.TestCase):
    def test_empty_study_set_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.meta_analyze([])

    def test_unknown_measure_refused(self):
        a = ma.EffectSize(study_id="A", yi=0.2, vi=0.01, pmid="1")
        with self.assertRaises(ma.MetaAnalysisError):
            ma.meta_analyze([a], measure="bogus")

    def test_bad_confidence_refused(self):
        a = ma.EffectSize(study_id="A", yi=0.2, vi=0.01, pmid="1")
        with self.assertRaises(ma.MetaAnalysisError):
            ma.meta_analyze([a, a], confidence=1.5)


class NumericsTests(unittest.TestCase):
    def test_chi2_sf_known_values(self):
        # χ²(1): survival at 3.841 ≈ 0.05; at 0 → 1.0
        self.assertAlmostEqual(ma._chi2_sf(3.8414588, 1), 0.05, places=4)
        self.assertEqual(ma._chi2_sf(0.0, 1), 1.0)
        # χ²(2): survival at 5.991 ≈ 0.05
        self.assertAlmostEqual(ma._chi2_sf(5.9914645, 2), 0.05, places=4)

    def test_two_sided_p_of_196(self):
        self.assertAlmostEqual(ma._two_sided_p(1.959963984540054), 0.05, places=5)
        self.assertAlmostEqual(ma._two_sided_p(0.0), 1.0, places=9)

    def test_z_critical_tabled_and_computed(self):
        self.assertAlmostEqual(ma._z_critical(0.95), 1.959963984540054, places=9)
        self.assertAlmostEqual(ma._z_critical(0.90), 1.6448536269514722, places=9)
        # Non-tabled level falls through to the inverse-normal path.
        self.assertAlmostEqual(ma._z_critical(0.975), 2.241402727, places=5)

    def test_inv_norm_cdf_matches_known_quantiles(self):
        self.assertAlmostEqual(ma._inv_norm_cdf(0.975), 1.959963985, places=6)
        self.assertAlmostEqual(ma._inv_norm_cdf(0.5), 0.0, places=9)


class RenderAndSerializeTests(unittest.TestCase):
    def setUp(self):
        self.res = ma.meta_analyze([
            ma.EffectSize(study_id="Devinsky 2017", yi=-0.4, vi=0.02, pmid="28538134"),
            ma.EffectSize(study_id="Thiele 2018", yi=-0.3, vi=0.03, pmid="29501248"),
        ], measure="OR")

    def test_markdown_contains_identifiers_and_verdict(self):
        md = ma.render_markdown(self.res)
        self.assertIn("PMID:28538134", md)
        self.assertIn("PMID:29501248", md)
        self.assertIn("Random effects", md)
        self.assertIn("I²", md)
        self.assertIn("GRADE inconsistency", md)

    def test_to_dict_is_json_serializable(self):
        d = self.res.to_dict()
        blob = json.dumps(d)  # must not raise
        round_trip = json.loads(blob)
        self.assertEqual(round_trip["k"], 2)
        self.assertIn("heterogeneity", round_trip)
        self.assertIn("grade_inconsistency", round_trip)
        self.assertEqual(len(round_trip["studies"]), 2)

    def test_determinism_byte_identical(self):
        self.assertEqual(ma.render_markdown(self.res), ma.render_markdown(self.res))


class CliMetaTests(unittest.TestCase):
    def _run(self, argv):
        from cannavec_science.__main__ import main
        return main(argv)

    def _write(self, payload):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "studies.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_generic_pooling_json(self):
        import io
        import contextlib
        path = self._write({
            "measure": "generic",
            "studies": [
                {"study_id": "S1", "pmid": "1", "yi": 0.1, "vi": 0.01},
                {"study_id": "S2", "pmid": "2", "yi": 0.5, "vi": 0.04},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path, "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertAlmostEqual(out["fixed"]["estimate"], 0.18, places=6)
        self.assertEqual(out["grade_inconsistency"]["verdict"], "serious")

    def test_binary_pooling_markdown(self):
        import io
        import contextlib
        path = self._write({
            "measure": "OR",
            "studies": [
                {"study_id": "T1", "pmid": "1", "events_t": 10, "n_t": 100,
                 "events_c": 20, "n_c": 100},
                {"study_id": "T2", "doi": "10.x", "events_t": 12, "n_t": 100,
                 "events_c": 22, "n_c": 100},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path])
        self.assertEqual(rc, 0)
        self.assertIn("Meta-analysis — OR", buf.getvalue())

    def test_missing_identifier_refused_nonzero(self):
        import io
        import contextlib
        path = self._write({
            "measure": "generic",
            "studies": [{"study_id": "anon", "yi": 0.2, "vi": 0.04}],
        })
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = self._run(["meta", path])
        self.assertNotEqual(rc, 0)
        self.assertIn("§I", err.getvalue())

    def test_empty_studies_refused_nonzero(self):
        import io
        import contextlib
        path = self._write({"measure": "generic", "studies": []})
        with contextlib.redirect_stderr(io.StringIO()):
            rc = self._run(["meta", path])
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
