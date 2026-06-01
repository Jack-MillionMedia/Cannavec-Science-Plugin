"""Tests for subgroup analysis and trim-and-fill (spec 014).

Reference values are hand-derived in the docstrings. Constitution §III:
positive + negative + refusal cases for every public function.
"""

import contextlib
import io
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cannavec_science import meta_analysis as ma


class SubgroupReferenceTests(unittest.TestCase):
    """Two subgroups of two studies each (equal vi = 0.04):

      low : 0.2, 0.4 → fixed M=0.3, Var=0.02, Q_low=0.5
      high: 1.0, 1.2 → fixed M=1.1, Var=0.02, Q_high=0.5
      overall (subgroup summaries) M̄ = 0.7
      Q_between = 50·(0.3−0.7)² + 50·(1.1−0.7)² = 16.0, df=1
      Decomposition check: Q_total=17.0, ΣQ_within=1.0 → 17−1 = 16.0 ✓
      I²_between = (16−1)/16 = 93.75%
    """

    def _effects(self):
        return [
            ma.EffectSize(study_id="S1", yi=0.2, vi=0.04, pmid="1", subgroup="low"),
            ma.EffectSize(study_id="S2", yi=0.4, vi=0.04, pmid="2", subgroup="low"),
            ma.EffectSize(study_id="S3", yi=1.0, vi=0.04, pmid="3", subgroup="high"),
            ma.EffectSize(study_id="S4", yi=1.2, vi=0.04, pmid="4", subgroup="high"),
        ]

    def test_subgroup_estimates_fixed(self):
        res = ma.subgroup_analysis(self._effects(), model="fixed")
        by = {r.label: r for r in res.subgroups}
        self.assertAlmostEqual(by["low"].estimate, 0.3, places=6)
        self.assertAlmostEqual(by["high"].estimate, 1.1, places=6)
        self.assertEqual(by["low"].k, 2)

    def test_q_between_reference(self):
        res = ma.subgroup_analysis(self._effects(), model="fixed")
        self.assertAlmostEqual(res.q_between, 16.0, places=4)
        self.assertEqual(res.q_between_df, 1)
        self.assertAlmostEqual(res.i_squared_between, 93.75, places=2)
        self.assertTrue(res.significant)
        self.assertLess(res.q_between_p, 0.001)

    def test_decomposition_matches_subgroup_summary_formula(self):
        # Q_total − ΣQ_within should equal the subgroup-summary Q_between.
        effects = self._effects()
        overall = ma.meta_analyze(effects, measure="generic")
        q_total = overall.q
        q_within = 0.0
        for label in ("low", "high"):
            members = [e for e in effects if e.subgroup == label]
            q_within += ma.meta_analyze(members).q
        res = ma.subgroup_analysis(effects, model="fixed")
        self.assertAlmostEqual(res.q_between, q_total - q_within, places=6)

    def test_random_model_also_significant(self):
        # Within-subgroup τ² = 0 here, so random ≈ fixed.
        res = ma.subgroup_analysis(self._effects(), model="random")
        self.assertAlmostEqual(res.q_between, 16.0, places=3)
        self.assertTrue(res.significant)

    def test_no_difference_when_subgroups_agree(self):
        effects = [
            ma.EffectSize(study_id="A", yi=0.50, vi=0.04, pmid="1", subgroup="x"),
            ma.EffectSize(study_id="B", yi=0.52, vi=0.04, pmid="2", subgroup="x"),
            ma.EffectSize(study_id="C", yi=0.49, vi=0.04, pmid="3", subgroup="y"),
            ma.EffectSize(study_id="D", yi=0.51, vi=0.04, pmid="4", subgroup="y"),
        ]
        res = ma.subgroup_analysis(effects, model="fixed")
        self.assertFalse(res.significant)
        self.assertGreater(res.q_between_p, 0.05)

    def test_ratio_measure_display_exponentiated(self):
        effects = [
            ma.binary_effect("T1", events_t=10, n_t=100, events_c=20, n_c=100,
                             measure="OR", pmid="1", subgroup="a"),
            ma.binary_effect("T2", events_t=12, n_t=100, events_c=22, n_c=100,
                             measure="OR", pmid="2", subgroup="a"),
            ma.binary_effect("T3", events_t=30, n_t=100, events_c=20, n_c=100,
                             measure="OR", pmid="3", subgroup="b"),
            ma.binary_effect("T4", events_t=33, n_t=100, events_c=21, n_c=100,
                             measure="OR", pmid="4", subgroup="b"),
        ]
        res = ma.subgroup_analysis(effects, model="fixed")
        for r in res.subgroups:
            self.assertAlmostEqual(r.estimate_display, math.exp(r.estimate), places=9)

    def test_requires_two_subgroups(self):
        one = [
            ma.EffectSize(study_id="A", yi=0.2, vi=0.04, pmid="1", subgroup="only"),
            ma.EffectSize(study_id="B", yi=0.4, vi=0.04, pmid="2", subgroup="only"),
        ]
        with self.assertRaises(ma.MetaAnalysisError):
            ma.subgroup_analysis(one)

    def test_requires_subgroup_labels(self):
        unlabelled = [
            ma.EffectSize(study_id="A", yi=0.2, vi=0.04, pmid="1"),
            ma.EffectSize(study_id="B", yi=0.4, vi=0.04, pmid="2"),
        ]
        with self.assertRaises(ma.MetaAnalysisError):
            ma.subgroup_analysis(unlabelled)

    def test_bad_model_refused(self):
        with self.assertRaises(ma.MetaAnalysisError):
            ma.subgroup_analysis(self._effects(), model="bogus")

    def test_render_and_to_dict(self):
        res = ma.subgroup_analysis(self._effects(), model="fixed")
        md = ma.render_subgroups(res)
        self.assertIn("Subgroup analysis", md)
        self.assertIn("subgroup differences", md)
        d = res.to_dict()
        json.dumps(d)  # serializable
        self.assertEqual(len(d["subgroups"]), 2)


class TrimFillSymmetricTests(unittest.TestCase):
    """Symmetric funnel (0.3..0.7, vi=0.05) → 0 imputed, estimate unchanged."""

    def test_symmetric_imputes_zero(self):
        effects = [
            ma.EffectSize(study_id=f"S{i}", yi=y, vi=0.05, pmid=str(i))
            for i, y in enumerate([0.3, 0.4, 0.5, 0.6, 0.7], start=1)
        ]
        res = ma.trim_and_fill(effects, model="fixed")
        self.assertEqual(res.k_imputed, 0)
        self.assertEqual(len(res.imputed_studies), 0)
        self.assertAlmostEqual(res.observed_estimate, 0.5, places=6)
        self.assertAlmostEqual(res.adjusted_estimate, 0.5, places=6)


class TrimFillAsymmetricReferenceTests(unittest.TestCase):
    """Asymmetric funnel: y = −0.5, 0.3, 0.4, 0.5, 0.6 (vi = 0.05 each).

      observed fixed estimate = 1.3/5 = 0.26
      L0 → k0 = 1 (right over-represented; suppressed on the left)
      trimmed-4 centre = 0.7/4 = 0.175 → impute mirror of 0.6 → −0.25
      augmented (6 studies) fixed estimate = 1.05/6 = 0.175
    """

    def setUp(self):
        self.effects = [
            ma.EffectSize(study_id=f"S{i}", yi=y, vi=0.05, pmid=str(i))
            for i, y in enumerate([-0.5, 0.3, 0.4, 0.5, 0.6], start=1)
        ]
        self.res = ma.trim_and_fill(self.effects, model="fixed")

    def test_one_study_imputed_on_left(self):
        self.assertEqual(self.res.k_imputed, 1)
        self.assertEqual(self.res.impute_side, "left")
        self.assertEqual(len(self.res.imputed_studies), 1)

    def test_observed_and_adjusted_estimates(self):
        self.assertAlmostEqual(self.res.observed_estimate, 0.26, places=5)
        self.assertAlmostEqual(self.res.adjusted_estimate, 0.175, places=5)
        # Adjustment pulls the estimate toward the suppressed (left) side.
        self.assertLess(self.res.adjusted_estimate, self.res.observed_estimate)

    def test_imputed_effect_value(self):
        self.assertAlmostEqual(self.res.imputed_studies[0].effect, -0.25, places=5)
        self.assertAlmostEqual(self.res.imputed_studies[0].variance, 0.05, places=6)

    def test_imputed_study_is_flagged_hypothetical(self):
        self.assertIn("not a primary source", self.res.imputed_studies[0].note)

    def test_determinism(self):
        a = ma.trim_and_fill(self.effects, model="fixed").to_dict()
        b = ma.trim_and_fill(self.effects, model="fixed").to_dict()
        self.assertEqual(a, b)


class TrimFillMiscTests(unittest.TestCase):
    def test_requires_three_studies(self):
        two = [
            ma.EffectSize(study_id="A", yi=0.1, vi=0.05, pmid="1"),
            ma.EffectSize(study_id="B", yi=0.2, vi=0.05, pmid="2"),
        ]
        with self.assertRaises(ma.MetaAnalysisError):
            ma.trim_and_fill(two)

    def test_bad_side_refused(self):
        effects = [
            ma.EffectSize(study_id=f"S{i}", yi=y, vi=0.05, pmid=str(i))
            for i, y in enumerate([0.1, 0.2, 0.3], start=1)
        ]
        with self.assertRaises(ma.MetaAnalysisError):
            ma.trim_and_fill(effects, side="sideways")

    def test_forced_side_right(self):
        # Mirror of the asymmetric reference: excess on the left → impute right.
        effects = [
            ma.EffectSize(study_id=f"S{i}", yi=y, vi=0.05, pmid=str(i))
            for i, y in enumerate([0.5, -0.3, -0.4, -0.5, -0.6], start=1)
        ]
        res = ma.trim_and_fill(effects, model="fixed", side="right")
        self.assertEqual(res.impute_side, "right")
        self.assertGreaterEqual(res.k_imputed, 1)
        self.assertGreater(res.adjusted_estimate, res.observed_estimate)

    def test_ratio_measure_display(self):
        effects = [
            ma.binary_effect("T1", events_t=2, n_t=40, events_c=8, n_c=40,
                             measure="OR", pmid="1"),
            ma.binary_effect("T2", events_t=3, n_t=42, events_c=9, n_c=41,
                             measure="OR", pmid="2"),
            ma.binary_effect("T3", events_t=40, n_t=200, events_c=52, n_c=200,
                             measure="OR", pmid="3"),
            ma.binary_effect("T4", events_t=45, n_t=210, events_c=55, n_c=205,
                             measure="OR", pmid="4"),
        ]
        res = ma.trim_and_fill(effects, model="fixed")
        self.assertTrue(res.log_scale)
        self.assertAlmostEqual(
            res.adjusted_estimate_display, math.exp(res.adjusted_estimate), places=9
        )
        for s in res.imputed_studies:
            self.assertAlmostEqual(s.effect_display, math.exp(s.effect), places=9)

    def test_render(self):
        effects = [
            ma.EffectSize(study_id=f"S{i}", yi=y, vi=0.05, pmid=str(i))
            for i, y in enumerate([-0.5, 0.3, 0.4, 0.5, 0.6], start=1)
        ]
        md = ma.render_trim_fill(ma.trim_and_fill(effects, model="fixed"))
        self.assertIn("Trim-and-fill", md)
        self.assertIn("Bias-adjusted estimate", md)


class PoolEstimateAndRankTests(unittest.TestCase):
    def test_pool_estimate_fixed_equal_weights_is_mean(self):
        est, var = ma._pool_estimate([0.0, 0.4, 0.8], [0.04, 0.04, 0.04], "fixed")
        self.assertAlmostEqual(est, 0.4, places=9)
        self.assertAlmostEqual(var, 0.04 / 3.0, places=9)

    def test_pool_estimate_random_matches_meta_analyze(self):
        effects = [
            ma.EffectSize(study_id="S1", yi=0.0, vi=0.04, pmid="1"),
            ma.EffectSize(study_id="S2", yi=0.4, vi=0.04, pmid="2"),
            ma.EffectSize(study_id="S3", yi=0.8, vi=0.04, pmid="3"),
        ]
        ref = ma.meta_analyze(effects)
        est, _ = ma._pool_estimate([0.0, 0.4, 0.8], [0.04, 0.04, 0.04], "random")
        self.assertAlmostEqual(est, ref.random_estimate, places=9)

    def test_rankdata_average_ties(self):
        # values 0.2, 0.1, 0.1, 0.3 → ranks 3, 1.5, 1.5, 4
        self.assertEqual(ma._rankdata([0.2, 0.1, 0.1, 0.3]), [3.0, 1.5, 1.5, 4.0])


class CliAdvancedDiagnosticsTests(unittest.TestCase):
    def _run(self, argv):
        from cannavec_science.__main__ import main
        return main(argv)

    def _write(self, payload):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "studies.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_diagnostics_includes_trimfill_and_subgroups(self):
        path = self._write({
            "measure": "generic",
            "studies": [
                {"study_id": "S1", "pmid": "1", "yi": 0.2, "vi": 0.04, "subgroup": "low"},
                {"study_id": "S2", "pmid": "2", "yi": 0.4, "vi": 0.04, "subgroup": "low"},
                {"study_id": "S3", "pmid": "3", "yi": 1.0, "vi": 0.04, "subgroup": "high"},
                {"study_id": "S4", "pmid": "4", "yi": 1.2, "vi": 0.04, "subgroup": "high"},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path, "--diagnostics", "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertIn("trim_and_fill", out)
        self.assertEqual(out["trim_and_fill"]["k_observed"], 4)
        self.assertIn("subgroup_analysis", out)
        self.assertAlmostEqual(out["subgroup_analysis"]["q_between"], 16.0, places=3)

    def test_diagnostics_markdown_sections(self):
        path = self._write({
            "measure": "generic",
            "studies": [
                {"study_id": "S1", "pmid": "1", "yi": -0.5, "vi": 0.05, "subgroup": "a"},
                {"study_id": "S2", "pmid": "2", "yi": 0.3, "vi": 0.05, "subgroup": "a"},
                {"study_id": "S3", "pmid": "3", "yi": 0.4, "vi": 0.05, "subgroup": "b"},
                {"study_id": "S4", "pmid": "4", "yi": 0.6, "vi": 0.05, "subgroup": "b"},
            ],
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self._run(["meta", path, "--diagnostics"])
        self.assertEqual(rc, 0)
        text = buf.getvalue()
        self.assertIn("Trim-and-fill", text)
        self.assertIn("Subgroup analysis", text)


if __name__ == "__main__":
    unittest.main()
